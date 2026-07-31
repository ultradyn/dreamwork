# Lane #731 report

Recorded 2026-08-01 02:32 AEST.

## Verdict

PASS. `dev/ledger.py retitle <id> "<new title>" --why "<reason>"` now exists
as a store-mode sibling of `reprioritise` and `unblock`. It changes the title,
appends the old title, new title, and reason to the task body, and records the
reason in the task event chain. `--why` is argparse-required.

A same-title call refuses with exit 1, writes no body or event, emits no success
line, and says:

> title is unchanged — a retitle that changed nothing must not read as success

The unresolved-store gate remains distinct: `_VERB_ARGV` includes a minimal
valid `retitle` invocation, and the every-verb gate pins that refusal to exit 2.

## Design decision

A changed title that still contains the #725 claim idiom `blocked on` is
allowed. `retitle` is a general reasoned writer; duplicating the current lint
predicate inside the writer would create a second authority and would
second-guess an author who supplied the mandatory reason. The existing #725
warning remains visible and is the authority for that contradiction.

Within the granted files, the event uses the existing closed-set `reconciled`
cause. Its body note names the operation explicitly as `retitled old→new`, so
both human and machine histories retain the reason without widening the event
vocabulary outside this lane's scope.

## Changes and commits

- `5a25295a` — `feat(#731): add reasoned retitle writer`
- `62190335` — `test(#731): bind retitle history and no-op atomicity`
- Changed `dev/ledger.py`, `ledger_write.py`, `test_ledger.py`, and
  `test_ledger_cli.py` only, plus this required report.
- Did not run any mutating command against the live ledger.

## Red-proof

### Direction 1 — discriminating no-op refusal

Used `python3 dev/redproof.py begin ledger_write.py`, sabotaged the production
guard to allow same-title calls, and ran exactly
`test_retitle_cli_same_title_refuses_not_success`. It failed at the intended
assertion:

> AssertionError: same-title retitle must refuse (exit 1), got 0

`python3 dev/redproof.py restore ledger_write.py` restored and verified the
fixed file.

### Direction 2 — successful retitle that still misleads

Constructed a fixture task titled `blocked on his ruling` with empty
`blocked_on`, then successfully retitled it to `still blocked on his ruling`.
The committed test asserts both the successful changed title and the still-empty
structured blocker. This is an intentional accepted false-green of the writer:
#725 lint still reports it, while the writer does not duplicate lint policy.

The hand-off gate output was:

> history: examined 2 commit(s) since 1d095ad3da65 (master) against 1 injected path(s); read 2 blob(s), 0 holding a recorded injection.
>
> check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits

## Verification

`python3 -m pytest test_ledger.py test_ledger_cli.py test_ledger_write.py`:

> collected 119 items
>
> 119 passed in 2.94s

`python3 lint.py`:

> clean (6 warning(s))

The six warnings are expected worktree/store or pre-existing repository
warnings; there were no ERRORs. No browser guards were run or required.

## Rebase

No rebase was required. At the completion check, local `master` was still
`1d095ad3da6565e6d1fd1503573ac86cb7f2d945`, the lane's base, and
`git rev-list --count HEAD..master` returned 0.

## Relied-on issue lines

- #731: “a retitle that changes nothing (same title passed) must REFUSE, not
  report success.”
- #627: “Needs `ledger.py reprioritise <id> <band> --why` and `ledger.py
  unblock <id> --why` … each recording WHY in the task's own history.”
- #725: “`list` prints titles, not notes. The correction is invisible exactly
  where the error is visible.”
- #734: “rc==2 is now PINNED” for the unresolved-store refusal, and “the
  failure message now says what to DO — which #731's retitle verb will hit
  next.”
- #671: pre-fix sweep printed “nothing to review (this ran)” after examining
  zero ledger entries; the relied-on rule is that a no-op or unexamined zero
  must not present itself as a successful answer.

## DOGFOOD REPORT

Friction found: the task's granted source files include `ledger_write.py` but
not `ledger_store.py`, while “look like its siblings” naturally suggests a new
`retitled` event cause and the cause vocabulary is closed in `ledger_store.py`.
The lane therefore had to infer that reusing `reconciled` was the intended
scoped solution. Future briefs adding a store mutation should state whether
the event-cause vocabulary may be widened or which existing generic cause to
use.

Minor tooling friction: `dev/lessons_index.py --act red-proof` returned 42
lessons and exceeded the displayed output budget for a one-line sabotage. The
required lesson was present, but a narrower sub-act or ranked top slice would
make the just-in-time consultation cheaper without weakening it.
