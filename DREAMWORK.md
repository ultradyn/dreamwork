---
dreamwork-version: 5853e1789929
---
# DREAMWORK.md — ud-dreamwork

## Goals

- Make "leave an agent dreaming on a project" a real workflow: the human
  can walk away and come back to steady, safe, well-chosen progress.
  - The loop's memory survives anything that ends a session — restart,
    compaction, a fresh agent. What it knew, it still knows.
  - The dashboard is how you check on it and steer it without a chat
    turn, and it is worth looking at.
  - **Nothing fails quietly** (folded 2026-07-25 from what the loop
    learned, not from a stated ask — say if you disagree). "Safe" turns
    out to mean legible: on one day this loop found a questions.md that
    parsed to nothing and rendered as "nothing to answer", a command
    channel nothing read, a refused write that reported success, an
    enter animation that had never once run under a matrix documenting
    it, and several checks that passed on their own bug. Every one of
    them looked fine. So the loop prefers a loud wrong state to a quiet
    one, and prefers removing the opportunity for a mistake over
    restating the rule against it.
  - **One human, several dreaming agents** (approved 2026-07-25, #96):
    the workflow scales past one session — a hub aggregates them, and
    managing an agent's lifecycle (spawning, steering, compacting,
    retiring) becomes something the system does deliberately rather
    than something the human improvises per client.
- The loop stays cheap (cache-warm heartbeat), never gets stuck or bored,
  and is always steerable in a few words (`do now` / `do next` /
  `add idea`).
- The loop gets on the human's wavelength over time: goals and
  preferences accrete here so questions get answered once and asking
  trends down, not up.

## Philosophy

- Small verified increments are the error-catching mechanism.
- Ideas are never lost.
- **His typed words are never lost either** (human-set 2026-07-27 21:35:
  *"we must have persistence and never lose work on an autoreload of a
  page"*). Stated about one box, but it is a property of the whole UI: any
  field he can type into keeps what he typed across a reload, a re-render
  and a route change, and a draft is cleared only on a **durable success** —
  never on close, blur, or a rejected send, because those are exactly the
  moments he most needs it back. He said it after losing answers on the page
  he uses to answer the loop's questions, which had stalled the loop's own
  largest open decision for hours; so this is not politeness about
  convenience, it is the channel the loop depends on.
- Know what the human wants so we make what the human needs.
- Reflection over momentum.
- The loop should feel like a colleague pottering productively — not
  runaway automation: no make-work, no ungated experiments, no pivots;
  scope expansion defers to the human.
- Unclear is a goals problem: every needed conversation with the human is
  also a moment to sharpen this file; contradictions between this file
  and what the human says now get surfaced, and the human resolves them.
- Durable over ephemeral: asks, decisions, and memory live in files
  (questions.md, dreams, docs) — never only in chat.
- The skill itself stays lean: principle-level lines over procedure
  bloat; reference files over SKILL.md growth.

## Preferences & Routines

- **Ask him less, and only where the answer is genuinely his** (human-set
  2026-07-28 05:35, folding #367's answer): *"instruct dreamwork agents to be
  more concise and keep to the most important topics. IGCs that only have one
  solution that is clearly superior don't need to be answered. If that belongs
  anywhere, let it be an aux document."* So a decision with **one clearly
  superior answer is not an ask** — decide it, record the reasoning in the plan
  or an aux document, and put only the genuinely open calls to him. Measured
  against the entry that produced this: of #367's four decisions, **M1 and M4
  were `rec`-and-taken** and should never have been asked, while **M2 and M3
  were overridden** and earned their place. Two of four is the ratio to beat,
  and the test before writing an ask is *"would I be surprised by any answer
  other than my rec?"* — if not, it is not a question.
- **The coordinator plans; subagents execute a written brief** (human-set
  2026-07-28 05:43, granting #263's lanes): *"I expect you main opus 5 claude
  orchestrator to do all the planning around this and to prepare precise
  instructions with measurable goals and acceptance criteria for your
  subagents. Idelaly write these to file so they are reusable in case of any
  issue and so you can show them to me."* Three requirements, and the third is
  the one that is easy to lose: the brief is a **file**, not a prompt — under
  `.dreamwork/docs/briefs/<id>-<slug>.md` — because a prompt dies with the
  dispatch and a file survives to be re-dispatched after a failure and read by
  him. Every brief carries **measurable goals and acceptance criteria**, not a
  description of the work; the test is whether a second agent could tell
  pass from fail without asking. Planning does not delegate: the coordinator
  writes the brief itself.
  · he asked for `xdg-open` on the briefs for #263 specifically, after
  dispatch — a one-off review, not a standing routine.
  · **and a brief must name a steering channel**, learned by not having one
  (2026-07-28 06:45): five lanes were dispatched with provably disjoint files, load
  hit 139 on 16 cores because one lane's brief correctly told it to generate load
  while another was measuring per-frame motion, and **I could not tell either of
  them.** A `ccc` lane reports on exit and reads nothing while running. So every
  brief for a lane longer than a few minutes names a file the lane **re-reads
  between increments** — the skill's `relay.py` writes it, and its rule is that
  steering takes two acts, write then wake. The thing worth saying mid-flight is
  usually something neither party could have known at dispatch, which is exactly
  why the channel has to exist before it is needed.
  · **but the channel is unreliable for anything mandatory, measured 2026-07-28
  09:12 — so it carries refinements only, and obligations go in the dispatch
  prompt.** `#389`'s lane read its relay and reported on it by name; `#395`'s lane
  never opened one written four minutes into its run, and the obligation in it
  simply did not happen. The discriminator is whether the lane's task decomposes
  into increments at all — a lane that treats it as one never reaches a boundary
  and so never re-reads — and **that is decided by the lane, after dispatch, and
  is invisible to the coordinator.** Worse, a missed steer is silent at both ends:
  "read it and judged it irrelevant" and "never opened it" look identical unless
  the report is scanned for evidence of receipt. So sort every steer by *what if
  this is never read*: if the answer is "the deliverable is incomplete", it is
  prompt material, not relay material. `#381`'s lane named this flaw hours before
  I tested it and I filed it as an aside.
  · **disjointness must cover the environment, not only files.** The loop's stated
  invariant is disjoint *files*; CPU, guard ports and the wall clock are shared, so
  a lane that consumes one is scheduled against the lanes that *measure* it.
  · **the general form, after a third instance 2026-07-28 09:31: "write X" is not
  "commit X", and in a shared tree an uncommitted file is one `git checkout` from
  gone.** The dream-file case below was the first two; the third was the `#394`
  hand-off line — the lane appended it and left it unstaged, which is precisely
  what the prompt said to do. **So every file a brief asks for appears in its
  commit paths, not only in its instructions.** The tell is an instruction phrased
  as an act of writing (`cat >>`, "append", "write up") with no path list beside
  it.
  · **and the brief must name the dream file among the paths to COMMIT**, not only
  among the things to write (2026-07-28 07:10): two lanes wrote a dream exactly as
  asked and both exited leaving it **untracked**, because every commit instruction
  named their code and tests. Untracked scratch is one `git add -A` or one worktree
  cleanup from gone, and one of the two carried a pattern claim — that this repo has
  now twice paid for a guard decoupling its click from its trace — which existed
  nowhere else.
- Cadence & comms: brief updates; `attn` (TTS) only for blockers,
  questions, and notable milestones. **Dreamwork decisions never use the
  harness Ask User Question tool** (human-set 2026-07-26): write the ask to
  `.dreamwork/questions.md`, say it is waiting on the dashboard, and continue
  the normal loop unless the dependency genuinely blocks all useful work.
- Subagent models (2026-07-26): use `codex-pooler/gpt-5.6-sol` with
  `thinking: low` by default; planning subagents use the same model with
  `thinking: xhigh` (the executable registry form of `pooler/gpt-5.6-xhigh`).
  **This line is harness-specific and names the pi registry** (scoped
  2026-07-27, when a Claude Code coordinator took this target over and found
  the two rules in conflict). Those model ids do not exist in Claude Code, and
  his global CLAUDE.md is explicit for that harness: *"Claude Code Agent tool
  and Claude Code workflows: use opus for all tasks. Never sonnet/haiku/other
  models — rework cost dwarfs token savings. Always pass the model
  explicitly."* So: in pi, the registry ids above; in Claude Code, opus,
  passed explicitly, every time. Recorded rather than silently resolved
  because a coordinator reading only this file would dispatch a model that
  does not exist, and one reading only CLAUDE.md would think this line was
  stale — it is neither, it is scoped.
- Autonomy: commit each increment (the skill folder is its own git repo).
  Push and deploy as needed (authorized 2026-07-26); neither needs a
  separate confirmation. **Commit messages are descriptive** (human-set
  2026-07-26): the subject names the concrete outcome and task id; the body
  explains why, load-bearing design/security decisions, and verification;
  add migration/config/consent trailers where applicable. Do not compress a
  substantial increment into an opaque one-line subject.
- Detail is ranked, never withheld (2026-07-25, his words): "in general
  we always want to present the user with more details if there are more
  details and users might want them." A thing that exists must be
  reachable — the page's job is to order it, not to decide he cannot
  have it. This is the same commitment the loop reached from the code's
  side as "nothing is dropped, only demoted" (#130), and it makes a fold
  a promise: what is inside is still there, and the summary says what.
- **One migration, not two** (human-set twice on 2026-07-27: 21:47 on `/tasks`,
  *"we might need to do multiple migrations unless we factor in the requirements
  of this task into sqlite task"*; 23:11 on #289, *"we should tie future versions
  into sqlite plan and/or redesign this to be done after sqlite"*). When a new
  design needs durable state, its requirements are folded into the pending
  storage migration's acceptance scope **at approval time**, and its own
  implementation either waits for the cutover or is shaped so the cutover
  re-points one seam. The thing to avoid is not the work, it is landing a
  pre-migration shape that must then be migrated again — paying twice and
  risking a second lossy conversion. Recorded because he has now said it about
  two unrelated features, which makes it a rule rather than a preference about
  either; the loop applies it without being asked again, and says in the fold
  which requirements it carried across.
- **Ask in plain terms** (human-set 2026-07-27 21:47, and it cost hours). Of
  seven design questions he answered in one go, six were "rec" — and the
  seventh got *"you'll need to explain what this means sorry."* The question
  was written in the loop's own vocabulary, so the only one he could not answer
  cheaply was the one asking him to learn the loop's jargon first. An ask is a
  request for his judgement, not a comprehension test: name the thing he would
  see or do, not the mechanism behind it, and if a term only exists inside this
  repo it does not belong in a question. The cost is not politeness — that
  question sat unanswered while the whole `/tasks` lane blocked on the batch it
  was part of.
- **The recommendation is the default, not the setting** (human-set 2026-07-27
  21:47, generalised from *"rec, but user configurable alongside filters"*). When
  he takes the loop's recommendation for a default, that is not a decision to
  hardcode it — it is the starting value of a control he expects to exist. And
  the control belongs beside the related ones he is already looking at, not in a
  settings page of its own. Same instinct as detail being ranked rather than
  withheld: the loop chooses the good default and still does not decide on his
  behalf that he cannot change it.
- **State the fact, do not hedge the claim** (human-set 2026-07-27 21:47). The
  loop proposed labelling an in-flight task as a *claim*, to be honest that the
  agent might have died. His answer: *"we don't need to draw attention to the
  fact it's a claim, we can just say that it's inprog and have a little box /
  tooltip on hover saying like 'Reported: Xm Ys ago'."* The honesty is carried
  by the **freshness**, not by the disclaimer — a timestamp lets him judge for
  himself, where "claimed" only tells him not to trust the page. Prefer a
  verifiable fact behind a hover to a word that shrugs; a UI that hedges every
  uncertain thing in prose teaches him to disbelieve all of it.
- Delegation routing (human-set 2026-07-27 21:40, superseding the 18:42
  no-native-subagents hold): **native subagents are allowed again for
  anything important or high risk; `ccc @glm52` stays the tool for easy
  work.** The 18:42 hold was a Claude Code 5h-limit measure, not a judgement
  about quality, and it is lifted. Route by stakes, not by habit: a visual-
  quality change on a surface he reads, a security or authority question, or
  anything where rework would cost more than tokens goes native (opus,
  always passed explicitly per CLAUDE.md); mechanical sweeps, conversions and
  small well-specified fixes go to `ccc @glm52`. He wants several agents in
  flight at once either way (18:50), so the routing is about which, not
  whether.
  - **SUPERSEDED 2026-07-27 23:14 — no more native subagents; `ccc @glm52` for
    everything.** His words: *"please do not start any more native subagents.
    but feel free to use more ccc glm52 ones. I updated it to be more performant
    a setup now."* So the 21:40 stakes-based split above no longer decides the
    harness — it decides only how much specification and how much coordinator
    verification a task gets. A high-stakes task now goes to `ccc @glm52` **with a
    correspondingly heavier prompt** (the design contracts quoted, the red-first
    and discriminating-red rules stated, ownership named file by file) and with
    the coordinator re-running its proof rather than reading its report. Agents
    already running when he said this may finish; nothing new is dispatched
    native. **Name the runner explicitly — `@oc-glm52`, not `@glm52`** — because
    `@glm52` resolved to opencode five times tonight and then to grok once, and
    the grok agent sat live and silent for twelve minutes with 127 bytes of log
    and zero writes.
  - **REAFFIRMED 2026-07-28 02:33, because the coordinator drifted straight back**
    (*"also please try to use more `ccc @glm52` subagents rather than native
    ones"*). This is the part worth recording, not the instruction: between 01:35
    and 02:18 the coordinator dispatched **three** native subagents while the
    23:14 rule sat five lines above in this file. Not disagreement — the rule was
    never re-read, because dispatching is the one action a coordinator does from
    habit rather than from a document, and each dispatch felt like a continuation
    of the last. So the drift is structural: **a routing rule that lives only in
    prose is re-checked exactly as often as someone happens to re-read the prose.**
    Until something checks it, the coordinator's own dispatch step must re-read
    this bullet, and a native dispatch needs a stated reason for not being
    `ccc @oc-glm52`. Agents already running when he said this may finish; nothing
    new goes native.
  - **CURRENT, set 2026-07-28 ~05:10 — two named runners and nothing else.** His
    words: *"I want you to try out being more of an orchestrator. You have two
    primary subagents available to you: `ccc @grok` and `ccc @glm52`. grok is
    multimodal (vision) but glm52 is not. your job is to use only those subagents and
    give them tasks to do as part of your dream loop. You can have up to 4 of each
    going at once. Primary differences: grok is much faster than glm52. depending on
    the situation, glm52 may be more capable consistently, though. You will need to
    experiment and get a feel for each by giving them tasks of different kinds and
    sizes. Also please not that we are dogfooding two thigns here, firstly what are
    hte best models and providers to use (for us), and second how does the dreamwork
    loop work for us with you as a coordinator rather than a dreamworker yourself?"*
    So: **`ccc @grok` and `ccc @glm52` only, up to four of each, and the coordinator
    does not implement.** The 23:14 rule's runner name is **superseded** — he fixed
    `ccc @glm52` mid-session on 2026-07-28 (*"note: i fixed `ccc @glm52`"*) and it has
    since completed five lanes, so **use `@glm52`, not `@oc-glm52`**; prefer the pi
    instance of glm5 over opencode, because opencode hangs on `/tmp`. A coordinator
    reading the bullet above without this one would dispatch the wrong runner, which
    is why this correction sits here rather than in a note.
    · **Two things are being dogfooded at once and they need separate records**: which
    runner to use for what (`.dreamwork/docs/dogfood-orchestration.md`, §"Runner
    routing"), and whether the loop works with a coordinator who only coordinates
    (same file, §"Notes on the orchestrator role"). He asked for notes on the second
    explicitly, so it is a deliverable and not a byproduct.
    · **measured routing so far, 10 lanes:** grok is much faster and is the right
    choice when the task needs *looking* at something (it is the multimodal one — a
    geometry or visual-quality measurement should go to it); glm52 is stronger on long
    verification chains and produced the best single piece of work of the day, but
    sweeps the space *around* its assigned chain less thoroughly, so pair it with a
    coordinator perimeter audit. Neither is reliably better; route by task shape.
- Subagent lifecycle (2026-07-25): **prefer fresh subagents; reuse an
  existing one only if it stopped less than ~4 minutes ago.** Retire
  idle dreamers rather than leaving them parked.
  - **The 4 minutes is a cost boundary, not a freshness preference**
    (human-set 2026-07-27 23:33, and it changes the decision): *"please do not
    reuse subagents that hhave been idle for more than 4 minutes, since there's a
    good chance we miss the cache -> expensive prompt of like 200k tokens. oof."*
    The rule above was recorded as *fresh eyes cost about the same*, which makes
    reuse-after-4-minutes merely unnecessary. His reason makes it actively
    expensive: past the window the prompt cache is gone and re-sending a
    dreamer's context is a ~200k-token bill for nothing. So the tie no longer
    goes either way — outside the window, spawning fresh is the CHEAPER act, and
    reuse needs a reason rather than an excuse. It also explains why he has been
    closing idle subagents himself (*"I have closed some idle subagents from time
    to time"*): prompt retirement is cost control, not tidiness, and leaving one
    parked is a standing liability the coordinator pays for on the next message. Exception/routine
  (human-set 2026-07-26): keep the named co-agent `grok-sugar-vesi-x6tv`
  usefully occupied whenever unblocked small/medium in-repo work exists with
  disjoint ownership; never manufacture busywork, violate a model gate, or
  skip coordinator validation. A dreamer here reached
  ~600k tokens because the coordinator accepted its own "I have room"
  three times — the incumbent is the party least able to judge its own
  context cost, so the call is the coordinator's.
- Routines: after structural edits, do a full coherence re-read of
  SKILL.md + initialization.md (this is the project's test suite).
  Periodically re-check this file against SKILL.md and recent decisions —
  goal alignment is maintenance, not a one-off. Groom
  `.dreamwork/questions.md` (fold answered entries). Keep any external
  index entries for this skill concise pointers — details live in the
  skill folder. Dogfood findings: fix immediately when small, file
  otherwise.
- Common tasks live in the `justfile`: `just test` (the verification
  every increment runs — there is no CI), `just watch`, and
  `just audit-styleguide`, which fails if any commit changed the page
  without updating the styleguide. The rule was already recorded; now it
  is checkable rather than remembered.
- watch.py webui: `watch-design.md` (skill root) is the authoritative
  styleguide — tokens, component idioms, and copy voice — and
  **`transitions.md` is the single source for how the page moves**
  (2026-07-25, his ask): every transition obeys it, appear/disappear/
  expand/collapse/state/movement alike, and the gist is that they are
  atmospherically suitable, like the transitions between pages. Read both
  before changing the page; keep them current in the same commit as the
  change. `CLAUDE.md` at the skill root carries the rule for anyone
  working on this repo.
- **A blocker that is his must always have a question he can answer**
  (2026-07-28 15:19, his words): *"we should structure things in such a way
  that it's impossible for us to be blocked on a user decision without a
  corresponding question ... either pending an answer/ruling, or that
  question could be answered but waiting for processing ... there always
  has to be an answer in our data for these kinds of questions."*
  So: **open, or answered-but-unfolded, are both fine; absent is not.**
  Saying "this is waiting on you" without an entry he can rule on is worse
  than not saying it, because he then believes he is blocking work he has
  no way to release. He found this by trying to rule on `#264` and finding
  nothing — the design had landed with its artifact and the ask was never
  filed. `#419` makes it a lint ERROR, which needs a machine-readable
  *blocked-on-human* marker first, since today it lives only in prose.
  Until that lands the guarantee is discipline, and he has been told so.
- **When a decision turns on a number, build it and measure it before
  asking.** `#367` went to him as *"option A costs ~214px"*; he asked to
  see the options rendered, and A measures **167.9px**. The 214 was
  arithmetic from a worst-case tab, never observed, and by the time it
  reached him it carried no trace of being derived. It was also the entire
  decision — 214-vs-32 in prose, 168-vs-32 in fact. A lane produced the
  measured previews in **thirteen minutes**. So a computed figure in
  anything he rules on **says that it is computed, in the same sentence**,
  and where the choice hinges on it, spend the thirteen minutes.
  His answer then improved on both options — C with a collapsible index —
  which he could only have seen with both on screen.
- **A research artifact is a kind of deliverable, not a note to himself.**
  His words via watch, 2026-07-28 16:29: *"get a subagnet to write a research
  artifact about how https://github.com/ayghri/i-have-adhd works (in terms of
  its instructions). Use that to create some options ... Then present those
  options to me as a question. also, we should support research artifacts in
  like `.dreamwork/docs/research/` or something. ideally HTML when they are
  user facing or benefit from visual expression."*
  Three things, and the first is the one easiest to skip: **he specified the
  method, not just the goal.** Research a named external artifact, derive
  options from it, put the options to him. A lane that reads the source and
  returns opinions has not done the task. Second, **the coordinator derives
  the options** — his 05:43 preference — and the lane supplies the material.
  Third, `.dreamwork/docs/research/` is the home, **HTML when user-facing**,
  which nothing builds or serves yet (`#422`), so research ships as markdown
  and the *options* ship as a review artifact through the existing pipeline.
- **The research is allowed to kill the premise, and that is the value.**
  `#421` was filed asserting *"three signals that our question format costs
  him"*. Measured: **19 of 56** entries carry two or more sub-decisions and
  **15 of 16** answered multi-part entries closed **complete**, often
  same-day on a bare `rec`. Durable partials: **2**. So *"ask one thing at a
  time"* is refuted by his own answering record, and it was the obvious port
  from the source he named. Recorded as rejected-with-reasons so nobody
  proposes it again.
  The defect that *is* measured is different and I would not have guessed it:
  **what we write is barely coupled to the size of what we are asking.** The
  two entries whose titles promise a *"one word"* answer are **300 and 448
  words**, both above the corpus median of **302**.

- **An agent must survive its own files changing under it, or be told to
  reload.** His words, 2026-07-28 17:38: *"the files on disk might be updated
  while agents are running, so they need to be able to continue running OR be
  explicitly told (via tooling or which files they read) that they must reload
  the skill and associated tooling like heartbeat, Monitor for user events,
  etc."* **Two acceptable states and no third** — continue correctly, or be told
  to reload. Running against a half-updated tree is what this forbids, and it is
  the default today: `SKILL.md` and `CLAUDE.md` are read once per session, so a
  change reaches nobody already running, and this session has been serving
  `watch.py` from a tree with dozens of commits under it. `.dreamwork/run-mode`
  is the only file with the right property today — re-read every tick precisely
  so an on-disk change reaches a running loop. Filed as `#426`; note that
  `#263`'s lane **H** solves the same problem for the journal, so decide whether
  they share a mechanism before building it twice.
- **A migration keeps the old path working for processes that already
  started.** Same message: when `watch.py` is split, the monolith moves to
  `deprecated/watch.py` and **`watch.py` becomes a symlink to it**, so *"clients
  won't break if the files on disk are updated before the new skill is rerun"*.
  This is a **constraint on `#368`**, not a follow-up to it — the split may not
  simply leave a smaller `watch.py` behind. Filed as `#425`, and it blocks `#368`.

## Plugins

- Load: `ud-dreamwork-hooks` (2026-07-28, **human-approved 02:47 — "sure, rec"**,
  asked as #361) — the compaction/lint hooks plugin #138/#156 shipped on 2026-07-27
  and nobody switched on. This line is the consent gate the plugin's own design
  requires: **both hooks re-check it on every invocation and skip silently without
  it**, so removing this line disables them without touching any config.
  - **Why it was asked for.** Two commits went through with a `lint.py` ERROR
    present, four hours apart, both because the lint run and the `git commit`
    shared one shell command and the error scrolled past above the commit's own
    output. `posttooluse_ledger_lint.py` lints `questions.md` and `tasks.md` **in
    the same turn as the write** — before any commit, while the agent that mangled
    the file still holds the context — which is exactly the window both slips fell
    through.
  - **Scope of the grant, read narrowly.** It authorises the Load line and
    reviewing `install.py --print`. It does **not** authorise `--apply`: the human's
    rec was *"add the Load line; I then show you `install.py --print` before
    anything is applied"*, so the printed diff goes to him and `--apply` waits for
    a second word. `--apply` is idempotent, takes a timestamped backup, and refuses
    to clobber.
  - **Claude Code only**, so it protects Claude lanes and does nothing for pi or
    `ccc` agents. Not a substitute for the discipline: never put a lint run and a
    `git commit` in one command.
- Load: `ud-dreamwork-worktrees` (2026-07-26) — explicitly requested by
  Max. Use bounded one-task worktrees for subagents and the same-host durable
  claim/inbox protocol for longer co-agents. The coordinator remains the main
  checkout's single writer and independently validates every receipt. Cross-host
  co-agent mode is not enabled until a durable relay adapter exists.
- Load: `ud-dreamwork-github` (2026-07-25) — the skill gained a forge
  presence (`git@github.com:ultradyn/dreamwork.git`, private), which was
  the recorded condition for revisiting. Its settings:
  - Watch: all open issues and PRs (the repo has neither yet).
  - Authority lines: none granted, so read-only — watch, capture, and
    progress locally; never touch the remote. Grant `comment`, `push`,
    `open-pr`, or `merge` by naming them here.
  - Auto-progress: on. gh-sourced items join normal selection like any
    other task; nothing about them is a private queue.
- Don't load:
