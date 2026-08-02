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
