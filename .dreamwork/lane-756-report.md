# Lane #756 report

## Verdict

Fixed. The standing boilerplate now makes lint and pytest bars command-, snapshot-, and interpreter-relative instead of pinning moving totals. It names the worktree-only lint warning messages, tells lanes to inspect every WARN message rather than totals or labels, gives the worktree-interpreter/main-target invocation, and warns that a stale interpreter need not understand current live state. It also replaces the unreachable `just pytest -q <files>` form with the supported `python3 -m pytest -q <files>` form.

Post-rebase commits: `162e1ea7 docs(#756): make lane verification bars command-relative`; `60ffb467 fix(#756): remove unreachable lane pytest command`.

## Measurements and verification

- Bare worktree `python3 lint.py`: `clean (6 warning(s))`. The two shared warnings were `questions.md` missing resolution dates and `lessons.md` near-duplicates. The four extra worktree/state rows were: `tasks.md` ledger absent; `status.json` absent; `tasks.md` examined 0 entries; and `ledger checks` examined nothing.
- Worktree interpreter over live main data, `python3 lint.py --target /home/xertrov/.llm-general/skills/ud-dreamwork`: `clean (2 warning(s))`. This is the direction-1 demonstration: the same interpreter produced 6 warnings for the worktree subject and 2 for the live subject, with the four named rows accounting for the difference.
- `just lint` and `python3 lint.py` were semantically identical (`rc 0`, `clean (6 warning(s))`); `just` only echoed `python3 lint.py`. The boilerplate therefore names the direct Python form as the one supported way.
- Before edit, `python3 -m pytest test_lint.py`: 535 collected/passed. After final edit and again after rebasing: 535 passed (final run: `535 passed in 71.70s`). The whole repo measured 2326 collected tests, already two above the quoted 2324, while the prescribed focused `test_lint.py` run collects 535. A whole-repo count is technically reachable but is not the bar for the required focused run.
- The prior boilerplate command `just pytest -q test_lint.py` was not reachable: `error: Justfile does not contain recipe '-q'`. The replacement direct pytest command accepts file arguments.
- `python3 dev/redproof.py check`: `check: calm — no injections registered (opt-in discipline; nothing to evaluate).`
- `git diff --check`: clean. `python3 lint.py`: NO ERRORs.

## Red-proof

Direction 1 was the required demonstration rather than a prose test: bare worktree lint ended `clean (6 warning(s))`; the explicit main target ended `clean (2 warning(s))`; the complete output showed precisely the four worktree/state rows listed above.

Direction 2 produced two real misleading cases and the final wording closes both:

1. `status.json absent` is conditional. It can disappear while a genuinely new warning appears, preserving a total of 6; a second warning can also reuse an existing `questions.md`/`lessons.md` label. The boilerplate therefore says to inspect every WARN **message** against the measured baseline, not totals or labels, and says the named worktree rows *may* occur.
2. A worktree created before the store cutover can carry a stale interpreter. The interpreter from pre-store commit `2a491111`, run against today's main target, returned `1 error(s), 26 warning(s)` including `ERROR tasks.md no Next id header`. The boilerplate therefore no longer promises that any worktree interpreter reproduces today's live output; it states that a stale interpreter need not do so.

The pre-store case does not justify historical brief edits: a previously dispatched lane reads its copied brief head, while a current lane gets this boilerplate and must rebase before reporting. I considered mass-editing historical briefs and deliberately did not: #398 measured the forward cutoff as “3 brief(s) in scope after hand-off obligation, 27 grandfathered”; #405 says older brief lines “are history and are left alone; the fix is forward-only”; and #587 records “Grandfathering upheld with an argument”. The requested change is forward-only in `briefs/boilerplate.md`.

## Relied-on issue lines

- #607: “The path you invoke is the INTERPRETER, while --target is only the SUBJECT.” This determined the explicit worktree-interpreter/main-subject wording.
- #611: “ONE row naming all six, not six rows” because repeated store-absence rows create the volume failure. This supported naming the artifact class compactly rather than adding a section.
- #667: “The ledger sqlite is gitignored, so it does not travel into a worktree.” This is the cause of the extra worktree rows.
- #400: “The lessons that reach a lane are the ones I hand-copy into its brief, and nothing else does.” This is why the correction belongs in the standing boilerplate.
- #612: “A report nobody can skim is a report nobody reads.” The actual addition remains two source lines, not a new section.
- #671: the broken sweep combined a real count with a false conclusion and “read as a positive all-clear.” This is why the wording rejects pinned totals and demands inspection of what was examined.
- #440: “a single supported way” prevents hand-rolled alternatives. `just lint` was equivalent, so the boilerplate names direct `python3 lint.py`; `just pytest -q <files>` was not equivalent or supported, so it was replaced.
- #737: “MEASURED, then built nothing — the right outcome for a task whose head said MEASURE FIRST.” The pytest measurement did require a small correction because the quoted total and the prescribed focused command were demonstrably different bars.
- #349: “Revert a deliberate RED injection with the inverse of the injection, never with `git checkout <file>`.” No injection was needed for the wording demonstration, and no checkout restore was used.
- #726: `redproof.py`'s old path conversion “cannot inject anywhere under .dreamwork/”. No `begin` was attempted on the dotfile report; the required `check` was run directly.

## Rebase outcome

`master` advanced by 8 commits to `f1f588b7` after the first verification. `git rebase master` replayed all three #756 commits cleanly with no conflict resolution; the anchored four-form marker sweep found no markers. Historical briefs, `lint.py`, `test_lint.py`, the justfile, and all off-limits files were left untouched.

## DOGFOOD REPORT

The boilerplate itself carried a second unreachable verification instruction: `just pytest -q <files>` treats `-q` as a recipe name because the `pytest` recipe accepts no arguments. This was the same failure class as the task—lanes could not reach the stated bar—and was corrected in the same file. The initially drafted lint sentence also overclaimed that four WARNs were invariant and that any worktree interpreter could reproduce live output; the independent second thread constructed both counterexamples before handoff, and the wording now carries those limits explicitly. No further friction found.
