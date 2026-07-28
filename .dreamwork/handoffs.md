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
- **#401** · landed `f2c950e` · 2026-07-28 09:47 · by ccc @grok — research: executed id-grammar matrix (14 patterns × 17 forms); #401 silent drop reproduces; 7 silent rejects ranked
- **#392a** · landed `159917b` · 2026-07-28 09:43 · by ccc @glm52 — date-only question ages show ONE figure (paintDayAge, data-day flag); today reads "today"; timed commits keep two figures
- **#401** · landed `e53d70c` · 2026-07-28 10:09 · by ccc @grok — hand-off id grammar accepts plain/sub-id/combined; malformed outside section; Folded-then-Pending so EOF append works (#401+#406)
## Folded
- **#398** → folded (2026-07-28 09:31): folded into `## Recently landed` citing `9f2012a`; verification owed
- **#397** → folded (2026-07-28 09:52): folded into `## Recently landed` citing `1b508b0`; recommendation (do-not-extract) accepted, no ruling requested, worktree alternative filed as #405
- **#401** → folded (2026-07-28 09:58): audit half folded into the `#401` entry citing `f2c950e`; fix half stays open, still needs `watch.py`
- **#392a** → folded (2026-07-28 10:00): verified and closed against `#392`'s entry citing `159917b` — independent red taken in a worktree, deployed page checked (38/38 day-precision, zero two-figure). NOTE: the Pending line above sits **under `## Folded`** (the `cat >>` trap) and is left in place deliberately as `#406`'s fixture.
