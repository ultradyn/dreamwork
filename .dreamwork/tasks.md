# Task ledger

The durable half of the task list. The backend's list is session-scoped —
this file is not, so ids here are permanent and everything else (commits,
docs, questions, dreams) refers to tasks by them.

**Written by the coordinator only.** Dreamers report queue changes.

A started task also carries its chain: `goal: <one line> ← <parent>`,
where the parent is a session goal or a DREAMWORK.md heading. Pending
tasks don't need one — the chain is named when work begins, which is
when the scope gate asks for it.

Next id: **145**

## Open

- **#138** — Ship a PreCompact hook so the write-down is automatic ·
  P2 · task · 60m · **scope gate applies**: Claude Code-specific
  machinery in a harness-portable skill, and it touches his own config
  — rec is an optional plugin, but confirm before building. A hook
  fires AT compaction, so it guarantees the write-down and cannot buy
  landing time; stdout becomes summariser instructions, so it must be
  silent by construction
- **#144** — A subagent's final message is a channel nobody reads back ·
  P2 · bug · 25m · three utility agents finished and their deliverable
  never arrived; dreamers have lost nothing all day because they append
  to a file. SKILL.md's own guardrail, failing on the coordinator's own
  machinery. Rec: every subagent writes to a file and pings the inbox
- **#143** — Per-project colour tint, persisted and cross-window · P3 ·
  idea · 45m · the value lands with dreamhub: a tint is decoration for
  one project and navigation for several, so the hub shows it too ·
  persist in `.dreamwork/` and let the existing `/mtime` poll sync the
  windows (localStorage loses it on another machine) · **the new file
  lands WITH its file-formats row and lint check** — #135 happened
  because one didn't · hue over the designed ramp, not free RGB, or the
  accent stops meaning anything
- **#142** — Burndown + stats panel on the dashboard · P2 · task · 75m ·
  no new instrumentation needed — the ledger is versioned, so
  `git log -p .dreamwork/tasks.md` IS the time series and permanent ids
  make tasks followable across snapshots. Show arrivals AND completions,
  not just the net (the gap cannot tell "he steers fast" from "work is
  slow"); human- vs loop-initiated is the most telling number here. No
  velocity score. Cost: bucket + cache on HEAD, never replay per tick
- **#141** — Dashboard questions section folds, counts, disables at
  zero · P2 · idea · 30m · **needs #136 first**: a grey disabled zero IS
  the all-clear signal, and an unreadable file currently produces the
  same zero — shipping this first makes the silent failure more
  convincing, not less
- **#140** — Close the commit-to-deploy window · P2 · task · 25m · a
  fix can be committed and undeployed while he is looking at the page,
  which is indistinguishable from broken — it cost a tracing cycle on
  #129. Rec: post-commit hook running `just deploy` when watch.py
  changed; say in DREAMWORK.md that this moves deploy authority
- **#135** — questions.md's format lives only in its parser · **P1** ·
  bug · 40m · **first slice of #137** · from the ez-feedback-pipeline
  instance · the loop writes a
  reasonable file the dashboard cannot read, and zero-parsed renders
  identically to all-clear. Producer half: state the format in SKILL.md,
  seed the skeleton on first use, migration
- **#136** — A questions.md that parses to nothing must say so · **P1** ·
  bug · 45m · reader half of #135 · THREE zero-states, not one: missing
  is a quiet warning (human, 11:28 — the loop writes it almost at once);
  present-but-unparseable is a fault and must look like one; genuinely
  empty is #141's calm grey. The same trap sits in `parse_answered`,
  `open_question_count` and the `append_subbullet` write path — a file
  the reader cannot see is one /answer cannot write
- **#134** — Wire the dreamhub guards into `just test` · P2 · chore ·
  15m · until the line lands, green `just test` does not cover the hub —
  bounded #117 gap, unbounded the moment it is forgotten
- **#133** — Teach watch.py a URL prefix · P3 · task · 45m · do it
  inside #124's server-core seam; unblocks the single-URL hub layout
- **#122** — Smokey awaiting-fold text: the words warp, a ghost copy
  blows backwards into the aether · P2 · idea · 60m · his brief is
  verbatim in the task; it is the dream dissolve's ghost held low and
  continuous, not a new effect. Taste is the deliverable — wants a
  dreamer that iterates on captures until satisfied
- **#130** — Status section renders raw JSON · P2 · task · 45m ·
  **next-up** (via composer) · show the three or four facts that answer
  "what is it doing, does it need me"; fold the rest, don't delete it —
  the bulk is load-bearing for agents. Colour by significance, not by
  JSON type. `awaiting_human` must be impossible to miss
- **#127** — One deliberate way to compact a dreamwork agent · P2 ·
  task · 45m · *mostly landed* · `compaction.md` + the harness dialect
  table in `~/.llm-general/ai-coding/agent-compaction.md`; hooks
  researched and folded in. Remaining: the managed sender, which the
  dreamhub plan places in stage 2 (needs a session handle). See #138
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
- **#96** — Daemon mode stage 1, dreamhub · P2 · task · 150-180m ·
  **GO** 2026-07-25 10:48 · plan delivered:
  `docs/plans/dreamhub-stage1.md`, nine increments each with its gate ·
  ships origin-per-project, not the sketched `/{project}/` prefix (that
  needs watch.py, filed as #133) · stage 1 only — check back before
  scope widens

## Recently landed

Pruned in grooming; git is the real ledger. **#126** a steer carries the
page it was sent from (56a791c) — and, unbriefed, a newline in the
composer can no longer forge a second line in the events log the
coordinator acts on. **#137** `lint.py` checks a
target's files by running the REAL readers, and `just test` now runs it
(b7151ec, 596116a). **#139** the `.qa` catch-alls are gone entirely, not
out-specified, and `oneinput` measures both halves of the field
(166c04b). **#128** the thread no
longer reads as him replying to himself (d6f0ca6) — the parse was
byte-identical whichever order the sub-bullets were written in, so
there was no order to respect; the parser now keeps `when` per note,
cuts the thread at the answer, and only the SETTLED segment collapses,
because folding away a live steer would be worse than the bug. **#131** the composer no
longer fades while he types into it again (896ee74). **#129** needed no
code — e8aeec9 had already animated the fold 24 seconds before he
reported it, and he was right about the deployed page; what it did
surface is now a stated contract, that `expand` is structure and
whether it MOVES is a separate question (f9d08bb), plus #140.
**#121 #123** ghost buttons and the `+` centreline (4fd393b) — #121 was
never a design change: `.sgbtn` asked for `background:none` since #103
and a `.qa button` catch-all outspecified it, so the source read right
while the screen was wrong. **#125** `heartbeat.py`,
a stdlib-only port of the Rust wake tick — byte-identical output, the
Rust test suite ported case for case, and one documented divergence
(`--no-time-prefix` works here; upstream documents it and rejects it). **#113** the awaiting-fold
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
