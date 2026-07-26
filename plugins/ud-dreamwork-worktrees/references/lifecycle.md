# Lifecycle — create, validate, merge, cleanup

## Preflight

1. Target is a git repo; `.gitignore` lists `.worktrees/`.
2. Co-agent: claims ledger present (empty ok).
3. Branch name free: `fix/N-slug` (no `#`).

## Create

```bash
git worktree add -b fix/N-slug .worktrees/N-slug master
# attach existing branch only when it already exists:
# git worktree add .worktrees/N-slug fix/N-slug
```

Confirm clean baseline on the expected branch.

## Validate (before merge)

- Evidence receipt present (`evidence.md`; co-agent: inbox + ack).
- Spot-check red/green or cold-read.
- Rebase onto current master inside the worktree; resolve conflicts
  deliberately (never blind `-X theirs`).

## Merge

Coordinator (or Max) on main checkout / project PR flow. Workers: **no push**
unless Max authorized.

## Cleanup (never force-blind)

**Never** first:

- `git worktree remove --force`
- `rm -rf .worktrees/<slug>`

**Do:**

1. `git worktree list`
2. Worktree `git status -sb`
3. Inspect **untracked and ignored** scratch (`git status --ignored`).
4. Classify artifacts:
   - **Obviously disposable** (e.g. `__pycache__`, `.pytest_cache`) → may
     remove with worktree.
   - **Non-obvious** (logs, screenshots, local DBs, half-written notes) →
     **owner/coordinator decision required**, recorded in the evidence
     receipt `cleanup decision` field or claim `notes`. Move valuable
     scratch out **before** remove.
5. If clean / disposable-only, remove worktree then merged branch:
   `git worktree remove .worktrees/N-slug`
   then `git branch -d fix/N-slug` when merged.
6. Clear claim ledger entry / status projection.

If remove refuses (dirty): stop and report — do **not** `--force` without
Max after inspect.

## Failure paths

| Situation | Action |
|-----------|--------|
| Tests red after rebase | fix or abandon with receipt |
| Null result | no merge |
| Orphan worktree | inspect; decision; then clean |
| Path conflict | reject new claim |
