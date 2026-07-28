# Brief — #402: `status.json`'s `dreamers` array has no stated shape, and it only ever goes stale one way

Repo: `ud-dreamwork`. Worktree: **`.worktrees/dreamers`**, branch **`wt/dreamers`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: status_sync.py, file-formats.md, test_status_sync.py

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[dreamers]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/dreamers-inbox.md` so I can steer you mid-task — I do, and two
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

## The defect, measured

Read `#402` in `.dreamwork/tasks.md`.

`status.json` carries the loop's runtime state — which lanes are out and what files each owns. It is how a
**compacted coordinator** avoids editing a file a lane holds. Three findings, all from using it:

1. **It goes stale in exactly the direction that costs parallelism.** `status_sync.py` recomputes `queue` and
   `current_task_ids` from live `pgrep` but **never touches `dreamers`**, so ownership only accumulates.
   `#396` and `#398` had landed and were still listed as owning five files. A stale entry says a free file is
   *owned*, so the coordinator declines a dispatch it could have made — and `#264` measured file contention as
   the **binding constraint** on how much runs at once. The constraint, manufactured.
2. **It crashed on a mixed-type id** — existing entries carry `"task": 396` (int), a new one `"task": "401"`,
   and `sorted()` raised `TypeError`.
3. **The shape is stated nowhere**, so every writer invents one. Tonight's coordinator wrote `owns`, `model`,
   `worktree`, `branch`, `brief` and `job`; `#465`'s lane measured the shape as `{task, pid, brief}` and
   correctly refused to build on it. **Both were right about different files at different times** — that is
   what an unstated shape produces.

## What to build

- **State the shape in `file-formats.md`**, in the same commit as the code that reads or writes it, and make
  `lint` check it. Ids: pick one type and coerce, or reject mixed and say so — but a `sorted()` that can raise
  on real data is not a shape, it is a crash waiting for a busy night.
- **Make `dreamers` self-expiring.** A lane's entry should stop being believed when the lane is gone. The pid
  is already recorded, and `status_sync.py` already does live `pgrep` for `queue` — that is the seam. Decide
  what "gone" means and what happens to a **stale-but-uncertain** entry: dropping an entry whose lane is
  alive is worse than keeping one whose lane is dead, because the first corrupts the disjointness invariant
  and the second only costs a dispatch. Say which way you erred and why.
- **`status.json` is gitignored and ephemeral.** Read it defensively: absent, truncated, or listing a lane
  that died is the *normal* case, and a check that hard-fails on it is worse than none.

Do not touch `watch.py` (another lane holds it) even though it reads this file — if a reader must change,
report the exact change for a later increment.

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
