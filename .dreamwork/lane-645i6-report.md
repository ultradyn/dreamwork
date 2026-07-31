# Lane 645 increment 6 report — schema v3

## Verdict

**PASS, with the empty-table limit stated first.** The proof can establish that
the frozen subject really starts at schema v2, has none of the v3 tables, and
has exactly **0 legacy `review_decision` rows examined**; that the one ordered
v2→v3 step creates the specified questions/reviews/issues/typed-link shape and
records `meta.schema_version = 3`; and that a refusal rolls the whole step back.

It **cannot** establish preservation, classification, or id mapping for even
one legacy decision row. An empty source contains no artifact/title mapping and
no `related`/`blocking` fact to preserve. That is why a non-empty v2
`review_decision` table refuses with its row count and the facts it cannot
classify, rather than treating an empty-table proof as evidence about data.

## What changed

- Added `dreamwork_db/migrations/v003_questions.py` with the dark `question`,
  `question_message`, `review_file`, `issue`, and `review_link` tables and their
  checks/indexes.
- Advanced the existing and only migration ladder in
  `dreamwork_db/migrate.py` from v2 to v3. No CLI, initializer, import, facade,
  read dispatch, or write dispatch was added.
- New stores and v2 stores both reach v3 through that same ladder. A malformed
  `meta.schema_version` now says it **could not determine** the version; it does
  not render like a successful migration. An already-current store is silent.
- Kept the empty v2 `review_decision` compatibility table temporarily. The
  pre-watermark `/decide` caller still writes that exact shape; dropping it in
  this increment would make the promised dark schema break a live route. The
  v3 step requires it to be empty at migration time and prepares the typed
  target schema without dispatching live traffic to it.
- Added frozen-v2 migration, atomic refusal, current-store silence, malformed
  version, future-version, schema/constraint, and false-green tests. Updated the
  existing v1→v2 caller assertion to expect the ordered ladder to continue to
  v3.

Post-rebase commits:

- `e68224a72e68257ee0be761b28955e501c0d2f17` — schema and migration tests
  (`Migration: dreamwork_db/migrations/v003_questions.py`)
- `855fb95134e559a2bf9cbada0482a5563b9f208a` — caller fallout
- `5c99ed5b460808486b9c64a057d0c3b08b7558a2` — tautology rejection

## Frozen source and migration proof

The before state is a literal v2 fixture copied from the live shape at the
dispatch base `bc7aab6b8e6f7e48ec74340af98e9c06a17dd995`. It is not built from
`v002_review.SCHEMA_SQL` or from the initializer being tested. Runtime
preconditions require:

- `meta.schema_version == "2"`;
- the exact five-column live v2 `review_decision` shape;
- none of the five v3 domain tables; and
- exactly 0 decision rows, reported rather than omitted.

The migration is invoked through `dreamwork_db.core.open_database()` with the
existing `initialize_legacy_store` initializer. Raw connections appear only in
tests to construct/corrupt frozen fixtures and inspect results.

## Direction 1 red-proof

Injection: removed the `review_link` check requiring exactly one of `task_id`,
`issue_id`, or `question_id`.

The exact schema-constraint node went red at the intended first assertion:

```text
with pytest.raises(sqlite3.IntegrityError):
E   Failed: DID NOT RAISE <class 'sqlite3.IntegrityError'>
```

That is discriminating: an invalid link with no target was accepted. It is not
a red caused by setup, migration failure, or a different constraint.

Restore/check receipt after the final rebase:

```text
history: examined 3 commit(s) since d8820fbc41f4 (master) against 1 injected path(s); read 3 blob(s), 0 holding a recorded injection.
check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits
```

## Direction 2 false-green

Constructed the exact tautology: start with the frozen v2 fixture, execute the
v3 DDL under test into it while leaving `meta.schema_version = 2`, and then
consider a no-op migration. A post-only table/column check would pass because
the fixture was already v3.

This lane's check decides **REFUSE BEFORE MIGRATION** with:

```text
fixture labelled v2 already contains v3 tables; a no-op migration would make the proof false-green
```

The exact direction-2 test passes because it expects that refusal. The
remaining honest false-green is intrinsic to this increment: with zero legacy
rows, no test can prove a real decision's artifact/title was resolved to stable
review/question ids or that its missing `link_kind` was classified. The
non-empty fixture therefore must and does refuse; data-bearing migration proof
belongs to the later import/verify unit.

## Call graph and caller fallout

Search and graph tracing found that the migration entry is reached through
both `ledger_store.open_store` and `dreamwork_db.tasks.task_store_spec`, not
only the two changed migration files. Production callers include
`dev/ledger.py`, `dev/replay_events.py`, `ledger_parse.py`, `task_origins.py`,
and `watch.py`; tests additionally exercise ledger CLI/read/write, replay,
status, lint, and dashboard review-decision paths.

Verification therefore included caller fallout rather than only touched files:

```text
pre-rebase broad caller run:
1185 passed, 65 subtests passed

post-rebase schema and caller run:
602 passed, 65 subtests passed

post-rebase lint regressions rechecked by exact node:
4 passed

required raw-connect guard, separately:
1 passed

python3 lint.py:
clean (5 warning(s))
```

Files/nodes covered were `test_dreamwork_db_migrate.py`,
`test_ledger_store.py`, `test_dreamwork_db_core.py`, `test_ledger_write.py`,
`test_task_repository_reads.py`, `test_watch.py`, `test_lint.py`,
`test_ledger_cli.py`, `test_status_derive.py`, `test_replay_events.py`,
`test_ledger_dispatch.py`, `test_ledger_warnings.py`, and
`test_no_raw_connect.py`. The v3 production module contains no
`sqlite3.connect`; the guard assertion would fail by naming that new path if
one were added outside the sanctioned `dreamwork_db/core.py` door.

One broad post-rebase run temporarily reported 4 failures in brief-corpus
dogfood while master was between brief-persistence commits. Master advanced
again before the final history rewrite; all four exact nodes then passed and
worktree-local lint returned the required 5-warning bar. This is reported
rather than omitted because the first result did not judge this schema.

## What a premature live import would break

Shipping a live import on this increment would create two authorities with no
watermark dispatch: existing readers would continue serving `questions.md`
while imported DB rows silently drifted. Existing `/answer` and `/comment`
writers would continue changing Markdown, and `/decide` would continue writing
the compatibility `review_decision` table rather than `review_link`. No
lossless parser/source-span manifest, idempotency/conflict policy, production
repository manifest comparison, or live denominators exist yet.

In particular, a decision written after the store reaches v3 can legitimately
make the compatibility table non-empty. The later import/verify unit inherits
the duty to classify or loudly refuse that row; it must not infer a link kind
or treat this increment's zero-row proof as covering it.

## Relied-on issue text

- `#645`: **“all our DB access should be like this — a principled, modular,
  reusable Python DB API.”** This is why the new schema uses the existing core
  and migration ladder.
- `#651`: **“a guard's message must name a mode the guard can actually detect,
  and the way to know is to construct that mode and watch it fail.”** The link
  target injection failed at the named integrity assertion.
- `#755`: **“the check fires two warnings on the healthy live file”** was the
  recorded unacceptable gap; current-store reopen is explicitly silent.
- `#671`: **“Zero entries now says `DID NOT REVIEW` rather than ‘nothing to
  review’.”** The proof states 0 legacy rows examined and limits its verdict.
- `#136`: **“present-but-unparseable is a fault and must look like one.”** A
  non-integer schema version is a
  typed refusal distinct from a healthy current store.
- `#702`: **“Nothing connects them and nothing complains when 'lanes' is
  populated and 'dreamers' is empty.”** The applicable rule is to expose the
  unclassifiable gap; non-empty legacy decisions name the missing kind/id facts.
- `#440`: **“so: a single supported way to fold an entry.”** Applied at the DB
  seam: the existing ordered initializer remains the single migration path.
- `#759`: **“one read-only SQLite backup of the live store as a FROZEN subject,
  then the unchanged main-checkout interpreter and the modified worktree
  interpreter both run against that same snapshot.”** The natural equivalent
  used here is the frozen v2 fixture, held independent of migrating code.

## Rebase outcome

The supplied base SHA was verified as both `HEAD` and the merge-base at
dispatch. Local master moved while the lane ran. The branch rebased cleanly,
without hand resolution, onto final observed master
`d8820fbc41f4938984e0f34db249b16c89d77476`; the tracked dispatch brief copies
were byte-identical to the lane's untracked copies before checkout. The
line-anchored four-form conflict-marker scan found none.

## DOGFOOD REPORT

Two findings:

1. The code graph's generic migration-directory exclusion omitted
   `dreamwork_db/migrations/`, so `search_graph` could not inventory the new
   migration unit even after indexing. `get_code_snippet` covered the runner,
   but the excluded version modules required direct reading. A repository whose
   main architecture is a migration ladder should not exclude its own migration
   package by basename.
2. The design says `review_decision` is “replaced,” while the same design says
   every increment preserves pre-watermark behaviour and this brief forbids
   live dispatch. The call graph exposes the conflict: dropping the table now
   breaks the still-live `/decide` writer. This lane retained the empty
   compatibility table and made the dark typed target, recording the later
   import duty explicitly. Future briefs should state that temporary
   compatibility decision instead of making a lane infer it from two opposing
   sentences.

No live ledger, `questions.md`, `status.json`, ports, browser guards, or
coordinator-owned hand-off file were touched.
