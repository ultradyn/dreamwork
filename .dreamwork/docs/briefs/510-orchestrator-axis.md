# Brief — #510 implementation: the `orchestration` posture axis

**Lane-owns:** `lint.py` (the posture sets + check ONLY), `watch.py` (posture
parsing/`_handle_posture`/`posture_line`/the dashboard posture picker ONLY),
`file-formats.md` (the `.dreamwork/posture` contract), `test_lint.py` /
`test_watch.py`, `dev/capture/posture.mjs` (only if the picker change requires
it), `.dreamwork/handoffs.md`. **Never** `SKILL.md` (coordinator does the docs
half after merge — the design's split), `_handle_decide`,
`track_question_updates`, the markdown renderer, `setContent`/burndown,
`command_line` (five lanes own those).

**He ruled (2026-07-30 07:46, all three recs):** orchestration is a MODE, not
an identity; a **binary axis `hands-on` | `orchestrator`, absent → `hands-on`**
(today's behaviour, so a pre-axis posture file is byte-identical in effect);
land the axis, do NOT enable the `hierarchical` run-mode value.

**Design (READ IT — the settled-shape section is the spec):**
`.dreamwork/docs/plans/orchestrator-posture.md`. The four touches, the same
shape `delivery` (#342) took:
1. `lint.py`: `POSTURE_AXES` gains the axis name (use **`orchestration`** —
   verify against the design doc; if it names a different axis string, the doc
   wins); a stops tuple `("hands-on", "orchestrator")` beside the others;
   `check_posture`'s axis-generic closed-set branch then enforces it (verify
   it really is axis-generic — if it is not, extend it and red-prove).
2. `watch.py`: `parse_posture_text`/`resolve_posture`/`write_posture`/
   `posture_line` (find the exact set `delivery` touches — mirror them, no
   more) and the dashboard posture picker gains ONE control for the axis,
   behind the same shared 10s arm, emitting the same one-`posture via
   watch`-line ceremony. The control follows watch-design.md's posture
   controls idiom (READ the posture section of watch-design.md first) and
   `transitions.md` governs any state change in it.
3. `file-formats.md`: the `.dreamwork/posture` contract gains the axis row in
   the same commit (lint checks this — run it).
4. Semantics of the stops (for the picker's copy and the doc): `hands-on` =
   the coordinator implements increments itself (it may also delegate, per
   the delegation number); `orchestrator` = the coordinator implements
   NOTHING inline — every increment is dispatched; the coordinator's role is
   adjudication/review/ledger only. Absent axis → `hands-on`.

**Acceptance (all required):**
1. Tests: (a) lint accepts `orchestration: orchestrator` and `…: hands-on`,
   ERRORs on a third value, WARNs on nothing new; (b) absent axis derives
   `hands-on` everywhere `delivery`'s absent-derives-default is asserted
   (find those tests; mirror them); (c) POST /posture with the new axis
   round-trips (writes the file, one events line, the arm ceremony
   unchanged); (d) the picker renders the control with the current value
   selected (guard or test — the posture.mjs idiom). Preconditions derived
   at runtime.
2. `python3 lint.py` clean; the file-formats contract and the code agree
   (lint verifies this — prove it by making them DISAGREE once and watching
   lint complain, then restoring).
3. Every added/changed check red-proved by injection into the production
   line it binds + cp restore; each red names the line injected. A green
   red-run is a finding, never a relief.
4. Run the posture guard SOLO after checking ports 39890-39899; run
   `python3 -m pytest test_lint.py test_watch.py -q`.
5. `git commit --only <paths>`; `.dreamwork/handoffs.md` Pending line
   `· landed \`<sha>\` · … · by lane-510impl —` naming commits, reds, and
   every site the axis touched (the list IS the claim of completeness —
   cross-check it against `grep -rn "delivery" lint.py watch.py` and note
   any site you deliberately skipped with the reason).

**Never:** touch the `hierarchical` run-mode value (stays disabled);
change what the axis DOES to loop behaviour (that is SKILL.md's restate +
the coordinator's conduct, landing separately); `just deploy`; bind ports
outside 39890-39899.

Model for the record: glm-5.2 (dispatch record — do not self-report a model).
