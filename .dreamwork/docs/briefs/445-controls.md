# Brief — #445 increment 2: the three-axis posture controls he asked for

Repo: `ud-dreamwork`. Worktree: **`.worktrees/controls`**, branch **`wt/controls`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: watch.py, test_watch.py, watch-design.md, dev/capture/posture.mjs, justfile

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[controls]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/controls-inbox.md` so I can steer you mid-task — I do, and two
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

## What he asked for

Read `#445` in `.dreamwork/tasks.md` and `file-formats.md`'s new posture section. Increment 1 landed the
**vocabulary** (`f57de41`): `.dreamwork/posture`, a sibling of `run-mode`, carrying **pace × asking ×
delegation**. His words: *"we should add controls for the new values and their dimensions. We can have like 3
stops on each axis maybe? IDK that i will leave up to you, but we get 3 dimensions of input is the point."*

**You are building the controls.** The closed sets already exist in `lint.py` — import them, never restate
them; a second copy of a closed set is the defect `#413` exists over.

## The problem increment 1 handed you deliberately

**The axes are asymmetric: asking has FOUR stops, pace has three, delegation is an integer target.** That is
not an oversight — asking's four levels are his own dictation and a lane was corrected tonight for compressing
them to three to make the control tidy. **Do not solve the asymmetry by deleting a level.** Solve it in the
control, and say how.

`#290`'s run-mode control is the prior art: a **10s arm** before writing, one `watch-events.log` line **only
on a real change**, re-read every tick. Reuse that idiom rather than authoring a second one. Three controls
that each arm independently may be three times the ceremony — if a single arm covering a whole posture edit
reads better, argue it.

**Delegation is a target, not a cap** (his ruling): `0` means *occasional* — average below 0.5 subagents
running — `1` means an average between 0.5 and 1.5. A control that reads as a limit misrepresents it. He also
said *"we can get agents to work on a single worktree as a pair"*, so the number is not a worktree count.

## Web UI bar

`CLAUDE.md`: *every contribution to the Web UI must be of EXCEPTIONAL quality.* **Load the relevant design
skills** and read **`watch-design.md`** and **`transitions.md`** before designing.

Every state change here is a transition with **no size floor** — a stop moving, an arm counting down, a
control arriving. `transitions.md` opens with *how to check*: an end-state assertion cannot fail on a motion
bug and neither can "did it move". **Sample.** Reduced-motion parity is part of the work.

Register a new guard in `justfile`'s `DEFAULT_GUARDS` (**56** today, each needing its file) or it gates
nothing.

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
