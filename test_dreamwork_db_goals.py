"""Goal schema and repository contract for task #888."""

from __future__ import annotations

import importlib
import json
import sqlite3

import pytest

from dreamwork_db import Access, SchemaMismatch, ValidationError, open_database
from dreamwork_db.store import dreamwork_store_spec


@pytest.fixture
def store_path(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    with open_database(dreamwork_store_spec(path), access=Access.WRITE) as db:
        with db.transaction():
            pass
    return path


def test_v008_upgrade_builds_the_decided_goal_shape(store_path):
    """Red on migrate.py:SCHEMA_VERSION/MIGRATIONS or v008_goals.upgrade."""
    conn = sqlite3.connect(store_path)
    try:
        version = conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()[0]
        assert version == "8", (
            "migrate.py must advance the ordered ladder through v008_goals; "
            f"stored schema_version was {version!r}"
        )
        assert conn.execute(
            "SELECT kind FROM task_group_kind WHERE kind='goal'"
        ).fetchone() == ("goal",), (
            "v008_goals.upgrade must seed kind='goal' in task_group_kind"
        )
        assert {
            row[1] for row in conn.execute("PRAGMA table_info(task_group)")
        } >= {"goal_state", "goal_rank"}, (
            "v008_goals.upgrade must add task_group.goal_state and goal_rank"
        )
        assert {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        } >= {"goal_state_kind", "goal_claim", "goal_verdict"}, (
            "v008_goals.upgrade must create all three decided goal tables"
        )
        assert conn.execute(
            "SELECT value FROM meta WHERE key='current_goal_id'"
        ).fetchone() == ("",), (
            "v008_goals.upgrade must create the single current-goal pointer"
        )
    finally:
        conn.close()


def test_v008_downgrade_names_every_nonempty_fact_before_discarding(store_path):
    """Red on v008_goals.downgrade's four destructive population counts."""
    v008_goals = importlib.import_module(
        "dreamwork_db.migrations.v008_goals"
    )
    conn = sqlite3.connect(store_path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "INSERT INTO task_group"
        " (kind,title,created_by,created_at,goal_state,goal_rank)"
        " VALUES ('goal','G','test','now','claimed',4)"
    )
    group_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO goal_claim"
        " (group_id,claimed_by,claimed_at,summary,details_sha,outcome,round)"
        " VALUES (?,?,?,?,?,'refuted',1)",
        (group_id, "test", "now", "claim", "details"),
    )
    claim_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO goal_verdict"
        " (claim_id,lens,refuted,findings,corroborated,examined)"
        " VALUES (?,?,?,?,?,?)",
        (claim_id, "criteria", 1, '["gap"]', "[]",
         '{"criteria":1,"members":1}'),
    )
    conn.commit()
    conn.execute("BEGIN")
    try:
        with pytest.raises(SchemaMismatch) as caught:
            v008_goals.downgrade(conn)
        message = str(caught.value)
        for expected in (
            "goal_claim=1", "goal_verdict=1", "goal_state values=1",
            "goal_rank values=1",
        ):
            assert expected in message, (
                "v008_goals.downgrade must name every destructive population; "
                f"missing {expected!r} from {message!r}"
            )
    finally:
        conn.execute("ROLLBACK")
        conn.close()


def test_v008_empty_downgrade_restores_v007_without_loss(store_path):
    """Red on v008_goals.downgrade's successful schema-removal branch."""
    v008_goals = importlib.import_module(
        "dreamwork_db.migrations.v008_goals"
    )
    conn = sqlite3.connect(store_path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("BEGIN")
    v008_goals.downgrade(conn)
    conn.execute("COMMIT")
    try:
        assert conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone() == ("7",), (
            "v008_goals.downgrade must return the watermark to v007"
        )
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(task_group)")
        }
        assert not ({"goal_state", "goal_rank"} & columns), (
            "v008_goals.downgrade must remove both v008 task_group columns"
        )
        assert conn.execute(
            "SELECT name FROM sqlite_master"
            " WHERE name IN ('goal_state_kind','goal_claim','goal_verdict')"
        ).fetchall() == [], (
            "v008_goals.downgrade must remove every v008-only table"
        )
    finally:
        conn.close()
