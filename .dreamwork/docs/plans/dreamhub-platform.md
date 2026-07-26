# dreamhub as a platform — architecture, product, staging (pre-plan)

Human-proposed 2026-07-26: *"plan and design the optimal dreamhub
architecture so that it works great for people who want to run it locally
or over their lan/meshvpn, and also so that I can turn it into a website
that sells both persistent tunnel access (locally hosted + log in to
website for access to one's own dreamwork agents / projects) and also
sells the agentic experience itself (like OpenClaw providers etc)"*, with
the shape already decided: *"does not need to be built on same
architecture or in this repo (and in fact won't be except maybe a thin one
like now for locally hosted nodes)."*

**Pre-plan. Nothing here is authorized to build.** It maps the option
space, states what is measured and what is guessed, and ends in a list of
decisions only he can make. The settled decisions in `daemon-mode.md`
(herdr-preferred runtime adapter, web lifecycle, ssh swarm, channel
plugins, PWA yes / Tauri deferred, metadreamer) are not re-opened; several
of them turn out to be on this plan's critical path and are named where
they are.

Chain: this serves **"one human, several dreaming agents"** (DREAMWORK.md,
#96) and then leaves it — see D0 below, which is the one decision that
must be answered before any of the rest is even coherent.

## D0 first: this ask changes the goals, not just the surface

Every goal in DREAMWORK.md is written about **one human**: *"the human can
walk away and come back to steady, safe, well-chosen progress"*, *"the loop
gets on the human's wavelength over time"*. `dreamhub-design.md` is written
about *him*, singular, by design — "one glance tells **him** which of his
dreamers has stopped moving."

Selling tunnel access and hosted dreamers means the loop acquires
**users who are not Max**, and that is a different product with different
obligations: support, uptime, threat models with hostile peers, data
handling for other people's source code, refunds, and a compatibility
promise where today there is a migration note. The repo's own philosophy —
*"scope expansion defers to the human"* — makes this exactly the kind of
widening that must be ratified in DREAMWORK.md rather than inferred from
an ask for an architecture.

So D0 is: **does "someone other than Max is a user" become a stated goal,
and if so at which stage?** Everything downstream (compatibility promises,
error copy, the honesty of the security statement, whether "unsupported"
is an acceptable answer) reads differently depending on the answer. The
rest of this document assumes yes-eventually and marks the point where it
starts to matter.

## Three products, and the single boundary that separates them

| | P1 · local / LAN / mesh | P2 · tunnel + identity | P3 · hosted dreamers |
|---|---|---|---|
| Whose machine runs the loop | theirs | theirs | **ours** |
| Whose machine holds the code | theirs | theirs | ours (checkout of their repo) |
| Whose machine holds the model key | theirs | theirs | ours, at runtime, supplied by them |
| What we operate | nothing | a relay + a website | a fleet of sandboxes |
| What they pay for | nothing | reachability, identity, push, fleet | all of P2, plus compute and orchestration |
| Our marginal cost | zero | bytes | a warm VM + their token spend |
| Trust they must extend | none | a courier that can see traffic it forwards | a host that can read their code and their key |

The claim this whole architecture rests on:

> **P2 and P3 differ only in who owns the machine the node runs on. P1 is
> the same node with the relay switched off.**

If that is true, there is one node, one API, one client, and three
topologies — and the hosted product is not a second implementation of
anything. If it is false anywhere, that place is where the design has a
hole. The places it is closest to false are named in *Unknowns* below
(hibernation, harness ToS, and the fact that a hosted node's filesystem is
not a human's filesystem).

**P1 must never require us.** No account, no network, no relay, no
build step, no login — the thing that works on a plane keeps working on a
plane. This is a design constraint with a checkable edge (S2 gate: the
node runs with the relay unreachable and every local surface is
unaffected), and it is also the honest position: a lapsed subscription
must never lock a human out of his own machine.

## The market anchor, and what it implies about sequencing

Measured from the comparable market (OpenClaw hosting, 2026): managed
hosting sells at **$15–60/month**, almost all of it BYOK, while the
customer's model spend runs **$50–200+/month and typically exceeds the
hosting bill**. Bundled-credit tiers exist at $40–100 and exist mainly to
remove the API-key step for non-technical buyers.

Three consequences, and they order the roadmap:

- **P2 is the good business.** Its marginal cost is bytes; its trust ask
  is small; it needs no sandbox fleet, no spend caps, no abuse team. It is
  also the only tier that is *strictly better* than the alternative the
  buyer already has (Tailscale plus remembering which port), because it
  adds identity, aggregation across machines, push, and a phone-shaped
  client.
- **P3's margin is thin and volatile**, because the dominant cost is
  somebody else's token bill and dreamwork is a *deliberately
  always-warm* workload (see *Hosted runtime*). BYOK first; bundled
  credits only once the per-dreamer distribution is measured rather than
  modelled.
- **The differentiator is not hosting.** It is the loop's discipline
  (small increments, durable memory, questions that wait for you) and a
  dashboard that is worth looking at. Both of those already exist. The
  platform's job is to stop them being reachable only from one machine.

## The load-bearing choice: where the seam goes

Today's shape: one `watch.py` process per project, filesystem-coupled,
serving a page it renders itself; `dreamhub.py` polls each one over
localhost HTTP and links out. Three ways to grow that into a platform.

### Option 1 — reverse-proxy the existing watch instances

The hub becomes a proxy; the tunnel exposes the hub; hosted mode is a
container per project with a watch inside.

Cheapest to start, and it is what `daemon-mode.md` originally sketched.
Costs, in order of how much they hurt:

- It needs the URL prefix (#133) anyway, which is the reason stage 1 went
  origin-per-project in the first place.
- The website's UI is then forever whatever `watch.py`'s single-file
  renderer can express. There is no seam at which a login shell, a fleet
  view, a billing page, or an offline state can live.
- The payload problem stays: **320,840 bytes** of `/data.json` per change,
  measured on this repo today (`files` 122 KB, `dreams_archive` 101 KB,
  `answered_entries` 42 KB, `dreams` 27 KB, `linkable_paths` 9 KB), and
  `collect()` costs **0.375 s** of wall time per call. A relay priced on
  bytes cannot forward a third of a megabyte per file save.
- N python processes per user, each with its own auth surface.

### Option 2 — a node API, and every surface becomes a client of it (rec)

One process per **machine** (`dreamnode`), not per project. It owns the
registry, the readers and writers for `.dreamwork/`, the runtime adapter,
and a small versioned API: **resources with ETags, an event stream of
change notices, and intents that return receipts.** Every surface — the
local page, the hub page, the website, the phone — is a client of that
API. The relay forwards it. The hosted runner runs one inside a sandbox.

This is the option that makes the central claim true: the website and the
sandbox consume the same API a laptop serves, so P2 and P3 stop being
separate products to build.

It has a real cost, stated plainly: it requires the **server-core seam of
#124** (routing, `resolve_confined`, `/data.json`, the status reader) and
the **client extraction** that lets the same page mount under a prefix and
under a different origin. That is the largest structural change this repo
has contemplated, and #124's own plan says not to do it as one big split.
The staging below takes it in slices that each pay for themselves locally
before any of it is load-bearing for a paid product.

### Option 3 — rebuild watch and the loop as one hosted service

Rejected, for the same reason `daemon-mode.md` rejected it: it discards
the session model and the harness tooling that make the loop work at all,
and it would put the file-format interpreters — the only implementation of
what a `questions.md` is — inside a server we host. That inverts the
property that makes P1 possible.

**Rec: option 2.** The rest of this document assumes it.

## The architecture, component by component

```
   THEIR MACHINE                      OUR INFRASTRUCTURE            ANY BROWSER
 ┌──────────────────────┐          ┌────────────────────────┐    ┌──────────────┐
 │ dreamnode  (stdlib)  │  wss     │ relay                  │    │ web app      │
 │  registry            │◀────────▶│  node link + auth      │◀──▶│  fleet       │
 │  .dreamwork readers  │ outbound │  session multiplexer   │    │  project     │
 │  intent writers      │   only   │  sealed intent queue   │    │  account     │
 │  runtime adapter     │          │  push fan-out          │    └──────────────┘
 │  /v1 API + SSE       │          │  summary cache (opt-in)│           ▲
 └──────────┬───────────┘          └───────────┬────────────┘           │
            │  LAN / mesh VPN, bearer token    │                        │
            └─────────────────────────────────▶│  artifact origin ──────┘
                                               │  (separate, sandboxed)
 ┌──────────────────────┐                      │
 │ hosted runner (ours) │──────────────────────┘
 │  sandbox = dreamnode + coding CLI + checkout + heartbeat
 └──────────────────────┘
```

### `dreamnode` — the thin local thing, and the only interpreter

Lives in **this repo**, stdlib-only, no build step, deployable by the same
snapshot pattern (`git archive` into a versioned directory, as
`parallel-architecture.md` already anticipated for a multi-file layout).

It is the grown-up dreamhub: today's registry and disk probe, plus the
readers currently inside `watch.py`, plus writes, plus the API. It serves
several projects and keeps `resolve_confined()`'s guarantee **per
project** — a request scoped to project A must not be able to read
project B's tree, which is a new invariant the single-target design got
for free and the multi-project one must test for.

The rule that makes the rest of the stack cheap is the one this repo
already wrote for the hub, promoted one level:

> **Only the node knows what a `.dreamwork/` is.** The relay, the website
> and the hosted runner move opaque JSON. Nothing outside this repo
> parses `questions.md`, counts open questions, classifies a state, or
> appends an answer.

Consequences worth having:

- The platform repo can be any language and never inherits a file format.
- `lint.py`'s property survives — it calls the *real* readers, so a clean
  pass still means the real reader can see the file.
- The "duplicate trivia, never duplicate an interpreter" trade stays
  bounded across a repo boundary, where it would otherwise be invisible.
- A checkable edge: **the platform repo contains no `.dreamwork` parser**,
  which is grep-able in its CI (no `questions.md`, no `## Open`, no
  `status.json` field names).

### The relay — a courier with an address book

New repo, ours, any language. Nodes dial **out** to it over WSS, so no
port forwarding, no DNS, no certificates for the user, and CGNAT works.
It does four things and should be resisted from doing a fifth:

1. **Authenticates a node to an account** and multiplexes browser sessions
   to it (request/response and streams framed over the one link).
2. **Queues intents** while a node is offline, sealed to that node's
   public key, with a TTL and a receipt id.
3. **Fans out push** (Web Push/VAPID, and stage-4 channels) when a node
   reports it is waiting on a human.
4. **Caches a per-project summary**, opt-in and per project, so the fleet
   list is useful when the laptop is shut.

What it must not become: a place that stores project content, renders a
page, or parses anything from `.dreamwork/`.

**Build vs buy.** A generic reverse tunnel (chisel, frp, rathole,
Cloudflare Tunnel) forwards bytes and knows nothing about accounts,
intents, receipts or capabilities — and *authorization is the product
here*, not transport. Rec: **own the link protocol, keep it small**, and
treat "bring your own tunnel or mesh VPN" as a supported P1 path rather
than the paid one.

### The web app — a shell around the page that already exists

New repo, and the first place a build step is acceptable (see D2). Two
parts, and keeping them separate is the point:

- **The shell** is new: login, node and project navigation, absent-node
  states, device linking, notification settings, billing, onboarding.
- **The project view is the extracted watch client**, mounted. Not a
  reimplementation. `watch-design.md` is 120 KB of decided design and
  `transitions.md` governs every motion on it; a second project view would
  diverge on the first bug fixed in only one of them, and the styleguide
  already names why — *"a second palette would read as a second
  product."*

### The hosted runner — a node that happens to be ours

New repo. One sandbox per project: a VM-isolated container holding a
checkout, a coding CLI with the skill installed, a wake mechanism, and a
`dreamnode` that dials the same relay a laptop dials. If the runner needs
an API the laptop's node does not have, that is a design smell and a
signal that P3 has drifted into being its own product.

### The artifact origin — separate, because `/reviewraw` serves raw HTML

`watch.py` serves `.dreamwork/review/<name>` **as-is, up to 2 MB, in an
iframe on the same origin as the dashboard**. Locally that is fine: it is
your own repo, and the artifacts are the loop's own decision documents.
Hosted, it is a stored-XSS delivery path — an artifact (or a file a
contributor added to a repo) can script the page it is embedded in and
take the session with it.

So: artifacts are served from a **separate origin**, sandboxed
(`<iframe sandbox>` plus a restrictive CSP), never from the API or app
origin. This is the same instinct as the repo's origin-per-project
decision, one level up, and it argues on its own for **origin isolation
per node** in the URL layout.

## What each component is allowed to know

The honest version, because a privacy claim that is not true is worse than
none.

| | live traffic | queued intents | summaries | project content at rest |
|---|---|---|---|---|
| node | everything | — | authors them | holds it |
| relay | **can read what it forwards** | sealed, cannot read | reads (opt-in) | never stores |
| website JS | everything the session opens | its own composed text | reads | never stores |
| us, operationally | policy: no body logging | cannot decrypt | can | no |

**TLS terminates at the relay, so the relay can read live traffic.**
End-to-end encryption against ourselves is theatre while we serve the
client JavaScript — we could always ship a client that leaks. What
sealing genuinely buys is protection of data **at rest**: an answer typed
on a phone while the laptop is asleep is a small, write-only payload that
the relay never needs to read, so it should be sealed to the node's public
key and the relay should be unable to decrypt its own queue.

The device that composed a queued intent can still show the human his own
words, because `IndexedDB dw-submissions` already records every submission
before the request leaves the browser (#175). Another device shows
"queued from your phone" without the text. That is a real limitation and
an honest one.

Summaries are the interesting consent question: the fleet list is only
useful offline if task titles, goals and `awaiting_human` lines have left
the machine. So it is **opt-in per project**, the page says when it is
showing a cached summary and how old it is, and a project that has not
opted in reads *"asleep — nothing cached"* rather than a stale row
pretending to be live. The alternative (never cache) is defensible and
should be the default for a first release.

## The protocol, in one page

Full contract: **`dreamnode-api.md`** (sibling doc). The shape and the
three decisions inside it:

- **Resources, not one snapshot.** `summary` (a fleet row: state, task,
  `awaiting_human`, counts, deploy staleness — hundreds of bytes) and then
  `status`, `questions`, `answers`, `ledger`, `dreams`, `reviews`, `git`,
  `burndown`, `file` on request, each with an ETag. Measured motivation:
  320,840 bytes today, of which the fleet view needs approximately none
  and a phone reading one question needs about 10 KB.
- **The event stream carries change notices, not payloads.** SSE
  `{seq, project, resource}`, resumable by `Last-Event-ID`; the client
  refetches what its current view needs. This is the same reasoning as
  "one renderer, and it is the Python one" — a delta merger on the client
  is a second interpreter that agrees with the first only on the day it
  is written. WebSockets are scoped to exactly one future feature: the
  PTY channel (#201).
- **Writes are intents with idempotency keys, and they return receipts.**
  `POST /v1/projects/:id/intents` with a client-minted `idem`; a repeat
  returns the same receipt rather than a second write. This is not a new
  mechanism invented for remoteness — it is #274 (duplicate identical
  submissions, witnessed) and #263 (one durable receipt spine) landing
  once and serving both. A queued-then-delivered intent is the same
  receipt in a different state, which is what makes the phone-then-laptop
  path legible.

Version skew is designed for rather than avoided: the node advertises
`capabilities`, and the website degrades **visibly** — *"this node cannot
do lifecycle; upgrade it"* — because the alternative is a control that
does nothing, and this repo has already paid for a command channel
nothing read.

## Auth, in three planes

Three separate problems that get confused because they all say "login".

**Plane 1 · node ↔ relay.** The node generates an Ed25519 keypair on
first run; `dreamnode link` shows a short code (and a QR); the website
binds code → account; thereafter the node authenticates by signing a
challenge. The relay never holds a secret that could impersonate a node,
and `dreamnode unlink` is a local kill switch that does not require us to
be reachable or solvent.

**Plane 2 · browser ↔ relay.** Ordinary web sessions. `shoo.dev`, which
he named, is a minimal Google-only OAuth+PKCE broker giving a
domain-scoped `pairwise_sub` and an ES256 `id_token` verifiable by JWKS
with no server SDK — genuinely elegant, and its own docs currently say
*"SUPER EARLY WIP — USE AT YOUR OWN RISK."* Rec: **own the account
record**, store a verified email alongside whatever subject the broker
gives, and treat the broker as a swappable front door. Then shoo is fine
to ship behind, and its disappearance costs a re-bind rather than the
customer list. Billing identity has to be ours regardless.

**Plane 3 · browser ↔ node, directly (LAN / mesh).** This is #276, and
it is what makes P1 good rather than merely possible:

- A bearer token, delivered by a one-time URL or QR from the CLI, stored
  in an `httpOnly` cookie scoped to that origin. **Never in a query
  string** — it lands in logs, history and referrers.
- The Host allowlist and the POST Origin check from #233 **stay**. They
  do a different job (rebinding, CSRF) and the threat-model artifact's
  sentence remains true: *"Host and Origin checks are necessary, but they
  are not login."*
- Scopes and revocation from the start: a phone token that reads and
  answers is not the token that may restart a loop.
- **TLS on the LAN is the unsolved part**, and there are four honest
  answers: (a) accept plaintext on a trusted LAN, as today, documented;
  (b) let the **mesh VPN be the encryption** — Tailscale/WireGuard, which
  is what he already has and the reason "meshvpn" is in the ask, making
  the token defence-in-depth rather than the only wall; (c) self-signed
  certificate pinned via the QR; (d) the paid service issues a real
  certificate for a name that resolves to a LAN address (the trick Plex
  uses), giving `https://` with a valid cert on a home network with zero
  configuration. Rec: (b) as the documented path now, (a) as the explicit
  fallback, and (d) filed as **the strongest reason a local-only user
  would ever pay us** — it is a genuine benefit that does not require
  sending anything anywhere.

## Authority: what a remote session may do

The sentence that has to be in the design and in the marketing copy:

> **An authenticated web session on a linked node is remote code execution
> on that machine.** The loop steers an agent that runs commands, edits
> files and pushes to git. "Answer a question from the pub" and "run
> arbitrary code on my laptop from the pub" are the same feature seen from
> two angles.

Therefore authority is the node's to enforce, never the relay's, and it is
graded:

| Intent class | Examples | Default over relay | Default over LAN token |
|---|---|---|---|
| read | resources, artifacts | allow | allow (scoped) |
| respond | answer, note, ask | allow | allow |
| steer | `do now`, `do next`, `add idea`, tint | allow | allow |
| lifecycle | pause, resume, wrap, restart a loop | **deny, opt-in per project** | opt-in |
| runtime | attach a PTY, send keys, run a command | **deny, opt-in, expiring** | opt-in |
| configure | change the node's own allowlists, grants, links | **never over the relay** | never |

Three supporting properties, each of which exists to make a failure loud:

- **The node keeps a local audit log** of every intent it accepted and
  where it came from — a file the human can read without us, next to the
  `submissions.log` that already records his words before anything can
  lose them.
- **Grants are short-lived and named.** A relay compromise then costs the
  window, not the fleet; and revocation is local.
- **The riskiest classes are off unless he turned them on**, per project,
  reusing the vocabulary the `ud-dreamwork-github` plugin already uses for
  exactly this shape of decision: *"Authority lines: none granted, so
  read-only… Grant `comment`, `push`, `open-pr`, or `merge` by naming
  them here."* That idiom is already load-bearing in this repo; the
  platform should not invent a second one.

## The design system across two repos

The tokens are currently duplicated by hand: `watch.py`'s `:root` block,
`dreamhub.py`'s `STYLE` (copied "value for value", with a comment saying
so), and every review artifact's inline `<style>`. A third consumer in
another repo makes hand-copying untenable, and `just audit-styleguide`
exists precisely because "the rule was already recorded; now it is
checkable rather than remembered."

Rec: extract **one token source** in this repo (a small JSON or CSS file),
generated into what each consumer needs, vendored into the platform repo
with a pinned checksum so its CI fails when the vendored copy drifts.
`transitions.md` and `watch-design.md` stay single-source and stay here;
the platform repo's contribution guide points at them rather than
paraphrasing, because a paraphrase is the second description this repo
keeps learning not to write.

Two design questions the shell raises that the current styleguide does not
answer, and they belong to whoever holds `watch-design.md`:

- **What does absence look like?** A node asleep, a relay unreachable, a
  summary from 40 minutes ago, a project whose consent was never given.
  The page's existing doctrine says the answer plainly: it says what it
  does not know, and it never lets a stale state read as live.
- **What is the phone for?** Rec: glance at the fleet, read and answer a
  question, read a dream or an artifact, send `do now`. Not: reading a
  320 KB snapshot, browsing the file tree, or reviewing a diff.

## The hosted runtime (P3), and its unit economics

A hosted dreamer is a sandbox containing a checkout, a coding CLI with the
skill installed, a wake mechanism, and a node. Requirements, in the order
they will bite:

- **Isolation is VM-level, not container-level.** The workload is an agent
  that runs arbitrary code by design.
- **Egress is allowlisted by default** (model APIs, package registries,
  the customer's git host). A box with a coding agent and open egress is a
  crypto miner with extra steps.
- **Spend caps per project, enforced by us**, with the loop told about the
  cap so it can stop cleanly rather than being killed mid-increment.
- **Git access via a GitHub App** with per-repo installation: branch per
  dreamer, no force-push, PRs for review. The same shape this repo's own
  github plugin already models.
- **Secrets: BYOK, envelope-encrypted at rest, injected at boot, never
  logged** — and the honest statement that a runtime which uses a key can
  read it. Competitors' "zero-knowledge" claims about this are mostly
  marketing.

The economics have a specific, unusual shape that must not be discovered
in production:

> **The 4.75-minute heartbeat exists to keep the model's prompt cache
> warm.** Provider caches expire in minutes. So a paused-and-resumed
> dreamer does not just lose time — it loses the cache and pays full input
> on the next tick. Hibernation is therefore a false economy for an
> *active* dreamer and only makes sense for a *paused* project.

Which means the cost floor per active hosted dreamer is roughly "a small
always-on VM plus continuous token spend", and the token half dominates by
an order of magnitude. That is why BYOK is the launch model, and why the
spike that measures a real 24-hour dreamer (below) gates any pricing page.

**The dependency to state loudly:** P3 needs `daemon-mode.md` **stage 2**,
the runtime adapter (herdr | tmux, send-keys, stop hooks), because
something has to start, wake, pause and resume a coding CLI that nobody is
sitting in front of. Stage 2 has never been given a go. P3 cannot start
before it does.

## What is already broken for remote use — measured, not guessed

Every item here is a present defect that is invisible locally because the
writer and the reader are the same machine. They are listed first because
they are cheap, they improve today's LAN mode, and each one is a way the
page could lie about liveness — which is the failure `watch-design.md`
calls disqualifying.

1. **Ages are computed from the browser's clock against the server's
   timestamps.** `ageStr` and `agePair` do `Date.now()/1000 - <server
   epoch>`; `titleLive` does `Date.now() - Date.parse(status.last_tick)`
   and prints `dreaming` or `stalled` from the result. Two machines, two
   clocks, and no correction. A node ten minutes fast reads as dreaming
   over a stopped loop.
   *Fix:* the node reports its own `now` with every response; the client
   carries one offset.
2. **`last_tick` has no stated timezone.** `file-formats.md` does not
   require an offset, the fixture happens to carry one (`+10:00`), and
   both readers — `Date.parse` in the browser, `datetime.fromisoformat` in
   `dreamhub.py` — silently interpret a naive stamp as *their own* local
   time. A phone in another timezone is wrong by hours.
   *Fix:* require offset-aware timestamps in `file-formats.md`, accept
   naive ones as node-local for compatibility, and say which was used.
3. **The page fetches the whole project on every change.** 320,840 bytes
   measured, with `linkable_paths` shipping the entire file tree (221
   entries here) to a page that only needs it to decide which code spans
   are clickable. Over a relay that is both a bandwidth bill and an
   inventory of the customer's repository.
4. **`ANSWER_LOCK` is a `threading.Lock()`** — in-process only. A node and
   a `watch.py` serving the same project, plus the agent itself rewriting
   `questions.md`, are three writers to one prose file with no lock
   between them. The repo's own lesson applies exactly: *durable shared
   state wants a single writer.*
   *Fix:* the node is the single writer for human-write files, watch defers
   to it when one is running, and the check is two processes appending
   concurrently with no answer lost.
5. **`/reviewraw` is same-origin raw HTML** (see *artifact origin*).
6. **`collect()` costs 0.375 s.** One process serving N projects on a
   2-second cadence needs incremental reads and per-resource work, not a
   whole-project sweep per poll.

## Staging

Seven stages. Each is independently useful, each has a gate, and each
names the failure the gate catches. Sizing is given as invasiveness and
dependencies, never as a date.

**S0 — Decide, and measure three numbers. No build.**
D0–D12 answered. Three spikes, each ending in a number rather than an
argument, in the tradition of #115:
  - *Payload*: what a fleet view and one project view actually cost per
    hour on a resource-split protocol, against today's 320 KB baseline.
  - *Hosted cost floor*: one real dreamer, 24 hours, on a small VM —
    tokens, dollars, and how often it actually ticked.
  - *Harness in a box*: can a coding CLI be driven headless in a container
    for 24 hours with a wake mechanism, and what do the vendor's terms say
    about doing it for a third party?
*Gate:* three documented numbers. *Catches:* a pricing page derived from a
model instead of a measurement, and a P3 that is legally impossible.

**S1 — Resources, summary and ETags on `watch.py`.** Inside #124's
server-core seam. Delivers the `/summary.json` already filed for stage 3,
so today's hub gets cheaper and the LAN page gets faster before anything
remote exists. Fixes findings 1, 2 and 6 above.
*Gate:* the hub reads summaries; measured payload down from 320 KB;
concurrent-writer test red then green; ages correct with a deliberately
skewed clock. *Catches:* a protocol designed on a guess about what the
views need.

**S2 — `dreamnode`.** Registry plus N-project reads plus the `/v1` API,
SSE notices, intents with idempotent receipts, per-project confinement,
and the bearer plane (#276). `dreamhub.py`'s page becomes a client of it;
`watch.py` keeps working standalone.
*Gate:* the existing hub guards pass against the node; a request scoped to
project A cannot read project B; the node runs with the relay unreachable
and every local surface is unaffected. *Catches:* the platform quietly
becoming a requirement for the local product.

**S3 — Client extraction and prefix-safe routing.** The watch client
becomes assets that mount under a prefix and a foreign origin — which is
#133 solved properly rather than shimmed, and the three root-absolute
sites (`fetch`, `pushState`, `routeOf`/`isInternal`) fixed at the source.
*Gate:* every existing browser guard passes against the extracted client,
**and** a prefix-mounted deep link renders the right view — the exact
silent failure origin-per-project was chosen to avoid. *Catches:* the
website and the local page becoming two project views.

**S4 — The local product, finished.** Bearer link by QR, PWA, local
notifications, the mesh-VPN document, artifact origin isolation. This is
P1 complete and free, and it is what makes the free tier good enough to
be the thing people recommend.
*Gate:* a phone on a mesh VPN answers a question and the loop folds it.
*Catches:* a paid tier justified by withholding something that should be
free.

**S5 — Relay and website.** New repo. Node link protocol, accounts,
fleet across machines, live proxying, sealed offline queue, push, billing.
P2 ships.
*Gate:* a laptop lid closed mid-answer; the answer arrives when it opens;
one receipt, not two. Relay cannot decrypt its own queue. *Catches:* the
duplicate-write class (#274) reappearing as a distributed bug, which is
where it is hardest to see.

**S6 — Hosted dreamers.** Requires `daemon-mode.md` stage 2. Sandbox
fleet, egress policy, spend caps, GitHub App, BYOK secrets, the honest
security page. P3 ships.
*Gate:* a tenant cannot reach another tenant or the control plane; a spend
cap stops a loop cleanly at a committed boundary. *Catches:* an isolation
story asserted rather than attacked.

Stages S1–S4 are worth doing **even if D0 is answered "no, this stays
mine"**: every one of them fixes something that is wrong for him today,
on his own LAN, on his own phone. That is deliberate. A roadmap whose
early stages only pay off if the business works is a roadmap that has bet
the product on the business.

## Repos, ownership, and the boundary rule

| Repo | Holds | Language / constraints |
|---|---|---|
| `ud-dreamwork` (this) | the skill, the loop, `watch.py`, `dreamnode`, the file formats, `lint.py`, the styleguides, the token source | stdlib Python, no build step, snapshot-deployable |
| `dreamhub-platform` (new) | relay, web app, hosted runner, infrastructure, billing | free choice; a build step is fine |

The boundary rule, restated because it is the whole reason this split is
safe: **the node is the only interpreter.** The platform repo never parses
a loop-written file; it moves opaque JSON, and its CI can prove it.

The corollary about upgrades is the part that gets forgotten: two repos
means version skew becomes normal rather than exceptional, so the API is
versioned, capabilities are advertised, and the website's job is to
degrade legibly against an old node — never to assume the node it is
talking to is the one it was tested against.

## Unknowns, and the cheapest way to close each

| # | Unknown | What it changes | How to close it |
|---|---|---|---|
| U1 | Harness terms for running a vendor's coding CLI on a customer's behalf, in our datacenter | whether P3 is legal as designed; whether BYOK-only is mandatory; which harnesses we can offer | read the terms; ask; design the adapter so no single vendor is load-bearing |
| U2 | Per-dreamer token spend distribution | P3 pricing, credit tiers, whether spend caps are a feature or a necessity | the 24-hour spike, repeated on three project shapes |
| U3 | Whether a suspended sandbox can resume a live CLI session at all | the paused-project cost story; whether "pause" is cheap or just "stop" | spike on the chosen substrate; measure a resume |
| U4 | Change rate under active dreaming (payload × events per hour) | relay cost, mobile data cost, whether SSE notices are enough | instrument a real day locally; it is a counter, not a design |
| U5 | Node process shape: one per machine reading N projects, vs one supervising per-project workers | S2's whole structure; the confinement test; the CPU cost of `collect()`-class reads at N=20 | measure the mtime-walk and per-resource reads at N=1, 5, 20 |
| U6 | Portable change detection without a dependency (stdlib has no inotify) | whether the event stream is truly event-driven or a fast poll wearing a stream's clothes | measure the stat-walk cost; decide if an optional accelerator is worth breaking stdlib-only |
| U7 | Whether the relay should cache summaries at all in v1 | the fleet's offline usefulness against the smallest honest privacy posture | product call (D5), not a measurement |
| U8 | Multi-device queued intents when the node is offline and sealed | whether another device can show pending text at all | design spike on TOFU key pinning; the fallback is "queued, text on the sending device" |
| U9 | Identity provider longevity (`shoo.dev` is self-described early WIP) | login implementation; account recovery; billing linkage | own the account record; treat the broker as swappable (D6) |
| U10 | Slug and identity stability across machines | every link, bookmark and push notification that names a project | node-scoped slugs, assigned once, never recomputed — the rule the hub already learned |
| U11 | Support and compatibility obligations once users are not Max | error copy, migration policy, whether "unsupported" is ever an answer | D0 |
| U12 | Brand, domain, and whether the public name is dreamwork/dreamhub | nothing technical; everything about the website | his call |

## Decisions for the human

Each has a recommendation. None is a build authorization.

- **D0 — Is "users who are not Max" a stated goal?** *Rec: yes, from S5
  onward, folded into DREAMWORK.md when S5 is authorized and not before —
  so S1–S4 stay honest local improvements.*
- **D1 — The seam: node API (option 2), proxy-over-watch (option 1), or
  rewrite (option 3)?** *Rec: option 2.*
- **D2 — May the platform repo be non-Python with a build step, while the
  node stays stdlib and build-free?** *Rec: yes. The constraint exists to
  keep the thing that runs on his machine simple, not to bind a website.*
- **D3 — One project view (extract the watch client, mount it in the
  website shell) or two?** *Rec: one. Two diverge on the first
  fix applied to only one of them.*
- **D4 — Authority defaults over the relay** (read/respond/steer allowed;
  lifecycle and runtime denied until granted per project; configure never).
  *Rec: as tabled.*
- **D5 — Does the relay cache project summaries so the fleet works while
  a machine is asleep?** *Rec: not in v1; opt-in per project afterwards,
  with the page always saying how old a cached row is.*
- **D6 — Identity: own the account record behind a swappable broker
  (shoo.dev acceptable as the front door), or adopt a full auth vendor?*
  *Rec: own the record; verified email alongside the broker subject.*
- **D7 — LAN encryption story:** mesh VPN documented as the path, plaintext
  trusted-LAN as the explicit fallback, service-issued LAN certificates
  filed as a paid-tier benefit. *Rec: as tabled.*
- **D8 — Tunnel: own the link protocol, or embed an existing reverse
  tunnel?** *Rec: own it, kept small — authorization is the product.*
- **D9 — P3 launch model: BYOK only, or bundled credits?** *Rec: BYOK
  only until U2 is measured.*
- **D10 — Pricing shape.** *Rec: P2 per account with a node allowance
  (bytes are the only marginal cost); P3 per running dreamer, plus their
  own model bill. No metered relay billing at launch — it punishes exactly
  the engaged users.*
- **D11 — Sequencing.** *Rec: S1–S4 regardless (they fix present defects),
  then S5, then S6 only after U1 and U2 are closed.*
- **D12 — Does anything in S1–S3 get to touch `watch.py` before #124's
  seams are taken in their planned order?** *Rec: no. S1 and S3 ARE those
  seams; they should be dispatched as #124 work with this plan as their
  motivation, not as a parallel track that re-splits the same file.*

## What this plan is not

- **Not an authorization to build anything**, including S0's spikes.
- **Not a schedule.** Sizing here is invasiveness and dependency, because
  a date on S6 would be a guess wearing a number's clothes.
- **Not a replacement for `daemon-mode.md`'s staging.** Stage 2 (runtime
  adapter) and stage 4 (channels) are still that document's, and this plan
  depends on both rather than restating them.
- **Not a design for the loop.** Nothing here changes how a dreamer works,
  what a tick does, or what lands in `.dreamwork/`. If an increment finds
  itself changing the loop to suit the platform, that is the signal to
  stop.
- **Not a security review.** The threat model for a hosted, multi-tenant,
  code-executing service is its own artifact and its own gate, in the
  shape `.dreamwork/review/lan-bind-threat-model.html` set for a much
  smaller question.

## For the coordinator (this document writes no ledger and no questions)

`.dreamwork/tasks.md` and `.dreamwork/questions.md` have one writer. Draft
entries, to be minted from `Next id: 287` if he wants them:

1. **Platform pre-plan review** — pair `.dreamwork/review/dreamhub-platform.html`
   with a P1 questions entry carrying D0–D12. Blocked on nothing; it is a
   decision request.
2. **Remote-correctness defects, splittable now** — clock offset in the
   client, timezone in `last_tick` (`file-formats.md` + both readers),
   single-writer lock for human-write files, artifact origin isolation.
   Each is small, each improves today's LAN mode, none needs the platform.
3. **`/summary.json` + resource split + ETags** — already filed as a
   stage-3 note in `dreamhub-stage1.md`; this plan promotes it to S1 and
   ties it to #124's server-core seam.
4. **Token single-source extraction** — one token file consumed by
   `watch.py`, `dreamhub.py` and artifacts, with the audit extended.

Suggested questions.md entry title: *"Platform: is dreamhub a product,
and does the node API become the seam?"* — with the artifact attached and
D0/D1 as the two answers that unblock everything else.

--- SUMMARY ---

- **The ask is three products** — free local/LAN/mesh, a paid tunnel with
  identity, and hosted dreamers — and they collapse into one stack if the
  architecture accepts a single claim: **P2 and P3 differ only in who owns
  the machine the node runs on; P1 is the same node with the relay off.**
- **D0 comes first and is not technical:** selling this makes people other
  than Max users of it, which widens DREAMWORK.md's goals. Rec: ratify at
  S5, not now, so the early stages stay honest local improvements.
- **The seam is a node API** (rec): one stdlib `dreamnode` per machine
  owning the registry, the `.dreamwork/` readers and writers, the runtime
  adapter, and a versioned API of resources + change notices + intents
  with receipts. Every surface — local page, hub, website, phone, sandbox
  — is a client of it. Proxy-over-watch is cheaper and caps the product's
  UI at what a single-file renderer can express; a rewrite would move the
  file-format interpreters into a server we host.
- **The boundary rule that makes a two-repo split safe:** *only the node
  knows what a `.dreamwork/` is.* The platform repo moves opaque JSON, can
  be any language, and can prove in CI that it contains no parser.
- **Six present defects are invisible only because writer and reader share
  a machine**, and all six are measured: browser-clock ages, timezone-free
  `last_tick`, a 320,840-byte snapshot per change (with the whole file
  tree in it), an in-process-only write lock with three possible writers,
  same-origin raw-HTML artifacts, and a 0.375 s whole-project read per
  poll. Fixing them improves his LAN mode today and is a prerequisite for
  anything remote.
- **Auth is three planes, not one:** node↔relay (Ed25519 + link code, local
  unlink as kill switch), browser↔relay (own the account record; shoo.dev
  is an acceptable but early front door), browser↔node (bearer token by
  QR, cookie not query string, #233's Host/Origin gates retained). Mesh
  VPN is the documented LAN encryption; service-issued LAN certificates
  are the strongest reason a local-only user would pay.
- **Authority is graded and enforced by the node:** read/respond/steer by
  default, lifecycle and PTY denied until granted per project, node
  configuration never remote — because an authenticated web session is
  remote code execution, and that has to be said in the design and in the
  copy.
- **Privacy claims are limited honestly:** TLS terminates at the relay, so
  E2E against ourselves is theatre while we serve the client. Sealing the
  offline intent queue to the node's key is real and cheap; the sending
  device can show its own words from the IndexedDB record that already
  exists.
- **P3's economics are unusual and must be measured before priced:** the
  heartbeat exists to keep the prompt cache warm, so hibernation is a
  false economy for an active dreamer, and the token bill dominates the
  compute bill by an order of magnitude. BYOK at launch. P3 also depends
  on `daemon-mode.md` **stage 2**, which has never been given a go.
- **Seven stages, S1–S4 of which pay off with no business at all.** S0 is
  three measurements; S1 resources/summary/ETags inside #124's server-core
  seam; S2 the node; S3 client extraction and prefix-safe routing (#133
  solved rather than shimmed); S4 the finished local product; S5 relay and
  website; S6 hosted dreamers.
- **Twelve unknowns are tabled with the cheapest way to close each**, and
  the three that could change the plan's shape are harness terms for
  hosted CLIs (U1), real token spend (U2), and whether a suspended sandbox
  can resume a live session (U3).
