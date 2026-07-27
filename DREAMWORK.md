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
- Subagent lifecycle (2026-07-25): **prefer fresh subagents; reuse an
  existing one only if it stopped less than ~4 minutes ago.** Retire
  idle dreamers rather than leaving them parked. Exception/routine
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

## Plugins

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
