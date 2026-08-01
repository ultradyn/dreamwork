#!/usr/bin/env python3
"""Tests for dev/lane_status.py — dead-lane legibility (#876)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest


ROOT = Path(__file__).resolve().parent
TOOL = ROOT / "dev" / "lane_status.py"
REDPROOF = ROOT / "dev" / "redproof.py"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "master")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    (repo / "file.txt").write_text("base\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    return repo


def _add_worktree(repo: Path, lane: str) -> Path:
    path = repo.parent / ".worktrees" / lane
    _git(repo, "worktree", "add", str(path), "-b", lane)
    return path


def _write_lock(worktree: Path, pid: int, lane: str) -> None:
    lock_dir = worktree / ".dreamwork"
    lock_dir.mkdir(exist_ok=True)
    identity = str(worktree / f".{lane}-lane-identity")
    (worktree / ".dreamwork" / "lane.lock").write_text(
        json.dumps({"pid": pid, "task": 900, "lane": lane,
                    "brief": "/fixture/brief.md", "identity": identity})
        + "\n",
        encoding="utf-8")


def _arm_injection(worktree: Path, scratch: Path, *,
                   subject: str = "victim.py",
                   expectation: str = "expectation.txt") -> None:
    """Arm a redproof injection in a worktree and leave it sabotaged.

    The begun-but-unrestored state is the dangerous one #876/#915 watch for.
    Pins an INDEPENDENT expectation file (not the subject) so the red-proof
    evidence is not its own subject (#906).
    """
    (worktree / subject).write_text("original = 1\n")
    (worktree / expectation).write_text("independent expectation bytes\n")
    env = {**os.environ, "REDPROOF_SCRATCH_ROOT": str(scratch)}
    begin = subprocess.run(
        [sys.executable, str(REDPROOF), "begin", subject,
         "--expectation", expectation, "--cwd", str(worktree)],
        capture_output=True, text=True, env=env,
    )
    assert begin.returncode == 0, (
        f"redproof begin failed (rc={begin.returncode}): {begin.stderr!r}")
    # Sabotage and leave it unrestored — the armed state.
    (worktree / subject).write_text("SABOTAGED = 0\n")


def _sweep_env(scratch: Path) -> dict:
    return {"REDPROOF_SCRATCH_ROOT": str(scratch)}


def _run_sweep(repo: Path, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    actual_env = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, str(TOOL), "sweep", "--repo", str(repo)],
        capture_output=True, text=True, env=actual_env,
    )


def test_sweep_over_zero_lanes_does_not_report_all_clear(tmp_path):
    """The zero-denominator: a sweep over zero worktrees is not an all-clear (#868)."""
    repo = _make_repo(tmp_path)
    result = _run_sweep(repo)
    assert result.returncode == 0
    assert "examined 0 lane worktree(s)" in result.stdout
    assert "EXAMINED NOTHING" in result.stdout
    assert "not an all-clear" in result.stdout


def test_sweep_reports_dead_lane_with_dirty_work(tmp_path):
    repo = _make_repo(tmp_path)
    wt = _add_worktree(repo, "cx-dead")
    _write_lock(wt, 999999, "cx-dead")  # pid that does not exist
    (wt / "file.txt").write_text("uncommitted change\n")

    result = _run_sweep(repo)

    assert result.returncode == 0  # dirty is not armed; not an error
    assert "examined 1 lane worktree(s)" in result.stdout
    assert "cx-dead" in result.stdout
    assert "DEAD" in result.stdout
    # Derive the expected dirty count independently — the lock file may also
    # count, so the exact number is not a literal the test should hardcode.
    dirty = _git(wt, "status", "--porcelain=v1", "--untracked-files=normal")
    expected_dirty = len([l for l in dirty.splitlines() if l.strip()])
    assert expected_dirty > 0, "precondition: the worktree should have dirty work"
    assert f"{expected_dirty} dirty" in result.stdout


def test_sweep_reports_armed_injections_prominently(tmp_path):
    """A dead lane with armed injections is the dangerous state (#876)."""
    repo = _make_repo(tmp_path)
    wt = _add_worktree(repo, "cx-armed")
    _write_lock(wt, 999999, "cx-armed")
    # Arm a redproof injection in the worktree (isolated scratch to avoid
    # cross-test registry leakage from identical repo/lane keys).
    scratch = tmp_path / "redproof-scratch"
    _arm_injection(wt, scratch)

    # The sweep must use the SAME scratch root to see the armed entry.
    result = _run_sweep(repo, env=_sweep_env(scratch))

    assert result.returncode == 1, (
        f"sweep should exit 1 for armed injections; stdout={result.stdout!r}"
    )
    assert "cx-armed" in result.stdout
    assert "ARMED" in result.stdout
    assert "victim.py" in result.stdout
    assert "mid-red-proof" in result.stdout


def test_sweep_reports_each_condition_independently_not_lumped(tmp_path):
    """A dirty lane with NO armed injections must not be flagged as armed."""
    repo = _make_repo(tmp_path)
    wt = _add_worktree(repo, "cx-dirty-clean")
    _write_lock(wt, 999999, "cx-dirty-clean")
    (wt / "file.txt").write_text("dirty but no injections\n")

    result = _run_sweep(repo)

    assert result.returncode == 0
    line = [l for l in result.stdout.splitlines() if "cx-dirty-clean" in l][0]
    assert "DEAD" in line
    assert "dirty" in line
    assert "0 dirty" not in line, "precondition: should have dirty work"
    assert "ARMED" not in line, (
        f"lane flagged for the wrong reason — dirty != armed: {line!r}"
    )


def test_sweep_examined_count_includes_main_checkout(tmp_path):
    """The examined count distinguishes lanes from the main checkout."""
    repo = _make_repo(tmp_path)
    _add_worktree(repo, "cx-one")
    _add_worktree(repo, "cx-two")

    result = _run_sweep(repo)

    assert "examined 2 lane worktree(s)" in result.stdout
    assert "of 3 registered, including main" in result.stdout


# --- #915: a registered worktree that is not a lane must not be counted -------
# The fleet denominator is the number the human steers by; a pytest fixture that
# registered itself under a tmp dir and was reaped (missing path) or regenerated
# (non-lane path) re-inflated it. These guards pin the exclusion and its count.


def test_sweep_excludes_worktree_whose_path_is_missing_and_reports_count(tmp_path):
    """Direction 1 (#915): a registered worktree whose dir was reaped is a
    corpse, not a lane. It is excluded and the exclusion count is reported;
    clearing the registration returns the count to zero.

    The expected lane set is derived from the worktrees this test created
    (one live, one corpse), not from ``git worktree list`` (#906).
    """
    repo = _make_repo(tmp_path)
    live = _add_worktree(repo, "cx-live")
    corpse = _add_worktree(repo, "cx-corpse")
    shutil.rmtree(corpse)  # dir reaped; the registration survives — the #915 corpse
    assert not corpse.exists(), "precondition: corpse dir is gone"
    assert live.exists(), "precondition: exactly one live lane remains"

    result = _run_sweep(repo)
    assert result.returncode == 0
    assert "examined 1 lane worktree(s)" in result.stdout  # corpse not counted
    assert "excluded 1" in result.stdout
    assert "missing path" in result.stdout

    # Clear the corpse's registration; the exclusion count returns to zero.
    # (prune is the remedy for the registration, not the fix — #915 point (c).)
    _git(repo, "worktree", "prune")  # fixture repo only, never the live registry
    result2 = _run_sweep(repo)
    assert "examined 1 lane worktree(s)" in result2.stdout
    assert "excluded 0" in result2.stdout


def test_sweep_excludes_existing_path_that_is_not_under_fleet_roots(tmp_path):
    """Direction 2 (#915): a worktree whose path EXISTS but is not under a
    canonical fleet root is not a lane. A pure existence check would count it
    forever; the roots discriminator excludes it and names 'non-lane path'.

    This is the false-green a path-only check would ship: a stray checkout
    somewhere unrelated that happens to be on disk.
    """
    repo = _make_repo(tmp_path)
    live = _add_worktree(repo, "cx-live")
    assert live.exists()
    # A stray checkout OUTSIDE the fleet roots, whose path exists.
    stray = tmp_path / "elsewhere" / "stray"
    stray.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", str(stray), "-b", "stray-branch")
    assert stray.exists(), "precondition: the non-lane path exists"

    result = _run_sweep(repo)
    assert result.returncode == 0
    assert "examined 1 lane worktree(s)" in result.stdout  # only the lane
    assert "excluded 1" in result.stdout
    assert "non-lane" in result.stdout


def test_armed_lane_still_counted_and_exits_1_alongside_a_corpse(tmp_path):
    """THE fail-closed contract — #915's one-thing-not-to-break.

    An exclusion rule that silenced an ARMED lane would turn the alarm the human
    actually watches for into silence. Construct a real lane in the ARMED state
    SHARING a registry with a missing-path corpse: the armed lane must still be
    counted, reported, and exit 1, while the corpse is excluded.
    """
    repo = _make_repo(tmp_path)
    armed = _add_worktree(repo, "cx-armed")
    _write_lock(armed, 999999, "cx-armed")
    scratch = tmp_path / "redproof-scratch"
    _arm_injection(armed, scratch)
    # A corpse in the SAME registry.
    corpse = _add_worktree(repo, "cx-corpse")
    shutil.rmtree(corpse)
    assert not corpse.exists()
    assert armed.exists()

    result = _run_sweep(repo, env=_sweep_env(scratch))

    assert result.returncode == 1, "ARMED lane must still trip exit 1"
    assert "examined 1 lane worktree(s)" in result.stdout  # armed counted
    assert "cx-armed" in result.stdout
    assert "ARMED" in result.stdout
    assert "victim.py" in result.stdout
    assert "excluded 1" in result.stdout
    assert "missing path" in result.stdout


def test_sweep_with_only_a_corpse_is_loud_not_a_clean_sweep(tmp_path):
    """DEGRADE-TO-ZERO (#915/#868): a registry holding only a corpse must not
    read as a clean sweep. '0 lanes ARMED' is distinguishable from '0 lanes
    examined' — the examined-nothing message stays loud.
    """
    repo = _make_repo(tmp_path)
    corpse = _add_worktree(repo, "cx-corpse")
    shutil.rmtree(corpse)
    assert not corpse.exists()

    result = _run_sweep(repo)
    assert result.returncode == 0  # not ARMED
    assert "examined 0 lane worktree(s)" in result.stdout
    assert "excluded 1" in result.stdout
    assert "missing path" in result.stdout
    assert "EXAMINED NOTHING" in result.stdout
    assert "not an all-clear" in result.stdout
