# Brief — #434 + #435: the `/review` route wastes a quarter of a phone screen, and the dev overlay draws on the wordmark

Repo: `ud-dreamwork`. Worktree: **`.worktrees/frame`**, branch **`wt/frame`**. Do not push, do not merge.
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not write
`.dreamwork/handoffs.md`** — the coordinator writes that line at merge time.

Lane-owns: watch.py, test_watch.py, watch-design.md, dev/capture/above_fold.mjs

Two defects, one lane, because both live in `watch.py`'s dashboard shell and a second lane there would
collide.

## #434 — 203px of dead space below the artifact frame (the important one)

Measured on the live dashboard at **390x844**: the artifact `<iframe>` occupies `135..641` — **506px** —
and the **203px beneath it contains zero rendering elements**. `document.scrollHeight` equals
`innerHeight`, so that quarter-screen is not off-screen content; **it is empty.** Desktop wastes 40px
(4%), so this is mobile-only.

**Why it is worth more than 203px.** Every review artifact is judged on this surface. The ask, its
accepted answers and the recommendation all compete for 506px instead of 709px — reclaiming it is a
**40% increase in reading area** where he makes decisions. It is also the root cause of a constraint
elsewhere: `dev/capture/above_fold.mjs` compares against an effective mobile fold of **504** *because of
this frame*, so fixing it moves the fold to ~707 and artifacts stop fighting for the top 500px.

Likely a fixed or calculated frame height rather than a flexed one — **read the `/review` layout before
assuming**, and say what you found. Do not simply set a taller fixed height: whatever you do must hold
at other viewport sizes too, so state which you tested.

## #435 — the `--dev` overlay overlaps the wordmark

At **1280x900** the overlay's third line — `683.3ms avg · 1233.3ms worst`, spanning `1079..1267` at
`y38..52` — overlaps the **`ud-dreamwork` wordmark** (`1149..1264`, `y43..64`) by **115x9px**. Text on
text. **Mobile is clear** (overlay ends `y52`, wordmark starts `y51`, disjoint columns) — so do not
"fix" mobile.

He sees this: `just deploy` starts the server with `--dev`. Make the overlay reserve its own space or
the wordmark yield. **Do not remove the fps counter or stop passing `--dev`** — whether he wants that
counter is his call and there is an open question channel for it; you are fixing the collision only.

## `transitions.md` binds, with no size floor

The route change onto `/review` is **this repo's reference gesture**. A frame-height change must not
introduce a second idiom, and anything that appears, disappears, grows or shrinks obeys that file. Read
it before you change a height, and **state whether you introduced any gesture and whether reduced-motion
parity is inherited or authored.** Checking motion needs per-frame sampling — an end-state assertion
cannot fail on a motion bug, and neither can "did it move".

## Done means all of these

1. **`#434` measured fixed**: at 390x844 the space below the frame within the viewport is **under 24px**
   (from 203), with the frame taller by the reclaimed amount. Print before/after for **390x844,
   1280x900, and one mid-width you choose**. Desktop must not regress past its current 40px.
2. **`#435` measured fixed**: zero overlapping pairs between the overlay lines and the wordmark at
   1280x900, and mobile still zero. Use a probe that **requires the element to actually render**
   (`width>2 && height>2`, tag not `SCRIPT`/`STYLE`) — my first attempt matched a `<script>` containing
   the letters `fps`, whose rect is `0x0`, and reported "no overlap" on a collision visible in a
   screenshot. That is the single most likely way to get this wrong.
3. **Every viewport probe asserts the viewport was applied** — `innerWidth === requested` **and**
   `innerHeight === requested`. Both: chromium's default is 1280x720 and desktop asks for 1280x900, so
   on a wrong `newPage({viewportSize:…})` (the wrong key, silently swallowed) **the width matches anyway**
   and only the height reveals it. `dev/capture/above_fold.mjs` has the idiom; note its playwright import
   path.
4. **`above_fold.mjs`'s mobile fold constant updated** to the new measured effective height, in the same
   commit, with its comment's numbers corrected. It currently hard-codes `fold: 504` with a dated note
   explaining why. Re-run it against `263-second-gate`, `421-question-options` and `417-burndown-commits`
   — all three must still pass.
5. **A guard**, or a stated reason there is none. `dev/capture/` holds the suite and `DEFAULT_GUARDS` in
   the `justfile` is what makes one gate anything — a `.mjs` in that directory that is in neither
   `DEFAULT_GUARDS` nor `lint.NOT_GUARDS` gates nothing, and `lint` will tell you so.
6. **Red-first, and a green red-run is a finding, not a relief.** Reinstate each defect, watch the check
   fail, then fix. **Name the exact production line whose removal makes each check fail.** If you cannot
   name one, there isn't one. Two checks in this repo were structurally incapable of failing about the
   single decision they were named for.
7. **`watch-design.md` documents any presentation change in the same commit** — the standing rule, and
   `just audit-styleguide` measures it.
8. `python3 lint.py` clean. `python3 -m pytest test_watch.py -q -p no:randomly` passes. **Do NOT run
   `just test`** — the coordinator has a full suite running and guard ports 39890–39899 are held. Bind
   nothing in 39880–39899 and do not kill anything holding one.
9. **Do not restart, `pkill` or redeploy the live dashboard on :35110.** It is his, it was down for two
   hours today, and `just deploy`'s `pkill -f` matches any process whose command line merely mentions the
   snapshot (`#431`). Start your own server on a port outside 39880–39899 and stop it.

## Files

Yours: `watch.py`, `test_watch.py`, `watch-design.md`, `dev/capture/above_fold.mjs` (the fold constant),
plus any new guard file and its `justfile` `DEFAULT_GUARDS` entry.

**Not yours:** `review-artifact.template.html` (touching it re-stamps all 23 artifacts and 12 cannot be
rebuilt — that is `#433`), `lint.py`, `dev/deploy_state.py`, `.dreamwork/review/*`, and
`.dreamwork/tasks.md` / `questions.md` (coordinator is the only writer — report exact lines instead).

## Practical

- 2 threads. `git add <newfile>` then `git commit --only <paths> -m 'fix(#434): …'` — **`--only`, never
  `git add -A`**. Note `--only <directory>` silently skips untracked files inside it.
- **Commit before you finish.** A lane today did 24 turns of correct work and exited without committing;
  `git log` showed nothing and it was recovered by hand from the dirty worktree.
- **You can see, and that is why you have this brief.** Look at the pages, at both viewports, before and
  after. Today a top rail was overflowing its bar and colliding with four nav chips while *every*
  mechanical check on that page passed — looking found it, measuring confirmed it. Give your own visual
  verdict on whether the reclaimed frame actually reads better, not just measures better.
- **Push back with reasons if any of this is wrong.** Many lanes today refuted something their brief
  asserted and every one was right to. If the dead space is load-bearing (a docked element, a
  reserved region), say so with the measurement rather than filling it.

## Report

Say: what the `/review` layout actually does with the frame height; before/after dead space at three
viewports; the overlap counts at both viewports with the rendering precondition you used; the exact
production line whose removal fails each check; the new fold constant and the three artifacts re-checked;
whether you added a guard and how it is registered; any transition you introduced and its reduced-motion
parity; your visual verdict; and confirmation you neither ran `just test` nor touched :35110.
