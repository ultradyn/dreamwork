# Brief — #523 + #524: burndown limit input — keep focus across ticks; add [-]/[+] steppers

**Lane-owns:** `watch.py` (the burndown region AND the `setContent`/render-swap
state-preservation code around watch.py:~6784 — ONLY for the input
focus/selection preservation below), one new guard under `dev/capture/` +
registration, `watch-design.md` (same commit), `.dreamwork/handoffs.md`.
**Never** `_handle_decide` (lane-515decide), `track_question_updates` ~12917
(lane-509sig), or the markdown renderer `mdBlocks/mdRender/linkify/mdInline`
(lane-521md).

**His words (journal, 07:44):**
- #523 (P1): *"the bug where stuff deselects when new data.json is recieved is
  still here. It's very frustrating when trying to type something eg to test
  burndown period number input."*
- #524 (P3): *"the limit input for burndown chart should have a [-] before it
  and a [+] after it so it's easy to modify. holding down the button should
  reapply the operation."*

**Context you MUST read first:** `transitions.md` (the one rule, no
exceptions), `watch-design.md` (burndown + forms chrome), and
`.dreamwork/docs/plans/render-architecture.md` §the 16-surface inventory —
#523 is surface #1 of the #505 design. Your fix is the targeted
snapshot/restore instance, NOT the architecture: the full keyed reconciliation
awaits his ruling, and the design explicitly says small snapshot/restore pairs
landed now become dead code it absorbs later. Do not build the general
reconciliation; do not preempt #505.

**#523 — preserve input focus/selection/value across the data tick:**
`setContent` swaps `#view`'s innerHTML every tick; any focused input inside
`#view` is destroyed and recreated, losing focus, caret, and selection. Add a
snapshot/restore pair in the existing idiom (the ~11 others around the swap):
BEFORE the swap, if `document.activeElement` is an input/textarea inside
`#view`, record a STABLE identity for it (its `id` — the burndown limit input
has one; if it doesn't, give it one) plus `selectionStart`/`selectionEnd` and
whether the value differs from the incoming render's value; AFTER the swap, if
a node with that identity exists, restore focus + caret/selection — but NEVER
clobber a value the user typed mid-swap with a stale server value (his typed
text wins; assert this in the guard). Typing into the burndown limit input
across a data tick must be uninterrupted.

**#524 — steppers:**
A `[-]` button immediately before the burndown limit input and a `[+]` after
it. Click decrements/increments the limit (respecting the input's existing
min/max validation — find it; clamp the same way). Press-and-HOLD auto-repeats
(pointerdown starts an interval; pointerup/pointerleave/pointercancel stops
it; a first repeat delay ~400ms then ~80ms is the conventional feel — tune to
match the page's tempo). The steppers are quiet chrome per watch-design.md;
keyboard-accessible (real `<button>`s, focusable, labelled); reduced-motion
parity (no motion should exist to reduce — if you add any, `transitions.md`
governs it). The steppers must compose with #523: holding [+] across many data
ticks must NOT lose the repeat (the buttons live through the swap — either
they're part of the preserved chrome or the pointer capture survives; solve
it and assert it).

**Acceptance (all required):**
1. New guard `dev/capture/bdinput.mjs` (name yours), registered, asserting:
   (a) focus the limit input, type, force a data tick — focus AND caret
   position AND typed value survive; (b) select a range, tick — selection
   survives; (c) click [-]/[+] — value decrements/increments and clamps at
   the input's own min/max; (d) hold [+] — at least 2 repeats fire (simulate
   pointerdown, wait, count changes); (e) hold ACROSS a forced data tick —
   the repeat continues (the #523/#524 composition). Preconditions derived
   at runtime (input exists, tick actually happened — assert the data
   changed or the swap ran, not just that time passed).
2. Every assertion red-proved by injection into the production line it binds
   + cp restore; each red names the line injected.
3. `watch-design.md` documents the focus-preservation rule (it generalises:
   ANY input inside `#view`) and the stepper chrome IN THE SAME COMMIT.
4. Visual verdict: headless screenshots (desktop + 390px) of the stepper
   row at rest and one mid-hold state; view them yourself (read_file) and
   state the verdict.
5. `git commit --only <paths>`; handoffs.md Pending line
   `· landed \`<sha>\` · … · by lane-523burndown —` naming commits, reds,
   guard, verdict.

**Never:** weaken existing guards; touch the journal/posture/delivery code;
`just deploy`; bind ports outside 39890-39899 (check ownership first — other
lanes run guards too; run yours SOLO).

Model for the record: grok-4.5 (dispatch record — do not self-report a model).
