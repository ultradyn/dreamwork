# Brief — #527: reconcile the wake-line against the cursor (do-now acts once)

**Lane-owns:** `watch.py` (ONLY `command_line` at ~13690 and its call site in
`_handle_command` ~14360), `test_watch.py`, `.dreamwork/handoffs.md`. **Never**
`_handle_decide` (merged but stay out of it), `track_question_updates` ~12917
(lane-509sig), the markdown renderer (lane-521md), `setContent`/burndown
(lane-523burndown), `dev/journal_consume.py` (a later lane wires the proof).

**Task (from the store, P1):** Reconcile the wake-line against the cursor so a
do-now that both woke and drained is acted on once.

**Source:** #519 audit F1 (`.dreamwork/docs/findings/519-exactly-once-audit.md`)
— READ IT FIRST. The double-delivery is unconditional in batched mode: the
wake-line fires for every do-now (`emits_wake` → True for PREEMPT_KINDS) AND
the receipt drains on the tick. `command_line(kind, text, source)` carries no
receipt id, so the coordinator cannot match a drained receipt to the wake-line
it already acted on.

**Chosen shape (decided here, from the audit's options):** carry the receipt id
IN the wake-line. `_handle_command` runs AFTER the E3 receipt commit
(`do_POST` commits before dispatch), so the receipt id is available at emit
time — find how the handler can learn it (the commit's return, the envelope,
or `self._<something>` the E3 cutover stashes; READ the do_POST/dispatch code
and pick the cleanest existing seam — do NOT re-plumb the journal). The line
becomes e.g. `command via watch: do-now: <text> [receipt <id>]` (suffix, so
existing tail-monitor parsing of the prefix is undisturbed — CHECK what parses
these lines: `grep` the repo for `command via watch` readers incl.
`dev/capture/*.mjs`, and keep their expectations intact or update them in the
same commit).

**Acceptance (all required):**
1. Every `/command` wake-line (all kinds) carries its receipt id; the id shown
   is the id of the receipt the SAME POST committed (assert equality in the
   test — not just "an id-shaped string is present").
2. `pending`'s output and the wake-line can be matched by id: add to
   `test_watch.py` (or the existing delivery/wake test class) a test that
   POSTs a do-now, reads BOTH the wake-line and the journal receipt, and
   asserts the id in the line == the receipt's id. Runtime-derived
   preconditions (the POST returned a receipt id; the line exists).
3. Every reader of `command via watch` lines found in the grep still holds
   (run the guards that read watch-events.log SOLO after port check —
   39890-39899; name them in your report).
4. Every added/changed check red-proved by injection into the production line
   it binds + cp restore; each red names the line injected.
5. `git commit --only <paths>`; `.dreamwork/handoffs.md` Pending line
   `· landed \`<sha>\` · … · by lane-527recon —` naming commits, reds, and
   the seam you used to get the receipt id.

**Never:** change `emits_wake`/`PREEMPT_KINDS`/the cursor machinery; wire
`apply.reconcile` (that is #526, a different lane); touch the coordinator's
SKILL.md; `just deploy`; bind ports outside 39890-39899.

Model for the record: glm-5.2 (dispatch record — do not self-report a model).
