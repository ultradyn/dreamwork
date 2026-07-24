#!/usr/bin/env python3
"""Unit tests for watch.py's data collector. Run: python3 test_watch.py"""

import os
import tempfile
import time
import unittest

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
        self.assertEqual(watch.parse_open_questions(None), [])

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

    def test_persistent_port_stable(self):
        with tempfile.TemporaryDirectory() as d:
            make_target(d)
            p1 = watch.persistent_port(d)
            p2 = watch.persistent_port(d)
            self.assertEqual(p1, p2)
            self.assertTrue(3000 <= p1 < 63000)


if __name__ == "__main__":
    unittest.main()
