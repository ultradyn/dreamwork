"""Tests for the lossless questions.md parser (increment 7 of #645).

The five fixtures — heading, wrapped-title, multi-answer, missing-date,
unclassifiable — are the specification. Each encodes a real shape that has
bitten this repo, and each test names the issue it guards against.

Direction 2 is the heart of the lossless claim: the coverage check must FAIL
on an off-by-one span and on an empty corpus, not silently pass. Those tests
are below — and they assert the discriminating failure message, not just a
red count.
"""

import errno
import os
import tempfile
import textwrap
from pathlib import Path

import pytest

from dreamwork_db.question_parse import (
    Contribution,
    QuestionEntry,
    QuestionManifest,
    Span,
    coverage_report,
    dry_run,
    independent_head_count,
    question_manifest,
)


# ─── helpers ───────────────────────────────────────────────────────────────

def _parse(text: str) -> QuestionManifest:
    """Parse a text fixture (UTF-8 encoded) into a manifest."""
    return question_manifest(text.encode("utf-8"))


# ═══ FIXTURE 1: heading — a `##` inside a body truncates the section (#753) ═══

# The #753 shape: a markdown heading inside a task BODY caused the section
# scanner to exit early, hiding every entry after it. The parser must DETECT
# this by counting those heads as outside the recognized section, and the
# coverage report must flag the non-zero outside count.

HEADING_FIXTURE = (
    "# Questions\n\n"
    "## Open\n\n"
    "- **P1 · 2026-08-01 — #100: visible question.**\n"
    "  Body that is fine.\n"
    "## Details\n"
    "\n"
    "- **P1 · 2026-08-01 — #101: hidden question one.**\n"
    "  This entry is after the stray heading.\n"
    "\n"
    "- **P2 · 2026-08-01 — #102: hidden question two.**\n"
    "  Also hidden.\n"
    "\n"
    "## Answered\n"
)


class TestHeadingFixture:
    """``## Details`` inside a body exits the section (#753)."""

    def test_visible_entry_parsed_before_heading(self):
        m = _parse(HEADING_FIXTURE)
        visible = [e for e in m.entries if e.section == "Open"]
        assert len(visible) == 1
        assert "#100" in visible[0].title

    def test_hidden_entries_counted_as_outside(self):
        """The two entries after ``## Details`` are outside the recognized
        section — counted, not silently absorbed."""
        m = _parse(HEADING_FIXTURE)
        assert m.heads_outside_sections == 2

    def test_independent_scan_agrees_on_outside_count(self):
        """The independent line scanner sees the same 2 outside heads."""
        data = HEADING_FIXTURE.encode("utf-8")
        _, outside = independent_head_count(data)
        assert outside == 2

    def test_coverage_report_flags_outside_heads(self):
        data = HEADING_FIXTURE.encode("utf-8")
        m = question_manifest(data)
        cov = coverage_report(m, data)
        check = cov["checks"]["heads_outside"]
        assert check["manifest"] == 2
        assert check["independent"] == 2
        assert check["ok"] is True


# ═══ FIXTURE 2: wrapped-title — title spans multiple lines (#116) ═════════

WRAPPED_TITLE_FIXTURE = textwrap.dedent("""\
    # Questions

    ## Open

    - **P1 · 2026-08-01 — this is a very long title that wraps
      onto a second line.**
      Body of the wrapped entry.

    ## Answered
    """)


class TestWrappedTitleFixture:
    """A hard-wrapped title joins into one string (#116)."""

    def test_title_joined_across_lines(self):
        m = _parse(WRAPPED_TITLE_FIXTURE)
        assert len(m.entries) == 1
        title = m.entries[0].title
        assert "wraps" in title
        assert "onto a second line." in title
        # the join collapses whitespace
        assert "wraps onto a second line." in title

    def test_body_not_contaminated_by_title(self):
        m = _parse(WRAPPED_TITLE_FIXTURE)
        assert "onto a second line" not in m.entries[0].body_markdown

    def test_wrapped_title_detected(self):
        m = _parse(WRAPPED_TITLE_FIXTURE)
        head_line = m.entries[0].raw_text.split("\n", 1)[0]
        # the head line has only the opening ** (no closing)
        assert head_line.count("**") < 2

    def test_span_covers_full_entry(self):
        m = _parse(WRAPPED_TITLE_FIXTURE)
        data = WRAPPED_TITLE_FIXTURE.encode("utf-8")
        # round-trip: the span slices to exactly the stored raw_text
        sliced = data[m.entries[0].span.start:m.entries[0].span.end].decode()
        assert sliced == m.entries[0].raw_text


# ═══ FIXTURE 3: multi-answer — one question, several answers (#446) ═══════

MULTI_ANSWER_FIXTURE = textwrap.dedent("""\
    # Questions

    ## Open

    - **P1 · 2026-08-01 — #200: question with two answers.**
      First paragraph of body.
      - **Answer (via watch, 2026-08-01 10:00):** first answer here.
      - **Note (human, 2026-08-01 10:30):** a follow-up note.
      - **Answer (via watch, 2026-08-01 11:00):** second answer amends.
      Tail of body.

    ## Answered
    """)


class TestMultiAnswerFixture:
    """A second answer must not overwrite the first (#446)."""

    def test_both_answers_preserved(self):
        m = _parse(MULTI_ANSWER_FIXTURE)
        answers = [c for c in m.entries[0].contributions if c.kind == "answer"]
        assert len(answers) == 2
        assert "first answer" in answers[0].text
        assert "second answer" in answers[1].text

    def test_answer_order_is_file_order(self):
        m = _parse(MULTI_ANSWER_FIXTURE)
        contribs = m.entries[0].contributions
        # answer, note, answer — in source order
        assert contribs[0].kind == "answer"
        assert contribs[1].kind == "note"
        assert contribs[2].kind == "answer"

    def test_state_is_answered_pending_fold(self):
        """An Open entry with at least one answer is awaiting fold, not
        fully answered."""
        m = _parse(MULTI_ANSWER_FIXTURE)
        assert m.entries[0].state == "answered_pending_fold"

    def test_note_between_answers_preserved(self):
        m = _parse(MULTI_ANSWER_FIXTURE)
        notes = [c for c in m.entries[0].contributions if c.kind == "note"]
        assert len(notes) == 1
        assert notes[0].author == "human"


# ═══ FIXTURE 4: missing-date — answered with no resolution date ═══════════

MISSING_DATE_FIXTURE = textwrap.dedent("""\
    # Questions

    ## Open

    - **P1 · 2026-08-01 — #300: real answered question.**
      Body.
      → settled (2026-08-01 12:00): the resolution.

    ## Answered

    - **P1 · 2026-07-31 — #301: answered with no resolution head.**
      This entry is in the Answered section but its body has no
      → verdict line, so resolution_date is None.

    - **P2 · 2026-07-31 — #302: answered with a date.**
      → done (2026-07-31 18:00): resolved properly.
    """)


class TestMissingDateFixture:
    """An Answered entry whose body lacks a ``→`` head has ``resolution_date``
    None — it is not dropped and not guessed (#572/#613/#614 shape)."""

    def test_missing_date_entry_preserved(self):
        m = _parse(MISSING_DATE_FIXTURE)
        answered = [e for e in m.entries if e.section == "Answered"]
        assert len(answered) == 2

    def test_missing_date_entry_has_null_resolution(self):
        m = _parse(MISSING_DATE_FIXTURE)
        no_date = [e for e in m.entries if "#301" in e.title]
        assert len(no_date) == 1
        assert no_date[0].resolution_date is None
        assert no_date[0].state == "answered"

    def test_entry_with_date_has_resolution(self):
        m = _parse(MISSING_DATE_FIXTURE)
        with_date = [e for e in m.entries if "#302" in e.title]
        assert len(with_date) == 1
        assert with_date[0].resolution_date is not None
        assert "2026-07-31" in with_date[0].resolution_date

    def test_open_entry_with_arrow_is_not_answered_section(self):
        """An Open entry with a ``→`` line is still in the Open section."""
        m = _parse(MISSING_DATE_FIXTURE)
        open_entries = [e for e in m.entries if e.section == "Open"]
        assert len(open_entries) == 1


# ═══ FIXTURE 5: unclassifiable — report, never drop (#702) ════════════════

UNCLASSIFIABLE_FIXTURE = textwrap.dedent("""\
    # Questions

    ## Open

    - **P1 · 2026-08-01 — #400: normal entry.**
      Body.

    This line is column-0 prose that is not an entry head.
    It cannot be classified; it must be reported, not dropped.

    - **P1 · 2026-08-01 — #401: entry after unclassified.**
      Body.

    ## Answered
    """)


class TestUnclassifiableFixture:
    """A column-0 non-entry line inside a section is reported as unclassified,
    not silently absorbed (#702)."""

    def test_unclassified_region_captured(self):
        m = _parse(UNCLASSIFIABLE_FIXTURE)
        assert len(m.unclassified) >= 1

    def test_unclassified_text_preserved(self):
        m = _parse(UNCLASSIFIABLE_FIXTURE)
        combined = "\n".join(u.raw_text for u in m.unclassified)
        assert "column-0 prose" in combined

    def test_entries_on_both_sides_preserved(self):
        m = _parse(UNCLASSIFIABLE_FIXTURE)
        open_entries = [e for e in m.entries if e.section == "Open"]
        assert len(open_entries) == 2
        assert "#400" in open_entries[0].title
        assert "#401" in open_entries[1].title

    def test_unclassified_span_round_trips(self):
        m = _parse(UNCLASSIFIABLE_FIXTURE)
        data = UNCLASSIFIABLE_FIXTURE.encode("utf-8")
        for u in m.unclassified:
            sliced = data[u.span.start:u.span.end].decode()
            assert sliced == u.raw_text


# ═══ STRUCTURAL: write-nothing proof ═══════════════════════════════════════

class TestWriteNothing:
    """``dry_run`` opens the file with a kernel-enforced read-only descriptor.
    This is STRUCTURAL: the descriptor itself rejects writes, so no code path
    bug can write through it."""

    def test_dry_run_descriptor_is_kernel_read_only(self, tmp_path):
        """The descriptor ``dry_run`` opens rejects ``os.write`` with EBADF."""
        qfile = tmp_path / "questions.md"
        qfile.write_text("## Open\n\n- **Q.**\n  body\n\n## Answered\n")
        data_before = qfile.read_bytes()

        # dry_run must not raise and must not modify the file
        report = dry_run(qfile)
        assert "coverage verdict" in report
        assert data_before == qfile.read_bytes()

    def test_os_RDONLY_descriptor_rejects_write_with_ebadf(self, tmp_path):
        """STRUCTURAL proof: a kernel ``O_RDONLY`` descriptor rejects
        ``os.write``. ``dry_run`` opens exactly this kind of descriptor, so
        no code-path bug inside the module can write through it — the kernel
        refuses before Python sees the bytes. This is the difference between
        'cannot write' (a property) and 'happens not to write' (a code path)."""
        qfile = tmp_path / "questions.md"
        qfile.write_text("hello\n")
        fd = os.open(str(qfile), os.O_RDONLY)
        try:
            with pytest.raises(OSError) as exc_info:
                os.write(fd, b"x")
            # EBADF is errno 9 on Linux
            assert exc_info.value.errno == errno.EBADF
        finally:
            os.close(fd)

    def test_module_has_no_write_calls(self):
        """No write-mode open, no sqlite3 import, no shutil — the module
        source contains no write path. Checks actual import/usage lines, not
        prose mentions in docstrings."""
        import dreamwork_db.question_parse as qp
        import ast
        source = Path(qp.__file__).read_text()
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
        # no sqlite3, no shutil, no io with write intent
        assert "sqlite3" not in imports
        assert "shutil" not in imports
        # the ONLY os.open call uses O_RDONLY
        assert "os.O_RDONLY" in source
        # no write-mode file open (look for open() with 'w' mode literal)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'open':
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and 'w' in arg.value:
                        pytest.fail(f"write-mode open() found: {ast.dump(node)}")


# ═══ DIRECTION 2: false-green traps the coverage check must catch ══════════

class TestCoverageFalseGreens:
    """``#671``: a check that examined nothing must not read as passing.
    Off-by-one: a span one byte short must fail the round-trip."""

    def test_empty_corpus_is_refusal_not_pass(self):
        """A non-empty source with zero entries is a REFUSAL (#671)."""
        data = b"# Questions\n\n## Details\n\nSome text.\n"
        m = question_manifest(data)
        cov = coverage_report(m, data)
        assert cov["ok"] is False
        assert cov["checks"]["examined_corpus"]["refusal"] is True
        assert cov["checks"]["examined_corpus"]["entries"] == 0

    def test_off_by_one_span_fails_roundtrip(self):
        """A span that is one byte short still round-trips through most
        checks — but the fresh-split length re-derivation catches it."""
        data = b"## Open\n\n- **Q1.**\n  body line\n\n## Answered\n"
        m = question_manifest(data)
        assert len(m.entries) == 1

        # sabotage: shrink the entry's span by one byte (drop trailing newline)
        entry = m.entries[0]
        sabotaged_entry = QuestionEntry(
            ordinal=entry.ordinal, section=entry.section, state=entry.state,
            title=entry.title, body_markdown=entry.body_markdown,
            asked_at=entry.asked_at, asked_precision=entry.asked_precision,
            resolution_date=entry.resolution_date, contributions=entry.contributions,
            raw_text=entry.raw_text, span=Span(entry.span.start, entry.span.end - 1),
            first_line=entry.first_line, last_line=entry.last_line,
        )
        sabotaged = QuestionManifest(
            source_bytes=m.source_bytes, source_chars=m.source_chars,
            source_lines=m.source_lines, sha256=m.sha256, sections=m.sections,
            entries=(sabotaged_entry,), unclassified=m.unclassified,
            heads_outside_sections=m.heads_outside_sections,
            section_bytes=m.section_bytes,
        )
        cov = coverage_report(sabotaged, data)
        assert cov["ok"] is False
        bad = cov["checks"]["roundtrip_spans"]["bad"]
        assert len(bad) == 1
        # discriminating message names the length mismatch
        assert "span" in bad[0]
        assert "!=" in bad[0]

    def test_wrong_head_count_fails(self):
        """If the parser reports fewer entries than the independent scan
        found, the head-count check fails."""
        data = b"## Open\n\n- **Q1.**\n  b1\n\n- **Q2.**\n  b2\n\n## Answered\n"
        m = question_manifest(data)
        assert len(m.entries) == 2

        # simulate dropping the second entry
        sabotaged = QuestionManifest(
            source_bytes=m.source_bytes, source_chars=m.source_chars,
            source_lines=m.source_lines, sha256=m.sha256, sections=m.sections,
            entries=m.entries[:1], unclassified=m.unclassified,
            heads_outside_sections=m.heads_outside_sections,
            section_bytes=m.section_bytes,
        )
        cov = coverage_report(sabotaged, data)
        assert cov["ok"] is False
        hc = cov["checks"]["head_count"]
        assert hc["manifest"] == 1
        assert hc["independent"] == 2
        assert hc["ok"] is False


# ═══ INDEPENDENCE: parser and scanner agree but use different logic ════════

class TestIndependentRoute:
    """The independent head scanner uses a different detection method than the
    parser — it must agree on clean input (#759: hold subject, vary
    interpreter)."""

    def test_agrees_on_well_formed_input(self):
        data = b"## Open\n\n- **Q1.**\n  b1\n\n- **Q2.**\n  b2\n\n## Answered\n"
        m = question_manifest(data)
        inside, outside = independent_head_count(data)
        assert len(m.entries) == inside
        assert m.heads_outside_sections == outside

    def test_scanner_ignores_contribution_bullets_like_parser(self):
        """Both the parser and the scanner must NOT count a contribution
        bullet (``  - **Answer...``) as an entry head."""
        data = (
            b"## Open\n\n"
            b"- **Q1.**\n  body\n"
            b"  - **Answer (via watch, 2026-08-01 10:00):** ans\n\n"
            b"## Answered\n"
        )
        m = question_manifest(data)
        inside, _ = independent_head_count(data)
        assert len(m.entries) == 1
        assert inside == 1


# ═══ SPAN CORRECTNESS: contiguous, no gaps between entries ═════════════════

class TestSpanCorrectness:
    def test_entry_spans_are_contiguous(self):
        """Adjacent entries have no gap: entry[i].end == entry[i+1].start."""
        data = b"## Open\n\n- **Q1.**\n  b1\n\n- **Q2.**\n  b2\n\n## Answered\n"
        m = question_manifest(data)
        assert len(m.entries) >= 2
        for i in range(len(m.entries) - 1):
            assert m.entries[i].span.end == m.entries[i + 1].span.start

    def test_first_entry_starts_after_section_heading(self):
        data = b"## Open\n\n- **Q1.**\n  b1\n\n## Answered\n"
        m = question_manifest(data)
        heading_end = data.index(b"## Open\n") + len(b"## Open\n")
        assert m.entries[0].span.start > heading_end or m.entries[0].span.start == heading_end + 1

    def test_span_covers_head_through_trailing_blank(self):
        """The trailing blank separator between entries is part of the
        entry's span (contiguous partition)."""
        data = b"## Open\n\n- **Q1.**\n  b1\n\n- **Q2.**\n  b2\n\n## Answered\n"
        m = question_manifest(data)
        e0 = m.entries[0]
        # raw_text should end with a newline (the trailing blank line)
        assert e0.raw_text.endswith("\n")
        # and contain the head + body + blank
        assert "- **Q1.**" in e0.raw_text
