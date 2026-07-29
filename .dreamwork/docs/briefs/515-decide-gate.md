# Brief — #515: gate `/decide` behind `emits_wake`

**Lane-owns:** `watch.py` (the `_handle_decide` function ONLY — do not touch
`track_question_updates` at ~12917; lane-509sig owns that region), `test_watch.py`
(new test class). Nothing else.

**Task (from the store, P1):** Gate `/decide` behind `emits_wake` so a review
decision rides the batched cursor like `/answer` and `/comment`.

**Source:** #514 wake-semantics audit, Finding F1 (`.dreamwork/docs/findings/514-wake-semantics-audit.md`).
`_handle_decide` (watch.py:~14264, the `log_event` at ~14321) journals a receipt
via the E3 cutover but emits its wake line with NO `emits_wake` guard — under
`delivery: batched` a `/decide` fires a wake every time, silently undoing batched
mode for review decisions. The four sibling content routes show the idiom:
`_handle_comment` at ~14260 calls `emits_wake("/comment", target)` and only then
`log_event`. `/decide` is the same content family and must follow the same shape.

**Acceptance (all required):**
1. `_handle_decide` emits its `log_event` line ONLY inside an
   `emits_wake("/decide", target)` guard, mirroring the `/comment` idiom.
2. The receipt commit path is UNCHANGED — a `/decide` under batched delivery
   still commits its receipt (the cursor carries it to the tick).
3. Red-first tests in `test_watch.py`:
   a. Under `delivery: batched` (write the posture file in a tmp target), a
      POSTed `/decide` writes NO line to `watch-events.log` AND the receipt IS
      in the journal (both halves asserted — a test that only checks the log
      is vacuous if the route 500s).
   b. Under `delivery: instant` (and under an ABSENT delivery axis — the
      default), the same POST writes exactly one `review-decision` line.
   c. Preconditions derived at runtime: the fixture's posture file actually
      carries the delivery axis; the route actually returned success.
4. Every added/changed check red-proved by injection + cp restore (never
   `git checkout`), and each red-proof names the PRODUCTION line it injected.
5. `git commit --only <paths>`; `.dreamwork/handoffs.md` Pending line with
   `· landed \`<sha>\` · … · by lane-515decide —` naming commits, reds, and
   the production line each red injected.

**Never:** touch the journal, `emits_wake`/`PREEMPT_KINDS` themselves,
`track_question_updates`, the dashboard UI, or `.dreamwork/` files other than
handoffs.md. Never run `just deploy`. Never bind ports 35110 or 39880-39899.

Model for the record: glm-5.2 (dispatch record — do not self-report a model).
