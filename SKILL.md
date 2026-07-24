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
- **Reflection over momentum.** The heartbeat buys thinking time after each
  change. Use it — a beat spent noticing a mistake is cheaper than an hour
  spent undoing it.

## Setup (on load)

1. **Heartbeat.** Start the wake timer — 4.75 min stays under the 5-minute
   prompt-cache TTL, keeping the loop cheap:

   `Monitor command="heartbeat 4.75m 'dream tick'" triggerTurn=true persistent=true`

   No regex filter. If the `heartbeat` CLI is absent, fall back to
   `while true; do echo 'dream tick'; sleep 285; done`. Re-arm after session
   restart or resume. (Same mechanism as the heartbeat-monitor skill.)
2. **Task backend.** Native Claude Code task tools (TaskCreate / TaskList /
   TaskGet / TaskUpdate) by default. If the repo already has backlog
   configured (a `.backlog/` dir exists), use `bl` instead: `bl howto`,
   `bl idea`, `bl next` / `bl grab` / `bl cycle`.
3. **Orient.** Read the project's CLAUDE.md and any goals/philosophy docs,
   review the task list, and give Max a one-paragraph status.

## The loop — on every heartbeat tick

Ticks are monitor events, not user input — never treat one as a reply or an
approval. Real user messages always take priority over the loop.

- **Mid-task** → checkpoint: still on track? Past the ~20-minute cap? (Land a
  coherent point, commit, split the remainder into a new task.) Did the last
  change introduce an error? Look before continuing.
- **Task just finished** → reflect and verify: re-read the diff, run the
  tests, commit the increment, mark the task completed. Then select the next
  task.
- **Idle** → run the selection algorithm below.

## Selecting the next task

0. **Sync.** Check the task list first. Resume unblocked in-progress work
   before starting anything new.
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
      dispatch a subagent with the superpowers:brainstorming skill.
      Constraints for it: ideas must be consistent with the project's goals
      and philosophy; experiments are fine but must be feature-gated; big
      feature swings and pivots are rejected (big changes genuinely necessary
      to solve a problem are exempt — those are a fact of life). The subagent
      must NOT use `attn`. Record when the brainstorm ran (metadata on a
      marker task) so it stays occasional.
   2. **Backlog.** Otherwise pick the highest-priority unblocked pending
      task.
4. **Maintenance rotation.** List empty and brainstorm recent? Rotate
   through: self-review recent commits for introduced errors; test-coverage
   gaps; docs freshness; task-list grooming (dedupe, reprioritize, prune
   stale). If truly nothing: idle quietly until the next tick — no make-work.

## Task-list conventions

- `metadata`: `priority` (P1-P3), `type` (idea | task | bug | experiment |
  chore), `size` (estimated minutes), `feasibility` (note from triage).
- Dependencies via `addBlockedBy` / `addBlocks`.
- Big features get a planning doc on disk (`docs/plans/<slug>.md` or the
  repo's convention); the task itself is a thin pointer. Bulk stays out of
  the task list until it's actually time to implement.

## Commands

Most bare user messages map to one of these; when ambiguous, ask (via `attn`
if Max is away).

- `add idea: <text>` — capture to the task list; feasibility-triage if
  complex.
- `do next` / `do next: <hint>` — run the selection algorithm now.
- `status` — current task, queue summary, recent completions.
- `pause` / `resume` — TaskStop the heartbeat monitor / re-arm it.
- `wrap up` — land the current increment cleanly, commit, summarize.

## Guardrails

- Commit each increment. Never push or deploy unless the project's CLAUDE.md
  or config explicitly authorizes it.
- Verification before completion: tests/lint pass before a task is marked
  completed.
- Experiments are feature-gated.
- Compaction-safe: durable state lives in the task list, planning docs, and
  commits — never only in conversation.
- Communication: brief updates as you go; `attn` only for genuine blockers,
  questions, or notable milestones. Subagents never use `attn`.

## Wake mechanisms (variants)

The Monitor heartbeat above is the default and preferred mechanism. A
Stop-hook variant ("fire back after a time": the Stop hook sleeps ~285s then
returns `{"decision":"block","reason":"dream tick"}`) is viable — the hook
default timeout is 600s — but it is a workaround: loop prevention is entirely
on the hook author (guard with a counter or marker file), and user input
during the sleep window is not well-defined. Prefer Monitor; consider `/loop`
where available; reserve the Stop-hook pattern for harnesses that have hooks
but no Monitor tool.
