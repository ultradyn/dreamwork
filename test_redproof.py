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
import hashlib
import inspect
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

import dev.land_lane as land_lane

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
    real lanes (the #652 hazard these tests exist alongside). A launch identity
    is set so the fixture models a REAL lane (#870): begin/restore/check resolve
    the lane's own token-keyed registry (MODE A). The coordinator path — no
    identity, enumeration — has its own tests below (#895)."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "master", ".")
    (root / "router.js").write_text("export function route() { return true; }\n")
    # Every fixture injection declares a separate expectation source. The
    # feature tests below use other files explicitly; this is the default for
    # the older protocol coverage.
    (root / "expectation.txt").write_text("route expectation fixture\n")
    _git(root, "add", "router.js")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    # Redirect the lane-private scratch root so tests own their registry.
    monkeypatch.setattr(rp._ls, "SCRATCH_ROOT", tmp_path / "scratch")
    # Model a dispatched lane: a launch identity is in env (#870). Without it a
    # test is indistinguishable from the coordinator, whose audit must enumerate.
    monkeypatch.setenv(rp._ls.IDENTITY_ENV, "fixture-lane-aa895")
    return root


def _begin(repo: Path, path: str,
           expectations: tuple[str, ...] = ("expectation.txt",)) -> int:
    return rp.begin(repo, path, expectations)


def _restore(repo: Path, path: str) -> int:
    return rp.restore(repo, path)


def _check(repo: Path, **kw) -> int:
    return rp.check(repo, **kw)


def _observe(repo: Path, path: str, failure: str, command: list[str]) -> int:
    return rp.observe(repo, path, failure=failure, command=command)


def test_two_lane_registries_in_one_worktree_restore_their_own_bytes(
        repo, monkeypatch):
    """#870: same target/name, distinct lane identities, no crossed restore."""
    target = repo / "router.js"
    lane_a = "a" * 32
    lane_b = "b" * 32

    monkeypatch.setenv(rp._ls.IDENTITY_ENV, lane_a)
    target.write_bytes(b"ONLY LANE A COULD HAVE SNAPSHOTTED\n")
    assert _begin(repo, "router.js") == 0
    registry_a = rp._registry_path(repo)

    monkeypatch.setenv(rp._ls.IDENTITY_ENV, lane_b)
    target.write_bytes(b"ONLY LANE B COULD HAVE SNAPSHOTTED\n")
    assert _begin(repo, "router.js") == 0  # force the same registry name
    registry_b = rp._registry_path(repo)

    assert lane_a != lane_b  # non-zero denominator: two actual identities
    assert registry_a != registry_b
    independent_digest = hashlib.sha1(lane_a.encode()).hexdigest()[:12]
    expected_a = (rp._ls.SCRATCH_ROOT / "repo" / "master" /
                  f"lane-{lane_a}-{independent_digest}" /
                  rp.SUB / "registry.json")
    assert registry_a == expected_a  # actual registry location, independent layout

    target.write_bytes(b"LANE A SABOTAGE\n")
    monkeypatch.setenv(rp._ls.IDENTITY_ENV, lane_a)
    assert _restore(repo, "router.js") == 0
    assert target.read_bytes() == b"ONLY LANE A COULD HAVE SNAPSHOTTED\n", (
        "crossed snapshot: lane A restore produced lane B bytes")

    target.write_bytes(b"LANE B SABOTAGE\n")
    monkeypatch.setenv(rp._ls.IDENTITY_ENV, lane_b)
    assert _restore(repo, "router.js") == 0
    assert target.read_bytes() == b"ONLY LANE B COULD HAVE SNAPSHOTTED\n"


def test_crossed_registry_would_restore_lane_b_bytes_into_lane_a(
        repo, monkeypatch):
    """The collision consequence, isolated from the armed-entry refusal.

    This models the state after two concurrent begins both observed no armed
    entry, then persisted. With broken identity keying, B overwrites A's
    registry and snapshot before A restores.
    """
    target = repo / "router.js"

    def persist_arm(identity: str, original: bytes) -> None:
        monkeypatch.setenv(rp._ls.IDENTITY_ENV, identity)
        snap = rp._snapshot_path(repo, "router.js")
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_bytes(original)
        rp._write_registry(repo, [{
            "path": "router.js",
            "original_sha": rp._sha(original),
            "snapshot": str(snap),
            "state": rp.ARMED,
            "begun_at": rp._now(),
            "expectation_sources": [{
                "path": "expectation.txt",
                "sha": rp._sha((repo / "expectation.txt").read_bytes()),
            }],
            "injected_sha": None,
            "injected_hint": None,
            "restored_at": None,
        }])

    persist_arm("a" * 32, b"ONLY LANE A COULD HAVE SNAPSHOTTED\n")
    persist_arm("b" * 32, b"ONLY LANE B COULD HAVE SNAPSHOTTED\n")
    target.write_bytes(b"LANE A SABOTAGE\n")

    monkeypatch.setenv(rp._ls.IDENTITY_ENV, "a" * 32)
    assert _restore(repo, "router.js") == 0
    assert target.read_bytes() == b"ONLY LANE A COULD HAVE SNAPSHOTTED\n", (
        "crossed snapshot: lane A restore produced lane B bytes: "
        f"{target.read_bytes()!r}")


def test_begin_refuses_to_replace_an_armed_snapshot(repo, capsys):
    assert _begin(repo, "router.js") == 0
    original_snapshot = rp._snapshot_path(repo, "router.js").read_bytes()
    (repo / "router.js").write_bytes(b"OTHER BYTES\n")

    assert _begin(repo, "router.js") == 2
    _, err = capsys.readouterr()
    assert "already has an armed snapshot" in err
    assert rp._snapshot_path(repo, "router.js").read_bytes() == original_snapshot


def test_atomic_claim_refuses_even_if_a_racing_registry_read_was_empty(
        repo, capsys):
    """The filesystem claim closes read-empty/read-empty begin interleaving."""
    assert _begin(repo, "router.js") == 0
    rp._registry_path(repo).unlink()  # model B's earlier empty registry read

    second = _begin(repo, "router.js")
    assert second == 2, (
        "second begin replaced the crossed snapshot after both lanes observed "
        "an empty registry")
    _, err = capsys.readouterr()
    assert "snapshot name" in err and "already armed" in err


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
        """Never used → calm zero, exit 0, distinct from a verified restore.

        An absent registry at --require 0 (the default) is the expected state,
        reported via the blind-case calm path with the evidence-artifact
        denominator (#1038 Finding 2). The assertions check the calm-zero
        SIGNATURE common to both coordinator and named-lane modes (the test
        process may carry a launch identity), not mode-specific wording, so the
        invariant holds regardless of which mode the fixture resolves to."""
        exit = _check(repo)
        out, _ = capsys.readouterr()
        assert exit == 0
        assert "no injection required and none registered" in out, out
        assert "0 required" in out, out
        # Finding 2: the evidence-artifact denominator is present and derived.
        assert "examined 0 evidence artifact(s) for 0 registered" in out, out
        assert "NOT a verification of restoration" in out, out
        # Distinct from a fault (#136): a broken channel reads as FAULT, not calm.
        assert "FAULT" not in out, out

    def test_empty_registry_is_calm_zero(self, repo, capsys):
        """Ran but nothing live → no evidence, exit 0."""
        _begin(repo, "router.js")
        # never sabotaged → restore drops the no-op entry → registry empties
        _restore(repo, "router.js")
        exit = _check(repo)
        out, _ = capsys.readouterr()
        assert exit == 0
        assert "no evidence" in out

    def test_unparseable_registry_is_a_fault_not_calm(self, repo, capsys):
        """A broken channel must read as a FAULT, never a calm zero (#671/#136)."""
        reg = rp._registry_path(repo)
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text("{ this is not json", encoding="utf-8")
        exit = _check(repo)
        _, err = capsys.readouterr()
        assert exit == 2, "an unparseable registry must FAULT (exit 2), not pass"
        assert "unparseable" in err or "FAULT" in err


class TestRequiredProofRemediesMatchTheProvenance:
    """Missing, empty, and short populations need one honest default remedy."""

    FRESH = "Produce a fresh causal proof"

    def test_missing_registry_asks_for_fresh_proof_not_an_ancestor(
            self, repo, capsys):
        exit_code = _check(repo, require=1)
        _, err = capsys.readouterr()

        assert exit_code == 2
        assert self.FRESH in err, (
            "missing registry received the wrong remedy; expected fresh causal "
            "proof guidance:\n" + err)
        assert "ancestor's injection" not in err, err

    def test_empty_registry_asks_for_fresh_proof_not_an_ancestor(
            self, repo, capsys):
        rp._write_registry(repo, [])

        exit_code = _check(repo, require=1)
        _, err = capsys.readouterr()

        assert exit_code == 1
        assert "registry empty" in err, err
        assert self.FRESH in err, (
            "empty registry received the wrong remedy; expected fresh causal "
            "proof guidance:\n" + err)
        assert "ancestor's injection" not in err, err

    def test_under_count_registry_asks_for_fresh_proof_not_an_ancestor(
            self, repo, capsys):
        _begin(repo, "router.js")
        (repo / "router.js").write_text("UNDER COUNT SABOTAGE\n")
        _restore(repo, "router.js")
        capsys.readouterr()

        exit_code = _check(repo, require=2)
        _, err = capsys.readouterr()

        assert exit_code == 1
        assert "1 injection(s) registered, but --require 2 was set" in err, err
        assert self.FRESH in err, (
            "under-count registry received the wrong remedy; expected fresh "
            "causal proof guidance:\n" + err)
        assert "ancestor's injection" not in err, err

    def test_explicit_carry_forward_names_the_coordinator_and_current_lane_cycle(
            self, repo, capsys):
        exit_code = _check(repo, require=1, carry_forward=True)
        _, err = capsys.readouterr()

        assert exit_code == 2
        assert "Carry-forward provenance was supplied" in err, err
        assert "coordinator's brief must name" in err, err
        assert "same carried production path" in err, err
        assert "same expectation" in err, err
        assert "same discriminating test" in err, err
        assert all(verb in err for verb in ("`begin`", "`observe`", "`restore`", "`check`")), err
        assert "prior worktree location for use as `--cwd`" in err, err
        assert "audits exactly the worktree root it is given" in err, err
        assert "can satisfy `--require` from that root's registry" in err, err
        assert "operator is responsible" in err, err


def test_reach_examined_fragment_formats_non_empty_population():
    """#1038 Finding 2: the shared denominator formatter must handle a
    NON-empty population. The calm path's population is structurally empty
    (it runs only when no registry was located), so its own "examined 0 for 0"
    assertion cannot distinguish a real formatter from a hardcoded zero. This
    test drives the formatter with (1, 1) — the discriminating guard a literal
    ``0`` or a ``sum()`` over an always-empty list would fail."""
    assert rp._reach_examined_fragment(1, 1) == (
        "examined 1 evidence artifact(s) for 1 registered injection(s)")
    assert rp._reach_examined_fragment(0, 0) == (
        "examined 0 evidence artifact(s) for 0 registered injection(s)")


class TestCheckDoesNotClaimProductionEvidence:
    """#795: restoration evidence must not masquerade as production reach."""

    def test_a_non_test_target_is_other_not_claimed_as_production(
            self, repo, capsys):
        _inject(repo, "router.js", "SABOTAGE\n")

        exit = _check(repo)
        out, _ = capsys.readouterr()

        assert exit == 0
        assert "check: restoration clean" in out
        assert "1 injection(s) registered" in out
        assert "1 other target(s), 0 test-like target(s)" in out
        assert "red-proof reach: DID NOT CHECK" in out
        assert "production" not in out.lower()
        assert "check: clean" not in out

    def test_a_test_file_is_visible_but_not_refused(self, repo, capsys):
        target = repo / "test_route.py"
        target.write_text("EXPECTED = True\n")
        _inject(repo, "test_route.py", "EXPECTED = False\n")

        exit = _check(repo)
        out, _ = capsys.readouterr()

        assert exit == 0, out
        assert "0 other target(s), 1 test-like target(s)" in out
        assert "[test-like] test_route.py" in out
        assert "WARNING: test-like target" in out
        assert "does not establish a production injection" in out

    def test_classification_uses_the_resolved_target(self, repo, capsys):
        target = repo / "test_route.py"
        target.write_text("EXPECTED = True\n")
        (repo / "production_alias.py").symlink_to(target)

        _begin(repo, "./production_alias.py")
        target.write_text("EXPECTED = False\n")
        _restore(repo, "production_alias.py")
        entries, _ = rp._read_registry(repo)
        assert entries[0]["path"] == "test_route.py"

        assert _check(repo) == 0
        out, _ = capsys.readouterr()
        assert "[test-like] test_route.py" in out
        assert "production_alias.py" not in out

    def test_a_nonmatching_test_name_is_other_but_the_disclaimer_still_holds(
            self, repo, capsys):
        target = repo / "expectations.py"
        target.write_text("EXPECTED = True\n")
        _inject(repo, "expectations.py", "EXPECTED = False\n")

        assert _check(repo) == 0
        out, _ = capsys.readouterr()
        assert "[other] expectations.py" in out
        assert "red-proof reach: DID NOT CHECK" in out
        assert "CAUGHT by" not in out

    def test_a_guard_fixture_target_remains_allowed(self, repo, capsys):
        target = repo / "dev" / "capture" / "fixture.mjs"
        target.parent.mkdir(parents=True)
        target.write_text("export const expected = true;\n")
        _inject(repo, "dev/capture/fixture.mjs",
                "export const expected = false;\n")

        assert _check(repo) == 0
        out, _ = capsys.readouterr()
        assert "[test-like] dev/capture/fixture.mjs" in out
        assert "valid when test/guard tooling is the named production subject" in out

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


# ─#950: a state this build cannot read ────────────────────────────────

class TestUnknownStateIsNamedNotCollapsed:
    """#950: an entry whose state this build does not know is refused as the
    dangerous case — fail-closed is right and is NOT changed — but its refusal
    names the format-skew possibility and reads distinctly from a genuinely
    armed entry. The class, not the instance: this models the next format
    change (whatever its string), not RETIRED specifically.

    A registry that adds a state and leaves entries in it is unlandable when
    the pre-merge gate runs an older build: the lane's own check (newer tool)
    reads clean while the gate (older tool) refuses. Naming the skew turns a
    twenty-minute diagnosis into a two-minute one (#940 applied here)."""

    # A state string this build does not know. Deliberately not RETIRED: the
    # fix must address the CLASS, not the instance, and a fixture that names
    # the current known-but-new state would pass for the wrong reason once the
    # gate build catches up to it.
    FUTURE_STATE = "quarantined"

    def _seed_unknown(self, repo: Path, *, state: str = FUTURE_STATE) -> dict:
        """Write a registry holding one entry in an unknown state.

        Mirrors the lane-state that caused #950: a state a newer build wrote
        and an older gate cannot classify."""
        rp._write_registry(repo, [{
            "path": "router.js", "state": state,
            "injected_sha": "0" * 40, "injected_hint": "future-format",
            "begun_head": _git(repo, "rev-parse", "HEAD"),
        }])
        return {"state": state}

    def test_an_unknown_state_refuses_and_names_the_skew(self, repo, capsys):
        """Direction 1: the production seam broken is check's classification
        loop (dev/redproof.py: the `st not in KNOWN_STATES` branch). An entry
        in an unknown state MUST refuse AND name the format-skew possibility —
        a bare 'refused' is not discriminating and is exactly the #950 bug
        (it reads identical to four genuinely-armed entries)."""
        seeded = self._seed_unknown(repo)
        # Precondition the check depends on: the state really is unknown to
        # this build. A check built on KNOWN_STATES cannot pass this assertion
        # while also classifying the entry — the two are mutually exclusive.
        assert seeded["state"] not in rp.KNOWN_STATES, (
            "fixture precondition: the seeded state must be outside "
            f"KNOWN_STATES={rp.KNOWN_STATES}, or the test proves nothing")
        exit = _check(repo)
        _, err = capsys.readouterr()
        assert exit == 1, "an unknown state MUST be refused (fail-closed, #950)"
        # discriminating referent 1: the unknown state string is named
        assert repr(self.FUTURE_STATE) in err, (
            "the refusal must name the unknown state value, so the next "
            "reader diagnoses the format skew in two minutes, not twenty")
        # discriminating referent 2: the format-skew possibility is named
        assert "cannot read" in err or "cannot classify" in err, (
            "the refusal must name that the tool cannot read the state — "
            "the remedy — not merely the condition (#940)")
        assert "pre-merge tool is reading post-lane data" in err or (
            "pre-merge" in err), err

    def test_the_unknown_refusal_prints_the_denominator(self, repo, capsys):
        """#868: a check that classified N entries and one that classified 0
        must not report alike. The refusal carries 'of <active>' so a reader
        can tell one unknown entry in a one-entry registry from one in forty."""
        self._seed_unknown(repo)
        exit = _check(repo)
        _, err = capsys.readouterr()
        assert exit == 1
        # denominator present: "1 of 1 active" — not a bare "1 ... injection(s)"
        assert "1 of 1 active" in err, err

    def test_the_two_refusals_read_differently(self, repo, capsys):
        """THE discriminating detail (#950): an unknown-state refusal and a
        genuine armed refusal must NOT print alike. Today they do — four
        unknown entries and four genuinely-armed entries produce the identical
        'begun-but-unrestored' message. Flip one byte (unknown → armed) and
        the message must change."""
        # Unknown state first.
        self._seed_unknown(repo)
        exit_unk = _check(repo)
        _, err_unk = capsys.readouterr()
        assert exit_unk == 1
        # Now flip one byte: the SAME entry, state ARMED (genuinely begun but
        # unrestored). This is the production contrast: unknown vs armed.
        entries, _ = rp._read_registry(repo)
        entries[0]["state"] = rp.ARMED
        rp._write_registry(repo, entries)
        exit_arm = _check(repo)
        _, err_arm = capsys.readouterr()
        assert exit_arm == 1
        # Both refuse (fail-closed holds for both), but they differ in wording.
        assert err_unk != err_arm, (
            "the two refusals MUST read differently — the #950 bug is that "
            "an unknown state and a genuine armed entry wear the same words")
        # The discriminating content: the unknown message names the state
        # value and the format-skew possibility; the armed message does
        # neither (it names the path and begun-but-unrestored as the cause).
        assert repr(self.FUTURE_STATE) in err_unk
        assert repr(self.FUTURE_STATE) not in err_arm
        assert "cannot read" in err_unk
        assert "cannot read" not in err_arm

    def test_unknown_is_not_treated_as_restored(self, repo, capsys):
        """Direction 2, the fail-closed invariant: the fix must NOT make an
        unknown state read as RESTORED. If it did, a genuinely-armed entry
        written by a future format would land silently. An unknown entry MUST
        refuse, never pass."""
        self._seed_unknown(repo)
        exit = _check(repo)
        out, err = capsys.readouterr()
        assert exit != 0, (
            "an unknown state must NEVER pass — defaulting unknown to restored "
            "converts a refusal into a silent hole (#950's prohibition)")

    def test_a_near_miss_state_is_also_unknown_not_restored(self, repo, capsys):
        """Direction 2, the attacker-shaped case: a lane writes 'restored '
        (trailing space) or 'Restored' (wrong case). The unknown-state path
        must NOT excuse a real armed entry as a format problem by passing it
        — it refuses. (Whether such an entry SHOULD be refused as unknown vs
        armed is a separate question; the invariant is that it does not PASS.)"""
        for near in ["restored ", "Restored", "RESTORED!", ""]:
            self._seed_unknown(repo, state=near)
            exit = _check(repo)
            capsys.readouterr()  # drain
            assert exit == 1, (
                f"a near-miss state {near!r} must not pass — only an exact "
                f"member of KNOWN_STATES may be classified as restored/armed")

    def test_the_remedy_text_does_not_read_as_permission(self, repo, capsys):
        """Direction 2: the format-skew remedy must never read as permission
        to merge. An attacker who writes an unknown state must not be able to
        quote the message as cover. The refusal states it is not permission."""
        self._seed_unknown(repo)
        exit = _check(repo)
        _, err = capsys.readouterr()
        assert exit == 1
        assert "not permission to merge" in err, (
            "the remedy text must explicitly disclaim being permission")


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


class TestInjectionReachEvidence:
    FAILURE = "route assertion saw the injected false branch"

    def _route_check(self) -> list[str]:
        return [
            sys.executable,
            "-c",
            "from pathlib import Path; "
            "assert 'return true' in Path('router.js').read_text(), "
            f"{self.FAILURE!r}",
        ]

    def test_paired_red_and_restored_run_names_what_caught_the_injection(
            self, repo, capsys):
        _begin(repo, "router.js")
        (repo / "router.js").write_text(
            "export function route() { return false; /* BUG */ }\n")

        assert _observe(repo, "router.js", self.FAILURE, self._route_check()) == 0
        assert _restore(repo, "router.js") == 0
        assert _check(repo, require=1) == 0

        out, err = capsys.readouterr()
        assert not err
        assert "red-proof reach: OK" in out
        assert "caught 1 of 1 registered injection(s)" in out
        # #1038 Finding 2 direction-2 guard: the evidence-artifact count is
        # NON-zero here (1 examined for 1 registered), proving the denominator
        # is derived from reality, not a hardcoded zero that the calm path and
        # this path would both satisfy.
        assert "examined 1 evidence artifact(s) for 1 registered" in out, out
        assert self.FAILURE in out
        entries, _ = rp._read_registry(repo)
        evidence = Path(entries[0]["reach"]["evidence"])
        assert evidence.is_file()
        text = evidence.read_text()
        assert "INJECTED RUN" in text and "RESTORED CONTROL RUN" in text
        assert self.FAILURE in text

    def test_unrelated_failure_does_not_count_as_caught(self, repo, capsys):
        unrelated = "unrelated pre-existing fixture failure"
        command = [sys.executable, "-c", f"raise AssertionError({unrelated!r})"]
        _begin(repo, "router.js")
        (repo / "router.js").write_text("BROKEN\n")

        assert _observe(repo, "router.js", unrelated, command) == 0
        assert _restore(repo, "router.js") == 0
        assert _check(repo, require=1) == 1

        out, err = capsys.readouterr()
        assert "red-proof reach: WARN" in err
        assert "caught 0 of 1 registered injection(s)" in err
        assert "restored control still failed" in err
        assert unrelated in err
        assert "restoration clean" in out

    def test_restored_without_an_observation_is_not_checked(self, repo, capsys):
        _begin(repo, "router.js")
        (repo / "router.js").write_text("BROKEN\n")
        assert _restore(repo, "router.js") == 0

        assert _check(repo, require=1) == 1
        out, err = capsys.readouterr()
        assert "restoration clean" in out
        assert "red-proof reach: DID NOT CHECK" in err
        assert "examined 0 evidence artifact(s) for 1 registered injection(s)" in err

    def test_missing_artifact_cannot_keep_a_caught_verdict(self, repo, capsys):
        _begin(repo, "router.js")
        (repo / "router.js").write_text(
            "export function route() { return false; /* BUG */ }\n")
        assert _observe(repo, "router.js", self.FAILURE, self._route_check()) == 0
        assert _restore(repo, "router.js") == 0
        entries, _ = rp._read_registry(repo)
        Path(entries[0]["reach"]["evidence"]).unlink()

        assert _check(repo, require=1) == 1
        _, err = capsys.readouterr()
        assert "red-proof reach: DID NOT CHECK" in err
        assert "evidence artifact absent/unreadable" in err
        assert "caught 0 of 1 registered injection(s)" in err

    def test_second_registration_does_not_inherit_first_reach(self, repo, capsys):
        _begin(repo, "router.js")
        (repo / "router.js").write_text(
            "export function route() { return false; /* FIRST */ }\n")
        assert _observe(repo, "router.js", self.FAILURE, self._route_check()) == 0
        assert _restore(repo, "router.js") == 0
        capsys.readouterr()

        _begin(repo, "router.js")
        (repo / "router.js").write_text("SECOND BREAK\n")
        assert _restore(repo, "router.js") == 0
        assert _check(repo, require=1) == 1
        _, err = capsys.readouterr()
        assert "red-proof reach: DID NOT CHECK" in err
        assert "caught 1 of 2 registered injection(s)" in err
        assert "0 not caught, 1 not checked" in err


class TestDeletedInjectionIsRestored:
    def test_restore_recreates_a_deleted_target_from_the_printed_snapshot(
            self, repo, capsys):
        """#961 direction 1: the production seam is ``restore``'s absent
        target branch. The expected bytes come from the target before begin,
        independently checked against the exact snapshot path begin prints."""
        target = repo / "router.js"
        original = target.read_bytes()

        assert _begin(repo, "router.js") == 0
        begin_out, _ = capsys.readouterr()
        snapshot_line = next(
            line for line in begin_out.splitlines()
            if "snapshotted original" in line)
        snapshot = Path(snapshot_line.rsplit(" -> ", 1)[1])
        assert snapshot.read_bytes() == original

        target.unlink()
        assert _restore(repo, "router.js") == 0

        assert target.read_bytes() == original
        assert target.read_bytes() == snapshot.read_bytes()
        entries, _ = rp._read_registry(repo)
        assert entries[0]["injected_kind"] == "absent"
        assert entries[0]["injected_sha"] is None
        assert entries[0]["injected_hint"] == "target absent from working tree"

    def test_check_counts_an_absent_kind_as_nonzero_evidence(
            self, repo, capsys):
        _begin(repo, "router.js")
        (repo / "router.js").unlink()
        command = [
            sys.executable, "-c",
            "from pathlib import Path; assert Path('router.js').exists(), "
            "'deleted router was reached'",
        ]
        assert _observe(repo, "router.js", "deleted router was reached", command) == 0
        assert _restore(repo, "router.js") == 0
        capsys.readouterr()

        assert _check(repo, require=1) == 0
        out, _ = capsys.readouterr()

        assert "targets: 0 other target(s), 0 test-like target(s), 1 absent target(s)" in out
        assert "[absent] router.js" in out
        assert "1 injection(s) registered" in out

    def test_check_still_faults_if_a_restored_absent_target_disappears_again(
            self, repo, capsys):
        """#895 invariant: only restore may account for deliberate deletion.
        A later unexplained absence must remain loud, never degrade to clean."""
        _begin(repo, "router.js")
        (repo / "router.js").unlink()
        assert _restore(repo, "router.js") == 0
        (repo / "router.js").unlink()
        capsys.readouterr()

        exit_code = _check(repo, require=1)
        _, err = capsys.readouterr()

        assert exit_code == 2
        assert "registered path 'router.js' is absent" in err
        assert "cannot evaluate its injection" in err

    def test_head_that_deleted_the_target_is_not_resurrected(
            self, repo, capsys):
        """Direction 2: a new HEAD, not the lane's working-tree sabotage,
        removes the file. Restore must fault and leave that deletion intact."""
        assert _begin(repo, "router.js") == 0
        snapshot = rp._snapshot_path(repo, "router.js")
        (repo / "router.js").unlink()
        _git(repo, "add", "-u", "router.js")
        _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit",
             "-qm", "new head deliberately removes router")
        capsys.readouterr()

        exit_code = _restore(repo, "router.js")
        _, err = capsys.readouterr()

        assert exit_code == 2
        assert not (repo / "router.js").exists()
        assert "HEAD no longer holds the snapshotted original" in err
        assert str(snapshot) in err
        assert f"cp -- {snapshot} router.js" in err
        assert f"cmp -- router.js {snapshot}" in err

    def test_absent_expectation_fault_names_the_exact_snapshot_recovery(
            self, repo, capsys):
        _begin(repo, "router.js")
        snapshot = rp._snapshot_path(repo, "router.js")
        (repo / "router.js").unlink()
        (repo / "expectation.txt").write_text("expectation drifted\n")
        capsys.readouterr()

        exit_code = _restore(repo, "router.js")
        _, err = capsys.readouterr()

        assert exit_code == 2
        assert not (repo / "router.js").exists()
        assert "expectation source changed" in err
        assert f"cp -- {snapshot} router.js" in err
        assert f"cmp -- router.js {snapshot}" in err

    def test_delete_then_recreate_different_bytes_is_a_bytes_injection(
            self, repo):
        """Direction 2: transient absence is irrelevant when bytes exist at
        restore time; the ordinary injected-bytes record must still govern."""
        _begin(repo, "router.js")
        target = repo / "router.js"
        target.unlink()
        target.write_bytes(b"RECREATED WITH DIFFERENT BYTES\n")

        assert _restore(repo, "router.js") == 0

        entries, _ = rp._read_registry(repo)
        assert entries[0]["injected_kind"] == "bytes"
        assert entries[0]["injected_sha"] == rp._sha(
            b"RECREATED WITH DIFFERENT BYTES\n")

    def test_history_scan_refuses_a_commit_that_holds_the_absence(
            self, repo, capsys):
        """A deletion injection has no blob sha, but a poisoned branch commit
        must remain visible to the same history gate as byte injections."""
        target = repo / "router.js"
        original = target.read_bytes()
        _git(repo, "switch", "-qc", "lane")
        _begin(repo, "router.js")
        target.unlink()
        assert _restore(repo, "router.js") == 0

        target.unlink()
        _git(repo, "add", "-u", "router.js")
        poisoned = _git(
            repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit",
            "-qm", "commit the recorded absence")
        target.write_bytes(original)
        capsys.readouterr()

        exit_code = _check(repo, require=1, base="master")
        out, err = capsys.readouterr()

        assert poisoned == ""  # commit command succeeded; output is quiet
        assert exit_code == 1
        assert "working tree is clean" in err
        assert "router.js" in err
        assert "target absent from working tree" in err
        assert "1 holding a recorded injection" in out

    def test_unknown_injected_kind_is_refused_not_defaulted_to_safe(
            self, repo, capsys):
        _begin(repo, "router.js")
        (repo / "router.js").write_text("SABOTAGE\n")
        assert _restore(repo, "router.js") == 0
        entries, _ = rp._read_registry(repo)
        entries[0]["injected_kind"] = "future-kind"
        rp._write_registry(repo, entries)
        capsys.readouterr()

        exit_code = _check(repo, require=1)
        _, err = capsys.readouterr()

        assert exit_code == 1
        assert "injected-target kind this build cannot audit" in err
        assert "future-kind" in err


class TestEphemeralRestoredSubject:
    PATH = "fixture/justfile"
    ORIGINAL = b"clean fixture\n"
    INJECTED = b"broken fixture\n"

    def restore_fixture(self, repo: Path) -> Path:
        target = repo / self.PATH
        target.parent.mkdir()
        target.write_bytes(self.ORIGINAL)
        assert _begin(repo, self.PATH) == 0
        target.write_bytes(self.INJECTED)
        command = [
            sys.executable, "-c",
            "from pathlib import Path; "
            "assert Path('fixture/justfile').read_bytes() == "
            "b'clean fixture\\n', 'ephemeral fixture remained injected'",
        ]
        assert _observe(
            repo, self.PATH, "ephemeral fixture remained injected", command) == 0
        assert _restore(repo, self.PATH) == 0
        assert target.read_bytes() == self.ORIGINAL
        return target

    def test_verified_untracked_subject_may_disappear(self, repo, capsys):
        """The tool earns this state while the restored fixture still exists."""
        target = self.restore_fixture(repo)
        entries, _ = rp._read_registry(repo)
        assert entries[0]["state"] == rp.RESTORED_EPHEMERAL
        target.unlink()
        capsys.readouterr()

        exit_code = _check(repo, require=1)
        out, err = capsys.readouterr()

        assert exit_code == 0, (
            "verified ephemeral disappearance must be restoration clean")
        assert err == ""
        assert "check: restoration clean" in out
        assert "1 injection(s) registered" in out
        assert "[other] fixture/justfile (ephemeral subject;" in out

    def test_recreated_injected_subject_is_refused(self, repo, capsys):
        """Direction 2: disappearance cannot hide the injected bytes returning."""
        target = self.restore_fixture(repo)
        target.unlink()
        target.write_bytes(self.INJECTED)
        capsys.readouterr()

        exit_code = _check(repo, require=1)
        _, err = capsys.readouterr()

        assert exit_code == 1
        assert "check: REFUSED — hand-off blocked" in err
        assert "fixture/justfile: working tree STILL MATCHES" in err

    def test_removed_armed_fixture_is_still_unrestored(self, repo, capsys):
        target = repo / self.PATH
        target.parent.mkdir()
        target.write_bytes(self.ORIGINAL)
        assert _begin(repo, self.PATH) == 0
        target.write_bytes(self.INJECTED)
        target.unlink()
        capsys.readouterr()

        exit_code = _check(repo, require=1)
        _, err = capsys.readouterr()

        assert exit_code == 1
        assert "check: REFUSED — 1 of 1 begun-but-unrestored injection(s)" in err

    def test_replacement_with_different_bytes_is_not_the_injection(
            self, repo, capsys):
        target = self.restore_fixture(repo)
        target.unlink()
        target.write_bytes(b"a later, different fixture\n")
        capsys.readouterr()

        exit_code = _check(repo, require=1)
        out, err = capsys.readouterr()

        assert exit_code == 0
        assert err == ""
        assert "check: restoration clean" in out

    def test_replacement_symlink_outside_worktree_faults(
            self, repo, tmp_path, capsys):
        target = self.restore_fixture(repo)
        target.unlink()
        outside = tmp_path / "outside-justfile"
        outside.write_bytes(b"outside\n")
        target.symlink_to(outside)
        capsys.readouterr()

        exit_code = _check(repo, require=1)
        _, err = capsys.readouterr()

        assert exit_code == 2
        assert "check: FAULT — path 'fixture/justfile' resolves outside" in err


class TestExpectationSourcesArePinned:
    """The subject and its expectation must have separate, stable bytes."""

    def test_begin_refuses_an_unpinned_expectation(self, repo, capsys):
        exit = rp.begin(repo, "router.js")
        _, err = capsys.readouterr()
        assert exit == 2
        assert "must declare at least one expectation source" in err

    def test_begin_records_an_independent_expectation_source(self, repo):
        expectation = repo / "independent-expectation.txt"
        expectation.write_text("route must remain true\n")

        assert _begin(repo, "router.js", ("independent-expectation.txt",)) == 0
        entries, _ = rp._read_registry(repo)
        assert entries[0]["expectation_sources"] == [{
            "path": "independent-expectation.txt",
            "sha": rp._sha(expectation.read_bytes()),
        }]

        # Self-referential red-proof precondition: the source we pin is a
        # distinct file whose bytes do not derive from the injected subject.
        (repo / "router.js").write_text("export function route() { return false; }\n")
        _restore(repo, "router.js")
        assert _check(repo) == 0

    def test_begin_refuses_the_injected_file_as_its_expectation(
            self, repo, capsys):
        exit = _begin(repo, "router.js", ("./router.js",))
        _, err = capsys.readouterr()
        assert exit == 2
        assert "expectation source" in err
        assert "injected file" in err
        assert "distinct canonical paths" in err

    def test_restore_refuses_when_expectation_changes_during_injection(
            self, repo, capsys):
        expectation = repo / "independent-expectation.txt"
        original_expectation = "route must remain true\n"
        expectation.write_text(original_expectation)
        assert _begin(repo, "router.js", ("independent-expectation.txt",)) == 0
        (repo / "router.js").write_text("SABOTAGE\n")
        expectation.write_text("route must remain false\n")

        exit = _restore(repo, "router.js")
        _, err = capsys.readouterr()
        assert exit == 2, "changed expectation must refuse during restore"
        assert "expectation source changed during the injection" in err
        assert "independent-expectation.txt" in err

        # Restore the declared expectation, then complete the protocol so the
        # failed proof does not leak an armed entry into sibling tests.
        expectation.write_text(original_expectation)
        assert _restore(repo, "router.js") == 0

    def test_check_refuses_expectation_drift_after_restore(self, repo, capsys):
        expectation = repo / "independent-expectation.txt"
        expectation.write_text("route must remain true\n")
        assert _begin(repo, "router.js", ("independent-expectation.txt",)) == 0
        (repo / "router.js").write_text("SABOTAGE\n")
        assert _restore(repo, "router.js") == 0
        expectation.write_text("route must remain false\n")

        exit = _check(repo)
        _, err = capsys.readouterr()
        assert exit == 1, "check must refuse expectation drift at hand-off"
        assert "expectation source" in err
        assert "not stable across the injection" in err


class TestExpectationDriftNamesTheRearm:
    """#910: an expectation-drift refusal must say the lane did nothing wrong
    and name the forget-and-re-arm remedy. Editing the expectation file
    mid-injection is the natural rhythm (inject -> red -> add a test ->
    restore), and the refusal is correct — but a refusal that does not say
    what to do next reads as "I made a mistake" and pushes a lane to weaken
    its test or skip the re-arm.

    Direction-2 guard (the false-green this repo has landed four tools
    against): a check on a refusal MESSAGE that passes when the refusal no
    longer fires at all. Each test proves the refusal FIRED (the exit code)
    over a REAL drift (the pinned bytes genuinely differ from current), then
    checks the remedy text — so a check that stops detecting drift fails on
    the exit-code assertion before the message is ever read."""

    def test_restore_drift_refusal_names_rearm_and_the_commands(
            self, repo, capsys):
        expectation = repo / "independent-expectation.txt"
        original = "route must remain true\n"
        expectation.write_text(original)
        assert _begin(repo, "router.js", ("independent-expectation.txt",)) == 0
        (repo / "router.js").write_text("SABOTAGE\n")
        # the natural mid-injection edit: add to the expectation file
        expectation.write_text(original + "# a newly added test\n")

        # PRECONDITION: the drift is REAL — pinned bytes differ from current.
        # A refusal over a non-drift proves nothing (#906): the population the
        # check evaluates must be non-empty and the assertion must reach it.
        entries, _ = rp._read_registry(repo)
        pinned = entries[0]["expectation_sources"][0]["sha"]
        assert pinned != rp._sha(expectation.read_bytes()), (
            "no real drift: the refusal would fire over nothing")

        exit = _restore(repo, "router.js")
        _, err = capsys.readouterr()
        # the refusal FIRED (direction-2 guard): exit 2, not a quiet pass
        assert exit == 2, err
        # the drift was evaluated and names the expectation file
        assert "independent-expectation.txt" in err, err
        # the remedy is present — HARDCODED LITERALS, not the production
        # symbol (an expectation drawn from the thing it checks is silent to
        # every tool, #906)
        assert "re-arm" in err.lower(), err
        assert "forget" in err, err
        assert "begin" in err, err
        assert "A rebase can stale the pin even after a clean restore" in err
        assert "repeat that cycle after the final rebase" in err

        # drop the armed entry so it does not leak into sibling tests
        assert rp.forget(repo, "router.js") == 0

    def test_check_drift_refusal_names_rearm_and_the_commands(
            self, repo, capsys):
        expectation = repo / "independent-expectation.txt"
        original = "route must remain true\n"
        expectation.write_text(original)
        assert _begin(repo, "router.js", ("independent-expectation.txt",)) == 0
        (repo / "router.js").write_text("SABOTAGE\n")
        assert _restore(repo, "router.js") == 0
        # drift introduced AFTER restore, caught at hand-off
        expectation.write_text(original + "# a newly added test\n")

        # PRECONDITION: real drift at hand-off time
        entries, _ = rp._read_registry(repo)
        restored = [e for e in entries if e.get("state") == rp.RESTORED][0]
        pinned = restored["expectation_sources"][0]["sha"]
        assert pinned != rp._sha(expectation.read_bytes()), "no real drift"

        exit = _check(repo)
        _, err = capsys.readouterr()
        assert exit == 1, err          # the refusal FIRED (direction-2 guard)
        assert "independent-expectation.txt" in err, err
        assert "re-arm" in err.lower(), err
        assert "forget" in err, err
        assert "begin" in err, err
        assert "A rebase can stale the pin even after a clean restore" in err
        assert "repeat that cycle after the final rebase" in err


class TestUntrackedExpectationWarning:
    """#1088: an untracked expectation is a registration with a scheduled expiry.
    begin WARNs on stdout — the same stream its other output uses — naming the
    consequence, but does not refuse: the fail-closed refusal lives at check
    time (``_read_wt``), not at registration."""

    def test_begin_warns_when_expectation_is_untracked(self, repo, capsys):
        """Direction 1: an untracked expectation source produces a WARNING that
        names the expiry consequence. Before the fix, begin accepted an
        untracked source silently — a registration with a scheduled expiry."""
        scratch = repo / "scratch-expectation.txt"
        scratch.write_text("untracked scratch expectation\n")
        # Explicitly NOT committed — this is the #1100/#1088 failure mode.
        assert _begin(repo, "router.js", ("scratch-expectation.txt",)) == 0
        out, _ = capsys.readouterr()
        assert "WARNING" in out, (
            "begin must warn when an expectation source is untracked — "
            "an untracked expectation is a registration with a scheduled "
            "expiry (#1088)")
        assert "not tracked by git" in out
        assert "will expire" in out, (
            "the warning must name the consequence so a lane can act on it")

    def test_begin_does_not_warn_when_expectation_is_tracked(self, repo, capsys):
        """A tracked expectation source produces NO warning — only untracked
        sources are registrations with a scheduled expiry."""
        tracked = repo / "committed-expectation.txt"
        tracked.write_text("committed expectation\n")
        _git(repo, "add", "committed-expectation.txt")
        _git(repo, "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-qm", "add tracked expectation")
        assert _begin(repo, "router.js",
                      ("committed-expectation.txt",)) == 0
        out, _ = capsys.readouterr()
        assert "WARNING" not in out, (
            "a tracked expectation must not warn — it survives cleanup")


    def test_warning_uses_git_truth_not_path_name(self, repo, capsys):
        """Direction 2: the check fires on ``git ls-files`` truth, not on the
        path NAME looking disposable. A tracked file named like a scratch file
        (``.redproof_expect_*``) does NOT warn — string matching on the name
        would false-positive here."""
        dotted = repo / ".redproof_expect_tracked.txt"
        dotted.write_text("looks disposable but is committed\n")
        _git(repo, "add", ".redproof_expect_tracked.txt")
        _git(repo, "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-qm", "add dotted expectation")
        assert _begin(repo, "router.js",
                      (".redproof_expect_tracked.txt",)) == 0
        out, _ = capsys.readouterr()
        assert "WARNING" not in out, (
            "the untracked check must use git ls-files truth, not string "
            "matching on the path name — a tracked file with a disposable-"
            "looking name is safe (#1088 direction 2)")

    def test_warning_reaches_stdout_not_stderr(self, repo, capsys):
        """Direction 2: the warning goes to stdout (the stream the lane reads
        for begin's other output), NOT to stderr where it would be invisible
        like the failure it replaces."""
        scratch = repo / "scratch-expectation.txt"
        scratch.write_text("untracked\n")
        assert _begin(repo, "router.js", ("scratch-expectation.txt",)) == 0
        out, err = capsys.readouterr()
        assert "will expire" in out, (
            "the warning must reach stdout — begin's other output stream")
        assert "will expire" not in err

    def test_a_tracked_path_containing_spaces_does_not_warn(self, repo, capsys):
        """#1088 contract edge: a tracked expectation whose path contains a
        space must NOT warn. ``_git_tracks`` shells the path to
        ``git ls-files -- <path>`` as one argv element, which finds a spaced
        tracked path; a caller that normalised or split on the space would
        miss it and warn over a file that is in fact tracked.

        Direction 2: assert the helper's OWN return (``True``), not just the
        absence of a warning. A caller that stripped the space before ls-files
        would leave the warning absent for the WRONG reason — only the helper's
        return proves the spaced path reached git intact."""
        spaced = "expectation with spaces.txt"
        (repo / spaced).write_text("spaced but committed\n")
        _git(repo, "add", spaced)
        _git(repo, "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-qm", "add spaced expectation")
        # PRECONDITION: the spaced path is genuinely tracked — derived from
        # git, not assumed, so the case cannot silently become an untracked one
        # (which would make a True assertion pass for the wrong reason).
        assert _git(repo, "ls-files", "--", spaced) == spaced

        # The helper's OWN return: the spaced path reached ls-files and git
        # found it. A normalising caller would leave this False over a tracked
        # file — the discriminating assertion a warning-absence check is not.
        assert rp._git_tracks(repo, spaced) is True, (
            "a tracked path containing a space must be found by ls-files — a "
            "normalising caller would leave this False and the warning absent "
            "for the wrong reason (#1088 direction 2)")

        assert _begin(repo, "router.js", (spaced,)) == 0
        out, _ = capsys.readouterr()
        assert "WARNING" not in out, (
            "a tracked spaced expectation must not warn — it survives cleanup")

    def test_ls_files_failing_returns_none_and_begin_does_not_warn(
            self, repo, tmp_path, monkeypatch, capsys):
        """#1088 contract edge: when ``git ls-files`` itself fails (a
        misbehaving git, a corrupt index), ``_git_tracks`` returns ``None`` —
        NOT ``False`` — and begin proceeds at exit 0 WITHOUT warning and
        WITHOUT refusing. ``None`` means 'the check could not run', which is
        distinct from ``False`` ('the file is untracked'): conflating them
        would warn on every registration on a machine where git misbehaves.

        Direction 2: the failure is forced at the ``git`` INVOCATION — a fake
        git on PATH that exits non-zero for ``ls-files`` and delegates every
        other command to the real binary — not stubbed at a level above
        ``_git_tracks``. Assert the helper's OWN return (``None``) AND that
        non-ls-files git still works, so the proof is the helper's exception
        handling, not the test harness."""
        bin_dir = tmp_path / "fake-git-bin"
        bin_dir.mkdir()
        fake_git = bin_dir / "git"
        # Scans ALL args for `ls-files` so the `-C <root>` prefix redproof's
        # _git leads with does not mask the match; delegates the rest.
        fake_git.write_text(
            "#!/bin/sh\n"
            "for arg in \"$@\"; do\n"
            "  if [ \"$arg\" = ls-files ]; then\n"
            "    echo 'fatal: fake broken git index' >&2\n"
            "    exit 1\n"
            "  fi\n"
            "done\n"
            "exec /usr/bin/git \"$@\"\n")
        fake_git.chmod(0o755)
        import os
        monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ.get('PATH', '')}")

        # The helper's OWN return: ls-files failed at the invocation, _git
        # raised RedproofError, _git_tracks caught it and returned None.
        assert rp._git_tracks(repo, "expectation.txt") is None, (
            "_git_tracks must return None (not False) when ls-files fails — "
            "'could not run' is distinct from 'untracked', and conflating them "
            "would warn on every registration where git misbehaves (#1088)")
        # Non-ls-files git still works: the fake delegates rev-parse to the
        # real binary, proving the failure is SPECIFIC to ls-files (at the
        # invocation), not a blanket stub above _git_tracks. Without this, a
        # fake that broke all git would leave _git_tracks None for the wrong
        # reason and the assertion would prove the harness, not the helper.
        assert rp._git(repo, "rev-parse", "HEAD"), (
            "the fake git must delegate non-ls-files commands — if rev-parse "
            "also failed, the test would prove the harness, not the helper")

        # begin proceeds: None is not False, so the expectation is not added
        # to the untracked list, no warning fires, and there is no refusal.
        assert _begin(repo, "router.js") == 0
        out, _ = capsys.readouterr()
        assert "WARNING" not in out, (
            "begin must not warn when ls-files fails — the check could not "
            "run, not 'the file is untracked' (#1088)")
        assert "will expire" not in out


class TestLaneOwnedExpectationWarning:
    def test_begin_warns_last_when_the_lane_already_changed_the_source(
            self, repo, capsys):
        source = repo / "owned-expectation.txt"
        source.write_text("baseline expectation\n")
        _commit(repo, "owned-expectation.txt", msg="add expectation")
        _git(repo, "checkout", "-qb", "lane")
        source.write_text("lane-owned expectation\n")
        _commit(repo, "owned-expectation.txt", msg="lane changes expectation")

        assert _begin(repo, "router.js", ("owned-expectation.txt",)) == 0
        out, _ = capsys.readouterr()
        warning = out.splitlines()[-1]
        assert "WARNING" in warning, (
            "begin did not warn for owned-expectation.txt:\n" + out)
        assert "owned-expectation.txt" in warning, out
        assert "plausibly part of this lane's work" in warning, out
        assert (
            "re-arm after your last commit to 'owned-expectation.txt'"
            in warning), out

    def test_begin_does_not_warn_for_a_clean_source_the_lane_did_not_touch(
            self, repo, capsys):
        source = repo / "clean-expectation.txt"
        source.write_text("stable expectation\n")
        _commit(repo, "clean-expectation.txt", msg="add expectation")
        _git(repo, "checkout", "-qb", "lane")

        assert _begin(repo, "router.js", ("clean-expectation.txt",)) == 0
        out, _ = capsys.readouterr()
        assert "plausibly part of this lane's work" not in out, out


class TestExpectationStalingCause:
    @staticmethod
    def _arm_and_restore(repo: Path) -> Path:
        source = repo / "mode-expectation.txt"
        source.write_text("baseline expectation\n")
        _commit(repo, "mode-expectation.txt", msg="add expectation")
        _git(repo, "checkout", "-qb", "lane")
        assert _begin(repo, "router.js", ("mode-expectation.txt",)) == 0
        (repo / "router.js").write_text("SABOTAGE\n")
        assert _restore(repo, "router.js") == 0
        return source

    def test_check_names_lane_caused_staling_after_a_lane_commit(
            self, repo, capsys):
        source = self._arm_and_restore(repo)
        capsys.readouterr()
        source.write_text("lane changed expectation after arming\n")
        _commit(repo, "mode-expectation.txt", msg="lane changes expectation")

        assert _check(repo) == 1
        _, err = capsys.readouterr()
        assert "mode-expectation.txt" in err, err
        assert "lane-caused staling" in err, err
        assert "re-arm after your last commit" in err, err
        assert "rebase-caused staling" not in err, err

    def test_check_names_rebase_caused_staling_after_master_moves_the_source(
            self, repo, capsys):
        source = self._arm_and_restore(repo)
        capsys.readouterr()
        _git(repo, "checkout", "master")
        source.write_text("master changed expectation after the lane armed\n")
        _commit(repo, "mode-expectation.txt", msg="master changes expectation")
        _git(repo, "checkout", "lane")
        _git(repo, "rebase", "master")

        assert _check(repo) == 1
        _, err = capsys.readouterr()
        assert "mode-expectation.txt" in err, err
        assert "rebase-caused staling" in err, err
        assert "re-observe the evidence" in err, err
        assert "lane-caused staling" not in err, err

    def test_unrelated_rebase_does_not_take_blame_for_a_lane_source_change(
            self, repo, capsys):
        source = self._arm_and_restore(repo)
        capsys.readouterr()
        _git(repo, "checkout", "master")
        unrelated = repo / "unrelated.txt"
        unrelated.write_text("master moved elsewhere\n")
        _commit(repo, "unrelated.txt", msg="unrelated master change")
        _git(repo, "checkout", "lane")
        source.write_text("lane changed expectation after arming\n")
        _commit(repo, "mode-expectation.txt", msg="lane changes expectation")
        _git(repo, "rebase", "master")

        assert _check(repo) == 1
        _, err = capsys.readouterr()
        assert "lane-caused staling" in err, err
        assert "rebase-caused staling" not in err, err


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
                            "--expectation", "expectation.txt",
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

    def test_check_require_faults_when_none_registered(self, repo, tmp_path):
        """--require > 0 with no registry locatable FAULTs (exit 2), matching
        the coordinator's treatment of an absent registry (#1038 Finding 3).
        A required injection that left no verifiable registry is a fault — the
        proof cannot be verified — not a refusal over a counted population. The
        old named-lane path REFUSED (exit 1) here, disagreeing with the
        coordinator's FAULT (exit 2) for the same facts; both paths now agree."""
        env = self._env(tmp_path)
        r = subprocess.run(["python3", str(CLI_PATH), "check", "--require", "1",
                            "--cwd", str(repo)], capture_output=True, text=True, env=env)
        assert r.returncode == 2, (
            f"an absent registry at --require 1 must FAULT (exit 2) in both "
            f"modes, not REFUSE (exit 1): {r.stdout}{r.stderr}")
        assert "FAULT" in r.stderr, r.stderr
        assert "cannot be verified" in r.stderr, r.stderr


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

    def test_the_commit_holding_the_injection_is_named(
            self, lane, capsys, monkeypatch):
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
        assert "wip(#710): mid red-proof" in err
        assert "return false" in err
        # discriminating: it names the poisoned commit, not every commit
        assert clean[:12] not in err, err
        assert "Committing mid-injection is correct, not the lane's fault" in err

        # Derive the expectation from the independent just recipe and
        # land_lane parser. A literal copied from this refusal would accept a
        # plausible-looking flag that argparse rejects.
        match = re.search(r"`(just land-lane [^`]+)`", err)
        assert match, "refusal did not name a runnable land-lane command"
        template = shlex.split(match.group(1))
        replacements = {
            "<branch>": "cx-example",
            "<tests...>": "test_redproof.py",
        }
        invocation = [replacements.get(arg, arg) for arg in template]
        dry = subprocess.run(
            [invocation[0], "--dry-run", *invocation[1:]],
            cwd=CLI_PATH.parent.parent,
            capture_output=True,
            text=True,
        )
        assert dry.returncode == 0, dry.stdout + dry.stderr
        rendered = (dry.stdout + dry.stderr).strip()
        parser_argv = shlex.split(rendered)
        assert parser_argv[:2] == ["python3", "dev/land_lane.py"], rendered

        parsed = {}

        # Bind against land()'s real signature, captured before the patch
        # below swaps land_lane.land for this double. The double now tracks
        # land()'s parameters: it cannot fall behind a new one (the drift
        # that broke the gate, #1040 — a literal stub lagged main()'s
        # forwarding) and cannot silently accept one land() does not take
        # (signature.bind rejects kwargs land() lacks, so this is not the
        # **kwargs trap). This matches the derive-from-real discipline
        # already applied to the invocation above, closing the one literal
        # that drifted.
        land_sig = inspect.signature(land_lane.land)

        def capture(*args, **kwargs):
            bound = land_sig.bind(*args, **kwargs)
            bound.apply_defaults()
            parsed.update(
                branch=bound.arguments["branch"],
                tests=list(bound.arguments["tests"]),
                base=bound.arguments["base"],
                squash=bound.arguments["squash"],
            )
            return 0

        monkeypatch.setattr(land_lane, "land", capture)
        assert land_lane.main(parser_argv[2:]) == 0
        assert parsed == {
            "branch": "cx-example",
            "tests": ["test_redproof.py"],
            "base": "master",
            "squash": True,
        }
        assert "`<branch>-presquash`" in err
        assert "`Presquash-Ref:`" in err

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


class TestHistoryScanRegistrationBoundary:
    def test_a_pre_begin_pre_fix_commit_is_not_an_armed_injection(
            self, lane, capsys):
        # The canonical direction-1 sabotage restores the pre-fix bytes.  That
        # state legitimately existed in this lane before redproof observed it.
        (lane / "router.js").write_text(
            "export function route() { return false; }\n")
        predecessor = _commit(lane, "router.js", msg="feat(#901): predecessor")
        (lane / "router.js").write_text(
            "export function route() { return Boolean(guard); }\n")
        fixed = _commit(lane, "router.js", msg="fix(#901): actual repair")

        _begin(lane, "router.js")
        (lane / "router.js").write_text(
            "export function route() { return false; }\n")
        _restore(lane, "router.js")

        entries, _ = rp._read_registry(lane)
        assert entries[0]["begun_head"] == fixed
        assert _blob_sha_at(lane, predecessor, "router.js") == entries[0]["injected_sha"]
        rep = rp.scan_history(lane, entries)
        assert rep["commits"] == 2 and rep["blobs_read"] == 2, rep
        assert rep["hits"] == [], (
            "pre-begin predecessor was misclassified as an armed injection: "
            f"{rep['hits']}")

        assert _check(lane) == 0
        out, err = capsys.readouterr()
        assert "restoration clean" in out, out
        assert "REFUSED" not in err, err

    def test_rebase_cannot_move_an_armed_commit_before_registration(
            self, lane, monkeypatch, capsys):
        (lane / "router.js").write_text(
            "export function route() { return true; /* FIXED #901 */ }\n")
        registration_commit = _commit(
            lane, "router.js", msg="fix(#901): state before registration")
        _begin(lane, "router.js")
        entries, _ = rp._read_registry(lane)
        begun_head = entries[0]["begun_head"]
        assert begun_head == registration_commit

        # Authored after begin, but with dates that claim it came decades
        # earlier.  Then rebase the lane so the offending commit has a new
        # object id as well as a deceptive date.
        monkeypatch.setenv("GIT_AUTHOR_DATE", "2000-01-01T00:00:00+00:00")
        monkeypatch.setenv("GIT_COMMITTER_DATE", "2000-01-01T00:00:00+00:00")
        (lane / "router.js").write_text(
            "export function route() { return false; /* ARMED #901 */ }\n")
        poisoned = _commit(lane, "router.js", msg="wip(#901): armed injection")
        _restore(lane, "router.js")
        clean = _commit(lane, "router.js", msg="fix(#901): restore after injection")

        monkeypatch.delenv("GIT_AUTHOR_DATE")
        monkeypatch.delenv("GIT_COMMITTER_DATE")
        _git(lane, "rebase", "--force-rebase", "master")
        rewritten_poisoned = _git(
            lane, "log", "--format=%H", "--grep=^wip(#901): armed injection$")
        assert rewritten_poisoned and rewritten_poisoned != poisoned
        assert _git(lane, "rev-parse", "HEAD") != clean
        assert subprocess.run(
            ["git", "-C", str(lane), "merge-base", "--is-ancestor",
             begun_head, "HEAD"], check=False).returncode == 1

        entries, _ = rp._read_registry(lane)
        rep = rp.scan_history(lane, entries)
        assert len(rep["hits"]) == 1, (
            "rebased post-begin injection escaped the history scan: "
            f"{rep['hits']}")
        assert rep["hits"][0]["commit"] == rewritten_poisoned, rep
        assert _check(lane) == 1
        _, err = capsys.readouterr()
        assert rewritten_poisoned[:12] in err, err
        assert "ARMED #901" in err, err


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

        exit_code = rp.begin(repo, "link.txt", ["expectation.txt"])
        _, err = capsys.readouterr()

        assert exit_code == 2, err
        assert "link.txt" in err, err
        assert "outside the worktree" in err, err

    def test_restore_rechecks_a_path_that_became_an_outside_symlink(
            self, repo, capsys):
        outside = repo.parent / "outside.txt"
        outside.write_text("outside bytes\n")
        assert rp.begin(repo, "router.js", ["expectation.txt"]) == 0
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
        exit_code = rp.begin(repo, "missing/child.txt", ["expectation.txt"])
        _, err = capsys.readouterr()

        assert exit_code == 2, err
        assert "missing/child.txt" in err, err
        assert "does not exist in the working tree" in err, err
        assert "outside the worktree" not in err, err


# ── #694: a reviewer's registry is separate, and check says which it checked ──

class TestRoleKeyedRegistries:
    """THE #694 seam: redproof.py's check must stay truthful across a role
    split. If author and reviewer have separate registries, check must say
    WHICH it checked rather than implying it checked both (#671, #651)."""

    def test_check_names_the_role_it_examined_when_clean(self, repo, capsys):
        """check's clean verdict must carry the role — 'check: clean' that
        omits the role implies it examined a registry it might not have."""
        _begin(repo, "router.js")
        (repo / "router.js").write_text("SABOTAGE\n")
        _restore(repo, "router.js")
        exit = _check(repo)
        out, _ = capsys.readouterr()
        assert exit == 0
        assert "role: author" in out, (
            "check must name the role it examined — 'clean' without 'role: "
            "author' implies it checked a registry it might not have (#651)")

    def test_check_names_the_role_in_calm_zero(self, repo, capsys):
        """Even calm-zero must carry the role: a calm reviewer says nothing
        about the author's registry."""
        exit = _check(repo)
        out, _ = capsys.readouterr()
        assert exit == 0
        assert "role: author" in out

    def test_author_and_reviewer_have_separate_registries(self, repo,
                                                          monkeypatch):
        """THE #694 core: two roles in one worktree get separate registries,
        so a reviewer's begin/restore cannot touch the author's entries."""
        # author registers an injection
        monkeypatch.delenv(rp._ls.ROLE_ENV, raising=False)
        _begin(repo, "router.js")
        (repo / "router.js").write_text("SABOTAGE\n")
        _restore(repo, "router.js")
        author_entries, _ = rp._read_registry(repo)
        assert len(author_entries) == 1, "author should have 1 entry"

        # reviewer — separate registry, sees nothing
        monkeypatch.setenv(rp._ls.ROLE_ENV, "reviewer")
        reviewer_entries, source = rp._read_registry(repo)
        assert reviewer_entries == [], (
            "reviewer's registry must be empty — separate from author's")
        assert source == "absent"

    def test_a_reviewer_can_read_the_authors_evidence(self, repo, monkeypatch):
        """#694 constraint: the author's directory stays READABLE by the
        reviewer. Isolating by hiding would break the review."""
        monkeypatch.delenv(rp._ls.ROLE_ENV, raising=False)
        _begin(repo, "router.js")
        # the author's snapshot file exists
        author_snap = rp._snapshot_path(repo, "router.js")
        assert author_snap.exists()

        # reviewer can resolve and read it via author_dir
        monkeypatch.setenv(rp._ls.ROLE_ENV, "reviewer")
        author_ev = rp._ls.author_dir(repo, sub=rp.SUB, create=False)
        snap_rel = author_snap.relative_to(
            rp._ls.lane_scratch_dir(repo, sub=rp.SUB, role="author",
                                    create=False))
        # the snapshot is under the AUTHOR's dir, which the reviewer can reach
        assert (author_ev / snap_rel).exists(), (
            "reviewer must be able to read the author's evidence — "
            "a fix that isolates by hiding has broken the review")


# ── #895: a coordinator's audit must SEE a lane's registry from outside it ──

class TestCoordinatorAuditSeesTheLane:
    """THE #895 red run. #870 keyed lane scratch on a dispatcher-generated
    DREAMWORK_LANE_ID that is UNSET in the coordinator's shell, so the
    coordinator's `check` resolved an empty scratch and printed an all-clear
    over whatever the lane's real state was. Two halves, both load-bearing:

    (1) Direction 2 — the whole point: a lane leaves an ARMED injection on disk
        (#863's exact state) and the coordinator's audit must REFUSE naming it,
        not print "no evidence".
    (2) The blind case must not read as an all-clear: "no evidence" and "I could
        not read this lane's registry" are opposite facts and were one sentence.
    """

    def _as_coordinator(self, monkeypatch):
        """Drop the launch identity, modelling the coordinator's shell (#870)."""
        monkeypatch.delenv(rp._ls.IDENTITY_ENV, raising=False)

    def test_an_armed_injection_in_a_lane_is_refused_by_the_coordinator(
            self, repo, monkeypatch, capsys):
        """DIRECTION 2 — reproducible, not hypothetical. A lane (token set)
        begins an injection and leaves it ARMED on disk. The coordinator (token
        unset) audits the worktree. It must REFUSE naming the armed path —
        exactly #863's state, where this refusal was the only reason two armed
        injections were caught."""
        _begin(repo, "router.js")          # armed, never restored
        # PRECONDITION: the lane genuinely armed an injection under its token.
        lane_registry = rp._registry_path(repo)
        assert lane_registry.exists(), "fixture did not arm an injection"
        armed_before = [e for e in rp._read_registry(repo)[0]
                        if e.get("state") == rp.ARMED]
        assert armed_before, "fixture's armed entry is missing — test proves nothing"

        self._as_coordinator(monkeypatch)
        # The coordinator resolves a DIFFERENT, tokenless path by default:
        assert rp._registry_path(repo) != lane_registry

        exit = _check(repo)
        _, err = capsys.readouterr()
        assert exit == 1, (
            f"a coordinator's audit MUST refuse an armed injection (#863); "
            f"got exit {exit}, stderr={err!r}")
        # discriminating: the armed PATH is named, and it names the identity dir
        # the injection came from — a bare 'refused' is not enough.
        assert "router.js" in err, err
        assert "unrestored" in err or "armed" in err, err

    def test_a_restored_lane_is_seen_as_clean_not_as_no_evidence(
            self, repo, monkeypatch, capsys):
        """The #888 scenario: a lane registered + restored injections, and the
        coordinator's audit printed "no evidence" — read as 'died before
        red-proofing'. The lane had done everything. Enumeration must FIND the
        registry and report restoration clean."""
        _begin(repo, "router.js")
        (repo / "router.js").write_text("SABOTAGE\n")
        _restore(repo, "router.js")
        # PRECONDITION: the lane has a restored entry under its token.
        restored = [e for e in rp._read_registry(repo)[0]
                    if e.get("state") == rp.RESTORED]
        assert restored, "fixture did not restore — test proves nothing"

        self._as_coordinator(monkeypatch)
        exit = _check(repo)
        out, _ = capsys.readouterr()
        assert exit == 0, out
        # discriminating: "restoration clean", NOT "no evidence"
        assert "restoration clean" in out, out
        assert "no evidence" not in out, (
            "the coordinator printed 'no evidence' over a lane that restored — "
            "the exact #888/#895 misread")

    def test_no_require_absent_registry_is_expected_not_a_fault(
            self, repo, monkeypatch, capsys):
        """#955: a coordinator auditing a worktree that owes no red-proof and
        registered nothing must PASS, not fault — the doc-only lane case the
        gate was refusing (#949's unfixed second half). The SAME fixture under
        --require 1 must still FAULT. That discriminating pair (one fixture,
        two flags, two verdicts) is the fix's whole claim: absent-with-0-
        required is expected; absent-with-1-required is unverifiable.

        #895's invariant still holds: the blind pass must read DIFFERENTLY
        from a registry-found-clean verdict, so a reader cannot take a sweep
        that audited nothing for a sweep that audited something."""
        self._as_coordinator(monkeypatch)
        # PRECONDITION: no identity dirs, no legacy registry — nothing to find.
        assert rp._ls.lane_identity_dirs(repo) == []
        assert not rp._redproof_dir(repo, "", rp._role(repo)).exists()

        # Flag 0: PASS. An absent registry is the expected state for a lane
        # that owes nothing.
        exit0 = _check(repo, require=0)
        out0, _ = capsys.readouterr()
        assert exit0 == 0, (
            "a coordinator that owes no red-proof and registered nothing must "
            "PASS, not fault (#955/#932): " + out0)
        # The pass must SAY WHY (0 required, none registered) and carry the
        # denominator, so it cannot read as a clean sweep of a population.
        assert "0 required" in out0, out0
        assert "none registered" in out0, out0
        assert "audited 0 registry/ies across 0 launch-identity dir(s)" in out0, out0
        # #895/#932: it must NOT read as an all-clear or a restoration verdict.
        assert "no evidence" not in out0, (
            "the pass printed the calm-zero 'no evidence' sentence over a "
            "population it did not sweep")
        assert "restoration clean" not in out0, out0

        # Flag 1, SAME fixture: FAULT. A required injection cannot be verified
        # when no registry can be located (#895's invisible-injection case).
        exit1 = _check(repo, require=1)
        _, err1 = capsys.readouterr()
        assert exit1 == 2, (
            "a coordinator that required an injection but located no registry "
            "must FAULT, not pass (#671)")
        assert "1 injection(s) were required" in err1, err1
        assert "cannot be verified" in err1, err1
        assert "Produce a fresh causal proof" in err1, err1
        assert "do not invent an unrelated injection" in err1, err1
        # THE discrimination: one fixture, two flags, two different verdicts.
        assert exit0 != exit1, (
            "the two flags produced the same verdict — the fix does not "
            "discriminate require==0 from require>=1 on an absent registry")

    def test_an_identity_that_ran_but_left_no_registry_passes_at_require_zero(
            self, repo, monkeypatch, capsys):
        """#955/#1038: a launch identity provably ran here (its dir exists)
        but left no redproof registry — because the lane owed no injection and
        never called begin. A doc-only lane that wrote lane-scratch evidence
        (creating its identity dir) must PASS at --require 0: nothing was
        required, none was expected, and an absent registry is the expected
        state, NOT a fault. The old behavior faulted here independently of
        --require, which is #949's unfixed second half.

        DIRECTION 2 — the paired assertion that stops this being an opt-out: the
        SAME fixture under --require 1 must still FAULT. A lane that changed real
        code and skipped its injection cannot pass by simply never creating a
        registry; the exemption is conditional on zero injections being
        REQUIRED, the fact land_lane computes from the diff and passes here.

        Why identity_dirs is not a hiding-armed-injection signal: an armed
        injection lives INSIDE registry.json, and this block's precondition is
        that NO registry.json exists anywhere this audit can reach. So no armed
        entry can be on disk under any discoverable identity; identity_dirs only
        means the lane wrote other scratch, which is unrelated to red-proof."""
        # A lane ran under an identity and used lane scratch (creating its dir)
        # but never called redproof begin, so no registry exists.
        monkeypatch.setenv(rp._ls.IDENTITY_ENV, "ran-but-no-registry-1038")
        rp._ls.lane_scratch_dir(repo, sub="snap")  # creates the identity dir
        monkeypatch.delenv(rp._ls.IDENTITY_ENV, raising=False)  # coordinator
        # PRECONDITION: an identity dir exists, but no redproof registry does.
        assert len(rp._ls.lane_identity_dirs(repo)) == 1
        assert not rp._redproof_dir(repo, "", rp._role(repo)).exists()

        # Flag 0: PASS. Nothing was required; an absent registry is expected.
        exit0 = _check(repo, require=0)
        out0, _ = capsys.readouterr()
        assert exit0 == 0, (
            "a lane that ran but owed no red-proof must PASS at --require 0, not "
            "fault — an absent registry is the expected state when nothing was "
            "required (#1038/#949 second half): " + out0)
        # State the denominator and the zero that is explained, not a bare pass.
        assert "0 required" in out0, out0
        assert "none registered" in out0, out0
        assert "1 launch-identity dir(s)" in out0, out0
        # #895/#932: must NOT read as an all-clear, a restoration verdict, or
        # the calm-zero 'no evidence' sentence over a population not swept.
        assert "restoration clean" not in out0, out0
        assert "no evidence" not in out0, out0

        # Flag 1, SAME fixture: FAULT. A required injection cannot be verified
        # when no registry can be located (#671/#895) — the gate stays closed.
        exit1 = _check(repo, require=1)
        _, err1 = capsys.readouterr()
        assert exit1 == 2, (
            "a coordinator that required an injection but located no registry "
            "must still FAULT even when an identity ran here — the exemption is "
            "conditional on zero being required (#1038)")
        assert "1 injection(s) were required" in err1, err1
        assert "cannot be verified" in err1, err1
        # THE discrimination: one fixture, two flags, two different verdicts.
        assert exit0 != exit1, (
            "the two flags produced the same verdict — the fix does not "
            "discriminate require==0 from require>=1 on a registry-less "
            "identity dir, and a require==0-only test would pass on a build "
            "that exempts every lane")

    def test_an_unreadable_registry_is_not_absence_and_faults_at_require_zero(
            self, repo, monkeypatch, capsys, tmp_path):
        """#1038 Finding 1: a registry that is PRESENT but UNREADABLE (a
        permission-denied parent dir) must FAULT even at --require 0, not
        report the calm zero. ``Path.exists()`` swallows ``OSError`` and
        returns False when the parent is unreachable, so the old code treated
        inaccessibility as absence — inverting #1038's original error rather
        than removing it. #136 keeps three facts distinct: nothing-required,
        nothing-found, could-not-be-read; "I could not determine whether this
        exists" is the third and must fault.

        This is a DIFFERENT code path from malformed-JSON unreadability: the
        malformed path reaches the JSON decoder; the permission path is
        blocked at the read, before any parse. The fixture makes the path
        genuinely inaccessible (``exists()`` returns False), not merely
        invalid, and asserts that precondition before the verdict."""
        import os
        monkeypatch.setenv(rp._ls.IDENTITY_ENV, "unreadable-registry-1038")
        rp._ls.lane_scratch_dir(repo, sub="snap")  # creates the identity dir
        monkeypatch.delenv(rp._ls.IDENTITY_ENV, raising=False)  # coordinator
        role = rp._role(repo)
        idirs = rp._ls.lane_identity_dirs(repo)
        assert len(idirs) == 1, "precondition: one identity dir exists"
        # A registry.json exists but its parent dir is unreadable.
        reg = rp._redproof_dir(repo, idirs[0].name, role) / "registry.json"
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text("[]")
        os.chmod(reg.parent, 0o000)
        try:
            # PRECONDITION (the brief insists): verify the fixture actually
            # reproduces exists() == False — on a filesystem that ignores mode
            # bits (or run as root) this would not hold and the test would
            # prove nothing.
            assert not reg.exists(), (
                "fixture does not reproduce the precondition — exists() must "
                "return False for a permission-denied parent; if it does not, "
                "the test runs under root or a mode-ignoring filesystem and "
                "proves nothing")
            exit = _check(repo, require=0)
            _, err = capsys.readouterr()
            assert exit == 2, (
                "an unreadable registry must FAULT at --require 0, not report "
                "the calm zero — inaccessibility is not absence (#136/#1038): "
                + err)
            assert "could not be read" in err, err
            assert "not confirmed absent" in err, err
        finally:
            os.chmod(reg.parent, 0o755)  # restore so cleanup can remove it

    def test_lane_flag_audits_a_named_identity_exactly(
            self, repo, monkeypatch, capsys):
        """`--lane <token>` resolves the named launch identity's registry
        exactly, even from the coordinator's shell (no env)."""
        _begin(repo, "router.js")
        (repo / "router.js").write_text("SABOTAGE\n")
        _restore(repo, "router.js")
        token = "fixture-lane-aa895"

        self._as_coordinator(monkeypatch)
        exit = _check(repo, lane=token)
        out, _ = capsys.readouterr()
        assert exit == 0, out
        assert "restoration clean" in out, out


# ── #955: --require 0 governs the minimum count, never the validity ──

class TestRequireZeroDoesNotExcuseInvalidEntries:
    """#955 direction 2: the relaxation lets an ABSENT registry pass at
    --require 0, but it must NOT let a registry that EXISTS with armed or
    unknown-state entries pass. --require governs the minimum COUNT, never the
    VALIDITY of what is on disk: a doc-only lane that left an injection armed
    is still wrong. The pass lives entirely inside the blind case (NO registry
    exists), so an entry — which lives IN a registry — can never reach it; an
    armed or unknown entry is refused on the normal path regardless of require.
    These tests pin that invariant and would fail if the relaxation were keyed
    on require==0 alone rather than on no-registry-exists."""

    def test_an_armed_entry_is_refused_even_at_require_zero(
            self, repo, monkeypatch, capsys):
        """A lane left an injection ARMED on disk. Even at --require 0 it must
        REFUSE — the audit found the registry and it holds an incomplete proof.
        This is #863's exact state, and it is the case the relaxation must
        never reach: a registry EXISTS, so the blind-case pass cannot fire."""
        _begin(repo, "router.js")          # armed, never restored
        # PRECONDITION: a registry exists and holds an armed entry — so the
        # blind case (no registry) cannot be the path taken.
        armed_before = [e for e in rp._read_registry(repo)[0]
                        if e.get("state") == rp.ARMED]
        assert armed_before, "no armed entry — the refusal would prove nothing"

        self._drop_identity(monkeypatch)
        exit = _check(repo, require=0)
        _, err = capsys.readouterr()
        assert exit == 1, (
            "an armed entry must REFUSE at --require 0 — the relaxation is for "
            "an absent registry, not for one holding an armed injection")
        assert "router.js" in err, err
        assert "unrestored" in err or "armed" in err, err

    def test_an_unknown_state_entry_is_refused_even_at_require_zero(
            self, repo, monkeypatch, capsys):
        """A registry holds an entry whose state this build cannot read (#950).
        At --require 0 it must still REFUSE — fail-closed is unchanged, and an
        unknown state is never excused as 'nothing required'."""
        rp._write_registry(repo, [{
            "path": "router.js", "state": "quarantined",
            "injected_sha": "0" * 40, "injected_hint": "future-format",
            "begun_head": _git(repo, "rev-parse", "HEAD"),
        }])
        assert "quarantined" not in rp.KNOWN_STATES  # precondition: unknown

        self._drop_identity(monkeypatch)
        exit = _check(repo, require=0)
        _, err = capsys.readouterr()
        assert exit == 1, (
            "an unknown-state entry must REFUSE at --require 0 — fail-closed "
            "is not relaxed by the require==0 path (#950)")
        assert "quarantined" in err, err

    @staticmethod
    def _drop_identity(monkeypatch):
        monkeypatch.delenv(rp._ls.IDENTITY_ENV, raising=False)


class TestCoordinatorModeBlindCaseViaCli:
    """#955: the merge gate (dev/land_lane.py) invokes check as a CLI
    subprocess with DREAMWORK_LANE_ID popped and DREAMWORK_LANE_ROLE=author,
    against the lane worktree, passing --require <derived>. The CLI path must
    reach the same blind-case verdicts the in-process tests assert, so a
    doc-only lane (require 0, no registry) lands and a lane that owed a proof
    (require 1) does not."""

    def test_require_zero_on_a_no_registry_worktree_passes_via_cli(
            self, repo, tmp_path):
        env = dict(__import__("os").environ)
        env["REDPROOF_SCRATCH_ROOT"] = str(tmp_path / "cli-scratch")
        env.pop(rp._ls.IDENTITY_ENV, None)
        env[rp._ls.ROLE_ENV] = rp._ls.ROLE_AUTHOR
        r = subprocess.run(
            ["python3", str(CLI_PATH), "check", "--cwd", str(repo),
             "--require", "0"],
            capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stderr
        assert "0 required" in r.stdout, r.stdout
        assert "none registered" in r.stdout, r.stdout
        assert "NOT a verification of restoration" in r.stdout, r.stdout
        # #1038 Finding 2: the evidence-artifact denominator is printed on the
        # calm path so a reader can tell "zero examined because zero were owed"
        # from "zero examined because the probe did nothing".
        assert "examined 0 evidence artifact(s) for 0 registered" in r.stdout, (
            r.stdout)

    def test_require_one_on_a_no_registry_worktree_faults_via_cli(
            self, repo, tmp_path):
        env = dict(__import__("os").environ)
        env["REDPROOF_SCRATCH_ROOT"] = str(tmp_path / "cli-scratch")
        env.pop(rp._ls.IDENTITY_ENV, None)
        env[rp._ls.ROLE_ENV] = rp._ls.ROLE_AUTHOR
        r = subprocess.run(
            ["python3", str(CLI_PATH), "check", "--cwd", str(repo),
             "--require", "1", "--carry-forward"],
            capture_output=True, text=True, env=env)
        assert r.returncode == 2, r.stdout + r.stderr
        assert "1 injection(s) were required" in r.stderr, r.stderr
        assert "coordinator's brief must name" in r.stderr, r.stderr
        assert "same carried production path" in r.stderr, r.stderr
        assert "same expectation" in r.stderr, r.stderr
        assert "same discriminating test" in r.stderr, r.stderr
        assert "prior worktree location for use as `--cwd`" in r.stderr, r.stderr

    def test_adoption_is_not_a_cli_proof_path(self, repo, tmp_path):
        """A candidate-authored foreign registry has no adoption entrypoint."""
        env = dict(__import__("os").environ)
        env["REDPROOF_SCRATCH_ROOT"] = str(tmp_path / "cli-scratch")
        r = subprocess.run(
            ["python3", str(CLI_PATH), "adopt", "--cwd", str(repo),
             "--from-registry", str(tmp_path / "forged-registry.json")],
            capture_output=True, text=True, env=env)

        assert r.returncode == 2, r.stdout + r.stderr
        assert "invalid choice: 'adopt'" in r.stderr, r.stderr

    def test_named_lane_absent_registry_agrees_with_coordinator_both_flags(
            self, repo, tmp_path):
        """#1038 Finding 3: --lane (named-lane mode) with an absent registry
        must agree with the coordinator on the SAME facts. Two code paths
        answering one question differently is how the next version of this bug
        is born. The old named-lane path REFUSED (exit 1) at require>0 where
        the coordinator FAULTs (exit 2), and printed 'no evidence' at require==0
        without '0 required' or the audit denominators. Both flags now match.

        Direction 2 — the paired negative that stops this gutting the gate: a
        required injection with no verifiable registry still faults (exit 2),
        NOT a calm pass; the agreement is in the FAULT direction, never a
        relaxation toward exit 0."""
        env = dict(__import__("os").environ)
        env["REDPROOF_SCRATCH_ROOT"] = str(tmp_path / "cli-scratch-f3")
        env.pop(rp._ls.IDENTITY_ENV, None)   # coordinator's shell: no own token
        env[rp._ls.ROLE_ENV] = rp._ls.ROLE_AUTHOR
        lane_token = "named-absent-1038f3"
        # require==0: calm zero, exit 0, with '0 required' + evidence denominator
        r0 = subprocess.run(
            ["python3", str(CLI_PATH), "check", "--cwd", str(repo),
             "--lane", lane_token, "--require", "0"],
            capture_output=True, text=True, env=env)
        assert r0.returncode == 0, r0.stdout + r0.stderr
        assert "0 required" in r0.stdout, r0.stdout
        assert "examined 0 evidence artifact(s) for 0 registered" in r0.stdout, (
            r0.stdout)
        assert "NOT a verification of restoration" in r0.stdout, r0.stdout
        # require==1, SAME facts: FAULT (exit 2), matching the coordinator —
        # NOT the old REFUSED (exit 1). The gate does not relax.
        r1 = subprocess.run(
            ["python3", str(CLI_PATH), "check", "--cwd", str(repo),
             "--lane", lane_token, "--require", "1"],
            capture_output=True, text=True, env=env)
        assert r1.returncode == 2, (
            f"named-lane absent registry at require>0 must FAULT (exit 2), "
            f"agreeing with the coordinator — not REFUSE (exit 1): "
            f"{r1.stdout}{r1.stderr}")
        assert "FAULT" in r1.stderr, r1.stderr
        assert "cannot be verified" in r1.stderr, r1.stderr
        # THE discrimination: one fixture, two flags, two verdicts — and the
        # require>0 verdict (2) matches what the coordinator produces.
        assert r0.returncode != r1.returncode


class TestObserveRemainderOptionGuard:
    @staticmethod
    def _run(repo: Path, env: dict[str, str], *args: str):
        return subprocess.run(
            ["python3", str(CLI_PATH), "--cwd", str(repo), *args],
            capture_output=True, text=True, env=env)

    def test_swallowed_lane_refuses_and_names_the_token(self, repo, tmp_path):
        env = dict(__import__("os").environ)
        env["REDPROOF_SCRATCH_ROOT"] = str(tmp_path / "scratch-989")

        result = self._run(
            repo, env, "observe", "router.js", "--failure", "not reached",
            "--command", sys.executable, "-c", "raise SystemExit(0)",
            "--lane", "cx-989lane")

        assert result.returncode == 2, result.stdout + result.stderr
        assert "observe: FAULT" in result.stderr, result.stderr
        assert "swallowed token '--lane'" in result.stderr, result.stderr
        assert "before --command" in result.stderr, result.stderr
        assert "command's `--` delimiter" in result.stderr, result.stderr

    def test_command_may_end_with_carry_forward_as_consumer_data(
            self, repo, tmp_path):
        """The check/handoff affordance must not reserve a pytest argument."""
        env = dict(__import__("os").environ)
        env["REDPROOF_SCRATCH_ROOT"] = str(tmp_path / "scratch-1171")
        lane = "cx-1171-command-data"
        armed = self._run(
            repo, env, "begin", "router.js", "--lane", lane,
            "--expectation", "expectation.txt")
        assert armed.returncode == 0, armed.stdout + armed.stderr
        (repo / "router.js").write_text("CARRY FORWARD COMMAND SABOTAGE\n")
        command_dir = tmp_path / "command-bin"
        command_dir.mkdir()
        pytest_command = command_dir / "pytest"
        pytest_command.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' 'carry-forward consumer argument reached' >&2\n"
            "exit 1\n",
            encoding="utf-8",
        )
        pytest_command.chmod(0o755)
        env["PATH"] = f"{command_dir}{os.pathsep}{env['PATH']}"

        result = self._run(
            repo, env, "observe", "router.js", "--lane", lane,
            "--failure", "carry-forward consumer argument reached",
            "--command", "pytest", "--carry-forward")

        assert result.returncode == 0, result.stdout + result.stderr
        assert "swallowed token" not in result.stderr, result.stderr
        restored = self._run(
            repo, env, "restore", "router.js", "--lane", lane)
        assert restored.returncode == 0, restored.stdout + restored.stderr

    def test_carry_forward_is_not_a_redproof_option_for_begin(
            self, repo, tmp_path):
        env = dict(__import__("os").environ)
        env["REDPROOF_SCRATCH_ROOT"] = str(tmp_path / "scratch-1171-scope")

        result = self._run(
            repo, env, "begin", "router.js", "--expectation",
            "expectation.txt", "--carry-forward")

        assert result.returncode == 2, result.stdout + result.stderr
        assert (
            "--carry-forward is valid only for check and handoff"
            in result.stderr
        ), result.stderr

    def test_guard_derives_options_and_honours_the_command_escape(self):
        parser = rp._parser()
        parser.add_argument("--future-option-989")
        escaped = rp._parse_args(parser, [
            "observe", "router.js", "--command", "grep", "--", "--lane",
            "somefile"])

        assert escaped.command == ["grep", "--", "--lane", "somefile"]
        assert rp._swallowed_self_option(parser, escaped.command) is None
        assert rp._swallowed_self_option(
            parser, ["consumer", "--", "--cwd"]) is None
        assert rp._swallowed_self_option(
            parser, ["consumer", "--cwd"]) == ("--cwd", "--cwd")
        assert rp._swallowed_self_option(
            parser, ["consumer", "--lan"]) == ("--lan", "--lane")
        assert rp._swallowed_self_option(
            parser, ["consumer", "--future-option-989"]) == (
                "--future-option-989", "--future-option-989")

    def test_lane_before_command_is_not_part_of_the_payload(self):
        parser = rp._parser()
        args = parser.parse_args([
            "observe", "router.js", "--lane", "cx-989lane", "--command",
            "grep", "needle", "somefile"])

        assert args.lane == "cx-989lane"
        assert args.command == ["grep", "needle", "somefile"]
        assert rp._swallowed_self_option(parser, args.command) is None

    def test_empty_registry_names_its_path_and_population(
            self, repo, tmp_path, monkeypatch):
        scratch = tmp_path / "scratch-989"
        monkeypatch.setenv("REDPROOF_SCRATCH_ROOT", str(scratch))
        monkeypatch.setattr(rp._ls, "SCRATCH_ROOT", scratch)
        env = dict(__import__("os").environ)
        lane = "empty-lane-989"
        expected_registry = rp._registry_path(repo, lane)

        result = self._run(
            repo, env, "observe", "router.js", "--lane", lane,
            "--failure", "not reached", "--command", sys.executable, "-c",
            "raise SystemExit(0)")

        assert result.returncode == 2, result.stdout + result.stderr
        assert str(expected_registry) in result.stderr, result.stderr
        assert "population=0" in result.stderr, result.stderr


class TestReachRunEnvPrefix:
    """#1119: leading ``VAR=value`` tokens run as shell env assignments, not
    as a confusing ``could not execute 'CI='`` exit 127.

    The real trap: ``subprocess.run`` with a list does not invoke a shell, so
    a leading env-prefix was treated as the executable name. ``_reach_run``
    now strips leading ``VAR=value`` tokens and merges them into the child
    environment.
    """

    def test_is_env_assignment_edges(self):
        assert rp._is_env_assignment("CI=")
        assert rp._is_env_assignment("FOO_BAR=baz")
        assert rp._is_env_assignment("LANG=C.UTF-8")
        assert not rp._is_env_assignment("python3")
        assert not rp._is_env_assignment("--lane")
        assert not rp._is_env_assignment("=foo")
        assert not rp._is_env_assignment("1foo=bar")
        assert not rp._is_env_assignment("test.py")
        assert not rp._is_env_assignment("--command")

    def test_env_prefix_runs(self, tmp_path):
        code, out = rp._reach_run(tmp_path, [
            "CI=1", sys.executable, "-c",
            "import os; print('CI=' + os.environ['CI'])"])
        assert code == 0, out
        assert "CI=1" in out

    def test_multiple_env_prefixes(self, tmp_path):
        code, out = rp._reach_run(tmp_path, [
            "CI=1", "VERBOSE=yes", sys.executable, "-c",
            "import os; print(os.environ['CI'] + os.environ['VERBOSE'])"])
        assert code == 0, out
        assert "1yes" in out

    def test_inherited_env_preserved(self, tmp_path, monkeypatch):
        monkeypatch.setenv("INHERITED_1119", "kept")
        code, out = rp._reach_run(tmp_path, [
            "CI=1", sys.executable, "-c",
            "import os; print(os.environ['INHERITED_1119'])"])
        assert code == 0, out
        assert "kept" in out

    def test_no_env_prefix_unchanged(self, tmp_path):
        code, out = rp._reach_run(tmp_path, [
            sys.executable, "-c", "print('plain')"])
        assert code == 0, out
        assert "plain" in out

    def test_env_only_no_executable_is_clear_error(self, tmp_path):
        code, out = rp._reach_run(tmp_path, ["CI=1", "VERBOSE=1"])
        assert code == 127, out
        assert "no executable" in out

    def test_command_with_dashprefixed_tokens_unaffected(self, tmp_path):
        # A command whose own argv includes --prefixed tokens after the
        # executable must not be confused with env assignments: _reach_run
        # only strips LEADING VAR= tokens.
        code, out = rp._reach_run(tmp_path, [
            sys.executable, "--version"])
        assert code == 0, out

    def test_wrong_order_with_env_prefix_refused_not_127(self, repo, tmp_path):
        """Wrong order (--lane after --command) with CI= prefix: #989 catches
        the swallowed --lane as a FAULT exit 2, NOT the confusing exit 127."""
        env = dict(__import__("os").environ)
        env["REDPROOF_SCRATCH_ROOT"] = str(tmp_path / "scratch-1119w")
        result = subprocess.run(
            ["python3", str(CLI_PATH), "--cwd", str(repo),
             "observe", "router.js", "--failure", "x",
             "--command", "CI=1", sys.executable, "-c", "pass",
             "--lane", "cx-1119w"],
            capture_output=True, text=True, env=env)
        assert result.returncode == 2, result.stdout + result.stderr
        assert "swallowed token '--lane'" in result.stderr, result.stderr

    def test_observe_with_env_prefix_runs_through_cli(self, repo, tmp_path):
        """The brief's required explicit test: a CI= ... invocation runs
        end-to-end through observe (correct order: --lane before --command)."""
        env = dict(__import__("os").environ)
        env["REDPROOF_SCRATCH_ROOT"] = str(tmp_path / "scratch-1119cli")
        lane = "cx-1119env"

        def run(*a):
            return subprocess.run(
                ["python3", str(CLI_PATH), "--cwd", str(repo), *a],
                capture_output=True, text=True, env=env)

        begin = run("begin", "router.js", "--expectation", "expectation.txt",
                    "--lane", lane)
        assert begin.returncode == 0, begin.stdout + begin.stderr
        (repo / "router.js").write_text("SABOTAGE 1119\n")
        observed = run(
            "observe", "router.js", "--lane", lane,
            "--failure", "sabotage 1119 present", "--command",
            "CI=1", sys.executable, "-c",
            "from pathlib import Path; "
            "assert 'SABOTAGE 1119' not in Path('router.js').read_text(), "
            "'sabotage 1119 present'")
        assert observed.returncode == 0, observed.stdout + observed.stderr
        assert "emitted" in observed.stdout, observed.stdout
        restore = run("restore", "router.js", "--lane", lane)
        assert restore.returncode == 0, restore.stdout + restore.stderr
        run("forget", "router.js", "--lane", lane)


class TestNamedLaneAcrossEveryCliVerb:
    """#957: ``--lane`` is one identity selector, not a check-only flag."""

    @staticmethod
    def _run(repo: Path, env: dict[str, str], *args: str):
        return subprocess.run(
            ["python3", str(CLI_PATH), "--cwd", str(repo), *args],
            capture_output=True, text=True, env=env)

    def test_explicit_lane_wins_over_a_disagreeing_env_for_all_five_verbs(
            self, repo, tmp_path):
        named = "named-lane-957"
        env_lane = "different-env-lane-957"
        named_seg = rp._ls.identity_segment(named)
        env_seg = rp._ls.identity_segment(env_lane)
        env = dict(__import__("os").environ)
        env["REDPROOF_SCRATCH_ROOT"] = str(tmp_path / "cli-scratch-957")
        env[rp._ls.IDENTITY_ENV] = env_lane
        env[rp._ls.ROLE_ENV] = rp._ls.ROLE_AUTHOR

        begin = self._run(
            repo, env, "begin", "router.js", "--expectation", "expectation.txt",
            "--lane", named)
        assert begin.returncode == 0, begin.stdout + begin.stderr
        assert named_seg in begin.stdout, begin.stdout
        assert env_seg not in begin.stdout, begin.stdout

        # This is the production pair from #957. Before the fix, begin accepts
        # the flag but writes under env_lane, so this exact check calmly says
        # "no injections registered". Now it finds the named armed entry.
        armed = self._run(repo, env, "check", "--lane", named, "--require", "1")
        assert armed.returncode == 1, armed.stdout + armed.stderr
        assert "begun-but-unrestored" in armed.stderr, armed.stderr
        assert named_seg in armed.stderr, armed.stderr
        assert armed.stderr.startswith("check: REFUSED —"), armed.stderr

        (repo / "router.js").write_text("SABOTAGE FROM NAMED LANE 957\n")
        observed = self._run(
            repo, env, "observe", "router.js", "--lane", named,
            "--failure", "named lane injection reached", "--command",
            sys.executable, "-c",
            "from pathlib import Path; assert 'SABOTAGE' not in "
            "Path('router.js').read_text(), 'named lane injection reached'")
        assert observed.returncode == 0, observed.stdout + observed.stderr
        assert named_seg in observed.stdout and env_seg not in observed.stdout
        restore = self._run(repo, env, "restore", "router.js", "--lane", named)
        assert restore.returncode == 0, restore.stdout + restore.stderr
        assert "original restored & verified" in restore.stdout, restore.stdout
        assert named_seg in restore.stdout and env_seg not in restore.stdout

        clean = self._run(repo, env, "check", "--lane", named, "--require", "1")
        assert clean.returncode == 0, clean.stdout + clean.stderr
        assert "restoration clean" in clean.stdout, clean.stdout
        assert named_seg in clean.stdout and env_seg not in clean.stdout

        forget = self._run(repo, env, "forget", "router.js", "--lane", named)
        assert forget.returncode == 0, forget.stdout + forget.stderr
        assert "RETIRED 1 restored registration(s)" in forget.stdout, forget.stdout
        assert named_seg in forget.stdout and env_seg not in forget.stdout

    def test_empty_explicit_lane_is_refused_without_creating_scratch(
            self, repo, tmp_path):
        scratch = tmp_path / "empty-lane-scratch-957"
        env = dict(__import__("os").environ)
        env["REDPROOF_SCRATCH_ROOT"] = str(scratch)
        env[rp._ls.IDENTITY_ENV] = "env-must-not-be-fallback-957"
        env[rp._ls.ROLE_ENV] = rp._ls.ROLE_AUTHOR

        result = self._run(
            repo, env, "begin", "router.js", "--expectation", "expectation.txt",
            "--lane", "")

        assert result.returncode == 2, result.stdout + result.stderr
        assert "empty launch identity" in result.stderr, result.stderr
        assert not scratch.exists(), (
            "an invalid named lane created a phantom scratch directory")

    def test_forget_resolves_the_same_identity_as_begin(self, repo, tmp_path):
        """#1148 (revised by #1153): begin and forget must resolve identity
        through ONE function — the raw token. #1148 made forget accept the
        canonical dir name check prints AND fault on an unknown token; that
        was a per-verb re-derivation, and #1153 removes it so a token begin
        accepts is never one forget refuses. forget takes the SAME raw token
        begin took; an unknown/empty token is "nothing to forget" (exit 1),
        not a FAULT — begin creates, forget drops, but both resolve the same
        segment."""
        lane = "cx-1148fixture"
        canonical = rp._ls.identity_segment(lane)
        env = dict(__import__("os").environ)
        env["REDPROOF_SCRATCH_ROOT"] = str(tmp_path / "cli-scratch-1148")
        env[rp._ls.ROLE_ENV] = rp._ls.ROLE_AUTHOR

        begin = self._run(
            repo, env, "begin", "router.js", "--expectation", "expectation.txt",
            "--lane", lane)
        assert begin.returncode == 0, begin.stdout + begin.stderr
        checked = self._run(repo, env, "check", "--lane", lane)
        printed = re.search(r"/(lane-[^/]+)/redproof/registry[.]json", checked.stderr)
        assert printed, checked.stdout + checked.stderr
        assert printed.group(1) == canonical, checked.stderr

        # forget takes the SAME raw token begin took (#1153): one resolution
        # rule, not a dir-name match begin does not perform.
        cleared = self._run(
            repo, env, "forget", "router.js", "--lane", lane)
        assert cleared.returncode == 0, cleared.stdout + cleared.stderr
        assert "dropped 1 armed/unrecorded entry(ies)" in cleared.stdout
        assert canonical in cleared.stdout, (
            f"forget did not resolve begin's identity segment {canonical}: "
            + cleared.stdout)

        # The canonical dir name is NOT a second accepted spelling: passing it
        # re-hashes (as begin would), resolving a different, empty segment.
        # That is "nothing to forget" (exit 1), not a silent clear (#1148's
        # false-all-clear) and not a FAULT (#1153 instance 2).
        rehashed = self._run(
            repo, env, "forget", "router.js", "--lane", printed.group(1))
        assert rehashed.returncode == 1, rehashed.stdout + rehashed.stderr
        assert "nothing registered" in rehashed.stderr

        # A now-empty lane and an unknown token are the SAME state — no
        # registry for that identity — and both are "nothing to forget"
        # (exit 1). #1148 faulted on the unknown one; #1153 unifies: forget
        # refuses calmly, never faulting on a token begin would accept.
        empty = self._run(repo, env, "forget", "router.js", "--lane", lane)
        assert empty.returncode == 1, empty.stdout + empty.stderr
        assert "nothing registered" in empty.stderr

        unknown = self._run(
            repo, env, "forget", "router.js", "--lane", "cx-1148fxture")
        assert unknown.returncode == 1, (
            "an unknown lane token must be a calm 'nothing to forget' (exit 1), "
            "not a FAULT — it resolves the same segment begin would: "
            + unknown.stdout + unknown.stderr)
        assert "nothing registered" in unknown.stderr
        # A typo must NOT report success (exit 0); exit 1 is the refusal.
        assert "did not resolve to an existing launch identity" not in unknown.stderr, (
            "the #1148 per-verb fault message survived the unification: "
            + unknown.stderr)


# ── #1153: every verb resolves ONE identity, stated once ──────────────

class TestEveryVerbResolvesOneIdentity:
    """#1153: ``begin``, ``forget``, ``observe``, ``restore``, ``check`` and
    ``handoff`` must resolve lane identity through ONE function. The bug only
    exists when a lane holds SEVERAL registries (a lane mixing the env token
    with ``--lane <branch>`` sprays them); construct that, then assert every
    verb selects the same segment for a given ``--lane``.

    The defect had two faces: (1) bare verbs resolved the env identity while
    ``--lane`` registrations lived elsewhere, FAULTing in a way that read like
    a proof failure; (2) ``forget`` re-derived identity (a dir-name match +
    existence check begin never applied) so a token ``begin`` accepted was one
    ``forget`` refused. Both are the per-verb re-derivation #992 names."""

    def test_every_verb_resolves_the_same_segment_when_several_exist(
            self, repo, monkeypatch, capsys):
        """A lane holds several registries (the bug's precondition). For
        ``--lane alpha``, every verb must resolve ``identity_segment(alpha)``
        — not whichever of the several sorts first. Captures each verb's
        printed 'resolved identity dir' and asserts they all name the same
        path begin armed."""
        # Several registries under one lane_key: arm two under different tokens.
        (repo / "second.js").write_text("export function two() { return 2; }\n")
        _git(repo, "add", "second.js")
        _git(repo, "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-qm", "add second")
        # Registry A (the one every verb must select):
        assert rp.begin(repo, "router.js", ("expectation.txt",),
                        lane="alpha") == 0
        out_begin, _ = capsys.readouterr()
        seg_alpha = rp._identity_segment("alpha")
        dir_alpha = str(rp._redproof_dir(repo, seg_alpha, rp._role(repo)))
        assert dir_alpha in out_begin, (
            f"begin did not resolve alpha's dir: {out_begin}")
        # Registry B (the distractor — a different segment under this lane_key):
        assert rp.begin(repo, "second.js", ("router.js",),
                        lane="beta") == 0
        capsys.readouterr()
        # PRECONDITION: two distinct identity dirs now exist under this lane.
        idirs = sorted(d.name for d in rp._ls.lane_identity_dirs(repo))
        assert {rp._identity_segment("alpha"),
                rp._identity_segment("beta")} <= set(idirs), idirs

        # observe / restore / check under --lane alpha all resolve dir_alpha:
        (repo / "router.js").write_text("SABOTAGE ALPHA\n")
        assert rp.observe(repo, "router.js",
                          failure="sabotage alpha present",
                          command=[sys.executable, "-c",
                                   "from pathlib import Path; "
                                   "assert 'SABOTAGE' not in "
                                   "Path('router.js').read_text(), "
                                   "'sabotage alpha present'"],
                          lane="alpha") == 0
        out_observe, _ = capsys.readouterr()
        assert dir_alpha in out_observe, (
            f"observe resolved a different identity than begin: {out_observe}")

        assert rp.restore(repo, "router.js", lane="alpha") == 0
        out_restore, _ = capsys.readouterr()
        assert dir_alpha in out_restore, (
            f"restore resolved a different identity than begin: {out_restore}")

        assert rp.check(repo, lane="alpha", require=1) == 0
        out_check, _ = capsys.readouterr()
        assert dir_alpha in out_check, (
            f"check resolved a different identity than begin: {out_check}")
        # And it did NOT silently pick beta's distractor registry:
        seg_beta = rp._identity_segment("beta")
        assert seg_beta not in out_check, (
            f"check picked the distractor registry {seg_beta}: {out_check}")

        # forget under --lane alpha resolves dir_alpha (retires the restored
        # entry), the same segment begin armed — not a fault, not beta.
        assert rp.forget(repo, "router.js", lane="alpha") == 0
        out_forget, _ = capsys.readouterr()
        assert dir_alpha in out_forget, (
            f"forget resolved a different identity than begin: {out_forget}")

    def test_forget_does_not_fault_on_a_token_begin_accepts(
            self, repo, capsys):
        """Instance 2, discriminating: ``forget --lane FRESH`` on a token with
        no registry must NOT FAULT (exit 2), because ``begin --lane FRESH``
        accepts the same token. forget resolves the same segment and reports
        'nothing to forget' (exit 1). The two operations differ (begin
        creates, forget drops) but they agree on identity."""
        # A registry exists under another token (the several-registries state):
        assert rp.begin(repo, "router.js", ("expectation.txt",),
                        lane="alpha") == 0
        capsys.readouterr()
        # forget on a FRESH token no registry exists for:
        exit = rp.forget(repo, "router.js", lane="fresh-unused-token-1153")
        out, err = capsys.readouterr()
        assert exit != 2, (
            f"forget FAULTED on a token begin would accept (#1153 instance 2): "
            f"{err}")
        # It resolved the SAME segment begin would, and said nothing-to-forget:
        seg = rp._identity_segment("fresh-unused-token-1153")
        assert str(rp._redproof_dir(repo, seg, rp._role(repo))) in out, (
            f"forget did not resolve begin's segment for the fresh token: {out}")
        assert "nothing to forget" in err or "nothing registered" in err, err

    def test_bare_check_names_the_env_identity_not_an_unnamed_lane(
            self, repo, monkeypatch, capsys):
        """#651: a bare ``check`` (env set, no --lane) that faults must name
        the identity it ACTUALLY audited (the env one), not 'the named lane'
        — no lane was named. And when other identity dirs exist (#1153
        instance 1: the work is under --lane), it names them so the absence
        reads as 'not THIS identity', not 'you have no registry'."""
        # The lane's real work is under --lane branchname (a different segment
        # than the env token), modelling instances 1 and 3 exactly.
        assert rp.begin(repo, "router.js", ("expectation.txt",),
                        lane="glm-1153ident") == 0
        capsys.readouterr()
        # Bare check uses the ENV identity (fixture-lane-aa895 from the repo
        # fixture), which is empty; require>0 faults.
        exit = rp.check(repo, require=1)
        _, err = capsys.readouterr()
        assert exit == 2, f"expected FAULT, got {exit}: {err}"
        # Must NOT claim a lane was named when none was (#651):
        assert "the named lane" not in err, err
        # Must name the env identity it audited:
        assert "this lane" in err, err
        # Must name the other identity dir where the work actually lives
        # (#136): the absence cannot read as 'no registry anywhere'.
        assert rp._identity_segment("glm-1153ident") in err, (
            f"check did not name the other identity holding the work: {err}")


# ── #877: a restored source whose downstream bundle is stale ──────────

def _build_bundle(root: Path) -> None:
    """Simulate ``just build-client``: regenerate outputs from inputs, write
    the manifest. Uses ``client_dist``'s own hash + path functions so the
    test's idea of a build agrees with the checker's, not a second copy."""
    import client_dist as _cd
    inputs = _cd.expected_inputs(str(root))
    in_hashes = {rel: _cd.sha256_file(str(root / rel)) for rel in inputs}
    # ds/index.js concatenates the client assets — that is how the real build
    # works, and it is what makes a source injection reach the bundle.
    bundle = "".join((root / "client" / n).read_text()
                     for n in _cd.asset_order(str(root)))
    (root / "client" / "dist" / "ds" / "index.js").write_text(bundle)
    (root / "client" / "dist" / "ds" / "styles.css").write_text("// styles\n")
    (root / "client" / "dist" / "native.js").write_text("// native\n")
    out_hashes = {rel: _cd.sha256_file(str(root / rel))
                  for rel in _cd.OUTPUT_RELS}
    manifest = {"asset_order": _cd.asset_order(str(root)),
                "inputs": in_hashes, "outputs": out_hashes,
                "schema": 1, "tool": {"test": "yes"}}
    with open(str(root / _cd.MANIFEST_REL), "w") as f:
        json.dump(manifest, f, indent=2)


@pytest.fixture
def bundle_repo(tmp_path: Path, monkeypatch) -> Path:
    """A git repo with a minimal client/dist build tree for #877 tests.

    Creates just enough for ``client_dist.expected_inputs`` and
    ``client_dist.check`` to work: ``watch.py`` with ``_CLIENT_ASSETS``, one
    client asset, one native source, the wrapper, and a committed dist. The
    ``_client_dist_override`` hook points redproof at the real module so the
    fixture does not need its own ``client_dist.py``."""
    import client_dist as _cd
    monkeypatch.setattr(rp, "_client_dist_override", _cd)
    root = tmp_path / "bundle"
    root.mkdir()
    _git(root, "init", "-q", "-b", "master", ".")
    (root / "expectation.txt").write_text("bundle expectation fixture\n")
    (root / "watch.py").write_text('_CLIENT_ASSETS = ("router.js",)\n')
    (root / "client").mkdir()
    (root / "client" / "router.js").write_text(
        "export function route() { return true; }\n")
    (root / "dev" / "build" / "src").mkdir(parents=True)
    (root / "dev" / "build" / "src" / "native-entry.js").write_text("// native\n")
    (root / "dev" / "build" / "wrapper-exports.js").write_text("// wrapper\n")
    (root / "client" / "dist" / "ds").mkdir(parents=True)
    _build_bundle(root)
    # PRECONDITION: the fixture dist starts clean.
    assert _cd.check(str(root))["state"] == _cd.OK, (
        "fixture dist is not clean at setup — every #877 test below would "
        "then be reading a defect the fixture introduced")
    _git(root, "add", ".")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    monkeypatch.setattr(rp._ls, "SCRATCH_ROOT", tmp_path / "scratch")
    monkeypatch.setenv(rp._ls.IDENTITY_ENV, "fixture-bundle-aa895")
    return root


class TestBundleStalenessIsRefused:
    """THE #877 red run: inject → build → restore (NO rebuild) → check REFUSES.

    The source is restored and the tree is clean, but the bundle a guard
    serves was built from the injected bytes. ``check`` must refuse, naming
    the source AND the stale bundle — a bare 'refused' is not discriminating."""

    def test_restored_source_with_stale_bundle_is_refused(self, bundle_repo,
                                                          capsys):
        import client_dist
        root = bundle_repo
        target = "client/router.js"

        _begin(root, target)
        sabotage = "export function route() { return false; /* SABOTAGE */ }\n"
        (root / target).write_text(sabotage)
        _build_bundle(root)  # build with the injection baked in

        # DIRECTION-2 CLOSURE — "green because the guard was never the
        # consumer": the bundle must ACTUALLY hold the injection. Verified
        # by reading bundle BYTES, not via client_dist.check (self-agreement:
        # the check and the assertion must not share an implementation).
        bundle_bytes = (root / "client" / "dist" / "ds" / "index.js").read_bytes()
        assert b"SABOTAGE" in bundle_bytes, (
            "precondition failed: the bundle does not hold the injection, "
            "so the whole scenario evaporates — the guard would never serve it")

        _restore(root, target)  # restore the SOURCE only — NO rebuild

        # The bundle STILL holds the injection, independently verified.
        assert b"SABOTAGE" in (root / "client/dist/ds/index.js").read_bytes(), (
            "the bundle lost the injection without a rebuild — the defect "
            "does not reproduce and the test proves nothing")

        exit = _check(root)
        _, err = capsys.readouterr()

        assert exit == 1, (
            "a restored source with a stale downstream bundle MUST be refused")
        # DIRECTION-2 CLOSURE — "refused for the wrong reason": assert on the
        # TEXT. The entry IS restored, so this is not an armed-entry or
        # live-injection refusal.
        assert "client/router.js" in err, "refusal must name the restored source"
        assert "stale" in err.lower(), (
            "refusal must name the stale bundle — a bare refusal is not "
            "discriminating and could fire for any reason")
        assert "#877" in err
        assert "STILL MATCHES" not in err, (
            "refused as a live injection, not as a stale bundle — the entry "
            "was restored, so this is the wrong reason")
        assert "armed" not in err, (
            "refused as an armed entry, not as a stale bundle")

    def test_rebuilt_bundle_after_restore_passes(self, bundle_repo):
        """The rebuild-first companion: inject → build → restore → REBUILD.

        This is the test that passes under BOTH the fixed and broken tool, so
        it cannot be the ONLY test (the rebuild-first vacuum). It proves the
        fix does not over-refuse when the lane correctly rebuilds."""
        root = bundle_repo
        target = "client/router.js"

        _begin(root, target)
        sabotage = "export function route() { return null; /* BUG */ }\n"
        (root / target).write_text(sabotage)
        _build_bundle(root)
        _restore(root, target)
        _build_bundle(root)  # REBUILD after restore — the correct sequence

        # PRECONDITION: the bundle no longer holds the injection.
        assert b"BUG" not in (root / "client/dist/ds/index.js").read_bytes()

        assert _check(root) == 0, (
            "a rebuilt bundle after restore must pass — over-refusing here "
            "would teach lanes to route around the check")

    def test_stale_on_a_different_input_does_not_refuse(self, bundle_repo):
        """A restored build input whose own hash matches the manifest is not
        refused, even when the dist is stale because of a DIFFERENT input.

        This is the false-positive guard: a lane with a dirty dist for an
        unrelated reason must not be blocked. The restored path is a build
        input but is NOT in client_dist's stale list, so the check stays
        silent."""
        import client_dist
        root = bundle_repo
        target = "client/router.js"

        # inject → restore WITHOUT building: manifest still records the
        # original, so router.js matches after restore.
        _begin(root, target)
        (root / target).write_text("SABOTAGE\n")
        _restore(root, target)

        # make the dist stale by editing a DIFFERENT build input
        (root / "dev" / "build" / "wrapper-exports.js").write_text("// changed\n")

        reading = client_dist.check(str(root))
        # PRECONDITIONS: the dist IS stale, but the restored path is NOT the
        # stale one — derived at runtime, not a literal.
        assert reading["state"] == client_dist.STALE
        assert "client/router.js" not in reading.get("stale", []), (
            "router.js is unexpectedly stale — the test's discriminating "
            "precondition (stale on a DIFFERENT path) has collapsed")

        assert _check(root) == 0, (
            "a restored input whose own hash is current must not refuse, "
            "even when the dist is stale for another reason")

    def test_a_restored_non_build_input_passes_with_stale_dist(
            self, bundle_repo):
        """A restored path that is NOT a client_dist build input must not
        trigger the bundle check at all, even when the dist is stale."""
        import client_dist
        root = bundle_repo

        # a file that is NOT a build input
        (root / "README.md").write_text("original readme\n")
        _inject(root, "README.md", "SABOTAGE README\n")

        # make the dist stale
        (root / "client" / "router.js").write_text(
            "export function route() { return 42; }\n")
        assert client_dist.check(str(root))["state"] == client_dist.STALE

        # README.md is restored and not a build input
        assert _check(root) == 0, (
            "a restored non-build-input must not trigger the bundle check")


# ── #934: redproof and lane_scratch print DIFFERENT roots for one lane ──

class TestBeginStatesTheRedproofRootDistinctFromLaneScratch:
    """THE #934 defect: ``lane_scratch.py snap`` and ``redproof.py`` print
    DIFFERENT snapshot roots for the same lane (``snap/`` vs ``redproof/``),
    and four lanes tripped on a ``cmp`` against the wrong one. The tools and
    their printed paths were never wrong — every lane recovered by using the
    exact path the tool PRINTED. The defect is that the standing procedure
    named one tool while the workflow used two, so an agent following it
    verbatim constructed the wrong path by default.

    The fix does NOT unify the roots (redproof content-addresses its snapshots
    by ``sha1(posix_path)``, which is load-bearing for ``check``/``restore``/
    ``forget`` finding each injection deterministically and for concurrent
    injections not clobbering each other; ``snap`` is general scratch with
    lane-chosen names). Instead, ``begin`` STATES the root distinction at the
    moment the path is in hand, and ``lane_scratch.py``'s docstring defers to
    redproof for red-proof injections (tested in test_lane_scratch.py).

    The acceptance test: an agent following the written procedure verbatim
    lands on the right path without having to notice a discrepancy."""

    def test_begin_output_names_the_sibling_lane_scratch_root(self, repo, capsys):
        """The discrepancy must be STATED in begin's output, not discovered via
        a false ``cmp``. begin must name ``lane_scratch`` so an agent with both
        tools' output knows the ``snap/`` root is a separate one.

        DISCRIMINATOR (false on the unfixed tool, true after): the unfixed
        begin output prints only the ``redproof/`` path and never names
        ``lane_scratch``. DERIVED FROM the sibling tool's identity
        (``dev/lane_scratch.py``), not a presentation detail (#917)."""
        _begin(repo, "router.js")
        out, _ = capsys.readouterr()
        assert "lane_scratch" in out, (
            "begin must name lane_scratch.py so an agent knows its snap/ root "
            "is separate from redproof's redproof/ root — the discrepancy must "
            "be stated, not discovered via a false cmp (#934)")

    def test_the_path_begin_prints_holds_the_original_bytes(self, repo, capsys):
        """Followability: an agent that uses the path begin PRINTED (not one it
        assumed) reaches the correct baseline. This is how all four #934 lanes
        recovered, and it is the regression net proving the printed path is the
        right one — a future change that printed a ``snap/`` path would fail
        here because the original is under ``redproof/``.

        The expected path is DERIVED FROM the original bytes and the snapshot's
        existence, not from the same function begin calls to print it (the path
        is read back from begin's own output and then verified against the
        original bytes an independent caller captured)."""
        original = (repo / "router.js").read_bytes()
        _begin(repo, "router.js")
        out, _ = capsys.readouterr()
        # extract the path begin printed — the one after "->"
        snap_line = next(ln for ln in out.splitlines() if "->" in ln)
        printed = Path(snap_line.split("->", 1)[1].strip())
        # the printed path exists and holds exactly the original
        assert printed.exists(), f"begin printed a path that does not exist: {printed}"
        assert printed.read_bytes() == original, (
            "the path begin printed must hold the original bytes — an agent "
            "cmp-ing against it reaches the right baseline (#934)")

    def test_begin_output_prints_a_redproof_root_not_a_snap_root(self, repo, capsys):
        """The printed snapshot path is under the ``redproof/`` root, NOT under
        ``snap/`` (the lane_scratch general-scratch root). Containment on the
        root IDENTITY (``redproof`` / ``snap`` are literal subdir names), not a
        presentation detail — matching #930's containment style rather than
        pinning an exact path string."""
        _begin(repo, "router.js")
        out, _ = capsys.readouterr()
        snap_line = next(ln for ln in out.splitlines() if "->" in ln)
        printed = Path(snap_line.split("->", 1)[1].strip())
        parts = printed.parts
        # DENOMINATOR stated: the red-proof root is real for this lane, and it
        # is NOT the lane_scratch snap root — the two differ for one lane, which
        # is the population the #934 friction lives in. This is a PRECONDITION
        # for the discriminator above, not the proof of followability by itself.
        assert "redproof" in parts, (
            f"the printed snapshot must be under the redproof/ root; got {printed}")
        assert "snap" not in parts, (
            f"the red-proof snapshot must NOT be under snap/ (lane_scratch's "
            f"general root); got {printed}")

    def test_restore_verifies_internally_so_a_manual_cmp_is_redundant(
            self, repo, capsys):
        """The other half of the fix: ``restore`` verifies the copy internally,
        so a user of the redproof protocol never needs a manual ``cmp`` at all
        — which removes the opportunity to aim it at the wrong root. begin's
        output must say so, pointing a manual cmp at the printed path if one is
        run anyway."""
        _begin(repo, "router.js")
        out, _ = capsys.readouterr()
        assert "verifies internally" in out, (
            "begin must say restore verifies internally — a user of this "
            "protocol needs no manual cmp, which is how the wrong-root cmp is "
            "avoided entirely (#934)")



# ── #942: a re-arm must not move the boundary past its own injection ──


def _rearm_after_rebase(lane: Path, sabotage: str) -> str:
    """The documented lane lifecycle, every step of it correct advice.

    inject -> COMMIT INCREMENTALLY while sabotaged -> restore -> commit the fix
    -> rebase (mandatory before reporting) -> the pinned expectation goes stale.
    Returns the rewritten sha of the commit that still holds the injection.
    """
    _begin(lane, "router.js")
    (lane / "router.js").write_text(sabotage)
    _commit(lane, "router.js", msg="wip(#942): mid red-proof")
    _restore(lane, "router.js")
    (lane / "router.js").write_text(
        "export function route() { return Boolean(guard); }\n")
    _commit(lane, "router.js", msg="fix(#942): the real fix")
    _git(lane, "rebase", "--force-rebase", "master")
    # What #910's fourth data point measured: "the rebase rewrote the
    # expectation's sha ... so the pinned expectation went stale post-rebase
    # even though the injection was restored and absent."
    (lane / "expectation.txt").write_text("route expectation, post-rebase\n")
    poisoned = _git(lane, "log", "--format=%H",
                    "--grep=^wip(#942): mid red-proof$")
    assert poisoned, "fixture did not produce a rewritten injection commit"
    return poisoned


class TestARearmCannotHideTheInjectionThatRequiredIt:
    """THE #942 red run, and every step of it is documented advice.

    `check` correctly refuses a post-rebase expectation drift and prints the
    remedy: forget, begin, re-sabotage, restore (#910). Following that remedy
    verbatim used to ERASE the only record bounded before the poisoned commit,
    and the re-armed record's `begun_head` sat AFTER it — so the registration
    boundary reclassified the real injection as preexisting and the scan
    printed `0 holding a recorded injection` over a genuinely broken branch.
    The tool's own advice defeated the tool's own check.
    """

    def _follow_the_printed_remedy(self, lane: Path, sabotage: str) -> None:
        assert rp.forget(lane, "router.js") == 0
        _begin(lane, "router.js")
        (lane / "router.js").write_text(sabotage)
        _restore(lane, "router.js")

    def test_the_rearmed_boundary_does_not_hide_the_committed_injection(
            self, lane, capsys):
        sabotage = "export function route() { return false; /* BUG #942 */ }\n"
        poisoned = _rearm_after_rebase(lane, sabotage)

        # The tool refuses the stale pin and PRINTS the remedy followed below —
        # so this test exercises the documented path, not an invented one.
        assert _check(lane) == 1
        _, drift_err = capsys.readouterr()
        assert "expectation source" in drift_err, drift_err
        assert "forget" in drift_err and "begin" in drift_err, drift_err

        self._follow_the_printed_remedy(lane, sabotage)
        capsys.readouterr()
        entries, _ = rp._read_registry(lane)
        rearmed = [e for e in entries if e.get("state") == rp.RESTORED]
        assert len(rearmed) == 1, entries

        # PRECONDITIONS, derived at runtime, all three about the WORLD rather
        # than about the fix — so a broken fix reds on the outcome below and
        # not on its own scaffolding.
        # (i) the branch GENUINELY still holds the recorded injection ...
        assert _blob_sha_at(lane, poisoned, "router.js") == rearmed[0]["injected_sha"]
        # (ii) ... while the tree is clean, so history is the only cause ...
        assert rp._sha((lane / "router.js").read_bytes()) != rearmed[0]["injected_sha"]
        # (iii) ... and the RE-ARMED boundary is a descendant of that commit,
        #       so the re-armed record on its own would exclude it. Without
        #       this the branch is not in the defective state and a pass here
        #       would prove nothing.
        assert subprocess.run(
            ["git", "-C", str(lane), "merge-base", "--is-ancestor",
             poisoned, rearmed[0]["begun_head"]], check=False).returncode == 0, (
            "the re-armed boundary does not sit after the poisoned commit; "
            "this fixture is not in the #942 state")

        rep = rp.scan_history(lane, entries)
        assert rep["commits"] == 2 and rep["blobs_read"] == 2, rep
        assert len(rep["hits"]) == 1, (
            "the re-arm hid the committed injection: the scan reported "
            f"{len(rep['hits'])} holding a recorded injection over a branch "
            f"whose commit {poisoned[:12]} still holds it — {rep}")
        assert rep["hits"][0]["commit"] == poisoned, rep["hits"]

        exit = _check(lane)
        out, err = capsys.readouterr()
        assert exit == 1, out + err
        assert "1 holding a recorded injection" in out, out
        assert poisoned[:12] in err, err
        assert "BUG #942" in err, err
        assert "squash" in err.lower(), err

    def test_the_retired_record_is_what_keeps_the_boundary_back(
            self, lane, capsys):
        """The mechanism, asserted separately from the outcome: `forget`
        retires rather than erases, and the retired record keeps the ORIGINAL
        registration boundary — which is the only reason the scan above can
        still reach the poisoned commit."""
        sabotage = "export function route() { return false; /* BUG #942 */ }\n"
        poisoned = _rearm_after_rebase(lane, sabotage)
        before, _ = rp._read_registry(lane)
        original_boundary = [e for e in before
                             if e.get("state") == rp.RESTORED][0]["begun_head"]

        self._follow_the_printed_remedy(lane, sabotage)
        capsys.readouterr()

        entries, _ = rp._read_registry(lane)
        retired = [e for e in entries if e.get("state") == rp.RETIRED]
        assert len(retired) == 1, (
            f"forget erased the prior registration instead of retiring it: "
            f"{entries}")
        assert retired[0]["begun_head"] == original_boundary, (
            "the retired record's boundary moved; carrying it unchanged is "
            "the whole fix")
        # ... and that boundary genuinely predates the poisoned commit, which
        # is what gives the scan authority over it.
        assert subprocess.run(
            ["git", "-C", str(lane), "merge-base", "--is-ancestor",
             poisoned, retired[0]["begun_head"]], check=False).returncode == 1
        # A retired record is history evidence and nothing else: no stale
        # expectation pin (that is what the re-arm cleared) and no snapshot.
        assert "expectation_sources" not in retired[0], retired[0]
        assert "snapshot" not in retired[0], retired[0]

    def test_a_retired_record_still_blocks_a_lane_that_never_rearms(
            self, lane, capsys):
        """`forget` alone is not an amnesty. A lane that commits an injection,
        restores, and then simply drops the record must still be refused —
        otherwise `forget` is a one-word hand-bypass of the #710 scan."""
        poisoned, _clean = _poison(lane)
        recorded = [e for e in rp._read_registry(lane)[0]
                    if e.get("state") == rp.RESTORED][0]["injected_sha"]
        assert _blob_sha_at(lane, poisoned, "router.js") == recorded

        assert rp.forget(lane, "router.js") == 0
        capsys.readouterr()
        entries, _ = rp._read_registry(lane)
        assert [e for e in entries if e.get("state") == rp.RESTORED] == []

        exit = _check(lane)
        out, err = capsys.readouterr()
        assert exit == 1, out + err
        assert poisoned[:12] in err, err

    def test_forgetting_a_retired_record_is_refused_and_says_why(
            self, lane, capsys):
        _inject(lane, "router.js",
                "export function route() { return false; /* BUG */ }\n")
        assert rp.forget(lane, "router.js") == 0
        capsys.readouterr()
        assert rp.forget(lane, "router.js") == 1
        _, err = capsys.readouterr()
        assert "retired" in err, err
        assert "cannot be dropped" in err, err

    def test_forgetting_an_armed_entry_still_drops_it_and_frees_the_name(
            self, lane, capsys):
        """The re-arm remedy depends on this: `begin` refuses a path that
        already has an armed snapshot, so a `forget` that left anything
        armed-shaped behind would make #910's printed remedy unusable."""
        _begin(lane, "router.js")
        assert rp.forget(lane, "router.js") == 0
        entries, _ = rp._read_registry(lane)
        assert entries == [], entries
        assert _begin(lane, "router.js") == 0, "re-arm after forget was refused"


class TestTheThreeHistoryZeroesAreDistinct:
    """#868/#915/#942: three facts that used to share one sentence.

    (1) scanned, found nothing; (2) nothing was recorded to look for; (3) the
    boundary matched and excluded. #942 is what (3) wearing (1)'s clothes
    costs — a real injection, in a real commit, reported as a clean count.
    """

    LOOKED = "holding a recorded injection"
    NOTHING = "NOTHING TO LOOK FOR"
    EXCLUDED = "boundary EXCLUDED"

    def test_looked_and_found_nothing(self, lane):
        _begin(lane, "router.js")
        (lane / "router.js").write_text("SABOTAGE\n")
        _restore(lane, "router.js")
        (lane / "router.js").write_text(
            "export function route() { return Boolean(guard); }\n")
        _commit(lane, "router.js", msg="fix(#942): only clean commits")
        entries, _ = rp._read_registry(lane)
        rep = rp.scan_history(lane, entries)
        # PRECONDITION: it really did have something to look for, in a range.
        assert rep["paths"] == 1 and rep["commits"] == 1, rep
        assert rep["hits"] == [] and rep["excluded"] == [], rep

        line = rp.history_line(rep)
        assert self.LOOKED in line, line
        assert self.NOTHING not in line, line
        assert self.EXCLUDED not in line, line

    def test_nothing_was_recorded_to_look_for(self, lane):
        (lane / "router.js").write_text(
            "export function route() { return Boolean(guard); }\n")
        _commit(lane, "router.js", msg="fix(#942): a commit and no registry")
        rep = rp.scan_history(lane, [])
        # PRECONDITION: a real range with real commits — the emptiness is the
        # RECORD, not the range, which is the distinction being made.
        assert rep["commits"] == 1 and rep["paths"] == 0, rep

        line = rp.history_line(rep)
        assert self.NOTHING in line, line
        assert self.LOOKED not in line, line
        assert self.EXCLUDED not in line, line

    def test_the_boundary_excluding_everything_is_loud(self, lane, capsys):
        """The legitimate exclusion — the canonical direction-1 sabotage IS
        the pre-fix bytes, which existed on this branch before the tool saw
        them. It must still pass, and it must no longer be silent."""
        (lane / "router.js").write_text(
            "export function route() { return false; }\n")
        predecessor = _commit(lane, "router.js", msg="feat(#942): predecessor")
        (lane / "router.js").write_text(
            "export function route() { return Boolean(guard); }\n")
        _commit(lane, "router.js", msg="fix(#942): actual repair")
        _inject(lane, "router.js", "export function route() { return false; }\n")

        entries, _ = rp._read_registry(lane)
        rep = rp.scan_history(lane, entries)
        # PRECONDITION: a blob really did MATCH; without a match there is
        # nothing for the boundary to exclude and this proves nothing.
        recorded = [e for e in entries if e.get("state") == rp.RESTORED][0]
        assert _blob_sha_at(lane, predecessor, "router.js") == recorded["injected_sha"]
        assert rep["hits"] == [], (
            "a pre-registration commit was blamed as an armed injection", rep)
        assert len(rep["excluded"]) == 1, (
            f"the boundary excluded {predecessor[:12]}, which DOES hold the "
            f"recorded bytes, and reported nothing — that exclusion is exactly "
            f"the silent zero #942 hid a real injection behind: {rep}")
        assert rep["excluded"][0]["commit"] == predecessor, rep["excluded"]

        line = rp.history_line(rep)
        assert self.EXCLUDED in line, line
        assert predecessor[:12] in line, line
        # both facts, so a reader cannot take the zero for the whole answer
        assert self.LOOKED in line, line
        assert self.NOTHING not in line, line

        # and the verdict is unchanged: a pre-registration commit is not blamed
        assert _check(lane) == 0
        out, err = capsys.readouterr()
        assert "restoration clean" in out, out
        assert "REFUSED" not in err, err


class TestTheAuditNamesItsTwoPopulationsSeparately:
    """#942 second defect. `audit_sources` is the legacy registry PLUS every
    launch-identity dir — two DISJOINT populations — so `N registry/ies across
    M launch-identity dir(s)` asserted a containment that does not hold. The
    true reading `1 across 0` read as a self-contradiction; a sibling lane
    wrote a test asserting `1 across 1` because that is what the sentence
    says, and the gate refused it at named-tests.
    """

    AUDIT = re.compile(
        r"audited (\d+) registry/ies across (\d+) launch-identity dir\(s\)")

    def _label(self, repo: Path, capsys) -> str:
        """The audit denominators as the MERGE GATE meets them: #935 runs
        `check --cwd <lane> --require 1` with DREAMWORK_LANE_ID popped, and
        this sentence is what its refusal prints."""
        exit = _check(repo, require=1)
        out, err = capsys.readouterr()
        assert exit == 1, out + err
        return err

    @pytest.mark.parametrize("under_identity", [False, True])
    def test_the_across_containment_holds_and_legacy_is_named_apart(
            self, repo, monkeypatch, capsys, under_identity):
        if not under_identity:
            monkeypatch.delenv(rp._ls.IDENTITY_ENV, raising=False)
        _inject(repo, "router.js", "SABOTAGE\n")
        assert rp.forget(repo, "router.js") == 0     # -> no live entries
        capsys.readouterr()

        monkeypatch.delenv(rp._ls.IDENTITY_ENV, raising=False)   # coordinator
        dirs = rp._ls.lane_identity_dirs(repo)
        legacy = rp._redproof_dir(repo, "", rp._role(repo)) / "registry.json"
        # PRECONDITIONS derived from disk, so the case cannot silently become
        # the other one: exactly one of the two populations holds the registry.
        assert legacy.exists() is (not under_identity), (legacy, dirs)
        assert len(dirs) == (1 if under_identity else 0), dirs

        line = self._label(repo, capsys)
        found = self.AUDIT.search(line)
        assert found, line
        registries, identity_dirs = int(found.group(1)), int(found.group(2))
        # the containment the word `across` asserts must actually hold ...
        assert registries <= identity_dirs, (
            f"'{found.group(0)}' claims a containment that does not hold", line)
        assert identity_dirs == len(dirs), (found.group(0), dirs)
        # ... and the OTHER population is reported, not folded into that count
        assert f"legacy registry {'absent' if under_identity else 'present'}" \
            in line, line


class TestRelaunchedLaneIsTheRemainingHole:
    """DIRECTION 2 for #942, executable and OPEN in one of the two modes.

    The carried-forward record lives in ONE registry, and a registry is keyed
    by launch identity (#870). A lane relaunched in the same worktree — a new
    `DREAMWORK_LANE_ID`, same branch — begins a registry the earlier identity's
    record is not in. Its own `check` (MODE A, its token in env) therefore
    searches only for its own bytes and prints a true `0 holding a recorded
    injection` over a commit that holds the FIRST identity's injection.

    The coordinator's audit (MODE B, no token: #895's enumeration, and what
    #935's merge gate runs) reads every identity dir under this lane's key and
    DOES catch it. So the hole is real and precisely bounded: it is open to a
    lane auditing itself and closed at the gate. Kept as a passing test
    asserting BOTH answers, so closing it fails here loudly rather than
    silently (the `TestKnownHole` idiom).
    """

    def test_mode_a_misses_it_and_the_coordinator_mode_b_catches_it(
            self, lane, monkeypatch, capsys):
        # Identity A: inject, COMMIT while sabotaged, restore.
        poisoned, _clean = _poison(lane)
        a_registry = rp._registry_path(lane)
        a_recorded = [e for e in rp._read_registry(lane)[0]
                      if e.get("state") == rp.RESTORED][0]["injected_sha"]

        # The lane is relaunched in the same worktree under a NEW identity.
        monkeypatch.setenv(rp._ls.IDENTITY_ENV, "fixture-lane-relaunched-b942")
        b_registry = rp._registry_path(lane)
        assert b_registry != a_registry, "fixture did not change identity"
        _inject(lane, "router.js", "export function route() { return 0; }\n")
        capsys.readouterr()

        # PRECONDITIONS: the branch really does hold identity A's injection,
        # and identity B's registry really does not know that sha — without
        # both, neither half below means anything.
        assert _blob_sha_at(lane, poisoned, "router.js") == a_recorded
        b_entries, _ = rp._read_registry(lane)
        assert a_recorded not in {e.get("injected_sha") for e in b_entries}

        # MODE A — the relaunched lane auditing itself: a TRUE zero, taken by
        # a reader as a clean branch. The false green, on purpose.
        assert _check(lane) == 0
        out, _ = capsys.readouterr()
        assert "0 holding a recorded injection" in out, out
        assert "restoration clean" in out, out

        # MODE B — the coordinator / #935 merge gate: enumeration reaches
        # identity A's registry and the commit is named.
        monkeypatch.delenv(rp._ls.IDENTITY_ENV, raising=False)
        assert len(rp._ls.lane_identity_dirs(lane)) == 2
        exit = _check(lane)
        out, err = capsys.readouterr()
        assert exit == 1, out + err
        assert poisoned[:12] in err, err


# ── #1086: handoff derives the requirement, then checks ──────────────────────


def _handoff(repo: Path, **kw) -> int:
    return rp.handoff(repo, **kw)


def _binding_branch(repo: Path) -> tuple[str, str]:
    """A lane branch with a BINDING diff so _classify_diff derives require=1.

    Models the #1086 case: a branch that changed a .py file owes an injection.
    Returns (base_sha, branch_sha) so a test can assert the precondition
    (require is 1 because the diff is binding, not because the test hardcoded it).
    """
    base = _git(repo, "rev-parse", "master")
    _git(repo, "switch", "-q", "-c", "handoff-fixture")
    (repo / "router.js").write_text(
        "export function route() { return Boolean(guard); }\n")
    head = _commit(repo, "router.js", msg="feat(#1086): binding change")
    _git(repo, "switch", "-q", "master")  # leave branch checked out cleanly
    _git(repo, "switch", "-q", "handoff-fixture")
    return base, head


class TestHandoffDerivesRequirement:
    """#1086: the requirement is DERIVED from the diff, never from the count.

    Each test asserts the precondition it depends on (the derived requirement)
    before asserting the verdict, because a literal exit code over today's
    fixture is a check with an expiry date."""

    def test_a_binding_diff_with_no_injection_is_refused_not_calm(
            self, repo, capsys):
        """glm-1038states: lane wrote 'no injection owed' over a require=1 diff.

        handoff derives the requirement from _classify_diff, so it contradicts
        the lane's recollection. With no registry locatable and a required
        injection, check FAULTs (exit 2) — the proof cannot be verified, not
        calm (#1038 Finding 3). The header still names the derived number."""
        base, head = _binding_branch(repo)
        # PRECONDITION: the diff really is binding (require=1). The verdict
        # below means nothing if this fixture stopped owing an injection.
        derived = rp._derived_requirement(repo, base, head)
        assert derived["require"] == 1, (
            f"fixture lost its binding diff; require={derived['require']} "
            f"binding={derived['binding']}")
        capsys.readouterr()
        exit = _handoff(repo)
        out, err = capsys.readouterr()
        assert exit == 2, out + err
        # The derived number is STATED in the header — the lane quotes THIS,
        # not its own "no injection owed" recollection.
        assert "1 injection(s) owed" in out, out
        assert "Produce a fresh causal proof" in err, err
        assert "Carry-forward provenance was supplied" not in err, err

    def test_a_carry_forward_binding_diff_with_no_registry_gets_cli_remedy(
            self, repo, capsys):
        """handoff forwards explicit CLI provenance without changing require."""
        base, head = _binding_branch(repo)
        derived = rp._derived_requirement(repo, base, head)
        assert derived["require"] == 1, derived
        capsys.readouterr()

        exit_code = _handoff(repo, carry_forward=True)
        out, err = capsys.readouterr()

        assert exit_code == 2, out + err
        assert "1 injection(s) owed" in out, out
        assert "Carry-forward provenance was supplied" in err, err
        assert "audits exactly the worktree root it is given" in err, err
        assert "Produce a fresh causal proof" not in err, err

    def test_a_retired_only_registry_is_refused_not_reported_clean(
            self, repo, capsys):
        """The largest #1086 sub-type: every registration RETIRED, lane wrote
        'no injection owed'. A retired registration is history-scope evidence,
        not live evidence (#942); handoff must REFUSE over require=1."""
        _binding_branch(repo)
        _begin(repo, "router.js")
        (repo / "router.js").write_text("export function route() { return 0; }\n")
        assert _restore(repo, "router.js") == 0
        # forget RETIRES the restored registration; it is no longer live.
        assert rp.forget(repo, "router.js") == 0
        entries, _ = rp._read_registry(repo)
        # PRECONDITION: the only registration is RETIRED — this is the exact
        # state the test exists for, and a fixture that left a live entry would
        # refuse for a different reason.
        states = [e.get("state") for e in entries]
        assert rp.RETIRED in states, states
        assert not any(s in rp.RESTORED_STATES for s in states), states
        capsys.readouterr()
        exit = _handoff(repo)
        out, err = capsys.readouterr()
        assert exit == 1, out + err
        # The discriminating message names retired-vs-live, not a generic count.
        assert "retired" in (out + err).lower(), out + err

    def test_a_restored_injection_with_no_observation_is_refused_not_caught(
            self, repo, capsys):
        """glm-1037read variant: lane restored an injection and wrote 'CAUGHT'
        from its recollection of running checks, but never called `observe` —
        so the tool has no causal reach receipt. handoff REFUSES on NOT CHECKED,
        not a calm 'caught N of N' over evidence that was never recorded."""
        _binding_branch(repo)
        _begin(repo, "router.js")
        (repo / "router.js").write_text("export function route() { return 0; }\n")
        assert _restore(repo, "router.js") == 0
        entries, _ = rp._read_registry(repo)
        live = [e for e in entries if e.get("state") in rp.RESTORED_STATES]
        assert len(live) == 1, "fixture precondition: exactly one live entry"
        # PRECONDITION: the restored entry has NO reach receipt — this is the
        # state where a lane's 'I red-proofed' is unverified by the tool.
        assert live[0].get("reach") is None, live[0]
        capsys.readouterr()
        exit = _handoff(repo)
        out, err = capsys.readouterr()
        assert exit == 1, out + err
        # Discriminating: NOT CHECKED names the missing causal evidence, not a
        # count mismatch.
        assert "NOT CHECKED" in (out + err), out + err

    def test_an_all_inert_diff_passes_with_require_zero(
            self, repo, capsys):
        """The vacuous-pass guard: a doc-only diff derives require=0 and passes,
        but the block must STATE zero was owed, not read as an unexamined sweep."""
        _git(repo, "switch", "-q", "-c", "inert-fixture")
        os.makedirs(repo / ".dreamwork", exist_ok=True)
        (repo / ".dreamwork" / "notes.md").write_text("a doc-only change\n")
        base = _git(repo, "rev-parse", "master")
        head = _commit(repo, ".dreamwork/notes.md", msg="docs(#1086): inert")
        derived = rp._derived_requirement(repo, base, head)
        # PRECONDITION: the diff is genuinely all-inert (require=0). A fixture
        # that gained a binding path would flip this and the test would refuse.
        assert derived["require"] == 0, (
            f"fixture gained a binding path; require={derived['require']}")
        capsys.readouterr()
        exit = _handoff(repo)
        out, err = capsys.readouterr()
        assert exit == 0, out + err
        assert "0 injection(s) owed" in out, out
        assert (
            "binding paths: (none — every changed path is inert documentation)"
            in out
        ), out

    def test_an_empty_diff_passes_without_claiming_inert_documentation(
            self, repo, capsys):
        """An empty typed Diff is a calm zero, with an empty-specific reason."""
        head = _git(repo, "rev-parse", "HEAD")
        derived = rp._derived_requirement(repo, head, head)
        assert derived["changed"] == ()
        assert derived["require"] == 0

        capsys.readouterr()
        exit = _handoff(repo)
        out, err = capsys.readouterr()

        assert exit == 0, out + err
        assert "0 injection(s) owed; 0 changed path(s)" in out, out
        assert "binding paths: (none — diff has no changed paths)" in out, (
            "empty handoff did not name its empty diff"
        )
        assert "every changed path is inert documentation" not in out, (
            "empty handoff claimed every changed path was inert documentation"
        )

    def test_an_unreadable_diff_faults_instead_of_inheriting_empty_zero(
            self, repo, capsys):
        """None from _classify_diff remains a loud, typed handoff fault."""
        head = _git(repo, "rev-parse", "HEAD")

        with pytest.raises(rp.RedproofError, match="could not read the diff"):
            rp._derived_requirement(repo, "definitely-not-a-sha", head)

        assert "fatal:" in capsys.readouterr().err

    def test_handoff_faults_when_a_registered_path_is_absent(
            self, repo, capsys):
        """glm-1034clean / glm-1029dash: a restored registration names a path
        that left the working tree (a scratch file the lane cleaned up). handoff
        inherits check's fail-closed FAULT (exit 2), not a calm report."""
        _binding_branch(repo)
        _begin(repo, "router.js")
        (repo / "router.js").write_text("export function route() { return 0; }\n")
        # Restore FIRST, creating a restored entry. Then the registered path
        # leaves the working tree — the exact glm-1034clean / glm-1029dash shape.
        assert _restore(repo, "router.js") == 0
        (repo / "router.js").unlink()
        # PRECONDITION: the restored entry's path is genuinely absent now.
        assert not (repo / "router.js").exists()
        capsys.readouterr()
        exit = _handoff(repo)
        out, err = capsys.readouterr()
        assert exit == 2, out + err
        assert "absent from the working tree" in err, err


def test_handoff_carries_head_identity_so_a_stale_paste_is_detectable(
        repo, capsys):
    """#1140/#1131: handoff's quoted block carries the HEAD it audited so a
    reader can detect a stale paste — a block whose HEAD is not the branch tip
    describes a tree that no longer exists (the lane committed again after
    running handoff). This is a READ aid, not a gate input: the gate derives its
    own number and never consults this block."""
    base, head = _binding_branch(repo)
    # PRECONDITION: the branch has a binding diff so the block is meaningful.
    derived = rp._derived_requirement(repo, base, head)
    assert derived["require"] == 1, (
        f"fixture lost its binding diff; require={derived['require']}")
    capsys.readouterr()
    exit = _handoff(repo)
    out, err = capsys.readouterr()
    assert exit == 2, out + err  # no registry -> FAULT (require>0)
    # The audited HEAD is the branch tip at the moment handoff ran.
    assert f"audited HEAD: {head}" in out, (
        f"handoff did not print the audited HEAD; got:\n{out}")
