# Brief — #294: design the SQLite ledger migration — DESIGN ONLY, nothing built

Repo: `ud-dreamwork`. Worktree: **`.worktrees/ledgerdb`**, branch **`wt/ledgerdb`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: .dreamwork/docs/plans/ledger-sqlite.md, .dreamwork/review/src/294-ledger-sqlite.html, .dreamwork/docs/doc-map.md

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[ledgerdb]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/ledgerdb-inbox.md` so I can steer you mid-task — I do, and two
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

## Scope: a design and a review artifact. Build nothing.

Read `#294` in `.dreamwork/tasks.md` — all of it, it is long and it is his. He asked (via `/answers`
2026-07-27 01:17) for the durable ledger to move from Markdown to SQLite behind a CLI: `dreamwork tasks
list|get|grab|cycle`, transactional claims/CAS/leases for same-target agents, and a *"deliberately readable
and user-modifiable"* migration script that dry-runs, reports exact counts/IDs/digests/conflicts, backs up,
imports atomically, verifies before cutover, and has explicit rollback.

**This task is P1 and it is the loop's own memory.** Getting it wrong loses the ledger, so the deliverable is
a design he can rule on, not code. **`#294` says it is blocked on `#264`'s concurrency design and `#263`'s
journal boundary — establish what those actually settled before designing on top of them**, and if a
dependency is genuinely unmet, say so and design only what does not rest on it.

## What the design must decide, with an IGC

`igc-method.md` / `igc-concepts.md` in the repo root: binary goals or breakpoints, `✔` non-refuted / `✘`
refuted **with the decisive error written out** / `?` a TODO, an `All` rollup, **never a score**.

Decisions worth rivals: **where the id sequence lives** (ids are permanent and never reused, and the ledger
hands out the next one); **what the single writer becomes** (today the coordinator is the only writer by
convention — a database makes concurrent writers *possible*, which is a new hazard, not a feature);
**whether `tasks.md` remains generated** for reading, and if so who regenerates it and when; **how a
compacted coordinator reads the queue** without loading 8,000 lines.

**The requirement most likely to be skipped:** he asked that *"every task grab/status/priority/complete
transition automatically maintain the dashboard's burndown history and live status projection through the
canonical transaction/outbox — no agent hand-editing `status.json`, no Git-HEAD lag, and no second derived
truth."* Today `status.json` and the ledger drift and `lint` warns when they disagree (`#362`). Say what
happens to that check.

## The artifact is mandatory

**Every request for a review ships a review artifact** (his rule, 2026-07-25): self-contained HTML, inline
everything, offline-clean, at `.dreamwork/review/src/294-ledger-sqlite.html` — read `review_artifact.py` and
an existing artifact first, and follow how they are built rather than inventing a second way. Report the
`questions.md` lines you want filed; **do not write `questions.md` yourself**.

Add your `doc-map.md` row. It is contended — resolve as a **union** and verify the row against the directory
**both ways**.

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
