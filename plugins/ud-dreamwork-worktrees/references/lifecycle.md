# Lifecycle — create, validate, merge, cleanup

## Preflight

1. Target is a git repo; `.gitignore` lists `.worktrees/` (migration).
2. Main checkout: coordinator commits its own work first; do not carry
   foreign dirty files into a merge.
3. Choose slug/branch; ensure branch name unused.

## Create

```bash
git worktree add -b fix/#N-slug .worktrees/#N-slug master
# or: git worktree add .worktrees/#N-slug existing-branch
```

Confirm clean baseline: `git status` in the worktree shows the expected
branch and no leftover unowned files.

## Validate (before merge)

- Evidence receipt present (`evidence.md`).
- Independent green sample or cold-read of diff + tests named in receipt.
- Rebase onto current master:
  ```bash
  cd .worktrees/#N-slug
  git fetch origin   # if used
  git rebase master  # or origin/master
  ```
- Conflicts: coordinator resolves or returns to worker — **never** blind
  `-X theirs`.

## Merge

- Prefer merge or ff into master from the **coordinator** session on main
  checkout (or explicit PR if that is the project flow).
- Workers: **no push** unless Max authorized.

## Cleanup (never force-blind)

**Never** as first action:

- `git worktree remove --force`
- `rm -rf .worktrees/<slug>`

**Do:**

1. `git worktree list`
2. In the worktree: `git status -sb` (tracked dirty?)
3. Inspect **untracked and ignored** scratch (`git status --ignored`,
   `find` for local DBs, screenshots, `.pytest_cache` you care about).
4. If valuable scratch exists → copy out or ask Max; abort cleanup.
5. If clean / only disposable, remove the worktree then the merged branch:
   `git worktree remove .worktrees/#N-slug`
   then `git branch -d fix/#N-slug`
6. Clear claim in status / peer registry.

If remove refuses (dirty): stop and report — do **not** `--force` without
Max.

## Failure paths

| Situation | Action |
|-----------|--------|
| Tests red after rebase | fix in worktree or abandon with receipt |
| Worker null result | no merge; reopen task |
| Orphan worktree, no claim | inspect; report maintenance; clean only if empty |
| Conflict with main | coordinator owns resolution |
