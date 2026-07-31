# Lane report — #645 increment 2 migration unit

## Verdict

COMPLETE for increment 2 only. The legacy task-store schema, lookup seeds, and
v1→v2 review migration now live under `dreamwork_db/` as versioned modules.
The behavior witnesses were committed before the move, and the implementation
was rebased onto final base `c3e01017` before handoff.

Post-rebase commits:

- `24750140` — `test(#645): pin legacy migration behavior`
- `b9d3a020` — `feat(#645): move ledger migration ladder into version modules`

## Decisions

- The caller asks for task-store initialization/migration explicitly by passing
  `dreamwork_db.migrate.initialize_legacy_store` as its `StoreSpec.initializer`.
  Generic `open_database` does not assume every store shares this ladder. This
  reduces the increment-1 seam to the ladder's own entry point while preserving
  the legacy facade's current implicit v1→v2 open behavior.
- Versions are per-version modules (`v001_legacy.py`, `v002_review.py`) bound by
  an ordered tuple of `Migration(source_version, target_version, upgrade)`.
- A newer `meta.schema_version` remains fail-closed with the exact legacy
  `ledger_store.SchemaVersionError` type and unchanged message. That retained
  type is now also a `dreamwork_db.SchemaMismatch`, so new package consumers can
  catch the principled database error without breaking existing callers.

## What changed

- `dreamwork_db/migrations/v001_legacy.py` owns the unchanged base schema,
  closed vocabularies, and idempotent lookup-table seeds.
- `dreamwork_db/migrations/v002_review.py` owns the current review-decision DDL
  and the intact empty-table-only v1→v2 reshaping step.
- `dreamwork_db/migrate.py` owns `SCHEMA_VERSION`, the ordered fail-closed
  runner, meta bootstrap, and the schema/seed transaction entry point.
- `ledger_store.py` re-exports the existing constants and exception name, and
  delegates initialization directly to the package ladder. It contains no
  schema string, migration runner, version step, or initializer wrapper.
- `test_dreamwork_db_migrate.py` builds its v1 fixture from the DDL at
  `7e35c6d5^`, not from the moved current-schema constants. It witnesses
  migration shape/version, idempotent reopen, future-version refusal, exact
  exception types, seed refusal, established reopen, and ladder order.
- `test_dreamwork_db_core.py` now proves `_connect` closes its connection when
  an initializer raises a `BaseException` (`KeyboardInterrupt`).

No schema v3, repositories, CLI commands, question work, other-store routing,
or other landing-sequence increment was added.

## Compatibility properties

1. A historical v1 review table migrates to the exact v2 columns and writes
   schema version 2.
2. Reopening that migrated store is idempotent.
3. Stored version 3 is refused with exact type `SchemaVersionError` and message
   text naming `schema_version 3 > supported 2`.
4. A new unseeded store still raises exact type `SeedError`; an established
   store reopens without `ledger_text` or `seed_next_id`.
5. The non-empty v1 decision-table refusal and rollback witnesses in
   `test_ledger_store.py` remain green.
6. `_connect` closes on initializer `BaseException`.

## Red-proof

Direction 1 snapshotted the committed fixed `dreamwork_db/migrate.py` through
the lane-private `dev/redproof.py` store, changed the v1→v2 step to a no-op,
and ran the named historical-fixture test. It failed at the intended assertion:

> `AssertionError: schema_version 1 must run the v1->v2 review migration exactly; got columns ['artifact', 'decided_at', 'decision', 'question_id']`

The injected line was read back before the test. `redproof.py restore` copied
the snapshot back and verified byte identity; the named test then passed.

Direction 2 ran the same broken ladder against an alleged v1 fixture made from
the moved code's own `v002_review.SCHEMA_SQL`. It printed:

> `FALSE GREEN: skipped v1->v2 step passed because the alleged v1 fixture used v002_review.SCHEMA_SQL`

This is the tautology trap the committed historical fixture prevents.

The required pre-report gate was:

> `history: examined 2 commit(s) since c3e01017e50e (master) against 1 injected path(s); read 1 blob(s), 0 holding a recorded injection.`
> `check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits:`
> `  dreamwork_db/migrate.py (sha 4cbe4b08032e, hint: 'Migration(1, 2, lambda _conn: None),  # RED: skip the v1->v2 step')`

## Verification

Before adding the witnesses, the requested existing files collected and ran:

> `124 passed in 3.70s`

After implementation and again after rebasing onto `master`, the requested
files plus `test_dreamwork_db_migrate.py` collected and ran:

> `129 passed in 3.24s`

`python3 lint.py` after rebase:

> `clean (6 warning(s))`

There were no ERRORs. Each warning matches the worktree baseline: three known
answered questions without dates; absent gitignored ledger/status state; the
explicit zero-examined ledger checks; and the pre-existing lessons duplicate.

For fixed-subject real-path parity, a read-only SQLite backup of the live store
was made into a scratch directory. The unchanged main-checkout interpreter and
this worktree interpreter read that same backup:

> `STABLE_COPY_LIST_IDENTICAL=true`
> `STABLE_COPY_COUNTS_IDENTICAL=true`
> `STABLE_COPY_COUNTS={"open": 168, "landed": 482}`

A separate read-only live smoke check successfully read task #645 as open. No
live ledger write or mutating ledger verb was run.

## DOGFOOD REPORT

The brief repeatedly says `user_version`, while the behavior to preserve is
actually `meta.schema_version`; SQLite `PRAGMA user_version` is not the ladder's
version fact here. The tests and implementation follow the real public behavior,
but future briefs should name `meta.schema_version` so a lane does not add or
test a second version channel by accident.

The design's eventual rule says ordinary opens require an exact schema and
migrations are explicit CLI operations, while this increment also requires the
existing implicit v1→v2 open behavior to remain unchanged and forbids CLI work.
Keeping that compatibility behind the ladder-owned initializer is the only
increment-2 shape satisfying both constraints; the later CLI increment will
need to make the explicit-operation cutover deliberately rather than treating
it as already complete.

`dev/redproof.py` worked cleanly: `begin` guaranteed the fixed committed bytes
were the snapshot, `restore` used `cp` and verified identity, and `check` named
both the injected blob and the scanned branch history.
