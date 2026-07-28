# Brief — #414 remainder: the second frame-rate-dependent assertion, and the design call behind it

Repo: `ud-dreamwork`. Worktree: **`.worktrees/prominence`**, branch **`wt/prominence`**. Do not push, do not merge.
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are** at the
top — four lane reports tonight named a different model than was dispatched and I am tracking it.
**Do not write `.dreamwork/handoffs.md`** — the coordinator writes that at merge time. Inbox and hand-off
paths for a worktree lane are absolute, per `SKILL.md` (#405).

**Read `transitions.md` first** — it is binding, it has no size floor, and it opens with how to check motion.

## What is left of #414, and the sweep is already done

`#414` fixed `confirmation.mjs` (a frame-rate precondition naming its sample count) and then swept: **34
guards sample with `requestAnimationFrame`; only three assertions use the frame-rate-dependent
`new Set(xs).size >= N` form.** Two were `confirmation.mjs` (now guarded). The remaining one:

**`dev/capture/prominence.mjs:183`** — *"…continuously, rather than in a couple of jumps"*,
`new Set(tops.map(Math.round)).size >= 6`. It has an anti-vacuity check beside it (`total >= 8`, that the
card travelled at all) but **that measures distance, not sample count**, so a starved trace fails it the
same way. Second site, same defect, unguarded.

**`reviewsplit.mjs` already solved this and says so in a comment**, which makes it the fix rather than an
idea: `travel()` computes `mid` = *"the number of frames strictly BETWEEN the two ends"*
(`ws.filter(v => v > lo && v < hi).length`, endpoints ±1), and its comment names our exact problem — a snap
has none of those *however slowly the machine is drawing*, while a distinct-value count is capped by how
many frames arrived. `#333` landed the same shape in `states.mjs` tonight; read that too.

## Two deliverables

**1. Convert `prominence.mjs:183`** to the `mid`/`between()` form with a frame-rate precondition asserted
first and naming its sample count, matching `confirmation.mjs`/`states.mjs`. Prefer **reusing** the existing
helper over authoring a third copy — if `reviewsplit.mjs`'s `travel()` or `dev/capture/dom.mjs`'s
`midFrames`/`midStates` (landed `a027ad0`) already does it, import it and say so. **A fourth private copy of
this logic is the wrong answer**; if extraction is needed, extract.

**2. Answer the design call `#414` parks**, which is why it stayed open: the guard now fails
*informatively* on a busy machine, which is smaller than being right. Observed: FAIL inside a full
`just test` at load ~30, PASS twice solo at the same load — so **contention within the suite is implicated,
not load alone.** Choose between waiting for a quiet frame budget, measuring distinct values over a duration
rather than a fixed window, or driving the clock deterministically. **Argue the choice and its cost.** You may
land it or recommend it as its own entry with the reasoning — but the *converted assertion in (1) must land
either way*, since it no longer depends on the answer. Relevant: **this host is never idle** (~30 load from
other agents' sessions), so "run it on a quiet machine" is not available and any criterion shaped like
*"passes when the machine is calm"* is untestable here.

## Done means all of these

1. `prominence.mjs`'s assertion is about the motion, with the precondition asserted **first** and its sample
   count named in the message. No fourth copy of the helper.
2. **Red-first, and name the production line.** Break the motion and show it failing; starve the window and
   show it failing **differently**, with distinguishable first lines. **A green red-run is a finding, never a
   relief** — a check that stays green with the motion broken is not reaching it, and that is the more
   valuable result.
3. **Assert the precondition your check depends on**, derived at runtime. `#441` was filed an hour ago
   because a sibling guard's floor is a literal with a 3px margin on one of the two motions it covers — do
   not repeat that: if one constant covers two motions with different headroom, say so or split it.
4. `node dev/capture/prominence.mjs` passes, and `DREAMWORK_GUARDS=prominence,confirmation
   DREAMWORK_HUB_GUARDS= just guards 39895` passes. `python3 lint.py` clean and
   `python3 -m pytest -q -p no:randomly` passes (1078 at dispatch). **Do not run the full `just test`.**
5. **Do not touch :35110**, the heartbeat, the monitors, or the loop. `just deploy` now stops its own server
   by port ownership (`#431`) — do not reintroduce a pattern kill.
6. **`transitions.md` binds.** If it records this as debt, spend the note in the same commit; the styleguide
   is single-source and `just audit-styleguide` measures it.

## Files

Yours: `dev/capture/prominence.mjs`, `dev/capture/dom.mjs` (only to extract/share a helper),
`transitions.md`, and `justfile` `DEFAULT_GUARDS` only if you add a `.mjs`.

**Not yours:** `dev/capture/confirmation.mjs`, `states.mjs`, `reviewsplit.mjs` (read them, do not edit),
`watch.py`, `lint.py`, `dev/ledger.py`, `.dreamwork/tasks.md`, `.dreamwork/questions.md` — report exact lines.

## Practical

- 2 threads. `git commit --only <paths> -m 'fix(#414): …'` — **`--only`, never `git add -A`**.
- **Commit before you finish.**
- **Push back with reasons if any of this is wrong.** Lanes tonight that refuted their brief were right to;
  one measured four alleged defects, found all four legitimate, and refused to build the check — then
  red-proved the refusal. If `prominence.mjs`'s existing `total >= 8` turns out to be sufficient after
  measurement, **say so with the measurement** rather than converting for symmetry.

## Report

Say: which model you are; the converted assertion and which existing helper you reused (or why extraction was
needed); the exact production line whose change reds it and that the two failure modes print distinguishable
lines; how the precondition is derived; your answer to the parked design call with its cost, and whether you
landed or deferred it; whether `transitions.md` had debt to spend; and confirmation you did not run the full
`just test` or touch :35110.
