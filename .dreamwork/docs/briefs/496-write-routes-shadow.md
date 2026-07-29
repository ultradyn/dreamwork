# Brief — lane-496routes: E2Shadow WRITE_ROUTES count is stale (9 routes, test asserts 8) (#496)

Lane-owns: `test_user_events_http.py` ONLY. Do NOT touch `watch.py` —
`WRITE_ROUTE_HANDLERS` is production truth and the shadow pins it; the
count is the test's, not the table's.

**Model:** llmp-glm-5-2 · **Isolation:** worktree (coordinator merge-gates).

## The defect (verified open in the store 2026-07-30)

`test_user_events_http.py:305` asserts `len(WRITE_ROUTES) == 8`, but
`watch.py`'s `WRITE_ROUTE_HANDLERS` (line ~14306) gained a ninth route
(`/deploy`, from #462) and the shadow was not extended. Pre-existing red
on master.

## What the shadow IS (read before editing)

`WRITE_ROUTES = tuple(_HANDLER_CLS.WRITE_ROUTE_HANDLERS.keys())` at line
42 derives the set from production; lines 310–311 then assert every write
route answers `202` with the journal on and `200` with it off, and line
323 asserts one receipt per route. The literal `8` at line 305 is the
**alarm**: a hand-pinned count whose whole job is to go red when the
production table changes, so a new write route cannot slip in without the
shadow being consciously extended. **Do not "fix" the alarm by deriving
it** (`len(WRITE_ROUTE_HANDLERS)` == itself is a check born hollow — the
repo has a documented lesson about exactly that shape). The literal stays
literal; it gets bumped, with its comment saying why a literal.

## The work

1. Read `test_user_events_http.py` around lines 42, 300–330 and the
   `WRITE_ROUTE_HANDLERS` table in `watch.py` (~14306). Enumerate the 9
   routes and identify which one the shadow is missing (`/deploy`).
2. **Verify `/deploy` genuinely belongs to the shadow's semantics** before
   bumping: does it pass through the same receipt path (202 with journal
   on, 200 off, one receipt per call)? Run the E2Shadow class and READ
   which assertions fail today — if `/deploy` behaves differently from the
   other eight (e.g. it is long-running, or its handler responds before
   the receipt commits), that is a finding to REPORT, not to paper over.
3. Bump the literal with a comment naming the date and the route that
   reddened it (the next reader must learn the alarm works, not that
   someone edited a number).
4. If the shadow's per-route assertions pass for all 9 with no other
   change, done. If `/deploy` needs a shadow carve-out (different expected
   status), propose the minimal honest shape — an explicit named exception
   is honest; a widened assertion that stops checking the other eight is
   not.

## Constraints (hard)

- Red-first: run the E2Shadow class on master FIRST and capture the
  failing output in your report (which assertions, verbatim).
- Small commits, `git commit --only <paths>`. NEVER `git add -A`.
- Never `attn`, never `pkill -f`, never ports 35110/39880-39899. The test
  spins its own fixture servers — let it use its own port selection; check
  `ss -ltnp` for squatters first if a bind fails.
- The repo rule: **a green red-run is a finding, never a relief.** Your
  change must be red-proved: revert the production-relevant line YOUR test
  pins (here: the literal — set it back to 8) and watch exactly the count
  assertion fail; then restore. Also verify the shadow is not hollow from
  the other side: if you temporarily REMOVE a route from a local copy of
  the fixture's handler table, the status assertions must red. Name the
  production line each red depends on.
- `python3 -m pytest test_user_events_http.py` green at the end; note in
  the report whether any OTHER failures in that file pre-exist on master
  (compare, don't fix).

## Acceptance criteria (measurable)

1. `test_user_events_http.py` E2Shadow green with the route table at 9.
2. The count stays a literal with a comment explaining the alarm (and why
   derived would be hollow).
3. Report shows: the master's failing assertions verbatim; the 9 routes
   enumerated; `/deploy`'s receipt semantics verified (or the carve-out
   proposed); both red directions run and named.
4. `git diff master --stat` touches only `test_user_events_http.py`.

## Hand-off obligation (#398)

Final report (the coordinator writes `.dreamwork/handoffs.md` from it):
the master failure verbatim, the fix, both red-proof directions with the
production lines named, and any `/deploy` finding.
