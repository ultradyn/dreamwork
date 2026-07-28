# Brief — #471: explain why a guard cannot be run alone, when the full run disagrees

Repo: `ud-dreamwork`. Worktree: **`.worktrees/guardport`**, branch **`wt/guardport`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: .dreamwork/docs/plans/suite-under-lanes.md, dev/capture/serve.mjs

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[guardport]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/guardport-inbox.md` so I can steer you mid-task.

Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not state a model name for
yourself** — the harness exports only `CCC_PROVIDER`, so you cannot know it; write the caveat instead (the
rule is at the top of `.dreamwork/handoffs.md`). **Do not write `.dreamwork/handoffs.md`**,
`.dreamwork/tasks.md` or `.dreamwork/questions.md` — report the lines you want added. Commit as you go and
report a line per milestone; an external sweep killed four background jobs here an hour ago.

## This is an INVESTIGATION. The deliverable is an explanation, not a patch.

Read `#471` in `.dreamwork/tasks.md`. The coordinator wrote it and the honest part is the admission at the
end: **I do not know why these two observations disagree**, and the first draft of the finding claimed
something the evidence did not support.

**Observation A.** `DREAMWORK_GUARDS=reviewdraft just guards` fails. So does
`DREAMWORK_GUARDS=identity just guards`. Both fail the same way:

```
Error: serve: :39899 is serving /tmp/tmp.X/target, not /tmp/tmp.X/identity/alpha-loop
       — a stale server holds the port and every assertion after this would grade the wrong target
```

The mechanism looks plain: `justfile`'s `guards` recipe pre-starts a server on `{{port}}` serving
`$OUT/target`, then invokes each guard as `node dev/capture/$g.mjs "$OUT/$g" {{port}}`. A guard that serves
its **own** directory calls `serveVerified(DIR, PORT)` with that shared port, finds it held by a server for a
different directory, and correctly refuses.

**Observation B, which contradicts the conclusion.** In the full `just test` run at 05:33, **`identity`
PASSED** — same shared port, same own-directory shape. `gitrow` and `serving` passed too.

**Both of my reproductions were single-guard runs.** So I have **no evidence** that any self-serving guard
fails in a full run, and the claim that some of the 57 guards silently do not gate is **unsupported**. Do not
inherit it. Your job is to find which of these is true:

1. Something in a full run frees `{{port}}` before the self-serving guards are reached (what, and is that
   deliberate or luck?).
2. Those guards differ from `reviewdraft` in a way I did not find.
3. Something about `DREAMWORK_GUARDS=<one>` changes the recipe's behaviour beyond the guard list.
4. Something else.

## Facts already established, so you do not re-derive them

- 8 of 58 registered guards call `serveVerified`: `fileimg filehead identity gitrow fileview reviewdraft
  staleremedy serving`.
- `identity`, `gitrow`, `serving`, `filehead`, `fileview`, `fileimg` all use
  `process.argv[3] ? +process.argv[3] : await freePort()`.
- `reviewdraft` uses `+(process.argv[3] || 39894)` — a **hardcoded** exclusive port.
- `staleremedy` uses `await freePort()` and **ignores `argv[3]` entirely**.
- The recipe resets `$OUT/target` from the fixture before **every** guard, and the shared server re-reads from
  disk per request, so it is never restarted mid-run.

## Method, and one trap to avoid

**Measure; do not reason from the recipe text.** The coordinator reasoned from the recipe and got a
conclusion the full run refuted — that is the whole reason this task exists. Run things and record what
happened.

**The trap:** the load on this machine sits near 50 on 16 cores because several agent sessions share it, and
a dozen guards sample frames and fail intermittently at that load. **A guard failing is therefore not
evidence of your hypothesis** unless the failure message is about the port or the target. Read the message,
not the exit code. The full-run output at
`/tmp/claude-1000/-home-xertrov--llm-general-skills-ud-dreamwork/c196985f-4070-4762-915f-7fd6cc8af895/scratchpad/justtest.txt`
is a real record of one full run — read it before running anything, it may answer the question for free.

**Do not run the full `just test`** to reproduce (15+ minutes, and two other lanes share the machine). A
**pair** or a **short list** of guards is enough to test whether "one guard" is the special case — that is
the cheapest discriminating experiment and it is probably the whole task.

## What you may change, and what you must not

**You own `dev/capture/serve.mjs`** — if the fix belongs in `serveVerified` (for example: refusing is right,
but the guard should be told to pick its own port when the shared one is not its own), that is yours.

**You do NOT own `justfile`.** Guard registration and the recipe are the coordinator's, centralised after two
lanes were granted the same `DEFAULT_GUARDS` line tonight. **Report the recipe change you want**, with the
exact diff, and say what it fixes and what it risks.

**You do NOT own `dev/capture/reviewdraft.mjs`** — another lane's guard landed there hours ago. If its
hardcoded `39894` is the defect, **report that too**; do not edit it.

## Verification

- **If you change `serve.mjs`, every guard that uses it is your blast radius.** Run a representative set
  (at least one self-serving guard and one shared-server guard) and report each result with its message.
- **Red-proof any check you add on the production line**, name the line, and confirm the red did not need a
  seam your diff introduced. **A green red-run is a finding, never a relief.**
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing.
- Bind nothing in 39880–39889 beyond what a guard you run binds; kill what you start by exact pid; check
  `ss -ltnp` before finishing. If you find an orphaned server from an earlier run, **report its pid and
  cmdline; do not kill it** without saying so — one of them turned out to belong to a live run tonight.
- **Do not touch :35110**, the heartbeat, the monitors, or the loop. Never `pkill -f`.
- Trailer: `docs:` for an explanation alone; `fix:` if you change `serve.mjs`.

## Files

**Yours:** the two in `Lane-owns:` above.

**Not yours:** `justfile`, `dev/capture/reviewdraft.mjs`, every other `dev/capture/*.mjs`, `watch.py`,
`test_watch.py` (a lane holds them), `ledger_store.py` (a lane holds it), `lint.py`, `test_lint.py`,
`file-formats.md`, `dev/lane_guard.py`, `SKILL.md`, `DREAMWORK.md`, `.dreamwork/tasks.md`,
`.dreamwork/questions.md`, `.dreamwork/handoffs.md`, `.dreamwork/lessons.md`.

## Practical

- 2 threads. **One commit per increment**, `git commit --only <paths>` — **never `git add -A`**.
- **Work only inside `.worktrees/guardport`.** Verify cwd and branch before every write.
- ~25 minutes. **Commit the explanation before you finish**, even if no fix follows from it — the explanation
  is the deliverable and a fix without one is a guess.
- **Push back with reasons.** *"There is no defect; here is why the two observations differ and why both are
  correct behaviour"* is a completely acceptable and possibly the best outcome. Say it plainly if so.

## Report

Say: which of the four possibilities is true, with the commands you ran and their **messages**; whether any
registered guard genuinely fails to gate in a full run (and if not, say so plainly so the ledger stops
implying it); whether `reviewdraft`'s hardcoded port is a defect; the exact `justfile` diff you want, if any,
with what it risks; anything you changed in `serve.mjs` and its blast radius measured; any orphaned server you
found (pid + cmdline, not killed); and confirmation you worked only in `.worktrees/guardport` (state the cwd
and branch you verified), edited no `justfile` and no other guard, left nothing listening, never touched
:35110, and did not run the full `just test`.
