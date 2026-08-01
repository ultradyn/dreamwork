#!/usr/bin/env python3
"""Census of ``@ dc739001`` occurrences the enrolment ledger does not cover.

This is a CENSUS tool, not a guard.  It cross-checks the #847/#920 citation
campaign's *enrolled* population (the reviewed identities in
``dev/check_watch_citations.py``'s ``PINNED_CITATIONS``) against the *detected*
population (an independent scan for the bad revision ``dc739001`` across tracked
Markdown) and reports the **gap** as a first-class number:

    enrolled=18  detected=33  covered=0  unenrolled=33

The defect this exists to close (#937): the campaign's census enrolled 19 of 52
pinned ``@ dc739001`` occurrences and printed ``examined=19`` as if it were a
coverage statement.  A fixed denominator protects against SHRINKAGE (an enrolled
row disappearing) but is blind to OMISSION AT CONSTRUCTION — a literal can never
grow to reveal what it never knew about.  This instrument makes that omission
visible by naming every detected occurrence the enrolment ledger does not
account for.  **It is the mirror of #868**: #868 is a denominator that can
silently reach zero; this is a denominator that can never notice it is too small.

THE RULING THIS OBEYS (#925): detection is legitimate for the COVERAGE question
and illegitimate for the VERDICT question.  No regex can read prose and decide
whether a pin is false; only enrolment (a human's reviewed judgement) can.  So
this tool never asserts an unenrolled occurrence IS false — it asserts only that
it was never REVIEWED.  A non-zero ``unenrolled`` is a FINDING, not a verdict,
and it does NOT fail the run.  Failing on it would re-create the pressure to
bulk-repair that the campaign ruling exists to prevent; the coordinator reads the
list and dispatches per-citation judgement, one at a time, exactly as the 19
enrolled rows were judged.

WHAT EACH NUMBER IS AND WHERE IT COMES FROM (stated, because a number that
agrees with itself forever is the defect — #852/#905/#909):

  - ``enrolled``  — from ``PINNED_CITATIONS.total()`` in the GUARD.  This is the
                    enrolment ledger: the identities a human reviewed and judged.
                    It is NOT read from the campaign doc's ROWS table, so it
                    cannot agree with the doc against the world.
  - ``detected``  — from an INDEPENDENT regex scan for the literal ``@ dc739001``
                    across tracked Markdown.  This is the load-bearing number:
                    it is the only one that can reveal an enrolment the ledger
                    forgot.
  - ``covered``   — detected occurrences whose ``(document, citation token)``
                    identity IS in ``PINNED_CITATIONS`` and whose pin is
                    ``dc739001``.  After the enrolled rows are repaired they no
                    longer carry the bad pin, so ``covered`` drops to 0 and
                    ``unenrolled`` equals ``detected`` — that is expected, not a
                    contradiction: every detected occurrence that remains IS
                    unenrolled, because the enrolled ones were fixed.
  - ``unenrolled``— ``detected - covered``.  In the pre-repair state this
                    reproduces the campaign's gap (52 detected - 19 covered =
                    33); in the post-repair state it is 33 - 0 = 33.  The number
                    is stable across repair because it counts occurrences the
                    ledger never enrolled, not occurrences the ledger enrolled
                    and then fixed.

DEGRADE-TO-ZERO (#868): BOTH ``detected`` and ``enrolled`` are loud at zero.
``detected=0`` means the scan found nothing and is almost certainly a broken
glob, wrong cwd, or wrong pattern — it must NEVER read as "nothing left to
enrol."  ``enrolled=0`` means the guard's enrolment ledger is empty, which is a
broken guard, not a clean corpus.  A zero on either exits 2 with a loud ERROR.

STATED BLIND SPOTS (a scanner with silent scope is the defect this task closes):

  1. ``dc739001`` ONLY.  A citation pinned to a DIFFERENT stale revision (e.g.
     ``@ deadbeef``) is invisible, and ``unenrolled=0`` would read as complete.
     This is the most likely direction-2 failure: the campaign is about
     ``dc739001`` because that is where it started, not because that is the only
     wrong pin.  The tool states this limit; closing it needs a detector for
     every revision pin, which is a separate increment.
  2. PROSE MENTIONS are counted as detected.  A sentence such as "stripping one
     ``@ dc739001`` from …" contains the literal but is not a citation; it has
     no enrollable identity and is therefore always unenrolled.  The per-line
     output marks these so a reader does not mistake them for pins to judge.
  3. RUN FROM THE MAIN CHECKOUT.  Gitignored-but-present files do not travel into
     a lane worktree, so a worktree run under-counts detected.  Like
     ``dangling_citations.py``, the honest run is against the main checkout.
  4. The campaign census DOC and ``.dreamwork/dreams/*`` are excluded from
     detected, because both are meta-discussion: the doc is this instrument's
     own substrate, and dreams are process narrative that quotes citation forms
     as examples (``watch.py:42 @ dc739001`` in a dream is an illustration, not
     a factual claim).  Counting either inflates the gap with
     instrument-internal mentions.

Exit codes: ``0`` for a completed census (a non-zero unenrolled is the repo's
normal state today, so unenrolled-is-not-failure is intentional); ``2`` for
vacuity (a denominator reached zero) or a usage error.
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
# Run as ``python3 dev/citation_enrolment_gap.py`` (sys.path[0] is then ``dev/``,
# not the repo root), so put the repo root on sys.path to import the guard.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The guard's enrolment ledger and citation/pin regexes are the honest source
# for the ENROLLED side.  Importing them (rather than re-deriving from the doc's
# ROWS) means the enrolled population cannot agree with the doc against the
# world — it is whatever the guard currently binds (#852/#905/#909).
from dev import check_watch_citations as guard

# The campaign census document is this instrument's own substrate: its ROWS
# table and prose name the bad pin as the subject under judgement.
CAMPAIGN_DOC = ".dreamwork/docs/citation-repair-2026-08-02.md"

# The campaign doc AND dreams are excluded from the detected scan because both
# are meta-discussion, not citation-bearing prose.  Dreams are process narrative
# that quotes citation forms as EXAMPLES (``watch.py:42 @ dc739001`` in a dream
# is an illustration, not a factual claim).  Counting either would inflate the
# gap with instrument-internal mentions — a dream discussing the pin added 5
# spurious detections the first time this ran.
EXCLUDED = {CAMPAIGN_DOC}
EXCLUDED_PREFIXES = (".dreamwork/dreams/",)

# The bad revision this campaign is about.  Stated as a named constant because
# blind spot #1 is precisely that a DIFFERENT stale revision is invisible: the
# needle is load-bearing and must not be buried in a regex literal.
BAD_REVISION = "dc739001"

# A bare occurrence of the literal ``@ dc739001`` — matches the campaign's own
# measurement methodology (``git grep -o '@ dc739001'``).  Whitespace around the
# ``@`` is tolerated to match the guard's PIN regex.
LITERAL = re.compile(r"@\s*dc739001\b")


@dataclass(frozen=True)
class Occurrence:
    """One detected ``@ dc739001`` occurrence in the corpus."""

    doc: str
    line_no: int
    text: str
    token: str | None  # the ``watch.py:NNNN`` citation preceding the pin, or None
    covered: bool  # True iff (doc, token) is enrolled AND the pin is dc739001


def _tracked_docs(root: Path) -> list[str]:
    """Tracked Markdown documents as repo-relative strings, minus instrument substrate."""
    proc = subprocess.run(
        ["git", "ls-files", "-z", "*.md", "*.markdown"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    return [
        p
        for p in proc.stdout.split("\0")
        if p
        and p not in EXCLUDED
        and not p.startswith(EXCLUDED_PREFIXES)
    ]


def scan(root: Path) -> tuple[int, int, list[Occurrence]]:
    """Scan tracked Markdown under ``root``; return enrolled count and detected hits.

    ``enrolled`` is read from the guard's ``PINNED_CITATIONS`` (the enrolment
    ledger).  ``detected`` occurrences come from an independent regex scan for
    the bad revision.  An occurrence is ``covered`` iff its ``(doc, token)``
    identity is enrolled in the guard AND its pin is the bad revision — after the
    enrolled rows are repaired, ``covered`` is 0 because the enrolled identities
    no longer carry the bad pin.
    """
    enrolled = guard.PINNED_CITATIONS.total()
    docs = sorted(_tracked_docs(root))
    hits: list[Occurrence] = []
    for rel in docs:
        path = root / rel
        if not path.is_file():
            continue
        for lineno, text in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            for lit in LITERAL.finditer(text):
                # Is there a watch.py citation token immediately preceding this
                # pin?  Walk the guard's CITATION matches on the same line and
                # pick the one whose PIN ends at this literal's start.
                token: str | None = None
                covered = False
                for cm in guard.CITATION.finditer(text):
                    pm = guard.PIN.match(text[cm.end():])
                    if (
                        pm is not None
                        and pm.group("rev") == BAD_REVISION
                        and cm.end() + pm.end() == lit.end()
                    ):
                        token = cm.group()
                        covered = (rel, token) in guard.PINNED_CITATIONS
                        break
                hits.append(Occurrence(rel, lineno, text.strip(), token, covered))
    return enrolled, len(hits), hits


BLIND_SPOTS = (
    "STATED BLIND SPOTS (a scanner with silent scope is the defect this task closes):",
    "  1. dc739001 ONLY. A citation pinned to a DIFFERENT stale revision is "
    "invisible, and unenrolled=0 would read as complete. The campaign is about "
    "dc739001 because that is where it started, not because that is the only "
    "wrong pin.",
    "  2. PROSE MENTIONS count toward detected. A sentence naming '@ dc739001' "
    "as a concept (not a citation) has no enrollable identity and is always "
    "unenrolled. The per-line output marks token=None rows so a reader does not "
    "mistake them for pins to judge.",
    "  3. RUN FROM THE MAIN CHECKOUT. Gitignored-but-present files do not travel "
    "into a lane worktree, so a worktree run under-counts detected.",
    f"  4. {CAMPAIGN_DOC} and .dreamwork/dreams/* are EXCLUDED from detected — "
    "they are meta-discussion (the census instrument's own substrate, and "
    "process narrative that quotes citation forms as examples), not "
    "citation-bearing prose.",
)


def report(root: Path) -> int:
    enrolled, detected, hits = scan(root)
    covered = sum(1 for h in hits if h.covered)
    unenrolled = detected - covered
    prose_only = sum(1 for h in hits if h.token is None)

    print(f"root: {root}")
    print(f"bad revision under census: {BAD_REVISION}")
    print(f"excluded (instrument substrate): {CAMPAIGN_DOC}, .dreamwork/dreams/*")
    for line in BLIND_SPOTS:
        print(line)

    if enrolled == 0:
        print(
            "ERROR vacuity: enrolled is 0 — the guard's PINNED_CITATIONS ledger "
            "is empty, which is a broken guard, not a clean corpus (#868)"
        )
        return 2
    if detected == 0:
        print(
            "ERROR vacuity: detected is 0 — the scan found no occurrences of the "
            "bad revision. This is almost certainly a broken glob, wrong cwd, or "
            "wrong pattern; it must NEVER read as 'nothing left to enrol' (#868, "
            "#915)"
        )
        return 2

    print(
        f"RESULT: enrolled={enrolled}  detected={detected}  covered={covered}"
        f"  unenrolled={unenrolled}  (prose-only={prose_only})"
    )
    print(
        "WHERE EACH NUMBER COMES FROM: enrolled=guard PINNED_CITATIONS.total() "
        "(the enrolment ledger); detected=independent regex scan for the bad "
        "revision; covered=detected occurrences whose (doc,token) identity is "
        "enrolled AND pinned to the bad revision; unenrolled=detected-covered."
    )
    if unenrolled > 0:
        print(
            f"FINDING: {unenrolled} detected occurrence(s) the enrolment ledger "
            "does NOT account for. This is a COVERAGE finding, not a verdict: "
            "each needs the same per-citation judgement the enrolled rows got "
            "(#925: detection answers coverage; enrolment answers verdict)."
        )
    else:
        print(
            "NOTE: unenrolled=0. Re-read blind spot #1 before treating this as "
            "complete: only dc739001 is scanned, so a pin to a different stale "
            "revision is invisible."
        )

    by_doc: Counter[str] = Counter(h.doc for h in hits if not h.covered)
    print(
        f"--- unenrolled by document (count) — {sum(by_doc.values())} occurrence(s) ---"
    )
    for doc, count in by_doc.most_common():
        print(f"  {count:>3}x  {doc}")
    print("--- unenrolled occurrences (doc:line -> token or PROSE) ---")
    for h in sorted(hits, key=lambda x: (x.doc, x.line_no)):
        if h.covered:
            continue
        kind = h.token if h.token is not None else "PROSE (no citation token)"
        print(f"  {h.doc}:{h.line_no}  {kind}")
        print(f"        | {h.text[:160]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        print(f"ERROR root is not a directory: {root}", file=sys.stderr)
        return 2
    return report(root)


if __name__ == "__main__":
    raise SystemExit(main())
