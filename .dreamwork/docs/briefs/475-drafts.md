# Brief — #475 · the two draft-store guards

Repo: `ud-dreamwork`. Worktree: **`.worktrees/drafts`**, branch **`wt/drafts`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: dev/capture/draft.mjs, dev/capture/rejectwrite.mjs

## Your two, and why they are the pair worth doing first

```
draft       | typing writes a draft for THIS project (keyed by the target path)
rejectwrite | ...and does not clear the draft store (the permanent-loss vector)
rejectwrite | ...and does not clear the draft store
```

Both are about the **draft store**, and **DraftStore landed tonight** as `#269`/`#459` (merged `ca799f5`). It
introduced a logical id `kind:scopeKey` inside a `data.target` partition, keyed on the question **title**, with
a dual-read of the older `dw:adraft` / `dw:draft` keys, and `isDurable(res)` preferring `_dwv.landed` and
falling back to `res.ok`. Consumers are `ask:main` (`#askbox`) and `popout:main` (`#ptext`).

**So there are two possibilities and they deserve OPPOSITE reactions:**

1. Both guards assert the **pre-DraftStore key shape** — in which case they are the fifth and sixth checks
   tonight to outlive their contract, and the fix is in the guards.
2. `rejectwrite`'s wording is **literal**: a rejected write really does clear the draft store, and a draft he
   typed is really lost. That is a **data-loss defect on his own words**, it is the highest-severity thing in
   `#475`, and it is P0 the moment you can show it.

**Decide which by measurement, and report the answer before you fix anything** — a one-line message to the
coord inbox the moment you know, because if it is (2) I need to know immediately and will re-prioritise the
whole batch. `read` the store in the browser and say what keys exist, under what partition, before and after a
refused write.

**Relevant contract:** a rejected write is **`202` with `rejected` in the body** (`#263` E5), not `4xx`. A
guard checking status alone cannot tell a rejection from an acceptance, and `#474` found exactly that bug in
`identity`. Check whether either of yours does the same.

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[drafts]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/drafts-inbox.md` so I can steer you mid-task.

Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not state a model name for
yourself** — the harness exports only `CCC_PROVIDER`, so you cannot know it; write the caveat instead.
**Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` — report the
lines you want added. **Commit each increment as it lands.**

## The situation, and the one thing that makes this task different

Read **`#475`** in `.dreamwork/tasks.md` in full before anything else. The short version: the first full
`just test` to complete in this session came back **48 PASS / 14 FAIL of 60**, and after re-running the
fourteen alone at load 24–31 **ten still fail exactly as they did at load 36–44**. So the load explanation is
**refuted**, not merely unproven, and you must not reach for it again.

Two systemic explanations were tested and refuted; **do not re-test them**:

1. **Writes are not broken.** A direct `POST /posture` against a fixture server returns
   `202 {{"ok": true, "changed": true}}` with a receipt, writes `.dreamwork/posture`, and appends its
   `watch-events.log` line.
2. **Headless Chromium is not reporting `prefers-reduced-motion: reduce`** (which would collapse every
   normal-motion assertion at once). It reports `false`, and a control transition sampled 20 distinct
   intermediate widths.

**The likeliest cause, stated as a hypothesis and not a conclusion:** tonight landed many merges, and four
checks have already been found asserting a contract that a later change had replaced —
`docktarget`/`noteprop`/`qacard` (`#474`) and `artifactwrap`/`markrail` (`43036f2`, where `#436`'s ask gate and
`#455`'s if-silent gate locked two guard fixtures out of `review_artifact.py`). So for each of your guards the
first question is **which is wrong, the guard or the page** — and the answer may differ per guard. Do not
assume either way, and do not assume they share a cause.

## What you may change, and what you must not

**You own only your guards' `.mjs` files** (listed above). **`watch.py` is NOT yours** — it is the one file
every one of these guards touches, so if it were shared the lanes would collide. If your diagnosis says the
defect is in `watch.py`:

- **Do not edit it.** Report the **exact diff** you want, the line it changes, and what it fixes.
- Say plainly that the page is wrong and the guard is right. That is a completely acceptable outcome and often
  the better one.

If the fix is in your guard — because it asserts a contract the design has since replaced — **land it**, and in
the comment name the commit or task that replaced the contract, the way `#474`'s fixes do.

## Verification

- **Red-proof every check you touch on the production line.** Name the line whose change reds it, change
  *that*, and watch it fail. **A green red-run is a finding, never a relief** — and if a red comes back green,
  **suspect your injection before the test**: confirm you edited the line the check names.
- **Assert the precondition the check depends on, derived at runtime.** A literal tuned to today's fixture is a
  check with an expiry date nobody can see; this repo has paid for that four times.
- **Own-server guards take `await freePort()` and IGNORE `argv[3]`.** `#461` did the opposite and silently
  stopped eight guards executing for three and a half hours (`#471`).
- **Do not register anything in `justfile`** — guard registration is centralised at merge. Report the name.
- `python3 lint.py --target .` clean; run your guards with an explicit port, e.g.
  `DREAMWORK_GUARDS="..." DREAMWORK_HUB_GUARDS= just guards 39891`. **Do not run the full `just test`** —
  other lanes share this machine.
- Bind nothing outside the port you are given; kill what you start by exact pid; `ss -ltnp` before finishing.
- **Do not restart, `pkill` or redeploy the dashboard on :35110**, the heartbeat, the monitors or the loop.
  Never `pkill -f`. **Never use `attn`** — the coordinator is the only party that notifies the human.
- Trailer: `fix:`.

## Files

**Yours:** the `.mjs` files in `Lane-owns:` above, and nothing else.

**Not yours:** `watch.py`, `test_watch.py`, `watch-design.md`, `transitions.md`, `justfile`, `lint.py`,
`test_lint.py`, `file-formats.md`, `dev/lane_guard.py`, `dev/capture/dom.mjs`, `dev/capture/serve.mjs` and
`report.mjs` (**read** them — the shared readers and the reporter contract live there — but do not edit),
every other `dev/capture/*.mjs`, `ledger_store.py`, `review_artifact.py`, `dreamhub.py`, `user_events/*`,
`bin/ud-dw-generate` (**never** touch it), `SKILL.md`, `DREAMWORK.md`, everything under `.dreamwork/`.

If you believe a shared file (`dom.mjs`, `report.mjs`) is the real defect, **that is a valuable finding** —
report it with the diff; several guards would share the cause and I would rather know than have one lane patch
around it.

## Practical

- 2 threads. **One commit per increment**, `git add <newfiles>` then `git commit --only <paths>` —
  **`--only`, never `git add -A`**.
- **Work only inside `.worktrees/drafts`.** Verify cwd and branch before every write.
- ~35 minutes. **Commit before you finish.** If you run out of time, a committed diagnosis of every guard beats
  one fix and three unexamined.
- **Push back with reasons.** "The page is wrong and here is the diff" is the best outcome for any of these.

## Report

For **each** guard, say: which is wrong — guard or page; the measurement that decided it; if the guard, the
change you landed and the contract-replacing commit you named in the comment; if the page, the **exact
`watch.py` diff** you want and the line it changes; the production line whose change reds each check you
touched, with confirmation the injection reached it; and the runtime-derived preconditions. Then: whether any
two of your guards share a cause; whether a shared file is implicated; and confirmation you worked only in
`.worktrees/drafts` (state cwd and branch), edited no `watch.py` and no `justfile`, left nothing listening,
never touched :35110, and did not run the full `just test`.
