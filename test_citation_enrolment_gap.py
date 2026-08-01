"""Narrow tests for `dev/citation_enrolment_gap.py`.

Selection is NARROW on purpose (#916): an over-broad named-test selection
widens the flake surface of every gate it touches.  Four tests cover the
load-bearing behaviour only — the gap is named, a covered occurrence is not
mis-counted as unenrolled, and BOTH denominators are loud at zero (#868) — and
each fixture is hand-written so the expectation is independent of the scanner
under test (#906).
"""

from __future__ import annotations

import subprocess
import textwrap
from collections import Counter
from pathlib import Path

from dev import citation_enrolment_gap as gap
from dev import check_watch_citations as guard


def _git(root: Path, *args: str) -> None:
    """Run git in ``root``; fail loud so a broken fixture does not silently pass."""
    subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    )


def _make_repo(root: Path, files: dict[str, str]) -> None:
    """Create a throwaway git repo at ``root`` with ``files`` committed at HEAD."""
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(body))
        _git(root, "add", "-f", rel)
    _git(root, "commit", "-q", "-m", "fixture")


# Independent literals: these are hand-written fixture content, NOT values
# derived from the scanner's output (#906).  The bad revision and the enrolled
# token are chosen so the fixture's bad pin is NOT at the enrolled identity.
BAD_REVISION = "dc739001"
ENROLLED_DOC = "doc/enrolled.md"
ENROLLED_TOKEN = "watch.py:111"
UNENROLLED_TOKEN = "watch.py:999"


def test_unenrolled_bad_pin_is_named_as_a_finding(monkeypatch, tmp_path, capsys):
    """A bad-pin occurrence NOT at an enrolled identity is the finding this tool exists for.

    Expectation source: the fixture places ``watch.py:999 @ dc739001`` in a doc
    whose only enrolled identity is ``watch.py:111``.  The unenrolled count of
    >= 1 derives from that hand-written mismatch, not from the scanner (#906).
    """
    _make_repo(
        tmp_path,
        {
            ENROLLED_DOC: f"See `{ENROLLED_TOKEN} @ deadbeef` for the truth.\n"
            f"Also `{UNENROLLED_TOKEN} @ {BAD_REVISION}` was never reviewed.\n",
        },
    )
    monkeypatch.setattr(
        guard,
        "PINNED_CITATIONS",
        Counter({(ENROLLED_DOC, ENROLLED_TOKEN): 1}),
    )
    enrolled, detected, hits = gap.scan(tmp_path)
    assert enrolled == 1, f"expected enrolled=1, saw {enrolled}"
    assert detected >= 1, f"expected >=1 detected, saw {detected}"
    unenrolled_tokens = {h.token for h in hits if not h.covered}
    assert UNENROLLED_TOKEN in unenrolled_tokens, (
        f"unenrolled occurrence {UNENROLLED_TOKEN!r} not named; saw {sorted(unenrolled_tokens)}"
    )
    # The report prints the finding and exits 0 (census, not guard).
    assert gap.report(tmp_path) == 0
    out = capsys.readouterr().out
    assert "FINDING:" in out
    assert "unenrolled=1" in out
    assert f"{UNENROLLED_TOKEN}" in out


def test_covered_occurrence_is_not_miscounted_as_unenrolled(monkeypatch, tmp_path, capsys):
    """A bad-pin occurrence AT an enrolled identity is covered, not unenrolled.

    This is the matching seam: the tool must distinguish an occurrence the
    enrolment ledger accounts for from one it does not.  Expectation derives
    from the fixture's enrolled identity matching the bad pin's token.
    """
    _make_repo(
        tmp_path,
        {
            ENROLLED_DOC: f"`{ENROLLED_TOKEN} @ {BAD_REVISION}` is enrolled but still bad.\n",
        },
    )
    monkeypatch.setattr(
        guard,
        "PINNED_CITATIONS",
        Counter({(ENROLLED_DOC, ENROLLED_TOKEN): 1}),
    )
    enrolled, detected, hits = gap.scan(tmp_path)
    assert enrolled == 1
    assert detected == 1
    covered = [h for h in hits if h.covered]
    assert len(covered) == 1, (
        f"expected the enrolled bad pin to be covered, saw {len(covered)} covered"
    )
    assert gap.report(tmp_path) == 0
    out = capsys.readouterr().out
    assert "unenrolled=0" in out


def test_zero_detected_is_a_fault_not_a_clean_corpus(monkeypatch, tmp_path, capsys):
    """detected=0 must exit 2 — a scan that found nothing is broken, not complete (#868, #915).

    A regex that silently stops matching reports the alarm and the all-clear
    identically; this test pins that a zero-detected run is a loud ERROR.
    """
    _make_repo(tmp_path, {"doc/clean.md": "# no bad pins here\n"})
    monkeypatch.setattr(
        guard, "PINNED_CITATIONS", Counter({("doc/clean.md", "watch.py:1"): 1})
    )
    rc = gap.report(tmp_path)
    assert rc == 2, "a run that detected zero occurrences must exit 2 (loud vacuity)"
    assert "detected is 0" in capsys.readouterr().out


def test_zero_enrolled_is_a_fault_not_a_clean_corpus(monkeypatch, tmp_path, capsys):
    """enrolled=0 must exit 2 — an empty enrolment ledger is a broken guard, not clean (#868)."""
    _make_repo(
        tmp_path,
        {"doc/bad.md": f"`watch.py:42 @ {BAD_REVISION}` is bad.\n"},
    )
    monkeypatch.setattr(guard, "PINNED_CITATIONS", Counter())
    rc = gap.report(tmp_path)
    assert rc == 2, "a run with an empty enrolment ledger must exit 2 (loud vacuity)"
    assert "enrolled is 0" in capsys.readouterr().out
