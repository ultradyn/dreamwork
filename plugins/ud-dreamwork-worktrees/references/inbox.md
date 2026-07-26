# Machine-local comms inbox (receipt channel)

c2c DMs wake peers; they are **not** a durable receipt. Durable
peer→coordinator messages for co-agent mode use an append-only inbox the
coordinator owns on the machine.

## Path

```
~/.config/dreamwork/worktrees/<stable-target-slug>/inbox.jsonl
```

- `stable-target-slug`: **deterministic once**, shared with `claims.json`
  (see `file-formats.md`). Not basename-only; no adaptive “hash if collision”
  rule that could change after first use.
- Machine-local, **never committed**, never under `.dreamwork/`.
- Directory created by coordinator on **first co-agent offer** (lazy).

## Schema (one JSON object per line)

```json
{
  "id": "r-20260726T135500Z-01",
  "ts": "2026-07-26T13:55:00Z",
  "from": "grok-sugar-vesi-x6tv",
  "to": "coordinator",
  "kind": "receipt",
  "claim_id": "c-20260726-001",
  "body": {
    "status": "landed",
    "commit": "abc1234",
    "branch": "fix/247-missing-aid",
    "files_owned": ["watch.py"],
    "red": "…",
    "green": "…",
    "verification": "…"
  }
}
```

| Field | Rule |
|-------|------|
| `id` | Unique line id (writer-minted, time-based) |
| `kind` | `receipt` \| `ping` \| `claim_accept` \| `blocked` \| `release_request` \| `ack` |
| `claim_id` | Must match ledger claim when applicable |
| `body` | Kind-specific; receipts follow `evidence.md` fields |

## Writers / readers

| Actor | Append? | Read? |
|-------|---------|--------|
| Peer | yes (`receipt`, `ping`, `claim_accept`, `blocked`, `release_request`) | own cursor optional |
| Coordinator | yes (`ack`) | full file / from cursor |

**Atomic append:** open with `O_APPEND` (or write temp segment + append
under coordinator lock). Never rewrite history lines.

## Receipt + ack contract

1. Peer finishes work → appends `kind:receipt` with full evidence body →
   **then wakes** coordinator (c2c / harness). Write then wake.
2. Coordinator reads new lines, validates against claim ledger, updates
   claim to `ready` or rejects with notes.
3. Coordinator appends `kind:ack` referencing `receipt id` + `claim_id` +
   ledger `revision`.
4. Claim ledger stores `receipt_id` + `ack_revision`.

DMs alone are **not** a receipt. Missing inbox line → no merge.

## Read cursor

Coordinator may keep
`~/.config/dreamwork/worktrees/<slug>/inbox.cursor` (byte offset or last
`id`). Ephemeral; rebuilding from full file is always safe.

## Relation to c2c

c2c = transport/wake. Inbox = durable body. Both required for
`ready`→merge path.
