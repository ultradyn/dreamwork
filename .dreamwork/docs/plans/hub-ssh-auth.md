# Self-hosted Dreamhub auth built on ssh — design + documentation (#360)

> **DESIGN AND DOCUMENTATION ONLY. No implementation.** Public/WAN serving of
> Dreamhub stays forbidden until a reviewed design is approved by the human.
> This document changes no `.py` file, no bind address, no listen logic, adds no
> dependency, opens no tunnel, and defines no flag that could be switched on. It
> is prose plus recipes plus a recommendation, written to be ruled on. The
> ssh-tunnel recipe in §6 is documentation of what is **already possible today**;
> running it is the operator's act, not the loop's.

Origin: **human** (task #360, via watch 2026-07-28 01:39), redirecting the
landed `#275` design: *"self-hosted with a tunnel or over a shared mesh or lan —
we should aim for simpler auth methods; ssh tunnel, session key auth'd via ssh
(magic-link esq), user/pw, sqrl if possible."*

10**His reasoning is sound and anchors this design: a self-hosted tool whose auth
depends on a third party's control plane is not self-hosted.** `#275`'s landed
design (`hub-public-auth.md`) put a mature authenticating reverse proxy —
Cloudflare Access, Tailscale Funnel — at the boundary and called that the safe
answer. He redirected because those boundaries lease identity from someone
else's control plane. This design does not re-argue for the proxy as the sole
boundary. One paragraph on where a proxy still wins, then move on:

> A local reverse proxy still wins for **one thing only**: TLS termination. HTTP
> without TLS on a LAN exposes every byte (including any credential) to anyone
> on the link, and stdlib Python cannot terminate TLS without dragging in a
> cert-handling story that belongs in a proxy, not a single-file hub. His own
20> `#360` Q2 ruling (14:53, on the tasks entry) settled this: **a local Caddy is
> acceptable** — its control plane is the operator's host, not a third party's.
> So a local Caddy may sit in front of the hub for TLS, while **ssh remains the
> identity trust root**. That is the shape this design aims at, not
> Cloudflare-Access-as-the-boundary.

---

## Relationship to `hub-public-auth.md` (#275) and `#276`

**This plan SUPERSEDES the identity recommendation of `#275` and EXTENDS its
boundary shape; it does not duplicate it.** Concretely:

30- `#275` (`hub-public-auth.md`) keeps its value as the **threat model, the
  asset inventory, the TLS/proxy analysis, and the `/data.json`-leak finding
  (its C2)**. None of that is re-derived here. Read §1–§4 of `hub-public-auth.md`
  first; this document assumes them.
- `#275`'s **identity recommendation** — Cloudflare Access / Tailscale Funnel as
  the authenticating boundary — is **superseded** by the operator's redirect:
  identity should root in ssh, which the operator already owns, not in a hosted
  control plane. The reverse-proxy *boundary* (its option B) survives with its
  identity component swapped for the ssh-issued session key (option 2 below), and
  with a local Caddy (option B3) substituted for Cloudflare/Tailscale so the
  trust stays on-host.
- `#276` (LAN bearer token) is **superseded by option 2 if the ssh-issued
  session lands**, per the `#360` ledger entry: a session key issued over ssh is
  strictly better than a static bearer token — same transport, but the credential
  is short-lived, revocable per-device, and not a static string an operator has
  to generate and guard by hand. If option 2 does not land, `#276` stands.
40- **Transport dependency:** options 2 and 3 reach the phone over the trusted-LAN
  binding that landed in `#233` (`lan-bind.md`). Option 1 (ssh tunnel) does not
  need it — ssh *is* the transport. So `#233` is a prerequisite for 2 and 3, and
  is already in place.

---

## The four options, in the order they cost least

Each option is answered against the six bullets the brief requires: **what the
operator does** (including the phone, per `#275`'s own use case — an auth design
that is correct and unusable from a phone has missed the point); **the trust
root** and what an attacker without it cannot do; **what code the hub needs and
what it must never store**; **revocation and expiry** ("how do I turn this off
after I lose my phone"); **cost** (implementation and per-new-device); and **the
failure mode**.

50A summary comparison table sits in the review artifact
(`360-hub-ssh-auth.html`); the prose is authoritative.

### Option 1 — ssh tunnel (no auth code at all)

The hub stays loopback-bound; **ssh is the boundary**. This is already possible
today, which is why documenting it is the first deliverable (§6).

**What the operator does.**
- *Host:* the hub runs as today — `python3 dreamhub.py serve` — binding
  `127.0.0.1:<port>`. The port is persisted at `~/.config/dreamwork/hub/port`
  (`dreamhub.py:792`); `dreamhub.py serve` prints the URL. The hub never binds a
  non-loopback interface.
60- *Laptop (same LAN or remote):* one command opens a forward from a local port
  to the hub's loopback port on the host:
  `ssh -N -L 8443:127.0.0.1:<hubport> operator@xsm` then browse to
  `http://localhost:8443`. `-N` means "no shell", which is what you want for a
  pure tunnel.
- *Phone:* an ssh app that does port forwarding (Termius, Blink Shell on iOS;
  Termux + `openssh` on Android). Configure a forward `8443 → 127.0.0.1:<hubport>`
  to `operator@xsm`, connect, then open the phone's browser to
  `http://localhost:8443`. See §6 for the full recipe. The phone must reach the
  host's sshd — directly on the LAN, or over Tailscale/WireGuard if remote.

**Trust root.** The operator's ssh private key on the device, authenticated by
`sshd` against `~/.ssh/authorized_keys`. An attacker who has not got the private
key cannot establish the tunnel, and therefore cannot reach the hub at all — the
70hub is invisible off-host. The hub itself holds no credential and makes no
authentication decision.

**What code the hub needs / must never store.** **None, and nothing.** The hub
keeps binding `127.0.0.1` exactly as it does today; the loopback default and the
`#233` trusted-LAN opt-in are load-bearing and untouched. This is the whole appeal:
zero auth surface in the hub, zero new secrets on disk.

**Revocation and expiry.** Remove the device's public key from
`~/.ssh/authorized_keys`; the next tunnel attempt fails. An *active* tunnel is
harder to kill without disrupting others — options are `pkill -u <device-user> -f
ssh` (blunt), or `sshd`'s `ClientAliveInterval`/`ClientAliveCountMax` to drop idle
sessions, or a per-key `ForceCommand`/`PermitOpen` restriction that scopes a key
to a single forward (see §6, hardening). Losing the phone = remove its key; the
80live session dies on its keepalive timer or when the phone sleeps.

**Cost.** **Zero implementation.** Per new device: generate a keypair, copy the
public key to `authorized_keys`, configure the ssh app's forward. The phone half
is the painful 10–15 minutes (install the app, import or generate a key, set up
the forward); a laptop is one `ssh -L`. No ongoing hub maintenance.

**Failure mode.** The tunnel drops on network change or sleep — the browser tab
goes dead; reconnecting re-establishes it and the page reloads. Two devices
racing: ssh handles this cleanly (two independent sessions/tunnels), and the hub
is read-only so there is no write race. A tunnel dropping mid-write: the hub's
existing atomic-write discipline (`#370`, `#371`) protects the data; the write
either landed or did not. **There is no credential to expire mid-session** — the
ssh session's lifetime is the credential's lifetime.

### Option 2 — session key issued over ssh (magic-link-shaped)

90The interesting one. The operator runs one command on the host (over ssh, or
locally) and gets a URL carrying a one-shot token; the browser trades the token
for a session cookie. **Ssh's existing authentication becomes the hub's, without
the hub verifying anything itself** — the hub trusts that whoever could run the
issue-command is the operator, because they already proved that to sshd.

This is the option that makes the phone usable **without an ssh app on the
phone**: the phone is just a browser on the LAN. The operator sshes in from a
trusted machine, mints a token, and hands the URL to the phone.

**What the operator does.**
- *Issue (from a laptop, or at the host console):*
  `ssh operator@xsm 'dreamhub issue-session --note phone'`. The hub prints a URL
  like `http://xsm:39880/?k=jT3x…` (the host is reached over the `#233` LAN
100  binding, not loopback). The `--note` tags the session for the revocation list.
- *Phone:* open that URL in the browser. The hub validates the one-shot `?k=`
  token on first hit, **consumes it**, and replies with a
  `Set-Cookie: dw_session=<sid>; HttpOnly; SameSite=Strict; Path=/` plus the page.
  Subsequent loads use the cookie; the `?k=` never appears again.
- *Delivery beyond copy-paste:* to keep the one-shot token off the phone's
  clipboard/history, the issue-command can print a QR code to the host terminal
  (stdlib `qrcode` is third-party; an ASCII/Unicode QR or a short numeric pairing
  code is the stdlib shape). The phone scans the screen; nothing is typed.

**Trust root.** Ssh (to run the issue-command) **plus** the one-shot token's
secrecy between issue and first use. An attacker who has not got ssh access
cannot mint a token. An attacker on the LAN who did not receive the token cannot
authenticate — the cookie gate returns 401. The token is one-shot, so a token
110sniffed from a log *after first use* is dead.

**What code the hub needs / must never store.**
- An `issue-session` subcommand: generate 32 bytes of `os.urandom`, store a
  record `{token_hash, created, expires_at, used=False, note}` (store the
  **hash**, not the token, the way a password store does — the token exists only
  in the printed URL and in memory for the seconds until first use) in a file
  under `~/.config/dreamwork/hub/sessions/`, and print the URL. Token TTL: ~5 min
  to first use.
- An auth middleware on every route: accept either a valid session cookie, or a
  valid unconsumed `?k=<token>` (which it then marks `used=True` and trades for a
  cookie). Otherwise 401.
- A session store: `{sid_hash, created, last_seen, expires_at, note}`; sliding
  expiry (e.g. 7 days, refreshed on activity).
- A `revoke-session` subcommand (`--all`, or `--note phone`).
- **What it must never store / log:** the cleartext token or sid (only their
  hashes); the full query string in any access log (redact `?k=`, always); the
120  password-equivalent in a URL that persists (the `?k=` is one-shot and dies in
  seconds — this is the answer to the brief's "a bearer token in a URL is a
  credential in his shell history and in any log"). The printed URL goes to the
  operator's stdout/tty, not to a file unless they pipe it; the issue-command
  should print directly to the tty to keep it out of shell history.
- **Pairs with `#275`'s C2:** the public/LAN surface must serve a redacted
  `/summary.json`, not the full-document `/data.json`, before this ships — the
  cookie gates the route, but a stolen cookie should not then leak
  `DREAMWORK.md`/`questions.md`/`lessons.md` in full. This is `#275`'s finding,
  inherited, not re-derived.

**Revocation and expiry.** `dreamhub revoke-session --all` (lost phone: ssh in,
revoke all, re-issue to the new device) or `--note phone`. Sessions expire on a
sliding TTL. The one-shot token expires in ~5 min if unused. This is the answer
to "how do I turn this off after I lose my phone": one ssh command, and the phone
130  is locked out the moment its cookie's next request 401s.

**Cost.** **Moderate** — ~3 increments: (1) `issue-session` + one-shot store +
hashing; (2) auth middleware + cookie + session store + log redaction; (3)
`revoke-session` + the redacted `/summary.json` (which is `#275`'s deliverable
anyway). Depends on the `#233` LAN binding (in place) and, for TLS, on a local
Caddy (his Q2 ruling). Per new device: one `ssh … issue-session` and a scan/paste
— **no key management on the device**, which is the whole point.

**Failure mode.** LAN drop: the phone loses the connection, reconnects, the
cookie is still valid (sliding TTL) — no re-login. Token expires before first use
(>5 min): re-issue, costs one command. Two devices: independent sessions, no
write race (read-only). Session store corruption: sessions are lost and everyone
re-logs-in — not catastrophic, since re-issue is one ssh command. Stolen cookie
on the LAN: bounded by the sliding TTL and by `/summary.json` redaction; rotate
by `revoke-session --all`.

### Option 3 — user/password

The fallback everyone understands, and the one with the most ways to get wrong.

**What the operator does.**
140- *Setup (once, at the host):* `dreamhub set-password` — prompts for a password,
  stores a scrypt hash (see measurement below) at
  `~/.config/dreamwork/hub/passwd` mode 0600.
- *Phone/laptop:* browse to `http://xsm:39880/`, get a login form, enter the
  password, the hub verifies with scrypt and sets a session cookie (same cookie
  machinery as option 2).

**Trust root.** The password — a **shared, reusable secret**. An attacker without
it cannot log in. Unlike ssh keys (which never leave the device) or one-shot
tokens (which die on use), a password is typed repeatedly and can be phished,
replayed, guessed, and reused across services.

**What code the hub needs / must never store.**
- A scrypt hash store. **`hashlib.scrypt` is stdlib and sufficient**: measured on
  this host today at **~105 ms/verify at n=2¹⁵ r=8 p=1** (32-byte key, ~34 MB
  working set), ~40 ms at n=2¹⁴. So a login verify is cheap; per-request verify
  is not (hence the session cookie). Store the record as
150  `scrypt$<n>$<r>$<p>$<salt_b64>$<hash_b64>`. No third-party import — the
  stdlib-only constraint (#275's C1) **holds for this option**, unlike shoo's
  ES256.
- Login route, session store, cookie middleware — identical to option 2's.
- **Must never store:** plaintext passwords (only scrypt hashes); never log the
  password; the hash file is 0600 and never served.

**The TLS gap is the real cost.** The password crosses the LAN in cleartext
unless the link is encrypted. So user/pw **requires either** the ssh tunnel
(option 1, which makes this redundant) **or** TLS (a local Caddy, his Q2 ruling).
Without one of those, anyone on the LAN sniffs the password. This is the central
reason user/pw is weak as a *standalone* design here.

**Revocation and expiry.** Change the password (one global password ⇒ changing it
revokes everyone). Per-user accounts are more complexity and buy little for a
single-operator hub. Session cookie expiry as option 2.

**Cost.** **Moderate-to-high, and mostly redundant.** scrypt verify (~105 ms) is
160fine; the login form and session store are shared with option 2; but the TLS
  requirement drags in a Caddy (or forces the tunnel, which makes user/pw
  pointless). Brute force: at ~9 verifies/sec single-threaded, a rate-limiter is
  mandatory (e.g. 5 attempts per sid per minute, exponential backoff). Per new
  device: type the password — the cheapest of all options, but also the weakest.

**Failure mode.** Forgotten password: locked out (recovery is ssh-in-and-reset,
which means ssh is the real trust root anyway). Brute force: bounded by rate
limiting + scrypt cost. Password reuse: if the operator reuses the dreamhub
password elsewhere, a leak there compromises the hub. Phishing on the LAN: a
lookalike page is trivial on HTTP.

### Option 4 — SQRL ("if possible") — a one-paragraph honest answer

SQRL (Steve Gibson, ~2013) is effectively **dormant**: the reference ecosystem
never reached sustained adoption, the `sqrlid.com` identity service is defunct,
and maintained clients are sparse and platform-specific. The protocol is
170idiosyncratic (EnScrypt KDF, Ed25519 signatures, base56 encoding) with **no
standard-library support anywhere** — and Ed25519 verify, like the ES256 that
blocked shoo in `#275`, is **not in Python's stdlib** (`cryptography` is
third-party). So for this hub SQRL is the worst combination: an unproven
protocol with a thin client ecosystem and a crypto dependency that breaks
stdlib-only. **Honest answer: no.** Not because SQRL is cryptographically broken,
but because it is not alive enough to bet an agent control plane on, and even if
it were it hits the same stdlib wall as the hosted-IdP tokens this whole task
exists to avoid.

---

## Recommendation, with an order

1. **Document option 1 (ssh tunnel) now — §6 is the deliverable that has value
   tonight.** It works today, it is the safest, it adds zero code, and it answers
   the phone case (clunkily, via an ssh app) without any new surface. This is the
   one thing to ship from this task as documentation.
1802. **If anything else is built, build option 2 (session key over ssh) first.** It
   is the option that honours his redirect most directly: ssh is the trust root,
   the phone needs no ssh app, the credential is short-lived and per-device
   revocable, and it supersedes `#276`'s static bearer token. It pairs with a
   **local Caddy** for TLS (his Q2 ruling), not with Cloudflare Access — so the
   identity stays on-host. It also carries `#275`'s redacted `/summary.json` as a
   hard prerequisite, which is correct: a session cookie should not gate a route
   that then leaks full documents.
3. **Do not build option 3 (user/pw) as a standalone.** Its only real value is as
   a layer behind TLS or the tunnel, both of which make it redundant. If TLS
   (Caddy) lands, option-2's session key is strictly better (no shared secret, no
   brute-force surface, no password reuse). User/pw is worth keeping in the file
   as the emergency fallback a future operator might want, not as something to
   spend an increment on.
4. **Do not build option 4 (SQRL).** Not alive; stdlib-blocked; even a survey
   implementation is not worth the crypto dependency.

**In one sentence:** document the ssh tunnel now; if he wants phone-without-ssh,
190build the ssh-issued session key behind a local Caddy; leave user/pw as a
   written fallback and SQRL as a documented "no".

**What is explicitly NOT worth doing:** a hosted IdP of any kind as the boundary
  (the thing this task redirects away from); a static bearer token (`#276`, if
  option 2 lands); hand-rolled crypto (re-stated from `#275`'s E3); and SQRL.

---

## §6 — The ssh-tunnel recipe (written and verified on paper)

> This is documentation of what is **already possible today**. It binds no
> interface, opens no tunnel itself, and starts no listener — it tells the
> operator what to type. The hub's loopback default is load-bearing and
> untouched.

**The shape:** `ssh -L` forwards a port on the *client* to the hub's loopback
200port on the *host*. The hub stays on `127.0.0.1`; ssh carries the bytes; the
client's browser talks to its own localhost. There are two hosts to name: the
**hub host** (where `dreamhub.py serve` runs) and the **client** (laptop or
phone).

### 0. Find the hub port (host)

```sh
# the hub persists its port at:
cat ~/.config/dreamwork/hub/port
# or just read the URL `dreamhub.py serve` prints when it starts
```
Call this `<HUBPORT>` below (e.g. `39880`).

### A. Laptop, on the same LAN or remote

```sh
# -N : no remote shell (this is a pure tunnel)
# -L 8443:127.0.0.1:<HUBPORT> : client's :8443 -> host's loopback :<HUBPORT>
# -o ExitOnForwardFailure=yes : fail loudly if the forward can't be set up
ssh -N -o ExitOnForwardFailure=yes -L 8443:127.0.0.1:<HUBPORT> operator@xsm
```
Then open `http://localhost:8443` in the laptop's browser. Leave the ssh session
210running; closing it closes the tunnel. Add `-f` to background it after auth
(`ssh -f -N …`), and `~C` (escape, then `C`) opens an ssh command-line to add more
forwards to a live session.

### B. Phone — iOS (Blink Shell or Termius)

These apps support port forwarding and are the realistic path on iOS, which has
no built-in ssh client.

1. Install **Blink Shell** (freemium) or **Termius** (freemium) from the App
   Store.
2. Import your ssh private key into the app (generate one in the app if you have
   none, and add its public half to the hub host's `~/.ssh/authorized_keys`).
3. Create a host: `operator@xsm` (or the host's LAN IP / Tailscale name).
4. Add a **port forward**: local `8443` → remote `127.0.0.1:<HUBPORT>`.
5. Connect the forward. Then open Safari to `http://localhost:8443`.

220The tunnel stays up while the app is in the foreground (and briefly in the
background, iOS permitting). Reconnecting after sleep is one tap.

### C. Phone — Android (Termux + openssh)

Termux is free and is the realistic path on Android.

```sh
# in Termux:
pkg install openssh
# copy your private key into Termux, then:
ssh -N -L 8443:127.0.0.1:<HUBPORT> operator@xsm
# leave Termux running; open Chrome/Firefox to http://localhost:8443
```
Termux's foreground-session "acquire wakelock" keeps the tunnel alive while the
screen is off.

### D. Remote (off-LAN) — reach sshd first

If the client is not on the LAN, it must reach the host's sshd some other way:
- **Tailscale/WireGuard** to the host (the mesh, not Funnel — no public
  exposure), then ssh to the tailnet address. This is option C from
  `hub-public-auth.md` and is strictly private (no public surface).
230- A **jump host** (`ssh -J jumpuser@jumphost operator@xsm`), if the operator
  already runs one.
- **Do not** expose sshd directly to the internet without hardening (see below).

### E. Hardening the sshd side (recommended, optional)

These sshd_config / authorized_keys restrictions scope a key to "forward to the
hub only" — defence in depth, so a stolen phone key can do nothing but reach the
hub:

```sh
# ~/.ssh/authorized_keys — prefix the phone's key with:
restrict,port-forwarding,permitopen="127.0.0.1:<HUBPORT>",command="echo tunnel-only" ssh-ed25519 AAAA... phone@device
```
`restrict` disables pty/shell/agent-forwarding; `port-forwarding` re-enables
forwards; `permitopen` limits the forward to exactly the hub's loopback port. A
key so scoped cannot open a shell or forward anywhere else. In `sshd_config`,
`ClientAliveInterval 300` + `ClientAliveCountMax 2` drops idle tunnels in ~10 min.

### F. Verification (paper)

240The recipe is verified on paper, not by running it (the hard constraint forbids
opening a tunnel): `ssh -L a:127.0.0.1:b host` is the standard OpenSSH local
forward — it binds `a` on the client and connects to `b` on the host's loopback,
which is exactly where the hub listens (`dreamhub.py:856` binds `127.0.0.1`). The
`permitopen` / `restrict` authorized_keys options are documented OpenSSH
directives. No part of the recipe requires the hub to bind off-loopback or the
operator to expose sshd publicly. **The hub's loopback default and the `#233`
trusted-LAN opt-in are untouched by this recipe.**

---

## Out of scope (and the hard constraint, restated)

- **No implementation.** No change to `dreamhub.py`, `watch.py`, `justfile`,
  `dev/capture/*`, `review-artifact.template.html`, `lint.py`, `tasks.md`,
  `questions.md`, `file-formats.md`, or any bind address or listen flag.
- **No non-loopback bind, no tunnel opened, no off-host listener started, no
250  config default changed** — by this lane. The hard constraint from the brief is
  absolute and was respected: this is design and documentation only. The
  ssh-tunnel recipe tells the *operator* what to type; the loop opened nothing.
- **`#275`'s open questions** (Q3 read-only vs read+write, Q5 the redacted
  `/summary.json`, Q6 the allowlist) are inherited, not re-asked here. Option 2
  assumes read-only publicly (Q3's safe answer) and assumes `/summary.json` ships
  first (Q5).
- A **migration**: none owed — no file format or persisted shape changes here.

## Primary sources reached

- `dreamhub.py` (read-only): `hub_port()` at `:792`, `serve()` at `:849`, loopback
  bind at `:856` — confirms the loopback-only posture and the persisted-port
  idiom.
- `hashlib.scrypt` (measured on this host, this session): ~105 ms/verify at
  n=2¹⁵ r=8 p=1, stdlib-only — the measurement behind option 3's "stdlib-only
  holds" claim.
260- `hub-public-auth.md` (#275): threat model, asset inventory, TLS/proxy
  analysis, `/data.json`-leak (C2) — inherited, not re-derived.
- `lan-bind.md` (#233): the trusted-LAN binding options 2 and 3 depend on.
- OpenSSH `ssh_config`, `sshd_config`, and `authorized_keys` man pages: the
  `-L`/`-N`/`ExitOnForwardFailure` flags and the `restrict`/`permitopen`/
  `port-forwarding` authorized_keys options cited in §6.
- SQRL: Steve Gibson's sqrl-protocol spec (grc.com/sqrl) for the protocol shape;
  ecosystem status from the absence of maintained, broadly-deployed clients and
  the defunct `sqrlid.com` — the basis for option 4's honest "no".
