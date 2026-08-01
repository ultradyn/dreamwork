"""SQLite task ledger store — FLAT schema + seeded id sequence (#294 inc 2).

One `task` table carries every column the Markdown entry carries — increment
1's entry/task split (`50f4933`) modelled combined entries, and #353 split
every one of them, so the join joined each task to exactly one entry forever.
The human ruled FLATTEN 2026-07-29 15:59 (rebuilding the lost, red-proved
`5c5e534`): no `entry` table, no `task_by_entry` index. The #346 S1 relations
(`related` n:n, `depends` directed) and the #264 transition boundary
(`task_event`, `task_state`) are unchanged — they bound task ids already.

The id sequence lives in the store (AUTOINCREMENT, R1). Seed is derived from
the Markdown ledger through lint's own parser — never a second regex — and
verified before it is written.

Machine-local, stdlib sqlite3 only (C1). No cutover, no import, no write verbs:
opening, creating, seeding, and proving the sequence is this module's whole job.

Prior art reused from user_events/sqlite.py (not reinvented):
- open(path) that creates parent, applies WAL + synchronous=FULL + busy_timeout
  on every open (synchronous is per-connection, not a file property)
- PRAGMA foreign_keys=ON set in the adapter and asserted by a test
- closed reason / state sets as module-level tuples a parser can read
- VersionMismatchError-style fail-closed open on a bad schema_version
- schema applied via executescript of one SQL string
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from dreamwork_db import Access, StoreSpec
from dreamwork_db import core as db_core
from dreamwork_db.migrate import (
    SCHEMA_VERSION,
    SchemaVersionError,
    initialize_legacy_store,
)
from dreamwork_db.migrations.v001_legacy import (
    ENTRY_STATES,
    ORIGINS,
    PRIORITY_BANDS,
    REVIEW_DECISIONS,
    TASK_CAUSES,
    TASK_STATES,
)
from dreamwork_db.migrations.v006_event_genesis import (
    LEGACY_GENESIS_HASH,
    META_KEY as EVENT_GENESIS_META_KEY,
)

PathLike = Union[str, os.PathLike]

BUSY_TIMEOUT_MS = 5_000
# Domain tag for the task_event hash chain (#264): distinct from the journal's
# so a task event can never verify as a receipt event.
DOMAIN_TAG = b"ud-dreamwork.task-event.v1"


class SeedError(RuntimeError):
    """The id sequence cannot be established safely.

    A store that opens with a *wrong* sequence is worse than one that refuses
    to open (R1): ids are permanent and never reused. Callers see this class —
    not a bare ValueError — so mixed-version / migration tooling can treat a
    seed failure as a hard stop rather than a malformed field.
    """


# ---------------------------------------------------------------------------
# Hash-chain primitives for task_event (#264 boundary, #294 inc 9).
#
# The task_event table is an append-only transition log whose integrity rests
# on a hash chain: each row's hash covers the previous row's hash, so a
# mutation to any row breaks the head. These primitives are the ONE copy of
# that construction — both the migration script (synthetic migration:git
# events) and the live write verbs (ledger_write.file_task / land_task) chain
# through them, and verify_task_event_chain recomputes from genesis over them.
# They live here because DOMAIN_TAG and SCHEMA_VERSION — the chain's only
# external inputs — already do.
# ---------------------------------------------------------------------------

def _length_framed(*parts) -> bytes:
    """8-byte big-endian length prefix per part (journal contract; matches
    user_events.digest.length_framed so the framing cannot drift)."""
    out = bytearray()
    for part in parts:
        data = part.encode("utf-8") if isinstance(part, str) else bytes(part)
        out.extend(len(data).to_bytes(8, "big"))
        out.extend(data)
    return bytes(out)


def genesis_hash(conn) -> str:
    """Return this journal's persisted task-event chain seed.

    The seed is data, not a function of the moving schema version.  Missing or
    malformed metadata fails closed: deriving it from ordinal 1 here would let
    a forged chain nominate its own root and verify forever.
    """
    row = conn.execute(
        "SELECT value FROM meta WHERE key = ?", (EVENT_GENESIS_META_KEY,)
    ).fetchone()
    value = None if row is None else row[0]
    if (not isinstance(value, str) or len(value) != 64
            or any(ch not in "0123456789abcdef" for ch in value)):
        raise SchemaVersionError(
            f"ledger meta {EVENT_GENESIS_META_KEY!r} is missing or invalid; "
            "refuse to infer genesis from task_event ordinal 1"
        )
    return value


def canonical_event_bytes(e: dict) -> bytes:
    """``length_framed(canonical_event)`` — the stable fields, never the hash."""
    return _length_framed(str(e["task_id"]), e["at"], e["cause"],
                          e["from_state"] or "", e["to_state"] or "",
                          e["actor"], e.get("detail") or "")


def hash_event(prev_hash: str, canonical: bytes) -> str:
    """H_i = SHA-256(domain_tag || H_(i-1) || length_framed(canonical_event_i)).

    DOMAIN_TAG is this table's own tag; prev_hash is load-bearing (B3): drop
    it and an earlier mutation stops moving the head.
    """
    return hashlib.sha256(
        DOMAIN_TAG + prev_hash.encode("ascii") + canonical).hexdigest()


def chain_events(events: list, genesis: str) -> list:
    """Order events deterministically and append prev_hash/hash per the chain.

    Order is ``(at, task_id, rank)`` with first-sight (from_state is None)
    before landed, so the same history always produces the same chain. Live
    write verbs append one event at a time (ordinal order); this bulk helper
    serves the migration import, which chains many events at once.
    """
    ordered = sorted(events, key=lambda e: (
        e["at"], e["task_id"], 0 if e["from_state"] is None else 1))
    prev, chained = genesis, []
    for e in ordered:
        h = hash_event(prev, canonical_event_bytes(e))
        chained.append({**e, "prev_hash": prev, "hash": h})
        prev = h
    return chained


def last_event_hash(conn) -> str:
    """The hash of the last ``task_event`` row by ordinal, or genesis if none.

    A live transition (and a replay) append one event at the end (ordinal is
    AUTOINCREMENT), so the previous hash in the chain is always the current
    last row's hash. Public so the live writer and the replay tool share ONE
    applier rather than restating the "chain from the last row" mechanic
    (#352 — the #460 gap-fill: this and :func:`append_chained_event` are the
    single apply primitive both ride).
    """
    row = conn.execute(
        "SELECT hash FROM task_event ORDER BY ordinal DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else genesis_hash(conn)


def append_chained_event(
    conn, *, task_id, at, cause, from_state, to_state, actor,
    receipt_id=None, detail="",
) -> None:
    """INSERT one ``task_event`` row, chained from the current last event.

    The row's ``prev_hash`` is the last event's hash by ordinal; its ``hash``
    covers the canonical bytes plus that prev. This is the live counterpart of
    :func:`chain_events`'s bulk loop — one event at a time, in real time — and
    the ONE apply primitive the live write verbs (:mod:`ledger_write`) and the
    journal replay tool (``dev/replay_events.py``) both ride, so the chain
    construction has one definition (#352 / #460). The caller holds the
    transaction (``BEGIN IMMEDIATE … COMMIT``); this function only appends.
    """
    event = {"task_id": task_id, "at": at, "cause": cause,
             "from_state": from_state, "to_state": to_state,
             "actor": actor, "detail": detail}
    prev = last_event_hash(conn)
    h = hash_event(prev, canonical_event_bytes(event))
    conn.execute(
        "INSERT INTO task_event(task_id, at, cause, from_state, to_state,"
        " actor, receipt_id, detail, prev_hash, hash)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (task_id, at, cause, from_state, to_state, actor, receipt_id, detail,
         prev, h))


# ---------------------------------------------------------------------------
# Seed derivation — one truth, lint's parser
# ---------------------------------------------------------------------------

def derive_next_id(ledger_text: str) -> int:
    """Return the next permanent id the store must hand out.

    Derives MAX(id)+1 over open ∪ landed through ``lint.load_watch()`` →
    ``parse_ledger`` — the production reader, never a second regex. A second
    parser would be a second truth, which is exactly the dual-write R2 refused.

    Raises SeedError when the seed cannot be established:
    - watch.py unimportable
    - no ids parse (empty / unparseable ledger)
    - header ``Next id`` present and disagrees with MAX(id)+1
    """
    # Import here so a missing lint mid-edit is a SeedError, not an import
    # failure of this module for unrelated callers.
    import lint  # noqa: WPS — skill-root module

    watch = lint.load_watch()
    if watch is None:
        raise SeedError(
            "cannot derive next id: lint.load_watch() returned None "
            "(watch.py unimportable); refuse rather than invent a sequence"
        )
    open_ids, landed_ids = watch.parse_ledger(ledger_text)
    # parse_ledger returns strings; normalise once at the seam.
    all_ids = {int(x) for x in open_ids} | {int(x) for x in landed_ids}
    if not all_ids:
        raise SeedError(
            "cannot derive next id: parse_ledger returned no ids "
            "(empty or unparseable ledger); refuse rather than seed at 1"
        )
    derived = max(all_ids) + 1

    # Header agreement is the F2 invariant: Next id must equal MAX(id)+1.
    # Use lint's own NEXT_ID pattern so the header has one reader, not two.
    header = lint.NEXT_ID.search(ledger_text)
    if header is not None:
        header_next = int(header.group(1))
        if header_next != derived:
            raise SeedError(
                f"cannot establish seed: header Next id is {header_next} but "
                f"MAX(id)+1 over parse_ledger is {derived}; a drifted header "
                "must stop the migration, not paper over it"
            )
    return derived


def derive_next_id_from_path(ledger_path: PathLike) -> int:
    """Read a ledger file and derive the next id. Path convenience wrapper."""
    path = Path(ledger_path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SeedError(
            f"cannot derive next id: failed to read {path}: {exc}"
        ) from exc
    return derive_next_id(text)


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

@dataclass
class LedgerStore:
    """A live connection to one target's task ledger database."""

    path: Path
    conn: sqlite3.Connection

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "LedgerStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def read_pragmas(self) -> dict:
        """Return journal_mode, synchronous, busy_timeout, foreign_keys."""
        mode = self.conn.execute("PRAGMA journal_mode").fetchone()[0]
        sync = self.conn.execute("PRAGMA synchronous").fetchone()[0]
        busy = self.conn.execute("PRAGMA busy_timeout").fetchone()[0]
        fks = self.conn.execute("PRAGMA foreign_keys").fetchone()[0]
        return {
            "journal_mode": str(mode).lower(),
            "synchronous": int(sync),
            "busy_timeout": int(busy),
            "foreign_keys": int(fks),
        }

    def sequence_high_water(self, table: str = "task") -> Optional[int]:
        """Return sqlite_sequence.seq for *table*, or None if unseeded."""
        row = self.conn.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = ?", (table,)
        ).fetchone()
        if row is None:
            return None
        return int(row[0])

    def next_id(self, table: str = "task") -> int:
        """The next id AUTOINCREMENT would hand out for *table*.

        Equals high_water + 1 when seeded; raises SeedError when the sequence
        has never been established (a store that invents 1 would collide with
        imported permanent ids after cutover).
        """
        hw = self.sequence_high_water(table)
        if hw is None:
            raise SeedError(
                f"id sequence for {table!r} is not established; "
                "seed it from the verified Markdown next id before allocating"
            )
        return hw + 1

    def seed_sequence(self, next_id: int, table: str = "task") -> None:
        """Seed AUTOINCREMENT so the next allocated id is *next_id*.

        Writes ``sqlite_sequence.seq = next_id - 1``. Refuses a non-positive
        next_id, and refuses to *lower* an already-established high-water mark
        (R1: a bad import must not be able to reset the sequence).
        """
        if not isinstance(next_id, int) or isinstance(next_id, bool):
            raise SeedError(
                f"next_id must be a positive int, got {type(next_id).__name__}"
            )
        if next_id < 1:
            raise SeedError(
                f"next_id must be >= 1, got {next_id}; refuse rather than "
                "seed a sequence that collides with itself"
            )
        # Production line the red targets: the refuse-to-lower guard below.
        current = self.sequence_high_water(table)
        new_seq = next_id - 1
        if current is not None and new_seq < current:
            raise SeedError(
                f"refusing to lower {table!r} sequence from {current} to "
                f"{new_seq}: ids are permanent and a bad seed must not reset them"
            )
        if current is None:
            # sqlite_sequence only exists after the first AUTOINCREMENT use on
            # a table; force it into existence with a no-op shape by inserting
            # the row directly. SQLite permits this for seeded sequences.
            self.conn.execute(
                "INSERT INTO sqlite_sequence(name, seq) VALUES (?, ?)",
                (table, new_seq),
            )
        else:
            self.conn.execute(
                "UPDATE sqlite_sequence SET seq = ? WHERE name = ?",
                (new_seq, table),
            )
        self.conn.commit()
        # Verify, never trust: the written high-water must yield next_id.
        got = self.next_id(table)
        if got != next_id:
            raise SeedError(
                f"seed verification failed: wanted next_id={next_id}, "
                f"store reports {got}"
            )

    def seed_from_ledger(self, ledger_text: str) -> int:
        """Derive next id from the Markdown ledger and seed the sequence.

        Returns the seeded next_id. Raises SeedError on any failure to
        establish a verified seed.
        """
        next_id = derive_next_id(ledger_text)
        self.seed_sequence(next_id)
        return next_id

    def tables(self) -> set[str]:
        """User tables present in this store (for schema-presence tests)."""
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return {r[0] for r in rows}


def open_store(
    path: PathLike,
    *,
    seed_next_id: Optional[int] = None,
    ledger_text: Optional[str] = None,
) -> LedgerStore:
    """Open or create the ledger store at *path*.

    Creates the schema on first open. The id sequence is seeded when:
    - ``ledger_text`` is given → derive + seed via ``seed_from_ledger``
    - ``seed_next_id`` is given → seed that value (caller already verified)
    - neither, and the sequence is already established → leave it
    - neither, and the sequence is unestablished → **SeedError** (fail loud)

    A store that opens with a wrong sequence is worse than one that refuses
    to open, so an unseeded first open is refused rather than defaulting to 1.
    """
    path = Path(path)
    spec = StoreSpec(
        path=path,
        initializer=initialize_legacy_store,
        busy_timeout_ms=BUSY_TIMEOUT_MS,
    )
    conn = db_core._connect(spec, Access.WRITE)

    store = LedgerStore(path=path, conn=conn)
    try:
        if ledger_text is not None:
            store.seed_from_ledger(ledger_text)
        elif seed_next_id is not None:
            store.seed_sequence(seed_next_id)
        elif store.sequence_high_water("task") is None:
            # Production line: refuse unseeded open.
            store.close()
            raise SeedError(
                "refusing to open an unseeded ledger store: pass ledger_text "
                "or seed_next_id so the id sequence is verified before any "
                "allocation (R1 — a wrong sequence is worse than a refusal)"
            )
    except SeedError:
        raise
    except Exception:
        store.close()
        raise
    return store
