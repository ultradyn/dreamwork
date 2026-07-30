# Brief — #274: duplicate Web UI submissions idempotent end to end (+ #341 shared fixture)

**Task:** #274 (P0/P1, bug) — three witnesses of duplicate submissions
reaching durable state: 17:48 two byte-identical answers ~188ms apart;
18:48:53 two byte-identical same-timestamp receipts + duplicate Answer
bullets; 2026-07-28 01:23 his #346 ruling landed as TWO byte-identical
Answer bullets (verified line-by-line) with the `watch-events.log` answer
line twice in the same second — and it stayed invisible for two hours
because nothing counts answer bullets per entry.

**Lane-owns:** `watch.py` — the composer/answer submit JS region
(`postJSON`, the confirmation controller, the cmdform/answer/ask submit
paths, `DraftStore`) and the POST receipt/application region (`do_POST`,
`_journal_receive`, `_handle_answer`/`_handle_command` as far as the
receipt→application join); `user_events/` ONLY if the dedupe itself is
incomplete (verify first — it looks complete); `test_watch.py` +
`test_user_events_sqlite.py`; `dev/capture/` for a guard if you write one.
**NOT** `track_question_updates` / `_sig_text` / `question-sigs.json`
(lane-534sig owns that region IN THE SAME FILE — stay out of it), NOT
`dev/journal_consume.py`.

## What the coordinator verified while briefing (start here, re-verify)

- The SERVER is ready: `_journal_receive` (`watch.py:~14253`) reads
  `X-Client-Action-Id` and mints a per-request UUID when absent;
  `user_events/sqlite.py` has `client_action_id TEXT NOT NULL UNIQUE`
  (:350), a deterministic `receipt_id` from it (:705-711), and a lookup by
  client_action_id (:655).
- The CLIENT never sends the header: `X-Client-Action-Id` appears exactly
  once in watch.py — the server read. No `crypto.randomUUID` anywhere. So
  every browser submit mints a fresh server UUID and every retry or
  double-click is a NEW receipt that reaches application. That is the bug's
  current shape.
- The fix is therefore the client attempt store PLUS the application-side
  join, not new journal machinery.

## Shape

1. **Characterise the application half first.** When `receive()` dedupes
   (same UUID+digest), what does the handler do? The receipt row is
   deduped by construction, but does the SECOND POST still run
   `_handle_answer` and append a second Answer bullet? If the
   receipt→application join has no dedup-hit signal, that is the server
   half of the fix: a dedup hit must short-circuit to the ORIGINAL
   receipt's verdict, never re-apply. Name the exact seam in your report.
2. **Client attempt store.** One UUID per composition attempt: minted when
   a composition begins (first input) or on first submit, persisted with
   the draft (#269's `DraftStore`/`localStorage` — drafts already survive
   restart), sent as `X-Client-Action-Id` on the submit POST, and cleared
   ONLY on durable landed (the same `cv.landed` gate that clears the
   draft — a failed/rejected send keeps BOTH the draft and the UUID, so
   his retry dedupes against the first attempt). In-flight double-click:
   both POSTs carry the same UUID → the journal dedupes the second. Also
   check the confirmation controller's attempt lifecycle — if an in-flight
   guard already exists, say what it covers and what it doesn't.
3. **The #341 shared fixture** (the entry says they are one story):
   replay same-ID → exactly one receipt AND one application; new ID with
   identical text → a distinct intentional action (two receipts, two
   applications — never dedupe across IDs). If `_parse_entries`'s
   `cur["answer"]` overwrite matters once the UI path is closed, say so
   explicitly rather than expanding scope into the parser.
4. **Every submit path or a stated boundary.** Composer `/command`,
   question answers, `/ask`, `/comment`, `/decide` — list which paths get
   the attempt store and which are declared out (with the reason), so the
   gate can check the boundary instead of discovering it.

## Evidence discipline (load-bearing, all recent)

- Red-first pytest for the server half (replay fixture through the REAL
  `receive()` path — never a hand-built fake that bypasses the function
  deciding dedupe; name the production line each test would fail on, then
  change that line and watch it fail; `cp` snapshot/restore, never
  `git checkout`).
- For the client half: if you add a capture guard, it runs SOLO on a free
  3989x port after `just reap`, ordinary-class layout (`$B/target` served,
  `$B/<guard>` OUT). Never `just test`, never another lane's guard (#424).
- A green red-run is a finding, never a relief — three-shape triage in
  `.dreamwork/lessons.md` (search "green red-run"); this exact class has
  three instances this week.
- Transitions: if the double-click prevention has any visible surface
  (e.g. a send button settling), `transitions.md` governs — read it first.
- `git commit --only <paths>` (new files need `git add` first). Never
  `attn`. Never `pkill -f`. Work only in your worktree.

## Report

Coordinator inbox (path in your dispatch prompt) + ONE literal
`## Pending` line in your worktree's `.dreamwork/handoffs.md` (grammar in
the file's header: `- **#274** · landed \`<sha>\` · <date> · by
lane-274idem — <what>`), committed with
`git commit --only .dreamwork/handoffs.md`.

## Done when

Replay of one attempt yields exactly one receipt and one application; a
new attempt with identical text is distinct; the client sends a stable
per-attempt UUID on every covered path; the boundary across submit paths
is stated; every check is red-proved; `test_watch.py` and
`test_user_events_sqlite.py` green; the Pending line is committed.
