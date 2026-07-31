"""Compatibility witnesses for the legacy ledger migration ladder."""

from __future__ import annotations

import sqlite3

import pytest

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


def test_historical_v1_store_migrates_to_v2_and_stays_current_on_reopen(tmp_path):
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
        assert version == "2", (
            f"v1->v2 migration must write schema_version 2, got {version!r}"
        )

    with open_store(path) as reopened:
        version = reopened.conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()[0]
        assert version == "2", (
            "reopening a migrated store must be idempotent and remain at "
            f"schema_version 2, got {version!r}"
        )


def test_newer_schema_version_is_refused_with_legacy_public_type(tmp_path):
    path = tmp_path / "future.sqlite3"
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO meta(key, value) VALUES ('schema_version', '3')"
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
    assert "schema_version 3 > supported 2" in str(caught.value), (
        "newer-version refusal must name stored version 3 and supported "
        f"version 2, got {str(caught.value)!r}"
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
