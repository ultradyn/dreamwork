# How the loop should ask him things — four options, measured

**Task:** #421 · **Input:** [`../research/2026-07-28-question-instruction-design.md`](../research/2026-07-28-question-instruction-design.md)
(`ccc @grok`, `bae566d`, `i-have-adhd` at sha `c784dcb`) · **Date:** 2026-07-28
**Status:** options only. Nothing here changes an instruction until he rules.

---

## What the measurement actually says, including where it contradicted me

His instruction was to research `i-have-adhd`, derive options, and put them to him. The research did
that and **refuted the premise the task was filed with**, which is why the options below are narrower
and different from what I would have proposed at 16:29.

| claim | verdict | evidence |
|---|---|---|
| *"our multi-part questions cost him"* | **refuted** | **19 of 56** entries carry ≥2 sub-decisions; **15 of 16** answered multi-sub entries closed **complete**, often same-day, often on a bare `rec`. Durable partials: **2** in the whole corpus (`#275` live, `#281` at fold) |
| *"`i-have-adhd` is an ask protocol to copy"* | **refuted** | it is an **output-density style** with a working-memory theory — lead with the action, cap lists at 5, one clarifying question, one end action. **It has no rule for silence, partial answers or late replies**, which is the one thing we need |
| *"29 entries don't ask anything"* | **wrong, and it was mine** | I wrote that at 16:47 from an ambiguous line in the research. They are **single-decision asks**, unlabelled — 27 of 34 contain a question mark, 23 carry a `Rec`, and several are literally titled *"one word: may I …"*. Good questions, not absent ones |
| *"length is the tax"* | **holds** | n=56: min **29**, p25 **112**, median **302**, p75 **517**, max **1121** words. Rises with sub-count: ~127 at 0 → ~738 at 4 → ~897 at 7 |

**The finding nobody was looking for, and it is the sharpest one.** The two entries whose *titles*
promise a one-word answer — *"one word: may I add `GIT_OPTIONAL_LOCKS=0`…"* and *"one word: may I run
`install.py --apply`?"* — are **300 and 448 words**, both **above the corpus median of 302**. So the
size of what we write is **weakly coupled to the size of what we are asking.** A one-word decision
gets a median-length essay. That, not the number of sub-questions, is the defect the corpus shows.

Two things the count conflates, which the options must keep apart:

- **options inside one decision** — `Rec H1` versus `H2`, two candidate layouts for one call;
- **separate decisions requested** — `S1`–`S4`, four independent rulings in one entry.

A fix that reduces one does not reduce the other, and the corpus's ten decision-label letters
(`Q R S G T M D B P H V N E A`) are used for both.

---

## Option A — the ask comes first, in its own line

Every entry opens with an **`Ask:`** line: the decision and the accepted answers, before any context.
Everything after it is optional reading. This is `i-have-adhd`'s lead-with-the-action rule, which is
the part of it that transfers.

- **Reduces:** time to find the decision. **Not** length.
- **Costs:** one convention; `lint` can check that the first body line carries the marker.
- **Evidence for:** the corpus's own short entries already do this informally, and they are the ones
  answered fastest.
- **Risk:** an `Ask:` line that restates the title adds a line and no information. The check should
  require it to name the accepted answers, not merely exist.

## Option B — a sub-decision that is not answered is recorded, and `lint` says so

Every sub-decision gets an explicit id. A fold that answers some and leaves others **must** record
the remainder, and `lint` **ERRORs** when a fold silently drops one.

- **Reduces:** the 2 durable partials, and the recurrence rather than the instances.
- **Costs:** a format rule in `file-formats.md` plus a check. Composes with `#419`'s
  blocked-on-human marker rather than duplicating it — same shape, one door over.
- **Evidence for:** `#275` has had Q3/Q5/Q6 unanswered since 2026-07-25 and **nothing in the loop
  notices**. `#281` Q6 was dropped at fold and only found by hand.
- **Risk:** it is the only option here with a real implementation cost, and it does nothing about
  length.
- **This is the one with an actual defect behind it.** The other three are improvements.

## Option C — a length budget, with the evidence in the artifact

Cap the entry at ~250 words — inside the p25–median band the corpus already occupies — and move
everything longer into the review artifact, which his standing rule already requires for every
ruling.

- **Reduces:** length directly. Median 302 → ≤250; max 1121 → capped.
- **Costs:** a `lint` warning on over-budget entries; more weight on artifacts being opened.
- **Risk, and it is the serious one:** an artifact he does not open makes the evidence **less**
  visible than a long entry does. Today's `#263` correction lived in the entry and he could read it
  without a click. A cap would have pushed it behind one.
- **Rec: as a soft target that `lint` reports, not a cap that refuses.**

## Option D — say what a valid answer looks like

Every question states the literal accepted answers: `rec`, `A`, `B`, `defer`, `no`.

- **Reduces:** the cost of answering, not of reading.
- **Costs:** nearly nothing.
- **Evidence for:** he answers with a bare `rec` repeatedly — including *"`rec` — all four"* on
  `#263`. **The fastest path already exists and we never advertise it.**
- **Risk:** a stated answer set that omits the option he actually wants is worse than none, so it must
  always admit a free-text answer explicitly.

## Rejected — one decision per entry

The obvious port from `i-have-adhd`'s one-clarifying-question rule, and **our own data kills it**: 15
of 16 answered multi-sub entries closed complete. It would multiply the count of items on his desk to
solve a problem occurring twice in 56 entries. **Recorded as rejected with its reason so it is not
re-proposed.**

---

## Recommendation

**A + B + D, and C as a reported soft target rather than a cap.** A and D are conventions costing a
line each and they attack the measured defect — the weak coupling between the size of the ask and the
size of the writing. B is the only one fixing a live defect and it composes with `#419`. C is left
soft because the failure mode of a hard cap (evidence behind a click) is worse than the failure mode
of a long entry (a long entry).

**What would change in practice:** `DREAMWORK.md` gains the `Ask:`-line and answer-set conventions;
`file-formats.md` gains the sub-decision id and remainder rule; `lint.py` gains one ERROR (dropped
remainder) and two WARNs (missing `Ask:` line, over-budget length). No change to `questions.md`'s
`## Open` / `## Answered` contract, so nothing existing reparses differently.

**What stays open regardless:** whether a *historical* entry gets retrofitted (rec: no — mark the
convention's start date and let the corpus age out), and whether the `Ask:` line should be a distinct
rendered element on `/questions` rather than plain text (a `watch.py` change, and a separate task).

---

--- SUMMARY ---

- **The research refuted the premise I filed the task with.** Multi-part questions are not the
  problem: 19 of 56 entries carry ≥2 sub-decisions and 15 of 16 answered ones closed complete, often
  same-day on a bare `rec`. Durable partials number **2** in the entire corpus.
- **`i-have-adhd` is an output-density style, not an ask protocol.** Lead with the action, cap lists
  at 5, one clarifying question. It has **no** rule for silence, partial answers or late replies —
  the one behaviour we actually need — so only its density half transfers.
- **The measured defect is a weak coupling between the size of the ask and the size of the writing.**
  Entry length: min 29, p25 112, median 302, p75 517, max 1121 words. The two entries whose titles
  promise a *one-word* answer are 300 and 448 words — both above the median.
- **A claim of mine was wrong and is corrected here:** the 34 zero-marker entries are single-decision
  asks, not non-asks. 27 contain a question mark and 23 carry a `Rec`.
- **Four options**, deliberately orthogonal: **A** the ask comes first with its accepted answers;
  **B** unanswered sub-decisions are recorded and `lint`-enforced; **C** a length budget with the
  evidence in the artifact; **D** state what a valid answer looks like.
- **Rejected with reasons: one decision per entry** — the obvious port, killed by our own completion
  data, recorded so it is not re-proposed.
- **Rec: A + B + D, with C soft.** B is the only one behind a live defect (`#275`'s Q3/Q5/Q6 unanswered
  since 2026-07-25 with nothing noticing) and it composes with `#419`. C stays soft because a hard cap
  pushes evidence behind a click, which is worse than a long entry.
