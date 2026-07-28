# Brief — #263 `E5b`: no write surface may confirm a rejected receipt

Repo: `ud-dreamwork`. Worktree: **`.worktrees/laneE5b`**, branch **`wt/laneE5b`**, **branched from `wt/laneE2`
so `E4` and `E5` are already present** (`git log -1` should show `a67f308`). Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[laneE5b]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/laneE5b-inbox.md` so I can steer you mid-task.

Report a line per milestone (**sites enumerated**, **fix in**, **red-proved in a browser**, **committed**).
Full report goes **once** to `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which
model you are** at the top. **Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or
`.dreamwork/questions.md` — report the lines you want added.

## The defect, measured — you are fixing his text, not a status code

`E5` is correct against its plan row and it is **not** being reverted. It converted body-validation failures
from a synchronous `400` into `202` + a durable `rejected` transition with a bounded reason. The response body
says so: `{"ok": false, "rejected": true, "reason": "schema_invalid"}`.

But **`202` makes `res.ok` true**, and every browser-side check is `res.ok` — 9 sites. That is why `#263`'s Q3
could rule `200 → 202` a non-event, and that reasoning holds for a *successful* write and fails for a rejected
one.

**Measured against a lane server whose pid was asserted:** `POST /ask {"nope": …}` → `202 {"ok": false,
"rejected": true, "reason": "schema_invalid"}`. And at **`watch.py:3109`**:

```js
if (res && res.ok) { liveBox.value = ''; if (liveMsg) liveMsg.textContent = 'asked'; }
```

So the box empties and the page says **asked** for a question that was durably **rejected**. The same shape is
at **`:3526`** (answers) and **`:3570`** (notes), where `dwDraft.clear()` follows — and there the loss is
permanent, because the draft was the only remaining copy of what he typed.

This is not a style preference. `:3527`'s own comment says *"confirming a write that did not happen is the one
thing worse than the 409 itself"* (`#136`), and `#269` exists so his words survive. Read both before you start.

## What to build

**One rule, one idiom: a write surface treats a rejected receipt exactly as it treats a failure — his words are
kept, and the confirmation does not run.**

- **Enumerate the sites from the code, not from this brief.** I found `2412`, `3109`, `3526`, `3570`, `3962`,
  `4203`, `4614`; line numbers move and `4614` is a *read* (`/filedata`), so derive the real set: the POST
  paths whose response decides whether to clear a box, clear a draft, or show a confirmation. **Report the set
  you derived and any site you judged out of scope, with the reason.**
- **One shared helper, not seven inline checks.** A per-site `&& !j.rejected` is the shape that goes stale the
  day someone adds an eighth site. Put the verdict in one place — the same argument `report.mjs` and
  `serve.mjs` were built on. Note the constraint: a `Response` body can be read **once**, so a helper that
  parses it must be the single reader, and sites that already parse the body must go through the same path.
- **Keep the reason visible where the surface already has a message element** (`askmsg`, `qaFail`'s target).
  A rejected write should say *why* in his voice, not print a reason code. `watch-design.md` owns the voice;
  read it, and document any new copy in the same commit (`just audit-styleguide` measures that).
- **Do not change `E5`'s server contract.** `202` + durable `rejected` is his approved design. You are teaching
  the client to read what the server already says.
- **`shadow_failed` is NOT yours.** That is `E6`, still out of scope. Rejection only.

## Verification — the part that decides whether this is real

- **A browser check, not an HTTP check.** The defect is that the *page* confirms. An HTTP assertion that the
  body carries `rejected: true` would pass with the bug fully present, which makes it worse than no check.
  Drive a real submit with a rejected body and assert **his text is still in the box** and the confirmation did
  **not** run. `dev/capture/draft.mjs` and `reviewdraft.mjs` are the closest idioms; `health.mjs` already has
  *"...and never shows the answered state for a write that did not land"* and *"keeps his text, which is now
  the only copy of it"* — those checks pass today against a `409`, and **the interesting question is whether
  they pass against a rejected `202`.** Run them first, before your fix, and report what they do. If they stay
  green with the bug present, say so loudly: that is a finding about those checks, and it belongs in
  `.dreamwork/lessons.md`.
- **Red-proof on the production line.** Name the line whose change reds your new check, change *that*, and
  watch it fail. **A green red-run is a finding, never a relief.**
- **Use `dev/capture/serve.mjs`** (`serveVerified` / `serveAllVerified`, landed tonight as `#461`) rather than
  spawn-and-sleep. Two orphaned servers made a correct change read as broken twice tonight, and `watch.py` has
  **no `--no-open` flag** — passing one kills your server on an argparse error and your request reaches a
  stranger.
- Register any new guard in `justfile`'s `DEFAULT_GUARDS` or it gates nothing.
- **Motion:** if anything appears or departs (a reason line arriving), `transitions.md` governs it, with no
  size floor, and it is checked by **sampling**, not end state. Reduced-motion parity included.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`.** Bind nothing in 39880–39889; kill everything you start by exact pid and check `ss -ltnp`
  before you finish.
- Do **not** restart, `pkill` or redeploy the dashboard on **:35110** (he is reading it). Do not touch the
  heartbeat, the monitors, or the loop. Never `pkill -f`.
- Trailer: `Migration:` is plausible (an install's write surfaces change behaviour); decide and say why.

## Files

**Yours:** `watch.py` (the client-side write paths), `test_watch.py`, your new `dev/capture/*.mjs`,
`justfile`'s `DEFAULT_GUARDS`, `watch-design.md` for any copy you add.

**Not yours:** `user_events/*` and `test_user_events_http.py` (`E5`'s server half is settled — do not
renegotiate it), `lint.py`, `file-formats.md`, `migration_notice.py`, `review_artifact.py`,
`.dreamwork/review/**`, `dev/capture/serve.mjs` and `report.mjs` (use them, do not edit them), `SKILL.md`,
`DREAMWORK.md`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/handoffs.md`.

**Note:** the `updrel` lane also holds `watch.py` in its own worktree, on the staleness row near `:2731`/`:2736`.
Keep your diff to the write paths so the merge stays mechanical, and say which regions you touched.

## Practical

- 2 threads. `git commit --only <paths> -m 'fix(#263): E5b …'` — **`--only`, never `git add -A`**.
- **Commit before you finish.** **~20 minutes.** If the shared-helper refactor turns out to be the whole
  budget, land it plus one real browser proof on the `/ask` path — that is the site measured to fail — and
  report the rest with the exact site list.
- **`#263`'s merge is blocked on you.** `E4` and `E5` are correct and sitting unmerged because of this; that is
  the priority order, not a reason to rush the proof.
- **Push back with reasons.** If you find the honest fix is server-side after all — that some surfaces cannot
  distinguish rejection without a status change, and Q3's non-event ruling needs revisiting — argue it. That
  would be a finding for him, and I will file it rather than have you build around it.

## Report

Say: which model you are; the site set you derived and anything you judged out of scope; **what `health.mjs`'s
existing "never shows the answered state" and "keeps his text" checks did against a rejected `202` before your
fix**; the shared helper and how it handles the read-once body; the browser proof and the production line whose
change reds it; the copy you added and where it is documented; which regions of `watch.py` you touched; the
trailer you chose; and confirmation you changed no server contract, did not touch `shadow_failed`, left nothing
listening, did not touch :35110, and did not run the full `just test`.
