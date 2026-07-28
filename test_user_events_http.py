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

import contextlib
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

    # Production default: the journal shadows every write. E2's baseline run
    # disables it to capture the pre-journal observable behaviour.
    journal_shadow = True

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
            watch.make_handler(self.target, authority=self.authority,
                               journal_shadow=self.journal_shadow))
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
        # above for the wrong reason. Status is 202 post-cutover (E3).
        status, _, _ = self.post(
            "/command", {"kind": "add-idea", "text": "complete body idea"})
        self.assertEqual(status, 202)
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


class E2Shadow(HttpHarness):
    """E2: every write route commits a shadow receipt, observable behaviour
    unchanged.

    The journal is the shadow (journal-shadow phase): a receipt is committed on
    every write request while the response, status code, submissions.log and
    every handler are identical to a baseline captured with the journal
    disabled. The route list is derived from watch.py's dispatch, not
    hand-copied, so a seventh route fails this test instead of slipping past.

    Red line: the `journal.receive(...)` call in do_POST (reached via
    _journal_receive)."""

    # The payloads that make each route return 200. /answer and /comment need a
    # matching question title, so run_all first /asks one and reuses its title.
    # /run-mode's first POST to a fresh target always changes the mode (the
    # default is lackadaisical), so it returns changed=True.
    def run_all_routes(self):
        """POST every write route once; return (statuses, submissions_rows).

        /answer and /comment match a title in questions.md; the fixture seeds
        one (`A real open question?`) so they fold against it. The exact text
        varies per call so each receipt's body differs (no accidental dedup).
        """
        import uuid as _uuid
        marker = _uuid.uuid4().hex[:8]
        statuses = []
        # 1. /ask — records a new question for the dreamer (answers.md).
        statuses.append(self.post(
            "/ask", {"question": f"E2 shadow question {marker}"})[0])
        # 2. /comment — note on the fixture's OPEN question (before /answer
        #    moves it to Answered, so the Open-section match still finds it).
        statuses.append(self.post(
            "/comment", {"question": "A real open question?",
                         "comment": f"note {marker}",
                         "section": "Open"})[0])
        # 3. /answer — fold the fixture's open question (moves to Answered).
        statuses.append(self.post(
            "/answer",
            {"question": "A real open question?",
             "answer": f"ans {marker}"})[0])
        # 4. /command — a valid command kind.
        statuses.append(self.post(
            "/command", {"kind": "add-idea", "text": f"idea {marker}"})[0])
        # 5. /tint — a valid tint name.
        statuses.append(self.post("/tint", {"tint": "indigo"})[0])
        # 6. /run-mode — a different mode than the default.
        statuses.append(self.post("/run-mode", {"mode": "hot"})[0])
        return statuses, self.submissions_rows()

    def test_every_write_route_commits_a_receipt_and_changes_nothing_else(self):
        # Run the six routes with the journal ON (this harness) and OFF
        # (baseline), each on a fresh target, and compare everything
        # observable except the receipt count.
        on_statuses, on_subs = self.run_all_routes()
        with self._baseline_server() as baseline:
            off_statuses, off_subs = baseline.run_all_routes()
        # The route list is derived from the dispatch, not hand-copied: assert
        # its length matches the routes we exercised (six), so a seventh route
        # added to WRITE_ROUTE_HANDLERS without a payload here fails loudly.
        self.assertEqual(len(WRITE_ROUTES), 6, WRITE_ROUTES)
        # Every route returned 202 with the journal ON (E3 cutover moved the
        # write-route status) and 200 with the journal OFF (the pre-cutover
        # baseline, which still uses _send). The shadow must change only the
        # receipt count and the status code, nothing else.
        self.assertEqual(on_statuses, [202] * len(WRITE_ROUTES), on_statuses)
        self.assertEqual(off_statuses, [200] * len(WRITE_ROUTES), off_statuses)
        # submissions.log is identical between the two runs (the journal adds a
        # receipt, not a submissions.log line). Compare the fields that are
        # stable across runs (path + whether parsed); timestamps differ.
        self.assertEqual(
            [r["path"] for r in on_subs],
            [r["path"] for r in off_subs])
        self.assertEqual(
            [("req" in r) for r in on_subs],
            [("req" in r) for r in off_subs])
        # The discriminating half: with the journal ON, there is exactly one
        # receipt per route. Derived from the route count, never a literal.
        self.assertEqual(self.receipt_count(), len(WRITE_ROUTES))

    def test_a_seventh_route_would_fail_this_test_not_slip_past(self):
        # The precondition the "derived route list" claim depends on: the
        # dispatch table IS the six routes we exercise. If a route is added to
        # WRITE_ROUTE_HANDLERS, run_all_routes does not POST it, so the receipt
        # count assertion above (len(WRITE_ROUTES)) would still pass while a
        # route went unshadowed — UNLESS this guard fails first. This is the
        # plan's "derive the route list" discipline made executable.
        exercised = 6  # ask, answer, comment, command, tint, run-mode
        self.assertEqual(len(WRITE_ROUTES), exercised, WRITE_ROUTES)

    @contextlib.contextmanager
    def _baseline_server(self):
        """A second harness with the journal disabled, for the E2 baseline."""
        baseline = _BaselineHarness()
        baseline.setUp()
        try:
            yield baseline
        finally:
            baseline.doCleanups()


class E3Cutover(HttpHarness):
    """E3: the journal commit, not the handler, authorises the response.

    A committed write route returns 202 + `Location: /user-events/<id>` + the
    receipt identity (id/sequence/digest) in the body, and the named receipt
    is `get()`-able from the journal (a hardcoded 202 fails). A same-UUID retry
    returns one receipt and the same Location. A journal open/commit failure
    returns no 202 (503), at a real seam (chmod 0500 parent), no mocking.

    Red lines: the `send_response(202)` in _send_receipt, and separately the
    `if ... is None: 503` guard in do_POST."""

    def _post_command(self, *, client_action_id):
        return self.post("/command",
                         {"kind": "add-idea", "text": "cutover idea"},
                         client_action_id=client_action_id)

    def test_202_names_a_receipt_that_exists(self):
        # (a) parse the body, get() that id from the journal; a hardcoded 202
        # with a fabricated id fails the get().
        status, headers, body = self._post_command(
            client_action_id="e3-a-receipt-exists")
        self.assertEqual(status, 202)
        location = headers.get("Location")
        self.assertIsNotNone(location, headers)
        payload = json.loads(body)
        receipt = payload["receipt"]
        rid = receipt["receipt_id"]
        # The Location header names the same receipt id as the body.
        self.assertEqual(location, f"/user-events/{rid}")
        # The discriminating half: that receipt really exists in the journal.
        # A hardcoded 202 mints an id that get() cannot find.
        with open_journal(self._journal_path()) as j:
            row = j.get_receipt(rid)
        self.assertIsNotNone(row, rid)
        self.assertEqual(row["receipt_id"], rid)
        # sequence/digest in the body match the journal's row.
        self.assertEqual(receipt["sequence"], row["sequence"])
        self.assertEqual(receipt["request_digest"], row["request_digest"])

    def test_retry_of_the_same_uuid_returns_one_receipt_and_the_same_location(self):
        # (b) idempotency: a same-UUID retry returns one receipt and the same
        # Location. The journal dedupes same UUID+digest.
        s1, h1, b1 = self._post_command(client_action_id="e3-b-retry")
        s2, h2, b2 = self._post_command(client_action_id="e3-b-retry")
        self.assertEqual(s1, 202)
        self.assertEqual(s2, 202)
        self.assertEqual(h1["Location"], h2["Location"])
        self.assertEqual(
            json.loads(b1)["receipt"]["receipt_id"],
            json.loads(b2)["receipt"]["receipt_id"])
        # Exactly one receipt for the two retries — derived, not a literal.
        self.assertEqual(self.receipt_count(), 1)

    def test_no_202_when_the_journal_cannot_commit(self):
        # (c) journal path in a directory chmod 0500 before start, so the open
        # genuinely fails. No 202, no receipt. NO MOCKING of sqlite3.connect:
        # real permissions, real failure. (Plan's "must not fake" clause.)
        # Run in a subprocess-free way: a fresh target whose .dreamwork is
        # read-only, so open_journal's parent-create / sqlite open fails.
        import os as _os
        import shutil as _shutil
        ro_target = _make_target(_os.path.join(self.tmp.name, "readonly"))
        dw = _os.path.join(ro_target, ".dreamwork")
        _os.chmod(dw, 0o500)
        try:
            port_probe = http.server.ThreadingHTTPServer(
                ("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)
            rport = port_probe.server_address[1]
            port_probe.server_close()
            rauth = watch.RequestAuthority(["allowed.test", "127.0.0.1"], rport)
            rserver = http.server.ThreadingHTTPServer(
                ("127.0.0.1", rport),
                watch.make_handler(ro_target, authority=rauth))
            threading.Thread(target=rserver.serve_forever,
                             daemon=True).start()
            try:
                base = f"http://127.0.0.1:{rport}"
                host = f"allowed.test:{rport}"
                body = json.dumps(
                    {"kind": "add-idea", "text": "should not commit"}).encode()
                req = urllib.request.Request(
                    f"{base}/command", data=body,
                    headers={"Host": host, "Origin": f"http://{host}",
                             "Content-Type": "application/json"},
                    method="POST")
                try:
                    urllib.request.urlopen(req, timeout=5)
                    status = 202  # should not reach here
                except urllib.error.HTTPError as exc:
                    status = exc.code
                # No 202: the journal could not commit, so no receipt
                # authorises the response. 503 is the contract-level failure.
                self.assertNotEqual(status, 202)
            finally:
                rserver.shutdown()
                rserver.server_close()
        finally:
            _os.chmod(dw, 0o700)


class _BaselineHarness(E2Shadow):
    """Same harness, journal disabled — the pre-journal observable baseline.

    Not a test target: it exists only to run the six routes against a
    journal-off server inside E2's comparison. `__test__ = False` stops
    unittest from collecting the inherited E2 tests against it (they would
    fail on the receipt count, which is the point of the baseline)."""
    __test__ = False
    journal_shadow = False


if __name__ == "__main__":
    unittest.main()
