# Brief — #333: the sixth holder of the forbidden count idiom, and the last live one

Repo: `ud-dreamwork`. Worktree: **`.worktrees/states`**, branch **`wt/states`**. Do not push, do not merge.
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are** at the
top — three lane reports tonight named a different model than was dispatched and I am tracking it.
**Do not write `.dreamwork/handoffs.md`** — the coordinator writes that at merge time. Inbox and hand-off
paths for a worktree lane are absolute, per `SKILL.md` (#405).

Lane-owns: dev/capture/states.mjs, transitions.md

## The defect

**Read `transitions.md` first — it is binding and it opens with how to check motion.** Its count rule:
**never assert an absolute count of distinct positions.** `uniq(positions).length >= 8` is a fact about how
many frames the machine drew, not about the motion. Five guards encoded that idiom and all five are converted.

`dev/capture/states.mjs:114,118,122` holds **three more** — `uniq(upH).length >= 6`, `uniq(dnH).length >= 6`,
`uniq(tkH).length >= 6` — and its line 134 comment instructs *"count intermediate positions"*. Measured
2026-07-27: **these are the only live instances left in `dev/capture/`**; every other grep hit is a comment
recording its own conversion.

The doc half is done (`transitions.md` names the exception and calls it a debt). **Remaining: convert the
three to `between()` with the vacuity precondition the rule requires, red-first.**

## Two things that will bite you

1. **`states.mjs:164-165` uses `<= 3` to assert reduced-motion does NOT animate.** That is the *opposite*
   assertion and **must stay a count** — converting it would destroy the check. Say explicitly in your report
   that you left it alone and why.
2. **`#414` changed what the right idiom IS.** It landed a *frame-rate precondition* first, so a starved
   window fails with a named "sampled enough to see motion (N frames)" message instead of masquerading as a
   motion bug. Read `dev/capture/confirmation.mjs` for the shape and follow it — a converted assertion
   without that precondition has two failure modes printing one line, which is the defect `#413` spent six
   hours miscategorised on.

## Done means all of these

1. The three counts are `between()`-style assertions about the *motion*, each with the vacuity/frame-rate
   precondition asserted **first** and naming its sample count.
2. **The line-134 comment no longer instructs the banned idiom.**
3. **Red-first, and name the production line.** Break the motion (or starve the window) and show the
   converted assertion failing with the *right* message for the *right* reason. **A green red-run is a
   finding, never a relief** — if it stays green the check is not reaching the motion, and that is the more
   valuable result. Show both failure modes printing distinguishable lines.
4. **Assert the precondition your check depends on.** If a check's meaning needs two sampled values to
   differ, derive both at runtime and assert the gap; a literal tuned to today's frame rate is a check with
   an invisible expiry.
5. `node dev/capture/states.mjs` passes on its own ephemeral port. `python3 lint.py` clean and
   `python3 -m pytest -q -p no:randomly` passes (1078 at dispatch). You may run
   `DREAMWORK_GUARDS=states DREAMWORK_HUB_GUARDS= just guards 39896`. **Do not run the full `just test`.**
6. **Do not touch :35110**, the heartbeat, the monitors, or the loop. Note `just deploy` now stops its server
   by port ownership rather than `pkill -f` (`#431`), so do not reintroduce a pattern kill.
7. **`transitions.md` binds with no size floor.** If the debt note it carries about these three is now spent,
   update it in the same commit — the styleguide is single-source and `just audit-styleguide` measures it.

## Files

Yours: `dev/capture/states.mjs`, `transitions.md`, and any shared helper under `dev/capture/` you extract
(plus its `justfile` `DEFAULT_GUARDS` / `lint.NOT_GUARDS` registration if it is a new `.mjs`).

**Not yours:** `dev/capture/confirmation.mjs` and `prominence.mjs` (read them, do not edit), `watch.py`,
`lint.py`, `dev/ledger.py`, `.dreamwork/tasks.md`, `.dreamwork/questions.md` — report exact lines instead.

## Practical

- 2 threads. `git commit --only <paths> -m 'fix(#333): …'` — **`--only`, never `git add -A`**.
- **Commit before you finish.**
- **Push back with reasons if any of this is wrong.** Several lanes tonight were right to refute their brief;
  one refused what it was handed after measuring, and that was the most valuable result of the evening. If
  one of these three counts turns out to be a legitimate opposite-assertion like line 164, **do not convert
  it** — say so with the measurement.

## Report

Say: which model you are; the three converted assertions; how each precondition is derived and asserted; the
exact production line whose change reds your check and that both failure modes print distinguishable lines;
that you left `164-165` as a count and why; whether `transitions.md`'s debt note is now spent; and
confirmation you did not run the full `just test` or touch :35110.
