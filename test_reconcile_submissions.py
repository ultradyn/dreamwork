#!/usr/bin/env python3
"""Red-first tests for dev/reconcile_submissions.py — the #260 witness audit.

The audit is a READ-ONLY cross-check of ``submissions.log`` (the verbatim
witness, #199) against the journal's receipts, proving every submission either
maps to a receipt (covered — drained or drainable) or is named as a record the
cursor can never reach (truncated / unknown-route / unmatched).  These tests do
NOT re-prove the journal's receipt/cursor mechanics (test_user_events_sqlite.py
/ test_journal_consume.py do); they prove the audit COMPOSES them correctly and
classifies each witness record by the right cause.

FIXTURE DISCIPLINE.  Receipts are seeded through the PRODUCTION ``receive()``
path; witness lines are written through the PRODUCTION ``watch.log_submission``
(so the shape is exactly what ``do_POST`` writes, never a hand-built lookalike).
The expected DRAINED/PENDING/UNJOURNALED sets are DERIVED at runtime from the
seed (receipt ids) and the cursor ordinal positioned via the production
``advance_cursor`` CAS — never a literal tuned to today's fixture, and never by
calling the audit's own matching logic to build the expectation (that would make
the test hollow: reverting the matcher would change nothing it could see).

The ordinal→receipt map the cursor split depends on is derived from the journal
projection (``events_since_cursor``) and its precondition ASSERTED — the
projection must return exactly the seeded receipts as a 1..n ordinal bijection,
or the test fails here, not in the audit.

RED-PROOF DISCIPLINE.  Each binding check names the production line whose
breakage must fail it.  Each is RUN: the file is snapshotted to scratch
(``cp f $SCRATCH/bak``), the named line is sabotaged, the test is watched to
FAIL, then the file is restored byte-identical (``cp $SCRATCH/bak f``) — never
``git checkout`` (lessons.md #348/#349: a whole-file revert can reach work the
snapshot cannot, and the work under test is committed first so the restore is
bounded to the file injected into).
"""
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path

import watch
from user_events.sqlite import Envelope, open_journal

REPO = Path(__file__).resolve().parent
CLI_PATH = REPO / "dev" / "reconcile_submissions.py"
CONSUMER = "coordinator"          # whose cursor the audit reads (drain completeness)
AUDIT_CONSUMER = "reconcile-audit"  # the never-advanced consumer the audit reads all receipts under


def _load_cli():
    """Load dev/reconcile_submissions.py as a module (it lives in dev/, not root)."""
    loader = importlib.machinery.SourceFileLoader("reconcile_submissions", str(CLI_PATH))
    spec = importlib.util.spec_from_loader("reconcile_submissions", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _uuid(i: int) -> str:
    """A distinct, well-formed UUIDv4 for deterministic seeding."""
    return f"00000000-0000-4000-8000-{i:012d}"


def _seed(path: Path, specs: list[tuple[str, bytes]]):
    """Seed one receipt per (route, body) via the PRODUCTION receive() path.

    Returns the receive() results (whose ``receipt_id`` is ground truth).
    Asserts the precondition that the journal ended with exactly as many
    receipt.created events as specs (derived from head_ordinal, never assumed).
    """
    results = []
    with open_journal(path) as j:
        assert j.head_ordinal() == 0, "precondition: a fresh journal is empty"
        for i, (route, body) in enumerate(specs):
            r = j.receive(
                Envelope(
                    client_action_id=_uuid(i),
                    protocol_version="1",
                    method="POST",
                    route=route,
                    content_type="application/json",
                    body=body,
                )
            )
            assert r.kind == "inserted", f"spec {i} did not insert: {r.kind}"
            results.append(r)
        n = j.head_ordinal()
        assert n == len(specs), (
            f"precondition: head_ordinal {n} must equal the {len(specs)} seeded "
            "specs — a seed that dropped/duplicated an event must fail here"
        )
    return results


def _ordinal_map(path: Path) -> dict[str, int]:
    """{receipt_id: event_ordinal} for every receipt, derived from the journal.

    Ground truth for the cursor split.  Asserts the precondition the split
    depends on: the projection returns exactly the seeded receipts as a 1..n
    ordinal bijection — so a seed that mis-ordered or dropped an ordinal fails
    here, not in the audit's classification.
    """
    with open_journal(path) as j:
        events = j.events_since_cursor(AUDIT_CONSUMER)
    ords = sorted(ev.ordinal for ev in events)
    assert ords == list(range(1, len(events) + 1)), (
        f"precondition: ordinals must be a 1..{len(events)} bijection, got {ords}"
    )
    return {ev.receipt_id: ev.ordinal for ev in events}


def _advance_to(path: Path, ordinal: int) -> None:
    """Position the coordinator cursor at ``ordinal`` via the production CAS.

    ``expected`` is the verified chain hash at ``ordinal`` (the same source
    ``advance_cursor`` itself uses — ``verify_chain(...).head_hash``), so this
    is the real advance path, not a hand-set row.  Asserts it actually advanced.
    """
    with open_journal(path) as j:
        expected = j.verify_chain(through_ordinal=ordinal).head_hash
        res = j.advance_cursor(CONSUMER, expected=expected, scanned_through=ordinal)
    assert res.kind == "advanced", f"cursor did not advance to {ordinal}: {res.kind}"


def _witness(target: Path, path: str, body: bytes, *, nbytes: int = None,
             truncated: bool = False) -> bool:
    """Write ONE witness line through PRODUCTION ``watch.log_submission``.

    The body is JSON so ``log_submission`` stores it parsed (``req``) — the
    shape ``do_POST`` writes, not a hand-built lookalike.  ``target`` must have
    a ``.dreamwork/`` dir (created by the caller).  Returns whether the line
    wrote (the production contract).
    """
    if nbytes is None:
        nbytes = len(body)
    return watch.log_submission(str(target), path, body, nbytes, truncated=truncated)


def _run(cli, argv):
    """Call the CLI's main with captured streams; return (code, out, err)."""
    out = io.StringIO()
    err = io.StringIO()
    code = cli.main(argv, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def _ids_for_verb(text: str, verb: str) -> list[str]:
    """The receipt id (2nd tab-field) of each ``<verb>`` line, in order.

    A line is ``<verb>\\t<id>\\t<path>\\t<preview>`` (DRAINED/PENDING) or
    ``<verb>\\t<cause>\\t<path>\\t<preview>`` (UNJOURNALED/UNMATCHED).  Derived
    from the line shape the CLI emits, never assumed.
    """
    ids = []
    for line in text.splitlines():
        if line.startswith(verb + "\t"):
            ids.append(line.split("\t")[1])
    return ids


def _causes_for_verb(text: str, verb: str) -> list[str]:
    """The cause (2nd tab-field) of each ``UNJOURNALED``/``UNMATCHED`` line."""
    out = []
    for line in text.splitlines():
        if line.startswith(verb + "\t"):
            out.append(line.split("\t")[1])
    return out


# ---------------------------------------------------------------------------
# 0 — drift guard: SUBMISSION_ROUTES equals watch.WRITE_ROUTE_HANDLERS
# ---------------------------------------------------------------------------

def test_submission_routes_match_watch(tmp_path: Path):
    """The audit's route set must equal watch's WRITE_ROUTE_HANDLERS exactly.

    A route added to watch must fail here until the audit's constant is updated,
    or the audit would misclassify the new route's receipts as unknown-route.

    RED LINE (run): drop a route from SUBMISSION_ROUTES (or add a bogus one).
      The set comparison fails. Production line: the SUBMISSION_ROUTES constant
      in dev/reconcile_submissions.py; binds to watch.WRITE_ROUTE_HANDLERS.
    """
    cli = _load_cli()
    handler_cls = watch.make_handler(str(tmp_path))
    expected = set(handler_cls.WRITE_ROUTE_HANDLERS)
    assert expected == set(cli.SUBMISSION_ROUTES), (
        f"SUBMISSION_ROUTES drifted from WRITE_ROUTE_HANDLERS: "
        f"{set(cli.SUBMISSION_ROUTES)} != {expected}"
    )
    # Precondition: the guard means something — there must be >1 route.
    assert len(expected) >= 5, "precondition: a non-trivial route set"


# ---------------------------------------------------------------------------
# 1 — the incident: cursor mid-stream, recovery enumerates exactly the later
#     records (none earlier, none missed), plus the cursor-unreachable ones
# ---------------------------------------------------------------------------

def test_reconcile_incident_midstream(tmp_path: Path):
    """THE #260 fixture: a witness + journal, cursor positioned mid-stream.

    Recovery must enumerate exactly: the covered receipts SPLIT by the cursor
    (DRAINED at/below it, PENDING above it — none missed, none earlier), and the
    cursor-unreachable records (a truncated body and an unknown route).  Every
    expected set is derived from the seed + the positioned cursor, never literal.

    RED LINE (run): flip the cursor comparison (e.g. ``ord_ < cursor_ord``
      instead of ``<=``). The record at the cursor ordinal flips DRAINED↔PENDING
      and the derived-set equality fails. Production line: the
      ``if ord_ <= cursor_ord`` branch in cmd_reconcile.
    """
    cli = _load_cli()
    journal = tmp_path / "je.sqlite3"
    target = tmp_path / "proj"
    (target / ".dreamwork").mkdir(parents=True)
    subs = target / ".dreamwork" / "submissions.log"

    # Seeded receipts, each paired with a witness line (the pairing is the
    # ground truth — the audit must re-derive it by route+body matching).
    specs = [
        ("/answer", b'{"text":"a1"}'),
        ("/ask", b'{"q":"q1"}'),
        ("/comment", b'{"text":"c1"}'),
        ("/tint", b'{"tint":"blue"}'),
    ]
    seeded = _seed(journal, specs)
    seeded_ids = [r.receipt_id for r in seeded]
    ordmap = _ordinal_map(journal)  # {rid: ordinal}, precondition-asserted

    # Witness lines for the COVERED submissions (production shape).
    for route, body in specs:
        assert _witness(target, route, body), f"witness write failed for {route}"
    # Cursor-unreachable records (no receipt, by construction).
    assert _witness(target, "/answer", b'{"text":"BIG"}',
                    nbytes=watch.MAX_BODY + 1, truncated=True), "truncated witness"
    assert _witness(target, "/bogus", b'{"x":1}'), "unknown-route witness"

    # Position the cursor mid-stream (between ord 2 and 3): r1,r2 DRAINED; r3,r4 PENDING.
    cursor_ord = 2
    _advance_to(journal, cursor_ord)

    code, out, err = _run(cli, ["--journal", str(journal), "--submissions", str(subs)])

    # Exit non-zero: two cursor-unreachable records are a coverage gap.
    assert code == cli.EX_SOFTWARE, (
        f"a coverage gap must exit EX_SOFTWARE, got {code} (out={out!r})"
    )
    # DRAINED = receipts at/below the cursor; PENDING = above it.  Derived.
    drained_expected = sorted(rid for rid in seeded_ids if ordmap[rid] <= cursor_ord)
    pending_expected = sorted(rid for rid in seeded_ids if ordmap[rid] > cursor_ord)
    # Precondition the split depends on: both buckets are non-empty (else the
    # comparison is vacuous and a flipped comparator could pass).
    assert drained_expected and pending_expected, (
        "precondition: cursor must split the seeded set into two non-empty halves"
    )
    drained_got = sorted(_ids_for_verb(out, "DRAINED"))
    pending_got = sorted(_ids_for_verb(out, "PENDING"))
    assert drained_got == drained_expected, (
        f"DRAINED must be exactly the at/below-cursor receipts: "
        f"{drained_got} != {drained_expected}"
    )
    assert pending_got == pending_expected, (
        f"PENDING must be exactly the above-cursor receipts: "
        f"{pending_got} != {pending_expected}"
    )
    # Cursor-unreachable: one truncated, one unknown-route — causes named.
    causes = sorted(_causes_for_verb(out, "UNJOURNALED"))
    assert causes == ["truncated", "unknown-route"], (
        f"unjournaled causes must be truncated + unknown-route, got {causes}"
    )
    # The summary line states the counts honestly.
    assert "4 covered (2 drained, 2 pending)" in out, f"summary wrong: {out!r}"
    assert "2 unjournaled" in out and "0 unmatched" in out, f"summary wrong: {out!r}"


# ---------------------------------------------------------------------------
# 2 — a truncated body is UNJOURNALED:truncated (no receipt by design)
# ---------------------------------------------------------------------------

def test_reconcile_truncated_is_unjournaled(tmp_path: Path):
    """A body over the cap is refused 413 pre-receipt → UNJOURNALED:truncated.

    RED LINE (run): delete the ``if rec.get("truncated")`` branch. The record
      falls through to unknown-route (path is registered) then to UNMATCHED, so
      the cause is no longer "truncated" and this fails. Production line: the
      ``if rec.get("truncated")`` branch in cmd_reconcile.
    """
    cli = _load_cli()
    journal = tmp_path / "je.sqlite3"
    target = tmp_path / "proj"
    (target / ".dreamwork").mkdir(parents=True)
    subs = target / ".dreamwork" / "submissions.log"

    _seed(journal, [("/answer", b'{"text":"ok"}')])  # one receipt, for a covered line
    assert _witness(target, "/answer", b'{"text":"ok"}'), "covered witness"
    assert _witness(target, "/answer", b'{"text":"BIG"}',
                    nbytes=watch.MAX_BODY + 1, truncated=True), "truncated witness"

    code, out, err = _run(cli, ["--journal", str(journal), "--submissions", str(subs)])
    assert code == cli.EX_SOFTWARE, "a truncated record is a coverage gap"
    assert _causes_for_verb(out, "UNJOURNALED") == ["truncated"], (
        f"truncated record must be UNJOURNALED:truncated, got {out!r}"
    )
    assert "0 unmatched" in out, f"a truncated record is not unmatched: {out!r}"


# ---------------------------------------------------------------------------
# 3 — an unknown POST path is UNJOURNALED:unknown-route (no receipt by design)
# ---------------------------------------------------------------------------

def test_reconcile_unknown_route_is_unjournaled(tmp_path: Path):
    """A POST path not in WRITE_ROUTE_HANDLERS is 404'd pre-receipt.

    RED LINE (run): delete the ``elif path not in SUBMISSION_ROUTES`` branch.
      The record falls through to UNMATCHED, so the cause is no longer
      "unknown-route" and this fails. Production line: that elif branch.
    """
    cli = _load_cli()
    journal = tmp_path / "je.sqlite3"
    target = tmp_path / "proj"
    (target / ".dreamwork").mkdir(parents=True)
    subs = target / ".dreamwork" / "submissions.log"

    # A journal MUST exist for the unknown-route classification to run: with no
    # journal the audit (correctly) reports every record UNJOURNALED:no-journal
    # instead.  Seed one covered receipt + witness so the journal is live, then
    # add the unknown-route record the test is about.
    _seed(journal, [("/answer", b'{"text":"ok"}')])
    assert _witness(target, "/answer", b'{"text":"ok"}'), "covered witness"
    assert _witness(target, "/totally-bogus", b'{"x":1}'), "unknown-route witness"

    code, out, err = _run(cli, ["--journal", str(journal), "--submissions", str(subs)])
    assert code == cli.EX_SOFTWARE, "an unknown-route record is a coverage gap"
    assert _causes_for_verb(out, "UNJOURNALED") == ["unknown-route"], (
        f"unknown route must be UNJOURNALED:unknown-route, got {out!r}"
    )


# ---------------------------------------------------------------------------
# 4 — absent journal: every witness record is a coverage gap (named)
# ---------------------------------------------------------------------------

def test_reconcile_no_journal_all_unjournaled(tmp_path: Path):
    """No journal ⇒ the cursor can cover nothing ⇒ every record UNJOURNALED.

    RED LINE (run): make the absent-journal path exit EX_OK (claim coverage).
      The exit-code assertion fails. Production line: the
      ``return EX_SOFTWARE if records else EX_OK`` in the no-journal branch.
    """
    cli = _load_cli()
    target = tmp_path / "proj"
    (target / ".dreamwork").mkdir(parents=True)
    subs = target / ".dreamwork" / "submissions.log"
    assert _witness(target, "/answer", b'{"text":"a"}'), "witness"
    journal = tmp_path / "absent.sqlite3"
    assert not Path(journal).exists(), "precondition: journal genuinely absent"

    code, out, err = _run(cli, ["--journal", str(journal), "--submissions", str(subs)])
    assert code == cli.EX_SOFTWARE, "absent journal with witness records is a gap"
    assert _causes_for_verb(out, "UNJOURNALED") == ["no-journal"], (
        f"absent-journal records must be UNJOURNALED:no-journal, got {out!r}"
    )


# ---------------------------------------------------------------------------
# 5 — absent witness: trivially covered (nothing to prove)
# ---------------------------------------------------------------------------

def test_reconcile_no_submissions_trivially_covered(tmp_path: Path):
    """No submissions.log ⇒ nothing to prove ⇒ exit 0.

    RED LINE (run): make the no-witness path exit non-zero. The exit assertion
      fails. Production line: the ``return EX_OK`` in the no-witness branch.
    """
    cli = _load_cli()
    journal = tmp_path / "je.sqlite3"
    _seed(journal, [("/answer", b'{"text":"a"}')])  # journal exists, no witness
    subs = tmp_path / "nope.log"
    assert not subs.exists(), "precondition: witness genuinely absent"

    code, out, err = _run(cli, ["--journal", str(journal), "--submissions", str(subs)])
    assert code == cli.EX_OK, "no witness ⇒ trivially covered"
    assert "no submissions to reconcile" in out, out


# ---------------------------------------------------------------------------
# 6 — fully covered (cursor at head): exit 0; PENDING does NOT fail the gate
# ---------------------------------------------------------------------------

def test_reconcile_fully_covered_exit_zero(tmp_path: Path):
    """All witness records map to a receipt ⇒ exit 0, even with PENDING ones.

    PENDING (matched receipt, cursor not yet advanced) is NOT a coverage gap —
    drainage is dev/journal_consume.py's job.  The gate is coverage only.

    RED LINE (run): make the gap gate count PENDING (``gap = unjournaled +
      unmatched + pending``). With a PENDING receipt present, the exit flips to
      EX_SOFTWARE and this fails. Production line: the
      ``gap = unjournaled + unmatched`` / ``return EX_OK if gap == 0`` gate.
    """
    cli = _load_cli()
    journal = tmp_path / "je.sqlite3"
    target = tmp_path / "proj"
    (target / ".dreamwork").mkdir(parents=True)
    subs = target / ".dreamwork" / "submissions.log"

    specs = [("/answer", b'{"text":"a"}'), ("/ask", b'{"q":1}')]
    _seed(journal, specs)
    for route, body in specs:
        assert _witness(target, route, body), f"witness {route}"
    # Cursor left at 0 ⇒ BOTH receipts are PENDING (above the cursor).
    ordmap = _ordinal_map(journal)
    pending_expected = sorted(ordmap)  # all seeded ids (cursor at 0)

    code, out, err = _run(cli, ["--journal", str(journal), "--submissions", str(subs)])
    assert code == cli.EX_OK, (
        f"fully covered must exit 0 even when all are PENDING; got {code} (out={out!r})"
    )
    assert sorted(_ids_for_verb(out, "PENDING")) == pending_expected, (
        f"both receipts must be PENDING under a 0 cursor: {out!r}"
    )
    assert "0 unjournaled" in out and "0 unmatched" in out, out


# ---------------------------------------------------------------------------
# 7 — matching is by ROUTE + BODY (one-to-one), not route alone
# ---------------------------------------------------------------------------

def test_reconcile_matches_by_route_and_body(tmp_path: Path):
    """Two same-route receipts with different bodies match their own witness.

    Guards against a matcher that keys on route alone (which would let one
    receipt stand in for another and mis-split DRAINED/PENDING).  One-to-one: a
    duplicate identical body consumes two receipts for two witness lines.

    RED LINE (run): make _receipt_body_key / _submission_body_key ignore the
      body (key on route only). The two distinct bodies collapse onto the first
      receipt and the second witness line becomes UNMATCHED → exit non-zero and
      the DRAINED id set is wrong. Production lines: _submission_body_key and
      _receipt_body_key (the body half of the match key).
    """
    cli = _load_cli()
    journal = tmp_path / "je.sqlite3"
    target = tmp_path / "proj"
    (target / ".dreamwork").mkdir(parents=True)
    subs = target / ".dreamwork" / "submissions.log"

    specs = [("/answer", b'{"text":"first"}'), ("/answer", b'{"text":"second"}')]
    seeded = _seed(journal, specs)
    seeded_ids = [r.receipt_id for r in seeded]
    for route, body in specs:
        assert _witness(target, route, body), f"witness {body!r}"
    _advance_to(journal, 2)  # cursor at head ⇒ both DRAINED

    code, out, err = _run(cli, ["--journal", str(journal), "--submissions", str(subs)])
    assert code == cli.EX_OK, f"both distinct bodies must match: {out!r}"
    drained = sorted(_ids_for_verb(out, "DRAINED"))
    assert drained == sorted(seeded_ids), (
        f"both receipts must be matched one-to-one by route+body: {drained} != "
        f"{sorted(seeded_ids)}"
    )
    assert "0 unmatched" in out, out
