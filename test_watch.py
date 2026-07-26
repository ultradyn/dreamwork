#!/usr/bin/env python3
"""Unit tests for watch.py's data collector. Run: python3 test_watch.py"""

import http.server
import inspect
import json
import os
import re
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
        import lint
        self.assertEqual(watch.LEDGER_ENTRY.pattern, lint.LEDGER_ID.pattern)
        self.assertEqual(watch.LEDGER_ENTRY.flags, lint.LEDGER_ID.flags)

    def test_parse_ledger_reads_both_of_the_files_two_shapes(self):
        # An id under `## Open` is an entry HEAD; under `## Recently landed`
        # it is named inline, in prose. Reading the landed section with the
        # entry-head rule finds NOTHING — which renders as "the loop has
        # completed nothing", the exact shape of failure #136 is about.
        text = ("# Task ledger\n\nNext id: **9**\n\n## Open\n\n"
                "- **#7** — a live one · P2 · task\n"
                "  - a continuation line mentioning **#99** in passing\n"
                "- **#8** — another · P3 · idea\n\n"
                "## Recently landed\n\n"
                "**#5** did a thing (abc1234) (2026-07-25). **#6** did "
                "another (def5678).\n")
        openids, landed = watch.parse_ledger(text)
        self.assertEqual(openids, {"7", "8"})
        self.assertEqual(landed, {"5", "6"})
        # a sub-bullet is not an entry, or a mention inside one would mint a
        # task that never existed
        self.assertNotIn("99", openids)
        self.assertEqual(watch.parse_ledger(""), (set(), set()))
        self.assertEqual(watch.parse_ledger("no sections here"), (set(), set()))

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
                            done="**#1** did it (aaa1111) (2026-07-25)."),
                 T + 3600),
                # t=2h: #2 lands, and #1 is GROOMED OUT of the landed section
                (LED.format(open=entry.format(i=3),
                            done="**#2** did it (bbb2222) (2026-07-25)."),
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

    def test_ledger_provenance_is_reported_as_coverage_not_drawn(self):
        # The most telling split would be human- against loop-initiated, and
        # the ledger cannot support it: `**human` is on a MINORITY of
        # entries. Reporting coverage is the honest version; drawing a chart
        # from it would be read as fact. The marker sits anywhere INSIDE an
        # entry, so it is matched per BLOCK — matched per line, an entry
        # whose head is short reads as unmarked.
        text = ("## Open\n\n"
                "- **#1** — one · P2 · idea · **human 17:45** · his words\n"
                "- **#2** — two · P2 · task\n"
                "  more of two, and this line carries the **human 09:00**\n"
                "  stamp on a continuation rather than the head\n"
                "- **#3** — three · P3 · chore\n\n"
                "## Recently landed\n\n**#0** and this **human** must not "
                "count, it is not open\n")
        # Driven through `ledger_stats`, not through `_entry_blocks`: the
        # first version of this test called the helper directly, so the whole
        # per-line/per-block distinction it names was unreachable from it and
        # it stayed green when `ledger_stats` was switched to matching per
        # line. A check has to exercise the path it is about.
        watch._LEDGER_SNAPS.clear()
        watch._LEDGER_CACHE.clear()
        with tempfile.TemporaryDirectory() as d:
            self._ledger_repo(d, [(text, 1784900000)])
            r = watch.ledger_stats(d)
            self.assertEqual(r["entries"], 3)
            self.assertEqual(r["marked"], 2)
            # and the coverage is a MINORITY, which is the whole reason the
            # panel reports it instead of drawing it — assert the gap, or
            # this stops meaning anything the day the ledger fills in
            self.assertLess(r["marked"], r["entries"])
        watch._LEDGER_SNAPS.clear()
        watch._LEDGER_CACHE.clear()

    def test_live_data_assignments_go_through_one_seam(self):
        # `ensureData` consumes mtime as it fetches, so reactive hooks wired
        # beside it are dead on a fresh page and look perfect on later ticks.
        # Every fetcher must assign through setData; a bare assignment silently
        # re-arms #208's exact failure.
        assignments = re.findall(r"(?m)^\s*data\s*=", watch.PAGE)
        self.assertEqual(assignments, ["  data ="])
        self.assertEqual(watch.PAGE.count("setData(await"), 2)

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

    def test_answers_route_and_ask_are_wired(self):
        self.assertIn("function buildAnswers(d)", watch.PAGE)
        self.assertIn("/answers", watch.PAGE)
        self.assertIn("postJSON('/ask'", watch.PAGE)
        self.assertNotIn("fetch('/ask'", watch.PAGE)
        self.assertIn('self.path == "/ask"', inspect.getsource(watch.make_handler))

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
                      'const STALE_TICK_MS'):
            self.assertIn(token, watch.PAGE)
        self.assertIn('applyTitle();     // the liveness word drifts',
                      watch.PAGE)          # ...inside ages()

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
        # #102: markdown prose reflows (hard wraps joined, inline emphasis
        # rendered); raw text stays verbatim in a <pre>. Both halves matter —
        # reflowing a source file or a JSON blob would be a regression.
        for token in ('function mdBlocks', 'function mdRender', 'const mdSpans',
                      'const mdB =', 'const mdBReview =',
                      # the four things a join must not destroy
                      "kind:'fence'", "kind:'h'", "kind:'li'",
                      'const MD_BULLET =',
                      # prose surfaces
                      'mdBReview(q.body.trim(), q.title)', 'mdB(d.content)',
                      'expand(n, mdB(d.files[n]))', 'mdInline(txt)'):
            self.assertIn(token, watch.PAGE)
        # the raw surface keeps <pre>: the file viewer's whole job is to be
        # literal, and it serves code as well as prose.
        self.assertIn('`<pre>${esc(text)}</pre>`', watch.PAGE)
        # status.json was in that list until #130 and is not any more. It is
        # neither prose to reflow nor a file to show verbatim — it is a set of
        # facts, and it has its own component. Asserting the dump is GONE is
        # the half that matters: the old rendering is the reported bug.
        self.assertNotIn('preB(JSON.stringify(d.status', watch.PAGE)
        self.assertIn('function statusBlock', watch.PAGE)

    def test_commit_age_ticks_off_the_render_path(self):
        # #132. The interesting half is not the format, it is WHERE the update
        # happens: a seconds-resolution clock must not ride the tick's
        # innerHTML swap, or it re-runs the regroup (#113) and re-carries his
        # typing (#118) once a second forever.
        for token in ('const agePair =', 'const AGE_PAIRS =', 'const gitRow =',
                      # written as text into nodes that already exist...
                      "querySelectorAll('.age[data-ct]')",
                      "el.textContent = agePair(",
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
        # what he opened survives the tick, or it snaps shut every 2s (#118)
        for token in ('function snapshotFolds', 'function restoreFolds',
                      "querySelectorAll('details[data-keep]')",
                      'restoreFolds(folds)'):
            self.assertIn(token, watch.PAGE)
        # the child combinator is what keeps `> summary` from restyling every
        # question card's own disclosure (the catch-all rule, #121/#139)
        self.assertIn('.qsec > summary', watch.PAGE)
        self.assertNotIn('.qsec summary {', watch.PAGE)

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
        self.assertEqual(
            watch.PAGE.count('qaFail(card, res ? res.status : 0)'), 2,
            "both sendAnswer and sendComment surface a refusal")

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
            self.assertEqual(status, 200)
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
                # #109: the tag names the AUTHOR, not just the channel
                self.assertIn("Note (human, via watch", f.read())
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
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            self.assertEqual(
                self._post_raw(base + "/answer", b"{not json, his words"), 400)
            ln = self._lines(d)[0]
            self.assertEqual(ln["raw"], "{not json, his words")
            self.assertEqual(ln["why"], "json")
            self.assertNotIn("req", ln)

    def test_a_body_that_is_not_utf8_is_kept_too(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._serve(make_target(d))
            self.assertEqual(
                self._post_raw(base + "/answer", b'{"a": "\xff\xfe"}'), 400)
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
                            "answer": "yes"}), 200)
            self.assertEqual(
                self._post(base + "/command",
                           {"kind": "add-idea", "text": "try X"}), 200)
            self.assertEqual(self._post(base + "/tint", {"tint": "nope"}), 400)
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
