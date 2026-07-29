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
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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


@dataclass(frozen=True)
class TransitionResult:
    """Outcome of transition(): applied | stale | invalid_edge | missing."""

    kind: str
    receipt_id: Optional[str] = None
    state: Optional[str] = None
    revision: Optional[int] = None


@dataclass(frozen=True)
class ClaimResult:
    """Outcome of claim(): claimed | refused | stale | missing."""

    kind: str
    receipt_id: Optional[str] = None
    state: Optional[str] = None
    revision: Optional[int] = None
    claim_token: Optional[str] = None
    lease_until: Optional[str] = None
    consumer: Optional[str] = None


@dataclass(frozen=True)
class FinishResult:
    """Outcome of finish(): finished | stale | refused | missing."""

    kind: str
    receipt_id: Optional[str] = None
    state: Optional[str] = None
    revision: Optional[int] = None


@dataclass(frozen=True)
class CursorView:
    """A consumer's replay cursor projection."""

    consumer: str
    journal_id: str
    scanned_through_event_ordinal: int
    chain_hash_at_ordinal: str
    revision: int


@dataclass(frozen=True)
class AdvanceCursorResult:
    """Outcome of advance_cursor(): advanced | refused.

    On refuse after a broken chain, rebuild is True and ordinals_read counts
    how many event rows the rebuild path examined (from 1 through the target).
    """

    kind: str  # "advanced" | "refused"
    reason: Optional[str] = None
    cursor: Optional[CursorView] = None
    rebuild: bool = False
    ordinals_read: int = 0
    failed_ordinal: Optional[int] = None


@dataclass(frozen=True)
class ReceiptEvent:
    """One ``receipt.created`` event in a cursor-bounded read projection (#342).

    ``events_since_cursor`` returns these for the ``receipt.created`` events in
    ``(cursor, head]`` — the queue a batched consumer drains on its tick.  Each
    carries what an adapter replay needs (the receipt's route and exact payload
    bytes) plus the ordinal and event hash; the high-end row's ``event_hash`` is
    what the caller passes to :meth:`Journal.advance_cursor`'s ``expected``.
    """

    ordinal: int
    event_hash: str
    receipt_id: str
    route: str
    exact_payload_bytes: bytes


@dataclass(frozen=True)
class CutoverResult:
    """Outcome of cutover() (H2): the generation advanced from_gen -> to_gen.

    ``in_flight_at_commit`` is the count of in-flight receipts under the
    drained generation at the moment the watermark committed.  With the drain
    it is 0 (every request completed under its received generation before the
    generation advanced).  A nonzero value would mean the cutover advanced over
    an in-flight request — the condition under which a downstream apply would
    write an effect under a generation the receipt was not received in (a
    legacy/uncoordinated direct write).  Recorded so a reader can tell a clean
    watermark from a dirty one without re-deriving the count.
    """

    from_gen: int
    to_gen: int
    holder: str
    in_flight_at_commit: int
    lease_token: str


# Edges authorised at B4. claim requires validated; rejected is a sink.
# finish moves claimed → applied (B5).
_TRANSITION_EDGES = {
    ("received", "validated"),
    ("received", "rejected"),
}

# Closed set of health statuses a receipt can carry (E4).  ``shadow_failed``
# is health, not application state: it says the best-effort witness shadow
# could not be written, NOT that the receipt is bad.  A parser (test, CLI
# ``health``, dashboard E6) reads this tuple to know the vocabulary; a new
# status adds an entry here and nowhere else.
RECEIPT_HEALTH = ("shadow_failed",)

# Closed set of reason codes for a received→rejected transition (E5).  A
# malformed or schema/domain-invalid body is still a *received* envelope: it
# gets a 202 and a durable rejected transition with one of these codes.  The
# set is bounded because a projection (CLI, dashboard) parses the code, and
# free-text exception messages would be an unparseable field.  A parser that
# finds a code outside this set treats it as a data-integrity issue.
#
#   malformed_json  — body is not valid JSON (the _read_json failure)
#   schema_invalid  — valid JSON but missing/wrong-type/empty required fields
#   domain_invalid  — schema valid but fails a domain rule (unknown kind/tint/mode)
REJECTION_REASONS = ("malformed_json", "schema_invalid", "domain_invalid")

# Transport protocol version carried on every Envelope and length-framed into
# the request digest (design §Receive and idempotency).  Closed set: an older
# process that does not understand a newer protocol must refuse the write,
# never invent a best-effort interpretation.  ``watch.JOURNAL_PROTOCOL_VERSION``
# must be a member; a widening lands here first.
PROTOCOL_VERSION = "1"
SUPPORTED_PROTOCOL_VERSIONS = (PROTOCOL_VERSION,)


class VersionMismatchError(RuntimeError):
    """Journal or envelope version this process cannot understand (H1).

    Fail-closed: refuse the open or the receive rather than skip, guess, or
    silently drop events.  Distinct from ordinary ValueError so a caller can
    surface mixed-version without treating it as a malformed field.
    """


class CutoverError(RuntimeError):
    """Base for cutover (H2) failures.  See CutoverBusy / CutoverDrainTimeout."""


class CutoverBusy(CutoverError):
    """Another holder's cutover lease is active and unexpired (H2).

    The lease is stealable only after expiry (reusing B5's
    ``lease_until > now`` predicate); an active, unexpired lease is refused so
    two cutover attempts over one target cannot both advance the generation.
    """


class CutoverDrainTimeout(CutoverError):
    """The drain deadline elapsed before in-flight receipts quiesced (H2).

    The lease is released on timeout so a later cutover can retry; no
    watermark is written.  Distinct from CutoverBusy because the holder itself
    gives up rather than being refused by another.
    """

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


def _canonical_receipt_health(
    receipt_id: str,
    health: str,
    detail: str = "",
) -> bytes:
    """Canonical bytes for a receipt.health journal event (E4).

    Health is not application state — ``shadow_failed`` does not move the
    receipt out of ``received``.  It is a canonical chained event so the
    dashboard (E6) and CLI (F4) can surface it without parsing free text.
    """
    return length_framed(
        "receipt.health",
        receipt_id,
        health,
        detail,
    )


def _canonical_generation_cutover(
    from_gen: int,
    to_gen: int,
    holder: str,
    in_flight_at_commit: int,
) -> bytes:
    """Canonical bytes for a generation.cutover journal event (H2).

    The cutover watermark is an irreversible chained event (design: *"Rollback
    never deletes/renumbers receipts"*).  ``in_flight_at_commit`` records
    whether the drain quiesced before the advance: 0 is a clean watermark; any
    other value means the generation advanced over an in-flight request, which
    is the legacy-direct-write class.  The two generation ints frame the
    advance so a projection (CLI, dashboard) can name the boundary without
    parsing prose.
    """
    return length_framed(
        "generation.cutover",
        str(from_gen),
        str(to_gen),
        holder,
        str(in_flight_at_commit),
    )


def _parse_framed_fields(payload: bytes) -> list:
    """Inverse of :func:`length_framed` — split a framed blob back into fields.

    Used by health-readback (tests, CLI, dashboard) so they do not hold a
    private copy of the framing format.
    """
    fields = []
    i = 0
    while i + 8 <= len(payload):
        n = int.from_bytes(payload[i:i + 8], "big")
        i += 8
        fields.append(payload[i:i + n])
        i += n
    return fields

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
    revision            INTEGER NOT NULL DEFAULT 1,
    claim_token         TEXT,
    claim_consumer      TEXT,
    lease_until         TEXT,
    -- H2: the generation (cutover epoch) this receipt was received under.
    -- Stamped server-side at receive() inside BEGIN IMMEDIATE, never supplied
    -- by the request, so an in-flight request's generation is frozen on its
    -- append-only row and cannot be promoted to a newer generation by itself.
    generation          INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cursors (
    consumer                       TEXT PRIMARY KEY,
    scanned_through_event_ordinal  INTEGER NOT NULL,
    chain_hash_at_ordinal          TEXT NOT NULL,
    revision                       INTEGER NOT NULL
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
    # H1 fail-closed red line: exact match, never "close enough".  A newer
    # journal (future writer) and an older one (pre-migration) both refuse
    # open before any receive can witness a write.  SCHEMA_VERSION is the
    # journal's version marker today; widening it needs a migration, not a
    # best-effort reader.
    if stored != SCHEMA_VERSION:
        raise VersionMismatchError(
            f"journal schema_version {stored} != supported {SCHEMA_VERSION}; "
            "mixed-version fail-closed: refuse open rather than guess"
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

        H1: protocol_version is checked BEFORE any write.  An unknown version
        raises VersionMismatchError with zero receipts inserted — refuse, do not
        store a record this process cannot later project.
        """
        # --- H1 red line: protocol_version closed-set check before BEGIN ---
        if envelope.protocol_version not in SUPPORTED_PROTOCOL_VERSIONS:
            raise VersionMismatchError(
                f"envelope protocol_version {envelope.protocol_version!r} "
                f"not in supported {SUPPORTED_PROTOCOL_VERSIONS}; "
                "mixed-version fail-closed: refuse receive rather than guess"
            )
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
            # received_at is not in the chain canonical form; wall clock is fine.
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            # H2 closure (coordinator steer on the drain's TOCTOU window):
            # while a cutover drain holds its lease, the current generation is
            # closed to NEW receipts. Replays and conflicts above still resolve
            # against the existing row (no new receipt); only a genuinely-new
            # insert is refused, because it has not yet been witnessed (no 202)
            # and refusing keeps every stamped generation honest — stamping it
            # under the next generation instead would mint a receipt in a
            # generation that may not commit if the drain times out, the same
            # two-durable-truths shape that decision 2 rejected. ISO-8601 Z
            # strings compare lexically, like the lease check in cutover().
            lease_row = self.conn.execute(
                "SELECT value FROM meta WHERE key = 'cutover_lease_until'"
            ).fetchone()
            if lease_row is not None and lease_row[0] > now:
                # The outer except rolls the BEGIN IMMEDIATE back and re-raises.
                raise CutoverBusy(
                    "cutover drain in progress (lease until "
                    f"{lease_row[0]}); generation closed to new receipts — "
                    "retry after the cutover completes"
                )
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
            # H2: stamp the current generation onto the receipt. Read here,
            # inside BEGIN IMMEDIATE, so the generation is the store's own
            # authoritative value at the moment of receive — the request never
            # supplies it and cannot forge a different one.
            received_generation = self.generation()
            self.conn.execute(
                """
                INSERT INTO receipts (
                    receipt_id, sequence, client_action_id, request_digest,
                    received_at, method, endpoint, content_type,
                    exact_payload_bytes, payload_size, target_id, source_hint,
                    redaction_class, state, revision, generation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'received', 1, ?)
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
                    received_generation,
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

    def get_receipt(self, receipt_id: str) -> Optional[dict]:
        """Read current receipt projection. Revisions must come from here, not the test."""
        row = self.conn.execute(
            "SELECT receipt_id, sequence, client_action_id, request_digest, "
            "state, revision, exact_payload_bytes, claim_token, claim_consumer, "
            "lease_until FROM receipts WHERE receipt_id = ?",
            (receipt_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "receipt_id": row["receipt_id"],
            "sequence": int(row["sequence"]),
            "client_action_id": row["client_action_id"],
            "request_digest": row["request_digest"],
            "state": row["state"],
            "revision": int(row["revision"]),
            "exact_payload_bytes": bytes(row["exact_payload_bytes"]),
            "claim_token": row["claim_token"],
            "claim_consumer": row["claim_consumer"],
            "lease_until": row["lease_until"],
        }

    def transition(
        self,
        receipt_id: str,
        to_state: str,
        expected_revision: int,
        reason_code: Optional[str] = None,
    ) -> TransitionResult:
        """Append a state transition against expected_revision (CAS).

        received→validated and received→rejected are the B4 edges. A stale
        expected_revision is refused without mutating state.
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.conn.execute(
                "SELECT state, revision FROM receipts WHERE receipt_id = ?",
                (receipt_id,),
            ).fetchone()
            if row is None:
                self.conn.execute("COMMIT")
                return TransitionResult(kind="missing")
            from_state = row["state"]
            current_rev = int(row["revision"])
            if current_rev != expected_revision:
                self.conn.execute("COMMIT")
                return TransitionResult(
                    kind="stale",
                    receipt_id=receipt_id,
                    state=from_state,
                    revision=current_rev,
                )
            if (from_state, to_state) not in _TRANSITION_EDGES:
                self.conn.execute("COMMIT")
                return TransitionResult(
                    kind="invalid_edge",
                    receipt_id=receipt_id,
                    state=from_state,
                    revision=current_rev,
                )
            new_rev = current_rev + 1
            self.conn.execute(
                "UPDATE receipts SET state = ?, revision = ? WHERE receipt_id = ?",
                (to_state, new_rev, receipt_id),
            )
            self.conn.execute(
                """
                INSERT INTO transitions (
                    transition_id, receipt_id, at, from_state, to_state, revision,
                    reason_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), receipt_id, now, from_state, to_state,
                 new_rev, reason_code),
            )
            canonical = length_framed(
                "receipt.transition",
                receipt_id,
                from_state,
                to_state,
                str(new_rev),
                reason_code or "",
            )
            self._append_event(
                event_kind="receipt.transition",
                receipt_id=receipt_id,
                at=now,
                canonical_payload=canonical,
            )
            self.conn.execute("COMMIT")
            return TransitionResult(
                kind="applied",
                receipt_id=receipt_id,
                state=to_state,
                revision=new_rev,
            )
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def record_health(
        self,
        receipt_id: str,
        health: str,
        detail: str = "",
    ) -> None:
        """Record a health event against a receipt (E4).

        Health is not a state transition — ``shadow_failed`` does not move
        the receipt out of ``received``.  It is a canonical chained event so
        the dashboard (E6) and CLI (F4) can surface it.  ``health`` must be
        in :data:`RECEIPT_HEALTH` (the closed set); a parser that finds an
        unknown value treats it as a data-integrity issue, not a new status.
        """
        if health not in RECEIPT_HEALTH:
            raise ValueError(f"unknown health status: {health!r}")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        canonical = _canonical_receipt_health(receipt_id, health, detail)
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self._append_event(
                event_kind="receipt.health",
                receipt_id=receipt_id,
                at=now,
                canonical_payload=canonical,
            )
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def get_receipt_health(self, receipt_id: str) -> Optional[str]:
        """Latest health status recorded against a receipt, or ``None``.

        Read-back path for tests, the CLI ``health`` command, and the
        dashboard (E6).  Returns the health string (a member of
        :data:`RECEIPT_HEALTH`), not the raw framed bytes.
        """
        row = self.conn.execute(
            "SELECT canonical_payload FROM events "
            "WHERE receipt_id = ? AND event_kind = 'receipt.health' "
            "ORDER BY event_ordinal DESC LIMIT 1",
            (receipt_id,),
        ).fetchone()
        if row is None:
            return None
        fields = _parse_framed_fields(bytes(row["canonical_payload"]))
        # ["receipt.health", receipt_id, health, detail]
        return fields[2].decode("utf-8") if len(fields) > 2 else None

    # ------------------------------------------------------------------
    # H2 — cutover lease, drain, watermark.
    #
    # A generation is a monotonic int in meta stamped on every receipt at
    # receive() (see above).  cutover() advances it: it acquires an exclusive
    # lease (reusing B5's claim/reclaim shape — fixture 12's "dual reclaimer
    # and stale claimant => one CAS winner"), DRAINS in-flight receipts at the
    # current generation to a terminal state, then commits an irreversible
    # watermark event and bumps the generation.  TEMP TARGETS ONLY: the
    # watermark is irreversible (design: rollback never deletes/renumbers
    # receipts), so running it against a live target is migration, not this
    # increment.
    # ------------------------------------------------------------------

    def generation(self) -> int:
        """Current cutover generation (meta ``generation``, default 1)."""
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key = 'generation'"
        ).fetchone()
        if row is None:
            return 1
        return int(row[0])

    def receipt_generation(self, receipt_id: str) -> Optional[int]:
        """The generation a receipt was received under (frozen on its row)."""
        row = self.conn.execute(
            "SELECT generation FROM receipts WHERE receipt_id = ?",
            (receipt_id,),
        ).fetchone()
        return int(row[0]) if row is not None else None

    def in_flight(self, generation: Optional[int] = None) -> int:
        """Count receipts at ``generation`` (default current) not yet terminal.

        A receipt is in-flight while it is received / validated / claimed —
        the window between receive() and finish().  The drain waits on this
        count reaching zero so a request spanning the cutover completes under
        the generation it was received in.
        """
        if generation is None:
            generation = self.generation()
        row = self.conn.execute(
            "SELECT COUNT(*) FROM receipts "
            "WHERE generation = ? AND state IN ('received','validated','claimed')",
            (generation,),
        ).fetchone()
        return int(row[0])

    def cutover_state(self) -> dict:
        """Read the current cutover lease, or an empty dict when none is held."""
        rows = self.conn.execute(
            "SELECT key, value FROM meta WHERE key IN "
            "('cutover_holder','cutover_token','cutover_lease_until')"
        ).fetchall()
        out = {r["key"]: r["value"] for r in rows}
        return out

    def _release_cutover_lease(self) -> None:
        """Drop the cutover lease rows (called on drain timeout)."""
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute(
                "DELETE FROM meta WHERE key IN "
                "('cutover_holder','cutover_token','cutover_lease_until')"
            )
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def cutover(
        self,
        *,
        holder: str,
        lease_seconds: int,
        drain_seconds: float,
        poll_interval: float = 0.02,
    ) -> CutoverResult:
        """Lease, drain, watermark: advance the generation from N to N+1.

        Three parts, and the middle one is the increment's meaning:

        1. **Lease** — CAS-acquire an exclusive cutover lease on meta.  Reuses
           B5's claim/reclaim shape: an active, unexpired lease is refused
           (``CutoverBusy``); an expired lease is reclaimable by a new holder
           (the ``lease_until > now`` predicate from B5, inverted).  A holder
           that dies mid-drain wedges no one.  **Taking the lease also closes
           gen N to new receipts** — ``receive()`` refuses while the lease is
           held, so the drain below cannot be overtaken by a brand-new gen-N
           receipt stamped behind its back (the TOCTOU window).
        2. **Drain** — wait until no receipt is in-flight at the current
           generation, or the ``drain_seconds`` deadline elapses.  This is the
           red line: deleting this wait lets the watermark advance over an
           in-flight request.  A request spanning the cutover therefore
           COMPLETES UNDER THE DRAINED GENERATION (the chosen outcome): it is
           never retried under the new generation, which keeps a ``202`` honest.
        3. **Watermark** — append an irreversible ``generation.cutover`` event,
           bump meta ``generation``, release the lease.  The event records
           ``in_flight_at_commit`` so a reader can tell a clean advance from
           one that ran over an in-flight request.

        TEMP TARGETS ONLY.  The watermark is irreversible.
        """
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if drain_seconds < 0:
            raise ValueError("drain_seconds must be >= 0")

        now = datetime.now(timezone.utc)
        now_s = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        lease_until = (now + timedelta(seconds=lease_seconds)).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        token = uuid.uuid4().hex

        # --- 1. lease: reuse B5's claim/reclaim shape (fixture 12 prior art) ---
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            from_gen = self.generation()
            cur_lease = self.conn.execute(
                "SELECT value FROM meta WHERE key = 'cutover_lease_until'"
            ).fetchone()
            cur_lease_s = cur_lease[0] if cur_lease is not None else None
            # B5 red-line predicate reused: an active lease is one whose
            # lease_until > backend now.  ISO-8601 strings compare lexically.
            active = cur_lease_s is not None and cur_lease_s > now_s
            if active:
                self.conn.execute("COMMIT")
                raise CutoverBusy(
                    f"cutover lease active until {cur_lease_s}; "
                    "steal only after expiry (reuse of B5 lease_until > now)"
                )
            self.conn.execute(
                "INSERT INTO meta (key, value) VALUES ('cutover_holder', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (holder,),
            )
            self.conn.execute(
                "INSERT INTO meta (key, value) VALUES ('cutover_token', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (token,),
            )
            self.conn.execute(
                "INSERT INTO meta (key, value) VALUES ('cutover_lease_until', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (lease_until,),
            )
            self.conn.execute("COMMIT")
        except CutoverBusy:
            raise
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

        # --- 2. drain (red line): wait for in-flight receipts at from_gen ---
        deadline = time.monotonic() + drain_seconds
        while self.in_flight(from_gen) > 0:
            if time.monotonic() >= deadline:
                # Release the lease so a later cutover can retry; no watermark.
                self._release_cutover_lease()
                raise CutoverDrainTimeout(
                    f"drain deadline ({drain_seconds}s) elapsed with "
                    f"{self.in_flight(from_gen)} receipt(s) in flight at "
                    f"generation {from_gen}; lease released, no watermark"
                )
            time.sleep(poll_interval)

        # --- 3. watermark: irreversible advance ---
        in_flight_at_commit = self.in_flight(from_gen)
        now2 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        to_gen = from_gen + 1
        canonical = _canonical_generation_cutover(
            from_gen, to_gen, holder, in_flight_at_commit
        )
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self._append_event(
                event_kind="generation.cutover",
                receipt_id=None,
                at=now2,
                canonical_payload=canonical,
            )
            self.conn.execute(
                "INSERT INTO meta (key, value) VALUES ('generation', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(to_gen),),
            )
            self.conn.execute(
                "DELETE FROM meta WHERE key IN "
                "('cutover_holder','cutover_token','cutover_lease_until')"
            )
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

        return CutoverResult(
            from_gen=from_gen,
            to_gen=to_gen,
            holder=holder,
            in_flight_at_commit=in_flight_at_commit,
            lease_token=token,
        )

    def last_watermark(self) -> Optional[dict]:
        """Newest ``generation.cutover`` event, or ``None`` if none exists.

        Fields are parsed from the canonical framed payload so callers do not
        hold a private copy of the framing format.
        """
        row = self.conn.execute(
            "SELECT canonical_payload FROM events "
            "WHERE event_kind = 'generation.cutover' "
            "ORDER BY event_ordinal DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        fields = _parse_framed_fields(bytes(row["canonical_payload"]))
        # ["generation.cutover", from_gen, to_gen, holder, in_flight_at_commit]
        return {
            "from_gen": int(fields[1]),
            "to_gen": int(fields[2]),
            "holder": fields[3].decode("utf-8"),
            "in_flight_at_commit": int(fields[4]),
        }

    def watermark_count(self) -> int:
        """Number of ``generation.cutover`` events committed (== generation - 1)."""
        row = self.conn.execute(
            "SELECT COUNT(*) FROM events WHERE event_kind = 'generation.cutover'"
        ).fetchone()
        return int(row[0])

    def claim(
        self,
        receipt_id: str,
        consumer: str,
        lease_seconds: int,
        expected_revision: int,
    ) -> ClaimResult:
        """Claim a validated receipt, or reclaim one whose lease has expired.

        B4 red line: AND state = 'validated' (rejected can never be claimed).
        B5 red line: lease_until > <backend now> — an active lease blocks
        reclaim; only when that predicate is false (lease expired) may a
        second consumer take the claim. Lease deadlines use backend/server
        time, never client clocks.
        """
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        now = datetime.now(timezone.utc)
        now_s = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        # lease_until from backend time (wall clock); never a client-supplied clock.
        lease_until = (now + timedelta(seconds=lease_seconds)).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        token = uuid.uuid4().hex

        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.conn.execute(
                "SELECT state, revision, lease_until, claim_token, claim_consumer "
                "FROM receipts WHERE receipt_id = ?",
                (receipt_id,),
            ).fetchone()
            if row is None:
                self.conn.execute("COMMIT")
                return ClaimResult(kind="missing")
            if int(row["revision"]) != expected_revision:
                self.conn.execute("COMMIT")
                return ClaimResult(
                    kind="stale",
                    receipt_id=receipt_id,
                    state=row["state"],
                    revision=int(row["revision"]),
                )
            from_state = row["state"]
            # --- B4: validated may be claimed; rejected never.
            # --- B5 red line: lease_until > backend now blocks reclaim ---
            # First claim: state = 'validated'.
            # Reclaim: state = 'claimed' AND NOT (lease_until > now_s)
            #   i.e. the active-lease predicate is false (expired or absent).
            cur = self.conn.execute(
                """
                UPDATE receipts
                SET state = 'claimed',
                    revision = revision + 1,
                    claim_token = ?,
                    claim_consumer = ?,
                    lease_until = ?
                WHERE receipt_id = ?
                  AND revision = ?
                  AND (
                    state = 'validated'
                    OR (
                      state = 'claimed'
                      AND NOT (lease_until > ?)
                    )
                  )
                """,
                (
                    token,
                    consumer,
                    lease_until,
                    receipt_id,
                    expected_revision,
                    now_s,
                ),
            )
            if cur.rowcount != 1:
                # Not validated, still leased, rejected, or lost the race.
                self.conn.execute("COMMIT")
                fresh = self.conn.execute(
                    "SELECT state, revision FROM receipts WHERE receipt_id = ?",
                    (receipt_id,),
                ).fetchone()
                return ClaimResult(
                    kind="refused",
                    receipt_id=receipt_id,
                    state=fresh["state"] if fresh else None,
                    revision=int(fresh["revision"]) if fresh else None,
                )
            new_rev = expected_revision + 1
            self.conn.execute(
                """
                INSERT INTO transitions (
                    transition_id, receipt_id, at, from_state, to_state,
                    revision, consumer_id, claim_token, lease_until
                ) VALUES (?, ?, ?, ?, 'claimed', ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    receipt_id,
                    now_s,
                    from_state,
                    new_rev,
                    consumer,
                    token,
                    lease_until,
                ),
            )
            canonical = length_framed(
                "receipt.claimed",
                receipt_id,
                consumer,
                token,
                lease_until,
                str(new_rev),
            )
            self._append_event(
                event_kind="receipt.claimed",
                receipt_id=receipt_id,
                at=now_s,
                canonical_payload=canonical,
            )
            self.conn.execute("COMMIT")
            return ClaimResult(
                kind="claimed",
                receipt_id=receipt_id,
                state="claimed",
                revision=new_rev,
                claim_token=token,
                lease_until=lease_until,
                consumer=consumer,
            )
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def finish(
        self,
        receipt_id: str,
        *,
        claim_token: str,
        consumer: str,
        expected_revision: int,
        outcome: str = "applied",
    ) -> FinishResult:
        """CAS-finish a claim. Stale claimant (wrong token/revision) cannot finish.

        Compares receipt + token + consumer + revision. After a reclaim, the
        first claimant's token no longer matches and finish is refused.
        """
        if outcome != "applied":
            # B5 only needs the applied path; other outcomes land with D later.
            raise ValueError(f"unsupported finish outcome: {outcome!r}")
        now_s = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.conn.execute(
                "SELECT state, revision, claim_token, claim_consumer "
                "FROM receipts WHERE receipt_id = ?",
                (receipt_id,),
            ).fetchone()
            if row is None:
                self.conn.execute("COMMIT")
                return FinishResult(kind="missing")
            if int(row["revision"]) != expected_revision:
                self.conn.execute("COMMIT")
                return FinishResult(
                    kind="stale",
                    receipt_id=receipt_id,
                    state=row["state"],
                    revision=int(row["revision"]),
                )
            cur = self.conn.execute(
                """
                UPDATE receipts
                SET state = 'applied',
                    revision = revision + 1,
                    claim_token = NULL,
                    claim_consumer = NULL,
                    lease_until = NULL
                WHERE receipt_id = ?
                  AND revision = ?
                  AND state = 'claimed'
                  AND claim_token = ?
                  AND claim_consumer = ?
                """,
                (receipt_id, expected_revision, claim_token, consumer),
            )
            if cur.rowcount != 1:
                self.conn.execute("COMMIT")
                fresh = self.conn.execute(
                    "SELECT state, revision FROM receipts WHERE receipt_id = ?",
                    (receipt_id,),
                ).fetchone()
                return FinishResult(
                    kind="refused",
                    receipt_id=receipt_id,
                    state=fresh["state"] if fresh else None,
                    revision=int(fresh["revision"]) if fresh else None,
                )
            new_rev = expected_revision + 1
            self.conn.execute(
                """
                INSERT INTO transitions (
                    transition_id, receipt_id, at, from_state, to_state,
                    revision, consumer_id, claim_token
                ) VALUES (?, ?, ?, 'claimed', 'applied', ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    receipt_id,
                    now_s,
                    new_rev,
                    consumer,
                    claim_token,
                ),
            )
            canonical = length_framed(
                "receipt.finished",
                receipt_id,
                consumer,
                claim_token,
                outcome,
                str(new_rev),
            )
            self._append_event(
                event_kind="receipt.finished",
                receipt_id=receipt_id,
                at=now_s,
                canonical_payload=canonical,
            )
            self.conn.execute("COMMIT")
            return FinishResult(
                kind="finished",
                receipt_id=receipt_id,
                state="applied",
                revision=new_rev,
            )
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def cursor(self, consumer: str) -> CursorView:
        """Return this consumer's cursor, or the empty-chain origin if none."""
        row = self.conn.execute(
            "SELECT scanned_through_event_ordinal, chain_hash_at_ordinal, revision "
            "FROM cursors WHERE consumer = ?",
            (consumer,),
        ).fetchone()
        if row is None:
            return CursorView(
                consumer=consumer,
                journal_id=self.journal_id,
                scanned_through_event_ordinal=0,
                chain_hash_at_ordinal=_h0(self.journal_id),
                revision=0,
            )
        return CursorView(
            consumer=consumer,
            journal_id=self.journal_id,
            scanned_through_event_ordinal=int(row["scanned_through_event_ordinal"]),
            chain_hash_at_ordinal=row["chain_hash_at_ordinal"],
            revision=int(row["revision"]),
        )

    def advance_cursor(
        self,
        consumer: str,
        expected: str,
        scanned_through: int,
    ) -> AdvanceCursorResult:
        """CAS-advance the cursor only past a verified chain endpoint.

        Always runs a bounded rebuild (verify_chain from ordinal 1 through
        scanned_through). On a broken chain, refuses and reports ordinals_read.
        The expected == verified head comparison is the B6 red line: without it
        a caller can advance past a hash they do not hold.
        """
        if scanned_through < 0:
            raise ValueError("scanned_through must be >= 0")

        # Bounded full rebuild from ordinal 1 — count is the target ordinal
        # (verify_chain walks 1..through inclusive; 0 reads nothing).
        verify = self.verify_chain(through_ordinal=scanned_through)
        ordinals_read = scanned_through

        if not verify.ok:
            return AdvanceCursorResult(
                kind="refused",
                reason="chain_broken",
                rebuild=True,
                ordinals_read=ordinals_read,
                failed_ordinal=verify.failed_ordinal,
            )

        # Verified endpoint hash. For ordinal 0 this is H_0.
        stored_chain_hash = verify.head_hash
        # --- B6 red line: expected == stored_chain_hash ---
        if expected != stored_chain_hash:
            return AdvanceCursorResult(
                kind="refused",
                reason="expected_mismatch",
                rebuild=True,
                ordinals_read=ordinals_read,
            )

        self.conn.execute("BEGIN IMMEDIATE")
        try:
            existing = self.conn.execute(
                "SELECT revision FROM cursors WHERE consumer = ?",
                (consumer,),
            ).fetchone()
            if existing is None:
                new_rev = 1
                self.conn.execute(
                    """
                    INSERT INTO cursors (
                        consumer, scanned_through_event_ordinal,
                        chain_hash_at_ordinal, revision
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (consumer, scanned_through, stored_chain_hash, new_rev),
                )
            else:
                new_rev = int(existing["revision"]) + 1
                self.conn.execute(
                    """
                    UPDATE cursors
                    SET scanned_through_event_ordinal = ?,
                        chain_hash_at_ordinal = ?,
                        revision = ?
                    WHERE consumer = ?
                    """,
                    (scanned_through, stored_chain_hash, new_rev, consumer),
                )
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

        return AdvanceCursorResult(
            kind="advanced",
            cursor=CursorView(
                consumer=consumer,
                journal_id=self.journal_id,
                scanned_through_event_ordinal=scanned_through,
                chain_hash_at_ordinal=stored_chain_hash,
                revision=new_rev,
            ),
            rebuild=False,
            ordinals_read=ordinals_read,
        )

    def events_since_cursor(self, consumer: str) -> list[ReceiptEvent]:
        """Cursor-bounded read: ``receipt.created`` events in ``(cursor, head]``.

        Delivery-modes batched consume, act 1 (#342 / delivery-modes.md §"How
        an agent consumes the cursor in batched mode").  Returns the events a
        consumer has not yet scanned past, each carrying what an adapter replay
        needs — the receipt's route and exact payload bytes — plus the ordinal
        and event hash.  The high-end row's ``event_hash`` equals
        :meth:`head_hash`, so the caller can pass it straight to
        :meth:`advance_cursor`'s ``expected``.

        Read-only: no writes, no cursor movement.  Reading twice returns the
        same rows.  The range is the half-open interval strictly above the
        consumer's cursor and up to the head, so an up-to-date consumer
        (cursor == head) reads nothing and a fresh consumer (no cursor row)
        reads from the empty-chain origin (ordinal 0).

        Only ``receipt.created`` events are projected: a batched consumer
        replays receipts through the adapters (apply.py), not transitions,
        claims, health marks or the cutover watermark — those share the chain's
        ordinals but carry no envelope to deliver (design doc: *"the
        receipt.created events and their receipts' route + exact_payload_bytes"*).
        """
        lower = self.cursor(consumer).scanned_through_event_ordinal
        upper = self.head_ordinal()
        rows = self.conn.execute(
            """
            SELECT e.event_ordinal, e.event_hash, e.receipt_id,
                   r.endpoint AS route, r.exact_payload_bytes
            FROM events e
            JOIN receipts r ON r.receipt_id = e.receipt_id
            WHERE e.event_kind = 'receipt.created'
              AND e.event_ordinal > ?
              AND e.event_ordinal <= ?
            ORDER BY e.event_ordinal ASC
            """,
            (lower, upper),
        ).fetchall()
        return [
            ReceiptEvent(
                ordinal=int(r["event_ordinal"]),
                event_hash=r["event_hash"],
                receipt_id=r["receipt_id"],
                route=r["route"],
                exact_payload_bytes=bytes(r["exact_payload_bytes"]),
            )
            for r in rows
        ]


def _ensure_generation_column(conn: sqlite3.Connection) -> None:
    """Add ``receipts.generation`` if an older journal lacks it (H2).

    SCHEMA_VERSION is unchanged (a watermark is not a schema migration), so a
    journal created before H2 opens fine under H1's version gate but lacks the
    column.  Additive ALTER only; fresh journals already have it.  TEMP
    targets in practice, but defensive so an accidental reuse cannot break.
    """
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(receipts)").fetchall()
    }
    if "generation" not in cols:
        conn.execute(
            "ALTER TABLE receipts ADD COLUMN generation INTEGER NOT NULL DEFAULT 1"
        )
        conn.commit()


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
        _ensure_generation_column(conn)
        journal_id = _bootstrap_meta(conn)
    except Exception:
        conn.close()
        raise
    return Journal(p, conn, journal_id)


# Backend registry for the adapter contract suite (B8). A second backend adds
# a registry entry and inherits every contract test; no new test is written.
# The meta-test derives counts from this map and collected node ids — never a
# hand-copied list of test names.
JOURNAL_BACKENDS: dict = {
    "sqlite": open_journal,
}
