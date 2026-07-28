#!/usr/bin/env python3
"""Red-first tests for the HTTP half of the durable user-event journal.

Lane E of #263 (`user-event-journal-implementation.md` §"Lane E — HTTP"):
increments 20 (E1 envelope), 21 (E2 shadow), 22 (E3 cutover). Kept separate
from `test_watch.py` so lane E's tests do not contend with the dashboard
dreamers' tests (plan §"Dependency order and lanes").

Harness: a real `http.server.ThreadingHTTPServer` bound to a reserved port,
reusing the port discipline of `TestRequestAuthorityHTTP` in `test_watch.py`
(E1 must reach the real `do_POST`, not a stub).

Why a raw socket for the interrupted body: `urllib` always sends a complete
body, so a `urllib` test with a short `Content-Length` header tests the
library and passes with the receipt gate absent — the #320 fixture trap. A
raw socket sends exactly the bytes we tell it to.
"""

import http.server
import json
import os
import socket
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import watch
from user_events.sqlite import open_journal

# The six write routes `do_POST` dispatches, derived from the dispatch itself
# (the Handler class's WRITE_ROUTE_HANDLERS keys) so a seventh route added
# later fails E2 instead of slipping past it — exactly the discipline the
# plan's "must not fake" clause demands. Built fresh from make_handler so the
# test never holds a hand-copied list.
_HANDLER_CLS = watch.make_handler("/unused-e2e-route-derivation",
                                   authority=watch.RequestAuthority(
                                       ["127.0.0.1"], 9))
WRITE_ROUTES = tuple(_HANDLER_CLS.WRITE_ROUTE_HANDLERS.keys())

QUESTIONS = """# Questions for the human

## Open

- **A real open question?** context here.
- not a question bullet

## Answered

- **Old one** -> resolved.
"""


def _make_target(root):
    """Mirror test_watch.make_target's layout (answers.md, questions.md, ...)."""
    dw = os.path.join(root, ".dreamwork")
    os.makedirs(os.path.join(dw, "dreams", "archive"))
    os.makedirs(os.path.join(dw, "docs"))
    with open(os.path.join(root, "DREAMWORK.md"), "w") as f:
        f.write("# DREAMWORK\n")
    with open(os.path.join(dw, "dreams", "2026-01-01-x.md"), "w") as f:
        f.write("dream body\n")
    with open(os.path.join(dw, "questions.md"), "w") as f:
        f.write(QUESTIONS)
    with open(os.path.join(dw, "lessons.md"), "w") as f:
        f.write("# Lessons\n")
    with open(os.path.join(dw, "skill-version"), "w") as f:
        f.write("2026-07-25-x.md\n")
    return root


class HttpHarness(unittest.TestCase):
    """Real server on a reserved port; helpers for urllib and raw-socket POSTs."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = _make_target(self.tmp.name)
        # Reserve a real port, then bind the tested server to it so the
        # authority checks the actual port its Host header must carry.
        probe = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)
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

    # --- urllib path (complete bodies) ---
    def post(self, path, data, *, client_action_id=None):
        body = json.dumps(data).encode()
        headers = {"Host": self.host,
                   "Origin": f"http://{self.host}",
                   "Content-Type": "application/json"}
        if client_action_id is not None:
            headers["X-Client-Action-Id"] = client_action_id
        req = urllib.request.Request(self.base + path, data=body,
                                     headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, dict(response.headers), response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()

    # --- raw-socket path (can send a deliberately short body) ---
    def raw_post(self, path, body_bytes, *, content_length=None, ctype=None):
        """Send one POST over a raw socket, read the full response.

        `content_length` defaults to len(body_bytes). Setting it higher than
        the bytes actually sent is how an interrupted body is expressed: the
        server is promised N bytes, receives fewer, and the connection closes.
        """
        cl = content_length if content_length is not None else len(body_bytes)
        ctype = ctype or "application/json"
        request = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: {self.host}\r\n"
            f"Origin: http://{self.host}\r\n"
            f"Content-Type: {ctype}\r\n"
            f"Content-Length: {cl}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode() + body_bytes
        with socket.create_connection(("127.0.0.1", self.base.rsplit(":", 1)[1]),
                                       timeout=5) as sock:
            sock.sendall(request)
            # Half-close the WRITE side so the server sees EOF: a short body
            # is only detectable when the read returns fewer bytes than the
            # promised Content-Length, which needs the peer to stop sending.
            # Closing the whole socket would also drop the unread response.
            sock.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                chunks.append(data)
        return b"".join(chunks)

    def _journal_path(self):
        return os.path.join(self.target, ".dreamwork", watch.JOURNAL_FILENAME)

    def receipt_count(self):
        if not os.path.exists(self._journal_path()):
            return 0
        with open_journal(self._journal_path()) as j:
            return j.receipt_count()

    def submissions_rows(self):
        path = os.path.join(self.target, ".dreamwork", "submissions.log")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]


class E1Envelope(HttpHarness):
    """E1: transport-envelope failures decided before receipt; interrupted body
    creates none.

    Red line: the `if short:` gate in `do_POST` that skips the journal
    receipt. The plan's original red line (a `len(body) != nbytes` check)
    already exists from the #371 incomplete-witness work, so it is NOT
    discriminating — see the amended plan row. The gate is."""

    def test_an_interrupted_body_creates_no_receipt(self):
        # A raw socket: promise 500 bytes, send 100, close. urllib cannot
        # express this (it always sends a complete body), so a urllib version
        # of this test would pass with the gate absent — the #320 trap.
        promised, sent = 500, 100
        # Assert the precondition the test depends on: a real interruption,
        # not a complete body mislabelled as one.
        self.assertGreater(promised, sent)
        response = self.raw_post(
            "/command", b"x" * sent, content_length=promised)
        status_line = response.split(b"\r\n", 1)[0]
        # The interrupted body is a transport-envelope failure: 400, and no
        # journal receipt.
        self.assertIn(b"400", status_line, status_line)
        self.assertEqual(self.receipt_count(), 0)

    def test_a_complete_body_still_creates_a_receipt(self):
        # The positive half: a complete, well-formed body DOES create a
        # receipt. Without this, `return`-without-receipt would pass the test
        # above for the wrong reason.
        status, _, _ = self.post(
            "/command", {"kind": "add-idea", "text": "complete body idea"})
        self.assertEqual(status, 200)
        self.assertEqual(self.receipt_count(), 1)

    def test_an_interrupted_body_is_still_witnessed_incomplete(self):
        # The incomplete-witness amendment (his 05:43 ruling, law 2): the
        # partial bytes are kept in submissions.log marked incomplete, so
        # tightening receipt semantics never reduces recoverability.
        promised, sent = 500, 100
        self.raw_post("/command", b"y" * sent, content_length=promised)
        rows = self.submissions_rows()
        self.assertEqual(len(rows), 1)
        # The precondition: the witness honestly marks it short.
        self.assertTrue(rows[0].get("short"), rows[0])
        self.assertEqual(rows[0].get("got"), sent)
        self.assertEqual(rows[0].get("bytes"), promised)


if __name__ == "__main__":
    unittest.main()
