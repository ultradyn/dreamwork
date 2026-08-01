"""Tests for dev/citation_audit.py — the #786 citation audit tool.

The tool's value is not catching every miscitation (it cannot — that is a
semantic judgment).  Its value is naming the cases it CAN decide and being
honest about the rest.  These tests bind both halves.
"""

import sys
import textwrap
from pathlib import Path

import subprocess

import pytest

# Make dev/ importable when running from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dev.citation_audit import (  # noqa: E402
    CorpusCoverage,
    Citation,
    _content_words,
    audit_briefs,
    classify,
    corpus_coverage,
    extract_citations,
    format_report,
)


# -- fixtures -----------------------------------------------------------------

# A miniature ledger with three entries whose subjects are deliberately
# different so that content-word overlap is unambiguous.  We build a dict
# directly (the production resolver reads the SQLite store; the unit tests
# bypass that and pass a hand-built dict into classify).
def _fixture_entries() -> dict[int, str]:
    return {
        100: "#100  open\ntitle: queued dispatches rot\n\n"
        "the dashboard shows stale task ids nobody verified\n",
        200: "#200  landed\ntitle: a guard whose message names a failure mode it cannot detect\n\n"
        "the assertion passed on the exact input its message warned about\n",
        300: "#300  open\ntitle: the burndown panel is too tall on mobile\n\n"
        "three rows of chrome eat the fold\n",
    }


@pytest.fixture
def entries() -> dict[int, str]:
    return _fixture_entries()


# -- extract_citations --------------------------------------------------------

def test_extract_finds_em_dash_citation():
    text = "See #100 — a principle about zebras."
    cits = extract_citations(text, "test")
    assert len(cits) == 1
    assert cits[0].task_id == 100
    assert "zebras" in cits[0].wording


def test_extract_finds_colon_citation():
    text = "The rule (#200: a guard that lies about its own scope) applies."
    cits = extract_citations(text, "test")
    assert len(cits) == 1
    assert cits[0].task_id == 200
    assert "guard" in cits[0].wording


def test_extract_ignores_bare_reference():
    """A bare #NNN with no descriptive text is a reference, not a citation."""
    text = "Fix #100 and also check #200."
    cits = extract_citations(text, "test")
    assert cits == []


def test_extract_ignores_too_short_wording():
    text = "See #100 — x."
    assert extract_citations(text, "test") == []


# -- classify -----------------------------------------------------------------

def test_classify_unresolvable(entries):
    """An id not in the ledger is UNRESOLVABLE — the tool says so, not silence."""
    cit = Citation(brief="t", task_id=999, wording="a principle about zebras", line=1)
    classify(cit, entries)
    assert cit.status == "UNRESOLVABLE"
    assert "999" in cit.detail


def test_classify_no_relationship(entries):
    """Zero shared content words = the clear false-citation case (#755 / healthy input)."""
    cit = Citation(
        brief="t",
        task_id=100,
        wording="a check that fires on a healthy input is worse than no check",
        line=1,
    )
    classify(cit, entries)
    assert cit.status == "NO_RELATIONSHIP"
    assert "zero shared" in cit.detail


def test_classify_unclassifiable_on_overlap(entries):
    """Some shared words = the tool declines to judge (#707)."""
    cit = Citation(
        brief="t",
        task_id=200,
        wording="a guard message that misleads the reader about its own scope",
        line=1,
    )
    classify(cit, entries)
    assert cit.status == "UNCLASSIFIABLE"
    assert "shared" in cit.detail.lower()


def test_classify_correct_citation_is_unclassifiable(entries):
    """Even a CORRECT citation lands UNCLASSIFIABLE unless it copies the title.

    This is the tool's honest limit: it cannot confirm a paraphrase is right,
    only that a CLEAR miscitation is wrong.  A correct citation with shared
    words goes to UNCLASSIFIABLE, not to a 'confirmed' bucket — there is no
    'confirmed' bucket.
    """
    cit = Citation(
        brief="t",
        task_id=200,
        wording="a guard whose message names a failure mode it cannot detect",
        line=1,
    )
    classify(cit, entries)
    assert cit.status == "UNCLASSIFIABLE"


# -- coverage (#671: examined-nothing must not read as passing) ---------------

def test_report_always_names_examined_count():
    """An audit that found nothing still prints how many it examined."""
    from dev.citation_audit import AuditReport
    report = AuditReport(examined=0)
    text = format_report(report)
    assert "examined 0" in text


def test_report_names_unresolvable_count():
    from dev.citation_audit import AuditReport
    report = AuditReport(examined=3, unresolvable=[
        Citation(brief="t", task_id=1, wording="x", line=1, status="UNRESOLVABLE", detail="not found"),
    ])
    text = format_report(report)
    assert "UNRESOLVABLE:     1" in text


# -- audit_briefs end-to-end --------------------------------------------------

def test_audit_briefs_end_to_end(tmp_path):
    """A brief corpus with one false citation and one valid one.

    The production resolver reads the SQLite store, so we pass a hand-built
    entries dict directly (audit_briefs takes entries, not a store path) —
    this keeps resolution separate from auditing and lets the test run
    without a live ledger store.
    """
    briefs = tmp_path / "briefs"
    briefs.mkdir()
    (briefs / "false.md").write_text(
        "#100 — a check that fires on a healthy input is worse than no check.\n"
    )
    (briefs / "valid.md").write_text(
        "#200 — a guard whose message names a failure mode it cannot detect.\n"
    )

    entries = _fixture_entries()
    report = audit_briefs(briefs, entries)
    assert report.examined == 2
    assert len(report.no_relationship) == 1
    assert len(report.unclassifiable) == 1
    assert report.no_relationship[0].task_id == 100


# -- content_words ------------------------------------------------------------

def test_content_words_strips_stopwords():
    words = _content_words("the check is a guard that fires on healthy input")
    assert "the" not in words
    assert "guard" in words
    assert "fires" in words
    assert "healthy" in words


def test_content_words_keeps_short_meaningful_words():
    """Three-letter words like 'rot' are kept (len > 2)."""
    words = _content_words("queued dispatches rot")
    assert "queued" in words
    assert "rot" in words


# -- corpus coverage (#671/#651/#788): a truncated audit must say so ---------
# The precondition these tests depend on is a corpus where tracked and
# on-disk counts DIFFER — a corpus where they are equal makes a broken
# split-reporter indistinguishable from a working one, which is precisely
# the shape that let #786 through (Direction 2 of the red-proof).


def _git_corpus(tmp_path: Path, tracked: int, untracked: int) -> Path:
    """Build a brief corpus under a fresh git repo with a measured split.

    Asserts the gap (tracked != on_disk) rather than trusting the caller's
    counts, so a fixture that accidentally lands equal is caught here
    rather than passing the real test vacuously.
    """
    briefs = tmp_path / "briefs"
    briefs.mkdir()
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "t@t"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "test"],
        check=True,
    )
    for i in range(tracked):
        (briefs / f"tracked-{i}.md").write_text(f"#100 — brief {i}\n")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "briefs"], check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-qm", "seed"], check=True,
    )
    for i in range(untracked):
        (briefs / f"untracked-{i}.md").write_text(f"#100 — stray {i}\n")
    # Precondition: the fixture must actually have the split we test for.
    cov = corpus_coverage(briefs)
    assert cov.on_disk == tracked + untracked, cov
    assert cov.untracked == untracked, cov
    return briefs


def test_corpus_coverage_names_tracked_vs_on_disk_split(tmp_path):
    """A corpus with untracked briefs reports the divergence (#788)."""
    briefs = _git_corpus(tmp_path, tracked=3, untracked=2)
    cov = corpus_coverage(briefs)
    # The discriminating assertion: untracked is named, not zero.
    assert cov.tracked == 3
    assert cov.on_disk == 5
    assert cov.untracked == 2


def test_corpus_coverage_equal_when_no_git(tmp_path):
    """Outside git, coverage reads as complete (no false alarm)."""
    briefs = tmp_path / "briefs"
    briefs.mkdir()
    (briefs / "a.md").write_text("x\n")
    (briefs / "b.md").write_text("x\n")
    cov = corpus_coverage(briefs)
    assert cov.tracked == cov.on_disk == 2
    assert cov.untracked == 0


def test_report_names_split_when_corpus_truncated(tmp_path):
    """format_report flags INCOMPLETE when untracked briefs exist (#671).

    This is the half that survives even if the corpus gets committed: a
    tool that names its own input boundary stays honest permanently.
    """
    briefs = _git_corpus(tmp_path, tracked=3, untracked=1)
    report = audit_briefs(briefs, _fixture_entries())
    text = format_report(report)
    assert "3 tracked / 4 on disk" in text
    assert "INCOMPLETE" in text


def test_report_quiet_when_corpus_complete(tmp_path):
    """format_report does not alarm when tracked == on_disk."""
    briefs = _git_corpus(tmp_path, tracked=2, untracked=0)
    report = audit_briefs(briefs, _fixture_entries())
    text = format_report(report)
    assert "2 tracked / 2 on disk" in text
    assert "INCOMPLETE" not in text
