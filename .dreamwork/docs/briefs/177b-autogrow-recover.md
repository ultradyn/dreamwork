# Brief — #177 recovery: a lane left correct work uncommitted; verify it and land it

Repo: `ud-dreamwork`. Worktree: **`.worktrees/autogrow`** (it already exists — **do not create it**), branch
**`wt/autogrow`**. Do not push, do not merge.
**Never use `attn`.** **Do not write `.dreamwork/handoffs.md`** — the coordinator writes it at merge time.
Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are**.

## The situation

A previous lane implemented `#177` (text boxes grow with what he types, then scroll) and **exited without
reporting and without committing its second half**. Its first commit landed on the branch:
`95a83fb feat(#177): composer + answer boxes grow with content, then scroll`.

**Uncommitted in the worktree right now — this is the work to rescue, not redo:**

- `dev/capture/autogrow.mjs` (371 lines, untracked) — the guard.
- `justfile` — `autogrow` appended to `DEFAULT_GUARDS`.
- `watch.py` — a `fitText` change: on a **restore** (tick, draft) it snaps to the target height and *then*
  restores the standing transition, so the box does not re-grow under him on every tick while the next
  character he types still travels. Plus a `snapshotCardState` comment explaining the height is re-fit from
  restored content rather than carried.
- `_capture-autogrow.mjs` — scratch. **Do not commit scratch.**

**Read the original brief** `.dreamwork/docs/briefs/177-composer-autogrow.md` for the acceptance criteria, and
**read the diff before trusting any of it.** Your job is to verify, finish, and commit — not to re-implement.
If something in it is wrong, fix it and say what and why.

## What to verify — in this order

1. **`git diff` and read it.** Then state in your report whether the `fitText` restore branch is correct:
   specifically that a status tick does not reset the height mid-typing (`#118`'s tick-survival), and that the
   *next* keystroke still animates.
2. **His numbers are the contract**: composer starts 2–3 rows and grows to 10–15; answer/note starts 2 and
   grows to 6, then scrolls. **The ceilings are deliberately different** — a 15-line box inside a question card
   would shove the list. Confirm what is implemented matches, and say the actual numbers you found.
3. **Run the guard**: `DREAMWORK_GUARDS="autogrow" DREAMWORK_HUB_GUARDS= just guards 39891` (**space
   separated** — a comma is read as one filename). It must pass.
4. **Red-first, and name the production line.** Neutralise the height transition and show the motion check
   failing; **a green red-run is a finding, never a relief** — if it passes with the transition removed, the
   guard is not reaching the motion and **that is the finding to report**, more valuable than a green run.
   Also prove the tick-survival step reds: make a tick reset the height and watch it fail.
5. **`transitions.md` binds with no size floor** — and note what landed tonight in `#442`: **a compositor-driven
   CSS transition (opacity/transform) is invisible to a starved rAF sampler**, so `transitionstart` is the
   load-independent snap detector; `framesInWindow`/`transitionWindow` are exported from `dev/capture/dom.mjs`.
   A **height** transition is main-thread layout, so rAF sampling should work — but **if this guard proves flaky
   under load, use the `#442` shape rather than inventing a third one**, and say which you used.
   **`dev/capture/dom.mjs` and `confirmation.mjs` are held by another lane right now** — read and import them,
   do not edit.
6. **Assert the precondition your checks depend on**, derived at runtime, not a literal. If one threshold covers
   both boxes with different ceilings, split it or justify one value — `#441` was filed tonight for exactly that.
7. **`watch-design.md` is authoritative and single-source**: the two ceilings and the gesture must be documented
   in the same commit. `just audit-styleguide` measures it. Check whether the previous lane did this; if not, do.
8. `python3 lint.py` clean; `python3 -m pytest -q -p no:randomly` passes (1078 at dispatch). **Do not run the
   full `just test`.** Do not touch :35110, the heartbeat, the monitors, or the loop.

## Files

Yours: `watch.py`, `justfile`, `dev/capture/autogrow.mjs`, `watch-design.md`, `test_watch.py`.

**Not yours:** `dev/capture/dom.mjs`, `confirmation.mjs`, `transitions.md` (**held for `#444`**),
`file-formats.md` (**held for `#402a`**), `review-artifact.template.html` and `.dreamwork/review/src/**`
(**held for `#436`**), `lint.py`, `dev/ledger.py`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`.

## Practical

- 2 threads. `git add dev/capture/autogrow.mjs` then
  `git commit --only dev/capture/autogrow.mjs justfile watch.py watch-design.md -m 'feat(#177): …'` —
  **`--only`, never `git add -A`**: five agents are committing in this tree right now, and `git add -A` would
  sweep the scratch file and their work in too. **Delete `_capture-autogrow.mjs` or leave it untracked; never
  commit it.**
- **COMMIT BEFORE YOU FINISH.** This brief exists because a lane did not. If you run low on room, commit what
  is verified and say what remains.
- **This host is never idle** (~25–50 load from other sessions) — see `#428`. Do not write a check whose pass
  condition assumes a quiet machine.

## Report

Which model you are; whether the rescued diff was correct and what you changed; both ceilings as actually
implemented; the guard result; the exact production line whose change reds each of the motion and
tick-survival checks; which motion-checking shape you used and why; what `watch-design.md` gained; and
confirmation you did not commit scratch, run the full `just test`, or touch :35110.
