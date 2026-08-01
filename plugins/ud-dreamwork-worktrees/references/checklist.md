# Checklists

## Pre-dispatch (coordinator)

- [ ] Task eligible; paths disjoint from active claims
- [ ] Ports assigned if needed
- [ ] New root `../.worktrees/` exists; legacy `.worktrees/` remains drain-only
- [ ] Atomic `git worktree add -b fix/N-slug ../.worktrees/N-slug <base>`
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

- [ ] **Process check first** — `occupied.py <worktree>`; if it names a live process, stop (`--force` does not answer this)
- [ ] **Was the agent native?** Then `clear` proves nothing — it owns no cwd here. Check file mtimes and that its completion actually arrived, or you commit over an agent still writing
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
