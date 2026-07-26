# Subagent mode — one task, one worktree

Coordinator launches a **bounded** agent for normally **one task** (one
increment batch). Fresh context; no multi-day career in one worktree.

## Dispatch (coordinator)

1. **Eligibility:** task unblocked; owned paths disjoint from every
   in-flight claim (see `ownership.md`).
2. **Baseline:** main checkout clean of *your* uncommitted work; note
   foreign dirty paths and do not stage them.
3. **Branch + worktree:**
   ```bash
   git fetch origin   # if remote tracking matters
   git branch fix/#N-slug origin/master   # or master
   git worktree add .worktrees/#N-slug fix/#N-slug
   ```
4. **Record claim** in `.dreamwork/status.json` agents (paths, worktree
   path, branch, task id, started).
5. **Prompt** the worker with: goal, acceptance, **file ownership list**,
   worktree absolute path, branch, red-first requirement, forbid
   push/merge/deploy/attn/parent edits, evidence receipt template.
6. **Wake** the worker (harness message / c2c). Writing a file alone is
   not delivery.

## Worker obligations

- Work only under the worktree and owned paths.
- **Red first** for new checks; then implement; verify.
- Commit on the branch with a descriptive subject + body; stage by
  **explicit path** (never `git add -A` while others may share a tree).
- Trailers when true: `Migration:`, `Feature:`, `Needs: config|consent`.
- Return the **evidence receipt** (`evidence.md`); do not merge.

## Integration (coordinator)

1. Independent sample of red/green or cold-read of the receipt.
2. `git fetch` / rebase branch onto current master inside the worktree
   (or rebase after attach); resolve conflicts deliberately.
3. Merge to master (ff-only preferred when possible).
4. Deploy only if the surface requires it and policy allows.
5. **Cleanup** per `lifecycle.md` (inspect scratch first).
6. Clear the claim in status.json; fold ledger line if needed.

## Failure / null

- Worker blocked → receipt with `status: blocked` + question text; no
  fake green.
- Worker vanished → coordinator marks claim stale; inspect worktree;
  do not delete until scratch reviewed.
- Empty result with "done" → reject; require hash or explicit null.
