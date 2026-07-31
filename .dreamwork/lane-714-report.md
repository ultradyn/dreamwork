# Lane report — #714: `_default_since` cannot read the fold form the repo actually writes

**Status: IN PROGRESS.** Measurements below are complete; implementation follows.

## The measurement (the task)

The brief forbade simply re-casing the pattern and demanded measuring what
forms the fold commits actually take. Measured against local `master`
(`e04a8c50` at measurement time):

| form | example | count | status under current `^fold ` |
|---|---|---|---|
| `fold #NNN:` (lowercase) | `eca5699b fold #274: …` | 41 | MATCHED (case-sensitive `fold`) |
| `Fold #NNN` (capital) | `5817617c Fold #674 (merged …)` | 47 | **MISSED** — the current convention |
| `fold(#NNN):` (lane-verb) | `fold(#260): Folded line …` | ~10 | not matched (no space after `fold`) |

The convention **moved** from lowercase `fold #NNN:` to capital `Fold #NNN`
mid-history: the most recent lowercase fold is `eca5699b`, the oldest capital
`Fold` is `c8219cda`, and every fold since `eca5699b` is capital. The current
case-sensitive `^fold ` therefore anchors on a form that went extinct ~500
commits ago.

**Window consequence (measured):**
- current base (`eca5699b`): `eca5699b..master` = **555 commits**
- corrected base (`5817617c`, most-recent capital `Fold`): **63 commits**

So the default window is ~9× too wide. Every one of the 47 capital `Fold`
commits was invisible to the match.

## A second defect the measurement surfaced (not in the brief)

`git log --grep=PATTERN` searches the **full commit message, body included**,
not just the subject. Confirmed: `feat(#294)` appeared in a `^fold` match
because its body opens `fold dispatches on source_of_truth:`. The current
`_default_since` is therefore contaminated by body text in BOTH directions —
and a body line starting `fold`/`Fold` would **narrow the window past real
landings**, which is the dangerous direction for an advisory tool whose safe
error is scanning too widely, not too narrowly. This loop commits constantly,
so a lane's body line landing between two real folds is a live possibility,
not theoretical.

Measured today: between the true most-recent fold (`5817617c`) and HEAD, zero
commits have a body-only `^fold`/`^Fold` match — so the body contamination does
not bite *today*. But it is latent, and the minimal case-insensitive `--grep`
fix leaves it open. This is the brief's direction-2 case (the one a naive fix
still gets wrong).
