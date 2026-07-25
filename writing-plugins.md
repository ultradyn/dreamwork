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
  conventions (priority/type/size, and a namespaced key like `gh:` for
  plugin-specific identity). Plugin tasks join normal selection — no
  private queues. A plugin never writes `.dreamwork/tasks.md`: the
  coordinator is its only writer. Work whose identity is already durable
  upstream — a GitHub issue, an upstream ticket — keeps that id instead
  of taking one of the loop's: as a candidate it competes in selection
  like anything else, but it earns no loop id, because the next poll
  re-derives it and a busy forge would otherwise flood the loop's
  numbering. Once the loop actually starts such an item it does earn one
  (a poll re-derives the issue, never the branch or the half-landed
  increment) — the coordinator mints it at that moment.
- **Forge items and the scope gate.** Ingesting an item is never gated;
  *starting* one is. An item the human authored or triaged upstream is a
  human-initiated steer and passes. Anything else is agent-initiated:
  the gate applies, the issue's stated purpose serves as the task goal,
  and the parent still has to be nameable — an issue nobody here asked
  for is exactly the case the gate exists for.
- **Commands.** Add commands if genuinely needed; never repurpose or
  shadow core ones. Declare them in the plugin's SKILL.md so humans and
  agents can read them, and the loop copies them into the target at
  plugin resolution as `.dreamwork/plugin-commands.json` — whole, never
  appended — where the composer can see them. Shape and reasoning:
  `file-formats.md`; `lint.py` enforces it.

  The copy exists because **`watch.py` reads the target** and plugin
  skills do not live there — they sit in `~/.claude-p/skills/`,
  `~/.agents/skills/`, and elsewhere, varying by harness and machine. A
  composer reading the plugin's own files would work on one machine and
  silently show nothing on the next. Consequences worth knowing before
  you design around them:

  - **`kind` is a wire token**: lowercase `namespace-name`, the
    namespace being the plugin's own (`gh-sync`, not `sync`, and never
    the core namespaces). The human sends `kind: text` exactly as with a
    core command. Collisions are refused by the linter rather than
    forbidden in prose — this paragraph used to be the only thing
    standing between a plugin and a hijacked `do-next`.
  - **Plugin commands live in the `...` menu, not the main row.** There
    is no way to ask otherwise. Loading a plugin can add to the composer
    and can never degrade it.
  - **Unloading is the absence of a write.** Because the file is rewritten
    whole, a removed plugin's commands vanish at the next resolution with
    nobody deleting anything. The linter cross-reads DREAMWORK.md and
    errors on a command whose plugin is not loaded, so a stale menu entry
    — one the human can send and nothing answers — cannot sit there
    quietly.
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

## Reviewing a plugin

Every new or substantially-changed plugin gets a fresh-eyes review — a
dreamer that did not write it, using the checklist below as its rubric.
The review checks the plugin against three sources: this contract, the
plugin's approved plan *including later amendments* (cadence changes,
authority tweaks — recorded in the plan's status header or questions.md
thread), and the core SKILL.md guardrails it inherits.

- **Fix in place**: prose drift, stale values superseded by amendments,
  checklist gaps with an obvious resolution, frontmatter defects. Commit
  in the plugin's repo, matching its log style.
- **Report, don't guess**: anything needing a human call — scope or
  authority ambiguity, a seam whose justification is unclear, behavior
  the plan never authorized. These go to the coordinator, who parks them
  in `questions.md`.
- **Verdict**: `PASS` (with fixes listed) or `issues found` (with the
  human-decision items). A review that changes nothing still reports —
  silence is indistinguishable from not looking.

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
