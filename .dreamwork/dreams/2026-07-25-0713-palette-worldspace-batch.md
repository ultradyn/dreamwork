# Command palette, per-route seeds, world-space shader, styleguide (#71/#68/#74/#72)

A four-item batch on the watch page. Commits: 6c17665 (#71, folds #76 +
#78-core), 8abcf12 (#68), 1b2e17f (#74), d1df255 (#72).

## Insights worth keeping

**A second write path as a wake-signal, not a durable write.** `/answer`
writes durably to questions.md (the loop folds it). `/command` instead just
appends a source-tagged line to `watch-events.log` — the loop's tail
monitor wakes and *the agent* does the durable action (add the idea to the
task list, etc.). The events log is the transport; the durable mutation
stays in the session. This is the right shape for adding steering surfaces
without turning the page into a writer: one localhost-trust endpoint, a
tagged line, no new file semantics.

**A popped-out control must self-identify.** The Document-PiP / window.open
command form can outlive the tab that spawned it and several can be open at
once (different targets). So the popout carries its project identity — name
+ full path + a tint band matching the page — in its own header and window
title. General rule: any detached/floating control window needs enough
identity to answer "which thing am I steering?" on its own, because the
context that made it is gone.

**Global single-key hotkeys must bail inside text fields.** The shader's
`l` layer-switch was harmless until the command palette added a textarea —
then typing "l" cycled the background. The fix is one guard
(`e.target.closest('input,textarea,select')`), but the lesson is the timing:
a latent input-focus bug is invisible until you add the first text input,
so add the guard *with* the input, not after a bug report. (Filed as #78;
the core is fixed, the activation-feedback half remains.)

**World-space shader = domain offset + wall-clock phase, and both need
care.** Anchoring adjacent windows to one field takes two things: (1) offset
the fBm domain by the window's screen position, in the domain's own units
(2.3/innerHeight per screen px) so a neighbouring window's slice lines up at
the seam; (2) drive phase from the wall clock so windows animate in
lockstep. The catch is float precision: raw epoch seconds (~1.7e9) destroys
highp — reduce it (UTC-day-wrapped, `%86400`) so it stays ~1e4 and precise,
accepting one simultaneous reshuffle at the day boundary. Domain-anchoring
alone is not enough; without phase sync, two windows match spatially but
their fields evolve out of step and the seam breaks.

## Styleguide closer (#72)

The motion language now lives in `watch-design.md` as the standing
reference (dream dissolve, one-SVG-filter mist rule, lifted-hero FLIP,
reduced-motion = timing-not-function, settled-crispness + frame-continuity
invariants, copy voice). DREAMWORK.md points to it: read before changing
the page, keep current in the same commit. Writing it down is what stops the
vocabulary living only in my head / the dreams.

## Out-of-scope (captured, several already filed)

- #78 activation-feedback half (the layer switch's hint could be clearer).
- #83 visible PiP-icon buttons wherever a pop-out helps (generalise the
  palette's pop-out affordance).
- The command palette could grow plugin-contributed command kinds (the
  writing-plugins.md "Commands" seam) — namespaced, never shadowing core.
