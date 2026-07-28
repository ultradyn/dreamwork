"""Red-first tests for ledger_store (#294 increment 1).

Named production lines whose change must red each test:

- AUTOINCREMENT on task.id in _SCHEMA_SQL
      → test_autoincrement_does_not_reuse_a_deleted_high_water_id
- seed_sequence refuse-to-lower guard (new_seq < current)
      → test_seed_refuses_to_lower_an_established_sequence
- open_store unseeded refusal (sequence_high_water is None branch)
      → test_open_without_seed_fails_loud
- derive_next_id empty-ids branch
      → test_derive_next_id_fails_on_empty_parse
- derive_next_id header != MAX(id)+1 branch
      → test_derive_next_id_fails_when_header_drifts_below_max
- derive_next_id uses watch.parse_ledger (not a hand regex)
      → test_derive_next_id_matches_lint_load_watch_parse_ledger
- seed verification after write (got != next_id)
      → test_seed_from_live_ledger_matches_derived_next_id
- PRAGMA foreign_keys=ON execute
      → test_foreign_keys_pragma_is_on
- PRAGMA synchronous=FULL execute (NORMAL-then-FULL pin)
      → test_pragmas_match_the_durability_boundary
- schema tables in _SCHEMA_SQL
      → test_schema_creates_entity_and_event_tables

A green red-run is a finding, never a relief. Each test names its line so an
injection can aim at production rather than scaffolding.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import lint
from ledger_store import (
    BUSY_TIMEOUT_MS,
    SCHEMA_VERSION,
    SeedError,
    derive_next_id,
    open_store,
)


REPO = Path(__file__).resolve().parent
LIVE_LEDGER = REPO / ".dreamwork" / "tasks.md"


@pytest.fixture
def live_text() -> str:
    """The real Markdown ledger — read-only. Never written."""
    return LIVE_LEDGER.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Seed derivation through lint's parser (one truth)
# ---------------------------------------------------------------------------

def test_derive_next_id_matches_lint_load_watch_parse_ledger(live_text):
    """Production line: derive_next_id → lint.load_watch → parse_ledger.

    Break by computing max via a second regex over `#N` tokens — a second
    truth that can disagree with parse_ledger on combined heads / also-landed.
    """
    watch = lint.load_watch()
    assert watch is not None, "precondition: watch.py must import for this check"
    open_ids, landed_ids = watch.parse_ledger(live_text)
    all_ids = {int(x) for x in open_ids} | {int(x) for x in landed_ids}
    # Runtime-derived precondition: a non-trivial next id, or the seed check
    # passes on an empty parse and measures nothing.
    assert all_ids, "precondition: live ledger must parse to at least one id"
    expected = max(all_ids) + 1
    assert expected > 1, (
        f"precondition: next id must be non-trivial, got {expected}"
    )
    got = derive_next_id(live_text)
    assert got == expected, (
        f"derive_next_id={got} != parse_ledger MAX+1={expected}"
    )


def test_derive_next_id_agrees_with_header_on_live_ledger(live_text):
    """On a healthy ledger the header and MAX(id)+1 agree (F2)."""
    header = lint.NEXT_ID.search(live_text)
    assert header is not None, "precondition: live ledger has a Next id header"
    header_next = int(header.group(1))
    derived = derive_next_id(live_text)
    assert derived == header_next
    assert derived > 100, (
        f"precondition: live next id is non-trivial, got {derived}"
    )


def test_derive_next_id_fails_on_empty_parse():
    """Production line: `if not all_ids: raise SeedError`.

    Break by returning 1 on empty — a store that seeds at 1 after cutover
    collides with every imported permanent id.
    """
    # A ledger with headings but no entry heads: parse_ledger returns empty.
    emptyish = (
        "# Task ledger\n\nNext id: **1**\n\n## Open\n\n## Recently landed\n"
    )
    watch = lint.load_watch()
    assert watch is not None
    o, l = watch.parse_ledger(emptyish)
    assert not o and not l, (
        "precondition: fixture must parse to zero ids, "
        f"got open={o!r} landed={l!r}"
    )
    with pytest.raises(SeedError, match="no ids"):
        derive_next_id(emptyish)


def test_derive_next_id_fails_when_header_drifts_below_max():
    """Production line: header_next != derived → SeedError.

    Break by trusting the header — a drifted header would mint a colliding id.
    Fixture carries a real entry so MAX(id)+1 is 11, header says 5.
    """
    drifted = (
        "# Task ledger\n\n"
        "Next id: **5**\n\n"
        "## Open\n"
        "- **#10** — a real open entry · **P2** · origin: **loop**\n"
        "  body line\n\n"
        "## Recently landed\n"
    )
    watch = lint.load_watch()
    assert watch is not None
    open_ids, landed_ids = watch.parse_ledger(drifted)
    all_ids = {int(x) for x in open_ids} | {int(x) for x in landed_ids}
    assert all_ids == {10}, f"precondition: fixture must parse to {{10}}, got {all_ids}"
    assert max(all_ids) + 1 == 11
    header = lint.NEXT_ID.search(drifted)
    assert header is not None and int(header.group(1)) == 5
    assert int(header.group(1)) != max(all_ids) + 1, (
        "precondition: header must disagree with MAX+1"
    )
    with pytest.raises(SeedError, match="drifted|header"):
        derive_next_id(drifted)


# ---------------------------------------------------------------------------
# Open / create / seed
# ---------------------------------------------------------------------------

def test_open_without_seed_fails_loud(tmp_path):
    """Production line: open_store unseeded branch raises SeedError.

    Break by defaulting next_id to 1 — silent wrong sequence.
    """
    path = tmp_path / "ledger.sqlite3"
    with pytest.raises(SeedError, match="unseeded"):
        open_store(path)
    # And nothing was left half-open as a usable unseeded DB that a second
    # call could accidentally trust — re-open still refuses without a seed.
    with pytest.raises(SeedError, match="unseeded"):
        open_store(path)


def test_seed_from_live_ledger_matches_derived_next_id(tmp_path, live_text):
    """Production line: seed_from_ledger → derive_next_id + seed_sequence verify.

    Break by writing seq = next_id instead of next_id-1 — next_id() would
    report next_id+1 and the verify assert must catch it.
    """
    expected = derive_next_id(live_text)
    assert expected > 1, f"precondition: non-trivial next id, got {expected}"
    store = open_store(tmp_path / "l.sqlite3", ledger_text=live_text)
    try:
        assert store.next_id() == expected
        assert store.sequence_high_water("task") == expected - 1
    finally:
        store.close()


def test_seed_refuses_to_lower_an_established_sequence(tmp_path):
    """Production line: `if current is not None and new_seq < current`.

    Break by removing the lower-guard — a bad re-seed resets permanent ids.
    """
    path = tmp_path / "l.sqlite3"
    store = open_store(path, seed_next_id=100)
    try:
        assert store.next_id() == 100
        # Raising is fine.
        store.seed_sequence(200)
        assert store.next_id() == 200
        # Lowering must fail loud.
        with pytest.raises(SeedError, match="lower|reset"):
            store.seed_sequence(50)
        # Sequence unchanged after the refusal.
        assert store.next_id() == 200
    finally:
        store.close()


def test_reopen_keeps_the_seeded_sequence(tmp_path):
    """Sequence is a file property: second open without re-seed still knows it."""
    path = tmp_path / "l.sqlite3"
    s1 = open_store(path, seed_next_id=77)
    s1.close()
    s2 = open_store(path)  # no seed args — already established
    try:
        assert s2.next_id() == 77
    finally:
        s2.close()


# ---------------------------------------------------------------------------
# AUTOINCREMENT non-reuse — the R1 property that must actually be tested
# ---------------------------------------------------------------------------

def test_autoincrement_does_not_reuse_a_deleted_high_water_id(tmp_path):
    """Production line: `id INTEGER PRIMARY KEY AUTOINCREMENT` on task.

    Break by dropping AUTOINCREMENT (plain INTEGER PRIMARY KEY) — SQLite then
    reuses the highest free id after a delete, which reissues a permanent id.

    Procedure: insert at the high-water mark, delete that row, insert again
    without an explicit id, assert the new id is strictly greater.
    """
    store = open_store(tmp_path / "l.sqlite3", seed_next_id=50)
    try:
        # Parent entry row so the FK holds.
        store.conn.execute(
            "INSERT INTO entry(entry_id, state, title, body) "
            "VALUES (1, 'open', 't', 'b')"
        )
        store.conn.execute(
            "INSERT INTO task(id, entry_id) VALUES (50, 1)"
        )
        store.conn.commit()
        assert store.sequence_high_water("task") == 50

        store.conn.execute("DELETE FROM task WHERE id = 50")
        store.conn.commit()
        # Row is gone…
        assert store.conn.execute("SELECT COUNT(*) FROM task").fetchone()[0] == 0
        # …but the high-water mark must still be 50.
        assert store.sequence_high_water("task") == 50, (
            "sqlite_sequence high-water must survive a delete of the highest row"
        )

        store.conn.execute("INSERT INTO task(entry_id) VALUES (1)")
        store.conn.commit()
        new_id = store.conn.execute("SELECT id FROM task").fetchone()[0]
        assert new_id == 51, (
            f"AUTOINCREMENT must not reuse deleted id 50; got {new_id}. "
            "If this is 50, the schema is missing AUTOINCREMENT and R1 is "
            "unimplemented whatever the DDL prose says."
        )
        assert new_id != 50
    finally:
        store.close()


# ---------------------------------------------------------------------------
# Schema + pragmas (user_events house style)
# ---------------------------------------------------------------------------

def test_schema_creates_entity_and_event_tables(tmp_path):
    """Production line: _SCHEMA_SQL CREATE TABLE statements.

    Break by dropping task_event or task from the DDL.
    """
    store = open_store(tmp_path / "l.sqlite3", seed_next_id=1)
    try:
        tables = store.tables()
        required = {
            "meta",
            "entry",
            "task",
            "related",
            "depends",
            "review_decision",
            "task_event",
            "task_state",
            "priority_band",
            "task_state_kind",
            "task_cause",
        }
        missing = required - tables
        assert not missing, f"schema missing tables: {sorted(missing)}"
    finally:
        store.close()


def test_pragmas_match_the_durability_boundary(tmp_path):
    """Production line: PRAGMA synchronous=FULL (after NORMAL pin) + WAL.

    Break by deleting the FULL execute — SQLite 3.53's default is already
    FULL, so the NORMAL pin makes the FULL line load-bearing.
    """
    store = open_store(tmp_path / "l.sqlite3", seed_next_id=1)
    try:
        # Read from a SECOND connection so we see file-level WAL and this
        # connection's re-applied per-connection pragmas independently.
        p = store.read_pragmas()
        assert p["journal_mode"] == "wal"
        assert p["synchronous"] == 2, (
            f"expected synchronous=FULL (2), got {p['synchronous']}"
        )
        assert p["busy_timeout"] == BUSY_TIMEOUT_MS
    finally:
        store.close()


def test_foreign_keys_pragma_is_on(tmp_path):
    """Production line: PRAGMA foreign_keys=ON.

    Break by dropping that execute — SQLite defaults OFF, so REFERENCES
    becomes a comment and a dangling task_id insert succeeds.
    """
    store = open_store(tmp_path / "l.sqlite3", seed_next_id=1)
    try:
        assert store.read_pragmas()["foreign_keys"] == 1
        # A violating insert must raise, proving the pragma is load-bearing
        # rather than merely reported.
        with pytest.raises(Exception):
            store.conn.execute(
                "INSERT INTO task(id, entry_id) VALUES (1, 999999)"
            )
            store.conn.commit()
    finally:
        store.close()


def test_schema_version_is_recorded(tmp_path):
    store = open_store(tmp_path / "l.sqlite3", seed_next_id=1)
    try:
        row = store.conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
        assert row is not None
        assert int(row[0]) == SCHEMA_VERSION
    finally:
        store.close()


def test_priority_uncertain_bit_and_closed_bands(tmp_path):
    """S2 shape: closed priority_band + priority_uncertain bit.

    Break by allowing an arbitrary priority string (no FK) — the compound
    P0/P1 values return.
    """
    store = open_store(tmp_path / "l.sqlite3", seed_next_id=1)
    try:
        store.conn.execute(
            "INSERT INTO entry(state, title, body, priority, priority_uncertain) "
            "VALUES ('open', 't', 'b', 'P1', 1)"
        )
        store.conn.commit()
        row = store.conn.execute(
            "SELECT priority, priority_uncertain FROM entry"
        ).fetchone()
        assert row == ("P1", 1)
        with pytest.raises(Exception):
            store.conn.execute(
                "INSERT INTO entry(state, title, body, priority) "
                "VALUES ('open', 't2', 'b', 'P0/P1')"
            )
            store.conn.commit()
    finally:
        store.close()
