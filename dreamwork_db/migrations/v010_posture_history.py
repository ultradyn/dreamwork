"""Version 10 adds append-only posture change history (#866)."""

from __future__ import annotations

import sqlite3


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
