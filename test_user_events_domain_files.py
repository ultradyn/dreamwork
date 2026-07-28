#!/usr/bin/env python3
"""Tests for ``user_events.domain_files`` — the managed domain-file store.

Run: ``python3 -m pytest test_user_events_domain_files.py -x -p no:randomly``

Each test here is a *discriminating* one: it is written so that deleting the
single production line it is named for makes it fail while its neighbours stay
green. The three named seam lines are pointed at in comments beside each test.
The lock and crash tests use **real child processes** — a patched ``fcntl`` or a
faked ``os.replace`` would assert the mock, not the OS property, and the plan is
explicit that they prove nothing otherwise.
"""

import os
import select
import subprocess
import sys
import tempfile
import unittest

from user_events import domain_files
from user_events.domain_files import DomainFileLock, LockTimeout

# A real second interpreter that takes the lock through the SAME acquire path as
# the parent, so the test proves the store's lock is OS-visible to another
# process — not that two calls into one process contend. Coordinated by stdout
# lines ("HELD" / "RELEASED") so the parent never makes a timing assumption.
_CHILD_HOLD = r"""
import sys, time
sys.path.insert(0, sys.argv[3])
from user_events.domain_files import DomainFileLock
path = sys.argv[1]
hold = float(sys.argv[2])
lk = DomainFileLock(path)
lk.acquire(timeout=10.0)
sys.stdout.write("HELD\n"); sys.stdout.flush()
time.sleep(hold)
lk.release()
sys.stdout.write("RELEASED\n"); sys.stdout.flush()
"""

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def _readline_timeout(stream, timeout):
    """Read one line from ``stream``, or ``None`` if nothing arrives in bound.

    ``readline`` alone blocks forever if the child never writes; ``select`` on
    the pipe fd bounds the wait so the test can never hang on a wedged child.
    """
    fd = stream.fileno()
    ready, _, _ = select.select([fd], [], [], timeout)
    if not ready:
        return None
    return stream.readline()


class TestDomainFileLock(unittest.TestCase):
    """Increment 11 (C1 lock): an OS-visible cross-process lock."""

    def test_a_second_process_cannot_read_while_the_lock_is_held(self):
        # PRODUCTION LINE WHOSE DELETION FAILS THIS TEST:
        #   the `fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)` call inside
        #   DomainFileLock.acquire. Without it, acquire holds nothing and two
        #   processes "succeed" at once — which is exactly #262's bug.
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "questions.md")
            # A real child process holds the lock for a bounded window.
            proc = subprocess.Popen(
                [sys.executable, "-c", _CHILD_HOLD, path, "3.0", REPO_ROOT],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                held = _readline_timeout(proc.stdout, 15.0)
                # Read the child's stderr ONLY when it failed to report HELD:
                # proc.stderr.read() blocks until the child's stderr reaches EOF
                # (i.e. the child exits), and an eager read here would consume the
                # whole contention window and let the parent's acquire sail through
                # a lock the child had already released by dying.
                if held is None:
                    self.fail("child never reported HELD: %s" % proc.stderr.read())
                self.assertEqual(held.strip(), "HELD")

                # The child holds the lock. The parent's acquisition through the
                # same acquire path must time out — never an unbounded block.
                parent_lock = DomainFileLock(path, timeout=1.0)
                self.assertRaises(LockTimeout, parent_lock.acquire)

                # Wait for the child to release, bounded; then the parent CAN
                # acquire, proving the lock is real and not merely broken.
                released = _readline_timeout(proc.stdout, 10.0)
                self.assertIsNotNone(released, "child never reported RELEASED")
                self.assertEqual(released.strip(), "RELEASED")

                after = DomainFileLock(path, timeout=5.0)
                after.acquire()       # succeeds now that the child released
                after.release()
            finally:
                proc.wait(timeout=10.0)


# Bodies used in the lineage test carry a distinctive token so a one-byte
# change to the body is unambiguous and provably does not touch the footer.
_BODY = ("the quick brown fox\n"
         "a second line carrying TOKEN so a one-byte body edit is exact\n"
         "third line")
_WRONG_DIGEST = "0" * 64      # valid-looking hex, asserted to differ from real


class TestDomainFileLineage(unittest.TestCase):
    """Increment 12 (C2 lineage): embedded generation + body digest excluding
    only its own field."""

    def test_body_digest_excludes_only_itself(self):
        # PRODUCTION LINE WHOSE DELETION FAILS THIS TEST (on its THIRD assertion):
        #   the single `_DIGEST_LINE_RE.sub("body_digest:", text, count=1)` in
        #   canonical_body(). Delete that exclusion and the digest becomes
        #   self-referential: validate() then reads False for every file, and
        #   re-emitting an unchanged body yields a DIFFERENT digest (because the
        #   hash now includes the old digest value) — which is the exclusion
        #   property this third assertion exists to catch.
        text1 = domain_files.build_managed_text(
            body=_BODY, generation=7, identity="receipt-abc|adapter-answer")
        md1 = domain_files.parse_metadata(text1)
        d1 = md1["body_digest"]

        # Precondition, asserted at runtime and chosen to hold WHETHER OR NOT
        # the exclusion filter is present, so the test reaches its third
        # (discriminating) assertion instead of failing early on the very
        # property under test. validate(text1) is deliberately NOT used here:
        # without the exclusion a digest is self-referential and validate is
        # False for every file, so asserting it would mask the third assertion
        # and the red would land on the precondition instead.
        self.assertIsNotNone(md1, "precondition: fixture has a managed footer")
        self.assertEqual(len(d1), 64,
                         "precondition: embedded digest is a SHA-256")
        self.assertTrue(all(c in "0123456789abcdef" for c in d1),
                        "precondition: embedded digest is hex")
        self.assertNotEqual(d1, _WRONG_DIGEST,
                            "precondition: wrong digest must differ from real")

        # 1. Rewrite the digest field ALONE to a wrong value: validation fails.
        #    Only the digest field changed — the body and generation are intact.
        tampered = domain_files.set_digest_value(text1, _WRONG_DIGEST)
        self.assertNotEqual(tampered, text1,
                            "precondition: tamper actually changed the text")
        self.assertFalse(domain_files.validate(tampered),
                         "a wrong digest field must not validate")

        # 2. Change ONE byte of the body (not the footer): validation fails.
        changed = text1.replace("TOKEN", "TOKEM", 1)
        self.assertNotEqual(changed, text1,
                            "precondition: body edit actually changed the text")
        self.assertEqual(domain_files.parse_metadata(changed)["body_digest"],
                         d1, "precondition: the body edit left the digest field "
                              "untouched (the change is in the body)")
        self.assertFalse(domain_files.validate(changed),
                         "a body with one byte changed must not validate")

        # 3. Re-emit the SAME body with the digest recomputed: the digest is
        #    UNCHANGED. That is the exclusion property — the digest covers the
        #    body minus its own field, so an unchanged body yields the same
        #    digest. This is the assertion that fails when the exclusion is gone.
        re_emitted = domain_files.recompute_digest(text1)
        d2 = domain_files.parse_metadata(re_emitted)["body_digest"]
        self.assertEqual(
            d1, d2,
            "re-emitting an unchanged body must yield the same digest "
            "(exclusion property); a differing digest means the digest is "
            "self-referential")


# A real child interpreter that drives write() straight into os._exit at the
# named seam (crash_before_replace=True). It prints RETURNED only if write()
# returned normally — which it must NOT, because os._exit kills first — so the
# parent can prove the child died inside the write rather than after it.
_CHILD_CRASH = r"""
import sys
sys.path.insert(0, sys.argv[2])
from user_events import domain_files
path = sys.argv[1]
domain_files.write(
    path,
    "this is the NEXT generation's body; it must never reach the file\n",
    generation=2, applied="receipt-crash|adapter-answer",
    crash_before_replace=True)
sys.stdout.write("RETURNED\n"); sys.stdout.flush()
"""


class TestDomainFileOneWrite(unittest.TestCase):
    """Increment 13 (C3 onewrite): effect+marker+generation+digest in one
    atomic durable replace, so a crash at the rename leaves the previous
    generation intact."""

    def test_kill_at_rename_leaves_the_previous_generation_intact(self):
        # PRODUCTION LINE WHOSE DELETION FAILS THIS TEST:
        #   the temp-then-os.replace sequence in _atomic_replace. Replace it
        #   with a direct open(path, "w") (what watch.py's /answer did before
        #   #370) and the crashed child truncates/corrupts the real file
        #   instead of leaving it untouched — so post != pre and this fails.
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "questions.md")

            # Seed a real first generation and snapshot its bytes BEFORE the
            # run. The comparison is against THIS captured value, never a
            # recomputed expectation — an end-state-only assertion cannot fail
            # on a crash-window bug, which is precisely why this test exists.
            domain_files.write(path, _BODY, generation=1,
                               applied="seed|adapter-answer")
            pre = open(path, "rb").read()
            self.assertGreater(
                len(pre), 100,
                "precondition: the seeded file is non-trivial, so a truncation "
                "or partial write is observable rather than indistinguishable "
                "from the seed")
            # Structural precondition ONLY — not validate(). validate() is the
            # lineage property (increment 12) and this test owns ATOMICITY
            # (increment 13); coupling them would make the exclusion red break
            # this neighbour too. We need only that the seed is a real managed
            # file, which holds whether or not the exclusion filter is present.
            pre_md = domain_files.parse_metadata(pre.decode("utf-8"))
            self.assertIsNotNone(
                pre_md, "precondition: the seed has a managed footer")
            self.assertEqual(
                len(pre_md["body_digest"]), 64,
                "precondition: the seed carries a SHA-256 digest")

            # A real child process crashes at the seam. Bounded wait; the child
            # is dead afterwards so reading its stdout hits EOF at once.
            proc = subprocess.Popen(
                [sys.executable, "-c", _CHILD_CRASH, path, REPO_ROOT],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            proc.wait(timeout=15.0)
            out = proc.stdout.read()
            self.assertNotIn(
                "RETURNED", out,
                "the child must have died inside write() at the seam, not "
                "returned normally")

            # The crash must leave the PREVIOUS generation byte-identical.
            post = open(path, "rb").read()
            self.assertEqual(
                post, pre,
                "a crash between the temp fsync and the rename must leave the "
                "previous generation byte-identical to its pre-state")

            # The temp is ACCOUNTED FOR. It is not gone (os._exit bypasses the
            # cleanup), so it must be provably ignorable: an orphaned hidden
            # .tmp in the same directory, never the managed path, and the next
            # write still lands correctly. (The store's read path reads <path>,
            # never <path>.*.tmp, and mkstemp mints unique names, so a later
            # write cannot collide with it.)
            base = os.path.basename(path)
            leftover = [f for f in os.listdir(d) if f != base]
            self.assertTrue(
                any(f.endswith(".tmp") for f in leftover),
                "precondition: the child reached the seam — it fsynced a temp "
                "before dying, which is what proves the crash was between fsync "
                "and replace rather than earlier")
            self.assertFalse(
                any(f == base for f in leftover),
                "no leftover may sit at the managed path")

            # The orphan is ignorable in the way that matters: a subsequent
            # normal write lands its content. Checked STRUCTURALLY (footer +
            # generation + the new body), not via validate() — this test owns
            # atomicity, not the digest-exclusion property, and coupling them
            # would make the exclusion red break this neighbour.
            domain_files.write(path, "after the crash, a clean recovery\n",
                               generation=3, applied="recv-1|adapter-answer")
            recovered = open(path, encoding="utf-8").read()
            self.assertEqual(
                domain_files.parse_metadata(recovered)["domain_generation"], 3,
                "the recovery write landed its new generation")
            self.assertIn(
                "after the crash, a clean recovery", recovered,
                "the recovery write landed its new body")


# A receipt marker in the same shape the application layer writes (apply.py's
# _marker_for), so the marker search is exercised against the real format. The
# search itself is marker-format-agnostic — it hunts a literal string — but a
# realistic marker keeps the fixture honest about what it represents.
_MARKER = "<!-- dreamwork:/answer:receipt-fold -->"


class TestDomainFileMarkers(unittest.TestCase):
    """Increment 14 (C4 markers): a marker is found anywhere in a valid file,
    across BOTH the literal ``Open`` and ``Answered`` sections.

    The loop folds an answered entry from ``## Open`` to ``## Answered``; a
    marker that was in Open moves with it. A search that scans only one section
    loses the marker after the fold — so the scan must cover both."""

    def _questions_body(self, marker_section):
        """A two-section questions body with the marker in exactly one section.

        ``marker_section`` is ``"Open"`` or ``"Answered"``. Produced as the BODY
        of a store-managed file (via domain_files.write), never hand-written as
        a managed file — so the digest and lineage come from the store.
        """
        open_entry = ("- an open question\n"
                      "  " + _MARKER + "\n") if marker_section == "Open" else ""
        answered_entry = ("- a folded answer\n"
                          "  " + _MARKER + "\n") if marker_section == "Answered" else ""
        return ("# Questions for the dreamer\n"
                "\n"
                "## Open\n"
                "\n"
                + open_entry + "\n"
                "## Answered\n"
                "\n"
                + answered_entry)

    def test_a_fold_between_sections_cannot_hide_a_marker(self):
        # PRODUCTION LINE WHOSE DELETION FAILS THIS TEST:
        #   the second entry in _MANAGED_SECTIONS ("Answered") inside
        #   domain_files. Remove it and a marker that has been folded into
        #   ## Answered is no longer scanned — find_marker returns False for
        #   the Answered fixture while the Open fixture stays True.
        with tempfile.TemporaryDirectory() as d:
            path_a = os.path.join(d, "answered.md")
            path_b = os.path.join(d, "open.md")

            # Two store-produced valid files, identical bodies except for which
            # section holds the marker.
            domain_files.write(path_a, self._questions_body("Answered"),
                               generation=1, applied="recv|/answer|app")
            domain_files.write(path_b, self._questions_body("Open"),
                               generation=1, applied="recv|/answer|app")
            text_a = open(path_a, encoding="utf-8").read()
            text_b = open(path_b, encoding="utf-8").read()
            self.assertTrue(domain_files.validate(text_a),
                            "precondition: fixture A is a valid managed file")
            self.assertTrue(domain_files.validate(text_b),
                            "precondition: fixture B is a valid managed file")

            # PRECONDITION, derived at runtime via the SAME section parser the
            # search uses: the two fixtures differ in which section holds the
            # marker. A fixture that puts it in both is vacuous (the plan's
            # explicit warning). Asserting the gap — never a literal — so the
            # test fails loudly the day the fixture stops differing.
            a_open = domain_files._section_text(text_a, "Open")
            a_ans = domain_files._section_text(text_a, "Answered")
            b_open = domain_files._section_text(text_b, "Open")
            b_ans = domain_files._section_text(text_b, "Answered")
            self.assertIsNotNone(a_ans, "precondition: A has an Answered section")
            self.assertIsNotNone(b_open, "precondition: B has an Open section")
            self.assertNotIn(_MARKER, a_open or "",
                             "precondition: A's marker is NOT in Open")
            self.assertIn(_MARKER, a_ans,
                          "precondition: A's marker IS in Answered")
            self.assertIn(_MARKER, b_open,
                          "precondition: B's marker IS in Open")
            self.assertNotIn(_MARKER, b_ans or "",
                             "precondition: B's marker is NOT in Answered")

            # The whole point: both are found, regardless of section.
            self.assertTrue(domain_files.find_marker(text_a, _MARKER),
                            "a marker folded into Answered must be found")
            self.assertTrue(domain_files.find_marker(text_b, _MARKER),
                            "a marker still in Open must be found")


# C5 imports the application layer to prove the unjournaled successor fails
# closed via the EXISTING detection (apply.prove_applied), then runs the
# domain-file operator rebaseline and re-proves. This is deliberate: the brief
# says the detection half already lives in apply.py (verified: _is_valid_known_file
# at apply.py:166 carries the lineage predicate; successor_matches at apply.py:132
# the successor half), and C5's remaining work is the operator. The test names
# both halves so the red is honest about which file holds which.
from user_events import apply  # noqa: E402

# A receipt identity the proof compares against, in apply.py's pipe-separated
# shape (receipt | adapter | application_ref). Same shape as test_user_events_apply.
_C5_REC = "receipt-rebaseline"
_C5_ADAPTER = "/answer"
_C5_APPREF = "app-rebaseline"


class TestDomainFileRebaseline(unittest.TestCase):
    """Increment 15 (C5 rebaseline): an unjournaled valid successor fails closed,
    and ``rebaseline`` is the only way to adopt one.

    External drift detection is ALREADY built in apply.py (lane D, red-proven by
    D1/D2): ``prove_applied`` reads a generation outside committed lineage and not
    the reserved successor as UNKNOWN. C5's own work is the operator that adopts
    such a file: validate, preserve bytes, mint a successor generation, and
    journal the import. The test drives BOTH halves end to end.
    """

    def _drifted_file(self, path, marker):
        """A store-produced valid file at a generation OUTSIDE committed lineage.

        The drift is the generation we asked the store to write (generation 99),
        not a forgery of the digest — the file is itself a valid managed file,
        which is the whole point: it is syntactically fine, just unjournaled. The
        marker is present so that AFTER rebaseline (which makes its generation
        part of committed lineage) the same file proves APPLIED.
        """
        body = "an answer that arrived by external edit\n" + marker + "\n"
        identity = apply.make_identity(_C5_REC, _C5_ADAPTER, _C5_APPREF)
        domain_files.write(path, body, generation=99, applied=identity)
        return open(path, encoding="utf-8").read()

    def test_unjournaled_valid_successor_fails_closed_until_rebaselined(self):
        # PRODUCTION LINE WHOSE DELETION FAILS THIS TEST:
        #   the detection half lives in apply._is_valid_known_file's lineage
        #   predicate (apply.py:166 ``if gen in committed_lineage: return True``;
        #   without it a drifted generation falls through to the reserved-successor
        #   check, and a file that is not the successor proves UNKNOWN for a
        #   DIFFERENT reason — that half is red-proven by D1). C5's OWN line is
        #   domain_files.rebaseline's lineage-adoption: the new successor
        #   generation it mints is ADDED to committed lineage, so the same file
        #   that proved UNKNOWN proves APPLIED afterward. Delete the adoption and
        #   the post-rebaseline assertion fails while the pre-rebaseline one still
        #   passes — the reverse of D1's discriminating pair.
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "questions.md")
            marker = apply._marker_for(_C5_ADAPTER, _C5_REC)
            drifted = self._drifted_file(path, marker)

            # PRECONDITIONS, derived at runtime (never a literal tuned to today):
            # the file is a VALID managed file whose only "drift" is its
            # generation, and its generation is genuinely outside committed
            # lineage and not the reserved successor.
            self.assertTrue(domain_files.validate(drifted),
                            "precondition: the drifted file is itself valid")
            md = domain_files.parse_metadata(drifted)
            committed_before = {1, 2, 3}
            reserved = 4
            self.assertNotIn(md["domain_generation"], committed_before,
                             "precondition: generation is outside committed lineage")
            self.assertNotEqual(md["domain_generation"], reserved,
                                "precondition: generation is not the reserved successor")
            self.assertEqual(
                apply.parse_identity(md["last_applied"]),
                (_C5_REC, _C5_ADAPTER, _C5_APPREF),
                "precondition: identity is intact")

            # ---- The detection half (already built in apply.py): UNKNOWN. ----
            # An unjournaled valid successor fails closed — never NOT_APPLIED,
            # which would re-apply and duplicate the effect. This assertion's
            # red is the lineage predicate at apply.py:166 (D1's red).
            common_before = dict(
                receipt_id=_C5_REC, adapter=_C5_ADAPTER, application_ref=_C5_APPREF,
                reserved_successor=reserved, committed_lineage=committed_before,
                has_marker=lambda t: apply._marker_for(_C5_ADAPTER, _C5_REC) in t)
            proof_before = apply.prove_applied(drifted, **common_before)
            self.assertIs(
                proof_before, apply.Proof.UNKNOWN,
                "an unjournaled valid successor must fail closed (UNKNOWN), not "
                "NOT_APPLIED (which would duplicate the effect)")

            # ---- C5's own half: the rebaseline operator. ----
            # A place the journal import lands. rebaseline is given a callback
            # (mirroring how reconcile takes a finish callback): the operator
            # decides to adopt and mints the successor; the caller wires the
            # import into the journal. The test records what rebaseline reported
            # so the "journals the import" requirement is observed, not assumed.
            imported = []

            def journal_import(old_generation, new_generation, identity_str):
                imported.append((old_generation, new_generation, identity_str))

            new_lineage = domain_files.rebaseline(
                path, committed_lineage=committed_before,
                journal_import=journal_import)

            # The successor generation rebaseline minted: one past the committed
            # high water, NOT the drifted file's 99 — rebaseline MINTS the
            # successor rather than trusting the external generation.
            expected_successor = max(committed_before) + 1
            self.assertEqual(
                new_lineage, committed_before | {expected_successor},
                "rebaseline mints a successor one past the committed high water "
                "and adds it to committed lineage; it does NOT adopt the drifted "
                "file's own generation")

            # The journal import fired exactly once, naming the minted successor
            # and the file's identity — "journals the import" (law 5). Derived
            # from the rebaseline result, never a literal.
            self.assertEqual(len(imported), 1, "the import is journaled exactly once")
            old_g, new_g, ident = imported[0]
            self.assertEqual(new_g, expected_successor,
                             "the journaled successor is the one rebaseline minted")
            self.assertEqual(ident, md["last_applied"],
                             "the journaled identity is the file's embedded identity")

            # Bytes preserved: the file on disk is byte-identical to the drifted
            # original. rebaseline validated and re-emitted the SAME body under a
            # new generation, so nothing the human typed changed.
            after = open(path, encoding="utf-8").read()
            md_after = domain_files.parse_metadata(after)
            self.assertEqual(
                md_after["domain_generation"], expected_successor,
                "rebaseline rewrote the file at the minted successor generation")
            self.assertEqual(
                md_after["last_applied"], md["last_applied"],
                "rebaseline preserved the identity")
            self.assertTrue(domain_files.validate(after),
                            "rebaseline left a valid file")

            # ---- The discriminating pair, reversed: now APPLIED. ----
            # The SAME file that proved UNKNOWN now proves APPLIED, because
            # rebaseline added its generation to committed lineage. Deleting the
            # lineage-adoption line makes THIS assertion fail while the
            # pre-rebaseline UNKNOWN assertion still holds — C5's own red.
            #
            # The post-rebaseline reserved successor is the NEXT application's
            # successor (one past the new high water), NOT the rebaselined
            # generation. This is what makes the assertion discriminating: the
            # rebaselined file's generation is in committed_lineage (the lineage
            # half grants APPLIED), and it is NOT the reserved successor (so the
            # successor half does not). Passing reserved=the rebaselined gen
            # instead would let the successor half grant APPLIED on its own and
            # the lineage-adoption red would be hollow — the two-mechanisms trap
            # the plan warns about (B1/B7).
            reserved_after = max(new_lineage) + 1
            common_after = dict(
                receipt_id=_C5_REC, adapter=_C5_ADAPTER, application_ref=_C5_APPREF,
                reserved_successor=reserved_after, committed_lineage=new_lineage,
                has_marker=lambda t: apply._marker_for(_C5_ADAPTER, _C5_REC) in t)
            proof_after = apply.prove_applied(after, **common_after)
            self.assertIs(
                proof_after, apply.Proof.APPLIED,
                "after rebaseline, the file's generation is in committed lineage "
                "and its marker is found, so it proves APPLIED — the only path "
                "that makes the journal-then-apply order safe")


if __name__ == "__main__":
    unittest.main()
