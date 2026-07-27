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

- **#397** · landed `1b508b0` · 2026-07-28 09:42 · by ccc @glm52 — design plan: client extraction is mechanically cheap (interpolation count 1) but leans do-not-extract; does not unblock #331/#352 (Python), multiplies the registry damage class, and four named breaks (deploy/serving/autoreload/audit) must ship together if ruled in
## Folded
- **#398** → folded (2026-07-28 09:31): folded into `## Recently landed` citing `9f2012a`; verification owed
- **#392a** · landed `159917b` · 2026-07-28 09:43 · by ccc @glm52 — date-only question ages show ONE figure (paintDayAge, data-day flag); today reads "today"; timed commits keep two figures
