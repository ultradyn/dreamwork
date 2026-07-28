# Brief — #263 lane E, batch 1: increments 20–22 (`E1 envelope`, `E2 shadow`, `E3 cutover`)

Repo: `ud-dreamwork`. Worktree: **`.worktrees/laneE`**, branch **`wt/laneE`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[laneE]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/laneE-inbox.md` so I can steer you mid-task.

Report one line per increment as it lands (`E1 committed <sha>`, red line named). Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which model you are** at the top.
**Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` — report the lines
you want added.

## The authority, and its exact edges

**The second gate is OPEN as of 2026-07-29 01:37** — his words, via the dashboard: *"ack good to go"*. Lane E
(increments **20–25**) is authorised. This matters because a lane was killed at 16:20 on 2026-07-28 for building
`E1` on a misread of an *answered question* as an *opened gate*; that is no longer the situation, the gate is
genuinely open, and the retraction was `6ea8f6b`.

**What the open gate still does not authorise:** payload **purge** and the **PostgreSQL** half. Those were
excluded by a different ruling (Q4) and this gate does not reach them. Do not build them.

**`200 → 202` is approved as a non-event** (his Q3: *"yes, a non-event"*). The 15 assertions pinning the literal
`200` move with the cutover — that count is by `ast`, not grep, which missed four multi-line `assertEqual`s.

## Your scope: increments 20, 21, 22 — and nothing past 22

**The plan is the specification and it is unusually precise. Read
`.dreamwork/docs/plans/user-event-journal-implementation.md` §"Lane E — HTTP" and implement rows 20, 21 and 22
exactly as written.** Each row names its test, its **red line**, and a *"must not fake"* clause. Do not
paraphrase them from this brief — the rows are authoritative and I am not restating them.

Three things from those rows deserve emphasis because they are where this lane will fail if it fails:

- **`E1`'s red is available immediately against real production behaviour** — the `len(body) != nbytes` check
  does not exist today. And **`urllib` cannot test it**: it always sends a complete body, so a `urllib` test
  with a short `Content-Length` tests the library and passes with the check absent. Use a raw `socket`.
- **`E2` must derive the route list from `watch.py`'s dispatch**, not from six hardcoded paths, so a seventh
  route added later fails the test instead of slipping past it.
- **`E3`(c) must not patch `sqlite3.connect`.** Real `chmod 0500`, real open failure. And the honest limit is
  already recorded: this covers *commit* failure; an `fsync`-specific failure needs fault injection and is a
  **recorded gap, not a claimed pass**. Do not close that gap by mocking.

**Increments 23–25 (`E4`, `E5`, `E6`) are out of this batch.** Report them as the successor. `E6` in particular
is a browser/motion increment and needs `transitions.md` plus the design skills loaded; it is not a tail you
bolt onto this one.

## Measured facts — reuse, do not re-derive

- **`_send` (`watch.py:8231`) hardcodes `send_response(200)`** and therefore cannot express a status code at
  all. The cutover needs a status-carrying send; that is the shape, not a refactor of everything.
- **Every browser-side check is `res.ok`**, across 9 sites — so `200 → 202` is invisible in the UI. That is why
  Q3 could be a non-event, and it means you do **not** need to touch browser code in this batch.
- `_read_json` is at `watch.py:8354` (relevant to `E5`, out of batch — do not pre-empt it).

## Verification — the rules that have actually caught things here

- **Red-proof every increment on the line the plan names.** Reinstate/remove that line, watch the named test
  fail, and report it. **A green red-run is a finding, never a relief** — this plan has had **three wrong red
  lines** (`B1`'s pragma was already the compile-time default; `B7`'s `UNIQUE` was not the line carrying
  concurrency; row 15's predicate was `D1`'s). If your prescribed red comes back green, **say so and find which
  layer is actually holding the property up** — do not conclude the code is fine, and do not invent a passing
  red.
- **Assert each check's precondition at runtime.** Derive it; never a literal tuned to today's tree.
- **Beware the fixture that stands in front of the code.** If a test hand-builds what the production function
  decides, reverting that function changes nothing the test can see — that has happened twice here. Name the
  production line you changed to red it, and change *that*.
- Prefer **`test_user_events_http.py`** (new file) per the plan, so lane E's tests do not tangle with
  `test_watch.py`.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`.** Bind nothing in 39880–39899 or 39890–39899. Note `TestCitedShas` can fail under random order
  with `OSError: File too large` when several lanes run `git` at once — that is the known interaction, use
  `-p no:randomly`, and say if you see it.
- Do **not** restart, `pkill` or redeploy the dashboard on **:35110** — he is reading it (pid 1542866, deployed
  01:33). Do not touch the heartbeat, the monitors, or the loop. Never `pkill -f` — build process patterns from
  parts.
- Trailer: a status-code cutover changes what an existing install does. `Migration:` is likely right — decide
  and say why.

## Files

**Yours:** `watch.py` (the HTTP paths only), `test_user_events_http.py` (new), `user_events/*` if a row requires
it, and the plan document **only** to amend a row you proved wrong (with the reason visible, as previous lanes
did).

**Not yours:** `lint.py`, `test_lint.py`, `file-formats.md` (the `subdec` lane holds all three),
`review_artifact.py`, `.dreamwork/review/**` (the `gateart` lane), `transitions.md`, `watch-design.md`,
`justfile`, `dev/capture/*`, `dev/ledger.py`, `SKILL.md`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`,
`.dreamwork/handoffs.md`.

**Note:** lane **G** also lives in `watch.py`, so it is deliberately not dispatched while you hold it. Keep your
diff to the HTTP paths so that stays true.

## Practical

- 2 threads. **One commit per increment**, `git add <newfile>` then
  `git commit --only <paths> -m 'feat(#263): E1 …'` — **`--only`, never `git add -A`**: a lane's staged test was
  once swept into an unrelated ledger commit (`12f47e3`) exactly this way.
- **Commit before you finish**, and **land what is done even if the batch is not** — a lane tonight exited with
  correct work uncommitted, twice.
- **~20 minutes per increment is the shape**; if `E1` alone consumes the batch, land it and report.
- Choosing between rival implementations? Use **IGC** — `igc-method.md` in the repo root: binary goals or
  breakpoints, `✔`/`✘`/`?`, decisive error under each `✘`, no scoring.
- **Push back with reasons** if a plan row is wrong. Three of its red lines were, and each lane that said so was
  right to.

## Report

Say: which model you are; one line per increment with its sha; the red line you changed for each and what
failed; any prescribed red that came back **green** and what you found instead; the trailer you chose; whether
`test_user_events_http.py` is new or you had a reason not to; the successor scope you are leaving (23–25); and
confirmation you built nothing behind purge/PostgreSQL, did not touch :35110, and did not run the full
`just test`.
