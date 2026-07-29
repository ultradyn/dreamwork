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

  consume   Read-then-advance as ONE act.  Derives the verification material
            (the high-end event hash + ordinal) from a fresh
            ``events_since_cursor`` read in the SAME invocation, then calls
            ``advance_cursor`` with it — the CAS that verifies the chain prefix
            up to that ordinal and refuses unless ``expected ==`` the verified
            head.  Prints the count + receipt ids consumed.  Refuses non-zero
            on verification failure (the journal changed underfoot); the cursor
            is left unmoved because ``advance_cursor`` only writes on success.

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

Consumer name is the literal ``'coordinator'`` (delivery-modes.md §"How an
agent consumes the cursor in batched mode").

USAGE
  python3 dev/journal_consume.py pending [--journal PATH]
  python3 dev/journal_consume.py consume  [--journal PATH]
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

# The single consumer this drain serves (delivery-modes.md).  A constant so the
# tick command line never has to name it and two tools cannot drift on the
# string the cursor row is keyed by.
CONSUMER = "coordinator"

# The projection yields only receipt.created events (events_since_cursor filters
# on event_kind); every line is one of these, so the kind is a constant derived
# from that contract, not read per-row.  Printed so the output is self-describing.
EVENT_KIND = "receipt.created"

JOURNAL_DEFAULT = ".dreamwork/user-events.sqlite3"

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


def cmd_consume(args, out, err) -> int:
    """Read-then-advance as one act: drain (coordinator_cursor, head].

    The verification material (high-end event hash + ordinal) is derived from a
    FRESH events_since_cursor read in this same invocation, then handed to
    advance_cursor — the CAS that verifies the chain prefix to that ordinal and
    refuses unless expected == the verified head.  A crash between read and
    advance cannot skip events: the cursor only moves at the advance (the last
    step), so a crash before it leaves the cursor unmoved and the next tick
    re-reads the same range.
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
        head = events[-1]
        # Read-then-advance as one act: expected + scanned_through come straight
        # from the read above (the high-end row's event_hash == head_hash() and
        # its ordinal == head_ordinal() — the contract events_since_cursor hands
        # a batched consumer).  advance_cursor verifies the prefix and refuses
        # unless expected matches the verified head; on refuse it writes nothing.
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
        for ev in events:
            out.write(ev.receipt_id + "\n")
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
    return EX_USAGE  # argparse(required=True) makes this unreachable


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
