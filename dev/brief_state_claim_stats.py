#!/usr/bin/env python3
"""Measure the task-state claim rule against the retained brief corpus (#1028).

``brief_corpus_stats.py`` (#881) enumerates briefs and fields but CANNOT
compute state-claim candidates or false positives — it has no notion of the
``_TASK_STATE_PREDICATE`` / ``_TASK_WARN_OUTPUT`` rules.  This tool fills that
gap so the 5-candidate / 0-FP figure recorded for the narrowed rule is
recomputable by anyone, rather than believed from a lane-private scratch file
that did not survive (#1028 Finding 2).

It applies the CURRENT rules in ``dev/brief.py`` to every retained core (the
authored head before the boilerplate cut) and reports, per core, every
state-claim candidate with its (line, task, context, claimed-word).  A
candidate is a false positive when the surrounding prose is ordinary context
rather than a genuine state assertion; classifying that requires reading the
line, so this tool reports the RAW candidates and leaves FP judgement to the
reader — exactly as the standing contract demands (#136: report the
population, do not certify it).

Reads the corpus only, writes nothing, takes no lock.

    python3 dev/brief_state_claim_stats.py [--briefs DIR]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BRIEFS = ROOT / ".dreamwork" / "docs" / "briefs"
BOILERPLATE = ROOT / "briefs" / "boilerplate.md"


def scan_core(core: str, predicate, warn_output) -> list[tuple[int, int, str, str | None]]:
    """Return state-claim candidates in one core as (line, task, context, word).

    Mirrors the claim-collection loop in ``brief._task_state_claim_report`` so
    the population it measures is the same one the report sees at generation.
    """
    claims: dict[tuple[int, int], tuple[int, int, str, str | None]] = {}
    in_fence = False
    for index, line in enumerate(core.splitlines()):
        if in_fence:
            if re.match(r"^ {0,3}`{3,}[ \t]*$", line):
                in_fence = False
            continue
        if re.match(r"^ {0,3}(`{3,}|~{3,})", line):
            in_fence = True
            continue
        for match in predicate.finditer(line):
            key = (index + 1, int(match.group("task")))
            claims.setdefault(
                key,
                (index + 1, int(match.group("task")),
                 "state predicate", match.group("state")),
            )
        for match in warn_output.finditer(line):
            for cite in re.finditer(r"#(\d+)", match.group("clause")):
                task = int(cite.group(1))
                key = (index + 1, task)
                claims.setdefault(key, (index + 1, task, "WARN output", None))
    return list(claims.values())


def measure(briefs_dir: Path) -> dict:
    sys.path.insert(0, str(ROOT / "dev"))
    import brief  # noqa: PLC0415

    boilerplate_head = BOILERPLATE.read_text(encoding="utf-8").splitlines()[0]
    examined = 0
    skipped: list[str] = []
    by_core: list[tuple[str, list]] = []

    for path in sorted(briefs_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        cut = text.find(boilerplate_head)
        if cut < 0:
            skipped.append(path.name)
            continue
        examined += 1
        candidates = scan_core(
            text[:cut], brief._TASK_STATE_PREDICATE, brief._TASK_WARN_OUTPUT
        )
        if candidates:
            by_core.append((path.name, candidates))

    total = sum(len(cs) for _, cs in by_core)
    return {
        "examined": examined,
        "skipped": skipped,
        "total_candidates": total,
        "cores_with_candidates": len(by_core),
        "by_core": by_core,
    }


def report(result: dict, out=sys.stdout) -> None:
    out.write(
        f"cores examined: {result['examined']}  "
        f"(skipped, no boilerplate: {len(result['skipped'])})\n"
    )
    out.write(f"state-claim candidates: {result['total_candidates']}  ")
    out.write(f"across {result['cores_with_candidates']} core(s)\n\n")
    out.write("raw candidates (line, task, context, claimed-word):\n")
    for name, candidates in result["by_core"]:
        out.write(f"  {name}:\n")
        for line_no, task, context, word in candidates:
            out.write(
                f"    line {line_no} #{task} [{context}]"
                + (f" '{word}'" if word else "")
                + "\n"
            )
    out.write(
        "\nFP classification is a reading judgement, not a count: open each\n"
        "core and decide whether the candidate is a genuine state assertion or\n"
        "ordinary context.  The recorded figure for the narrowed rule is 5\n"
        "candidates / 0 FP (all genuine state predicates: #818, #816, #821\n"
        "'is live').  Re-derive it from the candidates above.\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--briefs", type=Path, default=DEFAULT_BRIEFS)
    args = parser.parse_args(argv)
    if not args.briefs.is_dir():
        print(f"DID NOT MEASURE: no brief corpus at {args.briefs}", file=sys.stderr)
        return 2
    report(measure(args.briefs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
