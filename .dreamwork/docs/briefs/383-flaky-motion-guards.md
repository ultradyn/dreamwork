# Brief — three motion guards disagree with themselves between runs

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first, and
`transitions.md` — this task is about motion checks, and that file opens with how
to check motion and why the obvious way does not work.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route named at the bottom.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it.
- **Session goal**: the guard suite is not green, and until it is, every "verified"
  claim about the dashboard is weaker than it sounds. There is no CI — the guards
  are it.
- **This task**: three guards gave **different verdicts on two runs of the same
  unchanged code**. A check that disagrees with itself is worse than a red one,
  because neither of its answers can be believed. That is the bug, and it is a bug
  in the checks rather than in the page.

## The evidence, measured — do not re-derive it

Full sweep at 04:40 (47 guards, sequential, one browser at a time). Then a focused
re-run of only the four reds. The working tree did not change between them.

| guard | full sweep | focused re-run |
|---|---|---|
| `revieworder` | **FAIL** — `normal: z.html travels through intermediate Y positions without overshoot`, same for `a.html` | **PASS** |
| `gitrow` | **FAIL** — `opening: ...and it travels there rather than teleporting`, and `opening: the row itself grows continuously rather than in one step` | **FAIL**, but on `closing: ...and it travels there rather than teleporting` |
| `burndown` | **FAIL** — `...and it TRAVELS to its new height rather than snapping` | **FAIL** — `the guard threw before finishing its checks` |
| `plugcmd` | FAIL | FAIL, identically — **not yours**, another agent owns it |

Read that table carefully. `revieworder` flipped to green. `gitrow` failed on
*opening* once and *closing* the other time. `burndown` did not even reach its
checks the second time. The full sweep is the heavier run — 47 guards' worth of
browser and server churn — which is consistent with these being timing-sensitive
under load, but **consistent with is not the same as demonstrated**, and
demonstrating it is your job.

## What I want, in this order

1. **Characterise before changing anything.** Run each of the three several times
   in isolation and record pass/fail per run. Then run them under deliberate load
   and record again. Come back with a table: how often each fails, and whether
   failure correlates with load. Numbers, not impressions. If one turns out to be
   deterministically red and I mis-read it as flaky, that is a finding — say so
   loudly, because it changes what happens next.
2. **Find the shared mechanism.** All three sample *intermediate* frames of a
   transition. Read how they do it. My expectation, which you should confirm or
   refute: they sample on a wall-clock schedule and assume frames land inside a
   window, so a slow machine drops the sample outside it. If that is right, the
   three share one defective idiom and there is one fix, not three.
3. **Fix the instrument, not the threshold.** Widening a tolerance until a check
   stops failing makes it hollow, which this repo treats as worse than red — see
   `.dreamwork/lessons.md`. A motion check has to establish that motion *happened*
   without depending on catching a particular instant: sample per-frame via
   `requestAnimationFrame` rather than on a timer, and assert on the sequence you
   collected. `transitions.md` and `dev/capture/dreamfade.mjs` already do
   per-frame sampling — **reuse that idiom rather than authoring a second one.**
4. `burndown`'s "the guard threw before finishing its checks" is a different fault
   from the other two. A guard that throws reports as a failed assertion and hides
   what actually went wrong. Make it say what threw.

## A resource may appear under you — check for it once, do not block on it

Another agent is, right now, writing reference material on **testing animation in
the browser** into the shared KB (`~/.llm-general/`, most likely under
`ai-coding/` or as a top-level note; `grep -rl "animation" ~/.llm-general
--include="*.md"` will find it). It did not exist when this brief was written.

Look for it **once**, early. If it is there, read it before designing your
instrument and say in your report whether it changed your approach — that is
useful signal about whether the KB is earning its keep. If it is not there, carry
on with `transitions.md` and `dreamfade.mjs` as your references and do not wait.

## The verification rules, which are the point

- **A changed check is not verification until it has been red.** For each guard you
  touch: break the motion it checks (make the thing snap instead of travel), watch
  the check fail, then restore. Undo from a `cp` snapshot, never `git checkout --`.
- **A green red-run is a finding, never a relief.** If you make the transition snap
  and the check still passes, the check is hollow — report that; do not conclude the
  motion was fine. An end-state assertion cannot fail on a motion bug, and neither
  can "did it move" — that is precisely why these guards sample intermediate
  frames.
- For each guard, name in your report **the production line that would have to
  change for your version of the check to fail.** If you cannot name one, there
  isn't one.
- A check that passes reliably because it no longer asserts anything is the failure
  mode here. I would rather have one guard genuinely fixed and two honestly
  reported as still flaky than three that are quietly toothless.

## Files you own, and the ones you must not touch

**Yours:** `dev/capture/revieworder.mjs`, `dev/capture/gitrow.mjs`,
`dev/capture/burndown.mjs`.

**Read freely, do not edit:**
- `watch.py` — another agent has uncommitted work in it right now, and a third is
  editing its transition CSS. Editing it would collide. If a fix must live in
  `watch.py`, **stop and report that**; do not do it. This is the one hard boundary.
- `dev/capture/dreamfade.mjs` and `dev/capture/report.mjs` — reference idioms, read
  them, do not change them.
- `transitions.md`, `justfile`.

**Never touch:** `dev/capture/plugcmd.mjs` (another agent owns it right now),
`.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/status.json`,
`.dreamwork/inbox.md` (except the single append below), `bin/ud-dw-generate`.

## Operational constraints

- **Your guard port is `39895`.** Another agent is working in the same range
  concurrently, on `39897`. Run guards as:
  `DREAMWORK_GUARDS="revieworder gitrow burndown" DREAMWORK_HUB_GUARDS="" just guards 39895`
  (or one name at a time). **Never** run the full sweep, and never the default port.
- Limit builds/tests to 2 threads.
- The guards import playwright by absolute path — see the top of any `.mjs` in
  `dev/capture/`. A bare `import ... from 'playwright'` will not resolve.
- Commit your own work, **staging by explicit path only** (`git add -A` will bury
  other agents' half-finished work — several are live in this tree). Do not push.
- Cap yourself at roughly 20-30 minutes. If it grows past that, land a coherent
  point, commit, and report the remainder. Characterisation alone (step 1) is a
  perfectly good increment to land if the fix does not fit.

## How to report

Append **once**, at the end, using a single shell append (`cat >> …` or `>>`),
never by rewriting the file, because another agent appends to the same file
concurrently:

`.dreamwork/inbox.md`

Follow the shape of the existing entries. It must state: the run-by-run table from
step 1; whether the three share one mechanism; what you changed and where; **the
red-proof per guard — what you broke, what failed, the exact check name**; which
guards you are leaving red or flaky and why; and anything out of scope (I will file
it). If you have insights beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
