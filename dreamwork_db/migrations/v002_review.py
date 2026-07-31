"""Version 2 review-decision schema and v1-to-v2 upgrade."""

from __future__ import annotations

import sqlite3

from ..core import SchemaMismatch


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS review_decision (
    artifact       TEXT PRIMARY KEY,
    question_title TEXT NOT NULL,
    decision       TEXT NOT NULL
                   CHECK (decision IN ('pending','accepted','rejected')),
    decided_at     TEXT NOT NULL,
    actor          TEXT NOT NULL
);
"""


def upgrade(conn: sqlite3.Connection) -> None:
    """Advance review_decision: question_id -> question_title + actor."""
    count = conn.execute(
        "SELECT COUNT(*) FROM review_decision"
    ).fetchone()[0]
    if count != 0:
        raise SchemaMismatch(
            f"cannot migrate review_decision v1→v2: {count} row(s) carry a "
            "question_id with no referent (questions are not tasks), so an "
            "int→title mapping is impossible; refuse rather than drop a "
            "review decision silently"
        )
    conn.execute("DROP TABLE review_decision")
    conn.execute(SCHEMA_SQL)
