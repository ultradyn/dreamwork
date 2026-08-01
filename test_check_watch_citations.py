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
