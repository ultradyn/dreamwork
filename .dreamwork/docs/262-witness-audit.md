# #262 audit — does the accepted-but-unwitnessed path still exist?

**Verdict: CLOSED in production.** Measured 2026-08-01 on `e699d4f6` (master).
Both harms the entry names are closed; #262 should fold.

## Primary harm — accepted without durable witness

Commit `38ef4098` (E3 cutover, #263) closed it. On today's tree:

- `make_handler` (watch.py:4870) defaults `journal_shadow=True`; the only
  production caller (watch.py:6197) does not override it. The `journal_shadow=
  False` path is test-only (E2's baseline harness).
- `do_POST` (watch.py:5456) commits the receipt BEFORE dispatching the handler:
  `_journal_receive` → if `journal_result() is None` → 503 (no success). Only
  after a committed receipt does the handler run.
- All 12 write routes in `WRITE_ROUTE_HANDLERS` (watch.py:6077) terminate their
  success path in `_send_receipt` (watch.py:4997), which sends 503 if the
  receipt is absent. No handler calls `_send` or `send_response` for success.
- `receive()` (sqlite.py:619) only returns a `receipt_id` after a durable
  `COMMIT` under `synchronous=FULL`; any failure → ROLLBACK → raise → None →
  503.
- `log_submission` (watch.py:4741) is now a best-effort SHADOW written AFTER
  the receipt. Its `OSError` suppression (#199's property) no longer implies an
  unwitnessed acknowledgement — the receipt already committed.

The truncated-body path (Content-Length > MAX_BODY) takes the `else` branch
(no receipt) but returns 413, not a success status. Not an open path.

**E2/E3 tests cover this and are not hollow.** Red-proofed Direction 1:
removed the `COMMIT` in `receive()`'s insert path → E2 failed on `0 != 12`
(`receipt_count()` reads from a separate connection, proving durability not
just that `receive()` was called). Restored; `redproof.py check` clean.

Direction 2 (false-green): no construction found. The route list is derived
from the single dispatch table; E2 asserts both status (202) AND receipt
count; the companion `test_a_new_route_would_fail` guards route-list drift.
A handler calling `_send` (200) fails the status assertion; one calling
`send_response` directly fails by not being in the table.

## Secondary harm — multi-process receipt history splitting

**Also closed.** The brief's premise ("two same-target processes each hold
their own journal") was true in the submissions.log era but is false
post-journal. `_journal_path(target)` (watch.py:4655) resolves to one file
per TARGET (`.dreamwork/user-events.sqlite3`), opened WAL +
`synchronous=FULL` + `busy_timeout=5s`. Two processes serving the same
`--target` share the same SQLite database; `get_receipt()` opens a fresh
connection per call, so a receipt committed by process A is visible to
process B. `BEGIN IMMEDIATE` + busy_timeout serializes concurrent writers;
`client_action_id` dedup means two processes receiving the same UUID yield
one receipt.

No singleton guard prevents two processes on different ports, but they do
not split receipt history.
