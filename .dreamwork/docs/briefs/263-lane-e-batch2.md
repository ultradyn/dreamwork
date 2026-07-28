# Brief — #263 lane E, batch 2: increments 23–24 (`E4 besteffort`, `E5 reject`)

Repo: `ud-dreamwork`. Worktree: **`.worktrees/laneE2`**, branch **`wt/laneE2`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[laneE2]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/laneE2-inbox.md` so I can steer you mid-task.

Report one line per increment as it lands (`E4 committed <sha>`, red line named). Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which model you are** at the top.
**Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` — report the lines
you want added.

## Where batch 1 left the code, verified rather than reported

`E1`/`E2`/`E3` are merged at `df2989e`. The cutover is **live and I verified it end-to-end myself**: `POST
/command {kind:'add-idea'}` returns `202`, `Location: /user-events/<id>`, and that receipt id is present in all
three tables of `.dreamwork/user-events.sqlite3`. So you are building on a working cutover, not a claimed one.

The shape you inherit:

- **`_send_receipt` (`watch.py:9827`)** is the write-route success path: `202` + `Location` + receipt
  id/sequence/digest merged into the handler's body. It **refuses to mint a `202` from a missing receipt**
  (`send_error(503)`) rather than fabricating an id — do not weaken that.
- **`journal_result()` (`:9818`)** is the committed `ReceiveResult`, or `None`; `do_POST` has already returned
  `503` in the `None` case (`:10088`).
- A **legacy fallback** exists for `journal_shadow=False` (plain `200`, no receipt). It is the pre-cutover path
  `E2`'s baseline exercises. Keep it working; do not delete it as dead code.
- **Pre-`E5`, an invalid `kind` is a synchronous `400`** by design (`_handle_command`, `:10211`, against
  `COMMAND_KINDS`). `E5` is precisely the increment that moves that decision to *after* the receipt — so the
  `400` you find today is the thing you are changing, not a bug.

## Your scope: increments 23 and 24 — and nothing past 24

**The plan is the specification. Read `.dreamwork/docs/plans/user-event-journal-implementation.md`
§"Lane E — HTTP" rows 23 and 24 (prose at lines ~626 and ~636) and implement them exactly as written.** Each row
names its test, its **red line**, and a *"must not fake"* clause; I am not restating them here, because a
paraphrase is how a lane ends up building the brief instead of the plan.

Two things deserve emphasis because they are where this batch will fail if it fails:

- **`E4` must not turn a best-effort failure into a refusal.** A `submissions.log` write failure is
  `shadow_failed` health **on a durable receipt** — the receipt already committed, so the request was accepted
  and the response must still be a `202`. A lane that reds this by making the route fail has inverted the
  contract. Induce the log failure at a **real seam** (permissions on the real path), not by patching the writer.
- **`E5`'s hard part is that rejection is now durable, not synchronous.** A malformed or schema-invalid body gets
  a `202` *and* a durably recorded `rejected` status with a **bounded** reason code — bounded meaning a closed
  set, not the exception text, because the reason is read back by a projection and free text becomes an
  unparseable field. State the closed set where a parser can find it. `_read_json` is at `watch.py:8354`.
  **Every browser-side check is `res.ok`** across 9 sites, so a `202`-then-rejected body is invisible in the UI
  today — that visibility is `E6`, not yours.

**Increment 25 (`E6`) is out of this batch.** It is a browser/motion increment: it needs `transitions.md` and the
design skills loaded, and it is not a tail you bolt onto this one. Report it as the successor.

## Verification — the rules that have actually caught things here

- **Red-proof every increment on the line the plan names.** Reinstate/remove that line, watch the named test
  fail, and report it. **A green red-run is a finding, never a relief** — this plan has had **three wrong red
  lines** (`B1`'s pragma was already the compile-time default; `B7`'s `UNIQUE` was not the line carrying
  concurrency; row 15's predicate was `D1`'s). If your prescribed red comes back green, **say so and find which
  layer is actually holding the property up**.
- **Assert each check's precondition at runtime.** Derive it; never a literal tuned to today's tree.
- **Beware the scaffolding that stands in front of the code.** If a test hand-builds what the production
  function decides, reverting that function changes nothing the test can see — that has happened twice here.
  Name the production line you changed to red it, and change *that*.
- **New this batch, and it cost me two false results tonight: assert *whose* server answered.** If you start a
  `watch.py` and probe it over HTTP, resolve the listener's pid from `ss -ltnp` and **assert it equals the pid
  you started**. `watch.py` has **no `--no-open` flag** — passing one kills the server on an argparse error, and
  your request then silently reaches whatever stale server owns that port. I read a correct cutover as broken
  twice this way. Also: verify your server actually came up before asserting anything about its behaviour.
- Keep lane E's tests in **`test_user_events_http.py`** (exists now, from batch 1).
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`.** Bind nothing in 39880–39889 or 39890–39899 — those are guard ranges, and two orphaned servers
  squatting 39895/39896 are exactly what corrupted my probe. Kill every process you start, by exact pid.
  `TestCitedShas` can fail under random order with `OSError: File too large` when several lanes run `git` at
  once — known interaction, use `-p no:randomly`, say if you see it.
- Do **not** restart, `pkill` or redeploy the dashboard on **:35110** (he is reading it). Do not touch the
  heartbeat, the monitors, or the loop. Never `pkill -f` — build process patterns from parts.
- Trailer: a new durable `rejected` status changes what an existing install records. `Migration:` or `Feature:` —
  decide and say why.

## Files

**Yours:** `watch.py` (the HTTP paths only), `test_user_events_http.py`, `user_events/*` if a row requires it,
and the plan document **only** to amend a row you proved wrong (with the reason visible, as previous lanes did).

**Not yours:** `lint.py`, `test_lint.py`, `file-formats.md`, `review_artifact.py`, `.dreamwork/review/**`,
`transitions.md`, `watch-design.md`, `justfile`, `dev/capture/*`, `dev/ledger.py`, `SKILL.md`, `DREAMWORK.md`,
`.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/handoffs.md`, `migrations/*` (a lane holds those).

**Note:** lane **G** also lives in `watch.py`, so it is deliberately not dispatched while you hold it. Keep your
diff to the HTTP paths so that stays true.

## Practical

- 2 threads. **One commit per increment**, `git add <newfile>` then
  `git commit --only <paths> -m 'feat(#263): E4 …'` — **`--only`, never `git add -A`**: a lane's staged test was
  once swept into an unrelated ledger commit (`12f47e3`) exactly this way, and `--only <dir>` silently skips
  untracked files.
- **Commit before you finish**, and **land what is done even if the batch is not** — two lanes have exited with
  correct work uncommitted.
- **~20 minutes per increment is the shape.** If `E4` alone consumes the batch, land it and report.
- Choosing between rival implementations? Use **IGC** — `igc-method.md` in the repo root: binary goals or
  breakpoints, `✔`/`✘`/`?`, decisive error under each `✘`, no scoring.
- **Push back with reasons** if a plan row is wrong. Three of its red lines were, and each lane that said so was
  right to.

## Report

Say: which model you are; one line per increment with its sha; the red line you changed for each and what
failed; any prescribed red that came back **green** and what you found instead; `E5`'s closed reason-code set and
where a parser finds it; the seam you used to induce `E4`'s log failure (and confirmation you did not patch the
writer); the trailer you chose; and confirmation you built nothing behind purge/PostgreSQL, did not touch
:35110, killed every server you started by exact pid, and did not run the full `just test`.
