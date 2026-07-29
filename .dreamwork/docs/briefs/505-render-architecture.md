# Brief — #505: the wholesale-rerender architecture smell — investigate and design the principled fix (design lane, P1)

Lane-owns: `.dreamwork/docs/plans/render-architecture.md`, `.dreamwork/docs/doc-map.md` (one row), `.dreamwork/handoffs.md` (append ONE `## Pending` line)

**Design only — no code, no `watch.py` edit.** The implementation follows his
ruling on whatever genuine forks the design surfaces.

## His words (add-idea 2026-07-30 03:48, verbatim — the task)

> re the reset when data.json is recieved, yeah its definitely noticeable
> here, theres some ui reset indicators, and selecting text from any of the
> questions deselects on update. selecting quesitons at the top or the project
> name works fine and doesnt deselect. could we use ids on html elements to
> avoid this? or maybe do a check of html contents before rerendering? or use
> like react or something that handles dom differences for us? (Note: Im okay
> introducing react if we dont have it yet, or something equivalent, doesnt
> have to be react exactly as per se). In any case, this feels like a general
> architecture smell that we should investigate and fix properly in a
> principled way.

## The class, and the instance fixes already landed (read them first)

This is the CLASS of which two instance fixes are already in — read both
before designing, because the principled fix must subsume them without
re-opening what they closed:

- **#503 rest-collapse** (landed `6584c7e7`, fold entry in
  `.dreamwork/handoffs.md`): `expand()` emitted no `data-keep`, so the ~2s
  `/mtime` poll's innerHTML rebuild detached open disclosures. Fixed with the
  **#141 idiom** (`snapshotFolds`/`restoreFolds`, stable `data-keep` keys,
  silent restore). His 03:39 data.json suspicion was confirmed right.
- **#494 tooltip reset** (folded earlier): same class, instance level.
- The merge of #503 surfaced a stale full-call literal pin in
  `test_page_reflows_prose_but_not_raw_text` — relevant because it shows the
  render call shape is pinned in tests; your design must say how the pinned
  surface changes.

His own observations to explain: selection inside question cards deselects on
update; selection of the crumb/project name survives — consistent with
**views being pure builders returning `#view`'s innerHTML** (`buildDashboard`,
`buildQuestions`, `buildAnswers`, `buildFile`, `buildReview`, `buildResearch`;
the router swaps them) and the header region not being rebuilt.

His three sanctioned directions (explicitly his, none chosen): **ids on html
elements**, **check html contents before rerendering**, **React or equivalent
DOM-diffing** ("doesnt have to be react exactly").

## The constraint that makes this hard (and why it is P1 design, not a quick patch)

`transitions.md` governs EVERY transition with no size floor, and the route
change is the reference implementation: ghost gestures, the keyed route
dissolve, survivor FLIP, `foldDetailsLocal` travel. Any DOM-diffing layer sits
**between the poll and those gestures** — a naive morph that patches nodes
in-place will fight the departure ghosts and the keyed re-pose machinery. The
design must state, per gesture family, whether the new render path preserves
it, replaces it with something atmospherically equivalent (same gesture,
different mechanism), or changes it (which needs him). Reduced-motion parity
is not optional. Read `transitions.md` and the route-dissolve code before
writing a word of the options.

Also read: the poll/`/mtime` re-render loop in `watch.py`, `data-keep` /
`snapshotFolds` / `restoreFolds` (#141), `foldDetailsLocal` (#503), and the
`watch-design.md` "Views are pure builders" contract.

## What to deliver

`.dreamwork/docs/plans/render-architecture.md`, house style:

1. **The mechanism inventory, measured not assumed.** Enumerate what actually
   resets on a data.json update today: selection, scroll, open disclosures
   (patched), focus, hover/tooltip state, in-flight transitions, canvas/WebGL
   state. For each: the code path that loses it, and whether #141/#503-style
   preservation already covers it. This table is the design's foundation —
   derive it from the code, and where cheap, from a live probe (a scratch
   serve on a guard port with the fixture; ports 39890-39899, check ownership
   first).
2. **A real IGC** (`igc-method.md` + `igc-concepts.md`, vendored #447) over
   the integration shapes — his three plus what the inventory uncovers (e.g.:
   content-hash skip-if-identical; keyed preservation of interactive state
   (widen the #141 idiom); surgical DOM-diff of data-driven regions
   (morphdom-idiom, hand-rolled or vendored); full vdom adoption (React/
   preact/uhtml — weigh bundle, build step, and the transitions.md collision
   honestly)). Goals must include: gestures preserved or equivalently carried
   (transitions.md), no second render authority, selection/scroll/focus
   survive a poll, deploy/serving story unchanged (single-file watch.py is
   the deployed unit — a build step is a real cost, priced not waved).
3. **Open calls for him with recs** — including, if the IGC leaves it live,
   the build-step question (he said "okay introducing react", but the
   single-file deploy is his own architecture; the rec must be honest about
   which way it points). Draft the questions.md entry text (DRAFT — you do
   NOT edit questions.md).
4. **What the instance fixes become** — whether #141/#503's preservation
   idioms stay, get absorbed, or get replaced, and the migration note for
   `data-keep` if so.

## Acceptance criteria

- The reset inventory is a table with a code path per row, and every row was
  checked against the real source (cite line numbers).
- The IGC has ≥4 goal rows and ≥4 idea columns; refutations structural.
- Every transition family in `transitions.md` is named in the design with
  its fate under the recommended shape.
- The single-file deploy constraint is priced in the IGC, not footnoted.
- `python3 lint.py` clean; doc-map row; branch `lane-505arch` in YOUR
  worktree; `git commit --only <paths>`; ONE `## Pending` line appended to
  `.dreamwork/handoffs.md` (append-only, never rewrite; the literal path is
  `.dreamwork/handoffs.md`).

## Report back

The inventory headline (how many distinct reset surfaces, how many already
patched), the IGC survivor or fork + one-line why, the open calls with recs,
the fate of the #141/#503 idioms, and any place his three sanctioned
directions proved wrong against the real code (report plainly — he invites
pushback).
