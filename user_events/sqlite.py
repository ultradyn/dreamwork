"""SQLite journal store for durable user-event receipts (lane B).

open_journal(path) creates a durable WAL database with synchronous=FULL and a
bounded busy_timeout. Per-connection pragmas are re-applied on every open —
synchronous is not a file property, so a second open must set them again.

This module is new files only; nothing wires it into watch.py yet.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from user_events.digest import (
    canonical_media_type,
    canonical_method,
    canonical_route,
    length_framed,
    request_digest,
)

PathLike = Union[str, os.PathLike]


@dataclass(frozen=True)
class Envelope:
    """One complete registered transport envelope ready for receive."""

    client_action_id: str
    protocol_version: str
    method: str
    route: str
    content_type: str
    body: bytes
    target_id: str = ""
    source_hint: str = ""
    redaction_class: str = "default"


@dataclass(frozen=True)
class ReceiveResult:
    """Outcome of receive(): inserted | replay | conflict.

    kind is the discriminating field — a unique-constraint IntegrityError is a
    *different* failure and must not be counted as a successful replay.
    """

    kind: str  # "inserted" | "replay" | "conflict"
    receipt_id: Optional[str]
    sequence: Optional[int]
    request_digest: str
    state: Optional[str]
    revision: Optional[int]
    exact_payload_bytes: Optional[bytes] = None


@dataclass(frozen=True)
class ChainVerifyResult:
    """Outcome of verify_chain. On failure, failed_ordinal names the break."""

    ok: bool
    through_ordinal: int
    head_hash: Optional[str] = None
    failed_ordinal: Optional[int] = None


def _h0(journal_id: str) -> str:
    """H_0 = SHA-256(journal_id || schema_version)."""
    material = f"{journal_id}{SCHEMA_VERSION}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _hash_event(prev_hash: str, canonical_payload: bytes) -> str:
    """H_i = SHA-256(domain_tag || H_(i-1) || length_framed(canonical_event_i)).

    The prev_hash term is load-bearing (B3 red): without it the chain stops
    linking and an earlier-event mutation no longer moves the head.
    """
    # length_framed of the already-assembled event payload (one part) matches
    # the design's length_framed(canonical_event_i) for a single blob form.
    framed = length_framed(canonical_payload)
    # --- B3 red line: prev_hash term in the hash input ---
    material = DOMAIN_TAG + prev_hash.encode("ascii") + framed
    return hashlib.sha256(material).hexdigest()


def _canonical_receipt_created(
    receipt_id: str,
    client_action_id: str,
    digest: str,
    body: bytes,
) -> bytes:
    """Canonical bytes for a receipt.created journal event (not the H_i formula)."""
    return length_framed(
        "receipt.created",
        receipt_id,
        client_action_id,
        digest,
        body,
    )

SCHEMA_VERSION = 1
# Bounded busy timeout in milliseconds. The durability boundary claims a
# finite wait, not "wait forever".
BUSY_TIMEOUT_MS = 5_000
# Domain tag for the hash chain. Constant across a schema_version.
DOMAIN_TAG = b"ud-dreamwork.user-events.v1"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS receipts (
    receipt_id          TEXT PRIMARY KEY,
    sequence            INTEGER NOT NULL UNIQUE,
    client_action_id    TEXT NOT NULL UNIQUE,
    request_digest      TEXT NOT NULL,
    received_at         TEXT NOT NULL,
    method              TEXT NOT NULL,
    endpoint            TEXT NOT NULL,
    content_type        TEXT NOT NULL,
    exact_payload_bytes BLOB NOT NULL,
    payload_size        INTEGER NOT NULL,
    target_id           TEXT NOT NULL DEFAULT '',
    source_hint         TEXT NOT NULL DEFAULT '',
    redaction_class     TEXT NOT NULL DEFAULT 'default',
    purged_at           TEXT,
    state               TEXT NOT NULL DEFAULT 'received',
    revision            INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS transitions (
    transition_id        TEXT PRIMARY KEY,
    receipt_id           TEXT NOT NULL REFERENCES receipts(receipt_id),
    at                   TEXT NOT NULL,
    from_state           TEXT NOT NULL,
    to_state             TEXT NOT NULL,
    revision             INTEGER NOT NULL,
    consumer_id          TEXT,
    claim_token          TEXT,
    lease_until          TEXT,
    application_adapter  TEXT,
    application_ref      TEXT,
    reason_code          TEXT,
    bounded_detail       TEXT
);

CREATE TABLE IF NOT EXISTS events (
    event_ordinal      INTEGER PRIMARY KEY,
    event_kind         TEXT NOT NULL,
    receipt_id         TEXT,
    at                 TEXT NOT NULL,
    prev_hash          TEXT NOT NULL,
    event_hash         TEXT NOT NULL,
    canonical_payload  BLOB NOT NULL
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
    """Apply durability-boundary pragmas on this connection.

    journal_mode=WAL is a database property (persists in the file).
    synchronous and busy_timeout are per-connection and must be set every open.
    """
    # journal_mode returns the mode string; must be wal after this.
    conn.execute("PRAGMA journal_mode=WAL")
    # synchronous is per-connection. SQLite 3.53's compile-time default is
    # already FULL (2), so a bare `PRAGMA synchronous=FULL` is a no-op on this
    # build and deleting it leaves the pragma test green — a hollow red. Pin
    # NORMAL first so the FULL line is the one that establishes the durability
    # claim; deleting only that line leaves NORMAL (1) and the B1 red fails.
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")


def _bootstrap_meta(conn: sqlite3.Connection) -> str:
    """Ensure schema_version and journal_id rows exist; return journal_id."""
    row = conn.execute(
        "SELECT value FROM meta WHERE key = 'schema_version'"
    ).fetchone()
    if row is None:
        journal_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('journal_id', ?)",
            (journal_id,),
        )
        conn.commit()
        return journal_id
    stored = int(row[0])
    if stored != SCHEMA_VERSION:
        raise RuntimeError(
            f"journal schema_version {stored} != supported {SCHEMA_VERSION}"
        )
    jid = conn.execute(
        "SELECT value FROM meta WHERE key = 'journal_id'"
    ).fetchone()
    if jid is None:
        raise RuntimeError("journal meta missing journal_id")
    return jid[0]


class Journal:
    """A live connection to one target's user-event journal database."""

    def __init__(self, path: Path, conn: sqlite3.Connection, journal_id: str):
        self.path = path
        self.conn = conn
        self.journal_id = journal_id

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Journal":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def read_pragmas(self) -> dict:
        """Return journal_mode, synchronous, busy_timeout from THIS connection."""
        mode = self.conn.execute("PRAGMA journal_mode").fetchone()[0]
        sync = self.conn.execute("PRAGMA synchronous").fetchone()[0]
        busy = self.conn.execute("PRAGMA busy_timeout").fetchone()[0]
        return {
            "journal_mode": str(mode).lower(),
            "synchronous": int(sync),
            "busy_timeout": int(busy),
        }

    def receipt_count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0])

    def head_ordinal(self) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(MAX(event_ordinal), 0) FROM events"
        ).fetchone()
        return int(row[0])

    def head_hash(self) -> str:
        """Hash at the high-water ordinal, or H_0 when the chain is empty."""
        row = self.conn.execute(
            "SELECT event_hash FROM events ORDER BY event_ordinal DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return _h0(self.journal_id)
        return row[0]

    def _append_event(
        self,
        *,
        event_kind: str,
        receipt_id: Optional[str],
        at: str,
        canonical_payload: bytes,
    ) -> int:
        """Append one chained event inside the caller's open transaction.

        Returns the new event_ordinal.
        """
        prev_ordinal = self.head_ordinal()
        if prev_ordinal == 0:
            prev = _h0(self.journal_id)
        else:
            prev = self.conn.execute(
                "SELECT event_hash FROM events WHERE event_ordinal = ?",
                (prev_ordinal,),
            ).fetchone()[0]
        ordinal = prev_ordinal + 1
        event_hash = _hash_event(prev, canonical_payload)
        self.conn.execute(
            """
            INSERT INTO events (
                event_ordinal, event_kind, receipt_id, at,
                prev_hash, event_hash, canonical_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ordinal,
                event_kind,
                receipt_id,
                at,
                prev,
                event_hash,
                canonical_payload,
            ),
        )
        return ordinal

    def verify_chain(self, through_ordinal: Optional[int] = None) -> ChainVerifyResult:
        """Recompute H_1..H_n and name the first ordinal that does not match.

        Must not trust stored event_hash without recomputing from prev + payload.
        """
        high = self.head_ordinal()
        if through_ordinal is None:
            through_ordinal = high
        if through_ordinal < 0:
            raise ValueError("through_ordinal must be >= 0")
        if through_ordinal > high:
            return ChainVerifyResult(
                ok=False,
                through_ordinal=through_ordinal,
                failed_ordinal=high + 1 if high < through_ordinal else through_ordinal,
            )
        if through_ordinal == 0:
            return ChainVerifyResult(
                ok=True, through_ordinal=0, head_hash=_h0(self.journal_id)
            )

        prev = _h0(self.journal_id)
        head = prev
        for ordinal in range(1, through_ordinal + 1):
            row = self.conn.execute(
                "SELECT prev_hash, event_hash, canonical_payload FROM events "
                "WHERE event_ordinal = ?",
                (ordinal,),
            ).fetchone()
            if row is None:
                return ChainVerifyResult(
                    ok=False,
                    through_ordinal=through_ordinal,
                    failed_ordinal=ordinal,
                )
            # Recompute; naming the ordinal on mismatch is what property (c) asserts.
            expected = _hash_event(prev, bytes(row["canonical_payload"]))
            if row["prev_hash"] != prev or row["event_hash"] != expected:
                return ChainVerifyResult(
                    ok=False,
                    through_ordinal=through_ordinal,
                    failed_ordinal=ordinal,
                )
            prev = expected
            head = expected
        return ChainVerifyResult(
            ok=True, through_ordinal=through_ordinal, head_hash=head
        )

    def receive(self, envelope: Envelope) -> ReceiveResult:
        """Idempotent receive: absent→insert, equal digest→replay, else conflict.

        Implements the three-row table in user-event-journal.md §Receive and
        idempotency. The SELECT-then-compare before insert is load-bearing: without
        it a same-UUID retry raises IntegrityError on the unique constraint, which
        is a *different* failure than a clean replay (B2 red line).
        """
        digest = request_digest(
            protocol_version=envelope.protocol_version,
            method=envelope.method,
            route=envelope.route,
            content_type=envelope.content_type,
            body=envelope.body,
        )
        # Canonical surface fields stored on the receipt (import from digest;
        # never re-implement).
        method = canonical_method(envelope.method)
        endpoint = canonical_route(envelope.route)
        content_type = canonical_media_type(envelope.content_type)
        body = bytes(envelope.body)

        self.conn.execute("BEGIN IMMEDIATE")
        try:
            # --- B2 red line: this SELECT + digest comparison before insert ---
            existing = self.conn.execute(
                "SELECT request_digest, receipt_id, sequence, state, revision, "
                "exact_payload_bytes FROM receipts WHERE client_action_id = ?",
                (envelope.client_action_id,),
            ).fetchone()
            if existing is not None:
                if existing["request_digest"] == digest:
                    self.conn.execute("COMMIT")
                    return ReceiveResult(
                        kind="replay",
                        receipt_id=existing["receipt_id"],
                        sequence=int(existing["sequence"]),
                        request_digest=existing["request_digest"],
                        state=existing["state"],
                        revision=int(existing["revision"]),
                        exact_payload_bytes=bytes(existing["exact_payload_bytes"]),
                    )
                # present + different digest → conflict; preserve original
                self.conn.execute("COMMIT")
                return ReceiveResult(
                    kind="conflict",
                    receipt_id=existing["receipt_id"],
                    sequence=int(existing["sequence"]),
                    request_digest=existing["request_digest"],
                    state=existing["state"],
                    revision=int(existing["revision"]),
                    exact_payload_bytes=bytes(existing["exact_payload_bytes"]),
                )

            # absent → insert one receipt in state received.
            # receipt_id is deterministic from client_action_id so the same
            # logical sequence in two journals yields the same chain head
            # (property a); uuid4 would make every head differ for free.
            receipt_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"ud-dreamwork.receipt:{envelope.client_action_id}",
                )
            )
            seq_row = self.conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM receipts"
            ).fetchone()
            sequence = int(seq_row[0])
            # received_at is not in the chain canonical form; wall clock is fine.
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            self.conn.execute(
                """
                INSERT INTO receipts (
                    receipt_id, sequence, client_action_id, request_digest,
                    received_at, method, endpoint, content_type,
                    exact_payload_bytes, payload_size, target_id, source_hint,
                    redaction_class, state, revision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'received', 1)
                """,
                (
                    receipt_id,
                    sequence,
                    envelope.client_action_id,
                    digest,
                    now,
                    method,
                    endpoint,
                    content_type,
                    body,
                    len(body),
                    envelope.target_id,
                    envelope.source_hint,
                    envelope.redaction_class,
                ),
            )
            # Initial received transition at revision 1
            self.conn.execute(
                """
                INSERT INTO transitions (
                    transition_id, receipt_id, at, from_state, to_state, revision
                ) VALUES (?, ?, ?, '', 'received', 1)
                """,
                (str(uuid.uuid4()), receipt_id, now),
            )
            # Chain append in the same transaction as the receipt (B3).
            canonical = _canonical_receipt_created(
                receipt_id, envelope.client_action_id, digest, body
            )
            self._append_event(
                event_kind="receipt.created",
                receipt_id=receipt_id,
                at=now,
                canonical_payload=canonical,
            )
            self.conn.execute("COMMIT")
            return ReceiveResult(
                kind="inserted",
                receipt_id=receipt_id,
                sequence=sequence,
                request_digest=digest,
                state="received",
                revision=1,
                exact_payload_bytes=body,
            )
        except Exception:
            self.conn.execute("ROLLBACK")
            raise


def open_journal(path: PathLike) -> Journal:
    """Open (or create) the durable journal at path.

    Creates the parent directory durably, applies WAL + FULL + busy_timeout,
    installs the schema, and ensures a schema_version row.
    """
    p = Path(path)
    _ensure_parent_durable(p)
    # Default isolation: DML needs explicit commit. PRAGMA journal_mode=WAL
    # must run outside a multi-statement transaction.
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    try:
        _apply_pragmas(conn)
        # executescript issues its own COMMIT first; that is fine here —
        # pragmas are already applied and schema DDL is idempotent.
        conn.executescript(_SCHEMA_SQL)
        journal_id = _bootstrap_meta(conn)
    except Exception:
        conn.close()
        raise
    return Journal(p, conn, journal_id)
