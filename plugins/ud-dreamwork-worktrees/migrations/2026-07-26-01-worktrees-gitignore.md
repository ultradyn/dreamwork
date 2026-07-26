# 2026-07-26 — ignore `.worktrees/` in the target

## What changed

Isolated agent checkouts live under `.worktrees/` at the target root.
That directory must never be committed: it holds full working trees,
build caches, and agent scratch.

## How to apply

Add one line to the **target's** `.gitignore` if absent:

```
.worktrees/
```

No backfill. Existing accidental commits of `.worktrees/` should be
removed from the index carefully (`git rm -r --cached .worktrees`) only
with human consent — this migration does not do that automatically.

## Consent

Needs: config (gitignore edit). Safe and recommended for any target that
loads `ud-dreamwork-worktrees`.
