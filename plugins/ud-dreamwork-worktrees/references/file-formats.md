# File formats owned by ud-dreamwork-worktrees

Plugin-local contract (mirrors core `file-formats.md` discipline).

## `stable-target-slug` (deterministic)

Used for both `claims.json` and `inbox.jsonl` under
`~/.config/dreamwork/worktrees/<stable-target-slug>/`.

Compute once from the target’s resolved absolute path:

1. `abs = os.path.realpath(target)`
2. `base = re.sub(r'[^a-zA-Z0-9._-]+', '-', os.path.basename(abs)).strip('-') or 'target'`
3. `digest = sha256(abs.encode('utf-8')).hexdigest()[:12]`
4. `stable-target-slug = f"{base}-{digest}"`

No adaptive collision rule. Two checkouts with the same basename get
different digests; renaming the directory changes the slug (new empty
state — expected for machine-local paths).

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
