"""Tests for relay.py.

The first two are the reason the module exists: a body that would be
mangled by shell expansion must survive verbatim, and the header must come
from the clock rather than from an argument anyone can invent.
"""

import re
from datetime import datetime

import pytest

import relay as relay_mod


HOSTILE = """The reader tests `- **` and `## ` on the RAW line, and
`_parse_entries` joins continuation lines. $(echo pwned) and ${HOME} and
$USER must all survive, as must a literal backslash \\ and "quotes"."""


@pytest.fixture
def inbox(tmp_path, monkeypatch):
    monkeypatch.setattr(relay_mod, "INBOX_DIR", tmp_path)
    return tmp_path


class TestTheBugItExistsFor:
    def test_backticks_and_expansions_survive_verbatim(self, inbox):
        # An unquoted heredoc ate every backticked term in a real relay and
        # left the sentences without their nouns. Nothing here is a shell.
        relay_mod.relay("dreamer-thread", HOSTILE)
        written = (inbox / "dreamer-thread-inbox.md").read_text()
        for fragment in ["`- **`", "`## `", "`_parse_entries`", "$(echo pwned)",
                         "${HOME}", "$USER", "\\", '"quotes"']:
            assert fragment in written, fragment

    def test_the_stamp_comes_from_the_clock(self, inbox):
        relay_mod.relay("dreamer-thread", "body")
        written = (inbox / "dreamer-thread-inbox.md").read_text()
        m = re.search(r"\[coordinator (\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]", written)
        assert m, written
        stamped = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")
        drift = abs((datetime.now() - stamped).total_seconds())
        assert drift < 120, f"stamp is {drift}s from now"


class TestBothDirections:
    """The reverse direction is why the module grew a flag: a dreamer
    reporting to the coordinator must not type a time either."""

    def test_a_dreamer_reports_under_its_own_name(self, inbox):
        relay_mod.relay("coord", "increment 3 done", sender="dreamer-rows")
        written = (inbox / "coord-inbox.md").read_text()
        assert written.lstrip().startswith("[dreamer-rows ")
        assert "increment 3 done" in written

    def test_the_dreamers_stamp_also_comes_from_the_clock(self, inbox):
        relay_mod.relay("coord", "body", sender="dreamer-rows")
        written = (inbox / "coord-inbox.md").read_text()
        m = re.search(r"\[dreamer-rows (\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]", written)
        assert m, written
        drift = abs((datetime.now() - datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")).total_seconds())
        assert drift < 120

    def test_the_default_sender_is_still_the_coordinator(self, inbox):
        relay_mod.relay("dreamer-rows", "body")
        assert "[coordinator " in (inbox / "dreamer-rows-inbox.md").read_text()


class TestShape:
    def test_appends_rather_than_overwrites(self, inbox):
        relay_mod.relay("d", "first")
        relay_mod.relay("d", "second")
        written = (inbox / "d-inbox.md").read_text()
        assert "first" in written and "second" in written
        assert written.index("first") < written.index("second")

    def test_entries_are_separated(self, inbox):
        relay_mod.relay("d", "first")
        relay_mod.relay("d", "second")
        written = (inbox / "d-inbox.md").read_text()
        # A blank line before each header, so two entries never run together.
        assert "\n\n[coordinator" in written

    def test_creates_the_inbox_and_its_directory(self, tmp_path, monkeypatch):
        nested = tmp_path / "does" / "not" / "exist"
        monkeypatch.setattr(relay_mod, "INBOX_DIR", nested)
        path = relay_mod.relay("newcomer", "hello")
        assert path.exists()
        assert path.name == "newcomer-inbox.md"

    def test_an_explicit_inbox_filename_is_respected(self, inbox):
        path = relay_mod.relay("dreamer-thread-inbox.md", "body")
        assert path.name == "dreamer-thread-inbox.md"


class TestCli:
    def test_reads_the_body_from_stdin(self, inbox, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", __import__("io").StringIO(HOSTILE))
        assert relay_mod.main(["dreamer-thread"]) == 0
        assert "`- **`" in (inbox / "dreamer-thread-inbox.md").read_text()

    def test_an_empty_body_writes_nothing_and_says_so(self, inbox, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", __import__("io").StringIO("   \n"))
        assert relay_mod.main(["dreamer-thread"]) == 2
        assert not (inbox / "dreamer-thread-inbox.md").exists()
        assert "empty body" in capsys.readouterr().err
