# 2026-07-25 — async question answering via watch

## What changed

watch.py gained its single write exception (human-authorized): POST
/answer appends an "**Answer (via watch, <stamp>):**" bullet under the
matching open question in questions.md. The dashboard shows an answer box
per open question. Loop side: each tick, if questions.md changed, fold new
"(via watch)" answers first — act, then move the entry to Answered.

## How to apply

Nothing structural. Restart any running watch.py to pick up the endpoint
and UI; the tick-flow folding rule applies from the next tick.
