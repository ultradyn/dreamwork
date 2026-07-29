---
name: ud-dreamwork-matt-pocock-skills
description: >
  Dreamwork bridge plugin — adapts the installed mattpocock/skills suite to the
  Dreamwork protocol WITHOUT rewriting it. The suite runs unchanged; this plugin
  is the translation at three seams only: the task ledger (the suite's "tracker"
  becomes `dev/ledger.py`), the grill-to-questions scoping (one grill question →
  one `questions.md` entry via `watch.human_block`), and the suite's per-repo
  `docs/agents/*.md` dials. Read-only floor: it files tasks and poses questions
  through the loop's single writers and takes no elevated action. Load only via
  an explicit DREAMWORK.md `Load:` line.
---

# ud-dreamwork-matt-pocock-skills — bridge to the mattpocock/skills suite

A plugin to [ud-dreamwork](../../SKILL.md); its Guardrails and
`writing-plugins.md` bind everything here. The settled design is
[`.dreamwork/docs/plans/matt-pocock-skills-bridge.md`](../../.dreamwork/docs/plans/matt-pocock-skills-bridge.md)
— read it; this SKILL.md is the operator-facing summary, the design is the
authority.

## The one rule

**The suite runs unchanged.** No suite file is edited, forked, shadowed, or
wrapped-in-place. The suite is read where it is installed and invoked as-is.
"What to change to make it compatible" is a written note in the design (§9),
not a set of edits anyone makes. The bridge configures the suite's per-repo
dials and translates at the call boundary — that is the full surface.

## The three seams (and the three binding constraints)

- **The task seam (C1).** The suite's "publish to tracker" / triage-state calls
  route through `dev/ledger.py` verbs — `file`, `fold --note`, `counts` —
  invoked as SUBPROCESS calls from `tracker_adapter.py`. The adapter **never
  opens `.dreamwork/tasks.md` or `.dreamwork/ledger.sqlite3`** and **never
  branches on source-of-truth**: the verb dispatches on `source_of_truth`
  internally, so the #294 markdown→store cutover is invisible to the bridge by
  construction.
- **The grill seam (C2).** A grill question becomes one `questions.md` entry
  written through the production `watch.human_block()` (the only correct way to
  write human/loop text into that file — it cannot forge an entry). The
  adapter invents **no author tag**: it uses only the closed set
  `watch.NOTE_TAGS` / `watch.ANSWER_TAGS` already hold, imported, never
  restated. Grilling is human-in-the-loop; the bridge poses, never resolves.
- **The config seam (C3).** Machine-local bridge state (the resolved suite
  path, any issue↔ledger-id cache) lives under
  `~/.config/dreamwork/matt-pocock/<target-slug>/` — ephemeral, gitignored,
  rebuildable from the durable truth. The bridge writes **nothing new under
  `.dreamwork/`**; dreamhub reads no bridge-specific file.

## The tracker-adapter contract (design §8) — the bridge's one real spec

`tracker_adapter.py` maps the suite's issue-tracker operations onto Dreamwork:

| suite operation | bridge action | Dreamwork seam |
|---|---|---|
| create issue / publish ticket | file a task | `dev/ledger.py file <title> …` |
| close / wontfix | land with a note | `dev/ledger.py fold <id> --note …` |
| list open issues | read open ids | `dev/ledger.py counts …` |
| set state `needs-info` | ask the human | `questions.md` via `watch.human_block()` |
| set state `ready-for-agent` | (default — a filed candidate) | — |

The adapter shells out to the verb; it does not link the ledger module into the
suite's process. T1–T5 (in `tests/`) pin these invariants.

## Invocation buckets (design §11)

The suite mixes invocation modes; under Dreamwork the coordinator dispatches and
the human steers via the dashboard, so reach is three-valued. The bridge states
which bucket each skill falls in so neither a coordinator nor a reviewer infers
reach from the suite's frontmatter alone:

- **Human-typed (the spine default).** `grilling`, `to-spec`, `to-tickets`,
  `triage`, `implement`, `domain-modeling`, `handoff`, `prototype`,
  `setup-matt-pocock-skills` are `disable-model-invocation: true` — reachable
  only by the human typing the name. The bridge does not make these
  model-invoked; their task asks / questions get the seam treatment whatever
  files them.
- **Loop-dispatched as a subagent (gated).** `research`, `code-review` are
  model-invoked in the suite. The loop **may** dispatch them as read-only
  subagents, but that is an agent-initiated surface → the scope gate, and
  **default off** at the floor. When dispatched, their output feeds
  tasks/questions, never bypasses.
- **Never autonomous: anything that decides with him.** `grilling`,
  `domain-modeling` (HITL branch), HITL tickets — the loop never stands in for
  the human's side. The bridge routes their questions to `questions.md` and
  stops.

## Authority model (design §7) — read-only floor

**At the floor (no authority line needed):** read the installed suite (resolve
by name, never a broad scan); configure the suite's `docs/agents/*.md` dials;
file tasks through `dev/ledger.py file`; fold/note through the verbs; write grill
questions to `questions.md` through `human_block()`; dispatch
`research`/`code-review`/`prototype` as **read-only** subagents whose output
feeds tasks/questions.

**Explicitly NOT granted (recorded so they are not re-proposed):** no handoff
authority (`handoffs.md` + `relay.py` stay the single writer's channel); no
autonomous grilling; no dual queue / poll loop / second inbox; no edits to suite
files, `CLAUDE.md`, `AGENTS.md`, `CONTEXT.md`, `DREAMWORK.md`,
`file-formats.md`, or `lint.py`.

**Elevated actions, each a separate DREAMWORK.md line he grants by name:**
`comment` / `push` / `open-pr` / `merge` (only meaningful against a real remote
tracker); `file-as-task` (letting loop-generated specs/tickets enter the ledger
without a human steer — the scope-gate override); `dispatch-review` /
`dispatch-prototype` (autonomous tool dispatch). Autonomous dispatch and
self-filing are gated on the **posture autonomy axis** (plan
`posture-autonomy-axis.md`, tasks #493/#495) — until that axis exists the
default stands: human-invoked only. **Silence keeps the floor.**

## State summary

- `.dreamwork/tasks.md` / `.dreamwork/ledger.sqlite3` — the ledger, written
  ONLY through `dev/ledger.py` (the adapter shells out; C1).
- `.dreamwork/questions.md` — the grill chain, written through
  `watch.human_block()` (C2).
- `docs/agents/issue-tracker.md` — the suite's own configurable dial, pointed
  at the ledger seam (written only at activation, NOT in this slice).
- `~/.config/dreamwork/matt-pocock/<target-slug>/` — machine-local ephemera
  (resolved suite path, cache), gitignored, rebuildable (C3).
- dreamhub reads **none** of the machine-local state; the bridge's liveness is
  the ledger's liveness and the questions count, both already on the dashboard.

## Extension points used / declined

- **Init** (used): detect the installed suite by name (no scan); if present and
  not configured, propose the bridge through `questions.md`. On a recorded yes,
  write `docs/agents/issue-tracker.md` → the ledger seam. *(Not in this slice:
  activation is grant-gated.)*
- **Tasks** (used — the main job): the bridge IS the issue-tracker adapter the
  suite calls; `tracker_adapter.py` is the contract.
- **Maintenance** (used, lightly): one rotation item — re-resolve the suite
  path and re-check `docs/agents/*.md` against drift. `dreamwork(maintain:matt-pocock-config)`.
- **Tick flow** (declined — A′ removal): no poll loop, no dual queue, no Monitor.
- **Commands** (declined for v1): the spine skills are user-invoked; typing the
  name already works.

## Non-goals (this slice)

Loading/activation on any target; `docs/agents/*.md` writes; tick flow / poll /
commands menu; autonomy gating code; handoff adoption; autonomous grilling. See
the brief (`#500`) and design §5/§7 for the deferrals.
