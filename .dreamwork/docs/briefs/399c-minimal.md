# Brief — #399c: one function, one rule, one test

Repo: `ud-dreamwork`. Worktree: **`.worktrees/399c`**, branch **`wt/399c`**. Do not push, do not
merge. **Never use `attn`.**

## The bug

`watch._landed_ids(text)` decides which task ids a ledger's `## Recently landed` section marks done.
Today it counts **only** entry heads (`- **#N**`) plus an `also-landed:` field. That is too narrow:
until 2026-07-27 the ledger wrote landings as **inline mentions in prose** —
`**#91** composer tweaks and **#101** scrollbar styling (2026-07-25)` — and `watch.ledger_series`
walks old revisions of the file for the burndown chart. Measured across 435 revisions: for
2026-07-25 and 07-26 the entry-head rule finds **zero** landings. The burndown guard fails because
of this, and `master` is red.

It cannot simply go back to counting every bold id, because that reads a landed entry's
`related: **#367**` marker as a landing — which is what `#399` fixed an hour ago, and it made lint
tell the coordinator to close a question the human had not answered.

## The change

In `_landed_ids`, keep the entry-head and `also-landed:` rules, and **also count a bare bold id
mention — unless it sits inside a field-anchored marker**. `related:` is the one that matters; add
any other `· word:` field you find in the landed section.

## Done means all four

1. `python3 -m pytest test_watch.py test_lint.py -q -p no:randomly` passes.
2. **`just test` exits 0.** Run it, wait for it, and do **not** pipe it — a pipeline returns the
   last command's status and that is how this bug reached `master`. Write to a file, read the file,
   quote the tail and the real exit code. **Not done until this passes.**
3. Two new tests in `test_watch.py`: an inline mention in a landed entry **is** landed; an id inside
   `related:` **is not**.
4. Two red-proofs, in opposite directions. Restore head-only ⇒ the **burndown** guard fails. Restore
   count-every-mention ⇒ `test_lint.py::TestLandedAsks::test_this_repo_has_no_forgotten_folds`
   fails. Undo each from a `cp` snapshot, not `git checkout`. After each edit run
   `python3 -c "import ast; ast.parse(open('watch.py').read())"` — a syntax error means zero tests
   ran, which is not a red.

## Two things that will waste your time if you do not know them

- **Do not edit `dev/capture/burndown.mjs`.** Its fixture uses the inline form deliberately, because
  that is what the real history looks like. Changing it turns the guard green and deletes the
  property it tests.
- **A landed entry contains prose *about* id syntax** — one documents `no bold (- #5 …), no #
  (- **5** …)` as examples. Those are in no field, so field-exclusion alone still counts `#5` as
  landed. Handle it or say plainly that you did not.

## Files

Yours: `watch.py`, `test_watch.py`, `file-formats.md`. Nothing else — `git status --porcelain`
proves it.

## Practical

- 2 threads. `just test` runs browser guards and takes ~15 minutes; budget for it.
- Commit with `git commit --only <paths> -m 'fix(#399): …'`. **Commit the fix and its tests first**,
  before the red-proofs — three previous lanes on this task died with nothing committed.
- Then append one line to
  `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/handoffs.md` (absolute path, main
  checkout): `- **#399** · landed \`<sha>\` · <YYYY-MM-DD HH:MM> · by <you> — <what>`, and commit it.

## Report

Append once, at the end, to the **absolute** path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md` — your worktree has no copy of
that file and a relative path creates one nobody reads.

Say: the real `just test` exit code and how you got it; both red-proofs with exact test names; what
you did about `#5`; and anything you are unsure of.
