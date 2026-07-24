# Task ledger

The durable half of the task list. The backend's list is session-scoped —
this file is not, so ids here are permanent and everything else (commits,
docs, questions, dreams) refers to tasks by them.

**Written by the coordinator only.** Dreamers report queue changes.

A started task also carries its chain: `goal: <one line> ← <parent>`,
where the parent is a session goal or a DREAMWORK.md heading. Pending
tasks don't need one — the chain is named when work begins, which is
when the scope gate asks for it.

Next id: **106**

## Open

- **#102** — Reflow hard-wrapped source text in the webui · P1 · bug ·
  40m · human-reported with a screenshot; inline markdown leaks too
- **#106** — Follow-up preview truncates mid-phrase with no affordance ·
  P1 · bug · 25m · human-reported; reads as damaged text
- **#109** — Human notes must be obviously human, in file and on page ·
  P1 · bug · 35m · file half landed (04968d1); page half with the dreamer
- **#111** — Answered questions distinct and collapsed by default · P2 ·
  task · 30m · human-asked; awaiting-fold probably stays open
- **#113** — Awaiting-fold looks alive; every state transition covered ·
  P2 · task · 45m · do with #111; states encode who it waits on
- **#112** — Design proposals become fragments + shared template · P2 ·
  task · 90m · plan: `docs/plans/artifact-templates.md`
- **#115** — Spike: cost of unifying qaCard/pageHeader onto the
  vocabulary · P2 · experiment · 60m · *in progress (spike-components,
  worktree `spike/components`)* · measures a claim I made in #112's plan
  · goal: know the real cost before committing to one presentation
  system ← "the dashboard is how you check on it and steer it"
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
- **#114** — Dashboard renders the active goal chain · P3 · task · 25m ·
  stage 3 of #95; status.json already carries `goal`
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

Pruned in grooming; git is the real ledger. **#107 #108 #110** the
travelling heading, the ghost-pinned width glide, the clamped opener
(2026-07-25, 3f786fc). **#102 #106** prose reflow and the sub-bullet
parser fix (d14c7b3). **#105** one qaCard for all
four question surfaces (2026-07-25, ec6721f). **#91** composer tweaks and
**#101** scrollbar styling (2026-07-25), **#97** durable task ledger
(2026-07-25, this file). #63-#68, #71, #72, #74, #75,
#78, #79, #81-#85, #87-#89, #93, #94 landed 2026-07-24/25 (watch webui
batches, plugin docs, coherence fixes).
