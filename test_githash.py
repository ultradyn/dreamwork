"""bin/ud-dw-githash — the version contract, exercised for real.

The script's output IS the contract (the CI release replaces the whole file
with one that prints a constant, so the shape is all a consumer may rely on):

    <sha12>          clean checkout
    <sha12> +<N>     dirty checkout, N = tracked changes + untracked files
    <sha12> ?        repo found but dirtiness could not be determined
    unknown          no repo / no git / no HEAD

Always exit 0 — a skill that will not load because it cannot tell its own
version is worse than one that says "unknown".

Every test copies the script into a scratch repo because the script reports
the repo *it lives in*, not the caller's cwd — the caller is a dreamwork
target somewhere else entirely.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "bin" / "ud-dw-githash"

SHA_RE = re.compile(r"^[0-9a-f]{12}$")


def run(script: Path, cwd: Path | None = None):
    return subprocess.run(
        [str(script)],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        timeout=30,
    )


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(repo),
         "-c", "user.email=t@t", "-c", "user.name=t", *args],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def make_repo(path: Path) -> Path:
    """A committed scratch repo with the real script inside it."""
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q")
    dest = path / "bin" / "ud-dw-githash"
    dest.parent.mkdir(exist_ok=True)
    shutil.copy2(SCRIPT, dest)
    git(path, "add", "-A")
    git(path, "commit", "-qm", "seed")
    return dest


class TestGithash:
    def test_the_script_exists_and_is_executable(self):
        assert SCRIPT.exists(), "bin/ud-dw-githash is missing"
        assert SCRIPT.stat().st_mode & 0o111, "bin/ud-dw-githash is not executable"

    def test_clean_repo_prints_exactly_the_short_sha(self, tmp_path):
        script = make_repo(tmp_path / "repo")
        r = run(script)
        assert r.returncode == 0
        out = r.stdout.strip()
        assert SHA_RE.match(out), f"clean output not a bare sha12: {out!r}"
        assert out == git(tmp_path / "repo", "rev-parse", "--short=12", "HEAD")

    def test_dirty_repo_counts_both_modified_and_untracked(self, tmp_path):
        repo = tmp_path / "repo"
        script = make_repo(repo)
        (repo / "tracked.txt").write_text("v1")
        git(repo, "add", "tracked.txt")
        git(repo, "commit", "-qm", "add tracked")
        (repo / "tracked.txt").write_text("v2")      # modified
        (repo / "loose.txt").write_text("new")       # untracked
        r = run(script)
        assert r.returncode == 0
        sha, _, dirt = r.stdout.strip().partition(" ")
        assert SHA_RE.match(sha)
        assert dirt == "+2", f"expected '+2', got {dirt!r}"

    def test_outside_any_repo_says_unknown_and_still_exits_zero(self, tmp_path):
        loose = tmp_path / "nowhere" / "ud-dw-githash"
        loose.parent.mkdir(parents=True)
        shutil.copy2(SCRIPT, loose)
        r = run(loose)
        assert r.returncode == 0, "unknown-version must never be a failure"
        assert r.stdout.strip() == "unknown"

    def test_called_through_a_symlink_it_reports_its_real_home(self, tmp_path):
        # Load-bearing: the skill is installed by symlinking into
        # ~/.claude/skills — a script that resolves the symlink's location
        # instead of its own would report the wrong repo (or none).
        script = make_repo(tmp_path / "repo")
        link = tmp_path / "elsewhere" / "ud-dw-githash"
        link.parent.mkdir()
        link.symlink_to(script)
        r = run(link, cwd=tmp_path / "elsewhere")
        assert r.returncode == 0
        assert SHA_RE.match(r.stdout.strip().split()[0])
        assert r.stdout.strip() == git(tmp_path / "repo", "rev-parse", "--short=12", "HEAD")

    def test_callers_cwd_is_irrelevant(self, tmp_path):
        # A dreamwork target invokes this from its own tree; the answer is
        # about the skill's tree.
        script = make_repo(tmp_path / "repo")
        other = tmp_path / "someone-elses-project"
        other.mkdir()
        git(other, "init", "-q")
        r = run(script, cwd=other)
        assert r.stdout.strip() == git(tmp_path / "repo", "rev-parse", "--short=12", "HEAD")

    def test_single_line_output(self, tmp_path):
        script = make_repo(tmp_path / "repo")
        r = run(script)
        assert r.stdout.endswith("\n")
        assert r.stdout.count("\n") == 1

    def test_repo_with_no_commits_is_unknown_not_a_crash(self, tmp_path):
        repo = tmp_path / "empty"
        repo.mkdir()
        git(repo, "init", "-q")
        dest = repo / "ud-dw-githash"
        shutil.copy2(SCRIPT, dest)
        r = run(dest)
        assert r.returncode == 0
        assert r.stdout.strip() == "unknown"
