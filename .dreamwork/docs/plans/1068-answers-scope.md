# `/answers` scope — the `#1050` split

Scope doc for `#1050` (*flip /answers to native, deleting buildAnswers*). It
replaces `#1050`'s current coupling description, which is inaccurate: it names
`QaCard`, `QaCompose`, `FollowThread`, and `flipDock` as `/answers`' shared
machinery, and `buildAnswers` calls **none of them**. This document states what
`/answers` actually touches, derived from the current tree — not borrowed from a
sibling surface — so the flip can be split into increments that map to real
seams.

**Pinned to sha `7ee0d3786dd6a440dc9163b851857034c10b3c04` (branch tip ==
local `master` at the time of writing, 2026-08-03).** Every line number below is
against that sha; client files drift, so re-resolve before acting on any
citation.

This is a **scoping document**: it says what the increments ARE and where the
honest gaps are, not that any flip will work. It proposes no markup and asserts
no verification it did not perform. The second-truth rule (`DREAMWORK.md`) binds
the port — a native `/answers` may be a second *description* of state, but a
second *render* authority is refused; nothing here asks for one.

---

## Premise verification — the brief's citations have drifted

`#967` requires verifying the brief's premises before building on them. The
brief carried citations measured 2026-08-02; `client/` has moved. Re-resolved
against the pinned sha:

| Symbol | Brief said | Actually at | Delta |
|---|---|---|---|
| `buildAnswers` | `client/views.js:1198` | `client/views.js:1213` | +15 |
| `sendAsk` | `client/views.js:1224` | `client/views.js:1239` | +15 |
| `bindAskDraft` | `client/router.js:1501` | `client/router.js:1545` | +44 |
| `ANSWER_LIST` | `client/router.js:2296` | `client/router.js:2340` | +44 |

The substantive claims survive (each symbol exists and does roughly what the
brief says), but the line numbers were stale by 15–44 lines. Every citation in
the body below uses the **current** location.

---

## The coupling correction

`#1050`'s record says `/answers` is *"inside the qaCard/composer/FLIP family —
the four surfaces (`/`, `/questions`, `/answers`, `/question`) that share the
answer-submit FLIP morph (`router.js` `CARD_*`/`flipDock`), card-state
preservation across ticks (`snapshotCardState`/`restoreCardState`), the
composer, and the review dock."* Measured against the tree, that is wrong about
`/answers` specifically:

- `buildAnswers` (`client/views.js:1213`) renders a health banner, the ask form,
  and two read-only record lists (`answerRecord`, `client/views.js:1184`). It
  calls **no** FLIP/card-state/composer/review-dock machinery.
- The answer-submit FLIP morph (`flipDock`, `snapshotCards`/`regroupCards`,
  `ripple`, `travelQuestionColumn`) belongs to `sendAnswer`
  (`client/views.js:2219`) and `sendComment` (`client/views.js:2271`) — the
  **`.qa[data-qid]` QaCard surface on `/dashboard`/`/questions`/`/question`**
  (`QA_LIST`, `client/router.js:2339`). `/answers`' ask submission is `sendAsk`
  (`client/views.js:1239`), which uses **none** of it: it clears the box, writes
  a status message, and ticks.

`/answers` is the human's *ask* surface (he asks the dreamer; records render
read-only). The QaCard family is the *answer/comment* surface (cards he types
answers into). They share the word "answer" and little else. Conflating them is
the defect this doc exists to correct.

### What the four named symbols actually are

This repo uses a two-layer naming convention, measurable at
`dev/build/wrapper-exports.js:39-45`:

```
export const QaCard = ({ q, k, ctx = {} }) => React.createElement(HOST, { ... });
QaCard.displayName = 'QaCard';
QaCard.dwBuilder   = 'qaCard';
```

**PascalCase is the React wrapper** (authored in `dev/build/`) and
**camelCase is its string-template builder** (authored in `client/`). `QaCard`
itself returns 0 hits in `client/` source for exactly this reason — it delegates
to the `qaCard` builder (`client/components.js:1130`) — and nobody reads that
absence as phantom. With that convention, the symbols resolve as:

| `#1050` names (wrapper) | Builder in `client/`? | Wrapper in `dev/build/`? | Used by `/answers`? |
|---|---|---|---|
| `QaCard` | `qaCard` — `components.js:1130` | `wrapper-exports.js:39` | No |
| `QaCompose` | `qaCompose` — `components.js:888` | not yet written — that is `#1064` | No |
| `FollowThread` | `followThread` — `components.js:786` | not yet written — that is `#1063` | No |
| `flipDock` | `flipDock` — `router.js:4686` (not a wrapper/builder pair) | — | No (called only in `sendAnswer`/`sendComment`, a different surface) |

So `#1050`'s defect is not phantom names — the builders all exist, and
`QaCompose`/`FollowThread` are live React-port tasks (`#1063`/`#1064`) whose job
is to write the missing delegating wrappers. The defect is narrower: it names
these symbols as if `/answers` used them, and `/answers` calls **none of their
builders** — verified by scanning `buildAnswers`/`answerRecord`/`sendAsk`
(`client/views.js:1184-1280`) for `qaCard`, `qaCompose`, and `followThread`
(zero matches). **This is why QaCard FLIP work is excluded from the `/answers`
flip** (see *Exclusions*).

---

## What `/answers` actually touches

Three client seams, all verified:

1. **`buildAnswers(d)`** — `client/views.js:1213`. Renders the surface from
   `d.answers_health`, `d.answers_open`, `d.answers_answered`. Emits the ask form
   (`#askform`, `#askbox`, `#askmsg`) and the record lists.
2. **`sendAsk(form)`** — `client/views.js:1239`. The form's submit handler:
   one-in-flight guard, POST via `postAsk` (`client/components.js:1350`), and the
   success/reject/late branching.
3. **`bindAskDraft()`** — `client/router.js:1545`. Binds `#askbox` to the
   `ask:main` draft (`DraftStore`), restoring on bind. Called on route enter and
   tick (`client/router.js:2120`, `4949`).

Plus the disclosure motion (`ANSWER_LIST`, `client/router.js:2340`) and the
open-ask arrival (`revealNewOpenAsks`, `client/router.js:1897`), covered under
*Motion*.

---

## States

The brief asks for four states: unreadable, open, answered, no-aid. Derived from
`buildAnswers`/`answerRecord`, not borrowed:

### unreadable — `client/views.js:1214`
`buildAnswers` opens with `d.answers_health === 'unreadable' ? <health banner> :
''`. **Honest nuance:** unreadable is a *banner prepended* to the normal surface
(`h += …`), not a replacement state — the form and both lists still render below
it. A flip that treats it as a mutually-exclusive screen state would be
inventing a branch the legacy code does not have.

### open — `client/views.js:1220`, `answerRecord` `client/views.js:1203-1210`
`d.answers_open.map(e => answerRecord(e))` renders `<article class="aq open">`
rows ("you asked · awaiting dreamer"). Identity is `data-aqid` (server `aid`).

### answered — `client/views.js:1222`, `answerRecord` `client/views.js:1190-1198`
`d.answers_answered.map(e => answerRecord(e, true))` renders
`<details class="aq answered">` rows with `data-aid`/`data-keep` (the fold/FLIP
identity).

### no-aid — **NOT a distinct `buildAnswers` state.** `answerRecord` `client/views.js:1191` (answered) and `:1203` (open)
`no-aid` is a *per-record sub-branch*, not a top-level state: when `!e.aid`,
`answerRecord` omits the identity attributes (`data-aid`/`data-keep` for
answered, `data-aqid` for open) and downgrades the markup. The downgraded record
is excluded from FLIP/fold eligibility (it fails the `ANSWER_LIST`/arrival
selectors) but renders visually the same as its sibling. **Gap, stated plainly:**
a flip that models `no-aid` as a fourth screen state would be modelling
machinery `/answers` does not have; it is an attribute of a record, handled
inside the record builder.

---

## Responses (the `sendAsk` outcome paths)

`sendAsk` (`client/views.js:1239`) has three outcome classes:

### successful — `client/views.js:1260-1265`
`if (res && DraftStore.isDurable(res))`: clears the box, clears the `ask:main`
draft, sets `#askmsg` to "asked", and `await tick()`s. `isDurable`
(`client/router.js:1698`) is `res._dwv.landed` if a verdict is attached, else
`res.ok` — so a rejected-202 (`res.ok` true, `rejected:true`) does **not** take
this branch.

### rejected — `client/views.js:1266-1278` (the `else if (liveMsg)` arm)
Three sub-cases, **all keep the words** (draft survives):
- unreachable (`!res`) → "dreamwork is unreachable — your words are kept"
- rejected (`v.rejected`, reason via `REJECT_WHY`/`QSEND_WHY`,
  `client/views.js:1270-1271`) → "not written — \<why\>. your words are kept"
- otherwise refused → "question was refused — your words are kept"

### late — `client/views.js:1252` and `:1257` (silent no-ops, NOT a message)
"Late" produces **no user-facing message**; it is a *drop*. Two guards:
- **superseded** — `if (mine !== askFlightGen) return;` (`:1252`): a newer ask
  owns the generation, so the old response is ignored.
- **surface destroyed** — `if (view.name !== 'answers') return;` (`:1257`): the
  user navigated away. `invalidateAskFlight()` (`client/views.js:1235`) is called
  on that navigation (`client/router.js:4765`), bumping the generation so a late
  response hits the superseded guard.

**Gap, stated plainly:** if a flip wants a "late" *row* in its response matrix,
it must model a non-event (a dropped callback), not a message — there is no late
copy to port.

---

## Draft behaviour

### draft survival — `bindAskDraft` `client/router.js:1545-1552`, `DraftStore`
`bindAskDraft` restores `DraftStore.id('ask','main')` into `#askbox` on every
bind (route enter + tick). `DraftStore` (`client/router.js:1597+`) saves on every
`input`, restores only into an empty box (live outranks storage), and clears
**only** on durable success (`sendAsk` `client/views.js:1264`). So the draft
survives: tick re-renders (restore), reject/unreachable (kept), and full
reload (localStorage). It is cleared only on a successful ask.

### caret survival — keyed reconciliation is primary; `snapshotAskState` is the height belt
Two layers, both real:
- **Primary:** `#askbox` is a single node kept by id under keyed reconciliation,
  so value/caret/scroll/focus ride the kept node across a tick — the comment at
  `client/router.js:1537-1543` documents this and notes the old
  `snapshotViewInputs`/`restoreViewInputs` pair was deleted in favour of it.
- **Belt:** `snapshotAskState`/`restoreAskState` (`client/router.js:1519`/`:1526`)
  re-apply the autogrow `fitText` height (clobbered by `morphAttrs` each tick)
  and silently clamp scroll, with `setSelectionRange` as a belt. The comment at
  `client/router.js:1515-1518` is explicit that this pair exists for the
  **height**, because `bindAskDraft` "restores value only".

**Honest nuance:** caret survival is **not** owned by a dedicated caret routine —
it is a consequence of the box being a kept node. A flip that ports only
`snapshotAskState` would believe it has ported caret survival while actually
porting the height belt; the caret authority is the reconciliation layer.

---

## Motion

### fold movement (the `ANSWER_LIST` disclosure) — `client/router.js:3740-3749`
The answered-record `<details>` expand/collapse is registered in `EXPAND_SURFACES`
(`client/router.js:3740`) against `ANSWER_LIST`
(`{ sel: '.aq.answered[data-aid]', key: 'aid' }`, `client/router.js:2340`). It
shares the `snapshotCards`/`regroupCards` FLIP path with the QaCard family, but
over a **different row set** (answered asks, keyed by `aid`). Missing-aid
answered details fall back to `foldDetailsLocal` (`client/router.js:3755`,
`listlessFallback: true`) — they toggle but do not travel and re-close on tick.

### open-ask arrival — `revealNewOpenAsks` `client/router.js:1897` (related motion the brief's single-item list omits)
The brief's *Motion* category names only the fold. There is a second `/answers`
motion path: a one-shot `.dreamin` arrival pose for **new** open asks
(`.aq.open[data-aqid]`), applied only on the genuine known→new transition after
`setContent` (`client/router.js:2082`), never on first paint, never under
reduced-motion. It is an *arrival*, not a fold, but a flip must account for it.

**Gap, stated plainly:** the open→answered transition (a dreamer answers an open
ask) has **no dedicated morph** — it is a tick re-render; the record simply
moves lists. If a flip wants that transition animated, that is new work, not a
port.

---

## Exclusions (explicit)

**QaCard FLIP work is OUT of scope for `/answers`.** Reasons, all verified:

1. `/answers` does not use `QaCard`. `buildAnswers` (`client/views.js:1213`)
   renders `answerRecord`, not `QaCard`. `QaCard` exists only in the React
   design-system artifacts (`client/dist/ds/QaCard.d.ts`), not in the legacy
   surface being flipped.
2. The answer-submit FLIP morph belongs to a **different surface**:
   `sendAnswer`/`sendComment` (`client/views.js:2219`/`:2271`) on the
   `.qa[data-qid]` cards (`QA_LIST`, `client/router.js:2339`), reached on
   `/dashboard`/`/questions`/`/question`. `/answers`' `sendAsk` uses none of
   `flipDock`/`snapshotCards`/`regroupCards`/`ripple`.
3. `/answers` calls none of the builders `#1050`'s named wrappers sit over.
   `qaCard` (`components.js:1130`), `qaCompose` (`:888`), and `followThread`
   (`:786`) are all absent from `buildAnswers`/`answerRecord`/`sendAsk`
   (`views.js:1184-1280`). Folding QaCard work into `/answers` would scope
   machinery this surface does not call, reproducing `#1050`'s original error in
   a longer form (`#651`: a description that names something it cannot back).

The shared `EXPAND_SURFACES`/`snapshotCards`/`regroupCards` FLIP *engine* is
touched only insofar as `/answers` supplies it one row set (`ANSWER_LIST`); the
engine itself is owned by whichever surface-flip reaches it first, not this one.

---

## How this doc could look finished and still be false (Direction 2)

No test red-proofs a scoping doc, so the discipline is to construct the
false-greens and say which were ruled out and how (`#994`: a report is not a
certification).

1. **States borrowed, not derived.** The easy failure: lift the state list from a
   QaCard surface and apply it here. *Ruled out:* every state row above points at
   a branch in `buildAnswers`/`answerRecord`. `no-aid` was found to be a
   per-record attribute, not a screen state — stated as a gap rather than
   inflated to fill the fourth row.
2. **Citations precise but about the wrong half.** `/answers` has two surfaces
   (record list vs ask form). *Ruled out:* each citation was checked against the
   half its row is about — record states cite `answerRecord`/`buildAnswers`;
   responses/draft cite `sendAsk`/`bindAskDraft`; motion cites `ANSWER_LIST`/
   `revealNewOpenAsks`. The `flipDock` calls at `client/views.js:2267-2268,2327`
   were specifically traced to `sendAnswer`/`sendComment` (a different surface)
   and excluded — citing them as `/answers` motion would have been exactly this
   failure.
3. **Precision without currency.** The brief's own citations were stale (+15/+44
   lines). *Ruled out:* every line number was re-resolved against the pinned sha
   and the correction table is the first section of this doc.

**Open false-green I could not fully close:** a reader who does not re-resolve
the citations against *their* current sha will read true-last-week numbers as
true-now — the precise failure that made this task necessary. The pinned-sha
header and the correction table mitigate it but cannot eliminate it for a reader
who skips them.

---

## Cited issues (relied-on lines)

- `#967` — *"verify the brief's premises before building on them; the citations
  above are the premises."* (task brief). Drove the premise-verification table.
- `#136` — *"an empty selection is indistinguishable from a broken derivation."*
  Drove stating `no-aid`/open→answered as gaps rather than silently complete.
- `#651` — *"A guard whose message names a failure mode it cannot detect"* — the
  general shape of `#1050`'s defect (a description naming machinery it cannot
  back). Drove the exclusion's reasoning.
- `#994` — *"a report is not a certification; label it as what it is."* Drove the
  boundary statement and the Direction-2 framing.
- `#292` — in-flight ask lifecycle (cited in code at `client/views.js:1228-1231`
  and `client/router.js:4763-4765`): one in-flight ask at a time; navigation
  invalidates. Backs the "late" response analysis.
- `#250` — missing-aid answered details and `listlessFallback`
  (`client/router.js:3743-3746`): backs the fold/no-aid motion analysis.
- `#459` — `#askbox` bound to `DraftStore` `ask:main`
  (`client/router.js:1543-1552`): backs draft survival.
- `#505` — `#askbox` kept by id; `snapshotAskState` height belt
  (`client/router.js:1515-1543`): backs caret survival.
