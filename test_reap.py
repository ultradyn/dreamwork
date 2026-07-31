#!/usr/bin/env python3
"""Red-first integration tests for the checked lane-worktree reaper (#686)."""

import subprocess
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent
CLI = REPO / "dev" / "reap.py"


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
    (root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
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
    assert "untracked-ignored=0" in result.stderr
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
    assert "untracked-ignored=2" in result.stdout
    assert "unmerged-commits=0" in result.stdout


def test_non_worktree_is_unknown_not_clean(tmp_path):
    ordinary = tmp_path / "ordinary"
    ordinary.mkdir()

    result = _run("--check", ordinary)

    assert result.returncode == 2
    assert f"path={ordinary.resolve()}" in result.stderr
    assert "tracked-dirty=unknown" in result.stderr
    assert "untracked-ignored=unknown" in result.stderr
    assert "not a registered linked worktree" in result.stderr


def test_clean_branch_with_unmerged_commit_refuses(lane):
    _, worktree = lane
    (worktree / "landed.txt").write_text("committed lane output\n", encoding="utf-8")
    _git(worktree, "add", "landed.txt")
    _git(worktree, "commit", "-qm", "feat(#686): lane output")
    sha = _git(worktree, "rev-parse", "--short=12", "HEAD")

    result = _run("--check", worktree)

    assert result.returncode == 1
    assert "tracked-dirty=0" in result.stderr
    assert "untracked-ignored=0" in result.stderr
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
    assert "untracked-ignored=0" in result.stdout
    assert "unmerged-commits=0" in result.stdout
    assert "removed" in result.stdout
    assert not worktree.exists()
    assert str(worktree.resolve()) not in _git(root, "worktree", "list", "--porcelain")
