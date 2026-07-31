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

import json
from dataclasses import dataclass, replace

from .model import NODE_KINDS, SessionEvent, SessionNode, SourceRef

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


# === increment 3: full hierarchy scan =======================================

@dataclass(frozen=True)
class Bookmark:
    """A major-event bookmark: page boundary or user-turn start (§4).

    Only page boundaries and user-turn starts are bookmarked (§4: ~433 rows
    for the measured 4-day session = 405 user turns + 28 boundaries).  Agent
    turns, steps and notes are not major events — counting a tool result as
    one is injection 2 in the proof.
    """

    seq: int
    kind: str          # 'page' | 'turn.user'
    line: int
    byte: int
    ts: str | None
    label: str
    node_id: str


@dataclass(frozen=True)
class Diagnostic:
    """An unclassifiable record, reported not dropped (#702).

    Distinct from a suppressed record (chrome, silent by design #755):
    unclassifiable looks like content but matches no grammar row, so the
    scan must carry it forward for a human to see.
    """

    line: int
    byte: int
    reason: str


@dataclass(frozen=True)
class Frontier:
    """Resumable scan state — enough to continue a tree without duplicating a
    node (#631 increment 4).

    Carries the byte/line cursor plus the session/page/turn/tool-pairing
    frontier and the monotonic counters, so a resumed scan emits nodes that
    CONTINUE the tree (continuing ``seq`` numbering, reusing the open
    session and page, keeping an unpaired ``tool_use`` live) rather than
    restart it.  Produced by every scan; consumed only by
    :func:`scan_incremental` — the one supported way to resume (#440: a
    second unanchored form is the corruption vector).

    The empty frontier (``empty_frontier``) is the scan that examined
    nothing (#671): its counters are zero and its ids are ``None``, which is
    distinct from a real frontier whose counters are positive (#136).
    """

    byte: int
    line: int
    examined: int
    seq: int
    bm: int
    sid: str | None
    page_id: str | None
    page_n: int
    agent_id: str | None
    agent_seq: int
    agent_rid: str | None
    open_tools: tuple    # tuple of (tool_use_id, SessionNode) pairs


def empty_frontier():
    """The from-zero frontier: no records examined, no tree open (#671).

    A scan started here is equivalent to :func:`scan_complete` over the same
    text — the test exercises both through the same parser.
    """
    return Frontier(byte=0, line=1, examined=0, seq=0, bm=0,
                    sid=None, page_id=None, page_n=-1,
                    agent_id=None, agent_seq=0, agent_rid=None,
                    open_tools=())


@dataclass(frozen=True)
class ScanResult:
    """Scan output (#631 increments 3–4).

    ``examined`` counts every non-empty newline-terminated line parsed
    (#671): zero for an empty transcript, N for an all-chrome transcript
    with no events, and N for a real one — so an empty scan never reads as
    a confident pass.  ``frontier`` is the resumable state to feed
    :func:`scan_incremental`.
    """

    events: tuple      # tuple[SessionEvent, ...]
    bookmarks: tuple   # tuple[Bookmark, ...]
    diagnostics: tuple # tuple[Diagnostic, ...]
    examined: int
    frontier: Frontier


def scan_complete(text):
    """Scan a Claude Code JSONL transcript from zero (#631 increment 3).

    Composes classified records into one session/page/turn/step tree, pairs
    ``tool_use`` with ``tool_result`` by ``tool_use_id``, emits
    ``open``/``update``/``close`` events, and produces bookmarks for page
    boundaries and user-turn starts only.

    Only newline-terminated records are consumed; an unterminated trailing
    line (a writer mid-append) is left before the cursor (#631 increment 4).
    The returned ``frontier`` carries enough state to resume without
    duplicating a node.

    Parameters
    ----------
    text : str
        The complete JSONL file content (one JSON object per line).

    Returns
    -------
    ScanResult
        ``examined`` is the count of non-empty newline-terminated lines
        parsed, so an empty transcript (``examined == 0``) is never confused
        with a successful scan of real content (#671).
    """
    st = _ScanState()
    new_byte, new_line, examined = _scan_records(text, 0, 1, st)
    return ScanResult(
        events=tuple(st.events),
        bookmarks=tuple(st.bookmarks),
        diagnostics=tuple(st.diagnostics),
        examined=examined,
        frontier=st.to_frontier(new_byte, new_line, examined),
    )


def scan_incremental(text, frontier):
    """Resume a scan from ``frontier.byte``, carrying frontier state.

    The single supported way to resume (#440): consumes only
    newline-terminated records starting at ``frontier.byte`` and leaves the
    cursor before any unterminated tail.  Carried frontier — the open
    session/page, the current agent turn, unpaired ``tool_use`` steps and
    the monotonic counters — lets the resume CONTINUE the tree rather than
    restart it, so a concatenated scan equals the one-shot scan over the
    whole text and never duplicates a node.

    Bytes before ``frontier.byte`` are never read: a resume is not a
    re-scan.  The carried counters continue (``seq``/``bm`` do not reset),
    and an already-open session/page is not re-opened.

    Parameters
    ----------
    text : str
        The full JSONL file content (the prefix before ``frontier.byte`` is
        never examined).
    frontier : Frontier
        Resumable state from a prior :func:`scan_complete` /
        :func:`scan_incremental`.

    Returns
    -------
    ScanResult
        Events/bookmarks/diagnostics for the NEW records only, with
        ``examined`` continued from ``frontier.examined`` and a new
        ``frontier`` for the next resume.
    """
    st = _ScanState(frontier)
    new_byte, new_line, delta = _scan_records(
        text, frontier.byte, frontier.line, st)
    examined = frontier.examined + delta
    return ScanResult(
        events=tuple(st.events),
        bookmarks=tuple(st.bookmarks),
        diagnostics=tuple(st.diagnostics),
        examined=examined,
        frontier=st.to_frontier(new_byte, new_line, examined),
    )


# --- internal helpers -------------------------------------------------------

def _scan_records(text, start_byte, start_line, st):
    """Consume newline-terminated records from ``start_byte`` into ``st``.

    Stops before an unterminated trailing line (a partial write): the cursor
    advances to just past the last consumed ``\\n`` and never into the
    partial tail.  Returns ``(new_byte, new_line, examined)`` where
    ``examined`` is the count of non-empty lines parsed this call (#671).

    Line/byte/length positions are pure string arithmetic over the raw text,
    independent of the classifier — the same discipline as the test's
    ``_byte_offsets`` oracle.
    """
    pos = start_byte
    line_no = start_line
    examined = 0
    while True:
        nl = text.find("\n", pos)
        if nl == -1:
            break                      # unterminated tail: cursor stays before it
        raw = text[pos:nl]
        rec_len = len(raw)
        if raw.strip():
            examined += 1              # counted before parse: unparseable still examined
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                pos = nl + 1
                line_no += 1
                continue
            if isinstance(record, dict):
                _process_record(st, record, line_no, pos, rec_len)
        pos = nl + 1
        line_no += 1
    return pos, line_no, examined


def _process_record(st, record, line, byte, length):
    """Classify one complete record and fold it into the tree state ``st``.

    The body of the scan loop, shared by :func:`scan_complete` and
    :func:`scan_incremental` so both exercise the same parser.  Carried
    frontier (seeded into ``st``) is what makes a resume continue rather
    than restart: the ``st.sid is None`` guard re-opens session/page 0 only
    on the first content record of a from-zero scan.
    """
    cls = classify_record(record, line=line, byte=byte, length=length)

    if cls.outcome == SUPPRESSED:
        return                          # #755: silent on healthy input
    if cls.outcome == UNCLASSIFIABLE:
        st.diagnostics.append(          # #702: reported, not dropped
            Diagnostic(line=line, byte=byte, reason=cls.reason))
        return

    # --- lazy session + page 0 on first content record ---
    if st.sid is None:
        session_id = record.get("sessionId") or "sess"
        st.sid = f"sess:{session_id}"
        st.emit("open", SessionNode(
            id=st.sid, parent=None, kind="session",
            seq=st.next_seq(), ts=cls.ts,
            label=f"session {session_id}", state="live",
        ))
        st.page_n = 0
        st.page_id = f"{st.sid}/pg:0"
        st.emit("open", SessionNode(
            id=st.page_id, parent=st.sid, kind="page",
            seq=st.next_seq(), ts=cls.ts, label="page 0",
            state="live", ref=cls.ref,
        ))
        st.add_bookmark("page", line, byte, cls.ts, "page 0", st.page_id)

    kind = cls.kind

    if kind == "page":
        # compact_boundary → close agent turn, open new page
        st.close_agent(cls.ts)
        st.page_n += 1
        st.page_id = f"{st.sid}/pg:{st.page_n}"
        st.emit("open", SessionNode(
            id=st.page_id, parent=st.sid, kind="page",
            seq=st.next_seq(), ts=cls.ts,
            label=f"page {st.page_n}", state="live", ref=cls.ref,
        ))
        st.add_bookmark("page", line, byte, cls.ts,
                        f"page {st.page_n}", st.page_id)

    elif kind == "turn.user":
        st.close_agent(cls.ts)
        uid = cls.uuid or f"s{st.seq + 1}"
        turn_id = f"{st.page_id}/u:{uid}"
        st.emit("open", SessionNode(
            id=turn_id, parent=st.page_id, kind="turn.user",
            seq=st.next_seq(), ts=cls.ts, label="user turn",
            state="done", ref=cls.ref,
        ))
        st.add_bookmark("turn.user", line, byte, cls.ts,
                        "user turn", turn_id)

    elif kind in ("step.text", "step.thinking"):
        st.ensure_agent(record, cls)
        step_id = f"{st.agent_id}/{cls.uuid or st.seq + 1}"
        st.emit("open", SessionNode(
            id=step_id, parent=st.agent_id, kind=kind,
            seq=st.next_seq(), ts=cls.ts,
            label=kind.split(".")[1], state="done", ref=cls.ref,
        ))

    elif kind == "step.tool":
        if cls.tool and cls.tool.is_result:
            st.handle_tool_result(cls)
        else:
            st.ensure_agent(record, cls)
            label = (cls.tool.name if cls.tool and cls.tool.name
                     else "tool")
            step_uuid = cls.uuid or f"s{st.seq + 1}"
            step_id = f"{st.agent_id}/{step_uuid}"
            node = SessionNode(
                id=step_id, parent=st.agent_id, kind="step.tool",
                seq=st.next_seq(), ts=cls.ts, label=label,
                state="live", ref=cls.ref,
            )
            st.emit("open", node)
            if cls.tool and cls.tool.tool_use_id:
                st.open_tools[cls.tool.tool_use_id] = node

    elif kind in ("sys.compact", "sys.note"):
        short = "c" if kind == "sys.compact" else "n"
        suuid = cls.uuid or f"s{st.seq + 1}"
        node_id = f"{st.page_id}/{short}:{suuid}"
        label = ("compaction summary" if kind == "sys.compact"
                 else "system note")
        st.emit("open", SessionNode(
            id=node_id, parent=st.page_id, kind=kind,
            seq=st.next_seq(), ts=cls.ts, label=label,
            state="done", ref=cls.ref,
        ))

class _ScanState:
    """Mutable tree-builder state for one scan (#631 increments 3–4).

    Encapsulates the session/page/turn/tool-pairing state so the scan loop
    reads as a flat dispatch on classification outcome.  All node identity
    and event emission flows through here, which is what makes the wire
    stream deterministic and testable against a hand-authored oracle.

    For an incremental resume, ``__init__`` seeds the carried frontier so the
    scan continues the tree (open session/page reused, counters continued,
    unpaired ``tool_use`` kept live) instead of restarting it.
    """

    def __init__(self, frontier=None):
        self.events: list[SessionEvent] = []
        self.bookmarks: list[Bookmark] = []
        self.diagnostics: list[Diagnostic] = []
        f = frontier
        self.seq = f.seq if f else 0        # monotonic node sequence
        self.bm = f.bm if f else 0          # monotonic bookmark sequence

        self.sid: str | None = f.sid if f else None         # "sess:<id>"
        self.page_id: str | None = f.page_id if f else None
        self.page_n = f.page_n if f else -1

        self.agent_id: str | None = f.agent_id if f else None
        self.agent_seq = f.agent_seq if f else 0
        self.agent_rid: str | None = f.agent_rid if f else None

        self.open_tools: dict[str, SessionNode] = (
            dict(f.open_tools) if f else {})  # tool_use_id → step

    def to_frontier(self, byte, line, examined):
        """Snapshot the resumable state at the cursor ``(byte, line)``."""
        return Frontier(
            byte=byte, line=line, examined=examined,
            seq=self.seq, bm=self.bm,
            sid=self.sid, page_id=self.page_id, page_n=self.page_n,
            agent_id=self.agent_id, agent_seq=self.agent_seq,
            agent_rid=self.agent_rid,
            open_tools=tuple(self.open_tools.items()),
        )

    def next_seq(self):
        self.seq += 1
        return self.seq

    def emit(self, ev, node):
        self.events.append(SessionEvent(ev, node))

    def add_bookmark(self, kind, line, byte, ts, label, node_id):
        self.bm += 1
        self.bookmarks.append(Bookmark(
            seq=self.bm, kind=kind, line=line, byte=byte,
            ts=ts, label=label, node_id=node_id,
        ))

    def close_agent(self, ts):
        """Close the current agent turn (state → done), if one is open."""
        if self.agent_id is not None:
            self.emit("close", SessionNode(
                id=self.agent_id, parent=self.page_id,
                kind="turn.agent", seq=self.agent_seq, ts=ts,
                label="agent turn", state="done",
            ))
            self.agent_id = None
            self.agent_rid = None

    def ensure_agent(self, record, cls):
        """Open a new agent turn when requestId changes or none is open (§2).

        One API call = 1–5 consecutive assistant lines sharing
        ``requestId``/``message.id``; they form one agent turn.  Dropping
        this grouping is injection 1 in the proof: two records with the
        same ``requestId`` would wrongly open two turns.
        """
        rid = _request_id(record)
        if (self.agent_id is None or rid is None
                or rid != self.agent_rid):
            self.close_agent(cls.ts)
            self.agent_rid = rid
            self.agent_seq = self.next_seq()
            self.agent_id = f"{self.page_id}/a:{rid or self.agent_seq}"
            self.emit("open", SessionNode(
                id=self.agent_id, parent=self.page_id,
                kind="turn.agent", seq=self.agent_seq, ts=cls.ts,
                label="agent turn", state="live", ref=cls.ref,
            ))

    def handle_tool_result(self, cls):
        """Pair a ``tool_result`` with its open ``tool_use``, or emit orphan.

        Three distinct outcomes that must not render identically (#136):
        paired (open + update), still-open (open, no update), and orphaned
        (open with state already done/error, no preceding use).
        """
        tid = cls.tool.tool_use_id if cls.tool else None
        if tid and tid in self.open_tools:
            original = self.open_tools.pop(tid)
            state = "error" if (cls.tool and cls.tool.is_error) else "done"
            self.emit("update", replace(original, state=state, ts=cls.ts))
        else:
            parent = self.agent_id or self.page_id
            oid = cls.uuid or f"s{self.seq + 1}"
            orphan_id = f"{parent}/orphan:{oid}"
            state = "error" if (cls.tool and cls.tool.is_error) else "done"
            self.emit("open", SessionNode(
                id=orphan_id, parent=parent, kind="step.tool",
                seq=self.next_seq(), ts=cls.ts,
                label="orphaned tool result", state=state, ref=cls.ref,
            ))


def _request_id(record):
    """Extract the API-call grouping key from an assistant record (§2)."""
    rid = record.get("requestId")
    if rid:
        return rid
    message = record.get("message")
    if isinstance(message, dict):
        return message.get("id")
    return None
