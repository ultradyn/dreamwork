#!/usr/bin/env python3
"""Unit tests for watch.py's data collector. Run: python3 test_watch.py"""

import contextlib
import errno
import hashlib
import html
import http.server
import inspect
import io
import json
import os
import re
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock
import urllib.error
import urllib.parse
import urllib.request

import watch


QUESTIONS = """# Questions for the human

## Open

- **A real open question?** context here.
- not a question bullet

## Answered

- **Old one** -> resolved.
"""


def make_target(root):
    dw = os.path.join(root, ".dreamwork")
    os.makedirs(os.path.join(dw, "dreams", "archive"))
    os.makedirs(os.path.join(dw, "docs"))
    with open(os.path.join(root, "DREAMWORK.md"), "w") as f:
        f.write("# DREAMWORK\n")
    with open(os.path.join(dw, "dreams", "2026-01-01-x.md"), "w") as f:
        f.write("dream body\n")
    with open(os.path.join(dw, "dreams", "archive", "2025-12-01-y.md"),
              "w") as f:
        f.write("old dream\n")
    with open(os.path.join(dw, "questions.md"), "w") as f:
        f.write(QUESTIONS)
    with open(os.path.join(dw, "lessons.md"), "w") as f:
        f.write("# Lessons\n")
    with open(os.path.join(dw, "skill-version"), "w") as f:
        f.write("2026-07-25-x.md\n")
    return root


# #509 — a fixture DERIVED FROM the real answered #229 entry's triggering
# features: a hard-wrapped title, a `-> answered` resolution head inside a
# long rewrappable prose body, and a note carrying a box-drawing (nested)
# table plus a code fence. The real entry is the longest in questions.md and
# was the phantom's trigger. The body is one word-bag re-wrapped at a
# caller-chosen width, so two builds of the SAME words at DIFFERENT widths
# exercise the re-wrap the loop performs on every questions.md rewrite.
_LONG_ENTRY_229_BODY = (
    "The reviewed artifact is at `.dreamwork/review/topic-chats.html`. "
    "→ answered (2026-07-26 17:11): Revision directed, not approved. "
    "Update the artifact against the full architecture review and the "
    "measured UX review, self-review it against the project goals, then "
    "open a new proposal for human review. No implementation authority was "
    "granted. Rec: a compact dashboard chat index plus a dedicated `/chat` "
    "route; append-only Markdown transcript as primary truth and fresh "
    "worker input; one run and one editable queued follow-up per chat; a "
    "deep orchestration module; global cap two; machine-local gitignored "
    "chats; no MVP cancellation until `cancelled` can be durably finalised; "
    "manual retention. This is proposal approval only, not authority to "
    "implement. Answer `Approve A to E as recommended`, or name changes to "
    "A surface, B privacy, C concurrency, D cancellation, or E retention."
)
_LONG_ENTRY_229_NOTE = (
    "  - **Note (human, via watch, 2026-07-26 16:35):** re the proposal, a "
    "nested table of pre-build checks and a code fence:\n"
    "    ┌──────────────────────────────┬──────────────────┐\n"
    "    │ Check                        │ Why              │\n"
    "    ├──────────────────────────────┼──────────────────┤\n"
    "    │ Write the state machine      │ crash points     │\n"
    "    └──────────────────────────────┴──────────────────┘\n"
    "    ```\n"
    "    cap = 2  # per-machine lease, not per-process\n"
    "    ```\n"
    "  - **Follow-up (loop, via watch, 2026-07-26 16:48):** all checks "
    "accepted as proposal-hardening inputs, not approval.\n"
)


def _long_entry_229_md(body, body_width=72):
    """Build a questions.md whose answered #229 entry wraps `body` (a single
    word-bag) at `body_width`. Same words, different width => the re-wrap the
    loop performs on every questions.md rewrite."""
    import textwrap
    lines = textwrap.wrap(body, body_width, break_long_words=False,
                          break_on_hyphens=False)
    body_block = "\n".join("  " + ln for ln in lines)
    return (
        "# Questions for the human\n\n## Open\n\n## Answered\n\n"
        "- **P1 · 2026-07-26 — #229 threaded topic chats: approve the proposed\n"
        "  architecture and defaults?**\n"
        + body_block + "\n\n"
        + _LONG_ENTRY_229_NOTE
    )


# #534 — the OLD (sigtext-v0) digest algorithm: the raw-text payload the
# store held BEFORE the #509 whitespace normalisation. Live stores in the
# wild still hold these digests, so the re-seed test must build a store with
# them. This mirrors `_entry_content_digest` EXACTLY minus the `_sig_text`
# collapse (the one thing the v0->v1 change touched), so the runtime
# precondition "old digest != new digest" is meaningful and not an artefact
# of a hand-faked hash.
def _old_algo_digest(entry):
    payload = {
        "title": entry.get("title"),
        "body": entry.get("body"),
        "follows": entry.get("follows") or [],
        "answers": entry.get("answers") or [],
        "answer": entry.get("answer"),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _write_old_algo_store(target, entries, algo=None, stamps=None):
    """Write a question-sigs.json as if produced by an older algorithm.

    `entries` are the live entry dicts (title/body/...); each is recorded
    under its title key with the OLD-algo digest. `algo` controls the store's
    `algo` marker (None => unmarked, the pre-#534 shape live stores have).
    `stamps` (optional) maps title -> a prior updated_at to carry, modelling
    an entry that really did change before the algorithm upgrade."""
    store = {}
    for e in entries:
        key = watch._title_sig_key(e.get("title"))
        store[key] = {
            "digest": _old_algo_digest(e),
            "updated_at": (stamps or {}).get(e.get("title")),
            "title": (e.get("title") or "")[:120],
        }
    if algo is not None:
        store["algo"] = algo
    path = os.path.join(target, ".dreamwork", watch.QUESTION_SIGS)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(store, f)
    return path


class TestRequestAuthority(unittest.TestCase):
    def test_normalise_host_token(self):
        cases = {
            "Example.COM.": "example.com",
            "127.000.000.001": None,
            "127.0.0.1": "127.0.0.1",
            "[2001:0db8::1]": "2001:db8::1",
            "2001:db8::1": "2001:db8::1",
            "LOCALHOST": "localhost",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                if expected is None:
                    with self.assertRaises(ValueError):
                        watch.normalise_host_token(raw)
                else:
                    self.assertEqual(watch.normalise_host_token(raw), expected)

        for raw in ("", "*", "*.example.com", "example.com:80", "bad host",
                    "bad/host", "bad\nhost", "[::1", "::1]", "-bad.example",
                    "bad-.example", "a..b"):
            with self.subTest(rejected=raw):
                with self.assertRaises(ValueError):
                    watch.normalise_host_token(raw)

    def test_split_host_header(self):
        cases = {
            "Example.COM.:35110": ("example.com", 35110),
            "localhost": ("localhost", None),
            "127.0.0.1:80": ("127.0.0.1", 80),
            "[2001:db8::1]:35110": ("2001:db8::1", 35110),
            "[::1]": ("::1", None),
            "2001:db8::1": None,
            "example.com:0": None,
            "example.com:65536": None,
            "example.com:not-a-port": None,
            "one.example, two.example": None,
            "": None,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(watch.split_host_header(raw), expected)

    def test_host_and_origin_authority(self):
        auth = watch.RequestAuthority(["localhost", "xsm", "192.168.1.20",
                                       "2001:db8::1"], 35110)
        for header in ("localhost:35110", "XSM:35110", "192.168.1.20:35110",
                       "[2001:db8::1]:35110"):
            with self.subTest(allowed=header):
                self.assertTrue(auth.host_allowed(header))
        for header in (None, "", "evil.test:35110", "xsm:35111", "xsm:bad",
                       "2001:db8::1"):
            with self.subTest(rejected=header):
                self.assertFalse(auth.host_allowed(header))

        self.assertTrue(auth.origin_allowed(None, "xsm:35110"))
        self.assertTrue(auth.origin_allowed("", "xsm:35110"))
        self.assertTrue(auth.origin_allowed("http://xsm:35110", "XSM:35110"))
        self.assertTrue(auth.origin_allowed("http://[2001:db8::1]:35110",
                                            "[2001:db8::1]:35110"))
        for origin in ("null", "https://xsm:35110", "http://evil:35110",
                       "http://xsm:35111", "http://user@xsm:35110",
                       "http://xsm:35110/path", "not a url"):
            with self.subTest(rejected_origin=origin):
                self.assertFalse(auth.origin_allowed(origin, "xsm:35110"))

    def test_bind_family_and_display_host(self):
        self.assertEqual(watch.bind_family("127.0.0.1"), watch.socket.AF_INET)
        self.assertEqual(watch.bind_family("0.0.0.0"), watch.socket.AF_INET)
        self.assertEqual(watch.bind_family("::1"), watch.socket.AF_INET6)
        self.assertEqual(watch.bind_family("::"), watch.socket.AF_INET6)
        with self.assertRaises(ValueError):
            watch.bind_family("localhost")

        self.assertEqual(watch.display_host("127.0.0.1",
                                            ["localhost", "127.0.0.1"], None),
                         "127.0.0.1")
        with self.assertRaises(ValueError):
            watch.display_host("127.0.0.1", ["localhost"], None)
        self.assertEqual(watch.display_host("::1", ["::1"], None), "[::1]")
        self.assertEqual(watch.display_host("0.0.0.0", ["xsm"], "xsm"), "xsm")
        self.assertEqual(watch.display_host("::", ["2001:db8::1"],
                                            "2001:db8::1"), "[2001:db8::1]")
        with self.assertRaises(ValueError):
            watch.display_host("0.0.0.0", ["xsm"], None)
        with self.assertRaises(ValueError):
            watch.display_host("::", ["xsm"], None)
        with self.assertRaises(ValueError):
            watch.display_host("0.0.0.0", ["xsm"], "other")


class TestRequestAuthorityHTTP(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = make_target(self.tmp.name)
        # Reserve a real port first, then bind the tested server to it so the
        # authority checks the actual port its Host header must carry.
        probe = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                                http.server.BaseHTTPRequestHandler)
        port = probe.server_address[1]
        probe.server_close()
        self.authority = watch.RequestAuthority(["allowed.test", "127.0.0.1"],
                                                port)
        self.server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", port),
            watch.make_handler(self.target, authority=self.authority))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{port}"
        self.host = f"allowed.test:{port}"

    def request(self, path, *, host=None, origin=None, data=None):
        headers = {}
        if host is not None:
            headers["Host"] = host
        if origin is not None:
            headers["Origin"] = origin
        if data is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(data).encode()
        req = urllib.request.Request(self.base + path, data=data, headers=headers,
                                     method="POST" if data is not None else "GET")
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def test_host_gates_every_get_before_target_read(self):
        self.assertEqual(self.request("/data.json", host="evil.test")[0], 421)
        self.assertEqual(self.request("/data.json", host=self.host)[0], 200)

    def test_origin_gates_post_before_body_witness(self):
        payload = {"kind": "add-idea", "text": "must not be witnessed"}
        status, _ = self.request("/command", host=self.host,
                                 origin="http://evil.test", data=payload)
        self.assertEqual(status, 403)
        self.assertFalse(os.path.exists(os.path.join(
            self.target, ".dreamwork", "submissions.log")))

    def test_allowed_browser_and_cli_posts_are_witnessed(self):
        payload = {"kind": "add-idea", "text": "trusted LAN words"}
        self.assertEqual(self.request(
            "/command", host=self.host, origin=f"http://{self.host}",
            data=payload)[0], 202)
        self.assertEqual(self.request(
            "/command", host=self.host,
            data={"kind": "add-idea", "text": "CLI words"})[0], 202)
        with open(os.path.join(self.target, ".dreamwork", "submissions.log"),
                  encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle]
        self.assertEqual([row["req"]["text"] for row in rows],
                         ["trusted LAN words", "CLI words"])


class FakeConnection:
    """Just enough socket for StreamRequestHandler.setup: the request bytes
    in one direction, and a `sendall` that accepts `fail_after` writes then
    raises `exc` — a peer that leaves after the headers but before the body
    (#299). (wbufsize == 0, so BaseHTTPRequestHandler writes via sendall.)"""

    def __init__(self, request_bytes, exc, fail_after=1):
        self._rfile = io.BytesIO(request_bytes)
        self.exc = exc
        self.fail_after = fail_after
        self.writes = []

    def makefile(self, mode, _bufsize=-1):
        assert "r" in mode
        return self._rfile

    def sendall(self, data):
        self.writes.append(data)
        if len(self.writes) > self.fail_after:
            raise self.exc


class TestPeerDisconnect(unittest.TestCase):
    """#299: a browser cancelling a poll mid-response is expected client
    behaviour. It must not escape `handle` into socketserver's traceback
    printer — and every unrelated error still must."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = make_target(self.tmp.name)
        self.authority = watch.RequestAuthority(["127.0.0.1"], 9)
        self.handler_cls = watch.make_handler(self.target,
                                              authority=self.authority)

    def run_request(self, exc, path="/mtime", fail_after=1):
        # StreamRequestHandler.__init__ runs setup/handle/finish, so an
        # exception escaping the exchange surfaces right here.
        request = FakeConnection(
            f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:9\r\n\r\n".encode(),
            exc, fail_after=fail_after)
        handler = self.handler_cls(request, ("127.0.0.1", 43210),
                                   unittest.mock.Mock())
        return handler, request

    def test_cancelled_mtime_poll_is_quiet_and_closes(self):
        handler, conn = self.run_request(
            BrokenPipeError(errno.EPIPE, "Broken pipe"))  # must not raise
        self.assertTrue(handler.close_connection)
        self.assertIn(b"text/plain", conn.writes[0])   # real _send ran
        self.assertEqual(len(conn.writes), 2)          # headers, body

    def test_each_expected_disconnect_error_is_quiet(self):
        cases = [
            BrokenPipeError(errno.EPIPE, "Broken pipe"),
            ConnectionResetError(errno.ECONNRESET, "reset"),
            ConnectionAbortedError(errno.ECONNABORTED, "aborted"),
        ]
        for nr in (errno.EPIPE, errno.ECONNRESET, errno.ECONNABORTED):
            plain = OSError("peer gone")
            plain.errno = nr       # plain OSError carrying the exact errno
            cases.append(plain)
        for exc in cases:
            with self.subTest(exc=repr(exc)):
                self.run_request(exc)

    def test_disconnect_during_error_response_is_quiet(self):
        # 404 path: the very first (headers) write meets the departed peer.
        self.run_request(BrokenPipeError(errno.EPIPE, "Broken pipe"),
                         path="/nope", fail_after=0)    # must not raise

    def test_unrelated_errors_still_escape(self):
        for exc in (OSError(errno.ENOENT, "No such file or directory"),
                    RuntimeError("boom")):
            with self.subTest(exc=repr(exc)):
                with self.assertRaises(type(exc)):
                    self.run_request(exc)


class TestPeerDisconnectLive(unittest.TestCase):
    """The real server keeps serving across peers that RST mid-poll (#299)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = make_target(self.tmp.name)
        probe = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)
        self.port = probe.server_address[1]
        probe.server_close()
        authority = watch.RequestAuthority(["127.0.0.1"], self.port)
        self.server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", self.port),
            watch.make_handler(self.target, authority=authority))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def test_repeated_cancelled_polls_leave_the_server_responsive(self):
        host = f"127.0.0.1:{self.port}"
        request = f"GET /mtime HTTP/1.1\r\nHost: {host}\r\n\r\n".encode()
        for _ in range(5):
            with socket.create_connection(("127.0.0.1", self.port),
                                          timeout=5) as sock:
                sock.sendall(request)
                # RST, not FIN: the peer is gone before any response lands.
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                                struct.pack("ii", 1, 0))
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/mtime",
                                     headers={"Host": host})
        with urllib.request.urlopen(req, timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertTrue(response.read().strip())


class TestLANCLI(unittest.TestCase):
    def test_cli_surface_and_loopback_defaults(self):
        args = watch.parse_args(["--target", "/tmp/project", "--port", "35110"])
        self.assertEqual(args.bind, "127.0.0.1")
        self.assertEqual(args.allow_host, [])
        options = watch.network_options(args.bind, args.allow_host,
                                        args.url_host, args.port)
        self.assertEqual(options.bind, "127.0.0.1")
        self.assertEqual(options.url_host, "127.0.0.1")
        self.assertEqual(options.family, watch.socket.AF_INET)
        self.assertFalse(options.trusted_lan)
        self.assertTrue({"localhost", "127.0.0.1", "::1"}.issubset(
            set(options.allowed_hosts)))

    def test_non_loopback_requires_explicit_allowlist_and_url_host(self):
        with self.assertRaises(ValueError):
            watch.network_options("0.0.0.0", [], None, 35110)
        with self.assertRaises(ValueError):
            watch.network_options("0.0.0.0", ["xsm"], None, 35110)
        with self.assertRaises(ValueError):
            watch.network_options("0.0.0.0", ["xsm"], "other", 35110)
        options = watch.network_options("0.0.0.0", ["xsm", "192.168.1.20"],
                                        "xsm", 35110)
        self.assertTrue(options.trusted_lan)
        self.assertEqual(options.url_host, "xsm")
        self.assertEqual(options.allowed_hosts, ("192.168.1.20", "xsm"))

    def test_concrete_lan_bind_may_advertise_itself_when_explicitly_allowed(self):
        options = watch.network_options("192.168.1.20", ["192.168.1.20"],
                                        None, 35110)
        self.assertEqual(options.url_host, "192.168.1.20")
        self.assertTrue(options.trusted_lan)

    def test_concrete_lan_bind_requires_allowed_advertised_host(self):
        # The printed/opened URL is part of the authority contract: it must not
        # point at a Host that this same server answers with 421. A concrete
        # bind may default to itself only when that token was explicitly
        # allowlisted; otherwise the operator must choose an allowed url-host.
        with self.assertRaisesRegex(ValueError, "url-host"):
            watch.network_options("192.168.1.20", ["xsm"], None, 35110)
        with self.assertRaisesRegex(SystemExit, "url-host"):
            watch.main(["--target", "/tmp/project", "--port", "35110",
                        "--bind", "192.168.1.20", "--allow-host", "xsm"])
        options = watch.network_options("192.168.1.20", ["xsm"],
                                        "xsm", 35110)
        self.assertEqual(options.url_host, "xsm")
        self.assertIn("xsm", options.allowed_hosts)

    def test_ipv6_family_and_url_brackets(self):
        args = watch.parse_args(["--bind", "::", "--allow-host", "xsm",
                                 "--allow-host", "2001:db8::1",
                                 "--url-host", "2001:db8::1"])
        options = watch.network_options(args.bind, args.allow_host,
                                        args.url_host, 35110)
        self.assertEqual(options.family, watch.socket.AF_INET6)
        self.assertEqual(options.url_host, "[2001:db8::1]")
        self.assertEqual(watch.server_class(options.family).address_family,
                         watch.socket.AF_INET6)

    def test_cli_rejects_repeated_singular_flags(self):
        with self.assertRaises(SystemExit):
            watch.parse_args(["--bind", "127.0.0.1", "--bind", "::1"])
        with self.assertRaises(SystemExit):
            watch.parse_args(["--url-host", "xsm", "--url-host", "host2"])

    def test_main_prints_warning_and_opens_only_navigable_allowed_url(self):
        class FakeServer:
            def __init__(self, address, handler):
                self.address = address
                self.handler = handler
                self.served = False

            def serve_forever(self):
                self.served = True

        made = []
        def factory(address, handler):
            server = FakeServer(address, handler)
            made.append(server)
            return server

        out = io.StringIO()
        with (unittest.mock.patch.object(watch, "server_class",
                                         return_value=factory),
              unittest.mock.patch.object(watch.webbrowser, "open") as opened,
              contextlib.redirect_stdout(out)):
            watch.main(["--target", "/tmp/project", "--port", "35110",
                        "--bind", "0.0.0.0", "--allow-host", "xsm",
                        "--url-host", "xsm", "--open"])
        text = out.getvalue()
        self.assertEqual(made[0].address, ("0.0.0.0", 35110))
        self.assertTrue(made[0].served)
        self.assertIn("http://xsm:35110/", text)
        self.assertIn("allowed Hosts: xsm", text)
        self.assertIn("trusted-LAN mode is unauthenticated", text)
        self.assertIn("Public/WAN exposure is unsupported", text)
        opened.assert_called_once_with("http://xsm:35110/")


class TestCollector(unittest.TestCase):
    def test_age_str(self):
        self.assertEqual(watch.age_str(30), "30s")
        self.assertEqual(watch.age_str(90), "1m")
        self.assertEqual(watch.age_str(7200), "2h")
        self.assertEqual(watch.age_str(200000), "2d")

    def test_open_question_count(self):
        self.assertEqual(watch.open_question_count(QUESTIONS), 1)
        self.assertEqual(watch.open_question_count(None), 0)
        self.assertEqual(watch.open_question_count("## Answered\n- **x**"), 0)

    def test_collect(self):
        with tempfile.TemporaryDirectory() as d:
            data = watch.collect(make_target(d))
            self.assertEqual(len(data["dreams"]), 1)
            self.assertEqual(len(data["dreams_archive"]), 1)
            self.assertIn("mtime", data["dreams"][0])
            self.assertEqual(data["open_questions"], 1)
            self.assertEqual(data["files"]["skill-version"],
                             "2026-07-25-x.md")
            self.assertIsNone(data["status"])       # no status.json
            self.assertEqual(data["git"], [])       # not a git repo

    def test_collect_surfaces_no_chats_when_absent(self):
        """#504 — collect degrades to [] when there is no chats-v1 store (the
        slice ships before the apply lane; the dashboard stays quiet).

        Production line: the `list_chats(target)` call + the `if not
        os.path.isdir(root): return []` guard. A target with no chats must
        surface [], never throw.
        """
        with tempfile.TemporaryDirectory() as d:
            data = watch.collect(make_target(d))
            self.assertEqual(data["chats"], [])

    def test_collect_surfaces_chats_derived_from_transcripts(self):
        """#504 — collect's `chats` key derives chat records from chats-v1
        transcripts (title/turn count/status are derived, not a second truth).

        Production line: list_chats + _parse_chat_turns. PRECONDITION asserted
        at runtime: the two chats differ in status (one pending, one replied)
        and in turn count, so a reader that collapsed them or ignored the
        agent turn reds here rather than passing over a hollow derivation.
        """
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            watch.apply_chat_turn(d, "c-pending", "human", "a pending chat")
            watch.apply_chat_turn(d, "c-replied", "human", "a replied chat")
            watch.apply_chat_turn(d, "c-replied", "agent", "the reply")
            data = watch.collect(d)
            by_id = {c["id"]: c for c in data["chats"]}
            self.assertEqual(set(by_id), {"c-pending", "c-replied"})
            # PRECONDITION: the two chats genuinely differ in status + turns
            self.assertNotEqual(by_id["c-pending"]["status"],
                                by_id["c-replied"]["status"])
            self.assertEqual(by_id["c-pending"]["turns"], 1)
            self.assertEqual(by_id["c-replied"]["turns"], 2)
            # the derivation: pending has no agent turn; replied does
            self.assertEqual(by_id["c-pending"]["status"], "pending")
            self.assertEqual(by_id["c-replied"]["status"], "replied")

    def test_dashboard_renders_minimal_topic_chat_list(self):
        """#504 Q4 — chatList/chatRow render the minimal topic-chat list.

        Evaluated in node with stubbed esc/label so the assertion is on REAL
        rendered HTML, not source text. Production line: chatRow's status +
        preview + turn-count branch, and chatList's empty-guard (quiet when
        there are no chats, like reviews). The UI word is "topic chats" (Q2).
        """
        import subprocess, shutil
        node = shutil.which("node")
        if not node:
            self.skipTest("node not available — chatList render gate did NOT run")
        page = watch._get_page()
        # extract chatRow + chatList by brace-matching from chatRow's sig
        cs = page.index("function chatList(")
        depth = 0
        ce = None
        for i in range(cs, len(page)):
            if page[i] == "{":
                depth += 1
            elif page[i] == "}":
                depth -= 1
                if depth == 0:
                    ce = i + 1
                    break
        self.assertIsNotNone(ce, "could not extract chatRow/chatList")
        fns = page[page.index("function chatRow("):ce]
        script = (
            "const esc = t => String(t==null?'':t)"
            ".replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')"
            ".replace(/\"/g,'&quot;');\n"
            "const label = t => `<div class=\"label\">${t}</div>`;\n"
            + fns + "\n"
            "const cases = " + json.dumps([
                {"d": {"chats": []}, "name": "empty"},
                {"d": {"chats": [{"id": "c1", "status": "pending",
                  "preview": "ship #504?", "turns": 1}]}, "name": "pending"},
                {"d": {"chats": [{"id": "c2", "status": "replied",
                  "preview": "in review", "turns": 2}]}, "name": "replied"},
            ]) + ";\n"
            "console.log(JSON.stringify(cases.map(c => chatList(c.d))));\n"
        )
        proc = subprocess.run([node, "-e", script], capture_output=True,
                              text=True, timeout=10)
        if proc.returncode != 0:
            self.fail("node eval failed: " + proc.stderr)
        empty, pending, replied = json.loads(proc.stdout)
        # empty -> "" (quiet, like reviews)
        self.assertEqual(empty, "", empty)
        # pending -> the topic-chats label + the pending status + preview
        self.assertIn("topic chats", pending)
        self.assertIn("pending", pending)
        self.assertIn("ship #504?", pending)
        # replied -> the status word + the reply's preview (last turn)
        self.assertIn("replied", replied)
        self.assertIn("in review", replied)
        # PRECONDITION that the two statuses render distinctly (else a single
        # branch could satisfy both): pending contains 'pending' not 'replied'
        self.assertNotIn("replied", pending, pending)

    def test_build_dashboard_calls_chat_list(self):
        """#504 Q4 — buildDashboard wires chatList into the dashboard.

        Production line: the `h += chatList(d);` STATEMENT in buildDashboard.
        Asserted line-anchored (not a bare substring) so commenting the call
        out — which leaves the text `chatList(d)` inside a `/* … */` — still
        reds. A substring check passed over a commented-out call (found by the
        red-proof), which is the hollow-trap this anchor exists to close.
        Removing it stops the surface rendering entirely.
        """
        page = watch._get_page()
        m = re.search(r"function buildDashboard\(d\) \{", page)
        self.assertTrue(m, "buildDashboard not in shell")
        body = page[m.start():m.start() + 4000]
        # an ACTIVE statement: a line whose non-whitespace begins with
        # `h += chatList(d);` — a `/* h += chatList(d); */` comment does not.
        self.assertRegex(body, r"(?m)^[ \t]*h \+= chatList\(d\);")

    def test_question_update_stamp_is_per_entry_not_file_mtime(self):
        # #473 — "updated" means THIS entry's content changed after first
        # sight, not that questions.md was rewritten (a neighbour's answer
        # rewrites the same file). Derive the precondition at runtime: first
        # collect has updated_at None; after a body rewrite the same entry
        # has a stamp; a second entry left alone still has None.
        #
        # PRODUCTION LINE whose change reds this: track_question_updates's
        # digest-compare branch (or _entry_content_digest omitting body).
        # Deleting the body field from the digest payload makes a rewrite
        # invisible and leaves updated_at None.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            qpath = os.path.join(d, ".dreamwork", "questions.md")
            base = (
                "# Questions for the human\n\n## Open\n\n"
                "- **2026-07-01 — alpha entry**\n"
                "  alpha body original\n\n"
                "- **2026-07-01 — beta entry**\n"
                "  beta body stays\n\n"
                "## Answered\n"
            )
            with open(qpath, "w") as f:
                f.write(base)
            first = watch.collect(d)
            by = {e["title"]: e for e in first["questions_open"]}
            self.assertIn("2026-07-01 — alpha entry", by)
            self.assertIn("2026-07-01 — beta entry", by)
            # PRECONDITION: both are first-sight, no updated_at
            self.assertIsNone(by["2026-07-01 — alpha entry"].get("updated_at"))
            self.assertIsNone(by["2026-07-01 — beta entry"].get("updated_at"))
            # rewrite ONLY alpha
            with open(qpath, "w") as f:
                f.write(base.replace("alpha body original",
                                     "alpha body REWRITTEN " + str(time.time())))
            second = watch.collect(d)
            by2 = {e["title"]: e for e in second["questions_open"]}
            alpha_u = by2["2026-07-01 — alpha entry"].get("updated_at")
            beta_u = by2["2026-07-01 — beta entry"].get("updated_at")
            self.assertIsInstance(alpha_u, float)
            self.assertGreater(alpha_u, 0)
            # PRECONDITION derived: the two entries now differ on the stamp
            self.assertIsNone(beta_u,
                              "a neighbour rewrite must not stamp an untouched entry")
            self.assertNotEqual(alpha_u, beta_u)
            # event is best-effort; when the store can write, it is there
            log = os.path.join(d, ".dreamwork", "watch-events.log")
            with open(log, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("question-updated via watch:", text)
            self.assertIn("alpha entry", text)
            # third collect, no further change: stamp is stable
            third = watch.collect(d)
            by3 = {e["title"]: e for e in third["questions_open"]}
            self.assertEqual(
                by3["2026-07-01 — alpha entry"]["updated_at"], alpha_u)
            # only one event for the one change
            with open(log, encoding="utf-8") as f:
                lines = [ln for ln in f if "question-updated" in ln]
            self.assertEqual(len(lines), 1)

    def test_question_updated_ago_page_wiring(self):
        # #473 — structural: the display rides ages() + data-ut, reuses the
        # #456/#463 separator idiom, and arrives via revealQuestionUpdates.
        for token in ('const qUpdatedHtml =', 'data-ut=',
                      "querySelectorAll('.age.qup[data-ut]')",
                      "updated ' + s + ' ago",
                      'function revealQuestionUpdates',
                      'revealQuestionUpdates()'):
            self.assertIn(token, watch.PAGE)
        # pure text ages() — no transition on the digit flip
        self.assertIn(".age.qup", watch.PAGE)

    def test_the_dashboard_shows_pending_handoffs(self):
        # #381: a foreign session that lands work appends to handoffs.md; the
        # dashboard surfaces the pending count in the status panel so a
        # coordinator who skipped a tick still notices. The page reads the
        # FILE (a real reader), never a mirror of status.json — which is the
        # loop's own claim, not a report of landed work.
        # 1. the page wires the field into the status panel and surfaces it.
        self.assertIn("statusBlock(d.status, d.pending_handoffs)", watch.PAGE)
        self.assertIn("hand-off", watch.PAGE)
        # 2. collect() reads pending hand-offs from the file, hiding folded ones.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            dw = os.path.join(d, ".dreamwork")
            with open(os.path.join(dw, "handoffs.md"), "w") as f:
                f.write(
                    "# Hand-offs\n\n## Pending\n\n"
                    "- **#5** · landed `abc1234` · 2026-07-28 14:30 · by "
                    "dreamer-5 — the fix\n"
                    "- **#6** · landed `def5678` · 2026-07-28 14:31 · by "
                    "dreamer-6 — the fix 2\n\n"
                    "## Folded\n\n"
                    "- **#6** → folded (2026-07-28 14:35): moved to Recently "
                    "landed as `ghi9012`\n")
            data = watch.collect(d)
            ids = [h["id"] for h in data["pending_handoffs"]]
            self.assertEqual(ids, ["5"])  # #6 is folded -> consumed -> hidden
            self.assertEqual(data["pending_handoffs"][0]["sha"], "abc1234")
        # 3. absent file -> empty (a fresh target has none), not a crash.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            self.assertEqual(watch.collect(d)["pending_handoffs"], [])

    def test_git_tail_carries_a_machine_readable_time(self):
        # #132: the row's age ticks every second, so the TIME has to arrive as
        # a number. A page deriving it from what it displayed would be reading
        # its own output back.
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ,
                       GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x",
                       GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x",
                       GIT_AUTHOR_DATE="@1700000000 +0000",
                       GIT_COMMITTER_DATE="@1700000000 +0000")
            run = lambda *a: subprocess.run(  # noqa: E731
                ["git", "-C", d, *a], env=env, capture_output=True, check=True)
            run("init", "-q")
            # a subject carrying the separator the format uses, and spaces:
            # `%h %s` could not be taken apart again without guessing
            with open(os.path.join(d, "f"), "w") as f:
                f.write("x")
            run("add", "f")
            run("commit", "-q", "-m", "feat: a subject with spaces in it")
            rows = watch.git_tail(d)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["t"], 1700000000)
            self.assertEqual(rows[0]["subject"],
                             "feat: a subject with spaces in it")
            self.assertTrue(rows[0]["sha"])
            # and a non-repo is still the empty list, never a crash
            with tempfile.TemporaryDirectory() as e:
                self.assertEqual(watch.git_tail(e), [])

    def test_ledger_entry_rule_has_exactly_one_copy(self):
        # #142 reads the same file lint.py does, so "what counts as an entry"
        # must be ONE rule. The linter learned this today (3073055): it held a
        # wider copy of the priority-marker rule than the parser and blessed
        # three typos. Compared as a PATTERN, not by both finding the same
        # count on today's file — two different rules agree on most inputs.
        #
        # #331: the rule is now ONE core (`IDS_ONLY_SPAN`) shared by THREE
        # head readers — watch.LEDGER_ENTRY, lint.LEDGER_ID and
        # status_sync.LEDGER_HEAD — and the mention reader
        # (watch.LEDGER_COMBINED_MENTION) is built from the same core. This
        # test pins all of them; a fourth reader cannot be written wrong
        # without one of these assertions going red. Comparing patterns, never
        # "both find the same count on today's file" — that is exactly the
        # agreement-this-exists-to-catch.
        import lint
        import status_sync
        head = watch.LEDGER_ENTRY.pattern
        # All three heads share one pattern and one flags value.
        self.assertEqual(lint.LEDGER_ID.pattern, head)
        self.assertEqual(status_sync.LEDGER_HEAD.pattern, head)
        self.assertEqual(watch.LEDGER_ENTRY.flags, lint.LEDGER_ID.flags)
        self.assertEqual(watch.LEDGER_ENTRY.flags, status_sync.LEDGER_HEAD.flags)
        # Both surface forms are BUILT FROM the single core, not restated.
        core = watch.IDS_ONLY_SPAN
        self.assertEqual(head, rf"^- \*\*({core})\*\*")
        self.assertEqual(watch.LEDGER_COMBINED_MENTION.pattern,
                         rf"\*\*({core})\*\*")

    def test_ids_only_span_admits_three_joiners_and_rejects_prose(self):
        """#331: a span is ids-only or it is prose, and the distinction is the
        whole hazard. The core admits `/`, `+` and a blank run as joiners, and
        nothing else: comma is NOT a joiner (`**#392, #401**` is a prose list),
        a word after an id is prose (`**#96 stage 1**` is a section title), and
        a sub-id letter is prose (`**#392a**`). Each of these is in the live
        ledger and must stay inert at the pattern level — never relying on a
        column-0 or column-indent guard to save it.
        """
        core_re = rf"\*\*({watch.IDS_ONLY_SPAN})\*\*"
        mention = re.compile(core_re)
        # The three joiners that the live ledger uses and were lost (#331).
        self.assertEqual(mention.findall("**#5/#6**"), ["#5/#6"])
        self.assertEqual(mention.findall("**#121 #123**"), ["#121 #123"])
        self.assertEqual(mention.findall("**#157 + #222 + #223**"),
                         ["#157 + #222 + #223"])
        # Every hazard the brief names — all must land NOTHING.
        inert = [
            "**#96 stage 1**",                      # section title, not ids
            "**#392, #401, #405, #411, #412**",     # comma-joined prose list
            "**#388, #387 and #386**",              # comma + the word "and"
            "**#351 collides with this precisely**",  # id then prose
            "**#346's artifact was deliberately NOT marked `language-sql`**",
            "**#392a**",                            # a sub-id, not an id
            "**#501, #502**",                       # fictional test ids
        ]
        for span in inert:
            self.assertEqual(mention.findall(span), [],
                             f"inert span matched (must land nothing): {span!r}")
        # Comma is explicitly not a joiner — assert it as its own case, because
        # admitting a comma is the easiest widening to reach for.
        self.assertEqual(mention.findall("**#392, #401**"), [],
                         "comma-joined span must stay inert at the pattern level")
        # #5, #501, #502 are prose/fictional ids the ledger documents as syntax
        # examples; they must never enter the landed set via a span match.
        self.assertEqual(mention.findall("**#5**"), ["#5"])
        self.assertEqual(mention.findall("**#501, #502**"), [])

    def test_live_ledger_recovers_the_nineteen_joined_ids(self):
        """#331: the live ledger writes 19 ids in space- and `+`-joined bold
        spans that the old `/`-only reader dropped entirely. Each must now be
        in the LANDED set (the spans live under `## Recently landed`), and the
        open set must be unchanged and disjoint.

        Membership is tested PER ID against parse_ledger's real landed set —
        not by re-deriving the spans with a second regex, which disagreed (it
        said 9). Per-id set membership is the authoritative test.
        """
        # Post-cutover (#294) `.dreamwork/tasks.md` is the #458 one-line shim
        # — no `## Recently landed`, no parseable entries. This test describes
        # the FROZEN Markdown ledger, so it reads tasks.md.deprecated, the
        # same repoint as 135c2e31's test_ledger_store.py repair.
        live = os.path.join(os.path.dirname(os.path.abspath(watch.__file__)),
                            ".dreamwork", "tasks.md.deprecated")
        if not os.path.exists(live):
            self.skipTest("no frozen .dreamwork/tasks.md.deprecated in this tree")
        with open(live, encoding="utf-8") as fh:
            text = fh.read()
        open_ids, landed = watch.parse_ledger(text)
        open_ids, landed = set(open_ids), set(landed)
        # The 19 ids the brief names, derived from the ledger's own joined
        # spans. Asserted as a set so a fixture change can't hollow the count.
        wanted = {"77", "102", "104", "106", "107", "108", "109", "110",
                  "116", "121", "123", "132", "141", "149", "151", "154",
                  "157", "222", "223"}
        missing = sorted(wanted - landed, key=int)
        self.assertEqual(missing, [],
                         f"#331 joined-span ids missing from landed: {missing}")
        # Disjointness: an id is open OR landed, never both.
        self.assertEqual(open_ids & landed, set(),
                         "open and landed are not disjoint")
        # The inert ids must NOT have leaked in via a too-greedy span.
        for bogus in ("5", "501", "502"):
            self.assertNotIn(bogus, landed,
                             f"#{bogus} entered landed — span too greedy")

    def test_parse_ledger_reads_both_of_the_files_two_shapes(self):
        # Both sections use entry HEADS (#399 retired prose-mention landing).
        # A bare bold in a landed body is a reference, not a second landing.
        text = ("# Task ledger\n\nNext id: **9**\n\n## Open\n\n"
                "- **#7** — a live one · P2 · task\n"
                "  - a continuation line mentioning **#99** in passing\n"
                "- **#8** — another · P3 · idea\n\n"
                "## Recently landed\n\n"
                "- **#5** — did a thing · landed `abc1234` (2026-07-25)\n"
                "- **#6** — did another · landed `def5678`\n")
        openids, landed = watch.parse_ledger(text)
        self.assertEqual(openids, {"7", "8"})
        self.assertEqual(landed, {"5", "6"})
        # a sub-bullet is not an entry, or a mention inside one would mint a
        # task that never existed
        self.assertNotIn("99", openids)
        self.assertEqual(watch.parse_ledger(""), (set(), set()))
        self.assertEqual(watch.parse_ledger("no sections here"), (set(), set()))

    def test_an_entry_quoting_a_section_heading_cannot_move_the_split(self):
        """#304: the sections are STRUCTURE, so only a heading LINE names one.

        `parse_ledger` used to locate both sections with an unanchored
        `str.split` on the heading text, so an entry body that quoted a
        heading became the split point. This is not hypothetical and it is
        not adversarial input: it happened twice in ten minutes while
        writing ledger entries ABOUT this very parser, and the second time
        was the entry that filed the bug. The whole ledger misread — 2 open
        / 187 landed against a true 105 / 84 — and every number derived from
        it on the deployed dashboard was wrong, silently, with `lint.py`
        reporting the file clean throughout.

        Both directions matter. A quote ABOVE the real landed heading steals
        the split (the open section is truncated to nothing); a quote in the
        open section at all must be inert.
        """
        # Built by concatenation so THIS FILE never contains the literal
        # heading sequences either — the same trap one layer up.
        OPEN, LANDED = "## " + "Open", "## " + "Recently landed"
        text = ("# Task ledger\n\nNext id: **9**\n\n" + OPEN + "\n\n"
                "- **#7** — a live one · P2 · task\n"
                "  · quoting `" + LANDED + "` and `" + OPEN + "` in prose,\n"
                "    exactly as an entry describing this parser must\n"
                "- **#8** — another · P3 · idea\n\n"
                + LANDED + "\n\n"
                "- **#5** — did a thing · landed `abc1234`\n"
                "- **#6** — did another · landed `def5678`\n")
        openids, landed = watch.parse_ledger(text)
        # RED before the fix: openids == set() and landed swallowed #7/#8,
        # because the split landed inside #7's body.
        self.assertEqual(openids, {"7", "8"},
                         "an entry's prose re-sectioned the ledger")
        self.assertEqual(landed, {"5", "6"},
                         "landed set polluted by open-section entries")
        # And the heading must still be found when it is a real line, so the
        # anchor cannot have been achieved by simply failing to match.
        self.assertEqual(watch.parse_ledger(text.replace(LANDED + "\n\n", ""))[1],
                         set(), "no landed section should mean no landed ids")

    def test_parse_ledger_lands_every_id_in_a_combined_head(self):
        """#301 (landed half, post-#399): a combined ENTRY HEAD lands every id.

        Pre-#399 this was a bare combined *mention* (`**#5/#6**`); #399 makes
        landing explicit via heads / also-landed, so the multi-id case is the
        combined head `- **#5/#6**` (same atom as open). Narrow LEDGER_MENTION
        still misses the combined form — pinned so that defect stays real.
        """
        COMBINED_HEAD = "- **#5/#6**"
        text = ("# Task ledger\n\nNext id: **9**\n\n## Open\n\n"
                "- **#9** — a singular live one · P3 · idea\n\n"
                "## Recently landed\n\n"
                + COMBINED_HEAD + " — did two things · landed `abc1234`\n"
                "- **#2** — did another · landed `def5678`\n")
        self.assertIn(COMBINED_HEAD, text,
                      "fixture must hold a combined head to land")
        self.assertEqual(watch.LEDGER_MENTION.findall("**#5/#6**"), [],
                         "narrow LEDGER_MENTION misses the combined form")
        _openids, landed = watch.parse_ledger(text)
        self.assertEqual(landed, {"2", "5", "6"},
                         "a combined landed head lands every id it names")

    def test_parse_ledger_ignores_a_prose_span_that_only_references_an_id(self):
        """#301/#399: a bold prose span is a REFERENCE, not a landing.

        `**#96 stage 1**` is not ids-only; a bare `**#96**` in prose after a
        real head is also a reference under #399 (not only the stage-1 form).
        """
        text = ("# Task ledger\n\nNext id: **9**\n\n## Open\n\n"
                "- **#9** — open\n\n"
                "## Recently landed\n\n"
                "- **#5** — landed `abc1234`. The **#96 stage 1** dreamhub "
                "work relates.\n")
        self.assertIn("**#96 stage 1**", text,
                      "fixture must hold a prose-reference span to ignore")
        _openids, landed = watch.parse_ledger(text)
        self.assertEqual(landed, {"5"},
                         "a prose span referencing an id does not land it")

    def test_a_bare_bolded_id_in_a_landed_entry_is_not_landed(self):
        """#399: `filed as **#392**` / `related: **#367**` do not land the id.

        Pre-fix, LEDGER_COMBINED_MENTION scanned every ids-only bold span in
        `## Recently landed`, so a related marker or prose bare bold put an
        still-open task into the landed set — the exact defect that made
        check_landed_asks tell the coordinator to fold #367's open ask.
        """
        text = ("# Task ledger\n\nNext id: **400**\n\n## Open\n\n"
                "- **#367** — still open · P1 · origin: **human**\n"
                "- **#392** — still open · P2 · origin: **loop**\n\n"
                "## Recently landed\n\n"
                "- **#395** — explicit field · origin: **loop** · related: "
                "**#367, #392** · filed as **#399** in the same class · "
                "landed `abc1234`\n")
        # Precondition: the fixture really holds bare bold ids that the old
        # scanner would land, and those ids are open.
        self.assertIn("related: **#367, #392**", text)
        self.assertIn("filed as **#399**", text)
        self.assertIn("**#399**", text)
        openids, landed = watch.parse_ledger(text)
        self.assertEqual(openids, {"367", "392"})
        self.assertEqual(landed, {"395"},
                         "related: and filed-as bare bolds must not land")
        self.assertNotIn("367", landed)
        self.assertNotIn("392", landed)
        self.assertNotIn("399", landed)

    def test_a_landed_entry_head_is_landed(self):
        """#399: the entry head is what marks a task landed."""
        text = ("# Task ledger\n\nNext id: **10**\n\n## Open\n\n"
                "- **#9** — open\n\n"
                "## Recently landed\n\n"
                "- **#5** — shipped · landed `abc1234`\n"
                "- **#7/#8** — combined multi-close · landed `def5678`\n")
        _open, landed = watch.parse_ledger(text)
        self.assertEqual(landed, {"5", "7", "8"})

    def test_also_landed_field_lands_additional_ids(self):
        """#399: multi-close without a combined head uses also-landed:."""
        text = ("# Task ledger\n\nNext id: **10**\n\n## Open\n\n"
                "- **#9** — open\n\n"
                "## Recently landed\n\n"
                "- **#5** — closed two · origin: **loop** · also-landed: "
                "**#6, #7** · landed `abc1234`\n"
                "  · related: **#9** is a reference, not a landing\n")
        self.assertIn("also-landed: **#6, #7**", text)
        self.assertIn("related: **#9**", text)
        _open, landed = watch.parse_ledger(text)
        self.assertEqual(landed, {"5", "6", "7"},
                         "also-landed lands extra ids; related: does not")
        self.assertNotIn("9", landed)

    def test_also_landed_mid_sentence_is_not_a_field(self):
        """#399 / #395 class: unanchored prose must not claim the field."""
        text = ("# Task ledger\n\nNext id: **10**\n\n## Open\n\n"
                "- **#9** — open\n\n"
                "## Recently landed\n\n"
                "- **#5** — the form is also-landed: **#6** mid-sentence and "
                "must not mint a landing · landed `abc1234`\n")
        # Precondition: the old unanchored pattern would match.
        unanchored = re.compile(r"also-landed:\s*\*\*([^*]*?)\*\*", re.I)
        self.assertTrue(unanchored.search(text),
                        "fixture must hold the mid-sentence phrase")
        self.assertFalse(
            watch.ALSO_LANDED_MARKER.search(
                "the form is also-landed: **#6** mid-sentence"),
            "field anchor must refuse mid-sentence prose")
        _open, landed = watch.parse_ledger(text)
        self.assertEqual(landed, {"5"})
        self.assertNotIn("6", landed)

    # ── #399b: the historical inline landed form, which #399 lost ──────────
    # The burndown guard caught the regression and these unit tests did not,
    # which is why it reached master. They feed `_landed_ids` the shapes the
    # history walk (`ledger_series`) meets in old revisions, where the landed
    # section was inline prose — not entry heads — so every column-0 mention
    # is a landing and the indented body / reference-field guards must not
    # touch them.

    def test_a_historical_inline_mention_lands(self):
        """#399b: the pre-entry-head landed form is `**#N** <prose> (sha)`,
        a column-0 paragraph. `ledger_series` walks these old revisions, so a
        landed reader that misses them makes the burndown lose every
        completion older than the last groom — exactly how #399 re-reddened
        master. The inline mention must land."""
        text = ("# Task ledger\n\nNext id: **10**\n\n## Open\n\n"
                "- **#9** — still open\n\n"
                "## Recently landed\n\n"
                "**#1** landed (aaa1111). **#2** landed (aaa1112).\n")
        # Precondition: neither id is an entry head, so #399's entry-heads-
        # only rule read ZERO landings here — the regression this test pins.
        self.assertNotIn("- **#1**", text)
        self.assertNotIn("- **#2**", text)
        _open, landed = watch.parse_ledger(text)
        self.assertEqual(landed, {"1", "2"},
                         "the historical inline form must land its ids")

    def test_a_historical_one_line_multi_mention_lands_every_id(self):
        """#399b: history packed several landings on one column-0 line
        (`**#101** …, **#97** …`), and the burndown fixture joins its
        landings with a space for the same reason. A mention that is not at
        the start of its line still lands, because the line itself begins at
        column 0."""
        landed = watch._landed_ids(
            "## Recently landed\n\n"
            "**#101** scrollbar styling (2026-07-25), **#97** durable ledger\n")
        self.assertEqual(landed, {"101", "97"})

    def test_a_related_marker_does_not_land_even_at_column_zero(self):
        """#399b: #367's hole stays closed. A `related:` or `filed as`
        marker written on a ONE-LINE head sits at column 0, so the
        indented-body guard alone would not exclude it — the reference-field
        guard (LANDED_REF_FIELD) is what does. This is the load-bearing case
        for that guard and the third discriminating red."""
        text = ("## Recently landed\n\n"
                "- **#395** — x · related: **#367** · filed as **#392** · "
                "landed `abc`\n")
        landed = watch._landed_ids(text)
        self.assertEqual(landed, {"395"})
        self.assertNotIn("367", landed)
        self.assertNotIn("392", landed)

    def test_an_indented_body_prose_reference_does_not_land(self):
        """#399b: a cross-ref in an entry's INDENTED body ('see **#N**',
        'corrected (**#N**)') is a reference, not a landing. Counting it
        would put an open id into the landed set — #367's class of bug — and
        break open/landed disjointness on the live ledger. This is the
        load-bearing case for the indented-body guard."""
        text = ("## Recently landed\n\n"
                "- **#5** — shipped · landed `abc`\n"
                "  · see **#9** which is still open, and found **#8**\n"
                "  · corrected (**#7**) in the same pass\n")
        landed = watch._landed_ids(text)
        self.assertEqual(landed, {"5"})
        for ref in ("7", "8", "9"):
            self.assertNotIn(ref, landed)

    def test_an_empty_landed_section_lands_nothing(self):
        """#399b neighbour: a revision whose landed section is empty — the
        first commits of any ledger — lands nothing, without raising."""
        self.assertEqual(watch._landed_ids(""), set())
        self.assertEqual(watch._landed_ids("## Recently landed\n\n"), set())

    def test_a_combined_head_and_inline_combined_each_land_every_id(self):
        """#399b neighbour: a combined head (`- **#7/#8**`) and a combined
        inline mention (`**#7/#8** …`) each land BOTH ids — the historical
        walk meets the inline combined form."""
        self.assertEqual(
            watch._landed_ids("## Recently landed\n\n- **#7/#8** — x\n"),
            {"7", "8"})
        self.assertEqual(
            watch._landed_ids(
                "## Recently landed\n\n**#7/#8** the thing (sha)\n"),
            {"7", "8"})

    def test_an_id_both_a_head_and_mentioned_inline_lands_once(self):
        """#399b neighbour: an id that is an entry head AND named again in an
        inline summary lands once (a set), not twice; the inline repeat is
        idempotent, not additive."""
        text = ("## Recently landed\n\n"
                "- **#5** — shipped · landed `abc`\n"
                "**#5** also appears in an old summary (abc)\n")
        self.assertEqual(watch._landed_ids(text), {"5"})

    def test_the_real_ledger_has_no_id_both_open_and_landed(self):
        """#399: open ∩ landed is empty on the real ledger, measured at runtime.

        Precondition: both sections non-empty, or the disjointness assert is
        vacuous the day the ledger is empty. Overlap count is reported so a
        silent reintroduction of mention-scanning cannot pass without naming
        how many ids it re-polluted.
        """
        # Post-cutover (#294) `.dreamwork/tasks.md` is the #458 shim — empty
        # of entries, so the disjointness precondition below would fail
        # vacuously against it. The frozen Markdown ledger this test describes
        # is tasks.md.deprecated (same repoint as 135c2e31).
        path = os.path.join(os.path.dirname(watch.__file__),
                            ".dreamwork", "tasks.md.deprecated")
        self.assertTrue(os.path.isfile(path), f"frozen ledger missing at {path}")
        text = open(path, encoding="utf-8").read()
        open_ids, landed_ids = watch.parse_ledger(text)
        self.assertGreater(len(open_ids), 0,
                           "precondition: real ledger has open ids")
        self.assertGreater(len(landed_ids), 0,
                           "precondition: real ledger has landed ids")
        both = open_ids & landed_ids
        self.assertEqual(
            both, set(),
            f"{len(both)} id(s) in BOTH open and landed sets: "
            f"{sorted(both, key=lambda x: int(x) if x.isdigit() else x)}")

    def test_open_combined_head_reads_every_id_now_that_lint_widens_in_step(self):
        """#315 (the open half of #301, no longer deferred): a combined entry
        HEAD under `## Open` (`- **#7/#8**`) now reads EVERY id it names.
        The narrow LEDGER_ENTRY required `**` right after a single digit run
        and matched NEITHER half — verified directly against the regex below —
        so parse_ledger dropped both ids and the dashboard silently lost two
        tasks.

        This cannot be fixed in parse_ledger alone: lint.check_ledger_sections
        cross-checks `len(parse_ledger(open))` against its OWN open-id count,
        which uses LEDGER_ID — pinned identical to LEDGER_ENTRY. Widening one
        reader makes the two DISAGREE on any ledger holding a combined open
        entry (a previous agent watched test_combined_ids_all_old_are_exempt
        go red proving exactly that). So LEDGER_ENTRY, LEDGER_ID and
        check_ledger_sections widen in ONE commit. This guard exists so the
        lockstep is loud: narrow parse_ledger's open read again without
        lint.py and THIS test goes red before test_lint.py does.

        The runtime precondition asserts the fixture head genuinely carries
        TWO DISTINCT ids — both are derived from the fixture, never hardcoded,
        because a literal pair is true only of today's fixture and a future
        edit that collapsed them to one would pass vacuously.
        """
        COMBINED_HEAD = "- **#7/#8**"
        text = ("# Task ledger\n\nNext id: **9**\n\n## Open\n\n"
                + COMBINED_HEAD + " — a combined live one · P2 · task\n"
                "- **#9** — a singular live one · P3 · idea\n\n"
                "## Recently landed\n\n")
        self.assertIn(COMBINED_HEAD, text,
                      "fixture must hold a combined head to read")
        # Precondition is a property of the FIXTURE, not the pattern under
        # test, so derive both ids straight from the head string: the case is
        # only combined if there are two distinct ids. A literal pair would
        # be true only of today's fixture and a future edit that collapsed
        # them to one would pass vacuously.
        head_ids = watch.ENTRY_ID.findall(COMBINED_HEAD)
        self.assertEqual(len(head_ids), 2,
                         "fixture head must carry two ids to be combined")
        self.assertNotEqual(head_ids[0], head_ids[1],
                            "the two ids must differ or the case is singular")
        # Pin the WIDENED capture: a future narrowing of LEDGER_ENTRY turns
        # this assertion (and so this test) red.
        self.assertEqual(watch.LEDGER_ENTRY.findall(COMBINED_HEAD), ["#7/#8"],
                         "widened LEDGER_ENTRY captures the combined id span")
        openids, _landed = watch.parse_ledger(text)
        # RED before the fix: openids == {"9"} — the combined head contributed
        # neither id it named, and the dashboard silently lost two tasks.
        self.assertEqual(openids, {"7", "8", "9"},
                         "a combined open head reads every id it names")

    def _ledger_repo(self, d, snapshots):
        """Commit each `(text, when)` as .dreamwork/tasks.md. Returns the run
        helper so a caller can keep going."""
        import subprocess
        dw = os.path.join(d, ".dreamwork")
        os.makedirs(dw, exist_ok=True)
        base = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x",
                    GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
        subprocess.run(["git", "-C", d, "init", "-q"], env=base, check=True,
                       capture_output=True)
        for i, (text, when) in enumerate(snapshots):
            env = dict(base, GIT_AUTHOR_DATE="@%d +0000" % when,
                       GIT_COMMITTER_DATE="@%d +0000" % when)
            with open(os.path.join(dw, "tasks.md"), "w") as f:
                f.write(text)
            subprocess.run(["git", "-C", d, "add", ".dreamwork/tasks.md"],
                           env=env, check=True, capture_output=True)
            subprocess.run(["git", "-C", d, "commit", "-q", "-m", "ledger %d" % i],
                           env=env, check=True, capture_output=True)

    def test_ledger_series_counts_arrivals_and_completions(self):
        # #142. The open count alone cannot tell "he steers fast" from "the
        # work is slow" — they are the same curve — so both series are
        # derived and neither is summed into a score.
        LED = "## Open\n\n{open}\n## Recently landed\n\n{done}\n"
        entry = "- **#{i}** — task {i} · P2 · task\n"
        T = 1784900000
        watch._LEDGER_SNAPS.clear()
        with tempfile.TemporaryDirectory() as d:
            self._ledger_repo(d, [
                # t=0h: #1 #2 arrive
                (LED.format(open=entry.format(i=1) + entry.format(i=2),
                            done=""), T),
                # t=1h: #3 arrives, #1 lands
                (LED.format(open=entry.format(i=2) + entry.format(i=3),
                            done="- **#1** — did it · landed `aaa1111`\n"),
                 T + 3600),
                # t=2h: #2 lands, and #1 is GROOMED OUT of the landed section
                (LED.format(open=entry.format(i=3),
                            done="- **#2** — did it · landed `bbb2222`\n"),
                 T + 7200),
            ])
            r = watch.ledger_series(d, now=T + 7200)
            self.assertEqual(r["state"], watch.BURN_OK)
            self.assertEqual(r["arrived"], 3)
            # THE LOAD-BEARING ONE: #1 was pruned from the landed section by
            # grooming, and a completion read from the CURRENT contents would
            # have lost it. Arrival and completion are first-seen events.
            self.assertEqual(r["landed"], 2)
            self.assertEqual(r["open"], 1)
            self.assertEqual(r["step"], 3600)
            self.assertEqual([b["arrived"] for b in r["buckets"]], [2, 1, 0])
            self.assertEqual([b["landed"] for b in r["buckets"]], [0, 1, 1])
            # the open count is a LEVEL, not a count of events
            self.assertEqual([b["open"] for b in r["buckets"]], [2, 2, 1])
            # #417: ledger-touching commits per period — one rev per fixture
            # commit, so each non-empty hour that received a ledger commit
            # counts 1. The three revs land in buckets 0, 1, 2.
            self.assertEqual([b["commits"] for b in r["buckets"]], [1, 1, 1],
                             "each ledger rev is one commit in its bucket")
            self.assertEqual(r["commit_total"], 3)
            self.assertEqual(r["commit_max"], 1)
            self.assertEqual(r["commit_median"], 1)
            self.assertEqual(r["commit_quiet"], 0)

    def test_ledger_series_counts_commits_per_period(self):
        """#417. Commits-per-period is the same revs walk, not a second one.

        A quiet hour between two ledger commits must read 0 commits, not
        inherit the previous count — commits are events, unlike open which
        is a level. Peak / median / quiet are derived over the buckets the
        chart draws, so the c4 copy line cannot invent numbers.
        """
        LED = "## Open\n\n{open}\n## Recently landed\n\n{done}\n"
        entry = "- **#{i}** — task {i} · P2 · task\n"
        T = 1784900000
        watch._LEDGER_SNAPS.clear()
        with tempfile.TemporaryDirectory() as d:
            # three revs: t=0, t=2h, t=2h+ε is not possible in one step —
            # two revs in the first hour requires two commits in that hour.
            # Plant: hour0 has 2 commits (two revs inside the hour), hour1
            # is quiet (no rev), hour2 has 1.
            self._ledger_repo(d, [
                (LED.format(open=entry.format(i=1), done=""), T),
                (LED.format(open=entry.format(i=1) + entry.format(i=2),
                            done=""), T + 600),           # still hour 0
                # content must change or git refuses the commit; #3 arrives
                # in hour 2 so the middle hour stays quiet
                (LED.format(open=entry.format(i=1) + entry.format(i=2) +
                            entry.format(i=3), done=""), T + 2 * 3600),
            ])
            r = watch.ledger_series(d, now=T + 2 * 3600)
            self.assertEqual(r["state"], watch.BURN_OK)
            commits = [b["commits"] for b in r["buckets"]]
            # precondition: the planted shape really is 2, 0, 1 — a flat
            # list would make peak/quiet/median assertions vacuous.
            self.assertEqual(commits, [2, 0, 1],
                             "events per bucket, not a carried level")
            self.assertNotEqual(commits[0], commits[1],
                                "quiet hour must differ from the busy one")
            self.assertEqual(r["commit_total"], 3)
            self.assertEqual(r["commit_max"], 2)
            self.assertEqual(r["commit_quiet"], 1)
            # median of [0,1,2] = 1
            self.assertEqual(r["commit_median"], 1)

    def test_burndown_inspector_page_wiring(self):
        # #298 — structural: the column inspector rides #417's seam (same
        # data attributes, same arrival idiom), carries the interval and
        # coverage state the glance tip does not, and is reachable by
        # dwell, focus and tap with Escape/scroll dismissal. The exact
        # values are the browser guard's job (dev/capture/bdhover.mjs);
        # this pins the wiring that guard depends on.
        for token in ('class="bdinsp" hidden role="status"',
                      'data-t0="${b.t0}" data-t1="${b.t0 + s.step}"',
                      'data-covered="${c > 0 ? 1 : 0}"',
                      'function bdinspHTML(col)',
                      'function bdinspLay(bd, col, el)',
                      'function showBdInsp(col',
                      'function hideBdInsp(immediate)',
                      "'level carried — no ledger commits'",
                      "'period in progress'",
                      'bdinspSchedule(col)',
                      "e.key === 'Escape' && bdinspCol"):
            self.assertIn(token, watch.PAGE)
        # #487: pin is RHS-or-above from rendered widths (see
        # test_burndown_insp_pins_rhs_or_above), not column-centred.
        self.assertIn("el.dataset.bdslot", watch.PAGE)
        # hover is not the sole path: focus shows the same inspector,
        # tap pins without preventDefault (chart scroll unbroken)
        self.assertIn("showBdTip(col);\n  showBdInsp(col);", watch.PAGE)
        self.assertIn("bdinspPin = true; showBdInsp(col);", watch.PAGE)
        # reduced-motion parity: the inspector declares the same media rule
        self.assertIn(".bdinsp { transition:none; }", watch.PAGE)
        self.assertIn(".bdinsp.pose", watch.PAGE)
        self.assertIn(".bdinsp.depart", watch.PAGE)
        # #494: hover/pin survive the live tick's innerHTML swap — snapshot
        # before setLiveContent, restore after; settle avoids re-posing.
        for token in ('function snapshotBdHover',
                      'function restoreBdHover',
                      'restoreBdHover(bdHover)',
                      'showBdTip(col, settle)',
                      'showBdInsp(col, settle)'):
            self.assertIn(token, watch.PAGE)
        # both re-render seams carry the hover (tick + step cycle)
        self.assertGreaterEqual(watch.PAGE.count('restoreBdHover(bdHover)'), 2)

    def test_burndown_step_cycle_control_wiring(self):
        # #487 — the granularity label is a cycle control: affordance,
        # keyboard, announced state. Granularities are the ladder already
        # in BURN_STEPS / BURN_STEP_NAME, never a second list.
        for token in ('class="bdstep"',
                      'function cycleBurnStep',
                      'BURN_STEP_ORDER',
                      "role=\"button\"",
                      'aria-label',
                      "burn_step="):
            self.assertIn(token, watch.PAGE)
        # every server ladder step is named and cycled — derive from the
        # server constant so a new BURN_STEPS entry cannot go dark
        for sec in watch.BURN_STEPS:
            self.assertIn(str(sec), watch.PAGE)
            self.assertIn(str(sec),
                          str(getattr(watch, 'BURN_STEPS', ())))
        # the head's step name is the control, not bare prose
        self.assertIn('bdstep', watch.PAGE)
        self.assertRegex(watch.PAGE,
                         r'bdstep[^>]*(role="button"|tabindex)')

    def test_burndown_cycle_direction_wiring(self):
        # #489 — plain click walks coarse→fine (his order: daily →
        # 4-hourly → hourly → wrap to every-four-weeks); shift-click
        # reverses. The click handler must hand the modifier to the
        # cycle; bdhover owns the behavioural walk.
        self.assertIn('function cycleBurnStep(back)', watch.PAGE)
        self.assertIn('cycleBurnStep(e.shiftKey)', watch.PAGE)

    def test_ledger_series_honours_a_forced_step(self):
        # #487 — cycling needs a step the auto ladder would not pick.
        # A ~2h ledger auto-picks hourly; forcing daily must re-bucket.
        LED = "## Open\n\n{open}\n## Recently landed\n\n{done}\n"
        entry = "- **#{i}** — task {i} · P2 · task\n"
        T = 1784900000
        watch._LEDGER_SNAPS.clear()
        with tempfile.TemporaryDirectory() as d:
            self._ledger_repo(d, [
                (LED.format(open=entry.format(i=1), done=""), T),
                (LED.format(open=entry.format(i=1) + entry.format(i=2),
                            done=""), T + 3600),
                (LED.format(open=entry.format(i=2),
                            done="- **#1** — x · landed `aaa1111`\n"),
                 T + 7200),
            ])
            auto = watch.ledger_series(d, now=T + 7200)
            forced = watch.ledger_series(d, now=T + 7200, step=86400)
            # precondition: auto really is finer than the forced step, so
            # a no-op step= param would make the length check vacuous
            self.assertEqual(auto["step"], 3600,
                             "fixture span must auto-pick hourly")
            self.assertLess(auto["step"], 86400)
            self.assertGreater(len(auto["buckets"]), 1)
            self.assertEqual(forced["step"], 86400)
            self.assertLess(len(forced["buckets"]), len(auto["buckets"]))
            # same totals — rebucket, not a second walk of history
            self.assertEqual(forced["arrived"], auto["arrived"])
            self.assertEqual(forced["landed"], auto["landed"])

    def test_burndown_no_native_column_title(self):
        # #487 — one hover surface: wherever .bdtip/.bdinsp exist, the
        # native title= tooltip on the same column is gone.
        # Find the column template emission (data-open is level-track only).
        idx = watch.PAGE.find('data-open="${b.open}"')
        self.assertGreater(idx, 0, "level-track column template missing")
        # window around the column open-tag: no title= on that element
        window = watch.PAGE[idx - 200:idx + 400]
        self.assertIn('class="bdcol"', window)
        # the native tooltip was `title="${esc(title)}"` on the same tag
        self.assertNotRegex(window, r'<div class="bdcol"[^>]*\btitle=')

    def test_burndown_insp_pins_rhs_or_above(self):
        # #487 — consistent pin: RHS when room (measured from layout),
        # above chart+tip when not. Never follows the column centre.
        self.assertIn('function bdinspLay(bd, col, el)', watch.PAGE)
        # Slice to the next function declaration, never a fixed char window:
        # a +900 literal covered less than half of bdinspLay once #498's
        # geometry fix lengthened it, and the check failed on truncation,
        # not on the placement it names (the repo's tuned-literal lesson).
        start = watch.PAGE.index('function bdinspLay')
        end = watch.PAGE.index('\nfunction ', start + 1)
        lay = watch.PAGE[start:end]
        self.assertGreater(len(lay), 900,
                           "slice must beat the old fixed window — a shorter "
                           "one risks re-tuning the literal that just failed")
        # room is derived from rendered widths, not a guessed px breakpoint
        self.assertIn('offsetWidth', lay)
        self.assertIn('bdr.width', lay)
        # two placements: right-hand side, and above (including the tip)
        self.assertTrue('right' in lay.lower() or 'bdr.width - w' in lay,
                        "RHS placement missing from bdinspLay")
        self.assertIn('bdtip', lay)
        # old centre-on-column clamp is gone (consistent pin replaces it)
        self.assertNotIn('cx - w / 2', lay)

    def test_ledger_series_lands_every_id_in_a_combined_head(self):
        """#301/#399: ledger_series counts a combined landed HEAD as two ids.

        Pre-#399 the fixture was a bare combined mention; after #399 landing
        is heads / also-landed only, so the multi-id case is `- **#2/#3**`.
        """
        LED = "## Open\n\n{open}\n## Recently landed\n\n{done}\n"
        T = 1784900000
        one_open = "- **#1** — one · P2 · task\n"
        t0 = LED.format(open=one_open, done="")
        t1 = LED.format(open=one_open,
                        done="- **#2/#3** — did it together · landed `abc1234`\n")
        self.assertIn("- **#2/#3**", t1,
                      "fixture must hold a combined head to land")
        watch._LEDGER_SNAPS.clear()
        with tempfile.TemporaryDirectory() as d:
            self._ledger_repo(d, [(t0, T), (t1, T + 3600)])
            r = watch.ledger_series(d, now=T + 3600)
            self.assertEqual(r["state"], watch.BURN_OK)
            self.assertEqual(r["arrived"], 3, "the combined ids arrived")
            self.assertEqual(r["landed"], 2,
                             "a combined head lands every id it names")
            self.assertEqual(r["open"], 1)

    def test_ledger_series_carries_a_level_across_an_empty_bucket(self):
        # a bucket with no ledger commit in it inherits the last reading. The
        # alternative renders a quiet hour as a drop to zero open tasks,
        # which is a lie the shape of the chart makes convincing.
        LED = "## Open\n\n- **#1** — one · P2 · task\n\n## Recently landed\n\n"
        T = 1784900000
        watch._LEDGER_SNAPS.clear()
        with tempfile.TemporaryDirectory() as d:
            self._ledger_repo(d, [(LED, T), (LED + "\n", T + 4 * 3600)])
            r = watch.ledger_series(d, now=T + 4 * 3600)
            self.assertEqual(len(r["buckets"]), 5)
            self.assertEqual([b["open"] for b in r["buckets"]], [1, 1, 1, 1, 1])
            self.assertEqual(sum(b["arrived"] for b in r["buckets"]), 1)

    def test_ledger_series_widens_its_bucket_rather_than_its_chart(self):
        # a fixed step gives one column on a young ledger and four hundred on
        # an old one. The step is the smallest on the ladder that keeps the
        # chart under BURN_COLUMNS.
        LED = "## Open\n\n- **#1** — one · P2 · task\n\n## Recently landed\n\n"
        T = 1784900000
        for span, step in ((6 * 3600, 3600), (40 * 3600, 4 * 3600),
                           (20 * 86400, 86400), (100 * 86400, 7 * 86400)):
            watch._LEDGER_SNAPS.clear()
            with tempfile.TemporaryDirectory() as d:
                self._ledger_repo(d, [(LED, T), (LED + "\n", T + span)])
                r = watch.ledger_series(d, now=T + span)
                self.assertEqual(r["step"], step, "span %ds" % span)
                self.assertLessEqual(len(r["buckets"]), watch.BURN_COLUMNS)

    def test_ledger_series_says_which_kind_of_nothing(self):
        # "no ledger" and "git broke" are different things to tell a human,
        # and only one of them means the loop has nothing to show.
        with tempfile.TemporaryDirectory() as d:
            r = watch.ledger_series(d)
            self.assertEqual(r["state"], watch.BURN_NONE)
            self.assertIn("not a git checkout", r["note"])
        with tempfile.TemporaryDirectory() as d:
            self._ledger_repo(d, [])
            import subprocess
            with open(os.path.join(d, "other"), "w") as f:
                f.write("x")
            env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x",
                       GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
            subprocess.run(["git", "-C", d, "add", "other"], env=env,
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", d, "commit", "-q", "-m", "no ledger"],
                           env=env, check=True, capture_output=True)
            r = watch.ledger_series(d)
            self.assertEqual(r["state"], watch.BURN_NONE)
            self.assertIn("nothing to chart", r["note"])
            self.assertEqual(r["buckets"], [])

    def test_ledger_series_median_is_over_the_landed_intersection(self):
        """#218. The median is over the ids that have BOTH a first sighting
        and a first landing — the work that FINISHED. An id still open has
        no duration, so it is excluded; the renderer's label must be able to
        rely on median_n being the size of that intersection, not the
        arrival count. A median that folds unlanded ids in as zero-duration
        is the optimistic-bias trap the brief named, and the assertion that
        fails for it is named below."""
        LED = "## Open\n\n{open}\n## Recently landed\n\n{done}\n"
        entry = "- **#{i}** — task {i} · P2 · task\n"
        T = 1784900000
        # #1 and #3 arrive at t0; #1 lands 1h later; #2 arrives; #3 lands
        # 4h later; #2 stays open. The intersection is {1, 3}; #2 is
        # excluded from the duration population even though it arrived.
        watch._LEDGER_SNAPS.clear()
        with tempfile.TemporaryDirectory() as d:
            self._ledger_repo(d, [
                (LED.format(open=entry.format(i=1) + entry.format(i=3),
                            done=""), T),
                (LED.format(open=entry.format(i=2) + entry.format(i=3),
                            done="- **#1** — done · landed `aaa1111`\n"),
                 T + 3600),
                (LED.format(open=entry.format(i=2),
                            done="- **#1** — done · landed `aaa1111`\n" +
                                 "- **#3** — done · landed `ccc3333`\n"),
                 T + 4 * 3600),
            ])
            r = watch.ledger_series(d, now=T + 4 * 3600)
            self.assertEqual(r["state"], watch.BURN_OK)
            self.assertEqual(r["arrived"], 3, "all three arrived")
            self.assertEqual(r["landed"], 2, "two landed")
            self.assertEqual(r["open"], 1, "#2 is still open")
            # PRECONDITION, derived at runtime: the two landed durations
            # genuinely differ (1h vs 4h), so a median over them is a real
            # choice between values rather than a tautology.
            self.assertNotEqual(3600, 4 * 3600,
                                "fixture durations must differ for the "
                                "median assertion to mean anything")
            # THE LOAD-BEARING ONE: median_n is the INTERSECTION size (2),
            # not the arrival count (3). Folding #2 in as zero-duration
            # would make median_n == 3 and a different median.
            self.assertEqual(r["median_n"], 2,
                             "the median population is the landed "
                             "intersection, not the arrivals")
            self.assertEqual(r["median"], 3600 * 2.5,
                             "median of {3600, 14400} is their mean 9000")
            # #2 must not appear as a zero-duration duration: that is the
            # optimistic bias. The population is exactly the two finished.
            self.assertNotIn(0, [3600, 4 * 3600],
                             "an open id contributes no duration")

    def test_ledger_series_median_counts_a_combined_head_as_two_pairs(self):
        """#218 / #399. A combined landed head (`- **#A/#B**`) names TWO
        ids; ledger_series already counts them as two landings, and the
        median follows the function: it contributes TWO durations, not one.
        #392's audit lane got this wrong and was refuted — follow the
        function, and assert the pair count here."""
        LED = "## Open\n\n{open}\n## Recently landed\n\n{done}\n"
        T = 1784900000
        # #1 arrives; then #2 and #3 land together as a combined head an
        # hour later. The intersection is {2, 3} and BOTH contribute a
        # duration — the median population is 2, not 1.
        t0 = LED.format(open="- **#1** — one · P2 · task\n", done="")
        t1 = LED.format(open="",
                        done="- **#2/#3** — did it together · "
                             "landed `abc1234`\n")
        self.assertIn("- **#2/#3**", t1,
                      "fixture must hold a combined head to land")
        watch._LEDGER_SNAPS.clear()
        with tempfile.TemporaryDirectory() as d:
            self._ledger_repo(d, [(t0, T), (t1, T + 3600)])
            r = watch.ledger_series(d, now=T + 3600)
            self.assertEqual(r["state"], watch.BURN_OK)
            self.assertEqual(r["arrived"], 3, "the combined ids arrived")
            self.assertEqual(r["landed"], 2,
                             "a combined head lands every id it names")
            # THE LOAD-BEARING ONE: the combined head produced TWO
            # filed-to-landed pairs, not one. A reader that collapsed the
            # head would see median_n == 1.
            self.assertEqual(r["median_n"], 2,
                             "a combined head contributes two durations, "
                             "one per id it names — follow the function")

    def test_ledger_series_median_takes_the_mean_of_two_middles(self):
        """#218. An even-sized population has no single middle value. The
        standard median is the MEAN of the two middle values (statistics
        .median), and that choice is stated here so the renderer and any
        future reader know which of the two it is. The fixture has FOUR
        landed ids at distinct durations so the choice is observable."""
        LED = "## Open\n\n{open}\n## Recently landed\n\n{done}\n"
        entry = "- **#{i}** — task {i} · P2 · task\n"
        T = 1784900000
        watch._LEDGER_SNAPS.clear()
        with tempfile.TemporaryDirectory() as d:
            # land #1..#4 at 1h, 2h, 3h, 4h after their (simultaneous)
            # arrival — four distinct durations, even-sized population.
            open0 = "".join(entry.format(i=j) for j in range(1, 5))
            snaps = [(LED.format(open=open0, done=""), T)]
            for i, hrs in enumerate((1, 2, 3, 4), start=1):
                done = "".join("- **#%d** — done · landed `s%d`\n" % (j, j)
                               for j in range(1, i + 1))
                open_ = "".join(entry.format(i=j) for j in range(i + 1, 5))
                snaps.append((LED.format(open=open_, done=done),
                              T + hrs * 3600))
            self._ledger_repo(d, snaps)
            r = watch.ledger_series(d, now=T + 4 * 3600)
            self.assertEqual(r["state"], watch.BURN_OK)
            self.assertEqual(r["landed"], 4)
            # PRECONDITION: four distinct durations in ascending order, so
            # the even-mid choice (2h, 3h) is real rather than degenerate.
            self.assertEqual(r["median_n"], 4)
            self.assertEqual(4 % 2, 0,
                             "population must be even-sized for the "
                             "mean-of-middles assertion to be meaningful")
            # THE LOAD-BEARING ONE: the standard median (mean of the two
            # middles) is 2.5h. Returning the lower middle (2h) or the
            # upper (3h) would fail this.
            self.assertEqual(r["median"], 2.5 * 3600,
                             "an even population takes the mean of its two "
                             "middle values, not one of them")

    def test_ledger_series_median_says_which_kind_of_nothing(self):
        """#218. The no-data case follows the panel's existing idiom
        (`test_ledger_series_says_which_kind_of_nothing`): a bare `0` or a
        dash reads as 'work takes no time', which is a lie. 'Nothing has
        landed' is its own answer, distinguishable from 'one thing landed
        in 0s'. median is None and median_n is 0 — the renderer's no-data
        branch keys on median_n, and None here is the absence the branch
        names."""
        LED = "## Open\n\n- **#1** — one · P2 · task\n\n## Recently landed\n\n"
        T = 1784900000
        watch._LEDGER_SNAPS.clear()
        with tempfile.TemporaryDirectory() as d:
            self._ledger_repo(d, [(LED, T)])
            r = watch.ledger_series(d, now=T)
            self.assertEqual(r["state"], watch.BURN_OK)
            self.assertEqual(r["arrived"], 1, "one task filed")
            self.assertEqual(r["landed"], 0, "nothing landed")
            self.assertEqual(r["median_n"], 0,
                             "no landed id -> no duration population")
            self.assertIsNone(r["median"],
                              "median is absent (None), not 0 — a 0 would "
                              "read as 'work takes no time'")

    def test_ledger_series_median_handles_a_single_pair(self):
        """#218. One landed id: the median is its duration, and median_n
        is 1. The degenerate case is not the no-data case — it is a real
        measurement over one pair, and the renderer must not collapse it
        to 'nothing landed'."""
        LED = "## Open\n\n{open}\n## Recently landed\n\n{done}\n"
        T = 1784900000
        watch._LEDGER_SNAPS.clear()
        with tempfile.TemporaryDirectory() as d:
            self._ledger_repo(d, [
                (LED.format(open="- **#1** — one · P2 · task\n", done=""), T),
                (LED.format(open="",
                            done="- **#1** — done · landed `aaa1111`\n"),
                 T + 5400),
            ])
            r = watch.ledger_series(d, now=T + 5400)
            self.assertEqual(r["state"], watch.BURN_OK)
            self.assertEqual(r["landed"], 1)
            self.assertEqual(r["median_n"], 1)
            self.assertEqual(r["median"], 5400.0,
                             "a single pair's median is its own duration")

    def test_ledger_stats_replays_only_what_is_new(self):
        # the walk is one `git show` per ledger commit and it only ever grows,
        # so it must never replay per tick. History is immutable, so the
        # per-revision parse is memoised on the commit sha: a NEW head costs
        # only the commits that are new.
        import subprocess
        LED = "## Open\n\n- **#{i}** — one · P2 · task\n\n## Recently landed\n\n"
        T = 1784900000
        real = subprocess.run
        with tempfile.TemporaryDirectory() as d:
            watch._LEDGER_SNAPS.clear()
            watch._LEDGER_CACHE.clear()
            self._ledger_repo(d, [(LED.format(i=i), T + i * 600)
                                  for i in range(1, 6)])
            calls = []

            def counting(cmd, *a, **kw):
                calls.append(cmd)
                return real(cmd, *a, **kw)

            subprocess.run = counting
            try:
                watch.ledger_stats(d)
                cold = len([c for c in calls if "show" in c])
                n = len(calls)
                for _ in range(4):
                    watch.ledger_stats(d)
                warm = len(calls) - n
                # a sixth ledger commit: only IT should be shown
                subprocess.run = real
                self._ledger_repo(d, [(LED.format(i=6), T + 3600)])
                n = len(calls)
                subprocess.run = counting
                watch.ledger_stats(d)
                incr = [c for c in calls[n:] if "show" in c]
            finally:
                subprocess.run = real
            self.assertEqual(cold, 5, "the cold walk should read every revision")
            self.assertEqual(warm, 4, "a warm tick is one rev-parse and nothing else")
            self.assertEqual(len(incr), 1,
                             "a new head should replay only the new commit")
            watch._LEDGER_SNAPS.clear()
            watch._LEDGER_CACHE.clear()

    LED217 = "# Task ledger\n\nNext id: **99**\n\n## Open\n\n"

    def test_first_sight_grammar_has_exactly_one_copy(self):
        # #217 reads the ledger's first sightings with #213/#216's grammar,
        # so "what counts as an entry and what counts as an origin claim"
        # must be ONE rule. Pre-#352 that rule lived as a VERBATIM copy in
        # watch.py pinned equal to lint's — a test that two copies agree,
        # which is a test that should not need to exist. #352 made the
        # grammar one MODULE (ledger_parse) that watch, lint and
        # task_origins all import, so the pin is now IDENTITY: there are no
        # two copies left whose drift a test could catch.
        import ledger_parse
        import lint
        import task_origins
        for name in ("ENTRY_HEAD", "ENTRY_ID", "ORIGIN_MARK",
                     "ledger_entries"):
            self.assertIs(getattr(watch, name), getattr(ledger_parse, name),
                          f"watch.{name} is not ledger_parse's")
            self.assertIs(getattr(lint, name), getattr(ledger_parse, name),
                          f"lint.{name} is not ledger_parse's")
        for name in ("KNOWN_ORIGINS", "entry_origins"):
            self.assertIs(getattr(watch, name), getattr(ledger_parse, name),
                          f"watch.{name} is not ledger_parse's")
        self.assertIs(lint.open_section_text, ledger_parse.open_section_text)
        # task_origins consumed the grammar THROUGH lint before #352; its
        # module handle must be the shared one now, not lint's re-export.
        self.assertIs(task_origins.ledger_parse, ledger_parse)
        self.assertEqual(set(watch.KNOWN_ORIGINS),
                         set(lint.ORIGIN_VALUES) - {"unknown"})

    def test_ledger_entries_reads_the_hostile_shapes(self):
        # The pre-#352 pin asserted watch's and lint's COPIES of
        # ledger_entries agreed on this fixture; with one module that would
        # compare the function to itself. What still needs pinning is the
        # BEHAVIOUR on the hostile shapes: a hard-wrapped marker, a
        # combined head, a body cross-reference, and landed prose that is
        # not an entry.
        import ledger_parse
        hostile = (
            "## Open\n\n"
            "- **#250/#251** — combined · P2 · task · origin:\n"
            "  **loop** · wrapped marker\n"
            "- **#252** — body mentions #250 in passing · origin: **human**\n"
            "\n## Recently landed\n\n**#9** landed prose, not an entry.\n")
        self.assertEqual(ledger_parse.ledger_entries(hostile), [
            ([250, 251],
             "- **#250/#251** — combined · P2 · task · origin:\n"
             "  **loop** · wrapped marker"),
            ([252],
             "- **#252** — body mentions #250 in passing · origin: **human**"
             "\n"),
        ])
        self.assertEqual(ledger_parse.entry_origins(hostile),
                         [([250, 251], "loop"), ([252], "human")])

    def test_ledger_provenance_counts_first_sightings_exactly(self):
        # #217. The panel draws three counts — human, loop, historical
        # unknown — and unknown must NEVER be rolled into loop: the unknown
        # remainder is the absence of a claim, not evidence of one.
        T = 1784900000
        watch._LEDGER_SNAPS.clear()
        watch._LEDGER_CACHE.clear()
        with tempfile.TemporaryDirectory() as d:
            self._ledger_repo(d, [
                (self.LED217 +
                 "- **#1** — his · P2 · task · origin: **human**\n"
                 "- **#2** — the loop's · P2 · task · origin: **loop**\n"
                 "- **#3** — filed before markers existed · P2 · task\n", T),
            ])
            p = watch.ledger_stats(d)["provenance"]
            self.assertEqual(p["human"], 1)
            self.assertEqual(p["loop"], 1)
            self.assertEqual(p["unknown"], 1)
            self.assertEqual(p["total"], 3)
            self.assertEqual(p["human"] + p["loop"] + p["unknown"],
                             p["total"])
            self.assertTrue(p["history_complete"])
        watch._LEDGER_SNAPS.clear()
        watch._LEDGER_CACHE.clear()

    def test_ledger_provenance_first_sight_is_final(self):
        # SABOTAGE-PROVEN shape (task_origins.py's pair, one surface over):
        # a marker added LATER is documentation, not time travel. A reader
        # of the current snapshot reports human here; the first-sight walk
        # must keep this id unknown forever.
        T = 1784900000
        watch._LEDGER_SNAPS.clear()
        watch._LEDGER_CACHE.clear()
        with tempfile.TemporaryDirectory() as d:
            self._ledger_repo(d, [
                (self.LED217 + "- **#1** — unmarked at filing · P2 · task\n", T),
                (self.LED217 + "- **#1** — unmarked at filing · P2 · task · "
                               "origin: **human**\n", T + 3600),
            ])
            p = watch.ledger_stats(d)["provenance"]
            self.assertEqual(p["unknown"], 1)
            self.assertEqual(p["human"], 0)
            self.assertEqual(p["loop"], 0)
        watch._LEDGER_SNAPS.clear()
        watch._LEDGER_CACHE.clear()

    def test_ledger_provenance_combined_entries_and_deletions(self):
        # A combined entry classifies every id in its head token; a task
        # groomed OUT of the ledger keeps its first sight, because first
        # sight already happened and grooming cannot un-happen it.
        T = 1784900000
        watch._LEDGER_SNAPS.clear()
        watch._LEDGER_CACHE.clear()
        with tempfile.TemporaryDirectory() as d:
            self._ledger_repo(d, [
                (self.LED217 + "- **#1** — doomed · P2 · task · "
                               "origin: **human**\n", T),
                (self.LED217 + "- **#2/#3** — combined · P2 · task · "
                               "origin: **loop**\n", T + 3600),
            ])
            p = watch.ledger_stats(d)["provenance"]
            self.assertEqual(p["human"], 1)   # #1, though deleted
            self.assertEqual(p["loop"], 2)    # #2 and #3 from one entry
            self.assertEqual(p["unknown"], 0)
            self.assertEqual(p["total"], 3)
        watch._LEDGER_SNAPS.clear()
        watch._LEDGER_CACHE.clear()

    def test_ledger_provenance_uncommitted_entries_are_not_counted(self):
        # The denominator is COMMITTED first sightings. A brand-new entry
        # sitting uncommitted in the working tree is not a historical
        # arrival and must not inflate any of the three counts.
        T = 1784900000
        watch._LEDGER_SNAPS.clear()
        watch._LEDGER_CACHE.clear()
        with tempfile.TemporaryDirectory() as d:
            self._ledger_repo(d, [
                (self.LED217 + "- **#1** — committed · P2 · task · "
                               "origin: **loop**\n", T),
            ])
            with open(os.path.join(d, ".dreamwork", "tasks.md"), "a") as f:
                f.write("- **#2** — fresh and uncommitted · origin: **human**\n")
            p = watch.ledger_stats(d)["provenance"]
            self.assertEqual(p["total"], 1)
            self.assertEqual(p["human"], 0)
            self.assertEqual(p["loop"], 1)
        watch._LEDGER_SNAPS.clear()
        watch._LEDGER_CACHE.clear()

    def test_ledger_provenance_cache_refreshes_only_on_a_new_head(self):
        # The walk is one `git show` per ledger commit and only ever grows,
        # so the answer is cached on a truthful repository-history key — the
        # target and its HEAD — and a repeated tick must not recompute it.
        T = 1784900000
        watch._LEDGER_SNAPS.clear()
        watch._LEDGER_CACHE.clear()
        with tempfile.TemporaryDirectory() as d:
            self._ledger_repo(d, [
                (self.LED217 + "- **#1** — one · P2 · task · origin: **human**\n",
                 T),
            ])
            first = watch.ledger_stats(d)
            self.assertIs(watch.ledger_stats(d), first,
                          "a warm tick must reuse the cached answer")
            self._ledger_repo(d, [
                (self.LED217 + "- **#1** — one · P2 · task · origin: **human**\n"
                               "- **#2** — two · P2 · task · origin: **loop**\n",
                 T + 3600),
            ])
            second = watch.ledger_stats(d)
            self.assertIsNot(second, first, "HEAD moved — the answer must too")
            self.assertEqual(second["provenance"]["loop"], 1)
            self.assertEqual(second["provenance"]["total"], 2)
        watch._LEDGER_SNAPS.clear()
        watch._LEDGER_CACHE.clear()

    def test_ledger_provenance_reads_the_nested_targets_own_ledger(self):
        # The ledger path is resolved against the repository TOP LEVEL, not
        # blindly against the target: a target nested inside a larger repo
        # must read its OWN `.dreamwork/tasks.md` history, never the repo
        # root's. The two ledgers here classify disjointly, so a leak across
        # the boundary cannot pass as a correct answer.
        import subprocess
        watch._LEDGER_SNAPS.clear()
        watch._LEDGER_CACHE.clear()
        with tempfile.TemporaryDirectory() as d:
            base = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x",
                        GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
            subprocess.run(["git", "-C", d, "init", "-q"], env=base,
                           check=True, capture_output=True)
            os.makedirs(os.path.join(d, ".dreamwork"))
            os.makedirs(os.path.join(d, "sub", ".dreamwork"))
            with open(os.path.join(d, ".dreamwork", "tasks.md"), "w") as f:
                f.write(self.LED217 +
                        "- **#1** — the ROOT ledger's · origin: **human**\n")
            with open(os.path.join(d, "sub", ".dreamwork", "tasks.md"), "w") as f:
                f.write(self.LED217 +
                        "- **#7** — the NESTED ledger's · origin: **loop**\n")
            subprocess.run(["git", "-C", d, "add", "."], env=base,
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", d, "commit", "-q", "-m", "both"],
                           env=base, check=True, capture_output=True)
            # Query BOTH targets in one process. Their one shared commit sha
            # identifies two different blobs, so a per-revision memo keyed on
            # sha alone makes whichever target ticks first poison the other.
            root = watch.ledger_stats(d)["provenance"]
            nested = watch.ledger_stats(os.path.join(d, "sub"))["provenance"]
            self.assertEqual(root, {"human": 1, "loop": 0, "unknown": 0,
                                    "total": 1, "history_complete": True})
            self.assertEqual(nested, {"human": 0, "loop": 1, "unknown": 0,
                                      "total": 1, "history_complete": True},
                             "root-first memo poisoned the nested ledger")

            # And prove order independence, not merely one lucky order.
            watch._LEDGER_SNAPS.clear()
            watch._LEDGER_CACHE.clear()
            nested = watch.ledger_stats(os.path.join(d, "sub"))["provenance"]
            root = watch.ledger_stats(d)["provenance"]
            self.assertEqual(nested["loop"], 1)
            self.assertEqual(nested["human"], 0)
            self.assertEqual(root["human"], 1,
                             "nested-first memo poisoned the root ledger")
            self.assertEqual(root["loop"], 0)
        watch._LEDGER_SNAPS.clear()
        watch._LEDGER_CACHE.clear()

    def test_ledger_provenance_names_incomplete_coverage(self):
        # A shallow clone cannot see first sightings before its boundary;
        # claiming full coverage there would be a lie, so the flag goes
        # false and the page names the incompleteness (#216's contract).
        import subprocess
        T = 1784900000
        watch._LEDGER_SNAPS.clear()
        watch._LEDGER_CACHE.clear()
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "src")
            self._ledger_repo(src, [
                (self.LED217 + "- **#1** — old · P2 · task\n", T),
                (self.LED217 + "- **#1** — old · P2 · task\n"
                               "- **#2** — new · P2 · task · origin: **loop**\n",
                 T + 3600),
            ])
            dst = os.path.join(d, "shallow")
            subprocess.run(["git", "clone", "-q", "--depth", "1",
                            "file://" + src, dst],
                           check=True, capture_output=True)
            p = watch.ledger_stats(dst)["provenance"]
            self.assertFalse(p["history_complete"])
        watch._LEDGER_SNAPS.clear()
        watch._LEDGER_CACHE.clear()

    def test_ledger_provenance_degrades_explicitly_when_there_is_nothing(self):
        # Non-git targets and repos with no ledger history are ordinary
        # states: the burndown says WHICH nothing, and no provenance block
        # is emitted to contradict it — never a crash, never a silent zero.
        watch._LEDGER_CACHE.clear()
        with tempfile.TemporaryDirectory() as d:
            r = watch.ledger_stats(d)
            self.assertEqual(r["state"], watch.BURN_NONE)
            self.assertNotIn("provenance", r)
        with tempfile.TemporaryDirectory() as d:
            self._ledger_repo(d, [("no entries anywhere\n", 1784900000)])
            r = watch.ledger_stats(d)
            self.assertEqual(r["state"], watch.BURN_NONE)
            self.assertNotIn("provenance", r)
        watch._LEDGER_CACHE.clear()

    def test_ledger_provenance_render_is_escaped_and_exposes_its_copy(self):
        # The block's text and its aria-label are the accessibility story —
        # colour alone never carries the split — so the copy is asserted on
        # the page's own source: every string interpolated into an attribute
        # goes through esc(), the denominator names its source, and the
        # incomplete state is named, not implied.
        page = watch.PAGE
        self.assertIn('role="img" aria-label="${esc(aria)}"', page)
        self.assertIn("first sightings in recorded git history", page)
        self.assertIn("historical unknown", page)
        self.assertIn("coverage is incomplete", page)
        self.assertIn("title=\"${esc(n)} ${c}\"", page)
        self.assertIn('class="provline" title="${esc(', page)
        # Exact flex weights fill the track without independently-rounded
        # percentage slivers; nonzero tiny cohorts remain visible, while
        # zero remains truly absent.
        self.assertIn("flex:var(--share) 1 0", page)
        self.assertIn("min-width:${c ? 2 : 0}px", page)
        # the panel's height is the premise the bars' motion rests on, so
        # the count-carrying lines may never wrap
        self.assertRegex(page, r"\.provline\s*\{[^}]*white-space:nowrap")
        self.assertRegex(page, r"\.provsrc\s*\{[^}]*white-space:nowrap")
        # the accent is not spent here — nothing in this panel waits on him.
        # Scoped to the provenance rules: the panel's OTHER rules are #142's
        m = re.search(r"(\.bdprov\s*\{.*?\n  \})", page, re.S)
        self.assertIsNotNone(m, "no .bdprov rule in the page's STYLE")
        prov_css = page[m.start():m.start() + 1200]
        self.assertNotIn("--accent", prov_css)
        # unknown is visually distinct WITHOUT colour: the hatch is a
        # pattern, so it survives every tint and every colour-vision
        self.assertIn("repeating-linear-gradient", prov_css)
        # and there is deliberately NO motion on this datum: a live tick
        # commits its DOM instantly (transitions.md), so no transition may
        # be declared on any of its parts
        self.assertNotIn("transition", prov_css)

    def test_live_data_assignments_go_through_one_seam(self):
        # `ensureData` consumes mtime as it fetches, so reactive hooks wired
        # beside it are dead on a fresh page and look perfect on later ticks.
        # Every fetcher must assign through setData; a bare assignment silently
        # re-arms #208's exact failure.
        assignments = re.findall(r"(?m)^\s*data\s*=", watch.PAGE)
        self.assertEqual(assignments, ["  data ="])
        # ensureData + tick + #487 cycleBurnStep — every fetcher through setData
        self.assertEqual(watch.PAGE.count("setData(await"), 3)

    def test_git_tail_carries_what_an_expanded_row_shows(self):
        # #166: the row expands onto the full sha, the author, the message
        # BODY (where this repo's reasoning lives) and the files touched.
        # One `git log` call, so `--name-only`'s file list — which prints
        # after the format, on its own lines — has to be told apart from the
        # next commit. `%x1e` per record is what does that.
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ,
                       GIT_AUTHOR_NAME="a commit author",
                       GIT_AUTHOR_EMAIL="t@x",
                       GIT_COMMITTER_NAME="a commit author",
                       GIT_COMMITTER_EMAIL="t@x")
            run = lambda *a: subprocess.run(  # noqa: E731
                ["git", "-C", d, *a], env=env, capture_output=True, check=True)
            run("init", "-q")

            def commit(msg, body, *names):
                for n in names:
                    os.makedirs(os.path.dirname(os.path.join(d, n)) or d,
                                exist_ok=True)
                    with open(os.path.join(d, n), "w") as f:
                        f.write(n)
                    run("add", n)
                run("commit", "-q", "-m", msg, *(["-m", body] if body else []))

            # a body carrying the field separator: it is his prose, so the
            # parse rejoins the middle rather than indexing a fixed position
            commit("feat: with a body", "line one\nline two\x1fand a separator",
                   "a.txt", "sub/b.txt")
            commit("fix: subject \x1f carries one separator \x1e and the other",
                   None, "c.txt")
            rows = watch.git_tail(d)
            self.assertEqual(len(rows), 2)
            newest, older = rows
            self.assertEqual(
                newest["subject"],
                "fix: subject \x1f carries one separator \x1e and the other")
            self.assertEqual(newest["body"], "")
            self.assertEqual(newest["files"], ["c.txt"])
            self.assertEqual(older["who"], "a commit author")
            self.assertEqual(len(older["full"]), 40)
            self.assertTrue(older["full"].startswith(older["sha"]))
            self.assertIn("and a separator", older["body"])
            self.assertEqual(sorted(older["files"]), ["a.txt", "sub/b.txt"])
            self.assertEqual(older["more"], 0)
            # a commit that touches nothing is an ordinary state, not a
            # missing file list — the page says which
            run("commit", "-q", "--allow-empty", "-m", "chore: empty")
            self.assertEqual(watch.git_tail(d)[0]["files"], [])

    def test_a_no_body_commit_shows_its_full_subject_in_the_detail(self):
        # #486: the header's .gsub may ellipsise (nowrap + text-overflow), so
        # a commit with no body must render its FULL subject inside the
        # detail — otherwise the one line the commit has to say is shown
        # nowhere. Assert the empty-body branch emits gfullsub with the
        # subject, ahead of the parenthetical.
        idx = watch.PAGE.index('gfullsub">${esc(c.subject)}')
        seg = watch.PAGE[idx:idx + 300]
        self.assertIn("no message body", seg)
        self.assertIn(".git .gfullsub", watch.PAGE)

    def test_git_tail_caps_the_file_list_and_says_it_did(self):
        # five commits touching a thousand files each would be a megabyte of
        # /data.json on every tick, to fill a disclosure nobody opened. The
        # cap has to be VISIBLE, or the page silently claims a short commit.
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x",
                       GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
            run = lambda *a: subprocess.run(  # noqa: E731
                ["git", "-C", d, *a], env=env, capture_output=True, check=True)
            run("init", "-q")
            n = watch.GIT_FILES + 7
            for i in range(n):
                with open(os.path.join(d, "f%03d" % i), "w") as f:
                    f.write("x")
            run("add", "-A")
            run("commit", "-q", "-m", "feat: a wide commit")
            row = watch.git_tail(d)[0]
            self.assertEqual(len(row["files"]), watch.GIT_FILES)
            self.assertEqual(row["more"], 7)

    def test_serving_report_names_every_state(self):
        # #140. Each of these is a DIFFERENT answer to "what is this page
        # running", and only one of them means "I compared and they differ".
        # deployed.py exists because a shell version collapsed "I could not
        # compare" into "no match" and reported it with total confidence.
        import subprocess
        src = b"# the running source\n"
        with tempfile.TemporaryDirectory() as d:
            # not a checkout at all — the ordinary state for most targets
            r = watch.serving_report(d, src=src)
            self.assertEqual(r["state"], watch.SERVE_NOREPO)
            self.assertIsNotNone(r["note"])

            env = dict(os.environ,
                       GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x",
                       GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
            run = lambda *a: subprocess.run(  # noqa: E731
                ["git", "-C", d, *a], env=env, capture_output=True, check=True)
            run("init", "-q")
            with open(os.path.join(d, "other"), "w") as f:
                f.write("x")
            run("add", "other")
            run("commit", "-q", "-m", "nothing to do with the dashboard")
            # a repo that tracks no watch.py is still "no repo", not an error
            self.assertEqual(watch.serving_report(d, src=src)["state"],
                             watch.SERVE_NOREPO)

            def commit(body, msg):
                with open(os.path.join(d, "watch.py"), "wb") as f:
                    f.write(body)
                run("add", "watch.py")
                run("commit", "-q", "-m", msg)

            commit(b"# an older source\n", "older watch.py")
            # running something that is in NO commit
            r = watch.serving_report(d, src=src)
            self.assertEqual(r["state"], watch.SERVE_UNTRACKED)

            commit(src, "the running one")
            r = watch.serving_report(d, src=src)
            self.assertEqual(r["state"], watch.SERVE_CURRENT)
            self.assertTrue(r["rev"])
            self.assertEqual(r["missing"], [])

            served = watch.serving_report(d, src=src)["rev"]
            commit(b"# newer\n", "feat: a change to the dashboard")
            run("commit", "-q", "--allow-empty",
                "-m", "docs: untouched by the dashboard")
            commit(b"# newer still\n", "fix: another change")
            r = watch.serving_report(d, src=src)
            self.assertEqual(r["state"], watch.SERVE_BEHIND)
            self.assertEqual(r["rev"], served)
            # the empty commit is NOT in here: `missing` is pathspec-filtered,
            # which is why the line says "N watch.py commits behind" and not
            # "N commits behind" — HEAD moved three times, watch.py twice.
            self.assertEqual([s for _, s in r["missing"]],
                             ["fix: another change",
                              "feat: a change to the dashboard"])
            self.assertTrue(all(h for h, _ in r["missing"]))

    def test_serving_report_survives_a_process_that_cannot_read_itself(self):
        # the check exists for the state where its own subject is absent, so
        # it has to RETURN a reading rather than raise — a crash reads as
        # silence, and this one would take /data.json down with it.
        # SELF_SRC is populated in any normal run — assert that first, or this
        # whole check is measuring a module that never loaded
        self.assertTrue(watch.SELF_SRC, "watch.py never read its own source")
        saved, watch.SELF_SRC = watch.SELF_SRC, None
        try:
            r = watch.serving_report(".")
        finally:
            watch.SELF_SRC = saved
        self.assertEqual(r["state"], watch.SERVE_ERROR)
        self.assertIn("own source", r["note"])

    def test_serving_cached_keys_on_head(self):
        # the walk is O(revisions of watch.py) git calls — 75 today, growing
        # forever — so it must not run per tick. It may only re-run when HEAD
        # moves, because that is the only thing that can change the answer for
        # a process whose own bytes are fixed.
        import subprocess
        calls = []
        real = subprocess.run

        def counting(cmd, *a, **kw):
            calls.append(cmd)
            return real(cmd, *a, **kw)

        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ,
                       GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x",
                       GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
            subprocess.run(["git", "-C", d, "init", "-q"], env=env, check=True,
                           capture_output=True)
            with open(os.path.join(d, "watch.py"), "wb") as f:
                f.write(b"# not what is running\n")
            subprocess.run(["git", "-C", d, "add", "watch.py"], env=env,
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", d, "commit", "-q", "-m", "one"],
                           env=env, check=True, capture_output=True)
            watch._SERVE_CACHE.clear()
            subprocess.run = counting
            try:
                first = watch.serving_cached(d)
                n_cold = len(calls)
                for _ in range(5):
                    watch.serving_cached(d)
                n_warm = len(calls) - n_cold
            finally:
                subprocess.run = real
            self.assertEqual(first["state"], watch.SERVE_UNTRACKED)
            # five more ticks cost exactly one rev-parse each and nothing else
            self.assertEqual(n_warm, 5)
            self.assertTrue(all("rev-parse" in c for c in calls[n_cold:]))
            watch._SERVE_CACHE.clear()

    def test_every_git_call_refuses_the_index_lock(self):
        # his CLAUDE.md carries a live mitigation about `.git/index.lock`: a
        # background reader taking the real lock races his interactive git and
        # orphans it when killed. A dashboard that polls git forever is
        # precisely the shape that reintroduces it, so the flag is asserted
        # rather than remembered.
        import subprocess
        seen = []
        real = subprocess.run

        def spy(cmd, *a, **kw):
            if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "git":
                seen.append(list(cmd))
            return real(cmd, *a, **kw)

        with tempfile.TemporaryDirectory() as d:
            subprocess.run = spy
            try:
                watch._SERVE_CACHE.clear()
                watch._LEDGER_CACHE.clear()
                watch.serving_cached(d)
                watch.serving_report(d, src=b"x")
                # ...and the burndown's walk, which is the busiest git caller
                # on the page: one `git show` per ledger commit (#142)
                watch.ledger_stats(d)
                watch.ledger_series(d)
                watch.git_tail(d)
            finally:
                subprocess.run = real
                watch._SERVE_CACHE.clear()
                watch._LEDGER_CACHE.clear()
        # a comparison that could not run must not look like one that ran: if
        # no git call was made at all this assertion is vacuous, so require
        # the calls to exist first
        self.assertTrue(seen, "no git call was made — this check proved nothing")
        for cmd in seen:
            self.assertIn("--no-optional-locks", cmd, " ".join(cmd))

    def test_watched_mtime_moves(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            before = watch.watched_mtime(d)
            time.sleep(0.05)
            with open(os.path.join(d, ".dreamwork", "lessons.md"), "a") as f:
                f.write("- new lesson\n")
            self.assertGreater(watch.watched_mtime(d), before)

    def test_watched_mtime_sees_deletion(self):
        # #86's contract, re-implemented by #481 as a name-set fingerprint
        # rather than directory mtimes: removing a file cannot raise the max
        # mtime of what remains, so absence has to be observed directly.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            victim = os.path.join(d, ".dreamwork", "lessons.md")
            # precondition, derived at runtime: the file whose removal this
            # test relies on is there to be removed.
            self.assertTrue(os.path.exists(victim))
            before = watch.watched_mtime(d)
            time.sleep(0.05)
            os.remove(victim)
            self.assertNotEqual(watch.watched_mtime(d), before,
                                "deletion invisible to watched_mtime")

    def test_question_sigs_write_does_not_retrigger_a_render(self):
        # #481 — the sig store is derived state: collect() rewrites it (tmp +
        # os.replace) on first sight of an entry and on every content change,
        # always downstream of the questions.md write the walk already sees
        # directly. Counting it made a fresh target re-render once for
        # nothing ~2s after load. The exclusion is safe only while BOTH
        # halves below hold, so both are asserted from runtime-derived values.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            entry = {"title": "Sig test entry", "body": "v1",
                     "follows": [], "answers": [], "answer": None}
            # PRECONDITION, derived at runtime: the production writer really
            # creates the store at the path this test exercises — if it is
            # ever renamed or relocated this fails, instead of the exclusion
            # passing vacuously over a file nothing writes anymore.
            watch.track_question_updates(d, [dict(entry)])
            sig = os.path.join(d, ".dreamwork", watch.QUESTION_SIGS)
            self.assertTrue(os.path.exists(sig),
                            "writer no longer creates the excluded path")
            time.sleep(0.05)
            before = watch.watched_mtime(d)
            time.sleep(0.05)
            # Half 1: a first-sight write of a NEW entry (the fresh-target
            # case — no log_event line, so only the sig store moves) must not
            # move watched_mtime.
            watch.track_question_updates(
                d, [dict(entry, title="Sig test entry two")])
            after = watch.watched_mtime(d)
            self.assertEqual(after, before,
                             "question-sigs.json write re-triggered a render")
            # Half 2: a questions.md change must STILL move it — the walk
            # still covers the file the sig store merely derives from, so no
            # real re-render is lost.
            time.sleep(0.05)
            with open(os.path.join(d, ".dreamwork", "questions.md"),
                      "a") as f:
                f.write("\n## still watched\n")
            self.assertGreater(watch.watched_mtime(d), after,
                               "questions.md is no longer watched")

    def test_long_entry_digest_is_rewrap_invariant(self):
        # #509 — the loop re-wraps a long entry's body lines when it rewrites
        # questions.md; a line-break-only change (same words, different wrap
        # column) must NOT flip the per-entry signature. The #229 entry
        # (longest: nested tables, code fences, ~100 lines) was the phantom.
        #
        # PRODUCTION LINE whose change reds this: _entry_content_digest's body
        # normalisation (_sig_text). Without it the raw body line-structure is
        # hashed, so a re-wrap flips the digest and track_question_updates
        # phantom-fires question-updated. (Sabotage _sig_text to `return s`
        # and this assertion fails; a `return ""` sabotage is a FALSE GREEN —
        # both forms hash equal for the wrong reason — so the no-op is the
        # red that proves the test sees the words.)
        md_b = _long_entry_229_md(_LONG_ENTRY_229_BODY, 72)
        md_a = _long_entry_229_md(_LONG_ENTRY_229_BODY, 46)
        eb = [e for e in watch.parse_answered(md_b)
              if "#229" in (e.get("title") or "")][0]
        ea = [e for e in watch.parse_answered(md_a)
              if "#229" in (e.get("title") or "")][0]
        # PRECONDITION (derived at runtime): the fixture carries the #229
        # trigger features AND the two builds really differ only in wrap.
        self.assertIn("┌", md_b)             # nested box-drawing table
        self.assertIn("```", md_b)           # code fence
        # resolution head present as words (textwrap may split the line, so
        # check the word-bag, not answered_at's line-anchored regex)
        self.assertIn("answered", " ".join(eb["body"].split()))
        self.assertIn("Revision", " ".join(eb["body"].split()))
        self.assertGreater(len(eb["body"].split()), 60)  # long, rewrappable
        self.assertEqual(" ".join(eb["body"].split()),
                         " ".join(ea["body"].split()),
                         "precondition: same words at both widths")
        self.assertNotEqual(eb["body"], ea["body"],
                            "precondition: the wrap really differs")
        # the fix: same words => same signature regardless of wrap column
        self.assertEqual(watch._entry_content_digest(eb),
                         watch._entry_content_digest(ea),
                         "a re-wrap of unchanged content flipped the signature")

    def test_long_entry_rewrap_emits_no_phantom_event(self):
        # #509 acceptance: two consecutive questions.md rewrites that do NOT
        # change the #229 entry's words (only its body wrap) emit ZERO
        # question-updated events for it.
        # PRODUCTION LINE: _entry_content_digest's _sig_text normalisation —
        # sabotage it to `return s` and the rewrap flips the digest, so
        # track_question_updates logs a phantom question-updated line.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            qpath = os.path.join(d, ".dreamwork", "questions.md")
            with open(qpath, "w") as f:
                f.write(_long_entry_229_md(_LONG_ENTRY_229_BODY, 72))
            watch.collect(d)  # first sight — no event
            # rewrite the SAME words at a different wrap (the loop's rewrap)
            with open(qpath, "w") as f:
                f.write(_long_entry_229_md(_LONG_ENTRY_229_BODY, 46))
            watch.collect(d)
            log = os.path.join(d, ".dreamwork", "watch-events.log")
            # no phantom => the log is never created; treat absent as clean
            events = []
            if os.path.exists(log):
                with open(log, encoding="utf-8") as f:
                    events = [ln for ln in f if "question-updated" in ln]
            self.assertEqual(
                events, [],
                "a re-wrap of unchanged content emitted a phantom event")

    def test_follow_internal_whitespace_is_digest_invariant(self):
        # #509 gate finding: the parser's continuation join (watch.py:12430,
        # `follows[-1].text += " " + s`) already single-spaces a follow
        # ACROSS lines, which masked the coordinator's call-site sabotage
        # (follows bypassing _sig_text passed both rewrap tests — a
        # legitimate defense-in-depth green for LINE-BREAKS). What the
        # parser does NOT defend is whitespace WITHIN one line (tabs,
        # double spaces): only _sig_text collapses those, so the call-site
        # wrapping on follows/answers needs its own binding check.
        # PRODUCTION LINE whose change reds this: the follows call site in
        # _entry_content_digest (`{**f, "text": _sig_text(f.get("text"))}`) —
        # bypass it (the exact gate sabotage) and the two digests differ.
        base = _long_entry_229_md(_LONG_ENTRY_229_BODY, 72)
        marker = "all checks accepted as proposal-hardening inputs"
        assert marker in base, "precondition: the fixture carries the follow"
        spaced = base.replace(
            marker, "all  checks\taccepted  as proposal-hardening inputs")
        assert spaced != base, "precondition: the whitespace really differs"
        e1 = [e for e in watch.parse_answered(base)
              if "#229" in (e.get("title") or "")][0]
        e2 = [e for e in watch.parse_answered(spaced)
              if "#229" in (e.get("title") or "")][0]
        assert e1["follows"] and e2["follows"], (
            "precondition: both builds parse a follow")
        assert e1["follows"][-1]["text"] != e2["follows"][-1]["text"], (
            "precondition: the parser keeps the within-line difference — "
            "if this fails the parser started collapsing whitespace and "
            "the test is vacuous")
        self.assertEqual(watch._entry_content_digest(e1),
                         watch._entry_content_digest(e2),
                         "within-line whitespace in a follow flipped the "
                         "signature — the _sig_text call site is not doing "
                         "its one job")

    def test_long_entry_real_word_change_emits_one_event(self):
        # #509 acceptance: the channel keeps its teeth — a REAL word change
        # to the long entry still emits exactly ONE question-updated event.
        # PRODUCTION LINE: _entry_content_digest must include the body words —
        # sabotage _sig_text to `return ""` (constant digest) and the word
        # change becomes invisible, so zero events fire.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            qpath = os.path.join(d, ".dreamwork", "questions.md")
            with open(qpath, "w") as f:
                f.write(_long_entry_229_md(_LONG_ENTRY_229_BODY, 72))
            watch.collect(d)  # first sight — no event
            # a REAL content change (different words), not a rewrap
            changed = _LONG_ENTRY_229_BODY.replace("Revision directed",
                                                   "REVISION CHANGED")
            self.assertNotEqual(changed, _LONG_ENTRY_229_BODY,
                                "precondition: the word change really applied")
            with open(qpath, "w") as f:
                f.write(_long_entry_229_md(changed, 72))
            watch.collect(d)
            log = os.path.join(d, ".dreamwork", "watch-events.log")
            with open(log, encoding="utf-8") as f:
                events = [ln for ln in f if "question-updated" in ln]
            self.assertEqual(len(events), 1,
                             "a real word change must emit exactly one event")
            self.assertIn("#229", events[0])

    def _question_events(self, d):
        log = os.path.join(d, ".dreamwork", "watch-events.log")
        if not os.path.exists(log):
            return []
        with open(log, encoding="utf-8") as f:
            return [ln for ln in f if "question-updated" in ln]

    def test_old_algo_store_reseeds_silently(self):
        # #534 — when _entry_content_digest's algorithm changes (the #509
        # whitespace normalisation was the live instance), a store written by
        # the OLD algorithm sees every stored digest differ and would emit one
        # phantom question-updated event per entry on the first collect after
        # deploy (~21 phantom events at 09:43:31 on the 2026-07-30 deploy).
        # The store is versioned: an absent/older `algo` re-seeds SILENTLY —
        # every digest recomputed under the CURRENT algorithm, ZERO events.
        #
        # PRODUCTION LINE whose change reds this: track_question_updates's
        # algo-mismatch re-seed branch. Sabotage it to skip the re-seed (fall
        # through to the normal compare, where every old digest != new digest
        # fires an event) and the "zero events" assertion fails.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            # a body whose line-structure the OLD algo keeps but the NEW algo
            # (_sig_text) collapses — so the two digests genuinely differ.
            entry = {"title": "Re-seed alpha", "body": "line one\nline two\n"
                     "line three", "follows": [], "answers": [], "answer": None}
            # PRECONDITION (derived at runtime): the fixture is not vacuous —
            # the old-algo digest really differs from the new-algo one. A
            # single-line body would hash equal under both and the re-seed
            # would have nothing to do.
            self.assertNotEqual(_old_algo_digest(entry),
                                watch._entry_content_digest(entry),
                                "precondition: old/new digests differ")
            _write_old_algo_store(d, [entry])  # unmarked => treated as v0
            sig = os.path.join(d, ".dreamwork", watch.QUESTION_SIGS)
            self.assertNotIn("algo", json.load(open(sig)),
                             "precondition: store predates the algo field")

            live = [dict(entry)]
            watch.track_question_updates(d, live)
            # ZERO events — an algorithm upgrade is not a content change.
            self.assertEqual(self._question_events(d), [],
                             "re-seed fired a phantom question-updated")
            # the store is now stamped current and holds the NEW digest.
            store = json.load(open(sig))
            self.assertEqual(store.get("algo"), watch.SIG_ALGO,
                             "store not stamped with the current algo")
            key = watch._title_sig_key(entry["title"])
            self.assertEqual(store[key]["digest"],
                             watch._entry_content_digest(entry),
                             "store still holds an old-algo digest")
            # #516 refined: the re-seed stamps `now` for a PREVIOUSLY-SEEN
            # entry (this one has a row in the old store — cross-algo change
            # detection is impossible, so the visible stamp replaces the
            # silent stale one). A fresh target with NO prior row keeps None
            # (test_question_update_stamp_is_per_entry_not_file_mtime).
            self.assertAlmostEqual(live[0].get("updated_at") or 0,
                                   time.time(), delta=30,
                                   msg="re-seed did not stamp the seen entry")

            # second collect, unchanged content — still zero, no write storm.
            watch.track_question_updates(d, [dict(entry)])
            self.assertEqual(self._question_events(d), [],
                             "unchanged content after re-seed fired an event")

    def test_reseed_stamps_now_and_stays_silent(self):
        # #516 (Decision 3) REVISES the #534 carry contract: cross-algorithm
        # change detection is impossible (the old algo's digests are
        # incomparable by construction and its implementation is not
        # retained), so the re-seed cannot tell a genuinely-changed entry
        # from an unchanged one. The #534 choice — carry each entry's prior
        # updated_at — is the silent-lie option for the entry that DID
        # change in the same collect (its age goes stale, permanently:
        # the new-algo digest of its changed content means no later collect
        # ever fires). The ruled replacement stamps `now` uniformly: a
        # visible, self-aging blip on a rare algo upgrade over a hidden
        # stale age. Still ZERO events — an algorithm change is not a
        # content change.
        # PRODUCTION LINE: the re-seed branch's per-entry `"updated_at":`
        # value (watch.py, the `_store_algo != SIG_ALGO` arm). Restore the
        # prev_at carry and the stamp is the stale prior, not now.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            entry = {"title": "Re-seed beta", "body": "para one\npara two",
                     "follows": [], "answers": [], "answer": None}
            self.assertNotEqual(_old_algo_digest(entry),
                                watch._entry_content_digest(entry),
                                "precondition: old/new digests differ")
            prior = 1700000000.0
            _write_old_algo_store(d, [entry], stamps={entry["title"]: prior})
            live = [dict(entry)]
            watch.track_question_updates(d, live)
            self.assertEqual(self._question_events(d), [],
                             "re-seed fired a phantom question-updated")
            self.assertAlmostEqual(live[0].get("updated_at") or 0,
                                   time.time(), delta=30,
                                   msg="re-seed carried a stale stamp")
            sig = os.path.join(d, ".dreamwork", watch.QUESTION_SIGS)
            self.assertAlmostEqual(
                json.load(open(sig))[watch._title_sig_key(entry["title"])]
                ["updated_at"], time.time(), delta=30,
                msg="store did not stamp the re-seed time")

    def test_reseed_stamps_now_for_a_real_change_in_the_same_collect(self):
        # #516 Decision 3 — the SWALLOW: the store holds the OLD algo's
        # digest of the OLD content and the live entry's content has ALSO
        # genuinely changed; the re-seed collect must not leave the changed
        # entry carrying its stale prior stamp (the defect the #514 F2
        # design named: cross-algo detection is impossible, so stamp now).
        # PRODUCTION LINE: same re-seed per-entry stamp as above — with a
        # prev_at carry this test reads the PRIOR value, not now.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            old_entry = {"title": "Re-seed swallow", "body": "one\ntwo",
                         "follows": [], "answers": [], "answer": None}
            changed = dict(old_entry, body="one\nTWO CHANGED")
            self.assertNotEqual(
                watch._entry_content_digest(changed),
                watch._entry_content_digest(old_entry),
                "precondition: the word change really alters the digest")
            prior = 1700000000.0
            _write_old_algo_store(d, [old_entry],
                                  stamps={old_entry["title"]: prior})
            live = [dict(changed)]
            watch.track_question_updates(d, live)
            self.assertEqual(self._question_events(d), [],
                             "a re-seed collect must stay silent (#534)")
            self.assertAlmostEqual(live[0].get("updated_at") or 0,
                                   time.time(), delta=30,
                                   msg="swallow: the changed entry kept its "
                                       "stale prior stamp")

    def test_question_updated_wake_is_mode_gated(self):
        # #516 Decision 1 — a REAL content change's question-updated event is
        # a per-kind signal routed under the delivery mode: withheld in
        # batched (the tick's file read IS the drain), fired in instant.
        # The sig store still stamps either way — withholding the wake IS
        # batching, not dropping the change.
        # PRODUCTION LINE: the `if emits_wake("question-updated", target):`
        # gate around the log_event call in track_question_updates. Remove
        # the gate and the batched half fails (the event fires ungated).
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            # PRECONDITION (hollow-check): the posture file really carries
            # the batched axis, or a withhold assertion is unmeaningful.
            self.assertTrue(
                watch.write_posture(d, "idle", "ask", 0, "batched"))
            self.assertEqual(watch.read_posture_file(d)["delivery"],
                             "batched")
            entry = {"title": "Mode-gated epsilon", "body": "first",
                     "follows": [], "answers": [], "answer": None}
            watch.track_question_updates(d, [dict(entry)])  # first sight
            changed = dict(entry, body="first CHANGED")
            self.assertNotEqual(
                watch._entry_content_digest(changed),
                watch._entry_content_digest(entry),
                "precondition: the change really alters the digest")
            live = [dict(changed)]
            watch.track_question_updates(d, live)
            self.assertEqual(self._question_events(d), [],
                             "batched mode did not withhold question-updated")
            self.assertIsInstance(live[0].get("updated_at"), float,
                                  "precondition: the stamp landed even "
                                  "though the wake was withheld")
            # instant mode: the same change shape fires.
            self.assertTrue(
                watch.write_posture(d, "idle", "ask", 0, "instant"))
            changed2 = dict(entry, body="first CHANGED AGAIN")
            watch.track_question_updates(d, [dict(changed2)])
            events = self._question_events(d)
            self.assertEqual(len(events), 1,
                             "instant mode must fire question-updated")
            self.assertIn("Mode-gated epsilon", events[0])

    def test_real_change_after_reseed_emits_one_event(self):
        # #534 acceptance: after a silent re-seed the channel keeps its teeth
        # — a REAL content change still emits exactly ONE question-updated
        # event (the re-seed must not swallow genuine changes forever).
        # PRODUCTION LINE: the re-seed must stamp the store current so the
        # NEXT collect takes the normal compare path. Sabotage the re-seed to
        # leave the store un-stamped and every later collect re-seeds again,
        # swallowing the real change (zero events => this fails).
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            entry = {"title": "Re-seed gamma", "body": "first\nsecond",
                     "follows": [], "answers": [], "answer": None}
            self.assertNotEqual(_old_algo_digest(entry),
                                watch._entry_content_digest(entry),
                                "precondition: old/new digests differ")
            _write_old_algo_store(d, [entry])
            watch.track_question_updates(d, [dict(entry)])  # silent re-seed
            self.assertEqual(self._question_events(d), [])

            # a REAL content change (different words), not an algorithm flip.
            changed = dict(entry, body="first\nSECOND CHANGED")
            self.assertNotEqual(
                watch._entry_content_digest(changed),
                watch._entry_content_digest(entry),
                "precondition: the word change really alters the digest")
            watch.track_question_updates(d, [changed])
            events = self._question_events(d)
            self.assertEqual(len(events), 1,
                             "a real change after re-seed must emit one event")
            self.assertIn("Re-seed gamma", events[0])

    def test_collect_reseeds_both_sections_atomically_silently(self):
        # #534 regression: collect() processes the OPEN and ANSWERED sections
        # over one shared store. An earlier two-call design re-seeded the open
        # entries and stamped the store current while the answered entries
        # still held OLD-algo digests — so the second call compared new
        # digests against stale ones and fired a phantom event per answered
        # entry. collect() now passes both sections to one call, so the re-seed
        # is atomic across sections.
        # PRODUCTION LINE: collect()'s single track_question_updates call. Revert
        # it to two calls and the answered entry phantom-fires on re-seed.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            qpath = os.path.join(d, ".dreamwork", "questions.md")
            open_body = "open line one\nopen line two"   # multi-line => v0!=v1
            ans_body = "answered line one\nanswered line two"
            with open(qpath, "w") as f:
                f.write("# Questions for the human\n\n## Open\n\n"
                        "- **Open re-seed**\n  " + open_body.replace("\n", "\n  ")
                        + "\n\n## Answered\n\n"
                        "- **Answered re-seed -> resolved.**\n  "
                        + ans_body.replace("\n", "\n  ") + "\n")
            parsed = watch.collect(d)  # parse to get the live entry dicts
            open_e = parsed["questions_open"][0]
            ans_e = parsed["answered_entries"][0]
            # PRECONDITION: both entries' old/new digests differ, else the
            # re-seed has nothing to migrate and the phantom can't show.
            self.assertNotEqual(_old_algo_digest(open_e),
                                watch._entry_content_digest(open_e),
                                "precondition: open old/new digests differ")
            self.assertNotEqual(_old_algo_digest(ans_e),
                                watch._entry_content_digest(ans_e),
                                "precondition: answered old/new digests differ")
            # pre-seed a store with OLD-algo digests for BOTH sections.
            _write_old_algo_store(d, [open_e, ans_e])

            data = watch.collect(d)
            self.assertEqual(self._question_events(d), [],
                             "re-seed fired a phantom across sections")
            sig = os.path.join(d, ".dreamwork", watch.QUESTION_SIGS)
            store = json.load(open(sig))
            self.assertEqual(store.get("algo"), watch.SIG_ALGO)
            # BOTH sections' digests migrated to the current algorithm.
            self.assertEqual(
                store[watch._title_sig_key(open_e["title"])]["digest"],
                watch._entry_content_digest(open_e),
                "open entry not re-seeded to the current algo")
            self.assertEqual(
                store[watch._title_sig_key(ans_e["title"])]["digest"],
                watch._entry_content_digest(ans_e),
                "answered entry not re-seeded to the current algo")

    def test_unrecognised_algo_marker_reseeds_silently(self):
        # #534 — a store carrying an algo marker the code does NOT know
        # (a future generation, or a typo) is treated as the oldest known
        # generation and re-seeded to the current one. The only safe thing to
        # do with an unknown algorithm is re-seed; guessing "current" would
        # skip a real upgrade, and the next-oldest known alias would too.
        # PRODUCTION LINE: _store_algo's unknown-marker fallback. Sabotage it
        # to return SIG_ALGO for an unknown marker and the re-seed is skipped,
        # so the store keeps an old-algo digest (assertion fails).
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            entry = {"title": "Re-seed delta", "body": "a\nb\nc",
                     "follows": [], "answers": [], "answer": None}
            self.assertNotEqual(_old_algo_digest(entry),
                                watch._entry_content_digest(entry),
                                "precondition: old/new digests differ")
            _write_old_algo_store(d, [entry], algo="sigtext-future")
            watch.track_question_updates(d, [dict(entry)])
            self.assertEqual(self._question_events(d), [],
                             "unknown algo marker fired a phantom event")
            sig = os.path.join(d, ".dreamwork", watch.QUESTION_SIGS)
            store = json.load(open(sig))
            self.assertEqual(store.get("algo"), watch.SIG_ALGO,
                             "unknown marker did not re-seed to current")

    def test_current_algo_store_is_not_reseeded(self):
        # #534 — a store already stamped current with correct digests takes
        # the NORMAL path: unchanged content emits no event and the store is
        # not pointlessly rewritten. This guards against a re-seed that fires
        # on every collect (which would also swallow real changes — see the
        # sibling "real change after reseed" test).
        # PRODUCTION LINE: the `algo == SIG_ALGO` guard ahead of the re-seed.
        # Sabotage it to re-seed unconditionally and this still passes for the
        # WRONG reason (no events either way) — the discriminating red is the
        # sibling real-change test, which is why both exist.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            entry = {"title": "Current algo", "body": "stable body",
                     "follows": [], "answers": [], "answer": None}
            # write a store already under the CURRENT algo with correct digests
            store = {"algo": watch.SIG_ALGO}
            store[watch._title_sig_key(entry["title"])] = {
                "digest": watch._entry_content_digest(entry),
                "updated_at": None,
                "title": entry["title"],
            }
            sig = os.path.join(d, ".dreamwork", watch.QUESTION_SIGS)
            os.makedirs(os.path.dirname(sig), exist_ok=True)
            with open(sig, "w") as f:
                json.dump(store, f)
            before_mtime = os.path.getmtime(sig)
            time.sleep(0.05)
            watch.track_question_updates(d, [dict(entry)])
            self.assertEqual(self._question_events(d), [],
                             "unchanged current-algo content fired an event")
            # no content change => no write (mtime unchanged).
            self.assertEqual(os.path.getmtime(sig), before_mtime,
                             "current-algo store was pointlessly rewritten")

    def test_answers_health_fault_is_loud_and_path_specific(self):
        self.assertIn("answers channel unreadable", watch.PAGE)
        self.assertIn(".dreamwork%2Fanswers.md", watch.PAGE)
        self.assertIn("d.answers_health === 'unreadable'", watch.PAGE)

    def test_ask_submission_has_structured_client_recovery_mapping(self):
        self.assertIn("'/ask':     b => ({ kind:'ask'", watch.PAGE)
        self.assertIn("title:b.question, text:b.question", watch.PAGE)

    def test_answers_route_and_ask_are_wired(self):
        self.assertIn("function buildAnswers(d)", watch.PAGE)
        self.assertIn("/answers", watch.PAGE)
        self.assertIn("postJSON('/ask'", watch.PAGE)
        self.assertNotIn("fetch('/ask'", watch.PAGE)
        # /ask is dispatched as a write route (WRITE_ROUTE_HANDLERS keys).
        self.assertIn('"/ask": _handle_ask',
                      inspect.getsource(watch.make_handler))

    def test_answers_askbox_ctrl_enter_and_open_visibility_contract(self):
        # #292: Ctrl/Cmd+Enter must reach the ask form, not only cards/composer.
        self.assertIn("t.id === 'askbox'", watch.PAGE)
        self.assertIn("askform", watch.PAGE)
        self.assertIn("askInFlight", watch.PAGE)
        self.assertIn("if (askInFlight) return;", watch.PAGE)
        self.assertIn("function invalidateAskFlight", watch.PAGE)
        self.assertIn("invalidateAskFlight()", watch.PAGE)
        self.assertIn("view.name !== 'answers'", watch.PAGE)
        self.assertIn("'/answers'", watch.PAGE)  # navigate URL + isInternal
        # #293: open answer rows must not permanently carry the enter-snap pose.
        self.assertNotIn('class="aq open dreamin"', watch.PAGE)
        self.assertIn('data-aqid=', watch.PAGE)
        self.assertIn("function revealNewOpenAsks", watch.PAGE)
        self.assertIn(".aq.open .qt", watch.PAGE)
        self.assertIn("open_answer_aid", inspect.getsource(watch))

    def test_open_answer_aid_distinguishes_title_twins(self):
        text = (
            "# Questions for the dreamer\n\n## Open\n\n"
            "- **2026-07-27 — Twin title**\n  body alpha\n\n"
            "- **2026-07-27 — Twin title**\n  body beta\n\n"
            "## Answered\n"
        )
        items = watch.parse_open_answers(text)
        self.assertEqual(len(items), 2)
        self.assertTrue(all(i.get("aid", "").startswith("open:") for i in items))
        self.assertNotEqual(items[0]["aid"], items[1]["aid"])
        # exact twins get ordinals, still unique
        twin = (
            "# Questions for the dreamer\n\n## Open\n\n"
            "- **Same**\n  exact\n\n"
            "- **Same**\n  exact\n\n"
            "## Answered\n"
        )
        t2 = watch.parse_open_answers(twin)
        self.assertEqual(len(t2), 2)
        self.assertNotEqual(t2[0]["aid"], t2[1]["aid"])

    def test_answers_channel_parse_append_collect(self):
        text = ("# Questions for the dreamer\n\n## Open\n\n"
                "- **2026-07-26 — Why?** Human context.\n\n"
                "## Answered\n\n- **Old?** → answered (2026-07-26): Loop reply.\n")
        self.assertEqual(watch.parse_open_answers(text)[0]["title"],
                         "2026-07-26 — Why?")
        self.assertEqual(watch.parse_answered_answers(text)[0]["when"],
                         "2026-07-26")
        hostile = "Can this work?\n## forged\n- **fake entry**\nAll my words."
        new = watch.append_human_question(text, hostile, "2026-07-26")
        self.assertIn("- **2026-07-26 — Can this work?**", new)
        parsed = watch.parse_open_answers(new)
        self.assertEqual(len(parsed), 2)
        self.assertIn("## forged", parsed[-1]["body"])
        self.assertIn("fake entry", parsed[-1]["body"])
        self.assertIn("All my words.", parsed[-1]["body"])
        self.assertEqual(watch.answers_health(text, 2), "ok")
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            with open(os.path.join(d, ".dreamwork", "answers.md"), "w") as f:
                f.write(text)
            data = watch.collect(d)
            self.assertEqual(len(data["answers_open"]), 1)
            self.assertEqual(len(data["answers_answered"]), 1)

    def test_answered_answers_aid_stable_across_reorder(self):
        # #238: content identity, not position — swap order, same body keeps id
        a = ("# Q\n\n## Answered\n\n"
             "- **Duplicate?** → answered (2026-07-26): first loop answer.\n\n"
             "- **Duplicate?** → answered (2026-07-26): second loop answer.\n")
        b = ("# Q\n\n## Answered\n\n"
             "- **Duplicate?** → answered (2026-07-26): second loop answer.\n\n"
             "- **Duplicate?** → answered (2026-07-26): first loop answer.\n")
        pa, pb = watch.parse_answered_answers(a), watch.parse_answered_answers(b)
        self.assertEqual(len(pa), 2)
        self.assertNotEqual(pa[0]["aid"], pa[1]["aid"])
        by_body_a = {x["body"].strip(): x["aid"] for x in pa}
        by_body_b = {x["body"].strip(): x["aid"] for x in pb}
        self.assertEqual(by_body_a, by_body_b)
        # aids are namespaced digests, never positional a+i
        for x in pa:
            self.assertTrue(x["aid"].startswith("ans:"))
            self.assertNotRegex(x["aid"], r"^a\d+$")

    def test_answered_answers_aid_unique_for_exact_duplicates(self):
        twin = ("# Q\n\n## Answered\n\n"
                "- **Same** → answered (2026-07-26): identical body.\n\n"
                "- **Same** → answered (2026-07-26): identical body.\n")
        items = watch.parse_answered_answers(twin)
        self.assertEqual(len(items), 2)
        self.assertNotEqual(items[0]["aid"], items[1]["aid"])
        # deterministic: re-parse yields the same pair in the same order
        again = watch.parse_answered_answers(twin)
        self.assertEqual([x["aid"] for x in items], [x["aid"] for x in again])

    def test_answers_open_state_rides_data_keep_seam(self):
        # #238: no third snapshot path; answered details carry data-keep=aid
        self.assertIn('data-keep="${id}"', watch.PAGE)
        self.assertIn("e.aid", watch.PAGE)
        self.assertIn("data-aid", watch.PAGE)
        self.assertIn("'data-aid'", watch.PAGE)  # ghost strip list
        self.assertNotIn("answerRecord(e, true, 'a' + i)", watch.PAGE)

    def test_answer_record_missing_aid_omits_both_attrs(self):
        # #247: fail closed — missing aid must not emit empty data-aid/data-keep
        # (empty keys collide folds/FLIP) and must not emit a shared sentinel
        # as an id *value*. Branch-order in PAGE + node execution of the
        # extracted answerRecord (real renderer output, not fabricated HTML).
        import re, subprocess, json, textwrap
        page = watch.PAGE
        self.assertIn("if (!e.aid)", page)
        self.assertNotIn("e.aid || ''", page)
        start = page.index("function answerRecord(e, answered=false)")
        end = page.index("function buildAnswers", start)
        fn = page[start:end].rstrip()
        # no sentinel as a literal id value (comments may name the anti-pattern)
        self.assertNotIn("'ans:missing'", fn)
        self.assertNotIn('"ans:missing"', fn)
        self.assertNotIn("`ans:missing`", fn)
        with_attrs = 'data-aid="${id}" data-keep="${id}"'
        self.assertIn(with_attrs, fn)
        i_branch = fn.index("if (!e.aid)")
        i_plain = fn.index(
            'return `<details class="aq answered"><summary>${esc(e.title)}</summary>`',
            i_branch)
        i_with = fn.index(with_attrs, i_branch)
        self.assertLess(i_plain, i_with)
        script = textwrap.dedent("""\
            const esc = s => String(s ?? '').replace(/&/g,'&amp;')
              .replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
            const mdB = s => s;
            %s
            const missing = answerRecord({title:'T', body:'B'}, true);
            const present = answerRecord(
              {title:'T', body:'B', aid:'ans:deadbeef'}, true);
            process.stdout.write(JSON.stringify({missing, present}));
        """) % fn
        out = subprocess.check_output(["node", "-e", script], text=True)
        rendered = json.loads(out)
        self.assertEqual(
            rendered["missing"],
            '<details class="aq answered"><summary>T</summary>'
            '<div class="aqbody">B</div></details>')
        self.assertNotIn("data-aid", rendered["missing"])
        self.assertNotIn("data-keep", rendered["missing"])
        self.assertIn('data-aid="ans:deadbeef"', rendered["present"])
        self.assertIn('data-keep="ans:deadbeef"', rendered["present"])

    def test_missing_aid_answered_has_listless_expand_fallback(self):
        # #250: EXPAND_SURFACES preventDefault on .aq.answered > summary must
        # not leave missing-aid details dead when host[data-aid] misses.
        page = watch.PAGE
        self.assertIn("listlessFallback: true", page)
        self.assertIn("function foldDetailsLocal(det)", page)
        self.assertIn("if (m.listlessFallback) foldDetailsLocal(det)", page)
        # still fail-closed on attrs — no sentinel keep key for missing aid
        self.assertNotIn('data-keep="ans:missing"', page)
        self.assertNotIn("data-keep=\"\"", page)
        # keyed path remains for real aids
        self.assertIn(".aq.answered[data-aid]", page)
        self.assertIn("ANSWER_LIST", page)

    def test_answer_record_aid_doc_states_twin_deletion_fail_closed(self):
        # #247: exact-content twin ordinal renumbers on earlier twin deletion
        doc = watch.answer_record_aid.__doc__ or ""
        self.assertIn("Exact-content twin limitation", doc)
        self.assertIn("renumbers", doc)
        self.assertIn("fails closed", doc)

    def test_atomic_write_text_replaces_and_leaves_no_temp(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "answers.md")
            watch.atomic_write_text(path, "durable\n")
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), "durable\n")
            self.assertEqual(os.listdir(d), ["answers.md"])

    def test_parse_open_questions(self):
        qs = watch.parse_open_questions(QUESTIONS)
        self.assertEqual(len(qs), 1)
        self.assertEqual(qs[0]["title"], "A real open question?")
        self.assertIn("context here", qs[0]["body"])
        self.assertIsNone(qs[0]["answer"])          # unanswered
        self.assertEqual(watch.parse_open_questions(None), [])

    def test_parse_open_questions_answer_awaiting_fold(self):
        # a submitted-but-unfolded answer is lifted into `answer`, kept out of
        # `body`, and never swallows the questions that follow it (#81).
        text = ("# Q\n\n## Open\n\n"
                "- **First?** ctx one.\n"
                "  - **Answer (via watch, 2026-07-25 07:00):** go with A.\n"
                "- **Second?** ctx two.\n\n"
                "## Answered\n\n- **Old** done.\n")
        qs = watch.parse_open_questions(text)
        self.assertEqual([q["title"] for q in qs], ["First?", "Second?"])
        self.assertEqual(qs[0]["answer"], "go with A.")
        self.assertNotIn("Answer (via watch", qs[0]["body"])
        self.assertIsNone(qs[1]["answer"])
        # the badge counts only what still needs the human
        self.assertEqual(watch.open_question_count(text), 1)

    def test_append_answer(self):
        new, matched = watch.append_answer(
            QUESTIONS, "A real open question?", "yes do it", "2026-07-25")
        self.assertTrue(matched)
        self.assertIn("**Answer (via watch, 2026-07-25):** yes do it", new)
        # answer lands inside Open, before the Answered section
        self.assertLess(new.index("Answer (via watch"),
                        new.index("## Answered"))
        _new, matched = watch.append_answer(
            QUESTIONS, "No such question", "x", "2026-07-25")
        self.assertFalse(matched)

    def test_append_answer_last_open_entry(self):
        # the answer block must land inside Open even when the target is
        # the final entry before the Answered header
        text = ("# Q\n\n## Open\n\n- **Only question?** ctx.\n\n"
                "## Answered\n\n- **Old** done.\n")
        new, matched = watch.append_answer(text, "Only question?",
                                           "yes", "2026-07-25")
        self.assertTrue(matched)
        self.assertLess(new.index("Answer (via watch"),
                        new.index("## Answered"))

    def test_append_comment_open_and_answered(self):
        text = ("# Q\n\n## Open\n\n- **Open one?** ctx.\n\n"
                "## Answered\n\n- **Done one** resolved.\n")
        new, matched = watch.append_comment(text, "Open one?", "a thought",
                                            "2026-07-25 08:00", "Open")
        self.assertTrue(matched)
        self.assertIn(
            "**Note (human, via watch, 2026-07-25 08:00):** a thought", new)
        # a follow-up on an Answered entry lands in the Answered section
        new2, matched2 = watch.append_comment(text, "Done one", "amend it",
                                              "2026-07-25 08:01", "Answered")
        self.assertTrue(matched2)
        self.assertGreater(new2.index("Note (human"),
                           new2.index("## Answered"))
        _n, m3 = watch.append_comment(text, "Nope", "x", "2026-07-25", "Open")
        self.assertFalse(m3)

    def test_append_lands_inside_the_entry_not_after_the_blank(self):
        # #149. The block belongs at the end of the ENTRY, which is above the
        # blank line separating it from what follows. Appending straight onto
        # `out` put it below that blank — detached from its entry and flush
        # against the next `## `, which is not the shape file-formats.md
        # documents.
        text = ("# Q\n\n## Open\n\n- **Open one?** ctx.\n\n"
                "## Answered\n\n- **Done one** resolved.\n")
        new, matched = watch.append_comment(text, "Open one?", "a thought",
                                            "2026-07-25 08:00", "Open")
        self.assertTrue(matched)
        lines = new.splitlines()
        i = next(j for j, ln in enumerate(lines) if "a thought" in ln)
        # attached to its entry above...
        self.assertTrue(lines[i - 1].startswith("- **Open one?**"))
        # ...and still separated from the next section below
        self.assertEqual(lines[i + 1].strip(), "")
        self.assertEqual(lines[i + 2], "## Answered")
        # the same at end of file, where the trailing newline is the blank
        tail = "# Q\n\n## Open\n\n- **Last one?** ctx.\n\n"
        new2, m2 = watch.append_comment(tail, "Last one?", "at the end",
                                        "2026-07-25 08:01", "Open")
        self.assertTrue(m2)
        l2 = new2.splitlines()
        j = next(k for k, ln in enumerate(l2) if "at the end" in ln)
        self.assertTrue(l2[j - 1].startswith("- **Last one?**"))
        # and it round-trips: the reader still sees exactly one entry with
        # exactly one note (a structural check, not a glance — this is a file
        # whose structure is data)
        entries = watch.parse_open_questions(new2)
        self.assertEqual(len(entries), 1)
        self.assertEqual(len(entries[0]["follows"]), 1)

    def test_parse_follows_and_answered(self):
        text = ("# Q\n\n## Open\n\n"
                "- **First?** ctx.\n"
                "  - **Follow-up (via watch, 2026-07-25 08:00):** note one.\n"
                "- **Second?** ctx2.\n\n"
                "## Answered\n\n"
                "- **Old** resolved.\n"
                "  - **Follow-up (via watch, 2026-07-25 08:10):** reopen?\n")
        qs = watch.parse_open_questions(text)
        self.assertEqual([q["title"] for q in qs], ["First?", "Second?"])
        self.assertEqual(qs[0]["follows"],
                         [{"text": "note one.", "author": "human",
                           "when": "2026-07-25 08:00"}])
        self.assertNotIn("Follow-up", qs[0]["body"])
        ans = watch.parse_answered(text)
        self.assertEqual([e["title"] for e in ans], ["Old"])
        self.assertEqual(ans[0]["follows"],
                         [{"text": "reopen?", "author": "human",
                           "when": "2026-07-25 08:10"}])
        self.assertNotIn("Follow-up", ans[0]["body"])

    def test_answered_at_reads_the_resolution_head_only(self):
        # #111: collapsed, a folded entry states WHEN it was answered, so the
        # date has to come from the resolution the loop wrote — and only from
        # there. A wrong date is worse than no date, so this never guesses.
        cases = [
            ('→ resolved (2026-07-25): body text.', '2026-07-25'),
            ('→ "rec" via watch (2026-07-25 09:13): all of it.',
             '2026-07-25 09:13'),
            ('→ Default applied (2026-07-25). Prose after a full stop.',
             '2026-07-25'),
            # the file is written at ~72 columns, so the timestamp itself
            # routinely wraps mid-parenthesis
            ('→ "rec" via watch (2026-07-25\n09:14): wrapped.',
             '2026-07-25 09:14'),
        ]
        for body, want in cases:
            self.assertEqual(watch.answered_at(body), want, body)
        # a date that is not the resolution head is somebody else's date
        self.assertIsNone(watch.answered_at(
            'no arrow here, but a date (2026-07-25) further in.'))
        self.assertIsNone(watch.answered_at(
            '→ resolved: no timestamp at all, then (2026-07-25) later.'))
        self.assertIsNone(watch.answered_at(''))
        self.assertIsNone(watch.answered_at(None))

    def test_answered_at_finds_the_head_on_a_later_body_line(self):
        """#411 — two answered entries begin with an artifact-pointer line and
        carry the `→ answered (…)` marker on the SECOND body line. Anchoring
        at the body's absolute start (the \\A anchor) dropped a date they plainly
        carried; the marker is line-anchored (^ + re.M) so it is still found only
        at a line start and `.search` still returns the FIRST one — a date further
        down the body is never read. The real live shapes, verbatim."""
        # #233 LAN binding, verbatim first two body lines (wraps at ~72 cols)
        lan = ("The threat-model review is at\n"
               "  → answered (2026-07-26 17:49): Approved A: ship explicit\n"
               "  trusted-LAN mode.\n")
        self.assertEqual(watch.answered_at(lan), "2026-07-26 17:49")
        # #229 threaded topic chats, verbatim first two body lines
        tc = ("The reviewed artifact is at\n"
              "  → answered (2026-07-26 17:11): Revision directed, not\n"
              "  approved.\n")
        self.assertEqual(watch.answered_at(tc), "2026-07-26 17:11")
        # an indented marker still counts — the file writes at 2-space indent
        self.assertEqual(
            watch.answered_at("  → resolved (2026-07-25 09:00): ok.\n"),
            "2026-07-25 09:00")

    def test_answered_at_returns_none_when_a_date_has_no_resolution_arrow(self):
        """#411 — the never-guess half. A date that is not behind a `→`
        resolution head is prose, not a verdict, so it returns None even when
        a date is unambiguously present. This is the rule that makes widening
        the pattern dangerous: a wider pattern that finds a date anywhere in
        the body would manufacture a wrong date for withdrawn entries."""
        # withdrawn shape: the verdict is in the TITLE, the body opens with the
        # reasoning and carries NO arrow head anywhere
        withdrawn = ("decided by the loop, and withdrawn as an ask.\n"
                     "  Rec (b) stands — never landed.\n")
        self.assertIsNone(watch.answered_at(withdrawn))
        # a date with no arrow anywhere is not a resolution
        self.assertIsNone(
            watch.answered_at("Some prose mentioning 2026-07-25 in passing.\n"))
        # a date on a later line with no `→` is still not a resolution head
        self.assertIsNone(
            watch.answered_at("First line.\n  Closed on (2026-07-25).\n"))

    def test_a_retained_answer_bullet_is_his_contribution_not_body_prose(self):
        """#340 — his answer rendered as unattributed prose on 22 of 36 entries.

        Under `## Answered` the parser runs with `lift_answer=False`, so an
        `Answer (via watch…)` bullet matched `ANSWER_TAGS` but not `NOTE_TAGS`,
        `note_author` returned None, and it fell through to the
        `startswith("- ")` branch straight into `body` — rendered by `mdB` as a
        `·` item with its raw author tag visible as text and NO `you` label. His
        words lost their attribution while looking like loop prose (#109 made
        that a correctness matter, not a cosmetic one).

        The production line is `author = answer_by` when not lifting, in
        `_parse_entries`. Remove it and the first two assertions fail.

        The fix is deliberately NOT `lift_answer=True` here, and this test pins
        why: `answered_at()` reads the `→ answered` head out of `body`, and two
        call sites depend on it, so lifting would create a second place for the
        same fact to live. The third assertion is that guard — the head must
        still parse after the bullet is re-homed.
        """
        text = (
            "## Open\n"
            "## Answered\n"
            "- **P1 · 2026-07-27 — a question he answered**\n"
            "  → answered (2026-07-27 23:39): **took the rec.**\n"
            "  - **Note (human, via watch, 2026-07-27 22:00):** thinking aloud\n"
            "  - **Answer (via watch, 2026-07-27 23:39):** rec, ship it\n"
            "  - **Follow-up (loop, 2026-07-27 23:41):** folded\n"
        )
        items = watch.parse_answered(text)
        self.assertEqual(len(items), 1)
        entry = items[0]

        mine = [f for f in entry["follows"] if f["author"] == "human"]
        texts = [f["text"] for f in mine]
        self.assertIn("rec, ship it", texts,
                      "his answer is not a contribution: %r" % (entry["follows"],))
        # ...and it must not ALSO be sitting in the body with its raw tag.
        for prefix, _ in watch.ANSWER_TAGS:
            self.assertNotIn(prefix, entry["body"],
                             "the raw answer tag is still rendered as body prose")
        # The guard against the obvious one-argument fix: the resolution head
        # `answered_at` reads must survive in `body`, unmoved.
        self.assertEqual(entry["when"], "2026-07-27 23:39")
        self.assertEqual(watch.answered_at(entry["body"]), "2026-07-27 23:39")

        # Order is preserved, which is what makes the thread readable (#128):
        # the note he wrote first, then his answer, then the loop's fold.
        self.assertEqual([f["author"] for f in entry["follows"]],
                         ["human", "human", "loop"])

        # PRECONDITION, derived rather than pinned: the fixture must actually
        # contain an answer bullet and a resolution head, or every assertion
        # above passes over an entry that never exercised the branch.
        self.assertTrue(any(p in text for p, _ in watch.ANSWER_TAGS))
        self.assertIn("→ answered (", text)

        # And Open must be UNAFFECTED: there the answer is still lifted out,
        # because that is what distinguishes answered-awaiting-fold.
        open_text = text.replace("## Answered", "## Zzz").replace("## Open", "## Answered").replace("## Zzz", "## Open")
        opened = watch._parse_entries(open_text, "Open", lift_answer=True)
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0]["answer"], "rec, ship it")
        self.assertEqual([f["author"] for f in opened[0]["follows"]],
                         ["human", "loop"])

    def test_sub_when_reads_the_tag_head_only(self):
        # #128: a note's stamp decides whether it reads as a reply to an
        # answer or as the thing the answer replied to, so it is parsed — and
        # like note_author it never guesses.
        cases = [
            ("- **Note (human, via watch, 2026-07-25 09:00):** x",
             "2026-07-25 09:00"),
            ("- **Follow-up (via watch, 2026-07-25):** x", "2026-07-25"),
            ("- **Answer (via watch, 2026-07-25 10:47):** rec lgtm",
             "2026-07-25 10:47"),
        ]
        for line, want in cases:
            self.assertEqual(watch.sub_when(line), want, line)
        # a date in the note's own TEXT is somebody else's date
        self.assertIsNone(watch.sub_when(
            "- **Follow-up (loop, t):** we agreed on (2026-07-25) for this."))
        self.assertIsNone(watch.sub_when("- **Note (human, via watch, t):** x"))

    def test_parse_keeps_the_answers_place_among_the_notes(self):
        # #128 — the bug: lifting the answer out of the sub-bullets discarded
        # WHERE it sat, so the same entry parsed identically whichever order
        # its sub-bullets were written in, and the card hoisted the answer
        # above a note from two hours earlier. That reads as him replying to
        # himself, and no rendering fix could have reached it.
        head = "# Q\n\n## Open\n\n- **T.** body.\n"
        note = "  - **Note (human, via watch, 2026-07-25 08:51):** earlier.\n"
        ans = "  - **Answer (via watch, 2026-07-25 10:47):** rec lgtm\n"
        after = watch.parse_open_questions(head + note + ans)[0]
        before = watch.parse_open_questions(head + ans + note)[0]
        self.assertNotEqual(after, before)
        # one note preceded the answer; in the other order, none did
        self.assertEqual(after["answer_at"], 1)
        self.assertEqual(before["answer_at"], 0)
        for q in (after, before):
            self.assertEqual(q["answer"], "rec lgtm")
            self.assertEqual(q["answer_when"], "2026-07-25 10:47")
            # an answer typed on the page is HIS, and the page says so in the
            # same vocabulary his notes do (#109 symmetry)
            self.assertEqual(q["answer_by"], "human")
        # an entry with no answer carries the fields, unset — the card reads
        # them, and a missing key would make "no resolution" indistinguishable
        # from an older parse
        plain = watch.parse_open_questions(head + note)[0]
        self.assertEqual(
            [plain["answer"], plain["answer_at"], plain["answer_when"],
             plain["answer_by"]], [None, None, None, None])

    def test_a_second_answer_does_not_overwrite_the_first(self):
        """#446 — a second `Answer (via watch…)` under an Open question used to
        REPLACE the first at parse time, so the earlier text was lost before
        any render rule ran. questions.md is the durable record of what the
        human decided; a silent overwrite there is the worst class of bug this
        system can have, because the loop cannot know what it forgot.

        A second answer is a subsequent answer from the human, retained in file
        order — the parser does not rank or interpret (amendment vs correction
        vs re-open); it keeps every one. The first stays the thread's
        resolution anchor (the `answer_at` cut), so the single-field callers
        are unchanged; `answers` carries every answer for the page to show.

        Production line whose reversion reds this test: the `is_answer` branch
        in `_parse_entries` must retain every answer (append to `answers`),
        not assign single fields over the previous one. Remove the append and
        the first answer is gone from the parsed structure entirely — not in
        `answer`, not in `follows`, nowhere.

        The fixture's two answer texts are derived values asserted to differ,
        never a count of 2: a count passes on a parse that kept the wrong one
        or kept one twice.
        """
        first_txt, first_when = "go with A — first answer", "2026-07-25 09:00"
        second_txt, second_when = "no, B — changed my mind", "2026-07-25 10:00"
        # PRECONDITION, derived: the two answers must actually differ, or every
        # retrieval assertion below passes over a fixture that never exercised
        # the overwrite. A literal tuned to today's strings is a check with an
        # invisible expiry date.
        self.assertNotEqual(first_txt, second_txt)

        text = ("# Q\n\n## Open\n\n"
                "- **Which option?** body.\n"
                "  - **Note (human, via watch, 2026-07-25 08:00):** a note.\n"
                f"  - **Answer (via watch, {first_when}):** {first_txt}\n"
                "  - **Note (human, via watch, 2026-07-25 09:30):** between.\n"
                f"  - **Answer (via watch, {second_when}):** {second_txt}\n"
                "\n## Answered\n\n- **Old** done.\n")
        q = watch.parse_open_questions(text)[0]

        # BOTH answers retrievable from `answers`, each attributed and stamped,
        # in file order. This is the whole fix — his words are not lost. `.get`
        # so the red names the substance ("first answer lost") rather than a
        # missing key, and so a parser that keeps the wrong one still fails.
        ans = q.get("answers") or []
        texts = [a["text"] for a in ans]
        self.assertIn(first_txt, texts, "first answer lost: %r" % (ans,))
        self.assertIn(second_txt, texts, "second answer lost: %r" % (ans,))
        self.assertEqual(texts.index(first_txt), texts.index(second_txt) - 1,
                         "answers not in file order: %r" % (texts,))
        by_first = next(a for a in ans if a["text"] == first_txt)
        by_second = next(a for a in ans if a["text"] == second_txt)
        self.assertEqual(by_first["by"], "human")
        self.assertEqual(by_second["by"], "human")
        self.assertEqual(by_first["when"], first_when)
        self.assertEqual(by_second["when"], second_when)
        # each answer records where it sat among the notes (#128, per-answer):
        # one note preceded the first; two preceded the second.
        self.assertEqual(by_first["at"], 1)
        self.assertEqual(by_second["at"], 2)

        # The single fields stay the FIRST answer's projection — the resolution
        # anchor — so every existing caller (qaState truthiness, the thread cut
        # at `answer_at`, open_question_count) is unchanged. first == anchor.
        self.assertEqual(q["answer"], first_txt)
        self.assertEqual(q["answer_when"], first_when)
        self.assertEqual(q["answer_by"], "human")
        self.assertEqual(q["answer_at"], 1)
        # neither answer leaks into the body or the thread (still lifted)
        self.assertNotIn("Answer (via watch", q["body"])
        self.assertNotIn(first_txt, " ".join(f["text"] for f in q["follows"]))
        self.assertNotIn(second_txt, " ".join(f["text"] for f in q["follows"]))

        # the badge still counts this as answered-awaiting-fold (one entry)
        self.assertEqual(watch.open_question_count(text), 0)

    def test_an_entry_with_no_answer_carries_an_empty_answers_list(self):
        # the page reads `answers`; a missing key would make "no resolution"
        # indistinguishable from an older parse, exactly like the single fields
        text = "# Q\n\n## Open\n\n- **Q?** body.\n"
        q = watch.parse_open_questions(text)[0]
        self.assertEqual(q["answers"], [])

    def test_answer_authorship_never_guesses(self):
        self.assertEqual(
            watch.answer_author("- **Answer (via watch, t):** x"), "human")
        self.assertIsNone(watch.answer_author("- **Answer (somehow, t):** x"))
        self.assertIsNone(watch.answer_author("- **Note (human, via watch):** x"))

    def test_parse_answered_carries_when(self):
        text = ("# Q\n\n## Answered\n\n"
                "- **Dated** → Confirmed (2026-07-25 06:54): why.\n"
                "- **Undated** → resolved, no timestamp: why.\n")
        ans = watch.parse_answered(text)
        self.assertEqual([e["title"] for e in ans], ["Dated", "Undated"])
        self.assertEqual(ans[0]["when"], "2026-07-25 06:54")
        self.assertIsNone(ans[1]["when"])

    def test_parse_keeps_wrapped_subbullet_continuations(self):
        # #102: the loop hard-wraps at ~72 columns, so a sub-bullet routinely
        # spans several lines. Capturing only the first line truncated the
        # note AND spilled its tail into the body as orphaned prose.
        text = ("# Q\n\n## Open\n\n"
                "- **First?** body line one\n"
                "  body line two\n"
                "  - **Answer (via watch, 2026-07-25 08:00):** an answer that\n"
                "    runs onto a second line.\n"
                "  - **Follow-up (via watch, 2026-07-25 08:05):** a note that\n"
                "    also wraps, twice\n"
                "    over.\n"
                "- **Second?** ctx2.\n\n"
                "## Answered\n\n"
                "- **Old** resolved.\n"
                "  - **Follow-up (via watch, 2026-07-25 08:10):** reopened for\n"
                "    a reason.\n")
        qs = watch.parse_open_questions(text)
        self.assertEqual([q["title"] for q in qs], ["First?", "Second?"])
        self.assertEqual(qs[0]["answer"], "an answer that runs onto a second line.")
        self.assertEqual(qs[0]["follows"],
                         [{"text": "a note that also wraps, twice over.",
                           "author": "human", "when": "2026-07-25 08:05"}])
        # the tails belong to their bullet, never to the body
        for stray in ("runs onto", "also wraps", "over."):
            self.assertNotIn(stray, qs[0]["body"])
        self.assertIn("body line two", qs[0]["body"])
        self.assertEqual(watch.parse_answered(text)[0]["follows"],
                         [{"text": "reopened for a reason.",
                           "author": "human", "when": "2026-07-25 08:10"}])

    def test_parse_unrecognised_subbullet_never_joins_the_previous(self):
        # An in-session follow-up (written by the loop, not via watch) is not
        # a thread entry — it stays in the body. It must not be absorbed as a
        # continuation of the via-watch bullet above it.
        text = ("# Q\n\n## Open\n\n"
                "- **First?** ctx.\n"
                "  - **Follow-up (via watch, 2026-07-25 08:00):** typed here\n"
                "    and wrapped.\n"
                "  - **Follow-up (in-session, 2026-07-25 ~10:10):** written by\n"
                "    the loop instead.\n")
        q = watch.parse_open_questions(text)[0]
        # both are notes now (#109) — the in-session one is the LOOP's, and
        # it must not be absorbed as a continuation of the human's above it
        self.assertEqual([f["text"] for f in q["follows"]],
                         ["typed here and wrapped.", "written by the loop instead."])
        self.assertEqual([f["author"] for f in q["follows"]], ["human", "loop"])

    def test_parse_wrapped_title(self):
        # #116: the loop writes this file wrapped at ~72 columns, so a bold
        # title that spans lines is normal input. It closes at its `**`
        # wherever that falls, and its tail is body — not literal asterisks.
        text = ("# Q\n\n## Open\n\n"
                "- **2026-07-25 — the shader's ambient density changed, and\n"
                "  you did not ask for it.** Fixing the world-space anchoring\n"
                "  required dropping the per-viewport normalisation.\n")
        q = watch.parse_open_questions(text)[0]
        self.assertEqual(
            q["title"],
            "2026-07-25 — the shader's ambient density changed, and "
            "you did not ask for it.")
        self.assertIn("Fixing the world-space anchoring", q["body"])
        self.assertNotIn("**", q["body"])          # no leaked markers
        self.assertNotIn("ask for it", q["body"])  # the title is not body

    def test_wrapped_title_never_swallows_the_next_entry(self):
        # The load-bearing invariant: a top-level `- **` ALWAYS starts an
        # entry, so an unterminated title cannot absorb the entry after it
        # and make one silently vanish from the page.
        text = ("# Q\n\n## Open\n\n"
                "- **A title that wraps across\n"
                "  two lines.** body of the first.\n"
                "- **Second entry.** body of the second.\n"
                "- **Third entry.** body of the third.\n")
        qs = watch.parse_open_questions(text)
        self.assertEqual([q["title"] for q in qs],
                         ["A title that wraps across two lines.",
                          "Second entry.", "Third entry."])
        self.assertNotIn("Second entry", qs[0]["body"])
        # ...even when the title never closes at all
        broken = ("# Q\n\n## Open\n\n"
                  "- **An unterminated title\n"
                  "- **Next entry.** body.\n")
        self.assertEqual([q["title"] for q in watch.parse_open_questions(broken)],
                         ["An unterminated title", "Next entry."])

    def test_append_subbullet_matches_a_wrapped_title(self):
        # The writer must find an entry exactly the way the reader named it,
        # or /answer and /comment silently fail on an entry plainly on screen.
        text = ("# Q\n\n## Open\n\n"
                "- **A title that wraps across\n"
                "  two lines.** body of the first.\n"
                "- **Second entry.** body.\n")
        title = watch.parse_open_questions(text)[0]["title"]
        new, matched = watch.append_comment(text, title, "a note",
                                            "2026-07-25 09:40", "Open")
        self.assertTrue(matched)
        # it lands inside the first entry, before the second
        self.assertLess(new.index("Note (human"), new.index("Second entry"))
        q = watch.parse_open_questions(new)[0]
        # and the reader reads back everything the writer put in the tag,
        # stamp included — when the reader learns a new way to name something,
        # the writer has to still be saying it (#116's lesson, #128's stamp)
        self.assertEqual(q["follows"],
                         [{"text": "a note", "author": "human",
                           "when": "2026-07-25 09:40"}])

    def test_note_authorship(self):
        # #109: four tag forms map to an author; two are legacy and must keep
        # parsing because the file is a record and is never rewritten.
        self.assertEqual(watch.note_author("- **Note (human, via watch, t):** x"),
                         "human")
        self.assertEqual(watch.note_author("- **Follow-up (via watch, t):** x"),
                         "human")
        self.assertEqual(watch.note_author("- **Follow-up (loop, t):** x"), "loop")
        self.assertEqual(watch.note_author("- **Follow-up (in-session, t):** x"),
                         "loop")
        # an unknown tag attributes NOTHING — never guess
        self.assertIsNone(watch.note_author("- **Follow-up (someone, t):** x"))
        self.assertIsNone(watch.note_author("- **A question title.** body"))
        text = ("# Q\n\n## Open\n\n- **T.** body.\n"
                "  - **Note (human, via watch, t1):** his words.\n"
                "  - **Follow-up (loop, t2):** the loop's words.\n")
        # `t1`/`t2` are not timestamps, so `when` is None rather than guessed
        self.assertEqual(watch.parse_open_questions(text)[0]["follows"],
                         [{"text": "his words.", "author": "human",
                           "when": None},
                          {"text": "the loop's words.", "author": "loop",
                           "when": None}])

    def test_collect_lists_only_paths_the_linkifier_may_offer(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            os.makedirs(os.path.join(d, ".dreamwork"), exist_ok=True)
            with open(os.path.join(d, "DREAMWORK.md"), "w") as f:
                f.write("goal")
            with open(os.path.join(d, ".dreamwork", "questions.md"), "w") as f:
                f.write("# Questions for the human\n\n## Open\n\n"
                        "- **Paths.** `DREAMWORK.md`, "
                        "`.dreamwork/questions.md`, `newerrand.py`\n\n"
                        "## Answered\n")

            paths = watch.collect(d)["linkable_paths"]

            self.assertIn("DREAMWORK.md", paths)
            self.assertIn(".dreamwork/questions.md", paths)
            self.assertNotIn("newerrand.py", paths)

    def test_page_shows_note_authorship(self):
        # the human's words sit a step up the text ramp from the loop's, each
        # with a dim label; the accent is not spent on either.
        for token in ("const WHO = { human: 'you', loop: 'loop' }",
                      '.follow.human { color:var(--lit); }',
                      "class=\"who\"", 'f.author'):
            self.assertIn(token, watch.PAGE)

    def test_collect_lists_reviews(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            rd = os.path.join(d, ".dreamwork", "review")
            os.makedirs(rd)
            with open(os.path.join(rd, "plan-review.html"), "w") as f:
                f.write("<!doctype html><p>x")
            with open(os.path.join(rd, "notes.txt"), "w") as f:
                f.write("not an artifact")
            data = watch.collect(d)
            self.assertEqual([r["name"] for r in data["reviews"]],
                             ["plan-review.html"])

    def test_collect_orders_reviews_by_exact_created_ns_then_filename(self):
        # #463 — sort by *created* (birth), not mtime. utime changes mtime
        # without changing birth, so the pre-#463 mtime sort would still
        # reorder after a touch; created sort must not.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            rd = os.path.join(d, ".dreamwork", "review")
            os.makedirs(rd)
            # Create in a known order with short sleeps so birth times
            # differ on filesystems that only resolve birth to 1s.
            order_created = ["a-first.html", "m-mid.html", "z-last.html"]
            for name in order_created:
                path = os.path.join(rd, name)
                with open(path, "w") as f:
                    f.write("<!doctype html><p>x")
                time.sleep(0.02)
            # Touch the oldest so mtime would put it first if we still
            # sorted by mtime — the production-line trap this check reds.
            old = os.path.join(rd, "a-first.html")
            now_ns = time.time_ns()
            os.utime(old, ns=(now_ns, now_ns))

            reviews = watch.collect(d)["reviews"]
            # Runtime precondition: birth is available here, otherwise the
            # created-sort half of the check has no subject.
            known = [r for r in reviews if r["created_known"]]
            self.assertGreaterEqual(
                len(known), 3,
                "need birth time on ≥3 fixtures for created-order (statx "
                "btime unavailable would put every row in the unknown band)")
            names = [r["name"] for r in reviews]
            # Newest created first: z-last, m-mid, a-first — even though
            # a-first now has the newest mtime.
            self.assertEqual(names[:3],
                             ["z-last.html", "m-mid.html", "a-first.html"])
            # PRODUCTION LINE: list_reviews sort key uses created_ns. If it
            # falls back to mtime, a-first (touched) would lead.
            self.assertNotEqual(names[0], "a-first.html")
            # Age seconds for created come from the same ns when known.
            for r in known:
                self.assertEqual(r["created"], r["created_ns"] / 1_000_000_000)
                self.assertEqual(r["mtime"], r["mtime_ns"] / 1_000_000_000)

    def test_review_show_modified_only_when_created_differs(self):
        # #463 part 3 — secondary "modified X ago" only when created ≠ mtime.
        # PRODUCTION LINE: show_modified = known and created_ns != mtime_ns
        # in list_reviews. A fixture with equal times must not claim modified;
        # one we construct with unequal times must.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            rd = os.path.join(d, ".dreamwork", "review")
            os.makedirs(rd)
            same = os.path.join(rd, "same.html")
            with open(same, "w") as f:
                f.write("<!doctype html><p>same")
            diff = os.path.join(rd, "diff.html")
            with open(diff, "w") as f:
                f.write("<!doctype html><p>diff")
            time.sleep(0.05)
            # Pull mtime away from birth on diff only.
            later = time.time_ns() + 5_000_000_000
            os.utime(diff, ns=(later, later))

            reviews = {r["name"]: r for r in watch.collect(d)["reviews"]}
            # Runtime-derived precondition: the inequality we constructed.
            self.assertTrue(reviews["diff.html"]["created_known"])
            self.assertNotEqual(
                reviews["diff.html"]["created_ns"],
                reviews["diff.html"]["mtime_ns"],
                "precondition: constructed created ≠ mtime on diff.html")
            self.assertTrue(reviews["diff.html"]["show_modified"])
            # same.html is the case that killed exact inequality: a file that
            # was never edited still has mtime a few hundred microseconds past
            # birth (create, then write the content), so it IS a candidate —
            # and the row must still not say "modified", which ages() decides
            # by rendered figure. Assert the candidate/verdict split rather
            # than a false equality this filesystem does not give us.
            same = reviews["same.html"]
            if same["created_known"]:
                self.assertGreaterEqual(same["mtime_ns"], same["created_ns"])
                self.assertLess(
                    same["mtime_ns"] - same["created_ns"], 1_000_000_000,
                    "precondition: an unedited file's mtime sits within a "
                    "second of birth, which is why exact inequality is wrong")
                # That both figures RENDER the same, and that the pair is
                # therefore absent, is ageStr's business and belongs where
                # ageStr runs: dev/capture/revieworder.mjs asserts it in the
                # browser. Mirroring the formatter here would be a second copy
                # of it, which is the defect this fix exists to avoid.

    def test_review_created_unknown_does_not_silently_use_mtime(self):
        # #463 — missing birth must be a named state, never mtime-as-created.
        # PRODUCTION LINE: file_created_ns returning None → created_known
        # False and created null; sort key puts unknowns after knowns.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            rd = os.path.join(d, ".dreamwork", "review")
            os.makedirs(rd)
            known_path = os.path.join(rd, "known.html")
            with open(known_path, "w") as f:
                f.write("<!doctype html><p>k")
            unk_path = os.path.join(rd, "unknown.html")
            with open(unk_path, "w") as f:
                f.write("<!doctype html><p>u")
            real = watch.file_created_ns

            def fake_created(path):
                if path.endswith("unknown.html"):
                    return None
                return real(path)

            with unittest.mock.patch.object(
                    watch, "file_created_ns", side_effect=fake_created):
                reviews = watch.list_reviews(rd)
            by = {r["name"]: r for r in reviews}
            self.assertFalse(by["unknown.html"]["created_known"])
            self.assertIsNone(by["unknown.html"]["created"])
            self.assertIsNone(by["unknown.html"]["created_ns"])
            self.assertFalse(by["unknown.html"]["show_modified"])
            # Unknown sorts after known (even if mtime is newer).
            names = [r["name"] for r in reviews]
            if by["known.html"]["created_known"]:
                self.assertLess(names.index("known.html"),
                                names.index("unknown.html"))

    def test_page_emits_created_age_and_modified_secondary(self):
        # Static guard on the production render path for #463 parts 2+3.
        # PRODUCTION LINES: buildDashboard's review age HTML, and ages()'
        # branch on .rmod. A revert of either fails one of these tokens.
        page = watch.PAGE
        self.assertIn("show_modified", page)
        self.assertIn("created_known", page)
        self.assertIn("created unknown", page)
        self.assertIn("class=\"age rmod\"", page)
        self.assertIn("modified ' + s + ' ago'", page)
        self.assertIn("function revealReviewMods(", page)
        # Separator is the chrome's middot, not a second idiom.
        self.assertIn('class="rsep"> · </span>', page)
        # #473 added .age.qup to the same dimmer rule (updated-ago shares
        # the secondary idiom with modified / created-unknown).
        self.assertRegex(
            page, r'\.age\.rmod\s*,\s*\.age\.ageunk(?:\s*,\s*\.age\.qup)?'
                  r'\s*\{[^}]*color\s*:\s*var\(--dimmer\)')

    def test_list_reviews_skips_an_entry_that_vanishes_before_stat(self):
        with tempfile.TemporaryDirectory() as rd:
            path = os.path.join(rd, "gone.html")
            with open(path, "w") as f:
                f.write("<!doctype html><p>x")
            real_stat = os.stat

            def vanishing_stat(candidate, *args, **kwargs):
                if candidate == path:
                    os.unlink(path)
                    raise FileNotFoundError(candidate)
                return real_stat(candidate, *args, **kwargs)

            with unittest.mock.patch.object(watch.os, "stat",
                                            side_effect=vanishing_stat):
                self.assertEqual(watch.list_reviews(rd), [])

    def test_list_reviews_does_not_hide_permission_errors(self):
        with tempfile.TemporaryDirectory() as rd:
            path = os.path.join(rd, "blocked.html")
            with open(path, "w") as f:
                f.write("<!doctype html><p>x")
            with unittest.mock.patch.object(
                    watch.os, "stat", side_effect=PermissionError(path)):
                with self.assertRaises(PermissionError):
                    watch.list_reviews(rd)

    def test_collect_lists_research_built_html_ignoring_src(self):
        # #484 — research artifacts list under `.dreamwork/docs/research/`
        # exactly the way reviews list under `.dreamwork/review/`: the built
        # .html at the directory's root, non-recursively, so a source in
        # `src/` (the one builder's layout, review_artifact.build_path) is
        # never listed — and never served as a half-built page.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            rd = os.path.join(d, ".dreamwork", "docs", "research")
            src = os.path.join(rd, "src")
            os.makedirs(src)
            built = os.path.join(rd, "window-coords.html")
            source = os.path.join(src, "window-coords.html")
            note = os.path.join(rd, "README.md")
            for path in (built, source, note):
                with open(path, "w") as f:
                    f.write("<!doctype html><p>x")
            # Runtime-derived preconditions: both exclusions have a real
            # subject on disk, so "not listed" is the filter's doing, not an
            # empty fixture's.
            self.assertTrue(os.path.isfile(source))
            self.assertTrue(os.path.isfile(note))
            data = watch.collect(d)
            names = [r["name"] for r in data["research"]]
            self.assertEqual(names, ["window-coords.html"])

    def test_collect_research_absent_dir_is_empty_not_error(self):
        # Most loop targets have no research directory yet; the key exists
        # and is empty, mirroring the reviews absent-dir branch.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            self.assertFalse(os.path.isdir(
                os.path.join(d, ".dreamwork", "docs", "research")))
            self.assertEqual(watch.collect(d)["research"], [])

    def test_resolve_confined_nested(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            rd = os.path.join(d, ".dreamwork", "review")
            os.makedirs(rd)
            with open(os.path.join(rd, "a.html"), "w") as f:
                f.write("x")
            ok = watch.resolve_confined(
                d, os.path.join(".dreamwork", "review", "a.html"))
            self.assertTrue(ok and ok.endswith("a.html"))

    def test_resolve_confined(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            ok = watch.resolve_confined(d, "DREAMWORK.md")
            self.assertTrue(ok and ok.endswith("DREAMWORK.md"))
            self.assertIsNone(watch.resolve_confined(d, "../etc/passwd"))
            self.assertIsNone(watch.resolve_confined(d, "/etc/passwd"))
            self.assertIsNone(watch.resolve_confined(d, "~x"))
            self.assertIsNone(watch.resolve_confined(d, ""))
            self.assertIsNone(watch.resolve_confined(d, "."))

    def test_log_event_appends(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            watch.log_event(d, 'answer: "x" -> questions.md')
            watch.log_event(d, 'answer: "y" -> questions.md')
            log = os.path.join(d, ".dreamwork", "watch-events.log")
            with open(log) as f:
                lines = f.read().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertIn('answer: "y"', lines[1])

    def test_command_line(self):
        self.assertEqual(watch.command_line("add-idea", "a thought"),
                         "command via watch: add-idea: a thought")
        self.assertEqual(watch.command_line("do-next", ""),
                         "command via watch: do-next")
        # #527: the receipt id suffix so a drained receipt can be matched
        # to a wake-line it already acted on (F1). Absent when there is no
        # receipt (legacy E2 baseline that commits none).
        self.assertEqual(
            watch.command_line("do-now", "ship it", receipt_id="abc123"),
            "command via watch: do-now: ship it [receipt abc123]")
        self.assertEqual(
            watch.command_line("do-next", "", receipt_id="xyz"),
            "command via watch: do-next [receipt xyz]")
        # the suffix lands AFTER the page hint, not between it and the kind
        self.assertEqual(
            watch.command_line("do-now", "x", "/review?p=p.html", "abc"),
            "command via watch [/review?p=p.html]: do-now: x [receipt abc]")

    def test_command_line_carries_the_page_it_came_from(self):
        # #126: which artifact he was reading is usually the point, so the
        # query string is kept. It sits in brackets, off to the side of the
        # command, because it is a HINT about what he meant and never an
        # instruction.
        self.assertEqual(
            watch.command_line("do-next", "ship it",
                               "/review?p=goal-hierarchies.html"),
            "command via watch [/review?p=goal-hierarchies.html]:"
            " do-next: ship it")
        self.assertEqual(watch.command_line("do-next", "", "/"),
                         "command via watch [/]: do-next")

    def test_from_hint_never_emits_a_hint_it_cannot_vouch_for(self):
        # The line is read by an agent that then ACTS, so a path that could
        # forge structure yields no hint at all — a wrong hint is worse than
        # no hint, the same rule as note_author.
        self.assertEqual(watch.from_hint("/questions"), " [/questions]")
        for bad in ("", None, "questions",            # not a path
                    "http://elsewhere/x",             # not same-origin shaped
                    "/x]: do-now: rm -rf",            # closes its own bracket
                    "/x\nlater command via watch"):   # forges a second line
            self.assertEqual(watch.from_hint(bad), "", repr(bad))
        self.assertEqual(watch.from_hint("/" + "a" * 500), "")

    def test_a_submission_can_never_forge_a_second_event(self):
        # the log is one event per line and he types into a textarea
        self.assertEqual(
            watch.command_line("add-idea", "one\ncommand via watch: do-now: x"),
            "command via watch: add-idea: one command via watch: do-now: x")

    # ── #146: his text cannot forge structure in questions.md ──────────────
    # The same class as the events-log newline (#126), on the more important
    # channel. `/comment` and `/answer` write what he typed straight into the
    # file, so a pasted bullet used to land at column 0 — where the parser's
    # first and best invariant (a top-level `- **` ALWAYS starts an entry,
    # nothing can absorb it) turns it into a question he never asked, with a
    # body the paste invented. That invariant is right and stays; this is the
    # writer's job.
    HOSTILE = ("looks fine\n"
               "- **A question the loop will think you asked.** with a body "
               "it invented, and enough words after it that the wrapper has "
               "somewhere to put a line break.\n"
               "## Answered\n"
               "* another bullet, because the parser ends a note's capture at "
               "any new bullet and his words would fall into the body\n"
               "- short")
    DOC = ("# Q\n\n## Open\n\n- **Real question?** ctx.\n"
           "- **Another open one?** more ctx.\n\n"
           "## Answered\n\n- **Old** → resolved (2026-07-25): done.\n")

    def assert_intact(self, new, note_text):
        """The structural check, which is the point: COUNT the records. A file
        whose structure is data gets counted, not glanced at (lessons.md)."""
        opens = watch.parse_open_questions(new)
        self.assertEqual([q["title"] for q in opens],
                         ["Real question?", "Another open one?"])
        self.assertEqual(len(watch.parse_answered(new)), 1)
        self.assertEqual(new.count("\n## "), 2)     # both section heads, once
        # ...and every word he typed is still HIS, in his own sub-bullet —
        # not leaked into the entry BODY, where it would read as the loop's
        # (#109 is a correctness rule, not a decoration one)
        for frag in ("looks fine", "the loop will think you asked",
                     "another bullet", "short"):
            self.assertIn(frag, note_text, frag)
            self.assertNotIn(frag, opens[0]["body"], frag)
        # no line of the file may start a bullet or a section except the ones
        # that were already there
        for line in new.splitlines():
            if line.startswith("- ") or line.startswith("#"):
                self.assertIn(line.split("**")[1] if "**" in line else line,
                              ("Real question?", "Another open one?", "Old",
                               "# Q", "## Open", "## Answered"), line)

    def test_a_note_can_never_forge_an_entry(self):
        new, matched = watch.append_comment(
            self.DOC, "Real question?", self.HOSTILE, "2026-07-25 12:00")
        self.assertTrue(matched)
        note = watch.parse_open_questions(new)[0]["follows"][-1]
        self.assertEqual(note["author"], "human")
        self.assertEqual(note["when"], "2026-07-25 12:00")
        self.assert_intact(new, note["text"])

    def test_an_answer_can_never_forge_an_entry(self):
        # same writer, same hazard: /answer takes free text too
        new, matched = watch.append_answer(
            self.DOC, "Real question?", self.HOSTILE, "2026-07-25 12:01")
        self.assertTrue(matched)
        q = watch.parse_open_questions(new)[0]
        self.assertEqual(q["answer_when"], "2026-07-25 12:01")
        self.assert_intact(new, q["answer"])

    def test_a_note_on_an_answered_entry_cannot_forge_one_either(self):
        new, matched = watch.append_comment(
            self.DOC, "Old", self.HOSTILE, "2026-07-25 12:02", "Answered")
        self.assertTrue(matched)
        ans = watch.parse_answered(new)
        self.assertEqual(len(ans), 1)
        self.assert_intact(new, ans[0]["follows"][-1]["text"])

    def test_the_file_stays_readable_at_seventy_two_columns(self):
        # the loop writes this file at ~72 columns and a human reads it in an
        # editor; a note is wrapped rather than run out to one long line.
        long_note = "a sentence that keeps going " * 12
        new, _ = watch.append_comment(self.DOC, "Real question?", long_note,
                                      "2026-07-25 12:03")
        added = [l for l in new.splitlines() if "sentence that keeps" in l]
        self.assertGreater(len(added), 1)          # it wrapped
        self.assertTrue(all(len(l) <= 76 for l in added), added)
        # and it round-trips: the note is one string again, unbroken
        note = watch.parse_open_questions(new)[0]["follows"][-1]
        self.assertEqual(note["text"], long_note.strip())

    # ── #136: zero entries has three causes and they must not look alike ───
    SKELETON = "# Questions for the human\n\n## Open\n\n## Answered\n"

    def test_questions_health_tells_all_clear_from_broken(self):
        # the fault: content is there and the reader sees none of it. This is
        # the shape that opened a dashboard to zero over a file holding six.
        broken = ("# Questions for the human\n\n"
                  "## Should we ship the thing?\n"
                  "It matters because of X.\n\n"
                  "## What about privacy defaults?\n"
                  "Two options here.\n")
        self.assertEqual(watch.questions_health(broken), "unreadable")
        # ...and its purest form: headings ONLY, but not the reader's heading.
        # A naive "no prose ⇒ calm" exemption calls this all clear, which is
        # exactly the bug — so it is the case the exemption must not swallow.
        heads_only = "# Questions\n\n## Should we ship the thing?\n"
        self.assertEqual(watch.questions_health(heads_only), "unreadable")

    def test_questions_health_is_calm_about_the_seeded_skeleton(self):
        # init step 7 MANDATES this file, so a checker that reds it is a
        # checker nobody reads by week two.
        self.assertEqual(watch.questions_health(self.SKELETON), "empty")
        self.assertEqual(watch.questions_health(self.SKELETON + "\n\n"), "empty")

    def test_questions_health_is_quiet_about_a_missing_file(self):
        # his call: the loop writes one almost at once, so absence is not a
        # fault on a fresh target
        self.assertEqual(watch.questions_health(None), "missing")

    def test_questions_health_says_ok_when_it_can_see_entries(self):
        self.assertEqual(watch.questions_health(QUESTIONS), "ok")
        # answered-only still counts: the reader can see the file
        answered_only = "# Q\n\n## Open\n\n## Answered\n\n- **Old** done.\n"
        self.assertEqual(watch.questions_health(answered_only), "ok")

    def test_the_calm_exemption_did_not_swallow_the_fault(self):
        # An exemption is exactly where a check quietly dies, so prove the
        # real one still fires AFTER the exemptions exist: take the file the
        # exemption blesses and add one line of content to it.
        self.assertEqual(watch.questions_health(self.SKELETON), "empty")
        with_prose = self.SKELETON + "\nWe should decide about the thing.\n"
        self.assertEqual(watch.questions_health(with_prose), "unreadable")
        # and the heading the exemption keys on is not a magic word that
        # blesses everything else in the file
        self.assertEqual(
            watch.questions_health(self.SKELETON + "\n- not a bold title\n"),
            "unreadable")

    def test_collect_reports_questions_health(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            self.assertEqual(watch.collect(d)["questions_health"], "ok")
            q = os.path.join(d, ".dreamwork", "questions.md")
            with open(q, "w") as f:
                f.write("# Q\n\n## Should we?\nprose that never parses.\n")
            data = watch.collect(d)
            self.assertEqual(data["questions_health"], "unreadable")
            # the count still reads zero — which is the whole point: the
            # number cannot tell them apart, so the health must
            self.assertEqual(data["open_questions"], 0)
            os.remove(q)
            self.assertEqual(watch.collect(d)["questions_health"], "missing")

    def test_persistent_port_stable(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            p1 = watch.persistent_port(d)
            p2 = watch.persistent_port(d)
            self.assertEqual(p1, p2)
            self.assertTrue(3000 <= p1 < 63000)


class TestSummary(unittest.TestCase):
    # /summary.json — a redacted, whitelist view of collect() (Q5; the
    # hub-public-auth.md §11.2 / hub-ssh-auth.md deliverable). The full
    # /data.json serves DREAMWORK.md, questions.md and lessons.md IN FULL
    # plus parsed entries, transcripts and status.json; this drops all of
    # that and keeps only counts, health and operational metadata, for any
    # non-loopback consumer. Redaction is a whitelist: summary() names the
    # fields that may leave and never iterates collect()'s keys, so a field
    # collect() grows cannot appear unless deliberately classified.

    EXPECTED = {"generated", "open_questions", "questions_health",
                "answers_health", "tint", "run_mode", "posture",
                "skill_identity", "burndown_counts", "skill_version"}

    def test_summary_serves_only_the_whitelisted_fields(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            s = watch.summary(d)
            self.assertEqual(set(s), self.EXPECTED)

    def test_summary_classifies_every_collect_key(self):
        # THE HEART (#275/Q5): a summary built by naming what may leave is
        # only safe if a NEW collect() key cannot pass through unreviewed.
        # So every collect() key must be classified into exactly one of
        # ALLOWED (source, projected) or DENIED. A brand-new key lands in
        # NEITHER and this reds — forcing a deliberate decision rather than
        # a silent default to "exposed". This is the test that protects
        # against the field added in three weeks, not today's field list.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            keys = set(watch.collect(d))
        allowed = set(watch.SUMMARY_ALLOWED)
        denied = set(watch.SUMMARY_DENIED)
        # precondition — there ARE keys to classify, else this is vacuous
        self.assertGreater(len(keys), 10)
        unclassified = keys - allowed - denied
        self.assertEqual(unclassified, set(),
                         "new collect() key(s) not classified "
                         "allowed-or-denied: %s" % sorted(unclassified))
        # `files` is the one key allowed ONLY as a source projected to the
        # skill_version scalar — its full document bodies are denied. A key
        # that is BOTH allowed-source and denied is permitted only when the
        # allowed entry projects it to a safe scalar; assert that is `files`.
        overlap = allowed & denied
        self.assertEqual(overlap, {"files"},
                         "only `files` may be an allowed source AND denied; "
                         "a new overlap must prove its projection is safe, "
                         "got: %s" % sorted(overlap))

    def test_summary_drops_every_denied_field(self):
        # Each denied key is absent from summary() by NAME. The denied set is
        # DERIVED from the production constant, never hand-enumerated — the
        # hand list drifted twice (research #484, chats #504) while the
        # partition test above kept passing, because the partition binds
        # classification and this binds absence; both must hold per field and
        # a literal tuned to today's set is a check with an expiry date.
        # Precondition asserted: the denied set really has members, else a
        # gutted constant reads as "nothing to check" rather than failing.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            s = watch.summary(d)
            denied = set(watch.SUMMARY_DENIED)
            self.assertGreater(len(denied), 10)
            for key in denied:
                self.assertNotIn(key, s,
                                 "denied collect() key leaked into summary: "
                                 + key)

    def test_summary_drops_transcripts_and_full_documents(self):
        # #275 brief: transcripts are OUT, stated explicitly. A derived leak
        # string — taken from the REAL questions.md body at runtime — must
        # be absent from summary(); and the PRECONDITION that it really is in
        # collect()/data.json is asserted, or the absence is vacuous (the
        # exact hollowness that cost this repo two green red-runs). The probe
        # is DERIVED, never hand-written: a planted "secret" proves only that
        # the planted string is absent.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            full = watch.collect(d)
            s = watch.summary(d)
            # derive a distinctive phrase from the real questions.md body —
            # the first non-heading prose line, which carries the human's words
            questions_body = full["files"]["questions.md"]
            probe = next((ln.strip() for ln in questions_body.splitlines()
                          if ln.strip() and not ln.lstrip().startswith("#")
                          and len(ln.strip()) > 8), None)
            self.assertIsNotNone(probe, "fixture has no usable prose probe")
            # precondition: the probe really is in the full collect payload
            blob_full = json.dumps(full)
            self.assertIn(probe, blob_full)   # present in /data.json
            blob = json.dumps(s)
            # the leak: a value in summary() contains content only the full
            # document carries
            self.assertNotIn(probe, blob,
                             "summary.json leaked content from questions.md")
            # transcripts: dreams content is his words; assert its absence.
            # derive the probe from the real dream transcript too.
            self.assertGreaterEqual(len(full["dreams"]), 1)
            dream_probe = full["dreams"][0]["content"].strip()
            self.assertGreater(len(dream_probe), 8)   # precondition: real text
            self.assertIn(dream_probe, blob_full)
            self.assertNotIn(dream_probe, blob,
                             "summary.json leaked dream transcript content")

    def test_summary_count_and_health_fields_are_values_not_prose(self):
        # The fields that DO leave must be safe by shape, not by assumption.
        # open_questions is a count; the two health fields are enum tokens;
        # burndown_counts is three ints. None carry his words.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            s = watch.summary(d)
            self.assertIsInstance(s["open_questions"], int)
            self.assertIn(s["questions_health"],
                          {"ok", "missing", "unreadable", "empty"})
            self.assertIn(s["answers_health"],
                          {"ok", "missing", "unreadable", "empty"})
            self.assertEqual(set(s["posture"]),
                             {"pace", "asking", "delegation", "delivery",
                              "orchestration", "source"})
            self.assertEqual(set(s["skill_identity"]),
                             {"commit", "skill_version"})
            self.assertEqual(set(s["burndown_counts"]),
                             {"open", "arrived", "landed"})
            for k in ("open", "arrived", "landed"):
                self.assertIsInstance(s["burndown_counts"][k], int)


class TestSummaryRoute(unittest.TestCase):
    # /summary.json the route: served by watch.py's GET, behind the SAME
    # _preflight() authority gate as every other GET. Adding the read
    # endpoint changes no bind address, host allowlist or flag.

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = make_target(self.tmp.name)
        probe = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)
        port = probe.server_address[1]
        probe.server_close()
        self.authority = watch.RequestAuthority(
            ["allowed.test", "127.0.0.1"], port)
        self.server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", port),
            watch.make_handler(self.target, authority=self.authority))
        threading.Thread(target=self.server.serve_forever,
                         daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{port}"
        self.host = f"allowed.test:{port}"

    def _request(self, path, *, host=None):
        headers = {}
        if host is not None:
            headers["Host"] = host
        req = urllib.request.Request(self.base + path, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def test_summary_route_is_served_as_json(self):
        status, body = self._request("/summary.json", host=self.host)
        self.assertEqual(status, 200)
        s = json.loads(body)
        self.assertEqual(set(s), TestSummary.EXPECTED)

    def test_summary_route_is_gated_by_host_authority(self):
        # A foreign Host is refused exactly as /data.json is — this endpoint
        # adds a read surface, never a wider authority.
        self.assertEqual(
            self._request("/summary.json", host="evil.test")[0], 421)
        self.assertEqual(
            self._request("/summary.json", host=self.host)[0], 200)


class TestQuestionRoute(unittest.TestCase):
    # #452: /question serves the ONE app shell like every other in-app
    # route, so a deep link renders client-side. The qid is the question's
    # title identity — derived here from a REAL parse of the target's
    # questions.md, never a literal, so a fixture whose titles change
    # cannot silently vacate the check.

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = make_target(self.tmp.name)
        probe = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)
        port = probe.server_address[1]
        probe.server_close()
        self.authority = watch.RequestAuthority(
            ["allowed.test", "127.0.0.1"], port)
        self.server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", port),
            watch.make_handler(self.target, authority=self.authority))
        threading.Thread(target=self.server.serve_forever,
                         daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{port}"
        self.host = f"allowed.test:{port}"

    def _request(self, path, *, host=None):
        headers = {}
        if host is not None:
            headers["Host"] = host
        req = urllib.request.Request(self.base + path, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def _real_title(self):
        qfile = os.path.join(self.target, ".dreamwork", "questions.md")
        with open(qfile, encoding="utf-8") as fh:
            entries = watch.parse_open_questions(fh.read())
        # Precondition the check's meaning depends on: the fixture HAS an
        # open question to focus. Zero entries would make "the shell
        # answers for a real qid" pass over a route that resolves nothing.
        self.assertGreater(len(entries), 0,
                           "fixture has no open questions — the route "
                           "check below would be vacuous")
        return entries[0]["title"]

    def test_question_route_serves_the_app_shell(self):
        title = self._real_title()
        qid = urllib.parse.quote(title, safe="")
        status, body = self._request("/question?qid=" + qid, host=self.host)
        self.assertEqual(status, 200)
        self.assertIn(b'id="view"', body)

    def test_question_route_without_qid_still_serves_the_shell(self):
        # No key is not an error the SERVER can see — the client renders
        # the missing-question notice. The shell must still come back.
        status, body = self._request("/question", host=self.host)
        self.assertEqual(status, 200)
        self.assertIn(b'id="view"', body)

    def test_question_route_is_gated_by_host_authority(self):
        title = self._real_title()
        qid = urllib.parse.quote(title, safe="")
        self.assertEqual(
            self._request("/question?qid=" + qid, host="evil.test")[0], 421)


class TestAppShell(unittest.TestCase):
    """The single-document router: /, /questions and /file all serve the
    one shell (deep links render client-side), and /filedata backs the
    in-app file view behind the same confinement gate."""

    def test_page_has_router_and_tint_wiring(self):
        # Static guard: the shell must carry the router + shader hooks so a
        # refactor can't silently drop same-document nav or the per-page
        # atmosphere uniform.
        for token in ('id="view"', 'pushState', 'popstate',
                      'window.dreambg', 'pageTint', 'setTint'):
            self.assertIn(token, watch.PAGE)

    def test_page_has_tab_title_wiring(self):
        # Static guard: the tab title (#153) is assembled from live data and
        # refreshed off the 1s age sweep, not set once per navigation — the
        # liveness word drifts with the wall clock and a stopped loop writes
        # nothing for a tick to hang off. identity.mjs proves the behaviour;
        # this only stops a refactor unhooking it silently.
        for token in ('function pageTitle(', 'function applyTitle(',
                      'function titleNeed(', 'function titleLive(',
                      'const titleWho', 'const STALE_TICK_MS'):
            self.assertIn(token, watch.PAGE)
        self.assertIn('applyTitle();     // the liveness word drifts',
                      watch.PAGE)          # ...inside ages()
        # project name is part of the compound field, not a free substring —
        # a title that kept only "dreamwork" would otherwise still look wired
        self.assertIn("'dreamwork/' + proj", watch.PAGE)

    def test_page_has_favicon_wiring(self):
        # Static guard: the icon is drawn INLINE and refreshed off the same 1s
        # sweep as the title (#153). A file beside the server would not exist
        # in production — `just deploy` snapshots watch.py alone.
        self.assertIn('<link rel="icon" id="favicon"', watch.PAGE)
        for token in ('function favPaint(', 'function applyFavicon(',
                      'const favHue', "toDataURL('image/png')"):
            self.assertIn(token, watch.PAGE)
        self.assertIn('applyFavicon();   // ...and the orbit advances',
                      watch.PAGE)        # ...inside ages()
        # The orbit rides a 1s timer, never rAF: a hidden document is given no
        # rendering opportunities, and a hidden tab is where a favicon lives.
        # (the CALL, not the word — the comment above it explains why there
        # isn't one, and matching prose is how a check tests its own doc)
        self.assertNotIn('requestAnimationFrame(', watch.FAVICON_JS)

    def test_status_panel_gates_last_tick_on_the_field(self):
        # The verbatim fallback for an unparseable `last_tick` was documented
        # and unreachable: `if (t)` is falsy for NaN, so the fact vanished off
        # the page instead of rendering as written (#154's shape). The gate
        # belongs on the field, and the parse only picks the branch.
        self.assertIn('if (s.last_tick)\n    facts.push(isNaN(t)', watch.PAGE)

    def test_status_panel_renders_push_fault_strictly_and_quiets_the_rest(self):
        # #190 — the loop's push channel to the human can die (attn 403 for an
        # afternoon) and only the dashboard can say so. Three states must be
        # distinguishable from the data: never tried (no `push` key), last
        # succeeded (ok:true), last failed (ok:false). Only ok:false renders.
        # The branch is STRICT (=== false): a missing or malformed ok — which
        # lint catches at the writer — must never read as a fault, and lint's
        # own test pushes a string "no" to prove the strictness is load-bearing
        # on both sides. And `push` is in ST_GLANCE so it is rendered here
        # rather than folded into "the rest" (which would double-handle it and
        # bury the fault behind a click).
        self.assertIn('p.ok === false', watch.PAGE)
        self.assertIn("class=\"stpush\"", watch.PAGE)
        self.assertIn("'push'", watch.PAGE)  # in ST_GLANCE

    def test_page_has_dream_transition_wiring(self):
        # Static guard: the dissolve mist (SVG turbulence/displacement) and
        # the shader stir (warp uniform + pulseWarp handle) must stay wired
        # so a refactor can't silently flatten the transition back to a
        # plain fade.
        for token in ('dissolveOut', 'dissolveIn', 'feTurbulence',
                      'feDisplacementMap', 'uniform float warp', 'pulseWarp',
                      'const SEED = '):
            self.assertIn(token, watch.PAGE)

    def test_dev_overlay_measures_draw_time(self):
        # Static guard: the overlay must carry measured per-frame work — a CPU
        # stopwatch around draw() plus GPU-timer feature detection — not just
        # the inter-frame delta that sits at vsync regardless of shader cost.
        for token in ('EXT_disjoint_timer_query_webgl2', 'TIME_ELAPSED_EXT',
                      "'gpu'", "'draw'", 'performance.now()'):
            self.assertIn(token, watch.PAGE)

    def test_live_tick_renders_through_the_current_view_seam(self):
        # #271: a partial route switch left /review's dock stale even after
        # tick() fetched fresh data. One builder seam keeps live and navigate
        # aligned as routes are added.
        self.assertIn('const html = await buildCurrent();', watch.PAGE)
        self.assertIn('if (view !== tickView) return setTimeout(tick, 2000);', watch.PAGE)
        self.assertIn('restoreReviewFrame(reviewFrame);', watch.PAGE)
        self.assertNotIn("if (view.name === 'dashboard') setContent(buildDashboard(data));",
                         watch.PAGE)
        # #505: setContent reconciles #view (morphdom + hash-skip), not
        # wholesale innerHTML=. Red-prove: reintroduce
        # `document.getElementById('view').innerHTML = html` as the body of
        # setContent (and drop the morphdom call) — this pin and selectkeep
        # both go red.
        self.assertIn('morphdom(viewEl', watch.PAGE)
        self.assertIn('function viewNodeKey', watch.PAGE)
        self.assertIn('if (html === lastViewHtml) return;', watch.PAGE)
        # the old swap form must not be the setContent body
        sc = watch.PAGE.split('function setContent(html)', 1)[1][:1800]
        self.assertNotIn(
            "document.getElementById('view').innerHTML = html", sc)

    def test_505p2_review_dock_is_reconciled_not_replaced(self):
        # #505 phase 2 (Q3): the review dock is reconciled through the keyed
        # reconciler, not wholesale-replaceWith'd. Only the swap MECHANISM
        # changes — same content, same lifecycle. Red-proof: reintroduce
        # `currentDock.replaceWith(nextDock)` in setLiveContent's review
        # branch (and drop the morphdom call) → these pins go red, and the
        # dock card/textarea would be destroyed each tick (selection/caret
        # lost), which is the regression this prevents.
        sl = watch.PAGE.split('function setLiveContent(html)', 1)[1][:2200]
        self.assertIn('morphdom(currentDock', sl)
        self.assertIn("childrenOnly: true", sl)
        self.assertIn('getNodeKey: viewNodeKey', sl)
        self.assertIn('onBeforeElUpdated: reconcileGuard', sl)
        # the old wholesale swap must not survive in the review branch
        self.assertNotIn('currentDock.replaceWith(nextDock)', sl)
        # the fade classes ride the kept root (childrenOnly), so the manual
        # hand-copy that the old replaceWith needed is gone
        self.assertNotIn("nextDock.classList.toggle", sl)

    def test_505p2_reconcile_guard_is_shared_and_stamps_focused_value(self):
        # #505 phase 2: the reconciliation rules are ONE source — a named
        # reconcileGuard used by BOTH the #view reconcile (setContent) and the
        # review-dock reconcile (setLiveContent), so the dock and the view
        # cannot drift on what survives a tick. The focus-gated value-stamp is
        # the mechanism that absorbed snapshotViewInputs (a focused input's
        # mid-edit text is kept; caret/focus ride the kept node).
        # Red-proof A: rename reconcileGuard and leave the two call sites →
        #   both morphdom seams break (undefined function).
        # Red-proof B: drop the value-stamp line → bdinput's (a)/(b) go red
        #   (a focused limit input's typed value is clobbered to the server
        #   value across a tick).
        self.assertIn('function reconcileGuard(fromEl, toEl)', watch.PAGE)
        sc = watch.PAGE.split('function setContent(html)', 1)[1][:1200]
        self.assertIn('onBeforeElUpdated: reconcileGuard', sc)
        sl = watch.PAGE.split('function setLiveContent(html)', 1)[1][:2200]
        self.assertIn('onBeforeElUpdated: reconcileGuard', sl)
        # the focus-gated value-stamp (the mechanism that retired viewInputs)
        self.assertIn('document.activeElement === fromEl', watch.PAGE)

    def test_505p2_viewinputs_pair_retired(self):
        # #505 phase 2: snapshotViewInputs / restoreViewInputs are deleted —
        # #523 (a focused input inside #view surviving a tick) is now carried
        # by keyed reconciliation + the value-stamp, not a hand pair.
        # Red-proof: re-add `function snapshotViewInputs()` and the
        # `restoreViewInputs(viewIn)` call in tick() → this pin goes red.
        self.assertNotIn('function snapshotViewInputs()', watch.PAGE)
        self.assertNotIn('function restoreViewInputs(', watch.PAGE)
        tk = watch.PAGE.split('async function tick()', 1)[1][:3000]
        self.assertNotIn('restoreViewInputs(', tk)

    def test_505p2_surviving_snapshot_pairs_each_state_a_reason(self):
        # #505 phase 2: every snapshot/restore pair that survives around the
        # reconciled root states WHY reconciliation cannot absorb it (the
        # brief's anti-failure rule: "a pair that survives without a reason is
        # the failure this act exists to prevent"). The marker is a `#505 p2`
        # keep-reason comment on the snapshot function. Red-proof: delete a
        # keep-reason comment → this pin goes red, naming the unreasoned pair.
        import re
        for fn in ('snapshotCardState', 'snapshotAskState',
                   'snapshotBdHover', 'snapshotReviewFrame'):
            idx = watch.PAGE.find('function ' + fn + '(')
            self.assertNotEqual(idx, -1, fn + ' missing')
            # the keep-reason comment sits in the ~700 chars before the def
            pre = watch.PAGE[max(0, idx - 700):idx]
            self.assertIn('#505 p2', pre,
                          fn + ' survives without a #505 p2 keep-reason')

    def test_page_has_review_route_wiring(self):
        # Static guard: /review is an in-app route that embeds the artifact
        # (from /reviewraw) and docks the originating question, which morphs
        # into place (shared-element FLIP) from where it was clicked.
        for token in ('buildReview', 'reviewframe', 'qdock', 'flipDock',
                      '/reviewraw', 'linkifyReview'):
            self.assertIn(token, watch.PAGE)

    def test_page_has_question_route_wiring(self):
        # #452: /question?qid=<title> focuses ONE question on its own page —
        # a surface the loop's list churn cannot shift under him mid-answer
        # (the list re-sorts and re-bodies entries while he reads). The key
        # is the question's own title identity, the same one `data-qid`
        # already uses to survive regrouping: body rewrites, re-sorts and
        # the open→answered fold all keep it, and those three are the churn
        # the route exists for. A RETITLE breaks it, and that case must
        # render an explicit missing notice — never a blank page and never
        # a different question ("I could not tell" and "nothing" must not
        # render the same). Guard: dev/capture/qfocus.mjs.
        for token in ('buildQuestion', '/question?qid=', 'qfocus', 'qmissing'):
            self.assertIn(token, watch.PAGE)
        # A route lives in three places and must live in all three: the
        # client router (routeOf), the internal-link claim (isInternal),
        # and the server's app-shell table (covered live in
        # TestQuestionRoute). Two of three is a deep link that full-reloads
        # or a link the browser sends nowhere.
        self.assertIn("loc.pathname === '/question'", watch.PAGE)
        self.assertIn("a.pathname === '/question'", watch.PAGE)
        # Resolution searches BOTH sections: answering folds an entry from
        # questions_open into answered_entries while he watches, and the
        # focused page must follow it across the fold rather than reporting
        # a live question as gone.
        self.assertIn("d.answered_entries.find", watch.PAGE)

    def test_page_has_qroll_wiring(self):
        # #454 — an open question card rolls up to the top of the scroll:
        # a 5-6 line floor derived from the RENDERED line height at runtime
        # (never a pixel literal — #441's split-literal lesson), persisted
        # per-question to IndexedDB (the helper the submissions log already
        # races against a wedge — no second store path), synced across tabs
        # through the standing localStorage 'storage'-event idiom, and
        # re-applied through the one render seam (setContent) so a tick or a
        # route swap cannot unroll it. Guard: dev/capture/qroll.mjs.
        for token in ('qroll', 'rolled', '--rollh', 'rolledQids',
                      'restoreRolls', 'dw-ui:'):
            self.assertIn(token, watch.PAGE)
        # The affordance is emitted for the OPEN state only: the styleguide's
        # axis says awaiting still needs the loop and folded already IS the
        # collapsed treatment (#111), so a roll control on either is a second
        # collapse gesture on one card.
        self.assertIn("st === 'open' ? qrollBtn", watch.PAGE)
        # The floor is a line COUNT times a MEASURED line height, applied as
        # a custom property — pinning pixels is the #441 failure shape.
        self.assertIn("setProperty('--rollh'", watch.PAGE)
        # The gesture is the card fold's own (#111/#169): a roll goes through
        # the same snapshot + regroup, not a second way to move a card.
        self.assertIn("regroupCards(before, null, QA_LIST)", watch.PAGE)

    def test_page_has_research_route_wiring(self):
        # #484 — /research lists the built research artifacts under
        # .dreamwork/docs/research/ and /research?p=<name> views one through
        # the same iframe idiom as /review (raw served at /researchraw).
        # It deliberately does NOT reuse the review surface: no questions.md
        # pairing, no archive-on-answered lifecycle. Guard:
        # dev/capture/research.mjs.
        for token in ('buildResearch', '/researchraw', '/research?p='):
            self.assertIn(token, watch.PAGE)
        # A route lives in three places (the #452 lesson restated at
        # test_page_has_question_route_wiring): the client router, the
        # internal-link claim, and the server's app-shell table (covered
        # live in test_research_route_serves_shell_...).
        self.assertIn("loc.pathname === '/research'", watch.PAGE)
        self.assertIn("a.pathname === '/research'", watch.PAGE)
        # The view half embeds the raw artifact for style isolation —
        # reusing the reviewframe id is what gives the tick's
        # snapshotReviewFrame/restoreReviewFrame preservation to it.
        self.assertIn("'/researchraw?p=' + encodeURIComponent(", watch.PAGE)

    def test_narrow_review_frame_uses_measured_rvh_not_60vh(self):
        # #434 — production lines: the narrow #reviewdoc height, and the
        # review-route bottom-pad tighten. Restoring `height:60vh` is the
        # injection that fails the dead-space half of devoverlay.mjs; this
        # unit check names the same line so a greppable regression cannot
        # land without a red pytest either.
        # Precondition: the narrow media query that stacks the pane must
        # still exist, or "no 60vh" is vacuously true of a deleted layout.
        self.assertIn("@media (max-width:900px)", watch.PAGE)
        self.assertIn("#reviewdoc { height:var(--rvh,", watch.PAGE)
        self.assertIn("body.review { padding-bottom:1rem; }", watch.PAGE)
        self.assertNotIn("#reviewdoc { height:60vh", watch.PAGE)
        self.assertNotIn("height:60vh", watch.PAGE)

    def test_dev_overlay_marks_body_so_wordmark_yields(self):
        # #435 — production lines: body.dev class on mount, and the CSS
        # yield on .hproj (wide) / drop under chrome (narrow). Removing the
        # class or the yield rule is the injection that fails the overlap
        # half of devoverlay.mjs (a probe that requires rendered rects, not
        # a <script> containing the letters "fps").
        self.assertIn("doc.body.classList.add('dev')", watch.PAGE)
        self.assertIn("body.dev .hproj", watch.PAGE)
        self.assertIn("margin-right:calc(12.5rem", watch.PAGE)
        self.assertIn("@media (max-width:720px)", watch.PAGE)
        # the overlay itself must still mount — we fix the collision, we do
        # not remove the counter
        self.assertIn("box.id = 'devbox'", watch.PAGE)
        self.assertIn("/*DEV*/false", watch.PAGE)

    def test_every_route_has_its_own_atmosphere_and_title(self):
        # #302: the contract (watch-design.md: "Add a view by adding a builder
        # + a routeOf/TINT/SEED entry"; transitions.md: every destination has
        # its own seed and tint) is that each destination carries its own
        # atmosphere entry. A route missing from either table silently
        # inherits the dashboard's via `TINT[name] || 0` and
        # `SEED[view.name] != null ? ... : 7`, so the page sits outside a
        # stated contract and nothing on screen says so.
        #
        # This asserts the CONTRACT (entry presence), NOT a rendered colour:
        # a colour assertion pins today's palette and expires the next time
        # someone tunes a value — the exact "check with an expiry date" the
        # repo rules out. The set of destinations is read from `routeOf`
        # itself, the one place watch.py enumerates what counts as a page,
        # so a route added tomorrow is caught without restating the list
        # beside the tables. routeOf and the TINT/SEED tables are co-located
        # in ROUTER_JS and key off the same `name`, which is what makes the
        # pairing honest.
        router = watch.ROUTER_JS
        m = re.search(r"function routeOf\(loc\)\s*\{(.*?)\n\}", router, re.S)
        self.assertIsNotNone(m, "routeOf not found in ROUTER_JS")
        routes = set(re.findall(r"name:\s*'(\w+)'", m.group(1)))
        # Precondition the check depends on (transitions.md's own rule, and
        # the repo's standing guard discipline): a loop over zero routes
        # passes forever, and a one-route "set" is the tables restated.
        # Plural is the floor that keeps this check able to fail.
        self.assertGreaterEqual(
            len(routes), 2,
            "routeOf yielded fewer than 2 destinations; the checks below "
            "would be vacuous — did the routeOf parse break?")

        def table_keys(table):
            tm = re.search(r"const %s\s*=\s*\{([^}]*)\}" % table, router)
            self.assertIsNotNone(tm, "%s table not found in ROUTER_JS" % table)
            keys = set(re.findall(r"(\w+)\s*:", tm.group(1)))
            self.assertGreaterEqual(
                len(keys), 1,
                "%s table parsed empty — regex broke on the table?" % table)
            return keys

        tint = table_keys("TINT")
        seed = table_keys("SEED")
        missing_tint = routes - tint
        missing_seed = routes - seed
        self.assertFalse(
            missing_tint,
            "routes with no TINT entry (inherit the dashboard's hue via "
            "TINT[name] || 0): %s" % sorted(missing_tint))
        self.assertFalse(
            missing_seed,
            "routes with no SEED entry (inherit the dashboard's swirl via "
            "SEED[view.name] != null ? ... : 7): %s" % sorted(missing_seed))

        # #318: TITLE_ROUTE is the third per-route table and had the identical
        # omission, which is why this check covers the CLASS rather than the two
        # tables it was written for. Its fallback is
        # `(TITLE_ROUTE[v.name] || TITLE_ROUTE.dashboard)(v.param)`, and the
        # dashboard's entry returns '' — so a route without one does not get a
        # wrong title, it gets NO route word, and the tab reads as the
        # dashboard. That matters more than it sounds: per #153 the title is the
        # only part of this page that exists while the tab is backgrounded,
        # which is most of its life.
        missing_title = routes - table_keys("TITLE_ROUTE")
        self.assertFalse(
            missing_title,
            "routes with no TITLE_ROUTE entry (the tab falls back to the "
            "dashboard's empty route word and never says where it is): %s"
            % sorted(missing_title))

    def test_qa_compose_has_accessible_name_and_send_floor(self):
        # #273: placeholder is not a name; dock/cards need aria-label that
        # tracks mode, and the send control must meet the 44px target floor.
        # RED proved by temporarily dropping these tokens.
        for token in ('qaFieldLabel', 'qaSendLabel',
                      'aria-label="${esc(qaFieldLabel(mode, title))}"',
                      'aria-label="${esc(qaSendLabel(mode))}"',
                      'min-height:44px', 'min-block-size:44px'):
            self.assertIn(token, watch.PAGE)
        self.assertIn('qaCompose(key, st, q.title)', watch.PAGE)
        # mode switch must rewrite the name, not leave a stale answer label
        self.assertIn("ta.setAttribute('aria-label', qaFieldLabel(mode, title))",
                      watch.PAGE)

    def test_page_has_command_palette_wiring(self):
        # Static guard: the + opener, the palette, POST /command, the dream
        # ripple, and the pop-out (Document Picture-in-Picture + window.open
        # fallback) must stay wired so a refactor can't drop the steer path.
        #
        # The POST token moved from `fetch('/command'` to `postJSON('/command'`
        # in #175 and this test fired, correctly — it pins the steer path and
        # the steer path changed shape. It is re-pointed rather than relaxed to
        # `/command`, because a bare path would also match the composer growing
        # a private fetch again, which is the exact thing #175 removed: every
        # submission goes through the one seam that witnesses it.
        for token in ('id="cmdplus"', 'id="cmdpalette"', 'id="chrome"',
                      "postJSON('/command'", 'documentPictureInPicture',
                      'window.open', 'ripple('):
            self.assertIn(token, watch.PAGE)
        self.assertNotIn("fetch('/command'", watch.PAGE,
                         "the composer must not carry a fetch of its own")

    def test_command_vocabulary_has_one_source(self):
        # COMMANDS is the single source: the server's accepted set derives
        # from it, and the page carries it so the composer and the popped-out
        # form cannot drift from what POST /command will accept (#91).
        self.assertEqual(watch.COMMAND_KINDS,
                         tuple(c["kind"] for c in watch.COMMANDS))
        for c in watch.COMMANDS:
            self.assertLessEqual({"kind", "label", "desc", "common"},
                                 set(c), "every kind needs a menu description")
        # the whole vocabulary — descriptions included — reaches the client,
        # which renders the row, the menu and the popout options from it.
        # It arrives as CORE_COMMANDS because `COMMANDS` is the table the
        # plugin half appends to (#86), and it is `let` for that reason.
        self.assertIn(
            "const CORE_COMMANDS = " + json.dumps(list(watch.COMMANDS)),
            watch.PAGE)
        self.assertIn("let COMMANDS = CORE_COMMANDS.slice();", watch.PAGE)
        self.assertIn("COMMANDS.map(c =>", watch.PAGE)      # popout options
        self.assertIn("function renderKinds()", watch.PAGE)  # the button row
        self.assertIn("function renderMenu()", watch.PAGE)   # the hover menu

    def test_command_submit_decays_to_sticky_kind(self):
        # #337 / #504: after a STEERING command lands, the composer decays
        # back to the default (COMMANDS[0], the far-left kind). A steering
        # mode that persists silently raises the authority of his NEXT
        # message, so the composer settles on the least dangerous one —
        # #257's danger reasoning for do-now, generalised. The sticky kinds
        # are chat (#504 — conversational; a follow-up must not require
        # re-selection) and add-idea (parked thoughts chain); both persist,
        # for different stated reasons. The PROPERTY on COMMANDS drives the
        # decay, never a hardcoded pair of kinds: derive the expectation from
        # the table at runtime, so a hypothetical fourth kind with sticky:
        # false is covered by the same assertion without being added here.
        sticky = [c["kind"] for c in watch.COMMANDS if c.get("sticky")]
        self.assertEqual(set(sticky), {"chat", "add-idea"},
                         "chat + add-idea are the kinds that may persist")
        decaying = [c["kind"] for c in watch.COMMANDS if not c.get("sticky")]
        self.assertGreaterEqual(len(decaying), 2,
                                "one decaying kind would prove nothing about "
                                "the property — that a PAIR decays is the point")
        self.assertIn("do-next", decaying)
        self.assertIn("do-now", decaying)
        # The decay lands on the DEFAULT (COMMANDS[0], the far-left kind), not
        # a hardcoded name: `chat` is the default today, but naming it here
        # would re-open the third place a new kind must be remembered. The
        # submit path reads the property off the LIVE table — COMMANDS is a
        # `let` because plugin kinds APPEND (#86), so [0] is always a core
        # kind — and a kind with sticky:false (or no `sticky` at all) decays
        # whether it is core or contributed.
        self.assertIn("COMMANDS.find(c => c.kind === kind)", watch.PAGE)
        self.assertIn("!sent.sticky", watch.PAGE)
        self.assertNotIn("kind === 'do-now'", watch.PAGE)
        self.assertRegex(
            watch.PAGE,
            r"setKind\(\(COMMANDS\[0\] \|\| \{\}\)\.kind\)")
        # no hardcoded kind name in the decay — the old `setKind('add-idea')`
        # was the special case this generalised away.
        self.assertNotIn("setKind('add-idea')", watch.PAGE)

    def test_command_menu_lists_every_kind(self):
        # Hover discoverability (#91): the row shows the common kinds, and the
        # menu shows ALL of them with a one-line description — so an uncommon
        # kind is discoverable, not hidden knowledge. Both render from
        # COMMANDS at any length, so plugin kinds (#86) need no redesign.
        self.assertTrue(any(not c["common"] for c in watch.COMMANDS),
                        "menu is pointless if every kind is already a button")
        for token in ('id="cmdmore"', 'id="cmdmenu"', 'role="menu"',
                      "b.className = 'cmdmenuitem'", 'aria-haspopup="menu"',
                      # the row must admit a selected uncommon kind, or the
                      # indicator would have nothing to sit on
                      'c.common || c.kind === activeKind'):
            self.assertIn(token, watch.PAGE)

    def test_command_selection_is_a_button_group(self):
        # The kind picker is a radiogroup with a sliding indicator, not a
        # <select>; the indicator must land (snap) rather than tween in.
        # Since #103 it is the SHARED .sgroup group the question cards use,
        # so there is one implementation and the two cannot drift.
        for token in ('id="cmdkinds"', 'id="cmdind"', 'role="radiogroup"',
                      'moveIndicator(true)', 'class="sgroup cmdkinds"',
                      'function slideIndicator', "ind.classList.add('snap')",
                      'const moveIndicator = snap => slideIndicator(kindsEl, snap)',
                      'const kind = activeKind;'):
            self.assertIn(token, watch.PAGE)
        self.assertNotIn('id="cmdkind"', watch.PAGE)   # the old <select>

    def test_shader_world_space_wiring(self):
        # Static guard: the shader anchors its domain to the window's screen
        # position and takes its phase from the wall clock (UTC-day-wrapped),
        # so adjacent windows share one continuous, screen-pinned field.
        for token in ('uniform vec2 domainOffset', 'win.screenX', '% 86400'):
            self.assertIn(token, watch.PAGE)

    def test_shader_scale_is_world_fixed(self):
        # The domain scale is a WORLD constant, not a per-window one: two
        # windows of different heights must sample one field at one zoom, or
        # the seam between them can never line up (#91). Guards the regression
        # back to a `2.3 / innerHeight` style per-window scale.
        self.assertIn('const WORLD_SCALE = 2.3 / 900;', watch.PAGE)
        self.assertIn('uniform float domScale', watch.PAGE)
        self.assertNotIn('2.3 / Math.max(1, win.innerHeight)', watch.PAGE)
        # gl_FragCoord.y is bottom-up and screenY is top-down, so the vertical
        # anchor is the NEGATED screen position of the viewport's bottom edge.
        self.assertIn('-((win.screenY || 0) + chromeTop + win.innerHeight)',
                      watch.PAGE)

    def test_popout_carries_the_shader(self):
        # Static guard: the shader is a mountable function (not an IIFE bound
        # to the main document) and every floated window gets one, so a popout
        # shows the same world-space field as the page that spawned it (#91).
        for token in ('function mountDreambg(win, cv, opts)',
                      'function mountPopoutBg(w, tint)',
                      'mountPopoutBg(w, tint); }',   # openPopout always mounts
                      "cv.id = 'dreambg'",
                      'mountDreambg(w, cv, {})',
                      # and the popout stylesheet puts it behind the content
                      '#dreambg { position:fixed; inset:0; z-index:-1;'):
            self.assertIn(token, watch.PAGE)

    def test_page_has_answered_awaiting_fold_state(self):
        # Static guard: the questions view renders three states — an answered
        # (awaiting fold) entry is visually distinct with no input box (#81).
        for token in ('.qa.awaiting', 'awaiting fold', 'q.answer'):
            self.assertIn(token, watch.PAGE)

    def test_one_question_component_for_every_state(self):
        # #105: ONE card renders a question everywhere. The state is derived
        # from the key + entry (never passed in), so no caller can render an
        # entry in a state its own data contradicts, and every surface —
        # dashboard, /questions, the review dock, the folded Answered section
        # — addresses it by the same 'o'/'a' key.
        for token in ('const qaState =', 'const qaInner =', 'const qaCard =',
                      'const qaEntry =',
                      # every call site goes through the one component
                      "qaCard(q, 'o' + i)", "qaCard(e, 'a' + j)",
                      "qaCard(d.questions_open[i], 'o' + i)",
                      # ...including the submit morph, which restates the card
                      "card.className = 'qa ' + qaState(next, key)",
                      'card.innerHTML = qaInner(next, key)'):
            self.assertIn(token, watch.PAGE)
        # the folded Answered section no longer has look-alike markup
        self.assertNotIn('answeredEntry', watch.PAGE)
        self.assertNotIn('aentry', watch.PAGE)

    def test_page_reflows_prose_but_not_raw_text(self):
        # #102 + #158: markdown prose reflows (hard wraps joined, inline
        # emphasis rendered); raw text stays verbatim in a <pre>. The useful
        # line is WHAT the file is, not WHO composed it — .md at /file reflows
        # (same mdB as dashboard peeks); source code at /file does not.
        for token in ('function mdBlocks', 'function mdRender', 'const mdSpans',
                      'const mdB =', 'const mdBReview =',
                      # the six things a join must not destroy (#521 quote,
                      # #525 pipe table)
                      "kind:'fence'", "kind:'h'", "kind:'li'", "kind: 'quote'",
                      "kind: 'table'",
                      'const MD_BULLET =', 'const MD_QUOTE =',
                      'const mdSplitRow =', 'class="mdtable"',
                      # prose surfaces
                      'mdBReview(q.body.trim(), q.title)', 'mdB(d.content)',
                      # the files peek renders through mdB — pinned as a
                      # PREFIX, never the whole call: restcollapse added
                      # keep args (`file:${n}`) and a full-call literal went
                      # stale on a change that kept the thing being asserted;
                      # #522 threads filePath as second arg for relative links
                      'expand(n, mdB(d.files[n]', 'mdInline(txt)'):
            self.assertIn(token, watch.PAGE)
        # #158: /file branches on kind — .md (and kin) through mdB; else pre.
        # The branch is by EXTENSION, never content sniff, and the escape is
        # ordered FIRST: every inline transform (linkify included) runs on
        # already-escaped text, and fences escape too — so hostile markup in
        # a rendered .md is visible text, never honoured HTML. The browser
        # half of that statement is the reflow guard's hostile-file checks.
        # #522: mdB(text, param) so relative [text](../x) can resolve; pin
        # the call prefix, not the whole form.
        for token in ('function isMarkdownFile', 'function buildFile',
                      'isMarkdownFile(param)', 'mdB(text, param)',
                      "endsWith('.md')", "endsWith('.markdown')",
                      "endsWith('.mdx')",
                      # #522: linkifyReview → linkifyMd → linkify
                      'linkify(linkifyMd(esc(t), baseDir))',
                      'const linkifyMd =', 'class="mdquote"',
                      '${esc(b.text)}',
                      '`<pre>${esc(text)}</pre>`'):
            self.assertIn(token, watch.PAGE)
        # status.json was in that list until #130 and is not any more. It is
        # neither prose to reflow nor a file to show verbatim — it is a set of
        # facts, and it has its own component. Asserting the dump is GONE is
        # the half that matters: the old rendering is the reported bug.
        self.assertNotIn('preB(JSON.stringify(d.status', watch.PAGE)
        self.assertIn('function statusBlock', watch.PAGE)

    def test_review_artifact_links_dock_via_linkifyReview(self):
        # #472 — production lines: revDock + linkifyReview's two shapes
        # (preferred backticked `.dreamwork/review/name.html`, and the
        # markdown-link outlier `[text](../review/name.html)`). mdSpans has
        # no general [text](url) pass; only review-artifact targets are
        # rewritten, always to `/review?p=…` so a relative path cannot
        # 404 from /questions.
        for token in ('const revDock =', 'const linkifyReview =',
                      # #522 inserted linkifyMd between linkifyReview and
                      # linkify; review still runs first (more specific)
                      'linkify(linkifyMd(linkifyReview(esc(t), title), null))',
                      'mdBReview(q.body.trim(), q.title)'):
            self.assertIn(token, watch.PAGE)
        # the preferred shape still matches inside backticks (PAGE is the
        # assembled JS, so one backslash before each regex meta char)
        self.assertIn(r'`\.dreamwork\/review\/', watch.PAGE)
        # the outlier shape is recognised (../review/ OR .dreamwork/review/)
        self.assertIn(r'\.\.\/review\/', watch.PAGE)

    def test_linkifyReview_renders_both_corpus_shapes_to_working_href(self):
        # #472 — discriminating half: the *href works*, not merely that an
        # <a> exists. Run the production linkifyReview + mdSpans chain via
        # node (the same compose path question bodies use) and assert the
        # dock href. Then prove /reviewraw serves that basename from a real
        # artifact — a rendered link to a 404 is the defect wearing a fix's
        # clothes.
        #
        # PRODUCTION LINE whose change reds the JS half: the markdown-link
        # replace inside linkifyReview (the first h.replace). Deleting it
        # leaves the #417 shape as raw brackets and this fails. The
        # preferred-shape replace is the second half — deleting it leaves
        # the backticked path unlinked.
        import re, subprocess, textwrap, tempfile
        m = re.search(r'const revDock = .*?return h;\n\};', watch.PAGE, re.S)
        self.assertIsNotNone(m, "revDock+linkifyReview block missing from PAGE")
        block = m.group(0)
        script = textwrap.dedent("""\
            %s
            const esc = t => String(t)
              .replace(/&/g,'&amp;').replace(/</g,'&lt;')
              .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
            const mdSpans = h => h
              .replace(/`([^`]+)`/g, '<code>$1</code>');
            const linkify = h => h;
            const run = (title, t) => mdSpans(linkify(linkifyReview(esc(t), title)));
            const title = '2026-07-29 — probe';
            const md = 'Artifact: [`probe-art.html`](../review/probe-art.html)';
            const bt = 'Artifact: `.dreamwork/review/probe-art.html`';
            const outMd = run(title, md);
            const outBt = run(title, bt);
            if (!outMd.includes('class="rev"')) process.exit(11);
            if (!outMd.includes('/review?p=probe-art.html')) process.exit(12);
            if (outMd.includes('../review/')) process.exit(13);
            if (outMd.includes('](')) process.exit(14);
            if (!outBt.includes('/review?p=probe-art.html')) process.exit(15);
            if (!outBt.includes('class="rev"')) process.exit(16);
            process.stdout.write('ok');
        """) % block
        out = subprocess.check_output(["node", "-e", script], text=True)
        self.assertEqual(out, "ok")
        # HTTP half: the basename the link targets really resolves.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            rd = os.path.join(d, ".dreamwork", "review")
            os.makedirs(rd, exist_ok=True)
            with open(os.path.join(rd, "probe-art.html"), "w") as f:
                f.write("<!doctype html><title>probe</title><p>artifact body")
            base = self._serve(d)
            status, raw = self._get(base + "/reviewraw?p=probe-art.html")
            self.assertEqual(status, 200)
            self.assertIn("artifact body", raw)

    def test_commit_age_ticks_off_the_render_path(self):
        # #132. The interesting half is not the format, it is WHERE the update
        # happens: a seconds-resolution clock must not ride the tick's
        # innerHTML swap, or it re-runs the regroup (#113) and re-carries his
        # typing (#118) once a second forever.
        for token in ('const agePair =', 'const AGE_PAIRS =', 'const gitRow =',
                      'const paintAgePair =', 'const ageParts =',
                      # written into nodes that already exist...
                      "querySelectorAll('.age[data-ct]')",
                      "paintAgePair(el, parseFloat(el.dataset.ct), ' ago')",
                      # ...on the standing per-second sweep, and re-run after
                      # every render so a fresh row is filled before it paints
                      'setInterval(ages, 1000)', 'ages();'):
            self.assertIn(token, watch.PAGE)
        # the row emits the time as data, never as prose: nothing on the page
        # can parse an age back off the screen
        self.assertIn('data-ct="${c.t}"', watch.PAGE)
        self.assertIn('data-sha="${esc(c.sha)}"', watch.PAGE)
        # the old whole-line render is gone — it is the thing being replaced,
        # and leaving it would mean two ways to draw a commit
        self.assertNotIn("d.git.map(l =>", watch.PAGE)
        # no element catch-all inside the component (the standing rule, #121
        # and #139): every part of the row is addressed by its own class
        self.assertNotIn('.git div {', watch.PAGE)

    def _age_pair_js_block(self):
        """Extract p2 + AGE_* + agePair from production PAGE. The production
        lines that must change for these tests to fail are AGE_PAIRS and
        agePair itself — not a Python reimplementation."""
        import re
        page = watch.PAGE
        start = page.index('const p2 = n =>')
        end = page.index('/* components: every section', start)
        block = page[start:end].rstrip()
        self.assertIn('const AGE_PAIRS =', block)
        self.assertIn('const agePair =', block)
        return block

    def _age_pairs_from_page(self):
        """Parse AGE_PAIRS values via node so AGE_Y/AGE_W resolve exactly as
        production does — no second copy of 365 or 7."""
        import json, subprocess, textwrap
        block = self._age_pair_js_block()
        script = textwrap.dedent("""\
            %s
            process.stdout.write(JSON.stringify(AGE_PAIRS));
        """) % block
        out = subprocess.check_output(["node", "-e", script], text=True)
        pairs = json.loads(out)
        self.assertTrue(pairs, "AGE_PAIRS empty")
        return pairs  # [[bu, bd, su, sd], ...]

    def _age_pair_render(self, age_s, pairs_override=None):
        """Run production agePair (or the same body with AGE_PAIRS replaced)
        at a fixed now, age_s seconds ago. Returns 'XXu YYv'."""
        import re, subprocess, textwrap
        block = self._age_pair_js_block()
        if pairs_override is not None:
            # rewrite the table literal; production line under test is AGE_PAIRS
            import json
            lit = json.dumps(pairs_override)
            block = re.sub(
                r'const AGE_PAIRS = \[.*?\];',
                'const AGE_PAIRS = %s;' % lit, block, count=1, flags=re.S)
        script = textwrap.dedent("""\
            %s
            const NOW = 2000000000;  // fixed epoch seconds
            Date.now = () => NOW * 1000;
            const age = %d;
            process.stdout.write(agePair(NOW - age));
        """) % (block, int(age_s))
        return subprocess.check_output(["node", "-e", script], text=True)

    def _parse_pair(self, rendered):
        import re
        m = re.fullmatch(r'(\d+)([a-z]) (\d+)([a-z])', rendered)
        self.assertIsNotNone(m, f"agePair shape: {rendered!r}")
        return m.group(2), int(m.group(1)), m.group(4), int(m.group(3))

    def test_age_pairs_ladder_covers_seconds_to_years(self):
        # #385. The table itself must name every rung he asked for, in
        # descending order. Derived from PAGE via node — not a hand-list.
        pairs = self._age_pairs_from_page()
        bigs = [p[0] for p in pairs]
        self.assertEqual(bigs, ['y', 'w', 'd', 'h', 'm'],
                         f"ladder big units: {bigs}")
        for i, row in enumerate(pairs):
            bu, bd, su, sd = row
            if i + 1 < len(pairs):
                self.assertEqual(su, pairs[i + 1][0],
                                 f"{bu}'s small unit should be next big")
            else:
                self.assertEqual(su, 's')
        # year length is named in the source so the choice is not silent
        self.assertIn('365 * 86400', watch.PAGE)
        self.assertIn('7 * 86400', watch.PAGE)

    def test_age_pair_fields_stay_under_100_for_a_century(self):
        # #385 his invariant: neither XX nor YY > 99 for at least 100 years.
        # The field cap (100) is the digit budget the format is built around —
        # not a magic fixture number. The century LENGTH is derived from the
        # table's year rung when present; when the year rung is missing (the
        # discriminating injection) the same span is taken from the named
        # `365 * 86400` expression in PAGE so the check still probes a century
        # and can fail by SHOWING a field ≥ 100 rather than only by naming
        # the missing rung.
        pairs = self._age_pairs_from_page()
        day_s = next(bd for bu, bd, _, _ in pairs if bu == 'd')
        year_row = next((r for r in pairs if r[0] == 'y'), None)
        # Century length from the table's year rung. If the year rung is
        # gone (discriminating injection), size it as 100 × 365 × day_s —
        # 365 is the year-length decision named beside AGE_Y in PAGE, and
        # day_s comes from the table so a change to the day divisor moves
        # both halves together.
        if year_row is not None:
            year_s = year_row[1]
        else:
            self.assertIn('365', watch.PAGE)
            year_s = 365 * day_s
        century = 100 * year_s
        field_cap = 100
        samples = {0, 1, 59, 60, 3599, 3600, 86399, 86400, 100 * day_s}
        for bu, bd, su, sd in pairs:
            samples.add(bd)
            samples.add(max(0, bd - 1))
            samples.add(bd + sd)
            samples.add(100 * bd)  # age that overflows this unit alone
        samples.add(century - 1)
        samples = sorted(a for a in samples if 0 <= a < century)
        self.assertLess(100 * day_s, century,
                        "precondition: 100 days is inside the century span")
        for age in samples:
            rendered = self._age_pair_render(age)
            bu, bn, su, sn = self._parse_pair(rendered)
            for unit, n in ((bu, bn), (su, sn)):
                self.assertLess(
                    n, field_cap,
                    f"field {unit}={n} at age {age}s → {rendered!r}; "
                    f"year_s={year_s}")
        # production must not still render 100 days as a three-digit day
        # count — that is the live defect this test exists to see.
        rendered = self._age_pair_render(100 * day_s)
        bu, bn, su, sn = self._parse_pair(rendered)
        self.assertFalse(
            bu == 'd' and bn >= field_cap,
            f"100 days still renders as day-count: {rendered!r}")

    def test_question_title_carries_age_next_to_its_date(self):
        # #385: qtHtml is the one place a question headline gains an age, and
        # it reuses data-ct + paintAgePair — never a second humanizer.
        page = watch.PAGE
        for token in ('const qtHtml =', 'class="age qage" data-ct=',
                      'qtHtml(q.title)', '.qt .qage'):
            self.assertIn(token, page)
        # both open and folded titles go through it (one path, not a fork)
        self.assertEqual(page.count('qtHtml(q.title)'), 2)
        import json, subprocess, textwrap
        # extract qtHtml + esc enough to render
        start = page.index('const qtHtml =')
        end = page.index('const qaInner =', start)
        fn = page[start:end].rstrip()
        script = textwrap.dedent("""\
            const esc = t => String(t ?? '')
              .replace(/&/g,'&amp;').replace(/</g,'&lt;')
              .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
            %s
            const a = qtHtml('P1 · 2026-01-01 — urgent thing');
            const b = qtHtml('2026-06-15 — plain thing');
            const none = qtHtml('no date in this title at all');
            const cts = [...a.matchAll(/data-ct="([^"]+)"/g)].map(m => m[1]);
            const ctsB = [...b.matchAll(/data-ct="([^"]+)"/g)].map(m => m[1]);
            process.stdout.write(JSON.stringify({
              a, b, none, cts, ctsB,
              aHasAge: /class="age qage"/.test(a),
              bHasAge: /class="age qage"/.test(b),
              noneHasAge: /data-ct=/.test(none),
              aKeepsDate: a.includes('2026-01-01'),
              bKeepsDate: b.includes('2026-06-15'),
            }));
        """) % fn
        out = subprocess.check_output(["node", "-e", script], text=True)
        data = json.loads(out)
        self.assertTrue(data["aHasAge"] and data["bHasAge"])
        self.assertFalse(data["noneHasAge"])
        self.assertTrue(data["aKeepsDate"] and data["bKeepsDate"])
        self.assertEqual(len(data["cts"]), 1)
        self.assertEqual(len(data["ctsB"]), 1)
        # anti-vacuity: the two titles' timestamps differ
        self.assertNotEqual(data["cts"][0], data["ctsB"][0],
                            "two different title dates produced the same ct")
        self.assertIn('2026-01-01', data["a"])
        self.assertIn('urgent thing', data["a"])

    def test_age_pair_grays_only_the_pad_digit(self):
        # #385 gray zero: `05h 09m` greys two pads; `15h 42m` greys none.
        # Both directions — a rule that greys unconditionally passes any
        # check that only looks at the first. Production lines under test:
        # paintAgePair's `n < 10` branch and ages()' paintAgePair call.
        import json, subprocess, textwrap
        block = self._age_pair_js_block()
        self.assertIn("className = 'agepad'", block)
        self.assertIn('.age .agepad', watch.PAGE)
        script = textwrap.dedent("""\
            // minimal DOM sufficient for paintAgePair — not a browser.
            function frag() {
              return { nodes: [], append(...xs) {
                for (const x of xs) this.nodes.push(x);
              }};
            }
            const document = {
              createDocumentFragment: frag,
              createElement: () => ({ className: '', textContent: '' }),
            };
            %s
            const NOW = 2000000000;
            Date.now = () => NOW * 1000;
            function paint(age) {
              const el = { kids: null,
                replaceChildren(f) { this.kids = f.nodes; } };
              paintAgePair(el, NOW - age, '');
              const pads = el.kids.filter(k => k && k.className === 'agepad')
                                 .length;
              const text = el.kids.map(k =>
                (typeof k === 'string' || typeof k === 'number') ? String(k)
                : (k && k.textContent != null ? k.textContent : '')).join('');
              return { pads, text, plain: agePair(NOW - age) };
            }
            // 5h 9m → 05h 09m: two pads. 15h 42m: none.
            const single = paint(5*3600 + 9*60);
            const double = paint(15*3600 + 42*60);
            // anti-vacuity: the two ages really differ, and plain forms
            // really are the padded shapes under test.
            if (single.plain === double.plain)
              throw new Error('fixture ages collided: ' + single.plain);
            process.stdout.write(JSON.stringify({ single, double }));
        """) % block
        out = subprocess.check_output(["node", "-e", script], text=True)
        data = json.loads(out)
        self.assertEqual(data["single"]["plain"], "05h 09m")
        self.assertEqual(data["double"]["plain"], "15h 42m")
        self.assertEqual(
            data["single"]["pads"], 2,
            f"05h 09m must grey two pads; got {data['single']}")
        self.assertEqual(
            data["double"]["pads"], 0,
            f"15h 42m must grey none; got {data['double']}")
        self.assertEqual(data["single"]["text"], "05h 09m")
        self.assertEqual(data["double"]["text"], "15h 42m")

    def test_age_pair_without_year_rung_breaks_the_invariant(self):
        # #385 discriminating red for the ladder. Production line under
        # test: AGE_PAIRS. Strip the year rung and the century-span must
        # overflow a field. With weeks still present the week count passes
        # 99; the live defect (no year AND no week) shows a day count of
        # 100 at 100 days — both are the same class of bug, and this test
        # also proves the day-count signature against the pre-#385 table.
        pairs = self._age_pairs_from_page()
        self.assertEqual(pairs[0][0], 'y')
        year_s = pairs[0][1]
        without_year = pairs[1:]
        self.assertTrue(without_year and without_year[0][0] != 'y')
        century = 100 * year_s
        day_s = next(bd for bu, bd, _, _ in pairs if bu == 'd')
        # 1) remove year only — probe until a field ≥ 100 appears
        overflow = None
        for age in (100 * day_s, 100 * without_year[0][1], century - 1):
            rendered = self._age_pair_render(age, pairs_override=without_year)
            bu, bn, su, sn = self._parse_pair(rendered)
            if bn >= 100 or sn >= 100:
                overflow = (age, rendered, bu, bn, su, sn)
                break
        self.assertIsNotNone(
            overflow,
            "removing the year rung did not produce any field ≥ 100 "
            "inside a century — the invariant test cannot go red on that "
            "injection, so it is not testing his invariant")
        age, rendered, bu, bn, su, sn = overflow
        self.assertGreaterEqual(
            max(bn, sn), 100,
            f"year-rung removed: expected overflow, got {rendered!r} "
            f"at age {age}s")
        # 2) the live defect signature: days-only ladder at 100 days
        days_only = [row for row in pairs if row[0] in ('d', 'h', 'm')]
        rendered_d = self._age_pair_render(100 * day_s, pairs_override=days_only)
        bu_d, bn_d, su_d, sn_d = self._parse_pair(rendered_d)
        self.assertEqual(bu_d, 'd')
        self.assertGreaterEqual(
            bn_d, 100,
            f"days-only ladder at 100d must show day count ≥ 100; "
            f"got {rendered_d!r}")

    # ── #392a: a date-only question must stop claiming a sub-day figure ────
    # The age a question title claims must match the precision of its data.
    # A headline carries a DATE and no TIME, so `qtHtml`'s `ct` is local
    # midnight of that day; #385 rendered two figures off it anyway, so a
    # 24-minute-old entry read `08h 17m ago` (an eight-hour lie). The number
    # of figures is now the precision: date-only → one figure; timed → two.
    #
    # These tests drive the REAL `ages()` dispatch (extracted from PAGE) in a
    # minimal mock DOM, so a dispatch that routes date-only/timed to the wrong
    # painter is caught here rather than hidden behind a parallel
    # implementation. The expected strings come from offsets chosen by hand,
    # never from agePair/ageParts — that is the check #385 never had.

    def _ages_pieces(self):
        """Pull the production formatters, qtHtml and ages() out of PAGE.

        `ages()` is sliced to its column-0 close brace; its body carries no
        column-0 `}` of its own (every inner close is indented), so the slice
        is the whole function. The formatters live between `p2` and the
        `/* components` marker — the same range `_age_pair_js_block` uses."""
        page = watch.PAGE
        blk_start = page.index('const p2 = n =>')
        blk_end = page.index('/* components: every section', blk_start)
        block = page[blk_start:blk_end].rstrip()
        self.assertIn('const paintDayAge =', block)   # #392a one-figure painter
        self.assertIn('const pushFig =', block)       # shared greyed-pad path
        q_start = page.index('const qtHtml = title =>')
        q_end = page.index('const qaInner =', q_start)
        qthtml = page[q_start:q_end].rstrip()
        a_start = page.index('function ages() {')
        ages_fn = page[a_start:page.index('\n}', a_start) + 2]
        self.assertIn('paintDayAge', ages_fn)
        self.assertIn('paintAgePair', ages_fn)
        return block, qthtml, ages_fn

    def _qt_html(self, title):
        """Run the production `qtHtml` in node; return the emitted HTML."""
        import json, subprocess, textwrap
        block, qthtml, _ = self._ages_pieces()
        esc = ("const esc = t => String(t ?? '').replace(/&/g,'&amp;')"
               ".replace(/</g,'&lt;').replace(/>/g,'&gt;')"
               ".replace(/\"/g,'&quot;');")
        script = (esc + '\n' + qthtml + '\n' +
                  f'process.stdout.write(qtHtml({json.dumps(title)}));')
        return subprocess.check_output(["node", "-e", script], text=True)

    def _qt_ct(self, title):
        """The local-midnight `ct` the production `qtHtml` computes (node)."""
        import re
        m = re.search(r'data-ct="([^"]+)"', self._qt_html(title))
        self.assertIsNotNone(m, f"qtHtml emitted no data-ct for {title!r}")
        return int(m.group(1))

    def _render_via_ages(self, spans, now):
        """Run the production `ages()` against `spans` at fixed epoch `now`.

        Each span is a dict: `{title:...}` (a date-only question title —
        `qtHtml` marks it `data-day="1"`) or `{ct:<secs>}` (a TIMED node with
        no `data-day`, i.e. a commit). Only the DOM scaffolding is mocked;
        the dispatch, the painters and qtHtml are all production code."""
        import json, subprocess, textwrap
        block, qthtml, ages_fn = self._ages_pieces()
        esc = ("const esc = t => String(t ?? '').replace(/&/g,'&amp;')"
               ".replace(/</g,'&lt;').replace(/>/g,'&gt;')"
               ".replace(/\"/g,'&quot;');")
        script = textwrap.dedent("""\
            const ageStr = () => '';
            __BLOCK__
            __ESC__
            __QTHTML__
            const applyTitle=()=>{}, applyFavicon=()=>{}, applyTint=()=>{};
            let fetchedAt = 0;
            const NOW = __NOW__;
            Date.now = () => NOW*1000;
            function makeSpan(dataset){ return { dataset, _k:null,
              replaceChildren(f){ this._k=(f&&f.nodes)?f.nodes:(f==null?[]:[f]); },
              get textContent(){ return (this._k||[]).map(k=>
                (typeof k==='string'||typeof k==='number')?String(k)
                :(k&&k.textContent!=null?k.textContent:'')).join(''); } }; }
            function spanFromTitle(title){ const h=qtHtml(title);
              const ct=h.match(/data-ct="([^"]+)"/)[1];
              const dm=h.match(/data-day="([^"]+)"/);
              const ds={ct}; if(dm) ds.day=dm[1]; return makeSpan(ds); }
            let ACTIVE = __SPANS__.map(d => 'title' in d
              ? spanFromTitle(d.title) : makeSpan({ct:String(d.ct)}));
            const document={
              querySelectorAll(sel){ return sel==='.age[data-ct]'?ACTIVE:[]; },
              getElementById(){return null;},
              createElement(){return {className:'',textContent:''};},
              createDocumentFragment(){return {nodes:[],
                append(...xs){for(const x of xs)this.nodes.push(x);}}; } };
            __AGES__
            ages();
            process.stdout.write(JSON.stringify(ACTIVE.map(e=>e.textContent)));
        """).replace('__BLOCK__', block).replace('__ESC__', esc)\
            .replace('__QTHTML__', qthtml).replace('__AGES__', ages_fn)\
            .replace('__NOW__', str(int(now)))\
            .replace('__SPANS__', json.dumps(spans))
        return json.loads(subprocess.check_output(["node", "-e", script],
                                                  text=True))

    def test_a_date_only_question_shows_one_figure_not_two(self):
        # CRITERION 3 — assert the PRECISION of the input at runtime, not a
        # literal date. The fixture is a REAL open question, and the no-time
        # precondition is DERIVED from it (parsed, then asserted) before any
        # rendering is claimed. The rendering is then checked for ONE figure.
        # #385's check asked only that two fixture ages DIFFER; they differed
        # by two days and were both wrong by eight hours, so an output-to-
        # output comparison cannot find a systematic error — this asserts the
        # input precision and the figure count directly.
        import datetime, re
        text = open('.dreamwork/questions.md', encoding='utf-8').read()
        qs = watch.parse_open_questions(text)
        # A DATE-ONLY open entry whose date is NOT today, so it renders a day
        # figure. Selecting on date-only is the point: since #392b a title may
        # legally carry ` HH:MM`, and a selector that took any dated entry then
        # asserted date-only turned every new timed ask into a failure of this
        # test (it did, at 00:57, on a `#449` entry — the assertion below was
        # right and the selection was wrong). The precondition it protects is
        # now that a date-only entry EXISTS at all, asserted after the search.
        today = datetime.date.today().isoformat()
        dated_only = [x for x in qs
                      if not x['title'].startswith('P2 · ' + today)
                      and re.search(r'\d{4}-\d{2}-\d{2}', x['title'])
                      and not re.search(r'\d{2}:\d{2}|T\d', x['title'])]
        self.assertTrue(dated_only,
                        "no date-only open question left in the live file — "
                        "this test needs one to have anything to measure; "
                        "add a date-only fixture entry rather than deleting "
                        "the check (%d open entries, all timed)" % len(qs))
        q = dated_only[0]
        title = q['title']
        # ── RUNTIME PRECONDITION: the fixture genuinely carries NO TIME ──
        dm = re.search(r'(\d{4}-\d{2}-\d{2})', title)
        self.assertIsNotNone(dm, "fixture title carries no date")
        date = dm.group(1)
        self.assertRegex(date, r'^\d{4}-\d{2}-\d{2}$',
                         "title date is not day-precision")
        self.assertNotRegex(title, r'\d{2}:\d{2}|T\d',
                            "title carries a time — fixture is no longer "
                            "date-only, the precondition has expired")
        # ── RENDER via the real ages() dispatch ──
        # now is 3d 08h past the title's midnight (both derived in node via
        # qtHtml, so timezone is consistent end to end). 3 full days is MY
        # chosen offset; the rendered figure is checked against its shape and
        # against that choice, never against agePair's output.
        ct = self._qt_ct(title)
        now = ct + 3 * 86400 + 8 * 3600
        [rendered] = self._render_via_ages([{'title': title}], now)
        # ── ONE figure: the missing second figure IS the precision signal ──
        self.assertRegex(rendered, r'^\d{2}[ymdwh] ago$',
                         f"a date-only age must be ONE figure; got {rendered!r}")
        self.assertNotRegex(rendered, r'\d{2}[ymdwh] \d{2}[ymdwh]',
                            f"a date-only age claimed a sub-day figure the "
                            f"data does not hold: {rendered!r}")
        # the value (3) comes from MY 3-day offset, not from agePair
        self.assertEqual(rendered, '03d ago')

    def test_a_timed_timestamp_still_shows_two_figures(self):
        # CRITERION 4 — a TIMED node (a commit's real timestamp, no data-day)
        # keeps TWO figures. The expected value comes from OUTSIDE the code:
        # the offset is 14 hours 3 minutes (chosen by hand) and the rendered
        # string `14h 03m ago` is asserted against that choice — not against
        # anything watch.py computes. This is the half #385 got right; it must
        # not collapse to one figure when date-only learned to drop a figure.
        now = 2_000_000_000                         # fixed epoch seconds
        offset = 14 * 3600 + 3 * 60                 # 14h 03m — MY choice
        [rendered] = self._render_via_ages([{'ct': now - offset}], now)
        self.assertEqual(
            rendered, '14h 03m ago',
            f"a 14h03m-old timed entry must read `14h 03m ago` (two figures); "
            f"got {rendered!r}")
        self.assertRegex(rendered, r'^\d{2}h \d{2}m ago$',
                         f"timed age must keep two figures; got {rendered!r}")

    def test_an_entry_dated_today_does_not_read_as_stale(self):
        # #392a — the one case that is mine to decide, and the one he sees
        # most: an entry dated TODAY. `0d ago` reads as a broken zero for
        # something filed this morning, and `0d 0Xh`/`0Xh` would claim a time
        # the day-only data cannot support. The one honest thing day-only
        # data supports is the word itself: `today`. A deliberate, singular
        # break from the figure grammar — see watch-design.md (#392a).
        title = 'P1 · 2026-07-28 — filed this morning'
        ct = self._qt_ct(title)                     # local midnight (node)
        now = ct + 5 * 3600                          # 05:00 the same day
        # RUNTIME PRECONDITION: the entry really is "today" (same calendar
        # day, under 24h old) — derived from ct and now, not a literal.
        self.assertLess(now - ct, 86400,
                        "fixture is not 'today' relative to the fixed now")
        [rendered] = self._render_via_ages([{'title': title}], now)
        self.assertEqual(
            rendered, 'today',
            f"an entry dated today must read `today`, never a figure the "
            f"day-only data cannot support; got {rendered!r}")

    def test_all_open_questions_still_render_after_the_age_change(self):
        # CRITERION 8 — a display change that drops an entry it cannot
        # classify is the worst outcome: watch.py renders an unreadable file
        # as "nothing to answer". The age work is cosmetic (text in a span),
        # but assert the open count is unchanged and every open title still
        # produces an age node through the real qtHtml — none falls through
        # to the date-less plain-text branch or is dropped.
        text = open('.dreamwork/questions.md', encoding='utf-8').read()
        qs = watch.parse_open_questions(text)
        # The subject count is DERIVED, not a literal: this asserted "at least
        # the three known open questions" and went red on 2026-07-29 for the
        # honest reason that two had been answered. A literal tuned to the live
        # corpus is a check with an expiry date nobody can see (#474). What
        # this test can actually prove is that every open entry the parser
        # returns still produces an age node — plus that there IS one, or the
        # loop below passes over nothing.
        self.assertTrue(qs,
                        "no open questions in the live file — this check needs "
                        "a subject; the loop below would pass over nothing")
        # every open title carries a date, so every one gains a .age qage span
        for q in qs:
            self.assertIn('class="age qage" data-ct=',
                          self._qt_html(q['title']),
                          f"a title lost its age span: {q['title']!r}")
        # the page still renders the whole open list, unfiltered by age/date
        self.assertIn('questions_open.map', watch.PAGE)

    def test_a_timed_question_title_ages_from_its_time_not_midnight(self):
        # #392b — the red that catches the OFFSET, not presence.
        # A headline carrying `YYYY-MM-DD HH:MM` has a known clock time; the
        # age must come from THAT time. Age-from-midnight was the measured
        # defect (#392): a 07:54 filing read `08h 17m ago` at 08:18 while
        # being 24 minutes old. #392a stopped fabricating precision for
        # date-only entries; this half makes a timed entry exact.
        #
        # PRODUCTION LINE: `const qtHtml = title =>` in watch.PAGE — the
        # regex that captures optional ` HH:MM`, the `ct` built from that
        # local datetime, and the ABSENCE of `data-day` so ages() routes to
        # paintAgePair (two figures). Reinstating date-only midnight parsing
        # (or forcing `data-day="1"` on every span) reds this test.
        import re
        # Fixed local filing time — the measured defect's numbers, as a
        # fixture string. Not today's file; live questions.md is not edited.
        title = 'P2 · 2026-07-28 07:54 — timed fixture for age precision'
        # ── RUNTIME PRECONDITION: title carries a time that is NOT midnight ──
        dm = re.search(
            r'(\d{4}-\d{2}-\d{2})(?: (\d{2}:\d{2}))?', title)
        self.assertIsNotNone(dm, "fixture title carries no date")
        date, clock = dm.group(1), dm.group(2)
        self.assertIsNotNone(clock,
                             "fixture must carry HH:MM — without it this "
                             "test is a date-only check and cannot fail on "
                             "midnight-derived ages")
        h, mi = (int(x) for x in clock.split(':'))
        gap_from_midnight = h * 3600 + mi * 60
        self.assertGreater(
            gap_from_midnight, 0,
            "true time must differ from midnight by a known amount; "
            "a 00:00 fixture cannot discriminate midnight from real time")
        # ── RENDER via the real qtHtml + ages() ──
        html = self._qt_html(title)
        self.assertIn('class="age qage" data-ct=', html,
                      "a timed title must still gain an age span")
        # no data-day: the number of figures IS the precision (#392a)
        self.assertNotRegex(
            html, r'data-day=',
            f"a timed title must not carry data-day (that forces one-figure "
            f"day precision); got {html!r}")
        ct = self._qt_ct(title)
        # sibling date-only title on the SAME calendar day → midnight ct
        mid_title = f'P2 · {date} — date-only sibling for the gap assert'
        mid_ct = self._qt_ct(mid_title)
        # both derived at runtime; the gap must equal the fixture's clock
        self.assertEqual(
            ct - mid_ct, gap_from_midnight,
            f"timed ct must sit {gap_from_midnight}s after that day's "
            f"midnight; got ct={ct} mid={mid_ct} gap={ct - mid_ct}")
        # the measured defect case: 24 minutes after filing → 08:18.
        # Under an hour the #385 ladder is minutes+seconds (`24m 00s`), not
        # hours+minutes — that is the format, not a second humanizer.
        now = ct + 24 * 60
        [rendered] = self._render_via_ages([{'title': title}], now)
        self.assertEqual(
            rendered, '24m 00s ago',
            f"a 24-minute-old timed entry must read `24m 00s ago` (two "
            f"figures from its clock time), not a midnight-derived lie; "
            f"got {rendered!r}")
        self.assertRegex(rendered, r'^\d{2}m \d{2}s ago$',
                         f"timed age must keep two figures; got {rendered!r}")
        # and the midnight-derived age at the same `now` is a different claim
        mid_age_secs = now - mid_ct
        true_age_secs = now - ct
        self.assertNotEqual(
            mid_age_secs, true_age_secs,
            "precondition collapsed: midnight age equals true age")
        self.assertEqual(true_age_secs, 24 * 60)
        # midnight-derived would be ~8h18m (two figures of hours+minutes);
        # assert we did not land there or on day-only `today`
        self.assertNotEqual(rendered, 'today')
        self.assertNotRegex(
            rendered, r'^0[89]h \d{2}m ago$',
            f"rendered age looks midnight-derived, not 24m: {rendered!r}")

    def test_day_age_has_middot_separator_and_near_invisible_pad(self):
        # #456 — legibility of the date/age pair on a question headline.
        # Before: `2026-07-28 01d ago` (one continuous digit run; the eye
        # cannot find where the date ends). After: `2026-07-28 · 01d ago`
        # with the chrome's own ` · `, and the pad zero near-invisible via
        # opacity rather than a dimmer colour token.
        #
        # PRODUCTION LINES whose change reds this test:
        #   1. qtHtml join in watch.PAGE — the template that emits
        #      `${when} · <span class="age qage"…>` (revert the ` · `
        #      between date and span and the separator assert fails).
        #   2. STYLE rule `.age .agepad { opacity:.5; }` (revert to
        #      `color:var(--dimmer)` or drop opacity and the pad rule
        #      assert fails).
        # No transition added: ages() is a pure text rewrite once a
        # second (transitions.md exempts that sweep). Day-age path
        # (data-day → paintDayAge) is unchanged — only the join and the
        # pad's quietness.
        import datetime, re
        page = watch.PAGE
        # ── pad: opacity, not a solid dimmer colour ──
        # The rule must be present as a CSS declaration the browser applies.
        # A colour-only quieting fails the goal (opacity composites against
        # the shader; a token does not).
        m_pad = re.search(
            r'\.age\s+\.agepad\s*\{([^}]*)\}', page)
        self.assertIsNotNone(
            m_pad, "STYLE has no .age .agepad rule — pad quieting is gone")
        pad_body = m_pad.group(1)
        self.assertRegex(
            pad_body, r'opacity\s*:\s*\.?5\d*|opacity\s*:\s*0?\.5\b',
            f".agepad must quiet via opacity ~50% (close to invisible on "
            f"the shader); rule body was {pad_body!r}")
        # ── RUNTIME PRECONDITION: a date-only open question exists ──
        # Same trap as 72c9f2e: a check with no subject passes forever.
        # Select DATE-ONLY (not timed) so the day-age path is the one under
        # the separator, and not-today so the age is a figure not `today`.
        text = open('.dreamwork/questions.md', encoding='utf-8').read()
        qs = watch.parse_open_questions(text)
        today = datetime.date.today().isoformat()
        dated_only = [x for x in qs
                      if not x['title'].startswith('P2 · ' + today)
                      and re.search(r'\d{4}-\d{2}-\d{2}', x['title'])
                      and not re.search(r'\d{2}:\d{2}|T\d', x['title'])]
        self.assertTrue(
            dated_only,
            "no date-only open question left in the live file — this test "
            "needs one to have anything to measure; add a date-only fixture "
            "entry rather than deleting the check (%d open, none date-only)"
            % len(qs))
        q = dated_only[0]
        title = q['title']
        dm = re.search(r'(\d{4}-\d{2}-\d{2})', title)
        self.assertIsNotNone(dm, "fixture title carries no date")
        date = dm.group(1)
        self.assertNotRegex(
            title, r'\d{2}:\d{2}|T\d',
            "title carries a time — fixture is no longer date-only")
        # ── RENDER via production qtHtml ──
        html = self._qt_html(title)
        # separator sits BETWEEN the date and the age span — not after the
        # whole title, not inside the span. Chrome's ` · ` (U+00B7, spaces).
        # #474: and it is a `.rsep` NODE, not bare text. That is the load-
        # bearing half: `dockHeadline` identifies a docked question by the
        # headline MINUS its chrome, and it can only remove nodes — a bare-text
        # middot survived the strip and reddened both dock guards for two days
        # on a correct page. Asserting the node here is what keeps the strip's
        # premise true, so this regex must not be loosened back to bare text.
        self.assertRegex(
            html,
            re.escape(date) + r'<span class="rsep"> · </span>'
            r'<span class="age qage" data-ct="',
            f"date and age must be joined by a `.rsep` chrome node carrying "
            f"` · ` — bare text would survive dockHeadline's strip (#474); "
            f"got {html!r}")
        self.assertIn('data-day="1"', html,
                      "date-only path must still mark data-day (precision)")
        # age content is unchanged by the join: still one figure via ages()
        ct = self._qt_ct(title)
        now = ct + 3 * 86400 + 8 * 3600
        [rendered] = self._render_via_ages([{'title': title}], now)
        self.assertEqual(rendered, '03d ago',
                         f"separator must not alter day-age semantics; "
                         f"got {rendered!r}")
        # pad still only on the leading 0 of a single-digit unit — the
        # age string is 03d, so paintDayAge/pushFig still wears .agepad
        # on that 0. Drive paintDayAge on a mocked el and count pads.
        import json, subprocess, textwrap
        block = self._age_pair_js_block()
        script = textwrap.dedent("""\
            function frag() {
              return { nodes: [], append(...xs) {
                for (const x of xs) this.nodes.push(x);
              }};
            }
            const document = {
              createDocumentFragment: frag,
              createElement: () => ({ className: '', textContent: '' }),
            };
            %s
            const CT = %d;
            const NOW = CT + 3*86400 + 8*3600;
            Date.now = () => NOW * 1000;
            const el = { kids: null,
              replaceChildren(f) { this.kids = f.nodes; } };
            paintDayAge(el, CT);
            const pads = el.kids.filter(k => k && k.className === 'agepad')
                               .length;
            const text = el.kids.map(k =>
              (typeof k === 'string' || typeof k === 'number') ? String(k)
              : (k && k.textContent != null ? k.textContent : '')).join('');
            process.stdout.write(JSON.stringify({ pads, text }));
        """) % (block, ct)
        out = subprocess.check_output(["node", "-e", script], text=True)
        data = json.loads(out)
        self.assertEqual(data["text"], "03d ago")
        self.assertEqual(
            data["pads"], 1,
            f"03d must wear exactly one .agepad on the leading 0; "
            f"got {data!r}")

    def test_commits_panel_is_five_near_the_top_and_regroups_on_a_new_sha(self):

        # #151. Three claims, and the third is the one worth guarding.
        self.assertEqual(watch.GIT_ROWS, 5)
        # near the top: before the dreams heading, which used to be first
        sections = watch.PAGE[watch.PAGE.index('function buildDashboard'):]
        self.assertLess(sections.index("label('commits')"),
                        sections.index('label(`dreams'))
        # ONE regroup, not a second implementation of "one leaves, its
        # neighbours travel" — both lists go through the same pair
        for token in ('const QA_LIST =', 'const GIT_LIST =',
                      'snapshotCards(GIT_LIST)',
                      'regroupCards(gitBefore, null, GIT_LIST)'):
            self.assertIn(token, watch.PAGE)
        # ...and it fires on a NEW SHA, never on a tick: the dashboard
        # re-renders whenever any watched file changes, and rows sliding for
        # that is motion with nothing behind it.
        self.assertIn('const gitKey =', watch.PAGE)
        self.assertIn('gitKey(data) !== wasGit', watch.PAGE)
        # a corpse holds no address, and the new list has a new one (#113)
        self.assertIn("'data-qid', 'data-qkey', 'data-sha'", watch.PAGE)

    def test_dashboard_questions_section_folds_counts_and_greys(self):
        # #141. Collapsed by default via the standing expand idiom, counting
        # the server's number and nobody else's.
        for token in ('function qSection', 'const qSummary =',
                      '<details class="qsec" data-keep="qsec">',
                      'd.open_questions || 0'):
            self.assertIn(token, watch.PAGE)
        # the grey is keyed on HEALTH, not on the count: an unreadable file
        # produces a zero too, and a calm "nothing to answer" under #136's
        # amber warning would be the page contradicting itself
        self.assertIn("d.questions_health === 'empty'", watch.PAGE)
        self.assertIn("d.questions_health === 'ok'", watch.PAGE)
        # and it must not simply be `!n`
        self.assertNotIn('const calm = !n;', watch.PAGE)
        # what he opened survives the tick, or it snaps shut every 2s (#118).
        # The mechanism changed under #505: the snapshotFolds/restoreFolds
        # pair is deleted, and the keyed reconciler now stamps human-owned
        # `open` onto the incoming node so morphAttrs cannot clear it.
        for token in ("if (fromEl.tagName === 'DETAILS' && fromEl.dataset && fromEl.dataset.keep) {",
                      'if (fromEl.open) toEl.open = true;'):
            self.assertIn(token, watch.PAGE)
        # the child combinator is what keeps `> summary` from restyling every
        # question card's own disclosure (the catch-all rule, #121/#139)
        self.assertIn('.qsec > summary', watch.PAGE)
        self.assertNotIn('.qsec summary {', watch.PAGE)

    def test_expand_peeks_carry_data_keep_for_fold_restore(self):
        # restcollapse: expand() peeks must ride snapshotFolds, keyed stably
        # (not by the counted summary — "the rest (N)" shifts while identity
        # does not). Without data-keep the live tick re-closes under him.
        self.assertIn("const expand = (s, inner, cls='', keep='')", watch.PAGE)
        self.assertIn('data-keep="${esc(keep)}"', watch.PAGE)
        for token in ("'status-rest'",
                      "'dreams-archive'",
                      '`dream:${d.name}`',
                      '`file:${n}`'):
            self.assertIn(token, watch.PAGE)
        # status overflow must not key on the summary text alone
        self.assertIn("expand(`the rest (${rest.length + deep.length})`",
                      watch.PAGE)
        # keep is the last arg on that call
        self.assertRegex(
            watch.PAGE,
            r"expand\(`the rest \(\$\{rest\.length \+ deep\.length\}\)`[\s\S]*?"
            r"'status-rest'\)")

    def test_page_heading_is_persistent_chrome(self):
        # #110: the heading is the page's frame, not view content — it lives
        # in the shell as a sibling of #view, survives navigation, and its
        # crumbs are keyed so a survivor is the same element before and after
        # (a FLIP has nothing to measure otherwise).
        for token in ('id="chrome"', 'function renderChrome',
                      'function chromeSnapshot', 'function departCrumbs',
                      'function crumbsFor', 'data-k', 'crumbout', 'dreamin',
                      'renderChrome(view, data, snap)'):
            self.assertIn(token, watch.PAGE)
        # no view builder may emit its own heading any more
        self.assertNotIn('pageHeader', watch.PAGE)
        self.assertNotIn('<div id="meta">$', watch.PAGE)

    def test_page_slides_the_column_and_pins_the_ghost(self):
        # #107: the review column is wider, so a route change resizes the
        # page. The departing ghost is pinned to the box it was rendered in
        # (it must not re-wrap while still opaque) and the column glides.
        for token in ('body.wsliding .wrap { transition:max-width',
                      "ghost.style.width = outW + 'px'",
                      "ghost.style.height = outH + 'px'",
                      "document.body.classList.add('wsliding')",
                      "document.body.classList.remove('wsliding')"):
            self.assertIn(token, watch.PAGE)

    def test_page_clamps_the_command_opener(self):
        # #108: the + hangs in the gutter left of the column, which does not
        # exist on the review view or in a narrow window — it was clipped by
        # the page edge. The pull is clamped to the room available, and
        # re-clamped per frame because the column glides (#107).
        # The clamp is CSS, not a measure-then-write in rAF: the column
        # glides on a route change (#107) and JS would always paint a frame
        # behind it. `100%` is the column's own width, so the gutter is
        # expressible without naming a `ch`-sized column.
        self.assertIn('margin-left:calc(-1 * clamp(0px, (100vw - 100%) / 2',
                      watch.PAGE)
        # the old fixed breakpoint is gone: a clamp subsumes it
        self.assertNotIn('@media (max-width:820px) { #cmdplus', watch.PAGE)

    def test_page_has_layer_switch_guard_and_feedback(self):
        # #78: the layer hotkey ignores text-field keystrokes, and any switch
        # (key or corner triple-click) shows a self-explanatory toast.
        for token in ("closest('input, textarea, select')",
                      'press l to cycle', 'layerhint'):
            self.assertIn(token, watch.PAGE)

    def test_page_has_autoreload_client(self):
        # #84: /mtime carries a server generation; the client reloads when it
        # changes (server rebuilt/redeployed) and tolerates the restart gap.
        for token in ('parseMtime', 'location.reload', 'serverGen'):
            self.assertIn(token, watch.PAGE)

    def test_page_has_answer_submit_morph(self):
        # #79: submitting an answer morphs the box into the answered state
        # (restated through the shared qaInner), and Ctrl/Cmd+Enter submits
        # from a field.
        for token in ('qaInner(next, key)', 'requestSubmit',
                      "(e.ctrlKey || e.metaKey) && e.key === 'Enter'"):
            self.assertIn(token, watch.PAGE)

    def test_page_has_followup_wiring(self):
        # #82: every entry gets a follow-up thread and a box that POSTs
        # /comment; answered entries are rendered structured
        # (answered_entries). Since #103 that box is the card's ONE input,
        # shared with the answer path and routed by its mode group.
        for token in ('sendComment', 'postComment', "postJSON('/comment'",
                      'followThread', 'qaCompose', 'answered_entries'):
            self.assertIn(token, watch.PAGE)
        # #136: BOTH write paths check what came back. They did not, and a
        # refused write still ran the confirming morph — so the page said the
        # answer had landed, cleared his text, and the next tick put the
        # question back with no explanation anywhere.
        self.assertIn('function qaFail', watch.PAGE)
        # #263 E5b: the decision is the VERDICT's `landed`, never `res.ok`
        # alone — a rejected 202 (res.ok true, body rejected:true) is the same
        # failure, and on /answer+/comment that false confirmation cleared the
        # draft, the only copy of what he typed. Both paths hand qaFail the
        # verdict so it can name the reason; both gate on `v.landed`.
        self.assertGreaterEqual(
            watch.PAGE.count('qaFail(card, v)'), 2,
            "both sendAnswer and sendComment surface a refusal via the verdict")
        self.assertNotIn('!res.ok) { qaFail(card, res ? res.status : 0)',
                         watch.PAGE)

    def test_draft_is_cleared_on_exactly_one_path(self):
        """#163 — the draft is forgotten on a successful send and nowhere else.

        This is structural on purpose. The browser guard (`draft.mjs`) proves
        the behaviour; what it cannot notice is someone LATER adding a second
        `clearDraft()` to `closeCmd` or to the rejection branch, because that
        reads as tidy and the guard would then fail somewhere far away. The
        whole contract is the count.
        """
        # `clearDraft();` with the semicolon counts CALLS only — the
        # definition reads `function clearDraft() {` and would otherwise be
        # counted as one, which is how this test first failed at 2 != 1
        self.assertEqual(watch.PAGE.count('clearDraft();'), 1,
                         "clearDraft is called from the success branch only")
        # ...and it really is inside the success branch: the line that empties
        # the box is the one the confirmation is written next to
        i = watch.PAGE.index('clearDraft();')
        self.assertIn("getElementById('cmdtext').value = ''",
                      watch.PAGE[i - 200:i])
        # saving hangs off HIS acts, never off setKind — which also runs at
        # init and from restoreDraft, where it would erase the stored draft
        # before it was ever read
        self.assertNotIn('setKind(kind); saveDraft', watch.PAGE)
        self.assertEqual(watch.PAGE.count('saveDraft();'), 3,
                         "one input save, two explicit kind choices")

    def test_draft_is_partitioned_by_target_path_not_name(self):
        # two checkouts can share a basename, and a draft surfacing under the
        # wrong loop is worse than a lost one
        self.assertIn("'dw:draft:' + tgt", watch.PAGE)
        self.assertIn('data.target', watch.PAGE)

    def test_draftstore_module_surface_and_dual_read(self):
        """#269 extract: one DraftStore every surface routes through.

        Structural: the module names, the dual-read legacy shapes, and the
        two #459 consumers. Behaviour is reviewdraft.mjs; this pins the
        extract so a later rename cannot silently re-fork the key policy.
        """
        for token in (
            'const DraftStore',
            'const id = (kind, scopeKey)',
            'isDurable',
            "dw:draft:v1:",
            # dual-read of pre-module keys (orphaning ban)
            "'dw:adraft:' + t + ':'",
            "'dw:draft:' + t",
            # #459 consumers
            "id('ask', 'main')",
            "id('popout', 'main')",
            'bindAskDraft',
        ):
            self.assertIn(token, watch.PAGE, f"missing DraftStore contract token: {token}")
        # clear only after isDurable — the receipt seam, not bare res.ok
        self.assertIn('DraftStore.isDurable', watch.PAGE)
        # no debounce window on the answer save path (still delegated input)
        self.assertIn('dwDraft.save(title, t.value)', watch.PAGE)

    def test_page_has_pip_popout_buttons(self):
        # #83: discoverable PiP-glyph buttons float a doc/review in an
        # identity-headed window, reusing the popout machinery.
        for token in ('pipBtn', 'popoutDoc', 'data-pipurl', 'openPopout',
                      'popoutShell'):
            self.assertIn(token, watch.PAGE)

    def _serve(self, target):
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), watch.make_handler(target))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)   # LIFO: shutdown runs first
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def _get(self, url):
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read().decode("utf-8")

    def _post(self, url, obj):
        req = urllib.request.Request(
            url, data=json.dumps(obj).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode("utf-8")

    def test_view_routes_serve_one_shell(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            for path in ("/", "/questions", "/answers", "/file?p=DREAMWORK.md"):
                status, body = self._get(base + path)
                self.assertEqual(status, 200)
                self.assertIn('id="view"', body)      # same app shell
                self.assertIn("dreamwork watch", body)

    def test_ask_creates_optional_ledger_after_witness_and_wakes_loop(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            apath = os.path.join(d, ".dreamwork", "answers.md")
            self.assertFalse(os.path.exists(apath))
            base = self._serve(d)
            status, _ = self._post(base + "/ask", {
                "question": "Can this wake the dreamer?", "from": "/answers"})
            self.assertEqual(status, 202)
            with open(apath, encoding="utf-8") as f:
                text = f.read()
            self.assertEqual(len(watch.parse_open_answers(text)), 1)
            with open(os.path.join(d, ".dreamwork", "submissions.log"), encoding="utf-8") as f:
                witnessed = [json.loads(line) for line in f]
            self.assertEqual(witnessed[-1]["path"], "/ask")
            self.assertEqual(witnessed[-1]["req"]["question"],
                             "Can this wake the dreamer?")
            with open(os.path.join(d, ".dreamwork", "watch-events.log"), encoding="utf-8") as f:
                self.assertIn("question for dreamer", f.read())

    def test_ask_rejects_non_string_after_witness_without_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            base = self._serve(d)
            for bad in ({"nested": True}, ["list"]):
                # E5: schema-invalid JSON is 202 + durable rejected, not a
                # synchronous 400. His words are still witnessed (#199).
                status, _ = self._post(base + "/ask", {"question": bad, "from": "/answers"})
                self.assertEqual(status, 202)
            self.assertFalse(os.path.exists(os.path.join(d, ".dreamwork", "answers.md")))
            with open(os.path.join(d, ".dreamwork", "submissions.log"), encoding="utf-8") as f:
                self.assertEqual(len(f.readlines()), 2)

    def test_filedata_returns_confined_content(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            status, body = self._get(base + "/filedata?p=DREAMWORK.md")
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["content"], "# DREAMWORK\n")

    def test_filedata_blocks_escape(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            with self.assertRaises(urllib.error.HTTPError) as cm:
                self._get(base + "/filedata?p=../etc/passwd")
            self.assertEqual(cm.exception.code, 404)

    # ── #336: /file must show an image, not its bytes as mojibake ─────────
    # His report, typed from
    # /file?p=.dreamwork/review/evidence/review-note-reply-unclear.png:
    # "viewing images should work. this renderes as binary ascii like:" and
    # a paste of U+FFFD soup. The cause is diagnosed above (#336 in
    # .dreamwork/tasks.md); these are the load-bearing proofs. A 1x1 PNG is
    # too small to exercise the truncation half and too synthetic to be the
    # file he actually saw, so the byte-identical proof uses a real PNG body
    # whose length is the only thing that distinguishes "served in full"
    # from "served up to the old limit" — and the limit is derived from
    # watch.read_text.__defaults__ at runtime, never a literal here.
    _PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

    @staticmethod
    def _build_png(target_size):
        """A syntactically valid PNG of approximately `target_size` bytes,
        by padding an ancillary tEXt chunk. The smallest valid file plus a
        keyword means the result is within ~50 bytes of the request; the
        byte-identical proof compares against what we built, not against
        `target_size`, so the slack is irrelevant."""
        import struct, zlib
        def chunk(typ, data):
            return (len(data).to_bytes(4, "big") + typ + data +
                    struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff))
        ihdr = chunk(b"IHDR",
                     struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
        # Deflate of one filter-zero + one grayscale pixel.
        idat = chunk(b"IDAT", zlib.compress(b"\x00\x00", 9))
        iend = chunk(b"IEND", b"")
        # tEXt: keyword b"evidence\x00" + text. Pad the text so the whole
        # file lands near target_size; ancillary chunks may carry any text.
        used = len(TestAppShell._PNG_MAGIC) + len(ihdr) + len(idat) + len(iend)
        # The +9 is the chunk header (4 length + 4 type + 4 crc) plus the
        # b"evidence\x00" keyword terminator inside the data.
        pad = max(0, target_size - used - 12)
        text = chunk(b"tEXt", b"evidence\x00" + b"a" * pad)
        return TestAppShell._PNG_MAGIC + ihdr + text + idat + iend

    def _get_bytes(self, url):
        # The existing _get does .decode("utf-8"), which is wrong for binary
        # responses. This returns the raw bytes and the headers; the headers
        # carry the security-load-bearing Content-Type / Disposition /
        # X-Content-Type-Options that #336 asserts as behaviour.
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read(), {k.lower(): v for k, v in r.headers.items()}

    def test_fileview_image_served_byte_identical(self):
        # PROOF 1: the file he reported renders as an <img>, and the bytes
        # served are BYTE-IDENTICAL to the file on disk — full length and a
        # digest, because "it looks like an image" is what the mojibake also
        # claimed. Asserts the served length exceeds the OLD cap (derived
        # from read_text's default at runtime, never a literal) so this also
        # covers the truncation half: a file too large for the old endpoint
        # is served whole by the new one.
        import hashlib
        OLD_LIMIT = watch.read_text.__defaults__[0]
        with tempfile.TemporaryDirectory() as d:
            target = make_target(d)
            os.makedirs(os.path.join(target, ".dreamwork", "review", "evidence"))
            png_path = os.path.join(target, ".dreamwork", "review", "evidence",
                                    "review-note-reply-unclear.png")
            png = self._build_png(OLD_LIMIT + 50_000)
            with open(png_path, "wb") as f:
                f.write(png)
            # PRECONDITION, asserted rather than trusted: the file is bigger
            # than the old cap. A test whose truncation proof is "the file
            # exceeds the limit" is hollow if the fixture happens to make
            # them equal — pin the gap at runtime.
            self.assertGreater(len(png), OLD_LIMIT)
            base = self._serve(target)
            # /filedata describes the image rather than decoding it as text.
            status, body, _ = self._get_bytes(base + "/filedata?p=" +
                urllib.parse.quote(".dreamwork/review/evidence/review-note-reply-unclear.png"))
            meta = json.loads(body)
            self.assertTrue(meta.get("binary"))
            self.assertEqual(meta["kind"], "image")
            self.assertEqual(meta["mime"], "image/png")
            self.assertEqual(meta["size"], len(png))
            self.assertNotIn("content", meta)  # the mojibake path is gone
            # /filebytes serves the raw bytes, byte-identical and uncut.
            status, served, h = self._get_bytes(base + "/filebytes?p=" +
                urllib.parse.quote(".dreamwork/review/evidence/review-note-reply-unclear.png"))
            self.assertEqual(status, 200)
            self.assertEqual(h["content-type"], "image/png")
            self.assertEqual(len(served), len(png))
            self.assertEqual(hashlib.sha256(served).digest(),
                             hashlib.sha256(png).digest())
            self.assertEqual(served, png)             # the whole file, byte for byte

    def test_fileview_non_image_binary_says_what_it_is(self):
        # PROOF 2: a non-image binary does NOT dump its bytes into a <pre>.
        # /filedata describes it (kind=binary, mime, size); the bytes are
        # reachable via /filebytes only as an attachment.
        with tempfile.TemporaryDirectory() as d:
            target = make_target(d)
            # A .bin file with NUL bytes: not text, not in the image allowlist.
            blob = b"\x00\x01\x02BINARY\xff" * 100
            with open(os.path.join(target, "object.bin"), "wb") as f:
                f.write(blob)
            base = self._serve(target)
            status, body, _ = self._get_bytes(base + "/filedata?p=object.bin")
            meta = json.loads(body)
            self.assertTrue(meta.get("binary"))
            self.assertEqual(meta["kind"], "binary")
            self.assertEqual(meta["size"], len(blob))
            self.assertNotIn("content", meta)
            # The byte endpoint serves it ONLY as octet-stream + attachment.
            status, served, h = self._get_bytes(base + "/filebytes?p=object.bin")
            self.assertEqual(status, 200)
            self.assertEqual(h["content-type"], "application/octet-stream")
            self.assertIn("attachment", h["content-disposition"])
            self.assertEqual(h["x-content-type-options"], "nosniff")
            self.assertEqual(served, blob)

    def test_no_scriptable_type_can_reach_the_inline_mime_table(self):
        """The gap the #336 agent found in its own red proof, closed (coordinator).

        Its report was honest about a green red-run: flipping `INLINE_IMAGE_EXTS`
        to include 'svg' did NOT make the behavioural test below fail, because
        `detect_file_kind` also requires matching magic bytes and svg has no
        signature. That layering is a feature, not a bug — but it means the
        behavioural test cannot fail on an allowlist-only widening, so nothing at
        all would.

        The realistic accident is not the three-table sabotage a saboteur makes;
        it is a reader adding 'svg' to `INLINE_IMAGE_EXTS` and `_INLINE_IMAGE_MIME`
        — two structures declared four lines apart — and not thinking about magic.
        This fails on that, at the MIME table, which is the layer that decides what
        a browser is TOLD the bytes are.

        Production lines: `_INLINE_IMAGE_MIME`'s membership (first assertion) and
        `INLINE_IMAGE_EXTS`'s (second). Add 'svg' to either and this fails while
        every other file-view test stays green.
        """
        for name in ("a.svg", "a.html", "a.htm", "a.xml", "a.js", "a.pdf"):
            assert watch.inline_image_mime(name) == "application/octet-stream", (
                "%s can be served inline with a browser-honoured type" % name)
        for ext in ("svg", "html", "htm", "xml", "js"):
            assert ext not in watch.INLINE_IMAGE_EXTS, (
                "%r is in the inline allowlist; inline SVG/HTML is stored XSS "
                "against this origin" % ext)
        # Precondition: the table must still contain the rasters it is for, or
        # both loops above pass over an empty allowlist and mean nothing.
        assert watch.inline_image_mime("a.png") == "image/png"
        assert "png" in watch.INLINE_IMAGE_EXTS

    def test_fileview_inline_allowlist_is_raster_only(self):
        # PROOF 3 — the security decision, tested as BEHAVIOUR. SVG and HTML
        # in the tree must NEVER be served inline as image/svg+xml or
        # text/html: a raw-bytes endpoint that reflected a guessed type
        # would turn either into stored XSS against this origin. The named
        # production line is the allowlist membership check in
        # detect_file_kind / INLINE_IMAGE_EXTS — flip it to include 'svg'
        # and this test fails on the svg line.
        with tempfile.TemporaryDirectory() as d:
            target = make_target(d)
            # An SVG with a script tag: if this is ever served as
            # image/svg+xml, the browser executes it.
            with open(os.path.join(target, "evil.svg"), "w") as f:
                f.write('<svg xmlns="http://www.w3.org/2000/svg">'
                        '<script>alert(1)</script></svg>')
            # An HTML file in the tree: if this is ever served as text/html,
            # the browser parses it as a document.
            with open(os.path.join(target, "page.html"), "w") as f:
                f.write("<!doctype html><script>alert(1)</script>")
            # A PNG that genuinely is one (control: allowlist still works).
            with open(os.path.join(target, "ok.png"), "wb") as f:
                f.write(self._PNG_MAGIC + b"\x00" * 32)
            base = self._serve(target)
            # PRECONDITION: the raster allowlist does what it claims today,
            # so the assertion below is discriminating rather than vacuous.
            self.assertIn("png", watch.INLINE_IMAGE_EXTS)
            # SVG: never inline, always attachment.
            status, served, h = self._get_bytes(base + "/filebytes?p=evil.svg")
            self.assertNotEqual(h["content-type"], "image/svg+xml")
            self.assertNotEqual(h["content-type"], "text/html")
            self.assertEqual(h["content-type"], "application/octet-stream")
            self.assertIn("attachment", h["content-disposition"])
            self.assertEqual(h["x-content-type-options"], "nosniff")
            # HTML: never text/html either.
            status, served, h = self._get_bytes(base + "/filebytes?p=page.html")
            self.assertNotEqual(h["content-type"], "text/html")
            self.assertNotEqual(h["content-type"], "image/svg+xml")
            self.assertEqual(h["content-type"], "application/octet-stream")
            self.assertIn("attachment", h["content-disposition"])
            # Control: a real PNG is served inline, as image/png.
            status, served, h = self._get_bytes(base + "/filebytes?p=ok.png")
            self.assertEqual(h["content-type"], "image/png")
            self.assertEqual(h["content-disposition"], "inline")

    def test_fileview_magic_bytes_gate_extension_claims(self):
        # PROOF 3b: detection requires extension AND magic bytes — a .png
        # whose bytes are an SVG does not get served as image/png. Without
        # this, an attacker (or a confused copy) plants XSS under an
        # image extension. The named production line is _magic_matches()
        # short-circuiting detect_file_kind away from 'image'.
        with tempfile.TemporaryDirectory() as d:
            target = make_target(d)
            # An SVG body with a .png extension: extension is allowlisted,
            # magic bytes do not match the PNG signature.
            with open(os.path.join(target, "spoof.png"), "w") as f:
                f.write('<svg xmlns="http://www.w3.org/2000/svg">'
                        '<script>alert(1)</script></svg>')
            base = self._serve(target)
            status, served, h = self._get_bytes(base + "/filebytes?p=spoof.png")
            self.assertNotEqual(h["content-type"], "image/png")
            self.assertEqual(h["content-type"], "application/octet-stream")
            self.assertIn("attachment", h["content-disposition"])

    def test_filebytes_blocks_escape(self):
        # PROOF 4: the byte endpoint is confined by the SAME gate as
        # /filedata. Inheriting resolve_confined is not evidence that the
        # new endpoint called it; prove it on /filebytes directly, against
        # traversal, absolute, ~, empty, and a symlink that points outside.
        # The target is a SUBDIRECTORY of the tempdir so a real secret can
        # live outside it but inside the tempdir, which is what makes the
        # symlink-escape assertion load-bearing rather than vacuous.
        with tempfile.TemporaryDirectory() as d:
            target = make_target(os.path.join(d, "target"))
            with open(os.path.join(d, "secret.txt"), "w") as f:
                f.write("outside the target")
            base = self._serve(target)
            for bad, desc in [
                ("../secret.txt", "parent traversal"),
                ("/etc/passwd", "absolute path"),
                ("~x", "tilde"),
                ("", "empty"),
                (".", "dot"),
            ]:
                with self.assertRaises(urllib.error.HTTPError) as cm:
                    self._get_bytes(base + "/filebytes?p=" +
                                    urllib.parse.quote(bad, safe=''))
                self.assertEqual(
                    cm.exception.code, 404,
                    f"/filebytes did not refuse {desc}: {bad!r}")
            # A symlink that resolves outside the target root: the link
            # itself sits inside the target (so it would pass a naive
            # strings-only check) but realpath follows it to d/secret.txt.
            link = os.path.join(target, "escape.link")
            os.symlink(os.path.join(d, "secret.txt"), link)
            with self.assertRaises(urllib.error.HTTPError) as cm:
                self._get_bytes(base + "/filebytes?p=escape.link")
            self.assertEqual(cm.exception.code, 404)

    def test_fileview_no_truncation_for_oversize_binary(self):
        # PROOF 1 (truncation half): a binary file over the OLD text cap is
        # served whole. read_text used to clamp at 200_000 CHARACTERS, which
        # corrupted images too; /filebytes has no such cap, and this test
        # would fail if anyone re-introduced one (the served length would
        # come back clamped to the limit). The limit is derived at runtime.
        OLD_LIMIT = watch.read_text.__defaults__[0]
        with tempfile.TemporaryDirectory() as d:
            target = make_target(d)
            big = self._build_png(OLD_LIMIT + 12345)
            with open(os.path.join(target, "big.png"), "wb") as f:
                f.write(big)
            self.assertGreater(len(big), OLD_LIMIT)  # precondition, derived
            base = self._serve(target)
            # Magic matches, extension allowlisted → served inline.
            status, served, h = self._get_bytes(base + "/filebytes?p=big.png")
            self.assertEqual(len(served), len(big))
            self.assertEqual(h["content-type"], "image/png")

    # ── #354: /filebytes streams; never materialises the body ─────────────
    # Headers-only checks cannot tell read-all-then-slice from real streaming:
    # both produce byte-identical bodies and the same Content-Length. The
    # load-bearing proof observes per-read return sizes at the body open.

    class _ReadSizeProbe:
        """File wrapper that logs every read() return length.

        Installed on the fixture path only. detect_file_kind's 32-byte magic
        probe appears in the log (small, always ≤ CHUNK) and is not filtered
        out — a whole-file read is distinguished by returning more than
        FILEBYTES_CHUNK bytes in a single call, which magic never does.
        """
        def __init__(self, real, log):
            self._real = real
            self._log = log

        def read(self, size=-1):
            data = self._real.read(size)
            self._log.append({"req": size, "got": len(data)})
            return data

        def __enter__(self):
            self._real.__enter__()
            return self

        def __exit__(self, *a):
            return self._real.__exit__(*a)

        def close(self):
            return self._real.close()

        def __getattr__(self, name):
            return getattr(self._real, name)

    def _track_fixture_reads(self, fixture_path, reads):
        """Patch builtins.open so rb opens of `fixture_path` are probed."""
        import builtins
        path_real = os.path.realpath(fixture_path)
        real_open = builtins.open

        def probe_open(file, mode="r", *args, **kwargs):
            f = real_open(file, mode, *args, **kwargs)
            try:
                if (isinstance(mode, str) and "r" in mode and "b" in mode
                        and os.path.realpath(file) == path_real):
                    return self._ReadSizeProbe(f, reads)
            except OSError:
                pass
            return f

        return unittest.mock.patch("builtins.open", probe_open)

    def test_a_plain_get_never_reads_the_whole_file_at_once(self):
        """#354 A2 — body path never issues one whole-file read.

        Production lines that must break for red:
          - Handler._send_bytes body strategy (was `data = read_bytes(full)`)
          - read_bytes's unbounded `return f.read()` if reattached

        Restoring either form of whole-file materialisation makes a single
        read return the full 512 KiB and this fails. A hollow implementation
        that reads everything then writes 64 KiB pieces is caught the same
        way — the write loop is invisible to the HTTP body, but the read
        log is not.
        """
        CHUNK = watch.FILEBYTES_CHUNK
        FILE_SIZE = 512 * 1024
        # Precondition the check depends on: file larger than one chunk, or
        # a whole-file read is indistinguishable from a single chunk read.
        self.assertGreater(FILE_SIZE, CHUNK,
                           "fixture must exceed one chunk or max-read is vacuous")
        self.assertEqual(CHUNK, 65536)

        with tempfile.TemporaryDirectory() as d:
            target = make_target(d)
            # Binary head so kind=binary (attachment path); body is payload.
            blob = b"\x00\x01" + b"p" * (FILE_SIZE - 2)
            path = os.path.join(target, "stream.bin")
            with open(path, "wb") as f:
                f.write(blob)
            self.assertEqual(os.path.getsize(path), FILE_SIZE)

            reads = []
            base = self._serve(target)
            with self._track_fixture_reads(path, reads):
                status, served, h = self._get_bytes(
                    base + "/filebytes?p=stream.bin")
            self.assertEqual(status, 200)
            self.assertEqual(served, blob)
            self.assertEqual(int(h["content-length"]), FILE_SIZE)

            self.assertTrue(reads, "instrumentation saw no reads; seam missed")
            got_sizes = [r["got"] for r in reads if r["got"] > 0]
            self.assertTrue(got_sizes, "no positive-length reads recorded")
            largest = max(got_sizes)
            # The property under test — report this number, not "it works".
            self.assertLessEqual(
                largest, CHUNK,
                "largest single read was %d on a %d-byte file; a whole-file "
                "or oversize read means the body is still being materialised"
                % (largest, FILE_SIZE))
            # Total payload bytes observed across reads covers the file
            # (magic probe re-reads the head on a second open; allow that).
            total_got = sum(r["got"] for r in reads)
            self.assertGreaterEqual(total_got, FILE_SIZE)

            # Neighbours of the chunk boundary — same property, same seam.
            for label, n in (
                ("zero-byte", 0),
                ("exactly-one-chunk", CHUNK),
                ("one-over-a-chunk", CHUNK + 1),
            ):
                with self.subTest(neighbour=label, n=n):
                    nb = ((b"\x00\x01" + b"n" * (n - 2)) if n >= 2
                          else b"\x00" * n)
                    npath = os.path.join(target, "n-%s.bin" % label)
                    with open(npath, "wb") as f:
                        f.write(nb)
                    nreads = []
                    with self._track_fixture_reads(npath, nreads):
                        st, body, _ = self._get_bytes(
                            base + "/filebytes?p=" + os.path.basename(npath))
                    self.assertEqual(st, 200)
                    self.assertEqual(body, nb)
                    if n == 0:
                        # No positive body read required; empty is fine.
                        pos = [r["got"] for r in nreads if r["got"] > 0]
                        self.assertTrue(all(g <= CHUNK for g in pos))
                    else:
                        pos = [r["got"] for r in nreads if r["got"] > 0]
                        self.assertTrue(pos)
                        self.assertLessEqual(max(pos), CHUNK)
                        self.assertGreaterEqual(sum(r["got"] for r in nreads),
                                                n)

            # Sparse large file (plan A3): logical size ≫ disk, still no
            # whole-file read. Reuses the plan's truncate idiom — NOT
            # RLIMIT_FSIZE (that one is for write failures, #370).
            sparse_size = 32 * 1024 * 1024  # 32 MiB logical; suite-friendly
            spath = os.path.join(target, "huge.bin")
            with open(spath, "wb") as f:
                f.write(b"\x00\x01")
                f.truncate(sparse_size)
            st_stat = os.stat(spath)
            self.assertEqual(st_stat.st_size, sparse_size)
            disk = st_stat.st_blocks * 512
            self.assertLess(
                disk, sparse_size // 8,
                "fixture is not sparse (disk=%d, logical=%d); refuse to "
                "pretend a full allocation is the large-file condition"
                % (disk, sparse_size))
            sreads = []
            with self._track_fixture_reads(spath, sreads):
                st, body, hdr = self._get_bytes(
                    base + "/filebytes?p=huge.bin")
            self.assertEqual(st, 200)
            self.assertEqual(int(hdr["content-length"]), sparse_size)
            self.assertEqual(len(body), sparse_size)
            spos = [r["got"] for r in sreads if r["got"] > 0]
            self.assertTrue(spos)
            self.assertLessEqual(max(spos), CHUNK)

    def test_content_length_comes_from_stat_not_from_reading(self):
        """#354 — Content-Length is the stat size, set before the body is read.

        Production line: `_send_bytes` Content-Length source (was
        `str(len(data))` after `read_bytes`). Red: restore
        `data = read_bytes(full)` + `Content-Length: len(data)` — then by
        the time end_headers runs the whole body has already been read, and
        the order assertion below fails. Also fails if getsize is never
        consulted for the body path.
        """
        FILE_SIZE = 100_000
        with tempfile.TemporaryDirectory() as d:
            target = make_target(d)
            blob = b"\x00BIN" + b"c" * (FILE_SIZE - 4)
            path = os.path.join(target, "sized.bin")
            with open(path, "wb") as f:
                f.write(blob)
            size = os.path.getsize(path)
            self.assertEqual(size, FILE_SIZE)

            reads = []
            bytes_at_end_headers = []
            real_eh = http.server.BaseHTTPRequestHandler.end_headers
            real_getsize = os.path.getsize
            getsize_hits = []

            def spy_eh(handler_self):
                bytes_at_end_headers.append(sum(r["got"] for r in reads))
                return real_eh(handler_self)

            def spy_getsize(p):
                try:
                    getsize_hits.append(os.path.realpath(p))
                except OSError:
                    getsize_hits.append(p)
                return real_getsize(p)

            base = self._serve(target)
            with self._track_fixture_reads(path, reads), \
                    unittest.mock.patch.object(
                        http.server.BaseHTTPRequestHandler,
                        "end_headers", spy_eh), \
                    unittest.mock.patch("os.path.getsize", spy_getsize):
                status, served, h = self._get_bytes(
                    base + "/filebytes?p=sized.bin")
            self.assertEqual(status, 200)
            self.assertEqual(h["content-length"], str(size))
            self.assertEqual(served, blob)
            self.assertIn(os.path.realpath(path), getsize_hits,
                          "Content-Length path never called getsize")
            self.assertTrue(bytes_at_end_headers,
                            "end_headers never observed")
            # When headers closed, the body must not already be in memory.
            # Magic probe may have read 32 bytes; the whole file must not.
            self.assertLess(
                bytes_at_end_headers[0], size,
                "by end_headers the fixture had already been fully read "
                "(%d bytes) — Content-Length was derived from a materialised "
                "body, not from stat" % bytes_at_end_headers[0])

    def test_review_serves_shell_reviewraw_serves_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            rd = os.path.join(d, ".dreamwork", "review")
            os.makedirs(rd)
            with open(os.path.join(rd, "plan-review.html"), "w") as f:
                f.write("<!doctype html><title>R</title><p>review body")
            base = self._serve(d)
            # /review returns the app shell; the client renders the view
            status, body = self._get(base + "/review?p=plan-review.html")
            self.assertEqual(status, 200)
            self.assertIn('id="view"', body)
            # /reviewraw returns the raw artifact for the iframe
            status, raw = self._get(base + "/reviewraw?p=plan-review.html")
            self.assertEqual(status, 200)
            self.assertIn("review body", raw)

    def test_reviewraw_blocks_escape_and_missing(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            for bad in ("/reviewraw?p=../questions.md",
                        "/reviewraw?p=sub/dir.html",
                        "/reviewraw?p=missing.html"):
                with self.assertRaises(urllib.error.HTTPError) as cm:
                    self._get(base + bad)
                self.assertEqual(cm.exception.code, 404)

    def test_research_serves_shell_researchraw_serves_artifact(self):
        # #484 — same pair as /review + /reviewraw, over docs/research.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            rd = os.path.join(d, ".dreamwork", "docs", "research")
            os.makedirs(rd)
            with open(os.path.join(rd, "window-coords.html"), "w") as f:
                f.write("<!doctype html><title>R</title><p>research body")
            base = self._serve(d)
            # /research (list) and /research?p= both return the app shell;
            # the client router renders the matching view.
            for path in ("/research", "/research?p=window-coords.html"):
                status, body = self._get(base + path)
                self.assertEqual(status, 200)
                self.assertIn('id="view"', body)
            # /researchraw returns the raw artifact for the iframe.
            status, raw = self._get(base + "/researchraw?p=window-coords.html")
            self.assertEqual(status, 200)
            self.assertIn("research body", raw)

    def test_researchraw_blocks_escape_src_and_missing(self):
        # The src/ half is the load-bearing one: a source is .html under the
        # research tree, and only the no-slash basename rule keeps it from
        # being served as a finished artifact.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            rd = os.path.join(d, ".dreamwork", "docs", "research")
            os.makedirs(os.path.join(rd, "src"))
            with open(os.path.join(rd, "src", "draft.html"), "w") as f:
                f.write("<!doctype html><p>half-built source")
            self.assertTrue(os.path.isfile(
                os.path.join(rd, "src", "draft.html")))
            base = self._serve(d)
            for bad in ("/researchraw?p=../review/x.html",
                        "/researchraw?p=src/draft.html",
                        "/researchraw?p=missing.html"):
                with self.assertRaises(urllib.error.HTTPError) as cm:
                    self._get(base + bad)
                self.assertEqual(cm.exception.code, 404)

    def test_mtime_carries_generation(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            status, body = self._get(base + "/mtime")
            self.assertEqual(status, 200)
            gen, _, mtime = body.partition(" ")
            self.assertEqual(gen, watch.GENERATION)   # generation first
            self.assertTrue(mtime)
            float(mtime)                              # watched-mtime parses

    def test_comment_threads_and_validates(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))   # QUESTIONS has an Open entry
            status, _ = self._post(base + "/comment", {
                "question": "A real open question?", "comment": "a note",
                "section": "Open"})
            self.assertEqual(status, 202)
            qpath = os.path.join(d, ".dreamwork", "questions.md")
            with open(qpath) as f:
                # #109: the tag names the AUTHOR, not just the channel
                self.assertIn("Note (human, via watch", f.read())
            for bad, code in ((
                    {"question": "A real open question?", "comment": "x",
                     "section": "Nope"}, 202),    # E5: schema_invalid → 202+rejected
                    ({"question": "No such", "comment": "x",
                      "section": "Open"}, 409)):
                if code == 409:
                    with self.assertRaises(urllib.error.HTTPError) as cm:
                        self._post(base + "/comment", bad)
                    self.assertEqual(cm.exception.code, code)
                else:
                    status, _ = self._post(base + "/comment", bad)
                    self.assertEqual(status, code)

    def test_command_appends_event_and_validates(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            status, _ = self._post(base + "/command",
                                   {"kind": "add-idea", "text": "try X"})
            self.assertEqual(status, 202)
            log = os.path.join(d, ".dreamwork", "watch-events.log")
            with open(log) as f:
                self.assertIn("command via watch: add-idea: try X", f.read())
            # do-next may omit text
            status, _ = self._post(base + "/command",
                                   {"kind": "do-next", "text": ""})
            self.assertEqual(status, 202)
            # E5: unknown kind and a text-requiring kind with no text are 202
            # + durable rejected, not a synchronous 400.
            for bad in ({"kind": "nope", "text": "x"},
                        {"kind": "do-now", "text": ""}):
                status, _ = self._post(base + "/command", bad)
                self.assertEqual(status, 202)

    def test_composer_textarea_reserves_scrollbar_gutter(self):
        # #464 — the command composer's text reflowed when the scrollbar
        # vanished as the box grew tall enough to hold every line. The fix
        # is reserving the gutter (`scrollbar-gutter:stable`), not a
        # permanently-visible bar: both remove the reflow; the gutter does
        # it without adding furniture.
        #
        # PRODUCTION LINE whose change reds this test: the
        # `#cmdform textarea { … scrollbar-gutter:stable; … }` declaration
        # in STYLE. Removing that one property fails the body assert; a
        # rule on a different selector fails the match. No new seam — the
        # pre-diff code simply lacks the property, so a red run against
        # HEAD-before-the-diff is the same failure.
        # The reduced-motion block also names `#cmdform textarea` (to kill
        # the height transition only). Match the LAYOUT rule by requiring
        # min-height — that property lives only on the real box rule.
        matches = re.findall(r'#cmdform\s+textarea\s*\{([^}]*)\}', watch.PAGE)
        self.assertTrue(matches, "STYLE has no #cmdform textarea rule")
        body = next((b for b in matches if re.search(r'min-height\s*:', b)), None)
        self.assertIsNotNone(
            body,
            f"no #cmdform textarea layout rule (min-height) among {matches!r}")
        self.assertRegex(
            body, r'scrollbar-gutter\s*:\s*stable\b',
            f"#cmdform textarea must reserve its scrollbar gutter so "
            f"overflow on/off never reflows the draft; rule body was "
            f"{body!r}")
        # Autogrow still owns height: overflow:auto stays so past-ceiling
        # still scrolls, and reduced-motion only zeros the height transition
        # (a separate rule), never the gutter.
        self.assertRegex(body, r'overflow\s*:\s*auto\b')
        self.assertRegex(
            watch.PAGE,
            r'\.qfield\s+textarea\s*,\s*#cmdform\s+textarea\s*\{[^}]*'
            r'transition\s*:\s*none',
            "reduced-motion must still drop the height travel on the "
            "composer (function stays; timing goes)")


class TestSubmissionLog(unittest.TestCase):
    """#199 — his words are on disk before anything can refuse them.

    His framing: "because the user's time is the most valuable thing". Before
    this, an answer lived in exactly one place — questions.md — and every write
    path could refuse it and return with nothing recorded. `append_answer`
    returns unmatched when it cannot find the entry, which is precisely what
    #116 was (a title wrapped across lines), so this was a live loss path on
    his input rather than a theoretical one.

    THE TESTS THAT MATTER ARE THE FAILING SUBMISSIONS. That a good POST is
    logged proves almost nothing: it is logged after a successful write, which
    is what the old events log already did. The whole claim is about the
    request that is about to be REJECTED.
    """

    def _serve(self, target):
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), watch.make_handler(target))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)   # LIFO: shutdown runs first
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def _post_raw(self, url, data):
        """POST arbitrary bytes and return the status, error code and all.

        Not `_post`: half of what this class is about is bodies that are not
        JSON at all, and a helper that serialises for you cannot send one.
        """
        req = urllib.request.Request(url, data=data, method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def _post(self, url, obj):
        return self._post_raw(url, json.dumps(obj).encode("utf-8"))

    def _lines(self, d):
        path = os.path.join(d, ".dreamwork", "submissions.log")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(ln) for ln in f if ln.strip()]

    def test_a_rejected_answer_still_leaves_his_text_on_disk(self):
        # THE POINT OF THE WHOLE FILE. 409 is `append_answer` failing to match
        # the entry — #116's shape — and before #199 the handler returned right
        # there, having written nothing anywhere.
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            self.assertEqual(
                self._post(base + "/answer",
                           {"question": "No such question at all",
                            "answer": "an hour of his thinking"}), 409)
            lines = self._lines(d)
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]["path"], "/answer")
            self.assertEqual(lines[0]["req"]["answer"],
                             "an hour of his thinking")

    def test_a_rejected_comment_does_too(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            self.assertEqual(
                self._post(base + "/comment",
                           {"question": "No such", "comment": "his note",
                            "section": "Open"}), 409)
            self.assertEqual(self._lines(d)[0]["req"]["comment"], "his note")

    def test_a_body_that_is_not_json_is_kept_verbatim(self):
        # The payload that fails to PARSE is the one most worth keeping, and it
        # is the one a "log the parsed request" design would drop. `raw`
        # carries it; `why` says which way it was unusable.
        # E5: malformed JSON is 202 + durable rejected, not 400. The body is
        # still witnessed verbatim (#199).
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            self.assertEqual(
                self._post_raw(base + "/answer", b"{not json, his words"), 202)
            ln = self._lines(d)[0]
            self.assertEqual(ln["raw"], "{not json, his words")
            self.assertEqual(ln["why"], "json")
            self.assertNotIn("req", ln)

    def test_a_body_that_is_not_utf8_is_kept_too(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            self.assertEqual(
                self._post_raw(base + "/answer", b'{"a": "\xff\xfe"}'), 202)
            ln = self._lines(d)[0]
            self.assertEqual(ln["why"], "decode")
            self.assertIn("raw", ln)

    def test_an_oversize_body_is_truncated_rather_than_discarded(self):
        # 413 used to mean "nothing was read and nothing was kept". Reading the
        # cap and keeping it means a too-long answer loses its tail instead of
        # all of it.
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            huge = b'{"question": "q", "answer": "' + b'x' * 40_000 + b'"}'
            self.assertEqual(self._post_raw(base + "/answer", huge), 413)
            ln = self._lines(d)[0]
            self.assertTrue(ln["truncated"])
            self.assertEqual(ln["bytes"], len(huge))
            self.assertEqual(ln["why"], "json")     # a cut body cannot parse
            self.assertEqual(len(ln["raw"]), watch.MAX_BODY)
            self.assertIn("xxxx", ln["raw"])        # ...and it is HIS bytes

    def test_it_is_written_before_the_work_not_after_it(self):
        # The ordering claim, tested by removing the thing the handler needs:
        # with no questions.md there is nothing to write to and the handler
        # 404s before it reaches any log line it could have written itself.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            os.remove(os.path.join(d, ".dreamwork", "questions.md"))
            base = self._serve(d)
            self.assertEqual(
                self._post(base + "/answer",
                           {"question": "q", "answer": "still his"}), 404)
            self.assertEqual(self._lines(d)[0]["req"]["answer"], "still his")

    def test_every_post_path_is_logged_including_the_ones_that_succeed(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            self.assertEqual(
                self._post(base + "/answer",
                           {"question": "A real open question?",
                            "answer": "yes"}), 202)
            self.assertEqual(
                self._post(base + "/command",
                           {"kind": "add-idea", "text": "try X"}), 202)
            self.assertEqual(
                self._post(base + "/tint", {"tint": "nope"}), 202)  # E5: domain_invalid → 202+rejected
            self.assertEqual([ln["path"] for ln in self._lines(d)],
                             ["/answer", "/command", "/tint"])

    def test_every_line_has_the_shape_file_formats_states(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            self._post(base + "/answer", {"question": "A real open question?",
                                          "answer": "yes"})
            self._post_raw(base + "/comment", b"garbage")
            lines = self._lines(d)
            # a per-line loop over an empty file passes every assertion in it,
            # which is how this test read GREEN against a watch.py that wrote
            # no log at all
            self.assertEqual(len(lines), 2)
            for ln in lines:
                self.assertEqual(set(ln) & {"t", "path", "bytes"},
                                 {"t", "path", "bytes"})
                self.assertIsInstance(ln["bytes"], int)
                # exactly one of req / raw, and `why` iff `raw`
                self.assertEqual(("req" in ln), ("raw" not in ln))
                self.assertEqual(("why" in ln), ("raw" in ln))
                time.strptime(ln["t"], "%Y-%m-%dT%H:%M:%S")

    def test_an_unroutable_post_is_still_his_words(self):
        # 404 on the PATH, not on the content. Someone typing at a stale
        # endpoint still typed something, and this file is not a router.
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            self.assertEqual(self._post(base + "/nope", {"a": "his text"}), 404)
            self.assertEqual(self._lines(d)[0]["req"]["a"], "his text")


if __name__ == "__main__":
    unittest.main()


class TestBundleParses(unittest.TestCase):
    """The page is one `<script>` assembled from several Python strings, and
    a syntax error anywhere in it takes the WHOLE page down — no router, no
    tick, nothing. Nothing else in `just test` sees that: the pytest half
    asserts substrings, which still match perfectly in a file that will not
    parse, and `lint.py` never looks at the page. The browser guards do catch
    it, twenty minutes later and as thirty unrelated red lines.

    It is not hypothetical. A pair of backticks inside a GLSL *comment* ended
    the JS template literal the shader source lives in, and the rest of the
    shader was parsed as JavaScript — `SyntaxError: Unexpected identifier
    'tint'`, and a blank dashboard.
    """

    def test_page_script_is_valid_javascript(self):
        import shutil
        import subprocess
        import tempfile
        node = shutil.which("node")
        if not node:
            self.skipTest("node not available — the syntax gate did NOT run")
        body = watch.PAGE.split("<script>", 1)[1].rsplit("</script>", 1)[0]
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as f:
            f.write(body)
            path = f.name
        try:
            r = subprocess.run([node, "--check", path],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0,
                             "the page's script does not parse:\n" + r.stderr)
        finally:
            os.unlink(path)


class TestFileHeadingLockup(unittest.TestCase):
    """#284 — the basename is the heading, the parent path is metadata, and
    the copy button promises the EXACT path back.

    What is checkable here and nowhere else is the path SPLIT, which no
    browser guard will reach: a guard drives whatever paths its fixture
    happens to hold, and the cases that matter are the edges (a root-level
    file with no parent, a path with a trailing slash, a name that is all
    dots). Those are one regex away from wrong and silent — a heading that
    renders the whole path again, or a metadata line that invents a `./`.

    The rest of this class is structural, and it is deliberately about the
    two guarantees a rendered-DOM check cannot state as an intention: that
    the path element declares no shortening, and that the copy button opens
    no new attribute-injection site."""

    def _eval(self, expr):
        """Evaluate `expr` against the REAL `fileBase`/`fileDir` source, cut
        out of the page bundle. Not a re-implementation: if either function
        is renamed, deleted or changed, this stops finding it (loud) or
        stops agreeing with it (also loud)."""
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node not available — the path-split gate did NOT run")
        m = re.search(r"const fileBase = .*?\n};\nconst fileDir = .*?\n};",
                      watch.PAGE, re.S)
        self.assertIsNotNone(
            m, "fileBase/fileDir are not in the page in the shape this test "
               "reads them — find them and fix the cut, do not delete the test")
        r = subprocess.run(
            [node, "-e", m.group(0) + "\nconsole.log(JSON.stringify(" + expr + "))"],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_the_split_is_exact_and_invents_nothing(self):
        deep = ".dreamwork/docs/research/contextual-review-annotations.md"
        cases = [
            # path, basename, parent
            (deep, "contextual-review-annotations.md", ".dreamwork/docs/research/"),
            # a root-level file has NO parent: no invented "./"
            ("lint.py", "lint.py", ""),
            # a dotfile at the root is still a root-level file
            (".gitignore", ".gitignore", ""),
            # a trailing slash names no file, so the whole thing is the label
            # and there is no parent to claim
            ("a/b/", "a/b/", ""),
            ("", "", ""),
            # the parent keeps its trailing slash: that slash is a boundary
            # the path really has
            ("a/b.md", "b.md", "a/"),
        ]
        got = self._eval("[" + ",".join(
            "[fileBase(%s), fileDir(%s)]" % (json.dumps(p), json.dumps(p))
            for p, _, _ in cases) + "]")
        for (path, base, parent), (gb, gd) in zip(cases, got):
            self.assertEqual(gb, base, f"basename of {path!r}")
            self.assertEqual(gd, parent, f"parent of {path!r}")
            # THE PROPERTY THAT MATTERS, derived rather than restated: the two
            # halves must reassemble into the path character for character,
            # because the copy button promises exactly that string back.
            if gd:
                self.assertEqual(gd + gb, path)

    def test_the_heading_is_a_real_h1_and_the_title_is_the_basename(self):
        # A screen reader's heading list is the reason this is an <h1> rather
        # than the styled <span> it was, and the copy button describes itself
        # by its id — so both the tag and the id are contract, not decoration.
        self.assertIn('<h1 class="htitle" id="htitle"></h1>', watch.PAGE)
        self.assertIn("file: v => esc(fileBase(v.param || '')),", watch.PAGE)
        # ...and it must not have gained UA weight/size in the process: this
        # page says "more important" with luminance, never with metrics.
        self.assertIn(".htitle { display:inline; font:inherit; margin:0;",
                      watch.PAGE)

    def test_project_identity_is_edge_pinned_in_the_title_bar(self):
        # #172 — basename visible in the title section, pinned so a route
        # change does not move it; full path on title= only. The tab title's
        # dreamwork/<project> compound is already #153; this is the visible
        # bar. Static wiring only — projtitle.mjs proves the geometry.
        self.assertIn('id="hproj"', watch.PAGE)
        self.assertIn('class="hproj"', watch.PAGE)
        self.assertIn('const projectName =', watch.PAGE)
        self.assertIn("margin-left:auto", watch.PAGE)
        # the render path must use the shared basename helper, not invent a
        # second parse of data.target that can drift from the tab title
        self.assertIn('projectName(d)', watch.PAGE)
        # tooltip carries the full path (two checkouts, one basename)
        self.assertIn("projEl.setAttribute('title', path)", watch.PAGE)

    def test_the_path_element_declares_no_shortening(self):
        # His reasoning, and the one rule with no room in it: a path that lies
        # about its own segments is worse than one that takes two lines. So
        # the metadata line may wrap anywhere and may NOT ellipsise, clamp,
        # or refuse to break.
        rule = re.search(r"\n  \.fdir \{(.*?)\}", watch.PAGE, re.S)
        self.assertIsNotNone(rule, "the .fdir rule is gone")
        body = rule.group(1)
        self.assertIn("overflow-wrap:anywhere", body)
        for forbidden in ("text-overflow", "nowrap", "line-clamp", "direction:"):
            self.assertNotIn(forbidden, body,
                             f".fdir must not declare {forbidden}")
        self.assertIn("user-select:text", body)   # the clipboard fallback

    def test_the_copy_button_opens_no_new_attribute_injection_site(self):
        # `esc()` is div.textContent -> innerHTML: it escapes < > &, and NOT
        # the double quote. So any esc()'d value in a double-quoted attribute
        # can be broken out of by a crafted query string, and the button's
        # path is entirely query-controlled. It therefore carries NO path
        # attribute at all and reads `view.param` instead.
        btn = re.search(r"const copyPathBtn = .*?;\n", watch.PAGE, re.S)
        self.assertIsNotNone(btn, "copyPathBtn is gone")
        self.assertNotIn("esc(", btn.group(0),
                         "the copy button must not interpolate an esc()'d "
                         "value into an attribute — read view.param instead")
        self.assertIn("view.param", watch.PAGE)
        # associated with the heading for screen readers, and with the
        # metadata line first so the description reads as the full path
        self.assertIn("'fdir htitle' : 'htitle'", btn.group(0))

    def test_both_copy_outcomes_speak_on_the_one_confirmation_lifecycle(self):
        # One idiom, not a second: `.cmdmsg` is the composer's component and
        # `confirmationFor` is the composer's lifecycle. `note` is the only
        # thing added — claim WITH the hold-and-depart lifecycle.
        self.assertIn("confirmationFor(document, 'fmsg', 'cmdmsg fmsg', rmr)",
                      watch.PAGE)
        self.assertIn("note:(text,ok=true)=>show(text,ok,true)", watch.PAGE)
        self.assertIn("c.note('path copied', true)", watch.PAGE)
        self.assertIn(
            "c.note('copy was blocked — the path beside it is selectable', false)",
            watch.PAGE)
        # the live region, or nothing is announced at all
        self.assertIn('<div class="cmdmsg fmsg" id="fmsg" aria-live="polite">',
                      watch.PAGE)


class TestFileViewMode(unittest.TestCase):
    """#252 — Rendered / Source for markdown at `/file`.

    The browser guard drives the switch; what belongs here is the pair of
    guarantees that are about the SHAPE of the code rather than about the
    rendered page, because both are the kind of thing a later edit undoes
    without any check noticing:

    - **Source is the verbatim path that already existed**, not a second
      renderer. If a highlighter or any other transform is ever introduced
      between the server's string and the escaped text node, the mode stops
      being what he asked for — and #351 is an open request to add exactly
      such a highlighter to this view.
    - **`?view=source` is a ROUTE**, read in one place and written in one
      place, so a copied link and the page it came from cannot disagree.
    """

    def test_source_is_the_existing_verbatim_path_and_is_never_rewritten(self):
        # The verbatim `<pre>${esc(text)}</pre>` is still the fallback every
        # unhighlighted file renders — both markdown modes read `src`, so
        # there is no second renderer to drift.
        self.assertIn("`<pre>${esc(text)}</pre>`", watch.PAGE)
        # #522: mdB takes the file path as second arg for relative links;
        # pin the call site prefix so the branch remains the production line
        self.assertIn(
            "const body = (isMarkdownFile(param) && mode !== 'source')",
            watch.PAGE)
        self.assertIn("mdB(text, param)", watch.PAGE)
        self.assertIn(": src;", watch.PAGE)
        # The render-plain condition is EXPLICIT, never "no hl happened to
        # arrive": the guarantee must not depend on what the server chose to
        # send (#252's own note about the #351 collision).
        self.assertIn(
            "const renderPlain = isMarkdownFile(param) && mode === 'source';",
            watch.PAGE,
            "Source must NAME its render-plain condition (#252 vs #351)")
        self.assertIn("(!renderPlain && fetched.hl) ? fetched.hl", watch.PAGE,
                      "the highlighted branch must be gated by the negation "
                      "of that same condition")

    def _buildfile_eval(self, expr):
        """Evaluate `expr` against the REAL `isMarkdownFile`/`buildFile`
        source, cut out of the page bundle (the fileBase harness's shape).
        `esc` needs a DOM, so it is stubbed by its exact contract — escape
        & < >, nothing else — and `mdB` by a marker, so the branch taken is
        observable. If either function changes shape this stops finding it
        (loud), which is the point."""
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node not available — the buildFile gate did NOT run")
        cuts = []
        for pat, name in (
                (r"function isMarkdownFile\(p\) \{.*?\n\}", "isMarkdownFile"),
                (r"function buildFile\(param, fetched, mode\) \{.*?\n\}",
                 "buildFile")):
            m = re.search(pat, watch.PAGE, re.S)
            self.assertIsNotNone(
                m, f"{name} is not in the page in the shape this test reads "
                   "it — fix the cut, do not delete the test")
            cuts.append(m.group(0))
        prelude = ("const esc = t => String(t ?? '')"
                   ".replace(/&/g,'&amp;').replace(/</g,'&lt;')"
                   ".replace(/>/g,'&gt;');\n"
                   "const mdB = t => 'MD:' + t;\n")
        r = subprocess.run(
            [node, "-e", prelude + "\n".join(cuts) +
             "\nconsole.log(JSON.stringify(" + expr + "))"],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_source_mode_renders_plain_even_when_highlight_markup_arrived(self):
        """The `assertNotIn("tok-", watch.PAGE)` this class used to hold,
        NARROWED to the Source path rather than deleted (#351's collision
        with #252): the page now legitimately carries `tok-` — the server
        highlights source files, and the palette CSS lives in STYLE — so a
        global absence would fail on the feature itself. What must still
        hold is that a markdown file's Source mode shows no tokeniser output
        even when `hl` arrived, because that pane's bytes are the point of
        the mode. Evaluated against the real buildFile, not restated."""
        hostile = '# t <script> & "q"\n'
        # derived precondition, not a fixture hope: the bytes offered really
        # need escaping, else "escaped exactly" below is a weak claim
        self.assertTrue(all(c in hostile for c in ('<', '&', '"')))
        hl = ('<pre><code class="language-python">'
              '<span class="tok-kw">def</span></code></pre>')
        self.assertIn("tok-", hl)   # else every NotIn below is vacuous
        escaped = (hostile.replace('&', '&amp;').replace('<', '&lt;')
                   .replace('>', '&gt;'))
        # a markdown file in Source mode: the verbatim pre, no tok-, even
        # though the server offered highlighted markup
        src_mode = self._buildfile_eval(
            "buildFile('a/b.md', {text: %s, hl: %s}, 'source')"
            % (json.dumps(hostile), json.dumps(hl)))
        self.assertNotIn("tok-", src_mode,
                         "Source's bytes are the point of the mode (#252)")
        self.assertEqual(src_mode,
                         '<div id="filebody"><pre>' + escaped + '</pre></div>')
        # a source file in either mode takes the server's markup...
        py = self._buildfile_eval(
            "buildFile('x.py', {text: 'def f():\\n    pass\\n', hl: %s}, "
            "'rendered')" % json.dumps(hl))
        self.assertIn(hl, py)
        # ...and an extension the map does not name renders the same
        # verbatim pre it always did: plain, never guessed (#339's rule)
        plain = self._buildfile_eval(
            "buildFile('x.txt', {text: %s, hl: null}, 'rendered')"
            % json.dumps(hostile))
        self.assertNotIn("tok-", plain)
        self.assertIn('<pre>' + escaped + '</pre>', plain)
        # Rendered markdown is mdB's, untouched by any of this
        rend = self._buildfile_eval(
            "buildFile('a.md', {text: '# hi\\n', hl: null}, 'rendered')")
        self.assertEqual(rend, '<div id="filebody">MD:# hi\n</div>')

    def test_the_mode_is_read_from_the_route_and_written_back_to_it(self):
        # Read in exactly one place...
        self.assertEqual(
            1, watch.PAGE.count("sp.get('view') === 'source' ? 'source' : 'rendered'"),
            "the mode must be parsed in routeOf and nowhere else")
        # ...and written in exactly one place, so a deep link and the address
        # bar cannot disagree about which mode is showing.
        self.assertEqual(
            1, watch.PAGE.count("(mode === 'source' ? '&view=source' : '')"))
        # an unknown value is rendered, never a third state
        self.assertIn("const mode = opts.mode === 'source' ? 'source' : 'rendered';",
                      watch.PAGE)
        # every entry point into navigate carries it, or one of them silently
        # loses the mode (the deep-link bug this was red-proved against)
        for site in ("{ push: true, q: r.q, mode: r.mode }",
                     "{ push: false, q: r.q, mode: r.mode }",
                     "{ push: false, transition: false, q: r.q, mode: r.mode }"):
            self.assertIn(site, watch.PAGE, f"navigate call missing the mode: {site}")

    def test_the_switch_is_links_markdown_only_and_holds_its_own_state(self):
        # Links, not buttons: that is what makes the mode deep-linkable, the
        # switch keyboard-operable, and the swap ride the router's dissolve.
        sw = re.search(r"const fileModeSwitch = .*?\n};", watch.PAGE, re.S)
        self.assertIsNotNone(sw, "fileModeSwitch is gone")
        self.assertIn('<a class="sgbtn fmode" data-mode="rendered"', sw.group(0))
        self.assertIn('<a class="sgbtn fmode" data-mode="source"', sw.group(0))
        self.assertNotIn("<button", sw.group(0))
        # the `.on` state is NOT in the html — see paintFileMode: a rewritten
        # crumb is fresh nodes, and a fresh .sgind grows out of the row's left
        # edge instead of sliding to the other label
        self.assertNotIn("fmode on", sw.group(0))
        self.assertIn("stable: true", watch.PAGE)
        self.assertIn("if (isMarkdownFile(p))", watch.PAGE)
        # ...and the sliding group is the SHARED one, not a second switch
        self.assertIn('class="sgroup fmodes"', watch.PAGE)
        self.assertIn("slideIndicator(g, !slide)", watch.PAGE)

    def test_mobile_keeps_both_labels_in_one_row(self):
        # His rule. `.sgroup` wraps by default and a wrapped two-position
        # switch is a stack with the indicator sliding vertically through it.
        rule = re.search(r"\n  #meta \.fmodes \{(.*?)\}", watch.PAGE, re.S)
        self.assertIsNotNone(rule, "the #meta .fmodes rule is gone")
        self.assertIn("flex-wrap:nowrap", rule.group(1))
        # ...and it must OUT-SPECIFY `.sgroup`, which re-declares
        # `display:flex; flex-wrap:wrap` later in the same sheet at plain class
        # specificity. A bare `.fmodes` lost both, which made the switch a
        # block-level flex container that broke its own crumb in two.
        self.assertIn("display:inline-flex", rule.group(1))
        self.assertLess(watch.PAGE.index("#meta .fmodes {"),
                        watch.PAGE.index("  .sgroup {"),
                        "this block sits ABOVE .sgroup, so its selector — not "
                        "source order — is what makes the display stick")
        # nothing may hide either half at any width
        for m in re.finditer(r"\.fmodes?[^{]*\{[^}]*display:none[^}]*\}", watch.PAGE):
            self.fail(f"a width hides part of the switch: {m.group(0)!r}")

    def test_the_reading_position_is_measured_in_layout_space(self):
        # Two traps, both documented in transitions.md and both live on this
        # path: `documentElement.scrollHeight` counts the outgoing GHOST, and
        # `getBoundingClientRect` reads visual space while `#view` is
        # mid-`enter` (pushed back in Z and scaled down). offsetTop/offsetHeight
        # are immune to both.
        fn = re.search(r"function contentBottom\(\) \{.*?\n\}", watch.PAGE, re.S)
        self.assertIsNotNone(fn, "contentBottom is gone")
        body = fn.group(0)
        self.assertIn("offsetTop", body)
        self.assertIn("offsetHeight", body)
        for forbidden in ("getBoundingClientRect", "scrollHeight"):
            self.assertNotIn(forbidden, body,
                             f"contentBottom must not use {forbidden} — it "
                             f"answers for the ghost or for a transform")
        # a ratio, not a pixel offset: the two panes are different heights
        self.assertIn("window.scrollY / range", watch.PAGE)
        self.assertIn("if (modeSwap) restoreScrollRatio(keepRatio);", watch.PAGE)


class TestFileSourceHighlight(unittest.TestCase):
    """#351 — /file highlights source, runs wider, and does not wrap lines.

    His words, typed from /file?p=lint.py: "syntax highlighting for source
    code files, and a bit wider of a body + no line wrapping." Three changes,
    three sets of guarantees:

    - the highlighter is review_artifact.py's #339 scanner, REUSED through
      its public highlight() — there is no second tokeniser to drift;
    - the language comes from the extension and an unknown one renders plain
      (#339's never-guess rule, which /file inherits whole);
    - the /filedata cache is keyed by path and validated by (mtime_ns, size)
      — the same staleness predicate the dashboard already trusts — and the
      wrap/width change is scoped to the pane it was asked for.
    """

    def _serve(self, target):
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), watch.make_handler(target))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def _get(self, url):
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read().decode("utf-8")

    def test_the_language_map_only_names_supported_languages(self):
        import review_artifact
        # DERIVED, never restated: the supported set is the scanner's own,
        # so a language removed there fails here without an edit.
        self.assertTrue(review_artifact.SUPPORTED_LANGUAGES)
        self.assertTrue(watch._FILE_LANG)
        for ext, lang in watch._FILE_LANG.items():
            self.assertIn(lang, review_artifact.SUPPORTED_LANGUAGES,
                          f"{ext} maps to {lang}, which the scanner does "
                          "not tokenise — that is guessing by another name")
            self.assertTrue(ext.startswith(".") and ext == ext.lower(),
                            f"{ext!r} must be a lowercase dot-extension")

    def test_highlight_round_trips_the_served_bytes(self):
        # The pane's textContent must be the file. #339 proves the scanner
        # byte-exact; what is NOT proved there is the seam THIS adds — the
        # escape/wrap/highlight/unescape round-trip through the public
        # entry point — so it is proved here on hostile bytes.
        src = '# c <tag> & "q"\ndef f(a):\n    return "x" + \'y\' — 1\n'
        self.assertTrue(all(c in src for c in ('<', '&', '"', '—')))
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.py")
            with open(p, "w", encoding="utf-8") as f:
                f.write(src)
            hl = watch.file_highlight_html(p, src)
        self.assertIsNotNone(hl)
        # preconditions, derived at runtime: the markup really is the
        # highlighted block shape, and it really tokenised (three kinds,
        # so "round-trip" is not passing over an all-fallback scan)
        m = re.search(r"<pre><code[^>]*>(.*?)</code></pre>", hl, re.S)
        self.assertIsNotNone(m)
        kinds = set(re.findall(r'class="tok-([a-z]+)"', m.group(1)))
        self.assertGreaterEqual(len(kinds), 3,
                                f"only {kinds} token kinds — the fixture "
                                "stopped exercising the scanner")
        text = html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))
        self.assertEqual(text, src)

    def test_unknown_extension_renders_plain(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("x.txt", "x.md", "x.rst", "Makefile", "x.py.bak",
                         "x.fish"):
                p = os.path.join(d, name)
                with open(p, "w") as f:
                    f.write("def f(): pass\n")
                self.assertIsNone(watch.file_highlight_html(p, "def f(): pass\n"),
                                  f"{name} must render plain — never guess")

    def test_the_cache_is_a_cache_and_mtime_invalidates_it(self):
        watch._file_hl_cache.clear()
        self.addCleanup(watch._file_hl_cache.clear)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "m.py")
            src1 = "# one\ndef a():\n    return 1\n"
            with open(p, "w") as f:
                f.write(src1)
            h1 = watch.file_highlight_html(p, src1)
            self.assertIsNotNone(h1)
            # IDENTITY is the claim: the same file version returns the same
            # object, which is the only form "the tokeniser did not run
            # again" can take.
            self.assertIs(watch.file_highlight_html(p, src1), h1)
            # a new version recomputes...
            src2 = "# two\ndef b():\n    return 2\n"
            with open(p, "w") as f:
                f.write(src2)
            os.utime(p, (1700000000, 1700000000))
            h2 = watch.file_highlight_html(p, src2)
            self.assertIsNot(h2, h1)
            # ...and the precondition that gives that meaning: the two
            # versions really tokenise to different markup, else
            # "invalidated" is vacuous.
            self.assertNotEqual(h1, h2)
            self.assertIn("two", h2)
            # The predicate IS mtime, not content — the recorded decision.
            # The same bytes at a new mtime recompute; that is the edge the
            # /mtime poll has always accepted, not a bug found late.
            os.utime(p, (1700000100, 1700000100))
            self.assertIsNot(watch.file_highlight_html(p, src2), h2)

    def test_the_cache_is_bounded(self):
        watch._file_hl_cache.clear()
        self.addCleanup(watch._file_hl_cache.clear)
        with tempfile.TemporaryDirectory() as d:
            for i in range(watch._FILE_HL_CACHE_MAX + 5):
                p = os.path.join(d, "f%d.py" % i)
                src = "x = %d\n" % i
                with open(p, "w") as f:
                    f.write(src)
                watch.file_highlight_html(p, src)
        self.assertLessEqual(len(watch._file_hl_cache),
                             watch._FILE_HL_CACHE_MAX)

    def test_filedata_serves_highlight_alongside_the_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            src = "def f():\n    return '<tag>' & 1\n"
            with open(os.path.join(d, "m.py"), "w") as f:
                f.write(src)
            with open(os.path.join(d, "n.txt"), "w") as f:
                f.write("plain\n")
            base = self._serve(d)
            status, body = self._get(base + "/filedata?p=m.py")
            self.assertEqual(status, 200)
            j = json.loads(body)
            # the bytes still arrive — highlighting ADDS a field, it does
            # not replace the verbatim content the Source pane is made of
            self.assertEqual(j["content"], src)
            self.assertIn("tok-", j["hl"])
            self.assertIn("language-python", j["hl"])
            status, body = self._get(base + "/filedata?p=n.txt")
            self.assertEqual(status, 200)
            self.assertNotIn("hl", json.loads(body),
                             "an unknown extension gets no markup at all — "
                             "the client must never see a guess")

    def test_nowrap_is_scoped_to_the_source_pane(self):
        # The pane is code and code does not wrap; a long line scrolls
        # INSIDE it (watch-design.md: wide content scrolls inside its own
        # container). `.md pre.mdcode` already kept exactly this contract
        # for fences, so the idiom is reused, not authored twice.
        rule = re.search(r"\n  #filebody > pre \{(.*?)\}", watch.PAGE, re.S)
        self.assertIsNotNone(rule, "the #filebody > pre rule is gone")
        self.assertIn("white-space:pre", rule.group(1))
        self.assertIn("overflow-x:auto", rule.group(1))
        # ...and the change is SCOPED: every other <pre> on the page (preB
        # peeks — prose) keeps wrapping, and so does the global rule.
        self.assertIn("pre { white-space:pre-wrap", watch.PAGE)
        self.assertIn(".md pre.mdcode { margin:.45rem 0; white-space:pre; "
                      "overflow-x:auto; }", watch.PAGE)
        # the highlighted pane carries <code>; the prose inline-code chip
        # must be reset there or it plates the whole block
        self.assertIn("#filebody > pre > code {", watch.PAGE)

    def test_the_column_widens_on_the_file_route_only(self):
        self.assertIn("body.file .wrap { max-width:110ch; }", watch.PAGE)
        self.assertIn("body.review .wrap { max-width:1360px; }", watch.PAGE)
        self.assertIn(".wrap { max-width:72ch;", watch.PAGE)
        # the width class is committed at EVERY route commit, beside review's
        # — derived from review's own count, so a fourth site added for one
        # and not the other fails here without an edit
        self.assertEqual(
            watch.PAGE.count("classList.toggle('review',"),
            watch.PAGE.count("classList.toggle('file',"))
        self.assertGreaterEqual(
            watch.PAGE.count("classList.toggle('file',"), 3)

    def test_the_token_palette_is_scoped_and_warn_is_not_spent(self):
        # every token kind the scanner emits has a rule INSIDE the pane —
        # the kind set is derived from the emitted classes in STYLE, and
        # compared against review_artifact's own spec names so a kind added
        # there without CSS here is caught
        import review_artifact
        emitted = set()
        for spec in (review_artifact._PY, review_artifact._JSON,
                     review_artifact._BASH, review_artifact._JS,
                     review_artifact._HTML, review_artifact._SQL):
            emitted.update(name for name, _ in spec)
        self.assertTrue(emitted)
        for kind in emitted:
            self.assertIn("#filebody > pre code .tok-%s {" % kind, watch.PAGE,
                          f"tok-{kind} has no colour inside the pane")
        # --warn means BROKEN on this page (#136); a numeral is not broken.
        # The palette declares --amber instead, value-for-value the
        # artifact frame's.
        rules = re.findall(r"#filebody > pre code \.tok-[a-z]+ \{[^}]*\}",
                           watch.PAGE)
        self.assertTrue(rules)
        for rule in rules:
            self.assertNotIn("--warn", rule)
        self.assertIn("--amber:#fcd34d;", watch.PAGE)


class TestProjectTint(unittest.TestCase):
    """#143 — his colour for this project, on disk and in the page."""

    def test_read_tint_falls_back_rather_than_blanking(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".dreamwork"))
            self.assertEqual(watch.read_tint(d), watch.TINT_DEFAULT)  # absent
            p = os.path.join(d, ".dreamwork", "watch-tint")
            with open(p, "w") as f:
                f.write("green\n")
            self.assertEqual(watch.read_tint(d), "green")
            # An unknown name shows him the default rather than nothing: the
            # failure that loses nothing. It is also SILENT, which is exactly
            # why lint.py checks this file.
            with open(p, "w") as f:
                f.write("chartreuse\n")
            self.assertEqual(watch.read_tint(d), watch.TINT_DEFAULT)

    def test_write_tint_refuses_a_name_outside_the_set(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".dreamwork"))
            self.assertTrue(watch.write_tint(d, "teal"))
            self.assertFalse(watch.write_tint(d, "chartreuse"))
            # ...and refusing means not writing, not writing something else
            self.assertEqual(watch.read_tint(d), "teal")

    def test_tints_avoid_the_warn_band(self):
        # --warn amber is ~45deg and means BROKEN. A project tinted into that
        # band would paint its whole ambient field the one colour on this page
        # that must never read as anything but a fault.
        for name, hue in watch.TINTS.items():
            self.assertFalse(35 <= hue <= 70,
                             f"{name} ({hue}deg) sits in the --warn band")
        self.assertIn(watch.TINT_DEFAULT, watch.TINTS)

    def test_page_carries_the_tint_vocabulary_and_wiring(self):
        # ONE source, like COMMANDS: the server validates POST /tint against
        # TINTS and the page renders its picker from the same dict, so a name
        # the picker offers is always one the server will accept.
        self.assertIn("const TINTS = " + json.dumps(watch.TINTS), watch.PAGE)
        for token in ('function applyTint(', 'function tintPicker(',
                      'async function pickTint(', "fetch('/tint'",
                      'setProjHue', 'uniform float projHue'):
            self.assertIn(token, watch.PAGE)

    def test_no_backtick_in_a_shader_comment(self):
        # The GLSL lives in JS template literals, so a pair of backticks in a
        # COMMENT ends the literal and the rest of the shader is parsed as
        # JavaScript — the whole page goes blank. TestBundleParses catches the
        # consequence exactly; this one names the cause, because "the page
        # does not parse" is a long way from "take the quotes out of that
        # sentence".
        for i, line in enumerate(watch.SHADER_JS.splitlines(), 1):
            head = line.strip()
            if head.startswith(("/*", "*", "//")) and "`" in line:
                self.fail(f"backtick in a shader comment, line {i}: {head!r}")


class TestRunMode(unittest.TestCase):
    """#290 — dashboard-settable main-dreamer run mode.

    Authoritative machine-local file + dual-write event on change only.
    Hierarchical is planned/disabled UI, not a selectable write target.
    """

    def _serve(self, target):
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), watch.make_handler(target))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def _post(self, url, obj):
        req = urllib.request.Request(
            url, data=json.dumps(obj).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def _lines(self, d):
        path = os.path.join(d, ".dreamwork", "submissions.log")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(ln) for ln in f if ln.strip()]

    def test_closed_v1_vocabulary(self):
        self.assertEqual(tuple(watch.RUN_MODES),
                         ("lackadaisical", "hot", "assisted"))
        self.assertEqual(watch.RUN_MODE_DEFAULT, "lackadaisical")
        self.assertIn(watch.RUN_MODE_DEFAULT, watch.RUN_MODES)
        self.assertEqual(tuple(watch.RUN_MODES_PLANNED), ("hierarchical",))
        for m in watch.RUN_MODES_PLANNED:
            self.assertNotIn(m, watch.RUN_MODES)

    def test_read_falls_back_when_absent_or_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".dreamwork"))
            self.assertEqual(watch.read_run_mode(d), watch.RUN_MODE_DEFAULT)
            p = os.path.join(d, ".dreamwork", "run-mode")
            with open(p, "w", encoding="utf-8") as f:
                f.write("hot\n")
            self.assertEqual(watch.read_run_mode(d), "hot")
            with open(p, "w", encoding="utf-8") as f:
                f.write("hierarchical\n")  # planned, not selectable — fallback
            self.assertEqual(watch.read_run_mode(d), watch.RUN_MODE_DEFAULT)
            with open(p, "w", encoding="utf-8") as f:
                f.write("warp-speed\n")
            self.assertEqual(watch.read_run_mode(d), watch.RUN_MODE_DEFAULT)

    def test_write_refuses_outside_set(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".dreamwork"))
            self.assertTrue(watch.write_run_mode(d, "assisted"))
            self.assertEqual(watch.read_run_mode(d), "assisted")
            self.assertFalse(watch.write_run_mode(d, "hierarchical"))
            self.assertFalse(watch.write_run_mode(d, "nope"))
            self.assertEqual(watch.read_run_mode(d), "assisted")

    def test_run_mode_line_is_one_line_and_from_safe(self):
        self.assertEqual(watch.run_mode_line("hot"),
                         "run-mode via watch: hot")
        self.assertEqual(watch.run_mode_line("hot", "/"),
                         "run-mode via watch [/]: hot")
        # free text cannot forge a second events line
        self.assertEqual(watch.run_mode_line("hot\nforged", "/"),
                         "run-mode via watch [/]: hot forged")
        self.assertEqual(watch.run_mode_line("hot", "]\nforged"),
                         "run-mode via watch: hot")

    def test_collect_exposes_run_mode(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            data = watch.collect(d)
            self.assertEqual(data["run_mode"], watch.RUN_MODE_DEFAULT)
            self.assertTrue(watch.write_run_mode(d, "hot"))
            self.assertEqual(watch.collect(d)["run_mode"], "hot")

    def test_post_writes_file_and_one_event_on_change(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            self.assertEqual(
                self._post(base + "/run-mode",
                           {"mode": "hot", "from": "/"}), 202)
            self.assertEqual(watch.read_run_mode(d), "hot")
            log = os.path.join(d, ".dreamwork", "watch-events.log")
            with open(log, encoding="utf-8") as f:
                lines = [ln for ln in f if "run-mode" in ln]
            self.assertEqual(len(lines), 1)
            self.assertIn("run-mode via watch [/]: hot", lines[0])
            # identical final is idempotent: 202, no second event, file holds
            self.assertEqual(
                self._post(base + "/run-mode", {"mode": "hot"}), 202)
            with open(log, encoding="utf-8") as f:
                lines = [ln for ln in f if "run-mode" in ln]
            self.assertEqual(len(lines), 1)
            self.assertEqual(watch.read_run_mode(d), "hot")

    def test_post_rejects_planned_and_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            # E5: unknown/planned modes are 202 + durable rejected
            # (domain_invalid), not a synchronous 400.
            self.assertEqual(
                self._post(base + "/run-mode", {"mode": "hierarchical"}), 202)
            self.assertEqual(
                self._post(base + "/run-mode", {"mode": "turbo"}), 202)
            self.assertFalse(
                os.path.exists(os.path.join(d, ".dreamwork", "run-mode")))
            log = os.path.join(d, ".dreamwork", "watch-events.log")
            if os.path.exists(log):
                with open(log, encoding="utf-8") as f:
                    self.assertEqual([ln for ln in f if "run-mode" in ln], [])

    def test_page_carries_vocabulary_wiring_and_arm(self):
        self.assertIn("const RUN_MODES = " + json.dumps(list(watch.RUN_MODES)),
                      watch.PAGE)
        self.assertIn("const RUN_MODE_DEFAULT = "
                      + json.dumps(watch.RUN_MODE_DEFAULT), watch.PAGE)
        self.assertIn("const RUN_MODES_PLANNED = "
                      + json.dumps(list(watch.RUN_MODES_PLANNED)), watch.PAGE)
        for token in ('function runModePicker(', 'function pickRunMode(',
                      "fetch('/run-mode'", 'RUN_ARM_MS',
                      'dw:run-mode-pending:', 'hierarchical',
                      'runbarfill', 'prefers-reduced-motion'):
            self.assertIn(token, watch.PAGE)

    def test_run_mode_desc_is_contract_copy_and_wired(self):
        """#300 — shared description surface, one per mode, no marketing."""
        # every selectable + planned mode has a line
        for m in list(watch.RUN_MODES) + list(watch.RUN_MODES_PLANNED):
            self.assertIn(m, watch.RUN_MODE_DESC)
            self.assertTrue(watch.RUN_MODE_DESC[m].strip())
        # no extra keys invent a mode the file cannot hold
        for k in watch.RUN_MODE_DESC:
            self.assertIn(k, set(watch.RUN_MODES) | set(watch.RUN_MODES_PLANNED))
        # behavioural words from file-formats.md / SKILL.md, not slogans
        self.assertIn("no proactive fan-out",
                      watch.RUN_MODE_DESC["lackadaisical"])
        self.assertIn("coordinator only", watch.RUN_MODE_DESC["hot"])
        self.assertIn("helpers", watch.RUN_MODE_DESC["assisted"])
        self.assertIn("#264", watch.RUN_MODE_DESC["hierarchical"])
        self.assertIn("#288", watch.RUN_MODE_DESC["hierarchical"])
        # page embeds the table and the pure-presentation surface
        self.assertIn("const RUN_MODE_DESC = ", watch.PAGE)
        for token in ('id="rundesc"', 'id="rundesc-text"',
                      'function showRunDesc(', 'function hideRunDesc(',
                      'aria-describedby="rundesc-text"'):
            self.assertIn(token, watch.PAGE)
        # hover path must not call the arm/write path by name in showRunDesc
        # (structural: the function exists and pickRunMode is separate)
        self.assertIn('function pickRunMode(', watch.PAGE)
        idx = watch.PAGE.index('function showRunDesc(')
        end = watch.PAGE.index('function rundescPointerInside(', idx)
        body = watch.PAGE[idx:end]
        self.assertNotIn('pickRunMode(', body)
        self.assertNotIn("fetch('/run-mode'", body)
        self.assertNotIn('writeRunPending(', body)
        self.assertNotIn('commitRunMode(', body)

    def test_post_path_is_witnessed_like_other_writes(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            self.assertEqual(
                self._post(base + "/run-mode", {"mode": "assisted"}), 202)
            paths = [ln["path"] for ln in self._lines(d)]
            self.assertIn("/run-mode", paths)


class TestPosture(unittest.TestCase):
    """#445 increment 2 — three-axis posture controls on the dashboard.

    Closed sets imported from lint (never restated). Single shared 10s arm
    over a whole posture edit; one POST /posture; one events line only on a
    real change. Asking keeps four stops; delegation is a non-negative
    integer TARGET, not a cap.
    """

    def _serve(self, target):
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), watch.make_handler(target))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def _post(self, url, obj):
        req = urllib.request.Request(
            url, data=json.dumps(obj).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def _lines(self, d):
        path = os.path.join(d, ".dreamwork", "submissions.log")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(ln) for ln in f if ln.strip()]

    def test_vocabulary_is_imported_from_lint_not_restated(self):
        """Production line: watch.POSTURE_STOPS_* is lint's object (is, not ==).

        Restating the closed set as a fresh tuple would pass an equality
        check and re-open the #413 double-copy defect. Identity is the red.
        """
        import lint
        self.assertIs(watch.POSTURE_STOPS_PACE, lint.POSTURE_STOPS_PACE)
        self.assertIs(watch.POSTURE_STOPS_ASKING, lint.POSTURE_STOPS_ASKING)
        self.assertIs(watch.DELEGATION_POSTURES, lint.DELEGATION_POSTURES)
        self.assertIs(watch.derive_posture, lint.derive_posture)
        self.assertIs(watch.delegation_posture, lint.delegation_posture)
        # Asymmetry is load-bearing: asking has four, pace three.
        self.assertEqual(len(watch.POSTURE_STOPS_PACE), 3)
        self.assertEqual(len(watch.POSTURE_STOPS_ASKING), 4)
        self.assertEqual(set(watch.POSTURE_STOPS_ASKING),
                         {"ask", "inform", "near-auto", "auto"})

    def test_resolve_derives_when_absent_and_overlays_file(self):
        """Production lines: resolve_posture → derive_posture / read_posture_file."""
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".dreamwork"))
            r = watch.resolve_posture(d)
            self.assertEqual(r["source"], "derived")
            # Default run-mode is lackadaisical → idle/ask/0
            derived = watch.derive_posture(watch.RUN_MODE_DEFAULT)
            self.assertEqual(r["pace"], derived["pace"])
            self.assertEqual(r["asking"], derived["asking"])
            self.assertEqual(r["delegation"], derived["delegation"])
            self.assertEqual(r["delegation_label"],
                             watch.delegation_posture(r["delegation"]))
            self.assertTrue(watch.write_posture(d, "steady", "near-auto", 2))
            r2 = watch.resolve_posture(d)
            self.assertEqual(r2["source"], "file")
            self.assertEqual(r2["pace"], "steady")
            self.assertEqual(r2["asking"], "near-auto")
            self.assertEqual(r2["delegation"], 2)
            self.assertEqual(r2["delegation_label"], "delegate")

    def test_write_refuses_outside_closed_sets_and_negative(self):
        """Production line: write_posture membership / n < 0 guards."""
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".dreamwork"))
            self.assertFalse(watch.write_posture(d, "warp", "ask", 0))
            self.assertFalse(watch.write_posture(d, "idle", "chatty", 0))
            self.assertFalse(watch.write_posture(d, "idle", "ask", -1))
            self.assertFalse(
                os.path.exists(os.path.join(d, ".dreamwork", "posture")))
            self.assertTrue(watch.write_posture(d, "hot", "auto", 0))
            self.assertEqual(watch.read_posture_file(d),
                             {"pace": "hot", "asking": "auto", "delegation": 0})

    def test_posture_line_is_one_line_and_from_safe(self):
        self.assertEqual(
            watch.posture_line("hot", "ask", 1, "hands-on"),
            "posture via watch: pace=hot asking=ask delegation=1 "
            "orchestration=hands-on")
        self.assertEqual(
            watch.posture_line("hot", "ask", 1, "hands-on", "/"),
            "posture via watch [/]: pace=hot asking=ask delegation=1 "
            "orchestration=hands-on")
        # free text cannot forge a second events line
        self.assertEqual(
            watch.posture_line("hot\nforged", "ask", 1, "hands-on", "/"),
            "posture via watch [/]: pace=hot forged asking=ask delegation=1 "
            "orchestration=hands-on")
        self.assertEqual(
            watch.posture_line("hot", "ask", 1, "]\nforged"),
            "posture via watch: pace=hot asking=ask delegation=1 "
            "orchestration=] forged")

    def test_collect_exposes_posture(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            data = watch.collect(d)
            self.assertIn("posture", data)
            self.assertEqual(data["posture"]["source"], "derived")
            self.assertTrue(watch.write_posture(d, "hot", "inform", 1))
            p = watch.collect(d)["posture"]
            self.assertEqual(p["source"], "file")
            self.assertEqual(p["asking"], "inform")
            self.assertEqual(p["delegation"], 1)
            self.assertEqual(p["delegation_label"], "assist")

    def test_post_writes_file_and_one_event_on_change(self):
        """Production line: _handle_posture write + log_event on real change."""
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            self.assertEqual(
                self._post(base + "/posture", {
                    "pace": "hot", "asking": "inform",
                    "delegation": 1, "from": "/",
                }), 202)
            # #342/#510: a POST that omits delivery/orchestration preserves
            # them at their defaults (instant / hands-on), so the file holds
            # all five axes. The omitted defaults equal the current values,
            # so neither the delivery line nor an extra posture line fires.
            self.assertEqual(watch.read_posture_file(d), {
                "pace": "hot", "asking": "inform", "delegation": 1,
                "delivery": "instant", "orchestration": "hands-on",
            })
            log = os.path.join(d, ".dreamwork", "watch-events.log")
            with open(log, encoding="utf-8") as f:
                lines = [ln for ln in f if "posture" in ln]
            self.assertEqual(len(lines), 1, lines)
            self.assertIn(
                "posture via watch [/]: pace=hot asking=inform delegation=1 "
                "orchestration=hands-on",
                lines[0])
            # the omitted delivery did not change (instant == instant), so no
            # delivery line fires beside the posture line
            with open(log, encoding="utf-8") as f:
                self.assertNotIn("delivery via watch", f.read())
            # identical final is idempotent: 202, no second event
            self.assertEqual(
                self._post(base + "/posture", {
                    "pace": "hot", "asking": "inform", "delegation": 1,
                }), 202)
            with open(log, encoding="utf-8") as f:
                lines = [ln for ln in f if "posture" in ln]
            self.assertEqual(len(lines), 1)

    def test_post_rejects_unknown_pace_asking_and_negative(self):
        """Production line: domain_invalid branches in _handle_posture."""
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            self.assertEqual(
                self._post(base + "/posture", {
                    "pace": "warp", "asking": "ask", "delegation": 0,
                }), 202)
            self.assertEqual(
                self._post(base + "/posture", {
                    "pace": "idle", "asking": "chatty", "delegation": 0,
                }), 202)
            self.assertEqual(
                self._post(base + "/posture", {
                    "pace": "idle", "asking": "ask", "delegation": -3,
                }), 202)
            self.assertFalse(
                os.path.exists(os.path.join(d, ".dreamwork", "posture")))
            log = os.path.join(d, ".dreamwork", "watch-events.log")
            if os.path.exists(log):
                with open(log, encoding="utf-8") as f:
                    self.assertEqual(
                        [ln for ln in f if "posture" in ln], [])

    def test_asking_axis_accepts_all_four_stops(self):
        """Asymmetry: every asking stop is writable. Production: POSTURE_STOPS_ASKING."""
        # Precondition derived at runtime — if the set shrinks, this fails first.
        stops = list(watch.POSTURE_STOPS_ASKING)
        self.assertEqual(len(stops), 4, stops)
        self.assertIn("near-auto", stops)
        self.assertIn("auto", stops)
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            for stop in stops:
                self.assertEqual(
                    self._post(base + "/posture", {
                        "pace": "idle", "asking": stop, "delegation": 0,
                    }), 202, stop)
                self.assertEqual(
                    watch.read_posture_file(d)["asking"], stop, stop)

    def test_page_carries_vocabulary_wiring_and_arm(self):
        self.assertIn(
            "const POSTURE_STOPS_PACE = "
            + json.dumps(list(watch.POSTURE_STOPS_PACE)),
            watch.PAGE)
        self.assertIn(
            "const POSTURE_STOPS_ASKING = "
            + json.dumps(list(watch.POSTURE_STOPS_ASKING)),
            watch.PAGE)
        for token in (
            'function posturePicker(', 'function pickPostureAxis(',
            'function stepPostureDelegation(', "fetch('/posture'",
            'dw:posture-pending:', 'pbarfill', 'prefers-reduced-motion',
            'id="posture"', 'near-auto',
            'target, not a cap',
            'POSTURE_STOPS_ASKING.map',
            "pickPostureAxis('asking'",
            "pickPostureAxis('pace'",
        ):
            self.assertIn(token, watch.PAGE, token)
        # Asking axis is driven from the four-stop closed set (not a
        # hardcoded three-chip list). Production line: the .map over
        # POSTURE_STOPS_ASKING in posturePicker — compress to three by
        # slicing and this reds.
        idx = watch.PAGE.index('function posturePicker(')
        end = watch.PAGE.index('function showPostDesc(', idx) \
            if 'function showPostDesc(' in watch.PAGE[idx:] \
            else idx + 4000
        # showPostDesc is after posturePicker; bound the picker body.
        picker_end = watch.PAGE.find('/* Shared description for posture', idx)
        body = watch.PAGE[idx:picker_end if picker_end > idx else end]
        self.assertIn('POSTURE_STOPS_ASKING.map', body)
        self.assertIn('POSTURE_STOPS_PACE.map', body)
        # Must not compress asking: no .slice(0, 3) on the asking set.
        self.assertNotIn('POSTURE_STOPS_ASKING.slice', body)
        # Registered write route
        import inspect
        self.assertIn('"/posture": _handle_posture',
                      inspect.getsource(watch.make_handler))

    def test_post_path_is_witnessed_like_other_writes(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            self.assertEqual(
                self._post(base + "/posture", {
                    "pace": "hot", "asking": "ask", "delegation": 0,
                }), 202)
            paths = [ln["path"] for ln in self._lines(d)]
            self.assertIn("/posture", paths)

    def test_desc_tables_cover_every_stop_and_hover_does_not_write(self):
        """Contract copy present; showPostDesc never arms/POSTs."""
        for stop in watch.POSTURE_STOPS_PACE:
            self.assertIn(stop, watch.POSTURE_PACE_DESC)
            self.assertTrue(watch.POSTURE_PACE_DESC[stop].strip())
        for stop in watch.POSTURE_STOPS_ASKING:
            self.assertIn(stop, watch.POSTURE_ASKING_DESC)
            self.assertTrue(watch.POSTURE_ASKING_DESC[stop].strip())
        for lab in watch.DELEGATION_POSTURES:
            self.assertIn(lab, watch.POSTURE_DELEGATION_DESC)
        idx = watch.PAGE.index('function showPostDesc(')
        end = watch.PAGE.index('document.addEventListener(\'pointerover\'', idx)
        body = watch.PAGE[idx:end]
        self.assertNotIn('armPostureDraft(', body)
        self.assertNotIn("fetch('/posture'", body)
        self.assertNotIn('writePostPending(', body)
        self.assertNotIn('commitPosture(', body)

    def test_source_note_sits_beside_posture_heading(self):
        """#488: override/source chip lives next to the Posture heading.

        Production line: posturePicker builds `.posture-head` with the
        section label and `#posture-src` as siblings; `#posture-src` must
        NOT sit below the axes (old placement after `#pdesc`).
        """
        idx = watch.PAGE.index('function posturePicker(')
        end = watch.PAGE.find('/* Shared description for posture', idx)
        self.assertGreater(end, idx)
        body = watch.PAGE[idx:end]
        # Head row exists and carries both label + source note.
        self.assertIn('posture-head', body)
        head_i = body.index('posture-head')
        src_i = body.index('id="posture-src"')
        axes_i = body.index('posture-axes')
        self.assertLess(head_i, src_i, 'posture-src must be inside the head row')
        self.assertLess(src_i, axes_i,
                        'posture-src must sit with the heading, before the axes')
        # Old placement: source note after the description shell. Must not
        # reappear there — if it does, the chip is no longer "next to Posture".
        pdesc_i = body.index('id="pdesc"')
        # Only one posture-src id in the picker markup.
        self.assertEqual(body.count('id="posture-src"'), 1)
        self.assertLess(src_i, pdesc_i)

    def test_pdesc_reserves_layout_space_when_idle(self):
        """#488: hover description never reflows the card.

        Production lines:
          - CSS `.pdesc { min-height:… }` is permanent (not only under `.open`)
          - no `.pdesc[hidden] { display:none }` (display:none collapses space)
          - markup does not plant `hidden` on #pdesc (would collapse via UA)
        Visibility/opacity toggles; the box stays.
        """
        # Permanent min-height on the shell itself (not gated on .open).
        # Slice the posture CSS block so a later surface cannot satisfy this.
        css_i = watch.PAGE.index('.posture {')
        css_end = watch.PAGE.index('/* ── what he has sent', css_i)
        css = watch.PAGE[css_i:css_end]
        self.assertRegex(
            css, r'\.pdesc\s*\{[^}]*min-height\s*:\s*[1-9]',
            'pdesc must reserve min-height when idle, not only when open')
        # Collapse path that used to live here.
        self.assertNotIn('.pdesc[hidden]', css)
        self.assertNotRegex(css, r'\.pdesc\.open\s*\{[^}]*min-height')
        # Markup: the shell is always in flow (no hidden attribute).
        idx = watch.PAGE.index('function posturePicker(')
        end = watch.PAGE.find('/* Shared description for posture', idx)
        body = watch.PAGE[idx:end]
        # Match the pdesc open tag; it must not carry the HTML hidden
        # attribute (aria-hidden is fine — that is a11y, not layout).
        m = re.search(r'<div class="pdesc"[^>]*>', body)
        self.assertIsNotNone(m, 'pdesc shell missing from posturePicker')
        self.assertNotRegex(m.group(0), r'(?<!aria-)hidden')

    # ── #342 delivery posture axis ────────────────────────────────────────
    def test_delivery_vocabulary_is_imported_from_lint_not_restated(self):
        """Production line: watch.POSTURE_STOPS_DELIVERY is lint's object (is)."""
        import lint
        self.assertIs(watch.POSTURE_STOPS_DELIVERY, lint.POSTURE_STOPS_DELIVERY)
        self.assertEqual(set(watch.POSTURE_STOPS_DELIVERY),
                         {"instant", "batched"})

    def test_parse_posture_delivery_absent_is_instant(self):
        """Absent delivery → instant (today's behaviour); present batched parses.

        Production line: the `delivery` branch in parse_posture_text. Delete
        it and a batched file reads as {} (no delivery key), so resolve falls
        back to instant and the routing test below reds.
        """
        self.assertEqual(watch.parse_posture_text(""), {})
        self.assertEqual(
            watch.parse_posture_text("pace: hot\ndelegation: 0\ndevice: x"),
            {"pace": "hot", "delegation": 0})
        self.assertEqual(
            watch.parse_posture_text("delivery: batched"),
            {"delivery": "batched"})
        # garbage value is dropped here (lint ERRORs on hand-edits)
        self.assertEqual(
            watch.parse_posture_text("delivery: postal"),
            {})

    def test_resolve_posture_carries_delivery_default_and_override(self):
        """Production line: resolve_posture → read_posture_file / DELIVERY_DEFAULT."""
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".dreamwork"))
            r = watch.resolve_posture(d)
            self.assertEqual(r["delivery"], "instant")
            self.assertTrue(watch.write_posture(d, "hot", "ask", 0, "batched"))
            r2 = watch.resolve_posture(d)
            self.assertEqual(r2["delivery"], "batched")
            self.assertEqual(r2["source"], "file")

    def test_write_posture_delivery_is_optional_and_validated(self):
        """Production line: write_posture delivery membership guard."""
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".dreamwork"))
            # omitted → three-axis file (backward compatible)
            self.assertTrue(watch.write_posture(d, "hot", "ask", 0))
            self.assertNotIn("delivery", watch.read_posture_file(d))
            # provided → four-axis file
            self.assertTrue(watch.write_posture(d, "hot", "ask", 0, "batched"))
            self.assertEqual(watch.read_posture_file(d)["delivery"], "batched")
            # invalid delivery refused, file untouched at its last good state
            self.assertFalse(watch.write_posture(d, "hot", "ask", 0, "postal"))
            self.assertEqual(watch.read_posture_file(d)["delivery"], "batched")

    def test_delivery_line_is_one_line_and_from_safe(self):
        self.assertEqual(
            watch.delivery_line("batched"),
            "delivery via watch: batched")
        self.assertEqual(
            watch.delivery_line("instant", "/"),
            "delivery via watch [/]: instant")
        # free text cannot forge a second events line
        self.assertEqual(
            watch.delivery_line("batched\nforged", "/"),
            "delivery via watch [/]: batched forged")

    def test_post_delivery_dual_writes_file_and_one_event_on_change(self):
        """Production line: _handle_posture delivery branch + delivery_line.

        A real delivery change writes the file and emits exactly one delivery
        line; an identical re-POST is idempotent (no second line).
        """
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            # establish a file-backed posture (delivery defaults to instant)
            self.assertEqual(self._post(base + "/posture", {
                "pace": "idle", "asking": "ask", "delegation": 0,
            }), 202)
            log = os.path.join(d, ".dreamwork", "watch-events.log")
            # change ONLY delivery: the triple is unchanged, so no posture line
            self.assertEqual(self._post(base + "/posture", {
                "pace": "idle", "asking": "ask", "delegation": 0,
                "delivery": "batched", "from": "/",
            }), 202)
            self.assertEqual(
                watch.read_posture_file(d)["delivery"], "batched")
            with open(log, encoding="utf-8") as f:
                dlines = [ln for ln in f if "delivery via watch" in ln]
            self.assertEqual(len(dlines), 1, dlines)
            self.assertIn("delivery via watch [/]: batched", dlines[0])
            # no posture line fired for a delivery-only change
            with open(log, encoding="utf-8") as f:
                self.assertEqual(
                    [ln for ln in f if "posture via watch" in ln], [])
            # idempotent: same delivery, no second line
            self.assertEqual(self._post(base + "/posture", {
                "pace": "idle", "asking": "ask", "delegation": 0,
                "delivery": "batched",
            }), 202)
            with open(log, encoding="utf-8") as f:
                self.assertEqual(
                    [ln for ln in f if "delivery via watch" in ln].__len__(), 1)

    def test_post_delivery_preserved_when_omitted(self):
        """A triple-only POST must not silently reset delivery.

        Production line: the `if not delivery: delivery = current...` branch
        in _handle_posture. Without it, an omitted delivery defaults to
        instant and a batched file reverts — a pace change silently rewiring
        wake routing.
        """
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            self.assertEqual(self._post(base + "/posture", {
                "pace": "idle", "asking": "ask", "delegation": 0,
                "delivery": "batched",
            }), 202)
            # change pace WITHOUT mentioning delivery — batched must survive
            self.assertEqual(self._post(base + "/posture", {
                "pace": "hot", "asking": "ask", "delegation": 0,
            }), 202)
            pf = watch.read_posture_file(d)
            self.assertEqual(pf["pace"], "hot")
            self.assertEqual(pf["delivery"], "batched")

    def test_post_delivery_rejects_unknown(self):
        """Production line: the delivery closed-set guard in _handle_posture."""
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            self.assertEqual(self._post(base + "/posture", {
                "pace": "idle", "asking": "ask", "delegation": 0,
                "delivery": "postal",
            }), 202)  # E5: durable rejected, not a sync 400
            self.assertFalse(
                os.path.exists(os.path.join(d, ".dreamwork", "posture")))

    def test_collect_and_summary_expose_delivery(self):
        """Production line: resolve_posture delivery + _summary_posture."""
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            self.assertEqual(watch.collect(d)["posture"]["delivery"], "instant")
            self.assertTrue(watch.write_posture(d, "hot", "ask", 0, "batched"))
            self.assertEqual(
                watch.collect(d)["posture"]["delivery"], "batched")

    # ── #342 surface 3: the delivery dashboard chip ──────────────────────
    def test_page_carries_delivery_vocabulary(self):
        """The closed set is injected from lint (single source), not restated."""
        self.assertIn(
            "const POSTURE_STOPS_DELIVERY = "
            + json.dumps(list(watch.POSTURE_STOPS_DELIVERY)),
            watch.PAGE)

    def test_delivery_chip_reuses_the_posture_picker_idiom(self):
        """The delivery chip is a fourth axis row in the posture picker,
        reusing the EXACT pace/asking idiom (same class, same picker fn, the
        shared 10s arm) — authoring a second gesture is the failure
        transitions.md / CLAUDE.md name. Asserted in source (browser guards
        are the coordinator's merge-gate, not this lane's).

        Production line: posturePicker builds a delivery .paxis row whose
        chips come from POSTURE_STOPS_DELIVERY.map and fire pickPostureAxis.
        """
        # the chip row lives inside posturePicker, beside the other axes
        idx = watch.PAGE.index('function posturePicker(')
        end = watch.PAGE.find('/* Shared description for posture', idx)
        self.assertGreater(end, idx)
        body = watch.PAGE[idx:end]
        self.assertIn('data-axis="delivery"', body)
        self.assertIn('delivery-lab', body)
        # driven from the closed set (not a hardcoded two-chip list)
        self.assertIn('POSTURE_STOPS_DELIVERY.map', body)
        self.assertIn("pickPostureAxis('delivery'", body)
        # same chip class as pace/asking — no second gesture
        self.assertIn("class=\"sgbtn pchip", body)
        # no second arm: delivery routes through the shared posture arm, not
        # its own. A second arm would be a second ceremony.
        self.assertNotIn('armDelivery', watch.PAGE)
        self.assertNotIn('commitDelivery', watch.PAGE)

    def test_delivery_posts_through_the_shared_arm_and_posture_route(self):
        """Production lines: commitPosture carries delivery in the POST body
        and through the shared 10s arm (RUN_ARM_MS, one /posture route).

        Scoped to the JSON.stringify POST body — a bare or function-wide
        'delivery: draft.delivery' assertion is hollow (the optimistic
        data.posture update and the pending cache carry it too), so the check
        is sliced to the bytes the POST actually sends. A dropped field reds
        here; the two other copies do not satisfy it.
        """
        # Slice the JSON.stringify({...}) the /posture fetch sends, not the
        # whole fn (and not the tint POST, whose body:stringify comes first).
        fi = watch.PAGE.index("fetch('/posture'")
        si = watch.PAGE.index("body: JSON.stringify({", fi)
        se = watch.PAGE.index("}),", si)
        post_body = watch.PAGE[si:se]
        self.assertIn('pace: draft.pace', post_body)
        self.assertIn('delivery: draft.delivery', post_body)
        # committedPosture carries delivery so the chip paints its selection
        cp_i = watch.PAGE.index('function committedPosture(')
        cp_end = watch.PAGE.index('function delegationLabel(', cp_i)
        self.assertIn('POSTURE_STOPS_DELIVERY', watch.PAGE[cp_i:cp_end])
        # no second arm: delivery routes through the shared posture arm
        self.assertNotIn('armDelivery', watch.PAGE)

    def test_delivery_desc_table_covers_both_stops(self):
        """Contract copy present for both stops (hover descriptions)."""
        for stop in watch.POSTURE_STOPS_DELIVERY:
            self.assertIn(stop, watch.POSTURE_DELIVERY_DESC)
            self.assertTrue(watch.POSTURE_DELIVERY_DESC[stop].strip())
        self.assertIn('POSTURE_DELIVERY_DESC', watch.PAGE)
        # postDescFor serves the delivery axis
        pdf_i = watch.PAGE.index('function postDescFor(')
        pdf_end = watch.PAGE.index('function hidePostDesc(', pdf_i)
        self.assertIn("axis === 'delivery'", watch.PAGE[pdf_i:pdf_end])

    # ── #510 orchestration posture axis ────────────────────────────────
    def test_orchestration_vocabulary_is_imported_from_lint_not_restated(self):
        """Production line: watch.POSTURE_STOPS_ORCHESTRATION is lint's object."""
        import lint
        self.assertIs(watch.POSTURE_STOPS_ORCHESTRATION,
                      lint.POSTURE_STOPS_ORCHESTRATION)
        self.assertEqual(set(watch.POSTURE_STOPS_ORCHESTRATION),
                         {"hands-on", "orchestrator"})

    def test_parse_posture_orchestration_absent_is_hands_on(self):
        """Absent orchestration → hands-on (today); present orchestrator parses.

        Production line: the `orchestration` branch in parse_posture_text.
        Delete it and an orchestrator file reads as {} (no orchestration key),
        so resolve falls back to hands-on.
        """
        self.assertEqual(
            watch.parse_posture_text("orchestration: orchestrator"),
            {"orchestration": "orchestrator"})
        # garbage value is dropped here (lint ERRORs on hand-edits)
        self.assertEqual(
            watch.parse_posture_text("orchestration: turbo"),
            {})

    def test_resolve_posture_carries_orchestration_default_and_override(self):
        """Production line: resolve_posture → read_posture_file / ORCHESTRATION_DEFAULT."""
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".dreamwork"))
            r = watch.resolve_posture(d)
            self.assertEqual(r["orchestration"], "hands-on")
            self.assertTrue(
                watch.write_posture(d, "hot", "ask", 0, None, "orchestrator"))
            r2 = watch.resolve_posture(d)
            self.assertEqual(r2["orchestration"], "orchestrator")
            self.assertEqual(r2["source"], "file")

    def test_write_posture_orchestration_is_optional_and_validated(self):
        """Production line: write_posture orchestration membership guard."""
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".dreamwork"))
            # omitted → no orchestration line (backward compatible)
            self.assertTrue(watch.write_posture(d, "hot", "ask", 0))
            self.assertNotIn("orchestration", watch.read_posture_file(d))
            # provided → orchestration line lands
            self.assertTrue(
                watch.write_posture(d, "hot", "ask", 0, None, "orchestrator"))
            self.assertEqual(
                watch.read_posture_file(d)["orchestration"], "orchestrator")
            # invalid orchestration refused, file untouched at last good state
            self.assertFalse(
                watch.write_posture(d, "hot", "ask", 0, None, "turbo"))
            self.assertEqual(
                watch.read_posture_file(d)["orchestration"], "orchestrator")

    def test_posture_line_carries_orchestration(self):
        """Production line: posture_line emits an orchestration= field.

        Orchestration rides the `posture via watch` line (it has no separate
        consumer line the way delivery does); a dropped field reds here.
        """
        self.assertIn(
            "orchestration=orchestrator",
            watch.posture_line("hot", "ask", 0, "orchestrator"))
        # free text cannot forge a second events line
        self.assertEqual(
            watch.posture_line("hot", "ask", 0, "hands-on\nforged", "/"),
            "posture via watch [/]: pace=hot asking=ask delegation=0 "
            "orchestration=hands-on forged")

    def test_post_orchestration_dual_writes_file_and_one_event_on_change(self):
        """Production line: _handle_posture orchestration branch + posture_line.

        A real orchestration change writes the file and emits exactly one
        posture line (orchestration rides the posture line, not its own); an
        identical re-POST is idempotent (no second line).
        """
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            # establish a file-backed posture (orchestration defaults to
            # hands-on, so the file holds pace/asking/delegation only).
            self.assertEqual(self._post(base + "/posture", {
                "pace": "idle", "asking": "ask", "delegation": 0,
            }), 202)
            log = os.path.join(d, ".dreamwork", "watch-events.log")
            # change ONLY orchestration: the triple is unchanged, so the
            # posture line fires carrying the new orchestration value.
            self.assertEqual(self._post(base + "/posture", {
                "pace": "idle", "asking": "ask", "delegation": 0,
                "orchestration": "orchestrator", "from": "/",
            }), 202)
            self.assertEqual(
                watch.read_posture_file(d)["orchestration"], "orchestrator")
            with open(log, encoding="utf-8") as f:
                plines = [ln for ln in f if "posture via watch" in ln]
            self.assertEqual(len(plines), 1, plines)
            self.assertIn("orchestration=orchestrator", plines[0])
            # no delivery line fired for an orchestration-only change
            with open(log, encoding="utf-8") as f:
                self.assertEqual(
                    [ln for ln in f if "delivery via watch" in ln], [])
            # idempotent: same orchestration, no second posture line
            self.assertEqual(self._post(base + "/posture", {
                "pace": "idle", "asking": "ask", "delegation": 0,
                "orchestration": "orchestrator",
            }), 202)
            with open(log, encoding="utf-8") as f:
                self.assertEqual(
                    [ln for ln in f if "posture via watch" in ln].__len__(), 1)

    def test_post_orchestration_preserved_when_omitted(self):
        """A triple-only POST must not silently reset orchestration.

        Production line: the `if not orchestration: orchestration = current`
        branch in _handle_posture. Without it, an omitted orchestration
        defaults to hands-on and an orchestrator file reverts.
        """
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            self.assertEqual(self._post(base + "/posture", {
                "pace": "idle", "asking": "ask", "delegation": 0,
                "orchestration": "orchestrator",
            }), 202)
            # change pace WITHOUT mentioning orchestration — must survive
            self.assertEqual(self._post(base + "/posture", {
                "pace": "hot", "asking": "ask", "delegation": 0,
            }), 202)
            pf = watch.read_posture_file(d)
            self.assertEqual(pf["pace"], "hot")
            self.assertEqual(pf["orchestration"], "orchestrator")

    def test_post_orchestration_rejects_unknown(self):
        """Production line: the orchestration closed-set guard in _handle_posture."""
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            self.assertEqual(self._post(base + "/posture", {
                "pace": "idle", "asking": "ask", "delegation": 0,
                "orchestration": "turbo",
            }), 202)  # durable rejected, not a sync 400
            self.assertFalse(
                os.path.exists(os.path.join(d, ".dreamwork", "posture")))

    def test_collect_and_summary_expose_orchestration(self):
        """Production lines: resolve_posture orchestration (collect path) +
        _summary_posture projection (summary path). Both must carry it —
        collect reads resolve_posture, summary projects via _summary_posture,
        and a field dropped from the projection alone leaves collect whole."""
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            # collect path (resolve_posture)
            self.assertEqual(
                watch.collect(d)["posture"]["orchestration"], "hands-on")
            # summary path (_summary_posture projection)
            self.assertEqual(
                watch.summary(d)["posture"]["orchestration"], "hands-on")
            self.assertTrue(
                watch.write_posture(d, "hot", "ask", 0, None, "orchestrator"))
            self.assertEqual(
                watch.collect(d)["posture"]["orchestration"], "orchestrator")
            self.assertEqual(
                watch.summary(d)["posture"]["orchestration"], "orchestrator")

    # ── #510 surface 3: the orchestration dashboard chip ──────────────
    def test_page_carries_orchestration_vocabulary(self):
        """The closed set is injected from lint (single source), not restated."""
        self.assertIn(
            "const POSTURE_STOPS_ORCHESTRATION = "
            + json.dumps(list(watch.POSTURE_STOPS_ORCHESTRATION)),
            watch.PAGE)

    def test_orchestration_chip_reuses_the_posture_picker_idiom(self):
        """The orchestration chip is a fifth axis row in the posture picker,
        reusing the EXACT pace/asking/delivery idiom (same class, same picker
        fn, the shared 10s arm) — authoring a second gesture is the failure
        transitions.md / CLAUDE.md name.

        Production line: posturePicker builds an orchestration .paxis row
        whose chips come from POSTURE_STOPS_ORCHESTRATION.map and fire
        pickPostureAxis.
        """
        idx = watch.PAGE.index('function posturePicker(')
        end = watch.PAGE.find('/* Shared description for posture', idx)
        self.assertGreater(end, idx)
        body = watch.PAGE[idx:end]
        self.assertIn('data-axis="orchestration"', body)
        self.assertIn('orchestration-lab', body)
        # driven from the closed set (not a hardcoded two-chip list)
        self.assertIn('POSTURE_STOPS_ORCHESTRATION.map', body)
        self.assertIn("pickPostureAxis('orchestration'", body)
        # same chip class as pace/asking/delivery — no second gesture
        self.assertIn("class=\"sgbtn pchip", body)
        # no second arm: orchestration routes through the shared posture arm
        self.assertNotIn('armOrchestration', watch.PAGE)
        self.assertNotIn('commitOrchestration', watch.PAGE)

    def test_orchestration_posts_through_the_shared_arm_and_posture_route(self):
        """Production lines: commitPosture carries orchestration in the POST body
        and through the shared 10s arm (RUN_ARM_MS, one /posture route).

        Scoped to the JSON.stringify POST body — a bare 'orchestration:' is
        hollow (the optimistic update and the pending cache carry it too), so
        the check is sliced to the bytes the POST actually sends.
        """
        fi = watch.PAGE.index("fetch('/posture'")
        si = watch.PAGE.index("body: JSON.stringify({", fi)
        se = watch.PAGE.index("}),", si)
        post_body = watch.PAGE[si:se]
        self.assertIn('pace: draft.pace', post_body)
        self.assertIn('orchestration: draft.orchestration', post_body)
        # committedPosture carries orchestration so the chip paints selection
        cp_i = watch.PAGE.index('function committedPosture(')
        cp_end = watch.PAGE.index('function delegationLabel(', cp_i)
        self.assertIn('POSTURE_STOPS_ORCHESTRATION', watch.PAGE[cp_i:cp_end])
        # no second arm
        self.assertNotIn('armOrchestration', watch.PAGE)

    def test_orchestration_desc_table_covers_both_stops(self):
        """Contract copy present for both stops (hover descriptions)."""
        for stop in watch.POSTURE_STOPS_ORCHESTRATION:
            self.assertIn(stop, watch.POSTURE_ORCHESTRATION_DESC)
            self.assertTrue(watch.POSTURE_ORCHESTRATION_DESC[stop].strip())
        self.assertIn('POSTURE_ORCHESTRATION_DESC', watch.PAGE)
        pdf_i = watch.PAGE.index('function postDescFor(')
        pdf_end = watch.PAGE.index('function hidePostDesc(', pdf_i)
        self.assertIn("axis === 'orchestration'", watch.PAGE[pdf_i:pdf_end])


class TestDeliveryWakeRouting(unittest.TestCase):
    """#342 lane B surface 2 — per-kind wake routing.

    The receipt commits UNCONDITIONALLY in do_POST (E3); the watch-events.log
    wake line's emission is conditional on (kind, mode). do-now/do-next
    pre-empt even in batched mode; every other kind and the /answer, /comment,
    /ask routes wake only in instant mode. Withholding the wake line IS
    batching — the item rides the durable receipt and the tick's cursor read.
    """

    def _serve(self, target):
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), watch.make_handler(target))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def _post(self, url, obj):
        req = urllib.request.Request(
            url, data=json.dumps(obj).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def _post_body(self, url, obj):
        req = urllib.request.Request(
            url, data=json.dumps(obj).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def _wake_lines(self, d):
        """Every watch-events.log line — each is a wake line the tail monitor
        wakes on. NOT filtered to 'via watch', because the /answer, /comment
        and /ask wake lines carry no such marker; filtering to it would hide
        them and make a withheld-line check pass trivially (the hollow trap)."""
        log = os.path.join(d, ".dreamwork", "watch-events.log")
        if not os.path.exists(log):
            return []
        with open(log, encoding="utf-8") as f:
            return [ln for ln in f if ln.strip()]

    def _witnessed(self, d):
        """submissions.log paths — present iff the route ran end-to-end through
        do_POST (the witness runs after the durable receipt, so its presence
        proves the receipt committed)."""
        path = os.path.join(d, ".dreamwork", "submissions.log")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(ln)["path"] for ln in f if ln.strip()]

    def test_emits_wake_matrix_pure(self):
        """Production line: emits_wake — the routing decision table.

        PRECONDITION asserted at runtime (the hollow-check rule): the core
        command kinds are exactly the five in COMMANDS (incl. #504 chat), so
        a kind added later is covered by the 'not a pre-empt kind' branch
        instead of slipping past a hand-copied list.
        """
        core = set(watch.COMMAND_KINDS)
        self.assertEqual(core,
                         {"chat", "add-idea", "do-next", "do-now",
                          "maintenance"}, core)
        # #504 PRECONDITION: chat is the far-left default and NOT a pre-empt
        # kind (it is batched under #342 — Q3). Asserted here so a future
        # edit that makes chat pre-empt reds this matrix, not just the chat
        # test that depends on it.
        self.assertEqual(watch.COMMANDS[0]["kind"], "chat")
        self.assertNotIn("chat", watch.PREEMPT_KINDS)
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".dreamwork"))
            instant = d
            batched = os.path.join(d, "b")
            os.makedirs(os.path.join(batched, ".dreamwork"))
            self.assertTrue(
                watch.write_posture(batched, "idle", "ask", 0, "batched"))
            # pre-empt kinds wake in BOTH modes
            for kind in watch.PREEMPT_KINDS:
                self.assertTrue(watch.emits_wake(kind, instant), kind)
                self.assertTrue(watch.emits_wake(kind, batched), kind)
            self.assertEqual(set(watch.PREEMPT_KINDS), {"do-now", "do-next"})
            # every other kind + plugin kinds + the routes wake only instant.
            # #504: chat is in this batched family (Q3) — it withholds in
            # batched, same as add-idea/maintenance and the /ask route.
            for kind in ("chat", "add-idea", "maintenance", "some-plugin"):
                self.assertTrue(watch.emits_wake(kind, instant), kind)
                self.assertFalse(watch.emits_wake(kind, batched), kind)
            for route in ("/answer", "/comment", "/ask"):
                self.assertTrue(watch.emits_wake(route, instant), route)
                self.assertFalse(watch.emits_wake(route, batched), route)

    def test_command_preempt_kinds_wake_in_batched(self):
        """Live: do-now/do-next wake even in batched mode; receipt always lands.

        Production line: the `if emits_wake(kind, target):` gate in
        _handle_command. Remove it and add-idea wakes in batched too (next
        test); make emits_wake always-False and do-now stops waking here.
        """
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            self.assertTrue(
                watch.write_posture(d, "idle", "ask", 0, "batched"))
            base = self._serve(d)
            for kind in ("do-now", "do-next"):
                payload = {"kind": kind, "text": "preempt " + kind} \
                    if kind != "do-next" else {"kind": "do-next", "text": ""}
                self.assertEqual(self._post(base + "/command", payload), 202)
            wakes = self._wake_lines(d)
            self.assertTrue(any("do-now" in w for w in wakes), wakes)
            self.assertTrue(any("do-next" in w for w in wakes), wakes)
            # the receipt committed for both (E3 — unconditional)
            self.assertEqual(self._witnessed(d).count("/command"), 2)

    def test_command_batched_kinds_withhold_wake_in_batched(self):
        """Live: chat/add-idea/maintenance withhold the wake line in batched mode.

        Production line: the `if emits_wake(kind, target):` gate. The receipt
        still commits — withholding the wake IS batching; the cursor drains it.
        #504 adds `chat` to this batched family (Q3): a topic chat rides the
        tick's cursor read rather than pre-empting, exactly his "get unread at
        the start of a loop iteration".
        """
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            self.assertTrue(
                watch.write_posture(d, "idle", "ask", 0, "batched"))
            base = self._serve(d)
            self.assertEqual(self._post(base + "/command",
                                        {"kind": "chat", "text": "hi agent"}), 202)
            self.assertEqual(self._post(base + "/command",
                                        {"kind": "add-idea", "text": "parked"}), 202)
            self.assertEqual(self._post(base + "/command",
                                        {"kind": "maintenance", "text": "groom"}), 202)
            wakes = self._wake_lines(d)
            self.assertFalse(any("chat" in w for w in wakes), wakes)
            self.assertFalse(any("add-idea" in w for w in wakes), wakes)
            self.assertFalse(any("maintenance" in w for w in wakes), wakes)
            # the receipt committed for all three even though no wake fired
            self.assertEqual(self._witnessed(d).count("/command"), 3)

    def test_command_all_kinds_wake_in_instant(self):
        """Live: in instant mode (the default) every command kind wakes.

        Production line: emits_wake returns True in instant mode for non-
        pre-empt kinds (delivery_mode == DELIVERY_DEFAULT). A posture file
        with no delivery axis — or absent — is instant.
        """
        with tempfile.TemporaryDirectory() as d:
            make_target(d)  # no posture file → instant
            base = self._serve(d)
            self.assertEqual(self._post(base + "/command",
                                        {"kind": "add-idea", "text": "now"}), 202)
            self.assertEqual(self._post(base + "/command",
                                        {"kind": "do-now", "text": "now"}), 202)
            wakes = self._wake_lines(d)
            self.assertTrue(any("add-idea" in w for w in wakes), wakes)
            self.assertTrue(any("do-now" in w for w in wakes), wakes)

    def test_answer_ask_comment_withhold_wake_in_batched(self):
        """Live: /answer, /comment, /ask withhold the wake line in batched.

        Production line: the `if emits_wake(<route>, target):` gate in each of
        the three handlers. The receipt commits in every case (E3).
        """
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            self.assertTrue(
                watch.write_posture(d, "idle", "ask", 0, "batched"))
            base = self._serve(d)
            self.assertEqual(self._post(base + "/answer", {
                "question": "A real open question?", "answer": "yes"}), 202)
            self.assertEqual(self._post(base + "/comment", {
                "question": "A real open question?", "comment": "a note",
                "section": "Open"}), 202)
            self.assertEqual(self._post(base + "/ask", {
                "question": "a new question"}), 202)
            wakes = self._wake_lines(d)
            # /answer's wake line is 'answer: "..." -> .dreamwork/questions.md
            # (fold the answer...)' — distinct markers, no 'via watch'.
            self.assertFalse(any("fold the answer" in w for w in wakes), wakes)
            self.assertFalse(any("follow-up" in w for w in wakes), wakes)
            self.assertFalse(any("question for dreamer" in w for w in wakes),
                             wakes)
            # all three receipts committed despite no wake
            witnessed = self._witnessed(d)
            for route in ("/answer", "/comment", "/ask"):
                self.assertIn(route, witnessed)

    def test_answer_ask_comment_wake_in_instant(self):
        """Live: in instant mode the three routes wake (today's behaviour)."""
        with tempfile.TemporaryDirectory() as d:
            make_target(d)  # instant
            base = self._serve(d)
            self.assertEqual(self._post(base + "/answer", {
                "question": "A real open question?", "answer": "yes"}), 202)
            self.assertEqual(self._post(base + "/ask", {
                "question": "a new one"}), 202)
            wakes = self._wake_lines(d)
            self.assertTrue(any("fold the answer" in w for w in wakes), wakes)
            self.assertTrue(any("question for dreamer" in w for w in wakes),
                            wakes)

    def test_decide_withholds_wake_in_batched(self):
        """Live: /decide withholds the wake line in batched mode (#515, F1).

        Production line: the `if emits_wake("/decide", target):` gate around
        the review-decision log_event in _handle_decide. Remove it and the
        line fires in batched too, silently undoing the toggle for review
        decisions — the same family as /answer and /comment. The receipt
        still commits and the decision still lands in the store: withholding
        the wake IS batching; the cursor drains it.
        """
        with tempfile.TemporaryDirectory() as d:
            _store_target(d)  # store-mode, else /decide refuses (no_store)
            dw = os.path.join(d, ".dreamwork")
            # PRECONDITION (the hollow-check rule): the posture file really
            # carries the batched axis, or delivery_mode reads instant and a
            # withhold assertion is unmeaningful.
            self.assertTrue(
                watch.write_posture(d, "idle", "ask", 0, "batched"))
            self.assertEqual(watch.read_posture_file(d)["delivery"], "batched")
            # PRECONDITION: genuinely store-mode, or /decide refuses and never
            # reaches the wake line — a refusal writes no line either.
            self.assertEqual(watch.source_of_truth(dw), "store")
            base = self._serve(d)
            status = self._post(base + "/decide", {
                "artifact": "plan.html", "question_title": "ship it?",
                "decision": "accepted"})
            # PRECONDITION: the route ran end-to-end (202, not a 500), or a
            # withheld-line check is vacuous.
            self.assertEqual(status, 202)
            # the decision really landed in the store — the route did its job
            self.assertEqual(
                watch._review_decisions(dw)["plan.html"],
                ("accepted", "ship it?"))
            # the receipt committed (E3 — unconditional) despite no wake
            self.assertIn("/decide", self._witnessed(d))
            # F1: NO review-decision wake line in batched mode
            wakes = self._wake_lines(d)
            self.assertFalse(any("review-decision" in w for w in wakes), wakes)

    def test_decide_wakes_in_instant_and_default(self):
        """Live: in instant mode (and absent delivery axis — the default) a
        /decide writes exactly one review-decision wake line (#515, F1).

        Production line: the review-decision log_event emission inside the
        emits_wake gate in _handle_decide. Remove the emission and no line
        fires in any mode — this is the regression guard against over-gating
        (a /decide that never wakes).
        """
        for delivery in ("instant", None):  # None == absent axis => default
            with tempfile.TemporaryDirectory() as d:
                _store_target(d)
                dw = os.path.join(d, ".dreamwork")
                if delivery is not None:
                    self.assertTrue(
                        watch.write_posture(d, "idle", "ask", 0, delivery))
                    # PRECONDITION: the file carries the axis written.
                    self.assertEqual(
                        watch.read_posture_file(d)["delivery"], delivery)
                else:
                    # PRECONDITION: no posture file => absent axis => instant
                    self.assertNotIn("delivery", watch.read_posture_file(d))
                self.assertEqual(watch.source_of_truth(dw), "store")
                base = self._serve(d)
                status = self._post(base + "/decide", {
                    "artifact": "plan.html", "question_title": "ship it?",
                    "decision": "accepted"})
                self.assertEqual(status, 202)
                # exactly one review-decision wake line (today's behaviour)
                wakes = [w for w in self._wake_lines(d)
                         if "review-decision" in w]
                self.assertEqual(len(wakes), 1, (delivery, wakes))
                self.assertIn("plan.html", wakes[0])
                self.assertIn("accepted", wakes[0])

    # ── #504 composer `chat` (main-dreamer first slice of #229/#270) ──────
    # A chat send is a /command POST of kind `chat` (Q1: no new route) that
    # rides the #263 receipt and is BATCHED under #342 (Q3). The application
    # step writes a human turn to a chats-v1 transcript; the receipt is the
    # durable home. These bind: the COMMANDS entry, the batched wake gate, the
    # application step, and the reply→replied thread model.

    def test_chat_command_entry_is_far_left_default(self):
        """Production line: the `chat` dict in COMMANDS (watch.py:~315).

        Q1/Q2: chat is the far-left default composer kind, common (a row
        button), and sticky (conversational — a follow-up must not require
        re-selection). The UI label is "topic chat" (Q2); implementation vocab
        is chat/turn/reply, never `thread` (#229) — asserted so a renamed
        label does not silently drift from his ruling.
        """
        chat = watch.COMMANDS[0]
        self.assertEqual(chat["kind"], "chat")
        self.assertEqual(chat["label"], "topic chat")
        self.assertTrue(chat["common"], chat)
        self.assertTrue(chat["sticky"], chat)
        # every core kind the server accepts is in the validated vocab
        self.assertIn("chat", watch.COMMAND_KINDS)
        # add-idea stays sticky (parked thoughts still chain); chat is the
        # SECOND sticky kind — asserted so the sticky comment stays honest.
        sticky = [c["kind"] for c in watch.COMMANDS if c.get("sticky")]
        self.assertEqual(set(sticky), {"chat", "add-idea"}, sticky)

    def test_chat_withholds_wake_in_batched(self):
        """Live: a `chat` send withholds the wake line under delivery: batched.

        Mirrors test_decide_withholds_wake_in_batched. Production line: the
        `if emits_wake(kind, target):` gate in _handle_command — chat is not a
        pre-empt kind, so in batched mode the wake line is withheld (Q3) and
        the chat rides the tick's cursor read. The receipt still commits (E3)
        and the application step still writes the transcript: withholding the
        wake IS batching, not dropping the message.
        """
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            # PRECONDITION (hollow-check): the posture file really carries the
            # batched axis, or delivery_mode reads instant and a withhold
            # assertion is unmeaningful.
            self.assertTrue(
                watch.write_posture(d, "idle", "ask", 0, "batched"))
            self.assertEqual(watch.read_posture_file(d)["delivery"], "batched")
            base = self._serve(d)
            status, body = self._post_body(base + "/command",
                                           {"kind": "chat", "text": "hello"})
            # PRECONDITION: the route ran end-to-end (202), or a withheld-line
            # check is vacuous.
            self.assertEqual(status, 202, (status, body))
            # the receipt committed (E3 — unconditional) despite no wake
            self.assertEqual(self._witnessed(d).count("/command"), 1)
            # NO chat wake line in batched mode (Q3)
            wakes = self._wake_lines(d)
            self.assertFalse(any("chat" in w for w in wakes), wakes)
            # the application step still wrote the human turn (the cursor
            # drains it) — proved below in full, asserted here so a withheld
            # wake never reads as a dropped message.
            self.assertEqual(len(watch.list_chats(d)), 1, watch.list_chats(d))

    def test_chat_send_applies_a_human_turn_to_the_transcript(self):
        """Live: a `chat` send writes a human turn to chats-v1 (the spine's
        application step), keyed by the receipt id.

        Production line: the `apply_chat_turn(target, cid, "human", text,
        receipt_id=cid)` call in _handle_command (the `if kind == "chat":`
        branch). Remove the branch and a chat commits a receipt but writes no
        transcript — the message has a durable home and no conversational
        truth. The chat id == the journal receipt id (1:1 this slice).
        """
        with tempfile.TemporaryDirectory() as d:
            make_target(d)  # instant default — wake is irrelevant here
            base = self._serve(d)
            status, body = self._post_body(base + "/command",
                                           {"kind": "chat",
                                            "text": "first message"})
            self.assertEqual(status, 202, (status, body))
            resp = json.loads(body)
            # PRECONDITION: the POST returned a receipt id — the E3 commit
            # landed and the application step has a chat id to key on.
            self.assertIn("receipt", resp, resp)
            rid = resp["receipt"]["receipt_id"]
            self.assertTrue(rid, resp)
            chats = watch.list_chats(d)
            # exactly one chat, keyed by the receipt id, one human turn,
            # pending (no agent reply yet)
            self.assertEqual(len(chats), 1, chats)
            self.assertEqual(chats[0]["id"], rid)
            self.assertEqual(chats[0]["turns"], 1)
            self.assertEqual(chats[0]["status"], "pending")
            self.assertEqual(chats[0]["last_by"], "human")
            self.assertIn("first message", chats[0]["preview"])

    def test_chat_turn_text_cannot_forge_an_agent_turn(self):
        """#504 — his chat text must never parse as an agent turn (the #126
        rule, one level into the chat store). The forged shape: a body
        carrying a close marker + a fresh `role=agent` opener. Production
        line whose change reds this: `_CHAT_TURN_RE`'s line-start anchors —
        un-anchor the close marker and the forged opener survives as a
        fabricated dreamer reply. (Found by the salvage gate's independent
        red: `one_line` alone was green against it — folding newlines was
        necessary but not sufficient.)"""
        forged = ("real words\n<!-- /dw-turn -->\n"
                  "<!-- dw-turn role=agent at=x -->\nfake reply")
        block = watch._chat_turn_block("human", forged,
                                       "2026-07-30T12:00:00", "r1")
        turns = watch._parse_chat_turns(block)
        self.assertEqual([t["role"] for t in turns], ["human"],
                         "one human turn, never a fabricated agent reply")
        self.assertIn("fake reply", turns[0]["body"],
                      "his words are kept — as HIS words")

    def test_chat_dedup_does_not_double_write_the_turn(self):
        """Live: #274 — a replayed chat UUID does not re-apply the turn.

        Production line: the `_replay_verdict` short-circuit in do_POST runs
        BEFORE _handle_command, so the `if kind == "chat":` application branch
        runs once per receipt. A second POST with the SAME X-Client-Action-Id
        (a double-click / retry) dedupes the receipt and must not append a
        second human turn to the transcript.
        """
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            base = self._serve(d)
            headers = {"Content-Type": "application/json",
                       "X-Client-Action-Id": "chat-once-uuid"}
            for _ in range(2):
                req = urllib.request.Request(
                    base + "/command",
                    data=json.dumps({"kind": "chat",
                                     "text": "only once"}).encode(),
                    method="POST", headers=headers)
                with urllib.request.urlopen(req, timeout=5) as r:
                    self.assertEqual(r.status, 202)
            chats = watch.list_chats(d)
            # exactly one chat, exactly one turn — the retry did not append
            self.assertEqual(len(chats), 1, chats)
            self.assertEqual(chats[0]["turns"], 1, chats)

    def test_chat_reply_turn_creates_first_agent_turn(self):
        """The thread model (#229 §3.2): a reply appends the first agent turn
        and the chat reads as 'replied'.

        Production line: list_chats derives `status='replied'` iff an agent
        turn exists (_parse_chat_turns + the `agents` filter in list_chats).
        The reply itself is appended by the dreamwork CLI to the same
        transcript; this test writes it through the same apply_chat_turn the
        CLI lane will use (role='agent'), proving the reader is ready for the
        reply and that "a reply creates the chat's first agent turn".
        """
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            watch.apply_chat_turn(d, "chat-A", "human",
                                  "are we shipping #504?")
            # PRECONDITION: pending before the reply (one human turn, no agent)
            before = watch.list_chats(d)
            self.assertEqual(before[0]["status"], "pending")
            self.assertEqual(before[0]["turns"], 1)
            # the dreamer replies — the first agent turn
            watch.apply_chat_turn(d, "chat-A", "agent", "yes, it's in review")
            after = watch.list_chats(d)
            self.assertEqual(len(after), 1)
            self.assertEqual(after[0]["status"], "replied")
            self.assertEqual(after[0]["turns"], 2)
            self.assertEqual(after[0]["last_by"], "agent")
            self.assertIn("shipping #504", after[0]["title"],
                          "title is the first HUMAN turn, not the reply")

    def test_command_wake_line_carries_the_same_receipt_id_as_the_journal(self):
        """#527 — the wake-line's receipt id == the journal receipt's id.

        Production line: the `command_line(..., rid)` call in
        _handle_command, where `rid = self.journal_result().receipt_id` —
        the SAME id the E3 commit in do_POST put in the journal. The
        coordinator matches a drained receipt (channel B) to a wake-line it
        already acted on (channel A) by this id — the join F1 of the #519
        exactly-once audit found missing.

        Reads BOTH the wake-line AND the journal receipt (via the production
        `pending` CLI — `dev/journal_consume.py pending`, the same query the
        tick runs) and asserts the ids agree.
        """
        with tempfile.TemporaryDirectory() as d:
            make_target(d)  # instant (default) — do-now always wakes
            base = self._serve(d)
            status, body = self._post_body(base + "/command",
                                           {"kind": "do-now",
                                            "text": "exactly once"})
            # PRECONDITION: the route ran end-to-end (202, not 503), or a
            # missing-wake / missing-id assertion is vacuous.
            self.assertEqual(status, 202, (status, body))
            resp = json.loads(body)
            # PRECONDITION: the POST returned a receipt id — the E3 commit
            # landed and the wake-line has something to carry. Without this
            # the wake-line would carry no id and the equality below would
            # compare nothing.
            self.assertIn("receipt", resp, resp)
            post_id = resp["receipt"]["receipt_id"]
            self.assertTrue(post_id, resp)

            # ── channel A: the wake-line ──────────────────────────────────
            wakes = self._wake_lines(d)
            # PRECONDITION: exactly one wake-line fired (do-now pre-empts in
            # every mode); without it there is no id to read.
            self.assertEqual(len(wakes), 1, wakes)
            wake = wakes[0]
            m = re.search(r'\[receipt (\S+)\]', wake)
            self.assertIsNotNone(m, f"no receipt id in wake-line: {wake!r}")
            wake_id = m.group(1)

            # ── channel B: the journal receipt (the production `pending` CLI)
            journal = watch._journal_path(d)
            proc = subprocess.run(
                [sys.executable, "dev/journal_consume.py", "pending",
                 "--journal", journal],
                capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            # PRECONDITION: pending listed the receipt (it committed), or
            # an equality assertion is meaningless.
            self.assertTrue(proc.stdout.strip(), proc.stdout)
            journal_id = proc.stdout.strip().split('\t')[0]

            # ── the join: all three ids agree ─────────────────────────────
            self.assertEqual(wake_id, journal_id,
                             f"wake-line id {wake_id!r} != journal id "
                             f"{journal_id!r}\n  wake: {wake!r}\n"
                             f"  pending: {proc.stdout!r}")
            self.assertEqual(wake_id, post_id,
                             f"wake-line id {wake_id!r} != POST receipt id "
                             f"{post_id!r}")


class TestDeployAction(unittest.TestCase):
    """#462 increment 2 — page-triggered `just deploy`.

    Loopback-only, single-flight, runner is faked so a check never runs the
    real recipe. Both success and failure of the schedule path are driven;
    the browser half (arm, generation wait, timeout copy) lives in
    staleremedy.mjs.
    """

    def setUp(self):
        # Reset single-flight + runner between tests so order never leaks.
        watch._deploy_inflight = False
        watch._deploy_runner = None

    def tearDown(self):
        watch._deploy_inflight = False
        watch._deploy_runner = None

    def _serve(self, target):
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), watch.make_handler(target))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def _post_raw(self, url, obj, peer=None):
        """POST and return (status, body dict). peer unused on live server
        (always loopback); non-loopback uses _post_as_peer."""
        req = urllib.request.Request(
            url, data=json.dumps(obj).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            try:
                return e.code, json.loads(body)
            except ValueError:
                return e.code, {"raw": body}

    def _post_as_peer(self, target, peer_host, body=b"{}"):
        """Drive one /deploy with a chosen client_address (loopback gate)."""
        authority = watch.RequestAuthority(["127.0.0.1"], 9)
        handler_cls = watch.make_handler(target, authority=authority)
        # StreamRequestHandler needs a connection that can sendall.
        request_bytes = (
            b"POST /deploy HTTP/1.1\r\n"
            b"Host: 127.0.0.1:9\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: " + str(len(body)).encode() + b"\r\n"
            b"\r\n" + body
        )

        class Conn:
            def __init__(self, data):
                self._rfile = io.BytesIO(data)
                self.writes = []

            def makefile(self, mode, _bufsize=-1):
                assert "r" in mode
                return self._rfile

            def sendall(self, data):
                self.writes.append(data)

        conn = Conn(request_bytes)
        handler_cls(conn, (peer_host, 43210), unittest.mock.Mock())
        raw = b"".join(conn.writes)
        # First write is headers; later may be body. Join and parse.
        head, _, rest = raw.partition(b"\r\n\r\n")
        status_line = head.split(b"\r\n", 1)[0].decode()
        status = int(status_line.split()[1])
        try:
            payload = json.loads(rest.decode() or "{}")
        except ValueError:
            payload = {"raw": rest.decode("utf-8", "replace")}
        return status, payload

    def test_peer_is_loopback_names_loopback_and_not(self):
        # Production line: peer_is_loopback itself. Red: return True always.
        self.assertTrue(watch.peer_is_loopback(("127.0.0.1", 1)))
        self.assertTrue(watch.peer_is_loopback(("::1", 1)))
        self.assertFalse(watch.peer_is_loopback(("192.168.1.20", 1)))
        self.assertFalse(watch.peer_is_loopback(("10.0.0.2", 9)))
        self.assertFalse(watch.peer_is_loopback(("not-an-ip", 1)))

    def test_loopback_schedules_runner_and_returns_started(self):
        # PRECONDITION derived: runner was not already inflight.
        self.assertFalse(watch.deploy_inflight())
        hit = threading.Event()
        seen = []

        def fake(target):
            seen.append(os.path.abspath(target))
            hit.set()
            # Hold the lock briefly so concurrency test can collide if needed.
            time.sleep(0.05)

        watch._deploy_runner = fake
        with tempfile.TemporaryDirectory() as d:
            t = make_target(d)
            base = self._serve(t)
            status, body = self._post_raw(base + "/deploy", {})
            self.assertEqual(status, 202, body)
            self.assertTrue(body.get("ok") is True, body)
            self.assertTrue(body.get("started") is True, body)
            self.assertTrue(hit.wait(2), "runner never called")
            self.assertEqual(seen, [os.path.abspath(t)])
        # Production line whose change reds this: delete start_deploy's
        # runner call, or return without _send_receipt started.

    def test_non_loopback_peer_is_refused_not_silent(self):
        # A non-loopback peer must get a durable rejection (landed false),
        # never a silent 200/202 ok. Red: drop the peer_is_loopback gate.
        called = []
        watch._deploy_runner = lambda t: called.append(t)
        with tempfile.TemporaryDirectory() as d:
            t = make_target(d)
            status, body = self._post_as_peer(t, "192.168.1.50")
            self.assertEqual(status, 202, body)
            self.assertTrue(body.get("rejected") is True, body)
            self.assertEqual(body.get("reason"), "domain_invalid")
            self.assertFalse(body.get("ok", True))
            # Give a moment in case a silent schedule raced.
            time.sleep(0.1)
            self.assertEqual(called, [], "runner must not run for LAN peer")

    def test_second_deploy_while_inflight_is_refused(self):
        # Single-flight: two concurrent schedules must not both start.
        # Red: remove the _deploy_inflight claim in start_deploy.
        release = threading.Event()
        started = []

        def fake(target):
            started.append(1)
            release.wait(2)

        watch._deploy_runner = fake
        with tempfile.TemporaryDirectory() as d:
            t = make_target(d)
            base = self._serve(t)
            s1, b1 = self._post_raw(base + "/deploy", {})
            self.assertEqual(s1, 202, b1)
            self.assertTrue(b1.get("started"), b1)
            # Second while first holds the slot.
            deadline = time.time() + 1
            while not watch.deploy_inflight() and time.time() < deadline:
                time.sleep(0.01)
            self.assertTrue(watch.deploy_inflight(),
                            "precondition: first deploy still inflight")
            s2, b2 = self._post_raw(base + "/deploy", {})
            self.assertEqual(s2, 202, b2)
            self.assertTrue(b2.get("rejected") is True, b2)
            self.assertEqual(b2.get("reason"), "domain_invalid")
            release.set()
            deadline = time.time() + 2
            while watch.deploy_inflight() and time.time() < deadline:
                time.sleep(0.01)
            self.assertEqual(len(started), 1, started)

    def test_page_wires_arm_writeverdict_and_deadline(self):
        # Client contract: reuses RUN_ARM_MS, gates on writeVerdict.landed,
        # names the never-finished case. Red: delete fireStaleDeploy's
        # writeVerdict call or the DEPLOY_WAIT_MS timeout copy.
        for token in (
            "function armStaleDeploy(",
            "function fireStaleDeploy(",
            "function onStaleActionClick(",
            "fetch('/deploy'",
            "writeVerdict(res)",
            "DEPLOY_WAIT_MS",
            "update never finished — this page is still the old one",
            "arms in ",
            "paintStaleDeployUI",
        ):
            self.assertIn(token, watch.PAGE, token)
        self.assertIn(
            "const DEPLOY_WAIT_MS = " + json.dumps(watch.DEPLOY_WAIT_MS),
            watch.PAGE)
        # Deploy is a registered write route (E2 derives from the table).
        self.assertIn('"/deploy": _handle_deploy',
                      inspect.getsource(watch.make_handler))
        # #490: mid-arm countdown must not re-call note/claim (restarts
        # .dreamin ~4 Hz). The in-place textContent path + lastLeft gate
        # are the production lines; reinstate unconditional c.note in
        # setCount to red the browser half (staleremedy.mjs §3b).
        arm_body = watch.PAGE.split("function armStaleDeploy(")[1].split(
            "function fireStaleDeploy(")[0]
        self.assertIn("lastLeft", arm_body)
        self.assertIn("m.textContent = text", arm_body)
        self.assertNotIn(
            "c.note(`arms in ${left}s — then this page updates`", arm_body)


class TestQuestionPriority(unittest.TestCase):
    """#197 — priority, then oldest, decided once in the parse."""

    def entries(self, *titles):
        return "## Open\n\n" + "".join(
            f"- **{t}** a body.\n\n" for t in titles)

    def test_the_band_is_read_off_the_title(self):
        for title, want in (("P1 · a", 1), ("P2 · a", 2), ("P3 · a", 3),
                            ("a", 2), ("", 2)):
            self.assertEqual(watch.title_priority(title), want, title)

    def test_absent_means_the_MIDDLE_band(self):
        # Not a detail: it is what makes an explicit P3 sort genuinely BELOW
        # an unmarked entry rather than level with it, which is the only
        # reason a writer would type P3 at all.
        self.assertEqual(watch.title_priority("no marker here"),
                         watch.PRIORITY_DEFAULT)
        self.assertEqual(watch.PRIORITY_DEFAULT, 2)

    def test_a_marker_outside_the_band_reads_as_unmarked(self):
        # THE QUIET FAILURE, and the one thing lint.py errors on: it reads to
        # a human as prioritised and sorts as unmarked, so the entry he most
        # wants seen sits mid-list looking urgent. The parser must not invent
        # a band for it — a wrong priority is worse than none.
        for title in ("P0 · a", "P4 · a", "P9 · a", "p1 · a", "P1· a",
                      "P1 - a", "P1a · b", "see P1 · later"):
            self.assertEqual(watch.title_priority(title), 2, title)

    def test_open_questions_sort_by_priority(self):
        text = self.entries("P3 · third", "unmarked", "P1 · first")
        self.assertEqual(
            [q["title"] for q in watch.parse_open_questions(text)],
            ["P1 · first", "unmarked", "P3 · third"])

    def test_a_tie_keeps_FILE_order_and_needs_no_date(self):
        # "Oldest first on a tie" is FREE: the file is chronological, so a
        # stable sort by priority alone produces it. A date comparison would
        # be a second mechanism able to disagree with the first — and it
        # would disagree exactly where stamps are missing or hand-edited.
        text = self.entries("P1 · early", "second", "third",
                            "P1 · later", "fourth")
        self.assertEqual(
            [q["title"] for q in watch.parse_open_questions(text)],
            ["P1 · early", "P1 · later", "second", "third", "fourth"])

    def test_answered_entries_are_left_in_file_order(self):
        # A priority says how urgently something needs him; a settled entry
        # needs him for nothing. Sorting these would order a record by an
        # urgency that has expired, and scramble the one property the section
        # is read for.
        text = ("## Answered\n\n"
                "- **P3 · older** → resolved (2026-07-24): a.\n\n"
                "- **P1 · newer** → resolved (2026-07-25): b.\n")
        got = watch.parse_answered(text)
        self.assertEqual([e["title"] for e in got], ["P3 · older", "P1 · newer"])
        # and no priority key: a field nobody sorts by is a claim that
        # something does
        self.assertNotIn("priority", got[0])

    def test_ordering_is_in_the_PARSE_so_neither_surface_can_sort(self):
        # Three surfaces render these entries and all of them go through
        # qaCard. A sort in each is three chances to disagree about which
        # question is most urgent. Both list builders derive their pairs with
        # the SAME expression, so neither can quietly grow a sort of its own.
        derive = "d.questions_open.map((q, i) => [q, i]);"
        self.assertEqual(watch.PAGE.count(derive), 2,
                         "qSection and buildQuestions must derive the list "
                         "identically, and nothing else may derive it at all")
        self.assertNotIn("questions_open.slice().sort", watch.PAGE)
        self.assertNotIn("questions_open.sort", watch.PAGE)

    def test_the_fixture_carries_a_discriminating_arrangement(self):
        # THE KNOWN TRAP: the frozen fixture had zero P-prefixed entries, so
        # every ordering guard would have passed over a sort that did
        # nothing. Two properties are needed and neither is obvious:
        #   · the sorted order must be a real PERMUTATION of the file order,
        #     or a renderer that ignores priority is accidentally right;
        #   · an unmarked entry must appear AFTER the P3 one in the file, or
        #     a build defaulting to P3 renders the identical order.
        path = os.path.join(os.path.dirname(os.path.abspath(watch.__file__)),
                            "dev", "capture", "fixture", ".dreamwork",
                            "questions.md")
        with open(path) as f:
            text = f.read()
        filed = watch._parse_entries(text, "Open", lift_answer=True)
        sorted_ = watch.parse_open_questions(text)
        self.assertNotEqual([e["title"] for e in filed],
                            [q["title"] for q in sorted_],
                            "the fixture's sorted order equals its file order")
        bands = [watch.title_priority(e["title"]) for e in filed]
        p3 = bands.index(3)
        self.assertIn(2, bands[p3 + 1:],
                      "no unmarked entry follows the P3 one, so a build "
                      "defaulting to P3 would render the identical order")


class TestPluginCommands(unittest.TestCase):
    """#86 — a plugin's commands, read where the composer can render them.

    The declaration is the plugin's, the file is the loop's, and this is the
    READ. `lint.py` reports on the same file for a human to fix later; these
    are the refusals that have to hold while a request is being answered.
    """

    def write(self, d, doc):
        os.makedirs(os.path.join(d, ".dreamwork"), exist_ok=True)
        with open(os.path.join(d, ".dreamwork", "plugin-commands.json"),
                  "w") as f:
            f.write(doc if isinstance(doc, str) else json.dumps(doc))
        return d

    def test_absence_costs_nothing(self):
        # The common case by a wide margin: most targets load no plugin that
        # declares a command, and the composer must render exactly as it did
        # before there was a plugin system.
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".dreamwork"))
            self.assertEqual(watch.plugin_commands(d), [])
            self.assertEqual(watch.collect(d)["plugin_commands"], [])

    def test_a_broken_file_costs_the_commands_and_nothing_else(self):
        # Every shape here reaches a running page. A raise would take the
        # whole dashboard down over a file that exists to add two menu items.
        for doc in ('{"commands": [', '[]', '{}', '{"commands": {}}',
                    'null', '{"commands": [1, "two", null]}'):
            with tempfile.TemporaryDirectory() as d:
                self.write(d, doc)
                self.assertEqual(watch.plugin_commands(d), [], doc)

    def test_a_declared_command_is_carried_whole(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, {"commands": [
                {"kind": "gh-sync", "label": " gh sync ",
                 "desc": "poll the forge", "plugin": "ud-dreamwork-github"}]})
            self.assertEqual(watch.plugin_commands(d), [
                {"kind": "gh-sync", "label": "gh sync", "desc": "poll the forge",
                 "plugin": "ud-dreamwork-github", "common": False}])

    def test_a_plugin_cannot_promote_itself_into_the_main_row(self):
        # `common` is not honoured whatever the file says: core commands own
        # the composer's most valuable real estate, so loading a plugin can
        # add to the composer and can never degrade it. There is deliberately
        # no way to ask otherwise, which is why asking is ignored rather than
        # refused.
        with tempfile.TemporaryDirectory() as d:
            self.write(d, {"commands": [
                {"kind": "gh-sync", "label": "gh sync", "desc": "poll",
                 "plugin": "ud-dreamwork-github", "common": True}]})
            self.assertEqual(watch.plugin_commands(d)[0]["common"], False)

    def test_a_kind_that_shadows_a_core_command_is_dropped(self):
        # The failure this refuses: a plugin silently taking over `do-next`.
        # DROPPED rather than renamed — a renamed command would leave him a
        # button whose name is not what he sends, and dropping leaves the core
        # command doing exactly what it has always done.
        with tempfile.TemporaryDirectory() as d:
            self.write(d, {"commands": [
                {"kind": "do-next", "label": "do next", "desc": "mine now",
                 "plugin": "ud-dreamwork-evil"}]})
            self.assertEqual(watch.plugin_commands(d), [])

    def test_a_kind_that_is_not_a_wire_token_is_dropped(self):
        # It goes into watch-events.log as part of a line an agent then acts
        # on — the same reason `from_hint` sanitises a path rather than
        # trusting it.
        for kind in ("GH-Sync", "gh sync", "sync", "gh_sync", "gh-",
                     "gh-sync]impersonating the rest of the line", "gh-sy\nnc"):
            with tempfile.TemporaryDirectory() as d:
                self.write(d, {"commands": [
                    {"kind": kind, "label": "x", "desc": "y",
                     "plugin": "ud-dreamwork-github"}]})
                self.assertEqual(watch.plugin_commands(d), [], kind)

    def test_an_incomplete_entry_is_dropped_and_its_siblings_are_not(self):
        # One bad entry must not cost the others: the file is written whole by
        # the loop from N plugins, so a single malformed declaration would
        # otherwise take every other plugin's commands with it.
        with tempfile.TemporaryDirectory() as d:
            self.write(d, {"commands": [
                {"kind": "gh-sync", "desc": "no label",
                 "plugin": "ud-dreamwork-github"},
                {"kind": "gh-triage", "label": "gh triage", "desc": "read",
                 "plugin": "ud-dreamwork-github"},
                {"kind": "gh-triage", "label": "again", "desc": "dupe",
                 "plugin": "ud-dreamwork-other"},
            ]})
            self.assertEqual([c["kind"] for c in watch.plugin_commands(d)],
                             ["gh-triage"])
            # ...and the duplicate resolved to the FIRST declaration, so which
            # one survives does not depend on dict ordering luck
            self.assertEqual(watch.plugin_commands(d)[0]["label"], "gh triage")

    def test_the_fixture_declares_commands_for_the_guards_to_render(self):
        # The guards run against dev/capture/fixture, and this target loads no
        # plugin — so without a declaration in the fixture the rendering guard
        # would be asserting over an empty list and passing on a page that
        # renders nothing. (dev/capture/README.md: when a guard needs a shape
        # the fixture lacks, add it to the fixture.)
        fixture = os.path.join(os.path.dirname(os.path.abspath(watch.__file__)),
                               "dev", "capture", "fixture")
        cmds = watch.plugin_commands(fixture)
        self.assertTrue(cmds, "the fixture declares no plugin command")
        self.assertTrue(all(c["plugin"] for c in cmds))

    def test_the_page_reads_the_table_rather_than_a_fixed_set(self):
        for token in ('window.dwPluginCommands',
                      'function syncPluginCommands(',
                      'COMMANDS = CORE_COMMANDS.concat(next)',
                      # the menu is reconciled by kind, so the nodes it
                      # returns are exactly the arrivals
                      'function menuItem(', "class=\"cmpl\"",
                      # and an arrival eases in on the shared idiom
                      ".classList.add('qreveal', 'dreamin')",
                      '.cmdmenuitem.qreveal'):
            self.assertIn(token, watch.PAGE)


class TestAnswerWritesAreAtomic(unittest.TestCase):
    """#370 — `/answer` and `/comment` truncated `questions.md` in place.

    Both routes wrote `with open(qpath, "w") as f: f.write(new_text)`. The
    truncation happens at open, so anything that stops the write between there
    and the flush leaves his questions file destroyed — every open question,
    every answered one, every thread. Thirty lines earlier `/ask` already wrote
    `answers.md` through `atomic_write_text`, which does temp + fsync +
    os.replace + parent fsync, so the correct pattern was already in the module
    and these two routes simply did not use it.

    The failure is induced rather than mocked, because the design's own rule is
    to kill at a real seam instead of patching durability away: `RLIMIT_FSIZE`
    set just above the file's current length makes the longer post-answer text
    fail partway through a real `write(2)`. Under the old code that leaves a
    file of exactly the limit's size holding half the new text; under
    `atomic_write_text` the original is byte-identical and no temp survives.

    `SIGXFSZ` has to be ignored first — its default action terminates the
    process, which would take the test runner with it and report as a crash
    rather than a red.
    """

    @staticmethod
    @contextlib.contextmanager
    def _size_cap(limit):
        import resource
        import signal as sig
        prev = sig.signal(sig.SIGXFSZ, sig.SIG_IGN)
        soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
        resource.setrlimit(resource.RLIMIT_FSIZE, (limit, hard))
        try:
            yield
        finally:
            resource.setrlimit(resource.RLIMIT_FSIZE, (soft, hard))
            sig.signal(sig.SIGXFSZ, prev)

    def _serve(self, target):
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), watch.make_handler(target))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def _post(self, url, obj):
        req = urllib.request.Request(
            url, data=json.dumps(obj).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
        except Exception:
            # Under the old truncating write the handler thread dies and the
            # connection drops with no response at all — and the traceback it
            # tries to print hits the same size cap. Swallowed on purpose: the
            # claim being tested is about the FILE, and letting a transport
            # error escape here would make the red say "RemoteDisconnected"
            # instead of "his questions file was damaged".
            return 0

    def _interrupted(self, d, route, payload):
        """POST `route` with the file size capped, and return the file after."""
        qpath = os.path.join(d, ".dreamwork", "questions.md")
        before = open(qpath, encoding="utf-8").read()
        # The cap must sit ABOVE the current file and BELOW the file plus what
        # the route appends — derived from both, never a literal, or the day the
        # fixture grows this test starts asserting nothing.
        grown = len(before.encode()) + 40
        self.assertGreater(grown, len(before.encode()),
                           "the cap must allow the file that already exists")
        base = self._serve(d)
        with self._size_cap(grown):
            status = self._post(base + route, payload)
        after = open(qpath, encoding="utf-8").read()
        leftovers = [f for f in os.listdir(os.path.join(d, ".dreamwork"))
                     if f.startswith(".questions.md")]
        return before, after, status, leftovers

    def test_an_interrupted_answer_leaves_questions_md_intact(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            before, after, status, leftovers = self._interrupted(
                d, "/answer",
                {"question": "A real open question?",
                 "answer": "x" * 400, "from": "/questions"})
            self.assertNotEqual(status, 200,
                                "a write that could not complete must not report success")
            self.assertEqual(after, before,
                             "his questions file was damaged by a failed answer")
            self.assertEqual(leftovers, [], "a temp file survived the failure")

    def test_an_interrupted_comment_leaves_questions_md_intact(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            before, after, status, leftovers = self._interrupted(
                d, "/comment",
                {"question": "A real open question?",
                 "comment": "y" * 400, "section": "Open", "from": "/questions"})
            self.assertNotEqual(status, 200)
            self.assertEqual(after, before,
                             "his questions file was damaged by a failed comment")
            self.assertEqual(leftovers, [])

    def test_the_size_cap_really_does_stop_the_write(self):
        # The precondition of both tests above: if the cap were ineffective they
        # would pass on an unmodified file for the wrong reason. Proved on a
        # scratch file through the same mechanism, in the same process.
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "probe")
            with open(p, "w") as f:
                f.write("z" * 50)
            with self._size_cap(60), self.assertRaises(OSError) as cm:
                with open(p, "w") as f:
                    f.write("z" * 500)
                    f.flush()
            self.assertEqual(cm.exception.errno, errno.EFBIG)

    def test_neither_route_uses_a_truncating_open(self):
        # The production line, named. `open(qpath, "w")` truncates before it
        # writes; this is the construct that must not come back.
        src = inspect.getsource(watch)
        self.assertNotIn('open(qpath, "w"', src)
        self.assertEqual(src.count("atomic_write_text(qpath"), 2,
                         "both /answer and /comment write through the atomic path")


class TestSubmissionIdempotency(unittest.TestCase):
    """#274 — duplicate submissions must be idempotent end to end.

    The journal dedupes a RECEIPT by client_action_id (same UUID+digest → one
    receipt), but the receipt→application join had no dedup-hit signal: a
    replayed UUID still dispatched the handler and appended a second Answer
    bullet. Three witnesses of this reached durable state (two byte-identical
    answers ~188ms apart; duplicate same-timestamp receipts + Answer bullets;
    a ruling landed as two byte-identical bullets) and one was invisible for
    two hours.

    The fix short-circuits a dedup hit (kind != 'inserted') to the original
    receipt's verdict BEFORE the handler dispatches — the seam is in do_POST
    between `_journal_receive` and `handler(self)`. This is the application
    half; the journal half (receive() → replay/conflict/inserted) is complete
    and tested in test_user_events_sqlite.py.
    """

    def _serve(self, target):
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), watch.make_handler(target))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def _post_id(self, url, obj, action_id):
        """POST with an explicit X-Client-Action-Id (the idempotency key).

        This is the header the browser attempt store sends (#274); the test
        drives it directly so the red line is the server join, not the client.
        """
        req = urllib.request.Request(
            url, data=json.dumps(obj).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json",
                     "X-Client-Action-Id": action_id})
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode("utf-8")

    @staticmethod
    def _answer_bullets(d):
        """Count application side-effects: Answer sub-bullets in questions.md.

        append_answer does NOT move the entry to Answered — it appends an
        `- **Answer (via watch, …):**` sub-bullet while the entry stays in
        Open — so a replayed POST finds the entry again and appends a SECOND
        bullet. That is the double-application this test must catch.
        """
        qpath = os.path.join(d, ".dreamwork", "questions.md")
        with open(qpath, encoding="utf-8") as f:
            return f.read().count("**Answer (via watch,")

    @staticmethod
    def _receipt_count(d):
        with watch.open_journal(watch._journal_path(d)) as journal:
            return journal.receipt_count()

    @staticmethod
    def _extract_draftstore():
        """Pull the DraftStore IIFE out of PAGE for node execution.

        The module is self-contained (only globals it reads are `data`,
        `localStorage`, `crypto`), so it runs under node with those mocked.
        Splits on the IIFE's own open/close — there is no nested `})();`
        inside it, so the first close is the module's.
        """
        import re
        body = watch.PAGE.split("<script>", 1)[1].rsplit("</script>", 1)[0]
        marker = "const DraftStore = (() => {"
        head, rest = body.split(marker, 1)
        inner, _tail = rest.split("})();", 1)
        return marker + inner + "})();"

    def test_attempt_store_stable_per_draft_fresh_after_edit(self):
        """#274 client: the per-attempt id is stable for one composition —
        across repeat calls AND a same-text re-save (so a double-click or a
        retry after a re-render sends the SAME id and the journal dedupes) —
        and fresh after an edit (an edit is a new attempt, never deduped
        across content). Cleared with the draft on landed.

        Production lines: DraftStore.attemptId (mint/get) and the
        aid-on-text-match preservation in save()."""
        import shutil, subprocess, textwrap
        node = shutil.which("node")
        if not node:
            self.skipTest("node not available — the JS gate did NOT run")
        store = self._extract_draftstore()
        script = textwrap.dedent("""\
            // deterministic localStorage + REAL v4 UUIDs (backed by node's
            // crypto, so the shape assertion tests _mintId's real output, not
            // a mock). The behaviour under test is stability/drop/clear, which
            // are deterministic regardless of the random value.
            const _nc = require('crypto');
            const crypto = { randomUUID: () => _nc.randomUUID() };
            const _s = {};
            const localStorage = {
              getItem: k => (k in _s ? _s[k] : null),
              setItem: (k, v) => { _s[k] = String(v); },
              removeItem: k => { delete _s[k]; },
            };
            const data = { target: 'proj-T' };
            %s
            const lid = DraftStore.id('card', 'Q1');
            DraftStore.save(lid, 'hello');
            const a1 = DraftStore.attemptId(lid);          // mint for 'hello'
            const a2 = DraftStore.attemptId(lid);          // same draft -> stable
            DraftStore.save(lid, 'hello');                 // re-save same text -> kept
            const a3 = DraftStore.attemptId(lid);          // still stable
            DraftStore.save(lid, 'hello world');           // EDIT -> stale id dropped
            const a4 = DraftStore.attemptId(lid);          // new attempt -> fresh
            DraftStore.clear(lid);                         // landed -> record gone
            const rec = DraftStore.get(lid);
            process.stdout.write(JSON.stringify({
              stable: a1 === a2 && a2 === a3,
              freshAfterEdit: a4 !== a1,
              cleared: rec === null || !rec.attemptId,
              shape: /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(a1)
            }));
        """) % store
        out = subprocess.check_output(["node", "-e", script], text=True)
        res = json.loads(out)
        self.assertTrue(res['stable'],
                        f"attempt id must be stable for one draft: {res}")
        self.assertTrue(res['freshAfterEdit'],
                        f"an edit must mint a fresh id (dedupe by id, not content): {res}")
        self.assertTrue(res['cleared'],
                        f"clear must drop the id with the draft: {res}")
        self.assertTrue(res['shape'],
                        f"the id must be a v4 UUID shape: {res}")

    def test_covered_submit_paths_send_the_attempt_id(self):
        """#274: the boundary across submit paths, stated and checked.

        COVERED (append routes that duplicate content on re-application —
        these mint a per-attempt id and send X-Client-Action-Id):
          /answer, /ask, /comment, /command (main composer + popout).
        DECLARED OUT:
          /decide — its client POST originates in the review-artifact
            surface, not watch.py's composer/answer region (the server
            short-circuit still protects it once that surface sends the id);
          /tint, /run-mode, /posture — state-setting, application-level
            idempotent (same value = no mutation, no content duplication);
          /deploy — single-flight guard + loopback-only already prevents a
            double submit.
        This pins the boundary so a new path cannot slip past uninspected.
        """
        # the header is sent
        self.assertIn("'X-Client-Action-Id'", watch.PAGE)
        # each covered path mints an attempt id from its draft store
        for token in (
            "DraftStore.attemptId(DraftStore.id('card', q.title))",   # /answer
            "DraftStore.attemptId(DraftStore.id('card', entry.title))",  # /comment
            "DraftStore.attemptId(DraftStore.id('ask', 'main'))",     # /ask
            "DraftStore.attemptId(composerLid())",                    # /command main
            "DraftStore.attemptId(popLid)",                           # /command popout
        ):
            self.assertIn(token, watch.PAGE,
                          f"covered submit path must mint an attempt id: {token!r}")

    def test_same_action_id_replays_to_one_receipt_one_application(self):
        """#274: replay of one attempt → exactly one receipt AND one application.

        Production line that must change to fail this: the dedup-hit
        short-circuit in do_POST (kind != 'inserted' skips handler dispatch).
        Without it the second POST re-runs _handle_answer and appends a second
        Answer bullet — the bug's shape.
        """
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            base = self._serve(d)
            body = {"question": "A real open question?",
                    "answer": "one and only answer", "from": "/questions"}
            # precondition: the entry is answerable (matched, not 409)
            s1, _ = self._post_id(base + "/answer", body, "uuid-replay-A")
            self.assertEqual(s1, 202, "the first POST must match the entry")
            # same UUID + same body: a retry or double-click of one attempt
            s2, _ = self._post_id(base + "/answer", body, "uuid-replay-A")
            self.assertEqual(s2, 202)
            # ONE application — the second POST did not append a bullet
            self.assertEqual(self._answer_bullets(d), 1,
                             "a replayed attempt must not re-apply")
            # ONE receipt — the journal already deduped this (the red line is
            # the application count above; this pins the journal half)
            self.assertEqual(self._receipt_count(d), 1,
                             "same UUID+digest must be one receipt")

    def test_distinct_action_id_identical_text_is_two_attempts(self):
        """#274: a new attempt with IDENTICAL text but a different action id is
        a distinct intentional action — two receipts, two applications. Dedupe
        is by client_action_id, never by content."""
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            base = self._serve(d)
            body = {"question": "A real open question?",
                    "answer": "same words different intent", "from": "/questions"}
            self._post_id(base + "/answer", body, "uuid-distinct-A")
            self._post_id(base + "/answer", body, "uuid-distinct-B")
            self.assertEqual(self._answer_bullets(d), 2,
                             "distinct ids are distinct attempts — both apply")
            self.assertEqual(self._receipt_count(d), 2,
                             "distinct ids mint distinct receipts")

    def test_replayed_rejection_returns_the_rejection_verdict(self):
        """#274: a replayed REFUSED action returns the original rejection, so
        the client keeps its draft on a retried refusal exactly as on the
        first refusal.

        Production line whose change reds this (the coordinator's gate
        injection, which the lane's suite passed over — the green red-run
        this test closes): `_replay_verdict`'s
        `if result.state == "rejected":` branch. Sabotage it to always-ok
        and a replayed refusal reads `ok: true` — the client clears a draft
        nothing durable holds, the #136 lie one seam over.
        """
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            base = self._serve(d)
            body = {"question": "A real open question?",
                    "answer": "   ", "from": "/questions"}  # schema_invalid
            s1, b1 = self._post_id(base + "/answer", body, "uuid-replay-R")
            self.assertEqual(s1, 202)
            r1 = json.loads(b1)
            self.assertTrue(r1.get("rejected"),
                            "precondition: the first POST really was refused")
            rid = (r1.get("receipt") or {}).get("receipt_id")
            self.assertTrue(rid, "precondition: the 202 carries the receipt")
            with watch.open_journal(watch._journal_path(d)) as journal:
                rec = journal.get_receipt(rid)
            self.assertIsNotNone(rec, "precondition: receipt persisted")
            self.assertEqual(rec["state"], "rejected",
                             "precondition: the refusal is durable — else the "
                             "replay has no verdict to carry and the test is "
                             "vacuous")
            # the replay: same UUID + same body (a retry of the refused
            # attempt — a double-click or a lost-response resend)
            s2, b2 = self._post_id(base + "/answer", body, "uuid-replay-R")
            self.assertEqual(s2, 202)
            r2 = json.loads(b2)
            self.assertEqual(self._receipt_count(d), 1,
                             "precondition: the second POST was a dedup hit, "
                             "not a new receipt")
            self.assertTrue(r2.get("rejected"),
                            "a replayed refusal must return the rejection — "
                            "ok:true clears a draft nothing holds")


class TestShortBodyIsWitnessedAsShort(unittest.TestCase):
    """#371 — an interrupted body was recorded as a complete submission.

    `do_POST` reads `min(nbytes, MAX_BODY)` and never compares the result to
    what was promised, so a connection dropped mid-body yields a partial
    payload. `truncated` next to it catches the opposite case — a body too
    LARGE — and reads as though it covered both.

    The damage is in the recovery log rather than in a file: `submissions.log`
    stores `bytes` as the DECLARED length beside a shorter payload, with nothing
    saying it arrived short. That file exists so his words can be recovered when
    a handler refuses them, and a reader cannot tell a genuinely short answer
    from a truncated one.

    **This fixes only the half that needs no decision from him.** Whether the
    server should then reject, or keep a partial witness marked incomplete and
    proceed, is Q2 of #263's open ask; the entry says to wait rather than guess,
    so the response behaviour here is deliberately unchanged. Recording the
    shortfall is compatible with either answer and makes both implementable.
    """

    def _serve(self, target):
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), watch.make_handler(target))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server.server_address

    @staticmethod
    def _post_short(addr, path, declared, sent):
        """POST claiming `declared` bytes and sending `sent`, then half-close.

        urllib will not lie about Content-Length, and a mock would prove
        nothing about the read — so this is a real socket dropping a real body
        mid-flight, which is the event being witnessed.
        """
        s = socket.create_connection(addr, timeout=5)
        try:
            head = (f"POST {path} HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                    f"Content-Type: application/json\r\n"
                    f"Content-Length: {declared}\r\nConnection: close\r\n\r\n")
            s.sendall(head.encode() + sent)
            s.shutdown(socket.SHUT_WR)      # the drop: EOF before `declared`
            with contextlib.suppress(OSError):
                while s.recv(4096):
                    pass
        finally:
            s.close()

    def _witness(self, d):
        path = os.path.join(d, ".dreamwork", "submissions.log")
        with open(path, encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        self.assertTrue(lines, "nothing was witnessed at all")
        return lines[-1]

    def test_a_body_that_arrives_short_is_recorded_as_short(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            addr = self._serve(d)
            sent = b'{"question": "A real open question?", "answer": "abc'
            declared = len(sent) + 500
            # The precondition: the two numbers must actually differ, derived
            # from the payload rather than asserted as literals.
            self.assertGreater(declared, len(sent))
            self._post_short(addr, "/answer", declared, sent)
            rec = self._witness(d)
            self.assertEqual(rec["bytes"], declared,
                             "`bytes` stays what he SENT, per the format contract")
            self.assertEqual(rec["got"], len(sent),
                             "the number of bytes that actually arrived must be recorded")
            self.assertTrue(rec.get("short"),
                            "a short body must be marked, or a reader cannot tell "
                            "a truncated answer from a genuinely brief one")

    def test_a_complete_body_is_not_marked_short(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            addr = self._serve(d)
            body = b'{"question": "A real open question?", "answer": "complete"}'
            self._post_short(addr, "/answer", len(body), body)
            rec = self._witness(d)
            self.assertEqual(rec["bytes"], len(body))
            self.assertNotIn("short", rec,
                             "marking a complete body would make the flag meaningless")
            self.assertNotIn("got", rec, "`got` is only worth its bytes when it differs")

    def test_an_oversize_body_is_truncated_not_short(self):
        # The two conditions are distinct and the old code conflated them: too
        # LARGE is a cap the server applied, too SMALL is a promise the client
        # broke. A reader recovering his words needs to know which.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            addr = self._serve(d)
            body = b'{"a": "' + b'z' * (watch.MAX_BODY + 100) + b'"}'
            self._post_short(addr, "/answer", len(body), body)
            rec = self._witness(d)
            self.assertTrue(rec.get("truncated"))
            self.assertNotIn("short", rec,
                             "a body the server capped did not arrive short")


class TestShortBodyProceedsAsIncompleteWitness(unittest.TestCase):
    """#371 policy — his 05:43 ruling on #263 Q2: a short body is NOT refused;
    it is kept as a partial witness marked incomplete and allowed to proceed.

    The witness half (#371, `d33cc2f`) records `short`/`got`. The E1 envelope
    block then REFUSED an interrupted body with a 400 and no receipt, reading
    law 2 as "transport-envelope failure before receipt". The ruling amends
    that: the partial bytes are kept, marked incomplete, and the request
    proceeds through the normal pipeline. The incomplete marker is preserved
    end to end so a reader recovering the words knows what arrived is partial.

    A real socket, not a mock: urllib will not lie about Content-Length, and a
    mocked read proves nothing about the read (the #320 trap)."""

    def _serve(self, target):
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), watch.make_handler(target))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server.server_address

    @staticmethod
    def _post_short_response(addr, path, declared, sent):
        """Promise `declared`, send `sent`, half-close; return raw response."""
        s = socket.create_connection(addr, timeout=5)
        try:
            head = (f"POST {path} HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                    f"Content-Type: application/json\r\n"
                    f"Content-Length: {declared}\r\nConnection: close\r\n\r\n")
            s.sendall(head.encode() + sent)
            s.shutdown(socket.SHUT_WR)      # the drop: EOF before `declared`
            chunks = []
            with contextlib.suppress(OSError):
                while True:
                    data = s.recv(4096)
                    if not data:
                        break
                    chunks.append(data)
            return b"".join(chunks)
        finally:
            s.close()

    def _witness(self, d):
        path = os.path.join(d, ".dreamwork", "submissions.log")
        with open(path, encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        self.assertTrue(lines, "nothing was witnessed at all")
        return lines[-1]

    def test_a_short_body_proceeds_and_is_marked_incomplete(self):
        # The ruling: keep the partial witness, mark it incomplete, let it
        # proceed. A transport 400 refusal is the behaviour this replaces.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            addr = self._serve(d)
            sent = b'{"question": "A real open question?", "answer": "abc'
            declared = len(sent) + 500
            # Precondition, derived not pinned: a real interruption.
            self.assertGreater(declared, len(sent))
            resp = self._post_short_response(addr, "/answer", declared, sent)
            status = resp.split(b"\r\n", 1)[0]
            # It PROCEEDS, not refused: the partial body is malformed JSON, so
            # the handler rejects it, but that is a pipeline rejection (202
            # received->rejected), never a transport 400.
            self.assertNotIn(b" 400 ", status, status)
            # The incomplete marker is preserved end to end through the
            # proceed path (not lost when the refusal is removed).
            rec = self._witness(d)
            self.assertTrue(rec.get("short"), rec)
            self.assertEqual(rec["got"], len(sent))
            self.assertEqual(rec["bytes"], declared)

    def test_a_complete_body_is_unaffected_by_the_policy(self):
        # Byte-identical for a body that is not short: no marker, proceeds.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            addr = self._serve(d)
            body = b'{"question": "A real open question?", "answer": "ok"}'
            resp = self._post_short_response(addr, "/answer", len(body), body)
            status = resp.split(b"\r\n", 1)[0]
            self.assertIn(b" 202 ", status, status)
            rec = self._witness(d)
            self.assertNotIn("short", rec)
            self.assertNotIn("got", rec)


class TestHandoffIdGrammar(unittest.TestCase):
    """#401 / #406: hand-off id vocabulary and section rules.

    The earlier grammar was ``#(\\d+)`` on all three patterns, so a sub-id was
    dropped from pending AND from the malformed fallback (same blind axis).
    Wrong-section lines were invisible because malformed only ran in section P.
    """

    def test_a_sub_id_handoff_is_parsed_not_dropped(self):
        text = (
            "# Hand-offs\n\n## Pending\n\n"
            "- **#392a** · landed `abc` · 2026-07-28 09:40 · by ccc @glm52 — x\n"
            "\n## Folded\n"
        )
        pending, folded, malformed = watch.parse_handoffs(text)
        self.assertEqual(pending, [("392a", "abc", "ccc @glm52 — x")])
        self.assertEqual(malformed, [])
        self.assertEqual(folded, set())

    def test_a_combined_id_handoff_is_parsed(self):
        text = (
            "# Hand-offs\n\n## Pending\n\n"
            "- **#367/#392** · landed `deadbee` · 2026-07-28 10:00 · by x — y\n"
            "\n## Folded\n"
        )
        pending, folded, malformed = watch.parse_handoffs(text)
        self.assertEqual(pending, [("367/392", "deadbee", "x — y")])
        self.assertEqual(malformed, [])

    def test_a_pending_line_in_the_wrong_section_is_reported_malformed(self):
        # Precondition: the line sits under ## Folded, not ## Pending — derive
        # that at runtime so a fixture reorder cannot hollow the test.
        pend_line = (
            "- **#5** · landed `abc` · 2026-07-28 09:40 · by dreamer-5 — x"
        )
        text = (
            "# Hand-offs\n\n## Pending\n\n## Folded\n" + pend_line + "\n"
        )
        after_folded = text.split("## Folded", 1)[1]
        self.assertIn(pend_line, after_folded)
        self.assertNotIn(pend_line, text.split("## Folded", 1)[0])
        pending, folded, malformed = watch.parse_handoffs(text)
        self.assertEqual(pending, [], "wrong-section line must not be pending")
        self.assertEqual(len(malformed), 1, malformed)
        self.assertEqual(malformed[0][0], "5")
        self.assertIn(pend_line, malformed[0][1])

    def test_an_unrecognised_id_shape_is_malformed_not_silent(self):
        # Prose inside the bold head is not an accepted id token; bare must
        # still match so malformed fires (the load-bearing fallback widen).
        line = (
            "- **#96 stage 1** · landed `abc` · 2026-07-28 09:40 · by x — y"
        )
        text = "# Hand-offs\n\n## Pending\n\n" + line + "\n\n## Folded\n"
        self.assertIsNone(watch.HANDOFF_PENDING_RE.match(line))
        self.assertIsNotNone(
            watch.HANDOFF_BARE_RE.match(line),
            "BARE must match any bolded-id head or the fallback shares the "
            "parser's blind axis again")
        pending, folded, malformed = watch.parse_handoffs(text)
        self.assertEqual(pending, [])
        self.assertEqual(len(malformed), 1, malformed)
        self.assertIn("96 stage 1", malformed[0][0])

    def test_correlation_normalises_a_sub_id_to_its_parent(self):
        self.assertEqual(watch.handoff_parent_ids("392a"), ["392"])
        self.assertEqual(watch.handoff_parent_ids("392"), ["392"])
        self.assertEqual(watch.handoff_parent_ids("367/392"), ["367", "392"])
        self.assertEqual(watch.handoff_parent_ids("392b"), ["392"])
        self.assertEqual(watch.handoff_parent_ids("1000"), ["1000"])  # four-digit
        # Named function, deliberate — not ENTRY_ID's silent letter-strip as API.
        self.assertNotEqual(watch.handoff_parent_ids("392a"), ["392a"])


class TestHandoffMultiSha(unittest.TestCase):
    """#427: parse_handoffs accepts one-or-more shas (the #415 grammar split).

    lint.check_handoffs already reclassified multi-sha out of malformed; the
    watch parser still used a single-sha HANDOFF_PENDING_RE, so a two-sha
    line never reached pending_handoff_records. These tests call the real
    parser — not a hand-built filtered list — so reverting the RE reds them.
    """

    def test_one_sha_and_two_sha_parse_side_by_side(self):
        # Two distinct shas derived at runtime; the gap is the precondition
        # the test depends on (not a literal tuned to today's fixture).
        sha_a = "54c68e8"
        sha_b = "25a3fe4"
        self.assertNotEqual(sha_a, sha_b, "precondition: the two shas must differ")

        one_line = (
            f"- **#411** · landed `{sha_a}` · 2026-07-28 14:08 · by "
            f"grok (wt/411) — one commit"
        )
        two_line = (
            f"- **#411** · landed `{sha_a}` `{sha_b}` · 2026-07-28 14:08 · by "
            f"grok (wt/411) — fix plus follow-up"
        )
        # Production line named for red-run: watch.HANDOFF_PENDING_RE must match
        # both. Reinstate the single-backtick RE and this assertion fails first.
        self.assertIsNotNone(
            watch.HANDOFF_PENDING_RE.match(one_line),
            "one-sha Pending line must match HANDOFF_PENDING_RE")
        self.assertIsNotNone(
            watch.HANDOFF_PENDING_RE.match(two_line),
            "two-sha Pending line must match HANDOFF_PENDING_RE (#427)")

        one_text = "# Hand-offs\n\n## Pending\n\n" + one_line + "\n\n## Folded\n"
        two_text = "# Hand-offs\n\n## Pending\n\n" + two_line + "\n\n## Folded\n"

        one_pending, one_folded, one_mal = watch.parse_handoffs(one_text)
        two_pending, two_folded, two_mal = watch.parse_handoffs(two_text)

        self.assertEqual(one_mal, [])
        self.assertEqual(two_mal, [],
                         "two-sha must not be malformed after #427; was: "
                         f"{two_mal!r}")
        self.assertEqual(one_folded, set())
        self.assertEqual(two_folded, set())
        self.assertEqual(len(one_pending), 1)
        self.assertEqual(len(two_pending), 1)

        # Triple shape: (id, first_sha, claimer) — lint and older tests unpack it.
        self.assertEqual(one_pending[0][0], "411")
        self.assertEqual(one_pending[0][1], sha_a)
        self.assertEqual(two_pending[0][0], "411")
        self.assertEqual(two_pending[0][1], sha_a,
                         "sha stays the first (landing) sha for callers")
        # Full list on the row — this is the return-shape widen.
        self.assertEqual(list(one_pending[0].shas), [sha_a])
        self.assertEqual(list(two_pending[0].shas), [sha_a, sha_b])
        self.assertEqual(len(two_pending[0].shas), 2)
        self.assertNotEqual(two_pending[0].shas[0], two_pending[0].shas[1])

        one_recs = watch.pending_handoff_records(one_text)
        two_recs = watch.pending_handoff_records(two_text)
        # Side by side: both surfaces keep pending[0]["sha"] as the first sha;
        # multi-sha also exposes the full list so the dashboard can read both.
        self.assertEqual(one_recs[0]["sha"], sha_a)
        self.assertEqual(one_recs[0]["shas"], [sha_a])
        self.assertEqual(two_recs[0]["sha"], sha_a)
        self.assertEqual(two_recs[0]["shas"], [sha_a, sha_b])
        self.assertEqual(two_recs[0]["id"], "411")

    def test_multi_sha_reaches_pending_not_malformed_via_real_parser(self):
        # Names the production decision: parse_handoffs classifies the line.
        # A green red-run with the narrow RE restored means this test is hollow.
        sha_a, sha_b = "aaaaaaaa", "bbbbbbbb"
        self.assertNotEqual(sha_a, sha_b)
        text = (
            "# Hand-offs\n\n## Pending\n\n"
            f"- **#5** · landed `{sha_a}` `{sha_b}` · 2026-07-28 09:40 · by "
            f"dreamer-5 — two commits\n"
            "\n## Folded\n"
        )
        pending, _folded, malformed = watch.parse_handoffs(text)
        self.assertEqual(malformed, [], malformed)
        self.assertEqual(len(pending), 1)
        self.assertEqual(list(pending[0].shas), [sha_a, sha_b])
        recs = watch.pending_handoff_records(text)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["shas"], [sha_a, sha_b])
        self.assertEqual(recs[0]["sha"], sha_a)


class TestHandoffFoldCorrelation(unittest.TestCase):
    """#409: correlate a fold by (id, sha), not id alone.

    A fold citing one sha used to silence EVERY pending under that id, so a
    second landing under the same id was suppressed by the first one's fold.
    The fix: a fold that cites a sha a pending landed consumes ONLY that sha;
    a fold whose cited shas match no pending (a merge commit, not the work
    sha) falls back to id-only, so a legitimately-folded hand-off cannot
    resurface — the fold-sha vocabulary is inconsistent by accident, not by
    contract, and the fallback is what keeps the fix from a regression.
    """

    def test_a_fold_citing_one_sha_keeps_the_other_landing_visible(self):
        # The live #401 shape is the fixture: pending twice (audit + fix
        # halves) and folded once citing the audit sha. Both pending shas and
        # the fold's cited sha are derived at runtime from the live file — a
        # literal tuned to today's file is an expiry date (#409).
        path = os.path.join(".dreamwork", "handoffs.md")
        self.assertTrue(os.path.exists(path),
                        "precondition: live handoffs.md must exist (#409)")
        with open(path) as f:
            text = f.read()
        pending, _folded, _mal = watch.parse_handoffs(text)
        shas = [row.sha for row in pending if row.id == "401"]
        self.assertEqual(len(shas), 2,
                         "precondition: #401 lands twice (audit + fix halves)")
        self.assertNotEqual(shas[0], shas[1],
                            "precondition: the two #401 landings must differ")
        fold_line = next((ln for ln in text.splitlines()
                          if "→ folded" in ln and "**#401**" in ln), "")
        cited = set(re.findall(r"`([0-9a-f]{7,40})`", fold_line))
        folded_half = [s for s in shas if s in cited]
        open_half = [s for s in shas if s not in cited]
        self.assertEqual(len(folded_half), 1,
                         "precondition: the fold cites exactly one #401 sha")
        self.assertEqual(len(open_half), 1)
        # THE defect: id-only correlation hid BOTH halves, so rec_shas was
        # empty. Reinstate `if row.id in folded_ids: continue` and this reds.
        recs = watch.pending_handoff_records(text)
        rec_shas = {r["sha"] for r in recs if r["id"] == "401"}
        self.assertIn(open_half[0], rec_shas,
                      "the unfolded #401 half must stay visible (#409)")
        self.assertNotIn(folded_half[0], rec_shas,
                         "the folded #401 half stays consumed")

    def test_a_merge_sha_fold_does_not_resurface_a_consumed_handoff(self):
        # The fallback the fix depends on. Most folds cite the MERGE commit
        # (`merged \`X\``), not the work sha a pending landed; a fold whose
        # cited shas match no pending must fall back to id-only, or the #409
        # fix resurfaces every legitimately-folded hand-off in the file.
        sha_work = "a1b2c3d"     # what the pending landed
        sha_merge = "e5f6a7b"    # the coordinator's merge commit (differs)
        self.assertNotEqual(sha_work, sha_merge)
        text = (
            "# Hand-offs\n\n## Folded\n\n"
            f"- **#5** → folded (2026-07-29 10:00): merged `{sha_merge}`\n"
            "\n## Pending\n\n"
            f"- **#5** · landed `{sha_work}` · 2026-07-29 09:50 · by x — y\n"
        )
        recs = watch.pending_handoff_records(text)
        self.assertEqual([r["id"] for r in recs], [],
                         "a merge-sha fold matching no pending falls back to "
                         "id-only — the hand-off stays consumed")


class TestSkillIdentity(unittest.TestCase):
    """#426 — the identity signal a running agent reads to tell its own tree moved.

    Two independent facts (the same two-question discipline as deploy_state):
    `commit` (short HEAD sha of the SKILL tree, where watch.py lives) and
    `skill_version` (the latest migration filename, which IS the skill's version
    per migrations/README.md). A running agent records these at start and
    compares at increment boundaries; on a skill_version delta it reads the
    intervening migrations before the next increment.

    The function reads the SKILL tree (where watch.py lives), never the target —
    the target is somebody's project, and its git identity is a different
    question (answered by serving_report). Design:
    `.dreamwork/docs/reload-signal-design.md`.
    """

    def _skill_dir(self):
        return os.path.dirname(os.path.abspath(watch.__file__))

    def test_returns_both_keys_and_never_raises(self):
        # the shape: both keys present, values are str-or-None. Never raises,
        # because this rides /data.json and a crash takes the page down.
        ident = watch.skill_identity()
        self.assertIsInstance(ident, dict)
        self.assertEqual(set(ident), {"commit", "skill_version"})
        for k in ("commit", "skill_version"):
            v = ident[k]
            self.assertTrue(
                v is None or (isinstance(v, str) and len(v) > 0),
                f"{k} must be a non-empty str or None, got {v!r}")

    def test_commit_and_skill_version_match_the_skill_tree_at_runtime(self):
        # PRECONDITION (asserted, not assumed): the skill dir is a git checkout
        # AND carries migrations/. Without both, this check is hollow — a None
        # return is the right answer for a deployed snapshot (no checkout, no
        # migrations), and asserting non-None there would be a check with an
        # invisible expiry. Derive both expected values at runtime so a literal
        # tuned to today's tree cannot pass.
        import subprocess
        skill_dir = self._skill_dir()
        migrations = os.path.join(skill_dir, "migrations")
        # assert the precondition the check depends on
        self.assertTrue(
            os.path.exists(os.path.join(skill_dir, ".git")) or
            subprocess.run(["git", "-C", skill_dir, "rev-parse", "--is-inside-work-tree"],
                           capture_output=True).returncode == 0,
            "skill dir is not a checkout — commit check is hollow against this tree")
        names = [f for f in os.listdir(migrations)
                 if f.endswith(".md") and f != "README.md"] if os.path.isdir(migrations) else []
        self.assertTrue(names, "no migrations on disk — skill_version check is hollow")

        ident = watch.skill_identity()

        # expected commit: short HEAD sha of the skill tree, derived independently
        expected_commit = subprocess.run(
            ["git", "--no-optional-locks", "-C", skill_dir, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True).stdout.strip()
        self.assertTrue(expected_commit, "could not derive expected commit — check is hollow")
        self.assertEqual(ident["commit"], expected_commit)

        # expected skill_version: latest migration by lexicographic sort (README protocol)
        expected_version = max(names)
        self.assertEqual(ident["skill_version"], expected_version)
        # the two values differ in form (sha vs filename) — assert they are not
        # accidentally the same string, which would mean the function conflated them
        self.assertNotEqual(ident["commit"], ident["skill_version"],
                            "commit and skill_version collapsed to one value")

    def test_collect_exposes_skill_identity(self):
        # rides /data.json and the /mtime poll, so an open page and a running
        # agent converge on the same identity without a new channel.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            data = watch.collect(d)
            self.assertIn("skill_identity", data)
            ident = data["skill_identity"]
            self.assertIsInstance(ident, dict)
            # the target is a temp dir (not the skill tree), but identity reads
            # the skill tree, so both keys must be populated here
            self.assertIsNotNone(ident.get("commit"))
            self.assertIsNotNone(ident.get("skill_version"))


class TestDeployRefusalCopy(unittest.TestCase):
    """#462 — the two ways /deploy refuses must be distinguishable to the reader.

    Both are `domain_invalid` because REJECTION_REASONS is a three-wide
    contract, so before this the page said "the value was not one the server
    accepts" for BOTH — for a deploy already running, and for a request from
    another machine. Those are the only two refusals he can provoke, so the
    generic copy was wrong 100% of the time it appeared.

    The fix adds an OPTIONAL `detail` beside the reason. This class exists to
    hold the line that it stays optional and additive: widening the closed set
    would change the journal contract, which is not what this increment is for.
    """

    def test_the_closed_set_of_reasons_is_unchanged(self):
        """Precondition, and the constraint: `detail` must NOT have widened the
        contract. Production line: REJECTION_REASONS. If a later change adds a
        reason here, that is a contract change and it needs its own migration —
        this test is where it gets noticed.
        """
        from user_events.sqlite import REJECTION_REASONS
        self.assertEqual(
            tuple(REJECTION_REASONS),
            ("malformed_json", "schema_invalid", "domain_invalid"))

    def test_reject_omits_detail_when_none_is_given(self):
        """Production line: the `if detail:` guard in _reject. Every other route
        must keep its body byte-for-byte, or this "additive" change is not.
        """
        import inspect
        src = inspect.getsource(watch.make_handler)
        self.assertIn('body = {"ok": False, "rejected": True, "reason": reason_code}', src)
        self.assertIn('if detail:', src)
        self.assertIn('body["detail"] = detail', src)

    def test_the_two_deploy_refusals_carry_different_details(self):
        """Production lines: the two `_reject("domain_invalid", …)` calls in
        _handle_deploy. Reversing or merging them reds this.
        """
        import inspect, re
        src = inspect.getsource(watch.make_handler)
        body = src[src.index("def _handle_deploy"):]
        body = body[:body.index("WRITE_ROUTE_HANDLERS")]
        details = re.findall(r'_reject\("domain_invalid",\s*"(\w+)"\)', body)
        # Derived precondition: two refusals exist AND they differ. A literal
        # pair would keep passing if one were changed to match the other.
        self.assertEqual(len(details), 2, details)
        self.assertNotEqual(details[0], details[1], details)
        self.assertEqual(set(details), {"not_local", "in_flight"})

    def test_the_page_names_each_refusal_in_his_voice(self):
        """Production lines: DEPLOY_WHY and the `in_flight` branch of the note.
        Also holds the dead branch deleted: since the 202 cutover a refusal is
        202+rejected, never 403, so a 403 test could never fire.
        """
        page = watch.PAGE
        self.assertIn("const DEPLOY_WHY = {", page)
        self.assertIn("this page will pick up the new one when it lands", page)
        self.assertIn("the update only runs from the machine serving the page", page)
        self.assertIn("already updating —", page)
        # The dead 403 branch and its unreachable copy are gone.
        self.assertNotIn("deploy only runs from this machine", page)
        self.assertNotRegex(page, r"rv\.status === 403")
        # writeVerdict must carry detail through, or the copy can never select.
        self.assertRegex(page, r"detail:\s*\(j && j\.detail\)")


# ── #289 — review decisions on the watch dashboard ──────────────────────
# Three surfaces: the LEFT JOIN in list_reviews (data), the artifactRow
# render (JS, via node-eval), and the /decide POST handler (HTTP against a
# REAL temp store). Every check names the production line it targets so a
# revert fails the named test. Temp stores only — never the main checkout's
# live .dreamwork/ledger.sqlite3.

def _store_target(root):
    """A store-mode target: the .dreamwork skeleton + a seeded, cut-over
    ledger store (watermark present so source_of_truth=='store')."""
    make_target(root)
    dw = os.path.join(root, ".dreamwork")
    os.makedirs(os.path.join(dw, "review"), exist_ok=True)
    import ledger_store
    from ledger_parse import _WATERMARK_KEY
    store = ledger_store.open_store(watch.store_path(dw), seed_next_id=1)
    store.conn.execute(
        "INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",
        (_WATERMARK_KEY, "2026-07-30T00:00:00Z"))
    store.close()
    return dw


def _record_decision(dw, artifact, qtitle, decision):
    import ledger_store
    import ledger_write
    store = ledger_store.open_store(watch.store_path(dw))
    try:
        ledger_write.record_review_decision(
            store, artifact, qtitle, decision, actor="watch")
    finally:
        store.close()


def _review_artifact(rd, name, body="<p>x"):
    path = os.path.join(rd, name)
    with open(path, "w") as f:
        f.write("<!doctype html>" + body)
    return path


class TestReviewDecisionJoin(unittest.TestCase):
    """list_reviews LEFT JOINs review_decision (store-mode); degrades to
    decision=None ('unlinked') in markdown-mode and on rows with no record."""

    def test_join_carries_decision_and_question_title_per_row(self):
        with tempfile.TemporaryDirectory() as d:
            dw = _store_target(d)
            rd = os.path.join(dw, "review")
            _review_artifact(rd, "acc.html")
            _review_artifact(rd, "rej.html")
            _review_artifact(rd, "pen.html")
            _review_artifact(rd, "none.html")
            # PRODUCTION LINE: ledger_write.record_review_decision writes the
            # v2 row (artifact, question_title, decision, decided_at, actor).
            _record_decision(dw, "acc.html", "Q-accept", "accepted")
            _record_decision(dw, "rej.html", "Q-reject", "rejected")
            _record_decision(dw, "pen.html", "Q-pending", "pending")
            # Runtime precondition: the target really is store-mode, or the
            # join half of the check has no subject.
            self.assertEqual(watch.source_of_truth(dw), "store")
            rows = {r["name"]: r for r in watch.list_reviews(rd, dw)}
            self.assertEqual(rows["acc.html"]["decision"], "accepted")
            self.assertEqual(rows["acc.html"]["question_title"], "Q-accept")
            self.assertEqual(rows["rej.html"]["decision"], "rejected")
            self.assertEqual(rows["rej.html"]["question_title"], "Q-reject")
            self.assertEqual(rows["pen.html"]["decision"], "pending")
            self.assertEqual(rows["pen.html"]["question_title"], "Q-pending")
            # No row -> decision/question_title None (the 'unlinked' state).
            self.assertIsNone(rows["none.html"]["decision"])
            self.assertIsNone(rows["none.html"]["question_title"])

    def test_markdown_mode_degrades_to_unlinked_no_store(self):
        # A markdown-mode target (no cutover watermark) has NO decision data:
        # every row reads decision=None, which artifactRow renders as
        # 'unlinked' — distinct from 'pending' by contract.
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            dw = os.path.join(d, ".dreamwork")
            rd = os.path.join(dw, "review")
            os.makedirs(rd, exist_ok=True)
            _review_artifact(rd, "plain.html")
            # Precondition: genuinely markdown-mode (no store file).
            self.assertNotEqual(watch.source_of_truth(dw), "store")
            self.assertFalse(watch.store_path(dw).exists())
            rows = watch.list_reviews(rd, dw)
            self.assertEqual(len(rows), 1)
            self.assertIsNone(rows[0]["decision"])
            self.assertIsNone(rows[0]["question_title"])
            # _review_decisions returns {} wholesale in markdown-mode, so a
            # row can never accidentally read 'pending' from a missing store.
            self.assertEqual(watch._review_decisions(dw), {})

    def test_join_tolerates_a_missing_review_decision_table(self):
        # A store that has not yet been migrated to the v2 review_decision
        # shape must degrade (return {}), never crash collect().
        with tempfile.TemporaryDirectory() as d:
            dw = _store_target(d)
            rd = os.path.join(dw, "review")
            _review_artifact(rd, "x.html")
            import sqlite3
            # Drop the table to simulate a pre-v2 store; the read-only open
            # in _review_decisions must catch and degrade.
            conn = sqlite3.connect(str(watch.store_path(dw)))
            conn.execute("DROP TABLE IF EXISTS review_decision")
            conn.commit()
            conn.close()
            self.assertEqual(watch.source_of_truth(dw), "store")
            self.assertEqual(watch._review_decisions(dw), {})
            rows = watch.list_reviews(rd, dw)
            self.assertIsNone(rows[0]["decision"])


class TestArtifactRowRender(unittest.TestCase):
    """artifactRow (JS) renders the four decision states distinctly. Evaluated
    in node with stubbed esc/pipBtn so the assertion is on REAL rendered HTML,
    not the source text — reverting a branch changes the bytes it prints."""

    def _artifact_row_html(self, fixtures):
        page = watch._get_page()
        # Extract the function body by brace-matching from its signature.
        start = page.index("function artifactRow(")
        depth = 0
        end = None
        for i in range(start, len(page)):
            if page[i] == "{":
                depth += 1
            elif page[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        self.assertIsNotNone(end, "could not extract artifactRow from bundle")
        fn = page[start:end]
        script = (
            "const esc = t => String(t==null?'':t)"
            ".replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')"
            ".replace(/\"/g,'&quot;');\n"
            "const pipBtn = (url,label) => `<button data-pipurl=\"${esc(url)}\""
            " aria-label=\"pop out ${esc(label)}\">PIP</button>`;\n"
            + fn + "\n"
            "const fs = " + json.dumps(fixtures) + ";\n"
            "console.log(JSON.stringify(fs.map(r => artifactRow(r,'review'))));\n"
        )
        import subprocess
        proc = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True, timeout=10)
        if proc.returncode != 0:
            self.fail("node eval failed: " + proc.stderr)
        return json.loads(proc.stdout)

    def test_four_states_render_distinctly_and_unlinked_has_no_marker(self):
        # PRODUCTION LINE: artifactRow's `hasDec` gate. accepted/rejected/
        # pending get a `.rdecision` marker; unlinked (no decision) renders
        # NONE — absence is its own state, distinct from 'pending' by contract.
        fixtures = [
            {"name": "a.html", "decision": "accepted",
             "question_title": "Q1", "created_known": True, "created": 1,
             "mtime": 1, "show_modified": False},
            {"name": "r.html", "decision": "rejected",
             "question_title": "Q2", "created_known": True, "created": 1,
             "mtime": 1, "show_modified": False},
            {"name": "p.html", "decision": "pending",
             "question_title": "Q3", "created_known": True, "created": 1,
             "mtime": 1, "show_modified": False},
            {"name": "u.html", "decision": None, "question_title": None,
             "created_known": True, "created": 1, "mtime": 1,
             "show_modified": False},
        ]
        html = self._artifact_row_html(fixtures)
        by = dict(zip(["a", "r", "p", "u"], html))
        # data-decision carries all four.
        self.assertIn('data-decision="accepted"', by["a"])
        self.assertIn('data-decision="rejected"', by["r"])
        self.assertIn('data-decision="pending"', by["p"])
        self.assertIn('data-decision="unlinked"', by["u"])
        # accepted/rejected/pending each carry a marker; unlinked does NOT.
        self.assertIn("rdecision raccepted", by["a"])
        self.assertIn("rdecision rrejected", by["r"])
        self.assertIn("rdecision rpending", by["p"])
        self.assertNotIn("rdecision", by["u"],
                         "unlinked must render NO marker — its distinction "
                         "from pending. Reverting the hasDec gate breaks this.")
        # The marker links to /question?qid=<title> (a decision row always
        # carries question_title, NOT NULL by contract).
        self.assertIn('/question?qid=Q1', by["a"])
        self.assertIn('/question?qid=Q3', by["p"])

    def test_glyph_distinguishes_verdict_within_the_done_dim(self):
        # accepted ✔ and rejected ✘ both dim (done) but differ by glyph.
        fixtures = [
            {"name": "a.html", "decision": "accepted",
             "question_title": "Q", "created_known": True, "created": 1,
             "mtime": 1, "show_modified": False},
            {"name": "r.html", "decision": "rejected",
             "question_title": "Q", "created_known": True, "created": 1,
             "mtime": 1, "show_modified": False},
        ]
        html = self._artifact_row_html(fixtures)
        self.assertIn("\u2714", html[0])   # ✔
        self.assertIn("\u2718", html[1])   # ✘


class TestDecideHandler(unittest.TestCase):
    """/decide records a review decision; conflict and markdown-mode are
    readable refusals, not 500s. Drives the REAL handler over HTTP against a
    REAL temp store."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = self.tmp.name
        _store_target(self.target)  # store-mode, with a review dir
        probe = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)
        port = probe.server_address[1]
        probe.server_close()
        self.authority = watch.RequestAuthority(
            ["127.0.0.1"], port)
        self.server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", port),
            watch.make_handler(self.target, authority=self.authority))
        threading.Thread(target=self.server.serve_forever,
                         daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{port}"
        self.host = f"127.0.0.1:{port}"

    def _post(self, body):
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            self.base + "/decide", data=data,
            headers={"Host": self.host,
                     "Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return exc.code, json.loads(raw)
            except ValueError:
                return exc.code, raw

    def test_decide_happy_path_records_and_wakes(self):
        # PRODUCTION LINE: the handler calls
        # ledger_write.record_review_decision(store, artifact,
        # question_title, decision, actor=..., at=...) — the real signature.
        status, body = self._post({
            "artifact": "plan.html", "question_title": "ship it?",
            "decision": "accepted"})
        self.assertEqual(status, 202)
        self.assertTrue(body.get("ok"))
        self.assertEqual(body.get("decision"), "accepted")
        # The decision really landed in the store.
        dec = watch._review_decisions(os.path.join(self.target, ".dreamwork"))
        self.assertEqual(dec["plan.html"], ("accepted", "ship it?"))
        # It wakes the loop via watch-events.log (one event per line).
        with open(os.path.join(self.target, ".dreamwork",
                               "watch-events.log")) as f:
            line = f.read().strip()
        self.assertIn("review-decision", line)
        self.assertIn("plan.html", line)
        self.assertIn("accepted", line)

    def test_decide_conflict_is_a_readable_refusal_not_500(self):
        # PRODUCTION LINE: ledger_write.DecisionConflict is caught and surfaced
        # as a durable rejected receipt (domain_invalid/decision_conflict),
        # never a 500. A final decision is not silently reassignable.
        self._post({"artifact": "d.html", "question_title": "Q1",
                    "decision": "accepted"})
        status, body = self._post({"artifact": "d.html",
                                   "question_title": "Q2",
                                   "decision": "rejected"})
        self.assertEqual(status, 202)
        self.assertFalse(body.get("ok"))
        self.assertTrue(body.get("rejected"))
        self.assertEqual(body.get("reason"), "domain_invalid")
        self.assertEqual(body.get("detail"), "decision_conflict")
        # The first decision is untouched (not silently reassigned).
        dec = watch._review_decisions(os.path.join(self.target, ".dreamwork"))
        self.assertEqual(dec["d.html"], ("accepted", "Q1"))

    def test_decide_markdown_mode_refuses_not_500(self):
        # A markdown-mode target (no store) refuses with domain_invalid/
        # no_store, never a 500. The read join already degrades to 'unlinked'
        # there, so refusing the write is the honest counterpart.
        with tempfile.TemporaryDirectory() as md:
            make_target(md)
            probe = http.server.ThreadingHTTPServer(
                ("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)
            port = probe.server_address[1]
            probe.server_close()
            server = http.server.ThreadingHTTPServer(
                ("127.0.0.1", port),
                watch.make_handler(md, authority=watch.RequestAuthority(
                    ["127.0.0.1"], port)))
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            try:
                base = f"http://127.0.0.1:{port}"
                host = f"127.0.0.1:{port}"
                data = json.dumps({"artifact": "x.html",
                                   "question_title": "Q",
                                   "decision": "accepted"}).encode()
                req = urllib.request.Request(
                    base + "/decide", data=data,
                    headers={"Host": host,
                             "Content-Type": "application/json"},
                    method="POST")
                with urllib.request.urlopen(req, timeout=5) as r:
                    status, body = r.status, json.loads(r.read())
                self.assertEqual(status, 202)
                self.assertTrue(body.get("rejected"))
                self.assertEqual(body.get("detail"), "no_store")
            finally:
                server.shutdown()
                server.server_close()

    def test_decide_rejects_bad_decision_and_missing_fields(self):
        for body in (
            {"artifact": "x.html", "question_title": "Q",
             "decision": "maybe"},
            {"artifact": "", "question_title": "Q",
             "decision": "accepted"},
            {"artifact": "x.html", "decision": "accepted"},
        ):
            status, resp = self._post(body)
            self.assertEqual(status, 202, body)
            self.assertTrue(resp.get("rejected"), body)
            self.assertEqual(resp.get("reason"), "schema_invalid", body)
