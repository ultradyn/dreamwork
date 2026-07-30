# Brief — #516 design half: the question-updated wake policy under batched delivery

Task: **#516** (P2, open — verified in the store before writing this brief).
From the #514 wake-semantics audit, finding **F2 (VIOLATION, MEDIUM)**:
`track_question_updates` (watch.py, post-#534 around line ~12917) writes a
`question-updated` line to `watch-events.log` on every digest change —
**ungated and unjournaled**. The delivery-modes design (#342) and the
posture file (`delivery: batched` live right now) route which signals wake
the loop and which ride the durable receipt; this one routes through
nothing.

**You are the DESIGN half only.** Implementation touches `watch.py`, which
lane-504chat owns until it merges — your deliverable is a plan another
lane can implement cold, not code.

Lane-owns: `.dreamwork/docs/plans/question-updated-wake.md` (new file — create it)

You may READ anything (watch.py is owned by another lane for WRITES;
reading it is fine and required — read the post-#534 form on master,
`24052346`'s sibling merge is already in).

## Read first (all on master)

1. `watch.py` — `track_question_updates`, `log_event`, the sig-store re-seed
   (#534), and how `collect()` calls it. Note the #534 contract: an
   algo-upgrade re-seed emits ZERO events by design; only a real content
   change fires.
2. `.dreamwork/docs/plans/delivery-modes.md` — the #342 batched/instant
   model: what pre-empts in batched mode (`do-now`/`do-next`), what rides
   the receipt, what the per-kind policy table looks like.
3. `SKILL.md` — the tick flow's event-consumption step and the #342/#531
   drain (`pending → process → consume --through`).
4. The #514 audit findings doc under `.dreamwork/docs/findings/` — finding
   F2 verbatim, and its sibling findings (F1, F3…) so the policy you rule
   on is consistent with what the audit already established about wake
   semantics. `file-formats.md`'s `watch-events.log` row says the log is
   **best-effort and lossy by design** (`log_event` swallows `OSError`) —
   your ruling must live with that or change it deliberately.
5. `.dreamwork/posture` — the live axes (`delivery: batched`).

## The decisions to rule on (propose, with reasons — this repo refutes by
measurement, not taste)

1. **Gate or declare.** Is `question-updated` (a) a per-kind signal routed
   under the delivery mode — batched mode = rides the receipt, instant
   mode = wakes; or (b) an always-instant sync signal, exempt from the
   mode like `do-now`, with the justification written down? Consider: the
   event fires when the *dashboard server* notices a digest change, i.e.
   usually because the coordinator or a lane just edited questions.md —
   the loop already knows. Who is the event actually FOR? When did one
   last change what the loop did? (The watch-events.log tail is in the
   repo — measure, don't speculate.)
2. **Journal or not.** The submissions journal (#263) is the durable
   record a drain consumes; the events log is lossy. If the signal can
   matter after a restart, unjournaled means lost. State whether
   question-updated needs journal durability, and if not, why its loss is
   harmless *by construction* (e.g. the sig store itself is the durable
   record and the event is only ever a nudge).
3. **The phantom interaction.** #509's phantom #229 event and #534's
   re-seed-silence rule: your policy must state what happens to a REAL
   content change detected during the same collect as an algo re-seed
   (both can occur together — one entry changed while the store
   re-seeded). Is it still reported? (Check what the merged code actually
   does — the re-seed path returns zero events; if a real change rides
   the same collect, is it swallowed? If so, that is a defect your plan
   names, not a behaviour you design around.)
4. **Policy-table placement.** If the ruling is (a), say exactly which
   existing structure carries the per-kind row (delivery-modes.md's table?
   a `watch.py` constant?) so the implementation lane edits one place.

## Deliverable

`.dreamwork/docs/plans/question-updated-wake.md` — the repo's plan-doc
idiom (look at `delivery-modes.md` for the shape: context, the decision,
the refuted alternatives WITH the measurements that refuted them, the
implementation surface named by file+function). End with an explicit
**Implementation checklist** the follow-up lane can execute verbatim, and
a **Flagged for the human** section if any decision is genuinely his
(default: it is not — near-auto posture; rule it yourself with reasons).

## Constraints

- Do NOT edit watch.py, SKILL.md, lint.py, file-formats.md,
  .dreamwork/handoffs.md, or anything under `.dreamwork/` except your one
  new plan file. Do not create tasks; do not write questions.md.
- Commit your work in your worktree (`git commit`), one commit, message
  `design(#516): question-updated wake policy proposal`.
- When done, report to the coordinator inbox by appending ONE line to
  `~/.cache/agent-comms/ud-dreamwork/coord-inbox.md`:
  `[lane-516wake] DONE <sha> — <one line: the ruling in a sentence>` —
  plus a second line naming anything you flagged for the human.
  Use `dev/relay.py` if available; never `attn`.
- Model note: you were dispatched as glm-5.2; do not claim otherwise.

worktree: you are in an isolated worktree already. Your commit sha is the
deliverable handle — quote it in the DONE line.
