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


# ── #631 increment 5: the server-derived session catalogue ──────────────

# A second measured id, distinct from LIVE_ID/STALE_ID, so the active-vs-newest
# injection has two genuine candidates to confuse.
OTHER_ID = "11111111-2222-3333-4444-555555555555"
UUID_A = "aaaaaaaa-0000-0000-0000-000000000001"
UUID_B = "bbbbbbbb-0000-0000-0000-000000000002"


def _slug(target) -> str:
    """The production slug for a target, so fixtures name dirs the way the
    catalogue searches them (self-consistent, never a hand-guessed literal)."""
    return session_source._slug_for(target)


def _cat_target(tmp_path: Path, *, worktrees=()):
    """A target dir under tmp_path, optionally with `.worktrees/<name>` dirs.

    Returns (target, projects_root). Caller populates slug dirs under root.
    """
    target = tmp_path / "target"
    target.mkdir()
    for wt in worktrees:
        (target / ".worktrees" / wt).mkdir(parents=True)
    root = tmp_path / "projects"
    root.mkdir()
    return target, root


class TestCatalogueDiscovery:
    """`catalogue` discovers strictly-named uuid jsonl under the target's cwd
    slug(s) and nothing else. Production line: `_target_slug_dirs` +
    `_session_uuid` inside `catalogue`."""

    def test_the_slug_rule_matches_the_measured_root_independently(self):
        # Direction-2 guard: every discovery test names its fixture dir via
        # `_slug(target)`, so a WRONG slug rule is self-consistent between test
        # and impl and the tests pass anyway. This pins the measured rule
        # (`/` and `.` → `-`, verified against ~/.claude-p/projects) by a
        # literal the production function must reproduce — independent of the
        # function it checks.
        assert session_source._slug_for(
            "/home/x/.llm-general/skills/ud-dreamwork") == (
            "-home-x--llm-general-skills-ud-dreamwork")

    def test_finds_sessions_under_the_target_slug(self, tmp_path):
        target, root = _cat_target(tmp_path)
        slug = _slug(target)
        _write_transcript(root / slug / f"{LIVE_ID}.jsonl",
                          [{"type": "user", "timestamp": _ts(2)}])
        _write_transcript(root / slug / f"{OTHER_ID}.jsonl",
                          [{"type": "user", "timestamp": _ts(3)}])
        res = session_source.catalogue(target, projects_root=root, now=NOW)
        assert res.status == "ok"
        # Precondition derived at runtime: discovery found what the fixture put
        # there, so assertions on entries are not vacuous (#136/#671).
        assert res.entries, "precondition: fixture populated but empty catalogue"
        ids = {e.session_id for e in res.entries}
        assert ids == {LIVE_ID, OTHER_ID}

    def test_finds_sessions_across_two_cwd_slugs_target_and_worktree(
            self, tmp_path):
        # production line: `_target_slug_dirs` adding the worktree slug.
        target, root = _cat_target(tmp_path, worktrees=["lane-x"])
        main_slug = _slug(target)
        wt_slug = _slug(target / ".worktrees" / "lane-x")
        _write_transcript(root / main_slug / f"{UUID_A}.jsonl",
                          [{"type": "user", "timestamp": _ts(2)}])
        _write_transcript(root / wt_slug / f"{UUID_B}.jsonl",
                          [{"type": "user", "timestamp": _ts(2)}])
        res = session_source.catalogue(target, projects_root=root, now=NOW)
        assert res.entries  # precondition
        by_slug = {e.slug: e.session_id for e in res.entries}
        assert by_slug == {main_slug: UUID_A, wt_slug: UUID_B}

    def test_finds_sessions_across_new_and_draining_worktree_roots(
            self, tmp_path):
        target, root = _cat_target(tmp_path, worktrees=["lane-old"])
        new_lane = tmp_path / ".worktrees" / "lane-new"
        new_lane.mkdir(parents=True)
        old_lane = target / ".worktrees" / "lane-old"
        new_slug, old_slug = _slug(new_lane), _slug(old_lane)
        _write_transcript(root / new_slug / f"{UUID_A}.jsonl",
                          [{"type": "user", "timestamp": _ts(2)}])
        _write_transcript(root / old_slug / f"{UUID_B}.jsonl",
                          [{"type": "user", "timestamp": _ts(2)}])
        res = session_source.catalogue(target, projects_root=root, now=NOW)
        by_slug = {e.slug: e.session_id for e in res.entries}
        assert by_slug == {new_slug: UUID_A, old_slug: UUID_B}, \
            "session catalogue dropped one worktree root"

    def test_a_target_with_no_sessions_is_ok_but_empty(self, tmp_path):
        target, root = _cat_target(tmp_path)
        (root / _slug(target)).mkdir()  # slug dir exists, holds no sessions
        res = session_source.catalogue(target, projects_root=root, now=NOW)
        assert res.status == "ok"
        assert res.entries == []

    def test_an_unrelated_targets_sessions_are_not_listed(self, tmp_path):
        # A different target's slug dir must not bleed into this target's list.
        target, root = _cat_target(tmp_path)
        other = tmp_path / "other-target"
        other.mkdir()
        _write_transcript(root / _slug(other) / f"{UUID_A}.jsonl",
                          [{"type": "user", "timestamp": _ts(2)}])
        res = session_source.catalogue(target, projects_root=root, now=NOW)
        assert res.status == "ok"
        assert res.entries == []  # the other target's session is not ours


class TestCatalogueStrictUuidRejection:
    """Direction 2: names a loose `endswith('.jsonl')` check admits but a strict
    full-string uuid check rejects. The wire id selects the file, so a name the
    filter passes is a name the server may open. Production line:
    `_session_uuid`."""

    @pytest.mark.parametrize("bad_name", [
        "550e8400-e29b-41d4-a716-446655440000-evil.jsonl",  # uuid prefix + tail
        "evil-550e8400-e29b-41d4-a716-446655440000.jsonl",  # head + uuid
        "550e8400-e29b-41d4-a716-446655440000.JSONL",        # wrong case ext
        "not-a-uuid.jsonl",                                   # non-uuid stem
        "memory",                                             # a chrome dir name
        "..jsonl",                                            # traversal-shaped
    ])
    def test_a_loose_name_is_not_listed(self, tmp_path, bad_name):
        target, root = _cat_target(tmp_path)
        slug = _slug(target)
        (root / slug).mkdir(exist_ok=True)
        p = root / slug / bad_name
        if "." not in bad_name or bad_name.endswith(".jsonl"):
            p.write_text('{"type": "user"}\n')
        else:
            p.mkdir()
        # one clean session so the precondition (non-empty catalogue) holds and
        # we are asserting the BAD name is absent, not that everything is.
        _write_transcript(root / slug / f"{UUID_A}.jsonl",
                          [{"type": "user", "timestamp": _ts(2)}])
        res = session_source.catalogue(target, projects_root=root, now=NOW)
        assert res.entries  # precondition
        ids = {e.session_id for e in res.entries}
        assert UUID_A in ids
        # No entry's id is derived from the adversarial name — the loose name
        # produced no entry at all.
        assert all(e.session_id == UUID_A for e in res.entries)


class TestCatalogueSymlinkConfinement:
    """Confinement: links resolved FIRST, then confined. A symlink whose NAME is
    a clean uuid but whose TARGET leaves the root must be dropped; confining the
    name first and resolving after admits it. Production line:
    `_confined_to_root` (resolve-before-confine order)."""

    def test_a_symlinked_projects_root_is_catalogued(self, tmp_path):
        # #698: the real projects root is itself a symlink. Discovery must
        # follow it (the find-without-L trap), and confinement must still hold.
        real = tmp_path / "real-projects"
        target = tmp_path / "target"
        target.mkdir()
        slug = _slug(target)
        _write_transcript(real / slug / f"{LIVE_ID}.jsonl",
                          [{"type": "user", "timestamp": _ts(2)}])
        link = tmp_path / "link-projects"
        os.symlink(real, link)
        res = session_source.catalogue(target, projects_root=link, now=NOW)
        assert res.entries  # precondition
        assert res.entries[0].session_id == LIVE_ID

    def test_a_clean_named_symlink_pointing_outside_root_is_dropped(
            self, tmp_path):
        # The NAME is a valid uuid; the target is a file OUTSIDE the root. This
        # is the directory-traversal primitive the confinement gate exists for.
        target, root = _cat_target(tmp_path)
        slug = _slug(target)
        (root / slug).mkdir(parents=True, exist_ok=True)
        secret = tmp_path / "secret-outside-root"
        secret.write_text("SENSITIVE")
        os.symlink(secret, root / slug / f"{OTHER_ID}.jsonl")
        _write_transcript(root / slug / f"{UUID_A}.jsonl",
                          [{"type": "user", "timestamp": _ts(2)}])
        res = session_source.catalogue(target, projects_root=root, now=NOW)
        assert res.entries  # precondition
        ids = {e.session_id for e in res.entries}
        assert UUID_A in ids
        assert OTHER_ID not in ids  # the escape was dropped, not opened
        assert "dropped" in res.detail  # the filter is reported, not silent


class TestCatalogueEmptyVsUnmeasured:
    """#136/#671: an empty catalogue over an EMPTY root and one over a root the
    resolver FAILED to measure are different facts that must not render
    identically. Production line: the `projects_root is None / not is_dir`
    branch returning `unmeasured`."""

    def test_an_empty_measured_root_is_ok(self, tmp_path):
        target, root = _cat_target(tmp_path)
        (root / _slug(target)).mkdir()
        res = session_source.catalogue(target, projects_root=root, now=NOW)
        assert res.status == "ok"
        assert res.entries == []

    def test_a_missing_root_is_unmeasured(self, tmp_path):
        target = tmp_path / "target"
        target.mkdir()
        res = session_source.catalogue(
            target, projects_root=tmp_path / "does-not-exist", now=NOW)
        assert res.status == "unmeasured"
        assert res.entries == []

    def test_the_two_findings_render_differently(self, tmp_path):
        # The load-bearing #136 assertion: distinct nothings stay distinct.
        target = tmp_path / "target"
        target.mkdir()
        empty_root = tmp_path / "projects"
        (empty_root / _slug(target)).mkdir(parents=True)
        ok = session_source.catalogue(target, projects_root=empty_root, now=NOW)
        unmeasured = session_source.catalogue(
            target, projects_root=tmp_path / "nope", now=NOW)
        assert ok.status != unmeasured.status
        assert "could not be measured" in unmeasured.detail
        assert "could not be measured" not in ok.detail


class TestCatalogueActiveIdentity:
    """The recorded `agent_session` is the ONLY active identity; newest-mtime is
    never promoted. Production line: the `active=(uid == active_id)` assignment
    in `catalogue`."""

    def test_the_recorded_id_is_marked_active_even_when_older(self, tmp_path):
        # Two live sessions. The RECORDED id is the OLDER one (earlier mtime).
        # Active must follow the id, not the mtime.
        target, root = _cat_target(tmp_path)
        slug = _slug(target)
        older = root / slug / f"{UUID_A}.jsonl"
        newer = root / slug / f"{UUID_B}.jsonl"
        _write_transcript(older, [{"type": "user", "timestamp": _ts(5)}])
        _write_transcript(newer, [{"type": "user", "timestamp": _ts(2)}])
        # Pin mtimes so 'newest mtime' is unambiguous and genuinely UUID_B.
        old_mt = NOW.timestamp() - 600
        new_mt = NOW.timestamp() - 60
        os.utime(older, (old_mt, old_mt))
        os.utime(newer, (new_mt, new_mt))
        res = session_source.catalogue(
            target, projects_root=root, now=NOW, active_id=UUID_A)
        assert len(res.entries) == 2  # precondition: both candidates present
        by_id = {e.session_id: e for e in res.entries}
        assert by_id[UUID_A].active is True   # recorded id wins
        assert by_id[UUID_B].active is False  # newer mtime does NOT win
        assert by_id[UUID_B].mtime > by_id[UUID_A].mtime  # mtime is genuinely newer

    def test_with_no_recorded_id_nothing_is_active(self, tmp_path):
        target, root = _cat_target(tmp_path)
        slug = _slug(target)
        _write_transcript(root / slug / f"{UUID_A}.jsonl",
                          [{"type": "user", "timestamp": _ts(2)}])
        res = session_source.catalogue(target, projects_root=root, now=NOW)
        assert res.entries  # precondition
        assert all(not e.active for e in res.entries)
        assert res.active_id is None


class TestCatalogueNoWirePath:
    """Confinement assertion: the wire catalogue carries NO absolute path. A
    path the browser can read is a directory-traversal primitive against real
    session content; the wire shape carries an opaque id the server resolves.
    Production line: `CatalogEntry` having no path field."""

    def test_no_entry_exposes_a_path_field(self, tmp_path):
        from dataclasses import fields, astuple
        target, root = _cat_target(tmp_path)
        slug = _slug(target)
        _write_transcript(root / slug / f"{LIVE_ID}.jsonl",
                          [{"type": "user", "timestamp": _ts(2)}])
        res = session_source.catalogue(target, projects_root=root, now=NOW)
        assert res.entries  # precondition
        for e in res.entries:
            names = {f.name for f in fields(e)}
            assert "path" not in names, "CatalogEntry must not carry a path"
            for val in astuple(e):
                assert not isinstance(val, Path), \
                    "no field may hold a Path"
                if isinstance(val, str):
                    assert not val.startswith("/"), \
                        "no field may hold an absolute path string"


class TestCatalogueLiveness:
    """`live` is a claim at scan time over the stale_after window; the age is
    carried so a consumer can re-judge. Production line: the
    `last is not None and age <= stale_after` branch."""

    def test_a_fresh_session_is_live_and_carries_its_age(self, tmp_path):
        target, root = _cat_target(tmp_path)
        slug = _slug(target)
        _write_transcript(root / slug / f"{LIVE_ID}.jsonl",
                          [{"type": "user", "timestamp": _ts(3)}])
        res = session_source.catalogue(target, projects_root=root, now=NOW)
        assert res.entries  # precondition
        e = res.entries[0]
        assert e.live is True
        assert e.age_seconds is not None
        assert e.last_record_at is not None

    def test_a_stale_session_is_not_live_and_names_the_age(self, tmp_path):
        target, root = _cat_target(tmp_path)
        slug = _slug(target)
        _write_transcript(root / slug / f"{STALE_ID}.jsonl",
                          [{"type": "user", "timestamp": _ts(120)}])
        res = session_source.catalogue(target, projects_root=root, now=NOW)
        assert res.entries  # precondition
        e = res.entries[0]
        assert e.live is False
        assert "stale" in e.detail
        # age carried so a consumer can re-judge as `now` advances (#765 shape)
        assert e.age_seconds is not None and e.age_seconds > 0
