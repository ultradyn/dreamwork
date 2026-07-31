# Lane 645 report

## Verdict

READY. The design chooses one reusable Python database API over the existing
`ledger.sqlite3`, makes `dev/ledger.py` its CLI adapter, explicitly supersedes
the coordinator-only file writer with serialized transactions plus domain CAS,
and deletes `questions.md` after a measured/verified watermark cutover. It does
not preserve a projection shim.

Design commit after rebasing onto local master:
`b295e9d167eb3f901d7e4025d01b3a6dee000334`.

## Changed

- Added `.dreamwork/docs/cx-645-db-api-design.md`.
- Added this required lane report.
- Changed no behavior and no other tracked file.

The design measured 72 / 72 question heads: 5 unanswered, 0
answered-awaiting-fold, 67 Answered; 113 / 113 contributions; 31 / 72 wrapped
titles; and 0 / 72 unclassifiable entry heads. It measured 33 / 33 served
review HTML files and 0 / 33 structured decision/link rows. It also inventoried
13 / 13 direct production `sqlite3.connect` sites across eight modules, which
is why a question-only helper was rejected.

## Verification

- `python3 lint.py`: **clean, 0 ERRORs, 6 expected worktree/store WARNs**. It
  independently reported `5 open, 67 answered` and the same 3 / 67 missing
  resolution dates used in the design.
- `git diff --check`: clean.
- Post-rebase census: unchanged at 257,370 bytes, 5 unanswered and 67
  Answered; 33 served review HTML files.
- No pytest was run: this lane changes documents only.

## Red-proof

### Direction 1 — discriminating red

On `.dreamwork/questions-645-redproof.md`, a private byte-identical copy, I
reintroduced the former 200,000-character input to the real
`watch.append_answer` transformation. The command exited 1 on:

```text
precondition: source chars=252946 > cap=200000; parsed=72/72
write result: chars=200064 parsed=54/72 lost_titles=18/72 matched=True
RED: bounded read-modify-write returned success while 18/72 questions disappeared and 52882 characters were removed
```

The target answer was written successfully, so this was not a red caused by a
missing fixture or unmatched title. `dev/redproof.py restore` restored and
verified the copy; `cmp` against the source passed. The required gate said:

```text
check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits
```

The current production path already has the tourniquet, so this demonstrates
the structural class the DB migration removes rather than claiming the fixed
route is still lossy.

### Direction 2 — false greens

A column-0 body heading gives a count-only migration a green `1 / 1` while the
tail is absent:

```text
heading-like case: parsed=1/1 tail_preserved=False
FALSE GREEN under count-only verification: imported 1/1 while the tail is absent
```

The proposed source-span coverage check catches it because the tail is
non-whitespace outside a recognized section. Per-field byte comparison also
catches a multi-paragraph Answered body reduced to its first paragraph, and
stable ids keep later retitles attached to review links.

One false-green remains open and is named in the design:

```text
entry-like case: parsed=2/2 titles=['P1 · 2026-08-01 — real question',
 'This is emphasis inside the body, not a new question']
OPEN FALSE GREEN: parser and importer can agree 2/2 while author intended 1 question
```

Every mechanical layer treats a column-0 `- **...**` as an entry. The dry-run
prints all titles for adjudication and future CLI creation removes the
ambiguity, but automation cannot reconstruct the legacy author's intent. A
source already truncated in every retained git commit is the other stated
limit: verification can report what it examined, not recover absent history.

## Issue evidence read

- **#645:** *"all our DB access should be like this"* — the API is the
  deliverable and questions are its first consumer.
- **#440:** *"a single supported way to fold an entry"* — `dev/ledger.py`
  must consume the API rather than coexist with it.
- **#671:** the broken sweep printed *"nothing to review (this ran)"* after
  reading zero ledger entries — every migration result therefore carries a
  non-zero denominator and an explicit unclassified bucket.
- **#702:** its landed result says malformed task ids are *"KEPT and reported
  loudly rather than reaped as dead"* — the importer reports and refuses
  unclassifiable spans rather than dropping them.
- **#306:** the check governs an Open question whose named task has landed and
  is deliberately title-based today — state moves to a column, never a prose
  marker.
- **#632:** root cause was `read_text(path, limit=200_000)` feeding
  read-modify-write routes that returned success after deleting entries — the
  DB has no whole-file rewrite.
- **#643:** the same bound made 45% of `handoffs.md` invisible — the generalized
  bounded-read fix remains necessary after questions migrate.
- **#750:** its winning design measured the live value domain before choosing
  and required decisive errors for rejected options — copied here through the
  72-question, 33-review and 13-connection censuses plus IGC.
- **#572:** the task says its final design fork was answered on 2026-07-31, but
  its Answered entry has no parsed resolution date; the schema therefore
  permits `answered_at = NULL` without dropping its answered state.
- **#613:** *"Live/streamed hierarchical view ..."* is landed while its
  Answered entry likewise lacks a parsed resolution date; same migration case.
- **#614:** *"Transition the frontend webui to a websocket event model ..."*
  is landed while its Answered entry lacks a parsed resolution date; same
  migration case.

## Rebase outcome

Local `master` moved eight commits during the design increment and four more
during the hand-off gate. Both `git rebase master` runs completed cleanly with
no manual resolution. The post-rebase source census was byte-for-byte
unchanged.

## Out of scope findings

- The 15 filename-derived and 31 prose-derived review/task candidates are not
  relations. The future CLI must register them explicitly; this lane did not
  fabricate migration data.
- The current store already has a partial `review_decision` table keyed by
  mutable `question_title`, but the live table has 0 rows. Migration v3 must
  still refuse if unmatched/kindless rows appear before implementation.
- The design intentionally removes the raw `files.questions.md` payload field
  and the generic `/file?p=.dreamwork/questions.md` view. The structured
  question pages have no direct dependency on that raw field.

## DOGFOOD REPORT

- The brief describes #632/#643 as live defects to sequence around, but current
  master already contains their landed fix. The design treats that work as an
  already-installed tourniquet, not a future lane, while retaining it for
  `handoffs.md` and `lessons.md`.
- `dev/redproof.py check` requires a restored path to continue existing, while
  this lane's contract permits only the design and report at hand-off. That
  means a temporary-copy demonstration can either keep its registered proof or
  leave the tree in scope, not both. I quoted the clean registered check above,
  then used `forget` and removed only the temporary copy; the final calm check
  is necessarily less informative. A `forget --delete-restored-copy` or a
  registry mode for ephemeral copies would remove this friction.
- Codebase graph discovery found top-level question functions but did not index
  nested `Handler._handle_answer/_comment/_decide` methods. The documented
  fallback to an exact string search was necessary to enumerate the POST
  migration surface.
- `review_artifact.py corpus .dreamwork/review` looks like the `check` command's
  positional shape but errors; corpus requires `--review-dir`. `--help` made it
  recoverable, but the asymmetric CLI cost one failed read-only call.
