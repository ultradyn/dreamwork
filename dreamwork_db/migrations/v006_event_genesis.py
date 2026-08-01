"""Version 6 makes the task-event genesis a journal-local property.

Existing non-empty journals keep the root already recorded on ordinal 1.
That is a trust-on-first-use migration: it preserves history byte-for-byte and
does not re-chain it.  Empty journals persist the frozen v1 format root, which
keeps replay deterministic while making any future re-seed explicit data.
"""

from __future__ import annotations

import sqlite3
import hashlib

from ..core import SchemaMismatch


META_KEY = "task_event_genesis"

# The live journal began under schema v1.  This literal is the historical
# chain-format root, deliberately independent of the moving schema version.
LEGACY_GENESIS_HASH = (
    "dbb5fcbf8ada5ef7945a7175b9f2c206145f148dc6e4e1afa7567d485096f51d"
)

# Before v6, genesis was SHA-256(journal id || schema version).  A non-empty
# pre-v6 journal can therefore have only one of these roots.  This is not an
# external signature, but it prevents the migration blessing an arbitrary
# first-row value as though it were a root emitted by historical code.
HISTORICAL_GENESIS_HASHES = frozenset(
    hashlib.sha256(f"ud-dreamwork.task-ledger{version}".encode()).hexdigest()
    for version in range(1, 6)
)


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def upgrade(conn: sqlite3.Connection) -> None:
    """Pin the existing root, or create a journal-specific root if empty."""
    existing = conn.execute(
        "SELECT value FROM meta WHERE key = ?", (META_KEY,)
    ).fetchone()
    if existing is not None:
        if not _is_sha256(existing[0]):
            raise SchemaMismatch(
                f"cannot migrate task-event genesis: existing meta key "
                f"{META_KEY!r} is not a lowercase SHA-256 digest"
            )
        # A v6 store may be downgraded through an unrelated later schema and
        # then replay this step.  The chain root survives that downgrade and
        # must remain byte-identical rather than being regenerated.
        return

    first = conn.execute(
        "SELECT prev_hash FROM task_event ORDER BY ordinal LIMIT 1"
    ).fetchone()
    genesis = first[0] if first is not None else LEGACY_GENESIS_HASH
    if not _is_sha256(genesis):
        raise SchemaMismatch(
            "cannot migrate task-event genesis: ordinal 1 prev_hash is not "
            "a lowercase SHA-256 digest"
        )
    if first is not None and genesis not in HISTORICAL_GENESIS_HASHES:
        raise SchemaMismatch(
            "cannot migrate task-event genesis: ordinal 1 prev_hash was not "
            "emitted by any supported pre-v6 schema; refuse to bless an "
            "unbound row value as the journal root"
        )
    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?)", (META_KEY, genesis)
    )
