# 2026-07-25 — watch events log

## What changed

watch.py appends one-line user-action summaries to
`.dreamwork/watch-events.log` (gitignored ephemera): stamp, action, the
file to look at, next step. Init arms a Monitor tail on it where the tool
exists (dashboard answers wake the agent immediately); other harnesses
check its mtime each tick.

## How to apply

Add `.dreamwork/watch-events.log` to the target's .gitignore. Restart any
running watch.py; arm the tail monitor at next init (or now).
