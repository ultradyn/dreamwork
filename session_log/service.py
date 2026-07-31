"""Cold SessionService — resolves ids, scans, owns the ring/cursor (#631 i6).

One thread-safe service that resolves a session id through the catalogue,
runs the Claude Code scanner, owns the in-memory per-session event ring and
cursor, builds a snapshot skeleton, and parses a bounded peek from a
registered source range. It has NO file-notification thread and NO HTTP
caller yet — both are later increments (#631 i7 onward). Its only caller in
this increment is its test.

THE SECURITY BOUNDARY IS THE POINT (brief, §"the security boundary"). A
client-supplied path must be IMPOSSIBLE at this API boundary, not merely
rejected. How that is so:

  - Every public method takes ``session_id: str`` and NOTHING else that names
    a source. There is no ``path`` parameter on any public method.
  - The resolved transcript path is NEVER derived from the caller's string by
    joining or interpreting it. It is the OUTPUT of
    :func:`session_source.resolve`, called only AFTER the id has been matched
    against the catalogue's discovered set — and a discovered id is a strict
    UUID naming a confined file (increment 5 closed the path hole one level
    down: the wire ``CatalogEntry`` carries an opaque ``session_id`` and no
    path at all).
  - A caller's string is treated as an id TOKEN: it is compared for equality
    against the discovered uuids and nothing else. A path-shaped string is
    not a discovered uuid, so it fails the gate before any filesystem object
    is touched. There is no code path in which a caller's string becomes a
    filesystem path.

So the shape built is: an id that can only ever select a source by being
resolved through the catalogue. Replacing that resolution with ``Path(id)``
is the injection the proof reds on *"only a discovered session id may select
a source"*.

WHAT THE TESTS DO AND DO NOT ESTABLISH ABOUT THREAD SAFETY (#651: a
docstring's "thread-safe" is worth nothing unless exercised). Every public
method holds one re-entrant lock (``self._lock``) around the held-state dict
and every per-session mutation, so a register/advance and a snapshot/events/
peek cannot interleave on the same session. The contention test exercises
that under many threads and asserts consistency (no lost events, no
duplicate ids in the ring, monotonic cursor, no exception). It does NOT
prove lock-freedom, a specific scheduling, or absence of deadlock under
arbitrary lock ordering — there is one lock, so there is no ordering to
deadlock on, but the test is a smoke test of serialisation, not a formal
proof.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import session_source
from session_log import claude_code
from session_log.model import SessionNode

# A peek may read at most this many source units. The bound exists to stop an
# oversized request; a too-SMALL request is caught by a parse failure, never a
# silent truncation (the off-by-one proof re-derives the expected length rather
# than comparing strings). Source offsets share the scanner's basis (the decoded
# text), so a registered ``SourceRef`` slices the held text exactly.
MAX_PEEK_LEN = 1 << 20  # 1 MiB backstop over single-record ranges


class SessionServiceError(Exception):
    """Base for SessionService faults."""


class UnknownSessionId(SessionServiceError):
    """A caller-supplied id that is not a discovered session (#631 i6).

    This is the gate: only a discovered session id may select a source.
    """


class SessionNotRegistered(SessionServiceError):
    """An id that was never registered (no ``register`` call succeeded)."""


class SessionGone(SessionServiceError):
    """A discovered id whose transcript vanished between catalogue and read.

    Distinct from an EMPTY session (#136): a present-but-empty file scans to
    zero events and is the calm empty state, NOT a fault; a file that was
    catalogued and then deleted before the read is a fault, and must not read
    identically to the empty case.
    """


class PeekOutOfBounds(SessionServiceError):
    """A peek request outside the bound or outside the registered ranges."""


@dataclass(frozen=True)
class Snapshot:
    """The snapshot skeleton: the tree's structure without bodies (§6).

    ``session_node`` and ``pages`` are derived FRESH from the held event ring
    on every call (not cached at register time), so the skeleton and the
    cursor are projections of the same held state computed in the same call —
    they cannot disagree. The test for that property advances the ring after
    register and requires the skeleton to reflect the advance.
    """

    session_id: str
    client: str
    session_node: SessionNode | None
    pages: tuple            # tuple[SessionNode, ...]
    bookmarks: tuple        # tuple[claude_code.Bookmark, ...]
    diagnostics: tuple      # tuple[claude_code.Diagnostic, ...]
    cursor: int             # the server cursor = len(held event ring)
    examined: int           # records the scan parsed (#671: zero is honest)
    frontier_byte: int      # the resume cursor into the source


@dataclass(frozen=True)
class EventDelta:
    """The ordered events since a caller's cursor, plus the new cursor."""

    events: tuple           # tuple[SessionEvent, ...]
    cursor: int             # len(held event ring) after this call


@dataclass(frozen=True)
class Peek:
    """The parsed body of one registered source range (§6 peek, server-side).

    ``length`` is the number of source units actually read; the caller's
    request and this field must agree (re-derived by the caller, not trusted).
    """

    byte: int
    length: int
    record: object | None
    parse_error: str | None


@dataclass
class _Held:
    """Per-session in-memory state, mutated only under ``SessionService._lock``."""

    session_id: str
    client: str
    path: Path              # server-derived; never caller-supplied
    text: str               # the decoded source at the last scan (offset basis)
    events: list            # list[SessionEvent] — the ring
    bookmarks: tuple        # tuple[claude_code.Bookmark, ...]
    diagnostics: tuple      # tuple[claude_code.Diagnostic, ...]
    frontier: object        # claude_code.Frontier
    ranges: dict            # {byte_offset: record_length} — registered ranges


def _registered_ranges(events) -> dict:
    """The distinct source ranges the scan recorded (byte -> record length).

    A peek may only read a range the scan registered for a node, which is the
    confinement that stops an arbitrary byte offset from being opened.
    """
    ranges: dict[int, int] = {}
    for ev in events:
        ref = ev.node.ref
        if ref is not None:
            cur = ranges.get(ref.byte, 0)
            if ref.length > cur:
                ranges[ref.byte] = ref.length
    return ranges


class SessionService:
    """Cold, thread-safe session-log service (#631 increment 6).

    Construct with the target directory and (optionally) the client projects
    root; register a discovered session id to cold-scan it; read the snapshot,
    replay events from a cursor, or peek a registered source range. There is
    no watcher thread and no HTTP caller in this increment.
    """

    def __init__(self, target, *, projects_root=None,
                 stale_after=session_source.DEFAULT_STALE_AFTER):
        self._target = str(target)
        self._projects_root = projects_root
        self._stale_after = stale_after
        self._lock = threading.RLock()
        self._sessions: dict[str, _Held] = {}

    # --- internal helpers (callers already hold the lock or are pre-lock) ---

    def _root(self):
        if self._projects_root is not None:
            return self._projects_root
        return session_source._default_projects_root()

    def _discover(self, session_id, now):
        """The confinement gate: only a discovered session id may select a source.

        Runs the catalogue and requires ``session_id`` to be among the
        discovered entries. A path-shaped (or any non-uuid) string is not a
        discovered id and is refused here, before any filesystem object named
        by the caller is touched. Returns the catalogue so the caller can read
        metadata without re-running discovery.
        """
        cat = session_source.catalogue(
            self._target, projects_root=self._root(), now=now,
            stale_after=self._stale_after)
        ids = {e.session_id for e in cat.entries}
        if session_id not in ids:
            raise UnknownSessionId(
                "only a discovered session id may select a source; %r is not "
                "in the catalogue of %d session(s) for %s"
                % (session_id, len(ids), self._target))
        return cat

    def _require(self, session_id):
        held = self._sessions.get(session_id)
        if held is None:
            raise SessionNotRegistered(
                "session %r is not registered; call register() first"
                % session_id)
        return held

    def _snapshot_from(self, held):
        """Derive the skeleton FRESH from the held ring (no cached snapshot)."""
        session_node = None
        pages = []
        for ev in held.events:
            if ev.ev == "open":
                if ev.node.kind == "session":
                    session_node = ev.node
                elif ev.node.kind == "page":
                    pages.append(ev.node)
        return Snapshot(
            session_id=held.session_id,
            client=held.client,
            session_node=session_node,
            pages=tuple(pages),
            bookmarks=held.bookmarks,
            diagnostics=held.diagnostics,
            cursor=len(held.events),
            examined=held.frontier.examined,
            frontier_byte=held.frontier.byte,
        )

    def _ingest(self, held, scan, text):
        """Fold a scan's output into the held ring/bookmarks/frontier/ranges."""
        if scan.events:
            held.events.extend(scan.events)
            held.bookmarks = held.bookmarks + scan.bookmarks
            held.diagnostics = held.diagnostics + scan.diagnostics
            for ev in scan.events:
                ref = ev.node.ref
                if ref is not None and ref.length > held.ranges.get(ref.byte, 0):
                    held.ranges[ref.byte] = ref.length
        held.frontier = scan.frontier
        held.text = text

    # --- public API ---------------------------------------------------------

    def register(self, session_id, *, now=None):
        """Resolve ``session_id`` through the catalogue, cold-scan, and hold state.

        Raises :class:`UnknownSessionId` if the id is not a discovered session
        (the security gate), or :class:`SessionGone` if a discovered id's
        transcript vanished between catalogue and read (#136: a fault, distinct
        from an empty session). Returns the initial :class:`Snapshot`.
        """
        now = now if now is not None else datetime.now(timezone.utc)
        with self._lock:
            cat = self._discover(session_id, now)
            client = next(
                (e.client for e in cat.entries if e.session_id == session_id),
                session_source.CATALOGUE_CLIENT)
            res = session_source.resolve(
                session_id, self._root(), now=now,
                stale_after=self._stale_after)
            if res.path is None:
                raise SessionGone(
                    "discovered session %s did not resolve to a transcript "
                    "(%s)" % (session_id, res.detail))
            path = res.path
            try:
                text = path.read_text(encoding="utf-8")
            except (FileNotFoundError, OSError) as exc:
                raise SessionGone(
                    "discovered session %s vanished between catalogue and "
                    "read (%s)" % (session_id, exc)) from exc
            scan = claude_code.scan_complete(text)
            held = _Held(
                session_id=session_id, client=client, path=path, text=text,
                events=list(scan.events), bookmarks=scan.bookmarks,
                diagnostics=scan.diagnostics, frontier=scan.frontier,
                ranges=_registered_ranges(scan.events))
            self._sessions[session_id] = held
            return self._snapshot_from(held)

    def advance(self, session_id, *, now=None):
        """Re-read the source from the held frontier and append new events.

        The cold service's manual way to grow the ring (the watcher THREAD is
        increment 7). Returns the :class:`EventDelta` of new events and the new
        server cursor. Idempotent when the source has not grown: an unchanged
        file scans zero new events.
        """
        del now  # liveness is not re-judged on a manual advance
        with self._lock:
            held = self._require(session_id)
            before = len(held.events)
            text = held.path.read_text(encoding="utf-8")
            scan = claude_code.scan_incremental(text, held.frontier)
            self._ingest(held, scan, text)
            return EventDelta(
                events=tuple(held.events[before:]), cursor=len(held.events))

    def snapshot(self, session_id):
        """The current skeleton, derived fresh from the held ring."""
        with self._lock:
            return self._snapshot_from(self._require(session_id))

    def events(self, session_id, *, from_cursor=None):
        """The ordered events since ``from_cursor``, plus the new server cursor.

        ``from_cursor=None`` (or a stale/invalid value) recovers to a full
        replay — the cold-service half of the stale-cursor recovery the
        registration routes (increment 9) will need. The ring is never evicted
        in this increment, so any cursor in ``[0, len]`` is a valid delta.
        """
        with self._lock:
            held = self._require(session_id)
            total = len(held.events)
            start = from_cursor if isinstance(from_cursor, int) else 0
            if start < 0 or start > total:
                start = 0  # stale or ahead-of-server cursor: full recovery
            return EventDelta(
                events=tuple(held.events[start:]), cursor=total)

    def peek(self, session_id, *, byte, length):
        """Parse a bounded peek from a REGISTERED source range.

        ``byte`` must be a registered record offset and ``length`` must not
        exceed that record's registered length nor :data:`MAX_PEEK_LEN`; a
        too-large request is refused (the bound the exists to prevent), and a
        too-short request surfaces as a parse failure rather than a silent
        truncation. ``length`` in the result is the count actually read, which
        a caller re-derives rather than trusting the request (#645 i7 shape).
        """
        with self._lock:
            held = self._require(session_id)
            if not isinstance(length, int) or length < 1 or length > MAX_PEEK_LEN:
                raise PeekOutOfBounds(
                    "peek length %r outside [1, %d]" % (length, MAX_PEEK_LEN))
            reg = held.ranges.get(byte)
            if reg is None:
                raise PeekOutOfBounds(
                    "byte %d is not a registered source range" % byte)
            if length > reg:
                raise PeekOutOfBounds(
                    "peek length %d exceeds the registered range %d at byte %d"
                    % (length, reg, byte))
            chunk = held.text[byte:byte + length]
            if len(chunk) != length:
                raise PeekOutOfBounds(
                    "read %d of %d requested units at byte %d"
                    % (len(chunk), length, byte))
            try:
                record = json.loads(chunk)
            except (ValueError, json.JSONDecodeError) as exc:
                return Peek(byte=byte, length=length, record=None,
                            parse_error=str(exc))
            return Peek(byte=byte, length=length, record=record,
                        parse_error=None)
