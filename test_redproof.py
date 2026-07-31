#!/usr/bin/env python3
"""Red-first tests for dev/redproof.py — the red-proof hand-off gate (#683).

The defect under test is SILENT: a lane injects a defect, forgets to restore,
commits, and ships it with a green-looking report. `check` must refuse, naming
the path AND identifying the injected content — "refused" with no referent is
not discriminating. `test_an_unrestored_injection_is_refused_with_a_referent`
reproduces exactly that, so the fix is measured against a demonstrated failure
rather than an asserted one (#683 direction 1).

Restore discipline while writing these (#349/#652): snapshots live in
`~/.cache/ud-dreamwork/lane-scratch/.../redproof/`, restored by the tool's own
`restore` verb (cp from the lane-private snapshot, never `git checkout`).
"""
import importlib.machinery
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

CLI_PATH = Path(__file__).resolve().parent / "dev" / "redproof.py"


def _load():
    loader = importlib.machinery.SourceFileLoader("redproof", str(CLI_PATH))
    spec = importlib.util.spec_from_loader("redproof", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


rp = _load()


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args], stderr=subprocess.DEVNULL, text=True).strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch) -> Path:
    """A real git repo with one tracked file.

    The scratch root is redirected under tmp_path so tests do not collide with
    real lanes (the #652 hazard these tests exist alongside)."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "master", ".")
    (root / "router.js").write_text("export function route() { return true; }\n")
    _git(root, "add", "router.js")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    # Redirect the lane-private scratch root so tests own their registry.
    monkeypatch.setattr(rp._ls, "SCRATCH_ROOT", tmp_path / "scratch")
    return root


def _begin(repo: Path, path: str) -> int:
    return rp.begin(repo, path)


def _restore(repo: Path, path: str) -> int:
    return rp.restore(repo, path)


def _check(repo: Path, **kw) -> int:
    return rp.check(repo, **kw)


# ── direction 1: the defect, and the refusal that names it ────────────

class TestUnrestoredInjectionIsRefused:
    """THE red run: an injection left in the tree must be refused, with a referent."""

    def test_an_unrestored_injection_is_refused_with_a_referent(self, repo, capsys):
        """The #683 defect: inject, never restore, commit. check must REFUSE.

        The refusal must NAME the path and IDENTIFY the injected content — a
        bare 'refused' is not discriminating (it passes on a check that fired
        for any reason)."""
        _begin(repo, "router.js")
        # sabotage: the real defect, plausible-looking
        (repo / "router.js").write_text(
            "export function route() { return false; /* BUG injected */ }\n")
        # NOTE: no restore — the lane got distracted. This is the failure mode.
        exit = _check(repo)
        out, err = capsys.readouterr()
        assert exit == 1, "an unrestored injection MUST be refused (exit 1)"
        # discriminating referent 1: the path is named
        assert "router.js" in err, "refusal must name the injected path"
        # discriminating referent 2: the injected content is identified, not a
        # bare 'refused'. The sha fingerprint and the sabotage hint both count.
        assert "STILL MATCHES" in err or "armed" in err, (
            "refusal must say WHY — 'still matches its recorded injection' "
            "or 'armed'; a bare refusal is not discriminating")

    def test_an_armed_but_unrestored_entry_is_refused(self, repo, capsys):
        """begin without restore is an incomplete red-proof → refuse, naming it."""
        _begin(repo, "router.js")
        (repo / "router.js").write_text("SABOTAGE\n")
        exit = _check(repo)
        _, err = capsys.readouterr()
        assert exit == 1
        assert "router.js" in err
        assert "unrestored" in err or "armed" in err


class TestRestoredInjectionPasses:
    """The green path: restored (to original OR edited further) must pass."""

    def test_restored_to_original_passes(self, repo):
        _begin(repo, "router.js")
        (repo / "router.js").write_text("SABOTAGE\n")
        _restore(repo, "router.js")  # records injected, restores original
        assert _check(repo) == 0

    def test_restored_then_further_edited_passes(self, repo):
        """#683 point 1: a real fix touching the same file must NOT be blocked.

        The check is 'no injection still present', NOT 'identical to snapshot'.
        After restore, the lane applies the real fix; the file differs from both
        the original and the recorded injection, so it passes."""
        _begin(repo, "router.js")
        (repo / "router.js").write_text("SABOTAGE\n")
        _restore(repo, "router.js")
        # the real fix — a genuine change, different from the sabotage
        (repo / "router.js").write_text(
            "export function route() { return true && guard; }\n")
        assert _check(repo) == 0


# ── the three zero-states (#136) ───────────────────────────────────────

class TestZeroStatesAreDistinct:
    """#136: a calm zero and a broken channel must not render identically."""

    def test_no_registry_is_calm_zero(self, repo, capsys):
        """Never used → calm, exit 0, distinct message."""
        exit = _check(repo)
        out, _ = capsys.readouterr()
        assert exit == 0
        assert "calm" in out
        assert "no injections registered" in out

    def test_empty_registry_is_calm_zero(self, repo, capsys):
        """Ran but nothing live → calm, exit 0."""
        _begin(repo, "router.js")
        # never sabotaged → restore drops the no-op entry → registry empties
        _restore(repo, "router.js")
        exit = _check(repo)
        out, _ = capsys.readouterr()
        assert exit == 0
        assert "calm" in out

    def test_unparseable_registry_is_a_fault_not_calm(self, repo, capsys):
        """A broken channel must read as a FAULT, never a calm zero (#671/#136)."""
        reg = rp._registry_path(repo)
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text("{ this is not json", encoding="utf-8")
        exit = _check(repo)
        _, err = capsys.readouterr()
        assert exit == 2, "an unparseable registry must FAULT (exit 2), not pass"
        assert "unparseable" in err or "FAULT" in err


# ── fail closed (#671) ─────────────────────────────────────────────────

class TestFailClosed:
    """A check that cannot evaluate must not read as passing."""

    def test_missing_snapshot_for_an_entry_is_a_fault(self, repo, capsys):
        """A restore whose snapshot vanished cannot proceed → fault, not guess."""
        _begin(repo, "router.js")
        (repo / "router.js").write_text("SABOTAGE\n")
        # corrupt: delete the snapshot the registry points at
        snap = rp._snapshot_path(repo, "router.js")
        snap.unlink()
        exit = _restore(repo, "router.js")
        _, err = capsys.readouterr()
        assert exit == 2, "a missing snapshot must FAULT (exit 2), not guess (#671)"
        assert "missing" in err or "FAULT" in err

    def test_missing_working_tree_file_for_a_restored_entry_is_a_fault(
            self, repo, capsys):
        """A registered file that disappeared cannot be evaluated → fault."""
        _begin(repo, "router.js")
        (repo / "router.js").write_text("SABOTAGE\n")
        _restore(repo, "router.js")
        (repo / "router.js").unlink()  # file gone at hand-off
        exit = _check(repo)
        _, err = capsys.readouterr()
        assert exit == 2
        assert "absent" in err or "FAULT" in err


# ─# restore records the injected state correctly ──────────────────────

class TestRestoreRecordsInjected:
    def test_restore_records_the_injected_sha_and_hint(self, repo):
        _begin(repo, "router.js")
        sabotage = "export function route() { return false; /* BUG */ }\n"
        (repo / "router.js").write_text(sabotage)
        _restore(repo, "router.js")
        entries, _ = rp._read_registry(repo)
        # _find returns only ARMED entries now (#717); a restored record is
        # looked up by its (path, sha). Exactly one restored entry expected.
        restored = [e for e in entries if e.get("state") == rp.RESTORED]
        assert len(restored) == 1, entries
        e = restored[0]
        assert e["injected_sha"] is not None
        assert "BUG" in e["injected_hint"]

    def test_restore_reproduces_the_original_byte_for_byte(self, repo):
        original = (repo / "router.js").read_bytes()
        _begin(repo, "router.js")
        (repo / "router.js").write_text("DIFFERENT\n")
        _restore(repo, "router.js")
        assert (repo / "router.js").read_bytes() == original

    def test_a_noop_begin_is_dropped_not_left_armed(self, repo):
        """begin then restore with no change → no injection, entry dropped.

        Otherwise the byte-test would refuse (wt==injected==original) on a file
        that was never actually sabotaged."""
        _begin(repo, "router.js")
        _restore(repo, "router.js")  # unchanged
        entries, _ = rp._read_registry(repo)
        assert entries == []


# ── CLI smoke ──────────────────────────────────────────────────────────

class TestCli:
    def _env(self, tmp_path):
        # CLI subprocesses cannot see the in-process monkeypatch, so route
        # their scratch root through an env override into an isolated dir.
        env = dict(__import__("os").environ)
        env["REDPROOF_SCRATCH_ROOT"] = str(tmp_path / "cli-scratch")
        return env

    def test_full_protocol_via_cli(self, repo, tmp_path):
        proto = "router.js"
        env = self._env(tmp_path)
        # begin
        r = subprocess.run(["python3", str(CLI_PATH), "begin", proto,
                            "--cwd", str(repo)], capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stderr
        (repo / proto).write_text("CLI SABOTAGE\n")
        # restore
        r = subprocess.run(["python3", str(CLI_PATH), "restore", proto,
                            "--cwd", str(repo)], capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stderr
        # check clean
        r = subprocess.run(["python3", str(CLI_PATH), "check",
                            "--cwd", str(repo)], capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stderr
        assert "clean" in r.stdout

    def test_check_require_refuses_when_none_registered(self, repo, tmp_path):
        """--require enforces the brief-mandated minimum (point 3)."""
        env = self._env(tmp_path)
        r = subprocess.run(["python3", str(CLI_PATH), "check", "--require", "1",
                            "--cwd", str(repo)], capture_output=True, text=True, env=env)
        assert r.returncode == 1
        assert "require" in r.stderr


# ── #710: an injection committed mid-branch, restored, and committed again ──

def _commit(repo: Path, *paths: str, msg: str = "wip") -> str:
    _git(repo, "add", *paths)
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg)
    return _git(repo, "rev-parse", "HEAD")


def _blob_sha_at(repo: Path, rev: str, path: str) -> str:
    """sha1 of the CONTENT `rev` holds for `path` — the scan's own comparison."""
    out = subprocess.check_output(
        ["git", "-C", str(repo), "cat-file", "blob", f"{rev}:{path}"])
    return rp._sha(out)


@pytest.fixture
def lane(repo: Path) -> Path:
    """`repo` with a lane branch cut from master — the shape #710 describes.

    A fixture branch, never a live lane branch and never master."""
    _git(repo, "switch", "-q", "-c", "lane-fixture")
    return repo


def _poison(lane: Path) -> tuple[str, str]:
    """The #710 sequence: inject, COMMIT while sabotaged, restore, commit again.

    Returns (poisoned_sha, clean_sha). Committing mid-injection is not lane
    misbehaviour — COMMIT INCREMENTALLY mandates it — which is why the tree at
    hand-off is clean and only history is poisoned."""
    _begin(lane, "router.js")
    (lane / "router.js").write_text("export function route() { return false; }\n")
    poisoned = _commit(lane, "router.js", msg="wip(#710): mid red-proof")
    _restore(lane, "router.js")
    (lane / "router.js").write_text(
        "export function route() { return Boolean(guard); }\n")
    clean = _commit(lane, "router.js", msg="fix(#710): the real fix")
    return poisoned, clean


class TestInjectionInHistoryIsRefused:
    """THE #710 red run: clean tree, poisoned history, and the gate was blind."""

    def test_the_commit_holding_the_injection_is_named(self, lane, capsys):
        poisoned, clean = _poison(lane)
        entries, _ = rp._read_registry(lane)

        # PRECONDITIONS, asserted rather than assumed: a refusal is only
        # evidence if the scan had a range to look at and actually read blobs
        # in it, and if the TREE is clean so history is the ONLY possible cause.
        rep = rp.scan_history(lane, entries)
        assert rep["commits"] == 2, rep
        assert rep["blobs_read"] == 2, rep
        wt = rp._sha((lane / "router.js").read_bytes())
        assert wt != entries[0]["injected_sha"], "tree is dirty; test proves nothing"
        assert _blob_sha_at(lane, poisoned, "router.js") == entries[0]["injected_sha"]

        exit = _check(lane)
        out, err = capsys.readouterr()
        assert exit == 1
        assert poisoned[:12] in err, err
        assert "router.js" in err
        # discriminating: it names the poisoned commit, not every commit
        assert clean[:12] not in err, err
        # and it names the remedy, because refusing without one strands the lane
        assert "squash" in err.lower(), err

    def test_a_clean_branch_passes_and_says_what_it_examined(self, lane, capsys):
        """#590: a zero is a question about whether you looked. So say."""
        _begin(lane, "router.js")
        (lane / "router.js").write_text("SABOTAGE\n")
        _restore(lane, "router.js")           # restored BEFORE committing
        (lane / "router.js").write_text(
            "export function route() { return Boolean(guard); }\n")
        _commit(lane, "router.js", msg="fix(#710): only clean commits")

        entries, _ = rp._read_registry(lane)
        rep = rp.scan_history(lane, entries)
        assert rep["commits"] == 1 and rep["blobs_read"] == 1, rep

        exit = _check(lane)
        out, _ = capsys.readouterr()
        assert exit == 0
        assert "examined 1 commit" in out, out
        assert "read 1 blob" in out, out


class TestTheScanCannotLookAtNothingAndPass:
    """#671: a scan that examined nothing must not render as a clean branch."""

    def test_an_unresolvable_base_is_a_fault_not_a_pass(self, lane, capsys):
        _begin(lane, "router.js")
        (lane / "router.js").write_text("SABOTAGE\n")
        _restore(lane, "router.js")
        _git(lane, "branch", "-D", "master")   # no master, no main -> no range
        exit = _check(lane)
        _, err = capsys.readouterr()
        assert exit == 2, err
        assert "base" in err.lower()

    def test_a_zero_commit_range_does_not_read_as_clean(self, repo, capsys):
        """HEAD == base: genuinely nothing in history, and it must SAY that
        rather than print a clean bill of a history it never saw."""
        _begin(repo, "router.js")
        (repo / "router.js").write_text("SABOTAGE\n")
        _restore(repo, "router.js")
        entries, _ = rp._read_registry(repo)
        assert rp.scan_history(repo, entries)["commits"] == 0
        exit = _check(repo)
        out, _ = capsys.readouterr()
        assert exit == 0
        assert "EXAMINED NO COMMIT" in out, out


class TestKnownHole:
    """Direction 2, executable: the branch the scan still gets wrong.

    Kept as a passing test asserting the WRONG answer, so that closing the
    hole fails here loudly instead of silently — and so the hole cannot be
    forgotten the way a paragraph in a report can."""

    def test_a_fork_point_moved_past_the_injection_hides_it(self, lane, capsys):
        poisoned, clean = _poison(lane)
        # The coordinator merges (fast-forward here), then the lane keeps going
        # on the same branch. merge-base is now PAST the poisoned commit.
        _git(lane, "branch", "-f", "master", clean)
        (lane / "router.js").write_text("export function route() { return guard; }\n")
        _commit(lane, "router.js", msg="fix(#710): second increment")

        entries, _ = rp._read_registry(lane)
        rep = rp.scan_history(lane, entries)
        assert rep["commits"] == 1, rep          # only the post-merge commit
        assert rep["hits"] == []

        # ...while master demonstrably holds the injection, forever.
        assert _blob_sha_at(lane, poisoned, "router.js") == entries[0]["injected_sha"]
        assert _git(lane, "merge-base", "--is-ancestor", poisoned, "master") == ""

        assert _check(lane) == 0                 # <- the false green, on purpose

    def test_edits_between_the_sabotaged_commit_and_the_restore_hide_it(self, lane):
        """The comparison is whole-file byte-identity with what `restore` saw.

        A lane that keeps working on the file after the sabotaged commit makes
        `restore` record bytes that are not the bytes any commit holds — the
        defect is in history and the scan cannot recognise it."""
        _begin(lane, "router.js")
        (lane / "router.js").write_text("export function route() { return false; }\n")
        poisoned = _commit(lane, "router.js", msg="wip(#710): mid red-proof")
        (lane / "router.js").write_text(          # more work, still sabotaged
            "export function route() { return false; }\n// unrelated note\n")
        _restore(lane, "router.js")
        _commit(lane, "router.js", msg="fix(#710): the real fix")

        entries, _ = rp._read_registry(lane)
        rep = rp.scan_history(lane, entries)
        assert rep["commits"] == 2 and rep["blobs_read"] == 2, rep

        # the defect IS in that commit ...
        assert "return false" in subprocess.check_output(
            ["git", "-C", str(lane), "cat-file", "blob", f"{poisoned}:router.js"],
            text=True)
        # ... but its bytes are not the recorded ones, so the scan misses it
        assert _blob_sha_at(lane, poisoned, "router.js") != entries[0]["injected_sha"]
        assert rep["hits"] == []
        assert _check(lane) == 0                 # <- the false green, on purpose
