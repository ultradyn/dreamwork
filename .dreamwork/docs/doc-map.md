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
| `writing-plugins.md` | Plugin-authoring contract, extension seams, state split | Yes — validate against each new plugin |
| `watch-design.md` | watch.py standing design: routes, confinement, write exceptions, contract | Yes — shipped beside the tool it documents |
| `stop-hook-variant.md` | Unimplemented wake fallback design | Only if implemented or invalidated |
| `DREAMWORK.template.md` | Wizard seed for new targets | Yes — must track wizard section changes |
| `migrations/` | Versioned target-affecting changes; latest filename = version | Append-only; README holds the protocol |
| `.dreamwork/docs/plans/` | Active feature plans (ud-dreamtask, ud-dreamwork-github) | Prune when features fully land |
| `.dreamwork/{lessons,questions}.md` | Distilled lessons; asks for the human | Yes — groomed in rotation |
| `roll.py` / `watch.py` docstrings | Tool contracts (advisory dice; dashboard) | Yes — contracts live in the docstrings |

No public-facing README exists; SKILL.md is the entry point by design
(skills are consumed in-harness, not browsed on a forge).
