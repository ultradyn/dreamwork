"""Red-first tests for ledger_store (#294 increment 2 — the FLAT schema).

Increment 1 (`50f4933`) landed an entry/task split. #353 then split every
combined entry, so every entry IS one task and the join models nothing; the
human ruled FLATTEN 2026-07-29 15:59 — one `task` table, no `entry` /
`task_by_entry`. These tests pin the flat shape; the table set is derived
from sqlite_master at runtime, never a literal tuned to today's schema.

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
      → test_schema_creates_the_flat_task_and_transition_tables
- CREATE TABLE entry / INDEX task_by_entry in _SCHEMA_SQL
      → test_the_entry_split_is_gone
- flat task column list in _SCHEMA_SQL (state/title/body/band/type/origin/…)
      → test_task_carries_the_markdown_columns
- body TEXT NOT NULL on task
      → test_a_task_row_carries_the_free_text_body
- related / depends DDL + FK references to task(id)
      → test_related_and_depends_edges_reference_task_ids

A green red-run is a finding, never a relief. Each test names its line so an
injection can aim at production rather than scaffolding.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import lint
from ledger_store import (
    BUSY_TIMEOUT_MS,
    SCHEMA_VERSION,
    SchemaVersionError,
    SeedError,
    derive_next_id,
    open_store,
)


REPO = Path(__file__).resolve().parent
# Post-cutover (#294) the live Markdown ledger is the FROZEN deprecated file —
# tasks.md itself is a one-line migration-notice shim with no `Next id`
# header and no parseable entries. These markdown-path checks describe the
# frozen document, so that is the file they must read.
LIVE_LEDGER = REPO / ".dreamwork" / "tasks.md.deprecated"


@pytest.fixture
def live_text() -> str:
    """The real (frozen) Markdown ledger — read-only. Never written."""
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
        # Flat shape: the permanent id and the attributes are one row.
        store.conn.execute(
            "INSERT INTO task(id, state, title, body) "
            "VALUES (50, 'open', 't', 'b')"
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

        store.conn.execute(
            "INSERT INTO task(state, title, body) VALUES ('open', 't2', 'b2')"
        )
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

def test_schema_creates_the_flat_task_and_transition_tables(tmp_path):
    """Production line: _SCHEMA_SQL CREATE TABLE statements.

    Break by dropping task_event or task from the DDL.
    """
    store = open_store(tmp_path / "l.sqlite3", seed_next_id=1)
    try:
        tables = store.tables()
        required = {
            "meta",
            "task",
            "related",
            "depends",
            "review_decision",
            "task_event",
            "task_state",
            "priority_band",
            "task_state_kind",
            "task_cause",
            "task_type",
        }
        missing = required - tables
        assert not missing, f"schema missing tables: {sorted(missing)}"
    finally:
        store.close()


def test_the_entry_split_is_gone(tmp_path):
    """Production line: CREATE TABLE entry / INDEX task_by_entry in _SCHEMA_SQL.

    Break by re-adding the entry table or the task_by_entry index — the
    flatten ruling (2026-07-29 15:59) removes both. The sets are derived
    from sqlite_master at runtime: no literal tuned to today's schema.
    """
    store = open_store(tmp_path / "l.sqlite3", seed_next_id=1)
    try:
        tables = store.tables()
        # Runtime-derived precondition: the entity candidates we reason about.
        entity_tables = tables & {"entry", "task"}
        assert entity_tables == {"task"}, (
            f"exactly one entity table must exist and it must be task; "
            f"got {sorted(entity_tables)}"
        )
        indexes = {
            r[0]
            for r in store.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        assert "task_by_entry" not in indexes, (
            f"task_by_entry index survives the flatten: {sorted(indexes)}"
        )
        # task must carry no entry_id column — the join key is the split.
        cols = {
            r[1] for r in store.conn.execute("PRAGMA table_info(task)").fetchall()
        }
        assert "entry_id" not in cols, (
            f"task still carries the split's join key: {sorted(cols)}"
        )
    finally:
        store.close()


def test_task_carries_the_markdown_columns(tmp_path):
    """Production line: the flat task column list in _SCHEMA_SQL.

    Break by dropping any one of the columns the Markdown entry carries —
    state, title, body, priority band + uncertain bit (S2), type (S4 lookup
    FK), origin (closed set), blocked_on prose, body_digest, source_line.
    """
    store = open_store(tmp_path / "l.sqlite3", seed_next_id=1)
    try:
        rows = store.conn.execute("PRAGMA table_info(task)").fetchall()
        cols = {r[1] for r in rows}
        required = {
            "id",
            "state",
            "title",
            "body",
            "priority",
            "priority_uncertain",
            "type",
            "origin",
            "blocked_on",
            "body_digest",
            "source_line",
        }
        missing = required - cols
        assert not missing, (
            f"flat task table missing Markdown columns: {sorted(missing)}"
        )
        # Runtime-derived precondition: id is the integer primary key.
        pk_cols = {r[1] for r in rows if r[5]}
        assert pk_cols == {"id"}, f"task primary key must be id, got {pk_cols}"
        ddl = store.conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='task'"
        ).fetchone()[0]
        assert "AUTOINCREMENT" in ddl.upper(), (
            "task.id must keep the seeded AUTOINCREMENT behaviour (R1)"
        )
    finally:
        store.close()


def test_a_task_row_carries_the_free_text_body(tmp_path):
    """Production line: `body TEXT NOT NULL` on the flat task table.

    Break by dropping body from the DDL or making it nullable — notes and
    updates accumulate in the body across a task's life (his explicit
    question), so a task row must round-trip multi-line prose verbatim.
    """
    store = open_store(tmp_path / "l.sqlite3", seed_next_id=1)
    try:
        # task_type is a growing lookup (S4): a value must be registered
        # before a task may carry it — as the importer will do.
        store.conn.execute(
            "INSERT INTO task_type(type) VALUES ('implementation')"
        )
        body = (
            "first note: filed from the ledger\n"
            "  indented update: design narrowed to the flat shape\n"
            "final update: landed, see task_event for the transition"
        )
        store.conn.execute(
            "INSERT INTO task(state, title, body, priority, priority_uncertain,"
            " type, origin, blocked_on) "
            "VALUES ('open', 'flat task', ?, 'P2', 0, 'implementation',"
            " 'loop', 'blocked on nothing yet')",
            (body,),
        )
        store.conn.commit()
        row = store.conn.execute(
            "SELECT state, title, body, priority, priority_uncertain,"
            " type, origin, blocked_on FROM task"
        ).fetchone()
        assert row == (
            "open",
            "flat task",
            body,
            "P2",
            0,
            "implementation",
            "loop",
            "blocked on nothing yet",
        ), f"task row must round-trip the free-text body verbatim, got {row!r}"
        # body is NOT NULL: a task without one is refused.
        with pytest.raises(Exception):
            store.conn.execute(
                "INSERT INTO task(state, title) VALUES ('open', 'no body')"
            )
            store.conn.commit()
    finally:
        store.close()


def test_related_and_depends_edges_reference_task_ids(tmp_path):
    """Production line: related / depends DDL with REFERENCES task(id).

    Break by pointing either relation at entry(entry_id) — the #346 S1
    relations (n:n related, directed depends) survive the flatten unchanged
    and bind permanent task ids directly.
    """
    store = open_store(tmp_path / "l.sqlite3", seed_next_id=1)
    try:
        for i in (1, 2, 3):
            store.conn.execute(
                "INSERT INTO task(id, state, title, body) "
                "VALUES (?, 'open', ?, 'b')",
                (i, f"t{i}"),
            )
        # related is symmetric, stored once: CHECK (a < b).
        store.conn.execute("INSERT INTO related(a, b) VALUES (1, 2)")
        # depends is directed: 3 cannot start until 1 lands.
        store.conn.execute("INSERT INTO depends(task, needs) VALUES (3, 1)")
        store.conn.commit()
        assert store.conn.execute(
            "SELECT a, b FROM related"
        ).fetchone() == (1, 2)
        assert store.conn.execute(
            "SELECT task, needs FROM depends"
        ).fetchone() == (3, 1)
        with pytest.raises(Exception):
            # Un-normalised symmetric pair must be refused.
            store.conn.execute("INSERT INTO related(a, b) VALUES (2, 1)")
            store.conn.commit()
        with pytest.raises(Exception):
            # An edge to a task that does not exist must be refused (FK).
            store.conn.execute("INSERT INTO depends(task, needs) VALUES (1, 999)")
            store.conn.commit()
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
        # rather than merely reported: 'P9' is not in priority_band.
        with pytest.raises(Exception):
            store.conn.execute(
                "INSERT INTO task(state, title, body, priority) "
                "VALUES ('open', 't', 'b', 'P9')"
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
            "INSERT INTO task(state, title, body, priority, priority_uncertain) "
            "VALUES ('open', 't', 'b', 'P1', 1)"
        )
        store.conn.commit()
        row = store.conn.execute(
            "SELECT priority, priority_uncertain FROM task"
        ).fetchone()
        assert row == ("P1", 1)
        with pytest.raises(Exception):
            store.conn.execute(
                "INSERT INTO task(state, title, body, priority) "
                "VALUES ('open', 't2', 'b', 'P0/P1')"
            )
            store.conn.commit()
    finally:
        store.close()


# ---------------------------------------------------------------------------
# Schema migration v1→v2 (review_decision: question_id → question_title + actor)
#
# Named production lines whose change must red each test:
#
# - _migrate_v1_to_v2's DROP + _REVIEW_DECISION_SQL (the table reshaping)
#       → test_v1_to_v2_migration_reshapes_review_decision_when_empty
# - _migrate_v1_to_v2's `if count != 0: raise SchemaVersionError` guard
#       → test_v1_to_v2_migration_refuses_a_non_empty_table
# ---------------------------------------------------------------------------

# The v1 shape, laid down by a direct sqlite3 connection (NOT open_store) so
# the production migration is the code under test, not the fixture.
_V1_REVIEW_DECISION_SQL = """
CREATE TABLE review_decision (
    artifact    TEXT PRIMARY KEY,
    question_id INTEGER NOT NULL,
    decision    TEXT NOT NULL
                CHECK (decision IN ('pending','accepted','rejected')),
    decided_at  TEXT NOT NULL
);
"""


def _make_v1_store(path, *, with_decision_row=False):
    """Lay down a schema_version=1 store for migration tests.

    Only meta + the v1 review_decision are needed: open_store's
    executescript(IF NOT EXISTS) creates every other table, and the
    migration's behaviour turns entirely on review_decision's shape and row
    count. A second sqlite3 connection writes the v1 shape directly so the
    production migration is the thing under test.
    """
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute(
            "INSERT INTO meta(key, value) VALUES ('schema_version', '1')")
        conn.executescript(_V1_REVIEW_DECISION_SQL)
        if with_decision_row:
            conn.execute(
                "INSERT INTO review_decision"
                "(artifact, question_id, decision, decided_at)"
                " VALUES ('art-1', 7, 'accepted', '2026-07-29T00:00:00Z')")
        conn.commit()
    finally:
        conn.close()


def _columns(conn, table):
    """The column-name set for *table* on *conn*."""
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def test_v1_to_v2_migration_reshapes_review_decision_when_empty(tmp_path):
    """Production line: _migrate_v1_to_v2's DROP + CREATE (_REVIEW_DECISION_SQL).

    An empty v1 store migrates to v2: question_id is gone, question_title and
    actor arrive, and schema_version reads 2. Break by making the migration a
    no-op (drop the DROP+CREATE) — the version bumps to 2 but the table keeps
    its v1 shape, so the question_title/actor assertions fail.
    """
    path = tmp_path / "v1.sqlite3"
    _make_v1_store(path)  # empty review_decision

    # Precondition: the store genuinely is v1 (question_id present, v2 cols
    # absent) and the table is empty — the only state the migration may touch.
    pre = sqlite3.connect(str(path))
    try:
        assert _columns(pre, "review_decision") == {
            "artifact", "question_id", "decision", "decided_at"}, (
            "precondition: fixture must lay down the v1 shape")
        n = pre.execute(
            "SELECT COUNT(*) FROM review_decision").fetchone()[0]
        assert n == 0, "precondition: v1 table must be empty to migrate"
    finally:
        pre.close()

    store = open_store(path, seed_next_id=1)
    try:
        cols = _columns(store.conn, "review_decision")
        assert "question_title" in cols, (
            f"v2 migration must add question_title; cols={sorted(cols)}")
        assert "actor" in cols, (
            f"v2 migration must add actor; cols={sorted(cols)}")
        assert "question_id" not in cols, (
            f"v2 migration must drop question_id; cols={sorted(cols)}")
        version = store.conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        # Resolved at the merge gate (#849 over #848). The literal was `== 3`,
        # and #848 re-pinned it to `== 6` when it added v006 — the same
        # staleness one version later, which is what #849 exists to stop. What
        # this test proves is that the ladder RUNS PAST v3, not that the top of
        # the ladder is any particular number, so bind it to SCHEMA_VERSION and
        # keep only the floor the v1->v2 reshape actually needs.
        assert int(version) == SCHEMA_VERSION and int(version) >= 3, (
            "the ordered ladder must continue through v3 and every later migration "
            "after proving the "
            f"v1→v2 reshape; got schema_version {version!r}"
        )
    finally:
        store.close()


def test_v1_to_v2_migration_refuses_a_non_empty_table(tmp_path):
    """Production line: _migrate_v1_to_v2's `if count != 0: raise`.

    A v1 store WITH a review_decision row cannot migrate: question_id has no
    referent so no int→title mapping is possible (R5). The migration must
    refuse loudly. Break by removing the guard — the migration would DROP the
    row silently and open_store would succeed, so the raises assertion fails.

    Assert the precondition (a row exists) at runtime so the check measures a
    real refusal, not a fixture that happens to be empty.
    """
    path = tmp_path / "v1full.sqlite3"
    _make_v1_store(path, with_decision_row=True)

    # Precondition: the v1 table carries a row the migration must refuse to drop.
    pre = sqlite3.connect(str(path))
    try:
        n = pre.execute(
            "SELECT COUNT(*) FROM review_decision").fetchone()[0]
        assert n == 1, f"precondition: need a v1 row to refuse, got {n}"
    finally:
        pre.close()

    with pytest.raises(SchemaVersionError, match="refuse|impossible|question_id"):
        open_store(path, seed_next_id=1)

    # The refusal left the store at v1: the version UPDATE runs only after a
    # successful step, and the open BEGIN transaction rolled back on close.
    post = sqlite3.connect(str(path))
    try:
        version = post.execute(
            "SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        assert int(version) == 1, (
            f"refused migration must leave version at 1, got {version}")
        n = post.execute(
            "SELECT COUNT(*) FROM review_decision").fetchone()[0]
        assert n == 1, "the refused migration must not have dropped the row"
    finally:
        post.close()
