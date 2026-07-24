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

### Review artifacts

Artifacts under `.dreamwork/review/` are standalone documents, but they
are read inside this dashboard — so they carry the same `:root` tokens,
the same mono stack, and the same restraint. Inline everything (no
fetches; a strict reading of "offline-clean").

An artifact is a separate document, so page-level chrome does not reach
it: it carries its own scrollbar rules (the same hairline track and
`--dimmer` thumb the shell uses) or it shows the browser's default
inside our iframe. Same for any popped-out window.

Two idioms, both endorsed by the human (2026-07-25, on the
goal-hierarchies artifact — *"the diagram here is really nice, we should
be sure to remember it"*):

- **Diagrams are inline SVG in the token palette**, not images and not
  ASCII. Nested boxes indented by depth, hairline arrows between them,
  `--accent` reserved for the one row that is the point.
- **Label the columns, not the gaps.** Every row states its own two
  facts side by side under a header pair (`DEPTH` / `LIVES IN`) — a
  label floating between two rows attaches itself to the wrong one, and
  a reader will not notice they have learned it backwards. Found by
  looking at the render; the markup read fine.

A decision artifact shows each option beside its alternative rather than
only the recommendation: the human is being asked to decide, not to
ratify.

### Components (idioms)

Everything renders through shared factories so a redesign is one edit, not a
hunt: `page_shell` (the one HTML shell + `<script>` bundle); `pageHeader`
(every heading, with the `+` opener in the left gutter); `label`, `expand`
(`<details>`), `preB`/`linkify` (backticked repo paths become `/file`
links; a `.dreamwork/review/*.html` path becomes a `/review` link that docks
its question), `qaCard` (**the question card** — its own section below). A
low-emphasis PiP glyph (`pipBtn`) sits after doc/review affordances
(file + review headers, the dashboard reviews list, the composer); clicking it
floats the target in an identity-headed window (`openPopout` → Document
Picture-in-Picture, `window.open` fallback) that stays put while the main tab
navigates and carries the same dreaming field (see Shader). Views are pure builders returning `#view`'s innerHTML
(`buildDashboard`,
`buildQuestions`, `buildFile`, `buildReview`); the router swaps them. Add a
view by adding a builder + a `routeOf`/`TINT`/`SEED` entry, not new chrome.

### The persistent chrome

The heading is not content. It is the page's frame — the same `+` opener, a
title, and a crumb row, on every route — and it lives in the shell as a
**sibling of `#view`**, the standing `#dreambg` already has. While it lived
*inside* `#view` it dissolved and was rebuilt on every navigation, which is
why a route change read as "the elements jump around" rather than as the page
opening up (human, 2026-07-25). View builders return their body only; a new
view adds a `TITLES` entry and a `crumbsFor` branch, not a heading.

**Crumbs are keyed** (`data-k`), and that is the whole trick: a survivor must
be *literally the same element* before and after, or a FLIP has nothing to
measure and you get a fade where a glide was asked for. `home` is one crumb
across three routes even though its text gains and loses an arrow. Departing
crumbs are lifted out of flow at the rect they occupied — so survivors can
close the gap underneath them — and dream away in place on the mist idiom;
arrivals SNAP to their start state (`.dreamin`) before easing in.

The separator belongs to the crumb that **follows**, so a departing crumb
takes no punctuation with it. It is written with non-breaking spaces: an
inline-block collapses the leading and trailing whitespace of generated
content, and `content:" · "` renders flush against its neighbour.

**The column travels.** `/review` is the styleguide's one width exception,
and changing width is a layout change, so it glides (`body.wsliding`) on the
dissolve's own easing rather than snapping. Two consequences that are not
optional:

- **The departing ghost is pinned** to the box it was rendered in (top,
  width, height, measured before the class flip). It is *leaving*: it must
  not re-wrap every paragraph into a new column while still fully opaque.
  That reflow, at frame 0 and at full opacity, *was* the reported jump.
- **`body.wsliding` clips `overflow-x`**, because a ghost pinned to the wider
  old column would otherwise push a horizontal scrollbar as the column
  narrows underneath it.

`.wsliding` is added only for a route change, so a direct load of `/review`
arrives already wide instead of animating its column on first paint.

**The opener clamps, it does not track.** The `+` hangs in the gutter left of
the column, and the gutter does not exist on the review view or in a narrow
window — the button was sliced in half by the page edge. The pull is clamped
to the room that actually exists, in **CSS**:

```css
margin-left: calc(-1 * clamp(0px, (100vw - 100%) / 2 - .6rem, 2.4rem));
```

`100%` is the containing block's width — `.htitlebar`'s, which is the
column's — so `(100vw - 100%)/2` *is* the gutter, without naming a column
that is sized in `ch` (and `ch` would resolve against the button's own font,
not the column's). CSS rather than a measure-then-write in rAF is what makes
the guarantee hold on **every frame**: the column glides, and JS would always
paint one frame behind it. At the tightest column the button parks flush,
still inset by the body padding.

`dev/capture/headertravel.mjs` traces all of this per frame, in both
directions, plus reduced motion, plus every route at four window widths. Each
check was shown to fail on its own deliberately-reintroduced bug — the
unclamped opener measures **-22px**, i.e. off-screen. Note the ghost is
measured with `offsetWidth`, not `getBoundingClientRect()`: the dissolve
lifts it with `scale(1.07)`, and only layout width answers "did it re-wrap".

### Prose rendering

Everything the loop writes to disk is hard-wrapped at about 72 columns. A
`<pre>` renders those breaks literally and the browser then re-wraps them
inside a narrower card, so every paragraph breaks twice and reads as a
ragged mess (human, 2026-07-25, with a screenshot). So prose is **reflowed**:
wrapped lines are joined and the reading column does the wrapping.

**The line: markdown prose reflows, raw text does not.** Question bodies,
answers, follow-up notes, dreams, and the dashboard's `.md` peeks are prose
the page composes, and they go through `mdB` / `mdBReview`. `/file`, the
status blob, and the git tail are shown *as they are on disk*, and stay
verbatim in a `<pre>` — the file viewer's whole job is to be literal, and it
serves code as well as prose.

Four things survive the join, because each carries meaning a joined line
would destroy: a **blank line** is a paragraph break; a leading **`- `** is a
real list item and its **indent is its nesting**; a **``` fence** is code;
a **`#` heading** stands alone. Nesting is the *rank* of a bullet's indent
among the indents actually present, not its column count — a question body
arrives carrying the source file's own 2-space indent, and absolute columns
would push every sub-bullet a level too deep.

**Inline emphasis is luminance, not weight.** `**bold**` renders as
`--bright` at the same weight; the page already says "more important" with
its text ramp, and a mono bold would change metrics to say no more. `*em*`
is italic, `` `code` `` gets `--lit` on a `--panel` ground (a reading aid for
paths and identifiers, not a badge). Order in `mdSpans` is load-bearing: the
linkifiers inject `<a>` *inside* the backticks, so code spans convert after
them and swallow the link; `**` resolves before `*` so a bold pair is never
read as two emphases.

The parser feeds this: a sub-bullet may itself be hard-wrapped, and its
continuation lines belong to *it*. Capturing only the first line truncated
the note mid-phrase **and** spilled its tail into the body as orphaned prose
(that pair of symptoms was #106 — reported as a "confusing cut-off preview",
which is what data truncation looks like from the outside). Any line that
starts a new bullet ends the capture, so an unrecognised sub-bullet — an
in-session follow-up, say — can never be glued onto the one above it.

`dev/capture/reflow.mjs` measures this rather than eyeballing it. Range
`getClientRects()` returns one rect per inline *box*, so rects are grouped by
top edge into real line boxes first. The decisive check is an A/B: every live
question body rendered *both* ways at the same width, swept across widths.
The win peaks in the middle of the sweep — at a very narrow column both
renderers are ink-limited, and at a wide one the source's own 72 columns
nearly fit; it is the widths a card actually gets where a `<pre>` wraps every
line a second time.

### The question card

A question is the page's one interactive object, and it appears on four
surfaces — the dashboard, `/questions`, the review dock, and the card the
submit morph restates in place. All four go through **one** component, so a
change to how a question looks is one edit rather than a hunt.

**Contract: `qaCard(q, key)`.**

- **The key addresses the entry**, it does not describe it: `'o'+index` into
  `questions_open`, `'a'+index` into `answered_entries`. `qaEntry(key)` is
  the single place a key becomes an entry, for reads and writes alike. A
  title round-tripped through the DOM is never the address — a stale render
  must not be able to write to the wrong entry.
- **The state is derived, never passed.** `qaState(q, key)` returns
  `open` (needs the human — shows an answer box), `awaiting`
  (answered from the page, the loop hasn't folded it — the answer on a quiet
  accent rail with a `✓` and no box, so it never reads as still-open), or
  `folded` (key is `a…`; the loop has filed it into `## Answered`, so it
  recedes). Deriving it means no caller can render an entry in a state its
  own data contradicts.
- **The states are class modifiers on one card** (`.qa.open` / `.qa.awaiting`
  / `.qa.folded`, plus `data-qkey`), so shared styling is written once and
  only the differences are stated. A state that needs its own element tree is
  a signal the state is really a different component.
- **`qaInner` is split out from the card** purely so the answer-submit morph
  can restate a *live* card in its new state without assembling look-alike
  markup. Any future in-place state change uses the same seam.

Every state carries the follow-up thread (`- **Follow-up (via watch…)**`
sub-bullets) and the `add a note` box (`sendComment`, POST `/comment`); the
Answered section is rendered structured from `answered_entries`, not raw
text. The questions/dashboard views group cards by state with their own
counts — grouping is the view's job, rendering is the card's.

`dev/capture/qacard.mjs` guards this by *structural* comparison: it asserts
the dashboard's and the review dock's cards have the same tag path and class
vocabulary as `/questions`'s, which is exactly what a quiet fork would lose.

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

**One vocabulary.** `COMMANDS` (top of `watch.py`) is the single source of
steering kinds — `{kind, label, desc, common}`. The server derives
`COMMAND_KINDS` from it to validate `POST /command`, the page embeds it as a
JS `const`, the composer renders its buttons from it, and the popped-out form
fills its `<option>`s from it. A new kind is one entry and nothing else;
plugin-contributed kinds (#86) append to the list, so nothing downstream may
assume a fixed set or a fixed length.

**Choosing a kind** is a radiogroup of buttons with one background indicator
that slides between them — `.cmdkinds` / `.cmdind` / `.cmdkind`, driven by
`moveIndicator(snap)`. The row carries the `common` kinds plus the active one
when it is uncommon, so whatever is selected always has a button for the
indicator to sit on. The indicator is sized to the active *button*, never to
the group: the row wraps once a vocabulary outgrows one line, and a
`height:100%` indicator would span every line at once. Three rules:

- **Land, don't slide, on open** (`moveIndicator(true)`) and on reflow. The
  indicator starts 0-wide at the group's origin, so animating from there
  reads as a glitch rather than a choice — the enter-snap rule again. Add
  `.snap` (`transition:none`), set the geometry, force a reflow, then remove
  it. Verify with a per-frame trace (`dev/capture/indtrace.mjs`), never a
  screenshot.
- **The selected label glows, it does not re-metric.** `text-shadow`, not
  letter-spacing or weight: a text effect that changes layout would resize
  the buttons and so move the very target the indicator is chasing.
- **Rebuild only on membership change.** `renderKinds()` returns early when
  the row's kinds are unchanged, so a common→common switch leaves the DOM
  (and the indicator) alone and it slides. A rebuild replaces the indicator
  with a fresh 0-width one, so that path lands instead.

**Discoverability is the ⋯ menu.** Hovering (or focusing) `.cmdmorebtn`
reveals `.cmdmenu` — *every* kind, common or not, each with its one-line
`desc`. A rare kind is then discoverable rather than hidden knowledge, and
picking one from the menu selects it and adds it to the row. The menu drifts
in on the same soft blur as the composer itself, and there is deliberately
**no gap between the icon and the menu**: `:hover` follows the DOM, not the
box, so the pointer must be able to travel from one to the other without
ever leaving `.cmdmore` or the menu closes en route. `aria-expanded` is
mirrored from JS because CSS cannot set it. Both the row and the menu render
from `COMMANDS` at whatever length it has — plugin kinds (#86) appear with no
redesign, which is the whole point of the shape.

### Motion language (authored across the transition work)

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
- **The composer's sliding indicator.** Choosing a command kind slides the
  selection background to it (~.3s, the dream easing) — the composer's one
  piece of crisp motion. It lands without sliding on open and on reflow; see
  The composer.
- **Answer-submit morph.** Submitting an answer (button or **Ctrl/Cmd+Enter**,
  which works from any answer box) *is* the confirmation: the card reshapes
  in place into its answered-awaiting-fold state and the typed text lifts
  from the box into the rendered answer (the lifted-hero FLIP — the answer
  is the tracked element), a ripple accenting it. The live re-render is held
  ~1.6s so the morph settles before the loop's fresh data regroups the card.
  reduced-motion swaps straight to the answered state.
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
