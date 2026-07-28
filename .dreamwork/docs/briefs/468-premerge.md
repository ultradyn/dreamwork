# Brief — #468 R2: the pre-merge assertion, the recorded successor to the pre-commit guard

Repo: `ud-dreamwork`. Worktree: **`.worktrees/premerge`**, branch **`wt/premerge`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: dev/lane_guard.py, lint.py, test_lint.py, file-formats.md, .dreamwork/docs/plans/lane-containment.md

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[premerge]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/premerge-inbox.md` so I can steer you mid-task.

Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which model you are** at the
top. **Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` — report
the lines you want added. **Report a line per increment and commit as you go**; lanes have been killed here
without warning and the per-milestone inbox lines were the only surviving record.

## What exists, and the gap it does not cover

Read `#468`, `#465` and `.dreamwork/docs/plans/lane-containment.md`. Three layers exist today:

1. **`dev/lane_guard.py`** — a pre-commit guard on the **main checkout** that refuses a commit touching a
   path a live lane's brief declares under `Lane-owns:`. Ownership is the **union** over every brief naming
   the lane (a lane with two briefs resolved to the older one by sorted filename and declared nothing —
   that lane was unprotected while the coverage row still counted it).
2. **`lint.check_lane_containment_backstop`** — ERRORs when a lane-owned path is merely **dirty** in the
   main tree (staged, unstaged or untracked), which is the state that actually aborted a held `#263` merge
   before any commit existed.
3. The `Lane-owns:` retrofit: **54 briefs in scope, 21 deliberately skipped and reported**.

**R2, recorded in the plan as the successor and still not built, is the pre-merge assertion.** The failure
it addresses is different from the ones above and has happened twice: **`git merge wt/<lane>` aborts because
the index or worktree is dirty with someone else's work**, and the abort message names files rather than the
reason, so the coordinator diagnoses it as a conflict. Once it was staged-but-uncommitted briefs; once it
was a lane's edit in the main checkout. In both cases the merge was already half-done when the cause became
clear.

## Your scope

**Assert the preconditions of a merge *before* running it, and say which one failed in the repo's own
voice.** At minimum the check knows: is the index clean; is the worktree clean; does any dirty path belong
to a live lane (reuse the backstop's ownership resolution — **do not author a second reader**); and is the
branch being merged the branch whose brief declares that ownership.

**The decisions that are yours:**

1. **Where it lives.** A `just` recipe, a `dev/` script, a `lint` check, or a git hook are all defensible and
   they differ in one property that matters: a check the coordinator must remember to run is a check that
   will be skipped exactly when the tree is busiest. Argue your choice on that basis, not on tidiness.
   Note `core.hooksPath` is **global** at `~/.config/git/hooks` and already holds a `pre-commit` symlinked to
   another repo's script — `lane_guard._install()` chains rather than clobbers, and anything you add must
   preserve that property. A `pre-merge-commit` hook does **not** fire on a fast-forward, and a hook that
   silently does not run is worse than no hook.
2. **What it does on failure.** A refusal must name the file, the lane, the brief that declares it, and the
   one action that clears it. The `#465` incident's correct resolution was *retire the finished lane's
   worktree*, and the guard's value was that it produced that behaviour instead of a bypass — so the message
   is part of the mechanism, not decoration.
3. **What it must NOT do.** It must not offer to stash, reset, checkout or otherwise move anyone's work.
   Eight lanes have run in this tree tonight; a helpful automatic cleanup is how a lane's uncommitted hour
   disappears.

## Verification

- **Real git worktrees, not fakes.** `TestLaneContainmentBackstop` in `test_lint.py` already builds real
  worktrees and real `wt/*` branches — extend that discipline. A test that hand-builds the dirty-path list
  instead of calling the function that decides it cannot fail when that function breaks; that exact shape
  passed over its own bug here twice in two hours.
- **Red-proof each check on the production line.** Name the line whose change reds it, change *that*, and
  watch it fail. **A green red-run is a finding, never a relief.**
- **Could your red have been produced against the code as it stood before your diff?** If reaching the
  failure needs a seam your change introduced, the proof is circular.
- **Assert the precondition the check depends on, derived at runtime.** If a test's meaning needs two pieces
  of the fixture to differ, derive both and assert the gap — a literal tuned to today's fixture is a check
  with an expiry date nobody can see. If it needs a live lane to exist, assert the registry actually lists it.
- **A check that examines nothing looks identical to one that found nothing.** Put the count on the OK row —
  the backstop's own OK row silently never appeared once because its branch parsing mishandled
  `refs/heads/wt/x` and it saw no lanes at all.
- **Do not regress the existing coverage rows** in `lint.py`, and state in `file-formats.md` any shape you
  parse, **in the same commit** as the code that reads it.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`.** Bind nothing in 39880–39899.
- **Do not test by merging anything in the main checkout**, and do not touch :35110, the heartbeat, the
  monitors, or the loop. Never `pkill -f`. Other lanes are live and their branches are not your fixtures —
  build your own throwaway repo or worktree for the merge scenarios.
- Trailer: `Feature:`, plus `Needs: consent` if it installs anything into a git hook path (his consent for
  the pre-commit guard is a separate open ask; do not assume it covers a second hook).

## Files

**Yours:** the five in `Lane-owns:` above.

**Not yours:** `watch.py`, `test_watch.py`, `watch-design.md`, `dev/capture/*`, `review_artifact.py`,
`user_events/*`, `justfile`, `SKILL.md`, `DREAMWORK.md`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`,
`.dreamwork/handoffs.md`, `.dreamwork/lessons.md`, `.dreamwork/docs/doc-map.md` (report the row you want).

## Practical

- 2 threads. **One commit per increment**, `git add <newfiles>` then `git commit --only <paths>` —
  **`--only`, never `git add -A`**; `--only <directory>` silently skips untracked files.
- **Work only inside `.worktrees/premerge`.** Verify cwd and branch before every write — and note the irony
  available to you: the guard you are extending will name you by file and branch if you do not.
- ~25 minutes. **Commit before you finish**, and land the assertion without the installer rather than nothing.
- **Push back with reasons.** If your measurement says R2 is not worth building because the backstop already
  catches every case that has actually happened, say so with the cases enumerated — that is a real finding
  and this entry can close on it. Two lanes tonight refuted their briefs with measurement and both were right.

## Report

Say: which model you are; where the assertion lives and the argument for that choice on the
will-it-be-skipped axis; the exact refusal message and the one action it names; confirmation it never moves
anyone's work; how you reused the backstop's ownership resolution rather than writing a second one; for each
check the production line whose change reds it, the runtime-derived preconditions, and confirmation no red
needed a seam your diff introduced; the coverage counts on any new OK row; what you added to
`file-formats.md` and in which commit; the trailers; and confirmation you worked only in
`.worktrees/premerge` (state the cwd and branch you verified), merged nothing in the main checkout, never
touched :35110, and did not run the full `just test`.
