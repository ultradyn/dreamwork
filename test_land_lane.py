from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

import lint  # real lint.py: captures the actual transient WARN row from a worktree
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


def test_preflight_refuses_before_trusting_a_worktree_outside_the_invocation(
    landing_repo, tmp_path, monkeypatch, capsys
):
    root, _lane = landing_repo
    reported = tmp_path / "wrong-worktree"
    reported.mkdir()
    _git(root, "config", "core.worktree", str(reported))
    real_git = land_lane._git
    calls: list[tuple[Path, tuple[str, ...]]] = []

    def recording_git(cwd, *args):
        calls.append((Path(cwd).resolve(), args))
        return real_git(cwd, *args)

    monkeypatch.setattr(land_lane, "_git", recording_git)
    monkeypatch.chdir(root)

    assert land_lane.land("lane", ["test_named.py"]) == 1
    err = capsys.readouterr().err
    assert "REFUSE phase=preflight: Git resolved the invocation outside its worktree" in err
    assert f"invoked={root.resolve()}; resolved={reported.resolve()}" in err
    assert "git config --local --unset core.worktree" in err
    assert calls == [(root.resolve(), ("rev-parse", "--show-toplevel"))], (
        "preflight trusted the contaminated tree before proving that it contains "
        f"the invocation: {calls!r}"
    )


def test_preflight_accepts_a_normal_invocation_from_a_subdirectory(landing_repo):
    root, lane = landing_repo

    result = _run(root / "dev")

    assert result.returncode == 1
    assert "REFUSE phase=selection: named test selection is empty" in result.stderr
    assert "resolved the invocation outside its worktree" not in result.stderr
    _assert_retained(root, lane)


def test_preflight_property_also_catches_git_work_tree(
    landing_repo, tmp_path, monkeypatch
):
    root, lane = landing_repo
    reported = tmp_path / "environment-worktree"
    reported.mkdir()
    monkeypatch.setenv("GIT_WORK_TREE", str(reported))
    monkeypatch.setenv("GIT_DIR", str(root / ".git"))

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "REFUSE phase=preflight: Git resolved the invocation outside its worktree" in result.stderr
    assert f"invoked={root.resolve()}; resolved={reported.resolve()}" in result.stderr
    assert "possible causes: shared .git/config core.worktree or GIT_WORK_TREE" in result.stderr
    assert lane.is_dir()


def test_preflight_refuses_when_git_cannot_resolve_a_worktree(landing_repo):
    root, lane = landing_repo
    _git(root, "config", "core.bare", "true")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "REFUSE phase=preflight: Git could not resolve a worktree" in result.stderr
    assert f"invoked={root.resolve()}; resolved=UNRESOLVED" in result.stderr
    assert "base: UNTRUSTED (repository identity was not established)" in result.stderr
    assert lane.is_dir()


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
    ("lint_body", "failure_kind"),
    [
        ("raise SystemExit(2)\n", "lint-failed"),
        ("print('lint ran but omitted its trailer')\n", "report-invalid"),
        ("print('clean (1 warning(s))')\n", "report-invalid"),
    ],
)
def test_missing_warn_baseline_refuses_before_merge(
    landing_repo, lint_body, failure_kind
):
    root, lane = landing_repo
    _write(root / "lint.py", lint_body)
    _git(root, "add", "lint.py")
    _git(root, "commit", "-m", "broken baseline command")
    _git(lane, "rebase", "master")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert f"REFUSE phase=lint-baseline/{failure_kind}:" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


@pytest.mark.parametrize(
    ("lint_result", "git_result", "outcome", "phase", "evidence"),
    [
        (
            subprocess.CompletedProcess(["lint"], 2, "lint stdout\n", "lint exploded\n"),
            subprocess.CompletedProcess(["git"], 0, "", ""),
            land_lane.LintOutcome.LINT_FAILED,
            "lint-comparison/lint-failed",
            "lint stdout | lint exploded",
        ),
        (
            subprocess.CompletedProcess(["lint"], 0, "lint omitted trailer\n", ""),
            subprocess.CompletedProcess(["git"], 0, "", ""),
            land_lane.LintOutcome.REPORT_INVALID,
            "lint-comparison/report-invalid",
            "lint omitted trailer",
        ),
        (
            subprocess.CompletedProcess(["lint"], 2, "", "lint saw git fail\n"),
            subprocess.CompletedProcess(["git"], 128, "", "object database unreadable\n"),
            land_lane.LintOutcome.REPOSITORY_UNREADABLE,
            "lint-comparison/repository-unreadable",
            "object database unreadable",
        ),
    ],
)
def test_lint_unavailable_states_have_caller_visible_identities(
    monkeypatch, tmp_path, lint_result, git_result, outcome, phase, evidence
):
    """#1133: three refusals, not one prose-only unavailable sentinel."""
    monkeypatch.setattr(land_lane, "_run", lambda *args, **kwargs: lint_result)
    monkeypatch.setattr(land_lane, "_git", lambda *args, **kwargs: git_result)

    reading = land_lane._lint(tmp_path)
    refusal_phase, reason = land_lane._lint_refusal(
        reading, "lint-comparison", "post-gates"
    )

    assert reading.outcome is outcome
    assert refusal_phase == phase
    assert evidence in reason


def test_clean_lint_reading_does_not_run_repository_failure_probe(
    monkeypatch, tmp_path
):
    lint_result = subprocess.CompletedProcess(
        ["lint"], 0, "  WARN  expected row\nclean (1 warning(s))\n", ""
    )
    monkeypatch.setattr(land_lane, "_run", lambda *args, **kwargs: lint_result)
    monkeypatch.setattr(
        land_lane,
        "_git",
        lambda *args, **kwargs: pytest.fail("clean lint must not need a Git probe"),
    )

    reading = land_lane._lint(tmp_path)

    assert reading.outcome is land_lane.LintOutcome.CLEAN
    assert reading.rows == ("  WARN  expected row",)
    assert reading.repository_probe is None


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
# #1159: a lane-containment WARN about ANOTHER worktree's transient rebase is
# not a function of the merged tree, so it must not false-RED an unrelated
# branch when it appears in one of the gate's two lint readings and not the
# other. The row is still PRINTED (it surfaces a genuinely detached worktree);
# only the comparison excludes it. The transient row text is captured from a
# REAL mid-rebase worktree (#906) — never a hand-built string — so a rewording
# of lint.py's emission fails loud rather than silently passing.
# ---------------------------------------------------------------------------


def _capture_real_transient_lane_row(tmp_path: Path) -> str:
    """Build a fixture repo with a lane worktree MID-REBASE (a genuine conflict)
    and return the EXACT WARN row the real lint emits — captured from
    production, not hand-built.

    Reuses the #1116 technique (test_lint.py::_repo_with_conflicting_rebase):
    a real detached worktree with ``rebase-merge/`` state is the only input
    that proves the transient row is actually produced. Cleans up the rebase
    so no fixture leaves git in a bad state.
    """
    t = tmp_path / "transient-fixture"
    t.mkdir()

    def git(*a, cwd=None):
        r = subprocess.run(
            ["git", "-C", str(cwd or t), *a],
            capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        return r

    git("init", "-q", "-b", "master")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (t / "watch.py").write_text("# base\n", encoding="utf-8")
    briefs = t / ".dreamwork" / "docs" / "briefs"
    briefs.mkdir(parents=True, exist_ok=True)
    (briefs / "900-lane.md").write_text(
        "# Brief\n\nWorktree: `.worktrees/lane` on `wt/lane`.\n\n"
        "Lane-owns: watch.py\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "base")
    git("worktree", "add", "-q", "-b", "wt/lane", str(t / ".worktrees" / "lane"))
    lane_wt = t / ".worktrees" / "lane"
    # Diverge so the rebase conflicts → a genuine mid-rebase detached state.
    (t / "watch.py").write_text("# master\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "master edit")
    (lane_wt / "watch.py").write_text("# lane\n", encoding="utf-8")
    git("add", "-A", cwd=lane_wt)
    git("commit", "-qm", "lane edit", cwd=lane_wt)
    subprocess.run(
        ["git", "-C", str(lane_wt), "rebase", "master"],
        capture_output=True, text=True, check=False)  # conflict → detached
    try:
        rep = lint.Report()
        lint.check_lane_containment_backstop(t / ".dreamwork", rep)
        rendered = rep.render()
        row = next(line for line in rendered.splitlines()
                   if "lane-containment" in line
                   and "detached HEAD is transient" in line)
        return row
    finally:
        subprocess.run(
            ["git", "-C", str(lane_wt), "rebase", "--abort"],
            capture_output=True, text=True, check=False)


def test_real_mid_rebase_transient_row_is_produced_and_classified_excluded(
        tmp_path):
    """Both halves of #1159 at the partition unit: the transient row IS
    produced by a real detached worktree, and the comparison's partition
    classifies THAT real row as excluded — proven against production output,
    not a hand-built string (#906).
    """
    row = _capture_real_transient_lane_row(tmp_path)
    # Half 1 — the row is genuinely produced (real lint, real mid-rebase worktree).
    assert "lane-containment" in row
    assert "detached HEAD is transient" in row
    assert "mid-rebase" in row  # the operation, from a genuine conflict
    # Half 2 — the comparison's partition excludes the REAL row.
    assert land_lane._is_fleet_transient_lane_warn(row) is True
    compared, excluded = land_lane._partition_warn_rows([row])
    assert excluded == (row,) and compared == ()
    # The partition must NOT over-exclude. A plain WARN stays compared, and a
    # lane-containment ERROR (the #465 dirty-main-checkout hazard) stays
    # compared too — it is not WARN-level, so it is never a comparison input.
    plain = "  WARN  lessons.md  a standing fact belongs in an OK row"
    assert land_lane._is_fleet_transient_lane_warn(plain) is False
    dirty = ("  ERROR  lane-containment  other.py dirty in the MAIN CHECKOUT "
             "but owned by lane wt/lane (#465)")
    assert land_lane._is_fleet_transient_lane_warn(dirty) is False
    assert land_lane._partition_warn_rows([plain, dirty]) == (
        (plain, dirty), ())


def test_foreign_lane_transient_row_does_not_false_red_the_gate(
        landing_repo, tmp_path):
    """#1159 end-to-end: a lane-containment WARN about ANOTHER worktree's
    transient rebase lands in the post-merge reading but not the baseline —
    exactly the natural experiment that false-REDd glm-1140ingest2. The gate
    must PASS: the row is excluded from the comparison (not a function of the
    tree) while still printed for awareness. The row text is the REAL emission
    captured from a mid-rebase worktree (#906).
    """
    root, lane = landing_repo
    real_row = _capture_real_transient_lane_row(tmp_path)
    # The fixture lint prints '  WARN  ' + each lint-rows.txt line, so the line
    # carries the label + double-space + detail the real renderer produces.
    line = real_row[len("  WARN  "):]
    _write(lane / "lint-rows.txt", "old warning\n" + line + "\n")
    _git(lane, "add", "lint-rows.txt")
    _git(lane, "commit", "-m", "a foreign lane went mid-rebase between readings")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py")

    # The gate PASSES: the foreign transient row is excluded, not a tree change.
    assert result.returncode == 0, (
        "gate REFUSED on a foreign lane's transient row — the comparison "
        "counted a row that is not a function of the tree (a worktree other "
        "than the gated subject, mid-rebase):\n" + result.stdout + result.stderr)
    # Both halves visible in one run: the row WAS seen (printed) AND excluded
    # from the comparison with a stated reason and both denominators (#868).
    assert real_row in result.stdout, "the transient row must still be PRINTED"
    assert "excluded" in result.stdout
    assert "fleet-transient lane-containment" in result.stdout
    assert "#1159" in result.stdout
    # No false RED: among compared rows nothing was added or removed.
    assert "WARN row-set comparison: added=0 removed=0" in result.stdout
    # The gate PASSED, so master advanced (a refusal would have left it unmoved).
    assert _git(root, "rev-parse", "--verify", "refs/heads/master") != before, (
        "gate reported success but master did not advance")


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
    Validation is bound to WARN_ROW, the same filter _warn_rows applies to the
    observed lint output, so a declaration is unreadable exactly when it could
    not name a real row.

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


# ---------------------------------------------------------------------------
# #1111 — Also-Fixes propagation through --squash. A constituent that carries
# ``Also-Fixes: #NNN`` claims an incidental fix for another task. The squash
# collapses constituents into one commit, so the trailer must be propagated
# into the squashed message or the claim is lost.
# ---------------------------------------------------------------------------

def test_squash_propagates_constituent_also_fixes_into_squashed_message(tmp_path):
    """A constituent's Also-Fixes trailer survives the squash."""
    root, lane = _make_repo(tmp_path)
    # A constituent with an Also-Fixes trailer for a different task
    _write(lane / "also.txt", "claim\n")
    _git(lane, "add", "also.txt")
    _git(lane, "commit", "-m", "fix(#11): the named task", "-m",
         "Also-Fixes: #12")
    base_sha = _git(root, "rev-parse", "master")
    branch_sha = _git(lane, "rev-parse", "HEAD")

    result = land_lane._squash_lane(lane, "lane", base_sha, branch_sha)
    assert result.error is None, result.error

    msg = _git(lane, "log", "-1", "--format=%B")
    assert "Also-Fixes: #12" in msg, (
        f"the constituent's Also-Fixes #12 must be propagated into the "
        f"squashed message: {msg!r}")


def test_squash_deduplicates_also_fixes_already_in_the_tip_message(tmp_path):
    """The tip's own Also-Fixes ids are already in the preserved message; only
    ids from OTHER constituents (and not already present) are appended."""
    root, lane = _make_repo(tmp_path)
    # Tip carries Also-Fixes #12 already
    _write(lane / "tip.txt", "tip\n")
    _git(lane, "add", "tip.txt")
    _git(lane, "commit", "-m", "fix(#11): tip", "-m", "Also-Fixes: #12")
    # Earlier constituent also claims #12 (plus #13)
    _write(lane / "earlier.txt", "earlier\n")
    _git(lane, "add", "earlier.txt")
    _git(lane, "commit", "-m", "feat(#11): earlier", "-m",
         "Also-Fixes: #12, #13")
    base_sha = _git(root, "rev-parse", "master")
    branch_sha = _git(lane, "rev-parse", "HEAD")

    result = land_lane._squash_lane(lane, "lane", base_sha, branch_sha)
    assert result.error is None, result.error

    msg = _git(lane, "log", "-1", "--format=%B")
    assert "Also-Fixes: #12" in msg, (
        f"#12 was already in the tip and must survive: {msg!r}")
    assert "#13" in msg, (
        f"#13 is new from the earlier constituent and must be propagated: "
        f"{msg!r}")
    # #12 must appear exactly once in the appended trailer
    also_lines = [l for l in msg.splitlines() if l.startswith("Also-Fixes:")]
    all_ids = []
    for line in also_lines:
        all_ids.extend(land_lane._TRAILER_ID.findall(line))
    assert all_ids.count("12") == 1, (
        f"#12 must appear exactly once across all Also-Fixes lines: {msg!r}")


def test_squash_without_also_fixes_adds_no_trailer(tmp_path):
    """A squash with no constituent Also-Fixes must not append an empty trailer."""
    root, lane = _make_repo(tmp_path)
    _write(lane / "feat.txt", "feat\n")
    _git(lane, "add", "feat.txt")
    _git(lane, "commit", "-m", "fix(#11): no also-fixes here")
    base_sha = _git(root, "rev-parse", "master")
    branch_sha = _git(lane, "rev-parse", "HEAD")

    result = land_lane._squash_lane(lane, "lane", base_sha, branch_sha)
    assert result.error is None, result.error

    msg = _git(lane, "log", "-1", "--format=%B")
    assert "Also-Fixes:" not in msg, (
        f"no constituent carried an Also-Fixes trailer; the squashed message "
        f"must not add one: {msg!r}")


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


def test_success_advances_master_exactly_once(landing_repo, monkeypatch, capsys):
    root, lane = landing_repo
    before = _git(root, "rev-parse", "master")
    real_git = land_lane._git
    advances: list[tuple[str, ...]] = []

    def recording_git(cwd, *args):
        if Path(cwd).resolve() == root.resolve() and args[:2] == ("merge", "--ff-only"):
            advances.append(args)
        return real_git(cwd, *args)

    monkeypatch.setattr(land_lane, "_git", recording_git)
    monkeypatch.chdir(root)
    assert land_lane.land("lane", ["test_named.py"]) == 0, capsys.readouterr().err
    assert len(advances) == 1, f"master advance calls={advances!r}"
    assert _git(root, "rev-parse", "master") != before
    assert not lane.exists()


def test_compare_before_advance_exercises_moved_master_and_refuses(landing_repo):
    root, lane = landing_repo
    marker = root.parent / "moved-master.txt"
    _write(
        lane / "test_move_master.py",
        "from pathlib import Path\n"
        "import subprocess\n"
        "def git(*args):\n"
        "    return subprocess.run(['git', *args], check=True, capture_output=True, text=True).stdout.strip()\n"
        "def test_move_master():\n"
        "    base = git('rev-parse', 'refs/heads/master')\n"
        "    tree = git('rev-parse', base + '^{tree}')\n"
        "    moved = subprocess.run(['git', 'commit-tree', tree, '-p', base, '-m', 'concurrent master move'], check=True, capture_output=True, text=True).stdout.strip()\n"
        "    git('update-ref', 'refs/heads/master', moved, base)\n"
        f"    Path({str(marker)!r}).write_text(moved)\n",
    )
    _git(lane, "add", "test_move_master.py")
    _git(lane, "commit", "-m", "exercise moved-master CAS")

    result = _run(root, "test_move_master.py")

    assert result.returncode == 1
    assert "REFUSE phase=advance: compare-before-advance refused" in result.stderr
    assert "master moved from captured" in result.stderr
    moved = marker.read_text(encoding="utf-8")
    assert _git(root, "rev-parse", "master") == moved
    assert _git(root, "branch", "--show-current") == "master"
    assert not (root / ".dreamwork" / "gate-in-flight.json").exists()
    assert not any("/.gate-" in row for row in _git(root, "worktree", "list", "--porcelain").splitlines())
    _assert_retained(root, lane)


def test_reap_refusal_is_binding_when_lane_becomes_dirty_during_gates(landing_repo):
    root, lane = landing_repo
    _write(
        lane / "test_dirty_lane.py",
        "from pathlib import Path\n"
        "def test_dirty_lane():\n"
        f"    Path({str(lane / 'feature.txt')!r}).write_text('dirty after preflight\\n')\n",
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
    probe = root.parent / "gate-probe.json"
    _write(
        lane / "test_probe.py",
        "from pathlib import Path\n"
        "import json, os, subprocess\n"
        "def test_probe():\n"
        "    out = subprocess.run(['git', 'rev-list', '--parents', '-n', '1', 'HEAD'],\n"
        "        capture_output=True, text=True, check=True).stdout\n"
        f"    Path({str(probe)!r}).write_text(json.dumps({{'cwd': os.getcwd(), 'parents': out.split()}}))\n",
    )
    _git(lane, "add", "test_probe.py")
    _git(lane, "commit", "-m", "record the tree the gate judged")
    base_before = _git(root, "rev-parse", "--verify", "refs/heads/master")
    lane_head = _git(root, "rev-parse", "--verify", "refs/heads/lane")

    result = _run(root, "test_probe.py")

    assert result.returncode == 0, (
        "provisional gate command ran in main checkout\n" + result.stderr
    )
    assert probe.exists(), "the gate command did not run at all"
    record = json.loads(probe.read_text(encoding="utf-8"))
    gate_cwd = Path(record["cwd"]).resolve()
    assert gate_cwd not in {root.resolve(), lane.resolve()}, (
        "provisional gate command ran in main checkout or lane worktree"
    )
    assert f"registered detached scratch={gate_cwd}" in result.stdout
    assert f"at exact base={base_before}" in result.stdout
    seen = record["parents"]
    assert seen[1:] == [base_before, lane_head], f"gate judged {seen!r}"
    assert (
        f"merge-identity: {seen[0]} has parents master@{base_before} and lane@{lane_head}"
    ) in result.stdout
    assert _git(root, "rev-parse", "--verify", "refs/heads/master") == seen[0]


def test_a_restore_that_cannot_land_is_loud_and_master_is_still_correct(landing_repo):
    """A dirty failing scratch is removed without touching attached main."""
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
    assert "RECOVERY FAILED:" not in result.stderr
    assert _git(root, "branch", "--show-current") == "master"
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


def test_doc_only_branch_lands_with_empty_named_selection(doc_only_repo):
    """#1018: a documentation-only branch has no test to name.

    The honest path is a THIRD STATE (#136): covered by lint and by nothing
    else is different from covered by named tests and different from coverage
    unknown.  An empty named-test selection is legitimate when — and only
    when — the entire diff is inert documentation, so the #1010 guarantee (an
    empty selection is indistinguishable from a broken deriver) survives for
    any branch that has a single binding path.
    """
    root, lane = doc_only_repo
    _empty_registry(lane, ".dreamwork/docs/census.md")
    before = _git(root, "rev-parse", "--verify", "refs/heads/master")
    # Precondition the test's meaning depends on: the diff is one doc path.
    assert _git(lane, "diff", "--name-only", "master", "lane").split() == [
        ".dreamwork/docs/census.md"
    ]

    result = _run(root)  # no named tests — the honest path for a doc-only branch

    assert result.returncode == 0, result.stdout + result.stderr
    assert "selection: 0 named tests; the diff is entirely covered" in result.stdout
    assert (
        "named tests are not required because no changed path is binding"
        in result.stdout
    )
    assert "named-tests: 0 selected" in result.stdout
    assert "named-tests waived" in result.stdout
    assert "lint-precheck and lint-comparison are the covering phases" in result.stdout
    assert "gate-coverage: 6 of 6 declared gates passed" in result.stdout
    assert _git(root, "rev-parse", "--verify", "refs/heads/master") != before


def test_empty_selection_names_binding_paths_when_refusing(landing_repo):
    """#651/#1018: the refusal for a binding branch must NAME what it detected.

    The examined line carries the binding paths so an operator can see WHY an
    empty selection was refused — not just THAT it was.  This binds the
    BEHAVIOUR (a branch with binding paths still refuses) and names the
    detectable mode (the binding paths are listed), not just the prose.
    """
    root, lane = landing_repo
    before = _git(root, "rev-parse", "HEAD")
    result = _run(root)  # no named tests on a binding diff

    assert result.returncode == 1
    assert "REFUSE phase=selection: named test selection is empty" in result.stderr
    assert "binding path(s)" in result.stderr
    assert "feature.txt" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


def test_comment_only_py_still_refuses_empty_selection(tmp_path):
    """#1018 Symptom B is NOT fixed: a comment-only .py is still binding.

    A sound automatic inert-classification for comment-only .py diffs is not
    achievable — a line that looks like a comment inside a triple-quoted string
    is code, and a docstring a test asserts on IS behaviour (test_brief.py is
    a module full of assertions about text).  The classifier stays conservative:
    anything outside .dreamwork/ that ends in .py is binding, regardless of
    whether the diff content looks inert.  This binds that behaviour so the
    trap (Direction 2 of the brief) survives the fix for Symptom A.
    """
    root, lane = _make_repo(tmp_path)
    # A .py file whose diff is comments only — still classified binding by path.
    _write(lane / "some_tool.py", "# a comment-only change\n")
    _git(lane, "add", "some_tool.py")
    _git(lane, "commit", "-m", "comment-only py")
    _empty_registry(lane, "some_tool.py")
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root)  # no named tests

    assert result.returncode == 1
    assert "REFUSE phase=selection: named test selection is empty" in result.stderr
    assert "binding path(s)" in result.stderr
    assert "some_tool.py" in result.stderr
    _assert_base_unmoved(root, before)
    _assert_retained(root, lane)


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


def test_an_empty_diff_owes_no_injection_but_stays_distinct_from_all_inert():
    """A successful empty diff owes nothing without claiming doc coverage."""
    empty = land_lane.Diff(changed=(), inert=(), binding=(), tests=())
    assert empty.required_injections == 0
    assert "the diff is EMPTY" in land_lane._requirement_line(empty)
    assert "inert documentation" not in land_lane._requirement_line(empty)


def test_an_unreadable_diff_is_not_the_empty_diff(tmp_path, capsys):
    """A failed git read returns None; it never inherits empty's exemption."""
    _, lane = _make_repo(tmp_path)
    head = _git(lane, "rev-parse", "HEAD")

    empty = land_lane._classify_diff(lane, head, head)
    unreadable = land_lane._classify_diff(lane, "definitely-not-a-sha", head)

    assert empty is not None
    assert empty.changed == ()
    assert empty.required_injections == 0
    assert unreadable is None, (
        "unreadable diff was silently converted to an empty Diff"
    )
    assert "fatal:" in capsys.readouterr().err


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


def test_directory_map_derives_a_client_only_owns_list():
    """A client-only lane must select tests through the directory map (#1010).

    The client extraction made ``client/`` a first-class source directory whose
    files have no name-derivable or import-derivable Python test, so the
    directory map is the ONLY rule that reaches them. Without the ``client/``
    entry in ``DIR_TESTSET_MAP`` a client-only lane derives zero tests and is
    refused at dispatch as "an empty selection is indistinguishable from broken
    derivation" (#136) — silently blocking a whole class of work. ``168aa4c6``
    added the row; this guard pins the DERIVATION (what a client owns-list
    actually selects), not the data structure's contents, so it fails if the
    row is removed AND if the map rule itself is broken, but survives a
    legitimate rename of a mapped test module.

    A ``.js`` and a non-``.js`` client file both sit under ``client/``, so both
    must select through the directory map — a ``.js``-only probe would not
    notice a rule that accidentally keyed on extension.

    Production line this binds: the ``client/`` row in ``DIR_TESTSET_MAP`` plus
    ``_map_derived``'s membership walk (``_path_in_mapped_directory``) over it.
    """
    js_targets, js_dirs = land_lane._map_derived(["client/router.js"])
    css_targets, css_dirs = land_lane._map_derived(["client/style.css"])
    assert js_targets, "client/router.js derived no tests via the map rule"
    assert css_targets, "client/style.css derived no tests via the map rule"
    # Relevance, not identity: the path matched the client/ entry specifically
    # (not a catch-all), so a legitimate rename of a mapped test module does
    # not break this. Pinning the exact three module names would make this a
    # spelling checker that passes on a broken derivation keyed on the row.
    assert js_dirs == ("client/",) and css_dirs == ("client/",)
    # The map is path-gated: a path outside every mapped directory selects
    # nothing, which is the refusal that protects dispatch (#136). If this
    # stops being empty the map has stopped discriminating, and the guard has
    # traded one silent hole for another.
    outside_targets, outside_dirs = land_lane._map_derived(["unmapped/file.xyz"])
    assert outside_targets == () and outside_dirs == ()


def test_data_derived_finds_a_test_referencing_a_changed_data_file(tmp_path):
    """#1099's shape: a test that reads a tracked file as data is derived.

    A changed ``briefs/frame.md`` is read by a test that constructs the path
    as a 2+-component BinOp expression. No import edge connects a ``.md`` file
    to anything, so only the data rule reaches it.
    Production line this binds: the membership check in _data_derived.
    """
    (tmp_path / "briefs").mkdir()
    (tmp_path / "briefs" / "frame.md").write_text("# Frame\n")
    (tmp_path / "test_brief.py").write_text(
        "from pathlib import Path\n"
        "ROOT = Path('.').resolve()\n"
        "def test_frame():\n"
        "    text = (ROOT / 'briefs' / 'frame.md').read_text()\n"
        "    assert 'Frame' in text\n"
    )
    tests, matched = land_lane._data_derived(
        tmp_path, ["briefs/frame.md"]
    )
    assert "test_brief.py" in tests, (
        f"data rule missed test_brief.py for briefs/frame.md; got {tests!r}"
    )
    assert "briefs/frame.md" in matched


def test_data_derived_two_hop_finds_test_through_production_consumer(tmp_path):
    """The full #1099 path: data file -> production consumer -> test by name.

    ``briefs/frame.md`` is referenced by ``dev/brief.py`` via
    ``FRAME_PATH = ROOT / 'briefs' / 'frame.md'``. The data rule's two-hop
    applies the NAME CONVENTION ONLY to ``dev/brief.py`` (not the import
    rule — that was collateral #1101 r2), deriving ``test_brief.py``
    even though the test itself never references ``frame.md`` directly.
    """
    (tmp_path / "briefs").mkdir()
    (tmp_path / "briefs" / "frame.md").write_text("# Frame\n")
    (tmp_path / "dev").mkdir()
    (tmp_path / "dev" / "brief.py").write_text(
        "from pathlib import Path\n"
        "ROOT = Path(__file__).resolve().parent.parent\n"
        "FRAME_PATH = ROOT / 'briefs' / 'frame.md'\n"
    )
    (tmp_path / "test_brief.py").write_text(
        "import dev.brief\n"
        "def test_brief(): assert True\n"
    )
    tests, matched = land_lane._data_derived(
        tmp_path, ["briefs/frame.md"]
    )
    assert "test_brief.py" in tests, (
        f"two-hop data rule missed test_brief.py; got {tests!r}"
    )


def test_data_derived_finds_a_py_fixture_copy_not_an_import(tmp_path):
    """#1100's shape: a test that COPIES a .py file is derived.

    ``test_launch_lane.py`` copies ``dev/brief.py`` via ``read_text()`` — not
    an import. The data rule treats ``dev/brief.py`` as data: its path is a
    2+-component BinOp expression, and the referencing test is derived.
    """
    (tmp_path / "dev").mkdir()
    (tmp_path / "dev" / "brief.py").write_text("VALUE = 1\n")
    (tmp_path / "test_launch_lane.py").write_text(
        "from pathlib import Path\n"
        "REPO = Path('.').resolve()\n"
        "def test_copy():\n"
        "    src = (REPO / 'dev' / 'brief.py').read_text()\n"
        "    assert 'VALUE' in src\n"
    )
    tests, matched = land_lane._data_derived(
        tmp_path, ["dev/brief.py"]
    )
    assert "test_launch_lane.py" in tests, (
        f"data rule missed test_launch_lane.py for dev/brief.py; got {tests!r}"
    )


def test_data_derived_excludes_bare_basenames():
    """A bare ``"watch.py"`` is NOT a data match: it would select half the repo.

    The 2+-component requirement is the precision boundary. Dropping it to 1
    makes ``watch.py`` match in 32 test files' string constants (#1101 measured).
    """
    # _data_path_suffixes must not yield "watch.py" from a bare Constant
    suffixes = land_lane._data_path_suffixes(
        'x = "watch.py"'
    )
    assert suffixes == frozenset(), (
        f"bare basename should not yield a data suffix; got {suffixes!r}"
    )
    # But a 2-component BinOp should
    suffixes2 = land_lane._data_path_suffixes(
        'ROOT = "repo"\nx = ROOT / "dev" / "watch.py"\n'
    )
    assert "dev/watch.py" in suffixes2


def test_data_derived_finds_nothing_for_a_single_component_changed_path(tmp_path):
    """A changed ``watch.py`` (1 component) cannot match a 2+-component suffix."""
    (tmp_path / "watch.py").write_text("VALUE = 1\n")
    (tmp_path / "test_watch.py").write_text(
        'x = "watch.py"\n'  # bare constant — not detected
    )
    tests, matched = land_lane._data_derived(tmp_path, ["watch.py"])
    assert tests == (), f"1-component path should derive nothing; got {tests!r}"
    assert matched == ()


def test_ospathjoin_suffix_detected():
    """os.path.join with 2+ trailing constant string args is a data suffix.

    Production line this binds: ``_call_path_suffix`` in ``_data_path_suffixes``.
    The commonest path idiom (#1101 r2 measured 64 occurrences) was an accepted
    limitation in round 1; this test proves it is no longer.
    """
    # os.path.join with a variable prefix and 2 constant trailing args
    suffixes = land_lane._data_path_suffixes(
        'import os\n'
        'p = os.path.join(root, "dev", "journal_consume.py")\n'
    )
    assert "dev/journal_consume.py" in suffixes, (
        f"os.path.join suffix missed; got {suffixes!r}"
    )


def test_ospathjoin_single_constant_arg_excluded():
    """os.path.join with only 1 trailing constant arg is a basename, excluded."""
    suffixes = land_lane._data_path_suffixes(
        'import os\n'
        'p = os.path.join(root, "watch.py")\n'
    )
    assert "watch.py" not in suffixes, (
        f"1-component os.path.join suffix should be excluded; got {suffixes!r}"
    )


def test_ospathjoin_derivation_reaches_dynamic_load_consumer(tmp_path):
    """os.path.join detection closes the journal_consume → test_watch gap.

    #1101 r2 Direction 1: a test that dynamically loads a module via
    ``os.path.join(os.path.dirname(__file__), "dev", "journal_consume.py")``
    is a genuine consumer — changing the loaded file breaks the test — but
    round 1's BinOp-only detection missed it. This test proves the widened
    detection reaches it.

    Production line this binds: ``_call_path_suffix`` → ``_data_consumers``
    → ``_data_derived``.
    """
    (tmp_path / "dev").mkdir()
    (tmp_path / "dev" / "journal_consume.py").write_text("VALUE = 1\n")
    (tmp_path / "test_watch.py").write_text(
        "import os, importlib.util, importlib.machinery\n"
        "def test_dynamic_load():\n"
        "    cli_path = os.path.join(os.path.dirname(__file__), 'dev',\n"
        "                            'journal_consume.py')\n"
        "    loader = importlib.machinery.SourceFileLoader('jc', cli_path)\n"
        "    assert loader is not None\n"
    )
    tests, matched = land_lane._data_derived(
        tmp_path, ["dev/journal_consume.py"]
    )
    assert "test_watch.py" in tests, (
        f"os.path.join data rule missed test_watch.py; got {tests!r}"
    )


def test_path_call_suffix_detected():
    """Path('a/b') with internal slash is a 2+-component data suffix.

    Production line this binds: ``_call_path_suffix`` Path branch.
    """
    suffixes = land_lane._data_path_suffixes(
        'from pathlib import Path\n'
        'p = Path("dev/brief.py")\n'
    )
    assert "dev/brief.py" in suffixes, (
        f"Path('a/b') suffix missed; got {suffixes!r}"
    )


def test_write_context_excluded_from_data_suffixes():
    """A path expression used as a .write_text() receiver is NOT a data suffix.

    Production line this binds: ``_is_write_target`` in ``_data_path_suffixes``.
    A test that creates a fixture at ``tmp_path / 'dev' / 'brief.py'`` is
    manufacturing a synthetic file, not reading the real one (#1101 r2).
    """
    # write_text receiver — excluded
    suffixes = land_lane._data_path_suffixes(
        'from pathlib import Path\n'
        '(Path(".") / "dev" / "brief.py").write_text("VALUE = 1")\n'
    )
    assert "dev/brief.py" not in suffixes, (
        f"write-context suffix should be excluded; got {suffixes!r}"
    )


def test_write_context_excluded_but_read_context_included():
    """The same suffix in BOTH write and read contexts is included (read wins).

    If a file creates a fixture AND reads the real file, it IS a consumer —
    the read occurrence is the real dependency.
    """
    suffixes = land_lane._data_path_suffixes(
        'from pathlib import Path\n'
        '(Path("/tmp") / "dev" / "brief.py").write_text("x")\n'
        'text = (Path(".") / "dev" / "brief.py").read_text()\n'
    )
    assert "dev/brief.py" in suffixes, (
        f"read occurrence should win over write; got {suffixes!r}"
    )


# ---------------------------------------------------------------------------
# #1101 r4 — three write-detection gaps closed.  Each test below pins one form
# that r2's ``_is_write_target`` missed.  A missed write form means a path is
# treated as a read, so a genuine consumer is silently EXCLUDED and the gate
# goes green without running it.  Every mode is tested individually, not one
# representative — a single ``mode="w"`` case would leave the others in the
# same silent state.
# ---------------------------------------------------------------------------


def test_write_keyword_mode_open_excluded():
    """``open(path, mode="w")`` — the keyword-mode form — is a write target.

    Production line this binds: ``_open_mode_is_write`` (keywords branch)
    in ``_is_write_target``.  r2 only checked the POSITIONAL second arg
    (``parent.args[1]``); the keyword form was invisible (#1101 r4 P1.1).
    """
    suffixes = land_lane._data_path_suffixes(
        'open(Path("/tmp") / "dev" / "brief.py", mode="w")\n'
    )
    assert "dev/brief.py" not in suffixes, (
        f"keyword-mode open write should be excluded; got {suffixes!r}"
    )


@pytest.mark.parametrize("mode", ["w+", "wb", "a", "x"])
def test_write_positional_mode_variants_excluded(mode):
    """Every positional write-mode variant is excluded, not just ``"w"``.

    Production line this binds: ``_open_mode_is_write`` (positional branch)
    — the ``any(c in mode for c in "wax")`` check.  Each variant is a
    separate parametrize case because a single representative would leave
    the others untested (#1101 r4 P1.1).
    """
    suffixes = land_lane._data_path_suffixes(
        f'open(Path("/tmp") / "dev" / "brief.py", "{mode}")\n'
    )
    assert "dev/brief.py" not in suffixes, (
        f"positional mode {mode!r} should be excluded; got {suffixes!r}"
    )


def test_read_mode_open_not_excluded():
    """``open(path, "r")`` is a READ, not excluded — guard against over-narrowing.

    The mode check must accept ``"r"`` and ``"rb"`` as reads; only w/a/x
    are writes.  Without this guard, tightening the mode check could flip
    reads to writes.
    """
    assert "dev/brief.py" in land_lane._data_path_suffixes(
        'open(Path(".") / "dev" / "brief.py", "r")\n'
    ), "positional read mode 'r' should NOT be excluded"
    assert "dev/brief.py" in land_lane._data_path_suffixes(
        'open(Path(".") / "dev" / "brief.py", mode="r")\n'
    ), "keyword read mode 'r' should NOT be excluded"


def test_path_open_method_excluded():
    """``(path).open("w")`` — the Path.open method form — is a write target.

    Production line this binds: the ``parent.attr == "open"`` branch in
    ``_is_write_target``.  r2 did not detect the method form at all — only
    the builtin ``open(...)`` (#1101 r4 P1.2).  Mode is ``args[0]`` here,
    not ``args[1]`` (the path is the method's object).
    """
    suffixes = land_lane._data_path_suffixes(
        '(Path("/tmp") / "dev" / "brief.py").open("w")\n'
    )
    assert "dev/brief.py" not in suffixes, (
        f"Path.open('w') write should be excluded; got {suffixes!r}"
    )


def test_path_open_keyword_mode_excluded():
    """``(path).open(mode="w")`` — keyword mode on the method form."""
    suffixes = land_lane._data_path_suffixes(
        '(Path("/tmp") / "dev" / "brief.py").open(mode="w")\n'
    )
    assert "dev/brief.py" not in suffixes, (
        f"Path.open(mode='w') write should be excluded; got {suffixes!r}"
    )


def test_aliased_write_excluded():
    """A path bound to a name then written through the alias is excluded.

    Production line this binds: alias tracking in ``_data_path_suffixes``
    (the ``aliases`` dict + ``aliased_value_ids`` skip + Load-context Name
    scan).  r2 missed this entirely (#1101 r4 P1.3): ``p = <path>;
    open(p, "w")`` was treated as a read because the BinOp's parent was
    ``Assign`` (non-write).
    """
    suffixes = land_lane._data_path_suffixes(
        'from pathlib import Path\n'
        'p = Path("/tmp") / "dev" / "brief.py"\n'
        'open(p, "w")\n'
    )
    assert "dev/brief.py" not in suffixes, (
        f"aliased write should be excluded; got {suffixes!r}"
    )


def test_aliased_write_method_form_excluded():
    """Alias written through ``.write_text()`` is also excluded."""
    suffixes = land_lane._data_path_suffixes(
        'from pathlib import Path\n'
        'p = Path("/tmp") / "dev" / "brief.py"\n'
        'p.write_text("x")\n'
    )
    assert "dev/brief.py" not in suffixes, (
        f"aliased .write_text() should be excluded; got {suffixes!r}"
    )


def test_aliased_read_wins_over_write():
    """An alias used in BOTH write and read contexts is included (read wins).

    If a file writes to a fixture path AND reads the real path through the
    same alias, the read occurrence is the real dependency.
    """
    suffixes = land_lane._data_path_suffixes(
        'from pathlib import Path\n'
        'p = Path(".") / "dev" / "brief.py"\n'
        'open(p, "w")\n'
        'text = p.read_text()\n'
    )
    assert "dev/brief.py" in suffixes, (
        f"alias read should win over write; got {suffixes!r}"
    )


def test_read_wins_across_files(tmp_path):
    """A suffix written in file A and read in file B still selects B.

    The read-wins rule is per-FILE: ``_data_path_suffixes`` returns B's read
    suffixes independently of A's write-only suffixes, so ``_data_consumers``
    includes B.  This test exercises the cross-file path the task named
    specifically — a path written in one file and read in another.

    The ``_data_consumers`` assertion is the discriminating part: without
    alias tracking, file A's aliased write leaks the suffix as a read and
    A appears as a consumer (the cross-file write-exclusion breaks).
    """
    (tmp_path / "dev").mkdir()
    (tmp_path / "dev" / "brief.py").write_text("VALUE = 1\n")
    # File A writes the suffix (fixture creation) — not a consumer.
    (tmp_path / "fixture_maker.py").write_text(
        "from pathlib import Path\n"
        'p = Path("/tmp") / "dev" / "brief.py"\n'
        'open(p, "w")\n'
    )
    # File B reads the real file — genuine consumer.
    (tmp_path / "test_brief.py").write_text(
        "from pathlib import Path\n"
        'text = (Path(".") / "dev" / "brief.py").read_text()\n'
    )
    # _data_consumers: fixture_maker.py must NOT be a consumer.
    consumers = land_lane._data_consumers(tmp_path, ["dev/brief.py"])
    fixture_consumers = consumers.get("dev/brief.py", ())
    assert "test_brief.py" in fixture_consumers, (
        f"cross-file read should make test_brief.py a consumer; got {fixture_consumers!r}"
    )
    assert "fixture_maker.py" not in fixture_consumers, (
        f"write-only fixture_maker.py should not be a consumer; got {fixture_consumers!r}"
    )
    # _data_derived: the test is selected.
    tests, matched = land_lane._data_derived(
        tmp_path, ["dev/brief.py"]
    )
    assert "test_brief.py" in tests, (
        f"cross-file read should select test_brief.py; got {tests!r}"
    )


def test_data_rule_is_wired_into_derivation_selection(tmp_path):
    """The data rule contributes to the derived union, not just standalone.

    Production line this binds: ``_derive_tests_from_diff`` in ``land()`` —
    the single code path that computes the ``derived`` union from all four
    rules. Drop ``| set(data_tests)`` from THAT function and this test goes
    red, because it calls the function (not a local re-implementation of the
    union) and asserts membership in ``result.derived``.

    Round 1's wiring test was vacuous: it rebuilt the union locally, so
    removing ``| set(data_tests)`` from ``land()`` left the test green
    (#1101 r2). This rewrite exercises the real path.
    """
    (tmp_path / "briefs").mkdir()
    (tmp_path / "briefs" / "frame.md").write_text("# Frame\n")
    (tmp_path / "test_brief.py").write_text(
        "from pathlib import Path\n"
        "ROOT = Path('.')\n"
        "def test_frame():\n"
        "    assert 'Frame' in (ROOT / 'briefs' / 'frame.md').read_text()\n"
    )
    changed = ("briefs/frame.md",)
    diff = land_lane.Diff(changed=changed, inert=(), binding=changed, tests=())
    result = land_lane._derive_tests_from_diff(tmp_path, diff)
    assert "test_brief.py" in result.derived, (
        f"data rule not wired: test_brief.py absent from derived {result.derived!r} "
        "when briefs/frame.md changed; the _data_derived call in "
        "_derive_tests_from_diff was dropped or excluded from the derived union"
    )
    assert "test_brief.py" in result.data, (
        f"test_brief.py not in data-derived set {result.data!r}; "
        "the data rule found nothing for briefs/frame.md"
    )


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
        "derived-tests: 1 required test(s) from 2 changed path(s) by 4 rules "
        "[name=1 import=0 map=0 data=0]: test_lint.py"
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

    `test_brief.py` passes, but none of #953's derivation rules relates it to a
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
        "path(s); 1 unrelated-as-far-as-the-4-rules-can-tell: test_brief.py"
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
    assert "all 1 related by at least one of the 4 rules" in line


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


def test_land_tool_has_one_exact_scratch_removal_and_reap_still_owns_lane_removal():
    source = TOOL.read_text(encoding="utf-8")
    assert source.count('"worktree", "remove"') == 1
    assert "def _cleanup_gate_worktree" in source
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


# ---------------------------------------------------------------------------
# #1120/#1128: interrupted gating leaves a registered detached scratch while
# main remains attached. These cover absent/live/dead breadcrumbs and exact
# registered-path recovery.


def _write_dead_breadcrumb(
    root: Path, *, branch: str, merge_sha: str, phase: str
) -> tuple[Path, Path]:
    """Write a gate-in-flight breadcrumb with a pid guaranteed dead (#136).

    ``os.kill(0, 0)`` is NOT "no such process" on Linux — pid 0 means "the
    calling process's group", so it is always live. To guarantee a dead pid,
    spawn a child that exits immediately, reap it, and use its (now-recycled)
    pid: that pid refers to a process that no longer exists, so
    ``_pid_alive`` reports DEAD — the state a real SIGKILLed gate would leave
    behind (SIGKILL skips the signal handler, so the breadcrumb survives).
    """
    child = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(0)"])
    child.wait()
    dead_pid = child.pid
    scratch = (root.parent / ".worktrees" / f".gate-dead-{dead_pid}").resolve()
    _git(root, "worktree", "add", "--detach", str(scratch), "master")
    common = Path(_git(root, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    base_sha = _git(root, "rev-parse", "master")
    branch_sha = _git(root, "rev-parse", branch)
    crumb = root / ".dreamwork" / "gate-in-flight.json"
    crumb.parent.mkdir(parents=True, exist_ok=True)
    crumb.write_text(json.dumps({
        "branch": branch,
        "gate_worktree": str(scratch),
        "common_git_dir": str(common.resolve()),
        "base_ref": "master",
        "base_sha": base_sha,
        "branch_sha": branch_sha,
        "merge_sha": merge_sha,
        "phase": phase,
        "pid": dead_pid,
    }, sort_keys=True) + "\n", encoding="utf-8")
    return crumb, scratch


def _write_live_breadcrumb(root: Path, *, branch: str, merge_sha: str, phase: str) -> Path:
    """Write a gate-in-flight breadcrumb with THIS process's pid (LIVE)."""
    crumb = root / ".dreamwork" / "gate-in-flight.json"
    crumb.parent.mkdir(parents=True, exist_ok=True)
    common = Path(_git(root, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    crumb.write_text(json.dumps({
        "branch": branch,
        "gate_worktree": str((root.parent / ".worktrees" / "live-gate").resolve()),
        "common_git_dir": str(common.resolve()),
        "base_ref": "master",
        "base_sha": _git(root, "rev-parse", "master"),
        "branch_sha": _git(root, "rev-parse", branch),
        "merge_sha": merge_sha,
        "phase": phase,
        "pid": os.getpid(),
    }, sort_keys=True) + "\n", encoding="utf-8")
    return crumb


def test_dead_gate_breadcrumb_refuses_and_names_the_state(landing_repo):
    """Dead recovery removes the exact registration before the breadcrumb."""
    root, lane = landing_repo
    before = _git(root, "rev-parse", "HEAD")
    crumb, scratch = _write_dead_breadcrumb(
        root, branch="lane", merge_sha="deadbeefdeadbeef", phase="named-tests",
    )

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "REFUSE phase=gate-in-flight" in result.stderr
    # The refusal names the phase reached — the discriminating field (#1094:
    # a field no message reads is decoration). A dead gate at named-tests
    # must read differently from "no gate ran".
    assert "phase_reached=named-tests" in result.stderr
    # And the merge sha and the dead pid state.
    assert "merge=deadbeefdeadbeef" in result.stderr
    assert "DEAD" in result.stderr
    assert f"removed exact registered gate worktree {scratch}" in result.stderr
    assert "verified registration/path absent, then cleared" in result.stderr
    assert str(crumb) in result.stderr
    assert not crumb.exists()
    assert not scratch.exists()
    assert str(scratch) not in _git(root, "worktree", "list", "--porcelain")
    # master unmoved; the refuse happened before the merge.
    assert _git(root, "rev-parse", "--verify", "refs/heads/master") == before
    _assert_retained(root, lane)


def test_live_gate_breadcrumb_refuses_as_a_gate_running_now(landing_repo):
    """A LIVE breadcrumb means another gate is running right now — also refuse."""
    root, lane = landing_repo
    _write_live_breadcrumb(
        root, branch="lane", merge_sha="cafebabecafebabe", phase="repo-wide-guards",
    )

    result = _run(root, "test_named.py")

    assert result.returncode == 1
    assert "REFUSE phase=gate-in-flight" in result.stderr
    assert "LIVE" in result.stderr
    assert "phase_reached=repo-wide-guards" in result.stderr


def test_no_breadcrumb_does_not_refuse_on_detachment_alone(tmp_path):
    """A detached checkout with NO breadcrumb must not false-alarm (#1120 dir 2).

    Someone may detach the main checkout for their own reasons; the refusal
    fires on THIS TOOL's breadcrumb, not on detachment alone. This is a
    direction-2 guard: construct a detached checkout (the thing the refusal
    must NOT fire on) and confirm land_lane still reaches its normal
    preflight rather than refusing on detachment.
    """
    root, lane = _make_repo(tmp_path)
    _write(lane / "feature.txt", "lane\n")
    _git(lane, "add", "feature.txt")
    _git(lane, "commit", "-m", "lane change")
    armed = _redproof(lane, "begin", "feature.txt", "--expectation", "test_named.py")
    assert armed.returncode == 0, armed.stdout + armed.stderr
    _write(lane / "feature.txt", "inj\n")
    observed = _redproof(
        lane, "observe", "feature.txt", "--failure", "inj",
        "--command", sys.executable, "-c", "assert 0, 'inj'",
    )
    assert observed.returncode == 0, observed.stdout + observed.stderr
    _redproof(lane, "restore", "feature.txt")
    # Detach the main checkout for an unrelated reason — no breadcrumb.
    _git(root, "checkout", "--detach", "HEAD")

    result = _run(root, "test_named.py")

    # The refusal is the NORMAL preflight "requires current branch master",
    # NOT the gate-in-flight refusal — detachment alone does not trigger it.
    assert result.returncode == 1
    assert "REFUSE phase=preflight:" in result.stderr
    assert "gate-in-flight" not in result.stderr


def test_successful_landing_clears_the_breadcrumb(landing_repo):
    """A clean landing leaves no breadcrumb behind (it is deleted on success)."""
    root, lane = landing_repo
    crumb = root / ".dreamwork" / "gate-in-flight.json"
    assert not crumb.is_file(), "precondition: no breadcrumb before the run"

    result = _run(root, "test_named.py")

    assert result.returncode == 0, result.stdout + result.stderr
    assert not crumb.is_file(), (
        "a successful landing must delete the gate-in-flight breadcrumb; "
        "a leftover from a succeeded gate is a false alarm (#1120 dir 2)"
    )


def test_clean_scratch_refusal_clears_the_breadcrumb(landing_repo):
    """A post-merge gate refusal is not a death — it clears the breadcrumb.

    The breadcrumb records a gate that DIED (interrupted). A gate that ran,
    examined something, and refused is a clean exit: the checkout was restored
    and master is unmoved, so leaving the breadcrumb would be a false alarm.

    Uses a NEW failing test file rather than editing ``test_named.py``, because
    the ``landing_repo`` fixture arms redproof with ``test_named.py`` as the
    expectation source — editing it stale's the pin and refuses at red-proof,
    before the detach, so the breadcrumb would never be written.
    """
    root, lane = landing_repo
    _write(lane / "test_failing.py", "def test_fails(): assert False\n")
    _git(lane, "add", "test_failing.py")
    _git(lane, "commit", "-m", "add a failing named test")
    crumb = root / ".dreamwork" / "gate-in-flight.json"
    before = _git(root, "rev-parse", "HEAD")

    result = _run(root, "test_named.py", "test_failing.py")

    assert result.returncode == 1
    assert "REFUSE phase=named-tests" in result.stderr
    assert not crumb.is_file(), (
        "a clean post-merge refusal must clear the breadcrumb; only an "
        "interrupted gate (signal/SIGKILL) leaves it behind"
    )
    _assert_base_unmoved(root, before)


def test_cleanup_failure_retains_exact_scratch_breadcrumb(landing_repo, monkeypatch, capsys):
    root, lane = landing_repo
    _write(lane / "test_failing.py", "def test_fails(): assert False\n")
    _git(lane, "add", "test_failing.py")
    _git(lane, "commit", "-m", "reach cleanup failure")
    before = _git(root, "rev-parse", "master")
    real_cleanup = land_lane._cleanup_gate_worktree
    monkeypatch.setattr(
        land_lane, "_cleanup_gate_worktree",
        lambda repo, path: "injected exact scratch cleanup failure",
    )
    monkeypatch.chdir(root)

    assert land_lane.land("lane", ["test_named.py", "test_failing.py"]) == 1

    captured = capsys.readouterr()
    crumb = root / ".dreamwork" / "gate-in-flight.json"
    assert "RECOVERY FAILED: injected exact scratch cleanup failure" in captured.err
    assert crumb.is_file(), "breadcrumb cleared before failed scratch cleanup"
    record = json.loads(crumb.read_text(encoding="utf-8"))
    scratch = Path(record["gate_worktree"])
    assert scratch.is_dir()
    assert str(scratch) in _git(root, "worktree", "list", "--porcelain")
    assert _git(root, "branch", "--show-current") == "master"
    assert _git(root, "rev-parse", "master") == before

    monkeypatch.setattr(land_lane, "_cleanup_gate_worktree", real_cleanup)
    assert real_cleanup(root, scratch) is None
    crumb.unlink()


def test_real_sigkill_leaves_exact_scratch_and_recovery_removes_it(landing_repo):
    """A real uncatchable kill leaves the main attached and exact residue.

    This is the test the brief mandates (#1120 Direction 2): a mocked signal
    proves the handler runs, not that a real SIGTERM reaches it. Here a
    land_lane subprocess is started, allowed to reach the gate phase, then
    SIGKILL'd. Main was never detached, while the breadcrumb and registered
    scratch survive for the next invocation to recover in checked order.

    The gate phase is reached by adding a blocking named test that waits on a
    sentinel file: the land_lane subprocess will be in the named-tests gate
    when the signal arrives. A SEPARATE file avoids stale-ing the redproof
    expectation pin armed against ``test_named.py`` by the fixture.
    """
    root, lane = landing_repo
    _write(
        lane / "test_block.py",
        "import time, pathlib\n"
        "def test_block():\n"
        "    while not pathlib.Path('unblock.txt').exists():\n"
        "        time.sleep(0.05)\n",
    )
    _git(lane, "add", "test_block.py")
    _git(lane, "commit", "-m", "add a blocking named test")
    before = _git(root, "rev-parse", "HEAD")
    crumb = root / ".dreamwork" / "gate-in-flight.json"

    proc = subprocess.Popen(
        [sys.executable, str(TOOL), "lane", "test_named.py", "test_block.py"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        # Wait until the breadcrumb appears and names named-tests, proving
        # the subprocess reached the gate phase before we signal it.
        import time as _time
        deadline = _time.time() + 30
        while _time.time() < deadline:
            if crumb.is_file():
                try:
                    record = json.loads(crumb.read_text(encoding="utf-8"))
                except ValueError:
                    record = {}
                if record.get("phase") == "named-tests":
                    break
            _time.sleep(0.1)
        else:
            out, err = proc.communicate(timeout=5)
            raise AssertionError(
                f"breadcrumb never reached named-tests phase; "
                f"stdout={out!r} stderr={err!r}"
            )

        second = _run(root, "test_named.py")
        assert second.returncode == 1
        assert "REFUSE phase=gate-mutex" in second.stderr
        assert "another landing gate owns the whole-run mutex" in second.stderr

        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=15)
    finally:
        (root / "unblock.txt").write_text("unblock\n")
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)

    assert _git(root, "branch", "--show-current") == "master", (
        "main checkout detached while the scratch gate was running"
    )
    # master is unmoved — the signal arrived before the fast-forward.
    assert _git(root, "rev-parse", "--verify", "refs/heads/master") == before
    assert crumb.is_file(), (
        "SIGKILL must leave the durable breadcrumb"
    )
    record = json.loads(crumb.read_text(encoding="utf-8"))
    assert record["branch"] == "lane"
    assert record["phase"] == "named-tests"
    assert record["merge_sha"] != "<pre-merge>"
    scratch = Path(record["gate_worktree"])
    assert scratch.is_dir()
    assert str(scratch) in _git(root, "worktree", "list", "--porcelain")
    # A subsequent run refuses on the now-dead breadcrumb (pid no longer live).
    result = _run(root, "test_named.py")
    assert result.returncode == 1
    assert "REFUSE phase=gate-in-flight" in result.stderr
    assert "DEAD" in result.stderr
    assert "phase_reached=named-tests" in result.stderr
    assert f"removed exact registered gate worktree {scratch}" in result.stderr
    assert not scratch.exists()
    assert not crumb.exists()


# ---------------------------------------------------------------------------
# #1140: the gate derives the requirement and runs check, but never ingests the
# lane's prose hand-off. Its silence read as a prose verification it never
# performed (#651). The authority note states plainly what the gate verified
# (the registry against a derived requirement) and what it did NOT (the prose,
# which is gitignored and does not travel). These tests pin that line so a
# regression that lets the gate read as a prose verification is caught.
def test_gate_prints_authority_note_that_prose_was_not_an_input(doc_only_repo):
    """A doc-only lane (require 0) lands, and the gate prints a line stating the
    prose hand-off was NOT an input. #1140/#651: without this line the gate's
    silence reads as 'the lane's quoted number was verified', which it was not —
    the requirement was derived from the diff and checked against the registry."""
    root, lane = doc_only_repo
    result = _run(root, "test_named.py")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "red-proof requirement: 0 injections REQUIRED" in result.stdout
    # The discriminating authority line: it names BOTH what was derived and what
    # was not consulted. A bare "verified" string would not satisfy either half.
    assert "red-proof authority: 0 injections were REQUIRED (derived from the" in result.stdout
    assert "prose hand-off report was NOT an input to this gate" in result.stdout


def test_authority_note_responds_to_a_stale_paste_without_affecting_the_landing(
    landing_repo,
):
    """A binding lane (require 1) with a real, restored red-proof lands, and the
    authority note names the residual hole: a matching integer from a stale paste
    or recollection is not detected by the gate. The lane still LANDS — the note
    is a statement of the gate's authority boundary, not a new refusal."""
    root, lane = landing_repo
    result = _run(root, "test_named.py")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "red-proof requirement: 1 injection required" in result.stdout
    # The require>0 variant of the authority note names the residual hole
    # explicitly (#1140 direction 2): a stale paste is the open false-green.
    assert "1 injection(s) were REQUIRED (derived from the branch diff" in result.stdout
    assert "stale paste or from recollection is not detected by the gate" in result.stdout


def test_authority_note_does_not_claim_to_have_verified_the_lane_ran_handoff(doc_only_repo):
    """#651: the authority note must NOT name a failure mode it cannot detect.
    The gate cannot establish which command produced the lane's prose, so the
    note says so. A claim like 'the lane ran handoff' would be #651's shape."""
    root, lane = doc_only_repo
    result = _run(root, "test_named.py")
    assert result.returncode == 0, result.stdout + result.stderr
    note_lines = [
        line for line in result.stdout.splitlines()
        if line.startswith("red-proof authority:")
    ]
    assert len(note_lines) == 1, f"expected exactly one authority line, got {note_lines}"
    # It must name what it CANNOT establish, not assert it did.
    assert "cannot establish which command produced" in note_lines[0]


# ---------------------------------------------------------------------------
# #1157 — batched rebase-then-gate landing.
#
# When N branches are ready, landing the first staleifies the rest. The batch
# path rebases each entry onto the CURRENT master immediately before its gate,
# absorbing each landing before the next. These tests drive REAL fixture repos
# with REAL branches — not stubbed gates (#1157 red-proof direction 2).
# ---------------------------------------------------------------------------

def _run_batch(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), "batch", *args],
        cwd=root, capture_output=True, text=True,
    )


def _make_two_lane_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A base checkout plus two empty lane worktrees (branches 'lane', 'lane-b')."""
    root, lane_a = _make_repo(tmp_path)
    lane_b = tmp_path / "lane-b"
    _git(root, "worktree", "add", "-b", "lane-b", str(lane_b), "master")
    return root, lane_a, lane_b


@pytest.fixture
def batch_two_doc_lanes(tmp_path: Path):
    """Two doc-only lanes adding DIFFERENT files — neither conflicts on rebase.

    Each is inert documentation (.dreamwork/docs/*.md) so require=0 and no
    red-proof injection is needed (#1018). The diff is genuinely code-free so
    the #1010 empty-selection guarantee still holds for any branch that has a
    binding path — these do not.
    """
    root, lane_a, lane_b = _make_two_lane_repo(tmp_path)
    _write(lane_a / ".dreamwork" / "docs" / "alpha.md", "# Alpha\n")
    _git(lane_a, "add", ".dreamwork/docs/alpha.md")
    _git(lane_a, "commit", "-m", "doc alpha")
    _write(lane_b / ".dreamwork" / "docs" / "beta.md", "# Beta\n")
    _git(lane_b, "add", ".dreamwork/docs/beta.md")
    _git(lane_b, "commit", "-m", "doc beta")
    return root, lane_a, lane_b


def test_batch_lands_two_stale_doc_branches_by_rebasing_per_entry(batch_two_doc_lanes):
    """THE test (#1157): landing branch 1 staleifies branch 2, and the batch
    recovers by rebasing each entry onto current master immediately before its
    gate. If the rebase happened up front (the trap), branch 2 would be gated
    against a stale master and refuse — this test discriminates that.
    """
    root, lane_a, lane_b = batch_two_doc_lanes
    master_before = _git(root, "rev-parse", "--verify", "refs/heads/master")

    result = _run_batch(
        root, "--entry", "lane", "--entry", "lane-b",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    master_after = _git(root, "rev-parse", "--verify", "refs/heads/master")
    # Master advanced (at least once — landing lane staleifies lane-b, which
    # the batch then rebases and lands too).
    assert master_after != master_before, "master did not advance at all"
    # Both branches landed — not an aggregate "exit 0" (#1157 trap: "assert
    # the batch exited 0"). Each entry's verdict is named individually.
    assert "lane: LANDED" in result.stdout, result.stdout
    assert "lane-b: LANDED" in result.stdout, result.stdout
    # Both denominators stated (#868).
    assert "batch summary: attempted=2 landed=2" in result.stdout
    # Lane-a's landing advanced master; lane-b was rebased onto that new tip
    # before its own gate. If the rebase were up-front, lane-b would REFUSE.
    assert "REFUSE phase=preflight: branch is not rebased" not in result.stdout


def test_batch_master_advanced_once_per_landing(batch_two_doc_lanes):
    """The batch is serial: each landing fast-forwards master exactly once, so
    two landings = two distinct master shas after the batch. This catches the
    'rebase all up front' defect: in that case branch 2 refuses at preflight
    and master advances only once.
    """
    root, lane_a, lane_b = batch_two_doc_lanes
    master_before = _git(root, "rev-parse", "--verify", "refs/heads/master")

    result = _run_batch(root, "--entry", "lane", "--entry", "lane-b")
    assert result.returncode == 0, result.stdout + result.stderr

    # After the batch, master should have advanced past BOTH merges. The merge
    # commits are distinct (each has a different set of parents/content), so
    # counting commits from master_before to master should be at least 2
    # (one merge per landing, possibly more if fast-forward creates commits).
    count = _git(
        root, "rev-list", "--count", f"{master_before}..master",
    )
    assert int(count) >= 2, (
        f"master advanced only {count} commit(s) from the before-sha; "
        f"expected >= 2 (one per landing)"
    )


@pytest.fixture
def batch_conflict_lanes(tmp_path: Path):
    """Two doc lanes that both ADD the SAME file with different content.

    Lane-a lands first (adding the file); lane-b's rebase then hits an
    add/add conflict — both branches created .dreamwork/docs/shared.md.
    The batch must abort the rebase, leave lane-b's worktree clean, and
    continue (not die on the first conflict).
    """
    root, lane_a, lane_b = _make_two_lane_repo(tmp_path)
    _write(lane_a / ".dreamwork" / "docs" / "shared.md", "# From lane-a\n")
    _git(lane_a, "add", ".dreamwork/docs/shared.md")
    _git(lane_a, "commit", "-m", "doc shared from a")
    _write(lane_b / ".dreamwork" / "docs" / "shared.md", "# From lane-b\n")
    _git(lane_b, "add", ".dreamwork/docs/shared.md")
    _git(lane_b, "commit", "-m", "doc shared from b")
    return root, lane_a, lane_b


def test_batch_rebase_conflict_continues_and_leaves_worktree_clean(
    batch_conflict_lanes,
):
    """A rebase conflict must not strand every later branch (#1157 req 2).
    The batch aborts the rebase (leaving the branch untouched), reports the
    conflict loudly, and continues. #1159: a mid-rebase worktree breaks OTHER
    gates, so the worktree must be clean afterward.
    """
    root, lane_a, lane_b = batch_conflict_lanes
    master_before = _git(root, "rev-parse", "--verify", "refs/heads/master")

    result = _run_batch(root, "--entry", "lane", "--entry", "lane-b")

    # The batch exits non-zero (not all entries landed).
    assert result.returncode == 1, result.stdout + result.stderr
    # Lane-a landed; lane-b hit a rebase conflict.
    assert "lane: LANDED" in result.stdout, result.stdout
    assert "lane-b: CONFLICT" in result.stdout, result.stdout
    assert "rebase-conflict=1" in result.stdout, result.stdout
    # Master advanced once (lane-a landed; lane-b did not).
    master_after = _git(root, "rev-parse", "--verify", "refs/heads/master")
    assert master_after != master_before, "lane-a did not land"
    # Lane-b's worktree must be clean — no half-rebased state (#1159).
    assert lane_b.is_dir(), "lane-b worktree was removed"
    status = _git(lane_b, "status", "--porcelain=v1", "--untracked-files=no")
    assert status == "", f"lane-b worktree is dirty after aborted rebase: {status}"
    # Lane-b's branch ref must still exist.
    assert _git(root, "show-ref", "--verify", "refs/heads/lane-b")


@pytest.fixture
def batch_landed_plus_refused(tmp_path: Path):
    """One doc-only lane (lands) and one code lane with no named tests (refused).

    Lane-b adds a binding .py file but names no tests, so land() refuses at
    the selection phase ('named test selection is empty' for a branch with
    binding paths). The batch must report the refusal loudly and continue.
    """
    root, lane_a, lane_b = _make_two_lane_repo(tmp_path)
    _write(lane_a / ".dreamwork" / "docs" / "alpha.md", "# Alpha\n")
    _git(lane_a, "add", ".dreamwork/docs/alpha.md")
    _git(lane_a, "commit", "-m", "doc alpha")
    _write(lane_b / "new_tool.py", "VALUE = 1\n")
    _git(lane_b, "add", "new_tool.py")
    _git(lane_b, "commit", "-m", "code change with no tests")
    return root, lane_a, lane_b


def test_batch_gate_refusal_continues_and_reports_loudly(batch_landed_plus_refused):
    """A gate REFUSAL must not stop the batch (#1157 req 3), but it must be
    reported loudly and distinguishably from a pass.
    """
    root, lane_a, lane_b = batch_landed_plus_refused
    master_before = _git(root, "rev-parse", "--verify", "refs/heads/master")

    # Lane-a has no tests (doc-only, legal #1018); lane-b has no tests but a
    # binding path (illegal — land() refuses at selection).
    result = _run_batch(root, "--entry", "lane", "--entry", "lane-b")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "lane: LANDED" in result.stdout, result.stdout
    assert "lane-b: REFUSED" in result.stdout, result.stdout
    assert "refused=1" in result.stdout, result.stdout
    # The refusal reason must be visible.
    assert "REFUSE phase=selection" in result.stderr, result.stderr
    # Master advanced once (lane-a); lane-b's worktree is retained.
    master_after = _git(root, "rev-parse", "--verify", "refs/heads/master")
    assert master_after != master_before
    assert lane_b.is_dir(), "lane-b worktree was removed despite refusal"


def test_batch_with_zero_entries_refuses_not_exit_zero(tmp_path: Path):
    """A batch with zero entries must exit non-zero — 'the batch exited 0' is
    vacuous when zero branches were gated (#1157 trap, #868 denominator).
    """
    root, _lane = _make_repo(tmp_path)
    result = _run_batch(root)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "REFUSE batch: no entries" in result.stderr, result.stderr


def test_batch_entry_without_registered_worktree_is_skipped(tmp_path: Path):
    """An entry whose branch has no registered linked worktree is SKIPPED, not
    a crash. The batch continues and names it in the summary.
    """
    root, _lane = _make_repo(tmp_path)
    result = _run_batch(root, "--entry", "nonexistent-branch")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "nonexistent-branch: SKIPPED" in result.stdout, result.stdout
    assert "skipped=1" in result.stdout, result.stdout


def test_batch_summary_reports_all_five_outcomes_distinguishably(tmp_path: Path):
    """#136: the batch has FIVE outcomes (landed / refused / rebase-conflict /
    abort-failed / skipped) and they must stay distinguishable in the output.
    This test constructs a batch that exercises four of them in one run and
    asserts the fifth (abort-failed) is stated at zero, so a pass is never
    silent about whether a worktree was stranded.

    Entries: (1) a doc-only lane that lands; (2) a doc-only lane that conflicts
    with #1 on rebase; (3) a code lane with no tests that refuses at selection;
    (4) a branch with no registered worktree that is skipped.
    """
    root, lane_a, lane_b = _make_two_lane_repo(tmp_path)

    # Lane-a and lane-b both add the same shared doc (conflict after a lands).
    _write(lane_a / ".dreamwork" / "docs" / "shared.md", "# From a\n")
    _git(lane_a, "add", ".dreamwork/docs/shared.md")
    _git(lane_a, "commit", "-m", "doc shared from a")
    _write(lane_b / ".dreamwork" / "docs" / "shared.md", "# From b\n")
    _git(lane_b, "add", ".dreamwork/docs/shared.md")
    _git(lane_b, "commit", "-m", "doc shared from b")

    # Lane-c: code change, no named tests → refuses at selection.
    lane_c = tmp_path / "lane-c"
    _git(root, "worktree", "add", "-b", "lane-c", str(lane_c), "master")
    _write(lane_c / "new_tool.py", "VALUE = 1\n")
    _git(lane_c, "add", "new_tool.py")
    _git(lane_c, "commit", "-m", "code with no tests")

    result = _run_batch(
        root,
        "--entry", "lane",         # LANDED
        "--entry", "lane-b",       # CONFLICT (same file)
        "--entry", "lane-c",       # REFUSED (binding, no tests)
        "--entry", "ghost",        # SKIPPED (no worktree)
    )

    assert result.returncode == 1, result.stdout + result.stderr
    summary = [l for l in result.stdout.splitlines() if "batch summary:" in l]
    assert len(summary) == 1, f"expected one summary line, got {summary}"
    assert "attempted=4" in summary[0]
    assert "landed=1" in summary[0]
    assert "rebase-conflict=1" in summary[0]
    assert "refused=1" in summary[0]
    assert "skipped=1" in summary[0]
    # #1157 round 2: the abort-failed denominator is stated even at zero, so a
    # pass is never silent about whether a worktree was stranded (#868/#136).
    assert "abort-failed=0" in summary[0]
    # Each branch is named with its distinct state marker.
    assert "lane: LANDED" in result.stdout
    assert "lane-b: CONFLICT" in result.stdout
    assert "lane-c: REFUSED" in result.stdout
    assert "ghost: SKIPPED" in result.stdout


# ---------------------------------------------------------------------------
# #1157 round 2 — the P1: rebase cleanup must be exception-safe (a checked
# `finally`) and the abort's own result must be checked. These drive REAL git
# state (a real paused rebase, a real abort failure), not a stubbed gate.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# #1157 round 3 — the P1: a refused gate must not rewrite the lane's branch.
# The batch runs the non-mutating refusal checks (breadcrumb, dirty main)
# BEFORE the rebase, holding the mutex across both. These prove the lane SHA
# is byte-identical after each refusal the reviewer named (#136: "refused and
# left alone" is a distinct state from "refused after mutating").
# ---------------------------------------------------------------------------


def _stale_lane_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A repo where the lane is GENUINELY stale: master advanced after the lane
    branched, so a ``git rebase master`` in the lane WOULD move its ref.

    This is the discriminating substrate for the round-3 refusal tests: if the
    rebase ran before the refusal check (the bug), the lane ref moves; if the
    preflight ran first (the fix), it does not. A lane that is already up to
    date would not move on rebase, so a test against it could not tell the two
    apart — that is the false-green this fixture exists to close.
    """
    root, lane = _make_repo(tmp_path)
    # Lane has a doc-only commit (inert, so no named-tests requirement).
    _write(lane / ".dreamwork" / "docs" / "stale.md", "# stale\n")
    _git(lane, "add", ".dreamwork/docs/stale.md")
    _git(lane, "commit", "-m", "doc stale")
    # Master advances AFTER the lane branched → the lane is stale. A rebase
    # would replay the lane's commit onto this new tip, producing a new sha.
    _write(root / "master-advance.txt", "master\n")
    _git(root, "add", "master-advance.txt")
    _git(root, "commit", "-m", "master advances")
    return root, lane


def test_batch_refuses_dirty_main_without_rebasing_the_lane(tmp_path: Path):
    """#1157 round 3 P1. A dirty main checkout refuses at the batch preflight
    (BEFORE the rebase), so the lane ref is byte-identical to its pre-batch
    value. Asserting 'the batch refused' alone is vacuous — round 2 already
    refuses; this asserts the STATE that makes the fix meaningful (#136).
    """
    root, lane = _stale_lane_repo(tmp_path)
    lane_before = _git(root, "rev-parse", "refs/heads/lane")

    # Dirty main: a tracked file modified, not committed (a real dirty
    # checkout, not a mocked refusal — a mocked refusal proves the mock).
    _write(root / "test_named.py", "MODIFIED\n")

    result = _run_batch(root, "--entry", "lane")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "REFUSE phase=preflight: tracked worktree state is not clean" in result.stderr
    assert "lane: REFUSED" in result.stdout, result.stdout
    # THE assertion — the lane ref did not move (#136).
    lane_after = _git(root, "rev-parse", "refs/heads/lane")
    assert lane_after == lane_before, (
        f"dirty-main refusal moved the lane ref {lane_before[:12]} -> "
        f"{lane_after[:12]} — a REFUSE must change nothing (#136)"
    )
    assert "lane-ref-mutated=False" in result.stderr, (
        f"refusal reported a mutated lane ref: {result.stderr}"
    )


def test_batch_refuses_live_breadcrumb_without_rebasing_the_lane(tmp_path: Path):
    """#1157 round 3 P1. A LIVE gate-in-flight breadcrumb (another gate is
    running right now) refuses at the batch preflight before the rebase, so
    the lane ref is unchanged. The breadcrumb's pid is THIS test process,
    which is alive while the batch subprocess runs, so it reads as LIVE.
    """
    root, lane = _stale_lane_repo(tmp_path)
    lane_before = _git(root, "rev-parse", "refs/heads/lane")
    _write_live_breadcrumb(
        root, branch="lane", merge_sha="livebeef", phase="named-tests",
    )

    result = _run_batch(root, "--entry", "lane")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "REFUSE phase=gate-in-flight" in result.stderr
    assert "LIVE" in result.stderr, result.stderr
    lane_after = _git(root, "rev-parse", "refs/heads/lane")
    assert lane_after == lane_before, (
        f"live-breadcrumb refusal moved the lane ref {lane_before[:12]} -> "
        f"{lane_after[:12]} (#136)"
    )
    assert "lane-ref-mutated=False" in result.stderr


def test_batch_refuses_dead_breadcrumb_without_rebasing_the_lane(tmp_path: Path):
    """#1157 round 3 P1. A DEAD gate-in-flight breadcrumb (a prior gate died
    mid-flight) refuses at the batch preflight before the rebase, so the lane
    ref is unchanged. The dead breadcrumb names an exact scratch worktree; the
    refusal may recover (remove) it, but it never touches the lane ref.
    """
    root, lane = _stale_lane_repo(tmp_path)
    lane_before = _git(root, "rev-parse", "refs/heads/lane")
    _write_dead_breadcrumb(
        root, branch="lane", merge_sha="deadbeef", phase="named-tests",
    )

    result = _run_batch(root, "--entry", "lane")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "REFUSE phase=gate-in-flight" in result.stderr
    assert "DEAD" in result.stderr, result.stderr
    lane_after = _git(root, "rev-parse", "refs/heads/lane")
    assert lane_after == lane_before, (
        f"dead-breadcrumb refusal moved the lane ref {lane_before[:12]} -> "
        f"{lane_after[:12]} (#136)"
    )
    assert "lane-ref-mutated=False" in result.stderr


def _conflicting_lane_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A base checkout plus a lane whose rebase onto master hits a REAL add/add
    conflict: master and the lane both add ``shared.txt`` with different bytes.

    Leaves the lane clean and NOT yet rebased, so a caller can either let the
    helper start the rebase or start it themselves to pre-create the paused
    state (the abort-failed fixture).
    """
    root, lane = _make_repo(tmp_path)
    _write(root / "shared.txt", "from master\n")
    _git(root, "add", "shared.txt")
    _git(root, "commit", "-m", "master adds shared")
    _write(lane / "shared.txt", "from lane\n")
    _git(lane, "add", "shared.txt")
    _git(lane, "commit", "-m", "lane adds shared")
    return root, lane


def _git_raw(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """git without the rc==0 assert — for commands that legitimately fail
    (a conflicting rebase) or that we run to inspect a stranded state."""
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True
    )


def test_post_conflict_exception_is_cleaned_in_finally_leaving_worktree_clean(
    tmp_path, monkeypatch
):
    """#1157 P1, finally half. A rebase that REALLY conflicted leaves a real
    paused-rebase state; an exception raised in the POST-conflict handling
    seam (``_relay``, which runs AFTER ``_git(rebase)`` has returned) must not
    strand the worktree. Cleanup runs in a checked ``finally``, so the branch
    ref is restored and the worktree is clean.

    The conflicting rebase and the paused-rebase state it leaves are REAL
    (direction-2: drive a real git rebase into a real conflict, not a stubbed
    gate). Asserting 'the batch continued' would be vacuous; this asserts the
    STATE it would continue from — no stranded rebase, branch ref restored to
    its pre-rebase sha.

    LIMIT (#651): this does NOT prove an exception raised WHILE the git
    subprocess is still running. ``_relay`` is invoked only after
    ``_git(... rebase ...)`` returns (dev/land_lane.py), so the interruption
    lands between failure detection and cleanup, not during the rebase itself.
    Driving a genuine mid-subprocess interruption would require coordinating a
    blocking git hook with a mid-``subprocess.run`` signal, which is not done
    here; the rename to 'post-conflict' is what makes the name agree with what
    the assertions actually prove.
    """
    root, lane = _conflicting_lane_repo(tmp_path)
    lane_before = _git(lane, "rev-parse", "HEAD")

    # _relay is called right after the conflict is detected, before cleanup.
    # Raising there simulates an interruption between the returned conflict
    # and the abort. The conflicting rebase itself is real; only the
    # output-printing seam raises (see the LIMIT above — not a mid-git raise).
    def interrupting_relay(_result):
        raise RuntimeError("RED-PROOF interruption: raised in post-conflict handling")

    monkeypatch.setattr(land_lane, "_relay", interrupting_relay)

    attempt = land_lane._rebase_lane_checked(lane, "master")

    # The exception was recorded (the rebase did not complete cleanly), and
    # cleanup ran in the finally despite it.
    assert attempt.state == "conflict", attempt.detail
    assert "raised in post-conflict handling" in attempt.detail, attempt.detail
    # THE assertions — the state the batch would continue from:
    assert not land_lane._rebase_in_progress(lane), (
        "worktree left mid-rebase after a post-conflict exception (finally did not clean up)"
    )
    status = _git_raw(lane, "status", "--porcelain=v1", "--untracked-files=no").stdout
    assert status == "", f"worktree dirty after post-conflict exception: {status}"
    lane_after = _git(lane, "rev-parse", "HEAD")
    assert lane_after == lane_before, (
        f"branch ref moved {lane_before[:12]} -> {lane_after[:12]} after a "
        f"post-conflict exception; the abort did not restore it"
    )


def test_failed_rebase_abort_is_a_distinct_stranded_outcome(tmp_path):
    """#1157 P1, checked-abort half (#136). When ``git rebase --abort`` itself
    FAILS while a rebase is genuinely paused, that is a STRANDED worktree — a
    distinct state from a routine conflict (where the abort restored the
    branch cleanly). The two must not collapse.

    The paused rebase is REAL (a real add/add conflict, left in place), and
    the abort failure is REAL: a read-only git dir makes ``git rebase --abort``
    exit 128 ('Unable to create index.lock: Permission denied'). Nothing is
    stubbed. The worktree stays stranded because the abort genuinely could not
    clean up — and the outcome names that, loudly, instead of 'conflict'.
    """
    root, lane = _conflicting_lane_repo(tmp_path)
    lane_before = _git(lane, "rev-parse", "HEAD")

    # Start the rebase for real: it conflicts and pauses (rc != 0).
    started = _git_raw(lane, "rebase", "master")
    assert started.returncode != 0, "fixture rebase should have conflicted"
    assert land_lane._rebase_in_progress(lane), "fixture should be mid-rebase"

    # Make the abort genuinely fail: a read-only git dir blocks the writes
    # --abort needs (index.lock, removing the rebase-merge dir).
    git_dir = _git(lane, "rev-parse", "--absolute-git-dir")
    subprocess.run(["chmod", "-R", "a-w", git_dir], check=True)
    try:
        attempt = land_lane._rebase_lane_checked(lane, "master")
    finally:
        # Restore writability so pytest can tear down tmp_path.
        subprocess.run(["chmod", "-R", "u+w", git_dir], check=True)

    # The discriminating assertion (#136): abort-failed is NOT conflict.
    assert attempt.state == "abort-failed", (
        f"failed abort collapsed into '{attempt.state}' — a stranded worktree "
        f"must be its own outcome, not a routine conflict (detail: {attempt.detail})"
    )
    # The abort really did fail (its failure output was captured) and the
    # worktree really is stranded — the paused rebase was NOT cleaned up.
    assert attempt.detail, "abort-failed but no failure output captured"
    assert land_lane._rebase_in_progress(lane), (
        "abort-failed outcome but the worktree is not stranded — the fixture "
        "no longer reproduces a real failed abort"
    )
    # The branch REF was not advanced to master (the rebase never completed):
    # a rebase detaches HEAD but leaves refs/heads/<branch> at its original
    # tip, and the failed abort changed neither. The lane tip is intact.
    assert _git(root, "rev-parse", "refs/heads/lane") == lane_before, (
        "the lane branch ref moved even though the rebase never completed"
    )


def test_batch_reports_abort_failed_loudly_with_distinct_marker(
    tmp_path, monkeypatch, capsys
):
    """The batch must surface an ``abort-failed`` entry as its own loud marker
    and count it in the summary — not fold it into rebase-conflict (#136).

    A real abort-failure cannot be timed inside a single batch run (the git dir
    must be writable for the rebase to pause, then read-only for the abort to
    fail), so this exercises the batch's *response* to that outcome by routing
    the (real, separately-tested) helper to return it. It proves the marker,
    the stderr line, and both denominators — the git behaviour is proven by the
    two fixtures above. The monkeypatch short-circuits before land(), so no
    gate runs.
    """
    root, lane_a, lane_b = _make_two_lane_repo(tmp_path)
    _write(lane_a / ".dreamwork" / "docs" / "alpha.md", "# Alpha\n")
    _git(lane_a, "add", ".dreamwork/docs/alpha.md")
    _git(lane_a, "commit", "-m", "doc alpha")

    monkeypatch.setattr(
        land_lane, "_rebase_lane_checked",
        lambda lane, base: land_lane._RebaseAttempt(
            "abort-failed", "index.lock: Permission denied"
        ),
    )
    monkeypatch.chdir(root)

    rc = land_lane.land_batch(
        [land_lane.BatchEntry("lane", ()), land_lane.BatchEntry("lane-b", ())],
        base="master",
    )
    out, err = capsys.readouterr()

    assert rc == 1
    # Distinct marker, not CONFLICT (#136).
    assert "lane: ABORTBAD" in out, out
    assert "lane-b: ABORTBAD" in out, out
    assert "lane: CONFLICT" not in out
    # Reported loudly on stderr, naming the stranded worktree.
    assert "lane: ABORT-FAILED" in err, err
    assert "stranded" in err, err
    # Both denominators stated (#868): attempted and abort-failed counts.
    assert "attempted=2" in out, out
    assert "abort-failed=2" in out, out
    assert "rebase-conflict=0" in out, out
