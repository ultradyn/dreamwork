# Task ledger

The durable half of the task list. The backend's list is session-scoped —
this file is not, so ids here are permanent and everything else (commits,
docs, questions, dreams) refers to tasks by them.

**Written by the coordinator only.** Dreamers report queue changes.

**Scope-gated** work carries its chain on the ledger line:
`goal: <one line> ← <parent>`, where the parent is a session goal or a
DREAMWORK.md heading. That is agent-initiated work adding new surface or
breaking the size norms — the cases SKILL.md's scope gate stops for.

It is deliberately NOT every started task. This header used to say it
was, and after a day of heavy use exactly one line in the ledger carried
a chain — because almost everything came from the human, and human
steers are never gated. A convention that fires on everything gets
written on nothing; narrowed here to match the gate that actually asks
for it.

Next id: **160**

## Open

- **#138** — Ship a PreCompact hook so the write-down is automatic ·
  P2 · task · 60m · **scope gate applies**: Claude Code-specific
  machinery in a harness-portable skill, and it touches his own config
  — rec is an optional plugin, but confirm before building. A hook
  fires AT compaction, so it guarantees the write-down and cannot buy
  landing time; stdout becomes summariser instructions, so it must be
  silent by construction
- **#145** — Route findings by trigger; land the review's moves · P3 ·
  chore · 60m · findings + coordinator disposition:
  `docs/reviews-skillmd-2026-07-25.md` · 420 is not the problem, the RATE
  is · M2/M3 KEPT with the reason recorded · **blocked precondition**:
  ud-dreamtask points at named SKILL.md sections, so a rename orphans a
  live pointer in another repo — grep the sibling first · **open**: the
  routing rule has no bucket for CRAFT guidance; a second craft rule is
  the signal to split it out of `file-formats.md` · also argues against
  #119's `selection.md`
- **#144** — *landed as a convention* · the reporting rule is in
  SKILL.md (write then wake), and `status.json`'s `agents` entries now
  carry optional `kind` and `awaiting_result` so a dispatched-but-silent
  agent is legible without the coordinator remembering. Root cause,
  better than the symptom I filed: subagent PLAIN TEXT is not a channel
  at all — only files and harness messages arrive, so three "idle, no
  findings" were three complete reports with nowhere to go
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
- **#140** — Close the commit-to-deploy window · P2 · task · 25m · a
  fix can be committed and undeployed while he is looking at the page,
  which is indistinguishable from broken — it cost a tracing cycle on
  #129. Rec: post-commit hook running `just deploy` when watch.py
  changed; say in DREAMWORK.md that this moves deploy authority
- **#147** — Hub shows which targets run behind their own HEAD · P3 ·
  idea · 30m · #140 CLOSES the deploy window, this makes it LEGIBLE —
  decide which is the answer before building both
- **#148** — Two sibling guard dirs, one contract, no shared runner ·
  P3 · chore · 30m · fine while they have different owners, wrong the
  moment they do not; extract when a batch would have used it (#124)
- **#157** — A backticked filename links whether or not it resolves ·
  P2 · bug · 30m · verified: `/file` returns 200 and renders a 404
  inside it, and `/filedata` returns an HTML error page where JSON is
  expected · `file-formats.md` works (target root); `questions.md` and
  `status.json` are real but live at `.dreamwork/`; `newerrand.py` is in
  the SIBLING repo and should stay plain text — do not invent cross-repo
  linking · resolve before linkifying: a link that 404s promises
  something, which is "nothing fails quietly" aimed at the page's own
  affordances
- **#158** — `/file` should reflow markdown · P2 · bug · 25m ·
  **CONTRADICTS a recorded decision** ("markdown prose reflows, raw text
  does not — `/file` stays verbatim", #102). The rule drew its line at
  WHO COMPOSED IT; the useful line is CONTENT. `initialization.md` is
  the same prose that reflows in the dashboard's own peek, and reflows
  or not purely by the route it was reached through. Reflow `.md`, keep
  `.py`/`.json`/logs verbatim, and update watch-design.md in the same
  commit because this REPLACES a rule
- **#159** — "sent to the dream" appears instead of arriving · P3 · bug
  · 15m · use `.dreamin`, which only started working today (#154) ·
  check the departure too · verify by per-frame trace, since a two-frame
  fade looks instant and passes a "did it appear" check
- **#156** — Lint questions.md at WRITE time (PostToolUse hook) · P2 ·
  idea · 40m · his idea, and it is the strongest version of the fix:
  every current defence fires LATER than the mistake (lint at init and
  in `just test`, the dashboard at read time). A hook fires in the same
  turn, while the agent that mangled it still holds the context ·
  `lint.py` already does the checking, so the hook is thin · **his
  error-message spec is the deliverable**: where, what, expected, and a
  pointer to the format · **bundle with #138** — both are Claude Code
  hooks, ship the plugin or ship neither
- **#153** — Title that says whether you're needed, and a real favicon ·
  P2 · idea · 50m · the tab title is the only part of the dashboard
  visible in a background tab, so it carries the count front-loaded
  (tabs truncate from the right) · favicon must be inline (single-file
  deploy) · **rec against always-animating**: motion is opt-in here, and
  browsers throttle background timers — animate when the loop is
  dreaming, rest when idle, mark `awaiting_human`. Then the motion IS
  the status · taste is the deliverable, like #122 · pairs with #143
  (a tinted favicon is how two dashboards differ in a tab strip)
- **#152** — A dangling-parent check, deferred WITH A TRIGGER · P3 ·
  chore · 15m · (b) prose-wrap: measured, do not build — eleven long
  lines, three of them unwrappable frontmatter · (a) the ledger carries
  ONE chain line and that is correct, so a checker today checks nothing.
  **Build it when #114 lands** (chains become something he sees) **or
  when there are >5 chain lines**. The check is right; the timing is
  wrong
- **#150** — Audit the coordinator's own machinery · P2 · chore ·
  *all four slices landed* · `relay.py` (stdin body, clock stamp);
  write-then-wake in SKILL.md; `kind`/`awaiting_result` in status.json;
  and an honest "what stays unguarded" section in `file-formats.md`,
  because a list of what IS checked implies coverage it does not have.
  One finding left open by design: **a shutdown approval carries no
  payload**, so anything an agent knows at termination must be written
  BEFORE it agrees to stop — procedural, not checkable
- **#133** — Teach watch.py a URL prefix · P3 · task · 45m · do it
  inside #124's server-core seam; unblocks the single-URL hub layout
- **#122** — Smokey awaiting-fold text: the words warp, a ghost copy
  blows backwards into the aether · P2 · idea · 60m · his brief is
  verbatim in the task; it is the dream dissolve's ghost held low and
  continuous, not a new effect. Taste is the deliverable — wants a
  dreamer that iterates on captures until satisfied
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
- **#114** — Dashboard renders the active goal chain · P3 · task · 25m ·
  stage 3 of #95; status.json already carries `goal`
- **#92** — Hand-rolled Ctrl+K command palette · P3 · task · 40m
- **#99** — Popped-out composer should use the button group too · P3 ·
  task · 25m
- **#100** — Shader lens world-space so blur matches at a window seam ·
  P3 · task · 30m · the last break in "same position, same dream"
- **#73** — Split-view support for watch pages · P3 · experiment · 30m ·
  the shader half landed as #74; the open part is the affordance
- **#50** — ud-dreamtask · P2 · task · stages 1-5 DONE; only **stage 6
  (harvest) remains and it is GATED** on Max · shipped at
  `~/.llm-general/skills/ud-dreamtask/` (own repo, installed, indexed),
  with `newerrand.py` so an opening never hand-writes the two silent
  formats · dreamstate is target-shaped, so lint, hub and watch read an
  errand with zero new code
- **#80** — Pick a second dogfood target (hark or c2c) · P3 · chore · 30m ·
  **blocked**: human pick

## Recently landed

Pruned in grooming; git is the real ledger. **#155** the styleguide audit
now measures adjacency HONESTLY (487d1a6) — a 3-commit window, so writing
the doc before the code is no longer punished, and a comment saying what
it does not prove: touching both files passes whether or not the doc says
anything, so 29 green commits proved only that the files moved together.
Deliberately NOT gated — making adjacency mandatory would be worse than
the status quo. **#141 #149** (2bf61da,
6099998) — the questions section folds, counts and greys, keyed on
`questions_health` rather than the count so a calm grey can never sit
under #136's warning; and it would have SNAPPED SHUT under him every 2s,
the innerHTML-swap state loss for the third time after #118 and #111.
Restore only ever re-opens, so a stale snapshot cannot take anything
from him. **#132 #151 #154** (2c42da1)
— relative commit ages riding the page's existing per-second sweep, five
rows arriving as one gesture on a new SHA rather than on a tick, and the
enter-snap class fixed: `.dreamin` had NEVER worked for question cards,
so every arrival since #104 was a pop-in and the motion matrix's
"arrived: snap, then ease in" row had been false the whole time. **#119** DECIDED, not built:
selection stays in SKILL.md. The idle branch is by definition where no
other trigger fires, so a pointer would be followed only by a loop that
already knew what it was looking for; and step 2's dot line only works in
front of the reader — "explicit thinking time" behind a link gets read
past rather than performed. Only the 13-line maintenance rotation is
movable, which does not justify a fourth reference file. (Argued by the
#120 reviewer, taken 2026-07-25.) **#136** an unreadable
questions.md now says so, in a second `--warn` colour because a fault in
the live accent reads as activity (606ceaf) — and the sharper half was
unbriefed: `postAnswer` discarded its response, so a REFUSED write told
him it had succeeded, cleared his text, and the tick restored the
question two seconds later. **#134** the hub guards are in `just test`;
the recipe comment now names all THREE guard shapes, since `health`
already broke the one-contract claim before dreamhub arrived. **#135** the producer half of
the format bug (d9ce212) — `file-formats.md` states the shapes, init seeds
the skeleton, migration -13. **#146** a pasted bullet can
no longer forge a question (26037e7) — `human_block()` is now the only
way human text enters questions.md. Indenting alone was NOT enough: the
reader tests `- **` on the RAW line but 'starts a bullet' on the STRIPPED
one, and a bullet ends the note capture, so an indented `- foo` would have
spilled his words into the entry BODY as prose the loop appears to have
written — an attribution failure through a door #109 never considered.
Verified independently: entry, indented bullet and fake section all
blocked. **#96 stage 1** dreamhub —
a read-only aggregate over several targets, nine increments
(ab32541..dc69c8c), 102 pytest + 32 structural + 8 contract checks. Ships
origin-per-project, not the sketched `/{project}/` prefix, because
`routeOf()` compares literals no shim can reach and a prefixed deep link
would render the wrong view SILENTLY (#133). Stage 2+ still needs a go. **#130** 3.1KB of status JSON
became a 244px panel (c065a51) — folds by COMPLEMENT so the next field the
loop learns to write can never be hidden by an allowlist, and the accent is
spent only on `awaiting_human`, proven scarce by a guard shown red. **#120** the fresh-eyes read
(6827daa) — it found a LIVE bug rather than bloat: dashboard commands
exist only in a gitignored best-effort log that SKILL.md never mentioned,
so a `do now:` was lost silently whenever the tail monitor was not armed.
Plus four false or self-contradicting statements. Its structural half is
#145. **#126** a steer carries the
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
