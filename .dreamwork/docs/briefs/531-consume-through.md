# Brief — #531 consume advances past events it never read (race window)

Ledger id: **#531** (bug). Filed 2026-07-30 after a live instance: the
#505 answer receipt (ord=43) committed to the journal BETWEEN the
coordinator's `pending` read and its `consume` in the same tick; consume
advanced past it unread (recovered by hand via `show`).

## The defect

`dev/journal_consume.py consume` is read-then-advance, but the read it
verifies against is a FRESH read at consume time, not the read the
coordinator actually processed. Any event landing between the
coordinator's `pending` (t0) and `consume` (t1) is inside the advanced
range without ever having been listed — a silent skip with a green exit,
the exact failure the never-consume-blind rule exists for.

## The fix

`consume --through <ordinal>`: advance at most through the ordinal the
`pending` read reported as head (events carry `event_ordinal`; `pending`
already prints enough to know it — if it does not print the ordinal, add
it to the line). Without `--through`, consume keeps today's semantics
(advance to head) — the flag is the tight form the tick habit uses.
SKILL.md's drain habit gains one clause: the tick reads `pending`, notes
the head ordinal, and consumes `--through` that ordinal. (SKILL.md is
coordinator-owned — the lane implements the CLI + tests and NAMES the
SKILL.md line for the coordinator; it does not edit SKILL.md.)

Semantics on the edges, state each in the handoff:
- `--through` below the cursor: refuse (EX_USAGE 64) — a stale ordinal
  must not rewind or no-op silently.
- `--through` above head: refuse (EX_USAGE 64) — cannot advance past
  what exists.
- Events beyond `--through` stay pending and are listed by the next
  tick's `pending` — that is the point.
- The #526 proof act (reconcile per drained receipt) applies only to
  receipts INSIDE the advanced range.

## Proof obligations

- Red-first: a test that seeds events, reads pending (capturing head
  ordinal h), seeds one MORE event, then `consume --through h` — assert
  the cursor stopped at h and the late event is still pending. Born-red
  against the production line you name (e.g. the advance ignoring
  `--through`).
- Edge tests for both refusals.
- The existing 13 journal_consume tests stay green (incl. the #526
  unregistered-route binding).

## Lane-owns

`dev/journal_consume.py` + `test_journal_consume.py` only. Do NOT touch
SKILL.md, watch.py, user_events/, or handoffs.md beyond your one literal
Pending line.

## Handoff

Literal Pending line in `.dreamwork/handoffs.md`
(`- **#531** · landed \`<sha>\` · … · by lane-531through — …`) with the
edge semantics chosen, the born-red evidence, and the SKILL.md line the
coordinator should add. `git commit --only <paths>`; NEVER attn, never
pkill -f.
