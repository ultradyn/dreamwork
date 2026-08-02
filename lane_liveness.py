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
class FinishedLane:
    """A dispatched lane whose recorded runner is no longer present."""

    lane: str
    task: object
    pid: object
    identity: str


@dataclass(frozen=True)
class LaneInspection:
    """One checkable view of lane locks, worktrees, and process evidence."""

    live: tuple[str, ...]
    worktree_only: tuple[str, ...]
    process_only: tuple[str, ...]
    examined_processes: int
    finished: tuple[FinishedLane, ...] = ()


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


def _registered_worktrees(target: Path) -> tuple[Path, ...]:
    """Return git-registered lane worktrees under this target's two roots."""
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
    roots = tuple(root.resolve() for root in worktree_roots(target.resolve()))
    paths = []
    for line in result.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        path = Path(line.removeprefix("worktree ")).resolve()
        if any(path.parent == root for root in roots):
            paths.append(path)
    return tuple(paths)


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
) -> LaneInspection:
    """Inspect the canonical lane locks and report both mismatch directions.

    A live lane is the intersection of a git-registered worktree, its strict
    lane lock, and the exact process identity checked by :func:`pid_matches_lane`.
    Lockless worktrees, finished dispatched lanes, and governed process prompts
    whose worktree is no longer registered are named separately.
    """
    target = target.resolve()
    roots = tuple(root.resolve() for root in worktree_roots(target))
    if process_entries is None:
        try:
            process_entries = os.listdir("/proc")
        except OSError as exc:
            raise LivenessUnknown("cannot enumerate process candidates: %s" % exc) from exc
    pids = [int(entry) for entry in process_entries if entry.isdigit()]
    if not pids:
        raise LivenessUnknown("lane detector examined 0 process candidates")

    worktrees = (_registered_worktrees(target) if registered_worktrees is None
                 else tuple(path.resolve() for path in registered_worktrees))
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
            finished.append(FinishedLane(
                lane=record["lane"], task=record["task"], pid=record["pid"],
                identity=str(identity)))

    return LaneInspection(
        live=tuple(live),
        worktree_only=tuple(worktree_only),
        process_only=tuple(sorted(path.name for path in process_paths - registered)),
        examined_processes=len(pids),
        finished=tuple(finished),
    )
