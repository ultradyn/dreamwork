# Subagent mode — one task, one worktree

Coordinator launches a **bounded** agent for normally **one task**. Fresh
context; no multi-day career in one worktree.

## Dispatch (coordinator)

1. **Eligibility:** task unblocked; owned paths disjoint from every
   in-flight claim (ledger + status).
2. **Baseline:** main checkout free of coordinator’s uncommitted work.
3. **Branch + worktree** (atomic — avoids orphan branch if add fails):

```bash
git fetch origin   # if remote tracking matters
git worktree add -b fix/N-slug ../.worktrees/N-slug origin/master
# or: git worktree add -b fix/N-slug ../.worktrees/N-slug master
```

Branch names: `fix/N-slug`, `feat/N-slug` (ledger id **without** `#` —
matches repo style like `feat/answers-page`, safer in shells/comments).

4. **Record** ownership (status projection; subagent need not use co-agent
   ledger unless also a co-agent).
5. **Prompt** with goal, acceptance, file ownership list, worktree path,
   branch, red-first, forbids (push/merge/deploy/attn/parent), evidence
   template (`evidence.md`).
6. **Wake** the worker (harness/c2c). Write alone is not delivery.

## Worker obligations

- Only worktree + owned paths.
- Red first for new checks; verify; commit with descriptive body; stage by
  explicit path.
- Trailers when true: `Migration:`, `Feature:`, `Needs: config|consent`.
- Evidence receipt; no merge.

## Integration (coordinator)

Independent sample → rebase onto master → merge → deploy if needed →
cleanup (`lifecycle.md`) → clear claims/projection.

## Failure / null

Blocked/null/vanished → receipt or stale handling; no fake green; inspect
before delete.
