"""Standardised session-log nodes and events.

The package is deliberately dark until the transcript adapters land.  Its
public values are the one wire contract shared by scanners, routes and the
native component.
"""

from .model import (
    EVENT_TYPES,
    NODE_KINDS,
    NODE_STATES,
    ModelError,
    SessionEvent,
    SessionNode,
    SourceRef,
)

__all__ = [
    "EVENT_TYPES",
    "NODE_KINDS",
    "NODE_STATES",
    "ModelError",
    "SessionEvent",
    "SessionNode",
    "SourceRef",
]
