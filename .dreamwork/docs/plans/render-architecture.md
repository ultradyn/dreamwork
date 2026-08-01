# #505 — the wholesale-rerender architecture smell: principled fix (design)

Lane-owns: this doc, one doc-map row, one `## Pending` line in
`.dreamwork/handoffs.md`. **Design only — no code, no `watch.py` edit.**
His words and the constraint are in
[`.dreamwork/docs/briefs/505-render-architecture.md`](../../docs/briefs/505-render-architecture.md);
[`transitions.md`](../../../../transitions.md) governs every gesture.

> **Status (2026-07-31, #591).** Two things changed after this design was
> written. **(1) G4 is retired.** He ruled on 2026-07-30 (Q2 below, via watch
> 07:44, commit `0f97df03`): *"we don't have a no-build single-file
> constraint. We had a python stdlib constraint, but otherwise building the
> webui bundle and breaking up watch.py into modules are good and reasonable
> things."* The python-stdlib **server** constraint stands; the no-build goal
> does not. Every `✘ G4` in the matrix below is a historical record, not a
> live refutation — in particular **I3's refutation now rests on G2 alone**
> (see the annotated bullet under "Why the ✘s"). **(2) I5 landed.** The
> survivor was implemented: morphdom v2.7.4 is vendored
> (`vendor/morphdom.min.js`), `setContent` reconciles `#view` with the
> content-hash skip (`client/router.js:1550`–`1683`), and the review dock
> reconciles through the same seam (Q3 phase 2, `client/router.js:1459`).
> Whether the claude-design goal (his 2026-07-31 focus) re-opens G2 was
> **#591's question**, decided in
> `.dreamwork/review/505-g2-render-authority.html` — not here. His 2026-07-31
> ~16:38 submission (receipt `a71d1105…`) added two further inputs the artifact
> weighs as goals: a component-native live session view ("only be available
> via that") and a WS/RPC state-delta direction for the webui.
> **(3) G2 is now ruled, and the answer is a component system.** He ruled
> 2026-07-31 17:03 (`#591`, receipt `dc9200a0-4ebf-5d3b-afab-71257155bef9`),
> `rec` on all three: **G2 reads per-surface** — one render authority *per
> surface*, and a **derived** surface is not a second authority; the
> claude-design breakpoint is **component-level and staged** (tokens +
> `client/style.css` first, delegating wrappers second); the framework is
> **React**. So the standing position is a **transition to a component-based
> React web UI**, with replacing `watch.py`'s old inline HTML by those
> components prioritised at the earliest suitable time (`#630`).
> **(4) And on 2026-07-31 19:09 he scoped the second-truth rule and relaxed
> the renderer sentence outright** (`#614`): the rule binds **on-disk master
> state** — *"we shouldn't split state.json across 2 files that diverge"* —
> and the web UI's state is *"a secondary kind of state … fine to be a 'second
> description'"*; separately, *"'one renderer, and it is the Python one' …
> we should relax this now since we're changing over to react based webui."*
> Canonical statement: **One fact, one home on disk**, `DREAMWORK.md`
> Philosophy. So G2 no longer refuses a second render authority even of the
> same surface — what remains is the **cost** of two hand-maintained
> descriptions, which is why the survivor is still *derived* (wrappers
> compiled **from** the same `client/*.js` files `watch.py` already serves,
> restating no markup) and new surfaces are still born as components with no
> builder twin. Read every `G2` cell below as a cost judgement, not a
> prohibition; the matrix's own verdict for **this** bug (I5, landed) is not
> reopened by either ruling.

> re the reset when data.json is recieved … selecting text from any of the
> questions deselects on update. selecting quesitons at the top or the
> project name works fine … could we use ids on html elements to avoid this?
> or maybe do a check of html contents before rerendering? or use like react
> or something … (Note: Im okay introducing react … or something equivalent,
> doesnt have to be react exactly as per se). In any case, this feels like a
> general architecture smell … fix properly in a principled way.


## TL;DR

Every data tick does **one wholesale `innerHTML` swap of `#view`** and then
re-applies ~11 categories of human-owned state by hand
(`watch.py:6777` `setContent`). The crumb/project-name chrome survives because
it is a **sibling of `#view`** reconciled by a **keyed diff** (`renderChrome`,
`watch.py:8428`); his two surviving-selection surfaces are the proof that
keyed reconciliation is *already* the page's idiom for exactly this problem.
The reset he sees is the absence of that idiom inside `#view`.

The fix that survives the IGC is **the keyed diff that already exists, lifted
into `#view`** — a morphdom-idiom reconciliation over the data-driven lists
keyed by the identities the page already maintains (`data-qid`, `data-aid`,
`data-sha`, `data-review`, `data-keep`), so survivor nodes are literally kept
and only changed subtrees are rewritten. It is the existing `renderChrome`
discipline, generalised. It subsumes #141/#503, drops most of the snapshot/
restore pairs, and **keeps `watch.py` the single deployed file with no build
step**. His "React or equivalent" is the right *goal* (DOM diffing) and the
wrong *mechanism* for a no-build single-file product: a vendored morphdom
(~2KB) gives the diff without the bundle/build cost React would impose.

*(Superseded in its premises, not its verdict — see the Status note above.
The no-build/single-file constraint was retired 2026-07-30, and on 2026-07-31
17:03 he ruled the UI **is** transitioning to a component-based **React** web
UI (`#591`, receipt `dc9200a0-4ebf-5d3b-afab-71257155bef9`). So read the
sentence above as "React was the wrong mechanism **for this reset bug**",
which it remains: morphdom landed and fixed it. It is **not** a live position
that React is wrong for this product.)*


## The reset inventory, measured not assumed

How a tick renders today: `tick()` (`watch.py:9105`) snapshots state, calls
`buildCurrent()` (`watch.py:6430`) which returns a fresh HTML string for the
current view, then `setLiveContent(html)` (`watch.py:6685`) →
`setContent(html)` which does **`document.getElementById('view').innerHTML =
html`** (`watch.py:6778`). That single assignment replaces **every child of
`#view`** as new nodes. A live probe (fixture target on guard port 39890,
Playwright, touching the watched `DREAMWORK.md` to force a poll) confirmed
both halves: `#view`'s children are wholesale-replaced across a tick, and a
text selection set inside a question card body (`"bold"`) was **empty**
(`""`) one tick later. Selection in `#hproj` (the chrome) survived, because
the chrome is not inside `#view`.

The " Views are pure builders returning `#view`'s innerHTML" contract
(`watch-design.md:726`) is the structural cause: the router/tick hand a brand-
new string to one seam, and one seam throws the old DOM away.


Below, every row was checked against the source (line numbers cited). "Carried
today?" = whether a snapshot/restore pair already re-applies it after the
swap. **State that is carried is carried *imperfectly***: it is re-applied
node-by-node after the swap, so it survives *functionally* but the underlying
node was still destroyed and rebuilt — which is why a fresh selection (a
state no snapshot captures) is lost, and why in-flight CSS transitions on
swapped nodes are interrupted and have to be resumed (#477).

| # | Reset surface | Lost on a data tick? | Code path that loses it | Carried today? (snapshot/restore) |
|---|---|---|---|---|
| R1 | **Text selection inside `#view`** (his report) | **YES — lost** (probe-confirmed) | `setContent` `innerHTML` swap, `watch.py:6778`; no snapshot captures a DOM `Range` on prose | **No.** `snapshotCardState` (`watch.py:6826`) carries a *textarea's* `selectionStart/End` only, never a prose `Range`. The bug he named. |
| R2 | **Card-owned state: typed draft, caret, box scroll, open disclosures, read-scroll, dest-mode** | Functionally survives | `innerHTML` swap `watch.py:6778` | **Yes — re-applied.** `snapshotCardState`/`restoreCardState` (`watch.py:6826`/`6890`), keyed by `data-qid`. Survives only because it is re-created on fresh nodes. |
| R3 | **`#askbox` draft/caret/scroll** | Functionally survives | swap `watch.py:6778` | **Yes.** `snapshotAskState`/`restoreAskState` (`watch.py:6442`/`6449`) + `bindAskDraft` (`watch.py:6458`). |
| R4 | **Open `<details>` disclosures** (`data-keep`: qsec, status-rest, file:*, commits, answered aids) | Functionally survives | swap `watch.py:6778` | **Yes — #141/#503 idiom.** `snapshotFolds`/`restoreFolds` (`watch.py:6976`/`6986`), keyed by `data-keep`. |
| R5 | **Review dock** (`#qdock`) | Partially survives | `setLiveContent` review branch `watch.py:6685` swaps only `#qdock`, not whole `#view` | **Yes — narrower swap.** The dock node is `replaceWith`'d (`watch.py:6704`); scroll/draft/fade-classes re-applied. |
| R6 | **Review `<iframe>` browsing context** (cross-origin scroll/state) | Would be lost | swap | **Yes.** `snapshotReviewFrame`/`restoreReviewFrame` (`watch.py:6661`/`6672`) *keeps the live iframe element* (`replaceWith`, `watch.py:6679`) — the closest thing to reconciliation today. |
| R7 | **Burndown hover/pin/focus** (#494) | Functionally survives | swap `watch.py:6778` | **Yes — #494 idiom.** `snapshotBdHover`/`restoreBdHover` (`watch.py:7907`/`7926`), keyed by bucket `data-t0`. |
| R8 | **Burndown bar heights** (FLIP travel) | Geometry re-derived | swap | **Yes, conditionally.** `snapshotBars`/`regroupBars` (`watch.py:7450`/`7461`) — only on a `burnKey` change, else instant. |
| R9 | **Commits panel row order** (#151) | Would be lost | swap | **Yes, conditionally.** `snapshotCards(GIT_LIST)`/`regroupCards` (`watch.py:7017`/`7238`) — only on a `gitKey` change. |
| R10 | **Question list regroup** (#104/#77, key field `data-qid`) | Would jump | swap | **Yes.** `snapshotCards(QA_LIST)`/`regroupCards` (`watch.py:7017`/`7238`) FLIPs survivors. |
| R11 | **Run-mode arm bar / posture / rolls** (#290/#445/#454) | Functionally survives | swap | **Yes.** `syncRunModeFromData` (`watch.py:5605 @ dc739001`), `syncPostureFromData` (`watch.py:6249 @ dc739001`), `restoreRolls` (`watch.py:7338`). |
| R12 | **One-shot arrival classes** (`.dreamin` on new asks/decisions/stale) | Re-derived | swap | **Yes.** `revealNewOpenAsks`/`revealStaleAction`/etc. (`watch.py:6726`+) guard against replay. |
| R13 | **In-flight CSS transitions on swapped nodes** (#477 section fold) | **Interrupted then resumed** | swap destroys the animating node | **Partially — #477.** `snapshotFolds` records a non-empty inline `height` as the "mid-gesture" tell and `restoreFolds` *continues the travel* (`watch.py:6986`+). Only `data-keep` disclosures; a transition on a non-`data-keep` node is lost. |
| R14 | **`#dreambg` canvas / WebGL** | Never at risk | canvas is a sibling of `#view` (`watch.py`, frame-continuity invariant) | N/A — not inside `#view`. |
| R15 | **Crumbs / project name / title** (his "works fine") | **Never lost** | chrome is a sibling of `#view`, reconciled by key | **N/A — already keyed-diff.** `renderChrome` (`watch.py:8428`) reuses crumb elements by `data-k`, rewrites `innerHTML` only when content changed (`watch.py:8448`). |
| R16 | **Document-level scroll position** | Survives (the scroller is `body`/`html`, not inside `#view`) | N/A | N/A. |


**Inventory headline: 16 distinct surfaces; 1 is the bug he named (R1), 11 are
re-applied by hand after the wholesale swap (R2–R12, imperfectly — re-created
nodes, not kept nodes), 1 is partially resumed (R13), and 3 are never at risk
because they live outside `#view` (R14–R16).** The chrome (R15) is the
existence proof: the page already has a principled, keyed, content-gated
reconciliation, and it is the one region he reports as *not* resetting.

The cost of the current architecture is the eleven hand-maintained
snapshot/restore pairs: every new interactive state someone adds is a new
class of reset unless they remember to snapshot and restore it, and the
classes that *are* carried are carried as re-creation, which is why a
selection (R1) — a state nobody snapshots — falls through. #503 and #494 are
both instances of "a state nobody had snapshotted yet"; the principled fix
removes the need to keep adding snapshots.


## The IGC over integration shapes

**Context (C).** A single-file Python server (`watch.py`, ~382KB / ~7700
lines of client JS inlined as Python string constants, no build step, no
`node_modules`) serves one HTML document. A ~2s `/mtime` poll triggers a live
re-render through one seam (`setContent` → `innerHTML`). Every transition in
`transitions.md` — ghost dissolve, survivor FLIP, keyed re-pose,
`foldDetailsLocal` travel, the regroup matrix — is built *on top of* the
wholesale swap (it snapshots rects before, then animates survivors after).
`#view`'s children are always fresh nodes after a tick.

**Goals (binary, each can refute an idea).**

- **G1 — gestures preserved or equivalently carried.** Every transition
  family in `transitions.md` must still read as the same gesture after the
  change (ghost dissolve, FLIP regroup, keyed re-pose, fold travel, wisp,
  departures). A path that turns a travel into a teleport, or a dissolve into
  a fade, is refuted.
- **G2 — no second render authority.** There must remain exactly one place
  that commits the DOM for a view (`setContent` today). Two authorities
  (e.g. a vdom tree *and* the string builders) is the architecture smell
  restated, not fixed.
  **READING PINNED 2026-07-31** — he ratified the **per-surface** reading
  (`#591` Q1, receipt `dc9200a0-4ebf-5d3b-afab-71257155bef9`): G2 refuses two
  *maintained* truths about the **same** surface. A **derived** surface —
  compiled from the same source the one authority renders, restating no
  markup — is not a second authority, and different surfaces may legitimately
  differ. Every `G2` cell below was scored under that meaning and still holds
  under it.
  **READING RETIRED 2026-07-31 19:09 (`#614`)** — he relaxed *"one renderer,
  and it is the Python one"* outright, and separately scoped the second-truth
  rule to **on-disk master state** (canonical: **One fact, one home on disk**,
  `DREAMWORK.md` Philosophy). G2 no longer *refuses* anything on the render
  path, including a hand-maintained twin; it now prices one. The cells below
  are unchanged in verdict — a derived surface was cheap under the old reading
  and is cheap under this one — but a lane must read a `✘G2` as "this costs
  two maintained descriptions of one surface", not as "this is forbidden".
- **G3 — selection/scroll/focus survive a poll without per-state patching.**
  R1 must be fixed *as a class*, not by adding a 12th snapshot for prose
  selection. The bar is: a state nobody has yet thought to snapshot still
  survives, because the node that held it was kept.
- **G4 — single-file deploy unchanged (no build step).** `watch.py` remains
  the deployed unit, served verbatim, no bundler/compiler/`npm install`. A
  build step is a real cost; this goal prices it as decisive unless he rules
  otherwise (open call Q2).
  **RETIRED 2026-07-30** — he ruled otherwise (#505 Q2, commit `0f97df03`):
  no no-build/single-file constraint exists; the stdlib constraint is the
  *server's* (Python), and building the webui bundle is blessed. The G4
  column below stays as the record of the judgement as it was made; a ✘
  there no longer refutes anything.
- **G5 — reduced-motion parity.** Whatever the path, `prefers-reduced-motion`
  keeps function and legibility and drops only timing (transitions.md hard
  contract).


**Ideas (his three + what the inventory uncovers).**

- **I1 — ids on html elements (his).** Stamp stable ids and … (the brief
  asks; the code shows "ids" alone do nothing — the swap replaces the node
  regardless of its id).
- **I2 — content-check before rerendering (his).** Hash/compare the built
  HTML to the live HTML and skip the swap when identical.
- **I3 — full vdom adoption, React/preact/uhtml (his).** Re-target the views
  at a diffing framework.
- **I4 — keyed reconciliation of `#view` (morphdom-idiom; the inventory's
  finding).** Generalise the `renderChrome` keyed diff to the data-driven
  lists inside `#view`: parse the new HTML to a fragment, match survivor
  nodes by their existing identity keys, keep matched nodes, rewrite only
  changed subtrees. Hand-rolled or a vendored ~2KB morphdom.
- **I5 — content-hash skip *combined with* I4.** A cheap, fully-deciding
  short-circuit: if the built HTML string equals the last-built string, skip
  reconciliation entirely. Not a fix on its own (see ✘), but a free
  accelerator on top of any diff path.

| Idea | All | G1 gestures | G2 one authority | G3 survive w/o patching | G4 no build step | G5 RM parity |
|------|:---:|:--:|:--:|:--:|:--:|:--:|
| **I1** ids only | ✘ | ✔ | ✔ | ✘ | ✔ | ✔ |
| **I2** content-check skip | ✘ | ✔ | ✔ | ✘ | ✔ | ✔ |
| **I3** full vdom (React/preact/uhtml) | ✘ | ? | ✘ | ✔ | ✘ | ✔ |
| **I4** keyed reconcile `#view` (morphdom-idiom) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| **I5** hash-skip + I4 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |


**Why the ✘s (the errors are the reasoning):**

- **I1 ✘ on G3.** "Ids on elements" does not, by itself, stop the reset:
  `setContent` does `#view.innerHTML = html` (`watch.py:6778`), which
  unconditionally discards every child and parses the new string into fresh
  nodes — an id on a destroyed node does not survive to the new node. Ids are
  a *prerequisite* for reconciliation (the keys to match on), but without a
  matching step that *keeps* the old node, the id is decorative. (His instinct
  points at the right primitive — identity — but the matching is the missing
  half.) I1 is subsumed by I4: I4 is "ids + the matching step that makes them
  load-bearing."
- **I2 ✘ on G3.** A content-equality skip helps only when nothing changed.
  The moment *anything* in the view differs (an age ticked, a count moved, a
  new commit) the strings differ, the swap fires, and R1 resets exactly as
  today. It does not fix the class; it reduces its frequency. It is an
  accelerator (I5), not a fix.
- **I3 ✘ on G2 and G4.** (G2) A vdom library is a *second render authority*:
  the string builders (`buildDashboard` etc.) produce HTML and the vdom
  produces/patches a tree — two things that must be kept equivalent, which is
  the smell with a library in front of it. Adopting React honestly means
  *replacing* the string builders with component trees (a rewrite of all six
  views and the COMPONENTS), not layering it over them. (G4) `watch.py` is
  ~382KB of inlined JS with no build step and no `node_modules`
  (`watch-design.md:2737`: "watch.py is one file by design and cannot import
  it"). React+ReactDOM minified is ~45KB and ships as ES modules / JSX that
  need compilation; there is no way to drop it into the Python string without
  either a build pipeline (a new deploy dependency — against G4) or
  hand-writing `React.createElement` calls across ~7700 lines (unreadable,
  and still vendoring 45KB). preact (~3KB) and uhtml (~3KB) are lighter but
  share the same G2 second-authority and JSX/build shape. (G1 `?`: a full
  rewrite *could* preserve gestures, but every FLIP/ghost/keyed-re-pose in
  transitions.md is hand-tuned against the current swap-then-animate seam; a
  vdom would have to re-implement that integration, and whether it carries
  the gestures atmospherically is unproven — hence `?`, not ✘.)
  *(2026-07-31, #591: the G4 half of this refutation is void — G4 retired,
  see the Status note. The G2 half stands unchanged for the layered shape —
  a vdom **beside** the builders, which is still refused. Whether a component
  tree could be the ONE authority, and whether the claude-design goal forces
  one, was the larger decision, re-run in
  `.dreamwork/review/505-g2-render-authority.html` and **ruled 2026-07-31
  17:03** (receipt `dc9200a0-4ebf-5d3b-afab-71257155bef9`): yes — the UI is
  transitioning to a component-based **React** web UI, G2 read **per-surface**,
  breakpoint component-level and staged. That does not resurrect I3 as written:
  I3 is a vdom layered **over** maintained string builders producing the same
  markup, and two maintained descriptions of one surface are exactly what the
  ruling still refuses. What the ruling authorises instead is a **derived**
  surface — wrappers compiled from the same `client/*.js` `watch.py` serves,
  restating no markup — plus new surfaces born as components with no builder
  twin.)*
- **I4 ✔ (the survivor).** Keyed reconciliation over the existing identity
  attributes: a survivor node matched by key is *kept* (so R1's selection,
  R2's caret, R7's hover — any state on the node — survive because the node
  is the same object), only changed subtrees are rewritten, and the seam
  stays singular (`setContent` calls reconcile instead of `innerHTML =`).
  This is `renderChrome`'s discipline (`watch.py:8428`: reuse by key,
  `el.innerHTML !== c.html` gate at `watch.py:8448`) generalised into `#view`.
  Gestures (G1) are preserved *by construction*: the FLIP/ghost machinery
  snapshots rects *before* and animates *after* — reconciliation keeps the
  survivor nodes those mechanisms key on (`data-qid`, `data-sha`, …), so the
  snapshot/FLIP pipeline runs unchanged against the same nodes. No build
  step (G4): a morphdom diff is ~2KB of vendored, framework-free JS that can
  live in the Python string like every other helper. RM parity (G5) is
  untouched — reconciliation is state-preserving, not motion.
- **I5 ✔ (the recommended shape).** I4 plus a hash-skip: cache the last
  built HTML string; if the new build is byte-identical, return before
  reconciling. This captures I2's real value (skip the work entirely when
  nothing changed — e.g. a `status.json` rewrite that didn't touch the
  current view) *on top of* the structural fix. Both survive all goals; I5
  strictly dominates I4 on cost (fewer reconciliations) at no goal cost.


**Note on a tie avoided.** I4 and I5 both go All-✔. They are not rivals: I5
is I4 plus an accelerator. The differentiating goal is implicit cost (fewer
reconciliation passes), which is excess capacity on most ticks but decisive
on a hot `status.json` rewrite cycle. I5 is the recommendation; if the
hash-skip is judged not worth the one-line cache, I4 alone is already
non-refuted.

## Where his three sanctioned directions met the real code

Reported plainly, as invited:

- **"ids on html elements"** — *right primitive, incomplete alone.* The code
  proves an id on a node `innerHTML`'d away does not reach its replacement;
  ids need the matching step (I4) to become load-bearing. The page already
  *has* the ids (`data-qid`, `data-aid`, `data-sha`, `data-review`,
  `data-keep`); they are unused for reconciliation today because nothing
  matches on them inside `#view`.
- **"check html contents before rerendering"** — *an accelerator, not a fix.*
  It skips work when nothing changed but resets on the first real change. Its
  genuine value is as I5's hash-skip layer on top of the structural fix, not
  as the fix.
- **"react or equivalent DOM-diffing"** — *the goal is right (DOM diffing),
  the named mechanism is wrong for this product.* React/preact/uhtml impose a
  build step or a 45KB vendor + a second render authority, against the
  single-file, no-build, one-authority architecture that is *his own*
  (`watch-design.md:2737`). The "equivalent" he gestured at — a DOM-diff — is
  exactly I4, and it does not need to be React.
  *(**Superseded as a standing position, 2026-07-31.** The record of the
  push-back is kept because he invited it and it was right about **this bug**
  — morphdom landed and fixed the reset. But two of its three premises have
  since gone: the no-build constraint was retired 2026-07-30, and on
  2026-07-31 17:03 he ruled the UI **is** transitioning to a component-based
  **React** web UI, with G2 read **per-surface** and the claude-design
  breakpoint component-level and staged (`#591`, receipt
  `dc9200a0-4ebf-5d3b-afab-71257155bef9`). "React is wrong for this product"
  is no longer true and must not be quoted as if it were. What survives from
  the sentence is the narrow, still-live part: a component tree layered
  **beside** maintained string builders would be a second maintained truth,
  and that is still refused. The ruled shape avoids it by being **derived** —
  wrappers compiled from the same `client/*.js` the server already serves,
  restating no markup — with new surfaces born as components.)*


## Every transition family — its fate under the recommended shape (I5)

Reconciliation keeps survivor nodes by key; it does **not** animate. Every
family below keeps its mechanism because the mechanism keys on identities
that reconciliation preserves, and runs its snapshot-before / animate-after
pipeline against the *same* nodes it does today. "Preserved" = unchanged
mechanism; "absorbed" = the hand snapshot/restore it needed becomes redundant.

| Transition family (transitions.md) | Fate | Why |
|---|---|---|
| **Route dissolve / dream dissolve** (`crossfade`, `watch.py:8830`) | **Preserved.** | A *navigation*, not a poll — goes through `navigate`/`crossfade`, never `setContent`-on-tick. Reconciliation is the *tick* path; the route path is untouched. |
| **Survivor FLIP / the regroup** (`regroupCards`, `watch.py:7238`) | **Preserved + absorbed.** | Reconciliation keeps `.qa[data-qid]` etc., so `snapshotCards` before / FLIP after keys on the same nodes. The *travel* mechanism is unchanged; the manual card-state snapshot (`snapshotCardState`, R2) becomes *partially* redundant because kept nodes already hold caret/scroll — but the FLIP rect-snapshot stays. |
| **Keyed re-pose / state matrix** (`travelCard`, `watch.py:7052`) | **Preserved.** | Same argument — keys survive, the height/position travel runs against kept nodes. |
| **Section fold / `.qsec`** (#141/#196/#477) | **Preserved + absorbed.** | `data-keep` disclosures are kept nodes → their `open` state and inline height survive *without* `snapshotFolds`/`restoreFolds` re-applying them. #141's idiom is **subsumed**: the keep is now structural (the node is kept), not re-applied. The #477 mid-gesture-resume case simplifies: a kept node mid-transition was never interrupted, so the height-continuation hack is no longer needed for reconciliation ticks (still needed for genuine navigation). |
| **`foldDetailsLocal` travel** (#277/#503) | **Preserved.** | This is a *click* gesture, not a poll; reconciliation does not run on clicks. Untouched. Its `data-keep` open-state survival across the tick (#503) is absorbed as above. |
| **Departure ghosts / `dreamAway`** (`watch.py:7092`) | **Preserved — and the corpse rule stays load-bearing.** | The "a ghost holds no address" rule (`watch.py:7095`) must survive: reconciliation must not treat a detached ghost clone as a survivor. The ghost is appended to `.wrap` (outside `#view`), so it is outside the reconciled root — safe, but the design states it so a future change to where ghosts live does not silently re-introduce the double-count. |
| **Lifted-hero morph / submit morph** (#191) | **Preserved.** | Click/submit gesture, not a poll. Its `card.innerHTML = qaInner(…)` local restatement is on a *kept* node under reconciliation, so it composes. |
| **The wisp / awaiting-fold** | **Preserved.** | CSS keyframes on kept nodes; reconciliation keeps the node, the animation continues uninterrupted (today it is re-attached to a fresh node each tick — an improvement). |
| **Composer indicator / confirmation / courtesy-close** (#255/#291) | **Preserved + absorbed.** | The confirmation lifecycle re-binds on fresh nodes today; on kept nodes the in-flight timers and classes survive, reducing the re-bind churn. |
| **Burndown hover/pin** (#494, `snapshotBdHover`) | **Absorbed.** | Kept `.bdcol[data-t0]` nodes retain hover/focus; #494's snapshot/restore becomes redundant. |
| **Review dock fade state** (#326) | **Absorbed.** | The `.attop`/`.atend` classes ride kept nodes; the manual class-copy in `setLiveContent` (`watch.py:6697`) is no longer needed. |
| **Reduced-motion parity** (everywhere) | **Preserved.** | Reconciliation is state-preserving and non-animated; it changes nothing about timing. `rmr` paths untouched. |


## What the instance fixes become (#141 / #503 / #494)

- **#141 (`snapshotFolds`/`restoreFolds`, `data-keep`) — absorbed, key
  retained.** Under reconciliation, an open `<details data-keep>` is a *kept
  node*: its `open` property and any inline style survive the tick without
  `restoreFolds` re-applying them. The `data-keep` *attribute* is **retained
  as a reconciliation key** (it is already content-stable, the thing #141
  made it for) — its meaning shifts from "snapshot/restore marker" to
  "identity key for node matching." `snapshotFolds`/`restoreFolds` become
  dead code on the reconciliation path and are removed.
- **#503 (`expand(..., keep)` + `foldDetailsLocal`) — `keep` arg retained as
  key; `foldDetailsLocal` untouched.** `foldDetailsLocal` is a click gesture
  (not a poll), so it is untouched. The `keep` argument to `expand()`
  (`watch.py:2388`) is retained because it is what makes the `<details>`
  matchable across a tick. Its poll-survival job is now done by
  reconciliation.
- **#494 (`snapshotBdHover`/`restoreBdHover`) — absorbed.** Kept `.bdcol`
  nodes retain hover/focus/pin; the snapshot/restore pair is removed.

**Migration note for `data-keep`:** no rename, no format change. `data-keep`
values stay exactly as they are (content-stable: `qsec`, `status-rest`,
`file:<n>`, `commit:<sha>`, `dream:*`, answered `<aid>`). The only change is
*who reads them*: today only `snapshotFolds`/`restoreFolds`; after, the
reconciler matches on them (alongside `data-qid`, `data-aid`, `data-sha`,
`data-review`). A `data-keep` disclosure that is *also* keyed by another
attribute (e.g. an answered aid carries both `data-aid` and `data-keep=<aid>`)
must pick one canonical key per element to avoid ambiguous matches — the
design specifies "one identity attribute per reconciled element class,"
reusing the existing `*_LIST` declarations (`watch.py:7014`). No
`file-formats.md` change (the attribute's shape is unchanged); the
watch-design.md "`data-keep` so open rides snapshotFolds" notes update to
"so the reconciler keeps the node."


## Open calls for him (with recs)

- **Q1 — hand-rolled reconciler vs vendored morphdom.** Both satisfy I4.
  Vendoring a well-known ~2KB morphdom (e.g. the pataraco/morphdom algorithm)
  into the Python string is less code to maintain and is battle-tested;
  hand-rolling keyed-list reconciliation reuses the `renderChrome` pattern
  already proven in this codebase and avoids a vendored dependency. **`rec:
  vendored morphdom`** — the diff algorithm is exactly the kind of thing not
  worth re-deriving, and a 2KB vendor is far inside the no-build budget (the
  page already vendors an SVG-mist pipeline); the keyed-*list* FLIP layer on
  top stays hand-rolled (it is this page's own gesture, not a generic diff).
  Alternative if he prefers zero new vendored code: hand-rolled, modelled on
  `renderChrome`.
- **Q2 — confirm the no-build, single-file constraint rules out full vdom
  (G4).** He said "okay introducing react"; the IGC prices that as a real
  cost against his *own* single-file architecture (`watch-design.md:2737`),
  not a footnote. **`rec: hold G4 — the keyed-diff (I5) delivers the DOM-
  diffing he actually wants without the build/bundle/second-authority cost.`
  Adopt a vdom only if he wants the component model for its own sake, which
  is a different (larger) decision than this bug.**
- **Q3 — scope: `#view` only, or also narrow the review-dock `replaceWith`
  (#326) to reconciliation.** The review dock already does a narrower swap
  (`setLiveContent`, `watch.py:6685`); folding it into the same reconciler
  unifies the path but is extra surface. **`rec: phase 1 = `#view` lists and
  disclosures; phase 2 (optional) = fold the review-dock swap in.`**
- **Q4 — the corpse rule under reconciliation (load-bearing, needs a
  guard).** `dreamAway` ghosts are appended to `.wrap` (outside `#view`),
  so they are outside the reconciled root today. The design states the
  invariant ("the reconciler's root is `#view`; ghosts live in `.wrap` and
  are never matched"), but a regression here re-opens the double-count bug
  (`watch.py:7095`). **`rec: add a guard asserting no element carrying
  `.qaghost`/`.ghost` matches a reconciled identity key`** — same shape as
  the existing `states.mjs`/`morph.mjs` guards.


**DRAFT questions.md entry (NOT edited — for the coordinator to file):**

```
- **P1 · 2026-07-30 — #505: the wholesale-rerender smell — one call after the IGC.**
  **Sub-decisions:** `Q1`, `Q2`, `Q3`, `Q4`
  Design: `.dreamwork/docs/plans/render-architecture.md` (design only; no code authorised). His
  03:48 report: every data.json poll resets UI state inside question cards (text selection
  deselects; chrome survives). The inventory (16 surfaces) finds the chrome survives because it is
  ALREADY a keyed diff (`renderChrome`); the reset is the absence of that idiom inside `#view`,
  which is rebuilt by one wholesale `innerHTML` swap per tick (`watch.py:6778`) with ~11 hand
  snapshot/restore pairs re-applying state afterward. An IGC (I1–I5 × G1–G5) refutes his three
  directions as standalone fixes — ids alone don't survive the swap, content-check only skips
  unchanged ticks, React imposes a build step + second render authority against his single-file
  architecture — and the survivor is **keyed reconciliation of `#view` (morphdom-idiom) + a
  content-hash skip (I5)**: generalise `renderChrome`'s keyed diff to the data-driven lists,
  keeping survivor nodes by their existing keys so selection/caret/scroll/focus survive as a
  class. Subsumes #141/#503/#494 (their snapshot/restore pairs become dead code; `data-keep`
  stays as a reconciliation key).

  - **`Q1` — reconciler: vendored morphdom, or hand-rolled?** **`rec: vendored ~2KB morphdom`**
    (battle-tested diff, inside the no-build budget; the keyed-FLIP layer atop it stays
    hand-rolled). Alt: hand-rolled, modelled on `renderChrome`.
  - **`Q2` — hold the no-build single-file constraint (G4) and rule out full vdom?** **`rec:
    yes.`** The keyed-diff delivers the DOM-diffing he wants without React's build/bundle/
    second-authority cost. Adopt a vdom only if he wants the component model for its own sake.
  - **`Q3` — scope: `#view` only (phase 1), or also fold in the review-dock swap (#326)?**
    **`rec: phase 1 = `#view`; phase 2 (optional) = review dock.`**
  - **`Q4` — guard the corpse rule under reconciliation?** **`rec: yes — assert no ghost
    matches a reconciled key`** (the `dreamAway` double-count bug, `watch.py:7095`).

  **If you say nothing:** nothing is built — the design authorises no code, and the recs stand
  as defaults when the implementation is planned.
  Accepted answers: `rec` (takes all four) · per-question (`Q1: …`) · free text.
```


## Implementation sketch (for the planning lane, not this one)

The singular seam stays: `setContent` calls `reconcile(parsedFragment,
#view, KEYED_LISTS)` instead of `#view.innerHTML = html`. The views stay pure
HTML-string builders (`buildDashboard` etc. unchanged — G2). A `parseHTML`
template step turns the string into a fragment; the reconciler walks
`#view` and the fragment in parallel, keyed per list, keeping matched
survivors and patching only changed subtrees (inner content compare, as
`renderChrome` does at `watch.py:8447`). The hash-skip sits at the top of
`setContent`: `if (html === lastHtml) return;`. The snapshot/restore pairs
for carried state (R2–R12) are deleted in lockstep as each is proven
redundant against a kept node — R1 (the bug) is fixed for free the moment
`#view` reconciles, because a kept node keeps its selection. The FLIP/ghost
pipeline (`snapshotCards`/`regroupCards`/`dreamAway`/`travelCard`) is
unmoved: it snapshots rects before `setContent` and animates after, against
the same keyed nodes.

The pinned test surface (`test_page_reflows_prose_but_not_raw_text`,
`test_watch.py:4040`) pins token *prefixes* of the builders, not the render
call — those stay green. The render-call-shape pin
(`test_watch.py:3691`, asserting the *absence* of a stale
`setContent(buildDashboard(data))` literal) is exactly the kind of literal
the brief flags: the design says the pinned surface changes from
"`setContent` does `innerHTML =`" to "`setContent` reconciles," and that
test's anti-literal should be updated to assert the reconcile call, red-
proved against the old `innerHTML =` form.
