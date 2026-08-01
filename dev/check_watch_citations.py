#!/usr/bin/env python3
"""Check that #801's historical citations remain revision-pinned.

This guard binds only the ``(document, citation token)`` multiset and checks
that every occurrence is followed by a revision which resolves to a commit.
The coordinates are pinned, not verified against the pinned revision.  In
particular, the check never reads ``watch.py`` and cannot claim that a pinned
coordinate identifies the intended source at that revision.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]

# Derived from the former oracle's 19-member certified population.  Counter is
# load-bearing: two identities occur twice and must not collapse to a set.
PINNED_CITATIONS: Counter[tuple[str, str]] = Counter({
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

AFFECTED_DOCS = {
    ".dreamwork/docs/262-witness-audit.md",
    ".dreamwork/docs/briefs/172-project-identity-in-title.md",
    ".dreamwork/docs/briefs/269-draftstore.md",
    ".dreamwork/docs/briefs/547-composer-default-runmode-removal.md",
    ".dreamwork/docs/briefs/548-bdinput-cap-binding.md",
    ".dreamwork/docs/briefs/551-posture-remind.md",
    ".dreamwork/docs/briefs/560-status-from-store.md",
    ".dreamwork/docs/briefs/562-chat-surface.md",
    ".dreamwork/docs/cx-645-db-api-design.md",
    ".dreamwork/docs/cx-750-check-design.md",
    ".dreamwork/docs/handoffs/2026-07-29-0810-claude-to-grok.md",
    ".dreamwork/docs/plans/delivery-modes.md",
    ".dreamwork/docs/plans/filebytes-range.md",
    ".dreamwork/docs/plans/main-agent-recap.md",
    ".dreamwork/docs/plans/posture-autonomy-axis.md",
    ".dreamwork/docs/plans/question-updated-wake.md",
    ".dreamwork/docs/plans/render-architecture.md",
    ".dreamwork/docs/plans/session-log-view.md",
    ".dreamwork/docs/plans/superseded-contracts.md",
    ".dreamwork/docs/plans/tasks-page.md",
    ".dreamwork/docs/plans/user-event-journal-implementation.md",
    ".dreamwork/docs/plans/ws-delta-transport.md",
    ".dreamwork/docs/reload-signal-design.md",
    ".dreamwork/docs/research/contextual-review-annotations.md",
    ".dreamwork/handoffs.md",
    ".dreamwork/lane-641-report.md",
    ".dreamwork/lane-645i5-report.md",
    ".dreamwork/lane-721-report.md",
    ".dreamwork/lane-751-report.md",
    ".dreamwork/lane-752-report.md",
    ".dreamwork/lane-752rest-report.md",
    ".dreamwork/questions.md",
    ".dreamwork/review/evidence/309-skill-coherence-audit.md",
    ".dreamwork/reviews-cx-session-2026-08-01.md",
}

CITATION = re.compile(
    r"(?<![\w/])(?P<path>(?:[A-Za-z0-9_][\w./-]*/)?watch\.py):(?P<line>\d+)"
    r"(?P<tail>(?:\s*[-–]\s*\d+)?\+?)"
)
# A slash after a hash belongs to prose such as ``@ dc739001/4056`` (old/new
# coordinates), not to the revision.  The guarded corpus uses commit hashes.
PIN = re.compile(r"\s*@\s*(?P<rev>[0-9a-fA-F]{7,40})\b")


def _scan_affected_citations(
    root: Path,
) -> tuple[int, int, dict[tuple[str, str], list[str | None]]]:
    """Return runtime denominators and pins for the bound citation identities."""
    docs_scanned = 0
    citations_seen = 0
    pins: dict[tuple[str, str], list[str | None]] = {}
    for rel in sorted(AFFECTED_DOCS):
        path = root / rel
        if not path.is_file():
            continue
        docs_scanned += 1
        for text in path.read_text(encoding="utf-8", errors="replace").splitlines():
            for match in CITATION.finditer(text):
                citations_seen += 1
                key = (rel, match.group())
                if key not in PINNED_CITATIONS:
                    continue
                pin = PIN.match(text[match.end():])
                pins.setdefault(key, []).append(pin.group("rev") if pin else None)
    return docs_scanned, citations_seen, pins


def _revision_resolves(root: Path, revision: str) -> bool:
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"{revision}^{{commit}}"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    return proc.returncode == 0


def check(root: Path) -> int:
    docs_scanned, citations_seen, pins = _scan_affected_citations(root)
    if docs_scanned == 0:
        print("ERROR vacuity: docs_scanned denominator is empty (0 documents scanned)")
        return 2
    if citations_seen == 0:
        print(
            "ERROR vacuity: citations_seen denominator is empty "
            f"(0 citations seen across {docs_scanned} document(s))"
        )
        return 2

    seen = Counter({key: len(revisions) for key, revisions in pins.items()})
    failed = False
    for (doc, token), count in sorted(PINNED_CITATIONS.items()):
        actual = seen[(doc, token)]
        if actual < count:
            print(
                f"MISSING {doc}: {token}: expected {count} occurrence(s), "
                f"saw {actual}"
            )
            failed = True
        elif actual > count:
            print(
                f"DUPLICATE {doc}: {token}: expected {count} occurrence(s), "
                f"saw {actual}"
            )
            failed = True

    pinned = 0
    resolved: dict[str, bool] = {}
    for (doc, token), revisions in sorted(pins.items()):
        expected = PINNED_CITATIONS[(doc, token)]
        for occurrence, revision in enumerate(revisions[:expected], 1):
            if revision is None:
                print(
                    f"UNPINNED {doc}: {token}: occurrence {occurrence} of "
                    f"{expected} is not followed by @ <rev>"
                )
                failed = True
                continue
            if revision not in resolved:
                resolved[revision] = _revision_resolves(root, revision)
            if not resolved[revision]:
                print(
                    f"UNRESOLVABLE {doc}: {token}: @ {revision} does not "
                    "resolve to a commit"
                )
                failed = True
                continue
            pinned += 1

    if failed:
        return 1

    expected = PINNED_CITATIONS.total()
    print(
        f"PASS: {pinned} of {expected} pinned across {docs_scanned} document(s); "
        f"{citations_seen} citation(s) seen — pinned, not verified against the "
        "pinned revision"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    return check(args.root.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
