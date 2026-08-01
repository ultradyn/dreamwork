#!/usr/bin/env python3
"""Census of repo-relative file citations that name files which do not exist.

This is a CENSUS tool, not a guard.  It scans tracked Markdown documents for
citations to repo-relative file paths and reports those that resolve to
neither a tracked file nor a file on disk.  It deliberately does NOT fail the
run on dangling citations, because dangling splits into three classes —
STALE (a real defect), HISTORICAL (a brief legitimately describing a past
state) and FORWARD (a doc citing a not-yet-built file) — that share the same
path forms and differ only in authorial intent no regex can read.  See the
report at `.dreamwork/docs/dangling-citations-2026-08-02.md` for the ruling.

What counts as a CITATION (stated, because a scanner with silent scope is the
defect this task exists to close — the coordinator's first scan reported 198
dangling paths by counting HTTP routes and gitignored-but-present files):

  A citation is EITHER
    (a) a backtick-wrapped repo-relative file path, optionally with ``:line``
        or ``:line-line`` — e.g. `` `dev/relay.py` ``, `` `dev/x.py:4-11` ``;
    OR
    (b) a repo-relative file path immediately followed by ``:line`` —
        e.g. ``dev/x.py:42`` in running prose.

Exclusion rules (each applied, each stated in the output):
  1. REPO-RELATIVE.  After stripping a leading ``./``, ``../``, ``~/`` or
     ``/``, the path must still contain at least one ``/`` (a directory
     component).  This drops bare ``status_sync.py`` (a name, not a path),
     ``data.json`` (an HTTP route) and ``igc-method.md`` (skill-relative).
  2. FILE-SHAPED.  The final component must carry an extension (``.`` followed
     by alphanumerics) — so a citation names a file, not a directory or prose.
  3. ON-DISK-EXCLUDED.  A path present on disk is not dangling, even when it
     is gitignored (``.dreamwork/status.json`` is gitignored but present).
  4. TRACKED-EXCLUDED.  A path tracked at ``HEAD`` is not dangling.

The two denominators — documents scanned and citations seen — ALWAYS print,
and a run that examined zero of either exits ``2`` with a loud ``ERROR``: a
regex that silently stops matching reports a clean repo identically to a
clean scan (#868), and this whole instrument is one regex.

Exit codes: ``0`` for a completed census (dangling is the repo's normal state
today, so dangling-is-not-failure is intentional); ``2`` for vacuity (a
denominator reached zero) or a usage error.  There is no failing-on-dangling
mode on purpose: see the report.
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

# A file path body: one or more directory components, then a final component
# carrying an extension.  Each component MAY start with a single dot so a
# hidden directory like ``.dreamwork/`` is captured WHOLE — otherwise the
# leading dot is dropped and the tracked ``.dreamwork/tasks.md`` is mis-read
# as a dangling ``dreamwork/tasks.md`` (a systematic false positive).  A
# leading ``/``, ``~/`` or ``../`` is NOT captured here on purpose: such a
# prefix marks an ABSOLUTE or external path, which :func:`normalise` rejects
# outright (this is the rule that turns the coordinator's naive 198 into an
# honest census — ``/data.json`` is an HTTP route and ``/home/…`` is another
# machine, not repo-relative files).  An absolute path that nonetheless
# sneaks through a backtick pair (`` `/usr/lib/…/server.py` ``) is a STATED
# scanner artifact, not silently clean; see the report.
_COMPONENT = r"\.?[A-Za-z0-9_][\w.-]*"
_PATH_BODY = rf"(?:{_COMPONENT}/)+{_COMPONENT}\.[A-Za-z0-9]+"
# A line coordinate tail WITHOUT the leading colon: ``42`` or ``4-11``.
_LINE_TAIL = r"\d+(?:\s*[-–]\s*\d+)?"

CITATION = re.compile(
    rf"`(?P<bt_path>{_PATH_BODY})(?::(?P<bt_line>{_LINE_TAIL}))?`"  # backtick-wrapped
    # Bare form REQUIRES :line and a non-path char (incl. ``/`` and ``.``)
    # before it, so a mid-token snip such as ``3.14/http/server.py`` from an
    # absolute path, or a suffix after ``/``, is not lifted into a citation.
    rf"|(?:(?<![\w/`./])(?P<bare_path>{_PATH_BODY}):(?P<bare_line>{_LINE_TAIL}))"
)

# ``./`` is repo-current-dir-relative and is stripped; ``/``, ``~/`` and
# ``../`` mark an absolute/external path and are REJECTED (return None).
_DOTSLASH = re.compile(r"^\./+")
_ABSOLUTE = re.compile(r"^(?:/|~/|\.\./)")


@dataclass(frozen=True)
class Hit:
    """One dangling citation occurrence."""

    doc: str
    path: str
    line_no: int
    text: str


def normalise(raw: str) -> str | None:
    """Return the repo-relative path, or ``None`` if it is not repo-relative.

    An absolute/external path — one starting with ``/``, ``~/`` or ``../`` —
    is rejected outright (``None``): it was never a repo-relative file, and
    counting ``/data.json`` (an HTTP route) or ``/home/…`` (another machine)
    as dangling is the 198→30 error.  A leading ``./`` (repo-current-dir) is
    stripped.  What remains must contain a ``/`` (a directory component) and
    so bare ``status_sync.py`` (a name, not a path) is also rejected.
    """
    if _ABSOLUTE.match(raw):
        return None
    stripped = _DOTSLASH.sub("", raw, count=1)
    if "/" not in stripped:
        return None
    return stripped


def _tracked_paths(root: Path) -> set[str]:
    """Tracked Markdown documents, as repo-relative strings."""
    proc = subprocess.run(
        ["git", "ls-files", "-z", "*.md", "*.markdown"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return set()
    return {p for p in proc.stdout.split("\0") if p}


def _is_tracked(root: Path, path: str) -> bool:
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{path}"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    return proc.returncode == 0


def _exists_anywhere(root: Path, path: str) -> bool:
    return (root / path).exists()


def scan(root: Path) -> tuple[int, int, list[Hit]]:
    """Scan tracked Markdown under ``root``; return denominators and dangling hits.

    A hit is a citation whose normalised path is neither tracked at HEAD nor
    present on disk.  Tracked-ness is resolved per distinct path (one
    ``git cat-file`` per unique candidate), not per occurrence.
    """
    docs = sorted(_tracked_paths(root))
    docs_scanned = 0
    citations_seen = 0
    candidates: dict[str, list[tuple[str, int, str]]] = {}
    for rel in docs:
        path = root / rel
        if not path.is_file():
            continue
        docs_scanned += 1
        for lineno, text in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            for m in CITATION.finditer(text):
                raw = m.group("bt_path") or m.group("bare_path")
                citations_seen += 1
                norm = normalise(raw)
                if norm is None:
                    continue
                candidates.setdefault(norm, []).append((rel, lineno, text.strip()))

    dangling: list[Hit] = []
    for path, occs in sorted(candidates.items()):
        if _exists_anywhere(root, path):
            continue
        if _is_tracked(root, path):
            continue
        for doc, line_no, text in occs:
            dangling.append(Hit(doc, path, line_no, text))
    return docs_scanned, citations_seen, dangling


EXCLUSION_RULES = (
    "EXCLUSION RULES (each applied; each STATED — the coordinator's first scan "
    "reported 198 by silently counting HTTP routes, gitignored-but-present "
    "files, and absolute paths into other machines):",
    "  1. REPO-RELATIVE ONLY: a leading / ~/ or ../ REJECTS the path as "
    "absolute/external (/data.json is an HTTP route; /home/... is another "
    "machine). A leading ./ is stripped. A bare name with no '/' (e.g. "
    "'status_sync.py') is rejected — a name is not a path.",
    "  2. FILE-SHAPED: the final component must carry an extension.",
    "  3. ON-DISK-EXCLUDED: a path present on disk is not dangling "
    "(gitignored-but-present like '.dreamwork/status.json'). NOTE: gitignored "
    "files do not travel into a lane worktree, so a census run against a "
    "worktree over-counts them — run against the main checkout for the "
    "on-disk exclusion to bite.",
    "  4. TRACKED-EXCLUDED: a path tracked at HEAD is not dangling.",
)


def report(root: Path) -> int:
    docs_scanned, citations_seen, dangling = scan(root)
    print(f"root: {root}")
    print(f"documents scanned: {docs_scanned}")
    print(f"citations seen:    {citations_seen}")
    for line in EXCLUSION_RULES:
        print(line)
    if docs_scanned == 0:
        print(
            "ERROR vacuity: documents scanned is 0 — a regex that silently "
            "stops matching reads identically to a clean scan (#868)"
        )
        return 2
    if citations_seen == 0:
        print(
            "ERROR vacuity: citations seen is 0 across "
            f"{docs_scanned} document(s) — the citation regex matched "
            "nothing, which is indistinguishable from a clean repo (#868)"
        )
        return 2

    by_path: Counter[str] = Counter(h.path for h in dangling)
    distinct = len(by_path)
    total = sum(by_path.values())
    print(
        f"DANGLING: {total} occurrence(s), {distinct} distinct path(s) "
        "(neither tracked at HEAD nor present on disk)"
    )
    print("CITATION SCOPE: backtick-wrapped repo-relative file path, OR a "
          "bare such path immediately followed by :line. Bare un-backticked "
          "paths without :line, and Markdown link targets, are NOT matched "
          "(stated blind spot — see report).")
    if dangling:
        print("--- dangling by path (count) ---")
        for path, count in by_path.most_common():
            print(f"  {count:>3}x  {path}")
        print("--- dangling occurrences (doc:line -> path) ---")
        for h in sorted(dangling, key=lambda x: (x.path, x.doc, x.line_no)):
            print(f"  {h.doc}:{h.line_no}  {h.path}")
            print(f"        | {h.text[:140]}")
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
