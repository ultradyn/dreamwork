"""Tests for the questions import/verify unit (#645 increment 8).

Three things this suite proves, and each test names what it would catch:

1. **Import is correct.** Every content field round-trips through the store.
2. **Import is idempotent.** A second import of the same manifest reports
   every entry as ``unchanged`` and writes nothing — verified independently.
3. **Verification is independent.** It catches a modified store the importer
   would overwrite, a short-circuit importer that never looked, and an empty
   store that imported "successfully" under any implementation.

Direction 1 red-proofs inject a real defect and watch the check go red on
the discriminating message.  Direction 2 constructs implementations that
pass the wrong thing and shows what the verifier decides.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from dreamwork_db import Access, open_database
from dreamwork_db.question_parse import question_manifest
from dreamwork_db.questions import (
    EntryOutcome,
    FieldDelta,
    ImportResult,
    QuestionRepository,
    StoredSnapshot,
    VerificationResult,
    extract_priority,
    question_store_spec,
    verify_import,
)


# ─── fixtures ──────────────────────────────────────────────────────────────

SIMPLE_FIXTURE = (
    "# Questions\n\n"
    "## Open\n\n"
    "- **P1 · 2026-08-01 21:45 — #500: first question.**\n"
    "  Body of the first question.\n"
    "\n"
    "- **2026-08-01 — #501: second question, no priority.**\n"
    "  Body of the second.\n"
    "  - **Note (human, 2026-08-01 22:00):** a note on the second.\n"
    "\n"
    "## Answered\n\n"
    "- **P2 · 2026-07-31 — #502: answered question.**\n"
    "  → resolved (2026-07-31 18:00): the answer.\n"
    "\n"
    "- **P3 · 2026-07-30 — #503: answered with no resolution date.**\n"
    "  This is in the Answered section but has no → head.\n"
)

DATELESS_FIXTURE = (
    "# Questions\n\n"
    "## Open\n\n"
    "- **P1 · 2026-08-01 — #572: open question.**\n"
    "  Body.\n"
    "\n"
    "## Answered\n\n"
    "- **P1 · 2026-07-31 — #572: answered with no date.**\n"
    "  No resolution head here.\n"
    "\n"
    "- **P2 · 2026-07-31 — #613: also no date.**\n"
    "  Also no resolution head.\n"
    "\n"
    "- **P3 · 2026-07-30 — #614: third dateless.**\n"
    "  Three dateless answered entries.\n"
)


def _manifest(text: str):
    """Parse fixture text into a manifest."""
    return question_manifest(text.encode("utf-8"))


@pytest.fixture
def scratch_store():
    """A fresh empty store with the question schema, cleaned up after."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "scratch.sqlite3"
        # First WRITE open creates the schema (runs the migration ladder)
        with open_database(question_store_spec(path), access=Access.WRITE) as db:
            with db.transaction():
                pass  # empty transaction to trigger schema creation
        yield path


def _import(manifest, path, *, actor="migration", at="2026-08-01T00:00:00+00:00"):
    """Open, import, return the ImportResult."""
    with open_database(question_store_spec(path), access=Access.WRITE) as db:
        with db.transaction() as tx:
            return tx.questions.import_manifest(manifest, actor=actor, at=at)


def _snapshot(path) -> StoredSnapshot:
    """Open READ, return the snapshot."""
    with open_database(question_store_spec(path), access=Access.READ) as db:
        return db.questions.snapshot()


def _sabotage(path, sql, params=()):
    """Execute raw SQL against the scratch store for test sabotage.

    Tests are explicitly exempt from test_no_raw_connect.py — its purpose is
    to corrupt and tamper with fixtures, which is what deliberate sabotage
    for red-proofing is.  Production code routes through dreamwork_db.core;
    test code reaches the same bytes through a different door.
    """
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


# ─── basic import ──────────────────────────────────────────────────────────

class TestBasicImport:
    """Import into an empty scratch store and read back every field."""

    def test_all_entries_inserted(self, scratch_store):
        m = _manifest(SIMPLE_FIXTURE)
        result = _import(m, scratch_store)
        assert len(result.inserted) == len(m.entries)
        assert result.ok

    def test_question_count_matches_manifest(self, scratch_store):
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)
        snap = _snapshot(scratch_store)
        assert len(snap.questions) == len(m.entries)

    def test_titles_round_trip(self, scratch_store):
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)
        snap = _snapshot(scratch_store)
        for entry, sq in zip(m.entries, snap.questions):
            assert entry.title == sq.title

    def test_bodies_round_trip(self, scratch_store):
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)
        snap = _snapshot(scratch_store)
        for entry, sq in zip(m.entries, snap.questions):
            assert entry.body_markdown == sq.body_markdown

    def test_status_round_trip(self, scratch_store):
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)
        snap = _snapshot(scratch_store)
        for entry, sq in zip(m.entries, snap.questions):
            assert entry.state == sq.status

    def test_priority_round_trip(self, scratch_store):
        """Priority extracted from the title is stored in the column."""
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)
        snap = _snapshot(scratch_store)
        for entry, sq in zip(m.entries, snap.questions):
            assert extract_priority(entry.title) == sq.priority

    def test_no_priority_is_null_not_defaulted(self, scratch_store):
        """An entry with no P-band gets priority=NULL, not a default."""
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)
        snap = _snapshot(scratch_store)
        # #501 has no priority prefix
        no_pri = [sq for sq in snap.questions if "#501" in sq.title]
        assert len(no_pri) == 1
        assert no_pri[0].priority is None

    def test_asked_at_round_trip(self, scratch_store):
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)
        snap = _snapshot(scratch_store)
        for entry, sq in zip(m.entries, snap.questions):
            assert entry.asked_at == sq.asked_at
            assert entry.asked_precision == sq.asked_precision

    def test_messages_round_trip(self, scratch_store):
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)
        snap = _snapshot(scratch_store)
        # #501 has one note
        q501 = [sq for sq in snap.questions if "#501" in sq.title][0]
        msgs = [sm for sm in snap.messages if sm.question_id == q501.id]
        assert len(msgs) == 1
        assert msgs[0].kind == "note"
        assert msgs[0].author == "human"

    def test_no_extra_questions(self, scratch_store):
        m = _manifest(SIMPLE_FIXTURE)
        result = _import(m, scratch_store)
        assert result.extra_question_ids == ()


# ─── idempotence ───────────────────────────────────────────────────────────

class TestIdempotence:
    """A second import of the same manifest reports all unchanged, writes
    nothing, and the independent verifier agrees."""

    def test_second_import_all_unchanged(self, scratch_store):
        m = _manifest(SIMPLE_FIXTURE)
        first = _import(m, scratch_store)
        assert len(first.inserted) == len(m.entries)

        second = _import(m, scratch_store)
        assert len(second.unchanged) == len(m.entries)
        assert len(second.inserted) == 0
        assert len(second.conflicts) == 0
        assert second.ok

    def test_second_import_writes_nothing(self, scratch_store):
        """The store is byte-identical after the second import."""
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)
        snap1 = _snapshot(scratch_store)

        _import(m, scratch_store)
        snap2 = _snapshot(scratch_store)

        assert snap1.questions == snap2.questions
        assert snap1.messages == snap2.messages

    def test_verify_agrees_on_idempotent_reimport(self, scratch_store):
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)
        _import(m, scratch_store)

        snap = _snapshot(scratch_store)
        vr = verify_import(m, snap)
        assert vr.ok
        assert len(vr.matching) == len(m.entries)

    def test_three_imports_stable(self, scratch_store):
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)
        _import(m, scratch_store)
        third = _import(m, scratch_store)
        assert len(third.unchanged) == len(m.entries)


# ─── conflict detection (never repair-by-overwrite) ────────────────────────

class TestConflictDetection:
    """When the store drifts, the importer names the conflict and does NOT
    overwrite.  The independent verifier agrees."""

    def test_modified_title_is_named_conflict_not_overwrite(self, scratch_store):
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)

        # sabotage: change a stored title directly
        _sabotage(scratch_store,
                  "UPDATE question SET title = 'SABOTAGED' WHERE id = 1")

        result = _import(m, scratch_store)
        conflicts = result.conflicts
        assert len(conflicts) == 1
        delta_fields = [d.field for d in conflicts[0].deltas]
        assert "title" in delta_fields

        # the title was NOT overwritten back
        snap = _snapshot(scratch_store)
        assert snap.questions[0].title == "SABOTAGED"

    def test_verify_catches_modified_title(self, scratch_store):
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)

        _sabotage(scratch_store,
                  "UPDATE question SET title = 'SABOTAGED' WHERE id = 1")

        snap = _snapshot(scratch_store)
        vr = verify_import(m, snap)
        assert not vr.ok
        title_conflicts = [
            e for e in vr.conflicts
            if any(d.field == "title" for d in e.deltas)
        ]
        assert len(title_conflicts) == 1

    def test_modified_body_is_named_conflict(self, scratch_store):
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)

        _sabotage(scratch_store,
                  "UPDATE question SET body_markdown = 'truncated'"
                  " WHERE id = 1")

        result = _import(m, scratch_store)
        assert len(result.conflicts) == 1
        delta_fields = [d.field for d in result.conflicts[0].deltas]
        assert "body_markdown" in delta_fields

    def test_added_question_after_import_is_extra(self, scratch_store):
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)

        _sabotage(scratch_store,
                  "INSERT INTO question"
                  " (status, title, body_markdown, asked_precision,"
                  "  created_by, created_at, updated_at)"
                  " VALUES ('unanswered', 'extra', 'x', 'unknown',"
                  " 'test', 't', 't')")

        result = _import(m, scratch_store)
        assert len(result.extra_question_ids) == 1

        snap = _snapshot(scratch_store)
        vr = verify_import(m, snap)
        assert not vr.ok
        assert len(vr.extra_question_ids) == 1


# ─── dateless entries (the first real conflict case) ───────────────────────

class TestDatelessEntries:
    """The three Answered entries with no resolution date (#572/#613/#614)
    have null asked_at fields and no → head in their bodies.  The import
    must preserve nullness, not default it."""

    def test_dateless_entries_imported(self, scratch_store):
        m = _manifest(DATELESS_FIXTURE)
        _import(m, scratch_store)
        snap = _snapshot(scratch_store)
        answered = [sq for sq in snap.questions if sq.status == "answered"]
        assert len(answered) == 3

    def test_dateless_asked_at_preserved(self, scratch_store):
        """Asked_at is present in the title, so it is NOT null for these.
        The resolution_date (parsed from the body) IS absent, but it is
        not a column — it lives in body_markdown, which is stored verbatim.
        This test confirms the body is stored exactly."""
        m = _manifest(DATELESS_FIXTURE)
        _import(m, scratch_store)
        snap = _snapshot(scratch_store)
        for entry, sq in zip(m.entries, snap.questions):
            assert entry.body_markdown == sq.body_markdown

    def test_dateless_bodies_have_no_arrow_head(self, scratch_store):
        """The three dateless answered bodies contain no → resolution head.
        The import stores the body verbatim; no date is invented."""
        m = _manifest(DATELESS_FIXTURE)
        _import(m, scratch_store)
        snap = _snapshot(scratch_store)
        answered = [sq for sq in snap.questions if sq.status == "answered"]
        for sq in answered:
            assert "→" not in sq.body_markdown

    def test_dateless_idempotent(self, scratch_store):
        """Re-importing the dateless fixture is idempotent — null stays null."""
        m = _manifest(DATELESS_FIXTURE)
        _import(m, scratch_store)
        second = _import(m, scratch_store)
        assert len(second.unchanged) == len(m.entries)
        assert second.ok

    def test_dateless_verify_clean(self, scratch_store):
        m = _manifest(DATELESS_FIXTURE)
        _import(m, scratch_store)
        snap = _snapshot(scratch_store)
        vr = verify_import(m, snap)
        assert vr.ok

    def test_null_asked_at_preserved_not_defaulted(self, scratch_store):
        """An entry with no date in its title gets asked_at=NULL, not today."""
        fixture = (
            "## Open\n\n"
            "- **No date, no priority.**\n"
            "  Body.\n"
            "\n"
            "## Answered\n"
        )
        m = _manifest(fixture)
        _import(m, scratch_store)
        snap = _snapshot(scratch_store)
        assert snap.questions[0].asked_at is None
        assert snap.questions[0].asked_precision == "unknown"


# ─── independent verification (#759) ───────────────────────────────────────

class TestIndependentVerification:
    """The verifier reads the DB independently and does not trust the
    importer's own claims."""

    def test_verify_matches_on_clean_import(self, scratch_store):
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)
        snap = _snapshot(scratch_store)
        vr = verify_import(m, snap)
        assert vr.ok
        assert len(vr.matching) == len(m.entries)
        assert vr.conflicts == ()
        assert vr.extra_question_ids == ()

    def test_verify_catches_truncated_body(self, scratch_store):
        """Direction 1 red-proof: a truncated body is a named conflict."""
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)

        _sabotage(scratch_store,
                  "UPDATE question SET body_markdown = 'short'"
                  " WHERE id = 1")

        snap = _snapshot(scratch_store)
        vr = verify_import(m, snap)
        assert not vr.ok
        body_conflicts = [
            e for e in vr.conflicts
            if any(d.field == "body_markdown" for d in e.deltas)
        ]
        assert len(body_conflicts) == 1

    def test_verify_catches_dropped_message(self, scratch_store):
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)

        _sabotage(scratch_store, "DELETE FROM question_message WHERE id = 1")

        snap = _snapshot(scratch_store)
        vr = verify_import(m, snap)
        assert not vr.ok
        # a dropped message is caught — as conflict or cannot_tell depending
        # on how many remain (message_count delta fires either way)
        msg_issues = [
            e for e in (vr.conflicts + vr.cannot_tell)
            if any("message_count" in d.field for d in e.deltas)
        ]
        assert len(msg_issues) >= 1

    def test_verify_denominators_are_reported(self, scratch_store):
        """#671: the verifier reports source denominators, not just pass/fail."""
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)
        snap = _snapshot(scratch_store)
        vr = verify_import(m, snap)
        assert vr.question_count_manifest == len(m.entries)
        assert vr.question_count_stored == len(m.entries)
        assert vr.denominator_source_bytes == m.source_bytes


# ─── the short-circuit trap (Direction 2) ──────────────────────────────────

class TestShortCircuitTrap:
    """An importer that short-circuits on "destination already has rows"
    passes every idempotence test and silently skips genuine conflicts.

    The brief's key point: construct that implementation and show what the
    independent check decides.  If it passes, the check is measuring the
    short-circuit, not the import.
    """

    def test_short_circuit_returns_unchanged_without_looking(self, scratch_store):
        """A short-circuiting importer returns 'all unchanged' even when
        the store has drifted.  The independent verifier catches what it
        skipped."""
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)

        # drift: modify a title after import
        _sabotage(scratch_store,
                  "UPDATE question SET title = 'DRIFTED' WHERE id = 1")

        # a short-circuit importer: counts rows, sees >0, reports unchanged
        short_circuit_result = _short_circuit_import(m, scratch_store)
        assert len(short_circuit_result.unchanged) == len(m.entries)
        assert short_circuit_result.ok  # the short-circuit LIES

        # the independent verifier tells the truth
        snap = _snapshot(scratch_store)
        vr = verify_import(m, snap)
        assert not vr.ok
        assert len(vr.conflicts) >= 1
        title_conflicts = [
            e for e in vr.conflicts
            if any(d.field == "title" for d in e.deltas)
        ]
        assert len(title_conflicts) == 1

    def test_real_importer_does_not_short_circuit(self, scratch_store):
        """The production importer looks at every field and catches the
        drift — it does NOT short-circuit."""
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)

        _sabotage(scratch_store,
                  "UPDATE question SET title = 'DRIFTED' WHERE id = 1")

        result = _import(m, scratch_store)
        # the real importer caught it
        assert len(result.conflicts) == 1
        assert not result.ok


def _short_circuit_import(manifest, path) -> ImportResult:
    """A deliberately broken importer that short-circuits on row count.

    This is the implementation the brief asks us to construct: it checks
    whether the destination already has rows, and if so, returns 'all
    unchanged' without comparing any field.  It passes every idempotence
    test because the second import never looks at the data.
    """
    with open_database(question_store_spec(path), access=Access.READ) as db:
        n = db.questions.count_questions()

    if n > 0:
        return ImportResult(
            entries=tuple(
                EntryOutcome(ordinal=i + 1, disposition="unchanged",
                             question_id=i + 1)
                for i in range(len(manifest.entries))
            ),
            extra_question_ids=(),
            extra_message_ids=(),
        )
    return _import(manifest, path)


# ─── empty-store proof (#651, #671) ────────────────────────────────────────

class TestEmptyStoreProof:
    """An empty scratch store imports 'successfully' under almost any
    implementation.  The verifier must say what it can and cannot establish
    over a zero-row destination."""

    def test_verify_empty_store_is_refusal_not_pass(self, scratch_store):
        """#671: a non-empty source over an empty store is a REFUSAL."""
        m = _manifest(SIMPLE_FIXTURE)
        snap = StoredSnapshot(questions=(), messages=())
        vr = verify_import(m, snap)
        assert not vr.ok
        assert vr.empty_source_refusal
        assert vr.question_count_manifest == len(m.entries)
        assert vr.question_count_stored == 0

    def test_verify_empty_source_empty_store_is_match(self, scratch_store):
        """A genuinely empty source over an empty store IS a match."""
        empty_manifest = question_manifest(b"## Open\n\n## Answered\n")
        snap = StoredSnapshot(questions=(), messages=())
        vr = verify_import(empty_manifest, snap)
        assert vr.ok
        assert not vr.empty_source_refusal
        assert vr.question_count_manifest == 0

    def test_import_then_verify_establishes_match(self, scratch_store):
        """After a real import, verify CAN establish a match — the empty-store
        refusal does not persist once data exists."""
        m = _manifest(SIMPLE_FIXTURE)
        _import(m, scratch_store)
        snap = _snapshot(scratch_store)
        vr = verify_import(m, snap)
        assert vr.ok
        assert not vr.empty_source_refusal
        assert vr.question_count_stored == len(m.entries)


# ─── the no-raw-connect door ────────────────────────────────────────────────

class TestNoRawConnect:
    """The import module routes through dreamwork_db.core — no raw
    sqlite3.connect.  test_no_raw_connect.py enforces this for all
    production sources; this test confirms the module is part of that set."""

    def test_questions_py_has_no_raw_connect(self):
        """The module source contains no sqlite3.connect call."""
        import dreamwork_db.questions as mod
        source = Path(mod.__file__).read_text()
        assert "sqlite3.connect" not in source
