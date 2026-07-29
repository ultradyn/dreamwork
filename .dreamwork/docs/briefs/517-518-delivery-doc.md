# Brief — #517 + #518: delivery-modes.md catches up with the code

**Lane-owns:** `.dreamwork/docs/plans/delivery-modes.md`, `.dreamwork/handoffs.md`
(Pending line). Doc lane — review-gated, no test red-proof applies. Nothing else.

**Source:** #514 audit (`.dreamwork/docs/findings/514-wake-semantics-audit.md`),
findings F3 + "Contradictions with delivery-modes.md itself". READ THE AUDIT FIRST.

**Task (two store tasks, one doc increment):**
- **#517 (P3):** Document control-plane wakes (`/run-mode`, `/posture` — posture
  triple AND the delivery axis) as an explicit always-instant carve-out (the
  code's current behaviour) with the reasoning the audit surfaced: a `delivery`
  toggle that does not wake the loop until its next tick defeats the toggle.
  Also document the journal failure-path wakes (exception-only, `_journal_receive`
  / `_journal_record_health` / `_journal_reject`) as always-loud error
  diagnostics, and the one-shot `ud-dw-tasks-migrate` wake.
- **#518 (P3):** Reconcile the doc's route enumeration with reality.
  `WRITE_ROUTE_HANDLERS` has nine routes (watch.py:~14528 — verify the count at
  runtime, do not trust this number); the doc's §"What changes in watch.py's
  command handlers" names four. Cover ALL nine: the four gated content routes
  (`/command` by kind, `/answer`, `/ask`, `/comment`), `/decide` (being gated by
  lane-515decide — write the doc as the intended end-state: `/decide` rides the
  batched cursor like its siblings, and note the fix is in flight under #515),
  `/tint` and `/deploy` (correctly non-waking by design — say why), and the
  control routes (always-instant carve-out, per #517 above). Update the doc's
  "authorises no code / next increment" framing to design-as-built: the gates
  (`delivery_mode`, `emits_wake`, `PREEMPT_KINDS`) ARE landed in watch.py; name
  exactly which routes are gated.
- ALSO: add one line naming the two wake channels the audit found outside the
  route table entirely — `question-updated` (policy pending under #516) and the
  journal failure-path wakes — so the doc's completeness claim is auditable.

**Acceptance:**
1. Every claim about code cites a watch.py line you verified while writing
   (line numbers drift — verify, don't copy the audit's).
2. No claim that a route is gated unless the guard is in the code OR is named
   as in-flight (#515). The doc must not assert a future as a present.
3. The doc-map row (if delivery-modes.md has one) stays accurate.
4. `git commit --only <paths>`; handoffs.md Pending line
   `· landed \`<sha>\` · … · by lane-517doc —` naming what changed.

**Never:** touch watch.py or any code; never edit the audit findings doc;
never touch `.dreamwork/` files other than delivery-modes.md, its doc-map row,
and handoffs.md.

Model for the record: glm-5.2 (dispatch record — do not self-report a model).
