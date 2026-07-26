# Safe LAN Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let `watch.py` bind to an explicitly chosen loopback or trusted-LAN interface and serve approved hostnames without weakening the existing default.

**Approval gate:** Non-local binding opens the authentication question under this repository's existing architecture decisions. Implementation proceeds only if the human explicitly chooses either **A: unauthenticated trusted-LAN mode** (recommended narrow scope), accepting that any client which can reach the socket and send an allowed Host can read project data and invoke writes; or **B: authenticated access**, which supersedes this plan with a separate auth/TLS design.

**Architecture after A is approved:** Add one singular `--bind ADDRESS`, repeatable `--allow-host HOST`, and singular `--url-host HOST` for the advertised/opened URL. A small request-authority module normalises allowed host tokens, validates every request's `Host`, and validates browser `Origin` on every POST. Loopback stays implicit/default; wildcard or non-loopback binding requires explicit non-loopback allowed host names and displays an unauthenticated trusted-LAN warning. This is not authentication and is unsupported for public/WAN exposure.

**Tech Stack:** Python 3 stdlib `argparse`, `http.server`, `ipaddress`, `urllib.parse`; pytest integration tests.

## Global Constraints

- Default remains `127.0.0.1` with existing behaviour and deployment unchanged.
- Trusted-LAN exposure is opt-in, explicitly unauthenticated, and requires human consent before implementation.
- Host validation gates every route before target data is read or writes are witnessed.
- Origin validation gates POST before body read/submission logging, because a foreign site is not the human submitting to this app.
- No wildcard host patterns, suffix matches, DNS resolution, proxy-header trust, TLS, or public-network claims.
- IPv6 literals are bracketed in Host/Origin/URLs and use an AF_INET6 server class.

---

### Task 1: Pure authority and endpoint model

**Files:** Modify `watch.py`; test `test_watch.py`.

**Interfaces:**
- `normalise_host_token(raw: str) -> str`: lowercases DNS, strips one trailing dot, validates IPv4/IPv6/bracket syntax, rejects ports/wildcards/control chars.
- `split_host_header(raw: str) -> tuple[str, int | None] | None`: parses DNS/IPv4 with optional port and bracketed IPv6 with optional port; rejects ambiguous bare IPv6 and malformed ports.
- `RequestAuthority(allowed_hosts, port).host_allowed(header) -> bool`
- `RequestAuthority(...).origin_allowed(origin, host_header) -> bool`: absent Origin allowed for CLI/non-browser; `null`, foreign scheme/host/port rejected; same `http` authority accepted.
- `bind_family(address) -> AF_INET|AF_INET6`, `display_host(bind, allowed, url_host) -> navigable host`.

- [ ] Red unit matrix: case/trailing dot, hostname, IPv4, bracketed IPv6, missing/multiple/bad Host, ports, wildcard/control, Origin same/foreign/null, IPv6 family and display URL.
- [ ] Implement minimal pure helpers.
- [ ] Green focused tests.

### Task 2: Gate the HTTP server and CLI

**Files:** Modify `watch.py`, `test_watch.py`, `watch-design.md`.

- [ ] Red integration tests: every GET/POST rejects missing/disallowed Host (421); foreign/null Origin POST rejects (403) before `submissions.log` exists; allowed Host GET works; allowed same-origin POST works; absent-Origin CLI POST works and is witnessed.
- [ ] Extend `make_handler(target, dev=False, authority=None)`; default test authority derives from bound loopback host for compatibility. `do_GET`/`do_POST` call one preflight before route/body handling.
- [ ] CLI: `--bind ADDRESS` singular, default `127.0.0.1`; `--allow-host HOST` repeatable; `--url-host HOST` singular. Always allow exact numeric loopback aliases plus `localhost` only in loopback mode. Non-loopback/wildcard requires an explicit non-loopback allow-host and a url-host contained in the allowlist.
- [ ] Use AF_INET6 subclass for IPv6. `--open` uses `--url-host`; a concrete non-wildcard bind may supply its own default. Never browse/print `0.0.0.0` or `::` as destination.
- [ ] Startup output lists listen address, allowed Hosts, and trusted-LAN unauthenticated warning for non-loopback.
- [ ] Green integration and existing tests.

### Task 3: Docs, migration, deployment proof

**Files:** Modify `watch.py` module docstring, `SKILL.md`/README-facing invocation docs if present, `file-formats.md` only if persisted shape changes (none expected), `watch-design.md`; add `migrations/2026-07-26-16-lan-bind.md`; tests.

- [ ] Document examples:
  - default: `watch.py --target .`
  - LAN: `watch.py --target . --bind 0.0.0.0 --allow-host xsm --allow-host 192.168.1.20`
  - IPv6: `--bind :: --allow-host xsm --allow-host ::1` with bracketed URL display.
- [ ] State trusted-LAN threat model and public/WAN prohibition plainly.
- [ ] Prove default `just deploy` remains loopback and `deployed.py` still identifies snapshot.
- [ ] Run full `pytest -q test_watch.py`, lint, targeted network tests, diff-check, and `just audit-styleguide` (record historical baseline separately).
- [ ] Two-axis review/fix/rereview, rebase, verify, merge, push, deploy.

## Rejected alternatives

- **Repeatable binds:** stdlib would need multiple coordinated server instances/ports and lifecycle handling; one wildcard bind already covers loopback+LAN for the requested scope.
- **Automatic hostname/IP discovery:** network state changes and DNS resolution create an implicit, drifting allowlist.
- **Host-only security:** stops DNS rebinding but not another LAN client.
- **Token/basic auth in this increment:** without TLS it creates misleading protection and credential handling; real auth is a separate design prerequisite for untrusted/public exposure.
- **Allow `Origin: null`:** sandboxed/file origins could write over LAN; reject.

--- SUMMARY ---

- First obtain explicit consent for unauthenticated trusted-LAN mode, or stop for an auth/TLS design.
- Add singular explicit bind, repeatable exact Host allowlist, and explicit advertised URL host; loopback remains default.
- Validate Host on every request and same-origin browser POSTs before reading bodies.
- Support IPv4/IPv6 correctly and print only navigable URLs.
- Label non-loopback mode honestly as unauthenticated trusted-LAN access; public/WAN remains unsupported.
- Red-prove the security boundary, document/migrate it, then review and deploy without changing the default service.
