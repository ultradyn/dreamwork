# ud-dreamtask — bounded dreamloop for one task (incubation plan)

Human-proposed 2026-07-25 (~04:00). Sister skill to ud-dreamwork: the
same philosophy — small verified increments, reflection over momentum,
capture everything, heartbeat cadence — applied to completing ONE task,
then stopping. Dreamwork is a garden; dreamtask is an errand.

## Core shape

- **Invocation**: `/ud-dreamtask <task description>` (big or small).
- **Opening**: a mini-wizard establishes acceptance criteria — "what does
  done look like?" — plus size estimate and any constraints. Written to
  the dreamstate before work starts.
- **Loop**: identical tick flow (mid-task checkpoint / finished→verify+
  commit / next increment), but selection is a walk through the task's
  own decomposition, not an open-ended algorithm. No brainstorming, no
  backlog — out-of-scope ideas still get captured (handed to the repo's
  dreamwork loop if one exists, else left in the dreamstate for the
  human).
- **Termination**: when acceptance criteria verify, wrap up
  automatically: land, summarize, offer durable learnings upstream (repo
  docs / KB / lessons), archive the dreamstate.
- **Maintenance scaling**: beats budgeted by size — roughly one
  reflection/self-review beat per ~20 minutes of estimated work; a
  15-minute task gets only the closing verification. Possibly
  `roll.py --budget N` reusing the dice.

## State

- Repo has DREAMWORK.md → defer to it (goals/philosophy/autonomy bind as
  usual); dreamstate still holds the task-scoped files.
- No DREAMWORK.md → no wizard detour: ephemeral dreamstate at
  `~/.config/dreamwork/tasks/<slug>/` (proposed; consistent with the
  machine-local home precedent from roll-state design): `task.md`
  (description + acceptance criteria), `questions.md`, `status.json`,
  `dreams/` if any. Archived (moved to `tasks/archive/`) on completion.

## Open design questions (need Max)

1. Composition: can a dreamtask run inside an active dreamwork session
   (sub-loop), or standalone-only first? (Rec: standalone first.)
2. Heartbeat: same 4.75m cadence regardless of task size? (Rec: yes —
   cadence is about cache economics, not task size; short tasks just see
   fewer ticks.)
3. Naming: `~/.config/dreamwork/tasks/<slug>/` confirmed? (Rec: yes.)
4. Does dreamtask adopt commit markers/verification guardrails wholesale?
   (Rec: yes by reference to ud-dreamwork, minus rotation-specific
   parts.)

## Build stages (once design confirmed)

1. SKILL.md draft (lean; references ud-dreamwork's reflection.md and
   shared conventions rather than duplicating).
2. Init-lite: target/criteria wizard, dreamstate creation, heartbeat.
3. Completion path: verify → wrap → upstream learnings → archive.
4. Dogfood on a real task; fold friction.
5. install-symlinks + llm-general index entry (concise pointer).
