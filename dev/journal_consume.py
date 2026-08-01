#!/usr/bin/env python3
"""#501 — the tick-consume CLI over the durable user-event journal cursor.

Batched delivery's missing drain half (#342).  The coordinator's heartbeat
wakes the loop, but nothing enumerated what arrived since the last tick — so
batched delivery was lossy until a mechanical drain existed.  This is that
drain: a thin CLI over the ALREADY-LANDED projection
``Journal.events_since_cursor`` and the verifying CAS
``Journal.advance_cursor`` (both in ``user_events/sqlite.py``).  It adds no new
journal query and touches no ``user_events/`` file — it composes the two public
methods a batched consumer needs.

Two subcommands, both taking the store path the way ``dev/ledger.py`` verbs take
``--ledger`` (a default path, overridable with ``--journal`` for tests):

  pending   READ-ONLY.  Prints the ``receipt.created`` events in
            ``(coordinator_cursor, head]`` — one per line, receipt id first so
            the coordinator can parse them.  Quiet on empty (prints nothing,
            exit 0).  Never advances the cursor; never writes (an absent
            journal is treated as empty rather than created, so the read has no
            filesystem side effect).

  consume   Three acts (#526): read, **route each drained receipt through its
            adapter's reconcile** (the exactly-once proof against the
            applied-ledger — a receipt already applied writes nothing; one not
            applied is reported UNAPPLIED), then read-then-advance.  The
            advance derives the verification material (the high-end event hash
            + ordinal) from the SAME ``events_since_cursor`` read, then calls
            ``advance_cursor`` — the CAS that verifies the chain prefix up to
            that ordinal and refuses unless ``expected ==`` the verified head.
            Prints the count, applied/unapplied sub-counts, and one UNAPPLIED
            line per unapplied receipt.  Refuses non-zero on verification
            failure (the journal changed underfoot); the cursor is left unmoved
            because ``advance_cursor`` only writes on success.  The proof
            writes the applied-ledger (``--applied``) but never the cursor.

  #531     ``consume --through ORDINAL`` bounds the advance to ORDINAL — the
            ordinal the coordinator's prior ``pending`` reported as head — so
            an event landing between that read and this consume stays in
            ``(cursor, head]`` and is re-listed next tick instead of being
            advanced past unread (the live race that cost ord=43, the #505
            answer receipt).  Without ``--through`` consume advances to the
            live head.  Both edges refuse EX_USAGE: below/at the cursor (a
            stale ordinal must not rewind or no-op silently) and above the head
            (cannot advance past what exists).  The #526 proof act runs only
            over receipts inside the advanced range ``(cursor, through]``.

  #658     ``pending`` also writes a read-coverage marker sidecar recording the
            ordinal head it actually printed, and ``consume --through N``
            refuses unless that marker proves N was inside the listed range.
            #531 bound the advance against the LIVE head (a race); #658 tightens
            it against the READ head — the operator who piped ``pending`` through
            ``tail`` advanced past ordinals their eyes never saw.  Three named
            refusals (#136): marker absent (bootstrap — bare ``consume`` is the
            escape), marker from a different journal (stale sidecar), and N
            beyond the read's head (the bug — names the uncovered ordinals).
            Bare ``consume`` (no ``--through``) never reads the marker and never
            wedges.  The marker cannot detect a SHELL-level truncation of
            ``pending``'s own stdout (``pending | tail``): it proves every line
            was printed, not that every line was seen — named, not closed.

  #712     The residue of that, and the honest statement of the limit.  #658
            bounded ``--through`` from ABOVE only, so the traced loss survived:
            ``pending`` prints 96..99, the operator's ``tail -3`` shows 97..99,
            and ``consume --through 96`` is INSIDE the listed range — no
            refusal, 96 consumed unread.  Two changes, and they do different
            jobs:
              * ``--through`` must now EQUAL the head of the read on record, so
                a fourth named refusal covers a bound BELOW it (the traced
                case).  This proves the bound came from that read.  Partial
                drains go with it and are not missed: the alternative to
                consuming part of a range is consuming none of it, and an
                unadvanced range is re-listed in full next tick.
              * ``pending`` prints its coverage statement to STDERR, which a
                stdout pipe does not touch, so a truncated view is visibly
                inconsistent with what was listed.
            WHAT THIS DOES NOT DO, stated because the reverse would be the real
            failure: it does not establish that anything was SEEN.  "Seen"
            cannot be established from inside a process that only controls
            "printed" — any value ``pending`` prints either survives the
            truncation (and is then relayable by a truncated reader, proving
            nothing) or does not (and is then unavailable to an honest reader
            who used that truncation).  The only binding form is to require the
            identity of the FIRST listed line, which a ``tail`` removes; it was
            rejected as per-tick ceremony that a shell reflex discharges
            without reading.  The remaining open case is the natural variant:
            hold 97..99, consume ``--through 99``, and 96 is consumed unread
            with only the stderr line as a signal.  See
            ``.dreamwork/lane-712-report.md`` for the IGC.

#722     The drain's two domains disagreed and the journal had no legal
          move.  ``pending`` computed its reported head over
          ``receipt.created`` only, while the cursor advances over EVERY
          ordinal.  When the head was a ``receipt.transition`` (the live
          state), pending reported head 116 while the head was 117:
          ``consume --through 117`` was refused by #712's guard (correctly),
          and ``--through 116`` did not move — no value drained it.  Two
          changes, on the OTHER side from the guard (the guard is RIGHT and
          survives at full strength): ``pending`` reports the TRUE journal
          head while its LISTING stays receipt.created-only, so ``--through
          <head>`` covers every ordinal and the guard keeps bounding against a
          position in the log.  And the coverage line now fires whenever the
          cursor is below the head and NAMES the non-listed ordinals with
          their kinds — #702/#136: pre-fix pending was SILENT with a
          transition above the cursor, so "nothing needs you" and "something
          is hiding" rendered identically.

ATOMICITY SEAM (named, not hidden): the read and the advance are TWO separate
API calls, not one transaction.  Between them a concurrent writer may append.
That is SAFE BY CONSTRUCTION: the chain is append-only, so the prefix
``[1, snapshot_head]`` a consume verifies is unchanged by a later append, and
``advance_cursor`` moves the cursor only to the snapshot head — newer events
land in the NEXT tick's ``(cursor, head]`` and are never lost.  The refusal
case is not a clean append (which never refuses) but an ALTERATION of an
already-chained row (corruption/tampering), which the bounded rebuild inside
``advance_cursor`` detects.  No public write API alters an existing chain row,
so that refusal is not inducible through the real API; the tests reach it by
simulating the corruption with a direct SQL mutation and assert refuse +
cursor-unmoved at the seam the API does expose (see test_journal_consume.py).

#526 SEAM (named): the proof loop runs between the read and the advance.  It
writes the applied-ledger (a side effect on a separate file) but never the
cursor, so a crash in the loop leaves the cursor unmoved and the next tick
re-reads and re-proves the same range — and a receipt already proven APPLIED
writes nothing on the re-prove, so the crash window cannot double-apply.  This
is the wiring the #519 audit's F4 found missing: ``apply``'s exactly-once proof
was exercised only by tests; ``consume`` now imports ``apply`` and routes every
drained receipt through ``reconcile``/the adapter registry before advancing.

Consumer name is the literal ``'coordinator'`` (delivery-modes.md §"How an
agent consumes the cursor in batched mode").

  show      READ-ONLY.  Prints the FULL decoded payload of one or more
            receipts, each preceded by a small metadata header (receipt_id,
            state, revision, client_action_id, request_digest — the fields
            ``get_receipt`` returns).  Selectors are positional and may be an
            ORDINAL (what ``pending``/``consume`` print — all-digits) or a
            RECEIPT-ID (any other token).  Ordinals live on ``events``; a
            receipt does not carry its ordinal, so an ordinal selector joins
            ``events``→``receipts`` to find the receipt_id (#855: a schema
            detail encoded here once, not re-guessed each time).  Never
            advances the cursor; never writes.  Opens through
            ``open_journal_readonly`` (``mode=ro`` + ``query_only=ON``) so
            read-only-ness is a property of the OPEN, not of the care taken
            in composing a query — the single-writer rule made structural.
            Works for ALREADY-CONSUMED receipts too — consumption only moves
            the cursor, the receipt and its event rows persist — so a blindly
            consumed event (its content was never read, only its id printed)
            is recoverable here without hand SQL.  This closes the gap that
            cost one human instruction: the coordinator once ran ``consume``
            with no prior ``pending`` read, and the only way back to a payload
            was a hand-written sqlite query that failed twice on schema
            guesses before it worked (#855).

  expedite  #864 — the EXPEDITED class's delivery verb, called by the repo's
            Claude Code stop hook when the agent pauses.  It is a READER: it
            reads the SAME ``(cursor, head]`` range ``pending`` reads and then
            never advances the cursor and never writes the #658 marker, so the
            tick keeps sole ownership and can neither double-consume nor lose
            an event — everything delivered here is still pending and is still
            drained normally ("it can also be drained like normal from the
            event queue").  The DOUBLE DELIVERY is stopped by the #526/#527
            proof instead: the marker lands at the pause, so the tick proves
            APPLIED and the receipt never reaches consume's UNAPPLIED
            act-list, while ``consume`` names it on an EXPEDITED line so a
            hook whose output was never seen cannot swallow it silently.
            ``--limit`` caps one pause's delivery, expedited first: a cursor
            cannot express a non-contiguous drain, so the cap lives here (a
            projection) and never on ``consume``.

USAGE
  python3 dev/journal_consume.py pending [--journal PATH]
  python3 dev/journal_consume.py consume [--journal PATH] [--applied PATH] \
                                         [--through ORDINAL]
  python3 dev/journal_consume.py expedite [--journal PATH] [--applied PATH] \
                                          [--limit N]
  python3 dev/journal_consume.py show <ord|receipt-id>... [--journal PATH]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# `user_events/` is a package at the repo root; this module lives in `dev/`.
# Add the root so `from user_events.sqlite import open_journal` works when run
# as `python3 dev/journal_consume.py` (sys.path[0] is then `dev/`, not the cwd).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from user_events.sqlite import open_journal  # noqa: E402  — the public API
from user_events.sqlite import open_journal_readonly  # noqa: E402  — #855 read-only door
from user_events import apply  # noqa: E402  — the exactly-once proof (lane D); wiring it into the drain (#526)
from user_events import delivery  # noqa: E402  — the EXPEDITED class predicate (#864)

# The single consumer this drain serves (delivery-modes.md).  A constant so the
# tick command line never has to name it and two tools cannot drift on the
# string the cursor row is keyed by.
CONSUMER = "coordinator"

# The projection yields only receipt.created events (events_since_cursor filters
# on event_kind); every line is one of these, so the kind is a constant derived
# from that contract, not read per-row.  Printed so the output is self-describing.
EVENT_KIND = "receipt.created"

JOURNAL_DEFAULT = ".dreamwork/user-events.sqlite3"

# --- #658: the read-coverage marker. ---
#
# `pending | tail` truncated the operator's eyes and `consume --through <head>`
# then advanced past ordinals nobody ever saw (#658).  The fix is the #654 shape:
# make the silent failure loud.  `pending` records the head ordinal it actually
# printed into a sidecar; `consume --through N` refuses unless that sidecar
# proves N was inside the listed range.  Three refusal cases, each named (#136):
# marker absent (no read — bootstrap), marker from another journal (stale), and
# marker whose range does not cover N (the bug).  Bare `consume` (no --through)
# never reads the marker and never wedges — it is the escape hatch, the right
# form only when there was no prior read to bound against.
#
# The sidecar is a JSON file named "<journal-path>.pending-read" (a sibling of
# the db) so --journal overrides make it travel correctly in tests.  It is
# ephemeral coordination state between two CLI calls in one tick, not durable
# project content; it carries the journal_id (the UUID minted at journal
# creation) so a marker left by a different checkout cannot be honoured.


def _pending_read_path(journal_path: Path) -> Path:
    """The marker sidecar for a journal path: ``<journal>.pending-read``."""
    return Path(str(journal_path) + ".pending-read")


def _write_pending_read(journal_path: Path, journal_id: str, through: int) -> None:
    """Record the head ordinal a ``pending`` read actually printed (#658).

    One JSON object: the journal's id (binds the marker to THIS journal — a UUID
    minted at creation, so a marker from a different checkout cannot satisfy a
    consume against this one) and the upper bound of the range that was printed.
    Overwrites in place — one pending read per tick is the protocol, and the
    latest read is the one a bounded consume must honour.
    """
    import time
    payload = json.dumps(
        {"journal_id": journal_id, "through": through,
         "ts": time.strftime("%Y-%m-%dT%H:%M:%S")},
    )
    _pending_read_path(journal_path).write_text(payload)


def _load_pending_read(journal_path: Path) -> dict | None:
    """Read the marker sidecar, or None if absent, unparseable or malformed (#658).

    None covers BOTH the absent case (bootstrap) and a corrupt marker — both
    degrade to the same named refusal in ``consume``, and a corrupt marker must
    not raise (a guard whose subject may not exist has to degrade to a reading,
    never throw — lessons.md #622).  Returns the parsed dict on success.

    #712: "corrupt" means MALFORMED, not merely unparseable.  The docstring
    above already promised this; the code only delivered it for bad JSON, so a
    parseable-but-shapeless marker (``{}``, or ``through`` as a string) reached
    the ``mark["through"]`` comparisons in ``consume`` and raised there —
    exactly the throw this function exists to prevent, one layer down.  Both
    fields are checked here so every caller can index them.
    """
    mp = _pending_read_path(journal_path)
    if not mp.exists():
        return None
    try:
        mark = json.loads(mp.read_text())
    except (ValueError, OSError):
        return None
    if not isinstance(mark, dict):
        return None
    if not isinstance(mark.get("journal_id"), str):
        return None
    if not isinstance(mark.get("through"), int) or isinstance(mark["through"], bool):
        return None
    return mark


# --- #619: the durable uncleared-unapplied sidecar. ---
#
# The loss this exists to close: `consume` advanced the cursor past a receipt
# whose idea never entered the task ledger, and the ONLY record that it needed
# action was a transient `UNAPPLIED` line in stdout — gone the moment the tick
# was compacted.  Worse, the #526 proof WROTE that receipt's marker into the
# applied-ledger on the first drain (the exactly-once bookkeeping), so a future
# replay proves APPLIED and SILENTLY suppresses the re-report.  So the durable
# records actively concealed the receipt after one tick.
#
# WHY OPTION 1 (refuse to advance past unapplied) WAS REJECTED ON MEASUREMENT.
# `add-idea` (and chat/answer/comment/ask) are NOT expedited
# (`delivery.EXPEDITE_KINDS == ("do-next",)`), so on the FIRST drain of any new
# receipt the marker is absent → NOT_APPLIED → the receipt is ALWAYS unapplied.
# That makes `consumed N, applied 0, unapplied N` the ORDINARY tick, not the
# exception.  A refusal that fires on that fires every tick, so the coordinator
# learns `--force-unapplied` as a reflex and the guard is a rubber stamp — the
# exact degradation the brief predicted.  A non-zero exit on `applied 0` is the
# same noise.  (And either is hollow for loss besides: the proof loop writes the
# marker BEFORE advance_cursor, so a post-loop refusal leaves the marker landed
# and a replay still proves APPLIED.)
#
# THE REMEDY (option 2, minimal): make the unapplied ids DURABLE so they survive
# a compaction, and re-report them every tick until the coordinator CONFIRMS
# filing.  Confirmation clears an id (`consume --cleared <id>`); until then it
# carries over as a `STILL-UNAPPLIED` line.  `--force-unapplied` is the escape
# for a tick the coordinator has handled by inspection (records nothing).
#
# THE ALARM IS CARRIED-OVER, NOT FRESH (the degrade-to-zero ruling, #868).
# Fresh-this-tick unapplied is the ordinary, expected case (the coordinator just
# read `pending` and is filing), so it stays exit 0 with its `UNAPPLIED` lines.
# CARRIED-OVER unapplied (uncleared from a previous tick) is the genuine
# missed-idea signal — that, and only that, is `EX_UNAPPLIED`.  So:
#   `consumed N, applied N`                         → exit 0  (everything landed)
#   `consumed N, applied <N`, fresh UNAPPLIED       → exit 0  (ordinary tick)
#   + `STILL-UNAPPLIED` carried-over                 → exit EX_UNAPPLIED (alarm)
#   `consumed 0` (and nothing carried over)          → exit 0  (quiet — nothing
#                                                    needs you)
# A rubber stamp is impossible: the alarm needs a SECOND tick of non-clearing,
# which is the actual at-risk condition.  `consumed 0` stays quiet unless
# something is carried over, so an idle tick does not train the coordinator to
# ignore the output.
#
# This is RECOVERABLE, not impossible (the brief ranked "impossible" higher but
# that path is the refuted option 1).  It is strictly better than today: the
# content is never lost (`show <id>` recovers any consumed receipt, #855), and
# the REMINDER to act is now durable instead of transient.  The remaining
# residual is the crash window between the proof loop (marker write) and the
# advance — a pre-existing exactly-once property this change inherits and does
# not widen; closing it needs the marker to mean "coordinator-confirmed", a
# bigger change owned elsewhere (named below, out of scope).
#
# The sidecar is a JSON object `{"journal_id", "entries": [...]}` sibling to the
# journal (`<journal>.unapplied`), so `--journal` overrides make it travel in
# tests exactly as the `.pending-read` marker does.  `journal_id` binds it to
# THIS journal so a sidecar from a different checkout cannot satisfy it (#658).


def _unapplied_path(journal_path: Path) -> Path:
    """The uncleared-unapplied sidecar for a journal: ``<journal>.unapplied``."""
    return Path(str(journal_path) + ".unapplied")


def _load_unapplied(journal_path: Path, journal_id: str) -> list[dict]:
    """The uncleared-unapplied entries for THIS journal, or ``[]`` (#619).

    Returns ``[]`` for an absent, corrupt, shapeless, or STALE sidecar (one
    whose ``journal_id`` is not this journal's) — every one of those degrades to
    the same "nothing carried over" reading rather than raising (a guard whose
    subject may not exist has to return a reading, never throw — the
    "degrade to a reading, never throw" lesson).  Each surviving entry is
    shape-checked for a string ``receipt_id`` so a later comparison can index it.
    """
    up = _unapplied_path(journal_path)
    if not up.exists():
        return []
    try:
        data = json.loads(up.read_text())
    except (ValueError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    if data.get("journal_id") != journal_id:
        return []  # stale sidecar from a different journal (#658 binding)
    entries = data.get("entries")
    if not isinstance(entries, list):
        return []
    return [
        e for e in entries
        if isinstance(e, dict) and isinstance(e.get("receipt_id"), str)
    ]


def _store_unapplied(journal_path: Path, journal_id: str, entries: list[dict]) -> None:
    """Overwrite the sidecar with ``entries`` for THIS journal (#619).

    One entry per receipt the drain reported unapplied and the coordinator has
    not yet cleared.  Overwrites in place: the sidecar is the SET of uncleared
    ids, not an append-only log, so clearing shrinks it and a fresh drain that
    records the same id twice keeps one entry.
    """
    import time
    payload = json.dumps({
        "journal_id": journal_id,
        "entries": entries,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    })
    _unapplied_path(journal_path).write_text(payload)


# --- #526: the drain's applied-receipts proof ledger. ---
#
# The audit (#519 F4) found that ``apply``'s exactly-once proof
# (``prove_applied``/``reconcile``/the adapter registry) was exercised ONLY by
# tests — no production module imported it, and ``consume`` was a two-act
# read-then-advance with no middle act.  This is that middle act: every drained
# receipt is routed through its adapter's ``reconcile`` against this one managed
# file BEFORE the cursor advances.  A receipt whose marker is already present
# proves ``APPLIED`` and writes nothing (the ``apply.py`` APPLIED branch); one
# whose marker is absent proves ``NOT_APPLIED`` and is reported UNAPPLIED for
# the coordinator to act on (its marker lands here, so a replay of the same
# range is a no-op by construction).
#
# This file is the durable surface the proof needs.  It is a SINGLE generation
# the drain ever writes — a monotonic marker log (no fork, no rollback), so
# every marker that lands is committed — which is why the proof takes the
# committed-lineage marker path (the identity check is not consulted there;
# markers accumulate and each is provable on its own).  The generation never
# advances because the drain only ever appends, which is the honest model for a
# flat marker log.  (The per-receipt generation/claim/finish CAS is lane E's
# HTTP-cutover mechanism, which the drain does not use — see ``_prove_drained``.)
APPLIED_LEDGER_DEFAULT = ".dreamwork/applied.md"
APPLIED_LEDGER_GENERATION = 1
# The application reference written into each marker's identity.  The
# committed-lineage proof path checks the marker, not the identity, so this
# value does not affect the verdict; it names the drain as the applier.
APPLIED_REF = "coordinator-drain"

# --- #864: the EXPEDITED delivery class. ---
#
# `expedite` is the stop hook's verb: it delivers expedited receipts at the
# agent's next natural pause.  It is a READER — it never calls advance_cursor
# and never writes the #658 read-coverage marker — so the tick keeps sole
# ownership of the cursor and neither double-consumes nor loses an event.  What
# stops the DOUBLE DELIVERY is the #526/#527 proof this file already runs: the
# marker lands at the pause, so the tick's drain proves APPLIED and the receipt
# never reaches the UNAPPLIED list the coordinator acts on.
#
# Invariant, asserted rather than assumed: every expedited kind rides
# `/command`, which HAS an adapter — so the proof always lands a marker and the
# tick can recognise it.  Extending EXPEDITE_KINDS onto a route with no adapter
# would deliver with no marker and double up on the tick, so that change must
# fail here rather than in production.
assert delivery.COMMAND_ROUTE in apply.ADAPTERS, (
    "an expedited kind must ride a route with an application adapter, or the "
    "hook's delivery leaves no marker and the tick delivers it a second time"
)

# The cap on one pause's delivery.  A pause is an interstitial moment, not a
# tick: dumping an unbounded batch into it is the "overwhelmed" failure the
# whole delivery ruling exists to avoid.  Whatever the cap excludes is not lost
# — it is still in (cursor, head] and the tick drains it.
EXPEDITE_LIMIT_DEFAULT = 10

# Stable exit codes (asserted by the test).  pending's empty path and consume's
# 0-event path return EX_OK; a verification refusal returns EX_SOFTWARE (a
# data-integrity event, not a usage error — the caller re-reads next tick).
# #619: EX_UNAPPLIED signals carried-over uncleared-unapplied receipts — a
# genuine missed-idea alarm, NOT a fresh-this-tick drain (that is the ordinary
# tick and stays EX_OK).  Informational, not an error.
EX_OK = 0
EX_USAGE = 64
EX_SOFTWARE = 70
EX_UNAPPLIED = 65

_PREVIEW_LIMIT = 80


def _preview(payload: bytes) -> str:
    """A single-line, length-honest preview of a receipt's exact payload bytes.

    Newlines and tabs are collapsed (``\\n`` / ``\\t``) so one event stays one
    line: this output is line-oriented and may be read by an agent, and a
    payload-supplied newline would otherwise forge a second line (the
    lessons.md #126 injection surface — collapse newlines where human text
    enters any record an agent reads).  Non-UTF-8 payloads report as binary.
    """
    n = len(payload)
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return f"<{n}-byte binary>"
    if len(text) > _PREVIEW_LIMIT:
        text = text[:_PREVIEW_LIMIT] + "…"
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t")


def _format_event(ev) -> str:
    """One tab-separated line, receipt id first (trivially machine-parseable).

    Fields: receipt_id, kind, route, ord=<ordinal>, <len>B, <preview>.  The
    receipt id leads and contains no whitespace, so ``line.split('\\t')[0]`` (or
    ``line.split()[0]``) yields it; the coordinator parses receipt ids one per
    line from ``consume``'s body and these ``pending`` lines alike.
    """
    return (
        f"{ev.receipt_id}\t{EVENT_KIND}\t{ev.route}\t"
        f"ord={ev.ordinal}\t{len(ev.exact_payload_bytes)}B\t"
        f"{_preview(ev.exact_payload_bytes)}"
    )


# --- #504 remainder: the reply path. A drained chat receipt must carry what
# the dreamer needs to answer it — the chat id (== the receipt id), the text,
# and the exact reply command — so the drain is not just a count the loop
# consumes past but the moment it learns a chat is waiting. This is a
# presentation change in the consume output, not a new channel: the receipt is
# already the durable home (the spine's `application → transcript`).

# A topic-chat send rides the /command route (watch.WRITE_ROUTE_HANDLERS) with a
# JSON body {"kind": "chat", "text": "…"}; the chat id IS the receipt id (1:1,
# keyed in watch._handle_command). Neither is a second source of truth — both
# are read from the one receipt the drain already holds.
CHAT_ROUTE = "/command"


def _chat_text(ev) -> str | None:
    """The chat text carried by a drained receipt, or None if it is not a chat.

    Returns the body's ``text`` for a ``/command`` receipt whose payload
    decodes to ``{"kind": "chat", …}``; None for anything else (a non-chat
    command, an unreadable body, a different route). The consume loop uses this
    to decide which drained receipts get reply instructions without a second
    channel — the receipt is the one home.
    """
    if ev.route != CHAT_ROUTE:
        return None
    try:
        payload = json.loads(ev.exact_payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if isinstance(payload, dict) and payload.get("kind") == "chat":
        return str(payload.get("text", ""))
    return None


def _reply_command(chat_id: str) -> str:
    """The exact reply command for a chat id (act 1's writer, by absolute path).

    The dreamer runs it from the target root (where the drain ran), so the
    default ``--target .`` applies; the reply text comes via stdin or argv (the
    relay.py idiom) so shell-hostile bytes never meet a shell. The path is
    absolute (this file is ``<skill>/dev/journal_consume.py``, so the tool is
    ``<skill>/bin/ud-dw-chat``) so the command is copy-pasteable regardless of
    cwd. It goes through ``watch.apply_chat_turn`` — import, never re-implement.
    """
    tool = Path(__file__).resolve().parent.parent / "bin" / "ud-dw-chat"
    return f"python3 {tool} reply {chat_id}"


def cmd_pending(args, out, err) -> int:
    """Read-only: list receipt.created events in (coordinator_cursor, head].

    Never advances.  An absent journal is empty (and is NOT created — the read
    has no filesystem side effect).  Empty prints nothing.

    #658: writes the read-coverage marker sidecar so a bounded ``consume`` can
    refuse if its ``--through`` outruns what this read actually printed.  The
    marker records the head ordinal and the journal id; it is the one side
    effect of an otherwise read-only verb, and it is ephemeral coordination
    state (a sibling ``.pending-read`` file), never the journal itself.

    #712: the coverage statement also goes to STDERR — ``pending: listed N
    receipt(s), ordinals L..H``.  ``pending | tail -3`` truncates fd 1 and does
    not touch fd 2, so the count and the full range still reach the operator
    while the listing in their hands is short.  That is the whole reason it is
    on stderr rather than in a trailer: a trailer rides the channel being
    truncated, so whether it survives depends on WHICH truncation was used
    (``tail`` keeps it, ``head`` and ``grep`` remove it).  stdout stays
    byte-for-byte the documented record — one line per event, receipt id first
    — so no parser sees a line that is not an event.

    This is VISIBILITY, not proof.  It makes a truncated view visibly
    inconsistent with what was listed; it cannot make anyone look.  Nothing
    here establishes that a line was SEEN (see the module docstring's #712
    note).
    """
    journal = Path(args.journal)
    if not journal.exists():
        # No journal → nothing pending; do not create it (read-only).  Wipe a
        # stale marker so a later bounded consume cannot honour a read of a
        # journal that no longer exists (#136: the absent case is named).
        mp = _pending_read_path(journal)
        if mp.exists():
            mp.unlink()
        return EX_OK
    with open_journal(args.journal) as j:
        events = j.events_since_cursor(CONSUMER)
        journal_id = j.journal_id  # bound the marker to THIS journal (#658)
        head = j.head_ordinal()  # #722: the TRUE journal head (all event kinds)
        cursor_ord = j.cursor(CONSUMER).scanned_through_event_ordinal
    # #722: the marker records the TRUE journal head, not the receipt.created
    # head.  The cursor advances over every ordinal (transitions share the
    # chain), so the bound a consume honours must be a position in the log.
    # The listing stays receipt.created-only — the drain delivers receipts;
    # a transition has no envelope.  See the module docstring's #722 note for
    # why this widens the head without weakening #712's guard (the guard's
    # contract — `--through` must equal the head on record — is unchanged;
    # only the VALUE widens to the true head).
    _write_pending_read(journal, journal_id, head)
    for ev in events:
        out.write(_format_event(ev) + "\n")
    # #722: the coverage statement.  #712 put it on stderr; #722 makes it
    # fire whenever the cursor is below the head — including when the
    # listing is empty because every ordinal above the cursor is a kind
    # pending will not list (a transition).  That was the second defect:
    # pending knew something was there and printed nothing (#702 — report,
    # never silently drop; #136 — "nothing needs you" and "something is
    # hiding" must not render identically).  When head == cursor the range
    # is genuinely empty and pending stays quiet (#136's calm grey).
    not_listed = (_non_listed_events(args.journal, cursor_ord, head)
                  if head > cursor_ord else [])
    if events or not_listed:
        parts = [f"pending: listed {len(events)} receipt(s)"]
        if events:
            parts.append(f"ordinals {events[0].ordinal}..{events[-1].ordinal}")
        parts.append(f"head {head}")
        if not_listed:
            # Name the ordinals above the cursor pending will not list, with
            # their kinds — #702: an entry the tool cannot classify must be
            # REPORTED, never silently dropped.
            described = ", ".join(f"ord={o} {k}" for o, k in not_listed)
            parts.append(f"not listed: {described}")
        parts.append(f"(consume --through {head})")
        err.write(" ".join(parts) + "\n")
    return EX_OK


def _non_listed_events(journal_path, cursor_ord: int, head: int) -> list[tuple[int, str]]:
    """The ``(ordinal, kind)`` of events in ``(cursor_ord, head]`` pending does NOT list.

    pending lists ``receipt.created`` only; every other kind
    (``receipt.transition``, ``receipt.health``, ``generation.cutover`` …)
    shares the chain's ordinals but carries no envelope to deliver.  This reads
    them so pending can REPORT them (#702 — report, never silently drop) rather
    than leave the ordinals it knows are there invisible (#136 — "nothing needs
    you" and "something is hiding" must not render identically).
    """
    # READ connection through the one door (#645 increment 5). Core's READ path
    # opens ``?mode=ro`` with ``query_only=ON`` — the journal is not mutated.
    from dreamwork_db import StoreSpec  # noqa: E402 — local import keeps the
    from dreamwork_db import core as db_core  # noqa: E402 — module's cold path lean
    conn = db_core._connect(
        StoreSpec(path=Path(journal_path), busy_timeout_ms=5000), db_core.Access.READ
    )
    try:
        rows = conn.execute(
            "SELECT event_ordinal, event_kind FROM events "
            "WHERE event_ordinal > ? AND event_ordinal <= ? "
            "AND event_kind != ? ORDER BY event_ordinal ASC",
            (cursor_ord, head, EVENT_KIND),
        ).fetchall()
    finally:
        conn.close()
    return [(int(r[0]), r[1]) for r in rows]


def _prove_drained(applied_path: str, ev) -> "apply.Proof":
    """Route one drained event through its adapter's ``reconcile`` (#526 middle act).

    Looks up the adapter for the event's route in ``apply``'s registry and runs
    ONE ``reconcile`` pass against the applied-ledger: prove, then act per the
    post-crash table — ``APPLIED`` finishes only (no write, the
    ``apply.py:318-321`` branch); ``NOT_APPLIED`` writes the marker once then
    finishes; ``UNKNOWN`` surfaces without mutating.  The verdict is returned so
    ``consume`` can report the UNAPPLIED receipts (the ones the coordinator must
    act on).

    This is the wiring the audit's F4 found missing: a production module now
    imports ``apply`` and calls ``reconcile``/``adapter_for``, so a replay of an
    already-applied receipt proves ``APPLIED`` and writes nothing — the
    exactly-once property the design names (delivery-modes.md:168-170) is now
    built into the drain that runs.

    An UNREGISTERED route (no adapter in the registry) cannot be proven or
    marked: it returns ``NOT_APPLIED`` so ``consume`` lists it UNAPPLIED for the
    coordinator to act on, but no marker lands — the proof covers only the
    adapter-backed routes, and an unregistered route is delivered by another
    channel.  In normal operation the cursor advances past it once (it leaves
    ``(cursor, head]``), so it is not re-drained; only an artificial replay (a
    rewound cursor) would re-list it.

    ``finish`` is a NO-OP here: the drain's completion is the cursor advance
    (read-then-advance, unchanged), NOT lane E's per-receipt claim/finish CAS.
    Reconcile takes ``finish`` as a callback precisely so the proof→write
    decision is independent of the journal's completion mechanics, and the
    drain's completion mechanic is the range cursor, not the per-receipt CAS.
    The marker this writes IS the durable "applied" record; finish adds nothing
    the cursor advance does not already do.
    """
    try:
        adapter = apply.adapter_for(ev.route)
    except KeyError:
        return apply.Proof.NOT_APPLIED
    return apply.reconcile(
        applied_path,
        receipt_id=ev.receipt_id,
        adapter=adapter.route,
        application_ref=APPLIED_REF,
        append_effect=lambda text, rid=ev.receipt_id: adapter.append_effect(text, rid),
        reserved_successor=APPLIED_LEDGER_GENERATION,
        committed_lineage=(APPLIED_LEDGER_GENERATION,),
        has_marker=lambda text, rid=ev.receipt_id: adapter.has_marker(text, rid),
        finish=lambda: None,
    )


def _emit_uncleared(out, uncleared: list[dict]) -> int:
    """Write the ``STILL-UNAPPLIED`` block for carried-over receipts (#619).

    These are receipts drained unapplied on a PRIOR tick and not yet cleared —
    the at-risk ideas.  They LEAD the consume output so one is not buried under
    this tick's count, and each line names its recovery (``show``) on the
    summary and its id on its own line.  Returns ``EX_UNAPPLIED`` if any are
    carried over (the missed-idea alarm), else ``EX_OK`` — so a clean drain and
    an idle tick stay quiet, and only a tick with something still uncleared
    alarms.
    """
    if not uncleared:
        return EX_OK
    out.write(
        f"STILL-UNAPPLIED {len(uncleared)} receipt(s) drained on a prior tick "
        f"and not yet cleared — `show <id>` to recover, "
        f"`consume --cleared <id>` once filed\n"
    )
    for e in uncleared:
        out.write(
            f"STILL-UNAPPLIED\t{e['receipt_id']}\t{e.get('route', '?')}\t"
            f"ord={e.get('ordinal', '?')}\n"
        )
    return EX_UNAPPLIED


def _consume_cleared(args, journal_id: str, out, err) -> int:
    """``--cleared`` mode: remove confirmed-filed ids from the sidecar (#619).

    The coordinator's "I filed these" confirmation — the CLEAR half of the
    durable uncleared list, and the act that stops a receipt re-reporting every
    tick.  Does NOT drain and does NOT advance the cursor: it is sidecar
    maintenance, not a consume, so a bounded ``--through`` has no meaning
    against it (it is resolved before the bounds).  Reports what it cleared and
    re-emits whatever remains uncleared.  Returns ``EX_UNAPPLIED`` if anything
    remains, else ``EX_OK``.

    An id the coordinator names that was never recorded is a no-op for it (not
    an error): the clear is idempotent, and a twice-cleared id or one cleared
    before any drain is harmless.  The count printed is the ids that WERE
    present and removed, so the coordinator can see a typo'd id that cleared
    nothing.
    """
    entries = _load_unapplied(Path(args.journal), journal_id)
    cleared_set = set(args.cleared)
    remaining = [e for e in entries if e["receipt_id"] not in cleared_set]
    removed = sorted(
        e["receipt_id"] for e in entries if e["receipt_id"] in cleared_set
    )
    _store_unapplied(Path(args.journal), journal_id, remaining)
    out.write(f"cleared {len(removed)} unapplied receipt(s)\n")
    for rid in removed:
        out.write(f"CLEARED\t{rid}\n")
    return _emit_uncleared(out, remaining)


def cmd_consume(args, out, err) -> int:
    """Read-then-advance as one act: drain (coordinator_cursor, head].

    THREE acts now (#526): read, **route each drained receipt through its
    adapter's reconcile** (the exactly-once proof — a receipt already applied
    writes nothing; one not applied is reported UNAPPLIED), then advance.  The
    read-then-advance contract is UNCHANGED: the cursor advances only over what
    was read (the high-end event's hash + ordinal from the SAME read), and a
    verification refusal still returns EX_SOFTWARE with the cursor unmoved
    (``advance_cursor`` only writes on success).  The proof writes the
    applied-ledger (a side effect on a separate file) but never the cursor —
    the cursor still moves only at the advance, so a crash between the proof
    loop and the advance leaves the cursor unmoved and the next tick re-reads
    (and re-proves) the same range.  A receipt proven APPLIED on the re-prove
    writes nothing, so the crash window cannot double-apply.

    Output: a ``consumed N`` line, ``applied``/``unapplied`` sub-counts, then
    one ``UNAPPLIED`` line per unapplied receipt (id, kind, route) — the list
    the coordinator must act on.  Applied receipts are summarised by the count
    (their content is recoverable via ``show <id>``).

    #619 — the cursor no longer SILENTLY advances past an unapplied receipt.
    Every drained receipt that proves unapplied is recorded in a durable
    ``<journal>.unapplied`` sidecar and re-reported as ``STILL-UNAPPLIED`` on
    every later tick until the coordinator confirms filing (``consume --cleared
    <id>``).  The exit code distinguishes the three cases the degrade-to-zero
    ruling (#868) names: a clean drain and an idle tick stay ``EX_OK``; a tick
    with CARRIED-OVER (still-uncleared) unapplied receipts exits ``EX_UNAPPLIED``
    — the missed-idea alarm.  Fresh-this-tick unapplied is the ORDINARY tick
    (every non-expedited receipt is unapplied on its first drain) and stays
    ``EX_OK``, so the alarm cannot rubber-stamp.  See the #619 note above the
    sidecar helpers for why option 1 (refuse to advance) was rejected on
    measurement.
    """
    journal = Path(args.journal)
    if not journal.exists():
        # No journal → nothing to consume; do not create one to consume zero.
        out.write("consumed 0 event(s)\n")
        return EX_OK
    with open_journal(args.journal) as j:
        journal_id = j.journal_id  # #619: bind the uncleared sidecar to THIS journal
        # --- #619: --cleared is a sidecar-maintenance mode (no drain, no
        # advance).  Resolve it BEFORE the --through bounds — it is the
        # coordinator's "I filed these" confirmation, not a consume, and a
        # bounded --through has no meaning against it.
        if args.cleared is not None:
            return _consume_cleared(args, journal_id, out, err)
        uncleared = _load_unapplied(Path(args.journal), journal_id)
        # --- #531: bound the advance to what the prior pending read reported.
        # `consume` without `--through` advances to the live head (today's
        # semantics).  `consume --through H` advances at most through H — the
        # ordinal the coordinator's prior `pending` reported as head — so an
        # event landing between that `pending` and this `consume` stays in
        # (cursor, head] and is re-listed next tick instead of being advanced
        # past unread.  The live failure: ord=43 (#505 answer receipt) committed
        # between a pending read and consume in one tick; consume advanced to
        # the NEW head, past 43 blind.
        through = args.through
        if through is not None:
            # Both edges refuse EX_USAGE BEFORE any read, so a stale/bogus
            # ordinal never silently no-ops or rewinds.  Cursor/head come from
            # the journal directly (the same row advance_cursor writes/reads).
            cursor_ordinal = j.cursor(CONSUMER).scanned_through_event_ordinal
            head_ordinal = j.head_ordinal()
            if through <= cursor_ordinal:
                # At-or-below the cursor: a rewind (through < cursor) or a
                # no-op (through == cursor).  Neither may pass silently.
                err.write(
                    f"consume: --through {through} is at or below the cursor "
                    f"({cursor_ordinal}); a stale ordinal must not rewind or "
                    f"no-op silently — re-read pending and note its head\n"
                )
                return EX_USAGE
            if through > head_ordinal:
                # Above the head: cannot advance past what exists.
                err.write(
                    f"consume: --through {through} is above the head "
                    f"({head_ordinal}); cannot advance past what exists — "
                    f"re-read pending and note its head\n"
                )
                return EX_USAGE
            # --- #658: the read-coverage check.  A --through value honest
            # about the LIVE head is worthless if the operator's eyes never saw
            # every line of the pending read (the `pending | tail` failure).  So
            # a bounded consume additionally refuses unless the marker the prior
            # `pending` wrote proves `through` was inside the range it printed.
            # FOUR named refusal cases (#136), the last two of which are the
            # bug; the others degrade to a workable escape (bare consume):
            #   absent  → no pending read on record (bootstrap — first run,
            #             cleared state).  Bare `consume` is the right form.
            #   mismatch→ the marker is from a different journal (stale
            #             sidecar).  Bare `consume` is the right form.
            #   uncovered→ through exceeds the read's head: ordinals in
            #              (read_head, through] were never listed.  #658's
            #              truncation bug — re-run pending (do not tail it)
            #              and consume --through the head it prints.
            #   below   → through is under the read's head: the bound is not
            #             from that read at all, so it is from an older or
            #             truncated view of it.  #712's traced loss.
            mark = _load_pending_read(Path(args.journal))
            if mark is None:
                err.write(
                    f"consume: --through {through} but no pending read is on "
                    f"record — run `pending` first (bare `consume` with no "
                    f"--through also advances to the live head)\n"
                )
                return EX_USAGE
            if mark["journal_id"] != journal_id:
                err.write(
                    f"consume: --through {through} but the pending-read marker "
                    f"is for a different journal (stale sidecar) — run "
                    f"`pending` again, or use bare `consume`\n"
                )
                return EX_USAGE
            if through > mark["through"]:
                # Name the ordinals the read never listed — #658 requires the
                # refusal message name them, not merely say "check failed".
                uncovered = list(range(mark["through"] + 1, through + 1))
                err.write(
                    f"consume: --through {through} advances past ordinals the "
                    f"last `pending` read never listed "
                    f"(read reported head {mark['through']}; uncovered "
                    f"ordinals {uncovered}) — re-run `pending` without "
                    f"`head`/`tail` and consume --through the head it prints\n"
                )
                return EX_USAGE
            if through < mark["through"]:
                # --- #712: the traced loss, which #658's bound does not catch.
                # `pending` printed 96..99; the operator piped it through
                # `tail -3`, held 97..99, and consumed `--through 96` carried
                # over from an EARLIER read.  96 is inside the listed range, so
                # #658's `through > mark` check is satisfied and 96 is consumed
                # unread.  The tell is that the bound is not the head of the
                # read on record: a --through below it did not come from that
                # read, so it came from an older or truncated view of it.
                # Name the ordinals this consume would advance the cursor over
                # — a "range mismatch" that does not say what is lost is not
                # discriminating.  Partial drains are the collateral, and they
                # cost nothing: the alternative to consuming part of a range is
                # consuming none of it, and an unadvanced range is re-listed in
                # full next tick.
                over = list(range(cursor_ordinal + 1, through + 1))
                shown = over if len(over) <= 8 else over[:8] + ["…"]
                err.write(
                    f"consume: --through {through} is BELOW the head of the "
                    f"read on record ({mark['through']}) — a bound that did "
                    f"not come from that read came from an older or truncated "
                    f"view of it, and ordinals {shown} would be advanced past "
                    f"on that basis. Re-run `pending` (do not pipe it through "
                    f"`head`/`tail`) and consume --through "
                    f"{mark['through']}; or consume nothing this tick — an "
                    f"unadvanced range is re-listed in full, so skipping loses "
                    f"nothing. Bare `consume` (no --through) is never gated by "
                    f"the marker.\n"
                )
                return EX_USAGE
        events = j.events_since_cursor(CONSUMER)
        head_ordinal = j.head_ordinal()
        cursor_ordinal = j.cursor(CONSUMER).scanned_through_event_ordinal
        # #722: the advance target is the TRUE head (bare consume) or
        # --through.  Either may land on a non-receipt event the cursor must
        # still advance past — the cursor is a position in the append-only
        # chain, not a count of receipts, so advancing over a transition
        # (which carries no envelope) is a legal move and the only one that
        # drains the journal.  The proof loop below runs over receipts only.
        target_ord = through if through is not None else head_ordinal
        if target_ord <= cursor_ordinal:
            # Genuinely nothing to advance: the cursor already sits at or past
            # the target.  (An up-to-date consumer reads this on every tick.)
            # #619: an idle tick still re-reports carried-over uncleared
            # unapplied receipts (the at-risk ideas) — "nothing needs you"
            # holds only when nothing is carried over (#136: "nothing needs
            # you" and "something is hiding" must not render identically).
            code = _emit_uncleared(out, uncleared)
            out.write("consumed 0 event(s)\n")
            return code
        drained = [ev for ev in events if ev.ordinal <= target_ord]
        # The expected hash at the target ordinal.  When the target IS a
        # receipt in `events` use its hash directly; otherwise (a transition,
        # health mark, or cutover — not projected by events_since_cursor) derive
        # the verified hash from the chain.  advance_cursor recomputes and
        # refuses on mismatch, so either source is safe; verify_chain is the
        # "don't trust stored hash" path and costs O(target) — negligible next
        # to advance_cursor's own bounded rebuild of the same range.
        target_ev = next((ev for ev in events if ev.ordinal == target_ord), None)
        if target_ev is not None:
            target_hash = target_ev.event_hash
        else:
            target_hash = j.verify_chain(through_ordinal=target_ord).head_hash
        # --- #526 middle act: route each DRAINED receipt through the proof.
        # The proof applies only to receipts INSIDE the advanced range (#531):
        # a receipt already applied (its marker is in the ledger) proves APPLIED
        # and writes nothing; one not applied writes its marker once and is
        # reported UNAPPLIED.  This loop writes the applied-ledger only — it
        # never touches the cursor, so the read-then-advance contract below is
        # unchanged.  Events beyond `--through` are neither drained nor proven.
        applied = []
        unapplied = []
        for ev in drained:
            verdict = _prove_drained(args.applied, ev)
            if verdict is apply.Proof.APPLIED:
                applied.append(ev)
            else:  # NOT_APPLIED (written + reported) or UNKNOWN (reported, no write)
                unapplied.append(ev)
        # --- advance (read-then-advance over the bounded range): expected +
        # scanned_through come from the target ordinal (the high end of the
        # advanced range — the whole-chain head without --through, or `through`
        # with it).  advance_cursor verifies the prefix and refuses unless
        # expected matches the verified head; on refuse it writes nothing.
        result = j.advance_cursor(
            CONSUMER,
            expected=target_hash,
            scanned_through=target_ord,
        )
        if result.kind != "advanced":
            # Verification failed: the journal changed underfoot (an
            # already-chained row was altered — a clean append never refuses;
            # see the module docstring's atomicity seam).  Cursor unmoved
            # because advance_cursor only writes on success.  Never force.
            err.write(
                f"consume: refused ({result.reason}); journal changed underfoot "
                f"since the read — cursor unmoved, re-read next tick\n"
            )
            return EX_SOFTWARE
        # #619: carried-over uncleared LEAD the output, so an at-risk idea is
        # not buried under this tick's count.  The exit code follows the
        # carried-over alarm (EX_UNAPPLIED iff something is still uncleared);
        # fresh-this-tick unapplied is the ordinary tick and stays exit 0.
        code = _emit_uncleared(out, uncleared)
        out.write(f"consumed {len(drained)} event(s)\n")
        out.write(f"applied {len(applied)}\n")
        out.write(f"unapplied {len(unapplied)}\n")
        for ev in unapplied:
            out.write(
                f"UNAPPLIED\t{ev.receipt_id}\t{EVENT_KIND}\t{ev.route}\n"
            )
        # --- #864: name the receipts the stop hook already delivered.
        # An expedited receipt proving APPLIED on its drain was handed to the
        # agent at a pause, so it is correctly absent from the UNAPPLIED
        # act-list above.  But if that hook output never reached the agent, a
        # bare `applied N` would swallow one of his instructions in silence —
        # #136: "nothing needs you" and "something is hiding" must not render
        # identically.  So each one is named; the content is one `show` away.
        for ev in applied:
            if delivery.is_expedited(ev.route, ev.exact_payload_bytes):
                out.write(
                    f"EXPEDITED\t{ev.receipt_id}\t{ev.route}\t"
                    f"already delivered at a pause — `show {ev.receipt_id}` for its text\n"
                )
        # --- #504 remainder: drained chat receipts carry what the dreamer needs
        # to reply — the chat id (== receipt id), the text, and the exact reply
        # command. Presented for every drained chat receipt: the drain is the
        # moment the loop learns a chat is waiting, whether the receipt proved
        # APPLIED (its human turn already wrote) or UNAPPLIED. The text is
        # collapsed to one line (the lessons.md:283 rule — a newline in his
        # words must not forge a second output line); the full transcript is
        # one `show`/`ud-dw-chat show` away.
        chats = [(ev.receipt_id, _chat_text(ev)) for ev in drained]
        chats = [(rid, text) for rid, text in chats if text is not None]
        for chat_id, text in chats:
            oneline = " ".join(text.split())
            out.write(f"CHAT\t{chat_id}\t{oneline}\n")
            out.write(f"  reply: {_reply_command(chat_id)}\n")
        # --- #619: record this tick's fresh unapplied into the durable sidecar
        # so they survive a compaction and re-report next tick unless cleared.
        # --force-unapplied records nothing — the escape for a tick the
        # coordinator has handled by inspection (bootstrap, or a deliberate
        # "do not track this drain").  Carried-over uncleared persist in the
        # sidecar regardless: force is about THIS tick's fresh receipts, not
        # about forgetting ones already recorded.
        if not args.force_unapplied:
            existing = {e["receipt_id"] for e in uncleared}
            fresh = [
                {"receipt_id": ev.receipt_id, "ordinal": ev.ordinal,
                 "route": ev.route, "kind": EVENT_KIND}
                for ev in unapplied
                if ev.receipt_id not in existing
            ]
            if fresh:
                _store_unapplied(Path(args.journal), journal_id, uncleared + fresh)
        return code


def _expedited_record(ev, kind: str) -> str:
    """One delivery block: a column-0 record line, then the payload indented.

    The record line is tab-separated with the receipt id first, exactly like
    ``pending``.  The FULL payload follows — this verb IS the delivery, not a
    triage list, so the 80-character preview that sends the loop to hand-written
    SQL (#855) would defeat the point.  Every payload line is indented by two
    spaces so a newline in his text cannot forge a second column-0 record: the
    lessons.md #126 surface, met by indentation rather than by collapsing,
    because a multi-line instruction must stay readable here.
    """
    try:
        text = ev.exact_payload_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = f"<{len(ev.exact_payload_bytes)}-byte binary>"
    body = "\n".join("  " + line for line in text.splitlines()) or "  <empty>"
    return (
        f"EXPEDITED\t{ev.receipt_id}\t{ev.route}\tord={ev.ordinal}\t{kind}\n"
        f"{body}\n"
    )


def cmd_expedite(args, out, err) -> int:
    """Deliver EXPEDITED receipts at a natural pause, WITHOUT moving the cursor (#864).

    THE CURSOR CONTRACT, which is the whole of this verb's safety.  It reads the
    same ``(cursor, head]`` range ``pending`` reads, through the same
    ``events_since_cursor`` projection, and then:

      * it does NOT call ``advance_cursor`` — so the tick's ``consume --through
        N`` finds the cursor exactly where its own ``pending`` left it (#531's
        bound is untouched), and every receipt delivered here is STILL pending
        and still drained normally.  Neither double-consume nor loss is
        possible, because there is only ever one caller that advances.
      * it does NOT write the ``.pending-read`` marker — deliberately.  A hook
        firing between the coordinator's ``pending`` and its ``consume --through
        N`` would otherwise rewrite that marker and #712's ``through ==
        mark['through']`` guard would refuse the drain: a hook that silently
        jams the tick.

    WHAT STOPS THE DOUBLE DELIVERY is the proof, not the cursor.  Each receipt
    delivered here is routed through the same ``apply.reconcile`` the drain
    runs, so its marker lands at the pause; the tick then proves ``APPLIED``,
    writes nothing, and the receipt never reaches ``consume``'s ``UNAPPLIED``
    list — the list the coordinator acts on.  Delivered early, acted on once
    (#519/#527).  A receipt whose proof is ``UNKNOWN`` (a torn applied-ledger)
    is NOT delivered: no marker landed, so delivering it would double up on the
    tick.  It degrades to BATCHED, and the count is reported (#702).

    THE CAP AND WHAT "PRIORITISED" MEANS.  A cursor is a position, so a drain
    cannot skip a receipt — ``consume`` therefore has no cap and must not get
    one.  This verb is a projection, so its cap is real: the WHOLE pending range
    is ordered ``(class, ordinal)`` with expedited first, the first ``--limit``
    are taken, and the expedited members of that slice are delivered.  Ordinary
    receipts are never delivered here — that is what keeps the flag meaningful —
    so when they hold the lower ordinals they still do not take the cap's slots.
    """
    journal = Path(args.journal)
    if not journal.exists():
        # No journal → nothing to deliver.  Do not create it: this verb is a
        # reader and an absent journal must stay absent (the #501 discipline).
        return EX_OK
    with open_journal(args.journal) as j:
        events = j.events_since_cursor(CONSUMER)
    classed = [
        (delivery.is_expedited(ev.route, ev.exact_payload_bytes), ev)
        for ev in events
    ]
    # Expedited first, then by ordinal.  Dropping the class term here is the
    # #864 direction-1 red: with ordinary receipts on the lower ordinals a
    # capped slice would then hold none of his expedited ones.
    ordered = sorted(classed, key=lambda ce: (0 if ce[0] else 1, ce[1].ordinal))
    capped = ordered[: args.limit]
    candidates = [ev for expedited, ev in capped if expedited]
    total_expedited = sum(1 for expedited, _ in classed if expedited)
    ordinary = len(classed) - total_expedited

    delivered, held = [], []
    for ev in candidates:
        verdict = _prove_drained(args.applied, ev)
        if verdict is apply.Proof.NOT_APPLIED:
            delivered.append(ev)
        else:
            # APPLIED  — already delivered (an earlier pause, or the tick).
            # UNKNOWN  — the ledger is torn; no marker landed, so the tick must
            #            be the one to deliver it.
            held.append((ev, verdict))
    for ev in delivered:
        out.write(_expedited_record(
            ev, delivery.command_kind(ev.route, ev.exact_payload_bytes) or "?"))

    # The coverage statement, on stderr so it never mixes with the delivery the
    # hook forwards.  #136: silence must mean "nothing was here", so anything
    # withheld — by the cap, by an UNKNOWN proof, or because it is ordinary —
    # is counted out loud rather than dropped.
    if classed:
        parts = [f"expedite: delivered {len(delivered)} of {total_expedited} expedited"]
        withheld = total_expedited - len(candidates)
        if withheld:
            parts.append(f"{withheld} over the cap ({args.limit})")
        if held:
            parts.append(f"{len(held)} held ({', '.join(sorted({v.value for _, v in held}))})")
        if ordinary:
            parts.append(f"{ordinary} ordinary receipt(s) wait for the tick")
        parts.append("cursor unmoved — all of these are still pending")
        err.write("; ".join(parts) + "\n")
    return EX_OK


# The header keys shown above a show payload, in the order printed.  A constant
# so the header shape cannot drift from what get_receipt returns (the same dict
# the test asserts against) — every key here is a key get_receipt guarantees.
_SHOW_HEADER_KEYS = (
    "receipt_id", "state", "revision",
    "client_action_id", "request_digest",
)


def cmd_show(args, out, err) -> int:
    """Read-only: print the FULL decoded payload of one or more receipts (#855).

    Each positional selector is an ORDINAL (all-digits — what ``pending`` and
    ``consume`` print) or a RECEIPT-ID (any other token).  Composes the single
    public read ``get_receipt(receipt_id)`` for the payload; an ordinal
    selector is first joined ``events``→``receipts`` to recover the receipt_id
    (receipts do not carry the ordinal — #855's schema note, encoded once).
    Never advances the cursor; the receipt row persists after consume, so this
    is the recovery path for a blindly-consumed event whose content was never
    read.  An absent journal or any unknown selector falls to the same
    "not found" path: a one-line stderr message per miss and EX_USAGE, with no
    write and no db creation.

    Opens through ``open_journal_readonly`` — ``mode=ro`` + ``query_only=ON`` —
    so a read cannot mutate the store even in principle.  Read-only-ness is a
    property of the OPEN, not of a carefully-typed query string: the gap that
    motivated #855 was a hand heredoc one character away from a writing open.
    """
    journal = Path(args.journal)
    if not journal.exists():
        # No journal → not found; do not create it (read-only, #501 discipline).
        for sel in args.selectors:
            err.write(f"show: {sel} not found (journal absent: {args.journal})\n")
        return EX_USAGE
    misses = []
    with open_journal_readonly(args.journal) as j:
        for sel in args.selectors:
            receipt, ord_seen = _resolve_selector(j, sel)
            if receipt is None:
                misses.append(sel)
                err.write(f"show: {sel} not found\n")
                continue
            _write_receipt_block(out, receipt, ord_seen)
    return EX_OK if not misses else EX_USAGE


def _resolve_selector(j, selector: str):
    """Resolve one ORDINAL or RECEIPT-ID selector to ``(receipt, ordinal)``.

    An all-digits selector is an ORDINAL (what ``pending``/``consume`` print);
    receipt-ids are UUIDs (always contain a hyphen) so the discriminator is
    unambiguous.  Ordinals live on ``events.event_ordinal`` and a receipt does
    not carry its ordinal, so an ordinal selector joins ``events``→``receipts``
    to find the receipt_id before the by-id read (#855: the schema detail that
    cost two trial-and-error hand queries, encoded here).  A receipt-id
    selector reads the receipt directly and best-effort looks up its first
    ordinal for the banner.  Returns ``(receipt_or_None, ordinal_or_None)``;
    ``(None, None)`` means the selector resolved to no receipt.
    """
    if selector.isdigit():
        ordinal = int(selector)
        row = j.conn.execute(
            "SELECT receipt_id FROM events WHERE event_ordinal = ?",
            (ordinal,),
        ).fetchone()
        if row is None:
            return None, None
        receipt = j.get_receipt(row["receipt_id"])
        return receipt, ordinal
    receipt = j.get_receipt(selector)
    row = j.conn.execute(
        "SELECT event_ordinal FROM events WHERE receipt_id = ? "
        "ORDER BY event_ordinal ASC LIMIT 1",
        (selector,),
    ).fetchone()
    return receipt, (int(row["event_ordinal"]) if row is not None else None)


def _write_receipt_block(out, receipt, ord_seen) -> None:
    """One receipt block: a self-identifying banner, the header, then payload.

    The banner (``# receipt <id>  ord=<n>``) delimits multi-receipt output so a
    block is self-identifying without a separate separator line, and ``#``
    reads as metadata to a human scanning the output.  The header keys and the
    verbatim-payload write are unchanged from the single-receipt ``show``; the
    deliberate exception to the #126 newline-collapse rule applies here — this
    output is for an agent to READ, and a payload may be a multi-line human
    instruction.
    """
    banner = f"# receipt {receipt['receipt_id']}"
    if ord_seen is not None:
        banner += f"  ord={ord_seen}"
    out.write(banner + "\n")
    for key in _SHOW_HEADER_KEYS:
        out.write(f"{key}: {receipt[key]}\n")
    payload = receipt["exact_payload_bytes"]
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        # Verbatim bytes were not UTF-8; report the size and print nothing else
        # (no length cap, no preview collapse — this verb is for reading, and a
        # binary payload has nothing legible to read).
        out.write(f"\n<{len(payload)}-byte binary payload>\n")
        return
    # Newlines are printed VERBATIM here — the deliberate exception to the
    # lessons.md:283 collapse rule that pending/preview obey.  This output is
    # for an agent to READ (a payload may be a multi-line human instruction),
    # not a line-oriented log a monitor wakes on and parses one line at a time.
    out.write("\n")
    out.write(text)
    if not text.endswith("\n"):
        out.write("\n")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dev/journal_consume.py",
        description=(
            "Drain the durable user-event journal's coordinator cursor on a "
            "tick (#501). pending lists what arrived; consume read-then-advances."
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser(
        "pending",
        help="list receipt.created events since the coordinator cursor (read-only)",
    )
    pp.add_argument(
        "--journal", default=JOURNAL_DEFAULT,
        help="journal db path (default: %(default)s)",
    )

    pc = sub.add_parser(
        "consume",
        help="read-then-advance the coordinator cursor over (cursor, head]",
    )
    pc.add_argument(
        "--journal", default=JOURNAL_DEFAULT,
        help="journal db path (default: %(default)s)",
    )
    pc.add_argument(
        "--applied", default=APPLIED_LEDGER_DEFAULT,
        help=(
            "applied-receipts proof ledger path — each drained receipt is "
            "routed through its adapter's reconcile against this file (#526); "
            "default: %(default)s"
        ),
    )
    pc.add_argument(
        "--through", type=int, default=None, metavar="ORDINAL",
        help=(
            "bound the advance to ORDINAL — advance at most through the "
            "ordinal the prior `pending` read reported as head, so an event "
            "landing between that read and this consume stays pending (#531). "
            "Without it, consume advances to the live head (today's semantics). "
            "Refuses EX_USAGE below/at the cursor (a stale ordinal must not "
            "rewind or no-op silently) or above the head.  #658/#712: ORDINAL "
            "must EQUAL the head of the read on record — above it advances "
            "past ordinals never listed, below it means the bound came from an "
            "older or truncated view rather than that read.  Bare `consume` is "
            "never gated by the marker."
        ),
    )
    pc.add_argument(
        "--cleared", nargs="*", default=None, metavar="RECEIPT-ID",
        help=(
            "#619 — confirm that these receipt ids (drained unapplied on a "
            "prior tick) have been filed, removing them from the uncleared "
            "sidecar so they stop re-reporting.  Sidecar-maintenance mode: no "
            "drain, no advance.  With no ids, just reports what is still "
            "uncleared.  Exits EX_UNAPPLIED if anything remains uncleared."
        ),
    )
    pc.add_argument(
        "--force-unapplied", action="store_true",
        help=(
            "#619 — escape hatch: drain normally but do NOT record this tick's "
            "fresh unapplied receipts into the uncleared sidecar (carried-over "
            "ones still re-report).  For a tick handled by inspection, or "
            "bootstrap.  The safe default (no flag) records every unapplied "
            "receipt durably; do not make this reflexive or an idea can be "
            "lost the way it was before #619."
        ),
    )

    pe = sub.add_parser(
        "expedite",
        help=(
            "deliver EXPEDITED receipts at a natural pause, without moving the "
            "cursor (#864 — the stop hook's verb)"
        ),
    )
    pe.add_argument(
        "--journal", default=JOURNAL_DEFAULT,
        help="journal db path (default: %(default)s)",
    )
    pe.add_argument(
        "--applied", default=APPLIED_LEDGER_DEFAULT,
        help=(
            "applied-receipts proof ledger — the marker written here at the "
            "pause is what makes the tick's drain recognise the receipt as "
            "already delivered (default: %(default)s)"
        ),
    )
    pe.add_argument(
        "--limit", type=int, default=EXPEDITE_LIMIT_DEFAULT, metavar="N",
        help=(
            "cap one pause's delivery at N receipts, expedited first "
            "(default: %(default)s). Whatever the cap excludes stays pending "
            "and is drained by the tick."
        ),
    )

    ps = sub.add_parser(
        "show",
        help="print the full payload of one or more receipts by ordinal or id (read-only, #855)",
    )
    ps.add_argument(
        "selectors", nargs="+", metavar="ORD|RECEIPT-ID",
        help=(
            "one or more receipts to read — an all-digits token is an ORDINAL "
            "(what `pending`/`consume` print; joined events→receipts), any "
            "other token is a receipt-id. Read-only; never advances the cursor."
        ),
    )
    ps.add_argument(
        "--journal", default=JOURNAL_DEFAULT,
        help="journal db path (default: %(default)s)",
    )
    return p


def main(argv=None, out=None, err=None) -> int:
    """Dispatch one subcommand. Returns a stable exit code; never raises SystemExit."""
    if argv is None:
        argv = sys.argv[1:]
    if out is None:
        out = sys.stdout
    if err is None:
        err = sys.stderr
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else EX_USAGE
        return EX_OK if code == 0 else EX_USAGE
    if args.cmd == "pending":
        return cmd_pending(args, out, err)
    if args.cmd == "consume":
        return cmd_consume(args, out, err)
    if args.cmd == "expedite":
        return cmd_expedite(args, out, err)
    if args.cmd == "show":
        return cmd_show(args, out, err)
    return EX_USAGE  # argparse(required=True) makes this unreachable


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
