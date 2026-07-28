# Brief — #428: the only gate cries wolf whenever the machine is busy

Repo: `ud-dreamwork`. Worktree: **`.worktrees/falsered`**, branch **`wt/falsered`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: lint.py, test_lint.py, .dreamwork/docs/plans/suite-under-lanes.md

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[falsered]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/falsered-inbox.md` so I can steer you mid-task — I do, and two
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

## The measurement

Read `#428` in `.dreamwork/tasks.md`, especially the third instance recorded tonight.

`test_lint.py::TestTheBugItWasBuiltFor::test_this_repo_passes_its_own_linter` **FAILED** in a full run at
04:55 and **passed alone** seconds later, with `lint.py --target .` clean either side. The cause is measured,
not guessed: **that test lints the LIVE working tree**, and during the run another lane committed `Lane-owns:`
lines to 44 briefs while others wrote their own files. The tree it asserted about changed underneath it.

**Why this matters more than a flake:** there is no CI, so this suite is the only gate, and the human has
asked for up to **8 concurrent lanes** — so a test that reads mutable shared state during another lane's
commit is a false red **by design**, not by luck. Tonight's run had exactly one failure in 1193 tests and it
was this one. A gate that cries wolf when the machine is busy gets read as noise, and the next real failure
arrives wearing the same clothes.

## What to build, and the trap

**Fix the scope, not the tolerance.** Rivals worth an IGC (`igc-method.md`): lint a **snapshot** (`git stash
create`, or a temporary clone) so the assertion is about a fixed tree; **skip** while lanes are out
(`lint._live_lane_worktrees` already answers that); or move it out of pytest into the quiet-tree gate.

**Do NOT simply retry it.** A retry hides the mechanism and preserves the false red for whoever runs it next.

**The trap, and it is this repo's favourite:** a skip is how a check stops examining anything. If you skip,
the reason must be **printed** and the skip must be *visible in the output*, or you have converted a false red
into a silent pass — strictly worse, because nobody will ever notice. Prefer the snapshot if you can make it
cheap; if you skip, say exactly what a reader sees.

**Then look for siblings.** Any other test that reads the live tree — `git` state, the briefs directory, the
review directory, `status.json` — has the same defect. Enumerate them and report what you found, even where
you do not fix it. A count of the exposed surface is worth more than one fixed test.

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
