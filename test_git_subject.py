import os
import subprocess
from pathlib import Path

import pytest

from dev import git_subject


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        text=True,
        capture_output=True,
        check=True,
    )


@pytest.fixture
def worktrees(tmp_path):
    main = tmp_path / "main"
    lane = tmp_path / "carried-cwd"
    _run(tmp_path, "init", "-b", "master", str(main))
    (main / "tracked.txt").write_text("fixture\n")
    _run(main, "add", "tracked.txt")
    _run(
        main, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-m", "fixture",
    )
    _run(main, "worktree", "add", "-b", "lane", str(lane))
    return main, lane


def test_carried_cwd_refuses_the_wrong_worktree(worktrees):
    main, lane = worktrees

    result = git_subject.inspect_subject(command_cwd=lane, intended_root=main)

    assert result.state is git_subject.SubjectState.DIFFERENT, (
        "subject mismatch escaped: a carried lane cwd must differ from the explicitly "
        f"intended main checkout; {result.describe()}"
    )
    assert result.actual_root == lane
    assert result.intended_root == main


def test_matching_root_and_branch_are_accepted(worktrees):
    main, _ = worktrees

    result = git_subject.inspect_subject(
        command_cwd=main, intended_root=Path(f"{main}{os.sep}"), intended_branch="master")

    assert result.state is git_subject.SubjectState.MATCH, result.describe()


def test_branch_mismatch_is_distinct_from_an_unreadable_subject(worktrees):
    main, _ = worktrees

    result = git_subject.inspect_subject(
        command_cwd=main, intended_root=main, intended_branch="lane")

    assert result.state is git_subject.SubjectState.DIFFERENT
    assert result.reason == "Git resolved a different branch"


def test_directory_outside_git_is_not_a_worktree(tmp_path):
    result = git_subject.inspect_subject(command_cwd=tmp_path, intended_branch="master")

    assert result.state is git_subject.SubjectState.NOT_WORK_TREE


def test_git_failure_is_undeterminable_not_a_match(worktrees, monkeypatch):
    main, _ = worktrees
    real_git = git_subject._git

    def failing_show_toplevel(cwd, args, *, git):
        if args == ("rev-parse", "--show-toplevel"):
            return subprocess.CompletedProcess([], 74, "", "fixture read failure")
        return real_git(cwd, args, git=git)

    monkeypatch.setattr(git_subject, "_git", failing_show_toplevel)
    result = git_subject.inspect_subject(command_cwd=main, intended_root=main)

    assert result.state is git_subject.SubjectState.UNDETERMINABLE
    assert "exit 74" in result.reason


def test_core_worktree_residue_refuses_even_when_paths_match(worktrees):
    main, _ = worktrees
    _run(main, "config", "--local", "core.worktree", str(main))

    result = git_subject.inspect_subject(command_cwd=main, intended_root=main)

    assert result.state is git_subject.SubjectState.DIFFERENT
    assert "core.worktree residue" in result.reason


def test_symlink_alias_matches_without_rewriting_the_intended_name(worktrees, tmp_path):
    main, _ = worktrees
    alias = tmp_path / "stable-repo-name"
    alias.symlink_to(main, target_is_directory=True)

    result = git_subject.inspect_subject(command_cwd=alias, intended_root=alias)

    assert result.state is git_subject.SubjectState.MATCH, result.describe()
    assert result.intended_root == alias


def test_relative_subjects_are_rejected_before_git_runs(worktrees):
    main, _ = worktrees

    with pytest.raises(ValueError, match="cannot inherit ambient cwd"):
        git_subject.inspect_subject(command_cwd=main, intended_root="main")
