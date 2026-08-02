"""Version 1 task-ledger baseline and unchanged lookup seeds."""

from __future__ import annotations

import sqlite3


TASK_STATES = ("pending", "in_progress", "landed", "dropped")
ENTRY_STATES = ("open", "landed")
ORIGINS = ("human", "loop", "unknown")
PRIORITY_BANDS = ("P0", "P1", "P2", "P3")
REVIEW_DECISIONS = ("pending", "accepted", "rejected")
TASK_CAUSES = (
    "filed_from_command",
    "next_up_set",
    "next_up_cleared",
    "filed_from_leftover",
    "filed_from_idea",
    "filed_from_brainstorm",
    "filed_from_split",
    "started_from_backlog",
    "landed",
    "claimed_by_agent",
    "released",
    "lease_expired",
    "hold_set",
    "hold_cleared",
    "reprioritised",
    "blocked",
    "unblocked",
    "superseded",
    "dropped",
    "feasibility_noted",
    "goal_realigned",
    "reconciled",
    "ingested_upstream",
    "migration_git",
)


SCHEMA_BEFORE_REVIEW = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS priority_band (
    band TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS task_state_kind (
    state TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS task_cause (
    cause TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS task_type (
    type TEXT PRIMARY KEY
);

-- The flat entity: one row per permanent id, every Markdown column on it.
-- AUTOINCREMENT is load-bearing (R1): without it a deleted high-water id
-- can be reissued, which reuses a permanent id. No entry table, no
-- task_by_entry — post-#353 every entry IS one task, so the split joined
-- 1:1 forever and modelled nothing (his flatten ruling, 2026-07-29 15:59).
-- blocked_on stays verbatim prose, never an edge (#346 S1: edges live in
-- depends); body is where notes/updates accumulate across a task's life.
CREATE TABLE IF NOT EXISTS task (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    state               TEXT    NOT NULL CHECK (state IN ('open','landed')),
    title               TEXT    NOT NULL,
    body                TEXT    NOT NULL,
    priority            TEXT    REFERENCES priority_band(band),
    priority_uncertain  INTEGER NOT NULL DEFAULT 0
                        CHECK (priority_uncertain IN (0, 1)),
    type                TEXT    REFERENCES task_type(type),
    origin              TEXT    CHECK (origin IS NULL
                                  OR origin IN ('human','loop','unknown')),
    blocked_on          TEXT,
    body_digest         TEXT,
    source_line         INTEGER
);

CREATE TABLE IF NOT EXISTS related (
    a INTEGER NOT NULL REFERENCES task(id),
    b INTEGER NOT NULL REFERENCES task(id),
    PRIMARY KEY (a, b),
    CHECK (a < b)
);

CREATE TABLE IF NOT EXISTS depends (
    task  INTEGER NOT NULL REFERENCES task(id),
    needs INTEGER NOT NULL REFERENCES task(id),
    PRIMARY KEY (task, needs),
    CHECK (task <> needs)
);
CREATE INDEX IF NOT EXISTS depends_by_needs ON depends(needs);
"""


SCHEMA_AFTER_REVIEW = """
-- Append-only transition log. Own ordinal, distinct from the journal's.
-- receipt_id is free TEXT here (the receipt table may live in the same file
-- later); no FK until the journal tables are co-resident. Purge never reaches
-- this table (#264).
CREATE TABLE IF NOT EXISTS task_event (
    ordinal    INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    INTEGER NOT NULL REFERENCES task(id),
    at         TEXT    NOT NULL,
    cause      TEXT    NOT NULL REFERENCES task_cause(cause),
    from_state TEXT,
    to_state   TEXT,
    actor      TEXT    NOT NULL,
    receipt_id TEXT,
    detail     TEXT,
    prev_hash  TEXT    NOT NULL,
    hash       TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS task_event_by_task ON task_event(task_id, ordinal);
CREATE INDEX IF NOT EXISTS task_event_by_cause ON task_event(cause, ordinal);

-- Materialised only because a claim needs a row to CAS against (#264).
CREATE TABLE IF NOT EXISTS task_state (
    task_id     INTEGER PRIMARY KEY REFERENCES task(id),
    state       TEXT    NOT NULL REFERENCES task_state_kind(state),
    hold        INTEGER NOT NULL DEFAULT 0,
    hold_reason TEXT,
    owner       TEXT,
    claim_token TEXT,
    lease_until TEXT,
    revision    INTEGER NOT NULL DEFAULT 1,
    at_ordinal  INTEGER NOT NULL REFERENCES task_event(ordinal)
);
"""


def schema_sql(review_decision_sql: str) -> str:
    """Compose the legacy schema with the selected versioned review table."""
    return SCHEMA_BEFORE_REVIEW + review_decision_sql + SCHEMA_AFTER_REVIEW


def seed_lookup_tables(conn: sqlite3.Connection) -> None:
    """Populate the legacy closed lookup tables idempotently."""
    for band in PRIORITY_BANDS:
        conn.execute(
            "INSERT OR IGNORE INTO priority_band(band) VALUES (?)", (band,)
        )
    for state in TASK_STATES:
        conn.execute(
            "INSERT OR IGNORE INTO task_state_kind(state) VALUES (?)", (state,)
        )
    for cause in TASK_CAUSES:
        conn.execute(
            "INSERT OR IGNORE INTO task_cause(cause) VALUES (?)", (cause,)
        )
