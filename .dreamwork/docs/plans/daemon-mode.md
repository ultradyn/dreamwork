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

## Decisions (Max, 2026-07-25 ~09:45)

- **Runtime**: session-manager-managed CLI sessions — prefer **herdr**
  (docs: `~/.llm-general/ai-coding/herdr/` — server, protocol, input,
  stoppage), tmux as fallback, behind an **adapter model** so either
  works. Dedicated herdr session per swarm so Max can attach to
  debug/inspect.
- **Any-CLI insight** (Max): herdr/tmux + stop hooks + send-keys +
  dreamhub's own dynamic monitoring supports *any* coding CLI (e.g.
  cursor agent) even without a Monitor tool — the hub injects messages
  directly. Dreamhub becomes the wake/steer transport, not the
  harness.
- **Web lifecycle**: rec accepted — pause/resume/wrap from the web;
  project add/remove stays CLI.
- **Exposure**: not localhost-forever — spawning over **ssh** and
  managing remote dreamers is wanted, one hub covering a swarm.
  Implies URL/path adjustments and UX for host-qualified projects
  (auth story to design before any non-local bind).
- **Channels**: ntfy/Telegram/PWA-push defaults confirmed; add
  **Discord and Teams**. Reference implementations to mine:
  `~/src/clawq`. Channels are **plugins** that may install their own
  dependencies — keeps the bug surface off the core.
- **PWA**: yes, on the hub. **Tauri**: deferred, consideration-stage.
- **Metadreamer** (new): in bg/daemon mode dreamers may spawn other
  dreamers — enabling a metadreamer that manages projects in general
  and the other dreamers. (Recursive delegation needs its own
  guardrails: depth limits, budget, the no-attn and machinery rules
  cascade.)

## Staging (revised per decisions)

1. **dreamhub aggregator** — `/` list + `/{project}/` proxy over
   existing watch instances; stdlib.
2. **Runtime adapter** (herdr | tmux) + hub-driven wake/steer
   (send-keys + stop hooks); lifecycle controls in the hub.
3. **Swarm**: ssh spawn/attach of remote dreamers; host-qualified
   URLs; auth story.
4. **Channel plugin architecture** (own deps allowed) — ntfy,
   Telegram, Discord, Teams; PWA shell + push on the hub.
5. **Metadreamer** — dreamer-spawns-dreamer + management guardrails.

Build not yet started; stage 1 is ready to plan in detail on Max's go.
