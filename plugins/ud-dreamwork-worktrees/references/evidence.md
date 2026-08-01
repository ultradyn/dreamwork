# Evidence receipt — worker → coordinator

Return this structure in the **durable inbox** (`inbox.md`, `kind:receipt`)
and/or the subagent final report. c2c text alone is not sufficient for
co-agent merge.

```markdown
## Evidence receipt

- **status:** landed | blocked | failed | null
- **task:** #N — title
- **claim_id:** c-… (co-agent) or n/a (subagent)
- **branch:** fix/N-slug
- **worktree:** /abs/parent/.worktrees/N-slug
- **commit hash:** <sha>  (required if landed)
- **files owned:** paths actually touched under the grant
- **worktree attestation:** `git status` / diff summary **for this
  worktree only** — owned paths clean or listed; do **not** claim
  other actors' checkouts or the main tree are untouched (you cannot
  honestly observe them). Attest: "no edits outside owned paths in
  this worktree" via `git status` + path filter.
- **red proof:** command + key FAIL lines (or justified none)
- **green proof:** commands + pass summary
- **verification:** project verification result
- **cleanup decision:** none | disposable-only | held-for-owner
  (if non-obvious untracked/ignored artifacts exist, name them and
  who decides — do not delete until decided)
- **risks / ideas:** optional
- **blocked on:** if blocked
```

## Rules

- **hash** required for `landed`.
- **files owned** must match the grant; extras are a protocol break.
- **worktree attestation** replaces the old “files not touched” global
  claim — scope is the owned worktree and owned paths only.
- Failed/null: still send a receipt.
- Co-agent: append inbox line **then** wake coordinator; wait for ack
  before assuming merge.

## Coordinator gate

No merge without receipt (+ inbox ack path for co-agent). Spot-check red→green
when stakes are high.
