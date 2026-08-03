#!/usr/bin/env python3
"""Remove a lane worktree only after proving its work is discoverable (#686)."""

from __future__ import annotations

import argparse
import fcntl
import os
import stat
import subprocess
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

try:
    from lane_runner_identity import is_lane_runner
except ModuleNotFoundError as exc:
    if exc.name != "lane_runner_identity":
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from lane_runner_identity import is_lane_runner

try:
    from dev.land_lane import _read_gate_in_flight
except ModuleNotFoundError as exc:
    if exc.name != "dev":
        raise
    from land_lane import _read_gate_in_flight


@dataclass(frozen=True)
class StatusPath:
    kind: str
    path: str


@dataclass(frozen=True)
class WorktreeLiveness:
    """Processes whose current directory is inside a worktree.

    ``unknown`` is deliberately separate from an empty ``pids`` tuple: an
    incomplete process-table scan cannot safely prove that a lane is idle.
    """

    pids: tuple[int, ...]
    unknown: tuple[str, ...]


def worktree_liveness(target: Path) -> WorktreeLiveness:
    """Find known lane runners whose cwd is inside ``target``.

    Runner identity comes from the repo's shared argv[0] classifier.  This
    avoids making unrelated same-user processes with protected cwd links a
    fleet-wide veto while an unreadable *runner* cwd remains unknown.
    """
    target = target.resolve()
    live: list[int] = []
    unknown: list[str] = []
    try:
        entries = tuple(os.scandir("/proc"))
    except OSError as exc:
        return WorktreeLiveness((), (f"/proc: {exc}",))

    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            if entry.stat(follow_symlinks=False).st_uid != os.geteuid():
                continue
        except (FileNotFoundError, ProcessLookupError):
            continue
        except OSError as exc:
            unknown.append(f"pid {pid}: cannot identify owner: {exc.strerror or exc}")
            continue
        try:
            raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        except (FileNotFoundError, ProcessLookupError):
            continue
        except OSError as exc:
            # Identity failure is not evidence that the process is unrelated.
            # The current fleet has no unreadable same-uid cmdlines; if one
            # appears, refuse rather than turn it into a false idle verdict.
            unknown.append(f"pid {pid}: cannot read cmdline: {exc.strerror or exc}")
            continue
        if not is_lane_runner(raw):
            continue
        try:
            cwd = os.readlink(f"/proc/{pid}/cwd")
        except (FileNotFoundError, ProcessLookupError):
            continue
        except OSError as exc:
            unknown.append(f"pid {pid}: {exc.strerror or exc}")
            continue
        try:
            inside = os.path.commonpath((str(target), cwd)) == str(target)
        except (OSError, ValueError):
            unknown.append(f"pid {pid}: invalid cwd {cwd!r}")
            continue
        if inside:
            live.append(pid)
    return WorktreeLiveness(tuple(sorted(live)), tuple(unknown))


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        check=False,
    )


def _text(result: subprocess.CompletedProcess[bytes]) -> str:
    return result.stdout.decode("utf-8", errors="surrogateescape").strip()


def _registered_worktrees(target: Path) -> list[Path] | None:
    result = _git(target, "worktree", "list", "--porcelain")
    if result.returncode:
        return None
    paths = []
    for line in _text(result).splitlines():
        if line.startswith("worktree "):
            paths.append(Path(line.removeprefix("worktree ")).resolve())
    return paths or None


def _status_paths(target: Path) -> list[StatusPath] | None:
    result = _git(
        target,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--ignored",
    )
    if result.returncode:
        return None
    fields = result.stdout.split(b"\0")
    rows: list[StatusPath] = []
    index = 0
    while index < len(fields) and fields[index]:
        field = fields[index]
        if len(field) < 4:
            return None
        code = field[:2].decode("ascii", errors="replace")
        path = field[3:].decode("utf-8", errors="surrogateescape")
        index += 1
        if "R" in code or "C" in code:
            if index >= len(fields) or not fields[index]:
                return None
            old = fields[index].decode("utf-8", errors="surrogateescape")
            path = f"{old} -> {path}"
            index += 1
        kind = "untracked" if code == "??" else "ignored" if code == "!!" else "tracked"
        rows.append(StatusPath(kind, path))
    return rows


def _unmerged_commits(target: Path, base: str) -> list[tuple[str, str]] | None:
    base_result = _git(target, "rev-parse", "--verify", f"{base}^{{commit}}")
    if base_result.returncode:
        return None
    result = _git(target, "cherry", base, "HEAD")
    if result.returncode:
        return None
    commits = []
    for line in _text(result).splitlines():
        if not line.startswith("+ "):
            continue
        sha = line[2:].strip()
        subject_result = _git(target, "show", "-s", "--format=%s", sha)
        if subject_result.returncode:
            return None
        commits.append((sha, _text(subject_result)))
    return commits


# The one untracked file genuinely present in every lane: the coordinator
# writes BRIEF.md into each worktree and never tracks it. A literal of one
# filename is the honest smaller thing (#612) — it is a fact about the lane
# model, not a computed value to derive-and-restate (#596/#661). Anything
# untracked that is NOT in this set is named, because it may be work.
#
# `.dreamwork/lane-*-report.md` is deliberately NOT here: it is the lane
# deliverable, untracked until committed, and suppressing it would hide the
# one signal this tool exists to surface (#760/#136). It is named like any
# other unexpected untracked path; the tool does not pretend to classify work
# from scratch beyond this literal (#702), and the path name speaks for itself.
EXPECTED_UNTRACKED = frozenset({"BRIEF.md"})

# This is deliberately an allowlist of things known to be reproducible. Any
# unfamiliar ignored path falls through and is named. ``__pycache__`` is not a
# directory-prefix rule: normal contents are already covered by ``*.pyc``, and
# a hand-written note hidden inside that directory is still evidence.
DISPOSABLE_IGNORED_DIRS = frozenset({".pytest_cache", ".ruff_cache", "node_modules"})

# The ledger's existence is not its lifecycle marker: the one-way cutover is a
# watermark inside a valid SQLite store (ledger_parse.source_of_truth).  Thus a
# locked, zero-byte file at this exact path cannot carry ledger state.  No
# other empty path inherits that conclusion; sentinel files can encode state
# entirely through their existence.
EMPTY_LEDGER_PATH = ".dreamwork/ledger.sqlite3"


def _is_disposable_ignored(target: Path, path: str, ownership: ExitStack) -> bool:
    parts = PurePosixPath(path).parts
    if (
        path.endswith((".pyc", ".lock"))
        or any(part in DISPOSABLE_IGNORED_DIRS for part in parts)
    ):
        return True
    if path != EMPTY_LEDGER_PATH:
        return False

    # Hold a POSIX write lock from the size check through worktree removal.
    # SQLite writers honour this lock, so content cannot become durable between
    # classification and removal.  O_NOFOLLOW keeps a symlink from borrowing
    # the exception; the inode comparison catches replacement before the lock
    # is admitted.  A raw writer that ignores advisory locks remains outside
    # what this ownership proof can prevent.
    candidate = target / path
    fd = -1
    try:
        fd = os.open(
            candidate,
            os.O_RDWR | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
        )
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        held = os.fstat(fd)
        current = os.stat(candidate, follow_symlinks=False)
        if (
            not stat.S_ISREG(held.st_mode)
            or held.st_size != 0
            or (held.st_dev, held.st_ino) != (current.st_dev, current.st_ino)
        ):
            os.close(fd)
            return False
        ownership.callback(os.close, fd)
        return True
    except OSError:
        if fd >= 0:
            os.close(fd)
        return False


def _ignored_detail(rows: list[StatusPath], notable: list[StatusPath]) -> str:
    total = len(rows)
    if total == 0:
        return "ignored: examined 0 files; NOT an all-clear"
    disposable = total - len(notable)
    noun = "file" if total == 1 else "files"
    detail = (
        f"ignored: examined {total} {noun}; {disposable} disposable, "
        f"{len(notable)} NOT disposable"
    )
    if notable:
        detail += ": " + ", ".join(row.path for row in notable)
    return detail


def _summary(
    target: Path,
    tracked: int | str,
    untracked: int | str,
    ignored: int | str,
    unmerged: int | str,
    ignored_detail: str | None = None,
) -> str:
    # `untracked` and `ignored` are reported separately, never collapsed: an
    # uncommitted deliverable and a cache directory read identically under one
    # merged counter, and that is the loss this tool exists to prevent (#760).
    summary = (
        f"reap examined path={target} tracked-dirty={tracked} "
        f"untracked={untracked} ignored={ignored} unmerged-commits={unmerged}"
    )
    return summary if ignored_detail is None else f"{summary} ({ignored_detail})"


def _note_unexpected(unexpected: list[StatusPath]) -> None:
    """Name untracked paths beyond the known scratch set (#760).

    The gate does not refuse on untracked paths, so a deliverable left
    untracked reads as clean. Naming it — reporting only, never dropping (#702)
    — is what turns the count into a signal a coordinator can act on. Printed
    to stderr so it is visible alongside a passing summary on stdout.
    """
    for row in unexpected:
        print(f"NOTE: untracked path beyond expected scratch: {row.path}",
              file=sys.stderr)


def _unknown(target: Path, reason: str, *, tracked="unknown", untracked="unknown",
             ignored="unknown") -> int:
    print(_summary(target, tracked, untracked, ignored, "unknown"), file=sys.stderr)
    print(f"REFUSE: {reason}; cannot prove the lane is safe to reap", file=sys.stderr)
    return 2


def reap(target_arg: str, *, base: str = "master", force: bool = False,
         check_only: bool = False) -> int:
    target = Path(target_arg).expanduser().resolve()
    if not target.is_dir():
        return _unknown(target, "path is not a directory")

    worktrees = _registered_worktrees(target)
    if worktrees is None or target not in worktrees or target == worktrees[0]:
        return _unknown(target, "not a registered linked worktree")

    main = worktrees[0]
    gate = _read_gate_in_flight(main)
    try:
        gate_worktree = Path(gate.gate_worktree).resolve()
    except (OSError, RuntimeError):
        gate_worktree = None
    if gate.pid_live and gate_worktree == target:
        print(
            f"REFUSE: active landing gate breadcrumb {gate.path} names this "
            f"worktree (pid {gate.pid}, phase {gate.phase}); refusing to reap "
            "in-flight gate scratch",
            file=sys.stderr,
        )
        return 1

    rows = _status_paths(target)
    if rows is None:
        return _unknown(target, "git status failed")
    tracked = [row for row in rows if row.kind == "tracked"]
    untracked = [row for row in rows if row.kind == "untracked"]
    ignored = [row for row in rows if row.kind == "ignored"]
    # The untracked paths beyond the per-lane scratch set are the signal: they
    # may be a deliverable the lane forgot to commit (#760). Naming them does
    # not change the gate; it only turns a collapsed number into something a
    # coordinator can act on (#702).
    unexpected = [
        row for row in untracked if row.path not in EXPECTED_UNTRACKED
    ]

    commits = _unmerged_commits(target, base)
    if commits is None:
        return _unknown(
            target,
            f"could not compare HEAD with base `{base}`",
            tracked=len(tracked),
            untracked=len(untracked),
            ignored=len(ignored),
        )

    ownership = ExitStack()
    non_disposable_ignored = [
        row for row in ignored
        if not _is_disposable_ignored(target, row.path, ownership)
    ]
    summary = _summary(
        target,
        len(tracked),
        len(untracked),
        len(ignored),
        len(commits),
        _ignored_detail(ignored, non_disposable_ignored),
    )
    unsafe = bool(tracked or commits or non_disposable_ignored)
    stream = sys.stderr if unsafe and not force else sys.stdout
    print(summary, file=stream)
    # Name unexpected untracked paths on every classified run, not only the
    # clean one: a deliverable left untracked alongside tracked dirt is no
    # less about to be lost, and the summary line is read either way (#671).
    _note_unexpected(unexpected)

    if unsafe and not force:
        for row in tracked:
            print(f"REFUSE: tracked path would be lost: {row.path}", file=sys.stderr)
        for row in non_disposable_ignored:
            print(f"REFUSE: ignored path would be lost: {row.path}", file=sys.stderr)
        for sha, subject in commits:
            print(
                f"REFUSE: unmerged commit would become easier to delete unseen: "
                f"{sha[:12]} {subject}",
                file=sys.stderr,
            )
        print("Inspect the lane, then rerun with --force only if discarding is intended.",
              file=sys.stderr)
        ownership.close()
        return 1

    if force:
        for row in rows:
            print(f"FORCE: discarding {row.kind} path: {row.path}", file=sys.stderr)
        for sha, subject in commits:
            print(f"FORCE: overriding unmerged commit: {sha[:12]} {subject}",
                  file=sys.stderr)

    if check_only:
        print("reap gate OK (check only)")
        ownership.close()
        return 0

    # The periodic sweep scans liveness before it runs this gate, but a lane
    # can start while the gate is executing.  Re-probe here, immediately before
    # the one supported removal call, so the scan-time answer is never treated
    # as a removal-time answer.
    liveness = worktree_liveness(target)
    if liveness.unknown:
        print(
            "REFUSE: process liveness scan incomplete at removal time: "
            + "; ".join(liveness.unknown),
            file=sys.stderr,
        )
        ownership.close()
        return 1
    if liveness.pids:
        print(
            "REFUSE: active process cwd inside worktree at removal time: pids="
            + ",".join(str(pid) for pid in liveness.pids),
            file=sys.stderr,
        )
        ownership.close()
        return 1

    # git's --force and the tool's --force are two different flags (#762).
    # `git worktree remove` refuses on ANY untracked file, and BRIEF.md is
    # untracked in every lane by construction — so a lane whose gate just
    # PASSED could never be removed unless --force was also passed to git. That
    # made the tool's own --force the only spelling that worked, and a
    # coordinator who typed it habitually had silently disabled the tracked-work
    # gate — the exact "a gate people learn to --force past is worse than no
    # gate" failure #686 was built to avoid, reintroduced one layer down.
    # The tool's gate is the finer check: by the time we reach the removal it
    # has established no tracked dirt and no unmerged commit (or --force
    # overrode that refusal on purpose). git's cruder untracked-file refusal is
    # superseded, and BRIEF.md/__pycache__ are precisely what it refuses over.
    # So --force is passed to git UNCONDITIONALLY; the tool's own --force then
    # means ONLY "override my gate", which is what its help text already claimed.
    args = ["worktree", "remove", "--force", str(target)]
    removed = _git(main, *args)
    ownership.close()
    if removed.returncode:
        detail = removed.stderr.decode("utf-8", errors="replace").strip()
        print(f"REFUSE: git worktree remove failed: {detail}", file=sys.stderr)
        return 2
    print(f"removed linked worktree {target}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check a lane for tracked/unmerged work, then remove its worktree.")
    parser.add_argument("path", help="registered linked worktree to inspect and remove")
    parser.add_argument("--base", default="master",
                        help="branch used to detect unmerged commits (default: master)")
    parser.add_argument("--check", action="store_true",
                        help="run the complete gate without removing the worktree")
    parser.add_argument("--force", action="store_true",
                        help="override refusals, printing every discarded path and commit")
    args = parser.parse_args(argv)
    return reap(args.path, base=args.base, force=args.force, check_only=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
