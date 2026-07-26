# Evidence receipt — worker → coordinator

Return this structure (markdown or plain) when finishing, failing, or
blocking. Silence is not a result.

```markdown
## Evidence receipt

- **status:** landed | blocked | failed | null
- **task:** #N — title
- **branch:** fix/#N-slug
- **worktree:** /abs/path/.worktrees/#N-slug
- **commit hash:** <full or short sha>  (required if landed)
- **files owned:** list paths actually touched
- **files not touched:** confirm parent/tasks/other worktrees clean
- **red proof:** what failed before the fix (command + key FAIL lines)
- **green proof:** commands run + pass summary (pytest, guards, lint, …)
- **verification:** project verification routine result
- **risks / ideas:** optional follow-ups (not silently done)
- **blocked on:** if blocked — question text (also in questions.md if human)
```

## Rules

- **hash** required for `landed`.
- **red** required when a new check was introduced (or state "no new check;
  existing suite only" with justification).
- **green** names exact commands, not "tests passed".
- **files owned** must match the grant; extras are a protocol break.
- Failed/null: still send a receipt — coordinator must not invent success.

## Coordinator gate

No merge without a receipt (or Max override recorded). Spot-check at least
one red→green claim when stakes are high.
