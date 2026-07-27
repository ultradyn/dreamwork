# Hand-offs — work landed outside the ledger, waiting to be folded

A session that lands work it does **not** own `.dreamwork/tasks.md` for —
every session but the coordinator — appends ONE line under `## Pending`.
The coordinator reads it on every tick, folds each landing into the ledger,
and appends one `→ folded` line under `## Folded`. **Nothing ever moves**:
both sections grow only by append, so two sessions landing work at once
cannot lose each other's line — the property the dreamer inbox has and a
rewrite would not (#381).

One line per landing, mirroring the inbox's one-line-per-report shape.
Required: the task id, the **sha** (what landed), who is claiming it, and a
one-line `what`. The `→ folded` line is how the writer marks one consumed,
and it is itself an append — never a deletion — so a folded hand-off is not
flagged twice.

## Pending

- **#398** · landed `9f2012a` · 2026-07-28 09:26 · by ccc @grok — lint check: post-obligation briefs must mention handoffs.md

## Folded
- **#398** → folded (2026-07-28 09:31): folded into `## Recently landed` citing `9f2012a`; verification owed
