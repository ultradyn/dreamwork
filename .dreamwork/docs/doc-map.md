# Doc map — ud-dreamwork (the skill, self-hosted target)

What lives where, and what the loop keeps current. Link outward; never
duplicate content that has a home below.

| Doc | Covers | Loop keeps current? |
|---|---|---|
| `SKILL.md` | The product: philosophy, loop, selection, subagents, durable state, commands, guardrails | Yes — every behavior change lands here or in a reference file |
| `initialization.md` | The 11-step init procedure | Yes |
| `reflection.md` | Post-change checklist | Yes |
| `stop-hook-variant.md` | Unimplemented wake fallback design | Only if implemented or invalidated |
| `DREAMWORK.template.md` | Wizard seed for new targets | Yes — must track wizard section changes |
| `migrations/` | Versioned target-affecting changes; latest filename = version | Append-only; README holds the protocol |
| `.dreamwork/docs/plans/` | Feature plans (watch-py.md) | Prune when features fully land |
| `.dreamwork/{lessons,questions}.md` | Distilled lessons; asks for the human | Yes — groomed in rotation |
| `roll.py` / `watch.py` docstrings | Tool contracts (advisory dice; dashboard) | Yes — contracts live in the docstrings |

No public-facing README exists; SKILL.md is the entry point by design
(skills are consumed in-harness, not browsed on a forge).
