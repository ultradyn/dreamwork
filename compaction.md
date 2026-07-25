# Compaction — the notice, the checklist, the acknowledgement

A dreamwork agent runs for a long time, so sooner or later its context is
compacted. This file covers **deliberate** compaction: someone decides to
compact the agent. Automatic compaction gets the same checklist, but with
no warning, which is exactly why the durable state has to be written as
you go rather than at the end.

## Why a notice comes first

A compaction summary preserves what was *said*. It does not preserve what
was *held* — the half-formed diagnosis, the reason you rejected the
obvious fix, the shape of a design conversation. **The notice is the only
window in which the agent can externalise what only it knows.** Sending
`/compact` without one throws that window away silently; nothing errors,
and the loss shows up an hour later as a decision being re-litigated.

So the protocol is always three steps, never two:

1. **Notice** — "you are about to be compacted".
2. **Acknowledgement** — the agent runs the checklist and says it is
   ready, naming what will be lost anyway.
3. **The command** — `/compact`, `/summarize`, whatever this client calls
   it.

## On receiving a notice (the checklist)

1. **Stop taking new work.** Land the current increment at a coherent
   point: commit it, or park it as a task with the remainder described.
   An uncommitted edit is the worst thing to carry across a compaction —
   the diff survives on disk, the reasoning behind it does not.
2. **Write the runtime state** to `.dreamwork/status.json`: the current
   task and its goal chain, live subagents (name, inbox path, files
   owned, in flight, queued behind it), armed monitors, how to deploy,
   and what the next actor should do first. Durable-by-design state
   (ledger, questions, docs, commits) already survives; this is the part
   that lives only in your head.
3. **Check the ledger is truthful** against the backend and against git.
   Ids created but never written down are lost at the boundary.
4. **Check every open ask is in `questions.md`.** Anything you asked the
   human that exists only in the conversation will not be asked again.
5. **Say what will be lost.** Some things cannot be written down in the
   time available — taste, a half-tested hunch, the feel of a design
   discussion. Name them to the human. It is not a failure to lose them;
   it is a failure to lose them quietly, because then nobody knows to
   re-steer.
6. **Acknowledge**, briefly and concretely: what you landed, what state
   you wrote, and anything the human should decide before the boundary
   (unpushed commits, a subagent mid-batch).

## On the far side

A compacted agent is not a re-initialized one — nothing re-runs on its
own. On the first tick after the boundary:

- Re-read `.dreamwork/status.json` and the ledger; treat both as claims
  to check against reality (git, the backend, the running processes),
  not as truth.
- Verify the monitors are still armed. A heartbeat that fires proves
  itself; the other monitors do not, and a dead inbox monitor means the
  human's steers land in a file nobody reads.
- Check on any subagent listed in `agents` before assuming it is alive.

## Sending a compaction (safeguards)

The client's dialect matters, and getting it wrong turns a safe
compaction into an abrupt one:

- **Turn-end clients** (Claude Code): `/compact` queues and fires when
  the current turn ends. The agent gets its window for free.
- **Instant clients**: compaction runs the moment the message is
  received. There is no window — the notice **must** be a separate,
  earlier message, and the command waits for the acknowledgement.
- **Queue-on-tab clients** (codex): `<tab>` instead of `<enter>` queues
  the command; sometimes twice, the first to autocomplete and the second
  to queue.

Two rules follow, and they hold in every dialect:

- **Never send the command before the acknowledgement.** Not for speed,
  not because the agent looked idle. Idle is not the same as ready.
- **One caller, one implementation.** Per-client mechanics belong in one
  place that knows the dialects, not improvised per call site — that is
  how an instant client eventually gets treated like a turn-end one.

Client-specific mechanics are general knowledge about coding-agent CLIs
rather than dreamwork's own, so the dialect table lives in the shared KB
(`~/.llm-general/`, coding-agent CLI reference) and this file points at
it. A managed sender (dreamhub, when it exists) implements exactly the
three steps above; until then, the human sends the notice and the
command by hand, and this checklist is what the agent owes them in
return.
