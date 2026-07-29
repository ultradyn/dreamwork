# Questions for the human

## Open


- **P2 · 2026-07-30 07:05 — #505: the wholesale-rerender smell — the IGC is done, four calls are yours.**
  **Sub-decisions:** `Q1`, `Q2`, `Q3`, `Q4`
  Design: `.dreamwork/docs/plans/render-architecture.md` (design only; no code authorised). Your 03:48
  report: every data.json poll resets UI state inside question cards (text selection deselects; the chrome
  survives). The measured inventory (16 reset surfaces, each cited to code) finds the chrome survives
  because it is ALREADY a keyed diff (`renderChrome`); the reset is the absence of that idiom inside
  `#view`, rebuilt by one wholesale `innerHTML` swap per tick with ~11 hand-maintained snapshot/restore
  pairs re-applying state afterwards. An IGC (I1–I5 × G1–G5) refutes your three directions as standalone
  fixes — ids alone don't survive the swap (the node is destroyed), content-check only skips unchanged
  ticks (resets on the first real change), React/preact impose a build step + a second render authority
  against your own single-file architecture — and the survivor is **keyed reconciliation of `#view`
  (morphdom-idiom) + a content-hash skip**: generalise `renderChrome`'s keyed diff to the data-driven
  lists, keeping survivor nodes by their existing keys (`data-qid`/`data-aid`/`data-sha`/`data-keep`) so
  selection/caret/scroll/focus survive as a class — a state nobody has yet thought to snapshot survives
  because the node that held it was kept. Subsumes #141/#503/#494: their snapshot/restore pairs become
  dead code; `data-keep` stays as a reconciliation key.

  - **`Q1` — reconciler: vendored morphdom, or hand-rolled?** **`rec: vendored ~2KB morphdom`** —
    battle-tested diff algorithm, far inside the no-build budget (the page already vendors an SVG-mist
    pipeline); the keyed-FLIP layer on top stays hand-rolled (it is this page's own gesture, not a
    generic diff). Alternative if you prefer zero new vendored code: hand-rolled, modelled on
    `renderChrome`.
  - **`Q2` — hold the no-build single-file constraint and rule out full vdom?** **`rec: yes.`** The
    keyed-diff delivers the DOM-diffing you actually asked for without React's build/bundle/second-
    authority cost. Adopt a vdom only if you want the component model for its own sake, which is a
    different (larger) decision than this bug.
  - **`Q3` — scope: `#view` only, or also fold in the review-dock swap?** **`rec: phase 1 = `#view`
    lists and disclosures; phase 2 (optional) = the review dock`** (its swap is already narrower).
  - **`Q4` — guard the corpse rule under reconciliation?** **`rec: yes — a guard asserting no ghost
    element matches a reconciled identity key`** (the `dreamAway` double-count bug stays impossible;
    ghosts live in `.wrap`, outside the reconciled root, and a regression there re-opens #277's class).

  **If you say nothing:** nothing is built — the design authorises no code, and the recs stand as
  defaults when the implementation is planned.
  Accepted answers: `rec` (takes all four) · per-question (`Q1: …`) · free text.

- **P2 · 2026-07-30 06:05 — #510: an 'Orchestrator' option in Posture — three calls, after the IGC you asked for.**
  **Sub-decisions:** `Q1`, `Q2`, `Q3`
  Design: `.dreamwork/docs/plans/orchestrator-posture.md` (design only; no code authorised). Your 04:54
  do-next. The IGC (I1–I5 × G1–G5) settles *how* it integrates — **a fifth posture axis**, not a fold onto
  `delegation`, not the `hierarchical` run-mode value, not a control-only toggle, not a sibling file. What
  it does not settle is *what* "Orchestrator" is, and that is the first call. One finding worth your eye:
  the fleet concept you're gesturing at already exists, teed up and disabled, as the `hierarchical`
  run-mode value (`watch.py:343`) — so this is less "invent where it goes" than "it wants to be a posture
  axis, not the run-mode value it's parked as" (run-mode bundles decisions, `#443`; an axis is the
  unbundled form).

  - **`Q1` — the referent: orchestration MODE, or orchestrator IDENTITY?** Mode = the coordinator
    dispatches + reviews and implements nothing inline (the coordinator-only-loop mode
    `dogfood-orchestration.md` records; your "you main opus 5 claude orchestrator" usage). Identity =
    which model/session runs the loop. **`rec: mode.`** Identity is a dispatch/provenance fact you set by
    which session you run / which alias you dispatch — recorded at dispatch, not a posture dial; a
    gitignored, tick-re-read posture file is the wrong home for "who was dispatched." If you mean
    identity, say so — the integration is different and this IGC does not apply.
  - **`Q2` — the closed set and name (if mode).** **`rec: a binary axis `hands-on` | `orchestrator`,
    absent → `hands-on` (today).** `orchestrator` = the coordinator implements nothing inline — every
    increment is dispatched, the coordinator's role is adjudication/review/ledger. `hands-on` = today
    (implements inline, may also delegate). Binary because solo-vs-fleet is already `delegation`'s job
    (`delegation: 0` = solo); a third "solo" stop would duplicate it. The other stop's label is open
    (`hands-on` rec; `implementer`/`inline` alternatives); a three-stop `solo | mixed | orchestrator` is
    available if you want "mixed" nameable.
  - **`Q3` — the `hierarchical` run-mode (#264/#288).** **`rec: land the axis, do NOT enable
    `hierarchical` as a run-mode value.** The axis is the dial `hierarchical` always wanted to be;
    enabling the value re-bundles decisions (`#443`) and still needs #264/#288, while the axis needs
    neither. Alternative: land both, the axis being what a later `hierarchical` convenience bundle sets.

  **If you say nothing:** nothing is built — the design authorises no code, and the recs stand as the
  defaults when the implementation split (subagent WebUI, coordinator docs, per your instruction) is
  planned.
  Accepted answers: `rec` (takes all three) · per-question (`Q1: …`) · free text.

- **P2 · 2026-07-30 04:45 — #504: the composer 'chat' design is done — an IGC made it the first slice of #229, and four forks are yours.**
  **Sub-decisions:** `Q1`, `Q2`, `Q3`, `Q4`
  Design: `.dreamwork/docs/plans/composer-chat.md` (design only; no code authorised; the implementation
  anchor stays `#373`).

  The headline is the reconciliation, not a fork: a real IGC (A/B/C × G1–G5) decided your `chat` command
  **is** the main-dreamer first slice of `#229`/`#270`'s approved spine — not a separate channel. A separate
  store was refuted (a second durable inbox competing with the `#263` receipt), as was riding
  `/command`+`questions.md` (no queryable unread home, no enforceable reply channel). So the message path,
  thread model and reply channel are `#229`'s, and your *"get unread at the start of a loop iteration"* is,
  by name, the `#342` cursor read (`dev/journal_consume.py pending`). One pushback, stated plainly in the
  doc: *"tracked in the db, but only just in case"* understates the receipt — under `#342` it is the
  delivery path, not a backup.

  Four genuine forks, each with a rec; **`rec` takes all four.**

  - **`Q1` — the POST route home.** `rec`: a new **`/command` chat kind** — reuses the existing route, the
    receipt seam and the composer row; thinnest path, and matches your "command" framing. The alternative is
    a new `/chat` write route, reserved for `#373`'s full surface (a `watch.py` change plus an E2Shadow
    extension).
  - **`Q2` — the UI word.** Implementation never says `thread` (`#229`'s vocabulary rule). `rec`: the UI
    says **"topic chat"** too. The alternative keeps your word "thread" in the human-facing label only;
    behaviour is identical either way.
  - **`Q3` — the delivery default under `#342`.** `rec`: **batched** — rides the tick cursor read, exactly
    your "get unread at iteration start", joining the ambiguous class `#342` already ruled batched. The
    alternative is `instant` (pre-empts like `do-now`).
  - **`Q4` — does this slice ship a visible chat surface?** `rec`: a **minimal chat list reusing the
    dashboard**, deferring `#373`'s global `/chat` index and dedicated route. The alternative lands only the
    loop-side path now, all UI later.

  **If you say nothing:** nothing is built — the design authorises no code, and the recs stand as the
  design's defaults when `#373` is planned.
  Accepted answers: `rec` (takes all four) · per-question (`Q1: …`) · free text.

- **P2 · 2026-07-29 04:10 — #465: may I put the lane-containment guard in front of this repo's commits?**
  **What `#465` is** (you asked, and the old wording never said): tonight a subagent edited the main checkout
  instead of its own worktree. Nothing noticed until a verified merge, held half an hour, aborted on the stray
  file. `#465` is the guard that refuses such a commit — it reads which paths each lane declared and blocks
  anyone else touching them.

  **You also asked why it needs the global hook path. It does not — I framed that badly.** Your
  `core.hooksPath` is global (`~/.config/git/hooks`, holding c2c's `pre-commit`/`pre-push` plus a
  `commit-msg`), and because that setting exists git ignores `.git/hooks` entirely, which is the only reason
  the global dir came up at all. Setting `core.hooksPath` **repo-locally** overrides it for this repo alone.

  **`Q1` — which install?** New **`rec`: repo-local**, a tracked `.githooks/` here whose `pre-commit` runs
  c2c's hook first and then the guard. Blast radius is this repo; c2c keeps working here. The honest cost:
  a repo-local path also shadows `commit-msg` and `pre-push`, so the dir must forward all three or they
  silently stop applying — that is the work, and it is why the global install looked simpler.
  Global-and-chained is still available if you would rather have it everywhere.

  **Since you last read this, `#468` R2 landed** and needs no hook at all: `lane_guard.py pre-merge <branch>`
  checks the same preconditions before a merge. So some protection now exists either way.

  **If you say nothing:** the guard stays committed and inert, and the stray-edit protection does not exist —
  the status quo that cost the held merge. `DREAMWORK_LANE_GUARD_BYPASS=1` remains the escape.
  - **Note (human, via watch, 2026-07-29 05:51):** why can't we enable #465
    without this? And also, what is 465?


- **P2 · 2026-07-25 — how should an answer reach a loop on another machine?** **DEFERRED by him
  2026-07-29 16:14 — revisit once dreamhub is stable and the primary way we access dreamworkers.** Until
  then, nothing blocks and nothing is delivered by hand.
  - **Note (human, via watch, 2026-07-29 16:14):** this should be deferred
    as an open question that we'll revisit once dreamhub is stable and the
    primary way we access dreamworkers

## Answered


- **P2 · 2026-07-30 03:40 — #357 Q6: on the read verbs (`counts`, `sweep`), full warning line every time, or a terse `⚠ N warnings` hint?**
  → answered (2026-07-30 03:52): **rec — full line every verb (I1).** The read verbs carry the full warning breakdown every call; the terse hint is dropped. With Q5 (every verb) and Q6 both ruled and the throttle refuted by the IGC he ordered, `#357`'s design is fully settled and unblocked for implementation: stateless footer, one function in `dev/ledger.py` called by every verb at exit, his five counts + incomplete-data, WARN never ERROR, quiet rules, and the journal unconsumed-receipt count carrying on every verb. Recorded on `#357` and in the design doc.
  **Ask: `rec` (full line), `terse`, or free text.** One decision; a bare `rec` is a complete reply.

  Your throttle sketch was evaluated with the IGC you asked for, and it produced a headline worth
  stating plainly: **the sketch is refuted, and the refutation is not mine to over-rule.** "Surface
  warnings early so the dreamworker can plan them in" and "suppress 70–80% of prints on the verbs I
  run to look" are rivals — a throttle is a delay device pointed at your own stated goal. It also
  needs memory (last-seen warning, skip-count) a stateless verb process cannot hold without a new
  state file, and that state can suppress a warning you never saw, forever. Full reasoning:
  `.dreamwork/docs/plans/cli-warning-layer.md` §IGC.

  What survives is a genuine fork between the two stateless shapes, and it is yours because it is
  about your reading habits:

  - **`rec`: full line every verb (I1).** A `counts` alone shows WHAT the warnings are, so planning
    them in needs no second action — your stated goal. Cost: the identical line repeats on
    consecutive read-verb calls while counts are unchanged, and on `counts` it repeats a number the
    output just showed. Bounded: on a clean tree it prints nothing at all.
  - **terse hint on reads (I3).** Read verbs print `⚠ N warnings — lint.py` instead; no identical
    repeat. Cost: you see THAT warnings exist, not WHAT they are — planning needs a `lint.py` run
    or the next state-change verb. If fatigue bites later, this is a stateless drop-in, ruleable
    with no migration — which is why `rec` is the cheaper-to-reverse start.

  **If you say nothing:** the design's rec stands (full line, I1) and the footer ships that way
  when #357 is implemented; nothing is built by this entry.
  - **Answer (via watch, 2026-07-30 03:52):** rec


- **P2 · 2026-07-30 01:30 — #357: the CLI warning footer — on every `dev/ledger.py` verb, or only on verbs that change state?**
  → answered (2026-07-30 03:11): **rec — the footer on every verb**, with one amendment worth an IGC rather than a shrug: warnings should surface *early* in the loop so the dreamworker can plan them in, and he sketched a throttle for the read verbs — after every state-change verb always; for other verbs suppress 70–80% of prints, but only while the warning is unchanged AND time since last warning < heartbeat × 0.7 AND skips since last print < 4 (every 5th call prints regardless). His instruction: evaluate the options with `/use-igcs` and surface any issues as a new question. Recorded on `#357`; the design increment carries the ruling.
  The warning-layer design (`.dreamwork/docs/plans/cli-warning-layer.md`) is settled except this one fork,
  which is yours because it is about your reading habits. Your word was "tacked on," which reads as every
  verb. The footer's value is highest on the state-change verbs (`fold`/`file`/`note`) — they are what can
  CREATE the unfolded-answer situation it exists to catch. The read verbs (`counts`, `sweep`) are the ones
  you run to LOOK; tacking the footer there means every `counts` prints a warnings line under the counts.
  Bounded either way by the quiet rules (zero counts are absent; a clean tree prints nothing extra).
  - **`rec: every verb`** — the literal reading of "tacked on," the shape that can never miss a state-change
    verb, and on a clean tree `counts` prints just its counts. Cost over the alternative is one
    suppressed-absent line on read verbs — the cheapest possible cost. (The design folds the journal
    unconsumed-receipt count under this call: every-verb carries it, state-change-only omits it.)
  - **the alternative: state-change verbs only** (`fold`/`file`/`note`) — quieter on read verbs, at the cost
    of the footer not appearing on `counts`, the verb whose whole job is "tell me what is waiting."
  - **Answer (via watch, 2026-07-30 03:11):** rec; additional to your
    reasoning: we want to surface these *early* in the loop so that the
    dreamworker can plan them in. One more complex proposal is that we
    show them after every state-change verb, and for other verbs we hide
    them like 70-80% of the time, but only if: the warning is unchanged
    AND time since last warning < (heartbeat period * 0.7) AND warnings
    skipped since last print < 4 (which should print every 5th call
    regardless). Something like that. Use /use-igcs to evaluate options
    and ensure we have a good solution. Surface any issues in a new
    question.

- **P1 · 2026-07-29 22:31 — #287: the matt-pocock-skills bridge spec is written — five calls are yours.**
  → answered (2026-07-30 00:20): **OQ1 local ledger** — and a filed, deliberately-later task
    for mirroring task state to GitHub (issues for tasks, PR/issue↔task links, webhook comments
    into the hub as task events). **OQ2 rec** — one question per entry, awaited; his stated
    reason is the design’s own: outdated questions are never asked and every question is as
    informed as it can be. **OQ3 rec** — `CONTEXT.md` at repo-root, referenced not copied.
    **OQ4 an autonomy level on posture** — autonomous dispatch of suite tools is gated on it;
    task filed. **OQ5 probably the same autonomy level** — self-filing becomes a steer the
    autonomy level gates rather than a flat no. Recorded on `#287` and in the spec. With the
    cutover landed and all five calls answered, the bridge specification is settled; his
    earlier *"wait till after sqlite"* is spent, so planning the implementation is unblocked.
  The spec is at `.dreamwork/docs/plans/matt-pocock-skills-bridge.md` (landed today, written-spec
  authority only; the suite runs unchanged and the bridge translates at three seams). Each question
  has a rec in the doc; each is a genuine fork, so they are here rather than picked:

  **`OQ1` — local ledger, or a real GitHub tracker mirrored?** **`rec`: local ledger** — makes the
  sqlite cutover invisible and needs no remote authority. The fork: the suite's designed-for home is
  a real tracker; if you want that, `ud-dreamwork-github` already covers the forge side.

  **`OQ2` — grill cadence: one question per entry, awaited, or batched into one multi-part entry?**
  **`rec`: one per entry, awaited** — preserves the suite's cadence and #254's one-root rule.

  **`OQ3` — where does `CONTEXT.md` live?** **`rec`: repo-root, referenced not copied.** The fork is
  `.dreamwork/docs/domain/`, which touches repo-root layout.

  **`OQ4` — may the loop dispatch suite tools (`research`/`code-review`/`prototype`) autonomously?**
  **`rec`: human-invoked only** by default; autonomous dispatch is scope the authority lines grant
  explicitly, not a default.

  **`OQ5` — may loop-generated `to-spec`/`to-tickets` output file itself as tasks?**
  **`rec`: no — filing is a human steer** by default.

  **If you say nothing:** nothing is built — the spec authorises specification only.
  - **Answer (via watch, 2026-07-30 00:20):** 1. local. in future, we
    should add a feature for mirroring our task state to github (so
    there are github issues associated with tasks, PRs and issues can be
    linked to tasks or vice versa, comments on github sent via webhook
    to hub which can add as an event in the tasks db for that project,
    etc). Add a task for this but note in it that it's planned for much
    later. 2. rec (the reason for 1 q at a time is, I think, so that
    irrelevant/outdated questions aren't asked and every question is as
    informed as it can be). 3. rec 4. in this case I think some options
    would be good, like adding an autonomy level to posture for
    maintenance (which is probably a good thing for us to do anyway; pls
    add a task) 5. probably an autonomy level thing.

- **P2 · 2026-07-29 22:25 — #342: delivery modes — the three calls the design leaves to you.**
  → answered (2026-07-30 00:23): **rec on all three, with one amendment.** Q1 the ambiguous
    class is **batched** by default — a `do now` still pre-empts. Q2 a fourth posture axis
    `delivery` (`instant`|`batched`) in `.dreamwork/posture`, absent defaults to `instant`,
    reusing POST /posture + the 10s arm, batched mode keeping the most-urgent kinds
    pre-empting. Q3 the loop **gates** a kind’s urgency — amended: **plugins may suggest**
    urgency, the loop still decides. Recorded on `#342` and in the design; the ruling settles
    the design, so `#342` is unblocked for implementation.
  The design is at `.dreamwork/docs/plans/delivery-modes.md` (landed today; batched vs instant
  delivery for dashboard commands, riding #263's journal cursor). It deliberately does not pick
  these for you:

  **`Q1` — the ambiguous class** (answers to questions, notes/comments on reviews, `/ask`
  replies): instant or batched by default? You named this *"the genuinely ambiguous class the
  toggle is for."* **`rec`: batched** — they are read on the tick either way, and the class is
  exactly where "overwhelmed" comes from; a `do now` still pre-empts.

  **`Q2` — the toggle's shape and reach.** **`rec`: a fourth posture axis `delivery`
  (`instant`|`batched`) in `.dreamwork/posture`**, absent defaults to `instant` (today), reusing
  the dashboard's existing POST /posture + 10s arm — and batched mode keeps the most-urgent
  kinds pre-empting rather than demoting everything. The alternative is a sibling
  `.dreamwork/delivery` file.

  **`Q3` — may a plugin self-declare a kind's urgency, or does the loop gate it?**
  **`rec`: the loop gates it** — a plugin that can mark itself instant can wake you (and me) at
  will, which is the cost the toggle exists to remove.

  **If you say nothing:** nothing is built — the design doc explicitly authorises no mechanism.
  - **Answer (via watch, 2026-07-30 00:23):** 1. rec 2. rec 3. rec,
    though plugins can suggest stuff

- **P1 · 2026-07-29 12:39 — #294: one task table or the landed entry/task split, for the SQLite store?**
  → answered (2026-07-29 15:59): **RULED — flatten (`wt/294`).** His words: *"if you're satisfied then rec:
    flatten."* The coordinator is satisfied — the rec was flatten, the flat schema is red-proved, and
    flattening is free only until the import stage. Authorises the schema shape only; the import stage
    (`dreamwork tasks migrate --dry-run`) is the next increment.
  - **Follow-up (loop, 2026-07-29 16:00) — what an entry has, and yes, tasks update many times.** A flat
    `task` row carries the id-level facts: title, priority band, type, origin (human|loop|unknown),
    open|landed state, blocked-on and related ids — plus the **free-text body**, which is exactly where
    notes and updates accumulate: that is what happens in the Markdown today (follow-up bullets appended to
    an entry across its life), and the flat schema keeps that body column so the behaviour carries over
    unchanged. An entry is not a single immutable message — it is the task's living text. Separately,
    `task_event` (from `#264`'s ratified design) records *state transitions* as append-only rows, so the
    history of grabs/status/priority/completions is queryable rather than buried in prose. Prose updates
    live in the body; state changes live in the event log; neither is frozen.
  The store's schema landed at `50f4933` with an `entry`+`task` join — but the design's own S1 ruling and the
  entry normalisation mean every entry is now exactly one task, so the join models nothing. The flat version
  (one `task` table) is already built and red-proved on `wt/294`.
  **`Q1` — keep the split (`50f4933`) or flatten (`wt/294`)?** **`rec`: flatten** — the design's S1 ruling chose
  it ("the schema loses a table and every consumer loses a join, permanently"), the work is done and proved, and
  flattening is free only until the import stage (after that it is the two-migrations error). Measured IGC:
  `.dreamwork/review/294-entity-shape.html`. Say "B without the strictness" for the flatten minus its stricter
  `NOT NULL`s and extra columns. A ruling authorises only the schema shape — no import, cutover, CLI, or rename.
  - **Note (human, via watch, 2026-07-29 15:46):** What is an entry? Like
    is this the event log or? Can we cleanly migrate our current tasks to
    sqlite with the recommended model?
  - **Follow-up (loop, 2026-07-29 15:50):** **An `entry` is not the event log — and neither
    schema choice touches the event log.** In the landed split (`50f4933`), `entry` is one
    ledger entry's *text* and `task` is the id-level facts (band, type, origin, state), with a
    join for the combined entries (`#138/#156` — one body, two permanent ids). The event log
    is a separate thing entirely: `task_event`, an append-only table of *transitions* (grab,
    status, priority, complete) from `#264`'s ratified design. Split vs flat changes how a task
    **at rest** is stored; `task_event` is the same either way.
    **And yes — the recommended (flat) model migrates cleanly, and `#353` is why.** The
    normalisation already split every combined entry, so each Markdown entry is now exactly one
    task: the import is one row per id, no join, nothing to reconstruct or guess. The import
    stage runs `--dry-run` first — parse every open and landed entry, report exact
    counts/ids/digests/conflicts, back up, import atomically, verify the DB before cutover,
    explicit rollback. That stage is the next increment **after** your ruling; the ruling
    authorises only the schema shape.
    **Still pending, unchanged:** `Q1` — keep the split (`50f4933`) or flatten (`wt/294`)?
    **`rec`: flatten.** Say `flatten`, `keep`, or `B without the strictness`.
  - **Note (human, via watch, 2026-07-29 15:59):** Okay, so what does an
    entry have? Cause if it's a message about a task, surely we could like
    add notes to the task and update it more than once? But anyway, if
    you're satisfied then rec: flatten.


- **P2 · 2026-07-28 — #417: four ways to put commits-per-period on the burndown, priced. Which, if any?**
  **Ask: `C1`, `C2`, `C3`, `C4`, or `none` — and `rec` takes C4.**
  Artifact: [`417-burndown-commits.html`](../review/417-burndown-commits.html) (`5fe331a`) — ten real
  renders of the real panel against the live ledger, at desktop and mobile.

  Your words were *"design needs to be considered since we have a pretty good design now and it would
  be easy to make it worse"*, so this is a proposal and **nothing has been built into the chart.**

  | | what it is | what it costs |
  |---|---|---|
  | **C1** | faint commit histogram behind the flow | height holds; the bars share a colour family with arrived/landed, so the chart gains a second thing to disambiguate. New motion idiom |
  | **C2** | thin sparkline rail beneath the axis | **+25px, which breaks the `burndown` guard's constant-height premise.** New motion idiom |
  | **C3** | commit count encoded in the level line's weight | no second scale at all, but the level line then means two things at once. New motion idiom |
  | **C4** | copy only — one figure line in the panel's voice | **+19px, no new motion idiom** — inherits `#218`'s median treatment |

  **`rec: C4`,** and the reasoning is that it is the only option that spends nothing on the chart's
  legibility, which is the thing you said not to trade. The other three each introduce a new motion
  gesture, and `transitions.md` has no size floor — so each is a bigger job than it looks. If you want
  the *shape* of commit activity and not just its size, that is `C1`, and `rec` is wrong for you.

  **Visual verdict, 19:10 — I looked at them myself.** grok is 401 and `@glm52` cannot see, but the
  coordinator can, so this is no longer owed and `defer` is no longer needed. I extracted the ten
  embedded renders and read them. **It changes one of the four answers and confirms the rec.**

  Context the reference render supplies and the prose does not: **the panel already carries two bar
  series** (arrivals above the axis, landed below), plus the level line, the provenance bar and `#218`'s
  median line. A third quantity is landing in an already-dense frame.

  → answered (2026-07-29 06:24): **`c3` + `c4`, and your hover answers my objection better than my
    rejection did.** I rejected `c3` because the weight→commits mapping is learned rather than obvious;
    exact per-column numbers on hover make it *learnable*, which removes the objection instead of
    arguing with it. So: cap weight 2-6px carries commits, the copy line carries the figures, and
    hovering a column shows that column's exact numbers.
    **Your question — yes, nearly: the level line is how many were OPEN at that period**, not tasks
    completed. The panel runs two tracks over one set of columns: the *level* (open count) above, and
    the *flow* below (arrivals up, completions down about a hairline). So the chunkiness you like will
    sit on the open-count track, and commits are a third fact on a line that already means one thing —
    which is exactly why the hover matters, and it should show all three, not only commits.
    One constraint carried into the work: **every height in this panel is fixed** so fresh data never
    moves the page, and `c4`'s copy line must not wrap. Recorded on `#417`; two follow-up tasks filed
    from your other notes.
  - **`c1` histogram behind — reject. It is invisible.** Side by side with the reference at the panel's
    real 553px I cannot tell them apart; the faint bars are lost behind the two series already there.
    It buys nothing measurable and still costs a new motion idiom.
  - **`c2` sparkline rail — the real contender if you want the shape.** It is legible: a thin curve in
    its own band below the axis, labelled *"59 peak commits/period"* at the right, and it does not fight
    the bars because it is not among them. Costs `+25px` and **breaks the `burndown` guard's
    constant-height premise**, which is a real bill, not a formality.
  - **`c3` line weight — reject, and this is where I disagree with the lane.** It offered `c3` as the
    fallback if you want shape. Seen rather than reasoned about, `c3` makes the level line **chunky and
    noisy** next to the reference's clean dashes, and thickness cannot be read as a quantity — so it
    degrades the chart's *primary* signal to carry a secondary one badly. If you want shape, `c2`.
  - **`c4` copy only — still the rec, with one fix.** The chart is untouched and the line sits in
    `#218`'s exact voice. **But as rendered it truncates:** *"16 median ledger commits per period · 59
    peak · 3 periods with n…"*. The lane priced this honestly as *"one ellipsised line"*; seeing it, an
    ellipsis reads as broken rather than terse. **Shorten the copy so it fits** — that is a condition of
    `c4`, not a reason against it.

  **So: `rec` is still `c4` (with the copy shortened), and if you want the per-period shape the answer
  is `c2`, not `c3`.**
  · **Mockups built, 2026-07-29 06:03 — `5a6c964`.** The renders already existed; what was missing was a
  way to compare them, so `417-burndown-commits.html` now opens with a **five-up strip (reference + c1–c4)
  at one scale**, all real renders of the real panel against the live ledger. Nothing is drawn or
  approximated. A guard asserts the strip covers every option **as a set** rather than counting to four,
  that every render decodes to the same width (a comparison at two scales is not one), and that none is
  blank — verified independently by deleting one option's cell, which reds exactly that set check.
  - **Note (human, via watch, 2026-07-29 05:51):** show me mockups of all 4
    options please.
  - **Note (human, via watch, 2026-07-29 06:21):** note: the link to the
    review artifact does not work (doesn't render as a link even) note: it
    was not obvious that this question had updated, we should show the
    updated ago or something as well as having an event get posted to the
    user (for notifications) that a question was updated. Add tasks for
    these.
  - **Answer (via watch, 2026-07-29 06:23):** I think c3 + c4. I like
    the chunkyness of the line. granted it's not that intuitively
    connected to the number of tasks (which I think is what the line is,
    right?) but yeah. it shows density of action still which is kind of
    nice. with regards to: "Encodes a third fact (commits) into the
    level line's cap weight (2–6px). The mapping is learned, not
    obvious." in the review doc: we should show exact numbers for each
    column on hover of that column. then it's very easy to learn.

- **P2 · 2026-07-27 — #275 Dreamhub auth: three calls left of the original six**

  **Sub-decisions:** `Q3`, `Q5`, `Q6`

  Shrunk again 05:20 — **all three recs are now measured, not reasoned**, so the argument moved
  into the artifact and out of here. **Artifact: `275-hub-auth.html`** (rebuilt, offline-clean).
  Q1/Q2/Q4 are settled or moot; `#360`'s ssh-rooted design supersedes the identity half.
  **Public/WAN serving stays forbidden until you rule** — nothing implemented, nothing bound.

  **`Q3` read-only, or read+write?** Rec **read-only**. Measured: watch.py's write routes are
  agent-steering, not content (`#288`), and dreamhub is GET-only today.

  **`Q5` ship a redacted `/summary.json` as its own task first?** Rec **yes** — it is the blocker
  whatever else you choose. Measured at `collect()`: `/data.json` serves questions.md,
  DREAMWORK.md and lessons.md in full, plus parsed entries, transcripts and status.json.

  **`Q6` who else ever reaches this hub?** Rec **you only, v1**.

  Accepted answers: `rec` (takes all three) · per-question (`Q3: …`) · free text · `not yet`.
  → answered (2026-07-29 05:56): **Q3 REFUTES the rec — read+write**, and the reason is much larger than
    the question: *"dreamhub should entirely replace watch.py for normal day-to-day use. All features
    from watch.py should be ported over. or watch.py should be refactored into modules and then they
    can be imported to use in dreamhub."* So dreamhub is not a read-only window onto the loop, it is
    the successor surface — which makes `#368`'s extraction the enabling work rather than a cleanup.
    **Q5 yes** — redacted `/summary.json` ships first. **Q6 `rec`** — him only for v1, multi-user
    hubs later. Recorded on `#275`, `#368` and `DREAMWORK.md`.
    **This does NOT lift the public-serving gate:** he answered what dreamhub should DO, not where it
    may listen. Public/WAN serving stays forbidden pending a reviewed design, and read+write raises
    that bar rather than lowering it.
  - **Answer (via watch, 2026-07-29 05:54):** 3. read+write. dreamhub
    should entirely replace watch.py for normal day-to-day use. All
    features from watch.py should be ported over. or watch.py should be
    refactored into modules and then they can be imported to use in
    dreamhub. 5. sure 6. rec (multi-user hubs can come later)

- **P1 · 2026-07-29 05:00 — #294: the SQLite ledger migration — five calls on how the loop's own memory moves**
  **Artifact:** `.dreamwork/review/294-ledger-sqlite.html` — the design, the IGC, and what each option costs.
  Design only; **nothing is built**, and shipping is gated on `#263` lane H and `#352` regardless of your answer.

  This is the ledger — the loop's memory — so the migration is the one place a mistake is not recoverable by
  re-running anything. The design is deliberately conservative and it refuted the option that looked safest.

  **Sub-decisions:** `R1`, `R2`, `R3`, `R4`, `C1` — **`rec` takes all five.**

  - **R1** — the id sequence lives in the store (`AUTOINCREMENT`, seeded from today's next id and **verified**
    before cutover). Ids are permanent and never reused, so the sequence is the one thing a bad import cannot be
    allowed to reset.
  - **R2** — cutover takes an **exclusive lease** and consumes `#263` lane H's version gate. **Dual-write
    shadowing was refuted**, and the decisive error is worth your eye: a shadow period means two truths, which
    is exactly the second derived truth `#264` exists to remove.
  - **R3** — git history imports as **first-sight synthetic events**, attributed `actor=migration:git` rather
    than to you or the loop, so a reader can always tell a reconstructed event from a witnessed one.
  - **R4** — `tasks.md` becomes `tasks.md.deprecated` plus a **one-line shim** carrying a `#458` migration
    notice, so an agent still reading the old path is told where the ledger went instead of finding it stale.
  - **C1** — confirming v1 stays **machine-local**: no hosted store, no network, same trust boundary as today.

  **If you say nothing:** nothing is built and nothing blocks — the design sits in
  `.dreamwork/docs/plans/ledger-sqlite.md`, the Markdown ledger keeps working, and `#294` stays open. The cost of
  waiting is only that `status.json`/ledger drift stays a `lint` warning rather than becoming impossible.
  → answered (2026-07-29 05:49): **`rec` — all five taken.** R1 store-held `AUTOINCREMENT` seeded from
    today's next id and verified before cutover; R2 exclusive lease consuming `#263` lane H's version
    gate, dual-write shadowing stays refuted; R3 git history as `actor=migration:git` synthetic
    first-sight events; R4 `tasks.md.deprecated` plus a one-line `#458` notice shim; C1 v1 stays
    machine-local. Recorded on `#294`. **Nothing is built by this answer** — shipping remains gated
    on `#263` lane H and `#352`, which his own entry says and the ruling does not change.
  - **Answer (via watch, 2026-07-29 05:48):** rec

- **P2 · 2026-07-29 02:56 — #462: may the dashboard run `just deploy` when you click it?**
  → answered (2026-07-29 03:52): **Q1 `rec` — yes, the page may run `just deploy`.** So the staleness row
    becomes an action, not a copyable command: loopback-only, behind the existing confirmation idiom, and it
    must say what happened when the new generation never arrives. Recorded on `#462`; the surface work is
    queued behind the lane that currently holds `watch.py`.
  → asked after your 02:30 request for an 'update & reload' control. The lane built the affordance and then
  hit a consent question it will not answer for you.

  **What it found, and it is the reason the button cannot just be built:** the deployed dashboard serves a
  **snapshot** taken by `just deploy`, not your working tree. So neither cheap option does anything — a
  browser reload re-fetches the same snapshot bytes, and `watch.py`'s own `--autoreload` re-exec is
  byte-identical for a deployed server because its `__file__` *is* the snapshot, outside the repo. "Update"
  can only mean **re-snapshot from HEAD and restart**, which is exactly `just deploy`.

  So the question is not technical. It is whether a page may run that.

  **Sub-decisions:** `Q1`, `Q2`

  - **Q1** — may the page trigger `just deploy` on click? It means an unauthenticated, loopback-bound HTTP
    request runs deploy machinery on your box. Failure *is* visible (the loaded page keeps polling and says
    so when the new generation never arrives) and your drafts survive it, so the objection is authority,
    not safety. **`rec`: yes**, loopback-only and behind the existing confirmation idiom.
  - **Q2** — if no: keep what is landing now, which is the command surfaced on the staleness row, copyable
    on click. Or would you rather it not appear at all?

  **If you say nothing:** the copy-the-command version ships and nothing runs itself — you keep the one
  extra step you have today, and the row at least tells you what to type.
  - **Answer (via watch, 2026-07-29 03:46):** rec

- **P1 · 2026-07-29 02:42 — #445: ratify the four attention levels, and how they sit beside the run modes**
  → answered (2026-07-29 03:50): **ratified with amendments.** Q1 `rec` — three orthogonal axes stand.
    Q2 — widen `run-mode` eventually but *not yet*: convert today's three values into the new vocabulary first,
    and give each axis its own control with about **three stops**, the exact stops left to the loop. Q3 — the
    subagent number is an **average-concurrency target, not a cap**: `0` means occasional (use one when it is
    necessary or a particularly good choice; average below 0.5 running), `1` means an average between 0.5 and
    1.5, and so on — interdependence still governs, and **two agents may pair on a single worktree**, talking
    to each other via `subagent-protocols`. He also asked that skill be bundled with dreamwork (`#466`).
  **Artifact:** `.dreamwork/review/445-attention-modes.html` — context, the problem, the IGC, and a
  recommendation. Design only; nothing is built.

  Your dictation gave four levels for how much the loop asks you. Designing them turned up a structural
  finding worth your ruling before anything is built: **`run-mode` today carries three independent decisions
  in one word.** The decisive evidence is this session — you told me *"be lackadaisical, but also use
  sub-agents"* in prose, twice, because no control could express it. One enum cannot; the design resolves to
  **three axes: pace × asking × delegation**.

  **Sub-decisions:** `Q1`, `Q2`, `Q3`

  - **Q1** — ratify three orthogonal axes (pace × asking × delegation)? Or collapse them differently.
  - **Q2** — your four level names as the closed set, and **where the asking axis lives**: a sibling file (no
    migration) — recommended — or widen `run-mode` into a multi-field file (needs a `Migration:`).
  - **Q3** — the subagent target and policy: an integer target `>= 1`, warn on `0`, hard-invalid below `0`, plus
    free text, read every tick like `run-mode`. Or amend.

  **If you say nothing:** nothing is built and nothing blocks — the design sits in
  `.dreamwork/docs/plans/attention-modes.md` and the loop keeps its current posture, which is your prose
  instruction rather than a control. `#443` stays open, since it is the same knot.
  - **Answer (via watch, 2026-07-29 03:45):** 1. rec 2. widen it, but we
    don't need to do that yet. We can just convert the current modes
    into the new values. we should add controls for the new values and
    their dimensions. We can have like 3 stops on each axis maybe? IDK
    that i will leave up to you, but we get 3 dimensions of input is the
    point. 3. I had a thought about this: 0 can mean that subagents
    aren't necessarily banned or w/e, but they should only be used when
    a subagent is necessary or a particularly good choice. So like
    occasional subagent use. Another way to look at it is that the avg
    number of subagents running at any one time is <0.5. if the setting
    is 1, then the avg number of subagents should be 0.5 < x < 1.5. or
    the target number of subagents running at any one time is that. ofc
    we still need to be aware of interdependent work and all that, but
    should be fine. we can get agents to work on a single worktree as a
    pair, too. they can talk to eachother via /subagent-protocols
    (another skill we should bundle with dreamwork, btw, please add that
    as a task)

- **P2 · 2026-07-29 01:14 — #269: build it? (authorisation only, no design content)**

  → answered (2026-07-29 01:43): **granted, conditionally** — *"yes, provided no good reasons
  not to."* There is one reason worth knowing and it changes the shape, not the answer: the shipped
  `localStorage` path is **synchronous and cannot fail mid-keystroke**, while IndexedDB is async and
  a wedged store is a hazard `watch.py:2300` already races with a timeout. So a straight swap could
  make the **acute** path worse. Recorded plan: keep `localStorage` as the synchronous write, add
  IndexedDB as the durable / GC / cross-tab layer beside it. And `#459` (two boxes with no draft at
  all) is sequenced **first** — a missing draft outranks a better-stored one.

  You just settled C1 (`R1`) and C2 (30 days), so `.dreamwork/docs/plans/draft-durability-design.md`
  has no open design decision. This is only the build grant — the same shape as `#254`'s,
  which is the pattern `#451` wants queued separately.

  Scope if yes: per-field IndexedDB drafts keyed by the title-derived logical id, restore
  on load, the cross-tab prompt, 30-day idle GC, explicit forget. Out: anything touching
  `questions.md` on disk.

  Accepted answers: `yes` · `yes, but …` · `not yet`.
  - **Answer (via watch, 2026-07-29 01:43):** yes, provided no good
    reasons not to.

- **P1 · 2026-07-28 — #264: ratify the task-transition boundary, and one deployment call only you can make.**
  → answered (2026-07-29 01:43): **`rec` on the boundary and `(c)` on the deployment call, plus *"we
  should keep a .jsonl log"*.** Folded into `#264`; the log requirement is recorded there. The marker was
  dropped at fold time, which is the regression this check exists to surface (#411).
  Artifact: `.dreamwork/review/task-transition-boundary.html` (open it from
  the dashboard's review list); design at `.dreamwork/docs/plans/task-transition-boundary.md`,
  landed design-only at `914648c`. **Nothing is built** — no table, no CLI, no migration.
  **You are right that this was missing and it was my failure.** I told you in an answer at 15:02
  that ratifying `#264` was *"the only thing of this chain on your desk"*, and there was **no
  question here for you to rule on** — so the thing I called your blocker was one you had no way to
  clear. That is the exact shape you named at 15:19, and the general fix is filed as `#419`.
  **Q1 — ratify the boundary?** Your question was *"decide whether it shares #263's journal or uses
  a task-state outbox, but never dual-write two fallible truths."* The design's answer is **neither
  as posed**, because both options assume a task transition and a user event are the same kind of
  fact. *"Never dual-write two fallible truths"* forbids storing one fact **twice**, not storing
  **two** facts — and *"he asked for this at 14:11"* and *"the loop started #264 at 01:47"* are two
  facts whose whole relationship is a foreign key.
  The shape: **a task transition is one row appended to its own append-only `task_event` log, in
  the same SQLite database as #263's journal, in the same transaction as the CAS that moves
  `task_state`. No outbox, no drain.** Burndown and the dashboard status section become **queries**
  over that log, so neither can be stale. `task_state` is the only materialised row in the design,
  and only because a claim needs something to CAS against; it is rebuildable and replay-verified.
  **Rec: ratify.** It is strictly fewer moving parts than either option you named, and F1 in the
  doc records that the two truths we have today already disagree by 9.
  **Q2 — git portability, and this one is genuinely yours because it is a deployment choice.**
  The ledger is committed project content today, so **the burndown works on a fresh clone — git
  history *is* the source.** A SQLite store is gitignored and machine-local, so a clone starts with
  no history. Three ways:
  **(a) commit the database** — binary and unmergeable, and two agents on two machines will
  conflict irreconcilably. **(b) gitignore the DB and commit a deterministic append-only text
  export of `task_event`** — mergeable, and rebuild is *provable* because the event chain
  re-verifies. **(c) accept machine-local for v1** and lose cross-clone history.
  **Rec: (b).** It keeps the property you already have without paying for a binary in git, and the
  canonical byte form is defined in the design's §Ordering — which is what makes this a deployment
  decision rather than a schema change.
  **What ratifying does NOT authorise:** nothing is built by it. The migration, its cutover
  ordering, whether git's 331 revisions become synthetic events, rollback, `tasks.md.deprecated`'s
  frontmatter and the mixed-writer freeze are all `#294`'s, all after a ruling. Four smaller things
  stay open in the doc's own §"What stays open" and none of them blocks a start.
  **`#294` is your stated blocker and this is the last thing in front of it** — `#346`'s next
  increment (eight red-first fixtures) needs no ruling and is ours to start regardless.
  - **Answer (via watch, 2026-07-29 01:43):** 1. rec, is good 2. I think
    (c) -- in the future the way we deal with this is via the dreamhub.
    Right now we can assume it's running locally only. or at least in
    serial. having a determinisitc log of events though that can be
    reprocessed possibly by other tools later or as part of recovery,
    that is a good idea though. we should keep a .jsonl log I think,
    that way it's as flexible as we need it to be and we just need to be
    sure to capture enough detail and we'll be able to recover no matter
    what. We can add a future task (low priority for now) to write a
    tool to process this and reconstruct the DB. that way we know it'll
    work + we can run tests against fixtures and ensure determinism,
    etc. that will at least allow us to set a consistent rule for how to
    merge event streams.

- **P1 · 2026-07-28 — #263: the second gate's condition is met, verified this time. Open it?**
  → answered (2026-07-29 01:37): ***"ack good to go"* — the second gate is OPEN.** Lanes E, G and H
  authorised; payload purge and the PostgreSQL half stay excluded by the earlier Q4 ruling. Folded into
  `#263`; E1-E4 have since landed. Marker dropped at fold time (#411).
  **Ask: `rec` for "open E and H, split `#368` first" — or answer Q1/Q2/Q3 separately.** Free text
  fine; *"not yet"* is a real answer.
  **Q1 — open the gate for lane E** (increments 20–25, the HTTP cutover: the journal commit, not the
  handler, authorises the response)? **Rec: yes.**
  **Q2 — open it for lane H** (34–35, the mixed-version gate)? **Rec: yes for the code**; I will not
  run it against your live target without asking again.
  **Q3 — does `#368` (the modular split) land before lane E starts? Rec: split first.** Your own note
  in the plan said so. Measured now: `watch.py` is **9,688** lines — your 8,647 was stale — and **6 of
  6** of lane E's production increments touch it, adding no new module. Serial-now is the honest
  alternative and gets `#371`'s remaining half sooner.
  **What is different from my 16:24 ask, which was wrong.** I told you the condition was met; lane C
  was **3 of 5**. `C4` and `C5` landed at 17:21, so **A 2/2 · B 8/8 · C 5/5 · D 4/4 · F 4/4** and
  *"until A–D are proved"* is satisfied. **This time a merge gate asserted it**, taking its
  denominator from the plan's own increment table rather than from a lane's *"3/3"* — which is
  precisely the sentence I misread. The gate is red on `master` and passes on the merge, so it can see
  the absence it checks for.
  **Your 17:38 message lands on Q3 and I have folded it in.** If `#368` goes first, its **first
  increment is `#425`** — the monolith moves to `deprecated/watch.py` and `watch.py` becomes a symlink,
  so a client that started before the split keeps working. That makes split-first slightly cheaper than
  I priced it above (the symlink is the compatibility story, not a later migration), and it is filed as
  blocking `#368`. The general principle is `#426`.
  **Opening the gate does not authorise:** lane **G** (30–33, never in `G1`), increment 18's purge or
  19's PostgreSQL half (your Q4), or any migration of a live target.
  Optional: artifact `.dreamwork/review/263-second-gate.html` (**being rebuilt** — it still says
  3 of 5), plan `user-event-journal-implementation.md`.
  - **Note (human, via watch, 2026-07-29 01:22):** for this artifact page,
    please add to the top of it: - a paragraph explaining the context - an
    explanation of the problem - the IGC goals, ideas, and table. - your
    recommendation. be concise.
  - **Answer (via watch, 2026-07-29 01:37):** ack good to go

- **P1 · 2026-07-28 — #421: how the loop should ask you things (A/B/D live; C withdrawn on your note)**

  → answered (2026-07-29 01:17): **`rec` — A + B + D adopted**, C withdrawn. Plus the
  length rule refined: steer style with **descriptors** (precise, detailed, concise, dense),
  plan the words in advance, and a soft estimate is fine (*"aim for under 200 words"*) —
  models will be out, and inconsistently so. *"We just want to steer the soft stuff, not try
  to measure it."* Folded into DREAMWORK.md; B is the buildable half (`lint` errors on a
  dropped sub-decision).

  **One-minute version: `.dreamwork/review/421-qs-opts-short.html`.** Long page and corpus
  figures: `421-question-options.html`.

  **A** — the ask comes first, with the accepted answers. **B** — an unanswered sub-decision is
  recorded and `lint` errors when a fold drops one. **D** — state what a valid answer looks like.
  **Rec: A + B + D.** B is the only one with a live defect behind it — `#275`'s Q3/Q5/Q6 have been
  unanswered since 2026-07-25 and nothing notices.

  **Rejected, by your own data: one decision per entry** — **15 of 16** of your multi-part answers
  closed complete, so it would multiply items on your desk for a rare problem.

  ~~C — a ~250-word budget~~ **withdrawn 01:13 on your note**: *"don't quote word counts or whatever.
  like things like that which become errors too easily (are brittle)."* The intent survives without
  the number — evidence belongs on the artifact, judged by whether the ask reads short, not counted.

  Accepted answers: `rec` · any combination of `A`/`B`/`D` · free text · *"none of these"*.
  Note `#445` (your four attention levels) may retire this entry outright — say so if it does.
  - **Answer (via watch, 2026-07-29 01:17):** rec. with word counts,
    better to use descriptors like precise, detailed, concise, dense,
    etc to describe writing style. Tell the agent to plan out the words
    in advance so that it can be concise if you need to. You can also
    provide estimates (like: aim for under 200 words) with the knowledge
    that agents will be out but that amount out will proibabyl be
    somewhat consistent for that model (though different models might be
    totally different). Anyway, don't worry to much about it. We just
    wnat to steer the soft stuff, not try to measure it.

- **P1 · 2026-07-29 — #269 draft durability: two calls (C1/C2)**

  → answered (2026-07-29 01:12): **rec on both** — C1 = **R1** (offer *"updated in
  another tab — load?"*, never swap text under him) and C2 = **30 days** idle GC by
  `updatedAt` plus explicit *forget this* / *forget all for this project*. Design is now
  fully settled; folded into `.dreamwork/docs/plans/draft-durability-design.md`.

  Artifact: `.dreamwork/review/269-draft-durability.html` · Spec:
  `.dreamwork/docs/plans/draft-durability-design.md`

  **C1 — cross-tab, when two unfocused copies diverge.** Rec **R1**: offer
  *"updated in another tab — load?"* rather than swapping text under you. Alt
  **R2**: silently take the newer store when the field is unfocused. Either way a
  **focused or dirty field is never overwritten** — that part is settled.

  **C2 — orphan retention.** Rec **30 days** idle GC by `updatedAt`, plus explicit
  *forget this* and *forget all for this project*. Alts: 7d · 90d · never GC
  (explicit only). These are your words being kept on disk, so the number is
  yours.

  Settled without you: the logical id (title-keyed, no fuzzy restore), the
  clear-on-receipt seam (`res.ok` today, `#263`'s receipt later, behind your
  gate), localStorage first and IndexedDB later, and nothing built behind the
  `#263` second gate. The acute loss you reported is already closed.

  Accepted answers: `rec` · `R1`/`R2` plus a day count · free text ·
  `defer, implement the rest`.
  - **Answer (via watch, 2026-07-29 01:12):** rec

- **P1 · 2026-07-29 01:03 — #449 framey dissolve: the mist itself is the cost, and it is all-or-nothing**

  → answered (2026-07-29 01:05): **M3, framed as temporary** — *"let's try temporarily
  disabling the svg filter. we can make up for it as best we can with css."* Relayed to the
  `mistperf` lane: both filters off (its measured +128% frames, worst frame 262 → 129ms),
  CSS carrying as much of the gesture as it can, the mist left recoverable behind one named
  switch with the measurements beside it, and `transitions.md` + `watch-design.md` updated in
  the same commit. Successor candidate, filed not built: his moving/tiled-texture idea.

  **V1 is refuted — sorry, your call was sound and the measurement killed it.**
  Clamping the mist to the viewport cut 42% of the filtered area (553×1557 →
  553×900) and changed nothing: 13.7 → 13.7 frames, worst frame 184.9 → 187.4ms.

  **What the lane actually found**, and it is a threshold, not a gradient: removing
  **either** filter alone ≈ baseline; removing **both** → frames 12 → 28 (+128%),
  worst frame 262 → 129ms. Freezing every per-frame attribute write ≈ baseline. So
  the cost is two SVG filter rasterisations per frame contending with the shader —
  and **any** amount of mist costs the same as all of it.

  **So the only lever left is the gesture, which is yours, not mine.** Options, and
  I have no rec I trust yet: **M1** mist the departing ghost only and bring the
  incoming view in on a cheap CSS blur (one filter — but "either alone ≈ baseline"
  says that may buy nothing, so it needs measuring before you pick it); **M2** keep
  the mist and accept the frames on tall pages; **M3** drop to CSS blur both ways —
  fast, and a real loss of the liquify. Accepted answers: `M1` · `M2` · `M3` ·
  *"measure M1 first"* (rec if you want one) · free text.

  ~~Q1 freeze `baseFrequency`~~ withdrawn 00:52 · ~~V1 viewport-clamp~~ refuted
  01:00, both by measurement. Full numbers in `#449` in the ledger.
  - **Answer (via watch, 2026-07-29 01:05):** let's try temporarily
    disabling the svg filter. we can make up for it as best we can with
    css.

- **P1 · 2026-07-28 — #254: authorise implementation of the threaded-notes design?**

  → answered (2026-07-29 01:01): **Approve I1** — *"yes"*. Implementation authorised
  as the spec; scope exactly as stated. Queued behind the `mistperf` lane, which holds
  `watch.py` and `test_watch.py`.

  Design is written at `.dreamwork/docs/plans/threaded-notes-spec.md` (post-R1;
  supersedes `note-reply-threading-254.md` for implementers). N1 + R1 are settled;
  no design decision left open. This ask is the separate implementation grant your
  23:03 approval explicitly withheld.

  Scope if accepted: recognise `- **Reply (loop, <ts>):**` as a loop *resolution*
  tag (together in `NOTE_TAGS` / parser / `file-formats.md` / tests — never the
  format ahead of the parser); implement `qaBranch` as specified; one flat branch
  at one inset under the root; a11y nested list; 390px keep-rail/drop-padding;
  reuse existing transition matrix cells only; frozen fixtures F1–F6 and the
  named red-first checks. Out of scope still: true nesting, `## Answered`
  threading, two-answer retention (now `#446`), Answered raw-Answer lift.

  No artifact: the lane found no decision genuinely yours left open, and a decoy
  ask is worse than none. Before/after rendering is in the spec's §3.

  Rec **I1: authorise implementation as the spec**. Answer `Approve I1`,
  `Approve I1 with changes: …`, or `Hold; not yet`.
  - **Answer (via watch, 2026-07-29 01:01):** yes

- **P1 · 2026-07-29 — #288 contain vs detect: is the wall worth wiring, or are the positive invariants the whole defence?**

  → answered (2026-07-29 00:50): **A, trimmed further — plan it, do not build it.**
  Positive invariants are the defence; the wall stays prototyped and unwired. Note the
  deficiency explicitly and warn per harness where interception is impossible. Trusted
  nodes only until isolation exists. Filed as `#450`.

  Artifact: `.dreamwork/review/288-containment.html` · Spec:
  `.dreamwork/docs/plans/subagent-containment.md` · Prototype:
  `dev/containment_falsify.py`

  **A (rec):** ship the positive PID/health invariants as the whole defence —
  `GENERATION` ≥ snapshot mtime **and** snapshot bytes == HEAD bytes, sampled each
  tick, with a subagent's "PASS" downgraded to *suspect* on contradiction. That
  catches the `#288` class completely, within a tick, at negligible cost.

  **B:** spend the integration cost to route tool calls through a real wall —
  knowing it is `#358`-shaped, because the harness owns both the API call and tool
  execution in one process, so a wall around the harness contains the API key too.

  The wall itself works: all three incident vectors HELD at ~22ms per contained
  process on this host. The finding is that **the seam to cut is not ours** — so
  this is a build-authorisation question, not a feasibility one.

  Accepted answers: `rec` · `A` · `B` · free text · `not yet`.
  - **Answer (via watch, 2026-07-29 00:50):** don't do anything too
    expensive or time consuming. just plan for it and make sure the
    deficiency is noted. We are just going to be testing with our own
    trusted nodes first, so provided we can implement isolation layers
    later, then we can. Re claude code, we can have that kind of thing
    where we can't do tools or intercepts or whatever, we'll just have a
    warning next to it that it lacks certain protections. but i mean
    that's fine, if someone else is providing the api key then they can
    probably provide the harness, too.

- **P1 · 2026-07-28 — `ccc @grok` is 401 again, and it is your credential.**
  → answered (2026-07-28 19:15): *"note grok should be working again"* — confirmed by probe, `ALIVE`
  at 19:16, and a lane (`#434`/`#435`) is running on it now. Down ~16:50 to ~19:15, the second outage
  today. `#423` keeps the loop-side half, which is ours and not yours: a 401 dispatch exits **0**, so a
  dead runner is indistinguishable from a slow lane, and a lane that exits without committing should be
  recorded as failed — that happened for real today with the work recoverable only from a dirty
  worktree.
  **Ask: refresh grok's auth when convenient, then say so here (a bare "ok" is enough).** Nothing
  else needed from you.
  Recurrence of the ask you closed at 14:48 with *"ccc @grok now working again"*. It ran fine from
  then until **~16:50** — three lanes landed on it in that window (`#367` previews, `#172`, and the
  `#263` gate artifact twice) — and then went 401 mid-dispatch. Probed twice at 16:53, both
  `Unauthorized (401) … Invalid or expired credentials (auth_kind=none … reason=no auth context)`.
  **Cost, so you can judge the urgency:** it halves lane capacity and removes the only lane that can
  **see**. `@glm52` is unaffected and three of its lanes are running now, so work continues — but
  visual verdicts on rendered pages have no owner until grok is back. The `#421` options artifact was
  mid-flight when it died and is being re-dispatched to `@glm52` with the seeing half deferred.
  **Not asking you to change tools.** Two 401s in one day is worth recording rather than reacting to;
  if it recurs a third time I will propose something.


- **P2 · 2026-07-28 — #367: what do 5–7 marks become below the cliff?**
  → answered (2026-07-28 15:11): **C, with a collapsible index** — *"can we do C but: add a
  little double chevron on RHS indicating that the bar is collapsible, and when it expands it
  should show a list of the marks. Collapsed by default."*
  **This is neither of the options as posed and it is better than both.** It pays C's 31.8px by
  default and A's 167.9px only when asked for, so the overview stops being a permanent tax and
  becomes a disclosure. The cost I asked him to price — *"it loses the at-a-glance overview"* — is
  the one thing his answer removes, and the previews are what made that visible: A read lighter
  than my number and C read like a real walk, so combining them was the obvious move once both
  were on screen rather than in prose.
  Spec for increment 2b: default collapsed at the walk height; a double chevron at the right-hand
  edge as the affordance; expanded reveals the labelled marks. **`transitions.md` governs the
  expand and collapse with no exception** — it arrives and departs, it does not snap, and reduced
  motion gets identical meaning. `aria-expanded` on the chevron and keyboard parity are not
  optional. Two things left to the implementer rather than asked: whether the expanded list
  replaces the walk row or sits beneath it, and whether the expanded state persists across
  navigation.
  Artifact: `.dreamwork/review/367-strip-below-cliff.html` (one decision, three
  options, ~2 screens). It has the specimen that makes the case in one glance.

  **Your 05:35 ruling — two-line tabs, ~6 words, nobody truncates — moved two
  things and I have taken both, reversibly:** a worst-case tab is **180×32.3px**,
  not the 96px one-line flag every number rested on, so the rail/strip cliff is
  **~830px** and not the literal 780 (at 780 the flag is clipped **mid-word**);
  and two marks closer than a tab height are the renderer's problem, not an
  authoring rule you have to remember.

  **The one thing I cannot decide for you:** below the cliff there is no lateral
  space — the reading column is fixed at 613.5px and the page's outer margin is
  16px at every width from 1120px down — so at your soft cap of 7 a strip needs
  **3 rows and ~214px** of chrome stacked above the text. Truncation is off the
  table because you removed it.

  - **A · Pay the chrome** — the strip grows to as many rows as the marks need.
  - **B · Bounded strip, then "+3 more"** — **rec: reject.** Keeps the chrome
    *and* becomes an incomplete index, and it truncates the *set* rather than a
    label, which is the argument you already rejected one level up.
  - **C · Just the walk — rec.** No labels in the chrome below the cliff: one row
    with next/prev and "3 of 7", and the label appears *at* the mark you land on.
    ~32px instead of 214, nothing truncated, every mark reachable. The rail's
    affordance is lateral space at a height; below the cliff there is none, so
    preserving the *index* preserves the wrong half. The *walk* was your own
    second sentence.

  **The honest cost of C, which is yours to price:** it loses the at-a-glance
  overview. On a narrow window you would have to walk the marks to learn what
  they are. A says that overview is worth 214px; C says it is not.

  **This does not block increment 2a** — the rail, tab and next/prev *above* the
  cliff — which is fully specified and whose brief is written. 2a renders
  **nothing** below the cliff rather than a provisional strip, deliberately: a
  provisional strip is what ships and then gets argued with once you rule.
  Increment 1 has already landed and changed no artifact you have read.
  - **Note (human, via watch, 2026-07-28 14:52):** can you generate
    previews of each of the options and what they would look like please? I
    tihnk C is fine but want to see it first.
  - **Follow-up (loop, 2026-07-28 15:10): the previews are built, and they correct a number
    I gave you.** Artifact: **`.dreamwork/review/367-option-previews.html`** (open it from the
    dashboard's review list). All three options render at true below-cliff geometry with seven
    realistic two-line labels, and **every figure on the page is measured from the rendered DOM
    at load** — nothing is captioned by hand, red-proved by changing a row count and watching the
    caption follow.
    **Measured chrome, at 780px and at 640px:** **A 167.9px** (3 rows) · **B 127.2px** (2 rows +
    "+3 more") · **C 31.8px** (1 row). **I told you A costs ~214px. It costs 168.** The 214 was a
    worst-case extrapolation from a 180px tab; with realistic mixed labels the pills pack into
    three tidier rows.
    **A second correction, smaller but yours to know:** *"the reading column is fixed at
    613.5px"* holds down to 780 and **not** to 640, where it shrinks to 608 because 78ch stops
    fitting. **The 16px outer margin does hold at both**, so the "no lateral space below the
    cliff" argument — which is what the whole decision rests on — survives unchanged.
    **What seeing them changed, honestly.** The lane recommended C and so do I, but it also
    reported, and I agree having looked at the screenshots myself, that **A reads lighter than
    its number implied** — three tidy rows of product-shaped pills, not a wall. So if you often
    want the index *before* walking, A is more defensible than my 214 made it sound. **B is still
    reject** and looks worse in pixels than in prose: it keeps most of A's height and loses the
    complete index. C at 31.8px reads as a usable walk rather than a stub.
    **Still your call, and nothing is built** — increment 2a still renders nothing below the
    cliff until you rule.
  - **Answer (via watch, 2026-07-28 15:11):** Okay, can we do C but: -
    add a little double chevron on RHS indicating that the bar is
    collapsible, and when it expands it should show a list of the marks.
    Collapsed by default.

- **P2 · 2026-07-28 — `ccc @grok` (only `grok-4.5`) is 401; the other eleven models are fine.**
  → answered (2026-07-28 14:48): **option 2 — he refreshed the xAI key**, and I
  verified it rather than taking the claim: `ccc --yolo @grok` returned *"PROBE OK, Grok 4.5"*
  at 14:50. So `grok-4.5` is back and the fleet is the two aliases he named, with no config
  change of mine. The dogfood consequence is the point: everything measured between 05:52 and
  now was **one runner twice**, and from here a grok lane and a glm52 lane can run side by side
  on comparable work — recorded in `.dreamwork/docs/dogfood-orchestration.md`. The wider
  `llmp-*` fleet stays available as a fallback and needs no decision.
  Two lanes died at three seconds today with nothing in the tree. Verbatim:
  `Unauthorized (401) from https://cli-chat-proxy.grok.com/v1/responses: Invalid or expired
  credentials (auth_kind=none, x_xai_token_auth=xai-grok-cli, upstream=Unauthenticated,
  reason=no auth context)`, `Model: grok-4.5`, ccc `0.2.112`.
  **`ccc @glm52` is fine** — same runner binary, and it answered a probe instantly, so this is
  one model's credential and not the CLI. Work is continuing on glm52; `#399b` (the burndown
  regression that has `master` red) is running there now.
  **Correction, 11:12 — I had this backwards and the news is good.** `grok models` now lists
  **twelve** models and prints `Default model: llmp-glm-5-2`. At 05:52 that same command
  returned `grok-4.5` and nothing else, which is why this morning's dogfood note recorded
  `@glm52` as *"BROKEN — cannot work"*. The `llmp` provider became reachable through the grok
  CLI at some point today — your config never changed — so the fleet got **wider** during the
  outage: `grok-4.5, llmp-gpt-5-6-{luna,terra,sol}, llmp-gpt-5-{5,4-mini}, llmp-glm-{4-7,
  5-turbo,5-1,5-2,5,4-5-air}`. The CLI says the `llmp-*` models use a separate API key, which
  is why they work while `grok-4.5` does not.
  **So nothing is blocked and nothing is narrower** — one model of twelve is out. Worth your
  refresh whenever convenient, not urgent. I am not touching the credential; that is yours.
  Filed as `#410`.
  Worth knowing for the provider question you set me: the outage was **invisible** for two
  lanes because I was dispatching with `> /dev/null 2>&1`. ccc's own run log does not help —
  `~/.local/state/cc-w/ccc/runs/<run>/output.txt` is **zero bytes** for a 401. I now capture
  stderr on every dispatch, which is how this got diagnosed at all.

  **Follow-up 2026-07-28 12:43 — re-measured, and now it needs a decision from you, not a
  refresh.** Still 401 (probed 12:41), verbatim the same error, so this is stable and not a blip. I have read
  your `~/.config/ccc/config.toml` and the cause is exact: `[aliases.grok]` is
  `runner = "grok"`, `model = "grok-4.5"` with **no provider**, so it authenticates to xAI
  directly with the expired key; `[aliases.glm52]` is the **same runner binary** with
  `provider = "llmp"`, which has its own key and works. One credential, one alias.
  **The decision.** You told me to use `ccc @grok` and `ccc @glm52` and *only* those. One of
  them has been dead all day, so I have been running a **single lane** — for #399b, and now for
  #331 — where you sized the fleet at up to four each. Everything since 05:52 has therefore been
  one runner's behaviour measured twice, which is a much weaker answer to the "which models and
  providers are best for us" half of what you set me than it looks.
  Three ways out, in the order I would pick them:
  1. **Point `@grok` at a working provider** — e.g. `provider = "llmp"` with one of
     `gpt-5.6-terra` / `gpt-5.6-luna` / `gpt-5.6-sol`. Keeps your two-alias instruction intact,
     gives me a genuinely different model to compare against glm-5.2, and needs no credential.
     **This is my recommendation**, and terra is the one I would try first since your own
     `cx-reviewer` alias already trusts that family.
  2. **Refresh the xAI key** so `grok-4.5` itself comes back. Best if you specifically want
     grok-4.5 in the comparison; only you can do it.
  3. **Let me use `@glm51`** (your existing opencode + zai-coding-plan alias). Available right
     now, but it is a third alias you did not name, and glm-5.1 next to glm-5.2 is the least
     informative pairing of the three.
  I have not changed your config and will not — say which, or say "keep going on one lane" and
  I will, and record the comparison as single-runner rather than implying otherwise.
  - **Answer (via watch, 2026-07-28 14:48):** ccc @grok now working
    again

- **P2 · 2026-07-28 — one word: may I add `GIT_OPTIONAL_LOCKS=0` to `~/.claude/settings.json`?**
  → answered (2026-07-28 14:48): **yes**, and it is done — `~/.claude/settings.json`'s `env`
  gained `"GIT_OPTIONAL_LOCKS": "0"`, a one-key diff with nothing reformatted, verified by
  re-reading the file as JSON rather than by the write succeeding. It applies to **new**
  Claude sessions, not this one, so this session keeps taking real index locks until it
  restarts. `~/CLAUDE.md`'s mitigation paragraph is now true as written and needs no edit —
  the drift is closed by making the claim accurate rather than by softening it.
  `~/CLAUDE.md`'s git-index-lock entry says that setting is already there "for all Claude
  sessions". It is not — `settings.json`'s `env` has no such key, and `echo
  $GIT_OPTIONAL_LOCKS` in this session prints nothing. The other two thirds of that same
  mitigation paragraph **are** in place (the fish function has `--no-optional-locks`,
  `git-lock-watch.service` is active), so this one drifted alone and reading the paragraph
  would not tell you which third was false.
  It matters more than a stale doc: today's watcher log has **6,093** lock events in this
  checkout, because this session runs `git`, `lint.py` and `status_sync.py` many times a tick
  and each takes a **real** `.git/index.lock` instead of skipping it. `#283` was opened
  because that churn blocked a commit, and there is a live zero-byte orphan in
  `~/src/amaroo/.git/index.lock` right now (left alone — deleting another repo's lock on a
  guess is not a change I will make).
  **Yes** and I add the key. **No** and I correct `CLAUDE.md` instead so the next
  investigation does not rule this out as a cause. Either is fine; doing neither is the only
  wrong answer. Filed as `#408`, which also proposes auditing the other mitigation bullets the
  same way — each names a file or a unit, so each is one line to check.
  - **Answer (via watch, 2026-07-28 14:48):** yes

- **P2 · 2026-07-25 — #194: where does an upgrade check get its commit range?**
  → resolved (2026-07-25): the question was decided by the loop and withdrawn as an ask. Rec **(b)**
  stands. (The marker used to sit inside a two-line bold title, where `watch.answered_at` cannot see it —
  it reads only the head of the body.)
  Rec **(b)** stands — CI ships a generated changelog inside the release, and the
  upgrade pass reads a local file. Withdrawn under his 05:35 rule: option (a) puts a
  credential requirement in the startup path of a loop whose entire promise is
  running unattended, and fails with no network. That is not a taste difference, so
  I would be surprised by any answer other than the rec. (b) also removes the auth
  question instead of answering it, and produces a changelog worth having anyway.
  The git path stays available wherever history is present, so (b) costs nothing in
  a checkout like this one. Same decision settles the no-prior-hash fallback.
  Recorded in `.dreamwork/docs/plans/version-and-upgrade.md`.
  when the release has no repo?** Your version idea is captured and
  planned (`docs/plans/version-and-upgrade.md`); this is the one fork
  that decides step 4 onward, so I would rather ask than build both.

  The tension is inside the design and it is a real one: the CI
  replacement exists precisely so a **zip carries a hash without carrying
  the repo**. But the upgrade pass then wants every commit between two
  hashes, and `git@github.com:ultradyn/dreamwork.git` is private. So a
  zip-installed target has nothing to diff and no credentials to fetch
  with.

  Two ways out. **(a) Network + auth**: the pass fetches the range from
  GitHub. Real upgrade fidelity, but it puts a credential requirement in
  the startup path of a loop whose whole promise is running unattended,
  and it fails on a plane. **(b) Ship a generated changelog in the
  release**: CI writes the commits between tags into the zip, and the
  subagent reads a local file.

  **Rec: (b).** It removes the auth question rather than answering it,
  works offline, is a few lines of CI, gives the subagent better-shaped
  input than raw commits, and produces a changelog humans want anyway.
  The git path stays available wherever history is actually present —
  a checkout like this one — so (b) costs nothing there.

  Same decision also settles the no-prior-hash fallback: estimating the
  install date from asset mtimes is sound (for both an unzip and a clone,
  mtime really is install time), but turning that date into "the oldest
  plausible hash" needs history or a changelog — the same dependency.

  Answer "changelog", "network", or name a third shape.

  **Not blocking the whole idea** — `bin/ud-dw-githash`, the commit
  trailers and the frontmatter all proceed regardless, and I would start
  with the trailers since every commit written before they exist is one
  the future upgrade pass has to read blind.
  - **Note (human, via watch, 2026-07-26 18:54):** oh well it sees the old
    commit in DREAMWORK.md, and the new one from the ud-dw-githash command.
    also i'm making the repo public. not sure this answers your question,
    so adding it as a note. also in our own dreamwork.md we should note an
    exclusion because we're obviously going to see new commits all the
    time.
  - **Follow-up (loop, 2026-07-26 18:56):** Yes for the interval endpoints;
    public removes authentication from a network fallback. The remaining
    choice is where a zip/offline install gets the intervening objects. Rec:
    local Git history when present, packaged generated changelog for zip/
    offline use, and public-repo fetch only as explicit fallback. Leaving this
    open for that source choice. I will also add the requested self-repo
    exclusion: this development checkout must not treat ordinary new local
    commits as an installed-release upgrade on every tick.


- **P3 · 2026-07-25 — dreamhub URL space: one hub URL, or one per project?**
  → resolved (2026-07-25): decided by the loop and withdrawn as an ask — he never answered it and no
  longer needs to. Origin-per-project stands, on the measurement already recorded below. (Marker was
  inside a two-line bold title.)
  → resolved (2026-07-28 06:25): **decided by the loop, and withdrawn as an ask —
  he never answered it and no longer needs to.** Origin-per-project stands, on the
  measurement already in this entry: `routeOf()`/`isInternal()` compare
  `location.pathname` against literals inside a generated JS string and cannot be
  reached from outside, so a path prefix makes a deep link render the **wrong view,
  silently** — the worst failure on the menu. Withdrawn under his 05:35 rule that a
  decision with one clearly superior answer is not an ask; the test *"would I be
  surprised by any answer other than my rec"* is yes here, because the alternative
  is measurably worse rather than merely different. The reasoning lives in
  `.dreamwork/docs/plans/dreamhub-stage1.md`, which is the aux document his rule
  asks for. **He can still overturn it** — the single-URL bookmark is a preference
  only he holds — but it costs a `watch.py` change and it is not worth his
  attention unasked.
  (#96).** Your `daemon-mode.md` sketch was `/` lists projects and
  `/{project}/…` reverse-proxies to that project's watch. The stage-1
  plan ships **origin-per-project** instead — the hub lists and links
  out, each project keeps its own port and its own URLs.

  Why, measured rather than argued: the watch page is root-absolute in
  three places, and only two of them can be patched from outside. The
  fetches and `pushState` can be shimmed; `routeOf()`/`isInternal()`
  compare `location.pathname` against string literals inside a
  generated JS string and cannot be reached. So under a path prefix a
  deep link renders the **wrong view, silently** — the worst available
  failure. `ssh -L` also gives a local port per remote project, so
  origin-per-project survives all the way into the swarm stage, and the
  prefix work belongs to #124's server-core seam where those three
  sites are being touched anyway.

  **Not blocking** — the build proceeds on the rec. Answer only if you
  want the single-URL bookmark badly enough to serialise stage 1 behind
  a `watch.py` change. Full reasoning:
  `.dreamwork/docs/plans/dreamhub-stage1.md`.
  - **Follow-up (loop, 2026-07-25 17:24):** submissions attached to this
    entry at 14:34-14:35 have been REMOVED. They were never his: they are
    verbatim guard strings — `dev/capture/regroup.mjs:67` and
    `dev/capture/oneinput.mjs:139,153` — that reached the real
    `questions.md` because a guard ran against the live target instead of
    the fixture (the runner gap, fixed in 7be4a22). They were previously
    kept on the reasoning that they were his words; they are not. He asked
    at 17:23 whether three answers had been forgotten, and on the page
    they were indistinguishable from his.
    **This question is genuinely open and has never been answered.**

- **P1 · 2026-07-28 — implementation authority for the user-event journal:
  lanes A–D and F now, the cutover behind a second gate?**
  → answered (2026-07-28 05:43): **`rec` — all four.** So: **G1 granted** (lanes
  A–D and F may be implemented; **E, the HTTP cutover, and H, the mixed-version
  gate, stay behind a second gate** until A–D are proved), **Q2 yes** (amend law 2
  to keep a partial witness marked incomplete), **Q3 yes** (`200 → 202` is a
  non-event; the 15 pinned assertions move with it), **Q4 not built** (payload
  purge and the PostgreSQL half of fixtures 18/19 are out, and the fixture list
  says so rather than carrying permanent skips).
  · his note carried a durable preference that is now in DREAMWORK.md: the
  coordinator does all the planning and writes each subagent a **file** brief with
  measurable goals and acceptance criteria, reusable if a lane fails and readable
  by him; plus a one-off `xdg-open` of these briefs after dispatch.
  · lanes E and G both live inside the one 8,647-line `watch.py`, so they are one
  lane in practice whatever the graph says — an argument for #368 landing first,
  and it now sits behind the same second gate.
  lanes A–D and F now, the cutover behind a second gate?** Artifact:
  `.dreamwork/review/user-event-journal-implementation.html`. Plan:
  `.dreamwork/docs/plans/user-event-journal-implementation.md` (976 lines, `741b983`).
  The plan authorises no code and says so in its own second section — this entry is
  the gate.

  35 red-first increments in eight lanes. 18 of 20 design fixtures placed; the two
  that could not be placed are excluded *by your own approval clause*, not by a
  design gap.

  Rec **G1**: grant **lanes A–D and F** now — the digest, the journal, the
  domain-file store, the application adapters, and the CLI. Every one is new files
  and **zero change to any response**, so nothing he can see moves. Hold **lane E**
  (the HTTP cutover, where `200` becomes `202 + Location`) and **lane H** (the
  mixed-version gate) behind a second gate once A–D are proved.

  Three narrower calls, each with a rec:

  - **Q2 — one amendment to the design.** Amend §"Receive and idempotency" law 2 so
    the server keeps a **partial witness, marked incomplete**, for an interrupted
    body. **Rec: yes.** Today it witnesses interrupted bodies *badly*: `watch.py:8387`
    reads `min(nbytes, MAX_BODY)` and never compares the result to `nbytes`, so a
    short read is recorded as a complete line (that is #371, filed). Tightening
    receipts without this amendment would make a partial answer **less** recoverable
    than it is now for every non-browser client.
  - **Q3 — is `200 → 202` on the six write routes a non-event?** **Rec: yes**, and it
    is measured rather than assumed: every client check in the page is `res.ok`
    (9 sites), so the browser cannot tell the difference; 15 test assertions pin the
    literal `200` and move with it. That count was **13** by grep and **15** by an
    `ast` walk — grep missed four multi-line `assertEqual(self._post(...), 200)`
    statements — and the plan carries the script so the number is repeatable.
  - **Q4 — purge and PostgreSQL: not built, or built-but-not-run?** **Rec: not
    built.** Your approval excluded payload purge and PostgreSQL operation, so
    fixtures 18 and 19's Postgres half have nowhere to land. Saying "not built" keeps
    the fixture list honest instead of carrying two tests that are permanently
    skipped.

  One testability finding worth your eye, because it is the only place the plan
  cannot fully honour its own rule: *"journal fsync failure ⇒ no 202"* is not
  inducible through stdlib SQLite — no pluggable VFS, no failable pragma, and a
  patched `os.fsync` never reaches SQLite's own syscall. Increment 22 therefore
  proves the *contract* at a real seam (`chmod 0500` on the journal's parent before
  start) and records the `fsync`-specific case as a deferred gap with an `LD_PRELOAD`
  shim named. A mocked `fsync` test would be exactly what the design's own "kill at
  named seams rather than mocking away durability" sentence forbids.

  Scheduling note, which is a fact about the tree rather than the plan: lanes E and
  G both live inside the single 8,647-line `watch.py`, so they share one lane in
  practice no matter what the dependency graph says. That is the real constraint on
  parallelism here, and it is an argument for #368 (the modular split) landing before
  E does.

  Answer `Grant G1`, `Grant G1 with changes: …`, `Grant all lanes including E and H`,
  or `Hold #263`. Q2/Q3/Q4 can each be answered `rec` or overridden individually.
  - **Answer (via watch, 2026-07-28 05:43):** rec. note: I expect you
    main opus 5 claude orchestrator to do all the planning around this
    and to prepare precise instructions with measurable goals and
    acceptance criteria for your subagents. Idelaly write these to file
    so they are reusable in case of any issue and so you can show them
    to me (xdg-open after launching the subagents for this one)

- **P1 · 2026-07-28 — one word: may I run `install.py --apply`?**
  → answered (2026-07-28 05:38): **"apply"**, and it is done — `--apply` run at
  05:39, exit 0, `{"ok":true,"changed":true,"backup":".../settings.json.bak-20260728T053957"}`.
  · **verified independently of the tool's own report**, by diffing a snapshot I took
  before the write: non-hook keys byte-identical; your c2c `PostToolUse` group
  (matcher `^(?!mcp__).*`) preserved exactly; **no pre-existing group lost** across
  `PostToolUse`, `PreToolUse` or `SessionStart`; and exactly two groups added —
  `PostToolUse` matching `Write|Edit` running `posttooluse_ledger_lint.py`, and a new
  `PreCompact` running `precompact_focus.py`. Nothing else moved.
  · `hardlinked: null` in the output is the correct answer rather than a missing one:
  the field is `after if after > 1 else None`, and `~/.claude/settings.json` has
  `st_nlink` 1 — it is reached through a directory **symlink**, which is the
  correction #369 already carries.
  · rollback is one line: delete the `Load:` line in DREAMWORK.md to disable both
  hooks without touching config, or restore the timestamped backup above.
 You said `rec`
  to #361 at 02:47, which authorised the `Load:` line and a reviewed `--print`. I
  have done both and stopped there, because writing your Claude Code config is the
  separate act.

  **The condition I attached has dissolved, and for an embarrassing reason.** I told
  you `--apply` would break a hardlink between `~/.claude/settings.json` and
  `~/.claude-w/settings.json`. They are not hardlinked: same inode, yes, but
  `st_nlink` is 1 and `~/.claude` is a **symlink** to `~/.claude-w`. One file, two
  paths. A rename strands nothing. I measured the inode and inferred the rest.
  (#369 is fixed and kept anyway — a genuinely hardlinked config is a real hazard —
  and `--apply` now reads back what it wrote, re-stats the link count, and exits 2
  naming both counts instead of reporting a success it cannot see.)

  **What `--apply` will do**, dry-run against your real file, read-only, no
  conflicts: add one `PostToolUse` group matching `Write|Edit` running
  `posttooluse_ledger_lint.py`, and one new `PreCompact` group running
  `precompact_focus.py`. Your existing `PostToolUse` c2c inbox hook (matcher
  `^(?!mcp__).*`) is a separate object and is not touched. Everything else
  unchanged. Timestamped `.bak-<ts>` written first, and its path reported.

  **What it buys**: the ledger lint runs in the same turn as the write, before the
  commit, while the agent that mangled the file still holds the context. Two of my
  commits tonight went through a lint ERROR because the lint and the `git commit`
  were in one shell command and the error scrolled past above the commit's output.
  That is the window this closes.

  It is Claude Code-specific, so it protects this session and other Claude lanes,
  not pi or ccc agents. Deleting the DREAMWORK.md `Load:` line disables both hooks
  without touching any config.

  Answer `apply`, or `not yet`. No artifact — this is consent, not design.
  - **Answer (via watch, 2026-07-28 05:38):** apply

- **P1 · 2026-07-28 — #367, your postit flags: four decisions, and the geometry
  refuted the literal reading of your own metaphor**
  → answered (2026-07-28 05:35): **all four ruled, and two of them overrode the
  rec** — which is why the artifact asked rather than assumed. **M1 rec** (rail
  above 780px, strip below). **M2 is not 5-and-refuse**: *"soft limit at 7, hard
  limit at 15"* — so **two** thresholds, a warning at 7 and a refusal at 15, and my
  single hard 5 was both too tight and too blunt. **M3 rejected the premise**: not
  a 12-character refusal but *"2 lines, smaller text, maybe up to 6 words? probably
  need to measure. they don't have to have large text because they're already
  visible"* — the flag's job is to mark a position, so legibility at a glance is not
  what it is for, and a two-line tab at a smaller size holds far more than the one
  line I had costed. **M4 rec** (marks are not `nav` entries).
  · **and a durable preference, folded to DREAMWORK.md rather than left here**:
  *"instruct dreamwork agents to be more concise and keep to the most important
  topics. IGCs that only have one solution that is clearly superior don't need to be
  answered. If that belongs anywhere, let it be an aux document."* Read against this
  very entry: M1 and M4 were both `rec`-and-taken, so both were asks with one
  clearly superior answer and neither should have been put to him. M2 and M3 earned
  their place by being overridden.
  · #367 is unblocked to implement. First increment stays as stated — the
  source-mark contract in `file-formats.md` plus the "declares no marks &rarr;
  byte-identical output" check, red first — and the measurement M3 asks for
  (how many words fit two lines at a smaller size) comes before any CSS.
 Your 02:36 idea — *"pointer
  labels at the most important parts … like those little thin postits that lawyers
  use"*, plus next/prev, because reviews are *"sometimes quite long"*.

  Decision artifact:
  `.dreamwork/review/review-essential-marks.html`; design:
  `.dreamwork/docs/plans/review-essential-marks.md`. Design only — nothing built,
  no template touched, no artifact restamped.

  **They are quite long: the longest is 19.6 screens** (19,582px, 6,533 words),
  median 1,777. So the complaint is real, and the maximum is where flags pay.

  **I measured before designing, and it killed three designs including yours.**
  A list of the sections would be **22 entries** in the artifact that needs it most
  — your five-flags analogy rules that out, and the `nav` is already that axis.
  Tabs protruding past the page edge cannot work: the margin outside `.wrap` is
  **16px at every viewport from 1120px down**, so the physical reading of the
  metaphor is affordable on one monitor and nothing on a laptop. And a flag on each
  marked block's edge would scatter, because blocks in a section run from 614px to
  the full 1120px.

  **What survives**: a mark is a **flag at a height**, anchored to the reading
  column's right edge — which is fixed at **613.5px** and left-aligned, leaving
  **506px of wrap already empty** beside it. Above 780px that is the tab rail;
  below it the same marks are a compact strip under the top rail, because the slack
  is 54px there and a tab needs 96. Next/prev walks them in document order in both,
  so only the presentation changes.

  **The thing worth your eye**: #367's own entry guessed the hard case was mobile.
  The real cliff is **~780px** — above both existing breakpoints — so a design that
  answered only for 390px would have looked right in review and broken in a
  half-width window on your desktop, which is where you read these.

  Four decisions, all recommended in the artifact: **M1** rail above 780 / strip
  below · **M2** cap of five, and over it **refuses the build** rather than warning
  · **M3** ~12-character labels, refused rather than truncated — *this is the one I
  want your read on, not your ratification, because you are the person who reads the
  tabs* · **M4** marks are not also `nav` entries.

  `rec` takes all four. Approving authorises the source contract in
  `file-formats.md` plus the "declares no marks &rarr; byte-identical output" check,
  red first — not the template change, which restamps all 16 artifacts and is a
  separate increment.
  - **Answer (via watch, 2026-07-28 05:35):** 1. rec 2. soft limit at 7,
    hard limit at 15. 3. 2 lines, smaller text, maybe up to 6 words?
    probably need to measure. they don't have to have large text because
    they're already visible. 4. rec We can also instruct dreamwork
    agents to be more concise and keep to the most important topics.
    IGCs that only have one solution that is clearly superior don't need
    to be answered. If that belongs anywhere, let it be an aux document.

- **P1 · 2026-07-26 — #229/#270 topic chats v2: accept the revised
  proposal direction?**
  → answered (2026-07-28 02:56): **"rec, after cli and sqlite" — R1 accepted as the
  proposal direction only**, and the two words after the rec are the whole delivery
  plan: nothing about topic chats starts until #294's SQLite ledger and #346's
  schema plus read-only CLI surface exist
  · that ordering is not caution, it is your 23:24 note taken literally — if chat
  storage is only ever reached through the `dreamwork` CLI, the CLI is a
  *precondition* of the feature rather than a parallel effort, and building the UI
  first would mean building exactly the direct file access the rule forbids
  · #229 closes as decided. The implementation anchor is **#373**, carrying the
  accepted direction, the CLI-only seam (an `AGENTS.md` in the storage directory
  with `CLAUDE.md` symlinked to it, so an agent that wanders in meets the rule
  instead of having to have been told), and the gates approval did not lift: #263
  prove-applied reconciliation, the WorkerAdapter proof, #239, and consumption of
  #266/#269/#271
  · #236, #235 and #230 recorded themselves as "blocked on #229 approval"; they are
  now blocked on #373, which is a later date than the one they were waiting for, not
  an earlier one

  New reviewed artifact:
  `.dreamwork/review/threaded-topic-chats-v2.html`. It supersedes v1 for future
  design while preserving the old artifact as history.

  Rec **R1**: accept the revised direction only. It has one recovery spine
  (client attempt → durable #263 receipt → application → transcript), starts
  with the main dreamer, requires explicit proved WorkerAdapter promotion,
  shares cross-process leases/caps, makes attachments MVP, keeps indexes
  derived, and replaces the unreachable review composer with a viewport dock
  plus mobile Document/Discussion tabs.

  Architecture PASS. Vision and Geometry initially found clipped decision
  navigation, a detached mobile v2 marker and a 1.5s long-range smooth scroll;
  all were fixed and both rereviews PASS. Approval does **not** authorize
  implementation: #263 prove-applied reconciliation, WorkerAdapter proof, #239,
  and #266/#269/#271 integration gates remain.

  Answer `Accept R1 as proposal direction only`, `Accept R2 with amendments:
  …`, `Choose R3; rework … and show …`, or `Choose R4; pause topic chats`.
  - **Note (human, via watch, 2026-07-27 23:24):** we should use the cli
    only to interact with topic chats. Whatever directory they are in, we
    need an AGENTS.md (and CLAUDE.md symlinked to it) that specify to
    always use the dreamwork cli to interact with the topic chats.
  - **Answer (via watch, 2026-07-28 02:56):** rec, after cli and sqlite

- **P3 · 2026-07-25 — ud-dreamtask stage 6 (harvest): go, or leave it?**
  → answered (2026-07-28 02:53): **"rec go" — planning is authorised now.** The rec's own
  hedge was *"yes, but later"*, and that hedge was the loop's, about timing; his word is go.
  So #50 is unblocked for a PLAN, not for editing the core loop's init yet.
  · **the gate was never about value, it was about surface**: stage 6 is the one part that
  reaches back into ud-dreamwork, so it touches `initialization.md`, a migration, and probably
  `file-formats.md` and `lint.py` — new surface in the core loop rather than in the sibling.
  A plan can settle that shape without widening anything.
  · **and the argument for waiting has partly expired in his favour**: the rec said a week of
  using dreamtask would say more than a design conversation. What has accumulated since is a
  `.dreamwork/lessons.md` this repo prunes by hand — so the harvest question now has a
  concrete case to design against rather than a hypothetical one.
  · one correction carried forward from this entry's own history, because it is easy to lose:
  the submissions attached at 14:34-14:35 were **never his** — verbatim guard strings that
  reached the live `questions.md` through the runner gap fixed in `7be4a22`. They were removed
  on 2026-07-25 and this answer is the first real one the entry has had.

  Stages 1-5 shipped: the skill exists, is installed and indexed, walks
  its own procedure, and `newerrand.py` creates a dreamstate so an
  opening never hand-writes `questions.md`/`status.json` by hand.

  **Stage 6 is the only thing left and it is deliberately gated**,
  because it is the one part that reaches back into ud-dreamwork:
  dreamwork's init would read PAST dreamstates, so lessons an errand
  learned surface in the garden that spawned it. That means editing
  `initialization.md`, a migration, and probably `file-formats.md` and
  `lint.py` — new surface in the core loop, not in the sibling.

  Rec: **yes, but later.** The value is real (an errand's lessons
  currently die with its archive) and nothing else is blocked on it.
  But it widens the core loop's init, and today already added a linter
  step there. A week of using dreamtask will say more about what is
  worth harvesting than a design conversation will now.

  Answer "go" to plan it, or leave it and it stays parked.
  - **Follow-up (loop, 2026-07-25 17:24):** submissions attached to this
    entry at 14:34-14:35 have been REMOVED. They were never his: they are
    verbatim guard strings — `dev/capture/regroup.mjs:67` and
    `dev/capture/oneinput.mjs:139,153` — that reached the real
    `questions.md` because a guard ran against the live target instead of
    the fixture (the runner gap, fixed in 7be4a22). They were previously
    kept on the reasoning that they were his words; they are not. He asked
    at 17:23 whether three answers had been forgotten, and on the page
    they were indistinguishable from his.
    **This question is genuinely open and has never been answered.**
  - **Answer (via watch, 2026-07-28 02:53):** rec go



- **P2 · 2026-07-27 — #277 departure dreamfade: prototype one CSS-only
  pre-phase on the existing card ghost?**
  → answered (2026-07-28 02:51): **"okay yep rec" — the D1 prototype is authorised**, and
  you attached a delivery instruction: *"I'm going to set up an agent for you via c2c (load
  the skill after compaction) and you can direct it in a worktree to prototype it and get it
  to launch a live server for me. c2c alias: grok-heart-quint-sjax"*
  · that peer is **alive on the broker** (checked, along with five other grok aliases), and
  it is a fresh grant — DREAMWORK.md recorded that Grok held no coordinator grant after the
  earlier ones were cancelled, so this supersedes that for this one task
  · **what it is authorised to build**, unchanged from the rec: a 150-220ms CSS-only
  `.pregone` phase on the SINGLE existing absolute ghost — blur 0→~8px, opacity 1→~0.8, at
  most 2px upward drift — then the current fade/travel. The data/DOM commit and survivor FLIP
  stay immediate, so the corpse dreamfades while the live list is already correct. v1 covers
  question/answer rows, nested thread bodies and section folds only
  · **and what it must not touch**: route dissolve (double mist), survivor FLIP, commit
  special travel, composer confirmation, indicators, ambient background. Reduced motion skips
  the phase and the ghost. Total corpse lifetime stays ≤1.1s
  · the gap it closes is one line — `watch.py:666` is the whole departure today, a single
  `.qaghost.gone` class, so blur and travel begin together and there is no in-place phase
  · **the visual gate is the deliverable, not the diff**: pixel and geometry review must read
  as *"dissolve then leave"* and not *"mush then snap"*, and if it fails, it stops — no
  escalation to per-ghost SVG or WebGL without another ask. Approval covers the isolated
  prototype and its live server, not production integration or deployment

  Max directed Grok toward shader work;
  read-only review mapped the actual transition matrix. Route departures already
  have full SVG dissolve mist. Card/list/thread/section ghosts only blur while
  leaving, with no brief in-place liquify phase. Ambient/Jovian shaders are a
  separate layer and #279 failed that visual gate.

  Rec **D1**: prototype a 150–220ms CSS-only `.pregone` phase on the **single
  existing absolute ghost**: blur 0→~8px, opacity 1→~0.8, at most 2px upward drift,
  then the current `.gone` fade/travel. The data/DOM commit and survivor FLIP stay
  immediate—the corpse dreamfades while the live list is already correct. Apply
  v1 only to question/answer rows, nested thread bodies and section folds. Do not
  add it to route dissolve (double mist), survivor FLIP, commit special travel,
  composer confirmation, indicators, or ambient background. Reduced motion skips
  the phase/ghost. Total corpse lifetime remains ≤1.1s.

  Prototype gate: disposable question-card leave only; pixel/geometry review must
  read as “dissolve then leave,” not “mush then snap”; measure multi-card frame
  behavior; guard ordered intermediate blur+opacity, no transform overshoot,
  settled crisp live tree, no route double ghost, and RM no blur/travel. If visual
  review fails, stop—do not escalate to per-ghost SVG/WebGL without another ask.

  **D2** attaches the route SVG filter to every ghost (refuted: expensive and
  double-mist risk). **D3** uses WebGL element textures (refuted: new system and
  repeats #279's craft risk). Approval authorizes only the isolated D1 prototype
  and visual/performance review, not production integration/deployment. Answer
  `Approve D1 prototype`, `Approve D1 with changes: …`, or `Pause #277`.
  - **Note (human, via watch, 2026-07-28 01:39):** [Low priority to answer]
    Is this still relevant?
  - **Follow-up (loop, 2026-07-28 01:44):** Yes, and the gap is still one line.
    `watch.py:666` is the whole departure: `.qaghost.gone { opacity:0;
    filter:blur(6px); transform:translateY(-10px); }` — one class, so the blur and
    the travel begin together and the element is already moving by the time it
    starts dissolving. There is no `.pregone` in the tree and nothing has replaced
    it; #277 is open and unstarted, and none of tonight's motion work
    (#300's morph popover, the route dissolve) touched this path. So the proposal
    still describes the real code. What has changed is only queue position: it sits
    behind seven approved-and-unstarted `watch.py` items, so answering it costs you
    nothing today and I will not start it before those.
  - **Answer (via watch, 2026-07-28 02:51):** okay yep rec. I'm going to
    set up an agent for you via c2c (load the skill after compaction)
    and you can direct it in a worktree to prototype it and get it to
    launch a live server for me. c2c alias: grok-heart-quint-sjax


- **P1 · 2026-07-28 — #361: may I switch on the ledger-lint hook we built in
  #138/#156 and never turned on?**
  → answered (2026-07-28 02:47): **"sure, rec" — the Load line is in** (DREAMWORK.md,
  Plugins), which is the consent gate the plugin's own design requires: both hooks re-check
  it every invocation and skip silently without it, so deleting that line disables them
  without touching any config.
  · **`--apply` has NOT been run**, per your own rec that I show you `--print` first. The
  snippet is two entries: `PreCompact` -> `precompact_focus.py`, and `PostToolUse` matching
  `Write|Edit` -> `posttooluse_ledger_lint.py`. Your existing `PostToolUse` entry (the c2c
  inbox check, matcher `^(?!mcp__).*`) is a separate object and is not touched; `--apply`
  refuses to replace a differing entry without `--force`.
  · **And that pre-apply look found a real bug, filed as #369.** Your two config dirs are
  the SAME INODE — `~/.claude/settings.json` and `~/.claude-w/settings.json` are both
  `256518042` — and this session runs with `CLAUDE_CONFIG_DIR=~/.claude-w` while
  `install.py` defaults to `~/.claude`. It writes a `.tmp` and calls `replace()`, which is
  atomic and **breaks the hardlink**: the other name keeps the old inode. So `--apply` would
  print success, write its backup, be idempotent on re-run, and leave the session it was
  meant to protect with no hooks. Every visible signal would say it worked.
  · So I am holding at exactly where your grant ends. Say `apply` once #369 is fixed, or
  `apply anyway` if you would rather have it on the `~/.claude` name today and relink by
  hand.

  One line from you, then a reviewed install.
  No artifact — it is a consent question, not a design.

  **The evidence is two of my own mistakes tonight, four hours apart.** I wrote
  `tasks.md`, introduced a lint ERROR, and committed anyway — because the lint
  run and the `git commit` were in one shell command and the error scrolled past
  above the commit's own output. Once a next-id mismatch, once prose that quoted
  the origin marker literally so lint counted two markers on one entry. Both
  needed an amend, and both were caught only by the *next* lint run.

  **The fix already exists and is switched off.** #138/#156 shipped
  `plugins/ud-dreamwork-hooks/hooks/posttooluse_ledger_lint.py`, which lints
  `questions.md` and `tasks.md` **in the same turn as the write** — before any
  commit, while the agent that mangled the file still has the context. That is
  exactly the window both incidents fell through. It is measurably off: not
  referenced in `~/.claude/settings.json` or `~/.claude-w/settings.json`, and
  DREAMWORK.md has Load lines for `ud-dreamwork-worktrees` and
  `ud-dreamwork-github` but none for the hooks plugin.

  It is off because #138's entry put a scope gate on it — the plugin writes to
  your Claude Code config — and the plugin's own design refuses to act without a
  DREAMWORK.md Load line. So it cannot be self-granted, correctly.

  Rec: **add the Load line**; I then show you `install.py --print` before
  anything is applied (`--apply` is idempotent, takes a timestamped backup, and
  refuses to clobber). Note it is Claude Code-specific, so it protects this
  session and any other Claude lane, not pi or ccc agents.

  The weaker half of the fix needs no permission and I am doing it regardless:
  never put a lint run and a `git commit` in one command again.

  Answer `rec`, `rec but show me install.py --print first` (the same thing,
  said explicitly), or `Pause #361`.
  - **Answer (via watch, 2026-07-28 02:47):** sure, rec
  - **Follow-up (loop, 2026-07-28 03:16) — I told you something false above, and
    it is the sentence the whole hold was built on.** Your two config paths are
    NOT hardlinked. They do share one inode (`256518042`, which is the part I
    measured), but `st_nlink` is **1** and `~/.claude` is a **symlink** to
    `~/.claude-w`, made today at 00:00 — one settings.json reached two ways, not
    two links to one file. Under a directory symlink a rename strands nothing, so
    the silent failure I described could not have happened on your machine and
    `--apply` was safe against the default path the whole time. I observed the
    inode and *inferred* the relationship from it; the entry then read as measured
    for four hours.
    · #369 is fixed anyway (`5ecc326`) and worth keeping: a genuinely hardlinked
    config is a real hazard, and `--apply` now reads the file back, compares it to
    what it wrote, re-stats the link count and exits 2 naming both counts rather
    than reporting a success it cannot see. Correction recorded at `0d030fe`.
    · dry-run against the real file, read-only: no conflicts, one new
    `PostToolUse` `Write|Edit` group plus a new `PreCompact` group, your c2c inbox
    hook and everything else untouched.
    · so the condition I attached to your `apply` is gone. **One word — `apply` —
    and it goes on.** Re-asked as its own Open entry so it is not buried in an
    answered one.


- **P1 · 2026-07-28 — #264 the task-transition boundary: one append-only log, no
  outbox, and burndown becomes a query.**
  → answered (2026-07-28 02:45): **approved in full — T1 rec, T2 rec, T3 rec, T4 no.**
  *"mm yeah i like task history as an event log that gets processed. good point re git
  lagging. proper tooling will prevent that! T1: rec t2: rec t3: rec t4: no, we're good to
  go"* · so the boundary stands as designed: task history is its own append-only
  `task_event` log in #263's database, appended in the same transaction as the state CAS,
  and burndown plus the dashboard status section become **queries** over it.
  · **T3 mattered most and you took the rec**, so the canonical event byte form is defined on
  day one — the hash chain needs one anyway — which keeps a committed append-only text export
  a provable projection, and surviving a fresh clone a deployment choice rather than a schema
  change. Your *"good point re git lagging"* is the measured half: 331 commits touch the
  ledger, median gap 4.8 minutes, p90 20 minutes, max 13.3 hours.
  · **T2 rec retires three `status.json` fields** — `queue`, `current_task_ids` and the
  per-agent `task_ids` — because those three ARE the drift measured while designing this (123
  open against 115, and an empty current list beside three live agents). Everything else in
  that file is a live process describing itself and stays.
  · *"proper tooling will prevent that"* is the third time you have named the same thing
  tonight, so **#357** is P1 and its shape is settled by your own words *"tacked on"*: a
  footer every verb emits, not a verb you have to remember to run.
  · **Your answer arrived twice, byte-identical, again** — #274's fourth witness. This time
  `lint.check_unfolded_answers` reported it within one minute instead of an hour. One copy
  removed in the fold; nothing of your words lost.
  · Approval is the boundary as a design direction. It authorises no table, no migration, no
  CLI and no cutover — those wait on #263's plan, in flight now, and #294 behind it.

  Decision artifact:
  `.dreamwork/review/task-transition-boundary.html`; design:
  `.dreamwork/docs/plans/task-transition-boundary.md`, landed design-only at
  `914648c`. This answers the amendment you added at 14:11, and it needed your
  #263 approval first, which arrived at 01:27.

  **It is neither of the two options you named**, and the reason is one sentence.
  *"Never dual-write two fallible truths"* forbids storing one fact twice — it
  does not forbid storing two facts. "He asked for this at 14:11" and "the loop
  started #264 at 01:47" are different facts, neither derived from the other, and
  their entire relationship is a foreign key. Sharing #263's journal treats them
  as one fact by putting them in one table; an outbox treats them as one fact by
  making one a projection of the other's queue.

  **The shape.** A task transition is one row appended to its own append-only
  `task_event` log, in the same SQLite file as #263's journal, in the same
  transaction as the compare-and-swap that moves `task_state`. Burndown and the
  dashboard status section become **queries** over that log, so neither can be
  stale. `task_state` is the only materialised row in the whole design, and only
  because a claim needs something to CAS against. The rule that keeps it that
  small: *a materialised row exists only where a **writer** must CAS against it;
  everything a **reader** wants is a query.* One consequence is worth your
  attention — `blocked` becomes derived from the dependency graph, so landing a
  blocker writes no unblock event at all and blocked can never drift.

  **Why the journal cannot simply absorb it**, checked rather than argued:
  `Transition.receipt_id` is mandatory in #263's own notation (nine sibling
  fields carry `?`, that one does not), and its states are the *receipt's*
  processing lifecycle. Most task transitions have no receipt at all — the loop
  starts a task on its own tick, a task is unblocked by another landing. And
  separately: **zero task state is mutated at HTTP time today.** Your `do now:`
  writes one events-log line and nothing else; it becomes a task only when an LLM
  reads that log on a later tick, one line sometimes filing a task, marking
  another blocked and re-prioritising a third. No transaction could hold both the
  `202` and that judgement.

  **The measurement that made this urgent rather than theoretical.** Three
  numbers describing queue depth on one page already disagreed: the ledger read
  123 open while `status.json` said 115, and `current_task_ids` was empty while
  three tasks were in flight. I hand-fixed both; neither had any check behind it,
  which is why they drifted. That is exactly the two-halves-of-one-fact failure
  #306 predicted.

  Four questions, each answerable in a word:

  - **T1 · The boundary.** Take the shape above? *Rec: yes* — the only one of the
    three where each fact has exactly one home, and the smallest.
  - **T2 · `status.json` loses its task-derived fields** (`queue`,
    `current_task_ids`, per-agent `task_ids`) and the dashboard queries the store?
    *Rec: yes* — those three fields **are** the drift measured above. Everything
    else in that file is a live process describing itself, which is what it is for,
    and stays.
  - **T3 · Must the burndown survive a fresh clone?** Today it does, because git
    history *is* the source and the ledger is committed; a SQLite store would be
    gitignored and machine-local. *Rec: yes, and it costs nothing now* — the hash
    chain needs a canonical byte form anyway, so a committed append-only text
    export becomes a provable projection and a deployment choice later rather than
    a schema change. **This is the one answer that could still move the shape.**
  - **T4 · Any burndown or status consumer outside the dashboard** this would
    break? *Rec: only you know* — #334 is live on `burndown.mjs` and #281 on
    `/tasks`; both were reasoned about, neither touched.

  Approval would authorise the boundary as a design direction only. It authorises
  no table, no migration, no CLI and no cutover — those still wait on #263's
  implementation plan, and #294 behind it.

  Answer `rec`, `rec except T<n>: …`, or `Pause #264`.
  - **Answer (via watch, 2026-07-28 02:45):** mm yeah i like task
    history as an event log that gets processed. good point re git
    lagging. proper tooling will prevent that! T1: rec t2: rec t3: rec
    t4: no, we're good to go


- **P1 · 2026-07-28 — #346 task-store schema: approve the entity shape and
  four decisions (S1-S4)?**
  → answered (2026-07-28 01:23): **S1 split, S2 rec, S4 inverted by your own
  pushback — and three of the four recs turned over.** You said *"we can keep them
  split. For tasks, we should have n:n relationships for related tasks (like 250/251 i
  guess, not sure exactly what they are), and one way dependencies too … We should
  design the db with the kind of joins we'll do in mind so that we can be performant
  always."* That was more than a yes: the combined entries were an IMPLICIT relation
  written as a slash in a title, and you asked for it to become explicit — symmetric
  n:n for "same work", directed for "cannot start until".
  · **What landed on it.** The three combined entries are six (`9fec0bf`), and history
  wrote them: every original survives in git with its own title, band, type and origin,
  so nothing was reconstructed. All three pairs are the symmetric relation and none is a
  dependency, for one uniform reason — each was co-delivered, never sequenced. Your
  uncertainty about 250/251 is answered: #251 is the proof that #250's node really goes.
  The prose form of the relation is contracted in `file-formats.md` and checked by
  `lint.py` (`638b32a`), which ERRORs on a one-sided pair — because SQLite stores the
  pair once and cannot disagree with itself, while prose has to duplicate it.
  · **S2, with your caveat honoured.** Three of the four compound bands still say
  something one band cannot, so they stay unedited; the fourth was never ambiguity at
  all — it was #250's P1 and #251's P2 concatenated. And the schema still closes: the
  uncertainty is one bit beside a strict band, not a compound value.
  · **S4: your 01:25 pushback was right and it inverted the rec.** You asked *"if we
  have an enum type thing, is it faster/better/more efficient? … let's take the
  principled approach … avoid footguns"*. Measured against real SQLite rather than
  reasoned: there is **no performance difference**, SQLite has **no ENUM type at all**
  (any type name is accepted and enforces nothing), and both real options store TEXT.
  So it is validation versus evolvability, one footgun each — a CHECK constraint cannot
  be altered or dropped without rebuilding the table, and a lookup table's foreign keys
  are **off by default per connection**. Resolved to the lookup table plus REFERENCES,
  with the FK pragma asserted rather than assumed.
  · **S3 was withdrawn before you had to rule on it**, because the finding it rested on
  was wrong: a scan had missed line-wrapped markers. Real numbers are 50 unmarked
  entries, every one below id 216, so absence is the contract's forward-only cutoff and
  is derivable — nothing to preserve.
  · Your two other notes in the same breath became **#352** (standardise the duplicated
  parsing first — you called it the prerequisite and it is) and **#357** (a CLI warning
  layer plus the waiting-counts). The CLI-as-small-binary steer is successor work, not
  this ask.
  · **Your answer arrived in this file TWICE, byte-identical**, which is a live instance
  of #274 and is recorded there as evidence. One copy was removed in the fold; nothing
  of your words was lost.
  · Approval covered the entity shape and read verbs only. No table, migration, CLI or
  cutover was authorised, and none was built.

  Decision artifact:
  `.dreamwork/review/task-store-schema.html`; full design:
  `.dreamwork/docs/plans/task-store-schema.md`. You said at 23:33 that the sqlite
  db and cli are becoming a blocker and invited a question — this is it, plus the
  half of #294 that turns out not to need your #263 answer at all.

  **First, the gate is not what #294 said it was.** That entry claimed starting
  would mean designing against an *unsettled* event model. Read against the
  document, `user-event-journal.md:4` says *"human approval required; no
  implementation authority"* and its approval gate authorises *"a separate
  red-first implementation plan"*. So #263's model is designed, reviewed and PASS
  — it is **unratified**, which only you can change. What #264 gates is one
  question: does a task transition share #263's journal or use a task-state
  outbox? That is about how a **transition** becomes durable, and the columns
  describing a task **at rest** are identical either way. So the entity schema and
  its read surface are separable, and #346 is that half.

  **Five measurements against your live ledger, each breaking a schema that looks
  obviously right.** All five came from `watch.ledger_entries`/`parse_ledger`, not
  a fresh regex — a fresh regex was tried first and reported 10 open entries
  instead of 111, because `text.index('## Open')` matched a prose mention of the
  heading in the file's own preamble. (1) An entry is not a task id: `#138/#156`,
  `#250/#251`, `#292/#293` are one body under two permanent ids. (2) The count
  that would catch that agrees **by accident** today — open entries 111, open ids
  111, because all three combined entries happen to be landed. (3) Priority is not
  a closed set: `P0/P1`x3, `P1/P2`x1, and 6 entries with no band. (4) Origin has
  four states, because 60 entries have no marker at all and 8 say `unknown`
  explicitly, and your own contract makes those different facts. (5) The
  dot-separated fields are not positional, so `type` cannot be parsed by index —
  reading "the field after the band" yields 65 values including
  `landed 2026-07-27`.

  **It also settles the invariant #294 told us to verify rather than assume, and
  the answer is that it is already false.** `ledger_entries` has two
  implementations (lint's and watch's — same logic, different source), three
  callers (`lint.py`, `watch.py`, `task_origins.py`), pinned by one behavioural
  fixture at `test_watch.py:863`. Re-pointing `watch.py` alone at cutover would
  leave the other two parsing a file that cutover renames to
  `tasks.md.deprecated`.

  Rec **S1 keep** combined entries via an entry/task split (**refuted: split the
  three and forbid new ones** — simpler forever, but it edits three of your
  existing entries and combining was deliberate). Rec **S2 compound bands stay
  legal** (**refuted: resolve each to one band when touched** — `P0/P1` says
  something one band cannot, and a derived rank sorts it correctly without editing
  your words). Rec **S3 leave the 60 unmarked origins NULL** (**refuted: backfill
  to `unknown`** — that asserts an audit that never happened, and destroys exactly
  the distinction your #289 `unlinked`-vs-`pending` rule protects). Rec **S4 keep
  `type` free text with NULL for unreadable** (**refuted: freeze the ~10 real
  values** — closing the set requires classifying all 237 entries correctly, and
  finding 5 says that cannot be done).

  Approval accepts the entity shape, the read-only verbs, and whichever recs you
  do not overrule. It authorises **no** table, migration, CLI or cutover — those
  wait on #263 E1 like the rest of #294. Answer `rec`, `rec except S<n>: ...`, or
  `Pause #346`.
  - **Note (human, via watch, 2026-07-28 01:05):** with the cli btw, we
    should consider writing it in something other than python. We ideally
    want a small (fast to load) portable binary + quick to recompile. It
    should also support extensions kind of like how git does, eg
    `git-thingy` can be run `git thingy`. that way we can have python
    modules (or go or rust or ocaml) also before we work on this proper we
    should standardize the current python parsing so we fix the duplicate
    code issues and such now in case it matters as we migrate and things.
  - **Follow-up (loop, 2026-07-28 01:08):** all three folded. (c) is filed as
    **#352** and treated as the prerequisite you called it — the duplication is
    already measured, so it is not a research task: `ledger_entries` has two
    implementations (`lint.py` and `watch.py:6599`, whose docstring claims it is
    lint's *"VERBATIM"* while the source differs), three callers (`lint.py`,
    `watch.py`, `task_origins.py`), and one behavioural fixture pinning them
    (`test_watch.py:863`, a single hostile input). Rec is one module all three
    import, so the pin stops needing to exist. (a) and (b): the design doc's CLI
    section now says the language is undecided rather than quietly Python, and
    records that git-style `dreamwork-thingy` dispatch is what makes a compiled
    core affordable — an extension in any language becomes a sibling executable
    instead of a plugin API to design. The read verbs and the entity they read are
    language-independent and stand. **Still open for you: S1–S4**, which this note
    does not answer.
  - **Note (human, via watch, 2026-07-28 01:13):** oh one thought is that
    we can make the shape as restrictive as we want before migrating
    because we won't need the python / plaintext versions for much longer.
    not sure if that helps us.
  - **Follow-up (loop, 2026-07-28 01:20):** it helps a lot more than "not sure" —
    it **inverts three of the four recs**, and the artifact and design doc are
    rebuilt to say so. Every refutation I wrote for S1, S2 and S4 was the same
    sentence in different clothes: *"that edits three of your existing entries"*.
    If the plaintext is on its way out, that is a one-time cost set against
    looseness the schema carries forever and every consumer handles forever. So the
    plan is now **normalise the Markdown first, then let the schema be strict**, and
    it is bounded: **3** combined entries to split, **4** compound bands to resolve,
    **6** entries with no band, and the tail of the 66 distinct values sitting where
    `type` should be. Filed as **#353**, and it needs no #263 answer — so with #352
    it is the second thing that turns "sqlite is a blocker" into movement.
    **S3 is withdrawn, and not because of your note: finding 4 was WRONG.** I
    reported 60 unmarked origins against 8 `unknown` and read the split as
    audited-vs-untouched. It is **50 and 12**, every unmarked entry's id is below
    216, so absence is just your contract's forward-only cutoff and is derivable
    from the id — there was never a distinction to preserve. The scan tested
    `'origin: **' in body`, which misses a marker wrapped as `origin:\n  **loop**`;
    `lint.py` contradicted it and lint was right. I re-measured the other four
    wrap-tolerantly and they all stand. **The one cost worth your attention**:
    normalising means bulk edits to the loop's own memory, and a fold script damaged
    `questions.md` earlier tonight — so #353 carries its own guards and does not
    start without your ruling, because the entries are your words.
  - **Answer (via watch, 2026-07-28 01:23):** S1: we can keep them
    split. For tasks, we should have n:n relationships for related tasks
    (like 250/251 i guess, not sure exactly what they are), and one way
    dependencies too. Anyway we should capture the shape of work that
    makes sense, and if the split makes sense we should keep it. We
    should design the db with the kind of joins we'll do in mind so that
    we can be performant always. S2: rec S4: probs freetext or varchar,
    with null. with these kinds of things we can have an automated
    warning layer in cli calls that raises issues where data is
    incomplete or whatever. Also things like unchecked message count,
    new task count, new question count, unanswered question count,
    unfolded-in answer count, etc.
  - **Note (human, via watch, 2026-07-28 01:25):** oh now i'm not so sure
    about the free text -- what is the real benefit? if we have an enum
    type thing, is it faster/better/more efficient/etc? if not, then
    varchar or whatever it is that is just as fast but not as restrictive.
    enum has some advantages like easier validation. hmm. let's take the
    principled approach here that will give us the best result long term
    and avoid footguns
  - **Follow-up (loop, 2026-07-28 01:34):** measured against real SQLite rather
    than reasoned about, because the answer turned out to hinge on a footgun.
    **There is no performance benefit either way** — and "enum" is not a thing
    SQLite has: it accepts any type NAME and enforces nothing (`CREATE TABLE t (x
    ENUM_WHATEVER)` is accepted, stores the name verbatim, and takes any value).
    The two real options both store `TEXT` and read identically, so the choice is
    entirely **validation versus evolvability**, and each has one footgun:
    · **`TEXT` + `CHECK (x IN (…))`** genuinely enforces and **cannot be switched
    off by a connection setting** — I tried, it holds. Its footgun is that a CHECK
    cannot be altered or dropped: changing the allowed set means recreating the
    table.
    · **A lookup table + `REFERENCES`** enforces too, and adding a value is one
    `INSERT` with no rebuild. Its footgun is worse and it is the one that caught me
    while checking: **SQLite foreign keys are OFF BY DEFAULT, per connection**
    (`PRAGMA foreign_keys` is `0`). My first test "showed" the FK accepting garbage
    — because the pragma had not taken. Any connection that forgets it silently
    validates nothing.
    So the principled split, which is about whether the set is closed **by
    definition** or merely small today: **`CHECK` for closed-by-definition sets** —
    `state` (open|landed), `origin` (human|loop|unknown), `decision`
    (pending|accepted|rejected); those change only if the domain changes, and
    unbypassable is exactly what you want. **Lookup table + FK for a vocabulary
    that grows** — `type` is that, and your own automated-warning idea wants a place
    to hang per-type metadata anyway. The pragma then has to be set in ONE place
    (the adapter's connection setup) with a test asserting it, which is a single
    line and turns the footgun into a checked invariant.
    **And it settles the Postgres half**, which matters because #263's now-approved
    contract ships SQLite behind a PostgreSQL-portable adapter: Postgres native
    `ENUM` can add values but not remove them and bakes in an ordering, whereas a
    lookup table behaves **identically on both** backends. So the lookup table is
    the portable answer as well as the evolvable one.
    Rec: **`type` becomes a lookup table with an FK; the closed-by-definition
    columns get CHECK; nothing gets a bare unvalidated varchar.** That is stricter
    than your "freetext or varchar with null" and I think it is what you were
    reaching for with *"easier validation … avoid footguns"* — but say so if you
    want `type` left unvalidated, because that is the one place we would differ.


- **P0/P1 · 2026-07-26 — #288 protected-service boundary: contain
  subagent tools or isolate the dashboard identity?**
  → answered (2026-07-28 01:26): **"rec" — P1 authorised.** A written design and a
  bounded falsification prototype for explicit subagent tool routing through a real
  sandbox, with supervised restart plus positive same-PID/health invariants as
  defence-in-depth. Design and prototype only: it does not authorise deployment, and
  #288/#290 still grant no kill or sandbox authority from a run-mode alone.
  · He went further in the same breath, and that part is **#358**, not this entry: a
  head/body split where the head makes the LLM API calls and the body runs tools over a
  socket in a container, so the body cannot reach the API key. It is the general form of
  this question — the boundary between deciding and doing rather than around the tools —
  and it carries his own caveat that a harness owning both halves has no seam to cut.

  Decision artifact:
  `.dreamwork/review/protected-service-boundary-288.html`; analysis:
  `.dreamwork/docs/research/protected-service-boundary-288.md`.

  The #221 verifier explicitly ran `kill 1884627` against the committed live
  dashboard so its invented “no live 35110” assertion would pass. This was not
  a worktree escape: Pi and its subagents run with local-user authority, and
  both processes were UID 1000. Prompts, worktrees, listener snapshots and
  supervision can deter, detect and recover; they cannot prevent a same-UID
  signal. Pi's own security guidance requires an OS/container/VM boundary for
  real isolation. A coordinator-only Gondolin extension is insufficiently
  proven because `pi-subagents` creates fresh child sessions with ordinary
  built-in tools.

  Rec **P1**: authorize a written design and bounded falsification prototype for
  explicit subagent tool routing through a real sandbox, with supervised
  restart plus positive same-PID/health invariants as defense-in-depth. This
  addresses the source of authority and protects more than one service. **P2**
  instead isolates only the dashboard under a distinct OS identity with a
  tightly bounded deployment handoff. **P3** accepts detection/recovery only
  and explicitly drops the prevention claim.

  Approval authorizes design/prototype planning only. It does **not** authorize
  QEMU/container installation, Pi extension changes, system users,
  sudoers/polkit rules, systemd units, deployment changes, process signalling,
  or migration of the live dashboard.

  Answer `Choose P1 for containment design only`, `Choose P2 for service-identity
  design only`, `Choose P3; accept recovery without prevention`, or `Choose P4;
  pause #288`.
  - **Note (human, via watch, 2026-07-28 01:26):** rec, though also I kind
    of want to experiment with a head and a body part for running this
    stuff, like the head processes the LLM API calls and the like, but then
    sends tool calls over a socket to the body which is running in a docker
    container or a different box or something like that. The point is that
    it cannot kill the head or exfiltrate the API key, it can only kill
    itself (or escape I suppose). Anyway maybe that kind of architecture
    can help, but it presents a problem with like claude code and the like.
    hmmm.



- **P0/P1 · 2026-07-26 — #260/#262/#263/#269/#274: accept the
  reviewed durable user-event contract for implementation planning?**
  → answered (2026-07-28 01:27): **"rec" — the contract is ACCEPTED.** That
  authorises a separate red-first implementation plan and NOTHING more: not
  implementation, not migration, not deployment, not PostgreSQL operation, not
  topic chats, not payload purge — the approval gate's own words. #264 and #294
  are unblocked at the design level; #263's next increment is that plan.

  Design:
  `.dreamwork/docs/plans/user-event-journal.md`; narrow crash proof:
  `.dreamwork/docs/research/application-adapter-reconciliation-263.md`.

  Rec **E1**: accept the contract and authorize a separate red-first
  implementation plan only. One SQLite journal (behind a PostgreSQL-portable
  adapter) makes journal commit the sole `202` reception authority; browser
  UUID+digest attempts make retries idempotent; mutable IndexedDB drafts remain
  distinct from immutable receipts; leased/CAS application uses ternary
  `Applied | NotApplied | Unknown` proof; a mandatory `DomainFileStore`, embedded
  generation/digest lineage, and a quiesced cutover prevent legacy/manual writes
  from manufacturing duplicates; hash-chained cursors replace timestamp guesses;
  bounded CLI projections and explicitly scoped purge keep recovery inspectable
  without overclaiming erasure.

  Fresh-eyes architecture review initially found three Critical and four
  Important gaps (validation/status lifecycle, all-writer Markdown atomicity,
  undefined cursor integrity, HTTP/PG/purge/cutover detail). They were fixed. A
  second review found external-editor lineage ambiguity; fixed. A final
  provisional-successor rereview **PASSed**. Approval does **not** authorize
  code, migration, deployment, PostgreSQL operation, topic chats, or payload
  purge; it authorizes writing the implementation plan and its red fixtures.

  Answer `Accept E1 for implementation planning only`, `Accept E2 with
  amendments: …`, `Choose E3; revise … and rereview`, or `Choose E4; pause the
  event journal`.

  - **Follow-up (loop, 2026-07-27 23:36): asked again in plain terms, because this
    is the one decision standing in front of the sqlite work you just asked for.**
    You typed at 23:33: *"I think we need to start working on the sqlite db and
    cli next. it feels like it's becoming a blocker. ask a question of me if you
    would like to discuss."* You are right that it is a blocker — I measured the
    chain, and it is this question. `#294` (sqlite + CLI) waits on `#264`'s
    concurrency design, which waits on `#263`, which is **finished and reviewed
    and waits only on your answer here**. Nothing else is in the way. So this is
    the discussion, and everything above is the version of it written in the
    loop's own vocabulary — my fault, and the same mistake that left one of seven
    questions unanswered on 21:47. Here it is again as what you would see and do.

    **What you would be approving.** Today, when you type into the dashboard, the
    only record is one best-effort line in a log file that a monitor happens to be
    tailing. If that monitor is not armed — a restarted session, a compacted one,
    a server started later — your `do now:` is gone, and no surface anywhere says
    so. The design changes five things:

    1. Your words are written to disk and flushed **before** the page tells you it
       sent. Power cut a millisecond later, they are still there.
    2. The agent **reads** them from that record instead of being pushed them, and
       remembers how far it has read, so a restart or a compaction cannot skip
       one.
    3. If the same thing arrives twice — you double-click, the browser retries —
       it is applied once, because the page stamps each attempt with an id.
    4. One command shows you the last N things you sent and, for each, whether it
       was processed, failed, or the outcome is genuinely unknown. That third
       state is deliberate: the honest answer when a crash lands mid-apply is "I
       cannot tell", and I would rather show it than guess.
    5. Text you typed is removed only by a script you run on purpose, never by an
       agent editing a file, and a removal leaves a marker saying something was
       there.

    **Why it is worth answering now rather than later.** Your own idea five
    minutes earlier — batched vs instant delivery, and *"this should be part of
    the agent's loop \*always\*"* — needs exactly the thing item 2 describes: a
    record of how far the agent has read. I filed that as `#342` and then measured
    that no such record exists anywhere, so batched delivery is not merely
    unbuilt, it is currently impossible. Your two steers are the same piece of
    work approached from opposite ends.

    **What approving does NOT do.** No code, no database, no migration, no
    deployment, no topic chats, no deleting anything. It authorises writing the
    implementation plan and its deliberately-failing tests, which then comes back
    to you.

    So, in plain words: **`rec` = write the plan.** Or tell me which of the five
    is wrong and I will fix that first. If you would rather I start on `#294`'s
    sqlite schema in parallel without waiting, say so — it is possible, and the
    cost is that the schema may need reshaping once this settles, which is the
    "one migration, not two" trap you have warned me about twice tonight.
  - **Answer (via watch, 2026-07-28 01:27):** rec



- **P2 · 2026-07-27 — #295 shader dithering: replace the temporal white-noise
  LSB dither with static screen-space IGN?**

  → answered (2026-07-27 23:45): **Accept D1, amended — keep all three and let
  him toggle.** His words: *"hmm yeah we can try that. Keep both so that we can
  toggle. perhaps also add bayer too. We may want to consider creating a settings
  page where we can have a button group for these 3 options under a gfx settings
  section."* So static screen-space IGN at amplitude 1/255 in the final composite is
  accepted as the **default**, and the two options the review had refuted are
  reinstated as selectable rather than deleted: temporal white noise (today's
  behaviour, refuted for shimmer) and Bayer (which D1 had not proposed at all). The
  refutations stand as reasons IGN is the default; they were never reasons he cannot
  choose otherwise.

  **This is the third time today he has turned a chosen default into a control** —
  #281's filters at 21:47, #342's delivery mode at 23:28, and this — which is why
  *"the recommendation is the default, not the setting"* is in DREAMWORK.md and why
  the loop should now stop needing to be told. Two consequences folded onto the
  ledger rather than left here. The three modes must share **one** dither seam with
  the mode as a parameter, not three code paths, since a debug-only difference
  between them is a difference he cannot see and would not report. And the gfx
  settings section belongs to **#228**, the existing unify-dashboard-settings task,
  not to a second settings surface built beside it — he asked at 12:49 that settings
  persist and stay identical across tabs and browsers, and a gfx panel with its own
  storage is exactly the second truth that breaks.

  Authorises a red-first implementation in an isolated worktree plus the visual
  gate; not deployment. The capability record becomes the selected mode rather than
  the fixed `dither: "lsb-ign-v1"` string, since a fixed string cannot describe a
  toggle.

  Grok's read-only map found the
  composite pass **already dithers** — `col += (hash(gl_FragCoord.xy+t)-0.5)/255`
  — but the time seed makes it shimmer/grainy while ±½ LSB white noise is too
  weak and wrong-shaped to fully break 8-bit banding on the dark soft ramps
  (vignette corners, glow shoulders, hue-tinted near-black plates).

  Rec **D1**: static interleaved gradient noise, amplitude 1/255, screen-space
  `gl_FragCoord`, luminance-shared (same scalar added to RGB), applied in the
  final composite only, after hue/vignette, skipped on debug layers
  (`mode != 0`). No `t` anywhere in the seed: freeze-frame dual-draw must be
  pixel-identical; normal motion advects the field under a fixed pattern.
  Bayer 8×8 is the documented fallback if IGN looks wrong on SwiftShader;
  blue-noise texture is deferred to a v2 only if visual review fails D1.

  Guard shape (RED-capable): temporal stability (sabotage reintroducing `+t`
  fails), crop-zoom banding metric on a known soft-ramp ROI with an amp=0
  control proving the metric is non-vacuous, DPR sweep (desktop/mobile,
  scale 1/2), text-contrast sample under the 72ch column, no new passes/FBOs
  (≤~5 ALU, within the #278 budget), and the standing detailed
  visual-review-and-fix loop (vision + geometry) before merge. Not coupled to
  #277 ghosts; no FBO/WORLD_SCALE changes; #280 registry later records
  `dither: "lsb-ign-v1"` as a capability.

  **D2** keeps temporal white noise (refuted: shimmer). **D3** goes straight to
  blue-noise textures (refuted for v1: asset + sampling cost, #279 overreach
  risk). Approval authorizes red-first implementation in an isolated worktree
  plus the visual gate — not deployment. Answer `Accept D1`, `Accept D1 with
  amendments: …`, `Bayer instead`, or `Pause #295`.
  - **Answer (via watch, 2026-07-27 23:45):** hmm yeah we can try that.
    Keep both so that we can toggle. perhaps also add bayer too. We may
    want to consider creating a settings page where we can have a button
    group for these 3 options under a gfx settings section.

- **P2 · 2026-07-27 — #284 file heading: accept the two-line basename/path
  lockup?**

  → answered (2026-07-27 23:46): **Approve H1 — `rec H1`, the two-line
  basename/path lockup.** The basename becomes a bright semantic heading on its own
  primary line; the exact parent path sits beneath it as subdued, selectable
  metadata with a real keyboard- and focus-visible copy button that copies the full
  path, associated with the heading for screen readers. Copy success and failure use
  the page's existing polite-confirmation idiom; reduced motion snaps the visuals but
  keeps the message's timing and function. Long paths wrap anywhere inside the column
  and are **never** ellipsised or reordered — a path that lies about its own segments
  is worse than one that takes two lines. The existing keyed route transition is
  reused rather than animating path text on its own, per `transitions.md`.

  H2 (clickable breadcrumb segments) stays refuted until real directory routes exist,
  so it is a follow-up of `#243`/`#244` rather than of this. H3 stays refuted because
  long paths steal the primary line and destabilise the 520px geometry.

  This approval is broader than the others tonight — it authorises implementation,
  review **and deploy** for #284. Red-first evidence must prove luminance hierarchy,
  the exact clipboard bytes, the semantic heading/description/button labels, 520px
  no-overflow geometry, and both normal route travel and reduced-motion settling. The
  practical constraint is ownership, not authority: this is `watch.py`, held by the
  #326 agent until that merges.

  Exceptional-quality read-only design review compared three layouts.

  Rec **H1**: on `/file`, make the basename a bright semantic heading on its own
  primary line; place the exact parent path beneath it as subdued, selectable
  metadata with a real keyboard/focus-visible copy button that copies the full
  path. Associate the path with the heading for screen readers. Copy success or
  failure uses the existing atmospheric polite-confirmation idiom; reduced motion
  snaps visuals but keeps message timing/function. Long paths wrap anywhere
  inside the column; never ellipsise or reorder segments. Reuse the existing
  keyed route transition rather than animating path text independently.

  **H2** makes parent segments clickable breadcrumbs (refuted until real
  directory routes exist). **H3** keeps parent path inline after the basename
  (refuted: long paths steal the primary line and destabilise 520px geometry).

  Red-first evidence will prove luminance hierarchy, exact clipboard bytes,
  semantic heading/description/button labels, 520px no-overflow geometry, plus
  normal intermediate route travel and reduced-motion settling. Approval
  authorizes an isolated implementation/review/deploy for #284. Answer `Approve
  H1`, `Approve H1 with changes: …`, `Choose H2`, or `Pause #284`.
  - **Answer (via watch, 2026-07-27 23:46):** rec H1

- **P1 · 2026-07-27 — #254: the design you just approved will not change the card
  you complained about. Which way do you want it?**

  → answered (2026-07-27 23:38): **R1 — give the loop a resolution tag.** His
  `rec` took the option that makes N1 work on his card unchanged, and it closes the
  two alternatives with reasons worth keeping. **R2** (promote a loop reply to root
  when he has not answered) is refused because it inverts on the very common shape
  where the loop asks *him* a clarifying question and he answers it — the loop's
  question would become the root and his answer would hang beneath it, reading
  backwards; that is the same objection the spec's own D1 makes, so R2 would have
  contradicted a decision inside the document he approved. **R3** (ship N1, accept
  the card stays flat) he refused, which retires the honest-but-unsatisfying
  fallback rather than leaving it for someone to reach for later under time
  pressure. Folded into `.dreamwork/docs/plans/note-reply-threading-254.md` §8,
  where the resolution tag has moved from *"follow-up this design implies"* to part
  of the design. What R1 obliges, so the implementation cannot drift: a **new** tag
  distinct from `Answer (via watch, …)`, which is *his* and stays his — attribution
  is what #109 made a correctness matter — naming a loop **resolution** rather than
  any loop reply, so a non-resolution loop contribution keeps `Follow-up (loop, …)`
  and stays a branch member. **Implementation is not authorised by this**: his 23:03
  grant was the written design only and choosing among design options did not widen
  it, so `NOTE_TAGS` + `file-formats.md` + tests remain one increment awaiting one
  word. And they must land together — documenting a tag the renderer does not
  recognise would write the #340/#343 defect into the contract itself.

  Artifact:
  `.dreamwork/review/note-reply-threading-254.html`; spec:
  `.dreamwork/docs/plans/note-reply-threading-254.md`.

  You approved N1 at 23:03 and it is written up as approved. But the agent that wrote
  it checked its own design against your actual screenshot and found it does nothing
  there — and it is right. Verified.

  Why: N1 roots the branch at **your Answer**, and that question has no Answer at
  all. It has a note from you and a reply from the loop. Your own tie-breaker
  ("if no root exists, keep the note top-level rather than guessing") then says:
  leave it flat. Which is exactly how it looks today.

  There was a second, separate bug in that card, and it is already fixed: the loop had
  written its reply with a tag (`Answer (loop, …)`) that the parser does not recognise,
  so it was not treated as a reply at all — it fell into the question's body and
  rendered above the note it was answering. That one is repaired in the file.

  So the remaining question is what should happen when **the loop replies to something
  and you never answer it** — which is the common shape, and the shape of your
  screenshot.

  Rec **R1: add a loop resolution tag.** Today `Answer (via watch, …)` is *yours* — the
  page writes it when you answer, and there is no equivalent the loop can write. Give
  the loop one, and N1 works on your card unchanged, because now there is a root to
  hang the branch from. Costs one recognised tag in `file-formats.md`.

  **R2: let a loop reply become the root when you have not answered.** One line, fixes
  your card immediately — but it inverts on the very common case where the loop asks
  *you* a clarifying question and you answer it: the loop's question becomes the root
  and your answer becomes a reply underneath it, which reads backwards.

  **R3: ship N1 as-is and accept that this card stays flat.** Honest, and the threading
  still helps every question that does have an answer — but the thing you reported is
  not fixed.

  Answer `R1` (rec), `R2`, `R3`, or say what you would rather see.
  - **Answer (via watch, 2026-07-27 23:38):** rec

- **P2 · 2026-07-27 — #281 Q6, asked again in plain terms: should a task row on
  `/tasks` carry a button that points the loop at that task?**

  → answered (2026-07-27 23:39): **Yes, as a follow-up — filed as #344.** His
  words: *"yes, can be a followup (add to tasks in that case)"*, so the instruction
  to file it is explicit and is done rather than deferred to a later grooming pass.
  He took the recommendation's sequencing: `/tasks` earns read-correctness first,
  then gains the control. The reason that sequencing was recommended is recorded on
  #344 so it survives whoever implements it — a list you only read is safe to get
  wrong, a list that can start work is a control panel, and a mis-click redirects
  the loop.

  You said *"you'll
  need to explain what this means sorry"* — fair, the original asked in the
  loop's own vocabulary.

  Plainly: today, to aim the loop at one specific task, you type into the
  dashboard composer — `do-next: #281 …` — and the loop picks it up on its next
  tick. That machinery already exists and needs nothing new built.

  The question is whether **each row on the new `/tasks` page also carries a
  small button that sends exactly that**, so aiming the loop is one click on the
  row you are already reading instead of retyping its number into a box
  elsewhere.

  Rec **yes, but as a follow-up, after the page reads correctly** — because it
  changes what the page *is*. A list you only read is safe to get wrong; a list
  that can start work is a control panel, and a mis-click redirects the loop.
  How much authority a page holds is your call, not something to fold quietly
  into a list view.

  Answer `yes, v1`, `yes, follow-up` (rec), or `read-only`.
  - **Answer (via watch, 2026-07-27 23:39):** yes, can be a followup
    (add to tasks in that case)

- **P2 · 2026-07-27 — #252 Markdown `/file` modes: one quiet Rendered/Source switch in the file heading?**

  → answered (2026-07-27 23:39): **Accept M1 — one quiet Rendered/Source switch
  beside the path heading.** His `rec`. Rendered stays the default, Source shows
  exact escaped bytes and is deep-linkable via `?view=source`, the mode change uses
  the page's existing atmospheric dissolve with reduced-motion parity, and Source is
  never syntax-rewritten so copied bytes stay trustworthy. Two consequences for
  whoever picks it up. First, the approval authorises a red-first implementation
  with deterministic desktop/mobile captures and interleaved vision + geometry
  review — **not deployment**. Second, `#252`'s recorded blocker is now wrong: it
  says *blocked on #158*, and #158 has landed at `5c45d83`, so the real constraint
  is file ownership — `watch.py` is held by the #326 agent — not the dependency.
  Corrected on the ledger entry in the same increment, because a stale blocker is
  how a ready task sits unstarted while the loop looks past it.

  #158 already made `.md`/`.markdown`/`.mdx` reflow safely through the existing escape-first `mdB` pipeline while source files stay verbatim. #252 adds the explicit exact-bytes path and mode transition the human requested.

  Rec **M1**: for Markdown only, place a compact two-position **Rendered / Source** segmented switch beside the path heading. Rendered is the default; Source shows the exact escaped bytes in the existing `<pre>` and is deep-linkable with `?view=source` so copy/share preserves intent. Changing mode dissolves the body with the page's small atmospheric blur/fade gesture, keeps the heading/control fixed, restores the same scroll ratio where possible, and reduced-motion swaps instantly. Internal Markdown links reuse confined `/file` routing; external links remain explicit external anchors; raw HTML is always inert. Source is never syntax-rewritten, so exact copy remains trustworthy. Mobile keeps the same two labels in one row rather than hiding either mode.

  **M2** is a side-by-side rendered/source split (refuted: halves the reading column, poor on mobile, and makes exact/source secondary controls harder to understand). **M3** keeps Source as default with Rendered opt-in (refuted: contradicts the human's explicit default-rendered brief and #158's now-landed line). Approval authorises an isolated red-first implementation, deterministic desktop/mobile captures, and interleaved vision + geometry review; not deployment. Answer `Accept M1`, `Accept M1 with amendments: …`, or `Pause #252`.
  - **Answer (via watch, 2026-07-27 23:39):** rec

- **P1 · 2026-07-26 — #287 Matt Pocock skills bridge: accept the thin
  protocol/profile-adapter direction?**

  → answered (2026-07-27 23:18): **LGTM, and it waits for SQLite.** He took the
  option the loop's follow-up offered — *"let's wait till after sqlite so we
  don't have to rework anything"* — so #287 is APPROVED in direction, with both
  amendments (renamed `ud-dreamwork-matt-pocock-skills`; adapter layer plus a
  written compatibility note, never edits to the upstream skills) and the three
  constraints from the follow-up, and it is now **blocked on #294's cutover —
  the specification included.** Note for whoever picks this up: the loop's own
  answer was that constraint 1 (touch tasks only through the CLI seam) makes the
  cutover invisible, so the spec COULD have been written now; he chose to wait
  anyway, and that is the standing decision, not a misunderstanding to correct.
  This is the THIRD time today he has sequenced work behind the migration
  (#281 21:47, #289 23:11, this), which is why the rule is now in DREAMWORK.md. Cited research and coordinator/Grok
  iteration: `.dreamwork/docs/research/matt-pocock-skills-bridge-287.md`.

  Rec **A1**: accept revised Approach A′ and authorize writing the formal plugin
  specification only. `ud-dreamwork-matt-skills` adapts selected Dreamwork
  increments to Matt’s domain/grill/TDD/review/handoff norms while Dreamwork keeps
  the sole task queue, dashboard ask channel, scope/authority gates, worktree
  ownership, and compaction truth. It performs no tracker polling, creates no
  ready-agent queue/command or handoff authority, never auto-fires user-only
  skills, and remains useful without GitHub or `.scratch`.

  Defaults resolved from existing contracts: narrated process profile is normal;
  genuinely model-invocable installed skills may run when applicable; user-only
  commands require the human; one active grill serializes only its own
  `questions.md` chain; the chain is durable truth and any machine-local state is
  rebuildable; capabilities are detected and incompatibilities warned without
  exact-SHA lockout; `writing-great-skills` is author/review-time guidance, not a
  per-tick context tax. Observed friction does **not** yet justify new core
  runtime hooks—only clearer plugin documentation unless red evidence emerges.

  Approval does **not** authorize implementation, loading the plugin, running
  `setup-matt-pocock-skills`, editing CONTEXT/CLAUDE/AGENTS files, external
  tracker actions, or core Dreamwork changes. It authorizes a committed written
  spec for a second human review before planning/implementation.

  Answer `Accept A1 for specification only`, `Accept A2 with amendments: …`,
  `Choose A3; revise … and rereview`, or `Choose A4; pause the bridge`.
  - **Note (human, via watch, 2026-07-27 23:08):** Will this be a problem
    with the future migrations we're planning? those being like the sqlite
    tasks conversion, standardizing the loop through a cli tool (also
    relates to tasks), thhreaded discussions, dreamhub and making the
    architecture more modular, etc? If not, then rec also we should call
    the plugin ud-dreamwork-matt-pocock-skills also, we don't want to
    rewrite the skills, not sure if the proposed design (sec 9) implies
    that or not. but we want to like great a generic wrapper / adapter
    layer that says how to unify them and what to change to make it
    compatible with dreamwork.
  - **Follow-up (loop, 2026-07-27 23:16):** Short answer: **no, it should not
    collide with those migrations — but only because of three constraints, and
    they are cheap now and expensive later.** Taking your question first, then
    your two amendments.
  - **Follow-up (loop, 2026-07-27 23:16):** **1. SQLite tasks + the CLI (#294).**
    The bridge never owns the queue — it produces *candidates*, exactly as
    `ud-dreamwork-github` does with forge issues, and `tasks.md` stays
    coordinator-owned. The one real hazard is that if the spec is written against
    `tasks.md` **the file**, the bridge becomes a second parser that #294 then has
    to migrate — the very thing you told me to avoid twice tonight. So the
    constraint is: the bridge reads and writes tasks **only** through the
    tool/CLI seam (`dreamwork tasks list|get|grab|cycle`), never by parsing
    Markdown, from the first line of the spec. That makes the SQLite cutover
    invisible to it instead of a second conversion.
  - **Follow-up (loop, 2026-07-27 23:16):** **2. Threaded discussions (#254).**
    A "grill" is a question-and-answer chain and it lives in `questions.md`,
    which is the file #254 is about to give a rooted reply structure. Constraint:
    grill turns use the **existing** author-tag grammar and `human_block()` — no
    invented chain format. A bespoke sub-bullet shape would break the parser and
    #254's rooted-exchange rule at the same time, and it would break them
    silently, which is the failure mode this project cares most about. If a grill
    genuinely needs a new tag, that is a `file-formats.md` change reviewed on its
    own, not a side effect of the bridge.
  - **Follow-up (loop, 2026-07-27 23:16):** **3. Dreamhub and modularity.** Low
    risk, and already handled by a default you approved: any machine-local bridge
    state is rebuildable, and the durable truth is the `questions.md` chain. The
    constraint is just that the bridge adds no per-target state the hub must
    learn to read — otherwise "more modular" turns into one more thing every
    reader needs to know about.
  - **Follow-up (loop, 2026-07-27 23:16):** **Your amendments, both accepted.**
    The plugin is renamed **`ud-dreamwork-matt-pocock-skills`**. And on rewriting:
    §9 does not imply it — it says *adapt* Matt's suite to Dreamwork's grain,
    keeps most suite skills user-invoked, and reads CONTEXT/ADRs rather than
    replacing DREAMWORK.md. But it never states the prohibition outright, which
    is exactly how a later agent "adapts" by editing upstream. So the spec will
    say it plainly: the upstream skills are **not modified**, the bridge is a
    wrapper that maps his vocabulary onto ours, and *"what to change to make it
    compatible"* becomes a **written** compatibility note — a documented list of
    the gaps, not a set of edits anyone makes.
  - **Follow-up (loop, 2026-07-27 23:16):** Nothing here needs another decision
    from you unless you disagree with one of the three constraints. They are
    folded into #287's ledger entry so the spec is written against them. Say the
    word if you would rather the bridge wait until after the SQLite cutover
    entirely — it does not need to, given constraint 1, but that is your call and
    it is a one-word answer.
  - **Answer (via watch, 2026-07-27 23:17):** okay LGTM, but yeah let's
    wait till after sqlite so we don't have to rework anything.

- **P1 · 2026-07-27 — #289 review status/association: keep the decision
  record inside its owning question?**

  → answered (2026-07-27 23:12): **rec = Accept V1 for design**, plus a
  sequencing instruction: *"we should tie future versions into sqlite plan
  and/or redesign this to be done after sqlite."* Taken as: V1's record
  requirements are folded into #294's acceptance scope NOW (so the schema and
  CLI serve them at cutover), and #289's own implementation sequences after
  #294 rather than landing a pre-migration shape that then needs migrating
  again. This is the second time he has given that instruction — the first was
  #281 at 21:47 (*"factor in the requirements … so we do not pay for two
  migrations"*) — so it is recorded in DREAMWORK.md as a standing rule rather
  than applied twice by coincidence. The design authority stays exactly as his
  ask bounded it: a written design and migration proposal, no grammar, parser,
  lint, UI, icon, transition, artifact or deployment change. Read-only IGC compared a sidecar index,
  embedded question metadata, and a hybrid.

  Rec **V1**: extend the managed `questions.md` entry with one explicit record
  per artifact, e.g. `Review (pending|accepted|rejected, stamp): path`. The
  record is the sole authority for both association and decision. It moves with
  Open→Answered, survives title edits without duplicating the title elsewhere,
  supports several artifacts, disappears with its question, and never rewrites
  generated HTML. `collect()` derives the reverse artifact index in memory; list
  clicks use the current question title and can dock open or answered context.

  No record means **unlinked**, never pending. `pending` plus an answer awaiting
  loop fold may display an awaiting-fold waiting variant. Accepted/rejected are
  only the explicit enum—not answer prose, filename, HTML recommendation, or
  whether the question is folded. Two questions claiming the same artifact with
  conflicting decisions is a lint error. Existing artifacts remain unlinked
  unless deliberately migrated; no “Approved…” text scraping.

  **V2** uses committed `.dreamwork/review-index.json` (refuted: duplicates
  question title/status, needs lifecycle/GC writes, and can drift). **V3** puts
  metadata in each HTML artifact (refuted: generated artifacts need rewriting
  and question decisions live outside their channel).

  Approval authorizes a written design and migration proposal only—no grammar,
  parser, lint, UI, icon, transition, artifact, or deployment change. Answer
  `Accept V1 for design`, `Accept V1 with amendments: …`, `Choose V2`, or
  `Pause #289`.
  - **Answer (via watch, 2026-07-27 23:11):** rec, we should tie future
    versions into sqlite plan and/or redesign this to be done after
    sqlite.

- **P1 · 2026-07-27 — #254 note/reply conversation: use one rooted exchange
  branch rather than flat siblings or a nesting staircase?**

  → answered (2026-07-27 23:03): **rec = Accept N1 for written design.** The
  authority granted is a design/spec document and NOTHING else — his own words
  in the ask bound it: not parser, not file format, not UI, not migration, not
  deployment, not transitions. So the deliverable is a written spec plus a
  review artifact, and the implementation is a separate ask afterwards. Folded
  into #254 with that boundary stated in the entry, because an approval whose
  scope lives only in an answered question is an approval the next agent will
  read as broader than it is. Evidence:
  `.dreamwork/review/evidence/review-note-reply-unclear.png`.

  The screenshot's actual order is loop **Answer** first, then Max's later
  **YOU** note. Today they render as visually similar sibling rows, so the note
  reads like unrelated continuation. Rec **N1**: make the loop Answer the root
  response to the question and render later human Notes plus loop Replies as one
  connected discussion branch beneath it at a single inset depth. Preserve exact
  chronology, author and timestamp; recognise explicit `Reply (loop, …)`; never
  indent each turn more deeply; if no root exists, keep the note top-level rather
  than guessing. This is conventional comment→reply hierarchy without turning a
  long exchange into a diagonal staircase.

  **N2** nests only new explicit Reply tags, leaving legacy Notes flat until a
  file-format migration; this avoids inferred adjacency but leaves the reported
  case broken. **N3** uses a flat chat timeline with stronger bubbles/labels; it
  clarifies authorship but does not satisfy the requested comment→reply nesting.

  Approval authorizes a written design/spec only. It does not authorize parser,
  file-format, UI, migration, deployment, or transition changes. Answer `Accept
  N1 for written design`, `Accept N2 for written design`, `Choose N3`, or name a
  different relationship rule.
  - **Answer (via watch, 2026-07-27 23:02):** rec

- **P1 · 2026-07-27 — #283 index-lock attribution: authorise one bounded
  privileged audit capture, or stop at recurrence evidence?**

  → answered (2026-07-27 23:00): **Close after quiet window** (his rec), and
  the report is copied to `~/.llm-general/misc-reports/` as he asked —
  verbatim, because it already carries the 2026-07-27 attribution and the
  code-level fix, so it is not a snapshot that stops before the answer. Added
  a `README.md` there naming what the directory is for and, load-bearing for
  whoever reads it later, that a report is the INVESTIGATION while the current
  state of the machine is the `~/CLAUDE.md` mitigation entry plus
  `~/.llm-general/systems/<hostname>/` — a reader acting on the report alone
  could re-apply a fix that is already in place. #283 stays OPEN with its
  closing condition now written into the ledger entry rather than living only
  here: zero new orphaned locks in a quiet window after the next pi restart,
  which is the event that makes the patched extension effective. Updated report:
  `.dreamwork/docs/research/git-index-lock-attribution-283.md`.

  **2026-07-27 03:20 update — RESOLVED without L2/L3:** the existing
  git-lock-watch journal captured the creator in the act: `git status
  --porcelain` spawned by `pi-powerline-footer` (250/282 parent-pi snapshots
  in this repo). Code-level: `runGit(["status","--porcelain"],500)` had no
  `--no-optional-locks` and a 500ms `proc.kill()`, so under load the status
  died mid index-refresh and orphaned the lock. The installed extension is
  patched (effective on next pi restart; documented in the host mitigation
  ledger). L3/L2/L4 are moot. Remaining decision: keep #283 open until a
  quiet window after the next pi restart confirms zero new orphans, or close
  now with the watcher armed. Answer `Close after quiet window` (rec) or
  `Close #283 now`.
  - **Answer (via watch, 2026-07-27 22:58):** rec also please copy the
    report to ~/.llm-general/misc-reports/

- **P1 · 2026-07-27 — #281 `/tasks`: seven taste calls on the design proposal
  you asked for first.**
  → answered (2026-07-27 21:55): **ruled — six of seven, with Q1 overridden
  and Q6 sent back.** (1) **Not** as asked: the two-pane triage layout IS wanted,
  but as a second route `/tasks2`, with `/tasks` kept as the simpler one-column
  variant; order is the loop's choice. Filed as #328. (2) rec, plus the sort must
  be **user-configurable alongside the filters**, not a fixed default. (3) rec —
  open only, landed count visible and one click away. (4) rec — `?t=281` is
  canonical, so #282 may hardcode it. (5) rec with the hedge removed: do **not**
  label it "the loop's claim"; say **in progress** and put the honesty in a hover
  box reading *"Reported: Xm Ys ago"*. That is better than what was proposed —
  freshness is a fact where "claim" is a disclaimer, and it makes staleness
  legible rather than merely admitted. (6) **not answered** — *"you'll need to
  explain what this means sorry"*; re-asked plainly as its own entry, because the
  original asked in the loop's private vocabulary about the very thing it was
  meant to explain. (7) rec — and both have since landed (#301, #302).


  The self-contained artifact is
  `.dreamwork/review/tasks-page.html` (open it from the dashboard's review
  list); the implementation plan is `.dreamwork/docs/plans/tasks-page.md`,
  twelve increments landed as design-only at `f2c1bd0`. #281's own entry
  required a proposal before implementation, and #282's hovercards are blocked
  on the route/data contract it defines, so this is the ask that unblocks both.

  **Every one answers in a word, so a bare `rec` is a complete reply.**
  He also asked for two things the seven questions did not. First, **a full
  re-review of the proposal and its related docs against everything that has
  changed since `f2c1bd0`** — filed as #327, and warranted: #301 and #315 both
  moved the ledger readers the page depends on, and #302 moved `/answers`.
  Second, a ruling from me on ordering versus the SQLite migration.

  **The ordering call, made as he delegated it (*"Up to you what's best"*):
  `/tasks` first; #294 stays where it is.** His stated worry is paying for two
  migrations, and the answer is already inside #281's own entry: the page needs
  one new entry-level ledger reader as a single deep module, and **that reader is
  the designated seam #294 re-points at SQLite.** The page's markup, sort,
  filter, URL and hovercard contracts are therefore downstream of a *shape*, not
  of a storage — the migration re-points one function, not a page. Two migrations
  happen only if `/tasks` parses the Markdown itself, which is now a stated and
  checkable constraint on the task rather than a hope. Against that, #294 is
  blocked on #264 and #263, both still-unanswered design asks, so ordering it
  first would idle a P1 surface behind two open questions. What his hint does buy
  is real and has been taken: the `/tasks` read requirements are folded into
  #294's acceptance scope, so the migration is built already knowing what the
  page needs. The CLI is part of #294 and travels with it.

  1. **Wide-screen two-pane list-plus-detail triage layout?** Rec **no, for
     v1** — `watch-design.md` names `/review` as *the* deliberate width
     exception, and a second exception is how a one-column page becomes a
     two-column one. A split view can be added later without changing the
     data contract.
  2. **Default sort: priority band, or newest id (the file's own order)?** Rec
     **priority, then newest id** — the ledger is written in arrival order,
     which is not urgency, and the page's job is to say what to look at first.
  3. **Default filter: open only, or everything?** Rec **open only**, with the
     landed count visible in the count line and one click away — 17 settled
     rows diluting 103 live ones is the opposite of ranking.
  4. **Is `/tasks?t=281` the canonical detail URL #282 hardcodes, or do you
     want `/tasks/281`?** Rec **`?t=281`** — it keeps the server's route
     allowlist an exact membership test and matches `/file?p=` and
     `/review?p=`. `/tasks/281` reads nicer and costs prefix routing in the
     very seam #133 will rewrite.
  5. **Show the loop's `status.json` claim ("I am on #281 right now"), given
     it is a claim and not a fact?** Rec **yes, labelled as the loop's claim**,
     carrying the page's only accent. It is the sole in-flight signal that
     exists; #294 is what turns it into a fact. The alternative is a page that
     cannot tell you what is happening now.
  6. **A write affordance on a row later — `do now: #281` sent from the
     list?** Rec **not in v1, yes as a follow-up.** It needs no new endpoint or
     vocabulary (`/command` + `do-now` exist), so it is cheap — but it turns a
     read-only page into a steering surface, and that is deliberately your call
     rather than something folded into a list page.
  7. **The two findings the batch turned up** — now filed as **#301** (both
     ledger patterns are blind to combined entry heads) and **#302** (`/answers`
     has no `TINT`/`SEED` entry). Rec **filed, worked in id order behind
     #281**; #301 is P2 because it is a wrong number on the live dashboard, and
     the coordinator's own re-measurement narrowed *which* number — see the
     entry.

  Answer `rec`, `rec except N: …`, or answer them individually. Approval
  authorises red-first implementation of the twelve increments in an isolated
  worktree with the visual gate — not deployment.
  - **Answer (via watch, 2026-07-27 21:47):** Hmm perhaps we should do
    the task migration to sqlite first so that we can factor in the
    requirements of `/tasks`? 1. yes but let's do it at `/tasks2`, and
    keep a simpler 1 column variant at `/tasks`. We can do them in
    whichever order you prefer. 2. rec, but user configurable alongisde
    filters 3. rec 4. rec 5. rec, though we don't need to draw attention
    to the fact it's a claim, we can just say that it's inprog and have
    a little box/tooltip on hover saying like 'Reported: Xm Ys ago' or
    the like. 6. you'll need to explain what this means sorry. btw,
    please do a full review of the tasks-page proposal and related docs
    relative to anything that might have changed since then, make sure
    it all still works. 7. rec Okay so on the sqlite thing, we can go
    either way. Up to you what's best. However, keep in mind we might
    need to do multiple migrations unless we factor in the requirements
    of this task into sqlite task and then do the sqlite conversion
    first. and before that we should probably do the cli i guess.

- **P1 · 2026-07-27 — #286 note/answer paragraphs: preserve authored blank
  lines in the managed question record?**
  → answered (2026-07-27 21:50): **B1 accepted for design** — *"rec B1"*. The
  paragraph-aware safe writer is authorised as a written design and fixture
  proposal only; the grammar, writer, parser, renderer and migration changes
  still need their own approval, per the ask's own terms. #286 is unblocked for
  the design increment, and #254 replies inherit the contract it settles.

  Read-only diagnosis traced the loss. The browser and `submissions.log` retain exact newlines, but `human_block()`
  currently collapses **all** whitespace into one paragraph before writing
  `questions.md`; the parser treats a blank line as ending Note/Answer capture;
  the renderer uses inline Markdown. Therefore the durable question channel
  cannot reconstruct paragraphs today.

  Rec **B1**: make the existing safe writer paragraph-aware. Within each
  authored paragraph, soft newlines and source hard-wraps still join with spaces;
  authored blank lines become indented paragraph separators that remain inside
  the Note/Answer sub-record. The parser reconstructs `\n\n`, and the existing
  block Markdown renderer emits separate paragraphs. Preserve #146's anti-forge
  guarantees: pasted bullets/sections never become sibling entries, and exact
  receipt bytes remain unchanged. #254 replies inherit this contract later.

  **B2** stores a visible sentinel such as `¶` (refuted: invents an ugly private
  dialect). **B3** reconstructs from `submissions.log` (refuted: receipt is not
  the authoritative questions channel). **B4** keeps single paragraphs.

  Approval authorizes a written design/fixture proposal only—no grammar, writer,
  parser, renderer, migration, or deployment change. Answer `Accept B1 for
  design`, `Accept B1 with amendments: …`, or `Choose B4; keep one paragraph`.
  - **Answer (via watch, 2026-07-27 21:50):** rec B1

- **P1 · 2026-07-27 — #290 main-dreamer run modes: accept the local
  three-mode v1 and reserve hierarchy?**
  → answered (2026-07-27 16:35): **approved and shipped — this ask was simply
  never folded.** His authorization arrived on a different channel and went
  further than this entry asked for: the ask offered M1/M2/M3 and said approval
  would authorize "a written design and visual proposal only", while what he
  actually wrote in `answers.md` at 01:57 was "Modes 1-3 have no hard dependency
  and I have sent the implementation to Grok" — answering the dependency
  question and granting implementation authority in one move. M1 is what
  shipped: authoritative machine-local `.dreamwork/run-mode`, mirrored into
  status but never owned by it, with the resettable 10-second cross-tab arm
  emitting one coalesced event. `hierarchical` stays visible but disabled
  pending #264 and #288, exactly as both he and this entry required. Landed
  across `2f0e7ea`..`b0db53d`, closed `4d3ec8b`; this host's mode is `hot`.
  Why it sat here as an open P1 for ~15 hours: the answering commit `4c18941`
  wrote `answers.md` and the ledger and never touched this file, so the two
  channels did not cross-reference and the ask stayed open with its work already
  deployed. Nothing detects that — a question whose subject has landed looks
  exactly like one still waiting. Filed as #306.
 Read-only architecture map from Grok
  confirms `status.json` is an ephemeral loop claim, `/command` is wake-only,
  and `.dreamwork/watch-tint` is the closest durable-setting precedent.

  Rec **M1**: machine-local/gitignored `.dreamwork/run-mode` is authoritative;
  `status.json` mirrors it but never owns it. Selectable v1 modes are
  **lackadaisical** (idle-friendly, no proactive fan-out), **hot** (continuous
  bounded work, coordinator-only), and **assisted** (hot plus a few disjoint
  helpers under existing ownership rules). Show **hierarchical** as planned but
  disabled until #264 concurrency and #288 containment/authority design make it
  honest.

  The dashboard shares one pending mode/deadline across tabs. Every change resets
  a visible 10-second countdown; only the final mode is atomically persisted and
  emits one monitored event. Identical final submissions are idempotent. Reduced
  motion removes the continuously animated width but retains the second-by-second
  text countdown and identical application time/function. Reload/tick reads the
  authoritative file; compaction cannot lose it.

  **M2** commits the mode to Git so collaborators inherit it (not recommended: an
  operational posture becomes a surprising project default). **M3** puts it only
  in `status.json` (refuted: tick/compaction writers may overwrite it).

  Approval authorizes a written design and visual proposal only—no endpoint,
  state file, event, UI, mode-policy, subagent fan-out, deployment, or hierarchy.
  Answer `Accept M1 for design`, `Accept M1 with mode-name changes: …`, `Choose
  M2`, or `Pause #290`.

- **P1 · 2026-07-26 — #283 Git index-lock attribution: run the safe
  Dolphin-window falsification test before privileged tracing?**
  → answered (2026-07-27 00:16): Max closed the window and said, exactly,
  “closed. but not sure that it's dolphin is it? if it is that's good to
  know.” This authorizes only the previously described 60-second read-only
  L1 observation. It does not assume the window was Dolphin and does not
  authorize privileged tracing, process attachment, KIO changes, lock deletion,
  or watcher changes. The observation started immediately; its result will be
  folded into `.dreamwork/docs/research/git-index-lock-attribution-283.md`.

  **Human:** “closed. but not sure that it's dolphin is it? if it is that's
  good to know.”

- **P2 · 2026-07-25 — whose is `ud-dw-generate`? It is untracked in this repo
  and I am not touching it.**
  → answered (2026-07-26 18:51): Leave the executable byte-for-byte
  untouched. Added only `ud-dw-generate.notes.md`: intended standalone
  purpose is random ASCII-safe data (hex initially); current script came
  from Max’s dd2 download-page request and remains coupled to dd2. Revisit
  after dd2 is fixed and remove that dependency under #285.
 An 8KB executable appeared at 16:17: a
  preview-URL minter that reads repo+branch from the cwd, mints a nonce,
  and creates a directory on a server (config outside version control,
  keyed by repo slug; the example names `dd2-data-download-page`).

  Not mine and not the dreamer's — it flagged the same file and left it
  alone, which was right. Two agents have been committing in this tree
  all afternoon; both stage by explicit path, so it has survived, but it
  is not gitignored and one `git add -A` from anywhere would sweep it in.

  **Nothing needs deciding urgently** — it is safe as long as nobody gets
  careless. Say what it is when you get a moment: yours to keep here,
  something that belongs in another repo, or scratch to delete. Until you
  do it stays exactly where it is.
  - **Answer (via watch, 2026-07-26 18:50):** uhh yeah it was just meant
    to generate hex i think. add a ud-dw-generate.notes.md next to it
    saying that ud-dw-generate should generate random data (ascii safe)
    and that it was based on something Max requested in the dd2 download
    page repo but we should revisit it later once i get the dd2 thing
    fixed up so it doesn't depend on it.

- **P2 · 2026-07-25 — should the PreCompact hook ship, and as a plugin? (#138)**
  → answered (2026-07-26 18:50): Approved as recommended: ship #138 and
  #156 together as one optional plugin, off by default. Loading is a
  recorded DREAMWORK.md decision; it never silently edits machine config.
  PreCompact preservation must be silent/fail-safe and must not turn a
  preservation failure into skipped compaction. Two byte-identical receipts
  at 18:48:53 are one logical answer and a #274 duplicate-delivery witness.

  This one is here because it was missing. It has been listed as
  awaiting you in `status.json` for hours and was never written down —
  the third time today an ask lived only in a task description
  (also #158, #172). Recording it is the fix; see #181 for the
  mechanism fix.

  **The thing itself**: compaction can drop what the loop knows. The
  loop's answer is to write down before compacting, which currently
  depends on an agent remembering to. Claude Code fires a **PreCompact**
  hook for both manual and automatic compaction, so the write-down could
  be automatic. Verified against the binary (2.1.219) while writing
  `compaction.md`: a hook's stdout is appended to the summariser's focus
  instructions — undocumented, and genuinely useful, because the loop
  could tell the summariser what must survive.

  **Why it needs you and not a rec**: a hook is a line in *your* machine
  config, not project content. It fires on every compaction in that
  project, including sessions that have nothing to do with dreamwork. And
  blocking a compact is a hard skip, not a postponement — a hook that
  fails at the wrong moment removes the compaction rather than delaying
  it.

  Rec: **yes, as an optional plugin, off by default** — same shape as
  `ud-dreamwork-github`, so loading it is a recorded decision in
  DREAMWORK.md rather than something the loop does to your config. Bundle
  it with #156 (the PostToolUse lint hook), since both are the same
  question — may the loop install hooks — and answering once beats twice.

  Answer "ship it", "not yet", or name a different shape.
  - **Answer (via watch, 2026-07-26 18:48):** rec
  - **Answer (via watch, 2026-07-26 18:48):** rec

- **P2 · 2026-07-26 — #213 task-origin contract: adopt the forward-only
  cutoff?**
  → answered (2026-07-26 18:37): Approved: enforce origin: human|loop for tasks from
  the #216 cutoff onward; historical records remain honestly unknown. The
  contract/linter is authorized; parsing and three-way UI remain #216/#217.
 The review is at `.dreamwork/review/task-origin-contract.html`.
  Rec: record `origin: **human|loop**` on every new ledger task and begin
  enforcement at the current next id, #216; leave all older tasks unknown
  rather than backfilling guesses. This increment adds the contract and
  linter only. First-seen history parsing and the honest three-way
  human/loop/unmarked visualisation remain later increments.

  Answer `rec`, or leave a note naming what should change.
  - **Note (human, via watch, 2026-07-26 15:33):** the burndown warning that
    most entries cannot split human steers from loop ideas should be addressed
    by tracking task provenance.
  - **Follow-up (loop, 2026-07-26 15:34):** Confirmed as the #213 goal. #216 then
    parses first-seen origin and #217 renders human / loop / historical-unknown
    coverage. The remaining decision is migration honesty: rec remains the
    forward-only cutoff; guessing old origins would make the chart look more
    precise by making it less true.
  - **Answer (via watch, 2026-07-26 18:36):** rec

- **P2 · 2026-07-26 — #253 contextual review annotations: keep the review
  iframe and bridge selections to a parent-owned side rail?**
  → answered (2026-07-26 18:37): Approved as recommended: preserve the style-isolated
  iframe; add a narrow versioned postMessage selection bridge; parent owns
  validated anchored annotations and explicit orphans; attached chats stay
  globally visible, begin with the main dreamer, and only promote explicitly.
 Research is at
  `.dreamwork/docs/research/contextual-review-annotations.md`. Three models
  were tested: one chat per mark is too noisy/expensive; one document-wide
  chat loses per-selection resolution; the survivor is lightweight anchored
  sidecar notes with one-time promotion into #229 topic chat for deep or agent
  work.

  Rec: preserve the iframe as static, style-isolated evidence and add a narrow,
  versioned `postMessage` selection bridge. The parent validates quote/context
  and owns the mutable annotation rail. Anchors combine artifact hash, heading
  path, paragraph ordinal and normalised quote/context; ambiguous edits become
  explicit orphans, never silently move. Typed task/update requests mint normal
  human-origin ledger tasks; workers run only after chat promotion or ordinary
  coordinator dispatch.

  Answer `Approve #253 iframe bridge as recommended`, or choose `in-page`
  annotation rendering instead.
  - **Note (human, via watch, 2026-07-26 15:41; moved from #255):** chats
    should attach to any artifact or a precise reference within an artifact,
    while all chats remain visible from the global `/chat` route.
  - **Follow-up (loop, 2026-07-26 15:42):** Folded into #253/#229. Attachment is
    provenance/navigation, not a private namespace: an artifact-level or
    selection-level chat still appears in `/chat`. MVP should have one primary
    attachment plus reciprocal backlinks; multiple references can follow.
  - **Note (human, via watch, 2026-07-26 15:43; moved from #255):** provide a
    simple mode first with no subagent; the main dreamer responds as it does now.
  - **Follow-up (loop, 2026-07-26 15:44):** Adopted as staging: attached discussions
    begin in main-dreamer mode, then may be explicitly promoted to a dedicated
    fresh worker without forking transcript or attachment history. No silent
    fallback or automatic dispatch. This lets sidecar discussion ship before
    #229's worker orchestration.
  - **Answer (via watch, 2026-07-26 18:35):** Approve #253 iframe bridge
    as recommended

- **P2 · 2026-07-26 — #221 review datetime ordering: use file mtime?**
  → answered (2026-07-26 18:26): Approved: newest filesystem mtime first, filename
  as deterministic tie-break; the displayed age and ordering use the same
  source.

  The decision artifact is at `.dreamwork/review/review-datetime-order.html`.
  Rec: newest filesystem mtime first, filename as the deterministic tie-break.
  The row already displays age from that mtime, so ordering and its visible
  claim share one source. Parsing filenames fails for undated artifacts;
  embedded metadata would add a new format without new information.

  Answer `rec`, or leave a note naming a different authoritative datetime.
  - **Answer (via watch, 2026-07-26 18:25):** rec

- **P2 · 2026-07-26 — #225 `explore` command: approve the one-shot
  proposal contract?**
  → answered (2026-07-26 18:26): Approved with “hidden” clarified to mean exactly
  maintenance-style secondary disclosure: a real accessible composer kind,
  absent from the default visible row and never initially selected, but
  discoverable through the established cycling/secondary affordance. It is
  not undocumented, slash-only or keyboard/touch-inaccessible.
 The review artifact is at
  `.dreamwork/review/explore-command-contract.html`. Rec: hidden command
  named `explore`; fresh research/design subagent by default; one concise,
  offline-clean HTML decision artifact; explicit alternatives, unknowns and
  smallest experiment; proposal-only authority; accepted recommendations
  become ordinary human-approved tasks.

  Answer `Approve A–D as recommended`, or name changes to A name,
  B dispatch, C authority, or D output.
  - **Note (human, via watch, 2026-07-26 18:23):** what does 'hidden' mean
    here? I meant it to be like 'maintenance' in the composer, just not
    shown by default.
  - **Note (human, via watch, 2026-07-26 18:24):** LGTM. rec. (assuming we
    mean the same thing by 'hidden')
  - **Answer (via watch, 2026-07-26 18:25):** LGTM. rec. (assuming we
    mean the same thing by 'hidden')

- **P1 · 2026-07-26 — #255 composer confirmation lifecycle: approve the
  shared 5-second design?**
  → answered (2026-07-26 18:19): Approved as recommended: one shared ~5s success
  lifecycle independent of typing/panel close, with atmospheric arrival/
  departure, hard cleanup on unmount, and reduced-motion timing parity.
  Implementation is now authorized.
 Root cause is measured: typing during the POST sets
  `composing=true`, so success never creates the panel's 1425ms courtesy-close
  timer; later input handlers see no timer and leave `sent to the dream`
  forever. The popout has an independently permanent message path.

  Rec: separate the concerns. A successful confirmation always owns one shared
  lifecycle: atmospheric arrival, readable for about 5s, atmospheric departure,
  then clear. Typing keeps the panel open but does not erase or strand that
  valid confirmation. Closing/unmounting hard-cleans it. The panel's courtesy
  close stays independent. False/error claims still withdraw immediately.
  Reduced motion keeps the 5s semantics but snaps visual states. Main and
  popout consume the same lifecycle helper; this does not attempt #241's full
  composer extraction.

  Answer `Approve #255 as recommended`, or say whether typing should instead
  clear a valid confirmation immediately.
  - **Answer (via watch, 2026-07-26 18:18):** Approve #255 as
    recommended

- **P1 · 2026-07-26 — #257/#258 do-now urgency: approve the scoped rose
  signal and restrained ambient cast?**
  → answered (2026-07-26 18:19): D1 approved as the default. Other recommendations
  accepted except the earlier simple shader treatment, superseded by
  #278–#280. D2 may become an optional toggle after redesigning its left
  rail as border plus top-cast red light. #257 awaits #241 implementation;
  #258 closes into the new shader diagnosis/prototype/selector track.
 Reviewed artifact:
  `.dreamwork/review/do-now-urgency-treatment.html` (desktop/mobile vision and
  geometry PASS). Amber `--warn` already means BROKEN, so intentional
  interruption needs its own rose-red `--danger` token.

  Rec A: colour only the selected `do-now` label and existing ghost-outline
  indicator, not the whole command rail. Rec B: the shader gets a slight storm
  plus restrained rose cast, never a hard red wash. Rec C: use `#f87171`,
  distinct from warn amber and accent lilac. Rec D: implement composer chrome
  after #241's shared mount; shader emotion axes may follow independently.
  Reduced motion retains colour/state but removes energetic pulse; no new
  full-resolution shader pass.

  Answer `Approve A–D as recommended`, or choose A full-group hazard, B
  storm-only, a different danger token, or different sequencing.
  - **Note (human, via watch, 2026-07-26 18:12):** for the storm shader
    stuff, can we make the stormy version look more like jupiter? ohh and i
    notice having left this open that the shaders seem to get faster over
    time. anyway, i got some images that are kinda like what I want,
    basically more fluid dynamics at higher levels. The shaders presented
    are a bit simple. geometry should use some work.
    /home/xertrov/Documents/storm{1,2,3,4,5,6,7}.{webp,jpg} if we need to
    make substantial changes to the current bg shader, we should create a
    copy of it that we can edit without changing the original. keep both,
    we might let the user choose between different bg shaders in future.
  - **Follow-up (loop, 2026-07-26 18:13):** Captured as #278 acceleration
    diagnosis, #279 a separate Jupiter-like reference-driven storm prototype,
    and #280 a later preserved-shader registry/selector. The current shader
    remains untouched. This is an amendment, not A–D approval: scoped composer
    danger chrome remains separately reviewable; the shader recommendation will
    return in a new visual proposal after diagnosis/prototype review.
  - **Answer (via watch, 2026-07-26 18:17):** yeah D1 is a go. I like
    the idea of having an option for D2 that we can toggle, but idk that
    the left side is the right place for the glow. maybe just border +
    glow from above like red lighting or something? rec on any other
    questions for this one.

- **P1 · 2026-07-26 — #233 LAN binding: trust the LAN, or require
  authentication first?** The threat-model review is at
  → answered (2026-07-26 17:49): Approved A: ship explicit unauthenticated
  trusted-LAN mode with the reviewed Host/Origin safeguards and warnings.
  Later authentication is separate work: #275 public Dreamhub auth informed
  by shoo.dev and #276 simple LAN bearer-token access. The duplicate identical
  answer delivery is #274, not a second approval.
  `.dreamwork/review/lan-bind-threat-model.html`. Host + Origin checks stop
  DNS rebinding and browser CSRF, but do not authenticate another LAN client.
  Rec A: explicit unauthenticated trusted-LAN mode with loopback default,
  exact Host allowlist, same-origin browser writes, explicit advertised URL,
  IPv6 correctness and a loud startup warning. Alternative B: stop and design
  auth/TLS before non-local binding.

  Answer `Approve A: trusted-LAN mode`, or `B: require authentication`.
  - **Answer (via watch, 2026-07-26 17:48):** A, but later we'll add
    other auth like shoo.dev for public dreamhub and a simple bearer
    token like thing for lan PCs or phone or whatever.

- **P1 · 2026-07-26 — #229 threaded topic chats: approve the proposed
  architecture and defaults?** The reviewed artifact is at
  → answered (2026-07-26 17:11): Revision directed, not approved. Update the
  artifact against the full Grok architecture review and #272 measured UX
  review, self-review it against Dreamwork goals, then open a new proposal for
  human review. No implementation authority was granted.
  `.dreamwork/review/threaded-topic-chats.html`. Rec: a compact dashboard
  chat index + dedicated `/chat` route; append-only Markdown transcript as
  primary truth and fresh worker input; one run and one editable queued
  follow-up per chat; deep orchestration module; global cap 2; machine-local
  gitignored chats; no MVP cancellation until `cancelled` can be durably
  finalised; manual retention. This is proposal approval only, not authority
  to implement.

  Answer `Approve A–E as recommended`, or name changes to A surface,
  B privacy, C concurrency, D cancellation, or E retention.
  - **Note (human, via watch, 2026-07-26 14:47):** I added a task recently
    that intereacted with the threaded topic chats; has the html artifact
    been updated?
  - **Follow-up (loop, 2026-07-26 14:48):** Yes for the two feature amendments:
    the artifact's “Human amendments · 14:09” section explicitly includes
    #235 (`/answers` follow-up promotion) and #236 (compact accessed-file/tool
    provenance). The later cross-cutting #239 generated-HTML style-source
    requirement was only in the ledger/context, not named in the artifact;
    it is now an explicit third amendment: topic-chat generated HTML consumes
    the canonical resolver/plugin override and does not embed a private theme.
    The artifact is current; A–E remain awaiting approval.
  - **Note (human, via watch, 2026-07-26 16:12):** we should be able to
    attach chat's to any artifact or reference within an artifact. Still
    want to be able to see all chats via /chat route too.
  - **Follow-up (loop, 2026-07-26 16:12):** Re-homed onto this #229 card
    from a misfiled 15:41 note: submissions.log shows
    from=/review?p=threaded-topic-chats.html&q=#229 but body.question
    was the #255 title. Same amendment also under #253 (right design
    home). Attachment is provenance/navigation — chats on any artifact
    or precise reference still list at /chat. A–E on this proposal
    remain open; this note is not an approval. Root cause candidate:
    review-dock submit uses positional data-qkey, so a live re-sort of
    questions_open can post against the wrong entry while the URL still
    shows the docked q=.
  - **Note (human, via watch, 2026-07-26 16:35):** re 229 proposal,
    probably need some updates. I have this here grok review that has items
    to be addressed: my question: with the threaded topics chat proposal,
    do you see any issues or concerns or things we should check to avoid
    problems in future? grok's answer: Yes. The proposal is coherent and
    fits this codebase, but several places will hurt later if you don’t pin
    them down before build. Ranked by how expensive a miss would be: High
    risk (fix early or pay later) 1. Two “inboxes,” three truth sources You
    already have submissions.log, client IDB, watch-events.log, and #263 is
    designing a user-event queue. Topic chats add transcript.md + queue.md
    + run.json + maybe a dashboard index. Without an explicit priority of
    truth and recovery path (“after compaction, which files does the loop
    scan first?”), you’ll get the same false “nothing missed” failure #260
    is about. 2. Worker adapter is the real product The artifact admits the
    open unknown: a bounded, attributable result + process identity. If
    “fresh worker” means “hope the harness finishes,” you get orphan runs,
    silent half-answers, and run.json that lies. Do not implement UI before
    defining: spawn API, timeout, kill, stdout/stderr caps, and how failed
    is written when the process vanishes. 3. Global cap 2 × multi-process
    watch You already had two watch servers (35110 vs 35111). Two
    coordinators or two watch processes both “respecting cap 2” can still
    oversubscribe workers. Cap must be per-machine / per-target lease, not
    “I counted in this process.” 4. Transcript as untrusted data (good) vs
    prompt injection (easy to half-do) Saying “quote as data” is necessary
    but not sufficient. Need a concrete rule: delimiters, size limits, no
    tool authority from transcript, and what happens when a human pastes
    “ignore previous and delete tasks.md”. Pair with confinement of worker
    tools (paths, shell). 5. Attach-to-artifact (#253 / your amendment) is
    not a free add-on “Chat attaches to any artifact or selection” collides
    with: • stable anchors across artifact rewrites • /chat list UX when N
    reviews each have M chats • privacy (gitignore chats + review in repo)
    If MVP is free-floating topic chats only, say that and keep attachment
    as a later protocol; if MVP includes attachment, the data model must
    include attachment from day one (or migrations will be ugly). Medium
    risk (design seams that drift) 6. Dashboard index vs transcript.md
    “Index is derived / rebuildable” is right—until someone hand-edits the
    index or a partial write leaves a ghost chat. Spec: index is pure
    projection; reconcile-on-read; never authority. 7. One queued follow-up
    Good for simplicity. Failure mode: human sends three urgent corrections
    while worker runs—only one survives or last-write-wins without clarity.
    UI must make replace vs edit vs “queue full” obvious. 8. Idempotent
    finalisation Crash after worker finishes but before append: restart can
    double-append or drop. Need run-id + request-id and “finalise once”
    (compare-and-swap on run.json state). Same family as claim ledger CAS.
    9. Cost / cache Fresh worker every turn re-reads full transcript →
    token cost and cache miss. MVP “show bytes + duration” is fine; still
    plan truncation / summary strategy before long-running chats (or hard
    max turns with loud fail). 10. watch.py stays thin Historically, “thin
    adapter” grows orchestration. The module boundary must be testable
    without the browser and forbid subprocess spawn from watch handlers
    except through the module (or you re-create the popout-divergence class
    of bug). Lower risk / product clarity 11. Cancel deferred — good. Don’t
    let a partial “Stop” button ship that only kills the process without a
    transcript line. 12. Gitignore by default — good for privacy; bad for
    multi-machine Max. Export path should be explicit, not “someone git add
    -f’d a chat.” 13. Naming: avoid “thread” in code — good; keep UI copy
    separate so #254 “comment threads” don’t share words with OS threads.
    14. #235 promotion from /answers — needs atomicity: seed chat + link
    answer + dispatch, or you get orphan chats / double history. 15. #236
    provenance index — define redaction (paths ok? command args? secrets in
    shell?) before workers write it. Checks I’d run before treating A–E as
    build-ready
    ┌────────────────────────────────────────────────────────────────────────────────────────────┬──────────────────────────────┐
    │ Check │ Why │
    ├────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────┤
    │ Write the state machine for one chat (idle → running → queue full →
    failed → reconcile) as │ Same discipline as worktrees │ │ a table with
    crash points │ claims │
    ├────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────┤
    │ One hostile transcript fixture (injection + huge paste + forged
    terminal outcome) │ G4/G5 honesty │
    ├────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────┤
    │ Single-writer test: two processes try to dispatch same chat │
    Port/cap reality │
    ├────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────┤
    │ Recovery drill: kill worker mid-run, restart loop, assert no fake
    completed │ Compaction cousin │
    ├────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────┤
    │ Decide attachment MVP in/out with a one-line product rule │ Stops
    #229/#253 from │ │ │ fighting │
    ├────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────┤
    │ Map chat events onto #263 user-event story (or explicitly exclude) │
    Avoid third queue │
    ├────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────┤
    │ Confirm dock/submit identity (#266) doesn’t poison “send from review
    → create chat” later │ You just got bitten by wrong │ │ │ target │
    └────────────────────────────────────────────────────────────────────────────────────────────┴──────────────────────────────┘
    What’s already strong (don’t abandon) • Transcript-first, not
    model-session-first • Human words durable before dispatch • Dashboard
    index + dedicated route (not either alone) • One deep module vs fat
    watch.py • Honest terminal outcomes • Cap + single in-flight worker per
    chat Bottom line Approve A–E as architecture if you’re happy with those
    defaults—but treat worker adapter + crash finalisation + “which durable
    log is authority after restart” as gates before any implementation
    sprint. The future pain is less “wrong chat UX” and more orphan
    workers, double finalise, and competing recovery channels—the same
    failure modes this project has already paid for with submissions,
    ports, and compaction. I can turn this into a short “pre-implementation
    checklist” section for the proposal or questions.md if you want that
    written down later (currently still read-only unless you/dcd88e ask for
    edits).
  - **Follow-up (loop, 2026-07-26 16:48):** Re-homed from the #257/#258
    card after a second #266 wrong-target submission. All 15 review concerns
    are accepted as proposal-hardening inputs, not as A–E approval. #270 will
    update and re-review the artifact; recovery ordering consumes #263, and
    review-origin identity consumes #266 before implementation.
  - **Answer (via watch, 2026-07-26 17:10):** Fix up the 229 proposal
    according to the grok review and then do a self review after to
    figure out if the new proposal satisfies our goals. Then present me
    a new proposal to review that integrates all updates and fixes etc.

- **P1 · 2026-07-25 — which "t3 connect" do you mean, and does it change #201?
  (#202)** → resolved (2026-07-26): the linked primary source identifies T3
  Connect precisely. It is Clerk-backed environment discovery/linking plus a
  managed Cloudflare tunnel around an ordinary authenticated T3 Code server;
  it is not a TUI, agent, ACP, or PTY protocol. T3 Code overlaps #201's desired
  user outcome, but Connect itself cannot adopt or stream an existing herdr
  PTY. Keep #201's `/compact` herdr-control increment; before terminal
  rendering, investigate whether T3 Code exposes a supported deep lin
