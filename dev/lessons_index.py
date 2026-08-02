#!/usr/bin/env python3
"""Act-gated retrieval over `.dreamwork/lessons.md` (#349).

lessons.md is hundreds of entries across thousands of lines, and a lesson in
it failed to prevent its own repeat (the `git checkout` RED-undo lesson,
written 2026-07-25, repeated 2026-07-28) because nothing re-reads thousands
of lines before acting and the file's only retrieval path was scrolling. The
failure was the READING, not the writing.

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
     r"|deliberate.{0,20}bug|reinstat|false[ -]red"
     # Hollow-check vocabulary: a check that passes over the defect it was
     # written for IS a red-proof lesson, even when it never names the act
     # (#761). The #505 lesson ("the header's claim-list is not the
     # assertion-list") governs every red-proof and matched none of the
     # terms above, because it talks about a hollow check wearing a thorough
     # header rather than about an injection.
     r"|\bhollow\b|claim.list|assertion.list"),
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
    ("gate", "before you run a merge gate (also covers diagnosing / repairing one)",
     # The merge-gate sense of 'gate' is the core anchor. The word has a control-
     # sense homonym ("facts that gate behavior", "gate the verdict on the
     # findings") that leaks two non-gate lessons — visible, named, acceptable,
     # because the alternative (a proximity window around merge/run/land) SILENTLY
     # drops core gate lessons whose 'gate' sits far from those words ("the shape
     # to check for at gates", "At the gate, run the whole file") — the Direction-2
     # hazard this act exists to surface, not hide (#956).
     # The two recorded #956 hazards never name 'gate': a `pkill -f` whose pattern
     # matches other agents' argv, and a killed gate leaving the checkout DETACHED
     # at an unverified merge (recovery: `git checkout master`, discard the merge).
     # They are caught by their own distinctive vocabulary, not by broad pipe or
     # process terms (which flood the slice — #612: an index that prints
     # everything prints nothing).
     r"\bgate\b|pkill -f|detached.{0,15}(head|at a merge)|\bmerge_head\b"
     r"|\bland[_ ]lane\b|\bgating\b"),
    ("ui-craft", "before touching the dashboard / hub / any CSS or DOM",
     r"\bcss\b|\bdom\b|viewport|selector|position:|luminance|\bpx\b|\bhover"
     r"|\brender|\bnode\b|\belement\b|\binnerhtml\b"),
    ("agent-comms", "before relaying to / retiring / trusting an agent or inbox",
     r"\binbox|\brelay|subagent|dreamer|coordinator|\bagent"),
    ("clock", "before writing a timestamp / reasoning about elapsed time",
     r"timestamp|\bclock\b|elapsed|\bmtime|\bnow\(\)|wall-clock"),
]

ENTRY_START = re.compile(r"^- ")
SECTION_START = re.compile(r"^## ")  # newer lessons use `## ` heads, not `- ` bullets
BOLD_CLAIM = re.compile(r"^- \*\*(.+?)\*\*", re.S)
FIRST_SENTENCE = re.compile(r"^- (.+?\.)(?:\s|$)", re.S)
# A `## ` head is `## <claim> (<meta with a year>)`. The meta paren is always
# last and carries the date + issue tags; the claim is what precedes it.
SECTION_CLAIM = re.compile(r"(.+?)\s*\([^)]*20\d\d[^)]*\)\s*$", re.S)


def parse_entries(text: str) -> list[tuple[int, str]]:
    """Split lessons.md into (start_line, entry_text) at each lesson head.

    Two head shapes coexist in the file: the older ``- **<claim>**`` bullet
    (continuation lines indented) and the newer ``## <claim> (<meta>)``
    section head (body is flush-left prose). Both are lessons; treating only
    the bullet as an entry silently dropped every section-headed lesson —
    including the false-refusal and true-statement clusters — so both head
    shapes start an entry here.

    A bullet entry ends at the first flush-left line (document narration in
    the bullet region is not part of the lesson). A section entry runs until
    the next head of either shape: its body is flush-left prose, so a
    flush-left line cannot end it. The header block before the first head is
    not an entry.
    """
    entries: list[tuple[int, list[str]]] = []
    cur: list[str] | None = None
    start = 0
    section = False  # continuation rule depends on the head shape
    for i, line in enumerate(text.split("\n"), 1):
        if ENTRY_START.match(line) or SECTION_START.match(line):
            if cur is not None:
                entries.append((start, cur))
            cur, start = [line], i
            section = bool(SECTION_START.match(line))
        elif cur is not None:
            if section:
                # Flush-left prose is the body, not the end of the lesson.
                cur.append(line)
            elif line.startswith(" ") or not line.strip():
                cur.append(line)
            else:
                entries.append((start, cur))
                cur = None
                section = False
    if cur is not None:
        entries.append((start, cur))
    return [(ln, "\n".join(body).strip()) for ln, body in entries]


def claim_of(entry: str) -> str:
    """The first sentence — the bolded claim when present, else text to the
    first full stop. Shared shape with lint's near-duplicate check. A `## `
    head carries its claim in its first line before a trailing
    `(date, #tags, …)` meta paren, which is dropped so the claim matches its
    bullet-headed siblings' shape; the body below it is flush-left prose."""
    first_line = entry.split("\n", 1)[0]
    if first_line.startswith("## "):
        head = first_line[3:].strip()
        m = SECTION_CLAIM.match(head)
        return m.group(1).strip() if m else head[:160]
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
        # Build the verbatim body once so the header can state its line count
        # and a trailing sentinel can confirm it. The slice can run to
        # hundreds of lines and a reader (an agent harness) that receives a
        # truncated prefix has no way to tell it is incomplete: the header
        # states the magnitude up front, and the sentinel at the end is the
        # presence-check a truncated read loses — so a caller that does not
        # see the sentinel knows it received a prefix (#1033). The count is
        # metadata around the entries; output stays verbatim, never a summary
        # of the evidence (the evidence half is why the format exists).
        body_lines: list[str] = []
        for ln, body in hits:
            body_lines.append("")
            body_lines.append(f"lessons.md:{ln}")
            body_lines.extend(body.split("\n"))
        n_lines = len(body_lines)
        print(f"# act: {args.act} — {len(hits)} of {len(entries)} lessons, "
              f"{n_lines} lines (consult {when})")
        print("\n".join(body_lines))
        print(f"# end {args.act} — {len(hits)} lessons, {n_lines} lines")
        return 0

    # Default: the index summary plus the tool's own coverage report.
    print(f"lessons index — {path} ({len(entries)} entries)")
    for slug, when, _ in ACTS:
        print(f"  {slug:<18} {len(index[slug]):>3}  ({when})")
    classified = {ln for hits in index.values() for ln, _ in hits}
    missing = [(ln, body) for ln, body in entries if ln not in classified]
    print(f"\ncoverage: {len(entries) - len(missing)}/{len(entries)} entries "
          f"classified; {len(missing)} unclassifiable (matched no act anchor)")
    print("note: coverage depends on the act anchors above, which are "
          "hand-maintained and unaudited — a lesson nobody's vocabulary "
          "reaches is invisible here, the same failure this tool exists to "
          "prevent one level up. Read the anchors against the act you are "
          "about to perform, not just the count.")
    if missing:
        print("unclassifiable — visible, not silent (the tool's own #349 rule):")
        for ln, body in missing:
            print(f"  lessons.md:{ln} — {claim_of(body)[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
