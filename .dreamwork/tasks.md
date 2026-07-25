# Task ledger

The durable half of the task list. The backend's list is session-scoped —
this file is not, so ids here are permanent and everything else (commits,
docs, questions, dreams) refers to tasks by them.

**Written by the coordinator only.** Dreamers report queue changes.

A started task also carries its chain: `goal: <one line> ← <parent>`,
where the parent is a session goal or a DREAMWORK.md heading. Pending
tasks don't need one — the chain is named when work begins, which is
when the scope gate asks for it.

Next id: **133**

## Open

- **#122** — Smokey awaiting-fold text: the words warp, a ghost copy
  blows backwards into the aether · P2 · idea · 60m · his brief is
  verbatim in the task; it is the dream dissolve's ghost held low and
  continuous, not a new effect. Taste is the deliverable — wants a
  dreamer that iterates on captures until satisfied
- **#131** — Composer fades away while he types into it again · P2 ·
  bug · 25m · **next-up** (via composer) · the dismiss timer starts at
  submit and input never cancels it — same family as #118. Nothing
  auto-dismisses while it holds focus or unsent text; timeout ×1.5
- **#130** — Status section renders raw JSON · P2 · task · 45m ·
  **next-up** (via composer) · show the three or four facts that answer
  "what is it doing, does it need me"; fold the rest, don't delete it —
  the bulk is load-bearing for agents. Colour by significance, not by
  JSON type. `awaiting_human` must be impossible to miss
- **#129** — Expand/collapse under Answered isn't animated · P2 · bug ·
  30m · **next-up** (via composer) · the contract task: state the fold
  motion in watch-design.md once, then every fold obeys it. #128's
  thread consumes it, so do this one first
- **#128** — A follow-up thread reads as him replying to himself · P2 ·
  bug · 40m · **next-up** · a note written before the answer renders
  below it; the note is tagged `YOU` and the answer is tagged nothing.
  Thread collapses via the standing `expand` idiom, and the expand
  MOTION gets stated in watch-design.md if it isn't already — which
  overlaps #113's matrix, so state it once
- **#121** — `answer | add note` should be ghost buttons · P2 · bug ·
  20m · **next-up** (via composer) · opaque fills hide the animation
- **#123** — `+` button off the heading text's centreline · P2 · bug ·
  20m · **next-up** · likely every view since #110 shared the chrome
- **#126** — Composer commands carry the page they came from · P2 ·
  task · 25m · the route is a hint, never an instruction
- **#127** — One deliberate way to compact a dreamwork agent · P2 ·
  task · 45m · agent-side checklist written (`compaction.md`); the
  per-client dialect table belongs in `~/.llm-general/`, and the
  managed sender is dreamhub's
- **#125** — Vendor a stdlib-only `heartbeat.py` · P2 · task · 60m ·
  the wake mechanism is currently a Rust binary on one machine; port
  the interval AND the wall-clock `@` alignment, which the shell
  fallback cannot do
- **#124** — Break up watch.py; norms for cheap parallel work · P2 ·
  task · 120m · plan: `docs/plans/parallel-architecture.md` · seams as
  batches demand them, starting with #112's components
- **#112** — Design proposals become fragments + shared template · P2 ·
  task · 90m · plan: `docs/plans/artifact-templates.md`
- **#86** — Plugin-contributed command kinds in the composer · P2 · task ·
  45m · the composer now renders from one `COMMANDS` table, so this is
  an append rather than a redesign
- **#98** — Show the open queue on the watch dashboard · P2 · idea · 40m ·
  new page surface, fit-check at selection
- **#132** — Commits on the webui carry a relative timestamp · P3 ·
  idea · 30m · `05m 23s ago`, two units, two digits each until days
  reach 100 · the ticking clock must NOT ride the tick's innerHTML
  re-render, or it fights #118 and #113 once a second forever
- **#114** — Dashboard renders the active goal chain · P3 · task · 25m ·
  stage 3 of #95; status.json already carries `goal`
- **#92** — Hand-rolled Ctrl+K command palette · P3 · task · 40m
- **#99** — Popped-out composer should use the button group too · P3 ·
  task · 25m
- **#100** — Shader lens world-space so blur matches at a window seam ·
  P3 · task · 30m · the last break in "same position, same dream"
- **#73** — Split-view support for watch pages · P3 · experiment · 30m ·
  the shader half landed as #74; the open part is the affordance
- **#50** — ud-dreamtask plugin · P2 · task · 90m · **unblocked**
  2026-07-25 ("rec lgtm") — all four recs taken; build per
  `docs/plans/ud-dreamtask.md`, standalone before sub-loop
- **#80** — Pick a second dogfood target (hark or c2c) · P3 · chore · 30m ·
  **blocked**: human pick
- **#120** — Read SKILL.md for length, with fresh eyes · P3 · chore ·
  40m · not by whoever wrote today's additions
- **#119** — Revisit a `selection.md` reference once selection stops
  moving · P3 · idea · 30m · carried out of a pruned questions entry
- **#96** — Daemon mode stage 1, dreamhub · P2 · task · 120m ·
  **GO** 2026-07-25 10:48, hold lifted · `docs/plans/daemon-mode.md` ·
  next step is a detailed stage-1 plan, then a fresh dreamer — the
  earlier retraction means check back before scope widens past stage 1

## Recently landed

Pruned in grooming; git is the real ledger. **#113** the awaiting-fold
state breathes and every transition between the three states is covered
(86607dd, e8aeec9) — the matrix found three real defects, including a
ghost that kept its `data-qid` and could have swallowed his typing.
**#111** answered questions
collapse and stay findable (a8f6b7f). **#118** typing survives a
live tick — text, caret, focus and compose mode carried across the
re-render (c321c6c). **#117** the verification
gap — `just test` runs the browser guards against a frozen fixture
(bb20eb1, daa9472). **#103** one input per card
routed by a mode group (5b2fde9); **#104 #77** the regroup — answered
questions travel, neighbours close the gap (fc8185d). **#109 #116** author-tagged
notes and one reader for questions.md (2026-07-25, 34f272f) — #116 also
fixed a silent write failure: /answer and /comment could not match a
wrapped-title entry at all. **#115** the component-cost
spike — split verdict, findings in `docs/spikes/` (2026-07-25).
**#107 #108 #110** the
travelling heading, the ghost-pinned width glide, the clamped opener
(2026-07-25, 3f786fc). **#102 #106** prose reflow and the sub-bullet
parser fix (d14c7b3). **#105** one qaCard for all
four question surfaces (2026-07-25, ec6721f). **#91** composer tweaks and
**#101** scrollbar styling (2026-07-25), **#97** durable task ledger
(2026-07-25, this file). #63-#68, #71, #72, #74, #75,
#78, #79, #81-#85, #87-#89, #93, #94 landed 2026-07-24/25 (watch webui
batches, plugin docs, coherence fixes).
