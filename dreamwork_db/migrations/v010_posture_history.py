"""Version 10 adds append-only posture change history (#866)."""

from __future__ import annotations

import sqlite3

from ..core import SchemaMismatch


TABLE_SQL = """CREATE TABLE posture_change (
    ordinal    INTEGER PRIMARY KEY AUTOINCREMENT,
    at         TEXT NOT NULL,
    axis       TEXT NOT NULL,
    old_value  TEXT NOT NULL,
    new_value  TEXT NOT NULL,
    actor      TEXT NOT NULL,
    receipt_id TEXT,
    CHECK (old_value <> new_value)
)"""

INDEX_SQL = """CREATE INDEX posture_change_by_axis
    ON posture_change(axis, ordinal)"""


def upgrade(conn: sqlite3.Connection) -> None:
    """Create a history table independent of task lifecycle events."""
    conn.execute(TABLE_SQL)
    conn.execute(INDEX_SQL)


def downgrade(conn: sqlite3.Connection) -> None:
    """Remove only an empty history table; recorded posture is irreversible."""
    count = int(conn.execute(
        "SELECT COUNT(*) FROM posture_change"
    ).fetchone()[0])
    if count:
        raise SchemaMismatch(
            "cannot downgrade posture history without losing data: "
            f"posture_change rows={count}"
        )
    conn.execute("DROP TABLE posture_change")
    conn.execute("UPDATE meta SET value = '9' WHERE key = 'schema_version'")
