# Lane 773 report — shared mutable brief corpus

## Verdict: five lint checks read the live corpus

Five current lint checks read `.dreamwork/docs/briefs/`, the directory the
real dispatcher correctly mutates in the main checkout:

1. `check_brief_handoff_obligation`
2. `check_brief_worktree_abs_inbox`
3. `check_brief_lane_scratch`
4. `check_brief_lane_owns`
5. `check_lane_containment_backstop`, via `lane_owned_paths`

The first four also call `brief_corpus_reach`; the fifth reads the same files
to derive lane ownership. This is therefore a shared-boundary problem, not a
one-check fix. The broader `run_checks` list contains other live readers, but
these are the five whose input a correctly operating dispatch changes under
this task's constraints.

I shipped the fix. A synthetic main checkout was rejected: it would weaken the
real route proof without making a production lint run explain interference.
The dispatch route and `dev/dispatch_lane.py` are unchanged.

## Measured incident reproduction

Before changing code I used the worktree interpreter against the real main
checkout and inserted one temporary numbered brief between two check calls.
The reader saw:

```text
BEFORE: ... coverage reach UNKNOWN — newest numbered brief #773 is 1 id(s) ahead of task history #772
DURING: ... coverage reach UNKNOWN — newest numbered brief #999999 is 999227 id(s) ahead of task history #772
RESTORED: True
```

Both rows were ordinary `OK briefs` rows even though one lint operation had
sampled two populations. The temporary file was removed and its absence was
verified immediately.

## Decision (IGC)

Context: the supported dispatch must keep writing the real main corpus while
tests and merge lint can run concurrently.

| Idea | All | G1 | G2 | G3 | G4 |
|---|:---:|:---:|:---:|:---:|:---:|
| Point dispatch at a synthetic main checkout | ✘ | ✘ | ✘ | ✔ | ✔ |
| Retry or special-case each brief check | ✘ | ✔ | ✘ | ? | ✔ |
| Freeze test assertions; fingerprint the five-check block; name in-flight reach | ✔ | ✔ | ✔ | ✔ | ✔ |
| Record the measurement and build nothing | ✘ | ✔ | ✘ | ✘ | ✘ |

- G1: preserve proof through the real dispatch route.
- G2: distinguish a corpus changed during lint from a bad merge.
- G3: keep gate assertions independent of concurrent live writes.
- G4: retain historical-lag detection while distinguishing in-flight from
  genuinely unknown coverage.

The synthetic route fails G1 and leaves the real merge lint ambiguity in G2.
Per-check handling duplicates one shared-state policy five times and can still
sample different populations. The surviving design puts the stability check
around the shared reader block and uses the already-present `frozen_tree`
fixture only for the unit assertion; it does not replace the dispatch route.

## Changes

- `brief_corpus_fingerprint` hashes the names and bytes of all `.md` inputs.
  `run_checks` compares it immediately around all five corpus readers. A
  persistent concurrent write now emits an `ERROR brief corpus` whose message
  says `CHANGED DURING LINT`, says the checks did not examine one fixed corpus,
  and explicitly says this is not a merge verdict.
- The ahead branch now says `IN FLIGHT` and compares against `landed task
  history`; `UNKNOWN` remains reserved for a genuinely unorderable population.
- The live parity assertion now uses the existing detached-HEAD `frozen_tree`
  fixture. The real dispatcher is still exercised against its real destination
  by its own route tests.
- Tests construct a persistent mid-run write, the net-zero false-green, the
  in-flight reading, and the existing max-id completeness false-green.

The wording fix is the most valuable steady-state part: an active lane makes
the corpus ahead routinely, so teaching the operator that healthy means
`UNKNOWN` would make the line skippable. The fingerprint is still necessary to
close the rarer but expensive ambiguous-red incident.

## Red-proof, both directions

### Interference visibility

Direction 1 injected a constant fingerprint into the fixed `lint.py`. The
mid-run mutation test went red on the discriminating assertion:

```text
AssertionError: missing CHANGED DURING LINT interference verdict
```

With the fix restored, the test asserts the finding contains both `CHANGED
DURING LINT` and `not a merge verdict`.

Direction 2 is an open false-green, constructed in a passing test: a writer can
add and remove the same brief entirely between the two fingerprint samples.
The starting and ending content identities match, so no interference row is
emitted. This does not describe the supported dispatcher, whose artifact
persists for the merge gate; closing it would require a filesystem event log,
not a stronger snapshot.

### In-flight versus unknown

Direction 1 injected the old ahead branch. The test went red showing the exact
wrong reading:

```text
'coverage reach UNKNOWN — newest numbered brief #108 is 1 id(s) ahead of task history #107; ...'
assert reach.startswith("IN FLIGHT")
```

Direction 2 remains the reach signal's documented completeness false-green:
briefs `#100` and `#102` plus task subjects `#100`, `#101`, `#102` return
`current through task #102` even though brief `#101` is absent. The new test
pins that limit. The check orders maxima; it is not one-brief-per-dispatch
proof, and this task does not weaken or overclaim it.

Both injections used `dev/redproof.py`. The fixed file was separately copied
to the lane-private `dev/lane_scratch.py snap` directory, restored by `cp`, and
verified by `cmp`; no `git checkout` was used. Final redproof output:

```text
history: examined 1 commit(s) since ef909220b739 (master) against 1 injected path(s); read 1 blob(s), 0 holding a recorded injection.
check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits
```

## Verification

- `python3 lint.py`: exit 0, **5 warnings**, no errors. This matches the brief's
  lane bar at the rebased snapshot; the warnings are the expected worktree
  ledger/status/near-duplicate rows.
- `just pytest test_lint.py`: **552 passed** in 85.90s after rebasing.
- `just pytest test_lint.py::TestBriefCorpusReach`: **8 passed** after the
  explicit completeness false-green test was added.
- No browser guard or port was touched.

Rebase: successful, without conflicts, onto local `master` at `ef909220b739`.
The post-rebase code commit is `5937303`.

## Governing issue evidence

- `#773`: “Whatever ships must make the interference either impossible or
  VISIBLE.” The persistent-write fingerprint makes it visible.
- `#465`: “parallel increments only ever touch disjoint files, so there is
  never a split brain ... by construction.” This task preserves that invariant
  and treats the dispatcher corpus write as the explicit exception, not a
  reason to widen lane authority.
- `#770`: “the RUNNER needs cwd = worktree, the CORPUS needs the main checkout.”
  The implementation does not disturb either half.
- `#136`: “THREE zero-states, not one.” `IN FLIGHT` and genuinely `UNKNOWN` no
  longer render as one state.
- `#671`: “Zero entries now says DID NOT REVIEW rather than ‘nothing to
  review’.” Likewise, a changed corpus says it did not judge one population.
- `#702`: “this cannot be fixed by remembering.” The result is runtime-visible,
  not another lane instruction.
- `#755`: “Direction 2 to construct: the stale entry that PASSES.” Both open
  false-greens are constructed and named rather than hidden.
- `#440`: “the check that matters is that the tool exists and is the only path.”
  One boundary in `run_checks` owns the five-reader stability rule.
- `#766`: “FOUR LIVE LINT CHECKS NOW READ AS HEALTHY OVER A FROZEN CORPUS.” The
  four are still substantive, historical lag still says `HISTORICAL ONLY`, and
  the later containment reader makes today's measured count five.

## Out of scope

- The containment check also reads the live worktree registry and main-checkout
  dirty paths. Those inputs are intentionally live and are not changed by the
  dispatcher write at issue here. I did not generalise this into a transaction
  system for every lint input.
- Net-zero add/remove interference is visible only to an event watcher, not two
  content snapshots. It is recorded above; the supported persistence route
  does not perform that sequence.

## DOGFOOD REPORT

The highest-value sibling was already in `test_lint.py`: `frozen_tree` says a
dogfood test false-redred when another lane changed briefs mid-run and explains
that HEAD must be the fixed subject. The exact family had therefore already
been solved once, but `TestBriefCorpusReach` did not use the fixture. Finding
and reusing that seam avoided inventing a second isolation mechanism.

The `brief_corpus_reach` docstring also claimed its completeness false-green was
“covered by the tests”; no test constructed it. This lane added the missing
`#100/#102` with absent `#101` case, so the claim is now evidence-backed.

One verification run also exposed command-session friction: treating a yielded
long pytest command as completed started a duplicate suite and left one
temporary detached worktree. I stopped only those lane-owned processes,
removed that explicit temporary worktree, pruned the metadata, and reran once
with the session tracked to its exit-0 result. No product change is warranted;
the durable lesson for this lane is to retain and resume the yielded session.
