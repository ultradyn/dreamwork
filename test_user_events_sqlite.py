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
- B5: lease_until > <backend now> predicate in the claim UPDATE
      → test_expired_lease_is_reclaimable_and_the_stale_claimant_cannot_finish
- B6: expected == stored_chain_hash comparison in advance_cursor
      → test_broken_chain_forces_rebuild_not_a_silent_advance
- B7: UNIQUE(client_action_id) constraint in the schema
      → test_two_processes_one_uuid_make_one_receipt
- B8: registry entry for a backend
      → test_every_contract_test_runs_under_every_registered_backend

Must not fake (plan): second connection for pragmas; no raw INSERT for B2;
no H_i formula copy for B3; revisions read back from store for B4;
no patched clock for B5; processes not threads for B7; no hand-copied
contract-test list for B8.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import time
import uuid
from pathlib import Path

from user_events.sqlite import BUSY_TIMEOUT_MS, Envelope, open_journal


# ---------------------------------------------------------------------------
# B7 — module-level child entry (must be picklable under spawn)
# ---------------------------------------------------------------------------

def _b7_child_receive(
    path: str,
    action_id: str,
    body: bytes,
    barrier: "mp.synchronize.Barrier",
    result_queue: "mp.queues.Queue",
) -> None:
    """One OS process: wait on barrier, then receive() the same UUID+bytes."""
    # Report pid before barrier so the parent can assert distinct interpreters
    # even if receive() hangs.
    pid = os.getpid()
    try:
        barrier.wait(timeout=30)
        j = open_journal(path)
        try:
            env = Envelope(
                client_action_id=action_id,
                protocol_version="1",
                method="POST",
                route="/answer",
                content_type="application/json",
                body=body,
            )
            r = j.receive(env)
            result_queue.put(
                {
                    "pid": pid,
                    "kind": r.kind,
                    "receipt_id": r.receipt_id,
                    "sequence": r.sequence,
                    "request_digest": r.request_digest,
                    "ok": True,
                    "error": None,
                }
            )
        finally:
            j.close()
    except Exception as exc:  # noqa: BLE001 — surface to parent
        result_queue.put(
            {
                "pid": pid,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "kind": None,
                "receipt_id": None,
            }
        )


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


def test_rejected_receipt_can_never_be_claimed(tmp_path: Path):
    """A rejected receipt is refused by claim(); validated can be claimed.

    Revisions are read back from the store between calls — never tracked in
    the test. Red line: AND state = 'validated' in the claim UPDATE.
    """
    path = tmp_path / "j.sqlite3"
    j = open_journal(path)
    try:
        # --- rejected path ---
        ins = j.receive(_envelope(body=b'{"text":"reject-me"}'))
        assert ins.kind == "inserted"
        # Read revision from the store (must not remember ins.revision alone).
        stored = j.get_receipt(ins.receipt_id)
        assert stored is not None
        rev = stored["revision"]
        tr = j.transition(ins.receipt_id, "rejected", expected_revision=rev)
        assert tr.kind == "applied", f"reject transition failed: {tr!r}"
        stored = j.get_receipt(ins.receipt_id)
        assert stored["state"] == "rejected"
        rev = stored["revision"]
        claim = j.claim(
            ins.receipt_id,
            consumer="worker-a",
            lease_seconds=30,
            expected_revision=rev,
        )
        assert claim.kind == "refused", (
            f"rejected receipt must not be claimable, got kind={claim.kind!r}"
        )
        stored = j.get_receipt(ins.receipt_id)
        assert stored["state"] == "rejected", (
            "claim must not move a rejected receipt out of rejected"
        )

        # --- validated path (discriminating half: claim works when validated) ---
        ins2 = j.receive(_envelope(body=b'{"text":"validate-me"}'))
        stored = j.get_receipt(ins2.receipt_id)
        rev = stored["revision"]
        tr2 = j.transition(ins2.receipt_id, "validated", expected_revision=rev)
        assert tr2.kind == "applied"
        stored = j.get_receipt(ins2.receipt_id)
        assert stored["state"] == "validated"
        rev = stored["revision"]
        claim2 = j.claim(
            ins2.receipt_id,
            consumer="worker-a",
            lease_seconds=30,
            expected_revision=rev,
        )
        assert claim2.kind == "claimed", (
            f"validated receipt must be claimable, got kind={claim2.kind!r}; "
            "without this half, a claim that always refuses passes"
        )
        stored = j.get_receipt(ins2.receipt_id)
        assert stored["state"] == "claimed"
    finally:
        j.close()


def test_stale_revision_transition_is_refused(tmp_path: Path):
    """A transition with a stale expected_revision does not mutate state.

    Revisions are read back from the store; the test does not keep its own
    counter across successful transitions.
    """
    path = tmp_path / "j.sqlite3"
    j = open_journal(path)
    try:
        ins = j.receive(_envelope(body=b'{"text":"stale-check"}'))
        stored = j.get_receipt(ins.receipt_id)
        rev = stored["revision"]
        # First transition succeeds and advances revision.
        ok = j.transition(ins.receipt_id, "validated", expected_revision=rev)
        assert ok.kind == "applied"
        after = j.get_receipt(ins.receipt_id)
        assert after["state"] == "validated"
        assert after["revision"] == rev + 1
        # Re-using the pre-transition revision must be stale.
        stale = j.transition(
            ins.receipt_id, "rejected", expected_revision=rev
        )
        assert stale.kind == "stale", (
            f"stale expected_revision must be refused, got {stale.kind!r}"
        )
        still = j.get_receipt(ins.receipt_id)
        assert still["state"] == "validated", (
            "stale transition must not change state"
        )
        assert still["revision"] == after["revision"], (
            "stale transition must not advance revision"
        )
    finally:
        j.close()


def test_two_processes_one_uuid_make_one_receipt(tmp_path: Path):
    """B7: two real OS processes, one UUID+bytes → exactly one receipt.

    PRODUCTION LINE WHOSE DELETION MUST FAIL THIS TEST:
      UNIQUE(client_action_id) on receipts in the schema.

    Threads are not processes. A threaded version of this test passes with no
    database constraint at all — that is #262's bug reproduced as a green test.
    Children are multiprocessing spawn workers in separate interpreters; we
    assert distinct os.getpid() values at runtime.
    """
    path = tmp_path / "twoproc.sqlite3"
    # Create schema once in the parent so both children open an existing file.
    parent = open_journal(path)
    parent.close()

    action_id = str(uuid.uuid4())
    body = b'{"text":"concurrent-same-uuid"}'
    # spawn = separate interpreters (not fork of this one).
    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(2)
    result_queue = ctx.Queue()

    procs = [
        ctx.Process(
            target=_b7_child_receive,
            args=(str(path), action_id, body, barrier, result_queue),
        )
        for _ in range(2)
    ]
    for p in procs:
        p.start()
    results = []
    try:
        for _ in range(2):
            # Bounded wait — load on this box is high; never hang forever.
            results.append(result_queue.get(timeout=60))
        for p in procs:
            p.join(timeout=30)
            assert p.exitcode == 0, f"child exitcode={p.exitcode}"
    finally:
        for p in procs:
            if p.is_alive():
                p.kill()
                p.join(timeout=5)

    assert len(results) == 2, f"expected 2 results, got {len(results)}"
    for r in results:
        assert r.get("ok"), f"child failed: {r.get('error')}"

    pids = {r["pid"] for r in results}
    assert len(pids) == 2, (
        f"children must be separate OS processes with distinct pids; got {pids}. "
        "If pids collide this is threads or the same process twice."
    )
    # Parent is a third pid — belt and braces against accidental in-process call.
    assert os.getpid() not in pids

    kinds = {r["kind"] for r in results}
    assert kinds <= {"inserted", "replay"}, (
        f"both results must be insert-or-replay (202-shaped), got kinds={kinds}"
    )
    assert "inserted" in kinds or all(r["kind"] == "replay" for r in results), (
        "at least the racing winner inserts; both-replay is only ok if a prior "
        "row existed — it does not here"
    )
    # Exactly one of the two is the insert; the other is the replay. (If both
    # report inserted without UNIQUE, that is the bug this test exists to catch.)
    inserted = [r for r in results if r["kind"] == "inserted"]
    assert len(inserted) == 1, (
        f"exactly one process must insert; got inserted={len(inserted)} "
        f"kinds={[r['kind'] for r in results]}"
    )
    receipt_ids = {r["receipt_id"] for r in results}
    assert len(receipt_ids) == 1 and None not in receipt_ids, (
        f"both must share one receipt_id, got {receipt_ids}"
    )

    # Authoritative count from a fresh open — not from the children's memory.
    j = open_journal(path)
    try:
        assert j.receipt_count() == 1, (
            f"two processes same UUID must leave exactly one receipt row; "
            f"got {j.receipt_count()}"
        )
    finally:
        j.close()


def _validate(j, receipt_id: str) -> int:
    """Transition received→validated; return the new revision from the store."""
    stored = j.get_receipt(receipt_id)
    assert stored is not None
    tr = j.transition(
        receipt_id, "validated", expected_revision=stored["revision"]
    )
    assert tr.kind == "applied", f"validate failed: {tr!r}"
    stored = j.get_receipt(receipt_id)
    assert stored["state"] == "validated"
    return stored["revision"]


def test_expired_lease_is_reclaimable_and_the_stale_claimant_cannot_finish(
    tmp_path: Path,
):
    """B5: real short lease; after expiry a reclaimer wins; stale cannot finish.

    PRODUCTION LINE WHOSE DELETION MUST FAIL THIS TEST:
      the `lease_until > <backend now>` predicate in the claim UPDATE
      (written as NOT (lease_until > ?)). Without it, a second consumer can
      reclaim while the first lease is still active.

    Must not patch the clock. Backend/server time only. Assert at runtime that
    observed elapsed time exceeded the lease — a sleep that returned early on a
    loaded box would otherwise make the test pass vacuously.
    """
    path = tmp_path / "claims.sqlite3"
    j = open_journal(path)
    try:
        ins = j.receive(_envelope(body=b'{"text":"lease-me"}'))
        assert ins.kind == "inserted"
        rev = _validate(j, ins.receipt_id)

        lease_seconds = 1
        # --- first claimant ---
        claim_a = j.claim(
            ins.receipt_id,
            consumer="worker-a",
            lease_seconds=lease_seconds,
            expected_revision=rev,
        )
        assert claim_a.kind == "claimed", f"first claim failed: {claim_a!r}"
        assert claim_a.claim_token
        token_a = claim_a.claim_token
        rev_a = claim_a.revision
        assert rev_a is not None

        # While the lease is active, a second consumer must be refused.
        # This is what makes the lease_until predicate load-bearing: without
        # it, reclaim would succeed here and the sleep would be decorative.
        stored = j.get_receipt(ins.receipt_id)
        early = j.claim(
            ins.receipt_id,
            consumer="worker-b",
            lease_seconds=lease_seconds,
            expected_revision=stored["revision"],
        )
        assert early.kind == "refused", (
            f"active lease must refuse reclaim, got kind={early.kind!r}; "
            "if this passes as claimed, the lease_until > now predicate is gone"
        )

        # Real sleep past the lease. No monkeypatched time.
        t0 = time.monotonic()
        time.sleep(lease_seconds + 0.6)
        elapsed = time.monotonic() - t0
        assert elapsed > lease_seconds, (
            f"observed elapsed {elapsed:.3f}s did not exceed lease "
            f"{lease_seconds}s — sleep returned early; refuse to pass vacuously"
        )

        # --- reclaimer after expiry ---
        stored = j.get_receipt(ins.receipt_id)
        claim_b = j.claim(
            ins.receipt_id,
            consumer="worker-b",
            lease_seconds=30,
            expected_revision=stored["revision"],
        )
        assert claim_b.kind == "claimed", (
            f"expired lease must be reclaimable, got kind={claim_b.kind!r}"
        )
        assert claim_b.claim_token != token_a
        assert claim_b.revision != rev_a

        # Stale claimant (worker-a with old token/revision) cannot finish.
        finish_a = j.finish(
            ins.receipt_id,
            claim_token=token_a,
            consumer="worker-a",
            expected_revision=rev_a,
        )
        assert finish_a.kind in ("refused", "stale"), (
            f"stale claimant must not finish, got kind={finish_a.kind!r}"
        )
        stored = j.get_receipt(ins.receipt_id)
        assert stored["state"] == "claimed", (
            "stale finish must leave the receipt claimed by the reclaimer"
        )
        assert stored["claim_consumer"] == "worker-b"

        # Reclaimer can finish.
        finish_b = j.finish(
            ins.receipt_id,
            claim_token=claim_b.claim_token,
            consumer="worker-b",
            expected_revision=claim_b.revision,
        )
        assert finish_b.kind == "finished", f"reclaimer finish failed: {finish_b!r}"
        stored = j.get_receipt(ins.receipt_id)
        assert stored["state"] == "applied"
    finally:
        j.close()


def test_broken_chain_forces_rebuild_not_a_silent_advance(tmp_path: Path):
    """B6: corrupt below high water → advance_cursor refuses; rebuild counts.

    PRODUCTION LINE WHOSE DELETION MUST FAIL THIS TEST:
      the `expected == stored_chain_hash` comparison in advance_cursor.
      (Also load-bearing: verify_chain / rebuild — without it a broken chain
      with a still-matching stored high-water hash would silent-advance.)

    ordinals_read is asserted against a runtime-derived total, never a literal.
    """
    path = tmp_path / "cursor.sqlite3"
    j = open_journal(path)
    try:
        bodies = [b'{"n":0}', b'{"n":1}', b'{"n":2}', b'{"n":3}']
        for body in bodies:
            r = j.receive(_envelope(body=body))
            assert r.kind == "inserted"
        high = j.head_ordinal()
        # Runtime-derived total the rebuild must examine.
        assert high == len(bodies), (
            f"precondition: high water {high} must equal fixture size {len(bodies)}"
        )
        assert high >= 2, "precondition: need a low ordinal below high water"

        # Honest advance first: expected is the verified head.
        head = j.head_hash()
        ok = j.advance_cursor("consumer-a", expected=head, scanned_through=high)
        assert ok.kind == "advanced", f"clean advance failed: {ok!r}"
        assert ok.ordinals_read == high

        # Reset cursor by opening path — cursor is durable; re-advance from a
        # second consumer so we do not depend on rewriting the first.
        # Corrupt ordinal 1's stored hash; high-water ordinal stays put.
        j.conn.execute(
            "UPDATE events SET event_hash = ? WHERE event_ordinal = 1",
            ("0" * 64,),
        )
        j.conn.commit()
        assert j.head_ordinal() == high, "precondition: high water unchanged"

        # Caller still holds the pre-corruption head (or the stored high hash —
        # either way the chain is broken below). advance must refuse and the
        # rebuild path must have read every ordinal through high.
        # Use the *stored* high-water hash (unchanged by low-ordinal corruption)
        # as expected: without verify/rebuild this would silent-advance.
        stored_high = j.conn.execute(
            "SELECT event_hash FROM events WHERE event_ordinal = ?",
            (high,),
        ).fetchone()[0]
        refused = j.advance_cursor(
            "consumer-b", expected=stored_high, scanned_through=high
        )
        assert refused.kind == "refused", (
            f"broken chain must refuse advance, got kind={refused.kind!r}; "
            "silent advance means verify/rebuild is gone"
        )
        assert refused.rebuild is True
        assert refused.ordinals_read == high, (
            f"rebuild must examine every ordinal through high={high}, "
            f"got ordinals_read={refused.ordinals_read}"
        )
        # Cursor for consumer-b must not have advanced.
        cur = j.cursor("consumer-b")
        assert cur.scanned_through_event_ordinal == 0

        # Discriminating half of the B6 red: with a good chain, a *wrong*
        # expected must also refuse (this is the expected == stored comparison).
        # Rebuild a fresh journal for an unbroken chain.
    finally:
        j.close()

    path2 = tmp_path / "cursor-expected.sqlite3"
    j2 = open_journal(path2)
    try:
        for body in (b'{"x":1}', b'{"x":2}'):
            assert j2.receive(_envelope(body=body)).kind == "inserted"
        high2 = j2.head_ordinal()
        wrong = "f" * 64
        real = j2.head_hash()
        assert wrong != real, "precondition: wrong expected must differ from head"
        bad = j2.advance_cursor(
            "consumer-c", expected=wrong, scanned_through=high2
        )
        assert bad.kind == "refused", (
            f"wrong expected must refuse, got kind={bad.kind!r}; "
            "if this advances, the expected == stored_chain_hash comparison is gone"
        )
        assert bad.reason == "expected_mismatch"
    finally:
        j2.close()
