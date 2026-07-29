# Brief — #357 design: a CLI warning layer that surfaces incomplete data and what is waiting

Lane: `lane-357design` · READ-ONLY (design doc is the deliverable) · model on
record: llmp-glm-5-2.

## The task, in his words (2026-07-28 01:23, on #346 S4)

> "with these kinds of things we can have an automated warning layer in cli
> calls that raises issues where data is incomplete or whatever. Also things
> like unchecked message count, new task count, new question count,
> unanswered question count, unfolded-in answer count, etc."

…and 2026-07-28 02:45 (on #264): *"proper tooling will prevent that!"* —
recorded then as: **a footer every verb emits, not a verb you have to
remember to run** (the shape is settled by his word "tacked on").

## What to design

Write `.dreamwork/docs/plans/cli-warning-layer.md` — a design doc in the
house style (see `delivery-modes.md` / `attention-modes.md` for the shape:
measured facts first, the contract, what it does NOT authorise, open calls
only where a fork is genuinely his).

Ground it in what EXISTS today (measure, don't invent):
- the store (`.dreamwork/ledger.sqlite3`, schema v2 — read it READ-ONLY in
  the MAIN checkout: `sqlite3.connect('file:.dreamwork/ledger.sqlite3?mode=ro',
  uri=True)`; worktrees do NOT have it) — what "incomplete data" is actually
  queryable: NULL/unreadable `type` values, missing bands, `origin` unknown,
  blocked-on prose vs fields;
- the journal (`user_events/sqlite.py`) — what "waiting" is countable from:
  unconsumed receipts per consumer cursor, unapplied/unknown proofs;
- `questions.md` — unanswered question count, unfolded-answer count
  (`lint.check_unfolded_answers` already computes one of these — reuse,
  never duplicate);
- `dev/ledger.py` verbs (`file/fold/note/counts/fold`) — the footer seam:
  every verb emits it, so the warning rides output the human already sees.

## The questions the design must answer

1. **What the footer contains** — his five counts + incomplete-data warnings,
   and nothing else. What is cheap enough to compute on EVERY verb call
   (<50ms; the verbs run interactively)?
2. **Where it lives** — one function in `dev/ledger.py` (or a sibling module
   it imports) that every verb calls at exit. Not a new verb. Not opt-in.
3. **WARN, never ERROR** — the footer never changes an exit code and never
   blocks a verb. Say why in the doc (a warning that blocks is a verb).
4. **Quiet rules** — when does a count suppress (zero? unchanged since last
   call? a `.dreamwork/` opt-out?). Design against footer fatigue: a footer
   that always says the same thing teaches him to not read it.
5. **What is genuinely his to rule** — if every call has one clearly-superior
   answer, there are NO open questions (his standing rule). Candidate fork:
   footer on every verb vs only on verbs that change state.

## Constraints

- Read-only: the doc is the deliverable; no code changes. Mark clearly what
  the design does NOT authorise.
- Reuse over rebuild: `lint.py`'s existing counts, `ledger_parse` readers,
  the journal's cursor API — a second implementation of any of these is a
  defect the doc must not propose.
- House verification section: how each claim in the doc would be checked
  (and which checks could be red).
- Hand-off obligation (#398): if you stop before done, append state to
  `.dreamwork/handoffs.md` (main checkout).

Report: the doc's path, its open calls (if any), and the measurements it
rests on.
