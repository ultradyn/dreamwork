# Brief — #505 render-architecture implementation (I5: keyed reconciliation of `#view` + hash-skip)

Ledger id: **#505**. Design: `.dreamwork/docs/plans/render-architecture.md`
(merged `5eab68f4`) — read it in full before touching code; every claim in
it is line-cited. His rulings (2026-07-30, questions.md → Answered):

- **Q1 rec — vendored morphdom** (~2KB, framework-free, vendored into the
  client JS the way the page already vendors its SVG-mist pipeline).
- **Q2 MODIFIED — the no-build single-file constraint is LIFTED.** His
  words: "we don't have a no-build single-file constraint. We had a python
  stdlib constraint, but otherwise building the webui bundle and breaking
  up watch.py into modules are good and reasonable things." The python
  stdlib constraint on the SERVER stands. For THIS lane: module-splitting
  is permitted but not required — scope discipline says land the
  reconciler, not a refactor. If you want the client JS as a separate
  served asset to make the vendored diff reviewable, that is authorised;
  a wholesale module split is NOT this lane.
- **Q3 rec — `#view` first** (phase 1; the review-dock `replaceWith`
  stays as-is).
- **Q4 rec — guard the corpse rule** (see below).

## The change (I5 from the design)

The singular seam stays: `setContent` reconciles instead of swapping.
`watch.py:6778`'s `#view.innerHTML = html` becomes: hash-skip
(`if (html === lastHtml) return;`) → parse to fragment → keyed
reconciliation of `#view`'s children against the fragment, keyed per list
by the identities the page already maintains (`data-qid`, `data-aid`,
`data-sha`, `data-review`, `data-keep` — one canonical key per reconciled
element class, reusing the `*_LIST` declarations ~watch.py:7014). Views
stay pure HTML-string builders (G2 — one render authority).

**The binding discipline is the design's load-bearing unstated half:**
today everything re-binds on fresh nodes after every swap. Under
reconciliation, kept nodes KEEP their listeners — binding again
double-binds. Every post-render binding pass that touches reconciled
subtrees must become idempotent (guard-attribute idiom) or move to
delegation. Audit every `bind*`/`querySelectorAll(...).addEventListener`
that runs after `setContent` and state your chosen discipline in the
handoff.

## Increments (small, committed, each independently gated)

1. **Vendor + seam + hash-skip, keep ALL snapshot/restore pairs.** The
   reconciler runs; the 11 hand pairs still run on top (harmless — they
   re-apply what kept nodes already hold). Full guard suite green.
2. **The R1 proof-guard.** A new guard (own-server class, (OUT, PORT))
   that plants a fixture, sets a text selection inside a question card,
   forces a tick (touch the watched file), and asserts the selection is
   non-empty after the tick. This is his bug, fixed as a class — the
   guard is the acceptance test. It must FAIL on master before the seam
   lands (born-red against the real defect, not an injection).
3. **Corpse-rule guard (Q4).** Assert no element carrying
   `.qaghost`/`.ghost` matches a reconciled identity key — same shape as
   `states.mjs`/`morph.mjs`. Red-prove by temporarily reconciling a
   ghost.
4. **Lockstep pair deletion.** Delete `snapshotFolds`/`restoreFolds`,
   `snapshotBdHover`/`restoreBdHover`, `snapshotCardState`/
   `restoreCardState`, `snapshotViewInputs`/`restoreViewInputs`
   (#523's), etc. ONE PAIR PER COMMIT, each with its guard suite green —
   the guards that pinned the pair (bdinput, bdhover, restcollapse,
   states…) are the red-proof surface: if a deletion breaks a carried
   state, its guard FAILs. If a deletion is NOT covered by any guard,
   say so in the handoff and stop deleting there.
5. **Pin update.** `test_watch.py:3691`'s anti-literal changes from the
   absence of `setContent(buildDashboard(data))` to asserting the
   reconcile call — red-proved against the old `innerHTML =` form.

## Hard rules

- **transitions.md governs.** Reconciliation must not turn any travel
  into a teleport or any dissolve into a fade. The transition-fate table
  (design doc, "Every transition family") is the contract; the existing
  motion guards (`motion morph morphhold dissolve dreamfade artifactwrap
  qfade wisp states restcollapse`) are its enforcement — ALL must stay
  green, and any that goes red is a finding, not a nuisance.
- Reduced-motion parity untouched (G5).
- `#dreambg` canvas and the chrome (`renderChrome`) are outside scope —
  the chrome is already the keyed idiom; do not "unify" it.
- Red-proofs by injection + cp restore, each naming its production line.
- Guards take (OUT, PORT), ports 39890-39899, replicate the justfile
  layout for solo runs (`OUT/../target` must be the served fixture —
  mdquote derives its plant dir that way; check your guard's convention).
- Commit `git commit --only <paths>`; new files `git add` first.
- NEVER attn, never pkill -f.

## Lane-owns

The render seam region of watch.py (`setContent`/`setLiveContent`/
snapshot-restore machinery), the vendored diff asset, new guard(s) under
`dev/capture/`, `test_watch.py:3691`'s pin, and the `data-keep` note in
watch-design.md (design says: "snapshotFolds marker" → "reconciliation
key"). mdBlocks/mdRender belongs to lane-525tables — DO NOT touch it;
if the merge race happens, rebase, don't absorb.

## Handoff

Literal Pending line in `.dreamwork/handoffs.md` per increment-set
(`- **#505** · landed \`<sha>\` · … · by lane-505impl — …`): increments
landed, binding discipline chosen, guards green (counts), born-red
evidence for the R1 guard, per-pair deletion evidence, anything noticed
but not fixed.
