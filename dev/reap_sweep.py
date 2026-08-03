#!/usr/bin/env python3
"""Periodically apply :mod:`reap`'s existing gate to linked worktrees.

IGC context: a coordinator needs a repo-owned periodic caller while lifecycle
dispatch code is owned elsewhere.

| Idea | All | G1 | G2 | G3 | G4 |
|---|:---:|:---:|:---:|:---:|:---:|
| coordinator tick invokes this CLI | yes | yes | yes | yes | yes |
| manual ``just`` target | no | no | yes | yes | yes |
| independent timer daemon | no | yes | no | no | no |

G1 actually periodic; G2 no new service/state; G3 first bad gate is visible
and report-only unless ``--apply`` is explicit; G4 compact complete audit.
The surviving row is the coordinator-tick command.  A verdict-time reap has a
smaller first-error blast radius, but is custodial policy rather than lane code.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from dev.reap import WorktreeLiveness, worktree_liveness
except ModuleNotFoundError as exc:
    if exc.name != "dev":
        raise
    from reap import WorktreeLiveness, worktree_liveness


DEFAULT_HOLDS = Path(__file__).with_name("reap-holds.txt")


@dataclass
class Counts:
    examined: int = 0
    reaped: int = 0
    reapable: int = 0
    refused: int = 0
    held: int = 0
    live: int = 0
    gate_scratch: int = 0


def _git_worktrees(repo: Path) -> list[Path] | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        return None
    return [
        Path(line.removeprefix("worktree ")).resolve()
        for line in result.stdout.splitlines()
        if line.startswith("worktree ")
    ]


def _read_holds(path: Path) -> set[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read hold list {path}: {exc}") from exc
    holds: set[str] = set()
    for number, raw in enumerate(lines, 1):
        value = raw.split("#", 1)[0].strip()
        if not value:
            continue
        if value in {".", ".."} or Path(value).name != value:
            raise ValueError(f"invalid hold name at {path}:{number}: {value!r}")
        holds.add(value)
    return holds


def _run_reap(path: Path, base: str, *, check: bool) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(Path(__file__).with_name("reap.py"))]
    if check:
        command.append("--check")
    command.extend(("--base", base, str(path)))
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _reason(result: subprocess.CompletedProcess[str]) -> str:
    rows = [row.strip() for row in result.stderr.splitlines() if row.strip()]
    refused = next((row for row in rows if row.startswith("REFUSE:")), None)
    if refused:
        return refused
    return rows[-1] if rows else f"reap gate exited {result.returncode} without a reason"


def _detail(name: str, result: subprocess.CompletedProcess[str], verbose: bool) -> None:
    if not verbose:
        return
    for stream, body in (("stdout", result.stdout), ("stderr", result.stderr)):
        for row in body.splitlines():
            print(f"DETAIL {name} {stream}: {row}")


def _live_reason(liveness: WorktreeLiveness) -> str | None:
    if liveness.unknown:
        return "liveness scan incomplete: " + "; ".join(liveness.unknown)
    if liveness.pids:
        return "active process cwd pids=" + ",".join(str(pid) for pid in liveness.pids)
    return None


def sweep(repo: Path, holds_path: Path, *, base: str = "master",
          apply: bool = False, verbose: bool = False) -> int:
    try:
        holds = _read_holds(holds_path)
    except ValueError as exc:
        print(f"REFUSE sweep: {exc}", file=sys.stderr)
        return 2

    worktrees = _git_worktrees(repo.resolve())
    if not worktrees:
        print(f"REFUSE sweep: cannot enumerate worktrees from {repo}", file=sys.stderr)
        return 2

    main = worktrees[0]
    counts = Counts()
    for path in worktrees[1:]:
        counts.examined += 1
        name = path.name
        if name in holds:
            counts.held += 1
            print(f"HELD {name}: named by {holds_path}")
            continue
        if name.startswith(".gate-"):
            counts.gate_scratch += 1
            print(f"GATE-SCRATCH {name}: periodic sweep never reaps gate scratch")
            continue

        live_reason = _live_reason(worktree_liveness(path))
        if live_reason:
            counts.live += 1
            print(f"LIVE {name}: {live_reason}")
            continue

        checked = _run_reap(path, base, check=True)
        _detail(name, checked, verbose)
        if checked.returncode:
            counts.refused += 1
            print(f"REFUSED {name}: {_reason(checked)}")
            continue
        if not apply:
            counts.reapable += 1
            print(f"REAPABLE {name}: gate passed; report-only mode")
            continue

        removed = _run_reap(path, base, check=False)
        _detail(name, removed, verbose)
        if removed.returncode:
            reason = _reason(removed)
            if "active process cwd" in reason or "liveness scan incomplete" in reason:
                counts.live += 1
                print(f"LIVE {name}: {reason}")
            else:
                counts.refused += 1
                print(f"REFUSED {name}: {reason}")
            continue
        counts.reaped += 1

    mode = "apply" if apply else "report"
    print(
        f"SUMMARY mode={mode} examined={counts.examined} reaped={counts.reaped} "
        f"reapable={counts.reapable} refused={counts.refused} held={counts.held} "
        f"live={counts.live} gate-scratch={counts.gate_scratch} main={main}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd(),
                        help="any checkout in the worktree family (default: cwd)")
    parser.add_argument("--holds", type=Path, default=DEFAULT_HOLDS,
                        help=f"fail-closed basename hold list (default: {DEFAULT_HOLDS})")
    parser.add_argument("--base", default="master")
    parser.add_argument("--apply", action="store_true",
                        help="remove candidates that pass; default only reports")
    parser.add_argument("--verbose", action="store_true",
                        help="include reap.py's per-path gate detail")
    args = parser.parse_args(argv)
    return sweep(args.repo, args.holds, base=args.base,
                 apply=args.apply, verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
