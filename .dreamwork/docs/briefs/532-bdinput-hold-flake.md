# Brief — #532 bdinput (d) hold-repeat timing flake

Ledger id: **#532** (bug). Filed during the #523/#524 gate, 2026-07-30 08:45.

## The defect

`dev/capture/bdinput.mjs` section `(d)` holds the burndown limit `[+]`
stepper for 1100ms of wall-clock time and asserts the value rises by ≥3
(repeat engages at ~400ms, then ~80ms per repeat, so ~8 increments are
expected). Under CPU contention headless Chromium throttles timers: in
the #523/#524 gate the check delivered delta<3 in 1 of 3 runs (22:37 UTC,
port 39896) while the feature itself was correct — 30 other checks green,
visual verdict PASS. This is the **#507 readiness/flake class**: the
measurement is racing the mechanism, and the fix belongs to the harness,
never to a loosened assertion.

## The fix

Make the hold deterministic. First choice: Playwright's `page.clock`
(`clock.install()` before the hold, `clock.tick(ms)` to drive time) so the
repeat interval fires exactly as often as the production constants say it
should — this also lets the assertion stay at ≥3 or even tighten. If
`page.clock` fights the guard's other needs (real network waits,
screenshots), the fallback is a generous wall-clock budget (longer hold,
more samples) with the threshold UNCHANGED. Zero assertion loosening is
the hard rule either way.

Section `(e)` (hold across a tick/re-render) likely shares the timing
dependency — audit it and apply the same treatment if so.

## Proof obligations

- 10 consecutive PASS runs, at least 3 of them under load (e.g.
  `stress -c` or while another guard runs), on one shared fixture server
  if the guard takes (OUT, PORT).
- Red-proof still fires: sabotage the hold-to-repeat interval in watch.py
  (the production line the check binds) → `(d)`/`(e)` FAIL → restore
  byte-identical with `cp`. Name the production line in the handoff.
- The `(c2)` typed-clamp section added at the #523 gate (defense-in-depth
  disjunction) must stay green and untouched.

## Lane-owns

`dev/capture/bdinput.mjs` only. Do NOT touch watch.py except transiently
for the red-proof (cp restore). Do NOT touch other guards.

## Handoff

Append a literal Pending line to `.dreamwork/handoffs.md` in the
established grammar (`- **#532** · landed \`<sha>\` · … · by
<claimer> —`), including: the fix chosen and why, the 10-run evidence,
the red-proof result, and the load conditions.
