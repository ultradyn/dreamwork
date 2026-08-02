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
from dreamwork_db import Access, open_database
from dreamwork_db.tasks import task_store_spec

_WATERMARK_KEY = "ledger_cut_over"


def _cut_over_store(dw, total, land_n, *, seed=500):
    """A REAL post-cutover store: open_store + the cutover watermark + the
    real file/land verbs. Returns the expected OPEN count (total - land_n).

    The watermark is the one-way cutover flag (``ledger_cut_over`` in meta) —
    the same key ``perform_cutover`` writes, which is all ``source_of_truth``
    checks. Task rows are built by the real writers, never hand-built.
    """
    path = dw / "ledger.sqlite3"
    s = ledger_store.open_store(path, seed_next_id=seed)
    try:
        s.conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            (_WATERMARK_KEY, "2026-07-30"))
        s.conn.commit()
    finally:
        s.close()
    with open_database(task_store_spec(path), access=Access.WRITE) as handle:
        ids = [ledger_write.file_task(
            handle, "task %d" % i, "body %d" % i) for i in range(total)]
        for tid in ids[:land_n]:
            ledger_write.land_task(handle, tid)
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

    # The live roster is `dreamers` — the roster status_sync DERIVES and
    # maintains (#965: `agents` is the author-owned loop-claim and is empty;
    # `dreamers` is the pruned, liveness-checked lane set the writer keeps).
    dreamers = [{"name": "lane-a", "task": 600},
                {"name": "lane-b", "task": 601}]
    status = {"task": "prose loop claim", "dreamers": dreamers, "queue": stale}
    out = status_derive.status_from_store(str(dw), status)

    q = out["queue"]
    # the derivation makes the panel read the STORE total, not the claim.
    assert q["in_progress"] + q["pending"] == _open_count(dw) == 6
    assert q != stale, "the stale claim must be replaced, not echoed"
    # in_progress mirrors the live `dreamers` roster (2 lanes) the loop carries.
    assert q["in_progress"] == 2
    assert q["pending"] == 4
    # the loop-claim remainder is passed through untouched.
    assert out["task"] == "prose loop claim"
    assert out["dreamers"] == dreamers


# #965 — THE BUG: queue_depth took its live count from the EMPTY `agents`
# roster and rendered `0 in flight` while lanes were genuinely working. This
# is the regression: a NON-EMPTY `dreamers` roster must report those lanes as
# in flight. A fixture with an empty roster passes either way (0 is what the
# bug prints too), so the precondition asserts the roster AND the expected
# count are BOTH non-zero — the discriminating pair.
def test_post_cutover_dreamers_drives_in_flight_not_agents(tmp_path):
    dw = tmp_path / ".dreamwork"
    dw.mkdir()
    # 8 filed, 1 landed -> 7 open in the REAL store (more than the lanes, so
    # the clamp cannot be what caps in_progress at the roster size).
    open_count = _cut_over_store(dw, total=8, land_n=1)
    assert _open_count(dw) == open_count == 7, "fixture: store genuinely open"

    n_lanes = 5  # five lanes genuinely working, as in the live measurement
    dreamers = [{"name": "lane-%d" % i, "task": 700 + i} for i in range(n_lanes)]
    # `agents` is the author-owned loop-claim and is EMPTY in production; it is
    # carried here exactly to prove the old read is dead — if the derivation
    # read `agents` it would report 0.
    status = {"agents": [], "dreamers": dreamers,
              "queue": {"in_progress": 0, "pending": 0}}
    out = status_derive.status_from_store(str(dw), status)

    q = out["queue"]
    # precondition the assertion depends on: roster non-empty, expected > 0,
    # and open_count large enough that only the roster can set in_progress.
    assert n_lanes > 0 and n_lanes <= open_count, (
        "precondition: non-empty roster, expected in_progress non-zero")
    assert q["in_progress"] == n_lanes, (
        "the live `dreamers` roster must drive in_progress, not the empty "
        "`agents` roster — this is the #965 defect when it reads 0")
    # #362 invariant survives the field switch.
    assert q["in_progress"] + q["pending"] == open_count


def test_post_cutover_empty_dreamers_means_genuinely_zero(tmp_path):
    dw = tmp_path / ".dreamwork"
    dw.mkdir()
    _cut_over_store(dw, total=5, land_n=2)  # 3 open
    # an EMPTY `dreamers` list (present, zero lanes) is a genuine measurement:
    # nothing is running. This must NOT be confused with an absent roster
    # (next test) — 0 here is a true report, not a degrade.
    out = status_derive.status_from_store(
        str(dw), {"dreamers": [], "queue": {"in_progress": 9, "pending": 9}})
    assert out["queue"] == {"in_progress": 0, "pending": 3}


def test_post_cutover_absent_roster_is_unreadable_not_zero(tmp_path):
    dw = tmp_path / ".dreamwork"
    dw.mkdir()
    _cut_over_store(dw, total=5, land_n=2)  # 3 open
    # NO `dreamers` key at all: the live count cannot be measured. This is the
    # degrade-to-zero shape inside the arithmetic (#868) — the clamp would
    # manufacture a plausible 0. `queue is None` says "there and unreadable"
    # (the `== null` idiom views.js runs for `pending_events`) rather than
    # borrowing zero's pixels for an unmeasured count.
    out = status_derive.status_from_store(str(dw), {"queue": {"in_progress": 9, "pending": 9}})
    assert out["queue"] is None, (
        "an absent roster must degrade to None (unreadable), not to a "
        "confident 0 in flight — the #868 shape this clamp manufactures")


# A stale roster naming more lanes than there are open tasks: the clamp
# (#362) must still hold and the invariant must stay true. This is a
# Direction-2 input — without the clamp, in_progress would exceed open_count
# and the invariant would break.
def test_post_cutover_stale_roster_clamps_in_flight_to_open(tmp_path):
    dw = tmp_path / ".dreamwork"
    dw.mkdir()
    _cut_over_store(dw, total=4, land_n=2)  # 2 open
    open_count = _open_count(dw)
    assert open_count == 2, "fixture: store genuinely open"
    # 5 dreamers but only 2 open tasks — a stale roster. in_progress must be
    # clamped to the open count, not the roster size.
    dreamers = [{"name": "lane-%d" % i, "task": 800 + i} for i in range(5)]
    out = status_derive.status_from_store(
        str(dw), {"dreamers": dreamers, "queue": {"in_progress": 0, "pending": 0}})
    q = out["queue"]
    assert q["in_progress"] == open_count, (
        "a stale roster cannot name more lanes in flight than there are open "
        "tasks — the #362 clamp")
    assert q["in_progress"] + q["pending"] == open_count, (
        "in_progress + pending == open_count must hold under a stale roster")


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
        str(dw), {"dreamers": [{"name": "lane-a"}], "queue": {"in_progress": 5, "pending": 5}})
    # total is the store truth (0); in_flight clamped to 0.
    assert out["queue"] == {"in_progress": 0, "pending": 0}


# The `isinstance` guard on roster entries is inherited and kept (#965): a
# dreamers list carrying junk must not crash and must filter to dict entries.
# A non-list roster degrades to None (same as absent), never throws.
def test_post_cutover_non_dict_dreamers_entries_are_filtered(tmp_path):
    dw = tmp_path / ".dreamwork"
    dw.mkdir()
    _cut_over_store(dw, total=6, land_n=0)  # 6 open
    # mixed roster: 2 real dicts + junk. Only the dicts count.
    dreamers = [{"name": "lane-a", "task": 900}, "junk-string",
                42, {"name": "lane-b", "task": 901}]
    out = status_derive.status_from_store(
        str(dw), {"dreamers": dreamers, "queue": {"in_progress": 0, "pending": 0}})
    q = out["queue"]
    assert q["in_progress"] == 2, "non-dict roster entries are filtered, dicts counted"
    assert q["in_progress"] + q["pending"] == 6


def test_post_cutover_non_list_dreamers_degrades_not_throws(tmp_path):
    dw = tmp_path / ".dreamwork"
    dw.mkdir()
    _cut_over_store(dw, total=3, land_n=0)  # 3 open
    # a roster that is not a list at all cannot be measured — degrade to None,
    # never raise (the request path must not 500 over a derivation).
    out = status_derive.status_from_store(
        str(dw), {"dreamers": "not a list", "queue": {"in_progress": 9, "pending": 9}})
    assert out["queue"] is None
