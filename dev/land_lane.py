#!/usr/bin/env python3
"""Merge one rebased lane, gate it, then retire it through ``dev/reap.py``.

Every gate runs on a DETACHED HEAD holding the merge; ``refs/heads/master`` is
fast-forwarded onto it only once all of them have passed (#882). On 2026-08-01
this tool printed ``REFUSE phase=named-tests`` directly above ``examined:
merge=69fc8e9b``: it had already merged, and master carried a red merge while
the log said refused. A gate whose verdict arrives after its action is not a
gate.

Detaching beats merge-then-revert-on-refusal, and the difference is what
happens when the *recovery* fails. Here ``refs/heads/master`` never points at
an ungated merge at all, so a failed restore leaves the ref correct and only
the working tree detached — loud, local, and invisible to a lane rebasing onto
master. Revert-on-refusal fails the other way: interrupt it and master keeps
the bad merge, which is the incident this replaces.

The gates need the merged tree and its history, not the branch's — ``lint.py``
reads ``git log`` — so they run where HEAD *is* the merge commit, and
``merge-identity`` proves that before any of them are believed.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Sequence


WARN_ROW = re.compile(r"^\s+WARN(?:\s|$)")
PADDED_WARN_ROW = re.compile(
    r"^  WARN  (?P<label>\S(?:.*?\S)?)(?P<padding> {2,})(?P<detail>\S.*)$"
)
LINT_TRAILER = re.compile(r"^clean \((\d+) warning\(s\)\)$", re.MULTILINE)

# The gates this tool promises to run before the base branch is allowed to
# move. Declared apart from the code that runs them so that a gate deleted
# from the sequence is a REFUSAL rather than a shorter, quieter, green run:
# an empty phase list otherwise reports "all passed" and "none ran" alike.
# red-proof-history runs BEFORE the merge (it gates whether the merge may be
# built at all); the four below run on the merged tree. It is declared first
# because it is first to run, and it MUST be here — #951: the phase genuinely
# ran and blocked, but its absence from this tuple meant deleting its block
# left `gate-coverage: 4 of 4` UNCHANGED. The one phase with no protection
# against silent removal was the one phase that enforces every red-proof.
GATES = (
    "red-proof-history",
    "named-tests",
    "guard-selection",
    "repo-wide-guards",
    "lint-comparison",
)


def _gate_coverage_line(passed: Sequence[str]) -> str:
    """Report the lane gates without implying that they are the full suite."""
    return (
        f"gate-coverage: {len(passed)} of {len(GATES)} declared gates passed: "
        f"{' '.join(passed)}; full repo suite NOT RUN "
        "(test coverage was limited to lane-named tests, the tests derived from "
        f"the changed files by {len(DERIVATION_RULES)} derivation rule(s), and "
        "the repo-wide guards)"
    )


# ---------------------------------------------------------------------------
# The gate classifies its own diff, once, here.
#
# It used to demand a red-proof injection (#949) and trust a hand-written test
# selection (#948) without ever asking what the branch changed. Both demands
# are DERIVED below, from the diff — never from a flag the coordinator passes,
# which would be a bypass with extra steps.
#
# WHAT COUNTS AS INERT DOCUMENTATION, and why it is a narrow allowlist rather
# than a suffix test: a `.md` in this repo is frequently a program.
# `briefs/frame.md` is concatenated into every dispatched lane's prompt, so a
# change to it changes the whole loop's behaviour; `SKILL.md`, `watch-design.md`
# and `file-formats.md` are read by `lint.py`. None of those live under
# `.dreamwork/`, so none of them are reachable by this rule. What does live
# there is the loop's record OF ITSELF — analyses, plans, archived briefs, lane
# reports, review evidence — plus a handful of files the loop's own tools
# PARSE, which are named out below because a red-proof genuinely can bind them.
#
# ACCEPTED COST, stated rather than hidden: `.dreamwork/docs/*.md` holds
# re-runnable census blocks that a lane is told to extract and run, so editing
# one changes what a future lane executes while owing no injection here. That
# is deliberate — there is no check to turn red, so demanding a red-proof would
# force exactly the false-green this exemption avoids. The other gates still
# run on the merged tree; what the exemption removes is the demand for a
# LANE-AUTHORED red-proof, not the gating itself.
INERT_DOC_ROOT = ".dreamwork/"

EXECUTABLE_DOCS = frozenset({
    ".dreamwork/tasks.md",          # dev/ledger.py store; lint.py reads it
    ".dreamwork/lessons.md",        # dev/lessons_index.py parses its heads
    ".dreamwork/answers.md",        # dev/ledger.py
    ".dreamwork/questions.md",      # dev/ledger.py, dev/check_watch_citations.py
    ".dreamwork/handoffs.md",       # dev/brief.py, dev/check_watch_citations.py
    ".dreamwork/applied.md",        # dev/journal_consume.py, dev/expedite_hook.py
    ".dreamwork/docs/doc-map.md",   # lint.py check_doc_map_plans parses its rows
})


def _is_inert_doc(path: str) -> bool:
    """True when no behavioural red-proof could bind this path.

    Deliberately conservative in one direction only: anything this function
    cannot place confidently is NOT inert, so the injection is still required.
    """
    return (
        path.endswith(".md")
        and path.startswith(INERT_DOC_ROOT)
        and path not in EXECUTABLE_DOCS
    )


# The declared inventory of test-derivation rules. ``_derived_tests_line`` and
# ``_gate_coverage_line`` both read ``len(DERIVATION_RULES)`` so the rule count
# they print is derived from one place, not restated independently (#959: after
# #953 widened derivation to three rules, the coverage sentence still named only
# the name convention — the checker ratified the disagreement, #852/#905).
# Adding a rule means appending here AND implementing it at the call site in
# ``land()``; both reports' counts follow from this inventory.
DERIVATION_RULES: tuple[str, ...] = ("name", "import", "map")


def _derived_test(path: str) -> str | None:
    """This repo's test convention: ``foo.py`` → ``test_foo.py`` at the root.

    A changed test file is its own required test. Non-Python paths derive
    nothing — see ``_derived_tests_line`` for what that silence costs.
    """
    name = PurePosixPath(path)
    if name.suffix != ".py":
        return None
    if name.name.startswith("test_"):
        return name.name
    return f"test_{name.stem}.py"


# The name convention (above) finds tests NAMED FOR a module. It cannot find a
# test that merely IMPORTS the changed module under a different name — and that
# was #949's own blind spot: dev/land_lane.py changed, the convention derived
# test_land_lane.py, but the break was in test_suite_baseline.py, which does
# `from dev import land_lane` (#953). Two mechanisms close the two cases the
# convention cannot reach, because one rule cannot cover both:

# (1) IMPORT-GRAPH derivation — for each changed Python module, find every
# test file whose AST imports it. Strictly wider than the name convention for
# any test that imports what it tests, and it does NOT widen to prose mentions
# (a grep over the module name would drag in test_brief.py for nothing, which
# is the full-suite run under another name). Accepted cost: a test that
# exercises the module through importlib (test_land_lane.py's loader) or a
# subprocess is NOT reached here — the name convention covers the first, and
# the second has no static signal at all.
def _dotted_module(path: str) -> str | None:
    """``dev/land_lane.py`` → ``dev.land_lane``; non-``.py`` → ``None``."""
    name = PurePosixPath(path)
    if name.suffix != ".py" or name.name == "__init__.py":
        return None
    return ".".join(name.with_suffix("").parts)


def _import_targets(source: str) -> frozenset[str]:
    """Every dotted module a test source references via a static import.

    Records ``import a.b`` → ``a.b`` and ``from a import b`` → ``a`` plus
    ``a.b``, so ``from dev import land_lane`` yields ``dev.land_lane`` and
    matches a changed ``dev/land_lane.py``. Relative imports (``level > 0``)
    and ``*`` are excluded: the first is ambiguous without package context and
    the second carries no module name. A SyntaxError returns an empty set so an
    unparseable test file is skipped rather than crashing the gate.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return frozenset()
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                targets.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            targets.add(node.module)
            for alias in node.names:
                if alias.name != "*":
                    targets.add(f"{node.module}.{alias.name}")
    return frozenset(targets)


def _targets_import_module(targets: Sequence[str], module: str) -> bool:
    """The import-graph relation shared by derivation and relevance."""
    return module in targets or any(t.startswith(module + ".") for t in targets)


def _test_imports_modules(test_path: Path, modules: Sequence[str]) -> bool:
    """Whether ``test_path`` statically imports any requested module."""
    wanted = {module for module in modules if module}
    if not wanted:
        return False
    try:
        targets = _import_targets(test_path.read_text(encoding="utf-8"))
    except OSError:
        return False
    return any(_targets_import_module(targets, module) for module in wanted)


def _import_derived(repo: Path, modules: Sequence[str]) -> tuple[str, ...]:
    """Test files at the repo root whose AST imports any of ``modules``.

    ``modules`` are dotted module names (from ``_dotted_module``). A test
    covers a changed module when the module's dotted name is among the test's
    import targets, or a target extends it (``from dev.land_lane import X``
    produces ``dev.land_lane.X``). Root-level ``test_*.py`` only — matching the
    name convention's reach, so the two rules share one documented limit.
    """
    if not any(modules):
        return ()
    found: set[str] = set()
    for test_path in sorted(repo.glob("test_*.py")):
        if _test_imports_modules(test_path, modules):
            found.add(test_path.name)
    return tuple(sorted(found))


# (2) DIRECTORY→TESTSET MAP — for the case no file-name or import rule can
# express: a changed file whose coverage lives in GENERIC tests that SCAN a
# directory rather than name or import any one file. dev/capture/gitrow.mjs is
# covered by test_guard_evidence.py and test_guard_argv.py, which enumerate
# dev/capture/*.mjs as a set; the relationship is directory-to-testset, not
# name-to-name. A map is honest about being hand-maintained, and the gate
# REFUSES when an entry's target is absent from the merged tree (below) — a
# declared contract pointing at nothing is the map going stale, and landing
# through it would be the "named a file that exists but is irrelevant → GREEN"
# hole one level meta. test_guard_preflight.py is NOT here: it tests
# dev/guard_preflight.py (single file → the name convention reaches it), not
# the directory.
DIR_TESTSET_MAP: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("dev/capture/", ("test_guard_evidence.py", "test_guard_argv.py")),
)


def _path_in_mapped_directory(path: str, directory: str) -> bool:
    """The directory-map relation shared by derivation and relevance."""
    return path == directory.rstrip("/") or path.startswith(directory)


def _map_derived(changed: Sequence[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Apply ``DIR_TESTSET_MAP``: return (test targets, matched directories).

    A changed path matches a mapped directory when it sits at or beneath it.
    Only directories that actually matched a changed path contribute targets,
    so a landing that touches no file under a mapped dir is never blocked by
    that dir's entry.
    """
    matched_dirs: list[str] = []
    targets: set[str] = set()
    for directory, tests in DIR_TESTSET_MAP:
        if any(_path_in_mapped_directory(path, directory) for path in changed):
            matched_dirs.append(directory)
            targets.update(tests)
    return tuple(sorted(targets)), tuple(matched_dirs)


def _selected_test_file(selector: str) -> str:
    """The root test filename selected by a pytest path or node id."""
    return PurePosixPath(selector.split("::", 1)[0]).name


def _test_relation_rules(repo: Path, selector: str, changed: Sequence[str]) -> tuple[str, ...]:
    """Which of #953's three rules relate one selected test to the diff."""
    test_file = _selected_test_file(selector)
    rules: list[str] = []
    if any(_derived_test(path) == test_file for path in changed):
        rules.append("name")
    modules = tuple(
        module for module in (_dotted_module(path) for path in changed) if module
    )
    if _test_imports_modules(repo / test_file, modules):
        rules.append("import")
    if any(
        test_file in tests and _path_in_mapped_directory(path, directory)
        for path in changed
        for directory, tests in DIR_TESTSET_MAP
    ):
        rules.append("map")
    return tuple(rules)


def _test_relevance_line(repo: Path, selection: Sequence[str], changed: Sequence[str]) -> str:
    """Advisory relevance report over the final named-union-derived selection.

    The three rules are incomplete, so an unrelated result cannot safely
    refuse a correct landing. This is a gate-output advisory, not a lint WARN
    row, and therefore cannot enter the lint row-set comparison.
    """
    tests = tuple(dict.fromkeys(selection))
    prefix = (
        f"examined {len(tests)} selected test(s) against {len(changed)} changed path(s)"
    )
    if not tests or not changed:
        return (
            f"test-relevance: DID NOT CHECK — {prefix}; no relevance result is "
            "available when either population is empty"
        )
    unrelated = tuple(
        selector for selector in tests if not _test_relation_rules(repo, selector, changed)
    )
    if not unrelated:
        return (
            f"test-relevance: OK — {prefix}; all {len(tests)} related by at least "
            "one of the 3 rules"
        )
    return (
        f"test-relevance: WARN — {prefix}; {len(unrelated)} "
        "unrelated-as-far-as-the-3-rules-can-tell: "
        + " ".join(unrelated)
        + "; remedy: name or add a test related by the `test_<stem>.py` convention "
        "or a static import, or update DIR_TESTSET_MAP when a declared directory "
        "testset owns the changed path"
    )


def _named_files(tests: Sequence[str]) -> frozenset[str]:
    """The files the named selection runs IN FULL.

    A node id (``test_lint.py::TestOne``) runs part of a file, so it does NOT
    count as naming it: #936's eleven failures spanned five classes, and a gate
    satisfied by any one of them would have passed over the other ten. Adding
    the whole file alongside the node id re-collects that class once, which is
    much the cheaper of the two errors.
    """
    return frozenset(
        PurePosixPath(selector).name for selector in tests if "::" not in selector
    )


@dataclass(frozen=True)
class Diff:
    """What the branch changed, and what that makes the gate demand of it."""

    changed: tuple[str, ...]
    inert: tuple[str, ...]
    binding: tuple[str, ...]
    tests: tuple[str, ...]

    @property
    def required_injections(self) -> int:
        # An EMPTY diff is not an exemption: `changed` must be non-empty for
        # the documentation rule to have examined anything at all (#868).
        return 0 if self.changed and not self.binding else 1


def _classify_diff(repo: Path, base_sha: str, branch_sha: str) -> Diff | None:
    """Every path ``base_sha..branch_sha`` adds, changes or deletes.

    ``--no-renames`` on purpose: a rename reported as one post-image name can
    show a `.md` while hiding the `.py` it came from. Split as delete+add, both
    sides are classified. Returns ``None`` when git could not answer — a diff
    the gate cannot read is a refusal, never an exemption.
    """
    result = _git(repo, "diff", "--name-only", "--no-renames", "-z", base_sha, branch_sha)
    if result.returncode:
        _relay(result)
        return None
    changed = tuple(sorted(set(p for p in result.stdout.split("\0") if p)))
    inert = tuple(p for p in changed if _is_inert_doc(p))
    binding = tuple(p for p in changed if not _is_inert_doc(p))
    tests = tuple(sorted(set(t for t in (_derived_test(p) for p in changed) if t)))
    return Diff(changed=changed, inert=inert, binding=binding, tests=tests)


def _requirement_line(diff: Diff) -> str:
    """Why this branch owes the number of injections it owes.

    Three facts that must not collapse into one (#868): *nothing was required*,
    *nothing was found*, and *the registry could not be read*. This line owns
    the first; ``dev/redproof.py`` owns the other two, and the refusal below
    says which of them it is holding.
    """
    if diff.required_injections == 0:
        return (
            "red-proof requirement: 0 injections REQUIRED — all "
            f"{len(diff.changed)} changed path(s) are inert documentation under "
            f"{INERT_DOC_ROOT}; an increment that built no check must not "
            "manufacture a false-green: " + " ".join(diff.inert)
        )
    if not diff.changed:
        return (
            "red-proof requirement: 1 injection required — the diff is EMPTY, "
            "and examining no path is not a documentation exemption"
        )
    return (
        f"red-proof requirement: 1 injection required — {len(diff.binding)} of "
        f"{len(diff.changed)} changed path(s) are NOT inert documentation, so a "
        "behavioural red-proof could bind them: " + " ".join(diff.binding)
    )


def _derived_tests_line(
    diff: Diff,
    *,
    name: Sequence[str],
    imported: Sequence[str],
    mapped: Sequence[str],
    mapped_dirs: Sequence[str],
    existing: Sequence[str],
    unnamed: Sequence[str],
    absent: Sequence[str],
) -> str:
    """What derivation reached, per mechanism, and — the #948 failure mode — what it did not.

    "derived 0 required tests" is exactly how #936 hid: eleven failures sat on
    master for two hours because ``lint.py`` changed and ``test_lint.py`` was
    never named. So a zero here says WHY it is zero and what the branch's
    coverage then rests on, rather than reading like a satisfied requirement.

    Three rules now contribute (#953): the name convention, the import graph,
    and a directory→testset map. The line names what EACH reached, because a
    single total would hide that one of them contributed nothing — and the
    branch whose coverage rests on an empty mechanism is the one this report
    exists to flag. ``absent`` names derived tests the merged tree does not
    hold (a stale map target or a deleted name-derived file): the map case is a
    refusal at the call site, but the name/import cases can only be reported,
    so they appear here rather than reading as satisfied.
    """
    reach = (
        "name reaches root-level `test_<stem>.py` only; import reaches root "
        "`test_*.py` that statically import the module (not importlib loaders or "
        "subprocess calls); map reaches the declared directories in "
        "DIR_TESTSET_MAP only — anything else derives NOTHING and is not covered "
        "by this line"
    )
    by_rule = (
        f"name={len(name)} import={len(imported)} map={len(mapped)}"
        + (f" (matched dirs: {' '.join(mapped_dirs)})" if mapped_dirs else "")
    )
    if not existing:
        return (
            f"derived-tests: 0 required tests from {len(diff.changed)} changed "
            f"path(s) — {by_rule}; 0 present in the merged tree. This is NOT "
            f"coverage: the branch rests entirely on the named selection. {reach}"
        )
    added = (
        "all were already named"
        if not unnamed
        else f"{len(unnamed)} were NOT named and have been ADDED: " + " ".join(unnamed)
    )
    missing = (
        ""
        if not absent
        else f"; {len(absent)} DERIVED BUT ABSENT (stale derivation): "
        + " ".join(absent)
    )
    return (
        f"derived-tests: {len(existing)} required test(s) from "
        f"{len(diff.changed)} changed path(s) by {len(DERIVATION_RULES)} rules [{by_rule}]: "
        f"{' '.join(existing)}; {added}{missing}. {reach}"
    )


def _run(args: Sequence[str], repo: Path, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args), cwd=repo, env=env, capture_output=True, text=True
    )


def _relay(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", *args], repo)


def _git_text(repo: Path, *args: str) -> str | None:
    result = _git(repo, *args)
    if result.returncode:
        _relay(result)
        return None
    return result.stdout.strip()


def _worktrees(repo: Path) -> dict[str, Path] | None:
    result = _git(repo, "worktree", "list", "--porcelain")
    if result.returncode:
        _relay(result)
        return None
    found: dict[str, Path] = {}
    path: Path | None = None
    branch: str | None = None
    for line in [*result.stdout.splitlines(), ""]:
        if not line:
            if path is not None and branch is not None:
                found[branch.removeprefix("refs/heads/")] = path
            path = branch = None
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            path = Path(value).resolve()
        elif key == "branch":
            branch = value
    return found


def _warn_rows(output: str) -> tuple[str, ...]:
    return tuple(sorted(set(line for line in output.splitlines() if WARN_ROW.match(line))))


def _warn_row_identity(row: str) -> tuple[str, ...]:
    """Return WARN identity without ``lint.py``'s renderer-owned label padding.

    Only the spaces between the label and detail are presentation. Label text
    and the complete detail remain byte-for-byte identity, including meaningful
    whitespace. Older/simple fixture rows without that structured separator are
    compared raw rather than guessed.
    """
    match = PADDED_WARN_ROW.fullmatch(row)
    if match is None:
        return ("raw", row)
    return ("warn", match.group("label"), match.group("detail"))


def _warn_row_index(rows: Sequence[str]) -> dict[tuple[str, ...], str]:
    indexed: dict[tuple[str, ...], str] = {}
    for row in rows:
        identity = _warn_row_identity(row)
        prior = indexed.get(identity)
        if prior is not None and prior != row:
            raise ValueError(f"different WARN rows share one identity: {prior!r} and {row!r}")
        indexed[identity] = row
    return indexed


def _print_rows(label: str, rows: Sequence[str]) -> None:
    print(f"lint WARN rows {label}: {len(rows)}")
    for row in rows:
        print(row)


def _base_state(repo: Path, base: str, base_sha: str | None) -> str:
    """Where the base branch actually is, right now, in one greppable line.

    Every refusal carries this because a `REFUSE` that names only what it
    declined to do reads as "nothing happened" — which is precisely how the
    #882 incident was mis-read.
    """
    now = _git_text(repo, "rev-parse", "--verify", f"refs/heads/{base}") or "UNREADABLE"
    head = _git_text(repo, "rev-parse", "HEAD") or "UNREADABLE"
    if base_sha is None:
        return f"{base}={now}; no merge was attempted by this run; HEAD={head}"
    if now == base_sha:
        return f"{base}={now} unchanged by this run; HEAD={head}"
    if _git(repo, "merge-base", "--is-ancestor", base_sha, now).returncode == 0:
        return f"{base}={now} ADVANCED from {base_sha} by this run; HEAD={head}"
    return (
        f"{base}={now} MOVED OFF {base_sha} during this run; HEAD={head}; "
        f"any lane that rebased onto {base} in the interval must rebase again onto {now}"
    )


def _restore(repo: Path, base: str, base_sha: str) -> str | None:
    """Put the checkout back on ``base`` and PROVE it, or say how it did not.

    The checkout's exit status is not the evidence — it says only that git
    believed it worked. Reading the branch, HEAD and the tree back is. A
    restore that is performed but not verified is the same defect class as a
    merge that is performed but not gated.
    """
    checkout = _git(repo, "checkout", base)
    current = _git_text(repo, "branch", "--show-current")
    head = _git_text(repo, "rev-parse", "HEAD")
    dirty = _git(repo, "status", "--porcelain=v1", "--untracked-files=no")
    faults = []
    if checkout.returncode:
        faults.append(f"git checkout {base} exited {checkout.returncode}")
    if current != base:
        faults.append(f"checkout is on {current or 'a detached commit'}, not {base}")
    if head != base_sha:
        faults.append(f"HEAD is {head or 'UNREADABLE'}, not the pre-merge {base_sha}")
    if dirty.returncode or dirty.stdout:
        faults.append(f"{len(dirty.stdout.splitlines())} tracked path(s) still differ from {base}")
    return "; ".join(faults) or None


def _dirty_tree_line(label: str, path: Path, result: subprocess.CompletedProcess[str]) -> str:
    """One greppable line naming a tree and whether its tracked state is clean.

    Preflight inspects both the main checkout and the lane worktree, but its
    refusal used to print one sentence naming neither, so a reader who
    associated the refusal with the named branch inspected the clean lane while
    the main checkout was the dirty one (#898). The requirement that both trees
    be clean is unchanged; this only says which input failed.
    """
    if result.returncode:
        return f"{label}={path}: git status exited {result.returncode}"
    porcelain = result.stdout.splitlines()
    if porcelain:
        return f"{label}={path}: " + "; ".join(porcelain)
    return f"{label}={path}: clean"


def _refuse(
    phase: str,
    reason: str,
    examined: str,
    retained: str,
    *,
    base_state: str,
    alert: str | None = None,
) -> int:
    print(f"REFUSE phase={phase}: {reason}", file=sys.stderr)
    if alert:
        print(f"RESTORE FAILED: {alert}", file=sys.stderr)
    print(f"examined: {examined}", file=sys.stderr)
    print(f"base: {base_state}", file=sys.stderr)
    print(f"retained: {retained}", file=sys.stderr)
    print("deliberately did not perform: dev/reap.py lane retirement", file=sys.stderr)
    return 1


def _lint(repo: Path) -> tuple[subprocess.CompletedProcess[str], tuple[str, ...] | None]:
    result = _run([sys.executable, "lint.py"], repo)
    _relay(result)
    combined = result.stdout + result.stderr
    trailer = LINT_TRAILER.search(combined)
    rows = _warn_rows(combined)
    if result.returncode or trailer is None or int(trailer.group(1)) != len(rows):
        return result, None
    return result, rows


def land(branch: str, tests: Sequence[str], *, base: str = "master") -> int:
    repo_text = _git_text(Path.cwd(), "rev-parse", "--show-toplevel")
    repo = Path(repo_text).resolve() if repo_text else Path.cwd().resolve()
    retained = f"branch={branch}; worktree=not-yet-resolved"

    if not tests:
        return _refuse(
            "selection",
            "named test selection is empty",
            f"branch argument={branch}; named tests=0",
            retained,
            base_state=_base_state(repo, base, None),
        )

    current = _git_text(repo, "branch", "--show-current")
    base_sha = _git_text(repo, "rev-parse", "--verify", f"refs/heads/{base}")
    branch_sha = _git_text(repo, "rev-parse", "--verify", f"refs/heads/{branch}")
    worktrees = _worktrees(repo)
    if current != base or not base_sha or not branch_sha or worktrees is None:
        return _refuse(
            "preflight",
            f"requires current branch {base} and resolvable local branch {branch}",
            f"current={current or 'UNKNOWN'}; base={base_sha or 'UNKNOWN'}; branch={branch_sha or 'UNKNOWN'}",
            retained,
            base_state=_base_state(repo, base, None),
        )
    lane = worktrees.get(branch)
    if lane is None:
        return _refuse(
            "preflight",
            "branch has no registered linked worktree",
            f"base={base_sha}; branch={branch_sha}; registered worktrees={len(worktrees)}",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )
    retained = f"branch={branch}; worktree={lane}"

    ancestor = _git(repo, "merge-base", "--is-ancestor", base_sha, branch_sha)
    if ancestor.returncode:
        return _refuse(
            "preflight",
            f"branch is not rebased onto current {base}",
            f"base={base_sha}; branch={branch_sha}; worktree={lane}",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )

    main_dirty = _git(repo, "status", "--porcelain=v1", "--untracked-files=no")
    lane_dirty = _git(lane, "status", "--porcelain=v1", "--untracked-files=no")
    if main_dirty.returncode or lane_dirty.returncode or main_dirty.stdout or lane_dirty.stdout:
        return _refuse(
            "preflight",
            "tracked worktree state is not clean\n"
            + _dirty_tree_line("main", repo, main_dirty)
            + "\n"
            + _dirty_tree_line("lane", lane, lane_dirty),
            f"base={base_sha}; branch={branch_sha}; main-status={len(main_dirty.stdout.splitlines())}; lane-status={len(lane_dirty.stdout.splitlines())}",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )
    lane_all = _git(lane, "status", "--porcelain=v1", "--ignored")
    if lane_all.returncode:
        return _refuse(
            "preflight",
            "could not record lane worktree state",
            f"base={base_sha}; branch={branch_sha}; status command exit={lane_all.returncode}",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )
    print(
        f"pre-merge: base={base}@{base_sha} branch={branch}@{branch_sha} "
        f"worktree={lane} status-rows={len(lane_all.stdout.splitlines())} named-tests={len(tests)}"
    )
    for row in lane_all.stdout.splitlines():
        print(f"pre-merge lane-status: {row}")

    _, baseline = _lint(repo)
    if baseline is None:
        return _refuse(
            "lint-baseline",
            "WARN baseline was not captured (lint failed or emitted no clean trailer)",
            f"lint.py in {repo}; base={base_sha}; branch={branch_sha}",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )
    _print_rows("baseline", baseline)
    if not baseline:
        return _refuse(
            "lint-baseline",
            "WARN baseline population is empty; zero rows examined is not a comparison",
            f"lint.py in {repo}; base={base_sha}; branch={branch_sha}; baseline=0 rows examined",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )

    # Spans the pre-merge phase (red-proof-history, below) and the post-merge
    # phases. Declared here — before the first gate appends to it — so the
    # phase that runs before the merge is counted in the same denominator as
    # the four that run after it (#951).
    passed: list[str] = []

    branch_commits = _git(repo, "rev-list", "--count", f"{base_sha}..{branch_sha}")
    try:
        commits_examined = int(branch_commits.stdout.strip())
    except ValueError:
        commits_examined = -1
    if branch_commits.returncode or commits_examined < 0:
        _relay(branch_commits)
        return _refuse(
            "red-proof-history",
            "could not count the branch commits the red-proof scan must examine",
            f"base={base_sha}; branch={branch_sha}; rev-list exit={branch_commits.returncode}",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )

    diff = _classify_diff(repo, base_sha, branch_sha)
    if diff is None:
        return _refuse(
            "diff-classification",
            "could not read the branch diff, so neither the red-proof requirement "
            "nor the required tests could be derived from it",
            f"base={base_sha}; branch={branch_sha}",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )
    print(
        f"diff-classification: {len(diff.changed)} changed path(s); "
        f"{len(diff.inert)} inert documentation; "
        f"{len(diff.binding)} that a red-proof could bind"
    )
    print(_requirement_line(diff))
    required = diff.required_injections

    redproof_env = os.environ.copy()
    redproof_env.pop("DREAMWORK_LANE_ID", None)
    redproof_env["DREAMWORK_LANE_ROLE"] = "author"
    redproof = _run(
        [
            sys.executable,
            str(Path(__file__).with_name("redproof.py")),
            "check",
            "--cwd",
            str(lane),
            "--base",
            base_sha,
            "--require",
            str(required),
        ],
        repo,
        env=redproof_env,
    )
    _relay(redproof)
    audited_lane_head = _git_text(lane, "rev-parse", "HEAD")
    audited_branch_sha = _git_text(repo, "rev-parse", "--verify", f"refs/heads/{branch}")
    population = (
        f"commits examined={commits_examined}; registries audited=ALL DISCOVERABLE "
        f"by dev/redproof.py (zero is not accepted); injections registered and "
        f"causally caught>="
        f"{required} required; {_requirement_line(diff)}; "
        f"audited tip={audited_lane_head or 'UNREADABLE'}"
    )
    if redproof.returncode:
        # A FAULT stays a refusal at --require 0 — the exemption is about what
        # was OWED, never about whether the audit could run. But #940: say
        # which of the two this is, because a doc-only branch that owed nothing
        # and a branch hiding an armed injection print the same exit code.
        note = ""
        if required == 0 and redproof.returncode == 2:
            note = (
                "; NOTE this FAULT is NOT the --require rule: 0 injections were "
                "owed, and dev/redproof.py faults independently of --require when "
                "it can locate no registry for this worktree. That fault is #949's "
                "unfixed second half and lives in dev/redproof.py, not here"
            )
        return _refuse(
            "red-proof-history",
            f"dev/redproof.py check refused or faulted with exit {redproof.returncode}"
            + note,
            population,
            retained,
            base_state=_base_state(repo, base, base_sha),
        )
    if commits_examined == 0:
        return _refuse(
            "red-proof-history",
            "EXAMINED NO COMMIT; an empty history range is not an all-clear",
            population,
            retained,
            base_state=_base_state(repo, base, base_sha),
        )
    if audited_lane_head != branch_sha or audited_branch_sha != branch_sha:
        return _refuse(
            "red-proof-history",
            "branch tip moved while its red-proof history was being audited",
            population
            + f"; preflight tip={branch_sha}; branch now={audited_branch_sha or 'UNREADABLE'}",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )
    print(f"red-proof-history: PASS; {population}")
    passed.append("red-proof-history")

    detach = _git(repo, "checkout", "--detach", base_sha)
    if detach.returncode:
        _relay(detach)
        return _refuse(
            "detach",
            f"could not detach HEAD at {base} to build the merge off-branch (exit {detach.returncode})",
            f"base={base_sha}; branch={branch_sha}; worktree={lane}",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )
    print(f"detached at {base_sha}: {base} does not move until every gate in {list(GATES)!r} passes")

    merged_sha = "not-created"

    def refuse_gated(phase: str, reason: str, examined: str) -> int:
        """Refuse a post-merge phase, restoring the checkout first."""
        faults = _restore(repo, base, base_sha)
        return _refuse(
            phase,
            reason,
            examined,
            retained,
            base_state=_base_state(repo, base, base_sha),
            alert=None
            if faults is None
            else (
                f"{faults}; the checkout may still hold the ungated merge {merged_sha} — "
                f"run `git checkout {base}` in {repo}"
            ),
        )

    merge = _git(repo, "merge", "--no-ff", branch_sha, "-m", f"Merge {branch}")
    _relay(merge)
    if merge.returncode:
        _git(repo, "merge", "--abort")
        return refuse_gated(
            "merge",
            f"git merge --no-ff exited {merge.returncode}",
            f"base={base_sha}; branch={branch_sha}; worktree={lane}",
        )
    merged_sha = _git_text(repo, "rev-parse", "HEAD") or "UNKNOWN"

    # The gates below examine whatever HEAD is; prove it is the merge of the
    # two shas preflight read, so no gate can pass against the branch tree, a
    # stale merge, or a base that moved. The parents come from git, which the
    # tree under test cannot rewrite.
    parents = (_git_text(repo, "rev-list", "--parents", "-n", "1", "HEAD") or "").split()[1:]
    if parents != [base_sha, branch_sha]:
        return refuse_gated(
            "merge-identity",
            "HEAD is not the merge of the examined base and branch, so no gate below would judge it",
            f"merge={merged_sha}; parents={parents!r}; expected=[{base_sha!r}, {branch_sha!r}]",
        )
    print(f"merge-identity: {merged_sha} has parents {base}@{base_sha} and {branch}@{branch_sha}")

    # #948: the named selection is the coordinator's guess, made when they are
    # most eager to land. Three ways to use the derivation were weighed (IGC):
    # REPORT the omission, REFUSE on it, or RUN it. REPORT is refuted — this
    # gate already printed a true line saying the full suite had not run, and
    # that line was read past while eleven test_lint.py failures sat on master
    # for two hours after #936. REFUSE is refuted by cost: it spends a whole
    # landing cycle to arrive at the test run it could simply have performed.
    # So the derived tests are RUN, and the omission is reported alongside.
    # Accepted cost: a branch touching `foo.py` is now blocked when
    # `test_foo.py` is red for a reason the branch did not cause — which is
    # #936's complaint, not a regression against it.
    #
    # #953 widened derivation beyond the name convention. The name rule is
    # path-based and was computed pre-merge in ``_classify_diff`` (``diff.tests``);
    # the import-graph and directory-map rules are computed HERE because they
    # read test-file CONTENTS, and a branch may have ADDED the test that imports
    # the changed module — which only the merged tree (HEAD, below) holds. Each
    # rule is RUN, never just reported (#949's IGC ruling: REPORT was refuted by
    # #936, where a true "not run" line was read past for two hours).
    name_tests = diff.tests
    import_tests = _import_derived(
        repo, [_dotted_module(p) for p in diff.binding if p.endswith(".py")]
    )
    mapped_tests, mapped_dirs = _map_derived(diff.changed)
    derived = tuple(sorted(set(name_tests) | set(import_tests) | set(mapped_tests)))
    existing = tuple(t for t in derived if (repo / t).is_file())
    unnamed = tuple(t for t in existing if t not in _named_files(tests))
    absent = tuple(sorted(set(derived) - set(existing)))
    # The directory map is a declared contract: an entry whose target is absent
    # from the merged tree is the map going STALE, and landing through it would
    # be the "named a file that exists but is irrelevant → GREEN" hole one level
    # meta. Refuse only when a changed path actually matched the mapped dir, so
    # a landing that touches nothing under it is never blocked by its entry.
    map_absent = tuple(t for t in mapped_tests if t not in existing) if mapped_dirs else ()
    if map_absent:
        return refuse_gated(
            "named-tests",
            "directory→testset map targets a test ABSENT from the merged tree; "
            "the map is stale and the branch rests on coverage it does not have",
            f"merge={merged_sha}; matched-dirs={list(mapped_dirs)!r}; "
            f"absent-targets={list(map_absent)!r}; "
            "remedy: update DIR_TESTSET_MAP in dev/land_lane.py or restore the test",
        )
    print(_derived_tests_line(
        diff,
        name=name_tests,
        imported=import_tests,
        mapped=mapped_tests,
        mapped_dirs=mapped_dirs,
        existing=existing,
        unnamed=unnamed,
        absent=absent,
    ))
    selection = tuple(dict.fromkeys((*tests, *unnamed)))
    print(_test_relevance_line(repo, selection, diff.changed))

    named = _run(["just", "pytest", *selection], repo)
    _relay(named)
    if named.returncode:
        return refuse_gated(
            "named-tests",
            f"named test selection failed with exit {named.returncode}",
            f"merge={merged_sha}; tests={list(tests)!r}; "
            f"derived-and-added={list(unnamed)!r}",
        )
    passed.append("named-tests")

    guard_list = _run([sys.executable, "dev/repo_wide_guards.py", "list"], repo)
    _relay(guard_list)
    guards = guard_list.stdout.split()
    if guard_list.returncode or not guards:
        reason = (
            f"repo-wide guard list command exited {guard_list.returncode}"
            if guard_list.returncode
            else "repo-wide guard list is empty"
        )
        return refuse_gated(
            "guard-selection",
            reason,
            f"merge={merged_sha}; generator=dev/repo_wide_guards.py list; selected={len(guards)}",
        )
    passed.append("guard-selection")
    print(f"repo-wide guard selection: {len(guards)} test path(s): {' '.join(guards)}")
    guarded = _run(["just", "pytest", *guards], repo)
    _relay(guarded)
    if guarded.returncode:
        return refuse_gated(
            "repo-wide-guards",
            f"generated guard set failed with exit {guarded.returncode}",
            f"merge={merged_sha}; guards={guards!r}",
        )
    passed.append("repo-wide-guards")

    _, after = _lint(repo)
    if after is None:
        return refuse_gated(
            "lint-comparison",
            "post-merge WARN rows were unavailable (lint failed or emitted no clean trailer)",
            f"merge={merged_sha}; baseline rows={len(baseline)}",
        )
    _print_rows("post-merge", after)
    if not after:
        return refuse_gated(
            "lint-comparison",
            "post-merge WARN population is empty; zero rows examined is not a match",
            f"merge={merged_sha}; baseline={len(baseline)} rows; post-merge=0 rows examined",
        )
    try:
        baseline_index = _warn_row_index(baseline)
        after_index = _warn_row_index(after)
    except ValueError as exc:
        return refuse_gated(
            "lint-comparison",
            f"WARN identity normalisation is ambiguous: {exc}",
            f"merge={merged_sha}; baseline={len(baseline)} rows; post-merge={len(after)} rows",
        )
    added_ids = set(after_index) - set(baseline_index)
    removed_ids = set(baseline_index) - set(after_index)
    added = tuple(sorted(after_index[identity] for identity in added_ids))
    removed = tuple(sorted(baseline_index[identity] for identity in removed_ids))
    print(f"lint WARN row-set comparison: added={len(added)} removed={len(removed)}")
    print(f"lint WARN populations: baseline={len(baseline)} rows; post-merge={len(after)} rows")
    for row in added:
        print(f"+ {row}")
    for row in removed:
        print(f"- {row}")
    if added or removed:
        return refuse_gated(
            "lint-comparison",
            "WARN row set changed from the pre-merge baseline",
            f"merge={merged_sha}; baseline={len(baseline)} rows; post-merge={len(after)} rows",
        )
    passed.append("lint-comparison")

    missing = tuple(gate for gate in GATES if gate not in passed)
    if not GATES or not passed or missing:
        return refuse_gated(
            "gate-coverage",
            f"only {len(passed)} of {len(GATES)} declared gates ran, so a pass here would be vacuous",
            f"merge={merged_sha}; ran={passed!r}; declared={list(GATES)!r}; missing={list(missing)!r}",
        )
    print(_gate_coverage_line(passed))

    back = _restore(repo, base, base_sha)
    if back is not None:
        return _refuse(
            "advance",
            f"could not return to {base} to fast-forward it onto the gated merge",
            f"merge={merged_sha}; faults={back}",
            retained,
            base_state=_base_state(repo, base, base_sha),
            alert=f"{back}; the checkout may still hold the gated merge {merged_sha}",
        )
    forward = _git(repo, "merge", "--ff-only", merged_sha)
    landed = _git_text(repo, "rev-parse", "--verify", f"refs/heads/{base}")
    if forward.returncode or landed != merged_sha:
        _relay(forward)
        return _refuse(
            "advance",
            f"fast-forward of {base} onto the gated merge did not land",
            f"merge={merged_sha}; ff-exit={forward.returncode}; {base}={landed or 'UNREADABLE'}",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )
    print(f"advance: {base} {base_sha} -> {merged_sha} after {len(passed)} gate(s)")

    reap = _run(
        [sys.executable, str(Path(__file__).with_name("reap.py")), str(lane), "--base", base],
        repo,
        env=os.environ.copy(),
    )
    _relay(reap)
    if reap.returncode:
        return _refuse(
            "retirement",
            f"dev/reap.py refused with exit {reap.returncode}",
            f"merge={merged_sha}; branch={branch_sha}; worktree={lane}",
            retained,
            base_state=_base_state(repo, base, base_sha),
        )
    print(f"landed: merge={merged_sha}; branch retained={branch}; worktree retired by dev/reap.py")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Merge a rebased lane, run named and repo-wide gates, then reap its worktree."
    )
    parser.add_argument("branch", help="explicit local lane branch")
    parser.add_argument("tests", nargs="*", help="explicit named pytest paths/node ids")
    parser.add_argument("--base", default="master", help="checked-out base branch (default: master)")
    args = parser.parse_args(argv)
    return land(args.branch, args.tests, base=args.base)


if __name__ == "__main__":
    raise SystemExit(main())
