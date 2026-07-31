#!/usr/bin/env python3
"""#260 — the post-compaction witness audit: prove no missed submissions.

THE INCIDENT (#260, P1).  A coordinator, after a cancelled compaction,
GUESSED a cutoff and falsely concluded "no missed messages" before it had
scanned the full witness.  The guess was the failure: it had no proof, and
the proof it needed is that every submission the human made is either
drained-or-drainable by the cursor, or explicitly named as something the
cursor can never reach.

ACT 0 VERDICT (this is why the tool is shaped this way).  The journal cursor
CLOSES #260 for every submission *kind* the filing names.  Every registered
write route commits a durable receipt BEFORE dispatch (``watch.py`` E3 cutover,
``if not truncated and self.journal_shadow``), and ``dev/journal_consume.py
pending | consume --through <ord>`` drains ``(coordinator_cursor, head]`` with
an exactly-once proof (#526) and a bounded advance (#531).  The registered
routes are ``WRITE_ROUTE_HANDLERS`` (``watch.py``):

    /answer  /ask  /comment  /command  /decide  /tint  /run-mode  /posture  /deploy

— so answer/ask/comment/command/tint (the kinds the filing names) plus
decide/run-mode/posture/deploy are ALL journaled.  ``journal_shadow=True`` is
the production default, so this is live.

THE GAP THE CURSOR CANNOT SEE (and this tool exists to name).  The cursor
drains receipts; it can say nothing about submissions that LEFT NO RECEIPT.
Two classes of ``submissions.log`` record commit no receipt by construction:

  · TRUNCATED — a body over the 20,000-byte cap is refused 413 BEFORE the
    receipt branch (``watch.py`` ``if not truncated and self.journal_shadow``);
    its first 20,000 bytes live ONLY in ``submissions.log`` (#199).  The cursor
    will never list it.
  · UNKNOWN ROUTE — a POST path not in ``WRITE_ROUTE_HANDLERS`` is 404'd
    pre-receipt (``watch.py`` E5); ``submissions.log`` is its only home.

A coordinator trusting the cursor ALONE could conclude "nothing pending" while a
truncated answer sits unrecovered in the witness.  This tool cross-checks the
witness (``submissions.log``, verbatim and complete) against the journal and
PROVES coverage: every witness record either maps to a receipt (the cursor's
surface — drained already, or drainable next tick), or is named as a record the
cursor can never reach (truncated / unknown-route / unmatched).  Exit 0 means
"the journal cursor is a COMPLETE recovery surface for every witness record";
exit non-zero means "here are the records you must recover by hand."

WHAT THIS IS NOT.  It is not a second drain and it moves no cursor.  Drainage is
``dev/journal_consume.py``'s job (``pending`` lists undrained receipts;
``consume`` advances).  Coverage — "does the journal HAVE everything the human
submitted?" — is THIS tool's job, and it is the half the cursor can never
answer about itself.  A post-compaction coordinator runs BOTH: ``reconcile`` to
prove the journal is complete, then ``pending``/``consume`` to drain it.

READ-ONLY DISCIPLINE.  No cursor is advanced, no file is written.  The
all-receipts read uses a dedicated never-advanced consumer (``reconcile-audit``)
so ``events_since_cursor`` returns every ``receipt.created`` event from the
chain origin — the public projection, no new journal query, no ``user_events/``
change.

MATCHING KEY.  ``submissions.log`` carries no receipt id (it predates the
journal and survives the step that would parse one).  A witness record is
matched to a receipt by ROUTE + BODY: the receipt's ``exact_payload_bytes`` is
the same ``self._body`` the witness saw in the same ``do_POST`` call, so for a
covered record ``json.loads(receipt.exact_payload_bytes) == witness["req"]`` holds
exactly.  Comparison is on the PARSED value (order-independent for objects,
order-sensitive for arrays — correct for JSON), and falls back to the decoded
string for non-JSON bodies (``raw``).  Matching is one-to-one (a duplicate
identical submission consumes two receipts, two witness lines), so counts are
honest.

USAGE
  python3 dev/reconcile_submissions.py [--journal PATH] [--submissions PATH]

EXIT CODES  EX_OK (0) — fully covered; EX_SOFTWARE (70) — coverage gap present;
EX_USAGE (64) — bad arguments.  Read-only: never writes, never advances.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# `user_events/` is a package at the repo root; this module lives in `dev/`.
# Add the root so `from user_events.sqlite import open_journal` works when run
# as `python3 dev/reconcile_submissions.py` (sys.path[0] is then `dev/`, not cwd).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from user_events.sqlite import open_journal  # noqa: E402  — the public API

# The consumer whose drain-completeness matters for #260: the coordinator.  Its
# cursor ordinal splits matched receipts into DRAINED (cursor past them) and
# PENDING (cursor not yet past them — the live #260 signal).  The literal the
# cursor row is keyed by, identical to ``dev/journal_consume.py``'s CONSUMER.
CONSUMER = "coordinator"

# A dedicated never-advanced consumer for the all-receipts read.  Its cursor
# stays at the chain origin (0), so ``events_since_cursor`` returns every
# ``receipt.created`` event — the public projection used as a full index, with
# no new journal query and no cursor movement.  It is never consumed, so it
# never advances; two runs see the same full set.
AUDIT_CONSUMER = "reconcile-audit"

JOURNAL_DEFAULT = ".dreamwork/user-events.sqlite3"
SUBMISSIONS_DEFAULT = ".dreamwork/submissions.log"

# The registered write routes — every one commits a receipt before dispatch
# (the E3 cutover).  Sourced from ``watch.WRITE_ROUTE_HANDLERS`` (a class
# attribute, so not importable at module level without constructing the
# handler).  A drift-guard test (``test_submission_routes_match_watch``) builds
# the handler and asserts this set equals ``WRITE_ROUTE_HANDLERS`` exactly, so a
# route added to watch fails that test here until this constant is updated.
SUBMISSION_ROUTES = frozenset({
    "/answer", "/ask", "/comment", "/command", "/decide",
    "/tint", "/run-mode", "/posture", "/deploy", "/remind",
    "/chat-reply", "/chat-archive",
})

# Stable exit codes (asserted by the test).  EX_OK: fully covered; EX_SOFTWARE:
# a coverage gap is present (a data-integrity event — the witness holds a
# submission the journal cannot reach); EX_USAGE: bad arguments.
EX_OK = 0
EX_USAGE = 64
EX_SOFTWARE = 70

_PREVIEW_LIMIT = 80


def _preview(text: str) -> str:
    """A single-line, length-honest preview of a body (#126 collapse rule).

    The output is line-oriented and read by an agent; a newline in the human's
    text must not forge a second line.  Whitespace (incl. newlines) is collapsed
    to single spaces; over-length is marked with ``…``.
    """
    oneline = " ".join((text or "").split())
    if len(oneline) > _PREVIEW_LIMIT:
        oneline = oneline[:_PREVIEW_LIMIT] + "…"
    return oneline


def _canon(value) -> str:
    """A canonical, hashable string for a parsed JSON value.

    ``sort_keys`` + tight separators make equal JSON values produce identical
    strings regardless of key order, so a witness record and its receipt (both
    parsed from the SAME ``do_POST`` body bytes) canonicalize alike.  This is
    safe BY CONSTRUCTION here: the witness ``req`` is ``json.loads(body)`` and
    the receipt's ``exact_payload_bytes`` IS that same ``body``, so the two
    parse to byte-identical objects — canonical dumps of identical objects are
    identical, with no float/int or ordering edge to bridge.
    """
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def _submission_body_key(rec: dict):
    """The hashable match key for a witness record's body, or ``None``.

    ``("json", canonical)`` when the record carries ``req`` (the body parsed as
    JSON); ``("raw", decoded_string)`` when it carries ``raw`` (a body that did
    not parse).  The shape mirrors ``_receipt_body_key`` so a covered record
    compares equal to its receipt.
    """
    if "req" in rec:
        return ("json", _canon(rec["req"]))
    if "raw" in rec:
        return ("raw", rec["raw"])
    return None


def _receipt_body_key(payload: bytes):
    """The hashable match key for a receipt's exact payload bytes.

    Parses the payload as JSON when it can (mirroring ``log_submission``'s
    ``json.loads``) and canonicalizes; falls back to the UTF-8-decoded string
    with ``replace`` (mirroring ``log_submission``'s ``body.decode("utf-8",
    "replace")``).  A covered record's payload is the SAME bytes the witness
    saw, so the two keys agree.
    """
    try:
        return ("json", _canon(json.loads(payload.decode("utf-8"))))
    except (UnicodeDecodeError, ValueError):
        return ("raw", payload.decode("utf-8", "replace"))


def _iter_submissions(path: Path):
    """Yield ``(lineno, rec_or_None)`` for each non-blank line of the witness.

    A line that is not a JSON object yields ``(lineno, None)`` — reported as a
    malformed line rather than crashing the audit (the witness is append-only
    and an agent may read it partway through a write; a half-line must not abort
    the proof).  ``log_submission`` always writes one JSON object per line, so a
    ``None`` is itself a finding.
    """
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                yield lineno, None
                continue
            if not isinstance(rec, dict):
                yield lineno, None
                continue
            yield lineno, rec


def cmd_reconcile(args, out, err) -> int:
    """Read-only witness audit: prove the journal covers every submission.

    Never writes, never advances a cursor.  Classifies each ``submissions.log``
    record into:

      DRAINED      — matched a receipt whose ``receipt.created`` ordinal is at
                     or below the coordinator cursor (already drained).
      PENDING      — matched a receipt ABOVE the coordinator cursor (drainable
                     next tick — the live #260 signal; ``pending`` lists these).
      UNJOURNALED  — no receipt, by construction: ``truncated`` (over the cap,
                     refused 413 pre-receipt) or ``unknown-route`` (a POST path
                     not in ``WRITE_ROUTE_HANDLERS``, 404'd pre-receipt).
      UNMATCHED    — no receipt but the route IS registered and the body was not
                     truncated: an integrity anomaly (the journal should have
                     it).  Also covers a malformed witness line.

    Exit EX_OK iff every witness record is COVERED (DRAINED or PENDING — both
    map to a receipt, so the cursor is a complete recovery surface).  Any
    UNJOURNALED or UNMATCHED record is a coverage gap the cursor cannot reach →
    EX_SOFTWARE.  PENDING does NOT fail the gate: drainage is
    ``dev/journal_consume.py``'s job, and this tool's gate is coverage, not
    drainage (the two responsibilities are kept non-overlapping on purpose).
    """
    journal_path = Path(args.journal)
    subs_path = Path(args.submissions)

    # No witness → nothing to prove: trivially covered.
    if not subs_path.exists():
        out.write("reconcile: no submissions to reconcile\n")
        return EX_OK

    # Build the full receipt index.  An absent journal means the cursor can
    # cover NOTHING — every witness record is a coverage gap.  Reported as
    # UNJOURNALED:no-journal so the cause is named, not inferred.
    if not journal_path.exists():
        records = list(_iter_submissions(subs_path))
        out.write(
            f"reconcile: {len(records)} submission(s), 0 covered, "
            f"{len(records)} unjournaled (journal absent)\n"
        )
        for lineno, rec in records:
            path = rec.get("path", "?") if rec else "?"
            out.write(f"UNJOURNALED\tno-journal\t{path}\tline {lineno}\n")
        return EX_SOFTWARE if records else EX_OK

    with open_journal(journal_path) as j:
        # ALL receipts, via the never-advanced audit consumer (cursor 0 → every
        # receipt.created event).  Read-only: no advance, no write.
        receipts = j.events_since_cursor(AUDIT_CONSUMER)
        # The coordinator cursor ordinal: whose drain-completeness splits
        # matched receipts into DRAINED vs PENDING.  Read-only.
        cursor_ord = j.cursor(CONSUMER).scanned_through_event_ordinal

    # One-to-one match pool: (route, body_key) → list of (receipt_id, ordinal),
    # consumed left-to-right so duplicate identical submissions each take one.
    pool: dict[tuple, list[tuple]] = {}
    for ev in receipts:
        key = (ev.route, _receipt_body_key(ev.exact_payload_bytes))
        pool.setdefault(key, []).append((ev.receipt_id, ev.ordinal))

    drained = pending = unjournaled = unmatched = 0
    rows: list[tuple] = []  # (verb, rid_or_cause, path, preview)
    for lineno, rec in _iter_submissions(subs_path):
        if rec is None:
            unmatched += 1
            rows.append(("UNMATCHED", "malformed-line", "?", f"line {lineno}"))
            continue
        path = rec.get("path", "?")
        preview_src = rec.get("req")
        if preview_src is None:
            preview_src = rec.get("raw", "")
        preview = _preview(json.dumps(preview_src, ensure_ascii=False)
                           if not isinstance(preview_src, str)
                           else preview_src)
        body_key = _submission_body_key(rec)
        cand = pool.get((path, body_key)) if body_key is not None else None
        if cand:
            rid, ord_ = cand.pop(0)
            if not cand:
                del pool[(path, body_key)]
            if ord_ <= cursor_ord:
                drained += 1
                rows.append(("DRAINED", rid, path, preview))
            else:
                pending += 1
                rows.append(("PENDING", rid, path, preview))
            continue
        # No matching receipt.  Name the cause from the record itself.
        if rec.get("truncated"):
            unjournaled += 1
            rows.append(("UNJOURNALED", "truncated", path, preview))
        elif path not in SUBMISSION_ROUTES:
            unjournaled += 1
            rows.append(("UNJOURNALED", "unknown-route", path, preview))
        else:
            # Registered route, not truncated, yet no receipt: the journal
            # should have captured it.  An integrity anomaly, not by-design.
            unmatched += 1
            rows.append(("UNMATCHED", "no-receipt", path, preview))

    covered = drained + pending
    total = covered + unjournaled + unmatched
    out.write(
        f"reconcile: {total} submission(s), {covered} covered "
        f"({drained} drained, {pending} pending), {unjournaled} unjournaled, "
        f"{unmatched} unmatched\n"
    )
    for verb, cause_or_rid, path, preview in rows:
        if verb == "DRAINED":
            out.write(f"DRAINED\t{cause_or_rid}\t{path}\t{preview}\n")
        elif verb == "PENDING":
            out.write(f"PENDING\t{cause_or_rid}\t{path}\t{preview}\n")
        elif verb == "UNJOURNALED":
            out.write(f"UNJOURNALED\t{cause_or_rid}\t{path}\t{preview}\n")
        else:  # UNMATCHED
            out.write(f"UNMATCHED\t{cause_or_rid}\t{path}\t{preview}\n")

    gap = unjournaled + unmatched
    return EX_OK if gap == 0 else EX_SOFTWARE


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dev/reconcile_submissions.py",
        description=(
            "Witness audit for #260: prove the journal covers every "
            "submission in submissions.log, so a post-compaction coordinator "
            "can prove 'no missed messages' instead of guessing a cutoff."
        ),
    )
    p.add_argument(
        "--journal", default=JOURNAL_DEFAULT,
        help="journal db path (default: %(default)s)",
    )
    p.add_argument(
        "--submissions", default=SUBMISSIONS_DEFAULT,
        help="submissions.log path (default: %(default)s)",
    )
    return p


def main(argv=None, out=None, err=None) -> int:
    """Run the audit. Returns a stable exit code; never raises SystemExit."""
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
    return cmd_reconcile(args, out, err)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
