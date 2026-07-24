# Task ledger

The durable half of the task list. The backend's list is session-scoped —
this file is not, so ids here are permanent and everything else (commits,
docs, questions, dreams) refers to tasks by them.

**Written by the coordinator only.** Dreamers report queue changes.

Next id: **106**

## Open

- **#102** — Reflow hard-wrapped source text in the webui · P1 · bug ·
  40m · human-reported with a screenshot; inline markdown leaks too
- **#106** — Follow-up preview truncates mid-phrase with no affordance ·
  P1 · bug · 25m · human-reported; reads as damaged text
- **#107** — Page width jumps navigating to/from /review · P1 · bug ·
  30m · human-reported; `body.review` resizes outside the dissolve
- **#103** — One text input for answer and note, mode group + flush send ·
  P2 · task · 50m
- **#104** — Questions fade out, neighbours slide into place · P2 · task ·
  45m · do with #77; "things slide, never jump" is the principle
- **#77** — Cross-group morph when a question changes section · P2 · task ·
  45m · same regroup moment as #104
- **#86** — Plugin-contributed command kinds in the composer · P2 · task ·
  45m · the composer now renders from one `COMMANDS` table, so this is
  an append rather than a redesign
- **#98** — Show the open queue on the watch dashboard · P2 · idea · 40m ·
  new page surface, fit-check at selection
- **#95** — Goal hierarchies · P2 · task · 60m · **blocked**: human review
  of `review/goal-hierarchies.html` (questions.md)
- **#92** — Hand-rolled Ctrl+K command palette · P3 · task · 40m
- **#99** — Popped-out composer should use the button group too · P3 ·
  task · 25m
- **#100** — Shader lens world-space so blur matches at a window seam ·
  P3 · task · 30m · the last break in "same position, same dream"
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

Pruned in grooming; git is the real ledger. **#105** one qaCard for all
four question surfaces (2026-07-25, ec6721f). **#91** composer tweaks and
**#101** scrollbar styling (2026-07-25), **#97** durable task ledger
(2026-07-25, this file). #63-#68, #71, #72, #74, #75,
#78, #79, #81-#85, #87-#89, #93, #94 landed 2026-07-24/25 (watch webui
batches, plugin docs, coherence fixes).
