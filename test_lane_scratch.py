#!/usr/bin/env python3
"""Red-first tests for dev/lane_scratch.py — the lane-private snapshot dir (#652).

The defect under test is not a crash, it is a SILENT one: two concurrent lanes
share the harness scratchpad, both snapshot to the natural generic filename, and
one lane's `cp` restore writes the other lane's bytes while BOTH lanes' `cmp`
checks pass. `test_the_hazard_is_real` reproduces exactly that, so the fix is
measured against a demonstrated failure rather than an asserted one.

Restore discipline used while writing these (#349): snapshots were taken to
`~/.cache/ud-dreamwork/lane-scratch/ud-dreamwork/lane-652scratch/snap/`, restored
by `cp`, verified with `cmp` — never `git checkout`, and never a generic name in
a shared directory, which is the hazard this file exists to close.
"""
import importlib.machinery
import importlib.util
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent
CLI_PATH = REPO / "dev" / "lane_scratch.py"


def _load():
    """Load dev/lane_scratch.py as a module (it lives in dev/, not root)."""
    loader = importlib.machinery.SourceFileLoader("lane_scratch", str(CLI_PATH))
    spec = importlib.util.spec_from_loader("lane_scratch", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


ls = _load()


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args],
        stderr=subprocess.DEVNULL, text=True,
    ).strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A real git repo with one commit — worktrees need real history."""
    root = tmp_path / "origin"
    root.mkdir()
    _git(root, "init", "-q", "-b", "master", ".")
    (root / "a.txt").write_text("x\n")
    _git(root, "add", "a.txt")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    return root


# ── the hazard itself ──────────────────────────────────────────────────

class TestTheHazardIsReal:
    """A shared snapshot directory corrupts a restore with both `cmp` green."""

    @staticmethod
    def _two_lanes(tmp_path: Path, *, shared: bool) -> dict:
        a_file = tmp_path / "wtA" / "router.js"
        b_file = tmp_path / "wtB" / "router.js"
        a_file.parent.mkdir(parents=True)
        b_file.parent.mkdir(parents=True)
        a_file.write_text("LANE-A ORIGINAL\n" + "a" * 200)
        b_file.write_text("LANE-B ORIGINAL\n" + "b" * 300)
        a_want, b_want = a_file.read_text(), b_file.read_text()

        if shared:
            a_dir = b_dir = tmp_path / "scratchpad" / "snap"
            a_dir.mkdir(parents=True, exist_ok=True)
        else:
            a_dir = tmp_path / "lane-scratch" / "lane-A" / "snap"
            b_dir = tmp_path / "lane-scratch" / "lane-B" / "snap"
            a_dir.mkdir(parents=True)
            b_dir.mkdir(parents=True)

        # Both lanes pick the same natural filename. Nothing tells them not to.
        a_snap, b_snap = a_dir / "router.js.orig", b_dir / "router.js.orig"
        a_snap.write_bytes(a_file.read_bytes())      # A snapshots
        b_snap.write_bytes(b_file.read_bytes())      # B snapshots (clobbers, if shared)
        a_file.write_text("A SABOTAGE")              # A injects RED
        b_file.write_text("B SABOTAGE")              # B injects RED
        a_file.write_bytes(a_snap.read_bytes())      # A restores by cp
        b_file.write_bytes(b_snap.read_bytes())      # B restores by cp
        return {
            "a_cmp": a_file.read_bytes() == a_snap.read_bytes(),
            "b_cmp": b_file.read_bytes() == b_snap.read_bytes(),
            "a_ok": a_file.read_text() == a_want,
            "b_ok": b_file.read_text() == b_want,
        }

    def test_a_shared_dir_corrupts_while_both_cmp_pass(self, tmp_path):
        """The exact #652 failure: green checks over a wrong baseline."""
        r = self._two_lanes(tmp_path, shared=True)
        assert r["a_cmp"] and r["b_cmp"], "both lanes' cmp must pass — that is the danger"
        assert not r["a_ok"], "lane A's file should hold lane B's bytes"

    def test_derived_dirs_do_not_corrupt(self, tmp_path):
        """Same generic filename, different derived dirs, no corruption."""
        r = self._two_lanes(tmp_path, shared=False)
        assert r["a_cmp"] and r["b_cmp"]
        assert r["a_ok"] and r["b_ok"]


# ── the derivation ─────────────────────────────────────────────────────

class TestLaneKeyIsDerivedAndUnique:
    """The lane does not choose the key, so two lanes cannot choose alike."""

    def test_branch_is_the_key(self, repo):
        assert ls.lane_key(repo) == "master"

    def test_two_worktrees_get_different_keys(self, repo, tmp_path):
        """git refuses one branch in two worktrees, so branch keys cannot collide."""
        for name in ("lane-alpha", "lane-beta"):
            _git(repo, "worktree", "add", "-q", str(tmp_path / name), "-b", name)
        a = ls.lane_key(tmp_path / "lane-alpha")
        b = ls.lane_key(tmp_path / "lane-beta")
        assert a == "lane-alpha" and b == "lane-beta"
        assert a != b

    def test_git_itself_refuses_a_duplicate_branch(self, repo, tmp_path):
        """The guarantee the branch key rests on, asserted rather than assumed."""
        _git(repo, "worktree", "add", "-q", str(tmp_path / "one"), "-b", "dup")
        proc = subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", str(tmp_path / "two"), "dup"],
            capture_output=True, text=True,
        )
        assert proc.returncode != 0
        assert "already used by worktree" in (proc.stderr + proc.stdout)

    def test_detached_worktrees_do_not_collide(self, repo, tmp_path):
        """Every detached worktree reports the branch `HEAD` — the hole in a naive key.

        Two were live in this repo when #652 was written, so this is measured
        behaviour rather than a hypothetical.
        """
        for name in ("d1", "d2"):
            _git(repo, "worktree", "add", "-q", "--detach", str(tmp_path / name))
        assert _git(tmp_path / "d1", "rev-parse", "--abbrev-ref", "HEAD") == "HEAD"
        k1 = ls.lane_key(tmp_path / "d1")
        k2 = ls.lane_key(tmp_path / "d2")
        assert k1.startswith("detached-") and k2.startswith("detached-")
        assert k1 != k2, "detached lanes must not share a snapshot directory"

    def test_a_branch_named_like_the_fallback_still_separates(self, repo, tmp_path):
        """A branch literally called `detached-…` must not alias a detached lane."""
        _git(repo, "worktree", "add", "-q", str(tmp_path / "odd"), "-b", "detached-abc")
        _git(repo, "worktree", "add", "-q", "--detach", str(tmp_path / "det"))
        assert ls.lane_key(tmp_path / "odd") != ls.lane_key(tmp_path / "det")

    def test_a_slash_in_a_branch_stays_one_component(self, repo, tmp_path):
        """`lane/652` must not become a nested directory or escape the root."""
        _git(repo, "worktree", "add", "-q", str(tmp_path / "sl"), "-b", "feat/652")
        key = ls.lane_key(tmp_path / "sl")
        assert "/" not in key and ".." not in key

    def test_worktrees_of_one_repo_share_a_repo_key(self, repo, tmp_path):
        """A lane's evidence files under the repo it belongs to, not a sibling tree."""
        _git(repo, "worktree", "add", "-q", str(tmp_path / "lane-x"), "-b", "lane-x")
        assert ls.repo_key(tmp_path / "lane-x") == ls.repo_key(repo)


class TestScratchDir:
    def test_subdir_is_created_and_nested_under_the_lane(self, repo):
        d = ls.lane_scratch_dir(repo, sub="snap")
        assert d.is_dir()
        assert d.parent == ls.lane_scratch_dir(repo, create=False)

    def test_no_create_does_not_create(self, repo, monkeypatch, tmp_path):
        monkeypatch.setattr(ls, "SCRATCH_ROOT", tmp_path / "unmade")
        d = ls.lane_scratch_dir(repo, create=False)
        assert not d.exists()

    def test_a_traversing_subdir_cannot_escape_the_root(self, repo, monkeypatch, tmp_path):
        monkeypatch.setattr(ls, "SCRATCH_ROOT", tmp_path / "root")
        d = ls.lane_scratch_dir(repo, sub="../../etc")
        assert (tmp_path / "root") in d.parents

    def test_root_is_not_tmpfs(self):
        """The substrate half of #634: tmpfs does not update mtime for mmap'd writes.

        A lane measuring mtime/mmap/locking in the harness scratchpad gets a
        clean, confident, WRONG answer. This root must not be on tmpfs.
        """
        root = ls.SCRATCH_ROOT
        probe = root if root.exists() else root.parent
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        fstype = subprocess.check_output(
            ["stat", "-f", "-c", "%T", str(probe)], text=True).strip()
        assert fstype != "tmpfs", f"{probe} is tmpfs; snapshots and probes need real disk"

    def test_outside_a_repo_still_yields_a_usable_dir(self, tmp_path, monkeypatch):
        """Degrade to a private directory rather than raising."""
        monkeypatch.setattr(ls, "SCRATCH_ROOT", tmp_path / "root")
        d = ls.lane_scratch_dir(tmp_path / "not-a-repo", create=False)
        assert (tmp_path / "root") in d.parents


class TestCli:
    def test_prints_the_path_and_creates_it(self, repo):
        out = subprocess.check_output(
            ["python3", str(CLI_PATH), "snap", "--cwd", str(repo)], text=True).strip()
        assert Path(out).is_dir()
        assert out.endswith("/master/snap")

    def test_no_create_flag(self, repo, tmp_path):
        out = subprocess.check_output(
            ["python3", str(CLI_PATH), "--no-create", "--cwd", str(repo),
             str(tmp_path.name)], text=True).strip()
        assert out


class TestThisRepoIsSeparated:
    """Dogfood: every live worktree of this repo derives a distinct directory."""

    def test_live_worktrees_do_not_collide(self):
        out = _git(REPO, "worktree", "list", "--porcelain")
        paths = [Path(line.split(" ", 1)[1]) for line in out.splitlines()
                 if line.startswith("worktree ")]
        live = [p for p in paths if p.is_dir()]
        assert len(live) >= 2, "need at least two live worktrees for this to mean anything"
        keys = [str(ls.lane_scratch_dir(p, create=False)) for p in live]
        assert len(set(keys)) == len(keys), f"colliding lane dirs: {keys}"
