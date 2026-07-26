# File formats owned by ud-dreamwork-worktrees

Plugin-local contract (mirrors core `file-formats.md` discipline). Target
files the loop or coordinator parse must match these shapes.

## `.dreamwork/co-agent-claims.json`

- **Writer:** coordinator only.
- **Shape:** see `claim-ledger.md` (`version`, `revision`, `claims[]`).
- **Missing file:** treat as empty ledger v1.
- **Lint (plugin tests):** schema examples + transition table must stay
  aligned with this doc.

## `.dreamwork/worktrees-version`

- One line: migration id last applied for this plugin, e.g.
  `2026-07-26-02-co-agent-claims`.
- Written when migrations run at plugin init.

## `~/.config/dreamwork/worktrees/<slug>/inbox.jsonl`

- Machine-local append-only; see `inbox.md`.
- Not in git; not under `.dreamwork/`.

## Non-formats

- Peers do **not** get a private claim file.
- `status.json` agents block may **mirror** active claims for UI only.
