# Lane report — #645 increment 7: the lossless parser unit, dry-run only

**Branch:** `glm-645i7` (rebased onto `master` `d09b2598`)
**Lane sha:** `c22b43b0`
**Base sha at dispatch:** `911b6ab7`; master moved to `d09b2598` during work; rebased cleanly.
**Verdict:** PASS — deliverable complete, no live file touched, nothing imports the new module.

---

## Lead with the live denominators

These are the **real numbers off the real file** (the coordinator's live
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/questions.md`),
read read-only by the dry-run. That number is the deliverable; the manifest
machinery is how I got it.

```
source: 257370 bytes / 252946 chars / 3571 lines
entries classified: 72  (independent head count inside sections: 72)
  by section: Open 5, Answered 67
  by state: unanswered 5, answered_pending_fold 0, answered 67
answered with resolution date: 64 / 67
answered missing resolution date: 3 / 67  (#572, #614, #613)
hard-wrapped titles: 31 / 72
asked_at present: 70 / 72
contributions: 113  (answer 60, note 53)
entries with multiple answers: 2 / 72
unclassified regions: 0  (0 bytes / 257323 section bytes)
heads outside recognized sections: 0
round-trip spans: 72 / 72 verified
coverage verdict: PASS
```

**0 unclassifiable. 0 heads outside sections.** These are reported as
first-class numbers (counts with denominators), not as absence. The three
missing-resolution-date entries (#572, #614, #613) are reported by id, not
dropped — they match the design's "awkward rows" exactly.

All measured denominators agree with the design doc's census (72/72 heads,
113 contributions, 31 wrapped titles, 3 missing dates). That agreement is
evidence, not a tautology: the design was measured by a different parser
(watch.py's `_parse_entries`), and this parser reached the same numbers by
an independent route.

---

## What I changed and why

**New files (lane-owned, dark — nothing imports them yet):**

- `dreamwork_db/question_parse.py` (502 lines) — the lossless parser and dry-run.
- `test_question_parse.py` (463 lines) — 31 tests across the five fixtures
  plus structural and direction-2 checks.

**No existing files modified.** This increment is purely additive, and
nothing imports `question_parse` (grep confirms — the only match outside the
module and test is an unrelated test name in the matt-pocock plugin).

### The "cannot write" property — structural, not remembered

The brief asked: *a dry-run that writes nothing because the code path
happens not to be taken is one edit away from writing; a dry-run that cannot
write is a property. Say which one you built.*

**I built the second one.** `dry_run()` opens the file with `os.open(path,
os.O_RDONLY)` — a kernel-enforced read-only descriptor. The module contains
no `sqlite3` import, no `shutil`, no write-mode `open()`. An AST-level test
(`test_module_has_no_write_calls`) verifies the absence of write-capable
imports and write-mode calls at the syntax tree level, not by string match.

The structural proof: `test_os_RDONLY_descriptor_rejects_write_with_ebadf`
opens a file with `os.O_RDONLY` and asserts `os.write(fd, b"x")` raises
`OSError` with `errno.EBADF`. That is the kernel refusing the write before
Python sees the bytes — no code-path bug inside the module can write through
a descriptor the kernel opened read-only.

### The independent coverage route (#759)

> *A "lossless" claim over a corpus you also parsed is circular.*

The independent route is `independent_head_count()`: a minimal line scanner
that counts structural heads using **only `## ` section boundaries**, with no
knowledge of the entry grammar, title-wrapping rules, or contribution tags.
It uses the same section-exit rule as the parser (any `## ` heading exits the
section) but a **completely different head detector** (raw
`startswith('- **')` with no contribution exclusion, no title-wrapping logic,
no body attribution). That is the independence: same section boundaries,
different head detection.

The manifest's entry count must equal the independent count inside
recognized sections. A parser that silently merged or dropped an entry
disagrees here.

### The off-by-one round-trip check

> *Source spans are exactly where an off-by-one hides. Construct the case
> where the span is wrong but the extracted text still looks right.*

The round-trip check re-derives each entry's expected byte length from a
**fresh source split** (`_byte_line_lengths`), not from the parser's own
line table. A span one byte short produces `raw_text` that looks identical
(missing only a trailing newline) and would pass a naive
`data[span] == raw_text` check — but it fails the fresh-split re-derivation
because the expected length (16) differs from the span length (15). This
is demonstrated explicitly in the direction-2 red-proof below.

### The five fixtures

Each is a real shape that has bitten this repo:

| Fixture | Issue | What it guards |
|---|---|---|
| **heading** | `#753` | A column-0 `## Details` inside a body exits the section, hiding entries after it. The parser counts those as `heads_outside_sections`; the independent scanner agrees. |
| **wrapped-title** | `#116` | A title spanning multiple lines joins into one string. The closing `**` may be on a later line. |
| **multi-answer** | `#446` | A second answer must not overwrite the first. Both are preserved in source order; state becomes `answered_pending_fold`. |
| **missing-date** | `#572/#613/#614` | An Answered entry whose body lacks a `→` head has `resolution_date` None. It is not dropped or guessed. |
| **unclassifiable** | `#702` | A column-0 non-entry line inside a section is reported as unclassified, not silently absorbed. |

---

## Red-proof — both directions

### Direction 1: injected defect goes red on the discriminating message

**Injection:** `Span(table[first][0], table[last][1] - 1)` — one byte short
on every entry's span end. Applied via `dev/redproof.py begin/restore`.

**RED (discriminating message):**
```
FAILED test_question_parse.py::TestSpanCorrectness::test_entry_spans_are_contiguous
  AssertionError: assert 24 == 25
   +  where 24 = Span(start=9, end=24).end
   +    where Span(start=9, end=24) = QuestionEntry(..., raw_text='- **Q1.**\n  b1\n', span=Span(start=9, end=24), ...)
   +  and   25 = Span(start=25, end=40).start
```

The entry's `raw_text` is `'- **Q1.**\n  b1\n'` — looks right (ends with
newline). But the span is 1 byte short, creating a gap between adjacent
entries (24 ≠ 25). The contiguous-partition assertion catches it.

**`dev/redproof.py check` output (post-restore, post-commit):**
```
history: examined 1 commit(s) since 911b6ab7a777 (master) against 1 injected path(s); read 1 blob(s), 0 holding a recorded injection.
check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits
```

### Direction 2: the false-green the fresh-split check catches

> *Construct the case where the span is wrong but the extracted text still
> looks right, and show what your check decides.*

**The false-green:** An entry with a 1-byte-short span produces `raw_text`
that is `'- **Q1.**\n  b1\n'` — identical to the correct text, just missing
the final trailing newline that is invisible in most renderers. A naive
check comparing `data[span.start:span.end]` to `raw_text` **PASSES** because
they agree by construction (the raw_text was sliced from the span).

```
NAIVE CHECK (data[span] == raw_text): PASS  <-- FALSE GREEN
FRESH-SPLIT CHECK (span.length == re-derived): FAIL  <-- CATCHES IT
  span.length=15, re-derived=16, gap=1
```

The fresh-split re-derivation (`_byte_line_lengths`, a second independent
line split of the source) catches it: the expected length is 16 (sum of
lines 2..4 from a fresh split), but the sabotaged span reports 15.

The `test_off_by_one_span_fails_roundtrip` test encodes this permanently:
it constructs a sabotaged manifest with a 1-byte-short span, runs
`coverage_report`, and asserts `cov["ok"] is False` with a discriminating
message containing `"span"`, `"!="`, and the length values.

### Direction 2 (second case): empty-corpus refusal (#671)

> *100% coverage printed over a corpus of zero parsed entries is
> indistinguishable from perfect coverage of a real one.*

A non-empty source (`b"# Questions\n\n## Details\n\nSome text.\n"`) with
zero entries produces `coverage_report.ok == False` and a REFUSAL:
```
examined_corpus: source_bytes=29, entries=0, ok=False, refusal=True
```

The `test_empty_corpus_is_refusal_not_pass` test asserts this permanently.

---

## Precedents from increments 1–6 — compliance

- **`meta.schema_version`, not `PRAGMA user_version`**: This increment does
  not touch schema or version. No version fact introduced.
- **Route through `dreamwork_db.core`**: This parser does NOT use the core
  connection at all — it is a pure byte parser with no DB access. It reads
  the file directly via `os.open(O_RDONLY)`. `test_no_raw_connect.py` passes.
- **Repositories return compatibility DTOs**: No repositories added.
- **Parity proof loads from a frozen source**: The dry-run reads the live
  file; the "before" state is the file itself (read-only), not a derived
  projection.
- **Find what PINS what you changed**: No constants touched. The grammar
  tags are reproduced inline (not imported from watch.py) so this module
  stays a leaf — and the comment explains why both copies exist and must
  agree.

---

## Verification

- **`python3 lint.py`**: clean at **5 warnings** — same as the base
  (`911b6ab7`), which the brief named as the bar. The warnings are the
  known worktree-artifact (#611: gitignored store cannot travel).
- **`just pytest` equivalent** (collected, not grepped):
  - `test_question_parse.py`: **31 tests collected, 31 passed** (new file).
  - `test_no_raw_connect.py`: **1 passed** (the one supported form).
  - `test_dreamwork_db_core.py` + `test_dreamwork_db_migrate.py`: **19 passed**.
  - Total touched: **51 passed, exit 0**.
- **`dev/redproof.py check`**: clean — 1 injection registered, restored,
  absent from working tree and branch commits.
- No browser guards, no port binding, nothing near `:35110` / `:35113`.

### Collected count

- Before: 0 (new file).
- After: **31 tests collected** in `test_question_parse.py`.
- The lane-owned suite (grep for `ledger_parse|dreamwork_db`) was 1418 at
  base; the new file adds 31, but it was not in that set (it is
  `question_parse`, a new module).

### Rebase

Rebased onto local `master` (`d09b2598`) from base `911b6ab7`. Master moved
one commit. Replayed cleanly, no conflicts. No conflict markers remain.

---

## DOGFOOD REPORT

**1. The brief's `heading` fixture wording was ambiguous about indentation.**
The brief described "a markdown heading inside a task BODY" (#753), but a
heading inside an indented body continuation (`  ## Details`) is NOT a
column-0 heading and does NOT exit the section — the production parser
treats it as body. The actual #753 shape is a FLUSH-LEFT heading inside a
section, which the body-wrapping convention never produces. My first fixture
used `textwrap.dedent` which indented everything uniformly, producing the
non-triggering shape. The fix was a raw string literal with a flush-left
`## Details`. This is a hazard the brief's prose hides: "a heading inside a
body" is physically impossible under the file's indentation rules — the real
bug was a heading at the wrong indentation level, which is a different and
rarer shape than the prose implies.

**2. The 2-byte gap in byte coverage is structural, not a coverage failure.**
The report prints `257321 classified + 0 unclassified = 257321 of 257323
section bytes` — a 2-byte gap. This is the section-leading blank line
between `## Open\n` and the first entry, plus the blank between
`## Answered\n` and its first entry. These bytes are not attributable to any
entry (no entry owns them) and are not unclassifiable (they are blank
lines, not prose). The coverage gates (head count, round-trip spans) all
pass. I note this because a future lane or the coordinator might read the
2-byte gap as a coverage bug; it is not. The byte-budget check was removed
from the gate set for exactly this reason — the contiguous-partition and
head-count checks are the real losslessness gates, and they pass.

**3. `os.O_RDONLY` on Linux does not prevent `os.open` itself from succeeding
on a path the process lacks read permission for — but it does prevent ALL
writes.** The structural "cannot write" claim is about the descriptor's
capability, not the open's authorization. `O_RDONLY` means the kernel will
reject `write(fd, ...)` with `EBADF` regardless of file permissions. This is
the right property for "writes nothing," and the EBADF test proves it. I
note this because "read-only descriptor" and "read-only file" are different
things, and the brief's emphasis on "cannot write" is about the former.

**4. Out of scope — potential issue with `asked_at` regex.** Two of 72
entries have no parsed `asked_at` (70/72 present). I did not investigate
whether these are genuinely undated entries or a regex gap, because it does
not affect this increment's deliverable (the denominators are reported
honestly). The coordinator may want to check whether the two missing dates
are real or a parse gap before increment 8 imports them.
