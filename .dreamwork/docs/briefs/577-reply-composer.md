# Lane brief: #577 — reply composer on /chat/<id>

## Lane-owns

- `watch.py` — new `_handle_chat_reply` handler + registration in `WRITE_ROUTE_HANDLERS`
- `client/views.js` — `buildChat()` gains a reply composer below the transcript
- `client/command.js` — extract shared composer primitives IF needed (DraftStore, postJSON, confirmation lifecycle) — prefer import/reuse over duplication
- `test_watch.py` — born-red tests for the new route
- `.dreamwork/handoffs.md` — your Pending line (see #398 obligation below)

## Context

The `/chat/<id>` page renders read-only turns (transcript of a topic chat). Max wants to reply from the page itself: "this page needs a way to reply. reuse and extend our existing component(s)."

**Current architecture** (post-#397 refactor — client JS is in `client/*.js`, not `watch.py`):

- A chat send creates a NEW chat: POST `/command` `{kind: "chat", text}` → `_handle_command` calls `apply_chat_turn(target, cid, "human", text)` where `cid` = the journal receipt id. Each send is a new chat identity.
- The ONLY reply path is CLI: `bin/ud-dw-chat reply <chat-id>` imports `watch.apply_chat_turn` directly.
- `apply_chat_turn(target, chat_id, role, text, at=None, receipt_id=None)` is the ONE writer (watch.py:2512). It appends a framed turn to `.dreamwork/chats-v1/<id>/transcript.md`. Anti-forgery: `one_line`s the body, role-tested.
- The reply route does NOT exist in the UI. This lane creates it.

## What to build

**Server** (`watch.py`):

1. New handler `_handle_chat_reply`: reads JSON `{id, text}`, validates the chat id against `_CHAT_ID` regex (watch.py:2467), validates the chat EXISTS (the production reader `_parse_chat_turns` or `list_chats`), then calls `apply_chat_turn(target, id, "human", text)`. The existence guard runs BEFORE apply so a typo'd id is a loud refusal, never a forked chat (same discipline as `bin/ud-dw-chat`). Returns `{"ok": true}`.
2. Register `"/chat-reply": _handle_chat_reply` in `WRITE_ROUTE_HANDLERS` (the `WRITE_ROUTE_HANDLERS` dict at ~line 5240). This gets E2Shadow receipt + #274 idempotency for free.
3. The handler follows the same pattern as `_handle_command` for the chat branch: best-effort write (receipt committed first), `emits_wake` decision (a chat reply should wake the same way a chat send does — check `emits_wake` for the route).

**Client** (`client/views.js` + `client/command.js`):

1. `buildChat()` in `client/views.js`: after the transcript turns, render a reply composer. Reuse the EXISTING composer components from `client/command.js`:
   - `postJSON(url, body)` for the POST
   - `DraftStore` for draft persistence (use a chat-specific draft key like `DraftStore.id('chat', fetched.id)`)
   - The `#255` confirmation lifecycle (success → atmospheric arrival → ~5s → atmospheric departure)
   - The existing `esc()` for text safety
2. The composer is a textarea + submit (Ctrl+Enter or button), styled to match the existing composer's `.askform` idiom. It POSTs to `/chat-reply` with `{id: <chat id>, text: <textarea value>}`.
3. On success: confirmation lifecycle (the `#255` shared 5s design), clear the draft, and the next `/mtime` tick re-fetches `/chatdata` and the new turn appears in the transcript.
4. On the unknown-id degrade path (`buildChat` receives `null`): no composer — you can't reply to a chat that doesn't exist.

**Tests** (`test_watch.py`):

Born-red through the real handler:
- A reply to an existing chat appends one human turn (turn count N → N+1)
- A reply to a non-existent chat id is refused (not a forked chat)
- A reply with empty text is refused
- The draft persistence uses a chat-specific key (not the main composer's)

## Constraints

- `transitions.md` governs every appearance/disappearance/motion. Read it first. The composer's arrival/departure is a route-element gesture (it arrives with the page, departs on navigate). The confirmation lifecycle IS the #255 motion — reuse it, do not invent a second one.
- `watch-design.md` is the styleguide — single-source. If you add a new component shape, document it there in the same commit.
- Red-first: each test must FAIL against the unimplemented feature, then PASS once built. Red-proof each production line: cp-backup → sabotage → targeted FAIL → cp-restore byte-identical (`cmp`, never `git checkout`). A green red-run is a finding, never a relief.
- `git commit --only <paths>` (new files need `git add` first).
- Never `just test` (full suite); solo guard runs only after `ss -ltn` shows 39890-39899 free.
- No `attn`, no `pkill -f`.
- The server-side writer is `apply_chat_turn` — the ONE writer. Never re-implement it. The route calls it; the UI calls the route.
- #274 idempotency: the `WRITE_ROUTE_HANDLERS` registration gives you E2Shadow receipt + replay verdict for free. A double-click/retry must not double-write.

## #398 hand-off obligation

This brief mentions `.dreamwork/handoffs.md`. When your work lands, append ONE line under `## Pending`:
```
- **#577** · landed `<sha>` · 2026-07-31 · by lane-577reply — <one-line what>
```
The grammar requires `· landed \`<sha>\` · <date> · by <claimer>`.

## What NOT to touch

- `apply_chat_turn` itself — it's the shared writer; this lane calls it, not modifies it
- `bin/ud-dw-chat` — the CLI reply path is unchanged
- `client/router.js` routing — the `/chat/<id>` route already exists; this adds a composer TO the view, not a new route
- `lint.py`, `file-formats.md` — no new parsed file shape (the route is a handler, not a file)
