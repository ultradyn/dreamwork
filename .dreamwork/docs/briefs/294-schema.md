# Brief — #294 increment 1: the schema and the seeded sequence, verified. No cutover.

Repo: `ud-dreamwork`. Worktree: **`.worktrees/schema`**, branch **`wt/schema`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: ledger_store.py, test_ledger_store.py, .dreamwork/docs/plans/ledger-sqlite.md

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[schema]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/schema-inbox.md` so I can steer you mid-task.

Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not state a model name for
yourself** — the harness exports only `CCC_PROVIDER`, so you cannot know it; write the caveat instead (the
rule is at the top of `.dreamwork/handoffs.md`). **Do not write `.dreamwork/handoffs.md`**,
`.dreamwork/tasks.md` or `.dreamwork/questions.md` — report the lines you want added. **Report a line per
increment and commit as you go**; an external sweep killed four jobs here half an hour ago.

## He ratified the design an hour ago. You are building the first piece of it, and only that.

Read `#294` in `.dreamwork/tasks.md` and **`.dreamwork/docs/plans/ledger-sqlite.md`** in full — it is the
design and it is authoritative. His answer, **2026-07-29 05:48, `rec` on all five**, settles R1–R4 and C1.

**The two that govern this increment:**

- **R1 — the id sequence lives in the store** (`AUTOINCREMENT`), **seeded from today's next id and VERIFIED
  before cutover**. His stated reason: ids are permanent and never reused, so the sequence is the one thing a
  bad import must not be able to reset.
- **C1 — machine-local.** No hosted store, no network, same trust boundary as today. stdlib `sqlite3` only.

## Scope, and the line it stops at — this is the important part of this brief

**IN:** the schema, the store module, opening/creating it, the seeded sequence, and the **verification that
the seed is right**. Tests. The plan updated where building it teaches you something the design got wrong.

**OUT, firmly:** **no cutover, no import, no migration script, no `tasks.md` rename, no shim, no notice, no
writes to anything under `.dreamwork/` except the plan you own.** Shipping is gated on `#263` lane H and
`#352` — his ask said so and his ruling did not change it. A lane that migrates the live ledger tonight has
destroyed the loop's memory, which is the one failure this repo cannot recover by re-running anything.

**Read-only against the real ledger is fine and is encouraged** — parse it, count it, seed from it in a
temporary database under `tmp_path`. Never write it.

## The decisions that are actually yours

1. **The schema.** Entries, their ids, states, origins, priorities, parents, relations, and the event/receipt
   shape the plan describes. `user_events/sqlite.py` is prior art in this repo for a stdlib-only store with a
   closed reason set — read it before inventing a second house style, and say what you reused.
2. **What "verified" means for the seed, concretely.** This is the heart of the increment. *"Seeded from
   today's next id"* is not a test; a test is something that fails when the seed is wrong. Derive the expected
   next id from the Markdown ledger **through the same parser `lint` uses** (`lint.load_watch()` →
   `parse_ledger`), not by a second regex — a second parser is a second truth, which is exactly the error
   `#294` R2 refused when it rejected dual-write shadowing.
3. **What happens when the seed cannot be established.** A store that opens with a *wrong* sequence is worse
   than one that refuses to open. Closed set, fail loud, and say what the caller sees.

## Verification

- **`AUTOINCREMENT` has a specific property you must actually test**, not assume: SQLite's
  `sqlite_sequence` high-water mark is what stops a deleted id being reissued. Prove it — insert, delete the
  highest row, insert again, and assert the new id did **not** reuse the old one. If that fails, the schema is
  wrong and R1 is unimplemented whatever the DDL says.
- **Red-proof each check on the production line.** Name the line whose change reds it, change *that*, and
  watch it fail. **A green red-run is a finding, never a relief** — twice in one evening here a red run came
  back green because the test's own scaffolding stood in front of the injection.
- **Could your red have been produced against the code as it stood before your diff?** Your module is new, so
  most reds trivially need it to exist; that is fine. What is **not** fine is a test that builds the expected
  value the same way the code does — name, for each test, the production line that must change for it to fail,
  and if you cannot name one, there isn't one.
- **Assert the precondition, derived at runtime.** A seed test needs the real ledger to have a non-trivial
  next id; assert that before asserting the seed matches it, or the check passes on an empty parse.
- Any file shape a tool parses goes in **`file-formats.md`** — **not yours**: report the paragraph you want.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`** — it is 15+ minutes at this machine's load, and two other lanes are working.
- Bind nothing; start no server; this increment needs no browser and no port.
- **Do not touch :35110**, the heartbeat, the monitors, or the loop. Never `pkill -f`.
- Trailer: `Feature:` — and explicitly **not** `Migration:`, because nothing an existing install reads changes
  in this increment. If you think it does, you have exceeded the scope above.

## Files

**Yours:** the three in `Lane-owns:` above. `ledger_store.py` and `test_ledger_store.py` are **new** — remember
`git add` before `git commit --only`, because `--only <directory>` silently skips untracked files.

**Not yours:** `watch.py`, `test_watch.py` (a lane holds them), `lint.py`, `test_lint.py`, `file-formats.md`,
`dev/lane_guard.py`, `user_events/*` (**read** it for prior art, do not edit), `review_artifact.py`,
`dreamhub.py`, `justfile`, `SKILL.md`, `DREAMWORK.md`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`,
`.dreamwork/handoffs.md`, `.dreamwork/lessons.md`, and **every other file under `.dreamwork/`**.

## Practical

- 2 threads. **One commit per increment**, `git commit --only <paths>` — **never `git add -A`**.
- **Work only inside `.worktrees/schema`.** Verify cwd and branch before every write — the pre-commit guard,
  `lint`'s backstop and the new `pre-merge` assertion will each name you by file and branch.
- ~25 minutes. **Commit before you finish**, and land the schema plus the sequence proof rather than nothing.
- **Push back with reasons.** If building the schema shows the plan wrong somewhere, fix the plan and say so —
  it is yours for exactly that reason. Four lanes tonight refuted their briefs with measurement and every one
  was right to.

## Report

Say: the schema, and what you reused from `user_events/sqlite.py` rather than reinventing; how the seed is
derived through `lint`'s own parser and why that avoids a second truth; the **`sqlite_sequence` non-reuse
proof** and its result; what happens when the seed cannot be established; for each test the production line
whose change reds it and confirmation no red needed a seam your diff introduced; the runtime-derived
preconditions; the `file-formats.md` paragraph you want; anything the plan got wrong and how you fixed it;
and confirmation you wrote **nothing** under `.dreamwork/` except the plan, never touched the live
`tasks.md`, worked only in `.worktrees/schema` (state the cwd and branch you verified), started no server,
never touched :35110, and did not run the full `just test`.
