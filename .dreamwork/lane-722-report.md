# lane-722drain — report

**Verdict: DONE.** Both defects fixed, #712's guard intact at full strength,
27 → 29 tests, lint clean, redproof check clean, rebased onto master
(`0d7cc5be6025`) with no conflicts.

## What changed and why

Two defects, both rooted in `pending` computing its reported head over
`receipt.created` only while the cursor advances over every ordinal.

**Defect 1 — the livelock (#722).** `pending`'s marker recorded
`events[-1].ordinal` (the listing head); the cursor advances over all kinds.
When the journal head was a `receipt.transition`, pending reported head 116
while the head was 117, so `consume --through 117` was refused by #712's guard
(correctly — 117 was never listed) and `--through 116` did not move. **Fix:**
`cmd_pending` now records `j.head_ordinal()` (the TRUE head) while its listing
stays `receipt.created`-only. `cmd_consume`'s advance target is the true head
(or `--through`), and when that ordinal is a non-receipt event it derives the
expected hash from `verify_chain` (the public "don't trust stored hash" path)
rather than the projection.

**Defect 2 — the silence (#702/#136).** With only a transition above the
cursor, `pending` printed nothing on either stream. **Fix:** the coverage line
now fires whenever the cursor is below the head, and names the non-listed
ordinals with their kinds (`not listed: ord=2 receipt.transition`), so
"nothing needs you" (cursor at head) and "something is hiding" (an unlisted
kind above the cursor) render differently.

**Scope held.** Only `dev/journal_consume.py` and `test_journal_consume.py`
touched. No change to the guard logic, no `--force`, no transition-skipping
special-case. No change to `status_sync.py`, `dev/ledger.py`, or the journal
schema. Added one import (`sqlite3`) for the non-listed-events read.

## Design choice — argued, not defaulted

**Chosen (Option A): pending reports the true journal head; its listing stays
receipt.created-only.**

The cursor is a position in the single append-only event chain —
`advance_cursor(scanned_through=N)` advances over ordinal N regardless of its
event_kind, and `verify_chain` walks every row. A `receipt.transition` at the
head has a `prev_hash`/`event_hash` like any other row; the cursor sitting below
it is a genuine "unconsumed prefix" state.

**This does not weaken #712's guard.** The guard's contract —
`--through` must equal the head of the read on record — is unchanged; only the
VALUE the marker carries widens from the listing head to the true head. The
guard still refuses above, below, absent, and mismatched markers at full
strength. The guard's PURPOSE (don't advance past an unread `receipt.created`
instruction — the #513 steer) is preserved: if the ordinal at `through` is a
`receipt.created`, pending LISTED it; if it is a transition, there is no
envelope to read — `events_since_cursor` filters it out and the proof loop
never routes it.

**Rival rejected (Option B): the cursor advances only over listable kinds.**
It fragments the cursor's meaning — `scanned_through_event_ordinal` would track
"highest receipt.created" rather than "position in the chain," breaking
`verify_chain`'s whole-chain rebuild and `advance_cursor`'s CAS contract. It
would leave the cursor permanently below the true head (a permanent false
"unconsumed" warning). And it requires touching `user_events/sqlite.py`
(explicitly out of scope). Option A makes every future non-listed kind
drainable by construction; Option B needs a patch per kind.

## Red-proof

### Direction 1 (inject the defect, watch the check go red on the discriminating message)

**Injection:** `dev/redproof.py begin dev/journal_consume.py`, then reverted
`head = j.head_ordinal()` to
`head = events[-1].ordinal if events else j.cursor(...).scanned_through_event_ordinal`
(the pre-fix listing-head computation).

**`test_consume_drains_transition_head_then_pending_quiet` went RED:**
```
AssertionError: consume --through 3 (the true head) must SUCCEED — the livelock
is that pending reported head 2 while the true head was 3, so #712's guard
refused the only drainable value and no legal --through existed; got exit 64
(err='consume: --through 3 advances past ordinals the last `pending` read
never listed (read reported head 2; uncovered ordinals [3]) ...')
```
The red message names the livelock mechanism AND proves #712's guard fired
correctly on its own terms (`read reported head 2; uncovered ordinals [3]`) —
the fix is on the other side, exactly as the brief required.

**`test_pending_reports_true_head_and_not_listed_when_head_is_transition` also
went RED:** `the marker must record the TRUE journal head 2 (not the listing
head 1) ... got 1`.

Restored via `dev/redproof.py restore`, verified byte-identical, both tests
green again.

### Direction 2 (construct a case where the drain works but is wrong)

**Candidate: a `receipt.created` interleaved after a transition.** Fixture:
ord1 receipt.created (instr A), ord2 transition, ord3 receipt.created (instr B),
ord4 receipt.created (instr C). The widened head is 4. Does the guard let a
consume claim an unread instruction?

**Result: the guard HOLDS.** Simulating the operator's `tail` (they hold only
the last receipt), `consume --through 3` (the second receipt, which they did
not see) is **refused**:
```
consume: --through 3 is BELOW the head of the read on record (4) — a bound
that did not come from that read came from an older or truncated view of it...
```
The widened head makes #712's below-the-read-head refusal *stronger*, not
weaker: the gap between the read head (4) and the bound (3) is larger, so the
truncation is more visible. The transition is reported (`not listed: ord=2
receipt.transition`) but never lets an unread receipt slip through. **No
false-green found** — the guard's whole purpose is preserved by construction.

## Verification

- `python3 -m pytest test_journal_consume.py` → **29 passed** (was 27; +2 new tests)
- `python3 lint.py` → **clean (6 warning(s))** — the 6 are the known lane-workstore ledger WARNs, unchanged from baseline
- `python3 dev/redproof.py check` → **clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits**
- No conflict markers (`grep -nE '^(<{7}|>{7}|\|{7}|={7}$)'` → exit 1, no matches)

Files run: `test_journal_consume.py`. Non-UI lane, no browser guards.

## Cited issues, relied-on lines quoted

- **#712** — the guard that must survive. Relied-on line: *"the right form
  only when there was no prior read to bound against"* — the bare-consume
  escape hatch, which my fix does not widen.
- **#702** — *"an entry the tool cannot classify must be REPORTED, never
  silently dropped."* Governs the empty-`pending` half: a transition is exactly
  that class.
- **#671** — *"a check that examined nothing must not be read as passing."*
  The silent pending printed nothing while an ordinal sat unread.
- **#136** — *"nothing needs you and there is something above your cursor I
  will not show you rendered identically."* Defect 2 stated as the rule.
- **#612** — volume. The change is a head computation and one output line.

## Rebase outcome

Branched from `13e8b8c6b72d`; master moved to `0d7cc5be6025` (2 commits) during
the work. `git rebase master` applied cleanly, no conflicts. HEAD now
`a49e9f3f07db`. Three commits: `fix(#722):`, `test(#722):`, `docs(#722):`.

## Out of scope (not fixed — naming for the coordinator)

- **`verify_chain` is now called on the consume path for non-receipt target
  ordinals**, which doubles the work `advance_cursor` already does (it runs its
  own bounded rebuild of the same range). For a drain of N events this is 2N
  chain reads instead of N. Negligible at tick scale (N is single digits), but
  a future optimization could expose a public "hash at ordinal" read on
  `Journal` to avoid the recomputation. Not done here — it would touch
  `user_events/sqlite.py`, which is out of scope.
- **The `receipt.health` and `generation.cutover` event kinds** share the
  chain's ordinals and would be drained the same way (the fix is
  kind-agnostic). Not exercised by a test because `transition` is the only
  non-listed kind reachable through the public API today; if a health/cutover
  event ever lands as the head, it drains by the same construction.

---

## Dogfood report

1. **The BRIEF's claim that `transition` needs `expected_revision` from
   `get_receipt` (not 0) cost me one smoke-test cycle.** The brief did not state
   this; I guessed `expected_revision=0` and the transition silently no-op'd
   (returned `stale`), so my first fixture showed head=1 not head=2 and the
   pending output looked like the bug was still present. A one-line note in the
   brief — "a fresh receipt sits at revision 1, so `transition(...,
   expected_revision=rec['revision'])`" — would have saved that cycle. Minor.

2. **`dev/redproof.py` is excellent and the brief's instructions for it were
   exactly right.** The `begin`/`sabotage`/`restore`/`check` protocol worked
   first time, the snapshot was lane-private as advertised, and `check`'s
   branch-history scan caught that my first red-proof committed the restructured
   test under the injection (it didn't — clean). No friction here.

3. **The `just pytest -q` note in the brief is accurate and saved a wasted
   call** — I used `python3 -m pytest` directly. The `--tb=short` form is what
   the brief's examples imply and it worked.
