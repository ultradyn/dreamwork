# Brief — #526: wire the exactly-once proof into the cursor drain

**Lane-owns:** `dev/journal_consume.py`, `user_events/apply.py` (wiring surface
only — do not redesign the proof), `test_journal_consume.py` and/or
`test_user_events_apply.py`, `.dreamwork/handoffs.md`. **Never** `watch.py`
(lane-527recon owns `command_line`; other lanes own the rest), `SKILL.md`
(coordinator-owned), `.dreamwork/docs/plans/delivery-modes.md`.

**Task (from the store, P2):** wire the exactly-once proof into the cursor
drain, OR restate batched mode's exactly-once basis honestly. This brief CHOOSES
the wiring — the restate option is the fallback if you find the wiring is
unsound (then your deliverable is a written argument in your handoff, not code).

**Source:** #519 audit F4 (`.dreamwork/docs/findings/519-exactly-once-audit.md`)
— READ IT FIRST. The fact: `apply.prove_applied` (`apply.py:184`), `reconcile`
(`apply.py:274`), the `/command` adapter (`apply.py:419`) are exercised ONLY by
tests; `journal_consume consume` is two acts (read, advance) where
delivery-modes.md:162-180 describes three (read, verify+replay through adapters,
advance). The drain has no idea whether a receipt was already acted on.

**Shape (decided here):**
1. `consume` gains the middle act: for each drained event, route it through
   `apply.reconcile` (the adapter registry, exactly as the tests already
   exercise it) BEFORE advancing the cursor. A receipt that proves `APPLIED`
   finishes only (no second write — the `apply.py:318-321` behaviour). A
   receipt that does NOT prove applied is reported in `consume`'s output as
   UNAPPLIED (id + kind + route, one line) — the coordinator's tick habit
   says "process each event", and the unapplied list is what it must act on.
2. `pending` stays read-only and unchanged in shape (the coordinator's triage
   view), EXCEPT it may annotate each line with the proof verdict if that is
   cheap and honest — if it costs a second semantics, skip the annotation and
   say why in the handoff.
3. The cursor still advances only over what was read (the read-then-advance
   contract and its EX_SOFTWARE refusal are load-bearing — unchanged).
4. The proof must be BY-CONSTRUCTION about the drain itself: a second
   `consume` of the same range (simulate by rewinding the cursor in the
   fixture) applies NOTHING twice — assert the adapters' writes happen zero
   times on the replay.

**Acceptance (all required):**
1. Tests: (a) a drained `/command` receipt routes through reconcile and an
   already-applied one writes nothing (spies/fakes at the ADAPTER boundary —
   and name the production line that would have to change for the test to
   fail, then change it and watch it fail); (b) unapplied receipts are listed
   in `consume`'s output; (c) cursor semantics unchanged (advance only over
   read; refusal still EX_SOFTWARE 70); (d) the replay-of-replayed-range
   applies nothing (the by-construction test above). Preconditions derived at
   runtime everywhere.
2. Every added/changed check red-proved by injection into the production line
   it binds + cp restore; each red names the line injected. Per the repo's
   hardest rule: if a red run comes back GREEN, that is a finding — stop and
   fix the check, do not conclude the code was fine.
3. `git commit --only <paths>`; `.dreamwork/handoffs.md` Pending line
   `· landed \`<sha>\` · … · by lane-526proof —` naming commits, reds, and
   whether `pending` gained the annotation or not (and why).

**Never:** touch the dashboard, the guards, or ports; redesign `prove_applied`
(it is red-proven already — you are WIRING it); change the envelope/journal
shape; `just deploy`.

Model for the record: glm-5.2 (dispatch record — do not self-report a model).
