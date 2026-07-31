# Lane report — #645 increment 3 task read unit

## Verdict

COMPLETE for increment 3 only. All eight in-scope task-store reads now execute
inside `TaskRepository` through the increment-1 `StoreSpec.repositories` seam;
the existing module-level entry points remain thin compatibility facades and
their output, ordering, nulls, and id types are unchanged.

The lane rebased cleanly onto final base `c9c0976f` before this report. The
post-rebase implementation commits are:

- `a7111931` — `test(#645): freeze task read output before repository move`
- `6c0ff51d` — `feat(#645): move task reads behind TaskRepository`

## Decisions and precedent for increments 4–14

- `dreamwork_db/tasks.py` owns `TaskRepository` and the single
  `task_store_spec(path)` binding. Every READ facade opens
  `open_database(task_store_spec(...), access=Access.READ)`; no second handle
  or connection path was introduced.
- The repository returns the exact compatibility DTO shapes the facades
  already returned: lists/tuples/dicts with the same `int` versus `str` ids,
  nullable fields, sets, and deterministic order. It does not return
  `sqlite3.Row`. This is deliberate for this compatibility increment: moving
  shape conversion as well as SQL would make parity depend on every caller
  changing at once. Later new-domain repositories can introduce their designed
  frozen dataclasses without perturbing these established task facades.
- `ledger_parse.py`, `task_origins.py`, and the warning helper in
  `dev/ledger.py` keep their signatures and soft-failure behavior. They contain
  no task SQL and delegate to repository methods. This thin-wrapper pattern is
  the cheapest precedent for increment 4: move implementation behind the same
  repository, preserve adapter contracts, then remove facades only after their
  last callers migrate.
- READ specs intentionally need no initializer: core ignores initializers on
  READ handles. Increment 4 can add the already-existing migration initializer
  when it introduces WRITE bindings, without changing this read surface.

## Moved-read denominator and frozen captures

Moved: **8 / 8**. Captured before the move: **8 / 8**. Missing captures:
**0 / 8**.

1. `ledger_parse._read_meta_value`
2. `ledger_parse.store_entries`
3. `ledger_parse.store_records`
4. `ledger_parse.store_ids_by_state`
5. `ledger_parse.store_review_decisions`
6. `ledger_parse.store_series_raw`
7. `task_origins._store_origins`
8. `dev.ledger._store_incomplete_counts`

`test_task_repository_reads.py` was committed before the SQL move. Its fixture
has three tasks spanning open and landed states, headed and headless bodies,
null and non-null task fields, two ordered review rows, valid and invalid event
timestamps, extracted first-commit shas, and non-zero incomplete-data counts.
Every captured value is asserted non-empty/non-trivial before equality, and a
failure names the read and quotes both expected and actual rows.

Graph-augmented code search after the move found **0** raw `sqlite3.connect`
calls across `ledger_parse.py`, `task_origins.py`, the CLI warning path, and
`dreamwork_db/tasks.py`.

## Red-proof

Direction 1 snapshotted the committed fixed `dreamwork_db/tasks.py`, removed
the open-state `WHERE`, and ran the one eight-read parity witness. It failed at
the intended discriminating assertion:

> `AssertionError: ids_by_state parity differs:`
> `expected rows=(['1', '3'], ['2'])`
> `actual rows=(['1', '2', '3'], ['2'])`

The injected source was read back first. The fixed file was restored with
`cp` from the lane-private snapshot and verified byte-identical with `cmp`; the
witness then passed.

Direction 2 used the same broken repository against an all-open fixture. It
demonstrated the requested success-while-wrong case:

> `FALSE GREEN: ids_by_state parity passed on all-open fixture: expected=(['1', '2', '3'], []) actual=(['1', '2', '3'], []); repository is still wrong for any landed row`

This is why the committed fixture asserts both state partitions are exercised.
Its explicit `int`/`str` captures also bind the separate type-drift false-green.

Required final gate, verbatim after the rebase:

> `history: examined 2 commit(s) since c9c0976f3f28 (master) against 1 injected path(s); read 1 blob(s), 0 holding a recorded injection.`
> `check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits:`
> `  dreamwork_db/tasks.py (sha f6e6b7468c0a, hint: '"SELECT id FROM task ORDER BY id")]  # RED: open read includes landed')`

## Verification

Before movement, the newly frozen capture file collected **1** test and passed
against the unchanged loose-SQL implementation.

After implementation and again after rebasing, the requested files plus the
actual `ledger_parse` / `task_origins` coverage files collected **171** tests:

> `171 passed in 4.20s`

Command scope: `test_dreamwork_db_core.py`, `test_dreamwork_db_migrate.py`,
`test_ledger.py`, `test_ledger_cli.py`, `test_ledger_store.py`,
`test_task_repository_reads.py`, `test_ledger_dispatch.py`,
`test_task_origins.py`, and `test_ledger_warnings.py`, with `-n 2`.

`python3 lint.py` from the worktree reported:

> `clean (6 warning(s))`

There were no ERRORs. The six warnings are the expected worktree refusals and
baseline findings: the absent gitignored ledger/status, zero-examined
ledger-derived checks, the three answered questions without dates, and the
pre-existing lessons near-duplicate.

Both the changed worktree interpreter and unchanged main-checkout interpreter
linted the main checkout:

> `clean (2 warning(s))`

The two findings were identical: three known answered questions without dates
and the pre-existing lessons near-duplicate.

For fixed-subject real-path parity, one read-only SQLite backup of the live
ledger was made and both interpreters ran `dev/ledger.py list --json` and
`counts` against that same backup:

> `STABLE_COPY_LIST_IDENTICAL=true`
> `STABLE_COPY_COUNTS_IDENTICAL=true`
> `STABLE_COPY_COUNTS={"open": 168, "landed": 483, "total": 651}`

A separate read-only live smoke successfully read task `#645` as open. No live
ledger write, mutating live verb, browser guard, port bind, merge, or push was
performed.

## Explicitly not built

No task writes, other-store routing, schema v3, question/review repository,
question parser/import, CLI additions, dashboard cutover, UI work, or source
deletion. Those remain increments 4–14.

## DOGFOOD REPORT

The brief's verification placeholder says to add whatever covers
`ledger_parse`, but this checkout has no `test_ledger_parse.py`; naming that
natural file makes pytest collect zero tests and exit 5 for the whole command.
The real coverage lives in `test_ledger_dispatch.py` and
`test_ledger_warnings.py`. Future briefs should name those files explicitly so
a lane does not turn a missing path into a misleading “no tests ran” result.

The frozen-subject correction carried from increment 2 worked exactly as
intended. The live store advanced while other lanes landed, but one read-only
backup made old/new interpreter parity stable and attributable. The
`dev/redproof.py` lane-private snapshot and final history scan also worked
without friction.
