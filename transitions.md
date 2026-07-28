# Transitions — the page arrives and departs, it never appears

**The rule, and every other line here is a consequence of it** (human,
2026-07-25): *transitions must be atmospherically suitable, like the
transitions between pages.* The route change is the reference
implementation. Every smaller change — something appearing, disappearing,
expanding, collapsing, changing state, moving — is a smaller instance of
that same gesture, not a different kind of event.

**This applies to all of them.** If a thing on this page becomes visible,
stops being visible, changes size, changes state, or changes place, it is
a transition and it obeys this document. "It is only a small toggle" is
how a page ends up with one gesture that snaps among a hundred that
drift, and the snap is the one the eye catches.

Extracted from `watch-design.md` on 2026-07-25 so it can be pointed at
directly; that file remains the styleguide and holds tokens, type,
components and copy. This is the single source for motion — there is no
second description of it anywhere.

## Checking a transition

Three consecutive batches on 2026-07-25 each found a real motion bug that
every existing check had passed over, and the reason was the same each
time: **all three ended in exactly the right place and were wrong in the
middle.** A teleport, a confirmation lit on frame 0, a snap at the end of
a travel.

So, for anything in this document:

- **An end-state check cannot fail on a motion bug, and neither can "did
  it move".** Assert that some captured frame is *part-way* between the
  two ends — a snap has none there, at any frame rate. The helper is
  `between(vals, first, last)` with a ~3% deadband so a frame that really
  is an end does not read as travel: `reviewsplit.mjs:145` is where it
  started and `headertravel.mjs`, `regroup.mjs`, `morph.mjs` and
  `qsec.mjs` now all carry it verbatim. Copy the helper, not a file —
  it is deliberately one idiom, and the reason is that `qsec` spent a
  day holding both (the fade converted, the travel beside it still
  counting positions) and read as if that were a considered distinction
  rather than an unfinished job (#311).
- **A part-way count needs a vacuity precondition beside it, and that
  one IS a literal.** `between(...) >= 1` passes on a 2px twitch, so
  assert the span first — and the span's floor is a pixel distance,
  which is a property of the fixture's layout and not of the box, so a
  literal well below the measured value is exactly right there. This
  is the one place the never-a-literal rule does **not** apply, and
  saying so costs a line because three commits described their floors
  as "derived at runtime, never literals" when what is derived is the
  *measurement they print* and the floor is a deliberate constant. Both
  halves matter: derive and print the real span so the number in the
  output is today's, and keep the floor a constant so it fails when the
  subject stops moving. **One literal PER MOTION, never one shared
  across motions with different travel** (#441, 2026-07-29): a guard
  that folds *and* grows held a single `MIN_HEIGHT_SPAN = 20` over a
  ~193px fold and a ~23px grow, and the margin was invisible in the
  output — 10x headroom on one, ~0x on the other (the minimum real
  single-line note grow measured at exactly 20px, so the floor sat *on*
  the signal, not under it). Splitting gives each motion its own floor
  with its measurement recorded beside it; the *shape* stays a literal
  because a floor derived from the span it validates can never fail (any
  observed span satisfies its own fraction), which is the #444 trap one
  level down. Span is deterministic on a frozen fixture (a property of
  its CSS + content); only the sample count varies with load, so a
  per-motion literal pegged below the minimum real signal holds at every
  load.
- **…but never assert an absolute COUNT of distinct positions.** It reads
  as the same rule and it is not: `uniq(positions).length >= 8` says "this
  machine rendered eight frames in 850ms", which is a fact about the box,
  not about the motion. Five guards encoded it — `headertravel` (>= 8
  widths), `regroup` and `morph` (>= 6 positions), and `qsec` twice
  (>= 8 positions, >= 8 heights) — and a sixth, `states.mjs`, held three
  more (`uniq(h).length >= 6` on unfold / fold / tick-grow heights). **All
  are now converted** to `between()` with a sample-count precondition
  first (#333, after #414's confirmation shape). A seventh held out longest
  by NAMING a stronger claim: `prominence.mjs` asserted
  `new Set(tops.map(Math.round)).size >= 6` as "continuous, not a couple
  of jumps" and defended it as not-this-rule. It was this rule —
  "continuous" is no more frame-rate-decidable than "six frames" (two
  teleports and a starved smooth travel both yield few positions, for
  opposite reasons), and the assertion failed inside a loaded `just test`
  while passing solo, confirmation's failure at a second site. Now
  `midFrames(tops) >= 1`, the shared helper `confirmation` uses (#414),
  with the play-then-snap failure it was loosely proxying owned by the
  late-arrival check beside it. The opposite assertion — reduced-motion
  does NOT animate, so `uniq(h).length <= 3` — remains a count on
  purpose; converting it would destroy the check.

  `dismiss` holds two more on one trace with the terminal-state shape
  below, which is why "some checks passed" is not evidence a loaded run
  was sound: its neighbours got EASIER as frames spread apart while the
  terminal one got harder. They went red on a
  commit that was fine, twice, for two different amounts of load, then
  passed when re-run with fewer guards in flight. Base `f72f730` failed
  the threshold in 3 of 5 runs on its own.
- **The floor is ONE part-way frame, and not a fraction or a bigger
  count.** Both of those are still bets on the frame rate. Measured on
  `headertravel`'s 1s column glide: idle, 31 frames with **5** part-way;
  under six added CPU burners, 14 frames with **2**. So a floor of 2 was
  already sitting exactly on the line — and note that 5 of 31 is nowhere
  near "most", because the trace window deliberately outlives the
  transition and most frames sit at the settled end. A fraction would
  therefore be tuned to the window length, which is the literal-with-an
  -expiry-date trap one bullet down. Zero-versus-some is the whole
  distinction between a snap and a travel; whether the travel is too
  FAST is a separate question, answered by the no-frame-past-the-end rule
  above, and this assertion must not smuggle it in.
  (#311, measured 2026-07-27 at load 40-90 on 16 cores.)
- **Bound the trace window to the interaction.** A guard that watches
  long enough will see a later tick supply the movement it was asserting;
  one traced 5.2s across a 1.6s hold and was green over a real teleport
  for a day.
- **Drive the real gesture on the real route**, not the one that is
  easiest to automate.
- **Do not anchor an arrival assertion to a clock.** "It has arrived by
  `at(950)`" is a trap that scales with distance: it works at ~20px of
  travel and fails at 1246px, where a perfectly clean ease measured 32px
  short — the guard was reporting its own pointer-click latency, not the
  animation. Assert the timing-free form instead: **no frame goes PAST
  the final position**, and the last frame is at it. Catches the same
  failures (overshoot, snap, short-fall) and cannot be defeated by how
  far the thing happens to move. (dreamer-qsec, #196, after
  `prominence.mjs`'s `at(950)` broke on a full-section fold.)
- **Never measure geometry beneath an ancestor that is mid-transform.**
  A transformed ancestor redefines what a position *means* for everything
  under it: during a reveal that scales from 0.97, every
  `getBoundingClientRect` reads 3% small, and the error **multiplies with
  distance from the transform origin** — so the element nearest the
  origin measures clean while the farthest is pixels off, which is why it
  presents as intermittent and why a check that samples only one element
  passes over it. Unlike everything above, this one misleads the *code*,
  not just the check: paint after the travel ends, or divide the current
  scale back out (`rect.width / offsetWidth`, exactly 1 when nothing is
  mid-transform). One rule, four sightings: #198's indicator, #170,
  #160, and `position:fixed` under any transformed ancestor.
  (dreamer-qsec, #198, measured at `matrix(0.97, …)`.)
- **A wrong value that something else routinely overwrites is not a
  transient.** It is a permanent bug with a short, unreliable lifetime —
  #198 "autocorrected" only because unrelated re-renders repaint
  indicators every few seconds on a live target. A check may bound its
  window tightly, but it must *prove* the laundering path rather than
  trust it (break the value by hand, force one re-render, watch it come
  back) — especially against the frozen fixture, where nothing
  re-renders and a sloppy window passes by luck. (dreamer-qsec, #198.)
- **Do not round a per-frame trace.** Rounding to whole pixels reported a
  clean 2.1px ease as a snap — an instrument bug that presents as a feature
  bug, and the guard whose gesture is *small* is the one it bites. The
  idiom is live: `reviewsplit.mjs`'s `distinct()` rounds, and it is only
  safe there because its travel assertions require >=60px of movement.
  Either keep the raw values or state the minimum travel the rounding
  tolerates. (#308, found in #142's dream at one archive from being lost.)
- **Do not assert a terminal state inside a fixed sampling window.** It is
  the mirror image of the count trap and it fails for the opposite reason:
  `dismiss.mjs:134` asserts `ops.at(-1) >= 95`, i.e. "the fade finished
  within 700ms of sampling", so a slow box closes the window mid-fade and
  the check reddens over a perfect animation. Wait on the transition's own
  completion (`getAnimations()`, `transitionend`) and *then* assert.
  **The sharpest evidence that a loaded run cannot be partly trusted comes
  from this one trace:** while `ops.at(-1) >= 95` went red, its two
  neighbours on the same frames — `>= 6` distinct opacities and `>= 4`
  distinct transforms — got *easier*, because slow frames spread further
  apart. Two assertions over one trace, moving in opposite directions with
  load. So "the other checks on that trace passed" is never evidence the
  run was sound. (#311, 2026-07-27.)
- **The three above are one mistake with three faces: a motion check must
  not encode a property of the machine.** Frame count, pixel rounding and
  elapsed-time windows are all facts about the box, and each one turns a
  guard into a load meter that reports its findings as feature bugs. The
  timing-free forms already in this list — no frame past the final
  position, frames strictly part-way, wait for completion — are the same
  instinct applied three ways. When a motion guard goes red, the first
  question is which of these it encodes, and the second is what else the
  box was doing.
- **A compositor-driven CSS transition is invisible to a starved rAF
  sampler, and `transitionstart` is its load-independent snap detector.**
  `opacity` and `transform` transitions run on the **compositor** in real
  time; `requestAnimationFrame` runs on the **main thread**, which the
  page's own `#dreambg` shader and host load keep busy. Under contention
  the compositor animates the property while **zero** rAF callbacks fire
  inside the transition window — so `midFrames >= 1` reads 0 over a
  perfect animation, the exact false positive #414's form was built to
  prevent. The fix is not a better sampler but a different question:
  `transitionstart` fires iff the browser registered a CSS transition for
  the property — load-independent because it asks the browser, not the
  sampler. Use it as the snap detector; keep `midFrames >= 1` as the
  motion evidence when the trace sampled inside the window, and fall back
  to `transitionRan` when it did not. **FLIP animations do NOT have this
  gap**: the FLIP sets `element.style.transform` per frame on the main
  thread, so the sampler and the animation share the thread and stay in
  sync. Measured (#442, 2026-07-28): confirmation's 350ms `.depart`
  opacity transition drew zero rAF samples inside its window in 6/6 runs
  at load 40-63 on 16 cores; `transitionstart` fired in every one. The
  helpers are `transitionWindow` and `framesInWindow` in `dom.mjs`.
- **Existence is the snap detector; do not assert observed duration against
  the declared one (#444).** `transitionWindow` returns `dur` (end − start),
  so the width is measurable with no rAF sampling — load-independent by the
  same argument that motivated `#442`. That does **not** make a duration
  floor earn its keep. Measured 2026-07-28 on confirmation's main
  departure (declared `.cmdmsg` opacity `.35s` = 350ms) at load 36–42 on 16
  cores, six consecutive green runs: **239, 371, 354, 329, 307, 348 ms**.
  `#442` under 8 burners had already measured **289–665 ms** for the same
  gesture. A ±20% band around 350 (280–420) fails the green set on 239; a
  band wide enough for 665 only excludes pathologies the STYLE constant
  already forbids. Separately, pairing `ends.at(idx)` with `starts.at(idx)`
  independently produced **negative** popout-departure durs (−68…−178ms)
  when an opacity end from a transition that started *before* `afterT`
  landed after it — so `dur` is not even always the width of the transition
  under test (the helper now pairs the first end at-or-after the chosen
  start; the measurement still stands as evidence that the instrument was
  not ready to be a gate). **A check that restates the CSS it reads is not
  a check**: the declared duration lives in `watch.py`'s STYLE (and the
  styleguide's single-source rule), and existence already asks the browser
  whether it registered a transition. Shortening the declaration to `1ms`
  is a styleguide edit, not a silent motion bug the sampler can uniquely
  catch. Log `dur` as a diagnostic; assert `ran`. The red-proof of this
  refusal is `test_duration_refusal.py`: replaying the six measured green
  durs against a ±20% band fails, and the confirmation guard is asserted
  not to floor on `dur`/`win.dur`.
- **Show the check RED on the current behaviour before trusting it.**
- **Verify reduced-motion too** — it is a hard contract below, and it is
  the half nobody looks at.

## Motion language (authored across the transition work)

The page *dreams*: motion is soft, slow, and never crisp-mechanical. It is
also strictly opt-in — most state changes do **not** animate.

**Things that move, slide** (human, 2026-07-25): "in general when things
need to move they should slide gently, ethereally, not jump around." Read
this as the tie-breaker it is — it does not overturn the opt-in rule (a
live tick still re-renders instantly), but wherever the page *has* decided
to change layout, the elements that survive travel to their new positions
instead of teleporting. FLIP is the mechanism; reduced-motion is the
exception; an element leaving fades rather than vanishing.

- **When transitions apply.** Route changes (client nav) dissolve. The live
  mtime tick commits its new DOM **immediately** — liveness never waits on an
  animation — but where that re-render *moves* something that survived, the
  survivor travels to its new place rather than appearing there (the
  regroup, below). A disclosure that changes the page's layout folds and
  unfolds on that same travel — a card's, a thread's, and the dashboard's
  questions section (*The section fold*, below). The composer reveals on a
  soft blur drift. Nothing else animates.
- **The regroup** (a question is answered). One moment seen two ways: the
  questions below close the gap it left (#104), and the question itself
  travels to its new heading rather than being re-set there (#77). One
  mechanism — a FLIP over the list keyed by **`data-qid`**, the question's
  own identity, which survives the move its positional `data-qkey` cannot.
  A card whose **heading changed** gets the lifted-hero morph so the eye
  follows it across the page; a card that merely shifted slides. Use the
  heading, not the card's state class: the submit morph already changed that
  class locally when the answer was sent, so by regroup time it reports no
  change even as the card is about to cross the page. A card gone entirely
  dreams away at the rect it occupied, which is why the snapshot clones every
  card up front — after the re-render there is no node left to animate, and
  you cannot know in advance which will go.
- **The state matrix, and the one mechanism under it.** The three question
  states are one axis, so their transitions are one matrix, and every cell
  goes through `regroupCards` → `travelCard`. A card **travels** from the
  rect it had to the rect it has — in position *and* in height — and if it
  crossed to a different **heading** it is lifted while it goes (raised,
  blurred, dimmed, resolving) so the eye follows that one card.

  | cell | who acts | what happens |
  |---|---|---|
  | open → awaiting | he answers | the submit morph restates the card in place (the typed text lifts from the box into the answer, a ripple) **and regroups the list around it**, then the tick's regroup travels it to its new heading, lifted. The wisp starts at its dim keyframe and breathes up, so it arrives rather than snapping on. |
  | same card, a note lands | **he** adds a follow-up | the note lifts from the box into the thread and the card grows; same seam, same regroup |
  | awaiting → folded | the loop folds it | travels, lifted; the height collapses; the departing body dreams away |
  | open → folded | the loop answers it itself | the same, with no wisp ever |
  | folded → open/awaiting | a follow-up reopens it | travels, lifted; the height grows; the arriving body eases in |
  | awaiting → open | the loop drops the answer | travels, lifted; rail and wisp leave with the old node |
  | same state, moved | a neighbour left, a note landed | slides; if it also resized, the height travels |
  | folded ↔ expanded | **he** clicks the summary | the same snapshot and the same regroup — his own expand is not a special case, and routing it through the shared path is what gives it the neighbours' motion for free |
| thread ↔ expanded | **he** opens a settled thread | the same cell one level down: the card resizes, so the cards below it are carried. The reveal and the ghost are the disclosure's own contents, not the card's (see *`expand` is structure*) |
  | gone | the entry was deleted | dreams away at the rect it occupied |
  | arrived | a new question | `.dreamin`: snap, then ease in |

  Five things in there are not obvious and all five were bugs first:

  - **Height, never scale.** `flipDock` morphs by `scale()`, which is right
    for the review dock, where the card really does change column. In the
    list the column never changes but the height now can, by a factor of
    fifteen, because folding collapses the card. A scale morph would squash
    the text by that ratio at frame 0 and read as a stretch, not a fold.
  - **A body that leaves fades; a body that arrives eases in.** *"When it
    folds in, the body shouldn't disappear all at once"* (human,
    2026-07-25). The new node is already the folded one, so there is no live
    body left to animate — which is what the up-front clone in
    `snapshotCards` is for. `dreamAway` ghosts it at the rect it occupied,
    **clipped to below the line the survivor still fills**, on the page's one
    departure idiom. Unfolding is that moment run backwards, so the revealed
    children get `.qreveal` + `.dreamin`.
  - **Cards are processed in DOM order, and that is load-bearing.** A
    resizing card's own height animation carries everything below it —
    continuously, for free, and welded to the card it is following. So the
    FLIP only handles the **residual**: whatever moved for some other reason.
    Restoring a card's old height before the next is measured is exactly what
    makes the next card's `now` mean "where it would be if only that resize
    had happened". FLIPping the full difference instead moves a neighbour
    twice, once by transform and once by layout, and snaps it back at the end.
  - **A ghost is a corpse and must not keep the card's address.** It is a
    clone appended to `.wrap`, so it arrives carrying `data-qid` — and every
    `.qa[data-qid]` walk on the page would then find it: `snapshotCards`
    would capture its absolute rect as the question's, `restoreCardState`
    would restore his typing into it, and a per-frame trace measures it
    instead of the card animating underneath (which is how this was found).
    `dreamAway` strips the identity at the door rather than teaching six
    lookups to skip it.
  - **The morph is INSIDE this matrix, not beside it** (#191). `sendAnswer`
    restated its card with `card.innerHTML = qaInner(…)` and called neither
    `snapshotCards` nor `regroupCards`, so the one gesture this page has most
    carefully taught to travel was the only one that teleported: the cards
    below went **744 → 791 in two distinct positions, with no transform**,
    across 354 frames. `sendComment` had the identical shape — a note lands
    inside the card, so the card grows — and was fixed in the same breath,
    because finding one done and one not is how a reader concludes the rule is
    optional. Both now snapshot → mutate → regroup, on the seam the
    `.qa details > summary` handler was already using three functions away.

    **What the morph keeps for itself is its own card's CONTENTS.**
    `regroupCards`'s `restated` argument names the card the caller is
    animating, and skips the body ghost/reveal for it: the answer (or the
    note) already has its own lifted-hero arrival, and the body, the thread
    and the compose box were on screen before and after — re-fading them says
    a change happened where none did, which is #128's rule one level up. Its
    **height** still travels, and the height is what carries every card below
    it, for free, welded to the card they are following.

  The guard is `dev/capture/states.mjs`, and its assertion is deliberately
  about **outcome, not mechanism**: every card that ended somewhere else
  moved through the middle rather than jumping. The first version demanded
  an inline transform on everything that moved and was wrong — a card
  riding an animated height above it travels perfectly with no transform of
  its own, and the mechanism check would have forbidden the better motion.
  It spells that as frames strictly part-way between the height ends
  (`between()`, #333), with the sample-count precondition first so a
  starved window and a real snap print distinguishable lines (#414). The
  reduced-motion half keeps an absolute count (`uniq(h).length <= 3`) —
  the opposite assertion, and converting it would destroy the check.
- **The section fold** (#196) — the same moment one level up, and the last
  gesture on this page that was still snapping. His report: clicking
  "questions · 8 to answer" makes the questions *"just appear and
  disappear"*. It does not go through `regroupCards` — the cards inside have
  no geometry while the section is shut, and a FLIP from a zero rect is a
  slide in from the page's corner — but it is the card fold with the roles
  enlarged, so it reuses the same three pieces: `travelCard` for the height
  (which carries reviews, files, status and the tint picker for free, welded
  to the section they follow), `revealBody` for the arrival, `dreamAway` for
  the departure. Its direction needed no sign of its own: the panels below
  travel **up** to close the gap and the standing ghost rises, so #174 was
  already satisfied — the commits panel is the exception, not the rule.

  Two shared helpers had to grow for it, and both were latent bugs rather
  than new features:

  - **`travelCard` sets `box-sizing:border-box` while it animates height.**
    The two numbers being interpolated come from `getBoundingClientRect`,
    which is a *border* box; `height` is a *content* box by default. That was
    a distinction without a difference while only `.qa` and `.git .commit`
    travelled — neither has vertical padding — and then a `<details>` came
    through, which gains #169's `.5rem` of air on the frame it opens. Left
    alone the travel plays 16px **past** where it ends and snaps back when the
    inline height is cleared. Nothing about the end state can see that.
  - **A corpse holds no address THROUGHOUT ITS SUBTREE, not just at the
    root.** `dreamAway` stripped `data-qid`/`data-qkey`/`data-sha` from the
    node, which was the whole identity while the only ghosts were one card and
    one row. The section ghost is a clone of the entire open `<details>`: it
    carries `data-keep="qsec"` and every card inside it. `snapshotFolds` walks
    `details[data-keep]` and the last match wins — a ghost is appended to
    `.wrap`, i.e. last — so one surviving attribute means the next tick reads
    the section as open and re-opens it under him, a second after he shut it.

  The guard is `dev/capture/qsec.mjs`. Two of its assertions are worth
  copying: the count of distinct positions the panel *below* the section
  visits (a snap visits two, and every other check passes on it), and that no
  frame goes **past** the final position — the border-box failure stated as
  the thing it does, with no dependence on when the traced click landed.

  **The remaining instant disclosures are unexamined, not decided.** The
  plain `expand()` peeks — dreams, the archive, the `.md` files, the status
  overflow — still toggle natively. The rule that used to excuse them was
  "nothing that moves sits below the toggle", and that rule was checkably
  false about the questions section for the whole life of #141; it is no
  truer about these. Do not read their silence as a decision.
- **The departure has two beats** (#277). A leaving element should dissolve
  *in place first*, then leave — not blur and travel at the same moment,
  which reads as "mush then snap" because the thing is already moving by the
  time it starts dissolving. The single `.gone` class (blur + opacity +
  travel, all on one `.7s` transition) started all three together, so the
  dissolve and the departure were one undifferentiated leg. The fix is a
  `.pregone` phase on the same single ghost: blur `0 → 8px`, opacity
  `1 → .8`, at most `2px` upward drift, over `180ms` on its own shorter
  transition; then `.gone` sends it away on the `.7s` that was always there.
  Removing `.pregone` restores `.qaghost`'s `.7s`, and the browser retargets
  from the dissolve's mid-values to `.gone`'s targets, so the two beats chain
  continuously without a seam. `.gone`'s blur matches `.pregone`'s peak
  (`8px`), so the corpse never un-blurs as it leaves — it dissolves, then
  departs at the same softness. Total lifetime stays under `1.1s`.

  The data/DOM commit and the survivor FLIP stay **immediate** — the corpse
  dreamfades while the live list is already correct, exactly as before. v1
  applies to question/answer rows, nested thread bodies, and section folds;
  the commits panel **skips** `.pregone`, because its gesture is the
  grow-and-fall, and the phase's `2px` upward drift would fight the `14px`
  downward fall its neighbours are travelling. Under reduced motion the
  ghost never exists at all (`regroupCards` and `foldDetailsLocal` gate the
  whole departure on `rmr`), so the phase is simply unreachable.

  The guard is `dev/capture/dreamfade.mjs`. Its load-bearing assertions are
  **phase separation**: `.pregone` must appear before `.gone` (class
  membership), blur must reach ≥5px before opacity drops below 0.4
  (dissolve-first ordering), and blur must not decrease during departure
  (`.gone`'s blur matches `.pregone`'s peak — the corpse does not un-blur as
  it leaves). Reduced motion is traced on the same gesture and asserts no
  ghost is ever created.
- **The dream dissolve** (route change). The outgoing view becomes a
  `.ghost` (z-index above `#view`) that liquifies into a swirling mist and
  lifts up and toward the viewer as it fades — dissolving *in front*. The
  incoming view surfaces from *behind and below*, in depth: `.wrap` carries
  a `perspective`, and `#view.enter` starts pushed back (`translateZ`),
  lower and scaled down, at true opacity 0, then drifts forward into focus.
  ~1.15s with a hazy dwell (`DREAM_MS`); opacity + 3D transform ride CSS,
  the mist is JS-enveloped. The `#dreambg` shader stirs in sympathy (a
  `warp` pulse deepening the curl advection + a centred twist). Each
  destination has its own turbulence `SEED` and `TINT`.
- **True-zero start — the enter-snap rule.** Because `#view` carries an
  always-on opacity/transform transition, the enter (start) state **must**
  set `transition:none` so it *snaps* to opacity 0 / pushed-back; otherwise
  adding the class animates *toward* 0 and the class is removed a frame
  later, so opacity never leaves ~1 (the incoming "pops in" instead of
  fading up from nothing). Snap the start, force a reflow, then remove the
  class on the next frame to animate in. A brief opacity delay keeps it
  genuinely absent for the first ~150ms so it emerges rather than blends.
  **Never leave `.dreamin` on settled content (#293).** `/answers` open
  records once baked the class into every row's HTML; with no rAF removal they
  stayed at opacity 0 forever (including after hard refresh) while still
  taking pointer hits. `.dreamin` is a start pose, not a skin. Live-added open
  rows use a one-shot keyed arrival (`revealNewOpenAsks`): start pose on new
  `data-aqid` only, rAF remove; reduced motion never applies the start pose.
  First paint / hard refresh settles visible without replaying arrival.
- **The mist filter — the load-bearing rule.** Put *all* softening (blur
  **and** displacement) inside **one** SVG filter
  (`feTurbulence`→`feDisplacementMap`→`feGaussianBlur`) driven per-frame
  from rAF; keep only `opacity`/`transform` on CSS. You cannot CSS-tween a
  `filter` that holds a non-interpolable `url(#…)`. Clear the inline filter
  at rest so the settled element is pixel-crisp and zero-cost.
  **#449: this mist is TEMPORARILY OFF** (human ruling 2026-07-29: "let's
  try temporarily disabling the svg filter. we can make up for it as best we
  can with css"). Measured on the route he named — question→review — by A/B
  on this never-idle host (the only defensible comparison here; an absolute
  threshold is a load-meter, refused on #444's ground). The capture is
  `dev/capture/dissolveperf.mjs`, the guard is `dev/capture/dissolve.mjs`.
  The cost is per-frame `feTurbulence` rasterization, and the levers you
  would expect do not move it: freezing `baseFrequency` ≈ baseline (the
  field is *not* invalidated by the per-frame rewrite, contra the first
  guess); freezing **all six** `stepFx` attribute writes ≈ baseline — and
  that filter ran with `scale=0`/`stdDeviation=0`, so it was
  applied-but-inert and still cost the same, which is the proof: Chrome
  rasterizes `feTurbulence` afresh every frame and does **not** cache it
  across frames, whatever the attributes do. Clamping the ghost's filtered
  area 42% (553×1557→553×900, geometry confirmed mid-dissolve) ≈ baseline,
  so filtered-layer **area is not the lever** either — correcting the claim
  this bullet once made. Removing **both** dissolve filters recovered
  +100–128% of rAF frames, and that is what shipped. The filters stay
  defined and `stepFx` stays in place behind a single `MIST_ON` switch
  (const in `crossfade`), so restoring the liquify is one edit when a
  cheaper mechanism exists. CSS compositor `blur()` on the ghost (grows
  `0→7px` as it departs) and `#view` (`5px→0` as it arrives) carries the
  haze the mist gave — confirmed free on SwiftShader (≈ no-blur in the same
  run), and the gesture still arrives and departs (`dissolve.mjs` proves it
  via `transitionstart`, never an end-state assert). The non-refuted
  successor is the human's texture idea done as the one escape from
  per-frame regeneration: pre-render the noise **once** to a canvas/`<img>`
  and consume it via `feImage`, animating the field by `feOffset`/`feTile`
  or two interfering layers. Whether Chrome caches an `feImage` source
  across frames, and whether a translated static field reads as the gesture
  evolving, are the successor's first questions.
- **Lifted-hero FLIP** (shared-element morph, e.g. question → review dock).
  Measure the source rect, render the destination, invert to the source,
  play to identity — but the dream twist is a blurred, low-opacity drift,
  not a reveal.js slide. When the morph crosses a full view-swap, **lift the
  hero above the dissolve** (z-index, higher opacity floor, less own-blur)
  and make its glide **outlast** the dissolve, or it drowns in the page mist
  and reads as "page changed + thing appeared" rather than "thing
  travelled".
- **The ripple.** A soft expanding ring marks a received command; a felt
  pulse, not a modal.
- **The composer's sliding indicator.** Choosing a command kind slides the
  selection background to it (~.3s, the dream easing) — the composer's one
  piece of crisp motion. It lands without sliding on open and on reflow; see
  The composer.
- **Composer success confirmation** (#255) and **panel courtesy-close**
  (#131/#291). Main and popped-out composers use one `confirmationFor`
  lifecycle. Success arrives through `.dreamin`, remains readable for about
  five seconds even if a new draft begins (while the panel is still open),
  then departs by fading, blurring and drifting upward before it clears. The
  panel's auto-dismiss is a separate ~1.5s courtesy (`CMD_DISMISS_MS`); #255
  briefly tied it to the confirm hold and #291 restored the split. Typing
  cancels only the courtesy; left alone, courtesy close is destruction and
  hard-clears with the panel. The courtesy applies only to the transient main
  panel: an explicitly opened command popout is persistent and never auto-closes;
  it keeps the shared confirmation lifecycle until explicit close/`pagehide`.
  Manual close, route change and popout `pagehide` hard-clean immediately and invalidate timers, listeners and in-flight
  attempt callbacks. Rejection/connection/validation claims replace success
  immediately because falsehood must not
  linger through a gentle exit. Reduced motion keeps the hold and clear but
  snaps visual states. `confirmation.mjs` traces the real main delayed-POST
  race, close, persistent-popout and reduced phases; `dismiss.mjs` proves the ~1.5s
  courtesy vs the typing-cancels path; normal departure must show many
  intermediate opacity/transform values, reduced departure none.
- **Answer-submit morph.** Submitting an answer (button or **Ctrl/Cmd+Enter**,
  which works from any answer box) *is* the confirmation: the card reshapes
  in place into its answered-awaiting-fold state and the typed text lifts
  from the box into the rendered answer (the lifted-hero FLIP — the answer
  is the tracked element), a ripple accenting it, **and the list regroups
  around it** so the cards below travel rather than jumping the height delta
  (#191, above). The live re-render is held for `MORPH_HOLD_MS` (1250ms —
  #234: flipDock's 1150ms transform is the longest visible leg of the morph,
  plus a beat of slack; the 850ms card travel and the ripple finish inside
  it, and the old flat 1600ms was padding) so the morph settles before the
  loop's fresh data regroups the card. reduced-motion swaps straight to
  the answered state.

- **Missing-aid answered disclosure (#250).** `/answers` answered records
  with a content-stable `aid` expand through the keyed list path
  (`.aq.answered[data-aid]` + `ANSWER_LIST`). A record that has **no** `aid`
  still matches `.aq.answered > summary`, so the shared expand handler's
  `preventDefault` would leave it dead if the host lookup failed closed. It
  folds instead via `foldDetailsLocal` — height travel + body reveal/ghost,
  the same pieces as the section fold — with **no** `data-keep` and **no**
  invented list key. Open does not survive the tick. reduced-motion toggles
  immediately; function stays.

  **The hold is why this hid for so long, and the lesson is about the guard's
  WINDOW rather than about its assertions.** `regroup.mjs` submits through the
  real UI too, but it traces 5.2s — past the hold — so the tick's own regroup
  travels the neighbour, and every "it slid" check passes over a teleport that
  happened a second and a half earlier. `dev/capture/morph.mjs` traces
  **1200ms**, inside the hold, and its load-bearing assertion is that the card
  node was **never replaced** across the window: `card.innerHTML = …` keeps the
  node and a tick's list swap does not, so whatever moved, the *morph* moved.
  It runs four phases (answer/note × normal/reduced) on its own server and a
  pristine target each time, because answering the first open question changes
  which card the next phase would pick. The hold ITSELF is measured by
  `dev/capture/morphhold.mjs` (#234): it drives `tick()` over a forced
  /mtime change — blocked on every probe inside the hold, released ~1250ms
  after the hold is set, red against the old 1600ms value — with the race
  run in page time, because a Playwright roundtrip costs most of the window
  being measured.
- **The awaiting-fold wisp — the one standing exception to "opt-in".**
  Everything else on this page moves only in response to something; the
  awaiting-fold state breathes continuously, on purpose, because it is the
  only genuinely **in-progress** thing here: the human has answered and the
  loop has not yet folded it. Say that out loud whenever this rule is
  re-read, or it looks like the opt-in rule rotted. A wisp of accent drifts
  along a 2px rail and across the `answered · awaiting fold` label, ~5.5s,
  **fading in and out** rather than sweeping — a breath, not a spinner, and
  ambient in the way the shader is. One envelope duration and easing for both
  halves, so they read as one organism rather than two effects.

  **The cost is bounded by construction, not by a measurement that can
  drift**: the keyframes touch only `opacity` and `background-position`, and
  the animated boxes are a 2px rail and one short inline-block label (the
  label is inline-block precisely so its box hugs the words instead of
  invalidating a full-column strip to say nothing). Measured anyway:
  p95 frame time 16.8ms with the wisp, 16.9ms with every animation killed —
  indistinguishable at vsync.

  Under reduced motion the wisp **holds still at its brightest** rather than
  disappearing: the state must still read as in-progress with no motion at
  all. Legibility is safe by construction too — the gradient's darkest stop
  is `--dim`, the colour the label had before it moved.

  `dev/capture/wisp.mjs` guards all three claims, and one of its checks is
  worth knowing about: counting direction reversals does **not** tell a
  breath from a sawtooth, because a sweep that snaps back to its start also
  turns around twice per cycle. A deliberately introduced one-way sweep
  passed the first version of that check. What separates them is how *long*
  the fall takes — a breath spends about as long fading out as fading in, a
  sawtooth spends one frame — so the assertion is on the fraction of moving
  samples that are falling.
- **Run-mode 10s arm (#290).** Selecting a main-dreamer mode does not
  POST immediately: a shared pending deadline drains for 10s (linear bar
  100%→0% plus tabular `arms in Ns` text), and every reselection resets
  that deadline. The commit is one POST + one events line only when the
  mode actually changes. Reduced motion **hides the bar** and keeps the
  second-by-second text countdown and the same application time —
  function identical, continuous width animation gone. Cross-tab pending
  rides `localStorage` keyed by absolute target; do not invent a second
  countdown. Guard: `dev/capture/runmode.mjs` (intermediate bar widths
  under motion, ≤2 under RM, reset, event exactly-once, hierarchical
  disabled).
- **Run-mode description morph (#300).** One shared `#rundesc` shell under
  the chips explains the hovered/focused mode. **First arrival** snaps the
  shell to a pose (opacity 0, blur, 4px rise) then eases in on the page's
  atmospheric envelope; **final departure** (Escape, pointer-leave, blur)
  adds `.depart` and dissolves upward — the same soft exit as `.cmdmsg`.
  **Button→button** holds the shell fixed (`min-height` so geometry does
  not jump) while `.rundesc-text` dissolves (`.out`: opacity→0, blur 6px)
  and the new sentence resolves (`.in` start pose, then clear). Rapid
  hover retargets the pending mode without restarting the dissolve, so a
  fast sweep still lands the last mode rather than cancelling forever.
  Reduced motion snaps text with identical copy and `aria-describedby`.
  Hover/focus/dismiss are pure presentation — they must not arm, write
  pending, or POST. Guard: `dev/capture/rundesc.mjs` (one surface,
  geometry span, zero side effects including arm countdown + pending
  localStorage, rAF `between()` on text opacity, RM parity, hover≡focus).
- **The review split (#305) — where a DRAG is the one thing that does not
  travel.** `/review`'s two columns are separated by an invisible bar he can
  drag. Dragging is *continuous input*: his pointer already supplies every
  intermediate position, and a transition on the grid would put the columns
  behind his hand. A **keyed** step is a discrete state change and is
  therefore exactly what this document is about, so it travels — the width
  lives in a registered custom property (`@property --rsplit`) and `.rkeyed`
  lends it the column's own easing (`.38s`, the dissolve's curve) for that
  gesture only. Same rule as everywhere else, read through what the gesture
  IS: the class is added on a key and removed on a pointer.

  The bar itself appears and disappears, so it obeys this too: the hairline
  fades in on hover/focus/drag over `.45s` and widens to 2px when focused,
  rather than blinking on.

  The two **fades at the ends of the question column** are states with two
  ends each, so they cross rather than switch: the band over the text passing
  under the answer box lifts over `.45s` when the body ends at the box and
  comes back when he scrolls up, and the head of the column dissolves over the
  same `.45s` once anything is above it (`@property --qfade`, the mask depth —
  a plain `mask-image` swap has nothing to interpolate, which is exactly why
  the depth is a registered property). Both are driven by one read of the
  scroll, so the gesture that changes them is his scrolling, not a class the
  page decides to set.

  Reduced motion keeps all of it functional and drops the timing: the keyed
  step lands in one position, the hairline appears at once, both fades reach
  the same rest states in one step, and the drag is unchanged, because it
  never animated.

  `dev/capture/reviewsplit.mjs` asserts the middle: the count of distinct
  intermediate widths a keyed step visits (a snap visits two) plus the count
  of frames strictly *between* the ends, which is the frame-rate-free half —
  a loaded SwiftShader box draws eight frames in a `.38s` step, so a raw
  position count would red on the machine rather than on the page. Its
  reduced-motion phase asserts ≤2 on the same gesture, which is what makes
  the pair mean something. The fades are traced the same way, with one extra
  trap worth knowing: a pseudo-element with `content:none` is never generated
  and still reports `opacity:1` from `getComputedStyle`, so a band that had
  been deleted outright read as *present and fully lit*. Ask `content` whether
  it exists and `display` whether it is drawn — the version that asked only
  one of them passed a page with no fade at all.
- **Reduced-motion is a hard contract.** `prefers-reduced-motion` changes
  *timing, never function or legibility*: route swaps are instant (no ghost,
  no mist, tint/seed snap, no `warp`), the composer shows/hides at once, its
  selection indicator jumps rather than slides, the dock appears without a
  FLIP. Verify it on anything that moves.
- **Two invariants that always hold.** (1) *Settled crispness* — at rest,
  no filter, text wins the luminance contract, nothing blurred. Transient
  mid-transition haze is fine. (2) *Frame continuity* — the `#dreambg`
  canvas never unmounts, pauses, or resets across navigation; its frame
  tally stays monotonic. Both are guarded by tests; keep them green.

