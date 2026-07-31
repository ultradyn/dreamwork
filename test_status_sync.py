"""Tests for `status_sync.py` — #402a.

The hard part of this change is the TEST, not the fix. The natural way to
test the live-lane detector fakes `subprocess.run` and hands it a fabricated
`ps` string; that test passes with the broken `^ccc @` pattern still in place
because the fake never runs `pgrep` — the thing under test is the pattern, and
a fake replaces it. This repo has been bitten by that exact shape twice in one
day.

So criterion 1 below spawns a REAL process whose argv has today's dispatch
shape (a flag between the binary and the alias) and asserts the detector
finds its lane. That one cannot pass with a broken pattern. The remaining
criteria use real processes or real on-disk state wherever the branch can be
reached that way; fakes appear only beside the real-process test, for branches
a real process cannot reach (the OSError path), and each such test names the
production line that must change for it to fail.
"""
import contextlib
import io
import json
import os
import re
import subprocess
import time
from pathlib import Path

import pytest

import status_sync


# ── helpers ──────────────────────────────────────────────────────────────

def _ledger(*ids: int) -> str:
    """A minimal valid ledger with `ids` open. Combined heads expand."""
    body = "\n".join(f"- **#{i}** lane {i}" for i in ids)
    return f"## Open\n{body}\n"


def _write_target(tmp_path: Path, status: dict, ledger: str) -> Path:
    dw = tmp_path / ".dreamwork"
    dw.mkdir(exist_ok=True)
    (dw / "status.json").write_text(json.dumps(status, indent=2) + "\n")
    (dw / "tasks.md").write_text(ledger)
    return tmp_path


def _run(status: dict, ledger: str, tmp_path: Path, *extra: str):
    """Invoke the real `status_sync.main` against a fresh target.

    Captures rc + stdout + stderr by redirecting the streams (self-contained,
    no capsys plumbing). Calls `main` with its real argparse so the path under
    test is the one production takes, not a hand-built helper call.
    """
    target = _write_target(tmp_path, status, ledger)
    out_s, err_s = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out_s), contextlib.redirect_stderr(err_s):
        rc = status_sync.main(["--target", str(target), *extra])
    return rc, out_s.getvalue(), err_s.getvalue()


def _which_perl() -> str:
    import shutil
    p = shutil.which("perl")
    if not p:
        pytest.skip("perl is required to shape a ccc-style argv for the "
                    "real-process liveness test")
    return p


def _spawn_lane(brief: str, hold: float = 30.0):
    """A live process whose /proc/cmdline is shaped like today's dispatch.

    Real dispatch is `ccc --yolo @glm52 <brief>` — a flag sits between the
    binary and the alias, which is exactly the shape `^ccc @` cannot match.
    `executable` sets argv independently of the binary run, so argv[0] is
    `ccc` and a flag precedes the alias. The `--` terminates perl's own
    option parsing so the trailing `--yolo` is treated as a script argument
    perl ignores (without it perl errors `Unrecognized switch: --yolo` and
    exits, leaving a zombie whose `kill -0` still succeeds — a false alive).
    No fake anywhere: the detector's real `pgrep` reads this real /proc entry.
    """
    return subprocess.Popen(
        ["ccc", "-e", f"sleep {hold}", "--", "--yolo", "@glm52", brief],
        executable=_which_perl(),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)


def _dead_pid() -> int:
    """A pid that is provably not running, precondition re-asserted by callers.

    Spawn a short-lived process, wait (reap) for it to exit, return its pid.
    Reaping avoids the zombie trap (`kill -0` succeeds on an unreaped child).
    Pid reuse in the test window is vanishingly rare, and every caller
    re-asserts `not status_sync._pid_alive(pid)` before relying on it — that
    assertion is the guard the brief demands, so a reuse would fail loudly
    rather than pass vacuously.
    """
    p = subprocess.Popen(["true"])
    pid = p.pid
    p.wait()
    return pid


# ── 1. the real-process test (cannot pass with the broken pattern) ───────

class TestRealProcessDetector:
    """Criterion 1: a real ccc-shaped dispatch is found; `^ccc @` would miss.

    Production line that must change for this to fail if broken: the pgrep
    pattern in `status_sync._argv_listing` (today `ccc`; the bug was `^ccc @`).
    This dreamer carries only a `brief` (no `pid`), forcing the listing path,
    so the pattern is what decides the result.
    """

    def test_a_flag_between_binary_and_alias_is_still_found(self, tmp_path):
        brief = f"/tmp/brief-402a-realproc-{os.getpid()}-{time.time_ns()}.md"
        proc = _spawn_lane(brief)
        try:
            time.sleep(0.6)
            # Precondition (not vacuous): the spawned lane really is alive and
            # the broad listing really does see its brief. If the spawn shape
            # ever stops matching real pgrep, this fails loudly here rather
            # than letting the detector assertion pass for the wrong reason.
            assert status_sync._pid_alive(proc.pid)
            listing = status_sync._argv_listing()
            assert brief in listing, \
                "precondition: pgrep listing must see the spawned brief"
            live, pruned = status_sync.live_lanes([{"task": 402, "brief": brief}])
            assert 402 in live, live
            assert [d["task"] for d in pruned] == [402]
        finally:
            proc.kill()
            proc.wait()


# ── 2. a dead lane is pruned; a live one is not ──────────────────────────

class TestPruneDeadLanes:
    """Criterion 2: dead lanes leave `dreamers`; live lanes stay.

    Production line that must change for this to fail: the `if is_live:
    pruned.append(d)` gate in `live_lanes` — removing the gate (always append)
    keeps the dead lane, failing the prune assertion.
    """

    def test_dead_pruned_live_kept_counts_derived(self, tmp_path):
        live_proc = _spawn_lane(f"/tmp/brief-402a-live-{time.time_ns()}.md")
        dead_pid = _dead_pid()
        try:
            time.sleep(0.6)
            # Preconditions, asserted at runtime, derived — never literals.
            assert status_sync._pid_alive(live_proc.pid), "live pid must be alive"
            assert not status_sync._pid_alive(dead_pid), "dead pid must be dead"
            dreamers = [
                {"task": 7, "pid": live_proc.pid, "brief": "live"},
                {"task": 9, "pid": dead_pid, "brief": "dead"},
            ]
            n_alive = sum(1 for d in dreamers
                          if not status_sync._missing_pid(d)
                          and status_sync._pid_alive(d["pid"]))
            n_dead = len(dreamers) - n_alive
            assert n_alive >= 1 and n_dead >= 1   # else the test is vacuous

            live, pruned = status_sync.live_lanes(dreamers)
            live_tasks = {d["task"] for d in pruned}
            assert 7 in live_tasks and 9 not in live_tasks
            assert len(pruned) == n_alive          # dead lane gone
            # Survivors are kept verbatim — nothing else about them changes.
            assert pruned == [d for d in dreamers if d["task"] == 7]
        finally:
            live_proc.kill()
            live_proc.wait()


# ── 3. a failed probe changes nothing ────────────────────────────────────

class TestFailedProbeIsNotADerivedEmpty:
    """Criterion 3: an unknown probe leaves the fields byte-identical.

    The old `OSError` branch returned `[]` — the same destroy-on-failure shape
    as the bug. Production line that must change for this to fail: the
    `except OSError as e: raise LivenessUnknown(...)` in `live_lanes` —
    reverting it to `ps = ""` lets the brief-only lane read as dead, so
    `current_task_ids` becomes `[]` and `dreamers` is pruned, and the file is
    rewritten. This fake is permitted (a real process cannot make pgrep raise
    OSError); it exercises the error-handling branch, not the pattern.
    """

    def test_oserror_leaves_fields_untouched_and_skips(self, tmp_path,
                                                       monkeypatch):
        dreamers = [{"task": 31, "brief": "/no/such/brief-402a.md"}]
        status = {
            "queue": {"in_progress": 1, "pending": 1},
            "current_task_ids": [31],
            "dreamers": dreamers,
            "task": "on #31",
        }
        ledger = _ledger(31)
        _write_target(tmp_path, status, ledger)
        spath = tmp_path / ".dreamwork" / "status.json"
        before = spath.read_bytes()

        def boom(*a, **k):
            raise OSError("pgrep exploded")
        monkeypatch.setattr(status_sync.subprocess, "run", boom)

        rc, out, err = _run(status, ledger, tmp_path)

        assert rc == 3                              # distinct from stale(1)/clean(0)
        assert spath.read_bytes() == before         # byte-identical, nothing written
        assert "liveness unknown" in err.lower(), err
        # No clean sync line — the success message must not appear.
        assert "already in sync" not in out


# ── 4. mixed types and a sub-id survive ──────────────────────────────────

class TestMixedIdTypes:
    """Criterion 4: int, string id and sub-id together neither crash nor drop.

    Production line that must change for this to fail: `_normalise_live`'s
    `sorted(live, key=str)`. Reverting to `sorted(live)` raises
    `TypeError: '<' not supported between instances of 'str' and 'int'`.
    """

    def test_int_string_and_subid_all_survive_sorted_by_str(self, tmp_path):
        procs, dreamers = [], []
        for task in (396, "401", "392a"):
            brief = f"/tmp/brief-402a-mix-{task}-{time.time_ns()}.md"
            # A live pid decides liveness by the exact pid signal (the
            # measurement showed pid is the survivor), isolating the
            # mixed-type sort from the listing/brief path.
            p = _spawn_lane(brief)
            procs.append(p)
            dreamers.append({"task": task, "pid": p.pid, "brief": brief})
        try:
            time.sleep(0.7)
            assert all(status_sync._pid_alive(p.pid) for p in procs)
            status = {"dreamers": dreamers, "current_task_ids": [], "queue": {}}
            rc, out, err = _run(status, _ledger(396, 401, 392), tmp_path)
            assert rc == 0, err
            result = json.loads(
                (tmp_path / ".dreamwork" / "status.json").read_text())
            cti = result["current_task_ids"]
            assert "392a" in cti, cti               # sub-id kept, not coerced
            # Normalise-on-write (#402b): a quoted plain id "401" becomes int
            # 401; a sub-id "392a" stays a string. The plain int 396 is
            # already canonical.
            assert 396 in cti and 401 in cti, cti
            assert "401" not in cti, cti             # quoted plain id normalised
            assert cti == sorted([396, 401, "392a"], key=str), cti
        finally:
            for p in procs:
                p.kill(); p.wait()


# ── 5. coverage lists the untouched fields, derived from the file's keys ─

class TestCoverageIsDerived:
    """Criterion 5: a junk key appears in the untouched list, proving it is
    derived from the file's actual keys rather than a complete-on-today
    literal.

    Production line that must change for this to fail: `coverage`'s
    `sorted(k for k in status if k not in DERIVED)`.
    """

    def test_a_junk_key_shows_up_as_author_owned(self, tmp_path):
        status = {
            "queue": {"in_progress": 0, "pending": 1},
            "current_task_ids": [],
            "dreamers": [],
            "task": "on #1",
            "goal": "ship",
            "junk_field_402a": "added next month",   # proves it is derived
        }
        rc, out, err = _run(status, _ledger(1), tmp_path)
        assert rc == 0, err
        assert "junk_field_402a" in out, out          # junk key listed
        assert "task" in out and "goal" in out, out
        m = re.search(r"author-owned (\[.*?\])", out)
        assert m and "junk_field_402a" in m.group(1), out
        # Derived fields must NOT be listed as author-owned.
        assert "current_task_ids" not in m.group(1), out

    def test_coverage_prints_even_when_in_sync(self, tmp_path):
        # "already in sync" once read as success while other fields were stale;
        # coverage prints on every run including this one.
        status = {"queue": {"in_progress": 0, "pending": 1},
                  "current_task_ids": [], "dreamers": [], "task": "t"}
        rc, out, err = _run(status, _ledger(1), tmp_path)
        assert rc == 0, err
        assert "coverage:" in out and "already in sync" in out, out


# ── 6. --check keeps its contract ────────────────────────────────────────

class TestCheckContract:
    """Criterion 6: --check exits 1 when stale, writes nothing, and now also
    reports dreamers staleness."""

    def test_stale_dreamers_exits_1_writes_nothing_reports_dreamers(
            self, tmp_path):
        # A brief-only lane whose brief is not in any live argv reads as dead
        # and is pruned — deterministic, no process juggling.
        dreamers = [{"task": 5, "brief": "/no/such/brief-402a-check.md"}]
        status = {"queue": {"in_progress": 0, "pending": 1},
                  "current_task_ids": [], "dreamers": dreamers, "task": "t"}
        _write_target(tmp_path, status, _ledger(5))
        spath = tmp_path / ".dreamwork" / "status.json"
        before = spath.read_bytes()

        rc, out, err = _run(status, _ledger(5), tmp_path, "--check")
        assert rc == 1                                  # stale
        assert spath.read_bytes() == before             # wrote nothing
        assert "dreamers" in out.lower(), out           # reports dreamers staleness

    def test_clean_exits_0(self, tmp_path):
        status = {"queue": {"in_progress": 0, "pending": 1},
                  "current_task_ids": [], "dreamers": [], "task": "t"}
        rc, out, err = _run(status, _ledger(1), tmp_path, "--check")
        assert rc == 0, err


# ── docstring/contract invariant already pinned by test_watch ────────────

class TestLedgerHeadStillShared:
    """LEDGER_HEAD stays the one-copy head form (#331). test_watch pins the
    pattern identity; this is a cheap local echo so a regression here is
    visible next to the file that owns it."""

    def test_ledger_head_matches_watch(self):
        import watch
        assert status_sync.LEDGER_HEAD.pattern == \
            rf"^- \*\*({watch.IDS_ONLY_SPAN})\*\*"
        assert status_sync.LEDGER_HEAD.flags & re.M     # MULTILINE


# ── 7. a lane whose TASK has landed is reaped even with a live pid ──────
#
# #402(a): the syncer already reaps dead-pid entries (#402a), but an entry
# whose process is alive while its task has moved to `## Recently landed`
# was a hard STOP (return 2, "a lane is working on a task the ledger calls
# closed"). That stop blocks the whole sync for one stale entry — the
# opposite of "skip, report, keep going". The entry is not an owner: the
# coordinator moved the task to landed, so its file ownership is stale.

class TestReapLandedTask:
    """A live-pid entry whose task is NOT under `## Open` is reaped, not a
    hard stop.

    Production line whose reversion reds this test: the task-openness gate
    in ``main`` — ``if base is not None and base in ids: pruned.append(d)
    else: reaped.append(d)``. Reverting to the old ``unknown`` return-2
    path (or removing the gate so every pid-live entry survives) makes this
    fail: either rc == 2 (hard stop) or the landed entry survives in the
    written ``dreamers``.
    """

    def test_live_pid_landed_task_is_reaped_sync_continues(self, tmp_path):
        live_proc = _spawn_lane(f"/tmp/brief-402a-landed-{time.time_ns()}.md")
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(live_proc.pid), \
                "precondition: live pid must be alive"
            # The entry's task (999) is deliberately NOT in the open ledger.
            dreamers = [{"task": 999, "pid": live_proc.pid,
                         "brief": "/no/such/brief.md"}]
            # Precondition: 999 is not an open id, so the entry is stale.
            ledger = _ledger(7, 8)            # open: 7, 8 — not 999
            assert 999 not in status_sync.open_ids(ledger), \
                "precondition: task 999 must not be open"
            status = {"dreamers": dreamers, "current_task_ids": [999],
                      "queue": {"in_progress": 1, "pending": 1}, "task": "t"}
            rc, out, err = _run(status, ledger, tmp_path)
            # The sync must NOT hard-stop (old behaviour was return 2).
            assert rc != 2, err
            assert rc == 0, err
            result = json.loads(
                (tmp_path / ".dreamwork" / "status.json").read_text())
            # The landed entry is gone from dreamers.
            assert result["dreamers"] == [], result["dreamers"]
            # current_task_ids no longer claims 999 (it landed).
            assert 999 not in result["current_task_ids"], \
                result["current_task_ids"]
            # The sync reported the reap on stderr.
            assert "reaped" in err.lower() or "not under" in err.lower(), err
        finally:
            live_proc.kill()
            live_proc.wait()

    def test_live_pid_open_task_is_kept(self, tmp_path):
        live_proc = _spawn_lane(f"/tmp/brief-402a-keep-{time.time_ns()}.md")
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(live_proc.pid)
            dreamers = [{"task": 7, "pid": live_proc.pid,
                         "brief": "/no/such/brief.md"}]
            ledger = _ledger(7, 8)            # 7 IS open
            assert 7 in status_sync.open_ids(ledger), \
                "precondition: task 7 must be open"
            status = {"dreamers": dreamers, "current_task_ids": [],
                      "queue": {}, "task": "t"}
            rc, out, err = _run(status, ledger, tmp_path)
            assert rc == 0, err
            result = json.loads(
                (tmp_path / ".dreamwork" / "status.json").read_text())
            # The open-task entry survives — live pid, open task.
            assert len(result["dreamers"]) == 1, result["dreamers"]
            assert result["dreamers"][0]["task"] == 7
        finally:
            live_proc.kill()
            live_proc.wait()


# ── 8. a malformed entry is skipped, not a crash ────────────────────────
#
# "A syncer that exits 1 stops protecting everything after it." An entry
# that is not a dict, or has no task, or has neither pid nor brief, must
# be skipped and reported — never crash the whole sync.

class TestMalformedEntrySkipped:
    """Junk entries are skipped + reported; the sync continues for the rest.

    Production line whose reversion reds this test: the pre-filter
    ``_evaluable`` gate in ``main`` — without it, ``live_lanes`` receives
    the junk entry and ``d.get("pid")`` raises ``AttributeError`` (non-dict)
    or ``d["task"]`` raises ``KeyError`` (missing task), crashing the sync.
    """

    def test_non_dict_entry_does_not_crash(self, tmp_path):
        dreamers = ["not a dict", {"task": 7, "brief": "/no/such/brief.md"}]
        status = {"dreamers": dreamers, "current_task_ids": [],
                  "queue": {}, "task": "t"}
        ledger = _ledger(7)
        rc, out, err = _run(status, ledger, tmp_path)
        assert rc == 0, err
        result = json.loads(
            (tmp_path / ".dreamwork" / "status.json").read_text())
        # Junk is gone; the good entry was reaped (brief not in any argv).
        assert "not a dict" not in str(result["dreamers"])
        assert "skipped" in err.lower() or "malformed" in err.lower(), err

    def test_missing_task_does_not_crash(self, tmp_path):
        dreamers = [{"pid": 999999, "brief": "/x.md"},
                    {"task": 7, "brief": "/no/such/brief.md"}]
        status = {"dreamers": dreamers, "current_task_ids": [],
                  "queue": {}, "task": "t"}
        ledger = _ledger(7)
        rc, out, err = _run(status, ledger, tmp_path)
        assert rc == 0, err
        assert "skipped" in err.lower() or "malformed" in err.lower(), err

    def test_neither_pid_nor_brief_does_not_crash(self, tmp_path):
        # An entry with no pid and no brief: nothing to ask the OS about.
        # Old behaviour raised LivenessUnknown (abort the whole sync). Now
        # it is skipped + reported and the sync continues.
        dreamers = [{"task": 42}, {"task": 7, "brief": "/no/such/brief.md"}]
        status = {"dreamers": dreamers, "current_task_ids": [],
                  "queue": {}, "task": "t"}
        ledger = _ledger(7)
        rc, out, err = _run(status, ledger, tmp_path)
        assert rc == 0, err
        assert "skipped" in err.lower() or "malformed" in err.lower(), err


# ── 9. normalise-on-write: a quoted plain id becomes an int ─────────────
#
# "Tolerate on read, normalise on write" — the file is written by more than
# one hand, so the syncer writes back the canonical form. A plain id is an
# int; a sub-id is a string. A quoted plain id ("172") is always wrong and
# the syncer fixes it on write.

class TestNormaliseOnWrite:
    """A quoted plain id in a dreamer entry is normalised to int on write.

    Production line whose reversion reds this test: ``_normalise_task`` in
    ``main``'s write path — reverting it (writing entries verbatim) leaves
    ``"172"`` as a string, failing the type assertion.
    """

    def test_quoted_plain_id_becomes_int_in_dreamers(self, tmp_path):
        live_proc = _spawn_lane(f"/tmp/brief-402a-norm-{time.time_ns()}.md")
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(live_proc.pid)
            # "172" is a quoted plain id — wrong, but tolerated on read.
            dreamers = [{"task": "172", "pid": live_proc.pid,
                         "brief": f"/tmp/brief-402a-norm-{time.time_ns()}.md"}]
            status = {"dreamers": dreamers, "current_task_ids": [],
                      "queue": {}, "task": "t"}
            ledger = _ledger(172)
            assert 172 in status_sync.open_ids(ledger), \
                "precondition: 172 must be open"
            rc, out, err = _run(status, ledger, tmp_path)
            assert rc == 0, err
            result = json.loads(
                (tmp_path / ".dreamwork" / "status.json").read_text())
            # The survivor's task is now an int, not a quoted string.
            assert len(result["dreamers"]) == 1, result["dreamers"]
            task = result["dreamers"][0]["task"]
            assert task == 172, task
            assert isinstance(task, int) and not isinstance(task, bool), \
                "plain id must be int, not %s" % type(task).__name__
            # current_task_ids also carries the int form.
            assert 172 in result["current_task_ids"], \
                result["current_task_ids"]
            assert "172" not in result["current_task_ids"], \
                "quoted plain id must not survive into current_task_ids"
        finally:
            live_proc.kill()
            live_proc.wait()

    def test_sub_id_stays_string(self, tmp_path):
        live_proc = _spawn_lane(f"/tmp/brief-402a-sub-{time.time_ns()}.md")
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(live_proc.pid)
            dreamers = [{"task": "392a", "pid": live_proc.pid,
                         "brief": f"/tmp/brief-402a-sub-{time.time_ns()}.md"}]
            status = {"dreamers": dreamers, "current_task_ids": [],
                      "queue": {}, "task": "t"}
            ledger = _ledger(392)          # base id 392 is open
            rc, out, err = _run(status, ledger, tmp_path)
            assert rc == 0, err
            result = json.loads(
                (tmp_path / ".dreamwork" / "status.json").read_text())
            assert len(result["dreamers"]) == 1, result["dreamers"]
            assert result["dreamers"][0]["task"] == "392a", \
                result["dreamers"]
            assert isinstance(result["dreamers"][0]["task"], str)
        finally:
            live_proc.kill()
            live_proc.wait()


# ── 11. a dispatch form the probe cannot see is carried, not pruned (#537) ─
#
# Under the harness's native `spawn_subagent`, a lane is an independent clone:
# no `ccc` process exists, so `pgrep -af ccc` cannot see it and `kill -0` has
# no dispatch pid to ask about. The liveness probe is BLIND to that form. A
# live fleet of spawn_subagent lanes was once pruned to 0 by `status_sync`
# because the probe could not see it — an observation blind to a form clobbered
# records of that form. An entry declaring an unobservable `dispatch`
# (`spawn_subagent`, not the `ccc` default) must survive the liveness prune
# verbatim, and be reaped only by the ledger (a landed task is observable
# regardless of form). Two arms, each red-proved (#274 sibling-arm lesson):
# the survive arm and the reap arm. A green red-run is a finding.

class TestUnobservableDispatchSurvives:
    """A dispatch form the probe cannot see is carried verbatim, not pruned.

    Production line whose reversion reds the survive arm: the
    observable/unobservable split in ``main`` plus the ``if not _observable(d)
    return True`` short-circuit in ``_evaluable``. Revert both (ignore
    ``dispatch``, probe every entry) and the spawn_subagent entry's brief is
    absent from the ``ccc`` argv listing, so it reads as dead and is pruned —
    the incident this fixes.
    """

    def test_spawn_subagent_lane_survives_with_no_live_ccc(self, tmp_path):
        # The probe is blind to this lane: its brief is not in any live `ccc`
        # argv, and it carries no pid. Precondition, asserted at runtime —
        # never a literal — so the test cannot pass vacuously.
        brief = f"/no/such/spawn-subagent-brief-537-{time.time_ns()}.md"
        assert brief not in status_sync._argv_listing(), \
            "precondition: the probe must be blind to this brief"
        dreamers = [{"task": 537, "brief": brief,
                     "dispatch": "spawn_subagent"}]
        ledger = _ledger(537)
        assert 537 in status_sync.open_ids(ledger), \
            "precondition: task 537 must be open (else it is reaped, not carried)"
        status = {"dreamers": dreamers, "current_task_ids": [],
                  "queue": {}, "task": "on #537"}
        rc, out, err = _run(status, ledger, tmp_path)
        assert rc == 0, err
        result = json.loads(
            (tmp_path / ".dreamwork" / "status.json").read_text())
        # THE FIX: the live fleet survives — the entry is carried verbatim.
        assert len(result["dreamers"]) == 1, result["dreamers"]
        surv = result["dreamers"][0]
        assert surv["task"] == 537, surv
        assert surv["dispatch"] == "spawn_subagent"   # shape preserved
        assert surv["brief"] == brief                  # nothing else changed
        # An unobservable lane is in flight per the dispatch record, so it is
        # counted as live — the probe cannot deny a form it cannot see.
        assert 537 in result["current_task_ids"], result["current_task_ids"]

    def test_dead_ccc_lane_still_prunes_alongside_an_unobservable(self,
                                                                  tmp_path):
        # The other direction (constraint 5): a genuinely-dead `ccc` lane must
        # STILL prune — the fix must not turn unobservable-carried into
        # never-prune. A dead-pid ccc entry + a live-by-record spawn_subagent.
        brief_uo = f"/no/such/spawn-subagent-537-{time.time_ns()}.md"
        assert brief_uo not in status_sync._argv_listing(), \
            "precondition: probe blind to the unobservable brief"
        dead_pid = _dead_pid()
        assert not status_sync._pid_alive(dead_pid), \
            "precondition: dead pid must be dead"
        dreamers = [
            {"task": 8, "pid": dead_pid, "brief": "/dead/cc-lane.md"},
            {"task": 537, "brief": brief_uo, "dispatch": "spawn_subagent"},
        ]
        ledger = _ledger(537, 8)
        assert 8 in status_sync.open_ids(ledger) \
            and 537 in status_sync.open_ids(ledger), \
            "precondition: both tasks must be open"
        status = {"dreamers": dreamers, "current_task_ids": [],
                  "queue": {}, "task": "t"}
        rc, out, err = _run(status, ledger, tmp_path)
        assert rc == 0, err
        result = json.loads(
            (tmp_path / ".dreamwork" / "status.json").read_text())
        tasks = {d["task"] for d in result["dreamers"]}
        assert 8 not in tasks, "dead ccc lane must prune"       # other direction
        assert 537 in tasks, "unobservable lane must survive"   # the fix
        assert len(result["dreamers"]) == 1, result["dreamers"]

    def test_unobservable_lane_with_landed_task_is_still_reaped(self, tmp_path):
        # The reap arm (#274 sibling): an unobservable entry that survives the
        # liveness prune must STILL be reaped when its task lands — landing is
        # observable via the ledger regardless of dispatch form. Asserting the
        # `reaped` report binds the REAP path specifically (not the liveness
        # prune): under the unfixed code the entry is pruned by liveness and
        # no `reaped` line appears, so this reds on fix-absent via the report.
        brief = f"/no/such/spawn-subagent-landed-537-{time.time_ns()}.md"
        assert brief not in status_sync._argv_listing(), \
            "precondition: probe blind to the unobservable brief"
        dreamers = [{"task": 999, "brief": brief,
                     "dispatch": "spawn_subagent"}]
        ledger = _ledger(7, 8)            # open: 7, 8 — NOT 999 (landed)
        assert 999 not in status_sync.open_ids(ledger), \
            "precondition: task 999 must be landed (not open)"
        status = {"dreamers": dreamers, "current_task_ids": [999],
                  "queue": {}, "task": "t"}
        rc, out, err = _run(status, ledger, tmp_path)
        assert rc == 0, err
        result = json.loads(
            (tmp_path / ".dreamwork" / "status.json").read_text())
        # Reaped — gone from dreamers and from current_task_ids.
        assert result["dreamers"] == [], result["dreamers"]
        assert 999 not in result["current_task_ids"], \
            result["current_task_ids"]
        # The reap path fired (not the liveness prune): the entry survived the
        # blind probe and was THEN reaped by the ledger.
        assert "reaped" in err.lower() or "not under" in err.lower(), err


# ── 12. #702: a format error must not read as a dead lane ──────────────
#
# The observed defect: the coordinator wrote "task": "#696" (the `#`-prefixed
# form used everywhere else in this file), and `_base_id` matches leading
# DIGITS (`^\d+`), so it returned None and the lane was reaped with the SAME
# message as a genuinely dead lane — "reaped N dreamer(s) whose task is not
# under `## Open`". A format error was indistinguishable from a correct reap,
# which is the #136 shape ("nothing needs you" and "the channel is broken"
# must not render identically). The fix: a task the comparison cannot reach
# is KEPT and the format error is reported loudly; only a derivable base id
# that is NOT open counts as genuinely landed.

class TestMalformedTaskNotReapedAsDead:
    """A `#`-prefixed task id is kept and flagged, not reaped as dead.

    Production line whose reversion reds each arm: the malformed branch in
    ``main``'s reap loop — ``if base is None: malformed.append(d);
    pruned.append(d)``. Revert it (reap when ``base is None``, as the old
    ``if _base_id(...) in ids`` did) and the entry vanishes from dreamers
    while the "KEPT ... cannot reach" message never prints.
    """

    def test_hash_prefixed_task_is_kept_and_flagged_not_reaped(self, tmp_path):
        live_proc = _spawn_lane(f"/tmp/brief-702-hash-{time.time_ns()}.md")
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(live_proc.pid), \
                "precondition: live pid must be alive"
            # "#696" — the form used everywhere else in this file. _base_id
            # matches leading digits, so this yields None.
            assert status_sync._base_id("#696") is None, \
                "precondition: _base_id must not reach a #-prefixed id"
            dreamers = [{"task": "#696", "pid": live_proc.pid,
                         "brief": f"/tmp/brief-702-hash-{time.time_ns()}.md"}]
            ledger = _ledger(696)           # 696 IS open — the lane is real
            assert 696 in status_sync.open_ids(ledger), \
                "precondition: task 696 must be open"
            status = {"dreamers": dreamers, "current_task_ids": [],
                      "queue": {}, "task": "t"}
            rc, out, err = _run(status, ledger, tmp_path)
            assert rc == 0, err
            result = json.loads(
                (tmp_path / ".dreamwork" / "status.json"). read_text())
            # THE FIX: the malformed entry is KEPT, not reaped. A format error
            # reading as "dead lane" was the observed defect.
            assert len(result["dreamers"]) == 1, result["dreamers"]
            assert result["dreamers"][0]["task"] == "#696", result["dreamers"]
            # The format error is reported loudly and named distinctly from a
            # genuine reap — the discriminating message the brief demands.
            assert "KEPT" in err, err
            assert "cannot reach" in err, err
            assert "#696" in err, err
            # The reap REPORT ("reaped N dreamer(s) whose task is not under")
            # must NOT appear — that was the old message which made a format
            # error read as a dead lane. Bound to the report's two-word prefix
            # rather than the bare word "reaped", which the KEPT message itself
            # uses in its reasoning ("not reaped because …").
            reap_report = "reaped " in err and "whose task is not under" in err
            assert not reap_report, \
                "the dead-lane reap report must not fire for a malformed task" \
                " (it read a format error as a dead lane): %s" % err
        finally:
            live_proc.kill()
            live_proc.wait()

    def test_genuinely_landed_task_is_still_reaped_with_the_dead_message(
            self, tmp_path):
        # The other direction (constraint, not vacuous): a task whose base id
        # IS derivable and is NOT open must STILL be reaped with the "reaped"
        # message — the malformed carve-out must not turn "keep malformed" into
        # "keep everything". A genuinely landed lane is 999, not open.
        live_proc = _spawn_lane(f"/tmp/brief-702-landed-{time.time_ns()}.md")
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(live_proc.pid)
            assert status_sync._base_id(999) == 999, \
                "precondition: a plain int yields its base"
            dreamers = [{"task": 999, "pid": live_proc.pid,
                         "brief": f"/tmp/brief-702-landed-{time.time_ns()}.md"}]
            ledger = _ledger(696)           # 696 open — 999 is NOT (landed)
            assert 999 not in status_sync.open_ids(ledger), \
                "precondition: task 999 must be landed"
            status = {"dreamers": dreamers, "current_task_ids": [999],
                      "queue": {}, "task": "t"}
            rc, out, err = _run(status, ledger, tmp_path)
            assert rc == 0, err
            result = json.loads(
                (tmp_path / ".dreamwork" / "status.json").read_text())
            # Reaped — gone. The dead-lane message still fires for a real reap.
            assert result["dreamers"] == [], result["dreamers"]
            assert "reaped" in err.lower(), \
                "a genuinely landed task must still be reported as reaped: %s" % err
            assert "KEPT" not in err, \
                "the malformed message must not fire for a genuine reap: %s" % err
        finally:
            live_proc.kill()
            live_proc.wait()


# ── 10. status.json is ephemera: read it defensively (#402) ────────────
#
# The brief's third deliverable, verbatim: "status.json is gitignored and
# ephemeral. Read it defensively: absent, truncated, or listing a lane that
# died is the NORMAL case, and a check that hard-fails on it is worse than
# none." Absent and "listing a lane that died" are handled above; this class
# closes the remaining half — a status.json that is PRESENT but not a
# readable object (truncated mid-write, empty, or a non-object JSON value).
#
# A syncer that crashes on it (uncaught JSONDecodeError / AttributeError)
# stops protecting everything after it. A syncer that overwrites it with
# freshly-derived fields destroys the author-written fields (deployed, task,
# monitors, owed_verifications, …) it could not read — the file has more than
# one writer. So the contract is neither crash nor recover: report loudly,
# leave the bytes untouched, and let the coordinator rebuild from the durable
# sources (the ledger, submissions.log).

class TestReadsStatusJsonDefensively:
    """A present-but-unreadable status.json is refused cleanly, never crashed
    on, never overwritten.

    Production line whose reversion reds each test: the defensive read in
    ``_read_status`` (called from ``main``). Reverting ``main`` to a bare
    ``status = json.loads(spath.read_text())`` lets ``JSONDecodeError``
    propagate as a traceback on the truncated/empty cases, and lets
    ``status.get(...)`` raise ``AttributeError`` on the non-object case — so
    the ``rc = status_sync.main(...)`` call below raises instead of returning
    2, and the test errors rather than passing.
    """

    def _run_raw(self, tmp_path: Path, raw_status: str, ledger: str):
        """Write a RAW status.json (not json.dumps'd) and invoke the real main.

        The shared ``_run`` helper round-trips status through ``json.dumps``,
        which repairs exactly the broken bytes these tests need to feed in.
        """
        dw = tmp_path / ".dreamwork"
        dw.mkdir(exist_ok=True)
        (dw / "status.json").write_text(raw_status)
        (dw / "tasks.md").write_text(ledger)
        before = (dw / "status.json").read_bytes()
        out_s, err_s = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out_s), contextlib.redirect_stderr(err_s):
            rc = status_sync.main(["--target", str(tmp_path)])
        return rc, out_s.getvalue(), err_s.getvalue(), before, dw / "status.json"

    def test_truncated_status_json_is_left_untouched(self, tmp_path):
        # A file cut off mid-write: a valid prefix, no closing brace. The
        # realistic shape of "the process died writing it".
        truncated = '{"task": "on #7", "deployed": {"pid": 123}, "dreamers": ['
        # Precondition, asserted at runtime: the bytes are genuinely
        # unparseable, not a valid file that merely looks truncated.
        with pytest.raises(json.JSONDecodeError):
            json.loads(truncated)

        rc, out, err, before, spath = self._run_raw(tmp_path, truncated,
                                                    _ledger(7))

        assert rc == 2, err                       # refused to write (input unusable)
        assert spath.read_bytes() == before       # byte-identical — not overwritten
        assert "unparseable" in err.lower(), err
        assert "untouched" in err.lower(), err

    def test_empty_status_json_is_left_untouched(self, tmp_path):
        # A zero-byte / whitespace-only file — the other shape a crashed
        # writer leaves behind. ``json.loads("")`` raises JSONDecodeError.
        rc, out, err, before, spath = self._run_raw(tmp_path, "   \n  ",
                                                    _ledger(7))
        with pytest.raises(json.JSONDecodeError):
            json.loads("   \n  ")                 # precondition: genuinely empty

        assert rc == 2, err
        assert spath.read_bytes() == before
        assert "empty" in err.lower(), err

    def test_non_object_status_json_is_left_untouched(self, tmp_path):
        # Parses as JSON, but the top level is an array, not an object — so
        # ``status.get`` would raise AttributeError without the defensive
        # read. A different malformation than truncation, same contract.
        rc, out, err, before, spath = self._run_raw(tmp_path, "[]", _ledger(7))
        # Precondition: it IS valid JSON, just not an object.
        assert json.loads("[]") == []

        assert rc == 2, err
        assert spath.read_bytes() == before
        assert "not an object" in err.lower(), err

    def test_refusal_does_not_silently_match_a_clean_run(self, tmp_path):
        # Anti-vacuity: the refused (rc 2) path must be distinguishable from
        # a clean sync. A readable object with one open task and no live
        # lanes returns 0, not 2 — so the defensive-read refusal is a real
        # verdict rather than a default the broken case happens to share.
        good = json.dumps({"dreamers": [], "current_task_ids": [],
                           "queue": {"in_progress": 0, "pending": 1},
                           "task": "t"})
        rc, out, err, before, spath = self._run_raw(tmp_path, good, _ledger(1))
        assert rc == 0, err                        # clean — distinct from the rc==2 refusals
        assert "coverage:" in out


# ---------------------------------------------------------------------------
# Store mode (#294 T2): post-cutover status_sync must STRIP the retired
# fields (queue, current_task_ids) rather than derive them — the tool that
# used to write them is exactly the process that would regrow them, and
# lint's absence-invariant ERRORs on a regrown field.
#
# Production line: the ``status.pop(k, None)`` strip loop in main's
# store_mode branch. Break it (``for k in ():``) and the retired fields
# survive the sync — the regrowth the invariant exists to catch.
# ---------------------------------------------------------------------------
def _cut_over_target(tmp_path: Path) -> Path:
    """A REAL post-cutover scratch target (watermark + store + shim)."""
    import importlib.machinery, importlib.util
    repo = Path(__file__).resolve().parent
    loader = importlib.machinery.SourceFileLoader(
        "ud_dw_tasks_migrate", str(repo / "ud-dw-tasks-migrate"))
    spec = importlib.util.spec_from_loader("ud_dw_tasks_migrate", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    dw = tmp_path / ".dreamwork"
    dw.mkdir(exist_ok=True)
    (dw / "tasks.md").write_text(
        "# Task ledger\n\nNext id: **12**\n\n## Open\n\n"
        "- **#10** — a clean open entry · P1 · task · origin: **human**\n\n"
        "## Recently landed\n\n"
        "- **#11** — a landed entry · P0 · origin: **human** (abc1234)\n")
    mod.perform_cutover(str(dw), out=io.StringIO())
    import ledger_parse
    assert ledger_parse.source_of_truth(dw) == "store", \
        "fixture precondition: the watermark must be present"
    return tmp_path


def test_store_mode_strips_the_retired_fields(tmp_path):
    target = _cut_over_target(tmp_path)
    dw = target / ".dreamwork"
    (dw / "status.json").write_text(json.dumps(
        {"task": "294", "queue": {"in_progress": 1, "pending": 9},
         "current_task_ids": [10], "dreamers": []}, indent=2) + "\n")
    out_s, err_s = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out_s), contextlib.redirect_stderr(err_s):
        rc = status_sync.main(["--target", str(target)])
    assert rc == 0, err_s.getvalue()
    written = json.loads((dw / "status.json").read_text())
    assert "queue" not in written, \
        "queue regrown post-cutover — the second derived truth (#294 T2)"
    assert "current_task_ids" not in written, \
        "current_task_ids regrown post-cutover (#294 T2)"
    assert "dreamers" in written, \
        "the strip must not take the still-owned dreamers field with it"


# ── #541: atomic status.json write (tmp + os.replace) ───────────────────
#
# status_sync.py writes status.json with a plain `spath.write_text` (the
# single writer in the system). A crash mid-write tears the file, and every
# reader downstream must then treat a truncated status.json as the normal
# case (#402). The fix is the watch.py question-sigs idiom: serialise to a
# temp file in the SAME directory, then `os.replace` (a same-filesystem
# atomic rename). These two tests bind that — criterion (a) the write lands
# on the real path via os.replace; criterion (b) a failure raised mid-write
# leaves the pre-existing file byte-identical.
#
# Production line that must change for BOTH to fail: `spath.write_text(...)`
# at status_sync.py:525.


def test_status_write_lands_via_os_replace(tmp_path, monkeypatch):
    """#541 criterion (a): the write reaches the real status.json through
    `os.replace`, with the tmp source in the same directory (same-dir rename
    is atomic on POSIX/NTFS; cross-dir is not)."""
    status = {"task": "541", "deployed": "author-held"}
    target = _write_target(tmp_path, status, _ledger(541))
    spath = target / ".dreamwork" / "status.json"

    replaced = []
    real_replace = os.replace

    def spy(src, dst):
        replaced.append((str(src), str(dst)))
        return real_replace(src, dst)

    monkeypatch.setattr(status_sync.os, "replace", spy)

    rc, _out, err = _run(status, _ledger(541), tmp_path)
    assert rc == 0, err

    assert replaced, (
        "status.json write must go through os.replace, not a direct "
        "write_text (#541)")
    dests = [dst for _src, dst in replaced]
    assert str(spath) in dests, (
        "os.replace must target the real status.json path (%s); got %r"
        % (spath, dests))
    # the tmp source must share status.json's directory, else the rename
    # is cross-filesystem and not atomic.
    for src, dst in replaced:
        if str(dst) == str(spath):
            assert os.path.dirname(src) == os.path.dirname(str(spath)), (
                "tmp file must live in the same directory as status.json "
                "so os.replace is a same-filesystem atomic rename; got %s"
                % src)


def test_status_write_failure_leaves_existing_file_intact(tmp_path, monkeypatch):
    """#541 criterion (b): a crash mid-write must leave the pre-existing
    status.json byte-identical. With tmp+os.replace the only file a failed
    write can tear is the throwaway tmp; with a direct write_text the real
    file is truncated the instant it is opened for writing.

    Two interception points are patched because the two code shapes write
    through different calls: the OLD code calls `Path.write_text` (which
    binds io.open at import, so patching builtins.open does NOT reach it),
    and the NEW code calls the builtin `open` on a tmp path (which resolves
    `builtins.open` at call time, so patching builtins.open DOES reach it).
    Both are torn so the test stays honest under either shape.
    """
    import builtins

    original = {"task": "541", "deployed": "author-held", "marker": "ORIGINAL"}
    target = _write_target(tmp_path, original, _ledger(541))
    spath = target / ".dreamwork" / "status.json"
    original_bytes = spath.read_bytes()
    # Precondition the byte-identical comparison depends on: a real
    # pre-existing file was there to protect (comparing against nothing is
    # meaningless). Derived at runtime, not a literal tuned to this fixture.
    assert original_bytes, "fixture precondition: pre-existing status.json"

    real_open = builtins.open

    def tearing_open(path, mode="r", *a, **kw):
        f = real_open(path, mode, *a, **kw)
        # Crash mid-WRITE of any status.json-shaped path: under the old code
        # that is the real file (torn); under the new code it is *.tmp (the
        # throwaway, and replace is never reached).
        if "w" in mode and "status.json" in str(path):
            f.write("{torn-by-crash")
            f.flush()
            raise OSError("simulated crash mid-write")
        return f

    real_write_text = Path.write_text

    def tearing_write_text(self, data, *a, **kw):
        # OLD code path: writes straight onto the real status.json.
        if "status.json" in str(self):
            with real_open(self, "w", encoding="utf-8") as f:
                f.write("{torn-by-crash")
            raise OSError("simulated crash mid-write")
        return real_write_text(self, data, *a, **kw)

    monkeypatch.setattr(builtins, "open", tearing_open)
    monkeypatch.setattr(Path, "write_text", tearing_write_text)

    with pytest.raises(OSError):
        status_sync.main(["--target", str(target)])

    after = spath.read_bytes()
    assert after == original_bytes, (
        "status.json was torn by a failed write — a crash mid-write must "
        "leave the pre-existing file byte-identical (#541); got %r"
        % after[:40])


# ── 13. #716: discovery ADDS lanes the prune-only field missed ──────────
#
# The defect: `dreamers` is printed under `coverage: derived` but the
# derivation only ever SUBTRACTED (dead pid, landed task). Nothing added a
# lane, so a freshly-dispatched fleet read as zero while it ran. Discovery
# is the missing ADD: a `ccc` lane's cwd is its worktree, so a real process
# whose cwd is under `.worktrees/<lane>` and whose argv[0] is `ccc` is a
# live lane the field must carry.
#
# These tests spawn REAL processes in real `.worktrees/` dirs under the
# target (no fakes): the discovery function reads the real `/proc/*/cwd` and
# `/proc/*/cmdline`. The discriminating Direction-1 assertion names WHICH
# lane is missing, not a count — `len(dreamers) > 0` passes against the bug.

class TestDiscoveryAddsMissingLanes:
    """#716: a live ccc lane whose cwd is under .worktrees/ is discovered.

    Production line whose reversion reds each arm: the `discover_lanes` call
    and merge block in ``main`` (or ``discover_lanes`` returning ``[]``).
    Revert the merge (skip appending ``added`` to ``pruned``) and a
    dispatched-and-running lane stays absent from ``dreamers`` while the tool
    reports "already in sync" — the bug in production tonight.
    """

    def _make_worktree(self, target: Path, lane: str) -> Path:
        wt = target / ".worktrees" / lane
        wt.mkdir(parents=True, exist_ok=True)
        (wt / "BRIEF.md").write_text("lane brief")
        return wt

    def _spawn_cwd_ccc(self, cwd: Path, hold: float = 30.0):
        """A live process whose cwd is `cwd` and whose argv[0] is `ccc`.

        Discovery keys on cwd (under .worktrees/) AND argv[0] basename
        (== `ccc`). `executable` sets argv independently of the binary, so
        argv[0] is `ccc` while perl sleeps. `cwd=` sets the child's real
        cwd — the thing `readlink /proc/<pid>/cwd` returns.
        """
        return subprocess.Popen(
            ["ccc", "-e", f"sleep {hold}", "--", "--yolo", "@glm52", "brief"],
            executable=_which_perl(), cwd=str(cwd),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)

    def test_discovers_a_running_lane_the_field_did_not_carry(
            self, tmp_path, monkeypatch):
        # Confine discovery to the test target: point os.listdir('/proc') at
        # a fake proc whose only entries are the spawned lane + a noise pid.
        # discover_lanes reads /proc directly, so a monkeypatch of
        # os.listdir is the one seam that reaches it — and it is exercised
        # alongside the real /proc/<pid>/cwd and /proc/<pid>/cmdline reads,
        # which no fake can satisfy. (See TestRealProcessDetector for the
        # same real-reads principle against pgrep.)
        wt = self._make_worktree(tmp_path, "lane-707sweep")
        proc = self._spawn_cwd_ccc(wt)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(proc.pid), \
                "precondition: spawned ccc lane must be alive"
            real_cwd = status_sync._read_proc_cwd(proc.pid)
            assert real_cwd == str(wt), \
                "precondition: spawned lane cwd must be the worktree: %r" % real_cwd
            assert status_sync._is_ccc_proc(proc.pid), \
                "precondition: spawned argv[0] must read as ccc"
            monkeypatch.setattr(
                status_sync.os, "listdir",
                lambda d: [str(proc.pid)] if d == "/proc" else [])
            found = status_sync.discover_lanes(tmp_path)
            assert ("lane-707sweep", proc.pid) in found, found
            # Task id is derived from the lane name (707 IS open here).
            assert status_sync._lane_task("lane-707sweep", [707]) == 707

            status = {"dreamers": [], "current_task_ids": [], "queue": {},
                      "task": "t"}
            rc, out, err = _run(status, _ledger(707), tmp_path)
            assert rc == 0, err
            result = json.loads(
                (tmp_path / ".dreamwork" / "status.json").read_text())
            tasks = {d["task"] for d in result["dreamers"]}
            # THE DISCRIMINATING ASSERTION (Direction 1): the lane is present
            # by its task id. A count-only check passes against the bug; this
            # names exactly which lane was missing.
            assert 707 in tasks, \
                "discovery must add the running lane by its task id; got %s" \
                % result["dreamers"]
            assert any(d.get("lane") == "lane-707sweep"
                       for d in result["dreamers"]), result["dreamers"]
            assert "discovered" in err, \
                "the discovery report must fire on stderr: %s" % err
        finally:
            proc.kill()
            proc.wait()

    def test_does_not_clobber_coordinator_authored_entry(self, tmp_path,
                                                         monkeypatch):
        # A lane the field ALREADY carries (coordinator-authored) must not be
        # duplicated or overwritten by discovery. The merge keys on lane name;
        # an existing entry is kept verbatim.
        wt = self._make_worktree(tmp_path, "lane-707sweep")
        proc = self._spawn_cwd_ccc(wt)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(proc.pid)
            authored = {"task": 707, "lane": "lane-707sweep",
                        "pid": proc.pid,
                        "brief": str(wt / "BRIEF.md"),
                        "dispatch": "ccc", "model": "ccc @glm52",
                        "note": "coordinator-authored, must survive"}
            monkeypatch.setattr(
                status_sync.os, "listdir",
                lambda d: [str(proc.pid)] if d == "/proc" else [])
            status = {"dreamers": [authored], "current_task_ids": [707],
                      "queue": {"in_progress": 1, "pending": 0}, "task": "t"}
            rc, out, err = _run(status, _ledger(707), tmp_path)
            assert rc == 0, err
            result = json.loads(
                (tmp_path / ".dreamwork" / "status.json").read_text())
            assert len(result["dreamers"]) == 1, result["dreamers"]
            # Verbatim survival: coordinator fields are not lost to discovery.
            assert result["dreamers"][0].get("note") == \
                "coordinator-authored, must survive", result["dreamers"]
            assert "discovered" not in err, \
                "an already-carried lane must not be reported as discovered"
        finally:
            proc.kill()
            proc.wait()

    def test_check_exits_one_when_a_lane_is_discovered(self, tmp_path,
                                                       monkeypatch):
        # --check must exit 1 (stale) without writing when discovery finds a
        # lane the field lacks — the safe-on-a-bad-tick contract (#716
        # verification gate). A write here would be the bug.
        wt = self._make_worktree(tmp_path, "lane-707sweep")
        proc = self._spawn_cwd_ccc(wt)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(proc.pid)
            monkeypatch.setattr(
                status_sync.os, "listdir",
                lambda d: [str(proc.pid)] if d == "/proc" else [])
            status = {"dreamers": [], "current_task_ids": [], "queue": {},
                      "task": "t"}
            target = _write_target(tmp_path, status, _ledger(707))
            before = (tmp_path / ".dreamwork" / "status.json").read_bytes()
            out_s, err_s = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out_s), \
                    contextlib.redirect_stderr(err_s):
                rc = status_sync.main(
                    ["--target", str(target), "--check"])
            assert rc == 1, "discovery must register as stale under --check"
            assert (tmp_path / ".dreamwork" / "status.json").read_bytes() \
                == before, "--check must not write"
            assert "discovered" in err_s.getvalue(), err_s.getvalue()
        finally:
            proc.kill()
            proc.wait()
