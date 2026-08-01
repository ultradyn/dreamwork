"""Standing contract for the citation pins retained by #921."""

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
    (".dreamwork/docs/handoffs/2026-07-29-0810-claude-to-grok.md", "watch.py:4019-4021"): 1,
    (".dreamwork/handoffs.md", "watch.py:3654"): 2,
    (".dreamwork/handoffs.md", "watch.py:3942"): 1,
    (".dreamwork/handoffs.md", "watch.py:4039"): 1,
    (".dreamwork/handoffs.md", "watch.py:4050"): 1,
    (".dreamwork/handoffs.md", "watch.py:4135-4145"): 1,
    (".dreamwork/handoffs.md", "watch.py:4412"): 1,
    (".dreamwork/lane-641-report.md", "watch.py:4068"): 1,
    (".dreamwork/lane-645i5-report.md", "watch.py:3476"): 1,
    (".dreamwork/reviews-cx-session-2026-08-01.md", "watch.py:3946-3974"): 1,
    (".dreamwork/reviews-cx-session-2026-08-01.md", "watch.py:3999-4006"): 1,
})


# repo-wide-guard: checks every citation in the explicit multi-document #801 population
def test_reviewed_watch_citation_population_is_still_resolved(capsys):
    assert citations.PINNED_CITATIONS == REVIEWED_PIN_COUNTS
    assert REVIEWED_PIN_COUNTS.total() == 19
    assert citations.check(ROOT) == 0
    output = capsys.readouterr().out
    assert (
        "PASS: 19 of 19 pinned across 34 document(s); 216 citation(s) seen — "
        "pinned, not verified against the pinned revision"
    ) in output


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
    assert (
        "MISSING doc.md: watch.py:2: expected 1 occurrence(s), saw 0"
        in capsys.readouterr().out
    )
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
    assert (
        "UNPINNED doc.md: watch.py:2: occurrence 1 of 1 is not followed by @ <rev>"
        in capsys.readouterr().out
    )

    (root / "doc.md").write_text("watch.py:2 @ deadbeef\n", encoding="utf-8")
    assert citations.check(root) == 1
    assert (
        "UNRESOLVABLE doc.md: watch.py:2: @ deadbeef does not resolve to a commit"
        in capsys.readouterr().out
    )
