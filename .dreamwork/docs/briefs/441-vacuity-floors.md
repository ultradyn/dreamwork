# Brief — #441: one vacuity floor covers two motions with 10x different headroom

Repo: `ud-dreamwork`. Worktree: **`.worktrees/floors`**, branch **`wt/floors`**. Do not push, do not merge.
**Never use `attn`.** **Do not write `.dreamwork/handoffs.md`** — the coordinator writes it at merge time.
Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are**.

**Read `transitions.md` first** — binding, no size floor.

## The defect

Read `#441` in `.dreamwork/tasks.md`. `#333` converted `states.mjs`'s count-idiom assertions correctly, and its
vacuity check uses a **literal** `MIN_HEIGHT_SPAN = 20`, justified as *"well below measured 193px fold / 23px
tick-grow"*. For the fold that is a 10x margin. **For tick-grow it is 3px.**

One constant, two motions, wildly different headroom — and the margin is **invisible in the guard output**. A
chrome change that shaves the tick-grow travel by 15% takes it under the floor, and the guard then reports a
*vacuity* failure for a motion that is merely smaller. The repo's rule is explicit: a literal tuned to today's
fixture is a check with an expiry date nobody can see.

**It fails safe today** (a too-high floor reds, it does not pass silently), so this is P3 — correctness of the
*diagnosis*, not of the check.

## What to do

Derive the floor per motion rather than sharing one constant. **Argue the shape**: a fraction of the observed
span, a per-motion constant with its measurement recorded beside it, or a floor derived from the declared CSS.
Whatever you choose:

- **The tick-grow number is the one to look at first** — measure it several times under real load and report
  the spread, because a floor set from one sample is the same mistake in a new place.
- **A floor derived from the same trace it validates can be vacuous.** If the floor is computed from the
  observed span, it can never fail — say how you avoid that, or the check becomes decoration. This is the
  trap: the point of a vacuity check is to fail when the motion did not happen, so its threshold cannot come
  from the motion that did.
- Keep the assertion's **message informative**: which motion, what span, what floor. `#333`'s and `#442`'s
  lesson is that two failure modes printing one line cost six hours once.

## Done means all of these

1. Each motion's vacuity floor is derived or separately justified, with its measurement recorded in the file.
2. **Red-first, and name the production line.** Break each motion in turn and show its own check failing with
   the right message; then show that a *smaller but real* motion does **not** trip the vacuity check. That
   second half is the actual bug being fixed. **A green red-run is a finding, never a relief.**
3. `node dev/capture/states.mjs` passes, and passes again **under a concurrent second run** — `#442` proved a
   single pass here means little (`DREAMWORK_GUARDS="states" DREAMWORK_HUB_GUARDS= just guards <port>`,
   **space separated**; a comma is read as one filename). Record the loads.
4. Note what landed tonight so you do not fight it: **`#442`** — a compositor-driven CSS transition is invisible
   to a starved rAF sampler, `transitionstart` is the load-independent snap detector, and `#444` **refused** a
   duration floor because a ±20% band around the declared 350ms fails a measured-green 239ms. `#444` also fixed
   `transitionWindow` to pair the first end at-or-after the start, which had produced **negative durations**.
   A **height** transition is main-thread layout so rAF should see it — but if you find otherwise, use the
   `#442` shape rather than inventing a third one, and say which you used.
5. `python3 lint.py` clean; `python3 -m pytest -q -p no:randomly` passes (1091 at dispatch). **Do not run the
   full `just test`.** Do not touch :35110, the heartbeat, the monitors, or the loop.
6. If `transitions.md` states the span-floor-is-a-deliberate-literal rule, and your change refines it,
   **update it in the same commit** — single-source, measured by `just audit-styleguide`.

## Files

Yours: `dev/capture/states.mjs`, `transitions.md`, and `dev/capture/dom.mjs` **only** if a shared helper is the
right home (say why).

**Not yours:** `watch.py` (**a live lane holds it**), `confirmation.mjs`, `prominence.mjs`, `reviewsplit.mjs`,
`justfile`, `lint.py`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`.

## Practical

2 threads. `git commit --only <paths>` — **never `git add -A`**. **Commit before you finish.** This host is
never idle (~35–50 load from other sessions) — design for the loaded case, see `#428`.

## Report

Which model you are; the shape you chose and why; the tick-grow measurements and their spread; how you avoid a
floor derived from the trace it validates; the production lines whose changes red each check; the concurrent
run results with loads; and confirmation you did not run the full `just test` or touch :35110.
