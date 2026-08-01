#!/usr/bin/env python3
"""Check the #689-shifted ``watch.py`` citations classified by #801.

The twelve-line insertion after ``dc739001`` gives this check a deliberately
narrow, high-confidence oracle: an unqualified citation to N is stale when the
old text at N is byte-for-byte the current text at N+12.  Living prose must not
keep that unstable number.  Historical records may keep it only when the
citation names the source revision it describes.

This is not a general semantic citation verifier.  Four documents whose
shift-shaped matches were wholly attributed to the pre-existing reviewed
population are excluded here; ``test_reanchor_citations.py`` remains their
existing gate.  The #801 inventory itself is explicit because deciding whether
a document is living or historical is judgement, not a path heuristic.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
BASE_REV = "dc739001"
DRIFT = 12

# Re-derived from the exact old-line/current-line comparison.  These are the
# files outside the reviewed population that contained a positive match at the
# #801 baseline.  Keeping the inventory explicit prevents a future broad scan
# from silently reclassifying a historical record as living prose.
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

# These records describe a measured past tree.  Their old coordinates remain
# evidence once the compared revision is adjacent to the citation.
HISTORICAL_DOCS = {
    ".dreamwork/docs/262-witness-audit.md",
    ".dreamwork/docs/briefs/172-project-identity-in-title.md",
    ".dreamwork/docs/briefs/269-draftstore.md",
    ".dreamwork/docs/briefs/547-composer-default-runmode-removal.md",
    ".dreamwork/docs/briefs/548-bdinput-cap-binding.md",
    ".dreamwork/docs/briefs/551-posture-remind.md",
    ".dreamwork/docs/briefs/560-status-from-store.md",
    ".dreamwork/docs/briefs/562-chat-surface.md",
    ".dreamwork/docs/handoffs/2026-07-29-0810-claude-to-grok.md",
    ".dreamwork/docs/plans/render-architecture.md",
    ".dreamwork/handoffs.md",
    ".dreamwork/lane-641-report.md",
    ".dreamwork/lane-645i5-report.md",
    ".dreamwork/lane-721-report.md",
    ".dreamwork/lane-751-report.md",
    ".dreamwork/lane-752-report.md",
    ".dreamwork/lane-752rest-report.md",
    ".dreamwork/review/evidence/309-skill-coherence-audit.md",
    ".dreamwork/reviews-cx-session-2026-08-01.md",
}

# These four files are wholly inside the reviewed-anchor population named in
# the dispatch.  #801 deliberately does not widen that population.
REVIEWED_DOCS = {
    ".dreamwork/docs/plans/hub-public-auth.md",
    ".dreamwork/docs/plans/subagent-containment.md",
    ".dreamwork/docs/plans/task-transition-boundary.md",
    ".dreamwork/docs/plans/user-settings.md",
}

CITATION = re.compile(
    r"(?<![\w/])(?P<path>(?:[A-Za-z0-9_][\w./-]*/)?watch\.py):(?P<line>\d+)"
    r"(?P<tail>(?:\s*[-–]\s*\d+)?\+?)"
)


@dataclass(frozen=True)
class StaleCitation:
    doc: str
    doc_line: int
    source_line: int
    token: str
    pinned: bool


def _run(root: Path, *argv: str) -> str:
    proc = subprocess.run(argv, cwd=root, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "command failed: " + " ".join(argv))
    return proc.stdout


def _old_lines(root: Path) -> list[str]:
    return _run(root, "git", "show", f"{BASE_REV}:watch.py").splitlines()


def _tracked_markdown(root: Path) -> list[str]:
    return [rel for rel in _run(root, "git", "ls-files").splitlines() if rel.endswith(".md")]


def _is_shifted(old: list[str], current: list[str], line: int) -> bool:
    return (
        1 <= line <= len(old)
        and line + DRIFT <= len(current)
        and old[line - 1] == current[line + DRIFT - 1]
    )


def stale_citations(root: Path) -> list[StaleCitation]:
    old = _old_lines(root)
    current = (root / "watch.py").read_text(encoding="utf-8").splitlines()
    result: list[StaleCitation] = []
    for rel in _tracked_markdown(root):
        if rel in REVIEWED_DOCS:
            continue
        lines = (root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        for doc_line, text in enumerate(lines, 1):
            for match in CITATION.finditer(text):
                line = int(match.group("line"))
                if not _is_shifted(old, current, line):
                    continue
                suffix = text[match.end():]
                pinned = re.match(rf"\s*@\s*{BASE_REV}\b", suffix) is not None
                result.append(StaleCitation(rel, doc_line, line, match.group(), pinned))
    return result


def fix(root: Path) -> tuple[int, int]:
    findings = stale_citations(root)
    by_doc: dict[str, list[StaleCitation]] = {}
    for item in findings:
        if item.doc in AFFECTED_DOCS and not item.pinned:
            by_doc.setdefault(item.doc, []).append(item)
    changed = 0
    replacements = 0
    for rel, items in sorted(by_doc.items()):
        path = root / rel
        text = path.read_text(encoding="utf-8")

        def replace(match: re.Match[str]) -> str:
            nonlocal replacements
            line = int(match.group("line"))
            if not any(item.source_line == line and item.token == match.group() for item in items):
                return match.group()
            replacements += 1
            if rel in HISTORICAL_DOCS:
                return f"{match.group()} @ {BASE_REV}"
            return match.group("path")

        rewritten = CITATION.sub(replace, text)
        if rewritten != text:
            path.write_text(rewritten, encoding="utf-8")
            changed += 1
    return changed, replacements


def check(root: Path) -> int:
    if len(AFFECTED_DOCS) != 34:
        print(f"ERROR inventory: expected 34 affected docs, got {len(AFFECTED_DOCS)}")
        return 2
    findings = [item for item in stale_citations(root) if not item.pinned]
    if findings:
        for item in findings:
            print(
                f"STALE {item.doc}:{item.doc_line}: {item.token} is {DRIFT} lines behind "
                f"its byte-identical evidence at watch.py:{item.source_line + DRIFT}"
            )
        print(f"FAIL: {len(findings)} unqualified shifted citation(s)")
        return 1
    pinned = sum(item.pinned for item in stale_citations(root))
    print(
        f"PASS: no unqualified +{DRIFT} watch.py citations; "
        f"{pinned} historical citation(s) explicitly pinned to {BASE_REV}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--fix", action="store_true", help="rewrite only the reviewed #801 inventory")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.fix:
        changed, replacements = fix(root)
        print(f"rewrote {replacements} citation(s) across {changed} document(s)")
    return check(root)


if __name__ == "__main__":
    raise SystemExit(main())
