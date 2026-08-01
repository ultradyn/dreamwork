#!/usr/bin/env python3
"""Sweep registered lane worktrees and report live/dead, dirty, and armed state.

A killed lane is indistinguishable from a finished one except by hand-inspecting
its worktree, and the dangerous state — died mid-red-proof with armed injections
on disk — looks exactly like ordinary WIP (#876). This tool makes it loud.

It ORCHESTRATES three existing implementations rather than duplicating them:

- **Liveness** reuses ``lane_liveness.pid_matches_lane`` (#869's one
  process-identity implementation). The lane lock is #869's record; this tool
  reads it and asks lane_liveness whether the pid is alive and bound.
- **Armed injections** reuse ``dev/redproof.py check`` as a subprocess — the
  check already computes the armed-injection answer per worktree (#683, #877).
  Calling it rather than reimplementing it is the whole point: a second
  implementation would drift, and #870/#877 exist precisely to keep it single.
- **Uncommitted work** uses ``git status --porcelain``, the same source reap.py
  trusts for its discoverability gate.

THE ZERO-DENOMINATOR (#868)
---------------------------
A sweep over ZERO worktrees that prints "no armed injections" looks like an
all-clear — and a false ``lanes 0 live`` reading is exactly what led to reaping
a live lane's worktree on 2026-08-01. So the sweep prints how many worktrees it
examined, whatever the verdict, and an examined-nothing result is never an
all-clear. This mirrors ``dev/ledger.py sweep``'s contract: the examined count
is part of the answer (#590).
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lane_liveness import LivenessUnknown, pid_matches_lane  # noqa: E402
from worktree_paths import worktree_roots  # noqa: E402


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, check=False,
    )


def _registered_worktrees(repo: Path) -> list[tuple[str, Path]]:
    """[(branch_or_label, path)] for every registered worktree."""
    result = _git(repo, "worktree", "list", "--porcelain")
    if result.returncode:
        return []
    entries: list[tuple[str, Path]] = []
    path: Path | None = None
    branch: str | None = None
    for line in [*result.stdout.splitlines(), ""]:
        if not line:
            if path is not None:
                label = (branch.removeprefix("refs/heads/") if branch
                         else path.name)
                entries.append((label, path))
            path = branch = None
        else:
            key, _, value = line.partition(" ")
            if key == "worktree":
                path = Path(value).resolve()
            elif key == "branch":
                branch = value
    return entries


def _lane_lock(worktree: Path) -> dict | None:
    """The lane.lock record #869 writes, or None if absent."""
    lock = worktree / ".dreamwork" / "lane.lock"
    if not lock.is_file():
        return None
    try:
        return json.loads(lock.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"_unreadable": str(lock)}


def _liveness(worktree: Path) -> str:
    """LIVE, DEAD, or a diagnostic, via lane_liveness (#869)."""
    lock = _lane_lock(worktree)
    if lock is None:
        return "no-lock"
    if "_unreadable" in lock:
        return f"lock-unreadable"
    pid = lock.get("pid")
    identity = lock.get("identity")
    if pid is None or identity is None:
        return "lock-incomplete"
    try:
        if pid_matches_lane(pid, identity):
            return f"LIVE pid={pid}"
    except LivenessUnknown:
        return "liveness-unknown"
    return "DEAD"


def _dirty_count(worktree: Path) -> int:
    """Number of uncommitted entries, via git status --porcelain."""
    result = _git(worktree, "status", "--porcelain=v1", "--untracked-files=normal")
    if result.returncode:
        return -1
    return len([line for line in result.stdout.splitlines() if line.strip()])


def _armed_injections(worktree: Path, repo: Path) -> tuple[str, str]:
    """(status, detail) from redproof check, run as a subprocess.

    Reuses the ONE armed-injection implementation (#683/#877); never
    reimplements the registry reader. Returns:
      ("clean", "")           — no armed injections
      ("ARMED", "<paths>")    — begun-but-unrestored entries
      ("live-injection", ..)  — working tree matches a recorded injection
      ("history", ..)         — a commit holds a recorded injection
      ("FAULT", "<message>")  — could not evaluate
    """
    redproof = ROOT / "dev" / "redproof.py"
    result = subprocess.run(
        [sys.executable, str(redproof), "check", "--cwd", str(worktree)],
        capture_output=True, text=True, check=False,
    )
    combined = (result.stdout + result.stderr).strip()
    if result.returncode == 0:
        return "clean", ""
    if result.returncode == 2:
        return "FAULT", combined.split("\n")[0] if combined else "redproof fault"
    # exit 1: refusal — classify by the specific condition that fired.
    if "begun-but-unrestored" in combined:
        return "ARMED", combined
    if "still present" in combined:
        return "live-injection", combined
    if "still hold" in combined:
        return "history", combined
    return "REFUSED", combined.split("\n")[0] if combined else "redproof refusal"


def sweep(repo: Path) -> int:
    """Print a per-lane report. Exit 1 if any lane is ARMED, else 0.

    A registered worktree is a LANE only when its path exists AND sits under a
    canonical fleet root (``worktree_roots`` — the same location notion
    ``lane_liveness`` already uses). Anything else is EXCLUDED and named, never
    silently dropped (#915): a pytest fixture that registered itself under a
    tmp dir and was reaped (missing path) or regenerated (non-lane path) is not
    a lane, and counting it re-inflated the fleet denominator three tasks were
    spent to make truthful (#821/#837/#840). The exclusion count prints whatever
    the verdict, so a sweep that excluded ten is distinguishable from one that
    excluded none — same denominator discipline as #638's registry scan.
    """
    worktrees = _registered_worktrees(repo)
    # The main checkout is always in the list; it is in the registered
    # denominator only, never a lane. A lane must ALSO exist and live under a
    # canonical fleet root — otherwise it is a corpse or a non-lane checkout
    # (e.g. a pytest fixture) and is excluded by reason, not in silence.
    main = repo.resolve()
    roots = {root.resolve() for root in worktree_roots(repo.resolve())}
    missing: list[tuple[str, Path]] = []
    nonlane: list[tuple[str, Path]] = []
    lanes: list[tuple[str, Path]] = []
    for label, path in worktrees:
        if path == main:
            continue
        if not path.exists():
            missing.append((label, path))
        elif path.parent not in roots:
            nonlane.append((label, path))
        else:
            lanes.append((label, path))

    excluded = len(missing) + len(nonlane)
    parts = []
    if missing:
        parts.append(f"{len(missing)} missing path")
    if nonlane:
        parts.append(f"{len(nonlane)} non-lane path")
    detail = ", ".join(parts) if parts else "0 missing path, 0 non-lane path"
    print(f"lane_status: examined {len(lanes)} lane worktree(s) "
          f"(of {len(worktrees)} registered, including main); "
          f"excluded {excluded} ({detail})")

    if not lanes:
        if not worktrees:
            msg = ("the registry yielded no worktrees at all "
                   "(git worktree list failed?)")
        elif excluded:
            msg = "every non-main worktree was excluded (see counts above)"
        else:
            msg = ("if lanes are running, their worktrees are not "
                   "registered here")
        print("lane_status: EXAMINED NOTHING — this is not an all-clear (#868); "
              + msg + ".")
        return 0

    any_armed = False
    for label, path in lanes:
        live = _liveness(path)
        dirty = _dirty_count(path)
        armed_status, armed_detail = _armed_injections(path, repo)
        if armed_status == "ARMED":
            any_armed = True
        dirty_str = f"{dirty} dirty" if dirty >= 0 else "dirty-unknown"
        parts = [f"{live:<20}", dirty_str]
        if armed_status != "clean":
            parts.append(f"{armed_status}")
        line = f"  {label:<24} " + "  ".join(parts)
        print(line)
        if armed_status == "ARMED":
            # Extract paths from the redproof output for prominence.
            for detail_line in armed_detail.split("\n"):
                if detail_line.strip():
                    print(f"    {detail_line.strip()}")

    if any_armed:
        print("lane_status: ARMED injection(s) found — a lane died mid-red-proof "
              "with sabotaged files unrestored. Restore them before merging.")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="lane_status.py",
        description="Sweep lane worktrees: live/dead, dirty, armed injections (#876).")
    ap.add_argument("verb", choices=["sweep"], help="sweep all registered lane worktrees")
    ap.add_argument("--repo", default=None, help="repository root (default: auto-detect)")
    args = ap.parse_args(argv)

    if args.repo:
        repo = Path(args.repo).resolve()
    else:
        result = _git(Path.cwd(), "rev-parse", "--show-toplevel")
        if result.returncode or not result.stdout.strip():
            print("lane_status: could not determine repository root", file=sys.stderr)
            return 2
        repo = Path(result.stdout.strip()).resolve()

    if args.verb == "sweep":
        return sweep(repo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
