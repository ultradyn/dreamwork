"""Exact grammar-table proof for the Claude Code record classifier (#631 inc 2),
plus the full hierarchy scan proof (#631 increment 3).

Every §2 grammar row is exercised by a hand-authored fixture (no real session
content is copied into the repo).  The two named injections are isolated tests
with their discriminating assertions called out in the assertion messages.
"""

import json

import pytest

from session_log.claude_code import (
    NODE,
    SUPPRESSED,
    UNCLASSIFIABLE,
    Bookmark,
    Classification,
    Diagnostic,
    ScanResult,
    ToolFacts,
    classify_record,
    scan_complete,
)
from session_log.model import SessionEvent, SessionNode, SourceRef

# All fixtures share a fixed source position so SourceRef is predictable.
_REF = dict(line=1, byte=0, length=120)


def _classify(record, **pos):
    pos = {**_REF, **pos}
    return classify_record(record, **pos)


# --- helpers to build minimal hand-authored fixtures -----------------------

def _user(content, **extra):
    record = {"type": "user", "uuid": "u1", "timestamp": "2026-08-01T02:03:04Z",
              "message": {"role": "user", "content": content}}
    record.update(extra)
    return record


def _assistant(block, **extra):
    record = {"type": "assistant", "uuid": "a1", "timestamp": "2026-08-01T02:03:05Z",
              "message": {"role": "assistant", "content": [block]}}
    record.update(extra)
    return record


def _system(subtype, **extra):
    record = {"type": "system", "subtype": subtype, "uuid": "s1",
              "timestamp": "2026-08-01T02:03:06Z"}
    record.update(extra)
    return record


# === the exact table over every §2 grammar row =============================

@pytest.mark.parametrize("label,record,expected_kind", [
    # --- user rows ---
    ("plain-string user turn",
     _user("do the thing"),
     "turn.user"),
    ("text-block user turn",
     _user([{"type": "text", "text": "a message"}]),
     "turn.user"),
    ("tool_result is a step not a turn",
     _user([{"type": "tool_result", "tool_use_id": "toolu_1",
             "content": "ok", "is_error": False}]),
     "step.tool"),
    ("isCompactSummary user record",
     _user("continued from prior context", isCompactSummary=True),
     "sys.compact"),
    ("isMeta user record",
     _user([{"type": "text", "text": "skill preamble"}], isMeta=True),
     "sys.note"),
    # --- assistant rows ---
    ("assistant text block",
     _assistant({"type": "text", "text": "I will do it."}),
     "step.text"),
    ("assistant tool_use block",
     _assistant({"type": "tool_use", "id": "toolu_1", "name": "Bash",
                 "input": {"command": "echo hi"}}),
     "step.tool"),
    ("assistant thinking block",
     _assistant({"type": "thinking", "thinking": "planning…",
                 "signature": "sig"}),
     "step.thinking"),
    # --- system rows ---
    ("system compact_boundary",
     _system("compact_boundary", content="Conversation compacted",
             compactMetadata={"trigger": "auto", "preTokens": 287809,
                              "postTokens": 19920}),
     "page"),
    ("system stop_hook_summary",
     _system("stop_hook_summary", hookCount=1),
     "sys.note"),
    ("system turn_duration",
     _system("turn_duration", durationMs=1122, messageCount=5),
     "sys.note"),
    ("system away_summary",
     _system("away_summary", content="away for a bit"),
     "sys.note"),
])
def test_each_grammar_row_classifies_to_its_kind(label, record, expected_kind):
    result = _classify(record)
    assert result.outcome == NODE, f"{label}: expected NODE, got {result.outcome}"
    assert result.kind == expected_kind, (
        f"{label}: expected kind {expected_kind!r}, got {result.kind!r}")


def test_every_node_kind_from_the_table_is_in_the_closed_vocabulary():
    """The classifier must not widen the vocabulary increment 1 closed."""
    from session_log.model import NODE_KINDS
    covered = {
        "turn.user", "step.tool", "sys.compact", "sys.note",
        "step.text", "step.thinking", "page",
    }
    assert covered <= NODE_KINDS, (
        "a grammar-row kind is not in the closed vocabulary — "
        "the classifier must not invent kinds")


# === injection 1: tool_result is a step, not a turn start ==================

def test_tool_result_classifies_as_step_not_turn_start():
    """If tool_result were classified as turn.user, this reds on the message
    'tool results are steps, not turn starts'."""
    record = _user([{"type": "tool_result", "tool_use_id": "toolu_9",
                     "content": "done", "is_error": False}])
    result = _classify(record)
    # The discriminating assertion: the kind is step.tool, NOT turn.user.
    assert result.kind == "step.tool", (
        "tool results are steps, not turn starts")
    assert result.tool.is_result is True
    assert result.tool.tool_use_id == "toolu_9"
    assert result.tool.is_error is False


# A plain user turn must NOT be classified as a tool result — the inverse
# discrimination, proving the content-shape check goes both ways.
def test_plain_user_turn_is_not_a_tool_result():
    record = _user("hello there")
    result = _classify(record)
    assert result.kind == "turn.user", (
        "a plain-string user message is a turn start, not a tool result")
    assert result.tool is None


# === injection 2: unknown chrome is suppressed, not relabelled =============

def test_unknown_chrome_is_suppressed_not_relabelled_as_sys_note():
    """An unknown non-content record must be SUPPRESSED, not quietly emitted
    as sys.note.  The discriminating assertion is outcome == SUPPRESSED with
    kind is None: if the record were silently relabelled, outcome would be
    NODE and kind would be 'sys.note'."""
    record = {"type": "some-brand-new-metadata", "sessionId": "s1"}
    result = _classify(record)
    # This is the assertion that tells "suppressed" from "quietly relabelled":
    # the outcome discriminates them, and a suppressed record carries no kind.
    assert result.outcome == SUPPRESSED, (
        "unknown chrome must be suppressed, not emitted as a node")
    assert result.kind is None, (
        "a suppressed record carries no node kind — if this is sys.note "
        "the record was silently relabelled")
    assert "some-brand-new-metadata" in result.reason


# Known chrome types are suppressed too — not a separate code path.
@pytest.mark.parametrize("ctype", [
    "mode", "last-prompt", "permission-mode", "ai-title",
    "queue-operation", "attachment", "file-history-delta",
    "file-history-snapshot",
])
def test_known_chrome_is_suppressed(ctype):
    record = {"type": ctype, "sessionId": "s1"}
    result = _classify(record)
    assert result.outcome == SUPPRESSED
    assert result.kind is None


# === #702: unclassifiable is reported, not dropped =========================

def test_unrecognised_system_subtype_is_reported_not_dropped():
    """A content-type record with an unknown structure must be UNCLASSIFIABLE,
    not silently dropped or suppressed (#702)."""
    record = _system("brand-new-subtype")
    result = _classify(record)
    assert result.outcome == UNCLASSIFIABLE
    assert result.kind is None
    assert "brand-new-subtype" in result.reason


def test_assistant_with_unknown_block_type_is_unclassifiable():
    record = _assistant({"type": "redacted", "data": "???"})
    result = _classify(record)
    assert result.outcome == UNCLASSIFIABLE
    assert result.kind is None


def test_user_with_unrecognised_content_is_unclassifiable():
    record = {"type": "user", "uuid": "u1", "message": {"content": 42}}
    result = _classify(record)
    assert result.outcome == UNCLASSIFIABLE
    assert result.kind is None


def test_user_with_non_text_non_tool_result_block_is_unclassifiable():
    """Direction-2 false-green closer: if _is_text_content accepted any list
    (not just text blocks), an image-block user message would wrongly classify
    as turn.user while every grammar-table fixture stayed green.  §2 describes
    only string/text blocks for user turns; an image block matches no row."""
    record = _user([{"type": "image", "source": {"data": "base64…"}}])
    result = _classify(record)
    assert result.outcome == UNCLASSIFIABLE, (
        "a user message with a non-text, non-tool_result block matches no "
        "grammar row — it must be unclassifiable, not a turn start")
    assert result.kind is None


def test_suppressed_and_unclassifiable_are_distinct_outcomes():
    """#136: 'suppressed by design' and 'unclassifiable' must not render
    identically.  A non-content type is suppressed; a content type with an
    unrecognised structure is unclassifiable — and the two differ."""
    chrome = _classify({"type": "mode"})
    unknown = _classify(_system("never-seen"))
    assert chrome.outcome == SUPPRESSED
    assert unknown.outcome == UNCLASSIFIABLE
    assert chrome.outcome != unknown.outcome


# === extracted facts ========================================================

def test_timestamp_is_extracted_from_the_record():
    record = _user("hi", timestamp="2026-08-01T12:00:00.000Z")
    result = _classify(record)
    assert result.ts == "2026-08-01T12:00:00.000Z"


def test_missing_timestamp_is_none_not_fabricated():
    record = {"type": "user", "uuid": "u1", "message": {"content": "hi"}}
    result = _classify(record)
    assert result.ts is None


def test_source_ref_is_built_from_passed_position():
    record = _user("hi")
    result = classify_record(record, line=42, byte=840, length=121)
    assert result.ref == SourceRef(line=42, byte=840, length=121)


def test_tool_use_facts_carry_name_and_id():
    record = _assistant({"type": "tool_use", "id": "toolu_7", "name": "Edit",
                         "input": {"file_path": "f.txt"}})
    result = _classify(record)
    assert result.kind == "step.tool"
    assert result.tool == ToolFacts(name="Edit", tool_use_id="toolu_7")


def test_tool_result_facts_carry_id_and_error():
    record = _user([{"type": "tool_result", "tool_use_id": "toolu_7",
                     "content": "exit 1", "is_error": True}])
    result = _classify(record)
    assert result.kind == "step.tool"
    assert result.tool == ToolFacts(tool_use_id="toolu_7", is_error=True,
                                    is_result=True)


def test_uuid_is_extracted_for_identity():
    record = _user("hi", uuid="abc-123")
    result = _classify(record)
    assert result.uuid == "abc-123"


# === increment 3: full hierarchy scan ======================================
#
# The oracle below is HAND-AUTHORED: every expected event's kind, parent,
# state, id and seq were derived from the tree-building rules in §2/§3 of the
# design, not by running the scanner.  Byte positions are computed by
# ``_byte_offsets`` — simple string arithmetic over the raw lines — which is a
# different code path from the scanner's ``_iter_records`` (it does no JSON
# parsing, no classification, no tree building).  This independence is what
# makes the ordered-stream assertion non-vacuous (#645 FALSE GREEN lesson).

# --- frozen transcript ------------------------------------------------------

def _line(d):
    """Compact JSON for a transcript line."""
    return json.dumps(d, separators=(",", ":"), sort_keys=True)


_FROZEN_LINES = [
    _line({"type": "user", "uuid": "u1", "sessionId": "s1",
           "timestamp": "T1",
           "message": {"role": "user", "content": "hello"}}),
    _line({"type": "assistant", "uuid": "a1", "sessionId": "s1",
           "timestamp": "T2", "requestId": "r1",
           "message": {"role": "assistant", "id": "m1",
                       "content": [{"type": "text", "text": "hi"}]}}),
    _line({"type": "assistant", "uuid": "a2", "sessionId": "s1",
           "timestamp": "T3", "requestId": "r1",
           "message": {"role": "assistant", "id": "m1",
                       "content": [{"type": "tool_use", "id": "tu1",
                                    "name": "Bash",
                                    "input": {"command": "echo hi"}}]}}),
    _line({"type": "user", "uuid": "u2", "sessionId": "s1",
           "timestamp": "T4",
           "message": {"role": "user",
                       "content": [{"type": "tool_result",
                                    "tool_use_id": "tu1",
                                    "content": "hi", "is_error": False}]}}),
    _line({"type": "assistant", "uuid": "a3", "sessionId": "s1",
           "timestamp": "T5", "requestId": "r1",
           "message": {"role": "assistant", "id": "m1",
                       "content": [{"type": "text", "text": "done"}]}}),
    _line({"type": "system", "uuid": "sy1", "sessionId": "s1",
           "timestamp": "T6", "subtype": "stop_hook_summary",
           "hookCount": 1}),
    _line({"type": "user", "uuid": "u3", "sessionId": "s1",
           "timestamp": "T7",
           "message": {"role": "user", "content": "next"}}),
    _line({"type": "assistant", "uuid": "a4", "sessionId": "s1",
           "timestamp": "T8", "requestId": "r2",
           "message": {"role": "assistant", "id": "m2",
                       "content": [{"type": "text", "text": "working"}]}}),
    _line({"type": "system", "uuid": "sy2", "sessionId": "s1",
           "timestamp": "T9", "subtype": "compact_boundary",
           "content": "compacted",
           "compactMetadata": {"trigger": "auto", "preTokens": 100,
                               "postTokens": 50}}),
    _line({"type": "mode", "sessionId": "s1", "leafUuid": "u1"}),
]
_FROZEN_TEXT = "\n".join(_FROZEN_LINES) + "\n"


def _byte_offsets(lines):
    """Compute (line, byte, length) per line by pure string arithmetic.

    Independent of the scanner: no json.loads, no classify_record, no tree
    building — just cumulative byte counting.  Used to build the oracle's
    expected SourceRefs without running the code under test.
    """
    out = []
    byte = 0
    for i, raw in enumerate(lines, 1):
        out.append((i, byte, len(raw)))
        byte += len(raw) + 1  # +1 for newline
    return out


_POS = _byte_offsets(_FROZEN_LINES)


def _ref(line_no):
    """Expected SourceRef for *line_no* (1-based) in the frozen transcript."""
    ln, byt, ln1 = _POS[line_no - 1]
    return SourceRef(line=ln, byte=byt, length=ln1)


# The hand-authored oracle: 15 events in exact order, each with the expected
# ev type, node kind, seq, state and id.  Derived from §2/§3 rules, NOT by
# running scan_complete.

def _expected_frozen_events():
    S = "sess:s1"
    P0 = f"{S}/pg:0"
    P1 = f"{S}/pg:1"
    A1 = f"{P0}/a:r1"      # agent turn grouped by requestId r1
    A2 = f"{P0}/a:r2"      # agent turn grouped by requestId r2
    return [
        ("open", SessionNode(id=S, parent=None, kind="session", seq=1,
                             ts="T1", label="session s1", state="live")),
        ("open", SessionNode(id=P0, parent=S, kind="page", seq=2, ts="T1",
                             label="page 0", state="live", ref=_ref(1))),
        ("open", SessionNode(id=f"{P0}/u:u1", parent=P0, kind="turn.user",
                             seq=3, ts="T1", label="user turn",
                             state="done", ref=_ref(1))),
        ("open", SessionNode(id=A1, parent=P0, kind="turn.agent", seq=4,
                             ts="T2", label="agent turn", state="live",
                             ref=_ref(2))),
        ("open", SessionNode(id=f"{A1}/a1", parent=A1, kind="step.text",
                             seq=5, ts="T2", label="text", state="done",
                             ref=_ref(2))),
        ("open", SessionNode(id=f"{A1}/a2", parent=A1, kind="step.tool",
                             seq=6, ts="T3", label="Bash", state="live",
                             ref=_ref(3))),
        ("update", SessionNode(id=f"{A1}/a2", parent=A1, kind="step.tool",
                               seq=6, ts="T4", label="Bash", state="done",
                               ref=_ref(3))),
        ("open", SessionNode(id=f"{A1}/a3", parent=A1, kind="step.text",
                             seq=7, ts="T5", label="text", state="done",
                             ref=_ref(5))),
        ("open", SessionNode(id=f"{P0}/n:sy1", parent=P0, kind="sys.note",
                             seq=8, ts="T6", label="system note",
                             state="done", ref=_ref(6))),
        ("close", SessionNode(id=A1, parent=P0, kind="turn.agent", seq=4,
                              ts="T7", label="agent turn", state="done")),
        ("open", SessionNode(id=f"{P0}/u:u3", parent=P0, kind="turn.user",
                             seq=9, ts="T7", label="user turn",
                             state="done", ref=_ref(7))),
        ("open", SessionNode(id=A2, parent=P0, kind="turn.agent", seq=10,
                             ts="T8", label="agent turn", state="live",
                             ref=_ref(8))),
        ("open", SessionNode(id=f"{A2}/a4", parent=A2, kind="step.text",
                             seq=11, ts="T8", label="text", state="done",
                             ref=_ref(8))),
        ("close", SessionNode(id=A2, parent=P0, kind="turn.agent", seq=10,
                              ts="T9", label="agent turn", state="done")),
        ("open", SessionNode(id=P1, parent=S, kind="page", seq=12, ts="T9",
                             label="page 1", state="live", ref=_ref(9))),
    ]


def _expected_frozen_bookmarks():
    return [
        Bookmark(seq=1, kind="page", line=1, byte=_POS[0][1],
                 ts="T1", label="page 0", node_id="sess:s1/pg:0"),
        Bookmark(seq=2, kind="turn.user", line=1, byte=_POS[0][1],
                 ts="T1", label="user turn",
                 node_id="sess:s1/pg:0/u:u1"),
        Bookmark(seq=3, kind="turn.user", line=7, byte=_POS[6][1],
                 ts="T7", label="user turn",
                 node_id="sess:s1/pg:0/u:u3"),
        Bookmark(seq=4, kind="page", line=9, byte=_POS[8][1],
                 ts="T9", label="page 1", node_id="sess:s1/pg:1"),
    ]


def test_frozen_transcript_complete_ordered_wire_stream():
    """The complete ordered event stream must match the hand-authored oracle
    exactly — every event type, node id, parent, kind, seq, ts, label, state
    and ref.  This is the load-bearing assertion: if any tree-building rule
    is wrong, exactly one line of this comparison reds with the mismatch."""
    result = scan_complete(_FROZEN_TEXT)
    expected = _expected_frozen_events()
    assert len(result.events) == len(expected), (
        f"event count mismatch: got {len(result.events)}, "
        f"expected {len(expected)} — the scanner built a different tree")
    for i, (ev_exp, node_exp) in enumerate(expected):
        actual = result.events[i]
        assert actual.ev == ev_exp, (
            f"event {i}: expected ev={ev_exp!r}, got {actual.ev!r}")
        assert actual.node == node_exp, (
            f"event {i} ({ev_exp}): node mismatch — "
            f"expected {node_exp}, got {actual.node}")


def test_frozen_transcript_exact_bookmark_set():
    """The bookmark set must be exactly page boundaries + user-turn starts,
    no more, no less (§4).  Counting a tool result as a major event would
    inflate this set — injection 2 in the proof."""
    result = scan_complete(_FROZEN_TEXT)
    expected = _expected_frozen_bookmarks()
    assert result.bookmarks == tuple(expected), (
        f"bookmark mismatch — expected {len(expected)} bookmarks, "
        f"got {len(result.bookmarks)}: {result.bookmarks}")


def test_frozen_transcript_stable_ids_and_parents():
    """Every node id is content-stable (§3): session/page paths derived from
    session id and page number; turns keyed by record uuid / requestId; steps
    keyed by record uuid.  Parents point up the hierarchy."""
    result = scan_complete(_FROZEN_TEXT)
    ids = {ev.node.id for ev in result.events}
    # No duplicate ids among open events (stable identity)
    opens = [ev for ev in result.events if ev.ev == "open"]
    open_ids = [ev.node.id for ev in opens]
    assert len(open_ids) == len(set(open_ids)), (
        "duplicate node ids among open events — identity is not stable")
    # Parent chain: every non-root node's parent exists as a node id
    root = "sess:s1"
    for ev in result.events:
        if ev.node.parent is not None:
            assert ev.node.parent in ids, (
                f"node {ev.node.id} has parent {ev.node.parent!r} "
                f"that is not any node's id")


def test_frozen_transcript_state_transitions():
    """The tool step opens live and transitions to done on its result.
    The agent turn opens live and closes done.  User turns open done."""
    result = scan_complete(_FROZEN_TEXT)
    # Find the paired tool step (seq=6)
    tool_events = [ev for ev in result.events if ev.node.seq == 6]
    assert len(tool_events) == 2, (
        "a paired tool step must have exactly two events (open + update)")
    assert tool_events[0].ev == "open"
    assert tool_events[0].node.state == "live"
    assert tool_events[1].ev == "update"
    assert tool_events[1].node.state == "done"
    # Agent turn r1 (seq=4) opens live, closes done
    agent_events = [ev for ev in result.events if ev.node.seq == 4]
    assert agent_events[0].node.state == "live"
    assert agent_events[-1].node.state == "done"


def test_frozen_transcript_exact_line_byte_refs():
    """Every node backed by a record carries the exact line/byte/length of
    that record in the source file (§3 ref)."""
    result = scan_complete(_FROZEN_TEXT)
    for ev in result.events:
        if ev.node.ref is not None:
            ln, byt, ln1 = _POS[ev.node.ref.line - 1]
            assert ev.node.ref == SourceRef(line=ln, byte=byt, length=ln1), (
                f"node {ev.node.id} ref mismatch: "
                f"expected ({ln},{byt},{ln1}), got {ev.node.ref}")


def test_frozen_transcript_examined_count():
    """The scan examined all 10 non-empty lines — including the suppressed
    chrome record (#671: examined count is the denominator that proves
    the scan actually ran)."""
    result = scan_complete(_FROZEN_TEXT)
    assert result.examined == 10


# === #671: empty transcript must not read as passing =======================

def test_empty_transcript_examined_zero_not_confident_empty():
    """An empty transcript must produce examined=0 with no events, which is
    distinct from a successful scan that produced a real tree (#671).
    The assertion that discriminates: examined == 0 AND no events, versus
    a real scan where examined > 0 AND events exist."""
    result = scan_complete("")
    assert result.examined == 0, (
        "an empty transcript examined nothing — examined must be 0, not a "
        "confident-looking positive count")
    assert result.events == ()
    assert result.bookmarks == ()


def test_all_chrome_transcript_examined_but_no_events():
    """A transcript with only suppressed chrome records must report
    examined > 0 (it DID process records) but produce no events (#755:
    silent on healthy input).  This is distinct from empty (examined=0)
    and from a real scan (has events)."""
    text = _line({"type": "mode", "sessionId": "s1"}) + "\n" + \
           _line({"type": "last-prompt", "sessionId": "s1"}) + "\n"
    result = scan_complete(text)
    assert result.examined == 2, (
        "the scan processed 2 chrome records — examined must reflect that")
    assert result.events == (), (
        "chrome-only input must produce no events (#755)")


# === #702: unclassifiable records reported, not dropped ====================

def test_unclassifiable_records_appear_in_diagnostics():
    """An unclassifiable record must appear in diagnostics, not be silently
    dropped (#702).  The scanner carries it forward for a human to see."""
    text = _line({"type": "system", "uuid": "x1", "sessionId": "s1",
                   "timestamp": "T1", "subtype": "never-seen"}) + "\n"
    result = scan_complete(text)
    assert len(result.diagnostics) == 1, (
        "an unclassifiable record must be reported as a diagnostic, "
        "not dropped silently")
    assert "never-seen" in result.diagnostics[0].reason


# === malformed input: unpaired tool_use and orphan tool_result =============

def test_unpaired_tool_use_stays_live():
    """A tool_use with no matching result (a killed session) must open with
    state=live and never receive an update — distinct from a paired step
    which transitions to done (#136)."""
    text = "\n".join([
        _line({"type": "user", "uuid": "u1", "sessionId": "s",
               "timestamp": "T1", "message": {"role": "user", "content": "go"}}),
        _line({"type": "assistant", "uuid": "a1", "sessionId": "s",
               "timestamp": "T2", "requestId": "r1",
               "message": {"role": "assistant", "id": "m1",
                           "content": [{"type": "tool_use", "id": "tu1",
                                        "name": "Bash",
                                        "input": {"command": "ls"}}]}}),
    ]) + "\n"
    result = scan_complete(text)
    tool_opens = [ev for ev in result.events
                  if ev.node.kind == "step.tool" and ev.ev == "open"]
    assert len(tool_opens) == 1
    assert tool_opens[0].node.state == "live", (
        "an unpaired tool_use must stay live — it never got its result")
    # No update event for this tool
    updates = [ev for ev in result.events if ev.ev == "update"]
    assert updates == [], (
        "an unpaired tool_use must have no update event")


def test_orphan_tool_result_emitted_with_done_state():
    """A tool_result with no preceding tool_use must be emitted as a new
    step.tool node with state already done — not crashed, not silently
    dropped, and not rendered identically to a paired or still-open step
    (#136)."""
    text = "\n".join([
        _line({"type": "user", "uuid": "u1", "sessionId": "s",
               "timestamp": "T1",
               "message": {"role": "user", "content": "hi"}}),
        _line({"type": "assistant", "uuid": "a1", "sessionId": "s",
               "timestamp": "T2", "requestId": "r1",
               "message": {"role": "assistant", "id": "m1",
                           "content": [{"type": "text", "text": "ok"}]}}),
        _line({"type": "user", "uuid": "u2", "sessionId": "s",
               "timestamp": "T3",
               "message": {"role": "user",
                           "content": [{"type": "tool_result",
                                        "tool_use_id": "orphan1",
                                        "content": "?", "is_error": False}]}}),
    ]) + "\n"
    result = scan_complete(text)
    orphan_opens = [ev for ev in result.events
                    if ev.node.kind == "step.tool" and ev.ev == "open"
                    and "orphan" in ev.node.id]
    assert len(orphan_opens) == 1, (
        "an orphan tool_result must be emitted as its own step.tool node")
    assert orphan_opens[0].node.state == "done", (
        "an orphan result has no preceding use — it opens done, not live")
    assert "orphan" in orphan_opens[0].node.label.lower(), (
        "the orphan's label must distinguish it from a paired tool step")


def test_paired_still_open_and_orphaned_render_differently():
    """The three tool-step fates must be distinguishable in the event stream
    (#136): paired (open+update), still-open (open only, state=live),
    orphaned (open only, state=done, label says orphan)."""
    text = "\n".join([
        # turn 1: paired tool
        _line({"type": "user", "uuid": "u1", "sessionId": "s",
               "timestamp": "T1", "message": {"role": "user", "content": "1"}}),
        _line({"type": "assistant", "uuid": "a1", "sessionId": "s",
               "timestamp": "T2", "requestId": "r1",
               "message": {"role": "assistant", "id": "m1",
                           "content": [{"type": "tool_use", "id": "paired",
                                        "name": "Bash",
                                        "input": {"command": "x"}}]}}),
        _line({"type": "user", "uuid": "u2", "sessionId": "s",
               "timestamp": "T3",
               "message": {"role": "user",
                           "content": [{"type": "tool_result",
                                        "tool_use_id": "paired",
                                        "content": "ok",
                                        "is_error": False}]}}),
        # turn 2: unpaired tool (killed session)
        _line({"type": "user", "uuid": "u3", "sessionId": "s",
               "timestamp": "T4", "message": {"role": "user", "content": "2"}}),
        _line({"type": "assistant", "uuid": "a2", "sessionId": "s",
               "timestamp": "T5", "requestId": "r2",
               "message": {"role": "assistant", "id": "m2",
                           "content": [{"type": "tool_use", "id": "unpaired",
                                        "name": "Read",
                                        "input": {"file_path": "f"}}]}}),
        # orphan tool_result (no preceding use)
        _line({"type": "user", "uuid": "u4", "sessionId": "s",
               "timestamp": "T6",
               "message": {"role": "user",
                           "content": [{"type": "tool_result",
                                        "tool_use_id": "ghost",
                                        "content": "?",
                                        "is_error": False}]}}),
    ]) + "\n"
    result = scan_complete(text)
    tool_nodes = {}
    for ev in result.events:
        if ev.node.kind == "step.tool":
            tool_nodes.setdefault(ev.node.id, []).append(ev)

    # Paired: two events (open live + update done)
    paired = [evs for nid, evs in tool_nodes.items()
              if any(e.node.state == "live" and e.ev == "open" for e in evs)
              and any(e.ev == "update" for e in evs)]
    assert len(paired) == 1, f"expected 1 paired tool, got {len(paired)}"

    # Still-open: one event (open live, no update)
    still_open = [evs for nid, evs in tool_nodes.items()
                  if len(evs) == 1
                  and evs[0].node.state == "live"
                  and evs[0].ev == "open"]
    assert len(still_open) == 1, (
        f"expected 1 still-open tool, got {len(still_open)}")

    # Orphaned: one event (open done, label contains 'orphan')
    orphaned = [evs for nid, evs in tool_nodes.items()
                if len(evs) == 1
                and evs[0].node.state == "done"
                and "orphan" in evs[0].node.label.lower()]
    assert len(orphaned) == 1, (
        f"expected 1 orphaned tool result, got {len(orphaned)}")

    # The three are distinct by their event signatures
    sigs = {
        ("paired", len(paired[0]), paired[0][0].node.state),
        ("still_open", len(still_open[0]), still_open[0][0].node.state),
        ("orphaned", len(orphaned[0]), orphaned[0][0].node.state),
    }
    assert len(sigs) == 3, (
        "paired, still-open and orphaned must have distinct event signatures")


# === injection 1: requestId grouping =======================================
#
# Two assistant records sharing requestId r1 form ONE agent turn.  If the
# grouping is dropped, the scanner opens TWO turns where the oracle names one.
# This test asserts the exact agent-turn count, which reds on the mismatch.

def test_request_id_grouping_merges_assistant_records_into_one_turn():
    """§2: one API call = 1–5 consecutive assistant lines sharing requestId.
    Three assistant records with requestId r1 must form exactly ONE agent
    turn — not three.  This is the assertion injection 1 reds on: if the
    requestId grouping is dropped, the agent-turn open count increases."""
    text = "\n".join([
        _line({"type": "user", "uuid": "u1", "sessionId": "s",
               "timestamp": "T1", "message": {"role": "user", "content": "go"}}),
        _line({"type": "assistant", "uuid": "a1", "sessionId": "s",
               "timestamp": "T2", "requestId": "r1",
               "message": {"role": "assistant", "id": "m1",
                           "content": [{"type": "text", "text": "one"}]}}),
        _line({"type": "assistant", "uuid": "a2", "sessionId": "s",
               "timestamp": "T3", "requestId": "r1",
               "message": {"role": "assistant", "id": "m1",
                           "content": [{"type": "text", "text": "two"}]}}),
        _line({"type": "assistant", "uuid": "a3", "sessionId": "s",
               "timestamp": "T4", "requestId": "r1",
               "message": {"role": "assistant", "id": "m1",
                           "content": [{"type": "text", "text": "three"}]}}),
    ]) + "\n"
    result = scan_complete(text)
    agent_opens = [ev for ev in result.events
                   if ev.node.kind == "turn.agent" and ev.ev == "open"]
    assert len(agent_opens) == 1, (
        f"three assistant records with requestId r1 must form ONE agent "
        f"turn, got {len(agent_opens)} — requestId grouping is broken")


def test_different_request_ids_open_separate_turns():
    """Two assistant records with different requestIds must open two agent
    turns — the inverse discrimination."""
    text = "\n".join([
        _line({"type": "user", "uuid": "u1", "sessionId": "s",
               "timestamp": "T1", "message": {"role": "user", "content": "go"}}),
        _line({"type": "assistant", "uuid": "a1", "sessionId": "s",
               "timestamp": "T2", "requestId": "r1",
               "message": {"role": "assistant", "id": "m1",
                           "content": [{"type": "text", "text": "a"}]}}),
        _line({"type": "user", "uuid": "u2", "sessionId": "s",
               "timestamp": "T3", "message": {"role": "user",
                    "content": [{"type": "tool_result",
                                 "tool_use_id": "x", "content": "",
                                 "is_error": False}]}}),
        _line({"type": "assistant", "uuid": "a2", "sessionId": "s",
               "timestamp": "T4", "requestId": "r2",
               "message": {"role": "assistant", "id": "m2",
                           "content": [{"type": "text", "text": "b"}]}}),
    ]) + "\n"
    result = scan_complete(text)
    agent_opens = [ev for ev in result.events
                   if ev.node.kind == "turn.agent" and ev.ev == "open"]
    assert len(agent_opens) == 2, (
        f"two different requestIds must open two agent turns, "
        f"got {len(agent_opens)}")


# === injection 2: tool result is NOT a major event =========================
#
# Bookmarks are for page boundaries and user-turn starts only (§4).  A
# tool_result is a step, not a major event — counting it as one inflates the
# bookmark set.  This test asserts the exact bookmark count, which reds if a
# tool_result is wrongly bookmarked.

def test_tool_result_is_not_bookmarked():
    """The frozen transcript has exactly one tool_result (line 4) and exactly
    4 bookmarks (2 pages + 2 user turns).  If tool_result were counted as a
    major event, the bookmark denominator would be 5, not 4."""
    result = scan_complete(_FROZEN_TEXT)
    # Precondition: the transcript genuinely contains a tool_result
    tool_result_lines = [
        i for i, raw in enumerate(_FROZEN_LINES, 1)
        if '"tool_result"' in raw
    ]
    assert len(tool_result_lines) == 1, (
        "test depends on exactly one tool_result in the fixture")
    # The bookmark count must NOT include the tool_result
    bm_kinds = [bm.kind for bm in result.bookmarks]
    assert "step.tool" not in bm_kinds, (
        "a tool result must not be bookmarked — it is a step, not a major "
        "event (§4)")
    assert len(result.bookmarks) == 4, (
        f"expected 4 bookmarks (2 pages + 2 user turns), "
        f"got {len(result.bookmarks)} — a tool result was counted as a "
        f"major event")


# === wire serialisation round-trip =========================================

def test_scan_result_events_serialise_to_wire():
    """Every event in the scan result must serialise to the exact wire shape
    {ev, node} with ref.len (not ref.length) — the increment 1 contract."""
    result = scan_complete(_FROZEN_TEXT)
    for ev in result.events:
        wire = ev.to_wire()
        assert set(wire.keys()) == {"ev", "node"}
        node = wire["node"]
        assert "id" in node and "parent" in node and "kind" in node
        if node.get("ref") is not None:
            assert "len" in node["ref"], (
                "wire ref must spell its length field 'len' (inc 1 contract)")
            assert "length" not in node["ref"]
