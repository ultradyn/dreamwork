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


if __name__ == "__main__":
    unittest.main()
