# Brief — #449: the question→review dissolve is framey. Make the mist cheap without making it less.

Repo: `ud-dreamwork`. Worktree: **`.worktrees/mistperf`**, branch **`wt/mistperf`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

## Two-way channel — do this first, before any work

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow its **`for-subagents.md`**. Your **coordinator inbox is
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live, so a line there reaches me
in seconds. Send the startup handshake there **before** you start, prefix every line `[mistperf]`, and create +
watch `/home/xertrov/.cache/agent-comms/ud-dreamwork/mistperf-inbox.md` so I can steer you mid-task.

Append a one-line note at each milestone: **baseline measured** (with the number), **cause identified**,
**fix measured** (with the before/after), **committed**. Three lanes today exited without reporting after doing
correct work, and a working lane and a dead one looked identical to me. Your full report still goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are** at the
top. **Do not write `.dreamwork/handoffs.md`**, and **do not edit `.dreamwork/tasks.md` or
`.dreamwork/questions.md`** — the coordinator is their only writer; report the lines you want added.

## The report, verbatim

> *"hmm there is a bit of a performance issue when I changed from a question screen to this screen. This might
> be due to all of the, like the SVG liquify stuff, maybe? Because there could be a lot of elements on the
> page. Maybe there's some way we can optimize those or like remove them from the page if they're not going to
> make a difference at that point. Anyway, yeah, it's like, it's framey when it changes from, yeah, the
> question page to the review page. Maybe that's to do with like the reflow of all the HTML elements and stuff
> like that as well, but I think it might be a recent addition. That's why I suspect the page transition. Well,
> not the page transition, sorry. The additions that were made for expanding and contracting, like collapsible
> sections, so that they had the liquify effect as well."*
> — the human, 2026-07-29 00:39, dictated into the dashboard composer

He is describing **one specific route change**: a question view → the review view. Reproduce **that**, not a
generic navigation.

## What I already know, and what I do not

Read `#449` in `.dreamwork/tasks.md` for the same in ledger form. In `watch.py`:

- `crossfade()` (search `Dream dissolve`) clones `#view` into a full-page `.ghost`, sets
  `filter: url(#dissolveOut)` on the ghost and `url(#dissolveIn)` on the incoming view, and drives both from
  `stepFx` on `requestAnimationFrame` for `DREAM_MS = 1150`.
- `stepFx` animates three things per frame: `feDisplacementMap@scale`, `feGaussianBlur@stdDeviation`, and
  **`feTurbulence@baseFrequency` (0.009 → 0.018)**.
- **My hypothesis, which is yours to confirm or refute:** the `baseFrequency` animation is the expensive one.
  `scale` and `stdDeviation` re-use a cached noise field; changing `baseFrequency` invalidates it, so the
  browser regenerates the whole fractal-noise texture every frame — over a `150% × 150%` filter region on an
  element whose area scales with page height. **Review is the widest and tallest view**, which is exactly the
  transition he named, and the `#dreambg` shader is already consuming main-thread rAF alongside it, plus
  `flipDock`'s FLIP.
- **His "recent addition" hypothesis is not confirmed and may be wrong.** `grep` finds only three filters —
  `dissolveOut`, `dissolveIn`, `departMist` — all route/ghost gestures, and **no turbulence on any collapsible
  section**. So either something in the dissolve path changed recently, or he has attributed it to the wrong
  change. **Check the history** (`git log -p -S 'baseFrequency' -- watch.py`, and around the collapse/expand
  work) rather than trusting his account or mine. If the recent change is innocent, say so plainly — he would
  rather know that than have us fix the wrong thing quietly.

## Measure before you touch anything

**This host is never idle** (ambient load 25–55 on 16 cores from other agents' sessions), so an absolute
frame-time threshold is untestable here. Measure **A/B on the same host in the same run**: baseline vs
candidate, alternating, several repetitions, and report the distribution rather than one number. A single pass
is what made an earlier guard look fixed when it was not.

Useful instrumentation, in `dev/capture/` style (`node dev/capture/<x>.mjs` serves the real target on an
ephemeral port and drives Playwright — read one, e.g. `dev/capture/states.mjs` or `confirmation.mjs`, for the
house idiom):

- **rAF gaps inside the dissolve window** — the load-bearing signal *here*, unlike `#442`. `#442` found that
  compositor-driven opacity/transform transitions animate fine while zero rAF callbacks fire, so rAF counting
  was the wrong probe *for that*. This is the opposite case: `stepFx` **is** main-thread rAF, so a starved rAF
  loop is precisely the jank he is seeing. Say in your report which of the two situations you are in and why.
- Long-task / frame duration via CDP (`Performance` or `tracing`) if you can get it cheaply. Do not build a
  large harness; the point is a defensible before/after.
- Note the review page's **actual height and element count** — his "a lot of elements" is testable, and if the
  cost is area-driven rather than count-driven that changes the fix.

## The constraint that is not negotiable

**`transitions.md` governs this and the fix is cheaper mist, not less gesture.** Read it first. A route change
that stops liquifying in order to gain frames has traded away the thing the page exists to be, and would be
rejected. Nothing may start snapping, and the reduced-motion path (`rmr` → instant swap, no ghost, no mist)
must keep behaving exactly as it does.

His own sentence *"remove them from the page if they're not going to make a difference at that point"* is the
right instinct and the safest fix: mist that is **not visible** is pure cost. Candidate ideas —

- **Freeze `baseFrequency`** and get the "field tightens, it flows" reading from `scale` alone, which is
  cache-friendly. Judge whether the gesture still reads; if it does, this is nearly free.
- **Shrink the filter region** from `150%` to what the maximum displacement actually needs.
- **Cap the filtered area**: the ghost is pinned to `outW × outH` — a tall review page mists far more surface
  than is on screen. Mist what is in the viewport; the rest is invisible cost.
- **Drop the filter early**: once `stdDeviation` and `scale` have decayed below a perceptible floor, clear
  `filter` rather than animating to exactly zero (`finish()` already clears it at the end — the question is
  whether the last stretch of the animation is buying anything).
- **Quantise `stepFx` updates** — a filter attribute rewrite every frame may be more than the eye needs.

**Choose between these with an IGC, not a pro/con list**: (Idea, Goal, Context), binary goals, `✔`
non-refuted / `✘` refuted with the decisive error written out / `?` a TODO — never a score. Convert "faster"
into a **breakpoint** ("no dropped frame beyond X in the dissolve window, on this loaded host, A/B against
baseline") because "fastest" is not a binary goal. The method is
`/home/xertrov/.llm-general/skills/use-igcs/SKILL.md`; read it before you decide. One of your goals must be
*the gesture still reads as a liquifying dissolve* — and if you cannot evaluate that from measurement alone,
mark it `?` and say what would settle it, rather than quietly assuming it passes.

## Done means

1. **A measured cause**, named as a specific line or attribute, with the A/B numbers that identify it. If the
   cause is not what either of us guessed, that finding *is* the deliverable — report it and stop before
   changing anything speculative.
2. **A fix, if one is available inside the constraint above**, with before/after on the same host in the same
   run, and the IGC matrix that chose it.
3. **A check.** A motion bug cannot fail an end-state assertion and cannot fail "did it move" — `transitions.md`
   opens with how to check this and the reasoning cost three batches to learn. Then: **red-proof it** —
   reinstate the slow path, watch it fail, and **name the exact production line whose change reds it**. **A
   green red-run is a finding, never a relief**: if the check passes with the regression in place, the check
   is wrong; do not conclude the code was fine. **Assert the check's own precondition** derived at runtime
   (that the dissolve actually ran, that the page under test is the tall one) — never a literal tuned to
   today's page. If a perf number cannot be asserted stably on this host, **say so and refuse the check with
   that reason** rather than landing a flaky one; `#444` refused a threshold on exactly this ground and was
   right. A guard you register goes in `justfile`'s `DEFAULT_GUARDS` (52 today, each needing its file).
4. **`watch-design.md` and/or `transitions.md` updated in the same commit** if the gesture's declared
   parameters change — those docs are single-source and `just audit-styleguide` measures whether that happened.
5. `python3 lint.py --target .` clean, `python3 -m pytest -q -p no:randomly` passing. Guards bind
   **39890–39899** (watch) — you own that range for this lane; nothing in 39880–39889. **Do not run the full
   `just test`.**
6. Do **not** restart, `pkill` or redeploy the live dashboard on **:35110** — he is reading it right now, and
   your measurements must serve their own port, never his. Do not touch the heartbeat, the monitors, or the
   loop. Never `pkill -f`; build process patterns from parts (`#431`: the pattern self-matched from a comment).
7. Trailer if an install's behaviour changes: `Migration:`, `Feature:`, or `Needs: config|consent`.

## Files

**Yours:** `watch.py`, `transitions.md`, `watch-design.md`, `dev/capture/<your new guard>.mjs`, `justfile`'s
`DEFAULT_GUARDS`, `test_watch.py`.

**Not yours:** `SKILL.md`, `lint.py`, `test_lint.py` (the `igc` lane holds all three), `dev/capture/states.mjs`
(the `floors` lane holds it), `.dreamwork/docs/plans/*` (two lanes are writing there), `dreamhub.py`,
`review_artifact.py`, `review-artifact.template.html`, `.dreamwork/review/*`, `dev/ledger.py`,
`dev/deploy_state.py`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/handoffs.md`.

## Practical

- 2 threads. `git add <newfile>` then `git commit --only <paths> -m 'perf(#449): …'` — **`--only`, never
  `git add -A`**: other agents commit in this tree and a bare `git commit` sweeps their staged work into
  yours. `--only <dir>` silently skips untracked files, hence the `git add` first.
- **Commit before you finish**, and **land the measurement even if you land no fix** — a defensible baseline
  plus a named cause is a complete increment and the next lane starts from it instead of re-deriving it.
- **~15–20 minutes of work.** If the fix grows past that, land the diagnosis and say what remains.
- **Push back with reasons if any of this is wrong**, including if the framiness is reflow rather than filter
  (he raised that possibility himself and it is live). The most valuable lanes today refused what they were
  handed and were right.

## Report

Say: which model you are; the baseline numbers and how you got them; **the cause, named as a line**; whether
his recent-addition hypothesis held; the IGC matrix with the decisive error under each `✘`; the after numbers
from the same run; what check you added — with the production line whose change reds it and the precondition
you asserted — or your reason for refusing one; whether the gesture still reads and how you judged that; and
confirmation you did not run the full `just test`, did not touch :35110, and stayed off the files the other
lanes own.
