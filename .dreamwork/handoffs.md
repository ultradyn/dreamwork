# Hand-offs — work landed outside the ledger, waiting to be folded

A session that lands work it does **not** own `.dreamwork/tasks.md` for —
every session but the coordinator — appends ONE line under `## Pending`.
The coordinator reads it on every tick, folds each landing into the ledger,
and appends one `→ folded` line under `## Folded`. **Nothing ever moves**:
both sections grow only by append, so two sessions landing work at once
cannot lose each other's line — the property the dreamer inbox has and a
rewrite would not (#381).

**Section order (#406):** `## Folded` first, then `## Pending`, so an EOF
append lands under Pending and the instruction is true without a rewrite.

One line per landing, mirroring the inbox's one-line-per-report shape.
Required: the task id (plain `#N`, sub-id `#Na`, or combined `#N/#M`), the
**sha** (what landed), who is claiming it, and a one-line `what`. The
`→ folded` line is how the writer marks one consumed, and it is itself an
append — never a deletion — so a folded hand-off is not flagged twice.

## Folded
- **#411** → folded (2026-07-28 14:28): merged `1f01a95` into `## Recently landed`; gate re-run on the merged tree against an explicit pre-merge baseline — 2 recovered, 44 dated unchanged, None 5→3, bait probe still inert
- **#331** → folded (2026-07-28 13:18): merged `cb476a7` into `## Recently landed`; gate re-run on the merged tree with an explicit pre-merge baseline — 19 ids recovered, landed 152→171, span core 4 copies → 1, all three heads pinned including `status_sync`
- **#399** → folded (2026-07-28 12:24): merged `0595b13` into `## Recently landed`; burndown green on the merged tree, and the 3 remaining `just test` failures verified pre-existing on master; residual space-separated multi-id gap filed as #412
- **#398** → folded (2026-07-28 09:31): folded into `## Recently landed` citing `9f2012a`; verification owed
- **#397** → folded (2026-07-28 09:52): folded into `## Recently landed` citing `1b508b0`; recommendation (do-not-extract) accepted, no ruling requested, worktree alternative filed as #405
- **#401** → folded (2026-07-28 09:58): audit half folded into the `#401` entry citing `f2c950e`; fix half stays open, still needs `watch.py`
- **#392a** → folded (2026-07-28 10:00): verified and closed against `#392`'s entry citing `159917b` — independent red taken in a worktree, deployed page checked (38/38 day-precision, zero two-figure). Misfiled Pending-shaped line was the `#406` fixture; relocated under Pending after the check went red-loud.

## Pending

- **#398** · landed `9f2012a` · 2026-07-28 09:26 · by ccc @grok — lint check: post-obligation briefs must mention handoffs.md

- **#397** · landed `1b508b0` · 2026-07-28 09:42 · by ccc @glm52 — design plan: client extraction is mechanically cheap (interpolation count 1) but leans do-not-extract; does not unblock #331/#352 (Python), multiplies the registry damage class, and four named breaks (deploy/serving/autoreload/audit) must ship together if ruled in
- **#401** · landed `f2c950e` · 2026-07-28 09:47 · by ccc @grok — research: executed id-grammar matrix (14 patterns × 17 forms); #401 silent drop reproduces; 7 silent rejects ranked
- **#392a** · landed `159917b` · 2026-07-28 09:43 · by ccc @glm52 — date-only question ages show ONE figure (paintDayAge, data-day flag); today reads "today"; timed commits keep two figures
- **#401** · landed `e53d70c` · 2026-07-28 10:09 · by ccc @grok — hand-off id grammar accepts plain/sub-id/combined; malformed outside section; Folded-then-Pending so EOF append works (#401+#406)

- **#399** · landed `ddc6614` · 2026-07-28 12:08 · by dreamer-399b @grok — _landed_ids counts the historical inline form again (col0 + ref-field exclusion keeps #367 closed); burndown + forgotten_folds both green, 3 opposite-direction reds proven; just-test exit 1 is 3 pre-existing/unrelated guards (qacard=#392, docktarget/noteprop=motion flake under load) proven identical on master

- **#331** · landed `ddc4e3e` · 2026-07-28 13:13 · by dreamer-331 — one IDS_ONLY_SPAN core in watch.py, consumed by lint.LEDGER_ID and status_sync.LEDGER_HEAD; landed 152→171, open 135, all 19 joined-span ids recovered; red-proved both directions; the three guard reds (qacard/docktarget/noteprop) reproduce at parent 97becd9 and were fixed on master by 7007d5b+e15b0c0 (guard-contract fixes, not this parser change)
- **#411** · landed `25a3fe4` · 2026-07-28 14:08 · by grok (wt/411) — (also `54c68e8`) answered_at anchor \A→^+re.M+.search so the 2 second-line markers recover (5→3 None); 44 dated byte-identical; lint WARN with derived count; both red-proofs discriminating

- **#367** · landed `a36c674` · 2026-07-28 15:02 · by grok (wt/367p) — option previews A/B/C at true below-cliff geometry; chrome measured at load (A 167.9 / B 127.2 / C 31.8 px at 780); 16px margin holds at 640; row-count red-proof 3→1 rows

- **#420** · landed `2d7e242` · 2026-07-28 15:43 · by glm52 (wt/420) — read-only census of all 139 open entries (parser-supplied counts, blocking posture, the #419 blocked-on-human question cross-check, 10 stale blockers, symbol-overlap duplicates, ranked next-five); doc only, no review artifact (coordinator working document); 1 pre-existing pytest failure on the live #367 unfolded hand-off, outside this lane's ownership
