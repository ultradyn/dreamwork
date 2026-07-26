# Ownership — files, ports, resources

## File ownership

- Every dispatch names an explicit **owned path list** (files and/or
  directories).
- Two in-flight agents: path sets must be **disjoint**. Overlap → serialize
  or re-scope.
- Shared files (`tasks.md`, `questions.md`, `status.json` shape, core
  `SKILL.md`) stay with the **coordinator** unless a dispatch explicitly
  grants a slice.
- Staging: `git add path1 path2` only. **Never** `git add -A` / `git add .`
  in a multi-agent tree.

## Port and resource ownership

From dreamwork's parallel-architecture norms (reuse, do not invent):

| Range | Owner |
|-------|--------|
| project `watch-port` (e.g. 35110) | coordinator deploy |
| `39890–39899` | whoever holds `watch.py` guards/dev |
| `39880–39889` | whoever holds `dreamhub.py` |
| `39870–39879` | claim in docs before use |

Workers that start servers:

- bind only an owned free port;
- prove the server is **theirs** (e.g. `/data.json` target path) before
  asserting;
- kill what they started in finally/trap.

## No shared-file conflicts

Before dispatch, coordinator checks:

1. status.json / claim registry for overlapping paths;
2. worktree list for abandoned claims on the same paths;
3. ledger in_progress owners.

If unclear, do not dispatch — ask Max or wait.

## Explicit ownership in the prompt

Worker prompt must include a block like:

```
FILE OWNERSHIP (only these):
- watch.py
- dev/capture/foo.mjs
DO NOT TOUCH: parent checkout, tasks.md, other worktrees, …
```
