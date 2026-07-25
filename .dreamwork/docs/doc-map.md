# Doc map — ud-dreamwork (the skill, self-hosted target)

What lives where, and what the loop keeps current. Link outward; never
duplicate content that has a home below. Single-source rule: a fact
lives in exactly one doc — generic reference (useful to every target)
at the skill root, instance-specific knowledge under `.dreamwork/` —
and everything else points at it. The skill root is shipped product:
this instance is its upstream maintainer, so docs-freshness passes
cover it too.

| Doc | Covers | Loop keeps current? |
|---|---|---|
| `SKILL.md` | The product: philosophy, loop, selection, subagents, durable state, commands, guardrails | Yes — every behavior change lands here or in a reference file |
| `initialization.md` | The 11-step init procedure | Yes |
| `reflection.md` | Post-change checklist | Yes |
| `file-formats.md` | Required shapes for loop-written, tool-parsed files; questions.md in full | Yes — a reader change lands here in the same commit |
| `.dreamwork/docs/reviews-*.md` | Fresh-eyes review findings, kept whole; the fixes land separately | Keep while its proposals are unspent |
| `compaction.md` | Pre-compaction checklist, the notice protocol, per-client sending safeguards | Yes — client dialects change |
| `writing-plugins.md` | Plugin-authoring contract, extension seams, state split | Yes — validate against each new plugin |
| `watch-design.md` | watch.py standing design: routes, confinement, write exceptions, contract | Yes — shipped beside the tool it documents |
| `stop-hook-variant.md` | Unimplemented wake fallback design | Only if implemented or invalidated |
| `DREAMWORK.template.md` | Wizard seed for new targets | Yes — must track wizard section changes |
| `migrations/` | Versioned target-affecting changes; latest filename = version | Append-only; README holds the protocol |
| `.dreamwork/docs/plans/` | Active feature plans (ud-dreamtask, ud-dreamwork-github, artifact-templates, daemon-mode, dreamhub-stage1, parallel-architecture, goal-hierarchies) | Prune when features fully land |
| `.dreamwork/docs/spikes/` | Timeboxed experiments that answered a question with a number; the branch holds the diff | Keep — a measured answer outlives the code that produced it |
| `.dreamwork/review/` | Rich decision artifacts paired with a questions.md entry | Banner them decided; archive with the answered question |
| `.dreamwork/{lessons,questions}.md` | Distilled lessons; asks for the human | Yes — groomed in rotation |
| `.dreamwork/tasks.md` | The queue's durable half: open tasks, permanent ids, next id | Yes — same commit as any queue change |
| `.dreamwork/docs/github-processes.md` | The repo's GitHub shape and conventions (ud-dreamwork-github plugin) | Yes — re-survey when CI, labels, or PR flow appear |
| `README.md` | Public face of the repo: what dreamwork is, install, where to start | Yes — must not drift from SKILL.md |
| `lint.py` | Checks a target's `.dreamwork/` against the shapes its readers require, by calling the real readers | Yes — a reader change lands here in the same commit |
| `dreamhub-design.md` | dreamhub standing design: the stage-1 boundary and its checks, the origin-per-project deviation, and the exact status.json / watch-port / `/mtime` / `/data.json` fields the hub depends on (guards: `dev/hub/README.md`) | Yes — shipped beside the tool it documents |
| `roll.py` / `watch.py` / `heartbeat.py` / `dreamhub.py` docstrings | Tool contracts (advisory dice; dashboard; the wake tick; the multi-project hub) | Yes — contracts live in the docstrings |
| `test_watch.py` / `test_roll.py` / `test_heartbeat.py` / `test_lint.py` | The Python half of verification — asserts on generated source, cannot see what renders | Yes — a behaviour change ships with its test |
| `dev/capture/` | The structural half: browser guards (exit non-zero, gated by `just test`) plus print-only capture scripts | Yes — a guard joins `GUARDS` when its feature lands |
| `dev/capture/fixture/` | Frozen miniature target the guards run against, so a red light means the code broke | Yes — extend it when the parser learns a new input shape |
| `justfile` | Common tasks: test (both halves), pytest, guards, watch, audit-styleguide | Yes — a new routine worth repeating becomes a recipe |
| `DREAMWORK.md` (repo root) | This target's own goals, philosophy, preferences, plugin decisions | Yes — folded whenever the human reveals a durable preference |

**Routing rule — a finding lands where its trigger lives.** Behaviour
that must fire unprompted goes in SKILL.md; the shape of a file goes in
`file-formats.md`; a procedure with a nameable trigger (init,
compaction, plugins) goes in that trigger's reference file. SKILL.md is
re-read on every reload and fires on nothing in particular, so it is the
default destination only for things with no better trigger — it grew 246
to 433 lines in one day by being everyone's default (#120, #145).

SKILL.md is the entry point for the harness; README.md is the entry
point for a human browsing the forge. The README stays minimal on
purpose — what this is, how to install it, where to look — and every
fact in it has its home in a doc above.
