# 2026-07-26 — co-agent machine-local claims + plugin version stamp

## What changed

Co-agent mode keeps **runtime claim state machine-local**, not in the
project tree:

```
~/.config/dreamwork/worktrees/<stable-target-slug>/claims.json
~/.config/dreamwork/worktrees/<stable-target-slug>/inbox.jsonl
```

Schemas: plugin `references/claim-ledger.md`, `inbox.md`, `file-formats.md`.

A committed project ledger was rejected: every heartbeat would dirty git,
collide with integrate, and leak peer aliases/paths into the repo
(writing-plugins: ephemera stays under `~/.config/dreamwork/…`).

**Project-side durable state** for this plugin remains only:

- `.gitignore` entry `.worktrees/` (migration 01)
- optional `.dreamwork/worktrees-version` stamp (this migration)

## How to apply

1. Ensure `.worktrees/` is gitignored (migration 01).
2. On first co-agent use, coordinator creates the machine-local directory
   and empty `claims.json` if absent (not committed):

```json
{"version": 1, "revision": 0, "updated": "", "claims": []}
```

3. Optionally write `.dreamwork/worktrees-version`:

```
2026-07-26-02-co-agent-claims
```

4. Do **not** create `.dreamwork/co-agent-claims.json` (obsolete idea).
5. Do **not** invent peer-private claim files under the worktree.

## Consent

Needs: config (machine-local dir; optional version stamp). Safe defaults:
no co-agents until offered; empty claims file created on demand.
