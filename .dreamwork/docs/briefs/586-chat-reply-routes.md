# Brief — #586: `/chat-reply` was never registered with the route-registry guards

Lane-owns: `dev/reconcile_submissions.py`, `test_user_events_http.py`, `test_reconcile_submissions.py`, `.dreamwork/handoffs.md` (append ONE `## Pending` line)

Worktree: `/home/xertrov/.llm-general/skills/ud-dreamwork/.worktrees/lane-586routes` (branch `lane-586routes`, from `a2487003`)

## Chain

- **This task:** make `just test` green again by registering `/chat-reply` everywhere a write route must be declared.
- **Session goal:** restore a trustworthy green baseline so later increments are attributable to themselves.
- **DREAMWORK.md goal it serves:** the loop's verification must be able to see what the loop has written — a red baseline nobody can explain makes every later green meaningless.

## What happened

`#577` (the reply composer on `/chat/<id>`) added `/chat-reply` to `watch.WRITE_ROUTE_HANDLERS`. It did not update the two places that must move with a new write route. Three tests are red on clean `master`, and because `just test` runs `pytest lint guards` in that order, **pytest aborts the recipe and the browser guards never run at all** — so the guard suite currently has no baseline either.

This is not a guard that broke. These are the alarms that exist precisely to catch an unregistered route, and they fired correctly. What failed was the merge gate: `#577` landed without a full pytest run.

## The three failures, with their evidence

```
FAILED test_reconcile_submissions.py::test_submission_routes_match_watch
  AssertionError: SUBMISSION_ROUTES drifted from WRITE_ROUTE_HANDLERS
  Extra items in the left set: '/chat-reply'

FAILED test_user_events_http.py::E2Shadow::test_a_new_route_would_fail_this_test_not_slip_past
  AssertionError: 11 != 10 : ('/answer','/ask','/comment','/command','/chat-reply',
                              '/decide','/tint','/run-mode','/posture','/remind','/deploy')

FAILED test_user_events_http.py::E2Shadow::test_every_write_route_commits_a_receipt_and_changes_nothing_else
  AssertionError: 11 != 10 : (same tuple)
```

## What to do

**1. `dev/reconcile_submissions.py` — add `/chat-reply` to `SUBMISSION_ROUTES`.**
The test's own docstring states the stake: without it *"the audit would misclassify the new route's receipts as unknown-route"*. So this is a live defect in the submissions audit today, not just a red test. `test_reconcile_submissions.py::test_submission_routes_match_watch` derives `expected` from `watch.make_handler(...).WRITE_ROUTE_HANDLERS`, so it should go green on this change alone and probably needs no edit — if you find it does need one, say why in your report, because a derived check that needs hand-editing has usually stopped being derived.

**2. `test_user_events_http.py` — give `run_all_routes` a `/chat-reply` payload, then bump both literals from 10 to 11.**

Read the comment above the literal before you touch it. It is deliberate:

> *This literal is a deliberate alarm — do NOT derive it from `WRITE_ROUTE_HANDLERS` (that would be `len(table) == len(table)`, a check born hollow: the repo has a documented lesson about exactly that shape). Bump it consciously when extending `run_all_routes`, and say why here.*

It carries a dated line per bump (`#496: 8→9`, `#551: 9→10`). **Add yours in the same form** — `2026-07-31 #586: 10→11 — /chat-reply (#577) joined the dispatch; <the payload shape you gave it>`. Do not collapse the literal into a derivation, however tempting; that is the exact anti-pattern the comment warns about.

The payload is the real work here, not the number. `test_every_write_route_commits_a_receipt_and_changes_nothing_else` runs every route with the journal ON and OFF and compares everything observable except the receipt count — so a `/chat-reply` payload that 400s, or that writes something the baseline server also writes differently, will fail for a reason that has nothing to do with your change. Look at how `/comment` and `/answer` build their payloads and at `watch.py`'s `/chat-reply` handler to get a body that actually succeeds. Reaching a real chat id may need the harness to create one first; if the existing fixtures do not give you one, say so rather than posting a body you know 404s.

## Verification, and what counts

- **Targeted pytest only:** `python3 -m pytest test_reconcile_submissions.py test_user_events_http.py test_watch.py -q`, plus `python3 /home/xertrov/.claude-p/skills/ud-dreamwork/lint.py --target .`.
- **Do NOT run `just test` or `just guards`.** The coordinator owns both. The guards bind ports 39890-39899 and other work may hold them; a lane running them has left lanes blocked for a quarter of an hour before.
- **Red-proof each fix, one production line at a time.** After green: remove `/chat-reply` from `SUBMISSION_ROUTES` → watch `test_submission_routes_match_watch` fail → restore **by `cp` from a backup you took first, never `git checkout`** (that has destroyed a lane's uncommitted work here before) → confirm the restore is byte-identical with `cmp`. Do the same for the payload: neutralise the `/chat-reply` entry in `run_all_routes` and confirm the receipt-count assertion, not just the length literal, is what catches it.
- **A green red-run is a finding, never a relief.** If an injection leaves the suite passing, stop and report that — it means the check is not measuring what its name claims, and that is more valuable than the fix.

## Lessons that bear on this one

Cited by line so you can read the whole entry: `.dreamwork/lessons.md`.

- **`lessons.md:180`** — *a coordinator's diagnosis is a hypothesis and should be labelled one.* Everything above is mine. Five times in one day here the coordinator named a plausible layer and the dreamer measured a different one. Measure before you accept my account of the cause.
- **`lessons.md:336`** — *a check is only as good as the distance between what it asserts and what it exercises.* Directly relevant: it is easy to make `11 != 10` go away without ever proving a `/chat-reply` receipt is actually committed. The literal is the alarm; the receipt is the behaviour.
- **`lessons.md:953`** — *never re-author a file whose full key set you have not enumerated.* Edit these files surgically. Do not rewrite the test module or the constants block wholesale.
- **`lessons.md:292`** — *a channel nobody reads swallows deliverables.* Your final agent message is not read back. Put everything that matters in the commit, the hand-off line, and the inbox.
- **`lessons.md:157`** — *a guard that reads mutable content is testing the content.* If you find yourself reaching for live `.dreamwork/` state to make a payload work, freeze a fixture instead.

## Delivery obligations

1. **Commit on your branch**, in the worktree, with `git commit --only <paths>` — never a bare `git commit`, other agents hold this tree and a bare commit sweeps their staged files into yours.
2. **Append ONE line to `## Pending`** in the ABSOLUTE main-checkout path `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/handoffs.md`, naming task `#586` and your sha(s) — **and commit it**. Writing it is not committing it; the first lane ever asked for a hand-off appended it and left it unstaged. Note `handoffs.md` has `## Folded` first and `## Pending` second, both append-only.
3. **Report to `/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`**, every line prefixed `[lane-586routes] `, starting with your startup handshake before you work and ending with a `DONE` report naming shas, what you measured, each red-proof injection and its result, and anything you are still uncertain about.
4. **Do NOT use `attn`.** Only the coordinator talks to Max.
5. Do not merge, do not push, do not deploy. The coordinator merges after verifying guards on the merged tree.
