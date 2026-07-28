# Brief — plugins/ud-dreamwork-hooks: what does the hook plugin actually guarantee, and is any of it checked?

Repo: `ud-dreamwork`. Worktree: **`.worktrees/hooktests`**, branch **`wt/hooktests`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: plugins/ud-dreamwork-hooks, .dreamwork/docs/plans/hook-plugin-coverage.md

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[hooktests]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/hooktests-inbox.md` so I can steer you mid-task — I do, and two
lanes tonight were corrected mid-flight through exactly that channel.

Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md` (absolute path, main checkout — a report
written inside your worktree reaches nobody); **state which model you are** at the top, taken from the alias
you were dispatched with if you know it. **Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or
`.dreamwork/questions.md` — report the lines you want added.

**Report a line per milestone and commit as you go.** Lanes have been killed mid-task by an external sweep
with everything uncommitted and their final reports lost to 0-byte files.

**Several lanes are running.** Touch only your `Lane-owns:` paths — `dev/lane_guard.py` and
`lint.check_lane_containment_backstop` name you by file and branch otherwise, and tonight they caught the
coordinator doing it. Verify cwd and branch before **every** write.

## Why this lane exists

`plugins/ud-dreamwork-hooks/` ships hooks that run inside the human's harness. It has a `tests/` directory, so
somebody meant to check it — but nobody has audited whether what it ships is what the tests cover, and a hook
that silently stops firing is invisible by construction: the loop keeps working, slightly worse, forever.

**This is an audit first and an implementation second.** Do the measurement before you write anything.

## What to establish, in order

1. **What each hook claims to do**, from its own source and any docs in the plugin. List them.
2. **What the existing tests actually assert** — and for each hook, whether a test would fail if the hook
   stopped firing entirely. That is the only question that matters. A test that imports a hook and checks a
   pure function while the *registration* is broken proves nothing; name the production line for each.
3. **Run them** and report the result, including how they are (or are not) wired into `just test`. A test suite
   nothing runs is documentation. `#310` found exactly that: *"not yet wired into `just test`"* had been false
   for two days in one doc and assumed true in another.
4. **Then close the widest gap you found**, with a red-first test. One real check beats an inventory.

## Constraints

- **Do not change hook behaviour** to make it testable without saying so plainly — these run in his harness,
  and a hook that changes what it does is a change to his environment, not just to this repo.
- If a hook cannot be tested without his harness running, **say that** rather than writing a test that fakes
  the harness so thoroughly it tests the fake. That is the shape of two hollow checks found here recently.
- Report the `doc-map.md` row you want; you do not own that file.

## Verification — this repo's rules

- **Red-proof every check on the production line.** Name the line whose change reds it, change *that*, and
  watch it fail. **A green red-run is a finding, never a relief.**
- **Could your red have been produced against the code as it stood before your diff?** A red that needs a seam
  your change introduced is circular; a lane was rejected for that tonight.
- **Assert the precondition the check depends on, derived at runtime**, and put the count on the OK row. A
  check that examines nothing is output-identical to one that found nothing — that exact bug was found twice
  tonight, once in a coverage row reading `7 of 8`, once in tests appended into the wrong class so they never
  ran at all.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`.** Note `test_this_repo_passes_its_own_linter` can FALSE-RED while other lanes commit (`#428`) —
  if it fails, re-run it alone before believing it, and say so.
- Bind nothing in 39880–39899. Kill by exact pid; never `pkill -f`. **Never touch :35110**, the heartbeat, the
  monitors, or the loop.
- 2 threads. **One commit per increment**: `git add <newfiles>` then `git commit --only <paths>` — never
  `git add -A`; `--only <directory>` silently skips untracked files.
- ~20 minutes. **Commit before you finish.** Trailer where it applies; decide and say why.
- **Push back with reasons.** Several briefs tonight had premises measurement refuted — doubting mine is
  expected.
