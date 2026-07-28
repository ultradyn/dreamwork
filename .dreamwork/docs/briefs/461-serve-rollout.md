# Brief — #461 rollout: every own-server guard must prove whose server answered

Repo: `ud-dreamwork`. Worktree: **`.worktrees/serveroll`**, branch **`wt/serveroll`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[serveroll]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/serveroll-inbox.md` so I can steer you mid-task.

Report a line per milestone (**counted**, **first batch adopted**, **red-proved**, **committed**). Full report
goes **once** to `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which model you
are** at the top. **Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or
`.dreamwork/questions.md` — report the lines you want added.

## The defect, already fixed once — you are extending its reach

Read **`#461` in `.dreamwork/tasks.md`**, then `dev/capture/serve.mjs` (landed `188b8b2`), whose header comment
is the full argument.

Short form: guards that start their **own** `watch.py` take a base port and increment it
(`ports[name] = ++port`), landing on fixed ports in **39890–39899** — the range that collects orphans. Their
readiness step is typically `await sleep(2500)` with `stdio: 'ignore'`. So when a port is already held, python
exits *address in use* invisibly, the sleep passes anyway, and **every later assertion grades a different
target** — the guard reports feature bugs about a fixture nothing ever read.

This was demonstrated on a real squatter, both directions: the old shape went on to grade the squatter's
fixture; `serveVerified` fails naming both targets and node exits 1, so it gates. `health.mjs` is the first
adopter (`dev/capture/health.mjs`).

**The `justfile`'s shared runner is already defended and is not your business** — it checks the port it owns and
compares `/data.json`'s `target`. Its comment claiming own-server guards are immune is the thing that was wrong;
`#461`'s ledger entry records that, so do not re-litigate it.

## Your job

**Adopt `serveVerified` / `serveAllVerified` across the own-server guards, in batches, verifying as you go.**

1. **Count first, and show the expression.** How many guard scripts in `dev/capture/` start their own
   `watch.py`, and how many of those already verify the responder? Derive both — do not quote my numbers, and do
   not trust a `grep` for `watch.py` alone (a script may mention it in a comment). Report the expression you used.
2. **Adopt in batches of a few, running each adopted guard green after conversion.** A guard that changes from
   spawn-and-sleep to `serveVerified` must still pass — if one goes red on adoption, that is a **finding about
   that guard**, not a reason to revert: it may have been depending on the sleep for settle time. Say which, and
   fix it by making the settle explicit rather than by restoring the blind sleep.
3. **Do not change what any guard asserts.** You are changing how it obtains its server. A diff that also
   edits an assertion is out of scope and hides the interesting part.
4. **`serve.mjs` itself is nearly off-limits.** Use it. If a guard genuinely cannot adopt it — a different
   server shape, an ephemeral port, a target that is not a directory — **say so and leave that guard alone**,
   with the reason. Extending `serve.mjs` is permitted only if two or more guards need the same extension, and
   then the extension needs its own red-proof.

## Verification

- **Red-proof the rollout the way it was red-proved the first time: with a real squatter.** Start a `watch.py`
  on a port an adopted guard will want, run that guard, and confirm it **fails naming both targets** and that
  **node exits non-zero** (the exit code is what gates; a printed FAIL alone is not). Kill the squatter by exact
  pid. Do this for at least one guard per batch, not once for the whole rollout.
- **A green red-run is a finding, never a relief.** If a guard passes with a squatter on its port, it has not
  adopted the helper on the path that actually runs — find out why.
- **Assert preconditions at runtime**, derived — never a literal tuned to today's tree.
- `python3 lint.py --target .` clean (it checks that every `.mjs` in `dev/capture/` is either registered in
  `justfile`'s `DEFAULT_GUARDS` or listed in `lint.NOT_GUARDS` with a reason — `serve` is already listed, do not
  touch that entry). `python3 -m pytest -q -p no:randomly` passing.
- **Do not run the full `just test`.** Run the individual guards you converted.
- **Ports:** the guards bind 39890–39899 by design; that is expected and fine. Bind nothing in 39880–39889 (the
  hub). **Kill every process you start, by exact pid** — orphans in this range are the exact defect you are
  fixing, and leaving one behind would be a bad joke. Before you finish, run `ss -ltnp` and confirm nothing of
  yours is still listening.
- Do **not** restart, `pkill` or redeploy the dashboard on **:35110** (he is reading it). Do not touch the
  heartbeat, the monitors, or the loop. Never `pkill -f` — build process patterns from parts.
- Trailer: guards gaining a startup check that can refuse a run is `Feature:` — the same call `#461` made;
  confirm or differ with a reason.

## Files

**Yours:** `dev/capture/*.mjs` **except** `serve.mjs` and `report.mjs` (use them; do not edit them), and
`health.mjs` only if you find a defect in its adoption.

**Not yours:** `watch.py`, `test_watch.py` (**two lanes hold `watch.py` right now — `laneE2` on the HTTP paths
and `updrel` on the staleness row**), `test_user_events_http.py`, `user_events/*`, `lint.py`, `file-formats.md`,
`migration_notice.py`, `review_artifact.py`, `.dreamwork/review/**`, `transitions.md`, `watch-design.md`,
`justfile` (nothing here needs registering), `SKILL.md`, `DREAMWORK.md`, `.dreamwork/tasks.md`,
`.dreamwork/questions.md`, `.dreamwork/handoffs.md`.

## Practical

- 2 threads. **One commit per batch**, `git commit --only <paths> -m 'fix(#461): …'` — **`--only`, never
  `git add -A`**: other agents commit in this tree.
- **Commit before you finish**, and **land the batches you finished** even if the rollout is not complete. A
  partial rollout is genuinely useful here: each adopted guard stops being able to grade a stranger.
- **~20 minutes.** If the count turns out large, land two or three batches and report the remainder as the
  successor with the exact list of unconverted guards, so the next lane starts from a list rather than a count.
- **Push back with reasons.** If most own-server guards turn out to be immune for a reason I have not seen —
  they already check, or they use ephemeral ports — that is a complete answer and a cheaper one. Show the
  evidence.

## Report

Say: which model you are; the derived counts and the expression; which guards you converted, batch by batch, with
shas; which guards you deliberately left and why; the squatter red-proof per batch including **node's exit code**;
any guard that went red on adoption and what that revealed; the exact list of unconverted guards; the trailer you
chose; and confirmation you edited no assertion, left nothing listening (`ss -ltnp` output checked), did not
touch :35110, and did not run the full `just test`.
