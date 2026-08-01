# Suite baseline — 2026-08-02

## Verdict

The repository was **red** at `a23dd6a01ed77ac91aba577e2e28e5deb30f1dc2`.
The complete pytest population ran: **3192 passed / 22 failed / 0 skipped /
0 errors**, **3214 collected**. The browser-guard portion of `just test` was
**NOT RUN**, so this is not presented as a completed full-`just test` result.
That omission cannot make the repository's state unknown or green: 22 pytest
failures already make it red.

The first hand-off check rebased this lane onto local `master`, which had
advanced by seven commits:

```console
$ git rev-parse master; git rev-list --count HEAD..master; git rebase master
b74baaf2c4b1a85cfffe75b8d30c27d784675b5b
7
Successfully rebased and updated refs/heads/cx-919baseline.
```

Master then advanced another five commits before final hand-off, so the lane
rebased again. Final ancestry was:

```console
$ git rebase master; git merge-base master HEAD; git rev-parse master
Successfully rebased and updated refs/heads/cx-919baseline.
985298352f7e8fa5f9301e905aac6ec819b9d27b
985298352f7e8fa5f9301e905aac6ec819b9d27b
```

The measurement is therefore still valid for its recorded SHA
`a23dd6a01ed77ac91aba577e2e28e5deb30f1dc2`, but it does **not** describe the
final rebased `985298352f7e8fa5f9301e905aac6ec819b9d27b` tree. I did not manufacture
a current count by carrying the older result across that boundary, and I did
not add a second resource-heavy suite run while the browser fleet remained
live.

The measurement finished at `2026-08-02T04:04:53+10:00`. That timestamp and
SHA came from:

```console
$ date --iso-8601=seconds; git rev-parse HEAD
2026-08-02T04:04:53+10:00
a23dd6a01ed77ac91aba577e2e28e5deb30f1dc2
```

## Concurrency boundary

I ran the required advisory before the suite:

```console
$ python3 dev/concurrent_tests.py
concurrent tests: 3 other pytest suites; 32 browser/guard processes (advisory)
```

By the time the pytest recipe itself started, the pytest contention had drained,
but the browser contention had not:

```console
python3 dev/concurrent_tests.py
concurrent tests: no other pytest suites; 32 browser/guard processes (advisory)
```

I therefore ran the complete non-browser portion with thread-producing numeric
libraries capped at two threads, and did not bind any guard or hub port:

```console
$ env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 just pytest -ra
...
22 failed, 3192 passed, 1 warning, 65 subtests passed in 552.10s (0:09:12)
error: Recipe `pytest` failed on line 17 with exit code 1
```

Pytest reports every non-zero outcome category in that terminal summary.
`skipped` and `errors` were absent, hence both are zero; `3192 + 22 = 3214`,
so the result covers the complete collected population rather than a selection.
The warning and subtest figures are not test outcomes and are shown only to
preserve the command's complete summary.

The browser exclusion count was derived from the canonical defaults in
`justfile`, without starting a server or browser:

```console
$ python3 - <<'PY'
from pathlib import Path
import re
s = Path("justfile").read_text()
default = re.search(r'^    DEFAULT_GUARDS="([^"]+)"$', s, re.M).group(1).split()
hub = re.search(r'^    HUB_GUARDS=\$\{DREAMWORK_HUB_GUARDS-"([^"]+)"\}$', s, re.M).group(1).split()
print(f"default browser guards: {len(default)}")
print(f"default hub guards: {len(hub)}")
print(f"total browser guard programs excluded: {len(default) + len(hub)}")
PY
default browser guards: 92
default hub guards: 2
total browser guard programs excluded: 94
```

Thus **94 browser guard programs were excluded**: 92 watch guards and 2 hub
guards. Their status is **NOT RUN**, not passed, failed, or skipped. I also
confirmed the prohibited live surfaces were listening and did not touch them:

```console
$ ss -tln | awk 'NR==1 || $4 ~ /:(3988[0-9]|3989[0-9]|35110|35113)$/'
State  Recv-Q Send-Q               Local Address:Port  Peer Address:Port
LISTEN 0      5                        127.0.0.1:35110      0.0.0.0:*
LISTEN 0      5                        127.0.0.1:35113      0.0.0.0:*
```

## Every failure

The failing pytest node IDs, copied from the command's short summary, are:

1. `test_deploy_state.py::test_ship_siblings_and_assert_importable_cli_against_real_head`
2. `test_dreamwork_db_hierarchy.py::test_v005_preserves_tasks_members_triggers_and_the_id_sequence`
3. `test_dreamwork_db_hierarchy.py::test_downgrade_refuses_to_discard_nesting_or_dependencies`
4. `test_dreamwork_db_migrate.py::test_frozen_v2_store_migrates_through_current_and_reports_zero_legacy_rows`
5. `test_dreamwork_db_migrate.py::test_ladder_declares_the_single_ordered_path_to_current`
6. `test_event_genesis.py::test_chain_built_under_older_schema_keeps_literal_root_and_verifies`
7. `test_event_genesis.py::test_tamper_names_the_changed_ordinal[detail]`
8. `test_event_genesis.py::test_tamper_names_the_changed_ordinal[actor]`
9. `test_event_genesis.py::test_tamper_names_the_changed_ordinal[at]`
10. `test_event_genesis.py::test_forged_self_rooted_chain_is_refused_at_ordinal_one`
11. `test_event_genesis.py::test_verifier_refuses_missing_meta_instead_of_trusting_ordinal_one`
12. `test_lane_scratch.py::TestCli::test_prints_the_path_and_creates_it`
13. `test_lane_scratch.py::TestCli::test_measure_names_the_one_filesystem_measurement_location`
14. `test_lane_status.py::test_sweep_reports_armed_injections_prominently`
15. `test_mcp_screenshot_root.py::test_safe_staging_root_two_lanes_differ`
16. `test_reanchor_citations.py::test_each_reviewed_anchor_line_contains_the_named_evidence`
17. `test_reanchor_citations.py::test_unanticipated_watch_insertion_keeps_lines_derived`
18. `test_reconcile_submissions.py::test_submission_routes_match_watch`
19. `test_task_repository_reads.py::test_all_eight_task_store_reads_match_the_nontrivial_pre_move_capture`
20. `test_user_events_cli.py::test_submissions_is_never_load_bearing_in_the_journal_or_cli`
21. `test_user_events_http.py::E2Shadow::test_a_new_route_would_fail_this_test_not_slip_past`
22. `test_user_events_http.py::E2Shadow::test_every_write_route_commits_a_receipt_and_changes_nothing_else`

This inventory shows why `#918` was evidence of missing measurement, not an
inventory of the red state: both reanchor failures are present, alongside 20
other failures.

## Re-runnable baseline design

There is no trustworthy existing record from which to answer “when did the
full suite last pass, and at what SHA?” The honest current answer is
**UNKNOWN — no completed full-suite pass is recorded**. Git history cannot
reconstruct an execution that nobody recorded.

The smallest truthful design is a wrapper plus one machine-readable receipt,
not a merge gate:

- `dev/suite_baseline.py run` writes an atomic `RUNNING` attempt before it
  invokes `just test`, then atomically finalises the receipt after the command.
  An interrupted process therefore leaves `RUNNING`, never the prior green as
  the current attempt.
- `.dreamwork/suite-baseline.json` stores `schema_version`, `started_at`,
  `finished_at`, starting and ending SHA, clean-tree state, command, overall
  state, and one record per component: pytest, lint, watch guards, and hub
  guards. Each component carries `state`, its executed and expected
  denominators, and its outcome counts. The receipt also stores
  `last_full_pass`, initially `null`; only a completed eligible pass replaces
  it.
- A pass is eligible for `last_full_pass` only when the tree was clean, HEAD
  did not move, pytest collection completed, every collected pytest case has
  an outcome with zero failures/errors, lint completed cleanly, and every
  registered browser/hub guard both ran and judged with zero failures. A dirty
  or moving tree remains useful evidence but cannot be labelled “at SHA”.
- A read-only status/tick formatter prints both `last_attempt` and
  `last_full_pass`. It never substitutes the latter when the former is absent,
  running, incomplete, or red. This is periodic instrumentation; it does not
  run from `land-lane` and does not gate merges.

The three required states would be visibly different:

```text
full-suite last attempt: PASS at <sha> — pytest 3214/3214 outcomes; lint 1/1; browser guards 94/94 ran and judged
full-suite last attempt: NOT RUN — no attempt receipt; last full pass: <sha-or-UNKNOWN>
full-suite last attempt: INCOMPLETE at <sha> — pytest 40/3214 collected, collection errors 1; lint NOT RUN; browser guards 0/94 NOT RUN; last full pass: <sha-or-UNKNOWN>
```

The displayed numbers above are illustrative schema examples, not claims about
an execution. In real output every denominator is read from that attempt's
receipt. `PASS` is impossible unless every required component has a known,
complete denominator and judged outcomes equal that denominator. `NOT RUN` and
`INCOMPLETE` are first-class states, not aliases for the last known result.

I did **not** build this design. Although the concepts are small, a truthful
implementation crosses a runner, a parsed receipt format, and a tick/status
reader, and it needs both mandated red-proof directions. This lane owns only
this document; building across those surfaces would widen ownership while
several related lanes are live.

## Gate wording

The exact replacement wording proposed for `dev/land_lane.py` is:

```text
gate-coverage: 4 of 4 declared lane gates passed: <gate names>; full repo suite NOT RUN (test coverage was limited to lane-named tests plus changed-file-derived repo-wide guards)
```

This preserves the true declared-gate statement while attaching the missing
scope at the point where the stronger claim is otherwise inferred. I did not
edit `dev/land_lane.py`, as required.

## Named tests and deliberately unbuilt work

Named tests: **none — measurement and design only**. The measurement command
was the complete pytest run shown above. No production or test code was
changed; no browser guard, hub guard, `just test`, or deploy command was run.
I deliberately did not propose a per-merge full-suite gate: the existing cost
decision stands.
