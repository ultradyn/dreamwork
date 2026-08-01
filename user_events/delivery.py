"""The delivery CLASS of a receipt — EXPEDITED and how it is recognised (#864).

``delivery-modes.md`` rules two classes: PRE-EMPT (a wake line interrupts at
POST) and BATCHED (the tick's ``pending``/``consume`` drain).  #864 adds a third
between them — EXPEDITED: never interrupts, delivered at the agent's next
natural pause by the stop hook, and **still drained normally** if that hook
never fires.

WHERE THE FLAG LIVES, and why it is not a column.  The journal is
receipt-authority-only: ``exact_payload_bytes`` are the bytes the human sent,
hash-chained, and nothing is ever written back onto them.  A mutable
``expedited`` field on a receipt (or a sidecar table keyed by receipt id) would
be a second durable truth about that receipt — the #263 anti-pattern this design
already refused once for the cursor.  So the class is a **predicate over
(route, payload)**, computed where it is needed and stored nowhere.  It is
retroactive (a ``do next`` already in the journal is expedited the moment the
class exists) and it cannot drift from the payload, because it reads it.

ONE HOME, TWO IMPORTERS.  ``watch.py`` needs it at the wake gate (an expedited
kind must NOT pre-empt); ``dev/journal_consume.py`` needs it at the drain (they
take the cap's slots first).  A second copy of ``EXPEDITE_KINDS`` in either file
is exactly the drift this module exists to prevent, so neither defines one.
"""
from __future__ import annotations

import json

# The dashboard command kinds that are EXPEDITED.  `do-next` is the one he
# named ("this flag would be put on 'do next' command submissions, for
# example"); the tuple is the extension point for the "among others" half.
# It is a tuple of the SAME strings `watch.PREEMPT_KINDS` matches on — the kind
# a `/command` body already carries — so no new journal surface is added.
EXPEDITE_KINDS = ("do-next",)

# Only the command route carries a `kind`; every other write route is
# classified by its route alone and none of them is expedited today.
COMMAND_ROUTE = "/command"


def command_kind(route: str, payload: bytes) -> str | None:
    """The ``kind`` a ``/command`` receipt carries, or None.

    None for a different route, an undecodable body, a non-JSON body, a
    non-object body, or a missing/non-string ``kind``.  Every one of those is a
    receipt whose class cannot be established from its payload, and the safe
    reading of "cannot establish" is "not expedited" — an unclassifiable
    receipt then rides the ordinary drain, which is the fallback that loses
    nothing.  It must never raise: this runs on a stop hook and on the drain,
    and a classifier that throws on one odd payload would take the whole
    delivery with it.
    """
    if route != COMMAND_ROUTE:
        return None
    try:
        body = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(body, dict):
        return None
    kind = body.get("kind")
    return kind if isinstance(kind, str) else None


def is_expedited(route: str, payload: bytes) -> bool:
    """True iff this receipt is of an EXPEDITED kind."""
    return command_kind(route, payload) in EXPEDITE_KINDS
