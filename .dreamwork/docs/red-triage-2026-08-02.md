# Master-red triage — 2026-08-02

## Measurement boundary

This classification describes `439034feab04407341dd4e5249217dcbc240993d`.
The named 12-file set collected 194 tests and finished **19 failed / 175
passed**.  The concurrency advisory immediately before the run reported no
other pytest suites and 32 browser/guard processes; this run started no browser
or server fleet.

The two citation-anchor failures in the older baseline are gone.  Three
failures not forecast by the task remain in the measured population: two in
`test_lane_scratch.py` and one in `test_mcp_screenshot_root.py`.  They are
classified here rather than silently excluded.

## Verdict: seven distinct causes

### 1. Detached deploys no longer satisfy lint's corpus-root precondition — (b), 1 failure

- `test_deploy_state.py::test_ship_siblings_and_assert_importable_cli_against_real_head`

This is a genuine behavioural regression.  The staged snapshot imports, but
dies before serving: `lint: refusing detached corpus root <staging-dir> —
expected SKILL.md beside lint.py`.  Commit `3cc9b0e6603239acb8eb3cfe490ab0e071f2909c`
added that fail-closed import-time precondition on 2026-08-01; the deploy
closure still ships Python imports and data siblings but not the corpus anchor.
The deployment contract is to boot from the detached staged directory, so the
code/closure must be repaired.  Weakening the boot proof would hide a dark
dashboard.

### 2. Four schema assertions are pinned to pre-v9 reality — (a), 4 failures

- `test_dreamwork_db_hierarchy.py::test_v005_preserves_tasks_members_triggers_and_the_id_sequence`
- `test_dreamwork_db_hierarchy.py::test_downgrade_refuses_to_discard_nesting_or_dependencies`
- `test_dreamwork_db_migrate.py::test_frozen_v2_store_migrates_through_current_and_reports_zero_legacy_rows`
- `test_dreamwork_db_migrate.py::test_ladder_declares_the_single_ordered_path_to_current`

Commit `a058cbc0627bb63e19f59a736a4ca6a8870ee37f` intentionally introduced schema
v9 and `goal_claim.bypassed_by`.  The tests still spell version `8`, enumerate
the ladder only through `(7, 8)`, or enumerate the old `goal_claim` columns.
The behaviours under test—migration to current, an unbroken unit-step ladder,
and a refused downgrade leaving the version unchanged—remain valid.  Their
oracles should derive current version, adjacency, and before/after invariants
from authorities independent of the operation being checked, rather than
receiving another manual v9 bump.  The explicit public column contract needs a
separate judgement: retain an independent contract if exact columns are the
behaviour, otherwise derive the v9 addition from the migration's observable
result; do not compare a schema query to itself.

### 3. A partial v5 event fixture invokes every later migration — (a), 6 failures

- `test_event_genesis.py::test_chain_built_under_older_schema_keeps_literal_root_and_verifies`
- `test_event_genesis.py::test_tamper_names_the_changed_ordinal[detail]`
- `test_event_genesis.py::test_tamper_names_the_changed_ordinal[actor]`
- `test_event_genesis.py::test_tamper_names_the_changed_ordinal[at]`
- `test_event_genesis.py::test_forged_self_rooted_chain_is_refused_at_ordinal_one`
- `test_event_genesis.py::test_verifier_refuses_missing_meta_instead_of_trusting_ordinal_one`

All six fail before reaching their genesis assertion.  `_frozen_v5_chain`
creates only `meta` and `task_event`, while `_migrate_v5` calls the canonical
initializer, which now continues through v8 and tries to alter the absent
`task_group` table.  The fixture was sufficient only while v6 was current.
This is one stale fixture seam, not six event-chain regressions.  The repair
should exercise the v5-to-v6 behaviour it claims to test, or construct a
complete independently frozen v5 store if the intended property is migration
all the way to current.  Adding whichever table the next migration happens to
request would merely move the expiry point.

### 4. Three assertions encode the obsolete pre-launch-id path depth — (c), 3 failures

- `test_lane_scratch.py::TestCli::test_prints_the_path_and_creates_it`
- `test_lane_scratch.py::TestCli::test_measure_names_the_one_filesystem_measurement_location`
- `test_mcp_screenshot_root.py::test_safe_staging_root_two_lanes_differ`

Commit `d6df8d98df4dfb66c80dd3591f072cced38bdce4` intentionally inserted a
per-launch identity segment so two launches in one worktree cannot share
snapshots.  Assertions ending in `/master/snap`, `/master/measure`, or walking
exactly three parents to `SCRATCH_ROOT` describe the old presentation, not the
safety property.  Retire those exact-depth assertions.  Replacement coverage
should assert containment under `SCRATCH_ROOT`, the requested leaf name, and
separation for distinct launch identities; the new implementation already has
direct tests for the latter.

### 5. Independent write-route populations were maintained by hand — (a), 3 failures

- `test_reconcile_submissions.py::test_submission_routes_match_watch`
- `test_user_events_http.py::E2Shadow::test_a_new_route_would_fail_this_test_not_slip_past`
- `test_user_events_http.py::E2Shadow::test_every_write_route_commits_a_receipt_and_changes_nothing_else`

`/settings` entered the dispatch in `7ba4c2708bb078bda6307fb2b6c33dc45fedf128`;
`/goals` entered it in `86ad91d80ab595ce65bd73c756edb1976add3cb6`.
`SUBMISSION_ROUTES`, the `13` route count, and `run_all_routes` remained at the
old population.  These are not three behavioural regressions: they are three
alarms correctly reporting one inventory drift.  The HTTP oracle must compare
the production dispatch with the routes the harness actually POSTed, recorded
at the request seam; deriving both sides from the dispatch would pass forever.
The two new routes also need real payloads and observable postconditions.  The
reconciliation tool needs its own independent derivation or an explicit
coverage contract; copying two more strings is another expiring snapshot.

### 6. A frozen refactor snapshot now constrains an intentionally enlarged read API — (c), 1 failure

- `test_task_repository_reads.py::test_all_eight_task_store_reads_match_the_nontrivial_pre_move_capture`

Commit `d1a0889ca9842cfebee7130de25116419582afb9` intentionally added `next_up`
to task records.  The frozen pre-move capture has already served its one-time
refactor parity purpose; repinning it would convert a historical snapshot into
a hand-maintained duplicate of the live API.  Retire the whole-capture equality
with an argument, preserving focused tests for the stable fields and for
`next_up` semantics where those behaviours matter.

### 7. A lexical guard confuses unrelated prose with a dependency — (c), 1 failure

- `test_user_events_cli.py::test_submissions_is_never_load_bearing_in_the_journal_or_cli`

Commit `01c3b2e3fb50ee2dfa8e8d4773530dc7fe845f8a` added a comment containing
“command submissions”; no code reads `submissions.log`.  A raw substring scan
cannot establish data flow: it false-fails on prose and would false-pass an
aliased dependency.  Retire this source-shape assertion rather than deforming
the comment.  If the load-bearing boundary needs an executable check, exercise
journal/CLI behaviour with the witness file absent or unreadable.

## Ownership after this classification commit

This lane will take only `test_user_events_http.py`, the smallest coherent
group: cause 5's two HTTP failures.  It will not touch
`test_reconcile_submissions.py` or any file from causes 1–4, 6, or 7.  The
classification document itself is `.dreamwork/docs/red-triage-2026-08-02.md`;
`doc-map.md` is deliberately untouched, so the missing-row warning is expected.

The HTTP expectation will be derived from the actual paths observed by the
test harness's HTTP request method, while the subject remains watch's production
dispatch table.  Those are independent sources.  A route added only to the
dispatch therefore appears as missing coverage; a route merely named in a test
without a real POST cannot enter the observed set.

## Post-fix, post-rebase recount

After rebasing onto master `681f39cb479e12b2e14d715538ba12953aedd437`,
branch `eeb8fafdffcd2629c2e260abf451bb13738d5e6c` ran the same 12-file set:
**17 failed / 177 passed**, 194 collected.  The two owned
`test_user_events_http.py` failures are green; all 17 failures in the other
owned-nothing test files remain.  The seven-cause classification therefore
still describes the current tree: cause 5 now has one remaining failure in
`test_reconcile_submissions.py`, while causes 1–4, 6, and 7 are unchanged.
