# The guard suite under concurrent lanes (#428)

Status: increment 1 **landed** `1454717`. The full fix surface is enumerated here
rather than absorbed, because a count of the exposed surface is worth more than
one fixed test.

## The defect, measured

`test_lint.py::TestTheBugItWasBuiltFor::test_this_repo_passes_its_own_linter`
FAILED in a full suite run at 04:55 (eight lanes out) and PASSED alone seconds
later, with `lint.py --target .` clean either side. The cause is not load and
not a flake: **that test lints the LIVE working tree**, and during the run
another lane committed `Lane-owns:` lines to 44 briefs while others wrote their
own files. The tree the assertion was about changed underneath it.

This is a different failure shape from the first two `#428` instances (the
frame-sampling guards). Those were *"passes in isolation"* with no established
mechanism. This one is **state sensitivity with a measured mechanism**, and it
is guaranteed to recur: the human asked for up to 8 concurrent lanes, so a test
that reads mutable shared state during a lane's commit is a false red **by
design**.

Why a false red is worse than a missing check here: there is no CI, so this
suite is the only gate. A gate that cries wolf whenever the machine is busy
gets read as noise, and the next real failure arrives wearing the same clothes.

## What landed (increment 1)

The dogfood test now runs against a **detached worktree snapshot at HEAD** — a
fixed tree no concurrent lane can move — instead of the live working tree.

- `test_lint.py` gains a `frozen_tree` fixture: `git worktree add --detach
  <tmp>/frozen-head HEAD` (~94ms, measured), yielded, and removed `--force` in a
  `finally` so a crash cannot orphan a worktree the lane-containment backstop
  or the `#203` reaper would later trip on.
- The fixture **raises** if git cannot make the snapshot. Falling back to the
  live tree would reintroduce the false red this exists to fix; the failure
  surfaces instead.
- The test asserts a **runtime-derived precondition**: the snapshot carries a
  populated `questions.md`/`tasks.md` and `parse_ledger` yields a non-trivial
  open-id count, otherwise `not rep.failed` proves nothing on an empty tree
  (the hollowness this repo keeps paying for).

### Red-proof, both directions, against pre-existing production code

The check that goes red is `run_checks → check_questions` — production code that
predates this diff. The diff adds a snapshot *fixture*; it does not add the
check. So the red is not circular.

- **A — live churn must not move it.** Breaking the live `questions.md` to the
  exact `#428` failure shape (a `##` heading used as a question) leaves the test
  **GREEN**. It reads the snapshot, not the live tree. *This is the false-red
  mechanism, killed.*
- **B — a corrupted snapshot must fail it.** Writing the failure shape into the
  snapshot's `questions.md` makes `check_questions` ERROR and the test fails on
  `assert not rep.failed`. *The snapshot is the thing under test, not hollow.*

### Why the skill-tool reads staying live is correct

Three checks read the skill's own tool files from the module-global `SKILL_DIR`
rather than the passed target: `load_watch` (`SKILL_DIR/watch.py`),
`check_skill_version` (`SKILL_DIR/migrations/`), and `check_review_artifacts`
(`SKILL_DIR/review_artifact.py`). These are committed skill code, identical at
HEAD between snapshot and live, and no lane owns them. They cannot false-red
from data-file lane churn. Every **data** read goes through the passed `dw` /
`dw.parent`, which is the snapshot.

One caveat, recorded rather than hidden: `status.json` is gitignored, so it is
**absent** in the snapshot and the status checks degrade to WARN/silent — never
ERROR. The dogfood test no longer asserts about machine-local state, which is
correct: machine-local state is covered by `lint.py --target .` at the
quiet-tree gate, which is the brief's third option and where it belongs.

## The sibling surface (enumerated, 7 sites)

The brief asks for a count of the exposed surface, not one fixed test. Every
dogfood test in `test_lint.py` that reads the live tree shares the `#428`
defect. There are **7** sites; only the first false-redred tonight because it
runs the full check list and so is the most sensitive to a `Lane-owns:` sweep.

| # | site (test_lint.py) | reads | can false-red from lane churn? |
|---|---|---|---|
| 1 | `test_this_repo_passes_its_own_linter` (full `run_checks`) | whole `.dreamwork` tree | **yes — fixed (`1454717`)** |
| 2 | `test_this_repo_has_no_forgotten_folds` (`check_landed_asks`) | `questions.md` + ledger | yes — open-question/landing correlation drifts as lanes fold |
| 3 | `test_this_repo_maps_its_own_plans` (`check_doc_map_plans`) | `doc-map.md` + `docs/plans/` | yes — a lane adding a plan moves the enumeration |
| 4 | `test_this_repo_introduces_no_stale_artifacts` (`check_review_artifacts`) | `.dreamwork/review/` | yes — a lane landing an artifact changes staleness |
| 5 | `test_this_repo_passes_its_own_human_blocker_check` (`check_human_blocker`) | `tasks.md` + `questions.md` | yes — a `blocked-on: **human**` marker without a question is exactly what a mid-fold lane produces |
| 6 | `test_the_live_repo_is_dormant_not_broken` (`check_subdecisions`) | `tasks.md` + `questions.md` | lower risk today (zero declarations), but a lane folding a sub-decision entry mid-run would move it |
| 7 | `TestSelfCompletedOpen._real_ledger` (helper, not an assertion) | `tasks.md` | reads-only helper feeding fixtures; no direct false-red, but its callers share the ledger |

### Adoption rule

A dogfood test should adopt `frozen_tree` **iff** its verdict can be moved by a
file a concurrent lane owns. The three options the brief names map to the
site's risk:

- **snapshot** (the landed pattern): the test asserts "this repo passes its own
  linter" and the inputs are the repo's mutable data. Use the fixture. This is
  the right answer for sites 1–5.
- **skip while lanes are out** (`lint._live_lane_worktrees` already answers
  this): a test that genuinely cannot be made deterministic. If used, the skip
  reason must be **printed and visible** — a silent skip converts a false red
  into a silent pass, strictly worse. None of the 7 need this today.
- **move out of pytest** into the quiet-tree gate: a check that is only
  meaningful when no lane is running. `lint.py --target .` at the merge gate is
  that surface; the in-pytest dogfood tests are the busier surface.

Sites 2–5 are the next adoption batch. Each is a one-line change (`run(...)` →
`run(frozen_tree)` with the fixture arg), and each should gain its own
runtime-derived precondition (a non-empty file, a non-trivial parsed count) so
the snapshot cannot pass vacuously. Site 6 stays as-is until the sub-decision
marker is in use; site 7 is a helper.

## Why not retry, and why not tolerance

A retry hides the mechanism and preserves the false red for whoever runs it
next — explicitly forbidden by the brief. Widening the tolerance (e.g. only
failing if N checks error) is the same class of error as `#413`'s inverted
guard: it trades a loud wrong answer for a quiet one. The snapshot is the only
fix that keeps the assertion honest at full strength.

## Verification

- `python3 -m pytest test_lint.py -q -p no:randomly` — **328 passed**.
- `python3 lint.py --target .` — clean (0 errors; 1 warning, unchanged). This
  can itself false-red while lanes commit — see the brief's note; re-run alone
  before believing it.
- `git worktree list | grep frozen-head` after the run — clean (no orphans).

## Related

`#428` (this task), `#424` (the suite is one shared lock), `#461` (a guard
graded whatever held its port — the same *"the test measured somebody else's
state"* shape, one layer up), `#413` (a guard encoding a superseded contract —
the inverse failure mode, a silent green).
