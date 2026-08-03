#!/usr/bin/env python3
"""Process operations whose subject is explicit instead of inherited.

``run`` starts one child and returns that exact child's status.  It replaces
shell loops whose argv search can match the waiting shell itself.

``lane-runners`` finds current-user lane runners by exact cwd containment and
the shared ``lane_liveness._is_lane_runner`` argv[0] classifier. ``exact``
finds an interpreter/script pair in argv[0]/argv[1]. Neither searches arbitrary
argv prose.  The /proc walk is necessarily restated here:
``lane_liveness.inspect_lanes`` aggregates registered worktrees and discards
per-pid read failures, while this CLI accepts one explicit cwd and must retain
gone versus unreadable.  The classifier is imported, not copied; moving the
generic walk into a neutral module would remove the remaining duplication.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lane_liveness import _ancestor_pids, _is_lane_runner  # noqa: E402


class ObservationState(str, Enum):
    """The result of attempting to classify one listed pid."""

    MATCH = "match"
    OTHER = "other"
    GONE = "gone"
    UNREADABLE = "unreadable"
    EXCLUDED = "excluded"


@dataclass(frozen=True)
class ProcessObservation:
    pid: int
    state: ObservationState


@dataclass(frozen=True)
class RunnerScan:
    """A scan result that does not collapse unreadable into absent."""

    observations: tuple[ProcessObservation, ...]

    def count(self, state: ObservationState) -> int:
        return sum(item.state is state for item in self.observations)

    @property
    def matches(self) -> tuple[int, ...]:
        return tuple(
            item.pid for item in self.observations
            if item.state is ObservationState.MATCH
        )

    @property
    def examined(self) -> int:
        return self.count(ObservationState.MATCH) + self.count(ObservationState.OTHER)

    @property
    def status(self) -> str:
        if self.matches:
            return "present"
        if self.count(ObservationState.UNREADABLE) or self.examined == 0:
            return "unknown"
        return "absent"


def _contains(target: Path, cwd: str) -> bool:
    target_text = str(target)
    return cwd == target_text or cwd.startswith(target_text + os.sep)


def _scan_processes(
        cwd: Path,
        *,
        classifier: Callable[[bytes], bool],
        pids: Iterable[int] | None = None,
        proc_root: Path = Path("/proc"),
        skip_pids: set[int] | None = None,
        uid: int | None = None,
) -> RunnerScan:
    """Classify current-user lane runners contained by the absolute ``cwd``.

    A pid disappearing between enumeration and a read is ``gone``.  A listed
    same-user pid whose identity cannot be read is ``unreadable`` and makes a
    zero-match result ``unknown``.  Foreign-user processes and this probe's
    process ancestry are outside the subject and are ``excluded``.
    """
    if not cwd.is_absolute():
        raise ValueError("lane-runners cwd must be absolute")
    target = cwd.resolve()
    if pids is None:
        entries = proc_root.iterdir()
        candidates = sorted(int(entry.name) for entry in entries if entry.name.isdigit())
    else:
        candidates = sorted(set(int(pid) for pid in pids))
    skipped = _ancestor_pids() if skip_pids is None else set(skip_pids)
    subject_uid = os.geteuid() if uid is None else uid
    observations: list[ProcessObservation] = []

    for pid in candidates:
        if pid in skipped:
            observations.append(ProcessObservation(pid, ObservationState.EXCLUDED))
            continue
        proc_dir = proc_root / str(pid)
        try:
            owner = proc_dir.stat().st_uid
        except FileNotFoundError:
            observations.append(ProcessObservation(pid, ObservationState.GONE))
            continue
        except OSError:
            observations.append(ProcessObservation(pid, ObservationState.UNREADABLE))
            continue
        if owner != subject_uid:
            observations.append(ProcessObservation(pid, ObservationState.EXCLUDED))
            continue
        try:
            process_cwd = os.readlink(proc_dir / "cwd")
        except FileNotFoundError:
            observations.append(ProcessObservation(pid, ObservationState.GONE))
            continue
        except OSError:
            observations.append(ProcessObservation(pid, ObservationState.UNREADABLE))
            continue
        if process_cwd.endswith(" (deleted)") or not _contains(target, process_cwd):
            observations.append(ProcessObservation(pid, ObservationState.OTHER))
            continue
        try:
            raw = (proc_dir / "cmdline").read_bytes()
        except FileNotFoundError:
            observations.append(ProcessObservation(pid, ObservationState.GONE))
            continue
        except OSError:
            observations.append(ProcessObservation(pid, ObservationState.UNREADABLE))
            continue
        state = ObservationState.MATCH if classifier(raw) else ObservationState.OTHER
        observations.append(ProcessObservation(pid, state))

    return RunnerScan(tuple(observations))


def scan_lane_runners(
        cwd: Path,
        *,
        pids: Iterable[int] | None = None,
        proc_root: Path = Path("/proc"),
        skip_pids: set[int] | None = None,
        uid: int | None = None,
) -> RunnerScan:
    """Find lane runners using the repository's one shared classifier."""
    return _scan_processes(
        cwd, classifier=_is_lane_runner, pids=pids, proc_root=proc_root,
        skip_pids=skip_pids, uid=uid)


def scan_exact_command(
        cwd: Path,
        *,
        argv0: str,
        argv1: str,
        pids: Iterable[int] | None = None,
        proc_root: Path = Path("/proc"),
        skip_pids: set[int] | None = None,
        uid: int | None = None,
) -> RunnerScan:
    """Find an exact argv[0] basename plus exact argv[1] under ``cwd``."""
    executable = os.path.basename(argv0)

    def classifier(raw: bytes) -> bool:
        parts = raw.split(b"\x00")
        if len(parts) < 2:
            return False
        actual = os.path.basename(parts[0].decode("utf-8", "replace"))
        script = parts[1].decode("utf-8", "replace")
        return actual == executable and script == argv1

    return _scan_processes(
        cwd, classifier=classifier, pids=pids, proc_root=proc_root,
        skip_pids=skip_pids, uid=uid)


def run_exact(argv: list[str]) -> int:
    """Run and wait for exactly one child, returning shell-compatible status."""
    if not argv:
        raise ValueError("run requires a command after --")
    try:
        result = subprocess.run(argv, check=False)
    except OSError as exc:
        print("procprobe: cannot start %r: %s" % (argv[0], exc), file=sys.stderr)
        return 127
    return result.returncode if result.returncode >= 0 else 128 - result.returncode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="verb", required=True)
    run = commands.add_parser("run", help="run and wait for one exact child")
    run.add_argument("command", nargs=argparse.REMAINDER)
    runners = commands.add_parser(
        "lane-runners", help="find current-user lane runners under an exact cwd")
    runners.add_argument("--cwd", required=True, type=Path)
    runners.add_argument("--pid", action="append", type=int, dest="pids")
    exact = commands.add_parser(
        "exact", help="find an exact interpreter basename and argv[1] under a cwd")
    exact.add_argument("--cwd", required=True, type=Path)
    exact.add_argument("--argv0", required=True, help="exact executable basename")
    exact.add_argument("--argv1", required=True, help="exact first argument")
    exact.add_argument("--pid", action="append", type=int, dest="pids")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.verb == "run":
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        return run_exact(command)

    try:
        if args.verb == "lane-runners":
            scan = scan_lane_runners(args.cwd, pids=args.pids)
        else:
            scan = scan_exact_command(
                args.cwd, argv0=args.argv0, argv1=args.argv1, pids=args.pids)
    except (OSError, ValueError) as exc:
        print("procprobe: lane-runners unknown: %s" % exc, file=sys.stderr)
        return 2
    counts = {state: scan.count(state) for state in ObservationState}
    print(
        "status=%s matches=%d examined=%d gone=%d unreadable=%d excluded=%d "
        "candidates=%d pids=%s"
        % (
            scan.status,
            counts[ObservationState.MATCH],
            scan.examined,
            counts[ObservationState.GONE],
            counts[ObservationState.UNREADABLE],
            counts[ObservationState.EXCLUDED],
            len(scan.observations),
            ",".join(str(pid) for pid in scan.matches) or "-",
        )
    )
    return {"present": 0, "absent": 1, "unknown": 2}[scan.status]


if __name__ == "__main__":
    raise SystemExit(main())
