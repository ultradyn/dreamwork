# Lane report — #714: `_default_since` cannot read the fold form the repo actually writes

**Verdict: DONE.** Branch `lane-714since`, HEAD `96ed8720`, rebased clean onto
local master `9baac6f5`. Three commits, all `verb(#714):`.

## The measurement (the task)

The brief forbade simply re-casing the pattern and demanded measuring what
forms the fold commits actually take. Measured against local `master`
(`e04a8c50` at measurement time):

| form | example | count | status under old `^fold ` |
|---|---|---|---|
| `fold #NNN:` (lowercase) | `eca5699b fold #274: …` | 41 | MATCHED (case-sensitive `fold`) |
| `Fold #NNN` (capital) | `5817617c Fold #674 (merged …)` | 47 | **MISSED** — the current convention |
| `fold(#NNN):` (lane-verb) | `fold(#260): Folded line …` | ~10 | not matched (no space after `fold`) |

The convention **moved** from lowercase `fold #NNN:` to capital `Fold #NNN`
mid-history: the most recent lowercase fold is `eca5699b`, the oldest capital
`Fold` is `c8219cda`, and every fold since `eca5699b` is capital. The old
case-sensitive `^fold ` therefore anchored on a form that went extinct ~500
commits ago.

**Window consequence (measured):**
- old base (`eca5699b`): `eca5699b..master` = **555 commits**
- fixed base (`5817617c`, most-recent capital `Fold`): **63 commits**

So the default window was ~9× too wide. Every one of the 47 capital `Fold`
commits was invisible to the match.

## A second defect the measurement surfaced (not in the brief)

`git log --grep=PATTERN` searches the **full commit message, body included**,
not just the subject. Confirmed: `feat(#294)` appeared in a `^fold` match
because its body opens `fold dispatches on source_of_truth:`. The old
`_default_since` was therefore contaminated by body text in BOTH directions —
and a body line starting `fold`/`Fold` would **narrow the window past real
landings**, which is the dangerous direction for an advisory tool whose safe
error is scanning too widely, not too narrowly. This loop commits constantly,
so a lane's body line landing between two real folds is a live possibility.

Measured today: between the true most-recent fold (`5817617c`) and HEAD, zero
commits have a body-only `^fold`/`^Fold` match — so the body contamination does
not bite *today*. But it is latent, and a minimal case-insensitive `--grep`
fix leaves it open. This is the brief's direction-2 case.

## What changed and why

`_default_since` now reads subjects (`%H%x1f%s`) and matches in Python with
`_FOLD_SUBJECT = ^[Ff]old `. Two fixes in one change:

1. **Case** — `[Ff]old` reads both the extinct lowercase `fold #NNN:` and the
   current capital `Fold #NNN`. The brief's judgement call ("the tie goes to
   breadth") applies here: matching only the capital form would re-break old
   history whose last fold was lowercase, so both stay.
2. **Subject anchor** — reading `%s` and matching in Python keeps the anchor
   where the convention actually lives, refusing body contamination. A
   case-insensitive `--grep` fix would have left this open (the brief's
   direction-2 trap).

The trailing space in `[Ff]old ` refuses the `fold(#N):` lane-verb form (a
lane writing a Folded line, not a reconciliation fold) — matching it would
narrow the window to a lane commit and hide later landings. Measured today all
such commits are older than the recent real fold, but the tie goes to breadth.

Scope held: one function (`_default_since`) plus a new module-level regex.
`sweep()` itself untouched (the `#707` race the brief named).

## Both directions of every red-proof

### Direction 1 (inject the real defect, watch the check go red on the discriminating message)

Via `dev/redproof.py`: snapshotted `dev/ledger.py`, reverted `_default_since`
to the original `--grep=^fold ` form, ran the new tests.

- `test_default_since_reads_the_capital_fold_form_the_convention_now_uses` →
  **RED**, discriminating message:
  `assert 'd3fa40c01a1a…' == 'ef8e8dc1192c…'` — *"the capital `Fold #N` form —
  the repo's current convention — must be the window bound; #714 measured 47
  of these anchored out by a case-sensitive `^fold ` that could only read the
  extinct lowercase form"*. The bound landed on the lowercase fold, not the
  capital one. A width-count test would pass here (the window is non-empty);
  the boundary assertion is what catches it.
- `test_default_since_ignores_a_body_line_starting_fold` →
  **RED**, discriminating message:
  `assert 'c3f0eac6d9a3…' == 'db84845ae72f…'` — *"a body line starting `fold`
  must not narrow the window past the real fold — `git log --grep` reads the
  body and would make this non-fold commit the bound, hiding every landing
  between it and the next fold"*. The bound jumped to the `feat(#294)`
  body-contaminated commit.

Restored via `dev/redproof.py restore`, verified byte-identical. Never
`git checkout` (`#349`).

### Direction 2 (construct a case the fix still gets wrong)

- **Capital body line** (`Fold the store verbs into one module` under a
  `feat(#294)` subject): the subject anchor **correctly REFUSES** it (bound =
  the real fold). The fix handles both cases, not just lowercase.
- **Rebase reorder** (the brief's hardest named case): constructed a branch
  with an old `fold #1`, then a newer `Fold #3`, then rebased the old fold
  onto the newer one. `_default_since` returned the rebased `fold #1` (on top)
  — which is **correct**: `git log`'s default order is topological, so
  "most recent by log order" = "most recent by ancestry". The divergence the
  brief warned about only arises with `--date-order`, which neither the old nor
  the new implementation uses. **I could not construct a false-green here, and
  I name why: the topological walk makes log-order and ancestry-order agree.**
  A genuine reordering would require a future caller to pass `--date-order`,
  which is out of scope for this function.

## Cited issues with relied-on lines

- **#707** (the sibling, landed at `e04a8c50`): *"the id WAS in the subject.
  The pattern could not parse it."* Same defect class one layer down; this task
  is the same shape one layer up, and the measurement bore it out.
- **#404** (the window's purpose): *"for a same-tree lane, `git log` is a
  strictly more reliable landing channel"* — `sweep` is the primary
  landing-discovery route, and `_default_since` bounds what it scans.
- **#590** (governs reporting): *"every number is a recommendation"* — the
  window's width is reported, not enacted; a too-wide window costs read-time,
  a too-narrow one silently misses landings.
- **#671** (the cannot-check rule): *"420 commits examined, 177 open ids never
  seen"* — a window computed from a base that does not exist must not read as
  "scanned"; `_default_since` returning `None` (no fold) opens full-history
  scanning, the safe direction.
- **#612** (volume): *"A report nobody can skim is a report nobody reads"* —
  the 555→63 window reduction is itself a readability win, and the change is
  +20 lines of code, +125 of tests.

## Rebase outcome

Rebased from `e04a8c50` onto local master `9baac6f5` (master moved: `#713`
landed). Clean, no conflicts, no conflict markers (verified with the
line-anchored `grep -nE '^(<{7}|>{7}|\|{7}|={7}$)'` — exit 1). 24 sweep +
default_since tests pass post-rebase.

## Out of scope (named, not fixed)

- **`sweep()`'s own default window** still falls back to full-history when
  `_default_since` returns `None` (no fold commit at all). A repo with no fold
  gets a full scan, which is safe but unreadable for a long history — `#671`'s
  "cannot-check must not read as clean" rule may want a word printed when the
  window is unbounded. Separate task.
- **`--date-order` divergence** is closed only because no caller uses it; if a
  future caller does, the topological-log assumption breaks. Not actionable
  now.

## Files run

`python3 -m pytest test_ledger.py test_ledger_cli.py -k 'sweep or default_since'`
→ 24 passed. `python3 lint.py` → clean (6 warnings, all the expected
worktree-store-can't-travel ones). `python3 dev/redproof.py check` → clean.
No browser guards (non-UI lane).

## Dogfood report

1. **`_git_subjects` already uses `%h\x1f%s`** — the subject-anchored read my
   fix needed was already the established idiom in the sibling function ten
   lines above. Reusing it (with `%H` for the bound) kept the change to two
   lines of new logic. The repo's own patterns taught the fix; no new idiom
   invented. Worth keeping as a rule: before introducing a git-log format
   string, check what the neighbouring function reads.
2. **The brief's "do nothing is defensible" option was genuinely useful.**
   Measuring the 555-commit window against the actual noise (the `#707`
   confidence-class split already makes wide-window findings skimmable) made
   the fix/no-fix call a real judgement rather than an assumption. I chose fix
   because the body-contamination defect was latent and the safe direction is
   correctness, but the brief let me consider the alternative honestly.
3. **`git log --grep` searching the body was not in the brief and I nearly
   shipped a case-insensitive `--grep` fix that would have left it open.** The
   direction-2 red-proof framing ("construct the case your fix still gets
   wrong") is what made me test the body case — and it failed on the naive
   fix. The brief's insistence on direction 2 caught a real second defect.


