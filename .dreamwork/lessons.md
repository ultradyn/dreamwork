# Lessons

One concise line per important lesson, newest last, each pointing at its
source dream. Not a log — only things that should change future behavior.

- Verify before dismissing a subagent's contradiction — its fresh look may
  beat your cached fact. (2026-07-25-0210-dogfood-reflection)
- Facts that gate behavior (git-ness, backends, authorization) go stale —
  recheck them from the world at reconcile, not from memory.
  (2026-07-25-0210-dogfood-reflection)
- Watch for over-investing in one finished sub-feature (polish, extra
  mechanisms) while primary paths and principles stay unexercised — it's the
  make-work gradient in miniature. (2026-07-25-0244-alignment-roll-py-hotspot)
- In an alignment review, "ungated polish" may be human-authorized surface
  whose trail lived only in chat — check before recommending a trim; the
  durable fix for chat-authorized work is a verifiable in-band provenance
  note, not a revert. (2026-07-25-0310-alignment-pass2-clean)
- For a visual/WebGL task judged by headless screenshots, expect flaky
  headless-GL (SwiftShader) context loss — a blank render is likely the
  driver, not your shader. Add a webglcontextlost/restored rebuild handler
  and reload-on-loss capture; measure pixels rather than trusting the eye.
  (2026-07-25-0445-dreambg-shader-tilt-shift)
- For morph/dissolve transitions: put ALL softening (blur + displacement)
  inside ONE SVG filter and drive its attrs per-frame from rAF; keep only
  opacity/transform on CSS transitions — you can't CSS-tween a `filter`
  containing a non-interpolable `url(#…)`. Clear the inline filter at rest
  for a crisp, zero-cost settled state. Cost scales with filtered-layer
  area, not turbulence octaves. (2026-07-25-0623-dream-dissolve-transition)
- For a shared-element FLIP that crosses a full view-swap, lift the hero
  above the swap's dissolve (z-index, higher opacity floor, less own-blur)
  and make its glide OUTLAST the dissolve — else it inherits the page mist
  and reads as "page changed + thing appeared", not "thing travelled".
  (2026-07-25-0646-review-morph-and-frametime)
- Dev-overlay frametime that's inter-frame delta sits at vsync regardless
  of cost; wrap draw() in performance.now() for the real signal. Measured:
  the ambient shader is ~0.1-0.3ms/frame — transition dips are SVG-filter
  compositing, not the shader. (2026-07-25-0646-review-morph-and-frametime)
- Global single-key hotkeys must ignore keystrokes when a text field is
  focused — add the guard WITH the first text input, not after the bug
  report; the conflict is invisible until an input exists.
  (2026-07-25-0713-palette-worldspace-batch)
- A detached/floating control window (Document-PiP, window.open) must carry
  its own identity (what it steers), because the context that spawned it is
  gone and several may be open. (2026-07-25-0713-palette-worldspace-batch)
- Wall-clock shader phase must be range-reduced (e.g. %86400) or highp float
  precision dies at epoch magnitudes; world-space window anchoring needs
  BOTH a screen-position domain offset and shared phase, or seams break.
  (2026-07-25-0713-palette-worldspace-batch)
- For an enter animation, the start state must SNAP not transition — set
  `transition:none` on the start-state class, reflow, then remove it next
  frame; with an always-on transition, adding the class animates *toward*
  the start value and it never gets there (looks like a pop-in).
  (2026-07-25-0806-question-flow-and-reload-batch)
- A server generation on /mtime (client reloads when it changes) fixes stale
  tabs on any restart for free; `--autoreload` = os.execv on source-mtime,
  socket is close-on-exec so the port frees. Land dev-loop speedups early.
  (2026-07-25-0806-question-flow-and-reload-batch)
- Prefer impossible-by-construction over validation: parse so a sub-bullet
  can never be mistaken for an entry; key list rows by index not a
  DOM-round-tripped title. (2026-07-25-0806-question-flow-and-reload-batch)
- Busy-dreamer mailboxes deliver between turns, so coordinator orders
  routinely cross dreamer reports — write orders idempotently, expect
  "DONE" lines that predate them, and re-state once on the next idle
  rather than assuming receipt. (coordinator, 2026-07-25 wrap)
