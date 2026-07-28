# #447 — Bundle `use-igcs`, and make the loop reach for IGC before it judges

Context: the human ruled that dreamwork should bundle the `use-igcs` skill
and instruct the loop to use it before any decision-making / design
judgement (#445 blocked on IGC being undefined in the tree). This doc
records **how** the bundling was chosen — by IGC, the method's first
dogfood here — plus the staleness story, the SKILL.md placement, the
lint-check decision, and the trailer. It is the companion to the code
change in `SKILL.md`, `igc-method.md`, and `igc-concepts.md`.

## The bundling decision — an IGC matrix

The four goals below are binary (or a breakpoint of *enough*), derived
from the brief plus two the brief implies. The rival ideas are the four
named in the brief and one the brief invites ("there may be a fourth").

**Goals**

- **G1** — A dreamwork install on a machine *without*
  `~/.llm-general/skills/use-igcs` still gets the method.
- **G2** — An upstream fix does not *silently* leave a stale copy here
  (staleness breakpoint stated + how it is detected — not "zero staleness").
- **G3** — The loop reaches the method in a single step at the moment of
  the choice.
- **G4** — Nothing depends on a path outside the skill directory at
  runtime.
- **G5** — The *full* method is reachable — worked example **and** the
  conceptual grounding (`cf-concepts`: decisive vs indecisive errors,
  breakpoint conversion, differentiation) — not an abbreviated core. (The
  brief's depth emphasis: "the currency of every review artifact"; "getting
  it by feel would be the whole failure".)
- **G6** — The bundle fits dreamwork's structure (a reference doc the skill
  loads by path), not a nested skill with its own `name:` frontmatter that
  implies a second installable skill in the tree.

**Matrix**

| Idea | All | G1 | G2 | G3 | G4 | G5 | G6 |
|---|:---:|:--:|:--:|:--:|:--:|:--:|:--:|
| **A** — vendor the full `use-igcs` skill verbatim as a nested skill | ✘ | ✔ | ✔ | ✔ | ✔ | ✔ | ✘ |
| **B** — declare a dependency; load `use-igcs` by name at runtime | ✘ | ✘ | ✔ | ✔ | ✘ | ✔ | ✔ |
| **C** — restate a condensed IGC section in `SKILL.md` + pointer to the full skill | ✘ | ✔ | ✔ | ✔ | ✔ | ✘ | ✔ |
| **D** — instruction in `SKILL.md`; vendor full method + concepts as reference docs | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |

**Decisive errors (the ✘s)**

- **A ✘ G6** — a verbatim `use-igcs/SKILL.md` keeps its `name: use-igcs`
  frontmatter, so a skill loader scanning the tree sees a *second*
  installable skill inside ud-dreamwork — two skills claiming one tree, and
  the copy masquerading as independently installable. The fix (strip the
  frontmatter) is exactly what turns A into D.
- **B ✘ G1** — a machine without `use-igcs` installed cannot load it by
  name, so the method is absent precisely where G1 says it must work.
  **B ✘ G4** — loading by name depends on the harness resolving a skill
  from outside this skill's directory at runtime.
- **C ✘ G5** — a condensed core loses `cf-concepts`: decisive-vs-indecisive
  errors, breakpoint conversion, differentiation. That depth is what stops
  the matrix being misapplied (marking ✘ for an indecisive quibble, failing
  to convert "fastest" to a breakpoint). The pointer to the full skill is
  out-of-tree and absent on a foreign install, so the depth is unreachable
  exactly where G1 must hold. A condensed core is an *application-sufficient*
  sketch, not the method the brief wants shipped.

A and D tie on G1–G5; **G6 differentiates** (a real goal we hold — the
tree must not carry a second installable skill), and D passes it where A
fails. **One survivor: D.** Held tentatively: a future "prefer the live
`use-igcs` skill when present, fall back to the vendored copy" enhancement
could give B's zero-staleness on machines that have it, as a graceful
degradation that still satisfies G4 (it does not *depend* on the external
path). Not built now — D first.

## What D is, concretely

- **`igc-method.md`** (skill root) — the full method, vendored from
  `use-igcs/SKILL.md` with the skill frontmatter stripped (so it is a
  reference doc, not a nested skill) and one pointer retargeted
  (`references/cf-concepts.md` → `igc-concepts.md`). Byte-faithful to
  upstream otherwise.
- **`igc-concepts.md`** (skill root) — `cf-concepts.md` verbatim, the
  conceptual grounding. Vendored for the same reason.
- **`SKILL.md`** — the *instruction* at the points of judgement (see
  below), not a condensed restate of the method (that lives in the
  reference, single-source).

## Staleness story (G2, satisfied)

Vendored copies can drift from upstream. **Breakpoint:** staleness is
acceptable up to a change in the method's *application rules* — the matrix
shape, the ✔/✘/? semantics, breakpoint conversion, the decisive-error
definition — all stable Critical-Fallibilism theory that has not moved.
Cosmetic edits upstream do not cross the breakpoint. **Detection:** each
vendored file carries an upstream-provenance blockquote with the source
path and the sha256 it was synced from
(`f58310b6…` for the method, `313dfabd…` for the concepts, both
2026-07-17). The docs-freshness maintenance rotation (selection step 4,
already loop work) compares that sha against the upstream file; a changed
application-rule sha is the breakpoint firing, and the rotation re-syncs
and bumps the recorded sha. So drift is *detected*, not silent — and on a
foreign install where the upstream path does not exist, the vendored copy
is the source of truth and there is nothing to drift against.

A byte-compare `lint.py` check was considered and **rejected as
non-portable**: the upstream path (`~/.llm-general/skills/use-igcs/`) is
specific to this self-hosted machine, so the check would be a no-op on
every other install — a check that matches nothing anywhere but here is a
check that passes forever everywhere else, the hollow-check failure mode.
Detection rests on the recorded sha + the existing docs-freshness rotation
instead.

## SKILL.md placement (instruction at the judgement, not a preamble)

Four real judgement sites; the method is introduced once in Guardrails and
referenced from the other three:

1. **Task selection** (selection step 2) — "Multiple ideas … then pick
   with IGC (see Guardrails) — not by feel." Replaces the old vague "pick
   the best", which was the judgement happening by feel.
2. **Dispatch / lane briefs** (Subagents → Dreamers) — a dreamer that must
   choose between rival options is told to use IGC and handed
   `<skill-dir>/igc-method.md` in its brief, because a lane does **not**
   inherit this file's Guardrails. Highest leverage — most choosing now
   happens in lanes.
3. **Review artifacts** (Durable state → `.dreamwork/review/`) — when the
   ruling is a choice between options, the options *are* an IGC matrix
   (decisive error under each ✘, no score column). This is what makes a
   choice-ruling answerable, and unblocks #445.
4. **Guardrails** — the single source: "Judgement between rivals uses IGC",
   with the method pointer, the buy (a decisive error refutes regardless
   of other attractiveness; scoring hides that), and the cost (a matrix on
   a trivial choice is waste — scale to the decision; skip non-rivals),
   plus the zero/two-survivor rules.

Nothing duplicated was cut: there was no existing choosing/evaluating prose
to retire — "pick the best" was *sharpened* to "pick with IGC" rather than
duplicated.

## Downstream effect — ud-dreamtask

`doc-map.md` records that `../ud-dreamtask/SKILL.md` inherits this skill's
**Guardrails** section by reference, so the new "Judgement between rivals
uses IGC" guardrail propagates there automatically — and with it the
obligation. But the guardrail points the loop at `<skill-dir>/igc-method.md`,
and `<skill-dir>` resolves to ud-dreamtask's own directory there, which does
not carry the vendored files. So in ud-dreamtask the obligation now fires
but the method is one pointer-resolution away from unreachable. This is a
follow-up, not a blocker for #447: either ud-dreamtask bundles the same two
files (the symlink-install model makes that a copy or a shared symlink), or
its pointer is resolved per-skill. Flagged for the coordinator; this worktree
owns only the ud-dreamwork tree.

## Lint check — declined (section 3 of the brief)

Considered shape: a review artifact or brief that presents options must
carry an IGC-shaped table. **Declined, for four reasons:**

1. **The target is semantic, not structural.** "Presents options" is a
   judgement lint cannot make reliably — an options comparison can be pure
   prose with no table, and a checkmark table need not be options. A check
   that cannot identify its target either matches nothing (silent pass
   forever — the hollow-check failure) or matches the wrong things.
2. **It would restate the prose it reads.** Per #444 (which refused and was
   right): the rule "options presentations carry an IGC matrix" is exactly
   the SKILL.md review-artifact clause. Enforcement belongs in SKILL.md
   (behaviour, fires unprompted) and the review-authoring guidance, not a
   structural lint pass that paraphrases them.
3. **The precondition inherits the same unreliability.** Asserting "≥1
   artifact presents options" is itself the fuzzy judgement, so the
   precondition assertion is not trustworthy.
4. **The richest targets are not mine to red-proof.** `.dreamwork/review/*`
   is held by a live lane; a check I cannot red-proof against the real
   artifacts is a check born unverified, and this is the first dogfood so
   almost nothing matches the pattern today — a dormant check is a hollow
   check.

Enforcement is the SKILL.md clauses + the vendored method + the
coordinator's existing review of review artifacts. If a structural signal
becomes reliable later (e.g. a `<data-igc>` marker authors opt into), a
check can red-proof against *that* — not against "presents options".

## Commit trailer — `Feature:`

`Feature:` ("a target gains something worth surfacing when it upgrades")
rather than `Migration:` (no `migrations/` file) or `Needs:` (no config or
consent). An existing dreamwork install, on upgrade, gains both the bundled
IGC reference docs and a new obligation to use IGC at judgement points —
coordinators and lanes should know on upgrade that choosing between rivals
is now IGC, not feel. The trailer carries the one-line summary for the
upgrade candidate list.
