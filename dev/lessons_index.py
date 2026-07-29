#!/usr/bin/env python3
"""Act-gated retrieval over `.dreamwork/lessons.md` (#349).

lessons.md is 299 entries / ~3200 lines, and a lesson in it failed to
prevent its own repeat (the `git checkout` RED-undo lesson, written
2026-07-25, repeated 2026-07-28) because nothing re-reads 3000 lines before
acting and the file's only retrieval path was scrolling. The failure was
the READING, not the writing.

This tool is the read path. It derives an act -> lessons index FROM THE
ENTRIES' OWN TEXT at read time — nothing is stored, nothing is
hand-maintained, so there is no second file to go stale. Each act is a set
of anchor patterns over the vocabulary the lessons themselves use ("before
an injection", "red-proof", "worktree", ...). Consult it at the moment of
the act:

    python3 dev/lessons_index.py --act red-proof          # before an injection
    python3 dev/lessons_index.py --act parsed-file        # before writing a parsed file
    python3 dev/lessons_index.py --act worktree-dispatch  # before dispatching a lane

Output is the matching entries VERBATIM with `lessons.md:N` cites — never a
summary, because the evidence half is why the format exists
(file-formats.md). With no `--act` it prints the index summary and its own
COVERAGE: how many entries it classified and which it could not (named by
line). A retrieval tool that silently misses is the file's own failure one
level up, so the unclassifiable list is part of the contract, not an error
— the acts cover the loop's acts, and an entry about none of them is a
fact worth seeing, not a defect to hide.
"""

import argparse
import re
import sys
from pathlib import Path

# Each act: (slug, when to consult it, anchor regex over an entry's full text).
# Anchors are case-insensitive. An entry may govern several acts — membership
# is a set, not a filing.
ACTS: list[tuple[str, str, str]] = [
    ("red-proof", "before an injection / red-proof / reverting one",
     r"\binject|red[- ]proof|\bred\b.{0,20}\bgreen\b|goes red|go red\b"
     r"|deliberate.{0,20}bug|reinstat|false[ -]red"),
    ("worktree-dispatch", "before dispatching a lane / writing a brief / touching a worktree",
     r"worktree|dispatch|\blane\b|\blanes\b|\bbrief\b"),
    ("commit", "before committing / any git write",
     r"\bcommit|\bgit checkout|\bgit add|--only\b|index\.lock|uncommitted"
     r"|\bstash\b|\bcherry-pick\b"),
    ("parsed-file", "before writing a file a tool parses (ledger, questions, status.json, ...)",
     r"file-formats|parse[sd]?\b|parsing|ledger|tasks\.md|questions\.md"
     r"|status\.json|handoffs|answers\.md|\blint\b"),
    ("guard-check", "before writing or touching a guard / lint check",
     r"\bguard|\bassert|\bcheck\b|\bchecks\b"),
    ("verify-measure", "before trusting a verification / taking a measurement",
     r"\bverif|\bmeasur|screenshot|\bpixel|\bflaky|\bprobe\b"),
    ("transition-motion", "before changing anything that moves (transitions.md governs the how)",
     r"transition|animat|\bFLIP\b|dissolve|\bframe|\bmotion|\bsnap\b|\bglide"),
    ("fold-handoff", "before folding / writing a handoff / declaring a landing",
     r"\bfold|handoff|\blanded\b|\blanding\b|\bmerge"),
    ("ui-craft", "before touching the dashboard / hub / any CSS or DOM",
     r"\bcss\b|\bdom\b|viewport|selector|position:|luminance|\bpx\b|\bhover"
     r"|\brender|\bnode\b|\belement\b|\binnerhtml\b"),
    ("agent-comms", "before relaying to / retiring / trusting an agent or inbox",
     r"\binbox|\brelay|subagent|dreamer|coordinator|\bagent"),
    ("clock", "before writing a timestamp / reasoning about elapsed time",
     r"timestamp|\bclock\b|elapsed|\bmtime|\bnow\(\)|wall-clock"),
]

ENTRY_START = re.compile(r"^- ")
BOLD_CLAIM = re.compile(r"^- \*\*(.+?)\*\*", re.S)
FIRST_SENTENCE = re.compile(r"^- (.+?\.)(?:\s|$)", re.S)


def parse_entries(text: str) -> list[tuple[int, str]]:
    """Split lessons.md into (start_line, entry_text) at each `- ` bullet.

    An entry's continuation lines are indented (or blank); anything else
    ends it. The header block before the first bullet is not an entry.
    """
    entries: list[tuple[int, list[str]]] = []
    cur: list[str] | None = None
    start = 0
    for i, line in enumerate(text.split("\n"), 1):
        if ENTRY_START.match(line):
            if cur is not None:
                entries.append((start, cur))
            cur, start = [line], i
        elif cur is not None and (line.startswith(" ") or not line.strip()):
            cur.append(line)
        elif cur is not None:
            entries.append((start, cur))
            cur = None
    if cur is not None:
        entries.append((start, cur))
    return [(ln, "\n".join(body).strip()) for ln, body in entries]


def claim_of(entry: str) -> str:
    """The first sentence — the bolded claim when present, else text to the
    first full stop. Shared shape with lint's near-duplicate check."""
    flat = re.sub(r"\s+", " ", entry).strip()
    m = BOLD_CLAIM.match(flat)
    if m:
        return m.group(1)
    m = FIRST_SENTENCE.match(flat)
    return m.group(1) if m else flat[:160]


def classify(entries: list[tuple[int, str]]) -> dict[str, list[tuple[int, str]]]:
    index: dict[str, list[tuple[int, str]]] = {slug: [] for slug, _, _ in ACTS}
    for ln, body in entries:
        for slug, _, pat in ACTS:
            if re.search(pat, body, re.I):
                index[slug].append((ln, body))
    return index


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="lessons_index",
        description=__doc__.split("\n\n")[0] + " " + __doc__.split("\n\n")[1],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lessons", default=".dreamwork/lessons.md",
                    help="path to lessons.md (default: .dreamwork/lessons.md)")
    ap.add_argument("--act", help="print the entries governing this act, verbatim")
    ap.add_argument("--acts", action="store_true",
                    help="list the acts and when to consult each")
    args = ap.parse_args(argv)

    path = Path(args.lessons)
    if not path.is_file():
        print(f"lessons_index: {path} not found", file=sys.stderr)
        return 2
    entries = parse_entries(path.read_text(encoding="utf-8"))
    index = classify(entries)
    slugs = {slug for slug, _, _ in ACTS}

    if args.acts:
        for slug, when, _ in ACTS:
            print(f"  {slug:<18} {when}")
        return 0

    if args.act:
        if args.act not in slugs:
            print(f"lessons_index: unknown act {args.act!r} — acts:",
                  ", ".join(slug for slug, _, _ in ACTS), file=sys.stderr)
            return 2
        hits = index[args.act]
        when = next(w for s, w, _ in ACTS if s == args.act)
        print(f"# act: {args.act} — {len(hits)} of {len(entries)} lessons "
              f"(consult {when})")
        for ln, body in hits:
            print(f"\nlessons.md:{ln}")
            print(body)
        return 0

    # Default: the index summary plus the tool's own coverage report.
    print(f"lessons index — {path} ({len(entries)} entries)")
    for slug, when, _ in ACTS:
        print(f"  {slug:<18} {len(index[slug]):>3}  ({when})")
    classified = {ln for hits in index.values() for ln, _ in hits}
    missing = [(ln, body) for ln, body in entries if ln not in classified]
    print(f"\ncoverage: {len(entries) - len(missing)}/{len(entries)} entries "
          f"classified; {len(missing)} unclassifiable (matched no act anchor)")
    if missing:
        print("unclassifiable — visible, not silent (the tool's own #349 rule):")
        for ln, body in missing:
            print(f"  lessons.md:{ln} — {claim_of(body)[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
