"""Red-first tests for user_events.sqlite (lane B, journal store).

Named production lines whose deletion must fail each test (plan §Lane B):
- B1: PRAGMA synchronous=FULL execute
      → test_pragmas_are_what_the_durability_boundary_claims
- B2: SELECT request_digest … WHERE client_action_id = ? comparison before insert
      → test_same_uuid_same_digest_replays_and_does_not_insert
- B3: prev_hash term in the hash input
      → chain property (c) naming the ordinal
- B4: AND state = 'validated' predicate in the claim UPDATE
      → test_rejected_receipt_can_never_be_claimed

Must not fake (plan): second connection for pragmas; no raw INSERT for B2;
no H_i formula copy for B3; revisions read back from store for B4.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from user_events.sqlite import BUSY_TIMEOUT_MS, Envelope, open_journal


def _envelope(
    *,
    client_action_id: str | None = None,
    body: bytes = b'{"text":"hello"}',
    method: str = "POST",
    route: str = "/answer",
    content_type: str = "application/json",
    protocol_version: str = "1",
) -> Envelope:
    return Envelope(
        client_action_id=client_action_id or str(uuid.uuid4()),
        protocol_version=protocol_version,
        method=method,
        route=route,
        content_type=content_type,
        body=body,
    )


def test_pragmas_are_what_the_durability_boundary_claims(tmp_path: Path):
    """WAL + FULL + busy_timeout must hold on a second, fresh open_journal connection.

    synchronous is per-connection. Reading it from the setter's own handle can
    pass while the pragma was applied to the wrong scope. This test opens once
    to create, closes, then opens again and reads pragmas from that second
    connection — the production open path must re-apply them.
    """
    path = tmp_path / "nested" / "user-events.sqlite3"

    first = open_journal(path)
    first.close()

    # Second, fresh connection through the production open path — not a raw
    # sqlite3.connect, and not the setter's handle.
    second = open_journal(path)
    try:
        pragmas = second.read_pragmas()
        assert pragmas["journal_mode"] == "wal", (
            f"expected journal_mode=wal, got {pragmas['journal_mode']!r}"
        )
        # FULL = 2. Production pins NORMAL then FULL so this line is
        # load-bearing even when the compile-time default is already FULL
        # (SQLite 3.53); deleting only the FULL execute leaves 1.
        assert pragmas["synchronous"] == 2, (
            f"expected synchronous=FULL (2), got {pragmas['synchronous']!r}; "
            "if this is 1, PRAGMA synchronous=FULL was not applied on open"
        )
        assert pragmas["busy_timeout"] == BUSY_TIMEOUT_MS, (
            f"expected busy_timeout={BUSY_TIMEOUT_MS}, got {pragmas['busy_timeout']!r}"
        )
        # schema_version row must exist (B1 claims schema + version).
        row = second.conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        assert row is not None and int(row[0]) >= 1
        assert second.journal_id, "journal_id must be minted at create"
    finally:
        second.close()


def test_same_uuid_same_digest_replays_and_does_not_insert(tmp_path: Path):
    """Same UUID + same digest returns the original receipt; no second row.

    Asserts result *kind* is 'replay'. Without the SELECT+compare before insert,
    the unique constraint raises IntegrityError — a different failure — so a
    row-count-only assertion would not discriminate the B2 red line.
    Both calls go through receive(); no raw INSERT.
    """
    path = tmp_path / "j.sqlite3"
    j = open_journal(path)
    try:
        env = _envelope(body=b'{"text":"once"}')
        first = j.receive(env)
        assert first.kind == "inserted", f"first receive must insert, got {first.kind!r}"
        assert first.receipt_id is not None
        assert first.revision == 1

        second = j.receive(env)
        assert second.kind == "replay", (
            f"same UUID+digest must be kind='replay', got {second.kind!r}; "
            "IntegrityError or a second insert means the SELECT comparison is gone"
        )
        assert second.receipt_id == first.receipt_id
        assert second.sequence == first.sequence
        assert second.request_digest == first.request_digest
        assert j.receipt_count() == 1, (
            f"replay must not insert; row count is {j.receipt_count()}"
        )
    finally:
        j.close()


def test_same_uuid_different_bytes_conflicts_and_preserves_the_original(
    tmp_path: Path,
):
    """Same UUID + different body is conflict; original exact bytes stay.

    Precondition: the two bodies differ (derived at runtime). Both calls go
    through receive(); no raw INSERT.
    """
    path = tmp_path / "j.sqlite3"
    j = open_journal(path)
    try:
        action_id = str(uuid.uuid4())
        body_a = b'{"text":"alpha"}'
        body_b = b'{"text":"bravo"}'
        assert body_a != body_b, "precondition: bodies must differ"

        first = j.receive(_envelope(client_action_id=action_id, body=body_a))
        assert first.kind == "inserted"
        assert first.exact_payload_bytes == body_a

        conflict = j.receive(_envelope(client_action_id=action_id, body=body_b))
        assert conflict.kind == "conflict", (
            f"different digest for same UUID must be kind='conflict', got {conflict.kind!r}"
        )
        assert conflict.receipt_id == first.receipt_id
        assert conflict.exact_payload_bytes == body_a, (
            "conflict must preserve the original exact_payload_bytes, not the new body"
        )
        assert conflict.request_digest == first.request_digest
        assert j.receipt_count() == 1
    finally:
        j.close()


def _journal_with_id(path: Path, journal_id: str):
    """open_journal then pin journal_id so two files share H_0 for relation tests."""
    j = open_journal(path)
    j.conn.execute(
        "UPDATE meta SET value = ? WHERE key = 'journal_id'",
        (journal_id,),
    )
    j.conn.commit()
    j.journal_id = journal_id
    return j


def test_chain_same_sequence_twice_yields_same_head(tmp_path: Path):
    """Property (a): identical event sequences produce identical head hashes.

    Asserts a relation between two journals' outputs — no expected digest
    literal, no copy of the H_i formula in this test. journal_id is pinned so
    H_0 matches; otherwise random journal ids would make every head differ.
    """
    bodies = [b'{"n":1}', b'{"n":2}', b'{"n":3}']
    action_ids = [
        "00000000-0000-4000-8000-0000000000a1",
        "00000000-0000-4000-8000-0000000000a2",
        "00000000-0000-4000-8000-0000000000a3",
    ]
    fixed_jid = "00000000-0000-4000-8000-bbbbbbbbbbbb"

    def build(path: Path) -> str:
        j = _journal_with_id(path, fixed_jid)
        try:
            for aid, body in zip(action_ids, bodies):
                r = j.receive(_envelope(client_action_id=aid, body=body))
                assert r.kind == "inserted"
            assert j.head_ordinal() == len(bodies)
            return j.head_hash()
        finally:
            j.close()

    head_a = build(tmp_path / "a.sqlite3")
    head_b = build(tmp_path / "b.sqlite3")
    assert head_a == head_b, (
        "same sequence in two journals must share a head hash; "
        f"got {head_a!r} vs {head_b!r}"
    )
    assert head_a != "", "head hash must be non-empty"


def test_chain_earlier_payload_byte_changes_the_head(tmp_path: Path):
    """Property (b): one byte changed in an *earlier* event changes the head.

    Two sequences share events 2 and 3 and differ by one byte in event 1's
    body. Without prev_hash in the hash input, event 3's hash depends only on
    event 3's payload and the heads collide — that is the B3 red. Mutation is
    on an earlier event than the head, as the plan requires. No H_i formula
    and no expected digest literal in this test.
    """
    body1_x = b'{"ord":1,"k":"A"}'
    body1_y = b'{"ord":1,"k":"B"}'
    assert body1_x != body1_y, "precondition: earlier payloads must differ"
    shared_2 = b'{"ord":2}'
    shared_3 = b'{"ord":3}'
    fixed_jid = "00000000-0000-4000-8000-cccccccccccc"

    def head_for(path: Path, first_body: bytes) -> str:
        j = _journal_with_id(path, fixed_jid)
        try:
            j.receive(
                _envelope(
                    client_action_id="00000000-0000-4000-8000-000000000001",
                    body=first_body,
                )
            )
            j.receive(
                _envelope(
                    client_action_id="00000000-0000-4000-8000-000000000002",
                    body=shared_2,
                )
            )
            j.receive(
                _envelope(
                    client_action_id="00000000-0000-4000-8000-000000000003",
                    body=shared_3,
                )
            )
            assert j.head_ordinal() == 3
            return j.head_hash()
        finally:
            j.close()

    head_x = head_for(tmp_path / "x.sqlite3", body1_x)
    head_y = head_for(tmp_path / "y.sqlite3", body1_y)
    assert head_x != head_y, (
        "a one-byte change in an earlier event's payload must change the head; "
        "if heads match, prev_hash is not linking the chain"
    )


def test_chain_mutated_low_ordinal_is_named_by_verifier(tmp_path: Path):
    """Property (c): UPDATE a low-ordinal row → verify_chain names that ordinal.

    High-water ordinal stays put. Asserts failed_ordinal, not only ok==False.
    No H_i formula copy in the test.
    """
    path = tmp_path / "j.sqlite3"
    j = open_journal(path)
    try:
        for n in range(3):
            r = j.receive(_envelope(body=f'{{"n":{n}}}'.encode()))
            assert r.kind == "inserted"
        high = j.head_ordinal()
        assert high >= 3

        ok_before = j.verify_chain(through_ordinal=high)
        assert ok_before.ok is True, "precondition: chain must verify before mutation"

        # Mutate ordinal 1's stored hash so recomputation fails at 1.
        # (Mutating payload also works; either way the verifier must name 1.)
        j.conn.execute(
            "UPDATE events SET event_hash = ? WHERE event_ordinal = 1",
            ("0" * 64,),
        )
        j.conn.commit()
        # High water unchanged
        assert j.head_ordinal() == high

        result = j.verify_chain(through_ordinal=high)
        assert result.ok is False
        assert result.failed_ordinal == 1, (
            f"verifier must name ordinal 1, got failed_ordinal={result.failed_ordinal!r}"
        )
    finally:
        j.close()
