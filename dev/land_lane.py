#!/usr/bin/env python3
"""Merge and gate one rebased lane in a detached scratch worktree.

The main checkout remains attached to ``master`` for the whole run. A detached
registered scratch starts at the captured base, holds the provisional merge,
and is the cwd for every gate command. Only after all gates pass does one short
compare-before-advance section fast-forward ``master`` exactly once (#882,
#1128). The whole-run gate mutex remains: a scratch location does not make the
single ``master`` ref multiwriter.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
import errno
from enum import Enum
import fcntl
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
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
# built at all); the five below run on the merged tree. It is declared first
# because it is first to run, and it MUST be here — #951: the phase genuinely
# ran and blocked, but its absence from this tuple meant deleting its block
# left `gate-coverage: 4 of 4` UNCHANGED. The one phase with no protection
# against silent removal was the one phase that enforces every red-proof.
GATES = (
    "red-proof-history",
    "lint-precheck",
    "named-tests",
    "guard-selection",
    "repo-wide-guards",
    "lint-comparison",
)


# ---------------------------------------------------------------------------
# The gate-in-flight breadcrumb (#1120).
#
# ``land_lane`` builds the merge in a registered detached scratch. Interrupted
# after creation, that registration keeps the provisional commit reachable
# while main remains attached and ``master`` remains unmoved. This breadcrumb
# names the exact residue and makes it DISCOVERABLE rather than merely rarer.
#
# The breadcrumb is the piece that matters most because the ``finally``
# cleanup cannot cover SIGKILL, ``os._exit``, or a segfault — all of which
# skip Python cleanup (#651: say plainly which signals are covered and which
# are not, rather than implying the hole is closed). The breadcrumb covers
# those paths. A reader (the next run's preflight, below) distinguishes
# THREE states (#136: three zero-states, not two): no file / file with a
# LIVE pid / file with a DEAD pid. A live pid means a gate is running RIGHT
# NOW; a dead pid means the exact scratch registration must be recovered.
GATE_IN_FLIGHT_PATH = Path(".dreamwork") / "gate-in-flight.json"


def _pid_alive(pid: int) -> bool:
    """Whether a process id is currently live (``kill(pid, 0)``)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # The pid exists but is owned by another user — treat as live,
        # because a reader cannot distinguish "another user's gate" from
        # "my gate under a different uid" without that being a dead-state
        # false alarm.
        return True
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return False
        return True
    return True


@dataclass(frozen=True)
class GateInFlight:
    """The three states (#136) a reader must distinguish, encoded by data.

    * ``path is None`` — no breadcrumb file: no gate in flight.
    * ``path`` set, ``pid`` LIVE — a gate is running right now.
    * ``path`` set, ``pid`` DEAD — a gate died mid-flight; recover.
    """

    path: Path | None
    branch: str
    gate_worktree: str
    common_git_dir: str
    base_ref: str
    base_sha: str
    branch_sha: str
    merge_sha: str
    phase: str
    pid: int

    @property
    def present(self) -> bool:
        return self.path is not None

    @property
    def pid_live(self) -> bool:
        return self.path is not None and _pid_alive(self.pid)


def _read_gate_in_flight(repo: Path) -> GateInFlight:
    """The current gate-in-flight breadcrumb, or an absent sentinel.

    ``#136``: a file that is present but unparseable is a third state
    distinct from absent and genuinely empty, and it is read as "the
    breadcrumb could not be read" rather than collapsed into "no gate".
    A reader that cannot tell those apart reports a dead gate as clean.
    """
    path = repo / GATE_IN_FLIGHT_PATH
    if not path.is_file():
        return GateInFlight(None, "", "", "", "", "", "", "", "", 0)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Unparseable is a fault, not "no gate": a dead gate whose
        # breadcrumb was half-written reads exactly like no gate to a
        # reader that treats parse failure as absence (#136). Surface it
        # as a dead gate so the refusal below names it.
        return GateInFlight(
            path, "<unreadable>", "<unreadable>", "<unreadable>",
            "<unreadable>", "<unreadable>", "<unreadable>",
            "<unreadable>", "<unreadable>", 0,
        )
    try:
        return GateInFlight(
            path,
            str(record.get("branch", "")),
            str(record.get("gate_worktree", "")),
            str(record.get("common_git_dir", "")),
            str(record.get("base_ref", "")),
            str(record.get("base_sha", "")),
            str(record.get("branch_sha", "")),
            str(record.get("merge_sha", "")),
            str(record.get("phase", "")),
            int(record.get("pid", 0)),
        )
    except (TypeError, ValueError):
        return GateInFlight(
            path, "<unreadable>", "<unreadable>", "<unreadable>",
            "<unreadable>", "<unreadable>", "<unreadable>",
            "<unreadable>", "<unreadable>", 0,
        )


def _write_gate_in_flight(
    repo: Path, *, branch: str, gate_worktree: Path, common_git_dir: Path,
    base: str, base_sha: str, branch_sha: str, merge_sha: str, phase: str
) -> None:
    """Write (or update) the gate-in-flight breadcrumb naming this phase.

    Called once after the detach succeeds and again as each gate phase
    begins, so the breadcrumb always names the FURTHEST phase reached. A
    reader finding a dead breadcrumb then knows the gate died at exactly
    ``phase``, not merely "somewhere during the run".
    """
    path = repo / GATE_IN_FLIGHT_PATH
    record = {
        "branch": branch,
        "gate_worktree": str(gate_worktree.resolve()),
        "common_git_dir": str(common_git_dir.resolve()),
        "base_ref": base,
        "base_sha": base_sha,
        "branch_sha": branch_sha,
        "merge_sha": merge_sha,
        "phase": phase,
        "pid": os.getpid(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")


def _clear_gate_in_flight(repo: Path) -> None:
    """Delete the breadcrumb on a clean exit (landing or refusal)."""
    path = repo / GATE_IN_FLIGHT_PATH
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _common_git_dir(repo: Path) -> Path | None:
    value = _git_text(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(value).resolve() if value else None


def _try_lock(common_git_dir: Path, name: str):
    """Acquire one repository-local process mutex without waiting."""
    path = common_git_dir / name
    handle = path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def _registered_worktree_paths(repo: Path) -> tuple[Path, ...] | None:
    result = _git(repo, "worktree", "list", "--porcelain")
    if result.returncode:
        _relay(result)
        return None
    return tuple(
        Path(line.partition(" ")[2]).resolve()
        for line in result.stdout.splitlines()
        if line.startswith("worktree ")
    )


def _cleanup_gate_worktree(repo: Path, gate_worktree: Path) -> str | None:
    """Remove and verify only the exact registered scratch gate worktree."""
    registered = _registered_worktree_paths(repo)
    target = gate_worktree.resolve()
    if registered is None:
        return "could not read git worktree registrations before cleanup"
    if target not in registered:
        return f"recorded gate worktree is not registered: {target}"
    removed = _git(repo, "worktree", "remove", "--force", str(target))
    after = _registered_worktree_paths(repo)
    faults: list[str] = []
    if removed.returncode:
        faults.append(f"git worktree remove exited {removed.returncode}")
    if after is None:
        faults.append("could not read git worktree registrations after cleanup")
    elif target in after:
        faults.append("exact gate worktree remains registered after cleanup")
    if target.exists():
        faults.append("exact gate worktree path remains after cleanup")
    return "; ".join(faults) or None


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

TOOL_EXECUTABLE_DOCS = frozenset({
    ".dreamwork/tasks.md",          # dev/ledger.py store; lint.py reads it
    ".dreamwork/lessons.md",        # dev/lessons_index.py parses its heads
    ".dreamwork/answers.md",        # dev/ledger.py
    ".dreamwork/questions.md",      # dev/ledger.py, dev/check_watch_citations.py
    ".dreamwork/handoffs.md",       # dev/brief.py, dev/check_watch_citations.py
    ".dreamwork/applied.md",        # dev/journal_consume.py, dev/expedite_hook.py
})

# These remain executable documentation for the conservative classifier, but
# the landing gate itself runs the checker that parses them before and after
# its tests. Credit that coverage when deriving whether an injection is owed.
LINT_GATED_EXECUTABLE_DOCS = frozenset({
    ".dreamwork/docs/doc-map.md",   # lint.py check_doc_map_plans parses its rows
})

EXECUTABLE_DOCS = TOOL_EXECUTABLE_DOCS | LINT_GATED_EXECUTABLE_DOCS


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
DERIVATION_RULES: tuple[str, ...] = ("name", "import", "map", "data")


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
# root test whose AST imports it directly OR through one production consumer.
# The second hop is the smallest reach that catches watch.py -> tick_line.py ->
# test_tick_line.py (#991). Deeper closure is deliberately report-only: on the
# measured worst case, watch.py, depth 2 selected 31 files while closure reached
# 44, which is the full-suite run under another name. Accepted cost: a test
# reached only through a second consumer is reported but not selected, while a
# test using importlib or a subprocess has no static edge and is not reached at
# all. A grep over prose would be wider but would drag in unrelated tests.
IMPORT_SELECTION_DEPTH = 2
IMPORT_REPORT_DEPTH = 3


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


def _production_importers(repo: Path, modules: Sequence[str]) -> frozenset[str]:
    """Production modules that statically import any module in ``modules``."""
    wanted = {module for module in modules if module}
    if not wanted:
        return frozenset()
    worktree_roots = _in_repo_worktree_roots(repo)
    found: set[str] = set()
    for source_path in sorted(repo.rglob("*.py")):
        relative = source_path.relative_to(repo)
        if any(relative.is_relative_to(root) for root in worktree_roots):
            continue
        module = _dotted_module(relative.as_posix())
        if module is None or source_path.name.startswith("test_"):
            continue
        try:
            targets = _import_targets(source_path.read_text(encoding="utf-8"))
        except OSError:
            continue
        if any(_targets_import_module(targets, wanted_module)
               for wanted_module in wanted):
            found.add(module)
    return frozenset(found)


def _in_repo_worktree_roots(repo: Path) -> tuple[Path, ...]:
    """Git-registered linked-worktree roots nested below ``repo``."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "worktree", "list", "--porcelain"],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return ()
    if result.returncode:
        return ()
    repo_root = repo.resolve()
    roots: set[Path] = set()
    for line in result.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        try:
            path = Path(line.removeprefix("worktree ")).resolve()
            relative = path.relative_to(repo_root)
        except ValueError:
            continue
        if relative.parts:
            roots.add(relative)
    return tuple(sorted(roots))


def _import_derived(
    repo: Path, modules: Sequence[str], *, depth: int = 1
) -> tuple[str, ...]:
    """Root tests statically importing ``modules`` within ``depth`` hops.

    ``modules`` are dotted module names (from ``_dotted_module``). A test
    is depth 1 when it imports a changed module directly, depth 2 when it
    imports one production consumer of that module, and so on. The visited set
    makes cycles terminate. Root-level ``test_*.py`` only — matching the name
    convention's reach, so the two rules share one documented limit.

    The default remains depth 1 for reporting callers such as ``dev/brief.py``;
    the landing gate opts into ``IMPORT_SELECTION_DEPTH`` explicitly.
    """
    if depth < 1:
        raise ValueError(f"import derivation depth must be >= 1, got {depth}")
    reached = {module for module in modules if module}
    if not reached:
        return ()
    frontier = set(reached)
    for _ in range(depth - 1):
        consumers = set(_production_importers(repo, frontier)) - reached
        if not consumers:
            break
        reached.update(consumers)
        frontier = consumers
    found: set[str] = set()
    for test_path in sorted(repo.glob("test_*.py")):
        if _test_imports_modules(test_path, tuple(reached)):
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
    # The client extraction made client/ a first-class source directory with its
    # own three test modules and never registered them here, so a lane owning
    # ONLY client/ files derived zero tests and could not be dispatched at all --
    # the scope check refused it as "an empty selection is indistinguishable from
    # broken derivation", which was exactly right. Measured green before adding:
    # `just pytest test_client_assets.py test_client_dist.py test_client_env.py`
    # -> `60 passed in 9.88s`, because a mapped target that is absent or red
    # wedges every future landing that touches the directory.
    ("client/", ("test_client_assets.py", "test_client_dist.py", "test_client_env.py")),
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


# (3) DATA-PATH derivation — for the case no file-name, import, or directory-map
# rule can express: a test that consumes a tracked file as DATA, by reading its
# text (``.read_text()``) or loading it dynamically (``importlib`` +
# ``os.path.join``). The relationship is a path expression, not an import, so
# the import graph cannot see it. Two independent master-reds (#1099, #1100)
# landed through honest gates because of this gap, and a third —
# ``dev/journal_consume.py`` → ``test_watch.py`` — survived inside the rule's
# own fix because the path was expressed as ``os.path.join()`` (#1101 r2).
#
# DETECTION is AST-based and covers THREE syntactic forms, each yielding a
# constant path suffix of 2+ components:
#   (a) ``BinOp(Div)``: ``ROOT / "briefs" / "frame.md"`` → ``"briefs/frame.md"``
#   (b) ``os.path.join(root, "dev", "journal_consume.py")`` → trailing constant
#       string args → ``"dev/journal_consume.py"``
#   (c) ``Path("dev/brief.py")``: single string arg with internal slash
# Bare basenames (``"frame.md"``, 1 component) are excluded because they would
# select half the repo on any change to a common filename (#1101's measurement:
# ``watch.py`` alone appears as a bare string constant in 32 test files). The
# 2+-component requirement is what makes the rule precise.
#
# WRITE-EXCLUSION: a path expression used as the receiver of a write operation
# is NOT a data consumer. A test that creates a fixture at
# ``tmp_path / "dev" / "brief.py`` is not reading the real ``dev/brief.py`` —
# it is manufacturing a synthetic one. Without this exclusion the frame.md case
# pulled in ``test_land_lane.py`` as collateral, because its own data-rule
# tests build fixtures via ``(tmp_path / "dev" / "brief.py").write_text(...)``
# (#1101 r2). The exclusion covers EVERY write form a path can take:
#   (a) ``.write_text()`` / ``.write_bytes()`` / ``.mkdir()`` / ``.touch()`` /
#       ``.unlink()`` — method name alone determines write.
#   (b) ``open(path, "w")`` — builtin, positional mode, including ``"w+"``,
#       ``"wb"``, ``"a"``, ``"x"`` (any mode string containing w/a/x).
#   (c) ``open(path, mode="w")`` — builtin, keyword mode (#1101 r4: r2 only
#       handled the positional form).
#   (d) ``(path).open("w")`` / ``(path).open(mode="w")`` — the ``Path.open``
#       method form (#1101 r4: r2 did not detect this at all).
#   (e) ALIASED writes — ``p = <path>; open(p, "w")`` (#1101 r4: r2 missed
#       writes through a name bound to the path expression first).
# A suffix that appears in ANY read context — directly OR through the alias —
# is still included (read wins), including ACROSS files: written in file A and
# read in file B selects B (#1101 r4).
#
# DERIVATION has two shapes. (a) DIRECT: a test references the changed file in a
# read context → derive that test. (b) TWO-HOP: a production file references the
# changed data file → apply the NAME CONVENTION to that production file → derive
# ``test_<stem>.py``. The two-hop is NAME-ONLY (not import): round 1 applied the
# full import graph to intermediates, and a single data file referenced by
# ``lint.py`` dragged in every test that imports lint — 17 tests for
# ``briefs/frame.md``, costing more than the full suite it was meant to be
# cheaper than. The name convention alone reaches the dedicated
# ``test_<consumer>.py``, which is the documented coverage (#1099:
# ``briefs/frame.md`` → ``dev/brief.py`` → ``test_brief.py``).
#
# CANNOT ROT: the reverse index is recomputed from the merged tree on every
# gate run, so a new data dependency is covered the first time it appears. No
# declared table can go stale.
#
# ACCEPTED LIMITATIONS: paths built from runtime variables (``name + ".py"``),
# multi-arg ``Path(parent, child)`` constructors, and writes through custom
# helper functions (``_write(path, ...)``) are not detected. The first two had
# no real occurrences in the measured tree; the third affects one test
# (``test_launch_lane.py``'s fixture creation of ``briefs/frame.md``), which
# remains a low-cost collateral selection. Aliased paths ARE detected (#1101
# r4) — the alias must be a single ``Name`` target of a plain ``Assign`` whose
# value is a recognised path expression.

_WRITE_PATH_METHODS = frozenset({
    "write_text", "write_bytes", "mkdir", "touch", "unlink",
})
# ``open`` mode characters that make a mode string a write: ``"w"``, ``"a"``,
# ``"x"`` — covers ``"w+"``, ``"wb"``, ``"ab"``, ``"xb"``, etc.
_WRITE_MODE_CHARS = frozenset("wax")


def _open_mode_is_write(call: ast.Call, positional_mode_index: int) -> bool:
    """Whether an ``open(...)`` call's mode argument is a write mode.

    Handles BOTH the positional form and the keyword form (``mode="w"``).
    ``positional_mode_index`` is 1 for the builtin ``open(path, "w")`` (path
    is ``args[0]``, mode is ``args[1]``) and 0 for ``Path.open("w")`` (the
    path is the method's object; mode is ``args[0]``). Any mode string
    containing ``w``, ``a``, or ``x`` is a write; ``"r"`` and ``"rb"`` are
    not. An ``open`` with no explicit mode defaults to read.
    """
    if len(call.args) > positional_mode_index:
        mode = call.args[positional_mode_index]
        if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
            return any(c in mode.value for c in _WRITE_MODE_CHARS)
    for kw in call.keywords:
        if (kw.arg == "mode"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)):
            return any(c in kw.value.value for c in _WRITE_MODE_CHARS)
    return False


def _constant_path_suffix(node: ast.AST) -> str | None:
    """The trailing constant path components from a ``BinOp(Div)`` chain.

    ``ROOT / "briefs" / "frame.md"`` → ``"briefs/frame.md"``; a bare
    ``"frame.md"`` → ``"frame.md"``; a ``Name`` → ``None``. When the left
    side is a variable the constant suffix from the right propagates, so
    ``ROOT / "briefs" / "frame.md"`` yields the 2-component suffix while
    ``ROOT / "frame.md"`` yields only the 1-component basename.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _constant_path_suffix(node.left)
        right = _constant_path_suffix(node.right)
        if right is None:
            return None
        if left is None:
            return right
        return f"{left}/{right}"
    return None


def _call_path_suffix(node: ast.Call) -> str | None:
    """Constant path suffix from ``os.path.join(...)`` or ``Path("a/b")``.

    ``os.path.join`` yields the trailing constant string args joined by
    ``/`` (``os.path.join(root, "dev", "brief.py")`` → ``"dev/brief.py"``);
    a non-constant arg terminates the suffix so the variable prefix is
    dropped, matching ``_constant_path_suffix``'s treatment of ``Name``
    in a ``BinOp(Div)`` chain. ``Path("a/b")`` yields its single string
    arg verbatim. Returns ``None`` for any other call shape.
    """
    func = node.func
    if (isinstance(func, ast.Attribute) and func.attr == "join"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "path"
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "os"):
        const_parts: list[str] = []
        for arg in reversed(node.args):
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                const_parts.append(arg.value)
            else:
                break
        const_parts.reverse()
        return "/".join(const_parts) if const_parts else None
    if isinstance(func, ast.Name) and func.id == "Path" and len(node.args) == 1:
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    return None


def _path_expr_suffix(node: ast.AST) -> str | None:
    """Constant path suffix from any recognised path-producing expression.

    Unifies ``BinOp(Div)`` chains, ``os.path.join(...)`` calls, and
    ``Path("a/b")`` calls. The returned suffix may be 1+ components;
    callers enforce the 2+-component match requirement separately.
    """
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _constant_path_suffix(node)
    if isinstance(node, ast.Call):
        return _call_path_suffix(node)
    return None


def _is_write_target(node: ast.AST, parents: dict[int, ast.AST]) -> bool:
    """Whether a path expression is the receiver of a write operation.

    Covers every form a tracked path can be written through (#1101 r4
    closed three gaps that r2 missed):

    * ``(tmp_path / "dev" / "brief.py").write_text(...)`` — the BinOp is
      the ``value`` of an ``Attribute`` whose attr is a write method.
    * ``open(path, "w")`` / ``open(path, mode="w")`` — the builtin, in
      positional AND keyword-mode form (``"w+"``, ``"wb"``, ``"a"``,
      ``"x"`` all detected via ``_open_mode_is_write``).
    * ``(path).open("w")`` / ``(path).open(mode="w")`` — the ``Path.open``
      method form, same mode check against the enclosing Call.
    * Aliased paths — ``p = <path>; open(p, "w")`` — handled by
      ``_data_path_suffixes``'s alias tracking, which calls this on the
      ``Name`` usage.

    A read (``.read_text()``, ``.glob()``, an assignment, or any other
    non-write context) returns ``False``.
    """
    parent = parents.get(id(node))
    if parent is None:
        return False
    if isinstance(parent, ast.Attribute) and parent.value is node:
        if parent.attr in _WRITE_PATH_METHODS:
            return True
        if parent.attr == "open":
            call = parents.get(id(parent))
            if isinstance(call, ast.Call):
                return _open_mode_is_write(call, 0)
        return False
    if (isinstance(parent, ast.Call)
            and isinstance(parent.func, ast.Name)
            and parent.func.id == "open"
            and len(parent.args) >= 1
            and parent.args[0] is node):
        return _open_mode_is_write(parent, 1)
    return False


def _data_path_suffixes(source: str) -> frozenset[str]:
    """Every 2+-component constant path suffix a source references as DATA.

    Three syntactic forms are recognised (see ``_path_expr_suffix``). A
    suffix used only as the receiver of a write operation is EXCLUDED: a
    test that creates a fixture at ``tmp_path / "dev" / "brief.py"`` is
    not a consumer of the real file. A suffix that appears in ANY
    non-write context in the file IS included, even if it also appears in
    a write context elsewhere — the read occurrence is the real
    dependency.

    ALIASED paths (``p = ROOT / "dev" / "brief.py"; open(p, "w")``) are
    tracked: the binding itself is skipped, and the suffix's read/write
    fate is decided by the alias's Load-context USAGES. An alias used only
    in write contexts is excluded; an alias used in ANY read context is
    included (read wins). An alias defined but never loaded counts as a
    read — the binding references the path (``x = ROOT / "dev" / "f.py"``
    with no further use yields the suffix).

    A ``SyntaxError`` returns an empty set.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return frozenset()
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    # Alias map: Name.id -> suffix, for single-target Assign of a path expr.
    # The assigned path-expr node is skipped in the direct scan below — its
    # fate is decided by the alias's usages, not by the binding itself.
    aliases: dict[str, str] = {}
    aliased_value_ids: set[int] = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            suffix = _path_expr_suffix(node.value)
            if suffix is not None and "/" in suffix:
                aliases[node.targets[0].id] = suffix
                aliased_value_ids.add(id(node.value))
    read_suffixes: set[str] = set()
    alias_loaded: set[str] = set()
    for node in ast.walk(tree):
        # Direct path-expr occurrence (skip aliased assignment values).
        if id(node) not in aliased_value_ids:
            suffix = _path_expr_suffix(node)
            if suffix is not None and "/" in suffix:
                if not _is_write_target(node, parents):
                    read_suffixes.add(suffix)
        # Alias usage: a Load-context Name mapped to a known suffix.
        if (isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id in aliases):
            alias_loaded.add(node.id)
            if not _is_write_target(node, parents):
                read_suffixes.add(aliases[node.id])
    # An alias defined but never loaded counts as a read — the binding
    # references the path, matching ``x = ROOT / "dev" / "watch.py"``.
    for name, suffix in aliases.items():
        if name not in alias_loaded:
            read_suffixes.add(suffix)
    return frozenset(read_suffixes)


def _suffix_matches_path(suffix: str, path: str) -> bool:
    """Whether a constant suffix resolves to a tracked ``path``."""
    return path == suffix or path.endswith("/" + suffix)


def _data_consumers(
    repo: Path, changed: Sequence[str]
) -> dict[str, tuple[str, ...]]:
    """For each matchable changed path, which Python files reference it as data.

    Returns ``changed_path → tuple of Python relative paths``. Only changed
    paths with 2+ components are matchable (a single-component changed path
    like ``watch.py`` cannot produce a 2+-component suffix match). Worktree
    roots nested below ``repo`` are excluded.
    """
    matchable = frozenset(p for p in changed if "/" in p)
    if not matchable:
        return {}
    worktree_roots = _in_repo_worktree_roots(repo)
    consumers: dict[str, set[str]] = {p: set() for p in matchable}
    for source_path in sorted(repo.rglob("*.py")):
        relative = source_path.relative_to(repo)
        if any(relative.is_relative_to(root) for root in worktree_roots):
            continue
        try:
            source = source_path.read_text(encoding="utf-8")
        except OSError:
            continue
        suffixes = _data_path_suffixes(source)
        if not suffixes:
            continue
        rel_posix = relative.as_posix()
        for suffix in suffixes:
            for path in matchable:
                if _suffix_matches_path(suffix, path):
                    consumers[path].add(rel_posix)
    return {p: tuple(sorted(v)) for p, v in consumers.items() if v}


def _data_derived(
    repo: Path, changed: Sequence[str]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Apply the data-path rule: return (test targets, matched data paths).

    Test files that reference a changed path as data (in a read context) are
    selected directly. Production files that reference it are treated as
    implicitly changed: the NAME CONVENTION alone is applied to them — not the
    import rule. Round 1 applied the full import graph to intermediates, and a
    single data file referenced by ``lint.py`` dragged in every test that
    imports lint (17 tests for ``briefs/frame.md``). The name convention alone
    reaches the dedicated ``test_<consumer>.py``, which is #1099's documented
    coverage (``briefs/frame.md`` → ``dev/brief.py`` → ``test_brief.py``).
    """
    consumers = _data_consumers(repo, changed)
    if not consumers:
        return (), ()
    matched = tuple(sorted(consumers))
    direct_tests: set[str] = set()
    impl_modules: set[str] = set()
    for py_files in consumers.values():
        for py_file in py_files:
            if py_file.startswith("test_"):
                direct_tests.add(PurePosixPath(py_file).name)
            else:
                module = _dotted_module(py_file)
                if module is not None:
                    impl_modules.add(module)
    indirect_tests: set[str] = set()
    for module in impl_modules:
        stem = module.rsplit(".", 1)[-1]
        test_name = f"test_{stem}.py"
        if (repo / test_name).is_file():
            indirect_tests.add(test_name)
    return tuple(sorted(direct_tests | indirect_tests)), matched


@dataclass(frozen=True)
class DerivationResult:
    """The test-derivation union computed from a diff, per rule.

    Extracted from ``land()`` so that a wiring test can exercise the SAME
    code path the gate uses — not a local re-implementation that would
    pass even if the gate dropped a rule from its union (#1101 r2: the
    round-1 wiring test duplicated the union locally and stayed green
    after ``| set(data_tests)`` was removed from ``land()``).
    """

    derived: tuple[str, ...]
    name: tuple[str, ...]
    imported: tuple[str, ...]
    imported_direct: tuple[str, ...]
    imported_report_only: tuple[str, ...]
    mapped: tuple[str, ...]
    mapped_dirs: tuple[str, ...]
    data: tuple[str, ...]
    data_paths: tuple[str, ...]


def _derive_tests_from_diff(repo: Path, diff: Diff) -> DerivationResult:
    """Run all four derivation rules and return the union plus per-rule breakdown.

    This is the single code path both ``land()`` and the wiring test call.
    Removing any rule from the union here breaks the wiring test, because the
    test asserts membership in ``result.derived`` — not in a locally rebuilt set.
    """
    name_tests = diff.tests
    changed_modules = [
        _dotted_module(p) for p in diff.binding if p.endswith(".py")
    ]
    direct_import_tests = _import_derived(repo, changed_modules, depth=1)
    import_tests = _import_derived(
        repo, changed_modules, depth=IMPORT_SELECTION_DEPTH
    )
    deeper_import_tests = _import_derived(
        repo, changed_modules, depth=IMPORT_REPORT_DEPTH
    )
    import_report_only = tuple(
        sorted(set(deeper_import_tests) - set(import_tests))
    )
    mapped_tests, mapped_dirs = _map_derived(diff.changed)
    data_tests, data_paths = _data_derived(repo, diff.changed)
    derived = tuple(sorted(
        set(name_tests) | set(import_tests) | set(mapped_tests) | set(data_tests)
    ))
    return DerivationResult(
        derived=derived,
        name=name_tests,
        imported=import_tests,
        imported_direct=direct_import_tests,
        imported_report_only=import_report_only,
        mapped=mapped_tests,
        mapped_dirs=mapped_dirs,
        data=data_tests,
        data_paths=data_paths,
    )


def _selected_test_file(selector: str) -> str:
    """The root test filename selected by a pytest path or node id."""
    return PurePosixPath(selector.split("::", 1)[0]).name


def _test_relation_rules(
    repo: Path, selector: str, changed: Sequence[str], *, data_tests: Sequence[str] = ()
) -> tuple[str, ...]:
    """Which derivation rules relate one selected test to the diff."""
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
    if test_file in data_tests:
        rules.append("data")
    return tuple(rules)


def _test_relevance_line(
    repo: Path, selection: Sequence[str], changed: Sequence[str],
    *, data_tests: Sequence[str] = (),
) -> str:
    """Advisory relevance report over the final named-union-derived selection.

    The derivation rules are incomplete, so an unrelated result cannot safely
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
        selector for selector in tests
        if not _test_relation_rules(repo, selector, changed, data_tests=data_tests)
    )
    if not unrelated:
        return (
            f"test-relevance: OK — {prefix}; all {len(tests)} related by at least "
            f"one of the {len(DERIVATION_RULES)} rules"
        )
    return (
        f"test-relevance: WARN — {prefix}; {len(unrelated)} "
        f"unrelated-as-far-as-the-{len(DERIVATION_RULES)}-rules-can-tell: "
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
    def lint_gated_binding(self) -> tuple[str, ...]:
        return tuple(p for p in self.binding if p in LINT_GATED_EXECUTABLE_DOCS)

    @property
    def redproof_binding(self) -> tuple[str, ...]:
        return tuple(p for p in self.binding if p not in LINT_GATED_EXECUTABLE_DOCS)

    @property
    def required_injections(self) -> int:
        return 0 if not self.redproof_binding else 1


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
        if not diff.changed:
            return (
                "red-proof requirement: 0 injections REQUIRED — the diff is "
                "EMPTY; no changed path exists to bind an injection to"
            )
        if diff.lint_gated_binding:
            return (
                "red-proof requirement: 0 injections REQUIRED — "
                f"{len(diff.inert)} inert documentation path(s) need no "
                f"behavioural proof; {len(diff.lint_gated_binding)} executable "
                "documentation binding path(s) are already covered by "
                "lint-precheck and lint-comparison: "
                + " ".join(diff.lint_gated_binding)
            )
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
    if diff.lint_gated_binding:
        return (
            "red-proof requirement: 1 injection required — "
            f"{len(diff.redproof_binding)} of {len(diff.changed)} changed "
            "path(s) still need a behavioural red-proof; red-proof must bind: "
            + " ".join(diff.redproof_binding)
            + f"; {len(diff.lint_gated_binding)} executable documentation "
            "binding path(s) are already covered by lint-precheck and "
            "lint-comparison: "
            + " ".join(diff.lint_gated_binding)
        )
    return (
        f"red-proof requirement: 1 injection required — {len(diff.binding)} of "
        f"{len(diff.changed)} changed path(s) are NOT inert documentation, so a "
        "behavioural red-proof could bind them: " + " ".join(diff.binding)
    )


def _selection_waiver_line(diff: Diff) -> str:
    """State why an empty named-test selection is legitimate (#1018).

    The honest path for a documentation-only branch is a THIRD STATE, not a
    relaxation of the empty-selection refusal (#136): *covered by lint and by
    nothing else* is different from *covered by named tests* and different from
    *coverage unknown*.  An empty selection is allowed ONLY when the entire
    diff is covered — every changed path is inert documentation or a lint-gated
    executable document — so the #1010 guarantee (an empty selection is
    indistinguishable from a broken deriver) survives unchanged for any branch
    that has a single binding path.

    The line names the covering phases, not just the fact, because a branch
    that lands with zero named tests must SAY what checked it (#1140's
    authority-boundary model, #651's guard-must-name-a-detectable-mode rule).
    """
    parts: list[str] = []
    if diff.inert:
        parts.append(
            f"{len(diff.inert)} inert documentation path(s) under "
            f"{INERT_DOC_ROOT} (no executable input)"
        )
    if diff.lint_gated_binding:
        parts.append(
            f"{len(diff.lint_gated_binding)} executable documentation "
            "binding path(s) covered by lint-precheck and lint-comparison"
        )
    return (
        "selection: 0 named tests; the diff is entirely covered — "
        + "; ".join(parts)
        + "; named tests are not required because no changed path is binding"
    )


def _redproof_authority_note(required: int) -> str:
    """State plainly that the gate's DERIVED requirement is the authority and the
    lane's prose report was NOT an input (#1140, #651).

    The gate derives the requirement from the branch diff — the same
    ``_classify_diff`` that ``dev/redproof.py handoff`` calls — and runs
    ``check --require <derived>`` against the lane worktree's registry. What it
    does NOT do is read the lane's prose hand-off: ``.dreamwork/inbox.md`` is
    gitignored and does not travel to the gate worktree (#1131 found no transport
    at either launch-lane or brief-build, and the gate worktree confirms it: the
    only inputs are the branch commits and the lane worktree's filesystem).

    So the gate cannot establish WHICH command produced the lane's quoted number.
    This line says so rather than letting the gate's silence read as a
    verification it did not perform (#651 — a guard whose silence names a failure
    mode it cannot detect). The substantive verification is the registry: a lane
    that did real red-proof work (begin/observe/restore) passes whether or not it
    ran ``handoff``, because the registry reflects the work; a lane that skipped
    red-proof entirely is refused at ``require > 0``. The residual hole is that a
    correct-by-luck prose claim is not caught — but it cannot affect the landing
    decision, because the prose is not an input to it.
    """
    if required == 0:
        return (
            "red-proof authority: 0 injections were REQUIRED (derived from the "
            "branch diff) and dev/redproof.py check confirmed none was owed; "
            "the lane's prose hand-off report was NOT an input to this gate "
            "(it is gitignored and does not travel to the gate worktree), so "
            "the gate cannot establish which command produced the lane's quoted "
            "number"
        )
    return (
        f"red-proof authority: {required} injection(s) were REQUIRED (derived "
        "from the branch diff — not taken from the lane's prose) and "
        "dev/redproof.py check verified the registry against the lane worktree; "
        "the lane's prose hand-off report was NOT an input to this gate (it is "
        "gitignored and does not travel to the gate worktree), so the gate "
        "cannot establish which command produced the lane's quoted number — a "
        "matching integer from a stale paste or from recollection is not "
        "detected by the gate"
    )


def _derived_tests_line(
    diff: Diff,
    *,
    name: Sequence[str],
    imported: Sequence[str],
    imported_direct: Sequence[str],
    imported_report_only: Sequence[str],
    mapped: Sequence[str],
    mapped_dirs: Sequence[str],
    data: Sequence[str],
    data_paths: Sequence[str],
    existing: Sequence[str],
    unnamed: Sequence[str],
    absent: Sequence[str],
) -> str:
    """What derivation reached, per mechanism, and — the #948 failure mode — what it did not.

    "derived 0 required tests" is exactly how #936 hid: eleven failures sat on
    master for two hours because ``lint.py`` changed and ``test_lint.py`` was
    never named. So a zero here says WHY it is zero and what the branch's
    coverage then rests on, rather than reading like a satisfied requirement.

    Four rules now contribute (#953, #1101): the name convention, the import
    graph, a directory→testset map, and a data-path scan. The line names what
    EACH reached, because a
    single total would hide that one of them contributed nothing — and the
    branch whose coverage rests on an empty mechanism is the one this report
    exists to flag. ``absent`` names derived tests the merged tree does not
    hold (a stale map target or a deleted name-derived file): the map case is a
    refusal at the call site, but the name/import cases can only be reported,
    so they appear here rather than reading as satisfied.
    """
    reach = (
        "name reaches root-level `test_<stem>.py` only; import SELECTS root "
        "`test_*.py` that statically import the module or one production "
        "consumer, and REPORTS but does not select the next consumer hop "
        "(not importlib loaders or subprocess calls); map reaches the declared directories in "
        "DIR_TESTSET_MAP only; data reaches tests that reference a changed file "
        "as a 2+-component constant path expression (`ROOT / 'briefs' / 'frame.md'`, "
        "`os.path.join(root, 'dev', 'x.py')`, `Path('dev/x.py')`) in a READ context, "
        "plus tests of production files that do (two-hop: data → name convention only, "
        "not import — import fanout on intermediates was collateral #1101 r2) — "
        "anything else derives NOTHING and is not covered "
        "by this line"
    )
    by_rule = (
        f"name={len(name)} import={len(imported)} map={len(mapped)} data={len(data)}"
        + (f" (matched dirs: {' '.join(mapped_dirs)})" if mapped_dirs else "")
        + (f" (matched data paths: {' '.join(data_paths)})" if data_paths else "")
    )
    import_depth = (
        f"Import depth: {len(imported_direct)} direct; "
        f"{len(set(imported) - set(imported_direct))} added through one consumer; "
        f"depth {IMPORT_REPORT_DEPTH} REPORT ONLY would add "
        f"{len(imported_report_only)}"
        + (
            ": " + " ".join(imported_report_only)
            if imported_report_only else ""
        )
        + "."
    )
    if not existing:
        return (
            f"derived-tests: 0 required tests from {len(diff.changed)} changed "
            f"path(s) — {by_rule}; 0 present in the merged tree. This is NOT "
            f"coverage: the branch rests entirely on the named selection. "
            f"{import_depth} {reach}"
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
        f"{' '.join(existing)}; {added}{missing}. {import_depth} {reach}"
    )


def _run(
    args: Sequence[str],
    repo: Path,
    *,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args), cwd=repo, env=env, input=input_text, capture_output=True, text=True
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


@dataclass(frozen=True)
class SquashResult:
    new_sha: str | None
    tag_ref: str
    differing_paths: tuple[str, ...] = ()
    error: str | None = None


def _squash_commit_tree(lane: Path, branch_sha: str) -> str | None:
    """Return the complete lane tree to put in the squash commit.

    This seam is deliberately separate from verification below: deriving both
    the commit and its check from one answer would let one bad path selection
    make the same omission twice and call itself equal.
    """
    return _git_text(lane, "rev-parse", f"{branch_sha}^{{tree}}")


def _squash_tree_diff(
    lane: Path, preserved_ref: str, squashed_ref: str
) -> tuple[str, ...] | None:
    """Name every tree path changed by a history-only rewrite, or fail closed."""
    result = _git(
        lane,
        "diff",
        "--name-status",
        "--no-renames",
        "--no-ext-diff",
        preserved_ref,
        squashed_ref,
    )
    if result.returncode:
        _relay(result)
        return None
    return tuple(line for line in result.stdout.splitlines() if line)


# #1111: Also-Fixes trailer propagation through --squash. A constituent that
# carries ``Also-Fixes: #NNN`` claims an incidental fix for another task. The
# squash collapses constituents into one commit, so the trailer must be
# propagated into the squashed message — otherwise the claim is lost exactly
# when the motivating case (#1030, named only in a body) needs it most.
_ALSO_FIXES_RE = re.compile(r"^Also-Fixes:\s*(.+)$", re.MULTILINE)
_TRAILER_ID = re.compile(r"#(\d+)")


def _collect_constituent_also_fixes(lane: Path, base_sha: str, tip_sha: str):
    """Deduplicated, sorted Also-Fixes ids from ``base..tip`` commit messages.

    Returns ``None`` on git failure (the caller treats that as no propagation
    rather than blocking the squash). The tip itself is included in the range
    — its own Also-Fixes are already in the preserved message, so the caller
    strips ids already present before appending.
    """
    out = _git(lane, "log", "--format=%B", f"{base_sha}..{tip_sha}")
    if out.returncode:
        return None
    ids: set[int] = set()
    for m in _ALSO_FIXES_RE.finditer(out.stdout):
        for tid_str in _TRAILER_ID.findall(m.group(1)):
            ids.add(int(tid_str))
    return sorted(ids)


def _squash_lane(
    lane: Path, branch: str, base_sha: str, branch_sha: str
) -> SquashResult:
    """Rewrite ``branch`` in place as one commit, preserving and proving its tree.

    The commit is built before the ref moves, from the original tip's complete
    tree. ``update-ref`` then performs the only branch movement atomically. This
    removes the soft-reset/commit interruption window while retaining the
    established in-place result and its durable pre-squash tag.
    """
    tag_ref = f"refs/tags/{branch}-presquash"
    existing = _git(lane, "rev-parse", "--verify", "--quiet", tag_ref)
    if existing.returncode == 0:
        return SquashResult(
            None,
            tag_ref,
            error=(
                f"preservation tag {tag_ref} already exists at {existing.stdout.strip()}; "
                "refusing to replace the only recorded copy of earlier history"
            ),
        )
    if existing.returncode != 1:
        _relay(existing)
        return SquashResult(None, tag_ref, error=f"could not determine whether {tag_ref} exists")

    current_branch = _git_text(lane, "branch", "--show-current")
    lane_head = _git_text(lane, "rev-parse", "HEAD")
    if current_branch != branch or lane_head != branch_sha:
        return SquashResult(
            None,
            tag_ref,
            error=(
                f"lane moved before squash: branch={current_branch or 'DETACHED'} "
                f"HEAD={lane_head or 'UNREADABLE'} expected={branch}@{branch_sha}"
            ),
        )

    tagged = _git(lane, "tag", tag_ref.removeprefix("refs/tags/"), branch_sha)
    if tagged.returncode:
        _relay(tagged)
        return SquashResult(None, tag_ref, error=f"could not create preservation tag {tag_ref}")
    preserved = _git_text(lane, "rev-parse", "--verify", tag_ref)
    if preserved != branch_sha:
        return SquashResult(
            None,
            tag_ref,
            error=f"preservation tag {tag_ref} resolved to {preserved or 'UNREADABLE'}, not {branch_sha}",
        )

    tree = _squash_commit_tree(lane, branch_sha)
    message = _git_text(lane, "log", "-1", "--format=%B", branch_sha)
    if not tree or message is None:
        return SquashResult(None, tag_ref, error="could not read the lane tip tree or commit message")
    message = message.rstrip() + f"\n\nPresquash-Ref: {tag_ref}\n"
    # #1111: propagate Also-Fixes trailers from constituents into the squashed
    # commit, so an incidental-fix claim survives the squash. The tip's OWN
    # Also-Fixes ids are already in the message (they were in the preserved
    # body); only ids from OTHER constituents (and not already in the message)
    # are appended, deduplicated and sorted.
    constituent_ids = _collect_constituent_also_fixes(lane, base_sha, branch_sha)
    if constituent_ids:
        existing = {int(t) for t in _TRAILER_ID.findall(
            "\n".join(_ALSO_FIXES_RE.findall(message)))}
        extra = [tid for tid in constituent_ids if tid not in existing]
        if extra:
            also = ", ".join(f"#{tid}" for tid in extra)
            message = message.rstrip() + f"\nAlso-Fixes: {also}\n"
    built = _run(
        ["git", "commit-tree", tree, "-p", base_sha, "-F", "-"],
        lane,
        input_text=message,
    )
    if built.returncode or not built.stdout.strip():
        _relay(built)
        return SquashResult(None, tag_ref, error="could not build the squashed commit off base")
    new_sha = built.stdout.strip()

    moved = _git(lane, "update-ref", f"refs/heads/{branch}", new_sha, branch_sha)
    if moved.returncode:
        _relay(moved)
        return SquashResult(
            None,
            tag_ref,
            error=f"atomic branch update failed; {branch} remains at its original tip",
        )

    differing = _squash_tree_diff(lane, tag_ref, f"refs/heads/{branch}")
    if differing is None or differing:
        rollback = _git(lane, "update-ref", f"refs/heads/{branch}", branch_sha, new_sha)
        rolled_head = _git_text(lane, "rev-parse", "HEAD")
        rolled_status = _git(lane, "status", "--porcelain=v1", "--untracked-files=no")
        rollback_fault = (
            rollback.returncode
            or rolled_head != branch_sha
            or rolled_status.returncode
            or bool(rolled_status.stdout)
        )
        path_text = ", ".join(differing or ()) if differing is not None else "UNAVAILABLE"
        return SquashResult(
            None,
            tag_ref,
            differing_paths=differing or (),
            error=(
                f"squash tree verification {'could not run' if differing is None else 'found differences'}: "
                f"{path_text}; branch rollback {'FAILED' if rollback_fault else 'restored the original tip'}"
            ),
        )

    final_head = _git_text(lane, "rev-parse", "HEAD")
    final_parent = _git_text(lane, "rev-parse", f"{new_sha}^")
    clean = _git(lane, "status", "--porcelain=v1", "--untracked-files=no")
    if final_head != new_sha or final_parent != base_sha or clean.returncode or clean.stdout:
        return SquashResult(
            None,
            tag_ref,
            error=(
                "post-squash state could not be proved: "
                f"HEAD={final_head or 'UNREADABLE'} parent={final_parent or 'UNREADABLE'} "
                f"tracked-status={len(clean.stdout.splitlines())}"
            ),
        )
    return SquashResult(new_sha, tag_ref)


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


# #1159: lint.py's check_lane_containment emits a WARN whenever ANY registered
# lane worktree is mid-rebase/-merge/-cherry-pick (a detached HEAD transient
# during an instructed rebase). That row is a function of the FLEET's live git
# state, not of the merged tree, so it can appear in one of this gate's two lint
# readings and not the other and false-RED an unrelated branch — #1004's defect
# (a WARN row not a function of the tree breaks the comparison) with a source
# that is worse than wall-clock: another lane's rebase starts and ends at times
# uncorrelated with anything the gated branch does.
#
# The marker below is the phrase the #1116 transient emission hardcodes for ALL
# three operations (rebase/merge/cherry-pick). It does NOT match the perishable
# operation NAME ("mid-rebase"), which would sail straight through a mid-merge or
# mid-cherry-pick worktree. The row's own text announces the protection still
# holds ("its owned paths are still checked from the registered path"), so a row
# that names its own non-hazard is a poor candidate for failing a merge: it is
# printed for awareness and excluded from the comparison, never suppressed.
#
# Blind spot (#1004 — name the class of real change this is now blind to): the
# comparison can no longer detect a lane-containment WARN that carries this
# marker AND is a genuine function of the merged tree. No such row exists today
# — the only lane-containment WARN is this transient observation, and the real
# lane-containment hazard (a lane editing the main checkout's owned paths) is an
# ERROR (#465), caught outside the WARN row-set comparison. The binding is
# guarded by a test that constructs a real mid-rebase worktree and asserts the
# REAL emitted row is excluded (#906), so a rewording of the emission fails loud
# — false RED returns, the safe direction — rather than silently passing.
_LANE_CONTAINMENT_TRANSIENT_MARKER = "detached HEAD is transient"


def _is_fleet_transient_lane_warn(row: str) -> bool:
    """True for a lane-containment WARN observing another worktree's transient
    detached-HEAD state — by construction not a function of the merged tree.

    Keys on the structured WARN identity (the same parser the comparison uses)
    so it never matches a different label's detail, then on the class marker
    that is invariant across all three transient operations.
    """
    identity = _warn_row_identity(row)
    if identity[0] != "warn":
        return False
    label = identity[1] if len(identity) > 1 else ""
    detail = identity[2] if len(identity) > 2 else ""
    return label == "lane-containment" and _LANE_CONTAINMENT_TRANSIENT_MARKER in detail


def _partition_warn_rows(
    rows: Sequence[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split WARN rows into ``(compared, excluded_fleet_transient)``.

    Excluded rows are lane-containment WARNs observing another worktree's
    transient detached-HEAD state — not functions of the merged tree, so
    comparing them across the gate's two readings false-REDs unrelated branches
    (#1159/#1004). They are still printed (``_print_rows`` already showed the
    full population); only the fail-decision excludes them.
    """
    compared = tuple(r for r in rows if not _is_fleet_transient_lane_warn(r))
    excluded = tuple(r for r in rows if _is_fleet_transient_lane_warn(r))
    return compared, excluded


def _declared_warn_index(
    rows: Sequence[str],
) -> tuple[dict[tuple[str, ...], str], str | None]:
    """Normalise coordinator-declared WARN rows to an identity→row index.

    A declared row is the WARN line exactly as ``lint.py`` prints it
    (``"  WARN  detail"``). The coordinator copies it from the gate's own
    ``+ row`` / ``- row`` diff output, so a leading ``"+ "`` or ``"- "`` prefix
    is tolerated and stripped before normalisation. Identity is then derived by
    the same ``_warn_row_index`` the gate uses on the observed rows, so label
    padding never reads as a change (#794).

    Returns ``(index, None)`` on success or ``(empty, fault)`` on one of two
    distinct faults (#136 — nothing declared, nothing changed, the declaration
    could not be read must stay distinct):

    - **unreadable**: a cleaned row does not even parse as a WARN row — it
      could not name a real observed row. Validity is bound to ``WARN_ROW``,
      the *same* filter ``_warn_rows`` applies to the observed lint output, so
      a declaration is valid exactly when it could name a real row: a row with
      no structured separator (``"  WARN  detail"``) is still a valid WARN row,
      while a typo (``"not a WARN row"``) is not. The fault names the offending
      token, so a typo is caught as unreadable rather than silently authorising
      nothing and reporting as a mismatch (#1040).
    - **ambiguous**: two declared rows of different text collapse to one
      identity, which the gate cannot adjudicate.

    A valid declaration that simply names a row the merge did not observe is NOT
    unreadable — it is a mismatch, reported by the caller after the merge. The
    presence of a declaration never reads as its correctness (#994); only an
    exact identity-set match does.
    """
    cleaned: list[str] = []
    for row in rows:
        cleaned.append(row[2:] if row[:2] in ("+ ", "- ") else row)
    unreadable = [row for row in cleaned if not WARN_ROW.match(row)]
    if unreadable:
        return {}, (
            f"coordinator WARN declaration could not be read: "
            f"{unreadable[0]!r} is not a WARN row"
        )
    try:
        return _warn_row_index(cleaned), None
    except ValueError as exc:
        return {}, f"coordinator WARN declaration is ambiguous: {exc}"


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
        print(f"RECOVERY FAILED: {alert}", file=sys.stderr)
    print(f"examined: {examined}", file=sys.stderr)
    print(f"base: {base_state}", file=sys.stderr)
    print(f"retained: {retained}", file=sys.stderr)
    print("deliberately did not perform: dev/reap.py lane retirement", file=sys.stderr)
    return 1


def _refuse_dead_gate(repo: Path, crumb: GateInFlight, base: str) -> int:
    """Refuse on a live gate, or recover one exact dead scratch gate."""
    path_text = str(crumb.path) if crumb.path else "<none>"
    pid_state = "LIVE" if crumb.pid_live else "DEAD"
    print(
        f"gate-in-flight: {pid_state} breadcrumb at {path_text} "
        f"(branch={crumb.branch}; scratch={crumb.gate_worktree}; merge={crumb.merge_sha}; "
        f"phase={crumb.phase}; pid={crumb.pid})",
        file=sys.stderr,
    )
    recovery = "not attempted while the recorded pid is live"
    retained = (
        f"branch={crumb.branch}; gate-worktree={crumb.gate_worktree}; "
        f"gate-breadcrumb={path_text}"
    )
    if not crumb.pid_live:
        common = _common_git_dir(repo)
        fields_valid = all(
            value and value != "<unreadable>"
            for value in (
                crumb.gate_worktree, crumb.common_git_dir, crumb.base_ref,
                crumb.base_sha, crumb.branch_sha,
            )
        )
        if not fields_valid or common is None:
            recovery = "not attempted because the breadcrumb schema or common git directory is unreadable"
        elif Path(crumb.common_git_dir).resolve() != common:
            recovery = (
                "not attempted because recorded common_git_dir does not match this repository: "
                f"recorded={crumb.common_git_dir}; actual={common}"
            )
        else:
            target = Path(crumb.gate_worktree).resolve()
            target_common = _common_git_dir(target) if target.is_dir() else None
            target_branch = _git_text(target, "branch", "--show-current") if target.is_dir() else None
            target_head = _git_text(target, "rev-parse", "HEAD") if target.is_dir() else None
            identity_faults: list[str] = []
            if not target.name.startswith(".gate-"):
                identity_faults.append("recorded path does not have the gate-scratch name prefix")
            if target_common != common:
                identity_faults.append("recorded path does not belong to the recorded common Git directory")
            if target_branch != "":
                identity_faults.append(
                    f"recorded path is not detached (branch={target_branch or 'UNREADABLE'})"
                )
            if re.fullmatch(r"[0-9a-f]{40}", crumb.merge_sha) and target_head != crumb.merge_sha:
                identity_faults.append(
                    f"recorded merge {crumb.merge_sha} does not match scratch HEAD {target_head or 'UNREADABLE'}"
                )
            if identity_faults:
                recovery = "not attempted and breadcrumb retained: " + "; ".join(identity_faults)
            else:
                cleanup_fault = _cleanup_gate_worktree(repo, target)
                if cleanup_fault is None:
                    _clear_gate_in_flight(repo)
                    current_base = _git_text(repo, "rev-parse", "--verify", f"refs/heads/{crumb.base_ref}")
                    base_fact = (
                        f"{crumb.base_ref} still={crumb.base_sha}"
                        if current_base == crumb.base_sha
                        else f"{crumb.base_ref} moved to {current_base or 'UNREADABLE'} from {crumb.base_sha}"
                    )
                    recovery = (
                        f"removed exact registered gate worktree {target}, verified registration/path absent, "
                        f"then cleared {path_text}; {base_fact}"
                    )
                    retained = f"branch={crumb.branch}; recovered-gate-worktree={target}; breadcrumb=cleared"
                else:
                    recovery = f"FAILED and breadcrumb retained: {cleanup_fault}"
    return _refuse(
        "gate-in-flight",
        f"a previous land_lane left a {pid_state} scratch-gate breadcrumb",
        f"breadcrumb={path_text}; branch={crumb.branch}; gate_worktree={crumb.gate_worktree}; "
        f"base_ref={crumb.base_ref}; base_sha={crumb.base_sha}; branch_sha={crumb.branch_sha}; "
        f"merge_sha={crumb.merge_sha}; "
        f"phase_reached={crumb.phase}; pid={crumb.pid} ({pid_state}); "
        f"recovery: {recovery}",
        retained,
        base_state=_base_state(repo, base, None),
    )


class LintOutcome(Enum):
    CLEAN = "clean"
    LINT_FAILED = "lint-failed"
    REPORT_INVALID = "report-invalid"
    REPOSITORY_UNREADABLE = "repository-unreadable"


@dataclass(frozen=True)
class LintReading:
    process: subprocess.CompletedProcess[str]
    outcome: LintOutcome
    rows: tuple[str, ...] | None
    repository_probe: subprocess.CompletedProcess[str] | None = None


def _command_output(result: subprocess.CompletedProcess[str], limit: int = 2000) -> str:
    """A bounded, single-line account of what a failed command printed."""
    output = (result.stdout + result.stderr).strip().replace("\n", " | ")
    if not output:
        return "<no output>"
    if len(output) > limit:
        return "..." + output[-limit:]
    return output


def _lint_refusal(reading: LintReading, phase: str, label: str) -> tuple[str, str]:
    """Stable refusal identity plus evidence for each non-clean lint outcome."""
    refusal_phase = f"{phase}/{reading.outcome.value}"
    lint_output = _command_output(reading.process)
    if reading.outcome is LintOutcome.REPOSITORY_UNREADABLE:
        assert reading.repository_probe is not None
        reason = (
            f"repository-readability probe exited {reading.repository_probe.returncode}; "
            f"lint exit={reading.process.returncode}; lint output: {lint_output}; "
            f"git probe output: {_command_output(reading.repository_probe)}"
        )
    elif reading.outcome is LintOutcome.LINT_FAILED:
        reason = (
            f"lint exited {reading.process.returncode}; lint output: {lint_output}"
        )
    else:
        reason = (
            f"lint exited 0 but {label} WARN rows had no valid clean trailer; "
            f"lint output: {lint_output}"
        )
    return refusal_phase, reason


def _lint(repo: Path) -> LintReading:
    result = _run([sys.executable, "lint.py"], repo)
    _relay(result)
    combined = result.stdout + result.stderr
    trailer = LINT_TRAILER.search(combined)
    rows = _warn_rows(combined)
    if not result.returncode and trailer is not None and int(trailer.group(1)) == len(rows):
        return LintReading(result, LintOutcome.CLEAN, rows)

    # This is a separate checked Git reading, not an interpretation of lint's
    # output.  Force Git's diff machinery to materialise HEAD's patch (`-m`
    # includes both sides of the provisional merge), so a clean index cannot
    # short-circuit before reading the changed blob that exposed #1133's
    # unusable-but-verifier-clean multi-pack-index.
    repository_probe = _git(
        repo,
        "show",
        "-m",
        "--format=",
        "--no-ext-diff",
        "--no-renames",
        "--binary",
        "HEAD",
    )
    if repository_probe.returncode:
        outcome = LintOutcome.REPOSITORY_UNREADABLE
    elif result.returncode:
        outcome = LintOutcome.LINT_FAILED
    else:
        outcome = LintOutcome.REPORT_INVALID
    return LintReading(result, outcome, None, repository_probe)


def land(
    branch: str,
    tests: Sequence[str],
    *,
    base: str = "master",
    squash: bool = False,
    expect_warn_add: Sequence[str] = (),
    expect_warn_remove: Sequence[str] = (),
) -> int:
    invoked = Path.cwd().resolve()
    retained = f"branch={branch}; worktree=not-yet-resolved"
    repo_claim = _git(invoked, "rev-parse", "--show-toplevel")
    repo_text = repo_claim.stdout.strip()
    repo = Path(repo_text).resolve() if not repo_claim.returncode and repo_text else None
    if repo is None or (invoked != repo and repo not in invoked.parents):
        resolved = str(repo) if repo is not None else "UNRESOLVED"
        reason = (
            "Git resolved the invocation outside its worktree"
            if repo is not None else
            "Git could not resolve a worktree containing the invocation"
        )
        return _refuse(
            "preflight",
            reason,
            f"invoked={invoked}; resolved={resolved}; git-exit={repo_claim.returncode}; "
            "property=the invocation must equal or descend from Git's resolved worktree; "
            "possible causes: shared .git/config core.worktree or GIT_WORK_TREE, "
            "or rewritten .git indirection; remedy: inspect with "
            "`git config --show-origin --get core.worktree`; if set, run "
            "`git config --local --unset core.worktree`",
            retained,
            base_state="UNTRUSTED (repository identity was not established)",
        )

    common_git_dir = _common_git_dir(repo)
    if common_git_dir is None:
        return _refuse(
            "preflight", "could not resolve the repository common git directory",
            f"repo={repo}", retained, base_state=_base_state(repo, base, None),
        )
    # Held by this frame until land() returns. This is the whole-run gate
    # mutex: moving the provisional workspace does not make master multiwriter.
    gate_lock = _try_lock(common_git_dir, "dreamwork-gate.lock")
    if gate_lock is None:
        return _refuse(
            "gate-mutex", "another landing gate owns the whole-run mutex",
            f"lock={common_git_dir / 'dreamwork-gate.lock'}", retained,
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
    # #1120/#1128: a dead breadcrumb names an exact registered scratch to
    # recover; a live one means another land_lane is running right now.
    existing_crumb = _read_gate_in_flight(repo)
    if existing_crumb.present:
        return _refuse_dead_gate(repo, existing_crumb, base)
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

    # #1018: classify the diff early so the selection check is diff-aware.
    # A documentation-only branch has no test to name — the empty selection is
    # correct, not broken (#136's third state).  An empty selection on a branch
    # that HAS binding paths still refuses unchanged (#1010: an empty selection
    # is indistinguishable from a broken deriver).  The diff is reused later
    # for the red-proof requirement derivation, so it is computed once here.
    diff = _classify_diff(repo, base_sha, branch_sha)
    if not tests:
        if diff is None:
            return _refuse(
                "selection",
                "named test selection is empty and the diff could not be read "
                "to check whether any path is binding",
                f"branch argument={branch}; named tests=0; "
                f"base={base_sha}; branch_sha={branch_sha}",
                retained,
                base_state=_base_state(repo, base, base_sha),
            )
        if not diff.changed:
            return _refuse(
                "selection",
                "named test selection is empty and the diff is empty",
                f"branch argument={branch}; named tests=0; changed paths=0",
                retained,
                base_state=_base_state(repo, base, base_sha),
            )
        if diff.required_injections > 0:
            return _refuse(
                "selection",
                "named test selection is empty",
                f"branch argument={branch}; named tests=0; "
                f"{len(diff.binding)} binding path(s)={list(diff.binding)!r}",
                retained,
                base_state=_base_state(repo, base, base_sha),
            )
        print(_selection_waiver_line(diff))

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

    gate_worktree = (
        repo.parent / ".worktrees" /
        f".gate-{os.getpid()}-{base_sha[:12]}"
    ).resolve()
    _write_gate_in_flight(
        repo, branch=branch, gate_worktree=gate_worktree,
        common_git_dir=common_git_dir, base=base, base_sha=base_sha,
        branch_sha=branch_sha, merge_sha="<pre-merge>",
        phase="worktree-creation",
    )
    state_lock = _try_lock(common_git_dir, "dreamwork-repo-state.lock")
    if state_lock is None:
        _clear_gate_in_flight(repo)
        return _refuse(
            "worktree-creation", "repository-state mutex is busy",
            f"lock={common_git_dir / 'dreamwork-repo-state.lock'}; base={base_sha}",
            retained, base_state=_base_state(repo, base, base_sha),
        )
    added = _git(repo, "worktree", "add", "--detach", str(gate_worktree), base_sha)
    state_lock.close()
    registered = _registered_worktree_paths(repo)
    scratch_head = _git_text(gate_worktree, "rev-parse", "HEAD") if gate_worktree.is_dir() else None
    main_branch = _git_text(repo, "branch", "--show-current")
    main_head = _git_text(repo, "rev-parse", "HEAD")
    if (
        added.returncode
        or registered is None
        or gate_worktree not in registered
        or scratch_head != base_sha
        or main_branch != base
        or main_head != base_sha
    ):
        _relay(added)
        cleanup_fault = None
        if registered is not None and gate_worktree in registered:
            cleanup_fault = _cleanup_gate_worktree(repo, gate_worktree)
        if cleanup_fault is None:
            _clear_gate_in_flight(repo)
        return _refuse(
            "worktree-creation",
            "could not create and prove an exact-base detached scratch worktree",
            f"add-exit={added.returncode}; scratch={gate_worktree}; "
            f"scratch-head={scratch_head or 'UNREADABLE'}; expected={base_sha}; "
            f"main-branch={main_branch or 'DETACHED'}; main-head={main_head or 'UNREADABLE'}; "
            f"cleanup={cleanup_fault or 'verified'}",
            retained, base_state=_base_state(repo, base, base_sha),
            alert=cleanup_fault,
        )
    print(
        f"gate-worktree: registered detached scratch={gate_worktree} "
        f"at exact base={base_sha}; main remains {base}@{main_head}"
    )
    _write_gate_in_flight(
        repo, branch=branch, gate_worktree=gate_worktree,
        common_git_dir=common_git_dir, base=base, base_sha=base_sha,
        branch_sha=branch_sha, merge_sha="<pre-merge>", phase="lint-baseline",
    )

    _prev_sig: dict[str, signal.Handlers] = {}

    def _gate_signal_handler(signum: int, frame: object) -> None:
        # Leave the exact scratch registration and breadcrumb discoverable.
        # SIGKILL cannot run this handler; it leaves the same durable shape.
        raise SystemExit(
            f"land_lane interrupted by signal {signum}; main stayed on {base}; "
            f"scratch retained at {gate_worktree}"
        )

    def _install_gate_signals() -> None:
        _prev_sig["SIGTERM"] = signal.signal(signal.SIGTERM, _gate_signal_handler)
        _prev_sig["SIGINT"] = signal.signal(signal.SIGINT, _gate_signal_handler)

    def _restore_gate_signals() -> None:
        for name in ("SIGTERM", "SIGINT"):
            if name in _prev_sig:
                signal.signal(getattr(signal, name), _prev_sig[name])
                del _prev_sig[name]

    _install_gate_signals()

    merged_sha = "not-created"

    def update_gate_breadcrumb(phase: str, merge_sha: str = "<pre-merge>") -> None:
        _write_gate_in_flight(
            repo, branch=branch, gate_worktree=gate_worktree,
            common_git_dir=common_git_dir, base=base, base_sha=base_sha,
            branch_sha=branch_sha, merge_sha=merge_sha, phase=phase,
        )

    def refuse_gated(phase: str, reason: str, examined: str) -> int:
        """Clean the exact scratch before clearing its breadcrumb."""
        cleanup_fault = _cleanup_gate_worktree(repo, gate_worktree)
        if cleanup_fault is None:
            _clear_gate_in_flight(repo)
        _restore_gate_signals()
        return _refuse(
            phase, reason, examined, retained,
            base_state=_base_state(repo, base, base_sha),
            alert=(
                None if cleanup_fault is None else
                f"{cleanup_fault}; breadcrumb and exact scratch retained at {gate_worktree}"
            ),
        )

    baseline_reading = _lint(gate_worktree)
    baseline = baseline_reading.rows
    if baseline is None:
        refusal_phase, reason = _lint_refusal(
            baseline_reading, "lint-baseline", "baseline"
        )
        return refuse_gated(
            refusal_phase,
            reason,
            f"lint.py in {gate_worktree}; base={base_sha}; branch={branch_sha}",
        )
    _print_rows("baseline", baseline)
    if not baseline:
        return refuse_gated(
            "lint-baseline",
            "WARN baseline population is empty; zero rows examined is not a comparison",
            f"lint.py in {gate_worktree}; base={base_sha}; branch={branch_sha}; baseline=0 rows examined",
        )

    # Coordinator authorisation for an intended WARN row-set change (#1040).
    # The coordinator is the single writer of the lint baseline, so the
    # declaration arrives by the one channel the lane cannot forge: the gate
    # invocation itself. The declared rows are normalised by _declared_warn_index
    # (which also tolerates a leading "+ "/"- " prefix the coordinator copies
    # from the gate's own diff output), so padding differences do not read as a
    # mismatch. A declaration is validated here — before the merge — so an
    # ambiguous declaration (two rows sharing one identity) refuses early
    # instead of spending the lane's budget.
    declared_added_index, add_fault = _declared_warn_index(expect_warn_add)
    declared_removed_index, remove_fault = _declared_warn_index(expect_warn_remove)
    if add_fault or remove_fault:
        return refuse_gated(
            "lint-baseline",
            add_fault or remove_fault,
            f"declared_add={len(expect_warn_add)}; declared_remove={len(expect_warn_remove)}",
        )
    declared_added_ids = set(declared_added_index)
    declared_removed_ids = set(declared_removed_index)

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
        return refuse_gated(
            "red-proof-history",
            "could not count the branch commits the red-proof scan must examine",
            f"base={base_sha}; branch={branch_sha}; rev-list exit={branch_commits.returncode}",
        )

    # diff was computed early (before the selection check, #1018) and is reused
    # here; no re-computation is needed because base_sha and branch_sha are
    # stable refs and nothing between the two points commits.
    if diff is None:
        return refuse_gated(
            "diff-classification",
            "could not read the branch diff, so neither the red-proof requirement "
            "nor the required tests could be derived from it",
            f"base={base_sha}; branch={branch_sha}",
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
    def run_redproof() -> subprocess.CompletedProcess[str]:
        return _run(
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
            gate_worktree,
            env=redproof_env,
        )

    redproof = run_redproof()
    did_squash = False
    history_refusal = (
        redproof.returncode == 1
        and "commit(s) on this branch still hold a recorded injection"
        in redproof.stderr
    )
    if squash and (redproof.returncode == 0 or history_refusal):
        cause = "history held a recorded injection (#710)" if history_refusal else "explicit --squash request"
        print(f"squash cause: {cause}; pre-squash red-proof audit follows")
        _relay(redproof)
        original_sha = branch_sha
        squashed = _squash_lane(lane, branch, base_sha, original_sha)
        if squashed.error or not squashed.new_sha:
            differing = (
                "; differing paths=" + ", ".join(squashed.differing_paths)
                if squashed.differing_paths
                else ""
            )
            return refuse_gated(
                "squash-verification",
                squashed.error or "squash produced no commit",
                f"original={original_sha}; preserved={squashed.tag_ref}{differing}",
            )
        branch_sha = squashed.new_sha
        did_squash = True
        print(
            f"squash: rewrote {branch} in place {original_sha} -> {branch_sha}; "
            f"preserved original history at {squashed.tag_ref}"
        )
        print(
            "squash-verification: PASS — git diff --name-status "
            f"{squashed.tag_ref} refs/heads/{branch} examined the complete trees and found 0 differing paths"
        )
        branch_commits = _git(repo, "rev-list", "--count", f"{base_sha}..{branch_sha}")
        try:
            commits_examined = int(branch_commits.stdout.strip())
        except ValueError:
            commits_examined = -1
        if branch_commits.returncode or commits_examined < 0:
            _relay(branch_commits)
            return refuse_gated(
                "red-proof-history",
                "could not count the squashed branch commits the red-proof scan must examine",
                f"base={base_sha}; branch={branch_sha}; rev-list exit={branch_commits.returncode}",
            )
        redproof = run_redproof()
    else:
        _relay(redproof)

    if did_squash:
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
        #
        # #1038: the note must be CAUSE-AWARE. Exit 2 at --require 0 no longer
        # means "no registry found" (that case exits 0 now) — it means the
        # registry could not be read (permissions) or parsed (malformed JSON),
        # or some other audit fault. The old note asserted "can locate no
        # registry" / "#949" for every exit-2-at-require-0 cause, which is
        # false for the unreadable case (#1038 Finding 1): it sends the
        # operator looking for a missing file when the cause is a permission
        # bit. Round 3 fixed "absent" → "exists," which moved the overclaim one
        # notch: "exists" is equally false when the file is not there. #136's
        # three states are absent / present / could-not-determine, and the note
        # must say the third — "not confirmed" — rather than picking one.
        # Derive the cause from redproof's own stderr so the note can never
        # assert something the audit did not report.
        #
        # The cause→note coupling is a PROSE protocol (#1038 P2): land_lane
        # matches substrings of redproof's stderr. A wording rename in
        # redproof silently degrades to the generic cause. The protection is
        # test_land_lane.py::test_unreadable_registry_at_require_zero_names_its_cause_not_absence,
        # which asserts "permission issue" in the refuse line — that clause
        # lives ONLY in the cause-aware branch, so a broken match fails the
        # test. This is named here so the coupling is explicit, not incidental.
        note = ""
        if required == 0 and redproof.returncode == 2:
            fault = redproof.stderr
            if "could not be read" in fault:
                cause = (
                    "the registry could not be read — its existence is not "
                    "confirmed (it may be present but unreachable, or absent "
                    "under an unreadable parent); likely a permission issue "
                    "(e.g. a chmod 000 parent dir)")
            elif "present but unparseable" in fault:
                cause = (
                    "the registry is present but malformed JSON — inspect "
                    "and repair it")
            else:
                cause = (
                    "see dev/redproof.py's output above for the specific "
                    "cause")
            note = (
                "; NOTE this FAULT is NOT the --require rule: 0 injections "
                "were owed, and dev/redproof.py faulted during its own "
                f"audit because {cause}, not because a required injection "
                "is missing")
        return refuse_gated(
            "red-proof-history",
            f"dev/redproof.py check refused or faulted with exit {redproof.returncode}"
            + note,
            population,
        )
    if commits_examined == 0:
        return refuse_gated(
            "red-proof-history",
            "EXAMINED NO COMMIT; an empty history range is not an all-clear",
            population,
        )
    if audited_lane_head != branch_sha or audited_branch_sha != branch_sha:
        return refuse_gated(
            "red-proof-history",
            "branch tip moved while its red-proof history was being audited",
            population
            + f"; preflight tip={branch_sha}; branch now={audited_branch_sha or 'UNREADABLE'}",
        )
    print(f"red-proof-history: PASS; {population}")
    # State plainly what the red-proof gate DID and DID NOT verify, so its
    # silence does not read as a prose verification it never performed (#651).
    # The requirement is derived from the diff (the same _classify_diff handoff
    # uses) and checked against the registry; the lane's prose is not an input.
    print(_redproof_authority_note(required))
    passed.append("red-proof-history")

    update_gate_breadcrumb("provisional-merge")
    merge = _git(gate_worktree, "merge", "--no-ff", branch_sha, "-m", f"Merge {branch}")
    _relay(merge)
    if merge.returncode:
        _git(gate_worktree, "merge", "--abort")
        return refuse_gated(
            "merge",
            f"git merge --no-ff exited {merge.returncode}",
            f"base={base_sha}; branch={branch_sha}; worktree={lane}",
        )
    merged_sha = _git_text(gate_worktree, "rev-parse", "HEAD") or "UNKNOWN"
    update_gate_breadcrumb("merge-identity", merged_sha)

    # The gates below examine whatever HEAD is; prove it is the merge of the
    # two shas preflight read, so no gate can pass against the branch tree, a
    # stale merge, or a base that moved. The parents come from git, which the
    # tree under test cannot rewrite.
    parents = (
        _git_text(gate_worktree, "rev-list", "--parents", "-n", "1", "HEAD") or ""
    ).split()[1:]
    if parents != [base_sha, branch_sha]:
        return refuse_gated(
            "merge-identity",
            "HEAD is not the merge of the examined base and branch, so no gate below would judge it",
            f"merge={merged_sha}; parents={parents!r}; expected=[{base_sha!r}, {branch_sha!r}]",
        )
    print(f"merge-identity: {merged_sha} has parents {base}@{base_sha} and {branch}@{branch_sha}")

    def compare_lint(phase: str, reading: str) -> int | None:
        """Compare one merged-tree lint reading with the pre-merge baseline."""
        lint_reading = _lint(gate_worktree)
        after = lint_reading.rows
        if after is None:
            refusal_phase, reason = _lint_refusal(lint_reading, phase, reading)
            return refuse_gated(
                refusal_phase,
                reason,
                f"merge={merged_sha}; baseline rows={len(baseline)}",
            )
        _print_rows(reading, after)
        if not after:
            return refuse_gated(
                phase,
                f"{reading} WARN population is empty; zero rows examined is not a match",
                f"merge={merged_sha}; baseline={len(baseline)} rows; {reading}=0 rows examined",
            )
        # #1159: partition out fleet-transient lane-containment WARNs before
        # comparing — they are functions of the live fleet (another lane's
        # mid-rebase), not of the merged tree, so a foreign lane's instructed
        # rebase must not false-RED the branch under test. The full population
        # each reading examined is still reported above; the split below states
        # BOTH denominators so an authorised pass is never silent (#868).
        baseline_compared, baseline_excluded = _partition_warn_rows(baseline)
        after_compared, after_excluded = _partition_warn_rows(after)
        try:
            baseline_index = _warn_row_index(baseline_compared)
            after_index = _warn_row_index(after_compared)
        except ValueError as exc:
            return refuse_gated(
                phase,
                f"WARN identity normalisation is ambiguous: {exc}",
                f"merge={merged_sha}; baseline={len(baseline)} rows; {reading}={len(after)} rows",
            )
        added_ids = set(after_index) - set(baseline_index)
        removed_ids = set(baseline_index) - set(after_index)
        added = tuple(sorted(after_index[identity] for identity in added_ids))
        removed = tuple(sorted(baseline_index[identity] for identity in removed_ids))
        print(f"{phase} WARN row-set comparison: added={len(added)} removed={len(removed)}")
        print(f"lint WARN populations: baseline={len(baseline)} rows; {reading}={len(after)} rows")
        excluded_total = len(baseline_excluded) + len(after_excluded)
        if excluded_total:
            # #868: a pass that excluded rows must say how many and why, not
            # silently compare a smaller set — "row present" must not collapse
            # "this branch introduced it" with "another worktree was detached".
            print(
                f"{phase} excluded {excluded_total} fleet-transient lane-containment "
                f"WARN row(s) from the comparison — not functions of the merged tree, "
                f"so a foreign lane's mid-rebase cannot false-RED the branch under test "
                f"(#1159): baseline={len(baseline_excluded)} {reading}={len(after_excluded)}"
            )
            for row in baseline_excluded:
                print(f"~ (baseline excluded, #1159) {row}")
            for row in after_excluded:
                print(f"~ ({reading} excluded, #1159) {row}")
        for row in added:
            print(f"+ {row}")
        for row in removed:
            print(f"- {row}")

        # #1040: a coordinator may authorise an intended WARN row-set change by
        # declaring the exact added and removed rows. When a declaration is
        # present the observed sets must match the declared sets EXACTLY — set
        # equality, both directions, for added and removed separately. An exact
        # match passes (with denominators reported); anything else refuses. The
        # default with no declaration is unchanged behaviour: any change refuses.
        if declared_added_ids or declared_removed_ids:
            added_match = added_ids == declared_added_ids
            removed_match = removed_ids == declared_removed_ids
            added_matched = added_ids & declared_added_ids
            removed_matched = removed_ids & declared_removed_ids
            overdeclared_added = sorted(declared_added_ids - added_ids)
            undeclared_added = sorted(added_ids - declared_added_ids)
            overdeclared_removed = sorted(declared_removed_ids - removed_ids)
            undeclared_removed = sorted(removed_ids - declared_removed_ids)
            print(
                f"{phase} WARN authorisation: "
                f"declared_added={len(declared_added_ids)} observed_added={len(added_ids)} "
                f"matched_added={len(added_matched)}; "
                f"declared_removed={len(declared_removed_ids)} observed_removed={len(removed_ids)} "
                f"matched_removed={len(removed_matched)}"
            )
            if added_match and removed_match:
                # An authorised pass is never silent (#136/#868): the
                # denominators above distinguish it from a zero-change pass.
                return None
            mismatch: list[str] = []
            if undeclared_added:
                mismatch.append(
                    f"{len(undeclared_added)} added row(s) not declared"
                )
            if overdeclared_added:
                mismatch.append(
                    f"{len(overdeclared_added)} declared-added row(s) not observed"
                )
            if undeclared_removed:
                mismatch.append(
                    f"{len(undeclared_removed)} removed row(s) not declared"
                )
            if overdeclared_removed:
                mismatch.append(
                    f"{len(overdeclared_removed)} declared-removed row(s) not observed"
                )
            return refuse_gated(
                phase,
                "WARN row-set change does not match the coordinator declaration exactly",
                f"merge={merged_sha}; baseline={len(baseline)} rows; {reading}={len(after)} rows; "
                f"{'; '.join(mismatch)}",
            )
        if added or removed:
            return refuse_gated(
                phase,
                "WARN row set changed from the pre-merge baseline",
                f"merge={merged_sha}; baseline={len(baseline)} rows; {reading}={len(after)} rows",
            )
        return None

    # This is deliberately a pre-check, not a move of the authoritative
    # comparison below. Named tests are arbitrary repo code and can refresh a
    # live or derived artifact that lint.py reads; only the post-gate reading
    # can catch a WARN introduced by that refresh. The cheap duplicate closes
    # the common case before either pytest invocation spends the lane's budget.
    update_gate_breadcrumb("lint-precheck", merged_sha)
    lint_precheck = compare_lint("lint-precheck", "post-merge precheck")
    if lint_precheck is not None:
        return lint_precheck
    passed.append("lint-precheck")

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
    deriv = _derive_tests_from_diff(gate_worktree, diff)
    name_tests = deriv.name
    import_tests = deriv.imported
    direct_import_tests = deriv.imported_direct
    import_report_only = deriv.imported_report_only
    mapped_tests = deriv.mapped
    mapped_dirs = deriv.mapped_dirs
    data_tests = deriv.data
    data_paths = deriv.data_paths
    derived = deriv.derived
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
        imported_direct=direct_import_tests,
        imported_report_only=import_report_only,
        mapped=mapped_tests,
        mapped_dirs=mapped_dirs,
        data=data_tests,
        data_paths=data_paths,
        existing=existing,
        unnamed=unnamed,
        absent=absent,
    ))
    selection = tuple(dict.fromkeys((*tests, *unnamed)))

    update_gate_breadcrumb("named-tests", merged_sha)
    if not selection:
        # #1018: the diff is entirely covered (no binding paths) and no test
        # was named or derived; running ``just pytest`` with zero arguments
        # would invoke the FULL suite, which is the coordinator's sweep, not
        # this lane's gate (#666).  Waive named-tests explicitly and name the
        # covering phases, because a branch that lands with zero named tests
        # must SAY what checked it (#1140, #651).
        print(
            "named-tests: 0 selected; the diff is entirely covered by the "
            "documentation classification; running the full suite is the "
            "coordinator's sweep, not this lane's gate; named-tests waived — "
            "lint-precheck and lint-comparison are the covering phases"
        )
        passed.append("named-tests")
    else:
        print(_test_relevance_line(gate_worktree, selection, diff.changed, data_tests=data_tests))

        named = _run(["just", "pytest", *selection], gate_worktree)
        _relay(named)
        if named.returncode:
            return refuse_gated(
                "named-tests",
                f"named test selection failed with exit {named.returncode}",
                f"merge={merged_sha}; tests={list(tests)!r}; "
                f"derived-and-added={list(unnamed)!r}",
            )
        passed.append("named-tests")

    update_gate_breadcrumb("guard-selection", merged_sha)
    guard_list = _run(
        [sys.executable, "dev/repo_wide_guards.py", "list"], gate_worktree
    )
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
    update_gate_breadcrumb("repo-wide-guards", merged_sha)
    guarded = _run(["just", "pytest", *guards], gate_worktree)
    _relay(guarded)
    if guarded.returncode:
        return refuse_gated(
            "repo-wide-guards",
            f"generated guard set failed with exit {guarded.returncode}",
            f"merge={merged_sha}; guards={guards!r}",
        )
    passed.append("repo-wide-guards")

    update_gate_breadcrumb("lint-comparison", merged_sha)
    lint_comparison = compare_lint("lint-comparison", "post-gates")
    if lint_comparison is not None:
        return lint_comparison
    passed.append("lint-comparison")

    missing = tuple(gate for gate in GATES if gate not in passed)
    if not GATES or not passed or missing:
        return refuse_gated(
            "gate-coverage",
            f"only {len(passed)} of {len(GATES)} declared gates ran, so a pass here would be vacuous",
            f"merge={merged_sha}; ran={passed!r}; declared={list(GATES)!r}; missing={list(missing)!r}",
        )
    print(_gate_coverage_line(passed))

    update_gate_breadcrumb("compare-before-advance", merged_sha)
    state_lock = _try_lock(common_git_dir, "dreamwork-repo-state.lock")
    if state_lock is None:
        return refuse_gated(
            "advance", "repository-state mutex is busy",
            f"merge={merged_sha}; lock={common_git_dir / 'dreamwork-repo-state.lock'}",
        )
    current_base = _git_text(repo, "rev-parse", "--verify", f"refs/heads/{base}")
    current_branch = _git_text(repo, "branch", "--show-current")
    current_head = _git_text(repo, "rev-parse", "HEAD")
    current_dirty = _git(repo, "status", "--porcelain=v1", "--untracked-files=no")
    cas_faults: list[str] = []
    if current_base != base_sha:
        cas_faults.append(f"{base} moved from captured {base_sha} to {current_base or 'UNREADABLE'}")
    if current_branch != base:
        cas_faults.append(f"main checkout is on {current_branch or 'DETACHED'}, not {base}")
    if current_head != base_sha:
        cas_faults.append(f"main HEAD is {current_head or 'UNREADABLE'}, not captured {base_sha}")
    if current_dirty.returncode or current_dirty.stdout:
        cas_faults.append(
            f"main tracked state has {len(current_dirty.stdout.splitlines())} changed path(s)"
        )
    if cas_faults:
        state_lock.close()
        return refuse_gated(
            "advance",
            "compare-before-advance refused; " + "; ".join(cas_faults),
            f"merge={merged_sha}; captured-base={base_sha}; current-base={current_base or 'UNREADABLE'}; "
            f"main-branch={current_branch or 'DETACHED'}; main-head={current_head or 'UNREADABLE'}",
        )
    forward = _git(repo, "merge", "--ff-only", merged_sha)
    landed = _git_text(repo, "rev-parse", "--verify", f"refs/heads/{base}")
    state_lock.close()
    if forward.returncode or landed != merged_sha:
        _relay(forward)
        return refuse_gated(
            "advance",
            f"fast-forward of {base} onto the gated merge did not land",
            f"merge={merged_sha}; ff-exit={forward.returncode}; {base}={landed or 'UNREADABLE'}",
        )
    print(f"advance: {base} {base_sha} -> {merged_sha} after {len(passed)} gate(s)")

    cleanup_fault = _cleanup_gate_worktree(repo, gate_worktree)
    if cleanup_fault is not None:
        _restore_gate_signals()
        return _refuse(
            "scratch-cleanup", cleanup_fault,
            f"merge={merged_sha}; gate_worktree={gate_worktree}; breadcrumb retained",
            retained, base_state=_base_state(repo, base, base_sha),
            alert=f"master advanced safely, but exact scratch cleanup failed: {cleanup_fault}",
        )
    _clear_gate_in_flight(repo)
    _restore_gate_signals()

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


# ---------------------------------------------------------------------------
# Batch landing (#1157).
#
# When N branches are ready to land, landing the first advances master and
# staleifies the remaining N-1 — their preflight "branch is not rebased onto
# current master" refusal is CORRECT (#1055: it fires before any test work, so
# N refusals cost seconds, not N full gate runs). What was missing was a
# supported coordinator path that, per entry, rebases onto the CURRENT master
# and then gates, absorbing each landing before starting the next. The
# coordinator hand-built that as throwaway shell scripts three times in one
# afternoon; this is the version that lives in the repo.
#
# The rebase happens immediately before each gate, inside the loop — NOT all
# up front. Rebase-all-then-gate-all reproduces the original bug: the first
# landing staleifies the rest again (#1157 trap: "you rebase all branches up
# front, then gate them all").
#
# Four outcomes stay distinguishable (#136): landed, refused, rebase-conflict,
# skipped. A batch reports BOTH denominators (#868): how many it attempted and
# how many landed.

# Five outcomes. ``abort-failed`` (round 2, #1157 P1) MUST NOT collapse into
# ``rebase-conflict`` (#136): a conflict is routine and leaves the branch
# clean (the abort succeeded); an abort-failed rebase is a worktree the abort
# could NOT return to a clean state — stranded mid-rebase, which is precisely
# the state #1159 shows perturbing OTHER gates. They are two states and the
# batch must say so loudly for the second.
BATCH_STATES = (
    "landed", "refused", "rebase-conflict", "abort-failed", "skipped",
)


@dataclass
class BatchEntry:
    """One (branch, tests) pair in a batch.

    ``tests`` is the coordinator's explicit named-test list, passed verbatim
    to :func:`land`. An empty tuple is legal ONLY for a doc-only branch whose
    diff has no binding paths (#1018); ``land`` itself enforces that.
    """
    branch: str
    tests: tuple[str, ...]


@dataclass
class BatchOutcome:
    """The verdict for one entry, carried to the summary table unchanged.

    States must not collapse (#136): landed / refused / rebase-conflict /
    abort-failed / skipped are five outcomes. ``rebase-conflict`` means the
    rebase conflicted AND the abort restored the branch cleanly; ``abort-failed``
    means a partial rebase was left that the abort could NOT clean up — a
    stranded worktree (#1159/#1157 P1). ``base_before`` / ``base_after`` let
    the summary show that master advanced once per landing (#1157 red-proof).
    """
    branch: str
    state: str
    detail: str
    base_before: str
    base_after: str


def _parse_batch_entries(
    raw: Sequence[Sequence[str]] | None,
) -> list[BatchEntry]:
    """Turn ``--entry`` token-lists into BatchEntry objects.

    Each raw list's first token is the branch name; the rest are named test
    paths. This pairing is the thing a flat ``just land-lanes b1 b2 ...``
    recipe CANNOT express (IGC goal G2 refuted the justfile-only option),
    because there is no delimiter in a flat arg list to say where one
    branch's tests end and the next branch begins.
    """
    if not raw:
        return []
    entries: list[BatchEntry] = []
    for tokens in raw:
        if not tokens:
            continue
        entries.append(BatchEntry(branch=tokens[0], tests=tuple(tokens[1:])))
    return entries


# A rebase paused on a conflict leaves a ``rebase-merge/`` (interactive) or
# ``rebase-apply/`` (am/apply) directory inside the worktree's git dir. The
# batch must abort that state before the entry can be left alone — a worktree
# stranded mid-rebase is exactly what #1159 shows perturbing OTHER gates.
_REBASE_STATE_DIRS = ("rebase-merge", "rebase-apply")


def _rebase_in_progress(lane: Path) -> bool:
    """True if ``lane``'s repository has a rebase paused mid-operation.

    Reads only (``is_dir``), so it still answers correctly under a read-only
    git dir — which is how the abort-failed fixture (#1157 P1) makes
    ``git rebase --abort`` genuinely fail while this check still sees the
    stranded state.
    """
    git_dir = _git_text(lane, "rev-parse", "--absolute-git-dir")
    if not git_dir:
        return False
    gd = Path(git_dir)
    return any((gd / name).is_dir() for name in _REBASE_STATE_DIRS)


@dataclass(frozen=True)
class _RebaseAttempt:
    """Resolved outcome of rebasing one entry, cleanup included.

    ``ok``        — the rebase applied; nothing to clean up, proceed to gate.
    ``conflict``  — the rebase did not apply AND the abort restored the branch
                    to a clean state; the entry did not land but is safe to
                    leave (#1159: the worktree is not stranded).
    ``abort-failed`` — a partial rebase was left that ``--abort`` could NOT
                    clean up; the worktree is stranded mid-rebase and the
                    batch must report it loudly (#136: not collapsed with a
                    routine conflict).
    """

    state: str  # "ok" | "conflict" | "abort-failed"
    detail: str


def _rebase_lane_checked(lane: Path, base: str) -> _RebaseAttempt:
    """Rebase ``lane`` onto ``base`` with exception-safe, checked cleanup.

    This is the #1157 round-2 P1 fix. Round 1 reached ``git rebase --abort``
    only on the normal non-zero path, with no ``finally`` and with the abort's
    own result ignored — so an interruption/exception could strand the worktree
    mid-rebase, and a FAILED abort was reported as an ordinary conflict and the
    batch continued (the false-GREEN #1159 exists to defend against).

    Two halves, both required (direction-2: a ``finally`` whose abort result is
    still ignored fixes only the interruption half):

    1. Cleanup is a checked ``finally`` path. It runs whether the rebase
       conflicted normally OR an interruption/exception left the worktree
       mid-rebase. An ``except Exception`` records the interruption so the
       entry is reported (not silently dropped) and the batch continues;
       ``BaseException`` (real Ctrl-C / SystemExit) still propagates, because
       the cleanup runs in ``finally`` regardless.

    2. The abort's OWN result is checked. ``--abort`` succeeding is what makes
       a conflict routine (branch clean); ``--abort`` failing is a stranded
       worktree — a distinct ``abort-failed`` outcome (#136), reported loudly,
       not collapsed with ``conflict``. Abort is attempted only when a rebase
       is genuinely in progress, so a clean rebase (or a dirty-tree refusal
       that never started one) is left untouched.
    """
    conflict_detail: str | None = None
    abort_failed_detail: str | None = None
    try:
        rebase = _git(lane, "rebase", base)
        if rebase.returncode:
            _relay(rebase)
            conflict_detail = (
                rebase.stderr.strip()
                or rebase.stdout.strip()
                or f"git rebase exited {rebase.returncode}"
            )
    except Exception as exc:
        # An interruption mid-rebase: the finally below still aborts any
        # partial state, so the worktree is not stranded. Record the cause in
        # the conflict detail (the rebase did not complete) and let the batch
        # report this entry and continue — cleanup correctness does not depend
        # on reaching the explicit abort below.
        conflict_detail = f"rebase interrupted before cleanup: {exc}"
    finally:
        # Runs on the normal conflict path AND on any interruption/exception.
        # Only abort when a rebase is genuinely in progress, so a rebase that
        # applied cleanly is not rolled back. The abort result is CHECKED: a
        # failure here is a stranded worktree, its own outcome (#136). Cleanup
        # must not itself depend on printing, so the abort's output is captured
        # into the detail only when it FAILS (a successful abort is silent —
        # the rebase's own message, already relayed above, is the conflict's).
        if _rebase_in_progress(lane):
            abort = _git(lane, "rebase", "--abort")
            if abort.returncode:
                abort_failed_detail = (
                    abort.stderr.strip()
                    or abort.stdout.strip()
                    or f"git rebase --abort exited {abort.returncode}"
                )
    # A failed abort outranks a routine conflict: the worktree could NOT be
    # returned to a clean state, so it must be visible as a distinct, loud
    # outcome — never folded into the quiet "conflict, moving on" (#136).
    if abort_failed_detail is not None:
        return _RebaseAttempt("abort-failed", abort_failed_detail)
    if conflict_detail is not None:
        return _RebaseAttempt("conflict", conflict_detail)
    return _RebaseAttempt("ok", "")


def land_batch(
    entries: Sequence[BatchEntry],
    *,
    base: str = "master",
) -> int:
    """Land multiple branches serially: rebase-then-gate, per entry.

    For each entry: resolve the branch's registered linked worktree, rebase
    it onto the CURRENT ``base`` tip, and then call :func:`land` (which gates
    and, on PASS, fast-forwards base and reaps the worktree). A rebase
    conflict aborts the rebase (``--abort``, leaving the branch untouched)
    and continues to the next entry; a gate refusal likewise continues.
    Every entry's verdict is reported individually in the summary.

    Returns 0 iff every entry landed; 1 otherwise. A batch with zero entries
    returns 1 — "the batch exited 0" must not be vacuous (#1157 trap).

    Does NOT address #997 (the serial, exclusive gate means the fleet idles
    while one branch gates): batching removes the coordinator's re-derivation
    cost, not the gate's serial bottleneck.
    """
    if not entries:
        print(
            "REFUSE batch: no entries provided; a batch that gates zero "
            "branches is not a batch run",
            file=sys.stderr,
        )
        return 1

    invoked = Path.cwd().resolve()
    repo_claim = _git(invoked, "rev-parse", "--show-toplevel")
    repo_text = repo_claim.stdout.strip()
    repo = Path(repo_text).resolve() if not repo_claim.returncode and repo_text else None
    if repo is None or (invoked != repo and repo not in invoked.parents):
        print(
            "REFUSE batch: invocation is not inside a git worktree",
            file=sys.stderr,
        )
        return 1

    current = _git_text(repo, "branch", "--show-current")
    if current != base:
        print(
            f"REFUSE batch: main checkout is on {current or 'DETACHED'}, "
            f"not {base}; the batch rebase target must be the checked-out base",
            file=sys.stderr,
        )
        return 1

    outcomes: list[BatchOutcome] = []
    for i, entry in enumerate(entries, 1):
        separator = "=" * 60
        print(
            f"\n{separator}\nbatch entry {i}/{len(entries)}: "
            f"branch={entry.branch} named-tests={list(entry.tests)!r}\n{separator}"
        )

        base_before = (
            _git_text(repo, "rev-parse", "--verify", f"refs/heads/{base}")
            or "UNKNOWN"
        )

        # Refresh the worktree roster each iteration: a prior entry's
        # successful landing retired its worktree via reap.py, and a new
        # gate worktree may have been registered and removed in between.
        roster = _worktrees(repo)
        if roster is None:
            outcome = BatchOutcome(
                entry.branch, "skipped",
                "could not enumerate worktrees", base_before, base_before,
            )
            outcomes.append(outcome)
            print(f"batch: {entry.branch}: SKIPPED — could not enumerate worktrees")
            continue

        lane = roster.get(entry.branch)
        if lane is None:
            outcome = BatchOutcome(
                entry.branch, "skipped",
                "no registered linked worktree for this branch",
                base_before, base_before,
            )
            outcomes.append(outcome)
            print(f"batch: {entry.branch}: SKIPPED — no registered linked worktree")
            continue

        # A dirty worktree means the lane is mid-work; rebasing it would
        # either fail or silently incorporate uncommitted state. Skip it
        # rather than touching a worktree the lane still owns.
        dirty = _git(lane, "status", "--porcelain=v1", "--untracked-files=no")
        if dirty.returncode or dirty.stdout.strip():
            count = len(dirty.stdout.splitlines()) if dirty.stdout else 0
            outcome = BatchOutcome(
                entry.branch, "skipped",
                f"lane worktree has {count} uncommitted tracked change(s)",
                base_before, base_before,
            )
            outcomes.append(outcome)
            print(
                f"batch: {entry.branch}: SKIPPED — lane worktree not clean "
                f"({count} path(s))"
            )
            continue

        # Rebase onto the CURRENT base tip, immediately before gating. This
        # is the whole behaviour: it absorbs each prior landing before this
        # entry's gate checks staleness. Rebase-all-up-front would reproduce
        # the original bug (#1157).
        #
        # Cleanup is exception-safe and the abort result is checked (#1157 P1):
        # see _rebase_lane_checked. A conflict aborts cleanly (branch restored);
        # a FAILED abort is a stranded worktree reported as its own outcome.
        print(f"batch: rebasing {entry.branch} onto {base}@{base_before[:12]}")
        attempt = _rebase_lane_checked(lane, base)
        if attempt.state == "abort-failed":
            # The worktree could NOT be returned to a clean state — a stranded
            # mid-rebase worktree perturbs OTHER gates (#1159), so this is its
            # own outcome reported loudly, not collapsed with rebase-conflict
            # (#136). The branch did not land; the coordinator must clean up.
            outcome = BatchOutcome(
                entry.branch, "abort-failed",
                f"rebase aborted but cleanup FAILED: {attempt.detail}",
                base_before, base_before,
            )
            outcomes.append(outcome)
            print(
                f"batch: {entry.branch}: ABORT-FAILED — rebase left stranded "
                f"mid-rebase; cleanup did not complete: {attempt.detail}",
                file=sys.stderr,
            )
            continue
        if attempt.state == "conflict":
            # Routine conflict: the abort restored the branch, so the worktree
            # is clean and the entry is safe to leave (#1159).
            outcome = BatchOutcome(
                entry.branch, "rebase-conflict", attempt.detail,
                base_before, base_before,
            )
            outcomes.append(outcome)
            print(
                f"batch: {entry.branch}: REBASE-CONFLICT — {attempt.detail}",
                file=sys.stderr,
            )
            continue

        # Gate: land() re-checks staleness (now satisfied by the rebase),
        # runs all gates, and on PASS fast-forwards base and reaps the
        # worktree. Its full output is visible in the interleaved stream.
        result = land(entry.branch, entry.tests, base=base)
        base_after = (
            _git_text(repo, "rev-parse", "--verify", f"refs/heads/{base}")
            or "UNKNOWN"
        )

        if result == 0:
            outcome = BatchOutcome(
                entry.branch, "landed",
                f"{base} {base_before[:12]} -> {base_after[:12]}",
                base_before, base_after,
            )
            print(
                f"batch: {entry.branch}: LANDED — "
                f"{base} {base_before[:12]} -> {base_after[:12]}"
            )
        else:
            outcome = BatchOutcome(
                entry.branch, "refused",
                f"gate exited {result}", base_before, base_after,
            )
            print(
                f"batch: {entry.branch}: REFUSED — gate exited {result}",
                file=sys.stderr,
            )
        outcomes.append(outcome)

    # Summary: every entry's verdict is individually visible (#1157 req 4,
    # #136 states must not collapse, #868 both denominators).
    landed = sum(1 for o in outcomes if o.state == "landed")
    refused = sum(1 for o in outcomes if o.state == "refused")
    conflicts = sum(1 for o in outcomes if o.state == "rebase-conflict")
    abort_failed = sum(1 for o in outcomes if o.state == "abort-failed")
    skipped = sum(1 for o in outcomes if o.state == "skipped")

    print(f"\n{'=' * 60}")
    print(
        f"batch summary: attempted={len(outcomes)} landed={landed} "
        f"refused={refused} rebase-conflict={conflicts} "
        f"abort-failed={abort_failed} skipped={skipped}"
    )
    print(f"{'=' * 60}")
    markers = {
        "landed": "LANDED  ",
        "refused": "REFUSED ",
        "rebase-conflict": "CONFLICT",
        "abort-failed": "ABORTBAD",
        "skipped": "SKIPPED ",
    }
    for o in outcomes:
        print(f"  {o.branch}: {markers[o.state]}  {o.detail}")

    return 0 if landed == len(outcomes) else 1


def _main_batch(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="dev/land_lane.py batch",
        description=(
            "Land multiple branches serially: per entry, rebase onto current "
            "base then gate, absorbing each landing before the next (#1157)."
        ),
    )
    parser.add_argument(
        "--entry",
        action="append",
        dest="raw_entries",
        metavar="BRANCH [TESTS...]",
        nargs="+",
        help=(
            "one entry per repeat: the first token is the lane branch, the "
            "rest are its named pytest paths/node ids. Repeat --entry for "
            "each branch in the batch. A doc-only branch (#1018) may omit "
            "tests; any other branch must name at least one test."
        ),
    )
    parser.add_argument(
        "--base",
        default="master",
        help="checked-out base branch (default: master)",
    )
    args = parser.parse_args(argv)
    entries = _parse_batch_entries(args.raw_entries)
    return land_batch(entries, base=args.base)


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = list(argv) if argv is not None else list(sys.argv[1:])
    # The batch subcommand (#1157) has its own arg shape (--entry, repeated),
    # so it is routed before the single-branch parser. Anything else is the
    # original single-branch path, unchanged.
    if raw_argv and raw_argv[0] == "batch":
        return _main_batch(raw_argv[1:])
    parser = argparse.ArgumentParser(
        description="Merge a rebased lane, run named and repo-wide gates, then reap its worktree."
    )
    parser.add_argument("branch", help="explicit local lane branch")
    parser.add_argument("tests", nargs="*", help="explicit named pytest paths/node ids")
    parser.add_argument("--base", default="master", help="checked-out base branch (default: master)")
    parser.add_argument(
        "--squash",
        action="store_true",
        help="atomically squash the lane in place, preserving and verifying its original tree",
    )
    parser.add_argument(
        "--expect-warn-add",
        action="append",
        default=[],
        metavar="ROW",
        help="declare a WARN row (exact text as lint.py prints it) expected to be ADDED "
        "relative to the baseline; the observed added set must match all declared rows "
        "exactly (#1040). Repeatable.",
    )
    parser.add_argument(
        "--expect-warn-remove",
        action="append",
        default=[],
        metavar="ROW",
        help="declare a WARN row expected to be REMOVED relative to the baseline; "
        "the observed removed set must match exactly (#1040). Repeatable.",
    )
    args = parser.parse_args(argv)
    return land(
        args.branch,
        args.tests,
        base=args.base,
        squash=args.squash,
        expect_warn_add=args.expect_warn_add,
        expect_warn_remove=args.expect_warn_remove,
    )


if __name__ == "__main__":
    raise SystemExit(main())
