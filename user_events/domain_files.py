"""A managed domain-file store: OS-visible lock, embedded lineage, one write.

Three properties, each the whole point of the one before it (design
``user-event-journal.md``, "Crash-safe ApplicationAdapter", laws 2/3/5):

1. **OS-visible lock.** A managed file cannot be read or written without a
   cross-process lock taken on a sidecar path *before* the read and held until
   after the durable rename. The existing writer's only mutual exclusion is an
   in-process ``threading.Lock`` (``watch.py``'s ``ANSWER_LOCK``), which two
   ``watch.py`` processes on one target serialise against nothing — the second
   half of #262. ``fcntl.flock`` on a sidecar is OS-visible to every process.

2. **Embedded lineage.** Every managed file carries its own
   ``domain_generation``, ``body_digest`` and last-application identity, and the
   digest covers the canonical body *excluding only its own field* — so it is a
   witness of the bytes, not of itself.

3. **One atomic durable write.** Human-visible effect, receipt marker,
   generation and digest land in a single temp-then-``os.replace`` under the
   lock, or none of them do. A crash in the window can never half-write the file
   that holds his answers.

This module is greenfield and is **not wired** to ``watch.py``'s writers; wiring
is a later increment behind a later gate. It manages its own files and defines
its own managed-file shape (documented inline) until the cutover adopts it.
"""

import errno
import fcntl
import os
import time


class LockTimeout(TimeoutError):
    """Raised when a cross-process lock cannot be acquired in the bound asked."""


# Polling interval for the bounded non-blocking acquire loop. ``fcntl.flock``
# blocks by default and ``LOCK_NB`` returns immediately, so a timeout is a short
# sleep between attempts up to a deadline. Small enough to feel instant against
# a real contention window, large enough not to spin.
_LOCK_POLL = 0.05


class DomainFileLock:
    """An OS-visible cross-process lock for one domain file.

    Implemented as an advisory ``fcntl.flock(LOCK_EX)`` on a sidecar lock path
    (``<path>.lock``) rather than the file itself, so the lock outlives an
    in-flight temp/rename of the real file and never has to contend with the
    durability write it guards. Two processes each ``open()`` the sidecar, so
    they hold separate open file descriptions and ``flock`` contends between
    them — that is the OS visibility the lock is the whole claim of.

    Used as a context manager it acquires on entry and releases on exit; the
    acquire honours a bounded timeout via a non-blocking retry loop, because a
    plain blocking ``flock`` with no deadline is an unbounded wait.
    """

    def __init__(self, path, timeout=10.0):
        self.path = str(path)
        self.lock_path = self.path + ".lock"
        self.timeout = timeout
        self._fd = None

    def acquire(self, timeout=None):
        """Take the exclusive lock, bounded by ``timeout`` (default self.timeout).

        Raises ``LockTimeout`` if the lock is not free within the bound. On
        timeout the sidecar file descriptor is closed so a later acquisition
        opens fresh and nothing is held half-open.
        """
        if timeout is None:
            timeout = self.timeout
        directory = os.path.dirname(self.lock_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o644)
        self._fd = fd
        deadline = time.monotonic() + timeout
        while True:
            try:
                # The OS-visible exclusion itself. Removing this call makes
                # acquire a no-op that two processes pass simultaneously — which
                # is the red the lock test exists to catch.
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    os.close(fd)
                    self._fd = None
                    raise LockTimeout(
                        "could not acquire lock %s within %.2fs"
                        % (self.lock_path, timeout))
                time.sleep(_LOCK_POLL)

    def release(self):
        """Release the lock and close the sidecar descriptor. Idempotent."""
        if self._fd is None:
            return
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            os.close(self._fd)
            self._fd = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False
