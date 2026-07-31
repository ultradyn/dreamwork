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

import lint
import watch
from user_events.sqlite import open_journal, RECEIPT_HEALTH, REJECTION_REASONS

# The write routes `do_POST` dispatches, derived from the dispatch itself
# (the Handler class's WRITE_ROUTE_HANDLERS keys) so a new route added later
# fails E2 instead of slipping past it — exactly the discipline the plan's
# "must not fake" clause demands. Built fresh from make_handler so the test
# never holds a hand-copied list.
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
        # #462 /deploy must never run the real recipe in a unit check.
        watch._deploy_runner = lambda _t: None
        watch._deploy_inflight = False
        self.addCleanup(lambda: setattr(watch, "_deploy_runner", None))
        self.addCleanup(lambda: setattr(watch, "_deploy_inflight", False))
        # #551 /remind appends to the coordinator inbox via relay; redirect it
        # to a temp dir so E2's run-all-routes never writes the real shared
        # inbox. _BaselineHarness inherits this setUp, so the journal-off run
        # is redirected too.
        watch._remind_inbox_dir = os.path.join(self.tmp.name, "remind-inbox")
        self.addCleanup(lambda: setattr(watch, "_remind_inbox_dir", None))
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

    def test_an_interrupted_body_proceeds_and_creates_a_receipt(self):
        # His 05:43 ruling (law 2, #371): an interrupted body is KEPT as a
        # partial witness marked incomplete and ALLOWED TO PROCEED — it is
        # no longer refused as a transport-envelope failure. So: 202 (the
        # durable received path answers, never a transport 400), and the
        # envelope claims a journal receipt like any registered envelope.
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
        self.assertIn(b"202", status_line, status_line)
        self.assertNotIn(b"400", status_line, status_line)
        self.assertEqual(self.receipt_count(), 1)

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
    hand-copied, so a new route fails this test instead of slipping past.

    Red line: the `journal.receive(...)` call in do_POST (reached via
    _journal_receive)."""

    # The payloads that make each route return 200. /answer and /comment need a
    # matching question title, so run_all first /asks one and reuses its title.
    # /run-mode's first POST to a fresh target always changes the mode (the
    # default is lackadaisical), so it returns changed=True.
    # /deploy's runner is faked in HttpHarness.setUp — never `just deploy`.
    # /chat-reply needs an EXISTING chat, so run_all seeds one through the ONE
    # production writer before it posts (see step 11 for why a bogus id would
    # slip past every assertion in this class).
    def run_all_routes(self):
        """POST every write route once; return (statuses, submissions_rows).

        /answer and /comment match a title in questions.md; the fixture seeds
        one (`A real open question?`) so they fold against it. The exact text
        varies per call so each receipt's body differs (no accidental dedup).
        """
        import uuid as _uuid
        import ledger_store
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
        # 7. /posture — a three-axis triple (#445). Deliberately a pace other
        #    than the one step 6 just derived from run-mode `hot`, so the
        #    changed branch (the one that writes and emits) is what gets
        #    shadowed, not the silent identical-final early return.
        #    The precondition that makes those literals meaningful: they must
        #    be members of the closed sets the handler validates against, or
        #    this route 400s and the receipt it should have committed never
        #    exists — a renamed stop would otherwise turn this into a test of
        #    the rejection path wearing the name of the write path.
        self.assertIn("steady", lint.POSTURE_STOPS_PACE)
        self.assertIn("inform", lint.POSTURE_STOPS_ASKING)
        statuses.append(self.post(
            "/posture", {"pace": "steady", "asking": "inform",
                         "delegation": 1})[0])
        # 8. /decide — review decision (#289). The fixture is markdown-mode
        #    (no store), so this reaches the domain_invalid refusal — which is
        #    still a durable receipt (202 on / 200 off, same as every other
        #    route). The payload passes schema so the refusal is the honest
        #    "no store" one, not a schema_invalid that never reaches the domain
        #    check. The closed set the handler validates against: assert it so
        #    a renamed decision would turn this into a schema rejection wearing
        #    the domain path's name.
        self.assertIn("accepted", ledger_store.REVIEW_DECISIONS)
        statuses.append(self.post(
            "/decide", {"artifact": f"artifact-{marker}",
                        "question_title": "A real open question?",
                        "decision": "accepted"})[0])
        # 9. /deploy — page-triggered just deploy (#462); runner faked.
        statuses.append(self.post("/deploy", {})[0])
        # 10. /remind — send the resolved posture to the coordinator inbox
        #     (#551); relay redirected to a temp dir in setUp. Empty {} body
        #     is the normal press.
        statuses.append(self.post("/remind", {})[0])
        # 11. /chat-reply — continue an EXISTING chat (#577). Its existence
        #     guard runs BEFORE apply, so an unknown id is a domain_invalid
        #     refusal — and a refusal still commits a receipt and answers
        #     202 on / 200 off, exactly like the write path. So a bogus id
        #     here would sail past this class's status AND receipt-count
        #     assertions while never once exercising the write path — the
        #     same trap the /decide and /posture assertIns above guard
        #     against. Measured, not assumed (#586): with the id bogus and
        #     the post-condition below deleted, all 15 tests in this module
        #     pass. Hence: seed a real chat through the
        #     ONE production writer — apply_chat_turn, the same call the
        #     handler makes — assert the precondition the write path needs,
        #     and assert afterwards that the reply actually landed as a
        #     turn. The seed is a direct writer call, not a POST, so it adds
        #     no receipt and no submissions row to either run.
        cid = f"e2-chat-{marker}"
        self.assertTrue(
            watch.apply_chat_turn(self.target, cid, "human", f"seed {marker}"))
        self.assertTrue(watch._chat_exists(self.target, cid))
        reply = f"reply {marker}"
        statuses.append(self.post("/chat-reply", {"id": cid,
                                                  "text": reply})[0])
        self.assertIn(reply, watch.read_text(os.path.join(
            self.target, ".dreamwork", watch.CHAT_DIR, cid,
            "transcript.md")))
        return statuses, self.submissions_rows()

    def test_every_write_route_commits_a_receipt_and_changes_nothing_else(self):
        # Run every write route with the journal ON (this harness) and OFF
        # (baseline), each on a fresh target, and compare everything
        # observable except the receipt count.
        on_statuses, on_subs = self.run_all_routes()
        with self._baseline_server() as baseline:
            off_statuses, off_subs = baseline.run_all_routes()
        # The route list is derived from the dispatch, not hand-copied: assert
        # its length matches the routes we exercised, so a new route added to
        # WRITE_ROUTE_HANDLERS without a payload here fails loudly. This literal
        # is a deliberate alarm — do NOT derive it from WRITE_ROUTE_HANDLERS
        # (that would be `len(table) == len(table)`, a check born hollow: the
        # repo has a documented lesson about exactly that shape). Bump it
        # consciously when extending run_all_routes, and say why here.
        # 2026-07-30 #496: 8→9 — /decide (#289) joined /deploy (#462) in the
        # dispatch; both needed payloads in run_all_routes.
        # 2026-07-30 #551: 9→10 — /remind joined the dispatch; empty-body press.
        # 2026-07-31 #586: 10→11 — /chat-reply (#577) joined the dispatch;
        # payload is {"id", "text"} against a chat run_all seeds first via
        # apply_chat_turn, because the route refuses an id that does not
        # already exist.
        self.assertEqual(len(WRITE_ROUTES), 11, WRITE_ROUTES)
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

    def test_a_new_route_would_fail_this_test_not_slip_past(self):
        # The precondition the "derived route list" claim depends on: the
        # dispatch table IS the routes we exercise. If a route is added to
        # WRITE_ROUTE_HANDLERS, run_all_routes does not POST it, so the receipt
        # count assertion above (len(WRITE_ROUTES)) would still pass while a
        # route went unshadowed — UNLESS this guard fails first. This is the
        # plan's "derive the route list" discipline made executable.
        exercised = 11  # ask, comment, answer, command, tint, run-mode,
        #              posture, decide, deploy, remind, chat-reply
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

    Not a test target: it exists only to run the write routes against a
    journal-off server inside E2's comparison. `__test__ = False` stops
    unittest from collecting the inherited E2 tests against it (they would
    fail on the receipt count, which is the point of the baseline)."""
    __test__ = False
    journal_shadow = False


class E4BestEffort(HttpHarness):
    """E4: a submissions.log failure is shadow_failed health on a durable
    receipt, not a refusal.

    The shadow (submissions.log) is best-effort (design decision 3, step 4):
    it is written AFTER the journal receipt commits, and its failure records
    health against that receipt — the request was already accepted, so the
    response must still be 202.

    Red lines: the `record_health("shadow_failed", ...)` call, and separately
    the absence of a re-raise (log_submission must return False, not propagate
    the OSError)."""

    def test_a_shadow_write_failure_still_returns_202_and_records_health(self):
        # Make submissions.log a DIRECTORY so the append raises a real
        # OSError (IsADirectoryError). Do NOT patch `open` — that would also
        # break the journal write (sqlite3.connect uses os.open internally),
        # so the test would pass for the wrong reason and would keep passing
        # if the ordering inverted (plan's "must not fake" clause).
        subs = os.path.join(self.target, ".dreamwork", "submissions.log")
        os.makedirs(subs)
        # Precondition: submissions.log is now a directory, not a file — the
        # OSError is genuine, not mocked.
        self.assertTrue(os.path.isdir(subs), subs)
        # The closed set a parser reads: shadow_failed is the only health
        # status today. A fixture that adds one without updating the tuple
        # should fail loudly here.
        self.assertIn("shadow_failed", RECEIPT_HEALTH, RECEIPT_HEALTH)
        status, headers, body = self.post(
            "/command", {"kind": "add-idea", "text": "shadow failure test"})
        # The response is 202 — the receipt committed, and a shadow failure
        # cannot turn acceptance into a refusal.
        self.assertEqual(status, 202, status)
        payload = json.loads(body)
        rid = payload["receipt"]["receipt_id"]
        # The receipt is durable (it exists in the journal).
        with open_journal(self._journal_path()) as j:
            row = j.get_receipt(rid)
        self.assertIsNotNone(row, rid)
        # shadow_failed health is recorded against it — the discriminating
        # half. Removing the record_health call leaves the receipt healthy.
        with open_journal(self._journal_path()) as j:
            health = j.get_receipt_health(rid)
        self.assertEqual(health, "shadow_failed", health)

    def test_a_healthy_shadow_records_no_health(self):
        # The positive half: a normal submissions.log write records NO health
        # event. Without this, `return None` from get_receipt_health would
        # pass the test above for the wrong reason.
        status, _, body = self.post(
            "/command", {"kind": "add-idea", "text": "healthy shadow"})
        self.assertEqual(status, 202)
        rid = json.loads(body)["receipt"]["receipt_id"]
        with open_journal(self._journal_path()) as j:
            health = j.get_receipt_health(rid)
        self.assertIsNone(health, health)


class E5Reject(HttpHarness):
    """E5: malformed and schema/domain-invalid bodies are 202 then durably
    rejected, not a synchronous 400. Unknown POST paths stay pre-receipt
    404/405.

    A complete registered envelope is *received* before any body validation;
    JSON parsing, schema and domain checks happen after receipt. A failure
    transitions received → rejected with a bounded reason code from
    REJECTION_REASONS (closed set), never free text.

    Red line: the send_error(400) that USED to live in _read_json.
    Reinstating it makes malformed JSON a synchronous 400 and fails the first
    test below; the second (unknown path → 404) stays green either way."""

    def test_malformed_json_is_202_then_durably_rejected(self):
        # A raw POST with a body that is not valid JSON. Pre-E5 this was a
        # synchronous 400 from _read_json; now it is a 202 + a durable
        # rejected transition with reason_code malformed_json.
        body_bytes = b"{not json, his words"
        # Precondition: the body really is unparseable — the test means
        # nothing if json.loads succeeds.
        import json as _json
        with self.assertRaises(ValueError):
            _json.loads(body_bytes)
        # The closed set a parser reads: malformed_json is a member.
        self.assertIn("malformed_json", REJECTION_REASONS, REJECTION_REASONS)
        status, headers, payload = self.raw_post_json("/command", body_bytes)
        # The response is 202 — a complete registered envelope is received
        # even if its body is garbage. Rejection is durable, not synchronous.
        self.assertEqual(status, 202, status)
        # The receipt is durable and rejected.
        rid = payload["receipt"]["receipt_id"]
        with open_journal(self._journal_path()) as j:
            row = j.get_receipt(rid)
        self.assertIsNotNone(row, rid)
        self.assertEqual(row["state"], "rejected", row["state"])
        # The bounded reason code is recorded in the transition. Derive it
        # from the journal, not from the response body.
        reason = self._latest_reason_code(rid)
        self.assertEqual(reason, "malformed_json", reason)

    def test_schema_invalid_json_is_202_then_durably_rejected(self):
        # Valid JSON but schema-invalid: an unknown command kind. Pre-E5 this
        # was a synchronous 400; now it is a 202 + rejected (domain_invalid).
        self.assertIn("domain_invalid", REJECTION_REASONS, REJECTION_REASONS)
        status, _, body = self.post("/command", {"kind": "nope", "text": "x"})
        self.assertEqual(status, 202, status)
        payload = json.loads(body)
        rid = payload["receipt"]["receipt_id"]
        with open_journal(self._journal_path()) as j:
            row = j.get_receipt(rid)
        self.assertEqual(row["state"], "rejected", row["state"])
        reason = self._latest_reason_code(rid)
        self.assertEqual(reason, "domain_invalid", reason)

    def test_an_unknown_post_path_is_404_and_creates_no_receipt(self):
        # The PAIR is the point: a malformed body ON A REGISTERED PATH is 202
        # (above); an unknown path is pre-receipt 404 and creates no receipt.
        # Either alone is passable by a wrong implementation.
        before = self.receipt_count()
        status, _, _ = self.post("/nonexistent-route",
                                 {"anything": "whatever"})
        self.assertEqual(status, 404, status)
        self.assertEqual(self.receipt_count(), before)

    def test_a_valid_body_is_not_rejected(self):
        # The positive half: a valid body transitions received→validated (or
        # stays received) but is NOT rejected. Without this, `rejected`
        # returned unconditionally would pass the tests above.
        status, _, body = self.post(
            "/command", {"kind": "add-idea", "text": "valid idea"})
        self.assertEqual(status, 202)
        rid = json.loads(body)["receipt"]["receipt_id"]
        with open_journal(self._journal_path()) as j:
            row = j.get_receipt(rid)
        self.assertNotEqual(row["state"], "rejected", row["state"])

    # --- helpers ---

    def raw_post_json(self, path, body_bytes):
        """Raw POST returning (status, headers, parsed_json_body)."""
        response = self.raw_post(path, body_bytes)
        return self._parse_response(response)

    def _parse_response(self, raw):
        head, _, body = raw.partition(b"\r\n\r\n")
        status_line = head.split(b"\r\n", 1)[0]
        status = int(status_line.split()[1])
        headers = {}
        for line in head.split(b"\r\n")[1:]:
            if b": " in line:
                k, v = line.split(b": ", 1)
                headers[k.decode()] = v.decode()
        payload = json.loads(body) if body.strip() else {}
        return status, headers, payload

    def _latest_reason_code(self, receipt_id):
        with open_journal(self._journal_path()) as j:
            row = j.conn.execute(
                "SELECT reason_code FROM transitions "
                "WHERE receipt_id = ? ORDER BY revision DESC LIMIT 1",
                (receipt_id,),
            ).fetchone()
        return row["reason_code"] if row else None


class H1MixedVersion(HttpHarness):
    """H1: mixed-version fail-closed — refuse writes before witnessing.

    A journal whose ``schema_version`` this process cannot understand makes
    open fail; the cutover path then 503s with no receipt and no
    ``submissions.log`` line (same end-state as Origin's pre-body gate, at
    the journal-open seam).  Plan test name:
    ``test_a_mixed_version_server_refuses_before_witnessing``.

    Production line: ``_bootstrap_meta``'s ``stored != SCHEMA_VERSION`` check
    (via ``open_journal`` → ``_journal_receive`` → 503 when result is None).
    Drive more than one foreign version, assert coverage at runtime.
    """

    def _pin_schema_version(self, foreign):
        """Create the journal (if needed) then pin a foreign schema_version."""
        # Ensure the file exists with a real schema first.
        with open_journal(self._journal_path()) as j:
            from user_events.sqlite import SCHEMA_VERSION
            current = int(
                j.conn.execute(
                    "SELECT value FROM meta WHERE key = 'schema_version'"
                ).fetchone()[0]
            )
            # Precondition: the foreign value must differ from supported.
            self.assertNotEqual(foreign, current)
            self.assertNotEqual(foreign, SCHEMA_VERSION)
            j.conn.execute(
                "UPDATE meta SET value = ? WHERE key = 'schema_version'",
                (str(foreign),),
            )
            j.conn.commit()

    def test_a_mixed_version_server_refuses_before_witnessing(self):
        from user_events.sqlite import SCHEMA_VERSION

        # Two foreign versions, derived at runtime so a literal pair cannot
        # expire when SCHEMA_VERSION moves.  Both must refuse.
        foreign_versions = (SCHEMA_VERSION + 1, max(SCHEMA_VERSION - 1, 0))
        if foreign_versions[0] == foreign_versions[1]:
            # SCHEMA_VERSION == 0 is impossible today; keep the assertion.
            foreign_versions = (SCHEMA_VERSION + 1, SCHEMA_VERSION + 2)
        self.assertEqual(len(set(foreign_versions)), 2, foreign_versions)
        for fv in foreign_versions:
            self.assertNotEqual(fv, SCHEMA_VERSION)

        refused = []
        for foreign in foreign_versions:
            # Fresh target so receipts/submissions from one trial cannot
            # pollute the next (and so the open path re-reads the meta row).
            self.doCleanups()
            self.setUp()
            self._pin_schema_version(foreign)
            # A registered write route: after E3 the body is read, then the
            # journal open is attempted, then submissions.log is written only
            # on a successful receive.  Mismatch must 503 with neither.
            status, _, _ = self.post(
                "/command",
                {"kind": "add-idea", "text": f"mixed-ver probe {foreign}"},
            )
            # open_journal refuses a foreign schema, so count receipts by
            # raw SQL rather than through the production open path — the
            # refuse is the property under test; the count is the witness
            # that no row landed underneath it.
            import sqlite3 as _sql
            jpath = self._journal_path()
            if os.path.exists(jpath):
                c = _sql.connect(jpath)
                try:
                    receipts = int(
                        c.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]
                    )
                finally:
                    c.close()
            else:
                receipts = 0
            subs = self.submissions_rows()
            # 503 (or any non-202) with zero durable homes for the write.
            self.assertNotEqual(
                status, 202,
                f"foreign schema_version={foreign} still minted a 202",
            )
            self.assertEqual(
                receipts, 0,
                f"foreign schema_version={foreign} left {receipts} receipt(s)",
            )
            self.assertEqual(
                len(subs), 0,
                f"foreign schema_version={foreign} left submissions: {subs}",
            )
            refused.append((foreign, status, receipts, len(subs)))

        # Coverage: both foreign versions were exercised and refused.
        self.assertEqual(len(refused), len(set(foreign_versions)), refused)
        covered = {r[0] for r in refused}
        self.assertEqual(covered, set(foreign_versions), refused)

        # Positive half on a clean target: supported schema still 202s.
        # Without this, a blanket 503 would pass the refuse loop.
        self.doCleanups()
        self.setUp()
        status, _, body = self.post(
            "/command", {"kind": "add-idea", "text": "supported schema ok"})
        self.assertEqual(status, 202, body)
        self.assertEqual(self.receipt_count(), 1)
        self.assertEqual(len(self.submissions_rows()), 1)


if __name__ == "__main__":
    unittest.main()
