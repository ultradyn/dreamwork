# Lane report — #721 PASS 2: the widened-form ids (`Merge #N` / bare `#N`)

**Verdict: DONE — report only, no folds executed.** Six ids triaged by content
(the #706 standard: the content on master at this line, never the subject).
Pass 1 is the method (`lane-721-report.md`); this continues it on the
lower-confidence widened-form half.

## The count moved, as the brief warned

The entry recorded **7** widened-form ids. `sweep --since <root>` against the
**current** open set returns **6**: `#169, #275, #342, #465, #572, #630`. The
seventh folded or gained a verb-form citation since the entry was written —
exactly what the brief said would happen (`#196/#354/#159/#720/#721/#624/#627`
folded since, plus pass 1 cited shas in 14 more). I triage what is open now.

`sweep`: *examined 2866 commits since edfda2d8b… against 174 open ids
(1178 id-bearing, 1688 skipped, mostly other #N)*; *4 open id(s) git names
(verb form) the entry does not cite*; ***6 more named in widened form***.

## The 6

| id | disposition | sweep-named widened commit(s) | one-line basis |
|---|---|---|---|
| #169 | **landed — fold** | `81f455d1` (`#169:` bare) | AIR + luminance treatment live on master; guard registered; regression #391 fixed |
| #275 | **named, not landed — deliberately open** | `f1d04edf` (`#275:` bare) | research/plan artifact only; entry says NOT landed, blocked on his ruling |
| #342 | **partial** | `60826332` (`#342:` bare) | questions-filing only; cursor + delivery axis landed; tick-consume backstop remains |
| #465 | **landed but deliberately open — NOT a fold** | `36c7d867` (`#465 +` bare) | guard on master, but UNENABLED; blocked on human consent — the #465 trap, verbatim |
| #572 | **named, not landed — design only** | `9c3aee3c` `6ab05324` (`#572:` bare) | gh-etiquette design plan landed; no shim built; human signs off before any post |
| #630 | **partial — deliberately open** | `84183a5d` (`Merge #630`) | plan only; P1+P2 landed; P3–P5 remain; "stays OPEN deliberately" |

**Tally: 1 fold (#169), 2 partial (#342, #630), 2 named-not-landed (#275,
#572), 1 landed-but-deliberately-open (#465).** Fold rate ~17% (1 of 6) —
within the band pass 1's ~12% predicted for the lower-confidence half, and
nowhere near the 6-of-7 that would trigger an evidence-standard re-check.

## Calibration — #196 (direction 1, discharged against the method)

#196 is folded and will not appear in the open set, so it is the calibration
case (per the brief). The method independently re-derives the known answer:
`6d581823` is an ancestor of master, and the arrival/departure mechanism it
shipped is on master at `dev/capture/qsec.mjs:1` — *"qsec — #196: the
dashboard's questions fold ARRIVES and DEPARTS"* — 275 lines. The bare
`#196:` subject was missed by the old `SWEEP_SUBJECT` and matched under #707,
exactly as pass 1 recorded. **Direction 1 discharged: the procedure
(`show --stat` + `cat-file master:<path>` + `merge-base --is-ancestor`)
reproduces a known fold.**

## The deliberate-open check (the brief's mandated gate)

For every id below I read the **whole** entry and grepped it for
`deliberately open`, `stays open`, `unenabled`, `blocked`, `not landed`. The
result is stated per id. This is the check pass 1 failed on #465: it read the
`LANDED` line and missed the `STAYS OPEN, landed but UNENABLED` line two below.

- **#169 — CLEAN.** No deliberate-open / blocked / unenabled markers anywhere
  in the entry. The grep returned nothing. This is why #169 is the one fold.
- **#275 — DELIBERATELY OPEN.** *"CITED per #404's second option —
  deliberately open, awaiting HIS RULING rather than more work"*; *"blocked
  on: his ruling on the six questions"*; *"NOT landed"*.
- **#342 — no marker, but a stated remainder** (tick-consume habit, not yet
  tasked). Not deliberately open; partial.
- **#465 — DELIBERATELY OPEN (the trap).** *"STAYS OPEN, landed but
  UNENABLED"*; *"CITED per #404's second option — deliberately open"*;
  *"blocked-on: human (consent to install)"*; *"the open state is deliberate"*;
  and the entry carries the pass-1 rejection verbatim: *"COORDINATOR REJECTED
  THE FOLD."* **I do not fold it.**
- **#572 — no deliberate-open marker**, but implementation is human-gated:
  *"HE signs off before anything real is posted."*
- **#630 — DELIBERATELY OPEN.** *"The task stays OPEN deliberately — its
  title is build… P2 is the second of five phases"*; *"Citing the sha here
  per #404's second option."*

## Per-id evidence

### #169 — LANDED (recommend fold)

`81f455d1` `#169: an expanded element becomes prominent, not just taller` is
an ancestor of master. The original CSS lived in the `watch.py` inline
`STYLE` block; the block has since been extracted to `client/style.css`
(`watch.py:539` now reads `STYLE = "<style>" + _CLIENT_SRC["style.css"] +
"</style>"`). The treatment is live on master today:

- `client/style.css:228` — the `#169` comment block ("an expanded element
  becomes PROMINENT, not just taller"), 43 lines stating the two-channel
  contract (AIR + LUMINANCE) and the two traps the entry names.
- `client/style.css:271` — `details[open] { padding:.5rem 0; }` — the AIR
  rule. (This is the line #277 briefly rewrote and #391 restored; see below.)
- `client/style.css:273` — `details[open] > summary { color:var(--bright); }`
  — the LUMINANCE ramp step (one place up, never `font-weight` — the entry's
  first trap, handled).
- `client/style.css:275` — `details[open] > summary::before { content:"- "; }`.
- `dev/capture/prominence.mjs` (241 lines) is on master, registered in the
  `justfile` (`prominence` appears in the guard list), and asserts the
  per-surface ramp direction and the one-gesture neighbour travel (the
  entry's second trap — padding must not transition — handled and guarded).

**Regression history, checked and resolved.** `#277` (`22f9884`) rewrote the
shared `details[open]` padding rule and silently broke #169 on all four
surfaces; `#391` (`9e27c6e` `fix(#391): restore details[open] top air that
#277 cut`) restored it. #391 is **landed/folded** (closed 2026-07-28), so the
regression is fixed on master, not open. Both `9e27c6e` and `81f455d1` are
ancestors of master.

The entry names two traps (`font-weight` steps; padding + #104 neighbour
travel as ONE gesture). Both are addressed by the shipped treatment and
asserted by the guard. No remainder is stated; no deliberate-open marker is
present (grep clean). **Recommend fold**, citing `81f455d1` and the
`client/style.css:271`/`:273` lines.

### #275 — NAMED, NOT LANDED (stay open; deliberately open / human-blocked)

`f1d04edf` `#275: research public Dreamhub authentication` touches
`.dreamwork/docs/plans/hub-public-auth.md` (462 lines),
`.dreamwork/review/hub-public-auth.html`, and `doc-map.md` — **research and
a review artifact.** Nothing was implemented. The entry itself is unambiguous
and was already triaged by pass 1 (verb form `a75770eb`) as named-not-landed:
*"NOT landed, and #306's check is why… blocked on: his ruling on the six
questions."* Deliberate-open markers are present: *"CITED per #404's second
option — deliberately open, awaiting HIS RULING rather than more work."*

The research/design shas the entry cites (`4b49ecb`, `4b49ecbf`, `b758e059`,
`0b365c68`) are all ancestors of master — the research half genuinely landed.
The task's own terms require an approved design, which awaits a human ruling.
**Stays open.** (Overlap with pass 1 noted below.)

### #342 — PARTIAL (stay open, note remainder)

`60826332` `#342: file the delivery-modes ask` touches **only
`.dreamwork/questions.md`** (23 lines) — it files Q1/Q2/Q3. That is not a
landing; it is the ask. The real landings are separate and all ancestors of
master:

- `57f99aef` / `8b89f97c` — design landed (`.dreamwork/docs/plans/delivery-modes.md`),
  consuming #263's cursor rather than designing a second one.
- `59527090` (merge) — lane A: `Journal.events_since_cursor`, the
  cursor-bounded read projection.
- `d62265d9` (merge) — lane B: the `watch.py` delivery axis, emits_wake
  routing, picker chip (deployed on :35110).

**Remainder** (per entry): *"the tick-consume habit (the loop draining
events_since_cursor each tick) — the durable backstop that makes batched
delivery lossless; SKILL.md/tick-flow increment, not yet tasked."* No
deliberate-open marker. **Stays open, partial.** Recommend citing the four
landed shas to stop sweep re-flagging.

### #465 — LANDED BUT DELIBERATELY OPEN — NOT A FOLD (the trap)

This is the id the brief front-loaded, and it is the one pass 1 got wrong.
The sweep-named widened commit `36c7d867` `#465 + hand-off backlog` touches
**only `.dreamwork/questions.md` + `doc-map.md`** — a hand-off backlog edit,
not a landing. The real landing is the verb-invisible `58e3040`
(`wip(#465): lane containment…`), merged `ef5db01`; both are ancestors of
master, and the guard is on master at `dev/lane_guard.py` (refuses a
main-checkout commit touching a dispatched lane's paths).

**I do NOT recommend folding #465.** The entry, read in full, says:

- *"STAYS OPEN, landed but UNENABLED. `core.hooksPath` is machine-local, so
  the merge shipped a script and a documented step, not protection."*
- *"CITED per #404's second option — deliberately open."*
- *"blocked-on: human (consent to install)."*
- *"the open state is deliberate."*
- And the pass-1 rejection, recorded in the entry: *"#721 pass-1 triage
  recommended folding this; COORDINATOR REJECTED THE FOLD. The lane read the
  entry's 'LANDED 58e3040, merged ef5db01' line and missed the continuation
  two lines below."*

The landing is real; the open state is deliberate; the remaining work is
ENABLEMENT (installing the hook behind `core.hooksPath`, which is his call
because his hook path is global). **Deliberate-open markers checked and
present. Stays open.**

### #572 — NAMED, NOT LANDED (stay open; design only)

Two widened-form commits, both `.dreamwork/` artifacts:

- `9c3aee3c` `#572: fold his answer — settle four forks into a plan` — adds
  `.dreamwork/docs/plans/gh-etiquette-shim.md` (81 lines), the design plan.
- `6ab05324` `#572 Q2 answered` — `handoffs.md` + `questions.md`; records
  the last open fork's answer.

No shim was built. The entry: *"Q2 ANSWERED… the DESIGN IS NOW FULLY SETTLED
and the task is unblocked for implementation"* — design settled, implementation
not started. And a hard human gate on the implementation: *"the initial gh
shim must insert NOTHING — test with the additions commented out, and HE
signs off before anything real is posted."* No deliberate-open marker, but
the task is design-complete / implementation-not-started with a human sign-off
gate. **Stays open.** Recommend citing `9c3aee3c`.

### #630 — PARTIAL (stay open; deliberately open)

`84183a5d` `Merge #630: component-transition plan…` touches **only
`.dreamwork/docs/plans/component-transition.md`** (539 lines) — the PLAN. The
entry: *"PLAN landed `eb7112ad`… The task itself stays OPEN deliberately: its
title is build, and the lane was dispatched to plan."* Two phases have since
landed, both ancestors of master:

- P1 build step — `#653` (page byte-identical, coordinator-verified).
- P2 React runtime + component registry — `a49dcb4f`, merged `d34b6bae`
  (`client/dist/native.js`, mounts nothing; coordinator-verified
  byte-identical served page).

**Remainder:** P3 (first converted surface, `/research`), P4 (session view),
P5 (claude-design tokens-then-wrappers) — three of five phases. Deliberate-open
markers present: *"The task stays OPEN deliberately… Citing the sha here per
#404's second option."* **Stays open, partial.**

## Out of scope (named, not fixed)

1. **#275 and #465 overlap with pass 1.** Pass 1's out-of-scope note #3
   flagged that both appear in the widened form too. I triaged them here for
   completeness; pass 1's verb-form dispositions (both stay open) stand
   unchanged. The widened-form commits add no new evidence toward a fold.

2. **The 7th widened-form id is gone.** The entry recorded 7; sweep now
   returns 6. One id among the original 7 has folded or gained a verb-form
   citation since the entry was written. I did not determine which (it is no
   longer open, so it is outside this triage), but the coordinator may want
   to confirm none was folded on a false premise.

3. **#169's treatment migrated to `client/style.css`.** It is no longer in
   `watch.py`'s inline `STYLE` block (extracted per the #397 string-builder
   move; `watch.py:539` reads the file). A triager grepping `watch.py` for
   `#169` will find nothing and may wrongly conclude the treatment was
   reverted — I nearly did. The lesson at `lessons.md:1905` (the #277 break
   and #391 restore) is the corrective, and it points at `details[open]`,
   which now lives in `client/style.css`.

## Dogfood report

- **The brief's #465 warning is the single most valuable line in it.** Having
  read the entry in full *before* reaching a disposition, the
  `STAYS OPEN, landed but UNENABLED` line was unmissable. The brief earned its
  keep exactly once (it stopped pass 1), and it earned it again here — the
  entry now even carries the pass-1 rejection verbatim, which is a stronger
  guard than the brief. No friction.
- **The calibration case (#196) is well-chosen** and discharged cleanly; it
  caught nothing because the method is sound, which is the point.
- **One near-miss worth naming:** my first grep for #169's treatment was
  scoped to `watch.py`, returned empty, and read for ten seconds as "the
  treatment was reverted." It had migrated to `client/style.css`. The #706
  standard ("content on master at this line") held — I just had to find the
  line — but a triager who trusts a remembered file location over a content
  search would fold-or-not-fold #169 wrongly. Not a brief defect; a reminder
  that "on master" means "search master," not "search the file it used to be
  in."
- **The `&&`-chain-aborting-on-empty-grep failure** (the repo's own
  pipe-eats-the-tail lesson) bit my first verification batch exactly as
  `lessons.md` predicts. Re-ran with `;`. No loss, but it is a live trap for
  any lane chaining grep into `&&`.
