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
import shutil
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
        live_brief = f"/tmp/brief-402a-live-{time.time_ns()}.md"
        live_proc = _spawn_lane(live_brief)
        dead_pid = _dead_pid()
        try:
            time.sleep(0.6)
            # Preconditions, asserted at runtime, derived — never literals.
            assert status_sync._pid_alive(live_proc.pid), "live pid must be alive"
            assert not status_sync._pid_alive(dead_pid), "dead pid must be dead"
            dreamers = [
                {"task": 7, "pid": live_proc.pid, "brief": live_brief},
                {"task": 9, "pid": dead_pid, "brief": "dead"},
            ]
            n_alive = sum(1 for d in dreamers
                          if not status_sync._missing_pid(d)
                          and status_sync._pid_alive(d["pid"]))
            n_dead = len(dreamers) - n_alive
            assert n_alive >= 1 and n_dead >= 1   # else the test is vacuous

            live, pruned = status_sync.live_lanes(dreamers)
            live_tasks = {d["task"] for d in pruned}
            assert 9 not in live_tasks, \
                "dead lane was still reported live: task 9 in %s" % live_tasks
            assert 7 in live_tasks, \
                "live lane disappeared while pruning task 9: %s" % live_tasks
            assert len(pruned) == n_alive          # dead lane gone
            # Survivors are kept verbatim — nothing else about them changes.
            assert pruned == [d for d in dreamers if d["task"] == 7]
        finally:
            live_proc.kill()
            live_proc.wait()

    def test_reused_pid_does_not_impersonate_a_lane(self):
        """A live pid is necessary but not sufficient: it must still carry
        the recorded lane identity through cwd or its exact argv.

        Direction 1 seam: ``status_sync.live_lanes`` calling
        ``_pid_matches_lane``. Revert that call to ``_pid_alive`` and this
        fails on the discriminating message below, not merely a count.
        """
        real_brief = f"/tmp/brief-821-real-{time.time_ns()}.md"
        proc = _spawn_lane(real_brief)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(proc.pid), \
                "precondition: candidate pid must be alive"
            reused = {"task": 821, "pid": proc.pid,
                      "brief": "/tmp/different-lane/BRIEF.md"}
            live, pruned = status_sync.live_lanes([reused])
            assert 821 not in live and reused not in pruned, \
                "dead lane was still reported live because its pid was reused"
        finally:
            proc.kill()
            proc.wait()


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


# ── 6a. queued_dispatches ids are advisory ledger claims (#755) ───────

class TestQueuedDispatchIds:
    """Only structural ids are checked; findings never become sync staleness."""

    @staticmethod
    def _status(*entries) -> dict:
        return {"queue": {"in_progress": 0, "pending": 1},
                "current_task_ids": [], "dreamers": [],
                "queued_dispatches": list(entries)}

    def test_landed_id_warns_names_id_quotes_line_and_check_stays_clean(
            self, tmp_path):
        entry = {"ids": [2], "note": "implementation still queued"}
        status = self._status(entry)
        ledger = (_ledger(1)
                  + "## Recently landed\n- **#2** landed subject\n")
        target = _write_target(tmp_path, status, ledger)
        spath = target / ".dreamwork" / "status.json"
        before = spath.read_bytes()

        rc, out, err = _run(status, ledger, tmp_path, "--check")

        assert rc == 0, (out, err)  # warning is a question, not stale sync
        assert spath.read_bytes() == before
        assert "WARN queued_dispatches: #2 is landed" in err
        assert json.dumps(entry) in err
        assert "checked 1 entr" in out and "1 id reference" in out

    def test_only_open_ids_are_quiet_but_denominator_is_reported(
            self, tmp_path):
        rc, out, err = _run(self._status(
                                {"ids": [1], "note": "implementation queued"}),
                            _ledger(1), tmp_path)
        assert rc == 0, err
        assert "WARN queued_dispatches" not in err
        assert "checked 1 entr" in out and "1 id reference" in out
        assert "0 state question" in out and "0 unclassifiable" in out

    def test_legacy_text_entry_is_reported_unmigrated_not_scanned(
            self, tmp_path):
        line = "#999 legacy queued prose"
        rc, out, err = _run(self._status(line), _ledger(1), tmp_path)
        assert rc == 0, err
        assert "WARN queued_dispatches: legacy text entry; unmigrated" in err
        assert json.dumps(line) in err
        assert "checked 1 entr" in out and "0 id references" in out
        assert "1 unclassifiable" in out
        assert "#999 is not present" not in err

    def test_missing_ids_is_reported_unclassifiable_not_counted_clean(
            self, tmp_path):
        entry = {"note": "the SSE transport"}
        rc, out, err = _run(self._status(entry), _ledger(1), tmp_path)
        assert rc == 0, err
        assert "WARN queued_dispatches: no ids key; unclassifiable" in err
        assert json.dumps(entry) in err
        assert "0 id references" in out and "1 unclassifiable" in out

    @pytest.mark.parametrize("ids", [None, [], [1, "2"], [True], [0], [-1]])
    def test_invalid_ids_shape_is_reported_unclassifiable(self, tmp_path, ids):
        entry = {"ids": ids, "note": "queued"}
        rc, out, err = _run(self._status(entry), _ledger(1), tmp_path)
        assert rc == 0, err
        assert "ids must be a non-empty list of positive integers" in err
        assert "0 id references" in out and "1 unclassifiable" in out

    def test_every_structural_id_is_checked(self, tmp_path):
        entry = {"ids": [641, 630],
                 "note": "subject (held behind another task)"}
        ledger = (_ledger(630)
                  + "## Recently landed\n- **#641** landed subject\n")
        rc, out, err = _run(self._status(entry), ledger, tmp_path)
        assert rc == 0, err
        assert "#641 is landed" in err
        assert "#630 is landed" not in err
        assert "2 id references" in out

    def test_absent_id_is_a_retired_or_nonexistent_question(self, tmp_path):
        entry = {"ids": [999], "note": "follow-up queued"}
        rc, out, err = _run(self._status(entry), _ledger(1), tmp_path)
        assert rc == 0, err
        assert "#999 is not present in the ledger" in err
        assert "retired or non-existent" in err
        assert json.dumps(entry) in err

    def test_open_id_with_already_done_prose_is_an_honest_false_green(
            self, tmp_path):
        # Direction 2: ledger state cannot judge prose truth. The denominator
        # proves the id was examined while the deliberately stale prose passes.
        entry = {"ids": [1],
                 "note": "implementation already landed but still queued"}
        rc, out, err = _run(self._status(entry), _ledger(1), tmp_path)
        assert rc == 0, err
        assert "WARN queued_dispatches" not in err
        assert "1 id reference" in out and "0 state question" in out

    def test_note_citation_is_not_cross_checked_against_structural_ids(
            self, tmp_path):
        # Direction 2: even an open #NNN omitted from ids may be a citation.
        # Scanning it would rebuild the false-attribution defect one level up.
        entry = {"ids": [1], "note": "queued; compare open lesson #2"}
        rc, out, err = _run(self._status(entry), _ledger(1, 2), tmp_path)
        assert rc == 0, err
        assert "WARN queued_dispatches" not in err
        assert "1 id reference" in out and "0 state question" in out

    def test_current_live_queue_is_quiet_after_structural_migration(
            self, tmp_path):
        # Captured byte-for-byte from the live field on 2026-08-01. The old
        # audit attributed the lesson citation #666 to queued work and warned.
        legacy = [
            "#645 increments 2-14 - queued behind cx-645i1.",
            "#631 (P4) - the session view. NOT parallel with component-registry work.",
            "#736 and #628 phase 2 - HELD on load (browser guards return a WRONG answer under load, #666).",
            "#758 (P3) - justfile pytest *ARGS, so one supported command also runs the concurrency advisory.",
        ]
        assert "#666" in legacy[2]  # discriminating precondition
        migrated = [
            {"ids": [645], "note": legacy[0]},
            {"ids": [631], "note": legacy[1]},
            {"ids": [736, 628], "note": legacy[2]},
            {"ids": [758], "note": legacy[3]},
        ]
        rc, out, err = _run(self._status(*migrated),
                            _ledger(645, 631, 736, 628, 758), tmp_path)
        assert rc == 0, err
        assert "#666" not in err
        assert "WARN queued_dispatches" not in err
        assert "checked 4 entries" in out and "5 id references" in out


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
        brief = f"/tmp/brief-402a-landed-{time.time_ns()}.md"
        live_proc = _spawn_lane(brief)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(live_proc.pid), \
                "precondition: live pid must be alive"
            # The entry's task (999) is deliberately NOT in the open ledger.
            dreamers = [{"task": 999, "pid": live_proc.pid,
                         "brief": brief}]
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
        brief = f"/tmp/brief-402a-keep-{time.time_ns()}.md"
        live_proc = _spawn_lane(brief)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(live_proc.pid)
            dreamers = [{"task": 7, "pid": live_proc.pid,
                         "brief": brief}]
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
        brief = f"/tmp/brief-402a-norm-{time.time_ns()}.md"
        live_proc = _spawn_lane(brief)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(live_proc.pid)
            # "172" is a quoted plain id — wrong, but tolerated on read.
            dreamers = [{"task": "172", "pid": live_proc.pid,
                         "brief": brief}]
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
        brief = f"/tmp/brief-402a-sub-{time.time_ns()}.md"
        live_proc = _spawn_lane(brief)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(live_proc.pid)
            dreamers = [{"task": "392a", "pid": live_proc.pid,
                         "brief": brief}]
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
        brief = f"/tmp/brief-702-hash-{time.time_ns()}.md"
        live_proc = _spawn_lane(brief)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(live_proc.pid), \
                "precondition: live pid must be alive"
            # "#696" — the form used everywhere else in this file. _base_id
            # matches leading digits, so this yields None.
            assert status_sync._base_id("#696") is None, \
                "precondition: _base_id must not reach a #-prefixed id"
            dreamers = [{"task": "#696", "pid": live_proc.pid,
                         "brief": brief}]
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
        brief = f"/tmp/brief-702-landed-{time.time_ns()}.md"
        live_proc = _spawn_lane(brief)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(live_proc.pid)
            assert status_sync._base_id(999) == 999, \
                "precondition: a plain int yields its base"
            dreamers = [{"task": 999, "pid": live_proc.pid,
                         "brief": brief}]
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

    def test_dead_process_reaps_even_when_task_cannot_be_compared(self,
                                                                  tmp_path):
        """Process death and ledger landing are independent predicates.

        A malformed task id is kept only when its process is still the lane;
        the ``cannot compare`` refusal must not preserve a dead process entry.
        """
        dead_pid = _dead_pid()
        assert not status_sync._pid_alive(dead_pid), \
            "precondition: lane process must be dead"
        entry = {"task": "#696", "pid": dead_pid,
                 "brief": "/tmp/dead-821/BRIEF.md"}
        status = {"dreamers": [entry], "current_task_ids": ["#696"],
                  "queue": {}, "task": "t"}
        rc, out, err = _run(status, _ledger(696), tmp_path)
        assert rc == 0, err
        result = json.loads(
            (tmp_path / ".dreamwork" / "status.json").read_text())
        assert result["dreamers"] == [], \
            "dead lane was preserved by the cannot-compare ledger refusal"
        assert "KEPT" not in err, \
            "dead lane incorrectly reached the landed-task comparison: %s" % err


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


def test_queued_dispatch_landed_warning_reads_cut_over_store(tmp_path):
    target = _cut_over_target(tmp_path)
    dw = target / ".dreamwork"
    entry = {"ids": [11], "note": "follow-up still queued"}
    (dw / "status.json").write_text(json.dumps(
        {"dreamers": [], "queued_dispatches": [entry]}, indent=2) + "\n")
    out_s, err_s = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out_s), contextlib.redirect_stderr(err_s):
        rc = status_sync.main(["--target", str(target), "--check"])
    assert rc == 0, (out_s.getvalue(), err_s.getvalue())
    assert "WARN queued_dispatches: #11 is landed" in err_s.getvalue()
    assert json.dumps(entry) in err_s.getvalue()
    assert "1 id reference" in out_s.getvalue()


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
            found, _ph, _at = status_sync.discover_lanes(tmp_path)
            found_pairs = [(f[0], f[1]) for f in found]
            assert ("lane-707sweep", proc.pid) in found_pairs, found
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


# ── 14. #719: a removed worktree's lingering ccc process is a phantom ────
#
# Residue of #716, found at its gate. readlink on /proc/<pid>/cwd for a
# removed directory returns the path with " (deleted)" APPENDED. The prefix
# filter (cwd.startswith(wt_root + "/")) still passes, _lane_task's
# r"lane-(\d+)" still matches, and _is_ccc_proc still confirms the dispatch
# — so without a guard the phantom takes a fleet slot under a corpse's name.
# The fix: os.path.isdir(cwd) is False for the deleted-suffixed path, so the
# phantom is excluded from `found` and REPORTED via `phantoms` (never silently
# dropped — #702's rule, inherited by #716's discovery).
#
# These tests build the REAL state (a live process whose cwd is a worktree,
# then the worktree is removed) and read the REAL /proc — no fakes. The
# Direction-1 assertion names WHICH lane is excluded, not a count.

class TestPhantomWorktreeExcludedAndReported:
    """#719: a ccc process whose worktree is gone is excluded and reported.

    Production line whose reversion reds the survive arm: the
    ``if not os.path.isdir(cwd): phantoms.append(...)`` guard in
    ``discover_lanes``. Revert it (append to ``found`` regardless) and the
    phantom enters ``dreamers`` under a name carrying ``" (deleted)"`` while
    no ``phantoms`` report fires — the bug in production tonight.
    """

    def _make_worktree(self, target: Path, lane: str) -> Path:
        wt = target / ".worktrees" / lane
        wt.mkdir(parents=True, exist_ok=True)
        (wt / "BRIEF.md").write_text("lane brief")
        return wt

    def _spawn_cwd_ccc(self, cwd: Path, hold: float = 30.0):
        return subprocess.Popen(
            ["ccc", "-e", f"sleep {hold}", "--", "--yolo", "@glm52", "brief"],
            executable=_which_perl(), cwd=str(cwd),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)

    def test_phantom_excluded_from_found_reported_in_phantoms(self, tmp_path,
                                                              monkeypatch):
        # Build the state: a live ccc process whose cwd is a worktree, then
        # remove the worktree out from under it. The process keeps running
        # (it is sleeping, indifferent to its cwd); readlink now carries
        # " (deleted)" and isdir is False.
        wt = self._make_worktree(tmp_path, "lane-719test")
        proc = self._spawn_cwd_ccc(wt)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(proc.pid), \
                "precondition: spawned ccc lane must be alive"
            real_cwd = status_sync._read_proc_cwd(proc.pid)
            assert real_cwd == str(wt), \
                "precondition: cwd must be the worktree before removal: %r" \
                % real_cwd
            # Remove the worktree — the phantom-making event.
            shutil.rmtree(wt)
            cwd_now = status_sync._read_proc_cwd(proc.pid)
            # Precondition (the state is built, not assumed): readlink carries
            # the deleted suffix and isdir is False. A test that did not build
            # this state could pass vacuously.
            assert " (deleted)" in cwd_now, \
                "precondition: readlink must mark the removed cwd: %r" % cwd_now
            assert not os.path.isdir(cwd_now), \
                "precondition: the deleted-suffixed cwd must not be a dir"
            monkeypatch.setattr(
                status_sync.os, "listdir",
                lambda d: [str(proc.pid)] if d == "/proc" else [])

            found, phantoms, _at = status_sync.discover_lanes(tmp_path)
            # THE GUARD: the phantom is NOT in found (would take a fleet slot
            # under "lane-719test (deleted)" without the guard).
            assert found == [], \
                "phantom must be excluded from found; got %s" % found
            # THE REPORT: the phantom IS in phantoms, named by its lane.
            assert len(phantoms) == 1, phantoms
            ph_lane, ph_pid = phantoms[0]
            assert ph_pid == proc.pid, phantoms
            assert "719" in ph_lane and " (deleted)" in ph_lane, \
                "phantom report must name the deleted lane; got %r" % ph_lane
        finally:
            proc.kill()
            proc.wait()

    def test_phantom_not_in_dreamers_report_names_it(self, tmp_path,
                                                     monkeypatch):
        # End-to-end through main: the phantom is neither added to dreamers
        # nor counted as live, and the stderr report names the excluded lane.
        wt = self._make_worktree(tmp_path, "lane-719test")
        proc = self._spawn_cwd_ccc(wt)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(proc.pid)
            shutil.rmtree(wt)
            cwd_now = status_sync._read_proc_cwd(proc.pid)
            assert not os.path.isdir(cwd_now), \
                "precondition: removed worktree cwd must not be a dir"
            monkeypatch.setattr(
                status_sync.os, "listdir",
                lambda d: [str(proc.pid)] if d == "/proc" else [])

            status = {"dreamers": [], "current_task_ids": [], "queue": {},
                      "task": "t"}
            rc, out, err = _run(status, _ledger(719), tmp_path)
            assert rc == 0, err
            result = json.loads(
                (tmp_path / ".dreamwork" / "status.json").read_text())
            # DISCRIMINATING (Direction 1): the phantom is absent by its task
            # id. A count-only check passes against the bug; this names the
            # lane that must not be there.
            assert result["dreamers"] == [], \
                "phantom must not enter dreamers; got %s" % result["dreamers"]
            assert 719 not in result["current_task_ids"], \
                "phantom must not count as live: %s" \
                % result["current_task_ids"]
            # The report fires and names the excluded lane (not a silent drop).
            # #729: the ccc proxy IS a known runner (argv[0] basename == ccc), so
            # the split phantom report lands it in the "genuine leftover lane
            # runner" bucket — NOT the old generic "ccc process mid-exit" label
            # that never read argv (#671). The assertion binds the RUNNER arm.
            assert "leftover lane runner" in err, \
                "the phantom report must fire and classify a ccc phantom as a " \
                "known runner (not the old generic label): %s" % err
            assert "719" in err, \
                "the report must name the excluded lane's id: %s" % err
            assert " (deleted)" in err, \
                "the report must carry the deleted marker: %s" % err
        finally:
            proc.kill()
            proc.wait()

    def test_recreated_worktree_is_still_caught_not_a_false_green(
            self, tmp_path, monkeypatch):
        # Direction 2 candidate the brief named: a worktree removed and
        # RECREATED under the same name while the old process lingers. The
        # brief predicted isdir would read True and the pid (belonging to the
        # dead lane) would pass — a false green. MEASURED on this kernel it
        # does NOT: readlink keeps the " (deleted)" suffix because the process
        # holds the OLD orphaned inode; the kernel does not re-resolve the
        # cwd to the newly-created directory. So isdir(readlink) stays False
        # and the guard still catches it. This test PROVES that (it would red
        # if a future kernel re-resolved, or if the guard checked isdir on the
        # plain worktree path rather than the readlink result) — constructive
        # evidence the predicted false green does not materialise here.
        wt = self._make_worktree(tmp_path, "lane-719recreate")
        proc = self._spawn_cwd_ccc(wt)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(proc.pid)
            shutil.rmtree(wt)
            wt.mkdir(parents=True, exist_ok=True)  # recreate at the same path
            cwd_now = status_sync._read_proc_cwd(proc.pid)
            # The load-bearing measurement: readlink keeps the deleted suffix
            # even after recreation, so isdir(readlink) is False.
            assert " (deleted)" in cwd_now, \
                "precondition: readlink must keep the deleted suffix after " \
                "recreate on this kernel: %r" % cwd_now
            assert not os.path.isdir(cwd_now), \
                "precondition: the deleted-suffixed readlink is not a dir " \
                "even after recreate"
            assert os.path.isdir(str(wt)), \
                "precondition: the plain worktree path IS a dir again"
            monkeypatch.setattr(
                status_sync.os, "listdir",
                lambda d: [str(proc.pid)] if d == "/proc" else [])
            found, phantoms, _at = status_sync.discover_lanes(tmp_path)
            # Still caught: the recreate did not produce a false green.
            assert found == [], \
                "recreate must not let the phantom through; got %s" % found
            assert len(phantoms) == 1, phantoms
        finally:
            proc.kill()
            proc.wait()


# ── 17. #729: the phantom list splits self / runner / other ─────────────
#
# The defect: status_sync printed the coordinator's own process (claude, cwd
# deleted when the worktree merged) alongside head/grep/tail shell fragments,
# ALL labelled "ccc process mid-exit" — a specificity the code never had
# (it matched any cwd under .worktrees/, never read argv; #671). Three facts
# rendered as one (#136).
#
# The fix has two halves, and BOTH directions are tested:
#  (a) ancestry self-exclusion: a process in status_sync's own ppid chain is
#      labelled "coordinator's own ancestry", not "phantom lane". Exact, via
#      /proc/<pid>/stat field 4.
#  (b) positive identity: a process whose argv[0] basename is a known runner
#      (ccc/claude/grok/codex) is a genuine leftover; a head/grep/tail is NOT.
#      Copies reaper.parse_cmdline's shape (#440).
#
# Direction 1 (discriminating): SELF and a genuine leftover are DISTINGUISHABLE.
# Asserting the list merely got shorter passes against a fix that drops
# everything — the brief states this explicitly. The assertion must name which
# case each pid lands in.

class TestPhantomBucketSplit:
    """#729: the phantom list splits self / runner / other, all reported.

    The ancestry test (#729 fix half a) is tested by a PURE function: inject a
    known ancestor set into ``_ancestor_pids`` (monkeypatched) and assert a
    phantom pid in that set is labelled "coordinator's own ancestry", while a
    pid NOT in the set and NOT a runner is labelled "neither self nor a known
    runner". Production line whose reversion reds this: the three-way branch in
    ``main``'s phantom report (``if pid in ancestors / elif _is_lane_runner /
    else``) plus the ``_ancestor_pids`` helper. Revert the split (one bucket)
    and the self/runner/other labels never appear.
    """

    def _make_worktree(self, target: Path, lane: str) -> Path:
        wt = target / ".worktrees" / lane
        wt.mkdir(parents=True, exist_ok=True)
        (wt / "BRIEF.md").write_text("lane brief")
        return wt

    def test_coordinator_ancestor_is_labelled_self_not_phantom(
            self, tmp_path, monkeypatch):
        # THE DEFECT: pid 1328406 (the coordinator, a claude process whose
        # worktree merged) appeared in the phantom list labelled "ccc process
        # mid-exit". THE FIX: ancestry identifies it as self.
        # Build a phantom whose pid we force into the ancestor set, so the
        # ancestry test fires without needing a real coordinator pid.
        wt = self._make_worktree(tmp_path, "lane-coordinator")
        # A perl proxy so the process stays alive with a deleted cwd. We will
        # OVERRIDE _is_lane_runner to False so the ONLY discriminator active is
        # ancestry — isolating the self arm.
        proc = subprocess.Popen(
            ["claude", "-e", "sleep 30", "--", "fake"],
            executable=_which_perl(), cwd=str(wt),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(proc.pid)
            shutil.rmtree(wt)
            assert not status_sync._read_proc_cwd(proc.pid) is None
            monkeypatch.setattr(
                status_sync.os, "listdir",
                lambda d: [str(proc.pid)] if d == "/proc" else [])
            # Inject proc.pid into the ancestor set — the ancestry test is the
            # ONLY thing that should classify it as self.
            monkeypatch.setattr(status_sync, "_ancestor_pids",
                                lambda: {os.getpid(), proc.pid})
            # _is_lane_runner would return True (argv[0]=='claude'); force False
            # to isolate the ancestry arm from the runner arm.
            monkeypatch.setattr(status_sync, "_is_lane_runner",
                                lambda pid: False)
            status = {"dreamers": [], "current_task_ids": [], "queue": {},
                      "task": "t"}
            rc, out, err = _run(status, _ledger(729), tmp_path)
            assert rc == 0, err
            # DISCRIMINATING (Direction 1): the coordinator's pid is labelled
            # SELF, not "phantom" or "leftover". A fix that drops everything
            # passes a count-only check; this names the case.
            assert "coordinator's own ancestry" in err, \
                "an ancestor of status_sync must be labelled self, not a " \
                "phantom lane: %s" % err
            assert str(proc.pid) in err, err
            # The phantom must NOT enter dreamers (same as before — the split
            # is about the LABEL, not the exclusion).
            result = json.loads(
                (tmp_path / ".dreamwork" / "status.json").read_text())
            assert result["dreamers"] == [], result["dreamers"]
        finally:
            proc.kill()
            proc.wait()

    def test_shell_fragment_is_labelled_other_not_ccc_midexit(
            self, tmp_path, monkeypatch):
        # THE DEFECT (#671): a `head -3` / `grep` / `tail -F` with a deleted
        # worktree cwd was labelled "ccc process mid-exit" — a check the code
        # never performed. THE FIX: it is neither self nor a known runner.
        wt = self._make_worktree(tmp_path, "lane-fragment")
        # A perl proxy with argv[0]='head' — a shell-fragment shape, NOT a
        # lane runner. _is_lane_runner returns False for it.
        proc = subprocess.Popen(
            ["head", "-e", "sleep 30"],
            executable=_which_perl(), cwd=str(wt),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(proc.pid)
            shutil.rmtree(wt)
            # Precondition: argv[0] is 'head', so _is_lane_runner is False —
            # this is the #671 shape (a non-runner matching the cwd prefix).
            assert not status_sync._is_lane_runner(proc.pid), \
                "precondition: 'head' must NOT read as a lane runner"
            monkeypatch.setattr(
                status_sync.os, "listdir",
                lambda d: [str(proc.pid)] if d == "/proc" else [])
            # Ensure proc.pid is NOT in ancestor set (it isn't — it's a fresh
            # child of the test, not an ancestor of status_sync).
            real_ancestors = status_sync._ancestor_pids()
            assert proc.pid not in real_ancestors, \
                "precondition: the head proxy must not be an ancestor"
            status = {"dreamers": [], "current_task_ids": [], "queue": {},
                      "task": "t"}
            rc, out, err = _run(status, _ledger(729), tmp_path)
            assert rc == 0, err
            # DISCRIMINATING: the old label "ccc process mid-exit" must NOT
            # appear (#671: the label claimed a check not performed). The new
            # label names what it actually is.
            assert "ccc process mid-exit" not in err, \
                "the old false-specific label must not appear for a head " \
                "process (#671): %s" % err
            assert "neither self nor a known runner" in err, \
                "a shell fragment must be labelled as other, not as a ccc " \
                "process: %s" % err
        finally:
            proc.kill()
            proc.wait()

    def test_ccc_runner_is_labelled_leftover_not_other(
            self, tmp_path, monkeypatch):
        # The other direction of the split: a genuine ccc runner with a deleted
        # cwd lands in the RUNNER bucket, not the other/self buckets. This is
        # the #719 case (a real leftover) — the split must not misfile it.
        wt = self._make_worktree(tmp_path, "lane-leftover")
        proc = subprocess.Popen(
            ["ccc", "-e", "sleep 30", "--", "--yolo", "@glm52", "brief"],
            executable=_which_perl(), cwd=str(wt),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(proc.pid)
            assert status_sync._is_lane_runner(proc.pid), \
                "precondition: ccc proxy must read as a lane runner"
            assert proc.pid not in status_sync._ancestor_pids(), \
                "precondition: ccc proxy must not be an ancestor"
            shutil.rmtree(wt)
            monkeypatch.setattr(
                status_sync.os, "listdir",
                lambda d: [str(proc.pid)] if d == "/proc" else [])
            status = {"dreamers": [], "current_task_ids": [], "queue": {},
                      "task": "t"}
            rc, out, err = _run(status, _ledger(729), tmp_path)
            assert rc == 0, err
            # DISCRIMINATING: a ccc runner is a "genuine leftover lane runner",
            # NOT "other" or "self". Three facts, three renderings (#136).
            assert "leftover lane runner" in err, \
                "a ccc runner with deleted cwd must be labelled a genuine " \
                "leftover: %s" % err
            assert "coordinator's own ancestry" not in err, \
                "a ccc proxy is not self: %s" % err
            assert "neither self nor a known runner" not in err, \
                "a ccc proxy IS a known runner, not 'other': %s" % err
        finally:
            proc.kill()
            proc.wait()

    def test_all_three_cases_reported_none_dropped(self, tmp_path, monkeypatch):
        # #702 governs: an entry the tool cannot classify must be REPORTED,
        # never silently dropped. With all three cases present, all three
        # labels fire — the split does not hide the confusing ones.
        wt_self = self._make_worktree(tmp_path, "lane-self")
        wt_runner = self._make_worktree(tmp_path, "lane-runner")
        wt_other = self._make_worktree(tmp_path, "lane-other")
        self_proc = subprocess.Popen(
            ["claude", "-e", "sleep 30", "--", "fake"],
            executable=_which_perl(), cwd=str(wt_self)
            if False else wt_self,  # keep cwd explicit
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        runner_proc = subprocess.Popen(
            ["ccc", "-e", "sleep 30", "--", "--yolo", "@glm52", "brief"],
            executable=_which_perl(), cwd=str(wt_runner),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        other_proc = subprocess.Popen(
            ["head", "-e", "sleep 30"],
            executable=_which_perl(), cwd=str(wt_other),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        try:
            time.sleep(0.6)
            assert all(status_sync._pid_alive(p.pid)
                       for p in (self_proc, runner_proc, other_proc))
            for wt in (wt_self, wt_runner, wt_other):
                shutil.rmtree(wt)
            monkeypatch.setattr(
                status_sync.os, "listdir",
                lambda d: [str(self_proc.pid), str(runner_proc.pid),
                           str(other_proc.pid)] if d == "/proc" else [])
            # Force self_proc.pid into the ancestor set — isolates the self arm.
            monkeypatch.setattr(status_sync, "_ancestor_pids",
                                lambda: {os.getpid(), self_proc.pid})
            status = {"dreamers": [], "current_task_ids": [], "queue": {},
                      "task": "t"}
            rc, out, err = _run(status, _ledger(729), tmp_path)
            assert rc == 0, err
            # ALL THREE labels fire — #702: none dropped.
            assert "coordinator's own ancestry" in err, \
                "self case must be reported: %s" % err
            assert "leftover lane runner" in err, \
                "runner case must be reported: %s" % err
            assert "neither self nor a known runner" in err, \
                "other case must be reported: %s" % err
            # And none enter dreamers.
            result = json.loads(
                (tmp_path / ".dreamwork" / "status.json").read_text())
            assert result["dreamers"] == [], result["dreamers"]
        finally:
            for p in (self_proc, runner_proc, other_proc):
                p.kill()
                p.wait()


# ── 15. #720: discovery must REPOPULATE from empty under the default target ─
#
# #716's discovery was INERT under the invocation the loop actually uses:
# --target="." (the default) built wt_root="./.worktrees", tested with
# startswith against the ABSOLUTE path readlink returns — it never matched.
# The bug MERGED because the only check ran from a populated dreamers field,
# so it passed against the inert implementation. The discriminating test for
# "does X populate Y" is to EMPTY Y first. A test against a pre-populated
# fixture is not discriminating and would have shipped this bug again.
#
# Production line whose reversion reds each arm: the `target.resolve()` in
# `discover_lanes` (was `str(target)`). Revert it and a relative target
# produces wt_root="./.worktrees" which never prefix-matches the absolute
# path readlink returns — so discovery finds nothing and dreamers stays [].

class TestDiscoveryRepopulatesFromEmpty:
    """#720: the discriminating test. Starts from dreamers: [] under the
    production invocation (``--target .``) and asserts the field REPOPULATES.

    This is the assertion that distinguishes the bug from its fix, and its
    ABSENCE is why the bug merged: every prior discovery test started from a
    populated or empty field with an ABSOLUTE target, so it could not
    distinguish the resolve() fix from the inert version.
    """

    def _make_worktree(self, target: Path, lane: str) -> Path:
        wt = target / ".worktrees" / lane
        wt.mkdir(parents=True, exist_ok=True)
        (wt / "BRIEF.md").write_text("lane brief")
        return wt

    def _spawn_cwd_ccc(self, cwd: Path, hold: float = 30.0):
        return subprocess.Popen(
            ["ccc", "-e", f"sleep {hold}", "--", "--yolo", "@glm52", "brief"],
            executable=_which_perl(), cwd=str(cwd),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)

    def test_repopulates_from_empty_under_default_relative_target(
            self, tmp_path, monkeypatch):
        # THE PRECONDITION: dreamers starts EMPTY. A test against a populated
        # fixture passes against the inert implementation — the exact failure
        # that shipped this bug. This test starts from [] and asserts the
        # field repopulates, so the inert version returns [] and reds.
        wt = self._make_worktree(tmp_path, "lane-720target")
        proc = self._spawn_cwd_ccc(wt)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(proc.pid), \
                "precondition: spawned ccc lane must be alive"
            monkeypatch.setattr(
                status_sync.os, "listdir",
                lambda d: [str(proc.pid)] if d == "/proc" else [])
            # Write status.json + tasks.md under tmp_path/.dreamwork, then
            # chdir there and invoke main with the DEFAULT --target "." —
            # exactly the production shape (just status-sync, no --target).
            dw = tmp_path / ".dreamwork"
            dw.mkdir(exist_ok=True)
            (dw / "status.json").write_text(json.dumps(
                {"dreamers": [], "current_task_ids": [], "queue": {},
                 "task": "t"}))
            (dw / "tasks.md").write_text(_ledger(720))
            monkeypatch.chdir(tmp_path)
            out_s, err_s = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out_s), \
                    contextlib.redirect_stderr(err_s):
                rc = status_sync.main(["--target", "."])
            assert rc == 0, err_s.getvalue()
            result = json.loads((dw / "status.json").read_text())
            # DISCRIMINATING: the field REPOPULATED from []. Without the
            # resolve() fix, wt_root="./.worktrees" never matched the
            # absolute lane cwd, discovery returned [], and dreamers stayed
            # []. This assertion names the lane that was discovered, quoting
            # the message — a count-only check passes against the bug.
            assert len(result["dreamers"]) == 1, \
                "dreamers must repopulate from [] under the default " \
                "relative target; got %s" % result["dreamers"]
            assert result["dreamers"][0]["lane"] == "lane-720target", \
                result["dreamers"]
            assert 720 in result["current_task_ids"], \
                result["current_task_ids"]
            assert "discovered" in err_s.getvalue(), \
                "the discovery report must fire: %s" % err_s.getvalue()
        finally:
            proc.kill()
            proc.wait()

    def test_check_exits_one_when_repopulatable_from_empty(
            self, tmp_path, monkeypatch):
        # --check must exit 1 (stale) without writing when a lane is
        # discoverable but dreamers is empty — the safe-on-a-bad-tick
        # contract. Without the resolve() fix, discovery finds nothing and
        # --check exits 0 ("already in sync") over a field that SHOULD carry
        # a live lane — the bug reading that shipped #716.
        wt = self._make_worktree(tmp_path, "lane-720target")
        proc = self._spawn_cwd_ccc(wt)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(proc.pid)
            monkeypatch.setattr(
                status_sync.os, "listdir",
                lambda d: [str(proc.pid)] if d == "/proc" else [])
            dw = tmp_path / ".dreamwork"
            dw.mkdir(exist_ok=True)
            (dw / "status.json").write_text(json.dumps(
                {"dreamers": [], "current_task_ids": [], "queue": {},
                 "task": "t"}))
            (dw / "tasks.md").write_text(_ledger(720))
            before = (dw / "status.json").read_bytes()
            monkeypatch.chdir(tmp_path)
            out_s, err_s = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out_s), \
                    contextlib.redirect_stderr(err_s):
                rc = status_sync.main(["--target", ".", "--check"])
            assert rc == 1, \
                "a discoverable lane over an empty field is stale: %d" % rc
            assert (dw / "status.json").read_bytes() == before, \
                "--check must not write"
            assert "discovered" in err_s.getvalue(), err_s.getvalue()
        finally:
            proc.kill()
            proc.wait()

    def test_resolve_not_abspath_through_symlink(self, tmp_path, monkeypatch):
        # Direction 2: the brief named the case where a target is reached via
        # a DIFFERENT symlink/path than the one the lanes' cwd reports. This
        # repo IS reached through ~/.claude-p/skills/ud-dreamwork (a symlink
        # to ~/.llm-general/skills/ud-dreamwork), while lane cwds carry the
        # real path. abspath keeps the symlink; resolve() normalises to the
        # real path the cwds share. Without resolve(), a loop invoked through
        # the symlink would build wt_root under the symlink path and discovery
        # would find nothing — the same bug wearing a different hat.
        #
        # Build the state: a symlink to tmp_path, a lane whose cwd is the
        # REAL path (tmp_path/.worktrees/...), and discover through the link.
        wt = self._make_worktree(tmp_path, "lane-720target")
        proc = self._spawn_cwd_ccc(wt)
        link = tmp_path.parent / ("link-720-%d" % os.getpid())
        try:
            link.symlink_to(tmp_path)
            time.sleep(0.6)
            assert status_sync._pid_alive(proc.pid)
            # Precondition: the lane's cwd is the REAL path, not the link.
            real_cwd = status_sync._read_proc_cwd(proc.pid)
            assert real_cwd == str(wt), \
                "precondition: cwd is the real path: %r" % real_cwd
            assert str(link / ".worktrees" / "lane-720target") != real_cwd, \
                "precondition: the link path must differ from the real cwd"
            monkeypatch.setattr(
                status_sync.os, "listdir",
                lambda d: [str(proc.pid)] if d == "/proc" else [])
            # Discover through the symlink: resolve() normalises link → real.
            found, _ph, _at = status_sync.discover_lanes(link)
            assert any(f[0] == "lane-720target" for f in found), \
                ("resolve() must normalise the symlink to the real path so "
                 "wt_root matches the lane cwd; got %s" % found)
        finally:
            proc.kill()
            proc.wait()
            if link.is_symlink():
                link.unlink()


# ── 16. #720: discovered lanes carry a derived model (#716's second gap) ──
#
# A discovered lane has no recorded model while a hand-written one does —
# the same kind of lane rendering as two kinds on the dashboard. The model
# IS recoverable from argv[1:3]: "cc" for the Opus form (ccc cc -y +high)
# versus "@<alias>" for the cheap form (ccc -y @glm52). The trap: /proc
# cmdline is NUL-separated, so a substring test never matches and every lane
# silently reads as the default model. argv ELEMENTS must be compared.

class TestDiscoveryDerivesModel:
    """#720: a discovered lane's model is derived from its /proc argv.

    The NUL-split parsing is tested directly against known cmdline bytes
    (a perl proxy cannot place the alias in argv[1:3]: perl needs ``-e``
    first, so argv[1] is always ``-e``). The production line whose reversion
    reds each parsing test: ``raw.split(b"\\x00")`` and the ``args[1:3]``
    logic in ``_ccc_model`` — reverting to a substring test
    (``b" cc " in raw``) never matches NUL-separated args, so every lane
    silently reads as the default model, the exact trap #716 recorded.
    """

    def _make_worktree(self, target: Path, lane: str) -> Path:
        wt = target / ".worktrees" / lane
        wt.mkdir(parents=True, exist_ok=True)
        (wt / "BRIEF.md").write_text("lane brief")
        return wt

    def _spawn_cwd_ccc(self, cwd: Path, hold: float = 30.0):
        return subprocess.Popen(
            ["ccc", "-e", f"sleep {hold}", "--", "--yolo", "@glm52", "brief"],
            executable=_which_perl(), cwd=str(cwd),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)

    def _mock_cmdline(self, monkeypatch, pid: int, raw: bytes):
        """Patch builtins.open so /proc/<pid>/cmdline yields `raw` bytes."""
        import builtins
        real_open = builtins.open

        class _FakeFile(io.BytesIO):
            def __enter__(self):
                return self
            def __exit__(self, *a):
                self.close()

        def fake_open(path, *a, **kw):
            if str(path) == "/proc/%d/cmdline" % pid:
                return _FakeFile(raw)
            return real_open(path, *a, **kw)
        monkeypatch.setattr(builtins, "open", fake_open)

    def test_glm52_alias_derived_from_nul_separated_argv(self, monkeypatch):
        # The cheap form: ccc -y @glm52. NUL-split argv = ['ccc', '-y',
        # '@glm52', ...]. argv[1:3] = ['-y', '@glm52'].
        raw = b"ccc\x00-y\x00@glm52\x00You are a dreamwork lane\x00"
        self._mock_cmdline(monkeypatch, 7777, raw)
        model = status_sync._ccc_model(7777)
        assert model == "ccc @glm52", \
            "model must be derived from argv[1:3] NUL-split: %r" % model

    def test_opus_form_derived_from_nul_separated_argv(self, monkeypatch):
        # The Opus form: ccc cc -y +high. argv[1:3] = ['cc', '-y'].
        raw = b"ccc\x00cc\x00-y\x00+high\x00You are a dreamwork lane\x00"
        self._mock_cmdline(monkeypatch, 8888, raw)
        model = status_sync._ccc_model(8888)
        assert model == "ccc cc +high (opus)", \
            "opus form must read as 'ccc cc +high (opus)': %r" % model

    def test_substring_of_raw_cmdline_never_matches(self, monkeypatch):
        # THE TRAP: /proc cmdline is NUL-separated, so b" cc " never appears
        # as a substring even when 'cc' IS an argv element. A substring test
        # would return None here (wrong), proving the parser must split on
        # NUL and compare elements. This is the exact failure #716 recorded.
        raw = b"ccc\x00cc\x00-y\x00+high\x00brief\x00"
        assert b" cc " not in raw, \
            "precondition: NUL-separation means the substring is absent"
        self._mock_cmdline(monkeypatch, 9999, raw)
        model = status_sync._ccc_model(9999)
        assert model == "ccc cc +high (opus)", \
            "element comparison must succeed where substring fails: %r" \
            % model

    def test_unknown_alias_yields_none_not_a_default(self, monkeypatch):
        # argv[1:3] matches no known alias: None (not a silent default).
        raw = b"ccc\x00-y\x00--unknownflag\x00brief\x00"
        self._mock_cmdline(monkeypatch, 6666, raw)
        model = status_sync._ccc_model(6666)
        assert model is None, \
            "unknown alias must yield None, not a silent default: %r" % model

    def test_model_flows_into_discovered_entry(self, tmp_path, monkeypatch):
        # Integration: a discovered lane carries its derived model into the
        # dreamer entry. The real perl proxy cannot place the alias in
        # argv[1:3] (perl needs -e first), so _ccc_model is patched to a
        # known value — the production line this binds is the
        # ``if model is not None: entry["model"] = model`` gate in main's
        # merge loop. Revert it (never set model) and the entry has no model.
        wt = self._make_worktree(tmp_path, "lane-720model")
        proc = self._spawn_cwd_ccc(wt)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(proc.pid)
            monkeypatch.setattr(
                status_sync.os, "listdir",
                lambda d: [str(proc.pid)] if d == "/proc" else [])
            monkeypatch.setattr(status_sync, "_ccc_model",
                                lambda pid: "ccc @glm52")
            status = {"dreamers": [], "current_task_ids": [], "queue": {},
                      "task": "t"}
            rc, out, err = _run(status, _ledger(720), tmp_path)
            assert rc == 0, err
            result = json.loads(
                (tmp_path / ".dreamwork" / "status.json").read_text())
            assert len(result["dreamers"]) == 1, result["dreamers"]
            assert result["dreamers"][0].get("model") == "ccc @glm52", \
                result["dreamers"]
        finally:
            proc.kill()
            proc.wait()


# ── 16. #675: a non-ccc process with a lane cwd is discovered ────────────
#
# An Agent-tool subagent has no `ccc` in argv, so `_is_ccc_proc` filters it
# out — it is invisible to the ccc-only probe. But `discover_lanes` already
# walks /proc/*/cwd, and a non-ccc process with a lane cwd IS an Agent-tool
# lane's shape. The fix: collect those as a third list `agent_tool`, merge
# into dreamers so `current_task_ids` does not degrade to 0 while Agent-tool
# lanes run (the drift alarm Max asked the loop to watch for). The over-count
# risk (an editor or shell in the worktree) is accepted — zero is worse.

class TestAgentToolLaneDiscovery:
    """#675: a non-ccc process with a lane cwd is discovered and counted.

    Production line whose reversion reds the discover arm: the
    ``agent_tool`` collection in ``discover_lanes`` plus the merge loop in
    ``main``. Revert either (skip non-ccc processes, or skip the
    ``agent_added`` loop) and a non-ccc lane stays absent from
    ``dreamers`` while the tool reports "already in sync" — the #675
    drift alarm shape: the live count reads zero while a lane runs.
    """

    def _make_worktree(self, target: Path, lane: str) -> Path:
        wt = target / ".worktrees" / lane
        wt.mkdir(parents=True, exist_ok=True)
        (wt / "BRIEF.md").write_text("lane brief")
        return wt

    def _spawn_cwd_ccc(self, cwd: Path, hold: float = 30.0):
        return subprocess.Popen(
            ["ccc", "-e", f"sleep {hold}", "--", "--yolo", "@glm52", "brief"],
            executable=_which_perl(), cwd=str(cwd),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)

    def _spawn_cwd_nonccc(self, cwd: Path, hold: float = 30.0):
        """A live process whose cwd is `cwd` and whose argv[0] is NOT ccc.

        Uses perl (argv[0] is `perl`, not `ccc`) so `_is_ccc_proc` returns
        False — the exact shape of an Agent-tool lane: a process in the
        worktree the ccc probe is blind to.
        """
        return subprocess.Popen(
            ["perl", "-e", f"sleep {hold}"],
            cwd=str(cwd),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)

    def test_nonccc_lane_cwd_is_discovered_as_agent_tool(
            self, tmp_path, monkeypatch):
        wt = self._make_worktree(tmp_path, "lane-675agent")
        proc = self._spawn_cwd_nonccc(wt)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(proc.pid), \
                "precondition: spawned non-ccc lane must be alive"
            real_cwd = status_sync._read_proc_cwd(proc.pid)
            assert real_cwd == str(wt), \
                "precondition: spawned lane cwd must be the worktree"
            assert not status_sync._is_ccc_proc(proc.pid), \
                "precondition: spawned process must NOT read as ccc"
            monkeypatch.setattr(
                status_sync.os, "listdir",
                lambda d: [str(proc.pid)] if d == "/proc" else [])
            found, _ph, agent_tool = status_sync.discover_lanes(tmp_path)
            # THE DISCRIMINATING ASSERTION: the non-ccc lane appears in
            # agent_tool, not in found. A reverted discover_lanes (ccc-only)
            # would yield found=[] and agent_tool=[] — this test would pass
            # for the wrong reason. The precondition (not _is_ccc_proc) and
            # the assertion (lane IS in agent_tool) together pin the fix.
            assert ("lane-675agent", proc.pid) in agent_tool, agent_tool
            assert found == [], "non-ccc lane must not appear in ccc found"
        finally:
            proc.kill()
            proc.wait()

    def test_agent_tool_lane_merged_into_dreamers(self, tmp_path, monkeypatch):
        # The integration arm: a discovered agent-tool lane flows into
        # dreamers and current_task_ids, so the live count does NOT read
        # zero while the lane runs. This is the #675 binding check: a probe
        # that answered 0 while lanes run has the same defect as the
        # hand-maintenance it replaced.
        wt = self._make_worktree(tmp_path, "lane-675probe")
        proc = self._spawn_cwd_nonccc(wt)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(proc.pid)
            assert not status_sync._is_ccc_proc(proc.pid)
            monkeypatch.setattr(
                status_sync.os, "listdir",
                lambda d: [str(proc.pid)] if d == "/proc" else [])
            status = {"dreamers": [], "current_task_ids": [], "queue": {},
                      "task": "t"}
            rc, out, err = _run(status, _ledger(675), tmp_path)
            assert rc == 0, err
            result = json.loads(
                (tmp_path / ".dreamwork" / "status.json").read_text())
            tasks = {d["task"] for d in result["dreamers"]}
            # THE FIX: the lane is present by task id, NOT absent.
            assert 675 in tasks, \
                "agent-tool lane must be counted as live (not 0): %s" \
                % result["dreamers"]
            assert 675 in result["current_task_ids"], \
                "agent-tool lane must be in current_task_ids"
            entry = [d for d in result["dreamers"] if d["task"] == 675][0]
            assert entry["dispatch"] == "agent_tool", entry
            assert "agent-tool" in err.lower(), \
                "the agent-tool discovery report must fire: %s" % err
        finally:
            proc.kill()
            proc.wait()

    def test_agent_tool_lane_does_not_duplicate_a_ccc_lane(
            self, tmp_path, monkeypatch):
        # Direction 2 (false-green guard): a ccc lane spawns a child process
        # (grok) that shares the cwd. Both would match the cwd-walk, but the
        # lane must count ONCE, not twice. The dedup key is lane name: the
        # ccc arm claims the lane first, the child falls through to
        # agent_tool but is dropped by `seen_lanes`.
        wt = self._make_worktree(tmp_path, "lane-675dup")
        ccc_proc = self._spawn_cwd_ccc(wt)
        child_proc = self._spawn_cwd_nonccc(wt)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(ccc_proc.pid)
            assert status_sync._pid_alive(child_proc.pid)
            assert status_sync._is_ccc_proc(ccc_proc.pid)
            assert not status_sync._is_ccc_proc(child_proc.pid)
            monkeypatch.setattr(
                status_sync.os, "listdir",
                lambda d: [str(ccc_proc.pid), str(child_proc.pid)]
                if d == "/proc" else [])
            found, _ph, agent_tool = status_sync.discover_lanes(tmp_path)
            found_lanes = {f[0] for f in found}
            at_lanes = {a[0] for a in agent_tool}
            # The lane appears in ccc found (claimed first) but NOT in
            # agent_tool (deduped by lane name).
            assert "lane-675dup" in found_lanes, found
            assert "lane-675dup" not in at_lanes, \
                "a ccc lane's child must not double-count as agent_tool: %s" \
                % agent_tool
        finally:
            ccc_proc.kill()
            ccc_proc.wait()
            child_proc.kill()
            child_proc.wait()

    def test_agent_tool_lane_survives_liveness_probe_next_tick(
            self, tmp_path):
        # #537 consistency: an agent_tool entry is OBSERVABLE (it has a pid
        # kill -0 reaches), so it must survive the liveness probe on the
        # NEXT tick — not be carried verbatim like spawn_subagent. An entry
        # written by discovery, re-read with a live pid, must still be live.
        wt = self._make_worktree(tmp_path, "lane-675live")
        proc = self._spawn_cwd_nonccc(wt)
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(proc.pid)
            # Simulate a second tick: the entry from tick 1 is in dreamers.
            entry = {"task": 675, "pid": proc.pid,
                     "brief": str(wt / "BRIEF.md"),
                     "dispatch": "agent_tool", "lane": "lane-675live"}
            live, pruned = status_sync.live_lanes([entry])
            assert 675 in live, \
                "agent_tool entry with a live pid must be probed as live"
            assert entry in pruned
        finally:
            proc.kill()
            proc.wait()


# ── #728: the discover_lanes arity contract, pinned by ONE accessor ────
#
# discover_lanes returns a 3-tuple (found, phantoms, agent_tool) since #675.
# #728: guard_preflight unpacked it as 2 and a bare 'except Exception' hid
# the resulting ValueError as a silent '?'. The accessor live_lane_count is
# now the one supported way to read the count (#440); this test pins the
# arity contract so the NEXT change to discover_lanes fails a test rather
# than a gate at 2am.

def test_live_lane_count_returns_an_int(tmp_path):
    # Production line whose reversion reds this: live_lane_count's
    # `found, _phantoms, _agent_tool = discover_lanes(target)` unpack, or
    # discover_lanes changing its return arity.
    n = status_sync.live_lane_count(tmp_path)
    assert isinstance(n, int), \
        "live_lane_count must return an int; got %r" % type(n)
    assert n == 0, \
        "an empty target must report zero lanes, not None or a raise (%r)" % n


def test_discover_lanes_arity_is_three(tmp_path):
    # THE DISCRIMINATING ASSERTION for the arity contract: discover_lanes
    # returns EXACTLY three elements. If a future change adds a fourth
    # field, live_lane_count's unpack silently keeps working (Python drops
    # nothing into the gaps), so this guard catches what the accessor
    # cannot. Revert discover_lanes to its pre-#675 2-tuple and this reds.
    result = status_sync.discover_lanes(tmp_path)
    assert isinstance(result, tuple) and len(result) == 3, \
        "discover_lanes arity changed; live_lane_count and the test suite " \
        "need updating together (was %d-tuple)" % len(result)


def test_discovery_accounts_for_the_candidate_population(tmp_path, monkeypatch):
    """#671/#821: zero live lanes is valid only after a real population scan.

    Direction 2 seam: ``status_sync.discover_lanes`` incrementing
    ``process_candidates`` inside its numeric ``/proc`` loop. Replacing that
    loop with an empty iterable must name the broken instrument below.
    """
    monkeypatch.setattr(status_sync.os, "listdir",
                        lambda path: ["101", "202", "x"])
    monkeypatch.setattr(status_sync, "_read_proc_cwd", lambda pid: None)
    monkeypatch.setattr(status_sync, "_argv_lane", lambda pid, root: None)
    stats = {}
    found, phantoms, agent = status_sync.discover_lanes(tmp_path, stats=stats)
    assert found == phantoms == agent == []
    assert stats.get("process_candidates") == 2, \
        "lane detector examined no plausible process candidates: %r" % stats


# ── 18. #775: a lane whose cwd is NOT its worktree is found via argv ────
#
# THE BUG: status_sync.py's discover_lanes walked /proc/*/cwd for paths
# under .worktrees/. But dispatch_lane.py does `os.execvp(runner[0],
# [*runner, prompt])` from the MAIN checkout, so a live ccc lane's cwd is
# the main checkout, NOT its worktree — and the cwd-only walk read 0 live
# while lanes ran. The brief's "Worktree: <abs>/.worktrees/<lane>" line is
# appended as the last argv element and survives the exec chain (ccc execs
# away to codex-code-mode-host / the grok harness), so the worktree path in
# argv is the one invariant the dispatch route controls. The fix recovers
# the lane from argv when cwd is elsewhere.
#
# THE TRAP (stated so no lane walks into it): do NOT match the runner binary
# name (ccc/codex/grok) — that is the identical mistake one level down. A
# new runner is added, nothing matches, and the fleet silently reads zero
# again. The worktree PATH in argv is controlled by dispatch and is what we
# match. These tests hold that line: they name the path-invariant, not the
# binary.
#
# Direction 1: inject the cwd-only matcher and watch the test red on a
# DISCRIMINATING message that says "the lane was live in argv but the
# detector could not see it" — not a bare count.
# Direction 2: construct a process table where the detector's match token
# appears coincidentally (a container hex id containing "ccc", an unrelated
# path under .worktrees/ that is not a lane runner) and show it is not
# counted — the false-positive arm of #136 at this seam.

class TestArgvDiscoveryFindsLaneWithMainCwd:
    """#775: a live ccc lane whose cwd is the main checkout (not its
    worktree) is discovered via its argv-carried worktree path.

    Production line whose reversion reds the survive arm: the
    ``argv_lane = None if cwd_lane else _argv_lane(pid, wt_root)`` line and
    ``lane = cwd_lane or argv_lane`` in ``discover_lanes``. Revert to
    cwd-only (``if cwd is None or not cwd.startswith(...): continue``) and
    a lane whose cwd is the main checkout is invisible — the bug in
    production tonight.
    """

    def _make_worktree(self, target: Path, lane: str) -> Path:
        wt = target / ".worktrees" / lane
        wt.mkdir(parents=True, exist_ok=True)
        (wt / "BRIEF.md").write_text("lane brief")
        return wt

    def _spawn_maincwd_ccc(self, main_cwd: Path, wt_path: str,
                           hold: float = 30.0):
        """A live process whose cwd is the main checkout AND whose argv
        carries the worktree path — the exact shape of today's dispatch.

        ``ccc`` runs from the main checkout (cwd=main); the appended brief
        embeds ``Worktree: <wt_path>``. ``executable`` sets argv[0]=ccc
        independently of the binary; the trailing arg is a synthetic brief
        whose Worktree line names the worktree path.
        """
        brief = "Worktree: %s\nLane: test" % wt_path
        return subprocess.Popen(
            ["ccc", "-e", f"sleep {hold}", "--", "--yolo", "@glm52", brief],
            executable=_which_perl(), cwd=str(main_cwd),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)

    def test_lane_with_main_cwd_is_discovered_via_argv(self, tmp_path,
                                                       monkeypatch):
        # THE BUG SHAPE: a ccc lane whose cwd is the main checkout (tmp_path,
        # standing in for the repo root) but whose argv carries the worktree
        # path. A cwd-only walk finds nothing; the argv recovery finds it.
        wt = self._make_worktree(tmp_path, "lane-775argv")
        proc = self._spawn_maincwd_ccc(tmp_path, str(wt))
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(proc.pid), \
                "precondition: spawned ccc lane must be alive"
            real_cwd = status_sync._read_proc_cwd(proc.pid)
            # Precondition (the bug state, built not assumed): cwd is NOT the
            # worktree, and the worktree path IS in argv.
            assert real_cwd == str(tmp_path), \
                "precondition: cwd must be main checkout, not the worktree: %r" \
                % real_cwd
            assert str(wt) != real_cwd, \
                "precondition: cwd must differ from the worktree path"
            lane = status_sync._argv_lane(proc.pid, str(tmp_path / ".worktrees"))
            assert lane == "lane-775argv", \
                "precondition: argv must carry the worktree path: %r" % lane
            monkeypatch.setattr(
                status_sync.os, "listdir",
                lambda d: [str(proc.pid)] if d == "/proc" else [])

            found, _ph, _at = status_sync.discover_lanes(tmp_path)
            # DISCRIMINATING (Direction 1): the lane is present by name. A
            # count-only check passes against the bug; this names exactly
            # which lane was invisible.
            assert any(f[0] == "lane-775argv" for f in found), \
                "a ccc lane with main-cwd must be discovered via argv; " \
                "got found=%s" % found
        finally:
            proc.kill()
            proc.wait()

    def test_lane_with_main_cwd_repopulates_empty_dreamers(self, tmp_path,
                                                            monkeypatch):
        # End-to-end: starting from dreamers=[], a main-cwd lane repopulates
        # the field — the fleet no longer reads 0 live while the lane runs.
        wt = self._make_worktree(tmp_path, "lane-775argv")
        proc = self._spawn_maincwd_ccc(tmp_path, str(wt))
        try:
            time.sleep(0.6)
            assert status_sync._pid_alive(proc.pid)
            assert status_sync._read_proc_cwd(proc.pid) == str(tmp_path), \
                "precondition: cwd is the main checkout"
            monkeypatch.setattr(
                status_sync.os, "listdir",
                lambda d: [str(proc.pid)] if d == "/proc" else [])
            status = {"dreamers": [], "current_task_ids": [], "queue": {},
                      "task": "t"}
            rc, out, err = _run(status, _ledger(775), tmp_path)
            assert rc == 0, err
            result = json.loads(
                (tmp_path / ".dreamwork" / "status.json").read_text())
            # DISCRIMINATING: the field repopulated from [] and the lane is
            # named. The bug left dreamers=[] ("already in sync, 0 live").
            assert len(result["dreamers"]) == 1, \
                "a main-cwd lane must repopulate dreamers from []; got %s" \
                % result["dreamers"]
            assert result["dreamers"][0]["lane"] == "lane-775argv", \
                result["dreamers"]
            assert 775 in result["current_task_ids"], \
                result["current_task_ids"]
        finally:
            proc.kill()
            proc.wait()


class TestArgvDiscoveryInjectedTable:
    """#775 Direction 2: provable without a live fleet via an injected
    process table. These tests fake the /proc reads but exercise the real
    ``_argv_lane`` parser and the real ``discover_lanes`` classification
    logic against controlled cmdline bytes — so the behaviour is provable
    independent of which lanes happen to be running.

    Each test names the production line that must change for it to fail.
    """

    def _setup_proc(self, monkeypatch, pid, cwd, cmdline_raw):
        """Inject one process: /proc/<pid>/cwd -> cwd, /proc/<pid>/cmdline
        -> cmdline_raw, and /proc listing -> [str(pid)]. The real
        _read_proc_cwd, _argv_lane, _is_ccc_proc, and _ccc_model run
        against these — no logic is faked."""
        import builtins
        real_open = builtins.open

        class _FakeFile(io.BytesIO):
            def __enter__(self):
                return self
            def __exit__(self, *a):
                self.close()

        def fake_open(path, *a, **kw):
            sp = str(path)
            if sp == "/proc/%d/cmdline" % pid:
                return _FakeFile(cmdline_raw)
            return real_open(path, *a, **kw)
        monkeypatch.setattr(builtins, "open", fake_open)
        monkeypatch.setattr(status_sync.os, "readlink",
                            lambda p: cwd if p == "/proc/%d/cwd" % pid
                            else (_ for _ in ()).throw(OSError()))
        monkeypatch.setattr(status_sync.os, "listdir",
                            lambda d: [str(pid)] if d == "/proc" else [])

    def test_lane_execed_away_is_still_found(self, tmp_path, monkeypatch):
        # THE BUG: the matcher looked for `ccc` in argv. After exec, argv[0]
        # is `codex-code-mode-host` — no `ccc` anywhere — but the worktree
        # path survives in the appended brief. A matcher keyed on the
        # runner name reads zero; a matcher keyed on the worktree path
        # (the invariant the dispatch route controls) finds the lane.
        wt = tmp_path / ".worktrees" / "lane-775execed"
        wt.mkdir(parents=True)
        (wt / "BRIEF.md").write_text("x")
        # argv: codex-code-mode-host (NOT ccc) + a brief carrying Worktree:
        brief = "Worktree: %s" % wt
        raw = ("codex-code-mode-host\x00--yolo\x00"
               + brief + "\x00").encode()
        self._setup_proc(monkeypatch, 888111, str(tmp_path), raw)
        # _is_ccc_proc reads argv[0] basename == codex-code-mode-host -> False.
        # So this lane is NOT ccc; it falls to agent_tool (the #675 channel).
        # The POINT: discovery SEES it (it is not zero); a runner-name
        # matcher would not.
        found, _ph, agent_tool = status_sync.discover_lanes(tmp_path)
        assert found == [], found   # not ccc, so not in `found`
        # DISCRIMINATING (Direction 2a): the execed-away lane IS discovered
        # via argv — it appears in agent_tool, not nowhere. A matcher keyed
        # on argv[0]==ccc returns agent_tool=[] here (the bug: 0 live).
        assert any(a[0] == "lane-775execed" for a in agent_tool), \
            "an execed-away lane must be discoverable via its argv worktree " \
            "path, not invisible to a runner-name matcher; agent_tool=%s" \
            % agent_tool

    def test_ccc_lane_with_main_cwd_found_in_found(self, tmp_path,
                                                    monkeypatch):
        # A ccc lane (argv[0]==ccc) with main cwd: found via argv, classified
        # ccc. This is the exact production shape (ccc -y @glm52 <brief>).
        wt = tmp_path / ".worktrees" / "lane-775ccc"
        wt.mkdir(parents=True)
        (wt / "BRIEF.md").write_text("x")
        brief = "Worktree: %s" % wt
        raw = ("ccc\x00-y\x00@glm52\x00" + brief + "\x00").encode()
        self._setup_proc(monkeypatch, 888222, str(tmp_path), raw)
        found, _ph, _at = status_sync.discover_lanes(tmp_path)
        # DISCRIMINATING: the ccc lane with main cwd is in `found` (ccc,
        # not agent_tool), recovered via argv. Revert to cwd-only and
        # found=[] — the bug.
        assert any(f[0] == "lane-775ccc" for f in found), \
            "a ccc lane with main cwd must be found via argv; got %s" % found

    def test_container_hex_with_ccc_is_not_a_lane(self, tmp_path, monkeypatch):
        # THE FALSE POSITIVE (latent, from the brief): the old matcher
        # looked for the SUBSTRING `ccc` in argv. A containerd-shim line
        # carries `ccc` inside a container hex id
        # (...3a1c5ccc6d22e34...). It is NOT a lane. The worktree-path
        # invariant does not match it (no .worktrees/ path in argv), so it
        # is correctly NOT counted.
        raw = (b"containerd-shim-runc-v2\x00-namespace\x00moby\x00-id\x00"
               b"1640fa687243e9110badb503c6fa3ff1e1efe9805d4bd8d534a1c5ccc"
               b"6d22e34\x00-address\x00/run/containerd/containerd.sock\x00")
        self._setup_proc(monkeypatch, 888333, "/run/containerd", raw)
        found, phantoms, agent_tool = status_sync.discover_lanes(tmp_path)
        # DISCRIMINATING (Direction 2b): no lane is counted. A substring
        # matcher on `ccc` would count this container; the worktree-path
        # invariant does not.
        assert found == [], \
            "a container hex id containing 'ccc' must not be a lane: %s" \
            % found
        assert agent_tool == [], agent_tool
        # cwd is /run/containerd — not under .worktrees, so not even a phantom.
        assert phantoms == [], phantoms

    def test_unrelated_worktree_path_in_prose_is_not_false_counted(
            self, tmp_path, monkeypatch):
        # Direction 2 refinement: a process whose argv merely MENTIONS a
        # .worktrees/ path in passing prose (a coordinator's grep of the
        # tasks file) is not a lane. The matcher finds the path, recovers
        # a lane name — but the lane dir does not exist, so it is a phantom
        # (reported, not silently counted). This proves discovery does not
        # over-count on a coincidental path mention.
        fake_lane = "lane-doesnotexist"
        wt_path = str(tmp_path / ".worktrees" / fake_lane)
        raw = ("grep\x00-n\x00worktree\x00some note about %s here\x00"
               % wt_path).encode()
        self._setup_proc(monkeypatch, 888444, str(tmp_path), raw)
        found, phantoms, agent_tool = status_sync.discover_lanes(tmp_path)
        # The lane dir does not exist -> phantom (reported, not in found).
        # DISCRIMINATING: found is empty (not a false lane); the process is
        # reported as a phantom, not silently counted.
        assert found == [], \
            "a prose mention of a worktree path must not be a lane: %s" \
            % found
        # The grep process is non-ccc; its cwd is tmp_path (not a worktree);
        # its argv names a worktree whose dir does not exist. It lands in
        # phantoms (reported not dropped — #702).
        assert any(p[0] == fake_lane for p in phantoms), \
            "a process naming a non-existent worktree must be a phantom, " \
            "not silently dropped: phantoms=%s" % phantoms
