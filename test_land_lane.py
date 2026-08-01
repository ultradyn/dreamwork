from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest


REPO = Path(__file__).resolve().parent
TOOL = REPO / "dev" / "land_lane.py"


def _load_tool():
    """Import the worktree's own copy, for the checks that need its roster."""
    spec = importlib.util.spec_from_file_location("land_lane_under_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


land_lane = _load_tool()


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
    _write(lane / "lint-rows.txt", "old warning\nnew warning\n")
    _git(lane, "add", "lint-rows.txt")
    _git(lane, "commit", "-m", "add warning")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "lint WARN row-set comparison: added=1 removed=0" in result.stdout
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
    assert "lint WARN row-set comparison: added=1 removed=1" in result.stdout
    assert "+   WARN  new warning" in result.stdout
    assert "-   WARN  old warning" in result.stdout
    assert "REFUSE phase=lint-comparison: WARN row set changed" in result.stderr
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
    _write(lane / "test_guard.py", "def test_guard(): assert False\n")
    _git(lane, "add", "test_guard.py")
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


def test_success_runs_real_reap_and_retains_branch_only(landing_repo):
    root, lane = landing_repo
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py")

    assert result.returncode == 0, result.stderr
    assert (
        "gate-coverage: 4 of 4 declared gates passed: "
        "named-tests guard-selection repo-wide-guards lint-comparison"
    ) in result.stdout
    merged = _git(root, "rev-parse", "--verify", "refs/heads/master")
    assert merged != before
    assert f"advance: master {before} -> {merged} after 4 gate(s)" in result.stdout
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
    seen = (root / "probe.txt").read_text().split()
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
        ((), "only 4 of 0 declared gates ran"),
        (land_lane.GATES + ("phantom-gate",), "only 4 of 5 declared gates ran"),
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

    assert land_lane.land("lane", ["test_named.py"]) == 1

    err = capsys.readouterr().err
    assert f"REFUSE phase=gate-coverage: {reason}" in err
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


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
