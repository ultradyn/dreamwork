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
- Session-scoped task backends lose the queue *and* its ids on restart —
  the ledger (`.dreamwork/tasks.md`) is what makes task numbers safe to
  cite from docs, plans, and commit messages. (coordinator, 2026-07-25 restart)
- `git add -A` while a dreamer holds the same tree silently commits its
  in-flight edits — stage by explicit path whenever work is parallel.
  (coordinator, 2026-07-25 restart)
- Durable shared state wants a single writer: naming an owner is cheap and
  invisible to omit, and the race only appears under fan-out — when nobody
  is watching. (2026-07-25-0832-ledger-coherence)
- Write a migration's "How to apply" against the broken target that
  motivated it, not the healthy one you are sitting in.
  (2026-07-25-0832-ledger-coherence)
- Never let selection depend on a channel you have not read back: Claude
  Code's TaskGet returns subject/status/description only, so task
  `metadata` is write-only there. (2026-07-25-0832-ledger-coherence)
- An id that is already durable upstream beats minting a new one: the
  ledger holds only work the loop originated, or a busy forge floods it.
  (2026-07-25-0832-ledger-coherence)
- A fix stated in terms of its own implementation breaks the other
  implementation: "the ledger" had to become a concept (durable record)
  before backend-neutral lines could safely use the word.
  (2026-07-25-0832-ledger-coherence, verify pass)
- Re-deriving an item from upstream never re-derives the loop's progress
  on it — external identity is enough until work starts, not after.
  (2026-07-25-0832-ledger-coherence, verify pass)
- Redefining a term silently rewrites every rule that uses it: after
  turning "the ledger" into a concept, the rules resting on it had to be
  re-read — one had quietly started saying forge issues could never be
  selected. (2026-07-25-0832-ledger-coherence, final pass)
- Mounting a SECOND instance of a surface (second window, second render) is
  the cheapest audit of the first: it falsifies coordinate, normalisation and
  sign assumptions that are unfalsifiable while N=1. Budget a duplication
  feature for finding bugs in the original. (2026-07-25-0846-composer-batch)
- A passing pixel/visual comparison proves nothing until you show it FAILS on
  the old code — temporarily restore the bug and re-run. Also assert the plate
  has detail, or "identical" is satisfied by "identically blank".
  (2026-07-25-0846-composer-batch)
- To compare a time-varying visual across captures that can never be
  simultaneous (two frames, two documents), freeze the clock via
  `addInitScript` overriding `Date.now` rather than trying to synchronise
  them. (2026-07-25-0846-composer-batch)
- `position:fixed` is NOT viewport-relative when an ancestor has
  `transform`/`perspective`/`filter` — that ancestor becomes the containing
  block, so rect-derived coordinates need its origin subtracted.
  (2026-07-25-0846-composer-batch)
- A judgement call raised only in chat is not recorded: the ask-discipline
  covers questions the loop *asks*, and a "here is a change you did not
  request, tell me if you hate it" is one of those. Caught in my own work
  hours later. (coordinator, 2026-07-25)
- A rule that asks an agent to *state* something binds only where that
  something is durably carried to it — check the carriers before trusting
  the rule. "Name the chain" shipped with its middle link living nowhere
  readable. (2026-07-25-0926-goals-coherence)
