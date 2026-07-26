# Dreamhub platform architecture

**Status:** design / product architecture — not implementation authority.
**Scope:** how dreamhub should work for local, LAN, and mesh-VPN operators,
and how that same stack becomes a website that sells (1) persistent tunnel
access to self-hosted dreamwork and (2) a hosted agentic experience
(OpenClaw-class providers / always-on assistants).
**Constraint from the ask:** the commercial platform need not share this
repo's architecture, and mostly will not. This repo keeps at most a **thin
local node**. Everything else is a separate product stack that speaks a
stable contract to that node.

Related local work already in flight or landed:

| Piece | Role |
|---|---|
| `dreamhub.py` stage 1 | read-only multi-project aggregator on loopback |
| `daemon-mode.md` stages 2–5 | local control plane, ssh swarm, channels, metadreamer |
| `#233` trusted LAN | Host/Origin safeguards; explicitly not auth |
| `#276` LAN bearer | simple token for LAN PCs/phones |
| `#275` public auth research | shoo.dev-informed public Dreamhub auth |
| T3 Connect research | managed tunnel + account discovery analogy |

---

## 1. Verdict in one page

Dreamhub should be three planes with hard boundaries:

1. **Node** — runs on the human's machine (or their VPS). Owns projects,
   files, secrets, agent processes, and the truth of status. Thin,
   local-first, open/self-hostable forever.
2. **Control** — discovery, aggregation, lifecycle, identity, billing,
   and the web surfaces that steer many nodes/projects. Exists in two
   deployments of the same *ideas*: a local hub process, and a cloud
   control plane.
3. **Access** — how a browser or phone reaches a node. Loopback, trusted
   LAN, mesh VPN, and managed tunnels are **four transports for one Node
   API**, not four products with four security models.

Sell two SKUs on top of that:

| SKU | What the customer buys | Where compute lives |
|---|---|---|
| **Connect** | persistent reachability + account login to *their* nodes | customer's hardware |
| **Agents** | the agentic experience itself (hosted workspaces, providers, channels) | your cloud (or BYO node later) |

Do **not** collapse reachability into authentication, or authentication into
execution. Tunnel exposure without node auth is already ruled out by the
LAN threat model and by T3 Connect's own security model. Do **not** make
the website the only way to use dreamwork — local/LAN/mesh must remain
excellent with zero cloud account.

---

## 2. Audiences and jobs

| Audience | Job to be done | Must work offline / private-net? |
|---|---|---|
| Solo local operator | glance across projects; steer without chat | yes (default) |
| Home-lab / LAN / Tailscale | phone or other PC reaches the same hub | yes |
| Connect customer | log into website, see/steer own self-hosted agents | node online; website for discovery/UI |
| Agents customer | get an always-on assistant without running infra | no (hosted) |
| Power operator | mix: some projects local, some hosted, one glance | hybrid |

The UI vocabulary stays one product language across these (status,
waiting-on-you, questions, steer) even when the backend adapter differs.

---

## 3. Architecture: three planes

```text
 ┌─────────────────────────────────────────────────────────────┐
 │  Clients: browser / phone / PWA / channel bots              │
 └───────────────┬─────────────────────────────┬───────────────┘
                 │                             │
                 ▼                             ▼
      ┌────────────────────┐        ┌────────────────────┐
      │  Local Control     │        │  Cloud Control     │
      │  (dreamhub local)  │        │  accounts, billing │
      │  aggregate+steer   │        │  Connect + Agents  │
      └─────────┬──────────┘        └─────────┬──────────┘
                │                             │
                │    same Node API contract   │
                ▼                             ▼
      ┌────────────────────┐        ┌────────────────────┐
      │  Access plane      │◄──────►│  Access plane      │
      │  loopback / LAN /  │        │  managed tunnel /  │
      │  mesh VPN          │        │  relay / edge      │
      └─────────┬──────────┘        └─────────┬──────────┘
                │                             │
                └──────────────┬──────────────┘
                               ▼
                    ┌────────────────────┐
                    │  Node (thin)       │
                    │  projects, watch,  │
                    │  loops, secrets    │
                    └────────────────────┘
```

### 3.1 Node (thin local agent)

**Owns:** project registry on this machine, process lifecycle hooks,
`status.json` / questions / events, capability secrets, optional tunnel
connector child process.

**Does not own:** accounts, billing, multi-tenant directory, marketing
site, provider marketplace, global DNS.

**Speaks a versioned Node API**, not "whatever HTML watch serves today".
Stage-1 hub already depends on `/mtime` + `/data.json`; that is the wrong
long-term remote contract (`/data.json` carries full document text —
`dreamhub-design.md` already flags `/summary.json` for linked use).

Minimum Node surface:

| Endpoint / capability | Purpose |
|---|---|
| `GET /v1/health` | liveness + node id + api version |
| `GET /v1/summary` | light aggregate: projects, states, awaiting, counts |
| `GET /v1/projects/{id}/status` | one project's glance fields |
| `POST /v1/projects/{id}/steer` | command / answer / ask (capability-scoped) |
| `GET /v1/projects/{id}/events` | optional SSE/poll of recent events |
| `POST /v1/link` / unlink | enroll node with Connect cloud (optional) |

Keep today's `watch.py` as the rich per-project UI for local/LAN. The Node
API is what aggregators and the website use so they never need to scrape
HTML or pull full docs.

**Repo fate:** evolve `dreamhub.py` (and eventually a small sibling) into
this node + local control; leave commercial control/access in another
codebase.

### 3.2 Control plane

Two deployments, one conceptual model:

| Concern | Local control | Cloud control |
|---|---|---|
| Project list | `~/.config/dreamwork/hub/projects.json` | account → linked nodes → projects |
| Auth | loopback / LAN bearer / mesh identity | account session + node capability tokens |
| Lifecycle | herdr/tmux adapter (daemon-mode stage 2) | hosted runtime orchestrator |
| UI | hub page + link-out to watch | website app (may embed or deep-link) |
| Billing | none | Connect + Agents SKUs |

Local control remains useful even for Connect customers (offline, LAN,
debugging). Cloud control never becomes the only source of truth for a
self-hosted project's files.

### 3.3 Access plane

Ordered by trust and complexity:

| Mode | Reachability | Auth baseline | Product fit |
|---|---|---|---|
| **A. Loopback** | `127.0.0.1` | physical machine trust | default forever |
| **B. Trusted LAN** | bind + Host allowlist (`#233`) | optional bearer (`#276`) | home LAN |
| **C. Mesh VPN** | Tailscale / Headscale / WG — treat as **LAN with crypto** | bearer or node mTLS; same Host rules | power users, no Connect fee required |
| **D. Managed tunnel** | CF Tunnel / own relay | account session **and** node auth | **Connect SKU** |
| **E. Hosted ingress** | your edge | account + plan entitlements | **Agents SKU** |

**Recommendation:** ship A→B→C as first-class open paths. Sell D. Build E
as a separate product that reuses glance/steer UX and adapters, not as a
forced path for self-hosters.

Mesh VPN is not a tunnel product you sell; it is a free peer of LAN. The
website still helps mesh users with account features (sync of non-secret
prefs, hosted agents alongside local ones), but Connect's paid value is
**reachability without operating a mesh**.

---

## 4. Product architecture

### 4.1 Connect — persistent tunnel access

**Promise:** run dreamwork at home; log into the website from anywhere;
see and steer your agents/projects.

**What you operate:**

- Identity provider (or buy Clerk/Auth0 — T3's path is fine early)
- Tunnel broker / connector token issuer
- Edge that terminates TLS and multiplexes to node connectors
- Thin web app: account home → nodes → projects → steer/glance
- Billing for seat/node/bandwidth tiers

**What you do not operate for Connect customers:** their repos, their
model keys, their agent processes (unless they also buy Agents).

**Critical security split (non-negotiable):**

1. **Account auth** proves who is at the website.
2. **Node enrollment** proves which machine is linked (device key / pairing).
3. **Capability tokens** authorize which projects/actions the session may
   touch.
4. **Tunnel** only moves bytes; it grants no authority by itself.

Mirrors the T3 Connect lesson: Clerk/relay identity ≠ environment session.

**UX options for opening a project from the website:**

| Option | Pros | Cons | Rec |
|---|---|---|---|
| **Link-out** to node-origin watch UI via tunnel hostname | reuses watch; fast | origin-per-project cookies; CORS; styling across hosts | good MVP |
| **Reverse-proxy** `/{node}/{project}/…` under website origin | one bookmark | needs watch path-prefix (`#124`) or HTML rewriting; silent route bugs today | after Node UI is prefix-safe |
| **Cloud-native glance UI** over Node API | one origin; mobile-clean | rebuilds surfaces; must not fork styleguide forever | medium-term primary |
| **Embed iframe** of watch | little rewrite | cookie partitioning, third-party restrictions | avoid as primary |

**Rec:** MVP = authenticated Connect portal + link-out through tunnel to
node UIs; parallel Node API powers the portal's aggregate glance so the
home page never needs full watch. Medium-term = portal becomes the glance
surface; watch remains the deep local cockpit.

### 4.2 Agents — hosted agentic experience

**Promise:** OpenClaw-shaped product — always-on assistant / dreamers,
channels, providers — without self-hosting. Optionally later attach a
BYO node.

OpenClaw's useful decomposition (gateway + channels + providers +
nodes + control UI) maps cleanly:

| OpenClaw idea | Dreamhub Agents analog |
|---|---|
| Gateway | hosted control + session router |
| Channel plugins | Telegram/Discord/… as notification & chat ingress |
| Model providers | BYOK + resold/quota'd providers |
| Nodes | optional customer-linked dreamwork nodes |
| Control UI | website Agents console (same glance language) |
| Workspace/memory | hosted durable store (not customer's disk) |

**Do not** pretend hosted Agents are the same trust boundary as local
nodes. Hosted means you can read their workspace. Product copy and
architecture must say so.

**Adapters (one interface, many backends):**

```text
ExecutionBackend
  ├─ LocalLoop        (herdr/tmux on node — daemon-mode stage 2)
  ├─ HostedSandbox    (your cloud VM/container per workspace)
  ├─ ExternalHarness  (Cursor/Codex/Claude API session adapters)
  └─ ProviderRoute    (model-only: chat/completions without full loop)
```

The hub/website talks to `ExecutionBackend`, never to a specific CLI.
That is how "sell the agentic experience" and "self-host the loop" stay
one product family.

### 4.3 SKU packaging (suggested)

| Tier | Includes | Notes |
|---|---|---|
| Open / local | Node + local hub + LAN/mesh | forever free |
| Connect | managed tunnel, account portal, N nodes | bandwidth + device limits |
| Agents | hosted workspaces, provider quotas, channels | compute + tokens |
| Bundle | Connect + Agents | one glance across local + hosted |

Unknown: seat vs node vs workspace metering — see §9.

---

## 5. Identity, auth, and threat model

### 5.1 Trust tiers (extend `#233` / `#276` / `#275`)

| Tier | Network | Auth | Writes allowed? |
|---|---|---|---|
| T0 Loopback | 127.0.0.1 | none | yes (today) |
| T1 Trusted LAN | private L2/L3 | optional bearer | yes if bearer/policy says so |
| T2 Mesh | WG/Tailscale | bearer or mutual node TLS | yes |
| T3 Public edge | internet | account + node capabilities + TLS | yes, scoped |
| T4 Hosted | your VPC | account + plan | yes, on hosted data only |

Public/WAN direct bind of `watch.py` remains **forbidden**. Connect
customers reach nodes only through Access plane D with T3 auth.

### 5.2 Token design sketch

- **Enrollment key** (long-lived, node-held): proves node identity to
  cloud; rotatable; shown once at link time.
- **Session token** (short-lived, browser): account login on website.
- **Capability token** (short-lived, audience=`node`, scoped
  `projects[]`, `actions[]`): minted by cloud after account+enrollment
  check; presented to node on each steer/summary call.
- **LAN bearer** (`#276`): local-only; never accepted via Connect edge.

Nodes must verify capability tokens offline-enough (public key / JWKS
cache) so a cloud outage does not require opening the node anonymously.

### 5.3 Data classification

| Class | Examples | May leave node? |
|---|---|---|
| Secret | API keys, enrollment private key | never via tunnel as clear log |
| Private project | source, questions, dreams | only via authenticated session to owner |
| Glance metadata | dreaming/quiet, counts, task one-liner | Connect portal OK |
| Telemetry | versions, errors, opt-in | product analytics |

Default: Connect portal stores **glance + routing metadata**, not full
repo contents. Deep file views stay on-node (link-out) until an explicit
sync product exists.

---

## 6. Local / LAN / mesh: make them first-class

Commercial pressure usually wrecks local UX. Guardrails:

1. **Local hub works with cloud binary deleted.** No phone-home required.
2. **Mesh VPN is documented as the preferred free remote path** (same as
   OpenClaw's Tailscale guidance). Connect is convenience, not monopoly.
3. **One Node API** for local hub and cloud portal — no second parser of
   `questions.md` (reuse rule from stage 1).
4. **Origin-per-project survives** for local deep UIs until watch is
   prefix-safe; ssh/`-L` and mesh hostnames are the same shape.
5. **Bearer on LAN** before encouraging phone use (`#276`).
6. **mDNS / Tailscale MagicDNS names** in allow-host workflows — exact
   Host tokens, no wildcards (keep `#233` invariants).

### Recommended local progression (this repo / thin node)

1. `/summary.json` (or Node `/v1/summary`) on watch — cheap aggregate.
2. `#276` bearer design + implement.
3. Dreamhub local control plane (daemon-mode stage 2) — still loopback/LAN.
4. Mesh runbook: Tailscale serve / WG peer as LAN equivalent.
5. Optional Connect connector as a **plugin child**, not baked into
   watch's default path.

---

## 7. Cloud stack options

The commercial half should be a **new codebase**. Options:

### 7.1 Control + web app

| Option | When | Trade |
|---|---|---|
| **TypeScript full-stack** (Next/Remix + API) | need fast website + auth vendors | different language from node |
| **Go/Rust edge + TS web** | tunnel/relay performance matters | two runtimes |
| **Python** (FastAPI) | reuse dreamwork people | weaker for high-fanout tunnel edge |

**Rec:** TypeScript (or Go) for cloud control/web; keep Node in Python
stdlib-ish so local install stays trivial. Do not drag `watch.py`'s HTML
into the cloud binary.

### 7.2 Tunnel / relay

| Option | Pros | Cons |
|---|---|---|
| **Cloudflare Tunnel** (T3 path) | ship fast, NAT-friendly, ops light | vendor lock, pricing, policy risk |
| **Own QUIC/WS relay** | control, margin, branding | serious ops/security work |
| **Tailscale Funnel / serve** | great for power users | not a multi-tenant product you meter easily |
| **Hybrid** | CF early; own relay when scale/margin demand | migration cost |

**Rec:** Hybrid. Connect MVP on managed tunnel (CF or equivalent). Design
Node enrollment so the connector binary is swappable (`TunnelDriver`
interface). Mesh remains unsupported-as-SKU but documented.

### 7.3 Hosted Agents runtime

| Option | Pros | Cons |
|---|---|---|
| Firecracker / gVisor microVMs | strong isolation | heavier platform |
| Containers on Kubernetes | familiar | weaker isolation for arbitrary agent tools |
| Rent Cursor/cloud-agent style envs | buy vs build | margin, dependency |
| "Bring your VPS" with installer | light ops | support burden |

**Rec:** start with tightly scoped HostedSandbox (no arbitrary customer
root) + provider routes; expand isolation as tool surface grows. Do not
offer full desktop-equivalent agents on day one.

### 7.4 Channels

Daemon-mode already wants ntfy/Telegram/Discord/Teams as **plugins with
their own deps**. Cloud Agents should use the same plugin interface so a
channel works for local gateway and hosted gateway. That is the OpenClaw
gateway lesson applied here.

---

## 8. Implementation architecture (phased)

This is a sequencing plan, not a calendar. Each phase ends with a
checkable edge (what it is / is not), in the dreamhub stage-1 style.

### Phase 0 — Contracts (design-only, blocks everything)

Deliverables:

- Node API OpenAPI / protobuf sketch (`/v1/...`)
- Capability token claims schema
- Data classification table frozen
- Threat models: LAN bearer, Connect edge, Hosted Agents
- Decision records for tunnel driver + UI strategy (link-out vs native)

Exit: human approves contracts; `#275` research consumed or superseded.

### Phase 1 — Harden local access (this ecosystem)

- `/summary.json` on watch
- `#276` bearer for LAN/mesh
- Hub consumes summary, not full `/data.json`, when available
- Mesh VPN runbook

Exit: phone on Tailscale can glance/steer with bearer; public bind still
impossible.

### Phase 2 — Local control plane (daemon-mode stage 2)

- Runtime adapter (herdr|tmux)
- Lifecycle from hub
- Still no public internet path

Exit: web start/pause/wrap on localhost/LAN; read-only edge of stage 1
deliberately crossed with a new checkable boundary.

### Phase 3 — Connect MVP (new repo)

- Accounts + billing stub
- Node link/enroll CLI
- Tunnel driver v1
- Portal: list nodes/projects from Node summary
- Link-out to deep watch UI
- Audit logs: who steered what

Exit: customer can buy Connect, link a home node, steer from phone on
cellular without Tailscale.

### Phase 4 — Agents MVP (new repo, same org)

- HostedSandbox backend
- One channel (Telegram or ntfy) + one provider path
- Portal shows hosted workspaces beside linked nodes
- Clear trust labeling (hosted vs self-hosted)

Exit: paying customer runs an always-on dreamer with no home server.

### Phase 5 — Convergence

- Cloud-native glance UI primary; watch remains deep cockpit
- Path-prefix or node-served authenticated UI under one origin if needed
- Provider/channel marketplace
- Metadreamer guardrails (daemon-mode stage 5) for both local and hosted
- Optional: customer relay / region pinning / SSO

---

## 9. Unknowns, risks, and open decisions

Surfaced explicitly so they do not hide inside a pretty diagram.

### Product / business

1. **What is Connect's unit of sale?** Node, seat, concurrent tunnel,
   GB transferred, or "family home" flat fee?
2. **Agents margin:** BYOK vs resale; who eats runaway tool loops?
3. **Positioning vs OpenClaw / T3 / Cursor Cloud Agents:** complementary
   (dreamwork loop + multi-project glance) or head-on?
4. **Is the website brand "dreamhub", "dreamwork", or new?** Local tools
   already use both names.
5. **Team / multi-user on one node:** out of scope initially? Couples
   affect capability tokens and audit.

### Security / legal

6. **Hosted agents + shell tools = abuse/legal exposure.** Need policy,
   isolation, and possibly disallow network-from-agent until reviewed.
7. **Connect as covert exfil path** if capability scope is wrong —
   default deny actions; summary is read-mostly.
8. **Jurisdiction / logging** of tunnel metadata and steer payloads.
9. **`#275` shoo.dev model** may or may not fit — research not done;
   do not freeze IdP choice before that lands or is explicitly skipped.

### Technical

10. **Watch root-absolute URLs** still block clean single-origin proxy
    (`dreamhub-stage1` deviation). Connect MVP should not wait on `#124`
    if link-out works.
11. **Polling vs push** over tunnels: today's 2s `/mtime` poll is fine
    locally; over tunnels it wants backoff, `/summary` cache, or SSE.
12. **Node offline UX:** portal must show last-seen honestly (stage-1
    liveness rule), never freeze ages as present.
13. **Multi-hop:** hub-of-hubs (machine registry + project registry)
    vs flat node list — swarm stage wants host-qualified projects.
14. **Windows/macOS node install** story for Connect customers who are
    not already dreamwork skill users.
15. **Connector auto-update** vs dreamwork's deploy-snapshot discipline
    — conflicting instincts; needs a policy.
16. **End-to-end encryption** of tunnel payload to node (edge terminates
    TLS today in CF model) vs true E2E — product claim depends on this.

### UX

17. **One glance across local + hosted** without implying same trust.
18. **Mobile steer:** composer/commands on small screens; PWA from
    daemon-mode stage 4 may matter more for Connect than for local.
19. **Waiting-on-you** notifications: channels product overlaps Connect
    value; decide whether push is free or Agents-tier.

---

## 10. Recommendations (locked enough to plan against)

These are the load-bearing choices proposed for human confirmation:

1. **Three planes** (Node / Control / Access); Connect sells Access+Control
   login; Agents sells hosted ExecutionBackend.
2. **Thin Node in/near this repo**; commercial cloud in a **new repo**.
3. **Mesh VPN = free LAN peer**; do not require Connect for remote access.
4. **Tunnel ≠ auth**; capability tokens to the node always.
5. **Node API + `/summary`** as the aggregator contract; stop shipping
   full `/data.json` over links.
6. **Connect MVP = portal glance + link-out**; native portal UI grows later.
7. **Tunnel driver interface**; CF-or-equivalent first, swappable later.
8. **ExecutionBackend adapters** unify local loops and hosted Agents.
9. **Channels as plugins** shared conceptually across local and cloud.
10. **Local excellence is a product requirement**, not a nostalgia mode.

### Explicitly deferred / rejected for now

- Rewriting watch+loop into one cloud service (rejected in `daemon-mode.md`).
- Making path-prefix proxy a Connect blocker.
- Public unauthenticated bind of watch/hub.
- Treating T3 Connect as the streaming/control substrate (research:
  reachability only).
- Building marketplace/providers before Connect enrollment works.

---

## 11. Mapping to existing dreamwork stages

| Existing stage | Platform role |
|---|---|
| Dreamhub stage 1 (landed) | local Control prototype (read-only) |
| `#233` / `#276` / `#275` | Access + auth ladder |
| Daemon-mode stage 2 | local ExecutionBackend + Control writes |
| Daemon-mode stage 3 (ssh swarm) | multi-node before Connect; host-qualified IDs |
| `/summary.json` + `#124` prefix | Node API + optional single-origin |
| Daemon-mode stage 4 channels/PWA | Agents + Connect notification surface |
| Daemon-mode stage 5 metadreamer | needs quotas/guardrails on both local and hosted |

Connect and Agents are **not** "stage 6 of this repo". They are a sibling
product that consumes the Node contract stages 1–3 force into existence.

---

## 12. Suggested next human decisions (blocking)

Answer these to turn this architecture into build authority:

1. Confirm **three-plane + two-SKU** split (or name another packaging).
2. Confirm **mesh-first free remote** vs Connect-required remote.
3. Choose **Connect MVP UI**: link-out vs wait for single-origin.
4. Choose **tunnel strategy**: CF-managed MVP vs build relay first.
5. Scope **Agents MVP**: dreamwork-loop-hosted vs chat-gateway-first
   (OpenClaw-like) vs both thin slices.
6. Say whether `#275` must complete before any Connect IdP code, or
   whether a temporary IdP is acceptable behind a feature flag.

Until those are answered, Phase 0 contracts can be drafted, but Phases
3–4 should not start.

---

## 13. Document control

- **Authority:** proposal only. No implementation, billing, or public
  exposure is authorized by this file.
- **Home:** `.dreamwork/docs/plans/dreamhub-platform-architecture.md`
  (planning record in the skill repo). Commercial implementation will
  live elsewhere once approved.
- **Update rule:** when a blocking decision in §12 is answered, record it
  here in the same commit that unlocks the next phase plan.
