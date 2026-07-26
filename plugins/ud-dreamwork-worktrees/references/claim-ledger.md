# Co-agent claim ledger

**Authoritative durable store (v1):** `.dreamwork/co-agent-claims.json`  
**Writer:** coordinator only (single-writer serialization).  
**Readers:** coordinator on startup/tick; peers read copies the coordinator
sends in protocol messages (peers never write this file).  
**Dashboard:** `.dreamwork/status.json` `agents` may **project** active
claims for the human; it is not the ledger.

## Schema (`version: 1`)

```json
{
  "version": 1,
  "revision": 0,
  "updated": "2026-07-26T14:00:00Z",
  "claims": [
    {
      "id": "c-20260726-001",
      "peer": "grok-sugar-vesi-x6tv",
      "task_id": 247,
      "task": "#247 — missing-aid guard",
      "state": "working",
      "paths": ["watch.py", "dev/capture/answers.mjs"],
      "branch": "fix/247-missing-aid",
      "worktree": ".worktrees/247-missing-aid",
      "offered_at": "2026-07-26T13:50:00Z",
      "claimed_at": "2026-07-26T13:51:00Z",
      "last_seen": "2026-07-26T13:55:00Z",
      "updated": "2026-07-26T13:55:00Z",
      "updated_by": "coordinator",
      "receipt_id": null,
      "ack_revision": null,
      "notes": ""
    }
  ]
}
```

### Field rules

| Field | Rule |
|-------|------|
| `version` | Ledger format; currently `1` |
| `revision` | Monotonic int; every coordinator write +1. CAS token. |
| `claims[].id` | Stable claim id (coordinator-minted) |
| `peer` | c2c alias or harness session id |
| `task_id` / `task` | Ledger task when known |
| `state` | See transitions |
| `paths` | Explicit owned paths; disjoint across **active** claims |
| `branch` | `fix/N-slug` / `feat/N-slug` (no `#`) |
| `worktree` | Relative to target, under `.worktrees/` |
| `last_seen` | Heartbeat / last protocol activity |
| `receipt_id` | Inbox line id of evidence receipt when ready |
| `ack_revision` | Ledger `revision` when coordinator acked receipt |

### Active states (hold paths)

`offered`, `claimed`, `working`, `blocked`, `ready` — path sets must be
**disjoint**. `released` and `stale` free paths.

## States and transitions

| State | Meaning | Who may enter |
|-------|---------|----------------|
| `offered` | Coordinator proposed work | coordinator |
| `claimed` | Peer accepted | coordinator (on peer accept msg) |
| `working` | Peer coding | coordinator (on peer progress/heartbeat) |
| `blocked` | Peer needs decision | coordinator (on peer blocked msg) |
| `ready` | Receipt written; awaiting merge | coordinator (on receipt+ack path) |
| `released` | Done or abandoned; paths free | coordinator |
| `stale` | Missed heartbeats; paths free after inspect | coordinator |

```
offered → claimed → working ⇄ blocked → working → ready → released
                 ↘ stale
any active → released (coordinator cancel)
any active → stale (heartbeat policy)
stale → released (after cleanup decision)
```

Peers **request** transitions via protocol + inbox; the coordinator is the
only party that mutates the ledger. Conflicting claims (path overlap,
unknown claim id, stale revision on a CAS write) → **reject**, leave
prior state, message peer.

## CAS / serialization

1. Coordinator reads ledger, notes `revision`.
2. Applies one transition in memory.
3. Writes whole file with `revision+1` via atomic replace (temp + rename).
4. If another coordinator write interleaved, re-read and retry — never
   partial merge of two writers. (v1: one coordinator process.)

Peers never CAS-write the ledger.

## Startup reconstruction

1. Load `.dreamwork/co-agent-claims.json` (missing → `{version:1,revision:0,claims:[]}`).
2. `git worktree list`; match worktrees to claims.
3. Active claims with missing worktree → `blocked` or `stale` + notes.
4. Project active claims into status.json for the dashboard (optional).

## Staleness

Default: no `last_seen` for 3× expected peer heartbeat (e.g. 3×4.5m).
Coordinator sets `stale`, does **not** delete worktree until cleanup
checklist + owner decision.

## Worked example

1. Coordinator offers task #247, paths `[watch.py]`, mints `c-001`, state
   `offered`, revision 1→2.
2. Peer DMs accept → coordinator sets `claimed`, records branch/worktree.
3. Peer heartbeats → `working`, `last_seen` updates.
4. Peer appends evidence receipt to machine-local inbox (`receipt_id=r9`),
   wakes coordinator.
5. Coordinator validates receipt → `ready`, `ack_revision=N`, acks in
   ledger + optional inbox ack line.
6. Merge + cleanup → `released`.

## Migration / version

Plugin migration stamps `.dreamwork/worktrees-version` and may create an
empty ledger. See `migrations/` and `references/file-formats.md`.
