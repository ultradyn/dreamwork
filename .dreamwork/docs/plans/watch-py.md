# watch.py — live dreamloop dashboard (plan)

Human-authorized 2026-07-25 ("launches a livereloading server … status
dashboard about the dreamloop as it runs … open their browser"). This plan
pins *how*; stages land as separate committed increments.

## What it shows

- **Dreams** — active and archived, with ages; click to read (rendered or
  plain text). The journal is the heart of the page.
- **Main files** — DREAMWORK.md, questions.md (open count surfaced),
  lessons.md, skill-version; click to view.
- **Loop status** — everything reachable: git log tail (last ~15, marker
  commits highlighted), migrations vs target version, roll.py weights
  (`--list` output), and `.dreamwork/status.json` when present (see
  below).
- Header: target path, heartbeat freshness (from status.json), open
  questions badge.

## Design decisions

- **Stdlib only, self-contained** (http.server + a single embedded HTML
  page). Portability beats leveraging any machine-specific serving infra.
- **Bind 127.0.0.1 only.** The dashboard reads project files; never
  expose beyond localhost. No write endpoints at all — strictly read-only.
- **Port**: `--port` flag; default generated per Max's dev-server norm
  (random 3000–63000, chosen once and persisted to
  `.dreamwork/watch-port` so bookmarks survive restarts).
- **Live reload**: JS polls a `/mtime` endpoint (max mtime across watched
  paths) every ~2s; on change, re-fetch `/data.json` and re-render.
  No websockets, no dependencies.
- **`--open`**: launch the browser via `webbrowser.open` (cross-platform,
  stdlib) after binding.
- **status.json** (stage 3, own migration): the loop writes
  `.dreamwork/status.json` at each tick — current task subject, queue
  depth, last tick time, last commit — because the native task list isn't
  on disk. Dashboard degrades gracefully when absent.

## Stages (each ≤ ~20 min, committed separately)

1. **Server core**: watch.py serving `/` (embedded page), `/data.json`
   (dreams list + file contents + git tail), `/mtime`; port persistence;
   `--open`. Smoke-tested via curl.
2. **Dashboard page**: render the data — dreams with ages and
   click-to-expand, files, git tail with marker highlighting. Dark,
   simple, no framework.
3. **status.json convention**: SKILL.md line (loop writes it per tick,
   best-effort), migration entry, dashboard header consumes it.
4. **Tests + polish**: unit tests for the data collector (pure function
   over a directory), `--no-open` default in tests; README note in
   SKILL.md commands or durable-state section pointing at watch.py.

## Non-goals

- No write/interact endpoints (steering stays in the session).
- No historical analytics; this is a live window, not a metrics store.
- No public exposure; localhost only, by construction.
