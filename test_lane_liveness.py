"""Tests for strict lane-lock classification in :mod:`lane_liveness`."""

import json
from pathlib import Path

import pytest

import lane_liveness


def _subject(tmp_path, *, lane="cx-finished"):
    target = tmp_path / "project"
    target.mkdir()
    worktree = tmp_path / ".worktrees" / lane
    (worktree / ".dreamwork").mkdir(parents=True)
    identity = worktree / "brief.md"
    return target, worktree, identity


def _inspect(target, worktree):
    return lane_liveness.inspect_lanes(
        target, process_entries=["101"],
        registered_worktrees=(worktree,), read_cmdline=lambda _pid: b"")


def _write_lock(worktree, identity, **updates):
    record = {
        "pid": 4242,
        "task": 987,
        "lane": worktree.name,
        "identity": str(identity),
    }
    record.update(updates)
    (worktree / ".dreamwork" / "lane.lock").write_text(json.dumps(record))
    return record


def test_lockless_worktree_is_settled_not_finished(tmp_path):
    target, worktree, _identity = _subject(tmp_path, lane="cx-settled")

    inspection = _inspect(target, worktree)

    assert inspection.worktree_only == ("cx-settled",)
    assert inspection.finished == ()


def test_dead_runner_is_finished_with_its_lock_record(tmp_path, monkeypatch):
    target, worktree, identity = _subject(tmp_path)
    record = _write_lock(worktree, identity)
    monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_args: False)

    inspection = _inspect(target, worktree)

    expected = lane_liveness.FinishedLane(
        lane="cx-finished", task=987, pid=4242, identity=str(identity))
    assert (inspection.worktree_only == () and
            inspection.finished == (expected,)), \
        "cx-finished task #987 landed in wrong bucket: " \
        "worktree_only=%r finished=%r" % (
            inspection.worktree_only, inspection.finished)
    assert inspection.finished[0].pid == record["pid"]


def test_live_runner_stays_live_not_finished(tmp_path, monkeypatch):
    target, worktree, identity = _subject(tmp_path, lane="cx-live")
    _write_lock(worktree, identity)
    monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_args: True)

    inspection = _inspect(target, worktree)

    assert inspection.live == ("cx-live",)
    assert inspection.finished == ()


@pytest.mark.parametrize("fault", [
    "unreadable", "invalid-json", "missing-key", "wrong-lane", "outside",
])
def test_lock_faults_remain_liveness_unknown(tmp_path, monkeypatch, fault):
    target, worktree, identity = _subject(tmp_path)
    lock = worktree / ".dreamwork" / "lane.lock"
    if fault == "unreadable":
        lock.mkdir()
    elif fault == "invalid-json":
        lock.write_text("{")
    elif fault == "missing-key":
        _write_lock(worktree, identity)
        record = json.loads(lock.read_text())
        del record["task"]
        lock.write_text(json.dumps(record))
    elif fault == "wrong-lane":
        _write_lock(worktree, identity, lane="cx-someone-else")
    else:
        _write_lock(worktree, tmp_path / "outside" / "brief.md")
    monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_args: False)

    with pytest.raises(lane_liveness.LivenessUnknown):
        _inspect(target, worktree)


def test_recreated_worktree_with_old_lock_looks_finished(tmp_path, monkeypatch):
    """Open false-green: same path/name cannot prove worktree continuity."""
    target, worktree, identity = _subject(tmp_path, lane="cx-recreated")
    _write_lock(worktree, identity, task=111)
    monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_args: False)

    inspection = _inspect(target, worktree)

    assert inspection.finished[0].task == 111


def test_pid_reuse_can_make_a_dead_lane_look_live(tmp_path, monkeypatch):
    """Open false-green: an unrelated same-cwd process can reuse the pid."""
    target, worktree, identity = _subject(tmp_path, lane="cx-pid-reused")
    _write_lock(worktree, identity, task=222)
    probe = lane_liveness.pid_matches_lane
    monkeypatch.setattr(
        lane_liveness, "pid_matches_lane",
        lambda pid, brief: probe(
            pid, brief, is_pid_alive=lambda _pid: True,
            proc_cwd=lambda _pid: str(Path(brief).parent)))

    inspection = _inspect(target, worktree)

    assert inspection.live == ("cx-pid-reused",)
    assert inspection.finished == ()


def test_valid_dead_lock_is_finished_without_git_or_scratch_evidence(
        tmp_path, monkeypatch):
    """The never-started shape remains actionable without claiming commits."""
    target, worktree, identity = _subject(tmp_path, lane="cx-never-started")
    _write_lock(worktree, identity, task=333)
    monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_args: False)

    inspection = _inspect(target, worktree)

    assert inspection.finished[0].lane == "cx-never-started"


def test_stale_lock_on_settled_branch_looks_finished(tmp_path, monkeypatch):
    """Open false-green: lock age is not represented in the record."""
    target, worktree, identity = _subject(tmp_path, lane="cx-stale-lock")
    _write_lock(worktree, identity, task=444)
    monkeypatch.setattr(lane_liveness, "pid_matches_lane", lambda *_args: False)

    inspection = _inspect(target, worktree)

    assert inspection.finished[0].lane == "cx-stale-lock"
