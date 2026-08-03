# QaCard family scope — one authority across four surfaces

Scope document for `#1069`. It fixes the stale four-builder premise, records
the current route/state/event/motion ownership, and chooses the cut line for a
native QaCard family. It does not convert a surface, propose markup, or claim a
browser behaviour was verified.

**Pinned to sha `f5c44ee84b2a640f9acefabf1da18a8b18e470fe` (branch tip ==
local `master` when measured, 2026-08-04).** Every line number below is against
that sha. Re-resolve them before implementing this scope.

## Premise verification

The task record was parsed from the 2026-08-02 planning pass. The source tree,
not that account, is the authority (`#967`). Re-resolved at the pinned sha:

| Planner/body claim | Pinned-tree fact | Delta |
|---|---|---|
| `buildQuestion` consumes QaCard at `client/views.js:1718` | `buildQuestion` is absent. `/question` is registered natively and its `FocusQaCard` delegates to `qaCard` (`dev/build/src/question.js:8-35`). | Substantive: one native route consumer, not a builder consumer. |
| `buildReview` is missing at `client/views.js:1526` | `buildReview` exists at `client/views.js:1541-1563` and calls `qaCard` at `:1548`. | Substantive plus +15 lines from the named site. |
| `buildQuestions` is at `client/views.js:1150` | It exists at `client/views.js:1165-1183`. | +15 lines. The stop condition holds. |
| QaCard has no named component-side authority | The derived export is `QaCard` at `dev/build/wrapper-exports.js:38-44`; `/question` calls the same builder through `fromBuilder` (`dev/build/src/question.js:8-11`). | The component is real, but its markup authority is still the builder. |
| No satellite-wrapper state was recorded | `FollowThread` and `QaCompose` now also have derived exports (`dev/build/wrapper-exports.js:71-86`) and companion files under `dev/build/ds-src/`. | New relevant state since the planner report; neither export is native markup. |

The wrapper header is load-bearing context: exports call builders in the same
generated lexical scope and contain no copied markup
(`dev/build/wrapper-exports.js:1-14`). Therefore the pinned tree has **one
builder markup authority used through four compositions**: `/question` is a
native *route* whose card is derived, while `/questions`, the dashboard Q&A
composition, and `/review` are builder compositions.

The renderer relaxation does not change that measurement. Rendering is outside
the on-disk second-truth rule (`DREAMWORK.md:239-247`), so a maintained native
rival is admissible; it must be rejected, if at all, on its cost. The incumbent
still has the cheaper property: derived wrappers restate nothing, and a real
conversion deletes its builder in the flip commit
(`.dreamwork/docs/plans/component-transition.md:168-212`).

## Current authority matrix

“Event” covers the card gestures required by this scope: mode/edit, submit,
tick, and disclosure. “Motion” names the code that turns the event into travel
or a reduced-motion snap. Repeated shared citations are intentional: the same
imperative implementation currently owns all four DOM shapes.

| Route / composition | State and render authority now | Event authority now | Tick, draft, and submit-mid-flight authority now | Motion authority now |
|---|---|---|---|---|
| `/questions` | `buildQuestions` partitions `questions_open` into **open** and **awaiting**, and `answered_entries` into **folded**, then calls `qaCard` (`client/views.js:1165-1183`). `qaState` derives the card class (`client/components.js:1008-1009`); `qaInner` supplies the common body (`:1117-1178`). | Open/awaiting offer answer + note; folded is note-only (`client/components.js:928-963`). `submitCard` dispatches by live mode (`client/views.js:2142-2146,2178-2180`). Card/thread disclosures share the delegated click handler (`client/router.js:3830-3884`). | Title-keyed persistence is `DraftStore`/`dwDraft` (`client/router.js:1624-1812,1815-1828`); reload restoration is `restoreAnswerDrafts` (`:1838-1853`). A tick snapshots/restores card state and regroups (`:4994-5083`). `sendAnswer`/`sendComment` alone own the awaited request and result (`client/views.js:2181-2290`). | Submit success snapshots, restates through `qaInner`, regroups, ripples, and calls `flipDock` (`client/views.js:2205-2230,2255-2290`). Disclosure calls `regroupCards` (`client/router.js:3880-3883`). `regroupCards` snaps under `rmr` (`:2668-2721`); `flipDock` is `:4776-4806`. |
| Dashboard Q&A composition | `buildDashboard` inserts `qSection` (`client/views.js:1114-1126`). `qSection` renders **open** and **awaiting** cards only inside a kept disclosure (`:324-339`); it has no folded `answered_entries` row. Card markup/state is the same `qaCard`/`qaState` authority above. | Card events are the shared mode/edit/submit/disclosure handlers above. The dashboard adds one outer `.qsec` disclosure event (`client/router.js:3912-3925`). | The same `DraftStore`, card snapshot/restore, and submit functions own the cards. The outer disclosure is kept by `data-keep` during reconciliation (`client/router.js:2026-2088`), and tick restores card state before measuring regroups (`:5047-5077`). | Card submit/fold motion is shared. The outer `.qsec` uses `travelCard` plus body reveal/depart; reduced motion leaves the native instant toggle (`client/router.js:3909-3925`). |
| `/question` | `Question` is the native route composition. It selects **open/awaiting** from `questions_open`, **folded** from `answered_entries`, and renders **missing** without a card (`dev/build/src/question.js:13-31`). A found state uses `FocusQaCard = fromBuilder('qaCard', ...)` (`:8-11`), so `qaCard`, not React source, still owns its markup. | A found card uses the same global mode/edit/submit/disclosure handlers; missing has none. The derived component itself only calls the builder (`dev/build/src/delegate.js:85-120`). | `setData` snapshots card state, updates mounted React roots, then restores it (`client/router.js:1375-1402`); the registry update is synchronous (`dev/build/src/registry.js:153-172`). Persistence and submit still use the global `DraftStore` and `send*` functions. **No source branch arbitrates a submit response against a concurrent native update.** | Submit/fold motion is shared. Focus layout additionally re-stations the response column after answer/note (`client/views.js:1944-1951`). Route entry uses the general crossfade; `rmr` commits without animation (`client/router.js:4654-4664`). |
| `/review` | `buildReview` either emits **no dock** or selects one `questions_open` entry and calls `qaCard(..., 'dock')` (`client/views.js:1541-1563`). A dock can therefore be **open** or **awaiting**, never folded from `answered_entries`. | A present dock uses the common card events. It also makes `.qbody` the reading scroller (`client/views.js:1850-1852`); no-dock has no card event. | Review ticks reconcile only `#qdock` through the shared keyed guard and restore stored drafts (`client/router.js:1884-1919`). Card snapshot state includes reading scroll, mode, text, caret, and disclosures (`:2224-2264,2288-2364`). Submit remains `sendAnswer`/`sendComment`. | Submit/fold motion is shared. Navigation from a linked card carries its source rect into `crossfade`, which calls `flipDock` for the dock (`client/router.js:4686-4712`). Reduced motion commits the settled review directly (`:4657-4664`). |

### Shared identity and satellite facts

- `qaCard` alone emits `data-qkey` (positional write address), `data-qid`
  (URI-encoded title identity), and `data-qsurface` (`client/components.js:1179-1189`).
  `QA_LIST` and card-state restoration key on `data-qid`
  (`client/router.js:2423-2445,2288-2304`). There is no stable question id in
  this tree; a native cut must preserve title identity rather than invent one.
- `qaInner` composes **both** satellites: `followThread` and `qaCompose`
  (`client/components.js:1162-1163`). Their current definitions are
  `client/components.js:842-854` and `:944-963`; treating either as a later,
  independent flip would leave half the card under the old authority.
- Reduced motion has one current fact, sampled once at page load: `rmr`
  (`client/router.js:2-8`). Submit, regroup, folds, route transitions, and focus
  positioning all consult that value; the tree does not implement live media-
  query changes.

## IGC — where may the native authority begin?

**Context.** `/question` is already a native route with a derived card;
`/questions` is expected to flip next; dashboard and review route shells remain
outside this task. A renderer twin is allowed but costly. The decision is the
smallest boundary that can make the card family native without making a
builder and a component co-author any matrix cell.

| Idea | All | G1 | G2 | G3 | G4 | G5 | G6 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Keep derived QaCard; flip route shells around it (incumbent) | ✘ | ✘ | ✔ | ✔ | ✔ | ✘ | ✔ |
| Maintained native QaCard route by route beside `qaCard` | ✘ | ✘ | ✘ | ✔ | ✔ | ✘ | ✘ |
| Convert all four route compositions with QaCard in one family flag day | ✘ | ✔ | ✔ | ✘ | ✘ | ✔ | ✔ |
| **Flip the QaCard-bearing subtree on all four surfaces; keep outer shells** | **✔** | **✔** | **✔** | **✔** | **✔** | **✔** | **✔** |

- **G1** one native QaCard/QaCompose/FollowThread render authority reaches all
  four consumers · **G2** no state is written by both builder and component ·
  **G3** no whole-dashboard or whole-review cutover · **G4** the boundary
  survives `/questions` becoming a native route next without moving · **G5**
  the primitive builders die in the same commit native authority becomes
  reachable · **G6** tick, draft, submit, identity, and reduced-motion homes
  are explicit rather than exempted.

Decisive errors:

1. The derived incumbent has one cheap authority, but it does not make QaCard
   native (G1/G5). It is the bridge to the boundary, not the boundary.
2. The maintained route-local rival is **admissible under the relaxed render
   rule**. It fails this task's stronger G2/G5 test on engineering facts:
   builder and component must agree on `data-q*`, `.qcompose`, `.qthread`,
   state classes, and the selectors the shared event/motion code addresses.
   That is a hand-maintained protocol between two render descriptions, paid
   until the last route moves; the failure is cost and shared agreement, not
   doctrine.
3. The coordinated route flag day has clean card authority but necessarily
   converts dashboard/review composition and makes the cut depend on whether
   `/questions` already moved (G3/G4). That is a larger route boundary than
   this task owns.
4. The subtree partition has one card-family writer while each outer route
   keeps its current writer. Partition is not duplication: the builder shell
   may emit a component host, but it may not emit, mutate, or reconcile the
   card subtree.

## The one legal cutover boundary

**In one sentence:** atomically replace the complete QaCard-bearing subtree on
all four surfaces with one native `QaCard` tree (including native `QaCompose`
and `FollowThread`), while leaving the surrounding dashboard/review shells in
place, and in that same commit remove every builder call and builder/event
state writer for the subtree so `/questions` can later change route registry
without moving the card boundary.

“Complete subtree” is deliberately wider than the four `qaCard(...)` calls.
It includes the smallest surface adapter that currently derives card state:

- `/questions`: the `#qsections` grouping now owned by `buildQuestions`
  (`client/views.js:1165-1183`);
- dashboard: the `.qsec` disclosure, grouping, and cards now owned by
  `qSection` (`client/views.js:324-339`), but not the dashboard's Q&A label,
  answers link, or any later panel;
- `/question`: the found-card branch of `Question`, leaving its missing branch
  route-local (`dev/build/src/question.js:13-31`);
- `/review`: the card contents of the dock. `buildReview` keeps artifact,
  split, and no-dock layout authority (`client/views.js:1541-1563`).

### Authority on the two sides

| Concern | Before the cut | After the cut |
|---|---|---|
| QaCard/state/grouping | `buildQuestions`/`qSection`/`buildReview`/`Question` select; `qaCard` + `qaInner` render. | Surface adapters select/group; one native `QaCard` renders. No builder emits `.qa`. |
| QaCompose + FollowThread | `qaCompose` and `followThread` string builders, reached through `qaInner`. | Native children of the same tree; their derived wrapper exports stop calling deleted builders. |
| Identity | `qaCard` alone writes `data-qkey`, `data-qid`, `data-qsurface`. | `QaCard` alone writes those exact attributes. Island hosts use a distinct mount identity that card event code never reads. |
| Drafts | Global input listener writes through `dwDraft`; snapshot/reconcile/restoration writes live DOM. | `DraftStore` remains the sole durable store; QaCompose alone writes its live value and store entry. Remove the card input listener, `restoreAnswerDrafts`, and card snapshot restore from native cards rather than running belts beside React state. |
| Tick-mid-edit | Builder morph or delegated `dangerouslySetInnerHTML`, then snapshot/restore belts. | One island/route registry pushes new `q` props into stable keyed roots; React local edit/mode/disclosure/focus state survives. The shell reconciler skips owned subtrees. |
| Submit-mid-flight | `sendAnswer`/`sendComment` retain DOM references across `await`, then imperatively restate builder markup. | QaCompose owns request generation, durable-result application, draft clearing, and the settled card state. Retire `submitCard`/`sendAnswer`/`sendComment` as card state writers; transport helpers may remain. |
| Motion + reduced motion | Router owns `rmr`, list snapshots/regroups, `travelCard`, `flipDock`, route crossfade, and focus-column travel. | Router remains the sole cross-card/route motion engine and sole reduced-motion fact. The native tree emits one lifecycle intent per event; it does not implement a second FLIP. Card-local state is component-owned. |

This is also the deletion boundary. `qaCard`, `qaInner`, `qaCompose`, and
`followThread` cannot remain as reachable fallback renderers after the native
tree is reachable. Conversely, none can be deleted while even one of the four
call sites still emits a builder card. The current derived exports are the
safe bridge up to that commit (`dev/build/wrapper-exports.js:38-86`), not a
reason to stage an authority overlap after it.

## Proof obligations at implementation time

These are gates on the future flip, not verification claimed by this document:

1. A source/registry census proves the four compositions no longer call
   `qaCard`, and no `qaCard`/`qaInner`/`qaCompose`/`followThread` definition or
   derived `dwBuilder` claim remains reachable.
2. A real morph tick on each composition proves the native root is neither
   detached nor overwritten and that grouping/order changes still use title
   identity. The check must exercise the current `setData` and shell-reconcile
   paths, not mount a component in isolation.
3. A held answer and held note POST each race a real tick on every found-card
   composition. Success clears exactly once and runs one motion; refusal keeps
   words and runs none; a destroyed/retitled card produces a named recovery
   result rather than mutating a detached node.
4. Tick-mid-edit covers value, caret, focus, compose mode before first
   keystroke, textarea scroll/height, card/thread disclosure, review read
   scroll, and dashboard `.qsec` disclosure. This is the current
   `snapshotCardState` inventory (`client/router.js:2224-2264`), not an
   inferred smaller list.
5. Every motion assertion has a reduced-motion companion: function/state
   change still happens, while `regroupCards`, `flipDock`, fold travel,
   crossfade, and focus-column travel do not animate.

## Honest gaps

1. **No component-island lifecycle exists in the pinned tree.** The registry
   currently asserts whole-route `#view` ownership
   (`dev/build/src/registry.js:10-27`); `reconcileGuard` has no owned-subtree
   skip (`client/router.js:2026-2088`). The earlier transition plan names the
   island shape but still labels its per-subtree wording unratified
   (`.dreamwork/docs/plans/component-transition.md:328-349`). The later render
   relaxation makes the rival admissible, but this document does not pretend
   the mount/update/unmount mechanism already exists.
2. **Submit-mid-flight has no explicit current arbitration rule.** Both send
   functions capture `el`/`card`, await, and then mutate those objects
   (`client/views.js:2181-2219,2234-2274`); native updates can replace delegated
   inner markup (`dev/build/src/delegate.js:85-112`). I found no generation,
   mountedness, or re-resolution branch for that race. Static reading cannot
   certify the user-visible outcome, so the held-POST proof above is blocking.
3. **Title is the only card identity available.** `data-qid` is encoded title
   and `data-qkey` is positional (`client/components.js:1179-1189`). This scope
   neither invents a stable id nor promises draft survival across a retitle.
4. **The leaf-render closure is not decided here.** `qaInner` also calls
   Markdown, stamps, focus/roll links, and update chrome
   (`client/components.js:1117-1177`). A still-builder-owned leaf may stay
   derived, but the implementation must census its last consumers; copying it
   into QaCard is not licensed by this scope.
5. **The component-weight policy is Max's open parameter.** `#1203` records
   that migrated component bytes are currently reported, not bounded. If he
   chooses a bound, the flip must fit or wait; it may not split this atomic
   authority boundary into a maintained pair to satisfy a byte ceiling.
6. **This is source-backed scope, not runtime certification.** No browser
   guard was run for this document and no markup was authored. The matrix says
   where current behaviour lives; the obligations say what a future lane must
   prove.

## How this scope could look finished and still be false

1. **Route-native mistaken for card-native.** `/question` mounts React, but its
   found card still calls `qaCard`. Ruled out by distinguishing route authority
   from card markup authority in the premise table.
2. **An island that is only a second renderer.** A builder could leave its
   `.qa` markup in place while React mounts another subtree beside it. Ruled
   out by G2/G5 and the same-commit census/deletion obligation.
3. **End-state tests hide a broken race.** A tick after a submit can eventually
   show server truth even if the held response mutated a detached card. Left
   open until the held-POST/tick test observes the response window itself.
4. **Reduced motion tested as absence only.** A check can see no animation
   because the click or submit did nothing. The proof obligation pairs every
   no-motion assertion with the same state/function change.
5. **Precise citations become stale.** Mitigated by the pinned sha and delta
   table, not eliminated. Re-resolution is required before implementation.

## Cited task records

- `#1069` — *“Scope one native QaCard authority across `/questions`,
  `/question`, dashboard, and `/review`.”* This document is that scope.
- `#967` — *“Verify the entry's central factual claims before building.”*
  Drove the premise table and the stop-condition check.
- `#630` — *“For conversions the permanent mechanism is DELETION (the builder
  dies in the flip commit; zero-commit overlap).”* Drove G5 and the atomic
  builder-removal side of the boundary.
- `#1049` — *“`/question` is now a native component and `buildQuestion` is
  deleted.”* Explains the mixed starting state; the source citations above are
  the current proof.
- `#1203` — *“components are measured and REPORTED, not bounded”* while Max's
  decision remains open. Recorded as a gap, not decided here.
