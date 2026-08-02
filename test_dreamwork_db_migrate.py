"""Compatibility witnesses for the legacy ledger migration ladder."""

from __future__ import annotations

import sqlite3

import pytest

from dreamwork_db import Access, SchemaMismatch, StoreSpec, open_database
from dreamwork_db.migrate import MIGRATIONS, SCHEMA_VERSION, initialize_legacy_store
from dreamwork_db.migrations import v004_groups
from dreamwork_db.posture import (
    POSTURE_AGREE,
    POSTURE_CANNOT_COMPARE,
    POSTURE_DISAGREE,
    PostureRepository,
    resolve_posture_agreement,
)
from ledger_store import SchemaVersionError, SeedError, open_store


# Copied from ledger_store.py at 7e35c6d5^, the commit immediately before the
# v1->v2 migration landed.  Keeping the historical DDL here avoids proving the
# migration against a "v1" fixture manufactured from the code under test.
_HISTORICAL_V1_REVIEW_DECISION_SQL = """
CREATE TABLE review_decision (
    artifact    TEXT PRIMARY KEY,
    question_id INTEGER NOT NULL,
    decision    TEXT NOT NULL
                CHECK (decision IN ('pending','accepted','rejected')),
    decided_at  TEXT NOT NULL
);
"""


def _historical_v1_store(path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO meta(key, value) VALUES ('schema_version', '1')"
        )
        conn.executescript(_HISTORICAL_V1_REVIEW_DECISION_SQL)
        conn.commit()
    finally:
        conn.close()


# Frozen from the live v2 shape at bc7aab6b.  It is deliberately not built
# from v002_review.SCHEMA_SQL or the initializer under test: doing that would
# let a fixture that had already drifted to v3 "prove" a no-op migration.
_FROZEN_V2_SQL = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO meta(key, value) VALUES ('schema_version', '2');
CREATE TABLE priority_band (band TEXT PRIMARY KEY);
INSERT INTO priority_band(band) VALUES ('P1'), ('P2'), ('P3');
CREATE TABLE task (id INTEGER PRIMARY KEY);
CREATE TABLE review_decision (
    artifact       TEXT PRIMARY KEY,
    question_title TEXT NOT NULL,
    decision       TEXT NOT NULL
                   CHECK (decision IN ('pending','accepted','rejected')),
    decided_at     TEXT NOT NULL,
    actor          TEXT NOT NULL
);
"""


def _frozen_v2_store(path, *, with_decision=False) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(_FROZEN_V2_SQL)
        if with_decision:
            conn.execute(
                "INSERT INTO review_decision VALUES "
                "('design.html', 'mutable title', 'accepted', "
                "'2026-08-01T00:00:00Z', 'fixture')"
            )
        conn.commit()
    finally:
        conn.close()


def _tables(conn) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }


def _columns(conn, table) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _assert_frozen_v2_subject(conn) -> None:
    version = conn.execute(
        "SELECT value FROM meta WHERE key='schema_version'"
    ).fetchone()[0]
    tables = _tables(conn)
    assert version == "2", f"fixture must be schema v2, got {version!r}"
    assert not ({"question", "question_message", "review_file", "issue",
                 "review_link"} & tables), (
        "fixture labelled v2 already contains v3 tables; a no-op migration "
        "would make the proof false-green"
    )
    assert _columns(conn, "review_decision") == {
        "artifact", "question_title", "decision", "decided_at", "actor"
    }, "fixture must carry the frozen live v2 review_decision shape"


def test_posture_agreement_names_each_difference_and_both_denominators():
    axes = ("pace", "asking", "delegation", "delivery", "orchestration")
    result = resolve_posture_agreement(
        {"pace": "hot", "asking": "ask", "delegation": 2,
         "delivery": "instant", "orchestration": "hands-on"},
        {"pace": "idle", "asking": "inform", "delegation": "2",
         "delivery": "instant", "orchestration": "hands-on"},
        axes,
    )
    assert result["status"] == POSTURE_DISAGREE
    assert result["axes_compared"] == 5
    assert result["axes_not_compared"] == 0
    assert result["message"] == (
        "DISAGREE: pace file='hot' db='idle'; "
        "asking file='ask' db='inform'; axes compared 5, axes not compared 0"
    )


def test_posture_agreement_never_defaults_an_absent_history_axis():
    result = resolve_posture_agreement(
        {"pace": "idle", "asking": "ask"}, {"pace": "idle"},
        ("pace", "asking"),
    )
    assert result["status"] == POSTURE_CANNOT_COMPARE
    assert result["axes_compared"] == 1
    assert result["axes_not_compared"] == 1
    assert result["uncompared_axes"] == ["asking"]


def test_populated_file_and_empty_history_cannot_compare_on_day_one():
    result = resolve_posture_agreement(
        {"pace": "idle"}, {}, ("pace",),
    )
    assert result["status"] == POSTURE_CANNOT_COMPARE
    assert result["message"] == (
        "CANNOT_COMPARE: posture history is empty; "
        "axes compared 0, axes not compared 1"
    )


def test_history_reconstruction_uses_latest_row_even_when_it_is_a_noop():
    class Result:
        def fetchall(self):
            return [
                ("pace", "idle", "hot"),
                ("pace", "steady", "steady"),
            ]

    class Session:
        def execute(self, sql):
            assert "ORDER BY ordinal" in sql
            return Result()

    current = PostureRepository(Session()).current()
    assert current == {"pace": "steady"}
    result = resolve_posture_agreement(
        {"pace": "hot"}, current, ("pace",),
    )
    assert result["status"] == POSTURE_DISAGREE


def test_history_encoding_distinguishes_unset_from_literal_none():
    class Session:
        rows = None

        def executemany(self, _sql, rows):
            self.rows = rows

    session = Session()
    written = PostureRepository(session).append_changes(
        [("pace", None, "None")], at="now", actor="test"
    )
    assert written == 1
    assert session.rows[0][2:4] == ("\x1eunset", "None")


def _migrate_through_core(path) -> None:
    spec = StoreSpec(path, initializer=initialize_legacy_store)
    with open_database(spec, access=Access.WRITE):
        pass


def test_historical_v1_store_migrates_through_v2_to_current_on_reopen(tmp_path):
    path = tmp_path / "historical-v1.sqlite3"
    _historical_v1_store(path)

    with open_store(path, seed_next_id=41) as store:
        columns = {
            row[1]
            for row in store.conn.execute("PRAGMA table_info(review_decision)")
        }
        assert columns == {
            "artifact", "question_title", "decision", "decided_at", "actor"
        }, (
            "schema_version 1 must run the v1->v2 review migration exactly; "
            f"got columns {sorted(columns)}"
        )
        version = store.conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()[0]
        assert version == str(SCHEMA_VERSION), (
            "v1 migration must reach the current ordered schema version, "
            f"got {version!r}"
        )

    with open_store(path) as reopened:
        version = reopened.conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()[0]
        assert version == str(SCHEMA_VERSION), (
            "reopening a migrated store must be idempotent and remain at "
            f"schema_version {SCHEMA_VERSION}, got {version!r}"
        )


def test_frozen_v2_store_migrates_through_current_and_reports_zero_legacy_rows(
        tmp_path):
    path = tmp_path / "frozen-v2.sqlite3"
    _frozen_v2_store(path)
    before = sqlite3.connect(str(path))
    try:
        _assert_frozen_v2_subject(before)
        examined = before.execute(
            "SELECT COUNT(*) FROM review_decision"
        ).fetchone()[0]
        assert examined == 0, (
            f"migration proof examined {examined} legacy decision row(s); "
            "this increment's live-shape premise is exactly zero"
        )
    finally:
        before.close()

    _migrate_through_core(path)

    after = sqlite3.connect(str(path))
    try:
        version = after.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()[0]
        assert version == str(SCHEMA_VERSION), (
            f"v2->current must record version {SCHEMA_VERSION}, got {version!r}"
        )
        genesis = after.execute(
            "SELECT value FROM meta WHERE key='task_event_genesis'"
        ).fetchone()
        assert genesis is not None and len(genesis[0]) == 64, (
            "v6 must persist a journal-local task-event genesis"
        )
        assert _columns(after, "user_setting") == {"userid", "key", "value"}
        assert after.execute("SELECT COUNT(*) FROM user_setting").fetchone()[0] == 0
        assert _columns(after, "posture_change") == {
            "ordinal", "at", "axis", "old_value", "new_value", "actor",
            "receipt_id",
        }
        assert after.execute(
            "SELECT COUNT(*) FROM posture_change"
        ).fetchone()[0] == 0
        assert _columns(after, "question") == {
            "id", "status", "title", "body_markdown", "priority",
            "asked_at", "asked_precision", "created_by", "created_at",
            "updated_at", "revision",
        }
        assert _columns(after, "question_message") == {
            "id", "question_id", "kind", "author", "body_markdown", "at",
            "action_id",
        }
        assert _columns(after, "review_file") == {
            "id", "path", "content_sha256", "size_bytes", "registered_at",
            "registered_by", "revision",
        }
        assert _columns(after, "issue") == {
            "id", "tracker", "repository", "external_id",
        }
        assert _columns(after, "review_link") == {
            "id", "review_id", "link_kind", "task_id", "issue_id",
            "question_id", "decision", "decided_at", "decided_by",
        }
        assert _columns(after, "task_group") == {
            "id", "kind", "title", "description", "created_by", "created_at",
            "parent_id", "goal_state", "goal_rank",
        }
        assert _columns(after, "goal_state_kind") == {"state"}
        assert _columns(after, "goal_claim") == {
            "id", "group_id", "claimed_by", "claimed_at", "summary",
            "base_sha", "details_sha", "outcome", "round", "bypassed_by",
        }, "goal_claim columns are an explicit public schema contract"
        assert _columns(after, "goal_verdict") == {
            "id", "claim_id", "lens", "refuted", "blocking", "findings",
            "corroborated", "examined",
        }
        assert _columns(after, "task_group_kind") == {"kind"}
        assert _columns(after, "task_group_dependency") == {
            "id", "dependent_group_id", "dependent_task_id",
            "needs_group_id", "needs_task_id", "created_by", "created_at",
        }
        assert _columns(after, "task_group_member") == {
            "group_id", "task_id", "added_by", "added_at",
        }
        assert _columns(after, "task_group_trigger") == {
            "id", "group_id", "event", "task_title", "task_priority",
            "task_type", "created_by", "created_at",
        }
        assert _columns(after, "review_decision") == {
            "artifact", "question_title", "decision", "decided_at", "actor"
        }, "the live pre-watermark /decide compatibility table must remain"
        indexes = {
            row[0]
            for row in after.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }
        assert {"question_message_order", "review_link_task",
                "review_link_issue", "review_link_question"} <= indexes
    finally:
        after.close()


def test_already_v3_fixture_cannot_false_green_the_v2_migration_proof(tmp_path):
    path = tmp_path / "mislabeled.sqlite3"
    _frozen_v2_store(path)
    conn = sqlite3.connect(str(path))
    try:
        # Construct the exact tautology: manufacture the "before" fixture
        # from the v3 DDL under test but leave meta claiming v2.  A no-op
        # migration followed only by post-shape assertions would pass.
        from dreamwork_db.migrations import v003_questions
        for statement in v003_questions.SCHEMA_STATEMENTS:
            conn.execute(statement)
        assert {"question", "question_message", "review_file", "issue",
                "review_link"} <= _tables(conn), (
            "direction-2 precondition: fixture must already have full v3 shape"
        )
        with pytest.raises(AssertionError, match="already contains v3 tables"):
            _assert_frozen_v2_subject(conn)
    finally:
        conn.close()


def test_v3_constraints_bind_typed_links_decisions_and_messages(tmp_path):
    path = tmp_path / "v3-constraints.sqlite3"
    _frozen_v2_store(path)
    _migrate_through_core(path)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        conn.execute(
            "INSERT INTO question(status,title,body_markdown,asked_precision,"
            "created_by,created_at,updated_at) VALUES "
            "('unanswered','Q','body','minute','fixture','now','now')"
        )
        conn.execute(
            "INSERT INTO review_file(path,content_sha256,size_bytes,"
            "registered_at,registered_by) VALUES "
            "('design.html', ?, 10, 'now', 'fixture')",
            ("a" * 64,),
        )
        qid = conn.execute("SELECT id FROM question").fetchone()[0]
        rid = conn.execute("SELECT id FROM review_file").fetchone()[0]

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO review_link(review_id,link_kind) VALUES (?,?)",
                (rid, "related"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO review_link(review_id,link_kind,task_id,decision,"
                "decided_at,decided_by) VALUES (?,?,?,?,?,?)",
                (rid, "related", 1, "accepted", "now", "fixture"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO review_link(review_id,link_kind,question_id,"
                "decision) VALUES (?,?,?,?)",
                (rid, "blocking", qid, "accepted"),
            )
        conn.execute(
            "INSERT INTO review_link(review_id,link_kind,question_id,decision,"
            "decided_at,decided_by) VALUES (?,?,?,?,?,?)",
            (rid, "blocking", qid, "accepted", "now", "fixture"),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO review_link(review_id,link_kind,question_id) "
                "VALUES (?,?,?)",
                (rid, "related", qid),
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO question_message(question_id,kind,author,"
                "body_markdown) VALUES (?,?,?,?)",
                (qid, "note", "fixture", "   "),
            )
    finally:
        conn.close()


def test_v3_refuses_nonempty_legacy_decisions_it_cannot_classify(tmp_path):
    path = tmp_path / "v2-with-decision.sqlite3"
    _frozen_v2_store(path, with_decision=True)
    with pytest.raises(
            SchemaMismatch,
            match=r"1 row.*cannot classify link_kind.*no live import"):
        _migrate_through_core(path)

    conn = sqlite3.connect(str(path))
    try:
        assert conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()[0] == "2"
        assert conn.execute(
            "SELECT COUNT(*) FROM review_decision"
        ).fetchone()[0] == 1
        assert "question" not in _tables(conn), (
            "a refused v3 migration must roll back every new table"
        )
    finally:
        conn.close()


def test_current_store_reopen_is_silent(tmp_path, capsys):
    path = tmp_path / "current.sqlite3"
    _migrate_through_core(path)
    capsys.readouterr()
    _migrate_through_core(path)
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "", (
        "a healthy already-current migration open must emit no warning"
    )


def test_unparseable_schema_version_is_not_reported_as_migrated(tmp_path):
    path = tmp_path / "unknown-version.sqlite3"
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO meta VALUES ('schema_version', 'three-ish')"
        )
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(
            SchemaMismatch, match="could not determine.*schema_version"):
        _migrate_through_core(path)


def test_newer_schema_version_is_refused_with_legacy_public_type(tmp_path):
    path = tmp_path / "future.sqlite3"
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO meta(key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION + 1),),
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(SchemaVersionError) as caught:
        open_store(path, seed_next_id=1)
    assert type(caught.value) is SchemaVersionError, (
        "newer schema_version must retain the exact public exception type "
        f"callers catch, got {type(caught.value)!r}"
    )
    assert isinstance(caught.value, SchemaMismatch), (
        "the retained legacy SchemaVersionError must also cross the new "
        "database API as SchemaMismatch"
    )
    assert (f"schema_version {SCHEMA_VERSION + 1} > supported "
            f"{SCHEMA_VERSION}") in str(caught.value), (
        "newer-version refusal must name stored and supported versions, got "
        f"{str(caught.value)!r}"
    )


def test_new_store_seed_refusal_and_established_reopen_keep_public_type(tmp_path):
    path = tmp_path / "seeded.sqlite3"
    with pytest.raises(SeedError) as caught:
        open_store(path)
    assert type(caught.value) is SeedError, (
        "an unseeded new store must retain the exact SeedError callers catch, "
        f"got {type(caught.value)!r}"
    )

    with open_store(path, seed_next_id=19):
        pass
    with open_store(path) as reopened:
        assert reopened.next_id() == 19, (
            "an established store must reopen without ledger_text or "
            f"seed_next_id; got next id {reopened.next_id()}"
        )


def test_ladder_declares_the_single_ordered_path_to_current():
    versions = [
        (step.source_version, step.target_version) for step in MIGRATIONS
    ]
    step_count = len(versions)
    assert step_count > 0, "migration ladder examined 0 steps; no path exists"
    assert versions[0][0] == 1, (
        f"migration ladder must start at oldest supported schema v1; got {versions!r}"
    )
    sources = [source for source, _target in versions]
    duplicate_sources = sorted({source for source in sources
                                if sources.count(source) > 1})
    assert not duplicate_sources, (
        "migration ladder forks from source version(s) "
        f"{duplicate_sources}; examined {step_count} steps: {versions!r}"
    )
    for index, (source, target) in enumerate(versions, start=1):
        assert target == source + 1, (
            f"migration ladder step {index}/{step_count} is not unit-sized: "
            f"{source}->{target}"
        )
    for index, (previous, following) in enumerate(
            zip(versions, versions[1:]), start=1):
        assert previous[1] == following[0], (
            f"migration ladder has a gap or is out of order after step "
            f"{index}/{step_count}: {previous!r} then {following!r}"
        )
    assert versions[-1][1] == SCHEMA_VERSION, (
        "migration ladder does not terminate at the schema authority's current "
        f"version {SCHEMA_VERSION}; examined {step_count} steps: {versions!r}"
    )
    assert step_count == SCHEMA_VERSION - versions[0][0], (
        f"migration ladder examined {step_count} steps from v{versions[0][0]} "
        f"to v{SCHEMA_VERSION}; expected one step per version"
    )


def test_posture_history_downgrade_refuses_to_discard_a_change(tmp_path):
    from dreamwork_db.migrations import v010_posture_history

    path = tmp_path / "posture-history.sqlite3"
    _migrate_through_core(path)
    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT INTO posture_change"
        " (at,axis,old_value,new_value,actor) VALUES (?,?,?,?,?)",
        ("2026-08-02T00:00:00Z", "pace", "idle", "hot", "test"),
    )
    conn.commit()
    conn.execute("BEGIN")
    try:
        with pytest.raises(
                SchemaMismatch, match=r"posture_change rows=1"):
            v010_posture_history.downgrade(conn)
    finally:
        conn.execute("ROLLBACK")
    try:
        assert conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone() == (str(SCHEMA_VERSION),)
        assert conn.execute(
            "SELECT axis,old_value,new_value FROM posture_change"
        ).fetchall() == [("pace", "idle", "hot")]
    finally:
        conn.close()


def test_empty_v4_group_schema_rolls_back_to_v3_without_touching_tasks(tmp_path):
    path = tmp_path / "rollback-v4.sqlite3"
    _migrate_through_core(path)
    conn = sqlite3.connect(path)
    try:
        before = conn.execute(
            "SELECT id, state, title, body FROM task ORDER BY id"
        ).fetchall()
        v004_groups.downgrade(conn)
        conn.commit()
        assert conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()[0] == "3"
        assert not ({"task_group", "task_group_member", "task_group_trigger"}
                    & _tables(conn))
        after = conn.execute(
            "SELECT id, state, title, body FROM task ORDER BY id"
        ).fetchall()
        assert after == before, "v4 rollback must not rewrite existing tasks"
    finally:
        conn.close()


def test_v4_rollback_refuses_to_discard_grouping_facts(tmp_path):
    path = tmp_path / "nonempty-v4.sqlite3"
    _migrate_through_core(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT INTO task_group"
            " (kind,title,description,created_by,created_at)"
            " VALUES ('epic','kept','','test','now')"
        )
        with pytest.raises(SchemaMismatch, match=r"task_group=1"):
            v004_groups.downgrade(conn)
        assert "task_group" in _tables(conn)
    finally:
        conn.close()
