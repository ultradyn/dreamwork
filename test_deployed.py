"""Tests for deployed.py.

The load-bearing one is `test_a_broken_git_call_is_not_a_no_match`. This
module exists because a shell loop compared nothing and reported "no match"
three times running; a checker that cannot tell "I compared and they differ"
from "I could not compare" is the bug, not a rough edge.
"""

import subprocess
from pathlib import Path

import pytest

import deployed


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "proj"
    r.mkdir()
    git(r, "init", "-q")
    git(r, "config", "user.email", "t@t")
    git(r, "config", "user.name", "t")
    (r / "watch.py").write_text("print('v1')\n")
    git(r, "add", "watch.py")
    git(r, "commit", "-qm", "v1")
    return r


def commit(repo, text, msg):
    (repo / "watch.py").write_text(text)
    git(repo, "add", "watch.py")
    git(repo, "commit", "-qm", msg)


@pytest.fixture
def deploy_dir(tmp_path, monkeypatch):
    d = tmp_path / "deployed"
    d.mkdir()
    monkeypatch.setattr(deployed, "DEPLOY_DIR", d)
    return d


def snap(deploy_dir, target: Path, text: str):
    p = deploy_dir / f"{target.name}-watch.py"
    p.write_text(text)
    return p


class TestTheBugItWasBuiltFor:
    def test_a_broken_git_call_is_not_a_no_match(self, repo, deploy_dir, monkeypatch):
        # The shell version silenced git's fatal and reported "no match".
        # Here git raises, and the answer must be ERROR — never UNTRACKED,
        # which is the state that means "I read every revision and none
        # matched". Confusing the two is how a working deploy got reported
        # as running code from no commit.
        snap(deploy_dir, repo, "print('v1')\n")

        real = deployed.git

        def broken(r, *args, **kw):
            if args and args[0] == "log":
                raise subprocess.CalledProcessError(128, "git")
            return real(r, *args, **kw)

        monkeypatch.setattr(deployed, "git", broken)
        out = deployed.report(repo, repo)
        assert out["state"] == deployed.ERROR
        assert out["state"] != deployed.UNTRACKED

    def test_untracked_is_reached_only_after_really_scanning(self, repo, deploy_dir):
        # The complement: a snapshot that genuinely matches nothing. This
        # must still be reachable, or the fix above would have made the
        # real case unreportable.
        snap(deploy_dir, repo, "print('never committed')\n")
        out = deployed.report(repo, repo)
        assert out["state"] == deployed.UNTRACKED
        assert "uncommitted tree" in out["note"]


class TestStates:
    def test_serving_head_is_current(self, repo, deploy_dir):
        snap(deploy_dir, repo, "print('v1')\n")
        out = deployed.report(repo, repo)
        assert out["state"] == deployed.CURRENT
        assert out["missing"] == []

    def test_two_commits_behind_names_both(self, repo, deploy_dir):
        snap(deploy_dir, repo, "print('v1')\n")
        commit(repo, "print('v2')\n", "the focus fix")
        commit(repo, "print('v3')\n", "the cycle direction")
        out = deployed.report(repo, repo)
        assert out["state"] == deployed.BEHIND
        assert [s for _, s in out["missing"]] == ["the cycle direction", "the focus fix"]

    def test_an_unrelated_commit_does_not_count_as_behind(self, repo, deploy_dir):
        # Only revisions touching the watched path count. A day of README
        # commits must not read as a stale dashboard.
        snap(deploy_dir, repo, "print('v1')\n")
        (repo / "README.md").write_text("hi\n")
        git(repo, "add", "README.md")
        git(repo, "commit", "-qm", "docs")
        assert deployed.report(repo, repo)["state"] == deployed.CURRENT

    def test_no_snapshot_is_never_deployed_not_an_error(self, repo, deploy_dir):
        out = deployed.report(repo, repo)
        assert out["state"] == deployed.NEVER
        assert "never been deployed" in out["note"]

    def test_a_target_without_the_file_in_history_is_no_repo(self, tmp_path, deploy_dir):
        bare = tmp_path / "plain"
        bare.mkdir()
        git(bare, "init", "-q")
        git(bare, "config", "user.email", "t@t")
        git(bare, "config", "user.name", "t")
        (bare / "other.txt").write_text("x")
        git(bare, "add", "other.txt")
        git(bare, "commit", "-qm", "no watch.py here")
        snap(deploy_dir, bare, "print('v1')\n")
        assert deployed.report(bare, bare)["state"] == deployed.NO_REPO


class TestReporting:
    def test_behind_renders_every_missing_commit(self, repo, deploy_dir):
        snap(deploy_dir, repo, "print('v1')\n")
        commit(repo, "print('v2')\n", "the focus fix")
        text = deployed.render(deployed.report(repo, repo))
        assert "BEHIND by 1 watch.py commit" in text and "the focus fix" in text

    def test_one_commit_behind_is_not_pluralised(self, repo, deploy_dir):
        snap(deploy_dir, repo, "print('v1')\n")
        commit(repo, "print('v2')\n", "one")
        assert "1 watch.py commit " in deployed.render(deployed.report(repo, repo))

    def test_never_deployed_exits_zero(self, repo, deploy_dir, capsys):
        # A target nobody deployed must not fail a gate.
        assert deployed.main(["--target", str(repo), "--repo", str(repo)]) == 0

    def test_behind_exits_nonzero(self, repo, deploy_dir):
        snap(deploy_dir, repo, "print('v1')\n")
        commit(repo, "print('v2')\n", "later")
        assert deployed.main(["--target", str(repo), "--repo", str(repo)]) == 1


class TestTheLockRule:
    def test_every_git_call_disables_optional_locks(self, repo, deploy_dir, monkeypatch):
        # His CLAUDE.md carries an active mitigation for .git/index.lock
        # churn. A dashboard poller is exactly the kind of thing that would
        # reintroduce it, so the flag is asserted rather than remembered.
        snap(deploy_dir, repo, "print('v1')\n")
        commit(repo, "print('v2')\n", "later")

        # Spy installed AFTER the fixture's own commits, or it catches the
        # test harness's `git add` and fails on a call this module never
        # made — which is a test grading the wrong process.
        seen = []
        real = subprocess.run

        def spy(cmd, *a, **kw):
            seen.append(cmd)
            return real(cmd, *a, **kw)

        monkeypatch.setattr(subprocess, "run", spy)
        deployed.report(repo, repo)
        assert seen, "no git calls were made — the assertion would be vacuous"
        for cmd in seen:
            assert "--no-optional-locks" in cmd, cmd
