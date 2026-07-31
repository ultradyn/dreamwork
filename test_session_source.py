"""Tests for `session_source.py` — #698.

The defect this module exists for: the `agent_session` seam is empty, and the
obvious fallback (derive the transcript path from the target directory) lands
on a STALE file because the session relocated to a worktree slug. These tests
pin the resolution that replaces that fallback — uuid-search across slugs, plus
a liveness verdict that NAMES staleness rather than reading as absence (`#136`).

Every test names the production line whose reversion reds it. The two
directions the brief requires are isolated as their own classes:

  - `TestDirection1StalenessNamesAgeNotAbsence` — a transcript that resolves
    but is old must report `stale` with the age in the message, NOT `absent`.
    "no agent_session" and "agent_session names a file last written two days
    ago" are different findings, and the second is the dangerous one.
  - `TestDirection2PresentButWrong` — `#693`'s allowlist shape: a session_id
    that is set, non-empty, and resolves to a LIVE-but-WRONG transcript. The
    data alone cannot catch it (the test asserts the false-green HONESTLY);
    the `expected_session_id` cross-check is the one detection, and it is
    tested to fire and to stay quiet when the ids agree.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import session_source
import status_sync

UTC = timezone.utc
# A fixed clock so liveness never depends on wall time. `now` is the moment the
# resolver is asked "is this live?".
NOW = datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)


def _ts(minutes_ago: float) -> str:
    """An ISO8601 UTC timestamp `minutes_ago` before NOW, with trailing Z."""
    return (NOW - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _write_transcript(path: Path, records: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    return path


def _projects(tmp_path: Path, slug: str = "slug-a") -> Path:
    root = tmp_path / "projects"
    (root / slug).mkdir(parents=True)
    return root


LIVE_ID = "3a19e737-cb3f-4dde-8304-3241ac374cdb"
STALE_ID = "c196985f-4070-4762-915f-7fd6cc8af895"


# ── the five states ──────────────────────────────────────────────────────

class TestResolveStates:
    """`resolve`'s branches. Collapsing any two states reds the test that
    distinguishes them, which is the `#136` rule (distinct nothings must not
    read the same)."""

    def test_a_recent_transcript_is_live(self, tmp_path):
        # production line: the `age > stale_after` comparison in `resolve`.
        root = _projects(tmp_path)
        _write_transcript(root / "slug-a" / f"{LIVE_ID}.jsonl",
                          [{"type": "user", "timestamp": _ts(2)}])
        r = session_source.resolve(LIVE_ID, root, now=NOW)
        assert r.status == "live"
        assert r.ok is True
        assert r.path.name == f"{LIVE_ID}.jsonl"
        assert r.last_record_at is not None

    def test_no_session_id_is_absent_and_names_the_empty_seam(self, tmp_path):
        # production line: the `if not session_id` branch. This is the #698
        # state today: the seam exists and is empty.
        root = _projects(tmp_path)
        r = session_source.resolve(None, root, now=NOW)
        assert r.status == "absent"
        assert r.ok is False
        assert "seam is empty" in r.detail

    def test_an_id_with_no_transcript_is_missing(self, tmp_path):
        # production line: the `if not found` branch.
        root = _projects(tmp_path)
        r = session_source.resolve("deadbeef-0000-0000-0000-000000000000",
                                   root, now=NOW)
        assert r.status == "missing"
        assert "not found" in r.detail

    def test_an_id_under_two_slugs_is_missing_ambiguous_not_a_guess(self, tmp_path):
        # production line: the `len(found) > 1` branch. Picking one would be
        # the confident-wrong-answer this loop files bugs about.
        root = tmp_path / "projects"
        _write_transcript(root / "slug-a" / f"{LIVE_ID}.jsonl",
                          [{"type": "user", "timestamp": _ts(2)}])
        _write_transcript(root / "slug-b" / f"{LIVE_ID}.jsonl",
                          [{"type": "user", "timestamp": _ts(2)}])
        r = session_source.resolve(LIVE_ID, root, now=NOW)
        assert r.status == "missing"
        assert "ambiguous" in r.detail


class TestUuidSearchCrossesSlugs:
    """The whole point of the module: the slug is not derivable (the session
    relocates), so the uuid is searched across every slug. Production line:
    `_find_transcript`'s `projects_root.glob(f'*/{session_id}.jsonl')`."""

    def test_the_id_is_found_under_a_worktree_slug_not_the_target_slug(
            self, tmp_path):
        root = tmp_path / "projects"
        # The transcript lives under a slug that does NOT match any cwd the
        # loop would derive — it relocated here.
        _write_transcript(
            root / "-home-x--repo--worktrees-lane-x" / f"{LIVE_ID}.jsonl",
            [{"type": "user", "timestamp": _ts(3)}])
        r = session_source.resolve(LIVE_ID, root, now=NOW)
        assert r.status == "live"
        assert r.path.parent.name == "-home-x--repo--worktrees-lane-x"


class TestSymlinkTrap:
    """`#698`/`#691`: `$CLAUDE_CONFIG_DIR/projects` is a SYMLINK, and `find`
    without `-L` silently returns nothing against it. `Path.glob` follows the
    symlinked base (verified live); this pins that so a switch to `find` or a
    glob flag regresses loudly."""

    def test_a_symlinked_projects_root_still_resolves(self, tmp_path):
        real = tmp_path / "real-projects"
        _write_transcript(real / "slug-a" / f"{LIVE_ID}.jsonl",
                          [{"type": "user", "timestamp": _ts(2)}])
        link = tmp_path / "link-projects"
        os.symlink(real, link)
        r = session_source.resolve(LIVE_ID, link, now=NOW)
        assert r.status == "live", r.detail


class TestLastTimestampSkipsUntimestampedRecords:
    """`type: "relocated"` records (and others) carry no `timestamp`. Liveness
    must scan past them to the last record that does. Production line:
    `_last_timestamp`'s `if isinstance(ts, str)` guard."""

    def test_relocated_records_in_the_tail_are_scanned_past(self, tmp_path):
        root = _projects(tmp_path)
        path = root / "slug-a" / f"{LIVE_ID}.jsonl"
        _write_transcript(path, [
            {"type": "user", "timestamp": _ts(5)},
            {"type": "relocated", "sessionId": LIVE_ID,
             "relocatedCwd": "/home/x/repo/.worktrees/lane-x"},
            {"type": "relocated", "sessionId": LIVE_ID,
             "relocatedCwd": "/home/x/repo/.worktrees/lane-x"},
        ])
        last = session_source._last_timestamp(path)
        assert last == NOW - timedelta(minutes=5)


# ── Direction 1: staleness must NAME the age, not read as absence ─────────

class TestDirection1StalenessNamesAgeNotAbsence:
    """The brief: *the failure must name the staleness, not merely the
    absence.* `#136`: an absent seam and a stale one must not read the same."""

    def test_stale_reports_the_age_in_minutes_and_dead_not_absent(self, tmp_path):
        root = _projects(tmp_path)
        _write_transcript(root / "slug-a" / f"{STALE_ID}.jsonl",
                          [{"type": "user", "timestamp": _ts(60)}])
        r = session_source.resolve(STALE_ID, root, now=NOW)
        assert r.status == "stale"
        assert r.ok is False
        # The discriminating message: it names the AGE…
        assert "min ago" in r.detail
        # …it names this as a DEAD session, not a missing one…
        assert "DEAD" in r.detail
        # …and it does NOT read like absence (the word the absent state uses).
        assert "seam is empty" not in r.detail
        assert "empty" not in r.detail

    def test_a_two_day_old_transcript_is_stale_not_live(self, tmp_path):
        # Mirrors the live defect: the target-dir derivation lands on a file
        # last written two days ago. Here that file is found BY UUID and still
        # judged stale, because presence is not liveness (#693).
        root = _projects(tmp_path)
        _write_transcript(root / "slug-a" / f"{STALE_ID}.jsonl",
                          [{"type": "user", "timestamp": _ts(60 * 24 * 2)}])
        r = session_source.resolve(STALE_ID, root, now=NOW)
        assert r.status == "stale"
        assert "2880 min ago" in r.detail


# ── Direction 2: present, well-formed, and pointing at the wrong transcript

class TestDirection2PresentButWrong:
    """`#693`'s allowlist shape, transferred: a session_id that is set,
    non-empty, and resolves to a transcript — but the WRONG one. A presence
    check passes on this; liveness alone passes if the wrong transcript is
    fresh. The `expected_session_id` cross-check is the one detection."""

    def test_without_expected_a_live_but_wrong_id_is_a_false_green(self, tmp_path):
        """The honest limitation, asserted not hidden.

        A different live session's id resolves to ITS OWN fresh transcript and
        reads as `live`. The data alone cannot tell it is the wrong session —
        this is the case the brief asks to name plainly. `expected_session_id`
        (next test) is what catches it.
        """
        root = _projects(tmp_path)
        _write_transcript(root / "slug-a" / f"{LIVE_ID}.jsonl",
                          [{"type": "user", "timestamp": _ts(2)}])
        r = session_source.resolve(LIVE_ID, root, now=NOW)  # no expected id
        assert r.status == "live"  # the false green — documented, not hidden

    def test_with_expected_a_mismatching_id_is_detected(self, tmp_path):
        # production line: the `expected_session_id and session_id != expected`
        # branch. The recorded transcript is fresh, but it is not THIS process.
        root = _projects(tmp_path)
        _write_transcript(root / "slug-a" / f"{LIVE_ID}.jsonl",
                          [{"type": "user", "timestamp": _ts(2)}])
        r = session_source.resolve(LIVE_ID, root, now=NOW,
                                   expected_session_id="different-live-id")
        assert r.status == "mismatch"
        assert "differs from the running process" in r.detail

    def test_when_expected_agrees_no_mismatch_is_raised(self, tmp_path):
        # The cross-check must not fire when the ids agree — otherwise the
        # normal live path is unreachable from a process that knows its own id.
        root = _projects(tmp_path)
        _write_transcript(root / "slug-a" / f"{LIVE_ID}.jsonl",
                          [{"type": "user", "timestamp": _ts(2)}])
        r = session_source.resolve(LIVE_ID, root, now=NOW,
                                   expected_session_id=LIVE_ID)
        assert r.status == "live"


# ── reading the seam from status.json ────────────────────────────────────

class TestSessionIdFromStatus:
    """`session_id_from_status` reads the recorded id through the SHARED
    refusal reader (#655), so a torn status.json is refused, not crashed on
    (#580/#622: a guard whose subject may not exist must return, not throw)."""

    def _target(self, tmp_path, status):
        dw = tmp_path / ".dreamwork"
        dw.mkdir(exist_ok=True)
        (dw / "status.json").write_text(json.dumps(status, indent=2) + "\n")
        return tmp_path

    def test_reads_the_recorded_session_id(self, tmp_path):
        t = self._target(tmp_path, {"agent_session": {"session_id": LIVE_ID}})
        assert session_source.session_id_from_status(t) == LIVE_ID

    def test_no_agent_session_key_is_none(self, tmp_path):
        t = self._target(tmp_path, {"task": "on #698"})
        assert session_source.session_id_from_status(t) is None

    def test_a_null_session_id_is_none_not_an_empty_string(self, tmp_path):
        # `#665`: a known client with no id var records null, honestly. That
        # is absence, not an id, and must not become "" downstream.
        t = self._target(tmp_path, {"agent_session": {"session_id": None}})
        assert session_source.session_id_from_status(t) is None

    def test_a_torn_status_json_is_refused_not_crashed(self, tmp_path):
        spath = tmp_path / ".dreamwork" / "status.json"
        spath.parent.mkdir(parents=True)
        spath.write_text('{"task": "torn", "dreamers": [')  # unparseable
        assert session_source.session_id_from_status(tmp_path) is None


class TestSharedReaderBinding:
    """#655: a value meant to come from one place is bound there by a test that
    can only pass if the shared reader is what runs. This consumer must not
    hand-roll a second status.json reader."""

    def test_it_uses_status_syncs_read_status_not_a_copy(self):
        assert session_source._read_status is status_sync._read_status


# ── end to end through resolve_target ────────────────────────────────────

class TestResolveTarget:
    def test_an_empty_seam_target_resolves_absent(self, tmp_path):
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "status.json").write_text(json.dumps({"task": "on #698"}) + "\n")
        r = session_source.resolve_target(tmp_path, now=NOW,
                                          projects_root=_projects(tmp_path))
        assert r.status == "absent"

    def test_a_populated_seam_target_resolves_live(self, tmp_path):
        root = tmp_path / "projects"
        _write_transcript(root / "slug-a" / f"{LIVE_ID}.jsonl",
                          [{"type": "user", "timestamp": _ts(2)}])
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "status.json").write_text(
            json.dumps({"agent_session": {"session_id": LIVE_ID}}) + "\n")
        r = session_source.resolve_target(tmp_path, now=NOW, projects_root=root)
        assert r.status == "live"
