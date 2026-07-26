# Checklists

## Pre-dispatch (coordinator)

- [ ] Task eligible and unblocked
- [ ] Owned paths listed and **disjoint** from in-flight claims
- [ ] Ports/resources assigned if worker will bind any
- [ ] `.worktrees/` is gitignored
- [ ] Branch name chosen; worktree path free
- [ ] Worktree created from clean baseline (current master tip)
- [ ] Claim recorded (status.json / peers registry)
- [ ] Prompt includes ownership, forbids, red-first, evidence template
- [ ] Wake channel actually delivers (not write-only)

## Pre-merge (coordinator)

- [ ] Evidence receipt present with **hash** (if landed)
- [ ] Red proof credible; green commands re-run or spot-checked
- [ ] Diff limited to owned paths
- [ ] Rebased onto current master; conflicts resolved deliberately
- [ ] Descriptive commit message(s); trailers if migration/feature/consent
- [ ] No push from worker unless authorized
- [ ] Ledger/status update plan ready

## Cleanup

- [ ] `git worktree list` reviewed
- [ ] Worktree `git status` clean of valued work
- [ ] **Untracked + ignored** scratch inspected
- [ ] No `remove --force` / `rm -rf` unless Max approved after inspect
- [ ] Worktree removed; merged branch deleted if appropriate
- [ ] Claim cleared; peer heartbeats updated

## Worker self-check before "done"

- [ ] Only owned paths modified
- [ ] Parent checkout / other worktrees untouched
- [ ] Tests/lint/guards as required — green after red if new checks
- [ ] Commit on branch; explicit path staging
- [ ] Evidence receipt complete
- [ ] No push / merge / deploy / attn
