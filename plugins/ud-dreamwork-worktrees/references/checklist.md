# Checklists

## Pre-dispatch (coordinator)

- [ ] Task eligible; paths disjoint from active claims
- [ ] Ports assigned if needed
- [ ] `.worktrees/` gitignored; claims ledger exists (co-agent)
- [ ] Atomic `git worktree add -b fix/N-slug .worktrees/N-slug <base>`
- [ ] Claim recorded (ledger for co-agent; status projection)
- [ ] Prompt: ownership, forbids, red-first, evidence template
- [ ] Wake channel delivers

## Pre-merge

- [ ] Receipt present (co-agent: inbox + ack)
- [ ] Hash if landed; red/green credible
- [ ] Diff limited to owned paths in that worktree
- [ ] Rebased; descriptive commits; trailers if needed
- [ ] Cleanup decision recorded if non-obvious scratch

## Cleanup

- [ ] Inspect untracked + ignored
- [ ] Non-obvious artifacts: decision recorded; move before remove
- [ ] No force remove without Max
- [ ] Claim released; branch deleted if merged

## Worker before “done”

- [ ] Owned paths only (this worktree)
- [ ] Tests green after red if new checks
- [ ] Explicit path staging; commit on branch
- [ ] Receipt complete; co-agent: inbox then wake
- [ ] No push / merge / deploy / attn
