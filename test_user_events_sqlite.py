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

from pathlib import Path

from user_events.sqlite import BUSY_TIMEOUT_MS, open_journal


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
