# ud-dreamtask — bounded dreamloop for one task (build plan)

> **Status (2026-07-25 12:11):** design confirmed by Max — "rec lgtm"
> (10:47), taking all four recommendations. The Open-questions section is
> gone; its answers are folded into the shape below and restated once in
> **Settled**. Build stages revised accordingly. Two things the folding
> surfaced are recorded in **Findings from the fold** — one bullet the
> answers dissolve, one seam the answers do not settle. Prune this plan
> when dreamtask has completed a real errand end to end.
>
> **Built (2026-07-25 12:16):** stages 1-3 and 5 —
> `/home/xertrov/.llm-general/skills/ud-dreamtask/` (own git repo,
> symlinked into `~/.claude/skills/`), index pointer, doc-map row,
> README line. Coordinator rulings 12:12 folded below (location, hub
> opt-in, stage-6 handoff). Remaining: stage 4 (dogfood) and stage 6
> (gated).

Human-proposed 2026-07-25 (~04:00). Sister skill to ud-dreamwork: the
same philosophy — small verified increments, reflection over momentum,
capture everything, heartbeat cadence — applied to completing ONE task,
then stopping. Dreamwork is a garden; dreamtask is an errand.

Chain: this serves **"make 'leave an agent dreaming on a project' a real
workflow"** (DREAMWORK.md) by extending it to the shape a human reaches
for far more often than a garden — one bounded job, walked away from.

## What it is, and what it is not

- **dreamtask is a LOOP SHAPE**: one errand, one agent, terminates. It
  never serves a page.
- **dreamhub is a SURFACE**: many loops seen from outside. It never runs
  one.
- They meet only as a **data contract**: a dreamtask's state has the same
  `status.json` / `questions.md` / `dreams/` shapes as any target, so a
  hub can list it without knowing what it is. Config namespaces are
  split — `~/.config/dreamwork/tasks/` is dreamtask's,
  `~/.config/dreamwork/hub/` is the hub's.
- dreamtask is **not a plugin**: it takes no `ud-dreamwork-` prefix, so
  the plugin discovery mechanism never sees it, and `writing-plugins.md`
  binds it only by analogy. It is a sibling skill that *inherits* the
  core Guardrails by reference.

## Core shape

- **Invocation**: `/ud-dreamtask <task description>` (big or small).
- **Opening**: a mini-wizard establishes acceptance criteria — "what does
  done look like?" — plus size estimate and any constraints. Written to
  the dreamstate before work starts. Criteria are written to be
  **checkable**: a command that exits non-zero where one exists,
  otherwise a statement precise enough that its failure would be
  visible. A criterion only a human can judge is marked as such at the
  opening, not discovered at the end.
- **Loop**: identical tick flow (mid-task checkpoint / finished→verify+
  commit / next increment), on the **same 4.75-minute heartbeat
  regardless of task size** — the cadence is cache economics, not work
  measurement; a short errand simply sees fewer ticks. Selection is a
  walk through the task's own decomposition, not an open-ended
  algorithm. No brainstorming, no backlog, **no maintenance rotation** —
  out-of-scope ideas still get captured (see Capture, below).
- **Termination**: when the acceptance criteria verify, wrap up
  automatically: land, summarize, offer durable learnings upstream (repo
  docs / KB / lessons), archive the dreamstate.
- **The other termination**: an errand that cannot verify must stop
  rather than grind. When consecutive increments produce no movement
  toward a criterion, or a criterion turns out to be unreachable as
  written, dreamtask stops, records the ask in its `questions.md`, and
  reports — it never quietly redefines done. dreamwork's answer to
  "nothing to do" is to idle until the next tick; an errand has no such
  answer, which is why this is stated here and not inherited.

## Guardrails — inherited, by reference

ud-dreamwork's **Guardrails** section binds dreamtask unchanged: commit
each increment, never push or deploy unless authorized, verification
before completion, experiments feature-gated, compaction-safe durable
state, every ask recorded, the scope gate, no `attn` from subagents.
dreamtask's SKILL.md **points at that section and does not restate it** —
a copied guardrail drifts from its original, and this repo has watched
prose drift from its own tool twice in one day.

Only what is genuinely different about an errand is stated in
dreamtask's own words:

- **Acceptance criteria are the termination test**, and they are fixed at
  the opening. Loosening a criterion to reach done is the failure mode
  this skill has and dreamwork does not.
- **No maintenance rotation, no brainstorm, no backlog.** The scope gate
  therefore has a shorter chain to name: increment → the errand's
  criteria. There is no session goal to invent.
- **Scope creep has one destination**: the dreamstate's capture list,
  never the errand.
- **`dreamwork(maintain:<item>)` commit markers do not apply** — that
  marker exists so `roll.py` can read staleness out of git, and an
  errand has no rotation to schedule.

## State — a target-shaped dreamstate

Home confirmed: `~/.config/dreamwork/tasks/<slug>/`. Inside it, the
dreamstate is **shaped like a dreamwork target**:

```
~/.config/dreamwork/tasks/<slug>/
  task.md              # description, acceptance criteria, decomposition, capture list
  .dreamwork/
    status.json        # same interface as any target (file-formats.md)
    questions.md       # same shape: `## Open` / `## Answered`, literally
    dreams/            # if any
```

The nesting is not decoration — it is what makes every existing reader
work on an errand with **zero new code**:

- `python3 <skill-dir>/lint.py --target ~/.config/dreamwork/tasks/<slug>`
  checks it, because lint resolves `<target>/.dreamwork`;
- `dreamhub add ~/.config/dreamwork/tasks/<slug>` lists it, because the
  hub's target test is "has a `.dreamwork/` or a `DREAMWORK.md`";
- `watch.py --target <that dir>` serves it, same reason.

Do not duplicate an interpreter: dreamtask writes these files to the
shapes stated in ud-dreamwork's `file-formats.md` and adds no second
description of them. `task.md` is dreamtask's own file with one reader
(the errand's agent) — it earns a `file-formats.md` row and a `lint.py`
check the moment a second thing reads it, which is exactly what the
harvest below would do.

**One home, no branch.** A repo's `DREAMWORK.md`, where present, changes
what *binds* (goals, philosophy, autonomy — read and obeyed as usual); it
never changes where errand state *goes*. An errand does not litter a repo
it may not own, and archiving stays uniform.

Archived on completion by moving to `~/.config/dreamwork/tasks/archive/`.

## Capture — one-way, out of the errand

Out-of-scope ideas land in the dreamstate's capture list. At wrap-up they
are **offered** upstream, and offering is a report, not a write:
**a dreamtask never writes another loop's `.dreamwork/`.** Task ids
belong to that loop's coordinator, `questions.md` is a structured file
with its own single-writer discipline, and a second writer racing either
one is how a record loses exactly what it exists to keep. The data flows
one way — dreamtask writes only its own dreamstate; dreamwork *reads*
dreamstates (below).

## Seeding dreamwork (human-added 2026-07-25) — gated

The ephemeral dreamstates double as **seed for dreamwork initialization**:
when full ud-dreamwork later initializes on a target that has past
dreamtask state under `~/.config/dreamwork/tasks/` (match by target
path), init harvests it — the wizard proposes Goals/Philosophy drafts
from what the errands revealed, captured-but-unactioned ideas become
task-list seeds, and the dreamstates promote into the repo's new
`.dreamwork/` (ephemeral graduates to durable; config-dir copies archive).
Errands accumulate wavelength; the garden starts with it.

This is the read direction of the one-way flow above, and it is the only
part of this plan that **changes ud-dreamwork's own core files**
(`initialization.md`, a `migrations/` entry, and — because harvest makes
`task.md` a two-reader file — a `file-formats.md` row plus a `lint.py`
check in the same commit). Those files are not dreamtask's to edit
unilaterally while other agents hold this tree: it is stage 6, and it
starts by asking the coordinator.

## Settled (2026-07-25, "rec lgtm")

1. **Standalone before sub-loop.** Build dreamtask as its own skill
   first; invocable from inside a live dreamwork session comes later.
2. **Same 4.75m heartbeat regardless of task size.** Cadence is about
   cache economics; short errands just see fewer ticks.
3. **`~/.config/dreamwork/tasks/<slug>/` confirmed** as the state home.
4. **Guardrails inherited by reference, not restated** — minus the
   rotation-specific parts, which do not apply to an errand.

## Findings from the fold

- **The "maintenance scaling" bullet dissolves.** It proposed budgeting
  reflection/self-review beats by size — "roughly one per ~20 minutes of
  estimated work; a 15-minute task gets only the closing verification" —
  and a possible `roll.py --budget N`. Answers 2 and 4 remove both
  halves: what it was scaling is the maintenance rotation, which an
  errand does not have, and roll.py's dice exist to pick rotation items.
  What remains is not scalable and is not dreamtask's to scale:
  `reflection.md` runs after **every** change, because small verified
  increments are the error-catching mechanism, and a skill that relaxes
  that is not inheriting the guardrails it claims to. A 15-minute errand
  gets one increment and therefore one reflection — which is the honest
  version of what the bullet was reaching for.
- **The queue label is wrong, and it matters slightly.** Task #50 reads
  "ud-dreamtask plugin". dreamtask has no `ud-dreamwork-` prefix, so it
  is never discovered as one, and answer 1 (standalone) settles that it
  is a sibling skill rather than an extension seam. Worth correcting in
  the ledger so nobody builds to `writing-plugins.md`'s contract by
  mistake. (Coordinator's call — the ledger has one writer.)
## Coordinator rulings (2026-07-25 12:12)

- **Location: a sibling directory with its own git repo** —
  `/home/xertrov/.llm-general/skills/ud-dreamtask/`, following the
  ud-dreamwork-github precedent. The deciding reason is that
  `../ud-dreamwork/SKILL.md` resolves from **both** trees, which was
  checked rather than assumed: from `~/.claude/skills/ud-dreamtask/` it
  resolves lexically (both skills are symlinked into that dir) and
  physically (the symlink lands beside its sibling in the source tree).
- **A dreamtask does not appear in a hub by default.** Errands are
  transient and gardens are not; auto-listing would fill the hub with
  dead rows inside a week, and the hub's job is "what needs me" at a
  glance. `dreamhub add <dreamstate>` works by construction, as a human
  action.
  - **Parked consequence, deliberately not solved here:** an errand
    *blocked on the human* is exactly what should surface somewhere, and
    today it sits in `~/.config/dreamwork/tasks/<slug>/` with a
    non-empty `awaiting_human` that nothing reads. Whoever takes dreamhub
    stage 2 or stage 6 inherits this question rather than rediscovering
    it. Do not build for it before then.
- **Stage 6 is a handoff, not an edit.** `initialization.md`,
  `migrations/`, `file-formats.md` and `lint.py` belong to the
  coordinator: write the exact change wanted and hand it over (the
  pattern dreamhub used for its justfile block), which is why nothing
  has been clobbered in a tree three agents share.
- **The ledger title was corrected**: #50 now reads "ud-dreamtask, a
  sibling skill (NOT a plugin; takes no ud-dreamwork- prefix)".

## Build stages

1. **SKILL.md draft** — lean; references ud-dreamwork's `reflection.md`,
   `file-formats.md`, and Guardrails rather than duplicating them.
2. **Opening** — the mini-wizard (criteria, size, constraints),
   dreamstate creation in the target-shaped layout, heartbeat armed.
3. **Completion path** — verify criteria → wrap → offer learnings
   upstream → archive the dreamstate. Includes the no-progress stop.
4. **Dogfood on a real errand**; fold the friction.
5. **Install** — symlink (`~/.claude/skills/ud-dreamtask`), llm-general
   index entry (concise pointer), one doc-map row, one README line.
6. **Harvest** (gated) — ud-dreamwork init reads past dreamstates:
   `initialization.md` + migration + `file-formats.md` row + `lint.py`
   check. Needs the coordinator's go, because it edits core files this
   plan does not own.

--- SUMMARY ---

- Design is confirmed; the plan now states the four answers as settled
  and no longer asks them.
- **Shape**: one errand, one agent, terminates on acceptance criteria
  fixed at the opening; same 4.75m heartbeat; no rotation, no brainstorm,
  no backlog.
- **Guardrails are inherited by pointing at ud-dreamwork's section.**
  Only four genuinely-different things are stated in dreamtask's own
  words: criteria are the termination test and cannot be loosened; the
  chain the scope gate names is shorter; scope creep has one destination;
  the maintenance commit marker does not apply. Plus a second termination
  — an errand that cannot verify stops and asks rather than grinding.
- **State** lives at `~/.config/dreamwork/tasks/<slug>/` with a nested
  `.dreamwork/`, which makes lint.py, dreamhub.py and watch.py work on an
  errand with zero new code and no second description of any format.
- **Capture flows one way**: dreamtask writes only its own dreamstate and
  hands ideas upstream by report; dreamwork's init reads dreamstates
  (stage 6, gated — it touches core files).
- **The fold dissolved one bullet** (maintenance-beat budgeting by size —
  answers 2 and 4 remove what it was scaling; reflection stays
  per-change) and **found one mislabel** (#50 says "plugin"; it is a
  sibling skill, not an extension seam).
- Stages: SKILL.md → opening → completion path → dogfood → install →
  gated harvest.
