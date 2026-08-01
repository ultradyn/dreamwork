# Posture `autonomy` axis — what the loop may do unasked (#493)

> **DESIGN ONLY. No code.** This document changes no `.py` file, no
> `file-formats.md`, no `lint.py`, no `watch.py`, no running loop. It is
> prose plus measured facts plus one settled closed set, written to be
> ruled on or built. The autonomy axis does not exist yet; this is the
> design for it. It states, in its own §"What this does NOT authorise",
> every implementation surface it forbids.

Origin: **his #287 rulings** (OQ4/OQ5, 2026-07-30 00:20, via `questions.md`).
The bridge spec (`.dreamwork/docs/plans/matt-pocock-skills-bridge.md`, §14)
parked two gates on "an autonomy level to posture" rather than resolving them
as flat defaults, and filed this task. This doc is that axis.

**The shape is settled by his word "autonomy level":** a fourth posture axis in
`.dreamwork/posture`, closed set, absent = today's behaviour — the same physical
and discipline contract `pace`/`asking`/`delegation` already hold (#445). What
follows designs that axis against the two rulings, the scope gate, and the
existing posture machinery, measured read-only.

---

## Authority and what this builds on

His #287 OQ4 ruling, verbatim (the `Answer` at `questions.md:88-100`):

> *"4. in this case I think some options would be good, like adding an autonomy
> level to posture for maintenance (which is probably a good thing for us to do
> anyway; pls add a task)"*

and OQ5, verbatim:

> *"5. probably an autonomy level thing."*

The fold (`questions.md:62-64`) records them as the contract this axis owes:

> *"**OQ4 an autonomy level on posture** — autonomous dispatch of suite tools
> is gated on it; task filed. **OQ5 probably the same autonomy level** —
> self-filing becomes a steer the autonomy level gates rather than a flat no."*

So the axis gates **two agent-initiated surfaces** the rulings named, and his
framing — *"for maintenance"* — sets the middle stop's name and intent. The two
surfaces, concretely (bridge spec §7, §11, §14):

- **OQ4 — autonomous dispatch of suite tools.** The loop may fire
  `research` / `code-review` / `prototype` as subagents itself, rather than
  only when a human invokes them. Today: human-invoked only (the spec's floor
  proposes read-only dispatch, but his ruling parks even that behind this axis;
  until the axis exists, *"the default stands: human-invoked only"* — §14).
- **OQ5 — self-filing of loop-generated `to-spec` / `to-tickets` output.** The
  loop may put its own generated spec/ticket output into the ledger without a
  human steer. Today: a human steer by default (`file-as-task` is an elevated
  DREAMWORK.md authority line, silence = the floor).

Both are **agent-initiated surfaces** — exactly the class the scope gate
governs (`SKILL.md:736`). The axis does not invent a new category; it is the
dial his rulings asked for on a category that already has a gate.

---

## Two load-bearing facts, measured READ-ONLY

All measurements taken against the live checkout (`24d560f3`, 2026-07-30):
`lint.py`, `watch.py`, `file-formats.md`, `SKILL.md`. The posture file itself
(`.dreamwork/posture`) is his live file — read-only, and the contract in
`file-formats.md` §1124 is cited in preference to any live value.

### 1 · The posture axis seam already exists, and a fourth axis is an additive row — not a new mechanism

`.dreamwork/posture` is a sibling to `run-mode` (file-formats.md:1124,
file-formats.md:377): gitignored, machine-local, re-read every tick (#426),
one `axis: value` per line, `#` comments allowed, **absent → derived from
run-mode** so a loop that has not been restarted behaves identically. Three
axes today, and the discipline that guards them is uniform:

- **The closed set is the single source in `lint.py`.** `POSTURE_AXES =
  ("pace", "asking", "delegation")` (`lint.py:2248`); `POSTURE_STOPS_PACE`
  (`lint.py:2235`); `POSTURE_STOPS_ASKING` (`lint.py:2244`). `check_posture`
  (`lint.py:2329`) reads `POSTURE_AXES` to refuse an unknown axis with a WARN,
  and ERRORs on a closed-set value outside its stops — *"a closed set fails
  loud, like run-mode"* (`lint.py:2388`). Delegation carries a number that
  steers, never gates (WARN on nonsense, never on fleet size).
- **`watch.py` imports those sets, never restates them.** `_posture_vocab()`
  (`watch.py:397`) lazily imports `lint`'s closed sets; `parse_posture_text`
  (`watch.py`) keeps only axes whose values are in the stops;
  `resolve_posture` (`watch.py`) overlays a present file on the
  run-mode derivation; `write_posture` (`watch.py`) writes the triple
  `pace: …\nasking: …\ndelegation: …\n`. The route is one entry,
  `"/posture": _handle_posture` (`watch.py`), behind the shared 10s arm,
  emitting one `posture via watch: …` line (`posture_line`, `watch.py`)
  only on a real change.

**A fourth axis `autonomy` is therefore an additive row through every one of
those sites** — `POSTURE_AXES` gains it; a `POSTURE_STOPS_AUTONOMY` sits beside
the other two stop-tuples; `check_posture` ERRORs on an out-of-set value for
free (its closed-set branch is axis-generic); `parse_posture_text` /
`resolve_posture` / `write_posture` gain one field; the route, the arm, the
events line, and the dashboard picker (`posturePicker`, `watch.py`) gain
one control. Nothing here is new machinery; it is the same shape `delivery`
(#342, ruled the same hour) will take. This is measured, not assumed: the
closed-set enforcement at `lint.py:2386-2398` is written per-axis against the
imported tuples, so a fourth tuple is enforced by the existing code path.

### 2 · The axis gates surfaces the scope gate already governs — it must compose, not replace

The scope gate (`SKILL.md:736-748`) is the authority this axis relaxes, and
the line between them is load-bearing:

> *"Agent-initiated work that adds new surface area (a new file, section, or
> feature) or breaks the size norms has to state its chain out loud first …
> Human-initiated steers are never gated. Defaults and silence may resolve
> *how* or *when* for already-authorized work — never *whether* to add new
> surface; parked scope questions stay parked until answered."*

So the scope gate decides **whether a chain can be named** (the work is
in-scope); it never relaxes. The autonomy axis decides **whether the loop may
proceed without a human steer once the chain is named**. The composition rule,
stated once because it is the whole contract:

> **Autonomy relaxes the human-steer requirement. It never relaxes the chain
> requirement.** A surface the scope gate parks (no chain names it) stays
> parked at every autonomy level; a surface the gate chains may, at higher
> autonomy, proceed without waiting for him to say go.

This is why the axis is *additive over today*, not a clamp below it (see
§"What each level gates"): every level including the absent default preserves
the loop's already-authorised behaviour (the maintenance rotation, `SKILL.md`
selection step 4; `origin: loop` idea-filing), because gating that would be the
silent behaviour change the absent-derives-today rule exists to prevent
(`derive_posture`, `lint.py:2276`, derives today's posture for every run-mode).
The axis only permits surfaces that are **gated today and not yet authorised** —
which is exactly the suite's two surfaces, since the suite is not installed.

---

## The contract

### Axis name and closed set — `autonomy`: `off` | `maintenance` | `full`

His word, both rulings: *"an autonomy level."* Three stops, ordered by how much
agent-initiated surface the loop may **do unasked**, each defined by what it
**permits** (one line each):

| level | what it permits the loop to do without a human steer |
|---|---|
| **`off`** | **nothing new.** Agent-initiated surfaces need a human steer; autonomous suite-tool dispatch is flat-off and loop-generated `to-spec`/`to-tickets` output is not self-filed. This is today's behaviour. |
| **`maintenance`** | **investigate, don't produce.** The loop may autonomously dispatch **read-only** suite tools (`research`, `code-review`) whose output feeds tasks/questions, and record what they surface. No autonomous producing tools (`prototype`); no autonomous self-filing of generated `to-spec`/`to-tickets` output. |
| **`full`** | **produce.** The loop may additionally dispatch **producing** suite tools (`prototype`) and self-file its own generated `to-spec`/`to-tickets` output — autonomous scope expansion, still inside the scope gate's chain discipline and the increment/commit/verify discipline. |

**Absent → `off` → today.** A posture file that predates the axis (or omits the
line) behaves identically to today: no autonomous dispatch, no self-filing. This
mirrors the `delivery` precedent (absent = today's behaviour) and is the
load-bearing property — `derive_posture` (`lint.py:2276`) derives `autonomy:
"off"` for every run-mode, so adding the axis changes nothing until a human
sets it. A pre-axis posture file is byte-identical in effect.

**The differentiating goal between `maintenance` and `full` is one thing: does
the autonomous act produce new work-surface (code, feature specs, feature
tickets)?** `maintenance` permits only non-producing investigation and
recording; `full` permits producing and feature-scope self-filing. A single
decisive differentiator is the house-style discipline (`igc-method.md`: the
differentiating goal, never a score), and "produces new surface" is exactly the
property the scope gate keys on — so the level cut and the gate's vocabulary
agree by construction.

**`off` / `maintenance` / `full` are his vocabulary.** *"off"*, *"maintenance"*
(*"an autonomy level to posture for maintenance"*), and *"full"* (his
*"full-ish"* habit from #445/#295) are the words he used; the closed set uses
them rather than inventing synonyms.

**One collision, named and dissolved (the #367 discipline).** `maintenance` is
already a word in this repo — the `maintenance` command (`SKILL.md:643`) and the
*maintenance rotation* (selection step 4, `SKILL.md:204`). The posture level is
neither: the rotation is the *schedule* (when the loop grooms); the level is the
*permission dial* (how far the loop may reach during it). Naming the collision
dissolves it the way `file-formats.md` §"essential marks" dissolved the
`mark`/`mark` collision — a reader who meets `autonomy: maintenance` reads
"the loop may maintain-and-investigate unasked," not "the rotation is gated."
The rotation runs at every level; the level permits the rotation to be richer.

### What each level gates — the enumerated surfaces, composed with the scope gate

The axis gates the **agent-initiated surfaces the rulings named**, and only
those — it does not reach backward into already-authorised loop work:

1. **OQ4 — suite-tool dispatch.** `off`: human-invoked only (today).
   `maintenance`: the loop may dispatch `research` / `code-review` (read-only;
   output feeds tasks/questions, never bypasses — bridge §6/§11). `full`: + the
   loop may dispatch `prototype` (producing). Dispatch is still a subagent
   through the existing handshake (`subagent-protocols`), still obeys worktree
   ownership (#405) and disjointness; autonomy only removes the steer.
2. **OQ5 — self-filing of generated output.** `off`: a human steer files
   loop-generated `to-spec` / `to-tickets` output (today; the bridge's
   `file-as-task` authority line is the floor). `maintenance`: not permitted
   (generating a spec/ticket is producing work-surface). `full`: the loop may
   self-file its generated output through `dev/ledger.py file` (never the
   ledger directly — bridge C1), as `origin: loop`, still naming its chain.
3. **His "maintenance" framing.** The `maintenance` level is the level at which
   the loop can **self-serve the maintenance rotation with suite tools** —
   dispatch a read-only `research`/`code-review` to investigate friction, record
   the finding — without a steer. That is the literal reading of *"an autonomy
   level to posture for maintenance."* The rotation itself (grooming, goal
   alignment, self-review, docs freshness — `SKILL.md:204-213`) is core
   authorised work and runs at **every** level; the axis does not gate it.

**What the axis does NOT gate, stated because absence is load-bearing:**

- **The loop's existing autonomous filing.** Today the loop files `origin: loop`
  tasks from ideas, dogfood friction and maintenance findings without a steer
  (`SKILL.md` selection steps 1-2; the `add idea` command). That is
  already-authorised work; the axis does not reach it. `autonomy: off` does NOT
  mean "stop filing ideas" — it means "no NEW suite surfaces." Gating existing
  filing would be the silent behaviour change absent-derives-today forbids, and
  would duplicate `asking` / `pace` (a sub-today clamp is a different feature,
  and largely redundant — see §"Open calls").
- **Human-initiated steers.** *"Human-initiated steers are never gated"*
  (`SKILL.md:744`) — a `do now`, a typed suite-skill name, a `file-as-task`
  grant he gives: none of these consult the autonomy axis. The axis only governs
  what the loop initiates itself.
- **Scope the gate parked.** A surface the scope gate cannot chain stays parked
  at every level (the composition rule above). Autonomy never auto-grants scope.

**Composition with the bridge's authority lines (§7).** The bridge's elevated
lines (`file-as-task`, `dispatch-review`, `dispatch-prototype`) are the
**per-target grant** (DREAMWORK.md); the autonomy axis is the **per-host dial**
(posture). They compose multiplicatively: a bridge with a `file-as-task` line
has the *ability*; `autonomy: full` is what lets the loop *exercise* it without
a steer. At `autonomy: off`, even a granted line still asks first. This is the
same dial-vs-grant split `delivery` (#342 Q3) made for plugin urgency: the
loop gates; the line is input.

### Composition with the existing axes — orthogonality, and one interaction

Four posture axes once `delivery` lands, each answering a different question:

| axis | answers | today's default |
|---|---|---|
| `pace` | how **often** the loop acts | derived from run-mode |
| `asking` | how **much surfaces** to the human | derived = `ask` |
| `delegation` | **through whom** the loop works (own / subagents) | derived |
| `delivery` (#342, ruled) | **when** he is interrupted (instant / batched) | `instant` |
| **`autonomy`** (this doc) | **what the loop may do unasked** | **`off`** |

The orthogonality argument is one sentence each: `pace` is cadence, `asking` is
visibility, `delegation` is channel, `delivery` is interrupt-timing, `autonomy`
is permission. None subsumes another — a loop can be `pace: hot` + `autonomy:
off` (acts fast but only on steers), or `pace: idle` + `autonomy: full` (acts
rarely but unsteered when it does). The five are independent dials; their
product is the loop's operating posture.

**One real interaction, and it is the point.** `asking` and `autonomy` move on
opposite ends of one dial in practice: `asking: ask` surfaces every material
choice as a question (maximally observed); `autonomy: full` lets the loop act
without surfacing (minimally observed). Their **product** is how autonomous the
loop is in lived experience:

- `asking: ask` + `autonomy: off` — today: the loop surfaces and waits.
- `asking: auto` + `autonomy: full` — full autonomous operation: acts, never
  surfaces, journals silently. This is a real state the dials can express, and
  it is the state worth a human's deliberate setting.

They are still **orthogonal** — `asking: inform` + `autonomy: full` is coherent
(acts unsteered but documents each act), and so is `asking: ask` + `autonomy:
maintenance` (investigates unsteered, but escalates every producing choice).
No level of one forces a level of the other; the dashboard control sets them
independently, like `pace` and `delegation` already are.

**Does `delivery: batched` + high autonomy mean the loop does more unobserved?**
Yes, and that is the human choosing it, not a defect. `batched` means the loop
is not woken by low-urgency items (`delivery-modes.md`); with `autonomy:
maintenance` it can self-serve read-only investigations between his glances, so
more happens per glance. The composition is sound because each axis is
individually honest: `batched` never hides a durable receipt (the journal
cursor drains it on the next tick), and `autonomy` never relaxes the chain.
"More unobserved" is the explicit product of two dials he set, not a hole.

### Where it lives — a fourth posture axis, same shape as `delivery`

**A fourth axis `autonomy` in `.dreamwork/posture`**, closed set
`off | maintenance | full`, absent → `off` → today. It reuses `POST /posture`
(`watch.py`), the shared 10s arm, and the one-`posture via watch`-line
ceremony — *not* a second route, *not* a sibling file. The sibling-vs-widen
choice was already ruled for the other closed-set axes (#445: widen `posture`,
reject a sibling), and the same arguments carry here: a widening keeps one
control surface and lets the closed-set discipline already guarding
`pace`/`asking` guard this for free; a sibling touches no closed set but splits
one dial across two files.
`#650` found the boundary: a free-text field inherits no closed-set guard, so
this ruling does not decide its storage shape.

**What lands in the implementation commit (named, not authorised here):**
the same four touches `delivery` will take, in the same shape —

- **`lint.py`** — `POSTURE_AXES` gains `"autonomy"` (`lint.py:2248`); a new
  `POSTURE_STOPS_AUTONOMY = ("off", "maintenance", "full")` beside the other
  stop-tuples; `check_posture`'s closed-set branch enforces it for free (it is
  axis-generic at `lint.py:2386-2398`); `derive_posture` (`lint.py:2276`) and
  `RUN_MODE_TO_POSTURE` (`lint.py:2269`) derive `autonomy: "off"` for every
  run-mode.
- **`watch.py`** — `parse_posture_text` (`watch.py`),
  `read_posture_file`, `resolve_posture` (`watch.py`),
  `write_posture` (`watch.py`) gain the axis; `write_posture` writes the
  fourth line; `posture_line` (`watch.py`) emits `autonomy=…`;
  `_handle_posture` (`watch.py`) validates against the imported closed
  set; the dashboard picker (`posturePicker`, `watch.py`; controls at
  `watch.py`) gains one control.
- **`file-formats.md` §1124** — the posture section gains the fourth axis:
  one row in the shape table, the derivation map gains an `autonomy: off`
  column, and a one-line-per-level permission table (the table above).
- **No `Migration:` trailer** — `.dreamwork/posture` is a gitignored sibling
  that already exists; adding an axis to a file a loop re-reads every tick is
  covered by the #426 per-tick re-read, not a migration. (A notice under #458 is
  not needed: nothing an existing install *must do* changes, because absent =
  today.)

**The axis has no consumer until the bridge (#287) lands.** Today nothing reads
`autonomy` — the suite is not installed, no suite tool is dispatched, no
generated output is self-filed. The axis is a forward-looking dial the rulings
parked two gates on, exactly as `delivery` was a dial before its wake-routing
consumer landed. Stating this plainly: **setting `autonomy: maintenance` today
is inert** until a consumer (the bridge's dispatch decision, its filing
decision) reads `resolve_posture(target)["autonomy"]`. That is not a defect;
it is *"probably a good thing for us to do anyway"* — the infrastructure his
rulings asked for, ready for the surfaces they gate.

---

## What this design does NOT authorise

A design gets read as a licence. It is not one. This doc is the deliverable; it
authorises **no code.** Specifically, it does not authorise:

- **any `lint.py` change** — not `POSTURE_STOPS_AUTONOMY`, not the
  `POSTURE_AXES` widening, not a `derive_posture` derivation row. Those land in
  `#493`'s implementation increment, with their own red-first checks.
- **any `watch.py` change** — not the parse/resolve/write fourth field, not the
  `_handle_posture` validation, not the dashboard picker control, not the
  events-line field.
- **any `file-formats.md` change** — the fourth axis row, the derivation map
  column, and the permission table land in the implementation commit, not here.
- **any consumer** — the dispatch gate and the self-file gate the axis feeds do
  not exist; designing the axis does not build them. They arrive with the
  bridge (#287), and each is its own grant.
- **any change to the scope gate** — the axis *composes* with the gate; it does
  not edit `SKILL.md:736` or relax the chain requirement. That is the contract,
  not a deferred item.
- **no migration, no deployment, no change to a running loop or live target.**

---

## Open calls — none

His standing rule (his #367 amendment, folded to `DREAMWORK.md`): *if every call
has one clearly-superior answer, there are no open questions.* Every fork this
axis raises has one clearly-superior answer, so there are no open calls — the
work is shown below so the next reader can see each was decided, not skipped.

- **Axis name** — settled: `autonomy`. His word, both rulings. No fork.
- **Closed set, three stops** — settled: `off | maintenance | full`. A two-stop
  `off | full` is too coarse for his *"for maintenance"* intent (it erases the
  middle where the loop investigates but does not produce); a four-stop set
  adds a stop with no differentiating goal. Three is the honest shape, and his
  vocabulary names all three.
- **The `maintenance` / `full` cut** — settled: *produces new work-surface.*
  Read-only investigation vs producing/self-filing is the risk gradient (a
  read-only dispatch is reversible — its output feeds questions/tasks; a
  prototype or a self-filed spec mutates the tree/ledger), and it is the
  property the scope gate already keys on. No fork.
- **Scope: suite surfaces only, no retro-gating** — settled: the axis is
  *additive over today*. Gating the loop's existing `origin: loop` filing would
  be the silent behaviour change absent-derives-today exists to prevent, and a
  sub-today clamp duplicates `pace`/`asking` (a loop that files nothing
  autonomously is `pace: idle` selecting only on steers — already expressible).
  His rulings are additive (*"adding an autonomy level"*), so the axis adds
  permissions; it does not subtract today's.
- **Composition with the scope gate** — settled: *autonomy relaxes the steer,
  never the chain.* The one sentence the whole design turns on; no fork.
- **The `maintenance` naming collision** — settled (named, not avoided): the
  level vs the rotation is dissolved by definition, the #367 discipline. A
  rename (`assisted` / `investigate`) would discard his vocabulary to avoid a
  collision that a one-line definition already closes; the house style prefers
  his word plus a named collision over an invented synonym.

The one thing that is *arguably* his and is recorded as considered-not-open:
**whether he wants a sub-today `steered` level that clamps existing filing.**
Rec (settled): no — it duplicates `pace`/`asking` and breaks absent=today. If he
disagrees, it is a one-stop addition to the closed set and a separate question,
not a change to the three designed here.

---

## Verification — how each claim would be checked

House rule: a new check is not verification until it has been red, and a green
red-run is a finding, never a relief. This section names, for each load-bearing
claim, how the implementation increment would check it and which line could be
red.

- **Absent posture ⇒ `autonomy: off` ⇒ today's behaviour.** Check: with no
  `.dreamwork/posture`, assert `resolve_posture(target)["autonomy"] == "off"`
  and that no suite dispatch/filing consumer fires. **Red:** make the derivation
  default `"maintenance"` and watch a no-posture target gain a permission it
  never asked for. (Production line: the `autonomy` entry `derive_posture`
  returns — `lint.py:2276`.) **Structural-red guard:** the test must call the
  real `derive_posture`, not a fixture that hard-codes `off`.
- **A closed set fails loud.** Check: a `.dreamwork/posture` with
  `autonomy: turbo` ERRORs in `check_posture`. **Red:** make the check accept an
  out-of-set value (or spell the set wrong) and watch an invalid posture lint
  clean. (Production line: the closed-set branch at `lint.py:2386-2398`, now
  covering `autonomy`.)
- **The axis is additive — it never gates existing filing.** Check: at
  `autonomy: off`, the loop still files an `origin: loop` task from an idea (via
  the existing selection/command path) and the file/ledger act succeeds. **Red:**
  make an `off`-level consumer refuse an `origin: loop` file and watch the
  existing behaviour regress. (Production line: the dispatch/filing gate the
  bridge adds — it must read `autonomy` only for *suite* surfaces, never for
  `origin: loop` filing.) **The precondition the check depends on:** assert the
  fixture's idea-filing path is the real `dev/ledger.py file` verb, not a mock
  that bypasses the gate under test.
- **Autonomy composes with, not over, the scope gate.** Check: at
  `autonomy: full`, a surface whose chain the scope gate cannot name is still
  parked (not dispatched/filed). **Red:** make the `full` consumer skip the
  chain check and watch an un-chained surface proceed. (Production line: the
  consumer's chain check — it must run before the autonomy permit, not after.)
- **The fourth axis round-trips through POST /posture.** Check: POST a
  four-axis body; assert `.dreamwork/posture` holds all four lines and the
  events line carries `autonomy=…`. **Red:** drop the axis from `write_posture`
  and watch the file lose the line / the event omit it. (Production line:
  `write_posture` at `watch.py` and `posture_line` at `watch.py`.)

---

## Primary sources reached

- **his #287 rulings** — `questions.md:56-100` (the `Answer` at 00:20); OQ4 and
  OQ5 verbatim above. The fold (`questions.md:62-64`) states the contract this
  axis owes.
- **the bridge spec** — `.dreamwork/docs/plans/matt-pocock-skills-bridge.md`:
  §7 (authority model — `file-as-task` / `dispatch-review` / `dispatch-prototype`
  elevated lines); §11 (invocation truth — read-only vs producing tools); §14
  (OQ4/OQ5 ruled onto *"an autonomy level on posture"*, filed as `#493`); P4
  (the scope gate maps the suite's roles; tools that *produce* are gated, tools
  that *decide with him* are HITL).
- **the posture contract** — `file-formats.md:1124` (`.dreamwork/posture`,
  three-axis override of run-mode) and `file-formats.md:377` (the shape row).
  Absent → derived from run-mode; closed sets fail loud; machine-local /
  gitignored; re-read every tick (#426).
- **the posture machinery** — `lint.py`: `POSTURE_STOPS_PACE` (`:2235`),
  `POSTURE_STOPS_ASKING` (`:2244`), `POSTURE_AXES` (`:2248`),
  `RUN_MODE_TO_POSTURE` (`:2269`), `derive_posture` (`:2276`),
  `check_posture` (`:2329`, closed-set branch `:2386-2398`). `watch.py`:
  `_posture_vocab` (`:397`), `parse_posture_text` (`:12967`),
  `resolve_posture` (`:13009`), `write_posture` (`:13040`),
  `posture_line` (`:13061`), `_handle_posture` (`:14066`), route
  `"/posture"` (`:14170`), picker `posturePicker` (`:3733`).
- **the scope gate** — `SKILL.md:736-748` (*"name the chain"*; human-initiated
  steers never gated; parked scope stays parked). Referenced at `SKILL.md:181`,
  `SKILL.md:230`, `SKILL.md:588`.
- **the maintenance rotation** — `SKILL.md:204-213` (selection step 4) and the
  `maintenance` command (`SKILL.md:643`): the schedule the `maintenance` level
  augments, not the thing the level gates.
- **house style** — `delivery-modes.md` (the same-hour #342 ruling: a posture
  axis, absent = today, reusing POST /posture + the 10s arm; the dial-vs-grant
  split for plugin urgency) and `cli-warning-layer.md` (measured facts first,
  the contract, what it does NOT authorise, open calls only where genuinely his,
  verification section). This doc follows both.
