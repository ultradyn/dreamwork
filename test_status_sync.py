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
            assert 396 in cti and "401" in cti, cti
            assert cti == sorted([396, "401", "392a"], key=str), cti
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
