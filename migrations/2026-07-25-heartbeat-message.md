# 2026-07-25 — heartbeat message micro-protocol

## What changed

The heartbeat message is no longer bare `dream tick`: it now carries the
micro-protocol (run the tick flow; keep the task list truthful; reflect)
plus a self-recovery clause naming the skill — monitor text survives
compaction while conversation context may not, so the tick string is
guaranteed in-band re-anchoring.

## How to apply

Running sessions: swap the monitor — `TaskStop` the old one, then arm the
new command from initialization step 5 (stop-then-arm; never two at
once). Fresh sessions pick it up automatically.
