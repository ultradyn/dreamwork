# #645 increment 8 — lane report: import/verify unit, scratch-only

**Lane:** glm-645i8 · **Base:** 4a569f24 · **HEAD:** 085ad30 · **Rebase:** clean (master unmoved)

## Verdict: what the idempotence check decides for an importer that short-circuits without looking

**The idempotence check passes. The independent verifier fails.** An
importer that short-circuits on "destination already has rows" returns every
entry as `unchanged` without comparing any field, and a check that only asks
the importer whether re-import was clean reports success. The drift is
invisible to it.

The independent verifier (`verify_import`) reads the DB through raw SQL,
builds its own snapshot, and compares every content field against the
manifest. It caught the drift the short-circuit skipped:

```
short-circuit importer: ok=True, unchanged=1, conflicts=0   ← FALSE GREEN
independent verifier:   ok=False, matching=0, conflicts=1
  discriminating delta: field='title' manifest='P1 · ... — #500: ...' stored='DRIFTED'
```

This is why the verifier is a **separate function** from the importer's own
comparison. `_compare_existing` (the importer's method) and `_verify_entry`
(the verifier's function) implement the same field comparison, but the
verifier reads independently and does not consult `ImportResult`. An
importer bug in one does not hide in the other.

## What changed

Two new files, both dark (nothing imports them from a live path):

- **`dreamwork_db/questions.py`** (612 lines): `QuestionRepository` with
  `import_manifest` (idempotent insert-or-named-conflict), `snapshot`
  (independent read-back), and `verify_import` (standalone field-for-field
  comparison against a snapshot). Also `question_store_spec` binding both
  `TaskRepository` and `QuestionRepository` through the one core door.
- **`test_dreamwork_db_import.py`** (579 lines, 34 tests): import
  correctness, idempotence, conflict detection (never overwrite), dateless
  entries, independent verification, short-circuit trap, empty-store proof.

## The rule that carries the weight

> repeated import is idempotent or a named conflict, never repair-by-overwrite.

Three outcomes per entry: `unchanged`, `conflict` (named, specific field),
and `cannot_tell` (structural inability to compare — e.g. message counts so
different that per-field comparison is unreliable). `#136`: "imported, no
change" and "could not determine whether this differs" must not render
identically — they are separate dispositions.

A None-valued source field against a NULL column IS a match (both carry
nothing) and reports as `unchanged` for that field. `cannot_tell` is the
structural inability to compare, not an absence.

Extra stored questions (ids with no manifest counterpart) and extra messages
are **reported but never deleted** — deletion is repair-by-overwrite by
another name.

## The three dateless entries (#572, #613, #614)

These are live data, not a parser artifact. Their bodies have no `→`
resolution head, and section membership says they are `answered` while the
resolution date is absent. The import stores the body verbatim — no date is
invented. The `resolution_date` is not a column; it lives in `body_markdown`,
which is stored exactly. If a future increment adds it as a column, it must
be nullable, and `NULL` is the honest value for these three.

The `test_null_asked_at_preserved_not_defaulted` test confirms: an entry
with no date in its title gets `asked_at=NULL`, not `today`.

## Red-proof — Direction 1: repair-by-overwrite injection

Injected into `dreamwork_db/questions.py`: `_compare_existing` silently
overwrites conflicts (UPDATE instead of naming them), reporting drifted
rows as `unchanged`.

**Discriminating failure:**
```
test_modified_title_is_named_conflict_not_overwrite FAILED
>   assert len(conflicts) == 1
E   assert 0 == 1
 +  where 0 = len(())
```

Zero conflicts because the sabotaged importer silently overwrote the drifted
title back to the manifest value — exactly the repair-by-overwrite behavior
the rule forbids. `redproof check` clean after restore.

## Red-proof — Direction 2: short-circuit trap (the one the brief leads with)

**Constructed implementation:** `_short_circuit_import` — counts rows, sees
`>0`, returns `ImportResult(entries=all-unchanged)` without comparing any
field.

**What the idempotence check decides: PASSES (false green).** The
short-circuit importer reports `ok=True, unchanged=1, conflicts=0` even when
the store has drifted. An idempotence test that only asks the importer
whether re-import was clean would pass here — it is measuring the
short-circuit, not the import.

**What the independent verifier decides: FAILS.** `verify_import` reads the
snapshot independently and catches the title drift with a named delta.

**Open false-green, stated honestly:** the verifier compares the manifest
against what the DB holds. If the source itself was truncated before the
cutover blob, the verifier compares two copies of the same truncation and
reports a match. It cannot recover data absent from every retained copy.
This is the same limit increment 7 acknowledged.

## Empty-store proof (#651, #671)

An empty scratch store imports "successfully" under almost any
implementation. The verifier distinguishes:

- **Non-empty source / empty store → REFUSAL:** `ok=False`,
  `empty_source_refusal=True`. `#671`: a check that examined nothing must
  not read as passing.
- **Empty source / empty store → MATCH:** `ok=True`,
  `empty_source_refusal=False`. A genuinely empty corpus over an empty store
  is a real match.
- **After a real import → MATCH:** `ok=True`, `empty_source_refusal=False`.
  The refusal does not persist once data exists.

**What the verifier CAN establish over a populated store:** for each
manifest entry matched to a stored question by ordinal, whether every
content field (status, title, body_markdown, priority, asked_at,
asked_precision, and every message's kind/author/body/at) matches exactly.
For entries with no stored counterpart: missing. For stored questions with
no manifest counterpart: extra.

**What it CANNOT establish:** intent (the source itself could be wrong);
metadata fields (created_at, updated_at, revision — the manifest does not
carry them, so comparing them against the manifest is meaningless).

## Independent route (#759)

The verifier does NOT consult `ImportResult`. It takes the parser's
manifest and a snapshot read through raw SQL (`SELECT ... FROM question`),
builds two independent representations, and compares every field. An
importer that mishandles a field cannot bias the verifier because the
verifier never asks the importer anything — it reads what landed.

This matches increment 7's standard: it proved losslessness with a minimal
scanner that knew nothing of the entry grammar. Here the equivalent is a
SQL reader that knows nothing of the importer's insert logic.

## Verification

- **Lint:** 5 warnings (worktree baseline; unchanged from base).
- **Test collection:** before 51, after 85, delta +34 (all in the new test
  file).
- **Pytest:** 85 passed / exit 0 (test_dreamwork_db_core, _migrate,
  question_parse, no_raw_connect, _import).
- **`test_no_raw_connect.py`:** PASS — `dreamwork_db/questions.py` contains
  no `sqlite3.connect` call; all access routes through `dreamwork_db.core`.
- **`redproof check`:** clean — 1 injection registered, all restored and
  absent from working tree and commits.
- **Rebase:** clean (master unmoved at 4a569f24).

## Cited issues, relied-on lines quoted

- **#136**: "present-but-unparseable is a fault and must look like one" —
  the `cannot_tell` disposition is structurally distinct from `unchanged`.
- **#759**: "a parity proof must VARY the interpreter and HOLD the subject
  fixed" — the verifier varies the reader (raw SQL vs importer) and holds
  the manifest fixed.
- **#671**: "420 commits examined, 177 open ids never seen, and it printed
  'nothing to review (this ran)'" — the empty-store refusal is the same
  discipline: examined-nothing must not read as pass.
- **#651**: "A guard whose message names a failure mode it cannot detect" —
  the verifier's `ok` property names exactly what it can and cannot decide.

## DOGFOOD REPORT

**Friction found, stated.**

1. **The `tx.execute` API was wrong for sabotage.** My initial test code
   tried `db.transaction().__enter__().execute(...)` to sabotage the store
   from within a test, but `DatabaseHandle` deliberately exposes no
   `.execute` — repositories get a private `_RepositorySession`, handles do
   not. This is correct design (the public surface has no raw SQL), but it
   means tests that need to deliberately corrupt a store for red-proofing
   must open a raw `sqlite3.connect`, which they are exempt from under
   `test_no_raw_connect.py`. The friction was discovering this at test-run
   time rather than at design time; a one-line note in the core module's
   docstring ("tests may use raw sqlite3.connect for deliberate corruption")
   would have saved a round-trip. Not a defect — a documentation gap.

2. **The dateless fixture had an accidental `→` in prose.** My first
   `DATELESS_FIXTURE` included "No → head here" as body text, which the
   parser correctly picked up as a resolution date — exactly the opposite
   of what the fixture was meant to test. The parser is right: a `→` in
   body prose IS a resolution head. The fix was to reword the prose, but
   the trap is real: a fixture that says "no arrow" while containing an
   arrow is a self-defeating test. This is the same shape as the
   direction-2 open false-green from increment 7 — the grammar is richer
   than "title plus answer."

3. **No out-of-scope findings beyond the above.**
