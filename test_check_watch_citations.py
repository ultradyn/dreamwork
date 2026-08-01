"""Standing contract for the citation classification made by #801."""
from pathlib import Path

from dev import check_watch_citations as citations


ROOT = Path(__file__).resolve().parent


# repo-wide-guard: checks every citation in the explicit multi-document #801 population
def test_reviewed_watch_citation_population_is_still_resolved(capsys):
    assert citations.check(ROOT) == 0
    output = capsys.readouterr().out
    assert (
        f"PASS: #801's {citations.EXPECTED_CLASSIFIED_CITATIONS} certified "
        f"+{citations.DRIFT} watch.py citation(s) resolved"
    ) in output
    # The PASS line must report every class, including what it did NOT examine.
    assert " weak not certified" in output
    assert " out-of-range" in output
    assert " doubly-out-of-range" in output
    assert " non-surviving" in output
    assert " base lines" in output
    # The certified multiset must bind exactly — size alone permits substitution.
    assert citations.EXPECTED_CERTIFIED_MULTISET is not None
    assert len(citations.EXPECTED_CERTIFIED_MULTISET) == citations.EXPECTED_CLASSIFIED_CITATIONS


def test_zero_resolved_citations_is_a_fault_not_a_vacuous_pass(monkeypatch, capsys):
    # An empty scan must fail, not pass.  Patch the classifier to return
    # nothing: the multiset assertion fires (Counter() != expected) before the
    # vacuity line is reached, naming the certified-count gap.
    monkeypatch.setattr(citations, "_scan_affected_citations", lambda *a, **k: [])
    assert citations.check(ROOT) == 2
    out = capsys.readouterr().out
    assert "ERROR population" in out
    assert "certified multiset differs" in out
