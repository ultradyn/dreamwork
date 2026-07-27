"""Application layer for the user-event journal (lane D, increments 16-19).

This is where "exactly once" is actually won or lost. A receipt is applied to a
managed domain file; the question this module answers is *whether an effect
already happened*, and it answers it **ternary**:

    Proof.APPLIED      the effect is provably present in a valid known file
    Proof.NOT_APPLIED  the effect is provably absent from a valid known file
    Proof.UNKNOWN      the file is torn, drifted, or forged — neither verdict
                       is safe, so the safer one (quarantine) is taken

``Unknown`` is the third path that a boolean proof does not have, and it is the
whole of laws 2/7/8 of the design's Crash-safe ApplicationAdapter: a torn or
drifted file must never be read as ``NotApplied`` (which would re-apply and
duplicate the effect) nor silently as ``Applied`` (which would drop it).

Design: ``user-event-journal.md`` §"Crash-safe ApplicationAdapter" and the
post-crash proof table. Plan: ``user-event-journal-implementation.md`` §"Lane D".
This module is new files only; it consumes ``user_events.domain_files`` (lane C)
and is consumed in turn by lane E's HTTP cutover, which is behind a second gate
and not wired here.

Filename note: the design's §"Modules and ownership" names this
``user_events/application.py``; the lane-D brief and its test file name it
``apply.py``, and the brief's acceptance criterion 1 lists ``user_events/apply.py``
first. The brief is the operative document for this lane, so this is ``apply.py``.
"""

from __future__ import annotations

import enum
import os
from typing import Callable, Collection, Optional

from user_events import domain_files

# ---------------------------------------------------------------------------
# Last-application identity — the ``last_applied`` footer field's lane-D shape.
#
# The footer's ``last_applied`` is a free-form string (lane C parses it raw).
# Lane D fixes its shape as three pipe-separated parts so the proof can compare
# each independently:
#
#     <receipt_id>|<adapter>|<application_ref>
#
# Receipt id, adapter and application reference are the three things law 4 says
# a reserved-successor file must "exactly match started intent" — kept as one
# durable field but split for the four-predicate comparison (increment 17).
# ---------------------------------------------------------------------------

_ID_SEP = "|"


def make_identity(receipt_id: str, adapter: str, application_ref: str) -> str:
    """Assemble the ``last_applied`` identity from its three parts."""
    return _ID_SEP.join((receipt_id, adapter, application_ref))


def parse_identity(last_applied: str) -> tuple[str, str, str]:
    """Split a ``last_applied`` identity into (receipt_id, adapter, app_ref).

    Tolerant of fewer parts (an externally-edited file may carry a shorter
    form); the proof reads a missing part as empty, which never matches a real
    receipt's part, so a partial identity still proves ``Unknown``.
    """
    parts = (last_applied or "").split(_ID_SEP)
    while len(parts) < 3:
        parts.append("")
    return parts[0], parts[1], parts[2]


def _body_of(text: str) -> str:
    """The human-visible body: ``text`` with its managed footer removed.

    ``domain_files.build_managed_text`` joins ``body + "\\n" + footer``, so the
    body is everything before the trailing footer block. Used by adapters that
    append an effect to the current body (increment 18/19).
    """
    idx = text.rfind("\n<!-- dreamwork-managed v1")
    if idx == -1:
        # No footer separator newline; maybe the footer is the whole text or
        # absent. Strip a trailing footer that starts the file too.
        idx = text.rfind("<!-- dreamwork-managed v1")
        return text[:idx].rstrip("\n") if idx != -1 else text.rstrip("\n")
    return text[:idx]


# ---------------------------------------------------------------------------
# Increment 16 (D1) — ternary proof.
# ---------------------------------------------------------------------------


class Proof(enum.Enum):
    """Ternary application proof (design law 8). ``Unknown`` is a third path,
    never boolean false."""

    APPLIED = "applied"
    NOT_APPLIED = "not_applied"
    UNKNOWN = "unknown"


def successor_matches(
    text: str,
    md: dict,
    *,
    reserved_successor: int,
    receipt_id: str,
    adapter: str,
    application_ref: str,
) -> bool:
    """Law 4: a file proves the reserved successor only when ALL FOUR match.

    The four predicates of the reserved-successor comparison are spread across
    this function and its caller so each is a single line in exactly one place
    (the increment-17 red deletes one and watches exactly its sub-case flip;
    a predicate checked twice is a hollow red — deleting one copy changes
    nothing):

      (1) generation == reserved_successor   — here, term 1
      (2) body digest validates              — in ``_is_valid_known_file``
          (the ``if not validate(text): return False`` line), because it is a
          property of EVERY valid file, committed-lineage or successor, not
          just the successor path
      (3) receipt id matches                 — here, term 2
      (4) adapter/application reference      — here, terms 3 and 4

    ``md`` is the file's parsed metadata. The caller guarantees the body digest
    already validated before calling, so this function does not re-check it.
    """
    ri, ad, ar = parse_identity(md["last_applied"])
    return (
        md["domain_generation"] == reserved_successor       # (1) generation
        and ri == receipt_id                                # (3) receipt id
        and ad == adapter
        and ar == application_ref                           # (4) adapter/app-ref
    )


def _is_valid_known_file(
    text: str,
    md: Optional[dict],
    *,
    reserved_successor: Optional[int],
    committed_lineage: Collection[int],
    receipt_id: str,
    adapter: str,
    application_ref: str,
) -> bool:
    """True iff ``text`` is a valid managed file in committed lineage or the
    exact reserved successor matching started intent.

    False (which ``prove_applied`` reads as ``Unknown``) for a torn file, a
    digest mismatch, or a generation outside committed lineage that is not the
    reserved successor — laws 2, 7 and 8. This is the single guard whose
    deletion is increment 16's discriminating red.
    """
    if md is None:
        return False
    # (2) body-digest predicate — D2's second red deletes THIS line. It lives
    # here rather than in successor_matches because it is a property of every
    # valid file (committed-lineage or successor); checking it twice would make
    # the successor_matches copy a hollow red.
    if not domain_files.validate(text):
        return False
    gen = md["domain_generation"]
    if gen in committed_lineage:
        return True
    if reserved_successor is None:
        return False
    # gen is not in committed lineage: the only remaining way to be a valid
    # known file is to be the EXACT reserved successor matching started intent.
    # This routes through successor_matches rather than pre-gating on
    # ``gen == reserved_successor`` so that successor_matches's generation term
    # stays LIVE — a pre-gate would make it dead code and the increment-17
    # generation red would come back green (a hollow red).
    return successor_matches(
        text, md,
        reserved_successor=reserved_successor,
        receipt_id=receipt_id, adapter=adapter,
        application_ref=application_ref,
    )


def prove_applied(
    text: str,
    *,
    receipt_id: str,
    adapter: str,
    application_ref: str,
    reserved_successor: Optional[int],
    committed_lineage: Collection[int],
    has_marker: Callable[[str], bool],
) -> Proof:
    """Ternary proof that ``receipt`` was applied to the file ``text``.

    - torn / digest-mismatched / drifted-generation file  → ``UNKNOWN``
    - valid known-lineage or exact reserved successor with the marker → ``APPLIED``
    - valid known-lineage or exact reserved successor without the marker → ``NOT_APPLIED``

    ``has_marker`` is a callable bound to the receipt (and, for adapters, to the
    route) so the proof machinery is independent of any one adapter's marker
    format — that is what lets increments 16/17 prove the machinery before any
    adapter exists (increment 19).
    """
    md = domain_files.parse_metadata(text)
    # --- D1 red line: the single validation guard. Delete this branch and a
    # --- torn or drifted file falls through to the marker search, collapsing
    # --- both to NOT_APPLIED — which is exactly the duplicate-effect bug law 8
    # --- exists to prevent. The third fixture (valid, in-lineage, no marker)
    # --- already reaches NOT_APPLIED through this guard, so it stays put and
    # --- the red is discriminating rather than a suite that moves together.
    if not _is_valid_known_file(
        text, md,
        reserved_successor=reserved_successor,
        committed_lineage=committed_lineage,
        receipt_id=receipt_id, adapter=adapter,
        application_ref=application_ref,
    ):
        return Proof.UNKNOWN
    if has_marker(text):
        return Proof.APPLIED
    return Proof.NOT_APPLIED


# ---------------------------------------------------------------------------
# Increment 18 (D3) — reconciliation after a really-killed process.
#
# The post-crash proof table (design §"Crash-safe ApplicationAdapter"):
#
#   | post-crash state | proof      | action                           |
#   | received/claimed/ | APPLIED    | CAS finish; NO domain write      |
#   | applying          | NOT_APPLIED| one idempotent apply; then finish|
#   | same              | UNKNOWN    | CAS recovering; no mutation      |
#   | applied           | any        | no-op                            |
#
# The load-bearing branch is the first: a file that already proves APPLIED must
# be finished only, never written again. Delete it and the after-fsync case
# (where the crashed write already landed the marker) gets a second effect.
# ---------------------------------------------------------------------------


def _read_locked(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def reconcile(
    path: str,
    *,
    receipt_id: str,
    adapter: str,
    application_ref: str,
    append_effect: Callable[[str], str],
    reserved_successor: int,
    committed_lineage: Collection[int],
    has_marker: Callable[[str], bool],
    finish: Callable[[], None],
) -> Proof:
    """One reconciliation pass: prove, then act per the post-crash table.

    Reads the file under the cross-process lock, proves, and either finishes
    only (APPLIED), writes the effect once then finishes (NOT_APPLIED), or
    surfaces evidence without mutating (UNKNOWN). ``finish`` is the journal CAS
    (lane B's claim/finish); it is a callback here because the proof→write
    decision is what this increment owns and proves, and it is independent of
    the journal's CAS mechanics. ``append_effect`` returns the new human-visible
    body with this adapter's effect appended to the current body.
    """
    with domain_files.DomainFileLock(path):
        text = _read_locked(path)
        proof = prove_applied(
            text,
            receipt_id=receipt_id, adapter=adapter,
            application_ref=application_ref,
            reserved_successor=reserved_successor,
            committed_lineage=committed_lineage,
            has_marker=has_marker,
        )
        # --- D3 red line: a file that already proves APPLIED is finished only.
        # --- Delete this branch and the after-fsync case (marker already on
        # --- disk from the crashed write) gets a second effect appended.
        if proof is Proof.APPLIED:
            finish()
            return proof
        if proof is Proof.UNKNOWN:
            return proof  # recovering; no mutation, surface evidence
        # NOT_APPLIED: append the effect once, durably, then finish. The write
        # composes the store's durable-replace primitive directly under THIS
        # held lock rather than calling domain_files.write (which re-acquires
        # the same sidecar lock via a second file description and self-deadlocks
        # — per flock(2), a process's second open is denied by its first).
        identity = make_identity(receipt_id, adapter, application_ref)
        new_body = append_effect(text)
        new_text = domain_files.build_managed_text(
            new_body, reserved_successor, identity)
        domain_files._atomic_replace(path, new_text)
        finish()
        return proof


# ---------------------------------------------------------------------------
# Increment 19 (D4) — endpoint adapters and the registry.
#
# Each write route has one adapter that knows only its own marker format. A
# marker is route-tagged so an answer marker and a comment marker cannot be
# confused, and the proof's identity check (adapter field) is a second wall: an
# adapter proving a receipt against a file another adapter wrote fails closed.
# ---------------------------------------------------------------------------


def _marker_for(route: str, receipt_id: str) -> str:
    """The structured-margin marker one adapter writes for one receipt."""
    return f"<!-- dreamwork:{route}:{receipt_id} -->"


class ApplicationAdapter:
    """One endpoint's application adapter: its own marker, its own effect.

    ``has_marker`` looks for THIS route's marker only, so an adapter cannot read
    another's payload (law: each adapter sees only its own format). The identity
    check in ``successor_matches`` is the second wall.
    """

    def __init__(self, route: str, effect_line: Optional[Callable[[str, str], str]] = None):
        self.route = route
        # effect_line(receipt_id, body_so_far) -> the line to append; defaults
        # to the bare marker. An adapter may add human-visible prose alongside.
        self._effect_line = effect_line or (lambda rid, body: _marker_for(route, rid))

    def marker(self, receipt_id: str) -> str:
        return _marker_for(self.route, receipt_id)

    def has_marker(self, text: str, receipt_id: str) -> bool:
        return self.marker(receipt_id) in text

    def marker_count(self, text: str, receipt_id: str) -> int:
        return text.count(self.marker(receipt_id))

    def append_effect(self, text: str, receipt_id: str) -> str:
        """Return the new human-visible body with this receipt's effect appended."""
        body = _body_of(text)
        return body + "\n" + self._effect_line(receipt_id, body)

    def prove(
        self, text: str, *, receipt_id: str, application_ref: str,
        reserved_successor: Optional[int], committed_lineage: Collection[int],
    ) -> Proof:
        return prove_applied(
            text,
            receipt_id=receipt_id, adapter=self.route,
            application_ref=application_ref,
            reserved_successor=reserved_successor,
            committed_lineage=committed_lineage,
            has_marker=lambda t: self.has_marker(t, receipt_id),
        )


# The registry. Dispatch is by route; deleting one entry fails exactly that
# route's case (increment 19's red). Built at import so the five write routes
# each have an adapter the moment the module loads.
ADAPTERS: dict[str, ApplicationAdapter] = {}


def register(route: str, adapter: ApplicationAdapter) -> None:
    ADAPTERS[route] = adapter


def adapter_for(route: str) -> ApplicationAdapter:
    """Return the adapter for ``route``, or raise KeyError if none is registered.

    A missing entry is a hard failure rather than a silent fallback, so a
    forgotten registration is caught at the first use rather than misrouting
    effects to a wrong adapter."""
    return ADAPTERS[route]


def _install_default_adapters() -> None:
    for route in ("/answer", "/ask", "/comment", "/command", "/tint"):
        if route not in ADAPTERS:
            register(route, ApplicationAdapter(route))


_install_default_adapters()
