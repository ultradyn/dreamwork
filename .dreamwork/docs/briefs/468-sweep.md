# Brief — #468 half 2: retro-fit `Lane-owns:` so the containment guard is not inert

Repo: `ud-dreamwork`. Worktree: **`.worktrees/sweep`**, branch **`wt/sweep`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: .dreamwork/docs/briefs

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[sweep]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/sweep-inbox.md` so I can steer you mid-task — I do, and two
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

## The state, measured

Read `#465` and `#468` in `.dreamwork/tasks.md`, and `file-formats.md`'s `Lane-owns:` section.

`dev/lane_guard.py` refuses a main-checkout commit touching a dispatched lane's owned paths, and
`lint.check_lane_containment_backstop` errors when such a path is merely *dirty*. Both read ownership from the
lane's **brief**, as a machine-parseable `Lane-owns:` line.

**Today lint reports `65 worktree-naming brief(s), 0 in scope after lane-owns rule, 65 grandfathered`.** Every
brief written before the rule is exempt, so for those lanes the mechanism protects nothing. That is deliberate
— history is not rewritten to satisfy a new check — but it means the guard's coverage is only as wide as the
briefs that declare.

## Your job, and its one real trap

Add a `Lane-owns:` line to the briefs where it is **true and useful**, and leave the rest alone.

**The trap: a `Lane-owns:` line is not documentation, it is a rule that refuses commits.** A wrong or
over-broad declaration on a brief that gets re-run makes files untouchable that are not owned — and the
failure lands on *the coordinator's* commit, which is the one thing the constraint on `#465` forbids making
harder. So:

- Derive each brief's ownership from **what that brief actually says** — every one carries a prose
  *"Yours: … / Not yours: …"* section. Do not infer from the task, from git history, or from what the lane
  turned out to touch.
- **Where a brief's prose is ambiguous, skip it and list it in your report.** A skipped brief is the status
  quo; a wrong one is a new defect. Say how many you skipped and why — a sweep that silently covers 40 of 65
  and reports "done" is the kind of quiet truncation this repo logs as a lesson.
- **A brief whose lane is finished and merged will never run again** — declaring ownership on it protects
  nothing and adds a false claim to a historical document. Prefer briefs that could plausibly be re-run or
  extended, and say how you decided.
- Bold markers are invisible to the parser. `**Lane-owns:** …` fails; `Lane-owns: …` works. That happened to
  the first brief written after the rule landed — check your own work with `lint._parse_lane_owns`.

**Verify the sweep changed the coverage number**, and report it before and after. That row is the only
evidence the work did anything: `python3 lint.py --target . 2>&1 | grep lane-owns`.

Do not touch `lint.py`, `dev/lane_guard.py` or `file-formats.md` — briefs only. If you find a parser defect,
report it rather than fixing it.

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
