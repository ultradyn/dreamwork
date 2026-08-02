from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import subprocess
import sys

import pytest


REPO = Path(__file__).resolve().parent
TOOL = REPO / "dev" / "land_lane.py"
REDPROOF = REPO / "dev" / "redproof.py"


def _load_tool():
    """Import the worktree's own copy, for the checks that need its roster.

    Registered in ``sys.modules`` before execution because ``@dataclass``
    resolves ``cls.__module__`` through it: an unregistered module makes any
    tool that adopts a dataclass fail to import with a bare AttributeError
    from inside ``dataclasses``, which names neither this loader nor the tool.
    """
    spec = importlib.util.spec_from_file_location("land_lane_under_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


land_lane = _load_tool()


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _redproof(lane: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REDPROOF), "--cwd", str(lane), *args],
        cwd=lane,
        capture_output=True,
        text=True,
    )


def _make_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A base checkout plus an empty lane worktree, with nothing committed on it.

    Split out of ``landing_repo`` so a lane whose whole diff is documentation
    can be built without the ``feature.txt`` commit that makes the default
    fixture's diff code-shaped (#949).
    """
    # lane_scratch keys repositories by checkout-directory name; keep the
    # fixture's red-proof registry isolated across pytest cases.
    root = tmp_path / f"repo-{tmp_path.parent.name}-{tmp_path.name}"
    lane = tmp_path / "lane"
    root.mkdir()
    _git(root, "init", "-b", "master")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    _write(
        root / "justfile",
        "pytest *ARGS:\n    python3 -m pytest -q {{ARGS}}\n",
    )
    _write(
        root / "lint.py",
        "from pathlib import Path\n"
        "import sys\n"
        "p = Path('lint-rows.txt')\n"
        "rows = p.read_text().splitlines() if p.exists() else []\n"
        "for row in rows: print('  WARN  ' + row)\n"
        "print(f'clean ({len(rows)} warning(s))')\n",
    )
    _write(root / "lint-rows.txt", "old warning\n")
    _write(root / "dev" / "repo_wide_guards.py", "print('test_guard.py')\n")
    _write(root / "test_named.py", "def test_named(): assert True\n")
    # The guard reads a data file rather than asserting a literal, so a lane can
    # break the GENERATED GUARD SET without also changing a test file — which
    # the derived-test union would otherwise catch one phase earlier (#948).
    _write(
        root / "test_guard.py",
        "from pathlib import Path\n"
        "def test_guard(): assert Path('guard-data.txt').read_text().strip() == 'ok'\n",
    )
    _write(root / "guard-data.txt", "ok\n")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "base")
    _git(root, "worktree", "add", "-b", "lane", str(lane), "master")
    return root, lane


@pytest.fixture
def landing_repo(tmp_path: Path):
    root, lane = _make_repo(tmp_path)
    _write(lane / "feature.txt", "lane\n")
    _git(lane, "add", "feature.txt")
    _git(lane, "commit", "-m", "lane change")
    armed = _redproof(lane, "begin", "feature.txt", "--expectation", "test_named.py")
    assert armed.returncode == 0, armed.stdout + armed.stderr
    _write(lane / "feature.txt", "recorded red-proof injection\n")
    observed = _redproof(
        lane, "observe", "feature.txt", "--failure", "feature injection reached",
        "--command", sys.executable, "-c",
        "from pathlib import Path; assert Path('feature.txt').read_text() == "
        "'lane\\n', 'feature injection reached'",
    )
    assert observed.returncode == 0, observed.stdout + observed.stderr
    restored = _redproof(lane, "restore", "feature.txt")
    assert restored.returncode == 0, restored.stdout + restored.stderr
    return root, lane


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), "lane", *args],
        cwd=root,
        capture_output=True,
        text=True,
    )


def _assert_retained(root: Path, lane: Path) -> None:
    assert lane.is_dir()
    assert _git(root, "show-ref", "--verify", "refs/heads/lane")
    assert str(lane.resolve()) in _git(root, "worktree", "list", "--porcelain")


def _assert_base_unmoved(root: Path, before: str) -> None:
    """#882: a refusal must leave master exactly where the run found it.

    Four readings, because the incident had three of them true: the ref is
    what another lane rebases onto, HEAD and the branch name are what the
    restore had to put back, and a dirty tree is a restore that ran without
    landing.
    """
    assert _git(root, "rev-parse", "--verify", "refs/heads/master") == before, "master moved"
    assert _git(root, "rev-parse", "HEAD") == before, "HEAD was not restored"
    assert _git(root, "branch", "--show-current") == "master", "checkout left detached"
    assert _git(root, "status", "--porcelain=v1", "--untracked-files=no") == ""


def test_empty_named_selection_refuses_before_merge(landing_repo):
    root, lane = landing_repo
    before = _git(root, "rev-parse", "HEAD")
    result = _run(root)

    assert result.returncode == 1
    assert "REFUSE phase=selection: named test selection is empty" in result.stderr
    assert "named tests=0" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


@pytest.mark.parametrize(
    ("generator", "message"),
    [
        ("import sys\nsys.exit(2)\n", "repo-wide guard list command exited 2"),
        ("print('')\n", "repo-wide guard list is empty"),
    ],
)
def test_unavailable_guard_selection_refuses_instead_of_vacuously_running(
    landing_repo, generator, message
):
    root, lane = landing_repo
    _write(lane / "dev" / "repo_wide_guards.py", generator)
    _git(lane, "add", "dev/repo_wide_guards.py")
    _git(lane, "commit", "-m", "break guard inventory")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert f"REFUSE phase=guard-selection: {message}" in result.stderr
    assert "deliberately did not perform: dev/reap.py lane retirement" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


@pytest.mark.parametrize(
    "lint_body",
    [
        "raise SystemExit(2)\n",
        "print('lint ran but omitted its trailer')\n",
        "print('clean (1 warning(s))')\n",
    ],
)
def test_missing_warn_baseline_refuses_before_merge(landing_repo, lint_body):
    root, lane = landing_repo
    _write(root / "lint.py", lint_body)
    _git(root, "add", "lint.py")
    _git(root, "commit", "-m", "broken baseline command")
    _git(lane, "rebase", "master")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "REFUSE phase=lint-baseline: WARN baseline was not captured" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_new_warn_row_refuses_and_retains_lane(landing_repo):
    root, lane = landing_repo
    _write(
        lane / "test_expensive.py",
        "from pathlib import Path\n"
        "def test_expensive(): Path('named-test-ran.txt').write_text('ran\\n')\n",
    )
    _write(lane / "lint-rows.txt", "old warning\nnew warning\n")
    _git(lane, "add", "lint-rows.txt", "test_expensive.py")
    _git(lane, "commit", "-m", "add warning")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_expensive.py")

    assert result.returncode == 1
    assert "lint-precheck WARN row-set comparison: added=1 removed=0" in result.stdout
    assert "+   WARN  new warning" in result.stdout
    assert "REFUSE phase=lint-precheck: WARN row set changed" in result.stderr
    assert not (root / "named-test-ran.txt").exists(), (
        "lint-precheck spoke only after the named test had already run"
    )
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_warn_created_by_named_test_is_caught_by_authoritative_comparison(landing_repo):
    """The early check must not replace the reading after mutable gates run."""
    root, lane = landing_repo
    _write(
        lane / "lint.py",
        "from pathlib import Path\n"
        "rows = Path('lint-rows.txt').read_text().splitlines()\n"
        "if Path('named-test-warn.txt').exists(): rows.append('named-test warning')\n"
        "for row in rows: print('  WARN  ' + row)\n"
        "print(f'clean ({len(rows)} warning(s))')\n",
    )
    _write(
        lane / "test_refresh.py",
        "from pathlib import Path\n"
        "def test_refresh(): Path('named-test-warn.txt').write_text('warn\\n')\n",
    )
    _git(lane, "add", "lint.py", "test_refresh.py")
    _git(lane, "commit", "-m", "make named test refresh a lint input")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_refresh.py")

    assert result.returncode == 1
    assert "lint-precheck WARN row-set comparison: added=0 removed=0" in result.stdout
    assert "lint-comparison WARN row-set comparison: added=1 removed=0" in result.stdout
    assert "+   WARN  named-test warning" in result.stdout
    assert "REFUSE phase=lint-comparison: WARN row set changed" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_same_warn_count_with_different_rows_refuses(landing_repo):
    root, lane = landing_repo
    _write(lane / "lint-rows.txt", "new warning\n")
    _git(lane, "add", "lint-rows.txt")
    _git(lane, "commit", "-m", "replace warning")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "lint-precheck WARN row-set comparison: added=1 removed=1" in result.stdout
    assert "+   WARN  new warning" in result.stdout
    assert "-   WARN  old warning" in result.stdout
    assert "REFUSE phase=lint-precheck: WARN row set changed" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_wider_lint_label_padding_is_not_a_warn_identity_change(landing_repo):
    root, lane = landing_repo
    _write(
        root / "lint.py",
        "from pathlib import Path\n"
        "width = int(Path('lint-width.txt').read_text())\n"
        "print('  WARN  ' + 'lessons.md'.ljust(width) + '  same warning')\n"
        "print('clean (1 warning(s))')\n",
    )
    _write(root / "lint-width.txt", "19\n")
    _git(root, "add", "lint.py", "lint-width.txt")
    _git(root, "commit", "-m", "render a dynamically padded lint label")
    _git(lane, "rebase", "master")
    _write(lane / "lint-width.txt", "22\n")
    _git(lane, "add", "lint-width.txt")
    _git(lane, "commit", "-m", "widen the lint label column by three")

    result = _run(root, "test_named.py")

    assert result.returncode == 0, result.stderr
    assert "lint-comparison WARN row-set comparison: added=0 removed=0" in result.stdout
    assert "baseline=1 rows; post-gates=1 rows" in result.stdout


def test_warn_identity_does_not_collapse_meaningful_detail_whitespace():
    one_space = "  WARN  lessons.md  merging is his call"
    two_spaces = "  WARN  lessons.md  merging  is his call"

    assert " ".join(one_space.split()) == " ".join(two_spaces.split()), (
        "the killer input must collide under the rejected blanket whitespace rule"
    )
    assert land_lane._warn_row_identity(one_space) != land_lane._warn_row_identity(two_spaces)


def test_meaningful_detail_whitespace_swap_refuses_and_names_both_rows(landing_repo):
    root, lane = landing_repo
    _write(
        root / "lint.py",
        "print('  WARN  lessons.md  merging is his call')\n"
        "print('clean (1 warning(s))')\n",
    )
    _git(root, "add", "lint.py")
    _git(root, "commit", "-m", "render one-space warning detail")
    _git(lane, "rebase", "master")
    _write(
        lane / "lint.py",
        "print('  WARN  lessons.md  merging  is his call')\n"
        "print('clean (1 warning(s))')\n",
    )
    _git(lane, "add", "lint.py")
    _git(lane, "commit", "-m", "change meaningful warning whitespace")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "lint-precheck WARN row-set comparison: added=1 removed=1" in result.stdout
    assert "+   WARN  lessons.md  merging  is his call" in result.stdout
    assert "-   WARN  lessons.md  merging is his call" in result.stdout
    assert "REFUSE phase=lint-precheck: WARN row set changed" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


# ---------------------------------------------------------------------------
# #1040: coordinator authorisation for an intended WARN row-set change.
#
# The gate invocation is the one channel a lane cannot forge (the coordinator
# types it), so the declaration arrives as CLI flags. Every test below pairs a
# "declared change passes" assertion with its mandatory "undeclared change
# still refuses" counterpart, and asserts the reported DENOMINATORS rather than
# exit codes alone — an exit code cannot distinguish "adjudicated and matched"
# from "ignored the declaration" (#136/#868).
# ---------------------------------------------------------------------------


def _run_declared(root, *warn_flags, tests="test_named.py"):
    """Invoke the gate with coordinator WARN-authorisation flags.

    ``warn_flags`` are the raw CLI tokens (``--expect-warn-add ROW`` etc.) so
    the test body shows exactly what the coordinator would type.
    """
    return _run(root, *warn_flags, tests)


def _add_lane_warn(lane, *rows):
    """Commit a lint-rows.txt on the lane adding the given rows to the baseline."""
    _write(lane / "lint-rows.txt", "old warning\n" + "\n".join(rows) + "\n")
    _git(lane, "add", "lint-rows.txt")
    _git(lane, "commit", "-m", "add warn row(s)")


def _baseline_two_warnings(root, lane):
    """Give the baseline a second warning so removing one leaves a non-empty
    population — the gate refuses on an empty WARN reading BEFORE it reaches
    authorisation, so a fix-only test must leave at least one row."""
    _write(root / "lint-rows.txt", "old warning\nkeeper warning\n")
    _git(root, "add", "lint-rows.txt")
    _git(root, "commit", "-m", "add a second baseline warning")
    _git(lane, "rebase", "master")


def test_declared_warn_add_passes_and_reports_denominators(landing_repo):
    """The core #1040 case: a lane whose product is a new WARN row, declared
    by the coordinator, passes — and the pass reports denominators that
    distinguish it from a silent zero-change pass."""
    root, lane = landing_repo
    _add_lane_warn(lane, "new warning")
    before = _git(root, "rev-parse", "HEAD")

    result = _run_declared(
        root, "--expect-warn-add", "  WARN  new warning"
    )

    assert result.returncode == 0, result.stderr
    assert "gate-coverage: 6 of 6 declared gates passed" in result.stdout
    # The comparison still shows what changed — suppression would hide regressions.
    assert "lint-precheck WARN row-set comparison: added=1 removed=0" in result.stdout
    # The authorisation line reports denominators (#136/#868): declared,
    # observed, and matched must all be visible and distinguish this pass from
    # a zero-change pass.
    assert (
        "lint-precheck WARN authorisation: "
        "declared_added=1 observed_added=1 matched_added=1; "
        "declared_removed=0 observed_removed=0 matched_removed=0"
    ) in result.stdout
    # lint-comparison must also adjudicate the same declaration.
    assert (
        "lint-comparison WARN authorisation: "
        "declared_added=1 observed_added=1 matched_added=1"
    ) in result.stdout
    # Master advances on a successful landing (unlike a refusal).
    assert _git(root, "rev-parse", "refs/heads/master") != before


def test_undeclared_warn_add_still_refuses(landing_repo):
    """Mandatory pair for test_declared_warn_add_passes: the SAME diff without
    a declaration still refuses — proving the authorisation was adjudicated,
    not bypassed."""
    root, lane = landing_repo
    _add_lane_warn(lane, "new warning")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "lint-precheck WARN row-set comparison: added=1 removed=0" in result.stdout
    assert "REFUSE phase=lint-precheck: WARN row set changed" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_declared_warn_remove_passes(landing_repo):
    """Symmetry: a lane that FIXES a lint warning removes a row. The
    declaration covers removed as well as added, or a fix-only lane is stuck."""
    root, lane = landing_repo
    _baseline_two_warnings(root, lane)
    # Remove only one warning; the other survives so the after-population is
    # non-empty and the gate reaches the authorisation check.
    _write(lane / "lint-rows.txt", "keeper warning\n")
    _git(lane, "add", "lint-rows.txt")
    _git(lane, "commit", "-m", "fix the baseline warning")
    before = _git(root, "rev-parse", "HEAD")

    result = _run_declared(
        root, "--expect-warn-remove", "  WARN  old warning"
    )

    assert result.returncode == 0, result.stderr
    assert "gate-coverage: 6 of 6 declared gates passed" in result.stdout
    assert "lint-precheck WARN row-set comparison: added=0 removed=1" in result.stdout
    assert (
        "lint-precheck WARN authorisation: "
        "declared_added=0 observed_added=0 matched_added=0; "
        "declared_removed=1 observed_removed=1 matched_removed=1"
    ) in result.stdout
    # Master advances on a successful landing.
    assert _git(root, "rev-parse", "refs/heads/master") != before


def test_undeclared_warn_remove_still_refuses(landing_repo):
    """Mandatory pair for test_declared_warn_remove_passes."""
    root, lane = landing_repo
    _baseline_two_warnings(root, lane)
    _write(lane / "lint-rows.txt", "keeper warning\n")
    _git(lane, "add", "lint-rows.txt")
    _git(lane, "commit", "-m", "fix the baseline warning")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "lint-precheck WARN row-set comparison: added=0 removed=1" in result.stdout
    assert "REFUSE phase=lint-precheck: WARN row set changed" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_declared_add_wrong_row_refuses(landing_repo):
    """Declared A, observed B → refuse. A declaration that means 'some change
    is fine' would let an unrelated regression ride along."""
    root, lane = landing_repo
    _add_lane_warn(lane, "actual warning")
    before = _git(root, "rev-parse", "HEAD")

    result = _run_declared(
        root, "--expect-warn-add", "  WARN  declared warning"
    )

    assert result.returncode == 1
    assert "REFUSE phase=lint-precheck" in result.stderr
    assert "does not match the coordinator declaration exactly" in result.stderr
    # Denominators show the mismatch concretely.
    assert "declared_added=1 observed_added=1 matched_added=0" in result.stdout
    assert "1 added row(s) not declared" in result.stderr
    assert "1 declared-added row(s) not observed" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_declared_add_observed_has_extra_refuses(landing_repo):
    """Declared A, observed A plus B → refuse. The undeclared B is a
    regression hiding inside an authorised landing."""
    root, lane = landing_repo
    _add_lane_warn(lane, "declared warning", "undeclared warning")
    before = _git(root, "rev-parse", "HEAD")

    result = _run_declared(
        root, "--expect-warn-add", "  WARN  declared warning"
    )

    assert result.returncode == 1
    assert "REFUSE phase=lint-precheck" in result.stderr
    assert "does not match the coordinator declaration exactly" in result.stderr
    assert "declared_added=1 observed_added=2 matched_added=1" in result.stdout
    assert "1 added row(s) not declared" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_declared_add_overdeclared_refuses(landing_repo):
    """Declared A and B, observed only A → refuse. This is the case the brief
    names as most likely to be skipped: the declaration is a SUPERSET of the
    observed change, so a permissive check would pass."""
    root, lane = landing_repo
    _add_lane_warn(lane, "observed warning")
    before = _git(root, "rev-parse", "HEAD")

    result = _run_declared(
        root,
        "--expect-warn-add", "  WARN  observed warning",
        "--expect-warn-add", "  WARN  never appeared warning",
    )

    assert result.returncode == 1
    assert "REFUSE phase=lint-precheck" in result.stderr
    assert "does not match the coordinator declaration exactly" in result.stderr
    assert "declared_added=2 observed_added=1 matched_added=1" in result.stdout
    assert "1 declared-added row(s) not observed" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_declared_change_not_observed_refuses(landing_repo):
    """Declared A, observed nothing → refuse. The coordinator declared a
    change that did not happen; the gate must not pass on a phantom
    declaration."""
    root, lane = landing_repo
    # No change to lint-rows.txt — the lane only has feature.txt.
    before = _git(root, "rev-parse", "HEAD")

    result = _run_declared(
        root, "--expect-warn-add", "  WARN  phantom warning"
    )

    assert result.returncode == 1
    assert "REFUSE phase=lint-precheck" in result.stderr
    assert "does not match the coordinator declaration exactly" in result.stderr
    assert "declared_added=1 observed_added=0 matched_added=0" in result.stdout
    assert "1 declared-added row(s) not observed" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_malformed_warn_declaration_refuses_naming_offending_token(landing_repo):
    """#1040 Finding 1: a coordinator declaration that does not parse as a WARN
    row (a typo) must refuse as a DECLARATION-UNREADABLE fault naming the
    offending token — not as a generic row-set mismatch that diagnoses the
    coordinator's own command-line error as a lane defect (#136: nothing
    declared, nothing changed, the declaration could not be read must stay
    distinct).

    The lane has a GENUINE added warning, so the defect is not whether the lane
    changed the baseline — it did — but that the declaration cannot be read.
    Validation is bound to the same _warn_row_identity the observed rows use, so
    a declaration is unreadable exactly when it could not name a real row.

    This stays distinct from a mismatch: a valid declaration naming a row the
    merge did not observe is still a MISMATCH (proven by
    test_declared_add_wrong_row_refuses), never unreadable. Asserting both the
    offending token AND the absence of the generic mismatch closes the
    false-green where 'refuses' passes for the wrong reason.
    """
    root, lane = landing_repo
    _add_lane_warn(lane, "actual warning")
    before = _git(root, "rev-parse", "HEAD")

    result = _run_declared(
        root, "--expect-warn-add", "not a WARN row"
    )

    assert result.returncode == 1
    # Pre-merge validation (lint-baseline), not the post-merge mismatch (lint-precheck).
    assert "REFUSE phase=lint-baseline" in result.stderr
    assert "could not be read" in result.stderr
    # The offending token is named, so the coordinator sees THEIR typo, not a
    # lane defect.
    assert "not a WARN row" in result.stderr
    # The generic mismatch message must NOT appear — that is the bug this fixes.
    assert "does not match the coordinator declaration exactly" not in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_malformed_warn_remove_declaration_refuses_naming_offending_token(landing_repo):
    """#1040 Finding 1, remove direction: symmetry — a malformed remove
    declaration refuses the same way as a malformed add declaration."""
    root, lane = landing_repo
    _baseline_two_warnings(root, lane)
    _write(lane / "lint-rows.txt", "keeper warning\n")
    _git(lane, "add", "lint-rows.txt")
    _git(lane, "commit", "-m", "remove one warn row")
    before = _git(root, "rev-parse", "HEAD")

    result = _run_declared(
        root, "--expect-warn-remove", "total garbage declaration"
    )

    assert result.returncode == 1
    assert "REFUSE phase=lint-baseline" in result.stderr
    assert "could not be read" in result.stderr
    assert "total garbage declaration" in result.stderr
    assert "does not match the coordinator declaration exactly" not in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_zero_change_pass_prints_no_authorisation_line(landing_repo):
    """#136: a pass because zero rows changed must NOT print an authorisation
    line. The authorised-pass case prints one (proven by
    test_declared_warn_add_passes_and_reports_denominators); this test proves
    the discriminator — the two passes read differently."""
    root, lane = landing_repo

    zero_change = _run(root, "test_named.py")
    assert zero_change.returncode == 0, zero_change.stderr
    assert "WARN authorisation:" not in zero_change.stdout


def test_declared_warn_add_accepts_diff_prefix_from_gate_output(landing_repo):
    """The coordinator copies the added-row line straight from the gate's
    ``+   WARN  ...`` diff output. _declared_warn_index strips that leading
    ``+ `` so the declaration matches the observed row. Without prefix
    stripping the identity would differ (raw ``"+   WARN  ..."`` vs raw
    ``"  WARN  ..."``) and the authorisation would never fire — the helper
    exists to bridge exactly that gap."""
    root, lane = landing_repo
    _add_lane_warn(lane, "new warning")
    before = _git(root, "rev-parse", "HEAD")

    result = _run_declared(
        root, "--expect-warn-add", "+   WARN  new warning"
    )

    assert result.returncode == 0, result.stderr
    assert (
        "lint-precheck WARN authorisation: "
        "declared_added=1 observed_added=1 matched_added=1"
    ) in result.stdout
    assert _git(root, "rev-parse", "refs/heads/master") != before


def test_empty_warn_baseline_refuses_as_zero_population(landing_repo):
    root, lane = landing_repo
    _write(root / "lint-rows.txt", "")
    _git(root, "add", "lint-rows.txt")
    _git(root, "commit", "-m", "empty baseline")
    _git(lane, "rebase", "master")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "REFUSE phase=lint-baseline: WARN baseline population is empty" in result.stderr
    assert "baseline=0 rows examined" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_empty_post_merge_warn_population_refuses(landing_repo):
    root, lane = landing_repo
    _write(lane / "lint-rows.txt", "")
    _git(lane, "add", "lint-rows.txt")
    _git(lane, "commit", "-m", "empty post-merge lint report")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert (
        "REFUSE phase=lint-precheck: post-merge precheck WARN population is empty"
    ) in result.stderr
    assert "baseline=1 rows; post-merge precheck=0 rows examined" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_failing_named_test_names_phase_and_retains_lane(landing_repo):
    root, lane = landing_repo
    _write(lane / "test_failure.py", "def test_failure(): assert False\n")
    _git(lane, "add", "test_failure.py")
    _git(lane, "commit", "-m", "add a real failing test")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_failure.py")

    assert result.returncode == 1
    assert "REFUSE phase=named-tests: named test selection failed" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_failing_generated_guard_names_phase_and_retains_lane(landing_repo):
    root, lane = landing_repo
    _write(lane / "guard-data.txt", "broken\n")
    _git(lane, "add", "guard-data.txt")
    _git(lane, "commit", "-m", "break generated guard")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "REFUSE phase=repo-wide-guards: generated guard set failed" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_refusal_says_where_master_ended_up_not_only_what_it_skipped(landing_repo):
    """#882's second rule: the message must state master's resulting sha.

    The incident's REFUSE named four things it had not done and was silent
    about the merge it had, so the line this asserts is the one whose absence
    made an already-merged refusal readable as "nothing happened".
    """
    root, lane = landing_repo
    _write(lane / "test_failure.py", "def test_failure(): assert False\n")
    _git(lane, "add", "test_failure.py")
    _git(lane, "commit", "-m", "add a real failing test")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_failure.py")

    assert result.returncode == 1
    assert f"base: master={before} unchanged by this run; HEAD={before}" in result.stderr
    _assert_base_unmoved(root, before)


def test_stale_lane_refuses_before_baseline_or_merge(landing_repo):
    root, lane = landing_repo
    _write(root / "base-moved.txt", "new base\n")
    _git(root, "add", "base-moved.txt")
    _git(root, "commit", "-m", "move base")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "REFUSE phase=preflight: branch is not rebased onto current master" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_history_injection_refuses_before_detach_and_names_the_commit(
    landing_repo, monkeypatch
):
    """Exercise the real registry + git-history path, not a mocked scan result."""
    root, lane = landing_repo
    _write(lane / "feature.txt", "recorded red-proof injection\n")
    _git(lane, "add", "feature.txt")
    _git(lane, "commit", "-m", "test injection held in history")
    injected_commit = _git(lane, "rev-parse", "HEAD")
    _write(lane / "feature.txt", "lane\n")
    _git(lane, "add", "feature.txt")
    _git(lane, "commit", "-m", "restore fixed tree")
    before = _git(root, "rev-parse", "HEAD")
    monkeypatch.setenv("DREAMWORK_LANE_ID", "wrong-coordinator-identity")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "history: examined 3 commit(s)" in result.stdout
    assert "1 holding a recorded injection" in result.stdout
    assert "REFUSE phase=red-proof-history" in result.stderr
    assert "commit(s) on this branch still hold a recorded injection" in result.stderr
    assert injected_commit[:12] in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_squash_repairs_history_injection_and_preserves_original_tip(landing_repo):
    root, lane = landing_repo
    _write(lane / "feature.txt", "recorded red-proof injection\n")
    _git(lane, "add", "feature.txt")
    _git(lane, "commit", "-m", "test injection held in history")
    _write(lane / "feature.txt", "lane\n")
    _git(lane, "add", "feature.txt")
    _git(lane, "commit", "-m", "restore fixed tree")
    original = _git(lane, "rev-parse", "HEAD")

    result = _run(root, "test_named.py", "--squash")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "squash cause: history held a recorded injection (#710)" in result.stdout
    assert "squash-verification: PASS" in result.stdout
    assert "found 0 differing paths" in result.stdout
    assert _git(root, "rev-parse", "refs/tags/lane-presquash") == original
    squashed = _git(root, "rev-parse", "refs/heads/lane")
    assert _git(root, "rev-list", "--count", f"master^..{squashed}") == "1"


def test_squash_verification_refuses_a_dropped_outside_path_and_reattaches_main(
    landing_repo, monkeypatch, capsys
):
    """The complete-tree diff catches the exact ``commit --only`` loss.

    ``kept`` is the tree a hand squash naming only ``feature.txt`` would
    produce; ``outside.txt`` is the lane-owned path that spelling silently
    drops. The assertion message is the direction-1 discriminator for the
    production seam ``_squash_tree_diff``.
    """
    root, lane = landing_repo
    kept = _git(lane, "rev-parse", "HEAD")
    _write(lane / "outside.txt", "must survive squash\n")
    _git(lane, "add", "outside.txt")
    _git(lane, "commit", "-m", "change outside the imagined only-path list")
    original = _git(lane, "rev-parse", "HEAD")
    kept_tree = _git(lane, "rev-parse", f"{kept}^{{tree}}")
    before = _git(root, "rev-parse", "HEAD")
    monkeypatch.setattr(land_lane, "_squash_commit_tree", lambda *_: kept_tree)
    monkeypatch.chdir(root)

    code = land_lane.land("lane", ["test_named.py"], squash=True)
    output = capsys.readouterr()

    assert code == 1, (
        "dropped path outside.txt was not caught by _squash_tree_diff; "
        "the lossy squash continued"
    )
    assert "REFUSE phase=squash-verification" in output.err
    assert "D\toutside.txt" in output.err, output.err
    assert "branch rollback restored the original tip" in output.err
    assert _git(root, "rev-parse", "refs/heads/lane") == original
    assert _git(root, "rev-parse", "refs/tags/lane-presquash") == original
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_squash_preserves_deletion_mode_and_symlink_target(tmp_path):
    root, lane = _make_repo(tmp_path)
    _write(root / "deleted.txt", "remove me\n")
    _write(root / "mode.sh", "#!/bin/sh\nexit 0\n")
    (root / "link.txt").symlink_to("old-target")
    _git(root, "add", "deleted.txt", "mode.sh", "link.txt")
    _git(root, "commit", "-m", "add tree-shape fixtures")
    _git(lane, "rebase", "master")

    (lane / "deleted.txt").unlink()
    (lane / "mode.sh").chmod(0o755)
    (lane / "link.txt").unlink()
    (lane / "link.txt").symlink_to("new-target")
    _git(lane, "add", "deleted.txt", "mode.sh", "link.txt")
    _git(lane, "commit", "-m", "change deletion mode and symlink target")
    base_sha = _git(root, "rev-parse", "master")
    original = _git(lane, "rev-parse", "HEAD")

    result = land_lane._squash_lane(lane, "lane", base_sha, original)

    assert result.error is None, result.error
    assert result.new_sha
    assert land_lane._squash_tree_diff(
        lane, "refs/tags/lane-presquash", "refs/heads/lane"
    ) == ()
    assert not (lane / "deleted.txt").exists(), "squash resurrected a deletion"
    assert (lane / "mode.sh").stat().st_mode & 0o111, "squash dropped executable mode"
    assert (lane / "link.txt").readlink() == Path("new-target"), (
        "squash dropped a symlink target change whose regular-file content is empty"
    )


def test_tree_diff_names_reinstated_deletion_mode_loss_and_symlink_loss(tmp_path):
    root, lane = _make_repo(tmp_path)
    _write(root / "deleted.txt", "remove me\n")
    _write(root / "mode.sh", "#!/bin/sh\nexit 0\n")
    (root / "link.txt").symlink_to("old-target")
    _git(root, "add", "deleted.txt", "mode.sh", "link.txt")
    _git(root, "commit", "-m", "add tree-shape fixtures")
    _git(lane, "rebase", "master")

    (lane / "deleted.txt").unlink()
    (lane / "mode.sh").chmod(0o755)
    (lane / "link.txt").unlink()
    (lane / "link.txt").symlink_to("new-target")
    _git(lane, "add", "deleted.txt", "mode.sh", "link.txt")
    _git(lane, "commit", "-m", "change deletion mode and symlink target")
    original = _git(lane, "rev-parse", "HEAD")
    _git(lane, "tag", "lane-preserved", original)

    # This is the lossy post-squash tree: deletion resurrected, executable bit
    # removed, and symlink target reverted. No regular-file contents need be
    # missing for two of the three losses to be real.
    _git(lane, "reset", "--hard", "master")
    differing = land_lane._squash_tree_diff(
        lane, "refs/tags/lane-preserved", "refs/heads/lane"
    )

    assert differing == (
        "A\tdeleted.txt",
        "M\tlink.txt",
        "M\tmode.sh",
    ), f"tree verification failed to name every non-content loss: {differing!r}"


def test_existing_presquash_tag_is_never_force_replaced(tmp_path):
    root, lane = _make_repo(tmp_path)
    _write(lane / "one.txt", "one\n")
    _git(lane, "add", "one.txt")
    _git(lane, "commit", "-m", "first lane history")
    base_sha = _git(root, "rev-parse", "master")
    first_tip = _git(lane, "rev-parse", "HEAD")
    first = land_lane._squash_lane(lane, "lane", base_sha, first_tip)
    assert first.error is None, first.error

    _write(lane / "two.txt", "two\n")
    _git(lane, "add", "two.txt")
    _git(lane, "commit", "-m", "second lane history")
    second_tip = _git(lane, "rev-parse", "HEAD")
    second = land_lane._squash_lane(lane, "lane", base_sha, second_tip)

    assert second.new_sha is None
    assert "already exists" in (second.error or "")
    assert "refusing to replace the only recorded copy" in (second.error or "")
    assert _git(lane, "rev-parse", "refs/tags/lane-presquash") == first_tip
    assert _git(lane, "rev-parse", "refs/heads/lane") == second_tip


def test_empty_registry_refuses_with_loud_zero_denominators(landing_repo):
    root, lane = landing_repo
    forgotten = _redproof(lane, "forget", "feature.txt")
    assert forgotten.returncode == 0, forgotten.stdout + forgotten.stderr
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    # Degrade-to-zero visibility (#868): the refusal must PRINT its denominators
    # so a reader can see which population was empty. The counts themselves are
    # not pinned here — `redproof.py` builds `audit_sources` from the legacy
    # registry PLUS every launch-identity dir (two disjoint populations), so
    # "1 registry/ies across 0 launch-identity dir(s)" is the true and correct
    # reading of this fixture, not a contradiction. An earlier revision of this
    # test asserted "1 across 1" because the word "across" implies a containment
    # that does not hold, and that cost this branch a gate. #942 owns rewording
    # that message; asserting the STRUCTURE rather than its prose is what keeps
    # this test honest across the rewrite.
    assert re.search(
        r"audited \d+ registry/ies across \d+ launch-identity dir\(s\); "
        r"no injections registered",
        result.stderr,
    ), result.stderr
    assert "--require 1 was set" in result.stderr
    assert "commits examined=1" in result.stderr
    assert "registries audited=ALL DISCOVERABLE" in result.stderr
    assert "injections registered and causally caught>=1 required" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_registered_but_unchecked_injection_refuses_with_reach_denominators(
        landing_repo):
    """#948's remaining half: restored bytes are not evidence of causal reach."""
    root, lane = landing_repo
    armed = _redproof(lane, "begin", "feature.txt", "--expectation", "test_named.py")
    assert armed.returncode == 0, armed.stdout + armed.stderr
    _write(lane / "feature.txt", "second injection caught by nothing\n")
    restored = _redproof(lane, "restore", "feature.txt")
    assert restored.returncode == 0, restored.stdout + restored.stderr
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "red-proof reach: DID NOT CHECK" in result.stderr
    assert "caught 1 of 2 registered injection(s)" in result.stderr
    assert "examined 1 evidence artifact(s) for 2 registered injection(s)" in result.stderr
    assert "REFUSE phase=red-proof-history" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


@pytest.mark.parametrize(
    ("which", "dirty_file"),
    [("main", "lint-rows.txt"), ("lane", "feature.txt")],
)
def test_preflight_names_the_one_dirty_tree_and_calls_the_other_clean(
    landing_repo, which, dirty_file
):
    """#898: two trees collapse into one refusal, so it must name which.

    Direction-2 guard: a fixture that dirties BOTH trees would pass a "names
    the dirty tree" assertion vacuously. This dirties exactly one (each way
    round), asserts that precondition at runtime, then requires the message to
    name the dirty tree with its porcelain AND call the other clean.
    """
    root, lane = landing_repo
    if which == "main":
        _write(root / "lint-rows.txt", "old warning\nDIRTY\n")
        dirty_label, dirty_root = "main", root
        clean_label, clean_root = "lane", lane
    else:
        _write(lane / "feature.txt", "lane dirt\n")
        dirty_label, dirty_root = "lane", lane
        clean_label, clean_root = "main", root

    # Precondition the assertions below depend on: exactly one tree is dirty.
    main_porcelain = _git(root, "status", "--porcelain=v1", "--untracked-files=no")
    lane_porcelain = _git(lane, "status", "--porcelain=v1", "--untracked-files=no")
    if which == "main":
        assert main_porcelain and not lane_porcelain, "fixture must dirty only main"
    else:
        assert lane_porcelain and not main_porcelain, "fixture must dirty only lane"

    before = _git(root, "rev-parse", "HEAD")
    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "REFUSE phase=preflight: tracked worktree state is not clean" in result.stderr
    # The dirty tree is named by label and path, with its porcelain echoed.
    assert f"{dirty_label}={dirty_root.resolve()}" in result.stderr
    assert dirty_file in result.stderr
    # The clean tree is named and called clean — the line a both-dirty fixture hides.
    assert f"{clean_label}={clean_root.resolve()}: clean" in result.stderr
    # Preflight refuses before any detach, so the ref/HEAD/branch are untouched;
    # the tree is intentionally dirty here, so the clean-tree check is out of scope.
    assert _git(root, "rev-parse", "--verify", "refs/heads/master") == before, "master moved"
    assert _git(root, "rev-parse", "HEAD") == before, "HEAD was not restored"
    assert _git(root, "branch", "--show-current") == "master", "checkout left detached"
    _assert_retained(root, lane)


def test_success_runs_real_reap_and_retains_branch_only(landing_repo):
    root, lane = landing_repo
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py")

    assert result.returncode == 0, result.stderr
    assert (
        "gate-coverage: 6 of 6 declared gates passed: "
        "red-proof-history lint-precheck named-tests guard-selection repo-wide-guards "
        "lint-comparison"
    ) in result.stdout
    merged = _git(root, "rev-parse", "--verify", "refs/heads/master")
    assert merged != before
    assert f"advance: master {before} -> {merged} after 6 gate(s)" in result.stdout
    assert _git(root, "branch", "--show-current") == "master"
    assert (
        f"reap examined path={lane.resolve()} tracked-dirty=0 untracked=0 ignored=0 "
        "unmerged-commits=0"
    ) in result.stdout
    assert f"removed linked worktree {lane.resolve()}" in result.stdout
    assert "worktree retired by dev/reap.py" in result.stdout
    assert not lane.exists()
    assert _git(root, "show-ref", "--verify", "refs/heads/lane")


def test_reap_refusal_is_binding_when_lane_becomes_dirty_during_gates(landing_repo):
    root, lane = landing_repo
    _write(
        lane / "test_dirty_lane.py",
        "from pathlib import Path\n"
        "def test_dirty_lane():\n"
        "    Path('../lane/feature.txt').write_text('dirty after preflight\\n')\n",
    )
    _git(lane, "add", "test_dirty_lane.py")
    _git(lane, "commit", "-m", "exercise preserve refusal")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_dirty_lane.py")

    assert result.returncode == 1
    assert (
        f"reap examined path={lane.resolve()} tracked-dirty=1 untracked=0 ignored=0 "
        "unmerged-commits=0"
    ) in result.stderr
    assert "REFUSE: tracked path would be lost: feature.txt" in result.stderr
    assert "REFUSE phase=retirement: dev/reap.py refused with exit 1" in result.stderr
    # Retirement is the one refusal that legitimately follows the advance, so
    # this is where the message must say master DID move rather than "unchanged".
    landed = _git(root, "rev-parse", "--verify", "refs/heads/master")
    assert landed != before
    assert f"base: master={landed} ADVANCED from {before} by this run" in result.stderr
    _assert_retained(root, lane)


def test_gates_run_on_the_merge_commit_not_on_the_branch(landing_repo):
    """The population the gates judge must come from the merge, not the lane.

    Content alone cannot tell them apart — a rebased lane's tree and the
    --no-ff merge's tree are identical — so the probe reads git's own parent
    record, which the tree under test cannot rewrite. A gate run in the lane
    worktree, or before the merge, sees one parent and writes elsewhere.
    """
    root, lane = landing_repo
    _write(
        lane / "test_probe.py",
        "from pathlib import Path\n"
        "import subprocess\n"
        "def test_probe():\n"
        "    out = subprocess.run(['git', 'rev-list', '--parents', '-n', '1', 'HEAD'],\n"
        "        capture_output=True, text=True, check=True).stdout\n"
        "    Path('probe.txt').write_text(out)\n",
    )
    _git(lane, "add", "test_probe.py")
    _git(lane, "commit", "-m", "record the tree the gate judged")
    base_before = _git(root, "rev-parse", "--verify", "refs/heads/master")
    lane_head = _git(root, "rev-parse", "--verify", "refs/heads/lane")

    result = _run(root, "test_probe.py")

    assert result.returncode == 0, result.stderr
    probe = root / "probe.txt"
    assert probe.exists(), "the gate did not run in the main checkout at all"
    seen = probe.read_text().split()
    assert seen[1:] == [base_before, lane_head], f"gate judged {seen!r}"
    assert (
        f"merge-identity: {seen[0]} has parents master@{base_before} and lane@{lane_head}"
    ) in result.stdout
    assert _git(root, "rev-parse", "--verify", "refs/heads/master") == seen[0]


def test_a_restore_that_cannot_land_is_loud_and_master_is_still_correct(landing_repo):
    """The argument for detaching rather than merging-then-reverting.

    The named test dirties a tracked path the restore has to delete, so
    `git checkout master` genuinely fails. The refusal must say so — and
    refs/heads/master must still be right, because it never held the merge.
    """
    root, lane = landing_repo
    _write(
        lane / "test_blocks_restore.py",
        "from pathlib import Path\n"
        "def test_blocks_restore():\n"
        "    Path('feature.txt').write_text('edited during the gate\\n')\n"
        "    assert False\n",
    )
    _git(lane, "add", "test_blocks_restore.py")
    _git(lane, "commit", "-m", "dirty the path the restore must remove")
    before = _git(root, "rev-parse", "--verify", "refs/heads/master")

    result = _run(root, "test_blocks_restore.py")

    assert result.returncode == 1
    assert "REFUSE phase=named-tests: named test selection failed" in result.stderr
    assert "RESTORE FAILED:" in result.stderr
    assert "run `git checkout master` in" in result.stderr
    assert _git(root, "rev-parse", "--verify", "refs/heads/master") == before
    _assert_retained(root, lane)


@pytest.mark.parametrize(
    ("roster", "reason"),
    [
        # Both counts are len(passed)=6 over len(roster): red-proof-history now
        # appends too (#951), so the empty-roster case reads "6 of 0" and the
        # phantom case (GATES is 6 real + 1 phantom = 7) reads "6 of 7".
        ((), "only 6 of 0 declared gates ran"),
        (land_lane.GATES + ("phantom-gate",), "only 6 of 7 declared gates ran"),
    ],
)
def test_a_gate_roster_that_does_not_match_what_ran_refuses(
    landing_repo, monkeypatch, capsys, roster, reason
):
    """Assert the denominator: "every gate passed" and "no gate ran" must differ.

    An empty roster promises nothing, and a declared gate that never appended
    itself did not run — either way the base branch must stay put.
    """
    root, lane = landing_repo
    before = _git(root, "rev-parse", "--verify", "refs/heads/master")
    monkeypatch.setattr(land_lane, "GATES", roster)
    monkeypatch.chdir(root)

    assert land_lane.land("lane", ["test_named.py"]) == 1, (
        f"landed master with roster {roster!r}: a roster that does not match the "
        "gates that actually ran must refuse, not pass vacuously"
    )

    err = capsys.readouterr().err
    assert f"REFUSE phase=gate-coverage: {reason}" in err
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_every_phase_appended_to_passed_is_declared_in_gates():
    """#951: red-proof-history ran and blocked but was absent from GATES.

    Deleting its block from the running code printed ``N of N declared gates
    passed`` UNCHANGED, because a phase absent from GATES is invisible to the
    denominator — and this was the phase that enforces every red-proof. The
    GATES tuple exists (see its comment in land_lane.py) so a deleted phase is
    a REFUSAL rather than a shorter, quieter green run; that protection
    reaches ONLY phases that are declared. So any phase that appends itself to
    ``passed`` MUST appear in GATES, or its deletion is undetectable.

    Read from the tool's own source rather than naming red-proof-history by
    hand, so this catches the NEXT undeclared phase too, not just tonight's.
    The production line it binds: ``GATES = (...)`` in dev/land_lane.py — drop
    a phase from that tuple while its ``passed.append`` remains and this fails.
    """
    source = TOOL.read_text(encoding="utf-8")
    appended = set(re.findall(r'passed\.append\("([^"]+)"\)', source))
    # Precondition the check depends on (#685): a regex that matched nothing
    # would pass vacuously. Assert the parse found the phases we know append.
    assert appended, (
        "no passed.append(\"...\") calls found in dev/land_lane.py; the source "
        "parse is stale and this check is examining nothing"
    )
    undeclared = {phase for phase in appended if phase not in land_lane.GATES}
    assert not undeclared, (
        f"phases append to `passed` but are not declared in GATES: "
        f"{sorted(undeclared)}; a phase not in GATES can be deleted without "
        "changing the gate-coverage denominator, which is #951's defect"
    )


def test_gate_order_prechecks_lint_before_pytest_and_rechecks_after():
    expected = (
        "red-proof-history",
        "lint-precheck",
        "named-tests",
        "guard-selection",
        "repo-wide-guards",
        "lint-comparison",
    )

    assert land_lane.GATES == expected, (
        "phase order drifted: lint-precheck must precede named-tests and the "
        "authoritative lint-comparison must remain last; "
        f"got {land_lane.GATES!r}"
    )


def _empty_registry(lane: Path, path: str) -> None:
    """Leave a READABLE but empty red-proof registry for this lane.

    Historically this armed-then-forgot workaround kept a registry on disk so
    that `redproof.py check` did not FAULT on the no-registry blind case while
    that case was still #949's unfixed second half. #955 made an absent
    registry the EXPECTED state when nothing was required, so the workaround is
    no longer load-bearing for correctness — but it keeps this lane's audit
    path in MODE A (a registry exists) rather than the blind case, which is the
    variable this test isolates: with the registry readable, does the DERIVED
    `--require 0` let a documentation-only branch land where `--require 1`
    refused it?
    """
    armed = _redproof(lane, "begin", path, "--expectation", "test_named.py")
    assert armed.returncode == 0, armed.stdout + armed.stderr
    forgotten = _redproof(lane, "forget", path)
    assert forgotten.returncode == 0, forgotten.stdout + forgotten.stderr


@pytest.fixture
def doc_only_repo(tmp_path: Path):
    """A lane whose entire diff is one inert document — cx-944corpus's shape."""
    root, lane = _make_repo(tmp_path)
    _write(lane / ".dreamwork" / "docs" / "census.md", "a re-runnable census\n")
    _git(lane, "add", ".dreamwork/docs/census.md")
    _git(lane, "commit", "-m", "one inert document")
    return root, lane


@pytest.fixture
def plan_with_doc_map_repo(tmp_path: Path):
    """A new plan plus the doc-map row lint requires beside it."""
    root, lane = _make_repo(tmp_path)
    _write(lane / ".dreamwork/docs/plans/foo.md", "# New plan\n")
    _write(
        lane / ".dreamwork/docs/doc-map.md",
        "| `.dreamwork/docs/plans/` | Plans (foo) | add a row per plan |\n",
    )
    _git(
        lane,
        "add",
        ".dreamwork/docs/plans/foo.md",
        ".dreamwork/docs/doc-map.md",
    )
    _git(lane, "commit", "-m", "plan plus required doc-map row")
    return root, lane


def test_documentation_only_branch_requires_no_injection_and_lands(doc_only_repo):
    """A documentation-only gate must not manufacture a false-green.

    `--require 1` was unconditional, so the only route through for a lane that
    obeyed its brief was to fake an injection into a file it had no reason to
    touch — the exact act this exemption exists to prevent.
    """
    root, lane = doc_only_repo
    _empty_registry(lane, ".dreamwork/docs/census.md")
    before = _git(root, "rev-parse", "--verify", "refs/heads/master")
    # The precondition this test's meaning depends on, read BEFORE the gate
    # because a successful landing reaps the lane worktree: the diff really is
    # one documentation path. A fixture that changed code too would make the
    # requirement line below unreachable while the assertion still read well.
    assert _git(lane, "diff", "--name-only", "master", "lane").split() == [
        ".dreamwork/docs/census.md"
    ]

    result = _run(root, "test_named.py")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        "diff-classification: 1 changed path(s); 1 inert documentation; "
        "0 that a red-proof could bind"
    ) in result.stdout
    assert "red-proof requirement: 0 injections REQUIRED" in result.stdout
    assert "injections registered and causally caught>=0 required" in result.stdout
    assert "gate-coverage: 6 of 6 declared gates passed" in result.stdout
    assert _git(root, "rev-parse", "--verify", "refs/heads/master") != before


def test_unreadable_registry_at_require_zero_names_its_cause_not_absence(
        doc_only_repo, monkeypatch):
    """#1038 Finding 1 integration: a registry that is PRESENT but UNREADABLE
    (a chmod 000 parent) must not make land_lane tell the operator 'can locate
    no registry' or attribute the fault to #949's absent-registry case. The
    note in land_lane's FAULT clause was written when exit-2-at-require-0 meant
    the absent-registry blind case; #1038 made unreadable registries fault too,
    so the old note now asserts something false — the operator gets redproof's
    true FAULT and then a false explanation that sends them looking for a
    missing file when the cause is a permission bit they could fix in one
    command.

    This goes through the land_lane path (not redproof directly) because the
    defect is in land_lane's composition of redproof's output (#1038 F1 D2):
    a user of ``just land-lane`` never reads redproof's stdout directly.

    Direction 2 guards: (a) asserting the bad text is *absent* passes if the
    note is deleted entirely, so the test also asserts a CAUSE-SPECIFIC clause
    IS present; (b) a substring shared by both branches passes either way, so
    the asserted clause is the one unique to the unreadable cause.
    """
    import os
    root, lane = doc_only_repo
    assert _git(lane, "diff", "--name-only", "master", "lane").split() == [
        ".dreamwork/docs/census.md"
    ], "precondition: doc-only diff so --require derives to 0"

    # Create a launch-identity dir holding a registry.json, then make its
    # redproof dir unreadable so redproof faults at the read.
    monkeypatch.setenv("DREAMWORK_LANE_ID", "unreadable-1038")
    armed = _redproof(lane, "begin", ".dreamwork/docs/census.md",
                      "--expectation", "test_named.py")
    assert armed.returncode == 0, armed.stdout + armed.stderr
    forgotten = _redproof(lane, "forget", ".dreamwork/docs/census.md")
    assert forgotten.returncode == 0, forgotten.stdout + forgotten.stderr
    monkeypatch.delenv("DREAMWORK_LANE_ID", raising=False)

    import dev.redproof as rp
    idirs = rp._ls.lane_identity_dirs(lane)
    assert len(idirs) == 1, f"precondition: one identity dir, got {len(idirs)}"
    reg_dir = rp._redproof_dir(lane, idirs[0].name, rp._role(lane))
    reg = reg_dir / "registry.json"
    assert reg.exists(), "precondition: registry.json exists and is readable"
    os.chmod(reg_dir, 0o000)
    try:
        assert not reg.exists(), (
            "precondition: exists() must return False under chmod 000 — "
            "if not, the test runs as root or a mode-ignoring fs and "
            "proves nothing")
        result = _run(root, "test_named.py")
        assert result.returncode == 1, (
            "an unreadable registry must REFUSE, not pass:\n" + result.stderr)
        # Extract the REFUSE line — the note lives inside it, distinct from
        # the relayed redproof stderr that precedes it.
        refuse_lines = [
            line for line in result.stderr.splitlines()
            if "REFUSE phase=red-proof-history" in line
        ]
        assert refuse_lines, (
            "expected a REFUSE phase=red-proof-history line:\n" + result.stderr)
        refuse_line = refuse_lines[0]
        # Direction 1: the false attribution must be gone.
        assert "can locate no registry" not in refuse_line, (
            "land_lane's note told the operator the registry is absent when "
            "it exists but is unreadable:\n" + refuse_line)
        assert "#949" not in refuse_line, (
            "land_lane's note attributed an unreadable-registry fault to "
            "#949's absent-registry case:\n" + refuse_line)
        # Direction 2: the cause-specific clause must be present — this is
        # what catches a fix that just deletes the note. "permission issue"
        # is unique to the note, not to redproof's relayed stderr.
        assert "permission issue" in refuse_line, (
            "land_lane's note must name the unreadable cause specifically "
            "(permission issue), not just omit the false one:\n"
            + refuse_line)
    finally:
        os.chmod(reg_dir, 0o755)


def test_unreadable_parent_with_no_registry_does_not_assert_existence(
        doc_only_repo, monkeypatch):
    """#1038 Finding 1 (round 4): when the parent dir is unreadable and there
    is NO registry.json inside it, the cause note must NOT say the registry
    exists — redproof only establishes "not confirmed absent," and the
    registry may genuinely not be there. Round 3 fixed "absent" → "exists,"
    which moved the overclaim one notch: "exists" is equally false when the
    file is not there. #136's third state is "could not determine," not
    "exists," and the note must say that.

    This is a DIFFERENT fixture from ``test_unreadable_registry_at_require_zero``
    (which creates a registry.json then chmods its parent): here no registry
    exists at all, so the note's "exists" assertion is flatly wrong rather
    than merely unprovable. The fixture deletes registry.json after begin/
    forget so the identity dir is discoverable but the file is gone.

    Direction 2 guards: (a) asserting "registry exists" is absent passes if
    the note is deleted entirely, so the test also asserts "not confirmed" IS
    present — the undetermined state named explicitly; (b) "permission issue"
    must still be present so the cause-specific clause survives the reword."""
    import os
    root, lane = doc_only_repo
    assert _git(lane, "diff", "--name-only", "master", "lane").split() == [
        ".dreamwork/docs/census.md"
    ], "precondition: doc-only diff so --require derives to 0"

    # Create the identity dir + redproof dir via begin/forget, then REMOVE
    # registry.json so the scenario is: identity dir exists, redproof dir
    # exists, but no registry file inside it — and the dir is unreadable.
    monkeypatch.setenv("DREAMWORK_LANE_ID", "no-registry-1038")
    armed = _redproof(lane, "begin", ".dreamwork/docs/census.md",
                      "--expectation", "test_named.py")
    assert armed.returncode == 0, armed.stdout + armed.stderr
    forgotten = _redproof(lane, "forget", ".dreamwork/docs/census.md")
    assert forgotten.returncode == 0, forgotten.stdout + forgotten.stderr
    monkeypatch.delenv("DREAMWORK_LANE_ID", raising=False)

    import dev.redproof as rp
    idirs = rp._ls.lane_identity_dirs(lane)
    assert len(idirs) == 1, f"precondition: one identity dir, got {len(idirs)}"
    reg_dir = rp._redproof_dir(lane, idirs[0].name, rp._role(lane))
    reg = reg_dir / "registry.json"
    assert reg.exists(), "precondition: begin/forget created registry.json"
    reg.unlink()  # the no-registry case: the file is genuinely gone
    assert not reg.exists(), "precondition: registry.json deleted"
    os.chmod(reg_dir, 0o000)
    try:
        assert not reg.exists(), (
            "precondition: exists() must return False under chmod 000 — "
            "if not, the test runs as root or a mode-ignoring fs and "
            "proves nothing")
        result = _run(root, "test_named.py")
        assert result.returncode == 1, (
            "an unreadable parent with no registry must REFUSE, not pass:\n"
            + result.stderr)
        refuse_lines = [
            line for line in result.stderr.splitlines()
            if "REFUSE phase=red-proof-history" in line
        ]
        assert refuse_lines, (
            "expected a REFUSE phase=red-proof-history line:\n" + result.stderr)
        refuse_line = refuse_lines[0]
        # Direction 1: the overclaim. "registry exists" asserts a fact
        # redproof did not establish — the file may not be there at all.
        assert "registry exists" not in refuse_line, (
            "land_lane's note asserted the registry exists when there is no "
            "registry file — only the parent's unreadability was "
            "established:\n" + refuse_line)
        # Direction 2: the undetermined state must be named, not collapsed
        # into a generic "a registry problem." This catches a fix that
        # deletes the note or vagues it out.
        assert "not confirmed" in refuse_line, (
            "land_lane's note must name the undetermined state ('not "
            "confirmed') rather than asserting existence or absence:\n"
            + refuse_line)
        # Direction 2: the cause-specific clause survives the reword.
        assert "permission issue" in refuse_line, (
            "land_lane's note must still name the permission cause after "
            "rewording:\n" + refuse_line)
    finally:
        os.chmod(reg_dir, 0o755)


def test_plan_plus_required_doc_map_row_lands_without_an_injection(
    plan_with_doc_map_repo,
):
    """The gate, not only its classifier, admits #1032's complete diff."""
    root, lane = plan_with_doc_map_repo
    before = _git(root, "rev-parse", "--verify", "refs/heads/master")
    assert _git(lane, "diff", "--name-only", "master", "lane").split() == [
        ".dreamwork/docs/doc-map.md",
        ".dreamwork/docs/plans/foo.md",
    ]

    result = _run(root, "test_named.py")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        "diff-classification: 2 changed path(s); 1 inert documentation; "
        "1 that a red-proof could bind"
    ) in result.stdout
    assert "red-proof requirement: 0 injections REQUIRED" in result.stdout
    assert (
        "lint-precheck and lint-comparison: .dreamwork/docs/doc-map.md"
        in result.stdout
    )
    assert "gate-coverage: 6 of 6 declared gates passed" in result.stdout
    assert _git(root, "rev-parse", "--verify", "refs/heads/master") != before


def test_real_code_beside_a_doc_map_row_still_requires_an_injection(
    plan_with_doc_map_repo,
):
    """The narrow credit must not exempt a mixed documentation/code diff."""
    root, lane = plan_with_doc_map_repo
    _write(lane / "dev/feature.py", "VALUE = 1\n")
    _git(lane, "add", "dev/feature.py")
    _git(lane, "commit", "-m", "real code beside the plan")
    before = _git(root, "rev-parse", "--verify", "refs/heads/master")
    assert _git(lane, "diff", "--name-only", "master", "lane").split() == [
        ".dreamwork/docs/doc-map.md",
        ".dreamwork/docs/plans/foo.md",
        "dev/feature.py",
    ]

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "red-proof requirement: 1 injection required" in result.stdout
    assert "red-proof must bind: dev/feature.py" in result.stdout
    assert (
        "already covered by lint-precheck and lint-comparison: "
        ".dreamwork/docs/doc-map.md"
    ) in result.stdout
    assert "1 injection(s) were required (--require)" in result.stderr
    _assert_base_unmoved(root, before)


@pytest.mark.parametrize(
    "beside", ["feature.txt", "briefs/frame.md", ".dreamwork/tasks.md"]
)
def test_one_document_does_not_lower_the_bar_for_what_is_beside_it(doc_only_repo, beside):
    """`briefs/frame.md` is the sharp case: a `.md` compiled into every dispatch.

    A change to it is a behavioural change to the whole loop, so a classifier
    that reads it as documentation would exempt the loudest thing on the page.
    """
    root, lane = doc_only_repo
    _write(lane / beside, "not documentation\n")
    _git(lane, "add", beside)
    _git(lane, "commit", "-m", f"add {beside} beside the doc")
    _empty_registry(lane, beside)
    before = _git(root, "rev-parse", "--verify", "refs/heads/master")
    changed = _git(lane, "diff", "--name-only", "master", "lane").split()
    assert changed == sorted([".dreamwork/docs/census.md", beside]), changed

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert (
        "red-proof requirement: 1 injection required — 1 of 2 changed path(s) "
        "are NOT inert documentation, so a behavioural red-proof could bind "
        f"them: {beside}"
    ) in result.stdout
    assert "--require 1 was set" in result.stderr
    _assert_base_unmoved(root, before)


@pytest.mark.parametrize(
    "doc",
    [
        "briefs/frame.md",             # concatenated into every dispatched prompt
        "SKILL.md",                    # the loop's own instructions
        "watch-design.md",             # lint.py audits it
        ".dreamwork/lessons.md",       # dev/lessons_index.py parses its heads
        ".dreamwork/tasks.md",         # dev/ledger.py's store
        ".dreamwork/docs/doc-map.md",  # lint.py check_doc_map_plans parses its rows
    ],
)
def test_a_markdown_file_that_is_a_program_is_not_inert(doc):
    assert land_lane._is_inert_doc(".dreamwork/docs/census-2026-08-02.md"), (
        "the positive case must hold at runtime, or every row below passes "
        "vacuously against a classifier that calls nothing inert"
    )
    assert not land_lane._is_inert_doc(doc), (
        f"{doc} is executable input, so the conservative classifier must keep "
        "it binding even when a downstream requirement credits separate "
        "checker coverage"
    )


def test_an_empty_diff_is_not_a_documentation_exemption():
    """#868: zero changed paths must not read as "zero required"."""
    empty = land_lane.Diff(changed=(), inert=(), binding=(), tests=())
    assert empty.required_injections == 1
    assert "the diff is EMPTY" in land_lane._requirement_line(empty)


def test_a_node_id_does_not_count_as_naming_the_whole_file():
    """#936's eleven failures spanned five classes; naming one is not coverage."""
    assert land_lane._named_files(["./test_lint.py"]) == {"test_lint.py"}
    assert land_lane._named_files(["test_lint.py::TestOne"]) == frozenset()


# ── #953: import-graph and directory-map derivation ────────────────────
# The name convention finds tests NAMED FOR a module. It missed #949's own
# breakage: dev/land_lane.py changed, the convention derived test_land_lane.py,
# but the break was in test_suite_baseline.py, which does `from dev import
# land_lane`. Two mechanisms close the two cases the convention cannot reach.


def test_dotted_module_maps_a_py_path_to_its_import_name():
    """The bridge between a changed path and the AST import that references it."""
    assert land_lane._dotted_module("dev/land_lane.py") == "dev.land_lane"
    assert land_lane._dotted_module("lint.py") == "lint"
    assert land_lane._dotted_module("dev/capture/gitrow.mjs") is None  # not Python
    assert land_lane._dotted_module("dev/__init__.py") is None  # package marker


def test_import_targets_catches_from_import_not_prose_mention():
    """The guardrail that keeps this from becoming the full-suite run.

    `from dev import land_lane` is an import and MUST match. A bare mention of
    the module name in a docstring or comment MUST NOT — that is how
    test_brief.py would be dragged in for nothing, which is #949's ACCEPTED
    COST paragraph in the other direction.
    """
    targets = land_lane._import_targets(
        "from dev import land_lane, suite_baseline\n"
        "import dev.land_lane as ll\n"
        "from dev.land_lane import GATES\n"
        "# land_lane is mentioned here in prose only\n"
        "import os\n"
    )
    assert "dev.land_lane" in targets
    assert "dev" in targets
    assert "os" in targets
    # A relative import carries no absolute module name and is excluded.
    assert land_lane._import_targets("from . import x\n") == frozenset()
    assert land_lane._import_targets("this is not python\n") == frozenset()


def test_import_derived_finds_a_test_that_imports_the_changed_module(tmp_path):
    """#949's blind spot, reproduced: the cross-named test is now derived.

    A changed dev/land_lane.py is covered by a test that does `from dev import
    land_lane` under a different filename. The name convention yields
    test_land_lane.py; the import graph yields the cross-named test too.
    Production line this binds: the membership check in _import_derived — drop
    the `from dev import land_lane` target and this test goes red naming it.
    """
    (tmp_path / "test_cross.py").write_text("from dev import land_lane\n")
    (tmp_path / "test_other.py").write_text("import os\n")
    found = land_lane._import_derived(tmp_path, ["dev.land_lane"])
    assert found == ("test_cross.py",), (
        f"expected the cross-named importer test_cross.py, got {found!r}"
    )


def test_import_derived_reaches_a_test_through_one_consumer(tmp_path):
    """The shipped #991 shape: changed -> consumer -> observing test."""
    (tmp_path / "watch.py").write_text("VALUE = 1\n")
    (tmp_path / "tick_line.py").write_text("import watch\n")
    (tmp_path / "test_tick_line.py").write_text("import tick_line\n")

    shallow = land_lane._import_derived(tmp_path, ["watch"], depth=1)
    found = land_lane._import_derived(tmp_path, ["watch"], depth=2)

    assert "test_tick_line.py" not in shallow
    assert "test_tick_line.py" in found, (
        "depth-2 import derivation missed test_tick_line.py; the shallow "
        f"direct-import selection was {shallow!r}"
    )


def test_import_derived_sees_a_consumer_import_inside_a_function(tmp_path):
    """ast.walk includes statically written imports below module scope."""
    (tmp_path / "watch.py").write_text("VALUE = 1\n")
    (tmp_path / "consumer.py").write_text(
        "def value():\n    import watch\n    return watch.VALUE\n"
    )
    (tmp_path / "test_consumer.py").write_text("import consumer\n")

    assert land_lane._import_derived(
        tmp_path, ["watch"], depth=2
    ) == ("test_consumer.py",)


def test_production_importers_skip_a_registered_in_repo_worktree(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "master")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _write(repo / ".gitignore", ".native-lanes/\n")
    _write(repo / "subject.py", "VALUE = 1\n")
    _write(repo / "consumer.py", "import subject\n")
    _write(repo / ".native-lanes-notes" / "consumer.py", "import subject\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture")

    in_repo = repo / ".native-lanes" / "lane"
    external = tmp_path / "external-lane"
    _git(repo, "worktree", "add", "-b", "in-repo", str(in_repo))
    _git(repo, "worktree", "add", "-b", "external", str(external))
    listing = _git(repo, "worktree", "list", "--porcelain")
    assert f"worktree {in_repo.resolve()}" in listing, (
        "fixture did not register the in-repo worktree, so the exclusion "
        "assertion would pass vacuously"
    )

    roots = land_lane._in_repo_worktree_roots(repo)
    found = land_lane._production_importers(repo, ["subject"])

    assert roots == (Path(".native-lanes/lane"),), (
        "only the registered worktree nested below the repo is an exclusion "
        f"root; the external worktree must remain outside it: {roots!r}"
    )
    assert "consumer" in found
    assert ".native-lanes.lane.consumer" not in found, (
        "the registered in-repo worktree leaked a duplicate second-copy "
        f"module into production importers: {sorted(found)!r}"
    )
    assert ".native-lanes-notes.consumer" in found, (
        "a legitimate source path sharing only the worktree-root prefix was "
        f"excluded: {sorted(found)!r}"
    )


def test_depth_two_reports_but_does_not_select_a_third_hop(tmp_path):
    """Direction 2: one more consumer is the chosen selection boundary."""
    (tmp_path / "watch.py").write_text("VALUE = 1\n")
    (tmp_path / "middle.py").write_text("import watch\n")
    (tmp_path / "top.py").write_text("import middle\n")
    (tmp_path / "test_top.py").write_text("import top\n")

    selected = land_lane._import_derived(tmp_path, ["watch"], depth=2)
    reported = land_lane._import_derived(tmp_path, ["watch"], depth=3)

    assert "test_top.py" not in selected
    assert reported == ("test_top.py",)


def test_import_cycle_terminates_and_keeps_the_reachable_test(tmp_path):
    """The visited set closes a cycle before a large requested depth."""
    (tmp_path / "watch.py").write_text("VALUE = 1\n")
    (tmp_path / "left.py").write_text("import watch\nimport right\n")
    (tmp_path / "right.py").write_text("import left\n")
    (tmp_path / "test_right.py").write_text("import right\n")

    assert land_lane._import_derived(
        tmp_path, ["watch"], depth=100
    ) == ("test_right.py",)


def test_subprocess_observer_has_no_import_edge_even_at_report_depth(tmp_path):
    """Direction 2: a subprocess/file effect remains a genuine false-green."""
    (tmp_path / "watch.py").write_text("VALUE = 1\n")
    (tmp_path / "consumer.py").write_text("import watch\nprint(watch.VALUE)\n")
    (tmp_path / "test_cli.py").write_text(
        "import subprocess\n"
        "def test_cli():\n"
        "    subprocess.run(['python3', 'consumer.py'], check=True)\n"
    )

    assert land_lane._import_derived(
        tmp_path, ["watch"], depth=land_lane.IMPORT_REPORT_DEPTH
    ) == ()


def test_directory_map_matches_a_changed_file_under_it():
    """The gitrow.mjs case: no test names or imports it; a directory map does."""
    targets, dirs = land_lane._map_derived(["dev/capture/gitrow.mjs", "README.md"])
    assert dirs == ("dev/capture/",)
    assert "test_guard_evidence.py" in targets
    assert "test_guard_argv.py" in targets
    # A path that touches nothing under a mapped dir contributes no targets, so
    # an unrelated landing is never blocked by that dir's entry.
    empty_targets, empty_dirs = land_lane._map_derived(["watch.py"])
    assert empty_targets == () and empty_dirs == ()


def test_a_test_importing_a_changed_module_is_run_even_unnamed(landing_repo):
    """Direction 1 for #953: the widened derivation names the import case.

    The real land_lane/test_suite_baseline pair is the fixture, made concrete:
    the lane changes a module, and a test that IMPORTS it (under a name the
    convention cannot derive) is added to the selection and RUN. Before #953 the
    convention derived only the name-shaped test and this one ran only if the
    coordinator happened to name it.
    """
    root, lane = landing_repo
    # A module on master that a cross-named test will import.
    _write(root / "dev" / "thingmod.py", "VALUE = 1\n")
    _git(root, "add", "dev/thingmod.py")
    _git(root, "commit", "-m", "add thingmod")
    # A test that imports thingmod under a different name and asserts the value
    # the lane is about to flip — so if it is NOT run, master advances red.
    _write(
        root / "test_covers_thingmod.py",
        "from dev import thingmod\n"
        "def test_covers_thingmod():\n"
        "    assert thingmod.VALUE == 1, 'lane flipped VALUE and this ran'\n",
    )
    _git(root, "add", "test_covers_thingmod.py")
    _git(root, "commit", "-m", "cross-named test imports thingmod")
    _git(lane, "rebase", "master")
    # The lane flips the value the cross-named test pins.
    _write(lane / "dev" / "thingmod.py", "VALUE = 2\n")
    _git(lane, "add", "dev/thingmod.py")
    _git(lane, "commit", "-m", "flip VALUE")
    before = _git(root, "rev-parse", "--verify", "refs/heads/master")

    result = _run(root, "test_named.py")

    assert result.returncode == 1, (
        "master ADVANCED though the only test covering the changed module was a "
        "cross-named importer the coordinator did not name: the import graph "
        "should have derived and RUN it, which is #953's whole point"
    )
    assert "import=1" in result.stdout, (
        "the import-graph rule should report one derived test for a changed "
        "module a cross-named test imports"
    )
    assert "test_covers_thingmod.py" in result.stdout
    assert "derived-and-added=['test_covers_thingmod.py']" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_a_test_reached_through_one_consumer_is_run_even_unnamed(landing_repo):
    """Direction 1: the gate RUNS the depth-2 test, not only a helper."""
    root, lane = landing_repo
    _write(root / "dev" / "thingmod.py", "VALUE = 1\n")
    _write(
        root / "dev" / "consumer.py",
        "from dev import thingmod\nVALUE = thingmod.VALUE\n",
    )
    _write(
        root / "test_observes_consumer.py",
        "from dev import consumer\n"
        "def test_observes_consumer():\n"
        "    assert consumer.VALUE == 1, 'depth-2 observing test ran'\n",
    )
    _git(root, "add", "dev/thingmod.py", "dev/consumer.py",
         "test_observes_consumer.py")
    _git(root, "commit", "-m", "add a test through one consumer")
    _git(lane, "rebase", "master")
    _write(lane / "dev" / "thingmod.py", "VALUE = 2\n")
    _git(lane, "add", "dev/thingmod.py")
    _git(lane, "commit", "-m", "flip depth-2 observed value")
    before = _git(root, "rev-parse", "--verify", "refs/heads/master")

    result = _run(root, "test_named.py")

    assert result.returncode == 1, (
        "master ADVANCED though test_observes_consumer.py watches the changed "
        "module through one consumer; shallow derivation missed "
        "test_observes_consumer.py"
    )
    assert "test_observes_consumer.py" in result.stdout
    assert "0 direct; 1 added through one consumer" in result.stdout
    assert "derived-and-added=['test_observes_consumer.py']" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_a_stale_directory_map_target_refuses_rather_than_running_silent(landing_repo):
    """Direction 2 for #953: the map's own weakness, closed where it can be.

    The map's whole weakness is that a target can exist but stop scanning the
    directory — not cheaply machine-checkable, left open. But the SHARPER stale
    case, a target that no longer exists AT ALL, IS checkable, and landing
    through a map pointing at nothing would be 'named a file that exists but is
    irrelevant → GREEN' one level meta. So when a changed path matches a mapped
    dir and a target is absent, the gate refuses naming the stale entry.
    """
    root, lane = landing_repo
    # dev/capture/ is mapped to two tests this minimal fixture does not hold —
    # so a change under it makes the map point at targets absent from the tree,
    # which is the stale-map shape (a real repo reaches it by deleting a target).
    _write(lane / "dev" / "capture" / "touched.mjs", "// change\n")
    _git(lane, "add", "dev/capture/touched.mjs")
    _git(lane, "commit", "-m", "touch a file under a mapped directory")
    before = _git(root, "rev-parse", "--verify", "refs/heads/master")

    result = _run(root, "test_named.py")

    assert result.returncode == 1, (
        "master ADVANCED though the directory map targeted a test absent from "
        "the merged tree: a stale map must refuse, not run silent"
    )
    assert "REFUSE phase=named-tests" in result.stderr
    assert "directory" in result.stderr and "testset map" in result.stderr
    assert "absent" in result.stderr.lower()
    assert "test_guard_evidence.py" in result.stderr
    assert "update DIR_TESTSET_MAP" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_a_derived_test_the_coordinator_did_not_name_is_run_anyway(landing_repo):
    """#936's exact shape: `lint.py` changed, `test_lint.py` existed, unnamed.

    Eleven failures then sat on master for about two hours. Reporting the
    omission would not have caught it — the gate's honest `full repo suite NOT
    RUN` line was already there to be read past — so the derived test is RUN.
    """
    root, lane = landing_repo
    _write(root / "test_lint.py", "def test_lint(): assert False\n")
    _git(root, "add", "test_lint.py")
    _git(root, "commit", "-m", "a red test_lint.py, unnamed by the coordinator")
    _git(lane, "rebase", "master")
    _write(
        lane / "lint.py",
        "# a change to lint.py whose test nobody named\n"
        "from pathlib import Path\n"
        "p = Path('lint-rows.txt')\n"
        "rows = p.read_text().splitlines() if p.exists() else []\n"
        "for row in rows: print('  WARN  ' + row)\n"
        "print(f'clean ({len(rows)} warning(s))')\n",
    )
    _git(lane, "add", "lint.py")
    _git(lane, "commit", "-m", "change lint.py")
    before = _git(root, "rev-parse", "--verify", "refs/heads/master")

    result = _run(root, "test_named.py")

    assert result.returncode == 1, (
        "master ADVANCED with a red test_lint.py that covers a file this branch "
        "changed: the derived test was reported but never run, which is #936 exactly"
    )
    assert (
        "derived-tests: 1 required test(s) from 2 changed path(s) by 3 rules "
        "[name=1 import=0 map=0]: test_lint.py"
    ) in result.stdout
    assert "1 were NOT named and have been ADDED: test_lint.py" in result.stdout
    assert "REFUSE phase=named-tests: named test selection failed" in result.stderr
    assert "derived-and-added=['test_lint.py']" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_zero_derived_tests_says_why_rather_than_reading_as_coverage(doc_only_repo):
    """#948's trap: "derived 0 required tests" is exactly how the defect hides."""
    root, lane = doc_only_repo
    _empty_registry(lane, ".dreamwork/docs/census.md")

    result = _run(root, "test_named.py")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "derived-tests: 0 required tests from 1 changed path(s)" in result.stdout
    assert "This is NOT coverage" in result.stdout
    assert "rests entirely on the named selection" in result.stdout


def test_relevance_warns_when_test_brief_cannot_relate_to_redproof(tmp_path):
    """#948 direction 1: the real irrelevant-but-existing selection is named.

    `test_brief.py` passes, but none of #953's three rules relates it to a
    branch that changes only `dev/redproof.py`. The advisory must name the
    test and both denominators without turning the incomplete model into a
    refusal.
    """
    root, lane = _make_repo(tmp_path)
    _write(root / "dev" / "redproof.py", "VALUE = 1\n")
    _write(root / "test_brief.py", "def test_brief(): assert True\n")
    _git(root, "add", "dev/redproof.py", "test_brief.py")
    _git(root, "commit", "-m", "add redproof and an unrelated passing test")
    _git(lane, "rebase", "master")
    _write(lane / "dev" / "redproof.py", "VALUE = 2\n")
    _git(lane, "add", "dev/redproof.py")
    _git(lane, "commit", "-m", "change only redproof")
    armed = _redproof(lane, "begin", "dev/redproof.py", "--expectation", "test_brief.py")
    assert armed.returncode == 0, armed.stdout + armed.stderr
    _write(lane / "dev" / "redproof.py", "VALUE = 999\n")
    observed = _redproof(
        lane, "observe", "dev/redproof.py", "--failure", "redproof injection reached",
        "--command", sys.executable, "-c",
        "from pathlib import Path; assert Path('dev/redproof.py').read_text() == "
        "'VALUE = 2\\n', 'redproof injection reached'",
    )
    assert observed.returncode == 0, observed.stdout + observed.stderr
    restored = _redproof(lane, "restore", "dev/redproof.py")
    assert restored.returncode == 0, restored.stdout + restored.stderr

    result = _run(root, "test_brief.py")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        "test-relevance: WARN — examined 1 selected test(s) against 1 changed "
        "path(s); 1 unrelated-as-far-as-the-3-rules-can-tell: test_brief.py"
    ) in result.stdout
    assert "remedy: name or add a test related by" in result.stdout


def test_relevance_does_not_call_an_empty_changed_population_a_pass(tmp_path):
    line = land_lane._test_relevance_line(tmp_path, ["test_brief.py"], [])
    assert line.startswith(
        "test-relevance: DID NOT CHECK — examined 1 selected test(s) against 0 changed path(s)"
    )
    assert "no relevance result is available" in line


def test_relevance_import_under_try_is_a_known_false_green(tmp_path):
    """#948 direction 2: static import reach is not runtime execution reach."""
    _write(
        tmp_path / "test_optional.py",
        "try:\n"
        "    from dev import redproof\n"
        "except ImportError:\n"
        "    redproof = None\n"
        "def test_unrelated(): assert True\n",
    )

    line = land_lane._test_relevance_line(
        tmp_path, ["test_optional.py"], ["dev/redproof.py"]
    )

    assert line.startswith("test-relevance: OK — examined 1 selected test(s) against 1 changed path(s)")
    assert "all 1 related by at least one of the 3 rules" in line


def test_a_doc_only_lane_with_no_registry_lands_because_none_was_required(
    doc_only_repo,
):
    """#955: the fix to #949's unfixed second half, pinned where the next reader
    will meet it.

    A doc-only lane (0 injections required) that registered NOTHING — so there
    is no registry at all — used to be refused by the gate, because
    `dev/redproof.py check` FAULTed on an absent registry independently of
    `--require`. That was the state cx-944corpus was blocked in. After #955, an
    absent registry is the EXPECTED state when nothing was required and no
    launch identity ran, so the lane LANDS. What `land_lane.py` now relays is
    redproof's own pass line ("no injection required and none registered") —
    #940's ruling preserved: a pass that says WHY (0 required) and carries the
    denominator, not an all-clear.
    """
    root, lane = doc_only_repo
    before = _git(root, "rev-parse", "--verify", "refs/heads/master")

    result = _run(root, "test_named.py")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "red-proof requirement: 0 injections REQUIRED" in result.stdout
    # redproof's blind-case pass line reaches the gate's stdout via _relay
    # (redproof prints it; land_lane._relay maps subprocess stdout -> stdout).
    assert "no injection required and none registered" in result.stdout
    assert "audited 0 registry/ies across 0 launch-identity dir(s)" in result.stdout
    assert "could not locate ANY lane scratch" not in result.stdout + result.stderr
    assert "NOTE this FAULT" not in result.stdout + result.stderr
    # The lane LANDS, so master advances by design (the old test asserted base
    # unmoved because the gate refused; that inversion is the whole point).
    assert _git(root, "rev-parse", "--verify", "refs/heads/master") != before


def test_land_tool_contains_no_second_worktree_removal_route():
    source = TOOL.read_text(encoding="utf-8")
    assert '"worktree", "remove"' not in source
    assert 'Path(__file__).with_name("reap.py")' in source


def test_just_recipe_requires_branch_but_leaves_empty_tests_for_named_refusal():
    result = subprocess.run(
        ["just", "--dry-run", "land-lane", "lane", "test_land_lane.py"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "python3 dev/land_lane.py lane test_land_lane.py" in result.stderr
