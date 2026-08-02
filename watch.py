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

# #425/#397 — make module resolution agree with CLIENT_DIR about which
# directory this file lives in. CPython realpaths sys.path[0] but NOT
# __file__, and #425 makes watch.py a symlink to deprecated/watch.py. So
# without this line the two disagree: CLIENT_DIR (abspath) is the LINK's dir,
# where client/ is, while `import watch` from a sibling — lint.py does it at
# module level — resolves through sys.path[0] to deprecated/watch.py and
# builds a SECOND module object whose CLIENT_DIR is deprecated/client, which
# does not exist. That surfaces at the first page build, not at boot.
#
# Inserting the link's own directory first makes `import watch` find the same
# file that is already running, so there is one module and one CLIENT_DIR.
# A no-op today (watch.py is a regular file, so the two directories are the
# same path and it is already on sys.path); it is what keeps #425 from
# needing to move client/ into deprecated/ alongside the module.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from user_events.sqlite import Envelope, open_journal
# #864: the EXPEDITED class predicate has ONE home; a second copy of this tuple
# here would drift from the drain's copy, which is the whole point of the module.
from user_events.delivery import EXPEDITE_KINDS
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
# #560: the store-backed status derivation is ONE leaf module (the ledger_parse
# idiom — deep, importable, testable without a server), imported here so the
# derivation logic lives NOWHERE else. A sibling import like ledger_parse /
# review_artifact, so `just deploy`'s --ship-siblings stages it beside the
# snapshot the same way (derived transitively, never a hardcoded list).
import status_derive

# #653: "is client/dist built from this tree?" — one implementation, shared
# with lint.py, so the commit-time ERROR and the serving-time reading cannot
# give different answers. Stdlib-only and a plain sibling import, so the
# deploy closure stages it like status_derive above.
import client_dist

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
# lands. The sticky kinds are chat and add-idea; every STEERING kind decays
# back to the default (the entry marked `default`, else the far-left kind)
# at submit, because a steering mode that persists silently raises the
# authority of his NEXT message (#337's reasoning). chat and
# add-idea are sticky for
# DIFFERENT reasons: add-idea so consecutive parked thoughts do not require
# re-selection, and chat because it is CONVERSATIONAL, not steering — the
# #337 authority rationale does not apply to a message channel, and a
# follow-up should never require re-selecting it. Absent means NOT sticky —
# a plugin kind that says nothing must not linger either — so the decay
# needs no third place to be remembered.
COMMANDS = (
    # #504 — `chat` is the far-left kind (Q2): his "send a message to the
    # agent" entry point, the main-dreamer first slice of #229/#270. A chat
    # send is a /command POST of kind `chat` (Q1: no new route); it rides the
    # #263 receipt and is BATCHED under #342 (Q3) — it wakes only in instant
    # mode and otherwise drains on the tick's cursor read. Implementation
    # vocabulary is chat/turn/reply, never `thread` (#229); the UI word is
    # "chat" (Q2; label shortened from "topic chat", #543). See composer-chat.md for the spine this rides.
    # NOTE: chat is far-left, NOT the default — see add-idea below (#547).
    {"kind": "chat", "label": "chat", "common": True, "sticky": True,
     "desc": "message the agent · the dreamworker replies in chat"},
    # #547 — add-idea is the DECLARED default (the `default` marker), not
    # positional: he wants his parked-thought entry point pre-selected. chat
    # stays far-left (Q2 stands); only the default selection changed. The
    # marker is read by the one resolver idiom (defaultKind in the JS), so a
    # future reorder of the row must not change the default, and a change of
    # default must not reorder the row. Exactly one entry carries it.
    {"kind": "add-idea", "label": "add idea", "common": True, "sticky": True,
     "default": True,
     "desc": "park a thought; the loop picks it up when it chooses next"},
    {"kind": "do-next", "label": "do next", "common": True, "sticky": False,
     "desc": "jump this to the front of the queue (text optional)"},
    {"kind": "do-now", "label": "do now", "common": True, "sticky": False, "danger": True,
     "desc": "interrupt the current increment and start this instead"},
    {"kind": "maintenance", "label": "maintenance", "common": False,
     "sticky": False,
     "desc": "housekeeping: grooming, re-reads, alignment passes"},
    # #843 — ingest-plan files a plan's tasks into the ledger from a path on
    # disk. common:False puts it in the ⋯ extras menu only (his ask: "not
    # shown by default, just in the extras menu"), reusing the existing
    # overflow mechanism rather than a parallel one. The text field carries
    # the filesystem path; the server (this machine is where his plans live)
    # reads it under confinement. v1 is flat filing — #842 will re-ingest
    # into the hierarchy #841 is building, so no grouping here.
    {"kind": "ingest-plan", "label": "ingest plan", "common": False,
     "sticky": False,
     "desc": "file a plan's tasks into the ledger — paste a path on disk"},
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
# the dashboard picker was removed in #547 (superseded by posture), but the
# /run-mode POST route and the file stay — the coordinator reads them on
# tick and posture derives from run-mode. `hierarchical` is rejected as
# unknown (not in RUN_MODES); it stays a planned name in the docs only.
RUN_MODES = ("lackadaisical", "hot", "assisted")
RUN_MODE_DEFAULT = "lackadaisical"
RUN_ARM_MS = 10_000
# #462 — after POST /deploy lands, how long the loaded document waits for a
# new GENERATION before naming the failure. just deploy's own readiness is
# sleep 1 + up to 5s of curl probes (~6s healthy); 30s is ~3× that budget so
# a contended box is not a false timeout, and still short enough that a hung
# deploy does not leave a spinner forever. Copy decision as much as timing:
# the page must say something, in the styleguide voice, when nothing arrives.
DEPLOY_WAIT_MS = 30_000
# #547: the run-mode description surface (#300, RUN_MODE_DESC) was picker-
# only and is removed with the dashboard picker. The mode vocabulary and
# what each pace means live in file-formats.md / SKILL.md (single source).

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
    "batched": "drain on the next tick · chats and do-now/do-next still pre-empt",
}
# #510 — orchestration: does the coordinator implement, or only dispatch +
# review? Contract copy, not marketing. The axis is inert until a consumer
# reads it (the same forward-looking-dial shape delivery held before its
# consumer).
POSTURE_ORCHESTRATION_DESC = {
    "hands-on": "the coordinator implements increments itself · may also delegate",
    "orchestrator": "coordinator implements nothing · every increment is dispatched",
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


# The client — CSS, the app shell, and the six JS blocks — lives beside this
# file under `client/` rather than in string literals (#397's extraction,
# unblocked by his 2026-07-30 ruling on #505 Q2). Read once at import and
# assembled into the page exactly as the literals were, so the served bytes
# do not change.
#
# `abspath`, never `realpath`: #425 makes `watch.py` a symlink to
# `deprecated/watch.py`, and realpath would resolve this directory to
# `deprecated/`, where the assets are not. abspath keeps the LINK's own
# directory, which is the repo root. Never cwd (guards run from elsewhere)
# and never `--target` (that is the watched project, not this skill).
SELF_DIR = os.path.dirname(os.path.abspath(__file__))

CLIENT_DIR = os.path.join(SELF_DIR, "client")

# Every asset the page is assembled from, in no particular order. One list,
# three readers: the loader below, `--autoreload`'s watched set, and the
# DATA_SIBLINGS literal that `just deploy` ships. DATA_SIBLINGS cannot be
# derived from this (deploy_state.py reads it with ast.literal_eval and a
# computed value parses to nothing), so a test pins the two equal instead.
_CLIENT_ASSETS = (
    "style.css",
    "app_body.html",
    "components.js",
    "views.js",
    "favicon.js",
    "router.js",
    "command.js",
    "shader.js",
)


def _read_client(name):
    """One client asset. Decoded from bytes so the value is byte-exact —
    text mode could translate newlines and silently change the page.

    An EMPTY file raises. Before the extraction a mangled client meant a
    mangled watch.py, which failed to parse — loud, and impossible to serve.
    Read from a file it is silent instead: an empty style.css yields
    `<style></style>` and the page still returns 200, so the dashboard comes
    up unstyled with nothing anywhere saying why. `--assert-importable` does
    not catch it either, because the module imports perfectly well. This is
    the one corruption that is cheap to detect, so it is the one refused.

    Truncation is NOT detectable here and is not claimed to be: there is no
    recorded size to compare against, and inventing a floor would be a
    literal with an expiry date. It is bounded elsewhere instead — deploy
    ships whole blobs out of git via atomic rename, so a short read there
    cannot happen; in a working tree it comes from a half-written save, which
    is what `--autoreload` re-execs on.
    """
    path = os.path.join(CLIENT_DIR, name)
    with open(path, "rb") as f:
        raw = f.read()
    if not raw:
        raise OSError(
            "client asset %s is empty. The page would still assemble and "
            "still return 200, just without it — refusing rather than "
            "serving a dashboard that is broken in silence." % path
        )
    return raw.decode("utf-8")


# Design tokens + shared shell: every watch page renders through these,
# so a redesign is a token/component edit, not a page-by-page hunt.
# STYLE keeps its <style> wrapper here so client/style.css is
# real, lintable css; the assembled bytes are unchanged.
# Read once, into a dict, so `serving_report` can answer "which revision of
# the CLIENT am I running" from the very bytes that were loaded rather than
# from a second read taken later — the same reason SELF_SRC is captured at
# import. Re-reading would answer with an edit made since, which is the
# reverse of the question.
_CLIENT_SRC = {name: _read_client(name) for name in _CLIENT_ASSETS}

STYLE = "<style>" + _CLIENT_SRC["style.css"] + "</style>"

APP_BODY = _CLIENT_SRC["app_body.html"]

COMPONENTS_JS = _CLIENT_SRC["components.js"]

VIEWS_JS = _CLIENT_SRC["views.js"]

FAVICON_JS = _CLIENT_SRC["favicon.js"]

ROUTER_JS = _CLIENT_SRC["router.js"]

COMMAND_JS = _CLIENT_SRC["command.js"]

SHADER_JS = _CLIENT_SRC["shader.js"]


def page_shell(title, body, *scripts):
    """Shared page shell. Contract: `body` opens `<div class="wrap">`
    (the shell closes it) so every watch page shares chrome and tokens.

    Each script is a separate inline classic script. The dashboard needs that
    seam for the generated native runtime: builders load first, native.js can
    resolve their bare names from the shared global lexical environment, and
    only then does the router choose the initial route. The response remains
    self-contained; no script URL is fetched.
    """
    # The icon is empty until the page knows what to say (#153): claiming a
    # state before data arrives is worse here than showing nothing, and an
    # inline link also stops the browser asking us for /favicon.ico.
    return ('<!doctype html><html><head><meta charset="utf-8">'
            f'<title>{title}</title>'
            '<link rel="icon" id="favicon" href="data:,">' + STYLE
            + '</head><body>'
            + body + ''.join('<script>' + js + '</script>' for js in scripts)
            + '</div></body></html>')


# #598 — what a mistyped link, a stale bookmark or a rebuilt-away artifact
# lands on. Until now that was BaseHTTPRequestHandler's stock error body
# (white, Times, `<h1>Error response</h1>`, `color-scheme: light dark`, no way
# back) — the one surface on the whole instance outside the design system, and
# the first one a new reader could see (visual audit 2026-07-31, D3).
#
# A STANDALONE PAGE RATHER THAN THE APP SHELL, and the audit's suggestion was
# the other way, so the reason matters. Serving `page` under a 404 status only
# works if the client router has a not-found destination; `routeOf` falls
# through to `{name:'dashboard'}` for anything it does not claim, so /tasks
# would render THE DASHBOARD under a 404 status line — a body contradicting
# both its own URL and its own status code, which is worse than the stock page
# because it is confidently wrong. Giving the router that destination is a new
# route name plus an entry in every per-route table it feeds (TINT,
# TITLE_ROUTE, TITLES) — the machinery #302/#318's table diff exists to police
# — and it boots ~600KB of JS to say one sentence, on the path a scanner hits
# hardest. That is the cost the rejected option carries; it is not paid here.
#
# DREAMWORK.md's "two renderers only agree on the day they are written" does
# not bite (and since 2026-07-31 / #614 that sentence is relaxed anyway — it
# was never a state rule; see DREAMWORK.md "One fact, one home on disk" for
# the half that still binds). It would not have bitten regardless, because
# this is not a second renderer of the visual language: it is
# `page_shell` — the one shell — around class names `client/style.css` already
# defines (`.qmissing`'s dim rail idiom, #452). It declares no colour, no font
# and no spacing of its own, so a restyle carries it along with everything
# else. What it deliberately does NOT share with `buildChat(null)` is the
# COPY, because the copy has to differ: a wrong address is not a removed chat,
# which is the audit's own O2 about reusing that sentence for a second cause.
#
# NOTHING FROM THE REQUEST IS REFLECTED. Naming the missing path would read
# better and would put a client-controlled string into an HTML body on every
# unmatched request, on a server that already treats reflection as the way a
# file in the tree becomes stored XSS against this origin (/filebytes' fixed
# Content-Type). The address bar already shows the path. Keeping it out leaves
# a constant, built once at import, with no escaping to get right.
#
# `target="_top"` because /reviewraw and /researchraw 404 INSIDE the review and
# research <iframe>s (views.js) — without it the way back would load the
# dashboard into the frame it was meant to leave.
NOT_FOUND_PAGE = page_shell(
    'dreamwork watch · not found',
    '<div class="wrap">'
    '<header class="htitlebar"><h1 class="htitle">not found</h1></header>'
    '<div class="qmissing">'
    '<div class="qmisshead">404</div>'
    '<div class="qmissbody">this address does not name anything this '
    'dashboard serves &mdash; most likely a mistyped link, or one that '
    'outlived what it pointed at. Nothing has been substituted for it.'
    '</div>'
    '<div class="qmissback"><a href="/" target="_top">&larr; back to '
    'dashboard</a></div>'
    '</div>',
    '')


# One shell serves every same-document view. The router (last, so
# window.dreambg from the shader exists before it runs) picks the initial
# view from the URL; SHADER_JS mounts the persistent background.
# The one vocabulary reaches the client here, so the composer's buttons, its
# menu, and the popped-out form never drift from what POST /command accepts.
# The core half is baked in because it is a property of THIS FILE; the plugin
# half (#86) rides /data.json because it is a property of the machine, and so
# can change under a page that is already open. `COMMANDS` is the one table
# everything downstream reads, and it is a `let` for exactly that reason.
# #505: vendored morphdom (MIT) lives beside this file so the diff algorithm
# is reviewable without opening the PAGE blob. Loaded once at import; the
# page still ships as one HTML response (no separate asset request).
# DATA_SIBLINGS: files this module loads relative to __file__ rather than
# imports, so dev/deploy_state.py's import-derived sibling closure cannot
# discover them on its own. deploy_state parses THIS literal (AST, never an
# import of this module) and ships every path on it; keep it to plain string
# literals or the parse finds nothing. First entry is the vendored reconciler.
# #653: `client_dist.check` reads the build inputs and outputs relative to
# __file__ to answer "is the committed build current", and that question must
# be answerable on the DEPLOYED instance too. Left off this tuple they would
# simply be absent there, and the reading would go red for the rest of time on
# every deployment: a permanent false red is how a staleness signal becomes
# something nobody reads. `wrapper-exports.js` is a build INPUT and rides
# along for exactly that reason — it is one of the files the manifest records.
# #630 P2 added `dev/build/src/*.js` and `client/dist/native.js` on the same
# argument; #751 P3 also reads native.js into PAGE as an inline classic script.
# The design-tool outputs remain deployment siblings only. This tuple is the SECOND
# statement of "which files the build reads" — the first is
# `client_dist.expected_inputs`, which globs the tree — and it is a second
# statement only because deploy AST-parses this and an ast.literal_eval cannot
# run a glob. It is therefore CHECKED rather than trusted:
# `test_client_dist.test_deploy_declares_and_tracks_every_file_the_dist_check_reads`
# derives its want-set from `expected_inputs`, so a fifth source file added
# without a line here is a named red rather than a deployment that reads stale
# forever.
DATA_SIBLINGS = ("SKILL.md", "vendor/morphdom.min.js", "vendor/LICENSE.morphdom",
                 "client/style.css",
                 "client/app_body.html",
                 "client/components.js",
                 "client/views.js",
                 "client/favicon.js",
                 "client/router.js",
                 "client/command.js",
                 "client/shader.js",
                 "dev/build/wrapper-exports.js",
                 "dev/build/src/delegate.js",
                 "dev/build/src/native-entry.js",
                 "dev/build/src/probe.js",
                 "dev/build/src/research.js", "dev/build/src/goals.js",
                 "dev/build/src/registry.js",
                 "client/dist/manifest.json",
                 "client/dist/ds/index.js",
                 "client/dist/ds/styles.css",
                 "client/dist/native.js")


def _load_morphdom_js():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "vendor/morphdom.min.js")
    with open(path, encoding="utf-8") as f:
        return f.read()


MORPHDOM_JS = _load_morphdom_js()


def _load_native_js():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        client_dist.NATIVE_REL)
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if not src:
        raise OSError("client/dist/native.js is empty")
    return src


NATIVE_JS = _load_native_js()

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
                  + "const RUN_ARM_MS = " + json.dumps(RUN_ARM_MS) + ";\n"
                  + "const DEPLOY_WAIT_MS = " + json.dumps(DEPLOY_WAIT_MS) + ";\n"
                  + "/*__POSTURE_VOCAB__*/"
                  + MORPHDOM_JS
                  + COMPONENTS_JS + VIEWS_JS + FAVICON_JS + SHADER_JS,
                  NATIVE_JS,
                  ROUTER_JS + COMMAND_JS)

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
        + "const POSTURE_STOPS_ORCHESTRATION = "
        + json.dumps(list(lint.POSTURE_STOPS_ORCHESTRATION)) + ";\n"
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
        + "const POSTURE_ORCHESTRATION_DESC = "
        + json.dumps(POSTURE_ORCHESTRATION_DESC, ensure_ascii=True) + ";\n"
    )
    _PAGE_CACHE = _PAGE_TEMPLATE.replace("/*__POSTURE_VOCAB__*/", vocab)
    return _PAGE_CACHE


def age_str(seconds):
    for unit, div in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= div:
            return f"{int(seconds // div)}{unit}"
    return f"{int(seconds)}s"


def read_text_bounded(path, limit):
    """`(text, truncated)` — the ONLY way to get a short read, and it says so.

    #632 part two. The bug that deleted twelve answered entries was not really
    the 200,000 cap; it was that exceeding the cap was SILENT. A short string
    is indistinguishable from a whole file, so every caller downstream — a
    writer, a parser, a renderer — was entitled to believe it had everything.

    So a bounded read now returns the flag with the text, and a caller has to
    take the flag to get the string. That is the whole mechanism: it is no
    longer possible to truncate without holding, in your hand, the fact that
    you did. What you then DO about it is yours to decide — refuse, warn,
    render a marker — but you cannot decide nothing by accident.

    Reads one byte past the limit to distinguish "exactly the limit" from
    "longer than the limit", because a file whose length equals the cap is not
    truncated and must not be reported as if it were.
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            if limit is None:
                return f.read(), False
            text = f.read(limit + 1)
    except OSError:
        return None, False
    if len(text) > limit:
        return text[:limit], True
    return text, False


def read_text(path, limit=None):
    """A file's text, or None. UNBOUNDED unless a caller names a `limit`.

    THE DEFAULT USED TO BE 200_000 AND THAT WAS THE BUG (#632). Not because
    the number was wrong — raising it only moves the cliff — but because a
    display-shaped default reached a durability path, and defaults are exactly
    what review does not see. `/answer` read questions.md through this
    function, appended his answer to the SHORT text, and wrote the result back
    over the full file: twelve answered entries gone, no archive, the file cut
    mid-word.

    Now the safe thing is what you get for saying nothing, and a bound is
    something you must ask for by name. A caller that names a limit has said
    so deliberately and should generally use `read_text_bounded`, which also
    hands back whether the cut happened.

    The files this reads are a few hundred kilobytes. It was never the memory
    that justified the cap; it was habit.
    """
    text, _ = read_text_bounded(path, limit)
    return text


def read_text_full(path):
    """The WHOLE file, or None — the reader every durable write path uses.

    Deliberately a synonym for `read_text(path)` now that the default is
    unbounded. THE NAME IS THE POINT and is why it survives as its own
    function: at a write call site, `read_text_full` states the requirement in
    the line a reviewer is reading, so a future edit that reintroduces a bound
    has to visibly contradict it rather than quietly change a default. The
    source guard in test_watch.py asserts the write door calls this by name.
    """
    return read_text(path)


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

# ...and the other half of the same answer (#397). watch.py's bytes used to
# BE the dashboard — every css and js byte lived in a string literal in this
# file — so SELF_SRC alone was a complete identity. It no longer is: 10,500
# of those lines now live under client/, and the ordinary UI commit leaves
# this file byte-identical. Without the client here, the `.gserve` row would
# report `current` for a dashboard serving last week's stylesheet, which is
# exactly the #140 wound ("make a stale view announce itself") reopened by
# refactor rather than by a proxy.
#
# The client half comes from _CLIENT_SRC — the strings actually loaded,
# re-encoded — rather than from a second read, so it is the identity of what
# is RUNNING and not of what is on disk now. utf-8 round-trips exactly, so
# this is byte-equal to the file that was read. Non-client siblings (the
# vendored reconciler) are read here; they are static between deploys.
try:
    _self_assets = {"client/" + _n: _s.encode("utf-8")
                    for _n, _s in _CLIENT_SRC.items()}
    for _rel in DATA_SIBLINGS:
        if _rel not in _self_assets:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   _rel), "rb") as _f:
                _self_assets[_rel] = _f.read()
    SELF_ASSET_SRC = _self_assets
except OSError:
    SELF_ASSET_SRC = None


def serving_report(target, src=None, path="watch.py", assets=None):
    """Which revision of the DASHBOARD this process is running, against
    `target`'s history of it.

    The dashboard is `path` PLUS the client assets it loaded (#397) — see
    SELF_ASSET_SRC. A revision matches only when every one of those files
    matches it, because a client-only commit leaves `path` identical and
    would otherwise read as `current`.

    `src` and `assets` are the two halves of ONE identity, so they default
    together: supply neither and you get this process's own. Supplying `src`
    alone means "judge this source", and the asset half then defaults to
    empty rather than to this process's client — mixing one identity's
    Python with another's stylesheets would be incoherent, and it is what
    lets a caller ask the pre-#397 question deliberately.

    Every failure is its own named state and none of them is "no match" —
    deployed.py's rule, and the bug it was written for: **a comparison that
    could not run must never look like a comparison that ran and found
    nothing.** `no repo` is the ordinary answer for a project that is not
    this dashboard's own checkout, and it is a reading, not a fault.

    Never takes `.git/index.lock`: `--no-optional-locks` on every call. His
    CLAUDE.md carries a live mitigation about that lock.
    """
    if assets is None:
        # Only a fully-defaulted call adopts this process's client; see the
        # docstring. SELF_ASSET_SRC is None when the assets could not be
        # re-read at import, and that degrades to the watch.py-only answer
        # rather than to a false match.
        assets = SELF_ASSET_SRC if src is None else {}
        if assets is None:
            assets = {}
    src = SELF_SRC if src is None else src
    out = {"state": None, "rev": None, "missing": [], "note": None}
    # #653 — the serving-time half of the staleness signal, set here so it
    # rides EVERY return path below (a reading that is present only on the
    # happy path is absent exactly when something is wrong).
    #
    # It describes this SKILL's tree, not `target`'s: client/dist lives beside
    # this module. It is recomputed only when `serving_cached` misses, which
    # is when HEAD moves or the process is replaced — and that covers both
    # ways dist can go stale: a deploy is a new process, and `--autoreload`
    # re-execs on precisely the client edit that would strand the build.
    out["client_dist"] = client_dist.check(SELF_DIR)
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

    def assets_match(rev):
        """Do the running client assets equal their blobs at `rev`?

        A path ABSENT from `rev` is skipped rather than counted against it:
        each revision is judged by what IT carried. Every revision before
        #397 has no `client/` at all, and a target that tracks `watch.py`
        without the client is an ordinary project rather than a broken one —
        disqualifying those would turn every such answer into "matches no
        revision", which is the confident-wrong-answer this module exists to
        refuse. Where the file IS carried it is compared, which is the whole
        of the fix: at HEAD the assets exist, so a stale client cannot pass.
        """
        for rel, want in assets.items():
            try:
                blob = g("show", "%s:%s" % (rev, rel))
            except (OSError, subprocess.SubprocessError):
                continue                    # not carried at this revision
            if blob != want:
                return False
        return True

    try:
        head_ok = g("show", "HEAD:%s" % path) == src
    except (OSError, subprocess.SubprocessError) as exc:
        out["state"] = SERVE_ERROR
        out["note"] = "could not read %s at HEAD: %s" % (path, exc)
        return out
    if head_ok:
        if assets_match("HEAD"):
            out["state"] = SERVE_CURRENT
            out["rev"] = g("rev-parse", "--short", "HEAD").decode().strip()
            return out
        # watch.py matches HEAD but the client does not. Pre-#397 this state
        # was unreachable — the css lived in watch.py — and it is exactly the
        # one a watch.py-only comparison reports as `current`.

    # Widen the candidate revisions to every file in the identity, or a
    # client-only commit is not among them and a stale client falls through
    # to SERVE_UNTRACKED ("matches no revision"), which is a confident wrong
    # answer rather than a silent one. The emptiness check above stays scoped
    # to `path`: it asks whether this target carries the dashboard at all.
    if assets:
        try:
            revs = g("log", "--format=%H", "--", path,
                     *sorted(assets)).decode().split() or revs
        except (OSError, subprocess.SubprocessError):
            pass                        # keep the narrower list; never fail here

    for rev in revs:
        try:
            if g("show", "%s:%s" % (rev, path)) != src:
                continue
        except (OSError, subprocess.SubprocessError):
            continue
        if assets_match(rev):
            break
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
              path, *sorted(assets)).decode().splitlines()]
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
# #551: optional override for the /remind route's coordinator inbox dir.
# None → relay.relay's default (~/.cache/agent-comms/ud-dreamwork); a str or
# Path → that dir; a callable → invoked with no args, returns the dir. Tests
# set this (setattr) so a check never writes the real shared inbox; the
# browser guard redirects its spawned server via the DREAMWORK_REMIND_INBOX_DIR
# env var (read once at load). Production leaves it None and relay appends to
# the coordinator's tailed inbox.
_remind_inbox_dir = os.environ.get("DREAMWORK_REMIND_INBOX_DIR") or None


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


# #567: where `just deploy`'s output lands while the recipe runs. Beside the
# deployed dir's `serve.log` — the SAME ~/.cache/dreamwork/deployed the recipe
# itself writes its new server's output to — NOT under the target's
# `.dreamwork/`: watched_mtime walks that tree, and an append-mode log would
# bump the /mtime poll on every printed line, arming spurious mid-deploy
# reloads. None resolves to that default deploy dir; tests point this at a tmp
# dir so the log is isolated and the broken-pipe mechanism (a print-after-stop
# that dies on a pipe the dying server held) is observable against the REAL
# runner rather than a stand-in.
_deploy_log_dir = None


def _deploy_log_path():
    """Resolve deploy.log's path (override hook for tests)."""
    d = _deploy_log_dir or os.path.expanduser("~/.cache/dreamwork/deployed")
    return os.path.join(d, "deploy.log")


def _default_deploy_runner(target):
    """Run `just deploy` in `target`, detached from this server's lifetime (#567).

    The recipe's `--stop-deployed` kills the process running THIS function —
    the deployed server that received POST /deploy. Two things must survive
    that death or the deploy self-bricks:
      1. The recipe's OUTPUT — written to a FILE (deploy.log beside the
         deployed dir's serve.log), never a pipe whose read end the dying
         server holds. capture_output=True's pipes close when the server dies,
         and the recipe's next print (its own progress, AFTER --stop-deployed)
         hits a broken pipe (SIGPIPE) and dies mid-flight — before it ships the
         snapshot or starts the new server. That is the #567 incident: his
         dashboard went dark until a shell redeploy.
      2. The recipe PROCESS — spawned with start_new_session=True so it is in
         its own process group; a signal aimed at the server cannot reach it,
         and reparented to init it outlives its spawner.
    The runner thread still wait()s, so the single-flight slot is held for the
    deploy's life; when the server is stopped the thread dies with the process
    and the slot dies with it — the new server starts with a clear slot.
    """
    try:
        log_path = _deploy_log_path()
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        with open(log_path, "ab") as log:
            proc = subprocess.Popen(
                ["just", "deploy"],
                cwd=str(target),
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            proc.wait()
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


def first_lost_line(old, new):
    """The first non-blank line of `old` missing from `new`, or None (#632).

    These files are APPEND-ONLY through the HTTP handlers: `append_subbullet`
    inserts a block and copies every other line, `append_human_question`
    inserts an entry above `## Answered`, a chat turn concatenates. None of
    them may remove a line. So the invariant is not "the file got bigger" —
    it is that every line still there, in order, which is a SUBSEQUENCE test
    and is exactly strong enough to catch truncation, deletion and reordering
    while permitting any insertion.

    NON-BLANK lines only, and that is a deliberate weakening. `rstrip()` in
    `append_human_question` legitimately collapses trailing blanks to one, so
    a whole-line test would refuse a correct write. Losing a blank line is
    cosmetic; losing a line with content on it never is.

    Why this rather than "the answered-entry count must not decrease": that
    rule fights normal operation. The loop FOLDS entries from Open to
    Answered by editing the file directly, which legitimately moves entries
    around, and a count rule would either fire on folds or be too loose to
    catch a partial deletion. This invariant cannot false-positive on a fold
    for the simple reason that a fold does not come through these handlers at
    all — nothing the server writes here is ever allowed to lose a line.
    """
    it = iter(new.splitlines())
    for line in old.splitlines():
        if not line.strip():
            continue
        for candidate in it:
            if candidate == line:
                break
        else:
            return line
    return None


def rewrite_append_only(path, mutate, *, seed_missing=False):
    """The ONE door through which a durable human-channel file is rewritten.

    Read the file WHOLE, apply an append-only mutation, verify nothing was
    lost, write atomically. Returns `(status, value)`:

      ("missing", None)    the file is not there and the caller wanted it
      ("unmatched", None)  the mutation found no entry to attach to
      ("lossy", line)      REFUSED — `line` is the first content line dropped
      ("ok", new_text)     written

    This exists because #632 was not really a bug in any one handler. Three
    handlers each did read → mutate → write, each read through the bounded
    `read_text`, and each would have had to remember not to. Collapsing them
    onto one function makes the safe read and the loss check structural
    rather than remembered: a fourth handler written next month gets both by
    calling this, and cannot get neither.

    REFUSING IS SAFE HERE, and that is not a general claim about refusal —
    it is a specific consequence of `log_submission` (#199), which has
    already written his exact words to `submissions.log` before dispatch even
    began. So a refusal costs a fold, not his input, whereas the silent write
    it replaces cost twelve answered entries. That asymmetry is the whole
    argument for failing closed on this path.
    """
    text = read_text_full(path)
    if text is None and not seed_missing:
        return ("missing", None)
    old = text or ""
    new_text, matched = mutate(old)
    if not matched:
        return ("unmatched", None)
    lost = first_lost_line(old, new_text)
    if lost is not None:
        return ("lossy", lost)
    atomic_write_text(path, new_text)
    return ("ok", new_text)


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


# ── #504 composer `chat` — the chats-v1 transcript (main-dreamer first slice
# of #229/#270). A chat send is a /command POST of kind `chat`; the #263
# receipt is the durable home (committed in do_POST before dispatch), and this
# application step writes the CONVERSATIONAL truth: an append-only transcript of
# framed turns. The receipt id of the send that CREATES a chat is its identity
# (1:1 — #373 adds follow-up threading + the worker). Reply
# instructions attach at consume (journal_consume), not here; the main dreamer
# replies by appending an agent turn through the dreamwork CLI to this same
# transcript. Format (#229 `dw-turn` framing), each turn:
#   <!-- dw-turn role=human|agent at=<iso>[ receipt=<id>] -->
#   <multi-line markdown text; structural marker lines backslash-escaped>
#   <!-- /dw-turn -->
# Two rules make his text unforgeable as a turn without destroying its shape:
# the writer backslash-escapes any complete body line shaped like an open/close
# marker, and the parser anchors both structural markers at line start. The
# escape is reversible (including pre-existing backslashes), so the parsed body
# is still his exact text. A transcript is a document, never one log event.
# Only a complete marker-shaped line is escaped; an inline mention is prose.
# Existing backslashes are doubled on disk and restored on read, so the escape
# itself cannot erase user text.
# Indexes (title, turn count, status) are DERIVED at read time — chat.json
# carries identity only, never a second source of truth.
CHAT_DIR = "chats-v1"
CHAT_PREVIEW_N = 80
# A chat id is the creating journal receipt id (UUID hex) and a DIRECTORY NAME
# under chats-v1/, so it must be a safe path component — no separator, no `..`. The
# /chatdata endpoint validates against this before it ever joins the id onto a
# path, so a typo'd or hostile id is a 404, never a traversal. Mirrors
# bin/ud-dw-chat's _CHAT_ID (the CLI's reply guard), one definition of "what
# counts as a chat id" shared by the writer, the reader and the route.
_CHAT_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _chat_root(target):
    """`.dreamwork/chats-v1/` — the chat transcript store root."""
    return os.path.join(target, ".dreamwork", CHAT_DIR)


def _chat_turn_block(role, text, at, receipt_id=None):
    """One `dw-turn` block for the append-only transcript. Pure; testable."""
    rid = f" receipt={receipt_id}" if receipt_id else ""
    return (f"<!-- dw-turn role={role} at={at}{rid} -->\n"
            f"{_chat_turn_text(text, encode=True)}\n"
            f"<!-- /dw-turn -->\n")


_CHAT_TURN_RE = re.compile(
    r"^<!--\s*dw-turn\s+role=(?P<role>\w+)\s+at=(?P<at>\S+)"
    r"(?:\s+receipt=(?P<rid>\S+))?\s*-->[ \t]*\r?$\n"
    r"(?P<body>.*?)\r?\n^<!--\s*/dw-turn\s*-->[ \t]*\r?$", re.DOTALL | re.MULTILINE)


def _parse_chat_turns(text):
    """[{role, at, receipt, body}] in file order. Degrades to [] on absent."""
    if not text:
        return []
    out = []
    for m in _CHAT_TURN_RE.finditer(text):
        out.append({
            "role": m.group("role"),
            "at": m.group("at"),
            "receipt": m.group("rid") or "",
            "body": _chat_turn_text(m.group("body"), encode=False),
        })
    return out


def _chat_preview(text, n=CHAT_PREVIEW_N):
    """One-line, length-capped preview — a title/label, never a second truth."""
    s = one_line(text)
    return s[:n - 1].rstrip() + "…" if len(s) > n else s


def _chat_exists(target, chat_id):
    """A chat exists iff its transcript holds >= 1 parsed turn.

    Reuses ``_parse_chat_turns`` (the production reader ``list_chats`` uses),
    so the existence test cannot disagree with the dashboard about what counts
    as a chat — the same discipline ``bin/ud-dw-chat reply`` applies. A dir
    with a transcript but zero turns is not a chat you can reply to, and
    ``list_chats`` skips exactly those, so this matches. Pure in its inputs;
    testable. This is the reply guard: ``apply_chat_turn`` CREATES the chat on
    its first turn, so this runs BEFORE the call so a typo'd id is a loud
    refusal, never a forked conversation (#577)."""
    tpath = os.path.join(_chat_root(target), chat_id, "transcript.md")
    return bool(_parse_chat_turns(read_text(tpath)))


def apply_chat_turn(target, chat_id, role, text, at=None, receipt_id=None):
    """Append one turn to chats-v1/<chat_id>/transcript.md (+ chat.json).

    Creates the chat on its first turn (main-dreamer mode). The transcript is
    append-only conversational truth; chat.json carries identity only.
    `role` is 'human' (his send, written here) or 'agent' (a reply the
    dreamwork CLI appends). Returns True on success, False on a bad id / IO
    failure (the receipt already committed, so this never refuses the 202).
    """
    if not chat_id:
        return False
    cdir = os.path.join(_chat_root(target), chat_id)
    try:
        os.makedirs(cdir, exist_ok=True)
    except OSError:
        return False
    stamp = at or time.strftime("%Y-%m-%dT%H:%M:%S")
    meta = os.path.join(cdir, "chat.json")
    if not os.path.exists(meta):
        atomic_write_text(meta, json.dumps({
            "id": chat_id,
            "mode": "main-dreamer",
            "created_from_receipt": receipt_id or chat_id,
            "created": stamp,
        }, indent=2) + "\n")
    tpath = os.path.join(cdir, "transcript.md")
    # #632: WHOLE read. A transcript is append-only and grows without bound, so
    # reading it through the display cap would silently drop the oldest turns
    # of every chat that passed 200,000 chars — the same defect that deleted
    # twelve answered entries, on a file whose whole purpose is to be a record.
    prev = read_text_full(tpath) or ""
    atomic_write_text(tpath, prev + _chat_turn_block(role, text, stamp, receipt_id))
    return True


# #709 — the archive state is a sidecar MARKER FILE, not a chat.json field.
# chat.json is documented identity-only ("never a second source of truth"), and
# apply_chat_turn owns it on creation, so a mutable field there would both break
# that contract and add a read-modify-write second writer to a file the turn
# writer touches. The marker writes a file the turn writer NEVER touches, so it
# is not a second writer in the #577 sense (which bound the transcript path).
# Existence IS the state — the same shape .dreamwork/watch-tint and run-mode
# keep — so unarchive is the symmetric inverse (remove the file), designed in
# cheap rather than retrofitted.
CHAT_ARCHIVED_NAME = "archived"


def _chat_archived_marker(cdir):
    """Path to a chat's archive marker inside its chats-v1 dir."""
    return os.path.join(cdir, CHAT_ARCHIVED_NAME)


def is_chat_archived(target, chat_id):
    """Whether a chat is archived (#709). Existence of the marker IS the state."""
    return os.path.exists(_chat_archived_marker(
        os.path.join(_chat_root(target), chat_id)))


def set_chat_archived(target, chat_id, archived):
    """Set or clear a chat's archive flag (#709).

    The writer for archive state — owns ONLY the marker file, disjoint from
    apply_chat_turn's transcript/chat.json, so the ONE turn-writer is
    untouched. ``archived=True`` creates the marker; ``False`` removes it.
    Returns True on success, False on a bad id, a non-existent chat, or IO
    failure. Idempotent: archiving an archived chat (or unarchiving a live
    one) is a no-op success.

    The existence guard runs BEFORE the write — mirroring _chat_exists
    running before apply in _handle_chat_reply (#577): a typo'd id is a loud
    refusal, never a phantom marker for a chat that does not exist. Without
    it, makedirs+marker would fork an empty dir that looks archived."""
    if not chat_id or not _CHAT_ID_RE.match(chat_id):
        return False
    cdir = os.path.join(_chat_root(target), chat_id)
    # refuse before any write: a chat that has no parsed turn is not one you
    # can archive (same reader list_chats / _chat_exists use). Reuses the
    # production existence test so it cannot disagree with the dashboard.
    if not _parse_chat_turns(read_text(os.path.join(cdir, "transcript.md"))):
        return False
    marker = _chat_archived_marker(cdir)
    try:
        if archived:
            atomic_write_text(marker, "1\n")
        else:
            if os.path.exists(marker):
                os.remove(marker)
        return True
    except OSError:
        return False


def _chat_record_and_turns(cdir, name):
    """Derive one chat's record (+ its parsed turns) from a chats-v1 dir.

    The single source for the derivation the dashboard list and the per-chat
    page both serve, so title / turn count / status / unread can never
    disagree between them. Returns (record, turns); record is None when the
    dir holds no parsed turn (list_chats skips exactly those).

    #562: ``unread`` is True when the last turn is his (a human turn with no
    agent turn after it) — derived from the parsed turns, the same place
    status comes from. Note the relationship: pending (no agent turn yet) is
    a SUBSET of unread — a chat he followed up on after a reply is replied
    AND unread. chat.json stays identity-only (#504 contract)."""
    turns = _parse_chat_turns(read_text(os.path.join(cdir, "transcript.md")))
    if not turns:
        return None, []
    meta = _safe_json(read_text(os.path.join(cdir, "chat.json"))) or {}
    humans = [t for t in turns if t["role"] == "human"]
    agents = [t for t in turns if t["role"] == "agent"]
    first_human = humans[0]["body"] if humans else turns[0]["body"]
    # #709 — `archived` is read from the sidecar marker in the SAME dir as the
    # transcript, so it can never drift from "does this chat exist". Co-located
    # with the derivation the list and the page both serve (#136: an archived
    # chat is a real chat whose transcript still parses, distinct from one the
    # reader could not see).
    rec = {
        "id": meta.get("id", name),
        "title": _chat_preview(first_human),
        "mode": meta.get("mode", "main-dreamer"),
        "turns": len(turns),
        "status": "replied" if agents else "pending",
        "unread": turns[-1]["role"] == "human",
        "archived": os.path.exists(_chat_archived_marker(cdir)),
        "created": meta.get("created", ""),
        "last_at": turns[-1]["at"],
        "last_by": turns[-1]["role"],
        "preview": _chat_preview(turns[-1]["body"]),
    }
    return rec, turns


def list_chats(target):
    """Derived chat records for the dashboard's minimal topic-chat list (Q4).

    One per chats-v1/<id>/ dir that has a transcript. Title / turn count /
    status / unread are DERIVED from the transcript (no second source of
    truth) via _chat_record_and_turns. `status` is 'replied' once an agent
    turn exists (the dreamer replied), else 'pending'. `unread` is True when
    the last turn is his. Newest first by chat.json `created`, dir-name
    fallback. Degrades to [] when the store is absent (the slice ships before
    the apply lane wires the write).

    #709 — archived chats LEAVE the live list (his phrase: "chats that are
    done"). An empty return here is NOT "no chats": every chat may be
    archived, in which case the store holds transcripts that still parse but
    none surface here (#136 — "no archived chats" and "the archive state
    could not be read" must not render identically; the dirs and their
    transcripts remain, so the state is readable, not absent).
    """
    root = _chat_root(target)
    if not os.path.isdir(root):
        return []
    chats = []
    for name in os.listdir(root):
        cdir = os.path.join(root, name)
        if not os.path.isdir(cdir):
            continue
        rec, _ = _chat_record_and_turns(cdir, name)
        # archived chats leave the live list; their transcript stays readable
        # at /chat/<id> via /chatdata (which does not filter on archived).
        if rec and not rec["archived"]:
            chats.append(rec)
    chats.sort(key=lambda c: c.get("created") or c["id"], reverse=True)
    return chats


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


def _resolve_statx_libc():
    """Resolve libc for statx — CDLL(None) first, reporting WHICH won (#680).

    Mirrors ``file_notify._libc``'s ladder so this repo has ONE ctypes form,
    not two: ``CDLL(None)`` dlopens the already-loaded process image and is the
    form that works on musl, where ``find_library('c')`` returns None (and the
    old find_library-only form here then returned None, or — worse — a later
    author copying this site reached for ``CDLL(None)`` and loaded the main
    program *silently*). The symbol is probed, not assumed.

    Returns ``(libc, label)`` where ``label`` names the resolution that won, so
    a silent ``CDLL(None)`` (an image with no real libc) is distinguishable from
    a real one — that reporting is the entire point of #680. On failure returns
    ``(None, 'unresolved: …')``: never a silent None.
    """
    try:
        import ctypes
        import ctypes.util
    except ImportError as exc:
        return None, f"unresolved: no ctypes ({exc})"
    # CDLL(None) first — the robust form. Probe statx so a load WITHOUT it is
    # not reported as a resolution.
    try:
        lib = ctypes.CDLL(None, use_errno=True)
        lib.statx  # probe
        return lib, "CDLL(None)"
    except (OSError, AttributeError):
        pass
    name = ctypes.util.find_library("c")
    if not name:
        return None, "unresolved: find_library('c') returned None"
    try:
        lib = ctypes.CDLL(name, use_errno=True)
        lib.statx
        return lib, f"find_library: {name}"
    except (OSError, AttributeError) as exc:
        return None, f"unresolved: {name} has no statx ({exc})"


# ── #689: record which statx-libc resolution won, readable after the fact ─
# Mirrors file_notify.Watcher.selection_log (#664): the label that
# _resolve_statx_libc returns names which load won, and that fact was
# computed and discarded — the exact silence #680 was filed to end. Silent:
# no log line per lookup; a diagnostic or check reads this after the fact.
_statx_libc_label: str | None = None


def _statx_birth_ns(path):
    """Return birth time in nanoseconds, or None when unavailable.

    Stdlib-only: ctypes against libc.statx. Missing symbol, non-Linux,
    errno, or a mask without btime all return None — never a lie.

    libc is resolved via ``_resolve_statx_libc`` — the robust CDLL(None)-first
    form that matches ``file_notify._libc`` (#680). The old find_library-only
    form returned None on musl and was the attractor for a silent CDLL(None).
    The winning label is stored in ``_statx_libc_label`` so the resolution is
    legible after the fact — not computed and discarded (#689).
    """
    try:
        import ctypes
    except ImportError:
        return None
    libc, resolved_as = _resolve_statx_libc()
    global _statx_libc_label
    _statx_libc_label = resolved_as  # #689: record, don't discard
    if libc is None:
        return None
    statx = libc.statx

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
    # READ connection through the one door (#645 increment 5). Core's READ path
    # opens ``?mode=ro`` with ``query_only=ON``; soft-failure is preserved.
    from dreamwork_db import StoreSpec
    from dreamwork_db import core as db_core
    try:
        conn = db_core._connect(
            StoreSpec(path=db, busy_timeout_ms=5000), db_core.Access.READ
        )
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


def _sig_text(s):
    """Collapse whitespace so a re-wrap of the same words is the same
    signature (#509). The loop re-writes questions.md on tick, and a long
    entry's body lines get re-wrapped; a line-break-only change is not a
    content change, so the digest is over the WORDS, not the column the
    writer happened to wrap at — otherwise the longest entry (#229: nested
    tables, code fences, ~100 lines) phantom-fires question-updated on
    every rewrite. Note/answer text is already single-spaced by the parser,
    but one normalisation over every text field is the rule that keeps the
    class from recurring on any entry the re-wrap touches."""
    return " ".join((s or "").split())


def _entry_content_digest(entry):
    """Stable digest of one questions.md entry's visible content."""
    payload = {
        "title": _sig_text(entry.get("title")),
        "body": _sig_text(entry.get("body")),
        "follows": [
            {**f, "text": _sig_text(f.get("text"))}
            for f in (entry.get("follows") or [])
        ],
        "answers": [
            {**a, "text": _sig_text(a.get("text"))}
            for a in (entry.get("answers") or [])
        ],
        "answer": _sig_text(entry.get("answer")),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _title_sig_key(title):
    return hashlib.sha256((title or "").encode("utf-8")).hexdigest()[:16]


# #534 — version the sig store so a digest-ALGORITHM change (the #509
# whitespace normalisation was the live instance) does not fire one phantom
# question-updated event per entry on the first collect after deploy. A store
# written under an older algorithm sees every stored digest differ and would
# burst ~21 phantom events for content that did not change. The fix: stamp the
# store with the `algo` it was written under, and on a mismatch re-seed SILENTLY
# — recompute every live entry's digest under the CURRENT algorithm, persist the
# store with the new `algo`, and emit ZERO events (an event says "his question
# file changed"; an algorithm upgrade is not that).
#
# The generations are an explicit append-only list so the NEXT algorithm change
# is a one-line addition (a new trailing alias + bump SIG_ALGO), not a
# re-discovery of this task. `v0` is an UNMARKED store (or one predating this
# field) — the pre-#509 raw-text digests that live stores still hold.
_SIG_ALGO_GENERATIONS = ("sigtext-v0", "sigtext-v1")
SIG_ALGO = _SIG_ALGO_GENERATIONS[-1]   # the generation the code writes now


def _store_algo(store):
    """The algorithm generation a loaded store was written under.

    A store predating #534 carries no `algo` key, so it is treated as the
    oldest generation (`sigtext-v0`): unmarked == pre-normalisation raw
    digests. An unrecognised marker is also treated as the oldest, since the
    only safe thing to do with an unknown algorithm is re-seed to the current
    one (and the next-oldest known alias would skip a real upgrade)."""
    algo = store.get("algo") if isinstance(store, dict) else None
    if algo in _SIG_ALGO_GENERATIONS:
        return algo
    return _SIG_ALGO_GENERATIONS[0]


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

    # #534 — an algorithm-generation change is NOT a content change, so it may
    # emit zero events. When the store was written under an older generation,
    # recompute every live entry's digest under the CURRENT algorithm and
    # persist the store with the new algo. This is the silent migration:
    # content did not change, so no event may fire.
    # #516 (Decision 3) — the stamp on re-seed is `now` for every
    # PREVIOUSLY-SEEN entry, never the carried prior value (first sight keeps
    # None — nothing to lie about). Cross-algorithm change detection is impossible
    # (an old-algo digest differs from a new-algo one for UNCHANGED content by
    # definition, and the old implementation is not retained), so a re-seed
    # collect cannot tell a genuinely-changed entry from an unchanged one —
    # and carrying the prior stamp was the silent-lie option for the changed
    # one (its age went stale permanently: the new-algo digest of its changed
    # content means no later collect ever fires). A uniform `now` is the
    # visible, self-aging alternative; algo upgrades are rare (one ever).
    if _store_algo(store) != SIG_ALGO:
        reseeded_at = time.time()
        for e in entries:
            key = _title_sig_key(e.get("title"))
            prev = store.get(key)
            # stamp now for a PREVIOUSLY-SEEN entry — the swallow fix (#516),
            # see the block comment. A first-sight entry (no prior row) keeps
            # None: its content definitionally has not changed since first
            # sight, and stamping it would lie "just updated" on first load.
            seen_at = reseeded_at if isinstance(prev, dict) else None
            store[key] = {
                "digest": _entry_content_digest(e),
                "updated_at": seen_at,
                "title": (e.get("title") or "")[:120],
            }
            e["updated_at"] = seen_at
        store["algo"] = SIG_ALGO
        _write_question_sigs(path, store)
        return entries

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
            # #516 (Decision 1) — question-updated is a per-kind signal
            # routed under the delivery mode, not an always-instant
            # carve-out: withheld in batched (the tick's questions.md read
            # IS the drain), fired in instant. The stamp above lands either
            # way — withholding the wake IS batching, not dropping.
            if emits_wake("question-updated", target):
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
        store["algo"] = SIG_ALGO
        _write_question_sigs(path, store)
    return entries


def _write_question_sigs(path, store):
    """Atomically persist the sig store (tmp + os.replace); best-effort.

    Lifted out of track_question_updates so the #534 silent re-seed and the
    normal change path share one writer with one algo-stamping discipline."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=0, sort_keys=True)
        os.replace(tmp, path)
    except OSError:
        pass


def collect(target, burn_step=None):
    now = time.time()
    dw = os.path.join(target, ".dreamwork")
    questions = read_text(os.path.join(dw, "questions.md"))
    q_open = parse_open_questions(questions)
    q_answered = parse_answered(questions)
    # #473: stamp updated_at per entry before the payload leaves. One call
    # over BOTH sections (open first — what he is looking at — then answered)
    # so the sig store sees them together. #534: this is load-bearing for the
    # silent algorithm re-seed — collect used to make two calls on one shared
    # store, and a re-seed in the first (open) would stamp the store's algo
    # current while the answered entries still held OLD-algo digests, so the
    # second call compared new digests against stale ones and fired a phantom
    # question-updated per answered entry. One call migrates both sections
    # atomically: the store is re-seeded or it is not, never half.
    track_question_updates(target, q_open + q_answered)
    answers = read_text(os.path.join(dw, "answers.md"))
    a_open = parse_open_answers(answers)
    a_answered = parse_answered_answers(answers)
    # #655 — the status section shows how many batched events are waiting for
    # the coordinator to drain (the count `journal_consume.py pending` prints).
    # Reused, not reimplemented: status_derive.pending_event_count calls the
    # SAME events_since_cursor projection the drain composes, so the count and
    # the drain agree by construction. Layered onto whatever status_from_store
    # returned (it may be a dict or None) so the journal count is independent
    # of the ledger-cutover gate that owns the `queue` field. The journal rides
    # the existing /mtime poll (watched_mtime walks it under .dreamwork/), so a
    # received event reaches an open dashboard on the next tick with no new
    # channel — the same move as queue depth and chats. The value is an int
    # when the journal was read and None when it exists and could NOT be —
    # the `push` fact's three-states-from-the-data rule, because a zero
    # standing in for "unreadable" is the reassuring answer given for the
    # alarming reason, and the panel is quiet at zero.
    _status = status_derive.status_from_store(
        dw, _safe_json(read_text(os.path.join(dw, "status.json"))))
    if isinstance(_status, dict):
        _status["pending_events"] = status_derive.pending_event_count(
            _journal_path(target))
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
        # #560: the store owns queue depth post-cutover (#362 measured the
        # hand claim drift to 115 vs 123 open; file-formats.md retires
        # `queue` once the cutover watermark lands). status_derive regenerates
        # the store-derivable fields from the ledger, degrading byte-for-byte
        # to the status.json claim pre-cutover / no store. The loop-claim
        # remainder (agents, push, deployed, prose) passes through untouched.
        # The existing /mtime->collect() poll invalidates it — the store
        # files live under .dreamwork/, which watched_mtime walks — so there
        # is no second cache mechanism. #655 layers pending_events (journal
        # receipts after the coordinator cursor) onto the same dict; see the
        # _status computation above.
        "status": _status,
        "git": git_tail(target),
        # which revision this process is running (#140), so a stale page
        # announces itself instead of being mistaken for a bug
        "deployed": serving_cached(target),
        # the ledger's own history as a time series (#142) — no new
        # instrumentation, because tasks.md is versioned and its ids are
        # permanent. burn_step (#487) forces granularity; None keeps auto.
        "burndown": ledger_stats(target, step=burn_step),
        "groups": group_progress(target), "goals": goal_tree_payload(target),
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
        "posture": resolve_posture(target), "settings": read_settings(target),
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
        # #504 — the topic-chat list (Q4): derived chat records from the
        # chats-v1 transcripts. Rides the /mtime poll (transcripts live under
        # .dreamwork/, which watched_mtime walks), so a sent chat reaches an
        # open dashboard on the next tick with no new channel. His words →
        # SUMMARY_DENIED (see summary()).
        "chats": list_chats(target),
    }


# --- #641 phase 1: derived key-level deltas over the existing /data.json ---
#
# The plan's `## The trap, named before the matrix` (line 123): a delta is a
# second description of state unless it is DERIVED from the one builder. So
# `compute_delta` compares two `collect()` outputs per top-level key by their
# SERIALIZED equality (never a second traversal), ships changed keys whole,
# and excludes `generated` from both comparison and the check hash (it
# changes every build and would force every response to differ).
#
# "Full is always the safe answer": any mismatch, any unexpected `since`, any
# doubt — the server sends the whole document. A wrong delta is worse than a
# large correct one. Version = `watched_mtime`, the same number the /mtime
# poll already gates on, so a delta computed against the right base is one a
# client can reconstruct.

_DELTA_EXCLUDE = frozenset(("generated",))


def data_json_version(target):
    """The version stamp a /data.json build is cached against: the
    `watched_mtime` it was built from. The client sends this back as `since`."""
    return watched_mtime(target)


def derived_check(doc):
    """A stable hash of a `collect()` document with `generated` excluded, so
    a client can self-check that a delta reconstructed to the same state. The
    hash is of the sorted-key serialised form, so key order does not matter."""
    core = {k: doc[k] for k in doc if k not in _DELTA_EXCLUDE}
    return hashlib.sha256(
        json.dumps(core, sort_keys=True, default=str).encode()).hexdigest()


def compute_delta(prev, nxt):
    """Derived per-key delta between two `collect()` outputs.

    Returns a dict shaped `{changed: {k: whole-new-value}, removed: [k, ...]}`,
    with `generated` excluded from comparison. No subsystem states "what
    changed" by hand — both arguments are the one builder's output, compared
    by serialized equality of each top-level value. `apply_delta(prev, this)`
    reconstructs the same JSON value as `nxt`, ignoring object-member order
    and excluding `generated`; that field remains the value carried by the
    base document. That semantic round-trip is the born-red test."""
    keys = set(prev) | set(nxt)
    changed, removed = {}, []
    for k in keys:
        if k in _DELTA_EXCLUDE:
            continue
        if k not in nxt:
            removed.append(k)
        elif k not in prev or json.dumps(prev[k], sort_keys=True,
                                         default=str) != json.dumps(
                nxt[k], sort_keys=True, default=str):
            changed[k] = nxt[k]
    return {"changed": changed, "removed": sorted(removed)}


def apply_delta(base, delta):
    """Apply a `compute_delta` payload to `base`, returning the reconstructed
    document. Deletes removed keys, overwrites changed keys whole, leaves
    everything else untouched. `generated` is carried from `base`."""
    out = dict(base)
    for k in delta.get("removed", []):
        out.pop(k, None)
    out.update(delta.get("changed", {}))
    return out


# Last-built document cache keyed by (target, burn_step): (version, doc,
# prev_version, prev_doc). One build per real change instead of one per window
# per tick; the previous build is kept so a client one version behind gets a
# real delta. BURN_STEPS is a closed set of 5, so the cache is bounded.
_DATA_JSON_CACHE = {}


def _data_json_cached(target, burn_step, since=None):
    """Return ``(version, doc, prev_version, prev_doc)`` for this burn_step,
    building fresh for a full request or when watched_mtime moved. The previous
    build is kept so `?since=<prev_version>` yields a delta rather than a full
    doc. A request without `since` is the recovery path, so it never trusts the
    mtime-keyed cache: the mtime can alias two different file contents."""
    key = (target, burn_step)
    version = watched_mtime(target)
    entry = _DATA_JSON_CACHE.get(key)
    if since is None or entry is None or entry[0] != version:
        doc = collect(target, burn_step=burn_step)
        prev = (entry[0], entry[1]) if entry else (None, None)
        entry = (version, doc, prev[0], prev[1])
        _DATA_JSON_CACHE[key] = entry
    return entry


def _data_json_response(entry, since):
    """Full document vs delta vs 304-shaped 'no change', per the plan's table:
    since==current version → unchanged sentinel; since==prev_version → delta;
    anything else (or no since) → full. Full is always the safe answer."""
    version, doc, prev_version, prev_doc = entry
    if since is None or since != repr(version) and (
            prev_version is None or since != repr(prev_version)):
        return doc
    if since == repr(version):
        # #136: "no change" is a distinct sentinel, never the full document.
        return {"v": repr(version), "unchanged": True}
    delta = compute_delta(prev_doc, doc)
    return {"v": repr(version), "base": since,
            "changed": delta["changed"], "removed": delta["removed"],
            "check": derived_check(doc)}


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
    "chats",             # #504 topic-chat transcripts — his words + the
    "groups", "goals", "settings",  # replies/group prose; local preference metadata
})                       #   descriptions — authored prose, plus member ids


def _summary_posture(v):
    # The enum/int axes + delivery (#342) + orchestration (#510);
    # delegation_label is display chrome and never rides out unreviewed.
    # delivery and orchestration are real posture an external consumer needs
    # to route on, not chrome.
    #
    # `subagent_policy` (#650) is DELIBERATELY not here. It is his authored
    # prose, which is the SUMMARY_DENIED class (dreams, chats — "his words"),
    # and it names his local tooling. An external consumer routes on the
    # axes; it has no business reading the policy. The decision is recorded
    # rather than defaulted, per SUMMARY_ALLOWED's own rule.
    return {k: v.get(k) for k in
            ("pace", "asking", "delegation", "delivery", "orchestration",
             "source")}


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

# #620 — sqlite's shared-memory index is not content, and it was the noisiest
# file in the watched tree by a wide margin.
#
# MEASURED ON THE LIVE TREE (read-only stat walk, 15 samples at 2 s, no writes
# by the measuring process): `watched_mtime` changed on 15 of 15 samples, and
# `.dreamwork/ledger.sqlite3-shm` HELD THE MAXIMUM MTIME in 14 of them. With
# this exclusion in place the same 15 samples changed once — on `handoffs.md`,
# a real edit. Over a separate 40 s live window `-shm` moved on 20 of 20 two-
# second samples while `-wal` moved 4 times and the db file 4 times, so `-shm`
# was moving roughly five times more often than the store was changing.
#
# WHY THAT MATTERS RATHER THAN BEING COSMETIC: the client polls `/mtime` every
# 2 s and refetches `/data.json` — 917 KB, uncompressed, ~200 ms of `collect()`
# — whenever the number moves. Serving that read touches `-shm`, which moves
# the number, which schedules the next refetch. The gate that exists to make
# the poll cheap was holding itself open, per window, forever.
#
# `-wal` IS DELIBERATELY NOT HERE, and this is the half that must not be
# "widened to be safe". Measured both directions on a real store: a write
# moves `-wal` every time, and with `-shm` alone excluded a write still
# advances `watched_mtime`; with `-wal` ALSO excluded a write no longer
# advances it at all. That failure is silent and in the dangerous direction —
# the dashboard would simply stop noticing real changes with nothing going
# red. `-wal` is the write signal; `-shm` is the read's bookkeeping.
#
# A SUFFIX, NOT THE TWO NAMES the #614 plan proposed (`ledger.sqlite3-shm`,
# `user-events.sqlite3-shm`). The rule being expressed is "a sqlite shared-
# memory index is not content", which is true of every store, and
# `.dreamwork/` is already scheduled to gain a third (`session-index.sqlite3`,
# the session-log plan). A two-name list reintroduces this exact defect
# silently the day that lands. `-shm` is a name sqlite reserves; nothing that
# is really content ends in it.
#
# It filters `kept`, so it leaves the LISTING FINGERPRINT as well as the mtime
# max — that is a second arm of the same defect, not a bonus: sqlite creates
# and deletes the sidecars around the open/close of a single read, and with
# no other process holding the store that churn moved the fingerprint on its
# own (measured: 1 of 8 read-only polls before, 0 of 8 after).
WATCHED_MTIME_IGNORED_SUFFIXES = ("-shm",)


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
        kept = sorted(f for f in files
                      if f not in WATCHED_MTIME_IGNORED
                      and not f.endswith(WATCHED_MTIME_IGNORED_SUFFIXES))
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
        elif k == "orchestration" and v in lint.POSTURE_STOPS_ORCHESTRATION:
            out["orchestration"] = v
        elif k == "delegation":
            try:
                n = int(v)
            except ValueError:
                continue
            if n >= 0:
                out["delegation"] = n
    return out


def read_posture_file(target):
    """Axes present and valid in `.dreamwork/posture`, or {} if absent.

    Read through `read_text_full` (#659) — not because `read_text` truncates
    (since #632 it does not) but because this is the reader the NEXT control
    reader gets copied from, and what a copy carries is the name. These axes
    feed a read-modify-write: POST /posture carries delivery and orchestration
    forward out of `resolve_posture`, and `write_posture` rebuilds the whole
    file, so an axis the read did not recover is an axis the next chip press
    erases. `read_text_full` states that requirement in the line a reviewer
    reads, so a re-bound has to contradict it out loud instead of arriving as
    a changed default. `read_subagent_policy` is the sibling and says the same.
    """
    raw = read_text_full(os.path.join(target, ".dreamwork", "posture"))
    if raw is None:
        return {}
    return parse_posture_text(raw)


def read_posture_agreement(target):
    """Observe whether the readable file agrees with append-only history."""
    from dreamwork_db import Access, open_database
    from dreamwork_db.posture import resolve_posture_agreement
    from dreamwork_db.tasks import task_store_spec

    axes = tuple(_posture_vocab().POSTURE_AXES)
    path = os.path.join(target, ".dreamwork", "posture")
    try:
        with open(path, encoding="utf-8") as posture_file:
            file_posture = parse_posture_text(posture_file.read())
        file_error = None
    except OSError as exc:
        file_posture = None
        file_error = f"posture file unavailable: {one_line(str(exc))}"
    except UnicodeDecodeError as exc:
        # `UnicodeDecodeError` is a ValueError, NOT an OSError, so the clause
        # above never caught it and the exception escaped `resolve_posture`
        # entirely — taking every axis down over one unreadable file, when the
        # sibling reader `read_posture_file` tolerates the same bytes through
        # `read_text_full`. Undecodable is reported SEPARATELY from unavailable
        # because the file is present and its bytes are intact; saying
        # "unavailable" would send a reader looking for a missing file (#140).
        file_posture = None
        file_error = f"posture file undecodable: {one_line(str(exc))}"

    db_path = store_path(os.path.join(target, ".dreamwork"))
    if not db_path.exists():
        return resolve_posture_agreement(
            file_posture, {}, axes, file_error=file_error
        )
    try:
        with open_database(
                task_store_spec(db_path), access=Access.READ) as store:
            return store.posture.agreement(
                file_posture, axes, file_error=file_error
            )
    except Exception as exc:
        return resolve_posture_agreement(
            file_posture, {}, axes,
            file_error=file_error,
            history_error=f"posture history unavailable: {one_line(str(exc))}",
        )


def read_subagent_policy(target):
    """The free-text subagent policy override (#650), or None if unset.

    The whole file IS the value: nothing is parsed, escaped, normalised or
    re-wrapped, so the text round-trips byte for byte. Read through
    `read_text_full`, NOT `read_text` — this is a durable value that a control
    writes back, and `read_text` is the display-shaped name that still takes a
    `limit`, so only the named-whole reader makes a re-bound here contradict
    its own call site (#632, the defect that deleted 12 answered questions;
    #659, which is why `read_posture_file` now reads the same way).

    A present-but-blank file reads as unset, so the standing default stands
    and "no policy" is expressed by deleting the file rather than by an empty
    one that looks set. lint (`check_subagent_policy`) is what says aloud
    that such a file is inert — the same division of labour posture keeps,
    where the parser drops and lint is the loud layer.
    """
    lint = _posture_vocab()
    raw = read_text_full(
        os.path.join(target, ".dreamwork", lint.SUBAGENT_POLICY_FILE))
    if raw is None or not raw.strip():
        return None
    return raw


def resolve_posture(target):
    """Effective posture for the dashboard and collect().

    Absent file → derived from run-mode (lint.derive_posture). Present file
    overlays any valid axes on that derivation. Always returns pace, asking,
    delegation, source ('derived'|'file'), and delegation_label for display.

    #650: the datatype also carries `subagent_policy` (free text) and its own
    `subagent_policy_source`. That source is SEPARATE from `source` on
    purpose — `source` says where the AXES came from, and a policy override
    must not make the axes claim to be file-set when they are still derived.
    The policy is a third file merged here, which is the shape this function
    already had: it has always merged `run-mode` with `posture`.
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
        "orchestration": file_vals.get("orchestration", ORCHESTRATION_DEFAULT),
        "source": "derived",
    }
    if file_vals:
        out["source"] = "file"
        for k in ("pace", "asking", "delegation"):
            if k in file_vals:
                out[k] = file_vals[k]
    out["delegation_label"] = lint.delegation_posture(int(out["delegation"]))
    policy = read_subagent_policy(target)
    out["subagent_policy"] = (lint.SUBAGENT_POLICY_DEFAULT if policy is None
                              else policy)
    out["subagent_policy_source"] = "default" if policy is None else "file"
    out["agreement"] = read_posture_agreement(target)
    return out


_CHAT_BODY_MARKER_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<slashes>\\*)"
    r"(?P<marker><!--\s*(?:dw-turn\b[^\r\n]*|/dw-turn\s*)-->)"
    r"(?P<trail>[ \t]*)(?P<cr>\r?)$", re.MULTILINE)


def _chat_turn_text(text, *, encode):
    """Escape structural-looking lines reversibly; preserve everything else."""
    def replace(match):
        slashes = match.group("slashes")
        slashes = ("\\" + slashes) if encode else slashes[1:]
        return (match.group("indent") + slashes + match.group("marker") +
                match.group("trail") + match.group("cr"))

    if encode:
        return _CHAT_BODY_MARKER_RE.sub(replace, text or "")
    return _CHAT_BODY_MARKER_RE.sub(
        lambda m: replace(m) if m.group("slashes") else m.group(0), text or "")


def write_posture(target, pace, asking, delegation, delivery=None,
                  orchestration=None):
    """Persist a posture override. Returns False if refused.

    Writes the three required axes always; writes delivery / orchestration
    only when passed (None → omitted, so absent reads as the default — a
    caller with no opinion on either gets today's three-line file). A caller
    that sets one passes it through and the extra line lands."""
    lint = _posture_vocab()
    if pace not in lint.POSTURE_STOPS_PACE:
        return False
    if asking not in lint.POSTURE_STOPS_ASKING:
        return False
    if delivery is not None and delivery not in lint.POSTURE_STOPS_DELIVERY:
        return False
    if (orchestration is not None
            and orchestration not in lint.POSTURE_STOPS_ORCHESTRATION):
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
    if orchestration is not None:
        lines.append(f"orchestration: {orchestration}")
    body = "\n".join(lines) + "\n"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        atomic_write_text(path, body)
        return True
    except OSError:
        return False


def read_settings(target):
    """Return registry metadata plus effective values for the local user."""
    import settings as user_settings
    values = user_settings.defaults()
    dw = os.path.join(target, ".dreamwork")
    available = source_of_truth(dw) == "store"
    error = None if available else "settings require the ledger store"
    if available:
        try:
            from dreamwork_db import Access, open_database
            from dreamwork_db.tasks import task_store_spec
            with open_database(
                    task_store_spec(store_path(dw)), access=Access.READ) as db:
                values = db.settings.effective(user_settings.LOCAL_USER_ID)
        except Exception as exc:
            # Invalid persisted data must not masquerade as defaults. Keep the
            # page renderable, but carry a loud fault and disable writes.
            available = False
            error = str(exc)
    return {
        "userid": user_settings.LOCAL_USER_ID,
        "available": available,
        "error": error,
        "values": values,
        "registry": user_settings.public_registry(),
    }


def read_settings_batch(target, keys):
    """Return one HTTP-ready, registry-validated settings subset."""
    from dreamwork_db import Access, NotFound, ValidationError, open_database
    from dreamwork_db.settings import BatchSettingValidationError
    from dreamwork_db.tasks import task_store_spec
    dw = os.path.join(target, ".dreamwork")
    if source_of_truth(dw) != "store":
        error = "settings require the ledger store"
        return {"ok": False, "errors": {"$batch": error}}, 400
    try:
        with open_database(
                task_store_spec(store_path(dw)), access=Access.READ) as db:
            values = db.settings.get_many(keys)
    except BatchSettingValidationError as exc:
        return {"ok": False, "errors": exc.errors}, 400
    except ValidationError as exc:
        return {"ok": False, "errors": {"$batch": str(exc)}}, 400
    return {"ok": True, "values": values}, 200


def write_subagent_policy(target, text):
    """Persist a subagent-policy override (#650). False if refused.

    Writes `text` VERBATIM — no trailing-newline normalisation, no escaping,
    no re-wrapping. The value IS the file, so a writer that tidied it would
    make the stored policy differ from the policy that was set, and the
    round-trip this field's whole design buys would be gone.

    It cannot disturb the posture axes and `write_posture` cannot disturb it:
    they are different files. That is the property that made the sibling the
    right home — `write_posture` is a whole-file overwrite fired by every
    chip press, and a policy sharing that file would be erased by any writer
    that had not been taught to carry it through.

    Refuses a blank write: an empty file is inert, so a caller that means "no
    policy" must delete the file rather than leave one that looks set.
    """
    if not isinstance(text, str) or not text.strip():
        return False
    lint = _posture_vocab()
    path = os.path.join(target, ".dreamwork", lint.SUBAGENT_POLICY_FILE)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        atomic_write_text(path, text)
        return True
    except OSError:
        return False


def delete_subagent_policy(target):
    """Remove the subagent-policy override, returning to the standing default.

    Reset (#646): 'no policy' is expressed by deleting the file, NOT by clearing
    it to empty — the read side (read_subagent_policy) treats a present-but-blank
    file as unset AND lint (check_subagent_policy) warns that such a file is
    inert, so clear-to-empty would leave a file that looks set and is not. This
    is the one supported reset (#440): match the read side's decision rather
    than invent a second.

    Returns True when the override was present and removed; False when it was
    already absent (nothing to reset — the standing default is already in
    effect); None when deletion failed. Absence is idempotent, but an unlink
    failure must stay distinct so the route cannot report a successful reset
    while the override remains on disk.
    """
    lint = _posture_vocab()
    path = os.path.join(target, ".dreamwork", lint.SUBAGENT_POLICY_FILE)
    try:
        os.unlink(path)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return None


def posture_line(pace, asking, delegation, orchestration, source=""):
    """Source-tagged watch-events.log line for a committed posture change.

    Carries the posture POINT — pace / asking / delegation / orchestration —
    the axes without a separate consumer line. Delivery has its own
    `delivery via watch` line (it drives wake routing); orchestration rides
    here because it has no consumer yet. Pure; one_line on each free field so
    nothing forges a second event.
    """
    return (
        f"posture via watch{from_hint(source)}: "
        f"pace={one_line(str(pace))} "
        f"asking={one_line(str(asking))} "
        f"delegation={one_line(str(delegation))}"
        f" orchestration={one_line(str(orchestration))}"
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
# #510 — the orchestration posture axis (hands-on|orchestrator). Absent =
# hands-on, so the default is today's behaviour (the coordinator implements
# inline). The axis is inert until a consumer reads it; it rides the
# `posture via watch` line, not its own.
ORCHESTRATION_DEFAULT = "hands-on"


def delivery_line(mode, source=""):
    """Source-tagged watch-events.log line for a committed delivery change.

    Pure; one_line on the mode so nothing forges a second event. The ceremony
    posture/run-mode already use (dual-write + one line on real change), not a
    second one."""
    return f"delivery via watch{from_hint(source)}: {one_line(str(mode))}"


def subagent_policy_line(action, source="", policy=None):
    """Source-tagged watch-events.log line for a committed policy change (#646).

    The authoritative file remains byte-exact. On `set`, its complete content
    is copied into the line as a JSON string: leading/trailing whitespace and
    non-ASCII stay faithful, while control characters are escaped so one
    policy change remains one physical log event. Reset has no policy value.
    """
    line = f"subagent policy via watch{from_hint(source)}: {one_line(str(action))}"
    if action == "set":
        line += " " + json.dumps(policy or "", ensure_ascii=False)
    return line


# #342 — per-kind wake routing. The receipt commits UNCONDITIONALLY in do_POST
# (the E3 invariant); these decide only whether the watch-events.log wake line
# — the *interrupt* — fires on top. chat/do-now/do-next pre-empt even in batched
# mode (a do-now that does not pre-empt is a do-now that lied — his Q2 ruling);
# every other command kind (add-idea, maintenance, plugin kinds) and the
# /answer, /comment, /ask routes wake only in instant mode, riding the durable
# receipt and the tick's cursor read otherwise. Withholding the wake line IS
# batching.
PREEMPT_KINDS = ("chat", "do-now", "do-next")


def delivery_mode(target):
    """Effective delivery posture: 'instant' (default) or 'batched' (#342).

    Per-tick re-read of `.dreamwork/posture` via read_posture_file — the same
    contract pace/asking/delegation use, so an on-disk change reaches a
    running loop without restart. Absent axis → instant (today's behaviour)."""
    return read_posture_file(target).get("delivery", DELIVERY_DEFAULT)


# #864 — the EXPEDITED class's gate. One line `on` in `.dreamwork/expedite`;
# ABSENT MEANS OFF (the watch-tint/run-mode family, SKILL.md Guardrails).
# Machine-local and gitignored on purpose, deliberately against that
# convention's word "tracked": the stop hook this gates is installed into
# `.claude/settings.json`, which is itself gitignored and per-checkout, so a
# travelling gate would strip `do next` of its wake on a machine where nothing
# delivers it at a pause. `dev/expedite_hook.py install` writes both together.
EXPEDITE_ON = "on"


def expedite_enabled(target):
    """Is the EXPEDITED delivery class enabled on this checkout? (#864)

    Per-tick re-read of `.dreamwork/expedite` — the same on-disk contract
    run-mode and posture use, so enabling it reaches a running loop without a
    restart. Absent, empty, or anything but the single legal value `on` reads
    as OFF: a gate must fail to the state that changes nothing, and `lint.py`
    is what says an unknown value loudly rather than this guessing silently.
    """
    return (read_text(os.path.join(target, ".dreamwork", "expedite")) or
            "").strip() == EXPEDITE_ON


def emits_wake(kind, target):
    """Per-kind wake routing (#342): does this kind fire the wake line?

    Pre-empt kinds (chat/do-now/do-next) wake regardless of mode; every other kind
    — add-idea, maintenance, plugin kinds — and the /answer, /comment, /ask
    ROUTES (passed as their path string, which is never a pre-empt kind) wake
    only in instant mode. The receipt always commits in do_POST; this is the
    interrupt half only. Pure in `kind`; reads delivery posture from disk.

    #864 adds the third class ABOVE that table: an EXPEDITED kind never fires
    the wake line in ANY mode — his words, "it doesn't interrupt the agent,
    just gets delivered early if it's possible to do so". The stop hook
    delivers it at the next natural pause; the tick's drain delivers it if the
    hook never fires, so withholding the wake costs nothing. Gated, so a
    checkout with no hook installed keeps today's pre-emption instead of losing
    the promptness with nothing to replace it."""
    if kind in EXPEDITE_KINDS and expedite_enabled(target):
        return False
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
# top of file). Each becomes a journal entry and a source-tagged
# watch-events.log wake line for the loop's tail monitor.
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


def command_line(kind, text, source="", receipt_id=None):
    """Source-tagged watch-events.log line for a human-submitted command.

    Pure; testable. do-next may carry no text (it just nudges selection).
    The receipt id is appended as a suffix (#527 — F1 of the #519
    exactly-once audit) so the coordinator can match a drained receipt to
    a wake-line it already acted on; absent when the journal is off (the
    legacy E2 baseline that commits no receipt)."""
    body = f": {one_line(text)}" if text else ""
    suffix = f" [receipt {receipt_id}]" if receipt_id else ""
    return f"command via watch{from_hint(source)}: {kind}{body}{suffix}"


# ── #843: ingest-plan — file a plan's tasks into the ledger from a path ──────
# The server runs on the machine where his plans live, so it reads the file
# itself; a content-paste would defeat the point of "paste a path". That makes
# this a route that reads an arbitrary local file, which is why every function
# below is pure and confinement is a named refusal, not a string check.
#
# CONFINEMENT (option 1 of the brief): a small set of allowed roots. A path is
# resolved with os.path.realpath — which resolves BOTH `..` components AND
# symlinks — and the RESOLVED result is checked against the root. Checking the
# raw string first would let `../` and an in-root symlink pointing out walk
# straight out. This is the OPPOSITE of #425's `abspath`-not-`realpath` rule:
# #425 preserves the symlink's directory so __file__ keeps resolving to the
# repo root after watch.py becomes a link; here the goal is CONTAINMENT, so the
# symlink MUST be resolved (see .dreamwork/docs/migrate-watch-symlink.md:66-76
# for why the two differ). Do not blanket-copy abspath into a containment check.
INGEST_PLAN_ROOTS = (
    os.path.expanduser("~/.claude-p/plans"),
)


def resolve_ingest_path(raw_path):
    """Resolve a plan path and confine it to an allowed root.

    Returns ``(resolved_path, None)`` when the path is inside an allowed root,
    or ``(None, message)`` when it escapes. ``realpath`` resolves symlinks and
    ``..`` together, so a symlink inside the root pointing out is caught by the
    resolved target sitting outside — the string alone never reaches the check.
    """
    resolved = os.path.realpath(os.path.expanduser(raw_path))
    for root in INGEST_PLAN_ROOTS:
        root_r = os.path.realpath(root)
        if resolved == root_r or resolved.startswith(root_r + os.sep):
            return resolved, None
    return None, ("%s is not under an allowed ingest root "
                  "(one of %s)" % (raw_path, ", ".join(INGEST_PLAN_ROOTS)))


# The shape to parse: a "## Tasks for ingestion" heading followed by a markdown
# table whose columns include Title (and optionally type / pri). The worked
# example (delightful-munching-barto.md) carries `# | Title | type | pri |
# blocked on`; v1 reads Title/type/pri and drops the blocked-on column — flat
# filing, because #841 is rebuilding the group schema and #842 will re-ingest
# into it, so grouping now is work that gets redone next week.
_INGEST_HEADING = "## Tasks for ingestion"


def parse_ingestion_table(text):
    """Parse a plan's ``## Tasks for ingestion`` table.

    Returns ``(rows, None)`` on success, or ``([], message)`` when the plan has
    no such heading or no table under it — a command that silently files zero
    tasks is worse than one that says so. Each row is ``{title, type, priority}``
    with ``type``/``priority`` defaulting to ``None`` when the column is absent.
    The Title cell keeps its backticks stripped; the rest of the row's columns
    are dropped for v1 (#842 ingests the blocked-on hierarchy).
    """
    lines = text.split("\n")
    # Find the heading (any ## level, so a plan nested under a deeper heading
    # still works). Everything before it is preamble.
    head_idx = None
    for i, ln in enumerate(lines):
        if ln.strip() == _INGEST_HEADING or ln.strip().startswith(
                _INGEST_HEADING + " "):
            head_idx = i
            break
    if head_idx is None:
        return [], ("this plan has no '%s' section — nothing to file"
                    % _INGEST_HEADING)
    # The first pipe-table after the heading is the ingestion table. A prose
    # paragraph between heading and table is allowed (the example carries one
    # naming the priority bands); a sub-heading ends the search.
    table_start = None
    for j in range(head_idx + 1, len(lines)):
        s = lines[j].strip()
        if s.startswith("|") and s.endswith("|"):
            table_start = j
            break
        if s.startswith("## "):
            break
    if table_start is None:
        return [], ("'%s' has no markdown table under it — nothing to file"
                    % _INGEST_HEADING)
    # Skip the header row and its separator (---). Collect data rows until a
    # non-pipe line or EOF.
    rows = []
    for k in range(table_start + 2, len(lines)):
        s = lines[k].strip()
        if not (s.startswith("|") and s.endswith("|")):
            break
        cells = [c.strip() for c in s.strip("|").split("|")]
        rows.append(_ingest_row(cells))
    if not rows:
        return [], ("'%s' table is empty — nothing to file"
                    % _INGEST_HEADING)
    return rows, None


def _ingest_row(cells):
    """Build one filing dict from a table row's cells.

    Column 0 is the row id (#); column 1 is the Title; columns 2 and 3 are type
    and pri when present. A plan with fewer columns still files (Title is the
    only required cell); more columns are ignored. Backticks wrapping a Title
    are stripped so the ledger entry is not a code span.
    """
    title = cells[1].strip("`").strip() if len(cells) > 1 else ""
    type_ = cells[2].strip() if len(cells) > 2 and cells[2].strip() else None
    pri = cells[3].strip() if len(cells) > 3 and cells[3].strip() else None
    return {"title": title, "type": type_, "priority": pri}


# Regex for the filed-id both modes print: markdown 'filed #N into <path>',
# store 'filed #N (store)'. One reader, so a cutover changes nothing here.
_FILED_ID = re.compile(r"filed #(\d+)")


def file_ingested_tasks(target, tasks):
    """File parsed plan tasks into the target's ledger via the ONE writer.

    Subprocesses ``dev/ledger.py file`` (NOT an import — importing ledger.py
    into watch.py builds a second ``watch`` module object, the documented
    #425/#397 hazard). ``--ledger <target>/.dreamwork/tasks.md`` lands in the
    target's store (dw_dir is the ledger's parent, so source_of_truth routes
    markdown vs store correctly). Returns ``(count, ids)``; a task whose filing
    exits non-zero stops the run and the count reflects what landed before it.
    """
    ledger = os.path.join(target, ".dreamwork", "tasks.md")
    ledger_py = os.path.join(SELF_DIR, "dev", "ledger.py")
    ids = []
    for t in tasks:
        argv = [sys.executable, ledger_py, "file", t["title"],
                "--ledger", ledger, "--origin", "human"]
        if t.get("type"):
            argv += ["--type", t["type"]]
        if t.get("priority"):
            argv += ["--priority", t["priority"]]
        res = subprocess.run(argv, capture_output=True, timeout=20)
        if res.returncode != 0:
            break
        m = _FILED_ID.search(res.stdout.decode("utf-8", "replace"))
        ids.append(int(m.group(1)) if m else -1)
    return len(ids), ids


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

        def send_error(self, code, message=None, explain=None):
            """404 wears the design system; every other code keeps the stock
            body (#598).

            AT THIS SEAM, NOT AT A ROUTE, because a 404 leaves this server from
            seven places — the unmatched-path fall-through in `do_GET`, the
            unknown-path one in `do_POST`, /filedata, /chatdata, /reviewraw,
            /researchraw, and `_send_bytes` for /filebytes — and every one of
            them was serving the stock page. Fixing the fall-through alone
            leaves the audit's finding true on six routes, and an allowlist of
            "the ones a human can see" is a list that rots the next time an
            endpoint is added. One seam has no list.

            404 IS THE ONE CODE SCOPED IN, because it is the only error a
            READER arrives at: a typo, a stale bookmark, an artifact rebuilt
            out from under an open tab. The rest are deliberately left alone.
            421/403 are `_preflight` refusing a caller who is not the reader at
            all (a rebinding probe, a foreign origin) — dressing a refusal in
            the reader's ~118KB stylesheet spends the design system on someone
            it is not for and turns every rejected probe into a ~260x
            amplification of the stock 455 bytes. Every 5xx here is raised
            inside a `do_POST` handler, so none is reachable by typing a URL.

            THE STATUS LINE IS UNTOUCHED: this replaces the BODY of a 404, not
            the code. A styled page served 200 would lie to every tool that
            reads status codes, this server's own guards included. Everything
            else follows the stdlib's `send_error` exactly — `Connection:
            close` (which is also what sets `close_connection`), an explicit
            Content-Length, and no body on a HEAD."""
            if code != 404:
                super().send_error(code, message, explain)
                return
            body = NOT_FOUND_PAGE.encode("utf-8")
            self.send_response(code, message)
            self.send_header("Connection", "close")
            self.send_header("Content-Type", self.error_content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

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

        def _replay_verdict(self, result):
            """#274: a dedup-hit replay or conflict returns the ORIGINAL
            receipt's verdict without re-applying.

            The journal deduped the receipt (one row per client_action_id), so
            `receive()` hands back the original on a second same-UUID POST. But
            the receipt→application join used to dispatch the handler again
            regardless, and a second Answer bullet / question / comment landed
            byte-identical beside the first — durable, and invisible for hours.
            The original receipt is authoritative: a replay that found
            `received` already APPLIED once (ok — the answer folded on the
            first insert), one that found `rejected` already REFUSED once
            (rejected — the draft stays, as it did on the first refusal).

            `_send_receipt` merges the ORIGINAL receipt identity (id/sequence/
            digest) into the 202 + Location, so a replaying client sees a
            consistent verdict and clears its draft only when the original was
            durable. The precise rejection `reason` is not re-derived here (it
            would need a transition read in sqlite.py, outside this lane): a
            replayed rejection keeps the draft either way, and only the error
            copy is generic."""
            if result.state == "rejected":
                body = {"ok": False, "rejected": True}
            else:
                body = {"ok": True}
            self._send_receipt(json.dumps(body), "application/json")

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

        def _send(self, body, ctype, status=200, headers=None):
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(data)

        def _refuse_lossy(self, target, route, path, line):
            """A write that would have LOST a line was refused (#632).

            This is a backstop that should never fire: with the whole-file read
            in place there is no known way to reach it. It exists because the
            thing it guards against was silent for an unknown length of time
            and cost twelve of his answered entries, and the second occurrence
            of a failure is the repo's own signal to write the check rather
            than patch the instance (#509 was the first).

            It SHOUTS on the way out. `log_event` puts it on the dashboard's
            own event stream, so a refusal is visible where he already looks
            rather than only in a response body he may never see — the one
            property #632 lacked entirely.
            """
            log_event(target,
                      f"REFUSED a lossy rewrite of {os.path.basename(path)} "
                      f"via {route}: it would have dropped "
                      f'"{one_line(line)[:90]}". His words are safe in '
                      f".dreamwork/submissions.log — fold them by hand.")
            self.send_error(500, "lossy rewrite refused",
                            f"the write would have dropped: "
                            f"{one_line(line)[:200]}")

        def _reject(self, reason_code, detail=None, extra=None):
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
            if extra:
                body.update(extra)
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
            # #562: /chat/<id> is a same-document route too — the id is a path
            # segment, so it is matched by prefix rather than the fixed set.
            if (parsed.path in ("/", "/questions", "/answers", "/settings", "/file",
                               "/review", "/question", "/research",
                               "/reviews", "/tasks", "/tasks2", "/goals")
                    or parsed.path == "/chat"
                    or parsed.path.startswith("/chat/")):
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
                # #641 phase 1: GET /data.json?since=<v> returns a derived
                # delta against the last full build at that version, or the
                # full document for any mismatch (full is always the safe
                # answer). A client that never sends `since` sees this route
                # byte-identical to today.
                since = (qs.get("since") or [None])[0]
                doc_entry = _data_json_cached(target, burn_step, since)
                payload = _data_json_response(doc_entry, since)
                self._send(json.dumps(payload), "application/json")
            elif parsed.path == "/summary.json":
                # Q5: a whitelist view of collect() (summary()), for any
                # non-loopback consumer. /data.json serves full documents and
                # parsed entries; this serves only the counts, health and
                # operational metadata named in SUMMARY_ALLOWED. It does NOT
                # widen authority: it rides the same _preflight() gate as
                # every other GET, and where it may listen is a separate
                self._send(json.dumps(summary(target)), "application/json")
            elif parsed.path == "/tasksdata":
                self._send(json.dumps(tasks_response(target, parsed.query)),
                           "application/json")
            elif parsed.path == "/goalsdata":
                self._send(json.dumps(goal_tree_payload(target)),
                           "application/json")
            elif parsed.path == "/settingsdata":
                payload, status = read_settings_batch(
                    target, urllib.parse.parse_qs(parsed.query).get("key", []))
                self._send(json.dumps(payload), "application/json", status)
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
            elif parsed.path == "/chatdata":
                # #562 — the parsed transcript for one chat, for the /chat/<id>
                # page (the full turns are not in /data.json, only the derived
                # summaries). The id is validated as a safe path component
                # BEFORE it is joined onto _chat_root, so a hostile or typo'd
                # id is a 404, never a traversal. The derivation goes through
                # the SAME _chat_record_and_turns list_chats uses, so title /
                # status / unread can never disagree between the list and the
                # page; the page additionally gets the full parsed turns.
                cid = urllib.parse.parse_qs(parsed.query).get("id", [""])[0]
                if not _CHAT_ID_RE.match(cid):
                    self.send_error(404); return
                rec, turns = _chat_record_and_turns(
                    os.path.join(_chat_root(target), cid), cid)
                if not rec:
                    self.send_error(404); return
                payload = dict(rec)
                payload["entries"] = turns
                self._send(json.dumps(payload), "application/json")
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
                text, cut = ((read_text_bounded(full, 2_000_000))
                             if full else (None, False))
                if text is None:
                    self.send_error(404)
                    return
                if cut:
                    # #632: half an HTML document renders as a BROKEN page
                    # with nothing to say it was cut, which is the silent
                    # failure this whole change exists to remove. An error the
                    # reader can see beats a page that lies quietly.
                    self.send_error(500, "artifact too large",
                                    "the artifact exceeds the 2,000,000 "
                                    "character serving cap and would be "
                                    "served truncated")
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
                text, cut = ((read_text_bounded(full, 2_000_000))
                             if full else (None, False))
                if text is None:
                    self.send_error(404)
                    return
                if cut:
                    # #632: half an HTML document renders as a BROKEN page
                    # with nothing to say it was cut, which is the silent
                    # failure this whole change exists to remove. An error the
                    # reader can see beats a page that lies quietly.
                    self.send_error(500, "artifact too large",
                                    "the artifact exceeds the 2,000,000 "
                                    "character serving cap and would be "
                                    "served truncated")
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
            # #274: a dedup hit must not re-apply. The journal already deduped
            # the receipt (one row per client_action_id); without this seam a
            # replayed UUID still dispatched the handler and duplicated the
            # APPLICATION — a second byte-identical Answer bullet that stayed
            # invisible for two hours because nothing counts them per entry.
            # The original receipt is authoritative: short-circuit to its
            # verdict. This runs only when the journal committed (shadow on,
            # not truncated); the legacy no-journal path has no result and
            # falls through to the handler as before.
            result = self.journal_result()
            if result is not None and result.kind != "inserted":
                self._replay_verdict(result)
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
                # seed_missing: answers.md may legitimately not exist yet, and
                # append_human_question seeds the skeleton. #632's full read
                # and loss check still apply.
                status, value = rewrite_append_only(
                    path,
                    lambda text: (append_human_question(text, question, stamp),
                                  True),
                    seed_missing=True)
            if status == "lossy":
                self._refuse_lossy(target, "/ask", path, value); return
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
                # #632: the read is WHOLE and the write is loss-checked, both
                # inside rewrite_append_only. This used to read through the
                # bounded `read_text` and write the short result back over the
                # full file, which is what deleted twelve answered entries.
                # Atomic, like /ask thirty lines up (#370). Opening this path in
                # plain write mode empties the file before it writes, so a
                # failure between those two moments loses every question he ever
                # asked and every answer he ever gave. (Phrased without the
                # construct itself: the check for it greps the source, and an
                # explanation quoting what it forbids is a violation of it.)
                status, value = rewrite_append_only(
                    qpath,
                    lambda text: append_answer(text, title, answer, stamp))
            if status == "missing":
                self.send_error(404); return
            if status == "unmatched":
                self.send_error(409); return
            if status == "lossy":
                self._refuse_lossy(target, "/answer", qpath, value); return
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
                status, value = rewrite_append_only(   # #370 + #632, as above
                    qpath,
                    lambda text: append_comment(text, title, note, stamp,
                                                section))
            if status == "missing":
                self.send_error(404); return
            if status == "unmatched":
                self.send_error(409); return
            if status == "lossy":
                self._refuse_lossy(target, "/comment", qpath, value); return
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
            import ledger_write
            from dreamwork_db import Access, open_database
            from dreamwork_db.tasks import task_store_spec
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
            try:
                with open_database(
                        task_store_spec(store_path(dw)),
                        access=Access.WRITE) as store:
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
            # #342: /decide is a batched kind — wakes only in instant mode,
            # riding the durable receipt + the tick's cursor read otherwise
            # (same family as /answer and /comment; #514 F1).
            if emits_wake("/decide", target):
                log_event(target,
                          f'review-decision{from_hint(req.get("from"))}: '
                          f'"{one_line(artifact)}" {decision} for '
                          f'"{one_line(question_title)}" -> .dreamwork/ledger.sqlite3')
            self._send_receipt(json.dumps({"ok": True, "decision": decision}),
                               "application/json")

        def _handle_settings(self):
            """Atomically persist one or many settings through the canonical store."""
            import settings as user_settings
            from dreamwork_db import Access, Busy, ValidationError, open_database
            from dreamwork_db.settings import BatchSettingValidationError
            from dreamwork_db.tasks import task_store_spec
            req = self._read_json()
            if req is None:
                self._reject("malformed_json"); return
            if not isinstance(req, dict):
                self._reject("schema_invalid"); return
            if "values" in req:
                values = req["values"]
                if not isinstance(values, dict) or not values:
                    self._reject("schema_invalid"); return
            elif "key" in req and "value" in req and isinstance(req["key"], str):
                values = {req["key"]: req["value"]}
            else:
                self._reject("schema_invalid"); return
            dw = os.path.join(target, ".dreamwork")
            if source_of_truth(dw) != "store":
                self._reject("domain_invalid", detail="no_store"); return
            try:
                for attempt in range(2):
                    try:
                        with open_database(
                                task_store_spec(store_path(dw)),
                                access=Access.WRITE) as db:
                            with db.transaction():
                                changed = db.settings.set_many(
                                    values, user_settings.LOCAL_USER_ID)
                                result = db.settings.get_many(
                                    list(values), user_settings.LOCAL_USER_ID)
                        break
                    except Busy:
                        if attempt:
                            raise
                        time.sleep(0.1)
            except BatchSettingValidationError as exc:
                self._reject("domain_invalid", detail="invalid_settings",
                             extra={"errors": exc.errors}); return
            except ValidationError as exc:
                self._reject("domain_invalid", detail=str(exc)); return
            except Busy as exc:
                log_event(target, "SETTINGS STORE BUSY: " + one_line(str(exc)))
                self._send(json.dumps({
                    "ok": False, "retryable": True,
                    "reason": "settings_store_busy",
                    "detail": "the settings store is locked; retry the write",
                }), "application/json", status=503,
                    headers={"Retry-After": "1"})
                return
            except Exception as exc:
                log_event(
                    target,
                    "SETTINGS WRITE FAILED: " + type(exc).__name__ + ": "
                    + one_line(str(exc)),
                )
                self.send_error(500, "settings write failed; see dashboard event log")
                return
            if changed:
                log_event(target, f'settings via watch: "{one_line(", ".join(changed))}" '
                          '-> .dreamwork/ledger.sqlite3')
            self._send_receipt(json.dumps({
                "ok": True, "changed": changed, "values": result,
            }), "application/json")

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
            # #527: the wake-line carries the receipt id the SAME POST
            # committed (journal_result, available because do_POST commits
            # before dispatch) so the coordinator can match a drained receipt
            # to a wake it already acted on — the join F1 found missing.
            if emits_wake(kind, target):
                result = self.journal_result()
                rid = result.receipt_id if result else None
                log_event(target, command_line(kind, text, req.get("from"), rid))
            # #504: a `chat` send's application step — write the human turn to
            # the chats-v1 transcript (conversational truth; the receipt is the
            # durable home, already committed in do_POST). The receipt id is the
            # chat identity. Runs once per receipt: #274's replay verdict
            # short-circuits a dedup hit before this handler, so a
            # double-click/retry never double-writes the turn. Best-effort —
            # the receipt committed, so an IO failure never refuses the 202.
            if kind == "chat":
                result = self.journal_result()
                cid = (result.receipt_id if result and result.receipt_id
                       else str(uuid.uuid4()))
                apply_chat_turn(target, cid, "human", text, receipt_id=cid)
            # #843 — ingest-plan: the text field is a filesystem path. The
            # server reads it (this machine is where his plans live) under
            # confinement, parses the "## Tasks for ingestion" table, and files
            # each row flat into the ledger via the ONE writer (dev/ledger.py).
            # The receipt already committed, so an IO failure is a loud refusal,
            # not a silent no-op. v1 is flat filing — #841 is rebuilding the
            # group schema and #842 re-ingests into it.
            if kind == "ingest-plan":
                self._apply_ingest_plan(target, text, req); return
            self._send_receipt(json.dumps({"ok": True}), "application/json")

        def _apply_ingest_plan(self, target, path, req):
            """#843 — read a plan, parse its table, file the rows. Refuses loudly."""
            resolved, err = resolve_ingest_path(path)
            if err is not None:
                self._reject("domain_invalid", detail="path_not_confined"); return
            try:
                with open(resolved, "r", encoding="utf-8") as f:
                    plan = f.read()
            except OSError:
                self._reject("domain_invalid", detail="plan_unreadable"); return
            rows, perr = parse_ingestion_table(plan)
            if perr is not None:
                self._reject("domain_invalid", detail="no_ingestion_table"); return
            count, ids = file_ingested_tasks(target, rows)
            if emits_wake("ingest-plan", target):
                result = self.journal_result()
                rid = result.receipt_id if result else None
                log_event(target, command_line(
                    "ingest-plan", "%s → filed %d: %s" % (
                        os.path.basename(resolved), count,
                        ", ".join("#%d" % i for i in ids)),
                    req.get("from"), rid))
            self._send_receipt(json.dumps({
                "ok": True, "filed": count, "ids": ids}), "application/json")

        def _handle_chat_reply(self):
            """#577 — reply to an existing topic chat from the /chat/<id> page.

            A chat send (the ``chat`` branch of _handle_command) creates a NEW
            chat; this route continues an EXISTING one by appending a human
            turn through the ONE writer (apply_chat_turn). The reply is a
            continuation, so the dreamer must wake to answer it — and it wakes
            the SAME way a chat send does (the receipt committed in do_POST;
            this is the interrupt half). Registration in WRITE_ROUTE_HANDLERS
            gives it E2Shadow receipt + #274 replay verdict for free, so a
            double-click/retry never double-writes the turn.

            A typo'd id is a loud refusal, never a forked chat: the existence
            guard runs BEFORE apply (apply_chat_turn creates on first turn),
            mirroring ``bin/ud-dw-chat reply``'s discipline and reusing the
            SAME production reader (_chat_exists → _parse_chat_turns)."""
            req = self._read_json()
            if req is None:
                self._reject("malformed_json"); return
            try:
                cid = str(req["id"]).strip()
                text = str(req.get("text", "")).strip()
            except (KeyError, TypeError):
                self._reject("schema_invalid"); return
            # a chat id is a directory name under chats-v1/, so it must be a
            # safe path component — validated BEFORE it is ever joined onto a
            # path (the /chatdata gate, one route over). A bad id is refused,
            # never traversed.
            if not _CHAT_ID_RE.match(cid):
                self._reject("domain_invalid"); return
            if not text:
                self._reject("schema_invalid"); return
            # the existence guard: refuse rather than create. A chat that has
            # no parsed turn is not one you can reply to.
            if not _chat_exists(target, cid):
                self._reject("domain_invalid", detail="no_such_chat"); return
            # #342/#818 wake routing — wake the same way a chat send does.
            # `chat` is a pre-empt kind, so both new messages and replies wake
            # in every delivery mode; the receipt still rides the cursor too.
            # The route bracket carries the canonical chat id, independently
            # of this POST's receipt suffix (#527), so the line is dispatchable
            # without first reading the receipt payload.
            if emits_wake("chat", target):
                result = self.journal_result()
                rid = result.receipt_id if result else None
                log_event(target, command_line("chat", text, f"/chat/{cid}", rid))
            # best-effort write — the receipt already committed in do_POST, so
            # an IO failure never refuses the 202. apply_chat_turn is the ONE
            # writer; the route calls it, never re-implements it. Runs once per
            # receipt: #274's replay verdict short-circuited a dedup hit before
            # this handler, so a retry never appends a second turn.
            apply_chat_turn(target, cid, "human", text)
            self._send_receipt(json.dumps({"ok": True}), "application/json")

        def _handle_chat_archive(self):
            """#709 — archive or unarchive a topic chat from /chat/<id>.

            An archive flag is a NEW kind of mutation to a chat, so the trap
            is growing a second writer to the transcript. It does not: the
            writer is ``set_chat_archived``, which owns ONLY the sidecar
            marker file (disjoint from apply_chat_turn's transcript), so the
            ONE turn-writer is untouched (#577's discipline holds on the
            transcript path; this is a different file). Registration in
            WRITE_ROUTE_HANDLERS gives it E2Shadow receipt + #274 replay for
            free — and the marker write is idempotent, so a double-click/
            retry is a no-op, never a double-toggle.

            A typo'd id is a loud refusal, never a phantom marker: the
            existence guard runs BEFORE the write (mirroring _handle_chat_reply
            and reusing the SAME _chat_exists reader), so a bad id cannot leave
            a marker for a chat that does not exist. #586's trap is inherited
            too — a refusal still commits a receipt and answers 202-on/200-off
            identically — so the proof a bogus id was refused is the ABSENCE of
            the marker, not the status code (the test asserts that)."""
            req = self._read_json()
            if req is None:
                self._reject("malformed_json"); return
            try:
                cid = str(req["id"]).strip()
                archive = bool(req.get("archive", True))
            except (KeyError, TypeError):
                self._reject("schema_invalid"); return
            if not _CHAT_ID_RE.match(cid):
                self._reject("domain_invalid"); return
            if not _chat_exists(target, cid):
                self._reject("domain_invalid", detail="no_such_chat"); return
            # best-effort — the receipt already committed in do_POST, so an IO
            # failure never refuses the 202 (same discipline as the reply
            # route). Idempotent: the marker write/remove is a no-op if the
            # state already matches.
            set_chat_archived(target, cid, archive)
            self._send_receipt(json.dumps({"ok": True, "archived": archive,
                                           "id": cid}), "application/json")

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
            """Five-axis posture override (#445 + #342 delivery + #510 orchestration).

            Increment 1 triple-write: authoritative gitignored
            `.dreamwork/posture`, append-only store history, plus one
            watch-events.log line when a posture point actually changes
            — a `posture via watch` line for the pace/asking/delegation/
            orchestration point, a `delivery via watch` line for the delivery
            axis (delivery drives wake routing; the rest do not). Both
            are the SAME ceremony run-mode already uses (dual-write + one
            line on real change), not two. Identical final is 202 + no event.
            The client arms a single shared 10s pending across every axis
            (one file) and only POSTs the final point; this handler never
            debounce-timer itself. Closed sets imported from lint — never
            restated. Delegation is a non-negative integer TARGET, never a
            cap (his #445 Q3). Delivery / orchestration absent in the request
            preserve the axis's current value (a pace change must not silently
            reset wake routing or the orchestration mode); absent on disk is
            the default (instant / hands-on).
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
            # Orchestration (#510): same omit-preserves-current shape as
            # delivery; an empty value or no file falls back to hands-on.
            orchestration = str((req or {}).get("orchestration", "")).strip()
            if not orchestration:
                orchestration = current.get("orchestration", ORCHESTRATION_DEFAULT)
            if orchestration not in lint.POSTURE_STOPS_ORCHESTRATION:
                self._reject("domain_invalid"); return
            triple_same = (current.get("pace") == pace
                           and current.get("asking") == asking
                           and int(current.get("delegation", -1)) == delegation)
            delivery_same = current.get("delivery", DELIVERY_DEFAULT) == delivery
            orch_same = (current.get("orchestration", ORCHESTRATION_DEFAULT)
                         == orchestration)
            if (triple_same and delivery_same and orch_same
                    and current.get("source") == "file"):
                # Identical file-backed final: silent. (Derived-source match
                # still writes the file so an explicit override is durable.)
                self._send_receipt(json.dumps({
                    "ok": True, "pace": pace, "asking": asking,
                    "delegation": delegation, "delivery": delivery,
                    "orchestration": orchestration,
                    "changed": False, "store_log": "nothing-to-write",
                    "agreement": current["agreement"],
                }), "application/json")
                return
            # Also silent when the on-disk file already holds exactly this
            # point (resolve may have filled source=file already above).
            file_vals = read_posture_file(target)
            if (file_vals.get("pace") == pace
                    and file_vals.get("asking") == asking
                    and file_vals.get("delegation") == delegation
                    and file_vals.get("delivery", DELIVERY_DEFAULT) == delivery
                    and file_vals.get("orchestration", ORCHESTRATION_DEFAULT)
                        == orchestration
                    and len(file_vals) >= 3):
                self._send_receipt(json.dumps({
                    "ok": True, "pace": pace, "asking": asking,
                    "delegation": delegation, "delivery": delivery,
                    "orchestration": orchestration,
                    "changed": False, "store_log": "nothing-to-write",
                    "agreement": current["agreement"],
                }), "application/json")
                return
            if not write_posture(target, pace, asking, delegation, delivery,
                                 orchestration):
                self.send_error(500)
                return
            final = {
                "pace": pace, "asking": asking, "delegation": delegation,
                "delivery": delivery, "orchestration": orchestration,
            }
            axis_changes = [
                (axis, current[axis], final[axis])
                for axis in lint.POSTURE_AXES
                if current[axis] != final[axis]
            ]
            store_log = "nothing-to-write"
            if axis_changes:
                from dreamwork_db import Access, open_database
                from dreamwork_db.tasks import task_store_spec
                dw = os.path.join(target, ".dreamwork")
                try:
                    if not store_path(dw).exists():
                        raise FileNotFoundError(store_path(dw))
                    with open_database(
                            task_store_spec(store_path(dw)),
                            access=Access.WRITE) as store:
                        with store.transaction():
                            written = store.posture.append_changes(
                                axis_changes,
                                at=time.strftime(
                                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                actor="watch",
                                receipt_id=(self.journal_result().receipt_id
                                            if self.journal_result() else None),
                            )
                    if written != len(axis_changes):
                        raise RuntimeError(
                            f"wrote {written}/{len(axis_changes)} posture changes")
                    store_log = "wrote"
                except Exception as exc:
                    # Increment 1 keeps the file authoritative: a store fault
                    # must not roll back his posture, but it must be visible.
                    store_log = "failed"
                    log_event(
                        target,
                        "POSTURE STORE WRITE FAILED: " + one_line(str(exc)),
                    )
            changed = False
            # The posture point (pace/asking/delegation/orchestration) fires
            # one line on any change; orchestration rides it because it has
            # no separate consumer. Delivery has its own line (wake routing).
            if not triple_same or not orch_same:
                log_event(target, posture_line(pace, asking, delegation,
                                                orchestration, req.get("from")))
                changed = True
            if not delivery_same:
                log_event(target, delivery_line(delivery, req.get("from")))
                changed = True
            self._send_receipt(json.dumps({
                "ok": True, "pace": pace, "asking": asking,
                "delegation": delegation, "delivery": delivery,
                "orchestration": orchestration,
                "changed": changed,
                "store_log": store_log,
                "agreement": read_posture_agreement(target),
                "delegation_label": lint.delegation_posture(delegation),
            }), "application/json")

        def _handle_subagent_policy(self):
            """Free-text subagent policy override (#646 + #580, UNION of both).

            SIBLING route to /posture, NOT a field on it: every posture axis
            arms on one shared 10s pending, and this control is EXPLICITLY off
            that timer (his ruling — the inconsistency is the request), so it
            gets its own handler and its own ceremony rather than a branch in
            _handle_posture. That is the #440 call: one supported way is
            matched, not invented, because the policy is a different file, a
            different value shape (free text, no domain), and a different
            commit gesture (explicit Save/Reset buttons, not a debounced chip).

            Dual-write, the same ceremony posture/run-mode/delivery use:
            authoritative gitignored `.dreamwork/subagent-policy` plus one
            watch-events.log line only on a real change. On set, that line
            carries a faithful JSON-escaped copy of the whole policy, so a
            newline cannot forge a second event (#126). Identical-final is
            202 + no event.

            Reset = delete the file (delete_subagent_policy), returning to the
            standing default — NOT clear-to-empty, which would leave an inert
            file lint then has to complain about (read_subagent_policy's
            docstring settled this).
            """
            req = self._read_json()
            if req is None:
                self._reject("malformed_json"); return
            if not isinstance(req, dict):
                self._reject("domain_invalid"); return
            from_path = req.get("from")
            has_reset = "reset" in req
            if has_reset and (req.get("reset") is not True
                              or "policy" in req):
                self._reject("domain_invalid"); return
            # Reset: delete the override file. Idempotent — absent is already
            # the standing default, so reset-to-default returns changed=False.
            if has_reset:
                removed = delete_subagent_policy(target)
                if removed is None:
                    self.send_error(500); return
                after = resolve_posture(target)
                if removed:
                    log_event(target,
                              subagent_policy_line("reset", from_path))
                self._send_receipt(json.dumps({
                    "ok": True, "changed": removed,
                    "subagent_policy": after.get("subagent_policy", ""),
                    "subagent_policy_source": after.get(
                        "subagent_policy_source", "default"),
                }), "application/json")
                return
            text = (req or {}).get("policy", "")
            if not isinstance(text, str):
                self._reject("domain_invalid"); return
            # Identical-final: the on-disk file already holds exactly this text.
            # 202 + no event, the same idempotence posture/run-mode use.
            current = read_subagent_policy(target)
            if current is not None and current == text:
                self._send_receipt(json.dumps({
                    "ok": True, "changed": False,
                    "subagent_policy": current,
                    "subagent_policy_source": "file",
                }), "application/json")
                return
            if not write_subagent_policy(target, text):
                self._reject("domain_invalid",
                             "blank policy — clear via reset, not an empty save")
                return
            # Read back through the SAME reader the dashboard uses, not the
            # value we were handed: this is the round-trip proof (#632/#659).
            # A writer that tidied the text would be caught here, because the
            # read uses read_text_full (the whole-file reader) and the
            # comparison is byte-for-byte.
            persisted = read_subagent_policy(target)
            if persisted != text:
                self.send_error(500, "policy persistence mismatch")
                return
            log_event(target, subagent_policy_line(
                "set", from_path, persisted))
            self._send_receipt(json.dumps({
                "ok": True, "changed": True,
                "subagent_policy": persisted,
                "subagent_policy_source": "file",
            }), "application/json")

        def _handle_remind(self):
            """POST /remind — send the resolved posture to the coordinator (#551).

            The client sends nothing but the press; the message is composed
            SERVER-side so a posture without its project is never ambiguous —
            the coordinator inbox is shared across every dreamwork target on
            this host. One short paragraph carries: the target id, the
            resolved five-axis posture (resolve_posture, with the delegation
            label), and a pointer to where the meaning of each choice lives
            (SKILL.md §"Run mode (#290) and posture (#445)"; the stop
            vocabularies are lint.py's POSTURE_STOPS_* sets; the run-mode
            derivation is lint.derive_posture).

            Delivery is relay.relay("coord", …) — the append IS the delivery
            (relay stamps the [watch …] header), so this writes NO
            watch-events.log line. relay is imported lazily, mirroring
            _posture_vocab() (lint does `import watch` at its module top). The
            inbox dir is resolved through the module-level _remind_inbox_dir
            seam so tests redirect it and never touch the real inbox.
            """
            # No schema: an empty {} body is the normal press. A non-empty body
            # that is not JSON is refused — the _handle_deploy shape — so a
            # malformed press is a durable rejection, not a silent success.
            if self._body and self._body.strip():
                req = self._read_json()
                if req is None:
                    self._reject("malformed_json"); return
            import relay
            from pathlib import Path
            p = resolve_posture(target)
            src_phrase = ("override · .dreamwork/posture"
                          if p.get("source") == "file"
                          else "derived from run mode")
            body = (
                "posture remind · target {tid} · "
                "pace={pace} asking={asking} delegation={dlg} ({dlab}) "
                "delivery={dlv} orchestration={orch} · {src}. "
                "what each choice means: see SKILL.md "
                "\"Run mode (#290) and posture (#445)\"; the stop "
                "vocabularies are the POSTURE_STOPS_* sets in lint.py; "
                "the run-mode to posture derivation is lint.derive_posture."
            ).format(
                tid=_target_id(target),
                pace=p.get("pace"), asking=p.get("asking"),
                dlg=p.get("delegation"), dlab=p.get("delegation_label"),
                dlv=p.get("delivery"), orch=p.get("orchestration"),
                src=src_phrase,
            )
            inbox_dir = _remind_inbox_dir
            if callable(inbox_dir):
                inbox_dir = inbox_dir()
            relay.relay("coord", body, sender="watch",
                        inbox_dir=Path(inbox_dir) if inbox_dir else None)
            self._send_receipt(json.dumps({
                "ok": True, "sent": True,
                "posture": {
                    "pace": p.get("pace"), "asking": p.get("asking"),
                    "delegation": p.get("delegation"),
                    "delivery": p.get("delivery"),
                    "orchestration": p.get("orchestration"),
                    "source": p.get("source"),
                },
            }), "application/json")

        def _handle_deploy(self):
            """Page-triggered `just deploy` (#462).

            Loopback peer only (trusted-LAN Host/Origin is not enough: this
            restarts the server). Single-flight: a second POST while one is
            running is a durable rejection, not a second runner. The POST
            returns as soon as the runner is scheduled; success for the
            loaded document is a new GENERATION on /mtime, not this body.

            The runner is DETACHED (#567): `just deploy` runs in its own
            session with output to a file, so the recipe completes even
            though its `--stop-deployed` kills THIS process mid-recipe. The
            old runner captured output on pipes the dying server held, so the
            first print after the stop broke the pipe and the deploy died
            before it could ship the snapshot or start the new server — his
            dashboard went dark until a shell redeploy. The single-flight
            slot dies with this process (correct: the new server starts clear).

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
            "/chat-reply": _handle_chat_reply,
            "/chat-archive": _handle_chat_archive,
            "/decide": _handle_decide, "/goals": lambda self: _handle_goal_write(self, target),
            "/settings": _handle_settings,
            "/tint": _handle_tint,
            "/run-mode": _handle_run_mode,
            "/posture": _handle_posture,
            "/subagent-policy": _handle_subagent_policy,
            "/remind": _handle_remind,
            "/deploy": _handle_deploy,
        }

        def log_message(self, *_args):
            pass

    Handler.journal_shadow = journal_shadow
    return Handler


def _autoreload_sources():
    """Every file whose edit must re-exec the server.

    #397: the client assets are sources too. Before the extraction, editing
    CSS changed watch.py's own mtime and the loop below saw it; afterwards a
    `client/style.css` edit would change nothing this watcher looked at, so
    `just watch --autoreload --dev` would serve stale CSS until a manual
    restart — the exact loop a design lane lives in.

    #653: the build's OUTPUTS are sources here too, and for the mirror-image
    reason. They reach no page yet, but the startup staleness WARNING is read
    once per process, so without this a dev who runs `just build-client` to
    clear a red would keep seeing the red until they restarted by hand — the
    "edit and see nothing" loop above, one layer out. It also puts the wiring
    in place for the phase where dist IS served.
    """
    # abspath for the same reason CLIENT_DIR uses it: a relative __file__
    # after any chdir would silently stop watching watch.py itself, and
    # _sources_mtime's OSError handling would hide that it had.
    dist = [client_dist.MANIFEST_REL] + list(client_dist.OUTPUT_RELS)
    # #630 P2: the native runtime's SOURCES, on the mirror argument to the one
    # above. The outputs being watched is what lets a rebuild CLEAR a red
    # without a restart; the sources being watched is what lets an edit RAISE
    # one. The client assets already had this (they are in _CLIENT_ASSETS);
    # `dev/build/src/*.js` did not, so editing the registry and reloading gave
    # a page that read "dist is current" while it no longer was.
    #
    # Derived, never listed: `native_sources` globs the directory, so the file
    # a later phase adds is watched without an edit here. None means the
    # directory could not be read at all, which `client_dist.check` reports as
    # UNREADABLE on its own — watching a guessed set would be worse than
    # watching none.
    native = client_dist.native_sources(SELF_DIR)
    if native is not None:
        dist += native
    return ([os.path.abspath(__file__)]
            + [os.path.join(CLIENT_DIR, name) for name in _CLIENT_ASSETS]
            + [os.path.join(SELF_DIR, rel) for rel in dist])


def _sources_mtime(sources=None):
    """{path: mtime} for every watched source, or None if ANY is absent.

    None means "do not judge this tick", and the caller skips. That is the
    whole mitigation for the rename window: an editor saving a client asset
    via rename briefly unlinks it, and re-execing then imports a file that is
    not there — `FileNotFoundError`, dev server dead, no supervisor.

    A per-path MAPPING, not the newest mtime, and that is the fix rather than
    a tidy-up. `max()` over the readable files *drops* when the absent file is
    the newest one — and the newest one is precisely the file being edited,
    which is the only case this guard is about. So the previous version
    re-exec'd on a lower max during exactly the window it documented itself
    as protecting.

    `sources` is optional so the caller can pin the SAME list it announces
    (#629): the printed count, the absent-file names, and the mtimes the loop
    compares are one truth, not three reads of `_autoreload_sources()` that a
    later change could drift apart. Defaults to `_autoreload_sources()`.
    """
    if sources is None:
        sources = _autoreload_sources()
    stamps = {}
    for path in sources:
        try:
            stamps[path] = os.path.getmtime(path)
        except OSError:
            return None
    return stamps


def _autoreload_status_line(sources):
    """The one startup line the reloader prints. #629/#868: a watcher that
    found every source and one that found none must not print the same thing,
    so healthy STATES the count and a watcher that cannot start NAMES what is
    absent (rather than going silent). Pure over `sources` — it does not call
    `_sources_mtime`; the caller has already tried and branches on None — so
    the healthy-vs-dead announce is testable without running the re-exec loop.
    """
    missing = [p for p in sources if not os.path.exists(p)]
    if missing:
        return ("WARNING: --autoreload inactive — %d watched source%s absent "
                "at startup: %s" % (len(missing),
                                    "" if len(missing) == 1 else "s",
                                    ", ".join(missing)))
    return "autoreload: watching %d source%s" % (
        len(sources), "" if len(sources) == 1 else "s")


def _watch_source_and_restart(interval=1.0):
    """--autoreload: re-exec this process when its own source changes, so an
    edit takes effect with no manual restart. "Its own source" is watch.py
    AND the client assets it serves (#397). The listening socket is
    close-on-exec (Python default) so the port frees for the new image;
    clients reload on the changed GENERATION. Daemon thread; never blocks.

    #629/#868 — the watch set is a denominator. A run that found no sources
    and one that found all of them must not behave alike, so the reloader
    announces what it watches, and a source absent at startup is named loudly
    instead of silently disabling the flag. The previous body did `last =
    _sources_mtime(); if last is None: return` — no print, no warning — so a
    missing dist file or a renamed asset at startup killed `--autoreload` for
    the whole session with no signal anywhere. That is the same family as an
    instrument that reports 'no change' when the change is real: a flag whose
    name promises reload silently delivers nothing. `sources` is pinned once
    so the announce, the absent-file list, and the loop's comparison are one
    truth. This is dev-scoped: `--autoreload`/`--dev` only; production serves
    the import-time cache by design and never re-reads per request."""
    sources = _autoreload_sources()
    last = _sources_mtime(sources)
    print(_autoreload_status_line(sources))
    if last is None:
        # Not the rename window: nothing is being edited at startup. A source
        # is genuinely absent — announce (above) and stop, rather than serve a
        # false "autoreload is on" by looping over a set the loop can never
        # read. The announce is what makes 'watching nothing' unlike 'all'.
        return
    while True:
        time.sleep(interval)
        now = _sources_mtime(sources)
        if now is None:
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
    # Build the handler OUTSIDE the bind's except. It used to sit inside the
    # try, so any OSError it raised was reported as a port conflict — and
    # since #397 the handler reaches the client assets, which makes OSError
    # ("client asset X is empty", a missing client/ under a bad #425 layout)
    # a routine outcome of this call rather than an unreachable one. A missing
    # stylesheet announced as "cannot bind — another instance may be running"
    # sends whoever debugs it to the wrong subsystem entirely; let it raise
    # with its own traceback instead.
    handler = make_handler(args.target, dev=args.dev, authority=net.authority)
    try:
        server = server_class(net.family)((net.bind, port), handler)
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
    # #653 — the one HUMAN-visible surface of the staleness reading at P1.
    # The page cannot carry it yet: rendering it would edit client/views.js,
    # and P1's whole claim is that the served bytes do not change. So it goes
    # where a person already looks when they start the server. Never a refusal
    # to serve — a stale design bundle must not dark the dashboard.
    _dist = client_dist.check(SELF_DIR)
    if _dist["state"] != client_dist.OK:
        print("WARNING: client/dist is %s — %s%s" % (
            _dist["state"], _dist["note"],
            (" (%s)" % _dist["fix"]) if _dist["fix"] else ""))
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
        "POSTURE_STOPS_ORCHESTRATION",
        "DELEGATION_POSTURES", "POSTURE_AXES", "derive_posture",
        "delegation_posture", "RUN_MODE_TO_POSTURE",
        # #650 — the free-text policy field's name, home and standing value.
        # Proxied for the same reason as the stop sets: lint owns the schema
        # and this module consumes it, never restates it.
        "SUBAGENT_POLICY_FILE", "SUBAGENT_POLICY_DEFAULT",
        "POSTURE_TEXT_FIELDS",
    ):
        return getattr(_posture_vocab(), name)
    raise AttributeError(f"module 'watch' has no attribute {name!r}")


def group_progress(target):
    """Task groups with progress derived from their exact durable members.

    READ access never migrates or writes the store. Empty groups remain in
    the payload, but carry no ratio: without a denominator the view has not
    judged progress and must not draw a reassuring 0% or 100% bar.
    """
    from dreamwork_db import Access, DatabaseError, open_database
    from dreamwork_db.groups import EmptyGroup
    from dreamwork_db.tasks import task_store_spec

    path = store_path(os.path.join(target, ".dreamwork"))
    if not path.exists():
        return []
    try:
        with open_database(task_store_spec(path), access=Access.READ) as store:
            records = []
            for group in store.groups.list():
                record = {
                    "id": group.id,
                    "kind": group.kind,
                    "title": group.title,
                    "description": group.description,
                }
                try:
                    progress = store.groups.progress(group.id)
                except EmptyGroup as exc:
                    record["progress_error"] = str(exc)
                else:
                    record.update({
                        "completed": progress.completed,
                        "completed_count": progress.completed_count,
                        "total_count": progress.total_count,
                        "member_task_ids": list(progress.member_task_ids),
                        "landed_task_ids": list(progress.landed_task_ids),
                    })
                records.append(record)
            return records
    except DatabaseError:
        # The dashboard's collector is a read surface, not a migration route.
        # A pre-v004 or unreadable store therefore supplies no group claim;
        # another writer may migrate it through the canonical open path.
        return []


def task_payload_record(record):
    """Project one repository record into the honest /tasks vocabulary.

    The store has two durable states.  A structured blocker refines an open
    task to ``blocked``; every other value fails closed to ``unknown``.  Owner
    is deliberately null: the store has no owner field, and prose in ``body``
    is not a database column.
    """
    raw_state = record.get("state")
    blocked_on = record.get("blocked_on")
    if raw_state == "landed":
        state = "landed"
    elif raw_state == "open" and blocked_on:
        state = "blocked"
    elif raw_state == "open":
        state = "open"
    else:
        state = "unknown"
    dependencies = [int(value) for value in re.findall(
        r"#(\d+)", blocked_on or "")]
    return {
        "id": int(record["id"]),
        "state": state,
        "title": record.get("title"),
        "body": record.get("body"),
        "priority": record.get("priority"),
        "type": record.get("type"),
        "origin": record.get("origin"),
        "date": record.get("date"),
        "owner": None,
        "dependencies": dependencies,
        "blocked_on": blocked_on,
    }


def tasks_payload(target):
    """Read /tasks data through TaskRepository.records(), the one store seam."""
    dw = os.path.join(target, ".dreamwork")
    envelope = {
        "health": "missing",
        "unavailable_fields": ["owner"],
        "tasks": [],
    }
    if source_of_truth(dw) != "store":
        return envelope
    from dreamwork_db import Access, open_database
    from dreamwork_db.tasks import task_store_spec
    try:
        with open_database(
                task_store_spec(store_path(dw)), access=Access.READ) as store:
            records = store.tasks.records()
    except Exception:
        envelope["health"] = "unavailable"
        return envelope
    envelope["health"] = "ok"
    envelope["tasks"] = [task_payload_record(record) for record in records]
    return envelope


def tasks_response(target, query):
    """Build the list or canonical single-task /tasksdata envelope."""
    payload = tasks_payload(target)
    raw_id = (urllib.parse.parse_qs(query).get("t") or [None])[0]
    if raw_id is None:
        payload["tasks"] = [
            {key: value for key, value in task.items() if key != "body"}
            for task in payload["tasks"]
        ]
        return payload
    task_id = int(raw_id) if raw_id.isdigit() else None
    task = next((row for row in payload["tasks"]
                 if row["id"] == task_id), None)
    payload.pop("tasks")
    payload["task"] = task
    return payload


def _goal_criteria(details):
    """Numbered/list criteria under the exact ``## Done when`` heading."""
    criteria = []
    active = False
    for line in details.splitlines():
        if line.startswith("## "):
            active = line.strip().casefold() == "## done when"
            continue
        if not active:
            continue
        match = re.match(r"\s*(?:[-*+]\s+(?:\[[ xX]\]\s+)?|\d+[.)]\s+)(.+)", line)
        if match:
            criteria.append(match.group(1).strip())
    return criteria


def goal_tree_payload(target):
    """The one read projection for the dashboard handle and ``/goals``.

    ``expected_count`` is derived independently from ``preorder`` so a walk
    that drops a subtree fails closed instead of rendering a plausible partial
    tree. Empty and unreadable therefore cannot share an envelope.
    """
    dw = os.path.join(target, ".dreamwork")
    envelope = {
        "health": "missing", "examined_count": 0, "expected_count": 0,
        "current_goal_id": None, "nodes": [],
    }
    if source_of_truth(dw) != "store":
        return envelope
    from dreamwork_db import Access, DatabaseError, open_database
    from dreamwork_db.groups import EmptyGroup
    from dreamwork_db.tasks import task_store_spec
    try:
        with open_database(
                task_store_spec(store_path(dw)), access=Access.READ) as store:
            all_goals = tuple(group for group in store.groups.list()
                              if group.kind == "goal")
            expected = tuple(group.id for group in all_goals)
            ordered = store.goals.preorder()
            envelope["expected_count"] = len(expected)
            envelope["examined_count"] = len(ordered)
            if (len(ordered) != len(expected) or
                    set(ordered) != set(expected)):
                envelope.update({
                    "health": "incomplete",
                    "error": (
                        "goal tree incomplete: examined %d of %d goal nodes; "
                        "refusing to render a partial tree"
                        % (len(ordered), len(expected))),
                })
                return envelope

            task_records = {
                record["id"]: task_payload_record(record)
                for record in store.tasks.records()
            }
            groups = {group.id: group for group in all_goals}
            nodes = []
            for group_id in ordered:
                group = groups[group_id]
                blockers = []
                blocker_keys = set()

                def add_blocker(blocker):
                    key = (blocker.needs_kind, blocker.needs_id)
                    if key in blocker_keys:
                        return
                    blocker_keys.add(key)
                    if blocker.needs_kind == "group":
                        needed = store.groups.get(blocker.needs_id)
                        title = needed.title
                    else:
                        title = task_records.get(
                            blocker.needs_id, {}).get("title", "unknown task")
                    blockers.append({
                        "kind": blocker.needs_kind,
                        "id": blocker.needs_id,
                        "title": title,
                        "reason": blocker.reason,
                    })

                for blocker in store.groups.blockers(group_id=group_id):
                    add_blocker(blocker)
                node = {
                    "id": group.id,
                    "title": group.title,
                    "details": group.description,
                    "criteria": _goal_criteria(group.description),
                    "parent_id": group.parent_id,
                    "rank": store.goals.rank(group.id),
                    "state": store.goals.state(group.id),
                    "blockers": blockers,
                    "member_tasks": [],
                    "verdicts": [],
                }
                try:
                    progress = store.groups.progress(group.id)
                except EmptyGroup as exc:
                    node["progress_error"] = str(exc)
                else:
                    # blockers(task_id=...) is the repository seam that adds
                    # every governing group, including ancestor goals. Do not
                    # reproduce that hierarchy walk here.
                    for task_id in progress.member_task_ids:
                        for blocker in store.groups.blockers(task_id=task_id):
                            add_blocker(blocker)
                    node.update({
                        "completed_count": progress.completed_count,
                        "total_count": progress.total_count,
                        "member_tasks": [
                            task_records[task_id]
                            for task_id in progress.member_task_ids
                            if task_id in task_records
                        ],
                    })
                claims = store.goals.claims(group.id)
                if claims:
                    node["verdicts"] = [{
                        "lens": verdict.lens,
                        "refuted": verdict.refuted,
                        "blocking": verdict.blocking,
                        "findings": list(verdict.findings),
                        "corroborated": list(verdict.corroborated),
                        "examined": dict(verdict.examined),
                    } for verdict in store.goals.verdicts(claims[-1].id)]
                nodes.append(node)
            envelope.update({
                "health": "ok",
                "current_goal_id": store.goals.current_goal_id(),
                "nodes": nodes,
            })
            return envelope
    except (DatabaseError, OSError, ValueError) as exc:
        envelope.update({
            "health": "unavailable",
            "error": (
                "goal tree unavailable after examining %d of %d goal nodes: %s"
                % (envelope["examined_count"], envelope["expected_count"], exc)),
        })
        return envelope


def _append_goal_condition(details, condition):
    """Append one human-authored criterion under the exact Done when heading."""
    lines = details.splitlines()
    heading = next((index for index, line in enumerate(lines)
                    if line.strip().casefold() == "## done when"), None)
    if heading is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(("## Done when", f"- {condition}"))
    else:
        end = next((index for index in range(heading + 1, len(lines))
                    if lines[index].startswith("## ")), len(lines))
        lines.insert(end, f"- {condition}")
    return "\n".join(lines) + "\n"


def _handle_goal_write(handler, target):
    """Apply one quiet /goals mutation through the canonical store handle."""
    from dreamwork_db import Access, NotFound, ValidationError, open_database
    from dreamwork_db.tasks import task_store_spec

    req = handler._read_json()
    if req is None:
        handler._reject("malformed_json"); return
    if not isinstance(req, dict):
        handler._reject("schema_invalid"); return
    action = req.get("action")
    if action not in ("edit-details", "add-condition", "add-goal"):
        handler._reject("schema_invalid"); return
    dw = os.path.join(target, ".dreamwork")
    if source_of_truth(dw) != "store":
        handler._reject("domain_invalid", detail="no_store"); return

    try:
        with open_database(
                task_store_spec(store_path(dw)), access=Access.WRITE) as store:
            with store.transaction():
                if action in ("edit-details", "add-condition"):
                    goal_id = req.get("goal_id")
                    if isinstance(goal_id, bool) or not isinstance(goal_id, int):
                        raise ValidationError("goal_id must be an integer")
                    goal = store.groups.get(goal_id)
                    if goal.kind != "goal":
                        raise ValidationError("target group is not a goal")
                    if action == "edit-details":
                        details = req.get("details")
                        if not isinstance(details, str):
                            raise ValidationError("details must be a string")
                    else:
                        condition = req.get("condition")
                        if not isinstance(condition, str) or not condition.strip():
                            raise ValidationError("condition must be non-empty text")
                        details = _append_goal_condition(
                            goal.description, condition.strip())
                    store.groups._session.execute(
                        "UPDATE task_group SET description = ? WHERE id = ?",
                        (details, goal_id))
                    written_id = goal_id
                else:
                    title = req.get("title")
                    details = req.get("details", "")
                    parent_id = req.get("parent_id")
                    rank = req.get("rank")
                    if not isinstance(title, str) or not title.strip():
                        raise ValidationError("title must be non-empty text")
                    if not isinstance(details, str):
                        raise ValidationError("details must be a string")
                    if parent_id is not None:
                        if isinstance(parent_id, bool) or not isinstance(parent_id, int):
                            raise ValidationError("parent_id must be an integer or null")
                        if store.groups.get(parent_id).kind != "goal":
                            raise ValidationError("parent group is not a goal")
                    if rank is not None and (isinstance(rank, bool)
                                             or not isinstance(rank, int)):
                        raise ValidationError("rank must be an integer or null")
                    written_id = store.groups.create(
                        kind="goal", title=title, description=details,
                        parent_id=parent_id, actor="human-via-watch",
                        at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                    store.goals.set_state(written_id, "open")
                    store.goals.set_rank(written_id, rank)
    except (NotFound, ValidationError, ValueError, TypeError) as exc:
        handler._reject("domain_invalid", detail=str(exc)); return
    except Exception:
        handler.send_error(500); return

    # Deliberately no log_event/emits_wake call: every /goals action is quiet
    # under every posture. The receipt above is its delivery on the next tick.
    handler._send_receipt(json.dumps({
        "ok": True, "action": action, "goal_id": written_id,
    }), "application/json")


if __name__ == "__main__":
    main()
