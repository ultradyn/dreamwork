# Lane #761 report — `lessons_index` files a cross-cutting lesson under the act that FOUND it

**Branch:** `cx-761acts`
**Status:** DONE — fix landed, red-proofed both directions, tests green, lint clean.

## TL;DR

The brief's diagnosis was wrong; the measurement decided the fix. The taxonomy
**already** multi-files (287/334 lessons match 2+ acts). The real bug was a
**vocabulary gap in the `red-proof` anchor**: it named injections and red/green
runs but not the vocabulary of a hollow check. Adding three terms
(`\bhollow\b`, `claim.list`, `assertion.list`) pulls in 9 lessons including #505
at a 21% volume cost (42→51), staying within skimmability bounds. **No taxonomy
change, no lessons.md edit needed.**

## The measurement — count first

The brief says "MEASURE FIRST. Count how many lessons are genuinely
cross-cutting." The count **reframes the premise**:

| lessons matching N acts | count |
|------------------------:|------:|
| 0                       | 12    |
| 1                       | 35    |
| 2                       | 64    |
| 3                       | 69    |
| 4                       | 64    |
| 5                       | 63    |
| 6                       | 15    |
| 7                       | 10    |
| 8                       | 2     |
| **total**               | **334** |

**287 of 334 lessons (86%) already match 2+ acts.** The `classify()` function
already builds a set per act — an entry may match any number of them. The brief's
"single-home assumption that cross-cutting lessons violate" describes a bug that
does not exist in the code. The taxonomy is already many-to-many.

The #505 lesson itself — the one that went missing — already surfaces under **9
of 11 acts**. It is missing only from `red-proof` and `clock`. That is not a
taxonomy problem; it is a vocabulary gap in one anchor.

## The real bug: anchor vocabulary

The `red-proof` anchor matches `inject`, `red-proof`, `red...green`, `goes red`,
`deliberate bug`, `reinstat`, `false-red`. The #505 lesson's distinctive
vocabulary is "hollow check wearing a thorough header", "collected but never
asserted", "the header's claim-list is not the assertion-list" — none of which
the anchor reaches. Verified: `re.search(old_pattern, #505_body, re.I)` returns
`None`.

This is exactly the "small hand-maintained slice" the brief anticipated as the
right answer when the count is small.

## The fix

Widened the `red-proof` anchor by three terms in `dev/lessons_index.py`:

```python
r"|\bhollow\b|claim.list|assertion.list"
```

Impact: **42 → 51 lessons (+9, +21%)**. The 9 newly-added lessons are all
genuinely red-proof-relevant:

1. #505 — "A trace field that is collected but never asserted is a hollow check"
2. #269 — "The strongest guard evidence is a DISCRIMINATING red"
3. `getClientRects` hollow lesson
4. "commission it" review lesson
5. "resolve baseline by CONTENT" red-proof lesson
6. retired-field check lesson
7. #535 porcelain check hollow lesson
8. #672 brief evidence claim lesson (cites `lessons.md:3280`)
9. #696 check-disagrees-with-data lesson (cites `lessons.md:3280`)

Also added an honest-disclosure note to the coverage report output: the tool's
coverage depends on hand-maintained anchors nobody audits, and a lesson nobody's
vocabulary reaches is invisible — the same failure the tool exists to prevent one
level up.

## Red-proof, both directions

### Direction 1 — reproduce the miss, show it fixed

**Before** (pre-fix anchor, restored from lane-private snapshot by `cp`):
```
# act: red-proof — 42 of 334 lessons
$ python3 dev/lessons_index.py --act red-proof | grep -c "claim-list is not the assertion-list"
0
```

**After** (fix applied):
```
# act: red-proof — 51 of 334 lessons
$ python3 dev/lessons_index.py --act red-proof | grep -c "claim-list is not the assertion-list"
3
```

The discriminating output quotes the lesson text that appears — the #505 lesson
now surfaces, along with #672 and #696 which cite it. Snapshot/restore via `cp`
from lane-private scratch (`dev/lane_scratch.py snap`), never `git checkout`
(#349). Verified `cmp` identical after restore.

### Direction 2 — the case where the fix still misses

The fix widens one anchor's vocabulary; it does not change the mechanism. The
tool's coverage is still exactly as good as its most recent author's diligence,
because every lesson depends on a human writing vocabulary that reaches it. The
honest-disclosure note now says so in the tool's own output.

Two specific residual gaps the brief named:

1. **A cross-cutting lesson nobody annotated** — still possible. The anchors are
   hand-maintained regexes, not a semantic index. A lesson that uses entirely
   novel vocabulary for a known act will still be missed. The disclosure note is
   the mitigation: it tells the reader the coverage is not complete, so the count
   is not mistaken for a guarantee.

2. **An act with no slice at all** — handled (#136): an unknown act exits 2 with
   a named error listing the known acts; a known act exits 0. These render
   differently. Verified: `python3 dev/lessons_index.py --act nonexistent` exits
   2 with `unknown act 'nonexistent' — acts: ...`.

## Verification

### pytest — `test_lessons_index.py` (new file, 4 collected)

```
$ python3 -m pytest -q -n 2 test_lessons_index.py
....                                                                     [100%]
4 passed in 2.73s
```

Before/after collected counts: **0 → 4** for this file (it did not exist).

### Per-act line counts — before/after (skimmability evidence)

Only `red-proof` changed (+99 lines, 533→632, 42→51 lessons). Every other act is
unchanged — the fix touches one anchor.

| act | before | after | Δ lessons |
|-----|-------:|------:|----------:|
| red-proof | 42 | **51** | +9 |
| worktree-dispatch | 132 | 132 | 0 |
| commit | 89 | 89 | 0 |
| parsed-file | 115 | 115 | 0 |
| guard-check | 207 | 207 | 0 |
| verify-measure | 123 | 123 | 0 |
| transition-motion | 46 | 46 | 0 |
| fold-handoff | 95 | 95 | 0 |
| ui-craft | 65 | 65 | 0 |
| agent-comms | 180 | 180 | 0 |
| clock | 23 | 23 | 0 |

### `python3 lint.py` from the worktree (#607)

Exit 0. No ERRORs. WARNs are pre-existing (`questions.md` resolution dates,
#411-related) and unrelated to this change — the fix touches a tool, not a parsed
file.

### `python3 dev/redproof.py check`

```
check: calm — no injections registered (opt-in discipline; nothing to evaluate).
exit=0
```

## #702 check — unclassifiable entries surfaced

Confirmed: the default-mode output names each unclassifiable entry by line
number and first-sentence claim, not merely counts them. 12 unclassifiable
entries are listed verbatim. The test `test_unclassifiable_entries_are_surfaced_not_silent`
guards this.

## Commits

- `819bbd2e` — `fix(#761): widen red-proof anchor so hollow-check lessons surface`
- `3a26b246` — `test(#761): pin red-proof surfaces #505, skimmability, #136, #702`

## Scope touched

- `dev/lessons_index.py` — the red-proof anchor (+3 regex terms) and a
  disclosure note in the coverage output.
- `test_lessons_index.py` — new file, 4 tests.

**No lessons.md edit.** No taxonomy change. No `briefs/boilerplate.md` change.

## DOGFOOD REPORT

**Friction 1 — the brief's diagnosis was wrong, and measuring first was the
right call.** The brief framed this as a taxonomy problem ("the act taxonomy has
a single-home assumption that cross-cutting lessons violate") and offered three
options for fixing it (declare multiple acts, add a cross-cutting slice, add an
"also consider" list). Measuring took 5 minutes and showed the taxonomy already
multi-files. A lane that skipped the measurement and went straight to option 2
(cross-cutting slice) would have appended ~287 lessons to every act run,
destroying skimmability — the exact failure #612 warns about. **The brief's own
rule ("MEASURE FIRST") saved the task from its own framing.**

**Friction 2 — the line number in the brief (`lessons.md:3280`) has drifted.**
The #505 lesson is now at line 3292. The phrase "claim-list is not the
assertion-list" appears in three lessons (#505, #672, #696), all of which cite
`lessons.md:3280`. A lane following the literal line number would find the right
lesson only by luck. This is the `#607`/ledger-drift family: a citation is a
claim from the day it was written, and the file moves under it.

**Friction 3 — no dedicated test file existed for lessons_index.** The functions
(`parse_entries`, `claim_of`, `classify`) were imported by `test_watch.py`,
`test_lint.py`, `test_relay.py`, but nothing tested the tool's own act-gated
retrieval contract directly. I created `test_lessons_index.py`. A future lane
widening another anchor now has a place to add a regression test.

**Friction 4 — the brief's "Also check while you are in there" section was
already correct.** #702 (unclassifiable surfaced, not merely counted) and #136
(unknown act distinct from empty act) both hold. No fix needed; the tests pin
them.

**What I got wrong (self-caught):** my first red-proof restore command had a
typo (`cp -_RESTORE_PLACEHOLDER`), which was a no-op. I caught it by reading the
file back and re-applying the fix with `search_replace`. The lesson: even a
"restore" step needs its result verified, not assumed.
