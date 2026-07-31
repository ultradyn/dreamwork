# Lane report — #645 increment 1 core connection unit

## Verdict

COMPLETE for increment 1 only. Commit `d7240f95` (post-rebase) adds the
stdlib-only `dreamwork_db` connection/unit-of-work package, keeps the legacy
ledger facade behavior, and leaves the migration/repository/question/CLI work
for later increments exactly as the design sequences it.

Rebase: the lane began at `8561238f`; local `master` advanced twice while the
lane ran. The two lane commits rebased cleanly onto final base `792e5f90`
before handoff. No conflicts occurred.

## What changed

- `dreamwork_db/core.py` now owns path opening, parent durability, SQLite
  connection policy, READ snapshots, WRITE transactions, repository binding,
  and typed API errors. `StoreSpec` carries the file path, repository factories,
  the 5 s timeout, and a temporary initializer seam for pre-migration stores.
- `dreamwork_db/__init__.py` exports `Access`, `StoreSpec`, `open_database`, the
  public handle, and `NotFound`, `Conflict`, `ValidationError`, `Busy`, and
  `SchemaMismatch`.
- READ uses an absolute `file:...?...mode=ro` URI, `query_only=ON`,
  `foreign_keys=ON`, `busy_timeout=5000`, and one deferred transaction for the
  handle lifetime (`core.py:261-282`, `core.py:306-317`).
- WRITE opens in autocommit, applies WAL, deliberately transitions
  `synchronous=NORMAL` to `FULL`, enables foreign keys and the timeout, then
  requires repository SQL to occur inside `transaction()`; the default is
  `BEGIN IMMEDIATE`, with commit on success and rollback on every exception
  (`core.py:138-170`, `core.py:273-284`).
- The public handle has no connection field: state lives outside it in a weak
  map, it has no `__dict__`, is final, and exposes only repositories plus
  `access`, `path`, and `transaction()` (`core.py:111-170`, `core.py:204-229`).
  This enforces the requested ordinary attribute/subclass/`__dict__` paths.
  It is not a Python security boundary: code deliberately importing private
  module state, or a badly written repository that publishes its private
  session, can still pierce encapsulation. The supported surface does not.
- `ledger_store.open_store` is now a compatibility facade over the core's one
  internal connection primitive (`ledger_store.py:619-663`). Its schema and
  seed behavior remain where they were; the temporary initializer preserves
  the old bootstrap/migration transaction (`ledger_store.py:604-616`). The
  old parent/pragmas/connect implementation was removed from `ledger_store`.

## Existing facade inventory and compatibility

Before editing, `open_store` accepted the database file path directly,
converted it with `Path(path)`, created/fsynced the parent, opened with
`isolation_level=None`, applied WAL / NORMAL→FULL / 5000 ms timeout / foreign
keys, ran schema and v1→v2 bootstrap in a deferred transaction, and returned an
autocommit-capable `LedgerStore` whose `.conn` remains observable. New stores
still require `ledger_text` or `seed_next_id`; established stores reopen
without either; schema and seed exceptions retain their existing public types.

Production callers found before the change were the six task-changing CLI
verbs, CLI groom, replay, and the dashboard review-decision write. Read helpers
reach the same facade indirectly. Those callers still receive the legacy
`LedgerStore` and therefore have no observable API change in this increment.
Moving their SQL behind repositories is intentionally later work.

The delegation test records the core call and names failures for the exact
legacy properties: WRITE access, `isolation_level is None`,
`foreign_keys == 1`, WAL, FULL (`2`), and 5000 ms timeout.

## Red-proof

Direction 1 used the required lane-private `dev/redproof.py` protocol on the
committed fixed `dreamwork_db/core.py`. I changed the core line to
`PRAGMA foreign_keys=OFF` and ran the facade delegation test. It failed at the
intended assertion, not scaffolding:

> `AssertionError: legacy facade delegated with wrong foreign_keys pragma: 0, expected 1`

Restore verified the fixed file byte-for-byte against the snapshot. Final gate:

> `check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits`

Direction 2 attempted all four requested success-while-wrong shapes against
scratch stores:

- READ write: an actual `INSERT` raises SQLite `readonly`; it does not merely
  inspect a flag.
- Isolation: a second handle sees only committed rows while the first writer's
  transaction remains open; a long-lived READ snapshot continues seeing
  generation N after another handle commits N+1, while a new READ sees N+1.
- Rollback: a row is inserted and then a real exception is raised inside the
  context manager; reopening proves only the pre-transaction row exists.
- Encapsulation: `.conn`, `.execute`, `__dict__`, `dir()` discovery and a
  subclass escape were attempted. None reaches raw SQL through the supported
  handle. The non-security-boundary limitation above remains stated plainly.

No open false-green was found among those cases. The private-module/repository
trust limitation is the honest remaining escape and is not claimed closed.

## Verification

Before implementation:

> `collected 145 items`  
> `145 passed in 2.95s`

After implementation and again after rebase, using exactly the requested files
plus `test_dreamwork_db_core.py`:

> `collected 153 items`  
> `153 passed in 2.93s`

`python3 lint.py` after rebase:

> `clean (6 warning(s))`

Those are the expected worktree warnings: absent gitignored ledger/status
state, zero-examined ledger-derived checks, and the pre-existing lessons
near-duplicate. There were no ERRORs.

The literal live production check was run with this worktree's interpreter
before and after. Before:

> `warnings: 169 open tasks · 5 unanswered questions · 248 untyped`  
> `open ids:   169`  
> `landed ids: 476`

After:

> `warnings: 168 open tasks · 5 unanswered questions · 248 untyped`  
> `open ids:   168`  
> `landed ids: 478`

The output was therefore **not identical**. Inspection showed concurrent live
ledger changes during the lane: tasks 752 and 755 moved open→landed and new task
757 appeared; task 645 remained open. This lane never wrote or took a write
lock against the live store.

To distinguish that live-state race from delegation drift, I used SQLite's
read-only backup mechanism to make one scratch snapshot, then ran the unchanged
main-checkout interpreter and this modified worktree interpreter against that
same snapshot. Results:

> `STABLE_COPY_LIST_IDENTICAL=true`  
> `STABLE_COPY_COUNTS_IDENTICAL=true`

Both reported 168 open / 478 landed and the same task 645 line. This is the
stable-subject production-path parity proof; the requested literal live
before/after result is reported above rather than falsely called identical.

## Explicitly not built

No migration package or ordered ladder; no migration behavior changes; no task,
question, review, or journal repository modules; no schema v3; no question
parser/import/cutover; no CLI additions; no dashboard dispatch or UI changes;
no other production `sqlite3.connect` migration; no source-file deletion. In
particular, `ledger_store`'s existing schema/migration SQL remains behind the
temporary `StoreSpec.initializer` until increment 2 moves it intact.

## Out of scope

The legacy facade still exposes `.conn` because its current callers, replay,
groom, and tests use it. Removing that is a later repository/caller migration,
not compatible delegation. The new public handle does not expose it.

## DOGFOOD REPORT

The brief's demand that two reads of a shared live ledger be byte-identical is
not satisfiable while the coordinator is allowed to land/file tasks during the
lane. That happened here: two entries landed and one was filed, independently
of this code. The useful acceptance shape is both readings **plus** an old/new
interpreter comparison against one read-only SQLite backup; that preserves the
real-path check without confusing legitimate concurrent state change with API
drift. The brief should state that fallback explicitly.

`dev/redproof.py` worked well: its private snapshot, recorded sabotage hint,
history scan, and final clean gate made the deliberate FK defect unambiguous.
No other tooling or boilerplate friction affected the increment.
