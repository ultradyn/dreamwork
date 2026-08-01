#!/usr/bin/env python3
"""Tests for dev/lane_status.py — dead-lane legibility (#876)."""

from __future__ import annotations

import json
import os
from pathlib import Path
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
    target = wt / "victim.py"
    target.write_text("original = 1\n")
    scratch = tmp_path / "redproof-scratch"
    begin_env = {**os.environ, "REDPROOF_SCRATCH_ROOT": str(scratch)}
    begin = subprocess.run(
        [sys.executable, str(REDPROOF), "begin", "victim.py", "--cwd", str(wt)],
        capture_output=True, text=True, env=begin_env,
    )
    assert begin.returncode == 0, (
        f"redproof begin failed (rc={begin.returncode}): {begin.stderr!r}"
    )
    # Sabotage it (the injection stays armed — never restored).
    target.write_text("SABOTAGED = 0\n")

    # The sweep must use the SAME scratch root to see the armed entry.
    sweep_env = {"REDPROOF_SCRATCH_ROOT": str(scratch)}
    result = _run_sweep(repo, env=sweep_env)

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
