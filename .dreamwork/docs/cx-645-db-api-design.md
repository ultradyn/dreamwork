# #645 database API design — one store door, questions first

## Decision

Build a stdlib-only `dreamwork_db` package around the existing
`.dreamwork/ledger.sqlite3`, make the task ledger, questions, reviews and the
user-event journal consume its connection/transaction/migration primitives,
and keep `dev/ledger.py` as the one CLI adapter over those repositories.
Questions are the first new domain consumer; they are not the boundary of the
API.

Delete `.dreamwork/questions.md` after cutover. Do not keep a question
projection or a five-line shim. The immutable source remains reachable as the
git blob recorded in the database's cutover receipt, while all live reads and
writes go through the API. A stale reader must fail because its source is gone,
not confidently parse a projection that contains 0 or 40% of the real record.

This explicitly **supersedes** the coordinator-only writer policy. The new
policy is not “SQLite makes it safe”; it is:

1. every write enters through one repository API;
2. each command owns one `BEGIN IMMEDIATE` transaction;
3. append operations insert rows rather than rewrite a container;
4. state changes are compare-and-swap transitions on a question id and
   revision; and
5. WAL, `foreign_keys=ON`, `synchronous=FULL` and a 5 s busy timeout are
   applied on every connection.

If a dashboard POST and CLI command arrive together, SQLite lets one writer
hold the reserved lock and makes the other wait. The second command then sees
the first command's committed state. Two comments both append; two different
answers are both retained; a stale retitle/fold fails with a typed conflict
instead of overwriting. Journal `client_action_id` still prevents an HTTP
retry from becoming a second intended command.

## Measured domain — 2026-08-01

The measurements used the worktree copy and the coordinator's live main copy;
`cmp` found them identical. The file also matched its HEAD git blob
`3866dfb75a6318ce1cc61ce407f66dee00f4b0ef` at measurement time. These are a
snapshot, not acceptance constants: the implementation must derive them again
under the cutover lock.

### Questions

| Fact | Measured result |
|---|---:|
| UTF-8 source | 257,370 bytes / 252,946 characters / 3,571 lines |
| structural question heads classified | 72 / 72 |
| Open section | 5 / 72, all 5 unanswered |
| Open but answered-awaiting-fold | 0 / 5 Open |
| Answered section | 67 / 72 |
| Answered entries with a parsed resolution date | 64 / 67 |
| Answered entries with no parsed resolution date | 3 / 67 |
| hard-wrapped titles | 31 / 72 |
| multi-paragraph bodies | 72 / 72 |
| blank bodies | 0 / 72 |
| body characters | 189,972 total: 10,858 Open + 179,114 Answered |
| timestamped contributions | 113 / 113: 87 human + 26 loop |
| duplicate titles now | 0 / 72 |
| entry heads outside `## Open` / `## Answered` | 0 / 72 |

The three Answered entries whose `answered_at()` is null are #572, #613 and
#614. They are not malformed questions and must not be dropped: section
membership says they are answered, while the missing date is an honest
nullable field. This is why state is a column and not inferred from a
resolution sentence in prose.

The actual source grammar is richer than “title plus answer”:

```text
- **[P1|P2|P3 · ][date [time] — ]title, possibly hard-wrapped**
  arbitrary multi-paragraph Markdown body
  - **Note (human|loop, timestamp):** a wrapped contribution
  - **Answer (via watch, timestamp):** a wrapped contribution
```

The section supplies state today. Body prose may carry sub-decisions, paths,
code blocks and fold notes. Contributions have an author, timestamp, kind and
source order. The database model must carry all of those; an `answered` word
in body text is never authoritative.

The parser census found **0 / 72 unclassifiable structural heads**. That is a
reported result, not an omitted bucket. The importer must always print an
`unclassified N / source-heads` section and list every source span in it; a
non-empty bucket refuses import.

### Review files and existing associations

`.dreamwork/review/` contains 33 / 33 served root-level HTML artifacts, 21 / 21
HTML authoring sources under `src/`, 3 / 3 evidence files, and one root-level
non-HTML exemptions file. Only the 33 served HTML artifacts become
`review_file` rows.

There is no machine-readable task/question link to migrate:

- 0 / 33 artifacts have a live `review_decision` row in the current store.
- 15 / 33 filenames begin with a task-looking number (12 unique numbers), but
  that is a naming convention, not a relation.
- 31 / 33 artifacts mention `task #N` in prose.
- 12 / 33 mention `questions.md` in prose.
- 20 / 33 carry live `dreamwork-review-ask` metadata, 1 / 33 carries an exempt
  ask marker, and 12 / 33 carry no ask marker. The marker says whether a page
  makes an ask; it does not identify the question.

The importer registers all 33 files and **does not infer links** from names or
prose. It prints the 15 filename candidates and 31 prose candidates for later
explicit `reviews link` commands. If a live `review_decision` row appears
before implementation, its artifact and title must each match exactly one
registered review/question, and the operator must supply `related` or
`blocking`; the old row has no kind, so guessing one would fabricate data.

### Current read/write surface

The question migration has ten concrete surfaces, not one file read:

| Surface | What it needs after cutover |
|---|---|
| `watch.collect()` (`watch.py`) | one read snapshot yielding Open, awaiting-fold and Answered DTOs; counts; health; stable ids; revision/`updated_at` |
| `track_question_updates()` | retire its JSON signature sidecar; database revision/`updated_at` is the fact it was reconstructing |
| `POST /answer` | `questions.answer(id, body, actor, action_id)`, not a title-based whole-file rewrite |
| `POST /comment` | append a typed message by id in any state |
| `POST /decide` | set a decision on an existing review-to-question link by ids; no direct SQLite and no mutable title identity |
| `POST /ask` | **unaffected**: it writes the separate human-to-loop `answers.md` channel |
| `/questions` and `/question` | the same app shell; their client builders consume the structured DTOs from `/data.json` |
| `/review` | related-question rows, with `link_kind` and numeric question id, plus the default-selection rule below |
| `lint.py`, `dev/ledger.py`, `qsnap.py` | DB invariants/counts; retire Markdown shape/truncation checks and the file snapshotter after cutover |
| plugins/hooks | move `tracker_adapter.pose_question`, the precompact question count, and post-tool lint triggering to the API/CLI before deleting the file |

`collect()` currently also emits the entire file as
`files["questions.md"]`. No client JavaScript reads that field directly; the
question pages use `questions_open` and `answered_entries`. The raw field is
removed at cutover rather than regenerated from the database.

The standing API rule is already needed beyond questions. There are 13 / 13
direct production `sqlite3.connect` calls across eight modules:
`ledger_store.py` (1), `ledger_parse.py` (6), `watch.py` (1),
`task_origins.py` (1), `dev/ledger.py` (1), `dev/replay_events.py` (1),
`dev/journal_consume.py` (1), and `user_events/sqlite.py` (1). Tests use raw
connections to corrupt fixtures deliberately; production must converge on the
new connection door.

## IGC decision

**Context:** one existing SQLite store with a live ledger and review-decision
table; stdlib-only Python; threaded dashboard plus CLI writers; a demonstrated
projection loss; and a standing instruction that all database access should
look like this.

| Idea | All | G1 | G2 | G3 | G4 | G5 | G6 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| A. `dreamwork_db` core + domain repositories in the existing store | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| B. add question helpers to `ledger_store.py` / `ledger_write.py` | ✘ | ✘ | ✔ | ✔ | ✔ | ✘ | ✘ |
| C. create `questions.sqlite3` with a question-specific API | ✘ | ✘ | ✘ | ✔ | ✔ | ✘ | ✘ |
| D. DB authority plus a maintained `questions.md` projection | ✘ | ✔ | ✔ | ✘ | ✔ | ✘ | ✔ |
| E. dual-write Markdown and SQLite indefinitely | ✘ | ✘ | ? | ✘ | ✔ | ✘ | ✘ |

- **G1:** one supported connection, migration and transaction API.
- **G2:** review links have real foreign keys to tasks/questions in one
  transaction.
- **G3:** no uninstrumented projection can starve a consumer.
- **G4:** stdlib-only and landable as small compatibility-preserving steps.
- **G5:** `dev/ledger.py` becomes a consumer of the API, never a peer write
  implementation.
- **G6:** the same foundation can absorb every current production connection.

### Decisive errors

**B fails G1, G5 and G6.** It generalises the ledger's domain module into a
larger domain module while leaving connection policy, read helpers and the
journal elsewhere. The result is still “call SQLite here if the ledger is
involved”, not a reusable database API. `dev/ledger.py` would continue to mix
orchestration and SQL.

**C fails G1 and G2.** A second file creates a second WAL, migration ladder,
connection lifecycle and failure boundary. Its review links cannot foreign-key
the existing `task` table, so cross-domain integrity moves back into Python.

**D fails G3.** The ledger projection hid 142,249 characters from 77 open
entries while two consumers confidently acted on the shortened input. A shim
that renders no entries is worse for stale parsers: it reports an authoritative
zero. Instrumenting it would require byte/semantic parity on every write and
every reader, rebuilding the second truth this migration is meant to remove.

**E fails G1, G3, G5 and G6.** Atomic transactions cannot make a file write and
a database commit one atomic fact. A projector crash or stale process leaves
two authorities, and every reader must choose which lie to trust.

One survivor: **A**.

## API shape

### Modules

```text
dreamwork_db/
  __init__.py          # public types, open_database(), exceptions
  core.py              # path resolution, connection policy, unit of work
  migrate.py           # Migration + ordered fail-closed runner
  migrations/
    v001_legacy.py     # description/recognition of the existing baseline
    v002_review.py     # current v1->v2 migration moved intact
    v003_questions.py  # questions, reviews, issues and typed links
  tasks.py             # TaskRepository; absorbs ledger_parse/ledger_write SQL
  questions.py         # QuestionRepository + immutable DTOs/commands
  reviews.py           # ReviewRepository + link/decision DTOs
  journal.py           # connection/migration adapter used by Journal
```

`ledger_store.py`, `ledger_write.py` and `ledger_parse.py` may survive one or
two increments as compatibility facades, but their functions delegate to the
package and contain no connection or SQL. They are not a second supported API
and are deleted when their last caller moves.

### Getting a handle

```python
from dreamwork_db import Access, open_database

with open_database(target, access=Access.READ) as db:
    snapshot = db.questions.snapshot()
    review = db.reviews.get_by_path("design.html")

with open_database(target, access=Access.WRITE) as db:
    with db.transaction(immediate=True) as tx:
        q = tx.questions.post(command)
        tx.reviews.link(review_id, question_id=q.id, kind="blocking")
```

The handle exposes repositories and `transaction()`, never `.conn` or
`.execute`. Repositories return frozen dataclasses, not `sqlite3.Row`. Domain
errors are typed: `NotFound`, `Conflict`, `ValidationError`, `Busy`, and
`SchemaMismatch`; HTTP and CLI adapters translate them to a 404/409/422/503 or
a non-zero readable refusal.

### Connection lifecycle and transactions

- One short-lived connection per dashboard read snapshot, POST request, CLI
  invocation or hook call. Never share a connection across
  `ThreadingHTTPServer` threads.
- A READ handle opens `file:...?...mode=ro`, sets `query_only=ON`,
  `foreign_keys=ON` and `busy_timeout`, starts one deferred read transaction,
  and closes after all question/review/task DTOs are assembled. `collect()`
  therefore cannot combine questions from generation N with links from N+1.
- A WRITE handle applies WAL outside a transaction, then
  `foreign_keys=ON`, `synchronous=FULL` and `busy_timeout=5000` on every open.
  Each command uses one `BEGIN IMMEDIATE`; success commits, every exception
  rolls back.
- Migrations and cutover are explicit CLI operations, not side effects of a
  dashboard GET. Ordinary opens require the exact supported schema and name
  the migration command on an older version; a newer version always refuses.
- The existing `meta.schema_version=2` is adopted. Structural migration 3 is
  an ordered `upgrade(tx)` module. The runner holds one immediate transaction,
  applies every missing version in order, updates the version only after each
  step succeeds, and refuses a missing step or downgrade.

`dreamwork_db.core` accepts a `StoreSpec`, so the task/question store and
`user_events.sqlite3` keep their separate schemas and paths while sharing the
same connection, durability, version and transaction discipline. A test/lint
guard fails on any production `sqlite3.connect` outside `dreamwork_db/core.py`;
raw connections remain allowed in tests whose purpose is corruption/tamper.

## CLI and its relation to `dev/ledger.py`

Do not add a second executable. Extend the existing supported CLI:

```text
python3 dev/ledger.py db plan|migrate
python3 dev/ledger.py questions post --title ... --body-file - --priority P1 --actor coordinator
python3 dev/ledger.py questions answer ID --body-file - --actor watch [--action-id UUID]
python3 dev/ledger.py questions comment ID --body-file - --actor human
python3 dev/ledger.py questions fold ID --why ... --actor coordinator
python3 dev/ledger.py questions retitle ID --title ... --why ... --revision N
python3 dev/ledger.py reviews register .dreamwork/review/design.html
python3 dev/ledger.py reviews link design.html --question ID:blocking --task 645:related
python3 dev/ledger.py reviews link design.html --issue github:owner/repo#N:related
```

`--body-file -` is the normal multiline path; it avoids shell quoting and
command-substitution damage. The dashboard calls the repositories directly,
not the CLI subprocess, so validation and transitions remain one code path.
Existing task verbs (`file`, `fold`, `note`, `reprioritise`, `unblock`,
`retitle`) become adapters over `TaskRepository` without changing their
observable CLI contract. Thus the CLI and Python API are two interfaces to
one implementation, not two supported data-access ways.

## Schema — migration v3

Question ids are permanent integers and never titles. Titles are display text
and may change. Review identity is a row whose logical key is its canonical
path relative to `.dreamwork/review/`; a content hash is a revision fact, not
identity, because editing a review must not sever its links.

```sql
CREATE TABLE question (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    status          TEXT NOT NULL CHECK (status IN
                    ('unanswered','answered_pending_fold','answered')),
    title           TEXT NOT NULL,
    body_markdown   TEXT NOT NULL,
    priority        TEXT REFERENCES priority_band(band),
    asked_at        TEXT,
    asked_precision TEXT NOT NULL CHECK (asked_precision IN
                    ('unknown','day','minute','second')),
    created_by      TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    revision        INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0)
);

CREATE TABLE question_message (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id   INTEGER NOT NULL REFERENCES question(id),
    kind          TEXT NOT NULL CHECK (kind IN ('answer','note')),
    author        TEXT NOT NULL,
    body_markdown TEXT NOT NULL,
    at            TEXT,
    action_id     TEXT UNIQUE,
    CHECK (length(trim(body_markdown)) > 0)
);
CREATE INDEX question_message_order
    ON question_message(question_id, id);

CREATE TABLE review_file (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    path           TEXT NOT NULL UNIQUE,
    content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
    size_bytes     INTEGER NOT NULL CHECK (size_bytes >= 0),
    registered_at  TEXT NOT NULL,
    registered_by  TEXT NOT NULL,
    revision       INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0)
);

CREATE TABLE issue (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tracker    TEXT NOT NULL,
    repository TEXT NOT NULL,
    external_id TEXT NOT NULL,
    UNIQUE (tracker, repository, external_id)
);

CREATE TABLE review_link (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id     INTEGER NOT NULL REFERENCES review_file(id),
    link_kind     TEXT NOT NULL CHECK (link_kind IN ('related','blocking')),
    task_id       INTEGER REFERENCES task(id),
    issue_id      INTEGER REFERENCES issue(id),
    question_id   INTEGER REFERENCES question(id),
    decision      TEXT CHECK (decision IN ('pending','accepted','rejected')),
    decided_at    TEXT,
    decided_by    TEXT,
    CHECK ((task_id IS NOT NULL) + (issue_id IS NOT NULL) +
           (question_id IS NOT NULL) = 1),
    CHECK (decision IS NULL OR question_id IS NOT NULL),
    CHECK ((decision IS NULL AND decided_at IS NULL AND decided_by IS NULL)
        OR (decision IS NOT NULL AND decided_at IS NOT NULL
                             AND decided_by IS NOT NULL))
);
CREATE UNIQUE INDEX review_link_task
    ON review_link(review_id, task_id) WHERE task_id IS NOT NULL;
CREATE UNIQUE INDEX review_link_issue
    ON review_link(review_id, issue_id) WHERE issue_id IS NOT NULL;
CREATE UNIQUE INDEX review_link_question
    ON review_link(review_id, question_id) WHERE question_id IS NOT NULL;
```

The API path-validates `review_file.path` with `PurePosixPath`: relative,
non-empty basename, no `..`, root-level `.html`, resolved under
`.dreamwork/review`. Registration reads the file once, hashes those same
bytes, and inserts/refreshes the row in one transaction. Same path + same hash
is idempotent; same path + changed hash is an explicit refresh that increments
revision. A rename updates the path by id and preserves links.

Status is the three states the UI already renders. An answer appends a message
and moves `unanswered` to `answered_pending_fold`; another genuine answer is
retained in the same state. Fold requires at least one answer and moves to
`answered`. A note changes no status. Reopen and retitle are explicit id-based
commands with a reason and expected revision. No title parsing decides state.

The existing `review_decision(artifact, question_title, ...)` table is replaced
by decision columns on the typed question link. Absence of a link remains
`unlinked`; a link with `decision='pending'` remains explicitly pending.

## Serving and the review UX

Keep the current question DTO shape during the server cutover so the page can
move independently, but add `id`, `status` and `revision`; derive legacy
`answer`/`answers`/`follows` fields from ordered messages in the repository
adapter. Then change URLs and writes from mutable title to numeric id.

Each review row returned by `collect()` gains:

```json
{
  "questions": [{"id": 12, "title": "...", "status": "unanswered",
                 "link_kind": "blocking", "decision": null}],
  "tasks": [{"id": 645, "title": "...", "link_kind": "related"}],
  "issues": [{"ref": "github:owner/repo#N", "link_kind": "related"}]
}
```

Opening `/review?p=<path>` always renders the RHS **related questions** list.
Selection is deterministic:

1. an explicit `qid=<numeric id>` selects that linked question or shows a
   mismatch refusal;
2. otherwise, exactly one linked question whose status is `unanswered` is
   selected and its card loads by default;
3. otherwise, no question is selected and the list asks the reader to choose.

An `answered_pending_fold` or `answered` question is not “unanswered”, so it
never earns the automatic default. Link kind is shown beside every task,
issue and question. The current title-query compatibility path exists only
before the watermark; it is removed with the file, not kept as a permanent
alias that could select the wrong retitled question.

## Migration and proof of no loss

### Cutover protocol

1. **Land the dark API and dispatch first.** Before the watermark, all readers
   and writers still use Markdown. The pre-cutover route writers also take a
   cross-process `fcntl.flock` and check the watermark inside it; after the
   watermark, a legacy file write refuses.
2. **Commit the source.** Cutover requires `.dreamwork/questions.md` clean and
   committed. Record its commit, git blob id, SHA-256, bytes and lines.
3. **Dry-run parse and coverage.** Print every entry ordinal/title/state plus
   every unclassified source span. Refuse on a non-empty unclassified list,
   duplicate source span, missing section, or zero examined entries.
4. **Import under the same exclusive file lock and one DB transaction.** Create
   questions/messages, register 33 review files, migrate any explicit old
   decisions, verify, then set `questions_cut_over` and the source receipt in
   `meta`. No DB reader uses the shadow rows before that watermark.
5. **Re-read the source before commit.** Its blob/hash/size must still equal the
   committed source. The shared lock blocks cutover-aware dashboard writers;
   the coordinator abstains from manual writes. Inventory and restart older
   watch processes at this gate, because a process built before the lock cannot
   be made safe by a SQLite transaction it never opens.
6. **Read back through production repositories.** Run `collect()`, lint, CLI
   counts and review joins from the store. Only then release the lock.
7. **Delete `questions.md` in the next small commit.** Remove the raw
   `files.questions.md` field, retire `qsnap.py` and Markdown-only checks, and
   make lint ERROR if the file reappears after the watermark. Git plus the
   stored source receipt is the immutable archive.

There is no steady-state dual read or dual write. The watermark is the single
dispatch just as it is for the ledger.

### What `questions migrate --verify` compares

A row count is only one term. The verifier obtains the recorded git blob and
builds a length-framed canonical manifest containing:

- full source blob/hash/byte/line counts;
- exact section headings and source coverage spans;
- for every source ordinal: state, exact title, priority, exact question-body
  bytes, asked timestamp/precision and source span;
- every contribution's kind, author, timestamp, exact body bytes and order;
- the assigned permanent question id; and
- every review registration/link/decision row.

It queries the database through the production repositories, builds the same
manifest, compares values and manifests, and names every missing, extra or
changed ordinal/id. It also reports denominators:

```text
source bytes classified: 257370 / 257370
question heads classified: 72 / 72; unclassified: 0 / 72
questions imported: 72 / 72 (5 unanswered, 0 awaiting fold, 67 answered)
contributions imported: 113 / 113
review artifacts registered: 33 / 33; explicit links migrated: 0 / 0
```

Those figures are today's illustrative expected output, not pinned constants.
An implementation-time change is valid when both sides derive the new same
denominator; “0 errors” without non-zero source denominators is a refusal.

This catches a missing question, reordered/lost contribution, truncated body,
wrong state, null-vs-known resolution date, title change during cutover,
extra fabricated row, and the 200,000-character truncation shape. Git-blob
comparison also catches a source that shrank relative to the committed cutover
input. It cannot recover data already absent from every retained git commit;
that limitation is stated rather than converted into a green check.

## Red-proof

### Direction 1 — demonstrated loss shape

The current branch already contains the #632 tourniquet, so the production
route no longer performs a bounded whole-file read. Reintroducing its exact
former 200,000-character input on a private copy produced:

```text
precondition: source chars=252946 > cap=200000; parsed=72/72
write result: chars=200064 parsed=54/72 lost_titles=18/72 matched=True
first lost title: <the first tail entry omitted by the bounded read>
RED: bounded read-modify-write returned success while 18/72 questions disappeared and 52882 characters were removed
```

`dev/redproof.py` then restored the copy and reported:

```text
check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits
```

This is stronger than the historical story: one successful answer targeted an
entry in the retained prefix while 18 other questions vanished.

### Direction 2 — success while wrong

Two reproducible inputs distinguish the checks:

```text
heading-like case: parsed=1/1 tail_preserved=False
FALSE GREEN under count-only verification: imported 1/1 while the tail is absent
entry-like case: parsed=2/2 titles=['P1 · 2026-08-01 — real question',
 'This is emphasis inside the body, not a new question']
OPEN FALSE GREEN: parser and importer can agree 2/2 while author intended 1 question
```

The source-coverage check catches the first: `## Details` exits the recognized
section and leaves non-whitespace bytes unclassified. Per-field/message byte
comparison catches a multi-paragraph Answered body truncated to its first
paragraph. Stable ids catch a title changed **after** migration because links
do not move; an old `review_decision` naming no exact current title refuses
during migration.

The second case remains an honest open false-green: in today's grammar a
column-0 `- **...**` is an entry head. Parser, raw splitter and database can
all agree while disagreeing with the author's intent. The dry-run mitigates it
by printing all `N / N` source titles for human review, but automation cannot
infer whether bold text was intended as a question. Future CLI-only creation
eliminates the ambiguity for new rows; it cannot retroactively prove intent.

A source already truncated and committed before the recorded cutover blob can
also verify clean against itself. The verifier searches retained git history
and reports a larger prior blob/entry set, but if no retained copy exists, it
cannot recover the missing words. That limit is why the source receipt names
what it examined rather than claiming universal completeness.

## 15–20 minute landing sequence

Each increment ends usable and preserves pre-watermark behaviour.

1. **Core connection unit.** Add `dreamwork_db.core`, `StoreSpec`, read/write
   handles and transaction tests; make `ledger_store.open_store` delegate.
2. **Migration unit.** Move the existing schema/version ladder intact into
   version modules; prove v1→v2 and newer-version refusal unchanged.
3. **Task read unit.** Move the six `ledger_parse.py` store reads,
   `task_origins.py` and the CLI warning query into `TaskRepository`; facades
   delegate, output parity stays green.
4. **Task write unit.** Move `ledger_write.py` commands behind
   `TaskRepository`; `dev/ledger.py` is now only validation/presentation.
5. **Other-store unit.** Route `Journal`, replay and consume connections
   through the core with their existing domain APIs unchanged; enable the
   no-production-raw-connect guard. The standing rule is real before the first
   new schema depends on it.
6. **Schema-v3 unit.** Add questions/reviews/issues/links in scratch stores and
   migrate the empty live-shape `review_decision`; no live import or dispatch.
7. **Lossless parser unit.** Build dry-run manifest/source-span coverage with
   the heading, wrapped-title, multi-answer, missing-date and unclassifiable
   fixtures; print the live denominators, write nothing.
8. **Import/verify unit.** Import into a scratch copy and compare production
   repository manifests field-for-field; repeated import is idempotent or a
   named conflict, never repair-by-overwrite.
9. **CLI unit.** Add `questions post/...` and `reviews register/link/...` over
   repositories. Before the watermark mutating question verbs refuse with the
   cutover command, so no second writer path exists.
10. **Dark read unit.** Add watermark dispatch to `collect`, lint, warning
    counts, plugin count and tracker adapter; Markdown remains live with no
    watermark. Retire signature tracking on the store side only.
11. **Dark write unit.** Add repository branches for `/answer`, `/comment` and
    `/decide`, numeric ids, file lock and legacy-write refusal. Concurrency
    tests run dashboard and CLI commands against the same scratch DB.
12. **Review UX unit.** Serve typed link lists and implement the RHS list plus
    exactly-one-unanswered default. Empty links preserve today's no-dock view.
13. **Live cutover unit.** Commit/freeze source, rerun census, import+verify,
    set watermark, restart stale dashboard processes, and prove all production
    readers/writers use the store. `questions.md` remains frozen for this one
    reversible checkpoint.
14. **Deletion unit.** Delete `questions.md`, raw payload field, snapshotter and
    file-only checks; add reappearance ERROR and verify from the recorded git
    blob. This is the first state with no projection and the final state.

The already-landed #632/#643 work is retained throughout: it remains the
tourniquet for `handoffs.md`, `lessons.md` and every bounded display read even
after the question file disappears. The database migration removes the
question-specific whole-file rewrite class; it does not make the generalized
read/write safeguards obsolete.
