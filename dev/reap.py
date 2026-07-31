#!/usr/bin/env python3
"""Remove a lane worktree only after proving its work is discoverable (#686)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StatusPath:
    kind: str
    path: str


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


def _summary(
    target: Path,
    tracked: int | str,
    scratch: int | str,
    unmerged: int | str,
) -> str:
    return (
        f"reap examined path={target} tracked-dirty={tracked} "
        f"untracked-ignored={scratch} unmerged-commits={unmerged}"
    )


def _unknown(target: Path, reason: str, *, tracked="unknown", scratch="unknown") -> int:
    print(_summary(target, tracked, scratch, "unknown"), file=sys.stderr)
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

    rows = _status_paths(target)
    if rows is None:
        return _unknown(target, "git status failed")
    tracked = [row for row in rows if row.kind == "tracked"]
    scratch = [row for row in rows if row.kind != "tracked"]

    commits = _unmerged_commits(target, base)
    if commits is None:
        return _unknown(
            target,
            f"could not compare HEAD with base `{base}`",
            tracked=len(tracked),
            scratch=len(scratch),
        )

    summary = _summary(target, len(tracked), len(scratch), len(commits))
    unsafe = bool(tracked or commits)
    stream = sys.stderr if unsafe and not force else sys.stdout
    print(summary, file=stream)

    if unsafe and not force:
        for row in tracked:
            print(f"REFUSE: tracked path would be lost: {row.path}", file=sys.stderr)
        for sha, subject in commits:
            print(
                f"REFUSE: unmerged commit would become easier to delete unseen: "
                f"{sha[:12]} {subject}",
                file=sys.stderr,
            )
        print("Inspect the lane, then rerun with --force only if discarding is intended.",
              file=sys.stderr)
        return 1

    if force:
        for row in rows:
            print(f"FORCE: discarding {row.kind} path: {row.path}", file=sys.stderr)
        for sha, subject in commits:
            print(f"FORCE: overriding unmerged commit: {sha[:12]} {subject}",
                  file=sys.stderr)

    if check_only:
        print("reap gate OK (check only)")
        return 0

    main = worktrees[0]
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(target))
    removed = _git(main, *args)
    if removed.returncode:
        detail = removed.stderr.decode("utf-8", errors="replace").strip()
        print(f"REFUSE: git worktree remove failed: {detail}", file=sys.stderr)
        if scratch and not force:
            print("Rerun with --force to print and explicitly discard scratch paths.",
                  file=sys.stderr)
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
