# Composer 'chat' command — the #229 main-dreamer first slice (#504)

**Status: design only. Not authorised for implementation.**

This is the third time agent chat has been asked for, and the prior two
have APPROVED directions that bind this design. This document reconciles
his 03:39 idea (the `chat` composer command) against those directions and
settles what it can, escalating only the forks that are genuinely his.

The one-sentence outcome: **his `chat` command IS the first slice of
#229/#270's approved main-dreamer simple mode — not a separate channel.**
10The design adopts #229's recovery spine verbatim and does not authorise a
parallel chat store, a second durable inbox, or a reply channel outside
the one #229 already names. The IGC below is load-bearing: the message
path, the thread model, and the reply channel all fall out of it.

## Authority and what this builds on

His ask (#504, via watch add-idea 2026-07-30 03:39, verbatim):

> add a 'chat' command to the command palette as a default option (far
> left). This will send a message to the agent. It should be tracked in
> the db, but only just in case at this stage. When the agent calls the
20> command to get the message (like getting unread at the start of a
> dreamwork loop iteration), it should have attached to the chat msg
> instructions for how to reply (and that the dreamworker MUST reply via
> that channel). If an agent replies to the user's message, it should
> automatically result in the creation of a new thread. Any follow up
> messages to the agent appear as new thread messages and the agent
> replies in the thread as one would expect.

Four approved directions bind this design. All four are read in full
before a line below; each is summarised only enough to make the
reconciliation legible.

1. **#229/#270 — threaded topic chats v2** — approved "rec, after cli and
   sqlite" (2026-07-28 02:56); **R1 accepted as proposal direction only.**
   The implementation anchor is **#373**. Both preconditions he named now
   exist (the SQLite ledger cutover, `ledger_store.py` / `dev/ledger.py`,
30   landed as #294; the dreamwork CLI seam he insisted on at 23:24 —
   *"we should use the cli only to interact with topic chats"* — is that
   seam). Its recovery spine is the spine this design rides:
   *client attempt → durable #263 receipt → application → transcript.*
   It starts with the main dreamer (no worker), makes attachments MVP,
   keeps indexes derived, and fixes the vocabulary: implementation names
   use `chat` / `turn` / `run` / `reply` / `worker` — **never `thread`.**
   Source of record: `.dreamwork/review/threaded-topic-chats-v2.html`.

2. **#253 — contextual annotations** — approved direction (2026-07-26
   18:35): a lightweight annotation sidecar whose marks may be promoted
   **once** into a #229 topic chat; **not** one chat per mark. Relevant
   here only as a boundary: chat is not born from an annotation in this
   slice, and #253's promotion target is the same #229 chat this command
   creates.

3. **#263 — user-event journal** — LANDED. The durable receipt is the
40   sole replay authority; `202` means *received*, not *applied*. The
   E3 cutover is in `watch.py`: every write route commits a receipt
   before dispatch. `user_events/apply.py` keeps one `ApplicationAdapter`
   per route (`/answer`, `/ask`, `/comment`, `/command`, `/tint`),
   route-tagged markers, ternary `prove_applied`. **A `chat` kind rides
   this journal; it does not get a second one.**

4. **#342 — delivery modes** — LANDED and RULED (2026-07-30 00:23). The
   `delivery` posture axis (`instant` | `batched`) lives in
   `.dreamwork/posture`; the loop gates a kind's urgency and plugins may
   only suggest it. `Journal.events_since_cursor` + `advance_cursor`
   landed (lanes A+B); the **tick-consume CLI is lane-501consume** (in
   flight, `dev/journal_consume.py pending|consume`). **His "get unread
   at the start of a loop iteration" is that cursor read, by name.**

50The preconditions the #229 approval gated on are met: SQLite ledger
(#294), the CLI seam, the #263 receipt contract, and the #342 cursor
read. The remaining #229 gate — a proved production `WorkerAdapter` — is
**irrelevant to this slice**, because this slice is main-dreamer only and
worker promotion is explicitly OUT (§6).

## 1. The reconciliation — one real IGC, and the decision

The design question the brief sets: *is his 03:39 idea the MVP of #229
(a thinner first slice of the approved architecture), or a separate,
simpler channel that #229 later absorbs?* This is decided here, not
60escalated, because a design that ignores #229's approved spine is a dead
letter and one that duplicates it is waste — and the IGC is the tool for
exactly that judgement.

**Context (the C).** He wants a far-left composer `chat` command that
sends him→agent messages durably, with reply instructions attached, and
threaded follow-ups. #229/#270 (R1 accepted) already approved a full
architecture for durable agent conversation with this exact recovery
spine, main-dreamer-first, transcript storage, and a CLI-only seam he
himself mandated. The journal that spine rides (#263) is landed; the
cursor read his "get unread" names (#342 / lane-501consume) exists. So
the question is whether to reuse that spine or stand up a parallel one.

**Goals (binary — each can refute an idea on its own).**

- **G1 · one recovery authority.** No second durable inbox competes with
  the #263 receipt. (#263's whole purpose; #229 v2's Grok-concern-1,
70  refuted by making the receipt the sole replay authority.)
- **G2 · main dreamer answers in the first slice.** Ships without the
  worker. (His "message the agent"; worker promotion is OUT.)
- **G3 · unread is queryable before any reply.** His "get unread at the
  start of a loop iteration" requires the message to have a durable home
  the moment it is sent, not once the agent answers.
- **G4 · reply-via-channel is enforceable.** His MUST-reply rule needs a
  named channel the agent appends a reply to.
- **G5 · no throwaway store migrated later.** Nothing #229 will build is
  duplicated and then replaced (two truths during the overlap is the
  failure #263 exists to prevent).

**Ideas (rivals — at most one survives).**

- **A — `chat` is #229's main-dreamer first slice.** A `chat` kind posts
  a #263 receipt; a chat application step applies it as a human **turn**
  in a #229 `chats-v1` transcript; the main dreamer replies by appending
80  an agent turn to that transcript via the dreamwork CLI (the CLI-only
  seam). "Thread" = a chat. Reuses the approved spine verbatim.
- **B — a separate simpler chat store.** A dedicated minimal table (or
  file) for chat messages, reply via a fresh `/chat-reply` route; #229
  absorbs it later.
- **C — ride the existing `/command` kinds, reply in `questions.md`.** A
  `chat` is a `/command` steer whose reply lands as a #254 note/reply
  thread on a questions.md entry; #229 later promotes.

**Matrix.**

| Idea | All | G1 | G2 | G3 | G4 | G5 |
|------|:---:|:--:|:--:|:--:|:--:|:--:|
| A. #229 main-dreamer first slice | **✔** | ✔ | ✔ | ✔ | ✔ | ✔ |
| B. separate simpler chat store | ✘ | ✘ | ✔ | ✔ | ✔ | ✘ |
| C. `/command` + `questions.md` reply | ✘ | ✔ | ✔ | ✘ | ✘ | ✘ |

**Why the ✘s (the errors are the reasoning).**

- **B · G1:** a chat-specific durable store is a second inbox competing
  with the receipt as the chat's home — the exact failure #263 abolished
  and #229 v2 named "competing inboxes" to forbid.
- **B · G5:** a separate table/file is parallel to the `chats-v1/`
90  transcript #229 already specified; it is built only to be replaced,
  and during the replacement two structures hold chat truth at once.
- **C · G3:** `questions.md` is the Q&A ledger; #254 threads are a
  *render rule* over its contributions (Note/Answer/Follow-up/Reply
  tags), not a queryable store of free-floating chat messages. A chat
  that is not a question has no entry to hang a thread on, so there is
  no durable home to read as "unread" before a reply.
- **C · G4:** there is no chat-reply channel in `/command` land — a chat
  reply is not a question answer, so replying "via that channel" would
  mean inventing `/chat-reply` anyway, which is idea B.
- **C · G5:** same throwaway-asorbed-by-#229 failure as B.

**Decision.** **A is the sole survivor.** His `chat` command is the
main-dreamer first slice of #229/#270. The message path, thread model,
and reply channel below are #229's, applied to a composer entry point —
not a new channel. This is load-bearing: every "must settle" item in §3
100is resolved *because* the spine is reused, not in spite of it.

The tentativeness the method demands: a new error or a sharper goal could
reopen this, but the refutations on B and C are structural (they
re-introduce the failures #263 and #229 were built to end), not
preference. Holding them tentatively does not license building a
parallel channel "to be safe."

## 2. What "first slice" means — and what it leaves for #373

This slice is **thinner than #229's main-dreamer simple mode**, on
purpose. It is the loop-side path only: the composer entry point, the
receipt, the application to a transcript, the tick-consume read with
reply instructions, and the main-dreamer reply. It deliberately omits
most of the #229 surface so that #373 builds the full thing without
rework:

- **OUT for this slice (§6):** worker promotion, per-artifact attachment,
  the global `/chat` index and dedicated `/chat?p=<id>` dashboard route,
110  the review-route dock, cross-process cap/slots, the queued-follow-up
  `queue_full` contract, retention/GC, and export.
- **IN for this slice:** the composer `chat` kind, the #263 receipt, the
  chat application step that writes a human turn to a `chats-v1`
  transcript, the tick-consume read that surfaces unread chat turns with
  the MUST-reply instruction, and the main-dreamer reply as an agent
  turn appended via the dreamwork CLI.

The slice is shaped so #373 extends it rather than replaces it: the
transcript framing, the CLI-only seam, and the receipt-as-authority are
all #229's, so the only things #373 adds are the surfaces and the
worker. Nothing here is a throwaway.

## 3. The settled shape

Each item the brief named as "must settle" is resolved here, or — where
it is genuinely his fork — carried to §5 with a recommendation. There is
no third state.

### 3.1 The message path (route home is his — §5 Q1)

120The path is the #229 spine, point for point:

```
composer `chat` (far-left default)
  → POST (route: §5 Q1 — `/command` chat kind, rec; or a new `/chat`)
  → #263 durable receipt (E3 cutover commits before dispatch)
  → chat application step: apply receipt as a human TURN in chats-v1
  → tick: dev/journal_consume.py pending reads events in (cursor, head]
  → coordinator surfaces the unread chat turn WITH the reply instruction
  → main dreamer replies: append an agent turn via the dreamwork CLI
  → transcript is conversational truth after application
```

The only open point in the path is the POST route, and it is genuinely
his (§5 Q1). Everything else is determined by the spine. **A new write
route is a `watch.py` change and an `E2Shadow` extension** (the
`submissions.log` shadow append every write route makes) — said plainly,
because the brief asked it to be.

### 3.2 The thread model (reconciled; one residual fork — §5 Q2)

His "agent reply creates a thread; follow-ups append" is #229's chat
model in different words. Vocabulary first: in implementation this is a
**chat**, never a `thread` (#229's domain-language rule, so it does not
collide with OS/model threads or with #254's note/reply tree language).

130The reconciliation has one real tension. He says the *reply* creates the
thread; #229 creates the chat on the first *send* (main-dreamer request,
status `pending`), and the reply is the first agent *turn*. **His own
"get unread at the start of a loop iteration" forces #229's timing:** a
message with no home until the agent replies cannot be read as unread
before that reply — so the chat record must exist from the send. The
shape is therefore:

- first `chat` send → creates the chat (a `chats-v1/<id>` transcript),
  applies the human turn, status `pending`;
- main-dreamer reply → appends the first agent turn (what he perceives
  as "the thread now exists");
- follow-up send → appends a further human turn; reply appends a further
  agent turn. In main-dreamer mode (no active run) follow-ups append
  freely — the #229 `queue_full` one-queued-follow-up rule is a
  *worker-run* concept and does not apply to this slice.

The residual fork (§5 Q2) is cosmetic, not structural: whether he wants
the word "thread" kept in the UI copy ("topic chat" is #229's UI term).

### 3.3 The reply-instruction attachment (settled; implementer default)

His MUST-reply rule needs the instruction to reach every consumer of an
unread chat turn without duplicating the text per message. **Settled:**
the instruction is a property of the **chat kind's consume contract**,
not stored per message. When the coordinator's tick surfaces an unread
`chat`-kind receipt (via `journal_consume pending`), it attaches the
140standard instruction — *"reply via the dreamwork CLI to chat `<id>`;
the dreamworker MUST reply through that channel"* — from the kind's
contract (the same place `/ask` and `/answer` carry their consume
semantics). One text, applied at consume time; no per-turn duplication,
no second storage location. The channel it names is the chat transcript
the dreamwork CLI appends to — which is the CLI-only seam he mandated.

This is an implementer default (overrule by naming the line), not a fork
for him: storing the instruction per-message would be the duplication he
explicitly does not want, and a per-chat stored copy would be a second
source of truth for text that is identical across every chat.

### 3.4 The DB shape ("tracked in the db, but only just in case" — reconciled)

His framing understates the receipt's role, and the reconciliation
pushes back on it (§7). Under #342 + #263 the journal receipt is **not**
belt-and-braces — it is the delivery path: the cursor read is how the
agent gets the message at all. So "tracked in the db" is already true
and load-bearing: the #263 receipt (durable, hash-chained, cursor-read)
is the tracking. On top of it, the minimal #229 rows that make chats
queryable as conversations, without #229's full index/cap machinery:

- the receipt itself (route, body, ordinal) — already exists, no new
  table;
- `chats-v1/<id>/chat.json` — identity, title, revision, mode
  (`main-dreamer`), `created_from_receipt`;
- `chats-v1/<id>/transcript.md` — append-only framed turns
  (#229's `dw-turn` framing; `content_bytes` makes hostile pasted
  markers harmless).

No separate "just-in-case" table is built — that is idea B (refuted on
G1/G5). No projections, no global index, no cap/slots for this slice
(§6). The transcript is conversational truth after application; the
150receipt is the replay authority before it. That pair is the whole DB
shape, and it is the smallest honest subset of #229.

### 3.5 Delivery / urgency under #342 (default proposed; his — §5 Q3)

#342's ruling settles *who* gates urgency (the loop; plugins suggest) and
*where* the toggle lives (the `delivery` posture axis). It does **not**
pre-classify a `chat` kind, because `chat` did not exist when it ruled.
The classification is therefore his (§5 Q3). **Rec: `batched` by
default** — a chat rides the tick's cursor read, which is exactly his
"get unread at the start of a loop iteration," and it joins the
ambiguous class (#342 ruled batched: `/ask`, `/answer`, `/comment`). The
loop remains free to pre-empt a chat it judges urgent, consistent with
#342's "most-urgent kinds pre-empt even in batched mode"; a `chat` is
not auto-instant the way `do-now` is.

## 4. His verbatim requirements → design elements

| his words (verbatim) | design element | settled? |
|---|---|---|
| "a 'chat' command … as a default option (far left)" | a `chat` kind in `COMMANDS` (`watch.py:308`), `common:True`, ordered first; reuses the composer-row conveyor (#164) | shape settled; route is §5 Q1 |
| "send a message to the agent" | human turn applied to a `chats-v1` transcript; main dreamer is the addressee (main-dreamer mode) | settled |
| "tracked in the db, but only just in case" | the #263 receipt (load-bearing delivery path) + `chat.json`/`transcript.md`; **no separate table** (§3.4, §7 pushback) | settled (with pushback) |
| "get the message … like getting unread at the start of a … loop iteration" | `dev/journal_consume.py pending` (lane-501consume) over the coordinator cursor — the #342 batched read | settled |
| "attached … instructions for how to reply" | the chat kind's consume contract attaches the standard reply instruction at surface time; no per-message storage (§3.3) | settled |
| "the dreamworker MUST reply via that channel" | the channel is the chat transcript; reply = agent turn appended via the dreamwork CLI (the CLI-only seam) | settled |
| "an agent replies … automatically result in the creation of a new thread" | chat created on first **send** (pending); agent reply = first agent turn; "thread" = chat in #229 vocab (§3.2) | reconciled; UI word is §5 Q2 |
| "follow up messages … appear as new thread messages" | follow-up send appends a human turn; reply appends an agent turn; no `queue_full` in main-dreamer mode (§3.2) | settled |
| "the agent replies in the thread as one would expect" | main dreamer replies in-chat by appending an agent turn to the same transcript | settled |

## 5. Open calls for him (with recs — never picked for him)

These are the genuine forks. Each is his to rule; a rec is offered, not
applied.

- **Q1 — the POST route home.** Does `chat` post as a new **`/command`
  kind** (rec — reuses the existing route, the E3 receipt seam, and the
  composer-row `COMMANDS` entry; thinnest path matching his "command"
  framing), or as a **new `/chat` write route** (the #229 v2 surface; a
  `watch.py` change plus an `E2Shadow` `submissions.log` extension)?
  Rec: **`/command` chat kind** for this slice; reserve the dedicated
  `/chat` route for #373's full surface. Either way the #263 receipt
  commits first and a chat application step applies the turn.
- **Q2 — "thread" in the UI copy.** Implementation never uses `thread`
  (#229 vocabulary rule). Does the **UI** say "topic chat" (#229's term,
  rec — consistent across this slice and #373), or keep his word
  "thread" in the human-facing label only? Structural behaviour is
  identical either way.
- **Q3 — `chat` delivery default under #342.** **Batched** (rec — rides
  the tick cursor read, his "get unread at iteration start"; joins the
  ambiguous class #342 ruled batched) or **instant** (pre-empts like
  `do-now`)? The loop gates urgency either way; this only sets the
  default.
- **Q4 — does this slice ship a visible thread/chat surface at all?**
  His idea describes send + reply + follow-up, not a page. Does the MVP
  surface unread and replied chats somewhere existing (rec — the
  dashboard already renders channels; a minimal chat list reuses it,
  deferring #373's global `/chat` index and dedicated route), or is
  even that deferred to #373 with only the loop-side path landing now?
  This sets how much UI lands in the slice.

## 6. What this design does NOT authorise

Matched to house style (`threaded-notes-spec.md`, `delivery-modes.md`):
#504 was filed as a DESIGN task and this doc is the deliverable. It
authorises **no code.** Specifically, and additionally, it keeps OUT of
this slice (so #373 builds them once):

- **any `watch.py` change** — not a `chat` kind in `COMMANDS`, not a
  `/chat` route, not the per-kind consume contract wiring.
- **any `user_events/` change** — not a chat `ApplicationAdapter`, not a
  new route in the registry (`apply.py:418`).
- **any `chats-v1/` storage** — not `chat.json`, not `transcript.md`
  framing, not the CLI-only `AGENTS.md` + symlinked `CLAUDE.md` in the
  storage dir he mandated at 23:24.
- **worker promotion** — OUT of this slice and OUT of #229's first mode;
  gated on a proved `WorkerAdapter` this design does not touch.
- **per-artifact attachment** — his idea is free-floating chat; #253's
  one-time promotion and #229's MVP attachment are later.
- **the `/chat` index, dedicated route, review dock, mobile tabs** —
  #229 v2 surface; deferred to #373.
- **cross-process cap/slots and the `queue_full` contract** —
  worker-run concepts; this slice is single main-dreamer.
- **retention / GC / export** — deferred to #373's operation phase.
- **no migration, no deployment, no change to a running loop or target.**

A design gets read as a licence. It is not one. The open calls above are
what the next gate has to decide; the implementation anchor remains
**#373**, carrying the accepted #229 direction, and this slice's settled
shape is input to it.

## 7. Pushback

One item pushes back on his framing, none on the approved directions
(this brief and #229/#253/#263/#342 are consistent — the reconciliation
found no conflict, only his wording understating a mechanism).

- **"tracked in the db, but only just in case" understates the receipt.**
  Under #342's ruling the journal receipt is the *delivery path*, not a
  belt-and-braces backup: in batched mode the cursor read is how the
  agent gets the message at all, and the wake line is an optimisation.
  Treating it as optional would re-create the "lost if the monitor is
  off" failure #263 was built to end (`SKILL.md:117`). The design honours
  his *spirit* (minimal tracking, no full index machinery this slice) by
  using only the receipt + transcript — but the receipt is load-bearing,
  and that is stated rather than hidden behind "just in case."

No conflict with the approved directions was found. If he reads one, it
is almost certainly Q1 (route home) or Q3 (delivery default) — both are
his to rule in §5, and neither contradicts #229 or #342.

---

--- SUMMARY ---

- **What.** The #504 design: a far-left `chat` composer command. **Design
  only; authorises no code.** Reconciles his third ask for agent chat
  against the four approved directions that bind it.

- **Reconciliation (decided, load-bearing).** A real IGC (A/B/C × G1–G5)
  decides his `chat` command **IS the main-dreamer first slice of
  #229/#270** — not a separate channel. A (reuse the #229 spine) is the
  sole survivor; B (separate store) is refuted on G1+G5 (second inbox /
  throwaway); C (`/command` + `questions.md` reply) on G3+G4+G5 (no
  queryable home / no reply channel). The message path, thread model,
  and reply channel all follow from reusing the spine.

- **Settled shape (five lines).** (1) `chat` kind → #263 receipt → chat
  application writes a human turn to a #229 `chats-v1` transcript; (2)
  the tick's `journal_consume pending` (lane-501consume) surfaces unread
  chat turns with the MUST-reply instruction attached from the kind's
  consume contract — no per-message storage; (3) the main dreamer replies
  by appending an agent turn via the dreamwork CLI (the CLI-only seam he
  mandated); (4) "thread" = a chat in #229 vocab, created on first send
  (his own unread-requirement forces send-not-reply timing), follow-ups
  append freely in main-dreamer mode; (5) DB shape is the receipt +
  `chat.json`/`transcript.md` only — no separate "just-in-case" table.

- **Open calls for him (recs, not picks).** Q1 route home (rec `/command`
  kind, reserve `/chat` for #373); Q2 UI word "thread" vs "topic chat"
  (rec topic chat); Q3 delivery default under #342 (rec batched); Q4
  whether this slice ships any visible chat surface (rec minimal list
  reusing the dashboard, defer #373's `/chat` index).

- **Pushback.** His "just in case" understates the receipt — under #342
  it is the delivery path, not a backup; the design honours his spirit
  (minimal tracking) while stating the receipt is load-bearing. No
  conflict with the approved directions was found.

- **No code, no watch.py, no user_events, no chats-v1 storage, no
  migration is authorised.** The implementation anchor stays #373; this
  slice's settled shape is input to it.
