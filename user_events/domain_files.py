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
import tempfile
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


# ---------------------------------------------------------------------------
# Markers — whole-file marker search across BOTH literal Open and Answered
# sections (increment 14, C4).
#
# The loop folds an answered entry from ``## Open`` to ``## Answered`` (see
# watch.py: append_answer moves the entry and its marker below the ``##
# Answered`` header). A receipt marker travels with the entry it belongs to, so
# the same receipt's marker can sit in EITHER section depending on whether the
# fold has happened. A scan that looked only under ``## Open`` would lose the
# marker the moment the fold moved it — and the proof would then mis-read an
# applied receipt as not-applied and duplicate its effect. The search therefore
# scans every section a marker can legitimately live in, and the section list
# is the single place those sections are named.
# ---------------------------------------------------------------------------

# The literal section headers a managed marker may live under, in the form
# ``## <name>``. Order is stable and irrelevant to a union search; what matters
# is that BOTH are present. This tuple is the C4 red line: delete the
# ``"Answered"`` entry and a marker the fold has moved below ``## Answered`` is
# no longer scanned, so find_marker returns False for the folded fixture while
# the still-open fixture stays True — a discriminating failure, not a suite
# that moves together.
_MANAGED_SECTIONS = ("Open", "Answered")


def _section_header_re(section):
    """Anchored regex matching the ``## <section>`` header line.

    Anchored and strip-equal (``^[ \\t]*## <name>[ \\t]*$``), matching
    watch.py's ``LEDGER_SEC_OPEN`` / ``LEDGER_SEC_LANDED`` and lint.py's own
    ``heads`` rule. An unanchored ``text.split("## Open")`` once let an entry
    *say* ``## Open`` masquerade as a section boundary (watch.py:7642); the
    anchored form is the one-correct-answer that keeps this reader, watch and
    lint from disagreeing about where a section begins.
    """
    return re.compile(r"^[ \t]*## " + re.escape(section) + r"[ \t]*$", re.M)


def _section_text(text, section):
    """The text of one ``## <section>``: from its header to the next ``## ``
    header at column 0 or EOF.

    ``None`` when the file carries no such section (so a caller can tell
    "absent section" from "empty section"). The body returned excludes the
    header line itself and any text before it, and stops at the next top-level
    ``## `` heading — which is exactly the region an entry under that section
    occupies, and exactly where a marker the fold placed there would sit.
    """
    pattern = _section_header_re(section)
    m = pattern.search(text)
    if m is None:
        return None
    body = text[m.end():]
    nxt = re.search(r"(?m)^## ", body)
    if nxt is None:
        return body
    return body[:nxt.start()]


def find_marker(text, marker):
    """True iff ``marker`` appears within ANY managed section of ``text``.

    Searches the union of the sections named in ``_MANAGED_SECTIONS`` rather
    than the whole file, so a marker is found whether it sits under ``## Open``
    (before the fold) or under ``## Answered`` (after the fold). A marker that
    appears nowhere in those sections is absent — including a marker whose only
    occurrence is outside any section header, which is not a receipt the store
    would recognise.
    """
    for section in _MANAGED_SECTIONS:
        region = _section_text(text, section)
        if region is not None and marker in region:
            return True
    return False


# ---------------------------------------------------------------------------
# Rebaseline — the explicit operator that adopts an externally-edited valid
# file into committed lineage (increment 15, C5; design law 5).
#
# "Arbitrary editor drift fails closed": the application layer (lane D) already
# proves a valid file whose generation is outside committed lineage and not the
# reserved successor as UNKNOWN, and refuses to apply over it. That detection is
# red-proven there, and it is NOT duplicated here — rebaseline is the operator
# the SAME design law names for the *intentional* half: when an operator has
# decided the external edit is legitimate, rebaseline is the only path that
# validates the file, preserves its bytes, mints a successor generation, and
# journals the import before further application proceeds.
#
# The successor is MINTED (one past the committed high water), not adopted from
# the file's own generation — the external generation is untrusted by
# construction (it is the drift that made the file UNKNOWN), so rebaseline does
# not echo it. The file is re-emitted at the minted successor under the lock,
# byte-for-byte the same body, with its digest recomputed for the new
# generation.
# ---------------------------------------------------------------------------

def rebaseline(path, *, committed_lineage, journal_import, timeout=10.0):
    """Adopt an externally-edited valid file into committed lineage.

    Reads the file under the cross-process lock, validates it (law 5:
    "validate"), re-emits its body unchanged at a freshly minted successor
    generation ("preserve bytes", "mint a new successor generation"), and calls
    ``journal_import(old_generation, new_generation, identity)`` so the caller
    journals the import ("journal the import"). Returns the new committed
    lineage — the input plus the minted successor.

    Raises ``ValueError`` if the file is not a valid managed file: rebaseline is
    the intentional path for a *valid* external edit, not a repair for a torn
    one, so a file that fails validation is refused rather than silently
    adopted (a torn file proving UNKNOWN stays UNKNOWN; rebaseline does not
    override that).

    ``committed_lineage`` is the set of generations the caller treats as
    committed (the journal's CAS-finished lineage). The minted successor is
    ``max(committed_lineage) + 1`` — one past the high water, never the file's
    own (untrusted) generation. ``journal_import`` is a callback (mirroring how
    ``reconcile`` takes a ``finish`` callback) so the domain-file operator stays
    independent of the journal's concrete mechanics.
    """
    if not committed_lineage:
        raise ValueError("committed_lineage must be non-empty to mint a successor")
    with DomainFileLock(path, timeout=timeout):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        md = parse_metadata(text)
        if md is None or not validate(text):
            raise ValueError(
                "rebaseline refuses a file that is not a valid managed file; "
                "a torn/drifted file stays UNKNOWN — rebaseline is for the "
                "intentional adoption of a valid external edit, not a repair")
        # The successor is minted one past the committed high water. The file's
        # own generation is the drift that made it UNKNOWN, so it is not
        # echoed: rebaseline adopts the BYTES under a trusted generation.
        old_generation = md["domain_generation"]
        successor = max(committed_lineage) + 1
        # C5's own red line: the minted successor is ADDED to committed lineage.
        # Delete the union and the caller's new lineage still excludes the file's
        # generation, so the post-rebaseline proof reads UNKNOWN (the reverse of
        # the pre-rebaseline pair) — a discriminating failure.
        new_lineage = set(committed_lineage) | {successor}
        identity = md["last_applied"]
        # Re-emit the SAME body at the minted generation: the body is preserved
        # byte-for-byte (only the generation in the footer changes, and the
        # digest recomputed to cover the new footer). build_managed_text over the
        # existing body with the new generation yields exactly that.
        body = _body_for_rebaseline(text)
        new_text = build_managed_text(body, successor, identity)
        _atomic_replace(path, new_text)
        # Journal the import before further application proceeds (law 5). The
        # callback wires the import into the journal; the operator reports the
        # old generation, the minted successor, and the file's identity.
        journal_import(old_generation, successor, identity)
        return new_lineage


def _body_for_rebaseline(text):
    """The human-visible body of a managed file: text with its footer stripped.

    The footer is the last ``<!-- dreamwork-managed v1 ... -->`` block.
    ``rebaseline`` preserves this body unchanged when re-emitting at a new
    generation, so the external edit's prose, markers and structure are all
    preserved — only the footer (generation + recomputed digest) changes.
    """
    m = _FOOTER_RE.search(text)
    if m is None:
        # validate() already rejected this case; defensive only.
        return text.rstrip("\n")
    body = text[:m.start()]
    return body.rstrip("\n")


# ---------------------------------------------------------------------------
# One write — effect, marker, generation and digest land in a single atomic
# durable replace under the lock, or none of them do (design law 5).
#
# The durable shape is temp-in-same-directory + fsync + os.replace +
# fsync-parent — the same shape watch.py's atomic_write_text already uses for
# /ask. The difference is that here it is guarded by the cross-process lock and
# carries the lineage above, so a crash in the window between the temp fsync and
# the rename can never half-write the real file. The crash test drives a child
# straight into os._exit at that seam.
# ---------------------------------------------------------------------------

def _atomic_replace(path, text, *, crash_before_replace=False):
    """Durably replace ``path`` with ``text`` via temp + fsync + os.replace.

    ``crash_before_replace`` is the NAMED SEAM for the crash test: after the
    temp is written and fsynced but before os.replace, the calling process
    ``os._exit``s. Because the rename never ran the real file is byte-identical
    to its pre-state and only an orphaned temp is left behind — which is the
    whole point of temp-then-rename over a direct truncate-write.
    """
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".",
                               suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        # ---- named kill seam: temp is durable on disk, the real file is
        # ---- untouched. os._exit here terminates the process without running
        # ---- the except clause below, so the orphan temp is left on disk and
        # ---- os.replace never runs.
        if crash_before_replace:
            os._exit(0)
        os.replace(tmp, path)
        # Best-effort durability of the rename itself; a directory-fsync error
        # is never fatal (and never a reason to retry, which would duplicate).
        try:
            dfd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def write(path, body, *, generation, applied,
          crash_before_replace=False, timeout=10.0):
    """Write one managed generation atomically: lock, assemble, durable replace.

    ``body`` is the human-visible effect; ``applied`` is the last-application
    identity (receipt | adapter | application reference) that serves as the
    receipt marker. Effect, marker, generation and digest all land in the one
    ``_atomic_replace`` call, under the cross-process lock held across the
    whole read-to-write span.

    ``crash_before_replace`` is forwarded to ``_atomic_replace`` for the crash
    test only; production callers never set it.
    """
    with DomainFileLock(path, timeout=timeout):
        text = build_managed_text(body, generation, applied)
        _atomic_replace(path, text, crash_before_replace=crash_before_replace)
