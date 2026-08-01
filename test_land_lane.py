from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest


REPO = Path(__file__).resolve().parent
TOOL = REPO / "dev" / "land_lane.py"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def landing_repo(tmp_path: Path):
    root = tmp_path / "repo"
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
    _write(root / "test_guard.py", "def test_guard(): assert True\n")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "base")
    _git(root, "worktree", "add", "-b", "lane", str(lane), "master")
    _write(lane / "feature.txt", "lane\n")
    _git(lane, "add", "feature.txt")
    _git(lane, "commit", "-m", "lane change")
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


def test_empty_named_selection_refuses_before_merge(landing_repo):
    root, lane = landing_repo
    before = _git(root, "rev-parse", "HEAD")
    result = _run(root)

    assert result.returncode == 1
    assert "REFUSE phase=selection: named test selection is empty" in result.stderr
    assert "named tests=0" in result.stderr
    assert _git(root, "rev-parse", "HEAD") == before
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

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert f"REFUSE phase=guard-selection: {message}" in result.stderr
    assert "deliberately did not perform: dev/reap.py lane retirement" in result.stderr
    _assert_retained(root, lane)


@pytest.mark.parametrize(
    "lint_body",
    ["raise SystemExit(2)\n", "print('lint ran but omitted its trailer')\n"],
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
    assert _git(root, "rev-parse", "HEAD") == before
    _assert_retained(root, lane)


def test_new_warn_row_refuses_and_retains_lane(landing_repo):
    root, lane = landing_repo
    _write(lane / "lint-rows.txt", "old warning\nnew warning\n")
    _git(lane, "add", "lint-rows.txt")
    _git(lane, "commit", "-m", "add warning")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "lint WARN row-set comparison: added=1 removed=0" in result.stdout
    assert "REFUSE phase=lint-comparison: WARN row set changed" in result.stderr
    _assert_retained(root, lane)


def test_same_warn_count_with_different_rows_refuses(landing_repo):
    root, lane = landing_repo
    _write(lane / "lint-rows.txt", "new warning\n")
    _git(lane, "add", "lint-rows.txt")
    _git(lane, "commit", "-m", "replace warning")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "lint WARN row-set comparison: added=1 removed=1" in result.stdout
    assert "+   WARN  new warning" in result.stdout
    assert "-   WARN  old warning" in result.stdout
    assert "REFUSE phase=lint-comparison: WARN row set changed" in result.stderr
    _assert_retained(root, lane)


def test_failing_named_test_names_phase_and_retains_lane(landing_repo):
    root, lane = landing_repo
    _write(lane / "test_failure.py", "def test_failure(): assert False\n")
    _git(lane, "add", "test_failure.py")
    _git(lane, "commit", "-m", "add a real failing test")

    result = _run(root, "test_failure.py")

    assert result.returncode == 1
    assert "REFUSE phase=named-tests: named test selection failed" in result.stderr
    _assert_retained(root, lane)


def test_failing_generated_guard_names_phase_and_retains_lane(landing_repo):
    root, lane = landing_repo
    _write(lane / "test_guard.py", "def test_guard(): assert False\n")
    _git(lane, "add", "test_guard.py")
    _git(lane, "commit", "-m", "break generated guard")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "REFUSE phase=repo-wide-guards: generated guard set failed" in result.stderr
    _assert_retained(root, lane)


def test_stale_lane_refuses_before_baseline_or_merge(landing_repo):
    root, lane = landing_repo
    _write(root / "base-moved.txt", "new base\n")
    _git(root, "add", "base-moved.txt")
    _git(root, "commit", "-m", "move base")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "REFUSE phase=preflight: branch is not rebased onto current master" in result.stderr
    assert _git(root, "rev-parse", "HEAD") == before
    _assert_retained(root, lane)


def test_success_runs_real_reap_and_retains_branch_only(landing_repo):
    root, lane = landing_repo

    result = _run(root, "test_named.py")

    assert result.returncode == 0, result.stderr
    assert (
        f"reap examined path={lane.resolve()} tracked-dirty=0 untracked=0 ignored=0 "
        "unmerged-commits=0"
    ) in result.stdout
    assert f"removed linked worktree {lane.resolve()}" in result.stdout
    assert "worktree retired by dev/reap.py" in result.stdout
    assert not lane.exists()
    assert _git(root, "show-ref", "--verify", "refs/heads/lane")


def test_just_recipe_requires_branch_but_leaves_empty_tests_for_named_refusal():
    result = subprocess.run(
        ["just", "--dry-run", "land-lane", "lane", "test_land_lane.py"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "python3 dev/land_lane.py lane test_land_lane.py" in result.stderr
