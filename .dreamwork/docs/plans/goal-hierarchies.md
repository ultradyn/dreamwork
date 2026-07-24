# Goal hierarchies — incubation plan (#95)

Human-proposed 2026-07-25 (~09:00): "support goals, and hierarchies of
goals, and a session goal and a task goal. when we're doing a task we
should know the task goal and the session goal and any goals in between
(in the hierarchy). similarly, for user goals we should create a
hierarchy and know the current branch."

## The idea in one line

Make the loop's alignment machinery *mechanical*: every piece of work
sits on an explicit chain from the user's highest goals down to the
increment in hand, and the active branch is always known.

## Core shape

- **The hierarchy is one tree.** Root: the user's very-high-level goals
  (DREAMWORK.md Goals — already the wavelength reference). Under them:
  durable sub-goals (project-scale, e.g. "watch is a real product"),
  then session goals, then task goals. One tree, not parallel
  taxonomies — "user goals" vs "task goals" are depths, not kinds.
- **DREAMWORK.md Goals grows nesting.** Indented sub-goals under each
  top-level goal; stable and human-edited, like the rest of the file.
  The wizard elicits only the top level; sub-goals accrete from work.
- **Session goal.** Declared in the opening status (init step 11) and
  written to status.json (`goal` field) — one line naming what this
  session serves and which durable goal it hangs under. Re-declared on
  a pivot (the human's steer *is* the pivot signal).
- **Task goal.** Task metadata gains `goal` (one line) and `parent`
  (which goal above it serves — a session goal or a DREAMWORK.md
  sub-goal by name). Cheap: two metadata fields, no new store.
- **The active chain.** At any moment: task goal → session goal → the
  DREAMWORK.md branch above it. Selection states the chain when
  starting a task (one line in the status update); the scope gate's
  fit-check becomes "name the chain — if you can't, park it in
  questions.md". Watch renders the chain (status.json already flows).

## What this deliberately is NOT

- Not a planning bureaucracy: chains are one-liners, named at task
  start, never a document per goal.
- Not a new file: the tree lives in DREAMWORK.md (durable) +
  status.json (session) + task metadata (leaves).
- Not retroactive: existing tasks don't get back-filled; chains attach
  as tasks are started.

## Open design questions (need Max; recs inline)

1. Where do session goals persist beyond status.json (which is
   ephemeral)? Rec: they don't — a session goal that outlives its
   session was a durable sub-goal all along; promote it into
   DREAMWORK.md at wrap.
2. Should selection *enforce* branch focus (prefer active-branch tasks)
   or just *state* the chain? Rec: state-only first; observe whether
   drift actually happens before adding preference weights.
3. Task `parent` naming: free-text goal names or stable ids? Rec:
   free-text matching DREAMWORK.md headings — human-readable, and the
   coherence rotation catches dangling names.

## Build stages (post design review)

1. SKILL.md: task-conventions gain goal/parent; selection states the
   chain; scope gate wording. DREAMWORK.md template + self-hosted file
   gain nested Goals.
2. Init/wrap: session-goal declaration + wrap-time promotion.
3. status.json `goal` field + watch chain rendering (fresh dreamer).
4. Migration entry (task-metadata + status.json shape).
