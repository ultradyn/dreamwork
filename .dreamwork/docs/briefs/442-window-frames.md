# Brief — #442: the precondition counts frames that ARRIVED; the assertion needs frames INSIDE the window

Repo: `ud-dreamwork`. Worktree: **`.worktrees/window`**, branch **`wt/window`**. Do not push, do not merge.
**Never use `attn`.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are** at the
top. **Do not write `.dreamwork/handoffs.md`** — the coordinator writes that at merge time. Worktree lanes get
absolute inbox paths per `SKILL.md` (#405).

**Read `transitions.md` first** — binding, no size floor, and it opens with how to check motion.

## The finding, with its evidence

`#414` converted the last frame-rate-coupled assertion and concluded the `midFrames(...) >= 1` form is
**frame-rate-free**, so the parked design call needed no follow-up. The conversion is right; the conclusion is
too strong, and the counter-evidence was already on disk:

**`dev/capture/confirmation.mjs` has been on `midFrames(...)>=1` / `midStates(...)>=1` since `a027ad0`** — not
the count form. At `#414`'s merge it **FAILED** `popout success arrives through intermediate opacity and drift`
in a two-guard run at load **52.42**, then **PASSED solo** at load **53.06**. Same tree, same minute, *higher*
load on the passing run. So the count form was never the cause and load is not the variable: **contention
within a run is** — which is what `#414` originally observed and parked.

**The mechanism to check first.** `mid >= 1` needs a frame landing **strictly between the endpoints during the
transition window**. The precondition (`xs.length >= MIN_SAMPLES`, 3) only counts frames that **arrived**.
Under contention rAF can deliver frames clustered before and after the CSS transition rather than inside it —
so the precondition passes while `mid` is 0, and the guard reports a motion defect for a scheduling artifact.
**Verify this before fixing it.** If the real cause is something else (the trace starting late and missing the
transition entirely, the transition finishing before the first sample, a `waitFor` racing the FLIP), say so
with the measurement — the diagnosis above is mine and I may be wrong.

## What to build

Whatever the measurement supports, but the intended shape is: **the precondition should assert frames landed
INSIDE the window**, not merely that frames arrived. That is smaller and more testable than the three options
`#414` listed (quiet frame budget / measure-over-duration / deterministic clock) and needs no deterministic
clock. Consider: record the transition's start and end, count samples whose timestamps fall within it, and
make *that* the precondition — so a starved-or-misaligned trace fails as **"the trace did not sample the
window"**, distinguishable from **"the motion snapped"**.

**Reproduce it first.** A fix for an intermittent failure you have not reproduced is a guess. `just guards`
prints load per guard now, and running two guards concurrently is what produced the failure — that is your
reproduction recipe. **A one-sided value recorded after the fact proves nothing**: `#428` documents this loop
blaming its own dispatches for four runs that were confounded by a permanently loaded host, so **write down
what you expect before each run**.

## Done means all of these

1. **The failure is reproduced and its cause named with a measurement** — frame timestamps relative to the
   transition window, not a hypothesis.
2. The precondition distinguishes *"did not sample the window"* from *"snapped"*, with distinguishable first
   FAIL lines, and the fix applies to **every** guard sharing the helper (`confirmation.mjs`, `prominence.mjs`,
   `states.mjs`, `reviewsplit.mjs` — check which import from `dom.mjs` and which carry a local copy; a fix in
   one place that leaves three is half a fix, and say which you touched).
3. **Red-first, and name the production line.** Show a snap failing on the motion line and a
   starved/misaligned trace failing on the precondition line. **A green red-run is a finding, never a
   relief.**
4. **Assert the precondition your check depends on**, derived at runtime — not a literal. `#441` was filed for
   a shared floor with a 3px margin on one of two motions; do not add another.
5. `DREAMWORK_GUARDS="confirmation prominence states" DREAMWORK_HUB_GUARDS= just guards 39893` passes
   (**space-separated** — a comma is read as one filename), and passes **twice in a row** including under a
   concurrent second run, since a single pass is what made this look fixed the first time.
6. `python3 lint.py` clean; `python3 -m pytest -q -p no:randomly` passes (1078 at dispatch). **Do not run the
   full `just test`.**
7. **Do not touch :35110**, the heartbeat, the monitors, or the loop. `just deploy` now stops its own server by
   port ownership (`#431`) — do not reintroduce a pattern kill.
8. If `transitions.md`'s guidance on checking motion needs amending, do it in the same commit — single-source,
   measured by `just audit-styleguide`.

## Files

Yours: `dev/capture/dom.mjs`, `confirmation.mjs`, `prominence.mjs`, `states.mjs`, `reviewsplit.mjs`,
`transitions.md`, and `justfile` `DEFAULT_GUARDS` only if you add a `.mjs`.

**Not yours:** `watch.py`, `lint.py`, `dev/ledger.py`, `dev/deploy_state.py`, `.dreamwork/tasks.md`,
`.dreamwork/questions.md` — report exact lines instead.

## Practical

- 2 threads. `git commit --only <paths> -m 'fix(#442): …'` — **`--only`, never `git add -A`**.
- **Commit before you finish.**
- **This host is never idle** (~30 ambient, 52 during the failure, from other agents' sessions). Any criterion
  shaped like *"passes on a quiet machine"* is untestable here — see `#428`. Design for the loaded case.
- **Push back with reasons if any of this is wrong.** Tonight a lane refused what it was handed after measuring
  and that was the most valuable result of the evening. If the honest answer is *"the guard is right to fail
  under contention and the suite should serialise these two"*, argue it — that is a real answer and it changes
  the justfile, not the guards.

## Report

Say: which model you are; how you reproduced it and the frame-timing measurement that names the cause; what
you changed and in which files (and which sharers you did **not** touch and why); the exact production line
whose change reds each of the two failure modes; the two consecutive passing runs with their loads; whether
`transitions.md` needed amending; and confirmation you did not run the full `just test` or touch :35110.
