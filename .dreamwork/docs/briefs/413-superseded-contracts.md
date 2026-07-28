# Brief — #413: a guard can encode a contract that has since been superseded, and nothing measures that

Repo: `ud-dreamwork`. Worktree: **`.worktrees/superseded`**, branch **`wt/superseded`**. Do not push, do not
merge. **Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[superseded]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/superseded-inbox.md` so I can steer you mid-task.

Report a line per milestone (**instances measured**, **design chosen**, **implemented**, **red-proved**,
**committed**). Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which model you are** at the top.
**Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` — report the lines
you want added.

## Read `#413` first, then read the two instances tonight produced

`#413` in `.dreamwork/tasks.md` is the general statement. What it lacked until tonight was evidence; now there
are two, both measured, and **both are in `.dreamwork/lessons.md`** — read those two entries before designing
anything.

**Instance 1 — `health.mjs`, and it is the important one.** It carries exactly the checks this repo would want
for `#263`'s `E5` defect: *"never shows the answered state for a write that did not land"* and *"keeps his text,
which is now the only copy of it"*. Both were **green with the defect fully present**. Its `route.fulfill`
hardcodes `status: 409`, so it only ever drives a refusal where `res.ok` is **false**. `E5` moved refusal to a
`202`, where `res.ok` is **true**. The checks were structurally incapable of seeing it, and nothing in the guard
output said so. **This is the shape to solve: a fake's pinned parameter is part of the check's scope, and when
the contract moves, the fake keeps asserting the old world in the new one.**

**Instance 2 — a red-proof aimed at a pathway its own diff added** (`#461` batch 2, rejected). Different
mechanism, same family: a check whose relationship to the real contract was never verified.

## The task, and the hard part is what "superseded" can mean mechanically

**Do not start by writing a checker.** Start by measuring how big this is and in what forms, because the design
follows from that:

1. **Find the fakes.** `dev/capture/*.mjs` — every `route.fulfill`, every stubbed response, every hardcoded
   status, every pinned constant that stands in for a server behaviour. Derive the list and report it with the
   expression you used.
2. **For each, ask what production fact it is pinned to** — a status code, a header, a JSON shape, a route, a
   file format. Then ask whether that fact is still what production does. `REJECTION_REASONS` and the `202`
   cutover in `user_events/sqlite.py` and `watch.py` are tonight's moved facts; there may be older ones.
3. **Report the count of fakes whose pinned fact you could NOT verify against production**, separately from
   those you confirmed stale. "I could not tell" is a category and hiding it inside "fine" is the failure this
   task is about.

Then design the measurement. **Use IGC** — `igc-method.md` in the repo root: binary goals or breakpoints,
`✔`/`✘`/`?`, the decisive error written under each `✘`, never a score. Rival ideas worth stating: a lint check
that greps fakes for pinned statuses and requires a declared reference to the production constant; a convention
where a fake imports the constant instead of literalising it (so a moved contract fails at load); a per-guard
declaration of which contract it encodes, checked against a registry; a runtime assertion inside the fake that
the pinned value still appears in production source.

Goals that are binary and will refute at least one rival: *a fake pinned to a status production no longer
returns fails, rather than passing*; *the check cannot pass by matching nothing* (this repo's most-paid-for
failure); *adopting it does not require editing all ~69 guards at once* — the `report.mjs` and `serve.mjs`
precedent is that obligations are inherited one guard at a time, not swept.

**Be sceptical of a checker built on grep.** If the honest finding is that "superseded" cannot be detected
mechanically and the real fix is that fakes must *import* production constants rather than literalise them —
say so and argue it. That is a convention plus a narrow check, it is cheaper, and it fails at the right moment.
A refusal with evidence is a complete answer here; `#444` refused a threshold check on the ground that it would
merely restate the constant it read, and was right.

## Verification

- **Red-proof on the production line.** Name the line whose change reds your check, change *that*, and watch it
  fail. **A green red-run is a finding, never a relief.**
- **And the test this task itself teaches:** *could your red have been produced against the code as it stood
  before your diff?* If reaching the failure needs a seam your change introduced, the proof is circular. That
  mistake was made twice tonight, once by the coordinator.
- **Assert the precondition at runtime, derived** — never a literal tuned to today's tree. If your check
  examines N fakes, assert N > 0 from the filesystem, or the check can go quiet without anyone noticing.
- **The single most valuable concrete deliverable, if you get nothing else in:** make `health.mjs`'s two checks
  see a rejected `202`. They are the checks a future reader will trust, and today they are blind. Widening them
  is worth more than any new checker, and it is a real red-proof: with the widened fake, they must fail against
  the pre-`E5b` client and pass after. **Note `E5b` is in flight in another worktree** — if the client fix has
  not merged when you get there, widening the fake should make them **red**, and that red is the correct
  result; report it rather than papering over it.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`.** Run the individual guards you touch. Bind nothing in 39880–39889; kill everything you start by
  exact pid and check `ss -ltnp` before finishing.
- Use `dev/capture/serve.mjs`'s `serveVerified` if you start a `watch.py`. Note `watch.py` has **no
  `--no-open`** flag; passing one kills your server on an argparse error and your request reaches a stranger.
- Do **not** restart, `pkill` or redeploy the dashboard on **:35110** (he is reading it). Do not touch the
  heartbeat, the monitors, or the loop. Never `pkill -f`.
- Trailer: a new erroring check on an existing install is likely `Feature:`; decide and say why.

## Files

**Yours:** `dev/capture/*.mjs` (including `health.mjs`), `lint.py` and `test_lint.py` if your design needs them,
`file-formats.md` for any declared form you introduce (**same commit** as the code that reads it),
`justfile`'s `DEFAULT_GUARDS`, and a design doc at `.dreamwork/docs/plans/superseded-contracts.md` plus its
`doc-map.md` row (contended: resolve conflicts as a **union** and verify the row against the directory **both
ways**).

**Not yours:** `watch.py`, `test_watch.py`, `user_events/*`, `test_user_events_http.py` (**`laneE5b` holds those
and is mid-increment on the client write paths**), `dev/capture/serve.mjs` and `report.mjs` (use them, do not
edit them), `migration_notice.py`, `review_artifact.py`, `.dreamwork/review/**`, `transitions.md`,
`watch-design.md`, `SKILL.md`, `DREAMWORK.md`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`,
`.dreamwork/handoffs.md`, `.dreamwork/lessons.md`.

## Practical

- 2 threads. `git add <newfiles>` then `git commit --only <paths> -m 'feat(#413): …'` — **`--only`, never
  `git add -A`**: other agents commit in this tree, and `--only <directory>` silently skips untracked files.
- **Commit before you finish.** **~20 minutes.** Priority order if time runs short: (1) the measurement, (2)
  `health.mjs`'s two checks widened, (3) the general mechanism. The measurement alone is worth landing.
- **Push back with reasons.** The most valuable lanes tonight refused what they were handed — and one lane's
  work was rejected outright for proving something it had itself made true, so a smaller honest result is
  strictly better than a larger one that cannot be trusted.

## Report

Say: which model you are; the fake inventory and the expression that derived it; for each fake, the production
fact it pins and whether that fact still holds — with **"could not verify" as its own count**; the IGC with each
decisive error and the survivor; what you built or refused and why; whether `health.mjs`'s two checks now see a
rejected `202` and what they do against the unfixed client; the production line whose change reds each new
check, and confirmation your red did not need a seam your diff introduced; the trailer you chose; and
confirmation you left nothing listening, did not touch :35110, did not touch `watch.py`, and did not run the
full `just test`.
