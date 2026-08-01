"""Version 9 records the principal who bypassed a goal panel."""

from __future__ import annotations

import sqlite3

from ..core import SchemaMismatch


def upgrade(conn: sqlite3.Connection) -> None:
    """Add nullable attribution; v008 claims remain ordinary panel claims."""
    conn.execute("ALTER TABLE goal_claim ADD COLUMN bypassed_by TEXT")


def downgrade(conn: sqlite3.Connection) -> None:
    """Remove attribution only when no bypass history would be discarded."""
    count = int(conn.execute(
        "SELECT COUNT(*) FROM goal_claim WHERE bypassed_by IS NOT NULL"
    ).fetchone()[0])
    if count:
        raise SchemaMismatch(
            "cannot downgrade goal bypass schema without losing data: "
            f"bypassed_by values={count}"
        )
    conn.execute("ALTER TABLE goal_claim DROP COLUMN bypassed_by")
    conn.execute("UPDATE meta SET value = '8' WHERE key = 'schema_version'")
