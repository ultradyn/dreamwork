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
  python3 dev/journal_consume.py consume [--journal PATH] [--applied PATH]
  python3 dev/journal_consume.py show <receipt-id> [--journal PATH]
"""
from __future__ import annotations

import argparse
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


def cmd_pending(args, out) -> int:
    """Read-only: list receipt.created events in (coordinator_cursor, head].

    Never advances.  An absent journal is empty (and is NOT created — the read
    has no filesystem side effect).  Empty prints nothing.
    """
    journal = Path(args.journal)
    if not journal.exists():
        # No journal → nothing pending; do not create it (read-only).
        return EX_OK
    with open_journal(args.journal) as j:
        events = j.events_since_cursor(CONSUMER)
    if not events:
        return EX_OK  # the quiet rule: empty prints nothing extra
    for ev in events:
        out.write(_format_event(ev) + "\n")
    return EX_OK


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
        events = j.events_since_cursor(CONSUMER)
        if not events:
            out.write("consumed 0 event(s)\n")
            return EX_OK
        # --- #526 middle act: route each drained receipt through the proof.
        # A receipt already applied (its marker is in the ledger) proves APPLIED
        # and writes nothing; one not applied writes its marker once and is
        # reported UNAPPLIED.  This loop writes the applied-ledger only — it
        # never touches the cursor, so the read-then-advance contract below is
        # unchanged.
        applied = []
        unapplied = []
        for ev in events:
            verdict = _prove_drained(args.applied, ev)
            if verdict is apply.Proof.APPLIED:
                applied.append(ev)
            else:  # NOT_APPLIED (written + reported) or UNKNOWN (reported, no write)
                unapplied.append(ev)
        # --- advance (unchanged): read-then-advance over what was read.
        # expected + scanned_through come straight from the read above (the
        # high-end row's event_hash == head_hash() and its ordinal ==
        # head_ordinal()).  advance_cursor verifies the prefix and refuses
        # unless expected matches the verified head; on refuse it writes nothing.
        head = events[-1]
        result = j.advance_cursor(
            CONSUMER,
            expected=head.event_hash,
            scanned_through=head.ordinal,
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
        out.write(f"consumed {len(events)} event(s)\n")
        out.write(f"applied {len(applied)}\n")
        out.write(f"unapplied {len(unapplied)}\n")
        for ev in unapplied:
            out.write(
                f"UNAPPLIED\t{ev.receipt_id}\t{EVENT_KIND}\t{ev.route}\n"
            )
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
    # lessons.md #126 collapse rule that pending/preview obey.  This output is
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
        return cmd_pending(args, out)
    if args.cmd == "consume":
        return cmd_consume(args, out, err)
    if args.cmd == "show":
        return cmd_show(args, out, err)
    return EX_USAGE  # argparse(required=True) makes this unreachable


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
