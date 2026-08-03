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
import hashlib
import os
import signal
import subprocess
import sys
import time
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
    def test_two_launches_in_one_worktree_get_distinct_dirs(
            self, repo, monkeypatch, tmp_path):
        """#870: worktree identity is grouping, not the privacy boundary."""
        monkeypatch.setattr(ls, "SCRATCH_ROOT", tmp_path / "scratch")
        monkeypatch.setenv(ls.IDENTITY_ENV, "a" * 32)
        a = ls.lane_scratch_dir(repo, sub="snap", create=False)
        monkeypatch.setenv(ls.IDENTITY_ENV, "b" * 32)
        b = ls.lane_scratch_dir(repo, sub="snap", create=False)

        assert ls.lane_identity(env={ls.IDENTITY_ENV: "a" * 32}) != \
            ls.lane_identity(env={ls.IDENTITY_ENV: "b" * 32})
        assert a != b, f"distinct launches share scratch: {a}"
        independent_digest = hashlib.sha1(("a" * 32).encode()).hexdigest()[:12]
        expected_a_segment = f"lane-{'a' * 32}-{independent_digest}"
        assert expected_a_segment in a.parts  # independently derived layout

    def test_absent_launch_identity_preserves_the_legacy_path(
            self, repo, monkeypatch):
        """A live pre-#870 lane must keep finding its existing snapshots."""
        monkeypatch.delenv(ls.IDENTITY_ENV, raising=False)
        legacy = ls.SCRATCH_ROOT / ls.repo_key(repo) / ls.lane_key(repo) / "snap"
        assert ls.lane_scratch_dir(repo, sub="snap", create=False) == legacy

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
        path = Path(out)
        assert path.is_dir()
        assert path.is_relative_to(ls.SCRATCH_ROOT), (
            f"snapshot path escaped SCRATCH_ROOT: {path}"
        )
        assert path.name == "snap"

    def test_no_create_flag(self, repo, tmp_path):
        out = subprocess.check_output(
            ["python3", str(CLI_PATH), "--no-create", "--cwd", str(repo),
             "--dir", str(tmp_path.name)], text=True).strip()
        assert out

    def test_measure_names_the_one_filesystem_measurement_location(self, repo):
        out = subprocess.check_output(
            ["python3", str(CLI_PATH), "measure", "--cwd", str(repo)],
            text=True,
        ).strip()
        path = Path(out)
        assert path.is_dir()
        assert path.is_relative_to(ls.SCRATCH_ROOT), (
            f"measurement path escaped SCRATCH_ROOT: {path}"
        )
        assert path.name == "measure"


class TestMtimePositiveControl:
    """A negative is believable only after the substrate shows the mode."""

    @staticmethod
    def _run(path: Path, *command: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["python3", str(CLI_PATH), "require-mtime-change", str(path),
             "--", *command],
            capture_output=True,
            text=True,
        )

    def test_healthy_control_is_silent(self, tmp_path):
        probe = tmp_path / "probe"
        probe.write_bytes(b"x")
        old = time.time_ns() - 60_000_000_000
        os.utime(probe, ns=(old, old))
        result = self._run(
            probe,
            sys.executable,
            "-c",
            "import os,sys; os.utime(sys.argv[1], None)",
            str(probe),
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout == ""
        assert result.stderr == ""

    def test_control_that_exhibits_nothing_is_unsupported_not_ok(self, tmp_path):
        probe = tmp_path / "probe"
        probe.write_bytes(b"x")
        result = self._run(probe, sys.executable, "-c", "pass")
        assert result.returncode == 1
        assert result.stdout == ""
        assert "UNSUPPORTED" in result.stderr
        assert "positive control ran but mtime did not advance" in result.stderr
        assert "UNDETERMINED" not in result.stderr

    def test_missing_subject_is_undetermined_not_ok(self, tmp_path):
        result = self._run(tmp_path / "missing", sys.executable, "-c", "pass")
        assert result.returncode == 2
        assert result.stdout == ""
        assert "UNDETERMINED" in result.stderr
        assert "before the positive control" in result.stderr
        assert "UNSUPPORTED" not in result.stderr

    def test_failed_control_command_is_undetermined_not_unsupported(self, tmp_path):
        probe = tmp_path / "probe"
        probe.write_bytes(b"x")
        result = self._run(probe, sys.executable, "-c", "raise SystemExit(7)")
        assert result.returncode == 2
        assert result.stdout == ""
        assert "UNDETERMINED" in result.stderr
        assert "exited 7" in result.stderr
        assert "UNSUPPORTED" not in result.stderr


class TestThisRepoIsSeparated:
    """Dogfood: every live worktree of this repo derives a distinct directory."""

    def test_live_worktrees_do_not_collide(self):
        out = _git(REPO, "worktree", "list", "--porcelain")
        paths = [Path(line.split(" ", 1)[1]) for line in out.splitlines()
                 if line.startswith("worktree ")]
        live = [p for p in paths if p.is_dir()]
        # The precondition is correct but the test cannot control it: an empty
        # fleet (only the main checkout) is the STEADY STATE between dispatches,
        # so `assert len(live) >= 2` read a "could not run" as "found a defect"
        # and the suite was only ever green while lanes happened to be running.
        # Skip — do NOT lower to `>= 1`: a one-worktree run genuinely cannot
        # detect a collision, and asserting over it would be the vacuous pass
        # #671 forbids (#471: a check that gated nothing must not read as a
        # verdict; #136: "did not run" and "found a defect" must not render
        # identically).
        if len(live) < 2:
            pytest.skip("need at least two live worktrees to detect a "
                        "collision; only the main checkout is live between "
                        "dispatches (the fleet's steady state)")
        keys = [str(ls.lane_scratch_dir(p, create=False)) for p in live]
        assert len(set(keys)) == len(keys), f"colliding lane dirs: {keys}"


# ── #694: a reviewer shares the author's worktree but must not share scratch ──

class TestRoleKeying:
    """THE #694 defect: a reviewer runs in the author's own worktree, so both
    resolve to the SAME lane_key. Without a role segment, the reviewer's
    snapshots overwrite the author's evidence — the exact #652 corruption, one
    worktree over, and now structural because the Opus review is mandatory."""

    def test_author_and_reviewer_get_different_dirs(self, repo):
        """The core #694 fix: same worktree, different roles, different dirs."""
        a = ls.lane_scratch_dir(repo, role="author", sub="snap", create=False)
        r = ls.lane_scratch_dir(repo, role="reviewer", sub="snap", create=False)
        assert a != r, (
            f"author and reviewer resolve to the same dir ({a}) — the #694 "
            f"collision is not fixed")

    def test_the_separation_preserves_author_evidence(self, tmp_path):
        """Direction 1: a reviewer's snap cannot overwrite the author's.

        Reproduces what the Opus review lane over #674 reported it HIT: 'I
        overwrote one of the author snapshot files before realising.' With
        #694, both roles get separate dirs so the author's evidence survives."""
        root = tmp_path / "origin"
        root.mkdir()
        _git(root, "init", "-q", "-b", "master", ".")
        (root / "a.txt").write_text("x\n")
        _git(root, "add", "a.txt")
        _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")

        a_dir = ls.lane_scratch_dir(root, role="author", sub="snap")
        r_dir = ls.lane_scratch_dir(root, role="reviewer", sub="snap")
        # Both use the same natural filename — nothing tells them not to.
        (a_dir / "router.js.orig").write_bytes(b"AUTHOR EVIDENCE")
        (r_dir / "router.js.orig").write_bytes(b"REVIEWER SNAPSHOT")
        # The author's evidence survives because the dirs are separate
        assert (a_dir / "router.js.orig").read_bytes() == b"AUTHOR EVIDENCE"

    def test_author_maps_to_the_legacy_path_no_migration(self, repo):
        """AUTHOR must produce the pre-#694 path so live lanes don't move.

        This is the migration goal (#755): a change that makes a live lane's
        snapshots unfindable mid-flight is worse than the bug."""
        no_role = ls.lane_scratch_dir(repo, sub="snap", create=False)
        author = ls.lane_scratch_dir(repo, role="author", sub="snap", create=False)
        assert no_role == author, (
            "author role must map to the legacy path (no role segment); "
            f"got {author} vs legacy {no_role}")

    def test_lane_role_defaults_to_author(self, monkeypatch):
        """The default is author because every lane today IS an author lane.

        A default that moved four live lanes' snapshots would be worse than the
        bug. The default is also the honest boundary (#702)."""
        monkeypatch.delenv(ls.ROLE_ENV, raising=False)
        assert ls.lane_role() == ls.ROLE_AUTHOR

    def test_lane_role_reads_the_env_var(self, monkeypatch):
        monkeypatch.setenv(ls.ROLE_ENV, "reviewer")
        assert ls.lane_role() == ls.ROLE_REVIEWER

    def test_author_evidence_dir_is_the_author_dir(self, repo):
        """A reviewer can read the author's evidence via author_dir().

        The author's directory stays readable (#694 constraint): the goal is to
        remove the write collision, not to wall the reviewer off."""
        ev = ls.author_dir(repo, sub="snap", create=False)
        author = ls.lane_scratch_dir(repo, role="author", sub="snap",
                                     create=False)
        assert ev == author

    def test_cli_role_flag_separates(self, repo):
        a = subprocess.check_output(
            ["python3", str(CLI_PATH), "snap", "--role", "author",
             "--cwd", str(repo)], text=True).strip()
        r = subprocess.check_output(
            ["python3", str(CLI_PATH), "snap", "--role", "reviewer",
             "--cwd", str(repo)], text=True).strip()
        assert a != r
        assert a.endswith("/snap")
        assert "role-reviewer" in r

    def test_cli_env_var_separates(self, repo):
        env = dict(os.environ)
        a = subprocess.check_output(
            ["python3", str(CLI_PATH), "snap", "--cwd", str(repo)],
            text=True, env=env).strip()
        env[ls.ROLE_ENV] = "reviewer"
        r = subprocess.check_output(
            ["python3", str(CLI_PATH), "snap", "--cwd", str(repo)],
            text=True, env=env).strip()
        assert a != r

    def test_cli_author_evidence_flag(self, repo):
        """--author-evidence prints the author's dir from any role."""
        env = dict(os.environ)
        env[ls.ROLE_ENV] = "reviewer"
        out = subprocess.check_output(
            ["python3", str(CLI_PATH), "--author-evidence", "--cwd", str(repo)],
            text=True, env=env).strip()
        assert "role-reviewer" not in out


class TestRoleHonestBoundary:
    """Direction 2: the case where the fix LOOKS applied but is not.

    A reviewer whose dispatcher does not set DREAMWORK_LANE_ROLE defaults to
    author and gets the author's directory back — while the code is in place
    and the tests pass (#671). The tool cannot force the dispatcher to set it;
    it makes the default VISIBLE rather than silent (#702)."""

    def test_unset_role_is_author_not_silent(self, monkeypatch):
        """The default is author, not a guess — and it is named, not hidden."""
        monkeypatch.delenv(ls.ROLE_ENV, raising=False)
        role = ls.lane_role()
        assert role == "author", (
            "unset role must default to author, not a silent guess — this "
            "is the honest boundary (#702)")

    def test_a_reviewer_without_env_gets_author_dir_and_it_is_visible(
            self, repo, monkeypatch):
        """THE #694 direction-2 case: fix in place, tests pass, reviewer
        collides anyway because the env var is unset.

        This is constructible and real: the dispatcher must set the role for
        the separation to take effect. The tool makes it loud (the role is on
        the path) but cannot prevent it. Pinning the boundary rather than
        pretending it does not exist is #702's rule."""
        monkeypatch.delenv(ls.ROLE_ENV, raising=False)
        # Reviewer forgot to set the env var
        forgotten = ls.lane_scratch_dir(repo, sub="snap", create=False)
        author = ls.lane_scratch_dir(repo, role="author", sub="snap",
                                     create=False)
        # They collide — this is the honest boundary, not a bug in the fix
        assert forgotten == author, (
            "unset role defaults to author — the collision is the boundary "
            "the dispatcher must close, not one the tool can close alone")


# ── #934: lane_scratch defers to redproof for red-proof injections ─────

class TestDocstringDefersToRedproof:
    """#934: lane_scratch.py's usage block presents a manual cp/cmp snapshot
    procedure. That procedure names lane_scratch as the snapshot tool while the
    actual red-proof protocol (redproof.py, mandated by the boilerplate) uses a
    different ``redproof/`` root — so an agent following lane_scratch's
    procedure verbatim constructs the ``snap/`` path and a later ``cmp``
    against the ``redproof/`` snapshot fails falsely. The docstring must warn
    about the #934 root split so an agent reading lane_scratch.py sees the
    hazard rather than discovering it via a false cmp.

    HONEST LIMITATION (stated, per the brief's direction-2 note on doc-only
    fixes): this asserts the docstring CONTAINS the #934 warning — a necessary
    condition for followability, not proof that a fresh reader's cognition
    follows it. A docstring-content check cannot mechanically prove a reader
    reaches the right path; the behavioural proof of followability lives in
    test_redproof.py (begin states the root and the printed path holds the
    original). This check is a regression net: if the warning is removed, it
    fails. ``#934`` is the hazard's stable identity reference (absent from the
    original docstring, so this is a real discriminator, not a token that
    agrees with the tool regardless — #852)."""

    def test_docstring_warns_about_the_934_root_split(self):
        doc = ls.__doc__ or ""
        # DISCRIMINATOR: #934 is absent from the pre-fix docstring (which shows
        # `snap` in its usage block and names `redproof.py begin` at line 30 for
        # an unrelated reason, so those tokens do NOT discriminate — they agree
        # with the docstring regardless of the fix). #934 is unique to the added
        # warning. DERIVED FROM the hazard's identity reference.
        assert "#934" in doc, (
            "lane_scratch.py's docstring must warn about the #934 root split "
            "(snap/ vs redproof/) so an agent reading it does not assume the "
            "snap/ path is the red-proof snapshot root")


# ── #973: the `write` verb the frame promises but the tool lacked ──────

class TestWriteVerb:
    """#973: the frame (#878) names ``dev/lane_scratch.py`` as "the supported
    place" to persist red-proof evidence, but the tool only PRINTED a path — so
    every lane re-invented the write or skipped the evidence. This is the
    missing verb: ``write <name>`` reads stdin, lands under this lane's scratch
    dir, prints the absolute path.

    The CLI is exercised via subprocess (the production seam a lane invokes),
    not by calling ``_write_main`` directly: an import-call would not reach the
    argparse layer or the stdin path, and a check that patches out the
    production seam is structurally incapable of failing on it (the CLAUDE.md
    born-hollow rule)."""

    @pytest.fixture(autouse=True)
    def _clean_fixture_lane_scratch(self, repo):
        """The subprocess resolves to the REAL ~/.cache root keyed on this
        fixture's repo (repo_key=origin, lane_key=master), which is SHARED
        across every TestWriteVerb invocation. Files a prior test wrote trip
        the overwrite guard, so a second run of the suite reddens on its own
        residue. Clean the fixture's lane dir before each test so each measures
        its own call, not a leftover. Safe: this is under origin/master/, never
        the real lane's ud-dreamwork/<branch>/ evidence root."""
        import shutil
        d = ls.lane_scratch_dir(repo, create=False)
        if d.exists():
            shutil.rmtree(d)
        yield

    @staticmethod
    def _run(repo: Path, name: str, payload: bytes, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["python3", str(CLI_PATH), "write", name, *extra,
             "--cwd", str(repo)],
            input=payload, capture_output=True,
        )

    def test_writes_payload_and_prints_an_absolute_lane_private_path(self, repo):
        """The core #973 behaviour: pipe content in, get the path back, the file
        holds exactly what was piped."""
        r = self._run(repo, "redproof-d1-973.txt", b"FAIL: red line\n")
        assert r.returncode == 0, r.stderr
        printed = Path(r.stdout.decode().strip())
        assert printed.is_absolute(), f"printed path is not absolute: {printed}"
        # The file is under THIS repo's lane-private dir, not a shared root
        lane_dir = ls.lane_scratch_dir(repo, create=False)
        assert printed.is_relative_to(lane_dir), (
            f"wrote outside the lane-private dir ({printed} not under "
            f"{lane_dir}) — evidence must land lane-private (#652)")
        assert printed.read_bytes() == b"FAIL: red line\n"

    def test_the_path_it_prints_is_the_path_it_wrote_to(self, repo):
        """#934's sharper form: the printed path and the written path must be the
        SAME path, not a directory plus a name the lane has to rejoin. A lane
        quotes what was printed; that must be the evidence."""
        r = self._run(repo, "evidence.txt", b"payload\n")
        printed = Path(r.stdout.decode().strip())
        assert printed.read_bytes() == b"payload\n", (
            "the path printed on stdout must hold the bytes written — a lane "
            "quotes that path, and it must be the evidence the run produced")

    def test_empty_payload_is_refused_and_writes_no_file(self, repo):
        """Degrade-to-zero (#868): an empty capture must not look like a
        successful one. An evidence file that exists and proves nothing reads
        exactly like real evidence — the failure the #878 persistence rule
        exists to prevent. Refused (exit 2), no file left behind, remedy named.

        Isolation: the subprocess resolves to the REAL ~/.cache scratch root
        (keyed on this fixture's repo), so a leftover from a prior run would
        satisfy the absence assertion falsely. Clean the target first, then
        assert THIS call created nothing — measuring the call's effect, not a
        prior run's residue."""
        target = ls.lane_scratch_dir(repo, create=False) / "empty.txt"
        target.unlink(missing_ok=True)  # measure this call, not a leftover
        r = self._run(repo, "empty.txt", b"")
        assert r.returncode == 2, r.stderr
        assert b"refuse" in r.stderr
        assert b"0 bytes" in r.stderr
        # No file is left behind to masquerade as evidence
        assert not target.exists()

    def test_second_write_to_the_same_name_is_refused_without_force(self, repo):
        """Direction 2 candidate the brief named: a second call overwrites the
        first lane's capture, so the evidence quoted in a delivery is not the
        evidence the run produced. Refuse by default (#940 shape); --force opts
        in because same lane + same name is the lane's own choice."""
        first = self._run(repo, "cap.txt", b"FIRST\n")
        assert first.returncode == 0
        again = self._run(repo, "cap.txt", b"SECOND\n")
        assert again.returncode == 2, again.stderr
        assert b"refuse" in again.stderr
        assert b"--force" in again.stderr
        # The first capture is intact, not replaced
        printed = Path(first.stdout.decode().strip())
        assert printed.read_bytes() == b"FIRST\n", (
            "a refused overwrite must leave the original evidence byte-identical")
        # --force does replace, because the lane asked explicitly
        forced = self._run(repo, "cap.txt", b"SECOND\n", "--force")
        assert forced.returncode == 0, forced.stderr
        assert printed.read_bytes() == b"SECOND\n"

    def test_a_traversing_name_stays_inside_the_lane_dir(self, repo):
        """The slug is the traversal protection: `../../escape` folds each `..`
        into `unnamed`, so the path stays lane-private. A containment check
        AFTER slug-ging can never fire (the born-hollow rule), so the slug is the
        protection and this test pins that property rather than asserting a
        dead guard."""
        r = self._run(repo, "../../escape.txt", b"x")
        assert r.returncode == 0, r.stderr
        printed = Path(r.stdout.decode().strip())
        lane_dir = ls.lane_scratch_dir(repo, create=False)
        assert printed.is_relative_to(lane_dir), (
            f"a traversing name escaped the lane dir: {printed}")
        # No parent-component survives in the path
        assert ".." not in printed.relative_to(lane_dir).parts

    def test_help_lists_the_write_subcommand(self, repo):
        """Discoverability (#973's framing): a lane that runs ``--help`` must
        learn the verb exists, otherwise it re-invents the write exactly as
        before. The epilog names `write`."""
        r = subprocess.run(
            ["python3", str(CLI_PATH), "--help", "--cwd", str(repo)],
            capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert "write" in r.stdout, (
            "--help must advertise the write subcommand or a lane cannot "
            "discover it (#973)")

    def test_from_reads_a_file_instead_of_stdin(self, repo, tmp_path):
        """``--from <path>`` reads a file, so a lane can persist a file it
        already captured without re-piping. Empty --from is refused too
        (degrade-to-zero applies to both inputs)."""
        src = tmp_path / "src.txt"
        src.write_bytes(b"from-file-payload\n")
        r = self._run(repo, "from.txt", b"", "--from", str(src))
        assert r.returncode == 0, r.stderr
        printed = Path(r.stdout.decode().strip())
        assert printed.read_bytes() == b"from-file-payload\n"
        # Empty --from is refused (no stdin consumed)
        empty_src = tmp_path / "empty.txt"
        empty_src.write_bytes(b"")
        r2 = self._run(repo, "e.txt", b"", "--from", str(empty_src))
        assert r2.returncode == 2
        assert b"0 bytes" in r2.stderr


class TestVerbDirectoryDisambiguation:
    """#981: positional typos must not masquerade as successful directories."""

    @staticmethod
    def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["python3", str(CLI_PATH), *args, "--cwd", str(repo)],
            capture_output=True, text=True,
        )

    def test_write_typo_is_refused_with_suggestion_and_directory_remedy(self, repo):
        r = self._run(repo, "wrote", "evidence.txt")
        assert r.returncode == 2
        assert r.stdout == ""
        assert ("unknown verb 'wrote'; did you mean 'write'? "
                "for the legacy directory form use --dir wrote") in r.stderr

    def test_unknown_verb_is_refused_instead_of_creating_a_directory(self, repo):
        name = "brief-validator-unknown-verb"
        target = ls.lane_scratch_dir(repo, create=False) / name
        target.rmdir() if target.exists() else None
        r = self._run(repo, name)
        assert r.returncode == 2, (
            f"unknown verb '{name}' was absorbed as a directory and exited "
            f"{r.returncode}; evidence can be lost behind a printed path")
        assert r.stdout == ""
        assert (f"unknown verb '{name}'; for the legacy directory form use "
                f"--dir {name}") in r.stderr
        assert not target.exists()

    def test_explicit_directory_form_preserves_arbitrary_legacy_names(self, repo):
        name = "brief-validator-unknown-verb"
        r = self._run(repo, "--dir", name)
        assert r.returncode == 0, r.stderr
        assert Path(r.stdout.strip()).name == name

    def test_measure_still_survives_command_substitution(self, repo):
        script = 'M="$("$1" "$2" measure --cwd "$3")"; rc=$?; printf "%s\\n%s\\n" "$rc" "$M"'
        r = subprocess.run(
            ["bash", "-c", script, "bash", "python3", str(CLI_PATH), str(repo)],
            capture_output=True, text=True,
        )
        rc, measured = r.stdout.splitlines()
        assert rc == "0", (
            "measure returned nonzero inside command substitution; the shell "
            "would assign an empty string and could carry on")
        assert measured
        assert Path(measured).name == "measure"


class TestDetachedLaneJob:
    """The ccc shell may exit; only verified start + completion is success (#1169)."""

    @staticmethod
    def _env(tmp_path: Path) -> dict[str, str]:
        return {
            **os.environ,
            "HOME": str(tmp_path),
            "DREAMWORK_LANE_ID": f"fixture-{tmp_path.name}",
        }

    @staticmethod
    def _launch(tmp_path: Path, name: str, program: str) -> subprocess.CompletedProcess:
        # The outer bash exits immediately after job-launch, matching the parent
        # boundary that killed ccc-routed `nohup ... &` jobs in #1169.
        return subprocess.run(
            [
                "bash", "-c", 'python3 "$1" job-launch "$2" -- python3 -c "$3"',
                "lane-job-shell", str(CLI_PATH), name, program,
            ],
            cwd=REPO, env=TestDetachedLaneJob._env(tmp_path),
            text=True, capture_output=True, check=False,
        )

    @staticmethod
    def _wait(tmp_path: Path, name: str, timeout: str = "3") -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(CLI_PATH), "job-wait", name, "--timeout", timeout],
            cwd=REPO, env=TestDetachedLaneJob._env(tmp_path),
            text=True, capture_output=True, check=False,
        )

    @staticmethod
    def _field(output: str, key: str) -> str:
        prefix = f"{key}="
        return next(line.removeprefix(prefix) for line in output.splitlines()
                    if line.startswith(prefix))

    def test_job_survives_launch_shell_and_requires_complete_record(self, tmp_path):
        launched = self._launch(
            tmp_path, "completed",
            "import time; print('real output', flush=True); time.sleep(.15)",
        )
        assert launched.returncode == 0, launched.stderr
        pid = int(self._field(launched.stdout, "STARTED job=completed pid"))
        log = Path(self._field(launched.stdout, "log"))
        started = Path(self._field(launched.stdout, "start_receipt"))
        assert log.stat().st_size > 0
        assert ls._pid_alive(pid), "launcher must verify and return a still-live pid"
        assert started.read_text() == (
            f"version=1\npid={pid}\nlog_nonempty=1\npid_alive=1\n"
        )

        completed = self._wait(tmp_path, "completed")
        assert completed.returncode == 0, completed.stderr
        assert f"COMPLETE job=completed pid={pid} exit=0" in completed.stdout
        done = Path(self._field(completed.stdout, "completion"))
        assert done.read_text() == f"version=1\npid={pid}\nexit=0\n"
        assert "real output" in log.read_text()

    def test_nonempty_partial_log_and_dead_pid_are_failure(self, tmp_path):
        launched = self._launch(
            tmp_path, "dies",
            "import time; print('partial output', flush=True); time.sleep(.25)",
        )
        assert launched.returncode == 0, launched.stderr
        pid = int(self._field(launched.stdout, "STARTED job=dies pid"))
        log = Path(self._field(launched.stdout, "log"))
        done = Path(self._field(launched.stdout, "completion"))
        os.kill(pid, signal.SIGTERM)  # only the fixture supervisor spawned above

        failed = self._wait(tmp_path, "dies")
        assert failed.returncode == 1
        assert log.stat().st_size > 0, "partial output alone must not become success"
        assert not done.exists()
        assert (
            f"FAILURE: job 'dies' pid {pid} died without a valid completion record"
            in failed.stderr
        )

    def test_truncated_completion_record_is_failure(self, tmp_path):
        launched = self._launch(
            tmp_path, "truncated",
            "import time; print('partial output', flush=True); time.sleep(.3)",
        )
        assert launched.returncode == 0, launched.stderr
        done = Path(self._field(launched.stdout, "completion"))
        done.write_text("version=1\npid=")

        failed = self._wait(tmp_path, "truncated", timeout="0")
        assert failed.returncode == 1
        assert "completion record is invalid: empty or truncated" in failed.stderr
