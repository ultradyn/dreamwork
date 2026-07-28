# Brief — #450: name the containment deficiency, and warn per harness where interception is impossible

Repo: `ud-dreamwork`. Worktree: **`.worktrees/harnessgap`**, branch **`wt/harnessgap`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: SKILL.md, .dreamwork/docs/plans/harness-containment.md

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[harnessgap]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/harnessgap-inbox.md` so I can steer you mid-task — I do, and two
lanes tonight were corrected mid-flight by exactly that channel.

Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which model you are** at the
top. **Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` — report
the lines you want added.

**Report a line per milestone and commit as you go.** Two lanes were killed by an external sweep tonight with
everything uncommitted and their final reports lost to 0-byte files; the per-milestone inbox lines were the
only surviving record. Assume you may be stopped without warning.

**Eight lanes are running.** Touch only your `Lane-owns:` paths. `dev/lane_guard.py` and
`lint.check_lane_containment_backstop` will name you by file and branch if you edit the main checkout —
verify your cwd and branch before **every** write.

## What to read first

`#450` in `.dreamwork/tasks.md`, and then `#465` and `#468`, because tonight changed the ground under this
task: a pre-commit guard and a lint backstop now exist, and both have a **stated ceiling**. `#465`'s own
design says R5 fails at first *commit*, not first *write*, because the only mechanism that fails at first
write needs the lane's cooperation — and a rule the lane must obey is what already failed.

## The gap, stated plainly

**Some harnesses cannot intercept a subagent's file writes at all.** Where dreamwork runs a lane through
`ccc`, a `Write` tool with an absolute path reaches any file on the machine; `git -C` does not constrain it,
cwd does not constrain it, and a brief naming the worktree twice did not constrain it — that is the measured
incident behind `#465`. So containment is **partial by construction**, and the honest thing is to say so
where an operator will read it rather than let the guard imply more than it delivers.

## What to produce

1. **A short design at `.dreamwork/docs/plans/harness-containment.md`** stating, per harness dreamwork
   supports, whether a lane's writes can be intercepted before they land, and what the fallback is when they
   cannot. Do not enumerate harnesses you cannot check — **name the ones you verified and mark the rest
   unknown.** An invented capability matrix is worse than a short honest one.
2. **A warning where it will be read.** `SKILL.md` is yours for this: the delegation section already tells the
   coordinator to record what a lane owns. It should also say what containment does **not** cover, in one or
   two sentences, so nobody reads `#465`'s guard as a guarantee. **Keep it short** — SKILL.md is loaded every
   session and length is a real cost.

## The line not to cross

**`#450` must not be confused with the run-mode work (`#288`/`#290`), which explicitly grants no kill or
sandbox authority.** Do not propose killing, sandboxing or restricting a lane's process; that authority is the
human's and he has not granted it. This task is about **stating a limitation accurately**, and proposing
mechanisms that need no new authority.

If your conclusion is that no further mechanism is worth building and the right deliverable is one honest
paragraph plus the design note, that is a complete answer. Say it.

## Verification — this repo's rules, and they are not optional

- **Red-proof every check on the production line.** Name the line whose change reds it, change *that*, and
  watch it fail. **A green red-run is a finding, never a relief** — when you reinstate a bug and the check
  passes, the check is wrong.
- **Could your red have been produced against the code as it stood before your diff?** If reaching the
  failure needs a seam your change introduced, the proof is circular. A lane was rejected outright for that
  tonight.
- **Assert the precondition the check depends on, derived at runtime.** A check that examines nothing looks
  identical to one that found nothing — tonight a new check's coverage row silently never appeared because its
  parser saw no subjects. Put the count on the OK row.
- **Two values that must differ must be derived to differ.** A literal pair tuned to today's fixture is a
  check with an invisible expiry date; this repo has paid for that three times.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`** — eight lanes share this machine and the guard suite has documented load sensitivity (`#428`).
- Bind nothing in 39880–39899. Kill by exact pid; never `pkill -f`. Check `ss -ltnp` before finishing.
- **Never touch :35110, the heartbeat, the monitors, or the loop.** He is reading that dashboard.
- Trailer where it applies: `Migration:`, `Feature:`, `Needs: config|consent`. Decide and say why.
- 2 threads. **One commit per increment**: `git add <newfiles>` then `git commit --only <paths>` —
  **`--only`, never `git add -A`**; `--only <directory>` silently skips untracked files.
- ~20 minutes. **Commit before you finish**; land the smaller coherent half rather than nothing.
- **Push back with reasons.** A smaller honest result beats a larger one built on a premise you doubt — and
  two briefs tonight had premises that measurement refuted, so doubting mine is expected, not rude.
