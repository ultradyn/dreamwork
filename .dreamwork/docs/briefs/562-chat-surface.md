# Brief #562 — the topic-chat list gains an unread count, and each chat earns a page you can open

Origin: human (his 00:03 do-next, receipt b949814f). Filed P1, bug.

## Lane-owns

- `watch.py`, **chat region only**: `chatRow`/`chatList` (~4020-4040), the
  `list_chats` derivation (~12457-12480), the `"chats"` key assembly in
  `collect()` (~13397-13403), and the router where the new `/chat/<id>`
  route lands.
- NEW `dev/capture/chatsurface.mjs` — the solo guard (rendered structure
  changes; a new route exists where none did).
- Chat tests: extend the existing #504 chat tests, or add ONE focused new
  test file if the existing home doesn't fit.

**Explicitly not yours:** the burndown region (lane-559 in flight), the
status section / `statusBlock` / the `"status"` key in `collect()`
(lane-560 pending merge), the reviews panel, `transitions.md`,
`watch-design.md`, `file-formats.md`, `lint.py`, the justfile,
`questions.md`, the ledger. FLAG any wording a coordinator-owned file
needs in your report; do not edit them.

## The defect (mapped, with anchors)

1. **The count line is total-only.** `chatList` (watch.py:4037-4040 @ 8b3c10cc)
   renders `topic chats · ${d.chats.length}`. His question: "is that
   unread or total?" — it is total, and it doesn't say so.
2. **A chat cannot be opened.** `chatRow` (watch.py:4026-4036 @ 8b3c10cc) emits an
   inert `<div class="dim" data-chat="…" data-status="…">`. **No handler
   anywhere reads `data-chat`** (grep finds the attribute set at :4033 and
   read nowhere), and **no `/chat` route exists** (grep finds none). The
   rows look like rows and do nothing. His words: "the actual issue is
   that I can't open the chat!"

## The two acts

### Act 1 — the count line tells the truth

`topic chats · X unread · Y total` — the unread clause **only when
unread > 0**; the total always labeled `Y total`.

**Unread, defined:** a chat is unread when the **last turn of its
transcript is his** (a human turn with no agent turn after it). This is
derived at read time from the transcript — the same place `status`
(pending/replied) already comes from. `chat.json` stays identity-only
(#504 contract: title/count/status derived at read time); do not add
state to it. Note the relationship: `pending` (no agent turn yet) is a
subset of unread — a chat he followed up on after a reply is `replied`
AND unread. Derive both from the parsed turns; do not invent a second
definition.

### Act 2 — each chat earns a URL

A per-chat page at `/chat/<id>` rendering the conversation: the dw-turn
frames of `transcript.md` read as turns (his / the dreamer's), newest
last, the chat's derived title as the heading. watch-design.md's
navigate principle is the warrant — a chat is its own subject, the same
way the full reviews list earned `/reviews`. Each row in the list links
to its page. Quiet 404-style degrade for an unknown id, in the page's
own voice — never a traceback, never a thrown exception.

**Out of scope — flag, don't build:** a reply composer on the page.
Replies today go through `bin/ud-dw-chat reply` (CLI) and ingestion rides
the journal's `/command chat` application step; a web reply box is a new
ingestion path, not a rendering one. If you judge it small, say so in
the report as a follow-up candidate — do not implement it here.

## Contracts to read first (not optional)

- `transitions.md` — the route change IS the reference implementation;
  arriving at `/chat/<id>` is that gesture. Any element that appears,
  disappears, expands, or changes state on either page obeys it. The
  count line's text changing on a tick is the already-documented settled
  re-render idiom (see the comment at watch.py:4020-4027 @ 8b3c10cc) — reuse it,
  author nothing new.
- `watch-design.md` — tokens, type, the dim-row + `.age` idiom the list
  already uses, copy voice, the per-surface contracts. The chat page is
  a new surface; it speaks the dashboard's language value for value.
- The #504 chat machinery: `CHAT_DIR`, `_parse_chat_turns`,
  `append_chat_turn`, `list_chats` (watch.py:12357-12480).

## Verification (the repo's discipline, all of it)

- **Born-red:** write the failing tests first (through the real writers —
  `append_chat_turn` / real transcript files, never hand-built fixture
  text the parser never saw). Implement. Green.
- **Assert the precondition the check depends on, at runtime.** If a
  test needs "replied but unread" vs "replied and read" to differ, build
  both at runtime from real turns and assert the gap — no literal tuned
  to today's fixture.
- **Red-proof:** name the production line each test binds (e.g. the
  unread-derivation line, the route's dispatch), back up with `cp`,
  sabotage it, watch the discriminating tests fail — **a green red-run
  is a finding, never a relief** — then `cp`-restore and prove
  byte-identical with `cmp`. **Run every sabotage/restore inside your
  own worktree** — verify `pwd` first. (A prior lane ran its red-proof
  against the main checkout's file; that evidence had to be re-derived
  at the gate. Don't be that lane.)
- **Solo guard:** `DREAMWORK_GUARDS=chatsurface just guards 39892` —
  port 39892 is yours (39890 is lane-559's, 39891 lane-560's). Assert
  the row is a link to `/chat/<id>`, the count line's unread/total
  shape, and the chat page rendering a real transcript. Reduced-motion
  parity per transitions.md.
- Never touch port 35110 (deploy is the coordinator's, via `just
  deploy`). Never `pkill -f`. Never `attn`.
- Do not run the full coordinator suite / full guard sweep — your test
  file(s) + your solo guard.

## Handoff (#398)

End with `## Pending` handoff lines in the literal path
`.dreamwork/handoffs.md`: task id, bare shas (no parentheticals), no
model claims (#469). Commit with `git commit --only <paths>`; `git add`
any new file first. Your report lists: commits (bare shas), born-red and
red-proof evidence with the named production lines, the unread
definition as implemented, the page's shape, any FLAGs for
coordinator-owned files, and found-not-fixed items.
