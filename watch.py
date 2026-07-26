#!/usr/bin/env python3
"""watch.py — local dashboard for a running dreamloop.

Plan: .dreamwork/docs/plans/watch-py.md (human-authorized 2026-07-25).
Stdlib only. Binds 127.0.0.1 by default. Explicit non-loopback binding is an
unauthenticated trusted-LAN mode: every request requires an exact allowed Host
and browser POSTs require matching HTTP Origin. These are rebinding/CSRF
safeguards, not client authentication; public/WAN exposure is unsupported.
Human-authorized POST routes append answers, questions, notes, commands and
settings to their documented files; all other routes read.
"""

import argparse
import hashlib
import http.server
import ipaddress
import json
import os
import random
import re
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import urllib.parse
from dataclasses import dataclass
import webbrowser

# Server generation: a fresh value every time this process (re)starts, so a
# client can tell "same server, data changed" from "server rebuilt, reload
# the shell". Sent on /mtime; the client reloads when it changes. This alone
# (no --autoreload) fixes stale open tabs after a manual restart/redeploy.
GENERATION = "%.6f" % time.time()


_HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


def normalise_host_token(raw):
    """Return one canonical host-only allowlist token.

    No ports, wildcards or DNS lookups: the allowlist is exact and stable.
    IPv6 accepts bracketed configuration input for convenience but stores the
    compressed address without brackets; brackets belong only to authorities.
    """
    if not isinstance(raw, str) or not raw or raw != raw.strip():
        raise ValueError("host must be a non-empty token")
    if any(ord(c) < 33 or ord(c) == 127 for c in raw):
        raise ValueError("host contains whitespace or control characters")
    if raw.startswith("["):
        if not raw.endswith("]"):
            raise ValueError("malformed bracketed host")
        raw = raw[1:-1]
    elif "]" in raw or "[" in raw:
        raise ValueError("malformed bracketed host")

    try:
        return ipaddress.ip_address(raw).compressed.lower()
    except ValueError:
        pass
    if ":" in raw or "*" in raw or "/" in raw:
        raise ValueError("host token must not contain a port or wildcard")
    name = raw.lower()
    if name.endswith("."):
        name = name[:-1]
    if not name or len(name) > 253:
        raise ValueError("invalid DNS host length")
    labels = name.split(".")
    # Never reinterpret a rejected IPv4 spelling as DNS. Different HTTP/DNS
    # stacks disagree on leading-zero and non-canonical numeric forms, which
    # would make an exact allowlist non-exact at the socket boundary.
    if len(labels) == 4 and all(label.isdigit() for label in labels):
        raise ValueError("non-canonical IPv4 address")
    if not all(_HOST_LABEL.fullmatch(label) for label in labels):
        raise ValueError("invalid DNS host")
    return name


def split_host_header(raw):
    """Parse one HTTP authority into `(canonical_host, explicit_port)`.

    Bare IPv6 is deliberately rejected: HTTP requires brackets and guessing
    which colon begins a port turns an allowlist into an ambiguity.
    """
    if not isinstance(raw, str) or not raw or raw != raw.strip() or "," in raw:
        return None
    host, port = raw, None
    if raw.startswith("["):
        close = raw.find("]")
        if close < 0:
            return None
        host = raw[1:close]
        rest = raw[close + 1:]
        if rest:
            if not rest.startswith(":"):
                return None
            port = rest[1:]
    else:
        if raw.count(":") > 1:
            return None
        if ":" in raw:
            host, port = raw.rsplit(":", 1)
    if port is not None:
        if not port.isascii() or not port.isdigit():
            return None
        port = int(port)
        if not 1 <= port <= 65535:
            return None
    try:
        return normalise_host_token(host), port
    except ValueError:
        return None


class RequestAuthority:
    """Exact Host and same-origin policy for one listening server."""

    def __init__(self, allowed_hosts, port):
        self.allowed_hosts = frozenset(normalise_host_token(h)
                                       for h in allowed_hosts)
        self.port = int(port)

    def host_allowed(self, header):
        parsed = split_host_header(header)
        if not parsed:
            return False
        host, port = parsed
        return host in self.allowed_hosts and (port is None or port == self.port)

    def origin_allowed(self, origin, host_header):
        if origin is None or origin == "":
            return True                 # CLI/non-browser client
        if origin == "null" or not self.host_allowed(host_header):
            return False
        try:
            parsed = urllib.parse.urlsplit(origin)
            if (parsed.scheme != "http" or parsed.username is not None or
                    parsed.password is not None or parsed.path not in ("", "/") or
                    parsed.query or parsed.fragment):
                return False
            origin_host = normalise_host_token(parsed.hostname or "")
            origin_port = parsed.port or 80
        except (ValueError, UnicodeError):
            return False
        request_host = split_host_header(host_header)
        if not request_host:
            return False
        host, port = request_host
        return origin_host == host and origin_port == (port or self.port)


def bind_family(address):
    """Return the socket family for a numeric bind address."""
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError as exc:
        raise ValueError("--bind must be a numeric IPv4 or IPv6 address") from exc
    return socket.AF_INET6 if parsed.version == 6 else socket.AF_INET


def display_host(bind, allowed_hosts, url_host=None):
    """Choose one navigable, allowed host for printed/opened URLs."""
    bind_ip = ipaddress.ip_address(bind)
    allowed = frozenset(normalise_host_token(h) for h in allowed_hosts)
    if url_host is not None:
        chosen = normalise_host_token(url_host)
        if chosen not in allowed:
            raise ValueError("--url-host must also be allowed")
    elif bind_ip.is_unspecified:
        raise ValueError("wildcard bind requires --url-host")
    else:
        chosen = bind_ip.compressed.lower()
        if chosen not in allowed:
            raise ValueError("bind address must be in --allow-host or an allowed "
                             "--url-host is required")
    try:
        return "[{}]".format(ipaddress.IPv6Address(chosen).compressed)
    except ValueError:
        return chosen


@dataclass(frozen=True)
class NetworkOptions:
    bind: str
    port: int
    allowed_hosts: tuple
    url_host: str
    family: int
    trusted_lan: bool

    @property
    def authority(self):
        return RequestAuthority(self.allowed_hosts, self.port)


class _SingleValue(argparse.Action):
    """A singular flag that rejects accidental last-value-wins repeats."""

    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest, None) is not None:
            parser.error(f"{option_string} may be specified only once")
        setattr(namespace, self.dest, values)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--target", default=".", metavar="DIR")
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--bind", action=_SingleValue, default=None, metavar="ADDRESS",
                   help="numeric listen address (default: 127.0.0.1)")
    p.add_argument("--allow-host", action="append", default=[], metavar="HOST",
                   help="exact accepted Host name/address (repeatable)")
    p.add_argument("--url-host", action=_SingleValue, default=None, metavar="HOST",
                   help="allowed navigable host printed/opened for this bind")
    p.add_argument("--open", action="store_true",
                   help="open the dashboard in a browser")
    p.add_argument("--dev", action="store_true",
                   help="dev mode: show an fps counter on the page")
    p.add_argument("--autoreload", action="store_true",
                   help="re-exec on source change (implied by --dev)")
    args = p.parse_args(argv)
    if args.bind is None:
        args.bind = "127.0.0.1"
    return args


def network_options(bind, allow_hosts, url_host, port):
    """Validate CLI networking into the closed server configuration."""
    bind_ip = ipaddress.ip_address(bind)
    family = bind_family(bind)
    explicit = {normalise_host_token(host) for host in allow_hosts}
    trusted_lan = not bind_ip.is_loopback
    if trusted_lan:
        non_loopback = set()
        for host in explicit:
            try:
                if not ipaddress.ip_address(host).is_loopback:
                    non_loopback.add(host)
            except ValueError:
                non_loopback.add(host)       # explicit DNS name
        if not non_loopback:
            raise ValueError("non-loopback bind requires --allow-host")
        if url_host is None and not bind_ip.is_unspecified:
            candidate = bind_ip.compressed.lower()
            if candidate in explicit:
                url_host = candidate
        shown = display_host(bind, explicit, url_host)
        allowed = tuple(sorted(explicit))
    else:
        # Loopback mode preserves intentional aliases and the old zero-config
        # behavior. Explicit additions remain exact but do not make it LAN mode.
        allowed = tuple(sorted(explicit | {"localhost", "127.0.0.1", "::1"}))
        shown = display_host(bind, allowed, url_host)
    return NetworkOptions(bind_ip.compressed.lower(), int(port), allowed, shown,
                          family, trusted_lan)


def server_class(family):
    if family == socket.AF_INET:
        return http.server.ThreadingHTTPServer
    if family != socket.AF_INET6:
        raise ValueError("unsupported socket family")

    class IPv6ThreadingHTTPServer(http.server.ThreadingHTTPServer):
        address_family = socket.AF_INET6

    return IPv6ThreadingHTTPServer


# The steering vocabulary — ONE source. The server validates POST /command
# against it, the composer renders its buttons and its hover menu from it,
# and the popped-out form fills its options from it, so a new kind is one
# entry here and nothing else. Order is display order; `common` kinds get a
# button in the composer, the rest live in the hover menu. Plugin-contributed
# kinds (#86) append to this list — nothing downstream assumes a fixed set.
COMMANDS = (
    {"kind": "add-idea", "label": "add idea", "common": True,
     "desc": "park a thought; the loop picks it up when it chooses next"},
    {"kind": "do-next", "label": "do next", "common": True,
     "desc": "jump this to the front of the queue (text optional)"},
    {"kind": "do-now", "label": "do now", "common": True,
     "desc": "interrupt the current increment and start this instead"},
    {"kind": "maintenance", "label": "maintenance", "common": False,
     "desc": "housekeeping: grooming, re-reads, alignment passes"},
)

# His colour for this project (#143) — the closed set, and the whole reason
# it is a closed set. Absolute hues in degrees.
#
# A HUE, NOT A COLOUR. The tint rotates the ambient field's hue about the grey
# axis and moves nothing else, so every contrast on the page is what it was:
# the text ramp, and above all `--accent`, whose one job is marking the live
# and actionable thing. Free RGB would have let one choice put the field where
# the accent lives and quietly cost the page its loudest signal.
#
# Two constraints picked these six. They must be distinguishable AT 16PX in
# the favicon, which is where the tint is actually used to navigate — a strip
# of dreaming projects, told apart by colour. And none of them may sit in the
# amber band (~35-70), because `--warn` lives there: a project tinted amber
# would paint its whole ambient field the one colour on this page that means
# BROKEN.
TINTS = {"indigo": 229, "violet": 268, "teal": 188,
         "green": 150, "magenta": 312, "rose": 348}
TINT_DEFAULT = "indigo"

# Design tokens + shared shell: every watch page renders through these,
# so a redesign is a token/component edit, not a page-by-page hunt.
STYLE = """<style>
  :root { --bg:#0b0f19; --panel:#111827; --panel2:#1e293b;
    --line:#1f2937; --border:#334155; --text:#d1d5db; --bright:#f3f4f6;
    --lit:#e5e7eb; --muted:#9ca3af; --dim:#6b7280; --dimmer:#4b5563;
    --accent:#a5b4fc; --space:1.6rem; --radius:4px;
    /* The page's SECOND colour, and the only rule it has is that it means
       BROKEN rather than live (#136). The accent says "this is happening";
       amber says "the channel to you has failed and you cannot see it from
       the numbers". One user, ever: a questions.md the reader cannot see.
       Adding it breaks the one-accent rule on purpose — a fault rendered in
       indigo reads as activity, and this is the one thing on the page that
       must not. Same lightness family as the accent, warm against a cool
       page, so it is unmistakably not it. */
    --warn:#fcd34d; }
  /* Scrollbars are chrome, and chrome should recede: hairline track,
     dim thumb, no arrows. Firefox first, then the WebKit pseudos. */
  * { scrollbar-width:thin; scrollbar-color:var(--dimmer) transparent; }
  ::-webkit-scrollbar { width:7px; height:7px; }
  ::-webkit-scrollbar-track { background:transparent; }
  ::-webkit-scrollbar-thumb { background:var(--dimmer);
                              border-radius:var(--radius); }
  ::-webkit-scrollbar-thumb:hover { background:var(--dim); }
  ::-webkit-scrollbar-corner { background:transparent; }
  body { background:var(--bg); color:var(--text); margin:0;
         padding:2.5rem 1rem;
         font-family:ui-monospace,'JetBrains Mono',monospace; font-size:.8rem; }
  .wrap { max-width:72ch; margin:0 auto; position:relative;
          perspective:1500px; }
  header { color:var(--bright); font-size:1rem; margin-bottom:.25rem; }
  #meta { color:var(--dim); margin-bottom:2rem; }
  #meta .q { color:var(--accent); }
  /* The heading survives navigation, so its parts travel rather than
     reload (#110). Crumbs are inline-block because a transform does nothing
     to an inline box; the separator belongs to the crumb that FOLLOWS, so a
     departing crumb takes no punctuation with it. */
  #chrome { position:relative; }
  .crumb, .htitle { display:inline-block;
    transition:transform .85s cubic-bezier(.32,.1,.2,1),
               opacity .55s ease, filter .55s ease; }
  /* non-breaking spaces: an inline-block collapses the leading/trailing
     whitespace of generated content, so " · " would render flush */
  .crumb + .crumb::before { content:"\\00a0\\00b7\\00a0"; color:var(--dim); }
  /* the snapped start state for anything arriving: transition:none so it
     BEGINS here instead of animating toward here (the enter-snap rule).

     `!important` on the transition, and only on the transition. This class
     has to beat whatever the arriving element's own component says, or the
     rule is a lie exactly where a component has motion of its own — which is
     everywhere it matters. It WAS a lie: `.qa` declares the same three
     transitions at the same specificity and later in this sheet, so a
     question card carrying `.dreamin` kept a 0.85s transition and an opacity
     of 1, animated one frame TOWARD 0, and had the class removed. Arrivals
     have never faded in since #104; crumbs, which declare no transition of
     their own, always have. Source order is not a contract — a component
     added below here would silently take it back — so the invariant is
     stated as one. The other three properties stay overridable: they are the
     start POSE, and a component may reasonably want its own. */
  .dreamin { transition:none !important; opacity:0; filter:blur(4px);
             transform:translateY(5px); }
  /* a departing crumb is lifted out of flow at its own rect, so survivors
     close the gap underneath it while it dreams away in place */
  .crumb.crumbout { position:absolute; z-index:2; pointer-events:none; }
  .crumb.crumbout::before { content:none; }
  .crumb.crumbgone { opacity:0; filter:blur(5px); transform:translateY(-7px); }
  @media (prefers-reduced-motion: reduce) {
    .crumb, .htitle { transition:none; }
  }
  .label { color:var(--dim); text-transform:uppercase; letter-spacing:.08em;
           font-size:.7rem; margin:var(--space) 0 .5rem; }
  /* ── an expanded element becomes PROMINENT, not just taller (#169) ───
     His words: expanding should grow padding above and below, so the thing he
     opened reads as foregrounded. Expanding is a change in IMPORTANCE, not a
     reveal — what he opened is now the subject of the page — so it is an
     IDIOM here rather than a treatment on one component, and every disclosure
     on this page inherits it by existing.

     Two channels, both already this page's own vocabulary:

       AIR. It claims space above and below. On a page with no cards, borders
       or fills, whitespace IS the structural device, so claiming space is
       what being foregrounded looks like here. It costs the summary an 8px
       shift under his pointer on the click that opens it; that is what "air
       above" means and it is the half he asked for by name.

       LUMINANCE. Its summary steps one place UP the text ramp, because
       emphasis on this page is luminance (the same rule as `**bold**`).
       NEVER `font-weight`: a mono face steps rather than transitions, and
       re-metricing the summary would move the very thing being opened.

     The step is stated PER SURFACE, one line each, rather than as a single
     bright colour for every open summary — each of these sits somewhere
     different on the ramp when closed, on purpose (a settled thread at
     `--dim`, a folded card's title at `--muted`), and one flat rule would
     drag all of them to the same brightness. That is the shape that overruled
     `.sgbtn` (#121) and leaked into `.qfield textarea` (#139); what is
     generic here is the RULE (open is one step up), not the value.

     THE PADDING DOES NOT TRANSITION, and that is what keeps this one gesture
     rather than two. A card-nested disclosure measures its new rect
     immediately after `det.open` flips (the `.qa details > summary` handler),
     so the growth has to be in the layout by then — the CARD's height travel
     is what animates it, carrying every card below for free. A padding
     transition would hand `regroupCards` a start-of-transition rect and the
     FLIP would aim at a height the card never reaches, snapping at the end. */
  details { margin:.25rem 0; }
  details[open] { padding:.5rem 0; }
  summary { cursor:pointer; color:var(--lit); list-style:none; }
  details[open] > summary { color:var(--bright); }
  summary::before { content:"+ "; color:var(--dim); }
  details[open] > summary::before { content:"- "; }
  .age { color:var(--dim); margin-left:.5rem; }
  pre { white-space:pre-wrap; color:var(--muted); margin:.4rem 0 .8rem 1ch;
        border-left:1px solid var(--line); padding-left:1ch; }
  /* rendered prose (#102). Same hairline rail and colour as the <pre> it
     replaces — this changes how the text WRAPS, not how the page reads. */
  .md { color:var(--muted); margin:.4rem 0 .8rem 1ch;
        border-left:1px solid var(--line); padding-left:1ch; }
  .md > :first-child { margin-top:0; }
  .md > :last-child { margin-bottom:0; }
  .md p { margin:.45rem 0; }
  .md .mdh { color:var(--lit); margin:.7rem 0 .25rem; }
  /* a bullet hangs: the marker sits in the gutter and wrapped lines line up
     under the text, so nesting stays legible at any column width. */
  .md .mdli { margin:.28rem 0 .28rem calc(var(--lvl, 0) * 1.9ch);
              padding-left:1.6ch; text-indent:-1.6ch; }
  .md .mdli::before { content:"\\00b7  "; color:var(--dim); }
  .md pre.mdcode { margin:.45rem 0; white-space:pre; overflow-x:auto; }
  /* emphasis is luminance, not weight (see mdSpans) */
  .md strong, .anstext strong, .follow strong {
    font-weight:inherit; color:var(--bright); }
  .md em, .anstext em, .follow em { font-style:italic; color:var(--muted); }
  code { color:var(--lit); background:var(--panel);
         border-radius:3px; padding:0 .3ch; }
  /* a commit row (#132). No element catch-all in here: `.git div` used to
     colour these, and that is the shape that overrode `.sgbtn` (#121) and
     leaked into `.qfield textarea` (#139) — a rule that outlives the thing it
     stood in for silently beats the components that render inside it later.
     Every row part is addressed by its own class.
     FIXED HEIGHT is #151's, not decoration: the subject ellipsises rather
     than wrapping, so a long message cannot change the panel's height and a
     row arriving or leaving moves the rows by exactly one row. */
  /* THE ROW IS A <details> (#166), so the flex row moved onto its summary and
     the margin every other disclosure wants is taken back here. `details`
     carries `margin:.25rem 0` a hundred lines up, and 4px above and below
     five rows is 40px of panel that grows and shrinks — #151 rests on this
     panel's height being a CONSTANT so a landing commit moves the page by
     exactly nothing. Zeroed at the row, not weakened at `details`, because
     every other disclosure on the page still wants that margin. */
  .git .commit { margin:0; color:var(--dim);
                 /* the same travel a question card gets (#151 reuses #104's
                    regroup); travelCard overrides this inline while it runs */
                 transition:transform .85s cubic-bezier(.32,.1,.2,1),
                            opacity .55s ease, filter .55s ease; }
  .git .commit > summary { display:flex; align-items:baseline; gap:1ch;
                 height:1.4rem; line-height:1.4rem; color:var(--dim); }
  /* #169's step, stated for THIS surface as that rule requires: a closed row
     sits at --dim, the dimmest summary on the page, so open is one place up
     the ramp and not the shared --bright, which would drag the five-row panel
     to the loudest thing on the dashboard for a peek. */
  .git .commit[open] > summary { color:var(--muted); }
  /* the air is #169's and it must NOT transition: `regroupCards` measures the
     row's new rect in the same tick the toggle flips, so a growing padding
     hands the FLIP a start-of-transition height and the travel snaps at the
     end. Stated here because this list is the one `prominence.mjs` does not
     reach. */
  .git .commit[open] { padding:.5rem 0; }
  .git .gdetail { margin:.15rem 0 .1rem 2ch; }
  .git .gmeta { color:var(--dimmer); font-size:.7rem;
                font-variant-numeric:tabular-nums; }
  .git .gnone { color:var(--dimmer); font-size:.7rem; margin:.35rem 0; }
  /* the file list wraps as chips rather than a column: it is a glance at what
     the commit touched, and a fifty-line list would bury the body above it */
  .git .gfiles { display:flex; flex-wrap:wrap; gap:.2rem 1.5ch;
                 margin:.35rem 0 .1rem; }
  .git .gfile { color:var(--dim); font-size:.7rem; }
  .git .gmore { color:var(--dimmer); }
  .git .gsha { flex:0 0 auto; color:var(--dimmer); }
  .git .gsub { flex:1 1 auto; min-width:0; overflow:hidden;
               white-space:nowrap; text-overflow:ellipsis; }
  .git .maint .gsub { color:var(--accent); }
  /* the ticking half of the row: pinned right, and tabular so the digits do
     not jitter the column every second as they change */
  .git .cage { flex:0 0 auto; margin-left:auto;
               font-variant-numeric:tabular-nums; }
  /* which revision this page is RUNNING (#140), directly under the label.
     Three brightnesses for three kinds of answer, and the ranking is the
     whole design: a healthy answer is a fact (dim), an answer this page
     could not compute is a fact about the page (dimmest), and a page
     serving code older than HEAD is a FAULT — it invalidates everything
     else on screen, so it takes `--warn` and the rail.
     THE SECOND USE OF THE RAIL, and the comment on .qhealth used to say it
     was the only one. What the two share is exactly what earns it: both are
     the page saying it cannot be trusted right now — one about the file it
     reads, one about the code it runs. Nothing that is merely important
     gets it. */
  /* the burndown (#142). TWO TRACKS OVER ONE SET OF COLUMNS: the level (how
     many were open) above, the flow (arrivals up, completions down about a
     hairline) below. Direction is what tells the two flow series apart —
     colour is not spent on it, and the accent is not spent here at all,
     because nothing in this panel is waiting on him.
     EVERY HEIGHT IN HERE IS FIXED. The panel is a constant, exactly as the
     commits panel is (#151), so fresh data changes bars and never moves the
     page — which is what lets the bars animate on a data change without
     dragging four panels with them. */
  .bd { margin:.1rem 0 .9rem; }
  /* ONE LINE, ELLIPSISED — #151's mechanism for #151's reason, one panel
     down: the numbers in here change, and a head that wraps to two lines
     changes the panel's height, which is the premise that lets the bars
     animate without dragging everything below them. */
  .bdhead { color:var(--dim); font-size:.7rem; margin-bottom:.4rem;
            white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .bdhead .bdnum { color:var(--lit); }
  .bdtrack { display:flex; align-items:stretch; gap:2px; }
  .bdnet { height:30px; }
  .bdflow { height:34px; margin-top:9px; }
  .bdcol { flex:1 1 0; min-width:0; display:flex; flex-direction:column;
           justify-content:flex-end; }
  .bdflow .bdcol { justify-content:stretch; }
  .bdhalf { flex:1 1 0; display:flex; }
  .bdtop { align-items:flex-end; }
  /* the standing opacity transition is what `.dreamin` needs to ease BACK
     from: that class snaps the element to 0 with `transition:none
     !important` and is removed a frame later, so the element's own
     transition is the whole arrival. Without one here a new bucket would
     pop in — which is precisely what #154 found `.qa` doing for the whole
     life of #104. */
  .bdbar { width:100%; transition:opacity .55s ease; }
  /* THE LEVEL IS A STEP LINE, NOT A FILLED BAR, and that was decided by
     rendering it: on a ledger whose open count runs 12 to 67 the filled
     version is a near-uniform block, because every column is between 40 and
     100 percent of the tallest. A 2px cap on a transparent box of the same
     height is the same number and reads as the staircase it is. Dimmest on
     the ramp besides, because it is the DERIVED series — the two it comes
     from sit above it. */
  .bdlevel { border-top:2px solid var(--dimmer); }
  .bdup { background:var(--dim); align-self:flex-end; }
  .bddown { background:var(--muted); }
  .bdrule { height:1px; background:var(--line); flex:0 0 1px; }
  .bdaxis { display:flex; justify-content:space-between; color:var(--dimmer);
            font-size:.65rem; margin-top:.3rem; }
  .bdnote, .bdnone { color:var(--dimmer); font-size:.7rem; max-width:66ch;
                     margin:.45rem 0 0; }
  .gserve { color:var(--dim); font-size:.7rem; margin:-.15rem 0 .55rem;
            max-width:60ch; }
  .gserve.unknown { color:var(--dimmer); }
  .gserve.stale { color:var(--warn);
                  border-left:2px solid var(--warn); padding-left:.8rem; }
  /* the dashboard's questions fold (#141). `> summary` and not `summary`:
     the child combinator is what keeps this from being one of the catch-alls
     above — a question card inside carries its OWN <details><summary>, and a
     descendant rule here would restyle every one of them.
     At a genuine zero the whole line drops to the dim end and keeps no
     accent, because the accent is for things that are live and actionable. */
  .qsec > summary { color:var(--lit); }
  /* This one takes #169's DEFAULT step (--lit closed, --bright open) and so
     states nothing — but its zero state deliberately does not: `.none` outranks
     `details[open] > summary`, so a section with nothing to answer stays at the
     dim end even while he is looking inside it. Disabled means "nothing here
     needs you", and opening it does not change that (#141). */
  .qsec > summary.none, .qsec > summary.none::before { color:var(--dimmer); }
  .qsec .qsecn { color:var(--accent); }
  .dim { color:var(--dimmer); }
  a { color:var(--accent); text-decoration:none; }
  a:hover { text-decoration:underline; }
  /* a card travels to its new place in the list rather than teleporting
     there (#104/#77); the transform is set and cleared by regroupCards */
  .qa { margin:.6rem 0 1rem;
        transition:transform .85s cubic-bezier(.32,.1,.2,1),
                   opacity .55s ease, filter .55s ease; }
  /* a card that has left the list entirely dreams away where it stood */
  .qaghost { position:absolute; z-index:3; pointer-events:none;
    transition:opacity .7s ease, filter .7s ease, transform .7s ease; }
  .qaghost.gone { opacity:0; filter:blur(6px); transform:translateY(-10px); }
  /* ...but WHICH WAY it dreams away follows the list it is leaving (#174).
     A question card's neighbours travel UP to close the gap it left, so a
     ghost that rises is continuous with them. In the commits panel the
     gesture runs the other way: a new commit pushes the four survivors DOWN
     one row, so the departing bottom row has to fall with them and grow out
     of frame. Rising there reverses against everything around it, which is
     what he saw ("the bottom commit moves *up* towards where the new one
     appears"). Growing while fading is the page's standing departure — it is
     what `.ghost.out` does for a whole view — so this is the same idiom with
     its sign taken from its surroundings, not a second one. */
  .qaghost.commit.gone { transform:translateY(14px) scale(1.07); }
  /* the other end of the same gesture: the new row comes DOWN into the place
     it now owns, growing into it, rather than rising up into it against the
     four rows it is displacing. `.dreamin` still supplies the snap. */
  .git .commit.dreamin { transform:translateY(-10px) scale(.94); }
  /* content revealed by an unfold eases in on the same enter as .dreamin —
     which snaps, so the carrier only has to supply the transition back */
  .qreveal { transition:opacity .55s ease, filter .55s ease,
                        transform .55s ease; }
  @media (prefers-reduced-motion: reduce) { .qa { transition:none; } }
  .qa .qt { color:var(--lit); }
  /* No element catch-alls scoped inside `.qa`. There were two, and each one
     was a bug that took a human report to find:

     `.qa button` was #121 — left over from before `.qsend` and `.sgbtn` had
     styling of their own, still winning on specificity (0,1,1 beats 0,1,0)
     and so painting an opaque fill and a border onto buttons that had asked
     for neither. The mode switch had said `background:none` in its own rule
     since #103 and had never once rendered that way.

     `.qa textarea` was #139, the same shape one component over: it leaked
     `margin:.3rem 0` into `.qfield textarea`, insetting the box 5.8px inside
     the border it shares with a send button sitting flush at 1px — so the
     one object the field is meant to be had two different insets. Everything
     else it declared was already stated by `.qfield textarea` or made moot by
     the flex row, so deleting it was the whole fix.

     The rule, now that it has happened twice: a catch-all that outlives the
     components it stood in for does not announce itself, it quietly overrules
     them, and the component's own source reads correctly the whole time. DELETE
     it — out-specifying leaves the trap armed for the next component to render
     in here. */
  /* the three qaCard states (#105) are class modifiers on one card, so the
     shared parts are styled once and only the differences are stated here.
     awaiting: a quiet accent rail marks it apart from open questions; no
     input box, the answer shown plainly. folded: the loop has filed it, so
     it recedes. */
  /* awaiting-fold is waiting on the LOOP — the one genuinely in-progress
     thing on this page, and so the ONE deliberate exception to the opt-in
     motion rule (#113). It breathes: a wisp of accent drifting along the
     rail and across the label, slow and ambient like the shader, intensity
     fading in and OUT rather than sweeping on a loop. Never a spinner.
     The cost is bounded by construction rather than by measurement after
     the fact — an opacity breath on a 2px rail (compositor only) and a
     background drift across ~25 characters of .65rem label. */
  /* the rail sits INSIDE the padding box, not on a border hanging outside
     it, so that clipping the card while its height travels (travelCard)
     cannot shave the rail off */
  .qa.awaiting { position:relative;
    padding-left:.9rem; margin-left:-.9rem; opacity:.82; }
  .qa.awaiting::before { content:""; position:absolute; left:0;
    top:0; bottom:0; width:2px; pointer-events:none;
    background:linear-gradient(180deg, transparent, var(--accent) 16%,
      var(--accent) 84%, transparent);
    animation:qbreathe 5.5s ease-in-out infinite; }
  .qa.awaiting .qt::before { content:"✓ "; color:var(--accent); }
  /* one envelope, two places, same duration and easing, so the rail and the
     label read as one organism rather than two effects */
  @keyframes qbreathe { 0%,100% { opacity:.38; } 50% { opacity:1; } }
  @keyframes qwisp { 0%,100% { background-position:118% 50%; }
                     50% { background-position:-18% 50%; } }
  /* progressive enhancement: without background-clip the label is simply
     the dim label it has always been, never invisible text */
  @supports (background-clip:text) or (-webkit-background-clip:text) {
    .qa.awaiting .anstag {
      background-image:linear-gradient(100deg, var(--dim) 0%, var(--dim) 38%,
        var(--accent) 50%, var(--dim) 62%, var(--dim) 100%);
      background-size:260% 100%;
      -webkit-background-clip:text; background-clip:text;
      color:transparent;
      animation:qwisp 5.5s ease-in-out infinite; }
  }
  /* reduced motion holds the wisp STILL at its brightest instead of removing
     it: the state must still read as in-progress. Timing changes; function
     and legibility do not. */
  @media (prefers-reduced-motion: reduce) {
    .qa.awaiting::before { animation:none; opacity:1; }
    .qa.awaiting .anstag { animation:none; background-position:50% 50%; }
  }
  /* folded (#111): waiting on nobody, so it collapses and sits at the dim end
     of the ramp. NO accent — the accent is for live and actionable things and
     a settled entry is neither. The disclosure marker is the page's standing
     summary idiom, inherited rather than restated. */
  .qa.folded { margin:.15rem 0 .35rem; }
  .qa.folded .qt { color:var(--muted); font-weight:inherit; }
  .qa.folded .qt:hover { color:var(--lit); }
  .qa.folded .qfold > * { color:var(--dim); }
  .qa.folded .qfold > summary { color:var(--muted); }
  /* ...and when he opens one, the whole card steps up (#169): a settled entry
     he has just expanded is the thing he is reading, so its contents leave the
     dim end with it rather than the title brightening over unchanged prose.
     Still no accent — that is #111's line and expanding does not make an entry
     actionable, only prominent. */
  .qa.folded .qfold[open] > * { color:var(--muted); }
  .qa.folded .qfold[open] > summary { color:var(--lit); }
  .qwhen { color:var(--dimmer); margin-left:1ch; font-size:.7rem; }
  /* inline-block so the box hugs the words: the wisp is clipped to this
     text, so a full-column box would spread the drift across empty space
     and invalidate a full-width strip to say nothing */
  .anstag { color:var(--dim); text-transform:uppercase; letter-spacing:.07em;
    font-size:.65rem; margin:.35rem 0 .15rem; display:inline-block; }
  /* an answer is the human's, in a card whose body the loop wrote — so it
     reads at the same brightness as his notes do (#109) */
  .anstext { color:var(--lit); white-space:pre-wrap; }
  /* the questions channel's health (#136). Zero entries is the same NUMBER
     whether everything is answered or the reader cannot see the file, so the
     page has to say which — and the broken one has to look broken. It wears
     `--warn` and the rail idiom, which on this page marks one thing only:
     the page saying it cannot be trusted right now. Two things qualify —
     this, about the file it reads, and `.gserve.stale` (#140), about the
     code it runs. The quiet state (no file yet) is one dim line and no
     rail: a fresh target has not failed at anything. */
  .qhealth { margin:.3rem 0 .9rem; }
  .qhealth.unreadable { border-left:2px solid var(--warn); padding-left:.8rem; }
  .qhealth.unreadable .qhlabel { color:var(--warn); text-transform:uppercase;
    letter-spacing:.07em; font-size:.65rem; margin-bottom:.2rem; }
  .qhealth.unreadable .qhbody { color:var(--lit); }
  .qhealth.missing .qhbody { color:var(--dim); }
  .qh { color:var(--warn); }
  /* a send that did not land wears the same colour, because it is the same
     failure seen from the writing end: the channel to him did not work and
     nothing else on the page would have said so */
  .qerr { color:var(--warn); font-size:.7rem; margin-top:.35rem;
    max-width:56ch; }
  /* the status panel (#130): three facts and a fold, never a JSON dump.
     Colour is by SIGNIFICANCE, not by JSON type — the accent is spent on the
     one thing here that is waiting on HIM, and everything else rides the text
     ramp: what is happening brightest, what it serves under it, the liveness
     facts dim, the fold dimmer. */
  #status .stneed { border-left:2px solid var(--accent); padding-left:.8rem;
    margin:.2rem 0 .7rem; }
  #status .stneedhead { color:var(--accent); text-transform:uppercase;
    letter-spacing:.07em; font-size:.65rem; margin-bottom:.2rem; }
  #status .stneedrow { color:var(--lit); margin:.15rem 0; }
  #status .sttask { color:var(--bright); }
  #status .stgoal { color:var(--muted); margin:.1rem 0 .55rem; }
  #status .stagent { display:flex; gap:1.5ch; flex-wrap:wrap;
    margin:.2rem 0; }
  #status .stname { color:var(--lit); flex:none; }
  #status .stdoing { color:var(--muted); flex:1; min-width:24ch; }
  #status .stfacts { color:var(--dim); font-size:.7rem; margin:.6rem 0 .2rem; }
  /* non-breaking spaces: generated content renders flush against its
     neighbour otherwise, exactly as the crumb separator found */
  #status .stfacts span + span::before { content:"\\00a0·\\00a0";
    color:var(--dimmer); }
  #status .stfield { display:flex; gap:1ch; margin:.15rem 0;
    align-items:baseline; }
  /* a FIXED key column, not a minimum: the styleguide's "label the columns,
     not the gaps" applies to a key/value list too, and a long key on a
     min-width would shove that row's value out of line with every other
     row's. It wraps inside its own column instead. */
  #status .stfield > .stk { color:var(--dim); font-size:.7rem;
    flex:none; width:14ch; overflow-wrap:anywhere; }
  #status .stval { color:var(--muted); font-size:.75rem; }
  #status .stagentmore { margin:.35rem 0; }
  #status .stagentmore > .stk { color:var(--lit); font-size:.75rem; }
  /* follow-up thread + a quiet add-a-note box on every question entry */
  .thread { border-left:1px solid var(--line); padding-left:1ch;
    margin:.3rem 0 .2rem; }
  .follow { color:var(--muted); font-size:.75rem; margin:.25rem 0;
    padding-left:2.6ch; text-indent:-2.6ch; }
  .follow::before { content:"\\21b3  "; color:var(--dim); }
  /* authorship (#109): the human's words sit a step up the text ramp from
     the loop's, and each carries a dim label. Luminance, not accent. */
  .follow.human { color:var(--lit); }
  .who { color:var(--dim); text-transform:uppercase; letter-spacing:.08em;
    font-size:.62rem; margin-right:.7ch; }
  /* when it was written (#128). Quieter than the author label — the order is
     what carries the chronology, and the stamp is there to settle it. */
  .qts { color:var(--dimmer); font-size:.62rem; margin-right:.8ch; }
  /* the settled part of a thread collapses (#128): the resolution is the
     point of the card, and the discussion a resolution already answered is
     detail. Only that segment folds — see watch-design.md for why an
     unanswered question never hides its notes. */
  .qthread > summary { color:var(--dim); font-size:.7rem; cursor:pointer;
    letter-spacing:.03em; }
  .qthread > summary:hover { color:var(--muted); }
  /* open is one step up from wherever THIS surface sits closed (#169) */
  .qthread[open] > summary { color:var(--muted); }
  /* ONE input per card (#103, the human's words): the same field sends an
     answer or a note. The field and its send button share a single border
     and a single rounded box — the wrapper carries them and clips the
     button's corners — so they read as one object rather than a control
     placed next to a control. The mode group sits beneath. */
  .qcompose { margin:.45rem 0 .2rem; max-width:56ch; }
  .qfield { display:flex; align-items:stretch;
    background:var(--panel); border:1px solid var(--line);
    border-radius:var(--radius); overflow:hidden;
    transition:border-color .3s ease; }
  .qfield:focus-within { border-color:var(--border); }
  /* the box states everything about itself, because nothing above it does
     any more (#139). No margin: it fills the wrapper it shares a border with,
     exactly as the send button does. */
  .askform { margin:0 0 var(--space); max-width:56ch; }
  .askform textarea { display:block; box-sizing:border-box; width:100%; min-height:5rem;
    margin:.35rem 0; padding:.55rem; resize:vertical; color:var(--text);
    background:var(--panel); border:1px solid var(--line); border-radius:var(--radius);
    font:inherit; font-size:.75rem; outline:none; }
  .askform textarea:focus { border-color:var(--border); }
  .askform button { color:var(--lit); background:var(--panel2); border:1px solid var(--line);
    border-radius:var(--radius); padding:.35rem .7rem; font:inherit; cursor:pointer; }
  .aq { margin:.55rem 0 1rem; padding-left:.7rem; border-left:1px solid var(--line); }
  .aq.open { border-left-color:var(--accent);
    /* so removing the enter-snap .dreamin eases in rather than popping
       (#293 arrival). .dreamin's transition:none beats this while posed. */
    transition:opacity .55s ease, filter .55s ease,
               transform .55s cubic-bezier(.32,.1,.2,1); }
  /* Open title is the subject of the row — same luminance step as a
     question card's .qt (#293 makes the rule explicit so a future style
     catch-all cannot leave the words uncoloured). */
  .aq.open .qt { color:var(--lit); }
  .aqbody { color:var(--muted); margin-top:.25rem; }
  .aq > summary { color:var(--muted); cursor:pointer; }
  @media (prefers-reduced-motion:reduce) {
    .aq.open { transition:none; }
  }

  .qfield textarea { flex:1; min-width:0; background:none; border:0; margin:0;
    box-sizing:border-box; color:var(--text); font:inherit; font-size:.75rem;
    padding:.4rem .55rem; min-height:44px; resize:vertical; outline:none; }
  /* #273: send is a real control — min 44px touch/pointer target. Flex stretch
     already matches the field height; the floor stops a short single-line box
     from shrinking the button below the a11y floor (review dock and cards). */
  .qsend { flex:none; background:var(--panel2); color:var(--accent);
    border:0; border-left:1px solid var(--line); font:inherit;
    font-size:.7rem; padding:0 1rem; cursor:pointer;
    min-height:44px; min-block-size:44px;
    transition:background .3s ease, color .3s ease; }
  .qsend:hover { background:#26344a; }
  .qmodes { margin-top:.3rem; }
  .qmodes .sgbtn { padding:.2rem .5rem; font-size:.7rem; }
  #dreambg { position:fixed; inset:0; z-index:-1; width:100vw;
             height:100vh; }
  #devbox { position:fixed; top:.6rem; right:.8rem; z-index:10;
            color:var(--dimmer); font-size:.7rem; text-align:right; }
  #devbox canvas { display:block; margin-top:.25rem; opacity:.55; }
  #layerhint { position:fixed; bottom:1rem; right:1rem; z-index:10;
    color:var(--accent); background:rgba(17,24,39,.82);
    border:1px solid var(--line); border-radius:var(--radius);
    padding:.25rem .6rem; font-size:.7rem; opacity:0;
    transition:opacity .5s ease; pointer-events:none;
    letter-spacing:.04em; }
  /* single-document view swaps: the outgoing view liquifies into a
     swirling mist (SVG turbulence displacement + blur, enveloped per-frame
     in crossfade()) and drifts up as it fades; the incoming view coalesces
     from the same mist and settles perfectly crisp. Opacity + transform
     ride these CSS transitions; the mist (filter) is JS-driven so the
     middle of the dissolve lingers hazy. The shader stirs in sympathy. */
  /* The incoming view surfaces from BEHIND the outgoing ghost (z-index): it
     starts pushed back in depth (translateZ), lower and scaled down, at true
     opacity 0 — a delayed, slow-start opacity so it's genuinely absent for
     the first ~150ms, then rises as it drifts forward into focus. The ghost
     (in front) lifts up and toward the viewer as it dissolves. */
  #view { transition:opacity .8s cubic-bezier(.62,0,.34,1) .14s,
                     transform 1s cubic-bezier(.32,.1,.2,1);
          transform-origin:50% 40%; will-change:opacity, transform, filter; }
  /* the start state must SNAP (transition:none) — with the transition live,
     adding .enter would animate *toward* opacity 0 and get removed a frame
     later, so it never actually left ~1 (the old "pops in" bug). Snapping to
     0 + pushed-back, then removing .enter, gives a true fade-up from depth. */
  #view.enter { transition:none; opacity:0;
                transform:translateY(30px) translateZ(-110px) scale(.93); }
  /* the ghost is pinned to the box the outgoing view occupied (top/width/
     height set in crossfade), not stretched to the wrapper — the chrome now
     sits above #view, and a resizing column must not re-wrap the departing
     content while it is still opaque (#107). */
  .ghost { position:absolute; left:0; top:0; z-index:1; pointer-events:none;
           opacity:1; transform-origin:50% 40%;
           transition:opacity 1.05s cubic-bezier(.4,0,.66,.38),
                      transform 1.15s cubic-bezier(.34,0,.6,.4); }
  .ghost.out { opacity:0;
               transform:translateY(-34px) translateZ(70px) scale(1.07); }
  @media (prefers-reduced-motion: reduce) {
    #view, .ghost { transition:none; }
  }
  /* review view: the artifact fills the main column; the originating
     question docks beside it (sticky) so it can be answered with the
     review in front of you. Wider than the 72ch reading column. */
  body.review .wrap { max-width:1360px; }
  /* The column is the one thing on this page that changes SIZE, and the
     motion language says things that change travel rather than teleport
     (#107). So the width glides, on the dissolve's own easing and duration.
     Gated behind .wsliding, added only for a route change: a direct load of
     /review must arrive already wide, not animate its column on first paint.
     overflow-x is clipped for the same window because the departing ghost is
     pinned to its OLD width and would otherwise push a horizontal scrollbar
     while the column narrows underneath it. */
  body.wsliding .wrap { transition:max-width 1s cubic-bezier(.32,.1,.2,1); }
  body.wsliding { overflow-x:hidden; }
  @media (prefers-reduced-motion: reduce) {
    body.wsliding .wrap { transition:none; }
  }
  #reviewwrap { display:grid; gap:1.3rem; align-items:start; margin-top:1rem;
    grid-template-columns:minmax(0,1fr) minmax(24ch,34ch); }
  #reviewwrap.nodock { grid-template-columns:minmax(0,1fr); }
  #reviewframe { width:100%; height:74vh; border:1px solid var(--border);
    border-radius:var(--radius); background:var(--bg); display:block; }
  .revname { color:var(--dim); margin-left:.6rem; font-size:.8rem; }
  .qdock { position:sticky; top:1rem; will-change:transform, filter; }
  .qdock .label { margin-top:0; }
  @media (max-width:900px) {
    #reviewwrap { grid-template-columns:minmax(0,1fr); }
    .qdock { position:static; }
    #reviewframe { height:60vh; }
  }
  /* the composer: the + opener sits in the heading's left gutter; the
     panel it toggles drifts in through a soft blur (the dream language),
     not a hard pop. reduced-motion just shows/hides. */
  /* CENTRE, not baseline (#123). The opener is the tallest item in this row,
     so it defines the line's cross-size; under `baseline` the title was then
     hung from its own baseline near the top of that line and the button, at
     full line height, sat 3.1px lower through the middle. Centring both puts
     them on one centreline on every route — measured identically on /, on
     /questions and on /review — and it holds while the header TRAVELS,
     because it is a CSS invariant rather than something JS re-derives per
     frame. About 1px of residual is the font's own asymmetry (the box centre
     is not the ink centre) and is deliberately not chased: a magic nudge
     would be wrong the moment the mono stack falls back. */
  .htitlebar { display:flex; align-items:center; gap:.55rem; }
  .htitle { display:inline; }
  /* The opener hangs in the gutter LEFT of the reading column, so its offset
     is only affordable when the gutter exists. It does not on the review
     view's 1360px column, or in any narrow window — the button was sliced in
     half by the page edge (#108). So the pull is CLAMPED to the room that
     actually exists: it hangs out as far as it can, then locks; 0 parks it
     flush with the column, still inset by the body padding.

     `100%` is the containing block's width — .htitlebar's, which is the
     column's — so `(100vw - 100%)/2` IS the gutter, with no need to name the
     column's width (it is `ch`-sized, and `ch` would resolve against the
     button's own font rather than the column's). Doing this in CSS rather
     than JS is what makes the guarantee hold on every frame: the column
     GLIDES on a route change (#107), and a measure-then-write in rAF always
     paints one frame behind that. */
  #cmdplus { flex:none; align-self:center;
    margin-left:calc(-1 * clamp(0px, (100vw - 100%) / 2 - .6rem, 2.4rem));
    width:1.7rem; height:1.7rem; display:grid; place-items:center;
    background:transparent; color:var(--muted);
    border:1px solid var(--border); border-radius:var(--radius);
    font:inherit; font-size:1.15rem; line-height:1; cursor:pointer;
    transition:color .3s ease, border-color .3s ease, background .3s ease,
               transform .35s cubic-bezier(.32,.12,.2,1); }
  #cmdplus:hover, #cmdplus.on { color:var(--accent);
    border-color:var(--accent); background:rgba(99,102,241,.09); }
  #cmdplus.on { transform:rotate(45deg); }
  #cmdpalette { position:fixed; z-index:30; top:4rem; left:1rem;
    width:min(38ch,92vw); background:rgba(11,15,25,.94);
    border:1px solid var(--border); border-radius:8px; padding:1rem 1rem .85rem;
    box-shadow:0 14px 44px rgba(0,0,0,.5); backdrop-filter:blur(7px);
    visibility:hidden; opacity:0; transform:translateY(-8px) scale(.97);
    filter:blur(6px); pointer-events:none;
    transition:opacity .5s cubic-bezier(.32,.12,.2,1),
               transform .5s cubic-bezier(.32,.12,.2,1),
               filter .5s ease, visibility 0s linear .5s; }
  #cmdpalette.open { visibility:visible; opacity:1; transform:none;
    filter:none; pointer-events:auto; transition-delay:0s; }
  #cmdpalette .label { margin-top:0; }
  #cmdform textarea { width:100%; box-sizing:border-box;
    background:var(--panel); color:var(--text); border:1px solid var(--line);
    border-radius:var(--radius); font:inherit; padding:.4rem; margin:.3rem 0;
    min-height:3.4rem; resize:vertical; }
  /* command selection: a button group whose background indicator SLIDES to
     the active option. The one piece of crisp motion in the composer, kept
     soft (.3s, the dream easing). The selected label glows rather than
     changing metrics — a text effect that moved layout would resize the
     buttons and so move the target the indicator is chasing. */
  /* ONE sliding selection group, shared by the composer's command kinds and
     by every question card's answer/note switch (#103). Geometry and motion
     live here; each user styles only its own buttons. */
  .sgroup { position:relative; display:flex; flex-wrap:wrap; gap:.1rem; }
  /* The indicator is an OUTLINE that slides, not a filled chip (#121, his
     words: "have an outline but no bg color; they are currently opaque so
     you can't see the animation behind it"). It still marks the active
     option — the outline travels to it and its label glows accent — and the
     dreaming field now shows through the whole group. */
  .sgind { position:absolute; top:0; left:0; z-index:0; width:0; height:0;
    background:transparent; border:1px solid var(--border);
    border-radius:var(--radius); box-sizing:border-box;
    transition:transform .3s cubic-bezier(.32,.12,.2,1),
               width .3s cubic-bezier(.32,.12,.2,1),
               height .3s cubic-bezier(.32,.12,.2,1); }
  .sgind.snap { transition:none; }         /* land, never slide (see JS) */
  .sgbtn { position:relative; z-index:1; background:none; font:inherit;
    border:1px solid transparent; border-radius:var(--radius);
    color:var(--dim); cursor:pointer;
    transition:color .3s ease, text-shadow .3s ease; }
  .sgbtn:hover { color:var(--muted); }
  /* the selected label GLOWS rather than re-metricking: a text effect that
     changed layout would resize the button the indicator is chasing */
  .sgbtn.on { color:var(--accent);
    text-shadow:0 0 12px rgba(165,180,252,.45); }
  /* The tint picker (#143). It is the standing sliding group, so geometry
     and motion come for free and the ghost rule holds — an outline that
     travels, no fill anywhere, the dreaming field visible through every
     button. Two things are its own:

     Each label wears ITS OWN hue, because `teal` is a word until you can see
     it, and a row of identical dim words would make him click through six to
     find one. The swatch is on the TEXT, not a chip, which is the same
     restraint the group already asks for.

     And the selected one does NOT take `--accent` the way .sgbtn.on does —
     it takes its own colour, brightened. The accent means "live and
     actionable"; a settled preference is neither, and spending the accent
     here would be the fourth thing on the page wearing it. */
  .tintpick { margin:.2rem 0 .1rem; }
  .tintbtn { padding:.24rem .5rem; font-size:.7rem;
             color:color-mix(in oklab, var(--tintswatch) 55%, var(--dim)); }
  .tintbtn:hover { color:var(--tintswatch); }
  .tintbtn.on { color:var(--tintswatch);
    text-shadow:0 0 12px color-mix(in oklab, var(--tintswatch) 45%,
                                   transparent); }
  .tintmsg { color:var(--warn); font-size:.7rem; margin:.25rem 0 0; }
  /* ── what he has sent, from this browser (#165) ───────────────────────
     The row is the page's standing shape for a list of small facts — the
     commits panel's, one surface over: a fixed-height flex row, the identity
     on the left, the ticking age pinned right and tabular so the column does
     not jitter. Nothing here is a new component; only the middle column is.
     THE OUTCOME IS THE ONLY THING THAT TAKES COLOUR, because it is the only
     thing he cannot recover by looking somewhere else (#175). */
  .cmdhist { margin:.4rem 0 0; }
  .cmdhist > summary { color:var(--dim); font-size:.7rem; }
  .cmdhist[open] > summary { color:var(--muted); }   /* #169's per-surface step */
  /* capped and scrolled: the panel is fixed, so an uncapped list would grow
     off the bottom of the screen and take the send button with it */
  .cmdhistbody { max-height:11rem; overflow-y:auto; margin-top:.3rem; }
  .cmdhrow { display:flex; align-items:baseline; gap:.6ch;
             font-size:.7rem; line-height:1.5; color:var(--dim); }
  .cmdhkind { flex:0 0 auto; color:var(--dimmer); text-transform:uppercase;
              letter-spacing:.06em; }
  .cmdhtext { flex:1 1 auto; min-width:0; overflow:hidden;
              white-space:nowrap; text-overflow:ellipsis; color:var(--muted); }
  .cmdhage { flex:0 0 auto; margin-left:auto; color:var(--dimmer);
             font-variant-numeric:tabular-nums; }
  /* a send that did not land is the reason this list exists, so it is the one
     thing that leaves the dim end. --warn, not the accent: the accent marks
     what NEEDS him, and a failure from an hour ago is a fact, not an errand */
  .cmdhrow.bad .cmdhtext { color:var(--warn); }
  .cmdhwhy { flex:0 0 auto; color:var(--warn); }
  .cmdhrow.pending .cmdhtext { font-style:italic; }
  /* the honest footer: this is one browser's memory, not the project's */
  .cmdhnote { color:var(--dimmer); font-size:.65rem; margin-top:.4rem; }
  .tintmsg:empty { display:none; }
  .cmdkinds { margin:.3rem 0 .1rem; }
  .cmdkind { padding:.28rem .45rem; }
  /* Hover discoverability: the row carries the common kinds, and the ⋯ icon
     reveals EVERY command with a one-line description — so a rarely-used kind
     is discoverable rather than hidden knowledge. Rendered from COMMANDS at
     any length, so plugin-contributed kinds (#86) just appear. */
  .cmdpick { display:flex; align-items:flex-start; gap:.1rem; }
  .cmdmore { position:relative; display:inline-flex; align-items:center; }
  .cmdmorebtn { background:none; border:1px solid transparent; font:inherit;
    color:var(--dimmer); padding:.28rem .5rem; cursor:pointer; line-height:1;
    border-radius:var(--radius); transition:color .3s ease; }
  .cmdmore:hover .cmdmorebtn, .cmdmore:focus-within .cmdmorebtn {
    color:var(--accent); }
  /* no gap between icon and menu: the pointer must be able to travel from one
     to the other without ever leaving .cmdmore, or the menu closes en route */
  .cmdmenu { position:absolute; z-index:31; top:100%; left:0;
    width:max(32ch,100%); padding:.3rem;
    background:rgba(11,15,25,.97); border:1px solid var(--border);
    border-radius:8px; box-shadow:0 14px 44px rgba(0,0,0,.55);
    backdrop-filter:blur(7px);
    visibility:hidden; opacity:0; transform:translateY(-6px);
    filter:blur(5px); pointer-events:none;
    transition:opacity .34s cubic-bezier(.32,.12,.2,1),
               transform .34s cubic-bezier(.32,.12,.2,1),
               filter .34s ease, visibility 0s linear .34s; }
  .cmdmore:hover .cmdmenu, .cmdmore:focus-within .cmdmenu {
    visibility:visible; opacity:1; transform:none; filter:none;
    pointer-events:auto; transition-delay:0s; }
  .cmdmenuitem { display:block; width:100%; box-sizing:border-box;
    text-align:left; background:none; border:1px solid transparent;
    border-radius:var(--radius); font:inherit; color:var(--muted);
    padding:.3rem .45rem; cursor:pointer;
    transition:background .25s ease, color .25s ease; }
  .cmdmenuitem:hover, .cmdmenuitem:focus-visible {
    background:var(--panel2); color:var(--lit); }
  .cmdmenuitem.on .cmk { color:var(--accent); }
  .cmdmenuitem .cmd { display:block; color:var(--dim); font-size:.7rem;
    margin-top:.1rem; }
  /* which plugin answers a command (#86), on the item that offers it. The
     QUIETEST step of the ramp — the same --dimmer as the history's ages and
     its footer — because this is provenance, not an errand: he needs it when
     a command is unfamiliar or has stopped working, and never otherwise. It
     floats right so it costs the label no room and no wrapping, which is the
     failure #162 is about one row over. */
  .cmdmenuitem .cmpl { float:right; color:var(--dimmer); font-size:.65rem;
    margin-left:.75rem; }
  /* An arriving item eases in on `.qreveal`, and it needs this rule to do it.
     `.cmdmenuitem` declares a transition of its own at the SAME specificity
     and LATER in this sheet, so it wins and `.qreveal` silently supplies no
     transition at all — which is #154 exactly, one component over: the class
     is added, the element is already at opacity 1, and nothing ever fades.
     Restating both here is the fix that does not depend on source order (the
     invariant `.dreamin` states in its own comment), and it keeps the hover
     colours transitioning while the item is still on its way in. */
  .cmdmenuitem.qreveal { transition:opacity .55s ease, filter .55s ease,
    transform .55s ease, background .25s ease, color .25s ease; }
  .cmdrow { display:flex; gap:.5rem; align-items:center; margin-top:.2rem; }
  .cmdrow button { background:var(--panel2); color:var(--accent);
    border:1px solid var(--border); border-radius:var(--radius); font:inherit;
    padding:.25rem .8rem; cursor:pointer; }
  #cmdpop { margin-left:auto; color:var(--muted); }
  #cmdpop:hover { color:var(--accent); }
  .pipbtn { background:none; border:none; color:var(--dim); cursor:pointer;
    padding:0 .35rem; line-height:1; vertical-align:middle;
    transition:color .3s ease; }
  .pipbtn:hover, .pipbtn:focus-visible { color:var(--accent); }
  .pipbtn svg { display:inline-block; vertical-align:-2px; }
  /* the composer's status arrives and departs on one atmospheric envelope
     (#255). Success remains readable for the hold while the panel stays open;
     the panel's own courtesy-close is separate (~1.5s, #291). Reduced motion
     keeps timing but snaps both visual states. */
  .cmdmsg { color:var(--dim); font-size:.7rem; min-height:1em; margin-top:.5rem;
    transition:color .4s ease, opacity .35s ease, filter .35s ease,
               transform .35s cubic-bezier(.32,.1,.2,1); }
  .cmdmsg.depart { opacity:0; filter:blur(7px); transform:translateY(-5px); }
  /* no reserved slack under the buttons: the status line only takes room
     once it has something to say, and the panel grows downward to meet it
     (nothing above it moves). */
  .cmdmsg:empty { display:none; }
  .cmdmsg.ok { color:var(--accent); }
  /* dream ripple: a soft ring expanding from a received command / answer */
  .ripple { position:fixed; z-index:40; border-radius:50%; pointer-events:none;
    border:1px solid var(--accent); }
  @media (prefers-reduced-motion: reduce) {
    #cmdplus, #cmdpalette, #layerhint, .sgind, .sgbtn, .cmdmenu,
    .cmdmenuitem, .cmdmenuitem.qreveal, .cmdmorebtn,
    .cmdmsg { transition:none; }
  }
</style>"""

APP_BODY = """<canvas id="dreambg"></canvas>
<svg id="dreamfx" width="0" height="0" aria-hidden="true"
     style="position:absolute;width:0;height:0;pointer-events:none">
 <filter id="dissolveOut" x="-25%" y="-25%" width="150%" height="150%"
         color-interpolation-filters="sRGB">
  <feTurbulence type="fractalNoise" baseFrequency="0.009" numOctaves="1"
                seed="7" result="n"/>
  <feDisplacementMap in="SourceGraphic" in2="n" scale="0"
                     xChannelSelector="R" yChannelSelector="G" result="d"/>
  <feGaussianBlur in="d" stdDeviation="0"/>
 </filter>
 <filter id="dissolveIn" x="-25%" y="-25%" width="150%" height="150%"
         color-interpolation-filters="sRGB">
  <feTurbulence type="fractalNoise" baseFrequency="0.009" numOctaves="1"
                seed="7" result="n"/>
  <feDisplacementMap in="SourceGraphic" in2="n" scale="0"
                     xChannelSelector="R" yChannelSelector="G" result="d"/>
  <feGaussianBlur in="d" stdDeviation="0"/>
 </filter>
</svg>
<div class="wrap">
<div id="chrome">
 <header class="htitlebar"><button id="cmdplus" type="button"
   title="command the dream" aria-label="open command palette">+</button>
  <span class="htitle"></span></header>
 <div id="meta"></div>
</div>
<div id="view">loading…</div>
<div id="cmdpalette" role="dialog" aria-label="command palette">
 <form id="cmdform" autocomplete="off">
  <div class="label">command the dream</div>
  <div class="cmdpick">
   <div class="sgroup cmdkinds" id="cmdkinds" role="radiogroup"
        aria-label="command"></div>
   <div class="cmdmore" id="cmdmore">
    <button type="button" class="cmdmorebtn" aria-haspopup="menu"
            aria-expanded="false" aria-label="all commands">&#8943;</button>
    <div class="cmdmenu" id="cmdmenu" role="menu"></div>
   </div>
  </div>
  <textarea id="cmdtext" placeholder="a thought for the dream…"></textarea>
  <div class="cmdrow">
   <button type="submit" id="cmdsend">send</button>
   <button type="button" id="cmdpop"
           title="pop out — stays while you navigate"><svg viewBox="0 0 22 18"
     width="13" height="11" aria-hidden="true"><rect x="1" y="1" width="20"
     height="16" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.6"
     /><rect x="10.5" y="8.5" width="9" height="7" rx="1.2"
     fill="currentColor"/></svg> pop out</button>
  </div>
  <div class="cmdmsg" id="cmdmsg" aria-live="polite"></div>
 </form>
 <!-- what he has sent, from this browser (#165). A disclosure rather than a
      standing list: the composer is for the next thought, and the last one is
      only sometimes the question. -->
 <details class="cmdhist" id="cmdhist">
  <summary id="cmdhistsum">history</summary>
  <div class="cmdhistbody" id="cmdhistbody"></div>
 </details>
</div>"""

COMPONENTS_JS = """
window.DEV=/*DEV*/false;
const esc = t => { const d = document.createElement('div');
                   d.textContent = t ?? ''; return d.innerHTML; };
const ageStr = mt => {
  let s = Math.max(0, Date.now()/1000 - mt);
  for (const [u, div] of [["d",86400],["h",3600],["m",60]])
    if (s >= div) return `${Math.floor(s/div)}${u}`;
  return `${Math.floor(s)}s`;
};
/* the same age at commit resolution (#132): TWO units, each zero-padded to
   two digits — `05m 23s`, `02h 14m`, `03d 07h`.

   Two edges, both decided rather than fallen into:
     · under a minute it still reads as two units (`00m 12s`), so the column
       never changes width — and seconds-old is exactly when he is watching.
     · past 100 days the DAY count widens and the second unit stays at two.
       The shape is "two units", not "four characters"; a truncated day count
       would be a wrong number rather than a narrow one. */
const p2 = n => String(n).padStart(2, '0');
const AGE_PAIRS = [["d",86400,"h",3600], ["h",3600,"m",60], ["m",60,"s",1]];
const agePair = ct => {
  const s = Math.max(0, Math.floor(Date.now()/1000 - ct));
  for (const [bu, bd, su, sd] of AGE_PAIRS)
    if (s >= bd)
      return `${p2(Math.floor(s/bd))}${bu} ${p2(Math.floor((s % bd)/sd))}${su}`;
  return `00m ${p2(s)}s`;
};
/* components: every section on every watch page renders through these */
const label = t => `<div class="label">${t}</div>`;
/* a small standard picture-in-picture glyph — a low-emphasis button placed
   after doc/review affordances so pop-out is discoverable, never surprising.
   Clicking it floats the target (data-pipurl) in an identity-headed window. */
const PIP_SVG = '<svg viewBox="0 0 22 18" width="14" height="12"' +
  ' aria-hidden="true"><rect x="1" y="1" width="20" height="16" rx="2.5"' +
  ' fill="none" stroke="currentColor" stroke-width="1.6"/>' +
  '<rect x="10.5" y="8.5" width="9" height="7" rx="1.2"' +
  ' fill="currentColor"/></svg>';
const pipBtn = (url, label) =>
  `<button class="pipbtn" type="button" title="pop out — floats while you` +
  ` navigate" aria-label="pop out ${esc(label)}" data-pipurl="${esc(url)}"` +
  ` data-piplabel="${esc(label)}">${PIP_SVG}</button>`;
const expand = (s, inner, cls='') =>
  `<details><summary class="${cls}">${s}</summary>${inner}</details>`;
/* Backticked references become links only when the destination is known.
   `github.com/…` is an external URL; target files come from the collector's
   closed set. Everything else stays code — a broken link is a false promise. */
const linkify = h => h.replace(
  /`([\\w.-]+(?:\\/[\\w.-]+)+\\/?|[\\w-]+\\.[\\w]{1,8})`/g,
  (m, p) => {
    if (p.startsWith('github.com/'))
      return '`<a href="https://' + p + '">' + p + '</a>`';
    if (data && Array.isArray(data.linkable_paths) &&
        data.linkable_paths.includes(p))
      return '`<a href="/file?p=' + encodeURIComponent(p) + '">' + p + '</a>`';
    return m;
  });
const preB = t => `<pre>${linkify(esc(t))}</pre>`;
/* a backticked path to a review artifact docks THIS question onto the
   review page (carries its title); every other path stays a /file link. */
const linkifyReview = (escaped, title) => escaped.replace(
  /`\\.dreamwork\\/review\\/([\\w.-]+\\.html?)`/g,
  (m, name) => '`<a class="rev" href="/review?p=' + encodeURIComponent(name) +
    '&q=' + encodeURIComponent(title) + '">.dreamwork/review/' + name +
    '</a>`');
/* ── rendered prose (#102, #158) ──────────────────────────────────────────
   The loop writes its files hard-wrapped at ~72 columns. A <pre> renders
   those breaks literally and the browser re-wraps them again at a narrower
   reading column, so every paragraph breaks twice into a ragged mess. So we
   join the wraps back into paragraphs and let the column do the wrapping.

   The line this draws: MARKDOWN PROSE REFLOWS, RAW TEXT DOES NOT — by WHAT
   the text is, not who composed it (#158). Question bodies, answers,
   follow-ups, dreams, dashboard .md peeks, and `/file` for .md-like paths
   reflow through mdB. Source code and other files at `/file` stay verbatim
   in a <pre>. JSON is neither (#178). Status and git have their own components.

   Four things must survive the join, because each one carries meaning a
   joined line would destroy:
     · a blank line is a paragraph break
     · a leading `- ` is a real list item and its INDENT is its nesting —
       questions.md's whole parser rests on a sub-bullet never looking like
       an entry, and flattening the marker would render the two identically
     · a ``` fence is code, and code is not prose
     · a `#` heading stands alone
   Every other line break is a wrap, and gets joined with a space. */
const MD_BULLET = /^(\\s*)[-*]\\s+(.*)$/;
function mdBlocks(text) {
  const out = [];
  let cur = null, fence = null;
  const flush = () => { if (cur) { out.push(cur); cur = null; } };
  for (const line of String(text == null ? '' : text).split('\\n')) {
    if (/^\\s*```/.test(line)) {                 // fence open or close
      if (fence) { out.push({ kind:'fence', text: fence.join('\\n') }); fence = null; }
      else { flush(); fence = []; }
      continue;
    }
    if (fence) { fence.push(line); continue; }
    if (!line.trim()) { flush(); continue; }      // blank line ends a block
    if (/^\\s*#{1,6}\\s/.test(line)) {
      flush(); out.push({ kind:'h', text: line.replace(/^\\s*#+\\s*/, '') }); continue;
    }
    const m = line.match(MD_BULLET);
    if (m) { flush(); cur = { kind:'li', indent:m[1].length, text:m[2] }; continue; }
    if (cur) { cur.text += ' ' + line.trim(); continue; }   // a wrap: join it
    cur = { kind:'p', indent:0, text: line.trim() };
  }
  flush();
  if (fence) out.push({ kind:'fence', text: fence.join('\\n') });
  return out;
}
/* Nesting is the RANK of a bullet's indent among the indents actually used,
   not the raw column count: a question body carries the source file's own
   2-space indent, so absolute columns would push every sub-bullet one level
   too deep. Rank is invariant to whatever base indent the text arrived with. */
function mdRender(text, inline) {
  const blocks = mdBlocks(text);
  const levels = [...new Set(blocks.filter(b => b.kind === 'li')
    .map(b => b.indent))].sort((a, b) => a - b);
  return blocks.map(b =>
    b.kind === 'fence' ? `<pre class="mdcode">${esc(b.text)}</pre>` :
    b.kind === 'h' ? `<div class="mdh">${inline(b.text)}</div>` :
    b.kind === 'li' ? `<div class="mdli" style="--lvl:${levels.indexOf(b.indent)}">` +
                      `${inline(b.text)}</div>`
                    : `<p>${inline(b.text)}</p>`).join('');
}
/* Inline markdown the loop actually writes: **bold**, *em*, `code`. Bold is
   rendered as LUMINANCE — the page already says "more important" with its
   text ramp, and a mono bold would change metrics to say no more. Order is
   load-bearing: the linkifiers inject <a> INSIDE the backticks, so code
   spans convert after them and swallow the link; ** before * so a bold pair
   is never read as two emphases. */
const mdSpans = h => h
  .replace(/`([^`]+)`/g, '<code>$1</code>')
  .replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>')
  .replace(/(^|[\\s(\\[])\\*([^*\\s][^*]*?)\\*(?=$|[\\s.,;:)\\]])/g, '$1<em>$2</em>');
const mdInline = t => mdSpans(linkify(esc(t)));
const mdInlineReview = title => t =>
  mdSpans(linkify(linkifyReview(esc(t), title)));
const mdB = t => `<div class="md">${mdRender(t, mdInline)}</div>`;
const mdBReview = (t, title) =>
  `<div class="md">${mdRender(t, mdInlineReview(title))}</div>`;
/* a follow-up thread and a quiet add-a-note box, carried by every question
   entry in every state. */
/* Authorship is visible wherever the human's words sit beside the loop's
   (#109). A note carries who wrote it, and the page says so QUIETLY: a dim
   uppercase label — the same idiom as every other label here — and the
   human's words a step brighter on the text ramp, because emphasis on this
   page is luminance. No accent: the accent is for live and actionable
   things, and a note is neither. An unattributed note (an unknown tag) gets
   no label at all — a wrong attribution is worse than an absent one. */
const WHO = { human: 'you', loop: 'loop' };
/* WHEN a contribution was written. On a thread that is not decoration: a note
   written before an answer must not read as a reply to it (#128), and position
   says which came first only to a reader who already trusts the order. Absent
   when the tag carried no stamp — never invented, the same rule as the author
   label above. */
const stamp = w => w ? `<span class="qts">${esc(w)}</span>` : '';
const followRow = f => {
  const a = f && f.author, txt = f && f.text != null ? f.text : f;
  return `<div class="follow${a ? ' ' + a : ''}">` +
    (WHO[a] ? `<span class="who">${WHO[a]}</span>` : '') +
    stamp(f && f.when) + `${mdInline(txt)}</div>`;
};
/* A settled thread COLLAPSES (#128; his words: "if we have a thread of notes
   like that, they should be collapsed but also expandable"). `fold` is passed
   only for the segment that precedes a resolution — see `qaThread` — and the
   threshold is two because one note is not a thread: hiding a single line
   behind a click costs more than it saves, and his own reported entry had
   exactly one.

   The notes live in a `.threadin` wrapper rather than directly in the
   disclosure, so the thing that arrives or leaves when it toggles is ONE node
   with its own rect — which is what `cardBody` reveals and what the collapse
   ghosts. */
const QTHREAD_FOLD_AT = 2;
const followThread = (follows, fold) => {
  if (!follows || !follows.length) return '';
  const inner = `<div class="threadin">` + follows.map(followRow).join('') +
                `</div>`;
  if (!fold || follows.length < QTHREAD_FOLD_AT)
    return `<div class="thread">${inner}</div>`;
  const last = follows[follows.length - 1];
  return `<div class="thread"><details class="qthread">` +
    `<summary>${follows.length} earlier notes` +
    (last && last.when
      ? `<span class="qwhen">up to ${esc(last.when)}</span>` : '') +
    `</summary>${inner}</details></div>`;
};
/* ── the sliding selection group ──────────────────────────────────────────
   One indicator that slides to the active option, shared by the composer's
   command kinds and by every question card's answer/note switch (#103).
   Three rules, learned in the composer and true for any user of it:

   - **Land, don't slide, on first paint and on reflow** (`snap`). The
     indicator starts 0-wide at the group's origin, so animating from there
     reads as a glitch rather than a choice — the enter-snap rule. Add
     `.snap` (transition:none), set the geometry, force a reflow, remove it.
   - **Size to the active BUTTON, never to the group.** The row wraps once a
     vocabulary outgrows one line, and a height:100% indicator would span
     every line at once.
   - **The selected label glows, it does not re-metric** (CSS): a text effect
     that changed layout would resize the very target being chased.
   - **Measure in LAYOUT space, never in visual space** (#198). The indicator
     is a sibling of the buttons, so what it needs is where they sit in the
     group — and `getBoundingClientRect` answers a different question: where
     they appear on screen, ancestor transforms included. `openCmd` paints the
     indicator on the same frame it reveals the panel, and the panel reveals
     THROUGH a transform (`translateY(-8px) scale(.97)` -> none over .5s), so
     every rect read there came back 3% small. Measured: the indicator landed
     4.5px left of the button it marks and 1.9px narrow, and stayed there —
     it looked self-correcting only because the next live tick re-renders the
     view, and `setContent` re-paints every group at rest.

     Same family as #170 and #160: a transformed ancestor silently redefines
     what a "position" means for everything measured beneath it. */
function slideIndicator(group, snap) {
  if (!group) return;
  const ind = group.querySelector(':scope > .sgind');
  const btn = group.querySelector(':scope > .sgbtn.on');
  if (!ind || !btn) return;
  const g = group.getBoundingClientRect(), b = btn.getBoundingClientRect();
  if (!b.width) return;                  // not laid out yet; nothing to chase
  // The scale the group is being drawn at RIGHT NOW, read from the one
  // element whose layout width we can also ask for directly. Dividing it out
  // turns the rects back into layout values, and it is exactly 1 — a no-op
  // to the sub-pixel — everywhere no ancestor is mid-transform, which is
  // every question card and the composer once it has settled.
  const s = group.offsetWidth ? g.width / group.offsetWidth : 1;
  if (!s) return;
  if (snap || rmr) ind.classList.add('snap');
  ind.style.width = (b.width / s) + 'px';
  ind.style.height = (b.height / s) + 'px';
  ind.style.transform = 'translate(' + ((b.left - g.left) / s) + 'px,' +
                        ((b.top - g.top) / s) + 'px)';
  if (snap && !rmr) {
    void ind.offsetWidth;                // reflow so the landing is not a slide
    ind.classList.remove('snap');
  }
}
/* every group that exists right now lands its indicator — called after any
   render, and on resize, since a wrapped row moves its buttons */
const paintIndicators = snap =>
  document.querySelectorAll('.sgroup').forEach(g => slideIndicator(g, snap));
/* ── the card's one input (#103) ──────────────────────────────────────────
   The human's words: "use same text input for answer and note. below text
   input, have a button group choose between [ Answer | Add Note ]. on the
   RHS of the text field, integrate a 'send' button that sits flush with the
   text field so they appear to be one thing."

   The mode picks the endpoint. Only modes the entry's state can actually
   accept are offered — /answer appends into the Open section, so a folded
   entry is note-only and the group does not render at all rather than
   offering a choice that would fail. A card that already has an answer
   defaults to note: answering again is an amendment, not the obvious act. */
const QMODES = { answer: 'answer', note: 'add note' };
const qaModesFor = st => st === 'folded' ? ['note'] : ['answer', 'note'];
const qaDefaultMode = st => st === 'open' ? 'answer' : 'note';
const QPLACE = { answer: 'answer…', note: 'add a note…' };
/* #273: accessible name tracks mode + target. Placeholder alone is not a
   name; the dock especially needs which question is being answered. */
const qaFieldLabel = (mode, title) => {
  const act = mode === 'note' ? 'add a note on' : 'answer';
  const t = String(title || '').replace(/\\s+/g, ' ').trim();
  const short = t.length > 90 ? t.slice(0, 87) + '…' : t;
  return short ? `${act} ${short}` : (mode === 'note' ? 'add a note' : 'answer');
};
const qaSendLabel = mode => mode === 'note' ? 'send note' : 'send answer';
const qaCompose = (key, st, title) => {
  const modes = qaModesFor(st), mode = qaDefaultMode(st);
  const group = modes.length < 2 ? '' :
    `<div class="sgroup qmodes" role="radiogroup"` +
    ` aria-label="answer or add a note" data-modes="${key}">` +
    `<div class="sgind"></div>` +
    modes.map(m => `<button type="button" role="radio" data-mode="${m}"` +
      ` class="sgbtn qmode${m === mode ? ' on' : ''}"` +
      ` aria-checked="${m === mode ? 'true' : 'false'}">${QMODES[m]}</button>`
    ).join('') + `</div>`;
  return `<div class="qcompose" data-mode="${mode}">` +
    `<div class="qfield">` +
    `<textarea id="qi${key}" placeholder="${QPLACE[mode]}"` +
    ` aria-label="${esc(qaFieldLabel(mode, title))}"></textarea>` +
    `<button type="button" class="qsend"` +
    ` aria-label="${esc(qaSendLabel(mode))}"` +
    ` onclick="submitCard('${key}')">send</button></div>` +
    group + `</div>`;
};
/* THE THREAD, SPLIT AROUND ITS RESOLUTION (#128).
   The answer is lifted out of the sub-bullets so the card can show it as the
   resolution — and the lift used to discard where it sat among the notes, so a
   note written two hours EARLIER rendered underneath it and read as a reply to
   it ("the first thing that showed up was like me replying to me?"). The
   parser now records `answer_at`, and the thread is cut there: the discussion
   that led to the resolution sits above it, an amendment sits below.

   Only the part above collapses. That is the card's own axis — who is the
   entry waiting on — applied one level down: discussion that a resolution has
   already answered is settled, and everything else on a question card is
   still live. So an unanswered question never hides its notes (they are the
   human's own steers), and a note he adds now lands in the segment below the
   answer, which is never folded away under him. */
const qaThread = q => {
  const f = (q && q.follows) || [];
  // No resolution ⇒ NOTHING is settled. Defaulting the cut to the end of the
  // list instead was the obvious-looking arithmetic and it swept every note of
  // every open question into the folding half — the guard caught it, which is
  // what a rule written as a rule is for.
  const at = (q && q.answer && q.answer_at != null) ? q.answer_at : 0;
  return [f.slice(0, at), f.slice(at)];
};
/* THE question component (#105). Every question on every surface —
   dashboard, /questions, the review dock, and the answer-submit morph —
   renders through this one card, so a change to how a question looks is one
   edit rather than a hunt.

   Contract: `qaCard(q, key)`. The key ADDRESSES the entry in live `data`:
   'o'+index into `questions_open`, 'a'+index into `answered_entries`. It is
   never a title round-tripped through the DOM, so a stale render cannot
   write to the wrong entry. The state is DERIVED from the key and the entry,
   never passed in, so no caller can render an entry in a state its own data
   contradicts:
     open     — needs the human; shows an answer box
     awaiting — answered from the page, the loop hasn't folded it yet; the
                answer on a quiet accent rail with a ✓, no box, so it never
                reads as still-open
     folded   — key is 'a…'; the loop has folded it into `## Answered`
   `qaInner` is split out so the submit morph can restate a live card in its
   new state in place instead of assembling look-alike markup. */
const qaState = (q, key) =>
  key[0] === 'a' ? 'folded' : (q.answer ? 'awaiting' : 'open');
/* The one structural difference between the states (#111). A folded entry is
   waiting on NOBODY, so it collapses — through the page's existing `expand`
   idiom, `<details>`/`<summary>`, marker and all. Its title line BECOMES the
   summary rather than sitting beside one, so `.qt` still names the question
   line in every state and every rule written against it keeps applying.
   Collapsed it still says which question and when it was answered, because a
   settled entry that cannot be found again has simply been hidden. */
const qaInner = (q, key) => {
  const st = qaState(q, key);
  const body = q.body && q.body.trim() ? mdBReview(q.body.trim(), q.title) : '';
  const [settled, since] = qaThread(q);
  /* An answer is his words as much as a note is, so it says so in the same
     vocabulary (#109, #128 part b): of two things he wrote, it must not be
     that only one is attributed. The author comes from the tag, so an answer
     tag nobody recognises gets no label rather than a guessed one. */
  const answer = st === 'awaiting'
    ? `<div class="anstag">answered · awaiting fold</div>` +
      `<div class="anstext">` +
      (WHO[q.answer_by] ? `<span class="who">${WHO[q.answer_by]}</span>` : '') +
      stamp(q.answer_when) + `${mdInline(q.answer)}</div>` : '';
  const foot = followThread(settled, true) + answer +
               followThread(since, false) + qaCompose(key, st, q.title);
  if (st === 'folded')
    return `<details class="qfold"><summary class="qt">${esc(q.title)}` +
      (q.when ? `<span class="qwhen">answered ${esc(q.when)}</span>` : '') +
      `</summary>${body}${foot}</details>`;
  return `<div class="qt">${esc(q.title)}</div>${body}${foot}`;
};
/* Two identities, deliberately. `data-qkey` ADDRESSES the entry in live data
   and is positional, so it is what writes use. `data-qid` is the question
   ITSELF, and it survives the entry moving between sections — which its key
   cannot, since answering re-indexes it from questions_open into
   answered_entries. The regroup animation keys off qid: it is the same
   question, so it travels rather than being re-set (#77). URI-encoded
   because a title may contain quotes and this is an attribute. */
const qaCard = (q, key) =>
  `<div class="qa ${qaState(q, key)}" data-qkey="${key}"` +
  ` data-qid="${encodeURIComponent(q.title)}">${qaInner(q, key)}</div>`;
/* Resolve the logical question a LIVE CARD names, never merely the position it
   occupied when rendered (#266). A review route does not rebuild its dock on
   the data tick, so its `o<n>` can become stale while questions_open re-sorts.
   `data-qid` is the title identity the card already uses to survive regrouping;
   writes resolve that identity against fresh data. The positional fallback is
   only for callers with no live card, and fails closed when neither matches. */
const qaEntry = (key, card) => {
  if (!data || !key) return null;
  const list = key[0] === 'a' ? data.answered_entries : data.questions_open;
  const qid = card && card.dataset.qid;
  if (qid) {
    let title = null;
    try { title = decodeURIComponent(qid); } catch (e) { return null; }
    return (list || []).find(entry => entry.title === title) || null;
  }
  return (list || [])[+key.slice(1)] || null;
};
/* the page he was on when he sent it (#126). The query string is kept because
   WHICH artifact he was reading is usually the point. Every write path sends
   it; the server puts it in brackets in the events log, where it reads as a
   hint and not as an instruction. */
const fromPath = () => location.pathname + location.search;
/* Both POSTs RETURN their response, and both callers check it (#136). They
   did not, and the consequence was the worst shape available: a write that
   failed still ran the submit morph, so the card restated itself as answered,
   his text was cleared, and two seconds later the live tick quietly put the
   question back with no explanation anywhere. A file the reader cannot see is
   a file `/answer` cannot write to, so the read-side fault and the write-side
   "no match" are the same failure and want the same surfacing. */
/* ── every submission, as the CLIENT saw it (#175) ────────────────────────
   #199 gave the SERVER a verbatim record of everything it received. This is
   the other witness, and it exists for the case that one cannot cover: a
   submission the server never accepted, or never even heard. A 409 from
   `append_answer` (#136), a rejection he clicked past (#162), a POST that
   never left because the server was restarting — in every one of those, the
   client is the only party that knows what he tried to do.

   SO THE RECOVERY-CRITICAL FIELD IS THE OUTCOME, NOT THE TEXT. The text he
   can usually still see; what is unrecoverable an hour later is whether the
   thing he typed actually landed. A record is written BEFORE the request, as
   `pending`, and the outcome is attached when the response comes back — so a
   tab that dies mid-POST leaves a record saying exactly that, which is the
   true state and not a guess.

   PARTITIONED BY A DATABASE PER PROJECT, not by a field inside one database.
   A `project` column needs every reader to remember to filter by it, and a
   reader that forgets returns another loop's submissions while looking
   perfectly correct — the silent shape this page keeps closing. A separate
   database cannot leak by omission.

   NOTHING HERE MAY DELAY OR BREAK A SEND. Every failure resolves to null, and
   the write is raced against a short timeout: a wedged IndexedDB (a blocked
   upgrade, a storage-disabled origin) must cost him a few milliseconds, never
   a command. A missing record is a bad outcome; a command he could not send
   because of the logger is a worse one.

   IT MUST BE READABLE OR IT IS THEATRE. `#165` is the surface; until then, and
   for anyone debugging afterwards, `window.__dwSubmissions()` resolves to
   every record for the current project. */
const SUBS_STORE = 'subs';
const subsDbName = () => {
  const t = (typeof data !== 'undefined' && data && data.target) || '';
  return t ? 'dw-submissions:' + t : '';
};
function subsOpen() {
  return new Promise(res => {
    const name = subsDbName();
    if (!name || typeof indexedDB === 'undefined' || !indexedDB) return res(null);
    let rq;
    try { rq = indexedDB.open(name, 1); } catch (e) { return res(null); }
    rq.onupgradeneeded = () => {
      const db = rq.result;
      if (!db.objectStoreNames.contains(SUBS_STORE))
        db.createObjectStore(SUBS_STORE, { keyPath:'id', autoIncrement:true });
    };
    rq.onsuccess = () => res(rq.result);
    rq.onerror = rq.onblocked = () => res(null);
  });
}
/* one transaction, always closed, never throwing at the caller */
function subsTx(mode, fn) {
  return subsOpen().then(db => new Promise(res => {
    if (!db) return res(null);
    let out = null;
    const done = v => { try { db.close(); } catch (e) {} res(v); };
    try {
      const tx = db.transaction(SUBS_STORE, mode);
      const rq = fn(tx.objectStore(SUBS_STORE));
      if (rq) rq.onsuccess = () => { out = rq.result; };
      tx.oncomplete = () => done(out);
      tx.onerror = tx.onabort = () => done(null);
    } catch (e) { done(null); }
  })).catch(() => null);
}
/* what KIND of act each endpoint is, in his terms rather than the protocol's.
   An unknown path still records, with the body kept whole — a new POST route
   is logged the day it is added, without anyone remembering this table. */
const SUB_ACT = {
  '/ask':     b => ({ kind:'ask',    title:b.question, text:b.question }),
  '/answer':  b => ({ kind:'answer', title:b.question, text:b.answer }),
  '/comment': b => ({ kind:'note',   title:b.question, text:b.comment }),
  '/command': b => ({ kind:b.kind,   title:null,       text:b.text }),
};
const subFields = (url, b) => (SUB_ACT[url] ||
  (x => ({ kind:url, title:null, text:JSON.stringify(x) })))(b || {});
const SUBS_WAIT_MS = 250;
const subsRecord = (url, body) => Promise.race([
  subsTx('readwrite', st => st.add(Object.assign(
    { at: Date.now(), path: url, from: (body || {}).from || null,
      outcome: 'pending', status: 0 }, subFields(url, body)))),
  new Promise(r => setTimeout(() => r(null), SUBS_WAIT_MS)),
]);
function subsOutcome(id, outcome, status) {
  if (id == null) return;
  subsTx('readwrite', st => {
    const g = st.get(id);
    g.onsuccess = () => {
      const r = g.result;
      // never rewritten except to attach the outcome it was waiting for, and
      // never deleted: an entry that stays `pending` is a true statement about
      // a tab that died mid-send, not a gap to be tidied away
      if (r) { r.outcome = outcome; r.status = status; st.put(r); }
    };
    return null;
  });
}
const subsAll = () => subsTx('readonly', st => st.getAll());
window.__dwSubmissions = subsAll;
/* THE ONE SEAM every submission goes through, which is what makes the record
   complete rather than well-intentioned — the same reason #199 persists from
   `do_POST` rather than from four handlers. */
const postJSON = async (url, body) => {
  const id = await subsRecord(url, body);
  let res = null;
  try { res = await fetch(url, { method:'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(body) }); } catch (e) { res = null; }
  subsOutcome(id, res ? (res.ok ? 'ok' : 'rejected') : 'unreachable',
              res ? res.status : 0);
  return res;
};
const postAnswer = (title, text) =>
  postJSON('/answer', { question: title, answer: text, from: fromPath() });
const postAsk = text =>
  postJSON('/ask', { question: text, from: fromPath() });
const postComment = (title, note, section) =>
  postJSON('/comment',
           { question: title, comment: note, section, from: fromPath() });
/* Why a send did not land, in his terms. The status alone ("rejected (409)")
   names the protocol and not the problem. */
const QSEND_WHY = {
  404: 'there is no .dreamwork/questions.md to write to',
  409: 'this entry is not in .dreamwork/questions.md any more — it may have ' +
       'been folded, renamed, or the file may have stopped being readable',
  0:   'the page could not reach the server',
};
function qaFail(card, status) {
  const comp = card && card.querySelector('.qcompose');
  if (!comp) return;
  let m = comp.querySelector('.qerr');
  if (!m) { m = document.createElement('div'); m.className = 'qerr';
            comp.appendChild(m); }
  // his words stay in the box: the send failed, so the text is the only copy
  m.textContent = `not written (${status}) — ` +
    (QSEND_WHY[status] || 'the server refused it') +
    '. what you typed is still here.';
}
"""

VIEWS_JS = """
/* view builders: each returns the inner HTML of #view for one route.
   The dashboard/questions views are data-driven (re-rendered live on
   mtime change); the file view is a static read. */
function dreamBlock(d) {
  return expand(
    `${esc(d.name)}<span class="age" data-mt="${d.mtime}"></span>`,
    mdB(d.content));
}
/* ── the questions channel's health (#136) ────────────────────────────────
   "Nothing needs you" and "the loop's channel to you is broken" produce the
   same number, and for one morning they produced the same page: a dashboard
   reading zero open questions over a file holding six. So the count is not
   allowed to be the only thing that speaks — `questions_health` says WHICH
   zero this is, and only the broken one is loud.

   The calm states render nothing at all. That is deliberate and it is the
   half that keeps this check alive: a fresh target seeds an empty
   questions.md by design, and a page that greeted every new target with a
   warning would train him to ignore the one that matters. Absence of a
   message IS the all-clear, exactly as it was before. */
/* what the empty list SAYS is a claim about the file, so it is keyed on
   whether the file could be read at all. "none — all answered" was made
   unconditionally, which is the sentence that lied for a whole morning. */
const QNONE = { ok: 'none — all answered', empty: 'none — all answered',
                missing: 'none yet',
                unreadable: 'none that this page can read' };
const QHEALTH = {
  // the path is NOT backticked here: linkify would turn it into a /file link
  // to a file that does not exist, and an affordance that leads nowhere is a
  // small lie of its own on the one panel about lying.
  missing: { label: '',
    body: 'no .dreamwork/questions.md yet — the loop writes one the first ' +
          'time it needs you.' },
  unreadable: { label: 'questions unreadable',
    body: '`.dreamwork/questions.md` has content and this page can see no ' +
          'entries in it. anything the loop has asked you is sitting in that ' +
          'file, invisible here, while this page says none. an entry is a ' +
          'top-level bullet with a bold title, under a literal `## Open`.' },
};
function qHealth(d) {
  const c = QHEALTH[d && d.questions_health];
  if (!c) return '';
  const src = (d.files || {})['questions.md'];
  const n = src ? src.split('\\n').length : 0;
  return `<div class="qhealth ${d.questions_health}">` +
    (c.label ? `<div class="qhlabel">${esc(c.label)}` +
       (n ? ` · ${n} lines, 0 entries` : '') + `</div>` : '') +
    `<div class="qhbody">${mdInline(c.body)}</div></div>`;
}
/* ── the status section (#130) ────────────────────────────────────────────
   His words: "on main dashboard page for a dreamworker, the status section
   shows json. It should render that json nicely, using colors effectively,
   and making good use of space, and cutting out or hiding bulk or boring
   stuff."

   This panel is how he checks the loop at a glance, and a glance is three
   questions: what is happening, who is doing it, and does anything need him.
   Everything else in status.json is there so an AGENT can resume — which
   makes it load-bearing rather than junk, so it is folded and never dropped.

   **Nothing is dropped, only demoted.** status.json is a schema rather than a
   fixed shape and the loop keeps adding keys to it (it grew by half at 10:44
   the day this was written, which is what made the dump unreadable). A
   renderer that showed a known list would silently hide the next thing the
   loop learned to say, so the fold takes whatever is LEFT rather than a
   second list — a new key costs a click, not a disappearance.

   **Colour by significance, never by JSON type.** Tinting strings, numbers
   and booleans is the obvious move and the wrong one: it makes the panel
   louder without making any of it easier to read, and it spends the page's
   one accent on `true`. The accent goes to `awaiting_human` and nowhere else
   here, because it is the only thing on this panel waiting on HIM — the same
   axis the question card's three states run on. Everything else is the text
   ramp: what is happening is brightest, what it is for sits under it, the
   liveness facts are dim, the fold is dimmer. */
function stLines(v) {
  if (v == null) return [];
  if (Array.isArray(v)) return v.flatMap(stLines);
  if (typeof v === 'object')
    return Object.entries(v).map(([k, x]) =>
      `${k.replace(/_/g, ' ')}: ${stLines(x).join(', ')}`);
  return [String(v)];
}
const stField = (k, v) =>
  `<div class="stfield"><span class="stk">${esc(k.replace(/_/g, ' '))}</span>` +
  `<span class="stvals">` +
  stLines(v).map(l => `<div class="stval">${mdInline(l)}</div>`).join('') +
  `</span></div>`;
const ST_GLANCE = ['awaiting_human', 'task', 'goal', 'agents', 'queue',
                   'last_tick', 'last_commit'];
const ST_AGENT_GLANCE = ['name', 'in_flight'];
function statusBlock(s) {
  if (!s || typeof s !== 'object') return '';
  const arr = v => Array.isArray(v) ? v : (v == null ? [] : [v]);
  const agents = arr(s.agents).filter(a => a && typeof a === 'object');
  let h = `<div id="status">` + label('status');
  // 1. does anything need HIM. First, and the one accented thing here.
  const need = arr(s.awaiting_human);
  if (need.length)
    h += `<div class="stneed">` +
      `<div class="stneedhead">${need.length} awaiting you</div>` +
      need.map(x => `<div class="stneedrow">${mdInline(String(x))}</div>`)
          .join('') + `</div>`;
  // 2. what is happening, and what it is for
  if (s.task) h += `<div class="sttask">${mdInline(String(s.task))}</div>`;
  if (s.goal) h += `<div class="stgoal">${mdInline(String(s.goal))}</div>`;
  // 3. who is doing it — a name and the one line that says what they are on
  if (agents.length)
    h += agents.map(a =>
      `<div class="stagent"><span class="stname">${esc(String(a.name || '?'))}` +
      `</span><span class="stdoing">${mdInline(String(a.in_flight || '—'))}` +
      `</span></div>`).join('');
  // 4. liveness: the small facts that say the loop is still running. The tick
  //    is rendered through the page's live-age idiom rather than as a
  //    timestamp — a dashboard whose thesis is liveness should say "2m old",
  //    and it should keep counting while he watches it.
  const facts = [];
  if (s.queue) facts.push(esc(`${s.queue.in_progress || 0} in flight · ` +
                              `${s.queue.pending || 0} pending`));
  const t = s.last_tick ? Date.parse(s.last_tick) : NaN;
  // no space before the span: `.age` carries its own left margin, and a
  // literal one on top of it reads as a typo.
  // The gate is on the FIELD, not on the parse: `if (t)` is falsy for NaN, so
  // the verbatim fallback this line documents had never once run and an
  // unparseable last_tick rendered nothing at all — #154's shape exactly (a
  // documented behaviour nobody measured). Guarded now in identity.mjs.
  if (s.last_tick)
    facts.push(isNaN(t) ? esc(String(s.last_tick))
                        : `tick<span class="age" data-mt="${t / 1000}"></span>`);
  if (s.last_commit) facts.push(esc(String(s.last_commit)));
  if (facts.length)
    h += `<div class="stfacts">` +
         facts.map(f => `<span>${f}</span>`).join('') + `</div>`;
  // 5. the rest — folded, because an agent resumes from it and he does not
  //    read it. Whatever is LEFT, not a second known list.
  const rest = Object.keys(s).filter(k => !ST_GLANCE.includes(k));
  const deep = agents.filter(a =>
    Object.keys(a).some(k => !ST_AGENT_GLANCE.includes(k)));
  if (rest.length || deep.length)
    h += expand(`the rest (${rest.length + deep.length})`,
      deep.map(a => `<div class="stagentmore">` +
        `<div class="stk">${esc(String(a.name || '?'))}</div>` +
        Object.keys(a).filter(k => !ST_AGENT_GLANCE.includes(k))
          .map(k => stField(k, a[k])).join('') + `</div>`).join('') +
      rest.map(k => stField(k, s[k])).join(''), 'dim');
  return h + `</div>`;
}
/* ── the dashboard's questions section folds (#141) ───────────────────────
   His words: "on the dashboard, the questions section should be collapsed by
   default and show how many questions there are left to answer. it should be
   grayed out and disabeld when that number is zero."

   THE COUNT IS `open_questions`, the server's, and there is deliberately no
   second way to arrive at it — the crumb badge he glances at from every route
   reads that same field, and two counts that can disagree is how a page
   starts lying about the one number he checks.

   DISABLED MEANS "NOTHING HERE NEEDS YOU", NOT "YOU MAY NOT LOOK". At zero
   the summary drops to the dim end of the ramp and loses the accent — and the
   disclosure still opens. Refusing to open would be a claim about permission,
   where zero is a claim about need.

   AND IT IS KEYED ON HEALTH, NOT ON THE COUNT (#136). An unreadable
   questions.md produces a zero too, and a calm grey "nothing to answer" two
   lines under that file's amber warning would be the page contradicting
   itself. The grey is for a genuine zero; every other zero keeps the live
   treatment and lets the warning above it speak.

   THE WHOLE SECTION FOLDS, awaiting-fold cards included. The summary names
   what is inside, so a collapsed panel never hides the fact that something is
   in flight.

   AND IT TRAVELS (#196). This comment used to argue the opposite — that the
   fold was a standalone `expand`, instant like the `.md` peeks, because
   "nothing that MOVES sits below the toggle". That was simply false about
   this page: reviews, files, status and the tint picker all sit below it, and
   the section swings by ~1250px, so the one gesture licensed to snap was the
   largest displacement on the dashboard. His report, verbatim: the questions
   "just appear and disappear". The fold now goes through `travelCard` and the
   page's departure/arrival idioms like every other disclosure — see the
   `.qsec > summary` handler. */
const qSummary = d => {
  const n = d.open_questions || 0;
  const fold = d.questions_open.filter(q => q.answer).length;
  const calm = !n && (d.questions_health === 'empty' ||
                      d.questions_health === 'ok');
  return `<summary class="qseclabel${calm ? ' none' : ''}">questions` +
    (n ? ` · <span class="qsecn">${n} to answer</span>`
       : ` · nothing to answer`) +
    (fold ? ` · ${fold} awaiting fold` : '') + `</summary>`;
};
function qSection(d) {
  const qo = d.questions_open.map((q, i) => [q, i]);
  const openQ = qo.filter(([q]) => !q.answer);
  const foldQ = qo.filter(([q]) => q.answer);
  let inner = '';
  if (openQ.length)
    inner += label('answer questions') +
             openQ.map(([q, i]) => qaCard(q, 'o' + i)).join('');
  if (foldQ.length)
    inner += label('answered · awaiting fold') +
             foldQ.map(([q, i]) => qaCard(q, 'o' + i)).join('');
  if (!inner)
    inner = `<div class="dim">${QNONE[d.questions_health] || QNONE.ok}</div>`;
  return `<details class="qsec" data-keep="qsec">` + qSummary(d) + inner +
         `</details>`;
}
/* what "a commit happened" means, as one comparable value (#151). The whole
   sequence, not just the head: a rebase or an amend can change the panel
   without changing its top row. */
const gitKey = d => ((d && d.git) || []).map(c => c.sha).join(' ');
/* one commit row (#132). Two things about it are load-bearing rather than
   presentational:
     · `data-sha` is the row's IDENTITY, so a re-render can tell which rows
       survived it — the same job `data-qid` does for a question card.
     · the age is an EMPTY node carrying `data-ct`. Nothing server-rendered
       ever states the age, because it is stale the second after it is
       written; `ages()` fills it and keeps filling it (see below). */
/* what this page is RUNNING, said out loud (#140). One line, directly under
   the `commits` label, because the answer is only meaningful beside the list
   of commits it is behind.

   IT IS NEVER SILENT, and that is the one place this deliberately differs
   from the hub's version of the same line. dreamhub says nothing on a healthy
   row because it has N rows and a line on every healthy one hides the
   unhealthy one; here there is one page, and a silent healthy state is
   indistinguishable from no check at all — which is the failure this whole
   page is organised against. So the quiet states are quiet (dim, one short
   line) and only a genuinely wrong state is loud.

   The states, the vocabulary and the missing-commit list are `deployed.py`'s,
   value for value (#147), so hovering this line and reading the hub row give
   the same answer in the same words. Detail is ranked, never withheld: the
   summary is the line and the individual missing commits are its title. */
const SERVE_TEXT = {
  current: s => `serving ${esc(s.rev || '?')}`,
  // "watch.py commits", not "commits", and the extra word is load-bearing
  // HERE in a way it is not on the hub: this line sits directly above a list
  // of ALL of the project's commits, where "3 commits behind" would read as a
  // claim about those rows. HEAD can move thirty times without watch.py
  // moving once.
  behind: s => `this page is ${s.missing.length} watch.py commit` +
    `${s.missing.length === 1 ? '' : 's'} behind · serving ${esc(s.rev || '?')}`,
  untracked: () => 'this page is serving code that is in no commit — ' +
    'started from an uncommitted tree',
};
function servingLine(d) {
  const s = (d && d.deployed) || null;
  if (!s || !s.state) return '';
  const missing = s.missing || [];
  const say = SERVE_TEXT[s.state];
  // a state this page has never heard of is still a reading: say the state
  // rather than rendering nothing, which is what "no match" looked like
  if (!say)
    return `<div class="gserve unknown" title="${esc(s.note || '')}">` +
           `serving — unknown · ${esc(s.note || s.state)}</div>`;
  const loud = s.state !== 'current';
  const title = missing.length
    ? ` title="${esc(missing.map(([h, sub]) => `${h}  ${sub}`).join('\\n'))}"`
    : '';
  return `<div class="gserve${loud ? ' stale' : ''}"${title}>` +
         `${say({ ...s, missing })}</div>`;
}
/* what a row holds when he opens it (#166). The subject is a LABEL for the
   reasoning; the body is the reasoning, and in this repo it is the most
   useful text in the log — the row shows sixty ellipsised characters of it.

   Through `mdB`, which reflows (#102): a commit body is hard-wrapped at ~72
   columns by every tool that writes one, and rendered verbatim in a wider
   column it reads as a poem. It is prose the loop wrote, so it takes the
   prose renderer, exactly as `.md` files do.

   THE FILES ARE PLAIN TEXT, NOT LINKS, and that is a decision rather than an
   omission: a path from an old commit may not exist now, and #157 is open
   precisely because a link that 404s promises something. When #157 lands
   these become links by resolving first, not by being linkified now.

   Both empty cases say so. "(no message body)" and "(no files)" are one line
   each and they are the difference between "this commit had nothing more to
   tell you" and "this page could not read it" — which is #136's rule, one
   panel over. */
const gitDetail = c => `<div class="gdetail">` +
  `<div class="gmeta">${esc(c.full || c.sha)} · ${esc(c.who || 'unknown')}` +
  `</div>` +
  ((c.body || '').trim() ? mdB(c.body)
    : `<div class="gnone">(no message body — the subject is all of it)</div>`) +
  ((c.files || []).length
    ? `<div class="gfiles">` +
      c.files.map(f => `<span class="gfile">${esc(f)}</span>`).join('') +
      (c.more ? `<span class="gfile gmore">+${c.more} more</span>` : '') +
      `</div>`
    : `<div class="gnone">(no files — an empty or merge commit)</div>`) +
  `</div>`;
/* ...and the row IS the disclosure (#166). `<details>` rather than a div
   with a class, so it inherits the page's whole disclosure vocabulary at
   once: `summary::before`'s +/- affordance, #169's air and luminance step,
   `data-keep`'s survival across the tick, and the shared expand handler's
   motion. `data-sha` stays the row's identity for `GIT_LIST`; `data-keep`
   is a SECOND key because they answer different questions — one addresses
   the row inside its list, the other addresses what he opened across a
   re-render, and a commit row is the first element on this page to need
   both at once. */
const gitRow = c => `<details class="commit${
    c.subject.includes('dreamwork(maintain:') ? ' maint' : ''}"` +
  ` data-sha="${esc(c.sha)}" data-keep="commit:${esc(c.sha)}">` +
  `<summary class="grow"><span class="gsha">${esc(c.sha)}</span>` +
  `<span class="gsub">${esc(c.subject)}</span>` +
  `<span class="age cage" data-ct="${c.t}"></span></summary>` +
  gitDetail(c) + `</details>`;
/* ── the burndown (#142) ──────────────────────────────────────────────────
   Two tracks over one set of columns, because the open count alone cannot
   tell "he steers fast" from "the work is slow" — those are the same curve.

     the LEVEL   how many tasks were open in that bucket. This is the
                 burndown, and on this project it has gone up all day.
     the FLOW    arrivals above a hairline, completions below it. Direction
                 is the primary distinction and it needs no colour; the two
                 sit one step apart on the text ramp only so the eye can
                 tell them apart when a column is one pixel tall.

   NO VELOCITY SCORE, deliberately. A rate computed over a day of a loop
   that has been alive for a day is a claim about the future dressed as a
   measurement, and the page would then be believed about it.

   THE ACCENT IS NOT SPENT HERE. Nothing in this panel is waiting on him —
   it is context, not an errand — and the accent's one job on this page is
   marking what needs him. Same rule the status panel follows (#130). */
const BURN_SERIES = [['open', 'bdlevel'], ['arrived', 'bdup'],
                     ['landed', 'bddown']];
const burnKey = d => ((d && d.burndown && d.burndown.buckets) || [])
  .map(b => `${b.t0}:${b.arrived}:${b.landed}:${b.open}`).join(' ');
const BURN_STEP_NAME = { 3600: 'hourly', 14400: 'every four hours',
                         86400: 'daily', 604800: 'weekly',
                         2419200: 'every four weeks' };
/* a bucket's label. Hourly buckets want a clock; daily and wider want a
   date, because "00:00" five times in a row is not a time axis. */
const bstamp = (t, step) => {
  const d = new Date(t * 1000);
  return step >= 86400
    ? d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    : d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
};
const bdbar = (b, k, cls, max) =>
  `<div class="bdbar ${cls}" data-bk="${b.t0}" data-series="${k}"` +
  ` style="height:${max ? Math.round((b[k] / max) * 100) : 0}%"></div>`;
function burnPanel(d) {
  const s = (d && d.burndown) || null;
  if (!s || !s.state) return '';
  // the "cannot chart it" states live INSIDE `.bd` too, so the panel has one
  // address in every state. A reader that has to ask "is it missing or is it
  // empty" is the failure this whole page is organised against, and it
  // applies to the page's own checks as much as to him.
  if (s.state !== 'ok')
    return label('burndown') + `<div class="bd">` +
      `<div class="bdnone">${esc(s.note || s.state)}</div></div>`;
  const bs = s.buckets || [];
  const flowMax = Math.max(1, ...bs.map(b => Math.max(b.arrived, b.landed)));
  const levelMax = Math.max(1, ...bs.map(b => b.open));
  const col = b =>
    `<div class="bdcol" title="${esc(bstamp(b.t0, s.step))} · ${b.arrived} arrived · ` +
    `${b.landed} landed · ${b.open} open">`;
  // The head states the three totals it is a picture of, so a chart too
  // small to read is still a fact. `open` is the CURRENT count and it comes
  // from the same walk the columns do, not from a second reading.
  let h = label('burndown') + `<div class="bd">` +
    `<div class="bdhead"><span class="bdnum">${s.open}</span> open · ` +
    `${s.arrived} arrived · ${s.landed} landed · ` +
    `${BURN_STEP_NAME[s.step] || 'bucketed'} · sourced ${s.marked}/${s.entries}` +
    `</div>` +
    `<div class="bdtrack bdnet">` +
      bs.map(b => col(b) + bdbar(b, 'open', 'bdlevel', levelMax) + `</div>`)
        .join('') + `</div>` +
    `<div class="bdtrack bdflow">` +
      bs.map(b => col(b) +
        `<div class="bdhalf bdtop">${bdbar(b, 'arrived', 'bdup', flowMax)}</div>` +
        `<div class="bdrule"></div>` +
        `<div class="bdhalf bdbot">${bdbar(b, 'landed', 'bddown', flowMax)}</div>` +
        `</div>`).join('') + `</div>` +
    `<div class="bdaxis"><span>${esc(bstamp(s.from, s.step))}</span>` +
      `<span>arrivals above · landed below</span>` +
      `<span>${esc(bstamp(s.to, s.step))}</span></div>`;
  /* WHAT IT CANNOT SAY, said out loud. The most telling split would be
     human- against loop-initiated, and the ledger cannot support it: the
     `**human` stamp is on a MINORITY of entries, so a chart drawn from it
     would be mostly one bar wide and would be read as fact. Reporting the
     coverage is the honest version, and it is also the thing that would
     make someone add the field.

     THE COUNTS LIVE IN THE HEAD AND THE PROSE HERE IS CONSTANT, which is
     not a phrasing preference: this text wraps, and "0 of 4" becoming
     "0 of 14" pushed it onto a fourth line and grew the panel by 14px — so
     a bar easing over 850ms sat above four panels that had already jumped.
     Measured, by the guard, on the first version of this panel. The head is
     one ellipsised line for the same reason a commit row is (#151). */
  h += `<div class="bdnote">most entries do not record where they came from` +
       ` — see the count above — so this cannot split his steers from the` +
       ` loop's own ideas, only count them together</div>`;
  return h + `</div>`;
}
function buildDashboard(d) {
  let h = `<div id="sections">`;
  // a fault first (it is one line, and usually absent), then what the loop has
  // just DONE — "near the top of dreamworker dashboard should be the most
  // recent 5 commits" (human, 2026-07-25, #151). Nothing else changed order.
  h += qHealth(d);
  h += label('commits') + servingLine(d) + `<div class="git">` +
       d.git.map(gitRow).join('') + `</div>`;
  h += label(`dreams (${d.dreams.length})`) +
       (d.dreams.map(dreamBlock).join('') || '<div class="dim">none active</div>') +
       (d.dreams_archive.length
         ? expand(`archive (${d.dreams_archive.length})`,
                  d.dreams_archive.map(dreamBlock).join(''), 'dim') : '');
  h += qSection(d);
  h += `<div class="dim"><a href="/answers">questions for the dreamer · ${d.answers_open.length} open</a></div>`;
  if (d.reviews.length) {
    h += label('reviews') + d.reviews.map(r =>
      `<div data-review="${esc(r.name)}"><a href="/review?p=${encodeURIComponent(r.name)}">${esc(r.name)}</a>` +
      pipBtn('/reviewraw?p=' + encodeURIComponent(r.name), r.name) +
      `<span class="age" data-mt="${r.mtime}"></span></div>`).join('');
  }
  h += label('files') +
       ['DREAMWORK.md','questions.md','lessons.md'].map(n =>
         expand(n, mdB(d.files[n]))).join('');
  // ...then how the work itself is going (#142). Below the questions and the
  // reviews on purpose: the top of this page is what NEEDS him — a fault,
  // what just happened, what he must answer — and the burndown is context
  // rather than an errand. Above `status` because both are about the loop
  // and this one is the longer view of it.
  h += burnPanel(d);
  h += statusBlock(d.status);
  h += tintPicker(d);      // last, and dim: a preference, not status
  return h + `</div>`;
}
function buildQuestions(d) {
  // three explicit states: open (needs the human), answered-awaiting-fold
  // (the loop's to fold), and the folded Answered section — all three the
  // same qaCard, grouped by the state it derives from the key + entry.
  const qo = d.questions_open.map((q, i) => [q, i]);
  const openQ = qo.filter(([q]) => !q.answer);
  const foldQ = qo.filter(([q]) => q.answer);
  let h = `<div id="qsections">` + qHealth(d);
  h += label(`open (${openQ.length})`) +
       (openQ.map(([q, i]) => qaCard(q, 'o' + i)).join('') ||
        `<div class="dim">${QNONE[d.questions_health] || QNONE.ok}</div>`);
  if (foldQ.length)
    h += label(`answered · awaiting fold (${foldQ.length})`) +
         foldQ.map(([q, i]) => qaCard(q, 'o' + i)).join('');
  h += label('answered') + (d.answered_entries.length
    ? d.answered_entries.map((e, j) => qaCard(e, 'a' + j)).join('')
    : '<div class="dim">(none yet)</div>');
  return h + `</div>`;
}
function answerRecord(e, answered=false) {
  const body = `<div class="aqbody">${mdB(e.body)}</div>`;
  // #238/#247: content-stable aid from the server backs both list identity and
  // data-keep so open rides snapshotFolds (re-open only). Missing aid must
  // fail CLOSED: omit both data-aid and data-keep so empty keys cannot collide
  // folds or FLIP, and never emit a shared sentinel like ans:missing.
  if (answered) {
    if (!e.aid) {
      return `<details class="aq answered"><summary>${esc(e.title)}</summary>` +
        `${body}</details>`;
    }
    const id = esc(e.aid);
    return `<details class="aq answered" data-aid="${id}" data-keep="${id}">` +
      `<summary>${esc(e.title)}</summary>${body}</details>`;
  }
  // Open records must NOT bake a permanent `.dreamin` into the HTML (#293):
  // that class is only the enter-snap start pose. New open rows receive a
  // one-shot arrival in revealNewOpenAsks() after setContent (start pose +
  // rAF remove). Hard refresh / first paint of existing rows stays fully
  // visible — no stuck pose. Identity is server `aid` (title+body+ordinal),
  // never title alone — exact-title distinct-body twins must both arrive.
  if (!e.aid) {
    return `<article class="aq open"><div class="qt">${esc(e.title)}</div>` +
      `<div class="label">you asked · awaiting dreamer</div>${body}</article>`;
  }
  return `<article class="aq open" data-aqid="${esc(e.aid)}">` +
    `<div class="qt">${esc(e.title)}</div>` +
    `<div class="label">you asked · awaiting dreamer</div>${body}</article>`;
}
function buildAnswers(d) {
  let h = d.answers_health === 'unreadable'
    ? `<div class="qhealth"><span>answers channel unreadable</span> · <a href="/file?p=.dreamwork%2Fanswers.md">.dreamwork/answers.md</a></div>` : '';
  h += `<form id="askform" class="askform"><label class="label" for="askbox">ask the dreamer</label>` +
    `<textarea id="askbox" placeholder="A question for the dreamer"></textarea>` +
    `<div><button type="submit">Ask</button> <span id="askmsg" class="dim" aria-live="polite"></span></div></form>`;
  h += label(`open (${d.answers_open.length})`) +
    (d.answers_open.map(e => answerRecord(e)).join('') || `<div class="dim">none awaiting the dreamer</div>`);
  h += label(`answered (${d.answers_answered.length})`) +
    (d.answers_answered.map(e => answerRecord(e, true)).join('') || `<div class="dim">none yet</div>`);
  return `<div id="answersections">${h}</div>`;
}
/* /answers ask: one in-flight attempt at a time (#292).
   · While a POST is pending, further submit/Ctrl+Enter is a no-op (does not
     queue a second request with the same bytes).
   · askFlightGen: a response applies only if it still owns the generation.
   · Failure keeps his words; only a matching successful generation clears.
   · Leaving /answers (navigate away) is surface destruction: invalidateAskFlight
     bumps generation and clears the in-flight flag so a rebuilt form is not
     blocked, and a late old response cannot clear/status/tick the new surface.
   · Tick re-renders while still on /answers do NOT invalidate — same surface. */
let askFlightGen = 0, askInFlight = false;
function invalidateAskFlight() {
  askFlightGen++;
  askInFlight = false;
}
async function sendAsk(form) {
  if (askInFlight) return;
  const box = form.querySelector('#askbox'), msg = form.querySelector('#askmsg');
  if (!box) return;
  const words = box.value.trim(); if (!words) return;
  askInFlight = true;
  const mine = ++askFlightGen;
  let res = null;
  if (msg) msg.textContent = 'asking…';
  try { res = await postAsk(words); } catch (e) {}
  // Superseded or surface destroyed — do not touch a newer flight's flag.
  if (mine !== askFlightGen) return;
  askInFlight = false;
  // Re-query: navigate may have replaced the form; never mutate a new surface
  // with an old attempt's outcome, and never tick unless still on /answers.
  if (view.name !== 'answers') return;
  const liveBox = document.getElementById('askbox');
  const liveMsg = document.getElementById('askmsg');
  if (!liveBox) return;
  if (res && res.ok) {
    liveBox.value = '';
    if (liveMsg) liveMsg.textContent = 'asked';
    await tick();
  } else if (liveMsg) {
    liveMsg.textContent = res
      ? 'question was refused — your words are kept'
      : 'dreamwork is unreachable — your words are kept';
  }
}
/* #158: reflow by file kind, never by content sniff. A .py with a `#`
   comment must stay pre; a research .md must reflow. Path from the query
   is the only signal — same extensions a human means by ".md or similar". */
function isMarkdownFile(p) {
  const s = String(p || '').toLowerCase();
  return s.endsWith('.md') || s.endsWith('.markdown') || s.endsWith('.mdx');
}
function buildFile(param, text) {
  if (text == null)
    return '<div id="filebody"><div class="dim">not found</div></div>';
  const body = isMarkdownFile(param) ? mdB(text) : `<pre>${esc(text)}</pre>`;
  return `<div id="filebody">${body}</div>`;
}
/* review view: the raw artifact in an iframe (style-isolated) with the
   originating question docked beside it (answer box included), so it can
   be answered with the review in front of you. Deep-loads without a
   question just show the artifact. */
function buildReview(name, q, d) {
  const src = '/reviewraw?p=' + encodeURIComponent(name || '');
  let dock = '';
  if (q && d) {
    const i = d.questions_open.findIndex(x => x.title === q);
    if (i >= 0)
      dock = `<aside class="qdock" id="qdock">` +
        label('answering') + qaCard(d.questions_open[i], 'o' + i) + `</aside>`;
  }
  return `<div id="reviewwrap"${dock ? '' : ' class="nodock"'}>` +
      `<div id="reviewdoc"><iframe id="reviewframe" src="${src}" ` +
      `title="review artifact" loading="lazy"></iframe></div>` +
      dock +
    `</div>`;
}
/* every number on this page that can drift without a disk change is written
   HERE, once a second, as TEXT into nodes that already exist — never through
   a re-render. That was already the shape; #132 is what makes it load-bearing
   rather than convenient. A commit age at seconds resolution has to change
   every second, and routing that through the tick's `innerHTML` swap would
   re-run the regroup (#113) and re-carry his half-typed text (#118) sixty
   times a minute, forever, to move one digit. `setContent` re-runs this after
   every swap, so a fresh render is filled in before it paints. */
function ages() {
  document.querySelectorAll('.age[data-mt]').forEach(el =>
    el.textContent = ageStr(parseFloat(el.dataset.mt)) + ' old');
  document.querySelectorAll('.age[data-ct]').forEach(el =>
    el.textContent = agePair(parseFloat(el.dataset.ct)) + ' ago');
  /* a third flavour, and the difference is grammar rather than format (#165):
     a FILE is `5m old`, a thing he DID is `5m ago`. Commit resolution
     (`data-ct`) is two padded units and far too wide for a 38ch panel, so the
     history takes the short one. */
  document.querySelectorAll('.age[data-at]').forEach(el =>
    el.textContent = ageStr(parseFloat(el.dataset.at)) + ' ago');
  const upd = document.getElementById('upd');
  if (upd && fetchedAt) upd.textContent =
    `updated ${ageStr(fetchedAt/1000)} ago`;
  applyTitle();     // the liveness word drifts with the clock, not with disk
  applyFavicon();   // ...and the orbit advances one frame per second on it
  applyTint();      // ...and his colour arrives from whichever window set it
}
/* one field, two destinations: the mode group under the box picks which
   (#103). Everything downstream — the morph, the ripple, the re-render hold
   — is unchanged; only the routing is new. */
const cardMode = key => {
  const el = document.getElementById('qi' + key);
  const c = el && el.closest('.qcompose');
  return (c && c.dataset.mode) || 'note';
};
/* ONE implementation of "this card's text is destined for X" — used by the
   mode buttons and by the tick's restore (#118), so the two cannot drift.
   The mode is honoured only if this card actually offers it: a folded entry
   is note-only, so a carried-over 'answer' falls back to what the card
   rendered rather than arming a send that would fail. */
function setCardMode(comp, mode, snap) {
  if (!comp || !mode) return;
  const group = comp.querySelector('.sgroup.qmodes');
  const btn = group && group.querySelector('.qmode[data-mode="' + mode + '"]');
  if (!btn && comp.dataset.mode !== mode) return;   // not on offer here
  comp.dataset.mode = mode;
  if (group) group.querySelectorAll('.sgbtn').forEach(b => {
    const on = b === btn;
    b.classList.toggle('on', on);
    b.setAttribute('aria-checked', on ? 'true' : 'false');
  });
  const ta = comp.querySelector('textarea');
  if (ta) {
    ta.placeholder = QPLACE[mode] || '';
    // #273: keep the accessible name in lockstep with the mode control.
    const card = comp.closest('.qa');
    const titleEl = card && (card.querySelector(':scope > .qt')
      || card.querySelector(':scope > .qfold > .qt')
      || card.querySelector('.qt'));
    const title = titleEl ? titleEl.textContent.replace(/\\s+/g, ' ').trim() : '';
    ta.setAttribute('aria-label', qaFieldLabel(mode, title));
    const send = comp.querySelector('.qsend');
    if (send) send.setAttribute('aria-label', qaSendLabel(mode));
  }
  if (group) slideIndicator(group, !!snap);
}
function submitCard(key) {
  return cardMode(key) === 'answer' ? sendAnswer(key) : sendComment(key);
}
async function sendAnswer(key) {
  const el = document.getElementById('qi' + key);
  const card = el && el.closest('.qa');
  const q = qaEntry(key, card);
  if (!el || !el.value.trim() || !q) return;
  const val = el.value.trim();
  const fromRect = el.getBoundingClientRect();   // the box the text lived in
  const res = await postAnswer(q.title, val);
  // a failed write must NOT run the morph: the morph IS the confirmation, and
  // confirming a write that did not happen is the one thing worse than the
  // 409 itself (#136)
  if (!res || !res.ok) { qaFail(card, res ? res.status : 0); return; }
  if (!card) return;
  holdRerenderUntil = Date.now() + 1600;   // let the morph settle before regroup
  // the morph IS the confirmation: the box reshapes into the answered state,
  // the typed text lifting from the box into the rendered answer (the
  // lifted-hero rule — the answer text is the tracked element). A soft
  // ripple accents it. reduced-motion just swaps to the answered state.
  // Restated through the SAME component, so it cannot drift from a fresh
  // render of the same entry.
  //
  // ...and the card is not alone on the page (#191). Restating it changes its
  // HEIGHT, so every card below it moves — and this path went through neither
  // snapshot nor regroup, so they moved in one frame, in the one gesture this
  // page has most carefully taught to travel. Same seam as the disclosure
  // handler below: snapshot, mutate, regroup.
  const before = snapshotCards();
  const next = Object.assign({}, q, { answer: val });
  card.className = 'qa ' + qaState(next, key);
  card.innerHTML = qaInner(next, key);
  const anstext = card.querySelector('.anstext');
  // the settled destination, measured before the regroup clamps the card's
  // height for its travel — the flip's `to` is where the answer ENDS UP
  const toRect = anstext && anstext.getBoundingClientRect();
  regroupCards(before, null, null, card);
  if (typeof ripple === 'function')
    ripple(fromRect.left + fromRect.width / 2, fromRect.top + 22);
  if (!rmr && anstext && typeof flipDock === 'function')
    flipDock(anstext, fromRect, toRect);
}
/* thread a follow-up note onto any entry — same lifted-hero morph as an
   answer: the note lifts from the box into the thread, ripple accenting. */
async function sendComment(key) {
  const el = document.getElementById('qi' + key);
  const card = el && el.closest('.qa');
  const entry = qaEntry(key, card);
  if (!el || !el.value.trim() || !entry) return;
  const val = el.value.trim();
  const fromRect = el.getBoundingClientRect();
  const res = await postComment(entry.title, val,
                                key[0] === 'o' ? 'Open' : 'Answered');
  if (!res || !res.ok) { qaFail(card, res ? res.status : 0); return; }
  holdRerenderUntil = Date.now() + 1600;
  if (!card) { el.value = ''; return; }
  // #191, the same as an answer: the note lands INSIDE the card, so the card
  // grows and every card below it moves. Snapshot before the first thing that
  // changes a height — the box being cleared is one of those the moment a box
  // grows with what he types (#177), so it is inside the window rather than
  // trusted to stay inert.
  const before = snapshotCards();
  el.value = '';
  // the LAST segment, because what he just wrote is the newest thing in the
  // thread — appending to the first would drop it above an answer written
  // hours earlier, which is the bug this whole split exists to prevent (#128).
  // That segment is also never the collapsed one, so it cannot land hidden.
  let host = [...card.querySelectorAll('.threadin')].pop();
  if (!host) {
    const thread = document.createElement('div'); thread.className = 'thread';
    host = document.createElement('div'); host.className = 'threadin';
    thread.appendChild(host);
    card.insertBefore(thread, card.querySelector('.qcompose'));
  }
  const f = document.createElement('div');
  f.className = 'follow human';        // it is his; say so, same as a reload
  f.innerHTML = `<span class="who">${WHO.human}</span>` + mdInline(val);
  host.appendChild(f);
  const toRect = f.getBoundingClientRect();
  regroupCards(before, null, null, card);
  if (typeof ripple === 'function') ripple(fromRect.left + 24, fromRect.top + 14);
  if (!rmr && typeof flipDock === 'function') flipDock(f, fromRect, toRect);
}
"""

FAVICON_JS = """
/* ── the favicon: which loop, is it alive, does it need you (#153) ────────
   His words: "favicon required (we should make a great favicon, maybe
   animated? could render offline and load dynamically via round robin or
   whatever to loop)".

   THE MARK IS A RING WITH ONE TRAVELLER ON IT — the loop, and the thing
   going round it. Three facts in three channels that do not compete at 16
   pixels, which is the size this is really drawn at:

     hue       WHICH loop this is. #143's per-project tint lands here for
               free, so a tab strip of dreaming projects is legible by
               colour alone; six hues were checked at 16px before this shape
               was chosen.
     motion    the loop is ALIVE. It orbits while the loop ticks, and parks
               — dimmed, and with its trail gone — when it stalls, so the
               state reads from a single glance as well as from two.
     the pip   HE is the bottleneck: a crisp dot on the badge convention,
               knocked out of the ring so it reads as a separate object
               rather than a bulge. Amber rather than accent when the reader
               cannot see questions.md — that is #136's FIRST use on a new
               surface, not a third use of --warn.

   MOTION IS THE STATUS, which is the only reason it is here: an
   always-animating favicon is decoration, and this page's motion is opt-in
   and meaningful (see Motion language). The two channels are the title's
   two fields exactly — the pip is its count, the orbit is its liveness word
   — because both are derived from `titleNeed`/`titleLive` and a tab that
   contradicts itself would be worse than either half alone.

   INLINE, ALWAYS. `just deploy` snapshots watch.py alone, so a file beside
   the server does not exist in production. Canvas → PNG data URI rather
   than an SVG data URI, because Chrome renders an SVG favicon as ONE static
   frame and this one has twenty.

   THE GROUND IS TRANSPARENT. The first version painted the page's own
   near-black tile, which is right on his dark browser theme and becomes a
   black block on a light one — seen at 16px against real tab-strip greys,
   not reasoned about.

   MOTION IS DESIGNED FOR THE FRAME RATE THE TAB WILL ACTUALLY GET. A hidden
   document is given no rendering opportunities, so requestAnimationFrame
   does not run in a background tab at all — and a background tab is where
   this surface spends its life. Timers do survive there, clamped (≥1s, and
   ≥1min once Chrome throttles a long-hidden tab intensively). So the orbit
   is quantised to ONE FRAME PER SECOND, twenty frames to a revolution,
   riding the standing `ages()` sweep: right at 60fps, right at the 1s
   clamp, and degrading to nearly-still rather than to a stutter if the
   clamp becomes a minute. Frames are cached on first use — his round robin
   — so after one revolution a tick is a string assignment.

   Honest note: the clamp figures are documented behaviour, NOT measured
   here. Two attempts to put a page into the hidden state under Playwright
   failed (a second `newPage()` is a separate window, and `window.open`
   opened one too, so `visibilityState` stayed `visible` both times). The
   design does not rest on those numbers; it rests on rAF being unavailable,
   which is what "hidden" means.

   THE PHASE IS THE WALL CLOCK, not a counter. So every window watching the
   same loop shows the same frame — the shader's "one world, many viewports"
   rule one surface over — and a reload does not restart the orbit. */
const FAV_N = 20;                  // frames per revolution, one per second
const FAV_PX = 32;
const FAV_WARN_HUE = 45;           // --warn  #fcd34d
const favCache = new Map();
let favCv = null;
const favHsl = (h, s, l, a) => `hsla(${h}, ${s}%, ${l}%, ${a})`;
/* the hue comes from the project's tint (#143, `favHue` lives with it), so
   a strip of dreaming projects is legible by colour alone. */

function favPaint(hue, moving, pip, frame) {
  const S = FAV_PX;
  if (!favCv) {
    favCv = document.createElement('canvas');
    favCv.width = favCv.height = S;
  }
  const g = favCv.getContext('2d');
  g.clearRect(0, 0, S, S);
  const cx = S / 2, cy = S / 2, R = S * 0.315, W = S * 0.115;
  const dim = moving ? 1 : 0.6;    // a stalled loop reads faded, not absent
  g.lineCap = 'round';
  g.strokeStyle = favHsl(hue, 54, 57, 0.74 * dim);
  g.lineWidth = W;
  g.beginPath(); g.arc(cx, cy, R, 0, 7); g.stroke();
  const a0 = -Math.PI / 2 + (frame / FAV_N) * Math.PI * 2;
  // the trail: which way it is going, and the page's own softness. It is
  // also what makes "moving" legible in a single static frame, which is what
  // reduced motion is left with.
  if (moving) {
    const steps = 16, span = Math.PI * 0.9;
    for (let i = 0; i < steps; i++) {
      const t = i / steps;
      g.strokeStyle = favHsl(hue, 88, 76, (1 - t) * 0.55);
      g.lineWidth = W * (1 - t * 0.3);
      g.beginPath();
      g.arc(cx, cy, R, a0 - span * (t + 1 / steps), a0 - span * t);
      g.stroke();
    }
  }
  const hx = cx + Math.cos(a0) * R, hy = cy + Math.sin(a0) * R;
  const gl = g.createRadialGradient(hx, hy, 0, hx, hy, W * 2.1);
  gl.addColorStop(0, favHsl(hue, 96, 88, 0.95 * dim));
  gl.addColorStop(0.35, favHsl(hue, 96, 84, 0.55 * dim));
  gl.addColorStop(1, favHsl(hue, 96, 80, 0));
  g.fillStyle = gl;
  g.beginPath(); g.arc(hx, hy, W * 2.1, 0, 7); g.fill();
  g.fillStyle = favHsl(hue, 96, 90, dim);
  g.beginPath(); g.arc(hx, hy, W * 0.66, 0, 7); g.fill();
  if (pip) {
    // knock a transparent gap first: the badge has to read as a separate
    // object, and with no ground to paint one there is nothing else to cut
    // it out with.
    g.save();
    g.globalCompositeOperation = 'destination-out';
    g.beginPath(); g.arc(S * 0.79, S * 0.21, S * 0.168, 0, 7); g.fill();
    g.restore();
    g.fillStyle = pip === 'warn' ? favHsl(FAV_WARN_HUE, 95, 62, 1)
                                 : favHsl(hue, 92, 74, 1);
    g.beginPath(); g.arc(S * 0.79, S * 0.21, S * 0.118, 0, 7); g.fill();
  }
  return favCv.toDataURL('image/png');
}
function favURL(hue, moving, pip, frame) {
  const k = hue + '|' + (moving ? 1 : 0) + '|' + (pip || '-') + '|' + frame;
  let u = favCache.get(k);
  if (u === undefined) { u = favPaint(hue, moving, pip, frame);
                         favCache.set(k, u); }
  return u;
}
/* Derived from the title's own two functions, so the icon and the words in
   the same tab can never disagree. Nothing is drawn before data arrives —
   an invented state is worse here than no icon, because this one is read
   from across the room. */
function applyFavicon() {
  const link = document.getElementById('favicon');
  if (!link || !data) return;
  const need = titleNeed(data);
  const moving = titleLive(data) === 'dreaming';
  const pip = need === '!' ? 'warn'
            : (need && need !== '0') ? 'accent' : null;
  // Reduced motion pins the FRAME and keeps everything else: the trail and
  // the full brightness still say "in flight" with no motion at all, which
  // is the wisp's rule (timing changes, never function or legibility).
  const rm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const frame = (moving && !rm) ? Math.floor(Date.now() / 1000) % FAV_N : 0;
  const url = favURL(favHue(), moving, pip, frame);
  if (link.href !== url) link.href = url;
}
"""

ROUTER_JS = """
/* Single-document router. Views swap inside #view; the shader canvas is
   its sibling and is never touched, so the background is unbroken across
   navigations. Deep links still work: the server hands back this same
   shell for /, /questions, /file and /review, and we render the matching
   view on load. /review embeds the raw artifact (served at /reviewraw) in
   an iframe; a question that links to it travels along, docked. */
const rmr = matchMedia('(prefers-reduced-motion: reduce)').matches;
let data = null, fetchedAt = 0, lastMtime = null, serverGen = null;
/* after a local answer morph, hold the live re-render briefly so the card
   settles in place before the loop's fresh data regroups it (#79/#81). */
let holdRerenderUntil = 0;
/* /mtime is "<generation> <mtime>": a changed generation means the server
   was rebuilt (--autoreload) or restarted (redeploy) — reload to pick up the
   new shell; a changed mtime just re-renders the live data. */
const parseMtime = raw => {
  raw = (raw || '').trim();
  const sp = raw.indexOf(' ');
  return sp >= 0 ? { gen: raw.slice(0, sp), mtime: raw.slice(sp + 1) }
                 : { gen: '', mtime: raw };
};
let view = { name: null, param: null, q: null };
let fileCache = { param: null, text: undefined };
/* per-page atmosphere: a tiny tint bias the shader lerps toward (~1.5s) */
const TINT = { dashboard: 0.0, questions: 0.14, file: -0.14, review: 0.22 };
/* per-route dissolve signature: each destination swirls from its own
   turbulence seed, so arriving somewhere has a consistent feel (pairs with
   the per-route tint). Distinct small integers give distinct fields. */
const SEED = { dashboard: 7, questions: 23, file: 41, review: 61 };
/* ── the tab title (#153) ─────────────────────────────────────────────────
   The title is the ONLY part of this dashboard that exists while the tab is
   backgrounded, which is most of its life — so it answers the page's whole
   question rather than naming the app: DOES IT NEED ME, and WHICH loop is
   this. Both, because the workflow is now several dreaming agents at once.

       (2) dreamwork/ud-dreamwork · dreaming · questions
        ^   ^                        ^          ^
        |   |                        |          where you are (dropped first)
        |   |                        is the loop still ticking
        |   which app, and which loop of it
        how many things are waiting on YOU

   THE COUNT IS FRONT-LOADED because tabs truncate from the RIGHT, so
   everything past the first field is a bonus. Zero renders as `(0)`, not as
   an empty bracket: a title that says nothing about the count is
   indistinguishable from a page that has not loaded.

   THE TWO LOUD FIELDS ARE ORTHOGONAL, which is what keeps them worth
   reading. The count says whether HE is the bottleneck; the word says
   whether the LOOP is alive. `(2) x · stalled` — he is blocked and it is not
   moving — is a state neither field could report alone, and it is exactly
   the quiet failure this project exists to make loud.

   `!` REPLACES THE COUNT when the reader cannot see questions.md (#136),
   because in that state the count is the thing that lies. It does not say
   what broke — a tab title cannot — it says look, which is all a tab title
   is for. The dashboard's amber line says the rest.

   NOTHING IS CLAIMED THAT IS NOT KNOWN. Before data arrives the shell's own
   `<title>` stands; a target with no status.json gets no liveness word; an
   unparseable `last_tick` gets none either, on `note_author`'s rule. */
const TITLE_ROUTE = { dashboard: () => '', questions: () => 'questions',
                      file: p => p || 'file',
                      review: p => 'review ' + (p || '') };
/* two missed heartbeats (4.75m each) — one late beat is a busy machine, two
   is a loop that stopped. */
const STALE_TICK_MS = 10 * 60 * 1000;
const statusOf = d => (d && d.status && typeof d.status === 'object')
  ? d.status : null;
/* The honest count of what is visibly waiting on HIM. It derives from the
   open questions he can inspect, never from hand-maintained status prose;
   `awaiting_human` still names WHAT waits in the status panel (#181). */
function titleNeed(d) {
  if (!d) return null;
  if (d.questions_health === 'unreadable') return '!';
  return String(d.open_questions || 0);
}
function titleLive(d) {
  const s = statusOf(d);
  const t = s && s.last_tick ? Date.parse(s.last_tick) : NaN;
  if (isNaN(t)) return '';
  return Date.now() - t > STALE_TICK_MS ? 'stalled' : 'dreaming';
}
const projectName = d => ((d && d.target) || '').replace(/[\\/]+$/, '')
                          .split(/[\\/]/).pop();
/* WHICH loop, in one field. It was the project alone until he ruled at 15:30
   on 2026-07-25 (`(4) dreamwork · <status> · <extra>`) that the app's name
   comes back — the argument for dropping it was that a tab strip never has
   room, and his answer is that he wants to know what he is looking at.

   His example put `dreamwork` in the slot the PROJECT name occupied, and he
   was reading the ud-dreamwork dashboard when he wrote it, so it reads
   equally as "the app name returns" and as "this is what my tab already
   says". This is the one shape that is right under both: one compound field
   where he put one field, and for another target it reads `dreamwork/hark`,
   which is what it is. The state stays third, so truncation still takes the
   route first. */
const titleWho = d => {
  const proj = projectName(d);
  return proj ? 'dreamwork/' + proj : 'dreamwork';
};
function pageTitle(v, d) {
  const need = titleNeed(d);
  if (need === null) return null;             // no data: claim nothing
  const route = (TITLE_ROUTE[v.name] || TITLE_ROUTE.dashboard)(v.param);
  return `(${need}) ` +
    [titleWho(d), titleLive(d), route].filter(Boolean).join(' · ');
}
/* ── his colour for this project (#143) ───────────────────────────────────
   His words: "user can customize color tint for watch on dashboard for
   dreamworker. shoudl persist for that project and update any other windows
   for that project too."

   PERSIST *AND* SHARE IS WHAT RULES OUT localStorage: it syncs the tabs on
   one machine and loses the setting on the next, and the setting is meant to
   be how he tells this project apart from the others. It lives in
   `.dreamwork/watch-tint`, committable beside everything else the loop keeps
   about a project — so a checkout of the repo arrives already wearing it.

   AND SHARING NEEDS NO NEW MECHANISM. The write lands under `.dreamwork/`,
   which `watched_mtime` already walks, so the existing 2s `/mtime` poll
   carries it: he picks a colour in one window and every other window on this
   project follows within a tick, with nothing added and no reload.

   A HUE, NEVER A COLOUR — see `TINTS`. It rotates the ambient field about
   the grey axis and moves the FAVICON with it. It does not touch the text
   ramp and it deliberately does not touch `--accent`: the accent has one
   job, marking the live and actionable thing, and an indigo accent over a
   green field is more legible than one that moved with it, not less. So the
   thing the tint identifies is the project, and the thing the accent marks
   is still the only thing that needs him. */
let projTint = null;
const tintHue = name => TINTS[name] != null ? TINTS[name] : TINTS[TINT_DEFAULT];
const favHue = () => tintHue(projTint || TINT_DEFAULT);
function applyTint() {
  if (!data) return;
  const name = TINTS[data.tint] != null ? data.tint : TINT_DEFAULT;
  if (name === projTint) return;              // idempotent: the 1s sweep runs it
  projTint = name;
  if (window.dreambg)
    window.dreambg.setProjHue(
      (tintHue(name) - TINTS[TINT_DEFAULT]) * Math.PI / 180);
  // every cached frame was drawn in the old hue, and the icon is the one
  // place the tint has to be right immediately — it is what he is looking at
  // in the OTHER windows when this arrives.
  favCache.clear();
  applyFavicon();
}
/* The picker is the page's standing sliding group (#103/#121), not new
   chrome: an outline that travels, no fill anywhere, so the dreaming field
   stays the background of every button. Each label wears its own hue, which
   is the only way a name like `teal` means anything before you click it. */
function tintPicker(d) {
  const cur = TINTS[d.tint] != null ? d.tint : TINT_DEFAULT;
  return label('tint') +
    `<div class="sgroup tintpick" role="radiogroup" aria-label="project tint">` +
    `<div class="sgind"></div>` +
    Object.keys(TINTS).map(n =>
      `<button type="button" role="radio" class="sgbtn tintbtn` +
      `${n === cur ? ' on' : ''}" data-tint="${esc(n)}"` +
      ` style="--tintswatch:hsl(${TINTS[n]}, 62%, 66%)"` +
      ` aria-checked="${n === cur ? 'true' : 'false'}"` +
      ` onclick="pickTint('${esc(n)}')">${esc(n)}</button>`).join('') +
    `</div><div class="tintmsg" id="tintmsg" aria-live="polite"></div>`;
}
/* A refused write must not leave a swatch selected that will not survive the
   next tick — the same rule as /answer (#136): check what came back before
   showing the thing that means "it landed". */
async function pickTint(name) {
  const msg = document.getElementById('tintmsg');
  let ok = false;
  try {
    const res = await fetch('/tint', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tint: name }),
    });
    ok = res.ok;
  } catch (e) { ok = false; }
  if (ok) {
    if (msg) msg.textContent = '';
    // do not wait for the poll in the window he is actually looking at
    if (data) { data.tint = name; applyTint(); }
    document.querySelectorAll('.sgroup.tintpick').forEach(g => {
      g.querySelectorAll('.sgbtn').forEach(b => {
        const on = b.dataset.tint === name;
        b.classList.toggle('on', on);
        b.setAttribute('aria-checked', on ? 'true' : 'false');
      });
      slideIndicator(g, false);
    });
  } else if (msg) {
    msg.textContent = 'could not save the tint — the file was refused';
  }
}
/* Set from the route change, from the tick, AND from the 1s age sweep — the
   liveness word drifts with the wall clock and nothing on disk changes when
   a loop stops, so it needs the same seam the commit ages use (#132).
   Assigning only on a real change keeps that free. */
function applyTitle() {
  const t = pageTitle(view, data);
  if (t && document.title !== t) document.title = t;
}

function routeOf(loc) {
  if (loc.pathname === '/questions') return { name: 'questions', param: null };
  if (loc.pathname === '/answers') return { name: 'answers', param: null };
  if (loc.pathname === '/file')
    return { name: 'file',
             param: new URLSearchParams(loc.search).get('p') };
  if (loc.pathname === '/review') {
    const sp = new URLSearchParams(loc.search);
    return { name: 'review', param: sp.get('p'), q: sp.get('q') };
  }
  return { name: 'dashboard', param: null };
}
/* THE ONE PLACE `data` IS REPLACED, and it is a function rather than an
   assignment because there are TWO fetchers — the first paint (`ensureData`)
   and the live tick — so anything that must react to new data has to be hung
   off both or it silently works on one path only.

   #86 is how that was found. The composer's plugin vocabulary was notified
   from the tick alone, which looks like the live path and is not the first
   one: `ensureData` sets `lastMtime` as it fetches, so the first tick sees
   nothing changed and does nothing, and the commands never arrived at all on
   a freshly opened page. Adding a second call site would have fixed the
   symptom and left the next reader the same trap, which is #191's lesson
   about one gesture spelled two ways, aimed at data instead of at motion. */
function setData(next) {
  data = next;
  // WHICH PLUGINS RESOLVED IS A PROPERTY OF THE MACHINE, not of watch.py, so
  // the composer's vocabulary can change under a page that is already open
  // (#86). It compares whole and returns immediately on the ticks — nearly
  // all of them — where the declared set has not moved.
  if (window.dwPluginCommands) window.dwPluginCommands(data.plugin_commands);
  return data;
}
async function ensureData() {
  if (data) return data;
  try {
    const { gen, mtime } = parseMtime(await (await fetch('/mtime')).text());
    if (serverGen === null) serverGen = gen;
    lastMtime = mtime;
    fetchedAt = Date.now();
    setData(await (await fetch('/data.json')).json());
  } catch (e) {}
  return data;
}
async function fetchFile(param) {
  if (fileCache.param === param) return fileCache.text;
  let text = null;
  try {
    const res = await fetch('/filedata?p=' + encodeURIComponent(param || ''));
    if (res.ok) text = (await res.json()).content;
  } catch (e) {}
  fileCache = { param, text };
  return text;
}
async function buildCurrent() {
  if (view.name === 'file')
    return buildFile(view.param, await fetchFile(view.param));
  const d = await ensureData();
  if (view.name === 'review') return buildReview(view.param, view.q, d);
  if (!d) return '<div class="dim">loading…</div>';
  if (view.name === 'questions') return buildQuestions(d);
  if (view.name === 'answers') return buildAnswers(d);
  return buildDashboard(d);
}
function snapshotAskState() {
  const box = document.getElementById('askbox');
  if (!box || (!box.value && box !== document.activeElement)) return null;
  return {value:box.value, focus:box === document.activeElement,
          start:box.selectionStart, end:box.selectionEnd, scroll:box.scrollTop,
          height:box.style.height};
}
function restoreAskState(saved) {
  if (!saved) return;
  const box = document.getElementById('askbox'); if (!box) return;
  box.value = saved.value; box.scrollTop = saved.scroll;
  if (saved.height) box.style.height = saved.height;
  try { box.setSelectionRange(saved.start, saved.end); } catch (e) {}
  if (saved.focus) refocus(box);
}
function snapshotReviewFrame() {
  const frame = document.getElementById('reviewframe');
  if (!frame) return null;
  const saved = { frame, src: frame.src, x: 0, y: 0, readable: false };
  try {
    saved.x = frame.contentWindow.scrollX;
    saved.y = frame.contentWindow.scrollY;
    saved.readable = true;
  } catch (e) { /* cross-origin artifacts keep their URL; scroll is opaque */ }
  return saved;
}
function restoreReviewFrame(saved) {
  if (!saved) return;
  const fresh = document.getElementById('reviewframe');
  if (!fresh) return;
  // Preserve the live browsing context itself. Recreating an iframe starts a
  // navigation which necessarily resets its scroll and may also discard state
  // inside cross-origin artifacts that the parent is forbidden to inspect.
  if (fresh !== saved.frame) fresh.replaceWith(saved.frame);
  if (saved.frame.src !== saved.src) saved.frame.src = saved.src;
  if (saved.readable) {
    try { saved.frame.contentWindow.scrollTo(saved.x, saved.y); } catch (e) {}
  }
}
function setLiveContent(html) {
  if (view.name === 'review') {
    const parsed = document.createElement('template');
    parsed.innerHTML = html;
    const currentDock = document.getElementById('qdock');
    const nextDock = parsed.content.querySelector('#qdock');
    if (currentDock && nextDock) currentDock.replaceWith(nextDock);
    else setContent(html);
    paintIndicators(true); ages();
    return;
  }
  setContent(html);
}
/* One-shot atmospheric arrival for NEW /answers open rows (#293 amend).
   Keys by data-aqid (server `open:` aid over title+body+ordinal — never
   title alone). First paint of the answers view, and hard refresh,
   settle fully visible without replaying .dreamin. Live-added
   rows (after a successful /ask) snap to the enter pose then ease in;
   reduced motion leaves them fully visible (function, no start pose).
   window.__dwSkipOpenAskArrival is a deliberate inject point for the
   browser guard's RED of the arrival mechanism. */
let knownOpenAskKeys = null;
function revealNewOpenAsks() {
  if (view.name !== 'answers') { knownOpenAskKeys = null; return; }
  const nodes = [...document.querySelectorAll('.aq.open[data-aqid]')];
  const now = new Set(nodes.map(el => el.dataset.aqid));
  if (knownOpenAskKeys === null || window.__dwSkipOpenAskArrival) {
    // first answers paint, or inject: settle without stuck dreamin
    nodes.forEach(el => el.classList.remove('dreamin'));
    knownOpenAskKeys = now;
    return;
  }
  const rmr = matchMedia('(prefers-reduced-motion: reduce)').matches;
  for (const el of nodes) {
    if (knownOpenAskKeys.has(el.dataset.aqid)) continue;
    if (rmr) continue;                          // already fully lit
    el.classList.add('dreamin');
    void el.offsetWidth;                        // commit opacity 0
    requestAnimationFrame(() => {
      if (el.isConnected) el.classList.remove('dreamin');
    });
  }
  knownOpenAskKeys = now;
}
function setContent(html) {
  document.getElementById('view').innerHTML = html;
  // fresh groups carry a 0-width indicator, so land it rather than let it
  // slide up out of nothing (the enter-snap rule)
  paintIndicators(true);
  ages();
  revealNewOpenAsks();
}
/* ── what the human did to a card survives a tick (#118, #111) ────────────
   The tick re-renders the question list through `innerHTML`, so every card
   node is genuinely replaced — and with it whatever the human was part-way
   through typing, and whichever folded entry he had just opened up to read.
   Liveness is not negotiable (the tick has always committed its new DOM
   immediately), so the fix is not to suppress the render; it is to carry
   across the render the state that exists NOWHERE ELSE. What he typed, where
   his caret is, which endpoint it is destined for, and what he has expanded
   are not on disk, so nothing downstream can reconstruct them.

   Keyed by `data-qid` — the question itself — for exactly the reason the
   regroup is: answering re-indexes an entry out of `questions_open`, so a
   positional key would drop the text at the very moment the card moves. */
function snapshotCardState() {
  const act = document.activeElement;
  const m = new Map();
  document.querySelectorAll('.qa[data-qid]').forEach(card => {
    const comp = card.querySelector('.qcompose');
    const ta = comp && comp.querySelector('textarea');
    // EVERY disclosure in the card, in document order: the folded entry itself
    // (#111) and its settled thread (#128) both render closed, so either being
    // open is something he did and nothing on disk records.
    const dets = [...card.querySelectorAll('details')].map(d => d.open);
    const typed = ta && (ta.value || ta === act);
    const opened = dets.some(Boolean);
    if (!typed && !opened) return;         // he has done nothing to this card
    m.set(card.dataset.qid, {
      open: dets,
      value: typed ? ta.value : null, mode: comp && comp.dataset.mode,
      focus: ta === act,
      start: typed ? ta.selectionStart : 0, end: typed ? ta.selectionEnd : 0,
      dir: typed ? ta.selectionDirection : 'none',
      scroll: typed ? ta.scrollTop : 0,
      height: typed ? ta.style.height : '', // the box is resize:vertical
    });
  });
  return m;
}
function restoreCardState(saved) {
  if (!saved || !saved.size) return;
  document.querySelectorAll('.qa[data-qid]').forEach(card => {
    const s = saved.get(card.dataset.qid);
    if (!s) return;
    // only ever re-opened, never closed: the fresh render is the default and
    // what he did to it is the addition
    const dets = [...card.querySelectorAll('details')];
    (s.open || []).forEach((o, i) => { if (o && dets[i]) dets[i].open = true; });
    if (s.value === null) return;
    const comp = card.querySelector('.qcompose');
    const ta = comp && comp.querySelector('textarea');
    if (!ta) return;                       // the state stopped offering a box
    ta.value = s.value;
    if (s.height) ta.style.height = s.height;
    // the mode is WHERE THE TEXT GOES: a re-render must never silently
    // redirect it. setCardMode declines a mode the new state cannot accept.
    setCardMode(comp, s.mode, true);
    ta.scrollTop = s.scroll;
    try { ta.setSelectionRange(s.start, s.end, s.dir || 'none'); } catch (e) {}
    if (s.focus) refocus(ta);
  });
}
/* Put the caret back in the box he was typing in — and CHECK that it landed,
   because the way this fails is silence (#179).
   `focus()` on an element inside a CLOSED <details> does nothing at all and
   throws nothing, so a card restored while its section was still shut came
   back filled but dead, and only on the dashboard, where cards live inside
   `.qsec`. Ordering the two restores fixes that instance; this kills the
   class, which is what "his state survives ANY re-render" needs — the next
   container someone wraps the list in has no snapshot of its own and would
   silently eat the focus again.
   Re-opening is always safe here BY CONSTRUCTION: he could only have been
   typing in a box whose ancestors were open, so every one of them re-opening
   is restoring what he had. It obeys the standing rule that a restore only
   ever RE-OPENS or RE-FILLS — the worst it can do is give something back. */
function refocus(ta) {
  ta.focus({ preventScroll: true });
  if (document.activeElement === ta) return;
  for (let n = ta.parentElement; n; n = n.parentElement)
    if (n.tagName === 'DETAILS') n.open = true;
  ta.focus({ preventScroll: true });
}
/* ── the regroup (#104, #77) ──────────────────────────────────────────────
   Answering a question moves it out of the open list and under a different
   heading. That is one moment seen two ways: the questions below close the
   gap it left (#104), and the question itself travels to its new section
   rather than being re-set there (#77). So it is one mechanism — a FLIP over
   the list, keyed by `data-qid`, which is the question and survives the move
   its positional key cannot.

   Liveness is not delayed by this. The new DOM is committed IMMEDIATELY, as
   the tick always has; only the visual transform is animated, so what is on
   screen is always the current data drawn from where it used to be. */
/* which heading a card currently sits under — the thing #77 is actually
   about. Not the card's own state class: the submit morph already changed
   that locally when the answer was sent, so by regroup time it would report
   no change even though the card is about to cross the page. */
/* #118's rule one level up (#141). A SECTION he has opened is his, it exists
   nowhere on disk, and the tick rebuilds the dashboard through `innerHTML` —
   so without this the questions fold would snap shut under him every two
   seconds, which is the bug #118 fixed for a card's own disclosure. Keyed by
   `data-keep` rather than by position, and only ever RE-OPENED: the fresh
   render is the default and what he did to it is the addition. Any future
   section that wants the same gets it by carrying the attribute. */
function snapshotFolds() {
  const m = new Map();
  document.querySelectorAll('details[data-keep]').forEach(el =>
    m.set(el.dataset.keep, el.open));
  return m;
}
function restoreFolds(saved) {
  if (!saved) return;
  document.querySelectorAll('details[data-keep]').forEach(el => {
    if (saved.get(el.dataset.keep)) el.open = true;
  });
}
function cardGroup(el) {
  for (let n = el.previousElementSibling; n; n = n.previousElementSibling)
    if (n.classList.contains('label')) return n.textContent;
  return '';
}
/* the keyed lists that move. A "list" is a selector plus the attribute that
   IS a row's identity — never its position, because the whole job here is
   telling a row that MOVED from a row that LEFT, and a positional key cannot.
   Both lists go through the same snapshot and the same regroup: #151 is
   #104's motion over a different set of rows, and a second implementation of
   "one leaves, its neighbours travel" would be two things to keep true. */
const QA_LIST = { sel: '.qa[data-qid]', key: 'qid' };
const ANSWER_LIST = { sel: '.aq.answered[data-aid]', key: 'aid' };
const GIT_LIST = { sel: '.git .commit[data-sha]', key: 'sha' };
const REVIEW_LIST = { sel: '[data-review]', key: 'review' };
function snapshotCards(list) {
  list = list || QA_LIST;
  const m = new Map();
  document.querySelectorAll(list.sel).forEach(el =>
    m.set(el.dataset[list.key], {
      rect: el.getBoundingClientRect(),
      group: cardGroup(el),
      // cloned up front because a departure has no node left to animate once
      // the re-render has happened, and we cannot know which will depart
      node: el.cloneNode(true),
    }));
  return m;
}
/* ONE way a card moves inside the list (#104, #77, #113). It travels from the
   rect it had to the rect it has — in position AND in height — and when it
   crossed to a different HEADING it is lifted while it goes, so the eye
   follows that one card across the page instead of reading the whole list as
   re-laid-out.

   Height, not scale, and that distinction is load-bearing. `flipDock` morphs
   by `scale()`, which is right for the review dock, where the card genuinely
   changes column. Inside the list the column never changes — but the HEIGHT
   now can, by a factor of fifteen, because folding collapses the card (#111).
   A scale morph would stretch the text by that ratio at frame 0 and read as a
   squash, not a fold. So the size travels as height, with the box clipped
   while it does.

   Every state change on this list also changes the heading the card sits
   under, so `lifted` is the same signal as "the state changed" — read from
   the heading rather than the class, because the submit morph has already
   changed the class locally by the time we get here. */
const CARD_MS = 850;
const CARD_TRAVEL =
  'transform .85s cubic-bezier(.32,.1,.2,1),' +
  ' height .85s cubic-bezier(.32,.1,.2,1), filter .7s ease, opacity .7s ease';
function travelCard(el, was, now, lifted) {
  const resized = Math.abs(was.height - now.height) >= 1;
  el.style.transition = 'none';            // the enter-snap rule, again
  el.style.transform = `translate(${was.left - now.left}px,` +
                       `${was.top - now.top}px)`;
  if (resized) {
    // border-box, because the two numbers being interpolated came from
    // getBoundingClientRect and that is a BORDER box, while `height` is a
    // content box by default. It was a distinction without a difference while
    // the only travellers were `.qa` and `.git .commit`, neither of which has
    // vertical padding — and then #196 sent a <details> through here, which
    // gains #169's `.5rem` of air on the frame it opens. Left as content-box
    // the travel aims 16px past its real height and SNAPS back the moment the
    // inline height is cleared: invisible to an end-state check, and to "did
    // it move", which is the shape of every motion bug this page has had.
    el.style.boxSizing = 'border-box';
    el.style.height = was.height + 'px';
    el.style.overflow = 'hidden';          // content must not spill as it folds
  }
  if (lifted) {
    el.style.zIndex = '4'; el.style.filter = 'blur(5px)'; el.style.opacity = '.4';
  }
  void el.offsetWidth;                     // commit the inverted start
  el.style.transition = CARD_TRAVEL;
  // an explicit identity, not a removal: the inline transform IS the signal
  // that a card travelled rather than being re-laid-out, and removing it
  // synchronously leaves nothing for a per-frame trace to see. Cleared below.
  el.style.transform = 'translate(0px, 0px)';
  if (resized) el.style.height = now.height + 'px';
  if (lifted) { el.style.filter = ''; el.style.opacity = ''; }
  setTimeout(() => {
    for (const p of ['transition', 'transform', 'height', 'overflow',
                     'boxSizing', 'zIndex', 'filter', 'opacity']) el.style[p] = '';
  }, CARD_MS + 150);
}
/* an element leaving fades rather than vanishing — the page's one departure
   idiom, lifted out of flow at the rect it occupied so survivors can close
   the gap underneath it, then dissolved on the mist. `clipTop` hides the part
   of the ghost the survivor still occupies, which is what makes it usable for
   a BODY leaving as well as for a whole card leaving. */
function dreamAway(wrap, node, rect, clipTop) {
  if (!wrap) return;
  const org = wrap.getBoundingClientRect();
  // A ghost is a CORPSE, not the card, so it must not keep the card's
  // address. It is a clone, so it arrives carrying data-qid and data-qkey —
  // and it is appended to .wrap, which means every `.qa[data-qid]` walk on
  // the page would find it: snapshotCards would capture its absolute rect as
  // the question's, restoreCardState would type into it, and a per-frame
  // trace would measure it instead of the card animating underneath. That
  // last one is how this was found. Strip the identity at the door rather
  // than teaching six lookups to skip it.
  // Every identity attribute on the page, not just this list's: a corpse
  // holds no address at all, and enumerating them here is one line where
  // teaching each lookup to skip a ghost would be six.
  //
  // AND THROUGHOUT THE SUBTREE, not only on the node itself (#196). While the
  // only things that dreamed away were one card and one commit row, the node
  // WAS the whole identity; the questions fold ghosts a clone of the entire
  // open section, which carries `data-keep="qsec"` and every card inside it.
  // `snapshotFolds` walks `details[data-keep]` and the last match wins — and a
  // ghost is appended to `.wrap`, i.e. last — so that one attribute surviving
  // means the next tick reads the section as still open and re-opens it under
  // him, a second after he shut it.
  const IDS = ['data-qid', 'data-qkey', 'data-sha', 'data-keep', 'data-aid'];
  for (const n of [node, ...node.querySelectorAll(IDS.map(a => `[${a}]`).join(','))])
    for (const a of IDS) n.removeAttribute(a);
  node.classList.add('qaghost');
  node.style.left = (rect.left - org.left) + 'px';
  node.style.top = (rect.top - org.top) + 'px';
  node.style.width = rect.width + 'px';
  if (clipTop > 0) node.style.clipPath = `inset(${Math.round(clipTop)}px 0 0 0)`;
  wrap.appendChild(node);
  void node.offsetWidth;
  node.classList.add('gone');
  setTimeout(() => node.remove(), 1000);
}
/* the same departure idiom for a subtree that has just left the layout but is
   still in the DOM — a `<details>` that closed. It has no box any more, so the
   rect is the one measured while it did. */
function ghostNode(el, rect) {
  if (rmr || !rect || !rect.height) return;
  dreamAway(document.querySelector('.wrap'), el.cloneNode(true), rect, 0);
}
/* what is really arriving or leaving when a card changes height. Normally that
   is everything under its title line — the card folded or unfolded — and the
   title itself survives as the summary, so it is not part of the move.

   A disclosure INSIDE the card resizes the card too (its settled follow-up
   thread, #128), and there only that disclosure's own contents move: the body,
   the answer and the compose box were on screen before and after and must not
   be re-faded. So the toggle that caused the change is passed in when it is
   known, and when it is the card's own `.qfold` this is exactly what it always
   was. */
function cardBody(el, toggled) {
  const root = (toggled && el.contains(toggled)) ? toggled
             : (el.querySelector(':scope > .qfold') || el);
  return [...root.children].filter(c =>
    c.tagName !== 'SUMMARY' && !c.classList.contains('qt'));
}
/* was the height change caused by a disclosure NESTED inside the card, rather
   than by the card's own fold? The two need different departure ghosts, so
   they are told apart once, here. */
const nestedToggle = (el, toggled) =>
  !!toggled && el.contains(toggled) &&
  toggled !== el.querySelector(':scope > .qfold');
/* the arriving half of a fold, and the page has exactly one of them (#196).
   A body that arrives EASES IN rather than being wiped up by the growing box —
   the same moment `dreamAway` runs backwards. Shared by the card fold and the
   dashboard's questions section, because two spellings of one gesture is how
   a reader concludes the softer one was optional. */
function revealBody(el, toggled) {
  cardBody(el, toggled).forEach(c => {
    c.classList.add('qreveal', 'dreamin');
    requestAnimationFrame(() => c.classList.remove('dreamin'));
    setTimeout(() => c.classList.remove('qreveal'), CARD_MS + 150);
  });
}
const BODY_STEP = 24;             // about a line: below this nothing "left"
/* Cards are processed in DOM order, and that is load-bearing rather than
   incidental.

   A resizing card's own height animation carries everything below it — the
   layout does that continuously, for free, and it is the better motion
   because the neighbours stay welded to the card they are following. So the
   FLIP only has to handle the RESIDUAL: whatever moved for some other reason.
   Restoring a card's old height before the next card is measured is exactly
   what makes the next card's `now` mean "where it would be if only that
   resize had happened", so the residual it FLIPs is the right one. FLIPping
   the full difference instead would move a neighbour twice — once by
   transform and once by layout — and it would snap back at the end.

   The commits panel (#151) runs through this unchanged, and the two branches
   that are about a CARD are inert there BY CONSTRUCTION rather than by a
   guard clause: a commit row is fixed-height, so `dh` is always 0 and neither
   body branch is reachable, and no `.label` precedes a row inside `.git`, so
   `cardGroup` returns '' on both sides and nothing is ever lifted. Both of
   those are properties of the markup, which is why they are stated in the CSS
   and in gitRow rather than tested for here. */
function regroupCards(before, toggled, list, restated) {
  if (rmr || !before || !before.size) return;
  list = list || QA_LIST;
  const wrap = document.querySelector('.wrap');
  const seen = new Set();
  document.querySelectorAll(list.sel).forEach(el => {
    const id = el.dataset[list.key], was = before.get(id);
    seen.add(id);
    if (!was) {                       // newly arrived: snap, then ease in
      el.classList.add('dreamin');
      requestAnimationFrame(() => el.classList.remove('dreamin'));
      return;
    }
    const now = el.getBoundingClientRect();
    const moved = Math.abs(was.rect.left - now.left) >= 1 ||
                  Math.abs(was.rect.top - now.top) >= 1;
    // a card can change SIZE without moving — it is the first in its list and
    // it just folded — and that is as much a travel as a move
    const dh = now.height - was.rect.height;
    if (!moved && Math.abs(dh) < 1) return;
    travelCard(el, was.rect, now, was.group !== cardGroup(el));
    // A card the CALLER restated is not one whose body arrived or left (#191).
    // The submit morph replaces the card's contents itself and gives the one
    // thing that is genuinely new — the answer, the note — its own lifted-hero
    // arrival; the body, the thread and the compose box were on screen before
    // and after. Re-fading them would say a change happened where none did,
    // which is #128's rule one surface over. Its HEIGHT still travels, and
    // that is the thing carrying every card below it.
    if (el === restated) return;
    // The box travelling is only half of a fold. The BODY is leaving, and an
    // element leaving fades rather than vanishing (human, 2026-07-25:
    // "when it folds in, the body shouldn't disappear all at once"). The new
    // card is already the folded one, so there is no live body left to
    // animate — which is exactly what the up-front clone is for. Ghost it at
    // the rect it occupied, clipped to below the line the survivor still
    // fills, and let it dream away on the departure idiom.
    //
    // A NESTED disclosure closing is ghosted by its own handler instead: the
    // settled thread sits above the compose box, so what disappears is a
    // MIDDLE band, and clipping the card-level clone to below the new height
    // would ghost the bottom slice — the compose box, which never left.
    if (dh <= -BODY_STEP) {
      if (!nestedToggle(el, toggled))
        dreamAway(wrap, was.node, was.rect, now.height);
    }
    // ...and unfolding is the same moment run backwards: the body ARRIVES,
    // so it eases in rather than being wiped up by the growing box.
    else if (dh >= BODY_STEP) revealBody(el, toggled);
  });
  // gone entirely: dream away where it stood, so it fades rather than blinks
  before.forEach((was, id) => {
    if (!seen.has(id)) dreamAway(wrap, was.node, was.rect, 0);
  });
}
/* the burndown's bars (#142), on #151's gate and for #151's reason.

   A bar is a VALUE re-rendered, not an element that moved, so the opt-in
   rule's default is that it does not animate — and if the panel re-rendered
   its bars on every tick, a bar creeping by one pixel every two seconds
   would be motion with nothing behind it, which is exactly what #151's gate
   exists to prevent. But when the numbers really change, a bar jumping to a
   new height is the same snap the section fold was, one panel down.

   So: gated on the SERIES, never on the tick, and animated by height alone,
   because the panel's own height is fixed and nothing below it can move.

   AND THE GATE HERE IS AN OPTIMISATION, NOT A BEHAVIOUR — which #151's is
   not, and the difference is worth stating rather than leaving for someone
   to assume. A commit row can move because something ELSE re-laid the page
   out, so #151's gate has an observable effect and a guard that constructs
   it. A bar's height is a pure function of the series, so "the data changed"
   and "a bar moved" are the same event: delete this gate and `regroupBars`
   early-returns on every equal height, and no outcome changes. It is kept
   for the forced layouts it saves twice a second, forever. It is NOT
   guarded, and that is deliberate — a check that cannot fail is worse than
   no check, because its message sends the next person to the wrong file.
   That last part is why this needs no FLIP over neighbours — and it is a
   PREMISE, not an aside, so `burndown.mjs` asserts the panel height is
   invariant across a data change rather than taking my word for it. #204 is
   what a reasoned exemption costs when nobody checks its premise.

   Keyed by bucket AND series: two bars share a column and three share a
   bucket, so the bucket alone is not an identity — the shortening that
   merged three cards into one series in a trace was this same mistake. */
function snapshotBars() {
  const m = new Map();
  document.querySelectorAll('.bd .bdbar[data-bk]').forEach(el =>
    m.set(el.dataset.bk + '/' + el.dataset.series,
          el.getBoundingClientRect().height));
  return m;
}
function regroupBars(before) {
  if (rmr || !before || !before.size) return;
  document.querySelectorAll('.bd .bdbar[data-bk]').forEach(el => {
    const was = before.get(el.dataset.bk + '/' + el.dataset.series);
    const now = el.getBoundingClientRect().height;
    if (was === undefined) {          // a new bucket: snap, then ease in
      el.classList.add('dreamin');
      requestAnimationFrame(() => el.classList.remove('dreamin'));
      return;
    }
    if (Math.abs(was - now) < 1) return;
    /* RESTORE THE PERCENTAGE, NEVER CLEAR THE HEIGHT. Every other travel on
       this page clears its inline height at the end because those elements
       get their size from layout — a bar gets its size from an inline
       `height:N%` written by the renderer, so clearing it leaves the bar at
       ZERO. The whole chart collapsed to its 2px rules after every animation
       and stayed there until the next re-render put fresh nodes in: #198's
       shape exactly, a permanent bug with a short, unreliable lifetime,
       laundered by something unrelated. Found by the guard's quiet-tick
       check, which measured the bars at 2px before the tick it was about. */
    const pct = el.style.height;
    el.style.transition = 'none';     // the enter-snap rule, again
    // border-box for `travelCard`'s reason: `now` came from
    // getBoundingClientRect, which is a BORDER box, and `.bdlevel` is a 2px
    // rule with no fill — left content-box the travel aims 2px past where it
    // ends and snaps when the percentage comes back.
    el.style.boxSizing = 'border-box';
    el.style.height = was + 'px';
    void el.offsetWidth;
    el.style.transition = 'height .85s cubic-bezier(.32,.1,.2,1)';
    el.style.height = now + 'px';
    setTimeout(() => {
      el.style.transition = ''; el.style.boxSizing = ''; el.style.height = pct;
    }, CARD_MS + 150);
  });
}
/* switching a card's mode: the indicator slides, the placeholder follows,
   and the field keeps whatever is typed in it — the text is the point, the
   mode is only where it goes. */
addEventListener('click', e => {
  const btn = e.target.closest && e.target.closest('.qmode');
  if (!btn) return;
  e.preventDefault();
  // membership is fixed here, so the indicator slides rather than lands
  setCardMode(btn.closest('.qcompose'), btn.dataset.mode, false);
});
/* opening or closing a disclosure INSIDE a card HIMSELF — the folded entry
   (#111) or its settled follow-up thread (#128) — is the same moment as the
   loop folding one: a card changes height and its neighbours close or open the
   gap underneath it. So both go through the same snapshot and the same
   regroup, rather than growing a second way to move a card. That is the
   styleguide's line: an expand inside a list whose OTHER members move is the
   one that animates; a standalone `<details>` still toggles instantly. The
   native toggle is prevented because <details> flips before any event we could
   measure from, and a FLIP with nothing to measure is a jump. */
/* ...AND A COMMIT ROW IS THE SAME MOMENT (#166), which is why this handler
   takes a list of surfaces rather than gaining a sibling. A commit row IS
   its own `<details>` where a card CONTAINS one, so the element that resizes
   differs — and that is the only thing that differs. Everything else (the
   snapshot, the regroup, the body ghost, the reveal, reduced motion) is
   shared, and a second handler is how one gesture becomes two that drift.

   The `host` is the member of the keyed list whose box changes: for a card
   that is the `.qa` around the toggle, for a commit row it is the toggle
   itself. `nestedToggle` reads true in both cases (neither `det` is the
   card's own `.qfold`), so the departing body is ghosted by this handler at
   the rect it had rather than clipped from the card-level clone. */
const EXPAND_SURFACES = [
  { sum: '.qa details > summary', host: '.qa[data-qid]', list: QA_LIST },
  // #250: keyed host requires data-aid. Missing-aid answered details still
  // match the summary selector, so preventDefault would leave them dead
  // without a listless fallback (no invented sentinel, no data-keep).
  { sum: '.aq.answered > summary', host: '.aq.answered[data-aid]',
    list: ANSWER_LIST, listlessFallback: true },
  { sum: '.git .commit > summary', host: '.git .commit[data-sha]',
    list: GIT_LIST },
];
/* Human-click fold for a <details> that is not a member of a keyed list
   (#250). Reuses travelCard / revealBody / dreamAway — the qsec shape —
   and deliberately does NOT snapshot open across ticks (no data-keep, no
   positional sentinel). reduced-motion still toggles; only timing drops. */
function foldDetailsLocal(det) {
  if (!det) return;
  if (rmr) { det.open = !det.open; return; }
  const was = det.getBoundingClientRect();
  const corpse = det.open ? det.cloneNode(true) : null;
  det.open = !det.open;
  const now = det.getBoundingClientRect();
  travelCard(det, was, now, false);
  if (det.open) revealBody(det);
  else dreamAway(document.querySelector('.wrap'), corpse, was, now.height);
}
addEventListener('click', e => {
  if (!e.target.closest) return;
  const m = EXPAND_SURFACES.find(s => e.target.closest(s.sum));
  if (!m) return;
  e.preventDefault();
  const det = e.target.closest(m.sum).parentElement;
  const host = det.closest(m.host);
  if (!host) {
    // #250: answered summary matched, but no data-aid host — listless fold
    if (m.listlessFallback) foldDetailsLocal(det);
    return;
  }
  // measured while it still HAS a box: a closed <details> keeps its children
  // in the DOM and gives them no geometry, so the rect has to be taken first
  const leaving = (det.open && nestedToggle(host, det)) ? cardBody(host, det) : [];
  const rects = leaving.map(c => c.getBoundingClientRect());
  const before = snapshotCards(m.list);
  det.open = !det.open;
  regroupCards(before, det, m.list);
  leaving.forEach((c, i) => ghostNode(c, rects[i]));
});
/* the dashboard's questions section (#141) opening and closing — the SAME
   moment one level up (#196), and his report of it was that the questions
   "just appear and disappear".

   It is not a card, so it does not go through `regroupCards`: the cards inside
   it have no geometry at all while the section is shut, and a FLIP from a zero
   rect is a slide in from the page's top-left corner. It is instead the card
   fold with the roles enlarged — a summary that survives, a body that arrives
   or departs, and a HEIGHT that carries everything below it. So it reuses the
   three pieces that already say that: `travelCard` for the height (which is
   what moves reviews, files, status and the tint picker, continuously and for
   free, welded to the section they are following), `revealBody` for the
   arrival, `dreamAway` for the departure.

   THE DEPARTURE'S DIRECTION IS ALREADY RIGHT and that is worth saying out loud
   (#174): the panels below travel UP to close the gap, and the standing ghost
   rises, so this needed no sign of its own. The commits panel is the exception
   here, not the rule.

   The corpse is cloned BEFORE the toggle: a closed <details> keeps its
   children in the DOM and gives them no geometry, so a clone taken afterwards
   is a picture of nothing. Same reason the native toggle is prevented — it
   flips before any event we could measure from.

   Under reduced motion this handler declines the click entirely and the native
   toggle does the work at once, which is the hard contract: timing changes,
   function does not. */
addEventListener('click', e => {
  const sum = e.target.closest && e.target.closest('.qsec > summary');
  if (!sum || rmr) return;
  e.preventDefault();
  const det = sum.parentElement;
  const was = det.getBoundingClientRect();
  const corpse = det.open ? det.cloneNode(true) : null;
  det.open = !det.open;
  const now = det.getBoundingClientRect();
  travelCard(det, was, now, false);
  if (det.open) revealBody(det);
  // clipped to the line the summary still fills, exactly as a folding card
  // clips to the title it keeps
  else dreamAway(document.querySelector('.wrap'), corpse, was, now.height);
});
addEventListener('resize', () => paintIndicators(true));
/* ── the persistent chrome (#110) ─────────────────────────────────────────
   The heading is not content, it is the page's frame: the same + opener, a
   title, and a crumb row, on every route. While it lived inside #view it
   dissolved and was rebuilt on every navigation, which is why a route change
   read as "the elements jump around" rather than as the page opening up. So
   it is a SIBLING of #view — the standing #dreambg already has — it survives
   the route change, and it travels to its new position.

   Crumbs are KEYED, and that is the whole trick: a survivor has to be
   literally the same element before and after, or a FLIP has nothing to
   measure and you get a fade where a glide was asked for. `home` is one
   crumb across three routes even though its text gains and loses an arrow. */
const TITLES = {
  dashboard: () => 'dreamwork watch',
  questions: () => 'questions',
  answers: () => 'answers',
  file: v => esc(v.param || ''),
  review: v => `review<span class="revname">${esc(v.param || '')}</span>`,
};
function crumbsFor(v, d) {
  const home = { k:'home', html:'<a href="/">&larr; dashboard</a>' };
  if (v.name === 'questions' || v.name === 'answers') return [home];
  if (v.name === 'file') return [home,
    { k:'pip', html: pipBtn('/file?p=' + encodeURIComponent(v.param || ''),
                            v.param || 'file') }];
  if (v.name === 'review') return [
    { k:'qs', html:'<a href="/questions">&larr; questions</a>' },
    { k:'home', html:'<a href="/">dashboard</a>' },
    { k:'pip', html: pipBtn('/reviewraw?p=' + encodeURIComponent(v.param || ''),
                            'review: ' + (v.param || '')) }];
  if (!d) return [];
  return [
    { k:'target', html: esc(d.target) },
    { k:'version', html: esc(d.files['skill-version']) },
    { k:'updated', html:'<span id="upd"></span>' },
    // the count is zero whether everything is answered or the file cannot be
    // read, so the crumb must not quietly render the broken case as the calm
    // one (#136) — it is the badge he glances at from every route.
    { k:'openq', html: d.questions_health === 'unreadable'
        ? `<a class="q qh" href="/questions">questions unreadable</a>`
        : d.open_questions > 0
        ? `<a class="q" href="/questions">${d.open_questions} open ` +
          `question${d.open_questions > 1 ? 's' : ''}</a>`
        : `<a class="q" href="/questions" style="color:var(--dimmer)">` +
          `questions</a>` },
  ];
}
/* where the heading sits RIGHT NOW — taken before the column class flips,
   because that flip is what moves everything. */
function chromeSnapshot() {
  const meta = document.getElementById('meta');
  const titleEl = document.querySelector('#chrome .htitle');
  if (!meta || !titleEl) return null;
  const at = new Map();
  for (const el of meta.children) at.set(el.dataset.k, el.getBoundingClientRect());
  return { at, title: titleEl.getBoundingClientRect() };
}
/* a departing crumb dreams away where it stood: lifted out of flow at its own
   rect so the survivors can close the gap underneath it, then dissolved on
   the page's mist idiom rather than simply vanishing. */
function departCrumbs(gone) {
  const ch = document.getElementById('chrome');
  if (!ch) return;
  const org = ch.getBoundingClientRect();
  for (const [el, r] of gone) {
    if (!r) { el.remove(); continue; }
    el.classList.add('crumbout');
    el.style.left = (r.left - org.left) + 'px';
    el.style.top = (r.top - org.top) + 'px';
    el.style.width = r.width + 'px';
    ch.appendChild(el);
    void el.offsetWidth;
    el.classList.add('crumbgone');
    setTimeout(() => el.remove(), 900);
  }
}
function renderChrome(v, d, snap) {
  const meta = document.getElementById('meta');
  const titleEl = document.querySelector('#chrome .htitle');
  if (!meta || !titleEl) return;
  const nextTitle = (TITLES[v.name] || TITLES.dashboard)(v, d);
  const next = crumbsFor(v, d);
  const prev = new Map([...meta.children].map(el => [el.dataset.k, el]));
  const row = [], arrived = [];
  for (const c of next) {
    let el = prev.get(c.k);
    if (el) { prev.delete(c.k); if (el.innerHTML !== c.html) el.innerHTML = c.html; }
    else {
      el = document.createElement('span');
      el.className = 'crumb'; el.dataset.k = c.k; el.innerHTML = c.html;
      if (snap && !rmr) { el.classList.add('dreamin'); arrived.push(el); }
    }
    row.push(el);
  }
  const gone = [...prev].map(([k, el]) => [el, snap ? snap.at.get(k) : null]);
  meta.replaceChildren(...row);
  if (snap && !rmr) departCrumbs(gone); else gone.forEach(([el]) => el.remove());
  if (titleEl.innerHTML !== nextTitle) {
    titleEl.innerHTML = nextTitle;
    if (snap && !rmr) { titleEl.classList.add('dreamin'); arrived.push(titleEl); }
  }
  ages();
  if (!snap || rmr) return;
  // FLIP the survivors from where they stood to where the new row puts them,
  // then release the arrivals from their snapped start state (the enter-snap
  // rule: with an always-on transition, adding the start class animates
  // TOWARD the start value instead of beginning there).
  for (const el of row) {
    const b = snap.at.get(el.dataset.k);
    if (!b) continue;
    const a = el.getBoundingClientRect();
    const dx = b.left - a.left, dy = b.top - a.top;
    if (!dx && !dy) continue;
    el.style.transition = 'none';
    el.style.transform = `translate(${dx}px, ${dy}px)`;
    void el.offsetWidth;
    el.style.transition = '';
    el.style.transform = '';
  }
  requestAnimationFrame(() => arrived.forEach(el => el.classList.remove('dreamin')));
}
/* Dream dissolve: the outgoing view becomes a ghost that liquifies into a
   swirling mist (turbulence displacement + blur grow) and drifts upward as
   it fades; the incoming view coalesces from the same mist and settles
   perfectly crisp. Opacity + transform ride CSS; the mist is an SVG filter
   whose displacement + blur we envelope per-frame here, so the middle of
   the dissolve lingers hazy. The shader stirs in sympathy (pulseWarp).
   reduced-motion swaps instantly — no ghost, no mist. */
const DREAM_MS = 1150;                     // dwell of the whole dissolve
const fxNode = (id, tag) => document.querySelector('#' + id + ' ' + tag);
function crossfade(html, xopts) {
  xopts = xopts || {};
  const viewEl = document.getElementById('view');
  if (rmr) {
    document.body.classList.toggle('review', !!xopts.review);
    setContent(html);
    renderChrome(view, data, null);
    return;
  }
  // The review view is a wider column, so a route change onto or off it
  // RESIZES the page. Measure everything that is about to move BEFORE the
  // class flip that moves it.
  const outRect = viewEl.getBoundingClientRect();
  const outW = outRect.width, outH = outRect.height;
  const outTop = viewEl.offsetTop;
  const snap = chromeSnapshot();
  const ghost = viewEl.cloneNode(true);
  ghost.removeAttribute('id'); ghost.className = 'ghost';
  // a cloned iframe would re-fetch and flash while dissolving — drop it;
  // the ghost only needs the chrome/text to blur away.
  ghost.querySelectorAll('iframe').forEach(f => f.remove());
  viewEl.parentNode.appendChild(ghost);
  // Pin the ghost to the box it was rendered in. It is LEAVING: it should
  // dissolve as it was, not re-wrap every paragraph into a new column while
  // still fully opaque — that reflow, at frame 0 and at full opacity, was
  // the "elements jump around" (#107). The chrome now sits above #view, so
  // the ghost is placed at #view's own offset rather than stretched to the
  // wrapper with `inset:0`.
  ghost.style.top = outTop + 'px';
  ghost.style.width = outW + 'px';
  ghost.style.height = outH + 'px';
  // ...and the column itself glides to its new width rather than snapping
  // (see body.wsliding). The incoming view reflows as it widens, behind the
  // mist and up from opacity 0, so the resize reads as the page opening.
  document.body.classList.add('wsliding');
  document.body.classList.toggle('review', !!xopts.review);
  setContent(html);
  renderChrome(view, data, snap);   // the heading travels; it does not reload
  // measure the docked question's resting rect BEFORE the enter transform,
  // so a shared-element FLIP from the clicked question lands true.
  const dock = document.getElementById('qdock');
  const dockRect = dock ? dock.getBoundingClientRect() : null;
  ghost.style.filter = 'url(#dissolveOut)';
  viewEl.style.filter = 'url(#dissolveIn)';
  viewEl.classList.add('enter');
  void viewEl.offsetWidth;                 // commit the hidden start state
  if (xopts.fromRect && dock && dockRect) flipDock(dock, xopts.fromRect, dockRect);
  if (window.dreambg) window.dreambg.pulseWarp();
  requestAnimationFrame(() => {
    viewEl.classList.remove('enter');      // CSS eases opacity + drift in
    ghost.classList.add('out');            // CSS eases opacity + drift out
  });
  const dOut = fxNode('dissolveOut', 'feDisplacementMap');
  const bOut = fxNode('dissolveOut', 'feGaussianBlur');
  const tOut = fxNode('dissolveOut', 'feTurbulence');
  const dIn = fxNode('dissolveIn', 'feDisplacementMap');
  const bIn = fxNode('dissolveIn', 'feGaussianBlur');
  const tIn = fxNode('dissolveIn', 'feTurbulence');
  // per-destination swirl signature: this arrival's turbulence field
  const seed = SEED[view.name] != null ? SEED[view.name] : 7;
  if (tOut) tOut.setAttribute('seed', seed);
  if (tIn) tIn.setAttribute('seed', seed);
  const smooth = x => x * x * (3 - 2 * x);
  const t0 = performance.now();
  let raf = 0;
  const finish = () => {
    if (raf) cancelAnimationFrame(raf), raf = 0;
    if (ghost.isConnected) ghost.remove();
    viewEl.style.filter = '';              // crisp at rest, zero filter cost
    document.body.classList.remove('wsliding');
  };
  function stepFx(now) {
    const u = Math.min(1, (now - t0) / DREAM_MS);
    const eo = smooth(u);                          // ghost: mist grows in
    if (dOut) dOut.setAttribute('scale', (eo * 25).toFixed(2));
    if (bOut) bOut.setAttribute('stdDeviation', (eo * 3.8).toFixed(2));
    const ui = Math.min(1, Math.max(0, (now - t0 - 160) / (DREAM_MS - 160)));
    const ei = smooth(ui);                         // incoming: mist clears
    if (dIn) dIn.setAttribute('scale', ((1 - ei) * 19).toFixed(2));
    if (bIn) bIn.setAttribute('stdDeviation', ((1 - ei) * 3.2).toFixed(2));
    const bf = (0.009 + eo * 0.009).toFixed(4);    // field tightens: it flows
    if (tOut) tOut.setAttribute('baseFrequency', bf);
    if (tIn) tIn.setAttribute('baseFrequency', bf);
    if (u < 1) raf = requestAnimationFrame(stepFx);
    else finish();
  }
  raf = requestAnimationFrame(stepFx);
  setTimeout(finish, DREAM_MS + 400);      // safety net
}
/* shared-element morph: the docked question travels from where it was
   clicked (its list rect) to its docked rect — auto-animate style, but the
   dream twist is a blurred, low-opacity drift rather than a crisp slide. */
function flipDock(dock, fromRect, toRect) {
  const dx = fromRect.left - toRect.left;
  const dy = fromRect.top - toRect.top;
  const sx = Math.max(0.15, fromRect.width / (toRect.width || 1));
  const sy = Math.max(0.15, fromRect.height / (toRect.height || 1));
  // Lift the travelling question above the page mist (z-index) and keep it
  // luminous, so the eye tracks THIS element gliding to its dock while the
  // rest of the page dissolves behind it — a shared-element morph, but
  // dream-blurred not crisp. Its glide outlasts the mist so the travel reads.
  dock.style.zIndex = '4';
  dock.style.transformOrigin = 'top left';
  dock.style.transform = `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`;
  dock.style.filter = 'blur(5px)';
  dock.style.opacity = '0.4';
  dock.style.transition = 'none';
  void dock.offsetWidth;                    // commit the inverted start
  requestAnimationFrame(() => {
    dock.style.transition =
      'transform 1.15s cubic-bezier(.22,.61,.36,1), filter .95s ease, ' +
      'opacity .85s ease';
    dock.style.transform = 'none';
    dock.style.filter = '';
    dock.style.opacity = '1';
  });
  const clear = () => {
    for (const p of ['transition', 'transform', 'transformOrigin', 'filter',
                     'opacity', 'zIndex']) dock.style[p] = '';
  };
  dock.addEventListener('transitionend', clear, { once: true });
  setTimeout(clear, 1500);                  // safety net
}
async function navigate(name, param, opts) {
  opts = opts || {};
  if (window.__closeCmd) window.__closeCmd();   // context is changing
  // Leaving /answers destroys the ask surface — drop in-flight ownership so a
  // late /ask cannot clear or tick a form that no longer exists, and so a
  // return visit is not blocked by a stuck askInFlight flag (#292 lifecycle).
  if (view && view.name === 'answers' && name !== 'answers')
    invalidateAskFlight();
  view = { name, param, q: opts.q || null };
  applyTitle();
  if (window.dreambg) window.dreambg.setTint(TINT[name] || 0);
  const url = name === 'questions' ? '/questions'
    : name === 'answers' ? '/answers'
    : name === 'file' ? '/file?p=' + encodeURIComponent(param || '')
    : name === 'review' ? '/review?p=' + encodeURIComponent(param || '') +
        (opts.q ? '&q=' + encodeURIComponent(opts.q) : '')
    : '/';
  if (opts.push) history.pushState({ name, param, q: opts.q || null }, '', url);
  const html = await buildCurrent();
  if (opts.transition === false) {
    document.body.classList.toggle('review', name === 'review');
    setContent(html);
    renderChrome(view, data, null);   // first paint: arrive, don't animate
  } else {
    crossfade(html, { fromRect: opts.fromRect, review: name === 'review' });
  }
}
/* only same-document routes are intercepted; external links, new-tab and
   modified clicks fall through to the browser. */
function isInternal(a) {
  if (!a || a.target === '_blank' || a.hasAttribute('download')) return false;
  if (a.origin !== location.origin) return false;
  return a.pathname === '/' || a.pathname === '/questions'
      || a.pathname === '/answers'
      || a.pathname === '/file' || a.pathname === '/review';
}
addEventListener('click', e => {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey ||
      e.shiftKey || e.altKey) return;
  const a = e.target.closest('a');
  if (!isInternal(a)) return;
  e.preventDefault();
  const r = routeOf(a);
  const opts = { push: true, q: r.q };
  // a review link fired from inside a question card seeds the shared-element
  // morph: remember where the question sat so it can travel to its dock.
  if (r.name === 'review' && r.q) {
    const card = a.closest('.qa');
    if (card) opts.fromRect = card.getBoundingClientRect();
  }
  navigate(r.name, r.param, opts);
});
addEventListener('popstate', () => {
  const r = routeOf(location);
  navigate(r.name, r.param, { push: false, q: r.q });
});
/* live tick: re-render the active data-driven view in place, no fade.
   Tolerates the brief unreachable window while the server restarts. */
async function tick() {
  try {
    const { gen, mtime } = parseMtime(await (await fetch('/mtime')).text());
    if (serverGen === null) serverGen = gen;
    else if (gen && gen !== serverGen) { location.reload(); return; }
    if (mtime !== lastMtime && Date.now() >= holdRerenderUntil) {
      lastMtime = mtime; fetchedAt = Date.now();
      const wasGit = gitKey(data), wasBurn = burnKey(data);
      setData(await (await fetch('/data.json')).json());
      // the data lands instantly; surviving cards then travel from where
      // they were to where the new grouping put them (#104/#77). What the
      // human is mid-way through typing rides across the swap (#118).
      const tickView = view;
      const kept = snapshotCardState();
      const askKept = snapshotAskState();
      const reviewFrame = snapshotReviewFrame();
      const folds = snapshotFolds();
      const before = snapshotCards();
      // Exact artifact mtimes can reorder these rows on any data tick. Keep
      // their filename identity and reuse the list FLIP rather than snapping.
      const reviewBefore = view.name === 'dashboard'
        ? snapshotCards(REVIEW_LIST) : null;
      // #151: the commits panel animates on a NEW COMMIT, never on a tick.
      // The dashboard re-renders whenever ANY watched file changes — the loop
      // rewrites status.json every few seconds — so rows travelling on a tick
      // would be motion with nothing behind it, which is the opt-in rule. The
      // sha sequence is the thing that means "a commit happened", and it is
      // compared before the swap because after it there is nothing to compare.
      const gitBefore = (view.name === 'dashboard' && gitKey(data) !== wasGit)
        ? snapshotCards(GIT_LIST) : null;
      // the same gate for the same reason, one panel down (#142)
      const burnBefore = (view.name === 'dashboard' && burnKey(data) !== wasBurn)
        ? snapshotBars() : null;
      // Reuse the router's current-view seam so every data-backed route,
      // including the review dock, receives the same live snapshot (#271).
      // Card-owned state rides the existing #118/#269 discipline below.
      const html = await buildCurrent();
      // buildCurrent may await /filedata. A user navigation made during that
      // wait owns the screen; stale tick work must never overwrite it.
      if (view !== tickView) return setTimeout(tick, 2000);
      setLiveContent(html);
      restoreReviewFrame(reviewFrame);
      // FOLDS FIRST, then the cards inside them (#179). Both must land before
      // the regroups, which MEASURE — a section restored afterwards would be
      // measured shut and then opened underneath the animation — but the
      // order BETWEEN them is not free: a card's box is restored by putting
      // his text back and putting the CARET back in it, and focus() inside a
      // closed <details> does nothing and reports nothing. On the dashboard
      // every card lives inside `.qsec`, which renders closed, so restoring
      // the card first re-filled the box and silently dropped the focus.
      restoreFolds(folds);
      restoreCardState(kept);
      restoreAskState(askKept);
      regroupCards(before);
      regroupCards(reviewBefore, null, REVIEW_LIST);
      regroupCards(gitBefore, null, GIT_LIST);
      regroupBars(burnBefore);
      // the crumbs carry live numbers too (open count, version) — and the
      // tick re-renders in place, instantly, so they never animate
      renderChrome(view, data, null);
    }
  } catch (e) { /* server restarting; retry next tick */ }
  setTimeout(tick, 2000);
}
setInterval(ages, 1000);
(function () {                              // initial view from the URL
  const r = routeOf(location);
  navigate(r.name, r.param, { push: false, transition: false, q: r.q });
  tick();
})();
"""

COMMAND_JS = """
/* Command palette (#71): the heading's + opener reveals a small form to
   steer the dreaming loop without a chat turn. Submitting POSTs /command,
   which drops a source-tagged line into watch-events.log — the loop's tail
   monitor wakes on it (same transport as answers). A pop-out (Document
   Picture-in-Picture, window.open fallback) keeps the form handy while the
   main tab navigates; it identifies its project so multi-target popouts
   don't blur together. reduced-motion skips the drift, never the function. */
function ripple(x, y) {                     // soft expanding ring, dream feel
  if (rmr) return;
  const r = document.createElement('div');
  r.className = 'ripple';
  const s = 14;
  r.style.left = (x - s / 2) + 'px'; r.style.top = (y - s / 2) + 'px';
  r.style.width = r.style.height = s + 'px';
  r.style.transition = 'transform 1.1s cubic-bezier(.22,.61,.36,1), ' +
    'opacity 1.1s ease';
  r.style.opacity = '0.5';
  document.body.appendChild(r);
  requestAnimationFrame(() => {
    r.style.transform = 'scale(18)'; r.style.opacity = '0';
  });
  setTimeout(() => r.remove(), 1200);
}
/* the popped-out window is a bare document — give it its own dark theme and
   an identity band tinted like the page it came from. */
const POPOUT_CSS = `
  :root { color-scheme:dark; }
  * { scrollbar-width:thin; scrollbar-color:#4b5563 transparent; }
  ::-webkit-scrollbar { width:7px; height:7px; }
  ::-webkit-scrollbar-track { background:transparent; }
  ::-webkit-scrollbar-thumb { background:#4b5563; border-radius:4px; }
  ::-webkit-scrollbar-thumb:hover { background:#6b7280; }
  body { margin:0; background:#0b0f19; color:#d1d5db;
    font-family:ui-monospace,'JetBrains Mono',monospace; font-size:13px; }
  #dreambg { position:fixed; inset:0; z-index:-1; width:100vw;
             height:100vh; }
  .strip { height:4px; background:__STRIP__; }
  .phead { padding:.7rem .9rem .1rem; }
  .ptitle { color:#f3f4f6; }
  .ppath { color:#6b7280; font-size:.72rem; word-break:break-all;
    margin-top:.15rem; }
  form { padding:.3rem .9rem .9rem; }
  .plabel { color:#6b7280; text-transform:uppercase; letter-spacing:.08em;
    font-size:.66rem; margin:.6rem 0 .3rem; }
  select, textarea { width:100%; box-sizing:border-box; background:#111827;
    color:#d1d5db; border:1px solid #1f2937; border-radius:4px; font:inherit;
    padding:.4rem; margin:.2rem 0; }
  textarea { min-height:3.2rem; resize:vertical; }
  button { background:#1e293b; color:__ACCENT__; border:1px solid #334155;
    border-radius:4px; font:inherit; padding:.3rem .9rem; cursor:pointer;
    margin-top:.4rem; }
  .pmsg { color:#6b7280; font-size:.7rem; min-height:1em; margin-top:.4rem;
    transition:opacity .35s ease,filter .35s ease,transform .35s cubic-bezier(.32,.1,.2,1); }
  .pmsg.ok { color:__ACCENT__; }
  .pmsg.dreamin { transition:none;opacity:0;filter:blur(7px);transform:translateY(5px); }
  .pmsg.depart { opacity:0;filter:blur(7px);transform:translateY(-5px); }
  @media (prefers-reduced-motion:reduce){.pmsg{transition:none!important}}
  iframe { border:0; width:100%; height:calc(100vh - 54px); display:block;
    background:#0b0f19; }`;
const POPOUT_BODY = (base, path) => `
  <div class="strip"></div>
  <div class="phead"><div class="ptitle">+ command &middot; ${esc(base)}</div>
    <div class="ppath">${esc(path)}</div></div>
  <form id="pform" autocomplete="off">
    <div class="plabel">command the dream</div>
    <select id="pkind">${COMMANDS.map(c =>
      `<option value="${c.kind}">${esc(c.label)}</option>`).join('')}</select>
    <textarea id="ptext" placeholder="a thought for the dream…"></textarea>
    <div><button type="submit">send</button></div>
    <div class="pmsg" id="pmsg" aria-live="polite"></div>
  </form>`;
/* Every popped-out window (command form OR a doc/review iframe) wears the
   same identity: a hue-tinted band, the project basename + full path, and a
   matching title — so multiple target popouts never blur together. */
function popoutShell(w, base, path, tint, titleWord) {
  const doc = w.document;
  doc.title = titleWord + ' · ' + base + ' · dreamwork';
  const warm = tint >= 0;
  const accent = warm ? '#c4b5fd' : '#a5b4fc';
  const strip = warm ? 'linear-gradient(90deg,#6d5bd0,#a855f7)'
                     : 'linear-gradient(90deg,#4f5bd5,#5b8def)';
  doc.head.innerHTML = '<meta charset="utf-8">';
  const st = doc.createElement('style');
  st.textContent = POPOUT_CSS.replace(/__ACCENT__/g, accent)
                             .replace('__STRIP__', strip);
  doc.head.appendChild(st);
  return doc;
}
const popHead = (label, base, path) =>
  `<div class="strip"></div><div class="phead">` +
  `<div class="ptitle">${esc(label)} &middot; ${esc(base)}</div>` +
  `<div class="ppath">${esc(path)}</div></div>`;
/* Every floated window dreams the same dream. The shader is world-space
   anchored (#74): it reads ITS OWN window's screenX/screenY, so a popout
   parked anywhere over the page samples the identical deterministic field
   and the pattern stays continuous across the seam. Mounted after `fill`,
   because the fills assign body.innerHTML and would wipe the canvas. */
function mountPopoutBg(w, tint) {
  try {
    const cv = w.document.createElement('canvas');
    cv.id = 'dreambg';
    w.document.body.appendChild(cv);
    const bg = mountDreambg(w, cv, {});     // no dev overlay, no layer switcher
    if (!bg) return;
    bg.setTint(tint);                       // wear the spawning view's hue
    w.addEventListener('pagehide', () => bg.stop());
  } catch (e) { /* no WebGL here: the flat #0b0f19 still reads fine */ }
}
/* open a floating window — Document Picture-in-Picture where available (stays
   put while the main tab navigates), else a positioned window.open — and let
   `fill` render into it with the shared identity. */
async function openPopout(name, size, fill) {
  const d = await ensureData();
  const path = (d && d.target) || '';
  const base = path.split('/').filter(Boolean).pop() || 'dreamwork';
  const tint = TINT[view.name] || 0;
  let w = null;
  if (window.documentPictureInPicture &&
      documentPictureInPicture.requestWindow) {
    try { w = await documentPictureInPicture.requestWindow(size); }
    catch (e) { /* fall through */ }
  }
  if (!w) w = window.open('', name + '_' + base,
    'width=' + (size.width + 20) + ',height=' + (size.height + 20) +
    ',left=80,top=80');
  if (w) { fill(w, base, path, tint); mountPopoutBg(w, tint); }
  return w;
}
/* #255 — one confirmation lifecycle for every composer surface. Success is
   valid even when another draft begins, so it owns its ~5s readable hold and
   atmospheric departure. False/error claims withdraw it immediately. Closing
   a surface is destruction: clear synchronously and cancel old callbacks. */
const CMD_CONFIRM_HOLD_MS = 5000;
function confirmationFor(doc,id,baseClass,reduced) {
  const view=doc.defaultView||window,node=()=>doc.getElementById(id);
  let holdT=0,clearT=0,generation=0,departEnd=null;
  const cancel=()=>{
    view.clearTimeout(holdT);view.clearTimeout(clearT);holdT=clearT=0;
    const m=node();if(m&&departEnd)m.removeEventListener('transitionend',departEnd);
    departEnd=null;
  };
  const clear=()=>{generation++;cancel();const m=node();if(m){m.textContent='';m.className=baseClass;}};
  const show=(text,ok,lifecycle,expectedGeneration)=>{
    if(expectedGeneration!==undefined&&expectedGeneration!==generation)return false;
    generation++;const mine=generation;cancel();const m=node();if(!m)return false;
    m.className=baseClass+(ok?' ok':'');m.textContent=text;
    if(!reduced&&text){m.classList.add('dreamin');void m.offsetWidth;
      view.requestAnimationFrame(()=>{if(mine===generation)m.classList.remove('dreamin')});}
    if(lifecycle)holdT=view.setTimeout(()=>{if(mine!==generation)return;
      if(reduced){clear();return;}
      m.classList.add('depart');
      departEnd=()=>{if(mine===generation)clear();};
      m.addEventListener('transitionend',departEnd,{once:true});
      clearT=view.setTimeout(departEnd,650);
    },CMD_CONFIRM_HOLD_MS);
    return true;
  };
  const begin=()=>{
    clear();const mine=generation;
    return {success:()=>show('sent to the dream',true,true,mine),
      claim:(text,ok=false)=>show(text,ok,false,mine)};
  };
  return {begin,claim:(text,ok=false)=>show(text,ok,false),clear};
}
async function requestPopout() {
  const w = await openPopout('dreamcmd', { width: 340, height: 320 },
    (w, base, path, tint) => {
      const doc = popoutShell(w, base, path, tint, '+ command');
      doc.body.innerHTML = POPOUT_BODY(base, path);
      const endpoint = location.origin + '/command';
      // captured at SPAWN, not read at submit: this window floats free while
      // the main tab navigates on, and its own location is about:blank. Where
      // it was popped out FROM is the honest hint, and it is also the thing he
      // popped it out to keep beside him.
      const from = fromPath();
      const confirmation=confirmationFor(doc,'pmsg','pmsg',w.matchMedia('(prefers-reduced-motion: reduce)').matches);
      w.addEventListener('pagehide',confirmation.clear,{once:true});
      doc.addEventListener('keydown', ev => {        // Ctrl/Cmd+Enter submits
        if ((ev.ctrlKey || ev.metaKey) && ev.key === 'Enter') {
          ev.preventDefault(); doc.getElementById('pform').requestSubmit();
        }
      });
      doc.getElementById('pform').addEventListener('submit', async ev => {
        ev.preventDefault();
        const kind = doc.getElementById('pkind').value;
        const text = doc.getElementById('ptext').value.trim();
        if (kind !== 'do-next' && !text) {
          confirmation.claim('a thought is needed'); return;
        }
        const attempt=confirmation.begin();
        try {
          const r = await fetch(endpoint, { method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ kind, text, from }) });
          if (r.ok) { if(!attempt.success())return; doc.getElementById('ptext').value = ''; }
          else attempt.claim('rejected (' + r.status + ')');
        } catch (e) { attempt.claim('no connection'); }
      });
    });
  if (w && window.__closeCmd) window.__closeCmd();
}
/* pop a doc/review into a floating iframe window (kept identity header) so it
   stays handy while the main tab navigates. */
function popoutDoc(url, label) {
  openPopout('dreamdoc', { width: 620, height: 560 },
    (w, base, path, tint) => {
      const doc = popoutShell(w, base, path, tint, label);
      doc.body.innerHTML = popHead(label, base, path) +
        `<iframe src="${esc(url)}" title="${esc(label)}"></iframe>`;
    });
}
(function () {
  const pal = document.getElementById('cmdpalette');
  if (!pal) return;
  const confirmation=confirmationFor(document,'cmdmsg','cmdmsg',rmr);
  /* ── the status line ARRIVES, it does not appear (#159) ──────────────────
     It used to be four bare `textContent` assignments: the text landed,
     `:empty` stopped applying, and the line was simply THERE on the next
     paint. Everything else on this page that turns up eases in, and this is
     the composer's only feedback that a steer reached the loop at all.

     ONE implementation, for the usual reason: there were four assignment
     sites and a fifth message would otherwise have arrived differently from
     the other four.

     The enter is the page's standing `.dreamin` snap — which only started
     working at all today (#154), so this is its first new user. The forced
     reflow is not decoration: without a style recalc between adding the class
     and removing it, the element never commits opacity 0 and the transition
     has nothing to run from. That IS #154, and it is cheaper to be correct by
     construction here than to rely on some other read forcing the layout. */
  const setCmdMsg=(text,ok)=>confirmation.claim(text,ok);
  /* A successful claim departs through confirmationFor. Clearing here means
     destruction (manual close/route change), so it is intentionally instant:
     keeping a dead surface's timer alive can erase a later message after the
     composer reopens. False/error claims replace success immediately for the
     same reason — a false statement must not linger through a departure. */
  const clearCmdMsg=confirmation.clear;
  let open = false;
  const CMD_GAP = 18;            // breathing room under the +/× opener
  /* ── the panel does not close under him (#131 / #291) ────────────────────
     His words: "if on the composer, someone enters something, ctrl+enter
     submits, then starts typing again, the composer should not fade away.
     also the timeout before fading away should be increased by 1.5x."
     And later (#291): it should auto-disappear ~1.5s after a successful
     command, not after the confirmation's ~5s hold (#255 accidentally
     tied the two together).

     The auto-dismiss is a courtesy — it gets the panel out of the way once
     the thought has landed — and a courtesy must never take a channel away
     from someone who is still using it. That is the same rule as #118: what
     the human is in the middle of doing outranks anything the page decided
     on a timer. Any sign of him still being in here cancels the dismiss, and
     `composing` covers the race where he resumes DURING the POST, before
     there is a timer to cancel. The confirmation lifecycle is independent:
     typing cancels only this timer; left alone, panel close is destruction
     and hard-clears the line with the panel. */
  const CMD_DISMISS_MS = 1425;               // was 950; his 1.5x (#131/#291)
  let dismissT = 0, composing = false;
  const cancelDismiss = () => { clearTimeout(dismissT); dismissT = 0; };
  /* ── the half-typed thought survives a reload (#163) ─────────────────────
     The panel already keeps its text across a close and across a route
     change — it lives outside `#view`, so nothing rebuilds it. What loses his
     words is a RELOAD: the tab crashing, him refreshing, the server restarting
     and `tick` calling `location.reload()` on a new generation. That last one
     is the page doing it TO him.

     BROWSER STORAGE IS RIGHT HERE AND WAS WRONG FOR #143, and the difference
     is worth stating because the two look identical from a distance. A tint is
     a setting ABOUT the project: it should follow the project to another
     machine, so it lives in `.dreamwork/watch-tint` and is committable. An
     unsent draft is a thought in progress that he has not chosen to send to
     anyone — writing it to the repo would publish it, and #199 already gives
     the server a verbatim record of everything he DID send. So this one stays
     in the browser, on this machine, and never travels.

     PARTITIONED BY `data.target`, the absolute project path — not by the
     project NAME, because two checkouts can share a basename and a draft
     surfacing under the wrong loop is worse than a lost one. With no target
     yet (the first fetch has not landed) nothing is read or written at all,
     rather than everything sharing an empty key.

     THE TWO-WINDOW SEMANTIC, stated rather than discovered: he runs several
     windows per project — that is what #143 syncs a tint for — and they share
     one key, so the store holds THE MOST RECENT unsent thought on this
     project. A restore never overwrites a box that already has text in it
     (#118's rule: what he is in the middle of outranks anything stored), so
     two live composers never fight; only the stored copy is last-write-wins.

     IT RESTORES SILENTLY, and that is a decision about a different channel.
     `setCmdMsg` is the composer's one line for whether his command LANDED
     (#159), and putting "draft restored" on it would spend the one place he
     looks for a send confirmation on something that is not one. The text
     being in the box is the statement. */
  const draftKey = () => {
    const tgt = (typeof data !== 'undefined' && data && data.target) || '';
    return tgt ? 'dw:draft:' + tgt : '';
  };
  function saveDraft() {
    const key = draftKey(), t = document.getElementById('cmdtext');
    if (!key || !t) return;
    // never let a storage failure break the composer: private mode, a full
    // quota and a disabled origin all throw here, and none of them is a
    // reason he cannot send a command (`log_submission`'s rule, client-side)
    try {
      if (t.value) localStorage.setItem(key,
        JSON.stringify({ t: t.value, k: activeKind }));
      else localStorage.removeItem(key);
    } catch (e) { /* storage unavailable; the live box is unaffected */ }
  }
  /* ONLY on a successful send, which is the whole contract. A draft that is
     cleared on close, on blur, or on a rejected POST is a draft that
     disappears at exactly the moments he most needs it back. */
  function clearDraft() {
    const key = draftKey();
    if (!key) return;
    try { localStorage.removeItem(key); } catch (e) {}
  }
  function restoreDraft() {
    const key = draftKey(), t = document.getElementById('cmdtext');
    if (!key || !t || t.value) return;   // a live box outranks storage (#118)
    let d = null;
    try { d = JSON.parse(localStorage.getItem(key) || 'null'); } catch (e) {}
    if (!d || typeof d.t !== 'string' || !d.t) return;
    t.value = d.t;
    // the kind travels with the text, because the kind is WHERE THE TEXT GOES
    // (#103's rule for a card's mode, one surface over). Validated against the
    // live vocabulary: a plugin's command can disappear between sessions, and
    // silently sending his words as the wrong kind is worse than defaulting.
    if (d.k && COMMANDS.some(c => c.kind === d.k)) setKind(d.k);
  }
  // The composer is position:fixed, but `.wrap` carries `perspective`, which
  // makes IT the containing block — so `top`/`left` are measured from .wrap,
  // not the viewport. Rects are viewport coords, so subtract that origin or
  // the panel drifts right of the + and hangs a body-padding too low.
  function fixedOrigin() {
    const cb = document.querySelector('.wrap');
    if (!cb) return { x: 0, y: 0 };
    const b = cb.getBoundingClientRect();
    return { x: b.left, y: b.top };
  }
  function place() {
    const plus = document.getElementById('cmdplus');
    if (!plus) return;
    const r = plus.getBoundingClientRect();
    const w = pal.offsetWidth || Math.min(innerWidth * 0.92, 340);
    const o = fixedOrigin();
    // The opener rotates 45deg into an × when open, which swells its painted
    // box by its half-diagonal. Anchor off the centre (invariant under that
    // rotation) and the painted extent, so the breathing room is what the eye
    // sees and is the same whether we place while closed or while open.
    const bw = plus.offsetWidth || r.width;          // layout box, transform-free
    const bh = plus.offsetHeight || r.height;
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const left = cx - bw / 2;
    const bottom = cy + (bw + bh) * Math.SQRT2 / 4;   // rotated half-height
    pal.style.left =
      (Math.max(8, Math.min(left, innerWidth - w - 8)) - o.x) + 'px';
    pal.style.top = (bottom + CMD_GAP - o.y) + 'px';
  }
  // Command selection: a radiogroup of buttons with one background indicator
  // that slides between them. `snap` lands it without a slide — used for the
  // first placement and for reflows, because an indicator that animates from
  // its 0-width start reads as a glitch, not a choice (the enter-snap rule).
  const kindsEl = document.getElementById('cmdkinds');
  const menuEl = document.getElementById('cmdmenu');
  let activeKind = (COMMANDS[0] || {}).kind;
  // The row carries the common kinds PLUS the active one when it is uncommon,
  // so whatever is selected always has a button for the indicator to sit on.
  // Rebuilding is membership-only: a common->common switch leaves the row
  // (and so the indicator) alone, which is what lets it slide.
  let rowKinds = [];
  const rowWant = () => COMMANDS
    .filter(c => c.common || c.kind === activeKind).map(c => c.kind);
  function renderKinds() {
    if (!kindsEl) return false;
    const want = rowWant();
    if (want.join('\\u0000') === rowKinds.join('\\u0000')) return false;
    rowKinds = want;
    kindsEl.innerHTML =
      '<span class="sgind cmdind" id="cmdind" aria-hidden="true"></span>' +
      COMMANDS.filter(c => want.indexOf(c.kind) >= 0).map(c =>
        '<button type="button" class="sgbtn cmdkind" data-kind="' + esc(c.kind) +
        // the row carries no visible plugin mark, on purpose: it is a MODE
        // switch whose one job is saying where the text goes, its width is
        // load-bearing (#162 is the row wrapping and taking the panel with
        // it), and by the time a kind is in the row he has already read the
        // attribution in the menu, which is the only place one is offered.
        // The title still names it, because the row is also where he comes
        // back to a choice he made an hour ago.
        '" role="radio" aria-checked="false" title="' + esc(c.desc) +
        (c.plugin ? esc(' · from ' + c.plugin) : '') + '">' +
        esc(c.label) + '</button>').join('');
    return true;
  }
  // The menu lists EVERY kind with its description — the discoverability
  // surface, and the only place a plugin's command is ever offered (#86).
  function menuItem(c) {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'cmdmenuitem';
    b.setAttribute('role', 'menuitem');
    b.dataset.kind = c.kind;
    // WHO ANSWERS THIS, named on the item itself, at the quietest step of the
    // ramp. A plugin command can vanish between sessions and a core one
    // cannot, so the two are not interchangeable and the menu says which is
    // which — quietly, because on the overwhelmingly common day no plugin
    // declares anything and this is one more word in a small menu.
    b.innerHTML = '<span class="cmk">' + esc(c.label) + '</span>' +
      (c.plugin ? '<span class="cmpl">' + esc(c.plugin) + '</span>' : '') +
      '<span class="cmd">' + esc(c.desc) + '</span>';
    return b;
  }
  /* Reconciled by KIND, not rebuilt, and that is what makes the arrival
     legible: the nodes it returns are exactly the ones that were not here
     before, so only they carry the enter idiom. An innerHTML rebuild would
     re-create the core items too — identical pixels, but any hover or focus
     he was holding would be dropped, and there would be no way to tell an
     arriving item from a surviving one. */
  function renderMenu() {
    if (!menuEl) return [];
    const have = new Map(
      [...menuEl.children].map(n => [n.dataset.kind, n]));
    const arrived = [], frag = document.createDocumentFragment();
    for (const c of COMMANDS) {
      let n = have.get(c.kind);
      if (n) have.delete(c.kind);
      else { n = menuItem(c); arrived.push(n); }
      frag.appendChild(n);              // appending a live node MOVES it
    }
    // written whole, so a plugin unloading is the ABSENCE of an entry rather
    // than a remembered deletion — the same move the file itself makes
    have.forEach(n => n.remove());
    menuEl.appendChild(frag);
    return arrived;
  }
  /* ── the plugin half of the vocabulary (#86) ─────────────────────────────
     `writing-plugins.md` has granted plugins their own command namespace in
     prose for as long as there have been plugins, and the composer could not
     render one: the contract promised what the UI could not show. It rides
     /data.json, so this runs on every tick and must be cheap and idempotent.

     COMPARED WHOLE, because the file is WRITTEN whole. Anything finer would
     be a second model of a file whose entire shape is "this is the current
     set", and the two could disagree. */
  let pluginKey = '[]';
  function syncPluginCommands(list) {
    const next = Array.isArray(list) ? list : [];
    const key = JSON.stringify(next);
    if (key === pluginKey) return [];      // every tick but the ones that matter
    pluginKey = key;
    COMMANDS = CORE_COMMANDS.concat(next);
    const arrived = renderMenu();
    /* His selection can be a command that no longer exists — he chose it, the
       plugin unloaded, and the row would still offer a kind the server now
       refuses with a bare 400. Fall back to the first core kind, which cannot
       go away. */
    if (!COMMANDS.some(c => c.kind === activeKind))
      setKind((CORE_COMMANDS[0] || {}).kind);
    else
      setKind(activeKind);                 // re-mark `.on` on the new nodes
    /* THE ARRIVAL, and the condition on it is not an exemption.
       A menu that is shut is not showing him anything, so nothing has
       appeared: when he next hovers it open, the menu's own reveal is what
       brings these in, and that gesture already obeys the page. What needs a
       gesture of its own is the case where the set changes UNDER HIS EYE —
       the menu open in front of him — and that is the one animated here. */
    if (!rmr && menuEl && getComputedStyle(menuEl).visibility === 'visible')
      arrived.forEach(n => {
        n.classList.add('qreveal', 'dreamin');
        requestAnimationFrame(() => n.classList.remove('dreamin'));
        setTimeout(() => n.classList.remove('qreveal'), CARD_MS + 150);
      });
    return arrived;
  }
  // the tick is the only caller; exposed because the composer is its own IIFE
  window.dwPluginCommands = syncPluginCommands;
  // the same slideIndicator every question card uses (#103) — one
  // implementation, so the composer and the cards can never drift apart
  const moveIndicator = snap => slideIndicator(kindsEl, snap);
  function setKind(kind) {
    activeKind = kind;
    // a rebuilt row has a brand-new 0-width indicator, so land it rather than
    // slide it up from nothing (the enter-snap rule)
    const rebuilt = renderKinds();
    kindsEl.querySelectorAll('.cmdkind').forEach(b => {
      const on = b.dataset.kind === kind;
      b.classList.toggle('on', on);
      b.setAttribute('aria-checked', on ? 'true' : 'false');
    });
    if (menuEl) menuEl.querySelectorAll('.cmdmenuitem').forEach(b =>
      b.classList.toggle('on', b.dataset.kind === kind));
    moveIndicator(rebuilt);
  }
  /* The saves hang off HIS choice, never off `setKind` itself. `setKind` also
     runs at init and from `restoreDraft`, and saving there would write the
     empty box over a stored draft before it was ever read — deleting the
     feature at the moment it was supposed to work. */
  if (kindsEl) kindsEl.addEventListener('click', e => {
    const b = e.target.closest('.cmdkind');
    if (b) { e.preventDefault(); setKind(b.dataset.kind); saveDraft(); }
  });
  if (menuEl) menuEl.addEventListener('click', e => {
    const b = e.target.closest('.cmdmenuitem');
    if (b) { e.preventDefault(); setKind(b.dataset.kind); saveDraft(); }
  });
  // the menu opens on hover/focus in CSS; mirror that into aria-expanded,
  // which CSS cannot set.
  /* ── the history (#165) ──────────────────────────────────────────────────
     THE SOURCE IS #175's CLIENT LOG, and that is a decision the task's own
     ledger line did not make — it said `watch-events.log`, written before #199
     and #175 existed. Three sources exist now and they are not
     interchangeable:

       · `watch-events.log` — has the route (#126), covers every window and
         every machine that reached this server, but it is a RENDERING: one
         line per act, summarised for an agent to read. It cannot say whether
         a submission landed, because a line is only written once one did.
       · `.dreamwork/submissions.log` (#199) — verbatim and complete, but
         written BEFORE the work, so it is pre-outcome by construction.
       · #175's client log — has the OUTCOME, which is the field he cannot
         recover any other way, and is the only witness to a submission the
         server refused or never heard.

     A history is for recall and recovery, so the outcome decides it. Mixing
     the three would mean explaining, on every row, which of them that row
     came from and what it therefore cannot tell him — a panel that has to
     apologise per row is worse than a narrow one that says its limit once.

     SO IT SAYS ITS LIMIT ONCE, at the foot: this browser only. The ledger
     asked for exactly that honesty about `watch-events.log` being machine-
     local, and it applies more sharply here, not less.

     ONE LIST WITH THE KIND MARKED, per the ledger — he does not think of an
     answer as a different act from a command, and two lists would ask him to
     remember which one he used. */
  const HIST_MAX = 40;
  const histRow = r => {
    const bad = r.outcome === 'rejected' || r.outcome === 'unreachable';
    const why = r.outcome === 'rejected' ? '(' + r.status + ')'
              : r.outcome === 'unreachable' ? '(never sent)' : '';
    return '<div class="cmdhrow' + (bad ? ' bad' : '') +
      (r.outcome === 'pending' ? ' pending' : '') + '">' +
      '<span class="cmdhkind">' + esc(r.kind || r.path || '?') + '</span>' +
      '<span class="cmdhtext" title="' + esc(r.text || '') + '">' +
      esc(r.text || '') + '</span>' +
      (why ? '<span class="cmdhwhy">' + esc(why) + '</span>' : '') +
      '<span class="cmdhage age" data-at="' + (r.at / 1000) + '"></span></div>';
  };
  async function renderHist() {
    const body = document.getElementById('cmdhistbody');
    const sum = document.getElementById('cmdhistsum');
    if (!body) return;
    const recs = (await subsAll()) || [];
    // newest first: the thing he is looking for is nearly always the last
    // thing he did, and `id` is the store's own order (#175)
    const rows = recs.slice().sort((a, b) => b.id - a.id).slice(0, HIST_MAX);
    if (sum) sum.textContent = rows.length ? 'history · ' + recs.length
                                           : 'history';
    body.innerHTML = rows.length
      ? rows.map(histRow).join('') +
        '<div class="cmdhnote">what this browser has sent, on this project. ' +
        'other windows and other machines keep their own.</div>'
      // THE EMPTY STATE SAYS "NOT HERE", NEVER "NOT AT ALL". This browser is
      // one witness of several: a fresh profile, a second machine, or a
      // cleared store all land here, and "you have sent nothing" would be a
      // confident false statement about his own history. Same sentence shape
      // as the populated footer, so the scope reads identically either way.
      : '<div class="cmdhnote">nothing sent from this browser yet. other ' +
        'windows and other machines keep their own.</div>';
    ages();                       // the ages tick with everything else (#132)
    // it ARRIVES, on the page's one enter idiom — the rows are fetched async,
    // so without this they appear a frame after the panel finished opening,
    // which is the snap #196 was about at a smaller size
    if (!rmr) {
      body.classList.add('qreveal', 'dreamin');
      requestAnimationFrame(() => body.classList.remove('dreamin'));
      setTimeout(() => body.classList.remove('qreveal'), CARD_MS + 150);
    }
  }
  const histEl = document.getElementById('cmdhist');
  if (histEl) histEl.addEventListener('toggle', () => {
    if (histEl.open) renderHist();
  });
  const moreEl = document.getElementById('cmdmore');
  if (moreEl) {
    const btn = moreEl.querySelector('.cmdmorebtn');
    const expose = v => btn && btn.setAttribute('aria-expanded', v);
    moreEl.addEventListener('pointerenter', () => expose('true'));
    moreEl.addEventListener('pointerleave', () => expose('false'));
    moreEl.addEventListener('focusin', () => expose('true'));
    moreEl.addEventListener('focusout', () => expose('false'));
  }
  renderMenu();
  setKind(activeKind);              // paint the initial row + selection
  // the shell is served before /data.json returns, so the plugin half is
  // normally still in flight here and arrives via the tick below; this covers
  // the case where it landed first and nothing would otherwise ask for it
  if (data) syncPluginCommands(data.plugin_commands);
  /* he is composing again, so the panel is not finished with */
  for (const ev of ['input', 'keydown', 'pointerdown'])
    pal.addEventListener(ev, () => {
      composing = true;
      // NO DEBOUNCE, deliberately: a debounce is a window in which his words
      // are lost, which is the one thing this exists to prevent. The value is
      // a single command, so the write is far too small to be worth batching.
      if (ev === 'input') saveDraft();
      if (dismissT) cancelDismiss();
    });
  function openCmd() {
    cancelDismiss(); composing = false;
    place(); pal.classList.add('open'); open = true;
    // before the indicator moves: a restored draft may carry a KIND, and
    // `setKind` is what the indicator is being landed under (#163)
    restoreDraft();
    moveIndicator(true);          // land under the active kind, never slide in
    const plus = document.getElementById('cmdplus');
    if (plus) plus.classList.add('on');
    const t = document.getElementById('cmdtext');
    if (t) setTimeout(() => t.focus(), rmr ? 0 : 140);
  }
  function closeCmd() {
    cancelDismiss();
    pal.classList.remove('open'); open = false;
    document.querySelectorAll('#cmdplus.on').forEach(p =>
      p.classList.remove('on'));
    clearCmdMsg();
  }
  window.__closeCmd = closeCmd;
  document.addEventListener('submit', e => {
    if (e.target && e.target.id === 'askform') {
      e.preventDefault(); sendAsk(e.target);
    }
  });
  document.addEventListener('click', e => {
    const pip = e.target.closest && e.target.closest('.pipbtn');
    if (pip) { e.preventDefault();
      popoutDoc(pip.dataset.pipurl, pip.dataset.piplabel || 'doc'); return; }
    const plus = e.target.closest && e.target.closest('#cmdplus');
    if (plus) { e.preventDefault(); open ? closeCmd() : openCmd(); return; }
    if (open && e.target.closest && !e.target.closest('#cmdpalette')) closeCmd();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && open) closeCmd();
  });
  // Ctrl/Cmd+Enter submits from a text field: an answer box (anywhere —
  // questions view, review dock), the command palette, or the /answers
  // ask box (#292 — same shortcut, same one-submit rule).
  document.addEventListener('keydown', e => {
    if (!((e.ctrlKey || e.metaKey) && e.key === 'Enter')) return;
    const t = e.target;
    if (t && t.tagName === 'TEXTAREA' && /^qi[oa]\\d+$/.test(t.id)) {
      e.preventDefault(); submitCard(t.id.slice(2));
    } else if (t && t.id === 'cmdtext') {
      e.preventDefault();
      document.getElementById('cmdform').requestSubmit();
    } else if (t && t.id === 'askbox') {
      e.preventDefault();
      const form = document.getElementById('askform');
      if (form) form.requestSubmit();
    }
  });
  addEventListener('resize', () => {
    if (!open) return;
    place(); moveIndicator(true);         // the group may have re-wrapped
  });
  document.getElementById('cmdform').addEventListener('submit', async e => {
    e.preventDefault();
    const kind = activeKind;
    const text = document.getElementById('cmdtext').value.trim();
    if (kind !== 'do-next' && !text) {
      setCmdMsg('a thought is needed', false);
      return;
    }
    composing = false;          // from here, anything he does means "still here"
    {
      // THROUGH `postJSON`, not a fetch of its own (#175). It is the one seam
      // every submission passes, so routing the composer through it is what
      // makes the client-side record complete rather than well-intentioned —
      // a second fetch here would be a third of his submissions unwitnessed,
      // which is #191's lesson about one gesture spelled two ways, aimed at
      // data instead of at motion.
      const attempt=confirmation.begin();
      const r = await postJSON('/command', { kind, text, from: fromPath() });
      if (r && r.ok) {
        if(!attempt.success())return;
        const plus = document.getElementById('cmdplus');
        if (plus) { const b = plus.getBoundingClientRect();
          ripple(b.left + b.width / 2, b.top + b.height / 2); }
        document.getElementById('cmdtext').value = '';
        if (kind === 'do-now') setKind('add-idea');
        clearDraft();             // the one moment it is safe to forget (#163)
        // he may already have started typing again while the POST was in
        // flight, before there was any timer to cancel. Courtesy is NOT
        // the confirmation hold (#291): that is CMD_CONFIRM_HOLD_MS on the
        // controller, independent of whether the panel stays open.
        cancelDismiss();
        if (!composing) dismissT = setTimeout(closeCmd, CMD_DISMISS_MS);
      } else if (r) attempt.claim('rejected (' + r.status + ')');
      else attempt.claim('no connection');   // postJSON returns null on throw
      // if he is watching the history, it must include what he just did —
      // including, and especially, when it failed
      if (histEl && histEl.open) renderHist();
    }
  });
  document.getElementById('cmdpop').addEventListener('click', requestPopout);
})();
"""

SHADER_JS = """
/* dreambg: dream-like fractal background (task #51).
   Four passes, all cheap by construction — the costly work stays on a
   ~1/6-CSS-res buffer and only a flat upscale touches full res:
     pass 1 — domain-warped fBm fractal -> low-res texture A.
     pass 2 — tilt-shift blur A -> B (8 golden-angle taps; a drifting
              focus band keeps radius small, growing away from it).
     pass 3 — blur B -> C again; the two passes compound into a wide,
              smooth depth-of-field (most of the frame softly defocused).
     pass 4 — upscale C to screen, tint indigo/violet, dither, composite
              very subtly over #0b0f19.
   Blur stays low-res on purpose: it IS the perf budget, and splitting it
   across two <=8-tap passes also sidesteps a headless-SwiftShader quirk
   where many texture taps of a high-frequency buffer drop the context.
   Text always wins: shader luminance is capped far below the dim text.
   Hidden layer switcher: press 'l' (or triple-click the bottom-right
   corner) to cycle raw components — fractal, warp field, focus mask,
   blurred fractal. Pauses when tab hidden; reduced-motion => 1 frame;
   no WebGL / no FBO => canvas hidden (flat #0b0f19 shows through). */
// Domain units per CSS pixel — a WORLD constant, not a per-window one. It
// used to be 2.3/innerHeight, which pinned the field's origin to the screen
// but let each window pick its own zoom; two windows then showed the same
// dream at two scales and the seam between them could never line up. 900 is
// the reference height that keeps the density it always had.
const WORLD_SCALE = 2.3 / 900;
function mountDreambg(win, cv, opts) {
  opts = opts || {};
  const doc = win.document;
  const gl = cv.getContext('webgl',
    { antialias: false, depth: false, alpha: false });
  const rm = win.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!gl) { cv.style.display = 'none'; return null; }

  const VS = 'attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';
  const FRACTAL_FS = `precision highp float;
    uniform float t; uniform vec2 r; uniform float warp;
    uniform vec2 domainOffset;   /* screen-space anchor: world-space dream */
    uniform float domScale;      /* domain units per buffer pixel (world-fixed) */
    float hash(vec2 p){ p=fract(p*vec2(123.34,345.45));
      p+=dot(p,p+34.345); return fract(p.x*p.y); }
    float noise(vec2 p){ vec2 i=floor(p),f=fract(p);
      vec2 u=f*f*(3.0-2.0*f);
      return mix(mix(hash(i),hash(i+vec2(1,0)),u.x),
                 mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),u.x),u.y); }
    float fbm(vec2 p){ float s=0.0,a=0.5;
      mat2 m=mat2(1.6,1.2,-1.2,1.6);
      for(int i=0;i<5;i++){ s+=a*noise(p); p=m*p; a*=0.5; } return s; }
    void main(){
      vec2 uv=gl_FragCoord.xy/r;
      /* World-space: the domain is a fixed number of units per SCREEN pixel
         (domScale) offset by the window's on-screen position — so the pattern
         is pinned to the screen under both dragging AND resizing, and two
         windows of different sizes sample one continuous field rather than
         the same field at two zooms. */
      vec2 p=gl_FragCoord.xy*domScale + domainOffset;
      float tt=t*0.03;
      vec2 q=vec2(fbm(p+vec2(0.0,tt)), fbm(p+vec2(5.2,1.3)-tt));
      /* pinch of curl: divergence-free swirl advecting the domain —
         fluid (navier-stokes-ish) drift without a sim */
      vec2 curl=vec2(q.y-0.5, 0.5-q.x);
      p+=curl*(0.38+0.14*sin(tt*1.7));
      /* transition: the dream stirs — deepen the curl advection and twist
         the domain about screen-centre while a page dissolves, then relax
         back (warp is a 0->1->0 pulse driven by the router). */
      p+=curl*warp*0.6;
      vec2 ctr=r*0.5*domScale + domainOffset;   /* this window's centre */
      float wa=warp*0.15;
      float cw=cos(wa), sw=sin(wa);
      p=ctr+mat2(cw,-sw,sw,cw)*(p-ctr);
      vec2 s=vec2(fbm(p+2.6*q+vec2(1.7,9.2)+tt*0.6),
                  fbm(p+2.6*q+vec2(8.3,2.8)-tt*0.4));
      float f=fbm(p+3.2*s);
      f=clamp(f*1.15-0.05,0.0,1.0);
      gl_FragColor=vec4(f, clamp(q.x*0.5+0.5,0.,1.),
                        clamp(s.y*0.5+0.5,0.,1.), 1.0);
    }`;
  const FOCUS_GLSL = `
    float focusMask(vec2 uv){
      float band=0.5+0.30*sin(t*0.045);
      float foc=smoothstep(0.05,0.44,abs(uv.y-band));
      foc=clamp(foc+0.18*smoothstep(0.35,1.0,abs(uv.x-0.5)*2.0),0.0,1.0);
      return foc;
    }`;
  const BLUR_FS = `precision highp float;
    uniform sampler2D tex; uniform vec2 r; uniform float t;` + FOCUS_GLSL + `
    void main(){
      vec2 uv=gl_FragCoord.xy/r;
      float rad=mix(0.0,0.045,focusMask(uv));
      vec4 acc=texture2D(tex,uv); float w=1.0;
      for(int i=0;i<8;i++){
        float fi=float(i);
        float rr=sqrt((fi+0.5)/8.0)*rad;
        vec2 off=vec2(cos(fi*2.399963),sin(fi*2.399963))*rr;
        off.x*=r.y/r.x;
        acc+=texture2D(tex,uv+off); w+=1.0;
      }
      gl_FragColor=acc/w;
    }`;
  const COMPOSITE_FS = `precision highp float;
    uniform sampler2D texRaw; uniform sampler2D texBlur;
    uniform vec2 r; uniform float t; uniform int mode;
    uniform float pageTint;   /* per-page atmosphere: hue bias only */
    uniform float projHue;    /* HIS colour for this project (#143), radians */
    float hash(vec2 p){ p=fract(p*vec2(123.34,345.45));
      p+=dot(p,p+34.345); return fract(p.x*p.y); }
    /* Rodrigues rotation about the grey axis (1,1,1)/sqrt(3). A HUE rotation
       and nothing else: the component along that axis — the achromatic part,
       which is what luminance contrast is made of — is its own eigenvector
       and comes back untouched. So "contrast survives" is a property of the
       operation rather than a claim about the six values we happened to
       pick, and #143 cannot cost the page a text ramp or an accent. */
    vec3 hueRot(vec3 c, float a){
      const vec3 k=vec3(0.5773502691896258);
      float ca=cos(a);
      return c*ca + cross(k,c)*sin(a) + k*dot(k,c)*(1.0-ca);
    }` + FOCUS_GLSL + `
    void main(){
      vec2 uv=gl_FragCoord.xy/r;
      vec4 raw=texture2D(texRaw,uv);
      vec4 bl=texture2D(texBlur,uv);
      if(mode==1){ gl_FragColor=vec4(vec3(raw.r),1.0); return; }
      if(mode==2){ gl_FragColor=vec4(raw.g,0.25,raw.b,1.0); return; }
      if(mode==3){ gl_FragColor=vec4(vec3(1.0-focusMask(uv)),1.0); return; }
      if(mode==4){ gl_FragColor=vec4(vec3(bl.r),1.0); return; }
      float foc=focusMask(uv);
      vec4 img=mix(raw,bl,smoothstep(0.0,0.55,foc));
      float glow=smoothstep(0.34,0.92,img.r);
      vec3 indigo=vec3(0.28,0.30,0.62);
      vec3 violet=vec3(0.44,0.31,0.66);
      vec3 peri=vec3(0.33,0.41,0.74);
      vec3 tint=mix(indigo,violet,clamp(img.g,0.,1.));
      tint=mix(tint,peri,smoothstep(0.42,0.72,img.b));
      /* per-page identity: nudge the tint's hue a pinch. Luminance-safe —
         the glow multiplier below is untouched, so the peak-brightness
         cap that keeps text winning is unchanged. warm one page, cool
         another; magnitude stays a whisper (<=0.07 mix). */
      vec3 warmRef=vec3(0.50,0.33,0.62);
      vec3 coolRef=vec3(0.30,0.42,0.72);
      tint=mix(tint, pageTint>=0.0?warmRef:coolRef,
               clamp(abs(pageTint),0.0,1.0)*0.5);
      vec3 base=vec3(0.043,0.059,0.098);
      vec3 col=base+tint*(glow*0.105);
      /* ...and THEN his project's hue, over the COMPOSED colour rather than
         over the tint alone. (No backticks anywhere in this shader source:
         it lives in a JS template literal, and a pair of them in a COMMENT
         ends the literal and turns the rest of the GLSL into JavaScript.
         That is what "SyntaxError: Unexpected identifier 'tint'" means here,
         and it takes the whole page down.)

         Rotating only the tint moved almost nothing: the tint is multiplied
         by glow*0.105 and the near-black base — which is most of what is on
         screen — carried its own fixed blue through unchanged. Measured, not guessed: the mean field hue moved 2 degrees
         between indigo and green, and the guard that says so is the reason
         this line is here. Rotating the whole composite is also the version
         whose luminance guarantee is exact, since the achromatic component
         of the WHOLE colour is the rotation's eigenvector.

         Before the vignette and the dither on purpose: the dither is a
         neutral ±1/255 and rotating it would tint the noise. */
      col=hueRot(col, projHue);
      col*=1.0-0.22*smoothstep(0.35,1.25,length(uv-0.5));
      col+=(hash(gl_FragCoord.xy+t)-0.5)/255.0;
      gl_FragColor=vec4(col,1.0);
    }`;

  function compile(type, src) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS))
      console.warn('dreambg shader:', gl.getShaderInfoLog(s));
    return s;
  }
  function program(fs) {
    const pr = gl.createProgram();
    gl.attachShader(pr, compile(gl.VERTEX_SHADER, VS));
    gl.attachShader(pr, compile(gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(pr); return pr;
  }
  // GL objects live in these; initGL() (re)creates them so the whole
  // pipeline can be rebuilt if the browser loses/restores the context.
  let progF, progB, progC, uF, uB, uC, buf;
  let A = null, B = null, C = null, fboOK = false;
  let canW = 2, canH = 2, fboW = 2, fboH = 2;
  function bindQuad(pr) {
    const loc = gl.getAttribLocation(pr, 'p');
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  }
  function makeTarget(w, h) {   // low-res RGBA render target
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, w, h, 0,
      gl.RGBA, gl.UNSIGNED_BYTE, null);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    const fbo = gl.createFramebuffer();
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0,
      gl.TEXTURE_2D, tex, 0);
    const ok = gl.checkFramebufferStatus(gl.FRAMEBUFFER)
               === gl.FRAMEBUFFER_COMPLETE;
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    return ok ? { fbo, tex } : null;
  }
  function size() {
    canW = Math.max(2, Math.floor(win.innerWidth / 2));
    canH = Math.max(2, Math.floor(win.innerHeight / 2));
    cv.width = canW; cv.height = canH;
    fboW = Math.max(2, Math.floor(canW / 2));
    fboH = Math.max(2, Math.floor(canH / 2));
    for (const tgt of [A, B, C]) if (tgt) {
      gl.deleteTexture(tgt.tex); gl.deleteFramebuffer(tgt.fbo);
    }
    A = makeTarget(fboW, fboH);
    B = makeTarget(fboW, fboH);
    C = makeTarget(fboW, fboH);
    fboOK = !!(A && B && C);
    if (!fboOK) cv.style.display = 'none';
  }
  function initGL() {
    A = B = C = null;                 // context loss invalidated them
    progF = program(FRACTAL_FS);
    progB = program(BLUR_FS);
    progC = program(COMPOSITE_FS);
    uF = { t: gl.getUniformLocation(progF, 't'),
           r: gl.getUniformLocation(progF, 'r'),
           warp: gl.getUniformLocation(progF, 'warp'),
           domainOffset: gl.getUniformLocation(progF, 'domainOffset'),
           domScale: gl.getUniformLocation(progF, 'domScale') };
    uB = { tex: gl.getUniformLocation(progB, 'tex'),
           r: gl.getUniformLocation(progB, 'r'),
           t: gl.getUniformLocation(progB, 't') };
    uC = { raw: gl.getUniformLocation(progC, 'texRaw'),
           blur: gl.getUniformLocation(progC, 'texBlur'),
           r: gl.getUniformLocation(progC, 'r'),
           t: gl.getUniformLocation(progC, 't'),
           mode: gl.getUniformLocation(progC, 'mode'),
           pageTint: gl.getUniformLocation(progC, 'pageTint'),
           projHue: gl.getUniformLocation(progC, 'projHue') };
    buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER,
      new Float32Array([-1,-1, 3,-1, -1,3]), gl.STATIC_DRAW);
    size();
  }
  initGL();

  let mode = 0, lastMs = 0;
  // per-page atmosphere lerped in JS then handed to the composite shader;
  // frameCount is a monotonic draw tally (never resets) so a view swap's
  // continuity can be checked from outside.
  let tintCur = 0, tintTarget = 0, lastDrawMs = 0, frameCount = 0;
  /* his project hue, in radians off the default. Lerped like the
     route tint so picking a colour drifts rather than snaps — it is
     a change to the page's atmosphere, and the atmosphere moves the
     way everything ambient here moves. */
  let hueCur = 0, hueTarget = 0;
  // transition stir: a 0->1->0 envelope the router pulses per navigation;
  // deepens the fractal's curl advection + twist, then relaxes back.
  let warpStart = -1e9, lastWarp = 0;
  function unbindTextures() {
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, null);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, null);
  }
  function blurPass(src, dst, secs) {   // src.tex -> dst.fbo, low res
    gl.bindFramebuffer(gl.FRAMEBUFFER, dst.fbo);
    gl.viewport(0, 0, fboW, fboH);
    gl.useProgram(progB); bindQuad(progB);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, src.tex);
    gl.uniform1i(uB.tex, 0);
    gl.uniform2f(uB.r, fboW, fboH); gl.uniform1f(uB.t, secs);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
  function draw(ms) {
    lastMs = ms;
    // Shader phase comes from the wall clock (shared by every window), not
    // page-local time — so windows animate in lockstep. UTC-day-wrapped to
    // stay small enough for float precision (a single simultaneous reshuffle
    // at UTC midnight; frame deltas below still use page-local ms).
    const secs = (Date.now() * 0.001) % 86400;
    if (!fboOK || gl.isContextLost()) return;
    // world-space anchor: shift the fractal domain by the window's on-screen
    // position (polled per frame, so dragging pins the pattern to the
    // screen). Same units as the domain's per-pixel mapping (2.3/innerHeight).
    const chromeTop = Math.max(0, win.outerHeight - win.innerHeight);
    const domX = (win.screenX || 0) * WORLD_SCALE;
    // gl_FragCoord.y counts UP from the viewport's bottom while screenY counts
    // DOWN from the desktop's top, so the vertical anchor is the negated screen
    // position of the viewport's BOTTOM edge. (Adding the top edge instead
    // makes the field slide the wrong way, at double rate, as a window moves.)
    const domY = -((win.screenY || 0) + chromeTop + win.innerHeight)
                 * WORLD_SCALE;
    // buffer pixels are ~4 CSS px; convert so domScale is units per BUFFER
    // pixel while WORLD_SCALE stays units per CSS pixel (window-independent).
    const domScale = WORLD_SCALE * (win.innerHeight / Math.max(1, fboH));
    const dt = lastDrawMs ? Math.min(0.1, (ms - lastDrawMs) / 1000) : 0;
    lastDrawMs = ms;
    tintCur += (tintTarget - tintCur) * (1.0 - Math.exp(-dt / 0.6));
    hueCur += (hueTarget - hueCur) * (1.0 - Math.exp(-dt / 0.6));
    // warp envelope: fast attack, slow relax to 0 by ~1.6s after a pulse.
    const wage = (ms - warpStart) / 1000;
    let w = 0;
    if (wage >= 0 && wage < 1.6) {
      const atk = 0.22;
      w = wage < atk ? wage / atk : 1.0 - (wage - atk) / (1.6 - atk);
      w = Math.max(0, w); w = w * w * (3 - 2 * w);
    }
    lastWarp = w;
    frameCount++;
    unbindTextures();                       // no cross-frame feedback
    // pass 1: fractal -> A
    gl.bindFramebuffer(gl.FRAMEBUFFER, A.fbo);
    gl.viewport(0, 0, fboW, fboH);
    gl.useProgram(progF); bindQuad(progF);
    gl.uniform1f(uF.t, secs); gl.uniform2f(uF.r, fboW, fboH);
    gl.uniform1f(uF.warp, w);
    gl.uniform2f(uF.domainOffset, domX, domY);
    gl.uniform1f(uF.domScale, domScale);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    // passes 2 & 3: tilt-shift blur A -> B -> C
    blurPass(A, B, secs);
    blurPass(B, C, secs);
    // pass 4: upscale + composite C (blurred) with A (raw) -> screen
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, canW, canH);
    gl.useProgram(progC); bindQuad(progC);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, A.tex);
    gl.uniform1i(uC.raw, 0);
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, C.tex);
    gl.uniform1i(uC.blur, 1);
    gl.uniform2f(uC.r, canW, canH);
    gl.uniform1f(uC.t, secs);
    gl.uniform1i(uC.mode, mode);
    gl.uniform1f(uC.pageTint, tintCur);
    gl.uniform1f(uC.projHue, hueCur);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  win.addEventListener('resize', () => { size(); if (rm) draw(lastMs); });

  const MODES = ['dream (composite)', 'raw fractal', 'warp field',
                 'focus mask', 'blurred fractal'];
  let hint = null, hintT = 0;
  function cycle() {
    mode = (mode + 1) % MODES.length;
    if (!hint) {
      hint = doc.createElement('div');
      hint.id = 'layerhint'; doc.body.appendChild(hint);
    }
    // Self-explanatory feedback: names the layer AND how to cycle, so an
    // accidental switch (stray 'l', triple-click corner) is legible and
    // reversible rather than a mysterious background change.
    hint.textContent = 'background: ' + MODES[mode] + ' — press l to cycle';
    hint.style.opacity = '1';
    win.clearTimeout(hintT);
    hintT = win.setTimeout(() => { hint.style.opacity = '0'; }, 2200);
    if (rm) draw(lastMs);
  }
  // Debug switcher on the main page only: a popout carries no #layerhint
  // styles, and a stray 'l' there should stay a keystroke.
  if (opts.switcher) {
    win.addEventListener('keydown', e => {
      // never hijack a keystroke aimed at a text field (the composer etc.)
      if (e.target.closest && e.target.closest('input, textarea, select')) return;
      if (e.key === 'l' && !e.metaKey && !e.ctrlKey && !e.altKey) cycle();
    });
    let clicks = 0, clickT = 0;
    win.addEventListener('click', e => {
      if (!(e.clientX > win.innerWidth - 90 &&
            e.clientY > win.innerHeight - 90)) { clicks = 0; return; }
      const now = Date.now();
      if (now - clickT > 600) clicks = 0;
      clickT = now;
      if (++clicks >= 3) { clicks = 0; cycle(); }
    });
  }

  let rafId = 0, running = true;
  let fpsEl = null, dtEl = null, ftEl = null, sparkCtx = null;
  let fpsN = 0, fpsT = 0, prevMs = 0;
  const fts = [];                       // inter-frame deltas (missed-vsync)
  const dts = [];                       // measured CPU-side draw time (ms)
  const gts = [];                       // measured GPU frame time (ms), if any
  // GPU timer (dev-only): true per-frame GPU cost via one in-flight
  // TIME_ELAPSED query. Feature-gated to WebGL2 + the disjoint-timer ext;
  // dormant (the CPU number shows) otherwise, and never touched when the
  // overlay is off — no query machinery runs in prod.
  let gpuExt = null, gpuQuery = null, gpuPending = false, gpuOpen = false;
  function acquireGpuTimer() {
    gpuExt = gl.getExtension('EXT_disjoint_timer_query_webgl2');
    if (!(gpuExt && typeof gl.createQuery === 'function')) gpuExt = null;
    gpuQuery = null; gpuPending = false; gpuOpen = false;
  }
  if (opts.dev) {
    const box = doc.createElement('div');
    box.id = 'devbox';
    fpsEl = doc.createElement('div');
    dtEl = doc.createElement('div');
    ftEl = doc.createElement('div');
    const sp = doc.createElement('canvas');
    sp.width = 120; sp.height = 22;
    box.append(fpsEl, dtEl, ftEl, sp);
    doc.body.appendChild(box);
    sparkCtx = sp.getContext('2d');
    acquireGpuTimer();
  }
  function drawSpark() {
    const c = sparkCtx; if (!c || !fts.length) return;
    c.clearRect(0, 0, 120, 22);
    const worst = Math.max(16.8, ...fts);
    c.fillStyle = '#a5b4fc';
    fts.forEach((v, i) =>
      c.fillRect(i, 22 - (v / worst) * 22, 1, (v / worst) * 22));
    c.fillStyle = '#4b5563';           // 60fps guide line
    c.fillRect(0, 22 - (16.7 / worst) * 22, 120, 1);
  }
  const avgOf = a => a.reduce((x, y) => x + y, 0) / (a.length || 1);
  // draw() wrapped with a CPU stopwatch (JS + GL submission) and, when the
  // GPU timer is live, a TIME_ELAPSED query straddling the same draw.
  function timedDraw(ms) {
    if (gpuExt && gpuPending) {                    // reap the prior query
      const ready = gl.getQueryParameter(gpuQuery, gl.QUERY_RESULT_AVAILABLE);
      const disjoint = gl.getParameter(gpuExt.GPU_DISJOINT_EXT);
      if (ready || disjoint) {
        if (ready && !disjoint) {
          const ns = gl.getQueryParameter(gpuQuery, gl.QUERY_RESULT);
          gts.push(ns / 1e6); if (gts.length > 120) gts.shift();
        }
        gpuPending = false;
      }
    }
    if (gpuExt && !gpuPending) {
      gpuQuery = gpuQuery || gl.createQuery();
      gl.beginQuery(gpuExt.TIME_ELAPSED_EXT, gpuQuery); gpuOpen = true;
    }
    const t0 = performance.now();
    draw(ms);
    const cpuMs = performance.now() - t0;
    if (gpuOpen) {
      gl.endQuery(gpuExt.TIME_ELAPSED_EXT); gpuOpen = false; gpuPending = true;
    }
    return cpuMs;
  }
  function frame(ms) {
    const cpuMs = fpsEl ? timedDraw(ms) : (draw(ms), 0);
    if (fpsEl) {
      fpsN++;
      if (prevMs) {
        fts.push(ms - prevMs);
        if (fts.length > 120) fts.shift();
      }
      prevMs = ms;
      dts.push(cpuMs); if (dts.length > 120) dts.shift();
      if (ms - fpsT >= 1000) {
        fpsEl.textContent = fpsN + ' fps';
        // measured work per frame: real GPU time when the timer is live,
        // else CPU-side draw (JS + GL submission — understates true GPU).
        const useGpu = gts.length > 0, work = useGpu ? gts : dts;
        dtEl.textContent =
          avgOf(work).toFixed(1) + '·' + Math.max(0, ...work).toFixed(1) +
          'ms ' + (useGpu ? 'gpu' : 'draw');
        ftEl.textContent =
          avgOf(fts).toFixed(1) + 'ms avg · ' +
          Math.max(0, ...fts).toFixed(1) + 'ms worst';
        drawSpark();
        fpsN = 0; fpsT = ms;
      }
    }
    if (running && !rm) rafId = win.requestAnimationFrame(step);
  }
  function step(ms) {
    if (!running) return;
    if (!doc.hidden) frame(ms);
    else win.setTimeout(() => {
      if (running) rafId = win.requestAnimationFrame(step);
    }, 500);
  }
  // Context loss (GPU reset, tab backgrounding, driver hiccup) is
  // recoverable: rebuild every GL object on restore and resume.
  cv.addEventListener('webglcontextlost', e => {
    e.preventDefault();
    running = false;
    if (rafId) win.cancelAnimationFrame(rafId);
  });
  cv.addEventListener('webglcontextrestored', () => {
    initGL();
    if (opts.dev) acquireGpuTimer();       // ext + query died with the context
    running = true;
    if (rm) draw(lastMs);
    else rafId = win.requestAnimationFrame(step);
  });
  // The router talks to the shader through this handle: setTint nudges
  // the per-page atmosphere target (lerped inside draw); pulseWarp fires
  // the transition stir; frames exposes the monotonic draw tally so a view
  // swap's continuity is observable. reduced-motion never stirs.
  const handle = {
    setTint(v) { tintTarget = v; if (rm) { tintCur = v; draw(lastMs); } },
    setProjHue(rad) { hueTarget = rad;
                      if (rm) { hueCur = rad; draw(lastMs); } },
    pulseWarp() { if (!rm) warpStart = lastMs; },
    get frames() { return frameCount; },
    get tint() { return tintCur; },
    get warp() { return lastWarp; },
    stop() { running = false; if (rafId) win.cancelAnimationFrame(rafId); }
  };
  if (rm) draw(0);
  else rafId = win.requestAnimationFrame(step);
  return handle;
}
window.dreambg = mountDreambg(window, document.getElementById('dreambg'),
                              { dev: window.DEV, switcher: true });
"""

def page_shell(title, body, js):
    """Shared page shell. Contract: `body` opens `<div class="wrap">`
    (the shell closes it) so every watch page shares chrome and tokens."""
    # The icon is empty until the page knows what to say (#153): claiming a
    # state before data arrives is worse here than showing nothing, and an
    # inline link also stops the browser asking us for /favicon.ico.
    return ('<!doctype html><html><head><meta charset="utf-8">'
            f'<title>{title}</title>'
            '<link rel="icon" id="favicon" href="data:,">' + STYLE
            + '</head><body>'
            + body + '<script>' + js
            + '</script></div></body></html>')


# One shell serves every same-document view. The router (last, so
# window.dreambg from the shader exists before it runs) picks the initial
# view from the URL; SHADER_JS mounts the persistent background.
# The one vocabulary reaches the client here, so the composer's buttons, its
# menu, and the popped-out form never drift from what POST /command accepts.
# The core half is baked in because it is a property of THIS FILE; the plugin
# half (#86) rides /data.json because it is a property of the machine, and so
# can change under a page that is already open. `COMMANDS` is the one table
# everything downstream reads, and it is a `let` for exactly that reason.
PAGE = page_shell('dreamwork watch', APP_BODY,
                  "const CORE_COMMANDS = " + json.dumps(list(COMMANDS)) + ";\n"
                  + "let COMMANDS = CORE_COMMANDS.slice();\n"
                  + "const TINTS = " + json.dumps(TINTS) + ";\n"
                  + "const TINT_DEFAULT = " + json.dumps(TINT_DEFAULT) + ";\n"
                  + COMPONENTS_JS + VIEWS_JS + FAVICON_JS + SHADER_JS
                  + ROUTER_JS + COMMAND_JS)


def age_str(seconds):
    for unit, div in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= div:
            return f"{int(seconds // div)}{unit}"
    return f"{int(seconds)}s"


def read_text(path, limit=200_000):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except OSError:
        return None


def linkable_paths(target):
    """Existing target-relative files a prose renderer may promise as links.

    The browser cannot safely ask `/filedata` for every code span while it
    renders. Resolve once in the collector, excluding git/runtime bulk, then
    ship the closed set beside the prose it governs.
    """
    out = []
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in
                    {".git", ".worktrees", ".pi", ".playwright-mcp",
                     "__pycache__", "node_modules"}]
        for name in files:
            path = os.path.join(root, name)
            rel = os.path.relpath(path, target)
            if not rel.startswith(".."):
                out.append(rel)
    return sorted(out)


def list_dreams(dirpath, now):
    out = []
    if not os.path.isdir(dirpath):
        return out
    for name in sorted(os.listdir(dirpath), reverse=True):
        p = os.path.join(dirpath, name)
        if name.endswith(".md") and os.path.isfile(p):
            out.append({"name": name,
                        "mtime": os.path.getmtime(p),
                        "age": age_str(now - os.path.getmtime(p)),
                        "content": read_text(p)})
    return out


# Five, fixed (#151, his number). The panel's height is then a constant —
# five fixed-height rows — so a commit arriving moves the page by exactly
# nothing, and the motion underneath it is one row leaving at the bottom while
# the rest travel down one.
GIT_ROWS = 5


# A row expands (#166), so it carries more than it shows. Capped here rather
# than in the page: five commits touching a thousand files each would be a
# megabyte of /data.json on every tick to fill a disclosure nobody opened.
GIT_FILES = 40


def git_tail(target, n=GIT_ROWS):
    """Recent commits, newest first, as
    `[{sha, t, subject, full, who, body, files, more}]`.

    The time is `%ct` — a unix timestamp, a NUMBER — because the page renders
    an age that ticks every second (#132) and a page computing that from what
    it displayed would be reading its own output back. Whatever the row shows
    is derived here; nothing downstream parses it.

    Git's `-z` mode makes NUL the framing byte. Commit messages and paths
    cannot contain NUL, so unlike the former unit/record separators this frame
    cannot collide with a subject, body, or filename. A malformed record is
    dropped rather than half-read.

    THE RECORD FRAME IS WHY THIS IS ONE CALL. `--name-only` prints the file
    list *after* the format, so a line-oriented parse cannot tell a filename
    from the next commit. Two leading NULs plus the prior record's terminator
    create a run of at least three between records; single NULs frame fields
    and filenames inside one record.
    """
    try:
        res = subprocess.run(
            ["git", "--no-optional-locks", "-C", target, "log", "-n", str(n),
             "-z", "--name-only",
             "--pretty=format:%x00%x00%h%x00%ct%x00%s%x00%an%x00%H%x00%b%x00"],
            capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if res.returncode != 0:
        return []
    out = []
    for rec in re.split("\x00{3,}", res.stdout):
        parts = rec.lstrip("\x00").split("\x00")
        if len(parts) < 5:
            continue
        try:
            when = int(parts[1])
        except ValueError:
            continue
        body = parts[5].strip("\n") if len(parts) > 5 else ""
        files = parts[6:] if len(parts) > 6 else []
        if files:
            files[0] = files[0].removeprefix("\n")
        files = [f for f in files if f]
        out.append({
            "sha": parts[0], "t": when, "subject": parts[2],
            "who": parts[3], "full": parts[4], "body": body,
            "files": files[:GIT_FILES],
            "more": max(0, len(files) - GIT_FILES),
        })
    return out


# ── what this page is RUNNING (#140) ──────────────────────────────────────
#
# A fix that is committed but not deployed is indistinguishable from a bug,
# and he is looking at the deployed page — #129 was reported 24 seconds after
# the commit that fixed it and a tracing cycle went into the gap. The decided
# answer is NOT a deploy hook (`.git/hooks` is untracked, so it would be
# invisible and machine-local, and it would move deploy authority to whoever
# commits). It is to make a stale view announce itself.
#
# MEASURED BY BYTES, on #147's rule. `deployed.py`'s docstring is the long
# form: a sidecar naming the deployed sha says what someone BELIEVED they
# deployed, and this repo learned on #155 that a proxy eventually gets
# believed as the thing it proxies. The states below are that module's,
# value for value, so the hub row and this line say the same words.
#
# WHY IT IS NOT `import deployed`. `just deploy` snapshots watch.py to a
# single file outside the repo and runs THAT, so this process is routinely
# the only file of this project on disk — there is no sibling to import, and
# reaching into the *target* for one would mean a read-only dashboard
# executing code out of the directory it is watching.
#
# WHICH MAKES IT A DIFFERENT QUESTION, AND A STRICTER ONE. `deployed.py`
# asks what the snapshot at the conventional path holds; this asks what THIS
# PROCESS IS RUNNING, read from its own `__file__`. They agree whenever the
# deploy recipe started the server and disagree exactly when something else
# did — a `just watch` from the tree, or one of the orphaned servers #203 is
# about, which is the case where the answer matters most.
SERVE_CURRENT = "current"       # running HEAD's watch.py
SERVE_BEHIND = "behind"         # running an older revision, and we know which
SERVE_UNTRACKED = "untracked"   # matches no revision — started from a dirty tree
SERVE_NOREPO = "no repo"        # this project does not carry watch.py's history
SERVE_ERROR = "error"           # git failed; explicitly NOT "no match"

# Read at IMPORT, not at first request: what is executing is the file as it
# was when python read it. Reading later would answer with an edit made since
# — the reverse of the question — and `--autoreload` re-execs on source
# mtime, so a real change comes back through a fresh process anyway.
try:
    with open(os.path.abspath(__file__), "rb") as _f:
        SELF_SRC = _f.read()
except OSError:
    SELF_SRC = None


def serving_report(target, src=None, path="watch.py"):
    """Which revision of `path` this process is running, against `target`'s
    history of it.

    Every failure is its own named state and none of them is "no match" —
    deployed.py's rule, and the bug it was written for: **a comparison that
    could not run must never look like a comparison that ran and found
    nothing.** `no repo` is the ordinary answer for a project that is not
    this dashboard's own checkout, and it is a reading, not a fault.

    Never takes `.git/index.lock`: `--no-optional-locks` on every call. His
    CLAUDE.md carries a live mitigation about that lock.
    """
    src = SELF_SRC if src is None else src
    out = {"state": None, "rev": None, "missing": [], "note": None}
    if src is None:
        out["state"] = SERVE_ERROR
        out["note"] = "this process cannot read its own source"
        return out

    def g(*args):
        res = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(target), *args],
            capture_output=True, timeout=10)
        if res.returncode != 0:
            raise OSError(res.stderr.decode("utf-8", "replace").strip() or
                          "git exited %d" % res.returncode)
        return res.stdout

    # History FIRST, and its emptiness checked before anything else is read:
    # a project that simply does not track watch.py is an ordinary target,
    # and `git show HEAD:watch.py` raises there — which would report it as
    # broken rather than as different.
    try:
        revs = g("log", "--format=%H", "--", path).decode().split()
    except (OSError, subprocess.SubprocessError) as exc:
        # not a checkout at all is an ORDINARY state, not a failure — most
        # targets are somebody's project rather than this dashboard's own
        # repo. deployed.py splits these the same way and for the same
        # reason: only one of these states means "I compared".
        if os.path.exists(os.path.join(target, ".git")):
            out["state"] = SERVE_ERROR
            out["note"] = "could not read the history of %s: %s" % (path, exc)
        else:
            out["state"] = SERVE_NOREPO
            out["note"] = "this project is not a git checkout"
        return out
    if not revs:
        out["state"] = SERVE_NOREPO
        out["note"] = "this project does not carry %s's history" % path
        return out

    try:
        if g("show", "HEAD:%s" % path) == src:
            out["state"] = SERVE_CURRENT
            out["rev"] = g("rev-parse", "--short", "HEAD").decode().strip()
            return out
    except (OSError, subprocess.SubprocessError) as exc:
        out["state"] = SERVE_ERROR
        out["note"] = "could not read %s at HEAD: %s" % (path, exc)
        return out

    for rev in revs:
        try:
            if g("show", "%s:%s" % (rev, path)) == src:
                break
        except (OSError, subprocess.SubprocessError):
            continue
    else:
        # Every revision was read and none matched. The ONLY path that may
        # say "no match", and it is reached only after the loop truly ran.
        out["state"] = SERVE_UNTRACKED
        out["note"] = ("the running %s matches none of %d revisions"
                       % (path, len(revs)))
        return out

    out["state"] = SERVE_BEHIND
    try:
        out["rev"] = g("rev-parse", "--short", rev).decode().strip()
        out["missing"] = [
            (line.split(" ", 1) + [""])[:2] for line in
            g("log", "--format=%h %s", "%s..HEAD" % rev, "--",
              path).decode().splitlines()]
    except (OSError, subprocess.SubprocessError) as exc:
        out["note"] = "serving an older revision; could not name it: %s" % exc
    return out


# Cached on HEAD, because the answer can only change when HEAD moves or when
# the process is replaced — and a redeploy IS a new process, so the cache
# cannot outlive its subject. Without this, `behind` walks every revision of
# watch.py on every collect: ~40 git calls today and growing forever.
_SERVE_CACHE = {}


def serving_cached(target):
    try:
        head = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(target), "rev-parse", "HEAD"],
            capture_output=True, timeout=10).stdout.decode().strip()
    except (OSError, subprocess.SubprocessError):
        head = ""
    key = (os.path.abspath(target), head)
    if key not in _SERVE_CACHE:
        _SERVE_CACHE.clear()          # only one target, only one live HEAD
        _SERVE_CACHE[key] = serving_report(target)
    return _SERVE_CACHE[key]


# ── the ledger as a time series (#142) ────────────────────────────────────
#
# NO NEW INSTRUMENTATION. `.dreamwork/tasks.md` is versioned and its ids are
# permanent, so `git log` over that one path IS the time series and a task is
# followable across every snapshot by its id. Anything the loop had to start
# recording on purpose would be a second source that can disagree with the
# ledger, and the ledger is the one the human reads.
#
# WHY BOTH SERIES AND NOT THE NET. The open count alone cannot tell "he
# steers fast" from "the work is slow" — they are the same curve. Arrivals
# and completions separate them, so both are drawn and neither is summed into
# a score. There is deliberately NO velocity number: a rate computed over a
# day of a loop that has been alive for a day would be a claim about the
# future dressed as a measurement.
LEDGER_PATH = ".dreamwork/tasks.md"
# `lint.py`'s LEDGER_ID, VERBATIM, and a test asserts the two stay identical.
# What counts as an entry is one rule and it must have one copy: the linter
# already learned this the hard way today (3073055), holding a wider copy of
# the priority-marker rule than the parser and blessing three typos.
LEDGER_ENTRY = re.compile(r"^- \*\*#(\d+)\*\*", re.M)
# ...and in `## Recently landed` an id is named inline, in prose, so the
# entry-head shape does not apply there.
LEDGER_MENTION = re.compile(r"\*\*#(\d+)\*\*")
# A human steer is stamped `· **human 17:45**` by the coordinator. It is the
# only provenance mark the ledger has, and it is on a MINORITY of entries —
# which is why the panel reports its own coverage instead of drawing a split
# (see `burndown` in watch-design.md).
LEDGER_HUMAN = re.compile(r"\*\*human\b")
# The bucket ladder: the smallest step that keeps the chart under this many
# columns. A fixed step would give one column on a young ledger and four
# hundred on an old one.
BURN_COLUMNS = 24
BURN_STEPS = (3600, 4 * 3600, 86400, 7 * 86400, 28 * 86400)

BURN_OK = "ok"
BURN_NONE = "no ledger"    # this project keeps no versioned task ledger
BURN_ERROR = "error"       # git failed; explicitly NOT "no history"

_LEDGER_SNAPS = {}         # rev -> (open ids, landed ids); history is immutable
_LEDGER_CACHE = {}         # (target, head) -> the whole answer


def parse_ledger(text):
    """One ledger snapshot as `(open ids, landed ids)`.

    An id under `## Open` is an entry HEAD; an id under `## Recently landed`
    is named inline in prose. Two shapes because the file has two, and
    reading the landed section with the entry-head rule finds nothing at all
    — which would render as "the loop has completed nothing", the exact shape
    of failure #136 is about.
    """
    if not text or "## Open" not in text:
        return set(), set()
    after = text.split("## Open", 1)[1].split("## Recently landed", 1)
    landed = set(LEDGER_MENTION.findall(after[1])) if len(after) > 1 else set()
    return set(LEDGER_ENTRY.findall(after[0])), landed


def _burn_step(span):
    for s in BURN_STEPS:
        if span <= 0 or span / s <= BURN_COLUMNS:
            return s
    return BURN_STEPS[-1]


def ledger_series(target, path=LEDGER_PATH, now=None):
    """Arrivals, completions and the open count over the ledger's own history.

    An id ARRIVES at the first commit that mentions it anywhere, and is
    COMPLETE at the first commit that names it under `## Recently landed`.
    Both are first-seen events, which is what makes them survive grooming:
    that section is pruned, so anything derived from its current contents
    would lose a completion every time the coordinator tidies.
    """
    out = {"state": None, "note": None, "buckets": [], "step": 0,
           "open": 0, "arrived": 0, "landed": 0, "from": 0, "to": 0,
           "marked": 0, "entries": 0}

    def g(*args):
        res = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(target), *args],
            capture_output=True, timeout=15)
        if res.returncode != 0:
            raise OSError(res.stderr.decode("utf-8", "replace").strip() or
                          "git exited %d" % res.returncode)
        return res.stdout.decode("utf-8", "replace")

    try:
        log = g("log", "--format=%H %ct", "--reverse", "--", path).split("\n")
    except (OSError, subprocess.SubprocessError) as exc:
        # not a checkout is ordinary; a checkout whose git failed is not
        if os.path.exists(os.path.join(target, ".git")):
            out["state"] = BURN_ERROR
            out["note"] = "could not read the history of %s: %s" % (path, exc)
        else:
            out["state"] = BURN_NONE
            out["note"] = "this project is not a git checkout, so its task " \
                          "list has no history to read"
        return out

    revs = []
    for line in log:
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[0]:
            try:
                revs.append((parts[0], int(parts[1])))
            except ValueError:
                continue
    if not revs:
        out["state"] = BURN_NONE
        out["note"] = "no %s in this project's history — nothing to chart " \
                      "yet, which is not the same as nothing happening" % path
        return out

    arrived, landed, opencount = {}, {}, {}
    latest = set()
    for rev, ct in revs:
        if rev not in _LEDGER_SNAPS:
            try:
                _LEDGER_SNAPS[rev] = parse_ledger(g("show", "%s:%s" % (rev, path)))
            except (OSError, subprocess.SubprocessError):
                # one unreadable revision is a hole, not a failure of the
                # series — skip it and keep the rest rather than reporting
                # the whole history as absent
                continue
        o, done = _LEDGER_SNAPS[rev]
        for i in o | done:
            arrived.setdefault(i, ct)
        for i in done:
            landed.setdefault(i, ct)
        opencount[ct] = len(o)
        latest = o

    if not arrived:
        out["state"] = BURN_NONE
        out["note"] = "%s is versioned but this page can see no entries in " \
                      "any revision of it" % path
        return out

    first = revs[0][1]
    last = max(revs[-1][1], int(now if now is not None else time.time()))
    step = _burn_step(last - first)
    n = int((last - first) // step) + 1
    buckets = [{"t0": first + i * step, "arrived": 0, "landed": 0, "open": 0}
               for i in range(n)]
    idx = lambda t: min(n - 1, max(0, int((t - first) // step)))  # noqa: E731
    for t in arrived.values():
        buckets[idx(t)]["arrived"] += 1
    for t in landed.values():
        buckets[idx(t)]["landed"] += 1
    # the open count is a LEVEL, not a count of events: each bucket carries
    # the last reading inside it, and a bucket with no commits inherits the
    # one before rather than reading as a drop to zero
    carry = 0
    for b in buckets:
        inside = [v for t, v in opencount.items()
                  if b["t0"] <= t < b["t0"] + step]
        carry = inside[-1] if inside else carry
        b["open"] = carry

    out.update(state=BURN_OK, buckets=buckets, step=step, from_=first,
               open=len(latest), arrived=len(arrived), landed=len(landed))
    out["from"] = first
    out["to"] = last
    out.pop("from_", None)
    return out


def ledger_stats(target):
    """`ledger_series`, cached on HEAD, plus the provenance coverage read
    from the working tree.

    Cached because the walk is one `git show` per ledger commit — 139 today,
    and it only ever grows. Per-revision parses are memoised globally on the
    commit sha as well, because history is immutable, so a NEW head costs
    only the commits that are new.
    """
    try:
        head = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(target), "rev-parse", "HEAD"],
            capture_output=True, timeout=10).stdout.decode().strip()
    except (OSError, subprocess.SubprocessError):
        head = ""
    key = (os.path.abspath(target), head)
    if key not in _LEDGER_CACHE:
        _LEDGER_CACHE.clear()
        r = ledger_series(target)
        text = read_text(os.path.join(target, LEDGER_PATH)) or ""
        # Coverage, not a split. `**human` marks a minority of entries, so a
        # human-vs-loop chart drawn from it would be mostly one bar wide and
        # would read as fact. The panel says how much of the ledger can
        # answer the question instead — a reader that cannot see something
        # must not render identically to there being nothing to see (#136).
        lines = [ln for ln in text.split("\n") if LEDGER_ENTRY.match(ln)]
        r["entries"] = len(lines)
        r["marked"] = sum(1 for ln in _entry_blocks(text)
                          if LEDGER_HUMAN.search(ln))
        _LEDGER_CACHE[key] = r
    return _LEDGER_CACHE[key]


def _entry_blocks(text):
    """Each ledger entry as one string — its head line plus its continuation
    lines. The marker sits anywhere inside an entry, and matching it per LINE
    would count an entry whose head happens to be short as unmarked."""
    if not text or "## Open" not in text:
        return []
    body = text.split("## Open", 1)[1].split("## Recently landed", 1)[0]
    blocks, cur = [], None
    for line in body.split("\n"):
        if LEDGER_ENTRY.match(line):
            if cur is not None:
                blocks.append(cur)
            cur = line
        elif cur is not None:
            cur += "\n" + line
    if cur is not None:
        blocks.append(cur)
    return blocks


"""Who wrote a note (#109).

A page that mixes what the human said with what the loop wrote will
eventually mislead one of them — and the loop is the one that would then act
on its own invention as if it were an instruction. So the tag records the
AUTHOR, not just the channel, and the page shows it.

Four forms are live: the two current tags and two legacy ones that must keep
parsing, because the file is a record and is never rewritten. An unknown tag
attributes NOTHING — a wrong attribution is worse than an absent one.
"""
NOTE_TAGS = (
    ("- **Note (human,", "human"),           # current: the human, any channel
    ("- **Follow-up (via watch,", "human"),  # legacy: only he used it
    ("- **Follow-up (loop,", "loop"),        # current: the loop
    ("- **Follow-up (in-session,", "loop"),  # legacy: the loop, hand-written
)


def note_author(stripped):
    """'human', 'loop', or None for a sub-bullet note line. None is a real
    answer: render it, attribute nothing, never guess."""
    for prefix, author in NOTE_TAGS:
        if stripped.startswith(prefix):
            return author
    return None


# A sub-bullet's tag head also carries WHEN it was written:
# `- **Note (human, via watch, 2026-07-25 09:00):**`. On a thread the stamp is
# not decoration — a note that predates an answer must not read as a reply to
# it (#128) — so it is parsed rather than thrown away. Anchored to the tag's
# closing `)` so a date inside the note's own text is somebody else's date, and
# it never guesses: an unstamped tag yields None, exactly as `note_author`
# yields None for an author it does not recognise.
SUB_STAMP = re.compile(r"(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?\s*\)")


def sub_when(stripped):
    """When a sub-bullet was written, read from its tag head, or None."""
    m = SUB_STAMP.search(stripped.split(":**", 1)[0])
    if not m:
        return None
    return m.group(1) + (" " + m.group(2) if m.group(2) else "")


# An answer bullet is written by POST /answer and by nothing else, so it is
# always his — but that is a fact about this tag rather than about answers, so
# it is read back from a table for the same reason `note_author` is. The table
# is also what DEFINES an answer bullet for the parser, so the two can never
# disagree about which bullets are answers and whose they are.
ANSWER_TAGS = (
    ("- **Answer (via watch", "human"),
)


def answer_author(stripped):
    """'human', or None for a line that is not an answer bullet."""
    for prefix, author in ANSWER_TAGS:
        if stripped.startswith(prefix):
            return author
    return None


def _note_entry(stripped, author):
    return {"text": stripped.split(":**", 1)[-1].strip(), "author": author,
            "when": sub_when(stripped)}


ENTRY_MARK = "- **"


def _entry_title_parts(segment):
    """Split an entry line's text at the title's closing `**`.

    Returns (title_segment, closed, rest). `closed` is False when the title
    is hard-wrapped and continues on the next line."""
    seg, closed, rest = segment.partition("**")
    return seg, bool(closed), rest


def _join_title(parts):
    """One definition of how a wrapped title becomes a string, so the reader
    and the writer can never disagree about what an entry is called."""
    return " ".join(p.strip() for p in parts if p.strip())


def _parse_entries(text, section, lift_answer):
    """Entries under `## {section}` as [{title, body, follows[, answer]}].

    Four invariants, each of which was a bug at some point:

    1. A top-level `- **` line ALWAYS starts a new entry. Nothing can absorb
       it — not an unterminated title, not an open sub-bullet — so an entry
       can never silently vanish into the one above it.
    2. A TITLE may be hard-wrapped: it closes at its `**` wherever that
       falls, including several lines down. The loop writes this file at ~72
       columns, so a wrapped title is normal input, not malformed (#116).
    3. A SUB-BULLET may be hard-wrapped too: its continuation lines belong to
       it, not to the body. Keeping only the first line truncated the note
       AND spilled its tail into the body as orphaned prose (#106).
    4. An Answer or Note sub-bullet is never mistaken for an entry, even
       un-indented, so it cannot swallow the entries that follow it.

    `lift_answer` pulls a `- **Answer (via watch…):**` bullet out into
    `answer` (Open only), so the view can show answered-awaiting-fold
    distinctly rather than as an ambiguous open question. Lifting it out of
    the sequence is what makes `answer_at` necessary: it records how many
    notes preceded the answer, so the card can put the discussion that led to
    a resolution ABOVE it and any amendment below. Without that the answer was
    hoisted over every note whenever it was written, and a note from two hours
    earlier read as a reply to it (#128) — the entry parsed identically with
    its sub-bullets in either source order, which is the proof that no
    rendering fix could have reached it.
    """
    items = []
    if not text:
        return items
    in_sec = False
    cur = None
    sub = None            # which sub-bullet is absorbing wrapped lines
    title_parts = None    # non-None while a title is still open
    for line in text.splitlines():
        if line.startswith("## "):
            in_sec = line.strip() == f"## {section}"
            cur, sub, title_parts = None, None, None
            continue
        if not in_sec:
            continue
        s = line.strip()
        answer_by = answer_author(s)
        is_answer = lift_answer and answer_by is not None
        author = note_author(s)
        # invariant 1: this test comes FIRST and is unconditional
        if line.startswith(ENTRY_MARK) and not is_answer and author is None:
            seg, closed, rest = _entry_title_parts(line[len(ENTRY_MARK):])
            cur = {"title": _join_title([seg]), "body": "", "follows": []}
            if lift_answer:
                cur.update(answer=None, answer_when=None, answer_by=None,
                           answer_at=None)
            items.append(cur)
            sub = None
            title_parts = None if closed else [seg]
            if closed and rest.strip():
                cur["body"] = rest.strip() + "\n"
            continue
        if cur is None:
            continue
        if title_parts is not None:            # invariant 2
            seg, closed, rest = _entry_title_parts(s)
            title_parts.append(seg)
            cur["title"] = _join_title(title_parts)
            if closed:
                title_parts = None
                if rest.strip():
                    cur["body"] = rest.strip() + "\n"
            continue
        if is_answer:
            cur["answer"] = s.split(":**", 1)[-1].strip()
            cur["answer_when"] = sub_when(s)
            cur["answer_by"] = answer_by
            # how many notes preceded it — the position the lift would
            # otherwise discard, and the only thing that says which notes are
            # a reply to this answer and which it is a reply to (#128)
            cur["answer_at"] = len(cur["follows"])
            sub = "answer"
        elif author is not None:
            cur["follows"].append(_note_entry(s, author))
            sub = "follow"
        elif not s or s.startswith("- ") or s.startswith("* "):
            sub = None                          # a new bullet ends invariant 3
            cur["body"] += line + "\n"
        elif sub == "answer":
            cur["answer"] += " " + s
        elif sub == "follow":
            cur["follows"][-1]["text"] += " " + s
        else:
            cur["body"] += line + "\n"
    return items


# How urgent an entry is, read off the front of its own title (#197):
# `P1 · `, `P2 · `, `P3 · `. Same vocabulary as the task ledger, because he
# already reads P1-P3 there and a second scale would be one to learn. Spec:
# `file-formats.md`, "Priority on a question".
#
# ABSENT MEANS P2 — the middle band, deliberately. It is what makes an
# explicit `P3` sort genuinely BELOW an unmarked entry rather than level with
# it, which is the whole reason a writer would type `P3` at all.
#
# A marker outside the band (`P0 · `, `P4 · `) is left where it is and read as
# unmarked, i.e. P2. That is the quiet failure `lint.py` exists to name: it
# reads to a human as prioritised and sorts as unmarked, so the entry he most
# wants seen sits mid-list looking urgent.
PRIORITY_MARK = re.compile(r"\AP([123])\s+·\s+")
PRIORITY_DEFAULT = 2


def title_priority(title):
    """1, 2 or 3 for an entry title — the sort key, and only that."""
    m = PRIORITY_MARK.match(title or "")
    return int(m.group(1)) if m else PRIORITY_DEFAULT


def open_answer_aid(title, body, ordinal=0):
    """Content identity for an Open answers.md record (arrival key #293).

    Same discipline as answered aids: title+body + ordinal among exact twins.
    Namespace `open:` so it never collides with `ans:` fold keys. Title-only
    keys would merge distinct bodies and skip a second row's enter animation.
    """
    t = (title or "").strip()
    b = (body or "").strip()
    payload = "\n".join(["open.v1", t, b, str(int(ordinal))])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"open:{digest}"


def parse_open_answers(text):
    """Human-authored questions awaiting the dreamer, in file order.

    Each item carries `aid` for collision-safe open-row arrival (#293): exact
    title twins with distinct bodies stay unique; exact content twins get
    successive ordinals (delete renumbers — fail closed for animation keys).
    """
    items = _parse_entries(text, "Open", lift_answer=False)
    seen = {}
    for item in items:
        twin_key = ((item.get("title") or "").strip(),
                    (item.get("body") or "").strip())
        ordinal = seen.get(twin_key, 0)
        seen[twin_key] = ordinal + 1
        item["aid"] = open_answer_aid(
            item.get("title"), item.get("body"), ordinal)
    return items


def _answer_aid_parts(title, when, body, follows):
    """Normalized fields for #238 content identity (trailing noise ignored)."""
    follows_blob = json.dumps(follows or [], sort_keys=True,
                              separators=(",", ":"), ensure_ascii=False)
    return (
        (title or "").strip(),
        (when or "").strip(),
        (body or "").strip(),
        follows_blob,
    )


def answer_record_aid(title, when, body, follows, ordinal=0):
    """Deterministic content identity for an answered answers.md record (#238).

    Namespaced SHA-256 over the full logical record (title, resolution
    timestamp, body, follows) plus a 0-based occurrence ordinal among
    exact-content twins in file order. Fields are stripped so trailing
    newlines from the parser do not invent a new id on reorder. The same
    value backs `data-aid` and `data-keep` on the page so open state rides
    `snapshotFolds` and FLIP tracks the logical record, not list position.
    Body edits change the id (fail to restore is acceptable; never open
    another record).

    Exact-content twin limitation (#247): the ordinal is file-order among
    currently equal twins. Deleting an earlier twin renumbers later ones, so
    a survivor's aid changes and open restore fails closed — it must not
    migrate onto a different body.
    """
    t, w, b, follows_blob = _answer_aid_parts(title, when, body, follows)
    payload = "\n".join(["ans.v1", t, w, b, follows_blob, str(int(ordinal))])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"ans:{digest}"


def parse_answered_answers(text):
    """Questions resolved by the loop, in file order.

    Each item carries `aid` — a content-stable id for the page's open-state
    restore (#238). Exact content twins get successive ordinals so they stay
    distinguishable; reordering different records keeps each id.
    """
    items = _parse_entries(text, "Answered", lift_answer=False)
    seen = {}
    for item in items:
        item["when"] = answered_at(item["body"])
        twin_key = _answer_aid_parts(
            item.get("title"), item.get("when"), item.get("body"),
            item.get("follows"))
        ordinal = seen.get(twin_key, 0)
        seen[twin_key] = ordinal + 1
        item["aid"] = answer_record_aid(
            item.get("title"), item.get("when"), item.get("body"),
            item.get("follows"), ordinal)
    return items


def atomic_write_text(path, text):
    """Durably replace a UTF-8 file, cleaning the unique temp on failure."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".",
                               suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        # Once replace succeeds the ask is committed. A directory-fsync error
        # must not return failure and invite a duplicate retry; durability of
        # the rename is best-effort on filesystems that reject directory sync.
        try:
            dfd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def append_human_question(text, question, stamp):
    """Append a human question without letting pasted Markdown forge records.

    The compact title is a locator; the complete original words live in the
    body. Every body line is indented, so neither `##` nor `- **` can become a
    top-level structural token. Newlines remain visible and meaningful.
    """
    raw = (question or "").strip()
    if not raw:
        return text
    first = next((line.strip() for line in raw.splitlines() if line.strip()), raw)
    sentence = re.split(r"(?<=[?.!])\s+", first, maxsplit=1)[0]
    title = " ".join(sentence.split())
    if len(title) > 80:
        title = title[:77].rstrip() + "…"
    if not text:
        text = "# Questions for the dreamer\n\n## Open\n\n## Answered\n"
    body = "\n".join("  " + line if line else "" for line in raw.splitlines())
    entry = f"- **{stamp} — {title}**\n{body}\n"
    marker = "## Answered"
    at = text.find(marker)
    if at < 0:
        return text
    prefix = text[:at].rstrip() + "\n\n" + entry + "\n"
    return prefix + text[at:].lstrip()


def answers_health(text, entries=None):
    """Health of the optional human-to-dreamer answers ledger."""
    if text is None:
        return "missing"
    if entries is None:
        entries = len(parse_open_answers(text)) + len(parse_answered_answers(text))
    if entries:
        return "ok"
    heads = [line.strip() for line in text.splitlines()
             if line.strip().startswith("## ")]
    prose = [line for line in text.splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    return "empty" if not prose and {"## Open", "## Answered"}.issubset(heads) else "unreadable"


def parse_open_questions(text):
    """[{title, body, answer, follows, priority}] for `## Open`, IN THE ORDER
    THE PAGE SHOWS THEM.

    ORDERING IS A PROPERTY OF THE PARSE, not of a renderer (#197). Three
    surfaces render these entries — the dashboard's questions section,
    `/questions`, and the review dock — and every one of them goes through
    `qaCard`. A sort in each is three chances to disagree about which
    question is most urgent, on the one channel whose whole job is telling
    him what to look at first. It is also what keeps `data-qkey` honest: the
    key is an INDEX into this list, so the list the client is handed must
    already be the list it renders.

    **"Oldest first on a tie" is free and must stay free.** The file is
    chronological, so a STABLE sort by priority alone produces it — and
    Python's is stable. Do not add a date comparison: that would be a second
    mechanism able to disagree with the first, and it would disagree exactly
    on the entries whose stamps are missing or hand-edited.

    `## Answered` is deliberately NOT sorted (see `parse_answered`).
    """
    items = _parse_entries(text, "Open", lift_answer=True)
    for it in items:
        it["priority"] = title_priority(it["title"])
    items.sort(key=lambda it: it["priority"])
    return items


# A folded entry's body opens with the resolution the loop wrote:
# `→ <verdict> (<timestamp>): …`. Anchored at the body's start so it can only
# ever read the RESOLUTION head — a date further down the body is somebody
# else's date. The timestamp may be hard-wrapped (the file is written at ~72
# columns), so whitespace inside it is tolerated.
RESOLVED_AT = re.compile(
    r"\A\s*→[^:]*?\((\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?\s*\)")


def answered_at(body):
    """When a folded entry was resolved, or None.

    A collapsed row (#111) has to stay findable by *when*, and a wrong date is
    worse than no date — so this never guesses, exactly as `note_author`
    never guesses an author."""
    m = RESOLVED_AT.match(body or "")
    if not m:
        return None
    return m.group(1) + (" " + m.group(2) if m.group(2) else "")


def parse_answered(text):
    """[{title, body, follows, when}] for each entry in `## Answered`, so the
    view can render each with its follow-up thread and an add-a-note box —
    and, collapsed, still say when it was answered.

    IN FILE ORDER, which is chronological, and NOT by priority (#197). A
    priority says how urgently something needs him; a settled entry needs him
    for nothing, so sorting these would order a record by an urgency that has
    already expired — and it would scramble the one property this section is
    read for, which is when things happened. The `priority` field is not set
    here either, because nothing sorts by it: a key nobody uses is a claim
    that something does.
    """
    items = _parse_entries(text, "Answered", lift_answer=False)
    for it in items:
        it["when"] = answered_at(it["body"])
    return items


def append_subbullet(text, title, block, section="Open"):
    """Insert `block` at the end of the entry titled `title` inside
    `## {section}` (Open or Answered). Indented sub-bullets (Answer / Note)
    never count as entry boundaries. Returns (new_text, matched).
    Pure — testable without a filesystem.

    The writer must find an entry exactly the way the reader named it, so it
    walks titles with the same rules and the same `_join_title` — including
    hard-wrapped ones (#116). Comparing against the first source line only
    meant a wrapped-title entry could never be matched, and /answer and
    /comment would report failure for an entry plainly on screen.
    """
    lines = text.splitlines()
    out = []
    in_section = False
    in_target = False
    matched = False
    title_parts = None       # non-None while a wrapped title is still open

    def close_target():
        nonlocal in_target
        if not in_target:
            return
        # The block goes at the end of the ENTRY, which is above the blank
        # line separating it from whatever comes next — not below it (#149).
        # `out` already holds that blank by the time anything closes the
        # entry, so appending straight onto it detached the sub-bullet from
        # the entry it belongs to and left it flush against the following
        # `## Answered`. Cosmetic, but the file is the record a human opens
        # and the shape `file-formats.md` documents.
        tail = []
        while out and not out[-1].strip():
            tail.append(out.pop())
        out.append(block)
        out.extend(reversed(tail))
        in_target = False

    def claim(parts):
        nonlocal in_target, matched
        if _join_title(parts) == title:
            in_target = True
            matched = True

    for line in lines:
        s = line.strip()
        if line.startswith("## "):
            close_target()
            in_section = line.strip() == f"## {section}"
            title_parts = None
        elif (in_section and line.startswith(ENTRY_MARK)
                and not s.startswith("- **Answer (via watch")
                and note_author(s) is None):
            close_target()
            seg, closed, _rest = _entry_title_parts(line[len(ENTRY_MARK):])
            if closed:
                claim([seg])
                title_parts = None
            else:
                title_parts = [seg]
        elif in_section and title_parts is not None:
            seg, closed, _rest = _entry_title_parts(s)
            title_parts.append(seg)
            if closed:
                claim(title_parts)
                title_parts = None
        out.append(line)
    close_target()
    return "\n".join(out) + "\n", matched


NOTE_INDENT = "    "
NOTE_WIDTH = 72


def ends_capture(stripped):
    """The reader's own test for 'this line stops belonging to the sub-bullet
    above it' — a blank line or a new bullet. Stated once, here, so the writer
    cannot drift from the reader about where a note ends. (Blank is
    unreachable for text the writer folds to one paragraph, and is included
    anyway: the rule is the reader's, not the caller's.)"""
    return (not stripped or stripped.startswith("- ")
            or stripped.startswith("* "))


def human_block(head, text):
    """A sub-bullet carrying the human's own words (#146).

    He types into a box and pastes into it, so his text arrives with newlines
    and sometimes with bullets. Written naively it lands at column 0, where a
    pasted `- **…**` becomes a TOP-LEVEL ENTRY by the reader's first and best
    invariant — and the loop then reads a question he never asked, with a body
    the paste invented, in the file it treats as the record of what he wants.
    That invariant is correct and stays (it is what stops entries vanishing
    into each other, #116); this is the writer's job. No malice needed: a
    pasted bullet list does it by accident.

    Two guarantees, and the second is the one that is easy to miss:

    1. Every line after the first is INDENTED, so it can never open an entry
       (`- **`) or a section (`## `) — the reader tests both on the RAW line.
    2. No continuation line begins a BULLET, which the reader tests on the
       STRIPPED line. A bullet ends the note's capture, so his remaining words
       would land in the entry's BODY — which loses his attribution into prose
       the loop is assumed to have written, the exact failure #109 exists to
       prevent. A line that would begin one is joined onto the line above
       instead; that terminates, because every join removes a line. Text that
       is *all* bullets therefore comes out as one long line — correct over
       pretty, deliberately: the width is a courtesy to whoever opens the
       file, and the guarantee is what lets the loop trust it.

    The text is first folded to one paragraph, which costs nothing a reader
    could see: `_parse_entries` joins a sub-bullet's continuation lines back
    into one string, so a note has always been one string by the time anything
    renders it. Wrapping is for the human reading the file in an editor.
    """
    body = " ".join((text or "").split())
    lead = f"  {head} "
    pad = " " * len(lead)
    lines = textwrap.wrap(body, max(NOTE_WIDTH, len(lead) + 24),
                          initial_indent=pad, subsequent_indent=NOTE_INDENT,
                          break_long_words=False, break_on_hyphens=False)
    if not lines:
        return lead.rstrip()
    out = [lines[0][len(pad):]]
    for line in lines[1:]:
        stripped = line.strip()
        if ends_capture(stripped):
            out[-1] = (out[-1] + " " + stripped).rstrip()
        else:
            out.append(stripped)
    return "\n".join([lead + out[0]] + [NOTE_INDENT + s for s in out[1:]])


def append_answer(text, title, answer, stamp):
    """Insert an answer bullet at the end of the titled Open entry."""
    return append_subbullet(
        text, title, human_block(f"- **Answer (via watch, {stamp}):**", answer),
        "Open")


def append_comment(text, title, note, stamp, section="Open"):
    """Append a note to an entry (Open or Answered) — a chronological
    mini-thread inside the entry.

    The tag names the AUTHOR as well as the channel (#109): a note left here
    is the human's, and it must be impossible to mistake for something a
    dreamer wrote. `note_author` reads it back.

    Goes through `human_block` for the same reason `/answer` does: what he
    typed must not be able to forge a record (#146)."""
    return append_subbullet(
        text, title,
        human_block(f"- **Note (human, via watch, {stamp}):**", note),
        section)


# A questions.md the reader cannot see renders IDENTICALLY to one with nothing
# to report — which is how a dreamwork instance opened its dashboard to zero
# questions over a file holding six, four of them genuinely open (#135, #136).
# "All clear" and "your channel to him is broken" must never look the same, so
# zero entries is split into three states that the page treats differently:
#
#   missing    — no file. QUIET: the loop writes one the first time it needs
#                him and init seeds it, so a fresh target is not a fault.
#   unreadable — content is there and the reader sees NO entries. THE fault:
#                real questions are sitting in that file, invisible, while the
#                page says "none".
#   empty      — the seeded skeleton init mandates (a literal `## Open` and
#                nothing else), or every entry answered. Calm — the real
#                all-clear.
#
# The exemption is where a check like this quietly dies, so `empty` is defined
# as narrowly as it can be: not merely "no prose", but no prose AND the literal
# `## Open` the reader matches. A file whose only lines are headings and which
# has no `## Open` is not calm — it is precisely the failure that started this,
# where the loop wrote its questions AS `##` headings and every one of them was
# invisible to the page.
def questions_health(text, entries=None):
    """'ok' | 'missing' | 'unreadable' | 'empty' for a questions.md."""
    if text is None:
        return "missing"
    if entries is None:
        entries = len(parse_open_questions(text)) + len(parse_answered(text))
    if entries:
        return "ok"
    lines = text.splitlines()
    heads = [ln.strip() for ln in lines if ln.strip().startswith("## ")]
    prose = [ln for ln in lines
             if ln.strip() and not ln.lstrip().startswith("#")]
    if not prose and "## Open" in heads:
        return "empty"
    return "unreadable"


def open_question_count(questions_text):
    """Count of Open entries still awaiting an answer — the badge should
    reflect what needs the human, so answered-awaiting-fold entries don't
    count (they're the loop's to fold, not the human's to answer)."""
    return sum(1 for q in parse_open_questions(questions_text)
               if not q["answer"])


def _safe_json(text):
    try:
        return json.loads(text) if text else None
    except ValueError:      # torn mid-write read: degrade, don't 500
        return None


# Commands a plugin declares (#86), as the composer's table sees them. Shape
# and reasoning: `file-formats.md`; the plugin author's half:
# `writing-plugins.md`.
#
# WHY THE LOOP COPIES THEM INTO THE TARGET AT ALL: this file reads the TARGET.
# It is invoked `--target <project>` and its whole model is that what it shows
# lives under that root. Plugin skills do not — they sit in
# `~/.claude-p/skills/`, `~/.agents/skills/` and elsewhere, varying by harness
# and by machine, so a composer that read the plugin's own files would work
# here and silently show nothing on the next machine.
#
# `lint.py` reports on this file; THIS is the gate. The difference is timing:
# lint is advice a human reads at some later point, and a request is being
# answered now. So every rule below is a refusal rather than a correction, and
# a file that breaks one costs the composer that command and nothing else.
PLUGIN_KIND_OK = re.compile(r"\A[a-z0-9]+-[a-z0-9-]*[a-z0-9]\Z")


def plugin_commands(target):
    """The declared plugin commands, filtered to what may be shown and sent.

    Absent, unparseable or wrong-shaped all yield `[]`. **Absence is the
    common case** — most targets load no plugin that declares a command — so
    it costs nothing and says nothing; the composer renders exactly as it did
    before there was a plugin system.

    Three refusals, each of which is the failure it prevents:

    - **`common` is never honoured**, whatever the file says. Core commands
      own the composer's main row, so loading a plugin can add to the
      composer and can never degrade the most valuable real estate on the
      page. There is deliberately no way to ask otherwise.
    - **A kind that shadows a core one is dropped**, not renamed. Renaming
      would leave the human a button whose name is not what he sends;
      dropping leaves the core command doing exactly what it always did,
      and `lint.py` names the collision for whoever has to fix it.
    - **A kind that is not a `namespace-name` wire token is dropped.** It
      goes into `watch-events.log` as part of a line an agent then acts on,
      which is the same reason `from_hint` sanitises rather than trusts.
    """
    doc = _safe_json(read_text(
        os.path.join(target, ".dreamwork", "plugin-commands.json")))
    if not isinstance(doc, dict) or not isinstance(doc.get("commands"), list):
        return []
    core = {c["kind"] for c in COMMANDS}
    out, seen = [], set()
    for entry in doc["commands"]:
        if not isinstance(entry, dict):
            continue
        fields = [entry.get(f) for f in ("kind", "label", "desc", "plugin")]
        if not all(isinstance(v, str) and v.strip() for v in fields):
            continue
        kind, label, desc, plugin = (v.strip() for v in fields)
        if kind in core or kind in seen or not PLUGIN_KIND_OK.match(kind):
            continue
        seen.add(kind)
        out.append({"kind": kind, "label": label, "desc": desc,
                    "plugin": plugin, "common": False})
    return out


def list_reviews(review_dir):
    reviews = []
    for name in os.listdir(review_dir):
        if not name.endswith(".html"):
            continue
        try:
            stat = os.stat(os.path.join(review_dir, name))
        except FileNotFoundError:
            # An atomic writer may replace/remove an entry after listdir.
            continue
        reviews.append({"name": name, "mtime_ns": stat.st_mtime_ns,
                        "mtime": stat.st_mtime_ns / 1_000_000_000})
    reviews.sort(key=lambda review: (-review["mtime_ns"], review["name"]))
    return reviews


def collect(target):
    now = time.time()
    dw = os.path.join(target, ".dreamwork")
    questions = read_text(os.path.join(dw, "questions.md"))
    q_open = parse_open_questions(questions)
    q_answered = parse_answered(questions)
    answers = read_text(os.path.join(dw, "answers.md"))
    a_open = parse_open_answers(answers)
    a_answered = parse_answered_answers(answers)
    return {
        "target": os.path.abspath(target),
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "linkable_paths": linkable_paths(target),
        "dreams": list_dreams(os.path.join(dw, "dreams"), now),
        "dreams_archive": list_dreams(
            os.path.join(dw, "dreams", "archive"), now),
        "files": {
            "DREAMWORK.md": read_text(os.path.join(target, "DREAMWORK.md")),
            "questions.md": questions,
            "lessons.md": read_text(os.path.join(dw, "lessons.md")),
            "skill-version": (read_text(
                os.path.join(dw, "skill-version")) or "").strip(),
        },
        "reviews": list_reviews(os.path.join(dw, "review"))
        if os.path.isdir(os.path.join(dw, "review")) else [],
        "open_questions": open_question_count(questions),
        "questions_open": q_open,
        "answered_entries": q_answered,
        # zero entries is not one fact (#136): the page has to say WHICH zero
        # this is, because "all clear" and "the channel to him is broken" are
        # the same number.
        "questions_health": questions_health(
            questions, len(q_open) + len(q_answered)),
        "answers_open": a_open,
        "answers_answered": a_answered,
        "answers_health": answers_health(
            answers, len(a_open) + len(a_answered)),
        "status": _safe_json(read_text(os.path.join(dw, "status.json"))),
        "git": git_tail(target),
        # which revision this process is running (#140), so a stale page
        # announces itself instead of being mistaken for a bug
        "deployed": serving_cached(target),
        # the ledger's own history as a time series (#142) — no new
        # instrumentation, because tasks.md is versioned and its ids are
        # permanent
        "burndown": ledger_stats(target),
        # his colour for this project (#143). It rides /data.json rather than
        # the shell so the EXISTING mtime poll carries it: he picks a tint in
        # one window and every other window on this project follows within a
        # tick, with no new channel and no reload.
        "tint": read_tint(target),
        # plugin-contributed command kinds (#86), for the same reason and by
        # the same route. The core vocabulary is baked into the page shell
        # because it is a property of watch.py; this half is a property of the
        # MACHINE — which plugins resolved here — so it has to be able to
        # change under a page that is already open. `watched_mtime` walks all
        # of `.dreamwork/`, so a plugin loading mid-session reaches the
        # composer on the next tick with no reload and no new channel.
        "plugin_commands": plugin_commands(target),
    }


def watched_mtime(target):
    """The newest thing under the target, as one number the client polls.

    THE DIRECTORIES ARE IN HERE, and they are the half that took #86 to find.
    Statting only files makes a DELETION invisible: removing a file cannot
    raise the maximum mtime of the files that remain, so an open page goes on
    showing what is no longer there until something unrelated is written. A
    directory's mtime moves when an entry is added or removed, which is
    exactly the event that was missing — and adds no re-renders of its own,
    because a created file already carries a fresh mtime.

    The case that named it: unloading a plugin is deliberately the ABSENCE of
    a write rather than a remembered deletion, and the composer went on
    offering commands nothing would answer. That contract needs absence to be
    observable to hold at all.
    """
    latest = 0.0
    paths = [os.path.join(target, "DREAMWORK.md"),
             os.path.join(target, ".git", "logs", "HEAD")]
    dw = os.path.join(target, ".dreamwork")
    for root, _dirs, files in os.walk(dw):
        paths.append(root)
        paths.extend(os.path.join(root, f) for f in files)
    for p in paths:
        try:
            latest = max(latest, os.path.getmtime(p))
        except OSError:
            pass
    return latest


def read_tint(target):
    """The project's tint name, or the default.

    An unknown name falls back rather than blanking the page: the file is a
    preference, and the failure that loses nothing is to show him the
    default. That is also exactly why `lint.py` checks it — the fallback is
    silent, and a silent fallback on his own setting is the shape this
    project keeps finding.
    """
    raw = (read_text(os.path.join(target, ".dreamwork", "watch-tint")) or "")
    name = raw.strip()
    return name if name in TINTS else TINT_DEFAULT


def write_tint(target, name):
    """Persist his choice. Returns False if it could not be written — the
    page then says so rather than showing a swatch that will not survive a
    reload (the /answer rule: never confirm a write that did not happen)."""
    if name not in TINTS:
        return False
    path = os.path.join(target, ".dreamwork", "watch-tint")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(name + "\n")
        return True
    except OSError:
        return False


def persistent_port(target):
    marker = os.path.join(target, ".dreamwork", "watch-port")
    saved = read_text(marker)
    if saved and saved.strip().isdigit():
        return int(saved.strip())
    port = random.randrange(3000, 63000)
    try:
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w") as f:
            f.write(f"{port}\n")
    except OSError:
        pass
    return port


ANSWER_LOCK = threading.Lock()


def resolve_confined(target, rel):
    """Absolute path for `rel` iff it stays under target root, else None.

    The confinement gate for every file-serving path (/file, review
    artifacts). Pure; testable.
    """
    if not rel or rel.startswith(("/", "~")):
        return None
    full = os.path.realpath(os.path.join(target, rel))
    root = os.path.realpath(target)
    if full == root or not full.startswith(root + os.sep):
        return None
    return full


def log_event(target, line):
    """One-line user-action summary for agents (.dreamwork/watch-events.log).

    Best-effort append; points an agent at the right file and next step.
    Gitignored ephemera. Agents tail it with a Monitor tool (instant wake)
    or check its mtime each tick.
    """
    try:
        path = os.path.join(target, ".dreamwork", "watch-events.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {line}\n")
    except OSError:
        pass


# The largest request body that is read at all. Everything a human types
# through this page fits far inside it; the cap is here so an unbounded read
# cannot be aimed at the server.
MAX_BODY = 20_000
SUBMIT_LOCK = threading.Lock()


def log_submission(target, path, body, nbytes, truncated=False):
    """His words on disk before anything is allowed to refuse them (#199).

    His framing: "because the user's time is the most valuable thing". Before
    this, an answer he typed lived in exactly ONE place — questions.md — and
    every write path could refuse it and return having recorded nothing.
    `append_answer` returns unmatched when it cannot find the entry, which is
    exactly what #116 was (a title wrapped across lines), so this was a live
    loss path on his input rather than a theoretical one.

    THREE PROPERTIES, AND EACH IS THE WHOLE POINT OF THE ONE BEFORE IT.

    · It runs FIRST — from `do_POST`, before dispatch, before the body is
      parsed, before anything is validated. One call site rather than four, so
      a handler added later cannot forget, and no failure downstream of it can
      happen first.
    · It is UNVALIDATED. The payload that fails validation is precisely the one
      worth keeping, so a body that is not JSON, or not even UTF-8, is written
      verbatim as `raw` with `why` saying which. A design that logged only the
      parsed request would drop exactly the cases this file exists for.
    · It CANNOT RAISE. A logging failure must never be why his answer was
      refused, so every error is swallowed — including the ones that are the
      caller's fault. `log_event`'s rule, on a file where it matters more.

    Well-formed bodies are stored parsed (`req`) rather than as an escaped
    string, because `json.loads` → `json.dumps` round-trips every value
    faithfully and keeps the line readable and greppable; a raw string would
    turn every newline in his answer into a literal backslash-n. The shape is
    stated in `file-formats.md` and checked by `lint.py`.
    """
    # `bytes` is what he SENT, not what was read: on a truncated body the two
    # differ, and the number that says how much was lost is the declared one.
    rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "path": path,
           "bytes": nbytes}
    try:
        rec["req"] = json.loads(body)
    except (ValueError, TypeError):
        rec["raw"] = body.decode("utf-8", "replace")
        # WHICH kind of unusable, because they need different reading: a
        # `json` line is text a human can still act on, a `decode` line is
        # bytes that were never text and whose `raw` has replacement chars in
        # it. Naming that is the difference between recovering his answer and
        # trusting a mangled one.
        rec["why"] = "json"
        try:
            body.decode("utf-8")
        except UnicodeDecodeError:
            rec["why"] = "decode"
    if truncated:
        rec["truncated"] = True
    try:
        line = json.dumps(rec, ensure_ascii=False)
    except (TypeError, ValueError):        # a value json cannot render
        return
    try:
        # One append of one line, under a lock, because this server is
        # threaded and two interleaved writes lose both submissions rather
        # than one.
        with SUBMIT_LOCK:
            with open(os.path.join(target, ".dreamwork", "submissions.log"),
                      "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except OSError:
        pass


# Accepted POST /command kinds, derived from the one vocabulary (COMMANDS,
# top of file). Each becomes a source-tagged watch-events.log line the loop's
# tail monitor wakes on (same transport as answers); no file is written.
COMMAND_KINDS = tuple(c["kind"] for c in COMMANDS)


# WHERE he was when he sent it (#126). A command sent while reading
# `/review?p=goal-hierarchies.html` is usually about that artifact, and the
# query string is the part that says which one — so it is kept.
#
# It is a HINT and the log line says so by putting it in brackets, off to the
# side of the command: evidence about what he probably meant, never an
# instruction. A command sent from /questions is not thereby about /questions.
#
# The line is read by an agent that then acts, so the path is sanitised down to
# a conservative shape rather than trusted: it must start with `/`, carry no
# control characters, and carry no `]` — which would let it close its own
# bracket and impersonate the rest of the line. Anything else yields no hint at
# all, because a wrong hint is worse than none (the same rule as `note_author`).
FROM_MAX = 200
FROM_OK = re.compile(r"\A/[^\x00-\x1f\]]*\Z")


def from_hint(source):
    """` [<path>]` for a page path the client reported, or ''.

    Over-length is REJECTED, not truncated: a cut path is a different path,
    and it would point whoever reads the line at the wrong file."""
    path = (source or "").strip()
    if len(path) > FROM_MAX or not FROM_OK.match(path):
        return ""
    return f" [{path}]"


def one_line(text):
    """Fold a submission onto one line — the log is one event per line, and a
    newline typed into the box would otherwise forge a second event."""
    return " ".join((text or "").split())


def command_line(kind, text, source=""):
    """Source-tagged watch-events.log line for a human-submitted command.

    Pure; testable. do-next may carry no text (it just nudges selection)."""
    body = f": {one_line(text)}" if text else ""
    return f"command via watch{from_hint(source)}: {kind}{body}"


def make_handler(target, dev=False, authority=None):
    page = PAGE.replace("/*DEV*/false", "true") if dev else PAGE

    class Handler(http.server.BaseHTTPRequestHandler):
        def _authority(self):
            if authority is not None:
                return authority
            # Compatibility for callers/tests that construct the handler before
            # the ephemeral port is known. The production CLI always supplies
            # an explicit authority in trusted-LAN mode.
            port = self.server.server_address[1]
            return RequestAuthority(("localhost", "127.0.0.1", "::1"), port)

        def _preflight(self, write=False):
            hosts = self.headers.get_all("Host", [])
            if len(hosts) != 1 or not self._authority().host_allowed(hosts[0]):
                self.send_error(421, "misdirected request")
                return False
            if write:
                origins = self.headers.get_all("Origin", [])
                if len(origins) > 1 or not self._authority().origin_allowed(
                        origins[0] if origins else None, hosts[0]):
                    self.send_error(403, "origin not allowed")
                    return False
            return True

        def _send(self, body, ctype):
            data = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            # Authority gates every path before it can disclose target state.
            if not self._preflight():
                return
            parsed = urllib.parse.urlparse(self.path)
            # Same-document routes all return the one app shell; the client
            # router renders the matching view (deep links keep working).
            if parsed.path in ("/", "/questions", "/answers", "/file", "/review"):
                self._send(page, "text/html")
            elif parsed.path == "/data.json":
                self._send(json.dumps(collect(target)), "application/json")
            elif parsed.path == "/mtime":
                # "<generation> <watched-mtime>": generation gates a full
                # reload (new server build), mtime gates a data re-render.
                self._send(f"{GENERATION} {watched_mtime(target)}",
                           "text/plain")
            elif parsed.path == "/filedata":
                rel = urllib.parse.parse_qs(parsed.query).get("p", [""])[0]
                full = resolve_confined(target, rel)
                text = read_text(full) if full else None
                if text is None:
                    self.send_error(404)
                    return
                self._send(json.dumps({"path": rel, "content": text}),
                           "application/json")
            elif parsed.path == "/reviewraw":
                # The raw self-contained artifact, for the /review view's
                # iframe (style isolation). /review itself serves the shell;
                # the client router renders the review view around this.
                name = urllib.parse.parse_qs(parsed.query).get("p", [""])[0]
                full = (resolve_confined(
                    target, os.path.join(".dreamwork", "review", name))
                    if name and "/" not in name else None)
                text = read_text(full, limit=2_000_000) if full else None
                if text is None:
                    self.send_error(404)
                    return
                self._send(text, "text/html")   # self-contained artifact
            else:
                self.send_error(404)

        def _read_json(self):
            """The body this request already had read off the wire, parsed.

            It does NOT read the socket: `do_POST` did that, because his words
            have to be on disk before anything here can refuse them (#199).
            """
            try:
                return json.loads(self._body)
            except ValueError:
                self.send_error(400)
                return None

        def do_POST(self):
            # A foreign browser request is not the human submitting to this
            # dashboard. Reject Host/Origin before body read and before #199's
            # witness, otherwise the recovery log itself becomes a cross-site
            # write primitive.
            if not self._preflight(write=True):
                return
            # Human-authorized write paths under loopback or explicitly
            # configured trusted-LAN authority: /answer folds his answer;
            # /ask records his question for the dreamer; /comment threads his
            # note; /command records steering; /tint saves project colour.
            # The first four wake the loop through watch-events.log; tint does
            # not, because it is presentation state rather than agent work.
            # Every other POST path is rejected.
            #
            # THE BODY IS READ AND PERSISTED HERE, BEFORE ANY OF THAT (#199).
            # One call site rather than four: a handler added later gets the
            # guarantee by existing, and no dispatch, parse or validation can
            # run before his words are on disk. That ordering is the whole
            # feature — every one of the paths below can refuse a request, and
            # before this they refused it having recorded nothing.
            try:
                nbytes = int(self.headers.get("Content-Length", 0))
            except ValueError:
                nbytes = -1
            if nbytes < 0:
                self.send_error(400)
                return
            body = self.rfile.read(min(nbytes, MAX_BODY))
            truncated = nbytes > MAX_BODY
            log_submission(target, self.path, body, nbytes, truncated)
            # ...and only now may a request be turned away. An over-long body
            # is still refused — the cap is what makes the read bounded — but
            # it is refused with its first MAX_BODY bytes already kept, so a
            # too-long answer loses its tail rather than all of it.
            if truncated:
                self.send_error(413)
                return
            self._body = body
            if self.path == "/answer":
                self._handle_answer()
            elif self.path == "/ask":
                self._handle_ask()
            elif self.path == "/comment":
                self._handle_comment()
            elif self.path == "/command":
                self._handle_command()
            elif self.path == "/tint":
                self._handle_tint()
            else:
                self.send_error(404)

        def _handle_ask(self):
            req = self._read_json()
            if req is None:
                return
            try:
                raw_question = req["question"]
                if not isinstance(raw_question, str):
                    raise TypeError
                question = raw_question.strip()
            except (KeyError, TypeError):
                self.send_error(400)
                return
            if not question:
                self.send_error(400)
                return
            path = os.path.join(target, ".dreamwork", "answers.md")
            stamp = time.strftime("%Y-%m-%d")
            with ANSWER_LOCK:
                text = read_text(path)
                new_text = append_human_question(text, question, stamp)
                atomic_write_text(path, new_text)
            log_event(target, f'question for dreamer{from_hint(req.get("from"))}: '
                      f'"{one_line(question)}" -> .dreamwork/answers.md')
            self._send(json.dumps({"ok": True}), "application/json")

        def _handle_answer(self):
            req = self._read_json()
            if req is None:
                return
            try:
                title = str(req["question"]).strip()
                answer = str(req["answer"]).strip()
            except (KeyError, TypeError):
                self.send_error(400)
                return
            if not title or not answer:
                self.send_error(400)
                return
            qpath = os.path.join(target, ".dreamwork", "questions.md")
            stamp = time.strftime("%Y-%m-%d %H:%M")
            with ANSWER_LOCK:
                text = read_text(qpath)
                if text is None:
                    self.send_error(404)
                    return
                new_text, matched = append_answer(text, title, answer, stamp)
                if not matched:
                    self.send_error(409)
                    return
                with open(qpath, "w", encoding="utf-8") as f:
                    f.write(new_text)
            log_event(target,
                      f'answer{from_hint(req.get("from"))}: "{one_line(title)}"'
                      f' -> .dreamwork/questions.md '
                      f'(fold the answer, act, move to Answered)')
            self._send(json.dumps({"ok": True}), "application/json")

        def _handle_comment(self):
            req = self._read_json()
            if req is None:
                return
            try:
                title = str(req["question"]).strip()
                note = str(req["comment"]).strip()
                section = str(req.get("section", "Open")).strip()
            except (KeyError, TypeError):
                self.send_error(400)
                return
            if not title or not note or section not in ("Open", "Answered"):
                self.send_error(400)
                return
            qpath = os.path.join(target, ".dreamwork", "questions.md")
            stamp = time.strftime("%Y-%m-%d %H:%M")
            with ANSWER_LOCK:
                text = read_text(qpath)
                if text is None:
                    self.send_error(404)
                    return
                new_text, matched = append_comment(text, title, note, stamp,
                                                    section)
                if not matched:
                    self.send_error(409)
                    return
                with open(qpath, "w", encoding="utf-8") as f:
                    f.write(new_text)
            hint = ("(re-evaluate — a note on an answered entry may amend it)"
                    if section == "Answered" else "(fold with the entry)")
            log_event(target,
                      f'follow-up{from_hint(req.get("from"))}: '
                      f'"{one_line(title)}" -> .dreamwork/questions.md {hint}')
            self._send(json.dumps({"ok": True}), "application/json")

        def _handle_command(self):
            req = self._read_json()
            if req is None:
                return
            try:
                kind = str(req["kind"]).strip()
                text = str(req.get("text", "")).strip()
            except (KeyError, TypeError):
                self.send_error(400)
                return
            # The plugin half is read PER REQUEST rather than cached at start
            # (#86): a plugin that resolved a minute ago is sendable a minute
            # ago, and the composer already offers it on the next tick — a
            # cached set would refuse the very button it just drew. The read
            # is one small file and this is a human keypress, not a hot path.
            if kind not in COMMAND_KINDS and kind not in {
                    c["kind"] for c in plugin_commands(target)}:
                self.send_error(400)
                return
            if kind != "do-next" and not text:
                self.send_error(400)
                return
            log_event(target, command_line(kind, text, req.get("from")))
            self._send(json.dumps({"ok": True}), "application/json")

        def _handle_tint(self):
            """His colour for this project (#143).

            DELIBERATELY NOT AN EVENTS-LOG LINE, and it is the only write
            here that is not. That log's contract is one line per thing an
            agent then acts on — it is what the tail monitor wakes the loop
            for — and a colour is not one. The loop learns his choice the way
            it learns anything durable about him: the file is in the repo.

            Nothing else is needed to reach his other windows, either. The
            write lands under `.dreamwork/`, which `watched_mtime` already
            walks, so the existing 2s poll carries it.
            """
            req = self._read_json()
            if req is None:
                return
            name = str((req or {}).get("tint", "")).strip()
            if name not in TINTS:
                self.send_error(400)
                return
            if not write_tint(target, name):
                self.send_error(500)
                return
            self._send(json.dumps({"ok": True, "tint": name}),
                       "application/json")

        def log_message(self, *_args):
            pass

    return Handler


def _watch_source_and_restart(interval=1.0):
    """--autoreload: re-exec this process when its own source changes, so an
    edit takes effect with no manual restart. The listening socket is
    close-on-exec (Python default) so the port frees for the new image;
    clients reload on the changed GENERATION. Daemon thread; never blocks."""
    try:
        last = os.path.getmtime(__file__)
    except OSError:
        return
    while True:
        time.sleep(interval)
        try:
            now = os.path.getmtime(__file__)
        except OSError:
            continue
        if now != last:
            sys.stdout.flush()
            os.execv(sys.executable, [sys.executable] + sys.argv)


def main(argv=None):
    args = parse_args(argv)
    port = args.port or persistent_port(args.target)
    try:
        net = network_options(args.bind, args.allow_host, args.url_host, port)
    except ValueError as exc:
        raise SystemExit(f"watch.py: {exc}") from exc
    try:
        server = server_class(net.family)(
            (net.bind, port),
            make_handler(args.target, dev=args.dev, authority=net.authority))
    except OSError as e:
        raise SystemExit(
            f"watch.py: cannot bind {net.bind}:{port} ({e.strerror}). "
            f"Another instance may be running (port persisted in "
            f".dreamwork/watch-port); stop it or pass --port.")
    url = f"http://{net.url_host}:{port}/"
    print(f"dreamwork watch: {url} (target {os.path.abspath(args.target)})")
    print("allowed Hosts: " + ", ".join(net.allowed_hosts))
    if net.trusted_lan:
        print("WARNING: trusted-LAN mode is unauthenticated; every reachable "
              "client using an allowed Host can read and write. Public/WAN "
              "exposure is unsupported.")
    if args.open:
        webbrowser.open(url)
    if args.autoreload or args.dev:
        threading.Thread(target=_watch_source_and_restart,
                         daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
