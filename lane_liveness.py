"""Shared process identity probes for Dreamwork lanes."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from worktree_paths import WORKTREE_DIR
from worktree_paths import worktree_roots


class LivenessUnknown(Exception):
    """The probe could not determine whether a lane is live."""


@dataclass(frozen=True)
class FinishedWork:
    """The work a dead lane left behind, split the way ``dev/reap.py`` splits it.

    ``finished`` today is one word for a lane whose runner is gone, whether it
    reported and exited, died holding nothing, or died holding a day's work on
    its branch or in a dirty tree (#1154). The dangerous state — work that
    reaping would destroy or that sits unreviewed on a branch — looked exactly
    like the disposable one, because the classifier never looked at the work.

    These counts mirror ``dev/reap.py``'s ``tracked-dirty=N untracked=N
    ignored=N`` split on purpose: that is the model this repo already trusts for
    the decision "would work be lost", and a second taxonomy would drift. The
    split keeps ignored churn (``__pycache__``, ``lane.lock`` — present in every
    lane) OUT of ``holding_work``, so a lane with only cache dirt reads clean
    and not as "died holding work".

      - ``tracked_dirty`` — modified or staged tracked files. Work that reaping
        destroys (the ``cx-1140ingest`` shape: 448 insertions, zero commits).
      - ``untracked`` — notable untracked paths beyond the per-lane scratch set
        (``BRIEF.md``). A deliverable the lane forgot to commit.
      - ``unmerged`` — commits on the branch not on the base. Work on the branch
        (the ``cx-1060label6`` shape: 8 commits of accepted work).
      - ``ignored`` — ignored churn, named for audit (#868) but never counted
        toward ``holding_work``.

    ``commits_known`` is False when the branch could not be compared to the base
    (no ``master``, detached): ``unmerged`` is then 0 and the tick line says so
    rather than asserting an all-clear (#136).
    """

    tracked_dirty: int
    untracked: int
    ignored: int
    unmerged: int
    commits_known: bool = True

    @property
    def holding_work(self) -> bool:
        """Whether the dead lane left work that must not be silently reaped.

        Keys on the WORKING TREE and the branch, never on the runner: a lane
        that reported and then died has a clean tree and reads ``False`` here,
        so it is not classified as work-losing because its process vanished.
        Commit count alone does NOT decide this — a lane can hold a day's work
        with zero commits (#1154).
        """
        return self.tracked_dirty > 0 or self.untracked > 0 or self.unmerged > 0


# The per-lane scratch every lane carries, modelled on reap.EXPECTED_UNTRACKED.
# BRIEF.md is written into each worktree by the coordinator and never tracked;
# suppressing it would hide nothing, but counting it would call an idle lane
# "holding work". Kept as a literal of one name (#612): a fact about the lane
# model, not a computed value.
_FINISHED_EXPECTED_UNTRACKED = frozenset({"BRIEF.md"})

# Disposable ignored entries present in every lane (__pycache__, *.pyc,
# *.lock). Mirrors reap._is_disposable_ignored so the two never disagree on
# what "ignored churn" means; the comment there is the authority.
_FINISHED_DISPOSABLE_IGNORED_DIRS = frozenset(
    {".pytest_cache", ".ruff_cache", "node_modules"})


def _is_disposable_ignored(path: str) -> bool:
    parts = path.split("/")
    return (
        path.endswith((".pyc", ".lock"))
        or any(part in _FINISHED_DISPOSABLE_IGNORED_DIRS for part in parts))


def _finished_status_kinds(raw: bytes):
    """Parse ``git status -z --ignored`` into (kind, path) rows.

    Re-states reap._status_paths's porcelain walk rather than importing the
    dev/ script: lane_liveness is a top-level probe imported by tick_line and
    status_sync, and a dev/ import with its land_lane fallback would be the
    wrong direction. The split is the model reap trusts; the two are kept in
    sync by the test that builds all three tree states (#1154).
    """
    fields = raw.split(b"\0")
    rows = []
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
            index += 1
        kind = ("untracked" if code == "??"
                else "ignored" if code == "!!" else "tracked")
        rows.append((kind, path))
    return rows


def classify_finished_work(
        worktree: Path, *, base: str = "master") -> FinishedWork | None:
    """Classify the work a finished lane's worktree holds (#1154).

    Returns None when the worktree is not a git repo (``git status`` failed),
    so the caller renders ``finished`` without a work verdict rather than
    guessing clean. Mirrors reap's tracked/untracked/ignored split; see
    :class:`FinishedWork` for why each bucket is reported separately.
    """
    status = subprocess.run(
        ["git", "-C", str(worktree), "status", "--porcelain=v1", "-z",
         "--untracked-files=all", "--ignored"],
        capture_output=True, check=False,
    )
    if status.returncode:
        return None
    rows = _finished_status_kinds(status.stdout)
    if rows is None:
        return None
    tracked = sum(1 for kind, _ in rows if kind == "tracked")
    ignored = sum(1 for kind, _ in rows if kind == "ignored")
    notable_untracked = sum(
        1 for kind, path in rows
        if kind == "untracked" and path not in _FINISHED_EXPECTED_UNTRACKED)
    # Disposable ignored churn (__pycache__, *.lock) is present in every lane;
    # subtract it from the reported ignored count so a clean lane reads
    # ignored=0 and the audit trail shows the classifier saw the churn and
    # correctly discounted it (#868).
    notable_ignored = sum(
        1 for kind, path in rows
        if kind == "ignored" and not _is_disposable_ignored(path))
    cherry = subprocess.run(
        ["git", "-C", str(worktree), "cherry", base, "HEAD"],
        capture_output=True, text=True, check=False,
    )
    commits_known = cherry.returncode == 0
    unmerged = 0
    if commits_known:
        unmerged = sum(
            1 for line in cherry.stdout.splitlines()
            if line.startswith("+ "))
    return FinishedWork(
        tracked_dirty=tracked,
        untracked=notable_untracked,
        # Report NON-disposable ignored so the count is a signal, not noise:
        # a stray hand-written file inside an ignored dir is still evidence.
        ignored=notable_ignored,
        unmerged=unmerged,
        commits_known=commits_known,
    )


@dataclass(frozen=True)
class FinishedLane:
    """A dispatched lane whose recorded runner is no longer present.

    ``work`` classifies what the dead lane left behind (#1154): None when the
    worktree could not be classified (no git repo), otherwise a split that
    separates the dangerous state — died holding work on the branch or in a
    dirty tree — from the disposable one. The runner being gone is the same
    fact for both; the work is what differs.
    """

    lane: str
    task: object
    pid: object
    identity: str
    work: FinishedWork | None = None


@dataclass(frozen=True)
class LaneInspection:
    """One checkable view of lane locks, worktrees, and process evidence."""

    live: tuple[str, ...]
    worktree_only: tuple[str, ...]
    process_only: tuple[str, ...]
    examined_processes: int
    finished: tuple[FinishedLane, ...] = ()
    cwd_live: tuple[str, ...] = ()


def pid_alive(pid) -> bool:
    """Return the result of ``kill -0``; raise when it cannot be interpreted."""
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except (TypeError, ValueError):
        raise LivenessUnknown("unparseable dreamers pid: %r" % (pid,))
    except OSError as exc:
        raise LivenessUnknown("kill -0 %r failed: %s" % (pid, exc)) from exc


def read_proc_cwd(pid: int) -> str | None:
    """Return ``/proc/<pid>/cwd``, or None if it disappeared or is unreadable."""
    try:
        return os.readlink("/proc/%d/cwd" % pid)
    except OSError:
        return None


def pid_matches_lane(
        pid, brief,
        *,
        is_pid_alive: Callable[[object], bool] = pid_alive,
        proc_cwd: Callable[[int], str | None] = read_proc_cwd,
) -> bool:
    """Whether ``pid`` is alive and still carries ``brief``'s lane identity."""
    if not is_pid_alive(pid):
        return False
    if not isinstance(brief, str) or not brief:
        raise LivenessUnknown("live pid has no lane brief identity: %r" % pid)

    lane_dir = str(Path(brief).parent)
    cwd = proc_cwd(int(pid))
    if os.path.isabs(lane_dir) and (
            cwd == lane_dir or (cwd and cwd.startswith(lane_dir + os.sep))):
        return True

    try:
        with open("/proc/%d/cmdline" % int(pid), "rb") as handle:
            raw = handle.read()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise LivenessUnknown("cannot read pid %r identity: %s" % (pid, exc)) from exc

    needles = [brief.encode()]
    if WORKTREE_DIR in Path(brief).parts:
        needles.append(lane_dir.encode())
    return any(needle in raw for needle in needles)


# What counts as a lane runner, and the ancestor-self exclusion (#729), are
# shared with status_sync from lane_runner_identity — the single source — so
# the tick's fleet count and status.json's agree by construction, not by two
# hand-kept lists (#1113: the #868/#1084 "the fleet count lied" defect class
# was two copies drifting). is_lane_runner takes raw BYTES so this channel
# reuses the /proc read the governed-prompt scan already did (no second
# shell-out; a pattern in this tool's own command line can never match itself).
from lane_runner_identity import ancestor_pids as _ancestor_pids  # noqa: E402
from lane_runner_identity import is_lane_runner as _is_lane_runner  # noqa: E402


def _worktree_registry(target: Path) -> tuple[Path, tuple[Path, ...]]:
    """Return the main checkout and registered lanes under its two roots."""
    try:
        result = subprocess.run(
            ["git", "-C", str(target), "worktree", "list", "--porcelain"],
            capture_output=True, text=True, check=False,
        )
    except OSError as exc:
        raise LivenessUnknown("cannot list registered worktrees: %s" % exc) from exc
    if result.returncode:
        detail = result.stderr.strip().splitlines()[0] if result.stderr.strip() else "git failed"
        raise LivenessUnknown(
            "cannot list registered worktrees: %s" % detail)
    records = []
    for line in result.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        records.append(Path(line.removeprefix("worktree ")).resolve())
    if not records:
        raise LivenessUnknown("cannot list registered worktrees: git returned no records")
    # Porcelain lists the main checkout first even when invoked from a linked
    # worktree.  The gate breadcrumb is main-owned, so neither the lane roots
    # nor that breadcrumb may be rooted on the invocation checkout.
    main_checkout = records[0]
    roots = tuple(root.resolve() for root in worktree_roots(main_checkout))
    paths = []
    for path in records[1:]:
        if any(path.parent == root for root in roots):
            paths.append(path)
    return main_checkout, tuple(paths)


def _registered_worktrees(target: Path) -> tuple[Path, ...]:
    """Return git-registered lane worktrees under this target's two roots."""
    return _worktree_registry(target)[1]


def _in_flight_gate_worktree(main_checkout: Path) -> Path | None:
    """Return the exact scratch named by the main checkout's gate breadcrumb.

    This deliberately restates ``lint._in_flight_gate_worktree`` instead of
    importing the executable linter into this shared runtime probe.  Its
    identity rule is the same: breadcrumb path, never the ``.gate-*`` name.
    """
    path = main_checkout / ".dreamwork" / "gate-in-flight.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict):
        return None
    raw = record.get("gate_worktree")
    if not raw:
        return None
    try:
        return Path(str(raw)).resolve()
    except OSError:
        return None


def _prompt_worktree(raw: bytes, roots: tuple[Path, ...]) -> Path | None:
    """Read only an exact governed ``Worktree:`` line from process argv.

    NULs delimit argv elements, so mapping them to newlines lets the same
    line-anchored grammar read the one prompt argument.  Incidental prose or
    paths such as ``.../.worktrees/review`` are deliberately not identity.
    """
    text = raw.replace(b"\x00", b"\n").decode("utf-8", "replace")
    matches = re.findall(r"^Worktree:\s+([^\r\n]+?)\s*$", text, re.MULTILINE)
    if len(matches) != 1:
        return None
    path = Path(matches[0]).resolve()
    return path if any(path.parent == root for root in roots) else None


def inspect_lanes(
        target: Path,
        *,
        process_entries: list[str] | None = None,
        registered_worktrees: tuple[Path, ...] | None = None,
        read_cmdline: Callable[[int], bytes] | None = None,
        read_cwd: Callable[[int], str | None] | None = None,
        skip_pids: set[int] | None = None,
        work_classifier: Callable[[Path], FinishedWork | None] | None = None,
) -> LaneInspection:
    """Inspect the canonical lane locks and report both mismatch directions.

    A lock-confirmed live lane is the intersection of a git-registered
    worktree, its strict lane lock, and the exact process identity checked by
    :func:`pid_matches_lane`. The cwd channel is the dispatch-route-invariant
    fallback (#1084): a hand-dispatched lane has no ``lane.lock`` (every
    follow-up round is dispatched that way), so the lock channel is blind to
    it. The cwd channel names a lane live when a known RUNNER process holds
    the worktree as its cwd — a measurement that cannot vary with dispatch
    route the way a launch-lane-created marker does. Where the two channels
    disagree, the cwd-only lanes are reported in ``cwd_live`` rather than
    silently dropped or silently merged (#136).

    Lockless idle worktrees, finished dispatched lanes, and governed process
    prompts whose worktree is no longer registered are named separately.
    """
    target = target.resolve()
    if process_entries is None:
        try:
            process_entries = os.listdir("/proc")
        except OSError as exc:
            raise LivenessUnknown("cannot enumerate process candidates: %s" % exc) from exc
    pids = [int(entry) for entry in process_entries if entry.isdigit()]
    if not pids:
        raise LivenessUnknown("lane detector examined 0 process candidates")

    if registered_worktrees is None:
        main_checkout, worktrees = _worktree_registry(target)
    else:
        main_checkout = target
        worktrees = tuple(path.resolve() for path in registered_worktrees)
    roots = tuple(root.resolve() for root in worktree_roots(main_checkout))
    gate_scratch = _in_flight_gate_worktree(main_checkout)
    if gate_scratch is not None:
        worktrees = tuple(path for path in worktrees if path != gate_scratch)
    registered = {path.resolve() for path in worktrees}
    reader = read_cmdline or (
        lambda pid: Path("/proc/%d/cmdline" % pid).read_bytes())
    process_paths = set()
    for pid in pids:
        try:
            raw = reader(pid)
            if not re.search(rb"(?m)^# Task #\d+\b", raw.replace(b"\x00", b"\n")):
                continue
            path = _prompt_worktree(raw, roots)
        except OSError:
            continue
        if path is not None:
            process_paths.add(path)

    live = []
    worktree_only = []
    finished = []
    for worktree in sorted(registered, key=lambda path: path.name):
        lock = worktree / ".dreamwork" / "lane.lock"
        try:
            record = json.loads(lock.read_text(encoding="utf-8"))
        except FileNotFoundError:
            worktree_only.append(worktree.name)
            continue
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise LivenessUnknown("cannot classify lane lock %s: %s" % (lock, exc)) from exc
        required = {"pid", "task", "lane", "identity"}
        if not isinstance(record, dict) or not required.issubset(record):
            raise LivenessUnknown("cannot classify lane lock %s: missing lane identity" % lock)
        if record["lane"] != worktree.name:
            raise LivenessUnknown(
                "lane lock %s names lane %r, expected %r"
                % (lock, record["lane"], worktree.name))
        identity = Path(str(record["identity"]))
        if identity.parent.resolve() != worktree:
            raise LivenessUnknown(
                "lane lock %s identity is outside its worktree: %s"
                % (lock, identity))
        if pid_matches_lane(record["pid"], str(identity)):
            live.append(worktree.name)
        else:
            classify = work_classifier or classify_finished_work
            finished.append(FinishedLane(
                lane=record["lane"], task=record["task"], pid=record["pid"],
                identity=str(identity), work=classify(worktree)))

    # CWD-RUNNER SCAN — the dispatch-route-invariant channel (#1084). A lane
    # whose runner lives in its worktree but has no lane.lock (hand-dispatched,
    # every follow-up round) is invisible to the lock loop above. The cwd is
    # the measurement that was right in both fleet-undercount samples: it
    # cannot vary with dispatch route. A runner is distinguished from a
    # leftover (shell, editor, inotifywait) by its argv[0] basename, not by
    # cwd alone (#671/#729). Deleted cwds (" (deleted)" — a phantom whose
    # worktree was removed) are excluded. The set dedupes to one lane per
    # worktree, so a lane's many descendants count once.
    live_set = set(live)
    cwd_reader = read_cwd or read_proc_cwd
    skip = skip_pids if skip_pids is not None else _ancestor_pids()
    wt_by_path = {str(wt): wt.name for wt in worktrees}
    cwd_occupied: set[str] = set()
    for pid in pids:
        if pid in skip:
            continue
        cwd = cwd_reader(pid)
        if cwd is None or cwd.endswith(" (deleted)"):
            continue
        lane_name = next(
            (name for wt_str, name in wt_by_path.items()
             if cwd == wt_str or cwd.startswith(wt_str + os.sep)),
            None)
        if lane_name is None:
            continue
        if _is_lane_runner(reader(pid)):
            cwd_occupied.add(lane_name)
    cwd_live_names = tuple(sorted(
        name for name in cwd_occupied if name not in live_set))
    cwd_live_set = set(cwd_live_names)
    # A worktree the cwd channel found live is neither idle (worktree_only)
    # nor finished (the lock is stale, the lane was re-armed): it is live.
    worktree_only = tuple(n for n in worktree_only if n not in cwd_live_set)
    finished = tuple(f for f in finished if f.lane not in cwd_live_set)

    return LaneInspection(
        live=tuple(live),
        worktree_only=tuple(worktree_only),
        process_only=tuple(sorted(path.name for path in process_paths - registered)),
        examined_processes=len(pids),
        finished=tuple(finished),
        cwd_live=cwd_live_names,
    )
