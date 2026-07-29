# Brief — #342 lane A: cursor-bounded read projection for the user-event journal

Lane: `wt/lane-342a` · one task · worktree only · model on record: llmp-glm-5-2.

## What you are building

The ONE genuinely-new journal surface the ruled #342 design names
(`.dreamwork/docs/plans/delivery-modes.md` — read it first; Q1–Q3 are RULED,
its §"How an agent consumes the cursor in batched mode" is your contract):

> the journal has no read API that returns the event rows between two
> ordinals. `cursor()`/`advance_cursor()` give the position and the
> integrity check; they do not return the rows. Delivery-modes needs a
> **cursor-bounded read projection** — a function returning the
> `receipt.created` events (and their receipts' route +
> `exact_payload_bytes`) in `(cursor, head]`, ordered by ordinal.

## Acceptance criteria

1. A function on (or beside) `Journal` in `user_events/sqlite.py` — name it
   per the module's existing vocabulary — that takes a `consumer` and returns
   the events with ordinal in `(cursor(consumer).scanned_through_event_ordinal,
   head_ordinal()]`, ordered by ordinal, each carrying what a batched
   consumer needs: the envelope's route and exact payload bytes, the ordinal,
   and the event hash (so the caller can pass it to `advance_cursor`'s
   `expected`). Read-only; no writes, no cursor movement.
2. Semantics pinned by tests (`user_events/` test idiom, red-first):
   - empty range when cursor == head (returns nothing, does not error);
   - a fresh consumer (no cursor row) reads from the empty-chain origin;
   - order is ordinal order even when insertion interleaved consumers;
   - the function does NOT advance the cursor (read it twice, same rows);
   - it composes with `verify_chain` + `advance_cursor` exactly as the
     design's three acts describe — one test drives the full batched
     consume: read range → verify → advance → second read is empty.
3. Red-first: write the tests against the missing function, watch them fail,
   then implement. Red-proof at least one test by reverting a production
   line (e.g. the ordinal lower bound) and watching it fail; restore with
   `cp`. Assert runtime preconditions (a fixture with <2 events is a hollow
   range test — assert the range is non-trivial).
4. `python3 -m pytest user_events/ -q` green; `python3 lint.py --target .`
   no new warnings. Do not touch `watch.py` — lane B owns it. Do not touch
   `apply.py` — batched replay uses the adapters unchanged.

## Working agreement

- Small `#342` commits, `git commit --only <paths>` (`git add` new files
  first — `--only` misses untracked files).
- The ledger store is gitignored and absent in your worktree — `tasks.md`
  there is a one-line shim, not the ledger. Read the MAIN checkout's
  `.dreamwork/ledger.sqlite3` READ-ONLY (`file:...?mode=ro`, uri=True) if
  you need live context.
- Hand-off obligation (#398): if you stop before done, append your state to
  `.dreamwork/handoffs.md` in the MAIN checkout.
- Never `attn`, never `pkill -f`. Report: design notes, red runs, green
  runs, commit ids.
