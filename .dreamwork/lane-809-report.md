# #809 review lens E — can these tests actually fail?

## Verdict

The green suite is not uniformly vacuity-resistant. In a bounded, reproducible
sample I demonstrated two mutations that survive the complete relevant test
file, plus one hollow individual count assertion whose siblings compensate for
it. I also obtained eight clean, discriminating kills and one red for the wrong
reason. This is evidence of real false-green density, not an estimate of how
many of the 2,818 node ids at the audited snapshot are vacuous. Rebase added
25 node ids afterwards; those are explicitly outside the sample.

The strongest result is the split:

- **Suite-level relevant-file survivors:** 2 distinct mutations.
- **Individual-node survivor caught by siblings:** 1 distinct mutation.
- **Discriminating kills:** 8 distinct mutations.
- **Non-discriminating red:** 1 distinct mutation; counted as neither a kill
  nor a survivor.

There were 12 distinct registered mutations and 14 executions because I re-ran
the two strongest survivors against their whole relevant files. No mutation is
committed.

## Sampling method

The method was fixed before reading candidates:

1. Collect the real runner population, not `def test_` text. The audited
   pre-rebase branch collected **2,818 node ids** (the brief's 2,806 is a moving
   historical snapshot), representing **2,678 source test functions** across
   **87 tracked test files**. Parameter expansion accounts for the other 140
   node ids. After the required rebase, collection was **2,843**; the 25 new
   node ids were verified as collected but were not retrospectively sampled.
2. Run an AST census over every collected source function for five structural
   tells: no local oracle, only `is not None`, count-only assertions,
   status/return-code-only assertions, and an exception handler whose body is
   only pass/return/continue/break. This classified all 2,678 functions with no
   parse failures. It produced 6 / 5 / 25 / 18 / 13 candidates respectively;
   these sets overlap and are hypotheses, not findings.
3. Divide collected node ids into three predeclared strata:
   **meta/guard/tooling** (1,226), **runtime/state/other** (1,502), and
   **plugins/install** (90). Within each stratum sort by
   `sha256("7f978b35|" + node_id)` and read the first 25. This is a balanced
   density probe, not a proportional sample. I read the test body, fixtures and
   every assertion/oracle for **75 deterministic node ids**.
4. Spend mutation depth on 12 production seams. Nine came from the deterministic
   read sample; three came from the fixed structural-candidate lists. Each
   injection named a production path/symbol or executable guard module. Restore
   was exclusively through `dev/redproof.py`.
5. For a focused survivor, expand to its relevant file/cohort before calling it
   a suite-level gap. That upgraded two survivors and downgraded the reach-count
   survivor to an individual-node gap compensated by siblings.

This method tests the defect-history hypothesis rather than assuming it. Two of
the three survivors are in guard/tooling and one is in ordinary question-import
state, so the historical concentration partially held but is not exclusive.
The sample is too small and deliberately balanced to estimate relative density.

## Demonstrated false-greens

### 1. Guard corpus floor accepts a broken member

**Node id:**
`test_guard_argv.py::test_outdir_sweep_count`

**Appears to check:** every outdir-shaped browser guard was converted to the
shared `outdir(process.argv)` parser; its docstring says a revert shrinks the
sweep and should fail.

**Actually checks:** at least `CENSUS == 84` files contain the literal import
`from './outdir.mjs'`. The live population is 94 importers, so ten named guards
may lose the import before the floor fires. It checks a count, not membership
or executability.

**Production mutation:** in `dev/capture/wisp.mjs`, delete
`import { outdir } from './outdir.mjs';` while retaining
`const OUT = outdir(process.argv)`. The executable guard now calls an undefined
identifier before it can judge anything.

**Observed false-green:** the named node passed, and then the complete relevant
file passed: `10 passed in 1.03s`. I did not run `wisp.mjs` or any browser guard,
per the brief's load-safety prohibition.

This is the count/membership failure from #702 in a new live instance.

### 2. Import count survives swapped question identities

**Node id:**
`test_dreamwork_db_import.py::TestDatelessEntries::test_dateless_entries_imported`

**Appears to check:** the three dateless Answered entries are imported as
answered questions.

**Actually checks:** `len([q for q in snapshot if q.status == "answered"]) == 3`.
It never asserts which questions occupy that set.

**Production mutation:** in
`dreamwork_db/question_parse.py::_build_entry`, force ordinal 1 (the Open
`#90001`) to `answered` and ordinal 2 (Answered `#90002`) to `unanswered`.
The set is wrong but its cardinality remains three. The injected manifest read:

```text
(1, Open, answered, #90001)
(2, Answered, unanswered, #90002)
(3, Answered, answered, #90003)
(4, Answered, answered, #90004)
```

**Observed false-green:** the named node passed, and the complete relevant
import file also passed: `34 passed in 0.43s`.

### 3. The examined-count assertion does not prove examination

**Node id:**
`test_ledger.py::test_reach_counts_every_branch_examined_so_did_not_run_is_distinguishable`

**Appears to check:** `reach()` examined every branch, so a zero result can be
distinguished from a check that did not run.

**Actually checks:** the returned count equals `len(branch_marks)`, the input's
already-known length. It does not bind processing of any mark.

**Production mutation:** in `dev/ledger.py::reach`, return
`(len(branch_marks), 0, 0, [])` immediately, before processing a branch.

**Observed false-green:** the named node passed (`1 passed`). This is not a
suite-level hole: `test_ledger.py -k reach` then produced 7 failures, 3 passes.
Those siblings bind rows, aliases and liveness. The finding is that this node's
headline claim is hollow, not that the reach subsystem is wholly unguarded.

## Mutations that were killed

These eight produced the predicted assertion failure and therefore showed real
failure power in this sample:

- `test_ledger_cli.py::test_sweep_that_read_no_entries_refuses_to_call_it_nothing_to_review`
  — deleting `sweep_text`'s zero-entry refusal failed on the literal false
  all-clear: `a sweep that read no entries must not report nothing to review`.
- `test_deploy_state.py::test_assert_is_server_requires_both_markers`
  — removing the `GENERATION` member from `assert_is_server`'s missing set
  failed with `DID NOT RAISE ValueError`.
- `test_dispatch_lane.py::test_literal_command_substitution_refuses_and_names_missing_contract`
  — deleting the missing-contract arm failed because the different inbox
  refusal could not satisfy the expected missing-contract message.
- `test_lint.py::TestStatusAgreesWithLedger::test_an_empty_current_while_agents_claim_ids_warns`
  — disabling the owned-task warning failed with `rows == []`.
- `plugins/ud-dreamwork-hooks/tests/test_install.py::TestApply::test_apply_refuses_to_clobber_without_force`
  — deleting the no-force refusal changed exit 2 to exit 0.
- `plugins/ud-dreamwork-hooks/tests/test_posttooluse_lint.py::TestLedgerLint::test_missing_lint_py_reports_error_exit_zero`
  — reporting missing lint as `ok:true` failed at the verdict assertion.
- `plugins/ud-dreamwork-matt-pocock-skills/tests/test_tracker_adapter.py::TestT1TaskSeamNeverOpensLedger::test_create_never_opens_tasks_md_or_the_store`
  — adding a production `tasks.md` read failed with the exact opened path.
- `plugins/ud-dreamwork-worktrees/tests/test_occupied.py::TestOccupiedLiveProcess::test_clear_once_process_exits`
  — deleting the clear exit by returning 1 unconditionally failed at the
  post-exit verdict.

One further mutation was red but **not counted as a discriminating kill**:
disabling `_handle_posture`'s delivery closed-set branch made
`test_watch.py::TestPosture::test_post_delivery_rejects_unknown` fail at
`500 != 202`. `write_posture` independently rejected the value, so the red
proves defence in depth, not that the named handler branch was reached. Calling
that a clean red-proof would repeat the defect this lens is auditing.

## Read-only suspicions (not demonstrated)

- `plugins/ud-dreamwork-hooks/tests/test_precompact.py::TestPreCompactFocus::test_appends_across_invocations`
  asserts only that three invocations produce three records. It does not assert
  trigger membership or order. Other tests may bind those fields; I did not
  mutate this seam, so this remains a suspicion.
- `test_dreamwork_db_import.py::TestBasicImport::test_question_count_matches_manifest`
  is count-only. The demonstrated state-swap shows this family deserves a
  membership check, but I did not inject against this specific node.

No other item from the 75-node manual sample is reported as suspicious. Several
static hits were false alarms after helper expansion: no-local-oracle tests used
`self.fail`, no-exception-as-oracle, or assertion-bearing helpers; non-`None`
tests often tested regex presence precisely; swallowing-looking `except` blocks
were cleanup paths, not swallowed test failures.

## Collection and skip reachability

- At the audit snapshot, all 2,678 tracked source test functions appeared in
  the collected node-id population; zero source functions were unreachable.
- There are no `skip`, `skipif`, or `xfail` decorators.
- There are eight conditional `pytest.skip` call sites. Expanding their helper
  callers yielded 17 potentially-skipping node ids. A targeted `-rs` run passed
  all 17 with **zero skips** on this checkout.
- `just pytest --collect-only -q | tail -3` was run exactly as requested, but
  `just` adds its own `-q`, so the double-quiet pipeline hid the total and left
  only per-file tail rows. A raw single-quiet collection supplied the auditable
  total: `2818 tests collected`.

This says every tracked test is collected and the known conditional skips are
live here. It does not prove the full suite would execute every branch on every
platform.

## Coverage statement

I did **not** inspect 2,818 tests individually, still less the post-rebase 2,843,
and this report must not be read as a suite-wide mutation score.

- Structural AST census: 2,678/2,678 collected source test functions.
- Deterministic manual read: 75 node ids — 25/1,226 meta/guard/tooling,
  25/1,502 runtime/state/other, 25/90 plugin/install.
- Mutation-tested: 12 distinct production seams/registrations; 14 executions
  after the two whole-file confirmations.
- Whole relevant-file survivor checks: `test_guard_argv.py` (10 tests) and
  `test_dreamwork_db_import.py` (34 tests).
- Sibling-cohort compensation check: `test_ledger.py -k reach` (7 failed,
  3 passed under the injection).
- Conditional-skip execution probe: 17 node ids, all passed, zero skipped.
- Not examined manually: the other 2,743 audit-snapshot node ids plus all 25
  post-rebase additions (2,768 of the current 2,843), most browser/UI behavior,
  most database transitions, most migration-history cases, and cross-file
  compensating coverage outside the two expanded cohorts.
- Browser guards were deliberately **not run**, as required. No ports 35110 or
  35113 were touched.

The ratio `3 focused survivors / 12 mutations` is a property of this risk-biased,
balanced sample. It must not be extrapolated to `~704 vacuous tests` or any other
whole-suite number.

## Selected lessons and issue evidence

The relied-on lessons were resolved by content, not by the dispatch's shorthand:

- **A check that declines to run must say so; a bare `return` turns "cannot
  check" into "nothing to fix".** This is the common #611/#671 principle.
- **A guard's message must name a mode the guard can actually detect, and the
  way to know is to construct that mode and watch it fail.** This is #651's
  exact lesson title.
- **A check that fires on a healthy input is worse than no check — its message
  names a failure on every run, so the reader learns to dismiss the failure it
  exists to catch.** This is #786's exact lesson title and kept the static
  candidate list from becoming a noisy pseudo-verdict.
- **Two guard-repair shapes from the d56a3c2a fallout.** Its named-membership
  rule is the positive replacement for count-only corpus floors.

Relied-on ledger lines, quoted after opening every cited issue:

- **#671:** `the count is real ... the "nothing to review" is false, and the
  two together read as a positive all-clear.`
- **#611:** `a check that did not run must say so rather than be silently
  absent, because absence reads as a pass.`
- **#702:** `the lint check is count-only so lanes=[X]+dreamers=[Y] of equal
  length reads OK.`
- **#651:** `A guard's message must name a mode the guard can actually detect,
  and the way to know is to construct that mode and watch it fail.`
- **#786:** `A check that fires on a healthy input is worse than no check.`
- **#795:** editing a test expectation `proves only that an intentionally false
  assertion is false`.
- **#796:** worktree default was `219 tracked / 219 on disk — equal, so NO
  warning fires` while the main checkout exposed the missing corpus.
- **#798:** a revision with required strings only in a comment and an `echo`
  still returned `PASS -- historical guard-execution gate confirmed a judged
  pass`.

## Verification and safety

- `python3 dev/repo_wide_guards.py list` returned the two intended node ids.
- Worktree lint WARN rows were the known five: absent worktree ledger,
  absent `status.json`, related-marker examined zero, one human-gated lesson
  near-duplicate, and seven ledger checks examined nothing.
- Main-subject lint had exactly the one human-gated lesson near-duplicate WARN.
- Browser guards were not run.
- Final `dev/redproof.py check` output is recorded in the completion report.

## DOGFOOD REPORT

1. The task head says `python3 dev/ledger.py get 809`, while the standing brief
   correctly says the bare form refuses in a worktree and prescribes the
   absolute `--ledger` form. I ran both: the first spent a round trip producing
   #667's refusal, the second returned #809. The head should paste only the
   working form.
2. The required `just pytest --collect-only -q | tail -3` double-applies `-q`
   because the recipe already supplies it. On this branch its last three lines
   do not contain the total, so the command does not achieve the count its
   placement implies. `just pytest --collect-only | tail -3` or raw
   `python3 -m pytest --collect-only -q | tail -3` does.
3. The brief's 2,806 count had already moved to 2,818 before this lane started,
   then to 2,843 at the required rebase. The brief itself warns against moving
   counts, and the sampling method handled this by recording each collection
   snapshot rather than silently retargeting the sample.
4. `redproof.py` behaved well across repeated injections and caught every
   restore. The final check remained the useful safety net the brief promised.
5. One targeted pytest invocation that combined explicit node ids from three
   plugin test directories failed during collection: their tests use bare
   `from conftest import ...`, and pytest resolved the hooks tests against the
   matt-pocock plugin's `conftest.py`. Each plugin group passed when run in its
   own pytest process (2 + 1 + 1 tests). The repo's targeted-test guidance
   should warn that cross-plugin node lists are not safely composable.
