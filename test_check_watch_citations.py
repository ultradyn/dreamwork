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

    # Resolved rows print by default (Finding 5); verbose is accepted for
    # compatibility but does not gate them.
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
    # issue reference.  The rule is stated in the row.  The fixture max
    # MUST encompass the token's decimal value — int("334155") = 334155,
    # the value the max-first classifier actually compares — so it is not
    # diverted to SUSPICIOUS before the CSS check —
    # a CSS colour within range is the case the filter exists for (#1034).
    titles = {868: "a real entry", 5000000: "the current max"}
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


def test_css_colour_black_zero_is_filtered_not_unresolvable(monkeypatch, tmp_path, capsys):
    # Finding 4 (#1034): (#000000) is CSS black — six hex digits, all zero.
    # The old int-based check computed str(int("000000")) = "0" (length 1)
    # and returned False, so the token reached UNRESOLVABLE and wedged the
    # checker with exit 1.  The fix checks the ORIGINAL TOKEN STRING
    # "000000" (length 6, all hex) → FILTERED.  The FILTERED row must also
    # print the original token (#000000), not the int (#0), so leading
    # zeros are preserved.
    titles = {868: "a real entry", 1038: "the current max"}
    monkeypatch.setattr(citations, "_resolve_titles", lambda dw_dir: titles)
    root = _docstring_repo(
        tmp_path,
        _FIXTURE_A,
        (
            "black.py",
            '"""The background is (#000000) in this docstring.\n"""\n',
        ),
    )

    assert citations.check_docstring_citations(root) == 0
    out = capsys.readouterr().out
    assert "FILTERED" in out
    assert "#000000" in out
    assert "#0)" not in out  # the int re-rendering must not appear
    assert "UNRESOLVABLE" not in out
    assert "FAIL" not in out


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


def test_hex_letter_css_colour_is_extracted_and_filtered(monkeypatch, tmp_path, capsys):
    # Finding 2 path 1 (#1034): (#ffffff) contains hex letters, so the
    # old regex \\(#(\\d+)\\) never matched it — the token was invisible
    # and the checker reported ZERO citations for a docstring that had
    # one.  The broadened regex \\(#([0-9a-fA-F]+)\\) now extracts it;
    # int("ffffff") raises ValueError so task_id is None (never above max,
    # never in titles); _is_css_colour("ffffff") is True → FILTERED.
    # A test using only decimal digits cannot see this path.
    titles = {868: "a real entry", 1038: "the current max"}
    monkeypatch.setattr(citations, "_resolve_titles", lambda dw_dir: titles)
    root = _docstring_repo(
        tmp_path,
        _FIXTURE_A,
        (
            "hexcolour.py",
            '"""The background is (#ffffff) in this docstring.\n"""\n',
        ),
    )

    assert citations.check_docstring_citations(root) == 0
    out = capsys.readouterr().out
    # The token WAS extracted (it appears in FILTERED output) — proving
    # the regex now sees hex letters, not just decimal digits.
    assert "FILTERED" in out and "#ffffff" in out
    assert "CSS colour" in out
    assert "UNRESOLVABLE" not in out
    assert "SUSPICIOUS" not in out


def test_sentinel_task_id_does_not_resolve(monkeypatch, tmp_path, capsys):
    # P2 resolution (#1034): an in-band sentinel shared a type with real ids.
    # If the ledger has an explicit entry with id -1, a non-decimal token
    # like (#a) is given task_id -1 and MATCHES the ledger entry, falsely
    # resolving to its title.  The out-of-band None sentinel cannot collide
    # with any task id by construction: None is not an int and can never be
    # a key in the int-keyed titles dict.  (#a) is not six hex digits, so it
    # is NOT a CSS colour — it must be reported UNRESOLVABLE, never resolved.
    titles = {868: "a real entry", -1: "negative sentinel", 1038: "the max"}
    monkeypatch.setattr(citations, "_resolve_titles", lambda dw_dir: titles)
    root = _docstring_repo(
        tmp_path,
        _FIXTURE_A,
        (
            "hexletter.py",
            '"""See (#a) for something.\n"""\n',
        ),
    )

    assert citations.check_docstring_citations(root) == 1
    out = capsys.readouterr().out
    assert "UNRESOLVABLE" in out and "#a" in out
    assert "#-1" not in out  # sentinel must not appear in output
    assert "negative sentinel" not in out  # must not resolve to fake entry


def test_above_max_css_lookalike_is_suspicious(monkeypatch, tmp_path, capsys):
    # Finding 2 path 2 (#1034): (#999999) is six decimal digits (all hex),
    # so the old CSS-first classifier swallowed it as FILTERED before
    # consulting the ledger max.  But 999999 is far above the real max
    # (~1038) — it is a plausible typo for a future issue id, and silently
    # filtering it is precisely the false negative this checker exists to
    # prevent.  The max-first classifier reports it as SUSPICIOUS.
    # A test using a 1–5 digit id cannot see this path: the defect is
    # specific to six-digit tokens that look like colours.  Use six digits
    # above the max (#1034).
    titles = {868: "a real entry", 1038: "the current max"}
    monkeypatch.setattr(citations, "_resolve_titles", lambda dw_dir: titles)
    root = _docstring_repo(
        tmp_path,
        _FIXTURE_A,
        (
            "lookalike.py",
            '"""See (#999999) for the plan.\n"""\n',
        ),
    )

    assert citations.check_docstring_citations(root) == 0
    out = capsys.readouterr().out
    assert "SUSPICIOUS" in out and "#999999" in out
    assert "exceeds ledger max" in out
    # The dangerous direction: it must NOT be silently FILTERED.
    assert "FILTERED" not in out
    assert "FAIL" not in out


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
    assert re.search(r"\d+ \(#NNN\) citation\(s\) extracted", out)
    # Finding 5 (#1034): all three denominators present as a set —
    # examined, skipped, docstrings — so a regression losing the skip
    # count (or any other) stays red.  The banner format is
    # "N file(s) (M skipped), K docstring(s) scanned".
    assert re.search(r"\d+ file\(s\)", out)
    assert re.search(r"\d+ skipped", out)
    assert re.search(r"\d+ docstring\(s\) scanned", out)
    # The OK/FAIL verdicts must NOT appear — this is neither.
    assert "OK:" not in out
    assert "FAIL:" not in out


def test_store_absent_renders_raw_token_not_sentinel(monkeypatch, tmp_path, capsys):
    # P2 output (#1034): when the store is absent, a hex-letter token like
    # (#ffffff) must print (#ffffff) [unverified], not (#-1) [unverified].
    # The -1 sentinel was an in-band int that printed in place of the raw
    # token the operator actually needs to see.  The raw_token is always
    # what was extracted; a sentinel value must never be operator-visible.
    root = _docstring_repo(
        tmp_path,
        _FIXTURE_A,
        (
            "hexcolour.py",
            '"""The background is (#ffffff) in this docstring.\n"""\n',
        ),
    )

    def _raise(_dw_dir):
        raise FileNotFoundError("/fake/ledger.sqlite3")

    monkeypatch.setattr(citations, "_resolve_titles", _raise)
    assert citations.check_docstring_citations(root) == 0
    out = capsys.readouterr().out
    assert "#ffffff" in out  # raw token shown
    assert "#-1)" not in out  # sentinel must not appear
    assert "#None)" not in out  # None must not render as text either


def test_guard_is_registered_in_repo_wide_registry():
    # Finding 2 (#1034): deleting the REGISTRY entry for the docstring
    # guard would not fail any test the gate runs — the membership test
    # below would fail, but it was not itself in the generated set, so the
    # gate never ran it.  The detector stayed silent because a DIFFERENT
    # entry for the same file survived.  This test is now registered
    # alongside the guard it protects, so the gate runs it and catches the
    # deletion (#1034 Finding 2).
    #
    # Both nodes are asserted: the guard whose registration we protect,
    # and this test's own registration.  Deleting the guard's row fails
    # this test through the first assertion; deleting this test's row
    # means the gate no longer runs it (the circular case — a deliberate
    # attack on the protection mechanism, outside the stated threat model
    # of "a lane deletes only the new row").
    import dev.repo_wide_guards as guards

    guard_node = "test_check_watch_citations.py::test_docstring_citations_on_real_tree"
    self_node = "test_check_watch_citations.py::test_guard_is_registered_in_repo_wide_registry"
    assert guard_node in guards.REGISTRY, (
        f"guard node {guard_node!r} is not in REGISTRY — the guard is not on the gate"
    )
    assert self_node in guards.REGISTRY, (
        f"self-protection node {self_node!r} is not in REGISTRY — "
        f"the guard above can be silently de-registered"
    )


# repo-wide-guard: checks every dev/*.py docstring (#NNN) resolves against
# the real ledger, and the real miscitation at land_lane.py (#868 for #136's
# rule) is REPORTED in the output.  The synthetic fixtures above prove the
# parser works; this test proves the GATE would have caught tonight's error
# by asserting the REAL composed row.
def test_docstring_citations_on_real_tree(capsys):
    # Finding 1 (#1034): NOT CHECKED is its own reported state, not a skip.
    # A skip inside a green run collapses could-not-check with checked-and-
    # passed (#136).  The test RUNS in both cases: when the store is absent
    # it asserts the checker reported NOT CHECKED; when the store is present
    # it asserts resolved citations.  The state is surfaced in the gate's
    # own output via capsys.disabled() so a clean-checkout run is
    # distinguishable from a resolved one by its output alone.
    rc = citations.check_docstring_citations(ROOT)
    out = capsys.readouterr().out

    if "NOT CHECKED" in out:
        # Store absent (clean checkout, CI): the checker reported NOT CHECKED.
        assert rc == 0
        assert "NOT CHECKED" in out
        # Finding 5: all three denominators present together — examined,
        # skipped, docstrings — so a regression losing any one stays red.
        assert re.search(r"\d+ file\(s\)", out)
        assert re.search(r"\d+ skipped", out)
        assert re.search(r"\d+ docstring\(s\) scanned", out)
        assert re.search(r"\d+ \(#NNN\) citation\(s\) extracted", out)
        # NOT CHECKED is neither OK nor FAIL (#136 three states).
        assert "OK:" not in out
        assert "FAIL:" not in out
        # Surface the state in the gate's own output so a clean-checkout
        # run is distinguishable from a resolved one (#1034 Finding 1).
        with capsys.disabled():
            for line in out.splitlines():
                if "NOT CHECKED" in line:
                    print(line)
                    break
    else:
        # Store present: assert exit 0 and the real composed row.
        assert rc == 0
        # (1) Denominators are non-zero: the run examined real files (#868).
        assert re.search(r"examined [1-9]\d* file\(s\)", out)
        assert re.search(r"[1-9]\d* docstring\(s\) scanned", out)
        # (2) Finding 3 (#1034) — the EXACT composed row as one regex: path
        # + symbol + id + TITLE PREFIX all in one match.  The title is
        # asserted on the SAME row, not separately: the old test asserted
        # "the tick line reports 0 live lanes" alone, which passes even
        # when it appears on brief.py's or check_watch_citations.py's row
        # (both also cite #868).  Composing path + symbol + id + title
        # prefix into one regex means only the land_lane _requirement_line
        # row matches — no other row in the output carries all four.
        # The line number is deliberately :\\d+ (not pinned to :478): a
        # line number is brittle, and what the test guarantees is that
        # path + symbol + id + title are composed as one fact on one row,
        # not that the citation has not moved within the function.  Moving
        # the (#868) to a different function (different symbol) or a
        # different file fails the regex.  The title is a PREFIX match
        # (the full title can grow or change; the prefix "the tick line
        # reports 0 live lanes" is the stable, discriminating part).
        assert re.search(
            r'dev/land_lane\.py:\d+ _requirement_line \(#868\) '
            r'"the tick line reports 0 live lanes',
            out,
        ), "composed miscitation row (land_lane _requirement_line #868 + title) must be reported"
        # (3) No unresolvable citations on the tree it ships with.
        assert "UNRESOLVABLE" not in out
        # (4) #1034 round 7 — the committed expectation that arms against a
        # frozen-path collapse: the REAL #199 citation in
        # reconcile_submissions.py (a task that left the live store and lives
        # ONLY in tasks.md.deprecated) must resolve from FROZEN history, not
        # read as UNRESOLVABLE.  This is the row the red-proof names: if
        # _deprecated_task_ids returns nothing, #199 falls through to
        # UNRESOLVABLE and this assertion fails (and (3) above fails too).
        # The row composes path + symbol + id + provenance as one regex so
        # no other row can satisfy it.  #199 is frozen-only by construction
        # (absent from the live store); if it were re-filed live, everything
        # would pass for a reason that evaporates — the frozen provenance
        # string is what proves the frozen path was taken.
        assert re.search(
            r'dev/reconcile_submissions\.py:\d+ <module> \(#199\) '
            r'resolved from frozen history',
            out,
        ), ("the real #199 citation must resolve from frozen history "
            "(tasks.md.deprecated) — if this fails, the frozen path is "
            "unwired or #199 was re-filed live")
        # Surface the resolved-state banner.
        with capsys.disabled():
            for line in out.splitlines():
                if "DOCSTRING CITATIONS:" in line:
                    print(line)
                    break


# ---------------------------------------------------------------------------
# Frozen-history resolution (#1034 round 7, mirroring lint.py #1094)
#
# check_docstring_citations now resolves ids against BOTH the live store and
# frozen history (tasks.md.deprecated), using the SAME three-state pattern
# lint.py landed at 6e0d7524: (ids, readable).  These tests cover the two
# states that the live-only path could not produce: resolves-FROZEN and
# UNVERIFIABLE (frozen-unreadable, could-not-check).


def test_frozen_only_id_resolves_from_frozen_history(monkeypatch, tmp_path, capsys):
    # #1034 round 7: an id that is in frozen history but NOT in the live
    # store resolves from frozen, reported with its provenance — not
    # UNRESOLVABLE.  This is the synthetic complement to the real-tree #199
    # assertion: it isolates the frozen path so a collapse of _deprecated
    # task_ids alone (with live untouched) is caught here too.
    titles = {868: "a live entry", 10000: "the live max"}
    monkeypatch.setattr(citations, "_resolve_titles", lambda dw_dir: titles)
    # Frozen set contains 4242 (NOT in live titles); readable=True.
    monkeypatch.setattr(
        citations, "_deprecated_task_ids", lambda dw_dir: ({4242}, True)
    )
    root = _docstring_repo(
        tmp_path,
        _FIXTURE_A,
        (
            "frozen_only.py",
            '"""See (#4242) for the frozen rule.\n"""\n',
        ),
    )

    assert citations.check_docstring_citations(root) == 0
    out = capsys.readouterr().out
    # The frozen-only citation resolves, with provenance stated — NOT
    # UNRESOLVABLE.  Composed row: path + symbol + id + provenance as one
    # match, so no other row can satisfy it.
    assert re.search(
        r'frozen_only\.py:\d+ <module> \(#4242\) '
        r'resolved from frozen history',
        out,
    ), "frozen-only id must resolve from frozen history with provenance"
    assert "UNRESOLVABLE" not in out
    # The banner reports the frozen count.
    assert "1 resolved from frozen history" in out


def test_frozen_unreadable_is_unverifiable_not_unresolvable(
    monkeypatch, tmp_path, capsys
):
    # #1034 round 7 / #1094 round 2 / #136: when the frozen history is
    # UNREADABLE (present but unparseable), a citation NOT in the live store
    # is UNCLASSIFIABLE — it may resolve-frozen or resolve-nowhere, and the
    # checker cannot tell which.  Reporting it as UNRESOLVABLE would blame
    # valid code for the checker's own read failure.  It must be UNVERIFIABLE
    # (could-not-check), a DISTINCT reported state, and it must NOT gate
    # (exit 0, like NOT CHECKED).  This is the `readable` bool as behaviour,
    # not just signature: if the bool never changes the reported row, the
    # signature is hollow.
    titles = {868: "a live entry", 10000: "the live max"}
    monkeypatch.setattr(citations, "_resolve_titles", lambda dw_dir: titles)
    # Frozen UNREADABLE: (set(), False) — the file exists but could not be
    # parsed.  This is NOT the same as (set(), True) (empty-but-readable),
    # which would make #4242 UNRESOLVABLE (resolves-nowhere).
    monkeypatch.setattr(
        citations, "_deprecated_task_ids", lambda dw_dir: (set(), False)
    )
    root = _docstring_repo(
        tmp_path,
        _FIXTURE_A,
        (
            "unverifiable.py",
            '"""See (#4242) for the frozen rule.\n"""\n',
        ),
    )

    # Exit 0: UNVERIFIABLE does not gate (could-not-check, #136).
    assert citations.check_docstring_citations(root) == 0
    out = capsys.readouterr().out
    # The citation is UNVERIFIABLE, NOT UNRESOLVABLE — the discriminating
    # assertion.  If `readable` is ignored, #4242 falls to UNRESOLVABLE and
    # exit becomes 1; both assertions below fail.
    assert "UNVERIFIABLE" in out and "#4242" in out
    assert "could not check" in out
    assert "UNRESOLVABLE" not in out
    assert "FAIL" not in out
    # The OK verdict reports the unverifiable count.
    assert "1 unverifiable" in out
