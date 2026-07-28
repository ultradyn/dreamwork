# Brief — #471 successor: the suite must report which guards RAN, not which are registered

Repo: `ud-dreamwork`. Worktree: **`.worktrees/executed`**, branch **`wt/executed`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: justfile, lint.py, test_lint.py, .dreamwork/docs/plans/suite-under-lanes.md

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[executed]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/executed-inbox.md` so I can steer you mid-task.

Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not state a model name for
yourself** — the harness exports only `CCC_PROVIDER`, so you cannot know it; write the caveat instead.
**Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` — report the
lines you want added. **Commit each increment as it lands.**

## What happened, and the exact hole it went through

Read `#471` in `.dreamwork/tasks.md` and the `#471` section of
`.dreamwork/docs/plans/suite-under-lanes.md` (an earlier lane wrote it; it is yours now).

`#461` changed six own-server guards from `await freePort()` to `process.argv[3] ? +process.argv[3] : await
freePort()`, so a squatter red-proof could aim at a port. The `guards` recipe **always** passes `{{port}}`,
so those guards were forced onto the shared server's port, `serveVerified` correctly refused, and **eight
guards stopped executing at 02:56 and nobody noticed until 06:10.** Fixed at `80ac4b5`.

**The hole is the reporting.** `lint` says:

```
  OK    justfile          59 guard(s) registered, each with a file
```

That measures **registration**. Nothing measures **execution**. So a guard can be registered, have a file, be
believed to gate, and never run — which is `#310`'s family and this is now its second instance.

**And it cost more than the guards:** when `identity` was turned back on it immediately failed a real
assertion that had been wrong since `#263` E5 (it expected a refused tint to return 400; a durable rejection
is 202 with `rejected` in the body). That defect was invisible for as long as the guard was.

## Your job

**Make a run say which registered guards actually executed, and fail when the sets disagree.** Where that
lives is yours — the recipe already loops per guard and prints `PASS`/`FAIL`, so the information nearly
exists; what does not exist is the **comparison against the registered set** and a failure when one is missing.

Decisions that are yours, each needing an argument:

1. **What "executed" means.** A guard that ran and failed **did** execute; a guard that threw before its first
   assertion arguably did not. The `#471` guards all exited non-zero with an `Error:` before any check — the
   recipe printed `FAIL`, so a naive "did we print a line for it" test would have said yes and taught us
   nothing. **This is the crux: your definition must distinguish "ran and judged" from "died before
   judging."** `report.mjs` and the guards' `ok(...)` output are where a real signal lives.
2. **Where the failure surfaces.** A `lint` check reads files and cannot watch a run; the recipe can watch a
   run but is not `lint`. Both are yours, so pick, and say why — the axis that matters is whether it can be
   skipped.
3. **Whether a guard that reports zero assertions is a failure.** Consider it strongly: *a check that examines
   nothing looks identical to one that found nothing*, and that sentence is already in this repo's CLAUDE.md
   because it keeps happening.

**Do not weaken `serveVerified`** and do not touch `dev/capture/*.mjs` — those are not yours, the `#471` fix
already landed, and an earlier lane specifically argued that making `serveVerified` lenient would reopen the
defect it exists to close.

## Verification

- **Red-proof on the production line, and the red here is easy to make genuinely:** reintroduce `#471` by
  handing one own-server guard the shared port (in a **temporary copy**, not the real guard file, which is not
  yours — or by driving your comparison with a synthetic run record). Your check must fail. **If it passes,
  that is a finding, not a relief** — and check your injection reached the code before concluding the check is
  hollow, which cost the coordinator a near-miss tonight.
- **Assert the precondition at runtime.** A comparison of two sets is vacuous if either is empty: assert the
  registered set is non-trivial and that at least one execution record was seen, or a broken parse reads as
  "everything ran".
- **Put the counts on the OK row** — both numbers, registered and executed. A single number cannot show a gap,
  and the row that hid this bug had exactly one number on it.
- **Do not run the full `just test`** to prove the happy path — it is 15+ minutes at this machine's load and
  another lane is working. A short `DREAMWORK_GUARDS="..."` run of two or three guards is enough, and **note
  that a single-guard run of an own-server guard now works** (it did not before `80ac4b5`).
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. Do **not** regress the
  existing `lint` coverage rows.
- Bind nothing in 39880–39889 beyond what a guard you run binds; kill by exact pid; `ss -ltnp` before
  finishing. **Do not touch :35110**, the heartbeat, the monitors, or the loop. Never `pkill -f`.
- Any shape a tool parses goes in **`file-formats.md`** — that file is **not** yours; report the paragraph.
- Trailer: `Feature:`.

## Files

**Yours:** the four in `Lane-owns:` above. **Note you own `justfile` outright** — the coordinator centralised
guard *registration* at merge because two lanes were once granted that line, so if another lane's guard needs
registering I will do it after you merge; do not be surprised by a conflict on that one line.

**Not yours:** every `dev/capture/*.mjs` (including `serve.mjs` and `report.mjs` — **read** them, they are
where the execution signal lives), `watch.py`, `test_watch.py` (a lane holds them), `file-formats.md`,
`dev/lane_guard.py`, `ledger_store.py`, `review_artifact.py`, `dreamhub.py`, `SKILL.md`, `DREAMWORK.md`, and
everything under `.dreamwork/` except the plan.

## Practical

- 2 threads. **One commit per increment**, `git commit --only <paths>` — **never `git add -A`**.
- **Work only inside `.worktrees/executed`.** Verify cwd and branch before every write.
- ~25 minutes. **Commit before you finish**, and land the comparison even if the definition is still coarse.
- **Push back with reasons.** If the honest answer is that "executed" cannot be measured without changing the
  guards themselves (which are not yours), say so and name the change you would want — that is a real finding
  and a better outcome than a check that counts printed lines.

## Report

Say: your definition of executed and **how it distinguishes ran-and-judged from died-before-judging**; where
the check lives and the argument on the can-it-be-skipped axis; whether a zero-assertion guard fails and why;
the exact red you produced, the production line it names, and confirmation the injection reached it; the
runtime-derived preconditions; both counts on the OK row; the `file-formats.md` paragraph you want; and
confirmation you worked only in `.worktrees/executed` (state cwd and branch), edited no `dev/capture/*.mjs`,
left nothing listening, never touched :35110, and did not run the full `just test`.
