# Dreamwork initialization

Run this once per session, at loop start or on resume — not on every reload
of SKILL.md. If the heartbeat is already armed and DREAMWORK.md has been
read, initialization has already happened; return to the loop.

1. **Target.** Confirm which project the loop is dreaming on (default:
   the session's cwd). Every later step is relative to the target.

2. **DREAMWORK.md — read first.** Look for `DREAMWORK.md` at the target's
   root — the persistent memory of what the human wants from this project.
   If it exists, read it before anything else: it holds the human's very
   high-level goals, the project's philosophy, working preferences and
   routines, and plugin decisions. It is the primary source for judging
   what work fits. If it doesn't exist, note that — the wizard (step 4)
   will create it.

3. **Plugins.** Skills named `ud-dreamwork-*` are plugins to this loop;
   they may extend later initialization steps (including the wizard) and
   the loop itself. Discover what's available from the skills visible to
   you (the available-skills list — never by listing directories; if
   details are hidden or descriptions load lazily, use the harness's
   list-skills command). Resolve against DREAMWORK.md's Plugins section,
   which records both positive and negative decisions (load these; don't
   load those):
   - Recorded positive → load silently. Recorded negative → skip silently.
   - Unrecorded or newly-appeared plugins → ask the human which, if any, to
     load, and persist the answer to DREAMWORK.md either way (a "no" is a
     decision too — it stops repeat asking).
   - No DREAMWORK.md yet: if any plugins are visible, ask now; the wizard
     records the decisions.
   Invoke the chosen plugins before continuing. None visible: skip
   silently.

4. **Setup wizard (only when DREAMWORK.md is absent).** Runs after plugins
   so loaded plugins can extend or reshape the interview. A short
   interview, not a questionnaire — smooth, and sized to the human:
   - Elicit as much as the human wants to give, and no more. Partial
     answers are first-class: skipped sections keep their template
     comments as visible unfinished markers, and the file fills in
     incrementally later as the human adds ideas and preferences.
   - When the repo already says a lot (CLAUDE.md, README, code), propose
     drafted answers and ask what's wrong or missing — don't ask cold
     open-ended questions the repo can answer.
   - One topic per message. Answers often spill across sections; file
     each point where it belongs instead of re-asking.

   Ask about, in order:
   - *Goals* — very high-level, human-focused: what does the human want
     this project to be or do for them/its users? (We should always know
     what the human wants so we can make what the human needs.)
   - *Philosophy* — values and taste that should shape decisions (e.g.
     "feels alive and communal", "boring tech, exciting product").
   - *Preferences & routines* — cadence, communication style, autonomy
     bounds (push/deploy?), recurring chores worth scheduling.
   - *Plugins* — confirm the step-3 decisions, positive and negative.
   - Any questions contributed by loaded plugins.
   Write the answers to `DREAMWORK.md` — start from `DREAMWORK.template.md`
   in this skill's directory (sections: Goals, Philosophy, Preferences &
   Routines, Plugins; replace the guidance comments with real content) —
   confirm it back to the human, and treat it as committable project
   content.

5. **Heartbeat.** Start the wake timer — 4.75 min stays under the 5-minute
   prompt-cache TTL, keeping the loop cheap:

   `Monitor command="heartbeat 4.75m 'dream tick'" triggerTurn=true persistent=true`

   No regex filter. If the `heartbeat` CLI is absent, fall back to
   `while true; do echo 'dream tick'; sleep 285; done`. Re-arm after session
   restart or resume. (Same mechanism as the heartbeat-monitor skill.)

6. **Task backend.** Native Claude Code task tools (TaskCreate / TaskList /
   TaskGet / TaskUpdate) by default. If the target already has backlog
   configured (a `.backlog/` dir at its root), use `bl` instead: `bl howto`,
   `bl idea`, `bl next` / `bl grab` / `bl cycle`. With `bl`, map the
   skill's task conventions (priority, type, size, next-up queue-jumps)
   onto bl's own fields and mechanisms — the loop semantics stay the same.

7. **Orient.** Read the project's CLAUDE.md and any goals/philosophy docs —
   together with DREAMWORK.md these bound what the loop may do (including
   whether push/deploy is authorized). Read `.dreamwork/docs/` (living docs
   maintained by the dreamers) and skim recent `.dreamwork/dreams/` entries
   — they carry memory from earlier sessions and subagents. Learn the
   project's verify commands (justfile, package scripts: test, lint,
   build) — you'll run them every increment. Skim the recent git log
   (~10 commits) to absorb current direction and granularity.

8. **Reconcile.** `git status` — a dirty tree is unfinished prior work:
   understand it first, then land it as an increment or park it (stash +
   task) before starting anything new. Check the task list for in_progress
   tasks left by a previous session and verify each against reality (git
   log/diff): mark done what's done, split what's half-done, don't trust
   stale status.

9. **Green baseline.** With the tree reconciled, run the test suite once
   before any new work. Green means every later failure is attributable to
   your own increments. Red means fixing (or explicitly documenting) the
   breakage is your first task — never dream on top of an unexplained red
   baseline.

10. **Seed (first run).** If the task list is empty, capture obvious
    candidates surfaced while orienting — TODO/FIXME markers, planning
    docs, README roadmap items — as pending tasks with priority/size
    metadata. Don't force volume; the selection algorithm's brainstorm
    step handles a thin list later.

11. **Status.** One-paragraph opening status to the human: project,
    baseline state, loaded plugins, what you'll do first, queue depth.
