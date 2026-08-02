#!/usr/bin/env python3
"""Red-first integration tests for the checked lane-worktree reaper (#686)."""

import importlib.machinery
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent
CLI = REPO / "dev" / "reap.py"


def _load_reap():
    loader = importlib.machinery.SourceFileLoader("lane_reap", str(CLI))
    spec = importlib.util.spec_from_loader("lane_reap", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    return module


def _run(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(CLI), *(str(arg) for arg in args)],
        capture_output=True,
        text=True,
    )


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args],
        stderr=subprocess.DEVNULL,
        text=True,
    ).strip()


@pytest.fixture
def lane(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "master")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    (root / ".gitignore").write_text(
        "__pycache__/\n.dreamwork/applied.md\n*.tmp.*\nnode_modules/\n",
        encoding="utf-8",
    )
    (root / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(root, "add", ".gitignore", "tracked.txt")
    _git(root, "commit", "-qm", "base")
    worktree = tmp_path / "lane"
    _git(root, "worktree", "add", "-q", "-b", "wt/lane", str(worktree), "master")
    return root, worktree


def test_tracked_dirty_path_refuses_and_names_what_would_be_lost(lane):
    _, worktree = lane
    (worktree / "tracked.txt").write_text("unfinished\n", encoding="utf-8")

    result = _run("--check", worktree)

    assert result.returncode == 1
    assert f"path={worktree.resolve()}" in result.stderr
    assert "tracked-dirty=1" in result.stderr
    assert "untracked=0" in result.stderr
    assert "ignored=0" in result.stderr
    assert "tracked.txt" in result.stderr


def test_index_only_change_is_tracked_dirty(lane):
    _, worktree = lane
    (worktree / "tracked.txt").write_text("staged only\n", encoding="utf-8")
    _git(worktree, "add", "tracked.txt")

    result = _run("--check", worktree)

    assert result.returncode == 1
    assert "tracked-dirty=1" in result.stderr
    assert "tracked.txt" in result.stderr


def test_brief_and_ignored_cache_do_not_fire_the_gate(lane):
    _, worktree = lane
    (worktree / "BRIEF.md").write_text("lane-local brief\n", encoding="utf-8")
    cache = worktree / "__pycache__"
    cache.mkdir()
    (cache / "tool.pyc").write_bytes(b"cache")

    result = _run("--check", worktree)

    assert result.returncode == 0, result.stderr
    assert f"path={worktree.resolve()}" in result.stdout
    assert "tracked-dirty=0" in result.stdout
    # #760: untracked and ignored are split, not collapsed. BRIEF.md is the one
    # expected untracked scratch, so it is not named; the cache is ignored.
    assert "untracked=1" in result.stdout
    assert "ignored=1" in result.stdout
    assert "ignored: examined 1 file; 1 disposable, 0 NOT disposable" in result.stdout
    assert "unmerged-commits=0" in result.stdout
    assert "NOTE:" not in result.stderr


def test_ignored_evidence_is_named_without_changing_the_gate(lane):
    _, worktree = lane
    evidence = worktree / ".dreamwork" / "applied.md"
    evidence.parent.mkdir()
    evidence.write_text("actor=coordinator-drain\n", encoding="utf-8")

    result = _run("--check", worktree)

    assert result.returncode == 0, result.stderr
    assert "ignored=1" in result.stdout
    assert "ignored: examined 1 file; 0 disposable, 1 NOT disposable" in result.stdout
    assert ".dreamwork/applied.md" in result.stdout


def test_unforeseen_ignored_file_type_falls_through_allowlist(lane):
    _, worktree = lane
    (worktree / "red-proof.tmp.unforeseen").write_text("unknown kind\n", encoding="utf-8")

    result = _run("--check", worktree)

    assert result.returncode == 0, result.stderr
    assert "1 NOT disposable: red-proof.tmp.unforeseen" in result.stdout


def test_handwritten_note_inside_pycache_is_not_hidden_by_directory_name(lane):
    _, worktree = lane
    cache = worktree / "__pycache__"
    cache.mkdir()
    (cache / "handwritten-note.md").write_text("keep me\n", encoding="utf-8")

    result = _run("--check", worktree)

    assert result.returncode == 0, result.stderr
    assert "1 NOT disposable: __pycache__/handwritten-note.md" in result.stdout


def test_ignored_symlink_does_not_report_files_beyond_the_worktree(lane, tmp_path):
    _, worktree = lane
    outside = tmp_path / "coordinator-secret-report.md"
    outside.write_text("not in the lane\n", encoding="utf-8")
    dependencies = worktree / "node_modules"
    dependencies.mkdir()
    (dependencies / "external-report").symlink_to(outside)

    result = _run("--check", worktree)

    assert result.returncode == 0, result.stderr
    assert "ignored: examined 1 file; 1 disposable, 0 NOT disposable" in result.stdout
    assert "coordinator-secret-report.md" not in result.stdout


def test_untracked_deliverable_is_named_and_distinguishable_from_cache_only(lane):
    """#760 direction 1: the discriminating case the collapsed counter hid.

    A lane holding an untracked deliverable plus expected scratch must NOT read
    identically to one holding only scratch + cache. The split counters differ
    and — critically — the deliverable path is NAMED, which the count alone
    never was.
    """
    _, worktree = lane
    (worktree / "BRIEF.md").write_text("lane-local brief\n", encoding="utf-8")
    deliverable = worktree / ".dreamwork" / "lane-999-report.md"
    deliverable.parent.mkdir()
    deliverable.write_text("# deliverable about to be lost\n", encoding="utf-8")

    result = _run("--check", worktree)

    assert result.returncode == 0, result.stderr  # still passes (#755)
    assert "untracked=2" in result.stdout
    assert "ignored=0" in result.stdout
    # The deliverable path is named: a count alone cannot say WHICH file, and
    # that is the signal that turns a number into something actionable.
    assert ".dreamwork/lane-999-report.md" in result.stderr
    # BRIEF.md is expected scratch; it must NOT be named as unexpected.
    assert "BRIEF.md" not in result.stderr


def test_expected_scratch_and_ignored_read_identically_under_split(lane):
    """#760 direction 1 complement: the SAFE lane is still clean and unnamed.

    The scratch+cache lane must read with the SAME counters as before the fix
    (untracked=1 ignored=1), and no NOTE lines, so a coordinator's healthy
    baseline is preserved (#755).
    """
    _, worktree = lane
    (worktree / "BRIEF.md").write_text("lane-local brief\n", encoding="utf-8")
    cache = worktree / "__pycache__"
    cache.mkdir()
    (cache / "tool.pyc").write_bytes(b"cache")

    result = _run("--check", worktree)

    assert result.returncode == 0, result.stderr
    assert "untracked=1" in result.stdout
    assert "ignored=1" in result.stdout
    assert "NOTE:" not in result.stderr


def test_non_worktree_is_unknown_not_clean(tmp_path):
    ordinary = tmp_path / "ordinary"
    ordinary.mkdir()

    result = _run("--check", ordinary)

    assert result.returncode == 2
    assert f"path={ordinary.resolve()}" in result.stderr
    assert "tracked-dirty=unknown" in result.stderr
    assert "untracked=unknown" in result.stderr
    assert "ignored=unknown" in result.stderr
    assert "not a registered linked worktree" in result.stderr


def test_zero_ignored_population_is_visibly_not_an_all_clear(lane):
    _, worktree = lane

    result = _run("--check", worktree)

    assert result.returncode == 0, result.stderr
    assert "ignored=0" in result.stdout
    assert "ignored: examined 0 files; NOT an all-clear" in result.stdout


def test_git_status_failure_is_unknown_not_clean(tmp_path, monkeypatch, capsys):
    target = tmp_path / "lane"
    target.mkdir()
    reap = _load_reap()
    monkeypatch.setattr(reap, "_registered_worktrees",
                        lambda path: [tmp_path.resolve(), path])
    monkeypatch.setattr(reap, "_status_paths", lambda path: None)

    rc = reap.reap(str(target), check_only=True)

    err = capsys.readouterr().err
    assert rc == 2
    assert "tracked-dirty=unknown" in err
    assert "untracked=unknown" in err
    assert "ignored=unknown" in err
    assert "git status failed" in err


def test_clean_branch_with_unmerged_commit_refuses(lane):
    _, worktree = lane
    (worktree / "landed.txt").write_text("committed lane output\n", encoding="utf-8")
    _git(worktree, "add", "landed.txt")
    _git(worktree, "commit", "-qm", "feat(#686): lane output")
    sha = _git(worktree, "rev-parse", "--short=12", "HEAD")

    result = _run("--check", worktree)

    assert result.returncode == 1
    assert "tracked-dirty=0" in result.stderr
    assert "untracked=0" in result.stderr
    assert "ignored=0" in result.stderr
    assert "unmerged-commits=1" in result.stderr
    assert sha in result.stderr
    assert "feat(#686): lane output" in result.stderr


def test_force_names_every_discarded_path_and_removes_worktree(lane):
    root, worktree = lane
    (worktree / "tracked.txt").write_text("unfinished\n", encoding="utf-8")
    (worktree / "BRIEF.md").write_text("scratch\n", encoding="utf-8")
    cache = worktree / "__pycache__"
    cache.mkdir()
    (cache / "tool.pyc").write_bytes(b"cache")

    result = _run("--force", worktree)

    assert result.returncode == 0, result.stderr
    assert "FORCE: discarding tracked path: tracked.txt" in result.stderr
    assert "FORCE: discarding untracked path: BRIEF.md" in result.stderr
    assert "FORCE: discarding ignored path: __pycache__/" in result.stderr
    assert not worktree.exists()
    assert str(worktree.resolve()) not in _git(root, "worktree", "list", "--porcelain")


def test_clean_worktree_is_removed_after_reported_check(lane):
    root, worktree = lane

    result = _run(worktree)

    assert result.returncode == 0, result.stderr
    assert "tracked-dirty=0" in result.stdout
    assert "untracked=0" in result.stdout
    assert "ignored=0" in result.stdout
    assert "unmerged-commits=0" in result.stdout
    assert "removed" in result.stdout
    assert not worktree.exists()
    assert str(worktree.resolve()) not in _git(root, "worktree", "list", "--porcelain")


def test_real_lane_scratch_is_removed_without_force(lane):
    """#762: the happy path must actually COMPLETE for a real lane.

    Every lane holds an untracked ``BRIEF.md`` (the coordinator writes it and
    never tracks it) and an ignored ``__pycache__/``. ``git worktree remove``
    refuses on ANY untracked file, so a tool that passes ``--force`` to git only
    when its own ``--force`` is set cannot remove a lane whose gate just PASSED.
    The existing suite proved the gate's verdict but never the outcome (#671 in
    the suite itself): this test asserts the directory is GONE and the worktree
    is deregistered — the discriminating evidence is the worktree's absence, not
    a changed exit code.
    """
    root, worktree = lane
    (worktree / "BRIEF.md").write_text("lane-local brief\n", encoding="utf-8")
    cache = worktree / "__pycache__"
    cache.mkdir()
    (cache / "tool.pyc").write_bytes(b"cache")

    result = _run(worktree)

    assert result.returncode == 0, result.stderr
    assert "tracked-dirty=0" in result.stdout
    assert "untracked=1" in result.stdout
    assert "ignored=1" in result.stdout
    assert "unmerged-commits=0" in result.stdout
    assert "removed" in result.stdout
    # The discriminating evidence: the gate passed AND the removal completed.
    assert not worktree.exists()
    assert str(worktree.resolve()) not in _git(root, "worktree", "list", "--porcelain")


def test_just_recipe_routes_lane_reap_through_the_checked_tool():
    result = subprocess.run(
        ["just", "--dry-run", "reap-lane", "--check", "/tmp/lane"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "python3 dev/reap.py --check /tmp/lane" in result.stderr
