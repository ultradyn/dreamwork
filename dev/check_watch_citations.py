#!/usr/bin/env python3
"""Check that #801's historical citations remain revision-pinned.

This guard binds only the ``(document, citation token)`` multiset and checks
that every occurrence is followed by a revision which resolves to a commit.
The coordinates are pinned, not verified against the pinned revision.  In
particular, the check never reads ``watch.py`` and cannot claim that a pinned
coordinate identifies the intended source at that revision.

A second check, :func:`check_docstring_citations`, scans ``dev/*.py``
docstrings for ``(#NNN)`` issue references, resolves each id against the
ledger, and prints the title beside the citation for human aptness review
(#1034).  It reports, never certifies attribution (#994); it gates only on
an id that does not resolve.

A MISSING or UNPINNED finding often results from a CORRECT pin repair — the
coordinate moved or was retired to prose.  That requires a matching enrolment
update in BOTH ``PINNED_CITATIONS`` (this file) and the
``REVIEWED_PIN_COUNTS`` contract in ``test_check_watch_citations.py``.  This
is a COORDINATOR act at fold, not something a lane resolves by editing the
guard or its test to force green.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys
import tokenize


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


# --- Docstring citation report (#1034) ---------------------------------------
#
# The pin check above binds watch.py:NNN coordinates to git revisions in
# .dreamwork/ documents.  It never reads dev/*.py and never sees the (#NNN)
# issue references in docstrings — the gap that let land_lane's
# _requirement_line miscite #868 for #136's three-zero-states rule (#1034).
#
# This section scans every dev/*.py docstring for (#NNN), resolves each id
# against the ledger, and prints the resolved TITLE beside the citation so a
# human or brief author can spot an attribution mismatch at a glance.  It
# REPORTS, never certifies aptness (#994): a resolvable id is a real entry,
# not an attested attribution.  The only mechanical defect it gates on is an
# UNRESOLVABLE id — a dangling reference.

DOCSTRING_CITATION = re.compile(r"\(#(\d+)\)")
_DOCSTRING_NODES = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


@dataclass
class DocstringCitation:
    """One (#NNN) found inside a dev/*.py docstring."""

    rel_path: str
    symbol: str
    lineno: int
    task_id: int
    raw_token: str = ""


@dataclass
class SkippedFile:
    """A dev/*.py file that could not be parsed (#868/#1034).

    A file that could not be read or parsed must not be silently absorbed
    into the examined count (#868): a probe that examined nothing must not
    read like one that examined everything.
    """

    rel_path: str
    reason: str


def _scan_docstring_citations(
    root: Path,
) -> tuple[list[DocstringCitation], list[SkippedFile], int]:
    """Return ``(findings, skipped, docstrings_scanned)`` for dev/*.py.

    Uses the AST so only docstrings are examined — not inline comments, not
    string literals in executable code.  Source is read via
    :func:`tokenize.open`, which honours the PEP-263 coding cookie so a
    valid Latin-1 (or other non-UTF-8) file with a ``# coding:`` declaration
    is decoded correctly and its docstring IS examined (#1034).  Files that
    cannot be decoded (no cookie, invalid bytes) or parsed (SyntaxError) are
    returned as SKIPPED with their reason, never silently dropped into the
    examined count (#868).  The denominators are derived once at runtime,
    never as a stale literal.
    """
    findings: list[DocstringCitation] = []
    skipped: list[SkippedFile] = []
    docstrings_scanned = 0
    for path in sorted((root / "dev").glob("*.py")):
        rel = path.relative_to(root).as_posix()
        try:
            with tokenize.open(path) as stream:
                source = stream.read()
        except UnicodeDecodeError as exc:
            skipped.append(SkippedFile(rel, f"undecodable bytes: {exc}"))
            continue
        except SyntaxError as exc:
            # tokenize.detect_encoding raises SyntaxError for a malformed
            # coding cookie or BOM — a file that cannot be read, not one
            # whose body has a syntax error.
            skipped.append(SkippedFile(rel, f"bad encoding cookie: {exc}"))
            continue
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            skipped.append(SkippedFile(rel, f"SyntaxError: {exc}"))
            continue
        for node in ast.walk(tree):
            if not isinstance(node, _DOCSTRING_NODES) or not node.body:
                continue
            doc_node = node.body[0]
            if not isinstance(doc_node, ast.Expr):
                continue
            val = doc_node.value
            if not isinstance(val, ast.Constant) or not isinstance(
                val.value, str
            ):
                continue
            docstrings_scanned += 1
            doc = val.value
            base_line = doc_node.lineno
            name = getattr(node, "name", "<module>")
            for match in DOCSTRING_CITATION.finditer(doc):
                lineno = base_line + doc[: match.start()].count("\n")
                raw = match.group(1)
                findings.append(
                    DocstringCitation(
                        rel, name, lineno, int(raw), raw
                    )
                )
    return findings, skipped, docstrings_scanned


def _docstring_checkout_root() -> Path:
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
    """Find the main checkout's .dreamwork/ from a worktree (#1034)."""
    return _docstring_checkout_root() / ".dreamwork"


def _resolve_titles(dw_dir: Path) -> dict[int, str]:
    """Map task id to title via the one reader the loop uses (#352, #667).

    A hand-rolled reader over tasks.md is the documented failure mode: the
    file that travels into worktrees is a migration notice.  ledger_parse is
    the single reader, so we import it rather than re-deriving.
    """
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    import ledger_parse

    store = ledger_parse.store_path(dw_dir)
    if not store.is_file():
        raise FileNotFoundError(store)
    return {
        r["id"]: r["title"] for r in ledger_parse.store_records(str(dw_dir))
    }


def _is_css_colour(raw_token: str) -> bool:
    """Whether a parenthesised number is unambiguously a CSS colour.

    Operates on the ORIGINAL TOKEN STRING, not the int's decimal
    re-rendering (#1034).  The regex ``\\(#(\\d+)\\)`` extracts decimal
    digit runs; a six-digit all-decimal run like ``000000`` becomes int 0
    and ``str(0)`` is ``"0"`` (length 1), so the old int-based check
    returned False and the token reached UNRESOLVABLE — a legitimate CSS
    black wedged the checker.  Checking the original ``"000000"`` (length
    6, all hex) returns True → FILTERED, as documented.

    ``(#ffffff)`` is never extracted (the regex matches ``\\d`` only, and
    ``f`` is not a digit), so hex-letter colours are naturally absent.
    Six-digit decimal tokens above the ledger max (e.g. ``(#999999)`` with
    max 1056) are also six hex digits and are treated as CSS — a known
    false-negative direction stated here, not hidden: a decimal run that
    could be a miscited high issue id is indistinguishable from a CSS
    colour by syntax alone.  The checker exists to catch miscitations
    *within the plausible issue-id range*; an id above the max is already
    SUSPICIOUS when it is 1–5 digits, and a 6-digit above-max token is
    the one shape the CSS rule cannot disambiguate.
    """
    return len(raw_token) == 6 and all(
        d in "0123456789abcdefABCDEF" for d in raw_token
    )


def check_docstring_citations(
    root: Path, dw_dir: Path | None = None, *, verbose: bool = False
) -> int:
    """Report each dev/*.py docstring (#NNN) with its resolved title.

    Three resolution states, never collapsed (#136): titles were resolved,
    titles could not be resolved, and there were no citations.  When the
    ledger store is absent the check reports NOT CHECKED — it extracted
    citations but could not resolve their titles — and returns 0 so the
    store's absence does not mask the pin check (which works in any
    checkout).  The NOT CHECKED banner is printed so a reader who skims sees
    the check did not actually check.

    A file that cannot be parsed (SyntaxError, invalid encoding without a
    coding cookie) is reported as SKIPPED with its reason, separately from
    examined — never silently absorbed into a green count (#868).

    Parenthesised numbers are classified by a stated rule (#1034): six hex
    digits in the ORIGINAL TOKEN is a CSS colour (FILTERED); an issue
    reference above the ledger max is SUSPICIOUS (reported, not hidden);
    an id that resolves is reported with its title; an id that does not
    resolve is UNRESOLVABLE (the only mechanical gate).  Resolved rows
    print by default — the checker's value is the title beside each
    citation, visible without flags (#1034 Finding 5).

    Exit 2 if no dev/*.py files were examined (vacuity: #868).  Exit 1 if
    any cited id does not resolve.  Exit 0 when every cited id resolves or
    the store is absent (NOT CHECKED).  Titles are REPORTED for human
    aptness review, never certified (#994).
    """
    dev_dir = root / "dev"
    py_files = sorted(dev_dir.glob("*.py")) if dev_dir.is_dir() else []
    if not py_files:
        print("ERROR vacuity: examined 0 file(s) in dev/*.py")
        return 2

    citations, skipped, docstrings_scanned = _scan_docstring_citations(root)
    files_examined = len(py_files) - len(skipped)
    if files_examined == 0:
        print(
            f"ERROR vacuity: examined 0 of {len(py_files)} file(s) in "
            f"dev/*.py ({len(skipped)} skipped)"
        )
        for s in skipped:
            print(f"  SKIPPED {s.rel_path}: {s.reason}")
        return 2

    if dw_dir is None:
        dw_dir = _default_dw_dir()
    try:
        titles = _resolve_titles(dw_dir)
    except FileNotFoundError as exc:
        # NOT CHECKED (#136 third state): the store is absent.  The
        # extraction ran and found citations, but title resolution could
        # not run.  This must not read like "resolved and all good" or
        # "no citations found."  Exit 0 so this does not mask the pin
        # check; the banner makes the state unmissable.
        print(
            f"NOT CHECKED: ledger store not found ({exc}); "
            f"{len(citations)} (#NNN) citation(s) extracted across "
            f"{files_examined} file(s) ({len(skipped)} skipped), "
            f"{docstrings_scanned} docstring(s) "
            f"scanned — title resolution could not run, attribution "
            f"review did not happen (#136).  Pin check above remains "
            f"authoritative."
        )
        for s in skipped:
            print(f"  SKIPPED {s.rel_path}: {s.reason}")
        # Extracted citations print by default (#1034 Finding 5): the
        # operator should see what was extracted even when resolution
        # could not run.
        for c in sorted(
            citations, key=lambda x: (x.rel_path, x.lineno)
        ):
            print(
                f"  {c.rel_path}:{c.lineno} {c.symbol} "
                f"(#{c.task_id}) [unverified]"
            )
        return 0

    # Classify by the stated rule (#1034).
    max_task_id = max(titles) if titles else 0
    resolved: list[DocstringCitation] = []
    unresolvable: list[DocstringCitation] = []
    suspicious: list[DocstringCitation] = []
    filtered: list[DocstringCitation] = []
    for c in citations:
        if _is_css_colour(c.raw_token):
            filtered.append(c)
        elif max_task_id and c.task_id > max_task_id:
            suspicious.append(c)
        elif c.task_id in titles:
            resolved.append(c)
        else:
            unresolvable.append(c)
    total_real = len(resolved) + len(unresolvable) + len(suspicious)

    # Signal-first output (#1034 Finding 5): the rows a reader must act on
    # print first; resolved rows print only with --verbose.
    print(
        f"DOCSTRING CITATIONS: examined {files_examined} file(s) "
        f"({len(skipped)} skipped), {docstrings_scanned} docstring(s) "
        f"scanned, {total_real} (#NNN) citation(s)"
        f"{f', {len(filtered)} CSS colour(s) filtered' if filtered else ''}"
        f" — REPORT not certification (#994)"
    )
    for c in unresolvable:
        print(
            f"  UNRESOLVABLE {c.rel_path}:{c.lineno} {c.symbol} "
            f"(#{c.task_id}) not found in ledger"
        )
    for c in suspicious:
        print(
            f"  SUSPICIOUS {c.rel_path}:{c.lineno} {c.symbol} "
            f"(#{c.task_id}) exceeds ledger max (#{max_task_id}) — "
            f"typo, stale ref, or not-yet-filed"
        )
    for s in skipped:
        print(f"  SKIPPED {s.rel_path}: {s.reason}")
    for c in filtered:
        print(
            f"  FILTERED {c.rel_path}:{c.lineno} {c.symbol} "
            f"(#{c.raw_token}) CSS colour (6 hex digits)"
        )
    # Resolved rows print by default (#1034 Finding 5): the checker's value
    # is showing the title beside each citation so a human can spot an
    # attribution mismatch.  Hiding resolved rows on a clean run made the
    # miscitation this task exists to surface invisible by default.
    for c in sorted(resolved, key=lambda x: (x.rel_path, x.lineno)):
        print(
            f"  {c.rel_path}:{c.lineno} {c.symbol} "
            f"(#{c.task_id}) \"{titles[c.task_id]}\""
        )

    if unresolvable:
        print(
            f"\nFAIL: {len(unresolvable)} of {total_real} docstring "
            f"citation(s) did not resolve across {files_examined} file(s)"
        )
        return 1
    print(
        f"\nOK: {len(resolved)} resolved, {len(unresolvable)} unresolvable, "
        f"{len(suspicious)} suspicious, {len(filtered)} filtered, "
        f"{len(skipped)} skipped across {files_examined} file(s)"
    )
    return 0


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
    enrolment_note = False
    for (doc, token), count in sorted(PINNED_CITATIONS.items()):
        actual = seen[(doc, token)]
        if actual < count:
            print(
                f"MISSING {doc}: {token}: expected {count} occurrence(s), "
                f"saw {actual}"
            )
            failed = True
            enrolment_note = True
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
                enrolment_note = True
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
        if enrolment_note:
            print(
                "\nNOTE: a MISSING or UNPINNED coordinate often means a pin "
                "was CORRECTLY repaired (the coordinate moved, or was retired "
                "to prose).  A repaired pin requires a matching enrolment "
                "update in BOTH dev/check_watch_citations.py "
                "(PINNED_CITATIONS) and test_check_watch_citations.py "
                "(REVIEWED_PIN_COUNTS).  This is a COORDINATOR act at fold — "
                "a lane must not resolve it by editing the guard or its test "
                "to force green."
            )
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
    parser.add_argument(
        "--dw-dir",
        type=Path,
        default=None,
        help=".dreamwork/ dir for issue-id resolution "
        "(default: main checkout's)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="show resolved citation rows (default: signal-only output)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    return check(root) | check_docstring_citations(
        root, args.dw_dir, verbose=args.verbose
    )


if __name__ == "__main__":
    raise SystemExit(main())
