"""Version 3 dark question, review, issue, and typed-link schema."""

from __future__ import annotations

import sqlite3

from ..core import SchemaMismatch


# Keep statements separate: sqlite3.executescript() commits implicitly, while
# the migration ladder owns one atomic transaction around every version step.
SCHEMA_STATEMENTS = (
    """
    CREATE TABLE question (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        status          TEXT NOT NULL CHECK (status IN
                        ('unanswered','answered_pending_fold','answered')),
        title           TEXT NOT NULL,
        body_markdown   TEXT NOT NULL,
        priority        TEXT REFERENCES priority_band(band),
        asked_at        TEXT,
        asked_precision TEXT NOT NULL CHECK (asked_precision IN
                        ('unknown','day','minute','second')),
        created_by      TEXT NOT NULL,
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL,
        revision        INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0)
    )
    """,
    """
    CREATE TABLE question_message (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id   INTEGER NOT NULL REFERENCES question(id),
        kind          TEXT NOT NULL CHECK (kind IN ('answer','note')),
        author        TEXT NOT NULL,
        body_markdown TEXT NOT NULL,
        at            TEXT,
        action_id     TEXT UNIQUE,
        CHECK (length(trim(body_markdown)) > 0)
    )
    """,
    """
    CREATE INDEX question_message_order
        ON question_message(question_id, id)
    """,
    """
    CREATE TABLE review_file (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        path           TEXT NOT NULL UNIQUE,
        content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
        size_bytes     INTEGER NOT NULL CHECK (size_bytes >= 0),
        registered_at  TEXT NOT NULL,
        registered_by  TEXT NOT NULL,
        revision       INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0)
    )
    """,
    """
    CREATE TABLE issue (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        tracker     TEXT NOT NULL,
        repository  TEXT NOT NULL,
        external_id TEXT NOT NULL,
        UNIQUE (tracker, repository, external_id)
    )
    """,
    """
    CREATE TABLE review_link (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        review_id   INTEGER NOT NULL REFERENCES review_file(id),
        link_kind   TEXT NOT NULL CHECK (link_kind IN ('related','blocking')),
        task_id     INTEGER REFERENCES task(id),
        issue_id    INTEGER REFERENCES issue(id),
        question_id INTEGER REFERENCES question(id),
        decision    TEXT CHECK (decision IN ('pending','accepted','rejected')),
        decided_at  TEXT,
        decided_by  TEXT,
        CHECK ((task_id IS NOT NULL) + (issue_id IS NOT NULL) +
               (question_id IS NOT NULL) = 1),
        CHECK (decision IS NULL OR question_id IS NOT NULL),
        CHECK ((decision IS NULL AND decided_at IS NULL AND decided_by IS NULL)
            OR (decision IS NOT NULL AND decided_at IS NOT NULL
                                     AND decided_by IS NOT NULL))
    )
    """,
    """
    CREATE UNIQUE INDEX review_link_task
        ON review_link(review_id, task_id) WHERE task_id IS NOT NULL
    """,
    """
    CREATE UNIQUE INDEX review_link_issue
        ON review_link(review_id, issue_id) WHERE issue_id IS NOT NULL
    """,
    """
    CREATE UNIQUE INDEX review_link_question
        ON review_link(review_id, question_id) WHERE question_id IS NOT NULL
    """,
)


def upgrade(conn: sqlite3.Connection) -> None:
    """Add the dark v3 schema while the live decision table is empty.

    The legacy table remains temporarily because pre-watermark dashboard and
    CLI adapters still use its exact shape.  A non-empty table cannot be
    classified without the later live import: its mutable titles are not
    stable ids and it carries no related/blocking link kind.
    """
    count = conn.execute(
        "SELECT COUNT(*) FROM review_decision"
    ).fetchone()[0]
    if count != 0:
        noun = "row" if count == 1 else "rows"
        raise SchemaMismatch(
            f"cannot migrate review_decision v2→v3: {count} {noun}; cannot "
            "classify link_kind or resolve mutable artifact/question titles "
            "to stable ids with no live import; refuse rather than fabricate "
            "a typed link"
        )
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)
