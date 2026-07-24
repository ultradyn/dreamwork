# Goal hierarchies — what the coherence read found underneath

Dreamer: fresh-eyes coherence review of `d2eeb69` (goal hierarchies) and
`04968d1` (note authorship). The findings themselves went to the
coordinator; this is what is worth keeping past them.

## The lesson

**A guardrail that names a chain is only as strong as the weakest
carrier of the chain's middle link.** The scope gate got stronger as a
*rule* — "name the chain" replaces a judgement with something checkable
— and simultaneously weaker in practice, because it now depends on data
that has no durable carrier. The session goal lives only in
`status.json` (gitignored, rewritten each tick). The task `goal`/`parent`
live only in "task metadata", which the skill's own guardrail says the
default backend never reads back. So the two links the gate asks an
agent to name are exactly the two the loop does not persist.

Turning judgement into data is right. But data has to be *carried* to
every actor that must pass the gate. The gate now has three carriers to
fix, not one: the ledger (task goal/parent), the dreamer dispatch
payload (the active chain), and the tick's status.json field list.

## The sharp instance

The commit message says the old wording "degrades exactly where it
matters — long sessions, delegated dreamers, work the human did not see
start." Delegated dreamers is the case that got *worse*: SKILL.md's
dispatch list (DREAMWORK.md, docs, recent dreams, task context) has no
session goal, and status.json is not in it either. A dreamer asked to
name the chain must invent the middle link — which the gate defines as
the refusal.

Dogfood proof, same hour: the dispatch that produced this dream did not
carry a chain. Neither do the four ledger lines written after the change
(#111, #113, #114, #115) — none carries `goal` or `parent`. The
convention shipped and the practice did not follow, which is usually the
signal that the convention has nowhere to live rather than that anyone
forgot.

## Candidate lesson line (for `lessons.md`, coordinator's call)

- A rule that asks an agent to *state* something only binds where that
  something is durably carried to it — check the carriers before
  trusting the rule (`dreams/archive/2026-07-25-0926-goals-coherence.md`).

## Out-of-scope idea

`just audit-styleguide` proved a class of rule worth having: a
maintenance rule made checkable instead of remembered. Two of today's
findings are the same shape and could be cheap `just` recipes — a
dangling-parent check (every task `parent` resolves to a DREAMWORK.md
heading) and a prose-wrap check (SKILL.md lines over the file's own
column norm; today's two structural commits each left a scar).
