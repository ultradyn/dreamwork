#!/usr/bin/env python3
"""Unit tests for watch.py's data collector. Run: python3 test_watch.py"""

import http.server
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
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

    def test_watched_mtime_moves(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            before = watch.watched_mtime(d)
            time.sleep(0.05)
            with open(os.path.join(d, ".dreamwork", "lessons.md"), "a") as f:
                f.write("- new lesson\n")
            self.assertGreater(watch.watched_mtime(d), before)

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
        self.assertIn("**Follow-up (via watch, 2026-07-25 08:00):** a thought",
                      new)
        # a follow-up on an Answered entry lands in the Answered section
        new2, matched2 = watch.append_comment(text, "Done one", "amend it",
                                              "2026-07-25 08:01", "Answered")
        self.assertTrue(matched2)
        self.assertGreater(new2.index("Follow-up"), new2.index("## Answered"))
        _n, m3 = watch.append_comment(text, "Nope", "x", "2026-07-25", "Open")
        self.assertFalse(m3)

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
        self.assertEqual(qs[0]["follows"], ["note one."])
        self.assertNotIn("Follow-up", qs[0]["body"])
        ans = watch.parse_answered(text)
        self.assertEqual([e["title"] for e in ans], ["Old"])
        self.assertEqual(ans[0]["follows"], ["reopen?"])
        self.assertNotIn("Follow-up", ans[0]["body"])

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

    def test_persistent_port_stable(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            p1 = watch.persistent_port(d)
            p2 = watch.persistent_port(d)
            self.assertEqual(p1, p2)
            self.assertTrue(3000 <= p1 < 63000)


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

    def test_page_has_review_route_wiring(self):
        # Static guard: /review is an in-app route that embeds the artifact
        # (from /reviewraw) and docks the originating question, which morphs
        # into place (shared-element FLIP) from where it was clicked.
        for token in ('buildReview', 'reviewframe', 'qdock', 'flipDock',
                      '/reviewraw', 'linkifyReview'):
            self.assertIn(token, watch.PAGE)

    def test_page_has_command_palette_wiring(self):
        # Static guard: the + opener, the palette, POST /command, the dream
        # ripple, and the pop-out (Document Picture-in-Picture + window.open
        # fallback) must stay wired so a refactor can't drop the steer path.
        for token in ('id="cmdplus"', 'id="cmdpalette"', 'pageHeader',
                      "fetch('/command'", 'documentPictureInPicture',
                      'window.open', 'ripple('):
            self.assertIn(token, watch.PAGE)

    def test_shader_world_space_wiring(self):
        # Static guard: the shader anchors its domain to the window's screen
        # position and takes its phase from the wall clock (UTC-day-wrapped),
        # so adjacent windows share one continuous, screen-pinned field.
        for token in ('uniform vec2 domainOffset', 'window.screenX',
                      '% 86400'):
            self.assertIn(token, watch.PAGE)

    def test_page_has_answered_awaiting_fold_state(self):
        # Static guard: the questions view renders three states — an answered
        # (awaiting fold) entry is visually distinct with no input box (#81).
        for token in ('qa answered', 'awaiting fold', 'q.answer'):
            self.assertIn(token, watch.PAGE)

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
        # (shared answeredInner), and Ctrl/Cmd+Enter submits from a field.
        for token in ('answeredInner', 'requestSubmit',
                      "(e.ctrlKey || e.metaKey) && e.key === 'Enter'"):
            self.assertIn(token, watch.PAGE)

    def test_page_has_followup_wiring(self):
        # #82: every entry gets a follow-up thread + add-a-note box that POSTs
        # /comment; answered entries are rendered structured (answered_entries).
        for token in ('sendComment', 'postComment', "fetch('/comment'",
                      'followThread', 'noteBox', 'answered_entries'):
            self.assertIn(token, watch.PAGE)

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
            for path in ("/", "/questions", "/file?p=DREAMWORK.md"):
                status, body = self._get(base + path)
                self.assertEqual(status, 200)
                self.assertIn('id="view"', body)      # same app shell
                self.assertIn("dreamwork watch", body)

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
            self.assertEqual(status, 200)
            qpath = os.path.join(d, ".dreamwork", "questions.md")
            with open(qpath) as f:
                self.assertIn("Follow-up (via watch", f.read())
            for bad, code in ((
                    {"question": "A real open question?", "comment": "x",
                     "section": "Nope"}, 400),
                    ({"question": "No such", "comment": "x",
                      "section": "Open"}, 409)):
                with self.assertRaises(urllib.error.HTTPError) as cm:
                    self._post(base + "/comment", bad)
                self.assertEqual(cm.exception.code, code)

    def test_command_appends_event_and_validates(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            status, _ = self._post(base + "/command",
                                   {"kind": "add-idea", "text": "try X"})
            self.assertEqual(status, 200)
            log = os.path.join(d, ".dreamwork", "watch-events.log")
            with open(log) as f:
                self.assertIn("command via watch: add-idea: try X", f.read())
            # do-next may omit text
            status, _ = self._post(base + "/command",
                                   {"kind": "do-next", "text": ""})
            self.assertEqual(status, 200)
            # unknown kind, and a text-requiring kind with no text, are 400
            for bad in ({"kind": "nope", "text": "x"},
                        {"kind": "do-now", "text": ""}):
                with self.assertRaises(urllib.error.HTTPError) as cm:
                    self._post(base + "/command", bad)
                self.assertEqual(cm.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
