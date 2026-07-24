# 2026-07-25 — goal hierarchies

## What changed

Alignment stops being a judgement call and becomes something you can
state. One tree: the human's goals at the root of DREAMWORK.md, durable
sub-goals nested underneath, a session goal, and a task goal at the leaf
— depths of one hierarchy, not separate kinds.

- **DREAMWORK.md Goals nest.** Indented sub-goals accrete under the
  top-level ones as work reveals them. The wizard still elicits only the
  top level.
- **Session goal**: declared in the opening status (init step 11) and
  written to `status.json` as `goal`. Re-declared on a pivot.
- **Task goal**: tasks carry a one-line `goal` and the `parent` they
  serve — a session goal, or a DREAMWORK.md sub-goal by name (free text
  matching the heading; the maintenance rotation's goal-alignment pass
  catches dangling names). Both live **on the ledger line**, beside
  priority and owner — not in backend metadata, which some backends
  accept but never read back.
- **Starting a task names the chain** — task goal → session goal → the
  DREAMWORK.md branch above it — in the status update. One line.
- **The scope gate is now "name the chain"**: if new surface area can't
  be traced upward without inventing a link, that is the answer, and it
  parks in questions.md.
- **Wrap promotes**: a session goal the project will keep wanting
  becomes a DREAMWORK.md sub-goal. Otherwise it dies with the session,
  which is correct.

Approved by the human 2026-07-25 with all three design recommendations:
session goals do not persist on their own, selection *states* the chain
rather than enforcing branch focus, and parents are free text.

## How to apply

Nothing breaks if you do nothing: tasks without a goal still select and
run. To adopt it, nest any sub-goals that already exist implicitly under
DREAMWORK.md's Goals, declare a session goal at the next init, and add
`goal`/`parent` **to the ledger line** as tasks are started — existing
tasks are not back-filled.

Check the carriers before trusting the gate. "Name the chain" binds only
where the chain reaches the actor being gated, so three things must
carry it: the ledger (task goal/parent), `status.json` (the session
goal), and every dreamer dispatch (the active chain). Adopting the
convention without the carriers produces a gate that reads well and
cannot be passed — which is how it shipped here for an hour.

Deliberately *not* included: selection does not prefer tasks on the
active branch. State the chain first and see whether drift is real
before weighting for it.
