# Lane report — #707: widen SWEEP_SUBJECT to the forms the repo actually writes

**Verdict: DONE.** The primary landing-discovery route is no longer blind to the
repo's dominant commit forms. Branch `lane-707sweep`, HEAD `cbbde380`, rebased
clean onto local master `754aab93`. Three commits, all `verb(#707):`.

## What changed and why

`SWEEP_SUBJECT` matched only `verb(#N)`, so every coordinator `Merge #N:` and
every bare lane `#N:` commit was invisible to the tool whose job is discovering
landings. #671 measured 1697 unattributable commits; the live instance in #707's
own notes showed the merge form is the one that matters most.

The pattern is widened to three alternatives, each its own capture group so
`_subject_class` can tell them apart:

| alternative | example | confidence | why |
|---|---|---|---|
| `verb(#N)` | `fix(#688):`, `merge(#422,#403):` | high | the verb carries landing intent |
| `Merge`/`Fold #N` | `Merge #688: branch reachability` | lower | likely already folded |
| `#N` + separator | `#700: the gate is a file` | lower | verb is ambiguous |

Built on `_skip_shape` rather than bypassing it (the brief's instruction): the
widened forms flow into findings at lower confidence via `_subject_class`, and
`sweep_text` splits the report into **two summary lines** — verb findings and
widened findings — so a reader can dismiss a `Merge #688:` or `#700:` in one
glance without opening the commit.

Report wording changed: **"names"**, not "names a landing for". Sweep can only
know an id was NAMED; whether a naming is a landing is the reader's judgement
(#590: a count is a question, never a verdict; #136: "named" must not read as
"landed").

#404's four pins on `sweep()` hold: the pure function still returns
`(n, findings)` with the same subtraction rule; only the report splits.

## Both directions of every red-proof

### Direction 1 (inject the real defect, watch the check go red on the discriminating message)

Reverted `SWEEP_SUBJECT` to verb-only (restored from lane-private snapshot at
`~/.cache/ud-dreamwork/lane-scratch/ud-dreamwork/lane-707sweep/snap/`).
All 7 new tests went RED:

- `test_sweep_subject_widened_to_match_the_coordinator_merge_form` →
  `AssertionError: the coordinator merge form — every landing this loop records — must now match; #707 measured it invisible` / `assert None`
- `test_sweep_finds_a_merge_prefixed_landing_it_previously_missed` →
  `AssertionError: a Merge #10: landing for an open id whose entry does not cite the sha must now be found — #707 measured this class invisible` / `assert 10 in {}`
- `test_sweep_report_names_the_coordinator_merge_form_with_a_confidence_class` →
  `AssertionError: the Merge #10 landing (b92c2d4) must now be named — #707 measured this class invisible to the primary route` — and the live un-widened report read `0 id-bearing, 2 skipped, mostly already-landed`, the exact "cannot parse what landed" failure.
- (plus the bare-#N, the subtraction-precondition, and the split tests)

The discriminating message is the **confidence-class line** (`"lower confidence"`),
not the count: a report that folded Merge/#N into the verb findings would name
the id but hide that it is lower confidence — the trap the brief warns about.

Restored via `cp` from snapshot, verified `cmp` identical to the implemented
version. Never `git checkout` (#349).

### Direction 2 (construct a commit the widened pattern reports as a landing that is not one)

**The live `docs(#691,#700)` case** — CLOSED by classification + verb visibility,
not by pattern exclusion. `docs(#691,#700): Q1 is settled...` names #691 because
it is *about* #691, not because #691 landed. My classifier puts it in the
high-confidence "verb" class (because `docs(#N)` matches the verb form), which is
technically a misclassification. But the brief's own design input closes it: the
report carries the verb, so a reader dismisses #691 in one glance — that is #612's
"triage in one pass." Downgrading all `docs`/`test`/`design` to low confidence
would bury real doc/test/design landings, which is worse. **This is the one open
false-green and I name it: a weak verb (`docs`/`test`/`design`) that names an id
it is about rather than lands is classified as high-confidence "verb".** The
closure is honest: the verb is visible, so the cost is one glance, not a wrong
fold.

**The nastier cases the brief demanded:**
- `revert(#10): undo the bad fix` → **correctly NOT matched** (`revert` is not in
  the verb set). No false attribution.
- `Revert "fix(#10): bad"` → **correctly NOT matched** (the `#N` is inside quotes,
  not anchored at head; `Revert` isn't a verb). No false attribution.
- `fix(#10): re-apply after revert` → matched as verb. **Correct** (it IS a re-landing).
- `docs: notes on fix(#10) from last week` → **correctly NOT matched** (#10 in prose,
  not anchored).

So the only class the widening gets wrong is the pre-existing `docs(#N)` weak-verb
class, and it is closed by visibility rather than exclusion.

## Cited issues with relied-on lines

- **#404** (the premise): *"a git sweep that finds nothing prints the same as one
  that ran wrong. Whatever gets built reports how many commits it examined, not
  just what it found"* — and the "by construction" claim this task breaks: *"this
  repo's commit convention already puts the id in the subject... So the id is in
  git by construction."* #707 shows the id WAS in the subject; the pattern could
  not parse it.
- **#671** (measured the scale): *"1697 name an id in a form sweep cannot
  attribute (`Merge #667:`, `Fold #667`, `#667: hand-off`)"*. This is the
  unattributable count the widening recovers.
- **#590** (governs the report wording): *"a non-zero count is a QUESTION, never
  a verdict"* — carried verbatim into `reach()`'s docstring and now into sweep's
  split report.
- **#136** (the failure being fixed): *"present-but-unparseable is a fault and
  must look like one"* — "nothing landed" and "I could not parse what landed" must
  not render identically. The widened report names what it parsed and carries the
  verb so the two are distinguishable.
- **#612** (volume, constraint on the output): *"A report nobody can skim is a
  report nobody reads"* — the two-section split keeps the report triageable; the
  change is +24 lines in `ledger.py`, +173 in tests, not a classifier taxonomy.

## Rebase outcome

Rebased from `6a60a45a` onto local master `754aab93` (master moved while I worked).
Clean, no conflicts, no conflict markers (verified with the line-anchored
`grep -nE '^(<{7}|>{7}|\|{7}|={7}$)'` — exit 1). 19 sweep tests pass post-rebase.

## Live measurement (static probe, load ~23)

`sweep` against the live repo now finds **4 additional ids** in widened form that
were invisible before, including `#630 — Merge #630: component-transition plan`
(a real coordinator merge) and `#465`/`#572`/`#691` (bare `#N:` lane forms). The
report splits them: `1 open id(s) git names (verb form)` + `4 more named in
widened form (Merge/#N — lower confidence, likely folded or ambiguous; #590)`.

## Out of scope (named, not fixed)

- **`_default_since` greps `^fold ` case-sensitively** while the convention became
  `Fold #NNN` — noted in #671's landing note. The default window is ~445 commits
  wide instead of 1. Erring toward more scanning is safe for an advisory tool, but
  it means the live measurement above scanned since `eca5699` rather than the most
  recent fold. A separate task.
- **The `docs(#N)` weak-verb false-green** is the one class the widening (and the
  original pattern) misclassifies as high-confidence. Closed by verb visibility,
  not by exclusion; downgrading would bury real landings. Named above.

## Files run

`python3 -m pytest test_ledger.py test_ledger_cli.py -k sweep` → 19 passed.
`python3 lint.py` → clean (6 warnings, all the expected worktree-store-can't-travel
ones). No browser guards (non-UI lane).

## Dogfood report

1. **`just pytest -q` does not work** — `just` has no `-q` passthrough, so the
   brief's "`just pytest -q <files>`" instruction misfires; I used `python3 -m
   pytest`. Minor, but a lane copy-pastes the brief's form and loses a turn.
2. **The brief's red-proof direction-2 framing was the most useful part.** It
   forced me to construct the `revert(#N)` and subject-quoting cases, and two of
   four were genuine finds (revert correctly excluded; `docs(#691)` closed by
   visibility not exclusion). Without it I would have shipped a one-directional
   red-proof and called the `docs(#691)` case "handled" without arguing why.
3. **The `_subject_class` reuse of `_skip_shape`'s categories** was the right
   seam — the brief said "build on it, do not bypass it" and that constraint
   produced a cleaner design than a fresh classifier would have. Worth keeping
   as a rule: when widening a filter, reuse the existing discriminator.
