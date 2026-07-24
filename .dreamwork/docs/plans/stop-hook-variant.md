# Stop-hook wake variant — reference design (unimplemented)

For harnesses that have hooks but no Monitor tool. The Monitor heartbeat
remains the default; see SKILL.md "Wake mechanisms".

## Mechanism

Stop hook fires when the agent finishes a turn. The hook script:

1. Reads a state file (e.g. `.dreamwork/.stop-hook-state`): consecutive
   auto-continues counter + last-fire timestamp.
2. **Loop guard**: if counter ≥ N (suggest 3–5) or a `pause` marker file
   exists → exit 0 (allow stop, reset counter). There is no built-in loop
   prevention — the guard is entirely the hook author's job.
3. Sleeps ~285 s (must stay under the hook timeout; default 600 s,
   configurable per-hook).
4. Increments the counter, then returns
   `{"decision":"block","reason":"dream tick"}` (or exit code 2) — the
   agent continues with the reason as its next instruction.

The coordinator resets the counter whenever a real user message arrives
(any human input = engagement; auto-continue budget refreshes).

## Caveats (why it's a fallback)

- User input during the sleep window is not well-defined behavior — the
  session may appear locked while the hook sleeps.
- The reason string is a blunt instrument: every wake looks identical,
  unlike Monitor events which are distinguishable notifications.
- Cost: each blocked stop is a full turn; the guard counter is the only
  brake if the agent has nothing to do (pair with "idle quietly" — an
  idle wake must still count toward the guard).

## `pause` / `resume` mapping

`pause` = create the marker file (hook then allows stops); `resume` =
remove it. Mirrors TaskStop/re-arm in the Monitor mechanism.
