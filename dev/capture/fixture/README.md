# guard fixture

A frozen dreamwork target. `just guards` copies this to a temp dir and
serves *that*, so every browser guard runs against content it controls.

This exists because a guard that reads the live `.dreamwork/questions.md`
is testing the content: `qacard` asserts all three question states are
rendered, and went red whenever the loop happened to have folded the last
awaiting-fold entry — a red with no code change behind it, which is worse
than no guard at all because it trains you to ignore the light.

So this file set holds, deliberately and permanently, one question in each
of the three states, plus every input shape the parser and the prose
renderer are supposed to survive: a hard-wrapped title, a hard-wrapped
sub-bullet, a note from the human and one from the loop, a legacy tag of
each kind, inline emphasis, a nested bullet, a code fence, a backticked
path to a review artifact (which is what gives the review dock and the
route-change guards something to travel to), and — for #506's body-link
pips — a known-internal path (`.dreamwork/lessons.md`, which exists), an
unknown path (`nosuch/vanished.md`, which does not), and an external
`github.com/…` reference so the guard can derive both link kinds at runtime
rather than assume them.

Guards run against a COPY, so the ones that POST /answer and /comment can
mutate freely and the next run still starts here. Add to this file rather
than reaching for live content when a guard needs a new shape.

**A VALUE'S LENGTH IS AN INPUT SHAPE (#595).** `.dreamwork/skill-version` says
`2026-07-25-04-fixture-unbounded-version-name-worst-case.md`, and the ugliness
is the point — it is deliberately as long as a real migration filename, because
the head's `version` crumb renders whatever is in that file and the page's
"never scrolls sideways" contract is a claim about ANY length. It used to say
`2026-07-25-fixture`. Eighteen characters fit a 390px crumb row whether or not
they can wrap, so `hfit` passed for months while the live dashboard scrolled
28px sideways. `hfit` now FAILS if this value drops under 40 characters — if
that check reds, lengthen the value, do not lower the threshold. Frozen content
protects a guard from the loop's churn; it does not protect it from a value the
fixture author picked small.
