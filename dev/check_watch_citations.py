#!/usr/bin/env python3
"""Check the #689-shifted ``watch.py`` citations classified by #801.

The insertion after ``dc739001`` gives this check a deliberately narrow,
high-confidence oracle: an unqualified citation to N is stale when the old text
at N is byte-for-byte the current text at N+DRIFT.  Living prose must not keep
that unstable number.  Historical records may keep it only when the citation
names the source revision it describes.  DRIFT is a hand-measured constant and
that is the defect #845 exists to fix — see the note at its definition.

This is not a general semantic citation verifier.  Four documents whose
shift-shaped matches were wholly attributed to the pre-existing reviewed
population are excluded here; ``test_reanchor_citations.py`` remains their
existing gate.  The #801 inventory itself is explicit because deciding whether
a document is living or historical is judgement, not a path heuristic.

IGC, in the context of a frequently edited source file: G1 is survival across
future line movement; G2 is honest current evidence; G3 is preservation of a
historical record.  Adding the drift fails G1.  Pinning every citation fails G2 for
living prose.  Removing decorative numbers fails G3 for records.  The surviving
classification is therefore symbol/context without a number for living prose,
and the original number plus an explicit revision for historical evidence.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
BASE_REV = "dc739001"
# A HAND-MEASURED CONSTANT, and #845 is open because that is the wrong shape.
# It was 12 when #801 classified the population; #843's ten-line hunk at
# watch.py:366 sits above every classified citation and moved all 24 to +22 in
# one step, turning a lane's ordinary insertion into a master-red.  Any net
# insertion above the cited region breaks this identically whether it is +1 or
# +150 — it is exact-match, not a threshold.  Worse than fragile: because the
# constant is global, the guard only ever sees the cluster that happens to sit
# at this offset.  Measured today, citations into surviving watch.py lines sit
# at +0 (16, genuinely unshifted), +10 (62), +22 (24, the population below),
# and +83/+227/+228/+262/+347/+348 (24 more) — so 82 equally stale citations
# are invisible to this check by construction.  #845 replaces the constant with
# a per-citation offset derived from the real diff against BASE_REV.
# #864 added a three-line import at watch.py:53 — above every classified
# citation — so the true offset from dc739001 is now 25.  This is the
# maintenance #845 exists to abolish: the constant is global and exact,
# so ANY net insertion above the region is a master-red until it is
# re-measured by hand.  The certified multiset is unchanged by the bump,
# which is what proves the re-measure correct rather than merely quiet.
DRIFT = 25

# Distinctiveness: a matched old line is evidence only when it is non-empty,
# unique in the base revision, and long enough to be about something.  A blank
# line (681 copies in dc739001:watch.py) is byte-identical to every other blank
# line, so it can only ever confirm the offset you already guessed — #764 as a
# measurement.  The length floor is the widest gap in the data: every certified
# line is >=30 chars, every non-blank weak line is <=20, so any threshold in
# [21,29] produces the same partition.  Uniqueness alone (non-empty ∧ unique)
# admits one extra citation — `watch.py:4026-4036`, old line `    return entry`
# (16 chars, unique) — but a four-token return statement is one future edit
# away from a duplicate, so length is a stability proxy, not merely a
# distinctiveness proxy.  See the 2026-08-01 lesson on this check.
DISTINCTIVE_MIN_LEN = 25

# Living citations were removed by #801, so the standing resolvable population
# is the historical subset that remains deliberately line-pinned.  Re-measured
# at 19 after the distinctiveness rule excludes five weak +22 matches (two
# blank lines, two short lines, one non-unique line).
EXPECTED_CLASSIFIED_CITATIONS = 19

# The exact multiset of citations the guard certifies (distinctive +DRIFT
# byte-matches in AFFECTED_DOCS).  Binding the multiset — not a size — closes
# the vacuity guard against wrong-member substitution and dropped duplicates
# (#702; #841 produced a live case where a set() assertion passed over a
# duplicated multiset).  A Counter comparison preserves duplicates; a set()
# would silently drop one.  handoffs.md:395 legitimately carries two citations
# on one line, and handoffs.md cites source line 3654 twice (doc lines 169 and
# 225), so the 4-tuple (doc, doc_line, source_line, token) is the identity.
EXPECTED_CERTIFIED_MULTISET: frozenset[tuple[str, int, int, str]] = frozenset({
    (".dreamwork/docs/briefs/547-composer-default-runmode-removal.md", 44, 4101, "watch.py:4101"),
    (".dreamwork/docs/briefs/547-composer-default-runmode-removal.md", 46, 4100, "watch.py:4100"),
    (".dreamwork/docs/briefs/548-bdinput-cap-binding.md", 15, 3712, "watch.py:3712"),
    (".dreamwork/docs/briefs/548-bdinput-cap-binding.md", 16, 3931, "watch.py:3931"),
    (".dreamwork/docs/briefs/548-bdinput-cap-binding.md", 41, 3712, "watch.py:3712"),
    (".dreamwork/docs/briefs/562-chat-surface.md", 25, 4037, "watch.py:4037-4040"),
    (".dreamwork/docs/briefs/562-chat-surface.md", 74, 4020, "watch.py:4020-4027"),
    (".dreamwork/docs/handoffs/2026-07-29-0810-claude-to-grok.md", 138, 4019, "watch.py:4019-4021"),
    (".dreamwork/handoffs.md", 118, 4412, "watch.py:4412"),
    (".dreamwork/handoffs.md", 123, 3942, "watch.py:3942"),
    (".dreamwork/handoffs.md", 169, 3654, "watch.py:3654"),
    (".dreamwork/handoffs.md", 225, 3654, "watch.py:3654"),
    (".dreamwork/handoffs.md", 326, 4039, "watch.py:4039"),
    (".dreamwork/handoffs.md", 395, 4050, "watch.py:4050"),
    (".dreamwork/handoffs.md", 395, 4135, "watch.py:4135-4145"),
    (".dreamwork/lane-641-report.md", 136, 4068, "watch.py:4068"),
    (".dreamwork/lane-645i5-report.md", 65, 3476, "watch.py:3476"),
    (".dreamwork/reviews-cx-session-2026-08-01.md", 49, 3999, "watch.py:3999-4006"),
    (".dreamwork/reviews-cx-session-2026-08-01.md", 99, 3946, "watch.py:3946-3974"),
})

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


def _is_distinctive(old_counts: Counter, line_text: str) -> bool:
    """A matched line is evidence only when it could not match by coincidence."""
    return (
        bool(line_text.strip())
        and old_counts[line_text] == 1
        and len(line_text) >= DISTINCTIVE_MIN_LEN
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


def _scan_affected_citations(
    root: Path, old: list[str], current: list[str], old_counts: Counter
) -> list[tuple[str, int, int, str, str, bool]]:
    """Classify every ``watch.py:N`` citation in AFFECTED_DOCS by adjudication class.

    Returns ``(doc, doc_line, source_line, token, cls, pinned)`` tuples where
    ``cls`` is one of:

    * ``certified`` — a distinctive +DRIFT byte-match (evidence the citation is
      the reviewed, shifted one).
    * ``weak`` — a +DRIFT byte-match whose old line is blank, non-unique, or
      too short to be distinctive.  Not certified: the match could be
      coincidence.
    * ``out_of_range`` — the cited line is beyond the base revision's end, so
      the oracle cannot adjudicate it by construction.  Authored against a
      later tree.
    * ``non_surviving`` — in range, but the old line does not appear at +DRIFT
      in the current file.  May survive at a different offset or be gone; the
      single-offset oracle cannot tell.
    """
    result: list[tuple[str, int, int, str, str, bool]] = []
    for rel in sorted(AFFECTED_DOCS):
        if rel in REVIEWED_DOCS:
            continue
        path = root / rel
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for doc_line, text in enumerate(lines, 1):
            for match in CITATION.finditer(text):
                line = int(match.group("line"))
                token = match.group()
                suffix = text[match.end():]
                pinned = re.match(rf"\s*@\s*{BASE_REV}\b", suffix) is not None
                if line > len(old):
                    cls = "doubly_out_of_range" if line > len(current) else "out_of_range"
                elif not _is_shifted(old, current, line):
                    cls = "non_surviving"
                elif not _is_distinctive(old_counts, old[line - 1]):
                    cls = "weak"
                else:
                    cls = "certified"
                result.append((rel, doc_line, line, token, cls, pinned))
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
    old = _old_lines(root)
    current = (root / "watch.py").read_text(encoding="utf-8").splitlines()
    old_counts = Counter(old)

    scanned = _scan_affected_citations(root, old, current, old_counts)

    # The corpus the oracle reads must be non-empty, or every class resolves to
    # zero and the check is green over nothing (#671).  Name the size so a
    # future change that empties the corpus cannot hide behind a count of 0.
    n_old = len(old)
    n_cur = len(current)
    if n_old == 0:
        print(f"ERROR vacuity: BASE_REV {BASE_REV} resolved to {n_old} watch.py lines; the oracle cannot see an empty base")
        return 2

    by_class: dict[str, list[tuple[str, int, int, str, bool]]] = {
        "certified": [], "weak": [],
        "out_of_range": [], "doubly_out_of_range": [],
        "non_surviving": [],
    }
    for doc, doc_line, src, token, cls, pinned in scanned:
        by_class.setdefault(cls, []).append((doc, doc_line, src, token, pinned))
    certified = by_class["certified"]
    weak = by_class["weak"]
    oor = by_class["out_of_range"]
    doubly_oor = by_class["doubly_out_of_range"]
    nonsurv = by_class["non_surviving"]

    # Bind the exact multiset, not a size.  A size-only expectation permits
    # wrong-member substitution; a set() drops duplicates (#702; #841's live
    # case).  Counter preserves duplicates and distinguishes members.
    got = Counter((d, dl, s, t) for d, dl, s, t, _ in certified)
    want = Counter(EXPECTED_CERTIFIED_MULTISET)
    if got != want:
        only_got = got - want
        only_want = want - got
        detail = []
        for key in sorted(only_got):
            detail.append(f"+{key}")
        for key in sorted(only_want):
            detail.append(f"-{key}")
        print(
            "ERROR population: #801's certified inventory resolved "
            f"{len(certified)} distinctive +{DRIFT} citation(s); the certified "
            f"multiset differs from EXPECTED_CERTIFIED_MULTISET "
            f"({' '.join(detail) if detail else 'size only'})"
        )
        return 2

    findings = [item for item in certified if not item[4]]
    laundering = [
        item for item in certified
        if item[4] and item[0] not in HISTORICAL_DOCS
    ]
    if findings or laundering:
        for doc, doc_line, src, token, _ in findings:
            print(
                f"STALE {doc}:{doc_line}: {token} is {DRIFT} lines behind "
                f"its byte-identical evidence at watch.py:{src + DRIFT}"
            )
        for doc, doc_line, src, token, _ in laundering:
            print(
                f"STALE-LIVING {doc}:{doc_line}: {token} is revision-pinned "
                "inside a living document; a pin must not launder current prose as historical"
            )
        print(
            f"FAIL: {len(findings)} unqualified and {len(laundering)} "
            "misclassified shifted citation(s)"
        )
        return 1
    pinned = sum(1 for _, _, _, _, p in certified)
    # Report every class, including the ones the oracle did NOT adjudicate.
    # A check that says what it did not examine is worth more than one that
    # certifies its survivors and is silent about the rest (#671).  The
    # doubly-out-of-range class — citations past BOTH the base revision and
    # the current file — is simply wrong: it cannot be adjudicated by any
    # future tree because the line does not exist now, and it was never in the
    # base.  It is reported as a count so the size of the blind spot is
    # visible, and named distinctly from out-of-range (which a later tree
    # could still adjudicate).
    print(
        f"PASS: #801's {len(certified)} certified +{DRIFT} watch.py citation(s) "
        f"resolved ({pinned} pinned to {BASE_REV}); "
        f"{len(weak)} weak not certified; "
        f"{len(oor)} out-of-range; "
        f"{len(doubly_oor)} doubly-out-of-range (past both ends); "
        f"{len(nonsurv)} non-surviving; "
        f"{n_old} base lines, {n_cur} current lines"
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
