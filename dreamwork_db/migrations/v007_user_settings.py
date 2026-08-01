"""Version 7 adds validated, non-default user-setting overrides (#584)."""

from __future__ import annotations

import sqlite3


SCHEMA_SQL = """
CREATE TABLE user_setting (
    userid TEXT NOT NULL,
    key    TEXT NOT NULL,
    value  TEXT NOT NULL,
    PRIMARY KEY (userid, key)
)
"""


def upgrade(conn: sqlite3.Connection) -> None:
    """Create the override table; registry metadata remains code-owned."""
    conn.execute(SCHEMA_SQL)
