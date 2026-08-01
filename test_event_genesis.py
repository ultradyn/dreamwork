"""Compatibility and false-green proofs for the journal-local event genesis."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sqlite3
from pathlib import Path

import pytest

import ledger_store
from dreamwork_db import SchemaMismatch
from dreamwork_db.migrations import v006_event_genesis


# Frozen independently from schema v1.  The older-schema fixture must never
# call today's genesis_hash to choose its root: that was the original blind
# spot.  Recompute: SHA-256(b"ud-dreamwork.task-ledger1").
V1_GENESIS = (
    "dbb5fcbf8ada5ef7945a7175b9f2c206145f148dc6e4e1afa7567d485096f51d"
)

EVENTS = (
    {"task_id": 848, "at": "2026-07-01T01:00:00Z",
     "cause": "filed_from_command", "from_state": None, "to_state": "open",
     "actor": "old-v1-writer", "receipt_id": None, "detail": "first"},
    {"task_id": 848, "at": "2026-07-01T02:00:00Z",
     "cause": "landed", "from_state": "open", "to_state": "landed",
     "actor": "old-v1-writer", "receipt_id": None, "detail": "second"},
)


def _load_migrate():
    cli = Path(__file__).with_name("ud-dw-tasks-migrate")
    loader = importlib.machinery.SourceFileLoader("ud_dw_genesis_848", str(cli))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _frozen_v5_chain(path: Path) -> int:
    """Write a non-empty schema-v5 chain rooted in the pinned v1 literal."""
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO meta(key, value) VALUES ('schema_version', '5');
        CREATE TABLE task_event (
            ordinal INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL, at TEXT NOT NULL, cause TEXT NOT NULL,
            from_state TEXT, to_state TEXT, actor TEXT NOT NULL,
            receipt_id TEXT, detail TEXT, prev_hash TEXT NOT NULL,
            hash TEXT NOT NULL);
    """)
    prev = V1_GENESIS
    for event in EVENTS:
        digest = ledger_store.hash_event(
            prev, ledger_store.canonical_event_bytes(event)
        )
        conn.execute(
            "INSERT INTO task_event(task_id, at, cause, from_state, to_state,"
            " actor, receipt_id, detail, prev_hash, hash)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (event["task_id"], event["at"], event["cause"],
             event["from_state"], event["to_state"], event["actor"],
             event["receipt_id"], event["detail"], prev, digest),
        )
        prev = digest
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM task_event").fetchone()[0]
    assert count == len(EVENTS) > 0
    assert conn.execute(
        "SELECT value FROM meta WHERE key='task_event_genesis'"
    ).fetchone() is None
    conn.close()
    return count


def _migrate_v5(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute("BEGIN")
        v006_event_genesis.upgrade(conn)
        conn.execute(
            "UPDATE meta SET value = '6' WHERE key = 'schema_version'"
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _store(tmp_path: Path) -> tuple[Path, int]:
    path = tmp_path / "older-v5.sqlite3"
    count = _frozen_v5_chain(path)
    _migrate_v5(path)
    return path, count


def test_chain_built_under_older_schema_keeps_literal_root_and_verifies(tmp_path):
    path, examined = _store(tmp_path)
    conn = sqlite3.connect(path)
    assert conn.execute(
        "SELECT value FROM meta WHERE key='schema_version'"
    ).fetchone()[0] == "6"
    assert conn.execute(
        "SELECT value FROM meta WHERE key='task_event_genesis'"
    ).fetchone()[0] == V1_GENESIS
    assert conn.execute("SELECT COUNT(*) FROM task_event").fetchone()[0] == examined
    conn.close()
    assert examined == 2
    assert _load_migrate().verify_task_event_chain(str(path)) == []


@pytest.mark.parametrize("column", ["detail", "actor", "at"])
def test_tamper_names_the_changed_ordinal(column, tmp_path):
    path, examined = _store(tmp_path)
    assert examined == 2
    conn = sqlite3.connect(path)
    conn.execute(f"UPDATE task_event SET {column} = {column} || ' TAMPERED' "
                 "WHERE ordinal = 2")
    conn.commit()
    conn.close()
    failures = _load_migrate().verify_task_event_chain(str(path))
    assert failures == [
        "task_event ordinal 2: hash does not recompute from prev + canonical bytes"
    ]


def test_forged_self_rooted_chain_is_refused_at_ordinal_one(tmp_path):
    """A self-consistent forged chain cannot nominate ordinal 1 as genesis."""
    path, examined = _store(tmp_path)
    assert examined == 2
    forged_root = "f" * 64
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    prev = forged_root
    for row in conn.execute("SELECT * FROM task_event ORDER BY ordinal").fetchall():
        digest = ledger_store.hash_event(
            prev, ledger_store.canonical_event_bytes(dict(row))
        )
        conn.execute(
            "UPDATE task_event SET prev_hash=?, hash=? WHERE ordinal=?",
            (prev, digest, row["ordinal"]),
        )
        prev = digest
    conn.commit()
    conn.close()

    failures = _load_migrate().verify_task_event_chain(str(path))
    assert failures == [
        f"task_event ordinal 1: prev_hash breaks the chain (expected {V1_GENESIS[:12]})",
        "task_event ordinal 1: hash does not recompute from prev + canonical bytes",
    ]


def test_verifier_refuses_missing_meta_instead_of_trusting_ordinal_one(tmp_path):
    path, examined = _store(tmp_path)
    assert examined == 2
    conn = sqlite3.connect(path)
    conn.execute("DELETE FROM meta WHERE key='task_event_genesis'")
    conn.commit()
    conn.close()
    with pytest.raises(ledger_store.SchemaVersionError,
                       match="refuse to infer genesis from task_event ordinal 1"):
        _load_migrate().verify_task_event_chain(str(path))


def test_v6_migration_refuses_an_arbitrary_self_nominated_root(tmp_path):
    path = tmp_path / "forged-v5.sqlite3"
    examined = _frozen_v5_chain(path)
    assert examined == 2
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    prev = "f" * 64
    for row in conn.execute("SELECT * FROM task_event ORDER BY ordinal").fetchall():
        digest = ledger_store.hash_event(
            prev, ledger_store.canonical_event_bytes(dict(row))
        )
        conn.execute(
            "UPDATE task_event SET prev_hash=?, hash=? WHERE ordinal=?",
            (prev, digest, row["ordinal"]),
        )
        prev = digest
    conn.commit()
    conn.close()
    with pytest.raises(SchemaMismatch, match="not emitted by any supported pre-v6"):
        _migrate_v5(path)
