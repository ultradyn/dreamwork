# watch.py — live dreamloop dashboard (design record + styleguide)

Human-authorized 2026-07-25; built the same night in committed increments
(server core → dashboard → status.json → tests → components → questions →
review artifacts → events log → shader → router/transitions → dev overlay
→ review morph → the composer → world-space shader). This is the
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
- **Read-only, three write exceptions** (all human-authorized, localhost
  trust): POST `/answer` appends an answer into questions.md's matching Open
  entry; POST `/comment` threads a `- **Follow-up (via watch, <ts>):** …`
  note onto any entry (Open or Answered — a chronological mini-thread; a note
  on an Answered entry is flagged as a potential amendment in the events
  log); POST `/command` appends a source-tagged steering line
  (`command via watch: <kind>: <text>`, kinds add-idea / do-next / do-now /
  maintenance) to `.dreamwork/watch-events.log`. All three also append an
  events-log line so the loop's tail monitor wakes. Every other route reads.
  All file access goes through `resolve_confined()` (rejects absolute, `~`,
  traversal); `/filedata` and `/reviewraw` are both behind it.
- **Port** persisted to `.dreamwork/watch-port` (random 3000–63000 once)
  so bookmarks survive restarts; port-in-use error names the port.
- **Live reload**: poll `/mtime` ~2s → re-fetch `/data.json` → re-render
  the active view in place (no transition). No websockets. `/mtime` is
  `"<generation> <mtime>"`: a changed *mtime* re-renders the data; a changed
  *generation* (the server was restarted/redeployed, or rebuilt under
  `--autoreload`) triggers a full `location.reload()` so open tabs never go
  stale. The poll tolerates the brief unreachable window during a restart.
- **`--autoreload`** (implied by `--dev`): the server re-execs itself
  (`os.execv`) when its own source mtime changes — edit-and-see with no
  manual restart; the close-on-exec listening socket frees the port and the
  generation bump reloads clients.
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
  on-screen position at a world-fixed scale, and its phase to the wall
  clock, so every window — including popped-out ones — is a viewport onto
  one continuous, screen-pinned field. Hidden layer switcher: `l`
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
own counts). Every question entry — open, answered-awaiting-fold, and folded
Answered — also carries a follow-up thread (`- **Follow-up (via watch…)**`
sub-bullets) and a quiet `add a note` box (`sendComment`, POST `/comment`);
the Answered section is rendered structured from `answered_entries`, not raw
text. A low-emphasis PiP glyph (`pipBtn`) sits after doc/review affordances
(file + review headers, the dashboard reviews list, the composer); clicking it
floats the target in an identity-headed window (`openPopout` → Document
Picture-in-Picture, `window.open` fallback) that stays put while the main tab
navigates and carries the same dreaming field (see Shader). Views are pure builders returning `#view`'s innerHTML
(`buildDashboard`,
`buildQuestions`, `buildFile`, `buildReview`); the router swaps them. Add a
view by adding a builder + a `routeOf`/`TINT`/`SEED` entry, not new chrome.

### The composer

The `+` opener in every heading's left gutter toggles **the composer**
(`#cmdpalette`) — the panel that steers the loop without a chat turn. It is
anchored to its opener, not floated free: `place()` puts it `CMD_GAP` (18px)
under the opener and flush with its left edge. Two things make that
arithmetic non-obvious, and both are load-bearing:

- **The panel is `position:fixed` but the viewport is not its containing
  block.** `.wrap` carries `perspective` (for the dream dissolve's depth),
  which makes `.wrap` the containing block for fixed descendants — so `top`
  and `left` are measured from `.wrap`, while `getBoundingClientRect()`
  returns viewport coords. Subtract `.wrap`'s origin or the panel drifts
  right of the opener and hangs a body-padding too low.
- **The opener rotates 45° into an ×**, which swells its painted box by its
  half-diagonal. Anchor off the rect's *centre* (invariant under that
  rotation) plus the painted extent, so the gap is what the eye sees and is
  identical whether the panel is placed while closed or re-placed while open.

Nothing under the buttons is reserved: `.cmdmsg:empty` collapses, so the
panel grows downward only when there is something to say.

### Motion language (authored across the transition work)

The page *dreams*: motion is soft, slow, and never crisp-mechanical. It is
also strictly opt-in — most state changes do **not** animate.

- **When transitions apply.** Route changes (client nav) dissolve. The live
  mtime tick re-renders the active view **in place, instantly** — liveness
  must never wait on an animation. The composer reveals on a soft
  blur drift. Nothing else animates.
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
- **The ripple.** A soft expanding ring marks a received command; a felt
  pulse, not a modal.
- **Answer-submit morph.** Submitting an answer (button or **Ctrl/Cmd+Enter**,
  which works from any answer box) *is* the confirmation: the card reshapes
  in place into its answered-awaiting-fold state and the typed text lifts
  from the box into the rendered answer (the lifted-hero FLIP — the answer
  is the tracked element), a ripple accenting it. The live re-render is held
  ~1.6s so the morph settles before the loop's fresh data regroups the card.
  reduced-motion swaps straight to the answered state.
- **Reduced-motion is a hard contract.** `prefers-reduced-motion` changes
  *timing, never function or legibility*: route swaps are instant (no ghost,
  no mist, tint/seed snap, no `warp`), the composer shows/hides at once, the
  dock appears without a FLIP. Verify it on anything that moves.
- **Two invariants that always hold.** (1) *Settled crispness* — at rest,
  no filter, text wins the luminance contract, nothing blurred. Transient
  mid-transition haze is fine. (2) *Frame continuity* — the `#dreambg`
  canvas never unmounts, pauses, or resets across navigation; its frame
  tally stays monotonic. Both are guarded by tests; keep them green.

### Shader

Domain-warped fBm, four cheap passes on a low-res buffer (fractal → two
tilt-shift blur passes → composite/tint/dither); luminance-capped far below
the dim text so text always wins. Per-route `SEED`/`TINT`; transition `warp`
pulse. Recoverable context loss (rebuild on restore).

**One world, many viewports.** `mountDreambg(win, cv, opts)` is a mountable
function, not an IIFE bound to the main document — it reads everything from
the `win` it is handed, so any window can carry the field. The main page
mounts it on `#dreambg` (`{dev, switcher: true}`); `openPopout` mounts it on
every floated window (`mountPopoutBg`, after the fill, which assigns
`body.innerHTML` and would otherwise wipe the canvas), and the popout wears
the spawning view's tint. Three rules make "same screen position ⇒ same
pixels" actually true, and each was a bug until it wasn't:

- **The scale is a world constant** (`WORLD_SCALE = 2.3 / 900`, domain units
  per CSS pixel), not `2.3 / innerHeight`. A per-window scale pins the
  field's *origin* while letting each window pick its own *zoom*, so two
  windows show one dream at two magnifications and the seam can never line
  up. World-fixed scale also makes resizing reveal more of the field rather
  than rescale it — consistent with dragging, which already pinned.
- **The vertical anchor is negated and measured from the viewport's BOTTOM**
  (`-(screenY + chrome + innerHeight)`), because `gl_FragCoord.y` counts up
  from the viewport bottom while `screenY` counts down from the desktop top.
  Adding the top edge instead slides the field the wrong way at double rate.
- **The lens is per-window, deliberately.** The tilt-shift focus band and
  the edge defocus stay in each window's own `uv` space: one shared world,
  seen through each window's own lens. So blur can differ at a seam even
  though the field beneath it matches exactly.

`dev/capture/worldspace.mjs` and `popbg.mjs` prove this by freezing
`Date.now()` (the field is time-varying, so two screenshots are never
simultaneous otherwise) and comparing plates — across window heights, and
across the main/popout document boundary. Hidden layer switcher
for debugging — the hotkey is ignored inside text fields, and any switch
(key or corner triple-click) shows a self-naming auto-fading toast
("background: <layer> — press l to cycle") so an accidental change is
legible. `--dev` measures real per-frame work (steady state is ~0.1–0.3ms
CPU; transition dips are SVG-filter compositing, not the shader).

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
