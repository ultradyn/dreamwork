"""Guard: a posture ruling cited in a plan doc must carry its boundary case (#660).

The #445/#342 widen-not-sibling ruling was recorded unconditionally across the
plan docs — stated for *all* posture fields when its justification (the
closed-set discipline guards it for free) only holds for *closed-set* axes.
``#650`` found that boundary: a free-text field inherits no closed-set guard, so
the ruling does not decide its storage shape.  Commits ``66337807`` (the two
named docs) and the ``#660`` extension scoped every statement to closed-set axes
and named the ``#650`` boundary explicitly.

This test catches a reversion: if a doc cites the ruling but drops the ``#650``
boundary reference, the ruling reads as unconditional again — wider than its
justification supports.  The check scans **every** plan doc, not just the two
the prior round named, because the ruling is stated as a *standing precedent*
and a sibling construct (``delivery-modes.md``) carried the same defect until
this fix — the #690 "named site is an example, not the inventory" hazard.  The
detection is structural (issue-number-based, not phrase-based) so it survives
rewording, and it asserts a non-zero population so it cannot pass vacuously
(#671).
"""

from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent
PLANS_DIR = SKILL_DIR / ".dreamwork" / "docs" / "plans"


def _paragraphs(text: str) -> list[str]:
    """Split into paragraphs: blocks of consecutive non-blank lines."""
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def _invokes_ruling(para: str) -> bool:
    """A paragraph invokes the widen-not-sibling ruling when it cites #445 or
    #342 (the ruling's source decisions) AND names both ``sibling`` and
    ``widen`` — the combination that identifies the widen-not-sibling decision
    rather than an unrelated #445 citation (also about asking levels, IGC) or
    an unrelated use of "sibling" (a related task, a DOM sibling)."""
    low = para.lower()
    cites_ruling_source = "#445" in para or "#342" in para
    return cites_ruling_source and "sibling" in low and "widen" in low


def _cites_boundary(para: str) -> bool:
    """The paragraph names the #650 boundary case (free text inherits no
closed-set guard). A task id is a stable token, so this survives rewording."""
    return "#650" in para


def _plan_docs() -> list[Path]:
    return sorted(PLANS_DIR.glob("*.md"))


def test_widen_not_sibling_ruling_carries_its_boundary():
    """Every paragraph that invokes the #445/#342 widen-not-sibling ruling must
    also cite #650 — the boundary case that found where the ruling stops.

    Without the boundary, the ruling reads as unconditional: stated for all
    posture fields, when its justification (closed-set discipline guards it
    for free) only covers closed-set axes.  #660. Scans every plan doc because
    the ruling is a standing precedent, and a sibling construct carried the
    same defect after the two named docs were fixed (#690)."""
    missing = []
    for doc in _plan_docs():
        text = doc.read_text()
        for para in _paragraphs(text):
            if _invokes_ruling(para) and not _cites_boundary(para):
                missing.append(doc.name)
    assert not missing, (
        "widen-not-sibling ruling stated without #650 boundary in: "
        + ", ".join(sorted(set(missing)))
        + " — the ruling's stated scope exceeds the justification that "
        "supports it (the closed-set-discipline premise is false for "
        "free-text fields, so the ruling does not decide free-text storage; "
        "#650 found the boundary). State the scope: closed-set axes, with "
        "the free-text boundary explicit (#660)."
    )


def test_guard_examined_a_nonzero_population():
    """The guard must find ruling paragraphs across the plan docs — a guard
that examined nothing must not read as passing (#671). The floor is a minimum,
not the exact count, so it does not expire when a doc is added or removed."""
    total = 0
    for doc in _plan_docs():
        text = doc.read_text()
        found = [p for p in _paragraphs(text) if _invokes_ruling(p)]
        total += len(found)
    assert total >= 2, (
        f"expected at least 2 widen-not-sibling ruling paragraphs across "
        f"plan docs, found {total} — the population shrank below what this "
        f"guard was written for (#671: a check that examined nothing must "
        f"not read as passing)"
    )
