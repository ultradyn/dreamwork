# Lane 764 report — self-verifying lesson citations

## Result

Implemented the title-citation form plus a live-scope numeric-citation lint. The
two live authority citations in the `#672` and `#696` lessons now quote the exact
bolded title, and `briefs/boilerplate.md` tells future lanes to verify that a title
resolves to exactly one lesson head. The lint scans only `.dreamwork/lessons.md`
and `briefs/**/*.md`; historical lane reports remain grandfathered.

Start SHA: `0363ed8f`.

Master first moved by three commits, then by six more after the report was written.
I performed both required rebases; the final base is `377da328`. Post-final-rebase
implementation SHA: `5c02aa9e`. The report commit is necessarily the next/final
branch HEAD; a commit cannot embed its own SHA.

Commits after rebase:

- `9e363555` — `fix(#764): lint drifting lesson line citations`
- `5c02aa9e` — `docs(#764): cite lessons by verifiable title`

## Re-measurement and live fixes

Before editing, the required `git grep -n 'lessons\.md:3280'` found **12 tracked
occurrences**, rather than the filing-time eight:

- historical reports: lane 628 ×2, lane 661 ×2, lane 749 ×1, and the later lane
  761 ×4 — all deliberately left unchanged;
- `.dreamwork/lessons.md` ×3: the `#672` and `#696` authority citations, plus the
  new `#764` lesson's literal specimen.

The brief named the live trio as `#505`, `#672`, and `#696`. Re-measurement showed
that `#505` no longer carried the coordinate; the just-appended `#764` lesson did.
I converted the two actual authority citations (`#672` and `#696`) to the exact
title. I retained `#764`'s literal `lessons.md:3280` as the historical specimen
that explains the defect, and corrected that lesson's blast-radius paragraph to
distinguish filing-time measurement from lane-start reality.

I considered all historical lane reports and left them untouched, as required by
the four grandfathering rulings. I did not attempt to rewrite either merge commit
message.

`briefs/boilerplate.md` did not contain `3280`, but prospective lint measurement
found two other live stale coordinates there:

- `lessons.md:2704` resolved to continuation prose;
- `lessons.md:3295` resolved to a blank line.

Both are now exact title citations. Before the fixes, the scoped measurement was
8 numeric citations / 2 non-head targets. After the rebase it is 4 / 0.

## Reproducible rot

Before editing, the requested commands returned:

```text
$ sed -n '3280p' .dreamwork/lessons.md
- **A #535 porcelain check keyed on MASTER's head sha is hollow against a
$ sed -n '3292p' .dreamwork/lessons.md
- **A trace field that is collected but never asserted is a hollow check wearing a thorough header** (2026-07-30, #505 phase-2 gate). ...
```

Thus `3280` pointed at a real but unrelated lesson head, while the intended title
was at `3292`. The full intended title currently has one lesson-head match; the
same title text occurs in three lesson entries after the two authority citations
were repaired, which is why the boilerplate says to count **head** matches rather
than accept the first unanchored grep result.

## IGC decision

Context: fix current live citations without rewriting history, while leaving a
bounded check that is quiet on healthy live text.

| Idea | All | G1 | G2 | G3 | G4 |
|---|:---:|:---:|:---:|:---:|:---:|
| Exact bolded titles only | ✘ | ✔ | ✔ | ✘ | ✔ |
| Stable `L001…` ids | ✘ | ✔ | ✔ | ✔ | ✘ |
| Exact titles + scoped line lint | ✔ | ✔ | ✔ | ✔ | ✔ |

- G1: a reader verifies the subject without opening a numeric coordinate.
- G2: no advisory fires on the healthy live tree.
- G3: remaining legacy coordinates drifting into prose/blank/out-of-range are loud.
- G4: the change is bounded; no roughly 334-entry backfill.

Title-only fails G3: remaining legacy coordinates can still drift mechanically.
Stable ids fail G4 because they require the backfill the brief measured. Titles
plus scoped lint is the sole survivor and is what shipped.

## What the check decides — and cannot decide

`check_lesson_line_citations` resolves every `lessons.md:<number>` occurrence in
`.dreamwork/lessons.md` and `briefs/**/*.md`. It WARNs with source location and the
actual target-line content when the coordinate is blank, continuation prose, or
out of range. It deliberately ignores `.dreamwork/lane-*-report.md` history.

It cannot decide semantic intent. A stale coordinate that lands on a different
valid lesson head passes; `lessons.md:3280` is exactly that case. The test
`test_a_wrong_but_valid_lesson_head_is_beyond_the_check` makes this limitation
executable rather than hiding it behind the OK row.

Direction 2 findings for the title form:

1. An unanchored grep for the chosen title now sees three textual occurrences;
   accepting its first hit can mislead. The form therefore requires exactly one
   **lesson-head** match. Two lesson heads with the same title would remain
   ambiguous and must be reported, not guessed.
2. Drifted whitespace, line wrapping, or smart quotes makes exact grep return zero.
   That is visible failure rather than silent misresolution, but the reader still
   has to treat zero as unresolved.
3. The numeric lint can prove structure, not subject. A valid-but-wrong head is
   the original disease and remains outside this check's authority.

## Red proof

Direction 1 used `dev/redproof.py begin lint.py` after the fixed file existed. I
injected `if actual is not None:` so continuation prose was falsely accepted. The
focused test failed on the discriminating message:

```text
E       AssertionError: [('OK', '1 numeric citation(s) resolve to lesson heads')]
E       assert (1 == 1 and 'OK' == 'WARN'
```

`dev/redproof.py restore lint.py` then reported that the original was restored and
verified. The required pre-report check output, verbatim:

```text
history: examined 3 commit(s) since 377da328becc (master) against 1 injected path(s); read 3 blob(s), 0 holding a recorded injection.
check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits:
  lint.py (sha 8c76f070cb08, hint: 'if actual is not None:')
```

The brief's Direction-1 clause also said a head-only check should name the three
`3280` lesson entries before the fix. That is impossible for the specified check:
line 3280 was itself a valid lesson head. The brief's Direction-2 clause correctly
states the contradiction later: such a check “would have passed on `3280` the
whole time.” I followed the sharper constraint, proved the mechanical failure the
check can detect, and report the semantic limit explicitly.

## Verification

- Before: 539 tests collected across `test_lint.py` and
  `test_lessons_index.py`.
- After: 543 tests collected.
- `just pytest -q -n 2 test_lint.py test_lessons_index.py` — exit 0, 100%.
- `python3 lint.py` — exit 0, no ERRORs. Six WARNs, all matching the worktree
  baseline categories: three undated answered entries; absent worktree ledger;
  absent worktree status; zero-entry related-marker check; one pre-existing
  near-duplicate pair; and the aggregated seven skipped ledger checks.
- `python3 lint.py --target /home/xertrov/.llm-general/skills/ud-dreamwork` —
  exit 0, no ERRORs. It correctly names the two unfixed coordinates still present
  in the main-checkout subject and quotes their actual lines; the other two WARNs
  are the existing undated-answer and near-duplicate findings. This is the
  requested before-merge live-count measurement with the worktree interpreter.
- Post-rebase scoped measurement: 4 numeric citations, 0 non-head targets.
- Line-anchored diff3-marker scan over all edited files: no matches.
- No browser guards or ports were used.

## Durable state changed

- `.dreamwork/lessons.md` — repaired live authority citations and corrected the
  `#764` measurement narrative.
- `briefs/boilerplate.md` — exact-title citation contract and two live repairs.
- `lint.py` — scoped numeric-citation resolver.
- `test_lint.py` — four tests including scope/grandfathering and the intentional
  valid-but-wrong-head limit.
- `.dreamwork/lane-764-report.md` — this report.

## DOGFOOD REPORT

1. The brief's demand that the proposed head-only lint name the stale `3280`
   entries conflicts with its own later, correct statement that `3280` points at
   a valid-but-wrong head and therefore passes that check. This is the main task
   friction; the report preserves both facts instead of manufacturing a red.
2. Filing-time spread was already stale: lane 761 added four historical
   occurrences, `#505` no longer had the citation, and the new `#764` lesson
   itself became the third live literal occurrence. The mandatory re-measurement
   prevented editing the wrong lesson.
3. `codebase-memory-mcp` indexing crashed twice on a file, so code discovery had
   to fall back to targeted source reads after the required retries.
4. The required `just pytest -q ...` recipe expands to `pytest -q -q`; its final
   output shows 100% and exit 0 but suppresses the passed-count summary. I ran a
   separate collect-only measurement to make the requested 539→543 count explicit.
5. No unflagged conflict with `briefs/boilerplate.md` was found. The lane brief's
   prohibition on writing live status/ledger state correctly overrode coordinator
   initialization behavior; no such state was written.
