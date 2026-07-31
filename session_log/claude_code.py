"""Pure classifier for one complete Claude Code JSONL record (#631 increment 2).

Maps a single parsed transcript record onto the standardised node vocabulary
(:mod:`session_log.model`) **without building a tree**: one record in, one
classification out.  Parentage, stable ids, bookmarks and incremental state are
later increments; this layer decides *which grammar row* (§2 of the design) a
record is and pulls the facts a downstream scanner needs.

Three outcomes, deliberately distinct so "suppressed by design" never reads
identically to "unclassifiable" (``#136``):

  - ``NODE``           the record is content and maps to a known grammar row;
  - ``SUPPRESSED``     the record is non-content chrome, hidden by design (§3);
  - ``UNCLASSIFIABLE`` the record looks like content but matches no row —
                       reported, never dropped (``#702``).

The grammar rows this classifier covers (§2 table, measured against a real
81.9 MB / 31 784-line session):

  ===========  =========================  =============  ==================
  type         discriminator              node kind      grammar row
  ===========  =========================  =============  ==================
  user         content str/text blocks    ``turn.user``  user-turn start
  user         content tool_result block  ``step.tool``  tool result (half)
  user         isCompactSummary           ``sys.compact`` compaction summary
  user         isMeta                     ``sys.note``   meta / skill preamble
  assistant    block type text            ``step.text``  assistant text
  assistant    block type tool_use        ``step.tool``  tool use (half)
  assistant    block type thinking        ``step.thinking`` assistant thinking
  system       subtype compact_boundary   ``page``       compaction page boundary
  system       subtype stop_hook_summary  ``sys.note``   turn annotation
  system       subtype turn_duration      ``sys.note``   turn annotation
  system       subtype away_summary       ``sys.note``   away recap
  *other*      any non-content type       —              suppressed chrome
  ===========  =========================  =============  ==================
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import NODE_KINDS, SourceRef

# --- outcome discriminators -------------------------------------------------
#
# "suppressed" and "unclassifiable" must never render identically (#136):
# suppressed is non-content chrome hidden by design; unclassifiable is content
# the classifier could not place and must report (#702).
NODE = "node"
SUPPRESSED = "suppressed"
UNCLASSIFIABLE = "unclassifiable"

# The only top-level record types that carry conversational content.  Every
# other type is chrome and is suppressed by design (§2/§3).
_CONTENT_TYPES = frozenset({"user", "assistant", "system"})

# System subtypes that carry visible annotations → sys.note (§2).
_SYS_NOTE_SUBTYPES = frozenset({
    "stop_hook_summary",
    "turn_duration",
    "away_summary",
})


@dataclass(frozen=True)
class ToolFacts:
    """Native tool facts extracted from a ``tool_use`` or ``tool_result``.

    A tool step pairs a ``tool_use`` (assistant half) with its ``tool_result``
    (user half) by ``tool_use_id``; increment 3 does the pairing.  This layer
    extracts the facts either half carries so the scanner never re-parses the
    record.
    """

    name: str | None = None
    """Tool name (``Bash``, ``Edit``, ``Read``, …) — present on the use half."""

    tool_use_id: str | None = None
    """The ``id`` (use half) or ``tool_use_id`` (result half) that pairs them."""

    is_error: bool = False
    """``tool_result.is_error`` — derives the ``error`` node state."""

    is_result: bool = False
    """True on the result half, False on the use half."""


@dataclass(frozen=True)
class Classification:
    """Result of classifying one complete JSONL record.

    ``outcome`` discriminates the three cases.  For ``NODE``, ``kind`` is a
    standardised node kind from the closed vocabulary; for ``SUPPRESSED`` and
    ``UNCLASSIFIABLE`` it is ``None`` and ``reason`` explains the decision.
    """

    outcome: str
    kind: str | None
    ts: str | None
    ref: SourceRef
    reason: str
    uuid: str | None = None
    tool: ToolFacts | None = None

    def __post_init__(self):
        if self.outcome == NODE:
            if self.kind not in NODE_KINDS:
                raise ValueError(
                    f"classifier produced an unknown node kind: {self.kind!r}")
        elif self.kind is not None:
            raise ValueError(
                f"non-NODE outcome must not carry a kind, got {self.kind!r}")


def classify_record(record, *, line, byte, length):
    """Classify one complete parsed JSONL record.

    Parameters
    ----------
    record : dict
        The parsed JSON object from one transcript line.
    line, byte, length : int
        The record's position in the source file (1-based line, 0-based byte
        offset, byte length of the raw record text).  The caller — the scanner
        in increment 3/4 — owns these because they are file-position facts,
        not facts of the record itself.

    Returns
    -------
    Classification
        With ``outcome`` set to ``NODE``, ``SUPPRESSED``, or
        ``UNCLASSIFIABLE``.
    """
    ref = SourceRef(line=line, byte=byte, length=length)
    rtype = record.get("type")
    ts = record.get("timestamp")
    uuid = record.get("uuid")

    # Non-content records are chrome: suppressed by design (§2/§3).  This
    # covers known chrome (mode, last-prompt, file-history-*, …) AND unknown
    # non-content types — both are non-content, both hidden.
    if rtype not in _CONTENT_TYPES:
        label = repr(rtype) if rtype is not None else "no type field"
        return Classification(SUPPRESSED, None, ts, ref,
                              f"chrome: {label}", uuid)

    if rtype == "user":
        return _classify_user(record, ref, ts, uuid)
    if rtype == "assistant":
        return _classify_assistant(record, ref, ts, uuid)
    return _classify_system(record, ref, ts, uuid)


# --- per-type dispatch ------------------------------------------------------

def _classify_user(record, ref, ts, uuid):
    message = record.get("message")
    if not isinstance(message, dict):
        return Classification(UNCLASSIFIABLE, None, ts, ref,
                              "user record has no message object", uuid)
    content = message.get("content")

    # isCompactSummary and isMeta take priority over content-shape checks
    # because their content can look like a plain string or text blocks.
    if record.get("isCompactSummary"):
        return Classification(NODE, "sys.compact", ts, ref,
                              "compaction summary", uuid)
    if record.get("isMeta"):
        return Classification(NODE, "sys.note", ts, ref,
                              "meta user record", uuid)

    if _is_tool_result(content):
        block = content[0]
        return Classification(
            NODE, "step.tool", ts, ref, "tool result", uuid,
            ToolFacts(
                tool_use_id=block.get("tool_use_id"),
                is_error=bool(block.get("is_error")),
                is_result=True,
            ),
        )
    if _is_text_content(content):
        return Classification(NODE, "turn.user", ts, ref,
                              "user turn start", uuid)
    return Classification(UNCLASSIFIABLE, None, ts, ref,
                          f"user content not recognised: "
                          f"{_describe_content(content)}", uuid)


def _classify_assistant(record, ref, ts, uuid):
    message = record.get("message")
    if not isinstance(message, dict):
        return Classification(UNCLASSIFIABLE, None, ts, ref,
                              "assistant record has no message object", uuid)
    content = message.get("content")
    if not isinstance(content, list) or len(content) == 0:
        return Classification(UNCLASSIFIABLE, None, ts, ref,
                              "assistant record has no content blocks", uuid)
    block = content[0]
    if not isinstance(block, dict):
        return Classification(UNCLASSIFIABLE, None, ts, ref,
                              "assistant content block is not an object", uuid)
    btype = block.get("type")
    if btype == "text":
        return Classification(NODE, "step.text", ts, ref,
                              "assistant text", uuid)
    if btype == "thinking":
        return Classification(NODE, "step.thinking", ts, ref,
                              "assistant thinking", uuid)
    if btype == "tool_use":
        return Classification(
            NODE, "step.tool", ts, ref, "tool use", uuid,
            ToolFacts(
                name=block.get("name"),
                tool_use_id=block.get("id"),
                is_result=False,
            ),
        )
    return Classification(UNCLASSIFIABLE, None, ts, ref,
                          f"assistant block type not recognised: "
                          f"{btype!r}", uuid)


def _classify_system(record, ref, ts, uuid):
    subtype = record.get("subtype")
    if subtype == "compact_boundary":
        return Classification(NODE, "page", ts, ref,
                              "compaction page boundary", uuid)
    if subtype in _SYS_NOTE_SUBTYPES:
        return Classification(NODE, "sys.note", ts, ref,
                              f"system note: {subtype}", uuid)
    return Classification(UNCLASSIFIABLE, None, ts, ref,
                          f"system subtype not recognised: "
                          f"{subtype!r}", uuid)


# --- content-shape predicates -----------------------------------------------

def _is_tool_result(content):
    """True when *content* is a list whose first block is a tool_result."""
    return (isinstance(content, list) and len(content) > 0
            and isinstance(content[0], dict)
            and content[0].get("type") == "tool_result")


def _is_text_content(content):
    """True for a plain string or a list of text blocks (a user message)."""
    if isinstance(content, str):
        return True
    if isinstance(content, list) and len(content) > 0:
        return all(isinstance(b, dict) and b.get("type") == "text"
                   for b in content)
    return False


def _describe_content(content):
    """A short human-readable label for an unrecognised content value."""
    if content is None:
        return "None"
    if isinstance(content, str):
        return f"string ({len(content)} chars)"
    if isinstance(content, list):
        if len(content) == 0:
            return "empty list"
        first = content[0]
        if isinstance(first, dict):
            return f"list[{len(content)}] first block type={first.get('type')!r}"
        return f"list[{len(content)}] first={type(first).__name__}"
    return type(content).__name__
