# Lane report — #721: triage the open ids git already names (PASS 1, verb form)

**Verdict: DONE — report only, no folds.** All 17 verb-form ids triaged by
content (#706 standard: the content on master at this line, never the subject).
Rebased clean onto local master `13e8b8c6`; HEAD at report time.

## The 17

| id | disposition | sweep-named verb commit(s) | one-line basis |
|---|---|---|---|
| #194 | **partial** | `1618ac26` `472b9e83` `5c19a68f` (feat) | three feat slices landed; init step + discovery subagent remain |
| #196 | **landed — fold** | `6d581823` (fix) | qsec arrival/departure implemented on master |
| #225 | **named, not landed** | `7c234bcd` (docs) | steering/contract artifact; no `explore` command built |
| #235 | **named, not landed** | `00a52cff` (docs) | review artifact; no topic-chat promotion; blocked #373 |
| #236 | **named, not landed** | `00a52cff` (docs) | same commit as #235; no provenance recording; blocked #373 |
| #237 | **named, not landed** | `e7671a67` (docs) | steering artifact; no JSON-rain; MODEL GATE |
| #253 | **named, not landed** | `b9b6a475` (docs) | research artifact; no annotations built |
| #254 | **partial** | `542c43a1` (docs) `e9b6a842` (fix) | design landed; UI implementation is a separate, ungranted ask |
| #257 | **named, not landed** | `f944552e` (docs) | design artifact; no do-now treatment; blocked #241 |
| #263 | **partial** | 28 commits (feat/fix/merge/docs/design) | E1–E5b + H1–H2 landed; E6 (visible) + lane G remain |
| #269 | **partial** | `a47f4016` `03667067` (fix) | acute per-question fix landed; full module (all fields, IndexedDB, cross-tab) remains |
| #275 | **named, not landed** | `a75770eb` (docs) | research/plan artifact; entry itself says "NOT landed"; blocked-on-human |
| #354 | **landed — fold** | `0f77a1fa` (feat) | chunked streaming fixes the buffering bug; Range/206 is separate future scope |
| #448 | **named, not landed** | `bdc9cd19` (docs) | survey artifact; feature blocked on #294 |
| #465 | **landed — fold** | `bcad34f1` (docs) — **false positive** | sweep named the brief; the real landing `58e3040` uses `wip(#465)`, invisible to the pattern |
| #493 | **named, not landed** | `32647137` (docs) | design artifact; implementation is a follow-on |
| #500 | **partial** | `8bf3c5ba` `952db8dd` `904b7893` (test/feat) | first slice (scaffold + adapter + tests) landed; activation + hooks remain |

**Tally: 3 fold, 5 partial (stay open), 9 named-not-landed (stay open).** The 9
are the #707 weak-verb false-positive class exactly as the brief predicted — a
`docs(#NNN)` naming an id it is *about*, not one it lands.

## Calibration — #159 (direction 1, discharged against the method)

#159 is folded and will not appear in the list, so it is the calibration case.
The method independently re-derives the known answer: `fc643d7e` is an ancestor
of master, and the arrival mechanism it shipped is on master at
`client/command.js:135` (`confirmationFor`) applying `.dreamin` + a forced reflow
(`void m.offsetWidth`) + rAF class removal at `:148-149`, guarded per-frame in
`dev/capture/dismiss.mjs:153-173` (asserts part-way opacity and translateY
between frame endpoints — a snap has zero). The bare `#159:` subject was missed
by the old pattern and matched under #707, exactly as the entry records.

## Per-id evidence

### #194 — PARTIAL (stay open, note remainder)

Plan: `docs/plans/version-and-upgrade.md`. Three feat slices landed with real
content on master:

- `1618ac26` feat(#194): commit trailers — `SKILL.md` +14 lines (the
  `Migration:`/`Feature:`/`Needs:` trailer convention).
- `472b9e83` feat(#194): `bin/ud-dw-githash` (44 lines) + `test_githash.py`
  (134 lines) — the skill reports its own version.
- `5c19a68f` feat(#194): `DREAMWORK.md` frontmatter + `file-formats.md` row +
  `lint.py` check + `migrations/2026-07-25-14-version-frontmatter.md`.

All three are ancestors of master. **Remainder** (per entry): init step and
discovery subagent. Recommend: stay open, cite the three shas to stop re-flagging.

### #196 — LANDED (recommend fold)

`6d581823` fix(#196) is an ancestor of master. Content on master:
`dev/capture/qsec.mjs` line 1 — *"qsec — #196: the dashboard's questions fold
ARRIVES and DEPARTS"* — 275 lines implementing the arrival/departure transition
and its per-frame guard. `watch.py` wires the `.qsec` surface. The bug ("snaps
instead of arriving") is fixed; no remainder stated.

### #225 — NAMED, NOT LANDED (stay open, cite sha)

`7c234bcd` docs(#225,#232,#233) touches `.dreamwork/answers.md`,
`questions.md`, `review/explore-command-contract.html`, `tasks.md` — steering
and a review-contract artifact. The task is "Add an `explore` proposal command"
(implementation). No command was built. Recommend: cite `7c234bcd` in the entry.

### #235 — NAMED, NOT LANDED (stay open, cite sha)

`00a52cff` docs(#235,#236) touches `.dreamwork/review/threaded-topic-chats.html`
+ `tasks.md` — a review artifact. The task is "Promote /answers follow-ups into
topic chats" (implementation). Blocked on #373. Recommend: cite `00a52cff`.

### #236 — NAMED, NOT LANDED (stay open, cite sha)

Same commit as #235 (`00a52cff`). The task is "Record compact topic-chat action
provenance." No provenance recording built. Blocked on #373. Recommend: cite
`00a52cff`.

### #237 — NAMED, NOT LANDED (stay open, cite sha)

`e7671a67` docs(#233,#237,#238) touches `questions.md`,
`review/lan-bind-threat-model.html`, `tasks.md` — steering. The task is
"[Opus5] JSON-character rain on data refresh." MODEL GATE: no Opus-5 work
permitted. Recommend: cite `e7671a67`.

### #253 — NAMED, NOT LANDED (stay open, cite sha)

`b9b6a475` docs(#253) adds `.dreamwork/docs/research/contextual-review-annotations.md`
(61 lines) — research. The task is "Add contextual review annotations and
attached discussions" (approved design/implementation). No annotations built.
Recommend: cite `b9b6a475`.

### #254 — PARTIAL (stay open, note remainder)

Two commits named; the entry also cites a third (`5b813f1`):

- `542c43a1` docs(#254): `threaded-notes-spec.md` (498 lines) — design spec.
- `5b813f1` merge(#254): `note-reply-threading-254.md` (483 lines) + review
  artifacts — the rooted-exchange design.
- `e9b6a842` fix(#254): restores line breaks in `questions.md` (25 lines) — a
  ledger formatting fix, not UI.

The grant was **WRITTEN DESIGN ONLY** (entry: "the scope limit is part of the
approval"). Design landed; UI implementation is explicitly a separate, ungranted
ask. Entry: "stays open on purpose." Recommend: stay open, cite the design shas.

### #257 — NAMED, NOT LANDED (stay open, cite sha)

`f944552e` docs(#257,#258) adds `.dreamwork/review/do-now-urgency-treatment.html`
(787 lines) — a design artifact. The task is "Give do-now a danger and urgency
treatment" (implementation). Blocked on #241. Recommend: cite `f944552e`.

### #263 — PARTIAL (stay open, note remainder + stale successor list)

The durable-receipts / user-event-journal task. 28 verb-form commits named; the
implementation landings are real code on master:

- `69b85738` feat E1 envelope — `test_user_events_http.py` (213 lines) +
  `watch.py` (125 lines).
- `d460947a` feat E2 shadow, `38ef4098` feat E3 cutover — `watch.py` +
  `test_user_events_http.py` + `dev/capture/*.mjs`.
- `0024ad2f` feat E4 besteffort, `a67f3089` feat E5 reject, `a328507a` fix E5b.
- `0cbe62a4` feat H1, `b2fc6be9` feat H2 cutover, `25fc7891` feat H2 drain —
  `user_events/sqlite.py` (336 lines) + `test_user_events_sqlite.py` (289 lines).
- Merge commits `693b2e9e`, `c74046d6`, `5531533b`, `00a13438`, `741b9831` all
  ancestors of master.

**Remainder:** E6 (visibility — a browser/motion increment needing
`transitions.md`) and lane G (increments 30–33) do not appear among the landed
commits. The entry is deliberately open per #404 option 2.

**The entry's successor list is partly stale:** it names E4, E5, E6, G, H as
"still open as the successor," but E4, E5, E5b, H1, H2 have all landed since it
was written. Only E6 and G genuinely remain. Recommend: stay open; update the
successor list and cite the E4/H2 shas to stop re-flagging them.

### #269 — PARTIAL (stay open, note remainder)

Two fix commits, both real code on master:

- `03667067` fix(#269): `dev/capture/reviewdraft.mjs` (276 lines) +
  `watch.py` (110 lines) — the acute per-question answer-box draft durability.
- `a47f4016` fix(#269): drops a guard that could not fail in `watch.py`.

**Remainder** (per entry): the broader module — every text field, project-
partitioned IndexedDB store, cross-tab sync. The entry was de-prioritised P1→P3
("acute bug shipped; remainder is seams only"). Recommend: stay open, cite
`03667067`.

### #275 — NAMED, NOT LANDED (stay open, cite sha)

`a75770eb` docs(#275) adds `.dreamwork/docs/plans/hub-public-auth.md` (163 lines)
— plan/research. The entry itself states: *"NOT landed, and #306's check is
why... blocked on: his ruling on the six questions."* The research half is done;
the task's own terms require an approved design, which awaits a human ruling.
Recommend: cite `a75770eb`.

### #354 — LANDED (recommend fold)

`0f77a1fa` feat(#354) is an ancestor of master. Content on master:
`watch.py:903` `FILEBYTES_CHUNK = 65536`; `_send_bytes` at `watch.py:5003 @ 2ccc1995` does
`while True: chunk = body.read(FILEBYTES_CHUNK)` then `self.wfile.write(chunk)`
— chunked streaming, not whole-file buffering. The task's ask ("/filebytes
buffers a whole file with no cap") is fixed. `test_watch.py` gains 223 lines of
streaming tests. The planned single-range `206` capability is separate future
scope (the entry frames it as "increment 2, a new protocol capability"), not a
remainder of this task.

### #448 — NAMED, NOT LANDED (stay open, cite sha)

`bdc9cd19` docs(#448) amends `.dreamwork/docs/plans/questionnaire-survey.md` —
the survey. The task is "a questionnaire feature." Entry: *"The FEATURE stays
blocked on #294; the survey was always the precondition, not the deliverable."*
Recommend: cite `bdc9cd19`.

### #465 — LANDED (recommend fold; sweep-named commit is a false positive)

The sweep named `bcad34f1` docs(#465,#463,#464) — which adds
`.dreamwork/docs/briefs/465-lane-containment.md` (123 lines), a **brief file**.
This is exactly #707's false-positive class: a docs commit naming the id it is
about.

The real landing is `58e3040` `wip(#465): lane containment as the lane left it`
— invisible to the sweep because `wip` is not a canonical verb. `58e3040` is an
ancestor of master. Content on master: `dev/lane_guard.py` (752 lines), which
refuses a main-checkout commit touching a dispatched lane's paths (line 51:
"it refuses (exit 1), naming the lane, the contested paths, and the remedy"),
reading ownership from brief `Lane-owns:` lines (line 217). Entry confirms
"LANDED `58e3040`, merged `ef5db01`."

**Note for the coordinator:** the `wip` verb is structurally invisible to
`SWEEP_SUBJECT`. This is the same blind spot #707 widened for `Merge #N` and
bare `#N` — `wip(#N)` is a third form the pattern cannot read.

### #493 — NAMED, NOT LANDED (stay open, cite sha)

`32647137` docs(#493) adds `.dreamwork/docs/plans/posture-autonomy-axis.md` (463
lines) — design. Entry: *"design delivered... Implementation is a follow-on."*
The axis is inert until #500's bridge lands the consumers it gates. Recommend:
cite `32647137`.

### #500 — PARTIAL (stay open, note remainder)

Three commits, all real content on master:

- `904b7893` feat(#500): `plugins/ud-dreamwork-matt-pocock-skills/SKILL.md` (144
  lines) — the scaffold.
- `952db8dd` feat(#500): `tracker_adapter.py` (172 lines) — the §8 contract.
- `8bf3c5ba` test(#500): `tests/test_tracker_adapter.py` (267 lines) +
  `conftest.py` — T1–T5 seam checks.

**Remainder** (per entry): activation (`docs/agents/issue-tracker.md`), lifecycle
hooks, grill-skill wiring. The first slice is authority-floor only. Recommend:
stay open, cite the three shas.

## Out of scope (named, not fixed)

1. **`wip(#N)` is a third blind spot in `SWEEP_SUBJECT`.** #465's real landing
   (`58e3040`) uses the `wip` verb and is invisible to the pattern — same class
   as the bare `#N` and `Merge #N` forms #707 widened. The canonical-verb list
   (`merge fix feat close perf refactor guard docs test design`) does not include
   `wip`. This is a #707 follow-on, not a #721 fix.

2. **#263's entry successor list is stale.** It names E4/E5/H as open, but those
   landed after the note was written. Only E6 and G remain. A ledger edit, not a
   code change — for the coordinator.

3. **#275 and #465 both appear in PASS 2 (widened form) too.** #275 has
   `f1d04edf` `#275:` and #465 has `36c7d867` `#465 +`. Those are PASS 2 and not
   triaged here; flagged only so the coordinator knows the two passes overlap on
   these ids.
