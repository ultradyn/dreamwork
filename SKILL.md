---
name: ud-dreamwork
description: >
  Continuous low-cost autonomous dev loop ("dreamwork" / "productive dreaming"):
  a 4.75-minute heartbeat keeps the session cache-warm and wakes it when idle;
  work happens in small committed increments (15-20 min cap) with post-change
  reflection; every idea is captured to the task list; an explicit algorithm
  picks the next task when idle. Use when Max says dreamwork, productive
  dreaming, dream loop, start dreaming, or wants long-running free-flowing
  autonomous dev on a project.
---

# Dreamwork — the productive dreaming loop

## Philosophy (load-bearing)

- **Small increments are the error-catching mechanism.** Cap each task at
  ~15-20 minutes of work. After every change, pause and reflect: re-read the
  diff, run the tests. Mistakes get caught the moment they're made, while you
  are still on the path that made them. Split anything bigger into multiple
  tasks; each increment must end in a verifiable, committable state.
- **Ideas always go in the task list.** No idea is lost, and no work happens
  that isn't a task. The list is the loop's brain, and it must be durable —
  a record that forgets on restart is a cache, not a memory. (Which record
  that is depends on the backend; see Durable state.)
- **Know what the human wants.** `DREAMWORK.md` (repo root) records the
  human's high-level goals, philosophy, preferences, and routines. We should
  always know what the human wants so we can make what the human needs —
  it is where every chain of work terminates. It
  grows incrementally: when the human expresses a durable preference or
  goal mid-loop, record it there.
- **Reflection over momentum.** The heartbeat buys thinking time after each
  change. Use it — a beat spent noticing a mistake is cheaper than an hour
  spent undoing it.
- **Unclear is a goals problem.** All unclear things trace to unclear
  goals; always be improving clarity where it lacks. Any time we need to
  talk to the human is also a time to sharpen the recorded goals — fold
  what their answer reveals into DREAMWORK.md, don't just unblock the
  moment.

## Initialization (once per session)

Read `initialization.md` from this skill's base directory and follow it —
in order: confirm the target project, read the
target's DREAMWORK.md (if present), resolve plugins (`ud-dreamwork-*`
skills, which may extend later steps), run the setup wizard when
DREAMWORK.md is absent, then heartbeat, task backend, orientation,
reconciliation, green baseline, first-run seeding, and the opening status
report.

Initialization runs once per session (or on resume). This SKILL.md may be
loaded multiple times in a long session — if the heartbeat is already armed
and DREAMWORK.md has been read, skip initialization and return to the loop.

## The loop — on every heartbeat tick

Ticks are monitor events, not user input — never treat one as a reply or an
approval. Real user messages always take priority over the loop. When the
human is actively streaming messages, prefer capture and consultation over
starting new increments — resume autonomous work when the stream pauses.

- **Mid-task** → checkpoint: still on track? Past the ~20-minute cap? (Land a
  coherent point, commit, split the remainder into a new task.) Did the last
  change introduce an error? Look before continuing.
- **Task just finished** → reflect and verify (checklist: `reflection.md`
  in this skill's directory): re-read the diff, run the project's
  verification, commit the increment, mark the task completed. Then
  select the next task.
- **Idle** → run the selection algorithm below.

On each tick, best-effort, refresh `.dreamwork/status.json` (current task,
queue depth, last tick time, last commit, and the session goal — which
persists across ticks, rewritten only on a pivot) — the watch.py
dashboard reads it; failing to write it never blocks the loop. And if
`questions.md` changed since your last look, check for new
human-authored blocks (`Note (human, via …)`) —
fold them first: act on the answer, then move the entry to Answered.

Check `.dreamwork/watch-events.log`'s mtime too. A command he types into
the dashboard composer exists **only** as a line in that file — nothing
is written anywhere else, and the write is best-effort — so if the tail
monitor is not armed (a resumed session, a compacted one, a `watch.py`
started after init), his `do now:` is lost with no error anywhere. The
answer channel is durable because answers land in `questions.md`; the
command channel is not.

## Selecting the next task

0. **Sync.** Check the task list first. Resume unblocked in-progress work
   before starting anything new; then take any task marked next-up
   (marked next-up in the ledger, newest first, clearing the mark on start) —
   an explicit human steer outranks the agent's own ideas. Then: any
   goal/philosophy misalignment **you already know about** (DREAMWORK.md
   stale or contradicted) outranks everything below — restore alignment
   before other work. This is not a licence to audit DREAMWORK.md before
   every selection; the periodic check that *produces* such findings is
   step 4.
1. **Out-of-scope leftovers.** In recent work, did anything occur to you that
   was out of scope at the time? If complex: do a quick feasibility check,
   then add it to the task list. Otherwise: do it now (add it as in_progress
   first so the list stays truthful).
2. **Idea beat.** Does anything recent give you an idea for a productive
   thing to do? (a new feature, refactoring, integrating a new library and
   updating some things,
   ...).....................................................................
   (The dots are intentional: explicit thinking time. Let the idea surface
   before reading on.) If a good idea comes: do it (scope gate applies).
   Multiple ideas: add them all to the task list, then pick the best.
3. **Still nothing:**
   1. **Brainstorm (rare).** Only when few actionable ideas remain (fewer
      than ~3 pending unblocked tasks) and no brainstorm has run recently:
      dispatch a dreamer subagent (see Subagents) with the
      superpowers:brainstorming skill. Constraints for it: ideas must be
      consistent with the project's goals and philosophy (per DREAMWORK.md
      and CLAUDE.md — pass the relevant parts into the subagent prompt);
      experiments are fine but must be feature-gated; big feature swings
      and pivots are rejected (big changes genuinely necessary to solve a
      problem are exempt — those are a fact of life). Record when the
      brainstorm ran (metadata on a marker task) so it stays occasional.
   2. **Backlog.** Otherwise pick the highest-priority unblocked pending
      task. When torn between backlog and maintenance (or which
      maintenance item), you may roll `roll.py` in this skill's directory
      — advisory, never binding: a mess, an easier-now-than-later, or a
      human steer always overrides. Custom weights persist as a Routines
      line in DREAMWORK.md.
4. **Maintenance rotation.** List empty and brainstorm recent? Rotate
   through: goal alignment first — does DREAMWORK.md still reflect what
   the human wants and what the loop has learned? fold in any drift, and
   check every task `parent` still resolves to a DREAMWORK.md heading;
   then
   self-review recent commits for introduced errors; test-coverage gaps;
   docs freshness — the repo's own docs, `.dreamwork/docs/`, the
   doc-map, and any reference docs the target ships for others to
   consume, alike (keeping the repo's docs current is loop work; the
   doc-map's rows say what that covers);
   task-list grooming (dedupe, reprioritize, prune stale); dream grooming (archive dreams whose ideas and lessons are
   captured); dogfood reflection — friction with the loop itself: fix
   small, file the rest. If truly nothing: idle quietly until the next tick — no
   make-work.

## Subagents — utilities and dreamers

Two kinds, nothing in between:

- **Utility subagents** — narrow tools: answer a question (e.g. an Explore
  agent for "how does X work?" or "what's relevant to Y?") or run a scoped
  mechanical job. Focused prompt in, focused answer out. No dream files.
- **Dreamers** — little versions of us, dispatched for substantive work
  (brainstorming, an increment, a review). They share our memories: pass
  them DREAMWORK.md, the relevant `.dreamwork/docs/`, recent dreams, the
  task's context, and **the active chain** — the task's goal, the
  session goal, and the DREAMWORK.md goal above them. A dreamer holds
  the same scope gate we do; without the chain it would have to invent
  the middle link, which the gate defines as the refusal. When a dreamer finishes, if it had anything to say
  beyond its direct result — insights, surprises, out-of-scope ideas,
  warnings — it writes `.dreamwork/dreams/<date>-<time>-<slug>.md` (e.g.
  `2026-07-25-0140-export-panel-jank.md`). Nothing to say → no file; empty
  dreams are noise. If a dream contains an important lesson, its one-line
  distillation is also appended to `.dreamwork/lessons.md`. The coordinator
  reads new dreams and captures any ideas into the task list.

Delegation blocks files, not the loop. Record what a dispatched dreamer
owns (files/dirs) at dispatch; the coordinator stays off those. After
~10 minutes of a delegated task running, resume selection over
non-conflicting tasks. The invariant is disjointness: parallel
increments — the coordinator's own, or several dreamers' — only ever
touch disjoint files, so there is never a split brain over the same
files. The `parallelize` command is the explicit fan-out of this same
rule; the coordinator itself still works one inline increment at a
time. Disjoint files also means disjoint staging: while anyone else
holds the tree, commit by explicit path — `git add -A` sweeps up their
half-finished work and buries it in your increment.

When disjointness can't be arranged — the work overlaps owned files, or
the change is large or risky — dispatch the dreamer in a worktree (the
harness's worktree isolation, or a git worktree under `.worktrees/`,
gitignored): the invariant then holds by construction. Lifecycle follows
the human's standing worktree convention (CLAUDE.md) — merge back on
acceptance, and never force-remove without checking for untracked
scratch first. One cost that convention does not mention: worktrees
duplicate build state, so where the toolchain has a shared cache
(compiler cache, shared target/store dirs), set it up; if the project
lacks one, suggest it (questions.md). Storage ballooning is real.

Dreamers are batches, not careers. A long-lived dreamer's context grows
until fresh eyes are cheaper — bound its scope to the current batch,
retire it when the batch lands, and spawn fresh for new work (it
inherits the styleguide, docs, and lessons; that's the shared memory).

**Default to fresh. Reuse an incumbent only within ~4 minutes of its
last stop** (human-set 2026-07-25) — inside that window its context is
still cache-warm and respawning throws the cache away; outside it, a
fresh dreamer costs about the same and arrives with clean eyes. The
tight-follow-up exception (a bug in what it just built, a refinement of
its own motion language) lives inside that window, not beyond it.

**This is the coordinator's call, not the incumbent's.** A dreamer
saying "I have room" is evidence, not a decision — it is the party least
able to see its own context cost, and it will almost always say yes.
Ask instead: is this the same work, and did it stop moments ago? A
dreamer reached ~600k tokens here because its own assessment was
accepted three times running.

All subagents report to the coordinator **through a file**, and never use
`attn`. Give every one of them a path to write to and an inbox to ping —
a subagent's final message is a channel nobody reads back, and it has
silently swallowed deliverables here. Dreamers append to the coordinator
inbox and have never lost one; the fix is to dispatch utilities the same
way, not to watch harder.

**Steering an agent takes two acts: write, then wake.** The inbox is
durable but not delivered — a dreamer reads it *between increments*, so
one that has gone idle never sees it, and a batch written two minutes
after it went quiet sits unread indefinitely. Write with `relay.py`
(body from stdin, stamp from the clock, both for reasons in its
docstring), then send a message through the harness. A silent agent and
a silent channel look identical, so verify what READS a thing, never
just that it was written.

Subagents never stop or pause loop machinery — the heartbeat monitor, the
watch server, the loop itself; if one believes the loop should stop, it
says so in its report and the human (or the coordinator on the human's
instruction) decides. A report must always say what durable state
changed — dream file written, docs added or updated, with paths — change
notification is key and cheap. Everything else stays minimal: raw
results, no ceremony.

## Durable state — `.dreamwork/`

- `DREAMWORK.md` (repo root) — what the human wants; see Initialization.
- `.dreamwork/dreams/` — dream journals from dreamer subagents. Once a
  dream's ideas are tasks and its lessons are in `lessons.md`, move it to
  `dreams/archive/` — the journal stays lean, the memory survives. One
  exception worth keeping: **a dream stays active while the work it hands
  off to is unstarted**, so whoever picks that work up meets it without
  going looking. Archive it when its successor exists or the handoff is
  spent.
- `.dreamwork/lessons.md` — important lessons, each outliving the dream
  it came from. **Prune when a lesson has graduated into a guardrail or
  a check** — one now enforced by `lint.py` or a guard no longer has to
  persuade anyone. What a good entry looks like, and why its evidence
  half is load-bearing: `file-formats.md`.
- `.dreamwork/docs/` — living docs collaboratively added to and maintained
  by us, the dreamers: design notes, discovered conventions, gotchas,
  architecture understanding. Maintained means pruned and updated when
  stale, not append-only.
- **The ledger** — the queue's durable record, which everything else in
  this skill means by the word. On a backend whose list and ids survive
  a restart (`bl`) it *is* the backend, and there is no extra file. On a
  session-scoped backend (the native tools) it is
  `.dreamwork/tasks.md`: open tasks only, one line each (id, title,
  priority/type/size, owner or blocked-on, pointer to any plan), plus
  the next id to hand out. Either way ids are permanent and never
  reused, and everything that refers to a task — commits, docs,
  questions, dreams — uses them; a session-scoped backend's own numbers
  are local plumbing. The file version is rewritten as part of the
  increment that changes the queue, not on a separate beat, and **the
  coordinator is its only writer** — a dreamer reports a queue change
  instead: durable shared state wants a single writer, or the next
  fan-out races it (two dreamers mint the same id, and the ledger loses
  exactly what it exists to keep).
- `.dreamwork/questions.md` — open questions for the human: proposals
  awaiting a response, unclear-goals items, parked scope calls. Answers
  fold into DREAMWORK.md or tasks and the entry moves to a short Answered
  section (pruned in grooming). Entries thread: timestamped follow-ups
  accumulate inside an entry and folds move the whole thread, and a
  follow-up landing on an *Answered* entry is a potential amendment —
  re-evaluate the fold, it may reopen the question or redirect in-flight
  work. **Whose words they are is never in doubt**, which is why the
  author tags exist; their exact forms are in `file-formats.md`, because
  a parser reads them. **Its shape is a contract, not a style** —
  `watch.py` matches `## Open` and `## Answered` literally, and a file
  that misses them parses to nothing and renders as "nothing to answer",
  silently.
- **Formats.** Files the loop writes and a tool parses have required
  shapes, and getting one wrong fails silently rather than loudly — the
  reader cannot tell an unreadable file from an empty one.
  `file-formats.md` in this skill's directory states them; read it before
  writing one of those files for the first time, and follow the existing
  file's shape rather than inventing one when a format is not yet stated.
- `.dreamwork/review/` — rich review artifacts: when something sizeable
  or important needs the human's eyes (a plan, a design, an analysis),
  generate a self-contained HTML artifact (inline everything — charts,
  math, styles; offline-clean) as `<slug>.html`, paired with a
  questions.md entry for the response. watch.py lists and serves them.
  Archive alongside the answered question.
- `.dreamwork/status.json` — live loop status for the watch.py dashboard,
  rewritten each tick. Its timestamps come from the system clock, never
  from memory — a dashboard whose whole thesis is liveness must not
  render an invented time. It also carries the loop's **runtime state**:
  which dreamers are out, what files each owns, which monitors are
  armed, and how to deploy. That state dies with the session, so this
  ephemeral file is its right home — but it must survive *within* one,
  because a compacted coordinator that forgets a dreamer owns `foo.py`
  will edit `foo.py`. Gitignored, like `watch-events.log` — both describe
  a running process, so committing either would be a lie the moment it
  landed. The dashboard itself is `watch.py` in this
  skill's directory (read-only, localhost-only):
  `python3 <skill-dir>/watch.py --target . --open`; its port persists in
  `.dreamwork/watch-port`.
- `.dreamwork/skill-version` — which skill version this target last ran
  under; init's update check reads it (`initialization.md`).
- All of it is committable project content, like CLAUDE.md.

## Task-list conventions

- Every task needs a permanent id, and wears it at the front of its
  subject (`#91 — …`) — the subject is the field every backend reads
  back. A backend that mints durable ids does that itself; where the
  ledger is a separate file, the coordinator takes its next id and bumps
  it.
- Every task also knows what it is *for*: a one-line `goal`, and the
  `parent` it serves (a session goal, or a DREAMWORK.md sub-goal by
  name). It states its chain when it starts — see the scope gate. One
  line, never a document; a chain that needs a paragraph is a sign the
  work does not belong to it.
- The ledger carries what selection and triage read: `priority` (P1-P3),
  `type` (idea | task | bug | experiment | chore), `size` (estimated
  minutes), `feasibility` (note from triage), the next-up mark (set by
  `do next`, cleared on start), owner or blocked-on, and — once a task
  is started — its `goal` and `parent`, because the scope gate asks
  every actor to name a chain and a link no one can read is a link no
  one can name. Where the ledger is a separate file, mirror them into
  the backend's `metadata` if it surfaces them — but never depend on
  that unread.
- Work that arrives with a durable id upstream (a forge issue a plugin
  ingested) keeps that id instead of being given one of the loop's own.
  While it is only a candidate it sits in the backend and competes in
  normal selection like anything else, but it takes no loop id and no
  ledger line — the next poll re-derives it, so a busy forge never
  floods the loop's numbering. Starting it changes that: a poll
  re-derives the item, never the loop's progress on it, so as work
  begins it takes a loop id and from then on holds its own state —
  owner, branch, blocked-on.
- Dependencies recorded however the backend expresses them (Claude Code:
  `addBlockedBy` / `addBlocks`), and on the ledger line either way.
- Big features get a planning doc on disk (`.dreamwork/docs/plans/<slug>.md`
  or the repo's convention); the task itself is a thin pointer. Bulk stays
  out of the task list until it's actually time to implement.

## Commands

Most bare user messages map to one of these; when ambiguous, ask (via `attn`
if Max is away).

- `do now: <text>` — immediate. Park the current increment at a coherent
  point (commit it, or stash and split a remainder task), create the task
  as in_progress, and work it right away.
- `do next: <text>` — queue-jump. Create the task and mark it next-up
  (next-up mark in the ledger); it gets picked as soon as the current task
  lands, ahead of priority order. Several next-ups: newest first — the
  human's latest steer wins. Bare `do next` (no text): just run the
  selection algorithm now.
- `add idea: <text>` — capture, then expand. Add to the task list slotted
  by priority (feasibility-triage if complex); doesn't jump the queue.
  Then briefly develop the idea in line with the project's philosophy and
  goals: clearly-aligned implications and subtasks enter the task list as
  normal tasks; unclear extras park in `.dreamwork/questions.md`; and
  since the human just typed this, a one-line consult now beats guessing.
  Generalized: any sensible `add <thing>:` matches (`add idea` stays
  canonical) — the thing becomes the task's `type`. `add bug:` captures
  richer detail (repro, expected vs actual, severity — ask one line if
  missing); `add task:` / `add chore:` / `add experiment:` map directly;
  `add question:` routes to questions.md instead of the task list;
  anything else sensible maps to the best-fit type.
- `maintenance` / `do maintenance` / `maintenance: <item>` — run the
  maintenance rotation now, regardless of backlog state; without an item
  named, `roll.py --no-backlog` can pick one.
- `parallelize` (or "parallel" and similar) — dispatch subagents across
  disjoint pending tasks where possible. Disjoint means no shared file
  ownership (the delegation rule is the conflict test). Report what was
  parallelized and what couldn't be, with why (ownership overlap,
  human-gated).
- `status` — current task, queue summary, recent completions, open
  questions from `.dreamwork/questions.md`.
- `pause` / `resume` — TaskStop the heartbeat monitor / re-arm it.
- `wrap up` — land the current increment cleanly, commit, summarize, and
  note any friction with the loop itself — fix small, file the rest.
  Check the queue is restorable — where the ledger is a separate file it
  should already match the backend; if it doesn't, an increment skipped
  its reflection. (A check, not the mechanism: the restart that cost
  eight tasks had no wrap-up.) Then look at the session goal: if it
  turned out to be something the project will keep wanting, promote it
  into DREAMWORK.md as a sub-goal.

## Guardrails

- Commit each increment. Never push or deploy unless DREAMWORK.md or the
  project's CLAUDE.md/config explicitly authorizes it.
- Mark maintenance commits `dreamwork(maintain:<item>): ...` — git is the
  maintenance ledger (roll.py reads it for staleness). A maintenance pass
  that changes nothing may record an `--allow-empty` marker commit.
- Verification before completion: the project's verification passes
  (tests/lint, or its stated routine) before a task is marked completed.
- Experiments are feature-gated.
- Compaction-safe: durable state lives in files — DREAMWORK.md,
  `.dreamwork/` (dreams, docs, plans), and commits — never only in
  conversation, and never only in a session-scoped task backend. When a
  compaction is announced, run the checklist in `compaction.md` before
  it happens; a notice is the only window for what only you know.
- Never let the loop depend on a channel you have not read back. Task
  backends accept metadata they may never surface (Claude Code's
  `TaskGet` returns subject, status, and description — no metadata), so
  anything selection or triage reads lives in the subject, the
  description, or the ledger.
- A symptom is not a diagnosis. When capturing a bug the human reports,
  record what they *saw*, in their words; any cause you propose is a
  hypothesis and gets labelled as one. A dreamer handed "the joiner is
  swallowing entries" will go and fix the joiner — and a confident wrong
  layer costs hours, where reproducing the input costs minutes. Reproduce
  before building.
- Mismatched signals mean something is wrong. When context disagrees with
  itself — e.g. the cwd doesn't match the work being discussed, the task
  list contradicts git — don't guess and don't proceed on the wrong
  assumption: ask the human.
- Every ask is recorded. Never propose something needing the human's
  response without writing it to `.dreamwork/questions.md` in the same
  breath — they may be afk or miss the message. Unclear goals park there
  too, instead of being guessed at.
- Scope gate — **name the chain**. Agent-initiated work that adds new
  surface area (a new file, section, or feature) or breaks the size
  norms has to state its chain out loud first: this task serves *that*
  session goal, which serves *that* goal in DREAMWORK.md. The chain
  ends at the highest goal that exists — two rungs is a chain. If you
  can't name it without inventing a link, that is the answer — park it
  in questions.md instead of doing it. If *nothing* can be named
  because DREAMWORK.md holds no goals yet, the gate is telling you
  about the goals and not the work: park one question asking for them,
  not one per task. Human-initiated steers are never gated. Defaults
  and silence may resolve *how* or *when* for already-authorized work
  — never *whether* to add new surface; parked scope questions stay
  parked until answered.
- Surface contradictions. When what the human says now conflicts with
  recorded state (DREAMWORK.md, docs, the implementation), say so plainly
  and presume they know how to resolve it — it's wavelength-matching, not
  fault-finding. Fold the resolution back into DREAMWORK.md. Restoring
  alignment is priority work, not deferred maintenance: small drift folds
  in immediately; bigger drift becomes a top-of-queue task.
- Communication: brief updates as you go; `attn` only for genuine blockers,
  questions, or notable milestones. Subagents never use `attn`.

## Wake mechanisms (variants)

The Monitor heartbeat (armed in `initialization.md`) is the default and
preferred mechanism; consider `/loop` where available. For harnesses with
hooks but no Monitor tool, a Stop-hook fallback exists — reference design
and caveats in `stop-hook-variant.md` in this skill's directory.
