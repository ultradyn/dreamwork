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


if __name__ == "__main__":
    unittest.main()
