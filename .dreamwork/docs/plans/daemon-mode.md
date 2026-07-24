# Daemon mode — brainstorm (#96, pre-plan)

Human-proposed 2026-07-25 (~09:28) as a big idea: dreamwork as a
persistent daemon running multiple dreamers across different projects,
steerable entirely from the web when backgrounded. Brainstorm stage —
this doc maps the option space and splits what's auto/rec-able from
what needs Max. Nothing here is authorized to build yet.

## Vision in one line

Dreamwork stops being one terminal session and becomes an ambient
service: several projects dreaming at once, one web surface to watch
and steer them all.

## Architecture options (the load-bearing choice)

1. **Aggregator first (rec).** Keep loops exactly as today (one session
   per project, own watch instance on its persisted port). Add a thin
   `dreamhub` server: `/` lists projects, `/{project}/...`
   reverse-proxies to that target's watch port (ports already persist
   in `.dreamwork/watch-port`). Zero change to the loop; multi-project
   webui lands immediately; daemon can grow around it later.
2. **Supervisor daemon.** A daemon owns project registry + lifecycle:
   starts/stops headless agent sessions (CLI headless mode / agent
   SDK), owns the heartbeat scheduling (cleaner than per-session
   monitors — the daemon wakes sessions), serves the unified web UI.
   The full vision, much more new surface.
3. **Server-product rewrite.** Watch and loop rebuilt as one long-lived
   service. Rejected for now: discards the working session model and
   the harness's tooling.

Rec: 1 → 2 staged; 1 is buildable now and nothing in it is wasted by 2.

## URL space (auto-resolvable, per Max's sketch)

`/{project}/...` prefix; `/` = project list under the daemon/hub, or a
redirect to `/{project}/` when a single watch runs standalone. Project
slug = target dir basename (collision → short hash suffix). The
world-space shader + per-route seeds make each project's pages visually
distinct for free (per-project tint/seed offsets — nice identity cue).

## Web-only steering: what's missing today

Already there: composer commands, question answering, threaded
follow-ups, review artifacts, live status. Gaps for chat-free
operation: (a) loop lifecycle (start/pause/resume/wrap) from the web —
needs an authority decision; (b) longer-form conversation (design
reviews richer than a follow-up thread); (c) attn-equivalent outbound
push when the human is away from the page. (c) is "channels" below.

## Needs-Max decisions

- **Agent runtime for bg mode**: headless CLI sessions under the
  daemon vs SDK-driven loop vs tmux-managed interactive sessions.
  Cost, resumability, and tooling access differ; taste call.
- **Lifecycle authority**: may the web UI start/stop loops? (Rec: yes
  for pause/resume, wrap; project add/remove stays CLI.)
- **Exposure**: localhost-only stands today; multi-device LAN use (the
  hark ssh-pair spirit) would need explicit opt-in + auth story.
- **Channels**: which outbound push (ntfy/Telegram/desktop
  notifications via PWA) and does a channel accept inbound commands?
- **PWA vs Tauri**: rec PWA first (manifest + service worker on the
  hub — installable, push-capable, tiny); Tauri only if native needs
  emerge (tray, global hotkeys). Both can wait for the hub.

## Staging sketch (post-brainstorm, if approved)

1. dreamhub aggregator (`/` list + `/{project}/` proxy) — small,
   stdlib, composes existing watch instances.
2. Session-lifecycle controls in the hub (authority per decision).
3. Daemon supervision + daemon-owned heartbeats (bg mode proper).
4. PWA shell + channels.

## Open thread

Brainstorm with Max: which gaps bite first in real use? His answers
reshape staging before anything is planned in detail.
