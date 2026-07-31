"""Ordered, fail-closed migration ladder for the legacy task store."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable

from .core import SchemaMismatch
from .migrations import v001_legacy, v002_review, v003_questions


SCHEMA_VERSION = 3
_COMPOSED_BASE_VERSION = 2


class SchemaVersionError(SchemaMismatch):
    """Legacy name for an unsupported task-store schema version."""


@dataclass(frozen=True, slots=True)
class Migration:
    source_version: int
    target_version: int
    upgrade: Callable[[sqlite3.Connection], None]


MIGRATIONS = (
    Migration(1, 2, v002_review.upgrade),
    Migration(2, 3, v003_questions.upgrade),
)


def _step_from(version: int) -> Migration | None:
    return next(
        (step for step in MIGRATIONS if step.source_version == version), None
    )


def migrate(conn: sqlite3.Connection, stored: int) -> None:
    """Apply every ordered step from *stored* through ``SCHEMA_VERSION``."""
    if stored > SCHEMA_VERSION:
        raise SchemaVersionError(
            f"ledger schema_version {stored} > supported {SCHEMA_VERSION}; "
            "fail-closed: refuse open rather than guess a newer shape"
        )
    version = stored
    while version < SCHEMA_VERSION:
        step = _step_from(version)
        if step is None or step.target_version != version + 1:
            raise SchemaVersionError(
                f"no migration path from schema_version {version} to "
                f"{SCHEMA_VERSION}; fail-closed"
            )
        try:
            step.upgrade(conn)
        except SchemaVersionError:
            raise
        except SchemaMismatch as exc:
            raise SchemaVersionError(str(exc)) from exc
        version = step.target_version
    conn.execute(
        "UPDATE meta SET value = ? WHERE key = 'schema_version'",
        (str(SCHEMA_VERSION),),
    )


def _bootstrap_meta(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT value FROM meta WHERE key = 'schema_version'"
    ).fetchone()
    if row is None:
        # The composed CREATE IF NOT EXISTS baseline is v2.  New stores use
        # the same ordered ladder as old ones rather than a second current-DDL
        # entry point that can drift from migrations.
        migrate(conn, _COMPOSED_BASE_VERSION)
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        return
    try:
        stored = int(row[0])
    except (TypeError, ValueError) as exc:
        raise SchemaVersionError(
            "could not determine ledger schema_version from "
            f"{row[0]!r}; refuse open rather than report it migrated"
        ) from exc
    if stored != SCHEMA_VERSION:
        migrate(conn, stored)


def initialize_legacy_store(conn: sqlite3.Connection) -> None:
    """Apply current schema, version ladder, and unchanged legacy seeds."""
    conn.executescript(v001_legacy.schema_sql(v002_review.SCHEMA_SQL))
    # executescript leaves autocommit; re-enter for bootstrap writes.
    conn.execute("BEGIN")
    try:
        _bootstrap_meta(conn)
        v001_legacy.seed_lookup_tables(conn)
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
