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


# ── #717: a second injection to one file must not overwrite the first ──

def _inject(repo: Path, path: str, body: str) -> None:
    """begin -> sabotage -> restore, one distinct injection."""
    _begin(repo, path)
    (repo / path).write_text(body)
    _restore(repo, path)


class TestTwoInjectionsToOneFileAreBothCounted:
    """THE #717 red run: two distinct injections to ONE file, both restored,
    and check reports 2 naming both — not 1 with the first silently gone."""

    def test_two_distinct_injections_count_as_two_and_name_both_hints(
            self, repo, capsys):
        # PRECONDITION: the two injections differ, so this is two injections,
        # not the same one twice. Derived at runtime, not a literal, so a
        # future fixture change cannot collapse the case into a tautology.
        body_a = "export function route() { return false; /* BUG A */ }\n"
        body_b = "export function route() { return null; /* BUG B */ }\n"
        assert rp._sha(body_a.encode()) != rp._sha(body_b.encode())

        _inject(repo, "router.js", body_a)
        _inject(repo, "router.js", body_b)

        # the registry holds TWO restored entries for the one path
        entries, _ = rp._read_registry(repo)
        restored = [e for e in entries if e.get("state") == rp.RESTORED]
        assert len(restored) == 2, entries

        exit = _check(repo)
        out, _ = capsys.readouterr()
        assert exit == 0, out
        # discriminating: the count is 2, and BOTH hints are named — a count
        # alone is not (it could name the same hint twice)
        assert "2 injection(s) registered" in out, out
        assert "BUG A" in out, out
        assert "BUG B" in out, out

    def test_the_same_sabotage_restored_twice_is_one_not_two(self, repo, capsys):
        """The dedup arm of #717: observing the same state twice is one
        injection, not two — an injection is a state, not an act."""
        body = "export function route() { return false; /* BUG */ }\n"
        _inject(repo, "router.js", body)
        _inject(repo, "router.js", body)   # identical bytes second time

        entries, _ = rp._read_registry(repo)
        restored = [e for e in entries if e.get("state") == rp.RESTORED]
        assert len(restored) == 1, entries

        exit = _check(repo)
        out, _ = capsys.readouterr()
        assert exit == 0
        assert "1 injection(s) registered" in out, out


class TestTheHistoryScanSeesEveryInjectedSha:
    """The reason #717 stopped being cosmetic: a registry that keeps only the
    last injection per path blinds the #710 scan, which matches commits against
    EACH recorded sha. Two injections, the FIRST committed mid-branch — the scan
    must name that commit, not miss it because the second injection overwrote
    the record."""

    def test_a_committed_first_injection_is_caught_after_a_second(self, lane, capsys):
        # injection 1: committed while sabotaged, then restored
        _begin(lane, "router.js")
        (lane / "router.js").write_text(
            "export function route() { return false; /* BUG A */ }\n")
        poisoned = _commit(lane, "router.js", msg="wip(#717): mid red-proof A")
        sha_a_committed = _blob_sha_at(lane, poisoned, "router.js")
        _restore(lane, "router.js")

        # injection 2: a different sabotage, restored before any commit
        _begin(lane, "router.js")
        (lane / "router.js").write_text(
            "export function route() { return null; /* BUG B */ }\n")
        _restore(lane, "router.js")
        (lane / "router.js").write_text(
            "export function route() { return Boolean(guard); }\n")
        _commit(lane, "router.js", msg="fix(#717): the real fix")

        # PRECONDITIONS: two distinct shas recorded (the old bug kept one),
        # and BUG A's committed blob IS one of them — otherwise the scan has
        # nothing to match and the test proves nothing.
        entries, _ = rp._read_registry(lane)
        restored = [e for e in entries if e.get("state") == rp.RESTORED]
        assert len(restored) == 2, entries
        recorded_shas = {e["injected_sha"] for e in restored}
        assert sha_a_committed in recorded_shas, (
            "BUG A's sha is not recorded — the scan cannot catch it; the test "
            "would pass under the old bug by never having the sha to match")

        rep = rp.scan_history(lane, entries)
        assert rep["commits"] == 2 and rep["blobs_read"] == 2, rep
        assert len(rep["hits"]) == 1, rep
        assert rep["hits"][0]["commit"] == poisoned, rep["hits"]

        exit = _check(lane)
        _, err = capsys.readouterr()
        assert exit == 1, err
        assert poisoned[:12] in err, err
        assert "BUG A" in err, err


# ── #726: a dotted path must survive the round trip (lstrip-as-prefix) ──

class TestDottedPathRoundTrip:
    """THE #726 red run: ``_to_posix`` used ``lstrip("./")``, which takes a
    CHARACTER SET, not a prefix — so it ate every leading ``.`` or ``/`` and
    mangled ``.dreamwork/lessons.md`` into the nonexistent
    ``dreamwork/lessons.md``. ``begin`` then failed loudly (the mangled path
    does not exist) and NO existing test covered a dotted path, because every
    fixture used ``router.js``.

    The deliverable is the case nobody wrote: a DOTTED path surviving begin →
    restore → check with its leading dot intact, recorded under the path that
    actually exists."""

    def test_to_posix_preserves_a_leading_dot_not_strips_a_charset(self):
        """The one-line bug: ``lstrip("./")`` is a character-set strip.

        A test that only checks ``"./x"`` -> ``"x"`` passes today; the fix is
        only pinned by a path whose leading char is ``.`` but is NOT the
        ``./`` prefix."""
        # the intended case still works
        assert rp._to_posix("./watch.py") == "watch.py"
        # THE discriminating case: a dotfile/dotdir path keeps its dot
        assert rp._to_posix(".dreamwork/lessons.md") == ".dreamwork/lessons.md"
        assert rp._to_posix(".git/config") == ".git/config"
        # a bare dotfile (no slash) is preserved too
        assert rp._to_posix(".env") == ".env"

    def test_begin_on_a_dotted_path_records_the_correct_key(self, repo):
        """``begin`` must record the path AS PASSED (dot intact), so that
        ``check`` and the #710 history scan look at a file that exists. Under
        the bug the registry held ``dreamwork/lessons.md`` — a nonexistent
        file — and ``begin`` itself refused at the read step."""
        dotted = ".dreamwork/lessons.md"
        parent = repo / ".dreamwork"
        parent.mkdir()
        (repo / dotted).write_text("line\n")
        assert _begin(repo, dotted) == 0
        entries, _ = rp._read_registry(repo)
        armed = [e for e in entries if e.get("state") == rp.ARMED]
        assert len(armed) == 1, entries
        # THE discriminating assertion: the recorded key is the dotted path,
        # not the mangled 'dreamwork/lessons.md'.
        assert armed[0]["path"] == dotted, (
            f"recorded path {armed[0]['path']!r} lost its leading dot — "
            f"check/#710 would scan a file that does not exist (#671)")

    def test_a_dotted_path_survives_the_full_round_trip(self, repo):
        """begin → sabotage → restore → check on a DOTTED path, clean exit.

        This is the case the brief names: nobody wrote it, and it is the only
        one that exercises the bug end-to-end (the registry key, the working-
        tree read, and the history-scan path set all flow through _to_posix)."""
        dotted = ".dreamwork/lessons.md"
        (repo / ".dreamwork").mkdir()
        original = "# title\n"
        (repo / dotted).write_text(original)
        _begin(repo, dotted)
        (repo / dotted).write_text("# title\n# INJECTED BUG\n")
        assert _restore(repo, dotted) == 0
        # the original came back byte-for-byte
        assert (repo / dotted).read_text() == original
        assert _check(repo) == 0


# ── #740: every path entry point stays inside the resolved worktree ──

class TestPathsStayInWorktree:
    @pytest.mark.parametrize("verb", [rp.begin, rp.restore, rp.forget])
    @pytest.mark.parametrize("form", ["parent", "absolute"])
    def test_every_path_entry_point_names_and_refuses_an_escape(
            self, repo, capsys, verb, form):
        outside = repo.parent / "victim.txt"
        original = b"outside sentinel\n"
        outside.write_bytes(original)
        path = "../victim.txt" if form == "parent" else str(outside)

        exit_code = verb(repo, path)
        _, err = capsys.readouterr()

        assert exit_code == 2, err
        assert repr(path) in err, err
        assert "outside the worktree" in err, err
        assert outside.read_bytes() == original

    def test_begin_refuses_an_in_tree_symlink_to_an_outside_file(
            self, repo, capsys):
        outside = repo.parent / "outside.txt"
        outside.write_text("outside\n")
        (repo / "link.txt").symlink_to(outside)

        exit_code = rp.begin(repo, "link.txt")
        _, err = capsys.readouterr()

        assert exit_code == 2, err
        assert "link.txt" in err, err
        assert "outside the worktree" in err, err

    def test_restore_rechecks_a_path_that_became_an_outside_symlink(
            self, repo, capsys):
        outside = repo.parent / "outside.txt"
        outside.write_text("outside bytes\n")
        assert rp.begin(repo, "router.js") == 0
        (repo / "router.js").unlink()
        (repo / "router.js").symlink_to(outside)

        exit_code = rp.restore(repo, "router.js")
        _, err = capsys.readouterr()

        assert exit_code == 2, err
        assert "router.js" in err, err
        assert "outside the worktree" in err, err
        assert outside.read_text() == "outside bytes\n"

    def test_check_refuses_an_unsafe_legacy_registry_path(
            self, repo, capsys):
        outside = repo.parent / "victim.txt"
        original = b"legacy outside sentinel\n"
        outside.write_bytes(original)
        rp._write_registry(repo, [{
            "path": "../victim.txt",
            "state": rp.RESTORED,
            "injected_sha": rp._sha(original),
        }])

        exit_code = rp.check(repo)
        _, err = capsys.readouterr()

        assert exit_code == 2, err
        assert "../victim.txt" in err, err
        assert "outside the worktree" in err, err
        assert outside.read_bytes() == original

    def test_a_missing_contained_path_is_absent_not_outside(
            self, repo, capsys):
        exit_code = rp.begin(repo, "missing/child.txt")
        _, err = capsys.readouterr()

        assert exit_code == 2, err
        assert "missing/child.txt" in err, err
        assert "does not exist in the working tree" in err, err
        assert "outside the worktree" not in err, err
