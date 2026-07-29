# Brief — #519: audit the do-now exactly-once path (wake AND drain)

**Lane-owns:** `.dreamwork/docs/findings/519-exactly-once-audit.md` (you create
it), `.dreamwork/handoffs.md` (Pending line). AUDIT ONLY — owns no production
file. Review-gated, no test red-proof applies.

**Task (from the store, P2):** Audit coordinator-tick reconciliation of
wake-line vs cursor-drain for pre-empt kinds — confirm a do-now that BOTH woke
at POST and drained on the tick is acted on exactly once, not twice.

**Source:** #514 audit's "What I COULD NOT determine" (`.dreamwork/docs/findings/514-wake-semantics-audit.md`).
A do-now wakes at POST time via `emits_wake("do-now") → True` (a line in
`.dreamwork/watch-events.log` that the loop's tail Monitor fires on). The same
do-now's receipt is ALSO in the journal, so the tick's cursor drain
(`dev/journal_consume.py consume` for consumer `'coordinator'`) re-lists it.
delivery-modes.md relies on the adapters' exactly-once proof
(`apply.prove_applied` in `user_events/apply.py`) to make the replay a no-op.

**The question:** when the coordinator processes a do-now — woken by the event
line, with the receipt still pending in the cursor — is there any path where the
SAME instruction is acted on twice? And conversely: is there a path where acting
on the wake-line leaves the receipt unconsumed forever (a permanently-growing
pending list)?

**Method (like the #514 audit):** static, read-only. Read:
- `user_events/apply.py` — what `prove_applied` actually proves, what state it
  keys on, what happens on a second application of the same receipt.
- `dev/journal_consume.py` — what the coordinator sees at the tick (pending →
  consume) and what it does with each event (or: what the SKILL.md tick habit
  instructs, `SKILL.md` § batched delivery).
- `SKILL.md` — the tick flow: does the loop act on a wake-line directly, or only
  ever on drained receipts? Quote the instructing lines.
- `watch.py` `_handle_command` — what the wake line contains (does it carry the
  receipt id? enough to act on? or just a notification?).

**Verdicts required:** for each of the double-act and never-consumed paths:
COMPLIANT (exactly-once holds, cite the mechanism) / VIOLATION (a concrete
double-act or leak path, cited) / UNCLEAR (what you could not determine
statically, and what runtime evidence would settle it).

**Output:** the findings doc, same shape as the #514 audit (writers/seam table,
severity-first findings, could-not-determine section, proposed follow-up task
titles for the coordinator to file verbatim).

**Acceptance:** every claim cites a file:line you verified; handoffs.md Pending
line `· landed \`<sha>\` · … · by lane-519audit —`; `git commit --only <paths>`.

**Never:** modify any production file; never run servers or bind ports;
never touch `.dreamwork/` files other than your findings doc and handoffs.md.

Model for the record: glm-5.2 (dispatch record — do not self-report a model).
