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

  show      READ-ONLY.  Prints the FULL decoded payload of one receipt, plus a
            small metadata header (receipt_id, state, revision,
            client_action_id, request_digest — the fields ``get_receipt``
            returns, one per line).  Never advances the cursor; never writes.
            Works for ALREADY-CONSUMED receipts too — consumption only moves
            the cursor, the receipt and its event rows persist — so a blindly
            consumed event (its content was never read, only its id printed)
            is recoverable here without hand SQL.  This closes the lossy-tick
            failure that already cost one human instruction: the coordinator
            once ran ``consume`` with no prior ``pending`` read, and the only
            way back to a payload was a hand-written sqlite query that failed
            twice on schema guesses before it worked.

USAGE
  python3 dev/journal_consume.py pending [--journal PATH]
  python3 dev/journal_consume.py consume [--journal PATH] [--applied PATH] \
                                         [--through ORDINAL]
  python3 dev/journal_consume.py show <receipt-id> [--journal PATH]
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
from user_events import apply  # noqa: E402  — the exactly-once proof (lane D); wiring it into the drain (#526)

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

# Stable exit codes (asserted by the test).  pending's empty path and consume's
# 0-event path return EX_OK; a verification refusal returns EX_SOFTWARE (a
# data-integrity event, not a usage error — the caller re-reads next tick).
EX_OK = 0
EX_USAGE = 64
EX_SOFTWARE = 70

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
    conn = sqlite3.connect(str(journal_path))
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
    """
    journal = Path(args.journal)
    if not journal.exists():
        # No journal → nothing to consume; do not create one to consume zero.
        out.write("consumed 0 event(s)\n")
        return EX_OK
    with open_journal(args.journal) as j:
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
            journal_id = j.journal_id  # #658: bind the marker to THIS journal
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
            out.write("consumed 0 event(s)\n")
            return EX_OK
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
        out.write(f"consumed {len(drained)} event(s)\n")
        out.write(f"applied {len(applied)}\n")
        out.write(f"unapplied {len(unapplied)}\n")
        for ev in unapplied:
            out.write(
                f"UNAPPLIED\t{ev.receipt_id}\t{EVENT_KIND}\t{ev.route}\n"
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
        return EX_OK


# The header keys shown above a show payload, in the order printed.  A constant
# so the header shape cannot drift from what get_receipt returns (the same dict
# the test asserts against) — every key here is a key get_receipt guarantees.
_SHOW_HEADER_KEYS = (
    "receipt_id", "state", "revision",
    "client_action_id", "request_digest",
)


def cmd_show(args, out, err) -> int:
    """Read-only: print the FULL decoded payload of one receipt (#512).

    Composes the single public read ``get_receipt(receipt_id)`` — no new
    journal query, no ``user_events/`` change.  Never advances the cursor; the
    receipt row persists after consume (consume only moves the cursor), so this
    is the recovery path for a blindly-consumed event whose content was never
    read.  An absent journal or unknown receipt both fall to the same
    "not found" path: a one-line stderr message and EX_USAGE, with no write and
    no db creation (read-only, the #501 discipline).
    """
    journal = Path(args.journal)
    if not journal.exists():
        # No journal → not found; do not create it (read-only, #501 discipline).
        err.write(f"show: receipt {args.receipt_id} not found "
                  f"(journal absent: {args.journal})\n")
        return EX_USAGE
    with open_journal(args.journal) as j:
        receipt = j.get_receipt(args.receipt_id)
    if receipt is None:
        err.write(f"show: receipt {args.receipt_id} not found\n")
        return EX_USAGE
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
        return EX_OK
    # Newlines are printed VERBATIM here — the deliberate exception to the
    # lessons.md:283 collapse rule that pending/preview obey.  This output is
    # for an agent to READ (a payload may be a multi-line human instruction),
    # not a line-oriented log a monitor wakes on and parses one line at a time.
    out.write("\n")
    out.write(text)
    if not text.endswith("\n"):
        out.write("\n")
    return EX_OK


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

    ps = sub.add_parser(
        "show",
        help="print the full decoded payload of one receipt (read-only, #512)",
    )
    ps.add_argument("receipt_id", help="the receipt id to read")
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
    if args.cmd == "show":
        return cmd_show(args, out, err)
    return EX_USAGE  # argparse(required=True) makes this unreachable


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
