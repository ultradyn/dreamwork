# 2026-07-26 — co-agent claims ledger + plugin version stamp

## What changed

Co-agent mode uses a durable coordinator-owned ledger at
`.dreamwork/co-agent-claims.json` (schema in plugin
`references/claim-ledger.md` / `references/file-formats.md`). Machine-local
receipt inbox under `~/.config/dreamwork/worktrees/<slug>/` is created on
demand (not committed).

## How to apply

1. Ensure `.worktrees/` is gitignored (prior migration).
2. Create empty ledger if absent:

```json
{"version": 1, "revision": 0, "updated": "", "claims": []}
```

3. Write `.dreamwork/worktrees-version` with this migration id:

```
2026-07-26-02-co-agent-claims
```

4. Do **not** invent peer claim files under the worktree.

## Consent

Needs: config (new `.dreamwork/` files). Safe defaults: empty ledger, no
co-agents until offered.
