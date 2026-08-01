import os
from pathlib import Path
import stat
import subprocess
import time

import pytest

from dev import git_status


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "--no-optional-locks", "-C", str(repo),
         "-c", "user.name=test", "-c", "user.email=test@example.invalid", *args],
        check=True, capture_output=True, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "tracked").write_text("one\n", encoding="utf-8")
    _git(root, "add", "tracked")
    _git(root, "commit", "-qm", "base")
    return root


def _locking_git(tmp_path: Path, *, always: bool = False) -> Path:
    script = tmp_path / "locking-git"
    script.write_text(
        "#!/bin/sh\n"
        "repo=\n"
        "protected=0\n"
        "while [ $# -gt 0 ]; do\n"
        "  [ \"$1\" = --no-optional-locks ] && protected=1\n"
        "  if [ \"$1\" = -C ]; then shift; repo=$1; fi\n"
        "  shift\n"
        "done\n"
        f"if [ $protected -eq 0 ] || [ {int(always)} -eq 1 ]; then\n"
        "  : > \"$repo/.git/index.lock\"\n"
        "  sleep 0.003\n"
        "  rm \"$repo/.git/index.lock\"\n"
        "fi\n"
        "sleep 0.03\n"
        "printf '## main\\n'\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def test_healthy_poll_is_quiet_and_uses_both_lock_defences(repo, monkeypatch):
    monkeypatch.setenv("GIT_OPTIONAL_LOCKS", "1")
    seen = []
    real_run = subprocess.run

    def spy(argv, *args, **kwargs):
        seen.append((argv, kwargs.get("env", {})))
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(git_status.subprocess, "run", spy)
    status_result = git_status.poll(repo)
    assert status_result.dirty is False
    assert os.environ["GIT_OPTIONAL_LOCKS"] == "0"
    assert seen, "the poll never ran, so its lock discipline was not examined"
    assert all("--no-optional-locks" in argv for argv, _ in seen)
    assert all(env.get("GIT_OPTIONAL_LOCKS") == "0" for _, env in seen)


def test_dropping_the_explicit_flag_reports_that_index_lock_appeared(repo, tmp_path, monkeypatch):
    fake_git = _locking_git(tmp_path)
    monkeypatch.setattr(
        git_status, "_status_argv",
        lambda git, root: [git, "-C", str(root), "status", "--porcelain=v1"],
    )
    with pytest.raises(git_status.IndexLockAppeared, match="index.lock appeared during git status poll"):
        git_status.poll(repo, git=str(fake_git))


def test_explicit_flag_keeps_the_locking_positive_control_quiet(repo, tmp_path):
    fake_git = _locking_git(tmp_path)
    result = git_status.poll(repo, git=str(fake_git))
    assert result.lines == ("## main",)


def test_event_guard_catches_a_three_millisecond_lock_that_sampling_misses(repo, tmp_path):
    fake_git = _locking_git(tmp_path, always=True)

    # Positive false-green: a 10ms sampling watcher misses this real 3ms lock.
    proc = subprocess.Popen([str(fake_git), "-C", str(repo), "status"])
    time.sleep(0.010)
    assert not (repo / ".git/index.lock").exists()
    proc.wait(timeout=1)

    # The production guard consumes kernel creation events, retained after unlink.
    with pytest.raises(git_status.IndexLockAppeared, match="index.lock appeared during git status poll"):
        git_status.poll(repo, git=str(fake_git))


def test_cadences_are_separate_and_ci_requires_a_nondraft_pr():
    cadence = git_status.PollCadence()
    ages = {"status": 10, "pr": 60, "ci": 120}
    assert cadence.due(ages, pr_exists=False, pr_draft=False) == ("status", "pr")
    assert cadence.due(ages, pr_exists=True, pr_draft=True) == ("status", "pr")
    assert cadence.due(ages, pr_exists=True, pr_draft=False) == ("status", "pr", "ci")
    assert cadence.status_seconds < cadence.pr_seconds < cadence.ci_seconds
