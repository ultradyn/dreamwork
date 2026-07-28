# Brief — #465: a lane can edit the main checkout instead of its worktree, and nothing notices

Repo: `ud-dreamwork`. Worktree: **`.worktrees/contain`**, branch **`wt/contain`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

**Read the irony before you start:** this task exists because a lane edited the main checkout. If you do it, you
will have reproduced the defect while fixing it — and the check you are building would have caught you. Assert
your own cwd and branch before every write.

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[contain]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/contain-inbox.md` so I can steer you mid-task.

Report a line per milestone (**IGC done**, **implemented**, **red-proved**, **committed**). Full report goes
**once** to `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which model you are**
at the top. **Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` —
report the lines you want added.

## What happened, measured

Read **`#465` in `.dreamwork/tasks.md`** first. Short form: a lane dispatched into `.worktrees/superseded` on
`wt/superseded`, with the worktree named twice in its brief and `ccc` invoked with the worktree as cwd, edited
`dev/capture/health.mjs` and `.dreamwork/docs/doc-map.md` **in the main checkout on `master`** and wrote a new
plan file there. Its own worktree stayed clean.

**Two harms. One realised:** it aborted a verified `#263` merge that had been deliberately held for half an hour
(`error: Your local changes to the following files would be overwritten by merge`), and the coordinator could not
simply revert, because reverting under a live agent destroys work in progress — so a merge waited on a
subagent's acknowledgement. **One unrealised and worse:** a coordinator `git commit` would have swept the lane's
half-finished edits into a ledger commit under the wrong message. That is `12f47e3` in this repo's history
exactly, and **`--only` does not protect you** when the file is one the coordinator is also touching.

**The invariant at stake is the one the whole fan-out rests on:** *parallel increments only ever touch disjoint
files, so there is never a split brain*. A worktree makes that hold **by construction** — and the guarantee is
void the moment a lane writes outside it. A brief cannot enforce this; it named the worktree twice and was
ignored. Only a check can.

## Decide the mechanism with an IGC

`igc-method.md` / `igc-concepts.md` in the repo root: binary goals or breakpoints, `✔` non-refuted / `✘` refuted
**with the decisive error written out** / `?` a TODO, an `All` rollup, **never a score**.

Rival ideas, at minimum:

1. **A pre-commit hook in the main checkout** (`git config core.hooksPath`) that refuses a commit touching paths a
   dispatched lane owns. `.dreamwork/status.json` already records which lanes are out and what files each owns —
   it was built for a compacted coordinator, and it is exactly the registry this needs.
2. **A coordinator-side pre-merge assertion**: the main tree must be clean of paths no lane owns, naming the
   culprit paths and the lane. Cheap, but it catches the collision *late* — after the work has already gone into
   the wrong tree.
3. **A marker file** in each worktree that a lane must read and echo, so a lane in the wrong directory fails loudly
   at its first write rather than silently succeeding.
4. **Dispatch with an explicit `git -C <worktree>`** rather than trusting cwd, so a lane's git operations cannot
   land on `master` even if its file writes wander.

Goals worth stating binary, because they refute different rivals: *the coordinator never has to ask a subagent's
permission to merge* (this refutes anything that only warns after the fact); *a lane writing outside its worktree
fails at the first write, not at merge time*; *the mechanism needs no cooperation from the lane* (a rule a brief
states is what already failed); *no false refusal when no lane is out* — the ordinary solo case must stay
frictionless.

**Note 1 and 4 are not exclusive and 2 is nearly free.** If the honest answer is a layered pair — one that fails
early and one that cannot be bypassed — say so and build the cheaper half first.

## Constraints that matter here

- **Nothing may make the loop's own commits harder.** The coordinator commits the ledger constantly, and a hook
  that prompts or blocks on ordinary work will be disabled within the hour and then protects nothing.
- **Never `pkill -f`.** Never touch **:35110**, the heartbeat, the monitors, or the loop.
- **A hook is machine-local state** (`core.hooksPath` is not committed). If your design needs one, the *script*
  is committed and the *enabling* is a documented step — and it must say what happens on a checkout that never
  enables it. Trailer `Needs: config` is likely; decide.
- `.dreamwork/status.json` is **gitignored and ephemeral**. Read it defensively: absent, stale, or listing a lane
  that died is the normal case, and a check that hard-fails on a stale entry is worse than none.

## Verification

- **Red-proof it by reproducing the incident**, in a scratch clone or a throwaway worktree — never in the real
  main checkout: write to a path a fake lane owns, and watch the mechanism refuse. Name the production line whose
  change makes it pass again.
- **A green red-run is a finding, never a relief.**
- **And the test this repo learned tonight:** *could your red have been produced against the code as it stood
  before your diff?* If reaching the failure needs a seam your change introduced, the proof is circular — a lane
  was rejected outright for that a few hours ago.
- **Assert the precondition at runtime, derived** — if your check reads `status.json`'s ownership list, assert it
  parsed something, or the check passes vacuously whenever the file shape drifts.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`.** Bind nothing in 39880–39899.
- Trailer: `Needs: config` if enabling is manual, `Feature:` if not. Decide and say why.

## Files

**Yours:** a new script under `dev/` (name it), `lint.py` and `test_lint.py` if your design uses them,
`file-formats.md` **only** if you add a declared shape (same commit as the code that reads it), `SKILL.md`'s
delegation paragraph **only** to state the new obligation, a design doc at
`.dreamwork/docs/plans/lane-containment.md`, and its `doc-map.md` row (contended: resolve conflicts as a
**union** and verify the row against the directory **both ways**).

**Not yours:** `watch.py`, `test_watch.py`, `user_events/*`, `dev/capture/*`, `justfile`, `review_artifact.py`,
`.dreamwork/review/**`, `migration_notice.py`, `transitions.md`, `watch-design.md`, `DREAMWORK.md`,
`.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/handoffs.md`, `.dreamwork/lessons.md`.

## Practical

- 2 threads. `git add <newfiles>` then `git commit --only <paths> -m 'feat(#465): …'` — **`--only`, never
  `git add -A`**, and `--only <directory>` silently skips untracked files.
- **Commit before you finish.** **~20 minutes.** If the IGC lands on a layered pair, build the early-failing half
  and report the other as the successor.
- **Push back with reasons.** If you conclude no mechanism can do this without making ordinary commits worse —
  and that the honest fix is the cheap pre-merge assertion plus a louder dispatch — argue it. That is a complete
  answer, and a smaller honest result beats a larger one that gets disabled.

## Report

Say: which model you are; the IGC with each decisive error and the survivor; what you built and what you
deliberately did not; how `status.json`'s absence/staleness is handled; the production line whose change reds your
check and confirmation the red did not need a seam your diff introduced; whether enabling is manual and what an
un-enabled checkout gets; the trailer; and confirmation you worked **only** inside `.worktrees/contain` (state the
cwd and branch you verified), never touched :35110 or the loop, and did not run the full `just test`.
