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
import errno
import hashlib
import html
import http.server
import ipaddress
import json
import os
import random
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import urllib.parse
import uuid
from dataclasses import dataclass
import webbrowser

from user_events.sqlite import Envelope, open_journal
# #352: the ledger's entry/origin grammar is ONE module now, imported here
# (and by lint.py and task_origins.py) rather than copied. These names stay
# importable FROM watch — callers that read `watch.ledger_entries`,
# `watch.ENTRY_ID` etc. are undisturbed — but their definition lives in
# ledger_parse.py, which is why the deploy snapshot needs it alongside
# watch.py exactly the way it needs user_events/.
from ledger_parse import (ENTRY_HEAD, ENTRY_ID, KNOWN_ORIGINS, ORIGIN_MARK,
                          entry_origins, ledger_entries, source_of_truth,
                          store_path, store_series_raw)
# #351: /file's syntax highlighting REUSES #339's build-time scanner from
# review_artifact.py — the tested one — rather than growing a second
# highlighter here (two would drift). Only the public entry points are taken;
# the internals stay review_artifact's own. It is a sibling import like
# ledger_parse, so `just deploy`'s --ship-siblings stages it beside the
# snapshot the same way (derived transitively, never a hardcoded list).
from review_artifact import SUPPORTED_LANGUAGES as _HL_SUPPORTED
from review_artifact import highlight as _hl_document

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
# `sticky` (#337): whether the composer KEEPS the kind after its command
# lands. add-idea is the only sticky kind; every steering kind decays back
# to it at submit, because a mode that persists silently raises the
# authority of his NEXT message (#257's reasoning, generalised). Absent
# means NOT sticky — a plugin kind that says nothing must not linger
# either — so the decay needs no third place to be remembered.
COMMANDS = (
    {"kind": "add-idea", "label": "add idea", "common": True, "sticky": True,
     "desc": "park a thought; the loop picks it up when it chooses next"},
    {"kind": "do-next", "label": "do next", "common": True, "sticky": False,
     "desc": "jump this to the front of the queue (text optional)"},
    {"kind": "do-now", "label": "do now", "common": True, "sticky": False,
     "desc": "interrupt the current increment and start this instead"},
    {"kind": "maintenance", "label": "maintenance", "common": False,
     "sticky": False,
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

# #290 main-dreamer run modes. Authoritative file is gitignored machine-local
# `.dreamwork/run-mode` (not status.json, not tint). v1 selectable set only;
# hierarchical is visible-but-disabled UI until #264/#288 make it honest.
RUN_MODES = ("lackadaisical", "hot", "assisted")
RUN_MODE_DEFAULT = "lackadaisical"
RUN_MODES_PLANNED = ("hierarchical",)
RUN_ARM_MS = 10_000
# #462 — after POST /deploy lands, how long the loaded document waits for a
# new GENERATION before naming the failure. just deploy's own readiness is
# sleep 1 + up to 5s of curl probes (~6s healthy); 30s is ~3× that budget so
# a contended box is not a false timeout, and still short enough that a hung
# deploy does not leave a spinner forever. Copy decision as much as timing:
# the page must say something, in the styleguide voice, when nothing arrives.
DEPLOY_WAIT_MS = 30_000
# #300 — one shared hover/focus description per mode. Copy is the behavioural
# contract (file-formats.md / SKILL.md run-mode paragraph), never marketing.
# hierarchical is not selectable; its line names why it stays disabled.
RUN_MODE_DESC = {
    "lackadaisical":
        "idle-friendly · no proactive fan-out · the default pace",
    "hot":
        "continuous bounded work · coordinator only · no helper fan-out",
    "assisted":
        "continuous work · a few disjoint helpers under existing ownership",
    "hierarchical":
        "planned · needs concurrency (#264) and containment (#288)",
}

# Soft upper bound for the dashboard stepper only — the file and the loop
# accept any non-negative integer; this is a control affordance, not a cap
# on concurrency (his #445 Q3: the number is a TARGET, never a limit).
POSTURE_DELEGATION_UI_MAX = 9
# Contract copy per stop (file-formats.md / #445 dictation), not marketing.
# Closed sets live in lint.py (single source) and are reached via
# `_posture_vocab()` — lazy, so `import lint` (which imports watch at
# module level) does not meet a half-initialised lint when watch binds.
POSTURE_PACE_DESC = {
    "idle": "idle-friendly · no proactive fan-out",
    "steady": "continuous bounded work · measured, not urgent",
    "hot": "continuous work · the loop stays on it",
}
POSTURE_ASKING_DESC = {
    "ask": "ask me everything · material choices surface as reviews he decides",
    "inform": "keep me informed · mostly automatic; ~10–20% escalate as docs",
    "near-auto": "near-automatic · journal each material choice; surface only the big ones",
    "auto": "full auto · never blocked on a reply; still cooperates, never parks",
}
POSTURE_DELEGATION_DESC = {
    "own": "occasional helpers · target avg below 0.5 running — not forbidden",
    "assist": "a helper on average · target between 0.5 and 1.5",
    "delegate": "several helpers · target 2+; pairs may share one worktree",
}
# #342 — delivery: when he is interrupted. Contract copy, not marketing.
POSTURE_DELIVERY_DESC = {
    "instant": "wake the loop now · every kind fires the moment you send it",
    "batched": "drain on the next tick · do-now/do-next still pre-empt",
}
# Hoisted early so lint can `import watch` without waiting for the ledger
# section thousands of lines later. Single definition — the ledger block
# reuses this name, never restates.
IDS_ONLY_SPAN = r"#\d+(?:[ \t]*[/+][ \t]*#\d+|[ \t]+#\d+)*"


def _posture_vocab():
    """lint.py's posture closed sets — import, never restate (#445 / #413).

    Lazy on purpose: lint does `import watch` at module top, so a watch-level
    `import lint` during watch's own load would see lint mid-initialisation
    and miss POSTURE_STOPS_*. Callers (and `__getattr__`) reach this only
    after both modules have finished loading.
    """
    import lint
    return lint


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
    --warn:#fcd34d;
    /* The code-token palette (#351), spent ONLY inside /file's source pane.
       Value-for-value the review-artifact frame's (#339), because he moves
       between /file and /review constantly and the same token kind must be
       the same colour in both. `--amber` is deliberately NOT `--warn`: on
       this page `--warn` means broken (#136) and a numeral is not broken.
       These break the one-accent rule inside a code block the way the
       artifact already does — colouring code is the point of the pane. */
    --accent2:#7dd3fc; --ok:#86efac; --amber:#fcd34d; }
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
  .crumb, .htitle, .hproj { display:inline-block;
    transition:transform .85s cubic-bezier(.32,.1,.2,1),
               opacity .55s ease, filter .55s ease; }
  /* non-breaking spaces: an inline-block collapses the leading/trailing
     whitespace of generated content, so " · " would render flush */
  .crumb + .crumb::before { content:"\\00a0\\00b7\\00a0"; color:var(--dim); }
  /* A CRUMB NEVER BREAKS INSIDE ITSELF (#284, measured at 390px). The design
     already says the separator belongs to the crumb that FOLLOWS — that is why
     a departing crumb takes no punctuation with it — but a crumb is an
     inline-block whose contents wrap like any other inline content, so as soon
     as the row was long enough to wrap it broke between the separator and the
     mode switch and left a lone `·` on a line of its own, 17px above the crumb
     it belonged to.

     A trailing WORD JOINER (U+2060) in the separator was the first attempt and
     it did NOT work: it suppresses a break at its own position, and Chromium
     still took the break opportunity before the switch's atomic `inline-flex`
     box. `nowrap` is the rule actually wanted — a crumb is a short label — and
     the ONE exception is the path, which must wrap anywhere (`.fdir` re-enables
     wrapping for its own text). */
  .crumb { white-space:nowrap; }
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
  /* ── the file heading lockup (#284) ──────────────────────────────────────
     His report: a full path like `.dreamwork/docs/research/contextual-review-
     annotations.md` competes with the document it names. So the BASENAME is
     the `<h1>` and the exact parent path sits BENEATH it — in the crumb row,
     which already IS this page's subdued metadata line. That is the whole
     reason there is no new component and no new motion here: the path is a
     crumb, so it arrives, departs and travels on the keyed route transition
     every other crumb already uses.

     IT WRAPS ANYWHERE AND IS NEVER SHORTENED (human, 2026-07-27): "a path
     that lies about its own segments is worse than one that takes two lines."
     No ellipsis, no middle-truncation, no reordering — and `overflow-wrap:
     anywhere` is what lets a long directory chain break INSIDE a segment
     rather than push the column sideways, which is the only other thing an
     unbreakable 60-character token can do. It is selectable text, because
     selecting it is the fallback when the clipboard is refused. */
  .fdir { color:var(--dim); user-select:text; -webkit-user-select:text;
          white-space:normal; overflow-wrap:anywhere; word-break:break-word; }
  .fcopy { background:none; border:1px solid transparent; color:var(--muted);
    border-radius:var(--radius); font:inherit; padding:0 .3rem; cursor:pointer;
    transition:color .3s ease, border-color .3s ease; }
  .fcopy:hover { color:var(--accent); }
  /* A REAL focus ring, not a colour shift. `.pipbtn` marks focus by taking
     the accent alone, which is the same signal as hover and unreadable to
     anyone arriving by Tab on a page whose accent is already everywhere. The
     copy button is keyboard-first by construction (it is a <button>, so
     Enter and Space activate it natively), so its focus state has to be
     visible without a colour memory. */
  .fcopy:focus-visible { color:var(--accent); border-color:var(--accent);
    outline:1px solid var(--accent); outline-offset:2px; }
  /* The copy confirmation is the composer's confirmation — the same
     `.cmdmsg` component and the same `confirmationFor` lifecycle, so this
     page has exactly ONE polite-confirmation idiom rather than a second one
     that drifts. What is its own is WHERE it sits: absolutely positioned in
     the gap `#meta`'s 2rem bottom margin already leaves above `#view`, so a
     message that arrives moves NOTHING. Appearing is a transition, and the
     cheapest way to obey that is to need no layout in the first place. */
  .fmsg { position:absolute; top:100%; left:0; margin-top:.15rem;
          max-width:100%; }
  /* ── Rendered / Source (#252) ────────────────────────────────────────────
     The page's standing sliding selection group (#121), so the outline that
     travels, its easing and its reduced-motion landing all come for free and
     there is no second switch idiom here. What is its own is that it sits in
     a line of TEXT: inline-flex on the row's baseline, at the crumb row's own
     size, so it reads as part of the metadata line rather than as a control
     panel bolted to it.

     BOTH LABELS STAY IN ONE ROW AT EVERY WIDTH (his rule), which is what
     `flex-wrap:nowrap` is for — `.sgroup` wraps by default, and a wrapped
     two-position switch is a stack with an indicator sliding vertically
     through it. Two words cost under 16ch: there is no viewport where hiding
     or stacking half of a binary choice is the better trade.

     The active label takes `--accent`, i.e. `.sgbtn.on` unmodified. That is
     the accent's rule and not an exception to it: the mode is the live state
     of the surface he is reading, not a settled preference like the project
     tint (whose selected label deliberately wears its own hue instead).

     SOURCE ORDER IS NOT A CONTRACT, and this is the rule that proves it here:
     `.sgroup` declares `display:flex; flex-wrap:wrap` at the same specificity
     and LATER in this sheet, so a plain `.fmodes` lost both. The switch was
     therefore a BLOCK-level flex container, which forces a line break before
     and after itself — inside its own crumb — and the separator was orphaned
     on a line of its own 17px above it (measured at 390px). `#meta` is on the
     selector so the invariant holds wherever this block sits in the file,
     rather than depending on it sitting below `.sgroup`. The same reasoning
     `.dreamin`'s `!important` states in its own comment. */
  #meta .fmodes { display:inline-flex; flex-wrap:nowrap;
                  vertical-align:baseline; gap:.1rem; }
  .fmodes .fmode { padding:.1rem .4rem; font-size:.7rem; white-space:nowrap; }
  /* the row's links underline on hover; a segmented control's labels must not
     — the indicator is what says which one is live */
  .fmodes .fmode:hover, .fmodes .fmode:focus-visible { text-decoration:none; }
  .fmodes .fmode:focus-visible { outline:1px solid var(--accent);
                                 outline-offset:2px; }
  @media (prefers-reduced-motion: reduce) {
    .crumb, .htitle, .hproj, .fcopy { transition:none; }
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
     FLIP would aim at a height the card never reaches, snapping at the end.

     BOTH sides, not only the bottom. `padding:.5rem 0` is load-bearing for
     #169: top air is the half that shifts the summary 8px under the pointer,
     and that shift *is* the prominence he asked for by name. #277 (22f9884)
     cut it to `padding:0 0 .5rem` to quiet that shift when the fold motion
     made it more visible; that left every disclosure bottom-only and broke
     prominence.mjs on all four surfaces. Do not re-cut the top. */
  details { margin:.25rem 0; }
  details[open] { padding:.5rem 0; }
  summary { cursor:pointer; color:var(--lit); list-style:none; }
  details[open] > summary { color:var(--bright); }
  summary::before { content:"+ "; color:var(--dim); }
  details[open] > summary::before { content:"- "; }
  .age { color:var(--dim); margin-left:.5rem; }
  /* #385 / #456: the pad digit of a single-figure unit is quieter than the
     value. Only the leading 0 of `05` / `09` wears this — never a genuine
     tens digit. Opacity (not a dimmer colour token) so the pad composites
     against the animated shader and reads close to invisible; 50% is his
     estimate of that goal. */
  .age .agepad { opacity:.5; }
  /* age next to the date inside a question title. #456: the chrome's ` · `
     sits between date and age in the markup, so no left margin here — the
     separator carries the gap (was .35rem when the join was bare). */
  .qt .qage { margin-left:0; font-size:.7rem; }
  /* #463 — secondary "modified X ago" on a review row, and the named
     "created unknown" state when birth is unavailable. Same ` · `
     separator #456 reused for date/age (chrome's own middot), never a
     second idiom. Dimmer than the primary age so the two facts coexist
     without competing. No left margin: the separator owns the gap. */
  .age.rmod, .age.ageunk, .age.qup { color:var(--dimmer); margin-left:0; }
  .rsep { color:var(--dimmer); }
  /* #289 — review decision on the listing row. A settled verdict
     (accepted/rejected) dims like a folded entry: the work is done, so its
     marker steps down the text ramp. pending is in flight, so its marker
     stays a step brighter. 'unlinked' (no record) renders NO marker at all
     — absence of a record is its own state, distinct from pending by
     contract; data-decision carries all four so CSS/clients can key off it.
     The marker links to /question when a question_title is recorded (a
     decision row always is). Emphasis here is luminance, not colour:
     --ok/--warn are reserved (#351 pane / #136 broken), so the glyph (✔/✘)
     carries the verdict and the ramp carries 'done'. */
  .rdecision { margin-left:.6ch; font-size:.7rem; white-space:nowrap;
               /* the standing transition .dreamin eases BACK from (the
                  enter-snap rule, #154/#463): without it the arrival pose
                  snaps to lit rather than easing in. */
               transition:opacity .55s ease, filter .55s ease,
                          transform .55s ease; }
  .rdecision.raccepted, .rdecision.rrejected { color:var(--dim); }
  .rdecision.rpending { color:var(--muted); }
  .rqlink { color:inherit; text-decoration:none; }
  .rqlink:hover { text-decoration:none; }
  .rqlink:hover .rdecision { color:var(--accent); }
  pre { white-space:pre-wrap; color:var(--muted); margin:.4rem 0 .8rem 1ch;
        border-left:1px solid var(--line); padding-left:1ch; }
  /* #351 — /file's source pane is CODE, and code does not wrap (his ask:
     "no line wrapping"). A long line scrolls INSIDE the pane, never the
     page sideways — the same contract `.md pre.mdcode` already keeps for
     fences in rendered prose, so this is that idiom reaching the pane it
     was always meant for, not a second one. Scoped to `#filebody > pre`
     (the pane itself): the markdown fence keeps its own rule, and every
     other <pre> on the page (preB peeks — prose) keeps pre-wrap. */
  #filebody > pre { white-space:pre; overflow-x:auto; }
  /* The highlighted pane carries a <code> inside its <pre>; the generic
     inline-`code` chip (panel fill, padding, radius) is for prose spans and
     would paint a plate behind the whole block. Reset it here rather than
     weakening the prose rule. */
  #filebody > pre > code { color:inherit; background:none; padding:0;
                           border-radius:0; }
  /* #339's tok- spans, emitted by the SERVER (#351 reuses review_artifact's
     scanner; there is no tokeniser in this bundle). Palette tokens above;
     a span whose CSS is ever lost degrades to the pane's own colour. */
  #filebody > pre code .tok-kw { color:var(--accent); }
  #filebody > pre code .tok-str { color:var(--ok); }
  #filebody > pre code .tok-num { color:var(--amber); }
  #filebody > pre code .tok-com { color:var(--dimmer); font-style:italic; }
  #filebody > pre code .tok-fn { color:var(--accent2); }
  #filebody > pre code .tok-typ { color:var(--amber); }
  #filebody > pre code .tok-dec { color:var(--accent); }
  #filebody > pre code .tok-op { color:var(--muted); }
  #filebody > pre code .tok-tag { color:var(--accent); }
  #filebody > pre code .tok-attr { color:var(--accent2); }
  #filebody > pre code .tok-var { color:inherit; }
  /* ── the file view's image and binary surfaces (#336) ─────────────────
     A raster image is served by /filebytes and rendered as an <img>, framed
     like the rest of the column: hairline border on the panel fill (so its
     own content does not fight the shader field behind it), `max-width:
     100%` so it never breaks the 72ch reading column, `border-radius` for
     the same soft edge every box on this page has. The .pose class is the
     start state for the image's own arrival; see imgArrived. */
  .fileimg-wrap { margin:.4rem 0 .8rem 1ch; padding-left:1ch;
                  border-left:1px solid var(--line); }
  .fileimg { display:block; max-width:100%; height:auto;
             background:var(--panel); border:1px solid var(--border);
             border-radius:var(--radius);
             transition:opacity .55s ease; }
  /* the start pose is OPT-IN: it is applied only by JS at build time, and
     removed on `load` — so a JS error or a removed handler fails VISIBLE
     (the image stays fully lit) rather than invisible. The rule lives here
     rather than on .fileimg so the failure mode is "no animation", not
     "no image". Reduced motion overrides it to opacity:1, which is the
     same information and timing with the movement removed. */
  .fileimg.pose { opacity:0; }
  /* a non-image binary file: type and size as labelled facts, with a
     download link instead of a <pre> full of mojibake. The same hairline
     rail and dim labels every fact-list on this page uses, so it reads as
     a quiet part of the dashboard rather than as an error panel. */
  .filebin { margin:.4rem 0 .8rem 1ch; padding-left:1ch;
             border-left:1px solid var(--line); }
  .filebin-row { display:grid; grid-template-columns:6ch 1fr;
                 gap:.5ch 1ch; margin:.32rem 0; align-items:baseline; }
  .filebin-k { color:var(--dim); }
  .filebin-v { color:var(--text); overflow-wrap:anywhere; }
  .filebin-dl { display:inline-block; margin-top:.6rem; }
  @media (prefers-reduced-motion: reduce) {
    .fileimg { transition:none; }
    .fileimg.pose { opacity:1; }
  }
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
  /* #486: a commit with no body shows its FULL subject here, in the detail,
     because the header's .gsub may ellipsise it — otherwise the one line the
     commit has to say is shown nowhere */
  .git .gfullsub { margin:.1rem 0 0; }
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
  /* position:relative so the per-column hover tip can float without
     changing layout height (#417). */
  .bd { margin:.1rem 0 .9rem; position:relative; }
  /* ONE LINE — #151's mechanism for #151's reason, one panel down: the
     numbers in here change, and a head that wraps to two lines changes
     the panel's height, which is the premise that lets the bars animate
     without dragging everything below them. Flex so #499's limit control
     can sit on the same row without being ellipsised off the end: the
     count + step flex-shrink and ellipsis; the limit (when present) is
     flex:none and always fully visible. No second row — #417 fixed height. */
  /* min-height is sized for the #499 input's border box so the head is
     the same height with or without the limit control — appearing must
     not move the panel (#417). */
  .bdhead { color:var(--dim); font-size:.7rem; margin-bottom:.4rem;
            display:flex; align-items:center; gap:.35rem;
            white-space:nowrap; min-height:1.45em; }
  .bdhead-nums { flex:1 1 auto; min-width:0;
                 overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .bdhead .bdnum { color:var(--lit); }
  /* #487: granularity cycle control — looks like a control (underline
     affordance, pointer), keyboard-native as a real <button>, announces
     via its aria-label. Accent is not spent (panel rule #142). */
  .bdstep { background:none; border:none; font:inherit; color:var(--muted);
            padding:0; margin:0; cursor:pointer;
            text-decoration:underline; text-decoration-style:dotted;
            text-underline-offset:2px; }
  .bdstep:hover { color:var(--lit); text-decoration-style:solid; }
  .bdstep:focus-visible { color:var(--lit); outline:1px solid var(--muted);
    outline-offset:2px; border-radius:2px; }
  /* #499: column-count limit control. Shares the head line (no new row, no
     height change — #417). Renders when total buckets exceed the DEFAULT
     (28), regardless of the active limit — so limit=0 (all) still leaves
     the control up for recovery. Input is tabular and narrow; ⟳ resets
     to 28. Accent is not spent. Conditional presence is the same line
     growing/shrinking its content: no pose/depart of its own, because a
     live re-render of this panel commits instantly (transitions.md /
     #218) and inventing a second arrival idiom for a fragment of a fixed
     line would be the snap among drifts the rule forbids. Reduced-motion
     parity is free. */
  .bdlimit { flex:0 0 auto; display:inline-flex; align-items:center;
             gap:.2rem; color:var(--dim); white-space:nowrap; }
  .bdlimit-in {
    width:3.4ch; height:1.25em; line-height:1.15em; box-sizing:border-box;
    font:inherit; font-size:inherit; font-variant-numeric:tabular-nums;
    color:var(--lit); background:transparent;
    border:1px solid var(--line); border-radius:2px;
    padding:0 .15rem; margin:0; text-align:right; vertical-align:middle;
    -moz-appearance:textfield; appearance:textfield;
  }
  .bdlimit-in::-webkit-outer-spin-button,
  .bdlimit-in::-webkit-inner-spin-button { -webkit-appearance:none; margin:0; }
  .bdlimit-in:hover { border-color:var(--muted); }
  .bdlimit-in:focus { outline:1px solid var(--muted); outline-offset:1px;
    border-color:var(--muted); }
  .bdlimit-reset { background:none; border:none; font:inherit;
    color:var(--muted); cursor:pointer; padding:0 .12rem; margin:0;
    line-height:1; border-radius:2px; }
  .bdlimit-reset:hover { color:var(--lit); }
  .bdlimit-reset:focus-visible { color:var(--lit);
    outline:1px solid var(--muted); outline-offset:2px; }
  .bdtrack { display:flex; align-items:stretch; gap:2px; }
  .bdnet { height:30px; }
  .bdflow { height:34px; margin-top:9px; }
  .bdcol { flex:1 1 0; min-width:0; display:flex; flex-direction:column;
           justify-content:flex-end; outline:none; }
  /* #417 hover: a column is focusable so keyboard/touch reach the same
     readout pointer hover does. No accent, no fill — the panel's rule is
     that nothing here waits on him; focus only lifts the level cap one
     ramp step so the active column is findable. */
  .bdnet .bdcol:focus-visible .bdlevel { border-top-color:var(--muted); }
  .bdnet .bdcol:hover .bdlevel { border-top-color:var(--muted); }
  .bdflow .bdcol { justify-content:stretch; }
  /* #417 per-column readout — an ARRIVAL, not a native title. Floats over
     the chart so it never changes the panel's height (constant-height
     premise). Reuses the rundesc atmospheric blur+drift (pose → ease in,
     depart → ease out). Accent is not spent. Reduced motion snaps. */
  .bdtip { position:absolute; left:0; right:0; top:0; z-index:2;
           pointer-events:none; font-size:.7rem; color:var(--dim);
           background:color-mix(in srgb, var(--bg) 88%, transparent);
           padding:.15rem .4rem; white-space:nowrap; overflow:hidden;
           text-overflow:ellipsis; border-radius:2px;
           transition:opacity .42s ease, filter .42s ease,
                      transform .42s cubic-bezier(.32,.1,.2,1); }
  .bdtip[hidden] { display:none; }
  .bdtip.pose { transition:none !important; opacity:0;
    filter:blur(6px); transform:translateY(3px); }
  .bdtip.depart { opacity:0; filter:blur(6px); transform:translateY(-3px); }
  .bdtip .bdnum { color:var(--lit); }
  @media (prefers-reduced-motion: reduce) {
    .bdtip { transition:none; }
  }
  /* #298/#487 column inspector — the RICHER reading on #417's seam, not a
     second hover. The glance tip stays one ellipsised line across the
     head; the inspector is what a DELIBERATE look gets (a hover that
     dwells, a focus, a tap): the exact interval, the level, the flow,
     the commits, and the coverage state the chart's geometry cannot say
     (a level with no ledger commit that period is CARRIED, not measured).
     #487 pin: consistent location — right-hand side of the panel when the
     inspector's measured width fits in the right half (room from layout,
     not a guessed breakpoint); otherwise above the chart AND above .bdtip
     so the two never overlap. Floats, so the constant-height premise
     holds. Same arrival idiom (pose → ease in, depart → ease out, snap
     under reduced motion) — a smaller instance of the same gesture, never
     a second one (transitions.md). Accent is not spent. */
  /* border-box so max-width:100% INCLUDES padding + border. Content-box
     let the box sit 100% wide then grow by ~18px of padding/border past
     the panel — invisible on short coverage lines, exposed at 390px once
     #498 lengthened the open-period line ("…period in progress · N%
     elapsed") to the max-width ceiling (bdhover: right 392 vs bdR 374). */
  .bdinsp { position:absolute; top:0; left:0; z-index:3;
            pointer-events:none; font-size:.7rem; color:var(--dim);
            background:color-mix(in srgb, var(--bg) 92%, transparent);
            border:1px solid var(--line); border-radius:3px;
            padding:.3rem .5rem; white-space:nowrap; max-width:100%;
            box-sizing:border-box;
            overflow:hidden; text-overflow:ellipsis;
            transition:opacity .42s ease, filter .42s ease,
                       transform .42s cubic-bezier(.32,.1,.2,1); }
  .bdinsp[hidden] { display:none; }
  .bdinsp.pose { transition:none !important; opacity:0;
    filter:blur(6px); transform:translateY(3px); }
  .bdinsp.depart { opacity:0; filter:blur(6px); transform:translateY(-3px); }
  .bdinsp .bdnum { color:var(--lit); }
  .bdin-iv { color:var(--dimmer); font-size:.65rem; margin-bottom:.1rem; }
  .bdin-cov { color:var(--dimmer); font-size:.65rem; margin-top:.1rem; }
  @media (prefers-reduced-motion: reduce) {
    .bdinsp { transition:none; }
  }
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
     from sit above it.
     #417 c3: the cap's WEIGHT (border-top-width 2–6px) carries ledger
     commits-per-period. Height still means open count; thickness means
     how busy the period was. Zero commits is 1px (below the 2px floor) so
     a quiet period is distinguishable from a single-commit one; the peak
     is always 6px. The mapping is learned, so the per-column hover names
     the exact numbers. Width changes travel with the bar's height on the
     same .85s curve (regroupBars), not a snap. */
  .bdlevel { border-top:2px solid var(--dimmer); box-sizing:border-box; }
  .bdup { background:var(--dim); align-self:flex-end; }
  .bddown { background:var(--muted); }
  .bdrule { height:1px; background:var(--line); flex:0 0 1px; }
  .bdaxis { display:flex; justify-content:space-between; color:var(--dimmer);
            font-size:.65rem; margin-top:.3rem; }
  .bdnote, .bdnone { color:var(--dimmer); font-size:.7rem; max-width:66ch;
                     margin:.45rem 0 0; }
  /* the median filed-to-landed duration (#218): ONE honest duration in the
     panel's surrounding copy, and the population it was computed over —
     not a mark on the chart and not a velocity score. It is the head's
     `bdhead`/`bdnum` treatment one element down: the number is the fact, at
     `--lit` (one step down from the head's only because the head is the
     picture-of-the-whole and this is a derived figure), in a line that may
     never wrap for the same reason the head and the provenance lines may
     not — a number that changes must never move the panels below while the
     bars travel. NO MOTION, and no transition declared: this panel
     re-renders through innerHTML on every tick and nothing about it is a
     gesture the page initiates (transitions.md), so reduced-motion parity
     is the identical settled visual, the contract provenance holds one
     rule up. THE ACCENT IS NOT SPENT: the panel's rule (#142) is that
     nothing in it waits on him, and a median does not. */
  .bdmed { color:var(--dim); font-size:.7rem; max-width:66ch; margin:.3rem 0 0;
           white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .bdmed .bdnum { color:var(--lit); }
  /* #417 c4: commits-per-period figure in the panel's voice (the #218
     median treatment one element down). SHORTENED so it fits at 358px —
     his condition, not a preference: the first render truncated to
     "…3 periods with n…" and an ellipsis there reads as broken rather
     than terse. NO ellipsis: the copy is short enough that overflow is
     not the plan. Fixed-height one line, so the +19px is a deliberate
     one-time allowance in the panel's constant layout, not a growth on
     data change. NO MOTION, accent not spent — same contract as .bdmed. */
  .bdcommit-copy { color:var(--dim); font-size:.7rem; max-width:66ch;
                   margin:.3rem 0 0; white-space:nowrap; overflow:hidden; }
  .bdcommit-copy .bdnum { color:var(--lit); }
  /* the provenance coverage (#217): who filed each task, by FIRST SIGHT —
     three counts and a denominator, with the historical unknown drawn as
     itself and never folded into loop. THE ACCENT IS NOT SPENT (the
     panel's rule, #142), and colour never carries the split alone:
     human/loop are solid at two ramp steps and unknown is a HATCH — a
     pattern, so it survives every tint and every colour-vision — while
     the legend, the per-segment titles and the aria-label state the same
     facts in words. NO MOTION: a live tick commits its DOM instantly
     (transitions.md), so no part of this declares a transition, and
     reduced-motion parity is the identical settled visual. The
     count-carrying lines may never wrap — the panel's height is constant
     within each complete/incomplete state, which is the premise the bars'
     motion rests on — so they ellipsis like the head does, and their full
     text rides the aria-label/title. */
  .bdprov { margin:.45rem 0 0; }
  .provbar { display:flex; height:3px; gap:1px; margin-bottom:.35rem; }
  .provseg { height:100%; flex:var(--share) 1 0; }
  .provseg.phuman { background:var(--lit); }
  .provseg.ploop { background:var(--muted); }
  .provseg.punknown { background:repeating-linear-gradient(45deg,
                        var(--dimmer) 0 1px, transparent 1px 4px); }
  .provline { font-size:.7rem; color:var(--dim);
              white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .provline .phuman { color:var(--lit); }
  .provline .ploop { color:var(--muted); }
  .provline .punknown { color:var(--dimmer);
                        border-bottom:1px dotted var(--dimmer); }
  .provsrc { color:var(--dimmer); font-size:.7rem; margin-top:.15rem;
             white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .gserve { color:var(--dim); font-size:.7rem; margin:-.15rem 0 .55rem;
            max-width:60ch; }
  .gserve.unknown { color:var(--dimmer); }
  .gserve.stale { color:var(--warn);
                  border-left:2px solid var(--warn); padding-left:.8rem; }
  /* #462 — the staleness row's remedy, on the page. The row already named
     the fault; without this it tells him something is wrong and gives him no
     way to act on it.

     WHAT "UPDATE" MEANS HERE. The running process serves a fixed SNAPSHOT
     (`just deploy` copies watch.py outside the repo and runs that), so a
     browser reload only re-fetches the same stale bytes, and a self-re-exec
     (the --autoreload seam at :10351) re-serves that same snapshot too — its
     trigger is `__file__` mtime, and the served `__file__` IS the snapshot,
     which a tree commit never touches. So the only thing that actually
     clears the staleness is a re-snapshot from HEAD plus a restart, which is
     `just deploy`; the GENERATION bump it causes already reloads this tab.

     AUTHORISED ACTION (2026-07-29 03:46, `rec`). The row used to copy the
     command; he consented to the page running it — loopback-only, behind the
     existing confirmation idiom, single-flight. The click arms for RUN_ARM_MS
     (the #290 run-mode arm, reused rather than a second cooldown), then POST
     /deploy. Success is a new GENERATION (full reload); failure and a deploy
     that never finishes both speak on #fmsg, never a spinner forever.

     MOTION. The row is re-rendered through innerHTML every tick, so .dreamin
     is applied only on the current→behind transition by revealStaleAction()
     (the revealNewOpenAsks idiom: start pose on a genuinely new arrival, rAF
     remove; first paint settles without replaying it; reduced-motion skips
     the pose entirely), never baked in and never replayed on a tick where
     the affordance was already present. Behind→current is a redeploy = a new
     process = a generation change = a full reload, so the affordance departs
     with it and needs no departure motion of its own. Arming/running are
     class toggles on the same control (paintStaleDeployUI after setContent),
     not a second arrival gesture. */
  .gservact { font:inherit; color:inherit; background:none; border:0;
    margin-left:.4ch; padding:0; cursor:pointer;
    transition:opacity .55s ease, filter .55s ease, transform .55s ease;
    text-decoration:underline; text-decoration-style:dotted;
    text-underline-offset:2px; }
  .gservact:hover { text-decoration-style:solid; }
  .gservact:focus-visible { outline:1px solid var(--warn); outline-offset:2px; }
  .gservact.arming { text-decoration-style:solid; color:var(--warn); }
  .gservact.running { text-decoration-style:solid; cursor:wait;
    opacity:.7; pointer-events:none; }
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
  /* THE QUESTION'S BODY, wrapped so the review dock has an edge that belongs
     to the TEXT alone (#326). Everywhere else it must not exist at all, and
     `display:contents` is how an element says that: no box is generated, so
     margins collapse exactly as they did before it was introduced, and — the
     half that is load-bearing rather than convenient — no box means no mask
     and no scrollport either, which is what the narrow review layout wants
     back. Two things read the wrapper's children as the card's own and both
     are taught to look through it rather than at it: `cardBody` (the fold's
     reveal and ghost) and `sendComment`'s first-thread insert. */
  .qbody { display:contents; }
  /* a card that has left the list entirely dreams away where it stood */
  .qaghost { position:absolute; z-index:3; pointer-events:none;
    transition:opacity .7s ease, transform .7s ease; }
  /* the departure has two beats (#277): dissolve in place first, then leave.
     Without this phase blur and travel begin together — the element is already
     moving by the time it starts dissolving, so it reads as "mush then snap"
     rather than "dissolve then leave". pregone softens the ghost where it
     stands (dims, barely drifts) before .gone sends it away. The softer half
     — blur and liquify — is the SVG mist filter (#departMist), driven per-frame
     from rAF in dreamAway, exactly as the route dissolve drives #dissolveOut.
     Commits skip this phase (line below) and keep their CSS blur. */
  .qaghost.pregone {
    transition:opacity .18s ease, transform .18s ease;
    opacity:.8; transform:translateY(-2px); }
  .qaghost.gone { opacity:0; transform:translateY(-10px); }
  /* ...but WHICH WAY it dreams away follows the list it is leaving (#174).
     A question card's neighbours travel UP to close the gap it left, so a
     ghost that rises is continuous with them. In the commits panel the
     gesture runs the other way: a new commit pushes the four survivors DOWN
     one row, so the departing bottom row has to fall with them and grow out
     of frame. Rising there reverses against everything around it, which is
     what he saw ("the bottom commit moves *up* towards where the new one
     appears"). Growing while fading is the page's standing departure — it is
     what `.ghost.out` does for a whole view — so this is the same idiom with
     its sign taken from its surroundings, not a second one. Commits keep
     their original blur(6px) — inherited before #277 raised .gone to 8px to
     match .pregone, so the commit gesture is byte-identical (#277 must not
     touch it). */
  .qaghost.commit.gone { filter:blur(6px); transform:translateY(14px) scale(1.07); }
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
  .qa.folded .qfold { margin:0; }
  .peek { margin:0; }
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
  /* #452 — the focused question's said-missing state. The rail idiom at
     DIM level, not --warn: the channel is healthy and the question is
     simply gone, so it must not wear the fault colour — and it must not
     render as an empty list either (#402). The head is the page's small
     uppercase-label idiom; the body states what happened and guesses at
     nothing. */
  .qmissing { border-left:2px solid var(--dimmer); padding-left:.8rem;
    margin:.3rem 0 .9rem; }
  .qmissing .qmisshead { color:var(--dim); text-transform:uppercase;
    letter-spacing:.07em; font-size:.65rem; margin-bottom:.2rem; }
  .qmissing .qmissbody { color:var(--lit); max-width:56ch; }
  .qmissing .qmissback { margin-top:.5rem; }
  /* #452 — the per-card way into the focused page. Headline chrome, so it
     is quiet at rest (dimmer than the age it sits beside) and discovers
     itself on hover/focus with the page's ordinary link signal. No motion
     of its own: it never appears or disappears on a rendered card — it is
     part of the card's HTML and rides the card's own arrival. */
  .qfocus { color:var(--dimmer); font-size:.7rem; white-space:nowrap; }
  .qfocus:hover { color:var(--accent); }
  .qfocus:focus-visible { color:var(--accent);
    outline:1px solid var(--accent); outline-offset:2px; }
  /* #454 — the roll-up affordance: the same quiet headline chrome as the
     focus link it sits beside, as a BUTTON (it acts here; the link goes
     somewhere). Same rest/hover/focus ramp, and no motion of its own —
     it is part of the card's HTML and rides the card's arrival. */
  .qroll { background:none; border:0; padding:0; font:inherit;
    color:var(--dimmer); font-size:.7rem; white-space:nowrap; cursor:pointer; }
  .qroll:hover { color:var(--accent); }
  .qroll:focus-visible { color:var(--accent);
    outline:1px solid var(--accent); outline-offset:2px; }
  /* the dock is the reading surface: its card is never rolled, so the
     affordance the markup shares with the list declines there */
  .qdock .qroll { display:none; }
  /* ROLLED — the top of the scroll, never a bare title. The wrapper
     becomes a box for the first time: #326's display:contents is what an
     unrolled card needs (no box, margins collapse as if it were not
     there), but a clamp needs an overflow edge and an edge needs a box.
     The height is a line COUNT times the rendered line height, measured
     at runtime and handed over as --rollh (rollHeight) — a pinned pixel
     constant is #441's failure shape. The bottom edge softens with a CSS
     mask, the rolled scroll's cut; NEVER an SVG filter — a per-card
     filter is #449's measured jank and this feature is precisely the
     many-filtered-elements shape. The compose box leaves with the rest
     of the body: answering a question means reading it, and reading it
     means unrolling. The mask fade is ~1.5 lines of the 5.5, so the
     readable floor stays the 4-5 he asked to judge by. */
  .qa.rolled .qbody { display:block; max-height:var(--rollh, 6.5em);
    overflow:hidden;
    -webkit-mask-image:linear-gradient(to bottom, #000 72%, transparent 99%);
    mask-image:linear-gradient(to bottom, #000 72%, transparent 99%); }
  .qa.rolled .qcompose { display:none; }
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
   /* the push channel down (#190): the loop cannot reach him. The same fact
      as `.qhealth.unreadable` one surface over — the channel to him failed
      and no number on the page would have said so — so it reuses that idiom
      verbatim: `--warn` and the rail. See watch-design.md's tokens: `--warn`
      is enumerable, and this is a member of that class, not a new one. */
   #status .stpush { border-left:2px solid var(--warn); padding-left:.8rem;
     margin:.2rem 0 .7rem; }
   #status .stpushhead { color:var(--warn); text-transform:uppercase;
     letter-spacing:.07em; font-size:.65rem; margin-bottom:.2rem; }
   #status .stpushbody { color:var(--lit); }
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
    /* #177: growth is function; under reduced motion the box still fits its
       content and scrolls past its ceiling, just without the height travel. */
    .qfield textarea, #cmdform textarea { transition:none !important; }
  }

  /* #177 — same growth gesture as the composer (above), its own ceiling
     (6 rows, see fitText). A 15-line box inside a question card would shove
     the list for a ten-second sentence, which is why the two ceilings differ. */
  .qfield textarea { flex:1; min-width:0; background:none; border:0; margin:0;
    box-sizing:border-box; color:var(--text); font:inherit; font-size:.75rem;
    padding:.4rem .55rem; min-height:44px; resize:none; overflow:auto;
    outline:none; transition:height .85s cubic-bezier(.32,.1,.2,1); }
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
            color:var(--dimmer); font-size:.7rem; text-align:right;
            /* min-width is the reservation the wordmark yields (#435): the
               longest readout is ~"NNN.Nms avg · NNNN.Nms worst", and without
               a floor the box shrinks to whatever one sample printed and the
               yield would under-reserve on a quiet frame. */
            min-width:12.5rem; pointer-events:none; }
  /* the sparkline is narrower than the readout text beside it, so the
     box is text-width and the canvas parks at its LEFT edge by default —
     a gap to the wall. margin-left:auto absorbs the slack and pins the
     graph's right edge to the text's right edge (the wall side). */
  #devbox canvas { display:block; margin-top:.25rem; margin-left:auto;
                    opacity:.55; }
  /* #435: the --dev overlay and the project wordmark both claim the trailing
     top corner on a wide window. The wordmark YIELDS the overlay's column —
     margin-right equal to the overlay's reserved width plus its right inset
     plus a hair of air — rather than the overlay moving or the counter being
     removed. Settled chrome, not a gesture: no transition, reduced-motion
     parity is free (identical settled layout). The yield is wide-only: on a
     phone the same margin wraps the title bar and shoves the review frame
     down, so below 720px the overlay instead drops under the chrome and the
     wordmark keeps the trailing edge. */
  body.dev .hproj { margin-right:calc(12.5rem + .8rem + .4rem); }
  @media (max-width:720px) {
    body.dev .hproj { margin-right:0; }
    #devbox { top:4.75rem; }
  }
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
                     transform 1s cubic-bezier(.32,.1,.2,1),
                     filter 1s cubic-bezier(.32,.1,.2,1);
          transform-origin:50% 40%; will-change:opacity, transform, filter; }
  /* the start state must SNAP (transition:none) — with the transition live,
     adding .enter would animate *toward* opacity 0 and get removed a frame
     later, so it never actually left ~1 (the old "pops in" bug). Snapping to
     0 + pushed-back, then removing .enter, gives a true fade-up from depth. */
  #view.enter { transition:none; opacity:0;
                transform:translateY(30px) translateZ(-110px) scale(.93); }
  /* #449/#453: the arriving view's haze rides the COMPOSITOR as a CSS blur
     that clears as it surfaces into focus (peak ~5px at the back of the
     dissolve, resolving to crisp at rest) — measured free (#449). Ungated
     since #453: the dissolveIn SVG filter is defined but never applied (a
     second full-page rasterisation fails the frame budget), so this blur is
     the arrival's softening in every configuration; the ghost's own haze is
     the SVG mist when it is on, the .mistoff rules below when it is not.
     Reduced-motion zeroes it either way (transition:none below). */
  #view { filter:blur(5px); }
  #view:not(.enter) { filter:blur(0); }
  /* the ghost is pinned to the box the outgoing view occupied (top/width/
     height set in crossfade), not stretched to the wrapper — the chrome now
     sits above #view, and a resizing column must not re-wrap the departing
     content while it is still opaque (#107). */
  .ghost { position:absolute; left:0; top:0; z-index:1; pointer-events:none;
           opacity:1; transform-origin:50% 40%; filter:blur(0);
           transition:opacity 1.05s cubic-bezier(.4,0,.66,.38),
                      transform 1.15s cubic-bezier(.34,0,.6,.4),
                      filter 1.15s cubic-bezier(.4,0,.66,.38); }
  /* the ghost's haze GROWS as it departs — the same shape the mist gave
     (crisp at rest, swirling at the height of the dissolve). Compositor blur,
     gated on .mistoff so it never doubles up with the SVG mist when that is on. */
  body.mistoff .ghost { filter:blur(0); }
  body.mistoff .ghost.out { opacity:0;
               transform:translateY(-34px) translateZ(70px) scale(1.07);
               filter:blur(7px); }
  @media (prefers-reduced-motion: reduce) {
    #view, .ghost { transition:none; }
  }
  /* review view: the artifact fills the main column; the originating
     question docks beside it (sticky) so it can be answered with the
     review in front of you. Wider than the 72ch reading column. */
  body.review .wrap { max-width:1360px; }
  /* /file joins the width exceptions (#351, "a bit wider of a body"): code
     wants columns, and the wider body is what makes "no line wrapping"
     readable rather than a scroll on every line. 110ch, not review's
     1360px — this is still a reading column, just one sized for source.
     The column glides on the same body.wsliding mechanism as /review (the
     class is toggled beside 'review' at the same three sites), and a
     direct load arrives already wide. */
  body.file .wrap { max-width:110ch; }
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
  /* THE SPLIT (#305), in his words while he was reading one: "should be able
     to scroll the question alongside a review document… an invisible vertical
     bar between review doc and question being answered that allows dragging
     left/right… we also can extend the height of the review doc and RHS
     column if the height of the window allows."

     So the two are ONE window-tall pane rather than two documents stacked in
     a scrolling page: the artifact fills its column, the question scrolls
     inside its own, and neither runs off the bottom of the window. Reading
     and answering stop being two scrolls.

     `--rvh` is MEASURED (`fitReview`) rather than written as a calc, because
     the top of this pane depends on how the chrome wrapped, which depends on
     the window; the calc() is only the floor for the frames before the first
     measurement lands. `min-height` is what keeps a short window honest — at
     26rem the PAGE starts scrolling again instead of crushing both columns
     into slivers. */
  @property --rsplit { syntax:'<percentage>'; inherits:false;
                       initial-value:70%; }
  /* The question column's fade depths, head and foot, registered so they can
     travel. The initial value has to be an absolute length: a registered
     property's initial value must be computationally independent, so `1.5rem`
     would make this whole rule invalid and the mask would never resolve.
     ONE depth, stated twice, because the two ends lift on different states
     (`attop` and `atend`) and a single property could not hold both. */
  @property --qfade { syntax:'<length>'; inherits:false; initial-value:24px; }
  @property --qfoot { syntax:'<length>'; inherits:false; initial-value:24px; }
  #reviewwrap { display:grid; gap:0; align-items:stretch; margin-top:1rem;
    grid-template-columns:clamp(32ch, var(--rsplit), calc(100% - 26ch))
                          1.3rem minmax(0,1fr);
    height:var(--rvh, calc(100dvh - 12rem)); min-height:26rem; }
  /* The floors are in CSS, not in the drag handler, for #108's reason: a
     clamp holds on EVERY frame and at every window width, where a JS
     re-derivation is always one frame behind the layout it is correcting. */
  #reviewwrap.nodock { grid-template-columns:minmax(0,1fr); }
  #reviewdoc { display:flex; min-width:0; min-height:0; }
  /* border-box, because the height is now 100% of a measured pane rather
     than a vh: a content-box height plus the hairline is 2px of page scroll
     that reads as the pane not quite fitting. */
  #reviewframe { flex:1; width:100%; height:100%; min-height:0;
    box-sizing:border-box; border:1px solid var(--border);
    border-radius:var(--radius); background:var(--bg); display:block; }
  .revname { color:var(--dim); margin-left:.6rem; font-size:.8rem; }
  /* A DRAG is continuous input, so it needs no transition — his pointer IS
     the motion. A keyboard step is a discrete state change and does obey
     transitions.md, so `.rkeyed` lends the registered custom property the
     column's own easing for exactly that gesture. */
  #reviewwrap.rkeyed { transition:--rsplit .38s cubic-bezier(.32,.1,.2,1); }
  /* The bar is INVISIBLE at rest and is still a control: the gutter the eye
     already reads as space is the whole hit area, a hairline arrives on
     hover/focus/drag rather than blinking on, and it is focusable with arrow
     keys because a drag-only affordance is unreachable from a keyboard. */
  /* z-index because an ANSWERED-AWAITING card hangs its accent rail .9rem
     into this gutter (`.qa.awaiting`'s negative margin), and a positioned
     sibling later in the DOM wins the hit test: without this the bar is dead
     to the pointer for exactly the state he is in one second after
     answering — a control that works until it matters. */
  .rsplit { position:relative; z-index:2; align-self:stretch;
    cursor:col-resize; touch-action:none; }
  .rsplit::after { content:''; position:absolute; top:0; bottom:0; left:50%;
    width:1px; transform:translateX(-50%); background:var(--line); opacity:0;
    transition:opacity .45s ease, width .45s ease, background-color .45s ease; }
  .rsplit:hover::after { opacity:1; }
  .rsplit:focus { outline:none; }
  /* focus and drag both widen to 2px: at 1px an indicator this tall is a
     hair, and WCAG asks for a perimeter you can actually see. */
  .rsplit:focus-visible::after { opacity:1; width:2px;
                                 background:var(--accent); }
  .rsplit.rdrag::after { opacity:1; width:2px; background:var(--border); }
  .qdock { display:flex; flex-direction:column; min-height:0; min-width:0;
    will-change:transform, filter; }
  .qdock .label { margin-top:0; flex:none; }
  /* THE QUESTION SCROLLS ALONGSIDE (#305 (a)) — and what scrolls is the
     question's BODY, not the whole card (#326). The dock is not the scroller,
     so `answering` stays put as a column head — it says what this column IS,
     and a heading that scrolls away with its first paragraph makes the reader
     ask again. The card is not the scroller either, and that is the whole of
     #326: a scrollport that contains the answer box cannot fade its text at
     the box without fading the box, so the scrollport stops one element
     short. `scrollbar-gutter` keeps the text from re-wrapping the moment a
     live re-render changes the card's length. */
  /* the card's own 1rem bottom margin goes: "in line with the bottom of the
     review document" is a measurable claim and 16px is a visible miss. The
     card's border edge and the iframe's now end on the same line. */
  .qdock > .qa { flex:1 1 auto; min-height:0; margin-bottom:0;
    display:flex; flex-direction:column; }
  /* BOTH EDGES FADE, and they are one gesture mirrored rather than two
     mechanisms (#326 corrects #305 (c), which had a gradient BAND at the foot
     and a mask at the head). His words: "the black stuff around the answer box
     to emulate the fade thing is ugly. the text itself should fade, not be
     covered by fake fade. and the buttons and text box shouldn't have anything
     behind them". A band emulates a fade by painting `--bg` over whatever is
     behind it — which on this page is the living shader — and it has to be as
     tall as the box, so the box ends up sitting on a black plate. A mask fades
     the GLYPHS and paints nothing at all.

     Why a mask is now sayable when #305 argued it was not: the objection was
     true of a scroller that contained the box ("a mask over the scroller
     cannot be told about the box, and would dim his last line"). It is not
     true of one that stops where the box begins. The mask's bottom edge IS the
     scrollport's bottom edge, which is exactly where the text used to run into
     the band, and the box is outside the masked element entirely — so there is
     literally nothing behind it and nothing dimming it.

     Head: making the body a scroller cut the first visible line in half
     directly under `answering`, and half a row of glyph-tops under a heading
     reads as a rendering fault rather than as scrolled text. Both depths are
     registered properties so each edge ARRIVES when it is needed and departs
     when it is not (transitions.md), instead of blinking.

     The `transition` shorthand is safe HERE, where the same declaration on
     `.qdock > .qa` would not be: a shorthand on a more specific selector
     replaces the list wholesale, and `.qa` carries the card's own travel,
     which the one route that also re-groups cards would then lose. `.qbody`
     has no other transition to clobber. */
  /* `display` is stated, and it is not a formality: the base rule makes this
     element generate no box at all, and everything below — the flex sizing,
     the scrollport, the mask — is silently inert without it. A block box
     rather than a flex column, so the question's paragraphs collapse their
     margins here exactly as they do on /questions. */
  .qdock > .qa > .qbody { display:block; flex:1 1 auto; min-height:0;
    overflow-y:auto; scrollbar-gutter:stable;
    -webkit-mask-image:linear-gradient(to bottom, transparent, #000 var(--qfade),
      #000 calc(100% - var(--qfoot)), transparent);
    mask-image:linear-gradient(to bottom, transparent, #000 var(--qfade),
      #000 calc(100% - var(--qfoot)), transparent);
    transition:--qfade .45s ease, --qfoot .45s ease; }
  .qdock.attop > .qa > .qbody { --qfade:0px; }
  /* ...and the foot lifts when the body already ends at the box — his own
     exception, carried over from #305 (c) unchanged in meaning: at the end of
     the scroll nothing passes under the box, so a fade there would be dimming
     his last line to hide nothing. A state with two ends, so it crosses
     (transitions.md) rather than switching. */
  .qdock.atend > .qa > .qbody { --qfoot:0px; }
  /* (b) THE INPUT IS GLUED TO THE BOTTOM, in line with the artifact's bottom
     edge — his second ask, and the reason the first one is worth anything: a
     question you can scroll past an answer box you cannot reach is still two
     acts. `.qcompose` stays the shared component three other surfaces render
     and four functions address through the card (`snapshotCardState`,
     `setCardMode`, `submitCard`, the mode group) — it is the LAST FLEX ITEM of
     a card that does not scroll, which is glued by construction and needs
     neither `position:sticky` nor `margin-top:auto` to be so. #305 needed both
     and paid for them: sticky only holds a box the flow would push out of
     view, so a SHORT question left the box floating mid-column with 200px of
     dead space beneath it (at 1240px the artifact ended at 1200 and the box at
     974), and the `margin-top:auto` that fixed that made every child of the
     card a flex item, so its internal margins stopped collapsing and the dock
     card ran ~20px taller than the same card on /questions. Both go: the
     scroller takes the leftover space, the box takes what it needs, and the
     body is a plain block box again, so it collapses margins the way
     /questions does.
     The bottom margin still goes and the .3rem padding stays, so the box's
     border edge lands on the artifact's bottom line with air under its
     buttons — the geometry #305 measured, reached without sticky. */
  .qdock > .qa > .qcompose { margin-bottom:0; padding-bottom:.3rem; }
  @media (prefers-reduced-motion:reduce) {
    #reviewwrap.rkeyed { transition:none; }
    .rsplit::after { transition:none; }
    .qdock > .qa > .qbody { transition:none; }
  }
  /* NARROW STACKS, it does not crush. Below 900px there is no room for two
     readable columns, so the pane goes back to being a document: one column,
     natural heights, the page scrolls, and the bar is gone rather than
     present-but-useless (display:none takes it out of the tab order too). */
  @media (max-width:900px) {
    /* #434: body padding is 2.5rem top and bottom (40px). Desktop keeps that
       as its accepted ~40px foot; on a phone the same pad was sitting under
       a 60vh frame that had already thrown away 200px, so reclaiming the
       frame without also tightening the foot left 40px of "empty" that the
       brief's <24px bar still fails. The review route alone drops the bottom
       pad to 1rem on the stacked layout — the top pad and every other route
       keep 2.5rem. fitReview reads paddingBottom, so --rvh grows with it. */
    body.review { padding-bottom:1rem; }
    #reviewwrap { grid-template-columns:minmax(0,1fr); height:auto;
                  min-height:0; }
    .rsplit { display:none; }
    /* #434: 60vh was a fixed fraction of the WINDOW, not of the room left
       under the chrome — at 390x844 that is 506px of frame and ~200px of
       empty viewport (scrollHeight === innerHeight; nothing off-screen).
       fitReview already measures the remaining height into --rvh for the
       desktop pane; the narrow layout reuses that same variable so the
       frame fills the window rather than a third of it. A docked question,
       when present, stacks below and the page scrolls — the narrow layout's
       own rule. No height transition: the pane is measured layout, not a
       gesture (transitions.md); reduced-motion parity is free. */
    #reviewdoc { height:var(--rvh, calc(100dvh - 12rem)); min-height:12rem; }
    #reviewframe { height:100%; }
    /* no inner scroller, so nothing is glued and nothing passes under the
       box: both would be lying about a column that is now just a document.
       ONE line does all of it, because the wrapper goes back to the value it
       has on every other route: `display:contents` generates no box, and an
       element with no box carries no scrollport and no mask. Anything that
       switched the fades off by name would have to name each of them, and
       #326's whole point is that they are now one element's property. */
    .qdock > .qa > .qbody { display:contents; }
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
  /* The page's title is a real `<h1>` on every route (#284) — one top-level
     label per document, which is what a screen reader's heading list is for,
     and what `/file`'s copy button describes itself by. It carries NO weight
     or size of its own: emphasis on this page is luminance (see Type &
     geometry), and a UA-bold 2em heading would say "more important" twice
     while changing the metrics the + is centred against (#123).

     flex:1 soaks the free space so #hproj can sit on the bar's trailing
     edge without the route word's length shoving it (#172). */
  .htitle { display:inline; font:inherit; margin:0;
            flex:1 1 auto; min-width:0; }
  /* Project identity in the title bar (#172). The route word varies; the
     project does not — so the name is pinned to the TRAILING edge of the
     bar (margin-left:auto), not placed beside the route where a longer
     word would slide it. Basename only in the bar; the full path rides
     `title=` because two checkouts can share a basename (see popoutShell
     and the openPopout comment) and a full path in an h1 competes with
     the subject the way #284 already ruled against for file paths. Same
     size and --bright as the heading: this is identity, not a breadcrumb. */
  .hproj { flex:none; margin-left:auto; color:var(--bright); font:inherit;
           white-space:nowrap; max-width:42%; overflow:hidden;
           text-overflow:ellipsis; }
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
  /* #177 — the box grows with what he types, on the page's one height-travel
     gesture (.85s, the same curve #104's regroup and the card fold use), then
     scrolls past its own ceiling. `resize:none` because autosize OWNS the
     height: a manual drag and a content fit fighting over `height` is a box
     that loses the user's resize on the next keystroke. The ceiling is a
     per-surface contract carried as `data-max-rows` (composer 15, answer 6 —
     see fitText); reduced motion keeps the growth (function) and drops only
     the timing, the page's standing rule. */
  /* #464 — reserve the scrollbar gutter so the text never reflows when the
     box grows tall enough to hold every line and the bar would vanish.
     `scrollbar-gutter:stable` is the gutter-without-furniture reading of
     "always show": the reflow is the reported distraction, and a permanent
     bar would add chrome the rest of the page deliberately avoids. Overflow
     still scrolls past the 15-row ceiling; reduced-motion only drops the
     height timing (above) and does not touch the gutter. */
  #cmdform textarea { width:100%; box-sizing:border-box;
    background:var(--panel); color:var(--text); border:1px solid var(--line);
    border-radius:var(--radius); font:inherit; padding:.4rem; margin:.3rem 0;
    min-height:3.4rem; resize:none; overflow:auto; scrollbar-gutter:stable;
    transition:height .85s cubic-bezier(.32,.1,.2,1); }
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
  /* #290 run mode — same sliding group as tint/command kinds. Active mode
     takes the accent (it is live loop control, not a settled preference).
     Hierarchical is discoverable but disabled until #264/#288. The 10s arm
     progress is a linear width on the fill; reduced motion hides the bar and
     keeps the second-by-second text countdown so function is identical. */
  .runmode { margin:.55rem 0 .35rem; }
  .runmodes { margin:.2rem 0 .1rem; }
  .runchip { padding:.24rem .55rem; font-size:.7rem; }
  .runchip:disabled, .runchip[aria-disabled="true"] {
    color:var(--dimmer); cursor:default; opacity:.72; text-shadow:none; }
  .runchip:disabled:hover, .runchip[aria-disabled="true"]:hover {
    color:var(--dimmer); }
  .runarm { margin:.35rem 0 0; min-height:1.15rem; }
  .runbar { height:3px; background:var(--line); border-radius:2px;
            overflow:hidden; margin:0 0 .28rem; }
  .runbar[hidden] { display:none; }
  .runbarfill { height:100%; width:100%; background:var(--muted);
    border-radius:2px;
    transition:width 10s linear; transform-origin:left center; }
  .runbarfill.snap { transition:none; }
  .runcount { color:var(--dim); font-size:.7rem;
              font-variant-numeric:tabular-nums; }
  .runmsg { color:var(--warn); font-size:.7rem; margin:.25rem 0 0; }
  .runmsg:empty { display:none; }
  /* #300 — one shared description surface for the run-mode chips.
     Geometry is stable while open (min-height holds the longest line), so
     button→button swaps morph words in place rather than spawning a new
     tooltip per chip. Sits ABOVE the arm/countdown, never over it.
     Arrival/departure: atmospheric blur+drift (cmdmsg's idiom). Swaps:
     shell fixed, text dissolves then resolves. Reduced motion: instant. */
  .rundesc { margin:.28rem 0 .12rem; min-height:0; max-width:100%;
    font-size:.7rem; color:var(--dim); line-height:1.4;
    overflow:hidden;
    transition:opacity .42s ease, filter .42s ease,
               transform .42s cubic-bezier(.32,.1,.2,1); }
  .rundesc[hidden] { display:none; }
  .rundesc.open { min-height:2.6em; }   /* shell holds across mode swaps */
  .rundesc.pose { transition:none !important; opacity:0;
    filter:blur(6px); transform:translateY(4px); }
  .rundesc.depart { opacity:0; filter:blur(7px); transform:translateY(-4px); }
  .rundesc-text { display:block; max-width:100%;
    transition:opacity .34s ease, filter .34s ease,
               transform .34s cubic-bezier(.32,.1,.2,1); }
  .rundesc-text.out { opacity:0; filter:blur(6px); transform:translateY(-2px); }
  .rundesc-text.in { opacity:0; filter:blur(4px); transform:translateY(2px); }
  @media (prefers-reduced-motion: reduce) {
    .runbar { display:none; }
    .runbarfill { transition:none; }
    .rundesc, .rundesc-text { transition:none; }
  }
  /* #445 three-axis posture — sibling of run-mode. Asymmetry is honest:
     pace three chips, asking four (his dictation — do not compress),
     delegation an integer target with a derived label. One shared 10s arm
     covers a whole posture edit (one file, one event), not three ceremonies.
     Active stop takes --accent (live loop control). Reduced motion hides
     the bar, keeps the second-by-second text + same application time. */
  .posture { margin:.55rem 0 .35rem; }
  /* #488: source chip sits beside the Posture heading, not under the axes. */
  .posture-head { display:flex; align-items:baseline; gap:.55rem;
    flex-wrap:wrap; margin:var(--space) 0 .5rem; }
  .posture-head .label { margin:0; }
  .posture-axes { display:flex; flex-direction:column; gap:.45rem;
    margin:.2rem 0 .1rem; }
  .paxis { min-width:0; }
  .paxis-lab { color:var(--dimmer); font-size:.65rem; letter-spacing:.06em;
    text-transform:uppercase; margin:0 0 .15rem; }
  .paxis-chips { margin:0; }
  .pchip { padding:.24rem .5rem; font-size:.7rem; }
  .pchip .pchip-short { letter-spacing:0; }
  .pstep { display:inline-flex; align-items:center; gap:.35rem;
    margin:.05rem 0; }
  .pstepbtn { background:none; border:1px solid var(--line); font:inherit;
    color:var(--muted); padding:.18rem .55rem; cursor:pointer;
    border-radius:var(--radius); line-height:1.2;
    transition:color .3s ease, border-color .3s ease; }
  .pstepbtn:hover { color:var(--accent); border-color:var(--border); }
  .pstepbtn:disabled { color:var(--dimmer); cursor:default; opacity:.72; }
  .pstepval { min-width:1.6rem; text-align:center; color:var(--lit);
    font-variant-numeric:tabular-nums; font-size:.8rem; }
  .psteplabel { color:var(--dim); font-size:.7rem; }
  .pstephint { color:var(--dimmer); font-size:.65rem; margin:.1rem 0 0; }
  .posture-src { color:var(--dimmer); font-size:.65rem; margin:0;
    text-transform:none; letter-spacing:0; font-weight:400; }
  .posture-src.file { color:var(--dim); }
  .parm { margin:.35rem 0 0; min-height:1.15rem; }
  .pbar { height:3px; background:var(--line); border-radius:2px;
          overflow:hidden; margin:0 0 .28rem; }
  .pbar[hidden] { display:none; }
  .pbarfill { height:100%; width:100%; background:var(--muted);
    border-radius:2px;
    transition:width 10s linear; transform-origin:left center; }
  .pbarfill.snap { transition:none; }
  .pcount { color:var(--dim); font-size:.7rem;
            font-variant-numeric:tabular-nums; }
  .pmsg { color:var(--warn); font-size:.7rem; margin:.25rem 0 0; }
  .pmsg:empty { display:none; }
  /* #488: description shell always reserves layout height. Visibility is
     opacity only — never display:none / never inserted-removed — so hover
     cannot reflow the card or anything below it. Empty space is intentional. */
  .pdesc { margin:.28rem 0 .12rem; min-height:2.6em; max-width:100%;
    font-size:.7rem; color:var(--dim); line-height:1.4;
    overflow:hidden; opacity:0; pointer-events:none;
    transition:opacity .42s ease, filter .42s ease,
               transform .42s cubic-bezier(.32,.1,.2,1); }
  .pdesc.open { opacity:1; pointer-events:auto; }
  .pdesc.pose { transition:none !important; opacity:0;
    filter:blur(6px); transform:translateY(4px); }
  .pdesc.depart { opacity:0; filter:blur(7px); transform:translateY(-4px); }
  .pdesc-text { display:block; max-width:100%;
    transition:opacity .34s ease, filter .34s ease,
               transform .34s cubic-bezier(.32,.1,.2,1); }
  .pdesc-text.out { opacity:0; filter:blur(6px); transform:translateY(-2px); }
  .pdesc-text.in { opacity:0; filter:blur(4px); transform:translateY(2px); }
  @media (prefers-reduced-motion: reduce) {
    .pbar { display:none; }
    .pbarfill { transition:none; }
    .pdesc, .pdesc-text { transition:none; }
  }
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
     to the other without ever leaving .cmdmore, or the menu closes en route.
     The menu is anchored to the ⋯'s RIGHT edge and grows left, because the ⋯
     sits at the right end of the kinds row: a left-anchored menu grew right
     past the viewport and — a `visibility:hidden` box is still LAID OUT, not
     `display:none` — pushed a 122px horizontal scrollbar at phone width on
     every route, palette open or shut (#312). `right:0` keeps it in bounds;
     the clamp holds the preferred 32ch wherever it fits and never lets the
     left edge cross the body's padding at any width. */
  .cmdmenu { position:absolute; z-index:31; top:100%; right:0;
    width:max(32ch,100%); max-width:calc(100vw - 2rem); padding:.3rem;
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
  /* PiP glyph: always present, quiet at rest, accent on hover/focus — the
     same card-chrome arrival as .qfocus/.qroll (no appear/disappear of its
     own; rides the surface it sits on). user-select:none so a drag across
     prose that contains a body-link pip never swallows the button into the
     selection (#505; the pip is chrome, not copy). */
  .pipbtn { background:none; border:none; color:var(--dim); cursor:pointer;
    padding:0 .35rem; line-height:1; vertical-align:middle;
    transition:color .3s ease; user-select:none; -webkit-user-select:none; }
  .pipbtn:hover, .pipbtn:focus-visible { color:var(--accent); }
  .pipbtn svg { display:inline-block; vertical-align:-2px; }
  /* #506: known-internal path + its pip are ONE unbreakable unit. Without
     nowrap the button orphans onto the next line whenever the path sits
     near a wrap edge (the path is content; the pip is chrome that must
     travel with it). The unit is short (a path + 14px glyph); long paths
     already overflow as one code token. */
  .mdfile { white-space:nowrap; }
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
    .cmdmsg, .pipbtn { transition:none; }
  }
</style>"""

APP_BODY = """<canvas id="dreambg"></canvas>
<svg id="dreamfx" width="0" height="0" aria-hidden="true"
     style="position:absolute;width:0;height:0;pointer-events:none">
 <!-- #453: the dissolve mist is ONE CACHED noise field, pre-rendered once to a
      canvas (mistTexture()) and consumed via feImage — the human's texture idea
      ("just having a single texture ... and then just like moving it"). feTile
      wraps it across the filter region, feOffset MOVES it per frame (the flow),
      and the displacement/blur envelopes are the ones stepFx always drove.
      Nothing regenerates per frame: #449 measured feTurbulence re-rasterizing
      every frame as the whole cost, with the displacement+blur math free. -->
 <filter id="dissolveOut" x="-25%" y="-25%" width="150%" height="150%"
         color-interpolation-filters="sRGB">
  <feImage class="texsrc" x="0" y="0" width="256" height="256"
           preserveAspectRatio="none" result="img"/>
  <feTile in="img" result="tl"/>
  <feOffset in="tl" dx="0" dy="0" result="n"/>
  <feDisplacementMap in="SourceGraphic" in2="n" scale="0"
                     xChannelSelector="R" yChannelSelector="G" result="d"/>
  <feGaussianBlur in="d" stdDeviation="0"/>
 </filter>
 <!-- dissolveIn is DEFINED BUT NOT APPLIED (#453): the second full-page
      rasterisation is what fails the frame budget — one filtered element
      costs ~30% of rAF frames on this route, two cost ~50%, and the incoming
      view's mist was always its subtlest half (peak displacement lands while
      opacity is near 0). The arrival's haze rides the compositor CSS blur
      (5px→0, the ungated #view rules). Kept defined so a future mechanism
      can re-apply it without re-authoring. -->
 <filter id="dissolveIn" x="-25%" y="-25%" width="150%" height="150%"
         color-interpolation-filters="sRGB">
  <feImage class="texsrc" x="0" y="0" width="256" height="256"
           preserveAspectRatio="none" result="img"/>
  <feTile in="img" result="tl"/>
  <feOffset in="tl" dx="0" dy="0" result="n"/>
  <feDisplacementMap in="SourceGraphic" in2="n" scale="0"
                     xChannelSelector="R" yChannelSelector="G" result="d"/>
  <feGaussianBlur in="d" stdDeviation="0"/>
 </filter>
 <!-- #449: the shelved per-frame feTurbulence versions, kept for comparison
      (MIST_IMPL 'turbulence' in crossfade). Measured 2026-07-29: they cost
      the dissolve +128% of rAF frames vs none. Do not re-enable casually. -->
 <filter id="dissolveOutT" x="-25%" y="-25%" width="150%" height="150%"
         color-interpolation-filters="sRGB">
  <feTurbulence type="fractalNoise" baseFrequency="0.009" numOctaves="1"
                seed="7" result="n"/>
  <feDisplacementMap in="SourceGraphic" in2="n" scale="0"
                     xChannelSelector="R" yChannelSelector="G" result="d"/>
  <feGaussianBlur in="d" stdDeviation="0"/>
 </filter>
 <filter id="dissolveInT" x="-25%" y="-25%" width="150%" height="150%"
         color-interpolation-filters="sRGB">
  <feTurbulence type="fractalNoise" baseFrequency="0.009" numOctaves="1"
                seed="7" result="n"/>
  <feDisplacementMap in="SourceGraphic" in2="n" scale="0"
                     xChannelSelector="R" yChannelSelector="G" result="d"/>
  <feGaussianBlur in="d" stdDeviation="0"/>
 </filter>
 <filter id="departMist" x="-25%" y="-25%" width="150%" height="150%"
         color-interpolation-filters="sRGB">
  <feImage class="texsrc" x="0" y="0" width="256" height="256"
           preserveAspectRatio="none" result="img"/>
  <feTile in="img" result="tl"/>
  <feOffset in="tl" dx="0" dy="0" result="n"/>
  <feDisplacementMap in="SourceGraphic" in2="n" scale="0"
                     xChannelSelector="R" yChannelSelector="G" result="d"/>
  <feGaussianBlur in="d" stdDeviation="0"/>
 </filter>
</svg>
<div class="wrap">
<div id="chrome">
 <header class="htitlebar"><button id="cmdplus" type="button"
   title="command the dream" aria-label="open command palette">+</button>
  <h1 class="htitle" id="htitle"></h1>
  <span class="hproj" id="hproj" hidden></span></header>
 <div id="meta"></div>
 <div class="cmdmsg fmsg" id="fmsg" aria-live="polite"></div>
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
  <textarea id="cmdtext" placeholder="a thought for the dream…"
            data-max-rows="15"></textarea>
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
/* the same age at commit resolution (#132 / #385): TWO units, each zero-
   padded to two digits — `05m 23s`, `02h 14m`, `03d 07h`, `02w 03d`,
   `01y 14w`.

   Two edges, both decided rather than fallen into:
     · under a minute it still reads as two units (`00m 12s`), so the column
       never changes width — and seconds-old is exactly when he is watching.
     · the ladder runs seconds → minutes → hours → days → weeks → years, so
       neither field reaches 100 for ~100 years (his invariant). Without the
       year and week rungs the day count alone passed 99 at 100 days.

   Year length is 365 days, not 52 weeks (= 364). A human reading `01y …`
   expects a calendar-ish year; 52 weeks of remainder inside that year is
   still ≤ 99, so the XX≤99 invariant holds either choice — but 365 matches
   the word "year" and the remainder is derived, not assumed. Weeks are
   always 7 days. */
const p2 = n => String(n).padStart(2, '0');
const AGE_Y = 365 * 86400, AGE_W = 7 * 86400;
const AGE_PAIRS = [
  ["y", AGE_Y, "w", AGE_W],
  ["w", AGE_W, "d", 86400],
  ["d", 86400, "h", 3600],
  ["h", 3600, "m", 60],
  ["m", 60, "s", 1],
];
/* {big, bu, small, su} — shared by the plain string form and the painted
   form so there is still one pair-selection path (#385). */
const ageParts = ct => {
  const s = Math.max(0, Math.floor(Date.now()/1000 - ct));
  for (const [bu, bd, su, sd] of AGE_PAIRS)
    if (s >= bd)
      return {big: Math.floor(s/bd), bu, small: Math.floor((s % bd)/sd), su};
  return {big: 0, bu: 'm', small: s, su: 's'};
};
const agePair = ct => {
  const p = ageParts(ct);
  return `${p2(p.big)}${p.bu} ${p2(p.small)}${p.su}`;
};
/* The pad digit of a single-figure unit is quieter than the value (#385):
   only the leading 0 of `05` / `09` wears `.agepad` — never a genuine tens
   digit. Shared by the two-figure and one-figure painters so the grey rule
   stays one path, not two that can drift apart. */
const pushFig = (frag, n) => {
  if (n < 10) {
    const pad = document.createElement('span');
    pad.className = 'agepad';
    pad.textContent = '0';
    frag.append(pad, String(n));
  } else {
    frag.append(p2(n));
  }
};
/* Write the pair into a live `.age` node — `05m 23s`, `02h 14m`. Built with
   DOM nodes rather than innerHTML — every character is a digit or unit
   letter we produced, but textContent cannot carry the pad span, and
   inventing a second parser for a four-token string would be a second
   formatter. No transition: ages() rewrites once a second as pure text
   update (transitions.md — the live mtime tick / ages sweep commits
   immediately; a digit flip is not a layout change). */
const paintAgePair = (el, ct, suffix) => {
  const p = ageParts(ct);
  const frag = document.createDocumentFragment();
  pushFig(frag, p.big);
  frag.append(p.bu, ' ');
  pushFig(frag, p.small);
  frag.append(p.su, suffix || '');
  el.replaceChildren(frag);
};
/* #392a: a date-only entry shows ONE figure, because the number of figures
   is the precision. A question title carries a day and no time, so the `ct`
   `qtHtml` builds is local midnight of that day — two figures would claim a
   sub-day time the file does not hold (a 24-minute-old entry reading
   `08h 17m ago`, every multi-day age ending in the same hour figure). So
   three days reads `03d ago` beside a timed commit's `03d 07h ago`: the
   MISSING second figure is the signal, read against the timed entries
   beside it. Reuses ageParts + the same greyed pad digit, so it is #385's
   idiom with the second figure removed rather than a second humanizer.
   An entry dated TODAY (under a day old) reads as the word `today` — `0d`
   is honest but reads as a broken zero for something filed this morning,
   and the word is the one honest thing day-only data supports. See
   watch-design.md (#392a). */
const paintDayAge = (el, ct) => {
  const s = Math.max(0, Math.floor(Date.now()/1000 - ct));
  if (s < 86400) { el.replaceChildren('today'); return; }   // same calendar day
  const p = ageParts(ct);
  const frag = document.createDocumentFragment();
  pushFig(frag, p.big);
  frag.append(p.bu, ' ago');
  el.replaceChildren(frag);
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
/* expand(): plain read peeks — dreams, .md files, status overflow.

   `keep` is a content-stable id for snapshotFolds / restoreFolds. It is NOT
   the summary text: summaries carry live counts (`the rest (6)`,
   `archive (3)`) that shift while the disclosure's identity does not. Without
   data-keep the live tick rebuilds the dashboard through innerHTML and the
   disclosure reappears closed under him (~2s /mtime poll; status.json
   rewrites force a re-render). Same class as #141 qsec / #494 tip: open state
   is his, nowhere on disk; restore is silent (`el.open = true`, no re-pose).
   Counted summaries MUST pass keep explicitly. */
const expand = (s, inner, cls='', keep='') => {
  const attr = keep ? ` data-keep="${esc(keep)}"` : '';
  return `<details class="peek"${attr}><summary class="${cls}">${s}</summary>` +
         `${inner}</details>`;
};
/* Backticked references become links only when the destination is known.
   `github.com/…` is an external URL; target files come from the collector's
   closed set. Everything else stays code — a broken link is a false promise.
   #506: a known-internal file link also carries the page's ONE pop-out
   affordance (`pipBtn`) immediately after the backticked span — same closed
   set as the link itself, never a second list. External and unknown get
   none: a pip floats a local view, and a pip on a 404 is a false promise.
   The pip sits OUTSIDE the backticks so mdSpans wraps only the path in
   <code> and the button stays chrome (not copy, not code); both ride a
   `.mdfile` nowrap unit so the glyph never orphans onto the next line. */
const linkify = h => h.replace(
  /`([\\w.-]+(?:\\/[\\w.-]+)+\\/?|[\\w-]+\\.[\\w]{1,8})`/g,
  (m, p) => {
    if (p.startsWith('github.com/'))
      return '`<a href="https://' + p + '">' + p + '</a>`';
    if (data && Array.isArray(data.linkable_paths) &&
        data.linkable_paths.includes(p)) {
      const url = '/file?p=' + encodeURIComponent(p);
      return '<span class="mdfile">`<a href="' + url + '">' + p + '</a>`' +
             pipBtn(url, p) + '</span>';
    }
    return m;
  });
const preB = t => `<pre>${linkify(esc(t))}</pre>`;
/* a backticked path to a review artifact docks THIS question onto the
   review page (carries its title); every other path stays a /file link.
   #472: the corpus mostly writes `.dreamwork/review/name.html` in backticks,
   which this always handled. One outlier wrote a markdown link
   [`name`](../review/name.html) — mdSpans has no [text](url) pass, and the
   relative `../review/` path is wrong for /questions — so the artifact was
   unreachable from the ask. Prefer the backticked shape; ALSO recognise
   markdown links whose target is a review artifact (basename after
   `../review/` or `.dreamwork/review/`) so a live entry that used the
   outlier shape still docks. A bare relative href is never left as-is. */
const revDock = (name, title, label) =>
  '<a class="rev" href="/review?p=' + encodeURIComponent(name) +
  '&q=' + encodeURIComponent(title) + '">' + label + '</a>';
const linkifyReview = (escaped, title) => {
  // 1. markdown links to a review artifact — the #417 defect shape.
  //    Label may itself be backticked (`name`); strip those so the dock
  //    link is the affordance, not nested code around raw brackets.
  let h = escaped.replace(
    /\\[(?:`)?([^\\]`\\n]+?)(?:`)?\\]\\((?:\\.\\.\\/review\\/|\\.dreamwork\\/review\\/)([\\w.-]+\\.html?)\\)/g,
    (m, text, name) => revDock(name, title, text));
  // 2. preferred corpus shape: backticked `.dreamwork/review/name.html`
  //    (link stays inside backticks so mdSpans wraps it in <code>, same as
  //    every other path linkifier on this page).
  h = h.replace(
    /`\\.dreamwork\\/review\\/([\\w.-]+\\.html?)`/g,
    (m, name) => '`' + revDock(name, title, '.dreamwork/review/' + name) + '`');
  return h;
};
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
    ` data-max-rows="6"` +
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
/* #385: the date already lives in the title (`YYYY-MM-DD — …`, optional
   `P1 · ` prefix). Humanized age sits next to that date via the same
   `data-ct` + `paintAgePair` path commits use — one formatter, not a second.
   No date in the title → plain escape, same as before.
   #392a: a DATE-ONLY title is day-precision, so the span carries
   `data-day="1"` and ages() routes it to `paintDayAge` — one figure, not
   two. The flag is the precision of the input, read by the dispatch.
   #392b: an optional local ` HH:MM` after the date is a TIMED title. Its
   `ct` is that clock time (not midnight), and there is no `data-day`, so
   ages() uses paintAgePair — two figures, exact to the minute. Unknown
   time stays honestly imprecise (#392a); a known time must not fabricate
   from midnight. Same ` HH:MM` shape note tags already carry. */
const qtHtml = title => {
  // doubled backslashes: this lives in a Python string; the emitted JS
  // still sees a single backslash before each digit class.
  const m = /^(P[123] · )?(\\d{4}-\\d{2}-\\d{2})(?: (\\d{2}:\\d{2}))?( — )([\\s\\S]*)$/.exec(title || '');
  if (!m) return esc(title);
  const [, prio, date, time, sep, rest] = m;
  const [Y, Mo, D] = date.split('-').map(Number);
  let ct, dayAttr = '';
  if (time) {
    const [h, mi] = time.split(':').map(Number);
    ct = Math.floor(new Date(Y, Mo - 1, D, h, mi).getTime() / 1000);
  } else {
    ct = Math.floor(new Date(Y, Mo - 1, D).getTime() / 1000);
    dayAttr = ' data-day="1"';
  }
  const when = esc(date) + (time ? esc(' ' + time) : '');
  /* #456: chrome's ` · ` between date and age so the eye finds where the
     date ends — bare adjacency made `2026-07-28 01d ago` one continuous
     digit run. Same glyph/spacing as every other chrome separator.
     #473: an optional "updated X ago" rides the same separator + ages()
     sweep (data-ut). ages() writes pure text — no transition on the
     second-by-second digit flip (the ages() contract). The NODE's first
     appearance is an arrival (revealQuestionUpdates → .dreamin). */
  /* #474: the separator is a NODE, not bare text, and that is load-bearing
     rather than tidy. Everything in this headline that is not the question's
     title has to be removable as a node, because two guards ask "is this
     still the question I docked?" of the headline minus its chrome — see
     dockHeadline in dev/capture/dom.mjs. #456 added this ` · ` as bare text
     between the date and the age span, so stripping the age node left the
     middot behind and the raw title stopped being a substring of the result.
     Both dock guards went red on a page that was behaving correctly, which
     is exactly the failure dom.mjs's own comment predicted. It is `.rsep`
     because #473's separator two functions down already is — one idiom, and
     the two middots in one headline now match instead of one being dimmer
     than the other. */
  return `${esc(prio || '')}${when}<span class="rsep"> · </span>` +
    `<span class="age qage" data-ct="${ct}"${dayAttr}></span>` +
    `${esc(sep)}${esc(rest)}`;
};
/* #473 — optional secondary after the created age. Emitted only when the
   server stamped updated_at (a real content change after first sight).
   ages() decides whether the figure is honest enough to show (#463 lesson:
   suppress when ageStr(updated) === ageStr(created)). */
const qUpdatedHtml = q => {
  const u = q && q.updated_at;
  if (u == null || !(u > 0)) return '';
  return `<span class="rsep"> · </span>` +
    `<span class="age qup" data-ut="${u}" data-q-upd="${esc(q.title || '')}"></span>`;
};
/* #452 — the way IN to the focused page, on every card in every state (a
   folded entry can be focused too: a settled question stays findable). A
   REAL LINK, the #252 argument three ways: the href makes it deep-linkable
   and copyable, keyboard operation is native, and the click rides the
   router's existing dissolve because isInternal already claims /question —
   a button would re-implement all three. The key is the title identity the
   card itself carries as data-qid, so the link and the card cannot
   disagree about which question they name. It is headline CHROME, so it is
   a node with a class, and that class is listed in dockHeadline (#474's
   rule). Suppressed on the focus page itself — the page IS the focus —
   which is a per-view read of the same `view` the router owns. */
const qfocusLink = title =>
  (typeof view !== 'undefined' && view && view.name === 'question') ? '' :
  ` <a class="qfocus" href="/question?qid=${encodeURIComponent(title)}"` +
  ` title="focus this question — open it on its own page"` +
  ` aria-label="focus this question on its own page">focus</a>`;
/* #454 — the way to roll an OPEN question up to the top of its scroll:
   the card clamps to a 5-6 line card rather than vanishing behind a
   title, because a title alone does not say whether an entry still needs
   him and the rolled top of the body does. A REAL BUTTON, the same
   argument the focus link makes three ways: keyboard operation is native,
   aria-expanded says the disclosure state to AT, and it rides the card's
   own arrival rather than appearing. Open state ONLY — the styleguide's
   axis already answers for the other two: awaiting still needs the loop
   (it does not collapse), and folded IS the collapse (#111). Emitted
   everywhere the focus link is, including the dock, where CSS declines it
   (the dock card is the reading surface; it is never rolled) — which is
   why `.qroll` is listed in dom.mjs's dockHeadline chrome strip (#474's
   rule: headline chrome is a node, and the node is listed there).
   Suppressed on the focus page itself, like the focus link. */
const qrollBtn = title =>
  (typeof view !== 'undefined' && view && view.name === 'question') ? '' :
  ` <button type="button" class="qroll" aria-expanded="true"` +
  ` title="roll this question up to its first lines"` +
  ` aria-label="roll this question up to its first lines">roll up</button>`;
const qaInner = (q, key) => {
  const st = qaState(q, key);
  const body = q.body && q.body.trim() ? mdBReview(q.body.trim(), q.title) : '';
  const [settled, since] = qaThread(q);
  /* An answer is his words as much as a note is, so it says so in the same
     vocabulary (#109, #128 part b): of two things he wrote, it must not be
     that only one is attributed. The author comes from the tag, so an answer
     tag nobody recognises gets no label rather than a guessed one.
     #446: a second answer used to overwrite the first at parse time; the
     parser now retains every one in `answers` (file order). Each gets its own
     attributed `.anstext` block here, so none of his words vanish on the
     rail either. With one answer the DOM is byte-identical to before, so the
     submit-morph's `flipDock` on the first `.anstext` and the wisp guard are
     unchanged; the first answer stays the resolution anchor the thread is
     cut around. */
  const ansBlocks = (st === 'awaiting')
    ? (q.answers && q.answers.length
        ? q.answers
        : (q.answer != null
            ? [{text: q.answer, when: q.answer_when, by: q.answer_by}]
            : []))
    : [];
  const answer = ansBlocks.length
    ? `<div class="anstag">answered · awaiting fold</div>` +
      ansBlocks.map(a => `<div class="anstext">` +
        (WHO[a.by] ? `<span class="who">${WHO[a.by]}</span>` : '') +
        stamp(a.when) + `${mdInline(a.text)}</div>`).join('')
    : '';
  /* WHAT THE QUESTION SAYS IS WRAPPED; THE BOX HE ANSWERS IT WITH IS NOT
     (#326). `.qbody` is the review dock's scrollport, so it holds everything
     that should scroll — the title included, which is what #305 designed and
     why its head fade is described as landing under `answering` rather than
     under the title. A pinned title would also cost reading height without a
     bound: at the 32ch floor a long one can run six lines and never scroll
     away. On every route but the dock the wrapper generates no box at all
     (`display:contents`), so this is one structure rather than two — which is
     what lets `qacard.mjs` keep comparing the dock's card with /questions'
     card shape for shape, and what lets the submit morph restate a dock card
     through this same function without rebuilding the dock's layout.

     A FOLDED entry keeps its title OUT of the wrapper, and has no choice: the
     title IS the `<summary>`, which must be the disclosure's first child. The
     wrapper's membership therefore differs by state — which nothing downstream
     can see, because everything that reads the card's own children looks
     through the wrapper (`cardBody`) and no dock card is ever folded. */
  const foot = followThread(settled, true) + answer + followThread(since, false);
  const compose = qaCompose(key, st, q.title);
  /* #473: updated-ago sits on the title line beside the created age, so it
     is part of the headline chrome rather than a second fact buried in the
     body. Folded entries carry it in the summary for the same reason the
     created age is there — a settled entry that cannot be found again has
     simply been hidden. */
  const up = qUpdatedHtml(q);
  const focus = qfocusLink(q.title);
  const roll = st === 'open' ? qrollBtn(q.title) : '';
  if (st === 'folded')
    return `<details class="qfold"><summary class="qt">${qtHtml(q.title)}${up}` +
      (q.when ? `<span class="qwhen">answered ${esc(q.when)}</span>` : '') +
      `${focus}</summary><div class="qbody">${body}${foot}</div>${compose}</details>`;
  return `<div class="qbody"><div class="qt">${qtHtml(q.title)}${up}${roll}${focus}</div>` +
         `${body}${foot}</div>${compose}`;
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
/* the ONE IndexedDB helper, generalized rather than duplicated (#454):
   the open and the transaction are the wedged-store discipline — every
   failure resolves null, nothing throws at a caller — and each database
   says only what its upgrade creates. A second copy of this for a second
   store is how one of them loses the raced-timeout handling. */
function idbOpen(name, upgrade) {
  return new Promise(res => {
    if (!name || typeof indexedDB === 'undefined' || !indexedDB) return res(null);
    let rq;
    try { rq = indexedDB.open(name, 1); } catch (e) { return res(null); }
    rq.onupgradeneeded = () => upgrade(rq.result);
    rq.onsuccess = () => res(rq.result);
    rq.onerror = rq.onblocked = () => res(null);
  });
}
/* one transaction, always closed, never throwing at the caller */
function idbTx(openFn, store, mode, fn) {
  return openFn().then(db => new Promise(res => {
    if (!db) return res(null);
    let out = null;
    const done = v => { try { db.close(); } catch (e) {} res(v); };
    try {
      const tx = db.transaction(store, mode);
      const rq = fn(tx.objectStore(store));
      if (rq) rq.onsuccess = () => { out = rq.result; };
      tx.oncomplete = () => done(out);
      tx.onerror = tx.onabort = () => done(null);
    } catch (e) { done(null); }
  })).catch(() => null);
}
function subsOpen() {
  return idbOpen(subsDbName(), db => {
    if (!db.objectStoreNames.contains(SUBS_STORE))
      db.createObjectStore(SUBS_STORE, { keyPath:'id', autoIncrement:true });
  });
}
function subsTx(mode, fn) { return idbTx(subsOpen, SUBS_STORE, mode, fn); }
/* ── persisted UI state (#454) ──────────────────────────────────────────
   "Persisted to IndexedDB and kept in sync like other ui state." A SEPARATE
   database from the submissions log, for that log's own reason (a separate
   database cannot leak by omission): the subs store is an append-only
   record of what he SENT; this one is keyed state about how the page
   LOOKS — today the rolled questions. Same wedged-store discipline through
   the shared helper, and the write is raced the same way: a roll is a
   gesture, and a gesture never waits on storage.
   Cross-tab sync is no new mechanism either: the standing 'storage'-event
   idiom (#290's pending mode) carries the ping; IndexedDB carries the
   truth a reload reads back. */
const UI_STORE = 'ui';
const uiDbName = () => {
  const t = (typeof data !== 'undefined' && data && data.target) || '';
  return t ? 'dw-ui:' + t : '';
};
function uiOpen() {
  return idbOpen(uiDbName(), db => {
    if (!db.objectStoreNames.contains(UI_STORE))
      db.createObjectStore(UI_STORE, { keyPath:'k' });
  });
}
const uiTx = (mode, fn) => idbTx(uiOpen, UI_STORE, mode, fn);
const UI_WAIT_MS = 250;
const uiPut = (k, v) => Promise.race([
  uiTx('readwrite', st => st.put({ k, v, at: Date.now() })),
  new Promise(r => setTimeout(() => r(null), UI_WAIT_MS)),
]);
const uiAll = () => uiTx('readonly', st => st.getAll());
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
/* The one verdict on a write's response, in one place (#263 E5b). Every POST
   path whose response decides whether to clear a box, clear a draft, or show a
   confirmation asks this — never `res.ok` alone. E5 made body-validation
   failures a 202 with a durable `rejected` transition and a bounded reason,
   and 202 makes `res.ok` true, so `res.ok` confirms a write that did not
   happen — and on /answer and /comment that confirmation clears the draft,
   which was the only remaining copy of what he typed. A Response body can be
   read ONCE, so this is the single reader: `postJSON` calls it and stashes the
   verdict on the Response it returns; the three raw-fetch sites (/tint,
   /run-mode, the popped-out command) each own their own Response and call it
   directly. `landed` is the whole rule — ok AND not rejected — and it is the
   one thing every write surface checks. */
async function writeVerdict(res) {
  if (!res) return { landed: false, rejected: false, reason: null, status: 0 };
  let j = null;
  try { j = await res.json(); } catch (e) { j = null; }
  const rejected = !!(j && j.rejected === true);
  return { landed: res.ok && !rejected, rejected,
           reason: (j && j.reason) || null,
           // `detail` narrows a closed-set reason for copy only (#462): several
           // distinct refusals share one contract reason, and a route that can
           // say which one must be able to. Never gated on — `landed` is.
           detail: (j && j.detail) || null, status: res.status };
}
const postJSON = async (url, body) => {
  const id = await subsRecord(url, body);
  let res = null;
  try { res = await fetch(url, { method:'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(body) }); } catch (e) { res = null; }
  const v = await writeVerdict(res);
  if (res) res._dwv = v;   // single body read; callers ask the verdict, not res.ok
  // the outcome #175's ledger records is the VERDICT's, not res.ok's: a
  // rejected 202 used to record 'ok' — the exact lie this fixes — so a tab
  // that dies mid-send no longer lies that a rejected body landed.
  subsOutcome(id, !res ? 'unreachable' : (v.landed ? 'ok' : 'rejected'),
              v.status);
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
/* Why a body was REJECTED (E5: 202 + a durable `rejected` transition), in his
   terms. The server's reason code names the protocol; this names the problem.
   Closed set, paired with REJECTION_REASONS in user_events/sqlite.py — a code
   outside the set falls through to the status line, never an unrecognised
   string. Voice is watch-design.md's: a state, an em dash, what he can do. */
/* #462 — per-route narrowing of a closed-set reason, for copy only. In his
   voice: what happened and what it means for him, never a code. */
const DEPLOY_WHY = {
  in_flight: 'this page will pick up the new one when it lands',
  not_local: 'the update only runs from the machine serving the page',
};
const REJECT_WHY = {
  malformed_json: 'the request body could not be read',
  schema_invalid: 'a required field was missing or the wrong shape',
  domain_invalid: 'the value was not one the server accepts',
};
function qaFail(card, v) {
  const comp = card && card.querySelector('.qcompose');
  if (!comp) return;
  let m = comp.querySelector('.qerr');
  if (!m) { m = document.createElement('div'); m.className = 'qerr';
            comp.appendChild(m); }
  // his words stay in the box: the send failed, so the text is the only copy.
  // a rejected body (202 + rejected:true) is the same failure as a refused one
  // — the box does not clear and the morph does not run — so it says so in the
  // same idiom: a reason in his terms, then the consequence.
  const why = (v && v.rejected && v.reason && REJECT_WHY[v.reason]) ||
              (v && QSEND_WHY[v && v.status]);
  const head = (v && v.rejected) ? 'not written (rejected)'
                                 : `not written (${(v && v.status) || 0})`;
  m.textContent = `${head} — ${why || 'the server refused it'}` +
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
    mdB(d.content), '', `dream:${d.name}`);
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
const ST_GLANCE = ['awaiting_human', 'push', 'task', 'goal', 'agents', 'queue',
                   'last_tick', 'last_commit'];
const ST_AGENT_GLANCE = ['name', 'in_flight'];
function statusBlock(s, handoffs) {
  if (!s || typeof s !== 'object') return '';
  const hands = Array.isArray(handoffs) ? handoffs : [];
  const arr = v => Array.isArray(v) ? v : (v == null ? [] : [v]);
  const agents = arr(s.agents).filter(a => a && typeof a === 'object');
  let h = `<div id="status">` + label('status');
  // 0. can the loop reach him at all. A push that failed is the master fault
  //    here — it contextualises everything under it: an `awaiting_human` list
  //    the loop cannot deliver, a task he will never be pinged about. It goes
  //    first, in the page's one BROKEN colour, naming the channel and the
  //    reason because the remedy is his and "push down" alone sends him
  //    hunting (the 403 and the credit message are the actionable part).
  //
  //    QUIET BY CONSTRUCTION for the two non-fault states, and that is the
  //    half that keeps this credible: no `push` key means the loop has not
  //    tried (a fresh target), and ok:true means the last one landed. Only
  //    ok:false earns pixels. The branch is strict (`=== false`) so a missing
  //    or malformed ok — which lint catches at the writer — never reads as a
  //    fault, and a channel that is fine deserves no pixels. The three states
  //    are distinguishable from the DATA (absent / true / false), not from
  //    the render: a loop that never tried must NOT look identical to one
  //    whose pushes all land, and the browser guard asserts all three.
  const p = s.push;
  if (p && typeof p === 'object' && p.ok === false) {
    const ch = p.channel ? esc(String(p.channel)) : 'the channel';
    const why = p.detail ? esc(String(p.detail)) : 'no reason given';
    const at = p.at ? Date.parse(p.at) : NaN;
    // `data-at` (not data-mt/data-ct): a thing that HAPPENED renders "Xm ago",
    //    grammar rather than format (see ages()) — the sweep fills the span
    //    with "Xm ago" itself, so no appended "ago" here and a space before
    //    it so "failed" and the age do not run together. NaN falls back to
    //    verbatim, the same rule as last_tick.
    const when = isNaN(at)
      ? (p.at ? esc(String(p.at)) : '')
      : `failed <span class="age" data-at="${at / 1000}"></span>`;
    h += `<div class="stpush">` +
      `<div class="stpushhead">push channel down` +
      (when ? ` · ${when}` : '') + `</div>` +
      `<div class="stpushbody">the loop cannot reach you — its last push (` +
      ch + `) came back: ` + why + `. pushes land nowhere until this clears; ` +
      `the remedy is likely yours (billing or re-auth), not the loop's. ` +
      `this dashboard keeps working either way.</div></div>`;
  }
  // 1. does anyone need HIM. First, and the one accented thing here.
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
  // hand-offs awaiting a fold (#381): a count + the ids, inside the facts row
  // rather than a second appearing block, so it reuses the status panel's one
  // tick-driven treatment and authors no second motion idiom. A coordinator
  // looking at this page constantly notices it even if a tick was skipped.
  if (hands.length)
    facts.push(esc(`${hands.length} hand-off${hands.length > 1 ? 's' : ''} to fold: ` +
                   hands.map(h => '#' + h.id).join(', ')));
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
      rest.map(k => stField(k, s[k])).join(''), 'dim', 'status-rest');
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
  // #462 — the remedy appears ONLY when the row is genuinely behind. The
  // action runs `just deploy` (re-snapshot from HEAD + restart; the generation
  // bump reloads this tab), behind the #290 arm and the page's one confirmation
  // lifecycle. Never baked with .dreamin — revealStaleAction() applies that
  // start pose once, on the current→behind transition only (see setContent).
  const remedy = s.state === 'behind'
    ? ` — <button class="gservact" type="button" ` +
      `aria-label="update this page via just deploy">just deploy</button>` +
      ` to update`
    : '';
  return `<div class="gserve${loud ? ' stale' : ''}"${title}>` +
         `${say({ ...s, missing })}${remedy}</div>`;
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
   panel over. A no-body commit first shows its FULL subject (#486): the
   header's .gsub may ellipsise it, and "the subject is all of it" is a lie
   the page cannot afford when the subject is a long fold line. */
const gitDetail = c => `<div class="gdetail">` +
  `<div class="gmeta">${esc(c.full || c.sha)} · ${esc(c.who || 'unknown')}` +
  `</div>` +
  ((c.body || '').trim() ? mdB(c.body)
    : `<div class="gfullsub">${esc(c.subject)}</div>` +
      `<div class="gnone">(no message body — the subject is all of it)</div>`) +
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
/* #417: commits rides the gate too — a weight-only change is still a
   series change, even when open/arrived/landed are flat. */
const burnKey = d => ((d && d.burndown && d.burndown.buckets) || [])
  .map(b => `${b.t0}:${b.arrived}:${b.landed}:${b.open}:${b.commits || 0}`)
  .join(' ');
const BURN_STEP_NAME = { 3600: 'hourly', 14400: 'every four hours',
                         86400: 'daily', 604800: 'weekly',
                         2419200: 'every four weeks' };
/* #487: the ladder the head cycles through — same seconds as BURN_STEPS,
   fine → coarse, wrapping. One list, never a second vocabulary. */
const BURN_STEP_ORDER = [3600, 14400, 86400, 604800, 2419200];
let burnStepPref = null;   // null = server auto; else a BURN_STEP_ORDER entry
/* #499: client-side column-count limit. Default 28; <=0 means all/max;
   hard cap 168. Preference is per-target in localStorage (same family as
   burn_step — URL params would fight the posture picker's shared-arm
   idiom less, but the page already keeps small UI state for this panel in
   localStorage, and that is the tie-breaker). Cross-tab: each tab reads
   on load; no storage-event fanout (burn_step does not either) so it
   never races the posture pending key. */
const BURN_LIMIT_DEFAULT = 28;
const BURN_LIMIT_CAP = 168;
// null = use default; number is the stored preference (0 = all).
let burnLimitPref = null;
let _burnLimitDidLoad = false;
/* a bucket's label. Hourly buckets want a clock; daily and wider want a
   date, because "00:00" five times in a row is not a time axis. */
const bstamp = (t, step) => {
  const d = new Date(t * 1000);
  return step >= 86400
    ? d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    : d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
};
/* #417 c3: map ledger commits → level-line cap weight.
   0 commits → 1px (below the floor, so quiet ≠ one).
   1..peak  → 2..6px linear. Peak is always 6px; a lone commit is 2px. */
const CAP_ZERO = 1, CAP_MIN = 2, CAP_MAX = 6;
const commitCap = (n, peak) => {
  const c = Math.max(0, n | 0), p = Math.max(0, peak | 0);
  if (c <= 0) return CAP_ZERO;
  if (p <= 1) return CAP_MIN;
  return Math.round(CAP_MIN + (CAP_MAX - CAP_MIN) * (c - 1) / (p - 1));
};
const bdbar = (b, k, cls, max, peakCommits) => {
  const h = max ? Math.round((b[k] / max) * 100) : 0;
  let style = `height:${h}%`;
  // level line only: open-count height + commits weight
  if (k === 'open')
    style += `;border-top-width:${commitCap(b.commits || 0, peakCommits)}px`;
  return `<div class="bdbar ${cls}" data-bk="${b.t0}" data-series="${k}"` +
    ` data-commits="${b.commits || 0}"` +
    ` style="${style}"></div>`;
};
/* the provenance coverage (#217). THREE COUNTS AND A DENOMINATOR, read
   from the ledger's first sightings (#216): who filed each task at its
   ARRIVAL, which no later edit can reclassify. The historical unknown is
   drawn as itself — the absence of a claim — and is never added to loop
   or implied to be the loop's. The copy names what the denominator IS
   (committed first sightings in recorded git history), which is also the
   scope: an entry still uncommitted in the working tree is not a
   historical arrival and appears nowhere here. */
function provBlock(p) {
  if (!p) return '';
  const total = p.total || 0;
  if (!total)
    return `<div class="bdnote">no first sightings in recorded git history ` +
           `yet</div>`;
  const rows = [['human', p.human, 'phuman'], ['loop', p.loop, 'ploop'],
                ['historical unknown', p.unknown, 'punknown']];
  const incomplete = p.history_complete === false;
  /* the aria-label is the WHOLE datum in words: the bar is a picture of
     this sentence, and the sentence is what a screen reader gets. */
  const aria = `task provenance: ${rows.map(([n, c]) => `${n} ${c}`).join(', ')}` +
    ` — ${total} first sightings in recorded git history` +
    (incomplete ? ', coverage is incomplete (shallow clone)' : '');
  return `<div class="bdprov">` +
    `<div class="provbar" role="img" aria-label="${esc(aria)}">` +
    rows.map(([n, c, cls]) =>
      /* Flex distributes the exact remaining track after the two gaps, so
         independently rounded percentages cannot leave a false empty sliver.
         A real but tiny cohort stays visible; zero remains truly absent. */
      `<div class="provseg ${cls}" style="--share:${c};min-width:${c ? 2 : 0}px" ` +
      `title="${esc(n)} ${c}" aria-hidden="true"></div>`).join('') +
    `</div>` +
    `<div class="provline" title="${esc(rows.map(([n, c]) => `${n} ${c}`).join(' · '))}">` +
    rows.map(([n, c, cls]) =>
      `<span class="${cls}">${esc(n)} ${c}</span>`).join(' · ') +
    `</div>` +
    `<div class="provsrc">${total} first sightings in recorded git ` +
    `history</div>` +
    (incomplete
      ? `<div class="provsrc">shallow clone — first sightings before its ` +
        `boundary are invisible, so coverage is incomplete</div>` : '') +
    `</div>`;
}
/* the median filed-to-landed duration (#218). One honest number — the
   median of every filed-to-landed pair the walk already holds — and the
   population it was computed over. NOT a velocity score, a rate, or an
   index: a single duration that says how long finished work took. The
   population is the INTERSECTION of arrived and landed (the work that
   finished), so the copy says "finished" plainly: a reader otherwise
   assumes "how long work takes" and the still-open long tail is excluded,
   which is the optimistic bias the brief named. It rides the SAME age
   ladder as the commits (`ageParts`), one figure at its dominant unit —
   `1h`, `2d` — rather than a second humanizer, and the count beside it is
   the size of the population, because a median over 4 pairs and one over
   200 are different kinds of claim. NO MOTION: this panel re-renders
   through innerHTML on every tick and nothing about it is a layout change
   the page initiates (transitions.md), so this declares no transition —
   the same contract provenance holds one block up, and reduced-motion
   parity is the identical settled visual. */
function medDur(m) {
  if (!m && m !== 0) return '';
  const p = ageParts(Math.floor(Date.now()/1000) - Math.round(m));
  return p.big + p.bu;
}
function medianBlock(s) {
  const n = (s && typeof s.median_n === 'number') ? s.median_n : 0;
  /* THE NO-DATA CASE follows the panel's "which kind of nothing" idiom
     (`test_ledger_series_says_which_kind_of_nothing`): a bare `0` or a
     dash is the wrong thing under any count, because it reads as "work
     takes no time" rather than as "nothing has finished". Nothing has
     landed yet is its own sentence. (n===0 here means work has arrived
     but none of it has the pair a duration needs.) */
  if (!n)
    return `<div class="bdmed">nothing landed yet — no filed-to-landed ` +
           `duration to take the median of</div>`;
  const dur = medDur(s.median);
  /* The aria-label is the whole datum in words: the bar-less line states
     its own population and question, the way the provenance bar's label
     does. "finished" is the load-bearing word — it is what separates this
     median from the one a reader assumes. */
  const aria = `median time finished work took to land: ${dur} ` +
    `(over ${n} filed-to-landed ${n === 1 ? 'pair' : 'pairs'}; ` +
    `still-open work is not in this median)`;
  return `<div class="bdmed" role="img" aria-label="${esc(aria)}">` +
    `<span class="bdnum">${esc(dur)}</span> median time finished work ` +
    `took to land · over ${n} ${n === 1 ? 'pair' : 'pairs'}</div>`;
}
/* #417 c4: ledger-commits-per-period as one figure line. SHORTENED so it
   does not ellipsise at either viewport (his condition): the long form
   ("16 median ledger commits per period · 59 peak · 3 periods with none")
   clipped at mobile. The short form keeps the three facts — median, peak,
   empty periods — and names "commits/period" once so the unit is not
   lost. NO MOTION: settled text, reduced-motion parity free. */
function commitFigBlock(s) {
  if (!s || s.state !== 'ok') return '';
  const med = (typeof s.commit_median === 'number') ? s.commit_median : 0;
  const peak = (typeof s.commit_max === 'number') ? s.commit_max : 0;
  const quiet = (typeof s.commit_quiet === 'number') ? s.commit_quiet : 0;
  const total = (typeof s.commit_total === 'number') ? s.commit_total : 0;
  if (!total && !peak)
    return `<div class="bdcommit-copy">no ledger commits in these periods</div>`;
  const aria = `ledger commits per period: median ${med}, peak ${peak}` +
    (quiet ? `, ${quiet} period${quiet === 1 ? '' : 's'} with none` : '') +
    ` (${total} total)`;
  return `<div class="bdcommit-copy" role="img" aria-label="${esc(aria)}">` +
    `<span class="bdnum">${med}</span> median commits/period · peak ${peak}` +
    (quiet ? ` · ${quiet} empty` : '') + `</div>`;
}
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
  ensureBurnLimit();
  const all = s.buckets || [];
  const totalN = all.length;
  /* #499: slice to the most recent `lim` columns when the series exceeds
     the active limit. lim=0 means all/max (no slice). Presence of the
     control is totalN > BURN_LIMIT_DEFAULT (28) — his rule: "when we have
     more than 28 elements" — NOT vs the active limit. That way limit=0
     (all) still shows the control so he can dial back; a rule that hid it
     against the active limit left no in-UI recovery. */
  const lim = activeBurnLimit();          // 0 = all
  const showLim = totalN > BURN_LIMIT_DEFAULT;
  const bs = (lim > 0 && totalN > lim) ? all.slice(-lim) : all;
  const flowMax = Math.max(1, ...bs.map(b => Math.max(b.arrived, b.landed)));
  const levelMax = Math.max(1, ...bs.map(b => b.open));
  const peakCommits = (typeof s.commit_max === 'number') ? s.commit_max
    : Math.max(0, ...bs.map(b => b.commits || 0));
  /* #417: columns carry the exact numbers the hover/focus readout names
     (open + flow + commits). Level-track columns are keyboard-focusable so
     the mapping is learnable without a pointer. #487: no native title= —
     .bdtip/.bdinsp are the one hover surface; a browser tooltip stacked
     on them is the second surface the brief forbade. */
  const col = (b, focusable) => {
    const stamp = bstamp(b.t0, s.step);
    const c = b.commits || 0;
    const title = `${stamp} · ${b.open} open · ${b.arrived} arrived · ` +
      `${b.landed} landed · ${c} commit${c === 1 ? '' : 's'}`;
    /* #298: the inspector needs what the glance tip does not — the exact
       interval (t0→t1) and the coverage state. A period with no ledger
       commit CARRIES the previous level rather than measuring it (the
       chart's own rule), so the inspector must be able to say so. */
    const focus = focusable
      ? ` tabindex="0" role="listitem"` +
        ` data-open="${b.open}" data-arrived="${b.arrived}"` +
        ` data-landed="${b.landed}" data-commits="${c}"` +
        ` data-stamp="${esc(stamp)}"` +
        ` data-t0="${b.t0}" data-t1="${b.t0 + s.step}"` +
        ` data-covered="${c > 0 ? 1 : 0}"`
      : '';
    return `<div class="bdcol"${focus}` +
      ` aria-label="${esc(title)}">`;
  };
  // The head states the three totals it is a picture of, so a chart too
  // small to read is still a fact. `open` is the CURRENT count and it comes
  // from the same walk the columns do, not from a second reading.
  // #487: the step name is a cycle control (click / Enter / Space), not
  // bare prose — next ladder step, wrapping, announced via aria-live.
  // #499: when totalN exceeds the DEFAULT (28), the same line carries
  // `limit [ N] [⟳]` — no second row (#417). Presence is vs 28, not the
  // active limit, so all-mode (0) still shows the control.
  const stepName = BURN_STEP_NAME[s.step] || 'bucketed';
  const stepAria = `granularity ${stepName} — activate to cycle`;
  const limVal = displayBurnLimitValue();
  const limCtl = showLim
    ? `<span class="bdlimit" data-total="${totalN}" data-limit="${limVal}">` +
      `limit <input type="number" class="bdlimit-in" inputmode="numeric" ` +
      `min="0" max="${BURN_LIMIT_CAP}" step="1" value="${limVal}" ` +
      `aria-label="column limit, 0 for all, max ${BURN_LIMIT_CAP}">` +
      `<button type="button" class="bdlimit-reset" ` +
      `aria-label="reset column limit to ${BURN_LIMIT_DEFAULT}">⟳</button>` +
      `</span>`
    : '';
  let h = label('burndown') + `<div class="bd">` +
    `<div class="bdtip" hidden role="status" aria-live="polite"></div>` +
    /* #298/#487: the inspector is the richer reading; pin is RHS-or-above
       (bdinspLay), not column-centred. role=status like the tip. */
    `<div class="bdinsp" hidden role="status"></div>` +
    `<div class="bdhead"><span class="bdhead-nums">` +
    `<span class="bdnum">${s.open}</span> open · ` +
    `${s.arrived} arrived · ${s.landed} landed · ` +
    `<button type="button" class="bdstep" role="button"` +
    ` data-step="${s.step}"` +
    ` aria-label="${esc(stepAria)}">${esc(stepName)}</button>` +
    `</span>${limCtl}</div>` +
    `<div class="bdtrack bdnet" role="list" ` +
      `aria-label="open count per period; line weight is ledger commits">` +
      bs.map(b => col(b, true) +
        bdbar(b, 'open', 'bdlevel', levelMax, peakCommits) + `</div>`)
        .join('') + `</div>` +
    `<div class="bdtrack bdflow">` +
      bs.map(b => col(b, false) +
        `<div class="bdhalf bdtop">${bdbar(b, 'arrived', 'bdup', flowMax)}</div>` +
        `<div class="bdrule"></div>` +
        `<div class="bdhalf bdbot">${bdbar(b, 'landed', 'bddown', flowMax)}</div>` +
        `</div>`).join('') + `</div>` +
    `<div class="bdaxis"><span>${esc(bstamp(bs.length ? bs[0].t0 : s.from, s.step))}</span>` +
      `<span>arrivals above · landed below · weight is commits</span>` +
      `<span>${esc(bstamp(s.to, s.step))}</span></div>`;
  /* WHO FILED EACH TASK, said honestly (#217). The old panel reported its
     own coverage (`sourced N/M`) because the ledger could not answer the
     question; #216 made the answer readable from first sightings, so the
     panel now draws the split WITH its unknown remainder visible. The
     block is constant-height for the same reason the head is one
     ellipsised line: numbers that change must never move the panels below
     while the bars are travelling. */
  h += provBlock(s.provenance);
  /* HOW LONG FINISHED WORK TOOK, said honestly (#218). One duration —
     the median of filed-to-landed — and the population it was computed
     over, never a velocity score or a rate. It is COPY in the panel's
     surrounding text, not a mark on the chart: #417's caution is that the
     burndown's quality is not to be traded for an extra series, and a
     median belongs in the chart's honest voice (denominators named,
     unknowns drawn) rather than competing with it. The population is the
     INTERSECTION of arrived and landed — the work that finished — so the
     label says so plainly, because a reader otherwise assumes "how long
     work takes" and the still-open long tail is excluded. NO MOTION: this
     panel re-renders through innerHTML on every tick and nothing about it
     is a gesture the page initiates (transitions.md), so this line declares
     no transition and reduced-motion parity is the identical settled
     visual — the same contract provenance holds one block up. */
  h += medianBlock(s);
  /* #417 c4 — commits-per-period figure. After the median, same voice:
     one fixed line in the panel's surrounding copy. The +19px is a
     deliberate one-time allowance baked into the panel's constant
     height, not a growth that moves the page on a data change. */
  h += commitFigBlock(s);
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
                  d.dreams_archive.map(dreamBlock).join(''), 'dim',
                  'dreams-archive') : '');
  h += qSection(d);
  h += `<div class="dim"><a href="/answers">questions for the dreamer · ${d.answers_open.length} open</a></div>`;
  if (d.reviews.length) {
    /* #463 — primary age is *created* (birth), not mtime. When birth is
       unavailable the row says so by name rather than lying with mtime.
       Secondary "modified X ago" only when created is known and differs;
       the chrome's ` · ` is the same separator #456 used for date/age. */
    h += label('reviews') + d.reviews.map(r => artifactRow(r, 'review'))
        .join('');
  }
  h += label('files') +
       ['DREAMWORK.md','questions.md','lessons.md'].map(n =>
         expand(n, mdB(d.files[n]), '', `file:${n}`)).join('');
  // ...then how the work itself is going (#142). Below the questions and the
  // reviews on purpose: the top of this page is what NEEDS him — a fault,
  // what just happened, what he must answer — and the burndown is context
  // rather than an errand. Above `status` because both are about the loop
  // and this one is the longer view of it.
  h += burnPanel(d);
  h += statusBlock(d.status, d.pending_handoffs);
  h += runModePicker(d);   // loop control, after status, before preference
  h += posturePicker(d);   // #445 three-axis override of run-mode's posture
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
  const v = res && res._dwv;
  if (res && DraftStore.isDurable(res)) {
    liveBox.value = '';
    // durable success only — the #459 ask draft must not reappear as sent
    DraftStore.clear(DraftStore.id('ask', 'main'));
    if (liveMsg) liveMsg.textContent = 'asked';
    await tick();
  } else if (liveMsg) {
    // a rejected 202 (res.ok true, body rejected — E5) used to take this branch
    // as a success and clear the box; the verdict `landed` routes it here, and
    // the reason is named in his voice where the surface already has a message.
    const why = (v && v.rejected && v.reason && REJECT_WHY[v.reason])
              || (v && QSEND_WHY[v.status]);
    liveMsg.textContent = !res
      ? 'dreamwork is unreachable — your words are kept'
      : (v && v.rejected)
        ? (why ? `not written — ${why}. your words are kept`
               : 'question was refused — your words are kept')
        : 'question was refused — your words are kept';
  }
}
/* #158: reflow by file kind, never by content sniff. A .py with a `#`
   comment must stay pre; a research .md must reflow. Path from the query
   is the only signal — same extensions a human means by ".md or similar". */
function isMarkdownFile(p) {
  const s = String(p || '').toLowerCase();
  return s.endsWith('.md') || s.endsWith('.markdown') || s.endsWith('.mdx');
}
/* #284 — the split the heading lockup rests on. Both halves come out of the
   route's own `p` VERBATIM: nothing is normalised, no separator is inserted
   and no segment is collapsed, because the copy button promises the exact
   path back and the metadata line must agree with it character for character.
   `fileDir` keeps its trailing slash for the same reason — that slash is a
   segment boundary the path really has.

   A root-level file has NO parent, and gets no metadata line rather than an
   invented `./`. A heading that claims a directory it does not have is the
   same lie as an ellipsis, one segment smaller. */
const fileBase = p => {
  const s = String(p || ''), i = s.lastIndexOf('/');
  return i < 0 ? s : (s.slice(i + 1) || s);
};
const fileDir = p => {
  const s = String(p || ''), i = s.lastIndexOf('/');
  return i < 0 || !s.slice(i + 1) ? '' : s.slice(0, i + 1);
};
/* #336: human-readable byte count for the binary-file panel. Two units, two
   digits each — same shape as the commit age, so a 153065-byte PNG reads as
   `149.5 KB` rather than a long unbroken number. */
function humanSize(n) {
  const units = [['B', 1], ['KB', 1024], ['MB', 1024 * 1024],
                 ['GB', 1024 * 1024 * 1024]];
  for (let i = units.length - 1; i >= 0; i--) {
    if (n >= units[i][1]) {
      const v = n / units[i][1];
      const digits = i === 0 ? 0 : (v >= 100 ? 0 : 1);
      return v.toFixed(digits) + ' ' + units[i][0];
    }
  }
  return '0 B';
}
/* buildFile renders the body of /file for three kinds of file (#336), and a
   markdown file in one of two MODES (#252 — `mode` comes from the route, so
   Rendered vs Source is deep-linkable):
   - text: <pre> (or reflowed .md, per #158) — with the server's #351
     highlighted markup when the extension names a supported language.
   - image: an <img> served from /filebytes, framed like everything else
     in the column.
   - binary (non-image): a panel that SAYS what the file is — type, size
     — with a download affordance, instead of dumping its bytes into a
     <pre> as plausible-looking mojibake. The bytes are reachable (the
     download link) but never by accident, on the page's "detail is
     ranked, never withheld" rule. */
function buildFile(param, fetched, mode) {
  if (!fetched)
    return '<div id="filebody"><div class="dim">not found</div></div>';
    if (fetched.binary) {
      const dl = '/filebytes?p=' + encodeURIComponent(param || '');
      const mime = fetched.mime || 'application/octet-stream';
      const size = fetched.size || 0;
      if (fetched.kind === 'image') {
        /* MOTION: the image rides the route dissolve like every other part
           of #view (it is inside #view). Its bytes arrive asynchronously,
           though, so the <img> also carries its own arrival — a self-
           contained opacity fade on load, applied as a start pose that
           imgArrived() removes. Reduced motion suppresses the pose in CSS,
           so the image is fully visible from the first frame and the load
           handler is a no-op: same information and timing with the movement
           removed, never a feature that silently degrades. The mime and
           size travel as data-* so imgFailed can fall back to the binary
           panel without refetching. */
        return '<div id="filebody" class="fileimg-wrap">' +
               `<img class="fileimg pose" alt="" src="${dl}" ` +
               `data-mime="${esc(mime)}" data-size="${size}" ` +
               `onload="imgArrived(this)" onerror="imgFailed(this)"></div>`;
      }
      /* NON-IMAGE BINARY. The copy is read by a person who expected to see
         something — write it as information, not as an error. The file IS
         here, it is named, and its bytes are one click away; what it is not
         is text the page can show, so the page says that plainly. */
      return '<div id="filebody"><div class="filebin">' +
             label('binary file') +
             '<div class="filebin-row"><span class="filebin-k">type</span>' +
             `<span class="filebin-v">${esc(mime)}</span></div>` +
             '<div class="filebin-row"><span class="filebin-k">size</span>' +
             `<span class="filebin-v">${humanSize(size)}</span></div>` +
             `<a class="filebin-dl" href="${dl}" download>download the bytes</a>` +
             '</div></div>';
    }
  const text = fetched.text;
  /* #252 — SOURCE IS THE VERBATIM PATH THAT ALREADY EXISTED. It is the same
     `<pre>${esc(text)}</pre>` every non-markdown file at /file has always
     rendered, reached by a second route rather than by a second renderer, and
     that is precisely what makes the bytes trustworthy: there is nothing
     between the server's string and one escaped text node — no transform to
     audit, no tokeniser to drift out of step with the file.

     DO NOT HIGHLIGHT THIS PANE. #351 asks for syntax highlighting on /file,
     and a markdown file's Source mode is the one pane it must not touch: he
     asked for this mode so that what he copies out of it is the file. His
     words: that is the whole point of the mode and not a detail to optimise
     away. The condition is EXPLICIT (never "no hl happened to arrive") so
     the guarantee does not depend on what the server chose to send. */
  const renderPlain = isMarkdownFile(param) && mode === 'source';
  /* #351 — every OTHER text file takes the server's highlighted markup when
     it arrived (a known source extension; see file_highlight_html). The
     markup is review_artifact's #339 output — tok- spans, escaped, its
     round-trip proved byte-exact — so textContent is still the file. When
     no `hl` arrived (an extension the map does not name) the render is the
     same verbatim <pre> it always was: plain, never guessed. */
  const src = (!renderPlain && fetched.hl) ? fetched.hl
                                         : `<pre>${esc(text)}</pre>`;
  const body = (isMarkdownFile(param) && mode !== 'source') ? mdB(text) : src;
  return `<div id="filebody">${body}</div>`;
}
/* the image's own arrival (#336): if its bytes land after the view settled,
   it is still in its .pose start state — remove it once, on the load event,
   to ease in on .fileimg's standing opacity transition. If the bytes
   arrived during the route dissolve, the dissolve already carried the image
   and the load event finds no .pose to remove. Idempotent. */
function imgArrived(img) {
  if (!img || img.dataset.arrived) return;
  img.dataset.arrived = '1';
  if (img.classList.contains('pose')) {
    void img.offsetWidth;
    img.classList.remove('pose');
  }
}
/* a load failure (truncated upload, exotic codec the browser cannot decode)
   is the wrong state to leave as a broken-image icon. Replace the dead <img>
   with the same binary-info panel a non-image binary gets — the bytes stay
   reachable via the download link. The mime/size come from the data-*
   attributes captured at build time, so the failure path need not refetch. */
function imgFailed(img) {
  if (!img || img.dataset.failed) return;
  img.dataset.failed = '1';
  const body = img.closest('#filebody');
  if (!body) return;
  const mime = img.dataset.mime || 'application/octet-stream';
  const size = parseInt(img.dataset.size || '0', 10) || 0;
  const dl = img.getAttribute('src') || '';
  body.className = '';
  body.innerHTML = '<div class="filebin">' +
    '<div class="label">image would not render</div>' +
    '<div class="filebin-row"><span class="filebin-k">type</span>' +
    `<span class="filebin-v">${esc(mime)}</span></div>` +
    '<div class="filebin-row"><span class="filebin-k">size</span>' +
    `<span class="filebin-v">${humanSize(size)}</span></div>` +
    `<a class="filebin-dl" href="${esc(dl)}" download>download the bytes</a>` +
    '</div>';
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
  // The width he dragged is emitted INTO the markup rather than applied after
  // paint: a route change already animates this column's outer width, and a
  // second correction one frame later would be a visible re-lay-out of every
  // paragraph in both columns.
  const pct = readSplit();
  return `<div id="reviewwrap"${dock ? '' : ' class="nodock"'}` +
      (dock ? ` style="--rsplit:${pct.toFixed(1)}%"` : '') + `>` +
      `<div id="reviewdoc"><iframe id="reviewframe" src="${src}" ` +
      `title="review artifact" loading="lazy"></iframe></div>` +
      (dock ? reviewSplitBar(pct) : '') +
      dock +
    `</div>`;
}
/* ONE artifact row shape for both listing surfaces (#484): the dashboard's
   reviews panel and the /research route. kind is 'review' | 'research';
   the view is /<kind>?p=<name> and the raw endpoint /<kind>raw?p=<name> by
   the one convention, so a second surface is a parameter, not a second
   idiom. The #463 age pair (created primary, modified secondary only when
   the rendered figures differ) comes with the row. */
function artifactRow(r, kind) {
  let age = '';
  if (r.created_known && r.created != null) {
    age = `<span class="age" data-mt="${r.created}"></span>`;
    if (r.show_modified)
      age += `<span class="rsep"> · </span>` +
             `<span class="age rmod" data-mt="${r.mtime}" data-cr="${r.created}"` +
             ` data-review-mod="${esc(r.name)}"></span>`;
  } else {
    age = `<span class="age ageunk">created unknown</span>` +
          `<span class="rsep"> · </span>` +
          `<span class="age rmod" data-mt="${r.mtime}" data-review-mod="${esc(r.name)}"></span>`;
  }
  /* #289 — review decision from the ledger store (store-mode only). A row
     WITH a decision carries question_title (NOT NULL by contract), so the
     marker links to /question?qid=<title> — opening the question that the
     artifact was raised against. accepted (✔) and rejected (✘) are DONE:
     the marker dims like a folded entry. pending is in flight, so its
     marker stays lit. 'unlinked' (no record) renders NO marker — absence of
     a record is its own state, distinct from 'pending' by contract. */
  const dec = r.decision;
  const hasDec = dec === 'accepted' || dec === 'rejected' || dec === 'pending';
  let status = '';
  if (hasDec) {
    const glyph = dec === 'accepted' ? '✔'
                : dec === 'rejected' ? '✘' : 'pending';
    const inner = `<span class="rdecision r${dec}">${glyph}</span>`;
    status = r.question_title
      ? `<a class="rqlink" href="/question?qid=${encodeURIComponent(r.question_title)}">${inner}</a>`
      : inner;
  }
  return `<div data-${kind}="${esc(r.name)}" data-decision="${dec || 'unlinked'}">` +
    `<a href="/${kind}?p=${encodeURIComponent(r.name)}">${esc(r.name)}</a>` +
    pipBtn('/' + kind + 'raw?p=' + encodeURIComponent(r.name), r.name) +
    age + status + `</div>`;
}
/* #484 — research artifacts: the review VIEW idiom (the raw self-contained
   artifact in an iframe for style isolation; the same #reviewwrap/#reviewframe
   nodes, which is what lets the tick's snapshotReviewFrame/restoreReviewFrame
   preservation reach it unchanged) over a listing with NO questions.md
   pairing and NO archive-on-answered lifecycle — research outlives the
   decisions it informed (.dreamwork/docs/research/README.md). No dock, no
   split: there is no question to sit beside. */
function buildResearch(name, d) {
  if (name)
    return `<div id="reviewwrap" class="nodock">` +
      `<div id="reviewdoc"><iframe id="reviewframe" src="` +
      '/researchraw?p=' + encodeURIComponent(name) +
      `" title="research artifact" loading="lazy"></iframe></div></div>`;
  if (!d) return '<div class="dim">loading…</div>';
  if (!d.research.length)
    return label('research') +
      `<div class="dim">no built research artifacts yet — sources live in ` +
      `<code>.dreamwork/docs/research/src/</code> and build through ` +
      `<code>review_artifact.py</code>, the one template pipeline.</div>`;
  return label('research') +
    d.research.map(r => artifactRow(r, 'research')).join('');
}
/* #452 — ONE question on its own page: a surface the loop's churn cannot
   shift under him mid-answer. The key (`qid` in the URL) is the question's
   TITLE identity — the same string `data-qid` already carries to survive
   regrouping — chosen for what survives it: body rewrites, priority
   re-sorts and the open→answered fold all keep the title, and those three
   ARE the churn this page exists for (the loop rewrote #449's entry three
   times in fifteen minutes while he was reading it). A RETITLE breaks the
   key, and that case fails LOUD, in the .qmissing notice below — never a
   blank page and never a different question ("I could not tell" and
   "nothing" must not render the same). #294's planned question_id can
   later be accepted beside the title without invalidating a single link. */
function buildQuestion(title, d) {
  if (!d) return '<div class="dim">loading…</div>';
  if (title) {
    const oi = (d.questions_open || []).findIndex(x => x.title === title);
    if (oi >= 0)
      return `<div id="qfocus">` +
        qaCard(d.questions_open[oi], 'o' + oi) + `</div>`;
    /* the fold, followed: answering re-indexes the entry into
       answered_entries while he watches, and the page moves WITH it — a
       live question reported as gone is the failure this route exists to
       prevent. Same title, same card, new 'a<n>' address. */
    const ai = d.answered_entries.findIndex(x => x.title === title);
    if (ai >= 0)
      return `<div id="qfocus">` +
        qaCard(d.answered_entries[ai], 'a' + ai) + `</div>`;
  }
  /* Unresolved. The notice says WHAT (the key names nothing live), WHY
     (most likely a retitle), and the way back — and it guesses at nothing:
     a near title is a different question. Not --warn: the channel is fine,
     the question is simply gone, and a fault colour would cry broken over
     an edit. */
  return `<div id="qfocus"><div class="qmissing">` +
    `<div class="qmisshead">not found</div>` +
    `<div class="qmissbody">this link names a question the list no longer ` +
    `has — it was most likely re-titled or removed while you watched. ` +
    `No other question has been substituted for it.</div>` +
    `<div class="qmissback"><a href="/questions">&larr; back to questions</a></div>` +
    `</div></div>`;
}
/* ── the review split (#305) ──────────────────────────────────────────────
   An INVISIBLE affordance still has to be operable by everything that
   operates a control, so the bar is a real `separator` with a value: a
   pointer drags it, arrow keys step it, Home/End reach the floors, and
   Enter or a double-click puts it back. A drag-only splitter is a splitter
   the keyboard cannot see.

   Where the width lives: `localStorage`, read by `buildReview` at build
   time so a fresh /review PAINTS at his width instead of sliding to it.
   It is a preference rather than shared state, and nothing else has to
   carry it across a re-render — the tick replaces only `#qdock`
   (`setLiveContent`), never `#reviewwrap`. */
const RSPLIT_KEY = 'dw.review.split';
/* 70/30 by default because that is where BOTH columns read: the artifacts
   are authored around a ~1000px document and 30% of the widened column is
   ~46ch of question, against the 34ch dock that made this task. The floors
   are the range in which that stays true — at 82% the question is a margin
   note for someone who is only reading, at 30% the artifact is a thumbnail. */
const RSPLIT_MIN = 30, RSPLIT_MAX = 82, RSPLIT_DEF = 70;
const clampSplit = v => Math.min(RSPLIT_MAX,
  Math.max(RSPLIT_MIN, Number.isFinite(v) ? v : RSPLIT_DEF));
function readSplit() {
  let v = NaN;
  try { v = parseFloat(localStorage.getItem(RSPLIT_KEY)); } catch (e) {}
  return clampSplit(v);
}
const reviewSplitBar = pct =>
  `<div id="rsplit" class="rsplit" role="separator" tabindex="0"` +
  ` aria-orientation="vertical" aria-label="review and question widths"` +
  ` aria-valuemin="${RSPLIT_MIN}" aria-valuemax="${RSPLIT_MAX}"` +
  ` aria-valuenow="${Math.round(pct)}"` +
  ` aria-valuetext="${Math.round(pct)}% review, ${100 - Math.round(pct)}% question"` +
  ` title="drag to set the widths · arrow keys step, enter resets"` +
  ` onpointerdown="beginSplit(event)" onkeydown="splitKey(event)"` +
  ` ondblclick="applySplit(${RSPLIT_DEF}, true)"></div>`;
/* the live value is the one in the DOM, not the one on disk: a drag writes
   both, and reading back the element cannot disagree with what is rendered. */
function curSplit() {
  const wrap = document.getElementById('reviewwrap');
  const v = wrap ? parseFloat(wrap.style.getPropertyValue('--rsplit')) : NaN;
  return Number.isFinite(v) ? v : readSplit();
}
function applySplit(pct, keyed) {
  const wrap = document.getElementById('reviewwrap');
  if (!wrap) return;
  const v = clampSplit(pct);
  wrap.classList.toggle('rkeyed', !!keyed);
  wrap.style.setProperty('--rsplit', v.toFixed(1) + '%');
  const bar = document.getElementById('rsplit');
  if (bar) {
    bar.setAttribute('aria-valuenow', String(Math.round(v)));
    bar.setAttribute('aria-valuetext',
      `${Math.round(v)}% review, ${100 - Math.round(v)}% question`);
  }
  try { localStorage.setItem(RSPLIT_KEY, v.toFixed(1)); } catch (e) {}
}
function beginSplit(e) {
  const wrap = document.getElementById('reviewwrap');
  const bar = document.getElementById('rsplit');
  if (!wrap || !bar || e.button !== 0) return;
  e.preventDefault();                     // no text selection while dragging
  /* The mapping is a RATIO measured entirely in painted space — the pointer's
     travel over the pane's painted width — so it needs no correction for the
     enter transform that may still be playing above it (transitions.md's
     mid-transform rule bites when the two spaces are MIXED). The rect is
     re-read per move because that width is itself animating while the column
     glides. */
  const x0 = e.clientX, pct0 = curSplit();
  wrap.classList.remove('rkeyed');
  bar.classList.add('rdrag');
  try { bar.setPointerCapture(e.pointerId); } catch (err) {}
  const move = ev => {
    const r = wrap.getBoundingClientRect();
    applySplit(pct0 + (ev.clientX - x0) / (r.width || 1) * 100, false);
  };
  const end = () => {
    bar.classList.remove('rdrag');
    bar.removeEventListener('pointermove', move);
    bar.removeEventListener('pointerup', end);
    bar.removeEventListener('pointercancel', end);
  };
  bar.addEventListener('pointermove', move);
  bar.addEventListener('pointerup', end);
  bar.addEventListener('pointercancel', end);
}
function splitKey(e) {
  const step = e.shiftKey ? 8 : 2;
  let next = null;
  if (e.key === 'ArrowLeft') next = curSplit() - step;
  else if (e.key === 'ArrowRight') next = curSplit() + step;
  else if (e.key === 'Home') next = RSPLIT_MIN;
  else if (e.key === 'End') next = RSPLIT_MAX;
  else if (e.key === 'Enter' || e.key === ' ') next = RSPLIT_DEF;
  else return;
  e.preventDefault();
  applySplit(next, true);
}
/* THE PANE IS AS TALL AS THE WINDOW ALLOWS (#305, his last sentence).
   Its top is wherever the chrome ended, which depends on how the heading and
   crumbs wrapped, so it is measured rather than assumed — and measured with
   `offsetTop`, which is LAYOUT. `getBoundingClientRect` would be read through
   whatever transform the dissolve is part-way through (transitions.md), and
   this runs inside `setContent`, i.e. one frame before `.enter` is committed.
   Nothing here animates: a window resize is not a gesture. */
function fitReview() {
  const wrap = document.getElementById('reviewwrap');
  if (!wrap) return;
  let top = 0;
  for (let n = wrap; n; n = n.offsetParent) top += n.offsetTop;
  // the body's own bottom padding, so the pane ends where the page ends
  const pad = parseFloat(getComputedStyle(document.body).paddingBottom) || 0;
  const h = Math.round(window.innerHeight - top - pad);
  wrap.style.setProperty('--rvh', Math.max(0, h) + 'px');
  syncDockFade();                    // a resize changes what is still below
}
addEventListener('resize', fitReview);
/* WHICH BOX SCROLLS, asked once (#326). The docked question's scrollport is
   the body wrapper, not the card — the card holds the answer box too, and a
   scrollport that holds the box cannot fade its text at the box. Off /review
   the wrapper generates no box, so this returns an element whose scrollTop is
   always 0, which is what those callers already assumed of the card. Declared
   as a function so the three callers spread across three script blocks do not
   depend on which block loads first. */
function qaScroller(card) {
  return card ? card.querySelector('.qbody') : null;
}
/* IS ANYTHING STILL PASSING UNDER THE ANSWER BOX? That is the only question
   the fade band asks, and the answer is a scroll distance, so it is read
   rather than remembered. A card that does not overflow at all answers "no"
   by the same arithmetic — there is nothing below, so there is nothing to
   fade — which is the zero case his exception describes.

   Called from the three places the answer can change and nowhere else: the
   scroll itself, a resize, and a re-render — the last of those from the tick
   AFTER the scroll it reads has been put back, not from inside the swap. The
   listener is delegated on the CAPTURE phase because `scroll` does not
   bubble and the card it is watching is replaced every two seconds. */
function syncDockFade() {
  const dock = document.getElementById('qdock');
  if (!dock) return;
  const card = dock.querySelector(':scope > .qa');
  const body = card && qaScroller(card);
  if (!body) return;
  const below = body.scrollHeight - body.clientHeight - body.scrollTop;
  dock.classList.toggle('atend', below <= 2);
  /* and the mirror of it at the head: nothing is above at the top, so the
     title is crisp there and the edge only softens once he has scrolled */
  dock.classList.toggle('attop', body.scrollTop <= 2);
}
addEventListener('scroll', e => {
  const t = e.target;
  if (t && t.nodeType === 1 && t.classList.contains('qbody')) syncDockFade();
}, true);
/* every number on this page that can drift without a disk change is written
   HERE, once a second, as TEXT into nodes that already exist — never through
   a re-render. That was already the shape; #132 is what makes it load-bearing
   rather than convenient. A commit age at seconds resolution has to change
   every second, and routing that through the tick's `innerHTML` swap would
   re-run the regroup (#113) and re-carry his half-typed text (#118) sixty
   times a minute, forever, to move one digit. `setContent` re-runs this after
   every swap, so a fresh render is filled in before it paints. */
function ages() {
  /* data-mt: a FILE (or review *created*) is `5m old`. #463 adds `.rmod` for
     the secondary "modified X ago" on a review whose created ≠ mtime — same
     attribute, different grammar, so a single forEach branches on class. */
  document.querySelectorAll('.age[data-mt]').forEach(el => {
    const s = ageStr(parseFloat(el.dataset.mt));
    if (!el.classList.contains('rmod')) { el.textContent = s + ' old'; return; }
    /* #463 — the secondary earns its place only if it SAYS something the
       primary does not. `data-cr` is the created figure the row already shows;
       when both render to the same string the modification is invisible at
       this resolution, so the pair is dropped rather than printing
       `3d old · modified 3d ago`. Server-side exact inequality flagged 24 of
       28 real artifacts (create, then write content — sub-millisecond), which
       is why the verdict is here, beside the formatter, and not a threshold
       someone has to tune. Runs inside ages(), which setContent calls BEFORE
       paint, so the pair is absent from the first frame rather than vanishing
       out of a painted one (transitions.md — nothing disappears). */
    const cr = el.dataset.cr;
    if (cr !== undefined && ageStr(parseFloat(cr)) === s) {
      const sep = el.previousElementSibling;
      if (sep && sep.classList.contains('rsep')) sep.hidden = true;
      el.hidden = true;
      el.textContent = '';
      return;
    }
    el.hidden = false;
    el.textContent = 'modified ' + s + ' ago';
  });
  /* #392a: a `.age[data-ct]` node is TWO figures (timed — a commit's real
     timestamp) UNLESS it carries `data-day="1"`, which marks it DAY-precision
     (a question title's date-only midnight). One figure when we know only the
     day; two when we know the time. The number of figures IS the precision. */
  document.querySelectorAll('.age[data-ct]').forEach(el => {
    if (el.dataset.day === '1') {
      paintDayAge(el, parseFloat(el.dataset.ct));
    } else {
      paintAgePair(el, parseFloat(el.dataset.ct), ' ago');
    }
  });
  /* a third flavour, and the difference is grammar rather than format (#165):
     a FILE is `5m old`, a thing he DID is `5m ago`. Commit resolution
     (`data-ct`) is two padded units and far too wide for a 38ch panel, so the
     history takes the short one. */
  document.querySelectorAll('.age[data-at]').forEach(el =>
    el.textContent = ageStr(parseFloat(el.dataset.at)) + ' ago');
  /* #473 — "updated X ago" on a question whose content changed after first
     sight. Same honesty rule as #463's review secondary: only show when the
     rendered figure says something the created age does not. Pure text —
     ages() never transitions digit flips. */
  document.querySelectorAll('.age.qup[data-ut]').forEach(el => {
    const u = parseFloat(el.dataset.ut);
    if (!(u > 0)) { el.hidden = true; el.textContent = ''; return; }
    const s = ageStr(u);
    // pair with the created age on the same .qt, if present
    const qt = el.closest('.qt');
    const crEl = qt && qt.querySelector('.age.qage[data-ct]');
    if (crEl) {
      const cr = parseFloat(crEl.dataset.ct);
      if (cr > 0 && ageStr(cr) === s) {
        const sep = el.previousElementSibling;
        if (sep && sep.classList.contains('rsep')) sep.hidden = true;
        el.hidden = true;
        el.textContent = '';
        return;
      }
    }
    el.hidden = false;
    el.textContent = 'updated ' + s + ' ago';
  });
  const upd = document.getElementById('upd');
  if (upd && fetchedAt) upd.textContent =
    `updated ${ageStr(fetchedAt/1000)} ago`;
  applyTitle();     // the liveness word drifts with the clock, not with disk
  applyFavicon();   // ...and the orbit advances one frame per second on it
  applyTint();      // ...and his colour arrives from whichever window set it
}
/* #473 — an "updated X ago" that first appears is an ARRIVAL (transitions.md:
   no size floor). Mirror revealReviewMods: track known keys, one-shot
   .dreamin, first paint + reduced motion settle fully lit. Digit flips stay
   pure text via ages(). */
let knownQuestionUps = null;
function revealQuestionUpdates() {
  const nodes = [...document.querySelectorAll(
    '.age.qup[data-ut]:not([hidden])')];
  const now = new Set(nodes.map(el => el.dataset.qUpd || el.dataset.ut));
  if (knownQuestionUps === null || window.__dwSkipQuestionUpArrival) {
    nodes.forEach(el => el.classList.remove('dreamin'));
    knownQuestionUps = now;
    return;
  }
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  for (const el of nodes) {
    const k = el.dataset.qUpd || el.dataset.ut;
    if (knownQuestionUps.has(k)) continue;
    if (reduce) continue;
    el.classList.add('dreamin');
    void el.offsetWidth;
    requestAnimationFrame(() => {
      if (el.isConnected) el.classList.remove('dreamin');
    });
  }
  knownQuestionUps = now;
}
/* #463 — a "modified X ago" that appears when a review's mtime pulls away
   from its birth is an ARRIVAL (transitions.md: no size floor). Track which
   review-mod keys we have already settled; a newly-present `.rmod` gets the
   one-shot `.dreamin` enter-snap, then eases in. First paint and reduced
   motion settle fully lit (function, no pose) — the same contract as
   revealNewOpenAsks / revealStaleAction. Pure ages() digit flips stay
   exempt; this only fires when the secondary *node* appears. */
let knownReviewMods = null;
function revealReviewMods() {
  // Only the dashboard reviews list carries these; leave any other route
  // with a clean slate so the next dashboard paint settles, not re-arrives.
  if (view.name !== 'dashboard') { knownReviewMods = null; return; }
  /* `:not([hidden])` because ages() drops a secondary whose figure reads the
     same as the primary (#463). A hidden node is not on the page, so treating
     it as an arrival would animate nothing and, worse, would record it as
     known — so the row's REAL first modification would then be a no-op. */
  const nodes = [...document.querySelectorAll(
    '.age.rmod[data-review-mod]:not([hidden])')];
  const now = new Set(nodes.map(el => el.dataset.reviewMod));
  if (knownReviewMods === null || window.__dwSkipReviewModArrival) {
    nodes.forEach(el => el.classList.remove('dreamin'));
    knownReviewMods = now;
    return;
  }
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  for (const el of nodes) {
    if (knownReviewMods.has(el.dataset.reviewMod)) continue;
    if (reduce) continue;
    el.classList.add('dreamin');
    void el.offsetWidth;
    requestAnimationFrame(() => {
      if (el.isConnected) el.classList.remove('dreamin');
    });
  }
  knownReviewMods = now;
}
/* #289 — a review's DECISION token appearing/changing on its row is a state
   change (transitions.md: no size floor), and it reuses the SAME one-shot
   `.dreamin` arrival idiom as revealReviewMods (#463) / revealQuestionUpdates
   (#473): the row survives the tick (keyed by filename, travels via the list
   FLIP only when it MOVES), but the decision marker inside it is new
   innerHTML. Track each row's `data-decision`; on a genuine change the marker
   gets the enter-snap start pose, then eases in on the standing transition.
   First paint settles visible (no pose), reduced motion skips the pose
   (function only), and a decision going TO 'unlinked' is a departure of inner
   content (no survivor to animate) so it gets no arrival — the marker simply
   is absent from the new innerHTML, the same as the status panel's
   data-driven facts. */
let knownReviewDecisions = null;
function revealReviewDecisions() {
  // Only the dashboard reviews list carries decisions; reset on any other
  // route so the next dashboard paint settles rather than re-arriving.
  if (view.name !== 'dashboard') { knownReviewDecisions = null; return; }
  const rows = [...document.querySelectorAll('[data-review]')];
  const now = {};
  for (const r of rows) now[r.dataset.review] = r.dataset.decision || 'unlinked';
  if (knownReviewDecisions === null) {
    knownReviewDecisions = now;   // first paint: settle visible
    return;
  }
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  for (const r of rows) {
    const name = r.dataset.review, dec = now[name];
    if (knownReviewDecisions[name] === dec) continue;   // unchanged
    if (dec === 'unlinked') continue;   // marker left, not arrived
    const marker = r.querySelector('.rdecision');
    if (!marker || reduce) continue;
    marker.classList.add('dreamin');
    void marker.offsetWidth;
    requestAnimationFrame(() => {
      if (marker.isConnected) marker.classList.remove('dreamin');
    });
  }
  knownReviewDecisions = now;
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
    const titleEl = card && (card.querySelector(':scope > .qbody > .qt')
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
  // 409 itself (#136). A rejected 202 (res.ok true, body rejected:true — E5)
  // is that same failure, so the verdict `landed` decides, never res.ok.
  const v = res && res._dwv;
  if (!res || !v || !v.landed) { qaFail(card, v); return; }
  // the one moment it is safe to forget (#163's rule, one surface over): the
  // answer landed, so its draft must not survive to reappear as a thought he
  // already sent. A failed send returns above and keeps it. isDurable is the
  // module's receipt seam (writeVerdict.landed today; #263 later).
  if (DraftStore.isDurable(res)) dwDraft.clear(q.title);
  if (!card) return;
  holdRerenderUntil = Date.now() + MORPH_HOLD_MS;   // see ROUTER_JS
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
  const v = res && res._dwv;
  // a rejected 202 (res.ok true, body rejected — E5) clears the draft below,
  // which was the only copy of the note, so the verdict `landed` decides —
  // the same rule as sendAnswer one function up.
  if (!res || !v || !v.landed) { qaFail(card, v); return; }
  // a note is a successful send too, and the box clears for the next one — so
  // its draft clears with it, or the next re-render would restore the just-sent
  // note into the empty box he meant to clear (#269, #163's rule).
  if (DraftStore.isDurable(res)) dwDraft.clear(entry.title);
  holdRerenderUntil = Date.now() + MORPH_HOLD_MS;
  if (!card) { el.value = ''; return; }
  // #191, the same as an answer: the note lands INSIDE the card, so the card
  // grows and every card below it moves. Snapshot before the first thing that
  // changes a height — the box being cleared is one of those the moment a box
  // grows with what he types (#177), so it is inside the window rather than
  // trusted to stay inert.
  const before = snapshotCards();
  el.value = '';
  clearBox(el);                               // #177: snap to the floor; the regroup owns the travel
  // the LAST segment, because what he just wrote is the newest thing in the
  // thread — appending to the first would drop it above an answer written
  // hours earlier, which is the bug this whole split exists to prevent (#128).
  // That segment is also never the collapsed one, so it cannot land hidden.
  let host = [...card.querySelectorAll('.threadin')].pop();
  if (!host) {
    const thread = document.createElement('div'); thread.className = 'thread';
    host = document.createElement('div'); host.className = 'threadin';
    thread.appendChild(host);
    /* into the BODY, at its end (#326). `insertBefore(…, '.qcompose')` put it
       in the same visual place while the box was the card's last child, and
       would now land it OUTSIDE the review dock's scroller — a note he cannot
       scroll, wedged between the question and the box. The end of `.qbody` is
       the end of the thread on every route, which is what the segment rule
       below is about. */
    (qaScroller(card) || card).appendChild(thread);
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
   settles in place before the loop's fresh data regroups it (#79/#81).
   #234 derived the hold from the critical path instead of padding it:
   - `flipDock`'s transform leg is 1.15s — the longest VISIBLE gesture of
     the submit morph (its filter/opacity legs are shorter, and its 1500ms
     safety-net `clear` only strips inline styles `transitionend` already
     stripped at ~1150ms, so nothing is on screen past the transform).
   - the regroup's `CARD_TRAVEL` is 850ms of visible travel; its inline
     cleanup at `CARD_MS + 150` is, again, invisible.
   - the ripple lives on `document.body`, outside the re-rendered view, so
     a tick cannot interrupt it at all.
   So 1150ms plus one beat of slack for the rAF that starts the transition
   and for frame jitter: 1250ms. 850ms was considered and rejected — it
   would release mid-glide. Under reduced motion NONE of the three runs
   (`flipDock`/`ripple` skip on `rmr`, `regroupCards` returns early), so
   the same number is pure margin there, and the shared constant keeps the
   two paths from drifting. Measured by dev/capture/morphhold.mjs. */
const MORPH_HOLD_MS = 1250;
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
/* /file view fetch (#336). `fetched` is one of:
   - null: the file is missing or the request failed → 'not found'
   - {text}: the file is text → render as today (md or <pre>)
   - {binary, kind, mime, size}: a binary file → render an <img> (kind ===
     'image') or a binary-info panel with a download affordance (else).
   The /filedata response carries one of those shapes; never the bytes. */
let fileCache = { param: null, fetched: undefined };
/* per-page atmosphere: a tiny tint bias the shader lerps toward (~1.5s) */
const TINT = { dashboard: 0.0, questions: 0.14, answers: 0.08, file: -0.14, review: 0.22, question: 0.18, research: -0.08 };
/* per-route dissolve signature: each destination swirls from its own
   turbulence seed, so arriving somewhere has a consistent feel (pairs with
   the per-route tint). Distinct small integers give distinct fields. */
const SEED = { dashboard: 7, questions: 23, answers: 29, file: 41, review: 61, question: 67, research: 71 };
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
                      answers: () => 'answers',
                      file: p => p || 'file',
                      review: p => 'review ' + (p || ''),
                      question: () => 'question',
                      research: p => 'research' + (p ? ' ' + p : '') };
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
    // raw-fetch site: owns its Response, so reads the verdict here. A rejected
    // 202 (res.ok true) would otherwise apply a tint that did not land (#136).
    ok = (await writeVerdict(res)).landed;
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
/* ── #290 main-dreamer run mode ───────────────────────────────────────────
   Authoritative file is `.dreamwork/run-mode` (gitignored). The dashboard
   shares one pending mode/deadline across tabs via localStorage; every
   selection resets a 10s arm; only the final mode POSTs and emits one
   monitored event. Identical final is idempotent server-side. Hierarchical
   is visible and disabled (planned until #264/#288). Reduced motion drops
   the width animation but keeps second text + the same application time. */
let runArmGen = 0;
let runArmTimer = null;
let runArmTick = null;
// Only the tab that called pickRunMode POSTs. Followers that adopt via the
// storage listener (or setContent resume without ownership) display the same
// countdown but do not dual-fire /run-mode — that would double the event path.
// After a hard refresh, sessionStorage owner id can reclaim commit ownership.
let runArmShouldCommit = false;
let runArmUntil = 0;   // last armed deadline; avoids bar snap-restart on tick
function runPendingKey() {
  return (data && data.target) ? ('dw:run-mode-pending:' + data.target) : null;
}
function runTabId() {
  try {
    let id = sessionStorage.getItem('dw:run-mode-tab');
    if (!id) {
      id = 't' + Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem('dw:run-mode-tab', id);
    }
    return id;
  } catch (e) { return 'anon'; }
}
// How long after `until` an unclaimed arm stays readable for orphan reclaim
// (tab-close mid-arm). Must exceed the deferred reclaim delay (1500ms).
const RUN_ORPHAN_GRACE_MS = 3000;
function readRunPending() {
  try {
    const k = runPendingKey();
    if (!k) return null;
    const p = JSON.parse(localStorage.getItem(k) || 'null');
    if (!p || typeof p.mode !== 'string') return null;
    if (RUN_MODES.indexOf(p.mode) < 0) return null;
    if (typeof p.until !== 'number') return null;
    // Cancel tombstones: readable until `until`, then GC (M1). Live peers
    // still see them for converge-to-mode during the short grace window.
    if (p.phase === 'cancel') {
      if (Date.now() >= p.until) { localStorage.removeItem(k); return null; }
      return p;
    }
    // Arm pending: do NOT purge at `until` — orphan reclaim (tab close) reads
    // the same record after the deadline. GC only after orphan grace.
    if (Date.now() >= p.until + RUN_ORPHAN_GRACE_MS) {
      localStorage.removeItem(k);
      return null;
    }
    return p;
  } catch (e) { return null; }
}
function pendingIsLiveArm(p) {
  return !!(p && !p.phase && typeof p.until === 'number' && Date.now() < p.until);
}
function writeRunPending(mode, until, owner) {
  try {
    const k = runPendingKey();
    if (!k) return;
    const body = { mode, until, owner: owner || runTabId() };
    localStorage.setItem(k, JSON.stringify(body));
  } catch (e) { /* private mode / full disk — live UI still arms locally */ }
}
function writeRunCancel(mode) {
  // Distinguish cancel from "initiator cleared pending to POST": followers
  // must paint the committed mode now (cancel produces no mtime change).
  // `until` is the tombstone expiry (M1), not an arm deadline.
  try {
    const k = runPendingKey();
    if (!k) return;
    localStorage.setItem(k, JSON.stringify({
      mode, phase: 'cancel', until: Date.now() + 800, owner: runTabId(),
    }));
  } catch (e) {}
}
function clearRunPending() {
  try {
    const k = runPendingKey();
    if (k) localStorage.removeItem(k);
  } catch (e) {}
}
function committedRunMode(d) {
  const m = (d && d.run_mode) || RUN_MODE_DEFAULT;
  return RUN_MODES.indexOf(m) >= 0 ? m : RUN_MODE_DEFAULT;
}
function paintRunModeSelection(mode, snap) {
  document.querySelectorAll('.sgroup.runmodes').forEach(g => {
    g.querySelectorAll('.sgbtn').forEach(b => {
      if (b.disabled) return;
      const on = b.dataset.mode === mode;
      b.classList.toggle('on', on);
      b.setAttribute('aria-checked', on ? 'true' : 'false');
    });
    slideIndicator(g, !!snap);
  });
}
function clearRunArmUI() {
  if (runArmTimer) { clearTimeout(runArmTimer); runArmTimer = null; }
  if (runArmTick) { clearInterval(runArmTick); runArmTick = null; }
  runArmUntil = 0;
  const bar = document.getElementById('runbar');
  const fill = document.getElementById('runbarfill');
  const count = document.getElementById('runcount');
  if (bar) bar.hidden = true;
  if (fill) {
    fill.classList.add('snap');
    fill.style.width = '100%';
  }
  if (count) count.textContent = '';
}
function armRunModeUI(mode, until, gen) {
  // Stop prior timers without zeroing runArmUntil before we compare — a
  // setContent rebuild with the same deadline must resume mid-drain, not
  // snap the fill back to 100%.
  if (runArmTimer) { clearTimeout(runArmTimer); runArmTimer = null; }
  if (runArmTick) { clearInterval(runArmTick); runArmTick = null; }
  const bar = document.getElementById('runbar');
  const fill = document.getElementById('runbarfill');
  const count = document.getElementById('runcount');
  const rm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const remainingMs = () => Math.max(0, until - Date.now());
  const setCount = () => {
    if (gen !== runArmGen) return;
    if (!count) return;
    const s = Math.ceil(remainingMs() / 1000);
    count.textContent = s > 0
      ? `arms in ${s}s · ${mode}`
      : `applying ${mode}…`;
  };
  setCount();
  if (!rm && bar && fill) {
    bar.hidden = false;
    const left = remainingMs();
    // remaining fraction of the full arm — not always 100%, so a tick that
    // rebuilds the DOM mid-arm continues the drain instead of restarting.
    const frac = Math.max(0, Math.min(1, left / RUN_ARM_MS));
    fill.classList.add('snap');
    fill.style.transitionDuration = '0ms';
    fill.style.width = (frac * 100) + '%';
    void fill.offsetWidth;
    fill.style.transitionDuration = Math.max(0, left) + 'ms';
    fill.classList.remove('snap');
    fill.style.width = '0%';
  } else if (bar) {
    bar.hidden = true;
  }
  runArmUntil = until;
  runArmTick = setInterval(() => {
    if (gen !== runArmGen) return;
    setCount();
    if (remainingMs() <= 0 && runArmTick) {
      clearInterval(runArmTick); runArmTick = null;
    }
  }, 250);
  runArmTimer = setTimeout(() => {
    if (gen !== runArmGen) return;
    if (runArmShouldCommit) commitRunMode(mode, gen);
    else {
      // Display-only path: do NOT race the owner at the same deadline.
      // Orphan reclaim is deferred so a live initiator always wins the CAS.
      // Pending must still be readable after `until` (see readRunPending grace).
      clearRunArmUI();
      setTimeout(() => {
        if (gen !== runArmGen) return;
        const p = readRunPending();
        const cur = committedRunMode(data);
        if (p && !p.phase && p.mode === mode && cur !== mode)
          commitRunMode(mode, gen, { orphan: true });
        else
          paintRunModeSelection(committedRunMode(data), true);
      }, 1500);
    }
  }, remainingMs());
}
/** Claim the pending arm for a single POST. Returns false if a peer already
 *  claimed or the pending is not ours to fire — prevents dual-POST at the
 *  shared deadline (owner + follower timers both firing). */
function claimRunPending(mode, { orphan = false } = {}) {
  try {
    const k = runPendingKey();
    if (!k) return false;
    const raw = localStorage.getItem(k);
    if (!raw) return false;
    const p = JSON.parse(raw);
    if (!p || p.phase === 'cancel' || p.mode !== mode) return false;
    if (p.owner && p.owner !== runTabId()) {
      // Not the arming tab: only orphan reclaim after deadline + 1s may claim
      // (live owner still has exclusive window at `until`).
      if (!orphan) return false;
      if (typeof p.until === 'number' && Date.now() < p.until + 1000)
        return false;
    }
    localStorage.removeItem(k);   // claim — peer re-read sees null
    return true;
  } catch (e) { return false; }
}
async function commitRunMode(mode, gen, opts) {
  if (gen !== runArmGen) return;
  const msg = document.getElementById('runmsg');
  const orphan = !!(opts && opts.orphan);
  // CAS: only one tab POSTs for a given arm. Identical final stays server-side
  // idempotent if a second request still slips through.
  if (!claimRunPending(mode, { orphan })) {
    runArmShouldCommit = false;
    clearRunArmUI();
    paintRunModeSelection(committedRunMode(data), true);
    return;
  }
  let ok = false;
  try {
    const res = await fetch('/run-mode', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mode,
        from: location.pathname + location.search,
        // diagnostic only — server ignores unknown fields
        tab: runTabId(),
        orphan: orphan || false,
      }),
    });
    // raw-fetch site: owns its Response, so reads the verdict here. A rejected
    // 202 (res.ok true) would otherwise commit a mode that did not land (#136).
    const rv = await writeVerdict(res);
    ok = rv.landed;
  } catch (e) { ok = false; }
  if (gen !== runArmGen) return;
  if (ok) {
    runArmShouldCommit = false;
    clearRunArmUI();
    if (msg) msg.textContent = '';
    if (data) data.run_mode = mode;
    paintRunModeSelection(mode, true);
  } else if (msg) {
    msg.textContent = 'could not save the run mode — the write was refused';
    clearRunPending();
    runArmShouldCommit = false;
    clearRunArmUI();
    paintRunModeSelection(committedRunMode(data), true);
  }
}
function pickRunMode(mode) {
  if (RUN_MODES.indexOf(mode) < 0) return;  // hierarchical etc.
  const msg = document.getElementById('runmsg');
  if (msg) msg.textContent = '';
  const cur = committedRunMode(data);
  // re-selecting the committed mode cancels any pending arm
  if (mode === cur) {
    runArmGen++;
    runArmShouldCommit = false;
    writeRunCancel(cur);           // peers must converge (cancel ≠ commit-clear)
    clearRunArmUI();
    paintRunModeSelection(mode, false);
    // drop tombstone after storage has fired in other tabs
    setTimeout(() => {
      const p = readRunPending();
      if (p && p.phase === 'cancel') clearRunPending();
    }, 100);
    return;
  }
  const until = Date.now() + RUN_ARM_MS;
  runArmGen++;
  const gen = runArmGen;
  runArmShouldCommit = true;   // this tab owns the final POST
  writeRunPending(mode, until, runTabId());
  paintRunModeSelection(mode, false);
  armRunModeUI(mode, until, gen);
}
function runModePicker(d) {
  const pending = readRunPending();
  // Only a still-counting arm paints as selected pending; expired-but-
  // reclaimable pending must not look like an active countdown.
  const arm = pendingIsLiveArm(pending) ? pending : null;
  const cur = arm ? arm.mode : committedRunMode(d);
  // aria-describedby always points at the one shared surface (#300).
  // Hover/focus only rewrite that surface — never arm, POST, or localStorage.
  const chips = RUN_MODES.map(n =>
    `<button type="button" role="radio" class="sgbtn runchip` +
    `${n === cur ? ' on' : ''}" data-mode="${esc(n)}"` +
    ` aria-checked="${n === cur ? 'true' : 'false'}"` +
    ` aria-describedby="rundesc-text"` +
    ` onclick="pickRunMode('${esc(n)}')">${esc(n)}</button>`).join('') +
    RUN_MODES_PLANNED.map(n =>
      `<button type="button" role="radio" class="sgbtn runchip" data-mode="${esc(n)}"` +
      ` aria-checked="false" aria-disabled="true" disabled` +
      ` aria-describedby="rundesc-text"` +
      ` title="planned — needs #264 concurrency and #288 containment">` +
      `${esc(n)}</button>`).join('');
  return `<section class="runmode" id="runmode" aria-label="run mode">` +
    label('run mode') +
    `<div class="sgroup runmodes" role="radiogroup" aria-label="run mode">` +
    `<div class="sgind"></div>${chips}</div>` +
    `<div class="rundesc" id="rundesc" role="tooltip" hidden aria-hidden="true">` +
    `<span class="rundesc-text" id="rundesc-text"></span></div>` +
    `<div class="runarm" id="runarm">` +
    `<div class="runbar" id="runbar" hidden aria-hidden="true">` +
    `<div class="runbarfill" id="runbarfill"></div></div>` +
    `<span class="runcount" id="runcount" aria-live="polite"></span></div>` +
    `<div class="runmsg" id="runmsg" aria-live="polite"></div></section>`;
}
/* ── #300 shared run-mode description ───────────────────────────────────
   Pure presentation. Hover, focus, Escape and pointer-leave never write a
   mode, never arm, never touch localStorage or POST /run-mode. One shell
   morphs its text in place so the eye never meets a second tooltip. */
let rundescMode = null;
let rundescPendingMode = null;  // retarget mid-dissolve without cancelling it
let rundescMorphGen = 0;
let rundescHideTimer = null;
let rundescMorphTimer = null;
function rundescReduced() {
  return matchMedia('(prefers-reduced-motion: reduce)').matches;
}
function runDescFor(mode) {
  if (!mode) return '';
  if (typeof RUN_MODE_DESC !== 'undefined' && RUN_MODE_DESC[mode])
    return RUN_MODE_DESC[mode];
  return '';
}
function hideRunDesc(immediate) {
  const shell = document.getElementById('rundesc');
  const text = document.getElementById('rundesc-text');
  if (!shell) return;
  if (rundescHideTimer) { clearTimeout(rundescHideTimer); rundescHideTimer = null; }
  if (rundescMorphTimer) { clearTimeout(rundescMorphTimer); rundescMorphTimer = null; }
  if (!shell.classList.contains('open') && shell.hidden) {
    rundescMode = null;
    rundescPendingMode = null;
    return;
  }
  rundescMorphGen++;   // cancel any in-flight morph
  rundescPendingMode = null;
  const rm = !!immediate || rundescReduced();
  const finish = () => {
    shell.classList.remove('open', 'pose', 'depart');
    shell.setAttribute('aria-hidden', 'true');
    shell.hidden = true;
    if (text) {
      text.textContent = '';
      text.classList.remove('out', 'in');
    }
    rundescMode = null;
    rundescPendingMode = null;
  };
  if (rm) { finish(); return; }
  shell.classList.add('depart');
  const onEnd = e => {
    if (e.target !== shell || e.propertyName !== 'opacity') return;
    shell.removeEventListener('transitionend', onEnd);
    finish();
  };
  shell.addEventListener('transitionend', onEnd);
  rundescHideTimer = setTimeout(finish, 550);
}
function rundescResolveText(text, shell) {
  // End of dissolve: paint the LATEST pending mode (rapid hover retargets
  // without restarting the dissolve, which would cancel forever).
  const mode = rundescPendingMode || rundescMode;
  const body = runDescFor(mode);
  if (!body) return;
  text.textContent = body;
  shell.dataset.mode = mode;
  rundescMode = mode;
  rundescPendingMode = null;
  text.classList.remove('out');
  text.classList.add('in');
  void text.offsetWidth;
  text.classList.remove('in');
}
function showRunDesc(mode) {
  // Presentation only. Must never arm, write pending state, commit, or POST.
  // (Those live in pick/commit helpers — this function only paints text.)
  const body = runDescFor(mode);
  if (!body) return;
  const shell = document.getElementById('rundesc');
  const text = document.getElementById('rundesc-text');
  if (!shell || !text) return;
  if (rundescHideTimer) { clearTimeout(rundescHideTimer); rundescHideTimer = null; }
  shell.classList.remove('depart');
  const rm = rundescReduced();
  const first = !shell.classList.contains('open') || shell.hidden;

  if (first) {
    rundescMorphGen++;
    if (rundescMorphTimer) { clearTimeout(rundescMorphTimer); rundescMorphTimer = null; }
    text.classList.remove('out', 'in');
    text.textContent = body;
    shell.dataset.mode = mode;
    shell.hidden = false;
    shell.setAttribute('aria-hidden', 'false');
    shell.classList.add('open');
    if (rm) {
      shell.classList.remove('pose');
    } else {
      shell.classList.add('pose');
      void shell.offsetWidth;
      shell.classList.remove('pose');
    }
    rundescMode = mode;
    rundescPendingMode = null;
    return;
  }

  // Already open on this mode and not mid-dissolve — nothing to do.
  if (mode === rundescMode && text.textContent === body
      && !text.classList.contains('out')) return;

  // Button→button: shell stays open; text dissolves then resolves.
  if (rm) {
    rundescMorphGen++;
    if (rundescMorphTimer) { clearTimeout(rundescMorphTimer); rundescMorphTimer = null; }
    text.classList.remove('out', 'in');
    text.textContent = body;
    shell.dataset.mode = mode;
    rundescMode = mode;
    rundescPendingMode = null;
    return;
  }

  // Mid-dissolve: retarget the resolve leg only. Restarting .out would
  // cancel the in-flight transitionend/timeout forever under rapid hover.
  rundescPendingMode = mode;
  if (text.classList.contains('out')) return;

  const gen = rundescMorphGen;  // do not bump — hide is what cancels
  text.classList.remove('in');
  // Start the dissolve from the live computed style. Do NOT thrash
  // transition:none first: that cost ~130ms of still-at-1 frames under
  // load before the browser painted the fall, and the morph guard's
  // short window then saw only endpoints (false red, real motion).
  text.classList.add('out');
  let done = false;
  const finishMorph = () => {
    if (done) return;
    done = true;
    if (rundescMorphTimer) { clearTimeout(rundescMorphTimer); rundescMorphTimer = null; }
    text.removeEventListener('transitionend', once);
    // hideRunDesc bumps gen; a live morph keeps the same gen.
    if (gen !== rundescMorphGen) return;
    rundescResolveText(text, shell);
  };
  const once = e => {
    if (e.target !== text || e.propertyName !== 'opacity') return;
    finishMorph();
  };
  text.addEventListener('transitionend', once);
  rundescMorphTimer = setTimeout(finishMorph, 380);
}
function rundescPointerInside(node) {
  const sec = document.getElementById('runmode');
  return !!(sec && node && sec.contains(node));
}
// Document-level once: the section is rebuilt by the tick's innerHTML, so a
// per-element bind would die every two seconds. Hover never selects.
document.addEventListener('pointerover', e => {
  const b = e.target && e.target.closest && e.target.closest('#runmode .runchip');
  if (!b) return;
  showRunDesc(b.dataset.mode);
});
document.addEventListener('pointerout', e => {
  const sec = document.getElementById('runmode');
  if (!sec) return;
  // Leaving the whole section (not merely crossing a chip) dismisses.
  if (!rundescPointerInside(e.target)) return;
  if (rundescPointerInside(e.relatedTarget)) return;
  // Keep open while a chip holds keyboard focus.
  if (sec.querySelector('.runchip:focus')) return;
  hideRunDesc();
});
document.addEventListener('focusin', e => {
  const b = e.target && e.target.closest && e.target.closest('#runmode .runchip');
  if (b) showRunDesc(b.dataset.mode);
});
document.addEventListener('focusout', e => {
  const sec = document.getElementById('runmode');
  if (!sec) return;
  // Defer: focus may be moving to a sibling chip.
  setTimeout(() => {
    if (!sec.isConnected) return;
    if (sec.contains(document.activeElement)) {
      const b = document.activeElement.closest
        && document.activeElement.closest('.runchip');
      if (b) showRunDesc(b.dataset.mode);
      return;
    }
    // Pointer still over the section keeps it open.
    if (sec.matches(':hover')) return;
    hideRunDesc();
  }, 0);
});
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  const shell = document.getElementById('rundesc');
  if (!shell || !shell.classList.contains('open')) return;
  hideRunDesc();
  // Presentation only — do not cancel an arm, do not blur a chip forcibly
  // unless that would leave the tooltip stranded (it is already dismissed).
});
function syncRunModeFromData() {
  // After a re-render or remote tick: resume shared pending if live, else
  // follow the authoritative file. Never invent a pending from server alone.
  const pending = readRunPending();
  if (pending && pending.phase === 'cancel') {
    if (document.querySelector('.sgroup.runmodes'))
      paintRunModeSelection(pending.mode, true);
    runArmShouldCommit = false;
    clearRunArmUI();
    return;
  }
  if (pending && !pending.phase) {
    // Ownership is timer+flag state, NOT picker DOM. An initiator that
    // navigates to /questions mid-arm must still POST at the deadline —
    // reclaim via sessionStorage owner id (survives reload; lost on tab close).
    if (pending.owner && pending.owner === runTabId())
      runArmShouldCommit = true;
    if (document.querySelector('.sgroup.runmodes'))
      paintRunModeSelection(pending.mode, true);
    if (pendingIsLiveArm(pending)) {
      // Still counting: keep commit/display timer alive even without picker DOM.
      runArmGen++;
      armRunModeUI(pending.mode, pending.until, runArmGen);
    } else if (runArmShouldCommit || !pending.owner || pending.owner === runTabId()) {
      // Past until, still reclaimable: fire claim now (reload after deadline).
      runArmGen++;
      commitRunMode(pending.mode, runArmGen, { orphan: !runArmShouldCommit });
    } else {
      // Follower seeing expired pending: schedule orphan reclaim once.
      runArmGen++;
      const gen = runArmGen, mode = pending.mode;
      setTimeout(() => {
        if (gen !== runArmGen) return;
        const p = readRunPending();
        const cur = committedRunMode(data);
        if (p && !p.phase && p.mode === mode && cur !== mode)
          commitRunMode(mode, gen, { orphan: true });
      }, 200);
    }
    return;
  }
  if (document.querySelector('.sgroup.runmodes'))
    paintRunModeSelection(committedRunMode(data), true);
  // No live pending: drop ownership/timers. Do not do this merely because
  // the dashboard picker is absent while an arm is still shared.
  runArmShouldCommit = false;
  clearRunArmUI();
}
window.addEventListener('storage', e => {
  if (!e.key || e.key.indexOf('dw:run-mode-pending:') !== 0) return;
  if (!data || e.key !== runPendingKey()) return;
  // another tab rewrote the shared pending — adopt UI without write-back
  const pending = readRunPending();
  runArmGen++;
  if (!pending) {
    // Peer cleared pending to POST. Keep the armed selection (do not snap
    // to stale data.run_mode); /mtime carries the committed file.
    runArmShouldCommit = false;
    clearRunArmUI();
    return;
  }
  if (pending.phase === 'cancel') {
    runArmShouldCommit = false;
    clearRunArmUI();
    paintRunModeSelection(pending.mode, true);
    return;
  }
  runArmShouldCommit = false;
  paintRunModeSelection(pending.mode, true);
  armRunModeUI(pending.mode, pending.until, runArmGen);
});
/* ── #445 three-axis posture controls ───────────────────────────────────
   Sibling of run-mode. Authority is `.dreamwork/posture` when present;
   otherwise the UI paints the derivation from run-mode (lint.derive_posture
   via collect()). ONE shared 10s arm covers a whole posture edit — three
   independent arms would be three ceremonies for one file. Reuses RUN_ARM_MS
   rather than a second cooldown. Asymmetry is honest: pace three chips,
   asking four (his dictation — never compress), delegation an integer
   target with a derived label (own/assist/delegate) — a TARGET, never a cap.
   One POST /posture; one events line only on a real change. */
let postArmGen = 0;
let postArmTimer = null;
let postArmTick = null;
let postArmShouldCommit = false;
let postArmUntil = 0;
// Draft of the whole triple while arming (any axis change resets the arm).
let postDraft = null;
function postPendingKey() {
  return (data && data.target) ? ('dw:posture-pending:' + data.target) : null;
}
function postTabId() {
  try {
    let id = sessionStorage.getItem('dw:posture-tab');
    if (!id) {
      id = 't' + Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem('dw:posture-tab', id);
    }
    return id;
  } catch (e) { return 'anon'; }
}
const POST_ORPHAN_GRACE_MS = 3000;
function readPostPending() {
  try {
    const k = postPendingKey();
    if (!k) return null;
    const p = JSON.parse(localStorage.getItem(k) || 'null');
    if (!p || typeof p.pace !== 'string' || typeof p.asking !== 'string')
      return null;
    if (POSTURE_STOPS_PACE.indexOf(p.pace) < 0) return null;
    if (POSTURE_STOPS_ASKING.indexOf(p.asking) < 0) return null;
    if (typeof p.delegation !== 'number' || p.delegation < 0) return null;
    // delivery is optional in a stale pending cache — default it to instant
    // rather than rejecting, so a pre-#342 pending entry still resumes.
    if (p.delivery != null && POSTURE_STOPS_DELIVERY.indexOf(p.delivery) < 0)
      return null;
    if (typeof p.until !== 'number') return null;
    if (p.phase === 'cancel') {
      if (Date.now() >= p.until) { localStorage.removeItem(k); return null; }
      return p;
    }
    if (Date.now() >= p.until + POST_ORPHAN_GRACE_MS) {
      localStorage.removeItem(k);
      return null;
    }
    return p;
  } catch (e) { return null; }
}
function pendingPostIsLive(p) {
  return !!(p && !p.phase && typeof p.until === 'number' && Date.now() < p.until);
}
function writePostPending(draft, until, owner) {
  try {
    const k = postPendingKey();
    if (!k) return;
    localStorage.setItem(k, JSON.stringify({
      pace: draft.pace, asking: draft.asking, delegation: draft.delegation,
      delivery: draft.delivery,
      until, owner: owner || postTabId(),
    }));
  } catch (e) {}
}
function writePostCancel(draft) {
  try {
    const k = postPendingKey();
    if (!k) return;
    localStorage.setItem(k, JSON.stringify({
      pace: draft.pace, asking: draft.asking, delegation: draft.delegation,
      delivery: draft.delivery,
      phase: 'cancel', until: Date.now() + 800, owner: postTabId(),
    }));
  } catch (e) {}
}
function clearPostPending() {
  try {
    const k = postPendingKey();
    if (k) localStorage.removeItem(k);
  } catch (e) {}
}
function committedPosture(d) {
  const p = (d && d.posture) || {};
  const pace = POSTURE_STOPS_PACE.indexOf(p.pace) >= 0 ? p.pace : POSTURE_STOPS_PACE[0];
  const asking = POSTURE_STOPS_ASKING.indexOf(p.asking) >= 0
    ? p.asking : POSTURE_STOPS_ASKING[0];
  const delivery = POSTURE_STOPS_DELIVERY.indexOf(p.delivery) >= 0
    ? p.delivery : 'instant';
  let dlg = 0;
  try { dlg = Math.max(0, parseInt(p.delegation, 10) || 0); } catch (e) { dlg = 0; }
  return {
    pace, asking, delegation: dlg, delivery,
    source: p.source === 'file' ? 'file' : 'derived',
    delegation_label: p.delegation_label || delegationLabel(dlg),
  };
}
function delegationLabel(n) {
  if (n <= 0) return 'own';
  if (n === 1) return 'assist';
  return 'delegate';
}
function paintPostureSelection(draft, snap) {
  document.querySelectorAll('.sgroup.paxis-chips').forEach(g => {
    const axis = g.dataset.axis;
    g.querySelectorAll('.sgbtn').forEach(b => {
      const on = b.dataset.stop === draft[axis];
      b.classList.toggle('on', on);
      b.setAttribute('aria-checked', on ? 'true' : 'false');
    });
    slideIndicator(g, !!snap);
  });
  const val = document.getElementById('pstepval');
  const lab = document.getElementById('psteplabel');
  if (val) val.textContent = String(draft.delegation);
  if (lab) {
    const name = delegationLabel(draft.delegation);
    lab.textContent = name;
    lab.dataset.label = name;
  }
  const dec = document.getElementById('pstepdec');
  const inc = document.getElementById('pstepinc');
  if (dec) dec.disabled = draft.delegation <= 0;
  if (inc) inc.disabled = draft.delegation >= POSTURE_DELEGATION_UI_MAX;
  const src = document.getElementById('posture-src');
  if (src) {
    const live = pendingPostIsLive(readPostPending());
    if (live) {
      src.textContent = 'arming override…';
      src.className = 'posture-src file';
    } else if (draft.source === 'file') {
      src.textContent = 'override · .dreamwork/posture';
      src.className = 'posture-src file';
    } else {
      src.textContent = 'derived from run mode · pick a stop to override';
      src.className = 'posture-src';
    }
  }
}
function clearPostArmUI() {
  if (postArmTimer) { clearTimeout(postArmTimer); postArmTimer = null; }
  if (postArmTick) { clearInterval(postArmTick); postArmTick = null; }
  postArmUntil = 0;
  const bar = document.getElementById('pbar');
  const fill = document.getElementById('pbarfill');
  const count = document.getElementById('pcount');
  if (bar) bar.hidden = true;
  if (fill) {
    fill.classList.add('snap');
    fill.style.width = '100%';
  }
  if (count) count.textContent = '';
}
function armPostureUI(draft, until, gen) {
  if (postArmTimer) { clearTimeout(postArmTimer); postArmTimer = null; }
  if (postArmTick) { clearInterval(postArmTick); postArmTick = null; }
  const bar = document.getElementById('pbar');
  const fill = document.getElementById('pbarfill');
  const count = document.getElementById('pcount');
  const rm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const remainingMs = () => Math.max(0, until - Date.now());
  const setCount = () => {
    if (gen !== postArmGen) return;
    if (!count) return;
    const s = Math.ceil(remainingMs() / 1000);
    const label = draft.pace + ' · ' + draft.asking + ' · ' + draft.delegation;
    count.textContent = s > 0
      ? `arms in ${s}s · ${label}`
      : `applying ${label}…`;
  };
  setCount();
  if (!rm && bar && fill) {
    bar.hidden = false;
    const left = remainingMs();
    const frac = Math.max(0, Math.min(1, left / RUN_ARM_MS));
    fill.classList.add('snap');
    fill.style.transitionDuration = '0ms';
    fill.style.width = (frac * 100) + '%';
    void fill.offsetWidth;
    fill.style.transitionDuration = Math.max(0, left) + 'ms';
    fill.classList.remove('snap');
    fill.style.width = '0%';
  } else if (bar) {
    bar.hidden = true;
  }
  postArmUntil = until;
  postArmTick = setInterval(() => {
    if (gen !== postArmGen) return;
    setCount();
    if (remainingMs() <= 0 && postArmTick) {
      clearInterval(postArmTick); postArmTick = null;
    }
  }, 250);
  postArmTimer = setTimeout(() => {
    if (gen !== postArmGen) return;
    if (postArmShouldCommit) commitPosture(draft, gen);
    else {
      clearPostArmUI();
      setTimeout(() => {
        if (gen !== postArmGen) return;
        const p = readPostPending();
        const cur = committedPosture(data);
        if (p && !p.phase && p.pace === draft.pace
            && p.asking === draft.asking
            && p.delegation === draft.delegation
            && (cur.pace !== draft.pace || cur.asking !== draft.asking
                || cur.delegation !== draft.delegation
                || cur.source !== 'file'))
          commitPosture(draft, gen, { orphan: true });
        else
          paintPostureSelection(committedPosture(data), true);
      }, 1500);
    }
  }, remainingMs());
}
function claimPostPending(draft, { orphan = false } = {}) {
  try {
    const k = postPendingKey();
    if (!k) return false;
    const raw = localStorage.getItem(k);
    if (!raw) return false;
    const p = JSON.parse(raw);
    if (!p || p.phase === 'cancel') return false;
    if (p.pace !== draft.pace || p.asking !== draft.asking
        || p.delegation !== draft.delegation) return false;
    if (p.owner && p.owner !== postTabId()) {
      if (!orphan) return false;
      if (typeof p.until === 'number' && Date.now() < p.until + 1000)
        return false;
    }
    localStorage.removeItem(k);
    return true;
  } catch (e) { return false; }
}
async function commitPosture(draft, gen, opts) {
  if (gen !== postArmGen) return;
  const msg = document.getElementById('pmsg');
  const orphan = !!(opts && opts.orphan);
  if (!claimPostPending(draft, { orphan })) {
    postArmShouldCommit = false;
    clearPostArmUI();
    paintPostureSelection(committedPosture(data), true);
    return;
  }
  let ok = false;
  let body = null;
  try {
    const res = await fetch('/posture', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pace: draft.pace,
        asking: draft.asking,
        delegation: draft.delegation,
        delivery: draft.delivery,
        from: location.pathname + location.search,
        tab: postTabId(),
        orphan: orphan || false,
      }),
    });
    const rv = await writeVerdict(res);
    ok = rv.landed;
    body = rv;
  } catch (e) { ok = false; }
  if (gen !== postArmGen) return;
  if (ok) {
    postArmShouldCommit = false;
    clearPostArmUI();
    if (msg) msg.textContent = '';
    if (data) {
      data.posture = {
        pace: draft.pace,
        asking: draft.asking,
        delegation: draft.delegation,
        delivery: draft.delivery,
        source: 'file',
        delegation_label: delegationLabel(draft.delegation),
      };
    }
    postDraft = null;
    paintPostureSelection(committedPosture(data), true);
  } else if (msg) {
    msg.textContent = 'could not save the posture — the write was refused';
    clearPostPending();
    postArmShouldCommit = false;
    clearPostArmUI();
    postDraft = null;
    paintPostureSelection(committedPosture(data), true);
  }
}
function armPostureDraft(next) {
  const msg = document.getElementById('pmsg');
  if (msg) msg.textContent = '';
  const cur = committedPosture(data);
  // Re-selecting the fully committed point cancels any pending arm.
  if (next.pace === cur.pace && next.asking === cur.asking
      && next.delegation === cur.delegation
      && next.delivery === cur.delivery && cur.source === 'file') {
    postArmGen++;
    postArmShouldCommit = false;
    writePostCancel(cur);
    clearPostArmUI();
    postDraft = null;
    paintPostureSelection(cur, false);
    setTimeout(() => {
      const p = readPostPending();
      if (p && p.phase === 'cancel') clearPostPending();
    }, 100);
    return;
  }
  const until = Date.now() + RUN_ARM_MS;
  postArmGen++;
  const gen = postArmGen;
  postArmShouldCommit = true;
  postDraft = {
    pace: next.pace, asking: next.asking, delegation: next.delegation,
    delivery: next.delivery, source: 'file',
  };
  writePostPending(postDraft, until, postTabId());
  paintPostureSelection(postDraft, false);
  armPostureUI(postDraft, until, gen);
}
function pickPostureAxis(axis, stop) {
  if (axis === 'pace' && POSTURE_STOPS_PACE.indexOf(stop) < 0) return;
  if (axis === 'asking' && POSTURE_STOPS_ASKING.indexOf(stop) < 0) return;
  if (axis === 'delivery' && POSTURE_STOPS_DELIVERY.indexOf(stop) < 0) return;
  const base = postDraft || committedPosture(data);
  const next = {
    pace: base.pace, asking: base.asking, delegation: base.delegation,
    delivery: base.delivery,
  };
  next[axis] = stop;
  armPostureDraft(next);
}
function stepPostureDelegation(delta) {
  const base = postDraft || committedPosture(data);
  let n = base.delegation + delta;
  if (n < 0) n = 0;
  if (n > POSTURE_DELEGATION_UI_MAX) n = POSTURE_DELEGATION_UI_MAX;
  armPostureDraft({
    pace: base.pace, asking: base.asking, delegation: n,
    delivery: base.delivery,
  });
}
function posturePicker(d) {
  const pending = readPostPending();
  const arm = pendingPostIsLive(pending) ? pending : null;
  const cur = arm
    ? { pace: arm.pace, asking: arm.asking, delegation: arm.delegation,
        delivery: arm.delivery || 'instant', source: 'file' }
    : committedPosture(d);
  if (arm) postDraft = cur;
  const paceChips = POSTURE_STOPS_PACE.map(n =>
    `<button type="button" role="radio" class="sgbtn pchip` +
    `${n === cur.pace ? ' on' : ''}" data-stop="${esc(n)}"` +
    ` aria-checked="${n === cur.pace ? 'true' : 'false'}"` +
    ` aria-describedby="pdesc-text"` +
    ` onclick="pickPostureAxis('pace','${esc(n)}')">${esc(n)}</button>`
  ).join('');
  // Asking keeps all FOUR stops — his dictation. The control is asymmetric
  // on purpose; do not compress to three for tidy geometry.
  const askChips = POSTURE_STOPS_ASKING.map(n =>
    `<button type="button" role="radio" class="sgbtn pchip` +
    `${n === cur.asking ? ' on' : ''}" data-stop="${esc(n)}"` +
    ` aria-checked="${n === cur.asking ? 'true' : 'false'}"` +
    ` aria-describedby="pdesc-text"` +
    ` onclick="pickPostureAxis('asking','${esc(n)}')">${esc(n)}</button>`
  ).join('');
  // #342: delivery — a fourth axis row reusing the pace/asking chip idiom
  // verbatim (same .sgbtn.pchip class, same pickPostureAxis, the shared arm).
  // No second gesture; the chip arrives and changes state the same way.
  const deliveryChips = POSTURE_STOPS_DELIVERY.map(n =>
    `<button type="button" role="radio" class="sgbtn pchip` +
    `${n === cur.delivery ? ' on' : ''}" data-stop="${esc(n)}"` +
    ` aria-checked="${n === cur.delivery ? 'true' : 'false'}"` +
    ` aria-describedby="pdesc-text"` +
    ` onclick="pickPostureAxis('delivery','${esc(n)}')">${esc(n)}</button>`
  ).join('');
  const dlgLab = delegationLabel(cur.delegation);
  const srcNote = cur.source === 'file'
    ? 'override · .dreamwork/posture'
    : 'derived from run mode · pick a stop to override';
  // #488: source chip beside the heading; pdesc always in flow (no hidden).
  return `<section class="posture" id="posture" aria-label="posture">` +
    `<div class="posture-head">` +
    `<div class="label">posture</div>` +
    `<div class="posture-src${cur.source === 'file' ? ' file' : ''}"` +
    ` id="posture-src">${esc(srcNote)}</div></div>` +
    `<div class="posture-axes">` +
    `<div class="paxis" data-axis="pace">` +
    `<div class="paxis-lab" id="pace-lab">pace</div>` +
    `<div class="sgroup paxis-chips" role="radiogroup" data-axis="pace"` +
    ` aria-labelledby="pace-lab">` +
    `<div class="sgind"></div>${paceChips}</div></div>` +
    `<div class="paxis" data-axis="asking">` +
    `<div class="paxis-lab" id="asking-lab">asking</div>` +
    `<div class="sgroup paxis-chips" role="radiogroup" data-axis="asking"` +
    ` aria-labelledby="asking-lab">` +
    `<div class="sgind"></div>${askChips}</div></div>` +
    `<div class="paxis" data-axis="delegation">` +
    `<div class="paxis-lab" id="dlg-lab">delegation · avg concurrency target</div>` +
    `<div class="pstep" role="group" aria-labelledby="dlg-lab">` +
    `<button type="button" class="pstepbtn" id="pstepdec"` +
    ` aria-label="decrease delegation target"` +
    ` onclick="stepPostureDelegation(-1)"` +
    `${cur.delegation <= 0 ? ' disabled' : ''}>−</button>` +
    `<span class="pstepval" id="pstepval" aria-live="polite">` +
    `${esc(String(cur.delegation))}</span>` +
    `<button type="button" class="pstepbtn" id="pstepinc"` +
    ` aria-label="increase delegation target"` +
    ` onclick="stepPostureDelegation(1)"` +
    `${cur.delegation >= POSTURE_DELEGATION_UI_MAX ? ' disabled' : ''}>+</button>` +
    `<span class="psteplabel" id="psteplabel" data-label="${esc(dlgLab)}">` +
    `${esc(dlgLab)}</span></div>` +
    `<div class="pstephint">target, not a cap · 0 is occasional, not forbidden</div>` +
    `</div></div>` +
    // #342 delivery axis — same .paxis/.paxis-chips shape as pace/asking.
    `<div class="paxis" data-axis="delivery">` +
    `<div class="paxis-lab" id="delivery-lab">delivery · when interrupted</div>` +
    `<div class="sgroup paxis-chips" role="radiogroup" data-axis="delivery"` +
    ` aria-labelledby="delivery-lab">` +
    `<div class="sgind"></div>${deliveryChips}</div></div>` +
    `<div class="pdesc" id="pdesc" role="tooltip" aria-hidden="true">` +
    `<span class="pdesc-text" id="pdesc-text"></span></div>` +
    `<div class="parm" id="parm">` +
    `<div class="pbar" id="pbar" hidden aria-hidden="true">` +
    `<div class="pbarfill" id="pbarfill"></div></div>` +
    `<span class="pcount" id="pcount" aria-live="polite"></span></div>` +
    `<div class="pmsg" id="pmsg" aria-live="polite"></div></section>`;
}
/* Shared description for posture stops — presentation only; never arms. */
let pdescKey = null;
let pdescPendingKey = null;
let pdescMorphGen = 0;
let pdescHideTimer = null;
let pdescMorphTimer = null;
function pdescReduced() {
  return matchMedia('(prefers-reduced-motion: reduce)').matches;
}
function postDescFor(axis, stop) {
  if (axis === 'pace' && POSTURE_PACE_DESC[stop]) return POSTURE_PACE_DESC[stop];
  if (axis === 'asking' && POSTURE_ASKING_DESC[stop]) return POSTURE_ASKING_DESC[stop];
  if (axis === 'delegation' && POSTURE_DELEGATION_DESC[stop])
    return POSTURE_DELEGATION_DESC[stop];
  if (axis === 'delivery' && POSTURE_DELIVERY_DESC[stop])
    return POSTURE_DELIVERY_DESC[stop];
  return '';
}
function hidePostDesc(immediate) {
  const shell = document.getElementById('pdesc');
  const text = document.getElementById('pdesc-text');
  if (!shell) return;
  if (pdescHideTimer) { clearTimeout(pdescHideTimer); pdescHideTimer = null; }
  if (pdescMorphTimer) { clearTimeout(pdescMorphTimer); pdescMorphTimer = null; }
  // #488: shell stays in flow; idle is opacity:0, never hidden/display:none.
  if (!shell.classList.contains('open')) {
    pdescKey = null; pdescPendingKey = null; return;
  }
  pdescMorphGen++;
  pdescPendingKey = null;
  const rm = !!immediate || pdescReduced();
  const finish = () => {
    shell.classList.remove('open', 'pose', 'depart');
    shell.setAttribute('aria-hidden', 'true');
    if (text) { text.textContent = ''; text.classList.remove('out', 'in'); }
    pdescKey = null; pdescPendingKey = null;
  };
  if (rm) { finish(); return; }
  shell.classList.add('depart');
  const onEnd = e => {
    if (e.target !== shell || e.propertyName !== 'opacity') return;
    shell.removeEventListener('transitionend', onEnd);
    finish();
  };
  shell.addEventListener('transitionend', onEnd);
  pdescHideTimer = setTimeout(finish, 550);
}
function showPostDesc(axis, stop) {
  const body = postDescFor(axis, stop);
  if (!body) return;
  const shell = document.getElementById('pdesc');
  const text = document.getElementById('pdesc-text');
  if (!shell || !text) return;
  if (pdescHideTimer) { clearTimeout(pdescHideTimer); pdescHideTimer = null; }
  shell.classList.remove('depart');
  const key = axis + ':' + stop;
  const rm = pdescReduced();
  const first = !shell.classList.contains('open');
  if (first) {
    pdescMorphGen++;
    if (pdescMorphTimer) { clearTimeout(pdescMorphTimer); pdescMorphTimer = null; }
    text.classList.remove('out', 'in');
    text.textContent = body;
    shell.dataset.key = key;
    shell.setAttribute('aria-hidden', 'false');
    shell.classList.add('open');
    if (rm) shell.classList.remove('pose');
    else {
      shell.classList.add('pose');
      void shell.offsetWidth;
      shell.classList.remove('pose');
    }
    pdescKey = key;
    pdescPendingKey = null;
    return;
  }
  if (key === pdescKey && !pdescPendingKey) return;
  pdescPendingKey = key;
  if (rm) {
    text.textContent = body;
    shell.dataset.key = key;
    pdescKey = key;
    pdescPendingKey = null;
    return;
  }
  // dissolve then resolve — shell geometry fixed
  text.classList.add('out');
  const gen = ++pdescMorphGen;
  if (pdescMorphTimer) clearTimeout(pdescMorphTimer);
  pdescMorphTimer = setTimeout(() => {
    if (gen !== pdescMorphGen) return;
    const k = pdescPendingKey || pdescKey;
    const [ax, st] = (k || '').split(':');
    const b = postDescFor(ax, st);
    if (!b) return;
    text.textContent = b;
    shell.dataset.key = k;
    pdescKey = k;
    pdescPendingKey = null;
    text.classList.remove('out');
    text.classList.add('in');
    void text.offsetWidth;
    text.classList.remove('in');
  }, 340);
}
document.addEventListener('pointerover', e => {
  const b = e.target && e.target.closest && e.target.closest('#posture .pchip');
  if (!b) return;
  const g = b.closest('.paxis-chips');
  if (!g) return;
  showPostDesc(g.dataset.axis, b.dataset.stop);
});
document.addEventListener('focusin', e => {
  const b = e.target && e.target.closest && e.target.closest('#posture .pchip');
  if (!b) return;
  const g = b.closest('.paxis-chips');
  if (!g) return;
  showPostDesc(g.dataset.axis, b.dataset.stop);
});
document.addEventListener('pointerout', e => {
  const sec = document.getElementById('posture');
  if (!sec) return;
  setTimeout(() => {
    if (sec.matches(':hover')) return;
    hidePostDesc();
  }, 0);
});
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  const shell = document.getElementById('pdesc');
  if (!shell || !shell.classList.contains('open')) return;
  hidePostDesc();
});
// Stepper hover: show the label's description (own/assist/delegate)
document.addEventListener('pointerover', e => {
  const lab = e.target && e.target.closest && e.target.closest('#psteplabel');
  if (!lab) return;
  showPostDesc('delegation', lab.dataset.label || lab.textContent);
});
function syncPostureFromData() {
  const pending = readPostPending();
  if (pending && pending.phase === 'cancel') {
    if (document.getElementById('posture'))
      paintPostureSelection({
        pace: pending.pace, asking: pending.asking,
        delegation: pending.delegation, delivery: pending.delivery || 'instant',
        source: 'file',
      }, true);
    postArmShouldCommit = false;
    clearPostArmUI();
    return;
  }
  if (pending && !pending.phase) {
    if (pending.owner && pending.owner === postTabId())
      postArmShouldCommit = true;
    const draft = {
      pace: pending.pace, asking: pending.asking,
      delegation: pending.delegation, delivery: pending.delivery || 'instant',
      source: 'file',
    };
    postDraft = draft;
    if (document.getElementById('posture'))
      paintPostureSelection(draft, true);
    if (pendingPostIsLive(pending)) {
      postArmGen++;
      armPostureUI(draft, pending.until, postArmGen);
    } else if (postArmShouldCommit || !pending.owner
               || pending.owner === postTabId()) {
      postArmGen++;
      commitPosture(draft, postArmGen, { orphan: !postArmShouldCommit });
    } else {
      postArmGen++;
      const gen = postArmGen;
      setTimeout(() => {
        if (gen !== postArmGen) return;
        const p = readPostPending();
        const cur = committedPosture(data);
        if (p && !p.phase
            && (cur.pace !== p.pace || cur.asking !== p.asking
                || cur.delegation !== p.delegation
                || cur.delivery !== (p.delivery || 'instant')
                || cur.source !== 'file'))
          commitPosture({
            pace: p.pace, asking: p.asking, delegation: p.delegation,
            delivery: p.delivery || 'instant',
          }, gen, { orphan: true });
      }, 200);
    }
    return;
  }
  postDraft = null;
  if (document.getElementById('posture'))
    paintPostureSelection(committedPosture(data), true);
  postArmShouldCommit = false;
  clearPostArmUI();
}
window.addEventListener('storage', e => {
  if (!e.key || e.key.indexOf('dw:posture-pending:') !== 0) return;
  if (!data || e.key !== postPendingKey()) return;
  const pending = readPostPending();
  postArmGen++;
  if (!pending) {
    postArmShouldCommit = false;
    clearPostArmUI();
    return;
  }
  if (pending.phase === 'cancel') {
    postArmShouldCommit = false;
    clearPostArmUI();
    paintPostureSelection(committedPosture(data), true);
    return;
  }
  postArmShouldCommit = false;
  const draft = {
    pace: pending.pace, asking: pending.asking,
    delegation: pending.delegation, delivery: pending.delivery || 'instant',
    source: 'file',
  };
  postDraft = draft;
  paintPostureSelection(draft, true);
  armPostureUI(draft, pending.until, postArmGen);
});
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
  if (loc.pathname === '/file') {
    const sp = new URLSearchParams(loc.search);
    /* #252 — the view mode is part of the ROUTE, not a toggle the page
       remembers, so a copied or shared link preserves the intent it was
       copied with. Anything that is not `source` is rendered: an unknown
       value must not mint a third state, and `?view=` on a non-markdown path
       is simply inert (the switch is markdown-only and its body is verbatim
       either way). */
    return { name: 'file', param: sp.get('p'),
             mode: sp.get('view') === 'source' ? 'source' : 'rendered' };
  }
  if (loc.pathname === '/review') {
    const sp = new URLSearchParams(loc.search);
    return { name: 'review', param: sp.get('p'), q: sp.get('q') };
  }
  if (loc.pathname === '/question') {
    const sp = new URLSearchParams(loc.search);
    // the key is the question's TITLE identity — the same string data-qid
    // carries — so it survives everything the loop's churn does short of a
    // retitle (#452)
    return { name: 'question', param: sp.get('qid') };
  }
  // #484 — no param: the listing of built research artifacts; ?p=<name>:
  // one artifact in the review view's iframe idiom.
  if (loc.pathname === '/research') {
    const sp = new URLSearchParams(loc.search);
    return { name: 'research', param: sp.get('p') };
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
    if (burnStepPref === null) burnStepPref = loadBurnStepPref();
    setData(await (await fetch(dataJsonUrl())).json());
  } catch (e) {}
  return data;
}
async function fetchFile(param) {
  if (fileCache.param === param) return fileCache.fetched;
  let fetched = null;
  try {
    const res = await fetch('/filedata?p=' + encodeURIComponent(param || ''));
    if (res.ok) {
      const j = await res.json();
      if (j && j.binary) {
        fetched = { binary: true, kind: j.kind, mime: j.mime, size: j.size };
      } else if (j && typeof j.content === 'string') {
        /* #351: `hl` is the server's highlighted markup for a known source
           extension (review_artifact's #339 scanner, cached per file
           version). Absent for everything else; the client never tokenises
           and never invents markup — it only chooses between the server's
           two renderings. */
        fetched = { text: j.content,
                    hl: typeof j.hl === 'string' ? j.hl : null };
      }
    }
  } catch (e) {}
  fileCache = { param, fetched };
  return fetched;
}
async function buildCurrent() {
  if (view.name === 'file')
    return buildFile(view.param, await fetchFile(view.param), view.mode);
  const d = await ensureData();
  if (view.name === 'review') return buildReview(view.param, view.q, d);
  if (view.name === 'question') return buildQuestion(view.param, d);
  if (view.name === 'research') return buildResearch(view.param, d);
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
  box.value = saved.value;
  putScroll(box, saved.scroll);          // same silent clamp as the card's
  if (saved.height) box.style.height = saved.height;
  try { box.setSelectionRange(saved.start, saved.end); } catch (e) {}
  if (saved.focus) refocus(box);
}
/* #459: bind #askbox to DraftStore (ask:main). Snapshot (#118) carries a
   tick; storage carries a reload. bind is re-entrant-safe: unbind first so a
   tick re-render does not stack input listeners. Restores only into an empty
   box (live outranks). Silent — the text in the box is the statement. */
function bindAskDraft() {
  const box = document.getElementById('askbox');
  if (!box) return;
  const lid = DraftStore.id('ask', 'main');
  if (box.__dwDraftBound) DraftStore.unbind(box);
  DraftStore.bind(box, lid);
  DraftStore.restore(lid, box);
}
/* ── DraftStore (#269 module + #459 consumers) ───────────────────────────
   One deep module every text surface consumes. localStorage-backed (IDB is
   deferred: sync write on input cannot fail mid-keystroke; an async store
   would make the acute path worse than today). Rules, measured not assumed
   (draft-durability-status.md / 6a6ddff):

     - save on every `input`, no debounce;
     - restore only into a mounted element that declares its logical id —
       never fuzzy-match (wrong-box restore is worse than loss);
     - clear only on durable success via isDurable (close/blur/reject keep it);
     - a live box outranks storage (#118);
     - every storage call is try/catch — degrade to no-persistence, never a
       broken box;
     - cards key on the question TITLE (data-qid), not a positional index.

   logicalId = kind + ":" + scopeKey inside data.target. New key shape:
     dw:draft:v1:<target>:<logicalId>
   Dual-read of the pre-module keys so an existing browser draft is never
   orphaned by the extraction:
     card:<title>     ← dw:adraft:<target>:<title>
     composer:main    ← dw:draft:<target>
   On save through the new API the old key is removed after the new one is
   written (dual-read, not dual-write forever). Cross-tab (C1) and 30-day GC
   leave seams only — not built here. #263 receipt is isDurable's future
   body; today it prefers writeVerdict.landed when attached, else res.ok. */
const DraftStore = (() => {
  const tgt = () => (typeof data !== 'undefined' && data && data.target) || '';
  const id = (kind, scopeKey) => {
    if (!kind) return '';
    return kind + ':' + (scopeKey == null ? '' : String(scopeKey));
  };
  // primary key — design §1 storageKey; t first so legacy payload checks hold
  const v1Key = logicalId => {
    const t = tgt();
    return t && logicalId ? 'dw:draft:v1:' + t + ':' + logicalId : '';
  };
  // pre-module keys (still dual-read; string shapes kept for tests + migration)
  const legacyKey = logicalId => {
    const t = tgt();
    if (!t || !logicalId) return '';
    if (logicalId.indexOf('card:') === 0)
      return 'dw:adraft:' + t + ':' + logicalId.slice(5);
    if (logicalId === 'composer:main')
      return 'dw:draft:' + t;
    return '';
  };
  const parseRec = raw => {
    if (!raw) return null;
    let d = null;
    try { d = JSON.parse(raw); } catch (e) { return null; }
    if (!d || typeof d.t !== 'string' || !d.t) return null;
    return d;
  };
  const readRaw = logicalId => {
    const k1 = v1Key(logicalId);
    if (!k1) return null;
    try {
      const n = localStorage.getItem(k1);
      if (n) return { raw: n, from: 'v1', key: k1 };
      const lo = legacyKey(logicalId);
      if (lo) {
        const o = localStorage.getItem(lo);
        if (o) return { raw: o, from: 'legacy', key: lo };
      }
    } catch (e) { /* storage unavailable */ }
    return null;
  };
  function get(logicalId) {
    const hit = readRaw(logicalId);
    if (!hit) return null;
    const d = parseRec(hit.raw);
    if (!d) return null;
    return {
      v: d.v || 1, logicalId, project: tgt(), text: d.t,
      updatedAt: d.at || 0, meta: d.k ? { kindHint: d.k } : {},
      _from: hit.from, _key: hit.key
    };
  }
  function save(logicalId, text, meta) {
    const k1 = v1Key(logicalId); if (!k1) return;
    try {
      if (text) {
        const rec = { t: text };
        if (meta && meta.kindHint) rec.k = meta.kindHint;
        rec.v = 1;
        rec.at = Date.now();
        localStorage.setItem(k1, JSON.stringify(rec));
        // migrate: once the new key holds the truth, drop the old shape so a
        // second tab does not re-promote a cleared draft from legacy alone
        const lo = legacyKey(logicalId);
        if (lo) try { localStorage.removeItem(lo); } catch (e2) {}
      } else {
        localStorage.removeItem(k1);
        const lo = legacyKey(logicalId);
        if (lo) localStorage.removeItem(lo);
      }
    } catch (e) { /* storage unavailable; the live box is unaffected */ }
  }
  function restore(logicalId, el) {
    if (!logicalId || !el || el.value) return;  // live outranks (#118)
    const rec = get(logicalId);
    if (!rec || !rec.text) return;
    el.value = rec.text;
    if (el.dataset) el.dataset.draftId = logicalId;
  }
  function clear(logicalId) {
    const k1 = v1Key(logicalId); if (!k1) return;
    try {
      localStorage.removeItem(k1);
      const lo = legacyKey(logicalId);
      if (lo) localStorage.removeItem(lo);
    } catch (e) {}
  }
  /* receipt seam: prefer writeVerdict.landed (rejected 202 is res.ok true but
     not durable — E5b). Fall back to res.ok for call sites without _dwv.
     #263 second gate may replace this body later; consumers only call clear
     after isDurable says yes. */
  function isDurable(res) {
    if (!res) return false;
    if (res._dwv) return !!res._dwv.landed;
    return !!res.ok;
  }
  // bind: input→save, declare data-draft-id. No debounce. opts.meta() optional.
  function bind(el, logicalId, opts) {
    if (!el || !logicalId) return;
    el.dataset.draftId = logicalId;
    const onInput = () => {
      const meta = opts && typeof opts.meta === 'function' ? opts.meta() : null;
      save(logicalId, el.value, meta || undefined);
    };
    el.addEventListener('input', onInput);
    el.__dwDraftBound = { logicalId, onInput };
  }
  function unbind(el) {
    if (!el || !el.__dwDraftBound) return;
    el.removeEventListener('input', el.__dwDraftBound.onInput);
    delete el.__dwDraftBound;
  }
  // seams for later increments — no-op / stubs, not built here
  function forget(logicalId) { clear(logicalId); }
  function forgetProject() { /* retention increment */ }
  function gc() { /* 30-day idle GC — deferred with the store backend */ }
  function onRemote() { /* C1 offer-to-load — needs the store; seam only */ }
  return {
    id, bind, unbind, save, restore, clear, get, isDurable,
    forget, forgetProject, gc, onRemote,
    // test/guard seams: expose key builders without re-deciding shapes
    _v1Key: v1Key, _legacyKey: legacyKey
  };
})();
/* thin façade: existing answer-box call sites keep dwDraft.save(title, …).
   Routes through DraftStore so card and composer share one policy. */
const dwDraft = {
  save(title, value) {
    if (!title) return;
    DraftStore.save(DraftStore.id('card', title), value);
  },
  restore(title, el) {
    if (!title) return;
    DraftStore.restore(DraftStore.id('card', title), el);
  },
  clear(title) {
    if (!title) return;
    DraftStore.clear(DraftStore.id('card', title));
  }
};
/* Put a drafted answer back into every box a render just created. Runs AFTER
   the in-memory snapshot (`restoreCardState`) has had its say, so the more
   recent live state wins and storage is the backstop — which is the whole
   point: #118 carries text across a tick, this carries it across the reload
   #118 cannot. A box the snapshot already filled is a live box, and storage
   does not overwrite it (dwDraft.restore's `el.value` guard). Called from
   every DOM commit that recreates cards — `setContent` and the review-dock
   `replaceWith` — not only at load, because a box that reappears on a tick
   needs its draft back just as much as one that reappears on a reload. */
function restoreAnswerDrafts() {
  document.querySelectorAll('.qa[data-qid]').forEach(card => {
    let title = null;
    try { title = decodeURIComponent(card.dataset.qid); } catch (e) { return; }
    if (!title) return;
    const ta = card.querySelector('textarea[id^="qi"]');
    if (!ta) return;
    const before = ta.value;
    dwDraft.restore(title, ta);
    // #177: a draft restored into a fresh box must size that box, snapped —
    // the reload path `restoreCardState` does not reach (no in-memory snapshot
    // survived it), so without this a restored multi-line draft sits in a
    // 2-row box until the first keystroke.
    if (ta.value && ta.value !== before) fitText(ta, false);
  });
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
    if (currentDock && nextDock) {
      // THE FADE STATE RIDES ACROSS THE SWAP, like the scroll and the draft
      // do (#326). The depths TRANSITION, so they are only ever allowed to
      // move on a gesture — and a poll is not one. The server's markup carries
      // neither class, so a fresh dock resolves the full 24px first and lands
      // on its real value one style pass later: for half a second after every
      // tick, both edges of a question he is only reading dimmed and lifted.
      // The scroll position is restored below, so the state that was true
      // before this swap is the state that is true after it; syncDockFade
      // still runs once that restore has happened and corrects the one case
      // where it is not — content that grew, which IS a change and does move.
      for (const c of ['attop', 'atend'])
        nextDock.classList.toggle(c, currentDock.classList.contains(c));
      currentDock.replaceWith(nextDock);
    } else setContent(html);
    paintIndicators(true); ages();
    // the new #qdock is a fresh node, so a half-typed answer is gone unless a
    // draft is put back into it — the review-dock reload loss he reported (#269).
    restoreAnswerDrafts();
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
/* #462 — one-shot atmospheric arrival for the staleness row's remedy, present
   only when the page is behind. The row is re-rendered through innerHTML
   every tick, so like revealNewOpenAsks the .dreamin start pose is applied
   ONLY on the genuine current→behind transition (the moment the page just
   fell behind), never on first paint (which settles visible), never replayed
   on a tick where the affordance was already present, and never under
   reduced motion (function, no pose). Behind→current is a redeploy = a
   generation change = a full reload, so there is no departure to animate: the
   affordance leaves with the page that held it. window.__dwSkipStaleArrival
   is the guard's RED inject point, mirroring __dwSkipOpenAskArrival. */
let knownStaleAction = null;
function revealStaleAction() {
  if (view.name !== 'dashboard') { knownStaleAction = null; return; }
  const node = document.querySelector('.gservact');
  const now = !!node;
  if (knownStaleAction === null || window.__dwSkipStaleArrival) {
    if (node) node.classList.remove('dreamin');
    knownStaleAction = now;
    return;
  }
  if (now && !knownStaleAction) {
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!reduce && node) {
      node.classList.add('dreamin');
      void node.offsetWidth;                    // commit the start pose
      requestAnimationFrame(() => {
        if (node.isConnected) node.classList.remove('dreamin');
      });
    }
  }
  knownStaleAction = now;
}
function setContent(html) {
  document.getElementById('view').innerHTML = html;
  // before anything measures: the review pane's height is a measurement, and
  // crossfade reads the dock's rect on the very next line after setContent.
  fitReview();
  // fresh groups carry a 0-width indicator, so land it rather than let it
  // slide up out of nothing (the enter-snap rule)
  paintIndicators(true);
  ages();
  revealNewOpenAsks();
  revealStaleAction();
  // #462: the remedy is re-created by innerHTML; re-apply arm/running classes
  // and label so a mid-arm tick does not reset the control to idle copy.
  paintStaleDeployUI();
  revealReviewMods();
  revealReviewDecisions();  // #289: decision-token arrival, same idiom
  revealQuestionUpdates();  // #473: updated-ago arrival, after ages() hides dishonest ones
  // #290: innerHTML destroys the arm bar nodes; resume shared pending (or
  // re-sync the committed selection) without inventing a new deadline.
  syncRunModeFromData();
  // #445: same arm-resume idiom for the three-axis posture control.
  syncPostureFromData();
  // #454: rolled questions re-roll here, on the same argument as the
  // drafts below — every render commits through this seam, and the tick's
  // regroups measure AFTER it, so a kept roll invents no travel.
  restoreRolls();
  // every navigate and every non-review tick commits through here, so this is
  // the one place that puts a drafted answer back after the box is recreated —
  // the in-memory snapshot does the same for a tick, but only storage survives
  // the reload he reported (#269). Runs before paint, so the text is part of
  // the first frame rather than arriving into an empty box.
  restoreAnswerDrafts();
  // #459: #askbox is recreated with the answers form; re-bind + restore from
  // storage (after any in-memory snapshot the tick will still overlay).
  bindAskDraft();
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
    // HOW FAR HE HAS READ is his too (#305). On /review the question's body is
    // the scroller (#326 — the card holds the answer box, which must not fade
    // with the text), and the tick replaces the whole dock — so a question he
    // had scrolled halfway through would snap back to its first line every two
    // seconds, which is #118 with reading in place of typing.
    const sc = qaScroller(card);
    const read = sc ? sc.scrollTop : 0;
    // #479: a destination-MODE switch is something he did too, and it lives
    // only in this node — the group renders at the card's default, so any
    // other mode is his click. A tick that lands between the click and the
    // first keystroke otherwise re-renders the DEFAULT destination and
    // silently re-aims words he has not typed yet.
    const modeHis = comp && comp.dataset.mode !==
      qaDefaultMode(card.classList.contains('open') ? 'open' : 'awaiting');
    if (!typed && !opened && !read && !modeHis) return; // he has done nothing
    m.set(card.dataset.qid, {
      open: dets, read,
      value: typed ? ta.value : null, mode: comp && comp.dataset.mode,
      focus: ta === act,
      start: typed ? ta.selectionStart : 0, end: typed ? ta.selectionEnd : 0,
      dir: typed ? ta.selectionDirection : 'none',
      scroll: typed ? ta.scrollTop : 0,
      // #177's box height is re-fit from the restored content (`fitText` in
      // restoreCardState), so it is not carried here — recomputing is the same
      // value and cannot drift from the content the snapshot also restored.
    });
  });
  return m;
}
/* PUT A SCROLL OFFSET BACK, AND CHECK THAT IT LANDED — `refocus`'s rule
   (#179) applied to the other thing a restore hands back silently.

   A `scrollTop` assigned to a node the swap is one statement old is clamped
   to zero: as far as the assignment can see the fresh box has no overflow
   yet. It reports nothing in either direction, and whether it happens at all
   depends on whether something between the swap and here already forced a
   layout — so it is a bug with an unreliable lifetime (#198's shape), which
   is exactly the kind a guard passes over. Reading the value back both
   detects it and forces the layout that fixes it.

   Deliberately unguarded, and said out loud rather than left implied: the
   browser guard's tick check covers the FEATURE (his place in the question
   survives), and it stays green with the retry removed, because on that run
   something else had already forced the layout. A check that cannot fail for
   its stated cause sends the next reader to the wrong file. The mechanism was
   measured directly instead — assigning 209 to a just-swapped card reads back
   0, and reads back 209 with the layout forced first. */
function putScroll(el, top) {
  if (!el || !top) return;               // re-fill only, never clear
  el.scrollTop = top;
  if (el.scrollTop !== top) el.scrollTop = top;   // the read above laid it out
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
    // how far he had READ into the question (#305) — see putScroll
    putScroll(qaScroller(card), s.read);
    const comp = card.querySelector('.qcompose');
    // the mode is WHERE THE TEXT GOES: a re-render must never silently
    // redirect it — and it rides even with no text yet, because the click
    // that set it is his whether or not a keystroke has followed (#479), so
    // it is restored BEFORE the no-text early return below. setCardMode
    // declines a mode the new state cannot accept.
    setCardMode(comp, s.mode, true);
    if (s.value === null) return;
    const ta = comp && comp.querySelector('textarea');
    if (!ta) return;                       // the state stopped offering a box
    ta.value = s.value;
    // #177: re-fit the box to its restored content, SNAPPED — the tick
    // re-creates the box at its floor every ~2s, so an animated fit here would
    // re-grow it under him on every tick while he is mid-thought. The height
    // the snapshot carried is now derived from the content rather than trusted,
    // which is the same preference as letting `fitText` recompute on input.
    fitText(ta, false);
    putScroll(ta, s.scroll);
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
/* #477: re-opening is not enough when the tick catches the gesture ITSELF.
   `el.open = true` on the fresh node arrives at full height in ONE frame, and
   if the section was part-way through its 850ms open when the tick fired, that
   frame replaces the travel with a teleport — #196's snap re-entering at the
   surface #196 fixed, every time a tick happens to land inside the gesture.

   What it was mid-gesture is already legible on the page and needs no separate
   bookkeeping: `travelCard` owns `height` while it runs, so a non-empty inline
   `height` IS the tell, and it cannot go stale because `travelCard` clears it
   itself at CARD_MS + 150. The interrupted height is just the old node's rect
   at snapshot time. */
function snapshotFolds() {
  const m = new Map();
  document.querySelectorAll('details[data-keep]').forEach(el =>
    m.set(el.dataset.keep, {
      open: el.open,
      travelling: el.open && el.style.height !== '',
      height: el.getBoundingClientRect().height,
    }));
  return m;
}
function restoreFolds(saved) {
  if (!saved) return;
  document.querySelectorAll('details[data-keep]').forEach(el => {
    const was = saved.get(el.dataset.keep);
    if (!was || !was.open) return;
    el.open = true;
    if (!was.travelling || rmr) return;
    // resume the interrupted open on the node that now exists, through the
    // SAME two calls the summary's own handler uses — the height travels from
    // where it got to, the body eases in behind it. Only the height differs
    // from `now`, so the section does not move: it was never going to.
    const now = el.getBoundingClientRect();
    travelCard(el, { left: now.left, top: now.top, height: was.height }, now, false);
    revealBody(el);
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
  // Two beats (#277): dissolve in place first (.pregone, 180ms), then leave
  // (.gone, 700ms). The liquify/blur lives in an SVG mist filter (#departMist)
  // driven per-frame from rAF — the same idiom as the route dissolve's
  // #dissolveOut — so the ghost hazes and liquifies rather than just CSS-blurring.
  // #453: the field is the same cached feImage texture as the route dissolve,
  // drifted by feOffset instead of a baseFrequency ramp — a departure ghost is
  // small, but feTurbulence re-rasterizes per frame whatever the area (#449).
  // Removing .pregone restores .qaghost's .7s transition for the departure leg.
  // Commits are excluded: their gesture is the grow-and-fall (line 677), and
  // they keep CSS blur(6px) instead of the SVG filter.
  if (node.classList.contains('commit')) {
    node.classList.add('gone');
  } else if (!mistTexture()) {
    node.classList.add('pregone');     // no canvas: CSS-blur departure only
    setTimeout(() => { node.classList.remove('pregone'); node.classList.add('gone'); }, 180);
  } else {
    const dm = document.querySelector('#departMist feDisplacementMap');
    const bl = document.querySelector('#departMist feGaussianBlur');
    const of = document.querySelector('#departMist feOffset');
    const smooth = x => x * x * (3 - 2 * x);
    const t0m = performance.now();
    const MIST_MS = 880;               // 180ms pregone + 700ms gone
    // drift bounded by the ghost's own size: the offset must never push the
    // tiled field's edge into sampling reach (region margin − scale/2).
    const drift = Math.max(0, Math.min(8, rect.width * 0.25 - 8, rect.height * 0.25 - 8));
    node.style.filter = 'url(#departMist)';
    node.classList.add('pregone');
    (function mistStep(now) {
      const u = Math.min(1, (now - t0m) / MIST_MS);
      const e = smooth(u);
      if (dm) dm.setAttribute('scale', (e * 14).toFixed(2));
      if (bl) bl.setAttribute('stdDeviation', (e * 4.5).toFixed(2));
      if (of) {                        // the field flows up as it liquifies,
        of.setAttribute('dx', (e * drift * 0.6).toFixed(1));  // rising with
        of.setAttribute('dy', (-e * drift).toFixed(1));       // the ghost
      }
      if (u < 1 && node.isConnected) requestAnimationFrame(mistStep);
    })(performance.now());
    setTimeout(() => {
      node.classList.remove('pregone');
      node.classList.add('gone');
    }, 180);
  }
  setTimeout(() => node.remove(), 1050);
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
/* `.qbody` is looked THROUGH, never at (#326). It is the review dock's
   scrollport and nothing anywhere else — `display:contents`, no box — so a
   ghost cloned from it has no rect and a `.qreveal` transition on it has
   nothing to animate. The pieces that arrive and depart are its children, and
   they are the same list this returned before the wrapper existed. */
function cardBody(el, toggled) {
  const root = (toggled && el.contains(toggled)) ? toggled
             : (el.querySelector(':scope > .qfold') || el);
  return [...root.children]
    .flatMap(c => c.classList.contains('qbody') ? [...c.children] : [c])
    .filter(c => c.tagName !== 'SUMMARY' && !c.classList.contains('qt'));
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
/* ── #454: rolling an open question up to the top of its scroll ─────────
   His words: "the size of each collapsed question should be at least like
   5-6 lines ... more like a card or the top of a rolled up scroll." The
   floor is the whole design — a one-line collapse is a title list, and a
   title alone does not say whether an entry still needs him — so it is a
   line COUNT times the RENDERED line height (lineHeightOf's measured
   probe), never a pinned pixel constant (#441's split-literal lesson).

   The gesture is the card fold's own (#111/#169): snapshot, toggle,
   regroup — the height travels, the departing slice ghosts below the new
   edge, the arriving body eases in. No second way to move a card.
   `toggled` stays null so nestedToggle reads false and the card-level
   clone is what ghosts: what leaves IS this card's bottom slice, which is
   exactly what that clone clipped below the new height says.

   State is the question's title identity (data-qid), persisted to the
   dw-ui IndexedDB store and pinged across tabs through the standing
   'storage'-event idiom — "persisted to IndexedDB and kept in sync like
   other ui state". rolledQids is this page's truth between the two: the
   click writes all three, the storage event and the boot read keep the
   set current, and restoreRolls re-applies it inside setContent — the one
   seam navigate and tick both commit through — so neither a tick nor a
   route swap can unroll what he rolled, nor hold rolled what another tab
   unrolled. */
const ROLL_LINES = 5.5;          // the 5-6 line floor, in RENDERED lines
const rolledQids = new Set();    // decoded title identities
function rollHeight(card) {
  const probe = card.querySelector('.qbody .md p') ||
                card.querySelector('.qbody .qt') || card;
  return Math.ceil(lineHeightOf(probe) * ROLL_LINES);
}
function setRolled(card, rolling) {
  card.classList.toggle('rolled', rolling);
  const btn = card.querySelector('button.qroll');
  if (btn) {
    btn.setAttribute('aria-expanded', String(!rolling));
    btn.textContent = rolling ? 'unroll' : 'roll up';
  }
  if (rolling) card.style.setProperty('--rollh', rollHeight(card) + 'px');
  else card.style.removeProperty('--rollh');
}
/* re-apply the truth after ANY render. Landing inside setContent means
   landing before the tick's regroups MEASURE: a card re-rendered unrolled
   and re-rolled here has the small rect it had at snapshot, so no travel
   is invented for a state nothing changed. The dock's card is the reading
   surface — it is never rolled, and its button is not offered. */
function restoreRolls() {
  if (!rolledQids.size && !document.querySelector('.qa.rolled')) return;
  document.querySelectorAll('.qa[data-qid]').forEach(card => {
    if (card.closest('.qdock')) return;
    let title = null;
    try { title = decodeURIComponent(card.dataset.qid); } catch (e) { return; }
    const want = rolledQids.has(title);
    if (want !== card.classList.contains('rolled')) setRolled(card, want);
  });
}
function rollPingKey() {
  return (data && data.target) ? ('dw:qroll:' + data.target) : null;
}
/* the gesture never waits on storage: the click writes this page's set
   first, then the IndexedDB record a reload reads back (raced, uiPut),
   then the ping other tabs follow (best-effort). */
function persistRoll(title, rolling) {
  uiPut('qroll:' + title, rolling);
  const k = rollPingKey();
  if (k) try {
    localStorage.setItem(k,
      JSON.stringify({ qid: title, rolled: rolling, at: Date.now() }));
  } catch (e) {}
}
function applyRoll(card, rolling) {
  if (rmr) { setRolled(card, rolling); return; }
  const before = snapshotCards(QA_LIST);
  setRolled(card, rolling);
  regroupCards(before, null, QA_LIST);
}
function toggleRoll(card) {
  let title = null;
  try { title = decodeURIComponent(card.dataset.qid); } catch (e) { return; }
  if (!title) return;
  const rolling = !card.classList.contains('rolled');
  if (rolling) rolledQids.add(title); else rolledQids.delete(title);
  persistRoll(title, rolling);
  applyRoll(card, rolling);
}
addEventListener('click', e => {
  if (!e.target.closest) return;
  const btn = e.target.closest('button.qroll');
  if (!btn) return;
  const card = btn.closest('.qa[data-qid]');
  if (!card || card.closest('.qdock')) return;
  e.preventDefault();
  toggleRoll(card);
});
/* another tab rolled or unrolled: adopt into the set and re-apply through
   the SAME gesture — a card rolling in the corner of his eye still
   arrives and departs rather than appearing, because the ping is a state
   change he can see. */
window.addEventListener('storage', e => {
  if (!e.key || e.key !== rollPingKey() || !e.newValue) return;
  let m = null;
  try { m = JSON.parse(e.newValue); } catch (er) { return; }
  if (!m || typeof m.qid !== 'string') return;
  if (m.rolled) rolledQids.add(m.qid); else rolledQids.delete(m.qid);
  const card = document.querySelector(
    '.qa[data-qid="' + encodeURIComponent(m.qid) + '"]');
  if (card && !card.closest('.qdock') &&
      !!m.rolled !== card.classList.contains('rolled'))
    applyRoll(card, !!m.rolled);
});
/* boot: the store is the truth a reload reads back. Async on purpose —
   first paint never waits on IndexedDB (a roll restored a beat late is a
   restore; a page that waited on storage is the failure the raced write
   already refuses to risk). ensureData first: the database's name is the
   project's. */
async function loadRolls() {
  await ensureData();
  const recs = await uiAll();
  if (!recs) return;
  recs.forEach(r => {
    if (r && typeof r.k === 'string' && r.k.indexOf('qroll:') === 0) {
      const t = r.k.slice(6);
      if (r.v) rolledQids.add(t); else rolledQids.delete(t);
    }
  });
  restoreRolls();
}
loadRolls();
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
    m.set(el.dataset.bk + '/' + el.dataset.series, {
      h: el.getBoundingClientRect().height,
      // #417 c3: weight travels with height so a commits-only change does
      // not snap. parseFloat of computed border-top-width is the px value.
      cap: parseFloat(getComputedStyle(el).borderTopWidth) || 0,
    }));
  return m;
}
function regroupBars(before) {
  if (rmr || !before || !before.size) return;
  document.querySelectorAll('.bd .bdbar[data-bk]').forEach(el => {
    const was = before.get(el.dataset.bk + '/' + el.dataset.series);
    const nowH = el.getBoundingClientRect().height;
    const nowCap = parseFloat(getComputedStyle(el).borderTopWidth) || 0;
    if (was === undefined) {          // a new bucket: snap, then ease in
      el.classList.add('dreamin');
      requestAnimationFrame(() => el.classList.remove('dreamin'));
      return;
    }
    const hMoved = Math.abs(was.h - nowH) >= 1;
    const capMoved = el.classList.contains('bdlevel') &&
                     Math.abs(was.cap - nowCap) >= 0.5;
    if (!hMoved && !capMoved) return;
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
    const capEnd = el.style.borderTopWidth;
    el.style.transition = 'none';     // the enter-snap rule, again
    // border-box for `travelCard`'s reason: `now` came from
    // getBoundingClientRect, which is a BORDER box, and `.bdlevel` is a 2px
    // rule with no fill — left content-box the travel aims 2px past where it
    // ends and snaps when the percentage comes back.
    el.style.boxSizing = 'border-box';
    if (hMoved) el.style.height = was.h + 'px';
    if (capMoved) el.style.borderTopWidth = was.cap + 'px';
    void el.offsetWidth;
    el.style.transition = 'height .85s cubic-bezier(.32,.1,.2,1),' +
      'border-top-width .85s cubic-bezier(.32,.1,.2,1)';
    if (hMoved) el.style.height = nowH + 'px';
    if (capMoved) el.style.borderTopWidth = nowCap + 'px';
    setTimeout(() => {
      el.style.transition = ''; el.style.boxSizing = '';
      el.style.height = pct;
      // restore the rendered width (inline style from bdbar) rather than
      // clearing it — clearing would snap back to the CSS default 2px.
      if (capEnd) el.style.borderTopWidth = capEnd;
      else if (capMoved) el.style.borderTopWidth = nowCap + 'px';
    }, CARD_MS + 150);
  });
}
/* #487 — cycle the burndown's bucket width. The ladder is BURN_STEP_ORDER
   (same seconds as the server's BURN_STEPS). Preference rides localStorage
   keyed by target so a reload keeps the reading he picked; null means the
   server auto-picks. Fetching /data.json?burn_step=N is the only write
   surface — collect re-buckets, nothing else changes. */
function burnStepStorageKey() {
  try {
    return 'dw:burn-step:' + ((data && data.target) || '');
  } catch (e) { return 'dw:burn-step'; }
}
function loadBurnStepPref() {
  try {
    const v = parseInt(localStorage.getItem(burnStepStorageKey()), 10);
    if (BURN_STEP_ORDER.indexOf(v) >= 0) return v;
  } catch (e) {}
  return null;
}
function dataJsonUrl() {
  const s = burnStepPref;
  return (s && BURN_STEP_ORDER.indexOf(s) >= 0)
    ? '/data.json?burn_step=' + s : '/data.json';
}
async function cycleBurnStep(back) {
  const cur = (data && data.burndown && data.burndown.step)
    || BURN_STEP_ORDER[0];
  let i = BURN_STEP_ORDER.indexOf(cur);
  if (i < 0) i = 0;
  /* #489: plain click walks coarse→fine (his order: daily → 4-hourly →
     hourly → wrap to every-four-weeks); shift-click reverses. The
     ladder itself stays fine→coarse — click decrements, shift
     increments. */
  const L = BURN_STEP_ORDER.length;
  const next = BURN_STEP_ORDER[(i + (back ? 1 : L - 1)) % L];
  burnStepPref = next;
  try { localStorage.setItem(burnStepStorageKey(), String(next)); }
  catch (e) {}
  try {
    const wasBurn = burnKey(data);
    const bdHover = snapshotBdHover();   // #494: step cycle is also a swap
    setData(await (await fetch(dataJsonUrl())).json());
    const burnBefore = (burnKey(data) !== wasBurn) ? snapshotBars() : null;
    if (view && view.name === 'dashboard') {
      const html = await buildCurrent();
      setLiveContent(html);
      if (burnBefore) regroupBars(burnBefore);
      restoreBdHover(bdHover);
    }
  } catch (e) {}
}
addEventListener('click', e => {
  const btn = e.target.closest && e.target.closest('.bdstep');
  if (!btn) return;
  e.preventDefault();
  cycleBurnStep(e.shiftKey);
});

/* #499 — column-count limit. Client-only: no server state, no endpoint.
   localStorage per target (see burnLimitPref note above). Invalid input
   is refused quietly — re-render restores the previous value; no toast
   idiom exists on this panel. */
function burnLimitStorageKey() {
  try {
    return 'dw:burn-limit:' + ((data && data.target) || '');
  } catch (e) { return 'dw:burn-limit'; }
}
function loadBurnLimitPref() {
  try {
    const raw = localStorage.getItem(burnLimitStorageKey());
    if (raw == null || raw === '') return null;
    const v = parseInt(raw, 10);
    if (!Number.isFinite(v)) return null;
    return v;
  } catch (e) { return null; }
}
function ensureBurnLimit() {
  if (_burnLimitDidLoad) return;
  _burnLimitDidLoad = true;
  const v = loadBurnLimitPref();
  if (v !== null) burnLimitPref = v;
}
/* Active slice size: 0 = all (no slice); else 1..BURN_LIMIT_CAP. */
function activeBurnLimit() {
  ensureBurnLimit();
  if (burnLimitPref === null) return BURN_LIMIT_DEFAULT;
  if (!Number.isFinite(burnLimitPref) || burnLimitPref <= 0) return 0;
  return Math.min(BURN_LIMIT_CAP, Math.max(1, Math.floor(burnLimitPref)));
}
function displayBurnLimitValue() {
  ensureBurnLimit();
  if (burnLimitPref === null) return BURN_LIMIT_DEFAULT;
  if (!Number.isFinite(burnLimitPref)) return BURN_LIMIT_DEFAULT;
  if (burnLimitPref <= 0) return 0;
  return Math.min(BURN_LIMIT_CAP, Math.floor(burnLimitPref));
}
async function rerenderBurnLimit() {
  if (!view || view.name !== 'dashboard' || !data) return;
  try {
    const bdHover = snapshotBdHover();
    const html = await buildCurrent();
    setLiveContent(html);
    restoreBdHover(bdHover);
  } catch (e) {}
}
function applyBurnLimit(raw) {
  /* Refuse invalid quietly: non-numeric / empty leaves the prior pref
     and restores the input's displayed value (no toast idiom).
     <=0 → all/max (stored as 0). >cap → clamp to cap. */
  if (raw === '' || raw == null) {
    const inp = document.querySelector('.bdlimit-in');
    if (inp) inp.value = String(displayBurnLimitValue());
    return;
  }
  const n = parseInt(String(raw).trim(), 10);
  if (!Number.isFinite(n)) {
    const inp = document.querySelector('.bdlimit-in');
    if (inp) inp.value = String(displayBurnLimitValue());
    return;
  }
  const store = n <= 0 ? 0 : Math.min(BURN_LIMIT_CAP, n);
  burnLimitPref = store;
  _burnLimitDidLoad = true;
  try { localStorage.setItem(burnLimitStorageKey(), String(store)); }
  catch (e) {}
  rerenderBurnLimit();
}
function resetBurnLimit() {
  burnLimitPref = null;               // back to default 28
  _burnLimitDidLoad = true;
  try { localStorage.removeItem(burnLimitStorageKey()); }
  catch (e) {}
  rerenderBurnLimit();
}
addEventListener('change', e => {
  const inp = e.target && e.target.closest && e.target.closest('.bdlimit-in');
  if (!inp) return;
  applyBurnLimit(inp.value);
});
addEventListener('keydown', e => {
  const inp = e.target && e.target.closest && e.target.closest('.bdlimit-in');
  if (!inp) return;
  if (e.key === 'Enter') { e.preventDefault(); inp.blur(); }
});
addEventListener('click', e => {
  const btn = e.target && e.target.closest && e.target.closest('.bdlimit-reset');
  if (!btn) return;
  e.preventDefault();
  resetBurnLimit();
});

/* #417 per-column hover/focus readout. Shows open + arrived + landed +
   commits so the level line's two meanings (height = open, weight =
   commits) are never left implied. The tip is an arrival: rundesc's
   atmospheric pose → ease-in / depart, never a native title blink.
   Height of .bd is unchanged — the tip floats. Accent is not spent. */
let bdtipCol = null;
let bdtipHideTimer = null;
function bdtipReduced() {
  try { return matchMedia('(prefers-reduced-motion: reduce)').matches; }
  catch (e) { return false; }
}
function bdtipText(col) {
  const stamp = col.dataset.stamp || '';
  const open = col.dataset.open;
  const arrived = col.dataset.arrived;
  const landed = col.dataset.landed;
  const commits = col.dataset.commits;
  // open named first: he asked "which I think is what the line is, right?"
  // — answer it before naming the weight's meaning.
  return `<span class="bdnum">${esc(open)}</span> open · ` +
    `${esc(arrived)}↑ ${esc(landed)}↓ · ` +
    `<span class="bdnum">${esc(commits)}</span> commit` +
    `${commits === '1' ? '' : 's'}` +
    (stamp ? ` · ${esc(stamp)}` : '');
}
function hideBdTip(immediate) {
  const tip = document.querySelector('.bd .bdtip');
  if (!tip || tip.hidden) { bdtipCol = null; return; }
  if (bdtipHideTimer) { clearTimeout(bdtipHideTimer); bdtipHideTimer = null; }
  const rm = !!immediate || bdtipReduced();
  const finish = () => {
    tip.hidden = true; tip.classList.remove('depart', 'pose');
    tip.innerHTML = ''; bdtipCol = null;
  };
  if (rm) { finish(); return; }
  tip.classList.remove('pose');
  tip.classList.add('depart');
  bdtipHideTimer = setTimeout(finish, 450);
}
/* settle=true: land fully visible with no pose replay. Used by #494's
   rearm across the tick re-render — from his POV the tip never left, so
   re-posing every two seconds would be motion with nothing behind it. */
function showBdTip(col, settle) {
  const bd = col && col.closest && col.closest('.bd');
  const tip = bd && bd.querySelector('.bdtip');
  if (!tip || !col || !col.dataset || col.dataset.open === undefined) return;
  if (bdtipHideTimer) { clearTimeout(bdtipHideTimer); bdtipHideTimer = null; }
  const same = bdtipCol === col && !tip.hidden;
  bdtipCol = col;
  tip.innerHTML = bdtipText(col);
  if (same || settle) {
    tip.hidden = false;
    tip.classList.remove('depart', 'pose');
    return;
  }
  const rm = bdtipReduced();
  tip.hidden = false;
  tip.classList.remove('depart');
  if (rm) { tip.classList.remove('pose'); return; }
  // enter-snap: pose at opacity 0, reflow, then ease in
  tip.classList.add('pose');
  void tip.offsetWidth;
  requestAnimationFrame(() => tip.classList.remove('pose'));
}
// pointer + focus, delegated — columns are rebuilt every tick
addEventListener('pointerover', e => {
  const col = e.target.closest && e.target.closest('.bdnet .bdcol[data-open]');
  if (!col) return;
  lastBdPtr = { x: e.clientX, y: e.clientY };
  showBdTip(col);
  bdinspSchedule(col);             // #298: a hover that dwells inspects
});
/* keep the last pointer position while a hover/pin is live so a tick can
   rearm against the column still under the hand (#494), not a stale t0
   that a step-cycle may have retired. */
addEventListener('pointermove', e => {
  if (bdtipCol || bdinspCol || bdinspPin)
    lastBdPtr = { x: e.clientX, y: e.clientY };
}, { passive: true });
addEventListener('pointerout', e => {
  const col = e.target.closest && e.target.closest('.bdnet .bdcol[data-open]');
  if (!col) return;
  const to = e.relatedTarget;
  if (to && col.contains(to)) return;
  if (to && to.closest && to.closest('.bdnet .bdcol[data-open]') === col) return;
  // leave the tip up while focus stays on the column
  if (document.activeElement === col) return;
  hideBdTip(false);
  bdinspCancel();
  if (!bdinspPin) hideBdInsp(false);   // a pinned (tapped) reading stays
});
addEventListener('focusin', e => {
  const col = e.target.closest && e.target.closest('.bdnet .bdcol[data-open]');
  if (!col) return;
  showBdTip(col);
  showBdInsp(col);   // #298: focus is already deliberate — no dwell
});
addEventListener('focusout', e => {
  const col = e.target.closest && e.target.closest('.bdnet .bdcol[data-open]');
  if (!col) return;
  const to = e.relatedTarget;
  if (to && to.closest && to.closest('.bdnet .bdcol[data-open]')) return;
  hideBdTip(false);
  bdinspCancel();
  if (!bdinspPin) hideBdInsp(false);
});
/* #298 — the column inspector: the richer reading a DELIBERATE look gets.
   The #417 glance tip answers a passing hover; the inspector answers a
   hover that DWELLS (700ms), a keyboard focus (immediate — focus is
   already deliberate), or a tap (pinned until dismissed). Same seam, same
   arrival idiom, same data attributes — never a second hover. */
let bdinspCol = null, bdinspPin = false, bdinspDwell = null;
let bdinspHideTimer = null;
const BD_DWELL = 700;
function bdstampFull(t) {
  const d = new Date(t * 1000);
  return d.toLocaleDateString(undefined,
    { weekday: 'short', day: 'numeric', month: 'short' }) + ' ' +
    d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}
function bdinspHTML(col) {
  const d = col.dataset;
  const t0 = +d.t0, t1 = +d.t1, now = Date.now() / 1000;
  const iv = bdstampFull(t0) + ' – ' + (t1 > now ? 'now' : bdstampFull(t1));
  // coverage the geometry cannot say: a period with no ledger commit
  // CARRIES the previous level; the current period is still arriving.
  const cov = [d.covered === '1' ? 'measured'
                                : 'level carried — no ledger commits'];
  if (t1 > now) {
    cov.push('period in progress');
    /* #498: % of this open period elapsed, from the column's real t0/t1
       (not from column index). Clamped to 0..100 so a clock skew past the
       bounds cannot invent a figure the interval itself forbids. */
    const span = t1 - t0;
    if (span > 0) {
      const pct = Math.max(0, Math.min(100,
        Math.round(100 * (now - t0) / span)));
      cov.push(pct + '% elapsed');
    }
  }
  return `<div class="bdin-iv">${esc(iv)}</div>` +
    `<div><span class="bdnum">${esc(d.open)}</span> open · ` +
    `${esc(d.arrived)} arrived · ${esc(d.landed)} landed · ` +
    `<span class="bdnum">${esc(d.commits)}</span> commit` +
    `${d.commits === '1' ? '' : 's'}</div>` +
    `<div class="bdin-cov">${esc(cov.join(' · '))}</div>`;
}
function bdinspLay(bd, col, el) {
  /* #487: consistent pin, not column-centred. RHS of the panel when the
     inspector's measured width fits in the right half (room derived from
     rendered layout — no guessed px breakpoint); otherwise above the
     chart. When above, also above .bdtip so the glance stats line and the
     details never overlap. Same pose/depart arrival; only the resting
     slot changes.
     #498 geometry: pin max-width to the panel in px before measuring so
     a long coverage line (…period in progress · N% elapsed) cannot make
     offsetWidth exceed the panel, and clamp left so left+width stays
     inside — the border-box CSS is the real fix; this is the placement
     half of the same guarantee. */
  const bdr = bd.getBoundingClientRect();
  const track = bd.querySelector('.bdnet');
  const tr = track ? track.getBoundingClientRect() : bdr;
  const tip = bd.querySelector('.bdtip');
  const tipOn = tip && !tip.hidden;
  const tipR = tipOn ? tip.getBoundingClientRect() : null;
  el.style.maxWidth = bdr.width + 'px';
  const w = el.offsetWidth, h = el.offsetHeight;
  const pad = 4;
  // room = inspector fits entirely in the right half of the panel
  const hasRoom = (w + pad * 2) <= (bdr.width / 2);
  el.dataset.bdslot = hasRoom ? 'rhs' : 'above';
  // horizontal clamp: never past the panel edges
  const clampL = left => Math.max(0, Math.min(left, Math.max(0, bdr.width - w)));
  if (hasRoom) {
    el.style.left = clampL(bdr.width - w) + 'px';
    el.style.right = 'auto';
    // below the tip when it is up (no overlap); otherwise above the track
    let top = tr.top - bdr.top - h - pad;
    if (tipR) {
      const tipBot = tipR.bottom - bdr.top;
      top = Math.max(top, tipBot + pad);
    }
    el.style.top = top + 'px';
  } else {
    // centred horizontally, fully above chart AND above the tip line
    el.style.left = clampL((bdr.width - w) / 2) + 'px';
    el.style.right = 'auto';
    let top = tr.top - bdr.top - h - pad;
    if (tipR) {
      const tipTop = tipR.top - bdr.top;
      top = Math.min(top, tipTop - h - pad);
    }
    el.style.top = top + 'px';
  }
}
function bdinspCancel() {
  if (bdinspDwell) { clearTimeout(bdinspDwell); bdinspDwell = null; }
}
function hideBdInsp(immediate) {
  const el = document.querySelector('.bd .bdinsp');
  bdinspCancel();
  if (!el || el.hidden) { bdinspCol = null; bdinspPin = false; return; }
  if (bdinspHideTimer) { clearTimeout(bdinspHideTimer); bdinspHideTimer = null; }
  const finish = () => {
    el.hidden = true; el.classList.remove('depart', 'pose');
    el.innerHTML = ''; bdinspCol = null; bdinspPin = false;
  };
  if (!!immediate || bdtipReduced()) { finish(); return; }
  el.classList.remove('pose');
  el.classList.add('depart');
  bdinspHideTimer = setTimeout(finish, 450);
}
/* settle=true: same contract as showBdTip's settle — rearm across a tick
   without replaying the arrival pose (#494). */
function showBdInsp(col, settle) {
  const bd = col && col.closest && col.closest('.bd');
  const el = bd && bd.querySelector('.bdinsp');
  if (!el || !col.dataset || col.dataset.t0 === undefined) return;
  bdinspCancel();
  if (bdinspHideTimer) { clearTimeout(bdinspHideTimer); bdinspHideTimer = null; }
  const same = bdinspCol === col && !el.hidden;
  bdinspCol = col;
  el.innerHTML = bdinspHTML(col);
  el.hidden = false;               // visible before measuring
  bdinspLay(bd, col, el);
  if (same || settle) { el.classList.remove('depart', 'pose'); return; }
  el.classList.remove('depart');
  if (bdtipReduced()) { el.classList.remove('pose'); return; }
  el.classList.add('pose');        // enter-snap, then ease in (#417 idiom)
  void el.offsetWidth;
  requestAnimationFrame(() => el.classList.remove('pose'));
}
/* #494 — carry hover/pin across the live tick's innerHTML swap.

   The dashboard re-renders whenever ANY watched file changes (status.json
   every few seconds on the 2s /mtime poll). Without a carry, burnPanel
   recreates .bdtip/.bdinsp as hidden empty nodes and bdtipCol/bdinspCol
   still reference the detached columns — the tip fades in, then 1–2s later
   "it all resets" with the mouse unmoved. Detach also fires pointerout,
   which arms hide timers against the FRESH nodes; restore cancels those
   and rearms for the column still under the pointer (or the pinned t0).

   Identity is data-t0 (the bucket), never the node. settle=true so a
   rearm is not a second arrival every two seconds. Departing surfaces are
   not snapshotted — a leave already under way stays a leave. */
let lastBdPtr = null;
function bdColByT0(t0) {
  if (t0 == null || t0 === '') return null;
  const want = String(t0);
  let found = null;
  document.querySelectorAll('.bdnet .bdcol[data-open]').forEach(c => {
    if (c.dataset.t0 === want) found = c;
  });
  return found;
}
function snapshotBdHover() {
  const tip = document.querySelector('.bd .bdtip');
  const insp = document.querySelector('.bd .bdinsp');
  const tipLive = !!(tip && !tip.hidden && !tip.classList.contains('depart')
                     && bdtipCol);
  const inspLive = !!(insp && !insp.hidden && !insp.classList.contains('depart')
                      && bdinspCol);
  const act = document.activeElement;
  const focusCol = act && act.matches &&
    act.matches('.bdnet .bdcol[data-open]') ? act : null;
  return {
    tipT0: tipLive ? bdtipCol.dataset.t0 : null,
    inspT0: (inspLive || bdinspPin) && bdinspCol ? bdinspCol.dataset.t0 : null,
    pin: !!bdinspPin,
    focusT0: focusCol ? focusCol.dataset.t0 : null,
    hadTip: tipLive,
    hadInsp: inspLive,
  };
}
function restoreBdHover(s) {
  if (!s || (!s.tipT0 && !s.inspT0 && !s.pin && !s.focusT0)) return;
  // detach pointerout may have armed hide timers on the new nodes
  if (bdtipHideTimer) { clearTimeout(bdtipHideTimer); bdtipHideTimer = null; }
  if (bdinspHideTimer) { clearTimeout(bdinspHideTimer); bdinspHideTimer = null; }
  bdinspCancel();
  let under = null;
  if (lastBdPtr) {
    try {
      const el = document.elementFromPoint(lastBdPtr.x, lastBdPtr.y);
      under = el && el.closest && el.closest('.bdnet .bdcol[data-open]');
    } catch (e) {}
  }
  if (s.focusT0) {
    const fc = bdColByT0(s.focusT0);
    if (fc) {
      const keepPin = s.pin;
      fc.focus();   // focusin shows tip + insp; settle not needed
      if (keepPin && s.inspT0) {
        const pc = bdColByT0(s.inspT0);
        if (pc) { bdinspPin = true; showBdInsp(pc, true); }
      }
      return;
    }
  }
  if (s.pin && s.inspT0) {
    const pc = bdColByT0(s.inspT0);
    if (pc) { bdinspPin = true; showBdInsp(pc, true); }
    if (under) showBdTip(under, true);
    else if (s.hadTip && s.tipT0) {
      const tc = bdColByT0(s.tipT0);
      if (tc) showBdTip(tc, true);
    }
    return;
  }
  // Unpinned hover: prefer the column under the pointer (real mouse);
  // fall back to snapshotted t0 (synthetic pointerover has no coords).
  const col = under || (s.tipT0 && bdColByT0(s.tipT0));
  if (!col) return;
  if (s.hadTip || under) showBdTip(col, true);
  if (s.hadInsp) {
    const ic = under || (s.inspT0 && bdColByT0(s.inspT0)) || col;
    if (ic) showBdInsp(ic, true);
  } else if (s.hadTip || under) {
    bdinspSchedule(col);           // dwell was mid-flight — restart
  }
}
function bdinspSchedule(col) {
  if (bdinspPin) return;           // a pinned reading is not hover's to move
  bdinspCancel();
  bdinspDwell = setTimeout(() => showBdInsp(col), BD_DWELL);
}
/* tap selects / dismisses — no preventDefault, so chart scroll is never
   the inspector's to break. A tap on another column moves the pin; a tap
   outside the chart lets it go. */
addEventListener('click', e => {
  const col = e.target.closest && e.target.closest('.bdnet .bdcol[data-open]');
  if (col) {
    if (bdinspPin && bdinspCol === col) hideBdInsp(false);
    else { bdinspPin = true; showBdInsp(col); }
    return;
  }
  if (bdinspPin) hideBdInsp(false);
});
addEventListener('keydown', e => {
  if (e.key === 'Escape' && bdinspCol) { hideBdTip(true); hideBdInsp(false); }
});
/* a scrolled page moves the column out from under the reading — depart,
   never drift along stale coordinates. */
addEventListener('scroll', () => { if (bdinspCol) hideBdInsp(false); },
  { passive: true, capture: true });
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
/* #177 — a text box grows with what he types, to its own ceiling, then
   scrolls. The ceiling is a per-surface contract carried as `data-max-rows`
   (the composer 15, an answer/note box 6); the asymmetry is deliberate, so a
   long thought in the floating composer never shoves the question list for a
   ten-second sentence in a card.

   ONE gesture, not a second one. The box's HEIGHT travels on the page's
   atmospheric height-travel curve (.85s, the same `cubic-bezier(.32,.1,.2,1)`
   the card fold and #104's regroup use), and what sits below it is CARRIED
   by that travel rather than teleported: a height transition re-flows the
   box's containing block every frame, so the cards (or the composer's send
   row) ride the growth continuously, welded to it — the same outcome #104's
   FLIP produces for a discrete regroup, reached the way a small, frequent,
   one-line change reaches it. The plan's literal seam (snapshot → resize →
   `regroupCards(…, card)`) was the first instinct and is the right gesture,
   but `travelCard` clamps the host card to its old height with
   `overflow:hidden` for the travel, which HIDES the line he just typed (and
   its caret) for the whole .85s on every newline — unacceptable for the most
   frequent animation on the page. Letting the box itself own the travel keeps
   the caret in view and carries everything below on the same curve; the
   gesture is the page's, only the carrier differs.

   `animate=false` is the enter-snap rule again: a restore (the tick putting
   his text back, a draft surfaced on open) must not re-grow the box every two
   seconds, so it sets the height with the transition paused. A SEND clears the
   box through `clearBox` for the same reason — the card's own regroup already
   owns that height travel, and a second one on the textarea would fight it. */
function lineHeightOf(ta, cs) {
  cs = cs || getComputedStyle(ta);
  const lh = parseFloat(cs.lineHeight);
  if (isFinite(lh) && lh > 0) return lh;     // a resolved pixel line-height
  // 'normal' is font-metric-dependent and not a number: measure it with a
  // probe that inherits the box's own font, so the ceiling tracks the font
  // rather than a guessed ratio tuned to today's.
  const p = document.createElement('div');
  p.style.cssText = 'position:absolute;visibility:hidden;white-space:pre;' +
    'border:0;padding:0;margin:0;width:0;font:' + cs.font +
    ';line-height:' + cs.lineHeight;
  p.textContent = 'M\\nM';
  document.body.appendChild(p);
  const h = p.getBoundingClientRect().height / 2;
  p.remove();
  return h || (parseFloat(cs.fontSize) * 1.2);
}
function fitText(ta, animate) {
  if (!ta) return;
  const rows = parseInt(ta.dataset.maxRows, 10);
  if (!rows) return;                          // no ceiling: leave the box alone
  const cs = getComputedStyle(ta);
  if (!ta._lh) ta._lh = lineHeightOf(ta, cs); // constant for the font; cache it
  // border belongs to the border-box `height` but not to `scrollHeight`, so it
  // is added back so a 1px-bordered composer box never reads 2px short and
  // starts scrolling a line early.
  const bord = parseFloat(cs.borderTopWidth) + parseFloat(cs.borderBottomWidth);
  const ceil = Math.round(rows * ta._lh + bord);
  const oldH = ta.getBoundingClientRect().height;
  // measure the content's TRUE height: shrink first (transition paused) so a
  // deletion reads back smaller rather than as the box it currently fills —
  // scrollHeight otherwise returns max(content, client) and never shrinks.
  ta.style.transition = 'none';
  ta.style.height = 'auto';
  const want = ta.scrollHeight + bord;
  const target = Math.max(ta._lh + bord, Math.min(want, ceil));
  if (animate) {
    // the enter-snap rule, inverted: commit the OLD height with no transition,
    // then set the target with the standing transition restored, so the box
    // travels from where it was to where its content now needs.
    ta.style.height = oldH + 'px';
    void ta.offsetWidth;
    ta.style.transition = '';                 // the CSS height transition reapplies
    ta.style.height = target + 'px';
  } else {
    // a restore (tick, draft): snap to the target and THEN restore the
    // standing transition, so the box does not re-grow under him on every
    // tick yet the next input he types still travels.
    ta.style.height = target + 'px';
    void ta.offsetWidth;
    ta.style.transition = '';
  }
}
/* snap a box to its floor — used after a send clears it, where the CARD's own
   regroup already owns the height travel and a second transition on the
   textarea would animate against it. Sets no height, so the CSS `min-height`
   is the floor. */
function clearBox(ta) {
  if (!ta) return;
  ta.style.transition = 'none';
  ta.style.height = '';
  void ta.offsetWidth;
  ta.style.transition = '';
}
/* save a drafted answer as he types (#269 acute). Delegated on `document`
   because the box is recreated by every re-render — a listener bound to the
   node would die with it. Keyed by `data-qid` (the question's title identity),
   resolved against the live card so the draft never lands under the wrong
   question, and written through `dwDraft` so the composer's rules apply
   verbatim: no debounce, wrapped storage, and a value of '' removes the key
   (deleting his words is his act, unlike a close or a failed send). */
addEventListener('input', e => {
  const t = e.target;
  if (!t || t.tagName !== 'TEXTAREA' || !/^qi[oa]\\d+$/.test(t.id)) return;
  const card = t.closest('.qa[data-qid]');
  if (!card || !card.dataset.qid) return;
  let title = null;
  try { title = decodeURIComponent(card.dataset.qid); } catch (er) { return; }
  if (title) dwDraft.save(title, t.value);
  fitText(t, true);                           // #177: the box grows with what he typed
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
   (#250). Reuses travelCard / revealBody / dreamAway — the qsec shape.
   Open-state survival across ticks is not this function's job: expand()
   peeks and .qsec carry data-keep so snapshotFolds restores them; listless
   missing-aid answered details deliberately omit it and re-close on tick.
   reduced-motion still toggles; only timing drops. */
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
  /* #452: a REAL LINK inside the summary (the folded card's focus
     affordance) is navigation, not a fold — decline it so the router's
     handler takes it. This handler is registered FIRST, so its
     preventDefault would otherwise mark the click handled and the
     router's `e.defaultPrevented` check would skip the navigation: the
     link read as present but only ever toggled the fold. */
  if (e.target.closest('a')) return;
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
/* Plain read peeks — dreams, .md files, status overflow (#277 reusable).
   These were native <details> toggles with no animation: closing one snapped
   the body away. They now go through the same foldDetailsLocal path as the
   keyed-list fallback (#250), so the body departs on the mist idiom and
   everything below travels rather than jumping. reduced-motion: native toggle.
   Open state rides data-keep via expand()'s keep arg + snapshotFolds
   (status-rest, file:*, dream:*, dreams-archive) — same #141 rule the
   questions section already had; without it the tick re-closes under him. */
addEventListener('click', e => {
  const sum = e.target.closest && e.target.closest('.peek > summary');
  if (!sum || rmr) return;
  e.preventDefault();
  foldDetailsLocal(sum.parentElement);
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
  /* #284: the BASENAME is the heading. The parent path is metadata and lives
     one line down, in the crumb row (`crumbsFor`). */
  file: v => esc(fileBase(v.param || '')),
  review: v => `review<span class="revname">${esc(v.param || '')}</span>`,
  /* #452: the heading names the SURFACE, not the question — a title can run
     to a line and a half, and it is rendered in full by the card directly
     below. When the key resolves nowhere the missing notice says so. */
  question: () => 'question',
};
/* The copy button carries no path of its own, on purpose: it reads
   `view.param`, which is what the router parsed out of the URL and therefore
   the same string the heading and the metadata line were built from. A
   `data-path` attribute would be a second copy of the truth AND a new
   attribute-injection site — `esc()` escapes `<`/`>`/`&` but not `"`, so a
   query string can already break out of an attribute here (see the note in
   watch-design.md). Reading the route needs no escaping at all.

   `aria-describedby` names the metadata line and then the heading, in that
   order, so a screen reader announces the button as the full path in reading
   order: "copy path, button, .dreamwork/docs/research/, notes.md". When there
   is no parent it describes itself by the heading alone. */
const copyPathBtn = hasDir =>
  `<button type="button" class="fcopy"` +
  ` aria-describedby="${hasDir ? 'fdir htitle' : 'htitle'}">copy path</button>`;
/* #252 — Rendered / Source, beside the path, for markdown only.
   TWO ORDINARY INTERNAL LINKS, not buttons, and that is three things at once:
   the mode is deep-linkable because it is in the href, it is keyboard- and
   middle-click-operable because it is a link, and the swap rides the router's
   existing dissolve because `isInternal` already claims `/file`. A pair of
   buttons would have needed a handler, a history push and a transition of its
   own — three re-implementations of what the route already does.

   THE `.on` STATE IS DELIBERATELY NOT IN THIS HTML. `renderChrome` rewrites a
   crumb whose html changed, and a rewritten `.sgroup` is fresh nodes with a
   0-width indicator — the outline would grow out of the row's left edge
   instead of sliding to the other label. Held out, the switch is a SURVIVOR
   across a mode change and `paintFileMode` slides it: the sliding selection
   group's own documented gesture (#121). That is also why the crumb is
   declared `stable`. */
const fileModeSwitch = p => {
  const base = '/file?p=' + encodeURIComponent(p);
  return '<span class="sgroup fmodes" role="group" aria-label="markdown view">' +
    '<span class="sgind" aria-hidden="true"></span>' +
    `<a class="sgbtn fmode" data-mode="rendered" href="${base}">rendered</a>` +
    `<a class="sgbtn fmode" data-mode="source" href="${base}&amp;view=source">source</a>` +
    '</span>';
};
/* The switch's state, painted AFTER the crumb row is assembled, because the
   indicator needs the row's final geometry. `slide` is true only when the
   group SURVIVED the render — a group that just arrived lands instead, on the
   enter-snap rule, and reduced motion always lands (`slideIndicator`). */
function paintFileMode(v, slide) {
  const g = document.querySelector('#meta .fmodes');
  if (!g) return;
  const want = (v && v.mode === 'source') ? 'source' : 'rendered';
  for (const a of g.querySelectorAll('.fmode')) {
    const on = a.dataset.mode === want;
    a.classList.toggle('on', on);
    // `aria-current="page"` rather than a radio's checked state: these ARE
    // pages, and saying so is what makes the switch honest to a screen reader
    // about being navigation.
    if (on) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  }
  slideIndicator(g, !slide);
}
function crumbsFor(v, d) {
  const home = { k:'home', html:'<a href="/">&larr; dashboard</a>' };
  if (v.name === 'questions' || v.name === 'answers') return [home];
  if (v.name === 'file') {
    const p = v.param || '', dir = fileDir(p);
    const row = [home];
    if (dir) row.push({ k:'fdir', html:`<span class="fdir" id="fdir">${esc(dir)}</span>` });
    row.push({ k:'fcopy', html: copyPathBtn(!!dir) });
    // Markdown only (#252). The key carries the PATH, so switching files
    // departs one switch and arrives another (a different file's control),
    // while switching MODE on one file keeps the same element and lets the
    // indicator slide.
    if (isMarkdownFile(p))
      row.push({ k:'fview:' + p, html: fileModeSwitch(p), stable: true });
    row.push({ k:'pip', html: pipBtn('/file?p=' + encodeURIComponent(p),
                                     p || 'file') });
    return row;
  }
  if (v.name === 'review') return [
    { k:'qs', html:'<a href="/questions">&larr; questions</a>' },
    { k:'home', html:'<a href="/">dashboard</a>' },
    { k:'pip', html: pipBtn('/reviewraw?p=' + encodeURIComponent(v.param || ''),
                            'review: ' + (v.param || '')) }];
  // #452: the focused page belongs to the questions list — the way back is
  // the same pair the review dock carries (no artifact to pop out here).
  if (v.name === 'question') return [
    { k:'qs', html:'<a href="/questions">&larr; questions</a>' },
    { k:'home', html:'<a href="/">dashboard</a>' }];
  // #484: the listing's way back is the dashboard; an artifact adds the
  // listing as its middle crumb and the raw pop-out, the review pair's
  // shape with no questions half (there is no pairing to return to).
  if (v.name === 'research') {
    const row = [{ k:'home', html:'<a href="/">&larr; dashboard</a>' }];
    if (v.param) row.push(
      { k:'list', html:'<a href="/research">research</a>' },
      { k:'pip', html: pipBtn('/researchraw?p=' + encodeURIComponent(v.param),
                              'research: ' + v.param) });
    return row;
  }
  if (!d) return [];
  // #491 — the version crumb sits BESIDE the freshness age ("updated Ns ago"),
  // and a bare migration filename in that slot read as "this file changed Ns
  // ago". It is not: the value is the target's RECORDED skill version
  // (.dreamwork/skill-version, written by orient), a different source from the
  // skill tree's latest migration (skill_identity). The value is honest; the
  // defect was the adjacency implying an age, because the crumb named nothing
  // about what it IS. So it says so — a dim "skill" label before the name —
  // and the neighbour no longer supplies the meaning. Built only when there is
  // a name to show (an empty version file renders no crumb, not a bare dot).
  const sv = d.files['skill-version'];
  const row = [
    { k:'target', html: esc(d.target) },
  ];
  if (sv) row.push({ k:'version',
    html:'<span style="color:var(--dim)">skill</span> ' + esc(sv) });
  row.push(
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
          `questions</a>` });
  return row;
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
  let keptModes = false;
  for (const c of next) {
    let el = prev.get(c.k);
    if (el) {
      prev.delete(c.k);
      /* A `stable` crumb owns its own state and is never rewritten while it
         survives (#252). The mode switch is the one: its `.on` class is
         painted by `paintFileMode`, so an html comparison would see the live
         class, disagree, and replace the nodes the FLIP and the sliding
         indicator both need to be the SAME elements. Its key carries the
         path, so nothing stale can survive a change of file. */
      if (c.stable) keptModes = keptModes || /^fview:/.test(c.k);
      else if (el.innerHTML !== c.html) el.innerHTML = c.html;
    }
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
  /* #172 — project identity, edge-pinned. The basename is invariant across
     routes, so it is a SURVIVOR: rewrite only when the name itself changes
     (a different target would be a full reload anyway). First appearance
     rides the same enter-snap as the route word; a route change that leaves
     the name alone does not re-dream it. Full path is the title= tooltip —
     not in the bar — for popoutShell's reason (two checkouts, one basename). */
  const projEl = document.getElementById('hproj');
  if (projEl) {
    const name = projectName(d);
    const path = (d && d.target) || '';
    if (name) {
      if (projEl.textContent !== name) {
        projEl.textContent = name;
        if (snap && !rmr) {
          projEl.classList.add('dreamin');
          arrived.push(projEl);
        }
      }
      if (projEl.getAttribute('title') !== path) projEl.setAttribute('title', path);
      projEl.hidden = false;
    } else {
      projEl.textContent = '';
      projEl.removeAttribute('title');
      projEl.hidden = true;
    }
  }
  // #252: the switch's state and whether it slides. Before `ages()` only
  // because both are "finish the row"; it needs the row's final geometry,
  // which `replaceChildren` above has already committed.
  paintFileMode(v, !!snap && keptModes);
  ages();
  /* The review pane's top IS the bottom of this chrome, so it is refitted
     wherever the chrome is (re)laid out — `setContent` runs BEFORE this on
     every route change, and a crumb row that has not been written yet
     measures ~21px short. Here rather than after the FLIP below because a
     transform does not move `offsetTop`, and the early return above is on
     the animation, not on the layout. */
  fitReview();
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
/* ── copying the exact path (#284) ────────────────────────────────────────
   The heading shows the basename and the metadata line shows the parent, so
   the ONE place the whole path still exists in full is the route — and that
   is what this copies, character for character, with no separator inserted
   and nothing normalised. Reading `view.param` rather than an attribute is
   also what keeps a second copy of the truth off the page.

   Built lazily because `confirmationFor` is declared in COMMAND_JS, which is
   concatenated after this block; a top-level call here would depend on where
   the script boundaries happen to fall.

   BOTH OUTCOMES SPEAK, on the page's one confirmation lifecycle. The failure
   is not an apology — it names the fallback, and the fallback is real: the
   metadata line is selectable text precisely so a refused clipboard leaves
   him something to do. Under reduced motion `confirmationFor` keeps the hold
   and the clear and drops only the fade, which is the hard contract: same
   information, same timing, no movement. */
let fileMsg = null;
const fileConfirmation = () =>
  (fileMsg || (fileMsg = confirmationFor(document, 'fmsg', 'cmdmsg fmsg', rmr)));
async function copyFilePath() {
  const path = (view && view.name === 'file' && view.param) || '';
  const c = fileConfirmation();
  if (!path) { c.note('there is no path to copy', false); return; }
  try {
    if (!navigator.clipboard || !navigator.clipboard.writeText)
      throw new Error('no clipboard');
    await navigator.clipboard.writeText(path);
    c.note('path copied', true);
  } catch (e) {
    c.note('copy was blocked — the path beside it is selectable', false);
  }
}
/* #462 — the staleness row's remedy RUNS `just deploy` (authorised 03:46).
   Confirmation and failure speak on the page's ONE lifecycle (#fmsg), the
   same confirmationFor the file-path copy uses. The arm is #290's RUN_ARM_MS
   idiom reused: first click arms, re-click cancels, only the deadline POSTs,
   so two clicks do not start two deploys. Concurrent with an in-flight deploy
   is refused client-side and single-flight server-side.

   After a landed POST the server may die (that is the point of redeploy). The
   loaded document keeps polling /mtime; a new GENERATION is success (tick
   reloads). DEPLOY_WAIT_MS with no generation change is the named failure —
   never a spinner forever. Drafts ride #269's localStorage and survive the
   reload by construction (the restart destroys the server, not the document's
   storage). */
let staleDeployGen = 0;
let staleDeployPhase = null;   // null | 'arming' | 'running'
let staleDeployUntil = 0;
let staleDeployTimer = null;
let staleDeployTick = null;
let staleDeployWait = null;

function paintStaleDeployUI() {
  const btn = document.querySelector('.gservact');
  if (!btn) return;
  const arming = staleDeployPhase === 'arming';
  const running = staleDeployPhase === 'running';
  btn.classList.toggle('arming', arming);
  btn.classList.toggle('running', running);
  btn.setAttribute('aria-busy', running ? 'true' : 'false');
  if (arming) {
    const s = Math.max(0, Math.ceil((staleDeployUntil - Date.now()) / 1000));
    btn.textContent = s > 0 ? `arms in ${s}s` : 'updating…';
  } else if (running) {
    btn.textContent = 'updating…';
  } else {
    btn.textContent = 'just deploy';
  }
}

function clearStaleDeployArm() {
  if (staleDeployTimer) { clearTimeout(staleDeployTimer); staleDeployTimer = null; }
  if (staleDeployTick) { clearInterval(staleDeployTick); staleDeployTick = null; }
  staleDeployUntil = 0;
  if (staleDeployPhase === 'arming') staleDeployPhase = null;
  paintStaleDeployUI();
}

function cancelStaleDeployArm() {
  staleDeployGen++;
  clearStaleDeployArm();
}

function armStaleDeploy() {
  const c = fileConfirmation();
  const until = Date.now() + RUN_ARM_MS;
  staleDeployGen++;
  const gen = staleDeployGen;
  staleDeployPhase = 'arming';
  staleDeployUntil = until;
  paintStaleDeployUI();
  const remainingMs = () => Math.max(0, staleDeployUntil - Date.now());
  // #490: countdown is steady text that ticks once per second. Re-calling
  // note()/claim() restarts .dreamin at the poll rate (~4 Hz flash on #fmsg).
  // claim (not note) so a 10s arm is not auto-cleared at the 5s hold.
  let lastLeft = -1;
  const setCount = () => {
    if (gen !== staleDeployGen) return;
    const left = Math.ceil(remainingMs() / 1000);
    if (left <= 0) return;
    if (left === lastLeft) return;  // same second — do nothing
    lastLeft = left;
    paintStaleDeployUI();
    const text = `arms in ${left}s — then this page updates`;
    const m = document.getElementById('fmsg');
    if (m && /^arms in \\d+s — then this page updates$/.test(m.textContent || '')) {
      m.textContent = text;  // tick the number in place; no arrival gesture
    } else {
      c.claim(text, true);   // first paint of this arm only
    }
  };
  setCount();
  if (staleDeployTick) clearInterval(staleDeployTick);
  staleDeployTick = setInterval(setCount, 250);
  if (staleDeployTimer) clearTimeout(staleDeployTimer);
  // Remaining, not a fixed RUN_ARM_MS — same as #290 armRunModeUI, so a
  // mid-arm rebuild and the guard's compressed clock both land correctly.
  staleDeployTimer = setTimeout(() => {
    if (gen !== staleDeployGen) return;
    if (staleDeployTick) { clearInterval(staleDeployTick); staleDeployTick = null; }
    staleDeployTimer = null;
    fireStaleDeploy(gen);
  }, remainingMs());
}

async function fireStaleDeploy(gen) {
  if (gen !== staleDeployGen) return;
  staleDeployPhase = 'running';
  paintStaleDeployUI();
  const c = fileConfirmation();
  c.note('updating — waiting for the new page', true);
  let landed = false;
  try {
    const res = await fetch('/deploy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from: location.pathname + location.search }),
    });
    // raw-fetch site: owns its Response, gates on writeVerdict — never res.ok
    // alone (#263 E5b). A rejected 202 would otherwise look like success.
    const rv = await writeVerdict(res);
    landed = rv.landed;
    if (!landed) {
      staleDeployPhase = null;
      paintStaleDeployUI();
      /* The two ways this route refuses are both `domain_invalid`, so the
         generic copy ("the value was not one the server accepts") is wrong for
         both — and these are the ONLY two refusals he can provoke. `detail`
         names which. The old `res.status === 403` branch was dead: since the
         202 cutover (#263 E5) a refusal is 202 + rejected, never 403, so the
         "only runs from this machine" line could never have printed. */
      const why = DEPLOY_WHY[rv.detail]
        || (rv.rejected && rv.reason && REJECT_WHY[rv.reason])
        || null;
      c.note(
        rv.detail === 'in_flight'
          ? `already updating — ${why}`
          : `update was refused — ${why || 'try again in a moment'}`,
        false);
      return;
    }
  } catch (e) {
    staleDeployPhase = null;
    paintStaleDeployUI();
    c.note('update was refused — the page could not reach the server', false);
    return;
  }
  if (gen !== staleDeployGen) return;
  // Landed: the server may already be dying. Watch for a new generation;
  // if none arrives by DEPLOY_WAIT_MS, name the failure.
  // window.__dwDeployWaitMs is the guard's short-deadline inject (mirrors
  // __dwSkipStaleArrival): production never sets it; the default is the
  // styleguide constant.
  const waitMs = (typeof window.__dwDeployWaitMs === 'number')
    ? window.__dwDeployWaitMs : DEPLOY_WAIT_MS;
  const startedAt = Date.now();
  const baseline = serverGen;
  if (staleDeployWait) clearInterval(staleDeployWait);
  staleDeployWait = setInterval(() => {
    if (gen !== staleDeployGen) {
      clearInterval(staleDeployWait); staleDeployWait = null; return;
    }
    // tick() reloads on generation change; if we are still here past the
    // deadline, the new generation never came.
    if (serverGen && baseline && serverGen !== baseline) {
      clearInterval(staleDeployWait); staleDeployWait = null;
      return; // reload is in flight or done
    }
    if (Date.now() - startedAt >= waitMs) {
      clearInterval(staleDeployWait); staleDeployWait = null;
      staleDeployPhase = null;
      paintStaleDeployUI();
      c.note(
        'update never finished — this page is still the old one',
        false);
    }
  }, 400);
}

function onStaleActionClick() {
  const c = fileConfirmation();
  if (staleDeployPhase === 'running') {
    c.note('update already in flight — waiting for the new page', false);
    return;
  }
  if (staleDeployPhase === 'arming') {
    cancelStaleDeployArm();
    c.note('update cancelled', true);
    return;
  }
  armStaleDeploy();
}
addEventListener('click', e => {
  const stale = e.target.closest && e.target.closest('.gservact');
  if (stale) { onStaleActionClick(); return; }
  const btn = e.target.closest && e.target.closest('.fcopy');
  if (btn) copyFilePath();
});
/* Dream dissolve: the outgoing view becomes a ghost that liquifies into a
   swirling mist (turbulence displacement + blur grow) and drifts upward as
   it fades; the incoming view coalesces from the same mist and settles
   perfectly crisp. Opacity + transform ride CSS; the mist is an SVG filter
   whose displacement + blur we envelope per-frame here, so the middle of
   the dissolve lingers hazy. The shader stirs in sympathy (pulseWarp).
   reduced-motion swaps instantly — no ghost, no mist. */
const DREAM_MS = 1150;                     // dwell of the whole dissolve
// #449: the SVG liquify mist (feTurbulence→displacement→blur, driven per-frame
// from stepFx) was shelved behind this switch. Measured 2026-07-29 on the route
// he named (question→review): Chrome rasterizes feTurbulence afresh every frame
// and does not cache it across frames, so freezing baseFrequency, freezing ALL
// six stepFx attribute writes, and even clamping the ghost's filtered area 42%
// (553×1557→553×900, geometry confirmed) all bought nothing — the cost was the
// turbulence primitive regenerating, not the displacement math, the attribute
// writes, or the area. Removing both dissolve filters recovered +100–128% of
// rAF frames (capture: dev/capture/dissolveperf.mjs).
// #453: the mist is RESTORED as the human's texture idea — one cached noise
// field pre-rendered once (mistTexture below), consumed via feImage and MOVED
// per frame by feOffset ("just having a single texture ... and then just like
// moving it"). Nothing regenerates per frame; feOffset/feTile shift a cached
// bitmap, and #449 measured the displacement+blur math itself as free (I3).
// Measured in the same harness against #449's bar — see transitions.md (*The
// mist filter*) for the numbers. The shelved feTurbulence filters stay defined
// (#dissolveOutT/#dissolveInT) and MIST_IMPL 'turbulence' selects them for
// comparison. MIST_ON false = CSS blur carries the dissolve (#449's fallback;
// body.mistoff rules), whatever MIST_IMPL says.
const MIST_ON = true;
const MIST_IMPL = 'feimage';   // 'feimage' (#453) | 'turbulence' (#449, shelved)
// The cached mist field: a TILEABLE fractal value-noise texture, generated
// once, deterministic (fixed PRNG state so captures are reproducible), with
// independent R and G fields for the two displacement axes. Tileable by
// construction — each octave's lattice wraps at its period — so feTile repeats
// it seamlessly and feOffset can drift it without a seam ever crossing.
let MIST_TEX = null;
function mistTexture() {
  if (MIST_TEX !== null) return MIST_TEX;
  try {
    const T = 256;
    const cv = document.createElement('canvas'); cv.width = cv.height = T;
    const cx2 = cv.getContext('2d');
    if (!cx2) throw new Error('no 2d context');
    const im = cx2.createImageData(T, T);
    const fade = t => t * t * (3 - 2 * t);
    const hash = (x, y, p, sd) => {
      x = ((x % p) + p) % p; y = ((y % p) + p) % p;      // wrap → tileable
      let h = (x * 374761393 + y * 668265263 + sd * 2246822519) >>> 0;
      h = (h ^ (h >>> 13)) >>> 0; h = (h * 1274126177) >>> 0;
      return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
    };
    const oct = (px, py, p, sd) => {
      const gx = px / T * p, gy = py / T * p;
      const x0 = Math.floor(gx), y0 = Math.floor(gy);
      const fx = fade(gx - x0), fy = fade(gy - y0);
      const v00 = hash(x0, y0, p, sd), v10 = hash(x0 + 1, y0, p, sd);
      const v01 = hash(x0, y0 + 1, p, sd), v11 = hash(x0 + 1, y0 + 1, p, sd);
      return (v00 * (1 - fx) + v10 * fx) * (1 - fy) +
             (v01 * (1 - fx) + v11 * fx) * fy;
    };
    // periods/weights chosen to read like the old baseFrequency≈0.009 field
    // (~110px blobs) at a 256px tile: 2–3 large forms per tile, finer octaves
    // for the swirl. R and G are independent fields (sd 11 vs 47).
    const OS = [[2, .42], [4, .27], [8, .18], [16, .13]];
    let mn = 1, mx = 0;
    const R = new Float32Array(T * T), G = new Float32Array(T * T);
    for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
      let r = 0, g = 0;
      for (const [p, w] of OS) { r += oct(x, y, p, 11) * w; g += oct(x, y, p, 47) * w; }
      R[y * T + x] = r; G[y * T + x] = g;
      if (r < mn) mn = r; if (r > mx) mx = r;
    }
    for (let i = 0; i < T * T; i++) {   // stretch R to the full range (same
      const r = (R[i] - mn) / (mx - mn); // band G occupies, ±2%)
      im.data[i * 4] = r * 255;
      im.data[i * 4 + 1] = Math.max(0, Math.min(255, (G[i] - mn) / (mx - mn) * 255));
      im.data[i * 4 + 2] = 128; im.data[i * 4 + 3] = 255;
    }
    cx2.putImageData(im, 0, 0);
    MIST_TEX = cv.toDataURL('image/png');
    document.querySelectorAll('#dreamfx feImage.texsrc').forEach(fi => {
      fi.setAttribute('href', MIST_TEX);
      fi.setAttributeNS('http://www.w3.org/1999/xlink', 'xlink:href', MIST_TEX);
    });
  } catch (e) {
    MIST_TEX = '';                        // no canvas: degrade to CSS blur
    document.body.classList.add('mistoff');
  }
  return MIST_TEX;
}
const fxNode = (id, tag) => document.querySelector('#' + id + ' ' + tag);
function crossfade(html, xopts) {
  xopts = xopts || {};
  const viewEl = document.getElementById('view');
  if (rmr) {
    document.body.classList.toggle('review', !!xopts.review);
    document.body.classList.toggle('file', !!xopts.file);
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
  document.body.classList.toggle('file', !!xopts.file);
  setContent(html);
  renderChrome(view, data, snap);   // the heading travels; it does not reload
  // measure the docked question's resting rect BEFORE the enter transform,
  // so a shared-element FLIP from the clicked question lands true.
  const dock = document.getElementById('qdock');
  const dockRect = dock ? dock.getBoundingClientRect() : null;
  // #449/#453: the liquify mist is behind MIST_ON, and applied to the GHOST
  // ONLY. #453 measured the cost model end to end in #449's own harness on
  // this host: the per-frame price is the COUNT of full-page SVG filter
  // rasterisations, nothing else — feImage≈feTurbulence, static≈animated,
  // two filters ≈ 24 frames, one ≈ 34, none ≈ 47-50. So the departing view
  // keeps the whole gesture (liquify + flow + haze, one rasterisation) and
  // the arriving view's haze is the compositor CSS blur (measured free).
  // MIST_IMPL picks the field: 'feimage' is the cached moved texture (#453),
  // 'turbulence' the shelved per-frame feTurbulence (#449).
  const mistOk = MIST_ON && (MIST_IMPL === 'turbulence' || mistTexture());
  if (mistOk) {
    const sfx = MIST_IMPL === 'turbulence' ? 'T' : '';
    ghost.style.filter = 'url(#dissolveOut' + sfx + ')';
  }
  viewEl.classList.add('enter');
  void viewEl.offsetWidth;                 // commit the hidden start state
  if (xopts.fromRect && dock && dockRect) flipDock(dock, xopts.fromRect, dockRect);
  if (window.dreambg) window.dreambg.pulseWarp();
  requestAnimationFrame(() => {
    viewEl.classList.remove('enter');      // CSS eases opacity + drift in
    ghost.classList.add('out');            // CSS eases opacity + drift out
  });
  const t0 = performance.now();
  let raf = 0;
  const finish = () => {
    if (raf) cancelAnimationFrame(raf), raf = 0;
    if (ghost.isConnected) ghost.remove();
    viewEl.style.filter = '';              // crisp at rest, zero filter cost
    document.body.classList.remove('wsliding');
  };
  // The per-frame mist envelope, on the ghost's one rasterisation. feimage:
  // the displacement/blur envelopes plus feOffset DRIFTS that move the cached
  // field's two interfering layers on different bearings — the flow the
  // baseFrequency ramp used to fake, now from a field nothing regenerates.
  // turbulence (shelved): the original writes. The envelope endpoints are
  // identical either way, so the gesture's shape does not depend on the
  // mechanism.
  if (mistOk) {
    const sfx = MIST_IMPL === 'turbulence' ? 'T' : '';
    const dOut = fxNode('dissolveOut' + sfx, 'feDisplacementMap');
    const bOut = fxNode('dissolveOut' + sfx, 'feGaussianBlur');
    const tOut = fxNode('dissolveOut' + sfx, 'feTurbulence');
    const o1 = fxNode('dissolveOut' + sfx, 'feOffset');
    // per-destination swirl signature: this arrival's field. feimage moves a
    // STATIC field, so the seed selects where in the tile the field starts
    // and on what bearing it drifts; turbulence seeds the noise itself.
    const seed = SEED[view.name] != null ? SEED[view.name] : 7;
    if (tOut) tOut.setAttribute('seed', seed);
    // drift: bounded so the offset never pushes the tiled field's edge into
    // the region displacement can sample (region margin − scale/2; the
    // narrowest filtered element on any route is the 553px questions column).
    const ang = (seed % 12) / 12 * 2 * Math.PI;
    const ox0 = (seed * 37) % 96 - 48, oy0 = (seed * 91) % 96 - 48;
    const DX = Math.cos(ang) * 40, DY = Math.sin(ang) * 40;
    const smooth = x => x * x * (3 - 2 * x);
    function stepFx(now) {
      const u = Math.min(1, (now - t0) / DREAM_MS);
      const eo = smooth(u);                          // ghost: mist grows in
      if (dOut) dOut.setAttribute('scale', (eo * 25).toFixed(2));
      if (bOut) bOut.setAttribute('stdDeviation', (eo * 3.8).toFixed(2));
      if (o1) {
        o1.setAttribute('dx', (ox0 + eo * DX).toFixed(1));
        o1.setAttribute('dy', (oy0 + eo * DY).toFixed(1));
      }
      const bf = (0.009 + eo * 0.009).toFixed(4);    // shelved: field tightens
      if (tOut) tOut.setAttribute('baseFrequency', bf);
      if (u < 1) raf = requestAnimationFrame(stepFx);
      else finish();
    }
    raf = requestAnimationFrame(stepFx);
  }
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
/* ── the reading position across a mode swap (#252) ───────────────────────
   The document's scrollable range as the CONTENT implies it, in LAYOUT space.
   Two traps, both documented in transitions.md and both live here:

   - `documentElement.scrollHeight` answers for the outgoing GHOST too. The
     ghost is an absolutely positioned clone inside `.wrap`, so while it lives
     (~1.15s) it extends the document's scrollable area — and going
     source -> rendered it is the taller of the two. The restore would land
     low and then be clamped when the corpse is removed.
   - `getBoundingClientRect` answers in VISUAL space, and on the frame this
     runs `#view` is mid-`enter`: pushed back in Z and scaled down. Every rect
     beneath it reads small. `offsetTop`/`offsetHeight` are layout values and
     are immune to both, which is why the chain is walked by hand. */
function contentBottom() {
  const v = document.getElementById('view');
  if (!v) return 0;
  let y = 0;
  for (let n = v; n; n = n.offsetParent) y += n.offsetTop;
  return y + v.offsetHeight +
    (parseFloat(getComputedStyle(document.body).paddingBottom) || 0);
}
const scrollRange = () => Math.max(0, contentBottom() - window.innerHeight);
/* A RATIO, not a pixel offset: the two panes are different heights (a rendered
   document is shorter than the source it came from, by roughly its own markup)
   so the same pixel offset is a different place in the text. Null when there
   is nothing to scroll, so a short file restores nothing rather than 0/0. */
const scrollRatio = () => {
  const range = scrollRange();
  return range > 0 ? Math.min(1, window.scrollY / range) : null;
};
function restoreScrollRatio(r) {
  if (r === null || r === undefined) return;
  const range = scrollRange();
  if (range > 0) window.scrollTo(0, Math.round(r * range));
}
async function navigate(name, param, opts) {
  opts = opts || {};
  const mode = opts.mode === 'source' ? 'source' : 'rendered';
  /* A mode swap is a change of REPRESENTATION, not of place: same file, same
     point in it. Every other navigation is a new document and has no position
     to keep, which is why this is not a general scroll-restore. */
  const modeSwap = !!view && view.name === 'file' && name === 'file' &&
                   view.param === param && (view.mode || 'rendered') !== mode;
  const keepRatio = modeSwap ? scrollRatio() : null;
  if (window.__closeCmd) window.__closeCmd();   // context is changing
  // Leaving /answers destroys the ask surface — drop in-flight ownership so a
  // late /ask cannot clear or tick a form that no longer exists, and so a
  // return visit is not blocked by a stuck askInFlight flag (#292 lifecycle).
  if (view && view.name === 'answers' && name !== 'answers')
    invalidateAskFlight();
  // #284: a copy confirmation belongs to the file it was made on, and the
  // chrome SURVIVES a route change — so without this the message would follow
  // him onto another page and describe a path no longer on screen. Route
  // change is destruction here, exactly as it is for the composer.
  if (fileMsg && !(view && view.name === name && view.param === param))
    fileMsg.clear();
  view = { name, param, q: opts.q || null, mode };
  applyTitle();
  if (window.dreambg) window.dreambg.setTint(TINT[name] || 0);
  const url = name === 'questions' ? '/questions'
    : name === 'answers' ? '/answers'
    : name === 'file' ? '/file?p=' + encodeURIComponent(param || '') +
        (mode === 'source' ? '&view=source' : '')
    : name === 'review' ? '/review?p=' + encodeURIComponent(param || '') +
        (opts.q ? '&q=' + encodeURIComponent(opts.q) : '')
    : name === 'question' ? '/question?qid=' + encodeURIComponent(param || '')
    : name === 'research' ? '/research' +
        (param ? '?p=' + encodeURIComponent(param) : '')
    : '/';
  /* The wide artifact column is the review idiom's, and a research DOC
     (#484, /research?p=…) is the same reading gesture over the same
     #reviewwrap nodes — so it borrows body.review rather than growing a
     second wide-column rule. The research LISTING stays the normal column. */
  const artifactDoc = name === 'review' || (name === 'research' && !!param);
  if (opts.push) history.pushState({ name, param, q: opts.q || null }, '', url);
  const html = await buildCurrent();
  if (opts.transition === false) {
    document.body.classList.toggle('review', artifactDoc);
    document.body.classList.toggle('file', name === 'file');
    setContent(html);
    renderChrome(view, data, null);   // first paint: arrive, don't animate
  } else {
    crossfade(html, { fromRect: opts.fromRect, review: artifactDoc,
                      file: name === 'file' });
  }
  // after the new content is in layout, and only for the swap that has a
  // position worth keeping
  if (modeSwap) restoreScrollRatio(keepRatio);
}
/* only same-document routes are intercepted; external links, new-tab and
   modified clicks fall through to the browser. */
function isInternal(a) {
  if (!a || a.target === '_blank' || a.hasAttribute('download')) return false;
  if (a.origin !== location.origin) return false;
  return a.pathname === '/' || a.pathname === '/questions'
      || a.pathname === '/answers'
      || a.pathname === '/file' || a.pathname === '/review'
      || a.pathname === '/question' || a.pathname === '/research';
}
addEventListener('click', e => {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey ||
      e.shiftKey || e.altKey) return;
  const a = e.target.closest('a');
  if (!isInternal(a)) return;
  e.preventDefault();
  const r = routeOf(a);
  // `routeOf` reads `search` off the <a> as readily as off `location`, so the
  // mode switch needs no handler of its own: it is two ordinary internal links
  // (#252), which is also what makes it keyboard-operable and deep-linkable.
  const opts = { push: true, q: r.q, mode: r.mode };
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
  navigate(r.name, r.param, { push: false, q: r.q, mode: r.mode });
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
      if (burnStepPref === null) burnStepPref = loadBurnStepPref();
      setData(await (await fetch(dataJsonUrl())).json());
      // the data lands instantly; surviving cards then travel from where
      // they were to where the new grouping put them (#104/#77). What the
      // human is mid-way through typing rides across the swap (#118).
      const tickView = view;
      const kept = snapshotCardState();
      const askKept = snapshotAskState();
      const reviewFrame = snapshotReviewFrame();
      const folds = snapshotFolds();
      const before = snapshotCards();
      // #494: burndown hover/pin — same carry as card state, keyed by
      // bucket t0. Snapshot BEFORE the swap; the detach fires pointerout
      // which would otherwise clear the fresh (hidden) tip/inspector.
      const bdHover = snapshotBdHover();
      // Exact artifact *created* times can reorder these rows on any data
      // tick (#463). Keep their filename identity and reuse the list FLIP
      // rather than snapping.
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
      restoreBdHover(bdHover);       // #494 before anything that measures
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
      // AFTER the restore, never before it (#326). What is above and below the
      // docked question is a fact about its scroll position, and one line
      // earlier that position is still 0 — so syncing there answers for a
      // question scrolled to the top and then leans on the scroll steps
      // running before the next style pass to correct it before anything is
      // painted. That happens to hold, which is why no guard here fails on
      // the other order; stating the precondition costs less than the
      // reasoning does, and the fades are a transition, so the day it stops
      // holding it is visible motion rather than a wrong number.
      syncDockFade();
      restoreAskState(askKept);
      // storage is the backstop when the snapshot was empty (reload, or he
      // navigated away and back). Live text from the snapshot already wins.
      bindAskDraft();
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
if (!MIST_ON) document.body.classList.add('mistoff');   // #449: see crossfade
(function () {                              // initial view from the URL
  const r = routeOf(location);
  navigate(r.name, r.param,
           { push: false, transition: false, q: r.q, mode: r.mode });
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
  /* `note` is `claim` with the LIFECYCLE — a report of something that already
     happened, so it holds for ~5s and then departs on the atmospheric exit
     rather than sitting in the chrome until something else replaces it. The
     composer has no use for it (its success text is fixed, and its failures
     are claims that must not depart gently while still false); #284's copy
     confirmation does, for both outcomes, because a copy that failed a second
     ago is history and not a standing claim about the world. */
  return {begin,claim:(text,ok=false)=>show(text,ok,false),
          note:(text,ok=true)=>show(text,ok,true),clear};
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
      // #459: popout #ptext binds to DraftStore as popout:main — same rules
      // as the main composer (save every input, restore into empty, clear
      // only on durable success). The popout document is a separate window
      // but shares the same origin localStorage partition.
      const pta = doc.getElementById('ptext');
      const popLid = DraftStore.id('popout', 'main');
      if (pta) {
        DraftStore.bind(pta, popLid);
        DraftStore.restore(popLid, pta);
      }
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
          // raw-fetch site: owns its Response, so reads the verdict here. A
          // rejected 202 (r.ok true) would otherwise clear his thought (#136).
          const pv = await writeVerdict(r);
          // attach for isDurable (same shape postJSON sets)
          r._dwv = pv;
          if (DraftStore.isDurable(r)) {
            if(!attempt.success())return;
            doc.getElementById('ptext').value = '';
            DraftStore.clear(popLid);
          } else {
            const why = (pv.rejected && pv.reason && REJECT_WHY[pv.reason])
                     || QSEND_WHY[pv.status];
            attempt.claim(why ? `not written — ${why}. your words are kept`
                              : 'rejected (' + r.status + ')');
          }
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
  /* Composer drafts ride DraftStore as composer:main. draftKey keeps the
     pre-module key shape string (`'dw:draft:' + tgt`) so dual-read and the
     partition unit test still name the same contract; the module owns the
     actual write. */
  const draftKey = () => {
    const tgt = (typeof data !== 'undefined' && data && data.target) || '';
    return tgt ? 'dw:draft:' + tgt : '';
  };
  const composerLid = () => DraftStore.id('composer', 'main');
  function saveDraft() {
    // touch draftKey so the partition string stays live in PAGE for tests
    if (!draftKey()) return;
    const t = document.getElementById('cmdtext');
    if (!t) return;
    DraftStore.save(composerLid(), t.value,
      t.value ? { kindHint: activeKind } : undefined);
  }
  /* ONLY on a successful send, which is the whole contract. A draft that is
     cleared on close, on blur, or on a rejected POST is a draft that
     disappears at exactly the moments he most needs it back. */
  function clearDraft() {
    if (!draftKey()) return;
    DraftStore.clear(composerLid());
  }
  function restoreDraft() {
    const t = document.getElementById('cmdtext');
    if (!draftKey() || !t || t.value) return;   // a live box outranks storage (#118)
    const rec = DraftStore.get(composerLid());
    if (!rec || !rec.text) return;
    t.value = rec.text;
    fitText(t, false);                        // #177: size the box to the restored draft, snapped
    // the kind travels with the text, because the kind is WHERE THE TEXT GOES
    // (#103's rule for a card's mode, one surface over). Validated against the
    // live vocabulary: a plugin's command can disappear between sessions, and
    // silently sending his words as the wrong kind is worse than defaulting.
    const k = rec.meta && rec.meta.kindHint;
    if (k && COMMANDS.some(c => c.kind === k)) setKind(k);
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
      if (ev === 'input') {
        saveDraft();
        fitText(document.getElementById('cmdtext'), true);  // #177: grow with the thought
      }
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
      const cv = r && r._dwv;
      if (r && cv && cv.landed) {
        if(!attempt.success())return;
        const plus = document.getElementById('cmdplus');
        if (plus) { const b = plus.getBoundingClientRect();
          ripple(b.left + b.width / 2, b.top + b.height / 2); }
        document.getElementById('cmdtext').value = '';
        clearDraft();  // unguarded ON PURPOSE: already inside cv.landed, and
        // an isDurable() here would read as a gate while gating nothing (#163)
        // #337: a landed command does not keep its kind — the composer
        // decays back to the one sticky kind, so his NEXT message is never
        // silently promoted to the authority of the one he just sent.
        // Read the property off the LIVE table (COMMANDS is a `let`; plugin
        // kinds join it, #86), and absent means NOT sticky, so no kind is
        // named here and a new one is not a third place to remember. The
        // decay rides setKind — the indicator's existing slide, not a
        // second gesture (transitions.md).
        const sent = COMMANDS.find(c => c.kind === kind);
        if (sent && !sent.sticky) setKind('add-idea');
        fitText(document.getElementById('cmdtext'), true);  // #177: shrink back, the same gesture reversed
        // he may already have started typing again while the POST was in
        // flight, before there was any timer to cancel. Courtesy is NOT
        // the confirmation hold (#291): that is CMD_CONFIRM_HOLD_MS on the
        // controller, independent of whether the panel stays open.
        cancelDismiss();
        if (!composing) dismissT = setTimeout(closeCmd, CMD_DISMISS_MS);
      } else if (r) {
        // a rejected 202 (r.ok true, body rejected — E5) used to fall into the
        // success branch and clear his thought; the verdict routes it here and
        // names the reason in his voice. transitions.md: a falsehood replaces
        // success immediately and does not depart slowly.
        const why = (cv && cv.rejected && cv.reason && REJECT_WHY[cv.reason])
                 || (cv && QSEND_WHY[cv.status]);
        attempt.claim(why ? `not written — ${why}. your words are kept`
                          : 'rejected (' + r.status + ')');
      } else attempt.claim('no connection');   // postJSON returns null on throw
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
    // body.dev is the yield signal for the project wordmark (#435): the CSS
    // rule that cedes the overlay's column keys on it, so removing this class
    // (or never setting it) is the production line that makes the overlap
    // guard fail. The overlay itself still mounts exactly as before.
    doc.body.classList.add('dev');
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
      drawSpark();
      if (!fpsT) fpsT = ms;            // anchor the first window, else a
                                       // slow first paint reports a bogus
                                       // rate (count over a long elapsed)
      if (ms - fpsT >= 100) {
        // fps over the elapsed window, scaled to a per-second rate: the
        // window shrunk from 1s to 100ms for a livelier readout, so the
        // raw count would show "6 fps" at 60 real fps.
        const elapsed = ms - fpsT;
        fpsEl.textContent = Math.round(fpsN * 1000 / elapsed) + ' fps';
        // measured work per frame: real GPU time when the timer is live,
        // else CPU-side draw (JS + GL submission — understates true GPU).
        const useGpu = gts.length > 0, work = useGpu ? gts : dts;
        dtEl.textContent =
          avgOf(work).toFixed(1) + '·' + Math.max(0, ...work).toFixed(1) +
          'ms ' + (useGpu ? 'gpu' : 'draw');
        ftEl.textContent =
          avgOf(fts).toFixed(1) + 'ms avg · ' +
          Math.max(0, ...fts).toFixed(1) + 'ms worst';
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
# Template only — posture closed sets are injected by `_get_page()` on first
# access so `import lint` (which does `import watch` at its top) never meets a
# half-initialised lint. External code reads `watch.PAGE` via `__getattr__`.
_PAGE_TEMPLATE = page_shell('dreamwork watch', APP_BODY,
                  "const CORE_COMMANDS = " + json.dumps(list(COMMANDS)) + ";\n"
                  + "let COMMANDS = CORE_COMMANDS.slice();\n"
                  + "const TINTS = " + json.dumps(TINTS) + ";\n"
                  + "const TINT_DEFAULT = " + json.dumps(TINT_DEFAULT) + ";\n"
                  + "const RUN_MODES = " + json.dumps(list(RUN_MODES)) + ";\n"
                  + "const RUN_MODE_DEFAULT = "
                  + json.dumps(RUN_MODE_DEFAULT) + ";\n"
                  + "const RUN_MODES_PLANNED = "
                  + json.dumps(list(RUN_MODES_PLANNED)) + ";\n"
                  + "const RUN_ARM_MS = " + json.dumps(RUN_ARM_MS) + ";\n"
                  + "const DEPLOY_WAIT_MS = " + json.dumps(DEPLOY_WAIT_MS) + ";\n"
                  + "const RUN_MODE_DESC = "
                  + json.dumps(RUN_MODE_DESC, ensure_ascii=True) + ";\n"
                  + "/*__POSTURE_VOCAB__*/"
                  + COMPONENTS_JS + VIEWS_JS + FAVICON_JS + SHADER_JS
                  + ROUTER_JS + COMMAND_JS)

_PAGE_CACHE = None


def _get_page():
    """HTML shell with posture vocab injected from lint (single source)."""
    global _PAGE_CACHE
    if _PAGE_CACHE is not None:
        return _PAGE_CACHE
    lint = _posture_vocab()
    vocab = (
        "const POSTURE_STOPS_PACE = "
        + json.dumps(list(lint.POSTURE_STOPS_PACE)) + ";\n"
        + "const POSTURE_STOPS_ASKING = "
        + json.dumps(list(lint.POSTURE_STOPS_ASKING)) + ";\n"
        + "const POSTURE_STOPS_DELIVERY = "
        + json.dumps(list(lint.POSTURE_STOPS_DELIVERY)) + ";\n"
        + "const DELEGATION_POSTURES = "
        + json.dumps(list(lint.DELEGATION_POSTURES)) + ";\n"
        + "const POSTURE_DELEGATION_UI_MAX = "
        + json.dumps(POSTURE_DELEGATION_UI_MAX) + ";\n"
        + "const POSTURE_PACE_DESC = "
        + json.dumps(POSTURE_PACE_DESC, ensure_ascii=True) + ";\n"
        + "const POSTURE_ASKING_DESC = "
        + json.dumps(POSTURE_ASKING_DESC, ensure_ascii=True) + ";\n"
        + "const POSTURE_DELEGATION_DESC = "
        + json.dumps(POSTURE_DELEGATION_DESC, ensure_ascii=True) + ";\n"
        + "const POSTURE_DELIVERY_DESC = "
        + json.dumps(POSTURE_DELIVERY_DESC, ensure_ascii=True) + ";\n"
    )
    _PAGE_CACHE = _PAGE_TEMPLATE.replace("/*__POSTURE_VOCAB__*/", vocab)
    return _PAGE_CACHE


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


# ── #351: syntax highlighting at /file, on #339's scanner ─────────────────
# His ask, typed from /file?p=lint.py: "syntax highlighting for source code
# files". The tokeniser is review_artifact.py's (#339: tok- spans, no script,
# round-trip proved byte-exact) — one highlighter, consumed here through its
# public `highlight()`, never re-implemented.
#
# THE LANGUAGE COMES FROM THE EXTENSION, and an unknown one renders PLAIN.
# #339's rule is never-guess: a misdetected language colours code wrongly,
# which is worse than not colouring it. An artifact block DECLARES its
# language; a file path can only state one, so the map below is the whole of
# what is coloured — a file whose extension is not here is served without
# markup, exactly as before. Every value must be a language the scanner
# actually supports (the test derives that set from review_artifact rather
# than restating it).
_FILE_LANG = {
    ".py": "python",
    ".json": "json",
    ".sh": "bash", ".bash": "bash",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".html": "html", ".htm": "html",
    ".sql": "sql",
}

# CACHING IS A DECISION, NOT AN INHERITANCE. #339 tokenises at build time
# because an artifact is built once and frozen; /file renders ON REQUEST, so
# the same work would repeat for a result that cannot change per file
# version. The cache is keyed by path and validated by (mtime_ns, size) —
# the same staleness predicate the whole dashboard already trusts (/mtime's
# poll wakes the page on exactly that signal), and stat is cheap beside the
# read the response does anyway. A content digest was the alternative and is
# deliberately not used: it costs a full read of every file on every request
# only to detect the same change mtime already names, and "rewritten with an
# identical mtime and size" is the edge the live-reload mechanism has always
# accepted. Bounded, and a stale entry is only ever a highlight one edit
# behind — the bytes served are read fresh every time, never cached.
_FILE_HL_CACHE_MAX = 32
_file_hl_cache = {}


def file_highlight_html(full, text):
    """Highlighted <pre> markup for a served text file, or None when the
    extension names no supported language (the caller then renders plain).

    `text` is the string /filedata is already serving (read fresh per
    request); the cache only spares re-tokenising it. The markup is built by
    wrapping the escaped source in the one block shape review_artifact's
    highlighter consumes and taking the result back — the scanner's own
    round-trip check (it refuses partial coverage) is what makes that safe.
    """
    ext = os.path.splitext(full)[1].lower()
    lang = _FILE_LANG.get(ext)
    if lang is None:
        return None
    try:
        st = os.stat(full)
    except OSError:
        return None
    ent = _file_hl_cache.get(full)
    if ent is not None and ent[0] == st.st_mtime_ns and ent[1] == st.st_size:
        return ent[2]
    doc = ('<pre><code class="language-%s">%s</code></pre>'
           % (lang, html.escape(text, quote=False)))
    out = _hl_document(doc)
    if len(_file_hl_cache) >= _FILE_HL_CACHE_MAX:
        _file_hl_cache.clear()
    _file_hl_cache[full] = (st.st_mtime_ns, st.st_size, out)
    return out


def read_bytes(path):
    # Legacy whole-file reader. /filebytes no longer calls this (#354): a
    # 1GB target file used to become a 1GB resident `bytes` here. Kept only
    # as an explicit footgun — do not reattach it to a serving path. Prefer
    # stat + open + FILEBYTES_CHUNK reads (see Handler._send_bytes).
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


# #354: /filebytes streams with a fixed read buffer. Peak memory is this
# constant, not the file size. An <img src="/filebytes…"> sends no Range
# header, so chunked streaming — not 206 — is what stops the 1GB buffer.
FILEBYTES_CHUNK = 65536


# ── #336: serving an image rather than its bytes as mojibake ──────────────
# His report was a /file view of a 150KB evidence PNG rendering as U+FFFD
# soup: /filedata did read_text (UTF-8, errors=replace) and the client
# painted the result in a <pre>. The fix serves raster images as bytes from
# a separate endpoint, and the SECURITY-LOAD-BEARING decision is which types
# that endpoint will inline:
#
# A raw-bytes endpoint that echoes a client-supplied or extension-guessed
# Content-Type turns any .svg or .html in the tree into stored XSS against
# the dashboard's own origin — and #275/#276 are actively considering LAN
# and public exposure, so this is not theoretical. So the inline allowlist
# is RASTER ONLY, the Content-Type is taken from THIS table (never
# reflected), and SVG is deliberately OUT. The next reader will want to
# add SVG; do not, because the moment it is inline it is XSS.
#
# Detection is by EXTENSION AND MAGIC BYTES, because an extension alone is
# a guess and a guess is what produced the bug. A .png whose bytes do not
# begin with the PNG signature is not served as image/png; an .html whose
# bytes do is not served as image either, because .html is not in the
# allowlist. BOTH must agree.
INLINE_IMAGE_EXTS = ("png", "jpg", "jpeg", "gif", "webp", "avif")
_INLINE_IMAGE_MIME = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "gif": "image/gif", "webp": "image/webp", "avif": "image/avif",
}
# AVIF is an ISO BMFF container; there is no fixed magic prefix, only the
# ftyp box (bytes 4-8 == b'ftyp') whose major brand identifies the codec.
# These are the brands a browser will decode as AVIF; anything else with a
# .avif extension fails magic and is served as a download.
_AVIF_BRANDS = (b"avif", b"avis", b"mif1")


def _magic_matches(ext, head):
    """True iff `head` begins with the byte signature `ext` claims."""
    if ext in ("png",):
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in ("jpg", "jpeg"):
        return head[:3] == b"\xff\xd8\xff"
    if ext == "gif":
        return head[:6] in (b"GIF87a", b"GIF89a")
    if ext == "webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if ext == "avif":
        return head[4:8] == b"ftyp" and head[8:12] in _AVIF_BRANDS
    return False


def detect_file_kind(full):
    """'image' if `full` is an inline-safe raster, 'binary' for any other
    non-text file, 'text' otherwise. None if the file cannot be inspected.

    Pure over an extant path. The image verdict requires BOTH an allowlisted
    extension AND matching magic bytes (#336); the binary verdict is taken
    from the head so a UTF-16 file with a BOM does not read as 'text' on a
    technicality, and so a .png containing ASCII does not get the image
    treatment by virtue of its extension."""
    try:
        with open(full, "rb") as f:
            head = f.read(32)
    except OSError:
        return None
    ext = full.rsplit(".", 1)[-1].lower() if "." in full else ""
    if ext in INLINE_IMAGE_EXTS and _magic_matches(ext, head):
        return "image"
    if _looks_binary(head):
        return "binary"
    return "text"


def _looks_binary(head):
    """A NUL byte, or a C0 control other than tab/CR/LF, means this is not
    text. UTF-8's multibyte sequences are all >= 0x80, so they pass."""
    for b in head:
        if b == 0 or b == 0x7f or (b < 0x20 and b not in (0x09, 0x0a, 0x0d)):
            return True
    return False


def inline_image_mime(full):
    """The Content-Type /filebytes serves for an allowlisted raster, taken
    from the extension. Never client-supplied; never includes svg."""
    ext = full.rsplit(".", 1)[-1].lower() if "." in full else ""
    return _INLINE_IMAGE_MIME.get(ext, "application/octet-stream")


def safe_attachment_filename(name):
    """`filename=` for Content-Disposition, with nothing in it that can
    break an HTTP header or escape the quotes: ASCII alphanumerics plus
    .-_ only, capped. resolve_confined already stripped path separators;
    this is belt-and-braces against a quote or a control char, because a
    malformed header is worse than a drab name."""
    base = os.path.basename(name or "")
    clean = "".join(
        c if (c.isalnum() or c in ".-_") and ord(c) < 128 else "_"
        for c in base).strip("._")
    return (clean or "download")[:128]


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


# ── page-triggered deploy (#462 increment 2) ──────────────────────────────
#
# He authorised the dashboard to run `just deploy` (2026-07-29 03:46, `rec`).
# The loaded document keeps polling /mtime; success is a new GENERATION, not
# the POST response — the server may die mid-flight when the deploy stops the
# listening snap. Failure of the runner (or a deploy that never restarts)
# surfaces as DEPLOY_WAIT_MS with no generation change on the client.
#
# Loopback only: trusted-LAN serving exists, and this action must refuse a
# non-loopback peer. Single-flight: two clicks must not run two deploys.
# Tests inject `_deploy_runner` so a check never actually runs `just deploy`.

_deploy_lock = threading.Lock()
_deploy_inflight = False
# Optional override: callable(target) -> None. Tests set this; production
# leaves it None and runs `just deploy` from the watched target.
_deploy_runner = None


def peer_is_loopback(client_address):
    """True when the TCP peer is a loopback address (IPv4 or IPv6).

    The deploy action is host-bound: only the machine running the dashboard
    may trigger it. Trusted-LAN Host/Origin gates are not authentication, so
    this is the additional peer check for a command that restarts the server.
    """
    host = (client_address or ("", 0))[0]
    try:
        return ipaddress.ip_address(host).is_loopback
    except (ValueError, TypeError):
        return False


def _default_deploy_runner(target):
    """Run `just deploy` in `target` (the watched project: justfile + port).

    May kill this process — that is the recipe's job. stdout/stderr are
    captured for diagnostics on the rare path where the process survives.
    """
    try:
        subprocess.run(
            ["just", "deploy"],
            cwd=str(target),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def start_deploy(target):
    """Claim the single-flight slot and start the runner in a daemon thread.

    Returns True if the runner was scheduled, False if a deploy is already
    in flight. The POST returns before the runner finishes (and possibly
    before this process dies).
    """
    global _deploy_inflight
    with _deploy_lock:
        if _deploy_inflight:
            return False
        _deploy_inflight = True

    def run():
        global _deploy_inflight
        try:
            runner = _deploy_runner if _deploy_runner is not None \
                else _default_deploy_runner
            runner(target)
        finally:
            with _deploy_lock:
                _deploy_inflight = False

    threading.Thread(target=run, daemon=True, name="watch-deploy").start()
    return True


def deploy_inflight():
    """Whether a deploy is currently claimed (tests + diagnostics)."""
    with _deploy_lock:
        return _deploy_inflight


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
# #331: ONE definition of an ids-only bold span, consumed by every reader.
# The ledger joins several ids inside one bold span three ways — `**#5/#6**`,
# `**#121 #123**`, `**#157 + #222 + #223**` — and `/` only used to be parsed,
# so the space- and `+`-joined spans were invisible to every reader (19 ids
# lost). This core is the single place that decides what "ids only" means;
# `LEDGER_ENTRY` (head) and `LEDGER_COMBINED_MENTION` (anywhere) are built
# from it, and `lint.LEDGER_ID` / `status_sync.LEDGER_HEAD` import and reuse
# it rather than restating it — a fourth reader cannot be written wrong.
#
# Joiners are `[ \t]`, never `\s`: the ledger is line-structured, and a span
# that could run across a newline would be a new bug in place of the old one.
# Comma is NOT a joiner: `**#392, #401, #405**` is a prose list, not three ids,
# and it stays inert at the pattern level — `**#96 stage 1**` (a section title)
# and `**#392a**` (a sub-id) do too, because after the first `#\d+` the next
# token must be `/`/`+` (with optional blanks) or a blank run and another `#`,
# never a word, a comma, or a letter.
# IDS_ONLY_SPAN is defined near RUN_MODES (above) so lint can import watch
# mid-module for #445 posture vocab. Ledger uses that same name — one copy.
# `lint.py`'s `LEDGER_ID` and `status_sync.py`'s `LEDGER_HEAD` are built from
# it and a test asserts all three heads share one pattern.
# What counts as an entry is one rule and it must have one copy: the linter
# already learned this the hard way (3073055), holding a wider copy of the
# priority-marker rule than the parser and blessing three typos.
LEDGER_ENTRY = re.compile(rf"^- \*\*({IDS_ONLY_SPAN})\*\*", re.M)
# Pre-#399 landed readers: bare bold spans anywhere in `## Recently landed`.
# Kept for regression reconstructions in tests; `_landed_ids` no longer uses
# them (#399). A bare `**#N**` is a REFERENCE (related:, filed-as, prose).
LEDGER_MENTION = re.compile(r"\*\*#(\d+)\*\*")
# LEDGER_ENTRY is combined-aware: its bold span is ids only (`#7` or
# `#7/#8`), so a combined entry HEAD (`- **#7/#8**`) names EVERY id in it,
# while a prose span like `- **#7 stage 1**` (ids followed by non-id prose,
# then `**`) still does not match — `**` must follow the id-span immediately,
# exactly as the narrow rule always required. A combined head under `## Open`
# contributes all its ids to the open set (#315, the open half of #301).
#
# This widens in LOCKSTEP with lint.py's LEDGER_ID and check_ledger_sections:
# the linter cross-checks the size of parse_ledger's open-id set against its
# OWN open-id count, and that count uses LEDGER_ID. Widening one reader alone
# makes the two DISAGREE on any ledger holding a combined open entry — proven
# by watching test_combined_ids_all_old_are_exempt go red — so the three move
# in one commit or not at all. `test_ledger_entry_rule_has_exactly_one_copy`
# still pins the two patterns identical; it did not need editing.
#
# LEDGER_MENTION stays narrow and test-only: it is the pre-#304 landed reader,
# reconstructed verbatim in test_lint.py's regression. LEDGER_COMBINED_MENTION
# (ids-only bold span anywhere) is a production landed reader again from #399b:
# `_landed_ids` walks it but skips an entry's INDENTED body and any
# `related:`/`filed as`/`also-landed:` field (LANDED_REF_FIELD), so the
# historical column-0 inline form lands while a `related:` marker (#367) does
# not. #399 had retired it as too wide; the body+field guard is what makes the
# width safe, and the discriminating-pair reds prove neither side slides.
# Built from IDS_ONLY_SPAN (#331): the mention form is the same ids-only span
# as the head form, just unanchored, so one core defines both.
LEDGER_COMBINED_MENTION = re.compile(rf"\*\*({IDS_ONLY_SPAN})\*\*")
# #399b: `·`-fields whose bold id is a REFERENCE, not a landing. `related:`
# (lint.check_related_markers requires it; #367) and `filed as` (a filing
# cross-ref) never land. `also-landed:` is listed so the generic mention pass
# skips it — its ids land via ALSO_LANDED_MARKER, `·`-anchored, and
# mid-sentence "also-landed: **#9**" prose must not mint one (#395 class).
LANDED_REF_FIELD = re.compile(r"\b(?:related|also-landed)\s*:|\bfiled\s+as\b", re.I)
# #399: additional ids closed by the same landed entry, explicit like related:.
# Field-anchored so mid-sentence "also-landed: **#9**" prose is not a claim.
ALSO_LANDED_MARKER = re.compile(
    r"(?:^|[·])\s*also-landed:\s*\*\*([^*]*?)\*\*", re.I)
# A SECTION is opened by a heading LINE and by nothing else (#304). These were
# once located with an unanchored `text.split("## Open", 1)`, which let any
# entry whose PROSE quoted a heading become the split point — and that is not
# adversarial input: it happened twice within ten minutes while writing ledger
# entries about this very parser, the second time in the entry that filed the
# bug. The ledger read 2 open / 187 landed against a true 105 / 84, every
# derived number on the deployed dashboard was wrong, and `lint.py` called the
# file clean throughout, because it counts entries without splitting sections
# at all. Anchored, an entry can say `## Open` as freely as it says anything
# else. Strip-equality matches lint.py's own `heads` rule, so the two readers
# cannot disagree about where a section begins.
LEDGER_SEC_OPEN = re.compile(r"^[ \t]*## Open[ \t]*$", re.M)
LEDGER_SEC_LANDED = re.compile(r"^[ \t]*## Recently landed[ \t]*$", re.M)


def _ledger_section(text, pattern):
    """`(before, after)` around the first heading LINE matching `pattern`,
    or `None` when the file has no such heading."""
    m = pattern.search(text)
    return (text[:m.start()], text[m.end():]) if m else None
# A human steer is stamped `· **human 17:45**` by the coordinator on some
# entries. Provenance is NOT read from the working tree: a task's origin is
# a fact about its ARRIVAL, so it is classified from the FIRST snapshot in
# which its id appears (#216), inside the same walk the series below makes.
# The first-sight grammar — ENTRY_HEAD, ENTRY_ID, ORIGIN_MARK,
# KNOWN_ORIGINS, ledger_entries, entry_origins — is ledger_parse.py's
# (#352): one module, imported at the top of this file, no second copy
# here for a test to have to pin.
# The bucket ladder: the smallest step that keeps the chart under this many
# columns. A fixed step would give one column on a young ledger and four
# hundred on an old one.
BURN_COLUMNS = 24
BURN_STEPS = (3600, 4 * 3600, 86400, 7 * 86400, 28 * 86400)

BURN_OK = "ok"
BURN_NONE = "no ledger"    # this project keeps no versioned task ledger
BURN_ERROR = "error"       # git failed; explicitly NOT "no history"

_LEDGER_SNAPS = {}         # (rev, tree-relative path) -> parsed snapshot
_LEDGER_CACHE = {}         # (target, head) -> the whole answer


def parse_ledger(text):
    """One ledger snapshot as `(open ids, landed ids)`.

    An id under `## Open` is an entry HEAD. An id under `## Recently landed`
    lands when it is that section's entry HEAD, a `· also-landed:` field
    (#399), or a BARE inline mention at the start of a line — the
    historical `**#N** <prose> (sha)` form that `ledger_series` walks in old
    revisions (#399b). It does NOT land because an entry's indented body
    bolded it: `related:`, `filed as **#N**`, and prose cross-refs are
    references, and #399b reads that body as reference territory so the
    `#367` false landing stays closed. Both reads are combined-aware: a head
    like `- **#7/#8**` names EVERY id in its ids-only bold span, while a
    prose span like `**#96 stage 1**` stays inert. The open read widens in
    lockstep with lint.check_ledger_sections — see LEDGER_ENTRY's comment.
    """
    if not text:
        return set(), set()
    opened = _ledger_section(text, LEDGER_SEC_OPEN)
    if opened is None:
        return set(), set()
    split = _ledger_section(opened[1], LEDGER_SEC_LANDED)
    open_text, landed_text = split if split else (opened[1], "")
    return (_open_ids(open_text), _landed_ids(landed_text))


def _open_ids(text):
    """Every id named in an open-section entry HEAD, combined-aware.

    A combined head (`- **#7/#8**`) names TWO ids; LEDGER_ENTRY captures the
    ids-only bold span and ENTRY_ID reads each id in it. Returns strings,
    matching `_landed_ids`' shape — `ledger_series` and the origin walk key
    on string ids throughout.
    """
    ids = set()
    for m in LEDGER_ENTRY.finditer(text):
        ids.update(ENTRY_ID.findall(m.group(1)))
    return ids


def _landed_ids(text):
    """Ids this landed section marks as done.

    Three shapes land an id, and ONLY these:
      - the entry head (`- **#N**` or combined `- **#N/#M**`);
      - a `· also-landed: **#X, #Y**` field — extra ids closed by the same
        commit (#399), `·`-anchored so mid-sentence prose cannot claim one;
      - a BARE inline mention at the START OF A LINE — the HISTORICAL form,
        `**#N** <prose> (sha)` written as a column-0 paragraph with no entry
        heads and no `·`-fields. `ledger_series` walks these old revisions,
        so a landed reader that misses them makes the burndown lose every
        completion older than the last groom.

    #399 closed a real hole, and #399b keeps it closed while reopening that
    historical form. A `related: **#367**` marker in a landed entry is a
    CROSS-REFERENCE, and the pre-#399 reader scanned every bold span, so
    `#367` appeared landed and `check_landed_asks` told the coordinator to
    fold the human's still-open ask. #399's answer — entry heads only — went
    too far: it read the historical inline form as zero landings too. #399b
    threads the needle by reading an entry's INDENTED body as reference
    territory. That body is where `related:`, `filed as`, and prose
    cross-refs ("see **#N**") live, and the historical form has no such body
    — it is pure column-0 prose, so every mention in it lands. A `related:` /
    `filed as` / `also-landed:` marker is excluded BY NAME as well, so a
    head line that carries one inline (`- **#N** — … · related: **#X**`)
    cannot re-open the `#367` hole, and `also-landed:` is left to its own
    field-anchored marker below.

    Returns strings, matching the shape `ledger_series` and the origin walk
    key on throughout.
    """
    ids = set()
    for m in LEDGER_COMBINED_MENTION.finditer(text):
        line_start = text.rfind("\n", 0, m.start()) + 1
        # An entry's indented continuation body is reference territory —
        # `related:`, `filed as`, "see #N" — never a bare landing.
        if text[line_start] in " \t":
            continue
        # A `·`-field on a head line is a reference (related:/filed as) or
        # owned by its own marker (also-landed:), never a bare landing.
        if LANDED_REF_FIELD.search(text[line_start:m.start()]):
            continue
        ids.update(ENTRY_ID.findall(m.group(1)))
    for m in ALSO_LANDED_MARKER.finditer(text):
        ids.update(ENTRY_ID.findall(m.group(1)))
    return ids


# ── hand-offs: the delivery half of the single-writer rule (#381) ──────
# A foreign session that lands work it does not own the ledger for appends a
# line under `## Pending`; the coordinator folds it and appends `→ folded`
# under `## Folded`. Nothing moves; correlation is by id. This parser is the
# ONE definition of the shape — lint imports it rather than keeping a second
# copy, for the reason every other shared reader does (#137: two copies drift).
# `·` is U+00B7; the grammar is `·`-separated on purpose.
#
# Id vocabulary (#401): plain `#392`, sub-id `#392a`, combined `#367/#392`.
# The earlier `#(\d+)` grammar dropped sub-ids and combined heads from pending
# AND from the malformed fallback (same blind axis). HANDOFF_BARE_RE matches
# any bolded-id entry head so an unrecognised shape is LOUD, not silent.
# HANDOFF_ID_TOKEN is the accepted id forms; BARE is intentionally wider.
# Written form is `#367/#392` (hash before each number). Capture normalises to
# `367/392` so display `#{nid}` stays one hash, not `##367/#392`.
HANDOFF_ID_TOKEN = r"((?:\d+[a-z]?)(?:/#\d+[a-z]?)*)"
# One or more backticked shas after `landed` (#415 grammar / #427 parser).
# Group 2 is the whole `` `sha` [`sha`…] `` run; split with _handoff_pending_shas.
HANDOFF_PENDING_RE = re.compile(
    r"^-\s+\*\*#" + HANDOFF_ID_TOKEN +
    r"\*\*\s*·\s*landed\s+((?:`[^`\n]+`\s*)+)\s*·\s*.+?\s*·\s*by\s+(.+?)\s*$")
HANDOFF_FOLDED_RE = re.compile(
    r"^-\s+\*\*#" + HANDOFF_ID_TOKEN + r"\*\*\s*→\s*folded\s*\(([^)]+)\)")
# ANY bolded head after `- **#…**` — wider than the accepted token so a shape
# the full grammar rejects still reaches malformed (#401 defect 2).
HANDOFF_BARE_RE = re.compile(r"^-\s+\*\*#([^*\n]+)\*\*")


class HandoffPending(tuple):
    """One pending hand-off: unpacks as ``(id, sha, claimer)``.

    ``sha`` is the first (landing) sha so ``lint.check_handoffs``'s
    ``for nid, sha, claimer in pending`` and existing triple-equality tests
    stay valid without a lint change. ``shas`` is the full one-or-more list
    (#427 closes the #415 grammar split: lint already accepted multi-sha;
    this parser now does too).
    """

    def __new__(cls, nid, shas, claimer):
        if isinstance(shas, str):
            shas = (shas,)
        else:
            shas = tuple(shas)
        if not shas:
            raise ValueError("hand-off requires at least one sha")
        inst = tuple.__new__(cls, (nid, shas[0], claimer))
        inst._all_shas = shas
        return inst

    @property
    def id(self):
        return self[0]

    @property
    def sha(self):
        return self[1]

    @property
    def claimer(self):
        return self[2]

    @property
    def shas(self):
        return self._all_shas


def _normalise_handoff_id_token(raw):
    """Strip per-segment `#` so `#367/#392` capture becomes `367/392`."""
    if not raw:
        return raw
    return "/".join(p.lstrip("#") for p in raw.split("/"))


def _handoff_pending_shas(match):
    """All backticked shas from a HANDOFF_PENDING_RE match (group 2)."""
    return tuple(s.strip() for s in re.findall(r"`([^`\n]+)`", match.group(2))
                 if s.strip())


# Backticked hex git shas cited in a fold note (#409). Fold lines carry the
# landing sha in freeform prose — `citing \`f2c950e\``, `merged \`cb476a7\`` —
# never a parsed field. This reads what is there; an id ref (`\`#401\``) or a
# date is not hex, so it is excluded. {7,40} is short..full git sha length.
_HANDOFF_FOLD_SHA_RE = re.compile(r"`([0-9a-fA-F]{7,40})`")


def _handoff_fold_shas(fold_note):
    """Lowercased hex shas a fold note cites, in written order (#409).

    Returns ``()`` when the note cites no sha, so correlation can fall back
    to id-only — most folds cite the MERGE commit, not the work sha a pending
    landed, and a fold matching no pending must not resurface one.
    """
    return tuple(m.group(1).lower()
                 for m in _HANDOFF_FOLD_SHA_RE.finditer(fold_note or ""))


class FoldedHandoffs(set):
    """Folded id tokens, plus the shas each fold cites (#409).

    Behaves as the set of folded id tokens for callers that correlate by id
    alone (lint's ``nid in folded_ids`` / ``len(folded_ids)`` — unchanged), and
    carries ``shas_by_id``: id → set of lowercased shas cited in that id's
    fold note(s). ``pending_handoff_records`` uses it for (id, sha) correlation.
    """

    def __init__(self):
        super().__init__()
        self.shas_by_id = {}


def handoff_parent_ids(token):
    """Parent ledger id(s) for correlating a hand-off against `## Open`.

    Accepts the full hand-off id vocabulary and returns the numeric parent
    id(s) as strings (matching `parse_ledger`'s open set):

      ``392``      → ``['392']``
      ``392a``     → ``['392']``
      ``367/392``  → ``['367', '392']``

    Explicit and named — do **not** leave this to ``ENTRY_ID``'s incidental
    letter-stripping (``#392a`` → ``392`` silently wherever that atom runs).
    ``ENTRY_ID`` itself is out of scope here (#401); changing it would touch
    every ledger/related/origin reader that assumes digit-only captures.
    """
    if not token:
        return []
    out = []
    for part in str(token).split("/"):
        part = part.lstrip("#").strip()
        m = re.match(r"^(\d+)[a-z]?$", part)
        if m:
            out.append(m.group(1))
    return out


def parse_handoffs(text):
    """`(pending, folded_ids, malformed)` from `.dreamwork/handoffs.md`.

    `pending` is a list of `HandoffPending` rows — each unpacks as
    `(id, sha, claimer)` (ids as strings, no leading `#`; plain/sub-id/
    combined tokens kept as written; `sha` is the **first** landing sha) and
    also exposes `.shas` for the full one-or-more list (#415 / #427).
    `folded_ids` is the set of id tokens a fold record names; `malformed` is
    `(id, line)` for entry heads the grammar does not recognise **or** that
    sit in the wrong section (#401 / #406). Format validation is what lint
    acts on.

    Sections match literally — `## Pending` and `## Folded` — the way
    `## Open` does. A well-formed Pending line belongs under `## Pending` and
    a fold under `## Folded`; a bolded-id line in the wrong section (or
    outside both) is malformed, not silent. The malformed path runs for every
    section so a Pending-shaped line under `## Folded` cannot vanish (#406).
    """
    pending, folded_ids, malformed = [], FoldedHandoffs(), []
    section = None
    for ln in (text or "").splitlines():
        s = ln.strip()
        if s == "## Pending":
            section = "P"; continue
        if s == "## Folded":
            section = "F"; continue
        if s.startswith("## "):
            section = None; continue
        m_pend = HANDOFF_PENDING_RE.match(ln)
        m_fold = HANDOFF_FOLDED_RE.match(ln)
        m_bare = HANDOFF_BARE_RE.match(ln)
        if section == "P" and m_pend:
            shas = _handoff_pending_shas(m_pend)
            if not shas:
                # Zero-sha should not match the RE; if it somehow does, loud.
                if m_bare:
                    raw = m_bare.group(1).strip()
                    malformed.append((_normalise_handoff_id_token(raw), ln))
                continue
            pending.append(HandoffPending(
                _normalise_handoff_id_token(m_pend.group(1)),
                shas,
                m_pend.group(3).strip()))
        elif section == "F" and m_fold:
            nid = _normalise_handoff_id_token(m_fold.group(1))
            folded_ids.add(nid)
            # #409: capture the shas the fold cites so correlation can be by
            # (id, sha), not id alone. group(2) is only the TIMESTAMP parenthetical;
            # the sha lives in the freeform note after it (citing/merged …), so
            # scan the whole line. Backtick+hex filter excludes id refs / dates.
            fshas = _handoff_fold_shas(ln)
            if fshas:
                folded_ids.shas_by_id.setdefault(nid, set()).update(fshas)
        elif m_bare:
            # Wrong section, incomplete grammar, or unrecognised id shape —
            # all LOUD. Runs outside section P so a misfiled line is visible.
            raw = m_bare.group(1).strip()
            malformed.append((_normalise_handoff_id_token(raw), ln))
    return pending, folded_ids, malformed


def pending_handoff_records(text):
    """The hand-offs awaiting a fold, as the dashboard renders them (#381).

    Parsed once from the file the coordinator's tick and lint also read — never
    a mirror of `status.json`, which is the loop's own live claim. Inferring
    liveness from surviving artefacts is the wrong answer #363 proved, so the
    dashboard reads what was WRITTEN, not what a process claims. A pending
    hand-off is one whose id has no fold record. Returns `[]` when the file is
    absent or empty, the way a fresh target is.

    Each record carries ``sha`` (first / landing) and ``shas`` (one-or-more,
    written order) so a multi-commit landing surfaces every commit (#427).

    Correlation is by ``(id, sha)`` (#409): a fold citing a sha a pending
    landed consumes ONLY that sha, so a second landing under the same id is no
    longer silenced by the first one's fold. The fold-sha vocabulary is
    inconsistent — most folds cite the MERGE commit, not the work sha a
    pending landed — so the fallback is decided at the **id level**: when a
    fold's cited shas match no pending for that id, correlation falls back to
    id-only and a legitimately-folded hand-off cannot resurface. The cited
    shas ride on ``folded_ids.shas_by_id``; the ``row.id in folded_ids``
    membership test alone stays id-only (lint's contract, unchanged).
    """
    pending, folded_ids, _malformed = parse_handoffs(text)
    # Union of pending shas per id, so the fallback is an id-level decision:
    # a fold citing only a merge commit matches no pending and consumes all.
    pend_shas_by_id = {}
    for row in pending:
        pend_shas_by_id.setdefault(row.id, set()).update(
            s.lower() for s in row.shas)
    out = []
    for row in pending:
        if row.id in folded_ids:
            fold_shas = folded_ids.shas_by_id.get(row.id)
            row_shas = {s.lower() for s in row.shas}
            if (fold_shas is None                      # no citable sha: id-only
                    or not (fold_shas & pend_shas_by_id.get(row.id, set()))
                                                       # merge sha, no match: id-only
                    or (fold_shas & row_shas)):        # this sha was folded
                continue
        shas = list(row.shas)
        out.append({"id": row.id, "sha": shas[0], "shas": shas,
                    "claimer": row.claimer})
    return out


def _burn_step(span):
    for s in BURN_STEPS:
        if span <= 0 or span / s <= BURN_COLUMNS:
            return s
    return BURN_STEPS[-1]


def _series_from_model(arrived, landed, opencount, first_sight, latest,
                       commit_times, complete, now, step):
    """The bucketed chart + summary stats, shared by both read paths (#294 inc 7).

    Both the markdown git-walk and the store ``task_event`` query build the
    same first-sight model; this function turns it into the output dict the
    dashboard reads. Extracted verbatim from ``ledger_series``'s body so the
    two paths stay byte-identical — one bucket builder, not two (#218's
    one-source-of-truth rule).
    """
    out = {"state": None, "note": None, "buckets": [], "step": 0,
           "open": 0, "arrived": 0, "landed": 0, "from": 0, "to": 0}

    if not arrived:
        out["state"] = BURN_NONE
        out["note"] = ("no first-sight arrivals — nothing to chart yet, "
                       "which is not the same as nothing happening")
        return out

    first = min(commit_times) if commit_times else min(arrived.values())
    last = max((max(commit_times) if commit_times else min(arrived.values())),
               int(now if now is not None else time.time()))
    auto = _burn_step(last - first)
    if step not in BURN_STEPS:
        step = auto
    n = int((last - first) // step) + 1
    buckets = [{"t0": first + i * step, "arrived": 0, "landed": 0,
                "open": 0, "commits": 0}
               for i in range(n)]
    idx = lambda t: min(n - 1, max(0, int((t - first) // step)))  # noqa: E731
    for t in arrived.values():
        buckets[idx(t)]["arrived"] += 1
    for t in landed.values():
        buckets[idx(t)]["landed"] += 1
    for ct in commit_times:
        buckets[idx(ct)]["commits"] += 1
    carry = 0
    for b in buckets:
        inside = [v for t, v in opencount.items()
                  if b["t0"] <= t < b["t0"] + step]
        carry = inside[-1] if inside else carry
        b["open"] = carry

    out.update(state=BURN_OK, buckets=buckets, step=step,
               open=len(latest), arrived=len(arrived), landed=len(landed))
    out["from"] = first
    out["to"] = last
    ccounts = [b["commits"] for b in buckets]
    ccounts_sorted = sorted(ccounts)
    cn = len(ccounts_sorted)
    if cn == 0:
        cmed = 0
    elif cn % 2:
        cmed = ccounts_sorted[cn // 2]
    else:
        cmed = (ccounts_sorted[cn // 2 - 1] + ccounts_sorted[cn // 2]) // 2
    out["commit_total"] = sum(ccounts)
    out["commit_max"] = max(ccounts) if ccounts else 0
    out["commit_median"] = cmed
    out["commit_quiet"] = sum(1 for c in ccounts if c == 0)
    durations = sorted(landed[i] - arrived[i]
                       for i in landed if i in arrived)
    n = len(durations)
    median = None
    if n == 1:
        median = float(durations[0])
    elif n > 1:
        mid = n // 2
        median = (float(durations[mid]) if n % 2
                  else (durations[mid - 1] + durations[mid]) / 2.0)
    out["median"] = median
    out["median_n"] = n
    prov = {"human": 0, "loop": 0, "unknown": 0}
    for origin in first_sight.values():
        prov[origin] += 1
    prov["total"] = len(first_sight)
    prov["history_complete"] = complete
    out["provenance"] = prov
    return out


def ledger_series(target, path=LEDGER_PATH, now=None, step=None):
    """Arrivals, completions and the open count over the ledger's own history.

    Dispatches on :func:`ledger_parse.source_of_truth` (#294 inc 7): when the
    store's cutover watermark is present, the series is a query over
    ``task_event`` first-sight events (the synthetic ``migration:git`` rows);
    otherwise the markdown git-walk runs unchanged. Both paths feed the same
    first-sight model into :func:`_series_from_model`, so the output shape is
    identical — the live cutover flips readers by DATA, not by deploy.

    An id ARRIVES at the first commit that mentions it anywhere, and is
    COMPLETE at the first commit that names it under `## Recently landed`.
    Both are first-seen events, which is what makes them survive grooming:
    that section is pruned, so anything derived from its current contents
    would lose a completion every time the coordinator tidies.

    ``step`` (#487): when it is a member of ``BURN_STEPS``, that width is
    used instead of the auto ladder — the head's cycle control forces a
    coarser or finer reading. Anything else (including ``None``) keeps the
    auto pick that holds the chart under ``BURN_COLUMNS``.
    """
    out = {"state": None, "note": None, "buckets": [], "step": 0,
           "open": 0, "arrived": 0, "landed": 0, "from": 0, "to": 0}

    # #294 inc 7: dispatch on the cutover watermark. The store path queries
    # task_event; the markdown path walks git. Both build the same model and
    # feed _series_from_model. A missing/unreadable store is fail-closed to
    # markdown by source_of_truth itself — never let a missing store break
    # a reader.
    dw_dir = os.path.join(str(target), os.path.dirname(path))
    if source_of_truth(dw_dir) == "store":
        model = store_series_raw(dw_dir)
        if model is None:
            out["state"] = BURN_NONE
            out["note"] = "the ledger store is unreadable"
            return out
        # Reconstruct opencount from arrivals/landings (delta walk): at each
        # event time the open level = arrivals-so-far − landings-so-far,
        # the same count the markdown walk reads from each snapshot.
        from collections import defaultdict
        delta = defaultdict(int)
        for t in model["arrived"].values():
            delta[t] += 1
        for t in model["landed"].values():
            delta[t] -= 1
        opencount = {}
        running = 0
        for t in sorted(delta):
            running += delta[t]
            opencount[t] = running
        return _series_from_model(
            model["arrived"], model["landed"], opencount,
            model["first_sight"], model["latest_open"],
            model["commit_times"], True, now, step)

    def g(*args):
        res = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(target), *args],
            capture_output=True, timeout=15)
        if res.returncode != 0:
            raise OSError(res.stderr.decode("utf-8", "replace").strip() or
                          "git exited %d" % res.returncode)
        return res.stdout.decode("utf-8", "replace")

    try:
        # The ledger's pathspec is resolved against the repository TOP
        # LEVEL, not blindly against the target: a target nested inside a
        # larger repo must read its OWN ledger's history — `git -C sub log
        # -- .dreamwork/tasks.md` would otherwise walk the parent repo and
        # read the repo ROOT's ledger, silently (#217). The history walk
        # itself runs from the top level, because a pathspec is relative
        # to the directory git is invoked in.
        top = g("rev-parse", "--show-toplevel").strip()
        rel = os.path.relpath(os.path.join(target, path), top)
        rel = rel.replace(os.sep, "/")
        # A shallow clone cannot see first sightings before its boundary;
        # the panel names that rather than claiming full coverage (#216).
        complete = g("rev-parse", "--is-shallow-repository").strip() != "true"
        log = g("-C", top, "log", "--format=%H %ct", "--reverse", "--",
                rel).split("\n")
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
    first_sight = {}
    latest = set()
    for rev, ct in revs:
        # A commit identifies a TREE, not one chosen blob in it. Two targets
        # nested in the same repository can have distinct ledgers at the same
        # rev, so the immutable memo key must carry the tree-relative path;
        # rev alone makes whichever dashboard ticks first poison the other.
        snap_key = (rev, rel)
        if snap_key not in _LEDGER_SNAPS:
            try:
                text = g("-C", top, "show", "%s:%s" % (rev, rel))
                o, done = parse_ledger(text)
                _LEDGER_SNAPS[snap_key] = (o, done, entry_origins(text))
            except (OSError, subprocess.SubprocessError):
                # one unreadable revision is a hole, not a failure of the
                # series — skip it and keep the rest rather than reporting
                # the whole history as absent
                continue
        o, done, eorigins = _LEDGER_SNAPS[snap_key]
        for i in o | done:
            arrived.setdefault(i, ct)
        for i in done:
            landed.setdefault(i, ct)
        # An id's origin is read from the FIRST snapshot where it appears
        # and never revisited: a marker added later is documentation, not
        # time travel (#216). Unknown is the absence of a claim and is
        # never rolled into loop (#217).
        for ids, origin in eorigins:
            for i in ids:
                if i not in first_sight:
                    first_sight[i] = origin
        opencount[ct] = len(o)
        latest = o

    if not arrived:
        out["state"] = BURN_NONE
        out["note"] = "%s is versioned but this page can see no entries in " \
                      "any revision of it" % path
        return out

    commit_times = [ct for _rev, ct in revs]
    return _series_from_model(
        arrived, landed, opencount, first_sight, latest,
        commit_times, complete, now, step)


def ledger_stats(target, step=None):
    """`ledger_series`, cached on HEAD (+ optional forced step, #487).

    Cached because the walk is one `git show` per ledger commit — 139 today,
    and it only ever grows. Per-revision parses are memoised globally on the
    commit sha as well, because history is immutable, so a NEW head costs
    only the commits that are new. The cache key is the truthful one for a
    repository-history answer: the target (which fixes the ledger's path
    inside its repo, #217), its HEAD, and the forced step (or None for the
    auto ladder) — a tick with an unmoved HEAD reuses the answer, a new
    commit or a cycle-control click recomputes it.
    """
    try:
        head = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(target), "rev-parse", "HEAD"],
            capture_output=True, timeout=10).stdout.decode().strip()
    except (OSError, subprocess.SubprocessError):
        head = ""
    forced = step if step in BURN_STEPS else None
    key = (os.path.abspath(target), head, forced)
    if key not in _LEDGER_CACHE:
        # keep only this key's peers for the same HEAD cheap: drop other
        # HEADs entirely (history moved); keep other forced steps for this
        # HEAD so cycling back is free.
        if any(k[0] == key[0] and k[1] != head for k in _LEDGER_CACHE):
            _LEDGER_CACHE.clear()
        _LEDGER_CACHE[key] = ledger_series(target, step=forced)
    return _LEDGER_CACHE[key]


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
    """Entries under `## {section}` as [{title, body, follows[, answer…]}].

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

    `lift_answer` pulls every `- **Answer (via watch…):**` bullet out of the
    thread (Open only), so the view can show answered-awaiting-fold
    distinctly rather than as an ambiguous open question. Each is retained in
    `answers` — a list of {text, when, by, at} in file order — because a
    second answer used to overwrite the first at parse time and his earlier
    words were gone before any render rule ran (#446). The FIRST answer is
    also projected onto the single fields (`answer`, `answer_when`,
    `answer_by`, `answer_at`): it is the resolution anchor, so the thread cut
    (`answer_at`) and every existing caller stay on it, and "discussion that
    led to the resolution" still sits above an amendment below. A later answer
    is kept in `answers` but never displaces the anchor at parse time — the
    loop reconciles amendments at fold. `answer_at` per answer records how
    many notes preceded THAT answer, the position the lift would otherwise
    discard and the only thing that says which notes are a reply to it and
    which it is a reply to (#128).
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
        # #340 — when the answer is NOT being lifted, it is still HIS, and a
        # contribution is what it is. Without this it matched neither tag set,
        # fell through to the `startswith("- ")` branch, and landed in `body`
        # verbatim: rendered as a `·` item with its raw author tag showing as
        # text and no `you` label, on 22 of 36 answered entries.
        #
        # Deliberately NOT `lift_answer=True` for `## Answered`, which is the
        # obvious one-argument fix. `answered_at()` reads the `→ answered`
        # resolution head out of `body`, and two of the three call sites depend
        # on it; lifting would put the same fact in a second place that could
        # disagree with it. Making the bullet a contribution leaves the head
        # exactly where it is and adds no second source of the same truth.
        if author is None and not lift_answer:
            author = answer_by

        # invariant 1: this test comes FIRST and is unconditional
        if line.startswith(ENTRY_MARK) and not is_answer and author is None:
            seg, closed, rest = _entry_title_parts(line[len(ENTRY_MARK):])
            cur = {"title": _join_title([seg]), "body": "", "follows": []}
            if lift_answer:
                cur.update(answer=None, answer_when=None, answer_by=None,
                           answer_at=None, answers=[])
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
            # #446: a second Answer bullet used to overwrite the first, so his
            # earlier words were lost at parse time — before any render rule,
            # thread rule or dashboard code ran. questions.md is the durable
            # record of what he decided; the loop cannot know what it forgot.
            # So EVERY answer is retained in `answers`, in file order, each
            # with its author tag, timestamp, and place among the notes. The
            # parser does not rank or interpret (amendment vs correction vs a
            # re-opened entry); it keeps what he wrote, and the loop reconciles
            # semantics at fold. This extends the existing thread grammar
            # (timestamped contributions in file order) rather than inventing
            # a second one.
            at = len(cur["follows"])
            rec = {"text": s.split(":**", 1)[-1].strip(),
                   "when": sub_when(s), "by": answer_by, "at": at}
            cur["answers"].append(rec)
            if len(cur["answers"]) == 1:
                # The FIRST answer is the resolution anchor — the thread cut
                # (`answer_at`) and every single-field caller stay on it, so
                # "discussion that led to the resolution" still sits above and
                # an amendment below (#128). A later answer is retained in
                # `answers` but never displaces the anchor at parse time.
                cur["answer"] = rec["text"]
                cur["answer_when"] = rec["when"]
                cur["answer_by"] = rec["by"]
                cur["answer_at"] = at
            sub = "answer"
        elif author is not None:
            cur["follows"].append(_note_entry(s, author))
            sub = "follow"
        elif not s or s.startswith("- ") or s.startswith("* "):
            sub = None                          # a new bullet ends invariant 3
            cur["body"] += line + "\n"
        elif sub == "answer":
            # a wrapped continuation belongs to the answer being written — the
            # LAST in `answers` — and, while that is still the first (anchor)
            # answer, to its single-field projection too.
            cur["answers"][-1]["text"] += " " + s
            if len(cur["answers"]) == 1:
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
# `→ <verdict> (<timestamp>): …`. Two entries carry an artifact-pointer line
# first and the head on the SECOND body line (#233, #229), so the head is
# anchored to a LINE start (^ + re.M), not the absolute body start (\A), and
# found with .search. .search still returns the FIRST line-start head, so a
# date further down the body is never read — and the leading `→` is the
# never-guess rule: a date with no resolution head is prose, not a verdict
# (answered_at's docstring: "a wrong date is worse than no date"). The
# timestamp may be hard-wrapped (the file is written at ~72 columns), so
# whitespace inside it is tolerated. (\A would make .search identical to
# .match and is the no-op the trap warns of; the anchor is what changes.)
RESOLVED_AT = re.compile(
    r"^\s*→[^:]*?\((\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?\s*\)", re.M)


def answered_at(body):
    """When a folded entry was resolved, or None.

    A collapsed row (#111) has to stay findable by *when*, and a wrong date is
    worse than no date — so this never guesses, exactly as `note_author`
    never guesses an author."""
    m = RESOLVED_AT.search(body or "")
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


# ── #463: review "created" is filesystem birth time, never st_ctime ──────
# POSIX st_ctime is *inode change time* (chmod, rename, hardlink, write of
# mtime itself) — shipping it as "created" is wrong exactly where he cares.
# Linux fills stx_btime via statx when the filesystem knows it; when the
# mask lacks STATX_BTIME or the seconds are zero, created is UNAVAILABLE as
# a named state — never silently degraded to mtime (that was the bug).


def _statx_birth_ns(path):
    """Return birth time in nanoseconds, or None when unavailable.

    Stdlib-only: ctypes against libc.statx. Missing symbol, non-Linux,
    errno, or a mask without btime all return None — never a lie.
    """
    try:
        import ctypes
        import ctypes.util
    except ImportError:
        return None
    libname = ctypes.util.find_library("c")
    if not libname:
        return None
    try:
        libc = ctypes.CDLL(libname, use_errno=True)
        statx = libc.statx
    except (AttributeError, OSError):
        return None

    class _Ts(ctypes.Structure):
        _fields_ = [("tv_sec", ctypes.c_int64),
                    ("tv_nsec", ctypes.c_uint32),
                    ("__reserved", ctypes.c_int32)]

    class _Statx(ctypes.Structure):
        _fields_ = [
            ("stx_mask", ctypes.c_uint32),
            ("stx_blksize", ctypes.c_uint32),
            ("stx_attributes", ctypes.c_uint64),
            ("stx_nlink", ctypes.c_uint32),
            ("stx_uid", ctypes.c_uint32),
            ("stx_gid", ctypes.c_uint32),
            ("stx_mode", ctypes.c_uint16),
            ("__spare0", ctypes.c_uint16),
            ("stx_ino", ctypes.c_uint64),
            ("stx_size", ctypes.c_uint64),
            ("stx_blocks", ctypes.c_uint64),
            ("stx_attributes_mask", ctypes.c_uint64),
            ("stx_atime", _Ts),
            ("stx_btime", _Ts),
            ("stx_ctime", _Ts),
            ("stx_mtime", _Ts),
            ("stx_rdev_major", ctypes.c_uint32),
            ("stx_rdev_minor", ctypes.c_uint32),
            ("stx_dev_major", ctypes.c_uint32),
            ("stx_dev_minor", ctypes.c_uint32),
            ("stx_mnt_id", ctypes.c_uint64),
            ("__spare2", ctypes.c_uint64),
            ("__spare3", ctypes.c_uint64 * 12),
        ]

    AT_FDCWD = -100
    STATX_BTIME = 0x00000800
    # BASIC | BTIME — ask for what we need; the mask says what we got.
    mask_req = 0x000007ff | STATX_BTIME
    buf = _Statx()
    path_b = os.fsencode(path)
    statx.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                      ctypes.c_uint, ctypes.POINTER(_Statx)]
    statx.restype = ctypes.c_int
    if statx(AT_FDCWD, path_b, 0, mask_req, ctypes.byref(buf)) != 0:
        return None
    if not (buf.stx_mask & STATX_BTIME):
        return None
    sec = int(buf.stx_btime.tv_sec)
    nsec = int(buf.stx_btime.tv_nsec)
    if sec <= 0:
        return None
    return sec * 1_000_000_000 + nsec


def file_created_ns(path):
    """Created time for a review artifact: birth when known, else None.

    Also tries `st_birthtime` (BSD/macOS) when the platform exposes it, so
    a non-Linux host with real birth time is not forced through statx.
    """
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return None
    birth = getattr(st, "st_birthtime", None)
    if birth is not None and birth > 0:
        # Prefer nanoseconds when present; else seconds × 1e9.
        bns = getattr(st, "st_birthtime_ns", None)
        if bns is not None and bns > 0:
            return int(bns)
        return int(birth * 1_000_000_000)
    return _statx_birth_ns(path)


def _review_decisions(dw_dir):
    """``{artifact_name: (decision, question_title)}`` from the ledger store,
    or ``{}`` when there is no decision data.

    #289 — the decision is a LEFT JOIN onto the filesystem stat that
    ``list_reviews`` already does. Decisions live in the store's
    ``review_decision`` table (schema v2:
    ``artifact TEXT PK, question_title TEXT NOT NULL, decision TEXT NOT NULL
    CHECK(decision IN ('accepted','rejected','pending')), decided_at TEXT
    NOT NULL, actor TEXT NOT NULL``), written by
    ``ledger_write.record_review_decision``.

    Markdown-mode projects (no store, or no cutover watermark) have no
    decision data: the join degrades to an empty dict, and every row reads
    ``decision=None`` — which ``artifactRow`` renders as 'unlinked', a state
    DISTINCT from 'pending' by contract (absence of a record is its own
    state). Read-only via the ``?mode=ro`` URI idiom (ledger_parse.py); a
    missing or unreadable table/store is the same as no data.
    """
    if dw_dir is None or source_of_truth(dw_dir) != "store":
        return {}
    db = store_path(dw_dir)
    if not db.exists():
        return {}
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error:
        return {}
    try:
        rows = conn.execute(
            "SELECT artifact, decision, question_title FROM review_decision"
        ).fetchall()
    except sqlite3.Error:
        # A store that has not yet been migrated to the v2 review_decision
        # shape is the same as no decision data: degrade, never crash.
        return {}
    finally:
        conn.close()
    return {r[0]: (r[1], r[2]) for r in rows}


def list_reviews(review_dir, dw_dir=None):
    """Review artifacts newest-created first (#463).

    Sort and primary age use filesystem *birth* (created), not mtime.
    mtime is kept so the secondary "modified X ago" can appear when it
    differs. When birth is unavailable the row carries
    `created_known: false` and sorts after every known-created artifact —
    never silently under mtime as if that were created.

    #289 — when ``dw_dir`` is the ``.dreamwork/`` dir of a store-mode
    project, each row is LEFT JOINed to its ``review_decision`` (via
    ``_review_decisions``): ``decision`` and ``question_title`` keys are
    added (None when no row, or in markdown-mode). Absence of a record is
    NOT 'pending' — it is its own state ('unlinked') by contract.
    """
    decisions = _review_decisions(dw_dir)
    reviews = []
    for name in os.listdir(review_dir):
        if not name.endswith(".html"):
            continue
        path = os.path.join(review_dir, name)
        try:
            stat = os.stat(path)
        except FileNotFoundError:
            # An atomic writer may replace/remove an entry after listdir.
            continue
        created_ns = file_created_ns(path)
        known = created_ns is not None
        mtime_ns = stat.st_mtime_ns
        reviews.append({
            "name": name,
            "mtime_ns": mtime_ns,
            "mtime": mtime_ns / 1_000_000_000,
            "created_ns": created_ns,
            "created": (created_ns / 1_000_000_000) if known else None,
            "created_known": known,
            # A CANDIDATE for the secondary, not the verdict. Exact inequality
            # is the wrong test and measurably so: writing a file sets birth,
            # then the content write moves mtime, so 24 of this repo's 28
            # artifacts differ by under a millisecond and would every one of
            # them claim "modified" beside an identical age. His rule is *when
            # they differ*, and what differs to a reader is the rendered
            # figure — so the verdict belongs where the formatter is (ages()),
            # and no threshold has to be invented here.
            "show_modified": known and mtime_ns > created_ns,
            # #289 — LEFT JOIN to review_decision (None when no row / markdown).
            # Absence of a record is 'unlinked', NOT 'pending' (own state).
            "decision": (decisions.get(name) or (None, None))[0],
            "question_title": (decisions.get(name) or (None, None))[1],
        })
    # Known created first (newest-first), unknowns last, name as tie-break.
    reviews.sort(key=lambda r: (
        0 if r["created_known"] else 1,
        -(r["created_ns"] or 0),
        r["name"],
    ))
    return reviews


def skill_identity(target=None):
    """`{commit, skill_version}` — the identity of the SKILL tree this process
    is running from, so a running agent can tell its own tree moved (#426).

    Two independent facts, never one: `commit` is the short HEAD sha of the
    skill tree (where this module lives), `skill_version` is the latest filename
    in `migrations/` (which IS the skill's version, per `migrations/README.md`).
    The two-question discipline is `dev/deploy_state.py`'s: either alone
    misleads. `commit` moves on every change; `skill_version` moves only on a
    migration — so a commit-only delta is "the tree changed, maybe not for me"
    and a skill_version delta is "the tree changed in a way defined to reach
    me". A running agent records these at start and compares at increment
    boundaries; on a skill_version delta it reads the intervening migrations
    before the next increment.

    Reads the SKILL tree (`__file__`'s directory), never `target` — the target
    is somebody's project, and its git identity is a different question
    (`serving_report`). A deployed snapshot is a single file with no sibling
    `migrations/` and no `.git`, so both are `None` there; its *revision* is
    answered separately by `serving_report` (byte-compares the running bytes
    vs the target's history). Collapsing the two would read as reassurance and
    answer half.

    Never raises: this rides `/data.json`, and a crash takes the page down.
    `target` is accepted (and ignored) so `collect(target)` can call it
    uniformly with the other per-request readers; identity is a property of
    the running process, not the target.
    """
    skill_dir = os.path.dirname(os.path.abspath(__file__))
    out = {"commit": None, "skill_version": None}
    try:
        out["commit"] = subprocess.run(
            ["git", "--no-optional-locks", "-C", skill_dir,
             "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10
        ).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        mig = os.path.join(skill_dir, "migrations")
        names = [f for f in os.listdir(mig)
                 if f.endswith(".md") and f != "README.md"]
        if names:
            out["skill_version"] = max(names)   # lexicographic == chronological
    except OSError:
        pass
    return out


# #473 — per-entry "updated" is a content change, not file mtime. The store
# is machine-local (like watch-events.log): digests of each entry's content
# plus the wall-clock of the last observed change. First sight records the
# digest with updated_at=None (no false "updated" on an entry he has always
# seen). A later digest change stamps now and appends a best-effort
# question-updated line to watch-events.log. Git history was rejected (needs
# a commit, and the coordinator commits minutes later); a format marker was
# rejected (changes the parsed ledger shape; file-formats.md is not this
# lane's). Exact nanosecond inequality is not used for display — ages()
# suppresses a secondary whose ageStr equals the created figure (#463).
QUESTION_SIGS = "question-sigs.json"


def _entry_content_digest(entry):
    """Stable digest of one questions.md entry's visible content."""
    payload = {
        "title": entry.get("title") or "",
        "body": entry.get("body") or "",
        "follows": entry.get("follows") or [],
        "answers": entry.get("answers") or [],
        "answer": entry.get("answer"),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _title_sig_key(title):
    return hashlib.sha256((title or "").encode("utf-8")).hexdigest()[:16]


def track_question_updates(target, entries):
    """Stamp per-entry updated_at from content digests; emit event on change.

    Mutates each entry in place with `updated_at` (float epoch seconds, or
    None). Best-effort: a store or log failure never raises into collect().
    Returns the same list for chaining.
    """
    if not entries:
        return entries
    path = os.path.join(target, ".dreamwork", QUESTION_SIGS)
    store = {}
    try:
        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            store = loaded
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        store = {}

    dirty = False
    for e in entries:
        key = _title_sig_key(e.get("title"))
        dig = _entry_content_digest(e)
        prev = store.get(key)
        if not isinstance(prev, dict):
            prev = None
        if prev is None:
            store[key] = {
                "digest": dig,
                "updated_at": None,
                "title": (e.get("title") or "")[:120],
            }
            e["updated_at"] = None
            dirty = True
        elif prev.get("digest") != dig:
            now = time.time()
            store[key] = {
                "digest": dig,
                "updated_at": now,
                "title": (e.get("title") or "")[:120],
            }
            e["updated_at"] = now
            log_event(
                target,
                "question-updated via watch: "
                + one_line((e.get("title") or "")[:100]),
            )
            dirty = True
        else:
            u = prev.get("updated_at")
            e["updated_at"] = float(u) if isinstance(u, (int, float)) else None

    if dirty:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(store, f, indent=0, sort_keys=True)
            os.replace(tmp, path)
        except OSError:
            pass
    return entries


def collect(target, burn_step=None):
    now = time.time()
    dw = os.path.join(target, ".dreamwork")
    questions = read_text(os.path.join(dw, "questions.md"))
    q_open = parse_open_questions(questions)
    q_answered = parse_answered(questions)
    # #473: stamp updated_at per entry before the payload leaves. Open first
    # (what he is looking at); answered second so a folded rewrite also
    # signals. One store covers both sections.
    track_question_updates(target, q_open)
    track_question_updates(target, q_answered)
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
        "reviews": list_reviews(os.path.join(dw, "review"), dw)
        if os.path.isdir(os.path.join(dw, "review")) else [],
        # #484 — built research HTML under docs/research, listed by the SAME
        # one listing shape (non-recursive, .html only, created/mtime facts):
        # the src/ sources stay invisible exactly as review sources do. No
        # questions.md pairing, no archive lifecycle — that is the review
        # surface, and research is not it.
        "research": list_reviews(os.path.join(dw, "docs", "research"))
        if os.path.isdir(os.path.join(dw, "docs", "research")) else [],
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
        # hand-offs awaiting a fold (#381): read straight from the file the
        # coordinator's tick and lint read — a real reader, never a mirror of
        # status.json (which is the loop's own live claim, not a foreign
        # session's report of landed work).
        "pending_handoffs": pending_handoff_records(
            read_text(os.path.join(dw, "handoffs.md"))),
        "status": _safe_json(read_text(os.path.join(dw, "status.json"))),
        "git": git_tail(target),
        # which revision this process is running (#140), so a stale page
        # announces itself instead of being mistaken for a bug
        "deployed": serving_cached(target),
        # the ledger's own history as a time series (#142) — no new
        # instrumentation, because tasks.md is versioned and its ids are
        # permanent. burn_step (#487) is the cycle control's forced
        # granularity; None keeps the auto ladder.
        "burndown": ledger_stats(target, step=burn_step),
        # his colour for this project (#143). It rides /data.json rather than
        # the shell so the EXISTING mtime poll carries it: he picks a tint in
        # one window and every other window on this project follows within a
        # tick, with no new channel and no reload.
        "tint": read_tint(target),
        # main-dreamer run mode (#290). File is authoritative; this field is
        # how every open window converges via the existing /mtime poll. The
        # loop also sees the change through watch-events.log when the mode
        # actually changes (identical final is silent).
        "run_mode": read_run_mode(target),
        # #445 three-axis posture (pace × asking × delegation). Absent file
        # → derived from run-mode via lint.derive_posture (single source).
        # Rides the same /mtime poll so every open window converges.
        "posture": resolve_posture(target),
        # plugin-contributed command kinds (#86), for the same reason and by
        # the same route. The core vocabulary is baked into the page shell
        # because it is a property of watch.py; this half is a property of the
        # MACHINE — which plugins resolved here — so it has to be able to
        # change under a page that is already open. `watched_mtime` walks all
        # of `.dreamwork/`, so a plugin loading mid-session reaches the
        # composer on the next tick with no reload and no new channel.
        "plugin_commands": plugin_commands(target),
        # #426 — the skill tree's identity (commit + latest migration), so a
        # running agent can tell its own tree moved. Reads the SKILL tree, not
        # the target; rides /data.json and the /mtime poll so an open page and
        # a running agent converge on the same identity with no new channel.
        # The defined action on a delta is per-surface (design:
        # .dreamwork/docs/reload-signal-design.md): a lane finishes its
        # current increment then reloads; the server already reloads via
        # GENERATION on re-deploy.
        "skill_identity": skill_identity(target),
    }


# /summary.json — a redacted, whitelist view of collect(), for a consumer
# that is not the loopback dashboard (Q5; plans/hub-public-auth.md §11.2,
# plans/hub-ssh-auth.md). collect() feeds /data.json, which serves
# DREAMWORK.md / questions.md / lessons.md IN FULL plus parsed entries,
# transcripts and status.json — unfit to expose. This replaces it for any
# non-local consumer (dreamhub reading across projects, or a later
# authenticated remote reader). It is designed safe-to-expose over a link
# today, so a future bind ruling cannot re-open the leak by accident.
#
# REDACTION IS A WHITELIST, NEVER A DENYLIST. summary() names the fields
# that may leave and pulls ONLY those; it never iterates collect()'s keys,
# so a field collect() grows tomorrow cannot appear here unless it was
# deliberately named. Whether a new collect() key may leave is a decision
# recorded in SUMMARY_ALLOWED or SUMMARY_DENIED below — and the partition
# test (TestSummary.test_summary_classifies_every_collect_key) is what
# notices that the decision got made, because a summary that quietly passed
# a new field through is the exact bug this endpoint exists to prevent.

# collect() keys that may NOT leave, each excluded for a stated reason. The
# set is not "everything else" — it is exhaustive (see the partition test),
# so a brand-new collect() key is in NEITHER set and reds until classified.
SUMMARY_DENIED = frozenset({
    "target",            # absolute machine path — the operator's home dir
    "linkable_paths",    # every target-relative file path (repo structure)
    "dreams",            # agent transcripts — his words + working state
    "dreams_archive",    # the same, archived
    "files",             # full DREAMWORK/questions/lessons text (container;
                         #   one safe scalar is pulled out under skill_version)
    "reviews",           # design artifacts carrying his decision context
    "research",          # the same class as reviews (#484): research
                         #   artifacts and the reasoning they record
    "questions_open",    # parsed question bodies — his words
    "answered_entries",  # parsed answered-question bodies — his words
    "answers_open",      # his questions to the loop — his words
    "answers_answered",  # the same, answered
    "pending_handoffs",  # landed-work records — what the loop is doing
    "status",            # status.json: queue, agent ownership, pid, deploy
    "git",               # recent commit subjects — operational, sometimes his
    "deployed",          # serving state + machine-local paths/notes
    "plugin_commands",   # machine UI vocabulary (prose desc/label), not a
                         #   project-status summary, and reveals the plugin set
})


def _summary_posture(v):
    # The enum/int axes + delivery (#342); delegation_label is display chrome
    # and never rides out unreviewed. delivery is real posture an external
    # consumer needs to route on, not chrome.
    return {k: v.get(k) for k in
            ("pace", "asking", "delegation", "delivery", "source")}


def _summary_skill_identity(v):
    return {k: v.get(k) for k in ("commit", "skill_version")}


def _summary_burndown_counts(v):
    # The three scalar counts only — buckets is a working-cadence time
    # series, state/note/from/to carry machine-local error prose and paths.
    return {k: v.get(k) for k in ("open", "arrived", "landed")}


# collect() keys that MAY leave, each as (output_name, projection). A
# projection of None copies the value verbatim (the partition test vouches
# for its shape); a callable reaches into an otherwise-unsafe container or
# copies only named sub-keys, so a field the source grows never rides out
# unreviewed. `files` is allowed as a SOURCE only to extract the one safe
# skill-version scalar — the full document bodies never leave.
SUMMARY_ALLOWED = {
    "generated": ("generated", None),
    "open_questions": ("open_questions", None),
    "questions_health": ("questions_health", None),
    "answers_health": ("answers_health", None),
    "tint": ("tint", None),
    "run_mode": ("run_mode", None),
    "posture": ("posture", _summary_posture),
    "skill_identity": ("skill_identity", _summary_skill_identity),
    "burndown": ("burndown_counts", _summary_burndown_counts),
    "files": ("skill_version",
              lambda v: v.get("skill-version") if isinstance(v, dict) else None),
}


def summary(target):
    """Whitelist view of collect() served at /summary.json (Q5).

    Pulls ONLY the source keys named in SUMMARY_ALLOWED, projecting each to
    its output name; it never iterates collect()'s keys, so a field
    collect() grows cannot appear here unless it was deliberately named.
    Whether a new collect() key is allowed to leave is a decision recorded
    in SUMMARY_ALLOWED or SUMMARY_DENIED, and the partition test enforces
    that the decision gets made rather than defaulted to "passes through".
    """
    full = collect(target)
    out = {}
    for source, (name, project) in SUMMARY_ALLOWED.items():
        out[name] = (full[source] if project is None
                     else project(full[source]))
    return out


# #481 — machine-local derived state whose mtime carries no signal.
# question-sigs.json is rewritten by collect() (tmp + os.replace) on first
# sight of an entry and on every content change — always DOWNSTREAM of the
# questions.md write this walk already sees directly, so excluding it loses
# no real re-render. Counting it cost a spurious re-render ~2s after every
# fresh page load, and a second one behind every real question change. The
# .tmp twin is excluded too: the replace is two directory events, not one.
WATCHED_MTIME_IGNORED = frozenset((QUESTION_SIGS, QUESTION_SIGS + ".tmp"))


def watched_mtime(target):
    """The newest thing under the target, as one number the client polls.

    DELETIONS ARE IN HERE, and they are the half that took #86 to find.
    Statting only files makes a DELETION invisible: removing a file cannot
    raise the maximum mtime of the files that remain, so an open page goes on
    showing what is no longer there until something unrelated is written.

    That signal used to be the directories' own mtimes, which move when an
    entry is added or removed. #481 ended that: a directory's mtime moves
    for EVERY entry, including the ignored sig store's tmp+replace, and one
    number cannot subtract one file's contribution. So the add/remove signal
    is now the SET of non-ignored entry names per directory, hashed into a
    sub-second fraction of the returned float. The client only compares the
    value for inequality, so max-mtime plus a deterministic listing
    fingerprint is the same contract: the number changes iff the watched
    state changes.

    The case that named it: unloading a plugin is deliberately the ABSENCE of
    a write rather than a remembered deletion, and the composer went on
    offering commands nothing would answer. That contract needs absence to be
    observable to hold at all.
    """
    latest = 0.0
    paths = [os.path.join(target, "DREAMWORK.md"),
             os.path.join(target, ".git", "logs", "HEAD")]
    dw = os.path.join(target, ".dreamwork")
    listing = []
    for root, dirs, files in os.walk(dw):
        kept = sorted(f for f in files if f not in WATCHED_MTIME_IGNORED)
        listing.append((root, tuple(sorted(dirs)), tuple(kept)))
        paths.extend(os.path.join(root, f) for f in kept)
    for p in paths:
        try:
            latest = max(latest, os.path.getmtime(p))
        except OSError:
            pass
    digest = hashlib.sha256(repr(sorted(listing)).encode()).digest()
    return latest + int.from_bytes(digest[:7], "big") / (1 << 56)


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


def read_run_mode(target):
    """The project's main-dreamer run mode, or the default (#290).

    Unknown / planned / absent → default. Silent fallback matches tint: the
    UI must never blank, and lint.py is what says a hand-edited bad value
    was dropped.
    """
    raw = (read_text(os.path.join(target, ".dreamwork", "run-mode")) or "")
    name = raw.strip()
    return name if name in RUN_MODES else RUN_MODE_DEFAULT


def write_run_mode(target, mode):
    """Persist the selectable mode. Returns False if refused or unwritable."""
    if mode not in RUN_MODES:
        return False
    path = os.path.join(target, ".dreamwork", "run-mode")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        atomic_write_text(path, mode + "\n")
        return True
    except OSError:
        return False


def run_mode_line(mode, source=""):
    """Source-tagged watch-events.log line for a committed run-mode change.

    Pure; testable. one_line so free text cannot forge a second event.
    """
    return f"run-mode via watch{from_hint(source)}: {one_line(mode)}"


def parse_posture_text(raw):
    """Parse posture file body → dict of valid axes only.

    Unknown axes ignored; invalid pace/asking dropped (lint is what fails
    loud on hand-edits). Delegation must be a non-negative int. Empty /
    comment-only → {}. Pure so tests need no disk.
    """
    out = {}
    if not raw:
        return out
    lint = _posture_vocab()
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if ":" not in s:
            continue
        k, _, v = s.partition(":")
        k, v = k.strip().lower(), v.strip()
        if k == "pace" and v in lint.POSTURE_STOPS_PACE:
            out["pace"] = v
        elif k == "asking" and v in lint.POSTURE_STOPS_ASKING:
            out["asking"] = v
        elif k == "delivery" and v in lint.POSTURE_STOPS_DELIVERY:
            out["delivery"] = v
        elif k == "delegation":
            try:
                n = int(v)
            except ValueError:
                continue
            if n >= 0:
                out["delegation"] = n
    return out


def read_posture_file(target):
    """Axes present and valid in `.dreamwork/posture`, or {} if absent."""
    raw = read_text(os.path.join(target, ".dreamwork", "posture"))
    if raw is None:
        return {}
    return parse_posture_text(raw)


def resolve_posture(target):
    """Effective three-axis posture for the dashboard and collect().

    Absent file → derived from run-mode (lint.derive_posture). Present file
    overlays any valid axes on that derivation. Always returns pace, asking,
    delegation, source ('derived'|'file'), and delegation_label for display.
    """
    lint = _posture_vocab()
    mode = read_run_mode(target)
    base = lint.derive_posture(mode)
    if base is None:
        base = lint.derive_posture(RUN_MODE_DEFAULT) or {
            "pace": "idle", "asking": "ask", "delegation": 0,
        }
    file_vals = read_posture_file(target)
    out = {
        "pace": base["pace"],
        "asking": base["asking"],
        "delegation": int(base["delegation"]),
        "delivery": file_vals.get("delivery", DELIVERY_DEFAULT),
        "source": "derived",
    }
    if file_vals:
        out["source"] = "file"
        for k in ("pace", "asking", "delegation"):
            if k in file_vals:
                out[k] = file_vals[k]
    out["delegation_label"] = lint.delegation_posture(int(out["delegation"]))
    return out


def write_posture(target, pace, asking, delegation, delivery=None):
    """Persist a posture override. Returns False if refused.

    Writes the three required axes always; writes delivery only when it is
    passed (None → omitted, so absent reads as the instant default — a caller
    that has no opinion on delivery gets today's three-line file). A caller
    that sets delivery passes it through and the fourth line lands."""
    lint = _posture_vocab()
    if pace not in lint.POSTURE_STOPS_PACE:
        return False
    if asking not in lint.POSTURE_STOPS_ASKING:
        return False
    if delivery is not None and delivery not in lint.POSTURE_STOPS_DELIVERY:
        return False
    try:
        n = int(delegation)
    except (TypeError, ValueError):
        return False
    if n < 0:
        return False
    path = os.path.join(target, ".dreamwork", "posture")
    lines = [f"pace: {pace}", f"asking: {asking}", f"delegation: {n}"]
    if delivery is not None:
        lines.append(f"delivery: {delivery}")
    body = "\n".join(lines) + "\n"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        atomic_write_text(path, body)
        return True
    except OSError:
        return False


def posture_line(pace, asking, delegation, source=""):
    """Source-tagged watch-events.log line for a committed posture change.

    Pure; one_line on each free field so nothing forges a second event.
    """
    return (
        f"posture via watch{from_hint(source)}: "
        f"pace={one_line(str(pace))} "
        f"asking={one_line(str(asking))} "
        f"delegation={one_line(str(delegation))}"
    )


def posture_equal(a, b):
    """Whether two posture dicts name the same three-axis point."""
    if not a or not b:
        return False
    try:
        return (a.get("pace") == b.get("pace")
                and a.get("asking") == b.get("asking")
                and int(a.get("delegation")) == int(b.get("delegation")))
    except (TypeError, ValueError):
        return False


# #342 — the delivery posture axis (instant|batched). Absent = instant, so the
# default is today's behaviour (every wake line fires). The loop gates which
# kinds wake; the cursor read on every tick is the guarantee nothing is lost.
DELIVERY_DEFAULT = "instant"


def delivery_line(mode, source=""):
    """Source-tagged watch-events.log line for a committed delivery change.

    Pure; one_line on the mode so nothing forges a second event. The ceremony
    posture/run-mode already use (dual-write + one line on real change), not a
    second one."""
    return f"delivery via watch{from_hint(source)}: {one_line(str(mode))}"


# #342 — per-kind wake routing. The receipt commits UNCONDITIONALLY in do_POST
# (the E3 invariant); these decide only whether the watch-events.log wake line
# — the *interrupt* — fires on top. do-now/do-next pre-empt even in batched
# mode (a do-now that does not pre-empt is a do-now that lied — his Q2 ruling);
# every other command kind (add-idea, maintenance, plugin kinds) and the
# /answer, /comment, /ask routes wake only in instant mode, riding the durable
# receipt and the tick's cursor read otherwise. Withholding the wake line IS
# batching.
PREEMPT_KINDS = ("do-now", "do-next")


def delivery_mode(target):
    """Effective delivery posture: 'instant' (default) or 'batched' (#342).

    Per-tick re-read of `.dreamwork/posture` via read_posture_file — the same
    contract pace/asking/delegation use, so an on-disk change reaches a
    running loop without restart. Absent axis → instant (today's behaviour)."""
    return read_posture_file(target).get("delivery", DELIVERY_DEFAULT)


def emits_wake(kind, target):
    """Per-kind wake routing (#342): does this kind fire the wake line?

    Pre-empt kinds (do-now/do-next) wake regardless of mode; every other kind
    — add-idea, maintenance, plugin kinds — and the /answer, /comment, /ask
    ROUTES (passed as their path string, which is never a pre-empt kind) wake
    only in instant mode. The receipt always commits in do_POST; this is the
    interrupt half only. Pure in `kind`; reads delivery posture from disk."""
    if kind in PREEMPT_KINDS:
        return True
    return delivery_mode(target) == DELIVERY_DEFAULT


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


# --- Durable user-event journal (lane E, #263) -------------------------------
# The journal is one SQLite file per target under .dreamwork/, opened with WAL +
# synchronous=FULL so a committed receipt survives crash/reboot (design
# `user-event-journal.md` Durability boundary). `submissions.log` stays the
# best-effort witness until the cutover; the journal is the shadow now and
# becomes authority at E3. The transport protocol version is part of the
# receipt digest (law: request_digest length-frames it), so it is a named
# constant rather than a literal at each call site.
JOURNAL_PROTOCOL_VERSION = "1"
JOURNAL_FILENAME = "user-events.sqlite3"


def _journal_path(target):
    return os.path.join(target, ".dreamwork", JOURNAL_FILENAME)


def _target_id(target):
    """Stable short id for the target, for the receipt's target_id field.

    The journal stores which target a receipt belongs to; an absolute path is
    machine-specific and leaks structure, so a SHA-1 prefix is used — stable
    across restarts, not a secret (it is in a local-only database)."""
    return hashlib.sha1(os.path.abspath(target).encode("utf-8")).hexdigest()[:12]


def _journal_receive(target, envelope):
    """Receive one envelope into the target's journal (#263 lane E).

    Opens the per-target journal, receives, closes — one connection per
    request, so threaded requests never share a SQLite handle (busy_timeout
    serialises contention across them). A journal failure here is logged and
    swallowed: until the cutover (E3) the journal is a *shadow* and a receipt
    miss must never refuse a request the existing handlers accept. Returns the
    ReceiveResult, or None on any open/receive failure."""
    try:
        with open_journal(_journal_path(target)) as journal:
            return journal.receive(envelope)
    except Exception as exc:  # shadow phase: never let this refuse his words
        log_event(target, f"user-events journal receive failed: {exc!r}")
        return None


def _journal_record_health(target, receipt_id, health, detail=""):
    """Record a health event against a durably-committed receipt (E4).

    Best-effort: a journal that cannot record health must not refuse a request
    the receipt already accepted. Health is not application state
    (shadow_failed does not move the receipt), so a failure here is logged and
    swallowed — the dashboard (E6) surfaces it from the journal when it can."""
    try:
        with open_journal(_journal_path(target)) as journal:
            journal.record_health(receipt_id, health, detail)
    except Exception as exc:  # never let health recording refuse a request
        log_event(target, f"user-events journal health record failed: {exc!r}")


def _journal_reject(target, receipt_id, reason_code):
    """Record a received→rejected transition with a bounded reason (E5).

    Rejection is durable, not synchronous: the receipt already committed in
    do_POST, so a malformed/schema/domain-invalid body is *received* and then
    *rejected*. Reads the current revision from the journal (not tracked in
    the request) because a same-UUID replay may have advanced it. Best-effort:
    a journal failure here is logged and swallowed — the response is still
    202, because the receipt committed."""
    try:
        with open_journal(_journal_path(target)) as journal:
            row = journal.get_receipt(receipt_id)
            if row is None:
                return
            if row["state"] == "received":
                journal.transition(
                    receipt_id, "rejected", int(row["revision"]),
                    reason_code=reason_code)
    except Exception as exc:  # never let rejection recording refuse a request
        log_event(target, f"user-events journal reject failed: {exc!r}")


def log_submission(target, path, body, nbytes, truncated=False, short=False):
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

    Returns True if the line was written, False if it could not be (E4: the
    caller records shadow_failed health against the durable receipt, never a
    refusal).

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
    # A body that arrived SHORT is the opposite condition to `truncated` and was
    # conflated with it (#371): too large is a cap this server applied, too small
    # is a promise the client broke. Without this, `bytes` stated the declared
    # length beside a shorter payload and nothing said so — and this file exists
    # to recover his words, so a reader could not tell a truncated answer from a
    # genuinely brief one. Recorded only when it differs, because a marker that
    # is always present says nothing.
    if short:
        rec["short"] = True
        rec["got"] = len(body)
    try:
        line = json.dumps(rec, ensure_ascii=False)
    except (TypeError, ValueError):        # a value json cannot render
        return False
    try:
        # One append of one line, under a lock, because this server is
        # threaded and two interleaved writes lose both submissions rather
        # than one.
        with SUBMIT_LOCK:
            with open(os.path.join(target, ".dreamwork", "submissions.log"),
                      "a", encoding="utf-8") as f:
                f.write(line + "\n")
        return True
    except OSError:
        # E4: a shadow-write failure is returned to the caller as False so it
        # can record shadow_failed health against the (already-durable)
        # receipt. Swallowed, never re-raised — this function's oldest rule
        # ("CANNOT RAISE") is unchanged: a logging failure must never be why
        # his answer was refused.
        return False


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


def _expected_disconnect(exc):
    """Exactly the peer-departure errors a cancelled poll can raise (#299):
    the browser went away mid-response, which is expected client behaviour.
    Everything else must stay loud in socketserver's error reporting."""
    return isinstance(exc, (BrokenPipeError, ConnectionResetError,
                            ConnectionAbortedError)) or (
        isinstance(exc, OSError) and exc.errno in (
            errno.EPIPE, errno.ECONNRESET, errno.ECONNABORTED))


def make_handler(target, dev=False, authority=None, journal_shadow=True):
    # _get_page() injects posture vocab from lint on first access (lazy so
    # lint↔watch import order never meets a half-initialised lint).
    base_page = _get_page()
    page = (base_page.replace("/*DEV*/false", "true") if dev else base_page)

    class Handler(http.server.BaseHTTPRequestHandler):
        # E2 shadow phase toggle: when True (production default) every
        # well-formed write request commits a shadow journal receipt whose
        # failure is swallowed. Tests disable it to capture the pre-journal
        # baseline and assert the journal changed exactly the receipt count
        # and nothing observable. Set below from the constructor argument
        # (a class-body `journal_shadow = journal_shadow` shadows the param).
        journal_shadow = True

        def handle(self):
            # #299: a client that cancels its poll (usually /mtime) after we
            # committed to a response breaks the pipe under any write —
            # headers, body or error page. The peer is gone: no one to report
            # to, nothing to retry, and the next poll reconnects, so quiet
            # exactly that class and close. Any other error still escapes to
            # socketserver's traceback. (finish needs no wrapper: stdlib
            # already swallows socket.error on the final flush.)
            try:
                super().handle()
            except OSError as exc:
                if not _expected_disconnect(exc):
                    raise
                self.close_connection = True

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

        def _journal_receive(self, target):
            """Commit one shadow receipt for this POST (journal-shadow phase).

            Builds the transport envelope from the request the handler already
            validated (authority, method, route, media type, the complete
            bounded body) and receives it. The client_action_id is the
            idempotency key: the browser will send one (lane G, #269) and the
            journal dedupes same UUID+digest. CLI/curl sends none, so the
            server mints a per-request UUID — a CLI retry is then a distinct
            intentional action, which is the design's rule for a client with no
            attempt store. Until E3 a journal failure is swallowed (shadow)."""
            client_action_id = (
                self.headers.get("X-Client-Action-Id")
                or str(uuid.uuid4()))
            envelope = Envelope(
                client_action_id=client_action_id,
                protocol_version=JOURNAL_PROTOCOL_VERSION,
                method=self.command or "POST",
                route=self.path,
                content_type=self.headers.get("Content-Type", ""),
                body=self._body,
                target_id=_target_id(target),
            )
            self._journal_result = _journal_receive(target, envelope)

        def journal_result(self):
            """The committed receipt's ReceiveResult, or None if none committed.

            E3 cutover: the response authorisation. A None means the journal
            could not commit (open/receive failure) and `do_POST` has already
            returned 503; a handler that reaches `_send_receipt` therefore has
            a real receipt to name."""
            return getattr(self, "_journal_result", None)

        def _send_receipt(self, body, ctype):
            """Send a write-route success as 202 + Location + receipt identity.

            The journal commit — not the handler — authorises the response
            (E3 cutover). `body` is the handler's JSON object (e.g. {"ok":
            True}); the receipt identity (id/sequence/digest) is merged in and a
            `Location: /user-events/<id>` header is set. A hardcoded 202 without
            a real receipt fails E3(a): the body's receipt id is `get()`-able
            from the journal.

            Legacy fallback: when the journal is disabled (journal_shadow=False,
            the pre-cutover path E2's baseline exercises), this sends the body
            as a plain 200 via `_send` — no receipt, no Location."""
            if not self.journal_shadow:
                self._send(body, ctype)
                return
            result = self.journal_result()
            # result is non-None here: do_POST 503'd if the journal failed. But
            # parse defensively rather than trusting control flow — a missing
            # receipt must never mint a 202 with a fabricated id.
            receipt = self._receipt_body(result) if result is not None else None
            if receipt is None:
                self.send_error(503)
                return
            payload = self._merge_receipt(body, receipt)
            out = json.dumps(payload).encode("utf-8")
            self.send_response(202)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(out)))
            self.send_header("Location", f"/user-events/{receipt['receipt_id']}")
            self.end_headers()
            self.wfile.write(out)

        def _receipt_body(self, result):
            """Project a ReceiveResult into the response's receipt fields, or
            None if the result carries no committed receipt (conflict/kind)."""
            if not result or not result.receipt_id:
                return None
            return {
                "receipt_id": result.receipt_id,
                "sequence": result.sequence,
                "request_digest": result.request_digest,
            }

        def _merge_receipt(self, body, receipt):
            """Merge the handler's JSON body with the receipt identity.

            `body` is a JSON string; parse, merge under a `receipt` key, and
            re-serialise so the handler's own fields (tint, mode, changed) are
            preserved alongside the receipt."""
            try:
                obj = json.loads(body) if isinstance(body, str) else dict(body)
            except (ValueError, TypeError):
                obj = {}
            obj["receipt"] = receipt
            return obj

        def _send(self, body, ctype):
            data = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _reject(self, reason_code, detail=None):
            """Record a durable rejection and respond 202 (E5).

            `detail` is an OPTIONAL free-form discriminator for copy, and it is
            deliberately not part of the closed set: `REJECTION_REASONS` is a
            contract three values wide, while a route may refuse for several
            distinct reasons that all map to one of them. #462 is the motivating
            case — "a deploy is already running" and "you are not on this
            machine" are both `domain_invalid`, and telling him "the value was
            not one the server accepts" for either is wrong in the only two
            cases he will ever hit. Widening the closed set would change a
            contract and its journal; adding a copy hint does not.

            The receipt already committed in do_POST; rejection is durable,
            not synchronous. The reason is from REJECTION_REASONS (closed set
            in user_events.sqlite). A complete registered envelope never
            disappears behind a synchronous 400 — it is received, then
            rejected, and the response is still 202."""
            result = self.journal_result()
            if result and result.receipt_id and self.journal_shadow:
                _journal_reject(target, result.receipt_id, reason_code)
            body = {"ok": False, "rejected": True, "reason": reason_code}
            if detail:
                body["detail"] = detail
            self._send_receipt(json.dumps(body), "application/json")

        def _send_bytes(self, full, rel, *, inline):
            """Serve `full` as raw bytes (#336), streamed (#354).

            `inline=True` serves the allowlisted raster MIME; `inline=False`
            serves application/octet-stream + attachment disposition. Both
            carry X-Content-Type-Options: nosniff — the latter because
            `nosniff` is what makes a browser honour the octet-stream
            disposition over a sniffed guess. `full` is already behind
            resolve_confined; a None or missing file is a 404.

            Body production is stat + open + a FILEBYTES_CHUNK read/write
            loop. Content-Length comes from the stat size, never from
            materialising the file. Peak process memory for the body is one
            chunk, not one file — required because the common client is an
            <img> that issues a full GET with no Range header."""
            if not full:
                self.send_error(404); return
            try:
                size = os.path.getsize(full)
                body = open(full, "rb")
            except OSError:
                self.send_error(404); return
            try:
                self.send_response(200)
                if inline:
                    ctype = inline_image_mime(full)
                    disp = "inline"
                else:
                    ctype = "application/octet-stream"
                    disp = (
                        f"attachment; filename="
                        f"\"{safe_attachment_filename(rel)}\"")
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(size))
                self.send_header("Content-Disposition", disp)
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header(
                    "Cache-Control", "private, max-age=0, must-revalidate")
                self.end_headers()
                # Mid-stream disconnect is #299's Handler.handle quieting
                # BrokenPipeError / ConnectionResetError around the whole
                # request — a looped write raises the same OSError class as
                # the old single write, so no second disconnect path.
                while True:
                    chunk = body.read(FILEBYTES_CHUNK)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            finally:
                body.close()

        def do_GET(self):
            # Authority gates every path before it can disclose target state.
            if not self._preflight():
                return
            parsed = urllib.parse.urlparse(self.path)
            # Same-document routes all return the one app shell; the client
            # router renders the matching view (deep links keep working).
            if parsed.path in ("/", "/questions", "/answers", "/file",
                               "/review", "/question", "/research"):
                self._send(page, "text/html")
            elif parsed.path == "/data.json":
                # #487: optional burn_step lets the head's cycle control
                # re-bucket without a second walk of any other series.
                qs = urllib.parse.parse_qs(parsed.query)
                raw = (qs.get("burn_step") or [None])[0]
                try:
                    burn_step = int(raw) if raw is not None else None
                except (TypeError, ValueError):
                    burn_step = None
                if burn_step not in BURN_STEPS:
                    burn_step = None
                self._send(json.dumps(collect(target, burn_step=burn_step)),
                           "application/json")
            elif parsed.path == "/summary.json":
                # Q5: a whitelist view of collect() (summary()), for any
                # non-loopback consumer. /data.json serves full documents and
                # parsed entries; this serves only the counts, health and
                # operational metadata named in SUMMARY_ALLOWED. It does NOT
                # widen authority: it rides the same _preflight() gate as
                # every other GET, and where it may listen is a separate
                # ruling (#275/Q3) he has not given. Adding a read endpoint
                # changes no bind address, host allowlist or flag.
                self._send(json.dumps(summary(target)), "application/json")
            elif parsed.path == "/mtime":
                # "<generation> <watched-mtime>": generation gates a full
                # reload (new server build), mtime gates a data re-render.
                self._send(f"{GENERATION} {watched_mtime(target)}",
                           "text/plain")
            elif parsed.path == "/filedata":
                # #336: a binary file used to be UTF-8-decoded (errors=
                # replace) into a string of U+FFFD and rendered in a <pre>
                # as plausible-looking mojibake. Now the response describes
                # it instead, and a separate /filebytes endpoint serves the
                # raw bytes from the SAME resolve_confined gate.
                rel = urllib.parse.parse_qs(parsed.query).get("p", [""])[0]
                full = resolve_confined(target, rel)
                kind = detect_file_kind(full) if full else None
                if kind == "text":
                    text = read_text(full)
                    if text is None:
                        self.send_error(404); return
                    payload = {"path": rel, "content": text}
                    # #351: highlighted markup for a known source extension,
                    # cached per file version (see file_highlight_html). The
                    # field is ABSENT for everything else — an unknown
                    # extension renders plain (#339's never-guess), and the
                    # client never invents markup of its own.
                    hl = file_highlight_html(full, text)
                    if hl is not None:
                        payload["hl"] = hl
                    self._send(json.dumps(payload), "application/json")
                    return
                if kind in ("image", "binary") and full:
                    try:
                        size = os.path.getsize(full)
                    except OSError:
                        self.send_error(404); return
                    self._send(json.dumps({
                        "path": rel, "binary": True, "kind": kind,
                        "mime": (inline_image_mime(full)
                                 if kind == "image"
                                 else "application/octet-stream"),
                        "size": size,
                    }), "application/json")
                    return
                self.send_error(404)
            elif parsed.path == "/filebytes":
                # #336 — raw bytes, behind the SAME resolve_confined gate as
                # /filedata. The Content-Type is taken from INLINE_IMAGE_EXTS
                # and never from the client, because a reflected Content-Type
                # turns any .svg or .html in the tree into stored XSS against
                # this origin. An allowlisted raster (extension AND magic
                # bytes) is served inline; everything else is
                # application/octet-stream with an attachment disposition, so
                # the bytes are reachable but never rendered by the browser.
                rel = urllib.parse.parse_qs(parsed.query).get("p", [""])[0]
                full = resolve_confined(target, rel)
                if not full or detect_file_kind(full) != "image":
                    self._send_bytes(full, rel, inline=False)
                else:
                    self._send_bytes(full, rel, inline=True)
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
            elif parsed.path == "/researchraw":
                # #484 — the /reviewraw idiom over docs/research: the raw
                # self-contained artifact for the /research view's iframe.
                # The no-slash basename rule is load-bearing in the same
                # way: src/ sources are .html under this tree and must never
                # be served as finished artifacts.
                name = urllib.parse.parse_qs(parsed.query).get("p", [""])[0]
                full = (resolve_confined(
                    target, os.path.join(
                        ".dreamwork", "docs", "research", name))
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
            Returns None on a parse failure; E5 moved the 400 to a durable
            rejection in the caller, so this method no longer sends a
            response (the red line for increment 24).
            """
            try:
                return json.loads(self._body)
            except ValueError:
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
            # note; /command records steering; /decide records a review
            # decision into the ledger store (#289); /tint saves project
            # colour; /run-mode commits main-dreamer pace (#290); /posture
            # commits the three-axis override (#445); /deploy runs `just
            # deploy` (#462, loopback peer only, single-flight).
            # Answer/ask/comment/command/decide wake the loop through
            # watch-events.log; /run-mode and /posture do too, but only when
            # the value actually changes (identical final is silent). Tint
            # and deploy do not wake: tint is presentation state; deploy
            # restarts the dashboard process. Every other POST path is
            # rejected.
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
            want = min(nbytes, MAX_BODY)
            body = self.rfile.read(want)
            truncated = nbytes > MAX_BODY
            # `truncated` catches a body too LARGE; `short` catches one that
            # arrived SMALL (#371) — fewer bytes than promised, a connection
            # dropped mid-body. They are opposite conditions.
            short = len(body) < want
            self._body = body
            # #371 policy (his 05:43 ruling on #263 Q2): a body that arrived
            # SHORT is NOT refused. It is kept as a partial witness marked
            # incomplete and allowed to proceed through the normal pipeline.
            # Law 2 of `user-event-journal.md` §Receive and idempotency was
            # amended to match: an interrupted body claims a receipt like any
            # registered envelope and is processed, with the shortfall
            # recorded (`short`/`got`) so a reader recovering the words knows
            # what arrived is partial. (Earlier the partial bytes were kept
            # but the request was refused with a 400; the ruling removed the
            # refusal.) The witness still runs before any refusal (#199).
            # The write-route dispatch is ONE table, derived from itself, so a
            # new route added later is both handled here and covered by E2's
            # "every write route commits a receipt" test (rather than slipping
            # past a hand-copied list). `WRITE_ROUTE_HANDLERS` is a class
            # attribute defined below the handler methods.
            handler = self.WRITE_ROUTE_HANDLERS.get(self.path)
            # E5: an unknown POST path is pre-receipt 404/405, not an event
            # (design §Receive and idempotency). The receipt must only commit
            # for a REGISTERED write route. But #199 still holds — his words
            # are on disk before the refusal — so the witness runs here too;
            # an unknown path has no journal receipt, and submissions.log is
            # its only home.
            if handler is None:
                log_submission(target, self.path, body, nbytes, truncated,
                               short)
                self.send_error(404)
                return
            # The journal commit authorises the response (E3 cutover): the
            # receipt is committed BEFORE the handler dispatches, so a journal
            # open/commit failure is a 503 with no 202 — the request was never
            # durably received. When the journal is disabled (journal_shadow=
            # False, the pre-cutover legacy path used only by E2's baseline),
            # no receipt is attempted and the handlers fall back to 200.
            if not truncated and self.journal_shadow:
                self._journal_receive(target)
                if self.journal_result() is None:
                    self.send_error(503)
                    return
                # E4 besteffort: submissions.log is a best-effort SHADOW
                # written AFTER the durable receipt (design step 4, not step
                # 3). Its failure is shadow_failed health on the receipt,
                # never a refusal — the receipt already committed, so the
                # request was accepted and the response must still be 202.
                shadow_ok = log_submission(target, self.path, body, nbytes,
                                           truncated=False, short=short)
                if not shadow_ok:
                    result = self.journal_result()
                    if result and result.receipt_id:
                        _journal_record_health(target, result.receipt_id,
                                               "shadow_failed")
            else:
                # Journal disabled (E2 baseline) or over-long (truncated)
                # body: submissions.log runs in its pre-cutover position,
                # before dispatch/refusal. No receipt, no health.
                log_submission(target, self.path, body, nbytes, truncated,
                               short)
            # ...and only now may a request be turned away. An over-long body
            # is still refused — the cap is what makes the read bounded — but
            # it is refused with its first MAX_BODY bytes already kept, so a
            # too-long answer loses its tail rather than all of it.
            if truncated:
                self.send_error(413)
                return
            handler(self)

        def _handle_ask(self):
            req = self._read_json()
            if req is None:
                self._reject("malformed_json"); return
            try:
                raw_question = req["question"]
                if not isinstance(raw_question, str):
                    raise TypeError
                question = raw_question.strip()
            except (KeyError, TypeError):
                self._reject("schema_invalid"); return
            if not question:
                self._reject("schema_invalid"); return
            path = os.path.join(target, ".dreamwork", "answers.md")
            stamp = time.strftime("%Y-%m-%d")
            with ANSWER_LOCK:
                text = read_text(path)
                new_text = append_human_question(text, question, stamp)
                atomic_write_text(path, new_text)
            # #342: /ask is a batched kind — wakes only in instant mode.
            if emits_wake("/ask", target):
                log_event(target, f'question for dreamer{from_hint(req.get("from"))}: '
                          f'"{one_line(question)}" -> .dreamwork/answers.md')
            self._send_receipt(json.dumps({"ok": True}), "application/json")

        def _handle_answer(self):
            req = self._read_json()
            if req is None:
                self._reject("malformed_json"); return
            try:
                title = str(req["question"]).strip()
                answer = str(req["answer"]).strip()
            except (KeyError, TypeError):
                self._reject("schema_invalid"); return
            if not title or not answer:
                self._reject("schema_invalid"); return
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
                # Atomic, like /ask thirty lines up (#370). Opening this path in
                # plain write mode empties the file before it writes, so a
                # failure between those two moments loses every question he ever
                # asked and every answer he ever gave. (Phrased without the
                # construct itself: the check for it greps the source, and an
                # explanation quoting what it forbids is a violation of it.)
                atomic_write_text(qpath, new_text)
            # #342: /answer is a batched kind — wakes only in instant mode.
            if emits_wake("/answer", target):
                log_event(target,
                          f'answer{from_hint(req.get("from"))}: "{one_line(title)}"'
                          f' -> .dreamwork/questions.md '
                          f'(fold the answer, act, move to Answered)')
            self._send_receipt(json.dumps({"ok": True}), "application/json")

        def _handle_comment(self):
            req = self._read_json()
            if req is None:
                self._reject("malformed_json"); return
            try:
                title = str(req["question"]).strip()
                note = str(req["comment"]).strip()
                section = str(req.get("section", "Open")).strip()
            except (KeyError, TypeError):
                self._reject("schema_invalid"); return
            if not title or not note or section not in ("Open", "Answered"):
                self._reject("schema_invalid"); return
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
                atomic_write_text(qpath, new_text)   # #370, as above
            hint = ("(re-evaluate — a note on an answered entry may amend it)"
                    if section == "Answered" else "(fold with the entry)")
            # #342: /comment is a batched kind — wakes only in instant mode.
            if emits_wake("/comment", target):
                log_event(target,
                          f'follow-up{from_hint(req.get("from"))}: '
                          f'"{one_line(title)}" -> .dreamwork/questions.md {hint}')
            self._send_receipt(json.dumps({"ok": True}), "application/json")

        def _handle_decide(self):
            """#289 — record a review decision into the ledger store.

            Takes ``{artifact, question_title, decision}``; opens the store
            and calls ``ledger_write.record_review_decision``. The decision is
            NOT a task (#264 boundary) and lives in ``review_decision`` keyed
            by ``artifact``. A cross-question final-decision clash raises
            ``DecisionConflict`` — surfaced as a READABLE refusal (a durable
            ``rejected`` receipt with a ``decision_conflict`` detail), never a
            500, because a conflict is a user-facing "no", not a server fault.
            Markdown-mode projects have no store, so they refuse
            (``domain_invalid``, detail ``no_store``) rather than 500. The
            store write lands under ``.dreamwork/``, which ``watched_mtime``
            walks, so the dashboard re-renders the new token on its own poll.
            """
            import ledger_store
            import ledger_write
            req = self._read_json()
            if req is None:
                self._reject("malformed_json"); return
            try:
                artifact = str(req["artifact"]).strip()
                question_title = str(req["question_title"]).strip()
                decision = str(req["decision"]).strip()
            except (KeyError, TypeError):
                self._reject("schema_invalid"); return
            if not artifact or not question_title or \
                    decision not in ledger_write.REVIEW_DECISIONS:
                self._reject("schema_invalid"); return
            dw = os.path.join(target, ".dreamwork")
            if source_of_truth(dw) != "store":
                # No store to write to (markdown-mode target). The decision
                # join already degrades to 'unlinked' there, so refusing the
                # write is the honest counterpart — never a 500.
                self._reject("domain_invalid", detail="no_store"); return
            store = None
            try:
                store = ledger_store.open_store(store_path(dw))
                ledger_write.record_review_decision(
                    store, artifact, question_title, decision,
                    actor="watch", at=None)
            except ledger_write.DecisionConflict:
                # A final decision is not silently reassignable to another
                # question: a readable refusal, not a server fault.
                self._reject("domain_invalid", detail="decision_conflict")
                return
            except Exception:
                # An unreadable/locked/corrupt store is a server fault; the
                # receipt already committed, so a 500 is the honest answer.
                self.send_error(500)
                return
            finally:
                if store is not None:
                    try:
                        store.close()
                    except Exception:
                        pass
            log_event(target,
                      f'review-decision{from_hint(req.get("from"))}: '
                      f'"{one_line(artifact)}" {decision} for '
                      f'"{one_line(question_title)}" -> .dreamwork/ledger.sqlite3')
            self._send_receipt(json.dumps({"ok": True, "decision": decision}),
                               "application/json")

        def _handle_command(self):
            req = self._read_json()
            if req is None:
                self._reject("malformed_json"); return
            try:
                kind = str(req["kind"]).strip()
                text = str(req.get("text", "")).strip()
            except (KeyError, TypeError):
                self._reject("schema_invalid"); return
            # The plugin half is read PER REQUEST rather than cached at start
            # (#86): a plugin that resolved a minute ago is sendable a minute
            # ago, and the composer already offers it on the next tick — a
            # cached set would refuse the very button it just drew. The read
            # is one small file and this is a human keypress, not a hot path.
            if kind not in COMMAND_KINDS and kind not in {
                    c["kind"] for c in plugin_commands(target)}:
                self._reject("domain_invalid"); return
            if kind != "do-next" and not text:
                self._reject("schema_invalid"); return
            # #342: the receipt already committed in do_POST (E3). The wake
            # line is the interrupt half — pre-empt kinds always fire; the
            # rest fire only in instant mode (batched kinds ride the cursor).
            if emits_wake(kind, target):
                log_event(target, command_line(kind, text, req.get("from")))
            self._send_receipt(json.dumps({"ok": True}), "application/json")

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
                self._reject("malformed_json"); return
            name = str((req or {}).get("tint", "")).strip()
            if name not in TINTS:
                self._reject("domain_invalid"); return
            if not write_tint(target, name):
                self.send_error(500)
                return
            self._send_receipt(json.dumps({"ok": True, "tint": name}),
                       "application/json")

        def _handle_run_mode(self):
            """Main-dreamer run mode (#290).

            Dual-write: authoritative gitignored `.dreamwork/run-mode` plus one
            watch-events.log line when the mode actually changes. Identical
            final is 200 + no event (idempotent; no spam on the tail). The
            client arms a shared 10s pending selection across tabs and only
            POSTs the final mode; this handler never debounce-timer itself.
            Hierarchical is not writable here — it is planned UI only.
            """
            req = self._read_json()
            if req is None:
                self._reject("malformed_json"); return
            mode = str((req or {}).get("mode", "")).strip()
            if mode not in RUN_MODES:
                self._reject("domain_invalid"); return
            current = read_run_mode(target)
            if mode == current:
                self._send_receipt(json.dumps({"ok": True, "mode": mode,
                                       "changed": False}),
                           "application/json")
                return
            if not write_run_mode(target, mode):
                self.send_error(500)
                return
            log_event(target, run_mode_line(mode, req.get("from")))
            self._send_receipt(json.dumps({"ok": True, "mode": mode, "changed": True}),
                       "application/json")

        def _handle_posture(self):
            """Four-axis posture override (#445 + #342 delivery).

            Dual-write: authoritative gitignored `.dreamwork/posture` plus
            one watch-events.log line when a posture point actually changes
            — a `posture via watch` line for the pace/asking/delegation
            triple, a `delivery via watch` line for the delivery axis. Both
            are the SAME ceremony run-mode already uses (dual-write + one
            line on real change), not two. Identical final is 202 + no event.
            The client arms a single shared 10s pending across every axis
            (one file) and only POSTs the final point; this handler never
            debounce-timer itself. Closed sets imported from lint — never
            restated. Delegation is a non-negative integer TARGET, never a
            cap (his #445 Q3). Delivery absent in the request preserves the
            axis's current value (a pace change must not silently reset wake
            routing); absent on disk is the instant default.
            """
            req = self._read_json()
            if req is None:
                self._reject("malformed_json"); return
            pace = str((req or {}).get("pace", "")).strip()
            asking = str((req or {}).get("asking", "")).strip()
            raw_dlg = (req or {}).get("delegation", "")
            try:
                delegation = int(raw_dlg)
            except (TypeError, ValueError):
                self._reject("domain_invalid"); return
            lint = _posture_vocab()
            if (pace not in lint.POSTURE_STOPS_PACE
                    or asking not in lint.POSTURE_STOPS_ASKING):
                self._reject("domain_invalid"); return
            if delegation < 0:
                self._reject("domain_invalid"); return
            current = resolve_posture(target)
            # Delivery: the request may omit it (preserve the current value so
            # a triple-only edit never silently resets wake routing); an empty
            # value or no file yet falls back to the instant default.
            delivery = str((req or {}).get("delivery", "")).strip()
            if not delivery:
                delivery = current.get("delivery", DELIVERY_DEFAULT)
            if delivery not in lint.POSTURE_STOPS_DELIVERY:
                self._reject("domain_invalid"); return
            triple_same = (current.get("pace") == pace
                           and current.get("asking") == asking
                           and int(current.get("delegation", -1)) == delegation)
            delivery_same = current.get("delivery", DELIVERY_DEFAULT) == delivery
            if triple_same and delivery_same and current.get("source") == "file":
                # Identical file-backed final: silent. (Derived-source match
                # still writes the file so an explicit override is durable.)
                self._send_receipt(json.dumps({
                    "ok": True, "pace": pace, "asking": asking,
                    "delegation": delegation, "delivery": delivery,
                    "changed": False,
                }), "application/json")
                return
            # Also silent when the on-disk file already holds exactly this
            # point (resolve may have filled source=file already above).
            file_vals = read_posture_file(target)
            if (file_vals.get("pace") == pace
                    and file_vals.get("asking") == asking
                    and file_vals.get("delegation") == delegation
                    and file_vals.get("delivery", DELIVERY_DEFAULT) == delivery
                    and len(file_vals) >= 3):
                self._send_receipt(json.dumps({
                    "ok": True, "pace": pace, "asking": asking,
                    "delegation": delegation, "delivery": delivery,
                    "changed": False,
                }), "application/json")
                return
            if not write_posture(target, pace, asking, delegation, delivery):
                self.send_error(500)
                return
            changed = False
            if not triple_same:
                log_event(target, posture_line(pace, asking, delegation,
                                               req.get("from")))
                changed = True
            if not delivery_same:
                log_event(target, delivery_line(delivery, req.get("from")))
                changed = True
            self._send_receipt(json.dumps({
                "ok": True, "pace": pace, "asking": asking,
                "delegation": delegation, "delivery": delivery,
                "changed": changed,
                "delegation_label": lint.delegation_posture(delegation),
            }), "application/json")

        def _handle_deploy(self):
            """Page-triggered `just deploy` (#462).

            Loopback peer only (trusted-LAN Host/Origin is not enough: this
            restarts the server). Single-flight: a second POST while one is
            running is a durable rejection, not a second runner. The POST
            returns as soon as the runner is scheduled; success for the
            loaded document is a new GENERATION on /mtime, not this body —
            the process may die when the deploy stops the listening snap.
            Body is ignored (no schema); empty `{}` is fine.
            """
            # Optional body parse: ignore content; malformed JSON is not a
            # hard requirement for an action with no fields — but if a body
            # was sent and is not JSON, refuse rather than guess.
            if self._body and self._body.strip():
                req = self._read_json()
                if req is None:
                    self._reject("malformed_json"); return
            if not peer_is_loopback(self.client_address):
                # A refusal, not a silent no-op: durable rejected receipt so
                # writeVerdict.landed is false (never res.ok alone).
                self._reject("domain_invalid", "not_local"); return
            if not start_deploy(target):
                # Not an error he did anything wrong — a deploy is already
                # running, most likely from his other tab.
                self._reject("domain_invalid", "in_flight"); return
            self._send_receipt(
                json.dumps({"ok": True, "started": True}),
                "application/json")

        # The single source of truth for write routes: adding a route here both
        # dispatches it and exposes it (E2 derives its route list from these
        # keys, so an eighth route fails that test instead of slipping past it).
        WRITE_ROUTE_HANDLERS = {
            "/answer": _handle_answer,
            "/ask": _handle_ask,
            "/comment": _handle_comment,
            "/command": _handle_command,
            "/decide": _handle_decide,
            "/tint": _handle_tint,
            "/run-mode": _handle_run_mode,
            "/posture": _handle_posture,
            "/deploy": _handle_deploy,
        }

        def log_message(self, *_args):
            pass

    Handler.journal_shadow = journal_shadow
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


# Module-level accessors for posture closed sets and PAGE. Bare names inside
# this file go through `_posture_vocab()` / `_get_page()`; external code
# (tests, lint) may use `watch.POSTURE_STOPS_PACE` and `watch.PAGE`.
def __getattr__(name):
    if name == "PAGE":
        return _get_page()
    if name in (
        "POSTURE_STOPS_PACE", "POSTURE_STOPS_ASKING", "POSTURE_STOPS_DELIVERY",
        "DELEGATION_POSTURES", "POSTURE_AXES", "derive_posture",
        "delegation_posture", "RUN_MODE_TO_POSTURE",
    ):
        return getattr(_posture_vocab(), name)
    raise AttributeError(f"module 'watch' has no attribute {name!r}")


if __name__ == "__main__":
    main()
