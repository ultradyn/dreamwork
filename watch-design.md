# watch.py — live dreamloop dashboard (design record + styleguide)

Human-authorized 2026-07-25; built the same night in committed increments
(server core → dashboard → status.json → tests → components → questions →
review artifacts → events log → shader → router/transitions → dev overlay
→ review morph → command palette → world-space shader). This is the
authoritative reference for anyone changing the page: the standing design,
plus the token / component / motion / voice styleguide below. The delivery
plan it replaces is in git history (`docs/plans/watch-py.md`); keep this
file current as the page evolves.

## What it is

One stdlib-only file serving a single app shell with four client-routed
views — dashboard, questions, file viewer, review — plus the raw review
artifacts the review view embeds. The dashboard shows dreams (with live
ages), main files, git tail (maintenance markers highlighted), migrations
vs target version, roll weights, and `.dreamwork/status.json` (loop writes
it per tick; page degrades gracefully without it). Every view's heading
carries a `+` command opener (steer the loop without a chat turn).

## Standing design decisions

- **Stdlib only, self-contained**; no dependencies, no build step.
- **Bind 127.0.0.1 only.** Localhost by construction, never exposed.
- **Read-only, two write exceptions** (both human-authorized, localhost
  trust): POST `/answer` appends a human-typed answer into questions.md's
  matching Open entry (async question answering was the point); POST
  `/command` appends a source-tagged steering line
  (`command via watch: <kind>: <text>`, kinds add-idea / do-next / do-now /
  maintenance) to `.dreamwork/watch-events.log` — the loop's tail monitor
  wakes on it, same transport as answers; no file beyond the log is
  written. Every other route reads. All file access goes through
  `resolve_confined()` (rejects absolute, `~`, traversal); `/filedata` and
  `/reviewraw` are both behind it.
- **Port** persisted to `.dreamwork/watch-port` (random 3000–63000 once)
  so bookmarks survive restarts; port-in-use error names the port.
- **Live reload**: poll `/mtime` ~2s → re-fetch `/data.json` → re-render
  the active view in place (no transition). No websockets.
- **Single-document router**: `/`, `/questions`, `/file`, `/review` serve
  one shell; the client router renders the view, pushState/popstate drive
  the URL. The `#dreambg` canvas is a sibling of `#view` — never unmounted,
  so the background survives navigation. Route changes dissolve through a
  turbulence mist (see Motion language); reduced-motion swaps instantly.
  `/review` embeds the raw artifact (served at `/reviewraw`) in an iframe
  for style isolation; a question linking to it travels along, docked.
- **Events log**: user actions (answers, commands) append one line to
  `.dreamwork/watch-events.log` so agents can wake on a tail Monitor
  instead of waiting for a tick.
- **`--dev`**: fps, measured per-frame draw time (CPU stopwatch around
  `draw()`; true GPU time via `EXT_disjoint_timer_query_webgl2` when the
  context exposes it), inter-frame avg/worst, and a 120-frame sparkline
  overlay — on every view, zero cost when off.

## Design contract (per web-artisan-core, minimalized)

- Mode: Docs/Refined — a quiet tool page, "terminal readout" not product.
- Thesis: glanceable status; **liveness is the design** — every number
  that can drift without a disk change ticks client-side every second.
- Type: one mono stack, two sizes. Geometry: no cards/borders/pills; dim
  uppercase labels; max-width 72ch. Components: shared `page_shell` +
  `:root` token block + factored JS strings — one system, any redesign.
- Color: near-black bg, two grays, ONE accent (indigo) spent on
  maintenance markers and a nonzero open-questions count.
- Ambient shader background (human-authorized): domain-warped fBm with
  tilt-shift focus and a curl-advection pinch; hue-only per-route tint,
  luminance-capped so text always wins; static under reduced-motion,
  absent without WebGL. The sampling domain is anchored to the window's
  on-screen position and its phase to the wall clock, so adjacent windows
  share one continuous, screen-pinned field. Hidden layer switcher: `l`
  (ignored inside text fields) / triple-click bottom-right.
- Single ambient dark theme — intentional exception (overnight
  monitoring tool; human's stated dark preference).

## Styleguide

The standing reference for changing the page. New surfaces conform to this;
if a change needs to break a rule, update the rule here in the same commit.

### Tokens

All colour/space lives in the `:root` block in `STYLE` — edit tokens, never
hardcode. `--bg` near-black; `--panel`/`--panel2` raised fills; `--line`
hairlines, `--border` stronger edges; a text ramp `--text` → `--lit` →
`--bright` (up, brighter) and `--muted` → `--dim` → `--dimmer` (down,
quieter); **one** accent, `--accent` indigo. `--space` (section rhythm),
`--radius`. The accent is scarce on purpose — spent only on live/actionable
things (maintenance markers, a nonzero open-questions count, links, the
active command opener). If everything is accented, nothing is.

### Type & geometry

One mono stack, two sizes (heading `1rem`, body `.8rem`, labels `.7rem`).
No cards, borders-as-decoration, pills, or shadows in the reading views —
structure comes from whitespace and dim uppercase labels (`.label`, letter-
spaced). Reading column is `max-width:72ch`, centred; the review view is the
one deliberate exception (`body.review` widens the column for the artifact +
docked question). Dividers are hairlines (`--line`), not boxes.

### Components (idioms)

Everything renders through shared factories so a redesign is one edit, not a
hunt: `page_shell` (the one HTML shell + `<script>` bundle); `pageHeader`
(every heading, with the `+` opener in the left gutter); `label`, `expand`
(`<details>`), `preB`/`linkify` (backticked repo paths become `/file`
links; a `.dreamwork/review/*.html` path becomes a `/review` link that docks
its question), `qaCard` (a question in one of three states — **open** shows
an answer box; **answered-awaiting-fold** — a dashboard answer the loop
hasn't folded yet — shows the answer on a quiet accent rail with a `✓`, no
box, so it never reads as still-open; the **folded Answered** section is
rendered separately. The questions/dashboard views group by state with their
own counts). Views are pure builders returning `#view`'s innerHTML
(`buildDashboard`,
`buildQuestions`, `buildFile`, `buildReview`); the router swaps them. Add a
view by adding a builder + a `routeOf`/`TINT`/`SEED` entry, not new chrome.

### Motion language (authored across the transition work)

The page *dreams*: motion is soft, slow, and never crisp-mechanical. It is
also strictly opt-in — most state changes do **not** animate.

- **When transitions apply.** Route changes (client nav) dissolve. The live
  mtime tick re-renders the active view **in place, instantly** — liveness
  must never wait on an animation. The command palette reveals on a soft
  blur drift. Nothing else animates.
- **The dream dissolve** (route change). The outgoing view becomes a
  `.ghost` that liquifies into a swirling mist and drifts up as it fades;
  the incoming view coalesces from the same mist and settles crisp. ~1.15s
  with a hazy dwell in the middle (`DREAM_MS`); opacity + upward transform
  ride CSS, the mist is JS-enveloped. The `#dreambg` shader stirs in
  sympathy (a `warp` pulse deepening the curl advection + a centred twist).
  Each destination has its own turbulence `SEED` and `TINT` — arriving
  somewhere feels consistent and distinct from arriving elsewhere.
- **The mist filter — the load-bearing rule.** Put *all* softening (blur
  **and** displacement) inside **one** SVG filter
  (`feTurbulence`→`feDisplacementMap`→`feGaussianBlur`) driven per-frame
  from rAF; keep only `opacity`/`transform` on CSS. You cannot CSS-tween a
  `filter` that holds a non-interpolable `url(#…)`, and its cost scales with
  filtered-layer *area*, not turbulence octaves. Clear the inline filter at
  rest so the settled element is pixel-crisp and zero-cost.
- **Lifted-hero FLIP** (shared-element morph, e.g. question → review dock).
  Measure the source rect, render the destination, invert to the source,
  play to identity — but the dream twist is a blurred, low-opacity drift,
  not a reveal.js slide. When the morph crosses a full view-swap, **lift the
  hero above the dissolve** (z-index, higher opacity floor, less own-blur)
  and make its glide **outlast** the dissolve, or it drowns in the page mist
  and reads as "page changed + thing appeared" rather than "thing
  travelled".
- **The ripple.** A soft expanding ring marks a received command or answer
  (with a brief "received" / "sent to the dream"); confirmation is a felt
  pulse, not a modal.
- **Reduced-motion is a hard contract.** `prefers-reduced-motion` changes
  *timing, never function or legibility*: route swaps are instant (no ghost,
  no mist, tint/seed snap, no `warp`), the palette shows/hides at once, the
  dock appears without a FLIP. Verify it on anything that moves.
- **Two invariants that always hold.** (1) *Settled crispness* — at rest,
  no filter, text wins the luminance contract, nothing blurred. Transient
  mid-transition haze is fine. (2) *Frame continuity* — the `#dreambg`
  canvas never unmounts, pauses, or resets across navigation; its frame
  tally stays monotonic. Both are guarded by tests; keep them green.

### Shader

Domain-warped fBm, four cheap passes on a low-res buffer (fractal → two
tilt-shift blur passes → composite/tint/dither); luminance-capped far below
the dim text so text always wins. Domain anchored to `screenX/screenY`
(+ chrome estimate), phase from the UTC-day-wrapped wall clock — one shared
world-space field across windows. Per-route `SEED`/`TINT`; transition `warp`
pulse. Recoverable context loss (rebuild on restore). Hidden layer switcher
for debugging. `--dev` measures real per-frame work (steady state is
~0.1–0.3ms CPU; transition dips are SVG-filter compositing, not the shader).

### Voice & tone (page copy)

The page is a quiet tool that dreams — copy is spare, lowercase-leaning, and
a touch oneiric without being twee. Labels are dim uppercase single words
(`dreams`, `questions`, `answer questions`, `reviews`, `files`, `commits`).
Status reads plainly (`none active`, `updated 3m ago`, `2 open questions`).
The command surface carries the metaphor lightly: `command the dream`,
`a thought for the dream…`, and confirmations `sent to the dream` /
`received`. Never product-y CTA language ("Submit your request!"), never
exclamation. When in doubt: what would a calm terminal say at 3am.

## Non-goals

- Writes are limited to the two human-authorized localhost paths (`/answer`,
  `/command`); nothing else mutates. Steering stays lightweight.
- No historical analytics; a live window, not a metrics store.
- No public exposure; localhost only, by construction.
