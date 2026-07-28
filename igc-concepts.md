> **Bundled reference — vendored, not authored here.** The conceptual
> grounding behind IGC, copied from the `use-igcs` skill's
> `references/cf-concepts.md` so it travels with a dreamwork install.
> Upstream source:
> `~/.llm-general/skills/use-igcs/references/cf-concepts.md`, sha256
> `313dfabd522497b1e1ba91cbe8601614a082060d478cdd004d9e47bc00624813`
> (2026-07-17). Same staleness story as `igc-method.md`: this is stable
> theory (Popper/Goldratt/Rand via Critical Fallibilism); re-sync on the
> docs-freshness rotation only if upstream edits it, and bump the sha.

# CF concepts behind IGC

Conceptual grounding for the IGC method, drawn from Critical Fallibilism (Elliot Temple), which itself builds on Popper's Critical Rationalism, Goldratt's Theory of Constraints, and Rand's Objectivism. Read this when a decision hinges on *why* the binary approach is right, or when goals/criticisms are being contested.

## Decisive vs. indecisive errors

An **error** is a reason an idea fails at a goal. Only **decisive** errors refute: a decisive error means the idea genuinely fails the goal, so you can't accept both the idea and the criticism. An **indecisive** criticism — "this is a bit weaker", "I'd prefer otherwise" — is compatible with the idea succeeding, so it isn't really an error and shouldn't mark a cell ✘. Look specifically for decisive errors; ignore noise.

**Combining criticisms.** Several criticisms that each individually fail to refute can combine into one that does: a plan survives X alone and survives Y alone but fails if X and Y both occur. Form the larger criticism that explains why both happen and why together they cause failure — that combined criticism is decisive and refutes the idea.

## Binary goals and the case against degrees

A **binary goal** is well-defined enough that any outcome is unambiguously success or failure — like a well-formed proposition being true or false, never partially true. Saying a goal is *ambiguous*, or that you *don't know* an outcome, is not a third evaluation; it's a reason to clarify or to defer, not to mark partial success.

The main rival idea is **degrees of success** ("plan A succeeds more than plan B"). CF's argument that this collapses:

- A degrees-of-success goal is usually a vaguely-stated **maximization** goal in disguise. "Anything over $100 is fine, but $300 beats $200" really means *maximize money* — in which case any non-maximum is simply an error (a failure), so you're back to binary (best = success, not-best = failure).
- Any complete, correct formula for "amount of success" implies you should maximize it; if maximizing it doesn't give the best outcome, the formula is incomplete or wrong. Either way you land back on binary.
- And maximization itself is usually the wrong aim. Good goals want **enough** of a factor (with a margin of error), not the most. "Enough vs. not enough" is a binary distinction.

So instead of one rich score per idea, CF gives each idea **many simple binary evaluations** — one per goal. Nuance comes from having multiple evaluations, not from grading a single one. That's exactly what an IGC matrix records.

## Breakpoints and excess capacity

Treat the world as **small-digital** (a few discrete values) wherever possible. A **breakpoint** is a point on an analog spectrum where a *qualitative* change happens — where crossing it flips failure to success. Most quantitative changes don't cross any breakpoint, so they don't matter. A quantity-goal is really "be on the right side of the breakpoint" (binary), and the breakpoint is usually a "good enough" threshold, not a maximum.

**Excess capacity** (from Theory of Constraints): most factors are nowhere near their breakpoint — they already have plenty of slack — so optimizing them is wasted effort that doesn't change any outcome. Focus only on the few **constraints** (bottlenecks) that actually decide success. In matrix terms: don't add goals for excess-capacity factors; they bloat the grid and bury the real constraints. Give most factors at most a quick "is it good enough? yes → move on" pass.

People intuitively assume more of a good thing is linearly better. It usually isn't — value is typically flat across wide ranges with a few zones of rapid change at breakpoints. Assuming linearity is a common source of bad evaluations and decisions.

## Rivals and differentiation

**Rival** ideas make contradictory claims about the same issue, so you should accept at most one. To say idea A is *better* than rival B, you must name at least one **relevant, important** goal where A is non-refuted and B is refuted. "Better in general" with no such goal is not a real comparison. Non-rival (compatible) ideas don't need to be ranked against each other at all — you can keep both.

This is why a tie (multiple All-✔ ideas) is resolved by *finding a differentiating goal you actually hold*, never by scoring. If no real differentiating goal exists, the survivors are equivalent for your purpose and any is fine.

## Tentativeness

All conclusions are held **tentatively** (Popperian fallibilism): you can be confident and decisive while still expecting that a future idea or new evidence might reopen the question. Tentativeness is not indecision — it doesn't license endless hedging or refusing to choose. You pick the surviving idea and act, while staying open to correction. An IGC matrix is always reopenable: a new idea, a new goal, or a newly-found error can change the survivors.

## Why not scoring / weighting / pro-con

Learning and decision-making are **error-correction** processes, not accumulation of positive support. Infinitely many positive arguments for an idea are compatible with it still containing a fatal error, so positive justification can't establish an idea; a single decisive criticism can knock it out. Scoring systems and weighted pro/con lists are positive-justification machinery: they sum up goodness and let strengths paper over a disqualifying flaw. IGC instead asks the error-correcting question — *does a decisive error exist?* — for each goal, and keeps only ideas with no known errors anywhere that matters.

## Sources

- Introduction to Critical Fallibilism — https://criticalfallibilism.com/introduction-to-critical-fallibilism/
- CF Terminology and Partial Truth — https://criticalfallibilism.com/critical-fallibilism-terminology-and-partial-truth/
- Question-Based CF Epistemology Outline — https://criticalfallibilism.com/question-based-critical-fallibilism-epistemology-outline/
