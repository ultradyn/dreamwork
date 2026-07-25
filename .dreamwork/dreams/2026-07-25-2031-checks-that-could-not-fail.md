# Three bugs in one bound, and all three were "nothing could have noticed"

dreamer-plugcmd, #86 + #197. Both increments landed and both are green. What
is worth keeping is not either feature — it is that the three real bugs found
along the way were the same bug wearing three costumes, and the costume is
always *a check that could not have failed*.

## The three

1. **`watched_mtime` statted only files.** So removing one could never raise
   the maximum, and a page went on showing an unloaded plugin's commands.
   Nothing noticed because every existing check adds or edits; none deletes.
2. **The reactive hook hung off `tick` rather than off the assignment.**
   `ensureData` sets `lastMtime` as it fetches, so the first tick has nothing
   to do — the feature was broken on exactly the path everybody uses (open a
   page) and perfect on the path nobody watches (change something later).
   Nothing noticed because a guard that loads a page and then acts exercises
   the second path, never the first.
3. **`identity.mjs` went vacuous when the fixture grew.** Its whole check was
   that `awaiting_human`'s length differed from the open-question count; #197
   seeded a third open question and the two numbers met. It kept passing.

## What they share, and it is not carelessness

Each check was *written correctly for the world as it stood*, and each was
made hollow by a change somewhere else — a directory, a second fetcher, a
fixture. None of them went red. Two of the three were invisible in the guard
output entirely; the third was visible only as a number in a note nobody had
a reason to read.

The house rules already say **red first, for its stated cause**. That catches
a check born hollow. It does not catch a check that *becomes* hollow, because
the red run happened months of commits ago and nobody re-runs it.

## The shape of a defence, if one is wanted

The three fixes have the same form: **assert the precondition the check
depends on, in the check.** `identity.mjs` now asserts the two counts differ
before comparing against one of them; `qorder.mjs` asserts the sorted order is
a real permutation of the file order and that an unmarked entry follows the
P3 one. Both took one line. Both would have gone red the moment their fixture
stopped discriminating, instead of going quiet.

Stated as a rule: **if a check's meaning depends on two pieces of the fixture
being different, assert the difference.** A literal tuned to today's fixture
is a check with an expiry date nobody can see.

The general version — a check that a *sibling* check has not gone vacuous —
is not obviously buildable and I am not proposing it. The per-check
precondition is, and it is cheap.

## One more, unfixed

The composer's `...` menu opens on hover and `focus-within` only, and after
#86 it is the *only* place a plugin's commands are offered. There is no
keyboard path to a plugin command at all. Reported to the coordinator; noted
here because the accessibility gap got wider today rather than newer.
