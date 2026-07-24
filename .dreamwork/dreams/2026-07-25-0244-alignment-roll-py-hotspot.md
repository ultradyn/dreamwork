# Dream — alignment pass 1: roll.py is a hotspot, and verification is over-narrowed

Fresh-eyes alignment review (does the implementation serve the stated goals
and philosophy?). Findings went to the coordinator as a list; two things are
worth keeping beyond the list.

## roll.py is where the loop over-invested

Three of my five material findings land on one 138-line file: it treats
goal-alignment as just-another-weighted-item (contradicting "goal alignment
first"), it's gold-plated (a `Style` class + ANSI + a colored gate/roll
breakdown for an advisory, never-binding die that runs in an *unattended*
loop where nobody watches the TTY), and it has no committed test despite
shipping `--seed` for exactly that and despite the skill preaching verified
increments. Two dedicated commits, the second adding "rich debug output …
ANSI".

The meta-signal: this is the "runaway / make-work" tail (P5) showing up in
miniature — the loop polishing a shiny sub-feature while primary paths
(Monitor dogfooding, compaction/resume) stay unexercised and other principles
stay under-operationalized. Not runaway, but the same gradient. Worth watching
whether the loop keeps returning to decorate finished sub-features instead of
consolidating.

## "Run the tests / green baseline" is written for code-with-tests only

G1 is "leave an agent dreaming on *a project*" — any project. But
initialization #9 ("run the test suite", "red baseline") and the loop's
"Task just finished" bullet hardcode *tests*, while reflection.md #3 correctly
generalizes ("tests/lint, **or its stated routine**"). This very target proves
the gap: its own DREAMWORK.md says the test suite *is* a coherence re-read, so
init #9 is literally inapplicable here. The generalization already exists in
one place; the other two spots just need to match it.

## Concrete contradiction demo

`python3 roll.py --no-backlog --seed 7 --quiet` → `maintenance: self-review`
(not goal-alignment). So on an empty backlog the roll can skip "goal alignment
first" that step 4 promises.
