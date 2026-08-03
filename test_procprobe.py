from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

from dev import procprobe


ROOT = Path(__file__).parent


def _stop_pid(process: subprocess.Popen[bytes]) -> None:
    """Stop only the fixture pid; never search the live process table."""
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)


def test_naive_argv_waiter_self_matches_but_run_waits_for_exact_child():
    token = "procprobe-self-%s" % uuid.uuid4().hex
    naive = subprocess.Popen([
        "bash", "-c",
        "while pgrep -f '%s' >/dev/null; do sleep 0.02; done" % token,
    ])
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            naive.wait(timeout=0.2)
    finally:
        _stop_pid(naive)

    safe = subprocess.run(
        [
            sys.executable, str(ROOT / "dev" / "procprobe.py"), "run", "--",
            sys.executable, "-c", "pass", token,
        ],
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
    )
    assert safe.returncode == 0, (
        "procprobe run inherited an argv subject instead of waiting for its exact child: "
        + safe.stderr
    )


def test_probe_excludes_its_own_process_tree_before_classification(tmp_path, monkeypatch):
    proc_dir = tmp_path / "proc" / str(os.getpid())
    proc_dir.mkdir(parents=True)
    (proc_dir / "cwd").symlink_to(tmp_path, target_is_directory=True)
    (proc_dir / "cmdline").write_bytes(b"ccc\x00brief mentions ccc\x00")
    monkeypatch.setattr(procprobe, "_ancestor_pids", lambda: {os.getpid()})

    scan = procprobe.scan_lane_runners(
        tmp_path.resolve(), pids=[os.getpid()], proc_root=tmp_path / "proc")

    assert scan.matches == (), (
        "self-match: probe counted its own PID %d as a lane runner" % os.getpid())
    assert scan.count(procprobe.ObservationState.EXCLUDED) == 1
    assert scan.status == "unknown", "examined zero must not be reported as absent"


def test_runner_match_uses_exact_argv_zero_not_brief_prose(tmp_path):
    proc_root = tmp_path / "proc"
    target = tmp_path / "lane"
    target.mkdir()
    runner = proc_root / "101"
    prose = proc_root / "102"
    runner.mkdir(parents=True)
    prose.mkdir()
    (runner / "cwd").symlink_to(target, target_is_directory=True)
    (prose / "cwd").symlink_to(target, target_is_directory=True)
    (runner / "cmdline").write_bytes(b"/fixture/ccc\x00task brief\x00")
    (prose / "cmdline").write_bytes(b"/usr/bin/python3\x00brief quotes land_lane and ccc\x00")

    scan = procprobe.scan_lane_runners(
        target.resolve(), pids=[101, 102], proc_root=proc_root,
        skip_pids=set(), uid=os.geteuid())

    assert scan.matches == (101,)
    assert scan.status == "present"
    assert scan.examined == 2


def test_exact_interpreter_probe_does_not_match_a_brief_quoting_the_script(tmp_path):
    proc_root = tmp_path / "proc"
    target = tmp_path / "coordinator"
    target.mkdir()
    for pid in (111, 112):
        process = proc_root / str(pid)
        process.mkdir(parents=True)
        (process / "cwd").symlink_to(target, target_is_directory=True)
    (proc_root / "111" / "cmdline").write_bytes(
        b"/usr/bin/python3\x00dev/land_lane.py\x00--lane\x00cx-1\x00")
    (proc_root / "112" / "cmdline").write_bytes(
        b"/usr/bin/ccc\x00brief quotes dev/land_lane.py\x00")

    scan = procprobe.scan_exact_command(
        target.resolve(), argv0="python3", argv1="dev/land_lane.py",
        pids=[111, 112], proc_root=proc_root, skip_pids=set(), uid=os.geteuid())

    assert scan.matches == (111,), (
        "exact probe inherited its subject from arbitrary argv prose")


def test_live_spawned_runner_fixture_is_found_without_scanning_the_fleet(tmp_path):
    runner = tmp_path / "ccc"
    runner.symlink_to("/bin/sleep")
    process = subprocess.Popen([str(runner), "30"], cwd=tmp_path)
    try:
        deadline = time.monotonic() + 2
        proc_dir = Path("/proc") / str(process.pid)
        while (
            os.readlink(proc_dir / "cwd") != str(tmp_path)
            or not procprobe._is_lane_runner((proc_dir / "cmdline").read_bytes())
        ):
            assert time.monotonic() < deadline
            time.sleep(0.01)
        scan = procprobe.scan_lane_runners(
            tmp_path.resolve(), pids=[process.pid], skip_pids=set())
        assert scan.matches == (process.pid,)
        assert scan.status == "present"
    finally:
        _stop_pid(process)


def test_gone_unreadable_and_absent_remain_distinct(tmp_path, monkeypatch):
    proc_root = tmp_path / "proc"
    target = tmp_path / "lane"
    target.mkdir()
    for pid in (201, 202, 203):
        (proc_root / str(pid)).mkdir(parents=True)
    (proc_root / "203" / "cwd").symlink_to(tmp_path, target_is_directory=True)

    real_readlink = os.readlink

    def controlled_readlink(path):
        if Path(path).parent.name == "202":
            raise PermissionError("fixture unreadable")
        return real_readlink(path)

    monkeypatch.setattr(procprobe.os, "readlink", controlled_readlink)
    scan = procprobe.scan_lane_runners(
        target.resolve(), pids=[201, 202, 203], proc_root=proc_root,
        skip_pids=set(), uid=os.geteuid())

    assert scan.count(procprobe.ObservationState.GONE) == 1
    assert scan.count(procprobe.ObservationState.UNREADABLE) == 1
    assert scan.count(procprobe.ObservationState.OTHER) == 1
    assert scan.status == "unknown", "unreadable must not collapse into absent"

    absent = procprobe.RunnerScan((
        procprobe.ProcessObservation(203, procprobe.ObservationState.OTHER),
    ))
    assert absent.status == "absent"
