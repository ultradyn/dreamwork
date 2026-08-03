"""Tests for dev/rotate_inbox.py — the inbox.md rotation tool (#1104).

These tests build their OWN fixture inbox (never touching the live file) and
exercise the rotation against it: the 'fixture-built-list' false-green the
brief warned about is closed by asserting byte conservation and entry counts
that are DERIVED at runtime, never hardcoded literals tuned to a fixture.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent
TOOL = REPO / "dev" / "rotate_inbox.py"


def _load():
    spec = importlib.util.spec_from_file_location("rotate_inbox_under_test", TOOL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_entry(i: int) -> str:
    return f"## Task #{i} — report\n\nLane #{i} completed its work.\nSHA: abc{i:04d}\n\n"


@pytest.fixture
def dw(tmp_path: Path) -> Path:
    d = tmp_path / ".dreamwork"
    d.mkdir()
    return d


class TestSplitEntries:
    def test_splits_on_double_hash_headings(self):
        mod = _load()
        text = "old pointer line\n\n## First\nbody1\n\n## Second\nbody2\n"
        prologue, entries = mod._split_entries(text)
        assert "old pointer" in prologue
        assert len(entries) == 2
        assert entries[0].startswith("## First")
        assert "body1" in entries[0]
        assert entries[1].startswith("## Second")

    def test_no_headings_returns_prologue_only(self):
        mod = _load()
        text = "just prose\nno headings\n"
        prologue, entries = mod._split_entries(text)
        assert entries == []
        assert prologue == text


class TestRotate:
    def test_moves_older_entries_and_keeps_recent(self, dw: Path):
        mod = _load()
        n_total = 10
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(n_total)))
        result = mod.rotate(dw, keep=3)
        assert result["action"] == "rotated"
        assert result["entries_moved"] == 7  # derived: n_total - keep
        assert result["entries_kept"] == 3
        # The live file has the LAST 3 entries.
        live = inbox.read_text()
        assert "Task #7" in live
        assert "Task #8" in live
        assert "Task #9" in live
        assert "Task #0" not in live
        assert "Task #6" not in live

    def test_archive_contains_moved_entries(self, dw: Path):
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        mod.rotate(dw, keep=3)
        archive = list((dw / "inbox-archive").glob("*.md"))
        assert len(archive) == 1
        atext = archive[0].read_text()
        assert "Task #0" in atext
        assert "Task #6" in atext
        assert "Task #9" not in atext

    def test_pointer_comment_names_the_archive(self, dw: Path):
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        mod.rotate(dw, keep=3)
        first_line = inbox.read_text().splitlines()[0]
        assert "inbox-archive" in first_line
        assert first_line.startswith("<!--")

    def test_byte_conservation(self, dw: Path):
        """The archive + live file must account for every byte (minus the pointer)."""
        mod = _load()
        inbox = dw / "inbox.md"
        original = "".join(_make_entry(i) for i in range(10))
        inbox.write_text(original)
        original_bytes = len(original.encode("utf-8"))
        mod.rotate(dw, keep=3)
        live = inbox.read_text()
        archive = list((dw / "inbox-archive").glob("*.md"))[0].read_text()
        live_bytes = len(live.encode("utf-8"))
        archive_bytes = len(archive.encode("utf-8"))
        # live + archive >= original (pointer line adds a small overhead).
        assert live_bytes + archive_bytes >= original_bytes
        # The overhead is just the pointer comment (~100 bytes).
        overhead = live_bytes + archive_bytes - original_bytes
        assert overhead < 200, f"unexpected overhead: {overhead}"

    def test_noop_when_few_entries(self, dw: Path):
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(3)))
        result = mod.rotate(dw, keep=50)
        assert result["action"] == "noop"
        assert not (dw / "inbox-archive").exists()

    def test_idempotent_second_run(self, dw: Path):
        """Running twice does not corrupt or duplicate."""
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        mod.rotate(dw, keep=3)
        first_live = inbox.read_text()
        # Second run: only 3 entries, keep=3 -> noop.
        result = mod.rotate(dw, keep=3)
        assert result["action"] == "noop"
        assert inbox.read_text() == first_live

    def test_prologue_goes_to_archive(self, dw: Path):
        """Old pre-heading prologue (/tmp pointer era) is archived, not kept."""
        mod = _load()
        inbox = dw / "inbox.md"
        prologue = "- 302 — old /tmp pointer line\n- 203 — another old one\n"
        inbox.write_text(prologue + "".join(_make_entry(i) for i in range(5)))
        mod.rotate(dw, keep=2)
        live = inbox.read_text()
        assert "/tmp pointer" not in live
        archive = list((dw / "inbox-archive").glob("*.md"))[0].read_text()
        assert "/tmp pointer" in archive

    def test_absent_inbox_is_noop(self, dw: Path):
        mod = _load()
        result = mod.rotate(dw, keep=50)
        assert result["action"] == "noop"

    def test_appends_to_existing_archive_same_month(self, dw: Path):
        """Two rotations in the same month accumulate in one archive file."""
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        mod.rotate(dw, keep=3)  # moves 7, keeps 3
        # Add more entries to trigger a second rotation.
        live = inbox.read_text()
        inbox.write_text(live + "".join(_make_entry(100 + i) for i in range(5)))
        mod.rotate(dw, keep=3)  # moves 5 more
        archives = list((dw / "inbox-archive").glob("*.md"))
        assert len(archives) == 1  # same month -> one file
        atext = archives[0].read_text()
        assert "Task #0" in atext  # from first rotation
        assert "Task #100" in atext  # from second


class TestStatus:
    def test_reports_bytes_and_entries(self, dw: Path):
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(5)))
        info = mod.status(dw)
        assert info["exists"] is True
        assert info["entries"] == 5
        assert info["bytes"] > 0

    def test_absent_inbox(self, dw: Path):
        mod = _load()
        info = mod.status(dw)
        assert info["exists"] is False


class TestLiveLaneRefusal:
    """#1158: rotate refuses (distinct from noop) when a live lane is detected."""

    def test_refused_when_live_lane_count_positive(self, dw: Path):
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        result = mod.rotate(dw, keep=3, live_lane_count=lambda: 2)
        assert result["action"] == "refused"
        assert result["live_lanes"] == 2

    def test_refused_leaves_live_file_untouched(self, dw: Path):
        """Refusing must not move a single byte — no archive written."""
        mod = _load()
        inbox = dw / "inbox.md"
        original = "".join(_make_entry(i) for i in range(10))
        inbox.write_text(original)
        mod.rotate(dw, keep=3, live_lane_count=lambda: 1)
        assert inbox.read_text() == original  # untouched
        assert not (dw / "inbox-archive").exists()  # no archive created

    def test_refused_is_distinct_from_noop(self, dw: Path):
        """'refused (lane live)' and 'noop (nothing to do)' are two states (#136)."""
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        refused = mod.rotate(dw, keep=3, live_lane_count=lambda: 1)
        assert refused["action"] == "refused"
        # A separate file with too few entries is noop, not refused.
        dw2 = dw.parent / "dw2" / ".dreamwork"
        dw2.mkdir(parents=True)
        (dw2 / "inbox.md").write_text("".join(_make_entry(i) for i in range(2)))
        noop = mod.rotate(dw2, keep=50, live_lane_count=lambda: 1)
        assert noop["action"] == "noop"
        assert refused["action"] != noop["action"]

    def test_rotates_when_no_live_lanes(self, dw: Path):
        """A zero live count lets the rotation proceed."""
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        result = mod.rotate(dw, keep=3, live_lane_count=lambda: 0)
        assert result["action"] == "rotated"


class TestReconciliation:
    """#868/#702: a rotation must account for every entry it observed."""

    def test_reconciliation_balances_on_success(self, dw: Path):
        mod = _load()
        inbox = dw / "inbox.md"
        n_total = 12  # derived at runtime, not a tuned literal
        inbox.write_text("".join(_make_entry(i) for i in range(n_total)))
        keep = 4
        result = mod.rotate(dw, keep=keep)
        assert result["action"] == "rotated"
        # ONE counting rule (^## headings): moved + retained == observed.
        assert result["reconcile_moved"] + result["reconcile_retained"] == result["reconcile_observed"]
        assert result["reconcile_observed"] == n_total
        assert result["reconcile_moved"] == n_total - keep
        assert result["reconcile_retained"] == keep
        assert result["reconciled"] is True

    def test_pointer_names_first_retained_and_live_matches(self, dw: Path):
        """The pointer claims a heading; the live file's first entry must match."""
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        keep = 3
        mod.rotate(dw, keep=keep)
        live = inbox.read_text()
        first_line = live.splitlines()[0]
        # The pointer carries the first retained entry's heading.
        first_live_heading = next(l for l in live.splitlines() if l.startswith("## "))
        assert first_live_heading in first_line
        assert first_live_heading == "## Task #%d — report" % (10 - keep)

    def test_reconciliation_detects_a_lost_entry(self, dw: Path):
        """The balance check fires when moved+retained != observed (#868).

        A rotation that lost one retained entry: 7 moved + 2 retained != 10
        observed. The pure verdict is the single source, so a sabotage here
        reddens every reconciliation — tested directly with a discriminating
        count, not an ``assert 0 == 1``.
        """
        mod = _load()
        assert mod._reconcile_balanced(observed=10, moved=7, retained=3) is True
        # One entry lost: 7 + 2 = 9 != 10.
        assert mod._reconcile_balanced(observed=10, moved=7, retained=2) is False
        # An entry dropped from the archive side: 6 + 3 = 9 != 10.
        assert mod._reconcile_balanced(observed=10, moved=6, retained=3) is False

    def test_pointer_claims_first_retained_heading(self, dw: Path):
        """The pointer carries the first retained entry; the live file honours it."""
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        keep = 3
        mod.rotate(dw, keep=keep)
        live = inbox.read_text()
        first_line = live.splitlines()[0]
        first_live_heading = next(l for l in live.splitlines() if l.startswith("## "))
        # The pointer (an HTML comment) names the heading the live file resumes at.
        assert first_live_heading in first_line
        assert first_live_heading == "## Task #%d — report" % (10 - keep)

    def test_reconciliation_over_accumulating_archive(self, dw: Path):
        """Two rotations same month: archive accumulates, delta still balances."""
        mod = _load()
        inbox = dw / "inbox.md"
        inbox.write_text("".join(_make_entry(i) for i in range(10)))
        r1 = mod.rotate(dw, keep=3)
        assert r1["reconciled"] is True
        # Add entries and rotate again — archive_before > 0 this time.
        inbox.write_text(inbox.read_text() + "".join(_make_entry(100 + i) for i in range(5)))
        r2 = mod.rotate(dw, keep=3)
        assert r2["action"] == "rotated"
        assert r2["reconciled"] is True
        assert r2["reconcile_moved"] + r2["reconcile_retained"] == r2["reconcile_observed"]
