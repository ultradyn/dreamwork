# Brief — #456: put a `·` between the date and its age, and make the pad zero near-invisible

Repo: `ud-dreamwork`. Worktree: **`.worktrees/dayage`**, branch **`wt/dayage`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: watch.py, test_watch.py

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. Your **coordinator inbox is
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[dayage]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/dayage-inbox.md` so I can steer you.

Final report goes **once** to `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state
which model you are** at the top. **Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or
`.dreamwork/questions.md`.

## The instruction, verbatim

> *"with the day age on questions (\"2026-07-28 01d ago\"), please: add ` · ` between them, and lower the
> opacity on the 0 to 50%. Close to invisible."*
> — the human, 2026-07-29 01:18, dashboard composer

His reason is legibility of the pair, not decoration: `2026-07-28 01d ago` reads as one continuous run of
digits, so the eye cannot find where the date ends and the age begins.

## Where both halves live — you should not need to search

- **The pad zero** is `.agepad`, styled at **`watch.py:543`** (`.age .agepad { color:var(--dimmer); }`). It is
  written by **`pushFig`** (`watch.py:1795`) and, per the comment there, wears the class **only** for the
  leading `0` of a single digit — never a genuine tens digit. Keep that invariant.
- **The separator** belongs where **`qtHtml`** joins the title's date to the age span (the date-only path
  routes through `paintDayAge`, `watch.py:1834`, via `data-day="1"`).
- The `·` is already the chrome's separator elsewhere — **reuse it, do not introduce a second glyph or
  spacing convention.** Match the surrounding spacing exactly.

## The one real judgement call

`.agepad` currently dims by **colour** (`--dimmer`); he asked for **opacity**. These are not the same thing on
this page: opacity composites the pad against the animated shader background, a dim token does not. **Do
whichever actually reads as "close to invisible" on the live page**, and say in your report which you chose and
why. If opacity at 50% turns out to read *less* invisible than the current colour token — or if 50% of the
current dim colour is nearly gone entirely — that is worth telling him rather than following the number
literally; his words are the goal, `50%` is his estimate of how to reach it.

Do **not** add a length/threshold check of any kind here: he ruled at 01:17 that numbers steer and never gate.

## Constraints

- **No transition.** `ages()` rewrites this text once a second as a pure text update, and `transitions.md`
  explicitly exempts that sweep. **Do not add a gesture to a digit flip.** Read `transitions.md` before you
  touch anything that appears, moves, or changes, and confirm in your report that you added none.
- **`watch.py` is shared with a live lane right now.** The `mistperf` lane (`#449`) is editing `crossfade()`,
  the SVG-filter/mist CSS, `transitions.md` and `watch-design.md` in the same window. **Keep your diff to the
  two spots above** — the `.agepad` rule and the `qtHtml` join. A wide diff will collide and the coordinator
  will have to unpick it. Do **not** touch `crossfade`, `stepFx`, the `#dreamfx` filters, `transitions.md`, or
  `watch-design.md`'s motion section.
- **Day-age semantics are `#392a`'s and must not regress**: a date-only entry shows **one** figure (`03d ago`)
  or the word `today` for the same calendar day — never fabricated sub-day precision. A timed title
  (` HH:MM`, `#392b`) takes the two-figure path instead. Your separator change must not alter which path an
  entry takes.

## Done means

1. Both changes visible on a real render, with the `·` spacing matching the chrome's existing use.
2. **A test.** `test_watch.py` is `mistperf`'s file for its own guard — coordinate by keeping to a **new test
   function only**, appended, so the merge is trivial. Red-proof it: revert your change, watch it fail, and
   **name the exact production line whose change reds it**. **A green red-run is a finding, never a relief** —
   if it passes with your change reverted, the test is wrong. **Assert its precondition at runtime** (that a
   date-only open question exists to render at all — a check with no subject passes forever; a sibling test
   broke tonight for exactly this reason and its fix is at `72c9f2e`, read it).
3. `python3 lint.py --target .` clean, `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
   `just test`.** Bind nothing in 39880–39899 or 39890–39899.
4. Do **not** restart, `pkill` or redeploy the live dashboard on **:35110** — he is reading it right now. Do
   not touch the heartbeat, the monitors, or the loop. Never `pkill -f`.
5. `watch-design.md`'s **type/copy** section updated in the same commit **only if** the separator or the pad
   treatment is documented there — check, and say what you found. It is single-source and
   `just audit-styleguide` measures whether docs track the change.

## Files

**Yours:** `watch.py` (the two spots only), `test_watch.py` (a new function, appended).

**Not yours:** everything else — in particular `transitions.md`, `watch-design.md`'s motion section, `justfile`,
`dev/capture/*` (all `mistperf`'s), `review_artifact.py`, `.dreamwork/review/**` (the `context` lane),
`SKILL.md`, `lint.py`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/handoffs.md`.

## Practical

- 2 threads. `git commit --only watch.py test_watch.py -m 'style(#456): …'` — **`--only`, never `git add -A`**:
  other agents commit in this tree and a bare `git commit` sweeps their staged work into yours.
- **Commit before you finish.** Lanes tonight have exited with correct work uncommitted.
- **This is small — keep it small.** If you find yourself refactoring the age formatter, stop and report.
- **Push back with reasons if the change is wrong**, including if `·` collides with an existing separator in
  that line or if the pad zero is load-bearing for alignment.

## Report

Say: which model you are; the exact before/after text of the rendered day-age; whether you used opacity or a
colour token and why; what the test asserts, the production line whose change reds it, and the precondition you
asserted; whether `watch-design.md` documents this and what you did about it; and confirmation you added no
transition, did not touch `mistperf`'s regions, did not run the full `just test`, and did not touch :35110.
