"""Guard: a posture ruling cited in a plan doc must carry its boundary case (#660).

The #445/#342 widen-not-sibling ruling was recorded unconditionally in two plan
docs — stated for *all* posture fields when its justification (the closed-set
discipline guards it for free) only holds for *closed-set* axes.  ``#650`` found
that boundary: a free-text field inherits no closed-set guard, so the ruling does
not decide its storage shape.  Commit ``66337807`` scoped both docs to closed-set
axes and named the ``#650`` boundary explicitly.

This test catches a reversion: if a doc cites the ruling but drops the ``#650``
boundary reference, the ruling reads as unconditional again — wider than its
justification supports.  The check is structural (issue-number-based, not
phrase-based) so it survives rewording, and it asserts a non-zero population so
it cannot pass vacuously (#671).
"""

from pathlib import Path

import pytest

# The two plan docs this guard owns (#660's lane scope).
DOCS = [
    ".dreamwork/docs/plans/orchestrator-posture.md",
    ".dreamwork/docs/plans/posture-autonomy-axis.md",
]

SKILL_DIR = Path(__file__).resolve().parent


def _paragraphs(text: str) -> list[str]:
    """Split into paragraphs: blocks of consecutive non-blank lines."""
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def _invokes_ruling(para: str) -> bool:
    """A paragraph invokes the widen-not-sibling ruling when it discusses the
    sibling-vs-widen choice for posture AND cites #445 or #342 (the ruling's
    source decisions)."""
    cites_ruling_source = "#445" in para or "#342" in para
    discusses_sibling = "sibling" in para.lower()
    return cites_ruling_source and discusses_sibling


def _cites_boundary(para: str) -> bool:
    """The paragraph names the #650 boundary case (free text inherits no
    closed-set guard)."""
    return "#650" in para


@pytest.mark.parametrize("rel", DOCS)
def test_widen_not_sibling_ruling_carries_its_boundary(rel: str):
    """Every paragraph that invokes the #445/#342 widen-not-sibling ruling must
    also cite #650 — the boundary case that found where the ruling stops.

    Without the boundary, the ruling reads as unconditional: stated for all
    posture fields, when its justification (closed-set discipline guards it
    for free) only covers closed-set axes.  #660."""
    path = SKILL_DIR / rel
    text = path.read_text()
    ruling_paragraphs = [p for p in _paragraphs(text) if _invokes_ruling(p)]
    assert ruling_paragraphs, (
        f"{rel}: expected at least one paragraph invoking the widen-not-sibling "
        f"ruling (#445/#342 + sibling) — a doc that cites neither has either "
        f"been rewritten to remove the ruling or is the wrong file (#671)"
    )
    missing = [p for p in ruling_paragraphs if not _cites_boundary(p)]
    assert not missing, (
        f"{rel}: {len(missing)} paragraph(s) invoke the #445/#342 widen-not-sibling "
        f"ruling but do not cite #650 (the boundary case). The ruling is stated "
        f"without its scope — wider than its justification supports. A free-text "
        f"field inherits no closed-set guard, so the ruling does not decide its "
        f"storage shape (#650). State the scope: closed-set axes, with the "
        f"free-text boundary explicit (#660)."
    )


def test_guard_examined_a_nonzero_population():
    """The guard must find ruling paragraphs in BOTH docs — a guard that
    examined nothing must not read as passing (#671). This asserts the
    population the per-doc check above depends on."""
    total = 0
    for rel in DOCS:
        text = (SKILL_DIR / rel).read_text()
        found = [p for p in _paragraphs(text) if _invokes_ruling(p)]
        assert found, f"{rel}: no ruling paragraphs found — population is zero (#671)"
        total += len(found)
    assert total >= 2, (
        f"expected at least 2 ruling paragraphs across {len(DOCS)} docs, "
        f"found {total} — the population shrank below what this guard was "
        f"written for (#671)"
    )
