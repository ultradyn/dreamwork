"""Tests for `session_log/service.py` — the cold SessionService (#631 i6).

The service resolves ids through the catalogue, scans, owns the in-memory
event ring/cursor, builds a snapshot skeleton, and parses a bounded peek from
a registered source range. These tests are its only caller.

Every test names the production behaviour whose reversion reds it. The brief's
three sharp requirements are isolated:

  - the security boundary — a client-supplied path is IMPOSSIBLE at the API
    boundary (not merely rejected);
  - the three classifier outcomes (node / suppressed / unclassifiable) stay
    distinguishable through the service (#702);
  - a deleted session is a FAULT distinct from an empty one (#136), and a
    bounded peek re-derives its expected length rather than naive-comparing.
"""
import inspect
import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import session_source
from session_log import service as svc_mod
from session_log.service import (
    MAX_PEEK_LEN,
    EventDelta,
    Peek,
    PeekOutOfBounds,
    SessionGone,
    SessionNotRegistered,
    SessionService,
    Snapshot,
    UnknownSessionId,
)

UTC = timezone.utc
NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
SID = "3a19e737-cb3f-4dde-8304-3241ac374cdb"


def _ts(minutes_ago: float) -> str:
    return (NOW - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


# --- fixture builders ------------------------------------------------------

def _user_turn(uuid, text, minutes_ago=2):
    return {"type": "user", "uuid": uuid, "timestamp": _ts(minutes_ago),
            "message": {"role": "user", "content": text}}


def _fixture_records():
    """Six records exercising all three classifier outcomes + a page boundary.

    0 user "hello"            -> turn.user   (NODE)   opens session + page 0
    1 assistant tool_use      -> step.tool   (NODE)   opens agent turn + step
    2 user tool_result        -> step.tool   (NODE)   pairs the step (update)
    3 system compact_boundary -> page        (NODE)   closes agent, opens page 1
    4 user w/o content        -> UNCLASSIFIABLE       reported as a diagnostic
    5 type "mode"             -> SUPPRESSED           silent by design
    """
    return [
        _user_turn("u1", "hello"),
        {"type": "assistant", "uuid": "a1", "timestamp": _ts(2),
         "requestId": "r1",
         "message": {"role": "assistant", "content": [
             {"type": "tool_use", "id": "toolu_1", "name": "Bash",
              "input": {"command": "echo hi"}}]}},
        {"type": "user", "uuid": "u2", "timestamp": _ts(2),
         "message": {"role": "user", "content": [
             {"type": "tool_result", "tool_use_id": "toolu_1",
              "content": "hi", "is_error": False}]}},
        {"type": "system", "subtype": "compact_boundary", "uuid": "s1",
         "timestamp": _ts(2), "content": "compacted",
         "compactMetadata": {"trigger": "auto", "preTokens": 1000,
                             "postTokens": 200}},
        {"type": "user", "uuid": "u3", "timestamp": _ts(2),
         "message": {"role": "user"}},          # no content -> unclassifiable
        {"type": "mode", "mode": "plan"},        # chrome -> suppressed
    ]


def _build_world(tmp_path: Path, records, sid=SID):
    """A target + projects root with `records` written as the session transcript.

    Returns (target, root, path, text). The slug is named via the PRODUCTION
    `_slug_for` so fixtures live where the catalogue searches.
    """
    target = tmp_path / "target"
    target.mkdir(parents=True, exist_ok=True)
    root = tmp_path / "projects"
    slug = session_source._slug_for(target)
    (root / slug).mkdir(parents=True, exist_ok=True)
    path = root / slug / f"{sid}.jsonl"
    text = "".join(json.dumps(r) + "\n" for r in records)
    path.write_text(text)
    return target, root, path, text


def _line_offsets(text):
    """(byte, length) per newline-terminated line, matching the scanner's basis.

    The scanner measures `byte = pos`, `length = nl - pos` over the decoded
    text; this helper reproduces that exactly so peek offsets are derived
    independently of the service.
    """
    offs = []
    pos = 0
    while True:
        nl = text.find("\n", pos)
        if nl == -1:
            break
        offs.append((pos, nl - pos))
        pos = nl + 1
    return offs


def _register_fixture(tmp_path):
    target, root, path, text = _build_world(tmp_path, _fixture_records())
    svc = SessionService(target, projects_root=root)
    snap = svc.register(SID, now=NOW)
    return svc, target, root, path, text, snap


# === the security boundary: a client path is IMPOSSIBLE ===================

class TestSecurityBoundary:
    """A client-supplied path must be impossible at the API boundary, not merely
    rejected. The shape: an id that can only select a source by being resolved
    through the catalogue. No public method takes a path; the resolved path is
    always the OUTPUT of `resolve` for a catalogue-validated uuid."""

    def test_no_public_method_accepts_a_path_parameter(self):
        # Structural impossibility: there is no `path` parameter anywhere a
        # caller can reach. A path cannot be supplied because no method names
        # one.
        for name in ("register", "advance", "snapshot", "events", "peek"):
            params = inspect.signature(getattr(SessionService, name)).parameters
            assert "path" not in params, (
                "%s must not accept a path parameter" % name)
            assert "filename" not in params and "file" not in params, (
                "%s must not accept a file/path parameter" % name)

    def test_a_path_string_supplied_as_id_is_refused_at_the_gate(self, tmp_path):
        # The gate: only a discovered session id may select a source. A path to
        # a real file OUTSIDE the catalogue is not a discovered uuid, so it is
        # refused before any filesystem object named by the caller is touched.
        svc, target, root, path, text, snap = _register_fixture(tmp_path)
        secret = tmp_path / "secret.jsonl"
        secret.write_text('{"type": "user", "message": {"content": "leaked"}}\n')
        with pytest.raises(UnknownSessionId,
                           match="only a discovered session id may select a source"):
            svc.register(str(secret), now=NOW)

    def test_an_unregistered_id_is_refused_with_the_same_gate(self, tmp_path):
        svc, target, root, path, text, snap = _register_fixture(tmp_path)
        # a valid-looking uuid that was never discovered
        with pytest.raises(UnknownSessionId,
                           match="only a discovered session id may select a source"):
            svc.register("11111111-2222-3333-4444-555555555555", now=NOW)

    def test_no_return_value_carries_a_resolved_path(self, tmp_path):
        # The confinement holds on the way out too: snapshot/events/peek expose
        # ids and structured content, never the server-derived path. So a path
        # is neither an input nor an output of any public method.
        svc, target, root, path, text, snap = _register_fixture(tmp_path)
        assert not isinstance(snap.session_node, Path) if snap.session_node else True
        offs = _line_offsets(text)
        byte, length = offs[1]
        for obj in (svc.snapshot(SID), svc.events(SID),
                    svc.peek(SID, byte=byte, length=length)):
            for val in _walk(obj):
                assert not isinstance(val, Path), \
                    "no return value may carry a resolved Path"


def _walk(obj):
    """Yield every dataclass field value / dict value / iterable element."""
    stack = [obj]
    seen = set()
    while stack:
        cur = stack.pop()
        if id(cur) in seen:
            continue
        seen.add(id(cur))
        yield cur
        if hasattr(cur, "__dataclass_fields__"):
            stack.extend(getattr(cur, f) for f in cur.__dataclass_fields__)
        elif isinstance(cur, dict):
            stack.extend(cur.values())
        elif isinstance(cur, (list, tuple)):
            stack.extend(cur)


# === snapshot, cursor and exact event replay ==============================

class TestSnapshotAndEvents:
    def test_register_returns_the_exact_skeleton_and_cursor(self, tmp_path):
        svc, target, root, path, text, snap = _register_fixture(tmp_path)
        # session + two pages (page 0, then page 1 after the boundary)
        assert snap.session_node is not None
        assert snap.session_node.kind == "session"
        assert [p.kind for p in snap.pages] == ["page", "page"]
        # bookmarks: page 0, the user turn, page 1 (3 majors)
        assert [b.kind for b in snap.bookmarks] == ["page", "turn.user", "page"]
        # the three NODE outcomes produce 8 events; 6 lines examined (#671)
        assert snap.cursor == 8
        assert snap.examined == 6
        assert snap.client == session_source.CATALOGUE_CLIENT

    def test_events_replay_the_exact_ordered_stream(self, tmp_path):
        svc, target, root, path, text, snap = _register_fixture(tmp_path)
        delta = svc.events(SID)
        assert delta.cursor == snap.cursor
        # exact (ev, kind) sequence — the wire shape that must stay stable
        seq = [(e.ev, e.node.kind) for e in delta.events]
        assert seq == [
            ("open", "session"), ("open", "page"), ("open", "turn.user"),
            ("open", "turn.agent"), ("open", "step.tool"),
            ("update", "step.tool"), ("close", "turn.agent"),
            ("open", "page"),
        ]

    def test_events_from_a_cursor_returns_only_the_delta(self, tmp_path):
        svc, target, root, path, text, snap = _register_fixture(tmp_path)
        full = svc.events(SID)
        # cursor 4 -> events from index 4 onward
        delta = svc.events(SID, from_cursor=4)
        assert delta.cursor == full.cursor
        assert [e.node.kind for e in delta.events] == [
            "step.tool", "step.tool", "turn.agent", "page"]

    def test_events_from_none_or_stale_recovers_to_a_full_replay(self, tmp_path):
        svc, target, root, path, text, snap = _register_fixture(tmp_path)
        full = svc.events(SID)
        assert svc.events(SID, from_cursor=None).events == full.events
        # a cursor ahead of the server recovers to full rather than crashing
        assert svc.events(SID, from_cursor=99999).events == full.events


class TestUnregisteredSession:
    def test_snapshot_on_an_unregistered_id_is_a_fault(self, tmp_path):
        target, root, path, text = _build_world(tmp_path, [])
        svc = SessionService(target, projects_root=root)
        with pytest.raises(SessionNotRegistered):
            svc.snapshot(SID)

    def test_peek_on_an_unregistered_id_is_a_fault(self, tmp_path):
        target, root, path, text = _build_world(tmp_path, [])
        svc = SessionService(target, projects_root=root)
        with pytest.raises(SessionNotRegistered):
            svc.peek(SID, byte=0, length=10)


# === the three classifier outcomes stay distinguishable (#702) =============

class TestThreeOutcomesDistinguishable:
    def test_node_suppressed_and_unclassifiable_render_distinctly(self, tmp_path):
        # The fixture has one UNCLASSIFIABLE record (reported) and one
        # SUPPRESSED record (silent). They must not collapse: exactly one
        # diagnostic (not two), and the suppressed record produces no event.
        svc, target, root, path, text, snap = _register_fixture(tmp_path)
        # NODE — the scan emitted real tree events
        assert snap.cursor > 0
        # UNCLASSIFIABLE — reported as a diagnostic with a reason (#702)
        assert len(snap.diagnostics) == 1
        assert snap.diagnostics[0].reason
        # SUPPRESSED — absent from both events and diagnostics (#755). If the
        # suppressed record had leaked as unclassifiable, diagnostics would be
        # 2; if as a node, cursor would exceed 8.
        assert len(snap.diagnostics) == 1
        assert snap.cursor == 8


# === deleted vs empty: a fault is not a calm nothing (#136) ===============

class TestDeletedVersusEmpty:
    def test_an_empty_session_is_not_a_fault(self, tmp_path):
        target, root, path, text = _build_world(tmp_path, [])
        svc = SessionService(target, projects_root=root)
        snap = svc.register(SID, now=NOW)
        # honest empty: zero events, zero examined, no session opened (#671)
        assert snap.cursor == 0
        assert snap.examined == 0
        assert snap.pages == ()
        assert snap.session_node is None

    def test_a_session_deleted_between_catalogue_and_read_is_a_fault(
            self, tmp_path):
        from unittest.mock import patch
        target, root, path, text = _build_world(tmp_path, _fixture_records())
        # precondition: the id IS discovered while the file exists. The catalogue
        # uses iterdir/stat/open — NOT read_text — so it discovers the file here.
        cat = session_source.catalogue(target, projects_root=root, now=NOW)
        assert SID in {e.session_id for e in cat.entries}
        # Simulate the genuine race: the file is present for catalogue+resolve
        # but vanishes before the service's read_text. Patching read_text leaves
        # catalogue/resolve running for real; only the read step fails. The
        # production line is the `except (FileNotFoundError, OSError)` handler —
        # removing it propagates FileNotFoundError instead of SessionGone.
        with patch.object(Path, "read_text", side_effect=FileNotFoundError):
            svc = SessionService(target, projects_root=root)
            with pytest.raises(SessionGone):
                svc.register(SID, now=NOW)

    def test_deleted_and_empty_render_differently(self, tmp_path):
        from unittest.mock import patch
        # #136: distinct nothings must not read the same. An empty session
        # returns a snapshot; a deleted one raises a typed fault.
        empty_target, empty_root, _, _ = _build_world(
            tmp_path / "empty", [])
        svc_empty = SessionService(empty_target, projects_root=empty_root)
        snap = svc_empty.register(SID, now=NOW)  # calm, not a fault

        del_target, del_root, del_path, _ = _build_world(
            tmp_path / "gone", _fixture_records())
        with patch.object(Path, "read_text", side_effect=FileNotFoundError):
            svc_gone = SessionService(del_target, projects_root=del_root)
            with pytest.raises(SessionGone):
                svc_gone.register(SID, now=NOW)
        # the two findings are different kinds of answer
        assert snap.cursor == 0


# === snapshot/cursor consistency (Direction 2a) ===========================

class TestSnapshotCursorConsistency:
    """The skeleton and the cursor are projections of ONE held ring computed in
    the same call, so they cannot disagree. The test proves that is a property,
    not an assumption: advancing the ring after register must move the skeleton
    too — a stale cached snapshot would leave it behind."""

    def test_snapshot_advances_with_the_ring_not_a_stale_cache(self, tmp_path):
        svc, target, root, path, text, snap0 = _register_fixture(tmp_path)
        assert snap0.cursor == 8
        bm0 = len(snap0.bookmarks)
        # grow the source: append a new user turn under the open page
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(_user_turn("u9", "more", minutes_ago=1)) + "\n")
        delta = svc.advance(SID)
        assert len(delta.events) > 0
        snap1 = svc.snapshot(SID)
        # the skeleton reflects the advanced ring — cursor and bookmarks grew
        assert snap1.cursor == delta.cursor > snap0.cursor
        assert len(snap1.bookmarks) > bm0
        # snapshot.cursor and events.cursor agree (same held ring, same call)
        assert snap1.cursor == svc.events(SID).cursor

    def test_advance_is_idempotent_when_the_source_did_not_grow(self, tmp_path):
        svc, target, root, path, text, snap = _register_fixture(tmp_path)
        before = svc.snapshot(SID).cursor
        delta = svc.advance(SID)
        assert delta.events == ()
        assert delta.cursor == before

    def test_peek_after_advance_reads_the_grown_source_not_stale_text(
            self, tmp_path):
        # Direction-2 guard: removing `held.text = text` from `_ingest` leaves
        # every existing test green while a peek over a range an ADVANCE
        # registered reads stale text. This test is the one that reds.
        svc, target, root, path, text, snap = _register_fixture(tmp_path)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(_user_turn("zz", "peekme", minutes_ago=1))
                    + "\n")
        delta = svc.advance(SID)
        assert delta.events  # precondition: the advance registered a new range
        offs = _line_offsets(path.read_text())  # re-derive from the grown file
        byte, length = offs[-1]
        pk = svc.peek(SID, byte=byte, length=length)
        assert pk.parse_error is None
        # the record is a fresh re-derivation from the grown source, not the
        # stale text; if held.text were not updated, this is the line that reds
        assert pk.record["message"]["content"] == "peekme"


# === bounded peek over a registered source range ==========================

class TestBoundedPeek:
    def test_peek_returns_the_exact_registered_record_re_derived(self, tmp_path):
        # #645 i7 shape: re-derive the expected length/content independently,
        # do not naive-compare. The peeked length must equal the request, and
        # the parsed record must equal a fresh re-derivation from the source.
        svc, target, root, path, text, snap = _register_fixture(tmp_path)
        offs = _line_offsets(text)
        byte, length = offs[1]  # the assistant tool_use line -> step.tool node
        pk = svc.peek(SID, byte=byte, length=length)
        assert pk.parse_error is None
        assert pk.length == length            # read count == requested
        expected = json.loads(text[byte:byte + length])  # independent re-derivation
        assert pk.record == expected
        assert pk.record["type"] == "assistant"

    def test_peek_rejects_an_unregistered_byte(self, tmp_path):
        svc, target, root, path, text, snap = _register_fixture(tmp_path)
        # a byte past the end is not a registered record start
        with pytest.raises(PeekOutOfBounds, match="not a registered"):
            svc.peek(SID, byte=len(text) + 100, length=10)

    def test_peek_rejects_a_length_above_the_registered_range(self, tmp_path):
        svc, target, root, path, text, snap = _register_fixture(tmp_path)
        offs = _line_offsets(text)
        byte, length = offs[1]
        with pytest.raises(PeekOutOfBounds, match="exceeds the registered range"):
            svc.peek(SID, byte=byte, length=length + 1)

    def test_peek_rejects_a_length_above_the_global_bound(self, tmp_path):
        svc, target, root, path, text, snap = _register_fixture(tmp_path)
        offs = _line_offsets(text)
        byte, _ = offs[1]
        with pytest.raises(PeekOutOfBounds):
            svc.peek(SID, byte=byte, length=MAX_PEEK_LEN + 1)


# === thread safety: what the lock establishes (#651) ======================

class TestThreadSafety:
    """What these establish: the single re-entrant lock serialises every
    mutation and every read of held state, so concurrent callers cannot
    interleave a register/advance with a snapshot/events/peek on the same
    session, and concurrent advances cannot double-ingest. What they do NOT
    establish: a specific scheduling, lock-freedom, or behaviour under a lock
    ordering (there is one lock, so there is no ordering to deadlock on)."""

    def test_concurrent_reads_are_consistent(self, tmp_path):
        svc, target, root, path, text, snap = _register_fixture(tmp_path)
        errors = []
        expected = svc.events(SID).events  # the canonical ordered stream

        def reader():
            try:
                last = -1
                for _ in range(200):
                    s = svc.snapshot(SID)
                    d = svc.events(SID)
                    assert s.cursor == d.cursor, "snapshot/cursor disagree"
                    assert s.cursor >= last, "cursor went backwards"
                    last = s.cursor
                    # the ordered stream is stable under concurrent reads
                    assert d.events == expected, "event stream changed mid-read"
            except Exception as exc:  # noqa: BLE001 - collected, not swallowed
                errors.append(exc)

        threads = [threading.Thread(target=reader) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors

    def test_concurrent_advances_never_double_ingest(self, tmp_path):
        svc, target, root, path, text, snap = _register_fixture(tmp_path)
        base = svc.snapshot(SID).cursor
        # append three new user turns at once, then race eight advances
        with open(path, "a", encoding="utf-8") as f:
            for i in range(3):
                f.write(json.dumps(_user_turn("c%d" % i, str(i), minutes_ago=1))
                        + "\n")
        results = [None] * 8

        def worker(i):
            try:
                results[i] = svc.advance(SID)
            except Exception as exc:  # noqa: BLE001
                results[i] = exc

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        for r in results:
            assert not isinstance(r, Exception), r
        nonempty = [r for r in results if r and len(r.events) > 0]
        # exactly one advance ingested the new turns; the rest scanned nothing.
        # If two had ingested, the new events would appear twice in the ring.
        assert len(nonempty) == 1, "more than one advance ingested events"
        final = svc.snapshot(SID)
        # the ring grew by exactly the events one advance produced — no double
        assert final.cursor == base + len(nonempty[0].events)
