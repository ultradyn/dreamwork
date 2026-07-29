# Brief — lane-504chat: design the composer 'chat' command (#504)

Lane-owns: ONE new design doc `.dreamwork/docs/plans/composer-chat.md`
plus a `doc-map.md` row (same commit). Doc-only: no code, no watch.py, no
SKILL.md, no prototypes.

**Model:** llmp-glm-5-2 · **Isolation:** worktree (coordinator merge-gates).

## His idea (verbatim, add-idea via watch 2026-07-30 03:39)

"add a 'chat' command to the command palette as a default option (far
left). This will send a message to the agent. It should be tracked in the
db, but only just in case at this stage. When the agent calls the command
to get the message (like getting unread at the start of a dreamwork loop
iteration), it should have attached to the chat msg instructions for how
to reply (and that the dreamworker MUST reply via that channel). If an
agent replies to the user's message, it should automatically result in
the creation of a new thread. Any follow up messages to the agent appear
as new thread messages and the agent replies in the thread as one would
expect."

## The reconciliation this design MUST do (the reason it is a lane)

This want is not new — it is the third time he has asked for agent chat,
and the prior two have APPROVED directions that bind this design:

1. **#229/#270 threaded topic chats** — approved "rec, after cli and
   sqlite" (2026-07-28 02:56). BOTH preconditions now exist (sqlite
   cutover landed; `dev/ledger.py` verbs exist). Read
   `.dreamwork/docs/plans/` for the v2 proposal direction (recovery
   spine: client attempt → durable #263 receipt → application →
   transcript; main dreamer first; explicit worker promotion).
2. **#253 contextual annotations** — approved direction: sidecar notes +
   explicit promotion, NOT one chat per mark.
3. **#263 user-event journal** — LANDED. Receipts, cursors,
   `events_since_cursor`, and (in flight as lane-501consume) the
   tick-consume CLI his "unread at the start of a loop iteration" rides.
4. **#342 delivery modes** — LANDED. A `chat` kind's urgency is the
   loop's to gate; plugins may suggest. Where does a chat message sit:
   instant, batched, or pre-empting?

The design question: is his 03:39 idea the MVP of #229 (a thinner first
slice of the approved architecture), or a separate, simpler channel that
#229 later absorbs? DECIDE with an IGC and say why — a design that
ignores #229's approved spine is a dead letter; one that duplicates it is
waste.

## What the doc must settle (or escalate as questions)

- The message path: composer `chat` kind → POST → journal receipt (which
  route? existing `/command` kinds or a new write route — a new route is
  a `watch.py` change and an E2Shadow extension, say so) → tick consume
  → the coordinator reads it with reply instructions attached → reply
  lands where (a `/chat`-reply route? questions.md? a thread store?).
- The thread model: his "agent reply creates a thread; follow-ups append"
  — what is a thread in the store (one table? a receipt field?), and how
  does it square with #229's transcript-first principle.
- The reply-instruction attachment: where do the instructions live so
  every consumer of an unread chat message gets them (his MUST-reply
  rule) without duplicating the text per message.
- DB shape: "tracked in the db, but only just in case" — what minimal
  rows make chats durable and queryable without building #229's whole
  index machinery.
- Delivery/urgency classification under #342's ruling.
- What is deliberately OUT (worker promotion, per-artifact attachment,
  /chat route UI beyond the thread view he described, retention/GC).
- IGC where a genuine fork exists; escalate HIS forks as questions, do
  not pick for him. Likely candidates: chat vs #229 MVP boundary; reply
  channel home; whether `chat` pre-empts under batched delivery.

## Constraints (hard)

- Read `igc-method.md` + `igc-concepts.md`; every IGC is real (goals,
  ideas, grid, decisive criticisms), never prose wearing the label.
- Doc voice follows the sibling plans in `.dreamwork/docs/plans/` — state
  what the doc does NOT authorise, and end with what stays open.
- Small commits, `git commit --only <paths>` (new files `git add` first).
  NEVER `git add -A`.
- Never `attn`, never `pkill -f`, never ports 35110/39880-39899.
- If this brief and the approved directions conflict, PUSH BACK in the
  report.

## Acceptance criteria (measurable)

1. The doc exists, is in doc-map.md, and states its own authority (design
   only, no code).
2. The #229 reconciliation is decided with a real IGC and the decision is
   load-bearing in the design (the message path uses the approved spine
   or the doc says exactly why not).
3. Every "must settle" item above is either settled in the doc or
   enumerated as an open call for him with a rec — no third state.
4. His verbatim requirements are each traceable to a design element (a
   short mapping table is ideal).
5. `git diff master --stat` touches only the two owned files.

## Hand-off obligation (#398)

Final report (the coordinator writes `.dreamwork/handoffs.md` from it):
the #229 reconciliation outcome, the settled shape in five lines, the
open calls for him (with recs), and any pushback.
