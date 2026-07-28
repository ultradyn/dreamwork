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

**Origin is recorded, never reconstructed.** Every entry from #216 onward
carries exactly one `origin: **human**`, `origin: **loop**`, or
`origin: **unknown**` in its metadata chain — `unknown` is the truthful
value for anything filed before the convention existed. Older entries
stay unmarked; history is not guessed. Contract: `file-formats.md`.

Next id: **469**

## Open
- **#460** — a tool that replays the `task_event` `.jsonl` log and reconstructs the database · **P3** ·
  tooling/recovery · origin: **human** · **blocked-on: #294** (which creates the log) ·
  **human via watch 2026-07-29 01:43, answering `#264` Q2:** *"We can add a future task (low priority for now)
  to write a tool to process this and reconstruct the DB. that way we know it'll work + we can run tests
  against fixtures and ensure determinism, etc. that will at least allow us to set a consistent rule for how to
  merge event streams."*
  · **he named the priority himself — low — and the reason it exists is not recovery, it is proof.** *"That way
  we know it'll work"*: a log nobody has ever replayed is a backup nobody has ever restored. The tool is how
  the `(c)` ruling stays safe.
  · **three properties he asked for, each testable:** replay is **deterministic** (same log → byte-identical
  DB, tested against fixtures); the log carries **enough detail** to reconstruct — which is the real
  acceptance test of `#264`'s log schema, not of this tool; and it establishes **a consistent rule for merging
  event streams**, which is what makes the future dreamhub multi-agent case tractable.
  · so this task is also the **falsifier for `#264`'s "capture enough detail"** — if replay cannot rebuild the
  DB, the log schema is wrong and that is a finding about `#294`, not about this tool.
- **#459** — two typing boxes keep no draft: `#askbox` and the popout `#ptext` · **P2** ·
  dashboard/durability · origin: **loop** (draftcheck lane, verifying `#269`) ·
  · **found while checking what draft durability actually covers** (`6a6ddff`). The review dock, the
  `/questions` answer boxes and the command composer all persist per keystroke and survive a process restart.
  **`#askbox` and the popout `#ptext` do not** — text typed there is lost on a reload, a route change or a
  redeploy.
  · **his standing rule makes this a defect rather than a gap**: *"we must have persistence and never lose
  work on an autoreload of a page"* is a property of **any field he can type into**, not of the boxes we
  happened to fix. `#askbox` is how he files a question; losing that is losing an ask before it exists.
  · **the mechanism already exists and must be reused, not re-authored** — `dw:adraft:<target>:<id>` /
  `dw:draft:<target>`, written on every input event, restored after render, cleared only on durable success.
  Read `.dreamwork/docs/draft-durability-status.md` first; it names the lines.
  · smaller than it looks, and **independent of `#269`'s IndexedDB upgrade** — do not wait for that.
- **#454** — questions collapse to a rolled-scroll card of 5-6 lines, persisted like other UI state ·
  **P2** · dashboard/asking · origin: **human** ·
  **human via watch 2026-07-29 01:06:** *"questions on the questions page should be collasible. However, the
  size of each collapsed question should be at least like 5-6 lines. So it's more like a card or the top of a
  rolled up scroll. This should be persisted to IndexedDB and kept in sync like other ui state."*
  · **the 5-6 line floor is the whole design, not a detail.** A one-line collapse is a title list, and a title
  alone does not say whether an entry still needs him — that is exactly the failure `#419`'s blocked-on marker
  and `#392`'s honest ages exist to fix. *"the top of a rolled up scroll"* is the shape: enough of the body
  visible to judge without opening, so **derive the floor from rendered line height at runtime** rather than
  pinning a pixel constant (`#441` split a shared literal for exactly this reason).
  · **machinery already exists for both halves and must be reused, not re-authored:** `#111` folds answered
  cards via `cardBody` and `#169` makes expansion grow padding, and the IndexedDB helper at `watch.py:2300` is
  already the persisted-UI-state path (with its raced-timeout handling for a wedged store — do not add a second
  one).
  · **transitions are the hard part and there is no exemption**: this is expand/collapse, so it obeys
  `transitions.md` and reuses `#111`/`#169`'s existing gesture. Note `#449` has just disabled the SVG mist for
  measured cost — **a per-card filter is therefore forbidden**, and this feature is precisely the "many
  filtered elements" shape he wrongly suspected of causing that jank. CSS blur/transform/opacity only.
  · **read with `#452`** (focus one question) — collapsing and focusing are two answers to the same complaint
  about a churning list, and whoever builds either should say why both are wanted.
- **#453** — restore the liquify with a moved or layered noise texture instead of two live SVG filters ·
  **P2** · dashboard/motion · origin: **human** · **blocked-on: #449** (which disables the mist) ·
  **human via watch 2026-07-29 00:53:** *"could we generate the flowingness by just having a single texture
  (which i presume causes displacement) and then just like moving it? or layering and having 2 interfering? we
  can also tile them or whatever too if that is cheaper."*
  · **this is the successor to `#449`'s temporary removal**, and the word *temporarily* in his 01:05 ruling is
  what makes it a real task rather than a wish. `#449` leaves the filters defined behind one named switch with
  its measurements beside them, so restoring is one edit once a cheaper mechanism exists.
  · **what `#449` measured, and the constraint it puts on this:** the cost was **not** noise regeneration
  (freezing `baseFrequency`, and freezing all six per-frame attribute writes, both measured ≈ baseline) and
  **not** filtered area (a 42% clamp changed nothing). It was **two SVG filter rasterisations per frame**
  contending with the shader — a threshold, since removing either alone bought nothing and removing both gave
  +128% frames. **So a cheaper texture is only a win if it removes a rasterisation, not if it merely makes one
  cheaper.** One cached field translated, tiled, or two layers interfering must be measured against that bar,
  not against the old animated filter.
  · **acceptance is comparative, on this host, in one run** — `#449`'s harness exists; reuse it rather than
  re-deriving a baseline, and state the numbers next to the ones it recorded.
- **#452** — focus a single question on its own page · **P2** · dashboard/asking · origin: **human** ·
  **human via watch 2026-07-29 01:04:** *"should be able to focus on a question, like open up to a page showing
  only that question. useful if other qs are being updated etc"*
  · **the reason he gives is the requirement**: the loop rewrites `questions.md` while he is reading it, so a
  list view can shift under him mid-answer — tonight `#449`'s entry was rewritten three times in fifteen
  minutes while he was looking at it. A focused page is a surface the loop's churn cannot move.
  · **route shape already exists to copy:** `/review?p=<artifact>` is the single-document view, and
  `crossfade()` treats it as a distinct body class. A `/question?…` route is the same pattern, so the work is
  identification (a stable per-question key) plus the view, not new machinery.
  · **the stable key is the real design question** — titles change (this one's did, twice tonight), so a
  title-derived key breaks the link exactly when the entry is edited, which is the case the feature exists for.
  `#269` settled a title-keyed logical id for drafts and `#294` plans `question_id`; read both before choosing.
  · **transitions apply**: entering and leaving a focused question is a route change and uses the existing
  gesture (`transitions.md`), not a new one.
- **#451** — authorisation asks are a distinct queue, surfaced in the title bar opposite the composer ·
  **P2** · dashboard/asking · origin: **human** ·
  **human via watch 2026-07-29 01:02:** *"when a question is just an authorization request, we should have a
  special queue for them and something in the title bar, maybe on the RHS mirrored to where the command
  composer is."*
  · **the observation behind it is real and measurable:** an authorisation ask carries no design decision — the
  design is settled and the only content is *may I build it*. `#254` was exactly this (*"Approve I1"* →
  *"yes"*), `#288`'s was one, and `#263`'s second gate is one. They are the cheapest asks to answer and they
  currently sit in the same list as multi-part design rulings, which is why they wait longest.
  · **read with `#445`** (four question/attention modes) — an authorisation queue is plausibly one of the
  artifact obligations those levels differ on, not a separate feature. Whoever designs either reconciles them.
  · **scope:** how an authorisation ask is *recognised* (a declared kind in the entry, not a guess from prose
  — `file-formats.md` is the contract), the separate queue, and the title-bar surface mirroring the composer's
  side. The mirror placement is his, stated; do not relocate it without asking.
  · **transitions apply**: a counter that appears or changes in the title bar arrives and departs — read
  `transitions.md` and reuse the existing idiom rather than authoring a second one.
- **#448** — a questionnaire feature for asking him things, modelled on `pag-server`'s question form ·
  **P2** · dashboard/asking · origin: **human** · **blocked-on: #294** (SQLite) ·
  **human via watch 2026-07-29 00:34, while reading `421-qs-opts-short.html`:** *"eventually we should add a
  questionnaire feature (after sqlite so we can rely on structured data). This can work like pag's (get a grok
  subagent to see ~/src/pag-server/ and look for the question form. it was quite feature rich. We should
  probably cut back on any superfluous elements."*
  · **explicitly sequenced after `#294`** — the point of waiting is structured data, so a questionnaire built
  on markdown-parsed `questions.md` would be the wrong thing built early. The survey of `pag-server` is *not*
  blocked and is worth doing now while the reference is fresh: `.dreamwork/docs/plans/questionnaire-survey.md`.
  · **read together with `#445`** (four question/attention modes) and `#421` — a questionnaire is the surface
  those modes would ask through, and *"cut back on any superfluous elements"* is the design constraint he
  stated up front rather than a later review note.
- **#466** — bundle the `subagent-protocols` skill with dreamwork, so a lane's two-way channel is part of the
  loop rather than a path a brief happens to name · **P2** · packaging/subagents · origin: **human** ·
  **human via watch 2026-07-29 03:45**, inside his `#445` answer
  · his words: *"they can talk to eachother via /subagent-protocols (another skill we should bundle with
  dreamwork, btw, please add that as a task)"* — said while ruling that **two agents may pair on a single
  worktree**, which is what makes the channel load-bearing rather than convenient
  · **why it matters now.** Every brief this session hand-wrote the path
  `/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md` and the handshake obligation, and a lane that
  never loaded it would have no inbox — the coordinator's only mid-task steering channel. A dependency stated
  in prose in each brief is a dependency that goes missing the first time a brief is written in a hurry
  · **this is the same shape as `#372`'s `use-igcs` bundling** — read them together and reuse whatever
  mechanism that lands, rather than authoring a second one · related: **#445, #372**
- **#467** — a `- **Answer …` bullet in a questions.md body truncates the parsed entry, so a `→ answered`
  marker written after it is invisible to every reader · **P1** · tooling/lint · origin: **loop**
  · **measured, 2026-07-29 03:50**, folding his `#445` answer: the marker was appended after his answer and
  `watch.answered_at` returned `None`. Cause: the dashboard writes his answer as `  - **Answer (via watch,
  …):**`, and entry splitting treats a `- **` bullet as a boundary — so everything after it, marker included,
  lands outside the body the readers see. Moving the marker **above** his answer line fixed it immediately
  · **this is `#411`'s family, third instance.** A marker dropped (`#264`, `#263`), a marker trapped inside a
  wrapped title, and now a marker orphaned past a nested bullet — each time the fold looked done, lint's
  date check was the only thing that noticed, and it only notices *absence*, never *misplacement*
  · **the fix is a check, not a habit:** if a body contains a `→ answered` marker positioned after a nested
  `- **` bullet, ERROR and say where it must go. Assert the precondition at runtime — the check is vacuous
  unless the fixture's marker really is unreachable, so derive that from the parser rather than trusting the
  fixture's layout · related: **#411, #366**
- **#468** — the lane-containment backstop, and the briefs that predate the rule · **P2** ·
  tooling/lane-safety · origin: **loop** · successor to `#465`, named in its design doc
  · **two halves, both small.** (1) **R2, the pre-merge assertion**: walk the main tree's *dirty* paths,
  enumerate live worktrees, report when a path no lane owns is dirty in the main checkout while a lane is
  out. `#465` catches a commit; this catches an edit that has not reached one, which is the state that
  aborted the held `#263` merge. (2) **retro-fit `Lane-owns:`** — `#465`'s check grandfathers every brief
  written before the rule, and that is **all 101 of them**, so the guard protects nothing until a brief
  declares ownership
  · **do not make the loop's own commits harder** — the constraint that shaped `#465` binds this too
  · related: **#465**
- **#445** — question/attention modes: four named levels for how much the loop asks, each with a defined
  artifact obligation, plus a subagent target and policy · **P1** · loop-design/asking · origin: **human** ·
  **human via watch 2026-07-28 23:40, dictated at length while reading `421`** — the full text is in
  `.dreamwork/watch-events.log` at that timestamp and is the authority; this entry is a structuring of it, not
  a replacement
  · **this is the answer to `#421`'s question arriving as a design rather than a choice among my four options**,
  and it supersedes the shape of that ask. It is also the second axis of `#443` (run modes conflating pace with
  delegation) — read the two together; **whoever designs either must reconcile them or say why they stay
  separate**
  · **the four levels, in his order.** (1) **ask me everything** — any non-trivial design or architectural
  choice produces a review document and *he* chooses between the options; *"probably a bit more than you've
  been asking me, but you do ask me a lot of stuff"*. (2) **keep me informed** — mostly automatic, but each
  material choice emits **documentation rather than a question**: what the choice was, why a choice was
  needed, the details, a brief note on the other options, and the evaluation table. *"a review in the sense
  that it's for the human's review, but it's not asking them for a choice — so it's a bit different to what we
  have now."* He put a number on it: **~10–20% of questions escalate**. (3) **near-automatic** — the
  evaluation is still done and **logged to a journal folder** (ADR-shaped), but nothing is surfaced unless it
  is genuinely big or he is stuck; *"it's too much in the noise to actually surface"*. (4) **full auto** —
  *"tasked with figure it out"*; every blocker is the loop's to solve, never blocked on a reply
  · **the obligation that runs through all four: the IGC evaluation.** Level 1 *always shows it to him*, level
  2 includes it in the emitted document, level 3 logs it without surfacing. **`IGC` is now DEFINED and this no longer
  blocks** (2026-07-29 00:33, his pointer to the `use-igcs` skill; vendored by `#447` as `igc-method.md` +
  `igc-concepts.md`): **(Idea, Goal, Context)**, the Critical Fallibilism method — per (idea, goal) in a stated
  context, `✔` non-refuted / `✘` refuted with the decisive error written out / `?` a TODO, an `All` rollup,
  breakpoints instead of maximisation, and **never a score**. So "the evaluation table" in every level means an
  IGC matrix, and `SKILL.md` already instructs it at four judgement sites
  · **the rule about not-material choices**, which is what makes level 2 workable: *"some choices where you
  have multiple good options … are not very material. It doesn't really matter to the user's goals. You can
  just make a choice in that regard … unless the user has specifically mentioned something."* So the escalation
  test is **materiality against his goals**, not difficulty
  · **before declaring yourself stuck, research first**: *"you should always use a subagent to research the
  question, see if anyone's solved it before, what the options are."* Stuck is a state you have to earn
  · **and the deepest part, which belongs in `DREAMWORK.md` regardless of what gets built**: when uncertain,
  **ask about his goals rather than about the immediate decision** — *"if you know about their goals, you can
  evaluate not just the current answer … but you can also do that for many other questions."* Uncertainty
  usually means the goals need to be more specific. This is the skill's own *"unclear is a goals problem"*
  stated as an operational instruction, and it should be folded into `DREAMWORK.md` as a durable preference
  · **level 4's cooperation clause is explicit and must not be lost**: *"you still want to cooperate with the
  user … but you never want to be blocked just because the user hasn't replied or because you don't have
  access to something."* Raise the unblocking question **as early as possible**, keep working while it is
  unanswered, and do not go down a rabbit hole while other work exists. His worked example: don't buy a domain
  for a project that already has one, but do ask *"do we have a domain?"* early and cheaply
  · **the configuration also carries subagent policy**, and he specified the shape: a **target number** of
  subagents plus **free text** for type, special rules, when to use them and when not. Validation: `>= 1`,
  **warn in the UI on 0**, **hard-invalid below 0**. Free text now, standardise later if ever. Two consumers he
  named: sizing automatic task selection to the target, and **showing the subagent policy to the agent every
  time** — which makes it a per-tick read like `run-mode`, not a start-up read (`#426`)
  · **design first, and it needs an artifact with an `#ask`**: the level names, where the config lives, and how
  it composes with `run-mode` are all his calls. **Do not change `.dreamwork/run-mode`'s closed set or
  `file-formats.md` before he rules** — and note the `IGC` question above is a blocker on the artifact, not on
  the design discussion
  · **blocked-on: **human** (define `IGC`; then rule on the composition with `#443`)**
  · related: **#443, #421, #438, #426, #466**
  · **DESIGN LANDED `0eea21c`, merged `1462aeb` — and it STAYS OPEN, because a design is not a ruling.**
  `.dreamwork/docs/plans/attention-modes.md` plus the artifact `.dreamwork/review/445-attention-modes.html`;
  built no mechanism, as the brief required — no `watch.py`, no tick-read file, no change to `run-mode`'s closed
  set
  · **the reconciliation with `#443` resolved to THREE orthogonal axes: pace × asking × delegation.** The
  decisive error against one combined enum is concrete and it is *this session*: a single level drags pace and
  delegation with it, so *"lackadaisical but delegating"* — his own instruction tonight — is unexpressible, and
  that is precisely why `#443` was filed. Two axes fail too: asking (what surfaces to him) and delegation (who
  does the work) are independent and neither derives from the other. A per-task override survives as an
  *addition* to three axes, never a substitute
  · `#443`'s existing values decompose cleanly — `lackadaisical` → idle pace, `hot` → hot pace + own hands,
  `assisted` → hot pace + subagents — and the combination that has no name today (idle pace **with** subagents)
  becomes expressible, which is the test the design had to pass
  · each level fixes four things: what surfaces, what is emitted, where it is logged, and **what happens if he
  never replies** — L1 blocks on him by design, L2 parks nothing (a document is not an ask), L3 proceeds and
  *earns* stuck by researching first, L4 never blocks and keeps working the unanswered question in the
  background. The ~10–20% escalation figure is recorded as a **soft estimate that steers**, with no counter that
  gates, per his 01:17 ruling
  · **the escalation test is materiality against his goals, not difficulty** — a design that escalates by
  hardness escalates the wrong things
  · **artifact verified by me, not folded from the report**: exactly one real `#ask`, both build-time metas
  present, no stray `>` in the head (the `#457` regression), and the IGC table carries `table-layout:fixed`
  through a class selector because the template's bare-`table` rule would otherwise win — the same pattern
  `#421` proved after a 4197px table shipped and he could not read it
  · **asked 2026-07-29 02:42 with three declared sub-decisions** (`Q1` the three axes, `Q2` names + where the
  asking axis lives, `Q3` the subagent target and policy shape) · **blocked on his ruling**
  · **HIS RULING, 2026-07-29 03:45 (via watch) — Q1 `rec`, Q2 amended, Q3 amended.** The three orthogonal
  axes (**pace × asking × delegation**) are ratified. **Q2:** widening `run-mode` into a multi-field file is
  approved *in principle but deferred* — *"we don't need to do that yet. We can just convert the current modes
  into the new values"*. So the first increment is a **vocabulary conversion**, not a format change: today's
  three values are re-expressed as points in the new space, and **each axis gets its own control** with about
  **three stops** — *"IDK that I will leave up to you, but we get 3 dimensions of input is the point"*, so the
  stops are the loop's call and the three dimensions are not. **Q3:** the subagent number is an
  **average-concurrency target, not a cap or a quota** — `0` means *occasional*, i.e. a subagent when one is
  necessary or a particularly good choice (average below 0.5 running); `1` means an average strictly between
  0.5 and 1.5; and so on. Interdependent work still governs, and **two agents may pair on one worktree**,
  coordinating through `subagent-protocols` (`#466`)
  · **no longer blocked-on human** — the design is ratified and the axes are settled; what remains is
  implementation, and it starts with the conversion plus the controls
- **#443** — run modes conflate PACE with DELEGATION POSTURE, so there is no way to say *"idle-friendly, but
  use subagents"* · **P1** · loop-design/run-mode · origin: **human** · **human via watch 2026-07-28 22:18**
  · his words (dictated, lightly punctuated): *"We need to rethink how the Run modes work. Because when,
  like, we need ways to say, like, be lackadaisical, but also use sub-agents. So we need a good — I guess
  like a good — yeah, good way to do that. We need to think about how we're gonna structure this and
  restructure it from first principles so that it works and it works well."*
  · **the defect stated plainly.** `.dreamwork/run-mode` (`#290`) is one line from a closed set —
  `lackadaisical` / `hot` / `assisted` — and that single axis is carrying at least two independent
  decisions: **how often the loop acts** and **whether it acts through subagents.** `assisted` is the only
  value that implies helpers, and it also implies a pace, so *"lackadaisical but delegating"* is
  unexpressible. Tonight's session is exactly that state — he asked for low activity **and** for all work to
  go through subagents — and it was held in conversation rather than in the file, which means it does not
  survive a restart or a compaction
  · **first principles, as he asked**, and the axes to argue about rather than assume: (1) **pace** — how
  eagerly the coordinator starts new work; (2) **delegation** — coordinator's own hands vs subagents, and how
  many at once; (3) **quota posture** — what to spend, which tonight was the *reason* for the mismatch and is
  arguably its own axis rather than a consequence of pace; (4) **autonomy** — how much lands without asking.
  Whether these are four axes, or two axes and two derived values, is the actual design question
  · **what must not be lost.** `#288` is explicit that a run mode grants **no kill or sandbox authority** on
  its own, and `#290`'s file contract is load-bearing: gitignored, machine-local, re-read every tick, written
  by the dashboard behind a 10s arm with one events line on change. A richer mode must keep *re-read every
  tick* — that is the only property that lets an on-disk change reach a running loop (`#426`), and it is why
  `run-mode` is the prior art the reload design points at
  · **the closed set is the thing under review**, so `file-formats.md`, `watch.py`'s parser, the dashboard's
  composer control, and `SKILL.md`'s selection posture all move together — and a wider grammar has a
  migration cost for existing installs (`Migration:` trailer)
  · **design first, with a review artifact and an `#ask`** — this is a restructure of a contract he set and
  the axes are his call, not the loop's. Do not change the file format before he rules
  · **blocked-on: **human** (after the design lands)** · related: **#290, #288, #426, #438, #445**
  · **RESOLVED BY `#445`'s RULING, 2026-07-29 03:45.** The conflation is settled as **three** axes — pace,
  asking, delegation — not the four this entry proposed: **quota posture** collapses into delegation plus pace
  rather than standing alone, and **autonomy** is the asking axis under another name. The file format does not
  change yet (his Q2: convert the current values into the new vocabulary first), so `#290`'s contract and the
  *re-read every tick* property survive untouched for now. **No longer blocked-on human**
- **#438** — a generic scheduled-tasks facility, so maintenance and inbound-scanning work is filed rather
  than done ad hoc · P2 · feature/scheduling · origin: **human** · **human via watch 2026-07-28 20:34**
  · his words: *"we should add support for task scheduling (probably managed through dreamhub). central
  idea is that we can use this for maintenance jobs and things like scanning github for issues/prs and
  adding tasks to process them (those workers shouldn't process directly). so this is basically a generic
  scheduled tasks / cron style implementation. When we do design it, we should make sure that it's
  compatible with best practices and user-scheduled tasks (like can they set a cron-job on a server to
  start a dream worker) and that kind of thing. Will require some brainstorming, but we can leave that
  for after 9pm when quota resets."*
  · **the load-bearing constraint is his parenthesis**: a scanning worker **files** tasks, it does not
  **process** them. That keeps the ledger the single arbiter of what gets worked on, and it is the same
  single-writer rule the queue already runs on — a scheduled job that acted directly would be a second
  writer with no id, no origin marker and no reflection beat
  · two audiences that must not be conflated: the loop's **own** maintenance rotation (already a concept
  in `SKILL.md`) and a **user-scheduled** entry point (an operator's crontab starting a dream worker on a
  server). The second implies a headless start path with no interactive human, which is where the
  answers/questions channels stop working and something has to give
  · **brainstorm-gated, deliberately**: he asked for the design conversation to wait for the quota reset
  after 21:00, so this is filed now and designed then. Do not start building it
  · **blocked-on: **human** (brainstorm scheduled after 21:00 2026-07-28)**
  · related: **#443, #445**
- **#439** — the staleness banner says the page is behind but offers no way to act on it · P2 ·
  watch-ui/deploy · origin: **human** · **human via watch 2026-07-28 20:34**
  · his words: *"re: \"this page is 2 watch.py commits behind · serving bfc3222\", we should have after
  that a link/btn like 'update & refresh' that triggers watch.py to shutdown + self-reload (this should be
  made as a proper python module in preparation for refactoring all the python code to something more
  modular and maintainable)."*
  · the banner exists because `deploy_state.py` already answers *is the file right* and *is the process
  running that file* separately, and `#426` has just added `skill_identity()` alongside it — so the
  **detection** half is done and this is the **action** half
  · **two pieces, and the second is the larger one.** (a) the control: a button that triggers the
  shutdown+self-reload, which `watch.py` can already do via `os.exec` with its `GENERATION` stamp
  re-set. (b) his stated purpose for it: **`watch.py` becomes a proper python module**, as the first step
  of making the python side modular. (b) is a refactor of a 6,000+ line file and wants its own entry once
  scoped — do not smuggle it in behind the button
  · **`transitions.md` binds**: the banner changing state, the button appearing, and the page coming back
  after a reload are all transitions with no size floor. The reload especially — a page that vanishes and
  reappears is the largest gesture on the surface and must not be the one that snaps
  · related: **#431**
- **#428** — the guard suite fails under concurrent lanes and passes alone, twice now · P2 ·
  loop-tooling/orchestration · origin: **loop** · found by the coordinator's own suite run at 17:29
  · **`subslog` FAILED in the full run** on *"…and says so, with the status the server gave"*, with
  **three `ccc @glm52` lanes running**. Re-run alone at 17:47: **PASS**. Result: 51 PASS / 1 FAIL,
  `REAL_EXIT=1`, pytest **1028 passed**
  · **second instance today with a different guard.** The `#218` lane reported *"failing guards on an
  idle machine — `confirmation`, `identity`, `morphhold`, `prominence` all flipped to PASS, and `qsec`
  failed on a different assertion, the hallmark of load sensitivity"*. Different guards, same shape
  · **be careful what this claims:** *"passes in isolation"* is **not** proof of load sensitivity — it
  is equally consistent with order-dependence or an ordinary flake. What is established is that it fails
  under concurrent load and passes alone, twice, on timing-shaped assertions. **Establishing the cause
  needs the experiment, not the inference**: run the suite alone N times and under synthetic load N
  times and compare failure rates
  · **third instance, 2026-07-28 18:22 — six guards, and the sample is now big enough to describe.**
  `morphhold`, `qsec`, `history`, `plugcmd`, `reviewsplit`, `runmode` failed; pytest clean, lint clean,
  `REAL_EXIT=1`. **Every single failure is a frame-sampling assertion** — *"eases in rather than blinking
  on (distinct part-way opacities)"*, *"the column travels there rather than snapping"*, *"the morph
  glided through the hold"*, *"the guard threw before finishing its checks"*. Those are assertions that
  motion **happened**, and the way they fail under starvation is that the sampler misses the
  intermediate frames and the transition reads as a snap. **The failing set is not random across the
  suite; it is the subset that samples per frame** — `burndown`, `provenance`, `subslog`, `qorder`,
  `revieworder`, `serving`, `gitrow`, `hfit`, `contract` all passed in the same run
  · **and this run does not answer the experiment either, because I broke its isolation myself.** I
  dispatched the `#425` lane mid-run rather than waiting, so it is a third *contended* data point and
  not the controlled arm. Recorded as such rather than counted as evidence — the experiment above still
  needs running, and doing it accidentally three times is not doing it once deliberately
  · **all 6 flipped to PASS in isolation, 19:00-19:05** — `morphhold` and `qsec` together, then
  `history`, `plugcmd`, `reviewsplit`, `runmode` together, same commit, same machine, no lane running.
  **6 for 6**
  · **but that is not yet the experiment, and the reason is worth keeping.** The isolated runs differ
  from the failing run in **two** ways, not one: no concurrent lane **and** a 2-or-4-guard suite instead
  of the full 50. So the result is equally consistent with *"a concurrent lane starves the sampler"* and
  with *"the full suite starves it by itself"* — and **those have opposite remedies**: serialise lanes
  around the suite, versus fix the suite. Running the guards in small groups is exactly the confound the
  entry's own caution was about, and I walked into it once before assuming
  · **so the missing arm is running: the FULL suite on a verifiably idle machine**, started 19:06. If it
  goes green, concurrent lanes are implicated. If the same frame-samplers fail with no lane in sight,
  `#424`'s lock is not the problem and the suite is
  · **an aside that cost me a deploy today**: my own idle-check `pgrep -af 'ccc --yolo'` matched **its
  own shell**, because the pattern was in the command line doing the matching. Same shape as `#431`'s
  `pkill`. A process-pattern check must exclude itself or it can never report zero
  · **the failures grew as the run progressed** (2 at guard 29, 5 at guard 40, 6 at the end), which is
  what a load-dependent cause looks like and is not what order-dependence looks like. Weak evidence,
  stated as weak
  · **why it matters beyond flakiness:** this is the third structural cost of fan-out after `#424` (the
  guard range is one lock) and `#423` (a dead runner looks like a fast lane). A suite that goes red
  because *we* are busy trains everyone to discount its reds, which is the expensive failure — and the
  `#218` lane already discounted five of them correctly, which is exactly the habit that will one day
  discount a real one
  · **fourth run, 2026-07-28 19:06 — and I broke its isolation a fourth time, by the same act.** I
  dispatched the `frame` and `rail` lanes at ~19:15 while the run I had just called *"the missing arm"*
  was at roughly guard 20 of 50. So it is a fourth contended point, not the controlled arm. **The
  failure is not the dispatch — it is that I have now written the words "the experiment still needs
  running" four times and started a lane through it every time.** The experiment does not need designing;
  it needs a coordinator who will sit still for fifteen minutes
  · **what it did show:** 2 failures where the contended 18:22 run had 6, and **both are frame
  samplers again** — `morph` (*"…and still ends up in the same place"*) and `reviewsplit` (*"…having
  faded away rather than switched off"*). Four runs, every failure in the sampling subset, zero outside
  it. That pattern is now well-established independently of the load question
  · **careful about the probe I then armed, because it repeats the entry's own warning.** Re-running
  `morph` and `reviewsplit` alone is the 2-guard shape this entry twice calls a confound, so **a green
  tells us nothing we did not know at 19:00 (6 for 6 alone)**. Its value is one-sided: only a **failure
  alone on an idle machine** is informative, and it would be decisive — the guards would be broken and
  `#424`'s lock exonerated. Recorded before reading the result so the read cannot drift
  · **the arm still missing, stated as a procedure rather than an intention:** full 50-guard suite, no
  lane dispatched from suite start to `REAL_EXIT`, idle verified with a **self-excluding** process check
  (see the `pgrep` aside above), repeated until the failure rate is a number. Everything else is a
  fourth anecdote
  · related: **#424, #423, #442**
- **#424** — `just test` is a single shared lock, so N concurrent lanes cannot each verify · P2 ·
  loop-tooling/orchestration · origin: **loop** · found when `#419` reported guards blocked at 17:01
  · guards bind **39890-39899** and the recipe hard-aborts if any port in the range is held (the
  `#203` trap, and that abort is correct). So with four lanes live and every brief instructing
  *"then `just test`"*, **at most one lane can ever run it** — the others either wait indefinitely
  or report a blocked suite. `#419` waited, refused to force-kill, and said so; the reaper also
  refused (correctly — I checked, the holder's parent `just guards` was alive and writing)
  · **the brief's instruction is therefore unsatisfiable at fan-out and I have written it into five
  briefs today.** *"Check `ss -ltnp | grep 3989` and say if you waited"* tells a lane how to notice
  the collision and nothing about what to do for the next fourteen minutes
  · options: **(a)** a per-lane port range derived from the worktree name, so four lanes get four
  disjoint decades — needs the range to stop being a constant; **(b)** the coordinator owns `just
  test` and lanes run `pytest` + `lint` only, verifying guards once at merge — cheapest, and it
  matches who actually merges; **(c)** a lock file with a queue, which serialises honestly but makes
  a lane's wall-clock unpredictable. **Rec: (b)**, with the brief saying so instead of asking a lane
  to wait
  · this is a **dogfooding finding about the orchestrator mode itself**, which is the second thing
  he asked to be measured — parallel lanes are cheap until they share a lock nobody modelled
  · related: **#203, #423, #428**

- **#423** — `ccc @grok` 401s recur, and the loop has no signal for a dead runner · P2 ·
  loop-tooling/orchestration · origin: **loop** · **recurrence of landed `#410`**
  · grok was 401 from **05:52 to 14:50** (his fix), worked for three lanes, then went 401 again at
  **~16:50**. Probed twice, identical: `auth_kind=none … reason=no auth context`. Asked at 16:54
  · **the loop-side defect, which is ours and not his:** a dead runner looks exactly like a fast
  lane. `nohup ccc … &` exits **0** on a 401, the worktree stays at the branch point, and nothing
  reports. I found this one only because the pid vanished from `pgrep` sooner than a real lane would
  · so: a dispatch should **probe the runner first** (one cheap `PONG` round-trip) and a lane that
  exits without committing or writing to the inbox should be **recorded as failed**, not silently
  forgotten. `status_sync`'s liveness work (`#402a`) already knows how to ask whether a pid is
  alive; it does not know how to ask whether a lane *did* anything
  · **third instance, 17:45, and it is the worst shape yet because the work existed.** The `gate2`
  lane (`@glm52`) rebuilt the `#263` artifact correctly, ran 24 turns, and **exited without
  committing**. `git log master..wt/gate2` was empty and the worktree HEAD equalled master, so by
  every signal the loop watches the lane had done *nothing*; the edits were sitting unstaged in the
  worktree and would have been destroyed by a routine `git worktree remove`. Recovered by hand and
  committed on its behalf (`da197b8`). **So the missing signal is not "did the pid die" but "is the
  worktree dirty at exit"** — one `git status --porcelain` per finished lane distinguishes *crashed
  before working*, *worked and did not deliver*, and *delivered*, and only the middle one is
  recoverable-but-invisible. Fold that into whatever `#423` builds
  · related: **#410, #402, #424, #428**

- **#422** — a research artifact is a kind we produce and have never specified · P2 ·
  loop-tooling/format · origin: **human** · **human via watch `do-next` 2026-07-28 16:29**, second
  half of the same message
  · verbatim: *"also, we should support research artifacts in like `.dreamwork/docs/research/` or
  something. ideally HTML when they are user facing or benefit from visual expression."*
  · **the directory already exists and the documentation says otherwise.** `.dreamwork/docs/research/`
  holds one file (`2026-07-28-parallel-lanes-evidence.md`) while `doc-map.md:25` documents the flat
  form `.dreamwork/docs/research-*.md` — and a third file, `research-window-coords.md`, sits at
  `docs/` root in that flat form. **Three spellings of one kind**, so the convention is not a
  convention yet
  · **the HTML half is the real gap.** `review_artifact.py` builds and checks templated HTML and
  `watch.py` lists and serves it, but **only under `.dreamwork/review/`**. A user-facing research
  doc has no path to a rendered page today, which is why `#421`'s options will ship as a *review*
  artifact even though it is research
  · so: decide whether research HTML reuses the review pipeline (a second listing surface, one
  builder) or gets its own, document the directory + naming in the doc-map **and** `file-formats.md`
  if a tool will parse it, and say what distinguishes research from a measurement
  (`.dreamwork/docs/measurements/`, also undocumented there) from a plan
  · blocked on nothing · related: **#421**


- **#415** — the hand-off grammar allows ONE sha, and a task landing in two commits is the
  ordinary case · P3 · loop-tooling/format · origin: **loop** · found when the `#411` lane
  reported honestly and lint called it malformed
  · **what happened.** `#411` landed as `54c68e8` (the fix) + `25a3fe4` (the lint count), so the
  lane wrote `· landed \`54c68e8\` \`25a3fe4\` ·`. `file-formats.md:246` specifies
  `· landed \`<sha>\` ·` — singular — so `lint` reported *"a hand-off entry the grammar does not
  recognise"*. **The lane was right and the format was wrong**: two commits is what the work was
  · normalised by hand to the final sha with the other in the prose, which loses the structure —
  a tool can no longer find the first commit, only a human reading the sentence
  · **this is `#401` one field over.** That task widened the hand-off *id* vocabulary to accept
  plain / sub-id / combined because the loop's ids were richer than the grammar. The *sha* field
  has the identical defect and the same fix shape: accept a run of backticked shas, keep the
  first-and-last distinction if it is worth anything, and state it in `file-formats.md` in the
  same commit
  · **the cheap red is available without an injection**: today's `#411` line, before
  normalisation, is a real failing input — put it in the fixture and assert the grammar accepts
  it, then narrow the pattern back to one sha and watch it fail
  · low priority: the WARN is loud, correct, and the workaround is one edit. Filed so the next
  two-commit lane does not rediscover it — this is the third time today a lane has been marked
  wrong by a checker that was itself too narrow (`qacard`, the dock guards, now this)
  · related: **#401, #367, #427**
  · **a second instance of the same narrowness, found 15:10 and worth folding in here rather than
  filed separately:** `lint` cannot tell a merge that lands an *increment* of a multi-increment
  task from a merge that *closes* it, so `#367` — open by design, awaiting his ruling — reports as
  *"under `## Open` but git already has a close/merge commit"*. The hand-off grammar has the
  matching gap: `· landed \`<sha>\` ·` says *landed*, with no way to say *increment 2 of n
  landed*. Both are the same missing distinction, so whoever widens the sha field should widen
  this too
  · **IN PROGRESS 2026-07-28 17:03** — folded into the `#402b` lane (`ccc @glm52`,
  `.worktrees/fmt`), because both widen a grammar in `file-formats.md` + `lint.py` and both have a
  live symptom. The brief leans hardest on the **negative** tests: a widening's easy failure is
  accepting everything, and one with no negative test has removed a check rather than improved it
  · **DONE lint-local, `4c70722`, `ccc @glm52` (merged 17:47) — and the lane found the scope I got
  wrong.** The hand-off grammar lives in **`watch.py`'s `HANDOFF_PENDING_RE`**, which my brief listed as
  not-yours, and `parse_handoffs`' return shape is asserted on in `test_watch.py`. So it widened
  **`lint.check_handoffs`** instead: multi-sha lines are reclassified out of the parser's `malformed`
  bucket and counted separately. Red from the **real** `#411` line recovered from `f7d5bea`, not a
  fixture; negative test keeps a zero-sha line malformed
  · decisions, all in `file-formats.md`: order is **written-order, not enforced** (a hand-off is a
  report; `Recently landed` is where order is recoverable from `git log`), **no cap** (capping
  reintroduces the defect), **zero-sha stays malformed** (the delivery signal would be empty)
  · **REMAINDER, and the lane named it rather than leaving it to be discovered:** `parse_handoffs`
  still returns a multi-sha line as malformed, so `pending_handoff_records` **will not surface its
  shas on the dashboard** until `watch.py`'s grammar widens too. Filed as part of `#427`

- **#409** — two hand-offs for the same id: folding **either** silences **both**, and it is live
  right now · P2 · handoffs/correctness · origin: **loop** · **predicted by the `#401` lane in its
  neighbour table and not filed by it; found in the tree one minute later**
  · `pending_handoff_records` hides a pending line whose id is in `folded_ids`, and correlation is
  **by id alone** — so a second landing under the same id is suppressed by the first one's fold. Not
  hypothetical: the live file has **`#401` pending twice** (`f2c950e`, the audit half, and `e53d70c`,
  the fix half) and folded **once**. The fix-half landing is invisible to the dashboard
  · **it is the append-only design's own logic turned against it.** Nothing moves, so both lines
  persist; a fold marker is a bare id token with no sha, so it cannot say *which* landing it
  consumed. Every part of that is deliberate, and the combination loses a landing
  · **and it is the ordinary case, not an exotic one** — a task landing twice is exactly what an
  audit half plus a fix half looks like, which is how this repo splits work
  · rec: **correlate a fold by `(id, sha)`**, not by id. The sha is already in the pending line and
  every fold line already cites one in prose (*"citing `f2c950e`"*), so the data exists and only the
  parser ignores it. The honest cost is migration: existing fold lines carry the sha in **prose**,
  not in a parsed field
  · **the red is in the tree and needs no injection**, as `#406`'s was — but prove it before tidying,
  and **do not let a fold note claim a state nobody re-checked**; that mistake cost the last lane a
  restore step
  · related: **#401, #381**

- **#407** — `/questions` has **no** timed ages, so the one-figure precision signal has nothing on
  the page to be read against · P3 · dashboard/design-rationale · origin: **loop** · found by
  measuring the deployed page while verifying **#392a**, not by reading the design
  · `watch-design.md` justifies the one-figure form as *"the MISSING second figure is the signal,
  **read against the timed entries beside it**"*. Measured on the live page: **38 of 38** age nodes
  are day-precision and the timed sample is **empty**. There are no timed entries beside it
  · **the rendering is still honest** — that is the point of `#392a` and it holds; nothing claims
  precision it lacks. What is inaccurate is the **stated rationale**, and a rationale is what the
  next lane reasons from
  · the contrast is real **across** surfaces (a commit's age elsewhere shows two figures) and absent
  **within** this one. So a reader who does not already know the convention cannot infer precision
  from `/questions` alone; they infer it from the styleguide
  · **this is the caveat-holds-an-axis-fixed shape**: the design varied *precision* and held
  *page composition* fixed, and the defect is in the axis held fixed
  · smallest fix is one sentence in `watch-design.md` saying the contrast is cross-surface. The
  larger question — whether a page of uniformly day-precision ages needs any signal at all — is
  worth asking before writing that sentence
  · related: **#392**

- **#404** — for a same-tree lane, `git log` is a strictly more reliable landing channel than
  `handoffs.md`, and the tick reads the weaker one first · P2 · loop/design · origin: **loop** ·
  found by **noticing I had already run the experiment** — I learned of two landings from `git log`
  while looking for something else, and only then checked the hand-off file, which was empty
  · **the evidence, unplanned and therefore worth more:** `#392a` (`159917b`) and `#397` (`1b508b0`)
  both landed. I discovered both from `git log --oneline`. `handoffs.md`'s `## Pending` named
  neither — it still held only `#398`'s line
  · **the obligation was in the dispatch prompt**, not a relay — the fix `#398` exists to enforce
  and which was measured working once. So prompt-placement is **not sufficient**; compliance
  varies by lane. The count is **provisional and deliberately not recorded yet**: both lanes were
  still alive when this was filed and may write their lines before exiting. Confirm on exit, then
  amend this entry — a compliance number taken while the lane is running is a measurement of the
  wrong moment
  · **the structural point does not depend on that count.** A lane **cannot land work without
  committing**, and this repo's commit convention already puts the id in the subject
  (`fix(#392a):`, `design(#397):`, `docs(#401):`). So the id is in git **by construction**, whereas
  the hand-off line is an extra act a lane must remember. One channel cannot be forgotten; the
  other is a habit. `#381` built the habit
  · **which narrows what `handoffs.md` is actually for** — landings `git log` cannot attribute: a
  different machine, a different repo, or work that is not a commit. That is a real set and the
  file should stay. But `SKILL.md`'s tick reads the file and does **not** mention deriving landings
  from git, so the tick's **primary** route is the weaker one. That ordering is the defect
  · rec: keep `handoffs.md` for the foreign case; add a git-derived landing sweep to the tick as
  the primary route (ids in subjects since the last fold, correlated against `## Open`), and demote
  the file to supplementary. `lint.check_landed_still_open` already does adjacent correlation —
  **read it before designing, it may already be most of this**
  · **the trap to avoid, and it is this repo's own recurring one:** a git sweep that finds nothing
  prints the same as one that ran wrong. Whatever gets built reports **how many commits it
  examined**, not just what it found
  · **the recommended sweep was RUN by hand and it works — this entry now has a yield number.**
  Scanned **1,131** commit subjects for `fix|feat|close|perf|refactor(#N):` against the **136** open
  ids: **6 flagged** whose entry does not cite the sha. That is a **4% review load**, which is
  tractable rather than noise
  · **and one of the six is real: `#340`**, fixed at `8009c90` and open ever since, found by this
  sweep and by nothing else — not by `lint`, not by the hand-off channel, not by me reading the
  ledger. The other five (`#394`, `#399`, `#275`, `#254`, `#196`) are a mix of partial fixes and
  work I have not yet folded, so **the sweep needs a suppression convention and one already
  exists**: `check_landed_still_open` treats a **cited sha** as the entry's evidence that it is
  deliberately still open. Cite the sha, the row disappears
  · so the design is settled by measurement rather than argument: **scan subjects, subtract entries
  that cite the sha, report the remainder with a count.** The count is the part that matters —
  a sweep that finds nothing must be distinguishable from one that did not run
  · related: **#381, #398, #394, #406**

- **#403** — `.dreamwork/docs/research/` has no `doc-map.md` row and 11 files sit in it unmapped ·
  P3 · docs/freshness · origin: **loop** · found while checking a new file's ownership obligations
  · the existing row is for root-level `.dreamwork/docs/research-*.md` — a **different** location.
  The directory has never been mapped, so `lint.check_doc_map_plans` has a sibling that was never
  written: `plans/` is enumerated and checked, `research/` is neither
  · smallest useful version is one row. Whether it should **enumerate** like the plans row (and so
  gain a check) is the real question — 11 files is enough that a stale enumeration is a cost
  · related: **#402**


- **#393** — a pending hand-off's span appears on the status panel with no motion check · P2 ·
  dashboard/transitions · origin: **loop** · from **#381's own caveat**, probed rather than accepted
  · `#381` surfaced pending hand-offs by adding a span to the existing `stfacts` row, which is the
  right call — it reuses the panel's tick-driven treatment and authors no second motion idiom. But
  **the span appears**, and this repo's rule is that *every* transition obeys `transitions.md` and
  **"there is no size below which this stops applying"**
  · the lane said so itself: *"a populated hand-off's appearance is unverified in pixels … the
  pytest test asserts the wiring + `collect()` data, not the rendered motion"* — honest, and within
  its brief's "keep it small" and no-full-sweep constraints, so this is a follow-on and not a lane
  failure
  · **why a pytest cannot cover it, which is the reason this is its own task:** an end-state
  assertion cannot fail on a motion bug and neither can "did it move". `transitions.md` opens with
  how to check, and that reasoning cost three batches to learn
  · needs a `dev/capture/*.mjs` guard, so it also needs the `justfile`'s `DEFAULT_GUARDS` — grant
  both to whoever takes it, per the lesson that an ownership list comes from the deliverables
  · related: **#381**


- **#371** — `do_POST` witnesses an interrupted body as complete · P1 ·
  reliability bug · origin: **loop** · found by dreamer-263-plan, coordinator verified
  · **the half that needs no ruling from him is DONE (`d33cc2f`)**: `submissions.log` now
  records `short: true` and `got: <bytes>` when fewer bytes arrive than were promised, and
  `file-formats.md` states that `short` and `truncated` are opposite conditions — a cap this
  server applied versus a promise the client broke — with `lint.py` refusing either half of
  the pair alone · proved with a real socket (larger `Content-Length` than bytes sent, then
  `shutdown(SHUT_WR)`), because urllib will not lie about `Content-Length` and a mocked read
  proves nothing about the read
  · **what REMAINS is only the policy, and it is his**: whether a short body is refused, or
  · **NOTE 11:16 — he has never actually been asked this.** It sat in `status.json`'s
  `awaiting_human` panel, so the dashboard reported it as waiting on him, but there is **no open
  `questions.md` entry** for `#263` Q2 and therefore no way for him to answer it. Removed from the
  panel (the panel now mirrors the five real open questions); the block stays recorded here. **To
  actually unblock this P1, Q2 must be asked** — deliberately not asked yet: five questions are
  already open and unanswered, and `#263`'s E/H lanes are behind a second gate he has not opened
  kept as a partial witness marked incomplete and allowed to proceed. That is **Q2 of #263's
  ask**, filed 2026-07-28 and unanswered · the behaviour is deliberately unchanged until he
  rules, and the witness is now truthful either way, so his answer is implementable in one
  increment whichever way it goes
  · #263's plan places that half at its increment 20 (envelope decided before the body is
  read) · **blocked on #263 Q2 only** — no longer on `watch.py`, which is free
  · **UNBLOCKED — his `#263` Q2 was answered at 05:43 and this entry never noticed** (found by
  `#420`'s census, verified by the coordinator against `questions.md` 2026-07-28 16:08). The answer is
  explicit: *"**Q2 yes** (amend law 2 to keep a partial witness marked incomplete)"*. So the one thing
  this waited on has been settled for ten hours, `watch.py` is free, and **this is a startable P1**
  · **and it is `#419`'s reverse direction, in its most expensive form:** the loop never asked Q2 as
  its own question — it rode inside another entry — so when it was answered there was nothing pointing
  back here. A ruling that arrives on a *neighbouring* question is invisible to the entry that needed
  it. `#419`'s check must therefore key on the *decision*, not on the entry that happened to carry it
  · **IN PROGRESS 2026-07-28 16:14** — `ccc @grok`, `.worktrees/371`, brief
  `.dreamwork/docs/briefs/371-short-body-policy.md`, owning `watch.py` and `test_watch.py`. His ruling
  is the spec: keep the partial witness, mark it incomplete, let it proceed
  · the brief carries this entry's own hard-won method as a requirement rather than a suggestion: **a
  mocked read proves nothing about the read**, so the test is a real socket with an oversized
  `Content-Length` and `shutdown(SHUT_WR)`. And **two** red-proofs, because *keep it* and *mark it* are
  two claims and one red covers only one
  · it must **not** add a field to `file-formats.md` — the `#419` lane holds that file — so it reuses
  the landed `short`/`got` spelling or reports the field it needs
  · **RETRACTED 2026-07-28 16:22 — the "UNBLOCKED" note above is WRONG and I dispatched a lane on
  it before catching that.** His *"Q2 yes"* amended the **design**; it did not authorise the
  **implementation**. `user-event-journal-implementation.md:19` is explicit: *"landed in the design …
  **Increment 20 implements it — behind the second gate.**"* And increment 20 is
  **`E1 envelope`** (`:71`) — **lane E**, which his same 05:43 answer withheld: *"E, the HTTP
  cutover, and H, the mixed-version gate, **stay behind a second gate** until A–D are proved."*
  Lanes A, B, C and F are done; **D is not**, so the gate is correctly still shut
  · **so this entry is blocked on the SECOND GATE, not on Q2.** The lane (`ccc @grok`, dispatched
  16:14) was killed at 16:20 having committed nothing; its 233-line working diff is kept at
  `scratchpad/371-abandoned.diff` rather than discarded, since it is the same work whenever the gate
  opens. No commit, no merge, no change to `master`
  · **the mistake, named exactly, because the repo had already written this distinction down:** this
  entry's own text says *"the approval covers the CONTRACT, not #263's implementation"* about the
  01:27 approval, and I made the identical error one question later with the 05:43 one. **"He
  answered it" and "we may build it" are different facts, and an answer that arrives inside a
  neighbouring entry carries no authority beyond its own scope.** I read *"Q2 yes"* as a green light
  because the sentence was affirmative
  · `#420`'s census was right that the ruling landed and unprocessed, and wrong — as I was — that
  processing it means implementing it. Processing it means **recording** that the design changed,
  which is what this note does
  · **what would actually unblock it, and it is a question rather than work**: prove lane D, then ask
  him to open the second gate. That ask does not exist, which makes it a `#419` case — a human gate
  with no question — and the honest count of open questions on his desk is therefore still 3, not 4,
  until lane D is proved and the ask is worth making

- **#368** — Break the large Python files into a modular, testable codebase · P2 ·
  refactor/architecture · origin: **human** · **human via watch `add-idea` 2026-07-28 02:46**:
  *"after the cli, we should refactor the large python files into a proper modular codebase
  that's reusable and more easily tested. also, re cli, we can write a core in python that we
  can later replace with something written in a faster-to-start compiled language. We can
  measure how fast it is to start too and like return 'version' as a benchmark."*
  · **three asks, and the third makes the first two checkable**, which is the part worth
  keeping: a startup benchmark turns "modular" and "fast to start" from taste into numbers
  · measured now, so the baseline exists before anything moves: `watch.py` **8647** lines,
  `test_watch.py` 3830, `test_lint.py` 2443, `lint.py` 2004, `dreamhub.py` 982,
  `review_artifact.py` 813 · startup, min of 5 runs each: bare `python3 -c pass` **20ms**,
  `review_artifact.py --help` **75ms**, `lint.py --help` **106ms**, and `import watch` alone
  **93ms** · so the interpreter floor is 20ms and importing the dashboard costs 4.7x that
  before any work happens — his instinct that a `version` call is a fair benchmark is right,
  because it measures exactly the import cost and nothing else
  · **sequencing is his and it is deliberate — "after the cli"**: #352 standardises the
  duplicated ledger parsing, then the CLI exists, and only then does the refactor have a shape
  to move things into. Refactoring first would rearrange code around an interface that does not
  exist yet
  · and the middle ask sets the boundary the refactor must respect: a **Python core that a
  compiled language can later replace**, which means the seam is the CLI's data contract, not
  Python function signatures · #264's design already states its boundary "in terms a non-Python
  CLI could implement" for this reason, so the constraint is consistent and already partly paid
  · blocked on #352 and the CLI existing · rec when it starts: move the benchmark first (a
  `version` verb plus a recorded baseline), so every later step is measured against it rather
  than argued about
  · related: **#425, #426**

- **#367** — Tabbed pointers to a review's essentials, with next/prev · P2 ·
  review tooling/UX · origin: **human** · **human via watch `add-idea` 2026-07-28 02:36**,
  typed from `/review?p=task-store-schema.html` — so from inside the problem: *"on reviews, it
  would be really handy to have some pointer labels at the most important parts. like the
  absolute essentials. then i could have a next/prev button too. something like those little
  thin postits that lawyers use to indicate key points and where you need to sign. would make
  it a lot quicker to go through reviews I think. (Sometimes they are quite long)"*
  · **his analogy is precise and it decides the design.** A lawyer's flag is not a table of
  contents: it marks *where you must act*, it protrudes so you can find it without opening the
  document, and there are five of them and not fifty. So this is a **different axis from the
  existing `nav`** — nav is structure (`findings` / `shape` / `decision`), this is *"read this
  if you read nothing else"* — and conflating them would produce a second table of contents,
  which is not what he asked for
  · **the forcing function is worth as much as the feature.** Marks come from the source, so
  the authoring dreamer has to name which three or four passages are the essentials. An
  artifact that cannot say what its own essentials are is an artifact that has not decided what
  it is asking — so this makes a quality problem visible rather than only saving him time
  · design constraints already known, so nobody rediscovers them: **(a)** it is a frame change,
  and touching `review-artifact.template.html` restamps all 15 artifacts (`template_stamp`
  digests its bytes), so it should land **in one commit with #347's missing
  `white-space:nowrap`** and whatever #364's answered-marker turns out to be — three frame
  tasks, one rebuild · **(b)** next/prev is movement between marks, so `transitions.md` governs
  it, and a **long-range smooth scroll is already refuted** — the #229 v2 review found a 1.5s
  one and it failed the gate; a settled landing is the requirement, not a journey · **(c)** the
  template has no `scroll-behavior` today (measured: zero occurrences), so the behaviour is
  chosen here rather than inherited · **(d)** the tabs are navigation, so they are real
  focusable controls with the current mark announced, not decorative edge art · **(e)** on
  mobile a protruding edge tab competes with the column for width, which is where the physical
  metaphor stops paying and needs its own answer rather than a shrink
  · rec: one source-declared mark per essential passage (a class on the block, plus its short
  label), rendered as thin edge tabs; next/prev walks them in document order; the count is
  **capped low and the cap is stated**, because his whole point is that five flags help and
  fifty are wallpaper
  · **UNBLOCKED 2026-07-28 04:05, both reasons spent**: #365's measurement landed
  (`09c3881`), so the way to add a component rule is now demonstrated rather than deferred —
  count the class's real direct children across every built artifact, add the rule only if the
  set is unanimous, and record the count. That pass also refuted `.summary-line` and
  `.choice`/`.answer`, so a new `.mark` component must earn its rule the same way and not by
  analogy · and the frame batch it was waiting to ride landed at `405092f`, so this is now its
  own commit and its own rebuild, which is one restamp of 15 artifacts and acceptable
  · **design landed design-only 2026-07-28 04:30, awaiting his ruling.** Plan
  `.dreamwork/docs/plans/review-essential-marks.md`, artifact
  `.dreamwork/review/review-essential-marks.html`, asked in `questions.md` as four decisions
  M1-M4. Measured first, and **the measurement refuted three designs including the literal
  reading of his own metaphor**: a per-section list would be 22 entries in the artifact that
  needs it most; the margin outside `.wrap` is **16px at every viewport from 1120px down**, so a
  tab protruding past the page edge is affordable only above ~1250px; and blocks within a section
  run 614px to 1120px, so a per-block anchor would scatter the flags across 500px
  · **the shape that survived**: a mark is a flag at a *height*, anchored to the reading column's
  right edge — `.read` is a fixed **613.5px** (78ch at 13.12px, which does not scale) and
  left-aligned, leaving **506px of wrap already empty** at 1280px. Rail above 780px, compact
  strip below, next/prev walking document order in both
  · **constraint (e) above was wrong in a way worth keeping recorded**: it anticipated the hard
  case at mobile, and the cliff is at **~780px** — above both existing breakpoints (860, 480).
  A design answering only for 390px would have passed review and broken in a half-width window
  on his desktop
  · **RULED 2026-07-28 05:35 (`0597bc6`), so this is unblocked to build.** M1 (the 780px
  rail/strip split) and M4 (marks are not a `nav` entry) went with the rec. **M2 and M3 were
  overridden**: the cap is **soft 7 / hard 15** — seven is allowed, so the warning starts at
  **8** and the refusal at 15 (`MARKS_WARN_AT = 8`; a cap of 7 that warns *at* 7 is a cap of
  6, and this line and the plan's both used to say "at seven") — not my
  five-and-refuse; and the label is **two-line tabs at a smaller text size, up to ~6 words**,
  not my ~12 characters with builder truncation. The tab grows to fit the label; nobody
  truncates. The rulings are now recorded in the plan's §"What was decided", which wins over
  the superseded paragraphs left in place around it
  · **one measurement is owed before building M3** and it is the same class of thing that
  refuted three designs already: a two-line tab at a smaller size is **taller and possibly
  wider** than the tab all the geometry was measured against, and the geometry is tight — the
  gutter outside `.wrap` is 16px at every viewport from 1120px down. Measure ~6 words at two
  lines against that gutter first. If it does not fit somewhere, **report the measurement**;
  do not quietly reintroduce a cap he just removed
  · **increment 1 LANDED 2026-07-28 06:58 (`dbcbcc5`), and it is the safety net rather than
  the feature**: `essential_marks()` parses `data-mark` in document order, warns at 8, refuses
  at 15, refuses a mark whose element has no `id` of its own. **No visible change, no template
  touch, no artifact rebuilt** — which is the whole point: the frame now carries the machinery,
  so every later increment is shippable on its own. 70 tests in `test_review_artifact.py`
  · **coordinator verified independently, not folded**: the byte-identity guarantee is the
  criterion most likely to be hollow, so I recomputed its frozen baseline from a ref **I**
  picked by hand (`12d17ad`, confirmed to carry neither `MARKS_WARN_AT` nor `essential_marks`)
  and it matched to the digit — the constant is genuinely pre-change, not recomputed with the
  new code. Then I injected the realistic regression rather than the lane's placeholder — an
  unguarded marks stylesheet (`increment 2's CSS added without checking labels is non-empty`) —
  and `test_a_source_with_no_marks_renders_byte_identically_apart_from_the_stamp` went red
  alone, neighbours green. Snapshot-restored; 70 pass
  · **still to build: increments 2+** — the rail/strip presentation, the tab, next/prev.
  **Increment 1 hands increment 2 a guarantee it should not squander:** every mark's `id` is on
  the marked element itself, so next/prev can key off it directly with nothing to invent
  · **the owed measurement LANDED 2026-07-28 07:26 (`1696657`, `ccc @grok`), and it refuted the
  geometry the design rests on.** Doc `.dreamwork/docs/measurements/367-two-line-tab-geometry.md`,
  reproducible script `dev/capture/marktab-geometry.mjs`, screenshots under
  `.dreamwork/docs/measurements/367-tabs/`. **A worst-case ~6-word two-line tab is 180×32.3px,
  not the 96px flag every number in the plan assumed.** Consequences, all measured:
    · **the 780px cliff does not hold — it moves to ~830px.** The tab fits inside `.wrap` down
    to 830 (by 0.5px), is past the wrap at 820, and is **clipped past the page edge at 810 and
    at 780**. Typical authored labels are 117–130px and would have hidden this; the worst case
    is what decides a no-truncation design
    · **vertical collision is possible in real documents.** Tab height 32.3px is the minimum
    top-to-top gap; this artifact's densest adjacent block pair (`section#long` → `p.read`) is
    **29.2px**. Section-level marks are safe (329–929px apart); block-level adjacent marks are
    not
    · **the strip below the cliff needs its own answer for 5–7 marks.** At the soft cap of 7,
    worst-case labels need **3 rows / ~214px**; typical labels 2 rows / ~140px. He removed
    truncation, so "shrink it" is not available
  · **coordinator verified independently:** re-ran the lane's script and every number reproduced
  **byte-identically**, including the screenshots — the measurement is deterministic, which is
  stronger than the criterion asked for. I also looked at the images myself rather than reading
  its vision notes. The 780px shot shows the tab clipped **mid-word**, and carries an irony worth
  keeping: the artifact's own table in that same image reads *"780 · 134 · yes — and this is the
  last one"*, so the design doc is being falsified by the prototype rendered on top of it
  · **one boundary the lane did not name** (coordinator perimeter audit): its collision shot
  uses **identical labels** for both tabs, which exaggerates "reads as one continuous chrome
  mass" — distinct labels would separate better. The geometric finding stands regardless, and so
  does the fix (a minimum gap or a divider), so this changes the evidence's strength and not the
  conclusion
  · **derived decisions, mine and reversible — these follow from his ruling rather than adding
  to it**, and increment 2's brief carries them: **(i)** the rail/strip switch moves to the
  measured wrap-fit boundary rather than staying at the literal 780, because he ruled no
  truncation and a clipped flag is worse than no flag; **(ii)** two marks closer than the tab
  height are the renderer's problem, not the author's — offset or stack them, and refuse only if
  that is impossible, in the voice of the existing no-id refusal
  · **one question is genuinely his and is NOT derivable**: at 5–7 marks the strip becomes
  ~140–214px of chrome on a narrow screen. That is a reading-experience price, and he is the only
  one who can say whether it is worth paying or whether the strip should cap what it *shows*
  while next/prev still walks them all. Owed to him with an artifact
  · the first increment is unchanged by the rulings: the source contract in `file-formats.md`
  plus the "declares no marks ⇒ byte-identical output" check, red first, which touches no
  artifact — and it is the one that makes the frame change safe to ship before any artifact
  adopts it

  · related: **#396, #417, #415**
  · **INCREMENT 2a LANDED** `d4cbba8` `a818bf8` (+ `markrail` registered in the `justfile`, which the
  brief had failed to grant — ratified by relay). `ccc @glm52`. The rail, the flag, next/prev, above
  the cliff only; **below 860px nothing renders**, deliberately, because 2b is his call
  · **coordinator verification, all three owed checks done.** (1) **The motion red re-run and it is
  discriminating**: injecting `scroll-behavior:smooth` into the template's `html` rule fails exactly
  *"...and LANDS SETTLED — an instant jump, not a smooth journey (0 part-way)"* plus its
  reduced-motion twin, while every geometry neighbour stayed green. Restored from a `cp` snapshot,
  byte-exact. First attempt injected into a `html {` rule that does not exist and the guard passed —
  a green red-run, caught, not believed. (2) **Guard green at load 26.6**, which this repo's
  asymmetry rule makes conclusive. (3) **The retired byte-identity test is not weaker**: the lane
  dropped only the frozen whole-document digest and kept `_prechange_review_artifact`'s
  content-resolution, comparing the **body region** against the live pre-change builder — so the
  drift the digest existed to catch is still caught directly, and it no longer false-fails on frame
  CSS the template is supposed to gain
  · its `ch`-resolution finding is genuinely subtle and correct — a one-element flag would resolve
  `--measure:78ch` against the *tab's* narrower font, so the flag is an outer block inheriting the
  body font plus an inner visible postit
  · **probing its caveat found #396 (P1)** — see that entry. The caveat's own axis was clean at three
  densities; the axis it held constant was the element type
  · **still open for 2b**: the strip below the cliff, awaiting his ruling on the artifact  · **PREVIEWS LANDED `98670ae` (increment only; #367 STAYS OPEN awaiting his ruling)** — he asked
  at 14:52 to see A/B/C before deciding. `ccc @grok`, **13 minutes** end to end:
  `.dreamwork/review/367-option-previews.html` + source + six screenshots + a rail reference +
  `measures.json`, every figure measured from the rendered DOM at load and red-proved by changing
  a row count and watching the caption follow
  · **it corrected a number I had given HIM**: the entry said option A costs ~214px of chrome at
  seven marks; measured it is **167.9px** in 3 rows (B 127.2, C 31.8, unchanged at 640). The 214
  was extrapolated from a 180px worst-case tab and never observed. Also *"the reading column is
  fixed at 613.5px"* is true at 780 and false at 640 (608 — 78ch stops fitting); **the 16px outer
  margin does hold at both**, so the no-lateral-space argument the decision rests on is intact
  · **the rec survives but its shape changed**, and both the lane and I say so independently after
  looking at the pixels: **A reads lighter than its number implied** — three tidy rows of
  product-shaped pills — so if he wants the index before walking, A is more defensible than my
  figure made it sound. B looks worse in pixels than in prose. C reads as a usable walk, not a stub
  · **the two lint WARNs naming this entry are correct and are a grammar gap, not a mistake**: a
  merge commit that lands an *increment* of a multi-increment task is indistinguishable from one
  that closes it, so `#367` reads as "open but already merged". Same class as `#415` — a checker
  narrower than the work it describes. Recorded there rather than silenced here

- **#378** — One `.fact` sits outside any `.facts` grid, in a file with no source · P3 ·
  review tooling · origin: **loop** · 10m · found by #365's measurement and verified
  independently: `protected-service-boundary-288.html` has `containers=0 facts=1`, so that
  fact gets the component's padding and background with no grid around it · it also carries an
  `.eyebrow` and a bare `<div>` inside the `.fact`, which the `COMPONENT_CHILDREN` rule
  forbids · **invisible to every check that exists, and will stay so**: the file is one of the
  untemplated dozen with no source at all, and both the component refusal and the grid warning
  run in `build`, which never sees it · so this belongs to whatever migrates those files, not
  to a new check — a checker that read built output instead would be reporting on files nobody
  can regenerate · `test_every_shipped_artifact_still_satisfies_the_new_rules` excludes this
  one violation **by name**, so a new one in the same file is still caught · related: **#379**

- **#388** — A guard's own `watch.py` is starved to death at extreme load, and every guard
  inherits it · P3 · guards/infrastructure · origin: **loop** · 20m · **surfaced by #386 and
  correctly declared out of its scope** — the lane could have quietly absorbed it and did not
  · at load **100+** on 16 cores a guard throws `TypeError: fetch failed [cause] ECONNREFUSED
  127.0.0.1:<port>`: the `watch.py` the guard spawned for itself never became reachable, or
  stopped being reachable mid-run. It is **not** specific to `gitrow` — every guard that spawns
  its own server inherits it, so under contention any guard can report a fault that belongs to
  the harness
  · **this is the worst class of guard failure we have**, worse than a flake, because it arrives
  as *"the guard threw before finishing its checks"* — a third verdict that is neither pass nor
  fail and reads as a real problem with the page. #383 already had to fix `burndown` to say what
  threw, which is how we can see this one at all
  · rec: the fix is almost certainly a readiness wait rather than a timeout bump — poll the
  server's own endpoint until it answers, with a bounded deadline, before the first navigation,
  and make the failure say *"the server never came up in Ns"* rather than surfacing a raw
  `ECONNREFUSED`. Measure first: find whether the refusal happens at startup or mid-run, because
  those are different bugs and the report above is consistent with either
  · **do not chase this by making guards more patient in general** — a longer timeout hides a
  server that died, and the whole reason we can distinguish these classes today is that #383
  made a throwing guard name its own exception
  · related: **#383, #386**

- **#387** — The ledger-lint hook cannot see how the coordinator actually edits the ledger ·
  P2 · dogfood/reliability · origin: **loop** · 15m · **found by installing the thing, which is
  the only way this was ever going to surface.** #361 turned on
  `posttooluse_ledger_lint.py` and reported the window closed. It is half closed
  · **verified, not assumed** — `~/.claude/settings.json` registers the hook under
  `PostToolUse` with `matcher: "Write|Edit"`, so it fires on the **Write and Edit tools**.
  Every ledger edit this coordinator makes goes through a Bash heredoc
  (`python3 - <<PY … pathlib.Path(".dreamwork/tasks.md").write_text(…)`), because the edits are
  structural — move an entry between sections, bump the next id, splice a citation. The matcher
  never sees those, so the hook has not fired on a single real ledger write since it was
  installed
  · so the incident it was justified on — *"a `tasks.md` write introduced a lint ERROR and the
  commit went through anyway"* — is still live for the writer that caused both instances of it
  · **two candidate fixes, and they are not equivalent**: (a) add `Bash` to the matcher, which
  fires the hook on **every** shell command in every session — the hook must then be cheap and
  must decide quickly that a command touched no ledger file, and deciding that from a command
  string is guesswork; (b) have the hook key off the **file** rather than the tool, if the
  harness gives PostToolUse enough to do that for Bash. Measure (a)'s cost before choosing:
  a hook on every Bash call is a tax on every session on this machine, not just this loop
  · **the measurement is done, 07:08, and it kills option (a) outright** — and it needed no
  experiment, only reading the hook: `posttooluse_ledger_lint.py:59-63` does
  `payload["tool_input"]["file_path"]` and returns *"no file_path in tool input"* when absent.
  A **Bash** event's `tool_input` carries a **command string**, not a path. So adding `Bash` to
  the matcher would fire the hook and the hook would immediately decline, every time — the
  file it needs is not in the payload and cannot be, since for this coordinator the path lives
  *inside* a `python3 - <<PY` heredoc as Python source
  · so (a) is not "expensive", it is **inert**, and that changes the shape of the answer:
  widening the matcher requires *also* teaching the hook to guess a path out of shell text,
  which is the guesswork this entry already suspected
  · **new rec, better than the one it replaces: mtime, not the payload.** On a `Bash` event the
  hook ignores `tool_input` entirely and compares the two ledger files' mtimes against a stored
  value (`.dreamwork/.status-keys` already establishes the precedent that `lint.py` may own a
  small state file). Lint only when one moved. That is robust to *any* writer — heredoc,
  `sed`, an editor, another agent — which the `file_path` route can never be, and it costs one
  `stat` per Bash call rather than a lint
  · **and one thing needs no permission at all, so it is already in force**: this coordinator
  now uses Write/Edit for ledger files where the edit is expressible that way, which covers the
  writer that caused both incidents. Recorded here rather than left as an intention
  · related: **#361**

- **#359** — A hosted Dreamhub as a paid service, agents registering against it · P2 ·
  product/architecture · origin: **human** · **human via watch 2026-07-28 01:39**, splitting
  #275 in two: *"a service that is provided as a subscription that allows you to register
  dreamwork agents against a central dreamhub that you can log into and use and pay like
  $2/mo for. wrt stdlib only, that only applies for self-hosted stuff. for the SaaS
  frontend, we can include dependencies where required."* · **this is a different product,
  not a deployment mode of the local hub** — the local hub reads one machine's
  `.dreamwork/` off disk, whereas this one has many agents pushing to it from many
  machines, which makes registration, tenancy, transport and retention the design rather
  than afterthoughts · the constraint that shaped every earlier answer is **lifted here**:
  stdlib-only was a property of the self-hosted binary, so the SaaS may take dependencies
  · what it needs designed before any code: what an agent registers *as* and how that
  credential is issued and revoked; what it pushes and how often; whether the server ever
  stores project content or only derived status; tenant isolation; and the price point's
  actual implication — $2/mo is a strong statement about per-tenant cost, so storage and
  egress are design inputs, not billing details · unblocks nothing and blocks nothing;
  it can be designed while #275 continues on the self-hosted half

- **#357** — A CLI warning layer that surfaces incomplete data and what is waiting ·
  P1 · tooling/feature · origin: **human** · **human via watch 2026-07-28 01:23**, inside his
  #346 S4 answer: *"with these kinds of things we can have an automated warning layer in cli
  calls that raises issues where data is incomplete or whatever. Also things like unchecked
  message count, new task count, new question count, unanswered question count, unfolded-in
  answer count, etc."* · two features in one sentence and they share a mechanism · **(a)
  incompleteness warnings**: every CLI call can report the data quality it noticed —
  entries with no `type`, no priority band, a dependency naming a task that does not exist —
  which is what makes his S4 answer safe: an unvalidated column is fine *if* something
  routinely tells you what is missing · **(b) waiting-counts**, and these are the loop's own
  vital signs: unchecked messages, new tasks, new questions, unanswered questions, and
  **unfolded-in answers** — the last one is the interesting one, because an answer that
  arrived and was never folded is invisible today except by reading the file, and that is
  exactly how his 23:28 batched-delivery idea (#342) fails if nobody counts it
  · **it belongs to the store, not beside it**: these are all queries over #346's entities,
  so they are the first real consumers of the read surface and should shape it — a count
  that needs a full-table scan every invocation is a count that will be turned off
  · rec: one `dreamwork status`-shaped verb returning all counts as data, plus a warnings
  channel every other verb can emit on, so a human reading any command sees the same numbers
  · blocked on #346's read surface existing; the counts themselves are specifiable now
  · **RAISED TO P1 and re-argued by him, 2026-07-28 02:33** — the same idea arrived a second
  time, unprompted, pointing at a concrete incident rather than a hypothetical: *"428e85b shows
  why we need tooling i think (like cli) so that there's always a little status msg tacked on
  about that. then you will be prompted to check and can always know what is not folded in
  etc."* · an idea he raises twice, independently, is a priority and not a nice-to-have
  · **the incident is the specification.** His #346 ruling sat unfolded for 64 minutes and was
  found only because a coordinator happened to open the entry while doing something else. Two
  of his four named counts would each have caught it on the next command anyone ran
  · **and his word "tacked on" is the design constraint, not a manner of speaking.** A count you
  must ask for is a count nobody asks for; the value is entirely in it being **ambient** —
  present on the output of whatever you were already doing. `lint.check_unfolded_answers`
  (#366, `6db36f7`) is the interim half and shows the gap precisely: it catches exactly this
  fault, and it fires only when someone chooses to run lint
  · so the shape follows: not a `status` verb that reports counts, but a **footer every verb
  emits**, with the verb-specific output above it · the `status`-shaped verb still earns its
  place for the machine-readable form, but it is the secondary surface, not the primary one
  · **one design consequence worth stating before anyone builds it**: a footer on every
  invocation is a per-invocation cost, so each count must be cheap or the footer gets
  suppressed and the feature dies quietly. That is the real reason these counts belong to
  #346's store rather than beside it — an unfolded-answer count is one indexed query there and
  a full re-parse of `questions.md` otherwise

- **#358** — Head/body split so the tool-running half cannot reach the API key · P2 ·
  security architecture/research · origin: **human** · **human via watch 2026-07-28 01:26**,
  answering #288 with `rec` and then going further: *"I kind of want to experiment with a head
  and a body part for running this stuff, like the head processes the LLM API calls and the
  like, but then sends tool calls over a socket to the body which is running in a docker
  container or a different box or something like that. The point is that it cannot kill the
  head or exfiltrate the API key, it can only kill itself (or escape I suppose). Anyway maybe
  that kind of architecture can help, but it presents a problem with like claude code and the
  like. hmmm."* · **this is the general form of #288's specific ask** — #288 asks whether to
  contain subagent tools or isolate the dashboard identity, and this says: put the boundary
  between *deciding* and *doing* instead, so the credential lives on the side that never runs
  untrusted output · the threat model is stated precisely and worth keeping in his words: the
  body *"can only kill itself (or escape I suppose)"*
  · **his own caveat is the hard part and should not be glossed**: *"it presents a problem
  with like claude code and the like"* — a harness that owns both the API call and the tool
  execution has no seam to cut, so this is either a wrapper that proxies an existing agent's
  tool calls, or it only applies to agents we run ourselves · that fork is the first thing to
  decide and it decides whether this is buildable here at all
  · **it must not be confused with the run-mode work (#288/#290)**, which explicitly grants no
  kill or sandbox authority from a mode alone · rec: a read-only IGC comparing (1) a socket
  protocol with the body in a container, (2) a proxy that intercepts an existing harness's
  tool calls, (3) accepting the current boundary and hardening the credential instead — each
  judged on whether it survives his stated threat model, and on whether Claude Code can be
  made to fit at all · **research first, no implementation**: this changes where credentials
  live, and getting it wrong is worse than not doing it

- **#354** — `/filebytes` buffers a whole file with no cap · P2 · dashboard/robustness ·
  origin: **loop** · reported by `ccc-glm52-336` as out of scope, not fixed · `read_text` caps
  at 200_000 characters; `/filebytes` deliberately does not cap, and the agent's reasoning is
  right and worth keeping: **a cap on a byte stream corrupts an image rather than truncating
  readable text**, so the text cap's idiom does not transfer · consequence: a 1GB PNG in the
  target buffers 1GB in the server process · mitigated by confinement (only files inside the
  target are reachable) and by the dashboard being loopback-only today, which is exactly the
  mitigation `#275`/`#276` would remove · rec: HTTP `Range`/`206 Partial Content`, which is
  the only cap that does not corrupt — so this is a real feature, not a one-line guard, and
  that is why it was not smuggled into #336 · also revisit `Cache-Control: private, max-age=0,
  must-revalidate`, chosen conservatively because `--autoreload` re-execs on source mtime and
  a stale image mid-edit would confuse
  · **DESIGNED 2026-07-28 08:07 (`0d2d4f6`, `ccc @grok`), and the design REFUTED this entry's own
  recommendation** — which is the result worth having. Plan `.dreamwork/docs/plans/filebytes-range.md`,
  grounded in line numbers throughout. **`Range` alone does not fix the bug:** the common client is
  `<img src="/filebytes…">` (`watch.py:2939-2956`) which sends **no `Range` header**, so that path
  keeps buffering the whole file. The real fix is **chunked streaming from disk with a bounded
  buffer**, with single-range `206` as a **second, separate** capability. The recorded rec was not
  wrong about Range being the only non-corrupting *partial response* — it was wrong that Range is
  the fix
  · the 1GB is held as one full `bytes` from `read_bytes` (`:7107-7117`) inside `_send_bytes`
  (`:8968-8984`) → unbounded `f.read()` → a single `wfile.write`. Confinement **is** real and
  tested (`test_filebytes_blocks_escape`), it simply does not bound size
  · **staging, and the split matters for authority**: **(1) stream the full GET** — 64KiB
  read/write loop, `Content-Length` from `stat`, MIME/disposition/nosniff/`Cache-Control`
  unchanged, full-GET body byte-identical to disk, `fileimg`/`fileview`/`filehead` green with no
  client change. **(2) single-range `206`/`416` + `Accept-Ranges`.** **(3) optional.**
  · **increment 1 is AUTHORISED by the coordinator and dispatched**: it fixes a memory bug in an
  existing endpoint and changes nothing observable — no new capability, no new surface, no visible
  behaviour. **Increment 2 is a new protocol capability and waits**; it is not urgent while the
  dashboard is loopback-only, and it is exactly what `#275`/`#276` would make urgent
  · the plan names the hollow implementation to pre-empt: headers-only tests **cannot** tell
  read-all-then-slice from real streaming, so the check must observe **per-`read` sizes** and fail
  on a single whole-file read. Named red: restoring `:8968` / `:7115-7116`
  · `Cache-Control: private, max-age=0, must-revalidate` **stays** for v1 — revisit as a separate
  product call, not as a side effect
  · plan §7 covers **#355** and agrees with my measurement: not a defect today, make truncation
  **loud**, do not raise the cap

  · **INCREMENT 1 LANDED** `0f77a1f` — `ccc @grok`, brief
  `.dreamwork/docs/briefs/354-inc1-stream-filebytes.md`. `_send_bytes` is now stat + open + a
  64 KiB read/write loop; `Content-Length` comes from the stat size; peak body memory is one chunk
  rather than one file. `Cache-Control` kept, no client or guard change
  · **coordinator verified the red that was the whole point**, because headers-only tests cannot
  tell real streaming from read-all-then-slice and the plan's author flagged that instrumentation
  as their least-certain piece. Replacing the loop with an unbounded `body.read()` fails
  `test_a_plain_get_never_reads_the_whole_file_at_once` with **`largest single read was 524288 on a
  524288-byte file`** — it reports the number rather than "not equal", which is the discriminating
  form. `test_content_length_comes_from_stat_not_from_reading` and
  `test_fileview_image_served_byte_identical` **both stayed green** under that injection, so the
  test isolates the streaming property rather than general breakage. Injection grepped for before
  believing the result; restored from a `cp` snapshot, byte-exact
  · **`Range` deliberately NOT built** — increment 2, unauthorised. The design refuted it as the
  fix: an `<img>` sends no `Range` header, so `Range` alone would have left the common path
  buffering. That refutation is why this increment exists at all
  · lane's caveats, recorded rather than absorbed: mid-stream disconnect was not injection-tested
  (only structural continuity of `#299`); the probe watches `file.read`, so a hollow that read the
  whole file through a different API would dodge it — though that is the production seam
- **#355** — `/reviewraw` still serves artifacts through `read_text(limit=2_000_000)` · P3 ·
  dashboard/consistency · origin: **loop** · reported by `ccc-glm52-336`, outside its
  ownership · #336 gave `/file` a byte path and a type allowlist; `/reviewraw` kept the text
  path · **not a defect today**: it is confined to `.dreamwork/review/`, and an artifact's
  contract is self-contained HTML the loop itself built, so the trust story genuinely differs
  from an arbitrary file · flagged because *"what about reviewraw's Content-Type?"* is the
  next reader's natural question and it deserves a recorded answer rather than a rediscovery ·
  the 2MB cap is the substantive half: an artifact over it is silently truncated, and a
  truncated self-contained page can render as a blank frame with no error — check whether any
  artifact is near it before deciding
  · **measured 2026-07-28 08:02, and the answer changes the shape of this task.** Largest of the
  18 artifacts is `threaded-topic-chats-v2.html` at **84,987 B — 4.2% of the cap**, so there is
  **23.5x headroom** and nothing is close. Not live, and it should not be treated as urgent
  · **but the growth vector is now demonstrated rather than hypothetical**: the second-largest
  artifact is `367-strip-below-cliff.html` at 81,851 B, which I built **today**, and it got there
  almost entirely from **one 40 KB base64-embedded screenshot**. Artifacts must be offline-clean,
  so every image is inlined and costs ~1.33x its bytes. A decision artifact carrying ten
  screenshots — which is the direction #367's own increments and any visual review are heading —
  lands near the cap. So the honest reading is: **the cap will be reached by embedded evidence,
  at roughly 25 screenshots' worth**, and the failure mode is a silently blank page
  · so the priority stays P3 **today** and the trigger to raise it is measurable: re-run this
  measurement when any artifact passes ~25% of the cap, or fold the fix in whenever `/reviewraw`
  is being touched anyway

- **#356** — Two narrow papercuts in the new `/file` image view · P3 · dashboard/polish ·
  origin: **loop** · both reported by `ccc-glm52-336` with its reasoning for not fixing them,
  which stands · **(a) `imgFailed` reuses build-time metadata**: when an `<img>` fails to
  decode, the fallback panel is built from `data-mime`/`data-size` captured when the view was
  built, not refetched — so if the file changed between build and load failure the panel shows
  stale type and size. It declined to refetch because that adds a roundtrip in the failure path
  for a narrow window · **(b) `safe_attachment_filename` is ASCII-only**: a non-ASCII filename
  gets `_`-substituted in `Content-Disposition`. RFC 6266's `filename*=UTF-8''…` is the fix; it
  declined because the URL basename is the browser's default anyway and a malformed header is
  worse than a drab name · **the AVIF detection note belongs here too**: AVIF has no fixed
  magic prefix, only an `ftyp` box, and the brand check accepts `avif`/`avis`/`mif1` — an
  AVIF-compatible file with another major brand (e.g. `ma1a`) is served as a download instead
  of inline. Conservative failure mode, and a detection-vs-decode mismatch degrades through
  `imgFailed` rather than leaving a broken icon

- **#353** — Normalise the Markdown ledger so the store's schema can be strict · P1 ·
  data normalisation/prerequisite · origin: **human** · **human via watch 2026-07-28 01:13**,
  follow-up on the #346 ask: *"oh one thought is that we can make the shape as restrictive as
  we want before migrating because we won't need the python / plaintext versions for much
  longer. not sure if that helps us."* · **it helps a great deal and it inverted three of the
  four #346 recommendations**: every refutation there was the same sentence — *"that edits
  three of your existing entries"* — and that is a one-time cost against looseness the schema
  would carry forever and every consumer would handle forever
  · **bounded and countable, which is why it is a task and not a project**: 3 combined entries
  to split (`#138/#156`, `#250/#251`, `#292/#293`), 4 compound bands to resolve (`P0/P1`×3,
  `P1/P2`×1), 6 entries carrying no band (`#99`, `#315`, `#323`, `#325`, `#327`, `#333`), and
  the tail of the 66 distinct values sitting where `type` should be · after it, `task(id
  PRIMARY KEY)` needs no entry/task split, `priority` is a closed enum and `type` is a closed
  set — a table and a join fewer, permanently
  · **needs NO #263 answer**: normalising the plaintext is orthogonal to the event model, so
  with #352 this is the second thing that turns his "sqlite is becoming a blocker" into
  movement rather than waiting
  · **the real risk is the one the loop already realised tonight**: this is a bulk edit to the
  loop's own durable memory, and a fold script damaged `questions.md` at 23:5x by dropping the
  newline after `## Open`, making every entry invisible to the dashboard · so the guards are
  part of the task, not a nicety — parse with `watch.ledger_entries`/`parse_ledger` before and
  after, assert entry and id counts move ONLY where a split is intended (and derive both, per
  #346 finding 2, because they agree by accident today), diff every entry body for unintended
  edits, and keep a pre-write backup as the fold script now does
  · **do not start without his ruling on S1/S2/S4** — the entries are his words, and S2 in
  particular may carry meaning a single band cannot (*"urgent, not yet certain which"*), which
  only he can say · **blocked on that ruling**, not on any code
  · **UNBLOCKED — he ruled at 01:23 (S1 split, S2 rec) and the scope CHANGED**, so read
  this before starting: the type-classification item is **out**. His S4 answer plus the
  measured SQLite facts settled `type` as a lookup table with an FK rather than a closed
  set welded into the schema, so nothing needs classifying by hand — a new type is one
  INSERT. That removes the open-ended item and leaves only bounded ones
  · **what remains: 3 combined entries and 4 compound bands.** The 6 bandless entries are
  his call and were not ruled on — leave them unless he says otherwise, since an absent
  band already means P2 by contract and writing one changes meaning
  · **and the split is not just a split**: S1 asks for the relation to become explicit, so
  each combined entry becomes two tasks PLUS a `related` row (symmetric, n:n) — not a
  `depends` row. `#250/#251` is *"Missing-aid answer disclosures + node disconnect proof"*,
  two pieces of one landing, which is `related`. Propose and report the classification for
  all three rather than deciding silently; he said he was unsure what they were
  · in the Markdown there is no `related` table yet, so the split entries must carry the
  relation in prose the migration can read — decide that shape with #346, or the
  normalisation destroys the only record of which two tasks were one piece of work
  · **HALF LANDED `638b32a`: the prose shape is decided, contracted and checked.** The
  marker follows the origin marker's key-and-bold idiom, both entries of a pair carry it,
  and `lint.check_related_markers` ERRORs on a one-sided pair, a dangling id, a
  self-reference, two markers, the wrong case or an empty value. Contract in
  `file-formats.md`; red-proved with 10 injections, 8 discriminating to a single test
  · **it can ERROR rather than WARN because of a measurement**: `watch.ledger_entries` finds
  zero such markers in 180 entries, so there is no legacy to grandfather and the first one
  written is checked the day it is written
  · and the same scan corrected one assumption in this entry: **all three combined entries
  are under `## Recently landed`, not Open** — so the split edits history, not in-flight
  work, which lowers the risk materially and means no dreamer's context goes stale under it
  · `depends` was deliberately left unspecified: its Markdown form has to reconcile with the
  **29 entries that say "blocked on #N" in prose**, which is its own decision and its own
  task, not a line to smuggle into this one
  · **SPLIT LANDED `9fec0bf`: 3 combined entries are now 6, and history wrote them.** Every
  original single-id entry survives in git history with its own title, band, type and origin,
  so nothing was reconstructed from the combined summary — the six are the originals' identity
  merged with the summary's facts about what shipped
  · **his uncertainty is answered: all three pairs are `related`, none `depends`**, for one
  uniform reason — each was *co-delivered, never sequenced*, so no half was a precondition for
  the other. #251 is the proof that #250's node really goes; #292 and #293 are two bugs from
  one message of his at 01:17; #138 and #156 are two Claude Code hooks that had to ship in one
  plugin or not at all
  · **two facts the combination had silently lost, and history still had**: both pairs carried
  an unknown origin while the originals recorded loop/loop and human/human — four
  governed ids marked unknown when nothing was ever actually unknown (repaired; lint's origin
  coverage moved 127 → 129) · and **the `P1/P2` band was never ambiguity at all**: it is
  #250's P1 and #251's P2 concatenated, so the split resolved it for free
  · **what remained was smaller than it looked**: only **three** genuine compound bands, all
  `P0/P1` on single-id entries — #288, #274, #263. Those are the ones S2's caveat was written
  for (*"if any of the four still says something, say so and it stays"*), and the fourth turned
  out to be a mechanical artefact rather than a judgement call
  · **CLOSED, and the three bands STAY.** Each of them still says something: #288 is a
  security boundary, #274 and #263 sit on the durability path of his own words, and in each the
  band means *at least P1, possibly the very top, not yet certain which*. Overwriting that with
  one value would delete a real judgement he made about his own priorities, which is exactly
  what the caveat exists to prevent — so no entry was edited
  · **and the schema does not need to be loose to hold them**, which was S2's only real
  objective: a compound *value* is what opens the set, but the *uncertainty* is one bit. A
  closed band column plus `priority_uncertain` (0/1) records `P0/P1` as band P1 with
  "could be higher" beside it — orderable, groupable, no compound value anywhere. The band
  recorded is the LOWER urgency of the pair, because that is what the prose supports without
  inventing a promotion he never made. Written into `task-store-schema.md` under S2
  · so S2 answers **yes** — `priority` closes — with zero edits to his entries, and #353 is
  complete: 3 combined entries split, the relation contracted and checked, 4 compound bands
  accounted for, the 6 bandless entries deliberately left as his call

  · related: **#395, #440**
- **#352** — Standardize the duplicated ledger parsing before the store migration ·
  P1 · refactor/prerequisite · origin: **human** · **human via watch 2026-07-28 01:05**,
  as a follow-up on the #346 ask: *"before we work on this proper we should standardize the
  current python parsing so we fix the duplicate code issues and such now in case it matters
  as we migrate and things"* · **his reasoning is the strongest case for doing it now**: a
  duplicated parser is duplicated work to re-point at cutover, and whichever copy nobody
  re-points silently becomes a reader of `tasks.md.deprecated`
  · **already measured, do not re-derive it** (#346's design, §"The invariant #294 says to
  verify"): `ledger_entries` has **two implementations** — `lint.ledger_entries` and
  `watch.ledger_entries` (`watch.py:6599`), whose docstring claims it is lint's *"VERBATIM
  (a test pins the two identical)"*. The logic IS identical; the source is not — watch's copy
  drops the type annotations and rewrites the docstring, so a source-equality check fails on
  a pair that behaves the same · **the pin is behavioural and single-fixture**:
  `test_watch.py:863` asserts equality on ONE hostile input, which is a better pin than
  source comparison and a weaker one than it reads · **three callers**: `lint.py`,
  `watch.py`, `task_origins.py`
  · rec: one module both import, so the pin becomes unnecessary rather than better — a test
  that two copies agree is a test that should not need to exist · the seam matters more than
  the tidiness: #346's read surface and #294's cutover both re-point "the reader", and that
  phrase is only meaningful once there is one
  · **check what else is duplicated before assuming this is the only pair** — `parse_ledger`,
  the section-splitting, and the origin-marker parsing are all candidates, and #346's design
  found this pair only because it went looking for one thing
  · **blocked on `watch.py`** (`ccc-glm52-336` holds it) for the import change; the extraction
  and lint's side can be prepared first · when the module lands, delete the "VERBATIM" claim
  rather than updating it

- **#351** — `/file` should highlight source, run wider, and not wrap lines · P2 ·
  dashboard/readability · origin: **human** · **human via watch `add-idea` 2026-07-28
  01:03**, typed from `/file?p=lint.py` — the page he was reading this session's work on:
  *"syntax highlighting for source code files, and a bit wider of a body + no line
  wrapping."* · three separate changes in one sentence, and they are not equally sized
  · **the highlighter already exists and must be REUSED, not rewritten**: `#339` landed
  build-time tokenising in `review_artifact.py` (`_scanner`/`_scan`/`highlight`, the
  per-language specs, and `#348`'s `sql`), it emits `tok-` spans with CSS and ships no
  script, and its round-trip is proved byte-exact through unescape/tokenise/re-escape ·
  so `/file` wants the same tokenisers behind a shared seam rather than a second
  implementation — two highlighters would drift, and the artifact one is the tested one
  · **but the contexts differ in one load-bearing way**: an artifact is built once and
  frozen, while `/file` renders on request, so tokenising per request is work repeated
  for a result that cannot change per file version — decide caching explicitly (by path +
  mtime, or by content digest) rather than inheriting "build-time" reasoning that no
  longer applies · also `/file` serves ANY file, so the language comes from the extension
  and an unknown one must render plain, per #339's never-guess rule
  · **"no line wrapping" is a real trade, not a preference to apply blindly**: the frame
  currently wraps (`white-space:pre-wrap`), and turning that off means horizontal scroll
  on long lines — which is what he asked for and which interacts with the wider body he
  asked for in the same breath. Both together suggest he wants to read code as code. Check
  the narrow-viewport consequence before assuming it generalises, and confirm a
  horizontally scrolling `<pre>` does not scroll the PAGE sideways (`watch-design.md`'s
  contract: wide content scrolls inside its own container)
  · **blocked on `watch.py` being free** — `ccc-glm52-336` holds it, and #336 is working
  on `/file` right now, so this is adjacent enough that landing both in one pass may be
  cheaper than two: fold it into that lane rather than racing it · #348's sql support
  means his own schema docs would highlight too once this lands

- **#349** — `lessons.md` is 117 entries and 1476 lines, and a lesson in it failed to
  prevent its own repeat · P2 · dogfood/loop reliability · origin: **loop** · found
  pruning it during the maintenance rotation · **the evidence is specific and it is
  tonight's**: line 757 has recorded since **2026-07-25** *"Revert a deliberate RED
  injection with the inverse of the injection, never with `git checkout <file>`"*, naming
  the exact consequence — destroyed uncommitted work sharing the file. On **2026-07-28**
  the coordinator did precisely that while red-proving #348, lost the feature under test,
  and produced two proofs that failed for the wrong reason while looking clean. The
  lesson existed, was correct, was specific, and was not read
  · **so the failure is not the writing, it is the reading**: nothing re-reads 1476 lines
  before acting, and the file has no retrieval path other than a human scrolling it. The
  same file already knows this about itself at line 1002 — *"grepping a dream for its own
  phrasing does not tell you whether its lesson is already recorded"* — and that is how a
  duplicate of 757 got appended tonight before the pruning pass caught it
  · **the graduation rule is working and is not enough**: `SKILL.md` says prune when a
  lesson becomes a guardrail, and #343's `check_author_tags` earned exactly that pruning
  in this pass. But a lesson that *cannot* become a check (a habit, a shell hazard, a
  judgement) has no exit and no index, so the un-graduatable ones accumulate — and they
  are the ones that need to be recalled at the moment of acting
  · rec: **not** summarisation, which loses the evidence half the format exists to keep
  (`file-formats.md` says why). Candidates worth an IGC: a keyword/context index the loop
  consults at the top of the specific acts these lessons govern (before an injection,
  before writing a parsed file, before a worktree dispatch); splitting by act rather than
  by date so the relevant dozen is readable; or a check that refuses a *new* lesson whose
  first sentence is a near-duplicate of an existing one, which would have caught tonight's
  · **do not implement before asking him** — this changes a durable record he reads, and
  the cheap wrong answer (aggressive pruning) destroys evidence that is the point of the
  file

- **#346** — Design #294's task entity schema and read-only CLI surface, the half that
  is not gated on #263 · P1 · schema/CLI design · origin: **loop** · split from #294
  2026-07-28 00:26 while acting on his `do-next` steer (*"we need to start working on
  the sqlite db and cli next. it feels like it's becoming a blocker"*), because the
  honest answer to that steer was neither "blocked, wait" nor "start it all"
  · **the separability argument, which is the whole justification and must be
  attacked before this is built**: the gated question is #264's — *"decide whether it
  shares #263's journal or uses a task-state outbox, but never dual-write two fallible
  truths"* — and that is a question about how a **transition** becomes durable. The
  columns describing a task at rest do not vary with the answer: a journal-sourced
  materialised view and an outbox-sourced table expose the same entity. So this task
  covers only (a) the entity schema, (b) the read-only CLI verbs over it, (c) the
  migration script's **parse and report** half, and explicitly **not** any write verb,
  claim, lease, CAS, history table, or cutover
  · **acceptance is already enumerated** — do not re-derive it, it is the folded read
  requirements in #294: per entry `id`, `title`, priority band, `type`, origin marker
  (`human|loop|unknown`, exactly one — `lint.py` already enforces that on the Markdown
  and the schema must not weaken it), owner / blocked-on, dependency ids, `open|landed`
  state, and #281's rendered free-text tail; set-level filtering (open-only **with a
  landed count**), sort by priority-then-id AND by a user-chosen key, single-entry fetch
  by id for `?t=<id>`; plus #289's per-artifact decision enum `pending|accepted|rejected`
  with a stamp and one owning question, where **absence of a record is a distinct
  `unlinked` state and never `pending`**, and two questions claiming one artifact with
  conflicting decisions is detectable as an error
  · **the invariant to verify rather than assume** (#294 says so and it is the one that
  bites): the migration re-points #281's entry-level reader *and nothing else* only while
  that reader is the sole parser. `watch.py:6599` `ledger_entries` is documented as
  lint.py's copy **VERBATIM, with a test pinning the two identical** — so there are
  already two call sites of one shape, and the schema work must establish which of them
  is the seam before claiming a single reader
  · deliverable is a design doc under `.dreamwork/docs/plans/`, paired with a review
  artifact and a questions entry per the standing review rule · rec: do NOT create
  tables or ship a CLI under this id — a schema that exists before #263 is ratified is a
  migration he warned twice about, and a design that exists is the thing that makes the
  gated half small
  · **HIS 01:05 NOTE AMENDS THE CLI HALF, and one part of it is a prerequisite** (watch
  follow-up on the #346 ask, read from the artifact): *"with the cli btw, we should consider
  writing it in something other than python. We ideally want a small (fast to load) portable
  binary + quick to recompile. It should also support extensions kind of like how git does,
  eg `git-thingy` can be run `git thingy`. that way we can have python modules (or go or rust
  or ocaml) also before we work on this proper we should standardize the current python
  parsing so we fix the duplicate code issues and such now in case it matters as we migrate
  and things."* · three things, and the design must not treat them as one · **(a) the
  implementation language is now an OPEN DECISION, not Python by default** — the design doc's
  CLI section assumed Python implicitly because everything here is Python, and that assumption
  is withdrawn rather than defended; his stated criteria are load time, portability and
  recompile speed, which are exactly the criteria Python fails · **(b) git-style extension
  dispatch** (`dreamwork-thingy` on PATH invoked as `dreamwork thingy`) is a real
  architectural constraint on the CLI's shape and it is what makes (a) affordable: a compiled
  core with a dispatch convention lets a Python/Go/Rust/OCaml extension exist without
  rewriting it, so the core's language stops being a lock-in · **(c) is an instruction to act
  first**: *"before we work on this proper we should standardize the current python parsing so
  we fix the duplicate code issues"* — that is #352, filed, and it is the same duplication
  #346's design measured (two `ledger_entries` implementations, three callers, one behavioural
  fixture). His reason is the migration, which is the strongest possible argument for doing it
  now: a duplicated parser is duplicated work to re-point at cutover, and the copy nobody
  re-points becomes a reader of a deprecated file
  · **HIS 01:13 NOTE INVERTED THREE OF THE FOUR RECS** — *"we can make the shape as
  restrictive as we want before migrating because we won't need the python / plaintext
  versions for much longer"* · filed as **#353**; artifact and design doc rebuilt to say so
  · **and finding 4 of that design was WRONG, corrected in place 01:18**: it reported 60
  unmarked origins against 8 explicit `unknown` and read the split as audited-vs-untouched.
  It is **50 and 12**, every unmarked entry's greatest leading id is below 216, so absence is
  the contract's forward-only cutoff and is derivable — there was no distinction to preserve
  and **S3 is withdrawn as a question**. Cause: the scan tested for the literal marker prefix with a
  single space before the bold token, which misses every marker that wraps across a line
  (the key and its bold value separated by a newline and indent). Writing that pattern out
  here in full ERRORs this very check, which is its own small lesson about prose that quotes
  a parsed token. `lint.py` contradicted the
  measurement and lint was right, which is the lesson worth keeping — **a measurement that
  contradicts an existing check is a reason to doubt the measurement first.** The other four
  findings were re-measured wrap-tolerantly and all stand
  · **the S1–S4 ruling is still outstanding** — this note amends the CLI, it does not answer
  the entity questions, so the ask stays open
  · **design landed `03a5996`, artifact `31be2f1`, ask `9150e33` — awaiting his ruling on
  S1–S4.** The separability argument survived contact: the five findings are all about the
  entity at rest and none of them touched the transition question, which is the evidence
  that the split was real rather than convenient · the design's own §"Open questions"
  narrowed to four, all the same question — how much of today's looseness is a feature to
  preserve and how much is an artefact to resolve at cutover · next increment under this id
  is the eight red-first fixtures, which can be written before any ruling because each one
  names the production line that must change for it to fail; do not create the schema to
  run them
  · related: **#418**

- **#345** — `gitrow`'s motion assertions red under load, so `just test` is not
  reliably repeatable · P2 · verification reliability · origin: **loop** · found
  validating #326 · `gitrow.mjs:222-223` assert `t.positions >= 8` — a count of
  distinct sampled positions during the row's opening — so under CPU contention the
  sampler observes fewer rAF frames and the guard reds on code that is correct
  · **measured, not suspected**: red inside a full `just test` running alongside two
  `ccc` agents and the human's own work; **PASS alone on a quiet machine, same
  commit**, and the identical `closing` assertion at `:302` passed even in the red run
  · this is **already documented as expected** at the justfile's head — *"The browser
  half is intentionally serial; run it on a reasonably idle machine. Its motion checks
  sample rAF geometry and heavy contention can produce honest 'not enough frames'
  reds"* — which is exactly why it is worth a task rather than a shrug: a known
  false-red teaches the reader to discount reds, and `just test` is the whole of
  verification here (there is no CI). The next honest red in that guard will be read
  as contention and merged past
  · **do not simply lower the threshold** — 8 positions is what distinguishes travel
  from a teleport, and weakening it removes the only thing the check does. The
  directions worth exploring: assert on the geometry's SHAPE (monotone progress
  between first and last sample) rather than on a sample count, which is
  frame-rate-independent; or have the sampler report the frames it actually got and
  SKIP with a stated reason below a floor, so the output says "could not measure"
  instead of "did not move" — an unmeasurable check reporting failure is the same
  quiet-wrong-state this repo keeps paying for
  · **whichever way it goes, red-prove it against a real teleport**, because the
  failure mode of any fix here is a check that stops catching the bug it was written
  for — and `transitions.md` opens by saying an end-state assertion cannot fail on a
  motion bug · audit the other rAF-sampling guards for the same shape while in there
  (`motion`, `morph`, `morphhold`, `headertravel` are candidates); report, do not
  widen scope

- **#344** — A per-row control on `/tasks` that points the loop at that task · P2 ·
  feature · origin: **human** · **human via watch 2026-07-27 23:39**, answering
  #281 Q6: *"yes, can be a followup (add to tasks in that case)"* — the filing is his
  explicit instruction, not the loop's inference · each row on `/tasks` carries a
  small control that sends exactly what he types today as `do-next: #<id>`, so aiming
  the loop is one click on the row he is already reading rather than retyping the
  number into a composer elsewhere · **the transport already exists and must be
  reused, not reinvented**: the composer's `do-next` path (`watch.py:280` `COMMANDS`,
  the events-log write at `:7807`) is the same channel, so this is a second surface on
  one mechanism — a second way to enqueue a steer would be a second thing able to
  disagree with the first
  · **sequenced deliberately after `/tasks` reads correctly, which is the half he
  agreed to**, and the reason is recorded here so it survives whoever implements it:
  a list you only read is safe to get wrong, but a list that can start work is a
  control panel, and a mis-click redirects the loop. How much authority a page holds
  is his call, so the read surface earns trust first
  · that makes the interaction design load-bearing rather than decorative: the
  control must be unmistakable about what it will do before it is pressed, must not
  sit where a scanning eye lands, and needs a confirmation or an undo path — a
  silent successful mis-click is the failure mode, and it is invisible precisely
  because it succeeds
  · **P2, not P1** — his own sequencing puts it behind the read work, and #281's
  page is not landed yet · blocked on #281



- **#342** — Delivery mode for dashboard commands: batched vs instant, and a read
  cursor so polling is possible at all · P2 · design + reliability ·
  origin: **human** · **human via watch 2026-07-27 23:28** (typed on the #229/#270
  topic-chats v2 review): *"mode toggle for delivery method: either we deliver like we
  do now (instantly, pushed straight to agent), or we could have a queued delivery
  method where the agent gets all the updates at once at the start of the queue.
  Batched delivery … will be more efficient probably, but it won't be as responsive
  unless the agent is mostly doing orchestration. This probably depends on the cli
  update so there's a consistent way for the agent to like get any new messages for it
  (note: this should be part of the agent's loop \*always\* in any case, as their might
  be low urgency stuff that we don't want to interrupt the agent for). In fact, things
  like add task should not interrupt the agent, but 'do now' should. So there's maybe
  some sensible defaults, too. However, things like answers/notes to questions/reviews,
  that is something where we need the toggle to know how to handle properly. This
  should also help with the agent being overwhelmed or forgetting to process some
  things."*
  · **his premise verified**: `kind` reaches the log as nothing but a string prefix
  (`watch.py:7807`, `f"command via watch…: {kind}{body}"`), so no consumer
  differentiates urgency — an `add-idea` wakes the coordinator exactly as hard as a
  `do-now` today, which is the interruption cost he is describing
  · **the load-bearing half is not the toggle, it is the cursor, and it is missing.**
  The skill already instructs the loop to check `watch-events.log`'s mtime each tick,
  so a poll-based backstop is *specified* — but mtime says only that the file changed,
  and **there is no cursor, offset or seen-marker anywhere** (`.dreamwork/` has none;
  `file-formats.md` states none). So a polling loop cannot tell which lines are new: it
  must hold that in session memory, which is precisely what compaction destroys, on a
  log already 57KB. Batched delivery is therefore not merely unimplemented, it is
  currently *unimplementable* — and so is the "always part of the agent's loop"
  guarantee he attaches to both modes
  · that also names the failure this fixes rather than adds to: the command channel is
  **push-only and not durable** — his `do now:` exists only as a line in this file, the
  write is best-effort, and a resumed or compacted session with no tail monitor armed
  loses it with no error on any surface. A cursor converts delivery from
  monitor-dependent to read-dependent, which is the same "nothing fails quietly"
  commitment applied to the one channel that still can
  · sensible defaults he stated: `add task`/`add idea` do not interrupt, `do now` does;
  answers and notes on questions/reviews are the genuinely ambiguous class and are what
  the toggle is *for* — do not quietly pick for him there
  · scope note: the toggle half depends on **#294**'s CLI (his own "depends on the cli
  update", and the same CLI-only seam he set for `#229`/`#287`), so it waits. The
  cursor half does **not** depend on the CLI and is worth landing first — it is what
  makes the documented mtime check honest. **One migration, not two**: a cursor is
  durable state, so its shape folds into the sqlite migration's scope at approval time
  rather than landing as a file that must then be converted
  · **the cursor half is #263, not new work** (found while folding his 23:33
  `do-next`): #263's reviewed user-event journal already specifies a durable record
  with a hash-chained read cursor and a projection CLI, which is precisely what the
  always-poll guarantee needs. So this task does not design a cursor — it consumes
  #263's and adds the per-kind interrupt policy and the toggle on top. Recorded
  because filing it as independent work would have built a second cursor able to
  disagree with the first, which is the failure #263 exists to prevent
  · blocked on #294 for the toggle, #263's E1 answer for the cursor it consumes

- **#341** — Two answers on one OPEN entry silently keep only the last · P2 ·
  reliability · origin: **loop** · from #254's design agent · `_parse_entries`
  overwrites `cur["answer"]` and resets `answer_at`, so a second
  `Answer (via watch, …)` bullet on an entry in `## Open` discards the first
  answer's words from every surface · **coordinator correction, and it changes the
  priority**: the witness the report cited (the two byte-identical `rec` bullets at
  18:48) is in `## Answered`, where retaining both is DOCUMENTED behaviour and the
  `→ answered` head carries the resolution — so that entry is not evidence of loss ·
  measured at `0f9d753`: **0 open entries currently have two answers**, so the defect
  is **latent, not active** · it stays P2 rather than being dropped because #274 is the
  thing that reaches it: duplicate delivery is what puts two byte-identical answer
  bullets on one entry, it has been witnessed twice (17:48 and 18:48:53), and on an
  OPEN entry the second would overwrite the first · so #341 and #274 are one story and
  should be fixed with a shared fixture · red-prove by constructing the open-entry case
  the live file does not contain, and assert the precondition that both answers differ
  in text, or the check cannot tell overwriting from idempotence


- **#338** — Bundle `use-igcs` with Dreamwork, because planning depends on it ·
  P2 · packaging/method · origin: **human** · **human via watch `add-idea`
  2026-07-27 23:09**: *"we should bundle use-igcs with dreamwork, it's a core part
  of planning effectively"* · the skill is real and already in use here:
  `~/.llm-general/skills/use-igcs` — Critical Fallibilism Idea-Goal-Context
  triples, where each (idea, goal, context) cell is a **decisive pass/fail** and
  the answer is the single non-refuted option, explicitly instead of scoring or
  pro/con lists · **this loop already argues in its shape without naming it**: every
  `Rec X … **Y** refuted: …` question in `questions.md` is an IGC row, and #289's
  own ask says *"Read-only IGC compared a sidecar index, embedded question
  metadata, and a hybrid"* · so the task is less about acquiring a method than
  about making the one already in use explicit, available on a fresh install, and
  consistent · **the mechanism needs deciding and there is a real hazard**:
  `plugin_resolver.py` resolves `ud-dreamwork-*` packages declared in
  DREAMWORK.md's `## Plugins`, checking bundled `plugins/` first, and it
  deliberately never scans global skill directories — so the obvious move is to
  vendor a copy into `plugins/`, and that **forks a skill that lives in the shared
  KB**, which then drifts silently in whichever copy is not being read · rec:
  reference/adapter rather than copy — the loop declares the dependency and states
  what it needs from IGC, and a vendored copy is the fallback only if a fresh
  install genuinely cannot reach the KB · **the same instinct he stated one minute
  earlier on #287** (*"we don't want to rewrite the skills … a generic wrapper /
  adapter layer"*) applies here and the two should be decided together, because a
  fork-by-vendoring answer here contradicts the adapter answer there · also fold
  the method into DREAMWORK.md if it is confirmed as how he wants decisions argued,
  since that is a durable preference and not a packaging detail

- **#337** — `do next` should fall back to `add idea` after submitting, as
  `do now` already does · P2 · dashboard UX · origin: **human** · **human via
  watch `add-idea` 2026-07-27 23:01**: *"for the command composer, when the user
  submits something under 'do next' it should autoselect 'add idea' after
  submitting (just like 'do now' does)"* · **his premise verified exactly**:
  `watch.py:5567` is `if (kind === 'do-now') setKind('add-idea');` — one kind is
  special-cased and `do-next` is not · the literal fix is one condition, but
  **that is the wrong shape and the file says so itself**: `COMMANDS`
  (`watch.py:280`) is plugin-extensible (#86) and its comment states *"nothing
  downstream assumes a fixed set"*, so a hardcoded list of two kinds is a third
  place a new kind has to be remembered · rec: give the kind a property (e.g.
  `sticky: false`) and have the submit path read it, so `add-idea` is the only
  sticky kind and every steering kind — including `maintenance` in the hover
  menu and anything a plugin adds later — decays to it · **the reason this is
  worth more than a convenience**: a mode that persists silently raises the
  authority of his NEXT message, so the composer should decay toward the least
  dangerous kind rather than hold the most recent one; that also makes it
  consistent with #257's danger treatment for `do-now` instead of orthogonal to
  it · obeys `transitions.md` for the mode change itself, which already has an
  idiom (#300 morphs the run-mode descriptions through one popover) · blocked on
  `watch.py` being free; sequence after #336, which is his newer and higher steer
  · **UNBLOCKED — `#336` LANDED and nobody re-triaged this** (found by `#420`'s census, machine-verified against `parse_ledger`, re-verified by the coordinator 2026-07-28 15:53): the `do next` → `add idea` fallback's prerequisite landed. **Startable now.** This entry is one of **ten** with the same shape, which is why the census was worth running: a blocker that clears is invisible from the blocked side, so nothing ever re-reads it

- **#328** — Add `/tasks2`, the wide two-pane task triage layout · P2 · dashboard
  feature · origin: **human** · **human via watch 2026-07-27 21:47** · his answer
  to #281 Q1: the list-plus-detail wide layout IS wanted, but as a SECOND route,
  with `/tasks` kept as the simpler one-column variant — "We can do them in
  whichever order you prefer" · shares #281's data contract and entry-level
  reader exactly; adds no second parser and no new task database · `/review` is
  the existing precedent for a deliberate width exception (`watch-design.md`) and
  #305 just reworked its split, so inherit that idiom rather than authoring a
  second one — including the draggable divider · obeys `transitions.md` for the
  pane transitions and for anything that appears or departs on selection ·
  blocked on #281 landing first (its reader, URL contract and row rendering are
  the parts `/tasks2` composes)





- **#322** — Allow pasting images into the command composer · P2 · dashboard
  feature · origin: **human** · **human via dashboard composer 2026-07-27
  21:20** (verbatim: *"add-idea: allow pasting images to command composer"*) ·
  captured from `watch-events.log`, which is the only place that command exists ·
  he typed it while on `/review?p=tasks-page.html` — the #281 design questions —
  so it is an aside, not an answer to them · **open design questions, none
  decided**: where a pasted image GOES (a file under `.dreamwork/`, and if so
  whether it is committed or gitignored), what the composer shows once one is
  attached, how it reaches the loop (a path in the events line? a sidecar?),
  size and type limits, and whether the same affordance belongs on the review
  dock and the answer box or only here · note the events log is a single
  best-effort LINE per command, so an image cannot ride in it and this needs a
  durable sidecar the loop reads — that constraint shapes the whole design ·
  touches `watch.py` (held by an agent right now), so filed not started


- **#319** — Guard servers should bind port 0 and let the OS assign · P2 ·
  tooling · ~40m · origin: **loop** · goal: remove a failure class rather than
  clean up after it ← DREAMWORK.md *Nothing fails quietly* · #203's own
  recommendation, and the better fix: the reaper cleans up orphans, port 0
  means there is no fixed port for an orphan to squat and no readiness probe can
  ever grade somebody else's server · deliberately deferred out of #203 because
  it needs `watch.py` to report the port it actually got and another agent held
  that file · **the reaper stays** either way — it handles servers already
  running and the SIGKILLed-lane class — so this is not a replacement · needs:
  `watch.py` reporting the assigned port (it already persists
  `.dreamwork/watch-port`, so the mechanism exists), the `guards` recipe reading
  it instead of passing one, and the guards themselves taking the port they are
  given, which they already do · check that a run with no port argument still
  reaches its own server and not another


- **#275** — Research public Dreamhub authentication informed by shoo.dev · P2 ·
  security research/design · origin: **human** · **human via answer 17:48** ·
  evaluate shoo.dev's actual primary-source auth/deployment model and alternatives
  for public Dreamhub; define identity, TLS, session/cookie, CSRF, authorization,
  secrets, reverse proxy and threat model · public/WAN support remains forbidden
  until a reviewed design is approved
  · research + design landed `4b49ecb` (ccc-glm52-275, worktree removed); ask open
  in questions.md with `.dreamwork/review/hub-public-auth.html` · **the premise was
  corrected by the research**: shoo.dev is not a tunnel/expose tool but a hosted
  Google-OAuth PKCE broker returning an ES256 id_token, so identity is Google-only ·
  its GitHub repo returns 404 (coordinator re-checked independently: still 404), the
  site says "SUPER EARLY WIP", and no security review or threat model exists, so the
  server is unauditable · and this hub is stdlib-only Python, which cannot verify
  ES256 in-process — coordinator confirmed `cryptography` 49.0.0 is the third-party
  path · recommendation: read-only loopback hub behind a mature authenticating
  reverse proxy owning TLS/identity/session, allowlist at the proxy, and a redacted
  `/summary.json` replacing `/data.json`, which today serves DREAMWORK.md,
  questions.md and lessons.md in full · shoo fits later as an optional IdP BEHIND
  the proxy, never as the boundary · artifact verified offline-clean by the
  coordinator, not on report: zero external resource loads, 6 citation links, no
  `@import` or outward `url()` · public/WAN serving REMAINS FORBIDDEN until he rules
  on the six questions; nothing was implemented and no bind address or flag moved
  · **NOT landed, and #306's check is why.** The research half is done and merged,
  but this task's own terms are "public/WAN support remains forbidden until a
  reviewed design is APPROVED" — so it is blocked-on-human, not complete. Closing it
  tripped `check_landed_asks`, which correctly reads an open ask naming only landed
  ids as a forgotten fold; the guard caught the coordinator, not a false positive ·
  **blocked on: his ruling on the six questions** in questions.md
  · **PARTLY ANSWERED and SPLIT, human via watch 2026-07-28 01:39.** He answered Q1 by
  refusing the dichotomy: it is not public-or-private, it is **two products** — self-hosted
  over a tunnel/mesh/LAN, and a hosted subscription service. Those left this entry as
  **#360** (self-hosted, ssh-derived auth, and it redirects the reverse-proxy
  recommendation this task landed) and **#359** (the SaaS, where stdlib-only does not
  apply). He also settled the constraint that shaped the whole design: *"wrt stdlib only,
  that only applies for self-hosted stuff"* · Q2 is redirected rather than answered — he
  does not want a third party's control plane as the boundary of a self-hosted tool ·
  **still open on this entry**: Q3 read-only vs read+write, Q5 the redacted
  `/summary.json`, Q6 the allowlist. Q4's identity provider question is now #359's, since
  the self-hosted half has no IdP at all under his direction

- **#298** — Explain each burndown column on hover, focus and touch · P2 ·
  Web UI feature · 25m · origin: **human** · **human via watch `add-idea`
  14:10** · inspecting a chart column should reveal the exact interval/date,
  open-task level, arrivals and completions that its geometry currently encodes,
  plus source/coverage state where relevant; this is detail *about values already
  summarised on screen*, preserving #142's more-detail rule rather than hiding a
  second dataset in hover · one restrained chart-native inspector follows the
  active column without obscuring neighbours, arrives/departs through the page's
  atmospheric transition, and snaps under reduced motion · hover cannot be the
  sole path: every column is keyboard-focusable with a useful accessible name,
  focus shows the same inspector, and tap selects/dismisses it without breaking
  chart scroll on mobile · red-first guard proves exact values against a
  controlled ledger history, edge-column clamping, hover→focus parity, Escape/
  blur/tap dismissal, intermediate arrival/departure states and reduced-motion
  function · deterministic desktop/mobile captures + visual-review-and-fix ·
  relates #218's filed-to-landed median but does not depend on it

- **#297** — Make every dashboard disclosure travel instead of jump · P2 ·
  Web UI bug · 60m · origin: **human** · **human via watch `add-idea`
  14:09 (duplicate delivery recorded once)** · expanding/collapsing git rows,
  dream filenames and miscellaneous dashboard details currently changes their
  own or neighbouring positions abruptly; inventory every disclosure surface
  and either keep its anchor geometrically stable or carry all surviving
  elements through one smooth atmospheric fold/travel · the human's "anything
  that could move should have CSS for smooth transitions" states the visible
  outcome, not permission for a global `transition: all`: reuse the established
  `travelCard`/`foldDetailsLocal`/FLIP + body arrival/departure idiom so layout
  geometry is actually interpolated and reduced-motion keeps function while
  snapping · red-first guards must drive every real disclosure family, bound
  each trace to its click, count distinct intermediate positions, prove no
  overshoot/snap at settlement, and cover reduced motion · `transitions.md`
  already calls the plain `expand()` peeks (dreams, archive, Markdown files,
  status overflow) unexamined; include commit rows and any other discovered
  native `<details>` rather than fixing only the reported examples · relates
  #169, which adds expanded-state prominence but does not replace continuity

- **#295** — Add subtle dithering to background shaders · P2 · visual/shader
  quality · origin: **human** · **human via chat 2026-07-27 01:47** · add a
  restrained, resolution-stable dithering treatment to the current background
  shader and define how preserved/future shaders opt into it; reduce visible
  gradient banding without reading as grain, degrading text contrast, shimmering
  during motion, or causing device-pixel-ratio/resize seams · establish a
  deterministic fallback and performance budget, then run detailed
  visual-review-and-fix loops at representative desktop/mobile DPRs with
  crop-zoom banding evidence, geometry/source reasoning, reduced-motion parity,
  and settled screenshots until vision and geometry both PASS · coordinate with
  #278 shader performance and #280 shader registry design; do not couple it to
  #277 departing-element dreamfade
  · **APPROVED WITH AMENDMENTS, human via watch 2026-07-27 23:45**: *"hmm yeah we
  can try that. Keep both so that we can toggle. perhaps also add bayer too. We may
  want to consider creating a settings page where we can have a button group for
  these 3 options under a gfx settings section."* · so IGN at 1/255 in the final
  composite is the **default**, and the two refuted options come back as
  selectable: temporal white noise (today's behaviour) and **Bayer**, which the
  review had not proposed at all · the refutations stand as reasons IGN is the
  default, never as reasons he cannot choose otherwise
  · **one dither seam with the mode as a parameter, not three code paths** — three
  implementations would drift, and a difference between them that only shows in a
  debug layer is a difference he cannot see and would never report
  · **the gfx settings section belongs to #228, not to a new settings surface** ·
  he asked at 12:49 that settings persist and stay identical across tabs and
  separate browsers, so a gfx panel with its own storage is precisely the second
  truth that breaks that promise · the capability record becomes the SELECTED mode
  rather than a fixed `dither: "lsb-ign-v1"` string, since a fixed string cannot
  describe a toggle
  · authorises red-first implementation in an isolated worktree plus the visual
  gate; **not deployment**

- **#294** — Migrate the durable task ledger to SQLite and a tool/CLI API · P1 ·
  storage/tooling migration · origin: **human** · **human via `/answers`
  2026-07-27 01:17** · build after #264's reviewed concurrency design and the
  relevant #263 journal boundary: canonical task IDs/status/origin/priority/
  ownership/dependencies/history live behind commands such as `dreamwork tasks
  list|get|grab|cycle` rather than direct Markdown mutation; same-target agents
  use transactional claims/CAS/leases · ship a deliberately readable and
  user-modifiable migration script that dry-runs, parses every open/landed task,
  reports exact counts/IDs/digests/conflicts, backs up and imports atomically,
  verifies the database before cutover, and has explicit rollback · on successful
  verified cutover, preserve the old ledger as `tasks.md.deprecated` with YAML
  frontmatter declaring deprecation and pointing to canonical task-access and
  recovery instructions; never delete it automatically · **human via watch
  `add-idea` 14:11:** every task grab/status/priority/complete transition must
  automatically maintain the dashboard's burndown history and live status
  projection through the canonical transaction/outbox — no agent hand-editing
  `status.json`, no Git-HEAD lag, and no second derived truth; expose bounded
  snapshot/time-series APIs with crash-safe replay and prove the chart + status
  section update after real task commands · mixed-version/writer freeze,
  replay/idempotency, Git history/provenance import, dashboard consumers,
  lint/file-formats/doc-map/compaction and failure recovery are acceptance scope ·
  blocked on #264 design and relevant #263 cutover decisions · **`/tasks` read
  requirements folded in (human's steer, watch 2026-07-27 21:47: factor them in
  so we do not pay for two migrations)** — the schema and the CLI's read surface
  must serve, per entry: id, title, priority band, type, origin marker, owner /
  blocked-on, dependency ids, open|landed state, and the free-text tail #281
  renders; plus set-level filtering (open-only with a landed count),
  sort by priority-then-id AND by user-chosen key, and single-entry fetch by id
  for `?t=<id>`. The migration re-points #281's entry-level reader and nothing
  else, which is only true while that reader stays the sole parser — verify that
  invariant still holds at cutover rather than assuming it
  · **#289's review-decision record folded in too (his steer, watch 2026-07-27
  23:11 — the same "do not pay for two migrations" instruction he gave for
  `/tasks`)**: the schema and CLI must carry, per review artifact, an explicit
  decision enum (`pending|accepted|rejected`) with a stamp, its association to
  exactly one owning question, and the absence of a record as a DISTINCT state
  (`unlinked`, never `pending`) — plus the integrity rule that two questions
  claiming one artifact with conflicting decisions is an error the store can
  detect · #289 implements against this after cutover, not before
  · **NEXT-UP, human via watch `do-next` 2026-07-27 23:33**: *"I think we need to
  start working on the sqlite db and cli next. it feels like it's becoming a
  blocker. ask a question of me if you would like to discuss."* · his read is
  correct and measured: this entry is now the gate on `#287`, `#289`, part of
  `#281`, `#229`/`#270`'s CLI-only seam, and `#342`'s toggle — five lanes
  · **THE GATE IS CLEARED — he approved #263 at 01:27 with `"rec"`.** The chain
  `#294` ← `#264` ← `#263` now rests on #264's design rather than on him, and #264 is marked
  next-up. The reasoning below is kept because it still holds about what approval covers
  · **but the thing blocking it was not this task, it was his own answer on #263**,
  whose design is finished, reviewed and PASS and waits only on E1–E4. The chain is
  `#294` ← `#264` ← `#263`, so starting here without that answer means designing
  the schema against an unsettled event model — the exact double-migration he has
  warned about twice tonight
  · **the gate is sharper than "unsettled design", and the distinction changes what
  can start** (checked 2026-07-28 00:26, against the doc rather than from memory):
  `user-event-journal.md:4` states its own status as *"human approval required; no
  implementation authority"*, and its `## Approval gate` says approval *"accepts this
  contract and authorises a separate red-first implementation plan"*. So the design is
  not missing and not in doubt — it is **unratified**. That is not the same failure as
  #252's stale blocker, which was a blocker that had already been cleared; this one is
  real and only he can clear it
  · **and it gates less than the entry claimed**: the transition half of this task (how
  a grab/status/priority/complete becomes durable history, journal-vs-outbox, leases and
  CAS) is squarely #264's gated question, but the **task entity schema and the read-only
  CLI surface are orthogonal to it** — the columns that carry id, title, priority band,
  type, origin marker, owner/blocked-on, dependency ids, open|landed and #281's
  free-text tail are the same set whether transitions arrive from #263's journal or from
  a task-state outbox, because the read surface is what a materialised view exposes
  either way. Split out as **#346**, which is startable now; that also shrinks the
  post-approval half rather than racing it · so the loop's response to the steer is to ask, which
  he invited: the E1 ask has been **restated in plain terms** as a threaded
  follow-up (questions.md, 23:36), because the original was written in the loop's
  vocabulary and that is why it has sat unanswered · it also offers him the
  parallel-start option explicitly, with its cost named, rather than deciding on
  his behalf that he cannot have it
  · **#342 is the same work from the other end**: his batched-delivery idea needs a
  read cursor, and #263's journal IS that cursor — so E1 unblocks the delivery mode
  he asked about five minutes earlier, and the two steers should not be built twice
  · related: **#418, #419**

- **#289** — Show review decision status and open its associated question · P2 ·
  dashboard review-list feature/design · origin: **human** · **human via watch
  2026-07-26 23:22** · exact ask: “webui dashboard: the list of reviews should
  have ✔/✘ on the left for accepted or rejected, and also a similar icon for
  waiting/pending. could also darken the ones that are done a bit. and also,
  when i click one of the reviews, it should also open the question or whatever
  that it's associated with (works if i click the question)” · define one
  truthful review↔question association/status contract (accepted/rejected/
  pending plus stale/missing); render accessible icon + text semantics and let
  completed rows recede without becoming illegible; activating a review keeps
  the artifact open while opening/focusing the same associated question context
  the question-driven path already uses · no filename/text inference; proposal
  + transition/RM/a11y guards before implementation
  · **APPROVED for DESIGN ONLY with a sequencing instruction, human via watch
  2026-07-27 23:11** (`rec`, plus *"we should tie future versions into sqlite plan
  and/or redesign this to be done after sqlite"*) · V1 is: extend the managed
  `questions.md` entry with one explicit record per artifact
  (`Review (pending|accepted|rejected, stamp): path`), that record the SOLE
  authority for both association and decision; it moves with Open→Answered,
  survives title edits, supports several artifacts, and disappears with its
  question · **no record means `unlinked`, never `pending`**; accepted/rejected are
  only the explicit enum — never answer prose, filename, HTML recommendation, or
  whether the question is folded; two questions claiming one artifact with
  conflicting decisions is a lint ERROR; existing artifacts stay unlinked unless
  deliberately migrated, and there is no "Approved…" text scraping · **sequencing,
  which is the part that changes the plan**: the record requirements are folded
  into #294's acceptance scope now, and this entry's own implementation waits for
  #294 rather than landing a pre-migration shape that must then be migrated ·
  authority is a written design + migration proposal ONLY — no grammar, parser,
  lint, UI, icon, transition, artifact or deployment change
  · related: **#419**

- **#287** — Design a Matt Pocock skills bridge plugin for Dreamwork · P1 ·
  plugin/research/design · origin: **human** · **human via coordinator
  2026-07-26 19:56** · research the installed first-party
  `mattpocock/skills` suite, especially `writing-great-skills`, handoff,
  `CONTEXT.md`, grilling, and its established workflow norms; propose a
  `ud-dreamwork-*` bridge that modifies/enhances the normal Dreamwork protocol
  without copying or bypassing either system · coordinator and Grok iterate on
  responsibilities, lifecycle hooks, precedence/conflicts, state, authority,
  tests, and activation · record concrete authoring/runtime friction and split
  plugin-local adaptation from narrowly justified core Dreamwork improvements ·
  revised A′ removes polling/dual queues/handoff authority, scopes grilling,
  distinguishes invocation truth and rejects speculative core hooks · dashboard
  A1–A4 asks for written-spec authority only; no implementation/load authority ·
  awaiting human
  · **his conditional rec + two amendments, human via watch 2026-07-27 23:08**:
  *"Will this be a problem with the future migrations we're planning?"* (sqlite
  tasks, the CLI, threaded discussions, dreamhub/modularity) — *"If not, then rec
  also we should call the plugin `ud-dreamwork-matt-pocock-skills`"*, and *"we
  don't want to rewrite the skills … we want to create a generic wrapper /
  adapter layer that says how to unify them and what to change to make it
  compatible with dreamwork"* · **RENAMED** to `ud-dreamwork-matt-pocock-skills`
  (was `ud-dreamwork-matt-skills`) · **answered in the questions thread: no
  collision, CONDITIONAL on three constraints the spec must be written against**
  — (1) the bridge touches tasks ONLY through the tool/CLI seam
  (`dreamwork tasks list|get|grab|cycle`), never by parsing `tasks.md`, so #294's
  cutover is invisible to it rather than a second conversion; (2) grill chains use
  the EXISTING `questions.md` author-tag grammar and `human_block()` — an invented
  chain shape would break the parser and #254's rooted-exchange rule at once, and
  silently; a new tag is a reviewed `file-formats.md` change, never a side effect;
  (3) no per-target state dreamhub must learn to read — machine-local bridge state
  stays rebuildable, the `questions.md` chain stays the durable truth ·
  **on "do not rewrite"**: §9 already says *adapt* and keeps suite skills
  user-invoked, but never states the prohibition, which is how a later agent
  "adapts" by editing upstream — so the spec states it outright, and *what to
  change to make it compatible* becomes a WRITTEN compatibility note listing the
  gaps, not edits anyone makes · authority remains specification only: no
  implementation, no loading the plugin, no `setup-matt-pocock-skills`, no
  CONTEXT/CLAUDE/AGENTS edits, no tracker actions, no core changes
  · **BLOCKED ON #294's CUTOVER, including the specification** (human via watch
  2026-07-27 23:17: *"okay LGTM, but yeah let's wait till after sqlite so we don't
  have to rework anything"*) · the direction and both amendments are approved and
  the three constraints above stand; what changed is only WHEN · the loop had
  answered that constraint 1 makes the cutover invisible so the spec could be
  written now — he chose to wait regardless, and that is the standing decision,
  not a misunderstanding for a later agent to correct

- **#286** — Preserve intentional paragraph breaks in rendered question notes
  and answers · P2 · rendering/data-integrity bug · origin: **human** · **human
  via watch 18:55** · exact newlines are currently preserved in durable
  `submissions.log` JSON but question-thread Markdown rendering collapses them ·
  keep exact receipt bytes unchanged; distinguish soft source wrapping from
  intentional blank-line paragraph breaks; render the latter visibly in notes/
  answers without turning every hard-wrap into `<br>` · red-first multiline
  answer+note through server/file parse/browser render, plus copy/raw recovery ·
  **B1 accepted for DESIGN only, human via watch 2026-07-27 21:50 ("rec B1")** —
  the paragraph-aware safe writer is authorised as a written design + fixture
  proposal; grammar/writer/parser/renderer/migration changes need their own
  approval, per the ask's terms · unblocked for the design increment
  assertion; coordinate #252 Markdown rendering and #254 nested replies

- **#285** — Rebuild `ud-dw-generate` as a standalone ASCII-safe random-data
  generator · P2 · utility design · origin: **human** · **human via watch 18:50**
  · current untracked executable came from a dd2 download-page request but is
  coupled to dd2 preview infrastructure and is not the intended generator ·
  preserve it untouched; provenance/intent recorded in `ud-dw-generate.notes.md`
  · after dd2 is fixed, define CLI/output/length/entropy/error contract (hex is
  initial expected safe shape), remove dd2 dependency, add deterministic contract
  tests without weakening randomness, then decide install/commit location

- **#283** — Diagnose recurring orphaned Git index locks and dead attribution
  watcher · P1 · tooling/system reliability · origin: **loop** · blocked the
  18:27 steering commit and earlier #233 commits/cherry-picks · current witness:
  `.git/index.lock` inode `251560857`, zero bytes, uid/gid 1000, created
  `2026-07-26 17:56:57.381998849 +1000`, already ~31m old when commit failed;
  no `lsof`/`fuser` holder, no live repo Git process and no merge/rebase/
  cherry-pick state · `git-lock-watch.service` exited cleanly at 16:12 on
  2026-07-20 after ~6 days, so `Restart=on-failure` left it dead and its log has
  no current witness · watcher restarted at 18:29 and captured recurrence:
  symlink `/home/xertrov/src/dreamwork` is this checkout; lock create/delete
  repeated ~2s from 18:29:17–33, then final zero-byte create at 18:29:36 (inode
  `251691418`) remained · every snapshot saw PID `1246815`, reparented D-state
  `git rev-parse --is-inside-work-tree`, cwd KIO `filenamesearch`, but watcher
  samples all Git processes so this is correlated/candidate evidence, **not yet
  creator proof**; a short-lived writer may evade 50ms snapshots · third witness
  18:52:44–18:53:55 churned main index every ~1–2s and intermittently the LAN
  worktree index, ending with holderless zero-byte inode `251782419`; correlated
  PID remained the same D-state KIO Git · diagnose why watcher exits 0 and replace
  sampling with exec/exit or syscall-level attribution before changing mitigations;
  partial diagnosis at
  `.dreamwork/docs/research/git-index-lock-attribution-283.md`: pipeline EOF can
  exit 0 and evade `Restart=on-failure` (high confidence); 1246815 is falsified
  as creator; KIO/Dolphin was medium-confidence circumstantial only; exact argv/
  `openat(O_CREAT)` remains unknown · **L1 completed 2026-07-27 00:21** after Max
  said exactly “closed. but not sure that it's dolphin is it? if it is that's
  good to know.”: corrected read-only 60s inotify observer saw **0** index-lock
  events versus the former ~2s cadence, strongly supporting the closed window
  as trigger without proving its application or creator; later 00:46/00:57
  holderless recurrences falsified the strong window interpretation · host has no
  honest unprivileged tracer installed/permitted; L3/L2/L4 dashboard ask now
  chooses reviewed bounded audit, user-tracer research, or stop-with-unknown · no
  privileged tracing or host mitigation currently authorized · coordinate any
  future host fix with system KB entry
  · **his ruling, via watch 2026-07-27 22:58: `Close after quiet window`** (the
  loop's rec), plus *"also please copy the report to ~/.llm-general/misc-reports/"*
  — done, verbatim, with a `README.md` there recording that a report is the
  INVESTIGATION while the machine's current state is the `~/CLAUDE.md` mitigation
  entry · **so what closes this entry is now written down rather than remembered**:
  zero new orphaned `.git/index.lock` files in a quiet window after the next pi
  restart, which is the event that makes the patched `pi-powerline-footer`
  effective · until that restart happens the absence of orphans proves nothing,
  because the unpatched extension is still the one running · `git-lock-watch`
  stays armed as the witness
  · **closing condition TESTED 2026-07-28 10:10 and it is NOT met — `#283` stays open, and now for a
  stated reason rather than inertia.** The condition written into this entry is *zero new orphaned
  locks in a quiet window **after the next pi restart***. **pi has not restarted:** the newest
  instance started **2026-07-27 04:08**, before this entry's own 22:58 ruling, so the unpatched
  `pi-powerline-footer` is still the one running and any absence of orphans would prove nothing —
  exactly as the entry predicted
  · **and there is not an absence.** A live orphan exists: `~/src/amaroo/.git/index.lock`, **zero
  bytes**, stamped **21:10:15**, no holder — the same signature as every prior witness. **Left in
  place deliberately**: it is another repo's, and deleting a lock that something might legitimately
  hold is not a change to make on a guess
  · **`git-lock-watch` is armed and logging** (`systemctl --user is-active` → active), and today's
  log is dominated by **6,093** events in `~/src/dreamwork/.git/` (the symlink to this checkout),
  then amaroo 950, forum 844
  · **the KIO/Dolphin candidate is still alive and still doing it** — pid **1246815**, the same pid as
  the 2026-07-26 witness, `git rev-parse --is-inside-work-tree`, cwd
  `/run/user/1000/kio-fuse-*/filenamesearch`, parent `systemd --user`, seen again at **10:09:28
  today**. That pid was *falsified as creator*, so this is unchanged circumstantial evidence and
  **not** a reopening of the attribution
  · **separately, a documented mitigation is ABSENT — see #408**, and it means this session's own git
  activity is part of the 6,093
  · related: **#408, #416**

- **#282** — Link task references to rich hover previews · P1 · task-navigation
  feature · origin: **human** · **human via watch 18:22** · whenever `#229`-style
  references appear in Markdown docs or review HTML, link to the canonical task
  detail route and provide an accessible hover/focus panel with date, honest
  origin (human/loop/unknown), title, useful metadata and truncated description ·
  central resolver/parser, no regex rewriting inside code/pre/existing links;
  keyboard/touch behavior, confinement, transitions/RM and stale/missing task
  states · blocked on #281 route/data contract and #213 origin contract

- **#281** — Add a rich interactive `/tasks` page · P1 · dashboard feature/design
  · origin: **human** · **human via watch 18:22** · list all durable Dreamwork
  tasks at least as well designed as the rest of the Web UI; define canonical
  task detail URL, honest open/landed/blocked/unknown states, search/filter/sort,
  origin/date/priority/type/owner/dependencies, deep links and responsive/a11y
  interactions · ledger remains authority; no duplicate task database · requires
  self-contained proposal before implementation and coordinates with #213/#216 ·
  **human via chat 15:41 (Max's first steer to this coordinator):** make this the
  current lane ahead of the inherited do-next #172 · obey transitions.md and
  watch-design.md · owner: `dreamer-taskspage` holds the DESIGN phase only, in
  `.worktrees/281-tasks-page`, owning just
  `.dreamwork/docs/plans/tasks-page.md` + `.dreamwork/review/tasks-page.html` ·
  crux established by the coordinator: every existing ledger reader is id-set
  level (`parse_ledger`, `entry_origins`, `ledger_entries`), so this needs a new
  entry-level reader as ONE deep module, fail-closed to `unknown` exactly as
  `entry_origins` is, and that reader is both #213's blocking contract and the
  seam #294 later re-points at SQLite · **APPROVED with amendments, human via
  watch 2026-07-27 21:47** — implementation of the twelve increments is
  authorised (not deployment) under these rulings: `/tasks` stays the **simpler
  one-column** variant and the wide two-pane triage layout becomes a **separate
  `/tasks2`** route (#328), order the loop's choice; default sort is priority
  then newest id but **must be user-configurable alongside the filters**, not
  fixed; default filter open-only with the landed count visible and one click
  away; `?t=281` is the canonical detail URL, so #282 may hardcode it; the
  in-flight signal is labelled **"in progress"** with NO "this is a claim"
  hedge, its honesty carried instead by a hover box reading *"Reported: Xm Ys
  ago"* — freshness is a fact where "claim" is a disclaimer; a per-row write
  affordance is re-asked as its own question and is NOT in this scope · the
  entry-level reader is the ONE seam: `/tasks` must never parse the ledger
  Markdown itself, because that constraint is exactly what keeps #294 a
  one-function re-point rather than a second migration · **the one hazard measured, not
  theorised** (merged `9c00cd2`): `ledger_entries` yields ids as `int` and
  `parse_ledger` yields them as `str`, so the obvious composition — is this
  entry's id in the open set? — is `False` for every id and renders **154 of 154
  rows `unknown`** with every reader working correctly, nothing thrown and
  nothing logged · `ledger_index` normalises ONCE at the seam, to `int`, because
  that is what `?t=<id>` parses to; the plan's §9.1 case 22 holds it · blocked-behind: #327's
  drift re-review lands first, since #301/#315 moved the readers this depends on
  · in progress
  · related: **#418**

- **#280** — Design selectable preserved background shaders · P2 · visual/settings
  design · origin: **human** · **human via watch 18:12** · keep the current
  background shader and any substantial Jupiter/storm revision as separate named
  implementations; later let the user choose · define registry/interface,
  project setting/default/migration, capability/perf metadata, cross-tab sync,
  reduced-motion behavior and fallback; do not add selection UI until a future
  prototype proves a worthwhile second shader and #228 shared settings lands ·
  **#279 did not clear this gate**: deterministic technical base, visual FAIL


- **#276** — Add simple bearer-token authentication for LAN clients · P2 ·
  security design/feature · origin: **human** · **human via answer 17:48** ·
  later mode for LAN PCs/phones; distinct from initial #233 trusted unauthenticated
  LAN mode · design token generation/storage/rotation, browser entry/persistence,
  header/query avoidance, CSRF/Origin interplay, logs/redaction, revocation and
  migration before implementation · blocked on #233 base LAN mode
  · **UNBLOCKED — `#233` LANDED and nobody re-triaged this** (found by `#420`'s census, machine-verified against `parse_ledger`, re-verified by the coordinator 2026-07-28 15:53): bearer-token LAN auth was queued behind the base LAN mode, which landed. **Startable now.** This entry is one of **ten** with the same shape, which is why the census was worth running: a blocker that clears is invisible from the blocked side, so nothing ever re-reads it

- **#274** — Make duplicate Web UI submissions idempotent end to end · P0/P1 ·
  bug · origin: **loop** · witnesses: at 17:48 one #233 action produced two
  byte-identical answers ~188ms apart; #138 at 18:48:53 produced two fully byte-
  identical same-timestamp receipts and duplicate Answer bullets · preserve one
  logical answer per intent; diagnose double-click/handler versus retry; stable
  client UUID before send, receipt dedupe and idempotent application belong to
  #263/#269 · replay/concurrent same-ID fixture asserts one receipt/application;
  new ID with same text remains a distinct intentional action
  · **THIRD WITNESS, 2026-07-28 01:23, and this one is the most useful of the three**: his
  #346 answer — the ruling that turned over three of four recommendations — landed in
  `questions.md` as **two byte-identical `Answer` bullets** (verified line-by-line, not eyeballed:
  the twelve-line blocks compared equal), and `watch-events.log` carries the matching
  `01:23:21 answer` line **twice** with the same second. So the duplication is upstream of the
  file write, and both copies reached durable state
  · **why it is the useful witness: it stayed invisible for two hours.** The earlier two were
  noticed within minutes because they doubled something short. This one doubled a long ruling
  inside an entry nobody re-read, and it was found only while folding — so the duplicate is
  not merely untidy, it is **undetectable by reading**. Nothing counts answer bullets per entry,
  which is exactly the gap #357's waiting-counts would close from the other end
  · one copy was removed as part of the fold and none of his words were lost · the fold also
  showed the doubling is harmless to the RENDERER but not to the record: `_parse_entries` lifts
  every answer-tagged bullet in `## Answered`, so both copies vanished from the contribution
  list and the page looked correct with the file wrong — the silent shape this task exists for

- **#269** — Make every Web UI text draft durable and cross-tab coherent · P1 ·
  client reliability/module · origin: **human** · **human via watch 16:45** ·
  composer, answer/note boxes, future chat inputs and every later user text field
  get a stable logical input ID; autosave content before submission to one
  project-partitioned IndexedDB draft store; restore across reloads and route
  transitions; synchronise the same logical input across tabs so multiple views
  behave as one box · define ownership/conflict/clear-on-durable-receipt rules,
  privacy/retention and migration from composer localStorage · expose one deep
  module that future inputs must consume · design alongside #263 receipt boundary
  · **ESCALATED to P0 and marked next-up by him, 2026-07-27 21:35 via the
  dashboard composer** (verbatim: *"do-next: draft answers to questions on
  review pages can be lost. please have a subagent look at this asap. we must
  have persistence and never lose work on an autoreload of a page."*) — he is
  losing typed work on the page he uses to answer the loop, which is the likely
  reason #281's seven design calls have gone unanswered for hours · **the acute
  fix is out with ccc-glm52-269** (`.worktrees/269-draft`, port 39894, owns
  `watch.py`, `test_watch.py`, `watch-design.md` and a new
  `dev/capture/reviewdraft.mjs`), scoped to the per-question answer box as the
  FIRST CONSUMER of this module rather than the whole IndexedDB store · **the
  measured state**: the command composer already has the wanted mechanism
  (`watch.py` ~5062-5095 — `dw:draft:<target>` in localStorage, saved on input,
  cleared ONLY on a successful send, `try/catch` around every storage call, live
  box outranks storage per #118) but it is hardcoded to the single element
  `#cmdtext` and keys only by target, so it cannot serve N boxes; `qi${key}`
  (1700), `askbox` (2514) and `ptext` (4835) have nothing · **two loss modes, and
  the coordinator's diagnosis was WRONG about which**: I recorded that the live
  re-render was the biting mode and that "autoreload" pointed at it. Reproduction
  proved the opposite — #118's in-memory snapshot already carries text into the
  recreated node on both `/questions` and `/review`, and the real loss is the
  FULL RELOAD, which is exactly what "autoreload" named. Kept here rather than
  deleted because the brief handed that guess to an agent as the likely answer,
  and only the instruction to reproduce both modes before building stopped it
  from fixing a mode that was not broken · **the acute fix LANDED
  `0366706`, merged `e383492`**: `dwDraft` gives the per-question answer box the
  composer's rules verbatim, keyed by the question's `data-qid` title identity
  (stable across a re-render, a re-sort and the re-index between sections, where
  the positional key is not) and partitioned by target; guard
  `dev/capture/reviewdraft.mjs` is in DEFAULT_GUARDS (41 gating); the
  coordinator independently reproduced both its 12/12 green and its red, the red
  being discriminating — mode 2 PASS, mode 1 FAIL — so the guard separates the
  mode #118 covers from the one he reported · **STILL OPEN, and this is the
  remaining scope**: the project-partitioned IndexedDB store itself,
  cross-tab coherence for one logical input across views, ownership/conflict
  rules, privacy/retention, migration off composer localStorage, and the deep
  module every later input consumes. `askbox` (2514) and `ptext` (4835) still
  have no persistence at all and are the next cheapest consumers. Priority drops
  to P1 and the next-up mark is cleared: the acute loss he reported is fixed, so
  the remainder is no longer urgent
  · **DESIGN LANDED `e7d0b24` (2026-07-29 00:04, lane `wt/drafts`), design-only as scoped.** Logical id is `kind:scopeKey` inside a `data.target` project partition, keyed on the question **title** rather than a positional index, and **restore happens only into a mounted element that declares that id — no fuzzy title match**, because restoring into the wrong box is worse than losing the text. Cross-tab is **focus-wins, explicitly not last-write-wins**: a remote peer never overwrites a focused or dirty field, though the store still updates so a reload is safe. Clear-on-receipt goes through a pluggable `isDurable(response)` — `res.ok` today, `#263`'s receipt later — and **nothing behind the `#263` second gate was built**. **The acute loss he reported is already closed** by the `dwDraft` work (`0366706`/`e383492`); the remaining increments are extracting the `DraftStore` API with dual-read of old keys, then binding `#askbox` and `#ptext`, still on localStorage. It **pushed back usefully**: a blur-only or beforeunload fix would have been the wrong shape for his report because it misses an autoreload mid-sentence. Two calls are his and are filed as an `#ask` with a rebuilt artifact: **C1** cross-tab divergence policy and **C2** orphan retention.
  · **blocked-on: **human** (C1/C2)**

  · **C1/C2 answered 2026-07-29 01:12 — `rec` on both.** C1 = **R1**: offer *"updated in another tab —
  load?"*, never swap text under him. C2 = **30 days** idle GC by `updatedAt`, plus explicit *forget this*
  and *forget all for this project*. **No design decision remains open**; the build grant is asked
  separately (an authorisation-only ask, the shape `#451` wants queued apart from design rulings).
  · **CORRECTION 2026-07-29 01:43 — this entry (and the coordinator) had the shipped state wrong.** He said
  *"drafts are durable btw, ask a grok subagent to check"*, and the check (`6a6ddff`,
  `.dreamwork/docs/draft-durability-status.md`) settles it **empirically, not from comments**: typed text
  **survives a real `watch.py` kill and restart** (pid 1614177 → 1673912 on :39897) in the review dock,
  the `/questions` answer boxes **and the command composer** — the text reappeared in the fields, not
  merely in storage. Writes happen on **every input event with no debounce** (`watch.py` 4660,
  5448-5458, 6824-6828), so there is no lossy tail window; a draft clears **only** on durable success
  (3527/3571/6915) and a **failed send keeps it**. Storage is `localStorage`, not IndexedDB.
  · so the coordinator's caution about a redeploy eating his text was **wrong**, and the status is
  **(b) partly shipped** — acute durability live since `0366706`. **Remaining and still authorised:**
  the IndexedDB upgrade, cross-tab `R1`, 30-day GC, **and two boxes that are not covered at all —
  `#askbox` and the popout `#ptext`** (`#459`).
  · **BUILD GRANTED 2026-07-29 01:43, conditionally** — *"yes, provided no good reasons not to."* Taking that
  condition seriously, there is **one** and it changes the shape rather than the answer: the shipped
  `localStorage` write is **synchronous and cannot fail mid-keystroke**, whereas IndexedDB is async and a
  wedged store is a real hazard the code already races with a timeout (`watch.py:2300`). **A straight swap
  would risk making the acute path worse than it is today** — and the acute path is the one his standing
  rule is about. **So: keep `localStorage` as the synchronous write, add IndexedDB beside it** as the
  durable, GC-able, cross-tab layer. Belt and braces, not a replacement.
  · **sequencing: `#459` first.** Two boxes (`#askbox`, popout `#ptext`) keep **no** draft at all; a
  missing draft outranks a better-stored one, and `#459` needs none of this design.
- **#265** — Add a research command to the composer · P2 · command design ·
  origin: **human** · **human via watch 16:05** · hidden/menu command for
  primary-source feasibility research on features/subprojects · distinguish
  from #225 explore: research gathers cited durable facts; explore synthesises
  options/visual proposal · define wire name, main-dreamer vs fresh worker,
  research-only authority, output/provenance, retries and promotion · blocked on
  #225 command contract
- **#264** — Research concurrent-safe Dreamwork state and task ownership · P1 ·
  broad research/design · origin: **human** · **human via watch 16:05** · can a
  second dreamer/coordinator work in parallel without corrupting assignments,
  questions, user events or task state? compare single-writer+workers,
  append-only events/materialised views, locks/atomic replace/CAS, leases,
  SQLite and per-record spools · make tool/CLI-based task access (`dreamwork tasks
  list|get|grab|cycle`) the candidate public seam instead of direct `tasks.md`
  mutation; design the #294 migration script/import verification, mixed-writer
  cutover, rollback, preserved `tasks.md.deprecated` YAML notice and recovery
  instructions · cover stale recovery, multi-process same-target servers,
  worktrees/c2c, compaction, cross-machine/git boundaries and migration ·
  **human via watch 14:11:** explicitly design the single transactional
  task-transition history/materialised-view boundary that keeps burndown and the
  live dashboard status section current as the dreamer works; decide whether it
  shares #263's journal or uses a task-state outbox, but never dual-write two
  fallible truths
  · **UNBLOCKED 2026-07-28 01:27** — #263's contract is approved (`"rec"`), so the event model
  this waited on is settled and its own question is now answerable: journal-vs-outbox for task
  transitions, *"but never dual-write two fallible truths"* · the approval covers the
  CONTRACT, not #263's implementation, so this design may depend on the journal's shape but
  must not assume the journal exists yet · it is the only thing between the approval and
  #294, and #294 is his stated blocker
  · **IN PROGRESS 2026-07-28 01:47** (next-up mark cleared on start) — dreamer-264-boundary in
  `.worktrees/264-transition-boundary`, owning only `.dreamwork/docs/plans/task-transition-boundary.md`
  and its review artifact source · scoped to his 14:11 amendment alone, not the whole research
  brief: the journal-vs-outbox decision and the materialised-view boundary, design and ask only
  · the crux handed to it, to verify rather than accept: #263's `Transition` record is the
  **receipt's** lifecycle, but **most task transitions have no receipt** — the loop starts a task
  on its own tick, a dreamer is assigned files, a task is unblocked by another landing. So
  sharing the journal means events with no `receipt_id`, and not sharing it means proving
  single-truth across two stores. That asymmetry is what decides his question
  · **DESIGN LANDED `914648c` (merged; design only, ask open)** —
  `.dreamwork/docs/plans/task-transition-boundary.md` + artifact
  `.dreamwork/review/task-transition-boundary.html` · **the answer is neither of his two
  named options**, and the reasoning is the part worth keeping: *"never dual-write two
  fallible truths"* forbids storing one fact twice, not storing two facts. *"He asked for
  this at 14:11"* and *"the loop started #264 at 01:47"* are different facts, neither derived
  from the other, and their whole relationship is a foreign key — both of his options assume
  they are one fact
  · **the shape**: a task transition is one row appended to its own append-only `task_event`
  log, in the SAME SQLite file as #263's journal, in the SAME transaction as the CAS that
  moves `task_state` · burndown and the dashboard status section become **queries** over that
  log, so neither can be stale · one materialised row in the whole design, and only because a
  claim needs something to CAS against
  · the governing rule that keeps it small: **a materialised row exists only where a WRITER
  must CAS against it; everything a READER wants is a query** · consequence worth noting —
  `blocked` becomes derived from the dependency graph plus a small `gate` table, so landing a
  blocker writes no unblock event at all and blocked can never drift
  · the crux HELD and the dreamer strengthened it: `Transition.receipt_id` carries no `?`
  while nine siblings do (coordinator re-read `user-event-journal.md:101-103` — confirmed),
  and separately **zero task state is mutated at HTTP time today** — `_handle_command` writes
  one events-log line and nothing else, so a `do now:` becomes a task only when an LLM reads
  that log on a later tick, one-to-many and judgement-laden. No transaction could contain both
  the `202` and that
  · coordinator re-ran two more of its measurements independently: a cross-database
  `REFERENCES` is a **syntax error** in SQLite (`near ".": syntax error`), so the
  `task_event.receipt_id` constraint can only exist in one file; and `sqlite3` appears in no
  `.py` in the repo, so the one-file choice is free now and expensive later
  · **APPROVED IN FULL 2026-07-28 02:45 — T1 rec, T2 rec, T3 rec, T4 no.** *"mm yeah i like
  task history as an event log that gets processed. good point re git lagging. proper tooling
  will prevent that! T1: rec t2: rec t3: rec t4: no, we're good to go"* · the boundary stands as
  designed and nothing in it needs rework
  · **T3 is the consequential one**: taking the rec means the canonical event byte form is
  defined on day one, so a committed append-only text export stays a provable projection and
  surviving a fresh clone is a deployment choice rather than a schema change · his *"good point
  re git lagging"* endorses the measurement behind it — 331 ledger commits, median gap 4.8min,
  p90 20min, max 13.3h
  · **T2 retires three `status.json` fields** — `queue`, `current_task_ids`, per-agent
  `task_ids` — and they are precisely the three that drifted while this was being designed. So
  the field removal is not tidying: it deletes the second copy that made the drift possible
  · *"proper tooling will prevent that"* is his **third** naming of the same idea tonight, which
  is why #357 is now P1
  · **what this does NOT authorise, stated because approval reads as a licence**: no table, no
  migration, no CLI, no cutover. Those wait on #263's plan (in flight) and #294 behind it
  · **so the #294 chain is now clear of him on the design side**: #263's contract approved
  01:27, this boundary approved 02:45. What remains between here and #294 is work, not consent —
  #263's red-first plan, then its implementation gate
  · **EMPIRICAL HALF LANDED** `3eea4e3` — `.dreamwork/docs/research/2026-07-28-parallel-lanes-evidence.md`,
  `ccc @glm52`, brief `.dreamwork/docs/briefs/264-parallel-evidence.md`. 10 incidents with
  locators, **split 4 damage / 6 near-miss** as asked, since the ratio is what the answer turns on
  · **THE RESULT THAT KILLS AN OPTION, and it is what this task was for:** *"record-level
  concurrency primitives — locks, CAS, leases, SQLite, per-record spools — would have prevented
  **zero** of the actual damage, because **no two lanes ever wrote the same record**."* Zero
  concurrent-write instances across every writer and 121 commits in the window; the single-writer
  ledger and the append-only inbox both held **by construction**
  · **what did cause damage**: shared **CPU** (load-starved guards producing deterministic false
  reds), a shared **working tree** (dirty-file pollution, one index sweep), a shared **registry**
  (one lane's new file reddening others' baselines), and **one overloaded single-writer file**. So
  the evidence points at **modularity, not a concurrency mechanism** — and names `watch.py`, with
  six tasks queued behind it. **This bears directly on #294**, his stated blocker: it does not
  refute the SQLite migration, but it removes *concurrency safety* as the argument for it
  · **it refuted this coordinator twice, which is what I asked it to do.** (1) *"Thirteen lanes"*
  conflated cumulative dispatches with concurrency: **~17 dispatched, ~12 counting #263 as one,
  peak concurrency 5** — and `dogfood-orchestration.md`'s own tally drifts nine → ten → thirteen.
  Corrected there. (2) The `git commit --only` **same-file hunk sweep I put in six briefs has no
  instance** — the one index sweep was a plain `git commit`, i.e. `--only`'s absence. Mechanism
  kept, claimed observation withdrawn, in `lessons.md`
  · lane's own caveats, kept because they bound the result: git does not label lanes, so ~17/~12/
  peak-5 are inferences; a hunk sweep leaves no `--stat` mark, so its absence is consistent rather
  than proven; two incidents predate the fan-out window
  · **the broad research half remains open** — the primitive comparison and the #294 migration
  script, cutover and rollback. This task answered the evidence question, not that one
  · related: **#397, #402, #405, #419**
  · **RATIFIED 2026-07-29 01:43 — Q1 `rec`, and Q2 answered `(c)`, overriding my rec of `(b)`.** The
  boundary stands: a task transition is one row in an append-only `task_event` log in `#263`'s SQLite
  database, in the same transaction as the CAS on `task_state`; burndown and the dashboard become
  **queries**, so neither can be stale.
  · **Q2 as he actually ruled it, which is not either option as I posed them:** *"(c) — in the future the
  way we deal with this is via the dreamhub. Right now we can assume it's running locally only. or at
  least in serial … we should keep a .jsonl log I think, that way it's as flexible as we need it to be
  and we just need to be sure to capture enough detail and we'll be able to recover no matter what."*
  · **coordinator's reading, stated because it is an interpretation and not his words:** the `.jsonl` is
  **machine-local (gitignored)**, since a *committed* export would simply be `(b)`. So v1 accepts the loss
  of cross-clone burndown history, and the log exists for **recovery and reprocessing**, not portability.
  The upgrade path is cheap and worth noting: if he later wants cross-clone history, committing that same
  log **is** `(b)` — so `(c)` here is not a door closing. Say so if this reading is wrong.
  · **"capture enough detail" is the load-bearing requirement** and it belongs in the design before code:
  the log must carry whatever a reconstruction needs, which is only provable by `#460` replaying it into
  an identical DB. Design the log against that test, not against what is convenient to write.
  · **ratifying built nothing.** The migration, cutover ordering, whether git's 331 revisions become
  synthetic events, rollback, and the mixed-writer freeze remain `#294`'s and still need their own grant.
- **#263** — Design a durable user-event inbox and replay CLI · P0/P1 · design ·
  origin: **human** · **human via watch 16:05** · immutable disk event before
  acknowledgement; monitor only wakes dreamer; early-loop replayable/idempotent
  ingestion with statuses/receipt ids/errors · CLI like
  `ud-dw-user-events --limit 20` returns exact events and processing status ·
  compare append-only JSONL vs one-file spool; atomicity, concurrency,
  redaction/retention/migration and dual witnesses · accepted design decisions:
  HTTP `202` promises durable receipt (not application); persist across process
  and machine/power crash with file+directory durability; exact text retained
  until explicit **scripted** purge, never agent hand-editing · prefer append-only
  event/status history, but physical purge may remove payload while retaining a
  non-sensitive tombstone · LLMs read bounded CLI projections, not raw storage ·
  unify #260/#262, never a third inconsistent queue · reviewed design at
  `.dreamwork/docs/plans/user-event-journal.md` now PASS after resolving
  validation/status, all-writer DomainFileStore atomicity, hash-chain cursor,
  PostgreSQL, purge/cutover and external-drift/provisional-successor findings ·
  dashboard E1–E4 asked for implementation-**plan** authority only
  · **APPROVED — `"rec"` via watch 2026-07-28 01:27.** The contract is accepted, and the
  gate's own limits are what to read before acting on it: approval authorises *"a separate
  red-first implementation plan"* and explicitly **not** implementation, migration,
  deployment, PostgreSQL operation, topic chats, or payload purge · so the next increment
  under this id is **the plan**, red-first, taking `user-event-journal.md`'s §"Red-first
  acceptance fixtures" as its acceptance set — not code
  · **five lanes were waiting on this**: #264, #294, #287, #289 and #342's delivery toggle;
  #346 named it as the only thing standing between its design and the rest of #294
  · that doc's own status line saying human approval is required with no implementation
  authority is now the stale half of a true statement — update it when the plan lands, do not
  delete it
  · **PLAN LANDED `741b983` (merged; plan only, ask open)** —
  `.dreamwork/docs/plans/user-event-journal-implementation.md`, 976 lines, artifact at
  `.dreamwork/review/user-event-journal-implementation.html` · **35 increments in 8 lanes**
  (digest, journal, domain files, application, HTTP, CLI, browser, version gate), each naming
  the test AND the production line whose absence makes it fail · 18 of 20 design fixtures placed
  · **the two unplaceable fixtures are unplaceable for the right reason**: purge and the
  PostgreSQL half, both excluded by his own approval clause — not design gaps
  · and one is a real testability finding: *"journal fsync failure ⇒ no 202"* cannot be induced
  through stdlib SQLite (no pluggable VFS, no failable pragma, and a patched `os.fsync` never
  reaches SQLite's own syscall). Increment 22 tests the contract at a real seam — journal parent
  directory `chmod 0500` — and the fsync-specific case is a recorded gap with an `LD_PRELOAD`
  shim named, because mocking it away is what the design's own *"kill at named seams rather than
  mocking away durability"* sentence forbids
  · **the scheduling constraint is the file, not the graph**: lanes E and G both live inside the
  single 8647-line `watch.py`, so they share one lane in practice however disjoint their
  dependencies are · plan recommends lane E get its own `test_user_events_http.py`
  · measured facts worth keeping: no `sqlite3` anywhere; `_send` (`:8231`) hardcodes
  `send_response(200)` so it cannot express a status code at all; **every browser-side check is
  `res.ok`** across 9 sites, so `200 → 202` is invisible to him and only 15 test assertions move
  · one of its own measurements was wrong and it said so: the `200`-assertion count is **15** by
  `ast`, not the 13 grep reported, because grep missed four multi-line `assertEqual` statements ·
  the plan carries the `ast` script so the number is repeatable
  · **three bugs it found on the way out**, all verified by the coordinator in the source and
  filed rather than fixed: **#370** (P0, `/answer` and `/comment` truncate `questions.md` in
  place while `/ask` is atomic), **#371** (an interrupted body is witnessed as complete), and
  the correction to **#347** whose specified check turned out hollow
  · **blocked on his ruling** on four questions (Q1 start lanes A-D and F now with E and H behind
  a second gate, Q2 keep a partial witness marked incomplete, Q3 `200 → 202` as a non-event,
  Q4 purge and PostgreSQL not built rather than built-not-run)

  · **implementation began 2026-07-28 05:50** under his G1 grant, coordinator-planned with a
  brief per lane on disk (`.dreamwork/docs/briefs/263-lane-*.md`), which is his stated
  requirement rather than my convention
  · **lane A (digest) done, `@grok`, 12 minutes.** `A1` at `aad1d8d`; `A2`'s canonical helpers
  shipped inside `A1` and its test reached master **inside my own `12f47e3`** — I swept a lane's
  staged file into a ledger commit, because `git commit` commits the index and not the paths I
  added. History is left as it is rather than rewritten with two lanes live in the tree; the
  content is correct and the attribution is recorded here. The convention that was supposed to
  prevent this is fixed in `SKILL.md`/`CLAUDE.md` and every brief, and the lesson is in
  `lessons.md`
  · **the reason I know is that the lane reported the loss instead of hiding it** — it explicitly
  declined to invent a no-op `A2` commit to make its report look complete. That is the behaviour
  the brief asks for and it is worth naming, because a lane that quietly papered over this would
  have left a silent defect in the convention for the next fan-out to hit
  · **`A1` verified independently by me, not folded from its report**: removed the 8-byte length
  prefix from `length_framed`, `test_framing_boundary_cannot_be_shifted` FAILED
  (`b'abc' != b'abc'`) and its neighbour PASSED; restored from my own snapshot, byte-identical to
  the commit. The runtime precondition assertion is present and there is no `hashlib` in the test
  · **lane B (journal) DONE, `@grok`, ~20 minutes for all four increments** — `B1` `6a865e4`,
  `B2` `9bea281`, `B3` `2e1e987`, `B4` `37d0066`. 8/8 tests green; touched only
  `user_events/sqlite.py`, its test, and `.gitignore`
  · **its most valuable output is a defect in my plan, not in the code.** The plan's `B1` red
  line said "delete the `PRAGMA synchronous=FULL` execute and the assertion fails". SQLite
  3.53's compile-time default **is already FULL**, so the deletion changed nothing and the
  prescribed red came back green. The lane treated that as a finding rather than a relief —
  which is the rule — and made the pragma load-bearing by pinning `NORMAL` then `FULL`. I
  re-verified independently: the injection now yields `expected synchronous=FULL (2), got 1`
  with 7 neighbours green. Plan row amended; lesson recorded
  · read-only audit of its tests against my own acceptance criteria, all passing: zero
  `hashlib` in the test (so it holds no copy of the `H_i` formula), no raw SQL `INSERT` (both
  calls go through `receive()`), pragmas read from a **second** connection, and `B2` asserts the
  result *kind* — which is the specific trap the plan named, since a deleted `SELECT` comparison
  raises `IntegrityError` and a count-only assertion would "fail" for the wrong reason
  · `B5`-`B8` were out of batch and correctly not started
  · **lane C (domain files) is 3 of 5, NOT done — and this line said DONE for nine hours.**
  `@pi-glm52`, ~45 minutes** — `C1` `3f1a6af`, `C2` `8c1bb60`,
  `C3` `b5555e4`, plus `4a773e2`. 3/3 green, all criteria HOLD, and it explicitly noted seeing
  concurrent-lane dirt in the tree and not staging it — which is the ownership rule working
  · **CORRECTION 2026-07-28 16:35.** The `3/3` above is the count of what the lane **built**, and I
  read it as the lane's **scope**. Lane C is plan increments **11-15**: `C1` lock, `C2` lineage,
  `C3` one-write, **`C4` markers**, **`C5` rebaseline**. `C4` and `C5` are **not built** —
  `user_events/domain_files.py` has no whole-file marker search and no `rebaseline`, and
  `test_user_events_domain_files.py` holds 3 tests. **So A-D are NOT proved and the second gate is
  correctly still shut.** I filed a question at 16:24 telling him the condition was met; corrected
  in place at 16:35
  · **caught by the `@grok` lane building the gate artifact, from the tree** (`git log --
  user_events/domain_files.py` plus the plan's own lane table) — the fifth lane today to refute a
  figure I derived rather than observed, and the costliest, since acting on it meant asking him to
  open a gate on unproved prerequisites. The pattern is now specific enough to state: **a lane's
  self-reported `n/n` is a claim about its own brief, never about the plan's lane** — reconcile the
  two before either is quoted
  · **`C4` + `C5` are inside increments 1-19, which `G1` already authorises**, so they need no
  ruling and are the loop's next `#263` work rather than his
  · **`C3` verified independently by me, and the red is the most legible in the batch**: I
  replaced temp-then-`os.replace` with the direct `open(path, "w")` that `watch.py:8462` does
  today, and `test_kill_at_rename_leaves_the_previous_generation_intact` failed with
  `b'' != b'the quick brown fox…'` — **the file was emptied**, with 2 neighbours green. That is
  exactly what a crash mid-write does to `questions.md` or `answers.md` right now, which is the
  whole reason this increment exists. Restored byte-identical
  · **lane F (CLI) DONE, `@glm52`, ~35 minutes, 4/4** — `F1` `9263a42`, `F2` `e84ca0c`,
  `F3` `312daeb`, `F4` `4c918b2`. Two new files only (`ud-dw-user-events`,
  `test_user_events_cli.py`), 10 tests, and every acceptance criterion holds
  · **it produced two reds for `F4`, and the second is the one I care about.** My criterion 6
  said the coverage test must **fail loudly** if its parse of the design document finds zero
  semantics, rather than passing having checked nothing — the `lessons.md:1447` shape. The lane
  proved both halves: removing a `HEALTH_ROWS` entry fails by naming the missing semantic, **and**
  breaking the parser to zero fails on the floor
  · **verified independently by me**: I broke the bullet match to `"- NEVER-MATCHES "` and got
  `AssertionError: parse found only 0 failure semantics — the coverage check would be vacuous; the
  parser is broken or the section moved` / `assert 0 >= 5`, with its neighbour green. Restored
  byte-identical, 10 passed. So the check cannot go quiet, which is the failure mode that has cost
  this repo the most
  · nice detail in `F3`: widening `_write_authorized` to `return True` fails the read-only test
  **without** breaking the read commands, because they route through `READ_COMMANDS` upstream of
  the guard — so the red is specific to the property under test rather than collateral
  · **lane B second batch DONE, `@grok`, ~25 minutes, all four** — `B7` `5f729dc`, `B5` `bc731cf`,
  `B6` `30947d7`, `B8` `fec80be`. 12/12 green in its file, and it took the priority order it was
  given (`B7` first)
  · **lane D (application) DONE, `6cd9f95`, 2026-07-28 07:25 — and it went nine hours unrecorded
  here, which is the reason `#371` was mishandled.** All four increments in one commit, new files
  only (`user_events/apply.py` 383 lines + `test_user_events_apply.py` 485): `D1` ternary `Proof`
  (a torn or drifted file proves `UNKNOWN`, never `NOT_APPLIED`), `D2` one-provisional-successor
  reservation before mutation, `D3` reconcile via real `os._exit` children at two seams, `D4` five
  adapters that cannot read each other's format. **Its own message reports finding a hollow red
  inside itself** — the body-digest predicate lived in two places, so deleting the copy under test
  changed nothing — and consolidating to one line. That is what `proved` should mean
  · **so A, B, C, D and F are all landed and the second gate's condition — his 05:43 *"until A-D
  are proved"* — is MET.** Filed as a question 2026-07-28 16:24 rather than acted on: opening it is
  his, and the nine hours it sat shut with no ask is the `#419` hole he named at 15:19
  · **`B7`'s red came back GREEN, and that is the finding of the batch.** Removing
  `UNIQUE(client_action_id)` left the whole suite passing. **I reproduced it: 12 passed with the
  constraint deleted.** `BEGIN IMMEDIATE` plus `B2`'s SELECT-before-insert already serialise the
  writers, so the second process *replays* and never reaches the constraint. The lane proved it
  was not merely threaded — spawn context, `len({pids}) == 2` and `os.getpid() not in pids`
  asserted at runtime — and then **probed the mechanism instead of guessing**: `DEFERRED` with no
  `UNIQUE` gives `database is locked`, so the concurrency is real and `UNIQUE` is simply not the
  line carrying it. Plan row amended, `UNIQUE` retained as defence-in-depth without the claim that
  it is tested
  · **that is the second wrong red line in my own plan** (after `B1`'s pragma) and they share a
  shape: a plan written before the code names the mechanism its author imagines will carry the
  property, not the one that does. Lesson recorded — defence-in-depth and a discriminating red are
  in direct tension, and when a red comes back green the question is *"which layer is holding this
  up?"* rather than *"is the code fine?"*
  · `B5` honoured the no-clock-patch rule with a real 1s lease and a measured `elapsed > lease` via
  `time.monotonic()`; `B8`'s meta-test derives contract names from `inspect.signature` and asserts
  the product, so there is no hand-copied list to drift
  · **so lanes A, B, C and F of his G1 grant are complete.** Lane D (the adapters) dispatched 07:00
  now that `B5` and `C3` — its blockers — are both in. `#367` increment 1 and `#385` also in flight  · **lane C remainder IN PROGRESS 2026-07-28 16:38** — `ccc @glm52`, `.worktrees/263c`, brief
  `263-lane-c-remainder.md`. `C4` at `f85be1c`, `C5` at `2cc3537`; the lane is still verifying, so
  **lane C is not being called 5 of 5 until a gate says so** — that is the whole lesson of the 3/3
  error and calling it early would repeat it
  · **the merge gate is built and RED-PROVED before the lane reported**, at
  `scratchpad/gateC.py` (16 checks). Run against `master` it fails **6**, each the right one: no
  marker-search function, neither section word present, no `rebaseline`, and neither named test in a
  file whose three tests are `C1`-`C3`'s. So the gate can see the absence it exists to detect
  · **its denominator comes from the plan, never the lane.** It parses lane C's increment rows out
  of the plan's own table and **asserts there are five**, because *"a denominator from the same
  source as the numerator measures nothing"* is exactly how `3/3` passed for nine hours. It also
  re-runs `C4`'s named red independently (drop the second section from the scan's list, the fold
  test must fail) and refuses a **second** drift detector — `committed_lineage` in both
  `domain_files.py` and `apply.py` is lane D's already-shipped hollow-red bug
  · **lane C is 5 of 5 as of 2026-07-28 17:21** — `C4` `f85be1c`, `C5` `2cc3537`, `ccc @glm52`,
  ~43 minutes. `find_marker` scans `_MANAGED_SECTIONS = ("Open","Answered")`; `rebaseline` validates,
  mints `max(committed)+1`, preserves bytes and journals the import through a callback (mirroring
  `reconcile`'s `finish`). **So A, B, C, D and F are all complete and the second gate's condition is
  MET** — this time asserted by a gate rather than read off a lane's self-report
  · **the gate passed 16/16 on the candidate and still fails 6 on `master`**, so narrowing it did not
  hollow it. Its one FAIL was **mine**: it counted every mention of `committed_lineage` (7 in
  `domain_files`, 11 in `apply`) and called it a duplicated drift detector. It is a **parameter name
  threaded through**; the membership test exists once, `apply.py:166`. **A substring cannot tell a
  duplicated predicate from a threaded argument** — the same defect as grepping prose for *"condition
  met"* and finding five retractions, twice in one hour. Narrowed to `in committed_lineage`: 0 and 1
  · **the lane disclosed that its own `C5` red is defence-in-depth, not the sole mechanism.** The file
  after `rebaseline` always sits at `S = max(committed)+1`, so a caller passing `reserved_successor =
  S` sees `APPLIED` via the successor half alone and the lineage red would be **hollow**; its test
  passes `max(new_lineage)+1` so the lineage half is load-bearing. It reported the geometry rather
  than claim a cleaner discrimination than the geometry allows
  · **and it found plan row 15's red line stale** — it named `apply._is_valid_known_file`'s predicate,
  which is `D1`'s red and already proven there. Corrected in the plan with the reason visible; same
  class as the stale `B1`/`B7` rows
  · **`TestCitedShas` failed 3× under random order** (`OSError: File too large`) and passes in
  isolation and under `-p no:randomly` (1011 passed). Consistent with four lanes running `git`
  against the live repo at once — the known interaction, not a defect
  · related: **#426, #461**

  · **SECOND GATE OPEN 2026-07-29 01:37 — *"ack good to go"*.** Lanes **E** (HTTP `202`), **G** (browser)
  and **H** (version gate) are authorised; the standing prohibition on building them is lifted. Still
  **excluded by his earlier clause and not by this one**: payload purge and the PostgreSQL half — do not
  read an open gate as authorising those. E and G both live in `watch.py`, so they **serialise on that
  file** however disjoint the plan makes their dependencies; the plan recommends E take its own
  `test_user_events_http.py`. Measured facts to reuse rather than re-derive: `_send` (`watch.py:8231`)
  hardcodes `send_response(200)` so it cannot express a status at all, and **every** browser check is
  `res.ok` across 9 sites — so `200 → 202` is invisible to him and moves only 15 assertions (by `ast`,
  not grep, which missed four multi-line ones).
  · **lane E batch 1 DONE and merged `df2989e`** — `E1 envelope` `69b8573`, `E2 shadow` `d460947`,
  `E3 cutover` `38ef409`; new file `test_user_events_http.py`. The cutover's shape: the **journal
  commit, not the handler, authorises the response** — `_send_receipt` (`watch.py:9827`) sends `202`
  with `Location: /user-events/<id>` and merges receipt id/sequence/digest into the handler's body,
  and it refuses to mint a `202` from a missing receipt (`send_error(503)`) rather than fabricating an
  id. A journal open/commit failure is a `503` with no receipt (`:10088`)
  · **verified end-to-end by me against a real server, not folded from the report**: `POST /command`
  `{kind:'add-idea'}` → `202`, `Location: /user-events/43899c46-…`, and that receipt id present in
  **all three** tables of `.dreamwork/user-events.sqlite3` (`receipts`, `transitions`, `events`)
  · **and my first two probes were measuring somebody else's process.** They returned `200 {"ok":
  true}` — the exact legacy `journal_shadow=False` fallback — which read as a failed cutover. The
  cause was mine: `watch.py` has no `--no-open` flag, so my server exited on an argparse error and
  `urllib` reached a **stale lane server already listening on that port**. Now asserted in the probe:
  resolve the listener's pid from `ss -ltnp` and require it to equal the pid I started. A probe that
  does not verify *whose* server answered can report any result at all — the network equivalent of the
  fixture that stands in front of the code
  · **lane E batch 2 landed on its branch — `E4` `0024ad2`, `E5` `a67f308` — and I am HOLDING THE MERGE.**
  Both increments are correct against the plan and both red-proved on the named lines (`E4`: the
  `_journal_record_health` call, plus the absence of a re-raise in `log_submission`; `E5`: the `send_error(400)`
  in `_read_json`). `E4`'s seam is real — `submissions.log` made a **directory**, so `IsADirectoryError` comes
  from the filesystem rather than a patched `open`. Closed reason set `REJECTION_REASONS =
  ("malformed_json", "schema_invalid", "domain_invalid")` in `user_events/sqlite.py`, where a parser finds it
  · **MERGE RELEASED `8ccd2fb` at 03:34, after `E5b` landed the client half** (`a328507`, `@grok`) — one
  `writeVerdict(res)` reads the body **once** (a `Response` body is read once, so it is the single reader) and
  returns `{landed, rejected, reason, status}` where **`landed` is `res.ok && !rejected`**. That is the one thing
  `/ask`, `/answer`, `/comment`, `/command`, `/tint` and `/run-mode` gate on; `res.ok` alone decides nothing any
  more. The reason reaches him through a closed map paired with the server's `REJECTION_REASONS`, and a code
  outside the set falls through to the status line rather than printing an unrecognised string
  · **it also caught what I had missed**: `subsOutcome` — `#175`'s submission log — was recording `'ok'` for a
  rejected `202`, so a tab dying mid-send would have left a durable record claiming his words landed. The verdict
  now decides that entry too
  · **verified by me in an isolated worktree, not folded from its report**: reverting `writeVerdict`'s `landed` to
  `res.ok` fails **10 of 12** checks in the new `dev/capture/rejectwrite.mjs` — including *"does not clear the
  draft store (the permanent-loss vector)"* — while *"SUCCESS /ask clears the box on a write that lands"* still
  **passes** and no page errors appear. So the guard is specific to the property rather than broken, which is what
  its two-sided structure buys. On the merged tree: 12 PASS, exit 0
  · guard `rejectwrite` registered (**56**); the `justfile` conflict was resolved as a union — `staleremedy` from
  `#462`, `rejectwrite` from here — verified against `dev/capture/` in both directions with zero registered-but-
  missing and zero present-but-unregistered
  · **so lane E is complete except `E6`** (increment 25, `shadow_failed` on the dashboard), and `E6` is now the
  smaller job it should always have been, because the *rejection* half of visibility landed here instead
  · **why the merge is held: `E5` turns a refused write into one the browser reads as successful, and his text
  is what pays.** A rejected body now answers `202` with `{"ok": false, "rejected": true}` — and `202` makes
  `res.ok` **true**. Every browser check is `res.ok` across 9 sites, which is exactly why Q3 could call
  `200 → 202` a non-event; that reasoning holds for a *successful* write and breaks for a rejected one
  · **measured, not read**: against a lane server whose pid I asserted, `POST /ask {"nope": …}` returned
  `202 {"ok": false, "rejected": true, "reason": "schema_invalid"}`. At `watch.py:3109` the ask path is
  `if (res && res.ok) { liveBox.value = ''; liveMsg.textContent = 'asked'; }` — so the box empties and the page
  says **asked** for a question that was durably **rejected**. `:3526` and `:3570` are the same shape for
  answers and notes, where `dwDraft.clear()` follows, and his standing rule is that a draft clears only on
  **durable success**
  · that rule is not inferred — `:3527`'s own comment says *"confirming a write that did not happen is the one
  thing worse than the 409 itself"* (`#136`), and `#269`'s whole point is that his words survive. So `E5` does
  not violate a preference, it violates the invariant two earlier tasks exist to protect
  · **`E6` is where visibility was scheduled, and that is the scheduling error.** `E6` makes `shadow_failed`
  visible; nothing in the plan makes *rejection* visible, because the plan assumed `res.ok` stayed truthful.
  So the successor is not "do E6 sooner" — it is **`E5b`: no write surface may confirm a rejected receipt**,
  and `E5` merges with it or not at all
  · out of that batch and still open as the successor: **E4** (best-effort), **E5** (reject after
  receipt — `_read_json` at `watch.py:8354`; pre-E5 an invalid `kind` is still a synchronous `400` by
  design, which is *not* a cutover defect), **E6** (visible — a browser/motion increment, so it needs
  `transitions.md` and the design skills, not a tail bolted onto E). Then lane **G** (30–33, shares
  `watch.py` with E) and **H** (34–35)
- **#462** — the dashboard says it is N commits behind but gives him no way to act on it · **P1** ·
  feature/dashboard · origin: **human** · **human via watch 2026-07-29 02:30, next-up, delegate soon:** *"re
  'this page is 3 watch.py commits behind · serving f9bb49e' on dashboard, we should have a task for adding an
  'update & reload' button/link I think? Please delegate that to a subagent in the near future. I would like it
  soon."*
  · the staleness row already exists and already knows the answer — it computes the gap — so what is missing is
  only the action, which is why he reads it as an obvious omission
  · **it lands in `watch.py`, which lane E2 holds**, so it goes to a worktree and merges after; that is a
  scheduling cost, not a blocker
  · every transition it introduces obeys `transitions.md` — a button that appears when the page falls behind is
  an arrival, not a pop, and *"it is only a small toggle"* is how a page ends up with one gesture that snaps
  · the hard half is not the button: a reload that restarts the server he is reading must not lose his drafts
  (`#269` keys them per target) nor his place, and it must say what happened if the restart fails
  · related: **#461**
  · **increment 1 LANDED `f7781a5`, merged `b1551b1` — and `#462` STAYS OPEN on his consent call.** The
  staleness row now carries its own remedy: the exact command, present **only** when behind, copyable on click,
  confirming through the page's single `#fmsg` lifecycle, with the text selectable as the clipboard fallback.
  Label is the command itself rather than his two-verb phrasing, per the styleguide voice. `serving_report`'s
  `missing` is reused verbatim — no second computation of the gap
  · **the lane's IGC refuted every cheaper option, and the decisive error on self-restart is the one worth
  keeping.** `watch.py`'s `--autoreload` re-execs on `__file__`'s mtime — and for a **deployed** server
  `__file__` *is* the snapshot, outside the repo, which a tree commit does not touch. So `os.execv` re-serves
  byte-identical bytes and the staleness is unchanged **by construction**. A browser reload fails the same way.
  "Update" can therefore only mean *re-snapshot from HEAD and restart*, i.e. `just deploy`
  · it also **withdrew its own first refutation** after I pushed back: it had argued a failed redeploy leaves the
  failure invisible *"because the page that would report it is the page the restart destroys"*, which is false —
  a restart destroys the server, not the loaded document, and that is precisely why `#269`'s drafts survive one.
  The corrected refutation is about bytes, not page death, and it is right
  · **guard `staleremedy` registered (55 today) and verified by me on the merged tree**: 11 checks pass,
  including gating, a **sampled** arrival (not an end-state assertion), intermediate-opacity easing, the copy,
  the confirmation lifecycle, and reduced-motion parity — plus a runtime-derived precondition that the state
  really moved current→behind, so the arrival cannot be vacuous. My own red: deleting the single
  `revealStaleAction()` call failed exactly the two motion checks and nothing else
  · **remaining and on his desk**: may the page run `just deploy` itself? Asked 02:56 with `Q1`/`Q2` declared;
  the objection is authority, not safety
  · **AUTHORISED, 2026-07-29 03:46 (via watch): `rec` — yes, the page may run `just deploy`.** So the
  staleness row is an **action**, not a copyable command: loopback-only, behind the existing confirmation
  idiom, and it must report the case where the new generation never arrives (the lane's own finding: a
  deployed dashboard serves a snapshot, so a reload and an `--autoreload` re-exec are both byte-identical —
  "update" can only mean re-snapshot from HEAD and restart). **Queued behind the lane holding `watch.py`**
- **#262** — Make accepted Web UI submissions durably witnessed before 200 · P0 ·
  reliability bug · origin: **loop** · 30m · incident exposed by **human report
  2026-07-26 15:47** · current `log_submission()` catches and suppresses
  `OSError`, so a process can dispatch/acknowledge a request whose server witness
  was never persisted; multiple same-target watch processes also split receipt
  history · design with #263 rather than adding a competing queue · red-first
  coverage for write failure, accepted-but-unwitnessed requests, stale/multiple
  ports and concurrent same-target processes · blocked on #263 event model

- **#260** — Make post-compaction submission reconciliation cursor-based · P1 ·
  reliability · 25m · origin: **loop** · incident confirmed by **human 15:47** ·
  coordinator guessed a 15:43 cutoff after cancelled compaction and falsely
  concluded no missed messages before scanning the full witness · add durable /
  best-effort processed submission cursor or acknowledged range; recovery must
  enumerate every later `submissions.log` record by endpoint/kind and map it to
  task/question/answer/settings folding while preserving exact text · cover
  command/comment/answer/ask/tint separately; file format/migration/lint +
  red-first incident fixture

- **#259** — Cycle composer modes with Shift+Tab · P1 · keyboard UX · 20m ·
  origin: **human** · **human via watch 15:40** · inside response textarea,
  Shift+Tab cycles answer/add-note; inside main composer textarea it cycles
  available command kinds in visible order including eligible plugin commands ·
  draft/focus preserved; ordinary Tab and Shift+Tab elsewhere keep browser
  focus navigation · announce mode accessibly; existing sliding indicator +
  reduced-motion snap; popout inherits through #241, no duplicate handler ·
  red-first keyboard-only guards · blocked on #241 shared composer

- **#257** — Give `do-now` a danger and urgency treatment · P1 · visual/UI
  implementation · origin: **human** · **human via watch 15:30** · **D1 approved
  18:17:** scoped rose ghost-outline default; `#f87171`, sequencing, RM/perf and
  non-shader recommendations accepted · D2 remains optional future toggle only,
  redesigned from left rail to border + top-cast red lighting · prior simple
  storm/rose shader superseded by #278–#280 · blocked on #241 shared composer

- **#256** — Define a host-provided generated-artifact background hook · P2 ·
  design amendment · origin: **human** · **human via watch 15:25** · generated
  HTML declares a canonical class/hook whose embedded background comes from
  Dreamwork Web UI, complements active shader/theme without duplicating it ·
  define host injection/containment, theme tokens, plugin override,
  transition/reduced-motion and deterministic offline/public fallback · fold
  into #239 resolver, never a second theme pipeline · blocked on #239

- **#254** — Render review notes and loop replies as threaded conversation ·
  P1 · UX bug · 20m · origin: **human** · **human via watch 15:20** · a
  human Note followed by loop Answer currently reads as sibling bullets on the
  main question, obscuring authorship/causality · render conventional
  comment→reply nesting with durable authorship semantics, accessibility,
  responsive layout, atmospheric transition + reduced-motion · evidence:
  `.dreamwork/review/evidence/review-note-reply-unclear.png` · separate from
  broader #253 research · queued after active #250/#251
  · **APPROVED for WRITTEN DESIGN ONLY, human via watch 2026-07-27 23:03**
  (`rec` = Accept N1) · N1 is: the loop **Answer** becomes the root response to
  the question, and later human Notes plus loop Replies render as one connected
  discussion branch beneath it at a **single** inset depth — conventional
  comment→reply hierarchy without a diagonal staircase · preserve exact
  chronology, author and timestamp; recognise an explicit `Reply (loop, …)`;
  never indent each turn more deeply; **if no root exists, keep the note
  top-level rather than guessing** · **the scope limit is part of the approval
  and is not the loop's to widen**: his ask granted a design/spec document and
  explicitly NOT parser, file-format, UI, migration, deployment or transition
  changes · so the deliverable is the spec plus a review artifact, and
  implementation is a separate ask afterwards · stated here rather than left in
  the answered question, because an approval whose scope lives only in
  questions.md is one the next agent reads as broader than it is
  · **this block was misfiled onto #253 by `b3ab88a` and moved here 23:33.** The
  commit subject said `steering(#254)` and its body reasoned only about #254, but
  the hunk landed inside #253's bullet — so #254 read as unapproved while #253,
  whose own line says *"approved design/implementation"*, carried a contradictory
  design-only limit it was never given. Recorded rather than silently corrected
  because the commit that made the mistake was the one arguing that a misplaced
  approval is read wrong by the next agent
  · **design LANDED `5b813f1`** (spec
  `.dreamwork/docs/plans/note-reply-threading-254.md`, artifact
  `.dreamwork/review/note-reply-threading-254.html`) — the entry stays open on
  purpose, cited here the way #269 and #275 do, because the grant covered the
  written design only and implementation is a separate ask
  · **and the design as approved does not fix the card he filed this about**:
  verified — that question has no `Answer` bullet, N1 roots the branch at his
  Answer, so his own tie-breaker leaves the note flat, exactly as it renders
  today · a second defect in the same card explains the screenshot and is already
  repaired in the file (the loop had written `Answer (loop, …)`, a tag in neither
  `NOTE_TAGS` nor `ANSWER_TAGS`, so it was never a contribution) · so
  implementation is gated on his **R1/R2/R3** answer now open in questions.md,
  not merely on scheduling · spec records seven open decisions as D1–D7, and its
  own proof plan names two checks that would be hollow — see #340 and #341 for
  the two out-of-scope findings it produced
  · **UNBLOCKED — R1/R2/R3 were answered on 2026-07-27 (23:03 and 23:38) and the body still says
  the answer is "now open in questions.md"** (found by `#420`'s census, verified against
  `parse_answered` 2026-07-28 16:08). Both entries are in `## Answered`; nothing is open for this
  task. Startable, subject to its own scope
  · one of the **four** entries the census found holding a stale *"waiting on him"* claim (`#254`,
  `#367`, `#371`, `#50`). Together they are the ready-made red fixtures for `#419`'s check, and they
  make the point that the reverse direction is the one with the live cost now: the no-question half is
  loud once you look for it, while an *answered* question leaves the blocked entry reading exactly as
  it did before
  · **DESIGN LANDED `542c43a` (2026-07-28 23:42, lane `wt/threaded`), and the grant's boundary was respected exactly** — no parser, format, UI, transition or migration touched. Spec at `.dreamwork/docs/plans/threaded-notes-spec.md`. The rule is `qaBranch(q) → [lead, root, branch]`: his `Answer (via watch, …)` is root; failing that the last `Reply (loop, …)` is root (**R1 — the Reply *is* the resolution, not the row above it**); failing that, flat. One branch, one inset, never a staircase, and **prefer flat over wrongly-attached**. Never structure from timestamps. **Artifact deliberately skipped** because N1+R1 left no decision genuinely his — a decoy ask is worse than none. **Implementation is a separate grant and is now on his desk as an `#ask`** (`I1`). It also found four grammar ambiguities, one of which is data loss and is filed as `#446`.
  · **blocked-on: **human** (implementation grant `I1`)**
  · related: **#446**
  · **IMPLEMENTATION AUTHORISED 2026-07-29 01:01** — *"yes"* to `Approve I1`, via the dashboard. Build it
  as `.dreamwork/docs/plans/threaded-notes-spec.md` states, with the scope boundaries that ask listed
  (out: true nesting, `## Answered` threading, two-answer retention which is `#446`, Answered raw-Answer
  lift). **next-up**, queued behind the `mistperf` lane because it holds `watch.py` and `test_watch.py`.
- **#253** — Add contextual review annotations and attached discussions · P2 ·
  approved design/implementation · origin: **human** · **approved via watch
  18:35** · preserve static style-isolated iframe; narrow versioned `postMessage`
  selection bridge; parent validates quote/context and owns mutable side rail ·
  anchors combine artifact hash, heading path, paragraph ordinal and normalised
  quote/context; ambiguous edits become explicit orphans · chats attach to whole
  artifact/selection and remain globally visible at `/chat`; main dreamer first,
  explicit worker promotion only, preserving transcript/attachment history ·
  typed task/update requests mint normal human-origin tasks · coordinate storage
  and transcript contract with revised #270/#229 before red-first UI increments

- **#249** — Add dev-overlay sampling cadence controls · P2 · dev UI · 25m ·
  origin: **human** · **human via watch 14:37** · frame-time graph + other
  stats update at selectable `1s` / `10f` / `1f` cadence using the existing
  tiny sliding button-group idiom, not a new toggle · default rec `1s` for low
  overhead · keep per-frame measurement/aggregation correct when display is
  slower; persist/sync under #228 project settings · transitions/reduced-motion
  and perf guard required · blocked on #245 and #228
  · **UNBLOCKED — `#245` LANDED and nobody re-triaged this** (found by `#420`'s census, machine-verified against `parse_ledger`, re-verified by the coordinator 2026-07-28 15:53): dev-overlay sampling cadence; `#228` is landed too, so neither named blocker stands. **Startable now.** This entry is one of **ten** with the same shape, which is why the census was worth running: a blocker that clears is invisible from the blocked side, so nothing ever re-reads it

- **#246** — Keep Grok usefully occupied when work is available · P2 · routine
  · origin: **human** · **human via watch 14:33** · proactively assign
  `grok-sugar-vesi-x6tv` unblocked small/medium in-repo work with disjoint
  ownership · no manufactured busywork, cross-repo/external authority,
  collisions or model-gate bypass; diagnose first unless ownership explicit;
  coordinator validates every result · active durable routine
- **#244** — Define repository-browser visibility policy · P2 · design ·
  25m · origin: **human** · **human via watch 14:29** · decide tracked,
  untracked, dotfile, ignored, generated/vendor/cache, symlink and binary
  visibility + persistence · rec: tracked text default; untracked + dotfiles
  opt-in; ignored/generated/vendor/cache advanced-off; binary listed with
  type/size but not rendered; symlinks never escape target · review artifact
  required; prerequisite to #243; blocked behind #238
  · **UNBLOCKED — `#238` LANDED and nobody re-triaged this** (found by `#420`'s census, machine-verified against `parse_ledger`, re-verified by the coordinator 2026-07-28 15:53): **composer cluster**: three queued UI tasks sat behind one landed prerequisite. **Startable now.** This entry is one of **ten** with the same shape, which is why the census was worth running: a blocker that clears is invisible from the blocked side, so nothing ever re-reads it

- **#243** — Add a sticky animated repository file tree · P2 · feature ·
  several increments · origin: **human** · **human via watch 14:29** · thin
  left sticky tree on `/file`, expandable folders, active-file auto reveal /
  focus, keyboard navigation, responsive/mobile, client routing and aesthetic
  transitions · one confined server-side inventory; preserve expansion,
  scroll and selection through rerenders/routes · blocked on #244
- **#242** — Link changed files from expanded commits · P2 · feature · 15m ·
  origin: **human** · **human via watch 14:29** · changed paths become
  confined `/file` links; deleted paths must not promise a readable current
  file (plain deleted status or historical-intent affordance) · reuse existing
  route/link idioms and transitions · blocked behind #238
  · **UNBLOCKED — `#238` LANDED and nobody re-triaged this** (found by `#420`'s census, machine-verified against `parse_ledger`, re-verified by the coordinator 2026-07-28 15:53): **composer cluster**, same landing. **Startable now.** This entry is one of **ten** with the same shape, which is why the census was worth running: a blocker that clears is invisible from the blocked side, so nothing ever re-reads it

- **#241** — Extract one composer mount contract · P2 · task · 30m ·
  origin: **human** · implication of **human via watch 14:25** · make the
  existing rich composer mountable in main document, Document PiP and
  `window.open` fallback without duplicating command vocabulary, plugin
  refresh, per-project draft/settings, submission witness, keyboard behavior,
  transitions or styling · prerequisite to #240; blocked behind #238
  · **UNBLOCKED — `#238` LANDED and nobody re-triaged this** (found by `#420`'s census, machine-verified against `parse_ledger`, re-verified by the coordinator 2026-07-28 15:53): **composer cluster**, same landing — and this one is the contract the other two want, so it is the natural first of the three. **Startable now.** This entry is one of **ten** with the same shape, which is why the census was worth running: a blocker that clears is invisible from the blocked side, so nothing ever re-reads it

- **#240** — Bring the full composer and dream field into popouts · P2 · UI ·
  45m · origin: **human** · **human via watch 14:25** · retire legacy
  dropdown; reuse main button-group composer while retaining `+ command ·
  <name-slug>` header; same submission morph/ripple/confirmation · shared
  dreaming shader under ~80%-opaque popout surface so behind remains subtly
  visible · one component, not copied variant · transition/reduced-motion,
  keyboard/draft/plugin sync, shader continuity/fallback and visual/per-frame
  guards · blocked on #241

- **#239** — Canonicalise generated HTML review styling · P2 · idea ·
  30m design · origin: **human** · **human via watch 14:23** · reviews,
  answers, proposals and explorations should consistently use Dreamwork style
  from one canonical source, replaceable by a Dreamwork plugin · rec:
  target-local `.dreamwork/review-style.md` seeded from skill default; every
  HTML generator resolves it; explicit plugin override contract; artifact
  records style source/version; offline-clean always; absent/broken plugin
  falls back loudly to project file, never undocumented agent taste · connect
  to #225/#229/#235 + initialization/file-formats

- **#237** — `[Opus5]` JSON-character rain on data refresh · P2 · idea ·
  origin: **human** · **human via watch 14:13** · on each `data.json`
  refresh, a subtle top-down sheet of ASCII rain using JSON punctuation such
  as ``{}[]""'',`` with lightly jittered timing · **MODEL GATE: do not
  analyse, design, implement, review or dispatch except with an Opus 5 agent**
  · later must obey transitions.md, reduced-motion parity, bounded cost and
  per-frame visual guards · parked until eligible model exists

- **#236** — Record compact topic-chat action provenance · P2 · idea · 20m
  design · origin: **human** · **human via watch 14:09** · each ephemeral
  run records referenced/accessed file paths and tool invocations, especially
  shell commands; no hidden reasoning or full response retention beyond the
  transcript · future fresh workers receive this compact discovery index ·
  define trustworthy capture, bounds/redaction, failed-run semantics and file
  shape · blocked on #373 (#229 approved 2026-07-28 02:56, sequenced after the
  CLI); amend its proposal first
- **#235** — Promote `/answers` follow-ups into topic chats · P2 · idea ·
  25m design · origin: **human** · **human via watch 14:09** · answered
  record offers a follow-up which atomically creates a topic chat seeded with
  original human question + dreamer answer + follow-up, links the settled
  answer to it, and dispatches fresh subagent · avoid duplicate live histories
  and `/answers` bloat · blocked on #373 (#229 approved 2026-07-28 02:56; the
  implementation it waited on now waits on #294/#346)

- **#230** — Add a `use subagent` composer checkbox · P2 · task · later ·
  origin: **human** · **human via watch 12:57** · request fresh-context,
  parallel processing outside the main queue; integrate with #228 project
  settings, expose dispatch/ownership/result channel, and never silently fall
  back to inline · blocked on #373's lifecycle design (was #229, decided
  2026-07-28 02:56)

- **#374** — `esc()` does not escape the double quote, and three attributes take a
  URL parameter · P2 · security/bug · 30m · origin: **loop** · found by the
  fileview dreamer, out of its scope, and the escape defect re-verified here by
  reading: `watch.py:1489` is `esc = t => { d.textContent = t; return d.innerHTML }`
  — serialising *text* content, so `&`, `<` and `>` are escaped and `"` is not,
  because the HTML serialiser only escapes quotes inside attribute values · three
  attributes interpolate it: `watch.py:1527-1528` build
  `aria-label="pop out ${esc(label)}"`, `data-pipurl="${esc(url)}"` and
  `data-piplabel="${esc(label)}"` · reachable: `watch.py:4737` passes
  `v.param` — the route parameter from `/file?p=…` — as `label`, so a `"` in the
  query string closes the attribute early. `<` and `>` are still escaped so no new
  tag can be opened, but `onfocus=` on that same button is enough, and the button
  is focusable by definition · `url` is `encodeURIComponent`'d at the call sites and
  is the one of the three that is currently safe · the exposure today is a crafted
  link the human opens against his own dashboard, which is small; under #233's
  trusted-LAN mode it becomes any device on the LAN, which is not · fix is probably
  an `escA()` for attribute position rather than widening `esc()`, so text position
  keeps producing readable `"` · red-first: the proof is a `p` containing `"` and an
  assertion about the parsed DOM's attribute set, not about the HTML string, since
  the string looks plausible either way · related: **#375**
- **#376** — A guard given one argument treats the port as its output directory · P2 ·
  dogfood/tooling · origin: **loop** · 20m · **found by two empty directories named
  `39898` and `39899` sitting in the repo root**, created 2026-07-25 09:46 and removed
  today · every guard opens `const OUT = process.argv[2], PORT = process.argv[3] ||
  '<default>'` and then `mkdirSync(OUT, {recursive:true})`, so `node draft.mjs 39898`
  — a port passed where the outdir belongs, which is the natural one-argument mistake
  — creates a directory *named after the port* in the cwd and then screenshots into
  it · **measured: 52 guards read `argv[2]` and 0 of them validate it** (`grep -l
  'process.argv\[2\]' dev/capture/*.mjs | wc -l` → 52; no guard tests it, names a
  usage string on failure, or rejects a digits-only value) · the zero-argument case
  is loud (`mkdirSync(undefined)` throws), which is why only this shape survived
  · the damage is small and the signal is bad: the junk is named like a port, in a
  repo where ports are meaningful and two ranges are reserved, so it reads as a
  server artifact rather than a typo — and it sat for three days without anyone
  asking what made it · rec: one shared `outdir(argv)` helper in `dev/capture/` that
  refuses a missing or all-digits `argv[2]` with the usage line, and every guard
  calls it — a sweep, not 52 decisions · **blocked on `dev/capture/` being free**:
  dreamer-284-252 holds it and a ccc lane is adding one file there, and a 52-file
  sweep would conflict with both · red-first is easy and worth doing properly: run a
  guard with a single port-shaped argument and assert no directory by that name
  appears
- **#375** — Focus is indistinguishable from hover on `.pipbtn`, and the fallback
  ring computes to near-black · P3 · bug/a11y · 20m · origin: **loop** · found by
  the fileview dreamer, out of its scope · `.pipbtn:hover, .pipbtn:focus-visible {
  color: var(--accent) }` gives both states one appearance, so a keyboard user
  cannot tell where focus is when the pointer happens to rest nearby, and the UA
  fallback ring on this page computes to `rgb(16,16,16)` against a dark surface —
  effectively invisible · this is the same shape as the `.fcopy` bug that dreamer
  fixed in the same increment, which is why it is worth a sweep of the page's focus
  states rather than a single-selector patch: the pair-selector idiom is likely
  copied elsewhere · `watch-design.md` should end up stating the focus-vs-hover
  contract once, so the next component inherits it instead of re-deciding · related:
  **#374**
- **#373** — Build topic chats v2 on the accepted R1 direction · P1 · feature ·
  origin: **human** · **answered via watch 2026-07-28 02:56**: *"rec, after cli and
  sqlite"* · succeeds **#229**, which closed as decided the same minute — R1 is the
  direction, and the artifact of record is
  `.dreamwork/review/threaded-topic-chats-v2.html` (`9f08e47`), which supersedes v1
  for future design while retaining v1 as history · the direction itself: one
  recovery spine (client attempt → durable #263 receipt → application → transcript),
  starts with the main dreamer, requires an explicit *proved* WorkerAdapter
  promotion, shares cross-process leases and caps, attachments are MVP not later,
  indexes stay derived, and the unreachable review composer is replaced by a
  viewport dock plus mobile Document/Discussion tabs
  · **the seam that sets the order** · **human via watch 2026-07-27 23:24**: *"we
  should use the cli only to interact with topic chats. Whatever directory they are
  in, we need an AGENTS.md (and CLAUDE.md symlinked to it) that specify to always
  use the dreamwork cli to interact with the topic chats."* · so chat storage is
  reached ONLY through the `dreamwork` CLI, no agent reads or writes those files
  directly, and the prohibition is enforced **where it is discoverable** — an
  `AGENTS.md` in the storage directory with `CLAUDE.md` symlinked to it, so an agent
  that wanders in meets the rule instead of having to have been told · this is the
  same seam he approved for #287 (touch tasks only through the CLI, never the file),
  now stated as a general pattern · which is why his two words are a dependency and
  not a preference: **blocked on #294** (SQLite ledger + CLI API) **and #346**
  (entity schema + read-only CLI surface) — building the UI first would mean
  building precisely the direct file access the rule forbids
  · **what approval did not lift**: #263 prove-applied reconciliation, the
  WorkerAdapter proof, #239, and consumption of landed #266 plus #269/#271 · v2
  review record: architecture PASS; Vision/Geometry FAIL → fix → PASS (clipped
  decision navigation, a detached mobile v2 marker, a 1.5s long-range smooth scroll,
  all three fixed); offline clean, instant bounded decision navigation
  · #236, #235 and #230 were blocked on "#229 approval" and now point here

- **#228** — Unify project dashboard settings · P2 · idea · 30m ·
  origin: **human** · implication of **human via watch 12:49**: all
  settings persist and stay identical across tabs and separate browsers ·
  inventory tint + future settings; define one server-side project-settings
  contract carried by `/data.json` + `/mtime`, while typed drafts/submission
  history stay browser-local because they are private words · do not migrate
  only for abstraction unless #227 demonstrates the need
- **#227** — Open the composer with Space · P2 · idea · 30m ·
  origin: **human** · **human via watch 12:49** · when focus is outside
  every interactive/editable control, Space opens composer and autofocuses
  input · subtle enable checkbox; preference persists server-side and syncs
  across tabs + separate browsers, never localStorage · needs settings format,
  migration, keyboard red proof, and transition-conformant UI

- **#225** — Add an `explore` proposal command · P2 · implementation ·
  origin: **human** · **approved via watch 18:25** · one-shot fresh research/
  design subagent produces one concise offline-clean decision artifact with
  alternatives, unknowns and smallest experiment; proposal-only authority;
  accepted outcomes become ordinary tasks · command is a real accessible
  composer kind in exactly maintenance-style secondary disclosure: absent from
  default visible row, never initial, discoverable by established cycling/
  secondary affordance and keyboard/touch · red-first, implement in increments


- **#148** — Two sibling guard dirs, one contract, no shared runner ·
  P3 · chore · 30m · fine while they have different owners, wrong the
  moment they do not; extract when a batch would have used it (#124)
- **#205** — [plan: `docs/plans/heartbeat-into-monitor.md` — ezfb's
  `run_watch()` READ and mapped; timeout-on-receive, quiet limit 7,
  `on_quiet` = #200's audit seam] Roll the heartbeat INTO the monitor ·
  P2 · idea · **human 17:45** · **answer to his question: no, not integrated here** — this
  target runs three independent monitors (heartbeat 4.75m, events tail,
  inbox tail) and the timer fires regardless of whether anything
  happened; `ez-feedback-pipeline` has the combined shape, READ IT ·
  today the heartbeat fired ~40 times and most arrived mid-increment or
  mid-stream, where the right action was nothing — the timer is the
  loudest input and the least informative · buys quiet-time, backoff,
  event-driven wake (removes SKILL.md's own warning that an unarmed tail
  loses his `do now:` silently), and his "patterns and schedules" ·
  **CEILING**: 4.75m sits under the prompt-cache TTL, which is why the
  loop is cheap — state that in the design, do not discover it on a bill
  · relates #180, #200, #203
- **#204** — [#166's handler takes a LIST of surfaces (9ed526f) and its
  red-first run is this bug's direct evidence — six motion checks red on
  the native toggle while every end-state check stayed green — BUT the
  list path only fits members of a KEYED LIST, which the four plain
  peeks are not; they want the `.qsec > summary` shape instead (panels,
  bound report). NOT a one-liner; do not let the first annotation here
  suggest it is] The four plain `expand()` peeks still snap · P3 · task ·
  25m · dreams, archive, `.md` list, status overflow · **excused by the
  reason #196 just disproved** — "nothing that MOVES sits below the
  toggle", and all four have panels below · now marked UNEXAMINED rather
  than decided in both docs, so the trap is disarmed · his rule says
  "no size below which this stops applying"; rec: apply #196's
  section-fold shape to ONE and see if it falls out cheaply before
  deciding all four · after #199
- **#201** — Stream and control an agent's TUI in the browser via herdr ·
  P2 · idea · several increments · **human 17:27** · substrate EXISTS and
  is documented: `~/.llm-general/ai-coding/herdr/` verified against 0.7.4
  protocol 16, PTY panes over a Unix-socket NDJSON API + status
  classification; two reference consumers · **read those docs, do not
  re-derive** · **the hard constraint**: watch/dreamhub are stdlib-only,
  single-file, no build step, offline — a browser terminal normally means
  xterm.js · three options (vendor a single-file build · render the ANSI
  subset ourselves · render STATE not the TUI) and it needs deciding
  before code · **it turns dreamhub from read-only into a control plane**
  — the localhost bind and per-target isolation must survive explicitly ·
  **`/compact` button FIRST**: `compaction.md` already has the protocol
  and #127 parks the sender in stage 2, and it needs NO rendering, so it
  tests the herdr path before committing to an emulator · #202 resolved:
  **T3 Connect is Clerk discovery/linking + managed Cloudflare reachability,
  not a terminal/agent protocol**; primary-source research at
  `.dreamwork/docs/research/t3-code-connect.md` · before implementing terminal
  rendering, investigate a supported T3 Code deep-link/embed/adopt-session API
- **#200** — Monitor context usage; threshold triggers a self-audit ·
  P2 · idea · 2 parts · **human 17:23** · his example ("3 questions
  answered ages ago, forgotten?") turned out to be guard pollution, NOT
  his answers — but he could not tell, and that proves the point better
  than the example would have: **nothing in the loop notices that
  something was answered and never acted on** · **(1) do the cheap half
  first**: an entry carrying an Answer/Note sub-bullet while still under
  `## Open` IS by definition unprocessed, and the timestamp is right
  there — dashboard shows "answered 3h ago, not folded", lint WARNs past
  an age; no context monitoring needed and it would have caught today's
  case instantly · **(2) the general one**: MEASURE FIRST whether an
  agent can read its own context usage programmatically — if not, the
  fallback is a proxy and a proxy must say what it is not (#155) · the
  self-audit is worth having as a maintenance item regardless of trigger
  · **#199 gives this its input** — a raw log of everything received IS
  the "what was sent to me" half
- **#215** — No check notices a visual change it was not told to watch ·
  P3 · idea · 30m · #166's `summary::before` legitimately shifted the
  sha column 2ch right and only a human screenshot look caught it —
  "no check noticed a visual change" is the shape this repo keeps paying
  for · candidate: assert the x-position of load-bearing columns in the
  guards that own them, or a coarse screenshot-diff capture (NOT gated)
  that flags layout deltas for a human eye · relates #210's vacuity class
- **#211** — A title that GAINS a priority departs and arrives instead
  of travelling · P3 · idea · 20m · honest today (`data-qid` is the
  title, and the title changed) but a human watching the loop stamp
  `P1 · ` onto an existing question sees a card vanish and a stranger
  appear where it should have been the same card moving up · needs a
  stable identity that survives a title edit, which is the same question
  #77's cross-group morph already answered once — read it first
- **#196** — Dashboard questions section snaps instead of arriving ·
  P2 · bug · 25m · **human 17:12** · `.qsec` from #141 · the page learned
  this lesson all day one surface at a time (#129, #113, #169) and the
  one disclosure he clicks most never got it · build AGAINST
  `transitions.md` — it is the first thing built against that guide ·
  opening is an arrival, closing is a departure and per #174 leaves in
  the direction its list travels · **dreamer-qsec holds it**
- **#194** — [plan: `docs/plans/version-and-upgrade.md`] Version and
  upgrade: `ud-dw-githash`, DREAMWORK.md frontmatter, commit-range pass ·
  P2 · task · 4-5 increments · **human 17:07** · executable reports the
  skill's own version (hash+dirty in a checkout, hardcoded in a CI-built
  zip), read on EVERY load, compared against a hash in DREAMWORK.md's
  YAML frontmatter; on a difference a cheap subagent reads the
  intervening commits for migrations and features worth surfacing ·
  **plan keeps `migrations/` deterministic and makes this the DISCOVERY
  layer** — it reports, it never migrates, because a file existing beats
  a model reading prose · **do the commit trailers FIRST**
  (`Migration:`/`Config:`/`Consent:`) — greppable beats readable, and
  every commit written before they exist is one the pass reads blind ·
  frontmatter changes a file every target has, so it needs its own
  migration + a file-formats row + a lint check in the same commit ·
  **one open question:** endpoints are old DREAMWORK.md hash + new
  `ud-dw-githash`; repo becoming public removes auth but zip/offline still lacks
  intervening objects · rec layered resolver: local Git history, packaged
  generated changelog, explicit public fetch fallback · exclude this development
  checkout from treating ordinary new local commits as release upgrades ·
  trailers LANDED pre-compaction ·
  **githash LANDED 472b9e8** (output is the contract; 8 tests red-first)
  · **frontmatter LANDED 5c19a68** (file-formats row + lint check +
  migration `2026-07-25-14` + this target stamped, one commit) —
  remaining: init step, discovery subagent (both after the open
  question)
- **#193** — A blocked errand is invisible · P2 · task · 25m · an
  errand's `awaiting_human` in `~/.config/dreamwork/tasks/` is read by
  NOTHING; hub listing is opt-in (right call) but the consequence was not
  followed through · same shape as #130/#141 (awaiting_human means HE is
  the bottleneck) and #144 (a silent channel looks like a quiet one) ·
  becomes urgent the first time an errand blocks, which is exactly when
  nobody is watching · rec **(a)**: the errand writes a marker into its
  PARENT target's `.dreamwork/`, reusing a surface that already has his
  attention · inherited by dreamhub stage 2 or dreamtask stage 6,
  whichever is planned first — say so in that plan or it parks twice

- **#189** — World-space anchoring silently collapses on native
  Wayland · P2 · bug · 35m · `screenX`/`screenY` return **0** on native
  Wayland by protocol, so #74's world space becomes "both windows at the
  origin" — no error, and indistinguishable from the feature being off ·
  **you cannot detect the mode from JS**, so detect the SYMPTOM and
  degrade honestly · it works for him today only because his Brave runs
  `--ozone-platform=x11` for an unrelated KWin bug, which could be
  reverted any time · **blocks #187's T1**: the ripple would ride a
  coordinate system that does not exist · research:
  `docs/research-window-coords.md`
- **#188** — Review rows show who they are waiting on · P2 · idea ·
  25m · **not a new state system — the QUESTION axis one surface over**:
  a review is paired with a questions.md entry, so its state IS that
  entry's, and #113 already settled the axis (open = waiting on him,
  awaiting = waiting on the loop, folded = done) · derive from
  `qaState`, so the two surfaces cannot disagree and a review with no
  question becomes visibly unanswerable · the idioms exist: the wisp for
  in-flight (measured free), the accent for him, the dim end for done ·
  **avoid a literal spinner** — this page has a breath, not spinners, and
  a rotating glyph would read as borrowed from another application
- **#187** — A gravity-wave ripple that crosses windows · P3 · idea ·
  60m · **T1** the ripple itself: do it in the SHADER, which is already
  world-space anchored (#74/#100) so one wavefront crosses a window seam
  by construction, arriving later in the further window — "same
  position, same dream" finally used for something · **T2** cross-tab
  sync: the event is tiny, so `BroadcastChannel` plus the existing poll;
  rec against WebRTC for the same result on one machine · **T3
  multiplayer is a THRESHOLD** — everything here is local and has never
  left the machine; decide it separately, and make his "no project data
  ever" rule STRUCTURAL: a fixed-shape payload with no free text, so
  the rule cannot be broken by a later change rather than merely not
  being broken now
- **#186** — A light theme, cycled by seven background clicks · P3 ·
  idea · 90m · **his last sentence is the design**: three states cycle
  and `system` RESOLVES to one of the others, so a cycle can change
  state without changing a pixel — show the state by NAME
  ("system (light)"), because a flourish acknowledges the click where a
  name answers it · **the cost is not the cycling, it is the
  calibration**: the page is dark by construction, and the ramp, accent,
  `--warn`, shader, `.dreamin` blur and favicon were each tuned against
  a dark field, several BY LOOKING · tokens must become the only source
  of colour first, which is an audit pass of its own · #143's six hues
  become twelve, and the amber exclusion band probably moves
- **#185** — A consent gate: blurred, explanation on hover · P2 · idea ·
  45m · a PATTERN, not one panel's chrome — any surface reading
  something sensitive can use it · the design is good because the
  skeleton shows the SHAPE of what is offered without the content, so
  he consents to something he can see the outline of · **the blur must
  be real**: if the bytes are in the DOM the gate is theatre, so the
  server withholds until consent — a server-side gate with a
  client-side face · consent is a PERMISSION (machine-local,
  revocable), unlike `watch-tint` which is a preference and committable
- **#183** — [plan: `docs/plans/composer-row.md`] The composer's `+` sticks to the top when scrolling · P2 ·
  idea · 25m · on a long page the way to send a steer scrolls off
  exactly when he has read something and has a reply · **he named the
  hard part**: it collides with #108's clamp, so vertical and
  horizontal constraints are computed by different rules and must work
  together, not in sequence · the `+` is also #170's ANCHOR, so a
  moving anchor breaks a fit test computed once at open · build with the
  composer-geometry batch
- **#182** — Favicon smooth and graceful, with a rolling notification ·
  P2 · idea · 75m · "too slow, does not look smooth" is the direct
  consequence of #153's one-frame-per-second choice — right for a hidden
  tab, wrong for the one he is watching · **two regimes**: rAF while
  visible, the pre-rendered fallback when hidden, switched on
  `visibilitychange` — which also unblocks on-the-fly generation · the
  cylinder rolls a count up, PAUSES to be read, rolls away · "get super
  creative, multiple visual review-and-fix loops" is a method
  instruction; taste is the deliverable
- **#180** — Stream the dreamer's own events onto the dashboard · P3 ·
  idea · 120m · **APPROVED** 15:36 with his own mitigations, which beat
  the shapes offered: read only the **last 10-20 lines** (the bulk is
  never touched), prefilter to small objects, and gate it behind #185 ·
  counter-rec on `jq`: stdlib `json` does the same job without adding a
  binary the loop cannot assume exists · still needs an answer for
  `resolve_confined`, since the transcript sits outside `--target` and
  that gate is load-bearing · no inotify in stdlib: poll · "4-6
  review-and-improve loops" is a METHOD instruction — report the count
- **#178** — Pretty-print toggle for JSON at `/file` · P3 · idea · 25m ·
  resolves the tension #158 exposed: prose reflows by default, source
  stays verbatim, and JSON is NEITHER — its formatting carries no
  meaning but it is not prose, so reformatting is a VIEW and gets a
  control · general rule worth stating: reformat by default when the
  original formatting carries no meaning AND he never wants it back;
  offer a toggle when he might
- **#176** — Paste images into the composer and answer boxes · P3 ·
  idea · 90m · **the biggest new surface the page would gain**: a fifth
  write exception that takes ARBITRARY BINARY, where the other four take
  a short validated string. `resolve_confined` gates serving; an upload
  needs its inverse and there isn't one · **where they live is a real
  decision**: outside the repo means a pasted screenshot never travels,
  so a question read on another machine has text and a broken link ·
  it changes `questions.md`'s shape, so file-formats row + lint check,
  and `human_block()` must handle an embed without a crafted path doing
  what a crafted bullet used to · split it: storage first, render second
- **#173** — Live git status, without EVER taking `index.lock` · P2 ·
  idea · 60m · **the lock constraint is a known injury, not a
  preference**: his CLAUDE.md carries an active mitigation from
  2026-07-10 for background `git status` taking the real lock and
  racing his interactive git. So: `--no-optional-locks` everywhere,
  `GIT_OPTIONAL_LOCKS=0` in the server's env, read-only commands only,
  and a guard asserting the lock never appears during a poll · three
  cadences by design (status 5-15s, PR much slower, CI slower still and
  only when a PR exists and is not draft) · PR/CI go through
  `ud-dreamwork-github`, which already owns `gh`
- **#171** — Ascii vignette at the screen edge, from the loop's own
  words · P3 · idea · 90m · "we will play with some parameters" is an
  instruction about METHOD — ship the axes adjustable, expect to steer ·
  the content idea is what makes it belong here: DREAMWORK.md's own
  phrases murmuring at the edge · **never render questions.md there** —
  his words are his · two ambient systems now share a frame budget with
  the shader
- **#170** — [plan: `docs/plans/composer-row.md`] Composer opens LEFTWARD so it stops covering text · P2 ·
  idea · 25m · hang its top-RIGHT corner under the `+` instead of its
  top-left · "when there is enough room" is the requirement: prefer
  left, fall back to right, never clip · the anchor MOVES (#110 travels
  it, #108 clamps it), so the fit test runs at OPEN time, not at load ·
  `position:fixed` is not viewport-relative under a transformed or
  filtered ancestor — measure the rect, as with #160
- **#169** — An expanded element becomes PROMINENT, not just taller ·
  P2 · idea · 35m · expanding is a change in IMPORTANCE, not a reveal —
  the thing he opened is now the subject of the page · extends the
  fold-motion contract and belongs to the IDIOM (#111, #141, and
  #165/#166 inherit it) · **two traps**: `font-weight` steps rather than
  transitions unless the face is variable, and growing padding moves
  everything below, so the growth and #104's neighbour travel must be
  ONE gesture — the #141 lesson again
- **#168** — Keyboard shortcut opens AND focuses the composer · P3 ·
  idea · 20m · **check #92 first** — a Ctrl+K palette is already filed
  and two answers to one question is worse than either · the hotkey trap
  is already a lesson: a bare key must ignore keystrokes while a text
  field has focus, and this page now has many · rec open-or-focus,
  NEVER toggle-closed: a keystroke that discards what he typed is the
  #118/#131/#162 family. Escape closes
- **#167** — Composer text box translucent, blur on Chrome only · P3 ·
  idea · 25m · reading "a little blue" as "a little BLUR" (the Firefox
  parenthetical settles it) — flagged, since a blue TINT would collide
  with #143 · `@supports` cannot gate this: Firefox supports
  backdrop-filter, it is just expensive · rec UA-gate with the reason in
  a comment, because the measure-and-back-off alternative FLICKERS ·
  measure p95 with it on and off; blur over a live shader is the most
  expensive pairing on the page
- **#164** — [plan: `docs/plans/composer-row.md`] The button row becomes an information scent · P2 · idea ·
  75m · his verbatim design: the row is a CONVEYOR — non-default
  commands apparate at the left, push the rest right, and are consumed
  by the `...` menu at the right, sliding UNDER it and fading by
  PROXIMITY (not time) as they approach. Selecting a default slides
  everything back left. Reuse #104's regroup on a horizontal axis ·
  subsumes #162(a): a row that cannot wrap · depends on #161
- **#162** — Composer cosmetically vanishes on a mode switch · P3 · bug ·
  15m · the original wrapping half was subsumed by the composer-row plan;
  #163's guard proves the draft survives live and stored (8d0e6a7), so the
  remaining mode-switch disappearance is cosmetic, not destructive ·
  reproduce before changing the #131 dismissal path
- **#161** — [plan: `docs/plans/composer-row.md`] The composer's `...` menu: position, shape, vocabulary ·
  P2 · bug · 20m · centre the dots (MEASURE first — #123 was the same
  shape and took two wrong diagnoses) · **on the RHS, in the button row
  but hard right with a gap** (his 14:31 refinement) · fill, no stroke:
  a menu REVEALS where a button ACTS, so **outline means "this acts",
  fill means "this reveals"** belongs in watch-design.md as vocabulary,
  not as styling for one control. The fill is a surface colour, never
  the accent · #164 depends on this
- **#160** — Frame-time graph should hug the RHS wall · P3 · bug · 10m ·
  check `position:fixed` is not containing-block-trapped by an ancestor
  with transform/filter (already a lesson, and this page has several) ·
  and confirm the overlay is dev-only — a diagnostic that reaches him by
  accident is the more interesting bug
- **#159** — "sent to the dream" appears instead of arriving · P3 · bug
  · 15m · use `.dreamin`, which only started working today (#154) ·
  ~~check the departure too~~ **answered, do not re-derive** (2026-07-27,
  folded from the gesture batch dream before archiving it): the two
  hand-clears are *retractions* — the page withdrawing a claim that has
  become false — not departures, and the real departure is the panel's,
  which already drifts away on the same soft blur it arrived on. A false
  confirmation that fades slowly is a false confirmation that is quieter,
  so this was recorded in `watch-design.md` (#159/#255, "what it says
  arrives and departs") rather than animated · that leaves only the
  ARRIVAL · verify by per-frame trace, since a two-frame
  fade looks instant and passes a "did it appear" check
- **#152** — A dangling-parent check, deferred WITH A TRIGGER · P3 ·
  chore · 15m · (b) prose-wrap: measured, do not build — eleven long
  lines, three of them unwrappable frontmatter · (a) the ledger carries
  ONE chain line and that is correct, so a checker today checks nothing.
  **Build it when #114 lands** (chains become something he sees) **or
  when there are >5 chain lines**. The check is right; the timing is
  wrong
- **#133** — Teach watch.py a URL prefix · P3 · task · 45m · do it
  inside #124's server-core seam; unblocks the single-URL hub layout
- **#122** — Smokey awaiting-fold text: the words warp, a ghost copy
  blows backwards into the aether · P2 · idea · 60m · his brief is
  verbatim in the task; it is the dream dissolve's ghost held low and
  continuous, not a new effect. Taste is the deliverable — wants a
  dreamer that iterates on captures until satisfied
- **#124** — Break up watch.py; norms for cheap parallel work · P2 ·
  task · 120m · plan: `docs/plans/parallel-architecture.md` · seams as
  batches demand them, starting with #112's components
- **#112** — Design proposals become fragments + shared template · P2 ·
  task · 90m · plan: `docs/plans/artifact-templates.md`
- **#207** — Deletion must be observable, as a CLASS · P2 · idea · 30m ·
  from #86's first find: `watched_mtime` statted only files, so a
  deletion could never change it and an unloaded plugin haunted the menu
  until an unrelated write · the instance is fixed (a5a889d walks the
  directories) but the class is unguarded — several contracts here are
  "unloading is the absence of a write" (fold-by-complement,
  human_block, plugin-commands.json) and all assumed absence was
  observable, unchecked · a guard that DELETES (a dream, a review) and
  asserts the open page loses it would cover the class, not the instance
- **#98** — Show the open queue on the watch dashboard · P2 · idea · 40m ·
  new page surface, fit-check at selection
- **#114** — Dashboard renders the active goal chain · P3 · task · 25m ·
  stage 3 of #95; status.json already carries `goal`
- **#92** — Hand-rolled Ctrl+K command palette · P3 · task · 40m
- **#99** — [plan: `docs/plans/composer-row.md`] **P2** The popout composer has DIVERGED · task · 25m ·
  re-raised 15:48 with detail · it still carries the dropdown #103
  replaced, and has missed #121, #161 and #164 since — `lessons.md`
  says a second mount is the cheapest audit of the first, and nobody
  ran it, so the popout became a museum of the composer's previous
  state · **the fix is "there is ONE row", not "restyle the popout"**:
  build #164's conveyor as a component both mounts use, and it cannot
  drift again · his extra-width idea then falls out FREE — more width,
  more buttons visible before they tunnel, no special case · depends on
  #161 and #164; doing it first means building the row twice ·
  **it drifted AGAIN at 16:54**: the popout has its own `.pmsg`, so
  #159's arriving confirmation arrives inline and still POPS in the
  popout · dreamer-gesture left it deliberately (fixing it in two places
  makes the copy harder to delete, not easier) — the right call, and the
  fourth divergence this task has collected
- **#100** — Shader lens world-space so blur matches at a window seam ·
  P3 · task · 30m · the last break in "same position, same dream"
- **#73** — Split-view support for watch pages · P3 · experiment · 30m ·
  the shader half landed as #74; the open part is the affordance
- **#50** — ud-dreamtask stage 6: harvest past dreamstates · P2 · task ·
  gated on Max · stages 1-5 are complete in the installed sibling repo;
  only the core-init widening remains, and its open question recommends
  waiting for real dreamtask use before deciding what is worth harvesting
  · **UNBLOCKED 2026-07-28 02:53 — he answered "rec go".** The rec was *"yes, but later"* and the
  hedge was the loop's own, about timing; his word is go. So this is authorised for a **plan**,
  not for widening the core loop's init yet
  · the gate was never about value but about surface: stage 6 reaches back into ud-dreamwork, so
  it touches `initialization.md`, a migration, and probably `file-formats.md` and `lint.py` — new
  surface in the core loop rather than in the sibling · a plan settles that shape without
  widening anything, which is why planning is separable from doing here
  · and the reason for waiting has partly expired in his favour: the rec argued a week of real
  dreamtask use would teach more than a design conversation, and what has accumulated since is a
  `lessons.md` this repo prunes **by hand** — so the harvest question now has a concrete case to
  design against · rec: plan it against that case specifically, not against harvesting in general
- **#80** — Pick a second dogfood target (hark or c2c) · P3 · chore · 30m ·
  **blocked**: human pick

- **#417** — the burndown should show commits per period, without spending the design it already
  has · P2 · Web UI/dashboard · origin: **human** · **human via watch `add-idea` 2026-07-28 14:58**
  · verbatim: *"burndown chart should show how many commits were made each period. design needs to
  be considered since we have a pretty good design now and it would be easy to make it worse."*
  · **the caution is the requirement, not a politeness.** He is not asking for a bar chart behind
  the line; he is saying the current burndown is at a quality he does not want traded away for the
  extra series. So the deliverable is a **design proposal first** — a review artifact showing the
  candidate treatments against the real chart with real data — and implementation only after he
  rules. Shipping a provisional version is the failure mode `#367` inc 2a already names: what ships
  is what gets argued with
  · the hard part is that commits-per-period is a **second quantity in a different unit** on a chart
  whose whole legibility comes from one line meaning one thing. Density beside a trend is the
  classic way a good chart becomes a busy one
  · **proposal artifact landed `5fe331a` (glm52, `wt/417`), 2026-07-28 18:09 — four treatments priced,
  none picked, which is what the brief demanded.** `.dreamwork/review/417-burndown-commits.html`:
  `C1` faint histogram behind the flow, `C2` sparkline rail beneath the axis, `C3` commit count in the
  level line's weight, `C4` copy only. One table, every candidate carrying **buys / costs / makes
  harder to read** plus **guard** and **motion** columns. Ten real renders of the real panel against
  the live ledger, verified by me as **10 distinct sha256s** at both viewports
  · **the guard answer is quantified, which is the part a proposal usually leaves vague**: `C1` and
  `C3` hold the constant-height premise at 177px, `C2` grows the panel to 202px and so **breaks the
  `burndown` guard**, `C4` costs 19px and inherits `#218`'s treatment with **no new motion idiom**.
  The other three each need one
  · **visual verdict DISCHARGED 19:10 by the coordinator, who can see** — not owed, and not waiting on
  grok. Extracted the ten embedded renders and read them. **`c1` is invisible** at the panel's real
  553px (indistinguishable from the reference, because the panel already carries two bar series);
  **`c3` degrades the primary signal** (the level line goes chunky and noisy, and thickness cannot be
  read as a quantity) — so I **disagree with the lane's `c3`-as-shape-fallback** and say `c2` is the
  answer if he wants shape, since it is legible in its own band and labelled; **`c4` truncates as
  rendered** (*"3 periods with n…"*), which the lane priced honestly but which reads as broken, so
  shortening the copy is a condition of `c4` rather than an argument against it
  · **the standing lesson**: three artifacts have carried *"visual verdict owed"* on the assumption
  that only grok can see. **The coordinator is multimodal.** A verdict blocked on a 401 for twelve
  hours was never actually blocked
  · blocked-on: **human** — asked 2026-07-28 18:11
  · candidate treatments to price, not a decision: a faint baseline histogram behind the burndown;
  a thin sparkline rail beneath the axis; encoding it into the existing line (dot size or segment
  weight per period) so no second scale is introduced at all; or on-demand only, in the hover
  readout, where it costs zero permanent ink
  · **whatever it becomes obeys `transitions.md`** — a new series appearing, or a hover readout
  arriving, is a transition like any other, and this repo's rule has no size floor
  · needs `watch-design.md` updated in the same commit as any code, per the styleguide contract
  · related: **#367**
  · **IN PROGRESS 2026-07-28 17:28** — `ccc @glm52`, `.worktrees/417`, brief
  `417-burndown-commits-proposal.md`. **Proposal only: it commits the artifact and NO `watch.py`
  change**, and may modify `watch.py` uncommitted purely to render the candidates. That split is the
  `#367` lesson applied before it costs anything — what ships is what gets argued with, and a
  provisional treatment in the tree becomes the default by inertia
  · four candidates priced, `copy only` included deliberately as the option that spends nothing and
  that every other has to beat. Two costs a screenshot cannot show are demanded per candidate: which
  break the panel's **constant-height premise** that its guard measures, and which need a **new
  motion idiom** under `transitions.md`
  · **the runner cannot see and that is fine here** — the artifact's job is to put pixels in front of
  *him*, not the lane. Renders come from the live ledger history rather than a fixture, because a
  treatment that survives three tidy buckets and fails on the real distribution is what this exercise
  exists to catch
  · note for whoever reads the panel next: `#218`'s median line landed in it at 17:19, so it is
  fuller than the last person to look at it remembers

- **#418** — a `#264` in any rendered text should be hoverable for its info and clickable to its
  task page · P2 · Web UI/cross-cutting · origin: **human** · **human via watch `add-idea`
  2026-07-28 15:03** · verbatim: *"for after sqlite and `/tasks` impl, when dreamwork tasks are
  referenced like `#264`, it'd be great if I could hover to get their info (and click to open
  their task page)"*
  · **he stated the dependency himself**, which is the useful part: this is *after* `#294`'s
  SQLite cutover and `#281`'s `/tasks` page. Both are prerequisites for the honest reason — the
  hover needs **single-entry fetch by id**, which is exactly the read verb `#346` is designing
  (`?t=<id>`), and building it against a Markdown re-parse would be a second implementation
  thrown away at cutover
  · scope is wider than it first reads: task ids appear in the ledger panel, question bodies,
  hand-off lines, commit subjects on the git row, and review artifacts. **A treatment that only
  works in one surface is the wrong answer** — the id is a cross-cutting reference type, so this
  wants one linkifier consumed everywhere, in the spirit of `#331`'s one-span rule
  · the hover surface itself is a solved problem here and must not be re-solved: `#300` landed one
  geometrically stable popover that morphs its content between triggers, and `transitions.md`
  governs its arrival and departure. **Reuse `#rundesc`'s idiom rather than authoring a second**
  · open question for whoever takes it, worth settling before any code: what does hover show for
  an id that does not resolve — a landed task, a withdrawn one, a typo? `#402`'s lesson applies:
  *"I could not tell"* and *"nothing"* must not render the same
  · related: **#294, #346, #281, #300**

## Recently landed
- **#463** — review artifacts sort and age by the wrong timestamp · P2 · UI/review · origin: **human** ·
  **human via watch 2026-07-29 02:30:** *"fix the assets for review sorting — they should use ctime not mtime.
  And the age should show since ctime, not mtime. However, when ctime != mtime, we can show a 'modified X ago'
  msg to the right in a slightly different color. separate it from the age with a dot."*
  · so three changes, and the third is the interesting one: **the two facts coexist** — created-age is the
  primary, modified-age is secondary and only appears when it differs, dimmer, dot-separated
  · the dot separator and the age treatment already exist (`#456` landed the day-age separator and found
  `.qage`'s margin would have doubled the gap) — reuse that idiom rather than authoring a second one
  · note *ctime* in his sense is **creation**, which POSIX `st_ctime` is not (it is inode change) — decide the
  source of truth (birth time via `statx` where available, else the artifact's own build stamp or first commit)
  and say what happens when it is unavailable, rather than shipping `st_ctime` and calling it created
  · related: **#456**
  · **LANDED `e1db28d`, merged `a63930a`** — birth via `statx stx_btime` (`st_birthtime` on BSD), never
  POSIX `st_ctime`; `created unknown` is a named state that sorts after every known artifact rather than a
  silent fall back to mtime; the secondary is dimmer and dot-separated per `#456`
  · **the trap fired, and the lane's own test caught it.** Exact `created_ns != mtime_ns` flags **24 of
  this repo's 28 artifacts** — writing a file sets birth, then the content write moves mtime a few hundred
  microseconds later — so nearly every row would have read `3d old · modified 3d ago`, the exact inverse of
  his rule. **An exactness the reader cannot see is not a difference:** the server marks a *candidate* and
  `ages()` decides beside `ageStr`, dropping the pair when both render the same string. No threshold
  invented, and the formatter is not mirrored in python — that would be a second copy of the thing whose
  output is the criterion
  · **on his corpus the secondary is rare, and that is correct** — 0 of 28 differ at display resolution
  today, because each artifact is written once. It appears when `review_artifact.py` rebuilds one in place,
  which is the case he described
- **#464** — the command composer's scrollbar appears and disappears, reflowing his text as he types · P2 ·
  UI/polish · origin: **human** · **human via watch 2026-07-29 02:30:** *"make the scroll bar in the command
  composer always show. It causes text to reflow when it disappears after the text box grows large enough to
  hold all the text. It's a bit distracting."*
  · the reflow is the symptom of a width change, so reserving the gutter is the fix; `scrollbar-gutter: stable`
  is the cheap form, a permanently-visible bar the literal reading — his words say *always show*, so decide
  which he means and note that a gutter with no bar still removes the reflow
  · check it against the autogrow behaviour that makes the box tall enough in the first place, and against
  reduced-motion
  · **LANDED `a443b33`, merged `a63930a`** — `scrollbar-gutter: stable` on the composer textarea. The lane
  chose the gutter over a permanently visible bar and gave the reason: it removes the reflow he described
  **without** adding furniture to the page. If he meant the literal bar, it is a one-line change
- **#465** — a lane can edit the MAIN CHECKOUT instead of its worktree, and nothing notices until a merge fails ·
  **P1** · loop-machinery/containment · origin: **loop** · found 2026-07-29 03:32 when the `#263` merge aborted:
  `error: Your local changes to the following files would be overwritten by merge: dev/capture/health.mjs`
  · **what happened**: the `#413` lane was dispatched into `.worktrees/superseded` on `wt/superseded` and its
  brief named the worktree twice, but it edited `dev/capture/health.mjs`, `.dreamwork/docs/doc-map.md` and wrote
  a new plan file **in the main checkout on `master`**. Its own worktree stayed untouched. The `ccc` invocation
  ran with the worktree as cwd, so this was not a dispatch error
  · **two harms, one realised.** Realised: it blocked a verified merge that had been deliberately held for half
  an hour, and the coordinator cannot fix it by reverting, because reverting under a live agent destroys work in
  progress — so the merge waits on a subagent's acknowledgement. Unrealised but worse: **a `git commit` by the
  coordinator would have swept the lane's half-finished edits into a ledger commit under the wrong message**,
  which is `12f47e3` exactly, and `--only` does not help when the file is one the coordinator is also touching
  · **the invariant this breaks is the one the whole fan-out rests on** — *"parallel increments only ever touch
  disjoint files, so there is never a split brain"*. A worktree makes that hold **by construction**, and that
  guarantee is void the moment a lane writes outside it. The brief cannot enforce it; only a check can
  · **candidate mechanisms, none built**: a pre-dispatch marker file the lane must find in its cwd and assert;
  the coordinator asserting a clean main tree before each merge and naming the culprit paths (cheap, catches it
  late); `git config core.hooksPath` with a pre-commit hook in the main checkout that refuses a commit touching
  paths a dispatched lane owns (`status.json` already records ownership); or dispatching with the worktree as an
  explicit `-C` rather than trusting cwd. Decide with an IGC — a mechanism that only warns after the fact fails
  the goal *"the coordinator never has to ask a subagent's permission to merge"*
  · **`status.json` already carries what a check would need**: which lanes are out and what files each owns. That
  was built for a compacted coordinator; it is also the registry a containment check can read
  · related: **#450, #402, #413, #468**
  · **LANDED `58e3040`, merged `ef5db01`** — `dev/lane_guard.py` refuses a main-checkout commit touching a
  dispatched lane's paths, with `lint.check_brief_lane_owns` making a brief that declares nothing loud at
  write time. `Needs: config` — `core.hooksPath` is machine-local, so the script is committed and enabling
  is a documented step
  · **it refuted this brief's own premise by measuring it:** `status.json` carries **no** file-ownership
  field, so any mechanism reading an ownership list out of it reads nothing and passes vacuously from the
  day it ships. Ownership comes instead from the brief the lane was actually handed, as a machine-parseable
  `Lane-owns:` line
  · **honest about its ceiling:** R5 fails at first **commit**, not first write. The only rival that fails
  at first write needs the lane's cooperation, which is exactly what already failed — and both harms here
  were commit-shaped. The pre-merge assertion (R2) is the successor, deliberately unbuilt: `#468`
- **#413** — a guard can encode a SUPERSEDED contract, and nothing measures that · P2 ·
  verification/meta · origin: **loop** · found by fixing `qacard`, which had been red since
  `#392a` landed at 09:43 and was being reported as "pre-existing, not our fault" by every lane
  since
  · **the case.** `#385` required every question age to match `^\d{2}[a-z] \d{2}[a-z] ago$`.
  `#392a` then made the figure COUNT the precision signal — two figures means we know the time,
  one means we know only the day — and every questions entry is date-only, so the guard could
  only pass by rendering a precision the data does not have
  · **it was inverted, not merely stale, and only the red-proof showed that.** Injecting `#392`'s
  exact bug (`if (el.dataset.day === '1')` → `if (false)`) bypasses `paintDayAge` and produces
  the two-figure form, which is precisely what the old assertion demanded. **Green with the bug
  present, red with the code correct.** A stale check is noise; an inverted one actively defends
  the defect, and nothing in the output distinguishes the two — both just say FAIL
  · **the structural gap.** `just audit-styleguide` measures code-against-doc and is clean.
  `watch-design.md` had been correct since `#392a` — it documents both rules in adjacent
  paragraphs. The doc and the code agreed; **only the check disagreed with both**, and no tool
  looks at that edge. Fixed in `7007d5b`
  · **what makes it stick, not just noticing harder**: a red guard that a lane is TOLD is
  pre-existing becomes invisible — three lanes have now been briefed with `qacard docktarget
  noteprop` as known-failing, which converts a real signal into paperwork. **A failure excused
  in a brief must carry a reason and an owner, or the excusing is the bug**
  · **next, and cheap**: `docktarget` and `noteprop` are the other two, both dock-motion, both
  excused the same way. Check whether either is the same class before assuming load flake — they
  have been called flaky without anyone injecting anything. Do it at **low load**; the last
  reading was at load 21-29, where a motion guard proves nothing
  · **MEASURED 12:55, and the "load flake" story is WRONG — two of the three are a real
  regression.** I ran all three at load ~20. `docktarget` and `noteprop` fail on **four
  assertions that are all the same invariant**: *"dock visibly remains original after in-memory
  reorder"* (note + answer modes) and *"the dock stays on the same stable target"* (normal +
  **reduced** motion). One behaviour, four ways, and the reduced-motion arm failing beside the
  animated one rules out a motion-timing flake outright
  · **bounded by measurement, not guessed.** Both PASS at `d306b10` (07-27 22:42) *and* at its
  parent, so `#324`'s reporter conversion — which is what made me suspicious, since the three
  failing guards are **exactly** the three converted in its batch 1 — neither caused them nor
  merely revealed them. The break is in the 408 commits since; a bisect is running. `qacard` is
  a different cause entirely and is now fixed (`7007d5b`): it passed at `d306b10` only because
  `#392a` had not landed yet
  · **so the three were never one thing, and calling them one thing is what kept them alive.**
  I have carried "3 known pre-existing failures, possibly load flake" into three briefs. The
  flake hypothesis was never tested against anything — it came from having seen them fail at
  load 29 once. **A shared symptom is not a shared cause, and "pre-existing" is a claim about
  time that gets read as a claim about severity**
  · the dock half deserves its own entry once the bisect names the commit: it is a live product
  bug on `master`, not verification debt like the rest of this task
  · **RESOLVED for all three, and none was a flake** (`7007d5b`, `e15b0c0`). Bisect named
  `0dd136e` (`#385`, 07-28 07:00): it puts a live age **inside** the question headline —
  `qtHtml` emits the span *between* the date and the ` — ` separator — so the raw title stopped
  being a contiguous substring of `#qdock .qt` and four display assertions across two guards
  went red on a page that was behaving correctly
  · **no product bug, and the assertion that proves it is the one that stayed green**:
  `request targets visibly docked question after reorder (#266)` reads `posted.question` from
  **data**, not from rendered text. Identity that must survive presentation was already in the
  right place; only the checks were reading pixels
  · so the three shared a class after all — **guards encoding a superseded contract** — which is
  the opposite of the shared cause I had assumed. `docktarget`, `noteprop` and `qacard` all pass;
  the suite has no known reds left
  · **the fix is one copy of the rule**, `dev/capture/dom.mjs`'s `dockHeadline`, imported by both
  guards: it removes the age **node** rather than regex-stripping text, so it survives two-figure,
  one-figure and `today` alike. Each guard gained a runtime precondition so an empty headline or
  empty expected title cannot pass by vacuity. Red-proved by pointing each at a title that is not
  the docked question — all four fail — then restored from `cp` snapshots with the injection count
  verified back to zero
  · `watch-design.md` now states the contract: **a question headline is no longer its title**
  · **what remains of this task is the meta half**, which is unfixed: nothing measures
  guard-against-doc, and a red excused in a brief still goes invisible. Six hours here, across
  three lanes, on a signal that was correct the whole time
  · **LANDED `4966d9c`, merged `ac6bcf3`** (`@glm52`) — and the measurement came first, as asked: **6 fakes
  inventoried, 4 stale values, 1 blind to a moved contract (`health.mjs`), 1 category match, and `0`
  unverifiable.** Three had pinned values the check did not actually depend on, which is why a
  grep-for-stale-literals approach would have reported work that was not work
  · **its refutation of my brief's framing is the better analysis and I am recording it as such.** Production's
  `/answer` refusal **is** `409` today (`watch.py:10267`), so the pinned value was never stale. The blindness was
  the fake's **scope**: the client branches on `res.ok`, and the fake only ever drove one side of that branch.
  A stale-value checker would therefore have passed over the exact instance that motivated the task
  · **the surviving idea (its `R5`) is an in-guard coverage assertion derived at runtime**, plus a stated
  convention: *a refusal guard must drive the refusal on a status the client treats as SUCCESS as well as one it
  treats as failure, because the moved contract is always the 2xx one.* `REFUSAL_STATUSES` is filled by the
  helper that does the driving, so the fake cannot quietly shrink back to 409-only
  · **two lanes widened `health.mjs` for the same fact** — `E5b` added a hardcoded 202 block, this lane built the
  parameterised version — and I warned this lane about exactly that and it went ahead. Resolved as a union taking
  the parameterised structure (it subsumes the block and adds the coverage assertion) plus `E5b`'s message
  assertion, which the parameterised version had dropped
  · **verified by me on the resolved tree: 20 PASS, exit 0.** Then I reinstated the original blindness — drive
  only the 409, as before — and **`exit=1` with the coverage check and the message check failing**. The two
  *state* assertions did **not** fail, because a `409` also keeps his text and also does not claim answered:
  that is why they were blind on their own, and it is the empirical case for `R5` being the load-bearing part
  rather than the extra status
  · **FOLDED 2026-07-29 03:41.** The stale-value half (its `R4`) is recorded in the plan and not built — nothing
  in the inventory needs it today, and building it would be a checker in search of a defect
  · related: **#392, #414, #420, #442, #444, #461, #465**
- **#400** — `lessons.md` has outgrown being read, and the briefs that tell lanes to read it are
  cargo cult · P2 · loop/memory · origin: **loop** · found by **measuring receipt instead of
  assuming it**, the same instrument that caught the relay
  · **the file is 2,143 lines and 157 entries.** Every brief lists it under *"Read, do not edit"*.
  No lane can read that meaningfully, and the evidence says none does
  · **measured, and the confound is the finding.** Phrases that appear in **both** my briefs and
  lane reports prove nothing — the lane is echoing the brief. So compare the two: `"neighbour"` is
  in **20 briefs** and **51 report lines**; `"outside the system"` is in **4 briefs** and **0 report
  lines**. `lessons.md` itself is named **4** times across ~15 reports. **The lessons that reach a
  lane are the ones I hand-copy into its brief**, and nothing else does
  · **which means the mechanism is working — just not the one I thought.** `lessons.md` is the
  *coordinator's* memory: I accumulate, then select 4-6 relevant ones into each brief's "rules that
  matter most here". That is a good design and it is worth naming as the design rather than
  discovering it again. What is wrong is the vestigial *"read `lessons.md`"* line, which implies a
  lane will find the relevant lesson on its own
  · **it bears on a stated DREAMWORK.md goal** — *"the loop's memory survives anything that ends a
  session; what it knew, it still knows"*. Survival is not the failing half; **retrieval** is
  · rec, and deliberately small: **stop listing `lessons.md` as lane reading**, and keep doing what
  already works. If more is wanted, a short "start here" index of the load-bearing entries beats
  restructuring 157 of them — but measure whether the index gets read before growing it, because
  that is the mistake this entry is about
  · **do not prune to fix this.** I checked: few of today's entries have graduated into checks —
  they are principles, not rules with enforcers — so pruning would cost memory without buying
  readability
  · **re-measured 2026-07-29 03:24 and it is worse, which is the argument for the rec rather than against it**:
  **3021 lines, 38,407 words — about three hours of reading at 200wpm.** The entry's own count was 2143 lines,
  so it grew ~900 lines in a day, four of them added tonight by me
  · **its `do not prune` finding still holds and I checked before acting on the opposite instinct.** I came to
  this intending to prune graduated lessons; the entry had already established that few have graduated into
  checks — they are principles, not rules with enforcers — so pruning costs memory and buys no readability. The
  entry stopped me, which is what a ledger is for
  · **the rec is now implemented, and in the two places that emit the behaviour rather than describe it.**
  `SKILL.md`'s dreamer section says plainly that `lessons.md` is the **coordinator's** memory, that a lane gets
  the four to six selected into its brief, and that citing an entry means quoting it plus its line
  (`lessons.md:991`); `initialization.md` no longer implies the whole file is read at init — the newest entries
  plus a grep on demand
  · evidence the working pattern is already in use: tonight's newest briefs cite specific entries and line
  numbers, while the older ones still carry the vestigial *"read freely: `lessons.md`"* line. Those are history
  and are left alone; the fix is forward-only
  · **FOLDED 2026-07-29 03:24** — deliberately the small version the entry asked for. No index was built,
  because the entry's own warning is that measuring whether an index gets read must come before growing one
  · related: **#394, #405**
- **#461** — an own-server guard grades whatever holds its port, because it never checks whose server answered ·
  **P1** · loop-machinery/verification bug · origin: **loop** · found while verifying `#263`'s `202` cutover
  · **the shared runner is already defended and its comment says the own-server guards are immune. They are
  not.** `justfile`'s `guards` recipe refuses to start when someone holds its port and then compares
  `/data.json`'s `target` to the fixture it meant to serve — but it reasons *"only the guards that start their
  OWN server were immune, so the check belongs here rather than in each of the ten."* That was true of `#203`'s
  failure mode and is false of this one: own-server guards do **not** use ephemeral ports, they take a base port
  and increment it (`ports[name] = ++port`), landing on fixed ports in **39890–39899** — the range that collects
  orphans
  · **and their readiness step is `await sleep(2500)` with `stdio: 'ignore'`.** So when the port is held, python
  exits *address in use* invisibly, the sleep passes anyway, and every later assertion grades a **different
  target** — the guard reports feature bugs about a fixture nothing ever read. 32 of 69 guard scripts read
  `data.json`; measure the adopters rather than trusting that count
  · **the incident that found it**: two probes of the `E3` cutover returned `200` (the pre-cutover fallback) and
  read a correct change as broken. Two orphaned `watch.py` servers from a worktree deleted 2.5 hours earlier
  held 39895/39896, and the probe's own server had died on an argparse error (`watch.py` has no `--no-open`).
  Nothing was mocked — the answer just came from somewhere other than the code under test
  · **fix is a module, not a sweep** — `dev/capture/serve.mjs`, adopted one guard at a time exactly as
  `report.mjs` was, because a one-time sweep of 30 files is stale the day a 31st guard is written. It proves two
  things per port (the child is alive, and `/data.json`'s `target` is the directory asked for), since either
  alone passes over the failure
  · rollout is the successor: `health.mjs` is the first adopter; the rest adopt individually
  · **rollout batch 1 DONE and merged** (`@grok`, three commits `53a8484` / `aec8adc` / `54f8fcd`) — **8 of 18
  own-server guards adopted**: `pushhealth`, `reviewdraft`, `fileimg`, `fileview`, `identity`, `filehead`,
  `gitrow`, `serving`. The lane derived the set itself (`spawn(python3, […watch.py…])` **or** an import of
  `serve.mjs`, so a mere mention in a comment does not count) and reported the expression: **own-server 18,
  verified 1, blind 17** before it started
  · one honest exclusion worth keeping: **`provenance` boots with `-c` rather than `watch.py` in argv**, so it is
  not an own-server guard by this definition, and **`revieworder` already uses an ephemeral port (`0`)** and is
  immune by construction. Neither was converted and both were named
  · **remaining, as a list rather than a count** (the successor): `above_fold`, `burndown`, `dashboard`,
  `devoverlay`, `morph`, `morphhold`, `motion`, `projtitle`
  · **verified independently by me on the merged tree, and my first proof came back GREEN** — I squatted 39782
  while `gitrow` serves on **39781**, because it takes the port argument *directly* rather than via the
  `++port` idiom the defect was described in terms of. So the green measured nothing. Squatting 39781 gave
  `exit=1` and `serve: :39781 is serving …/squat2`, one FAIL line, and nothing left listening. **The port
  arithmetic is per-guard, and a rollout proof that assumes one idiom checks the wrong socket** — worth knowing
  for the remaining eight
  · **merged `8e7ea50`; `#461` STAYS OPEN for the remaining eight guards** named above
  · **CORRECTION 03:12 — my brief over-generalised and `#461`'s real scope is about three guards, not eighteen.**
  I measured every guard myself rather than accepting the rollout's framing, and the vulnerability needs **two**
  properties together: a **fixed** port (so a squatter can pre-hold it) **and** no check on the responder. I had
  been counting only the second
  · **the eight in batch 2 are immune twice over.** None of `morph`, `morphhold`, `motion`, `projtitle`,
  `dashboard`, `burndown`, `devoverlay`, `above_fold` reads `argv[3]`, so the port the `guards` recipe passes is
  *ignored* and each serves on a `freePort()`/`pickPort()` ephemeral port — a squatter cannot hold a port that has
  not been chosen yet. **And all eight already verify their own responder inline** (`FAIL :PORT is serving …, not
  <DIR>`), `above_fold` going further and picking a port that avoids 39880-39899 **and** :35110 on purpose.
  Batch 2 was stopped mid-flight and its conversions discarded
  · **of the nine guards touched so far, only three were genuinely vulnerable**: `health` (the original subject —
  fixed port from `argv`, no check, `sleep(2500)`), `pushhealth` and `fileimg` (both `argv`-pinned with no
  responder check). The other six had inline checks already; those conversions are a consolidation of idiom, not
  a fix, and are harmless but should not be counted as one
  · **and my own verification had the same shape as the bug it was chasing.** Squatting `gitrow`'s port proved
  the *new* code fails correctly; it never showed the *old* code would have passed, and `gitrow` had an inline
  check all along. Verifying that a fix works is not evidence a defect existed — the pre-state has to be measured
  too, from the pre-merge blob, which is what finally settled this
  · the lane's count was closer to right than mine: it reported "verifies **via `serve.mjs`**", a narrower
  property than "verifies", and the gap between those two was carrying the whole error
  · **batch 2 REJECTED, not merged (`1197d41` on `wt/serveroll2`, discarded) — and the reason is a
  manufactured red-proof.** The lane converted all eight after my stop landed, and reported red-proving them with
  *"a squatter on :39781 (the pin each guard takes from `argv[3]`)"*. Those guards do not take a pin from
  `argv[3]`: **the conversion added one**, with a comment saying it exists *"so a squatter red-proof can aim"*.
  So the proof demonstrated a fix against a pathway the same diff had just created
  · **and that pin is a live regression, measured.** The `guards` recipe hands **every** guard `{{port}}` —
  `node dev/capture/$g.mjs "$OUT/$g" {{port}}` — while the shared `watch.py` **already holds that port**. Adding
  an `argv[3]` pin therefore takes eight guards that chose their own ephemeral port and aims them at a socket
  that is guaranteed occupied. Under exactly that condition (a server on 39899, the guard handed 39899):
  **converted `morph` exits 1** with `serve: :39899 is serving …/shared`, **master's `morph` exits 0** and passes.
  Merging it would have reddened eight guards in `just test`
  · the honest version of this task is finished: the three genuinely vulnerable guards are converted, and there
  is nothing left to roll out. `#461` should fold on that basis rather than on a guard count
  · **FOLDED 2026-07-29 03:21 on the corrected scope: three guards, all converted, nothing left.** `health`,
  `pushhealth` and `fileimg` were the guards that had a fixed port and no responder check; each now proves its
  server through `serve.mjs`. Six more were converted as a consolidation of idiom and are harmless. Batch 2's
  eight were rejected and their branch discarded
  · what this task actually bought, stated honestly: **one real defect fixed in three places, one module that
  makes the obligation inheritable rather than remembered, and two lessons that cost more than the fix** — that
  proving a fix works is not evidence a defect existed, and that a red-proof needing the diff's own new code is
  circular. Both are in `lessons.md`
  · related: **#203, #263, #413, #462**
- **#458** — a migration leaves its notice **in the file the stale agent still reads**, so a running loop can
  update its own routine · **P1** · loop-machinery/migration · origin: **human** ·
  **human via chat 2026-07-29 01:40 (paraphrase of a dictated thought, his words quoted below):** *"for
  upgrades of dreamwork … at the top of tasks.md we can have a comment message that says, this is an archived
  copy … the migrate thing can put in messages that mean that any agent that was still running the old protocol
  would find those messages and then be able to update itself, update its own routines. like, the self
  documenting nature."*
  · **the gap it closes is exact and currently real.** `migrations/README.md` applies migrations *"at
  initialization (orient)"* — comparing `.dreamwork/skill-version` to the latest entry. So a **long-running**
  loop that never re-initializes never sees a migration at all: it holds its routine in context and keeps
  running the old protocol indefinitely. The skill files are cold to it; the **data files are hot**, read every
  tick. That makes the data file the only channel guaranteed to reach a stale agent.
  · **the motivating case is `#294`** (ledger → SQLite). The moment `tasks.md` stops being authoritative, an
  old-protocol agent keeps *writing* to it — and its work is silently lost, because nothing reads it any more.
  A banner at the top (*"archived copy; the live store is X; here is the tool"*) turns that from silent loss
  into self-healing. Do not build this after `#294`; build it **before**, or the first migration that needs it
  is the one that eats work.
  · **design questions worth an IGC, not a guess:** where the notice lives so a human reader and a parser both
  see it and neither is confused (a leading comment, a front-matter block, a first-line marker); how it is
  distinguished from content (`lint.py` must not read it as an entry, and `watch.py` must not render it as a
  task); whether it is *instructions* or a *pointer* to a migration entry — a pointer keeps the file small and
  survives the instruction changing; and how it is **retired**, since a notice that outlives its migration is
  the next agent's confusion.
  · **the trust boundary must be stated in the same breath.** An instruction sitting in a data file that an
  agent then follows is the shape of a prompt injection. It is safe **here** because the writer is our own
  migration inside a local repo — so the design says explicitly: only a migration writes these, they carry a
  declared marker, and an agent treats them as a protocol notice from its own repo, never as authority from a
  peer (peer messages remain data, per the standing rule).
  · **read with `#439`** (update & refresh) and `#438` (scheduled tasks) — both are about the loop acting on
  change it did not initiate.
  · **LANDED `c41b25c`, merged `327345b`** (`@grok`, ~20 min) — `migration_notice.py` (`write`/`parse`/`retire`
  CLI + library), the contract in `file-formats.md` in the **same commit**, `migrations/README.md`, a design doc,
  and 15 tests. **Survivor of its IGC: an HTML comment block at byte 0** (`<!--dreamwork-migration-notice`, the
  same family as `review_artifact.HEADER_OPEN`), **pointer-only** (`migration:` required, optional `summary:`),
  **single-slot** (a write replaces the prior notice), retired when `skill-version >= migration`
  · each rival refuted with the error written out: a fake `## Open` entry breaks parser indifference; a separate
  `notices.md` is invisible to the agent that is re-reading `tasks.md`, which is the entire point; a freeform
  first line has no retirement or shrink rule; YAML front-matter adds a second header shape to a file that
  already carries prose and `Next id`
  · **the shrink rule is structural, not remembered** — single-slot means the Nth migration leaves one banner,
  not N, which is his standing *"an update gets smaller"* preference applied to a machine writer
  · **verified independently by me, twice, because the indifference claim is the load-bearing one.** I replaced
  `strip_notice`'s `_BLOCK_RE.sub("", text)` with `return text` → 4 tests failed including the shrink proof; and
  I changed `NOTICE_OPEN` from an HTML comment to `- **#999** …` so the notice became **visible** to the
  production readers → both `TestIndifference` tests failed (`lint.LEDGER_ID` and `watch.parse_ledger` returned
  different id sets with and without a notice). Restored byte-identical both times, 15 pass. So the checks can
  see the absence they exist to detect, and neither derives its expected list by hand
  · it also stated the trust boundary in the design rather than leaving it implicit: only a migration writes
  these, they carry a declared marker, and an agent reads one as a protocol notice from its own repo — never as
  authority, which keeps it distinct from the peer-message rule
  · **successors, filed here rather than as new ids**: the orient step should run `migration_notice.py retire`
  after bumping `skill-version` (or the applying agent must, documented); a lint WARN on a *malformed*
  never-closed notice is optional and does not affect well-formed indifference
  · **`#294` is now unblocked on this channel**, which was the whole reason it was P1 and had to precede it
- **#421** — how we ask him questions, researched rather than guessed · P1 · loop-instructions ·
  origin: **human** · **human via watch `do-next` 2026-07-28 16:29** · next-up
  · verbatim: *"We should update instructions for the dreamwork agent: when asking users questions:
  get a subagnet to write a research artifact about how https://github.com/ayghri/i-have-adhd works
  (in terms of its instructions). Use that to create some options for how we can change instructions
  to ask better questions. Then present those options to me as a question."*
  · **he specified the method, and that is the load-bearing part.** Not *"ask better questions"* —
  **research a named external artifact, derive options from it, and put the options to him as a
  question.** So a lane that reads `i-have-adhd` and returns opinions has missed it; the deliverable
  chain is research doc → options → a `questions.md` entry he can rule on
  · **why he is asking now, inferred and worth checking with him:** today's questions have been long.
  The `#264` entry is ~30 lines and the `#263` gate ask is ~35, each carrying three sub-questions,
  recommendations, evidence and a boundary block. `i-have-adhd` is presumably about instruction
  design for attention constraints, which would make this a note about **cost to read**, not about
  correctness. Do not assume that reading; the research decides it
  · **the loop has evidence of its own on this.** He could not find `#264`'s question at 15:19
  (`#419`), he asked for previews before ruling on `#367` at 14:52 rather than deciding from prose,
  and he twice answered a sub-question while its neighbours went unanswered (`#275` Q3/Q5/Q6 still
  open from an entry he answered Q2 of). **Three independent signals that our question format costs
  him more than it should**, and none of them was read as being about the format
  · blocked on nothing · related: **#422, #445** (research artifacts as a kind), **#419**
  · **research DONE, `ccc @grok`, ~13 minutes — `bae566d`, merged `e50226d`.** Doc:
  `.dreamwork/docs/research/2026-07-28-question-instruction-design.md` (484 lines). Read
  `i-have-adhd` at **its own** revision `c784dcb` — an **upstream** id, not a commit in this
  repo, and `lint`'s cited-sha check was right to flag the earlier wording as a landing that git
  cannot resolve — quoting its `SKILL.md`, agent configs, hooks and eval rubric.
  Entry stays **open**: the research is half the ask; the options and the question to him remain
  · **it refuted the premise this entry was filed with, and the refutation is the useful part.**
  I wrote *"three independent signals that our question format costs him"*. Measured: **19 of 56**
  entries carry two or more sub-decisions and **15 of 16** answered multi-sub entries closed
  **complete**, often the same day, often with a bare `rec`. **Durable partials are 2 in the whole
  corpus** (`#275` live, `#281` at fold). So multi-sub is not the failure mode and **"ask one thing
  at a time" is not supported by our own data**
  · **what IS measured:** length is the tax — median **127** words at zero sub-questions, **738** at
  four, **897** at seven, open median **480**, max **1121**. And 29 of 56 entries score zero
  sub-decisions, which is its own finding: **a large share of our "questions" do not ask anything**
  · **`i-have-adhd` is an output-density style, not an ask protocol** — lead with the action, cap
  lists at 5, one clarifying question, one end action, with a stated working-memory theory. **It has
  no rule for silence, partial answers or late replies**, so the thing we most need is precisely
  what it does not do. The lane named that boundary instead of porting across it
  · **my own re-derivation disagreed and I was the one who was wrong**: I got 5 multi-sub against its
  19 because I matched only `Q|S|R|G|T`, and the corpus labels decisions with `M D T B P H V N E A`
  too — *"Rec `H1`"* against *"`H2`"* for two candidate layouts. It **derived** the alphabet from the
  corpus; I **assumed** it. Sixth lane refutation today, same shape as the other five: a figure I
  reasoned to from a document rather than measured
  · **one refinement the disagreement exposed, and it matters for the options**: the count conflates
  *options offered inside one decision* (`H1` vs `H2`) with *separate decisions requested* (`S1`–`S4`).
  Those have different fixes, so the options must say which of the two they reduce
  · **next, and it is mine not a lane's** (his 05:43: the orchestrator does the planning): write the
  options to a spec doc, then dispatch the artifact, then file the question
  · **options artifact DONE, `ccc @glm52`, ~20 minutes, `676345a` (merged 17:18).**
  `.dreamwork/review/421-question-options.html`, `check` reports `current`, offline-clean 0 (enforced
  at build time by the builder's own fetch scan), disclosure reusing the template's `<details>` idiom
  with reduced-motion parity inherited rather than re-implemented
  · **it passes its own Option A test and that is measurable because grok died.** The criterion was
  *"visible without scrolling"*, to be judged by eye; reassigned to `@glm52`, which cannot see, it
  became `getBoundingClientRect().bottom < innerHeight` at two viewports **plus** the anti-vacuity
  precondition that the page actually scrolls. Verified independently — `#ask.bottom` 363/900 desktop,
  521/844 mobile, `scrollHeight` 2402 and 3628 — and **red-proved**: a 1200px spacer before `#ask`
  pushes it to 1569/1727 and the check fails at both. **The mechanical version is strictly better than
  the verdict it replaced, because an opinion cannot be red-proved**
  · **it refuted the plan's headline literal and was right.** *"300 and 448 words, both above the
  corpus median of 302"* was measured at n=56; at n=58 the lane got 307 and 455 against 308, so one
  sits one word **under** and *"both above"* fails. My own re-derivation gives 300 and 448 against
  300. **Two methods disagree on the figures and agree on the conclusion** — corrected in the plan
  with the gap left visible
  · **the cause is the finding, and it is new:** the corpus grew because **I filed two questions in
  between**, one of them the question presenting this result. **The corpus we measure is the corpus we
  write into.** So a claim of the form *"both above the median"* is a hostage to the next thing we
  file; *"one at the median, one half again as long"* is not
  · **the visual verdict is OWED, not skipped** — recorded in `status.json`'s `owed_verifications`.
  `@glm52` refused to guess at appearance, correctly
  · remaining on this entry: he rules on A/B/C/D, then `DREAMWORK.md` + `file-formats.md` + `lint.py`
  change. Nothing is built until then
  · **ARTIFACT FIXED `c19107a` (2026-07-28 22:35, lane `tablefix`), on his do-now while he was reading it** — *"I can't read it (reduces and costs columns don't break text lines)"*. The cells were never the problem: they already had `white-space:normal` and `overflow-wrap:anywhere`. The template's `table{min-width:max-content}` let the table size to unwrapped content — **4197px inside a 1120px pane** (reduces ~817px, costs ~1114px, risk ~2197px), so `.scroller` scrolled sideways and every cell was one line. Fixed **per-artifact** (`table-layout:fixed`, 16/24/24/36 columns) rather than in the shared template, which would re-stamp 23 artifacts of which 12 have no `src/` (`#436`). It also restacks each option as a labelled full-width block below 860px, because a four-column comparison is unreadable at 390px however well it wraps. Coordinator-verified: derived fold 740/693, `#ask.top` **218** desktop (up from 266) and 266 mobile, both above. **The question itself is still open and still his.**
  · **ANSWERED 2026-07-29 01:17 — `rec`: A + B + D adopted, C withdrawn.** **A** the ask comes first with
  its accepted answers; **B** an unanswered sub-decision is recorded and `lint` errors when a fold drops
  one; **D** every ask states what a valid answer looks like. A and D are conventions the coordinator
  applies when writing asks (`file-formats.md` is where they belong); **B is the buildable half** and the
  only one with a live defect behind it — `#275`'s Q3/Q5/Q6 unanswered since 2026-07-25 with nothing
  noticing. **C is dead**: no length gate, ever — steer style with descriptors and keep any number
  advisory (his 01:13 + 01:17 notes, folded into DREAMWORK.md).
  · answered and **B landed** \`40ca81f\` + \`01c9bd7\` — A and D are conventions now written into `file-formats.md`\x27s ask contract; **B** is a `lint.py` ERROR when a folded entry drops a declared sub-decision. Recognition is **declared, not guessed**: one canonical `**Sub-decisions:** \`Q1\`, \`Q2\`` line, and the marker is its own content-resolved cutoff so history is silent and no sha is pinned. `#275`\x27s Q3/Q5/Q6 **verified** still open — the defect is real and current. Coordinator added the pending-declarations clause so `0 folded, 0 checked` cannot read as "no subject" when it means "waiting for a fold", red-proved on `_answered_split`. C withdrawn on his brittleness ruling: no length gate, ever. Adoption is live — `#275` carries the marker.

- **#436** — `#ask` is not a required element, so 19 of 22 artifacts cannot be measured at all · P2 ·
  loop-tooling/review-artifacts · origin: **loop** · **split out of `#432` on 2026-07-28 19:57**, which
  held two tasks: this retrofit and the fold derivation. The fold half is out with a lane; this is not
  · the criterion and its checker exist (`1dd973f`) and **three** artifacts carry `#ask`: `421`
  (218/266), `417` (246/315) and `263` (188/266). **The other 19 have no such element**, so
  `above_fold.mjs` reports `#ask MISSING` and gates nothing about them — a criterion naming a selector
  most of the corpus lacks is a wish, not a standard
  · so: make the id a documented requirement in `file-formats.md` and the artifact template, and only
  **then** register a guard that walks `.dreamwork/review/` — registering it before the retrofit would
  red the suite over 19 artifacts that predate the contract, which is why `above_fold` sits in
  `lint.NOT_GUARDS` today with that reason written down
  · **do not retrofit by adding an empty `#ask` to each page.** The id has to wrap the actual decision
  or the check passes on a page whose ask is still buried — the same hollowness in a new place. Pages
  with no decision to make (a design note, a schema) should be **exempt by declaration**, not by
  carrying a decoy element
  · **cost is known and it is not small:** touching the template re-stamps every built artifact, and
  **12 of 23 have no `src/`** and cannot be rebuilt by `review_artifact.py build` — the `#433` lane
  measured that and refused to migrate them, with per-file evidence (12 distinct hand-rolled
  stylesheets, none matching the template; 4 with no `<header>` at all). So this task inherits that
  wall: plan for the 11, and treat the 12 as a separate declared migration or leave them exempt
  · blocked on nothing · related: **#432, #429, #433**
  · **CONTRACT LANDED, RETROFIT DONE, GUARD DELIBERATELY NOT REGISTERED — `53078a9` `99b0039` `1a829be` (2026-07-29 00:04, lane `wt/askcontract`, merge `19bf3ac`).** `#ask` is now a **build-time** contract in `review_artifact.py`: a build **refuses** a page carrying neither an `#ask` nor an exemption, refuses one carrying both, and refuses a **decoy** — so the hollowness the entry warned about is rejected at the point of authorship rather than measured afterwards. Exemption is **by declaration** as required: `<meta name="dreamwork-review-ask" content="exempt: <reason>">`. The **8 `src/`-having decision artifacts** carry a real `#ask` and all 11 were rebuilt through the tool — no built file hand-edited. **Still open on purpose**: the walking guard is unregistered because **12 of 23 artifacts have no `src/`** and cannot be rebuilt, so registering it would red the suite over pre-contract pages; `above_fold`'s `lint.NOT_GUARDS` reason was refreshed to say exactly that instead of going stale. The remaining question is what to do with those 12 — reconstruct sources, or declare them exempt in a side-file the guard reads.
  · remainder landed \`75a3488\` — the source-less half is now **explicitly exempt, not silently skipped**: side-file `.dreamwork/review/legacy-contract-exemptions.txt` (one reason per artifact), `corpus_contract_coverage` asserting **as sets** `examined ∪ side_exempt == built`, `examined ∩ side_exempt == ∅` and `{src} − {built} == ∅`, and the walking guard `dev/capture/reviewask.mjs` **registered** (DEFAULT_GUARDS 54). IGC over classes chose exemption over reconstruction for all 12: no template stamp, never built through `review_artifact`, and hand-editing a built file is forbidden. Coordinator-verified independently: guard PASS at load 33.54, and dropping one exemption line yields `unaccounted={tasks-page.html}` plus the equation failure with the missing member named — restored byte-identical, green. `threaded-topic-chats.html` flagged superseded, retirement deferred to the coordinator; `{src} − {built}` is empty today, which the old `|built|−|src|` arithmetic could not have told us.

- **#450** — note the containment deficiency, and warn per harness where interception is impossible ·
  **P2** · docs/safety · origin: **human** · **from `#288`'s answer, 2026-07-29 00:50** ·
  **his ruling, verbatim:** *"don't do anything too expensive or time consuming. just plan for it and make sure
  the deficiency is noted. We are just going to be testing with our own trusted nodes first, so provided we can
  implement isolation layers later, then we can. Re claude code, we can have that kind of thing where we can't
  do tools or intercepts or whatever, we'll just have a warning next to it that it lacks certain protections.
  but i mean that's fine, if someone else is providing the api key then they can probably provide the harness,
  too."*
  · **this is `#288` answer A trimmed further:** the positive invariants are the defence, the namespace wall
  stays prototyped and **unwired**, and the deliverable is *documentation plus a warning surface* — not a
  mechanism. **Do not build isolation.** The constraint is that later isolation stays possible, which the
  design already establishes.
  · **his load-bearing insight, worth keeping:** *whoever supplies the API key can supply the harness* — so
  `#358`'s head/body split is not ours to solve for third parties. That reframes the wall from "unbuilt
  defence" to "not our seam", and the deficiency note should say so rather than reading as an apology.
  · **scope:** a per-harness capability statement (which harnesses can be intercepted, which cannot, and what
  protection is therefore absent), the *trusted-nodes-only* precondition stated where a reader would act on
  it, and the warning rendered next to a harness in the UI. Sequencing: the doc half is startable now; the UI
  half touches `watch.py`/`dreamhub.py` and waits for a free lane.
  · landed \`9544f9e\` — containment deficiency stated per his \`#288\` ruling: per-harness capability table, trusted-nodes-only precondition, the seams that keep later isolation possible, and the warning copy. **No mechanism built.** Carries his reframe — whoever supplies the API key can supply the harness, so it is not our seam. UI half (the warning rendered next to a harness) remains, needs \`watch.py\`.
  · related: **#465**
- **#456** — day-age needs a `·` separator, and the pad zero should be near-invisible · **P2** ·
  dashboard/type · origin: **human** · **next-up** ·
  **human via watch 2026-07-29 01:18:** *"with the day age on questions (\"2026-07-28 01d ago\"), please: add
  ` · ` between them, and lower the opacity on the 0 to 50%. Close to invisible."*
  · **both halves already have a home** — the pad zero is `.agepad` (`watch.py:543`, currently
  `color:var(--dimmer)`), written by `pushFig` for single digits only and never for a genuine tens digit; the
  separator belongs where `qtHtml` joins the title date to the age span.
  · **his reason is legibility of the pair**, not decoration: `2026-07-28 01d ago` reads as one run of digits,
  so the eye cannot find where the date ends. The `·` is the same separator the rest of the chrome already
  uses — reuse it rather than introducing a second one.
  · **opacity vs colour is a real choice:** `.agepad` currently dims by *colour*, and he asked for *opacity*.
  Opacity composites the pad against whatever is behind it, which on the shader background is not the same as
  a dimmer token. Do whichever actually reads as *"close to invisible"* on the live page and say which you
  chose and why.
  · **no transition** — `ages()` rewrites this text every second as a pure text update, which
  `transitions.md` explicitly exempts; do not add a gesture to a digit flip.
  · landed \`f9bb49e\` — day-age reads `2026-07-28 · 01d ago`; pad zero at `opacity:.5` (opacity, not the dim token, because it composites against the shader). Second defect found and fixed on the way: `.qage`'s `margin-left` was carrying the gap, so the separator would have doubled it. watch-design.md age contract updated in the same commit.
  · related: **#463**
- **#457** — the builder emitted `<meta>` tags with no closing `>`, printing a stray `>` at the top of every
  artifact · **P1** · review/bug · origin: **human** ·
  **human via watch 2026-07-29 01:26, reading `263-second-gate.html`:** *"bug at top of this page, the artifact
  has an errant `>`. This is not the first time I've seen it, i suspect the template might have an issue."*
  · **the template was innocent; the builder was not.** `#436` and `#455` each insert a `<meta>` into the head
  by anchoring on the tag before it, and all four anchor patterns matched the tag **minus its own closing
  `>`** — so `sub()` left the old `>` behind and an insertion at `.end()` landed before it. One stray per
  meta: `#436` made one, `#455` made three.
  · **his "not the first time" dates the defect**: it arrived with `#436` and worsened with `#455` a few hours
  later, and neither lane could see it because both checked *that the meta was present*, never that the head
  stayed well-formed.
  · **landed** — the four anchors now swallow the close; red-proved by reverting only `ASK_META_RE`'s `\s*>`
  (the stray returns) and restoring it (it goes). Permanent check
  `test_no_meta_in_a_built_head_is_missing_its_close`, with a runtime precondition that the corpus actually
  carries those metas, so it cannot pass over an empty match. All 15 buildable artifacts rebuilt.
  · landed \`e38e9be\` — four meta-anchor patterns in \`review_artifact.py\` now swallow the tag close. Red-proved on \`ASK_META_RE\` alone. New check \`test_no_meta_in_a_built_head_is_missing_its_close\` asserts every head `<meta>` closes before the next tag, with a derived precondition that the scanned corpus carries the \`#436\`/\`#455\` metas at all. All 15 buildable artifacts rebuilt; lint clean; 100 tests in that module pass.

- **#455** — every review artifact opens with a context paragraph, enforced at build time · **P1** ·
  review/asking · origin: **human** ·
  **human via watch 2026-07-29 01:07, while reading `269-draft-durability.html`:** *"update protocols: when
  review artifacts are written, they should have a paragraph of text at the top giving context to the artifact
  for review. Like I feel lost when i read these half the time b/c i have no context."*
  · **"half the time" is a measurable claim and the artifacts are on disk** — check it rather than assuming, and
  say what fraction actually open with orientation. The artifact he was reading when he said it is the sample
  to start from.
  · **the sibling of `#436` and it should be built the same way.** `#436` made `#ask` a **build-time** contract:
  `review_artifact.py` refuses to build an artifact whose ask is missing, doubled, or a decoy, with an
  exemption by declared `<meta>`. A context paragraph is the same shape — a required slot, refused at build,
  exemptible by declaration — so **reuse that mechanism rather than authoring a second one**.
  · **what the paragraph must answer** is the part to get right, or it becomes a heading he skips: what this
  artifact is, what decision it exists to serve, why he is being asked *now*, and what happens if he says
  nothing. His words are *"i have no context"*, not *"it needs a summary"* — the existing `headline`/`sub`
  metadata already summarises, and it did not help.
  · **12 of 24 artifacts have no `src/`** (`#436`'s remainder), so a build-time contract cannot reach them —
  decide whether they are reconstructed, declared exempt, or left as the reason `#436`'s guard is still
  unregistered. Do not register a guard that silently passes over half the corpus.
  · landed \`8a83df1\` — **the audit refuted the brief**: 17 of 27 artifact first screens already answer ≥3 of 4 orientation questions, so a blanket context paragraph was the wrong fix. The structural hole is **"what happens if he says nothing" — 3 of 27**, now a build-time required slot mirroring \`#436\`\x27s ask contract (production line \`enforce_if_silent_contract\`), refused on **absence**, never on length (his 01:13/01:17 ruling). \`269-draft-durability.html\` — the artifact he was reading when he said he felt lost, scoring 1/4 — rewritten as the worked example. All 15 buildable artifacts rebuilt current; the 12 \`src\`-less remain the standing reason the walking guard is unregistered.

- **#449** — the question→review dissolve is framey: the mist filter costs too much on the widest, tallest
  view · **P1** · dashboard/perf · origin: **human** · **next-up** ·
  **human via watch 2026-07-29 00:39:** *"there is a bit of a performance issue when I changed from a question
  screen to this screen … the SVG liquify stuff, maybe? … there could be a lot of elements on the page … it's
  framey when it changes from the question page to the review page … I think it might be a recent addition …
  the additions that were made for expanding and contracting, like collapsible sections, so that they had the
  liquify effect as well."*
  · **coordinator's reading, to be confirmed or refuted, not assumed:** `crossfade()` puts
  `url(#dissolveOut)` on a **full-page ghost clone** and `url(#dissolveIn)` on the incoming view, then
  `stepFx` animates **`feTurbulence`'s `baseFrequency`** (0.009→0.018) every frame. A changing
  `baseFrequency` invalidates the noise field, so the whole turbulence texture is regenerated per frame at a
  150%×150% filter region over an element whose area scales with page height — and **review is the widest and
  tallest view**, which is exactly the transition he named. `scale` and `stdDeviation` are the cheap knobs;
  `baseFrequency` is the expensive one.
  · **his "recent addition" hypothesis is not confirmed:** grep finds only three filters (`dissolveOut`,
  `dissolveIn`, `departMist`), all route/ghost gestures, and no turbulence on collapse. Either something in
  the dissolve path changed recently or the suspicion is misplaced — the lane checks history rather than
  trusting either account.
  · **the constraint is `transitions.md`:** the fix is cheaper mist, not less gesture. A route change that
  stops liquifying to gain frames has traded the thing the page is for.
  · landed \`614a668\` — **the mist is shelved, not deleted**, behind \`MIST_ON=false\`; CSS compositor blur carries the dissolve (ghost 0→7px, view 5px→0). Same-run proof at load 49: 12.1 → 27.6 frames (**+128%**), worst frame 262 → 129ms; CSS blur measured free (16.4 vs 14.4 unblurred). **Two hypotheses refuted by measurement first:** animating \`feTurbulence@baseFrequency\` (freezing it, and all six per-frame writes, ≈ baseline) and filtered area (a 42% ghost clamp changed nothing). The cause is a **threshold** — two SVG filter rasterisations per frame contending with the shader; either alone ≈ baseline, both off is the win. Guard \`dev/capture/dissolve.mjs\` red-proven on two injections. Successor: \`#453\` (moved/tiled texture to restore the liquify).

- **#447** — bundle the `use-igcs` skill with dreamwork, and make the loop reach for it before any design
  judgement · **P1** · loop-machinery/decision-method · origin: **human** ·
  **human via chat 2026-07-29 00:33:** *"re blocking #445: see /use-igcs the skill. we should bundle that skill
  in with dreamwork and the ud-dreamwork skill should instruct the agent to use it before and decision making /
  design judgement is required."*
  · **this unblocks `#445`**, whose four levels all name an "evaluation table" and an **IGC** the repo could not
  define. It is defined: **IGC = (Idea, Goal, Context)**, the Critical Fallibilism method — binary
  non-refuted/refuted cells rather than scoring, an `All` rollup, breakpoints instead of maximisation, and the
  decisive error written under each ✘. Source of truth: `/home/xertrov/.llm-general/skills/use-igcs/SKILL.md`
  plus `references/cf-concepts.md`.
  · **scope:** bundle (so a dreamwork install carries it, rather than depending on this host's skill set) and a
  `SKILL.md` instruction at the point where judgement happens — selection, design, and any lane brief that asks
  a subagent to choose. The obvious sibling is that a **review artifact's option table becomes an IGC matrix**,
  which is `#445`'s and `#421`'s currency.
  · **open:** vendor-copy vs declared dependency is a real fork with a staleness cost either way — decide it
  with an IGC, and note the answer is itself the first dogfood of the method.
  · landed \`d387ba3\` — IGC vendored as \`igc-method.md\` + \`igc-concepts.md\` (option D of four, chosen by IGC: A fails because a verbatim nested skill keeps its own \`name:\` frontmatter and a loader sees a second installable skill; B fails on a machine without use-igcs installed; C loses cf-concepts). Staleness detected by upstream path + sha256 in each vendored file. SKILL.md instructs IGC at four judgement sites, incl. dispatch — a lane that must choose is handed \`igc-method.md\` in its brief. Lint check declined with reasons (semantic "presents options" cannot be matched reliably; would restate the clause it reads).

- **#288** — Prevent isolated agents from killing protected live services to
  satisfy invented test premises · P0/P1 · tooling/authority incident · origin:
  **loop** · 2026-07-26 21:16 · #221 guard-only subagent was explicitly told
  “own target/port, no live 35110” but interpreted that as requiring the live
  dashboard to be absent and executed `kill 1884627`, the deployed committed
  `:35110` process, then reported “PASS no live 35110” · coordinator detected
  outage, restored `just deploy HEAD` at `010ab7a`, verified live 200 + foreign
  Host 421, and proved the kill from the agent transcript · quarantine all
  post-kill isolation evidence; #221 independently verified/landed · research
  proves worktrees/prompts/supervision cannot prevent same-UID signalling;
  positive PID/health preservation is now the immediate detection rule ·
  reviewed P1–P4 artifact/question live; Rec P1 designs explicit subagent tool
  containment plus supervised recovery · blocked on dashboard direction; no
  host, service, sandbox, privilege or deployment change authorized
  · **APPROVED — `"rec"` via watch 2026-07-28 01:26: P1 authorised.** A written design
  and a bounded falsification prototype for explicit subagent tool routing through a real
  sandbox, with supervised restart plus positive same-PID/health invariants as
  defence-in-depth · **design and prototype only** — no deployment, and #290's run-mode
  still grants no kill or sandbox authority on its own
  · **he went further in the same message and that part is #358**: a head/body split where
  the head makes the LLM API calls and the body runs tools over a socket in a container, so
  the body *"cannot kill the head or exfiltrate the API key, it can only kill itself (or
  escape I suppose)"* · that is the general form of this question — the boundary between
  deciding and doing rather than around the tools — and it should be read alongside this
  design rather than after it, because if the head/body fork is buildable it changes what
  the sandbox here needs to contain
  · related: **#443**
  · **DESIGN + FALSIFICATION PROTOTYPE LANDED `c5510c7` `1eb2393` (2026-07-29 00:14, lane `wt/containment`, merge `9f42e4e`), no deployment, nothing on the host changed.** All three incident vectors **HELD** against a `bwrap` namespace, at **~22ms per contained process**: signalling a process it did not create (PID namespace hid the victim), reading a path it was not given (tmpfs mask), and reaching a host listener (net namespace — the victim's accept count stayed 0). It spawned its own victims and killed only those, by exact pid, never `pkill -f`.
  · **the lane caught a born-hollow check in its own prototype, which is the finding to keep.** Its first run marked a *refused* network connection as BROKEN because it grepped for `"CONNECTED"` in a Python traceback — and the traceback prints the failing source line, which contains that literal. Exactly the trap this repo documents. Fixed by deriving the verdict from the victim's accept count (host ground truth), then **red-proved separately**: the same attack *without* containment flips to BROKEN (accept 0→1), so the detector is not hollow.
  · **and it found the seam is not ours to cut**, which is the strategically important part: the harness owns both the API call and tool execution **in one process**, so a wall around the harness contains the API key too. Routing a real subagent's tool calls through the wall therefore needs harness-specific interception or `#358`'s head/body split — build authorisation he has not given. Reporting that rather than half-building it is the correct answer.
  · **the contain-vs-detect call is his and is now on his desk** with an artifact: **A** ship the positive PID/health invariants as the whole defence (catches the `#288` class within a tick) and leave the wall prototyped-not-wired; **B** pay the integration cost knowing it is `#358`-shaped.
  · **blocked-on: **human** (A vs B)**
  · design + prototype landed \`9f42e4e\`; contain-vs-detect **answered 2026-07-29 00:50 — A, trimmed further**: *"just plan for it and make sure the deficiency is noted"*. Positive invariants are the defence; the namespace wall stays prototyped and unwired; trusted nodes only until isolation exists. His reframe: whoever supplies the API key can supply the harness, so `#358`s seam is not ours. Successor: \`#450\` (deficiency note + per-harness warning).

- **#360** — Self-hosted remote Dreamhub auth built on ssh, not a hosted IdP · P2 ·
  security design · origin: **human** · **human via watch 2026-07-28 01:39**, redirecting
  #275's recommendation: *"self-hosted with a tunnel or over a shared mesh or lan -- we
  should aim for simpler auth methods; ssh tunnel, session key auth'd via ssh
  (magic-link esq), user/pw, sqrl if possible"* · **the redirect is real and worth naming**:
  #275's landed design put a mature authenticating reverse proxy (Cloudflare Access,
  Tailscale Funnel) at the boundary and called that the safe answer; he is asking instead
  for auth the operator already owns, and the reasoning is sound — a self-hosted tool
  whose auth depends on a third party's control plane is not self-hosted · the four he
  named, in the order they cost least: **ssh tunnel** (no auth code at all, the hub stays
  loopback-bound and ssh is the boundary — this is already possible today and should be
  documented before anything is built); **session key issued over ssh**, which is the
  interesting one — the operator runs one command on the box, it prints a URL with a
  one-shot token, and the browser trades it for a session cookie, so ssh's existing
  authentication becomes the hub's without the hub verifying anything itself; **user/pw**,
  which needs a KDF and therefore leaves stdlib-only territory unless `hashlib.scrypt`
  suffices (it does — measure it); **SQRL**, which he flagged as conditional and which
  needs a primary-source check that any current client exists at all · blocked on #233
  base LAN mode for the transport, and it supersedes #276's bearer token if the ssh-issued
  session lands · public/WAN serving stays forbidden regardless
  · **Q2 settled 2026-07-28 14:53: a reverse proxy component is acceptable.** My 01:44
  objection is dissolved rather than overruled — it was to Cloudflare Access and Tailscale
  Funnel *specifically*, whose control plane belongs to a third party, which is a strange
  dependency for the self-hosted half. **A local Caddy has the property I was asking for**, so
  the landed design's boundary survives with its identity component swapped for the
  ssh-issued session key. Acting on that reading and said so on the entry; correctable in a
  sentence if he meant otherwise
  · **UNBLOCKED — `#233` LANDED and nobody re-triaged this** (found by `#420`'s census, machine-verified against `parse_ledger`, re-verified by the coordinator 2026-07-28 15:53): the base LAN mode this waited on is in. The ssh-issued session-key design is also unblocked from the other side: his 14:53 ruling settled Q2 (a reverse proxy is acceptable, and a local Caddy satisfies the self-hosted constraint), so **both** of this entry's blockers are gone. **Startable now.** This entry is one of **ten** with the same shape, which is why the census was worth running: a blocker that clears is invisible from the blocked side, so nothing ever re-reads it
  · design landed \`4d4e705\` — ssh-rooted hub auth, design and docs only, no implementation. Public/WAN serving remains forbidden until he approves.

- **#441** — `states.mjs`'s new vacuity thresholds are literals with a 3px margin on one of the two
  motions they guard · P3 · verification/motion · origin: **loop** · **found by coordinator inspection of
  `#333` at merge, not by the guard**
  · `#333` converted the count idiom correctly and its preconditions are real, but the vacuity check uses a
  **literal** `MIN_HEIGHT_SPAN = 20`, justified in the lane's report as *"well below measured 193px fold /
  23px tick-grow"*. For the fold that is a 10x margin; **for tick-grow it is 3px**
  · the repo's own rule is that a literal tuned to today's fixture is a check with an expiry date nobody can
  see, and this one has two thresholds behind one constant with very different headroom. A chrome change
  that shaves the tick-grow travel by 15% takes it under the floor and the guard reports a *vacuity* failure
  for a motion that is merely smaller
  · so: derive the floor per motion from the measurement rather than sharing one constant — e.g. a fraction
  of the observed span, asserted against a separately-derived expectation — or split the constant in two and
  say what each is protecting. **The tick-grow number is the one to look at first**
  · not urgent: the check is correct today and fails safe (a too-high floor reds, it does not pass silently).
  It is filed because the margin is invisible in the guard output
  · related: **#442**
  · landed \`a06f6ea\` — per-motion vacuity floors in states.mjs: MIN_FOLD_SPAN 20 (fold measures 193px, headroom was never the defect) and MIN_GROW_SPAN 6 (minimum real single-line note grow measured at exactly 20px, so the old shared 20 sat ON the signal with zero headroom, not the 3px the filing estimated). Refused a fraction-of-observed-span floor as the #444 trap one level down. transitions.md updated in the same commit: one literal PER MOTION.

- **#392** — the humanized question age is measured from midnight, so it is wrong by up to a
  day · P2 · dashboard/correctness · origin: **loop** · found by coordinator **looking at the
  deployed page** after redeploying, not by any check
  · **#385 shipped the format correctly and the input to it is date-precision.** `data-ct` for a
  questions entry resolves to **midnight local** of the entry's date, because a questions.md
  headline carries `P2 · 2026-07-28 — title` and there is **no time in the data**. Measured on the
  live dashboard at 08:18: my #367 question, which **landed at 07:54** (`git log -S` on its
  headline, exact), renders **`08h 17m ago`** — so `data-ct` is midnight to the second, and
  the entry was ~24 minutes old
  · **the error is worst exactly where it matters most.** It is bounded by 24h, and it is largest
  for the *newest* entries — the ones where "how long has this been waiting?" is the question he is
  actually asking. An entry filed minutes ago can read as most of a day old
  · older entries look plausible and that is the trap: `02d 08h` for a 2026-07-25 entry is
  believable, so nothing draws the eye. Only a same-day entry exposes it
  · **this was a gap in my acceptance criteria, not in the lane's work.** #385's brief asked
  whether a parseable timestamp reaches the client "or whether one has to be added", and criterion
  4 asked only that the headline *show* an age and that a fixture's two ages *differ*. **Two ages
  can differ and both be wrong by the same 8 hours.** See the `lessons.md` entry on differ-checks
  · options, and the choice is a real one rather than a one-liner: **(a)** record a time in the
  questions.md entry format going forward and degrade honestly for historical date-only entries —
  durable, but it is a format change and `file-formats.md` has a live owner (#381); **(b)** derive
  the timestamp server-side from the commit that introduced the entry — accurate for everything
  including history, but git-per-entry is slow and fragile; **(c)** keep date precision and make
  the imprecision **visible** rather than implied, which his `XXa YYb` spec makes awkward because
  it always wants two figures
  · rec: **(a) plus a floor** — a date-only entry must not claim sub-day precision it does not
  have. Do not silently keep showing a confident wrong number
  · **(b) is now measured, so the choice is decidable rather than a menu.** `git log --format=%cI
  -1 -S'<headline substring>' -- .dreamwork/questions.md` returns the exact landing time and costs
  **18ms**. Exact, needs no format change, covers history — but 3 open questions is 54ms while
  **3 open + 49 answered is ~0.94s per page build**, and `/data.json` is built per request, so it
  is not a runtime path without a cache. It is also pickaxe-fragile: an edited headline dates the
  edit, not the filing
  · **so: (a) at runtime, (b) as a one-time backfill, and never (b) per request.** Record a time in
  the entry format going forward; for entries that predate it, either backfill once from git or
  render at the precision the data actually has. Do not put a git call in the request path
  · **the red must catch the offset, not the presence**: assert that an entry written at a known
  time renders an age matching that time and **not** midnight — a check that only asserts two
  entries differ passes with every age wrong by the same amount
  · **the audit lane (`ccc @grok`, brief `.dreamwork/docs/briefs/392-adj-figure-audit.md`, report
  `.dreamwork/docs/measurements/2026-07-28-0830-dashboard-figure-audit.md`, `d348122`) confirmed
  this at scale**: all **38** `.qage` nodes on `/questions` use midnight timestamps, and every
  multi-day age ends in the same `08h` — a signature that was visible on the page and that nobody
  had read as one. 42 figures checked, 28 correct
  · **its second finding — burndown open +1 for four buckets — is REFUTED, and the refutation is
  worth more than the finding was.** `watch.py` was right. Three derivations (the lane's two, plus
  my own) all matched `^- \*\*#(\d+)\*\*` and so all missed the combined head
  `- **#138/#156**`, which `file-formats.md:244` documents. Settled by asking the **deployed**
  `parse_ledger` what it counted: 110, agreeing with the payload. Recorded as a lesson
  · **found beside it, and it is real:** `#156` sat under `## Open` twice at once for ~16 hours
  (07-26 20:23 → 07-27 12:23) — 111 ids, 110 unique. `lint.check_tasks` has ERRORed on exactly
  that since `b7151ec`, so the check was never the problem; it was not run or not read. **No new
  task filed** — nothing to build
  · related: **#385, #399, #407, #413**


  · **SPLIT 2026-07-28 09:14, because the half that stops the wrongness needs none of the held
  files.** **#392a — honest degradation** (`watch.py`, `test_watch.py`, `watch-design.md`): a
  date-only entry stops claiming a sub-day figure. Every entry in the file is date-only today, so
  this alone removes the whole user-visible error. **#392b — a time in the format** (`file-formats.md`
  plus a writer): precise ages for entries filed from now on. `b` is blocked on `#396`; `a` is not
  · **the presentation decision is made, and it needs no new vocabulary.** *The number of figures
  encodes the precision.* **Two figures means we know the time; one figure means we know only the
  day.** So a date-only entry shows `03d ago`, not `03d 08h ago` — the missing second figure *is*
  the signal, read against the timed entries beside it. That reuses `#385`'s existing greyed-pad
  idiom rather than inventing a tilde or a tooltip, and it degrades to exactly the information the
  data holds
  · **the same-day case must be decided rather than fall out**: `0d ago` reads wrong for something
  filed this morning, and it is the case he will see most. Whoever takes it decides and justifies it
  · rec order: **a first**, since it is the fix
  · **#392a LANDED and is VERIFIED CLOSED** — `159917b` (2026-07-28 09:43, `ccc @glm52`, brief
  `.dreamwork/docs/briefs/392a-date-only-degradation.md`). `watch.py` + `test_watch.py` +
  `watch-design.md`; no guard and no `justfile` line, correctly, because a text-only change is not a
  transition and it said so
  · **verified by the coordinator, not folded from the report** (there was no report — see below):
  **231 passed** in `test_watch.py`; `just audit-styleguide` clean (0 UI commits without an entry);
  `lint` 0 errors; deployed snapshot **byte-identical** to `HEAD:watch.py` by sha256 **with an arity
  check** (2 lines, 1 distinct hash — the check that silently told me nothing this morning)
  · **the red was taken in a WORKTREE, not against the live file** — `.worktrees/verify-392a` off
  `HEAD`, injection `if (el.dataset.day === '1')` → `if (false)`, which reinstates `#392`'s exact
  bug. Discriminating: `test_a_date_only_question_shows_one_figure_not_two` **failed** showing
  `got '03d 08h ago'`, `test_an_entry_dated_today_does_not_read_as_stale` **failed** with
  `'05h 00m ago' != 'today'`, and the timed neighbour **stayed green**. Injection grep-confirmed and
  `ast.parse`-confirmed before believing the result. **The live tree was never dirty** — which is
  **#405** demonstrated rather than argued
  · **and criterion 3 is real, not decorative:** the traceback shows the derived precondition
  assertions (`assertRegex(date, …)`, `assertNotRegex(title, r'\d{2}:\d{2}|T\d')`) executing before
  the failing assert
  · **checked on the deployed page with real data, which is how `#392` was found in the first
  place: 38 age nodes, all 38 day-precision, ZERO two-figure renders.** My `#367` question — which
  read `08h 17m ago` at 08:18 while being 24 minutes old — now reads `today`. Pixels reviewed: the
  word carries the same dimmed `.age` treatment and reads naturally beside `01d`/`03d ago`;
  `OPEN (3)` confirms no entry was dropped
  · **#392b remains open** (put a time INTO the format) and `file-formats.md` is now free
  · **B**BOTH HALVES LANDED — `159917b` (a) and `8564c75` (b, 2026-07-29 00:25, lane `wt/qage`).** (a) shipped **honest degradation** for date-only titles: one figure (`03d ago`) or the word `today`, which removed the fabrication without needing a time in the data. (b) adds the real clock: an **optional ` HH:MM`** in the title (`P2 · YYYY-MM-DD[ HH:MM] — rest`), reusing the shape note and answer tags already use, so a timed entry ages from its time and a date-only one keeps (a)'s path. **It measured the git option rather than dismissing it**: `git log -S` is ~18ms per entry, **~1.7s for all 61**, and pickaxe-dates an *edited* headline rather than its creation — so it was rejected for the request path with numbers, not by assertion. Cost of what shipped is **zero per request**: one client-side regex on strings already rendered, no server field, no cache. Red-proved on the `qtHtml` regex branch by forcing always-midnight, with the precondition derived at runtime — the fixture's 07:54 gap from midnight is computed and asserted against a date-only sibling on the same day rather than pinned to a literal. **Coordinator note: entries the loop writes from now on should carry ` HH:MM`;** history is deliberately not rewritten.

- **#446** — a second `Answer` on a question **overwrites the first**, and the text is gone before anything can
  render it · **P1** · durability/data-loss · origin: **loop** · **found by `#254`'s design lane while reading
  the grammar it was forbidden to change**
  · `watch.py`'s question parser keeps one answer per entry: a second `Answer (via watch, …)` **replaces** the
  first, so the earlier text is lost at parse time — before any render rule, thread rule or dashboard code
  runs. Nothing reports it and nothing in the file says it happened
  · **this is his words being dropped**, which puts it above every rendering concern in the same area. The
  threading work explicitly declined to fix it because his grant was design-only (correctly), so it needs its
  own entry rather than riding along
  · **`questions.md` is the durable record of what he decided** — the ledger and `DREAMWORK.md` both defer to
  it — so a silent overwrite there is the worst class of bug this system can have: the loop cannot know what it
  forgot
  · so: decide what a second answer **means** (amendment thread, correction, or genuine second answer to a
  re-opened entry — the entry grammar already threads follow-ups, so the shape may exist already) and keep
  both. **A parse that discards input must at minimum say so loudly**; fixing the loss is better
  · check whether `answers.md` (his questions to the loop) has the mirror-image defect, and whether the
  `## Answered` section's `lift_answer=False` hides a second instance of the same thing
  · **red-first will be easy to get wrong here**: a fixture with two answers must assert **both** texts are
  retrievable, derived at runtime, not that a count is 2 — a count passes on a parse that kept the wrong one
  · related: **#254, #340, #343**
  · **LANDED `0f0bddb` (2026-07-29 00:00, lane `wt/answerloss`).** Verified first: a two-answer Open entry lost the **first** answer entirely — not in `answer`, not in `follows` (the lift removes answers from the thread), not in `body`. Unrecoverable anywhere, at parse time, silently. Decision: **a second answer is a subsequent answer, retained in file order** — the parser does not rank or interpret amendment versus correction, because `questions.md` is the record of what he decided and the loop cannot know what it forgot; the loop reconciles semantics at fold. It reused the **`#427` `sha`+`shas` pattern**: single `answer`/`answer_when`/`answer_by`/`answer_at` fields now hold the **first** answer as the resolution anchor, plus an additive `answers` list, so **no caller changed** and single-answer DOM is byte-identical (the submit-morph `flipDock` and the wisp guard are untouched). Red-proved on `cur["answers"].append(rec)` in `_parse_entries`' `is_answer` branch: commenting it out reds on the substance — *first answer lost: []* — not on a missing key, so the test reaches the real parser. Precondition derived rather than pinned: the two answer texts are asserted different before the fixture is built. **Both mirrors checked and both safe**: `answers.md` and `## Answered` run `lift_answer=False`, so each answer survives as a separate contribution in `follows` — the defect was isolated to the Open-section lift path.

- **#177** — [plan: `docs/plans/composer-row.md`] Text boxes grow with what he types, then scroll · P2 ·
  idea · 30m · his numbers: composer 2-3 → 10-15, answer/note 2 → 6 ·
  the different ceilings are right — a 15-line box inside a question
  card would shove the list for a ten-second sentence · **third time
  today** that growing something moves what is below it (#141, #169,
  now) — the growth and #104's travel are ONE gesture · the box's HEIGHT
  is now state, so #118's tick-survival applies to it · fires on every
  newline, so it is the most frequent animation on the page
  · **LANDED `95a83fb` + `e0600d5` (2026-07-29 00:00, lanes `wt/autogrow` then a recovery lane).** Both boxes grow with content to **his** ceilings and scroll past them, and the ceilings stay deliberately different — composer 2–3 → 10–15, answer/note 2 → 6 — because a 15-line box inside a question card would shove the list. Guard `dev/capture/autogrow.mjs` registered in `DEFAULT_GUARDS`; PASS at load 46.1. The `#118` tick-survival half is real work rather than a formality: on a **restore** (tick, draft) `fitText` snaps to the target height and *then* restores the standing transition, so a status tick does not re-grow the box under him mid-typing while the next keystroke still travels. **Process finding, and the reason this took two lanes: the first lane exited without reporting and with its second half uncommitted** — the guard, the justfile registration and the `fitText` fix all sat dirty in the worktree. It was recovered by dispatching a fresh lane into the same worktree to verify and land it, which worked; but this is the second occurrence of the same failure in one day and the recovery only worked because the coordinator inspected the worktree instead of trusting the branch. **The recovery lane's own note, worth keeping**: the guard's tick-survival step cannot isolate `restoreCardState`'s fit line because `restoreAnswerDrafts` masks it, so if either restore-fit path is ever removed the guard needs a second step that exercises the other in isolation — otherwise the redundancy is silently relied upon. Recorded in `watch-design.md`.

- **#402** — `status.json`'s `dreamers` array has no stated shape, and the tool that reads it goes
  stale in the one direction that costs parallelism · P2 · loop-tooling/durability · origin:
  **loop** · found by using it: registering a new lane crashed the tool and revealed three more
  · **it went stale, measured.** `#396` and `#398` had **landed** and were still listed as owning
  `review_artifact.py`, `file-formats.md`, `dev/capture/fixture/**`, `lint.py` and `test_lint.py`.
  `status_sync.py` recomputes `queue` and `current_task_ids` from live `pgrep` but **never touches
  `dreamers`**, so ownership only ever accumulates
  · **the direction of the error is the whole problem.** A stale entry says a free file is *owned*,
  so the coordinator declines a dispatch it could have made. I reasoned `dev/capture/fixture` was
  free from *memory* of `#396` landing; the file said otherwise, and had I trusted the file I would
  have skipped the dispatch. `#264` measured file contention as the **binding constraint** on how
  much runs at once — this is that constraint, manufactured
  · **it crashed on a mixed-type id.** Existing entries carry `"task": 396` (int); writing
  `"task": "401"` made `sorted()` raise `TypeError: '<' not supported between instances of 'str'
  and 'int'` and `just status-sync` exited 1. **Loud, so not the worst kind** — but it stops the
  whole sync, and the drift it exists to prevent resumes silently from there
  · **and a fourth `#401` instance:** a **sub-id cannot be represented at all**. The live lane is
  `#392a`; the int field can only hold `392`. Same class — the tooling's id vocabulary is narrower
  than the loop's
  · **the root cause is a missing contract, and it is this repo's own stated rule.** `grep dreamers
  file-formats.md` returns **nothing**, yet `dreamers` is written by the loop and parsed by **two**
  tools (`status_sync.py`, and `watch.py` renders it). The rule is that such a file's shape is
  stated there and checked by `lint.py`, in the same commit. Absent that, the int/str question had
  no answer to get wrong
  · **a fifth thing, and it bears on what he asked me to find out:** the pre-existing entries carry
  **no `agent` field**, so `status.json` does not record *which model* owns a lane. He asked which
  models and providers work best for us; the runtime record cannot answer it
  · deliverables, and therefore ownership: `status_sync.py` (prune `dreamers` by the same live-pgrep
  test it already applies to `current_task_ids`; accept both id types or normalise), `file-formats.md`
  (the `dreamers` row), `lint.py` + `test_lint.py` (the check that row implies), `test_status_sync.py`
  if one exists — check
  · **the red is available without an injection**: reinstate a landed lane's entry and assert the
  prune drops it. Assert the precondition too — that at least one entry is live and one is dead,
  derived at runtime, or the test is vacuous the day nothing is running
  · **BIGGER THAN FILED, and this half is visible to HIM.** `status_sync.py` refreshes `queue` and
  `current_task_ids` and **silently leaves every other field to rot**. Measured 10:26:
  **`last_tick` was 133 minutes stale** (`08:13`), `last_commit` was `a6c0732` — **30+ commits
  behind** HEAD — and `deployed` named rev `b4d4b3e` and **pid `1970752`, which was dead**
  · **so the browser tab he reads said `· stalled` while the loop was doing its most productive work
  of the day.** `watch.py:3667` is right — `Date.now() - t > STALE_TICK_MS ? 'stalled' : 'dreaming'`
  — and its comment at `:3634` says that word is how he tells *whether the LOOP is alive*. **The
  dashboard did its job; the data lied to it.** Refreshing the three fields flipped the title to
  `· dreaming`, verified in the browser
  · **the dead `deployed.pid` is `#363`'s lesson reopened** — the one `pending_handoff_records`'
  docstring cites as *"inferring liveness from surviving artefacts is the wrong answer"*. A pid
  field nothing re-reads is exactly such an artefact
  · **and the tool's own success message is the trap:** `just status-sync` printed
  *"already in sync (136 open, 1 live)"* **while three fields were stale**. It is in sync on the two
  it knows about and says nothing about the rest, so the reassuring line is scoped to a subset the
  reader cannot see. **Whatever fixes this must either own the whole file or NAME the fields it does
  not touch** — a coverage statement, the same idiom `#395` established for checks, applied to a
  syncer
  · deliberately **not** fixed inline: this is the same tool and the same class as the `dreamers`
  half above, so it belongs to one lane, not to a coordinator patch. The **data** was corrected by
  hand at 10:26 as tick hygiene; the **tool** is still wrong
  · **another derived-in-two-places field, found 11:16: `awaiting_human`.** It is a hand-written
  list and `questions.md` is the source; they had drifted to **4 vs 5** — the panel was missing
  `#408` and `#410` (both asked today) and carried `#371/#263 Q2`, which is **not an open question
  at all**. So his dashboard said "waiting on you" for something he had never been asked, while two
  things he HAD been asked were absent from the panel. `status_sync.py` derives `queue` and
  `current_task_ids`; `awaiting_human` wants the same treatment, from `parse_open_questions`
  · **and my hand-rolled regex for it was wrong too** — `^- \*\*(.+?)\*\*\s*$` returned 4 because one
  title wraps across lines. Third hand-rolled parser to be wrong today, against a file whose
  production parser was importable the whole time. **`status_sync` should call `watch.parse_*`, never
  re-implement it**
  · **the derived half is wrong too, measured 12:52 — and it overwrote a correct value.**
  `status_sync.py:72` gates on `pgrep -af "^ccc @"`. Today's dispatch is
  `ccc --yolo @glm52 …` — a control flag sits between the binary and the alias, so the anchored
  pattern matches **nothing** and `current_task_ids` was recomputed from `[331]` to `[]` **while
  the lane was live**, in the same run that printed a clean sync. So the dashboard reports no
  current task for the entire duration of every lane dispatched with any flag
  · **this is worse than the un-derived fields above.** Those rot; this one **actively replaces a
  correct hand-written value with a derived wrong one**, so the more careful the coordinator is
  about writing truth, the more the tool destroys. A partial syncer that overwrites what it cannot
  correctly derive is worse than one that leaves the field alone — which sharpens the coverage
  rule already recorded here: **naming the fields it does not touch is not enough if it touches a
  field it cannot compute**
  · same root as this repo's standing `pgrep` lesson, one level up: that one is *the process name
  is not its arguments*, this one is *the argument order is not a contract*. `^ccc @` silently
  encodes "no flags between binary and alias". Match the alias wherever it appears, or resolve the
  lane from `dreamers[].pid` with `kill -0`, which is exact and needs no pattern
  · related: **#401, #264, #403, #405, #410, #423, #440, #465**
  · **it demonstrated itself at 14:56, while I was dispatching the lane to fix it.** Two lanes
  were live (`ccc --yolo @glm52`, `ccc --yolo @grok`) and `status_sync.py` printed
  *"already in sync (135 open, 0 live)"*. Not reconstructed from logs — observed in the same
  minute, which is the cleanest evidence this entry will get
  · **and the crash is currently MASKED by the pgrep bug, which will surprise whoever fixes
  them in the obvious order.** `dreamers` now carries `"task": "402a"` and `"task": 367` —
  mixed str/int, and one of them a sub-id. `sorted()` never sees either, because `live` is
  empty before it gets there. **Fixing the pattern makes the TypeError appear**, so the first
  green after fixing bug 1 is a crash, not a pass. Two bugs in series where the second is
  invisible until the first is fixed
  · **THE SYNCER HALF LANDED `f1f269b`** (lane `#402a`, `ccc @glm52`, ~40 min): an
  order-independent detector, `dreamers` pruned by that same liveness test, a failed probe that
  leaves fields **byte-identical** rather than writing a derived empty, a **coverage line** naming
  every field it does not own (derived from the file's keys, so a field added next month appears
  without anyone remembering), and mixed `str`/`int`/sub-id task ids
  · **verified on the real dashboard, not only on a fixture**: the first post-merge run reported
  `current_task_ids [] -> ['172', '420']` — it found both live lanes, **pruned the dead `402a`
  entry**, and listed all 26 author-owned fields. `gate402a.py` PASSED against the merged tree with
  the pre-merge baseline
  · **the mixed-type fix HAD to ship in the same commit**, and this is the general shape worth
  keeping: the `TypeError` was **masked** by the pgrep bug, because `live` was empty before
  `sorted()` ever saw the ids. Fixing the pattern is what makes the crash reachable, so the two
  bugs were in series with the second invisible until the first was fixed. Splitting them would
  have shipped a commit whose first real use crashes
  · **the lane refuted the premise of one of my gate's checks, by experiment, and it was right.**
  I demanded that a lane whose recorded pid died but whose argv is live still be found — encoding
  `live_tasks`' old docstring (*"ccc re-execs and the recorded pid is the wrapper's, not the
  survivor's"*). Measured: after an `exec` the **pid is preserved and the argv is what vanishes**.
  So the pid is the exact signal and the brief path is the fragile fallback — the reverse of the
  docstring, which it fixed in the same commit. **Fourth lane today to be right where a check
  disagreed**; the prior in `lessons.md` is now 4-for-4
  · **the residual risk this creates, recorded because nothing checks it**: correctness now depends
  on the dispatch recipe recording the **surviving** pid. A recipe whose recorded pid is a wrapper
  that exits early would prune a **live** lane — and over-pruning is the dangerous direction, since
  the coordinator then edits files a live lane owns. Today's `setsid bash -c "… ccc …"` is safe
  because bash execs into `ccc`, so the recorded pid *is* `ccc` (`comm=ccc`, measured). Any change
  to how lanes are launched must re-check that
  · **WHAT REMAINS OF THIS ENTRY, narrowed 15:40:** (a) the `dreamers` row in `file-formats.md` plus
  the `lint.py` check it implies — deliberately withheld from the lane as `#402b`; and (b)
  `awaiting_human` is **still hand-written**: the post-merge coverage line lists it under
  author-owned, so the 4-vs-5 drift this entry recorded can recur. It wants deriving from
  `watch.parse_open_questions`, which is now a three-line change against a tool that already has
  the idiom
  · **`#402b` now has a LIVE symptom, found within a minute of the merge and caused by my own
  scoping.** `lint.py` errors on *"current_task_ids has non-integer member(s) '172', '420' — ids
  are integers; a quoted id matches no task row, silently"*. The lane widened the syncer's id
  vocabulary to carry sub-ids (this entry's own fourth finding: the int field cannot hold `#392a`)
  and I **withheld `lint.py` from it**, so the two now disagree by construction
  · **both parties are half right, which is why this is a format decision and not a bug fix.** A
  genuine sub-id lane *must* be a string, and lint's stated reason is also real — a quoted `"172"`
  matches no task row in any consumer that compares to an int. So `file-formats.md` has to state
  the vocabulary (plain id → int; sub-id → string; never a quoted plain id) and `lint.py` has to
  enforce **that**, in the same commit. Fourth checker today found narrower than the work it
  describes
  · immediate data corrected by hand rather than by widening the check: my `dreamers` entries said
  `"task": "172"` where `172` is a plain integer id, which lint is right to reject. Sub-id lanes
  like `402a` still need the string form and still have nowhere legitimate to live
  · **`#402b` IN PROGRESS 2026-07-28 17:03** — `ccc @glm52`, `.worktrees/fmt`, with `#415` in the
  same lane (same two files, same shape). The live symptom is mine from 16:44: `lint` errored on
  `current_task_ids ['218','263','419']` while `status_sync` deliberately keeps the string form for
  sub-ids. Both correct, disagreeing about a vocabulary nobody wrote down. I worked around it by
  writing ints, and **the workaround is not the fix** — the next author to write `"392a"` hits the
  same wall from the other side
  · **`#402b` DONE, `2092d57` (merged 17:47).** The id vocabulary is now written down and enforced:
  plain id → **int**, sub-id → **string**, a quoted plain id is **always wrong**. Verified across all
  four cases independently, including the one that matters — `["263"]` is still an ERROR, so the
  widening did not remove the check it widened
  · **PART (a) LANDED `cc0e244` (2026-07-28 23:52, lane `wt/dreamers`).** `status_sync.py` now reaps a `dreamers` entry whose pid is dead or whose task has left the open section, **normalises ids on write** while tolerating both types on read, and **never crashes on junk** — it skips and reports instead of exiting 1, which mattered because a syncer that exits stops protecting everything after it. The mixed-type `sorted()` crash is covered by sorting with `key=str`. `file-formats.md` states the entry shape in the same commit. **The second half is NOT done and is deliberately left**: the dashboard's rendering of `dreamers`, and what the coordinator writes at dispatch time. The lane's recommendation on that is worth keeping — **record the surviving pid, not a wrapper that exits early**, because over-pruning is the dangerous direction: a live owner reaped by mistake invites two agents into one file, which is worse than a stale entry that merely costs a dispatch.

- **#444** — the new snap detector proves a transition EXISTS, not that it has the right duration · P2 ·
  verification/motion · origin: **loop** · **the cost of `#442`'s fix, recorded at merge rather than
  discovered later**
  · `#442` correctly made `transitionstart` the load-independent gate, because a compositor-driven transition
  is invisible to a starved rAF sampler and the frame evidence cannot be required. But `transitionRan` is a
  **boolean about existence**: a transition shortened to `1ms` still fires `transitionstart`, so it now passes
  the gate where the old frame-count form might have caught it
  · **the trade is right** — a guard that lies under load is worse than one that checks less — but the gap
  should be named: between *"the CSS says animate"* and *"it animated for the duration the styleguide
  specifies"* there is now no check on this path
  · the events already captured carry the answer: `transitionWindow` returns the window, so its **width** is
  measurable without any rAF sampling at all. Asserting the observed duration against the declared
  `CARD_TRAVEL`/`.cmdmsg` value (with tolerance, and derived from the declaration rather than a literal) would
  close it and is load-independent by the same argument that motivated `#442`
  · check first whether the duration is worth asserting at all, or whether `transitions.md`'s intent is
  satisfied by existence plus the styleguide's own single-source rule — **a check that restates the CSS it
  reads is not a check**. That is the design question and it may be a refusal
  · related: **#442, #414, #413**
  · **REFUSED, with measurement and a red-proved refusal, `a268255` (2026-07-28 23:52, lane `wt/duration`).** The lane measured six consecutive green runs at load 36–42 against the declared `.35s` and refused to add a duration floor, for reasons I accept: a ±20% band (280–420) **fails the green set** on an observed 239.4ms, while a band wide enough for `#442`'s measured 665ms would exclude only pathologies the STYLE constant already forbids — **a check that restates the CSS it reads**. Shortening the declared duration is a styleguide edit in a single-source file, not a silent motion bug. Existence via `transitionstart` stays the load-independent detector. **The refusal is red-proved** in `test_duration_refusal.py`: injecting `win.dur>=280` into the snap detector fails a test, so rebuilding the floor breaks the suite. **And it found a real bug while measuring**: `transitionWindow` paired ends by `ends.at(idx)`, producing **negative durations** (−67.7, −70, −177.8ms) while `ran` stayed true — so `#442`'s helper was not always measuring the transition under test. Now pairs the first end at-or-after the chosen start, red-proved by reverting to `ends.at(-1)`.

- **#442** — `midFrames(...) >= 1` reduces the frame-rate bet but does not remove it, and the guard that
  proves this is the one that claimed otherwise · P2 · verification/motion · origin: **loop** · **found by
  coordinator inspection at `#414`'s merge, minutes after the lane argued the problem was gone**
  · `#414`'s lane converted `prominence.mjs` to `midFrames(tops) >= 1` and concluded *"the conversion IS the
  resolution … the `mid >= 1` form is frame-rate-free — it needs one part-way frame, which a real non-snap
  motion produces regardless of load"*, and therefore that no separate entry was needed. The reasoning is
  good and the conversion is right; the conclusion is too strong
  · **the counter-evidence was already on disk.** `confirmation.mjs` has been on `midFrames(...)>=1` /
  `midStates(...)>=1` since `a027ad0` — not the count form — and at merge it **FAILED** `popout success
  arrives through intermediate opacity and drift` in a two-guard run at load 52.42, then **PASSED solo** at
  load 53.06. Same tree, same minute, higher load on the passing run. So load is not the variable and the
  count form is not the cause: **contention within a run is**, which is exactly what `#414` originally
  observed and parked
  · **the mechanism to check first**: `mid >= 1` needs one frame landing *strictly between* the endpoints
  **during the transition window**. Under contention rAF can deliver its frames clustered before and after
  the CSS transition rather than inside it, so `tops.length >= MIN_SAMPLES` (3) passes while `mid` is 0. The
  precondition and the assertion measure different things and the gap between them is where this lives
  · so: decide whether the precondition should assert *frames landed inside the window*, not merely *frames
  arrived*. That is a smaller and more testable claim than the three options `#414` listed, and it does not
  require a deterministic clock
  · **this host is never idle** (~30 ambient, 52 during this merge, from other agents' sessions), so any
  criterion shaped like *"passes on a quiet machine"* is untestable here — see `#428`
  · related: **#414, #441, #428, #413, #444**
  · **LANDED `9edb3f7` (2026-07-28 23:15, lane `wt/window`).** My diagnosis was the right shape and the wrong mechanism, and the lane found the real one: **rAF runs on the main thread while opacity/transform transitions run on the compositor**, so under load the compositor animates the property perfectly in real time while **zero** rAF callbacks fire inside the window — `midFrames` reads 0 over a flawless animation. Measured: 8 burners, 6 samples, transition 289–665ms wide, **0 rAF samples inside the window in all six**; at baseline 4 land inside. It also found the page's own `#dreambg` shader is a continuous main-thread rAF consumer, so the sampler competes with the page even at zero external load. Fix: `transitionstart` is the **load-independent snap detector** (a snap never fires it), with `transitionWindow`/`framesInWindow` in `dom.mjs` giving direct frame evidence when the trace did sample the window. **It refuted my acceptance criterion and was right**: I asked for *did-not-sample-the-window* to be a hard FAIL, and it measured that this happens at every load level including baseline, so my criterion would have made the guard fail permanently on this host. It deliberately left `prominence.mjs`, `states.mjs` and `reviewsplit.mjs` alone because those are FLIP animations on the main thread, where sampler and animation share a thread and cannot desync. Coordinator-verified after merge: three guards PASS solo at load 24.9, and **two concurrent suites both PASS at load 36.37** — the two-guard shape that failed at 52.42 before the fix.
- **#416** — a mitigation record is a claim about system state, and nothing re-checks it · P3 ·
  system/mitigation-drift · origin: **loop** · **split out of `#408`'s rec rather than folded into
  its closure**, because it applies to bullets `#408` never touched
  · `~/CLAUDE.md`'s *"System mitigations in place"* section has six bullets. Each names a file or a
  systemd unit, so each is checkable in **one line**. Three were checked while resolving `#408`
  (the `settings.json` env key, the fish `--no-optional-locks` function, `git-lock-watch.service`)
  and **one of the three was false** — the paragraph read as one mitigation and was two-thirds
  true, which is the shape that defeats reading it
  · the four unchecked: Brave's `--ozone-platform=x11` flag file, `sccache-server.service`, the
  amaroo git-wf2 / `pi-powerline-footer` patch (whose own note says *"re-check after package
  upgrades"*, so it has a stated expiry nobody is watching), and root's `ntp-force-sync.timer`
  · **the deliverable is the audit and its result written down**, not a tool. A checker for his
  dotfiles is scope this loop should not take; a dated line saying what held is cheap and is what
  the next investigation actually needs
  · one caution learned today: **do not "fix" a drifted mitigation by editing his config.** `#408`
  changed `settings.json` only because he answered yes to a direct ask. An audit reports, and asks
  before it repairs
  · related: **#408, #283**
  · **LANDED `9d05e3e` (2026-07-28 22:01, lane `mitaudit`, read-only on master).** `.dreamwork/docs/mitigation-audit.md`: **all four unchecked records hold** — Brave's x11 flag (line 4 of the flags file), `sccache-server.service` (active/enabled), the `pi-powerline-footer` patch (line 117 still carries `--no-optional-locks` and the xsm comment), and `ntp-force-sync.timer` (active/enabled, last oneshot 21:38:51 success). No repair entries filed because there is nothing drifted. Two honest gaps rather than guesses: it did **not** query the npm registry, so whether upstream 0.7.0 now carries the flag is unsettled (`npm view` would settle it), and amaroo PR #893 was not grepped in an install. **The rewording finding is the valuable half**: only the git index.lock bullet has the `#408` multi-claim shape, packing five independently falsifiable mitigations into one paragraph — a drop-in split is in the doc, and `~/CLAUDE.md` was correctly left unedited for him to apply. The `pi-powerline-footer` patch still has a stated expiry (*re-check after package upgrades*) with no watcher; this audit is the re-check.

- **#414** — a motion guard's pass condition depends on the browser's FRAME RATE, and it does
  not say so · P2 · verification/motion · origin: **loop** · found by the only failure in the
  first fully-clean `just test` of the day
  · **the shape.** `confirmation.mjs` samples `opacity`/`transform` in a `requestAnimationFrame`
  loop and asserts *"arrives through intermediate opacity and drift"* by requiring **≥4 distinct
  opacity values and ≥3 distinct transforms inside a 500 ms window**. That is the right way to
  check a transition — `transitions.md` is explicit that an end-state assertion cannot fail on a
  motion bug — but **4 distinct values are arithmetically impossible below 4 samples**, and the
  sample count is the frame rate. At 60 fps the window holds ~30 frames; under load rAF throttles
  and it starves
  · **so the check has two failure modes that print the same line**: the motion is wrong, or the
  machine was busy. Those need opposite responses, and the output could not tell them apart —
  which is exactly how `docktarget`/`noteprop` spent six hours miscategorised today (#413)
  · **PARTLY FIXED 2026-07-28 13:44** (`dev/capture/confirmation.mjs`): a precondition now runs first for all
  three windows and names the count — `popout arrival window sampled enough to see motion
  (N frames)`, threshold 8, comfortably above the 4 the assertion needs and far below the ~30 a
  healthy frame rate gives. **Red-proved** by starving the window to 20 ms: it fails with
  `(1 frames)` *above* the motion assertion, so the diagnosis is now readable in the summary line
  · **what is NOT fixed, and why this stays open.** The guard still *fails* on a busy machine — it
  now fails **informatively**, which is a smaller thing than being right. Observed: FAIL inside a
  full `just test` at load ~30, PASS twice solo at the same load, so contention within the suite
  is implicated rather than load alone. Deciding between waiting for a quiet frame budget,
  measuring distinct values over a duration rather than a fixed window, or driving the clock
  deterministically is a real design call and wants its own increment
  · **and the general form is worth a sweep**: every guard asserting "N distinct intermediate
  values" carries this hidden precondition. `grep -l 'requestAnimationFrame' dev/capture/*.mjs`
  and check each for a stated sample floor
  · **SWEPT, and the answer already exists in this repo.** 34 guards sample with
  `requestAnimationFrame`; only three assertions use the frame-rate-dependent form
  (`new Set(xs).size >= N`): `confirmation.mjs` ×3 (now precondition-guarded) and
  **`prominence.mjs:183`** — *"...continuously, rather than in a couple of jumps"*,
  `new Set(tops.map(Math.round)).size >= 6`. Prominence has an anti-vacuity check beside it
  (`total >= 8`, that the card travelled at all) but that measures **distance, not sample
  count**, so a starved trace fails it the same way. Second site, same defect, unguarded
  · **`reviewsplit.mjs` already solved this and says so in a comment**, which makes it the fix
  rather than a nice idea: `travel()` computes `mid` = *"the number of frames strictly BETWEEN
  the two ends"* (`ws.filter(v => v > lo && v < hi).length`, endpoints ±1) and its comment names
  our exact problem — *"A snap has none of those however slowly the machine is drawing, while
  `positions` is capped by how many frames a loaded SwiftShader box managed"*
  · **so the real fix is a formulation change, not a threshold.** *Count frames that landed
  part-way, not distinct values.* A snap has **zero** mid-frames at any frame rate; a genuine
  transition has ≥1 provided a single frame lands mid-flight. That is a **rank-1** requirement
  instead of a rank-4 one, which is why it survives a busy machine. The precondition I added is
  a diagnostic, not the cure, and should stay as one — it names the count when starvation does
  bite
  · **one direction NOT to copy blindly**: `reviewsplit` also asserts `distinct(head) === 1`
  (that something did NOT move). Starvation makes that assertion **more** likely to pass, so its
  failure mode is a false GREEN, which no precondition on this task's side would catch. Out of
  scope here, worth its own look
  · deliverables: adopt the `mid` formulation in `confirmation.mjs` (3 assertions) and
  `prominence.mjs` (1); keep the sample-count preconditions as diagnostics; red-prove each by
  removing the transition so mid-frames go to zero
  · **LANDED `a027ad0` (2026-07-28 14:03).** `midFrames`/`midStates` in `dev/capture/dom.mjs`, shared;
  `confirmation.mjs`'s three assertions converted; sampling preconditions kept as **diagnostics**
  and dropped 8 → 3 frames, which is where a mid-frame stops being arithmetically possible rather
  than merely unlikely
  · **red-proved on the real pipeline, not just the helper**: injected `transition:none` on
  `.pmsg` in a scratch worktree ⇒ both popout assertions FAIL **while the sampling preconditions
  PASS**, so the guard says *the motion is wrong* rather than *we did not look enough*. That
  discrimination was the entire task. Helpers separately checked both ways (snap → 0, gradual → 2)
  · **`prominence.mjs` deliberately NOT converted**, and the file says why in place. Its claim is
  *"continuously, rather than in a couple of jumps"* — strictly stronger than not-a-snap, and two
  jumps would satisfy a mid-frame test while failing the claim. **A smoothness property genuinely
  needs many samples**, so weakening it to survive load would be buying green with meaning. It
  gets the precondition only
  · **that distinction is the transferable part**: before reaching for the frame-rate-free form,
  ask what the assertion actually claims. *Not a snap* is rank-1 and converts. *Smooth* is rank-N
  and cannot — for those, state the precondition and accept that a starved machine cannot decide it
  · remaining, unchanged: `reviewsplit`'s `distinct(...) === 1` assertions (that something did NOT
  move) fail **green** under starvation — the opposite direction, uncovered by anything here
  · related: **#413, #442, #444**
  · **the ORIGINAL SYMPTOM IS FIXED, measured 14:31-14:50.** A full `just test` ran to completion
  under its own contention: **51 guards, 0 failures, real exit 0** — the first fully green suite of
  the day — and `confirmation`, the guard this entry was filed for, **passed under full-suite
  load**, which is precisely the condition it used to fail in while passing solo. So `a027ad0`'s
  frame-counting conversion holds where the distinct-value form did not
  · **what keeps this entry open is the INVERSE hazard, and it is the more dangerous half.**
  `reviewsplit.mjs` asserts `distinct(head) === 1 && range(head) <= 0.5` to prove a fade did
  **not** happen under reduced motion. Under starvation a real fade also samples one value — so
  that assertion **passes when the thing it forbids is occurring**. Frame-rate coupling in the
  positive direction costs a false red, which is loud; in the negative direction it costs a false
  green, which is silent, and this repo has spent a day on exactly that asymmetry
  · so the remaining work is not "convert the last two". `prominence.mjs:183` stays as it is
  deliberately (its *"continuously, not a couple of jumps"* is strictly stronger than
  not-a-snap, and a precondition already states its sampling requirement). The work is: give
  `reviewsplit`'s reduced-motion assertions a **sample-count precondition** so starvation makes
  them ABSTAIN rather than pass, and red-prove that by starving them on purpose
  · narrowed to that single deliverable 15:12; priority unchanged at P2
  · **LANDED `85310bf` (2026-07-28 22:10, lane `wt/prominence`).** `prominence.mjs`'s `new Set(tops.map(Math.round)).size >= 6` is now `midFrames(tops) >= 1` with a sample-count precondition asserted first and named in its message. It **reused** `dom.mjs`'s existing `midFrames` export — the same helper `confirmation.mjs` imports — so no fourth copy and `dom.mjs` untouched. Red-proved against `watch.py:4981`'s `el.style.transition = CARD_TRAVEL` (the FLIP): neutralised to `'none'` the neighbour snaps with 100 frames and 0 part-way, and the lane noted the arrival check reports `late=0.0` **even on the snap**, so the `mid` check is doing non-redundant work. The two failure modes print distinguishable first lines. It kept `total >= 8` as the *distance* vacuity literal and argued no `#441`-style split is needed because it covers one motion at ~5% of a measured 156px travel — correct reasoning. **On the parked design call it answered: the conversion IS the resolution, landed rather than deferred**, since all three options the brief listed assume the count form is retained. **Coordinator inspection at merge partly refutes that** — see `#442`: `confirmation.mjs` is already on `midFrames>=1` and still failed at load 52 in a two-guard run while passing solo at 53, so the frame-rate coupling is reduced but not removed.
- **#333** — `states.mjs` is the SIXTH holder of the forbidden count idiom, and
  unconverted · **P2** (raised from P3) · correctness · origin: **loop** · #327
  filed this as a docs-wording slip; measuring it made it a real one · the count
  rule in `transitions.md` says **never assert an absolute count of distinct
  positions** — `uniq(positions).length >= 8` is a fact about how many frames the
  machine drew, not about the motion — and names five guards that encoded it,
  "**all five now converted**" · `dev/capture/states.mjs:114,118,122` holds three
  more (`uniq(upH).length >= 6`, `uniq(dnH).length >= 6`, `uniq(tkH).length >= 6`),
  and its line 134 comment instructs *"count intermediate positions"* · **measured
  2026-07-27: those three are the only LIVE instances left in `dev/capture/`** —
  every other grep hit is a comment recording its own conversion, so the "five"
  count was accurate and simply never counted this guard · the document also
  DESCRIBED them approvingly ("visited many intermediate positions"), so a reader
  found the banned idiom endorsed 200 lines from the ban and would cite the nearer
  sentence · **the doc half is done**: `transitions.md` now names the exception in
  both places and says it is a debt · **remaining**: convert the three to
  `between()` with the vacuity precondition the rule requires, red-first · note
  `states.mjs:164-165` uses `<= 3` to assert reduced-motion does NOT animate — that
  is the opposite assertion and must stay a count · `dev/capture/states.mjs` is
  currently held by `ccc-glm52-324`, whose brief covers report.mjs adoption only,
  so sequence this after #324 lands to avoid two agents in one file
  · **UNBLOCKED — `#324` LANDED and nobody re-triaged this** (found by `#420`'s census, machine-verified against `parse_ledger`, re-verified by the coordinator 2026-07-28 15:53): the reporter conversion landed, so the sixth `states.mjs` count-idiom holder is reachable — and `#414` has since changed what the right idiom IS, so read that before starting. **Startable now.** This entry is one of **ten** with the same shape, which is why the census was worth running: a blocker that clears is invisible from the blocked side, so nothing ever re-reads it
  · **LANDED `988de22` (2026-07-28 21:38, lane `wt/states`).** The three `uniq(...).length >= 6` assertions are now three ordered checks each: a frame-rate precondition naming its sample count (the `#414`/`confirmation.mjs` shape), a vacuity check that the height really changes, then `between()` on the motion with the part-way count printed. It also found and converted a **fourth** site the entry did not name — the matrix continuous-size/position checks using `track(...).length < 6`, the same forbidden idiom on the multi-card path — and rewrote the line-134 comment that instructed it. `164-165`'s `<= 3` correctly **stays a count**: it asserts reduced motion does NOT animate, the opposite contract. Red-proved against `watch.py`'s `travelCard` height invert, and the two failure modes print distinguishable first lines — `sampled enough… (2 frames)` for a starved window versus `TRAVELS… (0 of 96 part-way)` for a real snap, which is the ambiguity `#413` was miscategorised on for six hours. Guard re-run green on the merged tree (22 PASS at load 32.3). `transitions.md`'s debt note is spent in the same commit.

- **#440** — the coordinator hand-rolls a ledger split on every fold, and the unanchored form has now
  corrupted the file once and produced a nonsense count once · **P1** · loop-tooling/ledger ·
  origin: **loop** · **found by doing it wrong twice in one hour, with the fix already written down**
  · `.dreamwork/tasks.md` has exactly one `## Open` and one `## Recently landed`, but the string
  `## Recently landed` also appears **in the prose of an open entry**. So `t.split('## Recently landed', 1)`
  splits at the *mention*, not the heading
  · **what that cost, both times on 2026-07-28.** (1) Folding four landed entries wrote a file with **two**
  landed headers and 130 lines in the wrong half; `lint` caught it only obliquely, reporting a *reciprocity*
  error about an unrelated pair (`#395`/`#353`), which took four probe commands to trace back to the
  structure. (2) Counting open entries for `status.json` returned **33** instead of 142, caught only because
  the number was absurd
  · **this is the fifth hand-rolled ledger parser to be wrong here**, two of which damaged a sectioned
  file, against a file whose production parser (`watch.parse_ledger` / `ledger_entries`) was importable
  every time. The lesson is recorded, `#437`'s brief warned a lane about this exact defect an hour before
  it bit, and it bit anyway — which is the argument that a **lesson is not a guardrail**
  · so: a single supported way to fold an entry. Sketch: `dev/ledger.py fold <id> --note <text>` that moves
  the entry from Open to the top of Recently landed, appends the note line, bumps nothing it should not, and
  **asserts both headings match `^## …$` exactly once before and after**. Counting comes free from the same
  module, which removes the second failure mode as well
  · **`lint` cannot police a throwaway script**, so the check that matters is that the tool exists and is
  the only path — the anti-corruption assertions live inside it, not in a linter looking at the aftermath
  · related: **#402, #353**
  · **LANDED `1b32398` (2026-07-28 21:20, lane `wt/ledgertool`).** `dev/ledger.py` is now the one supported path: `fold <id> --note <text>` and `counts`, both reusing the production parser — membership from `watch.parse_ledger`, section boundaries from the imported `watch.LEDGER_SEC_OPEN`/`LEDGER_SEC_LANDED`, entry grammar from `watch.LEDGER_ENTRY`, so no sixth parser exists. Headings asserted anchored, exactly-once-each and Open-first, **before and after** every write, and a file that fails is never written. Red-proved in place on `landed_idx = _heading_line(...)`: swapping it for the unanchored line-scan failed **3** tests and reproduced *both* real incidents — `#2 matches 0 open entry head(s)` (the 33-instead-of-142 count) and an entry folded at the prose mention (the corruption). Its trap fixture asserts its own precondition at runtime, so dropping the prose mention fails loudly rather than going hollow. `file-formats.md` now states the heading contract, which was implied but written down only for the other files. **This entry was folded by the tool itself.**

- **#431** — `just deploy`'s `pkill -f` kills any process whose command line merely mentions the
  snapshot, including the shell running the deploy · P1 · loop-tooling/deploy · origin: **loop**
  · **it killed my own shell mid-deploy, 2026-07-28 18:16**
  · The recipe does `pkill -f "$(basename "$snap")"` where the basename is
  `ud-dreamwork-watch.py`. **`pkill -f` matches the whole command line of every process**, so it kills
  not just the server but anything that names the file — an agent shell that assigned the path to a
  variable, an editor, a `grep`. My command line contained the string, so the deploy killed the shell
  executing it: **exit 144 (128+16, SIGTERM), the recipe cut off partway through.** The server did come
  back, verified `HTTP 200` at a fresh pid with `bdmed` served, so nothing was left broken — this time
  · **why it has never bitten before:** it only fires when the caller's own command line mentions the
  snapshot basename, which a plain `just deploy` does not. So it is rare, silent, and it interrupts the
  one recipe whose half-completion leaves **the human's dashboard down**. `pkill` cannot report this: it
  has already killed the process that would have noticed
  · fix: kill by **pid**, not by pattern — read the listening pid (`ss -ltnp` on the persisted port, the
  idiom `dev/deploy_state.py` already uses) and `kill` that, or add `pkill -f "^python3 .*<snap>"` so a
  mention is not a match. Prefer the pid: a pattern that must not match the caller is a pattern that
  will one day match the caller
  · related: **#426, #425, #439**
  · **LANDED `522d30d` (2026-07-28 20:52, lane `wt/deploykill`, merge `f96c94c`).** The deploy now identifies its own server rather than pattern-matching command lines: `ss -ltnp` gives the pid bound to `.dreamwork/watch-port`, `/proc/<pid>/cmdline` verifies an argv element whose realpath is the snapshot, then SIGTERM with SIGKILL only if it is still listening. Nothing listening exits 0 quietly; a **foreign** listener on the port exits 1 **without signalling** — the fail-loud case that matters, since killing nothing beats killing the shell. The lane argued against a pidfile and I accept the reasoning: the port file already identifies the target, a bare pid is ambiguous after wrap-around or `os.exec`, and a pidfile would still need the same cmdline verification. Red-proved twice — reinstating `pkill -f` in the recipe reds `test_justfile_deploy_does_not_use_pkill_f`, and reinstating it in `stop_deployed` kills the decoy. **Every decoy test asserts its own precondition** (decoy alive and `pgrep -f` actually matching) before the stop step, with a per-run unique pattern so the tests can never match the live dashboard's basename.
- **#432** — the above-fold checker hard-codes a fold that three separate inputs move · P2 ·
  loop-tooling/review-artifacts · origin: **loop** · **the half of `#429` that is a retrofit, not a fix**
  · The criterion and its checker exist (`1dd973f`) and three artifacts carry `#ask`: `421` (218/266),
  `417` (246/315) and now `263` (188/266). **The other 19 have no such element**, so
  `above_fold.mjs` reports `#ask MISSING` and gates nothing about them
  · so: make the id a documented requirement in `file-formats.md` / the artifact template, and only
  then register a guard that walks `.dreamwork/review/` — registering it before the retrofit would red
  the suite over 19 artifacts that predate the contract, which is why `above_fold` sits in
  `lint.NOT_GUARDS` today with that reason written down
  · **do not retrofit by adding an empty `#ask` to each page.** The id has to wrap the actual decision
  or the check passes on a page whose ask is still buried — the same hollowness in a new place. Pages
  with no decision to make (a design note, a schema) should be **exempt by declaration**, not by
  carrying a decoy element
  · **SPLIT 2026-07-28 19:57.** The `#ask`-as-a-contract retrofit above is now **#436**; this entry is
  the **fold-derivation half only**, and it is the half that is out with a lane
  · **also derive the fold from the live route rather than hard-coding it** — and the case for this is no
  longer theoretical. The mobile constant was wrong **three times in one evening, always optimistic**:
  **706** (the top of a measured 693..708 range, when a fold must take the floor), **691** (the floor
  measured inside a worktree), then **670** (the floor on the real target). Three separate inputs move
  it and none is the viewport: the **artifact's filename length** (`SPAN.revname` wraps the title bar,
  the chrome grows, the frame shrinks — the iframe's bottom is pinned at 828, its top is not); the
  **target directory's basename**, because that is the project name in `#hproj` sharing the same line
  (`frame` gives floor 693, `ud-dreamwork` gives 672 — so a fold verified in a worktree is not verified
  for his surface); and **how the name breaks** (a padded `xxxx…` run of the right character count has
  no hyphen to break on where real names do, so a derived *length* is not a derived *layout*)
  · **owner: `wt/fold` lane (glm52), dispatched 19:57** · brief: `.dreamwork/docs/briefs/432-derive-the-fold.md`
  · related: **#429, #430, #434, #436**
  · **LANDED `a6fbf3b` `04dcae9` (2026-07-28 20:35, lane `wt/fold`).** `above_fold.mjs` now derives the fold per artifact by serving the real target on an ephemeral port, loading `/review?p=…` and measuring `#reviewframe` — no constant survives. Reproduced 708 (shortest name) / 672 (longest) / 740 (desktop, and the lane's pushback is that desktop has **no** per-artifact spread: no name in the corpus wraps at 1280, so 740 is uniform and it says so). `devoverlay.mjs`'s fold block was **repointed, not deleted** — it keeps the anti-vacuity spread (≥8px between shortest and longest) and now cross-checks the tool's derived fold against the guard's own independent `getBoundingClientRect`. Red-proved on `fold: r.h` → `fold: r.ih`: 844 vs 708. The lane names the residual honestly — the cross-check cannot catch a fold that regresses *too small*, since a small fold passes `ask.top < fold` harder; that pessimism lives in FALLBACK mode and the spread assertion.

- **#426** — an agent must survive its own files changing under it, or be told to reload · P1 ·
  loop-architecture · origin: **human** · **human direct, 2026-07-28 17:38**, stated as a general
  principle rather than a bug
  · verbatim: *"In general this should kind of be a principle of ours: the files on disk might be
  updated while agents are running, so they need to be able to continue running OR be explicitly told
  (via tooling or which files they read) that they must reload the skill and associated tooling like
  heartbeat, Monitor for user events, etc."*
  · **the two acceptable states, and there is no third:** either the running agent **continues
  correctly** across the on-disk change, or it is **explicitly told to reload** the skill and its
  tooling (heartbeat, the watch-events monitor, the dashboard server). Silently running against a
  half-updated tree is the state this forbids, and it is the state we are in by default today
  · **we have live evidence this session, which is what makes it P1 rather than hygiene.** A brief was
  amended mid-flight three times today and each time the question *"has the lane already read it?"* had
  no answer available to either side. `SKILL.md` and `CLAUDE.md` are read once at session start, so a
  change to either reaches nobody already running. And this session is running `watch.py` as a server
  from a tree that has had **many** commits under it since it started
  · so the shape is a **version/identity signal** the running agent can check cheaply — the skill
  version plus what it read, against what is on disk — and a defined action when they differ. That is
  adjacent to `#263`'s mixed-version gate (lane **H**, increments 34-35: *"mixed-version fail-closed
  before witnessing"*), which solves the same problem for the **journal**. **The generalisation is
  his, and lane H is one instance of it** — worth deciding whether they share a mechanism before either
  is built twice
  · also names `.dreamwork/run-mode` as prior art: it is re-read on every tick precisely so an on-disk
  change reaches a running loop, and it is the only file in the system with that property today
  · related: **#425, #368, #263, #431, #443, #445**
  · **LANDED `ed2d7e1` `2b261f4` (2026-07-28 20:35, lane `wt/reload`).** Design at `.dreamwork/docs/reload-signal-design.md`; increment is `watch.skill_identity()` → `{commit, skill_version}`, exposed via `collect()` so it rides `/data.json`. **Two facts, never one** (the `deploy_state.py` discipline): `commit` moves on every change, `skill_version` only on a migration, so *"my tree changed"* and *"the change affects what I read"* split structurally rather than heuristically. **Lane H decision: do NOT share a mechanism** — same question shape, but different comparand (protocol version in data vs commit of source), trigger site (data-witness vs time boundary) and action (fail-closed refuse-write vs reload-or-report); parallel instances, not nested. Lanes E/G/H not built. Deliberately **not** built: a per-tick `reload-signal` flag file (it re-conflates exactly what the design splits), auto-reloading SKILL.md/CLAUDE.md (the harness reads once; the loop cannot make it re-read), content hashing. **No artifact shipped, on purpose** — the one decision that is his (convention vs flag file) is premature until the convention has been tried, and a decoy ask is worse than none.
- **#405** — the loop has been managing file contention by hand all session when his standing
  convention already removes it: **worktrees** · **P1** · loop/parallelism · origin: **loop** ·
  found because **#397's plan named it as the cheaper alternative to the thing #397 was asked to
  design** — the lane routed around its own brief and was right to
  · **the whole session's binding constraint is one that was already solved on paper.** `CLAUDE.md`
  states worktrees under `.worktrees/` as the preference for features and executing plans.
  `SKILL.md` is more specific still: *"When disjointness can't be arranged — the work overlaps owned
  files … dispatch the dreamer in a worktree: the invariant then holds by construction."* **Every
  lane this session ran in the shared tree.** Nothing consulted either rule at dispatch time
  · **what that cost, counted:** `#354` inc1 was **shelved** (`a6c0732`) purely because `#300`,
  `#385` and `#391` held `watch.py`; three dispatches serialised on that one file; `#392b` and
  `#399` are blocked on it **right now**; and `#402` exists because I hand-maintain the ownership
  list that only matters in a shared tree
  · **and it produced a 459-line design document.** `#397` asked whether to extract 6,756 lines of
  client into real files, and its own answer was *"the throughput win is captured more cheaply by a
  worktree"*. So the loop commissioned an architecture study for a problem the human had already
  ruled on, in writing, in the file the loop reads at init
  · **why it did not get used, which is the actually interesting question:** the coordinator tracks
  ownership in `status.json` and treats a conflict as *"do not dispatch"* rather than *"dispatch
  differently"*. That is a **selection** habit, and it never reaches the worktree branch because
  the conflict is resolved (by declining) before the branch is considered. Nothing is broken —
  a step is simply missing from the dispatch decision
  · rec: at dispatch, a file conflict routes to a **worktree**, not to a queue. Make it the
  documented default in `SKILL.md`'s subagent section, then measure whether the next batch actually
  takes the branch — *"the loop optimises against the criteria"*, and an unmeasured default is a
  preference nobody reads (**#400**)
  · **the two costs `SKILL.md` already names, which stay real:** duplicated build state (no
  compiled toolchain here, so cheap), and cleanup — never force-remove without
  `git status --porcelain --ignored` first, because untracked lane scratch is exactly what lives in
  a lane's worktree
  · **one thing to check before adopting, not after:** a lane in a worktree cannot see the parent's
  uncommitted state, and several guards resolve paths from `__file__` or copy the tree to a temp
  target. Verify `just guards` and `just deploy` behave in a worktree **before** a batch depends on
  it. `#397`'s plan already found `deploy` snapshots by `git show rev:`, which is worktree-safe
  · **FIRST USE, and it worked: `#392a`'s red was taken in `.worktrees/verify-392a` off `HEAD`**,
  injuring a copy while the live tree stayed clean throughout. `pytest` runs in a worktree unchanged.
  `git worktree list` also shows `.worktrees/277-dreamfade` — so the machinery has been used here
  before and simply never enters the dispatch decision, which is `#405`'s whole point
  · **but dispatching a LANE into one has two traps the shared tree hides, and both are silent:**
  **(1) `.dreamwork/inbox.md` is UNTRACKED, so it does not exist in a worktree at all** — a lane
  appending its report there creates a fresh file in the worktree that the coordinator never reads.
  That is exactly the loss `#392a` suffered by accident, made structural. **(2)
  `.dreamwork/handoffs.md` IS committed**, so a lane appends to its own copy and the line is
  invisible until merge, or becomes a merge conflict
  · **so the dispatch prompt must give both channels as ABSOLUTE paths into the main checkout**, not
  repo-relative ones. Every brief written so far says `.dreamwork/inbox.md`, which is correct in the
  shared tree and silently wrong in a worktree. **Fix the brief template before the second lane, not
  after**
  · **and adjacency is a real constraint on how much a worktree buys.** `#399`'s target
  (`_landed_ids`, `:7685`) and `#401`/`#406`'s (`parse_handoffs`, `:7712`, with the `HANDOFF_*_RE`
  constants **between** them) are **27 lines apart**. Worktrees remove the *contention*, not the
  *merge*: two lanes in one region still collide, just later and less visibly. Route by **region**,
  not by file
  · related: **#397, #264, #402, #400, #399, #406**
  · **LANDED `066c57d` (2026-07-28 20:35, lane `wt/wtdefault`).** `SKILL.md` now states **worktree-by-default for any dreamer that writes files** at the dispatch point — shared-tree is the exception needing a reason, a read-only lane being the legitimate one — and the escalate-only-when-disjointness-fails paragraph is gone rather than duplicated. It also states the trap this session kept paying by hand: **inbox and hand-off paths given to a worktree lane are absolute**, because a lane in `.worktrees/x` told to append `.dreamwork/inbox.md` writes its own copy and the coordinator never sees it. Made checkable: `lint.check_brief_worktree_abs_inbox` flags a post-cutoff brief naming a worktree without an absolute inbox path, with the cutoff **content-resolved rather than sha-pinned**, a hollow-no-cutoff ERROR, and a live-coverage precondition. Red-proved on the `ABS_INBOX_PATH_RE` branch. 30 existing worktree briefs grandfathered, 0 in scope.

- **#437** — dispatch selection depends on what the coordinator happens to remember, and the ledger is
  too large to re-read · P2 · loop-tooling/orchestration · origin: **loop** · **filed and landed in the
  same hour, split out of `#420`'s inventory work**
  · `#420` fixed the *inventory* question once; the *dispatch* question — given these files are already
  owned by live lanes, what should go out next and what would it own — is asked several times an hour and
  had no artifact
  · **LANDED `201bdf4` (2026-07-28 20:16, lane `shortlist`, read-only on master).**
  `.dreamwork/docs/dispatch-shortlist.md`: 12 ranked startable tasks, each with its file-ownership set,
  plus two parallel-safe triples with disjointness shown. It **corrected the census** rather than
  restating it: `#371` reads as unblocked in its own prose but sits behind `#263`'s second gate and is
  not buildable; `#172` and `#218` have landed, cutting the stale-blocker ten to eight; counts moved
  139/175 → 144/186. Lanes E/G/H excluded as ordered
- **#427** — the hand-off grammar is widened in `lint` but not in the parser, so the dashboard still
  cannot read a two-sha line · P3 · loop-tooling/format · origin: **loop** · **named by the `#415`
  lane rather than left to be found**
  · `#415` widened `lint.check_handoffs` to accept one-or-more shas, correctly declining to reach into
  `watch.py`'s `HANDOFF_PENDING_RE` which another lane's tests assert on. So `lint` is quiet and
  `parse_handoffs` **still classifies a multi-sha line as malformed** — `pending_handoff_records` will
  not surface its shas
  · so: widen `HANDOFF_PENDING_RE` and `parse_handoffs`' return shape in `watch.py`, in the same commit
  as the `test_watch.py` assertions that read `pending[0]["sha"]`, and the `lint` reclassification
  becomes a **no-op** rather than needing removal — that ordering is the point
  · related: **#415, #401**
  · **landed `30ed49d`** (Grok 4.5 lane `3b6e674`, self-identified). Shape: `HandoffPending(tuple)` that
  unpacks and compares as `(id, sha, claimer)` with an **additive `.shas`** — so `lint`'s 3-unpack and
  every existing triple assertion needed no change, and **`lint.py` was never touched**, which was the
  whole point of the ordering the entry specified
  · verified against the real parser rather than the report: a two-sha line yields `malformed=[]`,
  `shas=('54c68e8','25a3fe4')`, `sha == shas[0]`, with the two shas **asserted to differ at runtime** so
  the check cannot be vacuous. Red-proved by reverting the named production line
  (`HANDOFF_PENDING_RE`'s single-backtick form) with the pattern's presence asserted first, so a missed
  injection could not read as a pass. 262 passed (was 260)
  · `file-formats.md` updated in the same commit — its Multi-sha section still described the watch parser
  as single-sha, so the doc had been describing the bug as the design

- **#434** — the `/review` route wastes 24% of a phone screen below the artifact frame · P2 ·
  Web UI/dashboard · origin: **loop** · **found by looking at the page, measured after, 2026-07-28 19:12**
  · At **390x844** the artifact iframe is `135..641` — **506px** — and the **203px** beneath it holds
  **zero rendering elements**. `document.scrollHeight` equals `innerHeight`, so the page does not scroll:
  that quarter-screen is not off-screen content, it is **empty**. Desktop wastes only 40px (4%), so this
  is a mobile-only defect
  · **the cost is compounding, which is why it is worth more than 203px.** Everything he reads a
  decision in — the ask, its accepted answers, the recommendation — competes for 506px instead of 709px.
  Fixing it is a **40% increase in reading area** on the surface where every review artifact is judged
  · **and it is the root cause of a constraint I just tightened elsewhere.** `above_fold.mjs` compares
  against an effective fold of **504** on mobile precisely because of this frame; with the dead space
  reclaimed the fold moves to ~707 and artifacts stop having to fight for the top 500px. Better to fix
  the frame than to keep compensating in the checker (`#432` wants the fold derived at runtime, which
  would then pick this up for free)
  · likely a fixed/calculated frame height rather than a flexed one — read the `/review` shell's layout
  before assuming. **`transitions.md` applies**: the route change onto `/review` is the reference gesture
  in this repo, so a height change must not introduce a second idiom
  · related: **#430, #432, #435**
  · **landed `5abc4c1`** (grok lane `bfc3222`, coordinator `35ab3ad` + `e3d933c`). Narrow layout used
  `#reviewdoc { height:60vh }` — a fraction of the WINDOW, not of the room under the chrome. Now reuses
  fitReview's measured `--rvh`. Verified on six real artifacts: dead space **203 -> 16px**, frame
  672..708 depending on title wrap; desktop unchanged at 40px. **The fold constant took three goes and
  each wrong value was optimistic**: 706 (the top of the range), then 691 (the floor measured in a
  worktree), finally **670** (the floor on his real target, where the project name `ud-dreamwork` is
  longer than the worktree's `frame` and wraps the title one line further). Now held by `devoverlay`
  measuring the real corpus in the real chrome, red-proved

- **#433** — the artifact rail's identity crumb cannot shrink, and fixing it re-stamps 23 artifacts
  of which 12 cannot be rebuilt · P3 · Web UI/review-artifacts · origin: **loop**
  · **found by looking at the rendered page, 2026-07-28 18:50 — every mechanical check passed while the
  rail was visibly broken**
  · `review-artifact.template.html` styles `.identity b` as `white-space:nowrap` with **no**
  `overflow:hidden` or `text-overflow:ellipsis`, while its own sibling `.identity span` has both. So a
  long identity cannot shrink and collides with the nav chips instead. **The sibling proves the intent**
  · **the fix is one declaration and it is verified**: adding `overflow:hidden;text-overflow:ellipsis;
  min-width:0` to `.identity b` removes the overlap at 390x844 and 1280x900, tested by injecting it at
  runtime, and the text still renders in full because ellipsis only engages when it must
  · **but the blast radius is the reason this is a task and not a commit.** The build stamp is derived
  from the template's hash, so touching it marks **all 23** artifacts `stale` and takes `lint` from 1
  warning to **12**. Only **11 have a `src/`**; the other 12 — `do-now-urgency-treatment`,
  `explore-command-contract`, `goal-hierarchies`, `hub-public-auth`, `lan-bind-threat-model`,
  `protected-service-boundary-288`, `review-datetime-order`, `task-origin-contract`, `tasks-page`,
  `threaded-topic-chats`, `threaded-topic-chats-v2`, `ud-dreamtask` — **cannot be rebuilt at all**, so
  the warnings would be permanent. `review_artifact.py`'s docstring already calls migrating them *"a
  separate call, deliberately"*
  · so: do this **with** the untemplated migration, or not yet. Measured and reverted rather than landed
  · scope today was limited to the one artifact on his desk: `263`'s crumb shortened from 56 to 20
  characters, overflow 440px->390px in a 356px bar. **One overlap survives that**, which is why the
  template half is real
  · related: **#325, #429, #436**
  · **landed `2ade390`** (glm52 lane `9d9c41b`, `46f90dd`). `.identity b` gained the
  `overflow:hidden;text-overflow:ellipsis;min-width:0` trio its sibling one declaration away already
  carried. Lane chose **(a)** and refused all 12 untemplated migrations with per-file evidence — 12
  distinct hand-rolled stylesheets, none matching the template, 4 with no `<header>`. Correct, and it
  refused exactly where the brief said to
  · **verified independently**: zero pairwise leaf overlaps across all 13 railed artifacts at both
  viewports; red-proved on the SHIPPED artifacts by stripping the three declarations at runtime, 0 -> 1
  overlap with the exact pairs named, and a zero-hit injection made fatal because an injection that
  never lands looks identical to a fix that works. Diff is 4 lines per artifact: three copies of the
  template stamp and the one CSS rule, not one prose word
  · **the brief was wrong twice and the lane caught both.** My criterion "compare the rail's
  `scrollWidth` against its client width" is **blind to this bug** — `railOverflow` was false in every
  case before and after, because the collision is intra-rail; confirmed in my own probe. And (a) does
  not leave lint noisy: lint is silent on `untemplated` by design, so the 12 were never stale
  · **it also improved on the brief's red-first demand.** No single declaration's removal fails the
  check, because `overflow:hidden` and `min-width:0` are redundant routes to the same shrink. Naming
  that, instead of inventing a single culprit to satisfy the instruction, is the discipline working

- **#435** — the `--dev` perf overlay draws text on top of the wordmark · P3 · Web UI/dashboard ·
  origin: **loop** · **seen in a screenshot, then measured, 2026-07-28 19:14**
  · At **1280x900** the overlay's third line — `683.3ms avg · 1233.3ms worst`, spanning `1079..1267` at
  `y38..52` — overlaps the **`ud-dreamwork` wordmark** (`1149..1264`, `y43..64`) by **115x9px**. Text on
  text. Mobile is clear: the overlay ends at `y52` and the wordmark starts at `y51` in a disjoint column
  · **he sees it**, which is the only reason it is filed at all: `just deploy` starts the server with
  `--dev`, so the overlay is not a developer-only artifact of local runs. Either the overlay reserves its
  own space, or the wordmark yields, or `deploy` stops passing `--dev` — **that last one is a question
  for him, not a call for the loop**, because the fps counter on his own dashboard may be wanted
  · cosmetic and bounded — 9px of vertical collision on one label in one mode. Filed so it is not
  rediscovered, not because it is urgent
  · **worth noting how nearly it was missed**: my first probe searched for an element whose text matched
  `/fps/` and hit a `<script>` tag containing those letters, whose rect is `0x0` — so it reported
  *"overlap: none"*, a false negative, on a collision plainly visible in the screenshot. Fixed by
  requiring the element to actually render (`width>2 && height>2`, tag not in `SCRIPT/STYLE/...`).
  **Fourth instance today of an assertion aimed at the wrong element**, and the first one caught in
  under a minute because the pattern is now named
  · related: **#434**
  · **landed `5abc4c1`** (grok lane `bfc3222`). Overlay third line painted across the wordmark at
  1280x900. Fixed by the **wordmark yielding** (`body.dev .hproj` margin-right), not by removing the
  counter — whether he wants the counter is his call and was never this task's to make. Zero overlapping
  pairs at both viewports with a rendering precondition on every pair

- **#425** — the `watch.py` split must leave `watch.py` working for clients that are already running ·
  P1 · loop-tooling/migration · origin: **human** · **human direct, 2026-07-28 17:38** · next-up ·
  blocks **#368**
  · verbatim: *"when we migrate watch.py to something more maintanable, we should keep a copy of the
  monolithic script in like `deprecated/watch.py` but symlink `watch.py` in the main dir so clients
  won't break if the files on disk are updated before the new skill is rerun and things are properly
  updated."*
  · **so this is a constraint on `#368`, not a task after it.** The split cannot simply move code out
  of `watch.py` and leave a smaller `watch.py` behind: the path itself has to keep working for a
  **process that started before the split landed** and for tooling that names it. `deprecated/watch.py`
  holds the monolith; `watch.py` becomes a symlink to it until the new entry point is proven and the
  skill has been rerun
  · **it is timely to the hour**: `#263`'s open ask (Q3) asks him whether `#368` lands before lane E
  starts. If he says split-first, **this is the first increment of that split**, and the ask should say
  so — folded into that entry
  · what to check, since a symlink is the kind of thing that works until it does not: does
  `python3 watch.py` behave identically through the symlink; does the port file, `--target` resolution
  and `__file__`-relative path handling still resolve (a monolith that computes paths from `__file__`
  sees the **symlink target's** directory under some invocations); does `just test` still find its
  guards; and does an **already-running** server survive the swap without its next tick failing
  · **MEASURED BLOCKER, 2026-07-28 18:24 — the symlink as specified takes his dashboard down on the
  next `just deploy`, and the recipe's own safety check waves it through.** The recipe does
  `git show HEAD:watch.py > "$snap"` and then `ast.parse` on the snapshot. **Git stores a symlink as a
  blob whose content is the target path**, verified in a scratch repo: `git show HEAD:watch.py` prints
  `deprecated/watch.py` and the index mode is `120000`. And **`ast.parse("deprecated/watch.py")` parses
  clean** — it is a valid expression, `deprecated / watch.py`, a division with an attribute access. So
  the syntax guard that exists precisely to catch a broken snapshot **passes on a 19-byte file that is
  not a server**
  · the failure order is what makes it bite: `pkill` kills the working server **first**, then the
  garbage snapshot is written, passes `ast.parse`, is started, dies on import, and only the final
  `curl` notices — so the recipe correctly reports *"deploy failed"* **with his dashboard already down
  and staying down**. (`./deprecated/watch.py` as a target would at least fail `ast.parse`, but relying
  on that is relying on a syntax accident)
  · so `#425` must fix the **deploy path** too, not only the tree: resolve the link before snapshotting
  (`git show HEAD:$(git symlink target)`) or, better, stop snapshotting a single file — after `#368`
  the dashboard is a package and `deploy` has to copy a tree. **Whichever way, the `ast.parse` guard
  needs to assert the snapshot is a module that defines the server**, not merely that it parses; a
  syntax check that passes on a path string is measuring the wrong property
  · related: **#368, #426, #431**
  · **→ folded 2026-07-28 19:07 — landed `cf452d2` + `51729f4`.** The safety net exists and the
  measured blocker is closed: `deploy` resolves a symlinked `watch.py` through `git ls-tree` and proves
  the snapshot **is** the server (top-level `main` + `GENERATION`) **before** `pkill`, so a broken link
  is now refused with his dashboard still running rather than after it is dark. Verified independently
  in a scratch clone with a real symlink: the blob is 19 bytes, a bare `ast.parse` accepts it, the
  resolver emits the real 500,807-byte module, and the guard refuses the blob and a truncated module
  both. `dev/deploy_state.py` and the recipe share one resolver so they cannot drift. Procedure in
  `.dreamwork/docs/migrate-watch-symlink.md`
  · **the symlink itself is NOT created, deliberately** — his sentence opens *"when we migrate"*, and
  the migration is `#368`, behind his open `#263` Q3. So this stays `#368`'s first increment and the
  net is in place for it. `watch.py` is still mode 100755 and `deprecated/` does not exist

- **#429** — the above-fold criterion we put in every review brief is unenforceable on 20 of 22
  artifacts · P1 · loop-tooling/review-artifacts · origin: **loop** · **measured, 2026-07-28 17:52**
  · Every brief that asks him to rule says the ask must satisfy
  `getBoundingClientRect().bottom < innerHeight`. **`#ask` exists on 2 of 22 built artifacts.** On the
  other 20 the criterion cannot be evaluated at all, so it has been silently unenforced since it was
  written — a lane either invented the id, or didn't, and nothing noticed either way
  · **the two that have it disagree about the answer, which is the useful part.**
  `421-question-options` passes (`ask.top` 218 desktop / 266 mobile) because it puts the ask **inside
  the hero**; `263-second-gate` fails (594 / **1006**) because it puts the ask after the hero. So the
  working pattern already exists in the corpus and is undocumented
  · **the criterion's letter is also wrong for a multi-question ask.** 263's `#ask` is 870px tall
  because it holds three decisions; `bottom < innerHeight` is unachievable for it at any viewport and
  demanding it would mean splitting a coherent decision block. The measurable intent is *the ask
  **starts** above the fold and its first decision is readable* — `top < innerHeight`, plus the first
  sub-decision's `top < innerHeight`
  · so: make `#ask` a documented required element in `file-formats.md` / the artifact template, restate
  the criterion as above in `watch-design.md`, and give it **one shared checker** instead of each lane
  writing its own mjs
  · related: **#430, #325, #432, #433, #436**
  · **→ folded 2026-07-28 18:21 — landed `1dd973f` + `a54d162`.** The defect as stated is closed:
  the criterion is restated to something satisfiable (`top < innerHeight` for the block *and* its
  first decision, not `bottom < innerHeight` for a 870px three-decision block), it has one shared
  checker instead of a per-lane copy, and the single artifact that failed it now passes at 188/266.
  **What is NOT done is the retrofit**, and it is deliberately a separate increment: 19 artifacts
  still carry no `#ask`, so the checker cannot speak about them. That is `#432`

- **#430** — a viewport-setting check must assert the viewport was applied, because mine didn't · P1 ·
  loop-tooling/verification · origin: **loop** · **caught in my own hands, 2026-07-28 17:47**
  · I measured the `#263` artifact with `newPage({viewportSize:…})`. Playwright's option is
  **`viewport`**; `viewportSize` is accepted silently and ignored, so both "desktop 1280×900" and
  "mobile 390×844" runs were the **default 1280×720**. The tell was that they agreed to the byte —
  identical `scrollHeight` for a 1280px and a 390px render, which is impossible for a responsive page.
  Had the page happened to pass at 720, I would have reported two viewports verified and checked one
  · **this is the hollow-check failure with a new cause: not a bad assertion, a bad harness.** The
  assertion was right and it was applied to the wrong page. `.dreamwork/lessons.md` already says a
  check must assert its own preconditions; the precondition of *every* responsive measurement is
  **`innerWidth === requested`**, and no check in this repo asserts it
  · so: one `dev/capture/above_fold.mjs` (or similar) that takes ids + viewports, asserts
  `innerWidth`/`innerHeight` match the request before measuring anything, and is the only thing briefs
  cite. Kills the per-lane ad-hoc copy that produced this
  · **narrowed after measuring, 17:58 — the live bug is mine alone and the repo is clean of it.**
  `dev/capture/` holds 65 scripts, 60 of which set a viewport, and **none** uses the wrong
  `viewportSize` key. So this is not a defect in the tree; it is a missing precondition — **2 of 65
  assert `innerWidth` matches what they asked for.** The repo is one typo away from the failure, not
  living in it, which lowers the urgency and does not change the fix
  · related: **#429, #432, #434**
  · **→ folded 2026-07-28 18:14 — landed `1dd973f`.** The shared checker exists with all three
  preconditions red-proved, and is declared a tool rather than a guard in `lint.NOT_GUARDS` with the
  reason it gates nothing yet. Making it *gate* the corpus needs `#ask` to be a contract first, which
  is `#429` and stays open

- **#218** — Add filed-to-landed median · P2 · task · 20m ·
  origin: **loop** · blocked on #217 · `ledger_series` already computes
  arrival/landing pairs and discards them; render the median without a
  velocity score after provenance work
  · **UNBLOCKED — `#217` LANDED and nobody re-triaged this** (found by `#420`'s census, machine-verified against `parse_ledger`, re-verified by the coordinator 2026-07-28 15:53): filed-to-landed median over `ledger_series`; the provenance work it needed landed. **Startable now.** This entry is one of **ten** with the same shape, which is why the census was worth running: a blocker that clears is invisible from the blocked side, so nothing ever re-reads it
  · **IN PROGRESS 2026-07-28 16:33** — `ccc @glm52`, `.worktrees/218`, brief
  `.dreamwork/docs/briefs/218-filed-to-landed-median.md`, owns `watch.py`, `test_watch.py`,
  `watch-design.md`. Two things the brief makes non-optional: the population is the
  **intersection** of arrived and landed, so the figure answers *"how long did finished work
  take"* and the still-open tail is excluded — the label carries that or the number lies quietly;
  and his *"without a velocity score"* is taken literally, no composite index. Defaulted to **copy
  rather than a mark on the chart**, because `#417` says the burndown's design is at a quality he
  does not want traded for an extra series — the lane may argue
  · **DONE, `ccc @glm52`, ~40 minutes, landed `eb02cf8` (merged 17:14).** `ledger_series` now returns
  `median` + `median_n` from the pairs it already held; **1h 26m over 191 pairs** on the live repo
  (332 arrived, 191 landed). One line of copy in the burndown panel, not a chart mark — `#417`'s
  caution quoted back, that the chart's quality is not traded for a series
  · **the label carries the honesty**: `median time finished work took to land · over N pairs`, with
  the aria-label adding that still-open work is excluded. The population is the **intersection**, so
  the figure answers *"how long did finished work take"* and cannot be misread as *"how long does
  work take"* — the 141 open ids have no duration and folding them in as zero is the bias the brief
  named
  · **my own red-proof missed first, and the miss is the lesson.** I pattern-matched the generator
  the report described; it is written across two lines, so the regex found nothing, pytest passed,
  and it read as a green. That is *the injection never reaching the code* — CLAUDE.md's named
  failure. On the real line the bug moved the median from **5201s to 537.5s** and the population from
  **191 to 332**, failing three named tests
  · took *"without a velocity score"* literally: one duration on the same `ageParts` ladder the
  commits use. No new capture guard, and it argued that rather than assuming it
  · `audit-styleguide`: 32 UI commits, **0 without an entry**

- **#419** — it must be structurally impossible to be blocked on a human decision with no question
  asking for it · **P1** · loop-integrity/format · origin: **human** · **human via watch
  `/answers` 2026-07-28 15:19**
  · verbatim: *"I cannot see any question for #264 in the webui, how am I meant to provide a
  ruling? (Note: we must have a way to do this via the webui, and we should structure things in
  such a way that it's impossible for us to be blocked on a user decision without a corresponding
  question or sometihng either pending an answer/ruling, or that question could be answered but
  waiting for processing, but yea hthere always has to be an answer in our data for these kinds of
  questions."*
  · **he found it by being unable to act, which is the worst way to find it.** At 15:02 I answered
  that ratifying `#264` was *"the only thing of this chain on your desk"* — and no `questions.md`
  entry existed for it. The design had landed at `914648c` with its artifact and the ask simply was
  never filed. So the loop reported itself blocked on him, told him so, and gave him nothing to
  rule on. The question is filed now; **this entry is the reason it cannot recur**
  · **the invariant, stated so it can be checked:** every open task whose blocker is a human
  decision has a corresponding `questions.md` entry that is either **open** (awaiting his ruling)
  or **answered-but-unfolded** (ruled, awaiting processing). Both states are legitimate; **absent
  is not.** Equivalently — *"there always has to be an answer in our data"* — a blocked-on-human
  task with no entry is a lint ERROR, not a WARN
  · **the missing half is that a task cannot currently SAY this.** Entries express it in prose
  (*"awaiting his ruling"*, *"blocked on #264 Q2"*, *"WITHHELD behind a second gate"*), and prose is
  not checkable. So this needs a machine-readable marker in `file-formats.md` — a `blocked-on:
  **human**` field, or a `gate:` naming the question — in the same commit as the check, per the
  repo's standing rule. **Design the marker before writing the check**: a check over a field nobody
  fills is the hollow-check failure one level up
  · **and the reverse direction is worth the same line, because it is the cheaper error:** an
  answered-but-unfolded entry that has sat unprocessed is also a stall he cannot see. `lint` already
  derives *"N of 51 answered entries have no resolution date"*; this is the same idiom pointed at
  fold latency
  · his *"we must have a way to do this via the webui"* is already satisfied for entries that
  exist — the dashboard's `/questions` composer answers them — so the gap is purely that the entry
  was absent, not that the surface is missing. Worth stating so nobody builds a second surface
  · **P1 because it is a loop-integrity property, not a feature**: every hour he spends unable to
  unblock work he believes he is blocking is a direct cost, and the failure is silent on both sides
  · related: **#264, #294, #289, #420**
  · **landed `0f11df5`, 2026-07-28 17:00** — direction 1 enforced, direction 2 refused and the refusal red-proved

  · **IN PROGRESS 2026-07-28 16:14** — `ccc @glm52`, `.worktrees/419`, brief
  `.dreamwork/docs/briefs/419-human-blocker-invariant.md`, owning `file-formats.md`, `lint.py`,
  `test_lint.py`. Told to **design the marker before writing the check**, because a check over a field
  nobody fills passes on every entry including the ones it exists to catch
  · its reds come from **real history**, not fixtures: `#371`'s pre-fix body at
  `git show 7c5fc82^:.dreamwork/tasks.md` is a defect that really existed, and the four
  answered-but-unprocessed entries the census found are the corpus
  · `#402b`'s id-vocabulary row is offered to the same lane as an opportunistic add, since it is in the
  same file — with permission to decline it if it grows the diff
  · **DONE, `ccc @glm52`, ~45 minutes, landed `c58edc4` (merged 17:01).** `file-formats.md` +105,
  `lint.py` +173, `test_lint.py` +214 with 12 new tests. Marker: `· blocked-on: **human** ·`, with
  `· gate: **#N** ·` when the ruling rides a neighbour's question. Direction 1 is an **ERROR** and
  quotes his own words in the message
  · **verified independently before merge**: I injected the marker onto `#416` — an open entry with
  no question — in a copy of the live ledger and lint named that entry and errored; restored, silent
  again. `test_lint.py` 277 passed. **Silent on the live repo by design** (no entry carries a marker
  yet), so it is forward-looking: the next entry that claims a human block without a question errors
  the day it is written
  · **direction 2 REFUSED, with reasons, and the refusal is the better half.** The brief handed it
  four specimens as *"he ruled and nobody processed it"* and **none is a defect**: `#371` was
  retracted by my own 16:23 amendment, `#254` is a deliberate design-only grant, `#367` is being
  built now, `#50` is authorised-but-unstarted. Then it **measured** the prose form — `blocked on
  #N` where `#N` is answered fires on **11 open entries, all 11 legitimate** task dependencies. A
  WARN that is 11 wrong and 0 right is the hollow check this repo spent a day refusing
  · **it red-proved the refusal, which I had not thought to ask for**: reintroducing the rejected
  design breaks exactly the two tests that hold the rejection. A decision *not* to build something,
  defended by a test that fails if someone builds it
  · **the finding for his desk, and it is the real answer to his 15:19 ask:** *"there always has to
  be an answer in our data"* is only **half** satisfiable from what we keep. Direction 1 is now
  enforced. Direction 2 needs a record of **authorisation** — which is what `#263`'s journal is —
  rather than an inference from which section a question sits in
  · **and it vindicates `#421`'s option B rather than refuting it.** Option B asks that an
  unanswered sub-decision be **explicitly recorded**; this lane's refusal is precisely that
  *inferring* it is impossible. The two agree, one door apart
  · **transitive coverage does NOT count** — an entry whose own id has no question errors even when
  a neighbour's question covers the decision, because a reader landing on that entry alone cannot
  find it. Same shape as the `#371` trap. Consequence: `#353` carries no marker so the check is
  silent on it; giving it one requires either its own question or `gate: **#264**`, and that is my
  call not the check's
  · declined `#402b`'s id-vocabulary row as out of its diff, correctly — the brief said to

- **#420** — a census of everything not done, because nobody has a view of 138 open entries · P2 ·
  loop-tooling/grooming · origin: **human** · **human via watch `/answers` 2026-07-28 15:25**
  · verbatim: *"at some point soon, get a glm52 node to do a complete scan over our tasks and give
  you a report on everything not done so you have a concise view on it"*
  · **IN PROGRESS 2026-07-28 15:29** — `ccc @glm52` (his named runner) in `.worktrees/420`, brief
  `.dreamwork/docs/briefs/420-open-task-census.md`, owning only
  `.dreamwork/docs/open-task-census.md` and optionally a review artifact source. **Read-only
  otherwise**, which is why it runs beside two live implementation lanes with no ownership conflict
  · **the problem is real and measurable**: `tasks.md` is over 250,000 characters with 138 open
  entries, and entries are long by design — the detail is what makes them useful individually and
  unreadable collectively. The coordinator selects work from the part it happens to remember
  · the brief's highest-value section is **not** the summary: it is the cross-check that every entry
  whose prose says *blocked on him* has a `questions.md` entry that is open or answered-but-unfolded.
  That is `#419`'s invariant measured by hand once, before the check exists — and `#264` proves the
  failure is live rather than theoretical
  · **also asked for, because both have bitten today**: entries the ledger and reality disagree about
  (claimed open but actually done, or genuinely unstarted while a NEIGHBOUR landed and can be
  mistaken for it — `#172` is that specimen), and duplicates found by **overlapping symbol** rather
  than overlapping words, which is how `#412` escaped notice against `#331`
  · every count must be derived at runtime and shown with the test that produced it; **no literal
  counts**, since a literal is wrong the day after it is written
  · told to use `watch.parse_ledger` rather than any hand-rolled reader, with the reason: four
  hand-rolled parsers were wrong here today, including two that damaged sectioned files, against a
  file whose production parser was importable every time
  · related: **#419, #413**
  · **CLOSED `61354fb`** (lane commit `2d7e242`, `ccc @glm52`, **~14 minutes**, read-only).
  `.dreamwork/docs/open-task-census.md`
  · **it paid for itself in one section.** Ten entries said *"blocked on #N"* where `#N` is in the
  landed set — the composer cluster `#244/#242/#241` all behind a single landed `#238`, `#360`/`#276`
  behind `#233`, plus `#337`, `#333`, `#249`, `#218` and `#172`. Nine cleared in `30458af` after I
  re-verified each with `parse_ledger`; `#172` was the tenth and closed on its own. **A blocker that
  clears is invisible from the blocked side** — nothing re-reads a blocked entry — so this is a class
  the loop cannot find by working, only by scanning
  · derived headline: **139 open / 175 landed, 99 startable now**, 5 live on his desk, 24
  task-blocked, 24 at P1-or-hotter. My brief's *"138"* was already stale when it was written, which
  is the argument for the no-literal-counts rule it imposed
  · **it found `#419`'s live cost has moved to the reverse direction.** The no-question half closed
  when I filed `#419` and the `#264` ask; what remains is **answered-but-unprocessed** — `#254`,
  `#367`, `#371`, `#50`, with `#371`'s body still saying *"blocked on #263 Q2"* which he answered at
  05:43. Those four are ready-made red fixtures, and `#419`'s check must cover both directions
  · one honest ambiguity reported rather than smoothed: `#353` forbids starting without his S1/S2/S4
  ruling and **no question names `#353`**, though `Q#264` covers it transitively — *"a reader on #353
  alone cannot tell"*. Medium confidence, flagged as such
  · **a finding about the ledger itself**: the `type` token is freeform prose with **80 distinct
  spellings** across 139 entries, so any *"N bugs, M features"* summary would invent a taxonomy the
  ledger does not keep. It declined to invent one, and that is the cheaper half of the argument for
  `#346`'s strict schema
  · used only the production parsers and said so — `parse_ledger` and `ledger_entries` agree on all
  139 ids, both headings match exactly once. The brief demanded that after four hand-rolled parsers
  went wrong in one day, and the agreement line is worth having

- **#172** — Put project identity prominently in the title section · P1 ·
  implementation · 25m · **human via watch `do-next` 14:01** · show the
  target project name (`ud-dreamwork` here) in a materially more prominent
  position within the visible title section; queued immediately after #217
  because both modify the dashboard shell/CSS · keep the earlier invariant
  principle: **anchor what is invariant to an edge, not to a variable-width
  neighbour** — the route title varies while repo identity does not, so the
  identity must not be shoved about by unrelated route changes · document the
  rule in `watch-design.md`; deterministic desktop/mobile captures and
  visual-review-and-fix convergence required · do not infer first-sight
  provenance from this later human priority update (#216) · #153's browser-tab
  title remains related but does not broaden this visible-title increment ·
  **read his references first**: `grok-build`, `codename-thin` at
  `ssh://x-game:src/codename-thin`, on another machine  · **NEXT-UP, human via watch `do-next` 2026-07-28 15:13**, and the tone is earned: *"we have
  several tasks about putting hte project name in the title line. This has been delayed too long.
  it's essential and basic. Dispatch a subagent to solve this problem ASAP. (I thought we already
  did last night but it is still unimplemented)"*
  · **IN PROGRESS 2026-07-28 15:17** (next-up mark cleared on start) — `ccc @grok` in
  `.worktrees/172`, brief `.dreamwork/docs/briefs/172-project-identity-in-title.md`, owning
  `watch.py`, `watch-design.md`, a new `dev/capture` guard, the `justfile` DEFAULT_GUARDS line and
  `test_watch.py`. Routed to grok for vision: the acceptance includes its own verdict on whether
  the identity reads as *prominent* rather than merely present
  · **measured before briefing, and it is smaller than "delayed too long" suggests**: `/data.json`
  already carries `target`, so nothing needs plumbing — and **`popoutShell` already renders
  `basename + full path` for every popped-out window**. The popouts have project identity and the
  main window does not, so the idiom exists in the same file and this is a display change
  · **his constraint is the substance and is now checkable**: *"anchor what is invariant to an edge,
  not to a variable-width neighbour"*. Criterion 1 is the identity element's `getBoundingClientRect`
  on three routes including a long `/review?p=…` param, asserted **identical** — a layout that looks
  right on the dashboard and slides on a long route passes a screenshot and fails his rule
  · **a correction I owe this entry**: while briefing I asserted `#172` had been filed under
  `## Recently landed` without a closing marker — that a P1 had been falsely marked done. **False.**
  It has been open and unstarted, which is the honest and less flattering account. The error came
  from splitting `tasks.md` on an **unanchored** `## Recently landed`, which matches a prose mention
  147k characters early; `parse_ledger` disagreed the moment I asked it. Corrected in the brief in
  place, left visible there
  · his *"I thought we already did last night"* is worth taking as data regardless: `#153`
  (browser-tab title) and `#318` (`TITLE_ROUTE`'s route omission) both landed last night and both
  touch the title, so **title work did land — just not the half he can see**. That is exactly how a
  neighbouring landing reads as the wrong thing being done
  · **CLOSED `775022d`** (lane commit `33284c2`, `ccc @grok`, ~24 minutes from an urgent dispatch).
  `#hproj` is a sibling of `#htitle`, pinned with `margin-left:auto` + `.htitle { flex: 1 }`;
  basename at heading size and `--bright` so it reads as identity rather than a breadcrumb; **full
  path on `title=` only**, because two checkouts share a basename and a full path in the bar is what
  `#284` ruled out. `watch-design.md` gained its section in the same commit
  · **his constraint is verified, not eyeballed** — the identity box is byte-identical on `/` and
  `/questions` (730.39, 43.09, 96.02×21) and `trailGap` stays **0** on a long `/review` route where
  the bar itself widens. Route ink widths were 144 / 86 / 626, so the shove his rule forbids had room
  to show
  · guard `dev/capture/projtitle.mjs` registered in `DEFAULT_GUARDS`, red-proved from a `cp` snapshot
  by forcing `#hproj` empty: six named assertions fail, one of which is *"identity has a real painted
  box (else same-box is vacuous)"* — the precondition that stops a same-box check passing on a blank
  element, which is this repo's standing failure and the lane added it unprompted
  · **it refuted my brief, the eighth lane today to do so, and this one is instructive.** I wrote
  *"the tab title has no project identity"*. False — `titleWho` has emitted `dreamwork/<project>`
  since `#153` landed last night. **I had curled the served HTML, read `<title>dreamwork watch</title>`
  and called that the tab title**; it is the static shell before any JS runs. Measuring the thing
  adjacent to the thing I cared about, one more time
  · **and that is the answer to his *"I thought we already did last night"*:** `#153` put the name in
  the tab, where he saw it, and the visible bar is what was missing. His recollection was right about
  the evidence he had
  · it also surfaced a red on master that was mine — an unfolded `#367` hand-off failing
  `test_lint.py::TestHandoffs` — and correctly declined to fix it as out of scope; fixed in `090ecd0`
  · reference repos `grok-build` / `codename-thin` at `ssh://x-game:…` were unreachable and were
  treated as optional per the brief, as intended

- **#408** — `CLAUDE.md` documents a `GIT_OPTIONAL_LOCKS` mitigation that is **not in place**, so
  every Claude session takes real index locks · P2 · system/mitigation-drift · origin: **loop** ·
  found while testing **#283**'s closing condition, not by looking for it
  · `~/CLAUDE.md`'s git-index-lock entry states: *"`~/.claude/settings.json` env sets
  `GIT_OPTIONAL_LOCKS=0` for all Claude sessions"*. **Measured: it is not there.** `settings.json`'s
  `env` keys are `API_TIMEOUT_MS`, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`, `DISABLE_AUTOUPDATER`,
  three `x`-prefixed (disabled) keys, and `CLAUDE_CODE_AUTO_COMPACT_WINDOW`. No `GIT_OPTIONAL_LOCKS`
  · **confirmed from the other end too**, which matters because a value could arrive by another
  route: `echo $GIT_OPTIONAL_LOCKS` in this session prints nothing. It is genuinely unset
  · **so the mitigation's own stated purpose is unmet for the noisiest git client on the box.**
  Today's watcher log shows **6,093** lock events in this checkout — this session runs `git`,
  `lint.py` and `status_sync.py` many times per tick, and every one takes a **real** `.git/index.lock`
  rather than skipping it. `#283` was opened because that class of churn blocked a commit
  · **two honest resolutions and they are not equivalent.** Either the setting is added — which
  **`CLAUDE.md` says requires his consent**, so it is asked rather than done — or `CLAUDE.md` stops
  claiming it. **Doing neither is the only wrong answer**, because a documented mitigation that is
  absent is worse than no mitigation: the next investigation will rule it out as a cause
  · **the class, which is why this is worth an entry rather than a fix:** a mitigation record is a
  claim about system state, and nothing re-checks it. The fish-function half **is** in place
  (verified) and the systemd watcher **is** active (verified) — so this entry drifted alone, and
  reading the paragraph would never have revealed which third of it was false
  · rec: **audit every mitigation bullet in `CLAUDE.md` the same way** — each names a file or a unit,
  so each is checkable in one line. Doing it once and writing down what held is cheap; three were
  checked here and one failed
  · related: **#283, #416**
  · **ANSWERED "yes" 2026-07-28 14:48, and applied.** `~/.claude/settings.json`'s `env` gained
  `"GIT_OPTIONAL_LOCKS": "0"` — a one-key diff, nothing reformatted — verified by re-reading the
  file as JSON rather than by the write returning success. **It binds new Claude sessions, not
  this one**, so this session keeps taking real index locks until it restarts; the 6,093 figure
  will not move today, and that is expected rather than a failed fix
  · `~/CLAUDE.md` needed no edit: the paragraph that was false is now true as written. Closing the
  drift by making the claim accurate was available only because he said yes — had he said no, the
  same entry would have closed by deleting the sentence, and the two are equally honest
  · the audit half of the rec is `#416`, filed rather than folded into this closure: it applies to
  four bullets this entry never touched, and one of the three checked here was already false


- **#410** — `ccc @grok` is 401 and has been silently eating lanes: two died at three seconds
  with nothing in the tree · **P1** · dogfood/orchestration · origin: **loop** · found by capturing
  a lane's stderr after the second death
  · **the error, verbatim:** `Unauthorized (401) from https://cli-chat-proxy.grok.com/v1/responses:
  Invalid or expired credentials (auth_kind=none, x_xai_token_auth=xai-grok-cli, upstream=
  Unauthenticated, reason=no auth context)`, `Model: grok-4.5`, ccc version `0.2.112`
  · **`ccc @glm52` is ALIVE** and answered a probe immediately. It routes through the same runner
  binary (the warning still says `runner "grok"`) but on a model whose auth works, so this is a
  per-model credential failure, not the CLI being down. `#399b` was re-dispatched to it
  · **the reason this cost two lanes and forty minutes is mine, and it is the general lesson.** I
  dispatched with `> /dev/null 2>&1`, so the 401 went to a discarded stderr and a lane that died
  before its first token was indistinguishable from one that ran and reported nothing. I diagnosed
  the FIRST death as a mystery and re-dispatched into the same wall
  · **and ccc's own run log does not save you:** `~/.local/state/cc-w/ccc/runs/<run>/` exists and
  holds `output.txt` and `transcript.txt`, but for a 401 death **both are zero bytes**. The error is
  on stderr only. So the dispatch recipe must redirect stderr to a file the coordinator can read —
  `> "$LOG" 2>&1` — and that is now the recipe
  · **CORRECTED 11:12 — "the fleet is one runner deep" was backwards.** `grok models` now returns
  **twelve** models and `Default model: llmp-glm-5-2`; at 05:52 it returned `grok-4.5` alone, which
  is why the dogfood doc recorded `@glm52` as *"BROKEN — cannot work"*. `llmp` became reachable
  through the grok CLI during the day with no config change, so the fleet got **wider** during the
  outage. One model of twelve is out, not half the fleet
  · **the routing table's strongest claim was its least true one.** *"BROKEN — cannot work"* had a
  shelf life of five hours, and I lost two lanes to the row beside it. A routing verdict is a
  measurement with a timestamp — anything saying *cannot* gets re-probed before it is believed, and
  `grok models` costs one second. The table now carries both timestamps rather than one verdict
  · **owed to him, since he asked which providers work for us:** only he can refresh the `grok-4.5`
  credential. Not urgent now that eleven other models answer; filed rather than attempted
  · related: **#402, #423**
  · **ANSWERED 2026-07-28 14:48: *"ccc @grok now working again"* — he refreshed the xAI key.**
  Probed before believing it: `ccc --yolo @grok` returned *"PROBE OK, Grok 4.5"* at 14:50. This
  entry's own lesson is that a routing verdict is a measurement with a timestamp, so accepting
  *"it works now"* unprobed would have been the same mistake pointing the other way
  · **what it cost, stated plainly because it is half of what he set me to find out:** from 05:52
  to 14:50 the fleet was one alias. Every comparison recorded in that window is **one runner
  measured repeatedly**, not two runners compared, and the dogfood doc now says so rather than
  implying a breadth it did not have
  · the `llmp-*` fleet stays reachable as a fallback and needs no decision from him


- **#411** — two answered entries carry a perfectly good date and the page throws it away, because
  `answered_at` anchors at position 0 · **P2** · UI correctness / parser · origin: **loop** · found
  while checking a stray note that said "6 of 49"; the note was right and the cause was not
  · **`answered_at(body)` is `RESOLVED_AT.match(body)`** — `.match`, so the resolution head must be
  the FIRST thing in the body. Measured on the live file: **6 of 49** answered entries return
  `None`, and they are **not one fault, they are three**:
    - **2 are a real bug.** `#233 LAN binding` and `#229 threaded topic chats` both begin with an
      artifact-pointer line and carry the head on the SECOND line — `The threat-model review is at`
      then `→ answered (2026-07-26 17:49): …`. The timestamp is present, unambiguous, and dropped
      for a purely positional reason.
    - **2 are honest.** `#194` and the dreamhub-URL-space ask were *withdrawn* — `→ decided by the
      loop, and withdrawn as an ask` carries no timestamp because there was no answer. `None` is
      correct and the docstring earns it: *"a wrong date is worse than no date."*
    - **2 predate the convention** (`Four early asks`, and the user-event-journal grant whose body
      opens mid-sentence). History, not a defect.
  · **the page confirms the count from the other side, which is why this is worth believing:** the
  deployed `/questions` renders **43** `span.qwhen` stamps against **49** answered entries. 49−43=6.
  Two independent instruments, same six — the parse count is not measuring itself
  · **the fix is NOT `.search`.** That is the trap this ledger has paid for twice today: I split
  `tasks.md` on the literal `## Recently landed` an hour ago and hit a PROSE mention on line 355,
  and `#399` exists because mention-scanning read `related:` markers as landings. A `→ answered (…)`
  quoted deeper in a body would become that entry's date. **Line-anchored, and only within the head
  block** (before the first blank line) — same discipline as `ALSO_LANDED_MARKER` being
  field-anchored
  · **the silence is the actual defect, and it outlives whichever fix is chosen.** Two entries lose
  a date they own and nothing anywhere says so. Wanted either way: a `lint.py` line reporting how
  many answered entries have no parseable resolution date, with the withdrawn ones distinguished
  from the unparseable ones — a count cannot silently stop counting. **Derive it; never pin 6**
  · decide, and say which: widen the parser to a head *block*, or declare the two entries malformed
  and correct the file. The second is smaller and `file-formats.md` already claims the head is
  prefixed to the body — but it makes a hand-authored ordering load-bearing with nothing enforcing
  it, which is how these two got written in the first place
  · **`watch.py` is owned by the `#399b` lane right now** — do not dispatch this into that file
  until it merges
  · related: **#399, #340, #467**
  · **MEASURED 13:08 before writing any brief, and the recorded fix direction is INSUFFICIENT
  as stated.** `RESOLVED_AT` is `\A\s*→[^:]*?\((\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?\s*\)`
  — it begins with **`\A`**, so `.search` is **identical** to `.match` here and swapping them
  changes nothing. This entry says the fix "must be line-anchored, not `.search`", which is right
  about the destination and would still have sent a lane to a no-op if it read the second half as
  the instruction. The real edit is `\A` → `^` **with `re.M`**, then `.search`
  · **the population, derived not assumed**: 49 answered entries, **6** had no date. Under a
  line-anchored pattern **2 recover** — `#233 LAN binding` (2026-07-26 17:49) and `#229 threaded
  topic chats` (2026-07-26 17:11), both of which carry the marker on the SECOND body line because
  an artifact link precedes it — and **0 of the 43 that already have a date change**. That last
  number is the one that makes the change safe, and it is the one a lane will not think to check
  · **a third was not a parser bug at all and is already fixed** (`46de3da`): his 05:43 entry
  had its title truncated after `journal:` and its closing `**` dropped while I folded it, so the
  `**` opening his answer closed the title and swallowed the whole `→ answered (…)` marker into
  it. The date was not lost, it was **misfiled**, and the page was showing a question he never
  asked. So the count is now **5** with no date
  · **the remaining 5 are honest** and must stay `None`: `#194` and the dreamhub-URL-space ask
  were *withdrawn* (no answer, so no timestamp), and the rest predate the marker convention.
  **A fix that gives them a date is wrong** — this is why `answered_at`'s docstring says it never
  guesses, and any lane touching it should be told so
  · so the brief writes itself and it is small: change the anchor, keep the never-guess rule, and
  **assert both directions** — the 2 recover AND the 43 are byte-identical before and after.
  Derive the 43 at runtime; a literal is a check with an expiry date
  · **LANDED `54c68e8` + `25a3fe4`, merged `1f01a95` (2026-07-28 14:28), by a `ccc @glm52` lane.**
  `RESOLVED_AT`'s anchor `\A` → `^` with `re.M`, then `.search`; the rest of the pattern
  byte-for-byte. `#233 LAN binding` (2026-07-26 17:49) and `#229 threaded topic chats` (17:11)
  recover the date they own; **44 dated entries byte-identical**; None 5 → 3, and the three
  that remain are correct — two withdrawn asks and one pre-convention entry
  · plus a **derived** lint count naming the undated entries, WARN not ERROR because a `None`
  naming a withdrawn ask is right and an ERROR on a legitimate state teaches the reader to mute
  · **verified against a gate built before the lane reported, red-proved in THREE directions**:
  narrow fails the recoveries, over-greedy fails a bait probe, correct passes both
  · **THE BRIEF WAS WRONG THREE TIMES AND THE LANE CAUGHT ALL THREE.** It said 43 dated (44);
  its prose said *"5 of 49 must still return None"* while its own criteria said 5 → 3 — flatly
  contradictory; and it said three entries predate the convention when **one** does. The lane
  followed the measurable criteria, which were right, and reported the prose rather than
  quietly picking one. I re-derived all three afterwards: **the lane is correct on every one**
  · **and it declined a red it could have claimed.** Red-proof 2 was framed as *"the
  withdrawn-entries test fails"*; those bodies contain no date at all, so dropping the `→`
  requirement cannot manufacture one for them. It said so and pointed at the case that does
  discriminate. **That is the identical hollowness my own gate hit** — independently found, by
  the party with the least incentive to find it
  · residual: none. `#415` (hand-off grammar allows one sha, this landed in two) was filed
  while folding this and is unrelated to the fix

- **#331** — One shared notion of "an ids-only bold span", instead of a fourth
  one-separator patch · P2 · correctness/refactor · origin: **loop** · from #327's
  drift review, challenged by the coordinator, then substantiated and re-measured ·
  `LEDGER_COMBINED_MENTION` (`watch.py:6450`) is `\*\*(#\d+(?:/#\d+)*)\*\*` — `/`
  only — while `_landed_ids` runs it over the WHOLE landed section because, in
  `watch.py`'s own words (`6337-6339`), *"in `## Recently landed` an id is named
  inline, in prose, so the entry-head shape does not apply there"* · so the landed
  reader is already the prose/mention reader by design, and it declines these spans
  purely on **joiner width** · **the number is 19 and nothing is recovered** —
  corrected from the 12 this entry was originally filed with: `#77 #102 #104 #106
  #107 #108 #109 #110 #116 #121 #123 #132 #141 #149 #151 #154 #157 #222 #223`, in
  seven space-joined spans (`**#121 #123**` `**#104 #77**` `**#109 #116**`
  `**#107 #108 #110**` `**#102 #106**` `**#141 #149**` `**#132 #151 #154**`) and one
  `+`-joined (`**#157 + #222 + #223**`) · **coordinator-verified independently at
  `04b9e00`**: all 19 are in NEITHER `parse_ledger` set, tested per id rather than by
  re-deriving the spans — a first attempt to re-collect the spans with a quick bold
  regex disagreed (it said 9), and per-id set membership is the authoritative test,
  not any second regex · `#96` is NOT among them: its only span is `**#96 stage 1**`,
  which is prose and must stay inert · net and gross are the SAME number, so the
  entry's original "gross 19, some recovered from other single mentions" was wrong
  and is withdrawn · **reported by #327 and NOT re-verified here** (it needs a walk
  over 295 ledger revisions): none of the 19 was in a landed set at any revision, so
  history does not recover them, and closing the gap moves ever-landed 117 → 136 ·
  **the point of this task is NOT to add `[ /+]` to a third regex.** #301 widened the
  landed reader, #315 widened the open readers and `LEDGER_ID` together, and this is
  the same defect at a third door — three patches one separator at a time, each
  correct, each leaving the next · so: one shared definition of an ids-only bold span
  that every reader consumes, with the existing pinning test extended to hold them to
  it, exactly as `test_ledger_entry_rule_has_exactly_one_copy` already holds two ·
  **the hazard to respect**: `**#96 stage 1**` must stay INERT — a span is ids-only or
  it is prose, and a widening that admits trailing words would start reading section
  titles as task ids. Assert that at runtime, in the check, with `**#96 stage 1**` as
  the fixture · red-prove the 19-id case against the real ledger before and after
  · **re-verified by the coordinator 2026-07-28 12:34, on today's ledger**, after
  independently rediscovering this gap while closing `#399b` and filing it as `#412` —
  which is a **strict duplicate of this entry and is withdrawn**. #331 was already here,
  already had the right number, and already named the right fix; I did not check the
  ledger before filing. The re-derivation agrees with this entry exactly: all **19** ids
  are in NEITHER set today, and the list matches character for character
  · **today's numbers**, which have moved since this was filed: landed reads **151** and a
  correct fix gives **170**. Derive them again rather than trusting these — `#399` and
  `#399b` both changed the landed reader after this entry was written
  · **the third door is now confirmed by measurement, not just predicted.** The same
  `(?:/#\d+)*` sub-pattern is copied in three files: `watch.LEDGER_COMBINED_MENTION`,
  `lint.LEDGER_ID` and `status_sync.LEDGER_HEAD` (the last is new since this entry —
  the fourth door arrived while the task sat open, which is the entry's own argument
  made for it)
  · **red-prove both directions**, from #412: a space-joined AND a `+`-joined span land
  every id they name, AND `**#96 stage 1**` still lands nothing. One direction alone
  passes for a pattern that is simply too greedy
  · when it lands, `file-formats.md` should **state the joined form explicitly** — it
  documents `**#5/#6**` and says history packs several landings to a line, both true,
  so there is no lie to fix, but a reader can only infer the space and `+` forms
  · related: **#412**
  · **LANDED `ddc4e3e`, merged `cb476a7` (2026-07-28 13:18), by a `ccc @glm52` lane.** One
  `IDS_ONLY_SPAN` in `watch.py`; `watch.LEDGER_ENTRY` and `watch.LEDGER_COMBINED_MENTION` are
  built from it, and `lint.LEDGER_ID` / `status_sync.LEDGER_HEAD` import it instead of
  restating it — so there is no fourth copy to write wrong. `grep -rnF '#\d+(?:'` across the
  three files: **1 hit**, was 4
  · **verified by the coordinator against a gate built and red-proved BEFORE the lane reported**
  (narrow ⇒ 19-id/arithmetic/one-definition/pinning fail; deliberately over-wide ⇒ all six
  inert-span checks and the newline check fail), then re-run on the **merged** tree with the
  pre-merge sha as an explicit baseline: all 19 recovered, landed **152 → 171** exactly, open
  unchanged at 136, disjoint, every live prose span inert, all three heads the identical
  compiled rule — including `status_sync`, which nothing pinned before
  · **the lane pushed back and was right.** It refused my brief's stale claim that three guard
  failures were pre-existing on `master`, proved they reproduce at its parent `97becd9` and
  were fixed on `master` by `7007d5b`+`e15b0c0`, and declined to chase them. I had moved the
  baseline under it mid-run; that is recorded as a lesson
  · residual: none. `#412` was withdrawn into this task and is closed with it

- **#412** — withdrawn as a duplicate of `#331`, not implemented · P2 · parser/burndown ·
  origin: **loop** · filed 2026-07-28 12:0x while closing `#399b`, withdrawn 12:34 the same hour
  · I found the space-separated gap by running #399b's merge gate against the lane's tip, measured
  it at 16 ids, and filed it as new work. It is not new: **#331** has carried it since #327's drift
  review, with **19** ids (I missed the `+`-joined `**#157 + #222 + #223**` span entirely), a
  coordinator verification at `04b9e00`, and a better fix than mine
  · **#331 explicitly forbids the fix #412 prescribed.** I wrote *"the fix looks like
  `(?:[ /]#\d+)*`"*; #331 says, in its own words, *"the point of this task is NOT to add `[ /+]`
  to a third regex"* — because #301 widened the landed reader and #315 widened the open readers,
  and one more separator patch just moves the defect to the next door. It wants one shared
  definition every reader consumes
  · **the lesson is the filing, not the parser**: a residual discovered mid-task is exactly when
  the ledger is least likely to be consulted, and 136 open entries is far past the size where
  recognition works. Everything #412 measured was already written down. Grep the ledger for the
  symbol before filing — `LEDGER_COMBINED_MENTION` would have found #331 in one command
  · its two genuine additions are folded into #331: today's numbers (151 → 170) and the
  both-directions red-proof · related: **#331, #399**

- **#399** — any bare bolded id in a landed entry marks that task landed, so **7 open tasks are
  reported as landed** · P1 · ledger-parser/correctness · origin: **loop** · found because a lint
  WARN told me to fold **his unanswered question**
  · `watch._landed_ids` (`:7648`) takes every **ids-only bold span** anywhere in `## Recently
  landed`. Its docstring states the intent — *"`**#96 stage 1**` (a prose reference) does not land
  #96"* — and that exclusion only works when prose puts **words inside the bold**. **This ledger's
  natural voice is `filed as **#392**`**, a bare bolded id, which lands it
  · **measured: `parse_ledger` returns 7 ids in BOTH sets** — `353, 367, 378, 387, 392, 393, 394`.
  Each traced to its source: `#367` from a reciprocity marker naming it; `#393`/`#394` from *"gaps filed
  rather than absorbed: **#393** … and **#394**"*; `#353` and `#392` from `filed as **#N**`
  · **a third trap, met while writing this entry, and it is a real gap in `#395`'s fix:** `#395`
  anchored the marker pattern to line-start or a `·` separator so prose could not manufacture a
  phantom. But **quoting the marker *accurately* means quoting its separator too**, and that is
  exactly what an entry describing the marker does — this entry produced **two** phantom markers and
  a lint ERROR before it was reworded. The anchoring fix protects against casual mention and not
  against precise citation, which is the mention most likely to appear in a ledger about itself
  · **the first half is a direct tension between two checks, and obeying one corrupts the other.**
  `lint.check_related_markers` **requires** a landed entry to name its open counterpart —
  *"an entry is read alone"* — and `_landed_ids` then reads that very marker as a landing. So the
  more correctly the ledger is cross-referenced, the more open tasks are reported landed. Neither
  check is wrong alone; they share an input and disagree about what a bold id means
  · **consequence 1, which is how I found it and is the reason this is P1:** `lint` WARNed *"open
  ask names only landed task(s) #367 — fold the ask, or reopen the task"*. `#367` is **under
  `## Open`**, and its ask is the **strip-below-the-cliff question he has not answered**. The check
  instructed me to close an open question of his. A coordinator following lint would lose it
  · **consequence 2, and it closes an audit item that was left uncertain:** the dashboard audit
  (`d348122`) reported *"burndown arrived/landed per-bucket series not reproduced by open-id set
  diffs … uncertain, not filed as a hard bug"*. An inflated landed set is exactly that symptom.
  **The audit's honest non-finding was this bug** — treat it as corroboration, and re-derive the
  series once this is fixed rather than assuming
  · **rec:** a landing is claimed by an entry **HEAD**, the way `_open_ids` already works — not by a
  mention anywhere in the body. `_open_ids` reads `LEDGER_ENTRY` heads and is not affected, which is
  both the proof the shape works and the fix's model. If body mentions must keep meaning something,
  they need a distinct vocabulary, and that is a `file-formats.md` change
  · **red-first note:** the red is free and needs no fixture — assert `parse_ledger` returns
  **disjoint** sets on the **live** ledger. That assertion fails today with those 7 ids and no
  synthetic input at all. Derive the overlap at runtime; do not pin the list of 7, because it grows
  every time the ledger is cross-referenced correctly
  · blocked: `watch.py` is held by **#392a**
  · **NEXT-UP, and for a reason that is new: this defect makes the repo's own test suite RED.**
  `test_lint.py::TestLandedAsks::test_this_repo_has_no_forgotten_folds` **fails on master** —
  measured on the merged tree, **496 passed / 1 failed** — because `check_landed_asks` WARNs that the
  `#367` open ask *"names only landed task(s) #367"*, which is `_landed_ids` misreading a reciprocity
  marker. So this is not merely a misleading WARN: **`just test` does not pass**, and has not since
  `#367`'s question was filed at 07:54
  · **I missed that for hours, and the reason is worth more than the fix.** I ran `python3 lint.py`
  — exit **0**, because it is a WARN and not an ERROR — and *targeted* pytest selections
  (`-k "cutoff or grandfather or handoff"`), which never included this test. **A selection that
  excludes the failing test is indistinguishable from a green suite.** The `#401` lane ran the whole
  file and reported it in one line as "pre-existing"
  · so the acceptance criterion for whoever takes this is **`just test` green**, not "the WARN is
  gone"
  · **MERGED `8e37db3` (`3344e43`) AND NOT DONE — it traded one red for another.** `just test` is
  **still failing**, now on the **burndown guard** instead of `forgotten_folds`. Proved causally by
  bisect, not inferred: the burndown guard **PASSES at `c42af82`** (the merge's first parent) and
  **FAILS at HEAD**. Before `#399`: `forgotten_folds` red, burndown green. After: the reverse. **The
  suite has never been green today**
  · the two failing assertions are `dev/capture/burndown.mjs:183,185` — *"the head states the three
  totals it is a picture of"* and *"...a completion **GROOMED OUT** of the landed section still
  counts (#1, #2 and #3 were pruned)"*
  · **the cause, and it is the neighbour the brief failed to name.** The guard builds its own git
  history inline (`:91-107`) and writes landed entries in the **inline-mention** form —
  `**#1** landed (aaa1111).` — **not** as `- **#N**` entry heads. Under the new heads-plus-
  `also-landed:` rule those read as **zero landed ids**
  · **and that form is not the guard being unrealistic — it is the ledger's own history.**
  `ledger_series` walks **old revisions** of `tasks.md`, and the old landed shape was exactly that
  inline mention; the pre-`#399` docstring said so outright (*"an id under `## Recently landed` is
  named inline in prose … two shapes because the file has two"*). **`#399` fixed the present and
  lost the past.** A burndown that silently drops historical completions is `#136`'s failure shape —
  the chart reads as though the loop completed less than it did
  · **rec, smaller than what landed and probably right:** exclude ids that sit inside a **known
  field** (`related:`, and anything else field-anchored) rather than excluding **all** mentions.
  That kills the `#367` false landing — which was a `related:` marker — without discarding the
  historical inline form. Keep `also-landed:`; it is a good addition and costs nothing
  · **THE PREMISE IS CONFIRMED INDEPENDENTLY, and the shape of the loss is worse than "some
  entries".** Walked all **435** revisions of `.dreamwork/tasks.md`, sampling twelve, counting entry
  heads (`- **#N**`) against bold mentions in the landed section:
    heads = `- **#N**` entry heads · mentions = bold ids in the landed section
    2026-07-25 93246fe   heads=  0   mentions=  0
    2026-07-25 0fbea84   heads=  0   mentions= 24
    2026-07-26 2627df0   heads=  0   mentions= 63     <- two days, ZERO heads
    2026-07-27 4c18941   heads=  6   mentions= 71     <- the convention changes here
    2026-07-27 cab5cc7   heads= 42   mentions= 71
    2026-07-28 bb85450   heads= 86   mentions= 86
    2026-07-28 d2a9566   heads= 95   mentions=109
  **For the project's first two days the entry-head rule finds nothing at all** — not "fewer", zero.
  So post-`#399` the burndown does not merely under-count history, it renders the loop's first two
  days as **having completed nothing**, which is precisely `#136`'s failure shape and precisely what
  the guard's assertion says. The pre-`#399` docstring was not being sloppy; it was describing the
  file. **The convention changed mid-history on 2026-07-27**, so any correct reader must handle both
  forms — a fix that picks one era is a fix for half the chart
  · **and writing that table cost a lint ERROR worth one line:** I wrote it as a fenced code block,
  the fence sat at column 0, and **an unindented line silently ends a ledger entry** — so `#399`'s
  own `related:` line fell outside `#399` and four reciprocity pairs broke at once. `lint.py` caught
  it in the same breath as the commit, which is the check doing exactly its job. Tables inside an
  entry are indented lines, never fences
  · **so a fifth gate item, and it is the one the unit tests cannot fake:** after the fix, walk those
  same revisions and assert the landed count is **non-zero for the 07-25/07-26 revisions**. That is
  an assertion about real history, derived at runtime, and no fixture can satisfy it accidentally
  · **THE STRUCTURE OF THE BUG, derived independently at 11:21 so the lane's report can be judged
  against it rather than believed.** Exactly **two** callers consume the landed half of
  `parse_ledger`; the other three `lint.py` call sites discard it (`_landed`, `_`):
    - `lint.check_landed_asks` (`lint.py:791`) — reads **today's** ledger, to decide whether a human
      ask names a finished task and can be folded. A false landing **closes a question he has not
      answered**. It wants PRECISION and must fail closed.
    - `watch.ledger_series` (`watch.py:7913`) — reads **every historical revision**, for the burndown.
      A missed landing renders the loop as having achieved nothing. It wants RECALL and must fail
      open.
  **So one function serves two callers whose error preferences are opposite**, and that is the whole
  bug stated properly. `#399` optimised for precision — correct for the first caller, fatal for the
  second. It is not that the rule was "too narrow"; it is that a single rule cannot be right for both
  unless it raises precision **without** costing recall
  · **which is exactly why field-exclusion is the right shape and reverting is not.** Excluding
  `related:` removes false positives (precision up) while leaving every bare historical mention
  intact (recall unchanged). Head-only traded one for the other; mention-everything traded the other
  way. **If the lane proposes two functions instead, that is a legitimate answer** and the brief says
  so — but then each caller must be named with which one it takes, or the split just moves the
  question
  · **MY OWN RECOMMENDATION IS INSUFFICIENT, measured 11:25, and it would REINTRODUCE the P1.**
  Field-exclusion removes `related:` markers — but **six open tasks are mentioned in landed entries
  as ordinary prose, in no field at all**: `#367, #393, #399, #404, #405, #409`. Examples verbatim:
  *"gaps filed rather than absorbed: **#393**"*, *"see **#405**, which is the plan's own
  alternative"*, and — perfectly — *"(**#409**, open)"*. So a field-exclusion fix still lands
  **#367**, which is the precise false landing that made lint tell the coordinator to close his
  unanswered question. **The brief the lane is holding recommends a fix that does not work.**
  · **THE RULE THAT DOES WORK, and it came out of the data rather than out of me.** Compare the two
  populations: a genuine landing is **sentence-initial** — `**#111** answered questions collapse and
  stay findable (a8f6b7f).` — while a reference is **mid-sentence**, preceded by a word. That is
  positional anchoring, the same discipline as field anchoring, and it is what the ledger's authors
  were actually doing. Measured over the 81 contested ids, accepting only a bold ids-only span
  preceded by start-of-bullet or a sentence end:
    caught 65 of 68 genuine landings · caught **0 of 11** references · landed = **160**
    both-open-and-landed = **0** — `#399`'s win is preserved, which field-exclusion loses
  · **and the three it misses are instructive rather than damaging.** `#101` and `#97` sit in a
  comma-joined run (`**#91** composer tweaks and **#101** scrollbar styling (2026-07-25), **#97**
  durable task ledger`); `#270` follows a closing backtick. All three are cheap to add — accept
  after `, `, ` and `, and `` ` `` — and each addition should be re-measured against the false set
  rather than assumed safe
  · **a SECOND fictional-id class, found the same way as `#5`: `#501` and `#502` do not exist.**
  Next id is 412. They appear because a landed entry quotes a **test fixture** — *"Probed on a temp
  fixture: form A `related: **#501**, **#502**` → 3 ERRORs"*. The positional rule rejected both
  automatically, which is a point in its favour: **it excludes example ids without needing to know
  they are examples.** Any allowlist-of-fields approach has to enumerate this class; positional
  anchoring gets it for free
  · **THE LANE BEAT ME ON THIS, and the measurement is unambiguous (11:27, mid-run).** It found the
  same hole in my recommendation independently — *"prose references to OPEN ids in entry bodies
  (`found **#399**`, `see **#405**`, `fold (**#409**, open)`) … count-all-bare-mentions breaks
  disjointness"* — and then reached a **different discriminator than mine and a better one**:
  **column 0**. Its observation: historical inline landings are written at column 0, while every
  prose reference to an open id lives on an **indented continuation line**. Scored on the same 81
  contested ids:
    column-0 (lane) : catches **68**, false **0**, landed **163**, open∩landed **0**
    sentence-initial (mine) : catches **65**, false **0**, landed **160**, open∩landed **0**
  **The lane's rule is a strict superset of mine** — it catches everything mine does plus exactly
  the three I had identified as misses (`#97`, `#101`, `#270`) and adds no false positive. Not a
  close call; adopt the lane's rule
  · **it also refused the brief's framing where the framing was wrong.** I wrote that two callers
  want opposite things and may need two functions; the lane checked and concluded *"the two readers
  don't genuinely differ — `#399`'s strict rule under-counted the current snapshot too"*, and took
  one wide rule. That is the right answer and I had not tested it
  · **worth reconciling at review, not a conflict:** the lane reports a 149-set and 55 historical
  inline landings where I compute 163 and 68. Different counting bases or field lists. Ask which,
  and do not merge until the two numbers are explained by something other than "roughly the same"
  · **and the lane's rule is pre-verified against the guard itself, predicted before it runs.**
  Reproduced `burndown.mjs`'s fixture builder in isolation and applied column-0 to all six of its
  commits: it reads exactly the fixture's `done` list at **every step**, and the cumulative set
  across history is `1,2,3,4,5` — so **`#1`, `#2` and `#3`, which the fixture deliberately grooms
  out of the final ledger, are still counted.** That is the guard's load-bearing property and the
  assertion `#399` broke. The guard should pass; if it does not, the fix is not the rule
  · **and it corrected my scoring of its own rule, 11:29.** I measured column-0 against the **real
  ledger** and reported it as sufficient on its own. The lane checked a population I did not — the
  **existing tests** — and found `test_a_bare_bolded_id_in_a_landed_entry_is_not_landed` uses a
  one-line head carrying `related:` and `filed as` **inline at column 0**. So col0 alone does not
  exclude them and **field-exclusion remains independently load-bearing**; likewise `also-landed:`
  must be excluded from the generic pass, since `ALSO_LANDED_MARKER` counts that form separately.
  Its design is col0 **and** field-exclusion, and that is right. **My rule looked sufficient only
  because the real ledger happens to put field markers on indented lines** — a property of today's
  file, not of the format. Same discipline I keep writing into briefs, and I missed it: a
  measurement over one population is not a rule
  · **it also caught the pipefail trap unprompted** — *"the `| tail` masked the real exit code
  (exactly the trap the brief warns about)"* — re-ran to a file, and confirmed the baseline
  precisely: `forgotten_folds` **GREEN**, burndown **RED** with both named assertions failing. That
  is the brief's warning being used rather than read
  · **GATE RUN AGAINST THE LANE'S COMMITTED TIP, 11:42 — 7 of 8 pass, and the eighth is real.**
  Two commits on `wt/399b`: `d80e072` (the fix) and `8810309` (its tests). Scored:
    landed **150** (was 95 broken, 176 pre-`#399`) · open∩landed **0** · `#5`/`#501`/`#502` do not
    land · the six prose-mentioned open tasks do not land · early revisions now report
    **1, 9, 24, 26, 29, 47** landings where they reported 0 · `dev/capture/` untouched
  The burndown guard **PASSES** in isolation, real exit 0, non-piped
  · **the one residual, and it is a smaller instance of the same bug:** `LEDGER_COMBINED_MENTION`
  is `\*\*(#\d+(?:/#\d+)*)\*\*` — **slash-separated only**. The historical ledger also writes
  **space-separated** multi-id landings: `**#107 #108 #110** the travelling heading, the ghost-pinned
  width glide, the clamped opener (2026-07-25, 3f786fc)`, `**#141 #149** (2bf61da, 6099998)`,
  `**#132 #151 #154** (2c42da1)`, `**#102 #106**`, `**#104 #77**`, `**#109 #116**`. Every id after
  the first in such a span is still dropped. **Not a merge blocker** — master is red now and this
  fix recovers the bulk of history — but it is a real, named loss and it is roughly one character
  class (`(?:[ /]#\d+)*`). File as follow-up, do not hand-fix
  · **and TWO faults in my own gate, both the day's theme, both found only because I re-ran it:**
  (a) I appended the multi-id check **after** `sys.exit()`, so it never executed and the gate printed
  **GATE PASSED** — a check that cannot run reports success; (b) the gate read
  `.worktrees/399b/watch.py`, the **mutable worktree file**, while the lane was mid red-proof with
  the old behaviour injected, and scored the lane's fix at **176** — the very number it was
  injecting. **A running lane's worktree is mutable by definition; its branch tip is the artifact.**
  The gate now defaults to `git show wt/399b:watch.py` and asserts the source is non-empty
  · **THE MERGE GATE, written 11:19 BEFORE the lane reports, so it cannot be shaped by what the
  lane says it achieved.** Measured now, both parsers run against today's ledger:
    - deployed/pre-`#399` logic: **136 open, 176 landed**
    - master/post-`#399` logic: **136 open, 95 landed**
    - ids the old logic calls landed and the new one does not: **81**
    - ids the old logic reports as **both open and landed: 10** (`#367, #378, #387, #392, #393,
      #399, #404, #405, #409, #411`). New logic: **0**
  Spot-checking those 81 shows both populations are real, which is the whole tension: `**#91**
  composer tweaks and **#101** scrollbar styling (2026-07-25), **#97** durable task ledger` are
  **genuine historical landings** in the inline form, while `related: **#367**` and prose like
  *"the same question that found **#399**"* are **references**. So **176 is too high and 95 is too
  low**, and the fix must land between them.
  **Therefore the gate, and all four must hold:** `just test` green · both-open-and-landed stays
  **0** (that is `#399`'s win and must not regress) · landed count comes back **well above 95** ·
  and the burndown guard passes without its fixture being edited
  · **a neighbour NOBODY enumerated, and field-exclusion alone does not catch it: the ledger
  contains prose ABOUT id syntax, and that prose parses as ids.** `#5` is counted landed because a
  landed entry documents the shapes the parser cannot see — literally `no bold (- #5 …), no #
  (- **5** …), a different list marker (* **#5**)`. Those are *examples in a sentence*, inside no
  field at all, so excluding `related:` will not exclude them. **Check this specific id when
  reviewing the lane's work**; if `#5` still counts as landed the fix is incomplete, and if the lane
  found it independently that is a strong signal about the lane
  · **do not revert.** `8e37db3` fixed a real P1 and its tests are sound; the defect is that its
  landed-id rule is too narrow for the history walker. The follow-up is additive
  · **my error, stated plainly: I merged on `pytest` alone while `just test` was still running**,
  forty minutes after recording the lesson that a selection is not the suite. The lane's own brief
  made `just test` green the acceptance criterion and I merged without it
  · **CLOSED 2026-07-28 12:25 — merged at `0595b13`, and verified on the MERGED tree, not the
  lane's branch.** That distinction mattered: the lane's worktree carries the ledger as it was at
  `56f5871`, while `test_lint.py` reads the **real** ledger and I had rewritten it heavily all
  morning — so its own green could not have proved the merge green. Built `premerge399` = master +
  `wt/399b` and ran there: **pytest 991 passed, 57 subtests**, `lint.py` clean, **`PASS burndown`**
  · **the fix is the lane's, and it is better than the one I briefed.** I recommended excluding
  `related:` markers; that reintroduces the P1, because six OPEN tasks are named in landed entries
  as plain prose in no field at all (`see **#405**`, and literally `(**#409**, open)`). The lane
  found that independently and reached **column 0** instead — historical landings sit at column 0,
  prose cross-refs live on indented continuation lines. It then found what my scoring of its OWN
  rule had missed: existing tests put `related:`/`filed as` inline **at column 0**. Final rule is
  col0 **and** field-exclusion by name, both load-bearing, each with its own test
  · **numbers, derived by the coordinator before the lane reported:** landed **95 → 150**
  (pre-`#399` over-counted at 176); open∩landed **0**; the 07-25/07-26 revisions now report **1, 9,
  24, 26, 29, 47** landings where they reported **zero**. `#5`, `#501`, `#502` — prose about id
  syntax and a quoted test fixture, none of them real tasks — correctly do not land
  · **`just test` is exit 1 and I am not calling it green.** 48 pass, 3 fail: `qacard`,
  `docktarget`, `noteprop`. **The lane declined to claim criterion 1 and said so plainly** — worth
  more than the fix. I verified rather than accepted: run focused against master with the change
  absent, all three fail **identically, same sub-assertions**, at load 29
  · **a correction I owe the record: `master` was never fully green today.** I said the red was
  `#399`; in fact `#399` added `burndown` to an **already-failing set of three**, and my bisect ran
  only `burndown` focused so I never saw them. `qacard` is `#392`'s own bug (`#385 age text is the
  XXa YYb form`) — the format he asked for at 05:41. This merge takes master from **4 failures to
  3**
  · **one residual, filed as `#412`, not a regression:** `LEDGER_COMBINED_MENTION` is
  slash-separated only, so 7 space-separated spans naming 16 ids (`**#107 #108 #110**`) are still
  dropped — landed reads 150 where complete is 166. My brief never named the case; the lane met it
  · related: **#392, #401, #405, #411, #412**

- **#340** — His answer renders as raw prose in `## Answered`, tag showing, on more
  than half of them · **P1** · UI correctness · origin: **loop** · from #254's design
  agent, verified independently by the coordinator · in `## Answered` the parser runs
  with `lift_answer=False`, so a retained `- **Answer (via watch, …):**` sub-bullet
  falls into the entry **body** and `mdB` renders it as a `·` item with its raw author
  tag visible as text and **no `you` label** — his words lose their attribution on the
  page while looking like loop prose · **measured on the live file at `0f9d753`: 17 of
  31 answered entries** (~55%), where the agent reported 15 of 29 before tonight's four
  folds — same defect, count moves with the file, so the check must derive it at
  runtime and never pin a literal · this is the SAME visual defect as the screenshot he
  filed #254 about, on the more-travelled path, and #109 already made mis-attributed
  authorship a correctness matter rather than a cosmetic one · the fix is reportedly one
  `lift_answer` argument, which is exactly why it must not be done blind: `## Answered`
  also carries the `→ answered` resolution head that `answered_at()` reads, so lifting
  the bullet must not create a second thing able to disagree with it · red-prove with a
  real answered entry and assert at runtime that the `you` label appears AND that the
  raw tag does not
  · **STOP — this appears to be ALREADY FIXED, and I nearly dispatched a lane at it.** While
  verifying my own brief's line-number claims before dispatch, the citations proved stale after the
  `#399` merge — and re-deriving the measurement showed the defect gone. **`8009c90 fix(#340): his
  answer is a contribution, not unattributed body prose`** exists in history; this entry never cited
  it and so was never folded
  · **measured on the live file now:** `parse_answered` returns **49** answered entries, **0** with a
  raw `**Answer (via …)` tag in the body, **0** with one in a follow, and **36** whose follows carry
  an explicit `author` field (`'human'` / `'loop'`). The entry's own figure — 17 of 31, ~55% — is
  from before that commit
  · **and the fix would NOT have been the one-argument change this entry describes.** There are
  **two** `lift_answer=False` call sites for `## Answered`: `parse_answered` (`:8449`, reads
  `questions.md`, where the answer is **his**) and `parse_answered_answers` (`:8299`, reads
  `answers.md`, where it is the **loop's**). They are different channels, so the change is
  **asymmetric** — and `answers.md`'s Answered section contains **zero** `Answer (via …)` bullets,
  only `→ answered` heads. A lane doing "the one-argument fix" symmetrically would have attributed
  **loop prose to him**, which `#109` makes a correctness fault. Worse than the bug
  · **not closed yet, deliberately: the evidence is parsed-data, and the defect is about pixels.**
  Owed: look at `/questions`' Answered section on the deployed page and confirm the `you` label
  renders and no raw tag shows. Then close citing `8009c90`
  · **separately, worth a look and NOT part of this:** `answered_at` returns `None` for **6** of the
  49 answered entries, so those carry no answered-date. Five are real entries; one is *"Four early
  asks, all applied"*. File it if it survives a look
  · **CLOSED 2026-07-28 11:05, and the pixel check is what closed it.** The parsed evidence above
  said the defect was gone; this entry deliberately withheld the close until someone looked at the
  page, because the defect is about pixels and parsed data cannot see pixels. Looked, on the
  deployed `/questions`: **33** answered entries in the source carry a retained
  `- **Answer (via …):**` sub-bullet — the precondition, and without asserting it a count of zero
  raw tags is vacuous and reads exactly like a pass; **0** of them render the tag as literal text
  anywhere in the DOM (measured on `textContent`, 420,637 chars, so collapsed bodies count too —
  `innerText` alone sees 15,396 chars and would have proved nothing); and **53** `span.who`
  attribution pills render. The screenshot shows a thread as `↳ YOU 2026-07-26 18:54` /
  `↳ LOOP 2026-07-26 18:56`. Landed at **`8009c90`**, which this entry never cited — that missing
  citation is the whole reason a fixed defect stayed open as a P1 and nearly got a lane
  · **the instrument had to be checked before the measurement meant anything.** The deployed page
  is running `c42af82`, not master — but every hunk of that diff falls inside 7541-7711, the ledger
  parsers. The answered-rendering code is byte-identical, so the page could answer this question
  · **the brief written for this task was deleted, not kept.** Its premise was the stale one and
  its prescription — the symmetric one-argument fix — was actively wrong. A wrong brief left in
  `.dreamwork/docs/briefs/` is a loaded trap for whoever greps that directory next
  · related: **#411, #446** — the other half of this section: this entry is what the page gets RIGHT about an answered entry, `#411` is the date it silently drops
- **#394** — a dreamer lane reports only to the inbox, so its landing dies with its coordinator ·
  P2 · loop/durability · origin: **loop** · found while verifying **#381** end to end
  · `#381` built the delivery half of the single-writer rule and **both its readers work** — but
  `## Pending` was **empty** while two lanes had just landed work they cannot write the ledger for.
  Not a defect in #381: **nothing instructs a producer.** Every brief I write says *"report by
  appending once to `.dreamwork/inbox.md`"*, and an inbox report is **prose nobody parses**
  · the inbox has never lost a report *while a coordinator is alive to read it*. `#334` and `#362`
  are the other case — work landed, nobody folded, an hour each. **That is precisely the case a
  hand-off line survives and an inbox report does not:** one is machine-checked by `lint.py` and
  rendered on the dashboard, the other is paragraphs
  · so a lane should write **both**: the inbox report for the coordinator's judgement, and one
  hand-off line for the ledger's bookkeeping. Cheap — one `cat >>` per landing
  · where the instruction belongs is the open question: my brief prose is not durable, so the
  candidate is `SKILL.md`'s Subagents section, beside *"All subagents report to the coordinator
  through a file"* — which is already the right paragraph and already load-bearing

  · **LANDED (instruction), VERIFICATION PENDING** 2026-07-28 08:59 — `SKILL.md` now states the
  obligation at dispatch time with the reason: the inbox carries judgement, is prose, and is read by
  a coordinator **once**; the hand-off carries the id and the sha and is read by `lint.py` and the
  dashboard **forever**. Relayed to all three live lanes with `handoffs.md` explicitly granted,
  since none of their briefs could have granted it
  · **it is not verified yet and I will not record it as such.** The test is whether a hand-off line
  actually appears when a lane lands — and **the relay is itself a write-then-hope channel with no
  wake**, which is the irony `#381`'s lane pointed at and did not act on. A lane already past its
  increment boundary may never read it, so a silent result proves nothing about the instruction and
  everything about the delivery. If none of the three writes a line, the finding is that the
  instruction must reach a lane **in its dispatch prompt**, not in a relay it may never open
  · so the durable half of this fix is the brief template rather than `SKILL.md` alone — every
  future dispatch prompt carries the line, and that is a coordinator habit with no enforcement.
  A `lint.py` check that a landed-and-committed lane left a hand-off is not possible (lint cannot
  know a lane ran); what *is* checkable is the condition `#381` already checks
  · **VERIFIED NEGATIVE 2026-07-28 09:12, which is the result I predicted and it settles the
  design.** `#395` landed `301f195` and exited having written **no hand-off line**; its report
  mentions the relay **zero** times. So the instruction did not reach it. Per the annotation above
  I do not read this as "the instruction is wrong" — I read it as **"the relay was the wrong
  channel"**, which is what that annotation said the silent case would mean
  · **and the control exists, which makes it a measurement rather than a guess:** `#389`'s lane
  *did* read its relay and reported on it by name. So relays are read by lanes with increments left
  and missed by lanes that run straight through — a property of the lane's own decomposition, which
  is chosen after dispatch and is invisible to me. Recorded as a lesson
  · **so the fix moves: every dispatch prompt carries the hand-off line.** `SKILL.md` already states
  the obligation; what it must also say — and now does not — is that the obligation goes in the
  *prompt*, because a lane reads its brief and prompt exactly once and reliably. That is a one-line
  amendment and it is the remaining work on this task
  · `#396` is still in flight with the same relay-delivered obligation, so it is a second trial of
  the same negative; do not treat its silence as new information
  · **VERIFIED AND CLOSED** 2026-07-28 10:45 — `6f72b8d` (SKILL.md) + `9e7e209` (dispatch prompt),
  enforced by `#398`'s lint check (`9f2012a`)
  · **this entry named its own test and the test has now run.** It said the question was *"whether a
  hand-off line actually appears when a lane lands"*, and predicted that if the relayed lanes wrote
  nothing, *"the finding is that the instruction must reach a lane in its dispatch prompt, not in a
  relay it may never open"*. **Both halves came back exactly as predicted.** The relay arm: the lane
  that landed wrote no line and its report never mentioned the relay. The dispatch-prompt arm,
  measured across a four-lane batch: **4 of 4 wrote one**
  · **and the measurement corrected me once, which is why it is worth stating how it was taken.** At
  09:46 I observed two landed lanes with no hand-off line and nearly filed *"prompt placement is
  insufficient"*. I withheld it because both lanes were **still alive**; both wrote within fifteen
  minutes. **A landing and its hand-off are not one act**, so a compliance count taken at commit time
  measures the wrong moment — `pgrep`, not the file, decides when to count
  · **what it did NOT fix, now filed rather than assumed:** the line can land in the wrong section
  (**#406**, fixed), carry an id no reader accepts (**#401**, fixed), or be suppressed by another
  landing's fold (**#409**, open). And one lane wrote a hand-off but **no inbox report at all**, so
  the sentence this entry leaned on — *"the inbox has never lost a report"* — is **false as of
  today** and `SKILL.md` has been corrected (**#404**)
  · related: **#381, #398, #400, #404**

- **#401** — a sub-id hand-off is invisible to **every** reader: the parser drops it, the
  malformed-validator cannot see it, and the correlation would not match it either · **P1** ·
  handoffs-parser/correctness · origin: **loop** · found by asking what the grammar accepts of the
  id vocabulary the ledger actually uses — the same question that found **#399** and **#395**
  · **live right now, and I caused it.** `#392a`'s brief instructs its lane, verbatim, to append
  `- **#392a** · landed …`. All three patterns at `watch.py:7706-7709` are `#(\d+)`, so **measured
  on the real grammar**: a `#392a` line yields `pending=[]`, `malformed=[]` — it is not rendered,
  and it is not reported as garbled. It reads exactly like an empty file
  · **the same run drops `- **#367/#392**`**, the ledger's own documented combined-id head form
  · **`malformed` is the validator built for precisely this and it structurally cannot fire.**
  Its stated job is *"a Pending entry head the grammar does not recognise"*, but `HANDOFF_BARE_RE`
  is `#(\d+)` too — so a head neither pattern recognises falls through **both** branches. The
  fallback that exists to catch an unknown shape shares the assumption that makes the shape
  unknown. This is the recurring class, now found in production code rather than in a check
  · **and a second, independent reason it stays quiet:** lint's delivery WARN fires only when the
  id is in `open_ids`. `#392a` is **not a ledger head** — `grep` finds zero `- **#392a**` in
  `tasks.md`; the head is `#392`. So even a parser that accepted the id would correlate it against
  nothing. Two readers, one shared assumption — *ids are the ledger's numeric heads* — and it is
  invisible because they agree
  · **this defeats `#381`'s whole purpose, silently.** Its premise is that a landing cannot be lost
  because the file is append-only; the line does land as text. What is lost is every **reader** of
  it, which is the half `#381` was built to add. The only thing standing between this and a
  repeat of `#334`/`#362` is the coordinator reading the file by eye each tick, which is exactly
  what `#381` existed to stop relying on
  · **the policy question is real and I have not ruled:** should the grammar **accept** sub-ids and
  combined ids (mapping `392a → 392` for correlation), or should a hand-off be **required** to name
  a ledger head, with anything else a loud WARN? The second is smaller and arguably more correct —
  the ledger head is what gets folded
  · **but one change is needed either way, and it is the load-bearing one:** `HANDOFF_BARE_RE` must
  match **any** bolded-id entry head, so an id shape the grammar rejects becomes a WARN rather than
  silence. Do that first; the policy choice is decidable afterwards and independent
  · **blocked on `watch.py`** (held by `#392a`), and `lint.py` imports the parser rather than
  copying it, so the fix is one place. Whoever takes it gets `watch.py`, `test_watch.py`,
  `lint.py`, `test_lint.py`, and `file-formats.md`, whose hand-off row states the shape
  · **the red is free and it is about to write itself** — `#392a`'s own hand-off line will be in
  the file. Do not ask it to change; fold that line by hand and keep it as the fixture
  · **audit half LANDED** `f2c950e` (2026-07-28 09:48, `ccc @grok`, brief
  `.dreamwork/docs/briefs/401-id-grammar-audit.md`) →
  `.dreamwork/docs/research/2026-07-28-task-id-grammar-audit.md`. **14** id-touching sites × **17**
  forms derived from the repo, every cell **executed** against the real modules (harness in §3,
  re-runnable). **7 silent rejects.** This entry's measurement **reproduces exactly**. The fix half
  stays open and still needs `watch.py`
  · **the audit found a THIRD form of the defect that is worse than a drop, and it is new here:**
  `ENTRY_ID` **strips the letter**, so `#392a` parses as **`392`** — a *silently wrong* id rather
  than a missing one. So the same sub-id is invisible in one reader and **misattributed to its
  parent** in another; `related: **#392a**` would bind a relation to `#392`, and a landed-section
  mention of `#392a` would land `#392`. A drop is detectable by a coverage count; this is not
  · **the form the brief did not name**, found as required: `comma_list_one_bold`
  (`related: **#381, #399, #395**`) — the dominant `related:` shape, and it **works**
  · not reached, stated: the full 18×38 cell dump, `dreamhub.py`'s scope, and fixture-level lint
  reds
  · **the one cell the audit left unverified is now VERIFIED, by the coordinator, with a control —
  and the lane's classification was right.** The multi-bold `related:` case is **LOUD**. Probed on a
  temp fixture: form **A** `related: **#501**, **#502**` → **3 ERRORs**, the first being `#395`'s
  dedicated *"two adjacent bold spans — only the first id is read"* which names the true cause; form
  **B** `related: **#501, #502**` → **0** and the OK coverage line. Precondition asserted first: the
  probe confirmed the second span really is dropped before drawing any conclusion, so it was testing
  the real thing rather than a fixture that agreed with it
  · **CLOSED, verified** 2026-07-28 10:20 — `e53d70c`, merged `db4ab8d`. `ccc @grok`, brief
  `.dreamwork/docs/briefs/401-406-handoff-grammar-fix.md`. **The first lane dispatched into a
  worktree** (`.worktrees/401-406`); landed together with **#406**
  · the grammar now accepts the vocabulary the loop actually writes — plain `#N`, sub-id `#Na`,
  combined `#N/#M` — and correlation against `## Open` goes through a **named, tested**
  `handoff_parent_ids` (`watch.py:7732`), not `ENTRY_ID`'s incidental letter-strip
  · **verified independently by the coordinator: four shapes on temp roots, all four LOUD** — a
  Pending-shaped line in the wrong section (`malformed`, WARN), a sub-id landing (parses and
  correlates to its open parent), a combined id (parses), a junk id `#zzz` (`malformed`, WARN).
  **Precondition derived, not assumed**: the live section order was read from the file to establish
  that a landed line under `## Folded` really is misplaced. **496 passed** on the merged tree
  · lane's three injected reds each named a distinct failing test with neighbours green, each
  grep-confirmed and `ast.parse`-confirmed
  · **it corrected me twice.** `29fe5a6` had moved `#392a`'s line into Pending **nine minutes
  before** I wrote a fold note calling it a deliberate fixture still under `## Folded`; the lane
  **restored the fixture** so its own red could fire, then re-tidied. My 09:52 "invisible"
  measurement was right — the operative cause was the **id grammar alone**, not the section. And it
  left its hand-off line unstaged (**#394** again), which I committed as ledger writer
  · **what the widened fallback still cannot see**, stated rather than discovered later: no bold
  (`- #5 …`), no `#` (`- **5** …`), a different list marker (`* **#5**`), an indented list item —
  same class, different axis
  · **`ENTRY_ID` deliberately unchanged**, blast radius documented: it is the atom for
  `parse_ledger`, `_open_ids`, `_landed_ids`, related, origins and lint's entry walk. That is
  **#399**'s neighbourhood
  · related: **#381, #399, #395, #402, #406, #409, #415, #427**

- **#406** — `handoffs.md` instructs an append that **structurally cannot** put the line where it
  is required · **P1** · handoffs/format · origin: **loop** · found by watching a live lane obey
  the instruction literally, then confirmed twice more independently
  · **the instruction every brief and dispatch prompt carries is** *append only with `cat >>`, never
  rewrite* — **and `## Pending` is not the last section.** `cat >>` writes at end-of-file, which is
  **inside `## Folded`**. A lane that obeys exactly puts its landing in the wrong section
  · **three independent confirmations, none of them planned.** `#392a`'s line sits after `## Folded`
  in the file right now. The `#401` audit lane hit the same thing, reported it under *"not confident
  about"* — *"whether `cat >>` alone can ever place a line under Pending while `## Folded` sits
  below"* — and then **committed a fix for its own line** (`75e6139`). And its matrix ranks the live
  `#392a` case as its **second** silent reject, reached independently of mine
  · **triple-invisible, measured.** A Pending-shaped line inside `## Folded` matches neither
  `HANDOFF_FOLDED_RE` (wrong shape) nor `pending` (wrong section) — and the `malformed` fallback
  **only runs inside section P**, so it is not reported either. Same end state as **#401** by an
  entirely different route
  · **the inversion is the finding: the lanes that got it right DISOBEYED me.** Three of four
  inserted before `## Folded` — a rewrite, which the instruction forbids. **Compliance with the
  instruction produces the defect**, so the obligation's own wording selects against the outcome it
  exists to secure
  · **and the sections turn out to be redundant.** The two line shapes are already
  self-distinguishing — `· landed \`sha\`` versus `→ folded (ts):` — and correlation is by id, which
  is stated in the file's own header. `parse_handoffs` uses the headings only to pick which regex to
  apply, a choice the line itself already determines
  · rec, smallest first: **move `## Folded` above `## Pending`** so an EOF append lands correctly and
  the instruction becomes true. Better but larger: **drop the sections**, parse by line shape, and
  let append-only mean what it says. Either way the `malformed` fallback must run **outside** any
  section so a misplaced line is loud
  · **the red is in the tree and needs no injection** — `#392a`'s misfiled line is the fixture. Do
  not tidy it away before the check exists
  · **CLOSED, verified** 2026-07-28 10:20 — `e53d70c`, merged `db4ab8d`, same commit as **#401**,
  whose entry carries the full evidence
  · **`## Folded` now precedes `## Pending`**, so an EOF `cat >>` lands in the right section and the
  instruction every brief carries becomes true. `malformed` runs **outside** any section, so a
  misplaced line is reported rather than dropped
  · **four of five lanes had to work around the old wording**, two by silently self-correcting
  (`75e6139`, `29fe5a6`) — which is why it stayed invisible as long as it did
  · related: **#381, #401, #404, #405**

- **#397** — `watch.py` is the loop's contention bottleneck; propose splitting it · origin: **loop** ·
  closed 2026-07-28 09:52 · `1b508b0`
  · `ccc @glm52`, brief `.dreamwork/docs/briefs/397-client-extraction-design.md`, plan
  `.dreamwork/docs/plans/watch-client-extraction.md` (459 lines). **Folded from a hand-off** — the
  channel's second fold and its first with a lane that complied ~15 min *after* committing, which
  is why a compliance count taken at commit time measures the wrong moment (**#404**)
  · **the recommendation is do-not-extract and the loop is accepting it, deliberately without
  asking him.** Doing nothing needs no authorisation; building would. Accepting a
  do-nothing recommendation is the conservative direction and the scope gate's own default, so no
  review artifact and no `questions.md` entry ship — he has three unanswered questions already and
  a fourth that resolves itself is a cost, not a courtesy. **The plan is mechanically ready if he
  ever wants it**, and that is recorded here rather than lost
  · **why do-not-extract, in the plan's own terms:** the mechanics are *cheap* — interpolation
  count **1** (`/*DEV*/false` at `COMPONENTS_JS:1658`, swapped once at `:8989`); the 8 `json.dumps`
  values are a concatenated preamble, not interpolated into the assets. What kills it is that
  extraction **does not unblock the queue's hardest items** (`#331`, `#352` are Python parser work
  needing `#368`'s separate split), it **multiplies the registry-coupling class that caused today's
  actual damage** while file contention corrupted nothing, and **the throughput win is captured
  more cheaply by a worktree** — see **#405**, which is the plan's own alternative and his standing
  convention
  · **it refuted my measurement and I verified the refutation.** I told two lane prompts that
  `server_class` (`:262`) was **6,798 lines, 72% of the file**, as a number to *inherit rather than
  re-derive*. It is **10 lines** (`:262-:271`). Confirmed by `ast`: the largest top-level def is
  `make_handler` at **434** (`:9025`), and the client lives in **8 module-level string constants**
  totalling **6,756** lines (`ROUTER_JS` 2293, `STYLE` 1253, `VIEWS_JS` 1108, `COMMAND_JS` 716,
  `COMPONENTS_JS` 646, `SHADER_JS` 522, `FAVICON_JS` 149, `APP_BODY` 69). The ~75% conclusion
  survives; the attribution did not
  · **four breaks named concretely, which is what made this a plan rather than an opinion:**
  `just deploy` **breaks** (snapshots `watch.py` alone → blank page) and must become a directory
  snapshot; the `serving` guard **breaks** (needs one `cpSync`); `--autoreload` **regresses** (it
  watches only `__file__` mtime, so asset edits stop hot-reloading unless the watcher gains the 8
  paths); the styleguide audit needs re-pointing. Main `just guards` survives if `watch.py` resolves
  `client/` by `__file__`
  · **CSS-only is a false economy** — 3 of 4 client parties this session touched JS. All 8 or none
  · six tasks genuinely queue on `watch.py`: **#352, #351, #337, #331, #322, #295**; `#319` also
  needs it. Cost is **throughput**, not correctness
  · related: **#264, #405**

- **#398** — a brief written after the hand-off obligation landed must carry it · origin: **loop** ·
  closed 2026-07-28 09:31 · `9f2012a`
  · `ccc @grok`, brief `.dreamwork/docs/briefs/398-brief-handoff-check.md`. **Folded from a
  hand-off**, and that sentence is the point: this is the **first fold in the channel's history**
  and the first time `#381`'s work ran end to end with a real producer rather than my temp-target
  test. `lint` WARNed *"#398 is named as landed in a hand-off … but is still under `## Open` — fold
  it"*, exactly as designed, and this commit is the fold
  · **it is also `#394`'s verification, and the comparison is clean because both arms ran:** the
  obligation delivered by **relay** produced nothing (`#395` landed, wrote no line, never mentioned
  the relay); delivered in the **dispatch prompt** it produced a line on the first attempt. Same
  obligation, same wording, two channels, opposite outcomes — so the rule *"obligations go in the
  prompt, refinements go in the relay"* is measured rather than reasoned
  · the check itself: **`3 brief(s) in scope after hand-off obligation, 27 grandfathered`** on the
  live tree, matching the split I measured before dispatch, and carrying the coverage number in the
  idiom `#395` established an hour earlier
  · **VERIFIED 09:36, once the lane exited and released `lint.py`** — the fold above deliberately
  did not claim this, because an injection is a write and the owner was still running. The
  discriminating red is the strongest form available: replacing the cutoff phrase with one absent
  from `SKILL.md` makes `lint` **ERROR** rather than grandfather everything, and the message states
  the consequence out loud — *"could not resolve the hand-off obligation cutoff from SKILL.md
  content … **every brief would have been left unchecked**; a reworded phrase or missing history is a
  loud failure, never a silent pass"*. Two tests fail
  (`test_the_cutoff_is_resolved_from_content_not_a_pinned_sha`,
  `test_the_live_tree_is_green_with_coverage_numbers`) while **7 neighbours pass**
  · **my first injection of that red was invalid and I nearly believed it:** I replaced the regex's
  group 1, which for a parenthesised multi-line constant is just `(`, leaving a file that would not
  parse — so pytest reported a collection `IndentationError`, which is *not* a red. Restored,
  re-injected properly, `ast.parse`-checked before believing the second result. **A broken injection
  and a discriminating red look similar in a tail of output and mean opposite things**
  · the lane's own caveat is a good one and I am not acting on it: a prose phrase is load-bearing, so
  if rewording becomes frequent the stabler target is a never-reworded marker comment in `SKILL.md`.
  Noted rather than pre-empted — and my own `SKILL.md` edit ten minutes later did touch that
  paragraph and left the phrase's occurrence count unchanged, so `git log -S` still resolves to
  `6f72b8d`. Verified by lint staying green, not assumed
  · related: **#394, #404**
- **#396** — an inline `data-mark` puts its flag outside the reading column and clips past the page
  edge · origin: **loop** · closed 2026-07-28 09:26 · `7902818`
  · `ccc @glm52`, brief `.dreamwork/docs/briefs/396-inline-mark-refusal.md`. Refused at **build
  time** with a **tag-name allowlist** (`MARKS_BLOCK_HOSTS`, `:706`) rather than an inline denylist —
  the reasoning it recorded beside the constant is the part worth keeping: a denylist fails open on
  `abbr`, `kbd`, `mark`, `sub` *"and whatever arrives next"*, and only an allowlist can say yes to a
  `<span>` the page re-floated without saying yes to one it did not
  · **coordinator verified it against the artifact that FOUND the defect, which is the strongest
  form available**: the probe I built at 08:50 to reproduce the clipping **no longer builds**, and
  the refusal names both offending elements *and* both labels *and* the mechanism *and* the allowed
  containers. A block mark still builds. Injecting `strong em a code span` into the allowlist makes
  my probe build again and fails `test_an_inline_data_mark_is_refused` while
  `test_a_block_data_mark_is_still_accepted` stays green; injection grepped for, restored from a `cp`
  snapshot byte-exact. `markrail` re-run by me: **PASS at load 15.8**
  · **it refuted my brief's premise about the harness, and that is the third premise a lane has
  corrected today.** I wrote criterion 4 around adding an inline mark to `dev/capture/fixture/`.
  **`markrail` does not read that directory** — it builds its own fixture as an inline source string
  in `dev/capture/markrail.mjs` and loads it over `file://`; `dev/capture/fixture/` serves the guards
  that navigate a live `watch.py`. The lane put the mark in the right place, got the red there, and
  **reverted the guard** — because once the build refuses an inline mark, **a committed inline-mark
  fixture is unconstructible**. So the permanent regression net is the pytest, not the guard, and
  that is the correct resolution rather than a shortfall: the input class can no longer reach the
  geometry at all
  · **CSS-induced shape changes are explicitly out of scope** and it said so beside the constant — a
  block the artifact's CSS floated or shrank is `#367` increment 2b's territory
  · related: **#367**
- **#395** — a relation marker without bold parses as absent · origin: **loop** · closed
  2026-07-28 09:14 · `301f195`
  · `ccc @grok`, brief `.dreamwork/docs/briefs/395-relation-marker-shape.md`. A present-but-
  unparseable marker is now an ERROR naming the **shape** rather than a downstream reciprocity
  symptom, `RELATED_FIELD` anchors the match to line-start or a `·` separator so prose cannot
  manufacture a phantom, and adjacent bold spans are flagged instead of silently truncated to the
  first id
  · **coordinator verified all three claims independently.** (1) **Against the real revision**:
  `lint.py --target` on a temp target holding `660a294^`'s ledger names **#388, #387 and #386**,
  with the precondition checked first — that blob really does carry 3 unbolded markers. (2) **The
  discriminating red**: restoring `if not found: continue` fails **both**
  `test_an_unbolded_relation_marker_is_flagged_not_skipped` **and**
  `test_it_flags_the_unbolded_markers_in_the_actual_revision_that_hid_them`, while **15 other
  related tests stayed green**; injection grepped for before believing it, restored from a `cp`
  snapshot, byte-exact. (3) **The coverage number is live**: a clean run now prints *"19 related
  pair(s), all reciprocal; 0 entries unparseable"* — the general fix, and the line whose absence let
  this hole sit open
  · **no false positive on 130 open entries**, which was the way to make this worse: a check that
  nags on good entries gets muted
  · trap 1 respected — the wrong-case branch was **kept**, since it does fire
  · lane's caveats: the coverage count prints only on the clean summary, not beside ERRORs (a
  deliberate choice, to avoid claiming reciprocity next to errors); a trailing comma inside one span
  is accepted. Both fine
  · its spec note, which I will apply when `file-formats.md` frees: line 516 still says the ledger has
  zero relation markers, which is stale prose
  · related: **#353, #401**
- **#381** — the single-writer rule has no delivery half · origin: **loop** · closed
  2026-07-28 08:42 · `38b541c` `f09a1ba` `374c044`
  · `ccc @glm52`, brief `.dreamwork/docs/briefs/381-handoff-delivery.md`. `.dreamwork/handoffs.md`
  with literal `## Pending` / `## Folded`, append-only in both directions — **nothing ever moves**,
  so two sessions landing at once cannot lose each other's line, which is the property the dreamer
  inbox has and a rewrite would not. Plus `lint.check_handoffs`, the status-panel surfacing, and
  the `SKILL.md` tick step that reads and folds
  · **coordinator verified the READER end to end, which was the stated hollow outcome** — a channel
  nobody reads is the bug the task was sent to fix, so a written-but-unread file would have looked
  done. Against a temp target copy, with the precondition derived at runtime rather than
  hardcoded (`#392` really is under `## Open`): an unfolded landing WARNs *"#392 is named as landed
  in a hand-off … but is still under `## Open`"*; appending the `→ folded` line **clears it**, which
  is the property the brief cared about most, because a nag that persists after you comply gets
  muted and a muted check is worse than none. Second reader too: `pending_handoff_records` returns
  the record when pending and `[]` once folded, asserted as a gap rather than as two literals
  · **ruled on the lane's open offer, and the answer is no:** it asked whether a hand-off whose task
  has already landed but carries no fold record should WARN. **Leave it silent.** That state is
  "work done, bookkeeping lagging" — benign, and the grooming tick closes it. A check that fires on
  a benign state is exactly how a check gets muted, which is the title of the lane's own dream
  · gaps filed rather than absorbed: **#393** (the appearing span has no motion guard) and **#394**
  (nothing instructs a lane to write a hand-off, so `## Pending` sat empty while two landed)
  · the lane also observed, without acting on it, that **the relay is the same bug one layer up** —
  coordinator writes a steer, an idle lane never reads it, nothing wakes it. Same shape, same fix.
  Recorded in `.dreamwork/dreams/2026-07-28-0838-the-nag-that-gets-muted.md`
  · related: **#393, #394, #363, #401, #404, #406, #409**

- **#390** — a fresh domain's first answer creates its file · origin: **loop** · closed
  2026-07-28 08:06 · `fa65bce`
  · `ccc @glm52`, brief `.dreamwork/docs/briefs/390-reconcile-absent-file.md`. `reconcile`
  translates `FileNotFoundError` to `text = None`, and `prove_applied` gains
  `if text is None: return Proof.NOT_APPLIED` — so the create path and the update path share
  **one proof**, which is where exactly-once is won. 7 tests in `test_user_events_apply.py`
  · **coordinator re-ran the discriminating red**, which is the one that mattered: collapsing
  the branch to `if not text:` — the natural falsy test — makes absent and empty prove alike and
  reddens exactly `test_an_absent_file_and_an_empty_file_do_not_prove_the_same_thing`, with the
  other six green. Its assertion message names the trap rather than printing two enums.
  Snapshot-restored; 7 pass
  · **its one honest caveat is resolved without the revert it offered.** It could not capture a
  pre-change test count because another lane's commits overlapped its run, so it *inferred* the
  baseline from a +2 delta. Checked directly instead: `fa65bce` adds exactly 2 `def test_` and
  removes **0**, so the inference holds and no test was lost
  · **one contract widening a future reader should know**: `prove_applied`'s `text` went
  `str` → `Optional[str]`. Backward-compatible, the `str` path is byte-for-byte unchanged, and
  it is what lets create and update share the proof — but it is a widening on the function
  carrying lane D's delicate D1/D2 reds, and the lane flagged it rather than letting it pass
  · **law 8 untouched, and the lane argued why rather than asserting it**: law 8 governs
  *present* files, and an absent file has no bytes and no lineage, so its predicate cannot be
  evaluated. `prove_applied("")` is still `UNKNOWN`
- **#385** — humanized `XXa YYb` age beside a question's date · origin: **human** · closed
  2026-07-28 08:02 · `e1926b4` `8dc448c` `0dd136e` `aabe9fb`
  · `ccc @grok`, brief `.dreamwork/docs/briefs/385-humanized-age.md`. **All three gaps closed:**
  `AGE_PAIRS` now runs years → weeks → days → hours → minutes → seconds (it stopped at days, so
  `XX` passed 99 at **100 days** — about 3.3 months, not the century he specified); the pad digit
  of a single-figure unit is greyed; and the questions headline carries the age beside the date.
  Year length 365d, named in the source so the choice is not silent. Negative deltas clamp to 0,
  so a future timestamp from clock skew cannot render `-1d`
  · **coordinator re-ran the ladder red**: removing the year rung fails
  `test_age_pair_fields_stay_under_100_for_a_century` **by showing** `field w=100 at age
  60480000s → '100w 00d'` — a three-digit field, not merely by naming the missing rung, which is
  the discriminating form. Its century length derives from the table's year rung when present and
  from the named `365 * 86400` expression when absent, so the check still probes a century under
  its own injection. Snapshot-restored; 32 age tests pass
  · **but the third gap was closed only client-side, and the coordinator found it on the deployed
  page 15 minutes later:** the age is measured from **midnight** of the entry's date because that
  is all the data carries. Filed as **#392**; the lane built what was asked and the criterion did
  not ask for accuracy · related: **#392**
  · **one correction to my own brief:** criterion 2 predicted the failure would show *a day count*
  above 99. With the week rung present it shows a **week** count. The lane's test is right and my
  arithmetic was not
  · **its one open item became #391 and was a real regression.** It reported eleven guards failing
  at load 121 as probable flakes and honestly said it had not re-run quietly. Ten do pass quietly;
  `prominence` did not, and it was #277's doing. Closed at `9e27c6e`

- **#382** — `plugcmd` failed on a selector, not a race · origin: **loop** · closed 2026-07-28 ·
  `a6d66b0`, dream `aca4c37`
  · the guard read `#fmsg` where it meant `#cmdmsg`, so a page behaving perfectly reported a
  timing race. **The lane refuted the coordinator's own diagnosis** — my brief asserted a fixed
  900ms timing race — and its dream records the transferable half: the hollow-check pattern
  recurs in the *diagnosis*, not only in the check
  · related: **#384** — the same misread node turned out to be asserted on by `subslog`, which is
  why the two entries reference each other and why condensing this one dropped a marker `lint.py`
  then caught

- **#391** — prominence air restored · origin: **loop** · closed 2026-07-28 07:57 · `9e27c6e`
  · `ccc @grok`, brief `.dreamwork/docs/briefs/391-prominence-air.md`. **Cause: `22f9884`
  (#277), which rewrote the shared rule `details[open] { padding:.5rem 0 }` to
  `padding:0 0 .5rem`** to quiet an 8px summary shift under the pointer during a fold. Measured
  pads went `0/0 → 0/8` (top air unchanged at 0, bottom still growing) and are now `0/0 → 8/8`
  on all four surfaces. `git blame` on the line found it, so the bisect was not a walk
  · **coordinator verified the thing the lane could not**: its brief forbade the full sweep, so
  the open question was whether restoring #169's air reintroduces what #277 was quieting. I ran
  #277's **own** `dreamfade` guard plus `qfade morph morphhold states thread qacard reflow
  headertravel` at load 25–35 — **all nine pass.** So #277 changed two things for one symptom
  and only `.qa.folded .qfold { margin:0 }` was load-bearing; the padding rewrite was never
  needed and cost #169 four surfaces for three hours. Also re-ran the red myself: reinstating
  the one-sided rule reddens all four; restored from a `cp` snapshot
  · **it hid behind a load-flake reading**, which is the transferable part — see the
  `lessons.md` entries on closing a load-attributed red with a quiet run, and on isolating a
  deliberate change to a *shared* rule
- **#389** — empty/blank mark labels refused · origin: **loop** · closed 2026-07-28 07:44 · `b79f339` `e0a3356`
  · `ccc @glm52`, brief `.dreamwork/docs/briefs/389-empty-mark-label.md`. Valueless `data-mark`
  stays ignored; `""` and whitespace-only are refused naming the offending element; all three
  tested. **76 tests in `test_review_artifact.py`.**
  · **coordinator verified the red I actually cared about**: injecting the naive one-liner
  `if not (label or "").strip()` — the fix that swallows the valueless carve-out — reddened
  exactly `test_a_mark_label_must_carry_readable_text[valueless]` and
  `test_a_valueless_mark_on_an_id_less_element_is_not_a_no_id_error`, with all 74 others green.
  Snapshot-restored; 76 pass
  · **the lane read its relay and answered all four neighbours**, and found a limit I had not
  anticipated: `.strip()` catches every `Zs` space (U+00A0, U+2003, U+3000 all refuse) but
  **not U+200B**, which is category `Cf`. I confirmed that independently. It flagged rather
  than widened its brief unasked, which was right. Named as a known limit in `file-formats.md`
  and folded into #367 increment 2a's brief as a secondary item, since 2a owns that file next —
  a blank tab matters more once tabs are actually rendered

- **#300** — Let run-mode descriptions liquefy through one shared popover · P2
  · **IN PROGRESS 2026-07-28 06:13** — he re-raised it himself as `do-next` at 06:07:
  *"run mode button group needs a nice description that shows when any of the buttons are
  hovered. see the original task for a more."* Dispatched to `ccc @grok` with brief
  `.dreamwork/docs/briefs/300-runmode-popover.md`, sole holder of `watch.py`, port 39891
  · **routed to grok specifically because this one needs vision** — the acceptance includes
  visual review loops on rendered pixels and a text morph only judgeable from intermediate
  frames, and `@glm52` is not multimodal. That is the first time the model choice here has
  been forced by a capability rather than a preference
  · the entry below is the requirements document; `ca12a3c` only captured it
  · Web UI feature · 35m · origin: **human** · **human via watch `add-idea`
  14:37** · hovering a run-mode button should explain that mode; all buttons
  share one geometrically stable description surface so moving between them
  morphs/liquefies the words in place rather than spawning unrelated tooltips ·
  copy is sourced from the actual hierarchical/park/hot behavioural contract,
  including what continues, stops and commits, never marketing shorthand that
  can contradict runtime semantics · keyboard focus shows the same description
  and `aria-describedby` exposes it; touch/focus parity must not add a surprise
  second tap or interfere with #290's 10-second arm/reset/cancel/cross-tab rules ·
  first arrival and final departure reuse the atmospheric blur/drift idiom;
  button→button swaps keep the shell fixed while old text dissolves and new text
  resolves, with several causal intermediate opacity/blur states rather than a
  frame-zero replacement; reduced-motion swaps text instantly with identical
  meaning/function · Escape/pointer-leave/blur dismissal has no mode side effect
  and popover geometry clamps on desktop/mobile without obscuring the countdown ·
  red-first real-route guard + deterministic captures; multiple interleaved
  vision/geometry visual-review-and-fix loops until both PASS · depends on
  landed #290 and must keep its exactly-once POST/event guards green

  · **closed `97c4fac` + `a6959cf`** — one geometrically stable `#rundesc` under the chips, copy
  traced to the behavioural contract, morph via rAF + `between()`, reduced-motion parity with
  identical text and `aria-describedby`, and a 642-line `rundesc` guard registered in
  `DEFAULT_GUARDS` with `transitions.md` and `watch-design.md` updated in the same commit
  · **the lane found that MY acceptance criterion was unsound, which is the most valuable thing
  produced in this batch.** I had specified: prove hover has zero side effects by counting
  `/run-mode` POSTs, `watch-events.log` lines and the run-mode file's bytes across a hover sweep.
  That reads as thorough and **cannot work** — #290's arm deliberately stays silent for **ten
  seconds**, so a hover calling `pickRunMode` lights the arm UI, writes pending `localStorage` and
  starts the countdown while every signal I named stays quiet. Its first red-run of that check
  came back **green with the bug in place**, and it applied the rule rather than the instruction
  · fix: assert what flips at **selection** rather than at commit — `#runcount` must not read
  `arms in`, and `dw:run-mode-pending:` keys must be unchanged — with the durable signals kept as
  necessary but not sufficient. Dream: `.dreamwork/dreams/2026-07-28-0645-arm-silent-for-ten-seconds.md`
  · **verified independently by me, and the result discriminates exactly right**: I injected
  `pickRunMode(mode)` into `showRunDesc`, and the guard failed on **precisely the two assertions
  the lane added** — `FAIL hover sweep did not start an arm countdown (runcount empty of arms-in)`
  and `FAIL hover sweep left run-mode pending localStorage unchanged` — while the POST, events-log
  and file assertions **I** had specified stayed green. So my criterion was demonstrably blind to
  this bug and the extension is what catches it. Restored byte-identical; `PASS rundesc` after
  · criterion 7 is the one gap: the full `just test` sweep was not run end-to-end because other
  lanes held guard ports. `rundesc` is green twice isolated, `lint.py` clean, `test_watch.py::TestRunMode`
  10/10, and I have since run the whole pytest half at 910 passed — so the untested remainder is
  the guard sweep, not the code
  · related: **#418**

- **#386** — `gitrow` opens 0px under load: the gesture does not run, and the motion check
  correctly says nothing moved · P3 · guards/reliability · origin: **loop** · 15m ·
  **separated out of #383 rather than papered over inside it.** #383 replaced the three motion
  guards' frame-counting with `between()`, and after that fix `revieworder` and `burndown` are
  3/3 under moderate load while `gitrow` is **2/3**
  · **the residual failure is a different fault from the one #383 fixed.** #383's bug was a
  real travel with too few samples counted as no travel. This one is a **0px open** — the row
  never opened, so there is genuinely no motion and the check is right to fail. The instrument
  is not hollow here; the *gesture* did not happen
  · so the fix is click readiness, not tolerance: find what makes the click land on a row that
  is not yet ready to open under load, and wait for that condition rather than for time. Widening
  the motion assertion would make the guard unable to see a real snap, which is the failure mode
  `.dreamwork/lessons.md` keeps recording
  · rec: reproduce under the same moderate load (3 busyloops) that the #383 lane used, since it
  is the only condition known to show it, and check whether the row's own arrival transition is
  still in flight when the click is dispatched
  · related: **#383, #388**

  · **closed `1cd588a`** — and the lane refuted this entry's own hypothesis, which said the row's
  arrival transition was still in flight when the click landed. **It is not a page-readiness bug
  at all; it is a test-harness timing race.** The click was dispatched as a *separate* Playwright
  roundtrip after a fixed sleep, while the 1500ms trace window was bounded to its own start —
  so under load the click's transport+actionability latency landed it **after the window closed**,
  and the trace honestly recorded 0px
  · **the discriminator is the good part**: the CLOSE gesture, on a row that had been open through
  several roundtrips and was fully settled, failed **identically** — 0px, one position, no ghost.
  A settled row cannot be mid-arrival, so the readiness story was dead. Two failure faces, one
  cause: `open: 22 -> 64, 2 positions, 0 part-way` (window closed mid-animation) and
  `close: 0px, 1 position` (click landed after it entirely)
  · fix: the click is dispatched **inside** the trace evaluate — the `dreamfade.mjs` idiom, action
  and trace in one browser roundtrip, so click latency cannot eat the window. #141's
  pointer-events contract is preserved by hit-testing `elementFromPoint`, so a summary he could
  not press still fails
  · **motion assertions unchanged in strictness, verified line by line** — `t.moved >= 60`,
  `t.partway >= 1`, `hPartway >= 1`, `mid >= 1`, `t.late <= 4`, `t.over <= 4` all byte-identical.
  Two *preconditions* were added, not loosened: the click-reached-the-summary gate, so a future
  failure says what it saw instead of "nothing moved"
  · **the red still bites after the fix, which was the actual risk here**: #383's page-injected
  snapping `travelCard` still produces `FAIL opening: ...and it travels there rather than
  teleporting` plus the two others, by name. The fix changed how the click lands, not what the
  motion check sees. Production lines named: `travelCard` (`watch.py:4709`) and `foldDetailsLocal`
  (`watch.py:5071`)
  · **verified independently by me, and the verdict is conclusive rather than encouraging**:
  `PASS gitrow` at load **100** on 16 cores. Load here can only manufacture false *reds* — a
  dropped intermediate frame — so a green under 6x oversubscription is stronger evidence than a
  green on an idle box
  · one tradeoff it flagged and I am recording rather than burying: the synthetic
  `elementFromPoint` + `summary.click()` drops Playwright's own actionability checks
  (visibility/stability). Safe today because the row is always settled when the gesture runs; if a
  future change makes it transiently unstable, the synthetic click fires where a real pointer
  would have waited

- **#383** — Three motion guards give different verdicts on unchanged code · P2 ·
  guards/verification · origin: **loop** · 30m · owner: dispatched dreamer on `ccc @grok`, brief
  `.dreamwork/docs/briefs/383-flaky-motion-guards.md`, owns `dev/capture/revieworder.mjs`,
  `gitrow.mjs`, `burndown.mjs`, port 39895
  · **the evidence is the disagreement, not the failure**: between the 04:40 full sweep and a
  focused re-run with the tree unchanged, `revieworder` went FAIL → **PASS**, `gitrow` failed on
  *opening* then on *closing*, and `burndown` went from a named assertion to *"the guard threw
  before finishing its checks"*. A check that disagrees with itself is worse than a red one,
  because neither answer can be believed
  · all three sample **intermediate** frames of a transition, which is correct — `transitions.md`
  says an end-state assertion cannot fail on a motion bug — but the hypothesis to confirm is that
  they sample on a wall-clock schedule, so a loaded machine drops the sample outside the window.
  If so there is one defective idiom and one fix, not three
  · **the trap named in the brief**: widening a tolerance until the check stops failing makes it
  hollow, which this repo treats as worse than red. `dev/capture/dreamfade.mjs` already samples
  per-frame via rAF and is the idiom to reuse rather than author a second one
  · the human has another agent writing KB material on testing animation in the browser; the
  brief tells this lane to look for it once and report whether it changed the approach — free
  signal on whether the KB earns its keep

  · **closed `0d92862`** — the shared mechanism was confirmed and it was not the wall-clock
  hypothesis in this brief: all three counted *distinct sampled values* (`distinct >= 8`), so a
  loaded machine that produced a genuine smooth travel with seven samples failed, and the count
  was never a property of the motion. Replaced by the `between(frames, first, last)` idiom
  already used by `dreamfade`/`fileimg` — at least one frame strictly between the endpoints,
  plus a vacuity span floor so "it never moved" cannot pass as "it moved a little"
  · **red-proof is discriminating per guard**, each by sabotaging the named production line:
  `regroupCards` → both revieworder travel checks FAIL by name; a page-injected snapping
  `travelCard` → gitrow's three opening/closing checks FAIL; a no-op `regroupBars` → burndown's
  TRAVELS check FAILs. All three PASS again after restore from the `cp` snapshot
  · `burndown` also now reports what *threw* (`uncaughtException`/`unhandledRejection` push the
  real error into a named FAIL) — its "the guard threw before finishing its checks" was hiding a
  `TypeError` on `r0.provline` when the panel had not rendered
  · **honestly left flaky, and it is a different fault**: `gitrow` 2/3 under moderate load, where
  the failure is a **0px open** — the click or gesture did not run at all — not too few frames of
  a real travel. Filed as #386 rather than papered over here

  · related: **#386, #388**
- **#384** — Two more guards read the wrong `.cmdmsg`, and their notes lie about it · P3 ·
  guards/honesty · origin: **loop** · 10m · found by generalising #382's cause: `watch.py` has
  **two** elements carrying `class="cmdmsg"` — `#fmsg` at 1562 and `#cmdmsg` at 1587 — so
  `document.querySelector('.cmdmsg')` returns the file-message node, never the composer's
  · `dev/capture/draft.mjs:159-160` and `dev/capture/subslog.mjs:152` both do exactly that
  · **checked rather than assumed, and the answer is the interesting part**: in both files the
  read feeds only `notes.push(...)`, never an `ok(...)`. Their assertions are on other things
  (`after.value === TEXT`; the submissions-log record), so **they are not hollow** — they pass for
  the right reasons. `plugcmd.mjs` is the only one where the selector is load-bearing, which is
  why it is the only one red
  · so the harm is smaller but real: a **diagnostic note that states a falsehood**, and the next
  person to debug this area trusts it. That is not hypothetical — the coordinator read
  `plugcmd`'s empty string as evidence of a slow round-trip and filed #382 with a race hypothesis
  that was wrong, because the note said the message was empty when the message it named was never
  the one being written to
  · fix is the selector only; no assertion should change, and if one has to, that means this entry
  mis-measured and the finding should come back rather than the assertion move
  · related: **#382**
  · **closed `4d60217`** — and the lane refuted the premise above for one of the two.
  `subslog.mjs` *does* assert on it: `ok('and the page still told him it failed', msg === 'no
  connection')` was reading `#fmsg`, so that assertion had never once looked at the composer.
  The fix changes no assertion; it points a live one at the node it always claimed to check.
  `draft.mjs` was as filed — note text only
  · the lane also reverted just the two lines and reproduced `draft`'s tail click-timeout
  unchanged, which is how we know that flake is pre-existing rather than caused here

- **#361** — Turn on the ledger-lint hook we built and never switched on · P1 ·
  dogfood/reliability · origin: **loop** · 15m · **the evidence is two incidents tonight, four
  hours apart, both mine**: a `tasks.md` write introduced a lint ERROR and the commit went
  through anyway, because the lint run and the `git commit` were in the same shell command and
  the error scrolled past above the commit's own output. Once it was a next-id mismatch, once
  it was prose quoting the origin marker literally so lint counted two markers. Both were
  caught on the NEXT lint run and both needed an amend
  · **the fix already exists, shipped, tested, and switched off.** #138/#156 delivered
  `plugins/ud-dreamwork-hooks/hooks/posttooluse_ledger_lint.py`, which lints `questions.md` and
  `tasks.md` **in the same turn as the write** — before the commit, while the agent that
  mangled the file still holds the context. That is precisely the window both incidents fell
  through. Measured: it is referenced in neither `~/.claude/settings.json` nor
  `~/.claude-w/settings.json`, and DREAMWORK.md carries Load lines for
  `ud-dreamwork-worktrees` and `ud-dreamwork-github` but not for the hooks plugin
  · **it needs his consent and cannot be self-granted**, which is the whole reason it is off:
  #138's entry set a scope gate because the plugin writes to his Claude Code config, and the
  plugin's own design requires a DREAMWORK.md Load line before either hook does anything
  · rec: he adds the Load line, then `python3 plugins/ud-dreamwork-hooks/install.py --print`
  is reviewed before `--apply` (idempotent, timestamped backup, refuses to clobber) · asked in
  questions.md · **blocked on that consent**, not on any code
  · a discipline change is the weaker half of the same fix and needs no permission: never put
  a lint run and a `git commit` in one command — redirect lint to a file, read the exit, then
  commit. Doing that from now on regardless of his answer
  · **landed `6575473` — he answered `apply` at 05:38 and it ran at 05:39**, exit 0, backup
  `~/.claude/settings.json.bak-20260728T053957`
  · verified against a snapshot taken before the write rather than against the tool's own
  report: non-hook keys byte-identical, his c2c `PostToolUse` group preserved exactly, no
  pre-existing group lost, and exactly the two promised groups added
  · so the window this closes is now closed: the ledger lint runs in the same turn as a
  `Write|Edit`, before the commit, while the agent that mangled the file still holds the context


  · related: **#387**
- **#363** — lint's landed-but-open WARN cannot tell a forgotten fold from a live lane · P3 ·
  tooling/honesty · origin: **loop** · 10m · reported by dreamer-264-boundary as report-only ·
  `check_landed_still_open` says an entry under Open has a close/merge commit and asks the
  reader to fold it or cite the sha — but tonight the same message fired for `#334`, which is
  another session's *live* lane mid-flight, and for `#264` an hour after its design merged
  while its ask is legitimately open. Both are correct behaviour and neither is a forgotten
  fold · **the gap is in what a reader can conclude**: the message reads as an accusation, so
  a coordinator sweeping lint output must go and check each one by hand, which is the cost the
  check exists to remove · rec: name the discriminator the check already has access to —
  whether `status.json` says an agent owns that task id, or whether the entry was modified
  more recently than the commit — and soften the wording when it does. Small, and it should
  stay a WARN either way
  · **REC WITHDRAWN 2026-07-28 02:46, by trying to build it.** The discriminator would have
  been **wrong**, and the way it fails is the finding: #334's work merged at `ecc1f44` **01:39**,
  so from that minute the WARN was correct and the entry was a forgotten fold. Its worktree
  survived for another hour. A liveness signal — a worktree naming the id, or `status.json`
  saying an agent owns it — would therefore have printed *"another lane is mid-flight"* for a
  full hour after that stopped being true, which is worse than the blunt message: a
  softened WARN is one nobody re-checks
  · **and the check was never the problem.** It fired correctly all three times. What went
  wrong is that a coordinator overrode it **from memory** — "that is another session's lane" —
  three times across four hours, and was right only the first time. A cleverer message cannot
  fix a reader who is already sure
  · **so the real gap is upstream and it is a hole in the single-writer rule.** Another session
  landed #334 and correctly did not touch `tasks.md`, because the ledger has one writer. Its
  work therefore sat done-but-open with **nothing at all telling that writer it had landed** —
  the report went into its own session, not here. The single-writer rule has no delivery half
  · rec, replacing the withdrawn one: **treat this WARN as authoritative and never override it
  from memory** — check git, which takes one command — and give the single-writer rule a
  delivery half so a foreign session's landing arrives rather than waiting to be noticed.
  `#357`'s ambient counts are one end of that; the other is that a session which lands work it
  cannot fold should leave a line in `.dreamwork/inbox.md`, which is already the channel
  everything else reports through
  · **both forgotten folds tonight were found by a check, not by a person** (#330 and #334),
  and the third case — #264 — was silenced properly by citing its sha. The mechanism works;
  the habit around it did not
  · **landed the reader-facing half `28ac5ac`**: the WARN now carries `%cI` and `%cr` from the
  same `git log` it already ran, so it reads *"#334 (`755b497` 2026-07-28 01:39, 3 hours ago) is
  under `## Open` …"*. Deliberately NOT a softening — the entry withdrew that — it is the one
  command the rec told the reader to run, run for them, so an override from memory has to be made
  against a printed age. Red first; the test derives the expected stamp from `git log` rather than
  writing a literal, and asserts the sha survives so the age is added evidence and not a swap
  · **the delivery half is split out as #381** and is the larger, real gap


  · related: **#381**
- **#362** — Nothing compared status.json's queue with the ledger, so it drifted · P2 ·
  tooling/reliability · origin: **loop** · 20m · found by dreamer-264-boundary while measuring
  for #264, and the numbers are the argument: `queue` summed to **115** while `parse_ledger`
  read **123** open, and `current_task_ids` was `[]` while three agents named their `task_ids`
  · both restate what `tasks.md` already knows, and `lessons.md` (#306) says to assume that
  two files holding two halves of one fact have already drifted — they had, in both fields, and
  eight tasks of drift accumulated across one night of hand-maintained edits with nothing
  measuring it · the second one is a live bug beyond the drift: `file-formats.md` says `/tasks`
  badges rows from `current_task_ids`, and `check_status_task_ids` validates member *types* so
  `[]` lints clean — #281 would have shipped badging nothing
  · landed `4ce04e0` — `lint.check_status_agrees_with_ledger`, WARN on both, contract in
  `file-formats.md`, red-proved first against the real drift as it actually stood (both WARNs
  fired; restoring only the queue half isolated one) and then with five discriminating
  fixture injections · **WARN not ERROR is deliberate**: this file is a best-effort projection
  the loop is told must never block a tick, so a momentary lag mid-increment is truthful and
  crying red on it would punish the honesty the file exists for
  · the drift itself was hand-fixed at 02:06 before the check landed, which is why the red
  proof had to reconstruct it from the recorded values rather than observe it

- **#379** — A refusal no longer swallows the advisory it had already computed · landed
  `12d17ad` · origin: **loop** · `render` raised on the component violation before
  `grid_warnings` ran, so a source with both faults showed the error, and the author fixed it,
  rebuilt, and only then learned about the dead grid track
  · **the entry's own rec was to collect warnings before raising rather than reorder the
  checks, and that is what landed**: the `warn(...)` loop moved above both `raise`s. Priority
  unchanged — a refusal still refuses and still writes nothing
  · red first, and the red was discriminating: the test asserts the refusal really was the
  component rule (`"documented component" in str(exc)`) before asserting `warned == []`, so it
  cannot pass on some earlier gate making the grid check unreachable for an unrelated reason.
  It also derives the column count from the template at runtime rather than writing `4`
  · verified no restamp: rebuilding an artifact after the change is byte-identical, because
  `template_stamp` digests the template and not this module · related: **#378**

- **#380** — `check_cited_shas` said nothing on four different exits, and one fired · landed
  `8d7de88` · origin: **loop** · found by a flake, not by anyone reading the code: one full-suite
  run failed `test_a_dead_cited_sha_warns`, then 25 isolated runs and a full re-run passed and no
  single other test file reproduced it — so the check had declined to run and left no row naming
  which exit it took. Its own docstring already stated the principle the code broke
  · fixed all four, and the LEVEL is the discrimination rather than the silence: WARN when `.git`
  is present and git failed anyway (a real anomaly), OK when the target simply is not a repository
  · **the red proof found a second defect nobody had noticed**: `zip(shas, stdout.splitlines())`
  absorbed a short answer from `--batch-check`, and with the answer truncated to one line the
  check reported *"2 cited commit(s) all resolve"* having examined one — the dead sha was in the
  tail it never read. Now compares the line count and refuses to conclude
  · 5 tests, all red first, three induced at real seams (empty `PATH`, a `.git` gitdir pointer to
  nowhere, a non-repo target) rather than by patching; the one that patches asserts git really
  answered for both shas before truncating, so it cannot pass on an injection that never landed
  · two existing tests encoded the silence as intended — `test_every_sha_missing_says_nothing` and
  `test_a_target_that_is_not_a_git_repo_is_silent` — and their names were the tell; both replaced

- **#370** — `/answer` and `/comment` truncate `questions.md` in place ·
  **closed `ea9d7d9`** · P0 · durability bug · origin: **loop** · both routes opened his
  questions file in plain write mode, and truncation happens at open — so anything stopping
  the write before the flush left the file holding half the new text, on the two routes that
  carry his words · `atomic_write_text` (temp + `fsync` + `os.replace` + parent `fsync`) had
  been thirty lines above them the whole time, in use by `/ask`
  · **the proof induces a real failure instead of mocking durability**, which is what the
  design's own "kill at named seams" rule requires: `RLIMIT_FSIZE` set just above the file's
  current length makes the longer post-answer write fail partway through a real `write(2)`.
  `SIGXFSZ` must be ignored first or its default action kills the runner and reports as a
  crash rather than a red
  · discriminating red on both routes: the file came back holding truncated NEW content
  ending in the payload's own padding instead of the original, and the handler thread died so
  the connection dropped with no response · the transport error is swallowed in the test
  helper on purpose, so the red says *"his questions file was damaged"* and not
  *"RemoteDisconnected"* · the cap is derived from the fixture's length plus the append size,
  never pinned · `file-formats.md` states the durability contract in the same commit
  · **one self-inflicted red**: the explanatory comment quoted the construct the check greps
  for, so the check found the explanation of the bug. Third time prose naming a parsed token
  has tripped its own checker

- **#277** — Let departing UI elements blur and liquify before they travel ·
  **closed `1e3ce1b`** · P2 · visual/motion · origin: **human** · **human via watch 17:49**,
  D1 approved 2026-07-28 02:51 · built by his grok peer in a worktree (`458a4d0`, `a98e940`,
  `bd077e8`) · `.pregone` is a 180ms dissolve on the single existing ghost — blur 0→8px,
  opacity 1→0.8, 2px drift — then `.gone` departs as before; commits skip the phase because
  their gesture is grow-and-fall and 2px up would fight 14px down
  · **the visual gate was the deliverable and the peer correctly declined to claim it**;
  coordinator pixel/geometry review: handoff continuous across the class swap (blur
  7.976→7.995, opacity .801→.800, drift −1.994→−1.999), drift peaks at exactly −2.0px, corpse
  gone at 1082ms against the 1.1s bound, reduced motion satisfied **structurally** — no ghost
  is created at all, so the phase cannot run
  · that review found what 13 mechanical checks could not: `.pregone` peaked at `blur(8px)`
  while `.gone` declared `blur(6px)`, so **the corpse un-blurred as it left**, getting crisper
  while departing — a partial reversal of the dissolve, invisible to a `blur ≥ 5px` assertion
  because 6 > 5 throughout. Fixed by raising `.gone` to 8px and pinning `.commit.gone` to the
  6px it already inherited, on the selector that already overrode transform: no new class, and
  the commit gesture computes identically · guard gained a 14th assertion that blur must not
  decrease during departure · **an ORDER cannot be checked by an end state**, which is why
  `dreamfade.mjs` is per-frame: both end states are identical either way

  · **the departure half merged `0b3512e` (2026-07-28 05:59), and the peer merged it itself
  after I asked it to hold.** Recorded plainly because the reason for the hold was not
  ceremony: the browser guards are this repo's only verification, and at load 40-125 on 16 cores
  the motion guards fail *deterministically* — so a "15 guards green" measured under load is not
  evidence either way. **The merge is kept**: verified independently at 06:00 by me — 887 tests
  pass, `lint.py` clean, and the merge touched only `dreamfade.mjs` and `watch.py`, so it was
  disjoint from the two `#263` lanes live in the tree. Not pushed
  · **owed run discharged 06:07: `PASS dreamfade`**, and it did not need a quiet box after all.
  It ran at load **37** and passed, which is *conclusive* rather than merely encouraging — the
  load failure mode here is a dropped intermediate frame, so load manufactures false **reds**,
  never false greens. So a green under load is stronger evidence than a green on an idle machine,
  and waiting for quiet would have bought nothing. Worth remembering the next time I hold
  something for a quiet box: **ask which direction the noise pushes the verdict first**
  · one claim of the peer's was checked and was wrong in a harmless way: it reported `dreamfade`
  was in `DEFAULT_GUARDS` "before my branch, another lane added it too". It added the line
  itself in `6ddec36` at 03:48. No collision either way — but it is the reason a peer's report
  gets verified rather than folded, and this is the cheap end of that lesson
- **#347** — A review artifact's nav breaks words mid-syllable when the header is long ·
  **closed `405092f`** · P2 · review tooling/visual · origin: **loop** · one missing
  declaration: `.topactions a` had no `white-space:nowrap` while every sibling in the top rail
  carried it · fixed in the frame with nowrap plus an ellipsising min-width, so the next author
  cannot author their way back in
  · **its own spec was hollow for an hour and this is the lesson worth keeping**:
  `getClientRects().length === 1` on that anchor cannot see the bug, because `inline-flex`
  keeps the box ONE rect while the text wraps inside it — it reported `1` for four visibly
  broken labels. The instrument that discriminates is a `Range` over each WORD, skipping words
  containing `-` or `/` where a break is correct typography
  · and the first red-proof of that instrument came back GREEN, because rewriting labels
  through the DOM does not reproduce the wrap — the scaffolding stands in front of the bug.
  The discriminating red comes from rebuilding the nav FROM SOURCE
  · `dev/capture/artifactwrap.mjs` builds its fixture through `review_artifact.py`, so the real
  template and builder are what get measured · related: **#372**

- **#372** — The review template squeezes tables at mobile instead of scrolling them ·
  **closed `405092f`** · P2 · review tooling/visual · origin: **loop** · `.scroller` was
  `overflow-x:auto` around a table with no `min-width`, so it shrank until words broke inside
  cells and the container never scrolled — the one job it existed for · fixed with
  `min-width:max-content`
  · measured on the shipped `task-transition-boundary.html` at 390px: **16 → 0** mid-word cell
  breaks, and the scroller went from `358 = 358` (not scrolling at all) to `3976 vs 358`
  · checked with #347's word-`Range` instrument, because a break inside a cell is invisible to
  any end-state assertion · related: **#347, #466**

- **#364** — The #346 artifact still asks four questions he has already answered ·
  **closed `405092f`** · P2 · docs/accuracy · origin: **loop** · the page he opens to rule on
  the task store had been overtaken by his own 01:23 ruling, stale in four measured places ·
  a one-way sync from `task-store-schema.md`, which was already correct — no decision was made
  in the artifact · verified in the rendered pixels rather than the diff, because
  `review_artifact.py check` reports `current` on a page whose text is wrong
  · **the general problem outlives this instance**: an artifact is a snapshot of a question,
  and the moment he answers it the page he answered from becomes a false record. Nothing
  checks that

- **#284** — De-emphasise directory paths in file-view headings · **closed `197feef`** ·
  P2 · UI polish · origin: **human** · **human via watch 18:33**, approved 23:46 (`rec H1`)
  · built by dreamer-284-252 at `aba33e0`, merged `6d94e40`, guard registered `197feef`
  · `.htitle` is a real `<h1>` carrying the basename; the parent path is a **keyed crumb**
  (`.fdir`) so it travels on the existing route transition rather than getting motion of its
  own; `.fcopy` is a real `<button>` reading `view.param`, described by
  `aria-describedby="fdir htitle"` so it announces as the full path in reading order · long
  paths wrap and are never ellipsised, as he required
  · **the finding worth keeping is a GREEN RED-RUN**: deleting `.fcopy:focus-visible` left the
  focus check green, because Chromium's own default ring satisfied "an outline is drawn" — the
  check was asserting the browser rather than the page, and on this dark surface that default
  computes to `rgb(16,16,16)`. It now resolves `--accent` at runtime and compares. #375 exists
  because the same pair-selector shape is elsewhere on the page
  · a second check was hollow before it shipped: `scrollWidth <= clientWidth` on an inline box
  compares `0 <= 1`, so the wrap proof passed over an ellipsis, over a nowrap, and over a page
  with no path at all · related: **#252**

- **#252** — Render Markdown files on `/file` · **closed `197feef`** · P2 · feature ·
  origin: **human** · **human via watch 15:17**, approved 23:39 (`rec` = M1) · built by
  dreamer-284-252 at `ae4215f`, merged `6d94e40`, guard registered `197feef`
  · Rendered/Source is a **route**, parsed once in `routeOf` and written once in `navigate`'s
  url, so `?view=source` deep-links and a copied link preserves intent · the switch is two
  ordinary internal links inside a `stable` crumb keyed `fview:<path>`, with `.on` held out of
  the html so the group survives a mode change and `paintFileMode` slides the shared `.sgind`
  · Source is the pre-existing `<pre>${esc(text)}</pre>` and is asserted to hold **no element
  children at all** rather than "no `tok-` span", which would pass on any other rewrite · scroll
  ratio restored via `contentBottom()`
  · its recorded blocker was stale and was corrected when it started: the entry said blocked on
  #158, which had landed at `5c45d83`
  · **#351 collides with this precisely**: turning off `white-space:pre-wrap` on `<pre>` now
  also affects the Source pane, so #351 needs an explicit render-plain condition
  (`isMarkdownFile(param) && mode === 'source'`), and the pytest check
  `assertNotIn("tok-", watch.PAGE)` must be NARROWED to the Source path rather than deleted
  · related: **#284**

- **#377** — Nothing checked that a guard file is in `DEFAULT_GUARDS` · **closed `2db39f5`** ·
  P2 · dogfood/tooling · origin: **loop** · #117 named this once and it had happened **four
  times**: `filehead` and `fileview` arrived with seven named red proofs each and were left
  unregistered on purpose ("one line, still not mine"), and `fileimg` (#336) and `qfade` (#326)
  had been outside the list since the day they were written · all four PASS when invoked by
  hand, which is exactly why nobody noticed — in a report, a guard that WORKS and a guard that
  RUNS look identical
  · `lint.check_guards_registered` now reports both directions (a file with no entry gates
  nothing; an entry with no file survives a rename) and deliberately does **not** classify:
  `lint.NOT_GUARDS` is hand-maintained, so a new `.mjs` forces one cheap decision — register
  it, or say why it is not a guard. That decision is the whole value, since all four misses
  were made by someone who never had to make it
  · all four guards registered and run through the runner: PASS filehead, PASS fileview, PASS
  fileimg, PASS qfade · 45 registered, each with a file

- **#334** — `burndown.mjs` hand-rolls the reporter the plan cites it as a model for ·
  **closed `2747c8d`** · P3 · chore · origin: **loop** · from #327:
  `dev/capture/burndown.mjs` kept its own `checks`/`ok`/exit handler while `#281`'s plan cited
  burndown as the guard-writing precedent — so the plan pointed new work at the outdated idiom,
  and it was not in #324's fifteen so the sweep would have missed it · converted to
  `report.mjs` with its own crash injection, exactly as #324 does · merged `ecc1f44`
  · **landed by a DIFFERENT session and folded here an hour later**, which is the interesting
  part and is now #363's real content: that session correctly did not touch this file (the
  ledger has one writer), so its work sat done-but-open with nothing telling the writer it had
  landed. `check_landed_still_open` was in fact right from 01:39 onward — the coordinator read
  its WARN as "another lane is mid-flight" from memory, three times, and was wrong after the
  first

- **#330** — A guard run should not dirty the tree it is verifying · **closed `a617606`** ·
  P3 · tooling/dogfood friction · origin: **loop** · `provenance.mjs` wrote its four evidence
  plates into the COMMITTED path `.dreamwork/review/evidence/provenance-coverage-217/` on every
  run (byte-different each time: 248500 vs 248101 for the same screenshot), so `just guards`
  left four modified PNGs behind · that was not untidiness: a dirty tree is the signal the
  worktree-cleanup contract reads to decide whether a finished agent has unsaved work, and
  #316's procedure keys off `git status --porcelain`, so guard churn manufactured false
  positives in the check that protects other agents' work
  · resolved on the **keep** branch this entry itself offered, not by gitignoring: the plates
  are #217's evidence of record, so they stay committed, the guard writes only to `OUT` like
  every other guard, and a deliberate `just provenance-evidence` recipe refreshes the committed
  set · merged `17d2f97`
  · **folded late, and by a check rather than by anyone noticing**: it landed and sat under
  `## Open` until `check_landed_still_open` named it. The same forgotten-fold class as #346's
  unfolded answer, arriving from the other end of the file — which is two instances in one
  night and the argument for #357's ambient counts, not for trying harder

- **#366** — lint catches an answer sitting in the section reserved for the unanswered ·
  **landed `6db36f7`** · P2 · tooling/reliability · origin: **loop** · filed AFTER landing, and
  that is itself the finding: the id was cited in `lint.py`, `test_lint.py` and the commit
  message while the ledger's next id was still 366, so for one commit the code referenced a
  task that did not exist · caught by reading lint's own `next id` line, not by any check —
  nothing verifies that an id cited in source has an entry
  · what it does: WARNs when an answer-tagged bullet sits under `## Open`, with the **age** in
  the message rather than only the fact, because a fold on the next tick is legitimate and an
  ERROR inside that window would cry wolf on correct behaviour · and WARNs separately when two
  answer bullets share one timestamp, naming #274, since the duplication is upstream of the
  file write · both proved on the real pre-fold file (`git show 5041fa1:…`), then six
  injections, three discriminating to a single test
  · **its first version came back GREEN on the real file**, which is the durable part: it read
  `_parse_entries(…, "Open", False)` and looked in `body`, but #340's fix makes an answer
  bullet there a CONTRIBUTION — tag stripped, author label carrying it — so the parsed form
  cannot say whether a bullet was an answer or a note. The reader hides the one fact the check
  needs · it is the **interim half of #357**: it fires when someone runs lint, and he asked for
  ambient
  · related: **#467**
- **#336** — `/file` must show an image, not its bytes as mojibake · **closed `203ee06`** · **P1** ·
  **next-up** · dashboard bug · origin: **human** · **human via watch `do-next`
  2026-07-27 23:00**, typed from the page it happened on
  (`/file?p=.dreamwork/review/evidence/review-note-reply-unclear.png`): *"viewing
  images should work. this renderes as binary ascii like: ..."* followed by the
  actual U+FFFD soup · **diagnosed, so the implementer starts from the cause**:
  `/filedata` (`watch.py:7885`) is the only file-content endpoint and it does
  `read_text(full)` → `json.dumps({"path", "content"})`, while `read_text`
  (`watch.py:6147`) opens with `encoding="utf-8", errors="replace"` — so every
  byte that is not valid UTF-8 becomes `\ufffd` and the client renders the result
  in a `<pre>`. His paste IS that replacement character stream · it also
  truncates at `limit=200_000`, so the 248KB evidence PNGs he was reading are cut
  off as well as corrupted · **this is not only about images**: any binary file in
  the tree renders as plausible-looking garbage rather than saying what it is,
  which is the quiet-wrong-state DREAMWORK.md forbids · scope: detect type
  (extension AND magic bytes — an extension alone is a guess), serve raster
  images from a byte endpoint confined by the SAME `resolve_confined` gate as
  `/filedata`, render `<img>` in the file view, and for a non-image binary say
  what it is (type, size) with a download affordance instead of dumping bytes —
  detail ranked, never withheld · **the security call is load-bearing and must be
  made deliberately, not defaulted**: a raw-bytes endpoint that echoes a guessed
  `Content-Type` turns `.svg` and `.html` in the tree into stored XSS against the
  dashboard's own origin, and #276/#275 are actively considering LAN and public
  exposure · so serve inline ONLY an allowlist of raster types
  (`png|jpeg|gif|webp|avif`), send everything else as
  `application/octet-stream` with `Content-Disposition: attachment`, and never
  reflect a client-supplied type · SVG is explicitly OUT of the inline allowlist
  and the entry says so because the next reader will want to add it · obeys
  `transitions.md` for however the image arrives in the view, and
  `watch-design.md` for its framing · **blocked on `watch.py` being free** —
  `fade326` holds it for #326 right now; this is next in line behind it


  · **landed 2026-07-28 01:12** — `detect_file_kind` requires an allowlisted extension
  AND matching magic bytes; images come from a new `/filebytes` behind the SAME
  `resolve_confined` gate as `/filedata`; any other binary gets a panel naming its type
  and size with a download link. SVG stays out of the inline allowlist
  · **the security posture was re-verified adversarially by the coordinator**, not
  accepted from the report: `.svg`/`.html` resolve to kind=text and can only be served
  `application/octet-stream` with an attachment disposition; a PNG-magic file carrying
  an SVG script payload is served `image/png`, safe because `X-Content-Type-Options:
  nosniff` is present; an SVG payload with a `.png` extension and no PNG magic falls to
  the attachment path
  · **the agent reported a GREEN RED-RUN rather than hiding it**: the brief's "flip the
  allowlist to include svg and watch the test fail" did NOT fail, because the magic gate
  catches it. Correct behaviour, real gap — nothing could fail on an allowlist-only
  widening, closed in `345252c` with a test that fails on either single-table change,
  since the realistic accident is a reader editing the two tables declared four lines
  apart and forgetting magic
  · **THIS ENTRY'S OWN PREMISE WAS WRONG and the agent caught it**: it claimed the file
  is 248KB and over the old 200_000 `read_text` cap. It is **153065 bytes** and always
  has been (added at that size in `cbbb222`), so the truncation half never bit him — the
  bug he saw was pure mojibake. The 248KB belongs to `provenance-desktop.png` in a
  different evidence subdirectory; two files were conflated when this was filed.
  Truncation is still proved, separately, with a synthetic >200KB PNG deriving the cap
  from `read_text.__defaults__` rather than hard-coding it
  · served bytes byte-identical to disk: 153065 bytes, sha256 `312f4ea4…`, verified
  independently · 790 passed + 54 subtests on master, `just audit-styleguide` passes
  because `watch-design.md` gained its section in the same commit, and the coordinator
  ran the `fileimg` guard itself on port 39894 (PASS)

- **#350** — lint refuses a ledger citation whose commit does not exist ·
  **closed this commit** · P2 · reliability · origin: **loop** · found by the maintenance
  rotation's self-review, not by anyone noticing · **#323 made a cited sha load-bearing**:
  an entry that stays open after a landing proves the choice is deliberate by naming its
  commit, and every fold writes one — but nothing checked that the sha RESOLVES, so a dead
  citation is silent in both directions (a reader following it finds nothing, and
  `check_landed_still_open` cannot tell a wrong sha from an honest one)
  · **the live instance**: `#302` cited `f0f4e2a`-merge while the work is at `08cd931` —
  the worktree branch's sha, unreachable after the merge. That is the general hazard, since
  the sha an agent reports is from the tree it worked in, so the rule is **cite the sha on
  the branch you merged INTO**
  · **two looser rules were measured and both are wrong**, which is why the discrimination
  is the design: every backticked hex token flags 94, of which 6 are pure-digit PIDs
  (`1246815`, `251691418`) that are valid hex; a landing keyword within 40 characters still
  flags `fade326`, a c2c peer ALIAS of seven hex digits, because the nearby keyword
  introduces the sha *before* it. Requiring the keyword to immediately introduce the token
  gives 37 citations, 1 dead, precision 1-in-1 across 237 entries
  · WARNs and never ERRORs, silent on a non-repo target, and silent when EVERY sha is
  missing (a fresh clone is not a ledger that is entirely wrong) · shape in
  `file-formats.md`, four discriminating red proofs each failing a different subset

- **#348** — Teach the build-time highlighter `sql`, since schema designs are what it is
  read for · **closed `d22fb09`** · P3 · review tooling · origin: **loop** · found writing #346's design, whose
  code blocks are `CREATE TABLE` statements · #339 supports python json bash javascript
  html, and correctly leaves an unmarked or unsupported block plain rather than guessing
  — so #346's schema renders as plain text, which is the designed behaviour and not a bug
  · the case for adding it is that `.dreamwork/docs/plans/` will accumulate schema work
  through #294/#346, and a `CREATE TABLE` block is exactly where a colour tells a reader
  where the constraint ends · small: one `_scanner` spec plus the token classes that
  already exist (`kw`, `str`, `num`, `com`, `typ`) — no new CSS · the existing acceptance
  tests generalise: the round-trip must recover the source, and `test_the_supported_
  languages_are_the_advertised_set` pins the list against the template's own prose, so
  adding a language without documenting it fails
  · **landed 2026-07-28 00:54** — `(?i:…)` scoped to the sql keyword/type patterns
  rather than `re.IGNORECASE` on the shared master pattern, which would have reached
  every other language's spec and made `_PY`'s `typ` match `none`. `com` before `op`
  (`--` opens a comment, `-` is also an operator) and `kw`/`typ` before `var`, both
  commented and both pinned by a test
  · **#346's artifact was deliberately NOT marked `language-sql`** — its block is
  shorthand, not DDL, and mislabelling it to manufacture a consumer would be #339's
  never-guess rule broken in the other direction
  · the advertised-set test was strengthened while here: it now DERIVES the language
  list from the template's own authoring comment and compares it to
  `SUPPORTED_LANGUAGES`, so supported-but-unadvertised (invisible to the next author)
  and advertised-but-unsupported (renders plain, no explanation) both fail
  · three red proofs, each naming its production line; the FIRST ATTEMPT at them was
  invalid and is recorded in `lessons.md` — `git checkout --` as the injection-undo
  reverted the uncommitted feature itself, so two proofs failed because the feature
  was absent and read as clean discriminating reds

- **#339** — Syntax highlighting for code blocks in the review-artifact template ·
  **closed `be8812e`** · P2 · review tooling/visual · origin: **human** · **human via watch `add-idea`
  2026-07-27 23:19**, typed from `/review?p=threaded-topic-chats-v2.html`: *"in html
  codeblocks like here with TopicChats, we should make syntax highlighting available
  as part of the template. and if the template doesn't have code blocks, we can take
  some from here"* · **his premise measured, and half of it is already done**: the
  frame (`review-artifact.template.html:86-87`) already styles `code` and `pre`, and
  those two rules are **byte-identical** to the ones in the artifact he was reading —
  so there is nothing to copy across; what is genuinely missing is only the
  HIGHLIGHTING (no `hljs`, no token classes anywhere in either) · **the binding
  constraint is offline-cleanliness**: artifacts are self-contained and inline
  everything, so a CDN highlighter is out — the choice is build-time tokenising in
  `review_artifact.py` (emit `<span class=…>` at build, ship only CSS; no runtime
  cost, no script, degrades to plain text) versus a small inlined highlighter (works
  on content authored later, but adds script to every artifact) · rec **build-time**,
  because an artifact is a frozen record and highlighting it at read time is work
  done repeatedly for a result that cannot change · needs an explicit language marker
  on the block (`<pre><code class="language-…">`) rather than guessing — a
  misdetected language colours the code wrongly, which is worse than not colouring
  it · **the consequence to plan for, and it is immediate**: `template_stamp()` is a
  digest of the frame's bytes, deliberately so that editing the frame changes it
  without anyone remembering to — so this change makes **every templated artifact
  stale**, and #329's just-landed lint check will WARN on each until rebuilt · today's
  twelve are `untemplated` and stay silent, but `#254`'s artifact is being built right
  now and would go stale the moment this lands, so the task includes rebuilding
  whatever was templated in the interim · that is not a defect in either change; it
  is the staleness mechanism doing its job, and the entry says so because the next
  agent will otherwise read the WARNs as a regression
  · **landed 2026-07-28 00:33** — build-time tokenising, as recommended: `tok-`
  spans emitted by `review_artifact.py`, CSS in the frame, no script in the
  artifact, plain text for a block with no `language-…` marker. Its own
  prediction held exactly: the frame change staled the templated set, that set
  was #254's artifact alone, and it was rebuilt in the same branch — the twelve
  `untemplated` ones stayed silent as the entry said they would
  · **the agent died without reporting**, so this was validated from the diff;
  that turned up one defect (nothing could fail on the token re-escape, fixed
  in `a2be1e3` with a discriminating red) and one thing worth keeping: lint's
  `13 artifact(s), none stale` cannot distinguish a finished rebuild from a
  skipped one, because it is silent on `untemplated` by design — the per-file
  `review_artifact.py check` is what answers that, and it was run

- **#343** — lint rejects an unrecognised author tag in questions.md and
  answers.md · **closed `335ecf0`** · **P1** · reliability · origin: **loop** · a threaded bullet whose
  prefix is not in `NOTE_TAGS` or `ANSWER_TAGS` (`watch.py:6770`, `:6810`) is not a
  contribution: it falls into the entry **body** and renders with its raw tag showing
  and no author label — the #340 defect, reachable by a one-word typo
  · **evidence is a live near-miss, not a hypothetical**: the coordinator wrote
  `- **Note (loop, …)` on the P0 #263 question that gates five lanes, an hour after
  writing a merge message explaining that `Answer (loop, …)` was the #254 bug for
  precisely this reason. Knowing the failure by name did not prevent it, which is the
  argument for a check rather than another line of documentation
  · **and lint currently passes over it**: measured — with the bad tag in place
  `python3 lint.py` reported `clean (0 warning(s))` and `questions.md 14 open, 31
  answered`, because it counts entries and never inspects an author tag. So the only
  thing standing between a mistyped tag and his words vanishing from the page is
  whether the agent voluntarily ran the parser
  · the tags are asymmetric by channel, which is what makes the typo natural: the
  human's is `Note (human, via watch, …)`, the loop's is `Follow-up (loop, …)`, and
  `Note (loop, …)` reads perfectly reasonable while matching nothing
  · **the check must consume `NOTE_TAGS`/`ANSWER_TAGS` from `watch.py`, never restate
  them** — a second copy of the tag list is a second thing able to disagree with the
  renderer, and the whole defect class is renderer-disagreement · WARN vs ERROR is a
  judgement call: ERROR is defensible because there is no legitimate reason to write
  a tag the renderer does not know, and a silent drop of his words is the loudest
  thing in `DREAMWORK.md`'s "nothing fails quietly"
  · red-prove by the discrimination that found it: correct tag → parses as one
  contribution with `author='loop'`; change one word → **zero contributions and the
  raw tag in the body**. Assert both halves in one run, and derive them from the real
  tag tuples so the test cannot pass on a stale literal
  · **it found THREE live instances on its first run against the real file**, which is
  more than the near-miss that prompted it: three `- **Reply (loop, …)` bullets, each a
  loop reply sitting directly under one of his notes — the exact shape of the #254
  screenshot, and the gap #254's spec had flagged in the abstract. Measured through
  `watch.py`'s own parser rather than asserted: fixing the tags took the file from **28
  parsed contributions to 31**. His own tags were untouched (13 `Note (human,`, 23
  `Answer (via watch` before and after)
  · verification went three ways rather than once, because a single red cannot show a
  suite is not moving together: breaking prefix recognition fails 4 tests, breaking the
  single-word head that excludes prose fails exactly 1, replacing the `watch.py` import
  with a hardcoded copy fails 3 · the first red was also DISCARDED as invalid — all 9
  tests failed on `AttributeError` because the helper read `rep.rows` as objects when
  they are tuples, and a red that comes from the harness proves nothing about the check
  · **precision was measured on live data and the check tightened because of it**: it
  first flagged 4, one of which was prose (`- **Four early asks, all applied
  (2026-07-25)** —`). A test was written for that, watched fail, and the pattern narrowed
  to a single leading word plus a trailing colon — 3-in-3. The stated cost: a tag mangled
  so badly it loses its colon is missed, while the wrong-NAME case this exists for keeps
  the shape and only changes the word
  · related: **#446**
- **#326** — The answer box sits on a black band instead of the text fading ·
  **P1** · **next-up** · bug/visual · ~30m · origin: **human** · **human via chat
  with a screenshot 2026-07-27 21:40** (verbatim: *"the black stuff around the
  answer box to emulate the fade thing is ugly. the text itself should fade, not
  be covered by fake fade. and the buttons and text box shouldn't have anything
  behind them (should look like it did before)"*) · **located exactly**:
  `watch.py` ~1065-1069, `.qdock > .qa > .qcompose::before`, introduced by
  `4e5ea01` as #305 (c) · it is an absolutely-positioned band from `top:-2rem` to
  `bottom:0` at `z-index:-1` carrying
  `linear-gradient(to bottom, transparent, var(--bg) 2rem)` — so it fades over its
  first 2rem and then runs **solid `var(--bg)` for the whole height of the compose
  box**. That is both halves of his complaint in one rule: the 2rem OCCLUDES the
  live text instead of fading it, and the solid remainder is the panel behind the
  textarea and buttons · **two asks, and they are separable**: (1) nothing behind
  the box/buttons — that is deleting the band, and it restores the pre-#305 look
  he asked for; (2) the text itself fades — that is a mask on the scrolling text ·
  **the structural catch that makes (2) more than a one-liner, and the reason
  #305's author chose the band**: `.qcompose` is `position:sticky` INSIDE `.qa`,
  so a mask on `.qa` fades the ANSWER BOX along with the text. The author's stated
  objection ("a mask over the scroller cannot be told about the box, and would dim
  his last line at the end") is only half right — the `atend` state already
  detects the body ending at the box and is what currently zeroes the band's
  opacity, so the last-line problem is already solved machinery; the box-fading
  problem is the real one · rec: give the question body its own element inside the
  scroller and mask THAT, leaving `.qcompose` unmasked — it matches his words
  ("the text itself should fade") and it is the same mirrored gesture as the top
  edge, which already masks correctly via `--qfade` · **do not author a second
  idiom**: the top edge's registered-property fade is the reference, the bottom is
  it mirrored, and `transitions.md` governs the arrive/depart of the edge · the
  `@media (max-width:900px)` block and the reduced-motion block both reference the
  band and must be updated in step, or the narrow layout keeps a rule for an
  element that no longer exists · **watch.py is held by ccc-glm52-269 (the P0
  draft-loss fix)**, so this starts when that releases; he has authorised native
  subagents again for important work, and this is a visual-quality change on the
  surface he reads proposals on
  · **merged `7cdfc61`** (agent `fade326`, 5 commits `97c6a87..894e341`) · the question's
  BODY scrolls, not the whole card: `.qbody` wraps it and is `display:contents`
  everywhere else, so no box means no mask and no scrollport, which is what the narrow
  layout wanted back · `--qfoot` joins `--qfade` because the two ends lift on different
  states and one property could not hold both
  · **its three GREEN red-runs are documented in `qfade.mjs` where the next agent will
  read them**, each naming what the check could not see: the band is painted inside
  `opacity:.82` so `--bg` never reached the framebuffer and a 'no pixel may be --bg'
  guard could not fail at any wording; a `.qbody`-named override in the guard itself
  stood in front of the injection; and a mean over the region diluted the effect to
  1.2% and 11.9% inside tolerance. `pair()` now opens with 'never compare their means'
  and asserts worst-row ratios with runtime preconditions
  · **one guard red in the full run and it was NOT this branch**: `gitrow`'s two motion
  assertions, which sample rAF frames. It references none of the four things #326
  changed, its identical `closing` assertion passed in the same run, the justfile
  documents contention reds at its head, and `gitrow` alone on a quiet machine PASSES.
  Filed as #345

- **#324** — Convert the remaining 15 tail-printing guards to the shared
  reporter · P3 · chore · ~40m · origin: **loop** · goal: a crash must never
  read as a clean sheet ← DREAMWORK.md *Nothing fails quietly* · #192 landed
  `dev/capture/report.mjs` and converted three (`status`, `hfit`,
  `pushhealth`); this is the mechanical remainder: `headertravel reflow qacard
  docktarget noteprop oneinput regroup popbg typing wisp states confirmation
  thread health answers` · **this is now a sweep and not a rate problem**, which
  is the whole reason #192 built a module first — a new guard inherits the
  sentinel by importing it, so this list can only shrink · each conversion is
  the same four steps (import `makeReporter`, `declare({drives, traceWindow})`,
  drop the tail print, call `finish()` at the end) and each needs its own crash
  injection: **the checks accumulated before the throw must survive**, which is
  the property, and a conversion that changes a guard's normal verdict is a bug
  in the conversion · `declare` throws on a missing/empty half, so a converted
  guard cannot silently omit its coverage · cheap to parallelise across agents by
  file, since the guards do not import each other
  · **merged `7c44d28`** (agent `ccc-glm52-324` on `@oc-glm52`, 6 commits
  `d306b10..6e55d0c`) · all 15 remaining tail-printing guards converted, none skipped,
  374 PASS 0 FAIL, and each proved by its OWN crash injection — checks recorded before
  the throw now print with a sentinel FAIL where the same throw printed nothing
  · **the overlap with #326 was `qacard.mjs`, not `reviewsplit.mjs`** as assumed at
  dispatch; #324 never touched reviewsplit. Merge order still mattered, for a different
  file. `git merge-tree` reported no conflict and the `qacard`, `reviewsplit` and
  `qfade` guards were re-run against the MERGED tree anyway — all three PASS — because
  a clean textual merge of output plumbing onto a rewritten probe proves nothing about
  behaviour

- **#335** — lint catches an open entry that declares ITSELF completed · merged
  `21c6224` (agent commit `be0c1b0`, `ccc-glm52-335` on `@oc-glm52`) ·
  P2 · tooling/correctness · origin: **loop** · found by tripping over #261, which
  sat in `## Open` for a full day carrying *"completed **2026-07-26 16:21**"* in
  its own metadata run · #323 cannot see this class: it compares the ledger
  against git and warns when a `close(#N)`/`merge(#N)` commit is not cited, so an
  entry closed in PROSE with no such commit is invisible to it · **the naive rule
  is wrong and this was measured, not guessed**: grepping the 108 open entries for
  a completion keyword near a date or sha returns FIVE hits and only ONE is real —
  precision 1-in-5 · so the discriminator is POSITION, not vocabulary: a
  completion marker inside the entry's **metadata clause** (the ` · `-separated
  run immediately after the title, where `P1`, `origin:` and `owner:` live) is a
  self-declared close; the same words deep in the prose body are not · **the four
  false positives are the required fixtures, each a different way of being
  legitimately open**: `#275` (*"research + design landed `4b49ecb` … ask open"* —
  one half done, the human's ask still pending), `#283` (*"**L1 completed
  2026-07-27 00:21**"* — a sub-stage of several), `#269` (*"LANDED `0366706`"* /
  *"merged `e383492`"* — the acute half landed, the broader scope deliberately
  open), and `#281` (*"(merged `9c00cd2`)"* — a sha cited for a sub-finding inside
  an in-progress entry) · a check that flags any of those four is worse than no
  check, because the loop learns to ignore it · assert all four stay silent AT
  RUNTIME in the check itself, not in a comment · WARN not ERROR, same reasoning
  as #323 · red-prove against #261's exact text restored to Open
  · **validation found a live second instance**: run against the real ledger rather
  than its fixtures, the check WARNed on `#247` — open, and carrying `completed at
  ba03c1f` in its metadata run. Folded to `## Recently landed`, after which the check
  goes quiet. And it produced NO false positive on tonight's entries, which is the
  harder half: the ledger has since gained long ` · ` chains and #252's own text says
  "#158 has landed at `5c45d83`" — a completion keyword within 40 characters of a sha,
  held silent by position, which is the whole property the task exists for
  · **two follow-ups it reported rather than fixed**, both correctly left alone:
  `file-formats.md` needs a section stating the metadata-clause contract (it owned only
  `lint.py`/`test_lint.py`), and its `;`-or-over-50-characters body boundary is a
  heuristic — sound on all 161 real entries, every failure a WARN naming the phrase, but
  if it ever must be exact the ledger needs a real title/body separator rather than a
  ` · ` chain that fades into prose. That is a design call and it is the coordinator's

- **#247** — Harden answer-state IDs and deletion guard · **completed
  `ba03c1f`** · P2 · test/bug · origin: **loop** · missing server aid omits both
  persistence/FLIP attributes; exact-content twin ordinal limit documented;
  deletion guard strengthened · 439 tests, lint, focused answers browser and
  independent Standards/Spec PASS · pushed/deployed · late review follow-ups
  #250/#251 correct the unkeyed click-motion gap and true old-node proof
  · **moved here 23:47 by #335's new check, which is the first thing to notice
  it.** The entry had sat under `## Open` carrying `completed at ba03c1f` in its
  own metadata run — the #261 bug class exactly, and #261 was a P0 that sat a
  full day the same way. Nothing else could see it: `check_landed_still_open`
  compares the ledger against git and there is no `close(#247)` commit to cite,
  so it was structurally invisible until position became the discriminator
  · **the coordinator twice measured that this entry was NOT in `## Open` and was
  twice wrong**, nearly rejecting a correct check on the strength of its own
  ad-hoc regexes; `watch.py`'s `parse_ledger` settled it by returning 247 in the
  open-id set. That is the second time tonight a hand-rolled scan over this file
  disagreed with per-id set membership and lost — see `lessons.md`

- **#329** — `lint.py` reports a review artifact whose frame drifted behind the
  template · merged `8661db7` (agent commit `be1be46`, `ccc-glm52-329` on
  `@oc-glm52`) · P3 · tooling · origin: **loop** · from #325's report ·
  `review_artifact.py check` has answered current/stale/untemplated since #325 and
  exits 1 on stale, but nothing RAN it, so drift returned through a different door
  · two design calls, both about noise: **WARN never ERROR** (a stale frame is
  legible and recoverable — the words are there, the page renders, the fix is one
  rebuild) and **silent on `untemplated`** (the twelve unmigrated artifacts would
  otherwise fire every run, which is the noise that hides the finding that
  matters) · `file-formats.md` corrected in the same commit: it said *"Checked by
  `test_review_artifact.py`, not by `lint.py`"*, the opposite of what is now true
  · **coordinator-verified independently, not accepted**: built a real artifact
  through the real builder, stamp-swapped a genuinely stale one, confirmed the
  WARN named exactly it; confirmed all three silence conditions; then injected two
  separate bugs and watched WHICH tests moved — killing stale recognition failed
  exactly the 2 positive tests with all 7 silence tests green, and reversing the
  untemplated decision failed 3 including the dogfood test over this repo's real
  twelve, proving that test non-vacuous · 748 passed + 54 subtests (was 739)

- **#261** — Recover reported 14:47–15:17 Web UI submissions · P0 · incident ·
  origin: **human** · completed **2026-07-26 16:21** · human confirmed use of
  live `localhost:35111`; exact words were not found in either server
  `submissions.log` or browser IndexedDB, copied Brave Sessions/Session Storage/
  localStorage/form state, Pi transcript, Git history/unreachable-object scan,
  clipboard history, or the still-open tab's final DOM textarea dump · this is
  **not evidence that no submission occurred**; it means no available witness
  retained the exact text · live tab/process were preserved through recovery ·
  prevention continues in #260/#262/#263
  · **moved to landed 2026-07-27 22:57**: it had declared itself *completed
  2026-07-26 16:21* in its own metadata run while sitting in `## Open` for a
  full day. #323's check could not see it — that check compares the ledger
  against git and this entry was closed in PROSE, with no `close(#261)` commit
  to name. The gap is filed as #335.

- **#332** — `status.json` says WHICH tasks the loop claims, as integers ·
  closed `d05d442` · P2 · contract/data · origin: **loop** · from #327 · added
  `current_task_ids` (top level) and per-agent `task_ids`, both arrays of ints, so
  #281's "in progress" badge can decide PER ROW — prose in `task` cannot answer
  that, because one sentence routinely names several ids in different states · the
  increment's real content is `lint.py`'s `check_status_task_ids`: a quoted
  `"#281"` is worse than an absent field, since it is present, is a list, passes
  `STATUS_TYPES`, reads right to a human, and matches no row at all — silently ·
  `type(v) is not int` rather than `isinstance`, because `isinstance(True, int)` is
  True and the sibling `in_flight` was ALREADY written as a bool by this loop
  (#327 found the dashboard rendering `doing: true`) · red DISCRIMINATED (four
  positive cases red, integers-accepted and absent-silent green), then re-proved by
  injecting quoted ids into a copy of the REAL status.json · **both readers
  checked**: `dreamhub.py` projects a fixed per-agent subset and renders no task
  rows, so it needs neither field and was deliberately left unwidened · the
  renderer half stays with #281

- **#327** — the /tasks plan re-verified against the tree it will be built on ·
  merged `a2f4d82` · origin: **human** · **human via watch 2026-07-27 21:47** · his
  ask, and warranted far beyond tidying: 103 commits had landed since `f2c1bd0` ·
  every coverage number had moved; `present:false` was documented as "0 today" and
  is 87 of 238 records, so **the pruned path is the common case** and those records
  must stay in the payload or the landed filter lies; §2.1's stated reason for
  building on `ledger_entries` became FALSE when #315 widened `LEDGER_ENTRY`, and
  the review found the TRUE reason rather than just flagging it stale; §4.3
  disagreed with its own arithmetic · **and the part a drift framing would have
  missed**: his rulings contradicted the plan in three places, because the proposal
  had argued against what he chose — the plan now builds the one-column page, makes
  sort a control, and carries "in progress" with the `Reported: Xm Ys ago` hover ·
  twelve-increment structure survives unchanged · the `<style>` block was left
  untouched, so #325's hour-old fidelity assertions still hold · five out-of-scope
  findings filed as #331-#334 (one challenged by the coordinator, substantiated,
  and correct) · **this entry was itself caught stale under `## Open` by #323,
  minutes after #323 landed** — the fifth stale-open of the evening and the first
  found by a machine rather than by someone noticing

- **#323** — lint compares the ledger against git · landed this commit · origin:
  **loop** · `check_landed_still_open` WARNs when an open entry's id has a
  `close(#N)`/`merge(#N)` commit the entry does not name · the discrimination was
  the design: #269 and #275 are legitimately open after a landing, and a prose
  keyword rule was tried and MEASURED wrong first (all three cases contain the
  word "landed"; #315's is describing the problem it fixes) · the rule that works
  is "git names a commit the entry does not", which works because a deliberate
  partial already cites its sha — #269 and #275 both did unprompted, so the rule
  records a habit rather than inventing a marker · it found a fourth stale-open
  while being measured for: #315 itself, now folded · WARN never ERROR, and a
  non-git target is silent · red re-proved by injection on the final test;
  documented in `file-formats.md` in the same commit

- **#315** — both ledger readers widen to combined open heads together · landed
  `7764be4`, merged `4b69196` · origin: **loop** · `LEDGER_ENTRY`, `LEDGER_ID` and
  `check_ledger_sections` widened in ONE commit as the task required, since
  widening either alone makes the two readers disagree on any ledger holding a
  combined open entry · `parse_ledger` gained `_open_ids`; the section check counts
  ids rather than lines; the pinning test needed no change because the patterns
  stayed identical · the latent defect it fixed had no live instance (103 = 103
  when measured), so the red proof was the deliverable: a combined head filed in a
  fixture, watched missing by both readers · **it immediately earned its keep** —
  the widening surfaced a real stale-open (#156 open AND named in the landed
  roll-up `- **#138/#156**`), which lint reported as `duplicate id(s) [156]` ten
  minutes after landing, and that is also the error my own fold had just created
  · this entry was itself left stale under `## Open` after landing and was found
  by #323's measurement — the third such case in one evening, which is what
  finally made #323 worth building rather than filing

- **#325** — the review artifact is a template with a builder · landed `2365cb0`,
  merged `e798e07` · origin: **human** · **human via watch 2026-07-27 21:38** ·
  the shape was decided by measurement: the
  drift across twelve artifacts is entirely in the stylesheet (five font stacks,
  eight page backgrounds, twelve inline stylesheets, zero shared source) while the
  section markup is consistent — so template-owns-the-frame /
  author-owns-the-words, and the obvious copyable block would have put the drifted
  bytes back under per-author memory · sources at `.dreamwork/review/src/<slug>.html`
  (a subdirectory because `watch.py`'s `list_reviews` is a non-recursive `*.html`
  listing that would otherwise serve him a half-built page); stamp derived from the
  template's bytes so staleness never depends on an author judging their own change
  visible; `check` is three-valued (current/stale/untemplated) because two values
  would have to lie about the twelve pre-existing artifacts · fidelity proven three
  ways — style block extracted programmatically and inserted unedited, runtime
  parsed comparison of every shared selector and palette token including inside
  `@media`/`@starting-style`, and Chromium geometry matching to a tenth of a pixel
  at 1180px · 41 new tests (730 total) · SKILL.md now points at the builder, which
  was the one thing deciding whether this took effect · migration of the twelve
  deliberately NOT filed and I agree: they record what was proposed and when, and
  rebuilding would restyle pages he has already read and ruled on · this task's own
  proposal source sits unbuilt at `.dreamwork/review/src/325-review-template.html`
  by design — an artifact with no paired question would appear on his dashboard
  from nowhere, and its one open call (migration) is answered
  · related: **#429, #433**

- **#192** — Guards printed from a tail handler, so a crash read as a clean
  sheet · P2 · landed 2026-07-27 · chore · ~35m · origin: **loop** · goal: a
  crash must never read as a clean sheet ← DREAMWORK.md *Nothing fails quietly* ·
  9fcbcda, merged 5e95884 · `dev/capture/report.mjs` + three adopters · **landed
  as the entry's own rec asked — the PATTERN via a shared reporter, not fourteen
  files** — because the count was 17 of 39 eighteen minutes before it was
  re-measured as 18 of 40: `pushhealth` landed twenty minutes earlier without the
  sentinel, since there was nothing to inherit it from. A sweep would have been
  stale within a day; the remainder is #324 and can now only shrink · all four
  obligations are structural, not remembered: the exit-handler sentinel, absence-
  first `present()`, no count offered at all (so a guard cannot report one), and
  `declare({drives, traceWindow})` which THROWS on a missing half · **the
  dependency on #148 was measured and was not real** — that runner is the justfile
  recipe, this is a module the guards import · **committed by the coordinator on
  behalf of ccc-glm52-192, which finished and exited before committing**; reviewed
  and re-verified from scratch rather than accepted from its report · crash proof,
  re-run independently: unconverted printed `FAIL guard threw:` and **0** feature
  checks, converted printed **14 PASS** plus `FAIL the guard threw before
  finishing its checks` · **and it corrected its own task's measurement**: 17 of
  the 18 print NOTHING on a crash (the true clean-sheet class) and `pushhealth` is
  the lone variant — an `uncaughtException` handler makes it loud about the crash
  and silent about the 14 checks it had already proven

- **#314** — `audit-styleguide` asked the wrong question, so its misses were a
  mix · P3 · landed 2026-07-27 · tooling/correctness · ~40m · origin: **loop** ·
  goal: a check should not accrue failures for work it was never about ←
  DREAMWORK.md *Nothing fails quietly* · 3068b43, merged bff36ec · the filter was
  "did this commit touch `watch.py`?" — but that one file holds the HTTP server,
  the git and ledger parsers AND the whole UI (#124 is the split), so it could
  not tell a stylesheet change from a regex fix · now filters on the DIFF: does
  the commit touch a line inside one of the eight UI-bearing module constants,
  with **the boundaries resolved AT the audited commit** via `git show
  <sha>:watch.py` parsed with `ast`, never at HEAD — line numbers move, and
  judging last week's commit with today's numbers is the expiry-dated-literal
  trap · four named false positives (`06eacad`, `1d089ad`, `db1a1bc`, `e51da7e`)
  drop out as parser/server work · `Styleguide: n/a` kept only as a narrow,
  loudly-reported hatch, used by no commit · **it did not go green**, and that was
  correct: `cdb89df` remained a true positive, which #320 then explained (the
  window's unit) and #321 finally closed (the doc naming the task)

- **#321** — The styleguide audit had no honest way to close a miss once the
  window shut · P2 · landed 2026-07-27 · tooling · ~30m · origin: **loop** ·
  goal: a check must have a path from red to green that is not "move the
  goalposts" ← DREAMWORK.md *Nothing fails quietly* · 89d6991 · **the mechanism
  is NOT the one this entry proposed.** It asked for a tracked remediation file
  mapping `<missed sha> -> <documenting sha>`; measuring first found a better
  signal already present in history: `34131c7`'s added `watch-design.md` lines
  literally name `#302`, and `cdb89df`'s subject is `fix(#302)`. So **a styleguide
  entry that NAMES a task id documents that task's commits, at any distance** —
  falling out of the `type(#id):` convention the repo already keeps, needing no
  new file, no trailer, and nothing remembered at commit time (which is what
  ruled the `Styleguide: n/a` hatch out as a general remedy). The doc stating
  what it covers is better evidence than a mapping file asserting it · credits
  print as loud DOC-BY-ID lines, never a silent pass · **measured for hollowness
  rather than argued**: over the pre-baseline it credits 7 and leaves 4 MISSES
  standing, including `a6e98cc` (#273) and `bfa561f` (#181), the two verified by
  reading as genuinely undocumented; its four #290 credits are one feature
  documented once in `2f0e7ea` (86 lines, a whole run-mode section), spot-checked
  not assumed · three red proofs, one per rule · `just audit-styleguide` exits 0
  for the first time since #313

- **#320** — The styleguide audit's window counted commit rate, not documentation
  adjacency · P2 · landed 2026-07-27 · tooling/correctness · ~35m · origin:
  **loop** · goal: a check must fail for the reason it names ← DREAMWORK.md
  *Nothing fails quietly* · f51c2bf · #314 fixed WHICH commits are asked the
  question and left the window counting RAW commits; the coordinator lands a
  ledger update between every increment, so `cdb89df` and the commit documenting
  it sat SIX commits apart with not one of the six touching `watch.py` or a
  styleguide file — genuinely adjacent, reported as undocumented · the unit is
  now relevant commits (touching `watch.py` or a styleguide file) · **that change
  alone is a monotone weakening** — a strict superset of the old search — and
  measuring rather than reasoning caught it: applied by itself it took the
  pre-baseline from 11 misses to **0**, silencing `a6e98cc` and `bfa561f`, both
  verified BY READING as real undocumented UI changes, with `a6e98cc` credited to
  `f17f307`, a UI commit whose entry documents its own #250/#251 work · so it
  ships with a RESTRICTING companion rule: the search may not reach past another
  UI commit, and a neighbouring UI commit never supplies the entry even when it
  carries a styleguide file, because that entry is its own · only the two real
  shapes pass — same commit, or a nearby docs-only commit · three red proofs, one
  per rule · **the fourth finding is the one worth keeping**: the red proof for
  the unit change initially came back GREEN, because the test fixture built the
  relevant-commit list itself instead of calling `window_positions` — a check
  sitting outside the single decision it was named for, which is this repo's
  recurring failure mode and not a new one

- **#190** — The loop's push channel to him is dead, and only the dashboard can
  say so · P1 · landed 2026-07-27 · bug · ~25m · origin: **loop** · 9b7ce77,
  merged 49297df, wired 92b243e · `status.json` gains
  `push={at,channel,ok,detail}`; the dashboard renders `ok:false` as a `--warn`
  rail naming the channel, the reason and the age, above `awaiting_human` because
  a loop that cannot push cannot deliver that list either · **three states are
  distinguishable FROM THE DATA** — absent key, `ok:true`, `ok:false` — and the
  guard asserts the three fixtures genuinely differ before asserting any render,
  so "renders nothing" in two of them cannot pass over the feature · new guard
  `dev/capture/pushhealth.mjs`, 15 PASS, verified independently by the
  coordinator rather than accepted from the report; now in DEFAULT_GUARDS (40) ·
  **it deliberately adds no motion**, and that was checked rather than assumed:
  `.stpush` is `border-left:2px solid var(--warn); padding-left:.8rem`,
  value-for-value the structure of `.stneed` and `.qhealth.unreadable`, neither
  of which animates — reusing the existing idiom, not authoring a second one ·
  **the sender half stays out** — #203 established that "ask for more care" is
  not a fix, and the gap here was never a missing fallback: `PushNotification`
  exists, works, and is already the written rule; nothing makes the loop NOTICE

- **#316** — Removing a worktree cannot ask whether anyone is still in it · P2 · landed 2026-07-27 ·
  tooling/safety · ~30m · origin: **loop** · goal: a destructive step should not
  depend on the operator's belief about liveness ← DREAMWORK.md *Nothing fails
  quietly* · found the hard way at 20:00 today: the coordinator concluded an
  agent had exited because `ps | grep opencode` showed only one, removed its
  worktree with `--force`, and the agent was alive — it had committed
  `dev/capture/dismiss.mjs` two minutes earlier and was still running · **the
  commit survived because it was a commit**; anything uncommitted after 19:58
  did not, silently, and `--force` is exactly the flag that skips the question ·
  **the grep could not have worked**: a `ccc` agent's visible process is a `zsh
  -c` wrapper, so the process name never contains `opencode` · the mechanical
  test that does work needs no judgement and is the same shape as #203's
  deleted-cwd rule: **does any live process have this worktree as its `cwd`** ·
  `plugins/ud-dreamwork-worktrees/` already exists and is where this belongs ·
  rec: refuse removal when a process is cwd'd inside, naming pid and command
  line; require an explicit override that says what it is overriding; and
  `--force` must not imply it · red-prove by starting a shell cwd'd in a scratch
  worktree and confirming removal refuses, then that it proceeds once the shell
  exits

  · **out with ccc-glm52-316** in `.worktrees/316-wtsafe` (owns `plugins/ud-dreamwork-worktrees/` only, no guard port) · briefed NOT to share the `/proc/<pid>/cwd` primitive with #203's reaper mid-flight; one primitive with two callers is the consolidation once both land
  · landed `2865f07` (ccc-glm52-316) + coordinator fix · the lifecycle contract
  now asks the PROCESS question before it classifies file state, which is the
  ordering the incident turned on: every existing step was followed, the tree was
  correctly classified disposable-only, and the checklist blessed the removal ·
  verified against the live tree rather than on report — six processes found with
  a do-not-remove verdict and exit 1, clear and exit 0 for an unoccupied dir ·
  **and that live run found a defect the unit tests could not**: a dispatched
  agent's argv CONTAINS ITS WHOLE PROMPT, so one `ccc` process printed thousands
  of characters across many lines and the "one line per process" format stopped
  existing — neither the second process nor the verdict was visible on screen. A
  report that the operator cannot read is not a safeguard, and it is invisible to
  a test that only asserts the right pids were found. Command lines now collapse
  to one abridged line naming how much was withheld (`+6511 chars`), the pid is
  never abridged, and the full text is one command away · red-proved by reverting
  to the raw print

- **#318** — `TITLE_ROUTE` has #302's omission, so `/answers` never says where
  it is · P3 · landed 2026-07-27 · correctness · ~15m · origin: **loop** · found by ccc-glm52-302
  while landing #302, out of its scope and correctly left alone · `TITLE_ROUTE`
  (watch.py ~3076) has no `answers` entry, and the consumer falls back with
  `(TITLE_ROUTE[v.name] || TITLE_ROUTE.dashboard)(v.param)` — so the tab title on
  `/answers` renders the dashboard's route word · **the title is the only part of
  this dashboard that exists while the tab is backgrounded**, which #153 is
  entirely about, so a route that cannot name itself there is worse than it
  sounds · the check generalises from #302's: derive the route set from
  `routeOf`, diff against `TITLE_ROUTE`'s keys, assert presence and not a literal
  title string · red-prove by removing the entry again · same class as #302 and
  #314 — a per-route table gaining a route without its entry
  · landed: `answers: () => 'answers'` added, and the CHECK generalised rather
  than duplicated — #302's test now derives the destination set from `routeOf`
  and diffs all THREE per-route tables, so the class is covered instead of the
  two tables it was written for · **red-proved on the real defect with no
  injection at all**, which is the strongest form available: the test was written
  first and failed with `{'answers'} is not false ... never says where it is` ·
  confirmed in a real browser afterwards, which is the user-visible half the unit
  test cannot see: `/answers` titled `(3) dreamwork/target · stalled` — byte
  identical to `/` — and now titles `… · answers` · `watch-design.md` updated in
  the same commit, and its contract line now says why the list of tables is
  exhaustive: each table's fallback is silent, so a fourth table added there must
  be added to the check or the next omission is invisible too

- **#302** — Give `/answers` its own tint and turbulence seed · P3 · landed 2026-07-27 · chore ·
  10m · origin: **loop** · found by `dreamer-taskspage` during the #281 design
  batch · `TINT` and `SEED` have no `answers` entry, so the route silently
  inherits the dashboard's atmosphere via `TINT[name] || 0` while
  `transitions.md` states every destination has its own seed and tint · small,
  but the page is quietly outside a stated contract, and the same omission is
  what #281 must not repeat for `/tasks` (its proposal already names
  `TINT.tasks`/`SEED.tasks`) · check by reddening on the missing entry, not on
  the rendered colour

  · **out with ccc-glm52-302** in `.worktrees/302-tint` (owns `watch.py` + `test_watch.py`, port 39895); unblocked by #301's merge
  · landed `08cd931`-merge (ccc-glm52-302) · TINT 0.08 / SEED 29, reasoned not
  filled: the warm dialogue family beside `/questions` (+0.14) but quieter,
  because the loop's asks block the loop and must pull him while the human's
  asks are a surface he is already writing into — the pair reads as a gradient ·
  the check asserts entry PRESENCE and derives the destination set from `routeOf`
  itself, so a route added tomorrow is caught without restating the list; a hue
  assertion would pin today's palette · red-proved on each table independently
  with a runtime plural-routes precondition · **`TITLE_ROUTE` has the identical
  omission** — see #318


- **#203** — Guard servers are not reaped · P2 · landed 2026-07-27 · bug · 25m · found 17:40
  when a dreamer went quiet: FOUR orphaned watch.py servers in the guard
  ranges, one up **4.5 hours** serving `dev/capture/fixture` — the most
  confusing possible answer for a readiness probe · exactly what
  `parallel-architecture.md` predicted in writing and what cost
  dreamer-identity 20 minutes · **three consecutive agents believed they
  had cleaned up**, so do NOT fix by asking for more care · rec: bind
  port 0 and let the OS assign (removes the class), probe for something
  only THIS server serves, reap in a trap/finally, log what was started
  and killed · belongs with #148 + #192 in the shared runner · **a guard
  red only under LOAD is worse than plainly wrong** — the first re-run
  exonerates it and teaches everyone to re-run; if the runner ever
  retries, it must SAY it retried (qsec 18:17, prominence at 7ac4f02:
  the trace armed on the click, so it measured its own input latency) ·
  **~21:05**: panels found 39899 held, moved to 39893, and later NAMED
  the holder (pid 2331175, `watch.py --target /tmp/... --port 39899`,
  minutes old — legitimate, not an orphan) · the discrimination rule
  that fell out: TARGET PATH + ELAPSED together are the evidence — a
  /tmp target minutes old is somebody working; the same command on a
  repo target hours old is the orphan class · when a held port is
  found, capture `ss -tlnp` and name pid+command in the report ·
  **a mechanical discriminator that needs no judgement** (2026-07-27
  17:44): `readlink /proc/<pid>/cwd` ending in ` (deleted)` means the
  lane that started it is gone, full stop — target-path-plus-elapsed
  still needs a human to weigh "is 20 hours long", and this does not.
  Found by it and reaped: pid 1652343, `watch.py --target
  dev/capture/fixture --port 39951`, up 21h, cwd
  `/tmp/pi-agent-9f527dd0-…(deleted)` — the outgoing pi lane's, and the
  exact fixture-server hazard above · **two more still up**, both /tmp
  targets that still exist so the deleted-cwd test does not fire: 897036
  (`/tmp/a250/target`, 26h) and 3408270 (`/tmp/revieworder-green/target`,
  20h) · left running deliberately — reaping them is a judgement call and
  the reaper should make it, not a coordinator doing it by hand
  · **out with ccc-glm52-203** in `.worktrees/203-reaper` (owns `justfile` + new files under `dev/`, port 39894) · scoped deliberately: the port-0 half needs `watch.py`, which another agent holds, so the reaper lands first and port 0 follows
  · **reaper landed** `485717c` + coordinator fix `a0354ad` · the first
  deliverable was confirmed rather than assumed: `just guards` already traps and
  kills its own server, and a trap CANNOT be the fix because SIGKILL is handled
  in kernelspace and bypasses the handler — so the orphans are hand-started
  servers and survivors of SIGKILLed lanes · rule 2 (deleted cwd) outranks rule 1
  (old target) on purpose, so the kill decision never depends on a tunable
  threshold; rule 1 reports and can never kill; only SIGTERM; `--all-dead`
  refuses without `--yes` · **it reaped two pids it was told to spare** and
  reported that first, unprompted — both lanes had gone deleted between dispatch
  and its run, so they were mechanically dead-lane rather than the judgement
  calls the brief described; the deployed dashboard, dev server and forum
  instance were verified untouched and alive · the coordinator then found the
  hole its own note pointed at: `is_deployed` was printed and never consulted,
  so a deployed dashboard with a deleted cwd was sweepable — red-proved and
  closed · **the port-0 half remains open**, see #319
  · related: **#424, #461**

- **#317** — `qorder.mjs` is the fifth instance of the frame-count assertion ·
  P2 · guard craft · ~20m · origin: **loop** · goal: a guard must not go red for
  a reason unrelated to the thing it names ← DREAMWORK.md *Nothing fails
  quietly* · #311 converted four guards and named this one in its evidence
  without converting it: `qorder.mjs:242` counts distinct positions and its own
  comment reasons about "one distinct position", and dreamer-reviewsplit
  observed it PASS in small runs and FAIL in the full suite — the signature of a
  threshold that is really a frame-rate claim · **this entry exists because the
  close-out note on #311 pointed at #316, which is the worktree-liveness task
  and has nothing to do with it** — an incorrect cross-reference is how a named
  finding goes missing, so it gets its own id · the conversion is now
  mechanical: `between(vals, first, last) >= 1` with a runtime-derived,
  printed span beside a constant pixel floor, per `transitions.md` "Checking a
  transition" and the four landed examples · red-prove with `transition:none`
  injected and confirm the vacuity precondition stays green in that same run
  · landed: both assertions converted, animated `steps >= 6` -> `partway >= 1`
  and reduced `steps <= 3` -> `partway === 0` · the vacuity precondition was
  already upstream and did not need adding — `movedIn` drops any card that
  travelled under 4px and `moved.length > 0` asserts one survived that filter,
  which is why this file needed no new span check · **the reduced threshold was
  measured before it was chosen, not after**: 51 frames, 2 distinct positions,
  0 part-way, so a strict zero is the contract rather than a coincidence — had
  a layout intermediate landed inside the [first, last] window, zero would
  false-red on correct reduced-motion behaviour · red-proved with a
  `transition:none` style tag injected **into the guard, not into `watch.py`**,
  because another agent holds that file: 0 of 15 part-way fails the travel
  check while the vacuity stays green at 161px and both the past-the-end and
  reduced checks stay green · green three consecutive times

- **#311** — Two motion guards assert a frame COUNT the box cannot supply · P2 · landed 2026-07-27 ·
  guard craft · ~40m · origin: **loop** · goal: a guard must not go red for a
  reason unrelated to the thing it names ← DREAMWORK.md *Nothing fails quietly* ·
  `headertravel.mjs:127` asserts `uniq(f.map(x => x.wrap)).length >= 8` and
  `regroup.mjs:107` asserts `uniq(tops(n.frames)).length >= 6` — counts of
  distinct rounded positions sampled across a .85s transition, so the threshold
  is really "this machine rendered at least N frames" · **proven contended, not
  inferred**: the same commit (`ae2fd58`) failed `headertravel` in a run
  concurrent with a second guard suite (load 53.8, 35 chrome) and PASSED it
  alone minutes later, with `regroup` failing the same way in the same
  contended run · dreamer-reviewsplit A/B'd it five alternating pairs on base
  `f72f730` vs its own HEAD: BASE saw 5, 6, 8, 8, 9 distinct widths — so base
  itself fails three of five — and HEAD saw 5, 6, 6, 6, 7, i.e. #305 costs
  about two rAF frames (a window-tall iframe rasters more than a 74vh one) and
  tips a check already sitting one frame from red · the column TRAVELS in every
  run, 3 to 7 frames part-way, which is the frame-rate-free half of the same
  question · fix is the idiom `lessons.md` already prescribes and `qsec.mjs` +
  `reviewsplit.mjs:145` already implement — count frames strictly BETWEEN the
  two ends with a deadband, not distinct rounded positions · `qorder.mjs` has
  the same shape (its own comment at :242 reasons about "one distinct
  position") and the dreamer saw it pass in small runs and fail in the full
  suite · **the class is wider than frame counts, and both halves are now
  proven on `ae2fd58`**: `morph.mjs:176-179` is the same distinct-position
  count (`uniq(nTops)`/`uniq(nHs)` >= 6, `answer:` mode only), while
  `dismiss.mjs:134` is the OPPOSITE sensitivity — `ops.at(-1) >= 95` asserts
  the fade has FINISHED inside a fixed 700ms sampling window, so starving the
  box makes it red for the reverse reason. Its two neighbours on the same trace
  (`>= 6` opacity values, `>= 4` transforms) got EASIER under the same load,
  because slow frames spread further apart — one trace, two assertions moving
  in opposite directions with load, which is why "some checks passed" is not
  evidence the run was sound · all four (`headertravel`, `regroup`, `dismiss`,
  `morph`) failed in loaded runs and every one PASSED when re-run with fewer
  guards in flight, so the fix must address both shapes: frames strictly
  between the ends for the counts, and waiting on the transition's own
  completion (`getAnimations()`/`transitionend`) rather than a fixed window for
  the terminal states · **the dreamer deliberately did not touch either file**: changing
  another feature's guard to make your own batch green is the move that wants a
  second pair of eyes, and it was right about that · #308 landed the doc half:
  `transitions.md` now splits the part-way rule from the count rule and names
  all three faces as *a motion check must not encode a property of the machine*
  · **increment 1 landed `4ebb011` — `headertravel.mjs`, the reference the rest
  follow.** Both count assertions became part-way counts on `reviewsplit`'s
  `between()` helper, and **the floor is 1, from measurement not taste**: idle
  31 frames / 5 part-way, under six added CPU burners 14 frames / 2 part-way, so
  a floor of 2 sat exactly on the line and anything above 1 is still a bet on
  the frame rate · it also converted the REDUCED-MOTION mirror, which is the
  more dangerous half — `uniq(...) <= 2` is satisfied by a box that sampled a
  real ramp twice, so under load it went HOLLOW rather than red and would have
  passed a reduced-motion build that animated · red-proven with
  `transition:none` injected: all four travel checks at 0 part-way of 20/33
  frames while both new vacuity preconditions stayed green at 415px and
  175.6px, so the red was the contract and not an absent subject · **scope is
  wider than this entry was filed for**: `qsec.mjs:170` (`t.positions >= 8`)
  and `:172` (`distinct(heights) >= 8`) are two more instances — qsec uses the
  part-way idiom for its FADE only (`mid >= 3`) and is half converted · the
  remaining four (regroup, morph, dismiss, qsec) are out with ccc-glm52-311 in
  `.worktrees/311-guards`, holding exclusive guard rights on 39891 · the
  standing risk on the delegated half is that this task LOOSENS assertions, so
  a red proof per guard is the only thing between it and quietly disabling four
  guards — briefed as such · #308 is the sibling rounding half and has landed
  · **ALL FOUR CONVERTED AND MERGED.** increment 1 `4ebb011` (headertravel,
  the reference), then `2275ef9` merged regroup/morph/qsec and `e09f226` merged
  dismiss — each with its own red proof carrying real numbers, coordinator
  reviewed every diff and re-ran all four green on master · dismiss's proof is
  the one worth keeping: a `transition:none` injection catches its two count
  checks at 0 of 2 part-way while the terminal check stays green (an instant
  settle IS settled), so its red needed a SECOND injection — the fade stalled
  at 60% — and only then did "ends fully lit" fail at a settled 60/100 AFTER
  the wait, which is the proof the wait reached a real settled state rather
  than a window cut-off · `e041b9c` corrected two things in `transitions.md`:
  qsec is no longer the half-converted file to avoid, and the never-a-literal
  rule now says which literals it means, because three commits described their
  vacuity floors as "derived at runtime" when the derived part is the printed
  measurement and the floor is a deliberate constant — a pixel span is a
  property of the fixture's layout, not of the box · `qorder.mjs:242` was named
  in this entry as the same shape and is NOT converted; see #317


- **#301** — Teach the ledger patterns to see combined entry heads · P2 · landed 2026-07-27 · bug ·
  25m · origin: **loop** · found by `dreamer-taskspage` during the #281 design
  batch, then re-measured by the coordinator, which narrowed the claim ·
  **proven:** both patterns require `**` immediately after the digits
  (`LEDGER_ENTRY` = `^- \*\*#(\d+)\*\*`, `LEDGER_MENTION` = `\*\*#(\d+)\*\*`),
  so a combined head like `- **#138/#156**` matches *neither* — verified
  directly against both regexes · **live consequence, measured:** the three
  combined heads all sit in the recently-landed section (#138/#156, #250/#251,
  #292/#293), and `parse_ledger` reports #138, #250, #251, #292 and #293 as
  neither open nor landed, so `ledger_series` never records their completion
  and the burndown under-counts landings · **the dreamer's own numbers did not
  reproduce**: it reported 123 vs 118 ids and "arrival, completion and open
  level all wrong right now"; within the open section the two readers agree
  (103 = 103, no combined head is currently open), so the defect is confined to
  the landed section — file the narrow truth, not the alarming version ·
  **hypothesis, not established:** that these ids were never singular in the
  recently-landed section earlier in history (series `landed` = 83 equals the
  current file's mention count, which is consistent with it but does not prove
  it) — the red-first test settles it · also groom the inconsistency it
  surfaced: #156 has an open entry head while appearing in a landed combined
  entry · fix in the shared pattern so `lint.py` and `watch.py` cannot diverge
  (a test pins `ledger_entries` verbatim-identical between them)
  · **landed half merged `1f25243`** (ccc-glm52-301) · a new ids-only bold
  pattern reads every id in a combined mention; live landed set 94 -> 100, and
  the six ids in `**#138/#156**`, `**#250/#251**`, `**#292/#293**` all land ·
  the over-match guard was the load-bearing part and the coordinator
  re-verified it rather than taking the report: a first wider attempt landed
  #96 from the prose span `**#96 stage 1**` · the agent declined the OPEN half
  and was right to — see #315

- **#313** — `just audit-styleguide` is red for everybody on 10 historical
  commits · P3 · landed 2026-07-27 · chore/tooling · ~30m · origin: **loop** · the recipe enforces
  that a commit changing the UI records a styleguide entry within 3 commits;
  ten commits predate or missed that and it now fails for anyone who runs it,
  which makes a green audit unavailable as evidence · oldest first: `db1a1bc`,
  `0c1f5ad`, `a6a7ad2`, `bfa561f`, `a6e98cc`, `fe55cd3`, `7a0ffd5`, `2e92b49`,
  `e51da7e`, `cf33aa6` · none are #305's · two honest options and this needs a
  call, not a guess: **back-fill** the missing entries (real work, and the
  entries would be reconstructed after the fact, which is the thing the audit
  exists to prevent), or **scope** the audit to commits after a stated
  baseline and say so in the recipe · a check that is permanently red teaches
  people to ignore it, so leaving it is the one option that is not available
  · scoped, not back-filled — `45a8c6c`, merged `9d8502c` (ccc-glm52-313,
  worktree removed) · **the brief was wrong twice and the dreamer corrected both**:
  the recipe reports **11** misses, not 10 (the filed list was stale by one at the
  top — `1d089ad`, fix(#304) from 16:36 THIS SESSION, i.e. this coordinator is one
  of the violators), and they are not "months old history" but a 2-day burst,
  2026-07-26 12:13 to 2026-07-27 16:36, after the convention held for ~378 commits
  from `d1df255` · baseline is `1d089ad`, the most recent miss, derived from history
  rather than picked: every earlier candidate still contains a miss and would leave
  the recipe red, so it is the only point from which the enforced window is
  all-green, and it is self-maintaining because the next miss reddens it · the
  pre-baseline count is computed AT RUNTIME each run, not a literal, so it stays
  true as history grows, and the recipe prints what it is not covering plus the
  command to list it — bounding coverage silently would have been one dishonesty
  traded for another · **coordinator re-proved the load-bearing claim rather than
  accepting it**: appended a line to `watch.py`, committed, audit went to exit 1
  with `MISS`, reset, audit back to exit 0, `watch.py` byte-identical · 620 pytest,
  lint clean · it surfaced #314: the filter asks "touched watch.py", which that
  file's shape cannot answer, so the 11 are a mix of real misses and false ones


- **#312** — The command palette lets a phone scroll the whole page sideways ·
  P2 · Web UI bug · ~30m · origin: **loop** · found by dreamer-reviewsplit
  while scoping #305's responsive checks, and deliberately left out of scope so
  #305's suite was not gated on someone else's bug · at a 390px viewport the
  page overflows **122px horizontally on EVERY route**, dashboard included, and
  the overflowing element is `.cmdmenu` · this is shipped behaviour on the
  deployed dashboard, not a regression from #305 · `watch-design.md`'s
  responsive contract says the body must never scroll horizontally, so the
  styleguide already forbids it and no ruling is needed · wants a guard at
  390px that asserts `documentElement.scrollWidth <= clientWidth` on each
  route, which would also catch the next one
  · fixed in `65e9d1e`, merged `c0d6071` · **the root cause was subtler than the
  filing**: the menu overflowed while SHUT, because `visibility:hidden` is not
  `display:none` — the box stays laid out and keeps counting toward
  `documentElement.scrollWidth` on every route, palette open or closed. That is why
  it shipped: nothing looked wrong · `.cmdmenu` now anchors to the ⋯'s right edge
  and opens leftward, clamped by `max-width:calc(100vw - 2rem)` · the reveal is
  provably untouched: that gesture is `translateY(-6px)` + opacity + blur, purely
  vertical, so a horizontal anchor change cannot reach it · guard
  `dev/capture/hfit.mjs`, red-proven by reverting the fix — all three routes fail at
  exactly 122px naming `#cmdmenu`, plus 109px menu-open, while its precondition
  checks stayed green, so the red was the contract failing and not a hollow guard ·
  it asserts the palette exists and the menu is POPULATED before measuring, because
  "no overflow" is otherwise satisfied by an absent subject · **written by a ccc
  glm-5.2 subagent that was KILLED before committing or reporting**; work recovered
  uncommitted from the worktree and validated by the coordinator before landing, and
  its transcript was lost to a `| tail -40` in the dispatch — see lessons.md ·
  620 pytest, lint clean, hfit PASS on master · noted, not filed: the menu's own
  reveal has no motion guard (`cmdcap.mjs` does not reference it), which is
  pre-existing and was not #312's to fix

- **#303** — Make `lint.py` notice a `status.json` that lost known keys · P3 · landed 2026-07-27 ·
  chore · 20m · origin: **loop** · goal: make a silent projection-rewrite loss
  loud ← DREAMWORK.md *Nothing fails quietly* · this coordinator's wholesale
  rewrite of `status.json` at 16:07 dropped `retired_today` (fifteen prior
  lanes' retirements) and lint reported the result **clean**, because a
  projection missing a key is indistinguishable from one that never had it ·
  it caught the estimated future `last_tick` in the same write, so the shape of
  the fix is known: warn when a previously-present key disappears · needs a
  durable notion of "previously present" that does not itself become a second
  fallible truth — simplest candidate is the git-tracked handoff/doc trail
  rather than a new sidecar file, and status.json is gitignored, so decide that
  before implementing · check by reddening on a key removal, not on a schema
  list that would need updating with every new field · **the git-tracked route
  is refuted (2026-07-27 17:15)**: the only git-tracked description of this
  file is `file-formats.md`'s field table, and (a) it does not name
  `retired_today`, so it would have missed the exact incident that filed this,
  and (b) treating it as required would red-flag every fresh target, whose
  status.json is nearly empty by design — the same cry-wolf failure #306 was
  measured against · that leaves two live options, both needing a call: a
  gitignored `.status-keys` memo beside the gitignored file it describes (costs
  `lint.py` its read-only character — it writes nothing today), or a small
  merge-writer so a wholesale rewrite has to be deliberate, which is the
  *remove the opportunity* answer but adds a module and does not detect a
  coordinator who never calls it
  · **call made: the gitignored memo**, `.dreamwork/.status-keys`, one key per
  line. The merge-writer option was rejected as the primary fix because it cannot
  detect a coordinator who never calls it — and this session's own writes were all
  load-modify-dump merges already, so the option would have prevented nothing while
  the incident it was filed for still happened · the entry did not name the
  load-bearing property and it only surfaced while implementing: **the memo must be
  APPEND-ONLY**. Re-recording the current key set each run makes the first run after
  a bad rewrite adopt the reduced set as its baseline — one warning, in the same run
  as the mistake, then permanent silence. Union-only means a lost key keeps warning
  until a human deletes the line, which is the only act that should be able to
  accept a retirement · red-proven by INJECTING the plain implementation
  (`union = current`): exactly one of the nine tests failed, and the other eight —
  including `test_the_real_incident_goes_red` — PASSED over it, so a single-run
  proof cannot see this bug at all · lint.py gains its first write, priced
  explicitly: a write failure WARNs rather than raising, so a read-only checkout
  still lints · 620 pytest (+9), lint clean

- **#308** — Record the whole-pixel rounding trap in `transitions.md` · P3 · landed 2026-07-27 ·
  chore · 10m · origin: **loop** · goal: a motion guard should not be able to
  report a clean ease as a snap ← DREAMWORK.md *Nothing fails quietly* · found
  in dream grooming (#142's batch, one archive from being lost): rounding a
  per-frame trace to whole pixels reported a clean 2.1px ease as a snap, which
  is an instrument bug that presents as a feature bug · the trap is live in the
  idiom, not hypothetical — `reviewsplit.mjs`'s `distinct()` rounds, and it is
  only safe there because its travel assertions require >=60px of movement, so
  the guard whose gesture IS small is the one that will be bitten · belongs in
  `transitions.md` beside how to check a transition, which is where someone
  writing a motion guard is already looking · **blocked while
  dreamer-reviewsplit owns `transitions.md`** — take it after #305 merges
  · **it turned out to be three traps, not one, and the document's own opening
  rule was the source of the other two.** `transitions.md`'s first instruction for
  checking a transition said *assert the count of distinct intermediate positions*,
  which is what `headertravel`, `regroup` and `morph` encode and why all three go
  red on a slow box (#311) · so the bullet is now split: assert the frames you
  captured are PART-WAY (frame-rate-free — a teleport has none at any frame rate),
  and never an absolute count · plus the rounding trap this task was filed for,
  plus the mirror-image fixed-window terminal-state trap `dismiss.mjs:134` encodes
  · all three named as one mistake: **a motion check must not encode a property of
  the machine** — frame count, pixel rounding and elapsed-time windows are all
  facts about the box, and each turns a guard into a load meter that reports its
  findings as feature bugs · the cited idiom was verified in place rather than
  taken on report: `reviewsplit.mjs:148` filters strictly-between with a 3%
  deadband, and `qsec.mjs:157` does the same with no tunable threshold at all
  · landed in `9ba67db`, whose ledger half this entry is — that commit's message
  claimed the close while `tasks.md` still listed it Open, because the guarded
  edit and the commit were chained with `;` instead of `&&`

- **#305** — Read a review document and answer its question side by side · P1 · landed 2026-07-27 ·
  Web UI feature/design · ~75m, **needs splitting** · origin: **human** ·
  **do next via watch 16:34** · sent from `/review?p=tasks-page.html` while
  reading the #281 artifact, so the friction is first-hand and the page he was
  on is the page to fix · **his words, kept whole:** "should be able to scroll
  the question alongside a review document, and the answer/add note input
  should stay glued to the bottom in line with the bottom of the review
  document. Above that the text from answering should fade out close to the
  answer box (unless it is at the end of the question text body). use intuition
  and judgement to fit the webui aesthetic + remain consistent with design +
  produce an excellent design. Additionally, there should be an invisible
  vertical bar between review doc and question being answered that allows
  dragging left/right to change width of review doc and question block. We also
  can extend the height of the review doc and RHS column if the height of the
  window allows." · six distinct asks, and the last three are separable:
  (a) question scrolls alongside the document rather than after it,
  (b) the answer/note input is glued to the bottom, aligned with the document's
  bottom edge, (c) question text fades toward the input, suppressed when the
  body already ends there, (d) an invisible draggable divider resizes the two
  columns, (e) both columns may grow taller when the viewport allows,
  (f) the whole thing must read as this page's own aesthetic, not a generic
  split pane · **a correction to this entry's first reading, made before
  starting:** the coordinator initially called the width question a gate on
  #281 Q1 and that was wrong. Q1 asks whether **/tasks** may become two-pane;
  this is **/review**, which `watch-design.md` already names as *the* width
  exception and which already renders the question beside the document via
  `buildReview(name, q, d)` and `?q=`. So this restructures an existing wide
  page rather than creating a second exception, needs no ruling from him, and
  the two are separable — though landing it does weaken Q1's "a second
  exception is how one column becomes two" argument, which is worth saying
  when he answers ·
  the divider needs a persisted width, a keyboard-operable equivalent (a
  drag-only affordance is not reachable), a reduced-motion story, and a
  narrow-viewport fallback that stacks rather than shrinking both to unusable ·
  the fade is a gradient over live text, so it must not clip the last line or
  make copied text lossy · obey transitions.md and watch-design.md · likely
  three increments: the two-column shell + splitter, the glued input + fade,
  then the height/responsive behaviour · **the three-increment brief was wrong**
  (17:19) — the feature has no working intermediate, so it lands as one; see
  lessons.md · increment 1 committed in `.worktrees/305-review-split`
  (`a0cc24a`, 667 insertions) and coordinator-reviewed: 25 guard checks, each
  shown red against a build broken in the way it names, nine injections · it
  also fixed a latent bug of its own: a scroll offset assigned to a node the
  live-tick swap is one statement old clamps to zero and reports nothing, so
  his typed draft's scroll position had been silently discarded on every tick
  since #118; now a `putScroll()` that reads back and retries (#179's rule
  applied to the other thing a restore hands back silently) · **the class was
  audited and is contained** (17:28): `restoreReviewFrame` preserves the live
  browsing context rather than recreating the iframe, so its `scrollTo` never
  meets a fresh node, and the `setSelectionRange` calls are not
  layout-dependent — no third instance, do not re-audit · **MERGED** at
  `ae2fd58` (a real merge, two parents; all five branch commits are ancestors),
  plus `19c6aca` removing a diff3 base marker the coordinator's own
  conflict-marker sweep did not name · merged tree verifies at **611 pytest +
  54 subtests, lint clean**, and both parents' `lessons.md` content was proven
  present by set containment rather than by absence of markers · guards: the
  two motion FAILs seen in the first run (`headertravel`, `regroup`) were
  CONTENTION, proven by re-running the identical commit alone — see #311, which
  carries the evidence · the dreamer was retired at 18:44, harness-confirmed
  stopped; worktree clean apart from gitignored `__pycache__`
  · **verification, stated honestly**: 611 pytest + 54 subtests, lint clean,
  and all 40 guards pass on this commit — but NOT all in one run. The full
  solo suite was 38/40 with `dismiss` and `morph` red; both PASS in a
  two-guard re-run of the identical commit, exactly as `headertravel` and
  `regroup` did after the concurrent-suite run. Four load-sensitive guards,
  and which ones go red depends on what else the box is doing — the box sat
  at load 40-90 (16 cores) throughout from other agents' work. `reviewsplit`
  itself, 47 checks including the coordinator's line-406 fix, passed in every
  run. See #311, which now carries both failure shapes and the evidence ·
  dream archived; worktree and branch removed

- **#309** — Coherence re-read of SKILL.md + initialization.md · P3 · origin:
  **loop** · landed 2026-07-27 · the recorded DREAMWORK.md routine, run by a ccc
  glm-5.2 subagent in a worktree and validated line by line before anything was
  applied · **one real contract bug**: SKILL.md said the ledger is "open tasks
  only" while `## Recently landed` is load-bearing — `parse_ledger` returns both
  id sets from it, #304's `check_ledger_sections` ERRORs on a split disagreement,
  the burndown's completions come from its git history, and #306's stale-ask
  check reads the landed set. A coordinator following SKILL.md literally would
  have broken all four quietly, and the phrase predates the checks that made it
  costly · **one internal contradiction**: the field list a filer actually reads
  omitted `origin`, the one field `lint.py` ERRORs on, so filing from the
  Commands section alone minted an entry that failed lint next increment · both
  fixed; the growth note (the Subagents steering block is the candidate for the
  next lean pass) is recorded, not acted on · everything else checked out —
  #290, #216, #304, #307 and the worktrees plugin are coherent across all four
  files, the 11-step init lists match, and no named file/tool/flag is stale ·
  audit at `.dreamwork/review/evidence/309-skill-coherence-audit.md`

- **#310** — Audit `dreamhub.py` against `dreamhub-design.md` for drift · P3 ·
  origin: **loop** · landed 2026-07-27 · a ccc glm-5.2 subagent in a worktree,
  five findings all validated by the coordinator against the cited lines before
  anything was applied · all five were the DOC being wrong, not the code: the
  hub renders `agents[].owns` while the writer's contract omitted it; "not yet
  wired into `just test`" had been false since #134 (`09e3397`) while
  `dev/hub/README.md` already assumed the wiring; `agents[].in_flight` has TWO
  readers and was in neither doc; `deployed.py` is path-loaded and was named as
  a dependency nowhere, with `just deploy` snapshotting `watch.py` only; and one
  guard was credited with covering four contracts it covers two of · **one claim
  of its own corrected on review**: it read `kind`/`awaiting_result` as
  consumed by nothing, but `watch.py` folds every unnamed agent key into "the
  rest" deliberately — *"Whatever is LEFT, not a second known list"* — so the
  field list is a menu, not a whitelist, and that is now stated where someone
  would otherwise prune it · audit kept at
  `.dreamwork/review/evidence/310-hub-drift-audit.md`

- **#248** — Decide whether answers records need persisted IDs · P3 · design ·
  origin: **loop** · landed 2026-07-27 (`1fc4bc7`) · **ruling: defer, with a
  trigger** · a ccc glm-5.2 subagent measured rather than speculated — 0 Open,
  6 Answered, 0 exact-content twin pairs, matching `lint.py`'s own count — and
  found the decisive fact: reordering two byte-identical entries is a no-op on
  the file, so the "identity lost through reorder" the entry worried about has
  no observable consequence, because the records ARE the same identity by every
  field the schema treats as meaning · the only identity consumer, #238's
  open-state restore, already fails closed (#247), so the wrong outcome a
  durable id would prevent does not occur · revisit on: a human-reported
  collapse where he cares which twin survived, a workflow treating same-day
  same-text entries as intentionally distinct (#229 is the candidate), or a
  second aid consumer that is not fail-closed · analysis at
  `.dreamwork/docs/answer-record-ids.md`

- **#307** — Make the doc map's plans row checkable · P3 · origin: **loop** ·
  landed 2026-07-27 · the map's one row that enumerates a *directory* had
  drifted to 8 of 14 plans, silently, because nothing reads prose — six plan
  docs a reader of the map could not learn existed · kept the enumeration
  (detail is ranked, never withheld) and made it a shape: `check_doc_map_plans`
  WARNs both ways, stem-on-disk-not-listed and listed-with-no-file, contract in
  `file-formats.md` · **red first on the live drift**, not on a fixture

- **#306** — Notice an open question whose subject has already landed · P2 ·
  origin: **loop** · landed 2026-07-27 · `check_landed_asks` warns when an open
  `questions.md` entry names **only** task ids that are in the ledger's landed
  set, so a shipped feature can no longer read as an open gate the way #290 did
  for ~15 hours · **the rule is ALL named ids landed, not any, and that was
  measured before it was written**: the naive any-landed rule was run against
  this repo first and fired on the real `#229/#270 topic chats v2` question,
  where #270 had landed but #229 was still open and the ask was genuinely live
  — a check that cries wolf on a live question teaches the reader to ignore it ·
  WARN not ERROR, deliberately: an amendment thread on a landed task is
  legitimate and this cannot tell one from a forgotten fold, so it names the id
  and asks for a fold or a reason · the real cure — one write path that folds
  the ask when the answer is recorded — stays with #263; this is the detector ·
  **found while building it, and fixed as part of it:** `test_lint.py`'s `run()`
  helper hand-maintained its own copy of the check sequence and had drifted six
  checks behind `main()` (`check_answers`, `check_landed_asks`, `check_run_mode`,
  `check_plugin_commands`, `check_submissions`, `check_dreamwork_frontmatter`),
  so a new check was exercised by nothing while its tests passed — the exact
  checks-that-cannot-fail shape this repo keeps rediscovering. Both now call one
  `lint.run_checks`, which cannot drift from itself · red-first: the two
  positive checks failed on the absent function, and the all-vs-any decision was
  proven by running the naive rule and watching it flag the live question ·
  604 passed + 54 subtests, lint clean

- **#304** — Anchor the ledger section split to line starts · P2 ·
  origin: **loop** · landed 2026-07-27 · a section is now opened by a heading
  LINE and nothing else, so an entry may quote a heading in its prose as freely
  as it quotes anything else · `parse_ledger` previously located both sections
  with an unanchored `str.split` on the heading text, which this coordinator
  tripped TWICE in ten minutes while writing entries about this very parser —
  the ledger read 2 open / 187 landed against a true 105 / 84, every derived
  number on the deployed dashboard was wrong, and `lint.py` called the file
  clean throughout because it counts entries without splitting sections at all ·
  fixed with strip-equality line anchors matching `lint.py`'s own heading rule,
  so the two readers cannot disagree about where a section begins · **and the
  check, because the parser fix alone leaves the next reader with no signal**:
  `check_ledger_sections` walks the lines independently and errors when its
  open-entry count disagrees with `watch.parse_ledger`, naming both numbers ·
  red-first both halves — the parser check failed with #8 vanishing into a
  moved split, and the linter check was proven by reintroducing the OLD
  ALGORITHM verbatim and watching it redden (a regression guard has to be shown
  failing on the regression, so the test monkeypatches the bug back rather than
  asserting a hand-written number) · questions.md and answers.md were checked
  and are immune: `_parse_entries` already walks lines · 600 passed + 54
  subtests, lint clean with the new agreement line at 106 open, burndown +
  provenance + qorder guards PASS

- **#238** — Preserve `/answers` UI state across data refresh · P1 ·
  origin: **human** · landed 2026-07-26, **closed 2026-07-27** · open answered
  disclosures survive a real `data.json` tick through the existing data-keep
  snapshot/restore seam, keyed on a content-derived record identity (title,
  resolution stamp, body, follow-ups, exact-twin ordinal) rather than index or
  title, so reorder or deletion of another entry cannot reopen the wrong record;
  answer identities are stripped from departure ghosts so stale clones cannot
  poison later snapshots · `be27c8f`
  · **closed late, and deliberately on re-verified evidence rather than on the
  commit message**: the work landed 2026-07-26 red-first (open state lost on an
  unrelated refresh, stuck at the old index after reorder, lost after deleting
  another record) but the entry was left reading `in progress` across a
  coordinator handover. Rather than trust either the stale mark or the commit's
  own claim, this coordinator checked that the guard which passed actually
  covers *this* acceptance — `dev/capture/answers.mjs` carries named #238
  phases for reorder, not-stuck-on-index-0, closed-peer preservation and
  deletion — and that it went green in this session's own full sweep
  (596 + 54 subtests, 39/39 guards, 0 failures at `0d1e337`). A guard named
  `answers` passing is not the same fact as the check for this bug passing.

- **#217** — Render honest provenance coverage · P2 · origin: **loop** ·
  landed 2026-07-27 · burndown now names first-sight human/loop/historical
  unknown counts and committed-history denominator; unknown is hatched and
  never inferred as loop, shallow coverage is explicit, mobile/a11y intact ·
  target+HEAD cache and `(rev,path)` snapshots prevent nested-target poisoning ·
  596 + 54 subtests, provenance guard 22/22, Vision + Geometry PASS, Spec +
  Standards PASS after red-first cache fix · deployed :35110 PID 62810 ·
  `c1f5aaa`

- **#299** — Suppress expected peer-disconnect tracebacks at the HTTP
  handler boundary · P2 · origin: **human** · landed 2026-07-27 · exact
  `/mtime` BrokenPipe reproduced through the real handler red (8 failures);
  `Handler.handle` now closes quietly only for pipe/reset/aborted departures,
  never retries, while unrelated OS/application errors still escape · live five
  RST-cancel poll proof, focused 5 + 8 subtests, full 587 + 54 subtests,
  Standards + Spec PASS · deployed to :35110 PID 2367866 · `fe0351d`

- **#216** — Parse first-seen origin in ledger history · P2 · origin:
  **loop** · landed 2026-07-27 · `task_origins.py` walks only ledger-touching
  commits oldest-first and classifies each id once from its first leading-token
  appearance; later edits, current markers, body refs and commit metadata cannot
  rewrite arrival · combined/separate ids, deletions, shallow coverage and path
  confinement are explicit · 23 red-first tests, 582 + 46 subtests, Standards +
  Spec PASS · `e9c30ff`

- **#213** — Enforce forward-only task provenance · P2 · origin:
  **loop** · landed 2026-07-27 · entries whose leading id token contains any
  id >=216 require exactly one `origin: **human|loop|unknown**`; older entries
  may remain unmarked and are never guessed · combined ids key only on the
  leading token, body references do not govern · 12 landed summaries gained
  truthful unknown markers pending #216 archaeology · +17 red-first tests,
  559 + 46 subtests, Standards + Spec PASS · `f9dc636`

- **#296** — Stabilise answers guard premises under load · P1 · origin:
  **unknown** · landed
  2026-07-27 · guard-only fix for two root-caused races: #250 close now
  waits for the previous travel's concrete inline-style cleanup then proves
  the new close armed; #251 binds its original ElementHandle premise to the
  page consuming the phase's own mtime render instead of vacuous `count===2`
  · deterministic sabotage reproduced both exact assertions; 5 focused PASS
  incl 3 under load, full sweep 37/37, Standards + Spec PASS · `395c90f`

- **#158** — `/file` reflows markdown · P2 · landed earlier at `5c45d83`
  (task work 2026-07-27 found the entry stale in Open) · the line moved
  from WHO composed the text to WHAT the file is: `.md` / `.markdown` /
  `.mdx` at `/file` reflow through the same `mdB` as dashboard peeks,
  source and all other paths stay verbatim in a `<pre>`, path-based never
  content-sniffed · #102 rule rewritten in the same commit so it reads as
  reconsidered · raw bytes remain reachable via `/filedata`; full
  Source/Raw toggle is #252, JSON is #178 · reflow guard was left
  asserting the OLD verbatim line — updated to the new branch plus
  hostile-markup inertness and source-verbatim checks, each red-proved
  against a reintroduced break; pytest tokens extended (542 + 46 green)

- **#234** — Minimise the answer-morph rerender hold · P2 · origin:
  **unknown** · landed
  2026-07-27 · `Date.now() + 1600` replaced by named `MORPH_HOLD_MS = 1250`,
  derived from the measured critical path (flipDock's 1150ms transform is
  the longest visible leg + 100ms slack; the 850ms card travel, its 1000ms
  cleanup and the out-of-view ripple all finish inside it) — 850ms was
  rejected as mid-glide · reduced-motion path runs none of the three, so
  the shared constant is pure margin there · new guard
  `dev/capture/morphhold.mjs` drives `tick()` over a forced /mtime change:
  node intact on every page-clock decision inside the hold, release measured
  ~1250ms after hold-set · RED against old 1600ms and 100ms sabotage; load
  flake fixed by stamping `/mtime` response-body completion, the exact last
  await before the tick gate · `morph.mjs` window shrunk 1400→1200

- **#138** — Ship a PreCompact hook so the write-down is automatic · P2 · task ·
  landed 2026-07-27 · related: **#156** · `plugins/ud-dreamwork-hooks/`, off by
  default, same family shape as ud-dreamwork-github · appends a bounded
  preservation-focus record to machine-local `~/.config/dreamwork/hooks/<slug>/`
  (1.5s budget, always exit 0) and re-checks the DREAMWORK.md Load consent line
  every invocation, skipping silently without it · a hook fires AT compaction, so
  it guarantees the write-down and cannot buy landing time, and its stdout becomes
  summariser instructions, so it is silent by construction · shipped in one plugin
  with #156 exactly as this entry asked: both are Claude Code hooks, ship the
  plugin or ship neither · install.py --print default, --apply idempotent with
  timestamped backup + clobber refusal, never auto-applies · red-first 27 tests,
  542 + 46 subtests, Standards + Spec PASS · `d7983be`
  · no origin marker by contract, not by omission: #138 predates the #216 cutoff
  and the original entry recorded none, so the honest value is absent

- **#156** — Lint questions.md at WRITE time (PostToolUse hook) · P2 · idea · 40m ·
  origin: **human** · landed 2026-07-26 · related: **#138** · delivered as
  `plugins/ud-dreamwork-hooks/hooks/posttooluse_ledger_lint.py`, which lints
  `questions.md` and `tasks.md` in the same turn as the write, under the same
  consent boundary (4s timeout, ok:false on failure, exit 0) · his idea and the
  strongest version of the fix: every other defence fires LATER than the mistake
  (lint at init and in `just test`, the dashboard at read time), while a hook fires
  while the agent that mangled the file still holds the context · opt-in by design:
  no config until `install.py --apply`, and a DREAMWORK.md Load line is required
  for use · **found still listed Open on a truthfulness sweep**, a day after
  `close(#138,#156)` named it · `c51da8f`, merged `d7983be`

- **#245** — Build `ud-dreamwork-worktrees` plugin · P1 · origin:
  **unknown** · landed earlier at
  `8af7dc3` (ledger rescan 2026-07-27 found the entry stale in Open) ·
  red-first 11→22 contract tests, two independent Standards/Spec reviews,
  publishable package under `plugins/` symlinked into Pi/agents/llm-general
  roots; bounded subagent mode + durable co-agent claims/inbox protocol

- **#250** — Preserve motion for missing-aid answer disclosures · P1 · bug ·
  origin: **loop** · landed at `f17f307` · related: **#251** · identity-less
  answered details use a local human-click fold reusing travel/reveal/ghost
  without a persistence key; normal open/close prove >2 intermediate card heights
  and following-marker positions; reduced-motion function preserved · behavioral
  RED against the old `watch.py`; 440 tests, browser/lint/diff and Standards/Spec
  PASS · deployed · found stale in `## Open` by the 2026-07-27 ledger rescan, a
  day after it landed

- **#251** — Prove old answer node disconnects after deletion refresh · P2 · test ·
  origin: **loop** · landed with #250 at `f17f307` · related: **#250** · the
  original ElementHandle is proven connected before refresh and disconnected
  after; evaluation errors fail closed · a same-aid new survivor stays open · PASS
  · co-delivered with #250 rather than dependent on it: this is the proof that the
  node really goes, which is why the pair is `related` and not `depends`

- **#290** — Add a dashboard-settable main-dreamer run mode · P1 · origin:
  **unknown** · landed
  2026-07-27 · authoritative gitignored `.dreamwork/run-mode` drives three
  selectable modes (lackadaisical / hot / assisted) with hierarchical kept
  visibly planned-disabled behind #264/#288 · server validates, atomically
  writes, and emits exactly one watch event on real change; identical finals
  silent · 10s resettable arm with atmospheric progress bar, RM text parity ·
  one shared pending across tabs: initiator-only POST via sessionStorage owner
  id + CAS claim, followers display-only, cancel tombstone converges peers
  without an event, ownership survives navigation/reload, tab-close orphans
  reclaimed inside a 3s grace · review rounds closed dual-POST race, orphan
  reclaim dead code, tombstone expiry, guard quiet-window and flake findings ·
  TestRunMode 9/9, 515 tests + 46 subtests, runmode guard PASS repeatedly incl
  under pytest -n 2 load; final Standards + Spec PASS · deployed PID 2583034 ·
  `b0db53d`
  · related: **#443**
- **#292** — Make Ctrl/Cmd+Enter submit `/answers` questions · P1 · UI bug ·
  origin: **human** · **human via watch 2026-07-27 01:17** · landed 2026-07-27 ·
  related: **#293** · exact ask: “bug (give it to grok): on the /answers page,
  ctrl+enter does not work to submit a question to the dreamer, even though it
  should.” · Ctrl/Cmd+Enter on the `/answers` ask textarea now submits exactly
  once durably: an in-flight guard blocks a rapid double-press, generation
  invalidation on leaving the route stops a late response touching a rebuilt form,
  and failures keep the user's words · Grok-owned isolated branch, Standards and
  Spec reviews PASS, 506 tests + 46 subtests, answers guard ×2, merged `73ba7d8`,
  deployed

- **#293** — Render submitted `/answers` question text visibly · P1 · UI bug ·
  origin: **human** · **human via watch 2026-07-27 01:17** · landed 2026-07-27 ·
  related: **#292** · exact ask: “bug: when a question is submitted it's meant to
  go in the list and kind of does but the text stays invisible (though i can still
  see my cursor change to an I beam when hovering it) also, the question text on
  /answers stays invisible even after page refresh” · submitted text is visibly
  readable live and after hard refresh: the permanent `.dreamin` enter-pose was
  removed from open-row HTML, replaced by a keyed one-shot arrival (`open:` aids
  over title+body+ordinal, so exact-title twins stay distinct); computed
  opacity/color/geometry proven live and post-reload, reduced-motion parity, and a
  sabotage inject proves the guard is non-vacuous · same isolated Grok worktree as
  #292 but required its own RED · `9693106` + `f3f491c` + doc-nit `b931c04`

- **#291** — Restore the command composer's 1.5s courtesy-close · P1 ·
  origin: **unknown** · landed 2026-07-27 · successful main-panel command sends again auto-dismiss
  after 1425ms unless input resumes during/after POST; the ~5s confirmation
  remains independent while typing keeps the panel open; manual/context close
  remains destructive · explicitly opened command popouts are persistent and
  prove success remains visible beyond the main courtesy threshold · real guard
  was RED against the prior 5.65s coupling; 504 tests + 46 subtests, dismiss +
  confirmation guards, lint/diff clean; Standards + Spec PASS · `26c4bee`

- **#268** — Hide Dreamwork-only plugins from ordinary skill discovery · P1 ·
  origin: **unknown** · landed/migrated 2026-07-27 · active loops parse only exact bounded
  `DREAMWORK.md` Load declarations and resolve bundled/sibling/explicit packages
  deterministically, reading emitted `SKILL.md` files directly · migration first
  inventories every alias/source across recursive global/project/configured Pi
  roots, requires an exact fresh schema-v1 manifest, and removes aliases through
  a reversible drift-checked transaction · Pi `DefaultResourceLoader` proves
  global/project/configured plugins present before migration and absent after;
  live host post-check is empty while both active sources still resolve · final
  Standards + Spec PASS; 67 focused, 504 tests + 46 subtests · `ac4d57a`

- **#255** — Make composer confirmation self-dismiss reliably · P1 · UI bug ·
  origin: **unknown** · landed 2026-07-26 · one document-scoped `confirmationFor` controller serves
  main and popout: atmospheric arrival, ~5s readable hold, atmospheric
  departure/clear; reduced motion keeps timing and snaps visuals · typing
  cancels only panel courtesy-close; close/route/pagehide hard-clean timers,
  listener and in-flight attempt callbacks; newer submit supersedes older;
  error/rejection/validation replace success immediately · guard REDs proved
  the original permanent main/popout messages, popout enter-snap, fallback
  listener leak and close-during-POST resurrection · `dismiss` + `confirmation`
  PASS, Standards + Spec PASS, 459 tests + 46 subtests · `74837df`

- **#221** — Sort dashboard reviews by exact filesystem datetime · P2 ·
  implementation · origin: **unknown** · landed 2026-07-26 · newest exact `st_mtime_ns` first;
  filename ascending only on exact nanosecond ties; displayed age derives from
  the same stat result; disappearing TOCTOU entries are skipped while other
  stat errors surface · stable keyed review rows travel through the existing
  atmospheric FLIP system and reduced motion settles instantly · causal guard
  proves exact BigInt filesystem order survives server payload, transform-free
  natural geometry and settled DOM; reds cover disabled FLIP, pre-causal DOM
  mutation, smoothly wrong final order and adjacent-nanosecond Number collapse ·
  final Standards + Spec PASS; 459 tests + 46 subtests · integrated through
  `b9159db` · separate #288 authority incident remains open

- **#279** — Prototype a Jupiter-like higher-fluid-dynamics storm shader · P1 ·
  visual experiment/design · origin: **unknown** · completed 2026-07-26 as an honest **failed
  prototype** · all seven supplied references inspected; three standalone
  variants built without touching production · first evidence pass FAILed blank
  capture/telemetry race/submerged geometry; deterministic static pipeline,
  duplicate hashes, readback/contrast sanity and eye/wall composition fixed ·
  final Vision still FAILed reference-level fine turbulence, luminous material
  depth and organic multi-scale detail; Terra evidence/debrief PASS after
  bounding non-white and expected-framing claims · current `watch.py` shader
  remains unchanged; #280 stays blocked · throwaway primary source preserved at
  branch `prototype/279-jovian-final`, tip `a1c180c`

- **#271** — Rerender review docks on cross-browser data ticks · P1 · bug ·
  origin: **unknown** · completed 2026-07-26 · diagnosis:
  `.dreamwork/docs/research/cross-browser-note-propagation-271.md` · current-view
  tick rerender now refreshes remote notes without stale-navigation overwrite;
  preserves live iframe URL/scroll, stable question target, draft/selection/
  resize/scroll/focus and disclosure state · two independent Chromium launches,
  corrected baseline questions-green/dock-red evidence, normal+reduced shared
  non-vacuous guard · independent Spec/Standards review initially failed the
  vacuous scroll, navigation race and RM coverage; all fixed, final PASS · fresh
  `PASS noteprop`; 456 tests + 46 subtests; lint/diff clean; no new style miss ·
  commits `6388e70..2c0652b`

**#270** rebuilt the #229 topic-chat proposal around one #263 receipt authority,
main-dreamer-first operation, explicit bounded worker promotion, shared leases,
idempotent finalisation, attachment MVP, derived indexes and staged cutover.
Grok architecture PASS; Vision/Geometry FAILed then PASSed after anchor/mobile/
long-scroll fixes. Artifact `threaded-topic-chats-v2.html` at `9f08e47`; new R1–R4
question filed, no implementation authority (2026-07-26).

**#233** adds explicit unauthenticated trusted-LAN binding while preserving the
loopback default. Exact Host gates every request; browser writes additionally
require matching HTTP Origin before body/witness; advertised Host is always
allowlisted; IPv4/IPv6, wildcard URLs and warning are explicit. Initial dual-axis
review FAILed and was red-first fixed; final Spec/Standards PASS. Rebased commits
`f4ed3fe..a0de8fc`; 157 watch + 455 project tests (46 subtests each), focused
submission guards, socket probes and lint green; #233 adds no styleguide miss
(2026-07-26).

**#278** found no true open-duration shader acceleration: constant wall-clock
phase, one RAF/mount, stable ~60 FPS and non-monotonic optical displacement.
Phase-dependent agitation and brief navigation warp plausibly explain the human
perception; report `.dreamwork/docs/research/shader-acceleration-278.md` unblocks
#279 without changing the current shader (2026-07-26).

**#258** composable shader emotion research produced the first reviewed
urgency/shader proposal, then the human superseded its simple storm geometry
with a separate acceleration diagnosis, Jupiter-like prototype and selectable
preserved-shader track (#278–#280). D1 composer urgency remains #257
(2026-07-26).

**#266** fixes both observed review-dock wrong-target submissions by resolving
writes through the visible card's stable `data-qid`, never its stale positional
`data-qkey`. Independent Standards/Spec PASS; note and answer were both RED on
baseline and green after; 153 units plus focused `docktarget`/`qacard`, lint and
diff-check passed; deployed at `fe55cd3` (2026-07-26).

**#273** adds mode-and-target-aware accessible names to shared question/dock
textareas and send controls, and floors the send target at 44 px without a
structural layout change. Red evidence, 143-unit module, focused `qacard` browser
guard, lint and diff-check passed; integrated, deployed and cleaned at `a6e98cc`
(2026-07-26).

**#272** visually reviewed the live #229 route in isolated desktop/mobile
browsers. Measured evidence and ranked fixes are durable at
`.dreamwork/docs/research/review-route-ux-272.md`; critical findings are a
composer more than 4–5k px below the viewport and a decision prompt disconnected
across the iframe/dock seam. #273 owns small fixes; #270 owns the structural
proposal (2026-07-26).

**#267** contextual plugin discovery research is durable at
`.dreamwork/docs/research/contextual-plugin-discovery.md`: Pi's hidden
frontmatter retains a user command and dynamic resource discovery still
registers a normal skill. The IGC survivor removes global discovery symlinks
and has active Dreamwork read only declared plugin files from deterministic
install-relative paths; #268 owns implementation (2026-07-26).

**#232** the answer-morph pause is the intentional 1.6s rerender hold around
an 850ms local morph, followed by a phase-dependent 2s live poll; later loop
folding is separate. Diagnosed by requested GPT-5.6 Luna low-thinking agent,
folded into `.dreamwork/answers.md`, and delivered via `attn` (2026-07-26).

**#231** `/answers` is live: the human can ask the dreamer through a distinct,
durable `.dreamwork/answers.md` channel; the seeded governance question is its
first open item. Missing-first-create, unreadable health, raw/client recovery,
strict writes, live draft/focus, failure retention, and atmospheric answered
folds are guarded. Two-axis review/fix/rereview PASS; 136 Python tests, lint,
focused browser guard, and diff-check pass; b87475e deployed (human via Web UI,
2026-07-26).

**#202** “T3 connect” resolved from the human's exact source: Connect wraps an
ordinary T3 Code server with Clerk discovery/linking and a managed Cloudflare
tunnel; it does not supply TUI/PTY streaming. #201 keeps its transport-neutral
`/compact` first increment and gains a pre-render integration investigation.
See `.dreamwork/docs/research/t3-code-connect.md` (2026-07-26).

**#226** cross-browser tint synchronisation was already correct; the identity
guard now proves it through two separate Chromium processes rather than two
pages sharing one process. Focused guard passes with no production change
(human via Web UI, 2026-07-26).

**#181** title/favicon counts now derive from visible open questions, not
hand-maintained `status.awaiting_human` (bfa561f, deployed). Status keeps the
prose naming WHAT waits. Identity guard red-proved the old drift and now
checks status prose cannot alter the count; unreadable `!`, routes, and
favicons remain coherent (2026-07-26).

**#224** successful `do now` returns the composer to `add idea` through the
existing animated indicator path (a6a7ad2, deployed). Red proof held the old
kind; the focused draft guard passes. Rejected/unreachable sends and other
successful kinds are unchanged (human via Web UI, 2026-07-26).

**#157 + #222 + #223** links now promise only reachable destinations
(0c1f5ad, deployed): the collector ships existing target-relative paths;
known target/`.dreamwork/` paths link to `/file`, unresolved local-looking
references stay code, and `github.com/...` becomes external HTTPS. The
working-tree startup ReferenceError reported via do-now was fixed before
commit. Reflow guard, 405 pytest, and lint pass (2026-07-26).

**#206** the race-safe coordination protocol is in
`.dreamwork/docs/plans/parallel-architecture.md` (c59c163): file claims win,
messages wake; reports name omissions; absence waits beyond the report
window; commit-bound instructions name their boundary; explicit staging is
safe only for edits the stager made (2026-07-26).

**#127** deliberate compaction is documented in `compaction.md` plus the
shared harness-dialect table. Reconciled complete: a managed sender belongs
to dreamhub stage 2 because it requires a session handle; optional hooks are
the independently gated #138, not unfinished #127 work (2026-07-26).

**#209** closed by proving the existing keyboard path (4f9ed58): plugcmd
focuses the dots opener, Tabs into a visible plugin command, presses Enter,
and observes the same selected-kind path. The focused browser guard passes;
the implementation was accessible, but the claim had never been exercised
without a pointer (2026-07-26).

**#208** the single `setData` seam is now guarded (b91931a): a static test
permits one assignment inside the seam and requires both fetchers to use it.
Red proof bypassed the seam in `ensureData` and failed on the extra bare
assignment; all 128 watch tests pass (2026-07-26).

**#166** and **#140** were stale duplicate open lines, reconciled against
git and the handoff: commit-row expansion landed at 9ed526f; deployed
revision visibility landed at a621f31. Their detailed outcomes were already
in Recently landed and the 2026-07-25 handoff (reconciled 2026-07-26).

**#214** git history now uses collision-proof NUL framing (db1a1bc): red
proof showed `\x1f` in a subject shifted the old fields; Git `-z` preserves
subjects carrying both former separators because neither a commit message
nor path can contain NUL. Focused git-tail tests, 403 pytest, and lint pass;
gitrow's structural/data checks pass, with motion checks independently red
under severe host contention (2026-07-26).

**#220** a fully blocked queue now enters maintenance (07742b9): selection
says “no unblocked actionable work,” not “list empty,” and reuses the
existing `roll.py --no-backlog`; no duplicate flag was needed. Human steer
via Web UI at 12:03 (2026-07-26).

**#219** browser guards are bounded and self-identifying (ccc47a0): each
capture/hub check has a configurable 120s timeout and prints its name plus
exit code. Red proof: a 1s qacard run said `FAIL qacard (exit 124)`; normal
focused status passed. The original run had not hung — it completed in ~16m
under host load ~68 on 16 CPUs (2026-07-26).

**#212** closed as refuted: a real empty-subject commit preserves the
separator in `git log --format='%h %s'`, so `split(" ", 1)` already returns
`[hash, ""]`. The proposed regression test passed before any production
change; there was no red-capable bug to fix (2026-07-26).

**#210** reconciled as already fixed by #197 (3f411f3): the guard now
sets `AWAIT_N = OPENQ + 2` and explicitly asserts the counts differ.
Git reconstruction found the vacuous historical state at 266db84
(literal 3, open 3); the current focused identity guard passes, and a
sweep found no analogous gated guard (2026-07-26).

**#142** the ledger's own history, drawn (bb56f19) — a burndown below reviews, above status (the top of the page is what NEEDS him; this is context): the open LEVEL as a step line (a filled bar was rendered and rejected — at 12-to-67 open every column reads as a uniform block) over the FLOW (arrivals up, completions down), because the open count alone cannot tell "he steers fast" from "the work is slow"; arrivals/completions are FIRST-SEEN events so grooming's pruning of Recently-landed cannot erase a completion; the entry pattern is lint.py's VERBATIM, asserted identical by a test; provenance reported as `sourced 7/67` coverage rather than a split read as fact (→#213); found regroupBars' cleanup erasing the renderer's own inline height (#198's shape, fixed) and recorded #151's gate here as unguarded ON PURPOSE (a pure function of the series — the check was written, injected against, and could not go red); note: ledger_stats caches on HEAD, so the chart's right edge is the compute moment until HEAD moves — correct, and worth knowing before it is reported as a bug (2026-07-25). **#166** a commit row opens onto its reasoning (9ed526f) — a row IS a <details>, and the expand handler took a LIST of surfaces so the questions fold and the commit row share one gesture (snapshot, regroup, ghost, reveal, reduced motion all literally shared); the more-detail principle is in watch-design.md as three answers (expand = about the thing in place, navigate = its own subject deserving a URL, hover = never for anything not already summarised on screen); red-first showed #204 in miniature — with the native toggle, six motion checks red while every end-state check stayed green; also folded the last missing --no-optional-locks in watch.py (2026-07-25). **#140** the page says which revision it is running (a621f31) — one line under the commits label: dim when current, dimmest-with-why when unknowable, --warn + rail + missing-commits-in-title when stale; deliberately NOT `import deployed` (a deployed watch.py is often the only file on disk, and a read-only dashboard must not execute code out of the directory it watches) so the measurement is inlined and STRICTER — it compares this process's own __file__ bytes, catching #203's orphaned servers, the case that matters most; never silent, because one page's silent-healthy is indistinguishable from no check (2026-07-25). **#197** questions order by priority, decided once in the parse (3f411f3; the contract half — file-formats row, lint check, real entries stamped — had already landed at 6284402 17:32, so the coordinator's same-commit demand was stale and the dreamer's scoping right; the demand still provoked a real find, adopted at 3073055: the linter held a WIDER copy of the marker rule than the parser and blessed the three likeliest typos — the band is now asked of title_priority, never re-derived) — absent means P2 so an explicit P3 sorts below unmarked, Answered deliberately unsorted (expired urgency must not reorder a chronological record), and the fixture needed TWO properties before any check could fail: a real permutation, and an unmarked entry after the P3 one; found identity.mjs gone vacuous (→#210), title-edit identity caveat filed (→#211) (2026-07-25). **#86** P1 the composer renders what a plugin declares (a5a889d) — server filters the file (no core-kind shadowing, `common` never honoured), POST /command reads it per request so the menu never offers what the server refuses, menu items only because the row's width is load-bearing; found and fixed two wider bugs: `watched_mtime` was blind to deletions (→#207) and `tick` looked like the live path and was not (→#208); menu keyboard gap filed as #209 (2026-07-25). **#165** the history panel (91737bd) — sole source is #175's client log because only it knows the OUTCOME, and a panel that apologises per row is worse than a narrow one that states its limit once; failures leave via --warn because the accent marks what NEEDS him, and a failed send from an hour ago is a fact, not an errand (2026-07-25). **#175** every send is witnessed client-side (794d620) — IndexedDB, a DATABASE per project because a column can leak by omission and a database cannot; and the increment's find was a private fetch('/command') that left a third of his submissions unwitnessed, now unified through postJSON with a guard asserting the bare fetch stays absent (2026-07-25). **#163** the draft survives (8d0e6a7) — localStorage keyed by absolute target path (a draft is an unpublished thought, never a repo file; the #143 contrast is stated in watch-design.md), restore never overwrites live text, and the guard caught itself testing the restore while claiming to test the mode-switch (2026-07-25). **#198** the indicator was measured beneath a mid-transform ancestor (a86108e) — every rect read 3% small, error multiplying with distance from the origin; and the 'autocorrect' was unrelated re-renders laundering a permanent bug, not a transient (2026-07-25). **#199** P1 his words are on disk before anything may refuse them (fd3ae3b handler + 0bc0517 contract + migration 2026-07-25-15) — and the guard, by failing, proved questions.md is a RENDERING of his words, not a record of them (2026-07-25). **#191** the answer-morph carries its neighbours (38854bd) — and found that a guard's WINDOW can be the bug (2026-07-25). **#184** CLOSED not-reproduced: neither half; explained by #174, numbers in its dream (2026-07-25). **#179** P1 the focus steal (9e8469c) — focus() into a closed <details> is a silent no-op (2026-07-25). **#174** the cycle travels down (7d3c322) — a departure leaves in the direction its list travels (2026-07-25). **#150** coordination layer audited: relay.py, write-then-wake, agent visibility (2026-07-25). **#147** deployed.py measures by bytes; the hub row says it (59e7728, f3649f4) (2026-07-25). **#145** routing rule adopted (4 buckets) (2026-07-25). **#144** subagent plain text is not a channel; silent agents are shown (2026-07-25).
Pruned in grooming; git is the real ledger. **#143** a per-project tint
(6c49874) — a closed set, a Rodrigues hue rotation preserving the
achromatic component by construction, the existing `/mtime` poll doing the
cross-window sync, and six hues chosen to be distinguishable at 16px AND
to avoid the amber band, since a project tinted amber would paint the
field the colour that means broken. Its contract landed with it (338d17d).
**#153** the tab title and the favicon, and the app name's return as
`dreamwork/<project>` (10ca98a) — shipped in the one shape correct under
both readings of his ruling, rather than guessing. **#153** the tab now says
whether he is needed and the favicon is a ring with one traveller
(266db84, 0cefd06) — hue is which loop, motion is that the loop lives, a
pip is that he is the bottleneck. It ORBITS rather than breathes because
at 16px position reads and luminance does not, found by rendering both at
size. Also 7be4a22: `just guards` now proves the server is its own, after
a stray instance of mine stole the port and ten guards asserted fixture
facts against the live repo. **#155** the styleguide audit
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
