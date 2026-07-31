"""Closed, serialisable vocabulary for the live session-log tree.

Adapters may understand different transcript grammars, but their output must
cross this boundary before a route or component can consume it.  Optional
fields are omitted from the wire form rather than emitted as JSON null, so a
consumer can distinguish "not measured" from a measured zero.
"""

from dataclasses import dataclass


NODE_KINDS = frozenset({
    "session",
    "page",
    "turn.user",
    "turn.agent",
    "step.tool",
    "step.thinking",
    "step.text",
    "sys.compact",
    "sys.note",
})
NODE_STATES = frozenset({"live", "done", "error"})
EVENT_TYPES = frozenset({"open", "update", "close"})


class ModelError(ValueError):
    """A value cannot be represented by the standardised session model."""


def _non_empty(value, field):
    if not isinstance(value, str) or not value:
        raise ModelError(f"{field} must be a non-empty string")


@dataclass(frozen=True)
class SourceRef:
    """The exact source-record range backing a lazily fetched node body."""

    line: int
    byte: int
    length: int

    def __post_init__(self):
        if not isinstance(self.line, int) or self.line < 1:
            raise ModelError("ref.line must be an integer >= 1")
        if not isinstance(self.byte, int) or self.byte < 0:
            raise ModelError("ref.byte must be an integer >= 0")
        if not isinstance(self.length, int) or self.length < 1:
            raise ModelError("ref.len must be an integer >= 1")

    def to_wire(self):
        return {"line": self.line, "byte": self.byte, "len": self.length}


@dataclass(frozen=True)
class SessionNode:
    """One thin row in the standardised hierarchy."""

    id: str
    parent: str | None
    kind: str
    seq: int
    ts: str | None
    label: str
    state: str
    n_children: int | None = None
    ref: SourceRef | None = None

    def __post_init__(self):
        _non_empty(self.id, "node.id")
        if self.parent is not None:
            _non_empty(self.parent, "node.parent")
        if self.kind not in NODE_KINDS:
            raise ModelError(f"unknown node kind: {self.kind!r}")
        if not isinstance(self.seq, int) or self.seq < 0:
            raise ModelError("node.seq must be an integer >= 0")
        if self.ts is not None and not isinstance(self.ts, str):
            raise ModelError("node.ts must be a string or None")
        if not isinstance(self.label, str):
            raise ModelError("node.label must be a string")
        if self.state not in NODE_STATES:
            raise ModelError(f"unknown node state: {self.state!r}")
        if (self.n_children is not None and
                (not isinstance(self.n_children, int) or self.n_children < 0)):
            raise ModelError("node.n_children must be an integer >= 0 or None")
        if self.ref is not None and not isinstance(self.ref, SourceRef):
            raise ModelError("node.ref must be a SourceRef or None")

    def to_wire(self):
        out = {
            "id": self.id,
            "parent": self.parent,
            "kind": self.kind,
            "seq": self.seq,
            "ts": self.ts,
            "label": self.label,
            "state": self.state,
        }
        if self.n_children is not None:
            out["n_children"] = self.n_children
        if self.ref is not None:
            out["ref"] = self.ref.to_wire()
        return out


@dataclass(frozen=True)
class SessionEvent:
    """One idempotently applicable change to the tree."""

    ev: str
    node: SessionNode

    def __post_init__(self):
        if self.ev not in EVENT_TYPES:
            raise ModelError(f"unknown event type: {self.ev!r}")
        if not isinstance(self.node, SessionNode):
            raise ModelError("event.node must be a SessionNode")

    def to_wire(self):
        return {"ev": self.ev, "node": self.node.to_wire()}
