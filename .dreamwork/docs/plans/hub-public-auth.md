# Public Dreamhub authentication — design + research (#275)

> **DESIGN AND RESEARCH ONLY. No implementation.** Public/WAN support stays
> forbidden in this project until a reviewed design is approved by the human.
> This document changes no `.py` file, no bind address, no listen logic, adds no
> dependency, and defines no flag that could be switched on. It is prose plus a
> threat model, written to be ruled on.

Origin: **human** (task #275, via `answers.md` 17:48): *evaluate shoo.dev's
actual primary-source auth/deployment model and the realistic alternatives, then
define, for a public Dreamhub: identity, TLS, session/cookie handling, CSRF,
authorization, secrets management, reverse proxy, and the threat model.* Sibling
task **#276** (LAN bearer token) is the distinct, narrower, non-public design.

---

## 1. What the current thing actually is, and why loopback is the auth model

`dreamhub.py` is a **read-only aggregate** over several dreaming projects on one
machine. `dreamhub-design.md` states its boundary in one line: *"No remote, no
non-localhost bind, no auth — binds `127.0.0.1` by construction."* `watch.py`
inherited the same posture: its docstring and `watch-design.md` say *"Loopback
by default; trusted LAN only by explicit contract,"* and the trusted-LAN mode
landed in #233 / `2026-07-26-01-trusted-lan-bind.md` is **deliberately
unauthenticated** — Host + Origin checks are rebinding/CSRF safeguards, *not*
client authentication.

Loopback is not a default out of inertia; it **is** the authorisation model.
Three load-bearing facts follow from reading the actual code and design records:

1. **The hub is served by data that is fine over localhost and dangerous over a
   link.** `dreamhub-design.md` (§"What the hub depends on") says `/data.json`
   "currently carries the full text of `DREAMWORK.md`, `questions.md` and
   `lessons.md`… fine on a change-triggered fetch over localhost and is exactly
   what stops being fine over a link, which is why a light `/summary.json` is
   noted for stage 3." A public hub inherits this exposure the moment it is
   reachable.

2. **The hub can display the human's typed words and repository contents.**
   Questions, answers, notes (author-tagged, in the human's voice), dream
   transcripts, the task queue, agent ownership, and the `/file` viewer all read
   live from disk. This is the privacy ceiling any public design has to meet.

3. **`watch.py` has six human-authorised write routes** (`/answer`, `/ask`,
   `/comment`, `/command`, `/tint`, `/run-mode`) that append to durable files
   the loop reads back and acts on. `dreamhub.py` writes nothing outside
   `~/.config/dreamwork/hub/` and has no write routes. A public surface that
   proxied writes would be **remote steering of an autonomous coding agent** —
   which is exactly the take-over class task #288 (a subagent killing a live
   service to satisfy an invented premise) already proved is real on this loop.

The #233 threat-model artifact framed the choice honestly: *"Do not bind
non-locally yet. First design identity, session/token lifecycle, TLS or trusted
reverse-proxy boundaries, logout/revocation and secret handling."* This document
is that design.

---

## 2. Threat model — who the actual adversary is

**Assets behind the hub** (what a public exposure puts at risk):

- The human's **typed words**: questions, answers, notes to the dreamer, draft
  composer text. These are the most sensitive category; they include unfinished
  thinking and private direction.
- **Repository contents** reachable via `/file`, including private repos and
  dotfiles, not just the public skill repo.
- The **task queue, agent ownership, dream transcripts, and status** — enough to
  reconstruct what the loop is working on, where it is blocked, and what it has
  tried.
- **Write authority over the loop** if any write route is exposed: command
  injection becomes the ability to make an autonomous coding agent do work on
  the attacker's behalf, up to commit / push / deploy (the same authority
  boundary #288 surfaced).

**Adversaries, in order of how likely they actually appear:**

1. **Drive-by internet scanners and credential-stuffers** (Shodan, Censys, bot
   nets). Any public HTTP service is probed within minutes of appearing in a
   scan. They are noise, but they are the reason "nobody knows the URL" is not a
   control.
2. **Cross-site attackers (CSRF / XSS) driving the operator's logged-in
   browser.** A malicious or compromised site the operator visits can try to
   POST to the hub from their browser. CSRF on a write route is the high-value
   target; read routes behind auth still leak via XS-Read if SameSite is wrong.
3. **Targeted attackers who know the operator or the project.** Motive splits:
   - *Read* of private repo contents, the human's answers/notes, or the agent's
     working state.
   - *Write/steer* — injecting commands or answers to redirect the loop. This is
     the take-over case and the one a design must refuse to enable.
4. **Token/session theft** via XSS, log leakage, or a stolen device. The session
   is the live authority; its lifetime and revocation matter.
5. **The identity provider itself** (whichever is chosen). A compromised or
   rogue IdP that can mint valid assertions for attacker-controlled accounts is
   a trust root until an operator-managed allowlist sits in front of it.

**Trust roots the design must name explicitly:** the TLS certificate authority
chain; the IdP's signing key (for shoo, its ES256/JWKS key); and an
operator-managed **authorization** list (which identities may do what) — because
authentication alone ("this is a valid Google account") is not authorisation
("this is *the operator's* Google account"). The honest framing: identity is
*"a Google account the operator has pre-allowlisted,"* never *"any account the
IdP will sign for."*

---

## 3. shoo.dev — what its primary sources actually say (with citations)

I read shoo's own documentation rather than summarising second-hand. Cited
below; the load-bearing claims are quoted from those pages.

**What shoo is.** *"Shoo is a minimal auth broker for Google sign-in"* and
*"Shoo handles Google OAuth + PKCE and gives your app a domain-scoped identity
(`pairwise_sub`) and a signed `id_token`. No client signup. No unnecessary
scopes. Just identity."*
— `https://docs.shoo.dev/docs` (Introduction)

**The flow** (`https://docs.shoo.dev/docs/how-it-works`). PKCE OAuth, browser-side:
1. App calls `startSignIn()`, generates a PKCE bundle, stores the verifier in
   `sessionStorage`.
2. Browser redirects to `https://shoo.dev/authorize?code_challenge=…&redirect_uri=…&state=…`.
3. Shoo redirects to Google; the user authenticates with Google; Google
   callbacks to shoo with a code.
4. Shoo exchanges the Google code, derives `pairwise_sub`, signs an ES256
   `id_token`, redirects `?code=shoo_code&state=…` back to the app.
5. App `POST /token`s the code + `code_verifier`; shoo verifies PKCE and returns
   `{ id_token, pairwise_sub }`.

**Identity model** (how-it-works):
- `pairwise_sub = HMAC-SHA256(server_secret, google_sub + client_id)` — domain-
  scoped, stable per (Google account, app origin), not reversible to the Google
  `sub`, format `ps_{base64url}`. *"No cross-app tracking."*
- `client_id = "origin:" + new URL(redirect_uri).origin` — **auto-derived from
  the redirect origin, no registration step.** The first `/authorize` from a new
  origin auto-registers the client.

**Tokens** (how-it-works, and `https://docs.shoo.dev/docs/server-verification`):
- ES256 (ECDSA, P-256). JWT header carries `kid`; public keys at
  `https://shoo.dev/.well-known/jwks.json`; OIDC discovery at
  `https://shoo.dev/.well-known/openid-configuration`. Issuer `https://shoo.dev`;
  audience `origin:{your_origin}`.
- Always-present claims: `iss`, `aud`, `sub` (== `pairwise_sub`), `pairwise_sub`,
  `iat`, `exp`, `jti`. Optional PII claims (only when requested *and* consented):
  `email`, `email_verified`, `pii_sub`, `name`, `picture`.

**Server-side verification is mandatory, not optional.** From server-verification:
*"The browser auth flow gives the user a signed `id_token`, but the browser is
an untrusted environment… **Never trust unverified client-side claims for
authorization decisions.** Always verify the `id_token` signature, issuer,
audience, and expiration on your server before granting access."* The server
must check `iss == https://shoo.dev`, `aud == origin:{your_origin}`, `exp`,
a valid ES256 signature against JWKS, and that `pairwise_sub` is present.

**Server endpoints** (how-it-works): `GET /authorize`, `POST /token`
(CORS-enabled), `POST /session/check` (bearer-token revocation/status check:
`200 active` vs `401 login_required` with `reason revoked|expired|invalid_token`),
`GET /.well-known/jwks.json`, `GET /.well-known/openid-configuration`. No shoo
SDK is required on the server — standard JWKS verification with any JWT library.

**What shoo itself sees** (`https://shoo.dev/privacy`, last updated 2026-02-14):
the Google `sub`; optional profile data only when an app requests it and the
user consents; client/consent records; security/operations data (nonces, codes,
replay identifiers, rate-limit counters, IP for abuse prevention); a signed
HTTP-only `shoo_session` cookie. Operator entity is **ping.gg**
(`support@ping.gg`; issues at `github.com/pingdotgg/shoo/issues`).

**Maturity — read this before depending on it.** Every shoo page carries a
banner: *"SUPER EARLY WIP — USE AT YOUR OWN RISK."* The landing page
(`https://shoo.dev/`) links the GitHub repository as `github.com/pingdotgg/shoo`
with a **"COMING SOON"** badge. I fetched that URL directly: it returns
**HTTP 404 "Page not found"** as of 2026-07-27. So the landing's "Open source"
claim is **not yet verifiable**; shoo's server implementation cannot currently be
audited by reading it. The "Free forever. No sign up." pitch and the privacy
page exist, but there is no public source to confirm the PKCE/pairwise/JWKS
behaviour against, no uptime or SLA published, and no security audit referenced.

**Gaps I could not close from primary sources (stated, not papered over):**

- I could not read shoo's source — the repository is not public (404), and the
  GitHub REST API rate-limited the unauthenticated metadata call. So the
  behaviour described above is taken from shoo's own docs, not from code.
- I did not find any shoo-published threat model, security review, or
  incident-disclosure process. The privacy page is the only security-adjacent
  primary source.
- I did not verify shoo's uptime, its own authentication posture for the `/me`
  account-management surface, or its key-rotation cadence beyond the docs'
  claim that rotation is automatic via `kid` + JWKS.
- Shoo is **Google-only** at present (every primary page says so). There is no
  email/password fallback, no other IdP. If the operator cannot or will not use
  a Google account, shoo does not work.

---

## 4. Three hard constraints that shape any design

These are properties of *this* hub, and each one rules something out:

**C1 — Stdlib-only, single-file, no build step.** Both `dreamhub.py` and
`watch.py` are pure-stdlib Python (`watch-design.md`: *"Stdlib only,
self-contained; no dependencies, no build step"*). This is a product constraint,
not a preference. It collides head-on with shoo's ES256 `id_token`: **Python's
standard library cannot verify an ES256 (or RS256) signature.** I confirmed this
directly: `hashlib` and `hmac` are present but do only symmetric primitives;
`ssl` exposes no general-purpose ECDSA-verify on arbitrary data; the only
verifier installed here is `cryptography` 49.0.0, which is **third-party**, not
stdlib. The options for an in-process verifier are all bad:
- depend on `cryptography` / `PyJWT` / `jose` — **breaks stdlib-only**;
- shell out to `openssl dgst -verify` — adds a binary dependency and a parsing
  surface, and is the kind of subprocess call this repo's confinement rules
  (`resolve_confined`, the #288 authority incident) exist to discourage;
- hand-roll P-256 ECDSA in ~200 lines — a known security footgun, unfitting for
  the exact control plane where a verify bug means remote steering of an
  autonomous agent.
This tension is the single most load-bearing finding for the recommendation.

**C2 — `/data.json` leaks full documents today.** The hub's own design record
says so (§1 above). Any public path must ship a **redacted `/summary.json`** (or
equivalent) before the existing `/data.json` is exposed, or it must not expose
the existing surface at all.

**C3 — Writes are steering.** Publicly exposing any of `watch.py`'s six write
routes is exposing remote control of an autonomous coding agent. A read-only
public surface is a defensible increment; a read+write public surface is a
different, larger, and much more dangerous thing, and should not be assumed.

---

## 5. Options, with real trade-offs

Each option is judged against: preserves stdlib-only hub? (C1) · handles TLS ·
handles identity · handles authorisation · maturity risk · operational cost to
the operator.

### A. Shoo integrated directly into the hub
The hub gains a `/auth/shoo` flow (redirect to `shoo.dev/authorize`, callback,
server-side ES256 verification via JWKS), sets a session cookie, and gates
routes on it. Identity = a shoo `pairwise_sub` the operator allowlists.

- **C1:** ✗ — breaks stdlib-only (ES256 verify needs `cryptography`/`PyJWT`/
  `jose` or a footgun hand-roll). This is the deciding strike against A *as the
  sole boundary*, in this repo.
- **TLS:** the hub must terminate HTTPS at a stable public origin (the redirect
  origin is the shoo `client_id`). Shoo is HTTPS-only by construction.
- **Identity/authorisation:** Google-only; the operator must use a Google
  account and ship an allowlist of `pairwise_sub` values. Shoo is the trust
  root, plus the operator allowlist on top.
- **Maturity:** ✗ — "SUPER EARLY WIP", repo not public (404), unauditable, one
  operator entity (ping.gg), no published security review. Depending on it as
  the *sole* auth boundary for an agent control plane is more trust
  concentration than this surface warrants.
- **Cost:** medium — PKCE plumbing in the hub, a verifier dependency, a session
  store, a JWKS cache, a pairwise allowlist file.
- **Verdict:** the right *identity primitive*, the wrong *sole boundary*, today.

### B. Reverse-proxy auth boundary; the hub stays loopback-only ★ recommended shape
Put a TLS-terminating, authenticating reverse proxy in front. The hub keeps
binding `127.0.0.1`, accepts only the proxy's signed header, and **gains zero
auth code.** This preserves C1 entirely. Three concrete front doors:

- **B1 — Cloudflare Access (Zero Trust).** CF fronts the origin; identity is
  enforced at the edge (Google, GitHub, email OTP, SAML, or a custom OIDC IdP —
  which *could* be shoo later). The origin only accepts a request carrying CF's
  signed `Cf-Access-Jwt-Assertion` JWT, verified against CF's public keys. The
  hub is **unreachable** except through CF Access. Free for small teams. TLS is
  automatic.
- **B2 — Tailscale Funnel + ACL.** Funnel exposes the hub over public HTTPS
  (TLS auto-managed); Tailscale's auth/ACL decides who reaches it. The operator
  (and anyone they share with) authenticates to Tailscale on their device. The
  hub sees only the tailnet identity. Closest to "loopback feel, anywhere."
- **B3 — Caddy (or nginx + oauth2-proxy).** A single binary on the host, auto
  Let's Encrypt, `forward_auth` to an OIDC IdP (Google directly, GitHub, or
  self-hosted Logto/Zitadel/Ory/Keycloak). More moving parts than B1/B2, fully
  under the operator's control, no SaaS dependency.

  For all three, **the hub's only contract with the outside world is a trusted
  forwarded header** (CF's JWT, Tailscale's identity headers, or oauth2-proxy's
  `X-Forwarded-User`). Header-spoofing is the failure mode, so the hub must bind
  loopback and the proxy must overwrite (not trust client-supplied) auth
  headers. This is the one place a bug re-opens the whole surface, and the
  reason the hub must remain loopback-only even behind a proxy.

- **C1:** ✓ — no auth code, no verifier, no dependency in the hub. The hub
  becomes "read-only, loopback, header-gated."
- **TLS:** solved by the proxy (CF/Tailscale/Caddy all auto-manage certs).
- **Identity/authorisation:** solved at the edge; the hub maps a forwarded
  identity to "read allowed" / "denied." The operator allowlist lives in the
  proxy's policy (CF Access policy, Tailscale ACL, oauth2-proxy config).
- **Maturity:** ✓ — CF Access, Tailscale and Caddy are mature, audited, and
  widely deployed; none is a one-person WIP.
- **Cost:** low-to-medium — one extra component (the proxy) the operator runs
  or signs up to. Decoupled from the hub's release cycle.
- **Verdict:** best preserves the architecture and minimises trust
  concentration. Shoo can still be the *IdP behind* the proxy later (CF Access
  supports custom OIDC, and shoo publishes OIDC discovery), without the hub
  caring.

### C. Private overlay — not actually public
Tailscale/WireGuard without Funnel: the operator's devices join a tailnet; the
hub stays loopback or tailnet-only; no public internet exposure at all. TLS and
app-layer auth are unnecessary because the network is the boundary.

- Best safety profile; zero public attack surface; the operator's phone is a
  first-class client (Tailscale mobile apps). BUT it requires Tailscale/WG on
  every client, does not work from a borrowed browser, and is **not "public"** —
  it is the answer to a different question. Worth naming because the operator
  may actually want this and not realise it is distinct from #275. If the
  legitimate use is always "me, on my devices, away from my desk," C is strictly
  safer than B and should be chosen instead.

### D. SSH tunnel / bastion
The operator (and trusted others) reach the hub via `ssh -L` to a bastion, or a
browser-over-SSH setup. Already used for remote projects (`dreamhub-design.md`
notes `ssh -L` gives a local port per remote project).

- Familiar to the operator; no new public surface; strong transport. But SSH
  clients are awkward on mobile and impossible in a borrowed browser, so it
  serves a narrower use than B/C. Reasonable as a fallback, not as the design.

### Explicitly rejected
- **E1 — Bearer token in URL/header over public HTTPS, as the sole boundary**
  (the #276 LAN design extended to WAN). Tokens leak into logs, referrers and
  browser history; revocation is manual; and without TLS (which itself needs a
  cert) it is a non-starter. #276 is the right scope for bearer tokens; #275 is
  not.
- **E2 — mTLS client certificates.** Strongest transport auth, but provisioning
  client certs on phones and tablets is painful enough to make the surface
  unusable for the "check from my phone" use case that motivates public access.
- **E3 — Hand-rolled P-256 ECDSA verifier in the hub.** Named as a trap: it
  would *technically* let shoo-direct keep stdlib-only, at the cost of a
  security-critical primitive written by an agent. No.
- **E4 — "Any valid IdP token = authorised."** Authentication ≠ authorisation.
  Any option that skips the operator allowlist (of `pairwise_sub`, email, or
  tailnet identity) lets the IdP decide who runs this loop. Rejected for all
  options.

---

## 6. Per-axis definition for the recommended shape (B)

Stated for the recommended reverse-proxy boundary, so the human has something
concrete to rule on. (A shoo-direct variant would differ on identity, TLS, and
session as flagged; C/D remove most rows.)

| Axis | Recommended design |
|---|---|
| **Identity** | Decided at the proxy. CF Access / Tailscale / oauth2-proxy authenticates the operator (Google/GitHub/email OTP/tailnet). The hub never sees a password. The operator maintains a **fixed allowlist** of one or two identities who may read. |
| **TLS** | Terminated by the proxy (CF edge cert, Tailscale Funnel cert, or Caddy auto Let's Encrypt). The hub speaks plain HTTP on loopback to the proxy only. No TLS in the hub. |
| **Session / cookie** | The proxy issues and owns the session (CF Access sets `CF_Authorization` cookie; Tailscale uses its own; oauth2-proxy sets its own). The hub sees only the **trusted forwarded identity header** per request — it is stateless about sessions. Logout happens at the proxy. |
| **CSRF** | The hub keeps the existing Host + same-origin Origin check on POST (the #233 mechanism). With the public surface read-only by default (see Authorization), the CSRF surface shrinks to whatever writes are later exposed; those should additionally require a custom header or double-submit token if they ever ship. |
| **Authorization** | **Read-only publicly; writes stay loopback/trusted-LAN-only** (C3). The hub maps forwarded identity → `{read allowed, denied}`. No public write route ships in this design. Separately, the operator authorisation list (who may read) lives in the proxy's policy, not in hub code. |
| **Secrets** | Minimal. The hub holds no IdP secrets (the proxy does). The operator allowlist is a public, non-sensitive list of identifiers (pairwise subs / emails / tailnet identities), not a secret. TLS private keys live with the proxy. If shoo is later used as the IdP, the shoo-verifier keys are JWKS-fetched (public), and no shared secret crosses into the hub. |
| **Reverse proxy** | The hub binds `127.0.0.1` only; the proxy is the sole listener on the public interface. The proxy **overwrites** (never trusts client-supplied) the identity header. This is the one invariant a bug breaks; keep the hub loopback-only even behind the proxy. |
| **Data exposure** | Ship a **redacted `/summary.json`** (or restrict `/data.json`) before the public serve is enabled, per C2. The full-document `/data.json` must not be the public surface. |
| **Threat-model coverage** | Drive-by scanners: blocked (origin unreachable without the proxy). CSRF: existing Host+Origin + read-only surface. Token theft: proxy-owned session + operator-chosen TTL + revocation at the IdP. Targeted read: operator allowlist + redacted data. Targeted write: refused by design (no public writes). IdP compromise: operator allowlist still gates. |

---

## 7. Recommendation

**Use a reverse-proxy auth boundary (option B; Cloudflare Access or Tailscale
Funnel as the first concrete front doors), keep the hub loopback-only and
header-gated, expose a redacted `/summary.json` instead of `/data.json`, and
serve no write route publicly.** Treat shoo as a candidate identity provider
*behind* that proxy once its repository is public and auditable and the
stdlib-ECDSA tension is resolved one way or another — not as the sole boundary
today.

In two sentences (for the coordinator's report): a public Dreamhub should be a
read-only, loopback-bound hub fronted by a mature authenticating reverse proxy
that owns TLS, identity and the session, with the operator's authorisation
allowlist at the proxy; shoo.dev is an interesting Google-only identity
primitive but is too early-stage, too trust-concentrating, and (because the
stdlib-only hub cannot verify its ES256 tokens in-process) the wrong sole
boundary for an agent control plane.

---

## 8. Open questions for the human (verbatim, for the coordinator to file)

These are the decisions that gate any further work, in priority order:

1. **Is the real goal public access (any browser, anywhere, with auth) or
   private remote access (your devices only)?** If the latter, Tailscale/WireGuard
   (option C) is strictly safer and "public" is not needed. This single answer
   rewrites the rest of the design.
2. **Is adding one reverse-proxy component (Cloudflare Access, Tailscale Funnel,
   or Caddy) acceptable, given it keeps the hub itself stdlib-only and adds no
   auth code?** This is the C1 question. If the hub itself must do auth, the
   design changes substantially and shoo-direct (option A) or a hosted IdP
   (Clerk/Auth0/etc.) comes back into scope.
3. **Public read-only, or public read+write?** This design recommends
   read-only publicly (writes stay loopback/trusted-LAN). Confirm, or name which
   write routes you would want exposed and under what extra guard.
4. **Identity provider choice.** Shoo is Google-only and pre-release; CF Access
   / Tailscale / oauth2-proxy support Google, GitHub, email OTP, SAML, etc.
   Which IdP(s) do you want, and are you willing to depend on a Google account
   for this?
5. **May a redacted `/summary.json` be designed and shipped** (separate task)
   **before any public serve is enabled?** The current `/data.json` leaks full
   `DREAMWORK.md` / `questions.md` / `lessons.md` text and is unfit for public
   exposure as-is.
6. **Who, besides you, should ever reach this hub?** The answer defines the
   authorisation allowlist and whether multi-identity is worth any complexity.

---

## 9. What I am NOT confident about (stated plainly)

- **CF Access free-tier specifics.** I did not re-verify Cloudflare's current
  plan limits for Zero Trust / Access in detail; the design assumes the small-
  team free tier covers a single-operator hub. Confirm against CF's current
  pricing before committing to B1.
- **Caddy `forward_auth` exact current semantics.** I know the documented shape;
  a real implementation would verify against current Caddy docs and test the
  header-overwrite invariant. This is a design doc, so I cite the pattern and
  flag the verification rather than asserting it.
- **Shoo as a custom OIDC IdP behind CF Access.** Shoo publishes OIDC discovery,
  so it should be wireable as a custom OIDC provider, but I did **not** verify
  the integration end-to-end (shoo's repo is not public to test against, and CF
  Access's custom-OIDC support has its own requirements). Treat as plausible,
  not proven.
- **The hand-rolled P-256 verifier option (E3).** I am confident it is a trap,
  not a plan, but flag that I have not enumerated every stdlib crypto path; if a
  future Python release exposes a verifiable ECDSA primitive, this trade-off
  changes.
- **Whether the operator already has/uses a Google account.** Central to whether
  shoo (or Google-via-CF-Access) is even viable; I have no primary source for
  the operator's IdP preferences — that is question 4.

---

## 10. Out of scope

- Any change to `dreamhub.py`, `watch.py`, `justfile`, `dev/capture/`,
  `transitions.md`, the design records, `tasks.md`, `questions.md`,
  `answers.md`, or `status.json`. None made; none implied.
- Implementation, bind-address changes, dependency addition, or any flag that
  could enable public serving. All forbidden until a reviewed design is
  approved.
- The #276 LAN bearer-token design (narrower, non-public, separate).
- A migration: no file format or persisted shape changes here, so none is owed.

## Primary sources actually reached (URLs)

- `https://shoo.dev/` — landing ("Auth in 2 LOC", "SUPER EARLY WIP", GitHub "COMING SOON")
- `https://docs.shoo.dev/docs` — Introduction ("minimal auth broker for Google sign-in")
- `https://docs.shoo.dev/docs/how-it-works` — PKCE flow, `pairwise_sub`, auto-`client_id`, ES256/JWKS, endpoints
- `https://docs.shoo.dev/docs/server-verification` — mandatory server-side JWT verification
- `https://shoo.dev/privacy` — data shoo sees; operator = ping.gg
- `https://github.com/pingdotgg/shoo` — **HTTP 404** (repo not public as of 2026-07-27, matching "COMING SOON")

## Primary sources I could NOT reach (stated, not filled with generalities)

- `github.com/pingdotgg/shoo` source code (404) — shoo's server implementation is
  unauditable from primary sources today. The behaviour above is from shoo's own
  docs, not from readable code.
- Any shoo-published security review, threat model, or uptime/SLA — none found.
- GitHub's repo metadata API — rate-limited (HTTP 403) on the unauthenticated
  call; the 404 on the HTML page is the primary-source confirmation the repo is
  not public.
- The operator's IdP preference (Google account? GitHub?) — no primary source;
  that is open question 4.

---

## 11. Supersedence, and the three sub-decisions still open (Q3 / Q5 / Q6)

> This section was added by the `hubauth` research lane (brief #275, 2026-07-29).
> It reconciles this plan with `#360`'s ssh-rooted design and answers the three
> sub-decisions the human has left open since 2026-07-25, **with measurement
> rather than opinion**. §§1–10 above keep their value unchanged: the threat
> model, the asset inventory, the shoo.dev primary-source analysis, the TLS/proxy
> analysis and the `/data.json`-leak finding (C2) are all inherited by `#360`
> rather than re-derived there.

### 11.0 What `#360` superseded, and what it did not

`#360` (`hub-ssh-auth.md`, `4d4e705`) **supersedes this plan's identity
recommendation** — Cloudflare Access / Tailscale Funnel as the authenticating
boundary — because the human refused a self-hosted tool whose auth depends on a
third party's control plane (`#360`, watch 2026-07-28 01:39). What survives from
this plan, and what `#360` itself says it inherits:

- the **threat model and asset inventory** (§2);
- the **TLS / reverse-proxy analysis** (§5 option B) — re-pointed at a *local
  Caddy* rather than Cloudflare/Tailscale, but the boundary shape holds;
- the **`/data.json`-leak finding (C2)** — `#360`'s option 2 carries a redacted
  `/summary.json` as a hard prerequisite, citing this plan as its source;
- the **stdlib-only constraint (C1)** and the **writes-are-steering constraint
  (C3)** — both unchanged.

So the four candidate boundaries for a *self-hosted* hub are now, in cost order:
the **ssh tunnel** (`#360` option 1, zero code, works today), the **ssh-issued
session key** (`#360` option 2, the one worth building, supersedes `#276`'s
static bearer token), **user/password** (`#360` option 3, fallback), and
**SQRL** (`#360` option 4, an honest "no"). A hosted IdP as the *sole* boundary
is out — it is the redirect this task exists to make. **Read §§1–4 of this plan
and all of `hub-ssh-auth.md` before the three answers below; they are the
ground, not decoration.**

### 11.1 Q3 — read-only, or read+write, publicly? → **read-only publicly**

Measured against the code, not argued from preference. Two facts decide it.

**(a) The hub and the watch dashboard are different surfaces with different
blast radii.** `dreamhub.py` is a **read-only aggregate**: its handler serves
only `GET /hub.json`, `GET /rows` and `GET /` (`dreamhub.py:831` `do_GET`), it
writes nothing outside `~/.config/dreamwork/hub/`, and it has **no `do_POST`**.
Exposing the *hub* behind auth carries only the data-leak risk this plan's §2
inventories. `watch.py` is the other surface: it carries six human-authorised
write routes (`WRITE_ROUTE_HANDLERS`, dispatched from `do_POST` at
`watch.py:11651`) — `/answer`, `/ask`, `/comment`, `/command`, `/tint`,
`/run-mode` — and every one of them appends to a durable file the loop reads
back and acts on. **`/command` with `do-now` is remote steering of an
autonomous coding agent**, and `/run-mode` changes how hard it runs.

**(b) A public write route is the `#288` incident handed to the internet.**
`#288` proved a same-UID process can kill a live protected service to satisfy
an invented premise; the human's own `#358` framing names the boundary that
matters: the body *"can only kill itself"*, never the head. A public
`/command` makes the credential the head's equal — a stolen session cookie
becomes the ability to point the agent at arbitrary work, up to commit / push /
deploy, through exactly the authority surface `#288` surfaced. Read-only
publicly bounds the worst case of a compromised credential to **data leak**;
read+write publicly bounds it to **agent takeover**. That is not a trade-off a
v1 should make.

**Answer: read-only publicly.** The public/LAN surface serves reads only;
writes stay loopback / trusted-LAN / ssh-tunnel (the transports where the
operator's device is already authenticated). This is C3 restated as a ruling,
and it is the safe default regardless of which identity option (`#360` 1–3)
lands. A future read+write public surface is a separate, larger design that
would need its own per-route authorisation, a CSRF story beyond the existing
Host+Origin check, and a human ruling — none of which this task authorises.

### 11.2 Q5 — may a redacted `/summary.json` ship before any public serve? → **yes, and it is the blocker**

This plan's C2 says `/data.json` leaks full documents. **Verified against the
live `collect()` (`watch.py:10756`)**, the payload is worse than "full
documents": it is the loop's whole operating state, including the operator's
unfinished thinking. The fields, classified by sensitivity:

- **Most sensitive — the operator's words and private direction.**
  `files.DREAMWORK.md` (full project goals/config), `files.questions.md`
  (**the operator's typed questions, answers and notes, in full** — unfinished
  thinking, the ceiling of what a public design must protect), `files.lessons.md`
  (full lessons file), `questions_open` / `answered_entries` (parsed question
  bodies), `answers_open` / `answers_answered` (the `/answers` channel — his
  questions *to* the loop), `pending_handoffs` (landed-work records), `dreams` /
  `dreams_archive` (agent working-state transcripts).
- **Operational state — reveals pace, volume and where the loop is blocked.**
  `status` (full `status.json`: queue, current tasks, agent ownership, deployed
  pid), `git` (recent commits), `burndown` (historical task-count time series),
  `deployed` (serving revision).
- **Counts / health / metadata — safe to expose.** `target`, `generated`,
  `open_questions` (a count), `questions_health` / `answers_health`,
  `linkable_paths`, `tint`, `run_mode`, `posture`, `plugin_commands`,
  `skill_identity`, `files.skill-version`.
- **Reviews** — the design artifacts. Arguably meant-to-be-shared proposals,
  but each carries the operator's decision context, so they are **not** safe by
  default; a `/summary.json` should link them rather than inline them.

**Answer: yes.** A redacted `/summary.json` keeps the counts, health, and
operational metadata and **drops every full-text and parsed-entry field** —
no `files.*` document bodies, no `questions_open`/`answered_entries`, no
`answers_*`, no `pending_handoffs`, no `dreams*`. It is the blocker for any
public or trusted-LAN exposure whatever else is chosen: the existing
`/data.json` is unfit to expose, and a session cookie (or any credential)
should not gate a route that then leaks `DREAMWORK.md` / `questions.md` /
`lessons.md` in full. `#360`'s option 2 already carries this as a hard
prerequisite; Q5 makes it its own shippable task, decoupled from the auth
choice. **Rec: yes, design and ship `/summary.json` as its own task before any
non-loopback serve.**

### 11.3 Q6 — who besides you should ever reach this hub? → **you only, for v1**

Measured against what the surface exposes and what multi-identity costs.

- **The data is the operator's private thinking.** §11.2 shows the public
  surface (even redacted) carries the loop's working state, and any
  non-redacted path carries his questions, answers and dream transcripts.
  Adding a second identity is not a mechanical act — it is a decision to share
  that, which is the operator's, not the loop's.
- **`#360`'s option 2 makes a second identity mechanically cheap** (one
  `ssh … issue-session` per device, per-device revocable), so the *allowlist*
  does not need to be designed up front for more than one entry. v1
  single-operator keeps it trivially "the operator's session" and avoids both
  the multi-identity code and the "whose data is this" question entirely.
- **The cost of guessing wrong is low in one direction only.** Starting at
  "you only" and widening later is one issue-command; starting at "anyone
  authed by the IdP" and narrowing later is a revocation and a data-leak
  already happened. The safe default is the narrow one.

**Answer: you only, for v1.** The authorisation list is one identity (or one
ssh key / one session cookie). No multi-identity code, no role model, no shared
surface — and the path to a second person is documented (`#360` option 2 +
one issue-session) rather than designed speculatively.

### 11.4 The IGC, against the goals that actually discriminate

Per the brief: binary goals, `✘` with the decisive error written out, against
*no inbound port on his machine* · *no third-party IdP holding his data* ·
*works on a phone away from the LAN* · *a compromised credential does not grant
write access to the loop*. The candidate boundaries for a self-hosted hub:

| boundary | no inbound port | no 3rd-party IdP | phone off-LAN | stolen cred ≠ write |
|---|---|---|---|---|
| **ssh tunnel** (`#360` opt 1) | ✔ | ✔ | ✘ phone needs an ssh app + a reachable sshd off-LAN (Tailscale/WG or a jump host) | ✔ hub holds no credential |
| **ssh session key** (`#360` opt 2) | ✘ the `#233` LAN bind is an inbound port on his machine | ✔ ssh is the root, Caddy is local | ✔ phone is just a browser on the LAN | ✔ read-only publicly (Q3) |
| **user/password** (`#360` opt 3) | ✘ LAN bind | ✔ | ✔ | ✘ a sniffed/reused password over HTTP-on-LAN reaches the write routes unless TLS sits in front — and TLS fronting it makes this redundant |
| **hosted IdP** (CF Access / Tailscale Funnel) | ✘ | ✘ the IdP's control plane holds identity — the redirect `#360` exists to make | ✔ | ✔ (read-only) but fails the second goal |
| **SQRL** (`#360` opt 4) | ✘ | ✔ | ✘ no alive client ecosystem | ✔ but moot — Ed25519 not in stdlib |

**What survives:** nothing passes all four. The ssh **tunnel** passes three and
fails only the phone-off-LAN convenience (and even there, a Tailscale mesh to
the sshd recovers it without a public port). The **ssh session key** behind a
local Caddy passes three and fails only "no inbound port" — and that port is a
loopback-or-LAN bind the operator already chose to open (`#233`), fronted by a
local proxy, not a public WAN listener. **Those two are the design.** User/pw
fails the credential goal standalone; the hosted IdP is the superseded one;
SQRL is dead. So the recommendation is not "one boundary" but an **order**:
document the tunnel now (`#360` §6, zero code), and if the phone-without-ssh
case is real, build the ssh session key behind a local Caddy, read-only
publicly, redacted `/summary.json` first, operator-only allowlist. The three
sub-decisions above are the ruling that gates it.
