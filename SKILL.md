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

Long-running, free-flowing development. Not the most direct or fastest path,
but efficient, sustained, and never stuck or bored — built for ongoing
open-ended improvement of a project.

## Philosophy (load-bearing)

- **Small increments are the error-catching mechanism.** Cap each task at
  ~15-20 minutes of work. After every change, pause and reflect: re-read the
  diff, run the tests. Mistakes get caught the moment they're made, while you
  are still on the path that made them. Split anything bigger into multiple
  tasks; each increment must end in a verifiable, committable state.
- **Ideas always go in the task list.** No idea is lost, and no work happens
  that isn't a task. The task list is the durable brain of the loop.
- **Know what the human wants.** `DREAMWORK.md` (repo root) records the
  human's high-level goals, philosophy, preferences, and routines. We should
  always know what the human wants so we can make what the human needs —
  when in doubt about whether work fits, that file is the reference. It
  grows incrementally: when the human expresses a durable preference or
  goal mid-loop, record it there.
- **Reflection over momentum.** The heartbeat buys thinking time after each
  change. Use it — a beat spent noticing a mistake is cheaper than an hour
  spent undoing it.

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
approval. Real user messages always take priority over the loop.

- **Mid-task** → checkpoint: still on track? Past the ~20-minute cap? (Land a
  coherent point, commit, split the remainder into a new task.) Did the last
  change introduce an error? Look before continuing.
- **Task just finished** → reflect and verify (checklist: `reflection.md`
  in this skill's directory): re-read the diff, run the tests, commit the
  increment, mark the task completed. Then select the next task.
- **Idle** → run the selection algorithm below.

## Selecting the next task

0. **Sync.** Check the task list first. Resume unblocked in-progress work
   before starting anything new; then take any task marked next-up
   (`metadata.next: true`, newest first, clearing the mark on start) —
   an explicit human steer outranks the agent's own ideas.
1. **Out-of-scope leftovers.** In recent work, did anything occur to you that
   was out of scope at the time? If complex: do a quick feasibility check,
   then add it to the task list. Otherwise: do it now (add it as in_progress
   first so the list stays truthful).
2. **Idea beat.** Does anything recent give you an idea for a productive
   thing to do? (a new feature, refactoring, integrating a new library and
   updating some things,
   ...).....................................................................
   (The dots are intentional: explicit thinking time. Let the idea surface
   before reading on.) If a good idea comes: do it. Multiple ideas: add them
   all to the task list, then pick the best.
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
      task.
4. **Maintenance rotation.** List empty and brainstorm recent? Rotate
   through: self-review recent commits for introduced errors; test-coverage
   gaps; docs freshness; task-list grooming (dedupe, reprioritize, prune
   stale). If truly nothing: idle quietly until the next tick — no make-work.

## Subagents — utilities and dreamers

Two kinds, nothing in between:

- **Utility subagents** — narrow tools: answer a question (e.g. an Explore
  agent for "how does X work?" or "what's relevant to Y?") or run a scoped
  mechanical job. Focused prompt in, focused answer out. No dream files.
- **Dreamers** — little versions of us, dispatched for substantive work
  (brainstorming, an increment, a review). They share our memories: pass
  them DREAMWORK.md, the relevant `.dreamwork/docs/`, recent dreams, and
  the task's context. When a dreamer finishes, if it had anything to say
  beyond its direct result — insights, surprises, out-of-scope ideas,
  warnings — it writes `.dreamwork/dreams/<date>-<time>-<slug>.md` (e.g.
  `2026-07-25-0140-export-panel-jank.md`). Nothing to say → no file; empty
  dreams are noise. The coordinator reads new dreams and captures any ideas
  into the task list.

All subagents report to the coordinator and never use `attn`.

## Durable state — `.dreamwork/`

- `DREAMWORK.md` (repo root) — what the human wants; see Initialization.
- `.dreamwork/dreams/` — dream journals from dreamer subagents.
- `.dreamwork/docs/` — living docs collaboratively added to and maintained
  by us, the dreamers: design notes, discovered conventions, gotchas,
  architecture understanding. Maintained means pruned and updated when
  stale, not append-only.
- All of it is committable project content, like CLAUDE.md.

## Task-list conventions

- `metadata`: `priority` (P1-P3), `type` (idea | task | bug | experiment |
  chore), `size` (estimated minutes), `feasibility` (note from triage),
  `next` (true while queued as next-up via `do next`; cleared on start).
- Dependencies via `addBlockedBy` / `addBlocks`.
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
  (`metadata.next: true`); it gets picked as soon as the current task
  lands, ahead of priority order. Several next-ups: newest first — the
  human's latest steer wins. Bare `do next` (no text): just run the
  selection algorithm now.
- `add idea: <text>` — capture. Add to the task list slotted by priority
  (feasibility-triage if complex); doesn't jump the queue.
- `status` — current task, queue summary, recent completions.
- `pause` / `resume` — TaskStop the heartbeat monitor / re-arm it.
- `wrap up` — land the current increment cleanly, commit, summarize.

## Guardrails

- Commit each increment. Never push or deploy unless DREAMWORK.md or the
  project's CLAUDE.md/config explicitly authorizes it.
- Verification before completion: tests/lint pass before a task is marked
  completed.
- Experiments are feature-gated.
- Compaction-safe: durable state lives in the task list, DREAMWORK.md,
  `.dreamwork/` (dreams, docs, plans), and commits — never only in
  conversation.
- Mismatched signals mean something is wrong. When context disagrees with
  itself — e.g. the cwd doesn't match the work being discussed, the task
  list contradicts git — don't guess and don't proceed on the wrong
  assumption: ask the human.
- Communication: brief updates as you go; `attn` only for genuine blockers,
  questions, or notable milestones. Subagents never use `attn`.

## Wake mechanisms (variants)

The Monitor heartbeat (armed in `initialization.md`) is the default and
preferred mechanism. A Stop-hook variant ("fire back after a time": the
Stop hook sleeps ~285s then
returns `{"decision":"block","reason":"dream tick"}`) is viable — the hook
default timeout is 600s — but it is a workaround: loop prevention is entirely
on the hook author (guard with a counter or marker file), and user input
during the sleep window is not well-defined. Prefer Monitor; consider `/loop`
where available; reserve the Stop-hook pattern for harnesses that have hooks
but no Monitor tool.
