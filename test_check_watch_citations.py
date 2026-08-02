"""Standing contract for the citation pins retained by #921."""

import re
from collections import Counter
from pathlib import Path
import subprocess

from dev import check_watch_citations as citations


ROOT = Path(__file__).resolve().parent


def _git(root: Path, *argv: str) -> str:
    proc = subprocess.run(
        ["git", *argv], cwd=root, text=True, capture_output=True, check=True
    )
    return proc.stdout.strip()


def _fixture_repo(tmp_path: Path, doc: str) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "watch.py").write_text("one\ntwo\nthree\n", encoding="utf-8")
    _git(root, "add", "watch.py")
    _git(
        root,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "fixture",
    )
    revision = _git(root, "rev-parse", "HEAD")
    (root / "doc.md").write_text(doc.format(revision=revision), encoding="utf-8")
    return root, revision


# Independent literal: do not derive the checked population from production's scan.
REVIEWED_PIN_COUNTS = Counter({
    (".dreamwork/docs/briefs/547-composer-default-runmode-removal.md", "watch.py:4100"): 1,
    (".dreamwork/docs/briefs/547-composer-default-runmode-removal.md", "watch.py:4101"): 1,
    (".dreamwork/docs/briefs/548-bdinput-cap-binding.md", "watch.py:3712"): 2,
    (".dreamwork/docs/briefs/548-bdinput-cap-binding.md", "watch.py:3931"): 1,
    (".dreamwork/docs/briefs/562-chat-surface.md", "watch.py:4020-4027"): 1,
    (".dreamwork/docs/briefs/562-chat-surface.md", "watch.py:4037-4040"): 1,
    (".dreamwork/docs/handoffs/2026-07-29-0810-claude-to-grok.md", "watch.py:4016-4021"): 1,
    (".dreamwork/handoffs.md", "watch.py:3654"): 2,
    (".dreamwork/handoffs.md", "watch.py:3942"): 1,
    (".dreamwork/handoffs.md", "watch.py:4056"): 1,
    (".dreamwork/handoffs.md", "watch.py:4074-4082"): 1,
    (".dreamwork/handoffs.md", "watch.py:4135-4145"): 1,
    (".dreamwork/handoffs.md", "watch.py:4412"): 1,
    (".dreamwork/lane-641-report.md", "watch.py:4174"): 1,
    (".dreamwork/reviews-cx-session-2026-08-01.md", "watch.py:3946-3974"): 1,
    (".dreamwork/reviews-cx-session-2026-08-01.md", "watch.py:3999-4006"): 1,
})


# repo-wide-guard: checks every citation in the explicit multi-document #801 population
def test_reviewed_watch_citation_population_is_still_resolved(capsys):
    # (2) The contract: production enrolment must match the reviewed population.
    # A contract asserts intent; a mirror asserts nothing (#928).  This is the
    # one place the full multiset is pinned, and it stays.
    assert citations.PINNED_CITATIONS == REVIEWED_PIN_COUNTS
    # (3) Degrade-to-zero guard (#868): the reviewed population must be non-empty.
    # The exact count added no discrimination over (2) — only the both-empty
    # case — so the literal 18 is retired; >0 catches the same case with zero
    # bump cost on every legitimate enrolment change.
    assert REVIEWED_PIN_COUNTS.total() > 0
    assert citations.check(ROOT) == 0
    output = capsys.readouterr().out
    # (4a) The #921 narrowing stated in the PASS line: the guard pins
    # coordinates, it does not verify them against the pinned revision.
    assert "pinned, not verified against the pinned revision" in output
    # (4b) Degrade-to-zero visibility (#868): the PASS line prints its
    # denominators so a human can see "0 of 0" rather than read it as success.
    # The counts themselves are pinned by (2) and the guard's exit 0 — the
    # test asserts the STRUCTURE has them, not a hardcoded number.
    assert re.search(
        r"PASS: \d+ of \d+ pinned across \d+ document\(s\); "
        r"\d+ citation\(s\) seen",
        output,
    )


def test_zero_resolved_citations_is_a_fault_not_a_vacuous_pass(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(citations, "AFFECTED_DOCS", {"missing.md"})
    assert citations.check(tmp_path) == 2
    assert "docs_scanned denominator is empty" in capsys.readouterr().out

    (tmp_path / "empty.md").write_text("no citations here\n", encoding="utf-8")
    monkeypatch.setattr(citations, "AFFECTED_DOCS", {"empty.md"})
    assert citations.check(tmp_path) == 2
    assert "citations_seen denominator is empty" in capsys.readouterr().out


def test_watch_insertion_is_irrelevant_but_missing_citation_still_fails(
    monkeypatch, tmp_path, capsys
):
    root, revision = _fixture_repo(tmp_path, "watch.py:2 @ {revision}\n")
    monkeypatch.setattr(citations, "AFFECTED_DOCS", {"doc.md"})
    monkeypatch.setattr(citations, "PINNED_CITATIONS", Counter({("doc.md", "watch.py:2"): 1}))

    (root / "watch.py").write_text("inserted\none\ntwo\nthree\n", encoding="utf-8")
    assert citations.check(root) == 0
    assert "1 of 1 pinned" in capsys.readouterr().out

    (root / "doc.md").write_text(
        f"expected citation removed; watch.py:3 @ {revision} remains\n",
        encoding="utf-8",
    )
    assert citations.check(root) == 1
    missing_output = capsys.readouterr().out
    assert (
        "MISSING doc.md: watch.py:2: expected 1 occurrence(s), saw 0"
        in missing_output
    )
    # The #940 enrolment note names both files and states the coordinator role,
    # so a lane seeing its own correct repair knows an enrolment update is the
    # answer rather than weakening the guard.
    assert "dev/check_watch_citations.py" in missing_output
    assert "test_check_watch_citations.py" in missing_output
    assert "COORDINATOR act" in missing_output
    assert revision


def test_appended_doc_preserves_duplicate_identity(monkeypatch, tmp_path, capsys):
    root, _ = _fixture_repo(
        tmp_path,
        "watch.py:2 @ {revision}\nwatch.py:2 @ {revision}\n",
    )
    monkeypatch.setattr(citations, "AFFECTED_DOCS", {"doc.md"})
    monkeypatch.setattr(citations, "PINNED_CITATIONS", Counter({("doc.md", "watch.py:2"): 2}))
    with (root / "doc.md").open("a", encoding="utf-8") as stream:
        stream.write("appended prose\n")

    assert citations.check(root) == 0
    assert "2 of 2 pinned" in capsys.readouterr().out


def test_pin_and_revision_failures_name_the_identity(monkeypatch, tmp_path, capsys):
    root, _ = _fixture_repo(tmp_path, "watch.py:2 without a pin\n")
    monkeypatch.setattr(citations, "AFFECTED_DOCS", {"doc.md"})
    monkeypatch.setattr(citations, "PINNED_CITATIONS", Counter({("doc.md", "watch.py:2"): 1}))
    assert citations.check(root) == 1
    unpinned_output = capsys.readouterr().out
    assert (
        "UNPINNED doc.md: watch.py:2: occurrence 1 of 1 is not followed by @ <rev>"
        in unpinned_output
    )
    # The #940 note fires for UNPINNED too — a pin retired to prose is the
    # other shape a correct repair produces (direction-2 candidate: the note
    # must not be MISSING-only).
    assert "dev/check_watch_citations.py" in unpinned_output
    assert "test_check_watch_citations.py" in unpinned_output

    (root / "doc.md").write_text("watch.py:2 @ deadbeef\n", encoding="utf-8")
    assert citations.check(root) == 1
    unresolved_output = capsys.readouterr().out
    assert (
        "UNRESOLVABLE doc.md: watch.py:2: @ deadbeef does not resolve to a commit"
        in unresolved_output
    )
    # An unresolvable hash is NOT a correct repair, so the enrolment note must
    # NOT appear — this is the direction-2 check that the note is scoped to
    # MISSING/UNPINNED rather than firing on every finding type.
    assert "COORDINATOR act" not in unresolved_output


# ---------------------------------------------------------------------------
# Docstring citation report (#1034)
#
# The pin checks above bind watch.py:NNN coordinates to git revisions in
# .dreamwork/ documents.  check_docstring_citations scans dev/*.py DOCSTRINGS
# for (#NNN), resolves each id against the ledger, and prints the title beside
# the citation so an attribution mismatch is visible at a glance.  It REPORTS,
# never certifies aptness (#994); it gates only on an id that does not resolve.
#
# Two independently-constructed fixture citations: the second is NOT derived
# from the first, so a checker hardcoded to one string cannot pass both.


def _docstring_repo(tmp_path: Path, *entries: tuple[str, str]) -> Path:
    """Build a repo with dev/*.py docstring citations and a fake resolver.

    *entries* are (filename, filebody) pairs.  The fake title resolver is
    installed by the caller via monkeypatch; this helper only writes files.
    """
    root = tmp_path / "repo"
    dev = root / "dev"
    dev.mkdir(parents=True)
    for name, body in entries:
        (dev / name).write_text(body, encoding="utf-8")
    return root


# Fixture A: a module-level docstring citing #868 with a mismatched principle.
_FIXTURE_A = (
    "example_a.py",
    '"""A principle about three zero-states (#868).\n\nNothing required,\n'
    "nothing found, registry unread.\n\"\"\"\nx = 1\n",
)

# Fixture B: a FUNCTION-level docstring citing (#5001) with a different shape.
# Independently constructed — not a copy or rename of fixture A — so a
# checker hardcoded to fixture A's id or symbol cannot find it.
_FIXTURE_B = (
    "example_b.py",
    'def thing():\n    """See (#5001) for the rule.\n\nA docstring on a '
    'function, not a module.\n    """\n    pass\n',
)


def test_docstring_report_resolves_and_prints_titles(monkeypatch, tmp_path, capsys):
    titles = {
        868: "the tick line reports 0 live lanes",
        5001: "an unrelated real entry",
    }
    monkeypatch.setattr(citations, "_resolve_titles", lambda dw_dir: titles)
    root = _docstring_repo(tmp_path, _FIXTURE_A, _FIXTURE_B)

    # verbose=True so resolved rows appear (default hides them, Finding 5).
    assert citations.check_docstring_citations(root, verbose=True) == 0
    out = capsys.readouterr().out

    # (1) Denominator: the run examined real files, not nothing.  A run that
    # examined 0 files must not read as a clean run (#868).  All three
    # denominators are printed: examined, skipped, docstrings scanned.
    assert "examined 2 file(s)" in out
    assert "0 skipped" in out
    assert re.search(r"\d+ docstring\(s\) scanned", out)
    assert "2 (#NNN) citation(s)" in out
    # (2) Report-not-certify contract (#994): the banner states it plainly.
    assert "REPORT not certification" in out
    # (3) Both fixture citations are printed with their resolved titles, one
    # module-level (fixture A) and one function-level (fixture B) — proving
    # the scanner reads both docstring sites, not only module-level.
    # Composed row assertion (Finding 2 red-proof): path AND symbol AND id
    # in one substring, so a checker that finds them independently elsewhere
    # cannot pass.
    assert "example_a.py" in out
    assert "the tick line reports 0 live lanes" in out
    assert "example_b.py" in out
    assert "an unrelated real entry" in out
    assert "OK: 2 resolved" in out


def test_docstring_unresolvable_id_gates_on_exit_1(monkeypatch, tmp_path, capsys):
    # A miscitation cites a REAL entry (868) but a dangling ref (9999) does
    # not exist.  Resolution is the only mechanical gate; aptness is reported.
    # The boundary entry (10000) keeps #9999 within the ledger's range so it
    # is UNRESOLVABLE, not SUSPICIOUS (#1034).
    titles = {
        868: "the tick line reports 0 live lanes",
        10000: "boundary entry above the dangling id",
    }
    monkeypatch.setattr(citations, "_resolve_titles", lambda dw_dir: titles)
    root = _docstring_repo(
        tmp_path,
        _FIXTURE_A,
        (
            "dangling.py",
            '"""See (#9999) — a real-looking number that is not in the '
            'ledger.\n"""\n',
        ),
    )

    assert citations.check_docstring_citations(root) == 1
    out = capsys.readouterr().out
    assert "UNRESOLVABLE" in out and "#9999" in out
    assert "not found in ledger" in out
    assert "FAIL: 1 of 2" in out


def test_docstring_vacuity_no_dev_dir_is_a_fault(tmp_path, capsys):
    # Direction-2 guard: a run that examined 0 files must not read as a
    # clean run over everything and found nothing (#868's lesson).
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    assert citations.check_docstring_citations(empty_root) == 2
    assert "examined 0 file(s)" in capsys.readouterr().out


def test_syntax_error_file_is_skipped_not_examined(monkeypatch, tmp_path, capsys):
    # #868's own lesson reproduced inside the citation tool: a file that
    # cannot be parsed must appear as SKIPPED with its reason, NOT be
    # silently absorbed into the examined count.
    titles = {868: "a real entry", 10000: "boundary"}
    monkeypatch.setattr(citations, "_resolve_titles", lambda dw_dir: titles)
    root = _docstring_repo(tmp_path, _FIXTURE_A)
    (root / "dev" / "broken.py").write_text("def (\n", encoding="utf-8")

    assert citations.check_docstring_citations(root) == 0
    out = capsys.readouterr().out
    assert "SKIPPED" in out and "broken.py" in out
    assert "SyntaxError" in out
    # examined is 1 (example_a.py only); the broken file is NOT counted.
    assert "examined 1 file(s)" in out
    assert "1 skipped" in out


def test_undecodable_bytes_are_skipped_not_crashed(monkeypatch, tmp_path, capsys):
    # Invalid UTF-8 with NO coding cookie: a genuinely undecodable file.
    # tokenize.open defaults to UTF-8, f.read() raises UnicodeDecodeError,
    # the file is SKIPPED.  (See test_latin1_coding_cookie_is_examined for
    # the complement: a non-UTF-8 file WITH a cookie IS examined.)
    titles = {868: "a real entry", 10000: "boundary"}
    monkeypatch.setattr(citations, "_resolve_titles", lambda dw_dir: titles)
    root = _docstring_repo(tmp_path, _FIXTURE_A)
    (root / "dev" / "bad_utf8.py").write_bytes(
        b'"""docstring"""\n# \xff\xfe invalid bytes\n'
    )

    assert citations.check_docstring_citations(root) == 0
    out = capsys.readouterr().out
    assert "SKIPPED" in out and "bad_utf8.py" in out
    assert "undecodable" in out
    assert "examined 1 file(s)" in out


def test_latin1_coding_cookie_is_examined(monkeypatch, tmp_path, capsys):
    # Finding 4: a valid Python file with a PEP-263 '# coding: latin-1'
    # cookie carrying a (#NNN) docstring citation.  The fixture bytes are
    # genuinely non-UTF-8 (0xe9 = 'é' in Latin-1, invalid continuation in
    # UTF-8).  tokenize.open honours the cookie; the file IS examined and
    # its citation IS resolved, not silently skipped.
    titles = {868: "a real entry", 777: "the latin-1 entry", 10000: "boundary"}
    monkeypatch.setattr(citations, "_resolve_titles", lambda dw_dir: titles)
    root = _docstring_repo(tmp_path, _FIXTURE_A)
    # Latin-1 bytes with a PEP-263 cookie.  0xe9 is 'é' — invalid UTF-8.
    (root / "dev" / "latin1.py").write_bytes(
        b"# -*- coding: latin-1 -*-\n"
        b'"""Caf\xe9 cites (#777) here.\n"""\n'
        b"x = 1\n"
    )

    assert citations.check_docstring_citations(root, verbose=True) == 0
    out = capsys.readouterr().out
    # The file was examined (2 files, 0 skipped), not silently dropped.
    assert "examined 2 file(s)" in out
    assert "0 skipped" in out
    # The citation in the Latin-1 docstring was found and resolved.
    assert "latin1.py" in out
    assert "#777" in out
    assert "the latin-1 entry" in out
    assert "SKIPPED" not in out


def test_css_colour_six_hex_is_filtered(monkeypatch, tmp_path, capsys):
    # Finding 3: a parenthesised CSS colour like (#334155) is six hex
    # digits — unambiguous CSS syntax.  It is FILTERED, not counted as an
    # issue reference.  The rule is stated in the row.
    titles = {868: "a real entry", 1038: "the current max"}
    monkeypatch.setattr(citations, "_resolve_titles", lambda dw_dir: titles)
    root = _docstring_repo(
        tmp_path,
        _FIXTURE_A,
        (
            "colour.py",
            '"""The border is (#334155) in this docstring.\n"""\n',
        ),
    )

    assert citations.check_docstring_citations(root) == 0
    out = capsys.readouterr().out
    assert "FILTERED" in out and "#334155" in out
    assert "CSS colour" in out
    assert "6 hex digits" in out
    # The colour does NOT count as an unresolvable or suspicious citation.
    assert "UNRESOLVABLE" not in out
    assert "SUSPICIOUS" not in out


def test_above_max_non_colour_is_suspicious(monkeypatch, tmp_path, capsys):
    # Finding 3: a parenthesised number above the ledger max that is NOT
    # six hex digits is AMBIGUOUS — it could be a typo, a stale forward
    # reference, or a not-yet-filed task.  It is reported as SUSPICIOUS,
    # never silently filtered.  (#1035) with max 1038: 4 digits, above max,
    # but within plausible issue-id range.
    titles = {868: "a real entry", 1038: "the current max"}
    monkeypatch.setattr(citations, "_resolve_titles", lambda dw_dir: titles)
    root = _docstring_repo(
        tmp_path,
        _FIXTURE_A,
        (
            "forward.py",
            '"""See (#1042) for the plan.\n"""\n',
        ),
    )

    assert citations.check_docstring_citations(root) == 0
    out = capsys.readouterr().out
    assert "SUSPICIOUS" in out and "#1042" in out
    assert "exceeds ledger max" in out
    # SUSPICIOUS does NOT fail the check (it's a report, not a gate, #994),
    # but it MUST be visible — not silently filtered.
    assert "FAIL" not in out
    assert "FILTERED" not in out


def test_store_absent_reports_not_checked(monkeypatch, tmp_path, capsys):
    # Finding 1: when the ledger store is absent, the guard reports NOT
    # CHECKED (#136 third state: titles could not be resolved, distinct from
    # 'resolved OK' and 'no citations found') and returns 0 so a missing
    # store does not mask the pin check.
    root = _docstring_repo(tmp_path, _FIXTURE_A)

    # _default_dw_dir would resolve to the real checkout; patch _resolve_titles
    # to raise FileNotFoundError as the real store-absent path does.
    def _raise(_dw_dir):
        raise FileNotFoundError("/fake/ledger.sqlite3")

    monkeypatch.setattr(citations, "_resolve_titles", _raise)
    assert citations.check_docstring_citations(root) == 0
    out = capsys.readouterr().out
    # The #136 third state is named plainly, not collapsed with OK.
    assert "NOT CHECKED" in out
    assert "could not run" in out or "could not be resolved" in out
    # Denominators are present so a reader sees what WAS done.
    assert re.search(r"\d+ \(#NNN\) citation\(s\) extracted", out)
    # The OK/FAIL verdicts must NOT appear — this is neither.
    assert "OK:" not in out
    assert "FAIL:" not in out


def test_guard_is_registered_in_repo_wide_registry():
    # Finding 2: removing the REGISTRY entry for this guard would not fail
    # the direct unit test.  Assert the node id is present so a silent
    # de-registration is caught.
    import dev.repo_wide_guards as guards

    node = "test_check_watch_citations.py::test_docstring_citations_on_real_tree"
    assert node in guards.REGISTRY, (
        f"guard node {node!r} is not in REGISTRY — the guard is not on the gate"
    )


# repo-wide-guard: checks every dev/*.py docstring (#NNN) resolves against
# the real ledger, and the real miscitation at land_lane.py (#868 for #136's
# rule) is REPORTED in the output.  The synthetic fixtures above prove the
# parser works; this test proves the GATE would have caught tonight's error
# by asserting the REAL composed row.
def test_docstring_citations_on_real_tree(capsys):
    # When the store is absent (clean checkout, CI), the guard reports NOT
    # CHECKED — it cannot resolve titles.  A skip is the honest outcome:
    # the guard did not verify anything, and a pass would claim it did.
    try:
        dw = citations._default_dw_dir()
        titles = citations._resolve_titles(dw)
    except FileNotFoundError:
        import pytest
        pytest.skip(
            "ledger store not found — title resolution could not run (#136)"
        )

    # Store present: assert exit 0 and the real composed row.
    assert citations.check_docstring_citations(ROOT, verbose=True) == 0
    out = capsys.readouterr().out
    # (1) Denominators are non-zero: the run examined real files (#868).
    assert re.search(r"examined [1-9]\d* file\(s\)", out)
    assert re.search(r"[1-9]\d* docstring\(s\) scanned", out)
    # (2) Finding 2 — the composed row: path + _requirement_line + (#868)
    # together as one string, plus the #868 title text.  Asserting
    # "dev/land_lane.py" and "#868" separately passes even if line 478 is
    # never reported (both appear independently elsewhere in the output).
    assert "_requirement_line (#868)" in out
    assert "dev/land_lane.py" in out
    assert (
        "the tick line reports 0 live lanes" in out
    )
    # (3) No unresolvable citations on the tree it ships with.
    assert "UNRESOLVABLE" not in out
