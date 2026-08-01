"""Tests for dev/citation_audit.py — the #786 citation audit tool.

The tool's value is not catching every miscitation (it cannot — that is a
semantic judgment).  Its value is naming the cases it CAN decide and being
honest about the rest.  These tests bind both halves.
"""

import sys
import textwrap
from pathlib import Path

import sqlite3
import subprocess

import pytest

import ledger_parse
import ledger_store
from dreamwork_db.core import Access, open_database
from dreamwork_db.tasks import task_store_spec

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
from dev import citation_audit  # noqa: E402


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


def _real_store_audit(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A valid citation backed by the real task repository and store schema."""
    dw_dir = tmp_path / ".dreamwork"
    briefs = tmp_path / "briefs"
    dw_dir.mkdir()
    briefs.mkdir()
    store = dw_dir / ledger_parse.STORE_FILENAME
    ledger_store.open_store(store, seed_next_id=199).close()
    with open_database(task_store_spec(store), access=Access.WRITE) as database:
        with database.transaction():
            task_id = database.tasks.file(
                "a guard whose message names a failure mode it cannot detect",
                "the assertion passed on the exact input its message warned about",
                origin="loop",
            )
    (briefs / "valid.md").write_text(
        f"#{task_id} — a guard whose message names a failure mode it cannot detect.\n"
    )
    return dw_dir, briefs, store


def _run_real_audit(dw_dir: Path, briefs: Path) -> int:
    return citation_audit.main([
        "--briefs", str(briefs), "--dw-dir", str(dw_dir), "--quiet",
    ])


def test_documented_store_override_is_the_supported_flag(tmp_path, capsys):
    """The usage remedy is one spelling which argparse actually accepts (#651)."""
    assert "--dw-dir" in citation_audit.__doc__
    assert "--ledger" not in citation_audit.__doc__
    dw_dir, briefs, _store = _real_store_audit(tmp_path)
    assert _run_real_audit(dw_dir, briefs) == 0
    assert "UNCLASSIFIABLE:   1" in capsys.readouterr().out


def test_public_output_contract_has_one_detail_switch(capsys):
    """Default is summary and --verbose is the sole documented detail switch."""
    assert "--quiet" not in citation_audit.__doc__, (
        "citation_audit docs must not promise behaviour for the inert --quiet alias"
    )
    with pytest.raises(SystemExit) as caught:
        citation_audit.main(["--help"])
    assert caught.value.code == 0
    help_text = capsys.readouterr().out
    assert "--verbose" in help_text
    assert "--quiet" not in help_text, (
        "citation_audit help must present one supported detail switch: --verbose"
    )


def test_healthy_store_control_does_not_reach_fault_classifier(
    tmp_path, capsys, monkeypatch,
):
    """The healthy-only fixture is the mandatory vacuous false-green shape."""
    dw_dir, briefs, _store = _real_store_audit(tmp_path)
    monkeypatch.setattr(
        citation_audit, "_store_fault_message", lambda _exc: "wrong store fault",
    )
    assert _run_real_audit(dw_dir, briefs) == 0
    captured = capsys.readouterr()
    assert "UNRESOLVABLE:     0" in captured.out
    assert captured.err == ""


def test_missing_store_is_named_and_never_reported_unresolvable(tmp_path, capsys):
    """One valid citation stays valid when its store disappears: the store faults."""
    dw_dir, briefs, store = _real_store_audit(tmp_path)
    assert _run_real_audit(dw_dir, briefs) == 0
    healthy = capsys.readouterr()
    assert "UNRESOLVABLE:     0" in healthy.out

    store.unlink()
    assert _run_real_audit(dw_dir, briefs) == 2
    missing = capsys.readouterr()
    assert missing.err.lower().startswith("citation_audit: store missing:")
    assert "UNRESOLVABLE" not in missing.out


def test_exclusive_lock_is_named_store_busy(tmp_path, capsys):
    dw_dir, briefs, store = _real_store_audit(tmp_path)
    lock = sqlite3.connect(store)
    lock.execute("PRAGMA journal_mode=DELETE")
    lock.execute("BEGIN EXCLUSIVE")
    try:
        assert _run_real_audit(dw_dir, briefs) == 2
    finally:
        lock.rollback()
        lock.close()
    captured = capsys.readouterr()
    assert captured.err.lower().startswith("citation_audit: store busy:")
    assert "database is locked" in captured.err.lower()


def test_half_migrated_schema_is_named_schema_mismatch(tmp_path, capsys):
    dw_dir, briefs, store = _real_store_audit(tmp_path)
    broken = sqlite3.connect(store)
    broken.execute("ALTER TABLE task RENAME COLUMN title TO missing_title")
    broken.commit()
    broken.close()

    assert _run_real_audit(dw_dir, briefs) == 2
    captured = capsys.readouterr()
    assert captured.err.lower().startswith("citation_audit: store schema mismatch:")
    assert "store schema mismatch during sql:" in captured.err.lower()


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


def test_report_names_untracked_but_audited_corpus(tmp_path):
    """Untracked briefs are named without calling visible input invisible."""
    briefs = _git_corpus(tmp_path, tracked=3, untracked=1)
    report = audit_briefs(briefs, _fixture_entries())
    text = format_report(report)
    assert "3 tracked / 4 on disk / 4 audited (1 untracked)" in text
    assert "INCOMPLETE" not in text


def test_report_names_actual_incomplete_audit(tmp_path):
    """INCOMPLETE names the short audit count it can actually detect (#651)."""
    briefs = _git_corpus(tmp_path, tracked=3, untracked=1)
    report = audit_briefs(briefs, _fixture_entries())
    report.briefs_examined -= 1
    text = format_report(report)
    assert "AUDIT IS INCOMPLETE — audited 3 of 4 on-disk briefs" in text


def test_report_quiet_when_corpus_complete(tmp_path):
    """format_report does not alarm when tracked == on_disk."""
    briefs = _git_corpus(tmp_path, tracked=2, untracked=0)
    report = audit_briefs(briefs, _fixture_entries())
    text = format_report(report)
    assert "2 tracked / 2 on disk" in text
    assert "INCOMPLETE" not in text


def test_default_corpus_reaches_main_checkout_from_linked_worktree(tmp_path):
    """Default reaches main's briefs and resolves citations through its store."""
    main = tmp_path / "main"
    lane = tmp_path / "lane"
    briefs = main / ".dreamwork" / "docs" / "briefs"
    (main / "dev").mkdir(parents=True)
    briefs.mkdir(parents=True)
    source = Path(__file__).resolve().parent
    (main / "dev" / "citation_audit.py").write_text(
        (source / "dev" / "citation_audit.py").read_text()
    )
    (main / "ledger_parse.py").write_text(
        "from pathlib import Path\n"
        f"MAIN_DW = Path({str(main / '.dreamwork')!r})\n"
        "def store_path(dreamwork_dir):\n"
        "    return Path(dreamwork_dir) / 'ledger.sqlite3'\n"
        "def store_records(dreamwork_dir):\n"
        "    if Path(dreamwork_dir).resolve() != MAIN_DW.resolve():\n"
        "        return []\n"
        "    return [{'id': 671, 'state': 'landed', "
        "'title': 'A check that examined nothing must not read as passing', "
        "'body': ''}]\n"
    )
    (main / ".dreamwork" / "ledger.sqlite3").write_text("fixture store marker\n")
    (briefs / "tracked.md").write_text("tracked brief without citations\n")
    subprocess.run(["git", "init", "-q", str(main)], check=True)
    subprocess.run(["git", "-C", str(main), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(main), "config", "user.name", "test"], check=True)
    subprocess.run(["git", "-C", str(main), "add", "."], check=True)
    subprocess.run(["git", "-C", str(main), "commit", "-qm", "seed"], check=True)
    subprocess.run(
        ["git", "-C", str(main), "worktree", "add", "-qb", "lane", str(lane)],
        check=True,
    )
    try:
        (briefs / "untracked.md").write_text(
            "#671 — a check that examined nothing must not read as passing.\n"
        )
        command = [
            sys.executable, str(lane / "dev" / "citation_audit.py"),
            "--quiet",
        ]
        default = subprocess.run(command, capture_output=True, text=True)
        first = default.stdout.splitlines()[0]
        assert first == "corpus: 1 tracked / 2 on disk / 2 audited (1 untracked)", (
            "default audit did not examine every visible main-checkout brief: "
            f"expected 2 audited from {briefs}, got {first!r}"
        )
        assert "  UNRESOLVABLE:     0" in default.stdout, (
            "default audit resolved nothing through the main-checkout store: "
            f"known #671 was unresolvable\n{default.stdout}{default.stderr}"
        )
        assert default.returncode == 0

        explicit = subprocess.run(
            command + ["--briefs", str(lane / ".dreamwork" / "docs" / "briefs")],
            capture_output=True, text=True, check=True,
        )
        assert explicit.stdout.splitlines()[0] == (
            "corpus: 1 tracked / 1 on disk / 1 audited"
        ), (
            "explicit --briefs must remain caller-selected even when it names the "
            "truncated worktree corpus"
        )
    finally:
        subprocess.run(
            ["git", "-C", str(main), "worktree", "remove", "--force", str(lane)],
            check=True,
        )
