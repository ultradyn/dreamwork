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

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

PathLike = Union[str, os.PathLike]

# Closed sets — CHECK constraints for values closed by definition (#346 S4).
# Lookup tables for vocabularies that grow (type, cause).
TASK_STATES = ("pending", "in_progress", "landed", "dropped")
ENTRY_STATES = ("open", "landed")
ORIGINS = ("human", "loop", "unknown")
PRIORITY_BANDS = ("P0", "P1", "P2", "P3")
REVIEW_DECISIONS = ("pending", "accepted", "rejected")
# #264's enumerated causes (lookup, not CHECK — the set grows).
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
    "superseded",
    "dropped",
    "feasibility_noted",
    "goal_realigned",
    "reconciled",
    "ingested_upstream",
    "migration_git",  # first-sight synthetic events (R3)
)

SCHEMA_VERSION = 1
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


class SchemaVersionError(RuntimeError):
    """Store schema_version this process cannot understand. Fail-closed."""


# ---------------------------------------------------------------------------
# Schema — flat entity (#346 post-#353, ruled 2026-07-29) + boundary (#264)
# ---------------------------------------------------------------------------
# task.id is INTEGER PRIMARY KEY AUTOINCREMENT so the sequence lives in the
# store (R1). Explicit-id INSERTs (import) and auto-allocated ids share one
# high-water mark via sqlite_sequence; deleting the highest row does NOT
# reissue that id — which is the property the tests prove rather than assume.

_SCHEMA_SQL = """
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

CREATE TABLE IF NOT EXISTS review_decision (
    artifact    TEXT PRIMARY KEY,
    question_id INTEGER NOT NULL,
    decision    TEXT NOT NULL
                CHECK (decision IN ('pending','accepted','rejected')),
    decided_at  TEXT NOT NULL
);

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


def _ensure_parent_durable(path: Path) -> None:
    """Create the parent directory and best-effort fsync it into the directory entry."""
    parent = path.parent
    if parent == Path("") or parent == Path("."):
        return
    parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(parent), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    """Apply durability + FK pragmas on this connection.

    journal_mode=WAL is a database property. synchronous, busy_timeout and
    foreign_keys are per-connection and must be set every open. foreign_keys
    is OFF by default in SQLite — leaving it off would make every REFERENCES
    a comment (#264 footgun table, #346 S4).
    """
    conn.execute("PRAGMA journal_mode=WAL")
    # Pin NORMAL then FULL so the FULL line is load-bearing (user_events B1
    # finding: SQLite 3.53's compile-time default is already FULL, so a bare
    # FULL is a no-op and deleting it leaves the pragma test green).
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys=ON")


def _seed_lookup_tables(conn: sqlite3.Connection) -> None:
    """Populate closed lookup tables idempotently."""
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


def _bootstrap_meta(conn: sqlite3.Connection) -> None:
    """Ensure schema_version row exists; refuse a mismatched version."""
    row = conn.execute(
        "SELECT value FROM meta WHERE key = 'schema_version'"
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        return
    stored = int(row[0])
    if stored != SCHEMA_VERSION:
        raise SchemaVersionError(
            f"ledger schema_version {stored} != supported {SCHEMA_VERSION}; "
            "fail-closed: refuse open rather than guess"
        )


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
    _ensure_parent_durable(path)
    # isolation_level default: DML needs explicit commit.
    conn = sqlite3.connect(str(path), isolation_level=None)
    try:
        _apply_pragmas(conn)
        conn.executescript(_SCHEMA_SQL)
        # executescript leaves autocommit; re-enter for the bootstrap writes.
        conn.execute("BEGIN")
        _bootstrap_meta(conn)
        _seed_lookup_tables(conn)
        conn.execute("COMMIT")
    except Exception:
        conn.close()
        raise

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
