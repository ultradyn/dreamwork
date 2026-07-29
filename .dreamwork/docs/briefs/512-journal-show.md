# Brief — #512: `journal_consume show <receipt-id>` — a full-payload read verb so batched delivery is never lossy

Lane-owns: `dev/journal_consume.py`, `test_journal_consume.py`, `.dreamwork/handoffs.md` (append ONE `## Pending` line)

## The defect (lived, not hypothetical)

The coordinator dogfooded batched delivery and ran `consume` blind — no prior
`pending` read — discarding the content of two events. One of them was a
**human instruction** (recovered later by a hand-written sqlite query against
the events table: an `add-idea` from Max asking for a posture reminder at
every tick — now filed as #513). The tool made the mistake easy:

- `pending` prints an **80-char preview** (`_PREVIEW_LIMIT = 80` in
  `dev/journal_consume.py`) — enough to see a kind, not enough to act on.
- `consume` prints receipt ids only and advances the cursor.
- There is **no read verb for the full payload**. Once an event is consumed,
  the only way back to its content is SQL by hand — which failed twice on
  schema guesses before succeeding.

## What to build

Add a third subcommand to `dev/journal_consume.py`:

  show <receipt-id>   READ-ONLY. Prints the FULL payload of one receipt,
                      decoded, plus a small metadata header. Never advances
                      the cursor. Works for ALREADY-CONSUMED receipts too
                      (consumption only moves the cursor; the receipt and
                      its event rows persist) — recovering a blindly-consumed
                      event is precisely the use case.

Design constraints:

- **Use the existing public API.** `Journal.get_receipt(receipt_id)` in
  `user_events/sqlite.py` (line ~782) returns a dict including
  `exact_payload_bytes` — the original request body. That is the content to
  print. Do NOT add a new query to `user_events/`; do NOT touch any
  `user_events/` file. If you believe `get_receipt` is the wrong seam,
  stop and report why instead.
- **Unknown receipt id**: print a clear one-line error to stderr, exit
  EX_USAGE (64). Absent journal: same "not found" path, never create the db
  (read-only, no filesystem side effect — the #501 discipline).
- **Output shape**: a header block (receipt_id, state, revision,
  client_action_id, request_digest — the fields `get_receipt` returns, one
  per line, `key: value`) then a blank line, then the payload decoded as
  UTF-8 verbatim (this output is meant for an agent to READ, so multi-line
  is correct here — unlike the line-oriented `pending`); non-UTF-8 payloads
  print `<N-byte binary payload>` and nothing else. No length cap.
- The module docstring's USAGE block gains the `show` line, and the
  docstring's opening prose gains one sentence naming the lossy-tick
  failure this verb closes (the tool's own history is documentation).

## Tests (the repo's verification law applies — read CLAUDE.md first)

Extend `test_journal_consume.py`. Required, minimum:

1. `show` on a receipt seeded via the PRODUCTION write path
   (`Journal.receive`, as the existing tests seed) prints the full payload
   bytes verbatim — including a payload longer than 80 chars, with the
   length derived at runtime (e.g. `payload = "x" * 200` … assert the whole
   thing appears in the output; do not hardcode an 81-char fixture that a
   future preview-limit change would silently satisfy).
2. `show` on a receipt AFTER `consume` advanced the cursor past it still
   prints the payload (the already-consumed recovery case — assert the
   cursor moved first via `journal.cursor(CONSUMER)` so the test's meaning
   doesn't rot).
3. Unknown receipt id → exit 64, message on stderr, stdout empty.
4. Absent journal path → same as unknown, and assert the db file was NOT
   created.
5. Multi-line UTF-8 payload survives verbatim (this verb is the exception
   to the collapse-newlines rule; say so in the test name or docstring).

**Red-proof every new test**: name the production line that must change for
the test to fail, change it, watch it fail, restore byte-identical with
`cp`. Name each red line in your report. A green red-run is a finding,
never a relief. If you patch/fake anything, name the production line that
would have to change for the test to fail — if you can't name one, the
test is hollow, rewrite it.

## Constraints

- Lane branch off master: `lane-512show`. Commit with
  `git commit --only <paths>` (new files need `git add` first — but you
  should have no new files; extend the two owned ones).
- After your change: `python3 -m pytest -q test_journal_consume.py` all
  green, `python3 -m pytest -q` no NEW failures vs master (master is
  currently green except any in-flight-lane noise — record your baseline
  first), `python3 lint.py` clean.
- Do NOT change `pending`/`consume` behavior, `_PREVIEW_LIMIT`, or
  `_format_event` — #512 is the show verb only. (A "pending --full" flag
  was considered and rejected: one read verb, explicit by id.)
- Do NOT touch `.dreamwork/` state files other than the handoffs append.
- Append ONE `## Pending` line to `.dreamwork/handoffs.md` (append-only;
  never rewrite; the literal path is `.dreamwork/handoffs.md`).

## Report back

The tests added (names), the red-proof per test (production line named,
what failed, what restore showed), the `pytest -q` summary line, and one
sentence on whether `get_receipt` was the right seam or you hit a gap.
