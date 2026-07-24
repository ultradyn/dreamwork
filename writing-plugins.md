# Writing dreamwork plugins

A plugin is an ordinary skill whose name starts with `ud-dreamwork-` —
that prefix is the entire discovery mechanism. At initialization step 3
the loop finds plugins in its available-skills list (never by listing
directories), resolves each against the target's DREAMWORK.md Plugins
section, and invokes the ones recorded as load. One plugin, one concern:
a plugin earns its context cost or it doesn't load.

## Contract

- **It's a skill.** `SKILL.md` with `name` + `description` frontmatter.
  The description states what it extends and when to load it — the human
  reads it when the loop asks "load this?", so write for that moment.
- **Loading is a recorded decision.** DREAMWORK.md records both
  polarities (load these / don't load those); an unrecorded plugin
  triggers one ask, and the answer persists either way. Never re-ask,
  never auto-load on silence.
- **The core rules are inherited, not optional.** Everything in
  ud-dreamwork's Guardrails binds plugin behavior too: subagents never
  use `attn` and never touch loop machinery; every user-facing ask lands
  in `.dreamwork/questions.md`; the scope gate governs agent-initiated
  surface; commit-yes/push-no unless authorized. A plugin extends the
  loop; it never relaxes it.
- **Authority is explicit and per-action.** When a plugin can act on the
  outside world (comment, push, open PRs, call APIs that write), each
  action level is its own line in DREAMWORK.md, set via the wizard or an
  ask. Silence means the read-only floor, always.

## Extension points

The loop offers five seams; use the ones you need:

- **Initialization.** Plugins load before the wizard (step 4) precisely
  so they can reshape everything after it: add discovery/orientation
  work (e.g. survey a repo's GitHub conventions into
  `.dreamwork/docs/<domain>-processes.md`, with a doc-map entry),
  contribute wizard questions, extend the green-baseline checks.
- **Tick flow.** Add a per-tick check, or better, a Monitor (poll loop,
  log tail) that wakes the session on real events — with a tick-loop
  fallback for harnesses without a Monitor tool.
- **Tasks.** Feed work into the shared task list using the core
  conventions (priority/type/size metadata, plus a namespaced key like
  `gh:` for plugin-specific identity). Plugin tasks join normal
  selection — no private queues.
- **Commands.** Add `<plugin-thing>: ...`-style commands if genuinely
  needed; never repurpose or shadow core commands.
- **Maintenance.** Contribute rotation items; custom roll.py weights
  persist as a Routines line in DREAMWORK.md. Mark passes with the
  standard `dreamwork(maintain:<item>):` commit marker.

## State

- **Durable, project-owned** → `.dreamwork/` (committable: docs, plans,
  questions, discovered conventions). This is shared ground — follow the
  core file conventions rather than inventing parallel ones.
- **Machine-local ephemera** (cursors, etags, caches, auth-adjacent
  state) → `~/.config/dreamwork/<domain>/<target-slug>/`. Never commit
  these; never put them in `.dreamwork/`.
- **Versioned conventions.** If the plugin establishes durable
  target-side conventions that may later change shape, mirror the core
  migrations pattern: a `migrations/` dir in the plugin, a
  `.dreamwork/<plugin>-version` file in targets, update check at init.
  Skip all of it while the plugin owns no durable shape.

## The bridge-plugin pattern

The most common plugin isn't new machinery — it's a bridge to machinery
the repo already has: another task backend, an installed skill suite, an
improvement workflow the human already trusts. Orientation notices these
(init step 7) and suggests the bridge via `questions.md`; the plugin is
what a yes builds. A bridge:

- **Wraps, never wholesale-adopts.** The foreign tool keeps its identity;
  the bridge adapts each run to dreamwork's grain — scope reduced to an
  increment-sized slice, not the tool's natural full sweep.
- **Feeds, never bypasses.** Findings become tasks in the shared list and
  unclear calls become questions.md entries; the bridged tool never
  applies sweeping changes directly just because it could.
- **Schedules through the rotation.** Periodic runs (e.g. an
  architecture-improvement pass every few days) ride the maintenance
  rotation — roll.py's staleness weighting on `dreamwork(maintain:<item>)`
  markers produces that cadence naturally; no separate scheduler.
- **Runs autonomously only with a recorded authority line.** An explicit
  DREAMWORK.md line grants it, naming limits and the protocol for
  dangerous operations (destructive refactors, dependency changes,
  anything hard to revert → propose via questions.md instead of doing).
  Silence keeps the read-only floor, as always.

## Worked example

`.dreamwork/docs/plans/ud-dreamwork-github.md` designs the first real
plugin end to end — process discovery (init), issue/PR monitoring
(tick/Monitor), progression-until-blocked (tasks), per-action authority
(wizard + DREAMWORK.md), cursor state (config dir). Read it as the
template for how a plugin justifies each seam it uses; it shipped
2026-07-25 (`skills/ud-dreamwork-github/`) — building it validated this
document.

## Checklist

1. Name `ud-dreamwork-<thing>`; description written for the load-ask.
2. Each extension point used is listed in SKILL.md — init, tick, tasks,
   commands, maintenance — with what it does there.
3. Wizard questions contributed (if any) and where answers land in
   DREAMWORK.md, including explicit per-action authority lines.
4. State split: committable in `.dreamwork/`, ephemera in
   `~/.config/dreamwork/<domain>/<slug>/`.
5. Core guardrails restated where the plugin is most likely to strain
   them (usually external actions and subagent behavior).
6. Install like any skill (symlink scripts), concise index entry.
