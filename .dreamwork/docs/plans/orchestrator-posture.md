# Orchestrator posture — an 'Orchestrator' option in Posture, IGC'd (#510)

**Design only — no code authorised.** No `watch.py`, no `lint.py`, no
`file-formats.md`, no `.dreamwork/posture`, no dashboard, no migration, no
running loop. This doc + a doc-map row + a draft `questions.md` entry are the
deliverable; he rules, then a later split builds (a subagent does the WebUI,
the coordinator does the docs), and only after he rules.

## His words (2026-07-30 04:54, verbatim — the task)

> We should have an 'Orchestrator' option somewhere in the Posture. I'm not
> sure exactly how best to integrate that, it doesn't feel to strictly match
> anything we already have. Please /use-igcs to evaluate options and present
> them to me in a question so I can choose between them.

`/use-igcs` is the vendored method (`igc-method.md` + `igc-concepts.md` at the
skill root, #447): binary goals, decisive errors, one survivor or a real fork.

## Authority and what this builds on

The posture file (`.dreamwork/posture`, contract at `file-formats.md` §".dreamwork/
posture") holds **four axes today**: `pace`, `asking`, `delegation`, `delivery`
— read off the live file (`pace: hot` / `asking: near-auto` / `delegation: 4` /
`delivery: batched`). The closed-set discipline is uniform and was read at the
source: `POSTURE_AXES = ("pace", "asking", "delegation", "delivery")`
(`lint.py:2259`); `POSTURE_STOPS_PACE` (`lint.py:2234`), `POSTURE_STOPS_ASKING`
(`lint.py:2240`), `POSTURE_STOPS_DELIVERY` (`lint.py:2250`); `check_posture`
(`lint.py:2339`) ERRORs on an out-of-set value and WARNs on an unknown axis.
`delegation` is the exception — it carries a **number** (an average-concurrency
target, never a cap; his `#445` Q3), `RUN_MODE_TO_POSTURE` (`lint.py:2279`) and
`derive_posture` (`lint.py:2286`) derive posture from run-mode, and `watch.py`
imports those sets (never restating) through `POST /posture` behind the shared
10s arm with one `posture via watch` events line. A fifth axis is therefore an
**additive row through every one of those sites**, the same shape `delivery`
(#342) took and `autonomy` (#493) is designed to take — measured, not assumed.

What this builds on, beyond the machinery: the **orchestrator role is lived
material in this repo**, not an abstraction. `.dreamwork/docs/dogfood-
orchestration.md` is ~1400 lines about exactly the question his ask turns on —
*"does the dreamwork loop work with the main session as coordinator only —
dispatching every increment — rather than doing the work itself?"* — and it
records, from inside the role, that *"the coordinator's real job turned out to
be adjudication, not planning"* and *"I am closer to a reviewer with a fleet."*
And he has already **named the coordinator "the orchestrator" in his own
hand** — `questions.md:1119`, instructing `#263`: *"I expect you main opus 5
claude orchestrator to do all the planning around this and to prepare precise
instructions … for your subagents."* So "Orchestrator" is his word for the
main-dreamer/coordinator role, and the question is what an *option* for it
*in the Posture* means.

## The referent, investigated not assumed

His sentence — *"it doesn't feel to strictly match anything we already have"* —
is load-bearing: it says the nearest existing axis (`delegation`) is *not* it,
and the IGC below must take that seriously rather than forcing the fit. But
"Orchestrator" is genuinely two-faced in this repo, and which face he means is
**a fork for him, not a coin this doc flips silently**. Three readings, named
and ranked:

**Reading A — orchestration MODE (designed against; the primary).** *Does the
coordinator implement increments itself, or only dispatch + review (implement
nothing inline)?* This is the coordinator-only-loop concept `dogfood-
orchestration.md` is the running record of, and it is the posture his word
"orchestrator" describes when he used it at `questions.md:1119` (plan, brief,
dispatch, adjudicate — *not* implement). It is **adjacent to `delegation` but
orthogonal to it** (the IGC settles this): `delegation` answers *how many
helpers on average* (a number); orchestration answers *whether the
coordinator's own hands touch the work at all* (a mode). A coordinator can run
a fleet of four and still implement inline between dispatches (today's default);
an "orchestrator" runs the same fleet and implements nothing. The two axes
answer different questions. His "doesn't strictly match" is correct: delegation
is the nearest neighbor and it is not this.

**Reading B — orchestrator IDENTITY (a live second reading; pushed back on).**
*Which harness/model/session IS the orchestrator* — this Claude session vs a
Grok session vs a `ccc` runner. The coordinator flagged this as the strongest
reading, and it has real support: he literally said "opus 5 claude orchestrator,"
and the loop's behaviour *does* depend on which model coordinates (`dogfood-
orchestration.md`'s whole runner comparison: grok is fast + can see; glm52 is
slower + thorough). **But identity is a dispatch/provenance fact, not an
operating posture dial**, and the repo already records it correctly: the
provenance notice at `handoffs.md` (and `ccc-runner-routing.md`, #469) establishes
that a lane cannot know its own model, the **dispatcher owns the alias it
passed**, and the model is derived from `~/.config/ccc/config.toml`. Putting
"which model orchestrates" into `.dreamwork/posture` would mis-categorise a
provenance fact as a per-tick operating dial, and a posture file is the wrong
home for it — machine-local, gitignored, re-read every tick, set from the
dashboard. He sets "who orchestrates" by *which session he runs / which alias he
dispatches*, not by typing a value into a posture picker. The honest posture
surface for "the coordinator's behaviour depends on its model" is `pace` (cadence)
and the capability-routing `dogfood-orchestration.md` already does — not a new
identity axis. **This reading is escalated as Q1, with a rec against it**, not
silently dropped.

**Reading C — a named persona / system-prompt selector for the main dreamer.**
Rejected: a posture axis is operational state re-read every tick, not a prompt
template. The main dreamer's persona is fixed by SKILL.md + DREAMWORK.md; a
"persona" posture stop would be a second description of something that already
has one home. Not designed against; mentioned so it is visibly considered.

**This doc designs against Reading A.** Reading B is the genuine fork and is
Q1 below with a rec; if he means B, the IGC's integration question is different
(identity has no natural closed set of posture stops and belongs at dispatch),
and the doc says so plainly rather than forcing B into A's shape.

## Two load-bearing facts, measured read-only

Measurements against the live checkout at master (`f74197b0`): `lint.py`,
`watch.py`, `file-formats.md`, `.dreamwork/posture`, `.dreamwork/questions.md`,
`.dreamwork/docs/dogfood-orchestration.md`. The posture file is his live file —
read-only; the contract in `file-formats.md` is cited in preference to any live
value.

### 1 · Orchestration is orthogonal to delegation — witnessed, not argued

`delegation` is an **average-concurrency target integer** (`lint.py:2230`:
*"an average-concurrency TARGET, never a cap — his #445 Q3"*), `0` = own, `1` =
assist, `2+` = delegate (`delegation_posture`, `lint.py:2300`). It says nothing
about whether the coordinator *also implements*. The witness is the same shape
as `#443`/`#445`'s "tonight's session" evidence: `dogfood-orchestration.md` ran
the coordinator-only mode holding *"coordinator implements nothing"* **constant**
while the fleet size (delegation) **varied 2→5 concurrent** (§"The role at five
lanes"). So orchestration-mode was held fixed while the delegation number moved —
direct evidence they are independent decisions, the way *"lackadaisical but
delegating"* was direct evidence that pace and delegation are independent
(`#443`'s filing reason). A coordinator can be `delegation: 4` + orchestrator
(fleet of four, coordinator reviews only) **or** `delegation: 4` + hands-on
(fleet of four, coordinator also implements inline) — the latter is today's
default, and neither value of one forces a value of the other.

### 2 · The fleet concept he is gesturing at already exists, teed up and disabled

`watch.py:343`: `RUN_MODES_PLANNED = ("hierarchical",)`. `RUN_MODE_DESC
["hierarchical"]` (`watch.py:363`): *"planned · needs concurrency (#264) and
containment (#288)."* So the repo already has a name for *"the main dreamer
orchestrates a hierarchy/fleet"* — `hierarchical` — and it is **shown but
disabled** in the dashboard exactly because #264 (concurrency) and #288
(containment) are not yet honest. `hierarchical` is a **run-mode value**, and
run-mode derives posture (`derive_posture`, `lint.py:2286`). That is the trap an
integration has to avoid: `hierarchical` *bundles* decisions into one word —
which is precisely the defect `#443`/`#445` spent a whole design untangling
(*"run-mode today carries three independent decisions in one"*). Any integration
that re-bundles orchestration back into a run-mode value reopens `#443`; any
integration that lands it as its own posture axis is the orthogonal-dial form
`hierarchical` always wanted to be. The IGC below turns on this.

## The IGC — how to integrate 'Orchestrator' into Posture

Method: `igc-method.md`. Binary goals (each a breakpoint, not a maximum),
decisive errors written out, one survivor or a real fork. The **ideas are the
integration shapes** (his *"I'm not sure exactly how best to integrate that"*),
not interpretations of the word — the referent (Reading A) is fixed for the
matrix; Q1 escalates the referent itself.

### Context

A single developer steers an autonomous loop through a machine-local,
gitignored, tick-re-read posture file. He wants to express *"the coordinator is
in orchestrator mode — it dispatches and reviews, it does not implement"* as a
selectable posture, the way he already selects pace / asking / delegation /
delivery. The decision must reach a running loop, compose with the existing
four axes and the planned `hierarchical` run-mode, and not duplicate `delegation`.

### Goals (binary; each can refute alone)

- **G1 — settable independently of the delegation number.** The
  does-the-coordinator-implement decision must be changeable without also
  moving the average-concurrency target. *(Witness: tonight's coordinator-only
  mode held it constant while delegation moved 2→5.)*
- **G2 — reaches a running loop.** It survives a process restart and is re-read
  every tick — the only property that lets an on-disk change reach a running
  loop (`#426`); it does not live in conversation or a UI control alone.
- **G3 — preserves the closed-set discipline.** Lint-checked, dashboard-settable
  behind the shared 10s arm, one events line on change, no silent fallback —
  the contract `pace`/`asking`/`delivery` already hold.
- **G4 — does not duplicate or contradict `delegation`.** Two axes holding
  overlapping meaning drift (the two-truths hazard `#306`/`lint.py` exist for);
  the new axis must answer a genuinely different question.
- **G5 — composes with, not preempts, the `hierarchical` / #264 / #288 fleet
  machinery.** One story about fleet orchestration, not two vocabularies that
  disagree about the same concept.

### Ideas

- **I1 — a fifth posture axis** (closed set, absent = today). Additive row
  through `POSTURE_AXES` + a stop-tuple + `derive_posture`, the shape
  `delivery`/`autonomy` take.
- **I2 — fold onto `delegation`.** Encode solo-vs-orchestrate as a value or
  band on the delegation axis (a special sentinel, or "high delegation means
  orchestrator").
- **I3 — land the planned `hierarchical` run-mode value** and let it derive an
  orchestration posture. "Orchestrator" = enabling `hierarchical`.
- **I4 — a control only, no file.** A dashboard toggle with no persistence to
  `.dreamwork/posture`.
- **I5 — a sibling file** `.dreamwork/orchestration` (one line, closed set).

### Matrix

| Idea | All | G1 | G2 | G3 | G4 | G5 |
|------|:---:|:--:|:--:|:--:|:--:|:--:|
| I1 · fifth posture axis | **✔** | ✔ | ✔ | ✔ | ✔ | ✔ |
| I2 · fold onto delegation | ✘ | ✘ | ✔ | ✔ | ✘ | ✔ |
| I3 · `hierarchical` run-mode value | ✘ | ✘ | ✔ | ✔ | ✘ | ✘ |
| I4 · control only, no file | ✘ | ✔ | ✘ | ✘ | ✔ | ✔ |
| I5 · sibling file | ✘ | ✔ | ✔ | ✘ | ✔ | ✔ |

### Decisive errors (the ✘s)

- **I2 refuted on G1 and G4.** `delegation` is a *number* (average concurrency);
  orchestration is a *mode* (coordinator-implements-or-not). A number cannot
  encode a mode without losing the independent setting: folding makes
  *"orchestrator with a fleet of two"* and *"orchestrator with a fleet of five"*
  collapse into one delegation value, which is exactly the independence G1
  requires (and the witness establishes). And it **overloads delegation's clean
  meaning** — a number that also means "solo/orchestrate" is two axes pretending
  to be one, the same *"one word carries N decisions"* defect `#443`/`#445`
  refuted for run-mode. Decisive: the fold destroys the orthogonality that makes
  either axis legible.
- **I3 refuted on G1 and G5.** `hierarchical` is a *run-mode value*, and run-mode
  **bundles** pace + asking + delegation into one word — the conflation `#443`
  exists to end. Adding orchestration to the bundle reopens `#443` for a fourth
  decision (G1: the orchestration decision is no longer independently settable,
  it rides inside a named mode). And it **preempts rather than composes** (G5):
  landing `hierarchical` as *the* fleet concept means a run-mode value and a
  posture axis are two vocabularies for one thing, and run-mode is the wrong
  layer (it *derives* posture; it is not posture). The honest form of what
  `hierarchical` gestured at is the posture axis I1, not the run-mode value I3.
- **I4 refuted on G2 and G3.** A UI control with no file does not survive a
  restart and cannot reach a running loop — the exact property `#426`
  established and `#445`/`#342` rely on. Conversation-held (or session-held)
  posture is what tonight's *"lackadaisical but delegating"* was forced into and
  what the posture file exists to end. With no file there is also no lint
  closed-set and no events line (G3).
- **I5 refuted on G3, by standing ruling.** The sibling-vs-widen choice was
  **already ruled for the other four axes**: `#445` widened posture and rejected
  a sibling for asking; `#342` widened posture and rejected a sibling for
  delivery; `attention-modes.md` records the same arguments. A sibling touches
  no closed set but **splits one dial across two files** and fragments the
  control surface. The sibling is refuted by that ruling, not re-litigated here.

### Survivor

**I1 — a fifth posture axis.** Exactly one All-✔ idea. It is the additive,
orthogonal, tick-re-read, closed-set, lint-guarded form — the same shape
`delivery` landed in and `autonomy` is designed against — and it is what
`hierarchical` always wanted to be once `#443` unbundled run-mode. **What
survives is the *integration shape* (a fifth axis); the closed set, the name,
the referent itself, and the relationship to `hierarchical` are genuine forks
for him** — the open calls below. There is no third state between "settled by
the IGC" (the shape is a fifth axis) and "escalated with a rec" (Q1–Q3).

## The settled shape (what the IGC fixes)

If he rules Reading A (orchestration mode), the integration is **a fifth
posture axis in `.dreamwork/posture`**, reusing `POST /posture`, the shared 10s
arm, and the one-`posture via watch`-line ceremony — *not* a second route, *not*
a sibling file, *not* a run-mode value. Absent → today (the coordinator
implements inline), so a pre-axis posture file is byte-identical in effect — the
same absent-derives-today property `delivery`/`autonomy` hold, and the property
that makes adding the axis a no-op until he sets it. What lands in the
implementation commit (named, **not** authorised here) is the same four touches
`delivery`/`autonomy` take: `POSTURE_AXES` gains the axis; a stop-tuple sits
beside the others; `check_posture`'s axis-generic closed-set branch enforces it
for free; `parse_posture_text`/`resolve_posture`/`write_posture`/`posture_line`
and the dashboard picker gain one control. **No `Migration:` trailer** —
`.dreamwork/posture` is a gitignored sibling that already exists, and adding an
axis to a file re-read every tick is covered by `#426`, not a migration.

## Open calls for him — each with a rec, never picked for him

**`Sub-decisions:` `Q1`, `Q2`, `Q3`**

- **Q1 — the referent: orchestration MODE (solo/fleet) vs orchestrator IDENTITY
  (which model/session).** The only call that changes the *kind* of thing being
  integrated. **Rec: mode (Reading A).** Identity (Reading B) is a
  dispatch/provenance fact the dispatcher already owns (the alias, per
  `ccc-runner-routing.md`/`handoffs.md` provenance notice); it is not an
  operating dial he sets in a posture picker, and a posture file is the wrong
  home for "who was dispatched." If he means identity, the integration is
  different and this doc's IGC does not apply — say so and the design restarts
  against the provenance model rather than the posture axes.
- **Q2 — the closed set and the name (if mode).** **Rec: a binary axis
  `hands-on` | `orchestrator`, absent → `hands-on` (today).** `hands-on` = the
  coordinator implements increments itself (today; it may *also* delegate, per
  the delegation number). `orchestrator` = the coordinator implements **nothing**
  inline — every increment is dispatched and the coordinator's role is
  adjudication/review/ledger only (the coordinator-only-loop mode). Binary
  because the differentiating decision is exactly *"does the coordinator
  implement or not"*; *"solo vs fleet"* is already `delegation`'s job
  (`delegation: 0` = solo), so a third "solo" stop would duplicate delegation
  (the G4 the IGC guards). Name is his word for the new stop (`orchestrator`);
  the other stop's label is open (`hands-on` / `implementer` / `inline`) and
  rec is `hands-on`. A three-stop alternative (`solo | mixed | orchestrator`) is
  available if he wants "mixed" nameable, but rec is binary as the honest shape.
- **Q3 — relationship to the planned `hierarchical` run-mode (#264/#288).**
  **Rec: land the axis; do NOT enable `hierarchical` as a run-mode value.** The
  `orchestration: orchestrator` axis *is* the posture-layer dial `hierarchical`
  always gestured at; `hierarchical` can stay disabled, or be reframed later as
  *"the run-mode that derives `orchestration: orchestrator` + a high delegation
  number"* (a convenience bundle, not a fourth decision smuggled into run-mode).
  Enabling `hierarchical`-the-value re-conflates (the I3 refutation) and still
  needs #264/#288; the axis needs neither. The fork: he may want `hierarchical`
  as a named one-click bundle anyway, in which case both land and the axis is
  what the bundle sets.

The journal-folder / dashboard-control rendering is an implementation detail
folded under Q2, not its own call.

## Draft `questions.md` entry (DRAFT — coordinator-owned; this lane does not edit questions.md)

> **P2 · 2026-07-30 — #510: an 'Orchestrator' option in Posture — three calls, after an IGC over how it integrates.**
> **Sub-decisions:** `Q1`, `Q2`, `Q3`
>
> Design: `.dreamwork/docs/plans/orchestrator-posture.md` (design only; no code
> authorised). The IGC (I1–I5 × G1–G5) settles *how* it integrates — a **fifth
> posture axis**, not a fold onto delegation, not the `hierarchical` run-mode
> value, not a control-only toggle, not a sibling file. What it does not settle
> is *what* "Orchestrator" is, and that is the first call.
>
> **`Q1` — the referent.** Do you mean an orchestration **mode** (the coordinator
> dispatches + reviews and implements nothing inline — the coordinator-only-loop
> mode from `dogfood-orchestration.md`), or the orchestrator's **identity**
> (which model/session runs the loop)? **rec: mode.** Identity is a
> dispatch/provenance fact you already set by which session you run / which alias
> you dispatch (recorded at dispatch, `ccc-runner-routing.md`), not a posture
> dial; a posture file is the wrong home for "who was dispatched." If you mean
> identity, say so — the integration is different and the IGC above does not
> apply.
>
> **`Q2` — the closed set and name (if mode).** **rec: a binary axis
> `hands-on` | `orchestrator`, absent → `hands-on` (today).** `orchestrator` =
> coordinator implements nothing, only dispatches/reviews/ledger; `hands-on` =
> today (coordinator implements inline, may also delegate). Binary because
> solo-vs-fleet is already `delegation`'s job. The other stop's label is open
> (`hands-on` rec; `implementer`/`inline` are alternatives); a three-stop
> `solo | mixed | orchestrator` is available if you want "mixed" nameable.
>
> **`Q3` — the `hierarchical` run-mode (#264/#288).** **rec: land the axis, do
> not enable `hierarchical` as a run-mode value.** The axis is the dial
> `hierarchical` always wanted to be; enabling the run-mode value re-bundles
> decisions (`#443`) and still needs #264/#288. Alternative: land both, with the
> axis as what a later `hierarchical` bundle sets.
>
> **If you say nothing:** nothing is built — the design authorises no code, and
> the recs stand as the defaults when the implementation split is planned.
> Accepted answers: `rec` (takes all three) · per-question (`Q1: …`) · free text.

## What this design does NOT authorise

A design gets read as a licence. It is not one. This doc authorises **no code.**
Matched to house style (`delivery-modes.md`, `attention-modes.md`,
`posture-autonomy-axis.md`):

- **no `watch.py` change** — not the axis plumbing, not `POST /posture`, not the
  dashboard picker, not the events-line field.
- **no `lint.py` change** — not a `POSTURE_AXES` widening, not a stop-tuple, not
  a `derive_posture` row. Those land in `#510`'s implementation increment with
  their own red-first checks.
- **no `file-formats.md` change** — the fifth axis row, derivation map column
  and permission table land in the implementation commit, not here.
- **no `.dreamwork/posture` change** — his live file is untouched.
- **no consumer** — an `orchestration` axis has no reader until a future
  coordinator implements "coordinator-implements-nothing" behaviour; designing
  the axis does not build the behaviour. Stating it plainly: setting
  `orchestration: orchestrator` today is **inert** until a consumer reads it —
  the same forward-looking-dial shape `delivery`/`autonomy` hold before their
  consumers land.
- **no migration, no deployment, no change to a running loop or live target.**

## Pushback on his framing

Two things worth his eye, stated plainly because the brief asked for them:

1. **"Doesn't strictly match anything we already have" is half right.** It does
   not match `delegation` (a number about fleet size) — that is correct, and the
   IGC's G4/G1 turn on it. But the *fleet-orchestration concept* he is reaching
   for already exists, teed up and disabled, as the `hierarchical` run-mode value
   (`watch.py:343`, gated on #264/#288). So the integration question is less
   "invent where it goes" and more "it wants to be a posture axis, not the
   run-mode value it is currently parked as" — because run-mode *bundles*
   decisions (`#443`), and a posture axis is the unbundled form. Naming this so
   he can choose between "land the axis" (rec) and "finally enable
   `hierarchical`" is Q3.
2. **Identity (Reading B) is probably not what he wants *in posture*, even though
   his "opus 5 claude orchestrator" phrasing points at it.** The loop's
   model-dependent behaviour is real, but it is a dispatch/routing/capability
   fact (`dogfood-orchestration.md`'s whole runner comparison), already recorded
   truthfully at dispatch. A posture picker for "which model orchestrates" would
   duplicate the dispatch act and mis-categorise provenance as operating state.
   If he *does* want the dashboard to show/steer "the orchestrator is X," that is
   a status/routing surface, not a posture axis — and it is worth saying so
   before building the wrong thing. Hence Q1, with a rec against identity.

## Verification — how each load-bearing claim would be checked

House rule: a new check is not verification until it has been red, and the proof
must reach the real production line. This section names, for each claim the
implementation increment would rest on, how it is checked and which line could
be red.

- **Orchestration is orthogonal to delegation.** Check: set `delegation: 4` +
  `orchestration: orchestrator`; assert the coordinator refuses to implement an
  increment inline while the delegation target is honoured (a fleet of ~4 is
  aimed for). **Red:** make the `orchestrator` consumer ignore the axis and
  implement inline anyway, and watch the behaviour collapse to today's. (Line:
  the consumer that reads `resolve_posture(target)["orchestration"]`.)
  **Structural-red guard:** the test must call the real `resolve_posture`, not a
  fixture that hard-codes `orchestrator`.
- **Absent ⇒ today ⇒ the coordinator implements inline.** Check: with no axis in
  `.dreamwork/posture`, assert `resolve_posture(target)["orchestration"]` derives
  to the `hands-on` default and the consumer does not fire. **Red:** make the
  derivation default `orchestrator` and watch a no-axis target gain a behaviour
  it never asked for. (Line: the `orchestration` entry `derive_posture` returns —
  `lint.py:2286`.)
- **A closed set fails loud.** Check: a `.dreamwork/posture` with
  `orchestration: turbo` ERRORs in `check_posture`. **Red:** make the check
  accept an out-of-set value and watch an invalid posture lint clean. (Line: the
  axis-generic closed-set branch at `lint.py:2386`–`2398`, now covering the new
  axis.)
- **The axis round-trips through POST /posture.** Check: POST a five-axis body;
  assert `.dreamwork/posture` holds all five lines and the events line carries
  the field. **Red:** drop the axis from `write_posture` and watch the file lose
  the line / the event omit it. (Line: `write_posture` and `posture_line` in
  `watch.py`.)

---

--- SUMMARY ---

- **What this is:** the `#510` design — an 'Orchestrator' option in Posture,
  IGC'd over how to integrate it. **Design only; authorises no code.**

- **The referent, investigated:** "Orchestrator" is his word for the
  coordinator/main-dreamer role (`questions.md:1119`). Two live readings: **A —
  orchestration *mode*** (coordinator implements nothing, only dispatches +
  reviews; the coordinator-only-loop mode `dogfood-orchestration.md` records) —
  designed against; **B — orchestrator *identity*** (which model/session runs the
  loop) — pushed back on as a dispatch/provenance fact mis-categorised as posture,
  escalated as Q1 with a rec against. A third (a persona selector) is rejected.

- **The IGC headline:** **one survivor — a fifth posture axis.** Fold-onto-
  delegation (I2) is refuted on independence + overload; the `hierarchical`
  run-mode value (I3) is refuted on re-bundling (`#443`) + preemption; control-
  only (I4) on no restart-survival; sibling file (I5) by the standing #445/#342
  widen-not-sibling ruling. The integration shape is settled; the referent, the
  closed set/name, and the `hierarchical` relationship are genuine forks.

- **Open calls (recs):** Q1 mode over identity · Q2 binary `hands-on` |
  `orchestrator`, absent → `hands-on` · Q3 land the axis, do not enable
  `hierarchical`.

- **Pushback:** "doesn't match anything" is half-right (it matches `delegation`
  as a *neighbor*, and the fleet concept is the parked `hierarchical` run-mode);
  and identity-in-posture is probably the wrong surface even though his phrasing
  points at it.

- **Factual claims checked against the repo:** posture axes/closed-sets/
  `derive_posture` (`lint.py:2230`–`2398`, `.dreamwork/posture`);
  `delegation`-is-a-number (`lint.py:2230`, his `#445` Q3);
  `RUN_MODES_PLANNED`/`hierarchical`-disabled (`watch.py:343`, `:363`);
  the orchestrator-role material (`dogfood-orchestration.md`);
  his "opus 5 claude orchestrator" wording (`questions.md:1119`);
  provenance-owned-at-dispatch (`handoffs.md` notice, `ccc-runner-routing.md`).
