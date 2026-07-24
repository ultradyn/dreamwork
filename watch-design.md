# watch.py — live dreamloop dashboard (design record)

Human-authorized 2026-07-25; built the same night in committed increments
(server core → dashboard → status.json → tests → components → questions →
review artifacts → events log → shader → router/transitions → dev
overlay). This records the standing design; the delivery plan it replaces
is in git history (`docs/plans/watch-py.md`).

## What it is

One stdlib-only file serving a single app shell with three client-routed
views — dashboard, questions, file viewer — plus raw review artifacts.
The dashboard shows dreams (with live ages), main files, git tail
(maintenance markers highlighted), migrations vs target version, roll
weights, and `.dreamwork/status.json` (loop writes it per tick; page
degrades gracefully without it).

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
- **Single-document router**: `/`, `/questions`, `/file` serve one shell;
  the client router renders the view, pushState/popstate drive the URL.
  The `#dreambg` canvas is a sibling of `#view` — never unmounted, so
  the background survives navigation. Route changes crossfade through
  blur (ghost of the outgoing view); reduced-motion swaps instantly.
- **Events log**: user actions (e.g. answers) append one line to
  `.dreamwork/watch-events.log` so agents can wake on a tail Monitor
  instead of waiting for a tick.
- **`--dev`**: fps + frametime avg/worst + 120-frame sparkline overlay,
  on every view.

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
  absent without WebGL. Hidden layer switcher: `l` / triple-click
  bottom-right.
- Single ambient dark theme — intentional exception (overnight
  monitoring tool; human's stated dark preference).

## Non-goals

- No writes beyond `/answer` (steering stays in the session).
- No historical analytics; a live window, not a metrics store.
- No public exposure; localhost only, by construction.
