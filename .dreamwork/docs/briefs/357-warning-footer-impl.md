# Brief — #357 implementation: the CLI warning footer (design fully settled)

Lane-owns: `dev/ledger.py`, `test_ledger_dispatch.py` (or a new
`test_ledger_warnings.py` — your call, say why), `.dreamwork/docs/plans/cli-warning-layer.md`
(the Q6 → ruled edit ONLY), `.dreamwork/handoffs.md` (append ONE `## Pending` line)

## The task

Implement the warning footer for `dev/ledger.py` exactly as the design
`.dreamwork/docs/plans/cli-warning-layer.md` specifies. **Read that doc in
full first — it is the spec, and both open forks are now RULED:**

- **Q5 (ruled 2026-07-30 03:11): the footer on EVERY verb** — read verbs
  (`counts`, `sweep`) included, not only state-change verbs.
- **Q6 (ruled 2026-07-30 03:52): the FULL warning line every call (I1)** — the
  terse `⚠ N warnings` hint is dropped. Read verbs carry the same full
  breakdown.
- **The throttle is REFUTED** by the IGC in that doc (§IGC) — do not build any
  suppression, skip-count, or recency logic. The footer is stateless.

Settled shape (the doc's, restated so the brief stands alone):

- One function in `dev/ledger.py`, called by every verb at exit, emitting the
  footer to **stderr** (stdout stays machine-clean — verify which stream the
  doc names and follow it).
- Content: his five counts + incomplete-data (see the doc's worked example:
  open tasks · unanswered questions · untyped · missing origin · **unconsumed
  journal receipts** — `head_ordinal − coordinator_cursor.scanned_through`,
  read from the same store the verb just touched).
- **WARN, never ERROR** — the footer never changes an exit code, never fails
  a verb.
- **Quiet rules**: a zero count is absent from the line; a fully clean state
  prints nothing extra. The footer must not make a clean `counts` noisy.
- Stateless: no state file, no memory between invocations.

## Discipline (the repo's law — CLAUDE.md)

- Red-first: write the failing test(s) before the implementation. Every check
  you add must be **red-proved**: name the production line, inject the
  breakage, watch the check fail, restore byte-identical with `cp` (never
  `git checkout`). Report each red-proof.
- Assert in the check the precondition the check depends on (derive both
  sides of any fixture gap at runtime — no literal tuned to today's fixture).
- No hand-built fixture that bypasses the production function deciding the
  thing under test (the born-hollow trap; the doc and CLAUDE.md name it).
- The journal-count clause must be tested against a REAL scratch journal
  seeded through the production `receive()` path (`user_events.sqlite`),
  never a mocked cursor.

## Same-commit doc edit

In `.dreamwork/docs/plans/cli-warning-layer.md`, mark **Q6 ruled (full line,
I1, his 03:52 `rec`)** the way Q5's ruling is already recorded there. No
other doc changes; doc-map needs no row (the doc is already mapped).

## Acceptance criteria

- Every `dev/ledger.py` verb (`counts`, `sweep`, `file`, `note`, `fold`)
  emits the full footer at exit, on the correct stream, exit codes unchanged.
- Zero-count absence and clean-tree silence are each pinned by a test with a
  derived precondition.
- The unconsumed-receipt count is derived from the real cursor arithmetic and
  pinned against a scratch journal (seed 3, advance 1, expect 2 — or similar;
  the numbers derived at runtime).
- `python3 -m pytest -q` green except the 4 KNOWN pre-existing
  `test_tasks_migrate*` live-ledger failures (#511, another lane owns them —
  do not touch, do not "fix", do not report as yours).
- `python3 lint.py` clean.
- Branch `lane-357impl` off master; `git commit --only <paths>` (new files
  `git add` first). Append ONE `## Pending` line to `.dreamwork/handoffs.md`
  (append-only, never rewrite; the literal path is `.dreamwork/handoffs.md`).

## Report back

The verb/stream shape implemented, each red-proof (production line → failing
check → restore), the quiet-rule pins, the pytest summary line, and any place
the design doc proved wrong against the real code (report, don't silently
deviate).
