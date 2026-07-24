# Task ledger

The durable half of the task list. The backend's list is session-scoped —
this file is not, so ids here are permanent and everything else (commits,
docs, questions, dreams) refers to tasks by them.

Next id: **98**

## Open

- **#91** — Composer tweaks, the five human items · P1 · task · 90m ·
  *in progress (dreamer-composer)* · spec + code pointers:
  `docs/handoff-2026-07-25-beauty.md`
- **#77** — Cross-group morph when a question changes section · P2 · task ·
  45m
- **#86** — Plugin-contributed command kinds in the composer · P2 · task ·
  45m
- **#95** — Goal hierarchies · P2 · task · 60m · **blocked**: human review
  of `docs/plans/goal-hierarchies.md` (questions.md)
- **#92** — Hand-rolled Ctrl+K command palette · P3 · task · 40m
- **#73** — Split-view support for watch pages · P3 · experiment · 30m ·
  the shader half landed as #74; the open part is the affordance
- **#50** — ud-dreamtask plugin · P3 · task · 90m · **blocked**: human
  review of `docs/plans/ud-dreamtask.md` (questions.md)
- **#80** — Pick a second dogfood target (hark or c2c) · P3 · chore · 30m ·
  **blocked**: human pick
- **#96** — Daemon mode stage 1, dreamhub · P3 · task · 120m ·
  **ON HOLD**: a go was given then explicitly retracted; do not plan or
  build until Max re-opens it · `docs/plans/daemon-mode.md`

## Recently landed

Pruned in grooming; git is the real ledger. **#97** durable task ledger
(2026-07-25, this file). #63-#68, #71, #72, #74, #75,
#78, #79, #81-#85, #87-#89, #93, #94 landed 2026-07-24/25 (watch webui
batches, plugin docs, coherence fixes).
