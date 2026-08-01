"""Standing contract for the citation classification made by #801."""
from pathlib import Path

from dev import check_watch_citations as citations


ROOT = Path(__file__).resolve().parent


# repo-wide-guard: checks every citation in the explicit multi-document #801 population
def test_reviewed_watch_citation_population_is_still_resolved(capsys):
    assert citations.check(ROOT) == 0
    output = capsys.readouterr().out
    assert (
        f"PASS: #801's {citations.EXPECTED_CLASSIFIED_CITATIONS} classified "
        f"+{citations.DRIFT} watch.py citation(s) resolved"
    ) in output


def test_zero_resolved_citations_is_a_fault_not_a_vacuous_pass(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(citations, "stale_citations", lambda _root: [])
    assert citations.check(tmp_path) == 2
    assert (
        "ERROR population: #801's classified inventory resolved 0 shifted citation(s), "
        f"expected {citations.EXPECTED_CLASSIFIED_CITATIONS}"
    ) in capsys.readouterr().out
