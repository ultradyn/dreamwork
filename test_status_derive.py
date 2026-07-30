"""Born-red tests for status_derive — the store-backed status derivation (#560).

Red-first: each test names the production line its red run binds, builds a REAL
post-cutover store via the REAL writers (ledger_write.file_task / land_task —
never a hand-built fixture), and asserts the precondition gap at RUNTIME
(derive the stale claim's total AND the store's open count, then assert they
REALLY differ — pin neither). The bug these exist for is #362: the panel's
``queue`` summed to 115 while the ledger held 123 open, because the loop's
hand-maintained claim never met the truth.

Named production line whose change must red the core derivation:
- status_from_store's ``out["queue"] = queue_depth(open_count, live_count)``
  in the post-cutover branch — the one line that makes the panel read the
  store instead of the stale claim. Sabotage it (return status unchanged in
  store mode) and the derived-total test fails.

The store is built by the real verbs and cut over by writing the real
``ledger_cut_over`` meta key (the same flag ``perform_cutover`` writes), so
``source_of_truth`` answers ``'store'`` — the derivation's dispatch gate.
"""

from __future__ import annotations

import json

import ledger_parse
import ledger_store
import ledger_write
import status_derive

_WATERMARK_KEY = "ledger_cut_over"


def _cut_over_store(dw, total, land_n, *, seed=500):
    """A REAL post-cutover store: open_store + the cutover watermark + the
    real file/land verbs. Returns the expected OPEN count (total - land_n).

    The watermark is the one-way cutover flag (``ledger_cut_over`` in meta) —
    the same key ``perform_cutover`` writes, which is all ``source_of_truth``
    checks. Task rows are built by the real writers, never hand-built.
    """
    s = ledger_store.open_store(dw / "ledger.sqlite3", seed_next_id=seed)
    try:
        s.conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            (_WATERMARK_KEY, "2026-07-30"))
        s.conn.commit()
        ids = [ledger_write.file_task(s, "task %d" % i, "body %d" % i)
               for i in range(total)]
        for tid in ids[:land_n]:
            ledger_write.land_task(s, tid)
    finally:
        s.close()
    return total - land_n


def _open_count(dw):
    """The store's open id count, via the ONE read verb the derivation uses."""
    open_ids, _ = ledger_parse.store_ids_by_state(str(dw))
    return len(open_ids)


# ---------------------------------------------------------------------------
# queue_depth — the pure split (separately testable, no store needed).
# ---------------------------------------------------------------------------

def test_queue_depth_total_equals_open_count():
    # the #362 invariant: in_progress + pending == open_count always.
    for open_n, live in [(6, 2), (10, 0), (3, 3)]:
        q = status_derive.queue_depth(open_n, live)
        assert q["in_progress"] + q["pending"] == open_n


def test_queue_depth_mirrors_status_sync_split():
    # in_progress = live lanes; pending = open - live (status_sync's formula).
    assert status_derive.queue_depth(6, 2) == {"in_progress": 2, "pending": 4}


def test_queue_depth_clamps_in_flight_to_open():
    # a stale roster cannot name more lanes in flight than there are open
    # tasks — the total stays the store truth, not the roster's claim.
    assert status_derive.queue_depth(5, 7) == {"in_progress": 5, "pending": 0}
    assert status_derive.queue_depth(0, 2) == {"in_progress": 0, "pending": 0}


# ---------------------------------------------------------------------------
# status_from_store — post-cutover: the panel reads the store, not the claim.
# ---------------------------------------------------------------------------

def test_post_cutover_derives_queue_from_the_store(tmp_path):
    dw = tmp_path / ".dreamwork"
    dw.mkdir()
    # 10 filed, 4 landed -> 6 open in the REAL store.
    open_count = _cut_over_store(dw, total=10, land_n=4)
    # precondition, derived from the real store (not pinned): 6 open.
    assert _open_count(dw) == open_count == 6, "fixture: store genuinely open"

    # a STALE status.json claim whose total REALLY differs from the store.
    stale = {"in_progress": 99, "pending": 99}
    stale_total = stale["in_progress"] + stale["pending"]
    # assert the precondition gap at runtime: derive both, pin neither.
    assert stale_total != _open_count(dw), (
        "precondition: the stale claim's total must REALLY differ from the "
        "store's open count, or the test examines nothing")

    status = {"task": "prose loop claim", "agents": [
        {"name": "lane-a", "in_flight": "x"}, {"name": "lane-b"}],
        "queue": stale}
    out = status_derive.status_from_store(str(dw), status)

    q = out["queue"]
    # the derivation makes the panel read the STORE total, not the claim.
    assert q["in_progress"] + q["pending"] == _open_count(dw) == 6
    assert q != stale, "the stale claim must be replaced, not echoed"
    # in_progress mirrors the live roster (2 agents) the loop already carries.
    assert q["in_progress"] == 2
    assert q["pending"] == 4
    # the loop-claim remainder is passed through untouched.
    assert out["task"] == "prose loop claim"
    assert out["agents"] == status["agents"]


def test_post_cutover_handles_no_agents_roster(tmp_path):
    dw = tmp_path / ".dreamwork"
    dw.mkdir()
    _cut_over_store(dw, total=5, land_n=2)  # 3 open
    # no agents key at all (a loop with no live lanes): all open is pending.
    out = status_derive.status_from_store(str(dw), {"queue": {"in_progress": 9, "pending": 9}})
    assert out["queue"] == {"in_progress": 0, "pending": 3}


# ---------------------------------------------------------------------------
# Degrade, never throw — pre-cutover / no store / non-dict status.
# ---------------------------------------------------------------------------

def test_pre_cutover_status_returned_unchanged_byte_for_byte(tmp_path):
    # a target that never cut over: no store, no watermark. The hand-
    # maintained queue renders EXACTLY as it did today.
    dw = tmp_path / ".dreamwork"
    dw.mkdir()
    status = {"queue": {"in_progress": 7, "pending": 7}, "task": "x"}
    out = status_derive.status_from_store(str(dw), status)
    assert out is status
    assert out["queue"] == {"in_progress": 7, "pending": 7}


def test_non_dict_status_returned_unchanged(tmp_path):
    dw = tmp_path / ".dreamwork"
    dw.mkdir()
    _cut_over_store(dw, total=3, land_n=0)
    # None (no status.json / torn read) and a non-object must not crash and
    # must not be coerced into a dict — statusBlock handles falsy itself.
    assert status_derive.status_from_store(str(dw), None) is None
    assert status_derive.status_from_store(str(dw), "not a dict") == "not a dict"


def test_post_cutover_store_with_zero_open(tmp_path):
    dw = tmp_path / ".dreamwork"
    dw.mkdir()
    _cut_over_store(dw, total=3, land_n=3)  # all landed -> 0 open
    out = status_derive.status_from_store(
        str(dw), {"agents": [{"name": "lane-a"}], "queue": {"in_progress": 5, "pending": 5}})
    # total is the store truth (0); in_flight clamped to 0.
    assert out["queue"] == {"in_progress": 0, "pending": 0}
