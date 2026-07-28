# Brief — #427: `lint` accepts a two-sha hand-off line and the parser still calls it malformed

Repo: `ud-dreamwork`. Worktree: **`.worktrees/handoff`**, branch **`wt/handoff`**. Do not push, do not merge.
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not write
`.dreamwork/handoffs.md`** — the coordinator writes that line at merge time.

## The defect

`#415` widened `lint.check_handoffs` to accept one-or-more shas on a hand-off line, and **correctly
declined** to reach into `watch.py`'s `HANDOFF_PENDING_RE`, because another lane's tests asserted on it at
the time. The consequence is a grammar split: `lint` is quiet about a two-sha line, and
`watch.py`'s `parse_handoffs` **still classifies it as malformed**, so `pending_handoff_records` never
surfaces its shas and the dashboard cannot read it.

This was named by the `#415` lane in its own report rather than left to be discovered, so the diagnosis is
already trustworthy — **but verify it before fixing it.** Construct a real two-sha line, feed it to
`parse_handoffs`, and show the current classification. If it already parses, the task is done and the
finding is that the ledger entry is stale — say so and stop.

## The ordering is the point

Widen `HANDOFF_PENDING_RE` and `parse_handoffs`' return shape **in the same commit** as the `test_watch.py`
assertions that read `pending[0]["sha"]`. Done in that order, `lint`'s existing reclassification becomes a
**no-op** rather than something that has to be removed later. Do not touch `lint.py`.

Decide and state: does `parse_handoffs` return a `sha` (first) plus a `shas` list, or does it change shape?
Existing callers read `pending[0]["sha"]` — **find every caller before choosing**, and say what you found.
A change that breaks a caller silently is worse than the bug.

## Done means all of these

1. **A two-sha hand-off line parses**, and `pending_handoff_records` surfaces **both** shas. Show the
   parsed structure for a one-sha line and a two-sha line side by side.
2. **Backwards compatible**: every existing caller and every existing `test_watch.py` assertion still
   passes unchanged, or, where one had to change, you name it and say why the change is correct rather
   than convenient.
3. **`file-formats.md` states the grammar** in the same commit, if it does not already state the
   one-or-more form — the repo's standing rule is that a shape a tool parses is documented where the
   parser lives, and `lint.py` checks that.
4. **Red-first, and name the production line.** Reinstate the narrow regex and watch your new test fail.
   **A green red-run is a finding, never a relief** — if the test stays green with the narrow regex in
   place, your test is not reaching the parser, and that is the more valuable result. Two tests in this
   repo were structurally incapable of failing about the single decision they were named for: one built the
   filtered list itself instead of calling the function that decides it; one had a fake return `""` for
   precisely the input that would have reached the branch. **Name the exact line whose reversion reds
   your test.**
5. **Assert the precondition your test depends on.** If the test's meaning requires the two shas to
   differ, derive both at runtime and assert the gap — a literal tuned to today's fixture is a check with
   an expiry date nobody can see. This has bitten here three times.
6. **`python3 lint.py` clean** and **`python3 -m pytest test_watch.py -q -p no:randomly` passes** (260 at
   the time of writing). **Do not run the full `just test`** and bind nothing in 39880–39899.
7. **Do not restart, `pkill` or redeploy the live dashboard on :35110.** `just deploy`'s `pkill -f`
   matches any process whose command line merely *mentions* the snapshot (`#431`); the same self-match bit
   twice more today, once from a **comment** that contained the pattern. Build process patterns from parts.

## Files

Yours: `watch.py`, `test_watch.py`, `file-formats.md`.

**Not yours:** `lint.py` (the whole point is that it needs no change), `dev/capture/*` (**a live lane holds
`above_fold.mjs` and `devoverlay.mjs`**), `review-artifact.template.html`, `.dreamwork/review/*`, and
`.dreamwork/tasks.md` / `questions.md` — the coordinator is their only writer, so report exact lines.

## Practical

- 2 threads. `git commit --only <paths> -m 'fix(#427): …'` — **`--only`, never `git add -A`**: another
  agent commits in this tree and a bare `git commit` sweeps its staged work into yours.
- **Commit before you finish.** A lane today did 24 turns of correct work and exited without committing.
- **This is a small task.** If it is genuinely a ten-line change plus a test, that is the right size —
  do not inflate it. If it turns out to be larger than it looks (the return-shape change ripples), say so
  and land a coherent smaller piece rather than a sprawling one.
- **Push back with reasons if any of this is wrong.** Every lane today that refuted its brief was right to.

## Report

Say: the current classification of a two-sha line before your fix; the shape you chose for
`parse_handoffs`' return and every caller you found; the parsed structures side by side; the exact line
whose reversion reds your test; whether `file-formats.md` needed the grammar added; and confirmation you
did not touch `lint.py`, the full `just test`, or :35110.
