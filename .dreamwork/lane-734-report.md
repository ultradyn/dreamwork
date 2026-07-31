# Lane #734 report — gate the exit code, not just the message

## Verdict: SHIPPED. One commit, `75d43900`, test-only, 115/115 green.

## The one red on master, fixed

`test_ledger_cli.py::test_the_map_covers_every_verb` was red: `reprioritise`
and `unblock` were in the parser (added by #627) but never added to
`_VERB_ARGV` (the gate sweep's coverage map). Map test went green the moment I
added the two rows.

## THE BRIEF'S PREMISE WAS WRONG, and that is the finding

The brief's central claim — that both verbs **refuse with exit 0** — is **false
on the current code.** I measured it directly through the production path
(`_dispatch`), against a real linked-worktree fixture built from the test's own
helpers:

```
reprioritise 10 P3 --why probe --ledger <unresolved worktree>  → rc=2
unblock 10 --why probe --ledger <unresolved worktree>          → rc=2
get 10 --ledger <unresolved worktree>  (control)               → rc=2
md5 before == md5 after: UNCHANGED (both verbs)
```

The verbs already exit **2**, not 0. They never exited 0 on the current tree.

### Why the brief said exit 0, and why that no longer holds

`git blame` shows the timeline (and the brief itself half-named the cause —
"dev/ledger.py is FREE as of minutes ago (#724 merged)"):

- `ef3ac88ba` (Jul 31 19:34) — the **#667 gate** landed: the `_unresolved_store`
  check at the TOP of `_dispatch`, returning 2. One gate, every ledger-reading
  verb.
- `cb7a9460a` (Aug 1 00:53) — **#627** added the two verbs, *behind* the
  already-existing gate. The verbs' own `store-mode only` block (line 1959,
  `return 1`) is UNREACHABLE from a worktree: the gate fires first.

The brief's "throwaway copy of a worktree shim" measurement was almost
certainly taken **before** `ef3ac88ba` landed the gate — the exit-0 finding was
real then, and #667's gate fixed it for every verb *including these two* without
#627 having to do anything. The brief was written against a state that no longer
exists. The brief's safety finding ("there is NO data risk — neither verb
writes") is still correct and I re-verified it (md5 byte-unchanged), but the
exit-code defect it describes is already gone.

## The design question, decided — and it decided itself

The brief asked whether the gate accepts a second refusal form
("store-mode only") or forces the #667 wording ("did not resolve here"). **In a
worktree the question is moot**: the #667 gate fires before the #627
store-mode-only block can, so a lane in a worktree sees the #667 wording
("did not resolve here") on every verb, reprioritise and unblock included.
The "store-mode only" message only appears in a markdown-mode project (no store
at all), where it is the correct message — those columns genuinely do not exist
there. **Two refusal forms, each in the context where it is accurate, with no
overlap** — which is exactly the "accuracy leans to two" position, reached by
the code's structure rather than by argument. I changed nothing about either
wording.

### Exit code — already correct, and not colliding

Measured against the resolved store for these specific verbs:
- **exit 1** = "no such task" (`reprioritise #9999` → `cannot reprioritise
  #9999: no such task`, rc 1; same for unblock). This is #497's "no such id"
  contract, unchanged.
- **exit 2** = the #667 gate's refusal (store did not resolve). Reusing 1 here
  *would* collide with the not-found meaning, which is exactly why the gate
  returns 2. Confirmed: `test_the_refusal_is_distinguishable_from_a_real_not_found`
  pins this for `get`, and the same code path serves all verbs.

No change needed. The verbs were already non-zero, already not colliding.

## THE REAL DEFECT: the gate test asserted everything except the exit code

The brief said "the discriminating assertion is the EXIT CODE" and it was
exactly right about the *test*, even though the *code* was already correct.
`test_every_verb_is_gated_not_just_get` checked four things — that the refusal
message appeared, that the file was byte-identical, that the message went to
stderr not stdout, and (via the map) that the sweep covered every verb. **It did
not check the return code.** A future verb that refused correctly on stderr,
wrote nothing, and yet exited 0 (reads as success, #671) or 1 (collides with
"no such id", #667) would pass every assertion it had. That is the hole, and it
is the hole the brief was sent to close.

**Fix:** added `wrong_rc` — for every non-sweep verb that hit the gate, the test
now asserts `rc == 2`. Sweep keeps #404's advisory exit 0 (already pinned by its
own dedicated test).

## The map test, improved for #731

The failure message now says what to DO:

```
every parser verb must have a row in _VERB_ARGV (the gate sweep's coverage map)
and vice versa.
  add to _VERB_ARGV with a minimal valid argv: ['reprioritise', 'unblock']
  remove from _VERB_ARGV (no parser entry): []
```

#731's lane (retitle) will hit exactly this and be told the remedy. The map
test is NOT weakened — it still derives the verb set from the parser and demands
exact agreement.

## What I changed

`test_ledger_cli.py` only (3 edits, +25/-3):
1. Added `reprioritise` and `unblock` to `_VERB_ARGV` with minimal valid argv
   (`--why` is argparse-required, matching #627's design).
2. Improved `test_the_map_covers_every_verb`'s failure message to name the
   remedy (add/remove from `_VERB_ARGV`).
3. Added the `wrong_rc` assertion to `test_every_verb_is_gated_not_just_get`.

**No `dev/ledger.py` change.** The verbs were already correct. This is a
test-only fix.

## Both directions of red-proof

### Direction 1 — the discriminating red (quoted)

`python3 dev/redproof.py begin/restore/check dev/ledger.py` — full protocol.

Sabotage: the #667 gate's `return 2` → `return 0` (line 1905). Ran the gate
test. **`wrong_rc` fired**, the other three assertions passed (proving the new
assertion does unique work):

```
AssertionError: a store that did not resolve must exit 2, not 0 (reads as
success, #671) or 1 (collides with 'no such id', #667): [('count', 0),
('counts', 0), ('file', 0), ('fold', 0), ('get', 0), ('groom', 0),
('list', 0), ('note', 0), ('reprioritise', 0), ('reviews', 0), ('unblock', 0)]
```

Restored, `check` clean:
```
check: clean — 1 injection(s) registered, all restored and absent from the
working tree and from this branch's commits: dev/ledger.py (sha 816bb995e2fb,
hint: 'return 0')
```

### Direction 2 — the false-green I could not close, named

The open false-green: **a dead verb** — one that is parsed (so it appears in the
parser's choice list and satisfies the map) but never dispatched (no `if
args.cmd == "..."` branch in `_dispatch`). Such a verb would pass the map test,
and in the gate sweep it would hit the #667 gate, refuse correctly with exit 2,
write nothing, and put the message on stderr — passing all four assertions —
while doing nothing useful. The gate verifies that a verb *refuses* against an
absent store; it does not verify that a verb *does its job* against a present
one. That is a different test (one per verb, against the resolved store), and
`test_a_healthy_main_checkout_is_never_refused` only covers `get`. Reported, not
closed — closing it is a verb-by-verb happy-path suite, out of scope for #734.

**Two brief-named candidates ruled out as false-greens:** (a) missing `--why`
causes argparse `SystemExit(2)` *before* the gate — loud, not silent; (b)
stdout leakage is already caught by the existing `wrong_stream` assertion.

## Cited issues — relied-on lines quoted

- **#671** (the governing rule): *"a refusal that exits 0 reports success"*
  — relied on for the `wrong_rc` assertion's existence and its failure message.
- **#497** (the output contract): *"Unknown id -> one-line stderr + exit 1"*
  — relied on to establish that exit 1 already means "no such id", so the gate
  must not reuse it.
- **#667** (the gate this lane is about): *"Exit 2, not 1... `get`'s exit 1
  already MEANS 'no such id' under the #497 output contract, so reusing it
  would hide the refusal inside the answer it is refusing to give"* — relied on
  for the exit-2 contract the test now pins.
- **#136** ("I refused" and "I did it" must not render identically): *"A
  questions.md that parses to nothing must say so"* — the principle, applied at
  the exit code.
- **#612** (volume): *"A correct change that triples a doc's length gets
  reverted by the next reader"* — relied on for the +25/-3 scope.
- **#440** (one-supported-way): *"a single supported way to fold an entry"*
  — the one-wording-or-two question's frame; the code reached two-wordings by
  structure.
- **#731** (the incoming third verb): *"same shape as #627's reprioritise /
  unblock: --why MANDATORY and argparse-enforced"* — relied on for the improved
  map failure message, which tells #731's lane what to do.
- **#627** (the verbs themselves): *"--why is MANDATORY (argparse refuses
  without it, verified at the gate)"* — relied on for the argv shape in
  `_VERB_ARGV`.
- **#724** (freed ledger.py): *"THE SEAM IS THE GOOD PART: sweep() gained an
  optional cites(sha, body) callable whose DEFAULT is #404's existing substring
  check"* — read; the `cites` predicate in sweep was not touched, as instructed.

## Rebase

Not needed. `master` (`8a00df97`) is an ancestor of my branch (`75d43900`); the
branch sits one commit on top of master and master has not moved since dispatch.
Verified: `git merge-base --is-ancestor master lane-734gate` → exit 0.

## Verification

- `python3 -m pytest test_ledger_cli.py test_ledger.py test_ledger_write.py` →
  **115 passed** (was 114 before; the map test went from red to green, nothing
  else changed).
- `python3 lint.py` → **clean (6 warning(s))**, all expected markdown-mode
  worktree warnings, no ERRORs.
- No browser guards run (non-UI lane, #733 may be using the ports).

## Dogfood report

**The brief's premise was stale, and it cost me the first hour.** The brief was
written against a state where the verbs exited 0, but #667's gate (landed hours
earlier) had already fixed that for every verb. The brief *said* #667 had landed
("the gate they escaped is `test_every_verb_is_gated_not_just_get`") but then
described the verbs as if they had escaped it, which they had not. I spent the
first hour trying to reproduce the exit-0 the brief promised, and could not —
because it was already exit 2. **The brief's "I ALREADY MEASURED" framing made
this harder to question, not easier.** A measurement is only worth quoting if it
names the commit it was taken against, and this one did not — it named a
throwaway copy of a worktree shim with no timestamp. `git blame` on the two
refusal paths settled it in seconds.

**The redeeming half:** the brief's insistence on the exit code as the
discriminating assertion was *correct for the test* even though it was wrong
about the code. The gate test genuinely did not check the exit code, and a
future verb that refused correctly but exited 0 would have sailed through. That
is a real hole, and the brief found it. So the brief was wrong about the bug and
right about the fix — which is the most useful kind of wrong.

**Smaller notes:** the `_VERB_ARGV` lives in the *test file*, not `dev/ledger.py`
— the brief spoke as if it were in ledger.py ("never updated `_VERB_ARGV`"). A
lane that grepped ledger.py for it (as I first did) wastes one call. The map
test's docstring says where it is, but the brief could have said so.
