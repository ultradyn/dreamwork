# Lane 770 report — brief persistence reaches the main corpus

## Verdict and measured Git premise

PASS, with one merge condition: squash this branch because the required committed
red-proof injection remains reachable in its history.

`git rev-parse --git-common-dir` actually returned:

- linked worktree: `/home/xertrov/.llm-general/skills/ud-dreamwork/.git`
- main checkout: `.git`
- plain clone with no linked worktrees: `.git`

The candidate is therefore insufficient if its answer is naively joined to the
process cwd: two of the three measured cases are relative. The supported resolver
uses exactly one command, anchored independently of process cwd:

    git -C <interpreter-root> rev-parse --path-format=absolute --git-common-dir

That returned an absolute `.git` directory in all three cases. The resolver rejects
Git failure, empty/multiline output, relative output despite the absolute-path
request, a non-`.git` answer, and an absent directory. It never substitutes a
plausible fallback. A conventional checkout with a separate Git directory is not
silently misdirected: it is deliberately refused as "could not determine brief
corpus". Supporting that uncommon topology would require a separately designed
checkout-root mechanism and is outside this defect.

## Interpreter, subject, and change

The interpreter is the invoked worktree path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.worktrees/cx-770corpus/dev/dispatch_lane.py`.
The subject to persist is the main checkout corpus
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/docs/briefs`.
The runner still inherits the worktree cwd; the corpus is independently derived
from the interpreter worktree's Git common directory.

I removed the module-level worktree-derived corpus default and added one fail-closed
resolver used by both `persist_prompt()` and `verify_pending()`. Validation and the
receipt format are unchanged. `justfile` required no change, so I did not touch it.

Tests now prove:

- a plain clone persists to its own corpus;
- a linked-worktree interpreter persists only to the main corpus;
- a valid pair outside the corpus does not count when the canonical corpus is empty;
- Git failure says "could not determine brief corpus", distinct from a filesystem
  persistence failure;
- relative Git output is refused;
- the existing healthy dispatch remains silent.

## Actual supported-route proof

Before, I ran the pinned `7270566e` route from a temporary linked worktree with an
absolute `true` shim named `ccc`. The interpreter and cwd were that linked worktree.
The route returned 0 with zero output bytes; its receipt verified `OK`; the pair was
inside the linked worktree and absent from the main corpus.

After, I ran `just dispatch-lane` from this linked worktree with the same harmless
runner arrangement. The interpreter and cwd remained this worktree. The route
returned 0 with zero output bytes; the worktree artifact was absent; the pair was
in the main corpus and `sha256sum -c` reported `OK`. Every synthetic route artifact
was then removed; historical briefs and reports were not changed.

## Red-proof, both directions

Direction 1 injected the real defect by returning the interpreter-local
`.dreamwork/docs/briefs` path. The linked-worktree test went red on the intended
assertion:

> AssertionError: validated brief did not reach the main corpus:
> .../main/.dreamwork/docs/briefs/903-cx-linked.md

The injected line was committed in `1c456320`, then restored from both the
red-proof registry and the lane-private fixed snapshot, verified with `cmp`, and
the focused test returned `1 passed`.

Direction 2 produced a valid brief/receipt pair in the wrong worktree directory.
With an empty canonical corpus, the check refused with `DID NOT VERIFY`, proving
that "persisted somewhere" does not satisfy "persisted to this corpus". I then
constructed the harder false-green: the wrong pair still verified `OK`, its
canonical counterpart was absent, but unrelated canonical pairs existed. The
aggregate check printed:

> brief integrity verified: 2 governed brief(s) matched receipts

That open false-green is an expected limit of an aggregate corpus check with no
expected-dispatch inventory. Closing it would change the validation/inventory
contract, which this task forbids. For the supported dispatch route, the placement
bug is closed by construction: both write and verify resolve the same canonical
directory, the linked-worktree test asserts the lane-local directory does not
exist, and every resolution ambiguity refuses before the runner executes.

The final red-proof hand-off gate said:

> check: REFUSED — the working tree is clean, but 1 commit(s) on this branch still
> hold a recorded injection: 1c4563203fbe ...

It examined four branch commits and found the one deliberately injected blob.
The coordinator must squash this branch at merge so that defect is not reachable
from master history.

## Verification

- `just pytest test_dispatch_lane.py` — `20 passed in 2.16s`; the assertion that
  would fail is the linked-worktree artifact's presence in the main corpus and
  absence from the lane corpus.
- `python3 lint.py` — clean with exactly 5 warnings, the stated worktree lane bar;
  the zero-entry warnings explicitly say they examined nothing.
- fixed route from the linked worktree — rc 0, 0 output bytes, lane artifact absent,
  main artifact present, receipt `OK`.
- `git diff --check master...HEAD` — clean.
- rebased cleanly onto local `master` `3d082c0db964`; no conflicts and no hand
  resolution.

Implementation head before this report: `47f18c0e6fd1`.

## Ledger evidence relied on

- #770: "Brief persistence writes into the lane worktree, not the main checkout,
  because just resolves the worktree's own copy of the dispatcher."
- #607: "That leading path is a SYMLINK into the main checkout, so it is the
  INTERPRETER, while --target is only the SUBJECT."
- #671: "420 commits examined, 177 open ids never seen, and it printed
  'nothing to review (this ran)'."
- #136: "A questions.md that parses to nothing must say so."
- #440: "so: a single supported way to fold an entry."
- #465: "a lane can edit the MAIN CHECKOUT instead of its worktree, and nothing
  notices until a merge fails."
- #755: "status.json's queued_dispatches names task ids that nothing verifies are
  still open."
- #769: "SKILL.md says the supported dispatch route is silent on a healthy
  dispatch, but just echoes the expanded recipe line so it never is."

## DOGFOOD REPORT

The task head's attribution of healthy-route silence to #755 is wrong: the #755
entry is about stale queued-dispatch ids. The relevant route-silence evidence is
#769. I preserved silence based on the actual route behavior and its binding test,
not the miscitation.

The task head prescribes a manual lane-private snapshot and `cp` restore while the
standing boilerplate says the red-proof tool owns snapshot and restore. Neither
instruction explicitly overrides the other. I satisfied both by arming the
red-proof registry, taking the requested fixed-file snapshot, restoring through
the registry, copying the fixed snapshot back, and checking it with `cmp`. This was
redundant but safe; the brief should name an override or prescribe the combined
sequence.

My first harmless-runner shim was accidentally a broken relative symlink
(`ccc -> true`), so executable search fell through to the real external `ccc`. I
interrupted it promptly, then discarded that run as evidence. All reported before
and after route proofs were rerun with `ccc` linked to the absolute result of
`type -P true`. A testing recipe that asks for a harmless PATH shim should say
"absolute executable path"; a broken executable earlier in PATH is skipped rather
than producing an obvious not-found failure.

Finally, the aggregate pending verifier can still pass when one specific dispatch
is misplaced out of band and some unrelated canonical pair exists. The supported
writer can no longer produce that state, so it does not block this scoped fix, but
it is the larger inventory gap described in Direction 2 and should be filed rather
than silently treated as closed.
