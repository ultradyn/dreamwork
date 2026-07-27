"""SQLite journal store for durable user-event receipts (lane B).

open_journal(path) creates a durable WAL database with synchronous=FULL and a
bounded busy_timeout. Per-connection pragmas are re-applied on every open —
synchronous is not a file property, so a second open must set them again.

This module is new files only; nothing wires it into watch.py yet.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from pathlib import Path
from typing import Union

PathLike = Union[str, os.PathLike]

SCHEMA_VERSION = 1
# Bounded busy timeout in milliseconds. The durability boundary claims a
# finite wait, not "wait forever".
BUSY_TIMEOUT_MS = 5_000

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS receipts (
    receipt_id          TEXT PRIMARY KEY,
    sequence            INTEGER NOT NULL UNIQUE,
    client_action_id    TEXT NOT NULL UNIQUE,
    request_digest      TEXT NOT NULL,
    received_at         TEXT NOT NULL,
    method              TEXT NOT NULL,
    endpoint            TEXT NOT NULL,
    content_type        TEXT NOT NULL,
    exact_payload_bytes BLOB NOT NULL,
    payload_size        INTEGER NOT NULL,
    target_id           TEXT NOT NULL DEFAULT '',
    source_hint         TEXT NOT NULL DEFAULT '',
    redaction_class     TEXT NOT NULL DEFAULT 'default',
    purged_at           TEXT,
    state               TEXT NOT NULL DEFAULT 'received',
    revision            INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS transitions (
    transition_id        TEXT PRIMARY KEY,
    receipt_id           TEXT NOT NULL REFERENCES receipts(receipt_id),
    at                   TEXT NOT NULL,
    from_state           TEXT NOT NULL,
    to_state             TEXT NOT NULL,
    revision             INTEGER NOT NULL,
    consumer_id          TEXT,
    claim_token          TEXT,
    lease_until          TEXT,
    application_adapter  TEXT,
    application_ref      TEXT,
    reason_code          TEXT,
    bounded_detail       TEXT
);

CREATE TABLE IF NOT EXISTS events (
    event_ordinal      INTEGER PRIMARY KEY,
    event_kind         TEXT NOT NULL,
    receipt_id         TEXT,
    at                 TEXT NOT NULL,
    prev_hash          TEXT NOT NULL,
    event_hash         TEXT NOT NULL,
    canonical_payload  BLOB NOT NULL
);
"""


def _ensure_parent_durable(path: Path) -> None:
    """Create the parent directory and best-effort fsync it into the directory entry."""
    parent = path.parent
    if parent == Path("") or parent == Path("."):
        return
    parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(parent), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    """Apply durability-boundary pragmas on this connection.

    journal_mode=WAL is a database property (persists in the file).
    synchronous and busy_timeout are per-connection and must be set every open.
    """
    # journal_mode returns the mode string; must be wal after this.
    conn.execute("PRAGMA journal_mode=WAL")
    # synchronous is per-connection. SQLite 3.53's compile-time default is
    # already FULL (2), so a bare `PRAGMA synchronous=FULL` is a no-op on this
    # build and deleting it leaves the pragma test green — a hollow red. Pin
    # NORMAL first so the FULL line is the one that establishes the durability
    # claim; deleting only that line leaves NORMAL (1) and the B1 red fails.
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")


def _bootstrap_meta(conn: sqlite3.Connection) -> str:
    """Ensure schema_version and journal_id rows exist; return journal_id."""
    row = conn.execute(
        "SELECT value FROM meta WHERE key = 'schema_version'"
    ).fetchone()
    if row is None:
        journal_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('journal_id', ?)",
            (journal_id,),
        )
        conn.commit()
        return journal_id
    stored = int(row[0])
    if stored != SCHEMA_VERSION:
        raise RuntimeError(
            f"journal schema_version {stored} != supported {SCHEMA_VERSION}"
        )
    jid = conn.execute(
        "SELECT value FROM meta WHERE key = 'journal_id'"
    ).fetchone()
    if jid is None:
        raise RuntimeError("journal meta missing journal_id")
    return jid[0]


class Journal:
    """A live connection to one target's user-event journal database."""

    def __init__(self, path: Path, conn: sqlite3.Connection, journal_id: str):
        self.path = path
        self.conn = conn
        self.journal_id = journal_id

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Journal":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def read_pragmas(self) -> dict:
        """Return journal_mode, synchronous, busy_timeout from THIS connection."""
        mode = self.conn.execute("PRAGMA journal_mode").fetchone()[0]
        sync = self.conn.execute("PRAGMA synchronous").fetchone()[0]
        busy = self.conn.execute("PRAGMA busy_timeout").fetchone()[0]
        return {
            "journal_mode": str(mode).lower(),
            "synchronous": int(sync),
            "busy_timeout": int(busy),
        }


def open_journal(path: PathLike) -> Journal:
    """Open (or create) the durable journal at path.

    Creates the parent directory durably, applies WAL + FULL + busy_timeout,
    installs the schema, and ensures a schema_version row.
    """
    p = Path(path)
    _ensure_parent_durable(p)
    # Default isolation: DML needs explicit commit. PRAGMA journal_mode=WAL
    # must run outside a multi-statement transaction.
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    try:
        _apply_pragmas(conn)
        # executescript issues its own COMMIT first; that is fine here —
        # pragmas are already applied and schema DDL is idempotent.
        conn.executescript(_SCHEMA_SQL)
        journal_id = _bootstrap_meta(conn)
    except Exception:
        conn.close()
        raise
    return Journal(p, conn, journal_id)
