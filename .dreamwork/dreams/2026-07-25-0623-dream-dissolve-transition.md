# Dream dissolve — making the page transition beautiful (task #65)

Steer (human, verbatim): "the transition between pages is nice however a bit
too fast. and some movement would be good. maybe a bit more morphing or
fuzzing or the like."

Delivered: the outgoing view liquifies into a swirling turbulence mist and
drifts up as it fades; the incoming view coalesces from the same mist and
settles crisp. ~1.15s with a hazy dwell (was ~0.45s straight fade). The
#dreambg fractal stirs in sympathy via a new `warp` uniform the router
pulses per nav. Committed ea2e744.

## Insights worth keeping

**The CSS-`filter`-interpolation trap (the load-bearing lesson).** You
cannot CSS-`transition` the `filter` property when it contains a
non-interpolable `url(#…)` reference — the browser snaps instead of
tweening, and mixing a CSS-transitioned `blur()` with a JS-driven
`url()` in the same declaration fights itself. The clean pattern that
unlocked this whole effect: put ALL the softening (blur AND displacement)
*inside one SVG filter* — `feGaussianBlur` is a primitive, so it lives
next to `feTurbulence`+`feDisplacementMap` — and drive that filter's
attributes per-frame from a rAF envelope. Leave `opacity` + `transform`
on CSS transitions (they're not part of `filter`, so no conflict, and
they stay GPU-composited/smooth). At rest, clear the inline `filter` to
`''` so the settled element is zero-cost and pixel-crisp. This cleanly
separates "the drift/fade" (declarative CSS) from "the mist" (imperative
JS), and is reusable for any morph/dissolve transition.

**Perf surprise: area dominates, not turbulence complexity.** Dropping
`feTurbulence numOctaves` 2→1 barely moved the ~30fps floor during the
transition. The cost is two simultaneous *full-viewport filtered layers*
(raster area × 2), not octave count. So the real lever for SVG-filter
transitions is the number/size of filtered layers, not noise complexity.
1 octave was still worth it — it gives *larger, softer* swirls (dreamier,
less grainy) for free. Note the ~30fps was only the WebGL shader redraw +
SVG re-raster; the CSS opacity/transform drift stays on the compositor at
full rate, so the perceived motion is smooth.

**Taste calibration.** The first pass read as "defocus blur." Pushing
displacement UP (scale ~19→25) and blur DOWN (~4.5→3.8) flipped it to
"liquid morph" — the fuzzing the human actually asked for. Blur still
matters: it's what keeps a big displacement reading as *dreamy* rather
than *glitchy/torn*. The line between haunting and broken is the blur.

## Out-of-scope ideas (captured, not acted on)

- Task #66 (question → review shared-element morph) can reuse this exact
  mist filter for a FLIP-style transition — dissolve the source, resolve
  the destination through the same swirl.
- A per-route turbulence `seed` would give each destination its own
  signature swirl (dashboard dissolves differently from a file view).
- If the transition fps floor ever matters, the fix is fewer/smaller
  filtered layers (e.g. turbulence only on the ghost), not cheaper noise.
