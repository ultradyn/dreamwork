#!/usr/bin/env python3
"""Occurrence counter — the short, CORRECT form to reach for instead of ``grep -c``.

``grep -c NEEDLE FILE`` counts matching LINES, not occurrences.  In this corpus
citation-dense prose routinely puts two pins on one line, so the line count and
the occurrence count agree right up until the moment they don't — and by then
the number is load-bearing (#946).  ``grep -o NEEDLE | wc -l`` is correct but
longer and rarely reached for, because the wrong form is shorter and *usually*
right.  This module exists so the correct form is the shortest one to reach for:

    python3 dev/occur.py dc739001 .dreamwork/docs/briefs/551-posture-remind.md
    => occurrences=4  lines_matched=3  lines_examined=134  files_examined=1

It prints BOTH ``occurrences`` and ``lines_matched`` so the line-vs-occurrence
gap is visible by construction — an agent reaching for it expecting ``grep -c``
sees both numbers and the discrepancy, instead of a single number that hides
which question it answered.

NON-OVERLAPPING, stated (the direction-2 question this module closes by naming):
counts are non-overlapping — ``"aaaa".count("aa") == 2``, not 3.  This matches
``grep -o | wc -l``, ``re.findall`` and ``str.count``, which are the canonical
"correct" forms an agent would otherwise reach for, and it matches how
``dev/citation_enrolment_gap.py`` already counts (``LITERAL.finditer`` per line,
landed ``1224d73b``): this module is the SAME counting semantics factored out as
the short form to reach for, not a second one beside it.  A caller who needs
OVERLAPPING counts (a pattern that can overlap itself) wants a different tool;
state that rather than silently picking one engine's answer.

DEGRADE-TO-ZERO (#868): the CLI prints ``files_examined`` and
``lines_examined`` and exits 2 when it examined nothing, so a scan that matched
zero files (a broken glob, wrong cwd, misspelt path) cannot read as "nothing
matched" — the denominator is the one number that tells you, and it was the
denominator that eventually exposed #943.

WHAT THIS IS NOT: an occurrence count is not a CITATION count.  A sentence that
names ``dc739001`` as a concept (not a citation) counts toward occurrences but
has no enrollable identity — distinguishing those is ``citation_enrolment_gap``'s
job (#925: detection answers coverage, enrolment answers verdict).  This tool
answers "how many times does the needle appear", nothing more.

Exit codes: ``0`` for a completed count; ``2`` for vacuity (examined nothing) or
a usage error.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Tally:
    """Result of counting occurrences across one or more texts.

    ``occurrences`` is the non-overlapping match count (what ``grep -c`` SHOULD
    have answered).  ``lines_matched`` is the matching-LINE count (what
    ``grep -c`` actually answers).  The two differ exactly when one line holds
    two or more matches — the #946 defect.
    """

    occurrences: int
    lines_matched: int
    lines_examined: int
    files_examined: int


def count(text: str, needle, *, regex: bool = False) -> int:
    """Non-overlapping occurrence count of ``needle`` in ``text``.

    ``needle`` is a literal substring by default (``str.count`` — matches
    ``grep -F -o NEEDLE | wc -l``).  Pass ``regex=True`` for a regex string, or
    a compiled ``re.Pattern`` (the ``regex`` flag is then ignored).
    """
    if isinstance(needle, re.Pattern):
        return sum(1 for _ in needle.finditer(text))
    if regex:
        return len(re.findall(needle, text))
    return text.count(needle)


def count_file(path: Path, needle, *, regex: bool = False) -> tuple[int, int]:
    """Return ``(occurrences, lines_matched)`` for one file.

    Reads as UTF-8 with replacement so a lone bad byte never turns an
    occurrence count into a crash — a crash reads like silence (#622).
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    occurrences = 0
    lines_matched = 0
    for line in lines:
        n = count(line, needle, regex=regex)
        if n:
            occurrences += n
            lines_matched += 1
    return occurrences, lines_matched


def scan(paths, needle, *, regex: bool = False) -> Tally:
    """Count ``needle`` across ``paths``; return a :class:`Tally`.

    ``paths`` may be files or directories (directories are walked for files).
    The denominator fields (``files_examined``, ``lines_examined``) are the
    #868 guard: a scan that examined nothing reports them as 0, and the CLI
    turns that into a loud exit 2 rather than a clean-looking zero count.
    """
    occurrences = 0
    lines_matched = 0
    lines_examined = 0
    files_examined = 0
    seen: set[Path] = set()
    for p in paths:
        for f in _walk(p):
            if f in seen:
                continue
            seen.add(f)
            text_lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            lines_examined += len(text_lines)
            files_examined += 1
            for line in text_lines:
                n = count(line, needle, regex=regex)
                if n:
                    occurrences += n
                    lines_matched += 1
    return Tally(occurrences, lines_matched, lines_examined, files_examined)


def _walk(p: Path):
    """Yield regular files reachable from ``p`` (a file yields itself)."""
    if p.is_file():
        yield p.resolve()
        return
    if p.is_dir():
        for f in sorted(p.rglob("*")):
            if f.is_file():
                yield f.resolve()
        return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("needle", help="substring to count (or regex with --regex)")
    parser.add_argument(
        "paths", nargs="+", type=Path, help="files or directories to scan"
    )
    parser.add_argument(
        "--regex",
        action="store_true",
        help="treat NEEDLE as a regular expression (default: literal substring)",
    )
    args = parser.parse_args(argv)

    tally = scan(args.paths, args.needle, regex=args.regex)

    if tally.files_examined == 0:
        print(
            "ERROR vacuity: files_examined=0 — the scan matched no files. This "
            "is almost certainly a broken glob, wrong cwd, or misspelt path; it "
            "must NEVER read as 'nothing matched' (#868, #943).",
            file=sys.stderr,
        )
        return 2

    print(
        f"occurrences={tally.occurrences}  lines_matched={tally.lines_matched}"
        f"  lines_examined={tally.lines_examined}  files_examined={tally.files_examined}"
    )
    if tally.occurrences != tally.lines_matched:
        print(
            f"NOTE: occurrences ({tally.occurrences}) != lines_matched "
            f"({tally.lines_matched}) — one or more lines hold 2+ matches. "
            f"`grep -c` would report {tally.lines_matched} here (#946)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
