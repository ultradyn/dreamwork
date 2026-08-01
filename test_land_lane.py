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
        [sys.executable, str(REDPROOF), *args, "--cwd", str(lane)],
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
    _write(lane / "lint-rows.txt", "old warning\nnew warning\n")
    _git(lane, "add", "lint-rows.txt")
    _git(lane, "commit", "-m", "add warning")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "lint WARN row-set comparison: added=1 removed=0" in result.stdout
    assert "+   WARN  new warning" in result.stdout
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
    assert "lint WARN row-set comparison: added=0 removed=0" in result.stdout
    assert "baseline=1 rows; post-merge=1 rows" in result.stdout


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
    assert "lint WARN row-set comparison: added=1 removed=1" in result.stdout
    assert "+   WARN  lessons.md  merging  is his call" in result.stdout
    assert "-   WARN  lessons.md  merging is his call" in result.stdout
    assert "REFUSE phase=lint-comparison: WARN row set changed" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


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
    assert "REFUSE phase=lint-comparison: post-merge WARN population is empty" in result.stderr
    assert "baseline=1 rows; post-merge=0 rows examined" in result.stderr
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
    assert "injections registered>=1 required" in result.stderr
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
        "gate-coverage: 5 of 5 declared gates passed: "
        "red-proof-history named-tests guard-selection repo-wide-guards "
        "lint-comparison"
    ) in result.stdout
    merged = _git(root, "rev-parse", "--verify", "refs/heads/master")
    assert merged != before
    assert f"advance: master {before} -> {merged} after 5 gate(s)" in result.stdout
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
        # Both counts are len(passed)=5 over len(roster): red-proof-history now
        # appends too (#951), so the empty-roster case reads "5 of 0" and the
        # phantom case (GATES is 5 real + 1 phantom = 6) reads "5 of 6".
        ((), "only 5 of 0 declared gates ran"),
        (land_lane.GATES + ("phantom-gate",), "only 5 of 6 declared gates ran"),
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


def test_documentation_only_branch_requires_no_injection_and_lands(doc_only_repo):
    """#932 forbids manufacturing a false-green; the gate used to demand one.

    `--require 1` was unconditional, so the only route through for a lane that
    obeyed its brief was to fake an injection into a file it had no reason to
    touch — the exact act #932 exists to forbid.
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
    assert "injections registered>=0 required" in result.stdout
    assert _git(root, "rev-parse", "--verify", "refs/heads/master") != before


@pytest.mark.parametrize("beside", ["feature.txt", "briefs/frame.md"])
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
        f"{doc} is executable input, so exempting it would let a behavioural "
        "change land with no red-proof owed at all"
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
    assert "derived-tests: 1 required test(s) from 2 changed path(s): test_lint.py" in result.stdout
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
