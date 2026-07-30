# Brief — #504 remainder: the chat reply path (CLI verb + consume-side instructions + chats-v1 formalisation)

Task: **#504** (P2, open — verified in the store; the first slice landed
as merge `62ca184f` with its declared boundary: this lane is the
remainder). Read the landed slice first — `git show d56a3c2a` (the
chats-v1 transcript, `apply_chat_turn`, `list_chats`, the composer `chat`
kind) and `git show 5cea6e0f` (the line-start turn-marker anchors —
**the forgery rules are load-bearing for anything you write that appends
a turn**).

Lane-owns: `dev/journal_consume.py`, `bin/` (new tool file only), `file-formats.md`, `lint.py`, `test_lint.py`, `dev/ledger.py` (only if the reply verb rides it — see act 1)

`watch.py` is **read-only** for you (lane-505p2 owns it for writes).
`SKILL.md` is coordinator-owned — flag, don't edit.

## The three acts

1. **The reply verb — the dreamer answers a chat.** The main dreamer
   must be able to append an AGENT turn to a chat transcript from the
   command line. Choose the home: a new `bin/ud-dw-chat` (verbs like
   `list` / `reply <chat-id> <text>` / `show <chat-id>`), or a `chat`
   verb on an existing CLI — read `dev/ledger.py` and `bin/` and pick
   the one that matches the repo's CLI idiom (thin verb → a library
   function; the writer must go through `watch.apply_chat_turn` so the
   one-line + anchored-marker rules CANNOT be bypassed — import it, do
   not re-implement it). Reply must accept text on stdin as well as argv
   (his words can carry shell-hostile bytes; `relay.py` is the idiom).
   A reply to a chat id that does not exist is a loud refusal, never a
   created chat (a typo'd id must not fork a conversation).
2. **Consume-side reply instructions.** When the coordinator's tick
   drains a `chat` receipt (`dev/journal_consume.py` — read how it
   presents drained receipts today), the drained chat item must carry
   what the dreamer needs to act: the chat id (= receipt id), the text,
   and the exact reply command from act 1. This is a presentation
   change in the consume output, not a new channel — the receipt is
   already the durable home.
3. **Formalise chats-v1.** `file-formats.md` gains the
   `.dreamwork/chats-v1/<id>/` contract: `transcript.md` (the dw-turn
   framing, the two anti-forgery rules — writer one-lines, parser
   anchors at line start — stated as the contract, citing
   `test_chat_turn_text_cannot_forge_an_agent_turn`), `chat.json`
   (identity only, never a second truth), the derived-index rule
   (title/turns/status derived at read time), and who writes vs reads.
   `lint.py` gets a check proportionate to the risk: at minimum a
   malformed-transcript check (a turn block that does not parse, or a
   `chat.json` that is not valid JSON / disagrees with its dir name)
   WARNs with the count of chats examined — degrade silently only on an
   absent store (a fresh target has no chats). Every lint check you add
   lands with tests in `test_lint.py`, and every check must be shown to
   fail when its defect is injected (name the production line, sabotage,
   watch fail, restore byte-identical with `cp`).

## Constraints

- **Red-first everywhere, per repo culture** (read the repo CLAUDE.md):
  a check that has never been red is not verification. This includes the
  CLI: a reply going through `apply_chat_turn` with marker-bearing text
  must parse back as exactly one agent turn — test it.
- The dashboard already renders the list (`list_chats`); a replied chat
  flips to `replied` automatically once an agent turn exists — verify
  end-to-end via `test_watch.py`'s existing chat tests (do not edit
  watch.py to make this work; if something in watch.py is genuinely
  needed, STOP and flag it in the DONE line).
- Run `python3 -m pytest test_watch.py test_lint.py -q` and
  `python3 lint.py --target .` green before reporting.
- Small commits in your worktree, message prefix `504reply: …`.
- DONE report: append ONE line to
  `~/.cache/agent-comms/ud-dreamwork/coord-inbox.md`:
  `[lane-504reply] DONE <shas> — <one line>` plus lines for: the CLI
  home choice + why, every red-proof (production line → failing test),
  and anything flagged for the coordinator (file-formats edits are
  yours; SKILL.md/watch.py needs are flags).
  Use `dev/relay.py` if present; never `attn`.
- Do not claim a model you were not dispatched as.
