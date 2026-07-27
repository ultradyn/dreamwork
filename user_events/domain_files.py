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
import hashlib
import os
import re
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


# ---------------------------------------------------------------------------
# Lineage — embedded generation, body digest, last-application identity.
#
# A managed full file carries its own ``domain_generation``, ``body_digest``
# and ``last_applied`` identity in a trailing footer (design law 2). The digest
# covers the canonical body *excluding only its own digest field* — it is a
# witness of the bytes that are there, not of itself, so it stays computable and
# stable for an unchanged body. This is the lineage half of the store; the lock
# half is above and the one-write half lands in the next increment.
#
# The footer is a single trailing block so a reader finds it without parsing the
# whole file, and so the digest's exclusion target (one line) is unambiguous:
#
#     <body>\n
#     <!-- dreamwork-managed v1
#     domain_generation: <int>
#     body_digest: <hex>
#     last_applied: <identity>
#     -->
#
# The body is arbitrary text; the footer is the last such block in the file.
# ---------------------------------------------------------------------------

_FOOTER_RE = re.compile(r"(?s)<!-- dreamwork-managed v1\n(.*?)\n-->")
_GEN_RE = re.compile(r"(?m)^domain_generation:\s*(\d+)\s*$")
_APPLIED_RE = re.compile(r"(?m)^last_applied:\s*(.*)$")
# The digest line: the field whose value the canonical body must EXCLUDE. It
# accepts an absent/blank value too, because the canonical form blanks it.
_DIGEST_LINE_RE = re.compile(r"(?m)^body_digest:.*$")
_DIGEST_FIELD_RE = re.compile(r"(?m)^body_digest:\s*([0-9a-fA-F]*)\s*$")


def _footer(generation, digest, identity):
    return ("<!-- dreamwork-managed v1\n"
            "domain_generation: %d\n"
            "body_digest: %s\n"
            "last_applied: %s\n"
            "-->" % (generation, digest, identity))


def canonical_body(text):
    """The text with its own digest field's value excluded.

    The digest witnesses every byte of the file except the one field that holds
    it: without that exclusion the digest would be self-referential (a fixpoint
    that never holds), and an unchanged body would no longer yield a stable
    digest. The single substitution below is the line the lineage test is named
    for — delete it and the digest becomes self-referential.
    """
    return _DIGEST_LINE_RE.sub("body_digest:", text, count=1)


def compute_digest(text):
    """SHA-256 of the canonical body, hex-encoded."""
    return hashlib.sha256(canonical_body(text).encode("utf-8")).hexdigest()


def parse_metadata(text):
    """Return the footer's ``{domain_generation, body_digest, last_applied}``.

    ``None`` if the file carries no managed footer or a field is missing — which
    ``validate`` reads as "not a managed file this store wrote", distinct from
    "managed but tampered".
    """
    m = _FOOTER_RE.search(text)
    if not m:
        return None
    block = m.group(1)
    gm = _GEN_RE.search(block)
    dm = _DIGEST_FIELD_RE.search(block)
    am = _APPLIED_RE.search(block)
    if not (gm and dm and am):
        return None
    return {"domain_generation": int(gm.group(1)),
            "body_digest": dm.group(1),
            "last_applied": am.group(1)}


def build_managed_text(body, generation, identity, digest=None):
    """Assemble a managed file's full text with a correct embedded digest.

    The digest is computed over the canonical body (digest field blanked), so
    the placeholder never reaches the hash; the same body, generation and
    identity always yield the same digest.
    """
    body = body or ""
    draft = body + "\n" + _footer(generation, "", identity)
    if digest is None:
        digest = compute_digest(draft)
    return body + "\n" + _footer(generation, digest, identity)


def set_digest_value(text, value):
    """Return ``text`` with its digest field set to ``value`` (any string).

    Used to forge a wrong digest when testing that validation rejects it.
    """
    return _DIGEST_LINE_RE.sub("body_digest: " + value, text, count=1)


def recompute_digest(text):
    """Return ``text`` with its digest field set to the current canonical digest.

    This is the "re-emit the same body with the digest recomputed" operation:
    over a valid file the recomputed digest equals the embedded one, because the
    canonical body excludes only the digest field and the body is unchanged.
    """
    if parse_metadata(text) is None:
        raise ValueError("not a managed file: no footer")
    return _DIGEST_LINE_RE.sub("body_digest: " + compute_digest(text),
                               text, count=1)


def validate(text):
    """True iff ``text`` is a managed file whose embedded digest matches its body."""
    md = parse_metadata(text)
    if md is None:
        return False
    return md["body_digest"] == compute_digest(text)
