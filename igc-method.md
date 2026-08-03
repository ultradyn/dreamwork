> **Bundled reference — vendored, not authored here.** This is the IGC
> method, copied from the `use-igcs` skill so a dreamwork install gets it
> without a separate dependency (a machine without `use-igcs` installed
> still has the full method). Upstream source:
> `~/.llm-general/skills/use-igcs/SKILL.md`, sha256
> `f58310b61416069d6d6ae5dd014a45791b6bd689c15464c713bbfcf277c91c80`
> (2026-07-17). **Staleness story:** the core — the matrix, ✔/✘/?, the
> All rollup, decisive errors, breakpoint conversion — is stable, so a
> drifted snapshot is low-risk; re-sync this file during the docs-freshness
> maintenance rotation when the upstream *application rules* change (not on
> any edit), and bump the sha above. Depth on *why* binary evaluation beats
> scoring/weighting lives in `igc-concepts.md` (same upstream skill). The
> dreamwork loop reaches for this at every judgement between rivals — see
> the "Judgement between rivals uses IGC" guardrail in `SKILL.md`.

# IGC — Idea-Goal-Context evaluation

An **IGC** is an (Idea, Goal, Context) triple. The Critical Fallibilism (CF) move is to stop asking *"how good is each option?"* and instead ask, for each idea and each goal, the binary question: **is there a known decisive error, or not?** An idea you'd choose is one that is non-refuted on *all* the goals that matter, in this context.

This beats scoring/weighting/pro-con lists because those hide errors behind a number: an option can rack up points elsewhere while quietly failing a goal that should rule it out. A single decisive error refutes an idea no matter how attractive it looks otherwise. So we surface errors instead of averaging them away, and we look for the *one* option that survives — or improve the problem framing until one does.

Use this skill proactively whenever the user is weighing options, comparing alternatives, or deciding — not only when they say "IGC".

## The matrix

Ideas down the left, goals across the top (label them `G1, G2, …` and put the full text in a legend so the table stays narrow). Each cell:

- **✔** — non-refuted for that goal: no known decisive error.
- **✘** — refuted: there *is* a known decisive error (a reason this idea fails this goal in this context).
- **?** — not yet evaluated, or genuinely unknown. A `?` is a TODO, not a score.

Add an **All** column (just right of the ideas) that rolls up each row: **✘ if any cell is ✘; else ? if any cell is ?; else ✔**. The All column is the idea's overall status — only an All-✔ idea is a viable choice.

Symbols are swappable for the environment (e.g. `[+]/[-]/[?]` or `Y/N/?` in plain terminals).

## The flow

Run these as a loop, not a one-shot. Most of the work is in framing the problem well; the matrix just records the judgements.

**1. Fix the context.** State the situation explicitly — it's the C in IGC. The same idea can pass in one context and fail in another, so naming it prevents arguing past each other. Usually it's the user's current situation; sometimes a predicted future one, or someone else's (when advising them).

**2. Set binary goals.** Each goal must have an unambiguous pass/fail — *whatever happens, there's a fact of the matter about success or failure.* Vague goals ("a good house", "fast enough") can't be evaluated; sharpen them until they can. Two traps to watch:
   - **Disguised maximization.** "More is better" goals ("fastest", "cheapest") aren't binary. Convert them to a *breakpoint*: the threshold of *enough* (with margin), e.g. "read latency ≤ a few ms", not "lowest latency". Beyond enough is usually excess capacity that doesn't matter.
   - **Non-decisive factors.** Most factors already have excess capacity and shouldn't be goals at all — listing them bloats the matrix and dilutes the real constraints. Keep the few goals that can actually refute an idea.

**3. Generate ideas.** Brainstorm candidate solutions — the user's, plus other plausible ones they may not have raised. Ideas that make contradictory claims about the same issue are *rivals*; you'll pick at most one. Don't pre-filter to the "obvious" answer; a wider field is what makes the matrix earn its keep.

**4. Evaluate each cell decisively.** For each (idea, goal) in context, ask only: *is there a decisive error?* A decisive error is a reason the idea actually fails the goal — not merely "it's a bit weaker here." Indecisive quibbles compatible with success are not errors; don't mark ✘ for them. If several individually-survivable issues only fail *in combination* (works despite X, works despite Y, fails if X and Y), that combination is one decisive error — record it as such. Mark unknowns `?` and treat them as work to resolve.

**5. Read the survivors (the All column).** This is the decision:
   - **Exactly one All-✔ idea** → that's the choice (held tentatively — see references). Done.
   - **Zero** → don't pick a refuted option. Either brainstorm new ideas, or revise the problem: maybe a goal is wrong, too strict, or not actually decisive (drop or loosen it), or the context needs fixing. Go back to step 2 or 3.
   - **More than one** → they're tied *on the goals you've listed*. Don't break the tie by scoring. Either they're genuinely equivalent for your purpose (pick either, or they may be compatible — keep both), **or** you haven't found the differentiating goal yet: identify a goal you *actually* hold that one passes and another fails, and add it. The differentiating goal must be real and relevant — inventing one to justify a pre-chosen answer defeats the method.
   - Any **?** in a row you care about → resolve it before relying on that row.

**6. Show your work.** A bare ✘ is just an assertion. Beneath the table, briefly state the decisive error behind each ✘ (and each contested ✔). The errors *are* the reasoning; the grid is just the index.

**7. Discharge every deferral before you record the decision.** If a ✔ or ✘ rests on something being done later — "the fuller fix is filed as a follow-up", "the migration comes separately" — then **file it first, get its id, and cite the id in the write-up.** A deferral is load-bearing whenever it is what made the smaller option survive: the scoring depended on it, so an unrecorded one silently converts *do it later* into *do not do it*, and every later reader sees a closed decision rather than an open debt. Measured case (`#1049`, 2026-08-04): a round chose honest wording over a stable question id "filed as a follow-up", the comment cited a task id that belonged to an unrelated, already-landed task, and no such task ever existed. The wording fix was genuinely the right interim — but the comparison that selected it was, retroactively, resting on a promise nobody kept. Cite a real id or say plainly that nothing is planned.

Scale the effort to the decision: a quick 2–3 × 2–3 matrix for a small choice, a fuller pass with iteration for a big one. Hold conclusions tentatively — a better idea or a new error can always reopen the matrix.

## Worked example

Context: choosing where to keep web-session data for an app that runs on several nodes and already runs Postgres.

| Idea | All | G1 | G2 | G3 | G4 |
|------|:---:|:--:|:--:|:--:|:--:|
| Redis | ✘ | ✔ | ✔ | ✔ | ✘ |
| Postgres table | ✔ | ✔ | ✔ | ✔ | ✔ |
| In-memory map | ✘ | ✘ | ✘ | ✔ | ✔ |

- **G1** survives a process restart · **G2** shared across all app nodes · **G3** read latency ≤ a few ms (a *breakpoint* — "enough", not "fastest") · **G4** adds no new service to operate

Why the ✘s: in-memory loses data on restart (G1) and isn't shared across nodes (G2). With only G1–G3, Redis and Postgres both survived (two All-✔ → a tie). The tie was broken not by scoring but by adding **G4** — a constraint the team genuinely holds — which Redis fails (a new service to run) and Postgres passes (already running). One survivor: Postgres.

## Going deeper

For the conceptual grounding — decisive vs. indecisive errors, why binary goals beat degrees of success, breakpoints and excess capacity, rivals and differentiation, and tentativeness — read `igc-concepts.md`. Pull it in when a decision turns on *why* CF rejects scoring, or when goals/criticisms are contested.
