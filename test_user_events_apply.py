#!/usr/bin/env python3
"""Red-first tests for ``user_events.apply`` — the application layer (lane D).

Run: ``python3 -m pytest test_user_events_apply.py -q -p no:randomly``

Named production lines whose deletion must fail each test (plan §Lane D):
- D1: the single validation guard ``if not _is_valid_known_file(...): return UNKNOWN``
      → test_torn_and_drifted_files_prove_unknown_not_notapplied
- D2: each of the four terms in ``successor_matches`` (generation, body digest,
      receipt id, adapter/application reference), deleted one at a time, each
      flipping exactly its own sub-case
      → test_a_forged_next_generation_with_any_predicate_mismatch_proves_unknown
- D3: the ``if proof is Proof.APPLIED: finish(); return`` branch in ``reconcile``
      → test_each_row_of_the_proof_table_produces_exactly_one_effect
- D4: the ``register("/comment", ...)`` registry entry
      → test_each_endpoint_replays_through_its_own_adapter (comment case)

Must not fake (plan): valid D1/D2 fixtures produced BY ``DomainFileStore``; D3
crash is a real ``os._exit`` child at a named seam (never ``finish()`` out of
order); D4 uses five real adapters on five real files (not one adapter five
ways over one file); expected marker counts derived at runtime, never a literal.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from user_events import apply, domain_files

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Helpers — fixtures produced BY the store, identity parsing, marker counting.
# ---------------------------------------------------------------------------

def _write_valid(path: Path, *, body: str, generation: int,
                 receipt_id: str, adapter: str, application_ref: str) -> str:
    """Produce a valid managed file through ``DomainFileStore.write``.

    This is the D1 trap's whole point: the digest and lineage come from the
    store, not from the test's arithmetic. Every valid fixture goes through here.
    """
    identity = apply.make_identity(receipt_id, adapter, application_ref)
    domain_files.write(str(path), body, generation=generation, applied=identity)
    return open(path, "r", encoding="utf-8").read()


def _readline_timeout(stream, timeout):
    """Read one line within a bounded wait, or None. Bounds every child wait."""
    import select
    fd = stream.fileno()
    ready, _, _ = select.select([fd], [], [], timeout)
    if not ready:
        return None
    return stream.readline()


def _select_readline_timeout(stream, timeout):
    return _readline_timeout(stream, timeout)


# Fixed receipt/adapter identity used across D1-D3 so the proof has a real
# started-intent to compare against. D4 varies the adapter per route.
REC = "receipt-d"
ADAPTER = "/answer"
APP_REF = "app-ref-d"
COMMITTED = {7}          # generation 7 is the known committed lineage
RESERVED = 8             # the provisional successor reserved by started intent


def _answer_marker(rid: str = REC) -> str:
    return apply._marker_for(ADAPTER, rid)


def _has_answer_marker(text: str, rid: str = REC) -> bool:
    return _answer_marker(rid) in text


# ===========================================================================
# Increment 16 (D1) — ternary proof: torn/drifted → UNKNOWN, not NOT_APPLIED.
# ===========================================================================


class TestD1Ternary:
    """A torn or drifted file proves UNKNOWN, never NOT_APPLIED."""

    def test_torn_and_drifted_files_prove_unknown_not_notapplied(self, tmp_path):
        # PRODUCTION LINE WHOSE DELETION FAILS THIS TEST:
        #   the ``if not _is_valid_known_file(...): return Proof.UNKNOWN`` guard
        #   in prove_applied. Delete it and the torn + drifted fixtures collapse
        #   to NOT_APPLIED (they fall through to the marker search, which finds
        #   nothing) — the duplicate-effect bug law 8 exists to prevent. The
        #   in-lineage-no-marker fixture already reaches NOT_APPLIED THROUGH the
        #   guard, so it is unchanged by the deletion: that is what makes the red
        #   discriminating rather than a suite that moves together.
        path = tmp_path / "questions.md"
        base_body = "an open question\nmore context lines\n"

        # Fixture 1 — torn: a store-produced valid file whose body is then
        # truncated mid-record (footer intact, digest now mismatched). The store
        # produced the valid original; the truncation is the tear under test.
        text1_valid = _write_valid(
            path, body=base_body, generation=7,
            receipt_id=REC, adapter=ADAPTER, application_ref=APP_REF)
        torn = text1_valid[:len(text1_valid) // 2]   # cut mid-record
        # Precondition: the tear actually broke validation (footer region hit or
        # body shortened so the digest no longer covers it). Derived at runtime.
        assert domain_files.parse_metadata(torn) is None or \
            not domain_files.validate(torn), \
            "precondition: the torn fixture actually fails validation"
        assert not _has_answer_marker(torn), \
            "precondition: the torn fixture carries no answer marker"

        # Fixture 2 — drifted generation: a VALID file (store-produced, correct
        # digest) at a generation outside committed lineage and not the reserved
        # successor. The store produced it; the drift is the generation we asked
        # the store to write.
        drifted = _write_valid(
            tmp_path / "drifted.md", body=base_body, generation=99,
            receipt_id=REC, adapter=ADAPTER, application_ref=APP_REF)
        assert domain_files.validate(drifted), \
            "precondition: the drifted fixture is itself a valid file " \
            "(its drift is the generation, not the digest)"
        assert apply.parse_identity(
            domain_files.parse_metadata(drifted)["last_applied"]) == (REC, ADAPTER, APP_REF), \
            "precondition: the drifted fixture's identity is intact"
        assert not _has_answer_marker(drifted), \
            "precondition: the drifted fixture carries no answer marker"

        # Fixture 3 — valid, in-lineage, no marker: the NOT_APPLIED case. This
        # one is unchanged by the red, which is the whole point.
        inlineage = _write_valid(
            tmp_path / "inlineage.md", body=base_body, generation=7,
            receipt_id=REC, adapter=ADAPTER, application_ref=APP_REF)
        assert domain_files.validate(inlineage), \
            "precondition: the in-lineage fixture is valid"
        assert domain_files.parse_metadata(inlineage)["domain_generation"] in COMMITTED, \
            "precondition: the in-lineage fixture's generation is committed"
        assert not _has_answer_marker(inlineage), \
            "precondition: the in-lineage fixture carries no marker"

        common = dict(receipt_id=REC, adapter=ADAPTER, application_ref=APP_REF,
                      reserved_successor=RESERVED, committed_lineage=COMMITTED,
                      has_marker=_has_answer_marker)

        # Torn and drifted must prove UNKNOWN — never NOT_APPLIED.
        assert apply.prove_applied(torn, **common) is apply.Proof.UNKNOWN
        assert apply.prove_applied(drifted, **common) is apply.Proof.UNKNOWN
        # Valid + in-lineage + no marker proves NOT_APPLIED — and this is the
        # case that STAYS put when the guard is deleted (discriminating red).
        assert apply.prove_applied(inlineage, **common) is apply.Proof.NOT_APPLIED


# ===========================================================================
# Increment 17 (D2) — reserved successor: four predicates, four reds.
# ===========================================================================


# A real child interpreter is not needed for D2; the four forgeries are
# store-produced files with one parameter wrong. The body carries the marker so
# each forged file "claims" to be applied — law 7 says a forged marker alone
# never suffices, and each predicate mismatch proves UNKNOWN.


def _successor_fixture(tmp_path, *, name, body, generation, receipt_id,
                       adapter, application_ref) -> str:
    """A store-produced file claiming the reserved-successor slot."""
    return _write_valid(tmp_path / name, body=body, generation=generation,
                        receipt_id=receipt_id, adapter=adapter,
                        application_ref=application_ref)


class TestD2Reserve:
    """A forged next-generation file with any one predicate mismatch proves
    UNKNOWN; the all-match case proves APPLIED. Each predicate is an independent
    red (delete one term, exactly its sub-case flips)."""

    def test_a_forged_next_generation_with_any_predicate_mismatch_proves_unknown(
            self, tmp_path):
        # PRODUCTION LINE WHOSE DELETION FAILS THIS TEST (four of them, one per
        # sub-case): the four reserved-successor predicates, each a single line
        # in exactly one place (a predicate checked twice is a hollow red):
        #   (1) generation term in successor_matches
        #   (2) the ``if not domain_files.validate(text): return False`` line in
        #       _is_valid_known_file  (the body-digest predicate — it applies to
        #       every valid file, so it lives in the general guard, not doubled
        #       in successor_matches)
        #   (3) receipt-id term in successor_matches
        #   (4) adapter/application-reference terms in successor_matches
        # Deleting one flips EXACTLY its own sub-case to APPLIED and leaves the
        # other three UNKNOWN. Verified separately in the red run; here all four
        # mismatches prove UNKNOWN and the all-match proves APPLIED.
        marker_body = "an answer\n" + _answer_marker() + "\n"

        # All-match: the legitimate reserved successor. Store-produced.
        allmatch = _successor_fixture(
            tmp_path, name="allmatch.md", body=marker_body, generation=RESERVED,
            receipt_id=REC, adapter=ADAPTER, application_ref=APP_REF)
        assert domain_files.validate(allmatch), \
            "precondition: the all-match fixture is a valid file"

        # (1) generation mismatch: valid file, wrong generation (not RESERVED,
        #     not in COMMITTED). Store-produced with the forged generation.
        gen_bad = _successor_fixture(
            tmp_path, name="gen_bad.md", body=marker_body, generation=RESERVED + 5,
            receipt_id=REC, adapter=ADAPTER, application_ref=APP_REF)
        assert domain_files.validate(gen_bad), \
            "precondition: gen-mismatch is valid (its drift is the generation)"

        # (2) body-digest mismatch: store-produced valid successor, then ONE body
        #     byte tampered so the digest no longer validates. The tamper is the
        #     forgery under test; the store produced the valid base.
        digest_bad_valid = _successor_fixture(
            tmp_path, name="digest_bad.md", body=marker_body, generation=RESERVED,
            receipt_id=REC, adapter=ADAPTER, application_ref=APP_REF)
        digest_bad = digest_bad_valid.replace("an answer", "an ansxer", 1)
        assert domain_files.parse_metadata(digest_bad)["domain_generation"] == RESERVED, \
            "precondition: digest-mismatch is at the reserved generation"
        assert not domain_files.validate(digest_bad), \
            "precondition: the body tamper actually broke validation"

        # (3) receipt-id mismatch: valid file, wrong receipt in the identity.
        receipt_bad = _successor_fixture(
            tmp_path, name="receipt_bad.md", body=marker_body, generation=RESERVED,
            receipt_id="receipt-FORGED", adapter=ADAPTER, application_ref=APP_REF)
        assert domain_files.validate(receipt_bad), \
            "precondition: receipt-mismatch is a valid file"

        # (4) adapter/application-reference mismatch: valid file, wrong adapter.
        appref_bad = _successor_fixture(
            tmp_path, name="appref_bad.md", body=marker_body, generation=RESERVED,
            receipt_id=REC, adapter="/comment", application_ref=APP_REF)
        assert domain_files.validate(appref_bad), \
            "precondition: adapter-mismatch is a valid file"

        common = dict(receipt_id=REC, adapter=ADAPTER, application_ref=APP_REF,
                      reserved_successor=RESERVED, committed_lineage=COMMITTED,
                      has_marker=_has_answer_marker)

        # All four single-predicate mismatches prove UNKNOWN.
        assert apply.prove_applied(gen_bad, **common) is apply.Proof.UNKNOWN
        assert apply.prove_applied(digest_bad, **common) is apply.Proof.UNKNOWN
        assert apply.prove_applied(receipt_bad, **common) is apply.Proof.UNKNOWN
        assert apply.prove_applied(appref_bad, **common) is apply.Proof.UNKNOWN
        # The all-match proves APPLIED — without this, `return Proof.UNKNOWN`
        # unconditionally would pass the four above.
        assert apply.prove_applied(allmatch, **common) is apply.Proof.APPLIED


# ===========================================================================
# Increment 18 (D3) — reconciliation: exactly one effect per proof-table row.
# ===========================================================================

# A real child that crashes at seam A: it records started intent (prints
# APPLYING) then os._exit BEFORE any domain write. The file is left at its seed
# (committed generation, no marker) — "after applying, before domain write".
_CHILD_SEAM_A = textwrap.dedent(r"""
    import os, sys
    sys.path.insert(0, sys.argv[2])
    sys.stdout.write("APPLYING\n"); sys.stdout.flush()
    # Named seam: started intent recorded, domain write NOT yet attempted.
    os._exit(0)
""")

# A real child that crashes at seam B: it completes the durable domain write
# (generation = reserved successor, marker present, fsynced + renamed) then
# os._exit BEFORE the journal finish — "after domain fsync, before finish".
_CHILD_SEAM_B = textwrap.dedent(r"""
    import os, sys
    sys.path.insert(0, sys.argv[3])
    from user_events import domain_files, apply
    path = sys.argv[1]
    receipt = sys.argv[2]
    marker = apply._marker_for("/answer", receipt)
    identity = apply.make_identity(receipt, "/answer", "app-ref-d")
    # The domain write lands fully (temp + fsync + replace); then we die.
    domain_files.write(path, "seed body\n" + marker,
                       generation=8, applied=identity)
    os._exit(0)   # named seam: after domain fsync, before finish
""")


def _count_markers(text: str, rid: str = REC) -> int:
    return text.count(_answer_marker(rid))


class TestD3Reconcile:
    """Each row of the post-crash proof table produces exactly one effect,
    measured by counting marker occurrences in the file."""

    def test_each_row_of_the_proof_table_produces_exactly_one_effect(self, tmp_path):
        # PRODUCTION LINE WHOSE DELETION FAILS THIS TEST:
        #   the ``if proof is Proof.APPLIED: finish(); return proof`` branch in
        #   reconcile. Delete it and the after-fsync case (marker already on disk
        #   from the crashed write) gets a SECOND effect appended — marker count
        #   2 instead of 1.
        path = tmp_path / "questions.md"

        def append_answer_effect(text, rid=REC):
            return apply.ApplicationAdapter(ADAPTER).append_effect(text, rid)

        def make_finish_log():
            calls = []
            return (lambda: calls.append(True)), calls

        # ---- Row 1: crash AFTER APPLYING, BEFORE domain write ⇒ NOT_APPLIED.
        # Seed a committed file (generation 7, no marker); a real child dies at
        # seam A before touching it; reconciliation must apply EXACTLY once.
        _write_valid(path, body="seed body\n", generation=7,
                     receipt_id=REC, adapter=ADAPTER, application_ref=APP_REF)
        seed_text = open(path, encoding="utf-8").read()
        seed_markers = _count_markers(seed_text)
        assert seed_markers == 0, "precondition: seed carries no marker"

        proc_a = subprocess.Popen(
            [sys.executable, "-c", _CHILD_SEAM_A, str(path), REPO_ROOT],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            line = _readline_timeout(proc_a.stdout, 15.0)
            if line is None:
                self.fail("seam-A child never signalled: %s" % proc_a.stderr.read())
            assert line.strip() == "APPLYING"
        finally:
            proc_a.wait(timeout=10.0)
        # The file is unchanged by the seam-A crash (no domain write happened).
        assert open(path, encoding="utf-8").read() == seed_text, \
            "precondition: seam A left the seed byte-identical (no write happened)"

        finish, finish_calls = make_finish_log()
        proof_a = apply.reconcile(
            str(path), receipt_id=REC, adapter=ADAPTER, application_ref=APP_REF,
            append_effect=append_answer_effect, reserved_successor=RESERVED,
            committed_lineage=COMMITTED, has_marker=_has_answer_marker,
            finish=finish)
        assert proof_a is apply.Proof.NOT_APPLIED
        text_after_a = open(path, encoding="utf-8").read()
        # Exactly one effect: marker count rose by exactly one from the seed.
        assert _count_markers(text_after_a) == seed_markers + 1, (
            "after-applying reconciliation must apply exactly once; "
            "markers %d -> %d" % (seed_markers, _count_markers(text_after_a)))
        assert len(finish_calls) == 1, "NOT_APPLIED finishes exactly once"

        # ---- Row 2: crash AFTER DOMAIN FSYNC, BEFORE finish ⇒ APPLIED.
        # Re-seed a committed file; a real child completes the durable write
        # (generation 8 + marker) then dies before finish; reconciliation must
        # finish ONLY — no second marker.
        _write_valid(path, body="seed body\n", generation=7,
                     receipt_id=REC, adapter=ADAPTER, application_ref=APP_REF)
        proc_b = subprocess.Popen(
            [sys.executable, "-c", _CHILD_SEAM_B, str(path), REC, REPO_ROOT],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            proc_b.wait(timeout=15.0)
        except subprocess.TimeoutExpired:
            proc_b.kill()
            raise
        crashed_text = open(path, encoding="utf-8").read()
        crashed_markers = _count_markers(crashed_text)
        # Precondition, derived at runtime: the crashed write landed one marker
        # at the reserved successor generation. If this is 0 or 2, the rest of
        # the assertion cannot mean what it is named for.
        assert crashed_markers == 1, (
            "precondition: seam B landed exactly one marker (got %d); "
            "without this the count assertion below is vacuous" % crashed_markers)
        assert domain_files.parse_metadata(crashed_text)["domain_generation"] == RESERVED, \
            "precondition: seam B wrote the reserved successor generation"

        finish2, finish_calls2 = make_finish_log()
        proof_b = apply.reconcile(
            str(path), receipt_id=REC, adapter=ADAPTER, application_ref=APP_REF,
            append_effect=append_answer_effect, reserved_successor=RESERVED,
            committed_lineage=COMMITTED, has_marker=_has_answer_marker,
            finish=finish2)
        assert proof_b is apply.Proof.APPLIED
        text_after_b = open(path, encoding="utf-8").read()
        # The expected count is the crashed count (one) — reconciliation adds NONE.
        # Derived from the observed crashed count, never a literal tuned here.
        assert _count_markers(text_after_b) == crashed_markers, (
            "after-fsync reconciliation must finish ONLY (no second effect); "
            "markers %d -> %d" % (crashed_markers, _count_markers(text_after_b)))
        assert len(finish_calls2) == 1, "APPLIED finishes (once), without writing"


# ===========================================================================
# Increment 19 (D4) — five adapters, five files; none reads another's format.
# ===========================================================================


# The five write routes, derived from the registry — never a hand-copied list.
# Deleting one registry entry drops it here, failing exactly that case.
def _registered_routes():
    return sorted(apply.ADAPTERS.keys())


class TestD4Adapters:
    """Each endpoint replays through its own adapter onto its own file, and an
    adapter cannot read another adapter's payload."""

    def test_each_endpoint_replays_through_its_own_adapter(self, tmp_path):
        # PRODUCTION LINE WHOSE DELETION FAILS THIS TEST (the comment case):
        #   the ``register("/comment", ApplicationAdapter("/comment"))`` entry
        #   installed by ``_install_default_adapters``. Removing it makes
        #   ``adapter_for("/comment")`` raise KeyError, failing exactly the
        #   comment iteration and leaving the other four green.
        routes = _registered_routes()
        # Precondition, derived at runtime: all five write routes are present,
        # so a missing one is a real regression and not a vacuous pass. Compared
        # as a set — order is the registry's, not the test's assumption.
        assert set(routes) == {"/answer", "/ask", "/comment", "/command", "/tint"}, (
            "precondition: the five write routes are registered (got %r); "
            "the loop below is only meaningful if all five are present" % routes)

        for route in routes:
            adapter = apply.adapter_for(route)
            receipt = "receipt-" + route.strip("/")
            app_ref = "app-" + route.strip("/")
            # Each route gets its OWN file — not one adapter five ways over one.
            path = tmp_path / (route.strip("/").replace("/", "-") + ".md")
            _write_valid(path, body="seed for %s\n" % route, generation=7,
                         receipt_id=receipt, adapter=route, application_ref=app_ref)
            seed = open(path, encoding="utf-8").read()
            assert adapter.marker_count(seed, receipt) == 0, \
                "precondition: %s seed has no marker" % route

            # Replay through this adapter: append its effect, prove APPLIED.
            new_body = adapter.append_effect(seed, receipt)
            identity = apply.make_identity(receipt, route, app_ref)
            domain_files.write(str(path), new_body, generation=RESERVED,
                               applied=identity)
            applied_text = open(path, encoding="utf-8").read()
            proof = adapter.prove(
                applied_text, receipt_id=receipt, application_ref=app_ref,
                reserved_successor=RESERVED, committed_lineage=COMMITTED)
            assert proof is apply.Proof.APPLIED, (
                "%s did not prove APPLIED after its own replay" % route)
            assert adapter.marker_count(applied_text, receipt) == 1, \
                "%s landed exactly one of its own markers" % route

    def test_an_adapter_refuses_another_adapters_payload(self, tmp_path):
        # An adapter proving a receipt against a file ANOTHER adapter wrote must
        # fail closed (not APPLIED). Two independent walls: the marker is
        # route-tagged so the wrong adapter's has_marker finds nothing, and the
        # identity's adapter field does not match. Uses /answer vs /command (not
        # /comment) so the D4 /comment-deletion red fails exactly the comment
        # replay case and leaves this test green.
        answer = apply.adapter_for("/answer")
        other = apply.adapter_for("/command")
        receipt = "receipt-x"

        # /answer writes its marker and identity onto the file.
        path = tmp_path / "cross.md"
        body = "seed\n" + answer.marker(receipt) + "\n"
        identity = apply.make_identity(receipt, "/answer", "app-x")
        domain_files.write(str(path), body, generation=RESERVED, applied=identity)
        text = open(path, encoding="utf-8").read()

        # /answer proves its own work APPLIED (control).
        assert answer.prove(text, receipt_id=receipt, application_ref="app-x",
                            reserved_successor=RESERVED,
                            committed_lineage=COMMITTED) is apply.Proof.APPLIED
        # /command cannot read /answer's payload: its marker is absent AND the
        # identity's adapter field is /answer, not /command. Either alone bars it.
        cross = other.prove(text, receipt_id=receipt, application_ref="app-x",
                            reserved_successor=RESERVED,
                            committed_lineage=COMMITTED)
        assert cross is not apply.Proof.APPLIED, (
            "/command must not prove /answer's payload APPLIED; got %r" % cross)
        # Precondition, derived at runtime: the two markers actually differ, so
        # the refusal is a real format boundary and not an accidental string eq.
        assert answer.marker(receipt) != other.marker(receipt), \
            "precondition: answer and command markers differ (format boundary)"
        assert other.marker_count(text, receipt) == 0, \
            "precondition: /command finds zero of its own markers in the file"


if __name__ == "__main__":
    import unittest
    unittest.main()
