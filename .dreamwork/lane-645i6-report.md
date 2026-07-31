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

---

# Re-landing 6b — the schema-v3 unit plus the pin it broke

This section is **appended**, not a replacement: the increment above was
reverted as `7270566e` because the merged-tree gate went red on
`test_chain_golden.py` — a file the original lane never touched — and this
re-dispatch restores it and fixes that one pin. The original verdict, proofs,
and DOGFOOD REPORT above are unchanged and stand.

## Verdict (re-landing)

**PASS.** The revert-of-the-revert restored the entire increment intact, the
golden pin was repinned to schema v3 **by hand from the contract** (a second
same-shape pin `GOLDEN_HASH_EVENT` was found and moved in lockstep), and a
red-proof shows the repinned pin is **not** a rubber stamp for migration
correctness — a broken migration still reds the frozen-v2 fixture tests while
the genesis pin stays green, which is the correct separation of invariants.

## git diff master --stat — proof the revert restored the increment

`git revert --no-edit 7270566e` (the reapply) plus the pin fix. The non-empty
diff is the load-bearing check: an empty diff would mean the restore brought
nothing back and everything after was built on an empty base.

```text
 .dreamwork/lane-645i6-report.md           | 215 ++++++++++++++++++++++
 dreamwork_db/migrate.py                   |  18 +-
 dreamwork_db/migrations/v003_questions.py | 120 ++++++++++++
 test_chain_golden.py                      |  18 +-
 test_dreamwork_db_migrate.py              | 293 ++++++++++++++++++++++++++++--
 test_ledger_store.py                      |   5 +-
 6 files changed, 645 insertions(+), 24 deletions(-)
```

The original increment's trap material survived the revert intact: the
"Direction 2 false-green" section above (the empty-table migration tautology
that passes when the fixture is already v3, closed by REFUSE BEFORE MIGRATION)
is present and unchanged. A revert-of-a-revert is exactly where a reader stops
checking, so this was read back rather than assumed.

## What went wrong: the rule is "find what PINS what you changed"

`test_chain_golden.py::test_genesis_hash_matches_recorded_literal` asserts a
hard-coded literal against `ledger_store.genesis_hash()`, and `genesis_hash()`
is `SHA-256("ud-dreamwork.task-ledger" + SCHEMA_VERSION)`. The increment set
`SCHEMA_VERSION = 3`, so the literal moved `25d2c583… → 2002431098ba…` and the
gate went red.

The generalisation, in my own words: **the dependency arrow points the wrong
way.** `migrate.py` sets `SCHEMA_VERSION`; it does not name `test_chain_golden.py`
or any golden literal. A golden pin *names the value*; the value's *producer is
oblivious to the pin*. So a call-graph search outward from the changed module —
callers of `migrate`, callers of `genesis_hash` — can never surface the pin,
because nothing in that direction references it. The only search that finds it
is a search for the *value*: grep for the literal, or for recorded hash
literals, or for `genesis_hash`/`GOLDEN_` symbols. That is why "find the
callers of what you changed" is necessary but not sufficient — the rule that
covers this is **"find what pins what you changed,"** and a pin is a reverse
dependency the producer does not declare.

## Search for other pins of the same shape

Searched the whole tree (excluding `.git/`) for: every recorded literal
(`25d2c583…`, `747e81af…`, `27840d6e…`, and the new `2002431098ba…`); and the
symbols/patterns `genesis_hash`, `GOLDEN_`, `golden`, `recorded.*hash`,
`hexdigest` across `*.py`/`*.md`.

Findings:

- **A second same-shape pin exists, in the same file:** `GOLDEN_HASH_EVENT`.
  Its test (`test_hash_event_matches_recorded_literal`) feeds `GOLDEN_GENESIS`
  as the `prev_hash` input, so its recorded digest *transitively* encodes the
  schema version through the genesis prev. When `GOLDEN_GENESIS` moved to v3,
  `hash_event(v3_genesis, canonical)` no longer matched the v2-prev literal —
  so this pin breaks for the same reason and was moved in lockstep
  (`27840d6e… → fd7a478b…`).
- `GOLDEN_CANON_SHA256` is **not** the same shape: it is a digest of the
  canonical event bytes, which do not include the schema version. Unaffected,
  and confirmed passing throughout.
- **No other executable pins exist in the tree.** The literal strings appear
  only in `test_chain_golden.py` (and in this lane's brief as prose).
  `dev/replay_events.py` imports and *uses* `genesis_hash` at runtime but pins
  no literal; the `#549`/`#460`/`#653` mentions in `handoffs.md` and docs are
  narrative, not assertions. "Nothing else" holds for the rest of the tree.

## Why the pin must stay a literal, not computed

This is the substantive judgement. A golden hash that is *computed* from the
same code that produces it — e.g. `GOLDEN_GENESIS = ledger_store.genesis_hash()`
— asserts `x == x` and cannot fail (#759: hold the SUBJECT fixed, vary the
INTERPRETER; here the subject and the interpreter collapse into one function).
Such a pin would pass green for *any* seed string, *any* schema version,
including a corrupt one, because it has no independent reference to disagree
with. It would catch exactly nothing.

The literal's entire value is that **a human chose it once, from the contract,
and a machine cannot silently re-choose it.** The literal is the only form that
can *disagree* with the producer. So the correct behaviour on a legitimate
version bump is that the test **goes red and a person updates it on purpose** —
which is exactly what happened at the merge gate, and it is the system working,
not failing. That red is worth a great deal: it is a tripwire that forces a
human to *acknowledge* the seed/format change, and the same tripwire catches the
illegitimate cases (an accidental seed-string edit, a swapped field, a dropped
part) that a computed pin would hide. The two new literals were therefore
written by hand from the contract one-liner
(`SHA-256(b'ud-dreamwork.task-ledger3')`), never by calling `genesis_hash()` —
the producer output was used only as a *cross-check* (`genesis matches
derivation: True`), never as the source of truth. Recompute comments were
bumped `task-ledger2 → task-ledger3` so a reviewer can re-derive without
reading the producer.

## Direction 1 red-proof — the repinned pin catches genesis drift

Injection (via `dev/redproof.py`): reverted `SCHEMA_VERSION` to `2` in
`dreamwork_db/migrate.py` — the faithful regression, identical in shape to the
incident that broke the gate. Ran the exact genesis node.

Discriminating failure (only the genesis node reds; the other four golden
nodes stay green because they consume literals, not `genesis_hash()`):

```text
>       assert ledger_store.genesis_hash() == GOLDEN_GENESIS
E       AssertionError: assert '25d2c583ffda...25cfa240fdc1a' == '2002431098ba...8d762958c159c'
1 failed, 4 passed in 0.18s
```

This is a genesis-seed mismatch, not a setup/migration failure. Restored;
`dev/redproof.py check` clean (see receipt below).

## Direction 2 — the pin is NOT a rubber stamp for migration correctness

The new direction-2: with the pin updated to v3, break the migration and ask
whether the suite stays green regardless. Injection: replaced the v3 DDL loop
body (`conn.execute(statement)`) with a no-op in
`dreamwork_db/migrations/v003_questions.py`, so `schema_version` still advances
to 3 but **no v3 tables are created**. Ran the full targeted suite.

Result — the golden pin stays **green**, but the frozen-v2 fixture tests go
**red twice**:

```text
FAILED test_dreamwork_db_migrate.py::... - column set: + set()  - {…id, title, body_markdown, status, …}
FAILED test_dreamwork_db_migrate.py::test_v3_constraints_bind_typed_links_decisions_and_messages - sqlite3.OperationalError: no such table: question
2 failed, 23 passed
```

So the suite does **not** stay green when the migration is broken. Updating the
pin to whatever `genesis_hash()` emits does **not** paper over a broken
migration, because `genesis_hash()` is a pure function of a *constant*
(`SCHEMA_VERSION` + the seed string) and is, by construction, independent of
whether any DDL ran. The genesis pin and the migration pin are **orthogonal**:
one invariant per pin. Migration correctness is owned by the frozen-v2 fixture
tests, which load their "before" from a subject the code under test did not
produce (#759) and assert the post-migration shape against it. The genesis pin
owns only the seed format, and a reviewer who updates its literal signs off on
exactly that — nothing more. This is the correct separation, and it is why
updating the literal here is honest rather than a rubber stamp.

## Red-proof restore/check receipt

```text
history: examined 2 commit(s) since 7270566e5055 (master) against 2 injected path(s); read 4 blob(s), 0 holding a recorded injection.
check: clean — 2 injection(s) registered, all restored and absent from the working tree and from this branch's commits:
  dreamwork_db/migrate.py (sha 1a01b5e70c95, hint: 'SCHEMA_VERSION = 2')
  dreamwork_db/migrations/v003_questions.py (sha 35d72bbc6810, hint: 'pass  # dir2: migration broken — no DDL executed')
```

## Verification (re-landing)

```text
python3 -m pytest test_chain_golden.py test_dreamwork_db_core.py test_no_raw_connect.py test_dreamwork_db_migrate.py test_ledger_store.py test_replay_events.py:
52 passed

python3 lint.py:
clean (5 warning(s))   # lane bar; the 5 are the gitignored-doesn't-travel set (tasks.md/status.json/ledger-checks/lessons near-dup)
```

`SCHEMA_VERSION = 3` confirmed restored after the direction-1 injection; the v3
DDL loop body confirmed restored after the direction-2 injection.

## Rebase outcome (re-landing)

Local `master` was `7270566e` at dispatch and had not moved when this lane
reported (`git rev-parse master` == merge-base == `7270566e`), so the rebase
was a no-op (`Current branch glm-645i6b is up to date`). The line-anchored
four-form conflict-marker scan (`grep -nE '^(<{7}|>{7}|>{7}|={7}$)'`, with the
`$` that only the `=` arm carries) found none. Branch adds two commits on
master: the reapply (`461b192a`) and the pin fix (`fa1e07ce`).

## Re-landing relied-on issue text

- `#759`: **"a proof must load its 'before' state from a source the code under
  test did not produce."** Both the migration proof (frozen v2 fixture) and the
  pin proof (literal derived from the contract, producer used only as
  cross-check) hold their subject independent of the producer. The direction-2
  finding is the direct application: `genesis_hash()` cannot witness migration
  correctness because it shares no state with the DDL.
- `#671`/`#136`: **"Zero entries now says `DID NOT REVIEW`…"** / **"present-
  but-unparseable is a fault and must look like one."** A literal that disagrees
  loudly (goes RED on a version bump) is the fault-that-looks-like-a-fault; a
  computed literal is the silent pass.
- `#349`/`#608`: **"Revert a deliberate RED injection with the inverse… never
  `git checkout`."** Both injections used `dev/redproof.py begin/restore/check`,
  lane-private snapshots, never `git checkout`.

## Re-landing DOGFOOD REPORT

1. The reverse-dependency hazard is not in the lane brief boilerplate's
   "named defect site" rule. That rule says *check the sibling constructs in the
   same unit* — but `test_chain_golden.py` is a *different unit* from
   `migrate.py`, and the dependency between them is one-directional (pin →
   producer). The brief head had to teach it inline. A standing rule worth
   adding: **when you change a value that seeds a hash (a schema version, a
   domain tag, a seed string), grep the tree for recorded hash literals and for
   the producer's symbol — call-graph reach cannot find a pin that names you.**
2. The `GOLDEN_HASH_EVENT` second-pin was found by *reading the test file's own
   data flow*, not by grepping for the schema version. The literal's comment did
   not flag the transitive dependency; it said only `prev=genesis`. A pin whose
   value is derived from another pin should say so in its comment, or the next
   bumper will move `GOLDEN_GENESIS` and be surprised by a second red. I added
   that note to the comment; future bumpers get one lockstep edit, not two
   discovered separately.
3. No friction with `dev/redproof.py` itself — `begin`/`restore`/`check` ran
   cleanly across two files, the `check` gate refused nothing, and the
   lane-private snapshot paths were distinct. The tool discharged the
   snapshot/restore and history-scan rules exactly as the brief describes.
