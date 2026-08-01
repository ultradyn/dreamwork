#!/usr/bin/env python3
"""The always-run repo-wide guard set + a detector that flags unregistered
candidates (#778).

THE PROBLEM THIS EXISTS TO SOLVE
--------------------------------
``briefs/boilerplate.md`` tells a lane to "run a targeted subset, not the whole
tree" — the tests for the files it touched. That ruling is sound (a full sweep
is ~175s for ~2648 tests; N lanes re-proving it is N-1 wasted suites, #666) and
this tool does NOT reverse it. But a REPO-WIDE guard asserts a rule that spans
the whole repo, so it is not a test OF the lane's files:

- ``test_no_raw_connect.py`` scans EVERY production source for a raw
  ``sqlite3.connect``. #776's lane added one in ``dev/dispatch_lane.py``;
  the lane's targeted subset never reached the guard, and the merge was
  reverted (``8c6481fb``).
- ``test_ledger_cli.py::test_the_map_covers_every_verb`` requires EVERY parser
  verb to have a row in ``_VERB_ARGV``. #645 i9 added seven verbs with no rows;
  same gap, same revert (``5f1ea764``).

"Run the tests for the files you touched" cannot reach either, because the
governing test is not a test of those files. The fix is ADDITIVE: a small,
deliberate always-run set named next to the targeted-subset rule, so a lane
reading that rule also sees it.

THE ENTRY CRITERION (narrow, stated)
------------------------------------
A guard qualifies only if it **asserts a property over a population a lane
cannot enumerate from its own diff.** The unit is a TEST (a pytest node id),
not a file: ``test_ledger_cli.py`` holds ~36 tests, of which exactly one is
repo-wide, so registering the file would sweep in 35 targeted tests — the
widening #707 warns about. Registering the node id keeps the set at ~0.1% of
the tree instead.

CEILING, named honestly (#651): this catches cross-cutting RULES — a property
that spans a population the lane's diff cannot see. It does NOT catch a lane
breaking an unrelated feature's behaviour, which is what the coordinator's full
merged-tree sweep is for and remains for. Nothing here makes that sweep
optional.

THE REGISTRY IS AUTHORITATIVE; THE DETECTOR IS A BACKSTOP
---------------------------------------------------------
A hand-maintained list is the obvious answer and has the obvious defect: it
goes stale the day someone adds a repo-wide guard and does not register it, and
a stale list reads exactly like a complete one (#671). A purely derived list is
the other extreme — measured, "a test that enumerates repo files" matches six
files here and ``test_lint.py`` alone holds 563 tests, which is how the
targeted-subset ruling gets quietly reversed by a helper meant to support it
(#707).

So: a registered set (authoritative for what lanes run) PLUS a detector whose
only job is to say "this looks repo-wide and is NOT registered — classify it."
An unclassified candidate is a FINDING TO REPORT, not a member to add (#702).
That keeps the list small and deliberate, and it cannot rot in silence.

WHAT THE DETECTOR CAN AND CANNOT MECHANICALLY SEE
-------------------------------------------------
The detector's signal is deliberately narrow: a test source that enumerates the
FULL tracked-file set via a bare ``git ls-files`` (no path, no
``--error-unmatch``) — the unambiguous "scan the whole repo" form, and the
idiom every existing repo-wide guard of this family uses. It stays SILENT on:

- ``test_lint.py`` — its ``git ls-files`` calls are ``--error-unmatch <file>``
  (one file) and its globs are over a SPECIFIC directory (``briefs/``), not the
  whole repo. Flagging it wholesale would reproduce the trap, not avoid it.
- ``test_guard_evidence.py`` / ``test_client_dist.py`` — ``git ls-files
  <subdir>`` and ``--error-unmatch <file>``: path-restricted, so ordinary
  module tests that happen to enumerate a directory.

THE OPT-IN MARKER — closing the blind spot for guards that declare themselves
----------------------------------------------------------------------
The parser-coverage family (no ``git ls-files``, no whole-repo glob) is
invisible to the lexical signal above. Detecting "this test asserts a set is
complete" semantically would false-positive on hundreds of ordinary tests
(#707/#755), so the detector does not try. Instead, a repo-wide guard
DECLARES itself with a comment marker in its test source:

    # repo-wide-guard: <one-line reason>

The detector scans for this token as a second signal, alongside ``ls-files``.
Detection is exact (the guard asserts its own class) and zero-false-positive
(no ordinary test contains the token by accident).

THE BOUNDARY, NAMED HONESTLY (#651): the marker catches only guards whose
authors knew to declare it — the gap narrowed from "every parser-coverage
guard" to "every undeclared guard." ``validate`` states this boundary rather
than hiding it behind a green: it reports how many candidates each signal
found and says plainly that undeclared guards are invisible. The registry is
authoritative; the detector is a backstop for both the common form and the
declared form.

rglob / os.walk rooted at the REPO ROOT would also be repo-wide, but resolving
whether an rglob's base IS the repo root (vs a subdirectory) cannot be done
statically without false positives, so those are excluded too and named here.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------- #
# THE REGISTRY — authoritative always-run set.                                #
#                                                                             #
# Every entry is a pytest node id. Add one only when it meets the entry       #
# criterion (asserts a property over a population a lane cannot enumerate     #
# from its own diff) AND the cost is ~1% of the tree. `validate` refuses if   #
# an entry no longer resolves to a real collected test (#671).                #
# --------------------------------------------------------------------------- #
REGISTRY: list[str] = [
    # Scans EVERY production source for a raw sqlite3.connect outside the one
    # sanctioned door. Population: all tracked production Python. A lane adding
    # a connection in any one file cannot see from its diff that this guard
    # governs it. (#645 / #776's revert.)
    "test_no_raw_connect.py::test_no_raw_sqlite_connect_in_production_sources",
    # Requires the parser's verb set to EXACTLY equal _VERB_ARGV. Population:
    # every parser verb. A lane adding a verb cannot enumerate "every verb"
    # from its diff. (#645 i9's revert.)
    "test_ledger_cli.py::test_the_map_covers_every_verb",
]

# The detector signal: a quoted `ls-files` token that is the LAST positional
# argument — i.e. `git ls-files` with no path and no --error-unmatch after it,
# so it enumerates the FULL tracked-file set. The trailing `]` or `)` (with an
# optional comma) is what makes it "whole-repo" rather than "this subdirectory".
#   bare:     ["git", "ls-files"]            -> matches (whole repo)
#   path:     ["git", "ls-files", "screens"] -> no match (a subdirectory)
#   flag:     git("ls-files", "--error-unmatch", f)  -> no match (one file)
_BARE_LS_FILES = re.compile(r"['\"]ls-files['\"]\s*,?\s*[\]\)]")


def is_whole_repo_enumeration(source: str) -> bool:
    """True if ``source`` enumerates the full tracked-file set via bare git ls-files.

    Pure function over source text, so the detector is testable on synthetic
    inputs without depending on the live file set (which moves under every
    lane). The signal is the narrow one described in the module docstring.
    """
    return bool(_BARE_LS_FILES.search(source))


# The opt-in marker (#780). A repo-wide guard that the lexical detector
# cannot see (parser-coverage family) declares itself with this comment in
# its test source. The token is deliberately specific so no ordinary test
# contains it by accident — detection is exact and zero-false-positive.
_REPO_WIDE_MARKER = "repo-wide-guard:"


def is_declared_repo_wide(source: str) -> bool:
    """True if ``source`` declares itself a repo-wide guard via the marker.

    The marker is a comment: ``# repo-wide-guard: <one-line reason>``. It is
    the escape hatch for guards the lexical detector cannot see (no
    ``git ls-files``). Pure function over source text, like the ls-files signal.
    """
    return f"# {_REPO_WIDE_MARKER}" in source


def _tracked_test_files() -> list[Path]:
    """Every tracked ``test_*.py`` under the repo root (root + plugins)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z", "test_*.py",
             "*/test_*.py"],
            capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        # A fault reading the inventory is a fault, never a calm empty list: an
        # empty candidate set reads as "nothing to classify" and the detector
        # becomes decoration (#671).
        raise RepoWideGuardError(f"could not enumerate tracked test files: {exc}") from exc
    files = []
    for bit in out.stdout.split("\0"):
        if not bit:
            continue
        p = ROOT / bit
        if p.is_file():
            files.append(p)
    return sorted(files)


def find_candidate_files() -> list[Path]:
    """Tracked test files that look repo-wide by EITHER signal.

    A candidate is a FINDING, not a member: it still has to meet the entry
    criterion and be classified. ``detect`` reports those whose file is not
    already covered by a registry entry.

    Two independent signals:
    - ``is_whole_repo_enumeration``: bare ``git ls-files`` (lexical, for the
      file-enumeration family).
    - ``is_declared_repo_wide``: the opt-in marker ``# repo-wide-guard:``,
      which a guard that the lexical detector cannot see declares about itself
      (#780). This closes the blind spot for the parser-coverage family — a
      guard that declares itself is detected regardless of its enumeration idiom.
    """
    candidates = []
    for path in _tracked_test_files():
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if is_whole_repo_enumeration(source) or is_declared_repo_wide(source):
            candidates.append(path)
    return candidates


def _registry_files() -> set[str]:
    """The file stems the registry covers (the part before ``::``)."""
    return {nid.split("::", 1)[0] for nid in REGISTRY}


def detect_unregistered() -> list[Path]:
    """Candidate repo-wide guards (by either signal) whose file is not covered
    by the registry.

    These are the findings a classifier reviews. The marker closes the
    parser-coverage blind spot for DECLARED guards; an UNDECLARED guard (no
    ls-files, no marker) is still invisible — see the module docstring.
    """
    covered = _registry_files()
    return [p for p in find_candidate_files() if p.name not in covered]


def _collect_resolves(node_id: str) -> bool:
    """True if ``node_id`` collects as a real pytest test right now.

    Runs ``pytest <node_id> --collect-only -q`` and requires a zero exit AND
    the node id to appear in the collected output. A stale entry (renamed,
    deleted, moved) fails both: pytest exits nonzero with ``not found`` and the
    id never prints. Per-member collection is cheap (a file each) and avoids a
    full-tree pass.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", node_id, "--collect-only", "-q",
             "-o", "addopts=", "-p", "no:cacheprovider"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        # Cannot evaluate -> FAULT, not a silent pass (#671).
        raise RepoWideGuardError(
            f"could not run pytest to validate {node_id!r}: {exc}") from exc
    if proc.returncode != 0:
        return False
    # Parse collected node ids (lines containing '::'); ignore plugin chatter.
    return any(node_id in line for line in proc.stdout.splitlines()
               if "::" in line)


class RepoWideGuardError(Exception):
    """A fault the tool cannot evaluate — callers print and exit 2 (#671)."""


# --------------------------------------------------------------------------- #
# verbs                                                                        #
# --------------------------------------------------------------------------- #

def list_members() -> int:
    """Print the registered node ids, one per line. The single source a lane
    reads (#440); the boilerplate names them inline only for discoverability."""
    for nid in REGISTRY:
        print(nid)
    return 0


def _detect_detail() -> list[Path]:
    """All candidate files by either signal, for the verbs to report."""
    covered = _registry_files()
    return [p for p in find_candidate_files() if p.name not in covered]


def validate() -> int:
    """Every registry member must resolve to a real collected test (#671).

    Exit 0 = all members resolve (and unregistered candidates are reported as
    findings). Exit 2 = one or more members are stale, OR the inventory could
    not be read — a guard set that resolves to nothing must NEVER read as
    "all guards passed".

    The detector report states what each signal found and names the boundary
    it cannot see (#651): an UNDECLARED guard (no ls-files, no marker) is
    invisible to the detector. Completeness cannot be proven mechanically.
    """
    try:
        stale = [nid for nid in REGISTRY if not _collect_resolves(nid)]
    except RepoWideGuardError as exc:
        sys.stderr.write(f"validate: FAULT — {exc}\n")
        return 2
    if stale:
        sys.stderr.write(
            "validate: REFUSED — registry entries that no longer resolve to a "
            "real collected test (renamed / deleted / moved). A guard set that "
            "resolves to nothing must not read as 'all guards passed' (#671):\n"
            + "".join(f"  {nid}\n" for nid in stale))
        return 2
    print(f"validate: {len(REGISTRY)} registry member(s) all resolve.")
    # The detector runs as a backstop: report unregistered candidates as
    # findings, not failures (they need classification, #702).
    unregistered = _detect_detail()
    if unregistered:
        print("validate: DETECTOR — unregistered candidate(s) to classify "
              "(findings, not members):")
        for p in unregistered:
            signals = []
            src = p.read_text(encoding="utf-8")
            if is_whole_repo_enumeration(src):
                signals.append("file-enumeration")
            if is_declared_repo_wide(src):
                signals.append("opt-in-marker")
            print(f"  {p.name}  ({'+'.join(signals)}; classify against the "
                  f"entry criterion, then register or exclude)")
    else:
        print("validate: detector found no unregistered candidate by either "
              "signal (file-enumeration or opt-in marker). An UNDECLARED guard "
              "(no ls-files, no marker) is invisible — the registry is "
              "authoritative, not complete.")
    return 0


def detect() -> int:
    """Report repo-wide candidates by both signals and their registration status."""
    covered = _registry_files()
    candidates = find_candidate_files()
    if not candidates:
        print("detect: no candidate found by either signal (file-enumeration "
              "or opt-in marker). An UNDECLARED guard (no ls-files, no marker) "
              "is invisible — the registry is authoritative, not complete.")
        return 0
    for p in candidates:
        status = "registered" if p.name in covered else "UNREGISTERED — classify"
        print(f"detect: {p.name}  [{status}]")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="repo_wide_guards.py",
        description="The always-run repo-wide guard set (#778). "
                    "`list` prints the canonical set lanes run; "
                    "`validate` refuses if a registry entry is stale (#671) "
                    "and reports unregistered detector candidates; "
                    "`detect` reports candidates and their registration status.")
    ap.add_argument("verb", choices=["list", "validate", "detect"])
    args = ap.parse_args(argv)
    try:
        if args.verb == "list":
            return list_members()
        if args.verb == "validate":
            return validate()
        if args.verb == "detect":
            return detect()
    except RepoWideGuardError as exc:
        sys.stderr.write(f"{args.verb}: FAULT — {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
