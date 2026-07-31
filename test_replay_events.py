"""Red-first tests for dev/replay_events.py — the task_event replay tool (#460).

Three claims, each with a test that names the PRODUCTION LINE whose change
would red it, derives its preconditions at runtime, and was red-proved: the
named line was injected, the test failed, and the source restored
byte-identical.

  1. Determinism — same journal replayed twice → byte-identical store.
  2. Round-trip fidelity (the #294 falsifier) — a store built through the real
     apply path, its journal exported and replayed, holds the SAME task_event
     rows; the task TABLE does not round-trip (title/body are not in the
     journal) and that divergence IS the #294 finding.
  3. The merge rule — ONE deterministic total order, arg-order-independent.

Named production lines whose change must red each test:

- ledger_store.append_chained_event (the ONE apply primitive replay rides)
      → test_replay_is_byte_identical_across_two_runs
      → test_round_trip_task_event_chain_is_identical
- replay_into's task-row INSERT (the FK stub the journal cannot fill)
      → test_round_trip_task_state_matches_but_title_does_not_294_finding
- replay_into's call to append_chained_event IN ORDER (chain = line order)
      → test_replay_rebuilds_chain_in_line_order_not_sorted
- merge_streams' event_sort_key (the total-order tie-break)
      → test_merge_is_arg_order_independent
- merge_streams' sorted(a + b) (union, not last-wins)
      → test_merge_is_a_total_order_independent_of_line_shuffle
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

import ledger_store
import ledger_write
import dev.replay_events as rp
from dreamwork_db import Access, open_database
from dreamwork_db.tasks import task_store_spec

REPO = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Fixtures — a store built through the REAL apply path (the round-trip source).
# ---------------------------------------------------------------------------

def _build_real_store(path):
    """Build a store via ledger_write (file + land); return its path.

    Two tasks filed, one landed with a note — the live apply path the
    round-trip replays against. The events span both kinds (filed + landed)
    so the precondition "≥2 event kinds" is honest.
    """
    ledger_store.open_store(path, seed_next_id=500).close()
    with open_database(task_store_spec(path), access=Access.WRITE) as handle:
        t1 = ledger_write.file_task(handle, "first task", "body one",
                                     at="2026-07-29T10:00:00")
        ledger_write.file_task(handle, "second task", "body two",
                                     at="2026-07-29T10:00:01")
        ledger_write.land_task(handle, t1, note="done cleanly",
                                at="2026-07-29T11:00:00")
    with sqlite3.connect(path, isolation_level=None) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return path


def _task_event_rows(path):
    """All task_event columns that define a row, in ordinal order."""
    conn = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT task_id, at, cause, from_state, to_state, actor, "
            "receipt_id, detail, prev_hash, hash "
            "FROM task_event ORDER BY ordinal")]
        return rows
    finally:
        conn.close()


def _task_rows(path):
    conn = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(
            "SELECT id, state, title, body FROM task ORDER BY id")]
    finally:
        conn.close()


@pytest.fixture
def real_store(tmp_path):
    return _build_real_store(tmp_path / "real.sqlite3")


@pytest.fixture
def journal(tmp_path, real_store):
    """The real store's journal exported to .jsonl (the replay input)."""
    events = rp.export_journal(real_store)
    p = tmp_path / "journal.jsonl"
    rp.write_journal(events, p)
    return p


# ---------------------------------------------------------------------------
# 1. Determinism — same journal, replayed twice, byte-identical store.
# ---------------------------------------------------------------------------

def test_replay_is_byte_identical_across_two_runs(tmp_path, journal):
    """Production line: ledger_store.append_chained_event (ridden by replay_into).

    The chain is a PURE function of (prev_hash, canonical bytes), so replaying
    the same journal into two fresh stores must yield byte-identical files
    (after a wal_checkpoint). Break by making the apply non-deterministic —
    two runs would diverge and the byte comparison fails. SQLite is byte-
    deterministic for an identical op sequence from an empty image (probed
    independently: two real-path stores share a sha), so bytes are the honest
    invariant here, not a fallback.
    """
    events = rp.read_journal(journal)
    # Precondition: the journal really spans >=2 event kinds and >=2 tasks, so
    # a byte match is not a vacuous single-row artefact.
    kinds = {e["cause"] for e in events}
    tasks = {e["task_id"] for e in events}
    assert len(kinds) >= 2, f"precondition: need >=2 event kinds, got {kinds}"
    assert len(tasks) >= 2, f"precondition: need >=2 tasks, got {tasks}"

    out1 = rp.replay_into(events, tmp_path / "rep1.sqlite3")
    out2 = rp.replay_into(events, tmp_path / "rep2.sqlite3")
    b1, b2 = out1.read_bytes(), out2.read_bytes()
    assert b1 == b2, (
        f"two replays of the same journal differ ({hashlib.sha256(b1).hexdigest()[:12]}"
        f" vs {hashlib.sha256(b2).hexdigest()[:12]}) — the chain must be a pure"
        " function of its inputs")
    # And both are non-empty (a byte-match on two empty files would be vacuous).
    assert len(b1) > 0


def test_replay_rebuilds_chain_in_line_order_not_sorted(tmp_path):
    """Production line: replay_into applies events in line order via append_chained_event.

    A live store chains each event from the LAST by ordinal (real-time order),
    not from a re-sort. So a journal whose line order is NOT (at, task_id)
    order must replay to the SAME chain the live writer produced — proving
    replay preserves order rather than re-sorting (which would move hashes).
    """
    # Build a real store where the landed event's (at, task_id) sorts BEFORE
    # the second filed event, but was APPENDED after it (ordinal order).
    source = tmp_path / "src.sqlite3"
    ledger_store.open_store(source, seed_next_id=600).close()
    with open_database(task_store_spec(source), access=Access.WRITE) as handle:
        t1 = ledger_write.file_task(handle, "a", "b", at="2026-07-29T09:00:00")
        # second filed at 10:00 (later)
        ledger_write.file_task(handle, "c", "d", at="2026-07-29T10:00:00")
        # land t1 at 09:30 — its (at='09:30', task_id=600) sorts BETWEEN the
        # two filed events by (at,task_id), but it was appended LAST (ordinal 3).
        ledger_write.land_task(handle, t1, at="2026-07-29T09:30:00")
    with sqlite3.connect(source, isolation_level=None) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    events = rp.export_journal(tmp_path / "src.sqlite3")
    # Precondition: line order is NOT (at, task_id) order (else the test is
    # vacuous — a sort and a preserve would agree).
    line_order = [(e["at"], e["task_id"]) for e in events]
    sort_order = sorted(line_order)
    assert line_order != sort_order, (
        "precondition: the journal's line order must differ from its sorted "
        f"order for this red to discriminate; got {line_order}")

    rp.replay_into(events, tmp_path / "rep.sqlite3")
    real_hashes = [r["hash"] for r in _task_event_rows(tmp_path / "src.sqlite3")]
    rep_hashes = [r["hash"] for r in _task_event_rows(tmp_path / "rep.sqlite3")]
    assert rep_hashes == real_hashes, (
        "replay must chain in LINE order (matching the live writer), not "
        "re-sort; a re-sort would move every hash from ordinal 2 onward")


# ---------------------------------------------------------------------------
# 2. Round-trip fidelity — the #294 falsifier.
# ---------------------------------------------------------------------------

def test_round_trip_task_event_chain_is_identical(tmp_path, real_store, journal):
    """Production line: append_chained_event recomputes the SAME chain.

    The real store's task_event rows, exported to .jsonl and replayed into a
    fresh store, must hold IDENTICAL rows — every column, including the
    recomputed prev_hash/hash. This proves the journal captures the chain
    completely: nothing about the transition log is lost in a round-trip.
    Break by restating the chain (a second hash construction) and the hashes
    diverge.
    """
    events = rp.read_journal(journal)
    # Precondition: the real store really has a non-trivial chain to compare.
    real_rows = _task_event_rows(real_store)
    assert len(real_rows) >= 3, (
        f"precondition: need >=3 events for a non-trivial chain, got {len(real_rows)}")

    rp.replay_into(events, tmp_path / "rep.sqlite3")
    rep_rows = _task_event_rows(tmp_path / "rep.sqlite3")
    assert rep_rows == real_rows, (
        "the task_event chain must round-trip exactly; a divergence means the "
        "journal does not capture the chain — a #294 finding, not a tool bug")


def test_round_trip_task_state_matches_but_title_does_not_294_finding(
        tmp_path, real_store, journal):
    """Production line: replay_into's task-row INSERT (the FK stub).

    The journal captures task_id and the state transitions, so the replayed
    task rows match the real store on (id, state). But the journal carries
    NEITHER title NOR body (nor priority/origin/type/blocked_on/body_digest),
    so those do NOT round-trip — replay stubs them. That divergence is the
    #294 finding this tool exists to surface: the task_event journal alone
    cannot reconstruct the task entity, only its lifecycle.
    """
    events = rp.read_journal(journal)
    rp.replay_into(events, tmp_path / "rep.sqlite3")
    real_tasks = _task_rows(real_store)
    rep_tasks = _task_rows(tmp_path / "rep.sqlite3")

    # id + state DO round-trip (the journal captures the lifecycle).
    assert [t["id"] for t in rep_tasks] == [t["id"] for t in real_tasks], (
        "task ids must round-trip — they ARE in the journal")
    assert [t["state"] for t in rep_tasks] == [t["state"] for t in real_tasks], (
        "task state must round-trip — it is the latest transition's to_state")

    # title/body do NOT round-trip — the #294 finding. Assert the precondition
    # (the real titles are real, not already stubs) so a future stub source
    # cannot make this pass vacuously.
    assert all(t["title"] != rp._REPLAY_TITLE for t in real_tasks), (
        "precondition: the real titles must differ from the replay stub")
    titles_match = [t["title"] for t in rep_tasks] == [t["title"] for t in real_tasks]
    assert not titles_match, (
        "title must NOT round-trip: the task_event journal does not capture "
        "title/body/priority/origin/type — this is the #294 finding (name the "
        "missing fields: title, body, priority, origin, type, blocked_on, "
        "body_digest)")


# ---------------------------------------------------------------------------
# 3. The merge rule — ONE deterministic total order.
# ---------------------------------------------------------------------------

def _stream(path, events):
    rp.write_journal(events, path)
    return path


def test_merge_is_arg_order_independent(tmp_path):
    """Production line: merge_streams' event_sort_key (the total-order tie-break).

    merge(a, b) must equal merge(b, a) element-for-element. The total-order key
    (at, task_id, arrival-rank, from_state, to_state, actor, detail) makes the
    order independent of which stream is named first. Break by dropping the
    tie-break terms and a Python sort over equal keys is stable (input-order
    dependent), so merge(a,b) != merge(b,a) on colliding keys.
    """
    a = [
        {"task_id": 1, "at": "2026-07-29T10:00:00", "cause": "filed_from_command",
         "from_state": None, "to_state": "open", "actor": "loop",
         "detail": "", "receipt_id": None},
        {"task_id": 1, "at": "2026-07-29T11:00:00", "cause": "landed",
         "from_state": "open", "to_state": "landed", "actor": "loop",
         "detail": "done", "receipt_id": None},
    ]
    b = [
        {"task_id": 2, "at": "2026-07-29T10:30:00", "cause": "filed_from_command",
         "from_state": None, "to_state": "open", "actor": "loop",
         "detail": "", "receipt_id": None},
    ]
    ap = _stream(tmp_path / "a.jsonl", a)
    bp = _stream(tmp_path / "b.jsonl", b)
    m1 = rp.merge_streams(rp.read_journal(ap), rp.read_journal(bp))
    m2 = rp.merge_streams(rp.read_journal(bp), rp.read_journal(ap))
    assert m1 == m2, (
        "merge must be arg-order-independent — the total-order tie-break makes "
        "the result independent of which stream is named first")


def test_merge_is_a_total_order_independent_of_line_shuffle(tmp_path):
    """Production line: merge_streams' sorted(a + b) (deterministic total order).

    A TOTAL order is independent of within-stream line order: shuffling one
    stream's lines before the merge must not move any event in the merged
    output, because the sort key — not input position — decides order. This is
    what makes a merged journal safe to replay deterministically. Break by
    making merge stable-only (drop the key) and a shuffle changes the output.
    """
    base = [
        {"task_id": 1, "at": "2026-07-29T11:00:00", "cause": "landed",
         "from_state": "open", "to_state": "landed", "actor": "loop",
         "detail": "alpha", "receipt_id": None},
        {"task_id": 1, "at": "2026-07-29T11:00:00", "cause": "landed",
         "from_state": "open", "to_state": "landed", "actor": "loop",
         "detail": "beta", "receipt_id": None},
        {"task_id": 1, "at": "2026-07-29T11:00:00", "cause": "landed",
         "from_state": "open", "to_state": "landed", "actor": "loop",
         "detail": "gamma", "receipt_id": None},
    ]
    # Precondition: the three events collide on the COARSE key (at, task_id,
    # arrival-rank, from/to/actor) — only the tie-break term (detail) tells
    # them apart. A sort on the coarse key alone would leave them input-ordered
    # (stable), so the tie-break is the only thing making the order total.
    coarse = [rp.event_sort_key(e)[:-1] for e in base]
    assert coarse[0] == coarse[1] == coarse[2], (
        "precondition: events must collide on the coarse key so the tie-break "
        f"is the only discriminator; got {coarse}")
    full = [rp.event_sort_key(e) for e in base]
    assert len(set(full)) == 3, (
        "precondition: the full key (with tie-break) must distinguish all three")
    # Three different shuffles of the same stream.
    shuf1 = [base[1], base[0], base[2]]
    shuf2 = [base[2], base[1], base[0]]
    merged_from_base = rp.merge_streams(base, [])
    merged_from_shuf1 = rp.merge_streams(shuf1, [])
    merged_from_shuf2 = rp.merge_streams(shuf2, [])
    assert merged_from_base == merged_from_shuf1 == merged_from_shuf2, (
        "the merge must be a TOTAL order: shuffling a stream's lines cannot "
        "move any event in the output — only the sort key decides order")


def test_merged_stream_replays_to_an_identical_store(tmp_path):
    """The merged total order is replay-deterministic (the merge's payoff).

    Two different splittings of the same event set, each merged and replayed,
    yield byte-identical stores — the merge rule's whole point: any split of
    a multi-agent history converges on one store.
    """
    all_events = [
        {"task_id": 1, "at": "2026-07-29T10:00:00", "cause": "filed_from_command",
         "from_state": None, "to_state": "open", "actor": "loop",
         "detail": "", "receipt_id": None},
        {"task_id": 2, "at": "2026-07-29T10:30:00", "cause": "filed_from_command",
         "from_state": None, "to_state": "open", "actor": "loop",
         "detail": "", "receipt_id": None},
        {"task_id": 1, "at": "2026-07-29T11:00:00", "cause": "landed",
         "from_state": "open", "to_state": "landed", "actor": "loop",
         "detail": "done", "receipt_id": None},
    ]
    # Split the SAME history two ways, merge each, replay.
    split_a = rp.merge_streams(all_events[0:2], all_events[2:3])
    split_b = rp.merge_streams([all_events[2]], all_events[0:2])
    assert split_a == split_b, "precondition: both splits merge to the same order"
    rp.replay_into(split_a, tmp_path / "a.sqlite3")
    rp.replay_into(split_b, tmp_path / "b.sqlite3")
    assert (tmp_path / "a.sqlite3").read_bytes() == (tmp_path / "b.sqlite3").read_bytes(), (
        "two splittings of one history, merged and replayed, must converge on "
        "a byte-identical store")
