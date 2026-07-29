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
