"""Exact grammar-table proof for the Claude Code record classifier (#631 inc 2).

Every §2 grammar row is exercised by a hand-authored fixture (no real session
content is copied into the repo).  The two named injections are isolated tests
with their discriminating assertions called out in the assertion messages.
"""

import pytest

from session_log.claude_code import (
    NODE,
    SUPPRESSED,
    UNCLASSIFIABLE,
    Classification,
    ToolFacts,
    classify_record,
)
from session_log.model import SourceRef

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
