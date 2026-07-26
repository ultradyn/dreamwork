# File formats owned by ud-dreamwork-worktrees

Plugin-local contract (mirrors core `file-formats.md` discipline).

## Machine-local `claims.json`

Path: `~/.config/dreamwork/worktrees/<stable-target-slug>/claims.json`

- **Writer:** coordinator only (atomic whole-file replace + revision CAS).
- **Shape:** see `claim-ledger.md` (`version`, `revision`, `claims[]`).
- **Missing file:** treat as empty ledger v1; create on demand — **never
  commit** this file into the project.
- **Not** `.dreamwork/co-agent-claims.json` (that path is forbidden).

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
