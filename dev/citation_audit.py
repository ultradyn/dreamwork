#!/usr/bin/env python3
"""dev/citation_audit.py — does a brief's "#NNN — <wording>" citation hold?

The defect (#786): the coordinator's briefs cite real task ids for principles
those ids do not contain.  "#755 — a check that fires on a healthy input" points
at a task whose real subject is queued_dispatches rot; the principle is sound,
the id is real, and there is no relationship between them.

This tool CANNOT validate paraphrases — that is a semantic judgment, and a
fuzzy text-match would fire on every legitimate compression (#707: every
widening multiplies false attribution).  It reports only what it can decide
mechanically, and says so for everything else:

  UNRESOLVABLE     the cited id is not in the ledger at all
  NO_RELATIONSHIP  zero shared content words between the wording beside the id
                   and the entry's text (the clear false-citation case)
  UNCLASSIFIABLE   some overlap exists; the tool cannot judge whether it is a
                   valid paraphrase or a miscitation — a human must read it

A check that examined nothing must not read as passing (#671): the summary
always names how many citations it examined, how many it could not resolve,
and how many it declined to classify.  The corpus line separately names Git
tracking, on-disk population, and how many briefs the audit read; it calls the
audit incomplete only when the latter two differ (#788).

Usage:
    python3 dev/citation_audit.py [--briefs DIR] [--dw-dir DIR] [--verbose]

    --briefs DIR    the brief corpus to audit (default: .dreamwork/docs/briefs)
    --dw-dir DIR    the .dreamwork dir containing the ledger store
                    (default: auto-detect the main checkout)
    --verbose       show UNCLASSIFIABLE detail in addition to the default summary

From a worktree, the default resolves the MAIN checkout because the ledger store
is gitignored and cannot travel.  Pass --dw-dir only to select a different store.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# -- parsing helpers ----------------------------------------------------------

# A citation in a brief looks like "#NNN — <wording>" or "#NNN: <wording>";
# the task id may carry the house Markdown bold wrapper.
# The em-dash (—) and colon are the two forms the coordinator actually writes.
# We capture the id and the wording that follows it on the same logical line.
CITATION_RE = re.compile(
    r"(?:\*\*)?#(\d+)(?:\*\*)?\s*[—:]\s*(.+?)(?:\.\s|\.$|$)",
    re.MULTILINE,
)

# Explicitly narrow citation-like forms which the extractor does not claim to
# understand.  Keep this separate from CITATION_RE: widening the audit grammar
# to every task reference would turn ordinary prose such as "#1152" into noise.
UNSUPPORTED_CITATION_RES = (
    ("parenthesized", re.compile(r"\(#\d+\)")),
    ("possessive", re.compile(r"#\d+(?:'s|’s)\b")),
    ("bracketed", re.compile(r"\[#\d+\]")),
    (
        "line-wrapped",
        re.compile(r"#\d+(?:\*\*)?[ \t]*(?:—|:)[ \t]*[^\n]{0,4}\n[ \t]*\S"),
    ),
    (
        "shared-gloss",
        re.compile(
            r"#\d+(?:\*\*)?[ \t]*/[ \t]*(?:\*\*)?#\d+"
            r"(?:\*\*)?[ \t]*(?:—|:)"
        ),
    ),
)

# Words too common to carry meaning.  Deliberately SHORT: the tool's
# NO_RELATIONSHIP verdict fires only on ZERO overlap, so a long stopword list
# would make it fire more (the opposite of #707's caution — but a short one
# keeps the verdict honest by not stripping words that genuinely distinguish).
STOPWORDS = frozenset(
    "a an the is are was be been being to of in on at for with by from "
    "as it its this that these those and or not no but if so do does did "
    "has have had will would can could should may might must shall one "
    "more less than into out up down over under again then once here "
    "there where when why how all any both each few other some such only "
    "own same too very just also".split()
)


def _content_words(text: str) -> set[str]:
    """Significant lowercase word-tokens from *text* (stopwords removed)."""
    tokens = re.findall(r"[a-zA-Z][a-zA-Z'-]+", text.lower())
    return {t for t in tokens if t not in STOPWORDS and len(t) > 2}


def _entries_by_id(dw_dir: Path) -> dict[int, str]:
    """Map each task id to its full entry text.

    Resolves through the SQLite store (the source of truth since #294), not
    the text shim that travels into worktrees.  A hand-rolled reader over
    tasks.md is the documented failure mode here (#352, #667): the file that
    travels is a migration notice, and every id reads as UNRESOLVABLE against
    it.  ``ledger_parse.store_records`` is the ONE reader the rest of the loop
    uses, so we import it rather than re-deriving.
    """
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    import ledger_parse

    store = ledger_parse.store_path(dw_dir)
    if not store.is_file():
        raise FileNotFoundError(store)

    result: dict[int, str] = {}
    for r in ledger_parse.store_records(str(dw_dir)):
        # Reconstruct the text shape `dev/ledger.py get` produces, so the
        # content-word overlap runs against the same text a human reads.
        lines = [f"#{r['id']}  {r['state']}", f"title: {r['title']}"]
        body = r.get("body") or ""
        result[r["id"]] = "\n".join(lines) + "\n" + body
    return result


@dataclass
class Citation:
    """One "#NNN — <wording>" citation found in a brief."""

    brief: str  # brief filename (stem only)
    task_id: int
    wording: str
    line: int

    # classification result (filled by classify)
    status: str = ""  # UNRESOLVABLE | NO_RELATIONSHIP | UNCLASSIFIABLE
    detail: str = ""


@dataclass(frozen=True)
class UnsupportedCitationForm:
    """One citation-like form deliberately outside ``CITATION_RE``."""

    brief: str
    line: int
    form: str
    specimen: str


@dataclass
class CorpusCoverage:
    """The Git-tracked vs on-disk split of a brief corpus (#671, #651)."""

    on_disk: int = 0
    tracked: int = 0

    @property
    def untracked(self) -> int:
        return self.on_disk - self.tracked


def corpus_coverage(briefs_dir: Path) -> CorpusCoverage:
    """Count ``.md`` briefs on disk vs tracked by git.

    Returns equal counts when the dir is not under git (the common test and
    fixture case).  Tracking is provenance, not audit reach; ``audit_briefs``
    records the latter independently as it reads each file.
    """
    on_disk = sum(1 for _ in briefs_dir.glob("*.md"))
    result = subprocess.run(
        ["git", "-C", str(briefs_dir), "ls-files", "--", "*.md"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return CorpusCoverage(on_disk=on_disk, tracked=on_disk)
    tracked = sum(1 for line in result.stdout.splitlines() if line.strip())
    return CorpusCoverage(on_disk=on_disk, tracked=tracked)


@dataclass
class AuditReport:
    """Aggregate result of auditing one or more briefs."""

    examined: int = 0
    briefs_examined: int = 0
    coverage: CorpusCoverage = field(default_factory=CorpusCoverage)
    unresolvable: list[Citation] = field(default_factory=list)
    no_relationship: list[Citation] = field(default_factory=list)
    unclassifiable: list[Citation] = field(default_factory=list)
    unsupported_forms: list[UnsupportedCitationForm] = field(default_factory=list)

    @property
    def classified(self) -> int:
        return len(self.unresolvable) + len(self.no_relationship)

    @property
    def total(self) -> int:
        return self.examined


def extract_citations(text: str, brief_name: str) -> list[Citation]:
    """Pull every ``#NNN — wording`` citation from *text*.

    Only citations where wording follows the id on the same line count — a
    bare "#755" with no descriptive text is a reference, not a citation that
    claims a principle.
    """
    found: list[Citation] = []
    for m in CITATION_RE.finditer(text):
        wording = m.group(2).strip().strip(".*")
        if len(wording) < 5:  # too short to carry a principle claim
            continue
        line = text.count("\n", 0, m.start()) + 1
        found.append(
            Citation(
                brief=brief_name,
                task_id=int(m.group(1)),
                wording=wording,
                line=line,
            )
        )
    return found


def find_unsupported_citation_forms(
    text: str, brief_name: str
) -> list[UnsupportedCitationForm]:
    """Name known citation-like shapes outside the audit's narrow grammar."""
    found: list[UnsupportedCitationForm] = []
    for form, pattern in UNSUPPORTED_CITATION_RES:
        for match in pattern.finditer(text):
            found.append(
                UnsupportedCitationForm(
                    brief=brief_name,
                    line=text.count("\n", 0, match.start()) + 1,
                    form=form,
                    specimen=match.group(0).replace("\n", "\\n"),
                )
            )
    return sorted(found, key=lambda item: (item.line, item.form))


def classify(cit: Citation, entries: dict[int, str]) -> None:
    """Set *cit*.status and *cit*.detail against the resolved entry text."""
    entry = entries.get(cit.task_id)
    if entry is None:
        cit.status = "UNRESOLVABLE"
        cit.detail = f"#{cit.task_id} not found in ledger"
        return

    principle_words = _content_words(cit.wording)
    entry_words = _content_words(entry)
    shared = principle_words & entry_words

    if not principle_words:
        # The wording had no content words at all — nothing to check.
        cit.status = "UNCLASSIFIABLE"
        cit.detail = "wording carries no checkable content words"
        return

    if not shared:
        cit.status = "NO_RELATIONSHIP"
        cit.detail = (
            f"zero shared content words between wording and #{cit.task_id}'s entry"
        )
        return

    cit.status = "UNCLASSIFIABLE"
    cit.detail = (
        f"{len(shared)} shared word(s): {sorted(shared)[:5]}"
        " — tool cannot judge paraphrase validity"
    )


def audit_briefs(
    briefs_dir: Path, entries: dict[int, str]
) -> AuditReport:
    """Audit every ``.md`` brief in *briefs_dir* against *entries*.

    *entries* is the id→text map from ``_entries_by_id``; passing it in
    keeps resolution (a store concern) separate from auditing (a brief
    concern) and makes the function testable without a live store.
    """
    report = AuditReport()
    report.coverage = corpus_coverage(briefs_dir)

    for brief in sorted(briefs_dir.glob("*.md")):
        text = brief.read_text()
        report.briefs_examined += 1
        report.unsupported_forms.extend(
            find_unsupported_citation_forms(text, brief.stem)
        )
        for cit in extract_citations(text, brief.stem):
            classify(cit, entries)
            report.examined += 1
            if cit.status == "UNRESOLVABLE":
                report.unresolvable.append(cit)
            elif cit.status == "NO_RELATIONSHIP":
                report.no_relationship.append(cit)
            else:
                report.unclassifiable.append(cit)

    return report


def _main_checkout_root() -> Path:
    """Resolve the primary checkout through git's shared administrative dir."""
    here = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        ["git", "-C", str(here), "rev-parse", "--path-format=absolute",
         "--git-common-dir"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode == 0:
        return Path(result.stdout.strip()).parent
    return here


def _default_dw_dir() -> Path:
    """Find the main checkout's ``.dreamwork/`` dir from a worktree."""
    return _main_checkout_root() / ".dreamwork"


def _default_briefs_dir() -> Path:
    """Use the main checkout's live corpus when invoked from a worktree."""
    return _default_dw_dir() / "docs" / "briefs"


def _store_fault_message(exc: Exception) -> str:
    """Preserve the store ladder's classification at this CLI boundary."""
    from dreamwork_db.core import Busy, ConstraintViolation, Corrupt, SchemaMismatch

    if isinstance(exc, FileNotFoundError):
        return f"store missing: {exc}"
    if isinstance(exc, Busy):
        return f"store busy: {exc}"
    if isinstance(exc, Corrupt):
        return f"store corrupt: {exc}"
    if isinstance(exc, SchemaMismatch):
        return f"store schema mismatch: {exc}"
    if isinstance(exc, ConstraintViolation):
        return f"store constraint violation: {exc}"
    return f"unclassified store error: {exc}"


def format_report(report: AuditReport, quiet: bool = False) -> str:
    """Human-readable summary.  Always names coverage (#671)."""
    cov = report.coverage
    incomplete = report.briefs_examined != cov.on_disk
    lines = [
        f"corpus: {cov.tracked} tracked / {cov.on_disk} on disk / "
        f"{report.briefs_examined} audited"
        + (f" ({cov.untracked} untracked)" if cov.untracked > 0 else "")
        + (
            " (AUDIT IS INCOMPLETE — "
            f"audited {report.briefs_examined} of {cov.on_disk} on-disk briefs)"
            if incomplete else ""
        ),
        f"citation_audit: examined {report.examined} citation(s)",
        f"  CITATION FORMS NOT COVERED: {len(report.unsupported_forms)}",
        f"  UNRESOLVABLE:     {len(report.unresolvable)}",
        f"  NO_RELATIONSHIP:  {len(report.no_relationship)}",
        f"  UNCLASSIFIABLE:   {len(report.unclassifiable)}",
    ]
    if quiet:
        return "\n".join(lines)

    for cit in report.unresolvable:
        lines.append(f"  [UNRESOLVABLE] {cit.brief}:{cit.line} #{cit.task_id} — {cit.detail}")
    for cit in report.no_relationship:
        lines.append(
            f"  [NO_RELATIONSHIP] {cit.brief}:{cit.line} "
            f"#{cit.task_id} — {cit.wording[:60]}"
        )
        lines.append(f"    {cit.detail}")
    if report.unsupported_forms:
        by_form: dict[str, list[UnsupportedCitationForm]] = {}
        for item in report.unsupported_forms:
            by_form.setdefault(item.form, []).append(item)
        lines.append("  known citation forms outside extraction grammar:")
        for form, items in by_form.items():
            examples = "; ".join(
                f"{item.brief}:{item.line} {item.specimen!r}" for item in items[:3]
            )
            suffix = f"; {len(items) - 3} more" if len(items) > 3 else ""
            lines.append(f"    {form}: {len(items)} ({examples}{suffix})")
    if report.unclassifiable:
        for cit in report.unclassifiable:
            lines.append(
                f"  [UNCLASSIFIABLE] {cit.brief}:{cit.line} "
                f"#{cit.task_id} — {cit.wording[:60]}"
            )
            lines.append(f"    {cit.detail}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--briefs", type=Path, default=None, help="brief corpus directory")
    parser.add_argument(
        "--dw-dir", type=Path, default=None,
        help=".dreamwork/ dir containing the ledger store",
    )
    parser.add_argument("--quiet", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--verbose", action="store_true", help="show UNCLASSIFIABLE details")
    args = parser.parse_args(argv)

    briefs_dir = args.briefs or _default_briefs_dir()
    dw_dir = args.dw_dir or _default_dw_dir()

    if not briefs_dir.is_dir():
        print(f"citation_audit: briefs directory not found: {briefs_dir}", file=sys.stderr)
        return 2
    if not dw_dir.is_dir():
        print(f"citation_audit: dreamwork dir not found: {dw_dir}", file=sys.stderr)
        return 2

    try:
        entries = _entries_by_id(dw_dir)
    except FileNotFoundError as exc:
        print(f"citation_audit: {_store_fault_message(exc)}", file=sys.stderr)
        return 2
    except Exception as exc:
        from dreamwork_db.core import DatabaseError

        if not isinstance(exc, DatabaseError):
            raise
        print(f"citation_audit: {_store_fault_message(exc)}", file=sys.stderr)
        return 2
    report = audit_briefs(briefs_dir, entries)
    print(format_report(report, quiet=not args.verbose))

    # Exit code: non-zero if any UNRESOLVABLE or NO_RELATIONSHIP found,
    # so the tool can gate.  UNCLASSIFIABLE alone is exit 0 — the tool said
    # it could not decide, and that is not a failure.
    if report.unresolvable or report.no_relationship:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
