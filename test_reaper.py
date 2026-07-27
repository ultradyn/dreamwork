#!/usr/bin/env python3
"""#203 — classifier tests for dev/reaper.py.

The reaper has two rules and they are NOT equal, and the tests exist to pin
that inequality:

  rule2 (dead-lane, MECHANICAL): readlink /proc/<pid>/cwd ends in " (deleted)".
        This is the ONLY rule that may kill, because a deleted cwd means the
        lane that started the server is gone — no threshold, no judgement.
  rule1 (stale, HEURISTIC):      elapsed >= stale_hours. Report only; a human
        must weigh "is 20 hours long", so the reaper never acts on it.

The tests are written red-first: each constructs two records that differ in
exactly the axis under test, asserts that axis really does differ (the
precondition the check depends on — CLAUDE.md), then asserts the classification
differs the way the rule requires. A literal tuned to today's machine is a
check with an expiry date; these derive both sides at runtime.

The live-process RED proof (start a server on 39894 from a dir you delete,
confirm dry-run spares it and --kill reaps it) is NOT here — it belongs in the
commit message as real terminal output, because it cannot be made deterministic
against a drifting process table.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "dev"))
import reaper  # noqa: E402


# ---------------------------------------------------------------------------
# rule2: the mechanical discriminator
# ---------------------------------------------------------------------------

def test_dead_lane_detected_by_deleted_cwd_suffix():
    base = {"cwd": "/tmp/some-lane", "target": "/tmp/x/target", "elapsed_secs": 30}
    live_rec = dict(base)
    dead_rec = dict(base, cwd=base["cwd"] + " (deleted)")
    # precondition: the two differ ONLY in cwd, and only in the deleted suffix
    assert live_rec["cwd"].endswith("some-lane")
    assert dead_rec["cwd"].endswith(" (deleted)")
    assert live_rec["cwd"].rstrip(" (deleted)") != dead_rec["cwd"]
    c_live, r_live = reaper.classify(live_rec, stale_hours=2.0)
    c_dead, r_dead = reaper.classify(dead_rec, stale_hours=2.0)
    assert c_dead == "dead-lane" and r_dead == reaper.RULE2
    assert c_live != "dead-lane", "a live cwd must never classify as dead-lane"


def test_rule2_beats_rule1_a_deleted_cwd_is_dead_even_if_ancient():
    # A server old enough to be stale AND with a deleted cwd is dead-lane
    # (rule2), NOT stale. The kill rule must not depend on a threshold.
    rec = {"cwd": "/tmp/gone (deleted)", "target": "/tmp/x", "elapsed_secs": 999_999}
    c, rule = reaper.classify(rec, stale_hours=2.0)
    assert c == "dead-lane" and rule == reaper.RULE2


def test_is_dead_lane_only_on_trailing_marker():
    # The marker is a kernel-emitted suffix on the EXACT tail; a path that
    # merely contains the substring must not match.
    assert reaper.is_dead_lane("/tmp/x (deleted)") is True
    assert reaper.is_dead_lane("/tmp/x (deleted)/child") is False
    assert reaper.is_dead_lane("/tmp/x") is False
    assert reaper.is_dead_lane("") is False


# ---------------------------------------------------------------------------
# rule1: the heuristic (report only)
# ---------------------------------------------------------------------------

def test_stale_when_elapsed_at_or_above_threshold():
    base = {"cwd": "/tmp/live-lane", "target": "/tmp/x/target", "elapsed_secs": 0}
    threshold_h = 2.0
    fresh = dict(base, elapsed_secs=int((threshold_h - 0.5) * 3600))
    stale = dict(base, elapsed_secs=int((threshold_h + 1.0) * 3600))
    # precondition: one is genuinely below, one above the threshold
    assert fresh["elapsed_secs"] / 3600.0 < threshold_h
    assert stale["elapsed_secs"] / 3600.0 >= threshold_h
    assert fresh["elapsed_secs"] != stale["elapsed_secs"]
    c_fresh, r_fresh = reaper.classify(fresh, stale_hours=threshold_h)
    c_stale, r_stale = reaper.classify(stale, stale_hours=threshold_h)
    assert c_fresh == "live" and r_fresh is None
    assert c_stale == "stale" and r_stale == reaper.RULE1


def test_stale_threshold_is_inclusive_at_boundary():
    rec = {"cwd": "/tmp/x", "target": "/tmp/x", "elapsed_secs": 2 * 3600}
    c, rule = reaper.classify(rec, stale_hours=2.0)
    assert c == "stale", "boundary (==) is stale; the human decides from the report"


def test_stale_is_never_dead_lane_and_never_killable():
    # rule1 is report-only: a stale record must not be classified dead-lane
    # (only a deleted cwd does that), so the reaper's kill path cannot reach it.
    rec = {"cwd": "/tmp/live", "target": "/tmp/x", "elapsed_secs": 100 * 3600}
    c, rule = reaper.classify(rec, stale_hours=2.0)
    assert c == "stale"
    assert c != "dead-lane"


# ---------------------------------------------------------------------------
# parse_cmdline: who counts as a watch server, and what port/target
# ---------------------------------------------------------------------------

def test_watch_server_detected_by_watch_py_basename_plus_server_flag():
    # The deployed snapshot is named ud-dreamwork-watch.py and must count.
    deployed = ["python3", "/home/x/.cache/dreamwork/deployed/ud-dreamwork-watch.py",
                "--target", "/repo", "--dev"]
    info = reaper.parse_cmdline(deployed)
    assert info["is_watch_server"] is True
    assert info["target"] == "/repo"


def test_grep_watch_py_is_not_a_watch_server():
    # `ps | grep watch.py` and `grep watch.py file` have "watch.py" as an arg
    # but no server flag — the flag gate stops the false positive. The gap
    # between these two records is exactly the flag, nothing else.
    flagged = ["python3", "watch.py", "--port", "39891"]
    bare = ["grep", "watch.py"]
    base_with_flag = reaper.parse_cmdline(flagged)
    base_without_flag = reaper.parse_cmdline(bare)
    assert base_with_flag["is_watch_server"] is True
    assert base_without_flag["is_watch_server"] is False


def test_port_and_target_parsing_including_port_zero():
    cases = {
        "plain": (["python3", "watch.py", "--target", "/tmp/a", "--port", "39891"],
                  {"port": 39891, "port_was_zero": False, "target": "/tmp/a"}),
        "dash_u": (["python3", "-u", "watch.py", "--target", "/tmp/b", "--port", "0"],
                   {"port": 0, "port_was_zero": True, "target": "/tmp/b"}),
        "no_target": (["/usr/bin/python3", "./watch.py", "--dev", "--port", "35111"],
                      {"port": 35111, "port_was_zero": False, "target": None}),
    }
    for name, (args, want) in cases.items():
        info = reaper.parse_cmdline(args)
        for k, v in want.items():
            assert info[k] == v, f"{name}: {k}={info[k]!r} want {v!r}"
        assert info["is_watch_server"] is True, name


# ---------------------------------------------------------------------------
# /proc arithmetic (pure, so it can be tested without a live process)
# ---------------------------------------------------------------------------

def test_elapsed_from_starttime_is_just_clock_arithmetic():
    # starttime_ticks is jiffies since boot; btime is boot epoch.
    # elapsed = now - (btime + ticks/clktck). 100Hz is the Linux default.
    clktck = 100
    btime = 1_000_000.0
    starttime = 600 * clktck  # started 600s after boot
    now = 1_000_000.0 + 600.0 + 42.0  # 42s later
    assert reaper.elapsed_from_starttime(starttime, btime, now, clktck) == pytest.approx(42.0)


def test_parse_proc_stat_handles_parens_in_comm_and_finds_starttime():
    # Field 22 is starttime; comm (field 2) may contain spaces and parens,
    # so naive split() on the raw line is wrong. Construct a realistic line.
    # Layout: pid (comm) state ppid pgrp session tty_nr tpgid flags minflt
    #   cminflt majflt cmajflt utime stime cutime cstime priority nice
    #   num_threads itrealvalue starttime ...
    # Fields 3..21 are 19 fields; starttime is the 20th after ')'.
    fields_after_comm = ["S", "1092", "1092", "1092", "0", "-1", "0", "1"] + ["0"] * 11
    want_starttime = 123456789
    stat = f"897036 ((python3) worker) " + " ".join(fields_after_comm) + f" {want_starttime} " + " ".join(["0"] * 20)
    comm, starttime = reaper.parse_proc_stat(stat)
    assert comm == "(python3) worker", "parens inside comm must survive verbatim"
    assert starttime == want_starttime


# ---------------------------------------------------------------------------
# --all-dead safety gate (motivated by a real error during this task: an
# ungated --all-dead swept two pids the operator was told to spare, because
# their cwds had drifted to (deleted) since dispatch. The gate turns that
# into a refuse-with-guidance. These lock it.)
# ---------------------------------------------------------------------------

def _dead_record(pid):
    rec = {"pid": pid, "cwd": f"/tmp/gone-{pid} (deleted)",
           "target": "/tmp/x/target", "port": 39999,
           "port_requested_zero": False, "elapsed_secs": 99999,
           "elapsed_unknown": False,
           "cmd": f"python3 watch.py --target /tmp/x/target --port 39999",
           "is_deployed": False}
    rec["classification"], rec["rule"] = reaper.classify(
        {"cwd": rec["cwd"], "target": rec["target"],
         "elapsed_secs": rec["elapsed_secs"]}, stale_hours=2.0)
    return rec


def test_all_dead_refuses_without_yes(monkeypatch, capsys):
    fake = _dead_record(424242)
    # precondition: the fake record really IS dead-lane (the only killable class)
    assert fake["classification"] == "dead-lane", \
        "test fixture must be dead-lane or the assertion below is meaningless"
    monkeypatch.setattr(reaper, "gather", lambda hours: [fake])
    killed = []
    monkeypatch.setattr("os.kill", lambda pid, sig: killed.append((pid, sig)))
    rc = reaper.main(["--kill", "--all-dead"])
    assert rc == 2, "--all-dead must refuse (exit 2) without --yes"
    err = capsys.readouterr().err
    assert "REFUSED without --yes" in err
    assert "DREAMWORK_REAP_NEVER_KILL=424242" in err, \
        "refusal must print the never-kill env so the operator can spare pids"
    assert killed == [], "no kill may happen when --yes is absent"


def test_all_dead_with_yes_reaps_dead_lane(monkeypatch, capsys):
    fake = _dead_record(424243)
    assert fake["classification"] == "dead-lane"
    monkeypatch.setattr(reaper, "gather", lambda hours: [fake])
    killed = []
    monkeypatch.setattr("os.kill", lambda pid, sig: killed.append((pid, sig)))
    rc = reaper.main(["--kill", "--all-dead", "--yes"])
    assert rc == 0
    assert killed == [(424243, 15)], "SIGTERM (15) the dead-lane pid once"
    assert "REAPED pid=424243" in capsys.readouterr().out


def test_all_dead_with_yes_still_respects_never_kill(monkeypatch, capsys):
    fake = _dead_record(424244)
    assert fake["classification"] == "dead-lane"
    monkeypatch.setattr(reaper, "gather", lambda hours: [fake])
    monkeypatch.setenv("DREAMWORK_REAP_NEVER_KILL", "424244")
    killed = []
    monkeypatch.setattr("os.kill", lambda pid, sig: killed.append((pid, sig)))
    rc = reaper.main(["--kill", "--all-dead", "--yes"])
    assert rc == 0
    assert killed == [], "never-kill pid must be spared even with --yes"
    assert "skipped pid=424244" in capsys.readouterr().out


def test_kill_pid_refuses_a_live_server(monkeypatch, capsys):
    # --pid is targeted (deliberate), so it needs no --yes; but it must still
    # REFUSE a non-dead-lane pid rather than kill it.
    live = {"pid": 424245, "cwd": "/tmp/live", "target": "/tmp/x",
            "port": 39999, "port_requested_zero": False, "elapsed_secs": 60,
            "elapsed_unknown": False, "cmd": "python3 watch.py --port 39999",
            "is_deployed": False}
    live["classification"], live["rule"] = reaper.classify(
        {"cwd": live["cwd"], "target": live["target"],
         "elapsed_secs": live["elapsed_secs"]}, 2.0)
    assert live["classification"] == "live", "precondition: fixture is live"
    monkeypatch.setattr(reaper, "gather", lambda hours: [live])
    killed = []
    monkeypatch.setattr("os.kill", lambda pid, sig: killed.append((pid, sig)))
    rc = reaper.main(["--kill", "--pid", "424245"])
    assert rc == 0
    assert killed == [], "a live pid must never be killed"
    err = capsys.readouterr().err
    assert "REFUSED pid=424245" in err and "not dead-lane" in err
