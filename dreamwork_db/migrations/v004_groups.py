"""Version 4 task groups and inert completion-trigger definitions.

The migration is additive: it creates empty tables and does not read or
rewrite any existing task row.  Consequently all 183 currently-open tasks
remain byte-for-byte unchanged when the live store upgrades.

``downgrade`` is the explicit rollback seam.  It succeeds only while the new
tables are empty; once group data exists, deleting it would not be a rollback
but data loss, so downgrade refuses and requires an export/restore instead.
"""

from __future__ import annotations

import sqlite3

from ..core import SchemaMismatch


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE task_group (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        kind        TEXT NOT NULL CHECK (kind IN ('lane','epic','milestone')),
        title       TEXT NOT NULL CHECK (length(trim(title)) > 0),
        description TEXT NOT NULL DEFAULT '',
        created_by  TEXT NOT NULL CHECK (length(trim(created_by)) > 0),
        created_at  TEXT NOT NULL CHECK (length(trim(created_at)) > 0)
    )
    """,
    """
    CREATE TABLE task_group_member (
        group_id INTEGER NOT NULL REFERENCES task_group(id) ON DELETE CASCADE,
        task_id  INTEGER NOT NULL REFERENCES task(id),
        added_by TEXT NOT NULL CHECK (length(trim(added_by)) > 0),
        added_at TEXT NOT NULL CHECK (length(trim(added_at)) > 0),
        PRIMARY KEY (group_id, task_id)
    )
    """,
    """
    CREATE INDEX task_group_member_task ON task_group_member(task_id)
    """,
    """
    CREATE TABLE task_group_trigger (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id      INTEGER NOT NULL REFERENCES task_group(id) ON DELETE CASCADE,
        event         TEXT NOT NULL CHECK (event = 'completed'),
        task_title    TEXT NOT NULL CHECK (length(trim(task_title)) > 0),
        task_priority TEXT REFERENCES priority_band(band),
        task_type     TEXT NOT NULL DEFAULT 'task'
                      CHECK (length(trim(task_type)) > 0),
        created_by    TEXT NOT NULL CHECK (length(trim(created_by)) > 0),
        created_at    TEXT NOT NULL CHECK (length(trim(created_at)) > 0),
        UNIQUE (group_id, event, task_title)
    )
    """,
)


def upgrade(conn: sqlite3.Connection) -> None:
    """Create empty grouping tables without touching the task population."""
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)


def downgrade(conn: sqlite3.Connection) -> None:
    """Remove an unused v4 schema, refusing to discard grouping facts."""
    populations = {
        table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in ("task_group_member", "task_group_trigger", "task_group")
    }
    nonempty = {table: count for table, count in populations.items() if count}
    if nonempty:
        detail = ", ".join(f"{table}={count}" for table, count in nonempty.items())
        raise SchemaMismatch(
            f"cannot downgrade grouping schema without losing data: {detail}"
        )
    conn.execute("DROP TABLE task_group_trigger")
    conn.execute("DROP INDEX task_group_member_task")
    conn.execute("DROP TABLE task_group_member")
    conn.execute("DROP TABLE task_group")
    conn.execute(
        "UPDATE meta SET value = '3' WHERE key = 'schema_version'"
    )
