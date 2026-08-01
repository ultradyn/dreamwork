#!/usr/bin/env python3
"""Measure which parts of the lane-brief corpus are mechanical (#881).

This is the instrument behind `.dreamwork/docs/measurements/881-brief-frame.md`.
It exists so the mechanical/authored boundary that `dev/brief.py` implements can
be re-derived rather than believed: rerun it and the numbers move as the corpus
moves.

It reads the corpus only, writes nothing, and takes no lock.

    python3 dev/brief_corpus_stats.py [--sample N] [--briefs DIR]
"""

from __future__ import annotations

import argparse
import collections
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BRIEFS = ROOT / ".dreamwork" / "docs" / "briefs"
BOILERPLATE = ROOT / "briefs" / "boilerplate.md"

# Sections a coordinator retypes at the end of nearly every brief.  Membership
# here is what "frame" means for the byte split; a section outside it counts as
# authored.
FRAME_SECTIONS = {
    "## Standing rules",
    "## Live-state prohibitions — absolute",
    "## What to report back",
    "## What you must not do",
    "## Rebase before you report",
    "## Verification before you report",
    "## Your completion report",
    "## Bars",
}
FRAME_FIELD = re.compile(
    r"^(Worktree:|Branch:|Base sha:|Repo root:|Lane-owns:|Coordinator inbox|# Task #|\s+\(`?inbox)"
)
FIELDS = [
    ("# Task #<id> heading", r"^# .*#\d+"),
    ("Worktree:", r"^Worktree:\s+\S"),
    ("Branch:", r"^Branch:\s+\S"),
    ("Base sha:", r"^Base sha: [0-9a-f]{7,40}$"),
    ("Repo root:", r"^Repo root: \S"),
    ("Coordinator inbox line", r"^Coordinator inbox — ABSOLUTE path"),
    ("inbox-NOT-handoffs parenthetical", r"inbox\.md`?,? NOT"),
    ("ledger.py get <id> --ledger", r"ledger\.py get \d+ --ledger \S"),
    ("Lane-owns:", r"^Lane-owns:\s*\S"),
]


def corpus(briefs_dir: Path, sample: int) -> list[tuple[int, str, Path]]:
    found = []
    for path in briefs_dir.glob("*.md"):
        match = re.match(r"(\d+)-(.+)\.md$", path.name)
        if match:
            found.append((int(match.group(1)), match.group(2), path))
    found.sort()
    return found[-sample:] if sample > 0 else found


def measure(briefs_dir: Path, sample: int) -> dict:
    boilerplate_head = BOILERPLATE.read_text(encoding="utf-8").splitlines()[0]
    fields: collections.Counter = collections.Counter()
    sections: dict[str, list[str]] = collections.defaultdict(list)
    head_bytes = boiler_bytes = frame_bytes = authored_bytes = 0
    authored_blocks: list[str] = []
    examined = 0
    skipped: list[str] = []

    for _task, _lane, path in corpus(briefs_dir, sample):
        text = path.read_text(encoding="utf-8", errors="replace")
        cut = text.find(boilerplate_head)
        if cut < 0:
            skipped.append(path.name)
            continue
        examined += 1
        head, lines = text[:cut], text[:cut].splitlines()
        head_bytes += len(head.encode("utf-8"))
        boiler_bytes += len(text[cut:].encode("utf-8"))

        for name, pattern in FIELDS:
            if any(re.search(pattern, line) for line in lines):
                fields[name] += 1

        current: str | None = None
        body: list[str] = []
        authored: list[str] = []
        for line in lines:
            if line.startswith("## "):
                if current is not None:
                    sections[current].append("\n".join(body).strip())
                current, body = line.strip(), []
            elif current is not None:
                body.append(line)
            width = len(line.encode("utf-8")) + 1
            if current in FRAME_SECTIONS or FRAME_FIELD.match(line):
                frame_bytes += width
            else:
                authored_bytes += width
                if line.strip():
                    authored.append(line.strip())
        if current is not None:
            sections[current].append("\n".join(body).strip())
        authored_blocks.append("\n".join(authored))

    return {
        "examined": examined,
        "skipped": skipped,
        "head_bytes": head_bytes,
        "boiler_bytes": boiler_bytes,
        "frame_bytes": frame_bytes,
        "authored_bytes": authored_bytes,
        "fields": fields,
        "sections": sections,
        "distinct_authored": len(set(authored_blocks)),
    }


def report(result: dict, out=sys.stdout) -> None:
    examined = result["examined"]
    if not examined:
        out.write("DID NOT MEASURE: no brief carried the boilerplate\n")
        return
    total = result["head_bytes"] + result["boiler_bytes"]
    head = result["frame_bytes"] + result["authored_bytes"]
    out.write(f"briefs examined: {examined}  (skipped, no boilerplate: {len(result['skipped'])})\n")
    out.write(f"boilerplate bytes : {result['boiler_bytes']:>9,}  {result['boiler_bytes']/total*100:5.1f}% of corpus\n")
    out.write(f"head bytes        : {result['head_bytes']:>9,}  {result['head_bytes']/total*100:5.1f}% of corpus\n")
    out.write(f"  frame in head   : {result['frame_bytes']:>9,}  {result['frame_bytes']/head*100:5.1f}% of head"
              f"  ({result['frame_bytes']/total*100:.1f}% of corpus)\n")
    out.write(f"  authored in head: {result['authored_bytes']:>9,}  {result['authored_bytes']/head*100:5.1f}% of head"
              f"  ({result['authored_bytes']/total*100:.1f}% of corpus)\n")
    out.write(f"distinct authored blocks: {result['distinct_authored']}/{examined}\n\n")

    out.write("field presence\n")
    for name, _pattern in FIELDS:
        out.write(f"  {result['fields'][name]:>3}/{examined}  {name}\n")

    out.write("\nrecurring section drift (occurrences vs distinct bodies)\n")
    for name in ("## Standing rules", "## Live-state prohibitions — absolute",
                 "## What to report back"):
        bodies = result["sections"].get(name, [])
        if not bodies:
            continue
        out.write(f"  {name}: {len(bodies)} occurrences, {len(set(bodies))} distinct\n")
        bullets: collections.Counter = collections.Counter()
        for body in bodies:
            for line in {l.strip() for l in body.splitlines() if l.strip().startswith("- ")}:
                bullets[line] += 1
        for line, count in bullets.most_common(6):
            out.write(f"      {count:>3}/{len(bodies)}  {line[:96]}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sample", type=int, default=40,
                        help="measure the N most recent briefs by task id (0 = all)")
    parser.add_argument("--briefs", type=Path, default=DEFAULT_BRIEFS)
    args = parser.parse_args(argv)
    if not args.briefs.is_dir():
        print(f"DID NOT MEASURE: no brief corpus at {args.briefs}", file=sys.stderr)
        return 2
    report(measure(args.briefs, args.sample))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
