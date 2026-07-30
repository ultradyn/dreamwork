# Brief — #504 composer 'chat' command, implementation (his ruling: rec×4)

**Lane-owns:** `watch.py`, `test_watch.py`
**Read, do not edit:** `.dreamwork/docs/plans/composer-chat.md` (the design —
read it IN FULL first), `transitions.md`, `watch-design.md`,
`.dreamwork/questions.md` (the #504 entry, for his exact ruling words),
`dev/capture/` (guard idiom reference only).

## Task

#504 (open in the store, verified 2026-07-30): implement the composer `chat`
command per the design doc `.dreamwork/docs/plans/composer-chat.md`, under his
rulings on Q1–Q4 (all four recs accepted — verify the exact words in the #504
questions.md entry before building):

- **Q1:** the message posts as a **`/command` chat kind** — no new route.
- **Q2:** the UI word is **"topic chat"** (implementation vocabulary stays
  `chat`/`turn`/`reply` — never `thread`, per #229).
- **Q3:** chat is a **batched** kind under #342 — the wake goes through the
  `emits_wake` gate, same as `/answer`/`/comment`.
- **Q4:** the dashboard surface is the **minimal chat list** the design names.

The design's spine (load-bearing, do not re-decide): client attempt → durable
#263 receipt → application → transcript. The receipt machinery EXISTS (E3,
`user_events/`); #274 JUST landed in the composer submit region (merged
`9ce66ff7`) — a chat send is a `/command` POST and MUST ride the new seam:
`postJSON(url, body, attemptId)` with `DraftStore.attemptId(...)` so a
double-click/retry dedupes. Do not author a parallel store, a second inbox,
or a reply channel outside what the design names. His "get unread at loop
start" is the #342 cursor read — already landed (`dev/journal_consume.py
pending`); the reply-instruction attachment rides the chat receipt payload as
the design specifies.

## Hard constraints (the repo's, all measured)

1. **Worktree only.** Edit nothing in the main checkout. Commit in your
   worktree with `git commit --only <paths>` (new files need `git add` first).
2. **Red-first, and prove the red.** Every new check: reintroduce the bug
   (sabotage the production line the check binds — name that line in the
   test's docstring), watch the check FAIL, restore byte-identical with `cp`
   from a scratch snapshot — NEVER `git checkout` (a lane's restore once
   ate its own work). A green red-run is a finding, never a relief: if the
   check passes with the bug in place, the check or the injection is wrong —
   trace it, don't accept it. **If your fix adds a branch that maps N cases,
   the red set names an injection per ARM, not per path** (the #274 gate
   found the ok-path replay bound and the refused-path replay unbound —
   lessons.md, 2026-07-30).
3. **Fixture preconditions are asserted at runtime.** If a check's meaning
   needs two pieces of the fixture to differ, derive both and assert the
   gap — a literal tuned to today's fixture is a check with an expiry date.
4. **Never `just test`, never the guard suite** (ports 39890-39899; the
   coordinator owns both). Targeted `pytest` + `python3 lint.py` only. If
   you add a guard, register it in the justfile and run ONLY your own guard
   solo via `DREAMWORK_GUARDS=<name> DREAMWORK_HUB_GUARDS= just guards
   <port>` after `ss -ltn` shows the range free.
5. **transitions.md is the one rule with no exceptions.** Every appear/
   disappear/expand/state-change on the chat surface reuses the existing
   idiom (the keyed route transition is the reference); reduced-motion
   parity. `watch-design.md` tokens/type/components — no new tokens without
   a same-commit styleguide entry. Load the `frontend-design` and
   `web-artisan-core` skills before designing the surface.
6. **Visual evidence is part of the deliverable.** Screenshots (desktop
   rest, desktop interaction, 390px) captured against the FINAL fixture in
   ONE session (the #525 lesson: a pair captured across fixture edits reads
   as a contradiction). The coordinator views the actual pixels at the gate.
7. **Hand-off:** append ONE line to the main checkout's
   `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/handoffs.md`
   `## Pending` (absolute path — a relative one writes your worktree's copy)
   and COMMIT it among your paths ("write this" is not "commit this").
   Report durable state changed in your final message.
8. No `attn`, no `pkill -f`, no stopping loop machinery. Subagents never
   use `attn`.
9. Note in your report that the model running you is grok-4.5 (the dispatch
   record says so; a lane cannot know its own model — just repeat it).

## Acceptance

- `chat` (the far-left default) in the composer sends a durable message per
  the design + Q1–Q4; the receipt carries the reply instructions; the
  dashboard shows the minimal topic-chat list; a reply creates the chat's
  first agent turn per the design's thread model.
- Tests: new TestWatch/TestJournal tests for the chat kind (receipt shape,
  batched wake gating, payload), each red-proved per §2; full `test_watch.py`
  green; `lint.py` no new findings.
- The batched classification means NO wake line under `delivery: batched`
  (test it like `test_decide_withholds_wake_in_batched` does).
- transitions.md/watch-design.md updated in the same commit as any new
  surface idiom or token (there should be none new — reuse).
