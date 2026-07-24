# Question-travels-to-review morph + a measured-frametime finding (#66, #67)

Two tasks landed together after the #65 dissolve: a shared-element morph
that carries a question onto its review page (#66), and a measured
draw-time metric for the dev overlay (#67). Commits: 0ab31dc (#66),
becbd0d (#67).

## Measured finding (the human asked: is the shader heavy?)

With the new metric live: **steady-state shader draw is ~0.1–0.3ms
CPU-side** (JS + GL submission) at a locked 60fps — the ambient background
is cheap. During a page dissolve, the measured draw stays ~0.1ms while the
*inter-frame* delta balloons to ~33ms worst (fps dips to ~50). So the
transition dip is **SVG-filter compositing on the main thread, not the
WebGL shader**. Conclusion for future work: don't optimise the steady-state
shader (it's already nearly free); if a transition ever needs to be
cheaper, the lever is fewer/smaller filtered layers, not the fractal.
GPU-timer path (EXT_disjoint_timer_query_webgl2) is dormant on this
WebGL1/SwiftShader context — the honest CPU number shows instead.

## The shared-element-morph lesson (reusable)

A FLIP that carries an element *across a full view-swap* (list → review)
fights the swap's own transition: the moving element is a child of the
incoming `#view`, so it inherits that view's dissolve filter (blur +
displacement) and its enter drift. First cut: the travelling question
drowned in the page mist — you couldn't tell one element was moving. Fix:
make the hero **rise above the mist** — `z-index` above the dissolving
page, a higher opacity floor (0.4 not 0.15), less of its own blur, and a
glide (~1.15s) that **outlasts** the page dissolve (~0.9s) so it's still
visibly settling after the mist clears. The steer wanted "dream-blurred
drift, not reveal.js-crisp", so the goal isn't sharpness — it's a
*trackable* luminous drift. General rule: for a shared-element morph over a
dissolve, lift the hero out of the dissolve's blur budget and let its
motion run longer than the dissolve, or it reads as "page changed + thing
appeared" rather than "thing travelled".

## Architecture note

`/review` now serves the app shell (client-routed); the raw artifact moved
to `/reviewraw` and loads in an iframe (style isolation) behind the same
`resolve_confined` gate. The question→review link convention: a backticked
`.dreamwork/review/<name>` path inside a question becomes
`/review?p=<name>&q=<title>`, so clicking docks *that* question. This
extends the existing "backticked paths become links" convention rather than
inventing a new affordance.

## Out-of-scope ideas (captured, not acted on)

- After answering from the dock, a subtle "answered" confirmation (a dream
  ripple / toast) would close the loop — right now submit is silent.
- Per-route turbulence seed (#68) pairs naturally: the review route could
  have its own signature swirl, reinforcing "you arrived somewhere".
- The morph could be bidirectional — leaving the review could send the
  (now-answered) question back to its list slot.
