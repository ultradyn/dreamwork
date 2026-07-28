# Brief — #417: he asked to see all four options, side by side

Repo: `ud-dreamwork`. Worktree: **`.worktrees/mockups`**, branch **`wt/mockups`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: .dreamwork/review/src/417-burndown-commits.html, .dreamwork/review/417-burndown-commits.html, dev/capture/burndownmock.mjs

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[mockups]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/mockups-inbox.md` so I can steer you mid-task.

Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not state a model name for
yourself** — the harness exports only `CCC_PROVIDER`, so you cannot know it; write the caveat instead (the
rule is at the top of `.dreamwork/handoffs.md`). **Do not write `.dreamwork/handoffs.md`**,
`.dreamwork/tasks.md` or `.dreamwork/questions.md` — report the lines you want added. **Report a line per
increment and commit as you go**; an external sweep killed four background jobs here twenty minutes ago and
the per-milestone inbox lines were the only surviving record.

## His request, verbatim, and what it means

`.dreamwork/questions.md`, `#417`, **2026-07-29 05:51**: *"show me mockups of all 4 options please."*

Read `#417` in `.dreamwork/tasks.md` and the whole `#417` entry in `questions.md` — including the
coordinator's visual verdict, which rejected `C1` as invisible and redirected `C3` → `C2`.

**The artifact already contains ten real renders** (`417-burndown-commits.html`, `5fe331a`) — so the gap is
almost certainly not "renders do not exist", it is that they are **not presented as a comparison he can
read**. Measure that before building: open the artifact, find what is actually there, and say in your report
whether the four options each have a render at the panel's real width and whether they can be seen *together*.
If they cannot, that is the defect and the fix is a **four-up (five-up with the reference) comparison at one
scale**, same width, same ledger data, adjacent.

**If your measurement says something else is wrong — say so and fix that instead.** He asked to see the
options; he did not specify a layout.

## The one rule that decides this task

**Every panel in the comparison is a REAL RENDER of the real panel against the live ledger.** Not a drawing,
not CSS approximating what C1 would look like, not a hand-built SVG. The reason is specific and this repo has
already paid for it: `#367`'s "visible without scrolling" was an *opinion* until it became
`getBoundingClientRect().bottom < innerHeight`, and **an opinion cannot be red-proved**. A mockup he cannot
check is worse than no mockup, because it looks like evidence.

So each option needs the panel actually rendered with that option applied. If applying an option requires a
change to the chart code you do not own, **do it in the capture script as an injected override** and say
exactly what you injected — an override you disclose is evidence; one you do not is a forgery.

## Verification

- **New guard `dev/capture/burndownmock.mjs`**, and register it in `justfile`'s `DEFAULT_GUARDS` (**57**
  today) — an unregistered guard gates nothing. **Note the port discipline you must follow:** take the port
  from `process.argv[3]` and if you serve your own target use `await freePort()` **when argv[3] is absent
  only**. Do not hardcode an exclusive port; `reviewdraft` hardcodes `39894` and I am currently unable to
  explain its behaviour under `just guards`, so do not copy that pattern.
- **What the guard must assert, mechanically, not by eye:** that the comparison carries one render per option
  (derive the option list from the artifact rather than a literal `4`), that the renders are the same width
  (assert the widths are equal at runtime — a comparison at two scales is not a comparison), and that each
  render is non-blank (a broken data URI renders as nothing and looks like a subtle design).
- **Red-proof each check on the production line.** Name the line whose change reds it, change *that*, and
  watch it fail. **A green red-run is a finding, never a relief.**
- **Assert the precondition each check depends on, derived at runtime.** If "same width" is the claim, two
  renders must actually exist to compare; assert the count before asserting the equality, or the check
  passes vacuously on one render.
- The artifact must pass `python3 review_artifact.py check` as **current** and be **offline-clean** (zero
  external URLs — the builder enforces this). It needs a meaningful `#ask` and an `#if-silent`; `#436`'s
  build-time contract refuses neither/both/decoy, and the exemption side-file is **not** available to you.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`** — I ran it once tonight and it is 15+ minutes at this machine's load.
- Bind nothing in 39880–39889; kill what you start by exact pid; check `ss -ltnp` before finishing.
- **Do not restart, `pkill` or redeploy the dashboard on :35110** — he is reading it. Never `pkill -f`.
- Trailer: `Feature:` if you add the guard; the artifact rebuild alone is `docs:`.

## Files

**Yours:** the three in `Lane-owns:` above.

**Not yours, and this matters here:** `watch.py` (**use** it to render — run it, read it, never edit it),
`review_artifact.py`, `lint.py`, `test_lint.py`, `dev/lane_guard.py`, `dev/capture/serve.mjs` and
`report.mjs` (use, do not edit), `justfile` (**one exception**: the `DEFAULT_GUARDS` line, to register your
guard — change nothing else in it), `watch-design.md`, `SKILL.md`, `DREAMWORK.md`, `.dreamwork/tasks.md`,
`.dreamwork/questions.md`, `.dreamwork/handoffs.md`, `.dreamwork/lessons.md`.

## Practical

- 2 threads. **One commit per increment**, `git add <newfiles>` then `git commit --only <paths>` —
  **`--only`, never `git add -A`**; `--only <directory>` silently skips untracked files.
- **Work only inside `.worktrees/mockups`.** Verify cwd and branch before every write — `dev/lane_guard.py`
  and `lint`'s backstop will both name you by file and branch if you do not, and R2 now refuses the merge too.
- ~25 minutes. **Commit before you finish**, and land the comparison without the guard rather than nothing.
- **Push back with reasons.** If the honest finding is that the existing artifact already shows him all four
  properly and the real problem is that he could not *find* the renders in it, that is a different fix
  (navigation, not rendering) and a better answer — argue it. Lanes have refuted their briefs here tonight
  and every one of them was right to.

## Report

Say: what the existing artifact actually contained (measured, per option, with widths); what you built and
why that was the right fix; **exactly what you injected** to render each option and the line you injected it
at; how the guard derives the option count rather than hardcoding it; for each check the production line
whose change reds it, the runtime-derived preconditions, and confirmation no red needed a seam your diff
introduced; the `check` verdict and external-URL count; the guard count in `DEFAULT_GUARDS`; and confirmation
you worked only in `.worktrees/mockups` (state the cwd and branch you verified), edited no `watch.py`, left
nothing listening, never touched :35110, and did not run the full `just test`.
