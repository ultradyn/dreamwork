# Lane report — #645 increment 4 task write unit

## Verdict

COMPLETE for increment 4 only. All seven named commands now execute behind
`TaskRepository`; `ledger_write.py` is a SQL-free compatibility facade and each
facade owns exactly one default `DatabaseHandle.transaction()`.

Nothing from the seven-command denominator remains:

1. `file_task`
2. `land_task`
3. `note_task`
4. `reprioritise_task`
5. `unblock_task`
6. `retitle_task`
7. `record_review_decision`

The lane rebased cleanly onto final base `bfd7b2f604e1` before final
verification. Post-rebase commits before this report are:

- `957991f3` — `feat(#645): move task writes behind repository`
- `eafd4f15` — `test(#645): prove task write rollback and false greens`
- `0e87d8d8` — `test(#645): migrate task writer fixtures to repository handles`

The relied-on line from the opened task is: **“all our DB access should be like
this — a principled, modular, reusable Python DB API.”** Increment 4 advances
that standing rule without starting another landing-sequence item.

## What changed

- `dreamwork_db/tasks.py` now owns write validation, task/review row mutations,
  task-event appends, write error types, and timestamp defaults. Its event helper
  still delegates to `ledger_store.append_chained_event`, preserving the one
  canonical hash construction used by live writes and replay.
- `task_store_spec` supplies `migrate.initialize_legacy_store` for WRITE opens.
  READ behavior is unchanged because core deliberately ignores initializers on
  READ handles.
- `ledger_write.py` preserves all seven public signatures and error exports but
  contains no SQL. Each function opens one default transaction and calls one
  repository method.
- The six task CLI adapters in `dev/ledger.py` open the one WRITE handle through
  `task_store_spec`; they retain their existing stdout, stderr, and exit-code
  behavior.
- The dashboard `/decide` writer uses the same handle/repository path. Its
  conflict response remains unchanged.
- Existing direct writer fixtures were migrated to repository-bearing handles;
  raw SQLite remains only as test-side observation/corruption machinery.

`note_task` deliberately writes no task event, and `record_review_decision` is
not a task and also writes no task event. The other five commands atomically
commit their row/body change and chained event together.

## Transaction and compatibility proof

The exact pre-move implementation was loaded from
`e72674be:ledger_write.py`. Two independently seeded stores then received all
seven commands with fixed inputs and timestamps: one through that historical
module, one through the new repository path. Captured `task`, `task_event`, and
`review_decision` rows were asserted non-empty before equality and matched
exactly, including allocated id, nulls, bodies, details, previous hashes, and
event hashes.

A separate mixed-chain fixture filed through the pre-move implementation and
landed through the new repository. It held exactly one old and one new event,
and `verify_task_event_chain` returned no findings. Thus the proof does not
construct its “before” chain with the moved code.

For `file`, `land`, `reprioritise`, `unblock`, and `retitle`, a parametrized
test raises a custom `BaseException` from `_append_chained_event` after the row
mutation. Each assertion compares the full pre/post task, event, and review
state and names the command plus both quoted states on failure. All five stores
were byte-for-byte unchanged at the captured SQL-row level. A facade protocol
test additionally proves all seven commands enter exactly one default
transaction and make exactly one repository call; core's existing transaction
test binds that default to `BEGIN IMMEDIATE`, commit on success, and rollback on
every `BaseException`.

## Red-proof

### Direction 1 — moved command defect

The committed fixed `dreamwork_db/tasks.py` was snapshotted with
`dev/redproof.py`. I removed `file`'s chained-event append while leaving the
task insert and return value intact. The historical parity witness failed at
the intended discriminating assertion:

> `AssertionError: events parity differs after seven commands:`
>
> `expected store state=[(700, '2026-08-01T00:00:00Z', 'filed_from_command', None, 'open', 'fixture', '', ...), ...]`
>
> `actual store state=[(700, '2026-08-01T00:01:00Z', 'reprioritised', 'open', 'open', 'fixture', 'priority reason', ...), ...]`

The failure therefore names the missing filed event and quotes the divergent
store states; it is not a count-only red. `redproof.py restore` restored and
verified the fixed bytes, and the named parity test passed afterwards.

### Direction 2 — success while wrong

The committed false-green construction replaces the repository event append
with a no-op, then files a task. A field-only checker passes because the task
row exists with the returned id. The chain verifier also returns `[]` because
the empty event chain verifies against itself. The store is nevertheless wrong:
the filed task has zero events. The pre-move parity witness catches this exact
case, while the rollback fixtures catch the separate partial-commit case.

The mandatory `why` contracts and live priority-band validation remain exercised
through the repository path by the existing writer and CLI tests; validation
was not left solely in a presentation layer.

Required final red-proof gate, verbatim:

> `history: examined 3 commit(s) since bfd7b2f604e1 (master) against 1 injected path(s); read 3 blob(s), 0 holding a recorded injection.`
>
> `check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits:`
>
> `  dreamwork_db/tasks.py (sha b12efb48a1bd, hint: '# RED: deliberately drop the filed event while retaining the task row.')`

## Verification

Requested files before implementation: **177 tests collected and passed**.

Requested files after implementation and after rebase: **186 tests collected**;
all passed with `-n 2`:

`test_ledger_write.py`, `test_ledger.py`, `test_ledger_cli.py`,
`test_ledger_dispatch.py`, `test_ledger_warnings.py`, `test_ledger_store.py`,
`test_dreamwork_db_core.py`, `test_dreamwork_db_migrate.py`, and
`test_task_repository_reads.py`.

The direct caller/fixture fallout set also passed with `-n 2`:
`test_status_derive.py`, `test_replay_events.py`, `test_lint.py`, and
`test_watch.py`. No browser guard ran and no port was bound by this lane.

`python3 lint.py` from the rebased worktree:

> `clean (6 warning(s))`

There were no ERRORs. The warnings are the expected worktree findings: three
answered questions without dates; absent gitignored ledger/status state;
zero-examined ledger-derived checks; and the pre-existing lessons
near-duplicate.

Both the rebased worktree interpreter and unchanged main-checkout interpreter
linted the main checkout with identical findings:

> `clean (2 warning(s))`

One read-only backup froze the live subject. Both interpreters read that same
backup through `dev/ledger.py list --json` and `counts`:

> `STABLE_COPY_LIST_IDENTICAL=true`
>
> `STABLE_COPY_COUNTS_IDENTICAL=true`
>
> `open ids:   165`
>
> `landed ids: 488`

A separate raw live read reported the same 165 open / 488 landed as context
only. No live ledger write, mutating live verb, `BEGIN IMMEDIATE` on the live
store, status/questions write, browser guard, port bind, merge, push, or `attn`
call occurred.

## Explicitly not built

No other-store routing, schema v3, question/review schema work, parser/import,
new CLI question verbs, dashboard question cutover, UX work, or source deletion.
Those remain increments 5–14.

## DOGFOOD REPORT

The brief's `Free:` list omitted `watch.py`, but one of its mandatory seven
commands is `record_review_decision`, whose live production caller is the
dashboard `/decide` handler. Leaving that caller on `ledger_store.open_store`
would make a required command fail at runtime; migrating the small handler was
necessary to complete the stated denominator. Future briefs should either list
the live caller as free or explicitly require a compatibility adapter that can
preserve it without creating a second handle path.

Likewise, the named verification command did not include four existing files
that construct stores through the production write facades:
`test_status_derive.py`, `test_replay_events.py`, `test_lint.py`, and
`test_watch.py`. They needed mechanical handle migration and would have failed
the coordinator's merged-tree gate despite the prescribed files being green.
Naming the caller-fallout set in the brief would make the lane bar complete.

The transaction paragraph says each of the seven commands combines “the row
change and its chained event,” but `note_task` and `record_review_decision`
deliberately have no task event by the pre-existing domain boundary. I followed
the actual contract: exactly one transaction for all seven, plus post-row/
pre-event rollback proof for the five event-producing commands. This was an
ambiguity, not an unflagged conflict with `briefs/boilerplate.md`; I found no
other unflagged boilerplate conflict.
