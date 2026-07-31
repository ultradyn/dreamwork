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
import subprocess
import sys
import time
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
    # The fake process must DIE on SIGTERM. After os.kill(pid, 15) returns,
    # do_kill polls os.kill(pid, 0); that probe must raise ProcessLookupError
    # for the record to be confirmed gone (REAPED). A fake that returns None
    # for the probe would read as still-alive and yield SIGNALLED — which is
    # exactly the bug this test exists to keep red against.
    sent = []
    def fake_kill(pid, sig):
        sent.append((pid, sig))
        if sig == 0:
            raise ProcessLookupError  # process confirmed gone
    monkeypatch.setattr("os.kill", fake_kill)
    monkeypatch.setattr(reaper, "_VERIFY_TIMEOUT", 0.1)
    rc = reaper.main(["--kill", "--all-dead", "--yes"])
    assert rc == 0
    assert sent == [(424243, 15), (424243, 0)], \
        "SIGTERM (15) then a probe (0); the probe is the verification step"
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


def test_a_deployed_dashboard_is_never_reaped_even_when_dead_lane(monkeypatch, capsys):
    """The instance the human READS must not be sweepable. (#203 follow-up.)

    `is_deployed` was computed and printed as a note, but not consulted by the
    kill path — so a deployed dashboard whose cwd had gone `(deleted)`
    classified as dead-lane like anything else and `--all-dead --yes` would
    SIGTERM it. That is reachable in practice: `just deploy` starts the
    snapshot from the current directory, so deploying from a worktree and later
    removing that worktree produces exactly this record.

    The two preconditions are asserted rather than assumed, because each one
    alone makes the test vacuous: if the fixture were not dead-lane the sweep
    would skip it for the ordinary reason, and if it were not flagged deployed
    there would be nothing for the new guard to key on.
    """
    fake = _dead_record(424244)
    fake["is_deployed"] = True
    fake["cmd"] = ("python3 /home/xertrov/.cache/dreamwork/deployed/"
                   "ud-dreamwork-watch.py --port 35110")
    assert fake["classification"] == "dead-lane", \
        "fixture must be dead-lane, else --all-dead skips it for the wrong reason"
    assert fake["is_deployed"], "fixture must be flagged deployed, else nothing is tested"
    monkeypatch.setattr(reaper, "gather", lambda hours: [fake])
    killed = []
    monkeypatch.setattr("os.kill", lambda pid, sig: killed.append((pid, sig)))

    rc = reaper.main(["--kill", "--all-dead", "--yes"])
    assert killed == [], "the deployed dashboard must survive a --yes sweep"
    out = capsys.readouterr().out
    assert "deployed" in out.lower(), \
        "and the skip must SAY it was the deployed instance, not vanish silently"
    assert rc == 0, "sparing it is the correct outcome, not an error"

    # ...and naming it explicitly must not be a way around the guard either:
    # an operator reaching for --pid is at least as likely to have the wrong pid.
    killed.clear()
    reaper.main(["--kill", "--pid", "424244"])
    assert killed == [], "--pid must not reach the deployed instance either"


# ---------------------------------------------------------------------------
# exit verification (#730): REAPED vs SIGNALLED must not collapse
#
# The old code appended to `killed` the instant os.kill RETURNED, so a process
# that ignored SIGTERM, was still shutting down, or was wedged in D state all
# rendered as REAPED. That is #136 ("gone" and "I did not look" must not render
# identically) and #671 (a completed action that verified nothing must not read
# as done). These tests exercise the branch against REAL processes — a fake
# os.kill that returns None for the probe passes against the broken code too.
# ---------------------------------------------------------------------------

def test_wait_for_exit_returns_true_when_pid_is_gone(monkeypatch):
    # The probe raises ProcessLookupError immediately => gone.
    calls = []
    def probe(pid, sig):
        calls.append((pid, sig))
        raise ProcessLookupError
    monkeypatch.setattr("os.kill", probe)
    assert reaper._wait_for_exit(999, timeout=1.0, poll=0.01) is True
    assert calls == [(999, 0)], "a single sig-0 probe that raised ends the wait"


def test_wait_for_exit_returns_false_when_pid_still_alive(monkeypatch):
    # The probe succeeds every time => still alive at timeout.
    monkeypatch.setattr("os.kill", lambda pid, sig: None)  # no exception
    slept = []
    monkeypatch.setattr(reaper.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(reaper.time, "monotonic", iter([0.0, 0.0, 10.0]).__next__)
    assert reaper._wait_for_exit(999, timeout=1.0, poll=0.01) is False


def test_reaped_confirms_exit_against_a_real_victim():
    """A cooperative process that dies on SIGTERM must report REAPED, and the
    real os.kill path must be exercised (no monkeypatch on os.kill)."""
    import subprocess
    # `sleep` has no SIGTERM handler; default disposition terminates it.
    victim = subprocess.Popen(["sleep", "300"])
    assert victim.poll() is None, "precondition: victim is alive before reap"
    rec = _dead_record(victim.pid)
    assert rec["classification"] == "dead-lane"
    killed, signalled, refused, skipped = reaper.do_kill(
        [rec], [victim.pid], False, set(), verify_timeout=5.0)
    try:
        assert killed == [rec], "a process that exits after SIGTERM is REAPED"
        assert signalled == [], "must not be SIGNALLED when it actually died"
        assert victim.poll() is not None, "ground truth: the victim is dead"
    finally:
        if victim.poll() is None:
            victim.kill()
            victim.wait()


def test_signalled_when_sigterm_is_ignored_real_victim():
    """THE discriminating test (#730, #136): a process that IGNORES SIGTERM
    must report SIGNALLED and NOT REAPED. Uses a real child with SIG_IGN —
    no os.kill monkeypatch, so the SIGNALLED branch is genuinely taken.

    A happy-path-only test passes against today's broken code, because today's
    code gets the happy path right; this is the one that does not.
    """
    import tempfile
    ready = tempfile.NamedTemporaryFile(delete=False)
    ready.close()
    os.unlink(ready.name)  # child will create it; absence = not ready
    victim = subprocess.Popen(
        ["python3", "-c",
         "import os,signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
         "open(%r,'w').close(); time.sleep(300)" % ready.name],
        env={**os.environ})
    # Wait until the handler is actually installed, else SIGTERM wins the race
    # and the test exercises the REAPED path instead of the SIGNALLED one.
    for _ in range(200):
        if os.path.exists(ready.name):
            break
        time.sleep(0.01)
    assert os.path.exists(ready.name), "precondition: victim installed SIG_IGN"
    assert victim.poll() is None, "precondition: victim alive before reap"
    rec = _dead_record(victim.pid)
    assert rec["classification"] == "dead-lane"
    killed, signalled, refused, skipped = reaper.do_kill(
        [rec], [victim.pid], False, set(), verify_timeout=0.4)
    try:
        # precondition held: SIGTERM was delivered and ignored
        assert victim.poll() is None, \
            "precondition: the victim must still be alive (it ignores SIGTERM)"
        assert signalled == [rec], \
            "a SIGTERM-ignoring process is SIGNALLED, not REAPED"
        assert killed == [], \
            "must NOT be REAPED — the process is verified still alive (#136)"
    finally:
        victim.kill()  # SIGKILL is the human's call, not the reaper's
        victim.wait()


def test_signalled_renders_distinctly_and_names_the_pid(monkeypatch, capsys):
    """The operator reads SIGNALLED, sees the pid, and the message says it is
    NOT confirmed gone and offers the kill command as a human decision."""
    import tempfile
    ready = tempfile.NamedTemporaryFile(delete=False)
    ready.close()
    os.unlink(ready.name)
    victim = subprocess.Popen(
        ["python3", "-c",
         "import os,signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
         "open(%r,'w').close(); time.sleep(300)" % ready.name],
        env={**os.environ})
    for _ in range(200):
        if os.path.exists(ready.name):
            break
        time.sleep(0.01)
    assert os.path.exists(ready.name), "victim must be ready before reaping"
    try:
        rec = _dead_record(victim.pid)
        monkeypatch.setattr(reaper, "gather", lambda hours: [rec])
        monkeypatch.setattr(reaper, "_VERIFY_TIMEOUT", 0.3)
        rc = reaper.main(["--kill", "--pid", str(victim.pid)])
        out = capsys.readouterr().out
        assert rc == 0
        assert f"SIGNALLED pid={victim.pid}" in out
        assert "REAPED" not in out, "REAPED must not appear for a survivor"
        assert "NOT confirmed gone" in out
        assert f"kill -9 {victim.pid}" in out, \
            "the human's one-command decision must be named"
        assert victim.poll() is None, "the tool did not kill it"
    finally:
        victim.kill()
        victim.wait()


def test_do_kill_returns_four_lists():
    """do_kill now returns (killed, signalled, refused, skipped). A caller that
    unpacks three would silently drop the signalled pids — pin the arity."""
    result = reaper.do_kill([], [], False, set())
    assert len(result) == 4
