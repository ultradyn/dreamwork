# Brief — #469: record which MODEL ran, from the dispatch config and never from a self-report

Repo: `ud-dreamwork`. Worktree: **`.worktrees/runner`**, branch **`wt/runner`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: .dreamwork/docs/plans/ccc-runner-routing.md

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[runner]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/runner-inbox.md` so I can steer you mid-task — I do, and two
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

## Read this first: the task was filed on a wrong finding, and the correction IS the task

`#469` in `.dreamwork/tasks.md` was filed at 04:24 claiming *"`ccc @glm52` runs grok"*. **The human corrected
it at 04:47:** *"@glm52 resolves to the grok CLI but uses the glm-5.2 model. the cli harness is nice and works
better than pi or opencode for this."* So the two-model mix works, and nothing about routing needs fixing.

**Both signals the claim rested on were unreliable, in opposite directions:**

1. `ccc` prints `warning: runner "grok"` — that names the **CLI harness**, and never claimed anything about the
   model.
2. A lane asked *"state which model you are"* answered **`grok-4.5 (xAI)`** while running glm-5.2, and a direct
   probe answered `Grok (xAI)`. A model's account of its own identity, under a harness that supplies one, is
   not evidence.

They were believed because they agreed — and they agreed because both were the same misreading.

## What to build: provenance from the dispatch, not from the process

- **Find where `ccc` maps an agent alias to a model.** `ccc` is a compiled binary at `~/.cargo/bin/ccc`; run
  logs are under `~/.local/state/cc-w/ccc/runs/` named by *runner*. Look for a config the alias resolves
  through (`ccc --help` and any config/doctor/agents subcommand, `strings` for config paths, whatever env it
  reads). **Report the path and the resolved `@grok` and `@glm52` definitions, quoted.**
- **Then say how a dispatcher can record the model truthfully** — the smallest reliable step. If it is *"read
  this config file at dispatch time"*, say which key. If the mapping lives only in the human's head or in the
  binary, say that, and the honest answer becomes *"record the alias, never a model name"*.
- **Do not probe models for their identity.** That is the method that produced the wrong answer, and each probe
  costs him money. One probe is acceptable only to demonstrate that a self-report is wrong — which is already
  demonstrated twice, so you probably need none.
- **Re-correct the attributions, the other way.** Ledger rows crediting `@glm52` lanes were **right**; the rows
  this session wrote as `grok-4.5` for the `axes` and `contain` lanes are wrong. `grep -rn "grok-4.5\|glm52"
  .dreamwork/` and report the corrections as lines for me to apply — **do not edit `.dreamwork/tasks.md`,
  `questions.md` or `status.json`**. Where the record is genuinely unknown, write **unknown**; a model
  attribution is history and history is never guessed.

## Constraints

- **Do not change any dispatch machinery, config or alias.** This is an investigation. If the fix is a config
  edit, propose it with the exact diff and let me and the human decide — his dispatch path is his.
- Do not spend the whole budget probing models. **One identity probe per candidate runner is enough**, and
  each costs him money.
- Write findings to `.dreamwork/docs/plans/ccc-runner-routing.md` as you go, not only at the end.
- If the honest conclusion is *"there is one model here and the two-alias convention is a fiction"*, say that
  plainly. It is the most useful possible result and it changes how the whole fan-out is planned.

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
