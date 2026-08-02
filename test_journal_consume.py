#!/usr/bin/env python3
"""Red-first tests for dev/journal_consume.py — the tick-consume CLI (#501).

The CLI is a thin composition over two ALREADY-LANDED public methods in
``user_events/sqlite.py``: ``Journal.events_since_cursor`` (the read
projection) and ``Journal.advance_cursor`` (the verifying CAS).  These tests
do NOT re-prove those methods (that is test_user_events_sqlite.py's job, e.g.
the B6 ``expected == stored_chain_hash`` red line); they prove the CLI
COMPOSES them correctly — the five behaviours the brief names.

Named production lines whose breakage must fail each test are in each
docstring, and each is RUN: the injection is made, the test watched fail, then
the file restored byte-identical with ``cp`` (never ``git checkout`` — the
work under test is committed first, so a snapshot/restore cannot reach anything
but the file injected into; lessons.md #348/#349).

No hand-built event list: the journal is seeded through the PRODUCTION path
(``open_journal`` + ``receive``), and the expected receipt-id set / count is
derived from the SEED and from ``head_ordinal`` / ``receipt_count`` — never
from ``events_since_cursor`` itself.  Building the expected list by calling the
same projection the CLI calls would be the hollow trap (reverting the
projection would change nothing the test could see), so it is not done.

The five behaviours:
  1. pending is quiet on empty (prints nothing, exit 0).
  2. pending lists exactly the events in (cursor, head].
  3. pending does NOT advance (two runs see the same events; cursor unmoved).
  4. consume advances; a second pending is empty.
  5. consume refuses non-zero on verification failure, cursor unmoved.
"""
import importlib.machinery
import importlib.util
import io
import sqlite3
from pathlib import Path

from user_events.sqlite import Envelope, open_journal, open_journal_readonly

REPO = Path(__file__).resolve().parent
CLI_PATH = REPO / "dev" / "journal_consume.py"
CONSUMER = "coordinator"  # the literal the CLI and the cursor row agree on


def _load_cli():
    """Load dev/journal_consume.py as a module (it lives in dev/, not the root).

    spec_from_file_location works for a .py file; an explicit SourceFileLoader
    mirrors how test_ledger_dispatch.py loads dev/ledger.py.
    """
    loader = importlib.machinery.SourceFileLoader("journal_consume", str(CLI_PATH))
    spec = importlib.util.spec_from_loader("journal_consume", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _uuid(i: int) -> str:
    """A distinct, well-formed UUIDv4 for deterministic seeding."""
    return f"00000000-0000-4000-8000-{i:012d}"


def _seed(path: Path, bodies: list[bytes], *, route: str = "/answer"):
    """Insert one receipt per body via the PRODUCTION receive() path.

    Returns the receive() results (whose ``receipt_id`` is the ground-truth id
    set).  Asserts the precondition that the journal ended with exactly as many
    events as bodies — derived from head_ordinal(), never assumed — so a seed
    that quietly dropped or duplicated an event fails here, not in the CLI
    assertions.
    """
    results = []
    with open_journal(path) as j:
        assert j.head_ordinal() == 0, "precondition: a fresh journal is empty"
        for i, body in enumerate(bodies):
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
            assert r.kind == "inserted", f"row {i} did not insert: {r.kind}"
            results.append(r)
        n = j.head_ordinal()
        assert n == len(bodies), (
            f"precondition: head_ordinal {n} must equal the {len(bodies)} seeded "
            "bodies — a seed that dropped/duplicated an event must fail here"
        )
    return results


def _append_one(path: Path, body: bytes, *, route: str = "/answer", idx: int):
    """Append ONE event to an EXISTING journal via the production receive() path.

    Unlike _seed (which asserts a FRESH/empty journal), this appends to a
    journal that already holds events — the #531 race setup: an event lands
    AFTER a pending read, between the read and the consume.  Asserts the head
    rose by exactly one (derived from head_ordinal() before/after, never
    assumed) so an append that silently no-op'd fails here, not in the CLI
    assertions.
    """
    with open_journal(path) as j:
        before_head = j.head_ordinal()
        r = j.receive(
            Envelope(
                client_action_id=_uuid(idx),
                protocol_version="1",
                method="POST",
                route=route,
                content_type="application/json",
                body=body,
            )
        )
        assert r.kind == "inserted", f"append did not insert: {r.kind}"
        after_head = j.head_ordinal()
        assert after_head == before_head + 1, (
            f"append must raise head {before_head} -> {before_head + 1}; "
            f"got {after_head}"
        )
        return r


def _ord_fields(text: str) -> list[int]:
    """The ``ord=<n>`` field of each non-empty line, in order.

    Both ``pending`` and ``consume``'s event lines carry ``ord=<n>`` (one tab
    field); deriving the ordinal list from the line shape (never assuming the
    value) keeps the assertions honest against a future format drift.
    """
    ords = []
    for line in text.splitlines():
        if not line.strip():
            continue
        for field in line.split("\t"):
            if field.startswith("ord="):
                ords.append(int(field[4:]))
    return ords


def _run(cli, argv):
    """Call the CLI's main with captured streams; return (code, out, err)."""
    out = io.StringIO()
    err = io.StringIO()
    code = cli.main(argv, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def _pending_ids(text: str) -> list[str]:
    """The receipt id (first tab-field) of each non-empty line of pending output."""
    ids = []
    for line in text.splitlines():
        if line.strip():
            ids.append(line.split("\t")[0])
    return ids


def _unapplied_ids(text: str) -> list[str]:
    """The receipt id (2nd tab-field) of each ``UNAPPLIED`` line of consume output.

    A consume line is ``UNAPPLIED\\t<id>\\t<kind>\\t<route>``; the id is the
    second tab-field.  Derived from the line shape the CLI emits, never assumed.
    """
    ids = []
    for line in text.splitlines():
        if line.startswith("UNAPPLIED\t"):
            ids.append(line.split("\t")[1])
    return ids


def _still_unapplied_ids(text: str) -> list[str]:
    """The receipt id (2nd tab-field) of each ``STILL-UNAPPLIED`` line (#619).

    A carried-over line is ``STILL-UNAPPLIED\\t<id>\\t<route>\\tord=<n>``; the
    id is the second tab-field.  Derived from the line shape, never assumed, and
    DISTINCT from the fresh ``UNAPPLIED`` lines so a test can tell a re-reported
    (carried-over) idea from a fresh-this-tick one.
    """
    ids = []
    for line in text.splitlines():
        if line.startswith("STILL-UNAPPLIED\t"):
            ids.append(line.split("\t")[1])
    return ids


def _sidecar_ids(cli, path: Path) -> list[str]:
    """The uncleared ids in the durable sidecar, read via the PRODUCTION helper
    that consume uses (#619 — direction-2 strong).

    Observing the durable state through ``cli._load_unapplied`` (not by trusting
    a consume exit code or output count) is what closes the false-green where a
    receipt 'reports recorded' but wrote to the wrong path: this reads the REAL
    ``<journal>.unapplied`` bound to THIS journal, so a record that landed
    elsewhere is absent here and the test fails.
    """
    with open_journal(path) as j:
        return sorted(e["receipt_id"] for e in cli._load_unapplied(path, j.journal_id))


def _append_transition(path: Path, receipt_id: str) -> int:
    """Append ONE ``receipt.transition`` event via the production transition() path.

    A transition shares the chain's ordinals but carries no envelope, so
    ``events_since_cursor`` does not project it — the exact shape that
    livelocked the drain (#722).  Returns the new head ordinal (derived from
    head_ordinal before/after, never assumed) so the caller can assert the
    transition landed as the head.
    """
    with open_journal(path) as j:
        before = j.head_ordinal()
        rec = j.get_receipt(receipt_id)
        assert rec is not None, "precondition: receipt must exist to transition"
        result = j.transition(
            receipt_id, "validated", expected_revision=rec["revision"],
        )
        assert result.kind == "applied", f"transition did not apply: {result.kind}"
        after = j.head_ordinal()
        assert after == before + 1, (
            f"a transition must raise the head by one ({before} -> {after})")
        return after


# ---------------------------------------------------------------------------
# 1 — pending is quiet on empty (prints nothing, exit 0)
# ---------------------------------------------------------------------------

def test_pending_quiet_on_empty(tmp_path: Path):
    """An empty journal prints nothing and exits 0; so does an absent journal.

    Derives the precondition (the journal genuinely has head 0) rather than
    assuming emptiness.  The quiet contract is that NO output is emitted
    independently of the events — there is no header or summary line.

    RED LINE (run): add a non-event-driven write on the empty path (e.g. a
      ``no events`` summary). stdout becomes non-empty → this asserts
      ``out == ""`` and fails. Production line: the empty-events path returns
      EX_OK without writing (and the absent-journal path likewise).
    """
    cli = _load_cli()
    path = tmp_path / "empty.sqlite3"
    # Create the journal so it exists but holds nothing, and prove it is empty.
    with open_journal(path) as j:
        assert j.head_ordinal() == 0, "precondition: journal must be empty"
        assert j.events_since_cursor(CONSUMER) == []

    code, out, err = _run(cli, ["pending", "--journal", str(path)])
    assert code == 0, f"empty pending must exit 0, got {code} (err={err!r})"
    assert out == "", f"empty pending must print nothing, got {out!r}"

    # An absent journal is also empty — and must NOT be created (read-only).
    absent = tmp_path / "never.sqlite3"
    code, out, err = _run(cli, ["pending", "--journal", str(absent)])
    assert code == 0
    assert out == "", "absent journal must print nothing"
    assert not absent.exists(), (
        "pending must not create an absent journal — it is read-only"
    )


# ---------------------------------------------------------------------------
# 2 — pending lists exactly the events in (cursor, head]
# ---------------------------------------------------------------------------

def test_pending_lists_events_since_cursor(tmp_path: Path):
    """pending lists exactly the seeded events, ordered, receipt id first.

    The expected id set + count come from the SEED (receive() results) and
    head_ordinal — NOT from events_since_cursor (calling the same projection
    the CLI calls would make this hollow: reverting the projection would change
    nothing the test could see).

    RED LINE (run): make the print loop emit nothing (e.g. ``continue`` at the
      top of the loop, or skip the write). pending prints zero lines → the
      ``len(ids) == n`` assertion fails. Production line: the loop body in
      cmd_pending that writes one line per event.
    """
    cli = _load_cli()
    path = tmp_path / "pending.sqlite3"
    bodies = [b'{"text":"answer-0"}', b'{"text":"answer-1"}', b'{"q":2}']
    seeded = _seed(path, bodies)
    n = len(seeded)
    expected_ids = [r.receipt_id for r in seeded]

    code, out, err = _run(cli, ["pending", "--journal", str(path)])
    assert code == 0, f"pending exited {code} (err={err!r})"

    lines = [ln for ln in out.splitlines() if ln.strip()]
    ids = _pending_ids(out)
    assert len(ids) == n, (
        f"pending must list exactly {n} event(s), got {len(ids)}; out={out!r}"
    )
    assert sorted(ids) == sorted(expected_ids), (
        "pending must list exactly the seeded receipt ids"
    )
    # Ordered by ordinal (asc): the lines carry ord=<n>; verify they ascend.
    ords = []
    for ln in lines:
        for field in ln.split("\t"):
            if field.startswith("ord="):
                ords.append(int(field[4:]))
    assert ords == sorted(ords) == list(range(1, n + 1)), (
        f"ordinals must ascend 1..{n}, got {ords}"
    )
    # The route and a payload preview are present on each line.
    for ln, body in zip(lines, bodies):
        assert "/answer" in ln, f"route must appear: {ln!r}"
        assert body.decode("utf-8")[:8] in ln, (
            f"payload preview must appear: {ln!r}"
        )


# ---------------------------------------------------------------------------
# 3 — pending does NOT advance (two runs see the same events; cursor unmoved)
# ---------------------------------------------------------------------------

def test_pending_does_not_advance(tmp_path: Path):
    """Reading is side-effect-free: read twice, same events, cursor unmoved.

    Derives the cursor position before/after from j.cursor() (revision 0 /
    ordinal 0 for a fresh coordinator) and asserts byte-for-byte unchanged.

    RED LINE (run): add a call to advance_cursor inside cmd_pending. The cursor
      moves (revision bumps, ordinal advances) and the SECOND pending sees a
      smaller range → the equality + cursor-unchanged assertions fail.
      Production line: cmd_pending performs no write (no advance_cursor call).
    """
    cli = _load_cli()
    path = tmp_path / "nomove.sqlite3"
    bodies = [b'{"i":0}', b'{"i":1}', b'{"i":2}']
    seeded = _seed(path, bodies)
    n = len(seeded)
    expected_ids = sorted(r.receipt_id for r in seeded)

    with open_journal(path) as j:
        before = j.cursor(CONSUMER)
    assert (before.scanned_through_event_ordinal, before.revision) == (0, 0), (
        "precondition: a fresh coordinator cursor sits at the origin"
    )

    code1, out1, _ = _run(cli, ["pending", "--journal", str(path)])
    assert code1 == 0
    ids1 = sorted(_pending_ids(out1))
    assert ids1 == expected_ids, "first pending must list the seeded events"

    # Cursor must not have moved between the two reads.
    with open_journal(path) as j:
        mid = j.cursor(CONSUMER)
    assert (mid.scanned_through_event_ordinal, mid.revision) == (0, 0), (
        "a read must not move the cursor (got "
        f"ord={mid.scanned_through_event_ordinal} rev={mid.revision})"
    )

    code2, out2, _ = _run(cli, ["pending", "--journal", str(path)])
    assert code2 == 0
    ids2 = sorted(_pending_ids(out2))
    assert ids2 == ids1, (
        "two pending runs with no consume must see the same events"
    )

    with open_journal(path) as j:
        after = j.cursor(CONSUMER)
    assert (after.scanned_through_event_ordinal, after.revision) == (0, 0), (
        "two reads must leave the cursor at the origin"
    )
    assert n >= 2  # precondition: a non-trivial range so "same events" means something


# ---------------------------------------------------------------------------
# 4 — consume advances; a second pending is empty
# ---------------------------------------------------------------------------

def test_consume_advances_then_pending_empty(tmp_path: Path):
    """consume read-then-advances to head; afterwards pending reads nothing.

    #526: a fresh drain (empty applied-ledger) reports every receipt UNAPPLIED
    and writes the applied-ledger; the cursor still advances to head (the proof
    writes the ledger, never the cursor).  The UNAPPLIED list names exactly the
    seeded ids — derived from the SEED, never from the projection the CLI calls.

    RED LINE (run): remove the advance_cursor call from cmd_consume (consume
      reads but never advances). The cursor stays at 0, so the post-consume
      pending is NOT empty → the ``out == ""`` assertion fails. Production line:
      the advance_cursor call in cmd_consume.
    """
    cli = _load_cli()
    path = tmp_path / "consume.sqlite3"
    applied = tmp_path / "applied.md"
    bodies = [b'{"x":0}', b'{"x":1}', b'{"x":2}', b'{"x":3}']
    seeded = _seed(path, bodies)
    n = len(seeded)
    expected_ids = sorted(r.receipt_id for r in seeded)

    code, out, err = _run(cli, ["consume", "--journal", str(path),
                                "--applied", str(applied)])
    assert code == 0, f"consume must exit 0, got {code} (err={err!r})"
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert lines[0] == f"consumed {n} event(s)", (
        f"first line must report the count, got {lines[0]!r}"
    )
    # A fresh applied-ledger ⇒ every receipt proves NOT_APPLIED → all UNAPPLIED.
    assert "applied 0" in out, f"a fresh drain reports 0 applied; got {out!r}"
    assert f"unapplied {n}" in out, (
        f"a fresh drain reports {n} unapplied; got {out!r}")
    unapplied = _unapplied_ids(out)
    assert sorted(unapplied) == expected_ids, (
        "the UNAPPLIED list must name exactly the seeded receipt ids"
    )
    assert applied.exists(), (
        "the proof must have created/written the applied-ledger on the first drain"
    )

    # The cursor advanced to the head; derive head from the journal.
    with open_journal(path) as j:
        head = j.head_ordinal()
        cur = j.cursor(CONSUMER)
    assert head == n, f"precondition: head must equal seeded count {n}, got {head}"
    assert cur.scanned_through_event_ordinal == head, (
        "consume must advance the coordinator cursor to the head"
    )
    assert cur.revision >= 1, "an advance must bump the cursor revision"

    # A second pending is empty — the range (cursor, head] is now empty.
    code, out, _ = _run(cli, ["pending", "--journal", str(path)])
    assert code == 0
    assert out == "", (
        "after consume advances to head, pending must read nothing"
    )


# ---------------------------------------------------------------------------
# 5 — consume refuses non-zero on verification failure, cursor unmoved
# ---------------------------------------------------------------------------

def test_consume_refuses_on_corruption_cursor_unmoved(tmp_path: Path):
    """consume refuses (non-zero) when the chain changed underfoot; cursor stays.

    ATOMICITY GAP (named): the read-then-advance within one consume are two
    API calls, not one transaction — but a CLEAN concurrent append never
    refuses (append-only chain: advance moves only to the snapshot head, newer
    events reappear next tick; nothing lost).  The only refusal reachable is
    an ALTERATION of an already-chained row (corruption/tampering), and NO
    public write API does that.  So the real race is not inducible through the
    public API; this test simulates the corruption with a direct SQL mutation
    and proves consume surfaces the refusal at the seam advance_cursor exposes
    (its bounded rebuild + expected check), leaves the cursor unmoved, and
    exits non-zero.

    RED LINE (run): make cmd_consume swallow the refusal (e.g. treat a refused
      result as success, or force the advance). consume exits 0 → the
      ``code != 0`` assertion fails. Production line: the refusal check in
      cmd_consume that returns EX_SOFTWARE when result.kind != "advanced".
    """
    cli = _load_cli()
    path = tmp_path / "refuse.sqlite3"
    bodies = [b'{"a":0}', b'{"a":1}', b'{"a":2}']
    seeded = _seed(path, bodies)
    n = len(seeded)

    with open_journal(path) as j:
        head = j.head_ordinal()
    assert head == n, "precondition: head must equal the seeded count"

    # Corrupt the head event's canonical_payload (the bytes the chain hashes),
    # so advance_cursor's bounded rebuild recomputes a different hash than the
    # stored event_hash and refuses (chain_broken). This is the "journal
    # changed underfoot" an append-only chain protects against; no public API
    # does it, hence the direct SQL mutation.
    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute(
            "SELECT canonical_payload FROM events WHERE event_ordinal = ?",
            (head,),
        ).fetchone()
        assert row is not None, "precondition: head event row must exist"
        # Alter the payload in a way that cannot hash-collide: prepend a byte.
        corrupted = b"\x00ALTERED" + bytes(row[0])
        conn.execute(
            "UPDATE events SET canonical_payload = ? WHERE event_ordinal = ?",
            (corrupted, head),
        )
        conn.commit()
    finally:
        conn.close()

    # Snapshot the cursor BEFORE consume — it must be unmoved on refusal.
    with open_journal(path) as j:
        before = j.cursor(CONSUMER)
    assert (before.scanned_through_event_ordinal, before.revision) == (0, 0), (
        "precondition: fresh coordinator cursor at the origin"
    )

    code, out, err = _run(cli, ["consume", "--journal", str(path),
                                "--applied", str(tmp_path / "applied.md")])
    assert code != 0, (
        "consume must refuse non-zero when the chain changed underfoot, "
        f"got exit {code} (out={out!r})"
    )
    assert "refused" in err.lower(), (
        f"the refusal message must go to stderr, got err={err!r}"
    )

    # Cursor unmoved: advance_cursor only writes cursors on success.
    with open_journal(path) as j:
        after = j.cursor(CONSUMER)
    assert (after.scanned_through_event_ordinal, after.revision) == (0, 0), (
        "a refused consume must leave the cursor unmoved (got "
        f"ord={after.scanned_through_event_ordinal} rev={after.revision})"
    )
    # And pending still sees the events — the cursor did not advance.
    code, out, _ = _run(cli, ["pending", "--journal", str(path)])
    assert code == 0
    assert len(_pending_ids(out)) == n, (
        "after a refused consume, pending must still list the unconsumed events"
    )


# ---------------------------------------------------------------------------
# #526 — the exactly-once proof wired into the drain.
#
# The audit (#519 F4) found apply's proof was exercised ONLY by tests.  These
# tests prove it is now WIRED: consume routes every drained receipt through its
# adapter's reconcile before advancing, so a replay of an already-applied range
# writes nothing by construction.  Spies/fakes sit at the ADAPTER boundary
# (the brief's named seam); the real proof runs over the real applied-ledger.
# ---------------------------------------------------------------------------

def _rewind_cursor(path: Path) -> None:
    """Delete the coordinator cursor row so (cursor, head] re-drains.

    This simulates a replay (the by-construction test): the same range is
    consumed a second time.  It is a direct SQL mutation of the cursor row only
    — it does not touch the chain (advance_cursor would refuse a mutated chain;
    this keeps the chain intact so the replay verifies, not refuses).
    """
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("DELETE FROM cursors WHERE consumer = ?", (CONSUMER,))
        conn.commit()
    finally:
        conn.close()


class _SpyCommandAdapter:
    """Wraps the real ``/command`` adapter, counting ``append_effect`` calls.

    ``append_effect`` is the adapter's effect WRITE — the boundary the #526
    proof guards.  A replay that proves APPLIED must NOT call it (the count
    stays flat).  ``has_marker`` delegates to the REAL adapter over the REAL
    applied-ledger, so the proof machinery (prove_applied → has_marker) is
    genuinely exercised; the spy only OBSERVES the write, it does not fake the
    verdict (a fake that short-circuits has_marker would not prove the real
    machinery, which is the whole point of wiring it).
    """

    def __init__(self, real):
        self._real = real
        self.route = real.route
        self.writes = 0

    def append_effect(self, text, rid):
        self.writes += 1
        return self._real.append_effect(text, rid)

    def has_marker(self, text, rid):
        return self._real.has_marker(text, rid)


def test_command_receipt_routes_through_reconcile_replay_writes_nothing(tmp_path: Path):
    """#526 (a + d): a drained /command receipt routes through reconcile; the
    adapter writes ONCE on the first drain and ZERO on a replay of the same
    range (the by-construction exactly-once property).

    A spy at the ADAPTER boundary counts append_effect.  First drain: NOT_APPLIED
    → reconcile writes the marker once (spy rises) and lists it UNAPPLIED.
    Rewind the cursor and re-drain: the marker is present → APPLIED → reconcile
    finishes ONLY, append_effect is NOT called (spy flat) and the receipt is NOT
    listed UNAPPLIED.  has_marker delegates to the REAL adapter over the REAL
    applied-ledger, so the proof is exercised, not faked.

    RED LINE (run): delete the APPLIED-no-write branch in reconcile
      (``user_events/apply.py``: ``if proof is Proof.APPLIED: finish(); return
      proof``).  The replayed receipt then falls through to append_effect → the
      spy count rises on the replay → the ``replay wrote nothing`` assertion
      fails. Production line injected: that APPLIED branch in reconcile.
    """
    cli = _load_cli()
    path = tmp_path / "cmd.sqlite3"
    applied = tmp_path / "applied.md"
    seeded = _seed(path, [b'{"kind":"do-now","text":"stand up and check posture"}'],
                   route="/command")
    rid = seeded[0].receipt_id
    n = len(seeded)
    assert n >= 1, "precondition: at least one seeded receipt"

    real = cli.apply.ADAPTERS["/command"]
    spy = _SpyCommandAdapter(real)
    cli.apply.ADAPTERS["/command"] = spy
    try:
        # First drain: the receipt is not yet applied → write once, UNAPPLIED.
        # --force-unapplied (#619) keeps this setup drain out of the uncleared
        # sidecar: this test proves the EXACTLY-ONCE property of the replay,
        # not the #619 carried-over re-report, and a recorded unapplied would
        # make the rewound replay load it as STILL-UNAPPLIED (exit EX_UNAPPLIED)
        # — unrelated to what this test asserts.
        code, out, err = _run(cli, ["consume", "--force-unapplied",
                                    "--journal", str(path),
                                    "--applied", str(applied)])
        assert code == 0, f"first consume exited {code} (err={err!r})"
        assert spy.writes == n, (
            f"first drain must call append_effect once per receipt ({n}); "
            f"spy saw {spy.writes}")
        assert rid in _unapplied_ids(out), (
            f"the not-yet-applied receipt must be listed UNAPPLIED; got {out!r}")
        assert applied.exists(), (
            "precondition: the first drain wrote the applied-ledger (the marker "
            "the replay must find) — without it the replay assertion is vacuous")
        first_writes = spy.writes

        # Rewind the cursor so the SAME range re-drains (a replay).
        _rewind_cursor(path)

        # Replay: the marker is present → APPLIED → write NOTHING.
        code, out, err = _run(cli, ["consume", "--journal", str(path),
                                    "--applied", str(applied)])
        assert code == 0, f"replay consume exited {code} (err={err!r})"
        assert spy.writes == first_writes, (
            f"replay must call append_effect ZERO times (spy {first_writes} -> "
            f"{spy.writes}); an already-applied receipt proves APPLIED and "
            "finishes only — the exactly-once property, by construction")
        assert _unapplied_ids(out) == [], (
            f"an already-applied receipt must NOT be listed UNAPPLIED; got {out!r}")
    finally:
        cli.apply.ADAPTERS["/command"] = real


def test_unapplied_receipts_listed_in_consume_output(tmp_path: Path):
    """#526 (b): receipts not already applied are listed UNAPPLIED in consume's
    output — one line each, ``UNAPPLIED \\t id \\t kind \\t route`` — the list
    the coordinator must act on.

    A fresh drain lists every seeded receipt UNAPPLIED with its kind and route.
    The expected ids/routes come from the SEED; the kind/route on each line are
    derived from the line and asserted against the seed (never assumed).

    RED LINE (run): remove the UNAPPLIED-reporting loop in cmd_consume.  No
      UNAPPLIED lines are emitted → the line-count assertion fails. Production
      line injected: the unapplied write-loop in cmd_consume.
    """
    cli = _load_cli()
    path = tmp_path / "unappl.sqlite3"
    applied = tmp_path / "applied.md"
    bodies = [b'{"text":"a"}', b'{"text":"b"}', b'{"text":"c"}']
    seeded = _seed(path, bodies, route="/command")
    n = len(seeded)
    assert n >= 2, "precondition: a non-trivial list so the shape check means something"
    expected = {r.receipt_id: "/command" for r in seeded}

    code, out, err = _run(cli, ["consume", "--journal", str(path),
                                "--applied", str(applied)])
    assert code == 0, f"consume exited {code} (err={err!r})"
    lines = [ln for ln in out.splitlines() if ln.startswith("UNAPPLIED\t")]
    assert len(lines) == n, (
        f"must list {n} UNAPPLIED receipts, got {len(lines)}; out={out!r}")
    for ln in lines:
        parts = ln.split("\t")
        # UNAPPLIED \t id \t kind \t route  — the brief's "id + kind + route".
        assert len(parts) == 4, (
            f"an UNAPPLIED line is 4 tab-fields (UNAPPLIED/id/kind/route); "
            f"got {ln!r}")
        _, rid, kind, route = parts
        assert rid in expected, f"unexpected id on UNAPPLIED line: {rid!r}"
        assert kind == cli.EVENT_KIND, (
            f"kind must be {cli.EVENT_KIND!r}, got {kind!r}")
        assert route == expected[rid], (
            f"route must be {expected[rid]!r}, got {route!r}")
    assert sorted(_unapplied_ids(out)) == sorted(expected), (
        "the UNAPPLIED ids must be exactly the seeded ids")


def test_unregistered_route_is_listed_unapplied_never_silent(tmp_path: Path):
    """#526 gate finding: a drained event whose route has NO adapter in
    apply's registry must still surface on consume's UNAPPLIED list — the
    proof cannot cover it, so the coordinator must be told to act on it.
    The cursor still advances past it (it is not re-drained), and no
    marker lands in the applied-ledger (there is no adapter to mark
    through).

    Preconditions derived at runtime: the route is REALLY unregistered
    (adapter_for raises KeyError — a route the registry later adopts
    would silently vacate the test), and the seed landed.

    RED LINE (run): the ``except KeyError: return NOT_APPLIED`` branch in
    ``_prove_drained`` returning ``Proof.APPLIED`` instead (the exact
    sabotage the #526 gate probed and found unbound) → no UNAPPLIED line
    for the event → the membership assertion fails.  Production line
    injected: the KeyError branch's verdict in _prove_drained.
    """
    import user_events.apply as _apply
    cli = _load_cli()
    path = tmp_path / "unreg.sqlite3"
    applied = tmp_path / "applied.md"
    route = "/totally-unregistered-route"
    try:
        _apply.adapter_for(route)
        raise AssertionError(
            f"precondition: {route!r} must be unregistered for this test "
            "to mean anything — the registry adopted it")
    except KeyError:
        pass
    seeded = _seed(path, [b'{"text":"x"}'], route=route)
    rid = seeded[0].receipt_id

    code, out, err = _run(cli, ["consume", "--journal", str(path),
                                "--applied", str(applied)])
    assert code == 0, f"consume exited {code} (err={err!r})"
    unapplied = [ln for ln in out.splitlines() if ln.startswith("UNAPPLIED\t")]
    assert any(ln.split("\t")[1] == rid for ln in unapplied), (
        f"the unregistered-route receipt must be listed UNAPPLIED — a "
        f"silent skip leaves the coordinator never told to act on it; "
        f"out={out!r}")
    ledger = applied.read_text() if applied.exists() else ""
    assert rid not in ledger, (
        "no marker may land for a route with no adapter — the proof "
        "covers adapter-backed routes only")
    code2, out2, _ = _run(cli, ["pending", "--journal", str(path)])
    assert code2 == 0 and not out2.strip(), (
        "the cursor advances past the unregistered event once — it is "
        "reported, not re-drained")


# ---------------------------------------------------------------------------
# 6 — show prints the FULL payload verbatim (no 80-char preview cap), + header
# ---------------------------------------------------------------------------

def test_show_prints_full_payload_and_header(tmp_path: Path):
    """show prints the whole payload bytes decoded, plus a key: value header.

    The payload is deliberately longer than the preview limit (_PREVIEW_LIMIT,
    imported here and asserted-exceeded at runtime — a literal 81-char fixture
    would silently satisfy a future limit bump and is the exact hollow-trap the
    brief names).  The expected payload and the header values come from the
    SEED / get_receipt — NOT from a second call to the CLI.

    RED LINE (run): make cmd_show print the truncated preview instead of the
      verbatim decoded text (``out.write(_preview(payload))``).  The
      >_PREVIEW_LIMIT payload no longer appears in full → the
      ``payload_text in out`` assertion fails.  Production line: the verbatim
      ``out.write(text)`` payload write in cmd_show (NOT the _preview path).
    """
    cli = _load_cli()
    limit = cli._PREVIEW_LIMIT
    path = tmp_path / "show.sqlite3"
    # Derive the length at runtime from the actual preview limit so a future
    # change to _PREVIEW_LIMIT cannot make a literal fixture pass vacuously.
    payload_text = "x" * (limit + 120)
    assert len(payload_text) > limit, (
        f"precondition: payload {len(payload_text)} must exceed the preview "
        f"limit {limit} — else the no-cap assertion is vacuous"
    )
    seeded = _seed(path, [payload_text.encode("utf-8")])
    rid = seeded[0].receipt_id

    # Ground-truth header values from the public read the CLI composes — never
    # assumed, so a header that printed a stale/wrong field fails here.
    with open_journal(path) as j:
        receipt = j.get_receipt(rid)
    assert receipt is not None, "precondition: the seeded receipt must read back"

    code, out, err = _run(cli, ["show", rid, "--journal", str(path)])
    assert code == 0, f"show must exit 0, got {code} (err={err!r})"

    # Header: each field on its own ``key: value`` line.
    for key in ("receipt_id", "state", "revision",
                "client_action_id", "request_digest"):
        assert f"{key}: {receipt[key]}\n" in out, (
            f"header field {key} must appear as 'key: value'; got {out!r}"
        )
    # A blank line separates header from payload.
    assert "\n\n" in out, "a blank line must separate the header from the payload"
    # The FULL payload appears verbatim — no truncation, no length cap.
    assert payload_text in out, (
        "the full payload (longer than the preview limit) must appear verbatim; "
        f"got {out!r}"
    )


# ---------------------------------------------------------------------------
# 7 — show works AFTER consume advanced the cursor past the receipt
# ---------------------------------------------------------------------------

def test_show_works_for_already_consumed_receipt(tmp_path: Path):
    """show recovers a blindly-consumed receipt: consume moves only the cursor,
    the receipt row persists, so show prints its payload after consume too.

    The cursor is asserted MOVED first (derived from j.cursor, not assumed) so
    the test's meaning — "already consumed" — does not rot into "never
    consumed" if consume ever stopped advancing.

    RED LINE (run): make cmd_show read via the cursor-scoped projection
      (events_since_cursor + match-by-id) instead of the by-id get_receipt.
      After consume the event is out of (cursor, head] → not found → exit 64
      → the ``code == 0`` assertion fails.  Production line: the
      ``j.get_receipt(args.receipt_id)`` call in cmd_show (a cursor-INDEPENDENT
      by-id read) — that independence is precisely why it is the recovery seam.
    """
    cli = _load_cli()
    path = tmp_path / "showconsumed.sqlite3"
    payload_text = '{"instruction":"stand up and check posture"}'
    seeded = _seed(path, [payload_text.encode("utf-8")])
    rid = seeded[0].receipt_id

    # Consume advances the cursor past this receipt.
    code, out, err = _run(cli, ["consume", "--journal", str(path),
                                "--applied", str(tmp_path / "applied.md")])
    assert code == 0, f"consume must exit 0, got {code} (err={err!r})"

    # Precondition (derived): the cursor genuinely moved past the receipt.
    with open_journal(path) as j:
        cur = j.cursor(CONSUMER)
        head = j.head_ordinal()
    assert head == 1, f"precondition: one event seeded, head must be 1, got {head}"
    assert cur.scanned_through_event_ordinal >= 1, (
        "precondition: consume must have advanced the cursor past the receipt "
        f"(got ord={cur.scanned_through_event_ordinal}) — else 'already "
        "consumed' is meaningless"
    )

    # show still prints the payload of the now-consumed receipt.
    code, out, err = _run(cli, ["show", rid, "--journal", str(path)])
    assert code == 0, (
        f"show must work for an already-consumed receipt, got {code} (err={err!r})"
    )
    assert payload_text in out, (
        f"the consumed receipt's payload must still print; got {out!r}"
    )


# ---------------------------------------------------------------------------
# 8 — unknown receipt id → exit 64, stderr message, stdout empty
# ---------------------------------------------------------------------------

def test_show_unknown_receipt_exits_usage(tmp_path: Path):
    """An unknown receipt id prints a one-line error to stderr, exits EX_USAGE
    (64), and writes nothing to stdout.

    RED LINE (run): make the not-found branch return EX_OK instead of
      EX_USAGE (swallowing the miss).  The ``code == 64`` assertion fails.
      Production line: the ``return EX_USAGE`` in cmd_show's receipt-is-None
      branch.
    """
    cli = _load_cli()
    path = tmp_path / "unknown.sqlite3"
    _seed(path, [b'{"x":1}'])  # a real journal, so the miss is the id, not the db
    bogus = "00000000-0000-4000-8000-999999999999"

    code, out, err = _run(cli, ["show", bogus, "--journal", str(path)])
    assert code == cli.EX_USAGE, (
        f"unknown receipt must exit EX_USAGE({cli.EX_USAGE}), got {code}"
    )
    assert out == "", (
        f"unknown receipt must write nothing to stdout, got {out!r}"
    )
    assert err.strip() != "", "unknown receipt must print an error to stderr"
    assert bogus in err, "the stderr message should name the missing id"


# ---------------------------------------------------------------------------
# 9 — absent journal → same not-found path, and the db is NOT created
# ---------------------------------------------------------------------------

def test_show_absent_journal_not_created(tmp_path: Path):
    """An absent journal is 'not found' (exit 64, stderr, empty stdout) AND the
    db file is never created — the read-only #501 discipline.

    RED LINE (run): remove the ``if not journal.exists()`` early return so
      execution falls through to open_journal, which creates the db.  The
      ``not absent.exists()`` assertion fails (and the file now exists).
      Production line: the absent-journal early return in cmd_show that
      prevents open_journal from running (no filesystem side effect).
    """
    cli = _load_cli()
    absent = tmp_path / "never.sqlite3"
    assert not absent.exists(), "precondition: the journal must not exist yet"
    rid = "00000000-0000-4000-8000-000000000001"

    code, out, err = _run(cli, ["show", rid, "--journal", str(absent)])
    assert code == cli.EX_USAGE, (
        f"absent journal must exit EX_USAGE({cli.EX_USAGE}), got {code}"
    )
    assert out == "", "absent journal must write nothing to stdout"
    assert err.strip() != "", "absent journal must print an error to stderr"
    assert not absent.exists(), (
        "show must NOT create an absent journal — it is read-only"
    )


# ---------------------------------------------------------------------------
# 10 — multi-line UTF-8 payload survives verbatim (the #126-collapse exception)
# ---------------------------------------------------------------------------

def test_show_multiline_payload_verbatim(tmp_path: Path):
    """show is the deliberate exception to the collapse-newlines rule (#126):
    a payload may be a multi-line human instruction, and this verb is for an
    agent to READ it — so newlines print verbatim, not as ``\\n`` escapes.

    The payload has at least two distinct lines; both must appear with a REAL
    newline between them (the escaped ``\\n`` would be two chars, not a split).

    RED LINE (run): collapse newlines before the verbatim write (``text =
      text.replace('\\n', '\\\\n')``).  The two lines no longer appear on
      separate lines → the ``line_two in lines`` assertion fails.  Production
      line: the verbatim ``out.write(text)`` in cmd_show that does NOT collapse
      newlines (unlike _preview/_format_event, which do).
    """
    cli = _load_cli()
    path = tmp_path / "multiline.sqlite3"
    line_one = "remember to hydrate"
    line_two = "and stretch every hour"
    payload_text = f"{line_one}\n{line_two}\n"
    assert payload_text.count("\n") >= 2, (
        "precondition: payload must have multiple newlines — else the "
        "verbatim-newline assertion is vacuous"
    )
    seeded = _seed(path, [payload_text.encode("utf-8")])
    rid = seeded[0].receipt_id

    code, out, err = _run(cli, ["show", rid, "--journal", str(path)])
    assert code == 0, f"show must exit 0, got {code} (err={err!r})"

    lines = out.splitlines()
    assert line_one in lines, (
        f"the first payload line must appear verbatim on its own line; "
        f"got {lines!r}"
    )
    assert line_two in lines, (
        f"the second payload line must appear verbatim on its own line; "
        f"got {lines!r}"
    )
    # The two payload lines are adjacent (only each other between them), so a
    # collapse-to-\\n escape (which would join them into one line) is caught.
    i = lines.index(line_one)
    assert i + 1 < len(lines) and lines[i + 1] == line_two, (
        "the two payload lines must be adjacent real lines, not joined by an "
        f"escaped newline; got {lines!r}"
    )


# ---------------------------------------------------------------------------
# 11 — #531 consume --through bounds the advance; a late event stays pending
# ---------------------------------------------------------------------------

def test_consume_through_bounds_advance_leaves_late_event_pending(tmp_path: Path):
    """#531: ``consume --through H`` advances at most through H, so an event
    that lands between the coordinator's ``pending`` read and its ``consume``
    is NOT advanced past unread — it stays in ``(cursor, head]`` for the next
    tick.  This is the race that cost ord=43 (#505 answer receipt): it
    committed between a pending read and consume in one tick, consume advanced
    to the NEW head past 43 blind, and only ``show`` recovered it.

    The head ordinal H comes from the ``pending`` read's LAST line (derived
    from the ``ord=`` field, never assumed); the late event is appended AFTER
    that read via the production ``receive()`` path; the cursor position is
    read from ``j.cursor`` (the real row advance_cursor writes), not faked.

    RED LINE (run): make cmd_consume ignore ``--through`` and advance to
      ``events[-1]`` (the live head) — i.e. revert the bound-honouring
      ``drained = [ev ... ordinal <= through]`` / ``target = next(ev ...
      ordinal == through)`` lines to ``drained = events; target =
      events[-1]``.  The cursor advances to H+1 (not H), the consumed count
      rises to H+1 (not H), and the late event leaves ``(cursor, head]`` →
      the three assertions below all fail.  Production line injected: the
      ``target``/``drained`` selection honouring ``args.through`` in
      cmd_consume.
    """
    cli = _load_cli()
    path = tmp_path / "through.sqlite3"
    applied = tmp_path / "applied.md"
    # Seed the first batch; the pending read will report its head as H.
    seeded = _seed(path, [b'{"a":0}', b'{"a":1}', b'{"a":2}'])
    H = len(seeded)  # the head the pending read reports (derived, not assumed)
    assert H >= 2, "precondition: a non-trivial first batch so H > cursor"

    # The pending read — H is the LAST reported line's ord (the head it names).
    code, out, err = _run(cli, ["pending", "--journal", str(path)])
    assert code == 0, f"pending exited {code} (err={err!r})"
    pending_ords = _ord_fields(out)
    assert pending_ords == list(range(1, H + 1)), (
        f"precondition: pending must report ords 1..{H}; got {pending_ords}")
    assert pending_ords[-1] == H, "the head H is the last pending line's ord"

    # An event lands AFTER the pending read but BEFORE consume (the race).
    late = _append_one(path, b'{"late":true}', idx=H)
    late_ord = H + 1
    with open_journal(path) as j:
        assert j.head_ordinal() == late_ord, (
            f"precondition: the late event raised head to {late_ord}; "
            f"got {j.head_ordinal()}")

    # consume --through H: advance at most through H, leaving the late event.
    code, out, err = _run(cli, ["consume", "--through", str(H),
                                "--journal", str(path),
                                "--applied", str(applied)])
    assert code == 0, f"consume --through exited {code} (err={err!r})"

    # The bound held: only the H events in (cursor, H] were drained.
    first_line = out.splitlines()[0] if out.splitlines() else ""
    assert first_line == f"consumed {H} event(s)", (
        f"a --through {H} consume drains exactly {H} event(s) (the late one "
        f"is beyond the bound); first line was {first_line!r}")

    # The cursor stopped at H (NOT H+1): the bound held at the advance too.
    with open_journal(path) as j:
        cur = j.cursor(CONSUMER)
    assert cur.scanned_through_event_ordinal == H, (
        f"consume --through {H} must stop the cursor at {H}; got "
        f"{cur.scanned_through_event_ordinal} (the late event was advanced "
        "past blind — the #531 race)")

    # The late event is STILL pending — the next tick re-lists it.
    code, out, _ = _run(cli, ["pending", "--journal", str(path)])
    assert code == 0
    pending_ords2 = _ord_fields(out)
    assert late_ord in pending_ords2, (
        f"the late event (ord={late_ord}) must remain pending after a "
        f"--through {H} consume; pending ords were {pending_ords2}")
    assert late.receipt_id in _pending_ids(out), (
        "the late event's receipt id must be in the next pending read")


# ---------------------------------------------------------------------------
# 12 — #531 edge: --through at/below the cursor refuses EX_USAGE 64
# ---------------------------------------------------------------------------

def test_consume_through_at_or_below_cursor_refuses_usage(tmp_path: Path):
    """#531 edge: ``--through`` at or below the cursor refuses EX_USAGE (64) —
    a stale ordinal must not rewind (below) or no-op silently (at).  Both
    leave the cursor unmoved and write nothing to stdout.

    The cursor is advanced to N by an ordinary consume first (the precondition
    is DERIVED from ``j.cursor`` afterward, never assumed), so ``--through N``
    is the at-cursor no-op and ``--through N-1`` the rewind.

    RED LINE (run): make the bounds check pass through (e.g. delete the
      ``if through <= cursor_ordinal`` block, or return EX_OK instead of
      EX_USAGE).  consume proceeds instead of refusing → ``code == EX_USAGE``
      fails, and stdout is non-empty.  Production line injected: the
      ``through <= cursor_ordinal`` refusal branch in cmd_consume.
    """
    cli = _load_cli()
    path = tmp_path / "below.sqlite3"
    applied = tmp_path / "applied.md"
    seeded = _seed(path, [b'{"a":0}', b'{"a":1}', b'{"a":2}'])
    n = len(seeded)
    # Advance the cursor to n with an ordinary consume (no --through).
    code, out, err = _run(cli, ["consume", "--journal", str(path),
                                "--applied", str(applied)])
    assert code == 0, f"setup consume exited {code} (err={err!r})"
    with open_journal(path) as j:
        cur_ord = j.cursor(CONSUMER).scanned_through_event_ordinal
    assert cur_ord == n, (
        f"precondition: cursor must sit at {n} after the setup consume; "
        f"got {cur_ord}")

    # Both a no-op (through == cursor) and a rewind (through < cursor) refuse.
    for stale in (n, n - 1):
        code, out, err = _run(cli, ["consume", "--through", str(stale),
                                    "--journal", str(path),
                                    "--applied", str(applied)])
        assert code == cli.EX_USAGE, (
            f"--through {stale} (<= cursor {n}) must refuse EX_USAGE; "
            f"got {code} (err={err!r})")
        assert out == "", (
            f"a refusal must write nothing to stdout; got {out!r}")
        assert err.strip() != "", (
            f"the refusal must explain on stderr; got {err!r}")

    # Cursor unmoved across both refusals.
    with open_journal(path) as j:
        after = j.cursor(CONSUMER)
    assert after.scanned_through_event_ordinal == n, (
        "a refused --through must leave the cursor unmoved at "
        f"{n}; got {after.scanned_through_event_ordinal}")


# ---------------------------------------------------------------------------
# 13 — #531 edge: --through above the head refuses EX_USAGE 64
# ---------------------------------------------------------------------------

def test_consume_through_above_head_refuses_usage(tmp_path: Path):
    """#531 edge: ``--through`` above the head refuses EX_USAGE (64) — the
    cursor cannot advance past what exists.  Cursor unmoved, stdout empty.

    The head is derived from ``j.head_ordinal()`` (never assumed), and the
    ``--through`` value is provably above it.

    RED LINE (run): make the bounds check pass through (e.g. delete the
      ``if through > head_ordinal`` block).  consume proceeds (or crashes on a
      missing ordinal) instead of refusing → ``code == EX_USAGE`` fails.
      Production line injected: the ``through > head_ordinal`` refusal branch
      in cmd_consume.
    """
    cli = _load_cli()
    path = tmp_path / "above.sqlite3"
    applied = tmp_path / "applied.md"
    seeded = _seed(path, [b'{"a":0}', b'{"a":1}'])
    n = len(seeded)
    with open_journal(path) as j:
        head = j.head_ordinal()
    assert head == n, f"precondition: head must be {n}; got {head}"

    beyond = n + 5
    assert beyond > head, "precondition: --through must be above the head"

    code, out, err = _run(cli, ["consume", "--through", str(beyond),
                                "--journal", str(path),
                                "--applied", str(applied)])
    assert code == cli.EX_USAGE, (
        f"--through {beyond} (> head {n}) must refuse EX_USAGE; got {code}")
    assert out == "", f"a refusal must write nothing to stdout; got {out!r}"
    assert err.strip() != "", f"the refusal must explain on stderr; got {err!r}"

    # Cursor unmoved on refusal.
    with open_journal(path) as j:
        cur = j.cursor(CONSUMER)
    assert (cur.scanned_through_event_ordinal, cur.revision) == (0, 0), (
        "a refused --through must leave a fresh cursor unmoved; got "
        f"ord={cur.scanned_through_event_ordinal} rev={cur.revision}")



# ---------------------------------------------------------------------------
# #504 remainder — the consume-side reply instructions.
# ---------------------------------------------------------------------------

def test_consume_drained_chat_carries_reply_instructions(tmp_path: Path):
    """#504 remainder: a drained chat receipt (/command, kind=chat) carries the
    chat id (== the receipt id), the text, and the exact reply command; a
    non-chat command does not.

    RED LINE (run): delete the CHAT emit loop in cmd_consume.  consume still
    exits 0 and prints the counts, but the CHAT line vanishes -> the assertion
    fails.  Production line injected: the ``for chat_id, text in chats:`` loop
    in cmd_consume (restored byte-identical with cp).
    """
    cli = _load_cli()
    path = tmp_path / "chat.sqlite3"
    applied = tmp_path / "applied.md"
    chat_body = b'{"kind": "chat", "text": "are we shipping #504?"}'
    other_body = b'{"kind": "do-next", "text": "ship it"}'
    results = _seed(path, [chat_body, other_body], route="/command")
    chat_rid = results[0].receipt_id
    other_rid = results[1].receipt_id
    assert chat_rid != other_rid, "precondition: two distinct receipt ids"

    code, out, err = _run(cli, ["consume", "--journal", str(path),
                                "--applied", str(applied)])
    assert code == 0, err
    lines = out.splitlines()

    # exactly one CHAT line — the chat receipt, not the do-next
    chat_lines = [ln for ln in lines if ln.startswith("CHAT\t")]
    assert len(chat_lines) == 1, (
        f"exactly one CHAT line (the chat receipt): {chat_lines}")
    chat_line = chat_lines[0]
    assert chat_line.split("\t")[1] == chat_rid, "the chat id IS the receipt id"
    assert "are we shipping #504?" in chat_line, "his text is carried"

    # the exact reply command names the chat id and the reply tool
    reply_lines = [ln for ln in lines if "reply:" in ln and chat_rid in ln]
    assert len(reply_lines) == 1, f"one reply command for the chat: {reply_lines}"
    assert "bin/ud-dw-chat" in reply_lines[0] and " reply " in reply_lines[0], (
        f"the reply command must be act-1's writer: {reply_lines[0]!r}")

    # the non-chat command gets NO chat/reply line
    assert not any(ln.startswith("CHAT\t" + other_rid) for ln in lines), (
        "a non-chat command must not get a CHAT line")
    assert not any("reply:" in ln and other_rid in ln for ln in lines), (
        "a non-chat command must not get a reply command")


def test_consume_chat_text_with_a_newline_is_collapsed_to_one_line(tmp_path: Path):
    """#126 rule one level into the consume output: a newline in his chat text
    must not forge a second output line.  Production line: the
    ``" ".join(text.split())`` collapse in cmd_consume's CHAT emit."""
    cli = _load_cli()
    path = tmp_path / "chat-nl.sqlite3"
    applied = tmp_path / "applied.md"
    # a payload whose text carries a newline
    body = b'{"kind": "chat", "text": "line one\\nsecond line"}'
    results = _seed(path, [body], route="/command")
    rid = results[0].receipt_id
    code, out, err = _run(cli, ["consume", "--journal", str(path),
                                "--applied", str(applied)])
    assert code == 0, err
    chat_lines = [ln for ln in out.splitlines() if ln.startswith("CHAT\t")]
    assert len(chat_lines) == 1, (
        f"one CHAT line (the newline must not split it): {chat_lines}")
    assert "line one" in chat_lines[0] and "second line" in chat_lines[0]
    assert "\n" not in chat_lines[0], "the CHAT line is a single line"
    assert "\\n" not in chat_lines[0].split("\t", 2)[2], (
        "the text is collapsed to spaces, not left as a literal backslash-n")


# ---------------------------------------------------------------------------
# #658 — a read whose output was truncated is not a read.
#
# `pending | tail` hid ordinals the operator never saw, and `consume --through
# <head>` then advanced past them unread.  The fix is the #654 shape: `pending`
# writes a marker sidecar recording the ordinal range it printed; `consume
# --through N` refuses unless that marker proves N was inside the listed range.
# These tests prove the wiring: the marker is written, the check refuses the
# truncation case, each named refusal (#136) is distinct, and bare consume is
# never gated.
# ---------------------------------------------------------------------------

def _pending_read_marker(cli, journal_path: Path) -> dict | None:
    """Read the marker sidecar a ``pending`` run wrote (or None)."""
    return cli._load_pending_read(Path(str(journal_path)))


def test_pending_writes_read_coverage_marker(tmp_path: Path):
    """#658: ``pending`` records the head ordinal it printed into a sidecar, so
    a later bounded ``consume`` can prove its --through was actually listed.

    The marker carries the journal id (bound to THIS journal) and the head
    ordinal (the last printed line's ord, derived from the output — never
    assumed).  An empty pending read records the cursor as its head (so a
    consume bound past zero is still covered).

    RED LINE (run): delete the ``_write_pending_read`` call in cmd_pending's
      non-empty branch.  No marker is written → the ``marker is not None``
      assertion fails. Production line injected: the final
      ``_write_pending_read(...)`` call in cmd_pending.
    """
    cli = _load_cli()
    path = tmp_path / "marker.sqlite3"
    bodies = [b'{"a":0}', b'{"a":1}', b'{"a":2}']
    seeded = _seed(path, bodies)
    n = len(seeded)
    assert n >= 2, "precondition: a non-trivial range so the head is real"

    code, out, err = _run(cli, ["pending", "--journal", str(path)])
    assert code == 0, f"pending exited {code} (err={err!r})"
    pending_ords = _ord_fields(out)
    head = pending_ords[-1]  # the head the read reported (derived, not assumed)
    assert head == n, f"precondition: pending head must be {n}, got {head}"

    mark = _pending_read_marker(cli, path)
    assert mark is not None, (
        "pending must write the read-coverage marker sidecar")
    assert mark["through"] == head, (
        f"the marker's `through` must be the pending read's head {head}; "
        f"got {mark['through']}")
    # The marker is bound to this journal by id (the UUID minted at creation).
    with open_journal(path) as j:
        jid = j.journal_id
    assert mark["journal_id"] == jid, (
        "the marker must carry this journal's id so a marker from a different "
        "checkout cannot satisfy a consume against this one")


def test_consume_through_refuses_when_read_was_truncated(tmp_path: Path):
    """#658 direction 1 (the bug): ``consume --through N`` refuses when N
    exceeds the head the prior ``pending`` actually printed — i.e. when the
    operator truncated their own read (``pending | tail``).

    Reproduces the original loss on today's pre-fix shape, then proves the fix
    REFUSES.  The refusal must NAME the uncovered ordinals (the brief requires
    it name them, not merely say the check failed).  Cursor unmoved.

    The truncation is simulated honestly: ``pending`` is run, its REAL head H
    is derived from the output, then a marker is hand-written with through=H-1
    (what the operator's eyes saw after ``tail`` dropped the last line) — so the
    consume asks for through=H against a read that proved only through H-1.

    RED LINE (run): delete the ``if through > mark['through']`` refusal branch
      in cmd_consume.  consume proceeds and advances the cursor → the
      ``code == EX_USAGE`` and cursor-unmoved assertions fail. Production line
      injected: the ``through > mark['through']`` refusal in cmd_consume.
    """
    cli = _load_cli()
    path = tmp_path / "trunc.sqlite3"
    applied = tmp_path / "applied.md"
    bodies = [b'{"a":0}', b'{"a":1}', b'{"a":2}', b'{"a":3}']
    seeded = _seed(path, bodies)
    n = len(seeded)
    assert n >= 3, "precondition: enough events that truncation is meaningful"

    # The honest pending read reports head H (derived from its output).
    code, out, err = _run(cli, ["pending", "--journal", str(path)])
    assert code == 0
    pending_ords = _ord_fields(out)
    H = pending_ords[-1]
    assert H == n, f"precondition: pending head is {n}, got {H}"

    # Simulate the operator's `tail` dropping the last line: overwrite the
    # marker so it proves only through H-1 (what their eyes actually saw),
    # while consume asks for through=H (the live head they think they read).
    with open_journal(path) as j:
        jid = j.journal_id
    cli._write_pending_read(Path(str(path)), jid, H - 1)

    # Cursor before — must be unmoved on refusal.
    with open_journal(path) as j:
        before = j.cursor(CONSUMER)
    assert before.scanned_through_event_ordinal == 0, "precondition: fresh cursor"

    code, out, err = _run(cli, ["consume", "--through", str(H),
                                "--journal", str(path),
                                "--applied", str(applied)])
    assert code == cli.EX_USAGE, (
        f"consume --through {H} must REFUSE when the read proved only "
        f"through {H - 1} (the truncation); got exit {code} (out={out!r})")
    assert out == "", "a refusal must write nothing to stdout"
    # The brief requires the refusal NAME the uncovered ordinals.
    assert str(H) in err, (
        f"the refusal must name ordinal {H} (the uncovered one); got {err!r}")
    assert "never listed" in err, (
        f"the refusal must say the ordinals were never listed; got {err!r}")

    # Cursor unmoved: the refusal advances nothing.
    with open_journal(path) as j:
        after = j.cursor(CONSUMER)
    assert after.scanned_through_event_ordinal == 0, (
        "a refused consume must leave the cursor unmoved (got "
        f"{after.scanned_through_event_ordinal})")


def test_consume_through_absent_marker_refuses_named_bootstrap(tmp_path: Path):
    """#658/#136: a bounded consume with NO prior pending read refuses with a
    NAMED bootstrap message — not a hard wedge, and distinct from the
    truncation case.  The escape hatch is bare ``consume`` (no --through),
    which never reads the marker.

    The marker is genuinely absent (no pending run was made), so this is the
    first-run / cleared-state case, and it must say so.

    RED LINE (run): make the absent-marker branch proceed (delete the ``if mark
      is None`` refusal).  consume advances the cursor → the ``code == EX_USAGE``
      assertion fails. Production line injected: the ``mark is None`` refusal.
    """
    cli = _load_cli()
    path = tmp_path / "bootstrap.sqlite3"
    applied = tmp_path / "applied.md"
    seeded = _seed(path, [b'{"a":0}', b'{"a":1}'])
    n = len(seeded)
    # Precondition: no pending read was made → no marker sidecar exists.
    assert _pending_read_marker(cli, path) is None, (
        "precondition: no pending read, so no marker — this is the bootstrap")

    code, out, err = _run(cli, ["consume", "--through", str(n),
                                "--journal", str(path),
                                "--applied", str(applied)])
    assert code == cli.EX_USAGE, (
        f"a bounded consume with no prior read must refuse EX_USAGE; got {code}")
    assert out == "", "a refusal writes nothing to stdout"
    # #136: the absent case names itself, distinct from the truncation case.
    assert "no pending read" in err, (
        f"the refusal must name the absent-marker bootstrap case; got {err!r}")

    # The escape hatch: bare consume (no --through) is NEVER gated by the
    # marker — it is the right form when there was no prior read.
    code2, out2, err2 = _run(cli, ["consume", "--journal", str(path),
                                   "--applied", str(applied)])
    assert code2 == 0, (
        f"bare consume must never be gated by the marker; got {code2} ({err2!r})")
    assert f"consumed {n} event(s)" in out2, (
        f"bare consume advances to the live head; got {out2!r}")


def test_consume_through_marker_from_different_journal_refuses(tmp_path: Path):
    """#658/#136: a marker left by a DIFFERENT journal (a stale sidecar from
    another checkout, or a journal that was recreated) must not satisfy a
    consume against this one.  The journal_id binds the marker to its journal.

    RED LINE (run): delete the ``mark['journal_id'] != journal_id`` refusal.
      The mismatched marker is honoured → consume proceeds → ``code == EX_USAGE``
      fails. Production line injected: the journal_id-mismatch refusal.
    """
    cli = _load_cli()
    path = tmp_path / "mismatch.sqlite3"
    applied = tmp_path / "applied.md"
    seeded = _seed(path, [b'{"a":0}', b'{"a":1}'])
    n = len(seeded)

    # Run pending so a marker exists, then corrupt its journal_id so it reads
    # as "from a different journal".
    _run(cli, ["pending", "--journal", str(path)])
    mp = cli._pending_read_path(Path(str(path)))
    import json as _json
    orig = _json.loads(mp.read_text())
    orig["journal_id"] = "00000000-0000-0000-0000-differentjournal"
    mp.write_text(_json.dumps(orig))

    code, out, err = _run(cli, ["consume", "--through", str(n),
                                "--journal", str(path),
                                "--applied", str(applied)])
    assert code == cli.EX_USAGE, (
        f"a marker from a different journal must refuse; got {code}")
    assert out == "", "a refusal writes nothing to stdout"
    assert "different journal" in err, (
        f"the refusal must name the journal-mismatch case; got {err!r}")


def test_consume_through_honoured_when_marker_covers_it(tmp_path: Path):
    """#658 happy path: ``pending`` then ``consume --through <head>`` proceeds
    when the marker honestly covers the bound — the normal tick, now gated.

    This is the existing #531 behaviour re-proven under the new check: the
    marker a real pending read writes satisfies a consume bounded to that
    read's head.  The cursor advances; a late event stays pending.

    RED LINE (run): make the marker check refuse unconditionally (e.g. invert
      ``through > mark['through']`` to ``through > 0``).  consume refuses →
      ``code == 0`` fails. Production line injected: the comparison in the
      uncovered-ordinal refusal branch.
    """
    cli = _load_cli()
    path = tmp_path / "honour.sqlite3"
    applied = tmp_path / "applied.md"
    seeded = _seed(path, [b'{"a":0}', b'{"a":1}', b'{"a":2}'])
    H = len(seeded)
    assert H >= 2, "precondition: a non-trivial range"

    code, out, err = _run(cli, ["pending", "--journal", str(path)])
    assert code == 0
    assert _ord_fields(out)[-1] == H, "precondition: pending head is H"

    code, out, err = _run(cli, ["consume", "--through", str(H),
                                "--journal", str(path),
                                "--applied", str(applied)])
    assert code == 0, (
        f"a bounded consume covered by the marker must proceed; got {code} "
        f"({err!r})")
    assert f"consumed {H} event(s)" in out
    with open_journal(path) as j:
        assert j.cursor(CONSUMER).scanned_through_event_ordinal == H


def test_consume_through_empty_pending_refuses_past_zero(tmp_path: Path):
    """#658 edge: a pending read that was EMPTY recorded head = cursor (0 on a
    fresh journal).  A subsequent ``consume --through N`` (N > 0) must refuse —
    those ordinals were never listed — and name them.  This closes the path
    where an operator runs pending (empty), events land, and they consume
    --through the new live head without re-reading.

    RED LINE (run): make the empty-pending branch in cmd_pending NOT write the
      marker (so it stays absent).  The refusal would then fire the absent-case
      message instead of the uncovered-ordinal one → the ``never listed``
      assertion fails. Production line injected: the ``_write_pending_read``
      call in cmd_pending's empty branch.
    """
    cli = _load_cli()
    path = tmp_path / "emptypending.sqlite3"
    applied = tmp_path / "applied.md"
    # Seed ONE event AFTER an empty pending read, so pending(0) then a live
    # head of 1 is the truncation-via-empty case.
    _seed(path, [b'{"late":true}'])  # but read pending FIRST on an empty journal

    # Actually: seed after the empty pending. Build an empty journal, read
    # pending (empty, marker head=0), then seed one event.
    path2 = tmp_path / "emptypending2.sqlite3"
    with open_journal(path2) as j:
        assert j.head_ordinal() == 0, "precondition: fresh empty journal"
    code, out, err = _run(cli, ["pending", "--journal", str(path2)])
    assert code == 0 and out == "", "precondition: pending is empty"
    mark = _pending_read_marker(cli, path2)
    assert mark is not None and mark["through"] == 0, (
        "precondition: the empty pending read recorded head=0 (the cursor)")

    # An event lands after the empty read.
    _append_one(path2, b'{"x":1}', idx=0)

    code, out, err = _run(cli, ["consume", "--through", "1",
                                "--journal", str(path2),
                                "--applied", str(applied)])
    assert code == cli.EX_USAGE, (
        "consume --through 1 after an empty pending read (head 0) must refuse")
    assert "never listed" in err, (
        f"the refusal must name ord=1 as never listed; got {err!r}")
    assert "1" in err


# ---------------------------------------------------------------------------
# #712 — the marker proved a line was PRINTED, not SEEN.
#
# #658 bounded `--through` from ABOVE only, so the traced loss survived it:
# `pending` prints 96..99, the operator's `tail -3` shows 97..99, and `consume
# --through 96` is INSIDE the listed range — #658's check is satisfied and 96 is
# consumed unread.  Two changes are pinned here and they do DIFFERENT jobs, so
# they are tested separately and neither is allowed to stand in for the other:
#   * `--through` must EQUAL the head of the read on record (a fourth named
#     refusal for a bound BELOW it) — this REFUSES the traced command;
#   * `pending`'s coverage statement goes to stderr, which a stdout pipe does
#     not touch — this makes the truncation VISIBLE, and nothing more.
# Neither establishes that a line was SEEN; see the module docstring's #712 note
# and .dreamwork/lane-712-report.md for why that is not establishable here.
# ---------------------------------------------------------------------------

def test_consume_through_below_read_head_refuses_naming_the_lost_ordinal(tmp_path: Path):
    """#712 direction 1: the traced loss, reproduced and then refused.

    The trace, verbatim from the task: pending lists 96..99 and marks
    through=99; the operator pipes through ``tail -3`` and holds 97..99;
    ``consume --through 96`` is run from an earlier read; 96 is INSIDE the
    listed range so #658's marker is satisfied and there is NO refusal; ordinal
    96 is consumed unread.

    The truncation is simulated on the REAL output rather than asserted about:
    the operator's view is the last three lines of what ``pending`` actually
    printed, and the ordinal at stake is derived as one the full listing
    contains and that view does not.  The load-bearing precondition is that
    #658's own check would NOT have fired (the ordinal is at or below the
    marker's head) — without it this test would be re-proving #658 and would
    pass on the unfixed code.

    RED LINE (run): delete the ``if through < mark['through']`` refusal branch
      in cmd_consume.  The consume proceeds and advances the cursor over the
      unseen ordinal → the ``code == EX_USAGE`` and cursor-unmoved assertions
      fail.  Production line injected: the below-the-read-head refusal in
      cmd_consume.
    """
    cli = _load_cli()
    path = tmp_path / "below.sqlite3"
    applied = tmp_path / "applied.md"
    seeded = _seed(path, [b'{"a":0}', b'{"a":1}', b'{"a":2}', b'{"a":3}'])
    n = len(seeded)
    assert n >= 4, "precondition: enough events that a tail -3 view is short"

    # The honest read: pending prints the whole range and marks its head.
    code, out, err = _run(cli, ["pending", "--journal", str(path)])
    assert code == 0, f"pending exited {code} (err={err!r})"
    listed = _ord_fields(out)
    assert listed == list(range(1, n + 1)), (
        f"precondition: pending must list 1..{n}; got {listed}")

    # The operator's `tail -3`: they hold the LAST three lines of that output.
    held = _ord_fields("\n".join(out.splitlines()[-3:]))
    assert len(held) < len(listed), (
        "precondition: the truncated view must be genuinely shorter than the "
        f"listing, else there is nothing to lose (held {held}, listed {listed})")
    # The ordinal at stake: listed, and NOT in the view — derived, not a literal
    # tuned to this fixture (the lowest such is what the operator carries over).
    unseen = [o for o in listed if o not in held]
    assert unseen, "precondition: the tail must have removed at least one ordinal"
    lost = unseen[0]

    mark = _pending_read_marker(cli, path)
    assert mark is not None, "precondition: the pending read wrote its marker"
    # THE PRECONDITION THIS WHOLE TEST DEPENDS ON: #658's check does not fire.
    # `lost` is inside the listed range, so `through > mark['through']` is
    # false and the pre-#712 code reaches the advance with no refusal at all.
    assert lost <= mark["through"], (
        f"precondition: ordinal {lost} must be INSIDE the marked range "
        f"(head {mark['through']}) — otherwise #658 already refuses this and "
        "this test proves nothing new")
    assert lost < mark["through"], (
        f"precondition: the bound {lost} must be strictly BELOW the read head "
        f"{mark['through']} — that gap is the signal #712 reads")

    with open_journal(path) as j:
        before = j.cursor(CONSUMER).scanned_through_event_ordinal
    assert before == 0, "precondition: fresh cursor"

    code, out2, err2 = _run(cli, ["consume", "--through", str(lost),
                                  "--journal", str(path),
                                  "--applied", str(applied)])
    assert code == cli.EX_USAGE, (
        f"consume --through {lost} must REFUSE: the read on record printed "
        f"through {mark['through']}, so a bound of {lost} came from an older "
        f"or truncated view and would advance past an unseen ordinal; got "
        f"exit {code} (out={out2!r})")
    assert out2 == "", "a refusal must write nothing to stdout"
    # The refusal must NAME the ordinal that would be lost — "range mismatch"
    # without naming what goes is not discriminating (the brief's words).
    assert str(lost) in err2, (
        f"the refusal must name ordinal {lost} specifically; got {err2!r}")
    assert str(mark["through"]) in err2, (
        f"the refusal must name the head of the read on record "
        f"({mark['through']}) so the operator can see the gap; got {err2!r}")
    assert "BELOW" in err2, (
        f"the refusal must name the below-the-read-head case, distinct from "
        f"#658's 'never listed' case (#136); got {err2!r}")
    # The escape must be reachable from the message alone (no wedge), and it is
    # not "delete the marker file".
    assert "bare `consume`" in err2.lower(), (
        f"the refusal must name the non-wedging escape; got {err2!r}")

    with open_journal(path) as j:
        after = j.cursor(CONSUMER).scanned_through_event_ordinal
    assert after == before, (
        f"a refused consume must leave the cursor at {before}; got {after} — "
        f"ordinal {lost} was consumed unread, which is the #712 loss")

    # Not a wedge: the escape in the message works, and so does the honest form.
    code3, out3, err3 = _run(cli, ["consume", "--through", str(mark["through"]),
                                   "--journal", str(path),
                                   "--applied", str(applied)])
    assert code3 == 0, (
        f"consuming --through the read's own head must proceed; got {code3} "
        f"({err3!r}) — the refusal above must not have wedged the tick")
    assert f"consumed {n} event(s)" in out3


def test_pending_coverage_line_reaches_stderr_when_stdout_is_truncated(tmp_path: Path):
    """#712: the coverage statement rides stderr, which a stdout pipe cannot cut.

    ``pending | tail -3`` truncates fd 1 and does not touch fd 2, so the count
    and the full ordinal range still reach the operator while the listing in
    their hands is short.  A trailer on stdout would not do this — it rides the
    channel being truncated, so its survival depends on which truncation was
    used.  This test pins the CHANNEL, not just the text, by asserting the line
    is in stderr AND that stdout is still exactly the event record.

    This is a VISIBILITY property.  It does not establish that anything was
    seen, and the sibling test above is the one that refuses.

    RED LINE (run): write the coverage line to ``out`` instead of ``err`` in
      cmd_pending — i.e. the in-band trailer this was chosen over.  The
      truncated view then drops it, stderr is empty, and both the
      ``in err`` and the stdout-line-count assertions fail.  Production line
      injected: the ``err.write(...)`` coverage statement in cmd_pending.
    """
    cli = _load_cli()
    path = tmp_path / "cover.sqlite3"
    seeded = _seed(path, [b'{"a":0}', b'{"a":1}', b'{"a":2}', b'{"a":3}'])
    n = len(seeded)
    assert n >= 4, "precondition: more events than the truncated view holds"

    code, out, err = _run(cli, ["pending", "--journal", str(path)])
    assert code == 0, f"pending exited {code} (err={err!r})"

    listed = _ord_fields(out)
    assert listed == list(range(1, n + 1)), f"precondition: 1..{n}; got {listed}"

    # The operator's `tail -3` view: strictly shorter than what was listed.
    held = _ord_fields("\n".join(out.splitlines()[-3:]))
    assert len(held) < n, (
        f"precondition: the truncated view ({held}) must be shorter than the "
        f"{n} listed, else there is no inconsistency to make visible")
    lowest = listed[0]
    assert lowest not in held, (
        f"precondition: ordinal {lowest} must be the one the tail removed; "
        f"held {held}")

    # The coverage statement survived the truncation, on stderr.
    assert f"listed {n} receipt(s)" in err, (
        f"stderr must state the count the operator can compare against the "
        f"{len(held)} lines they hold; got {err!r}")
    assert f"{lowest}..{listed[-1]}" in err, (
        f"stderr must name the full range, including ordinal {lowest} which "
        f"the truncation removed from their view; got {err!r}")
    # The exact next command, so the normal tick is copy-paste and the bound
    # cannot be mistranscribed (#712 requires --through to EQUAL this head).
    assert f"--through {listed[-1]}" in err, (
        f"stderr must name the exact bound for the consume; got {err!r}")

    # stdout is UNCHANGED as the record: one line per event, no trailer in it.
    # (Checked AFTER the channel assertions above, so an in-band trailer reds
    # on the property that decided the design — the truncated view loses it —
    # rather than on the parser contract, which is the secondary reason.)
    stdout_lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(stdout_lines) == n, (
        f"stdout must be exactly {n} event lines — a coverage line in the "
        f"record would break `line.split('\\t')[0]` parsers; got "
        f"{len(stdout_lines)}: {stdout_lines!r}")

    # The quiet rule holds: an empty read says nothing on either channel.
    empty = tmp_path / "quiet.sqlite3"
    with open_journal(empty) as j:
        assert j.head_ordinal() == 0, "precondition: fresh empty journal"
    code2, out2, err2 = _run(cli, ["pending", "--journal", str(empty)])
    assert code2 == 0 and out2 == "" and err2 == "", (
        f"pending is quiet on empty on BOTH channels; got {out2!r} / {err2!r}")


def test_malformed_marker_degrades_to_the_named_absent_refusal(tmp_path: Path):
    """#712: a parseable-but-shapeless marker must degrade, not throw.

    ``_load_pending_read``'s docstring already promised that a corrupt marker
    returns None and falls to the named absent refusal — but it only delivered
    that for bad JSON.  ``{}`` parses fine and then raised ``KeyError`` at the
    ``mark["journal_id"]`` comparison in consume: the throw the guard exists to
    prevent, one layer down (a guard whose subject may not exist must degrade
    to a reading, never throw).

    RED LINE (run): delete the ``isinstance`` shape checks in
      ``_load_pending_read``.  ``{}`` is returned as a valid marker and the
      consume raises KeyError instead of refusing → the call errors out before
      any assertion.  Production line injected: the shape validation in
      ``_load_pending_read``.
    """
    cli = _load_cli()
    path = tmp_path / "malformed.sqlite3"
    applied = tmp_path / "applied.md"
    seeded = _seed(path, [b'{"a":0}', b'{"a":1}'])
    n = len(seeded)

    _run(cli, ["pending", "--journal", str(path)])
    mp = cli._pending_read_path(Path(str(path)))
    assert mp.exists(), "precondition: pending wrote a marker to overwrite"
    for bad in ("{}", '{"journal_id": "x"}', '{"journal_id": "x", "through": "3"}'):
        mp.write_text(bad)
        # The BLACK-BOX consequence first, deliberately: without the shape
        # check this line RAISES (KeyError: 'journal_id') rather than
        # refusing, so the test's own red is the production crash and not a
        # white-box reading of the helper that stands in front of it.
        code, out, err = _run(cli, ["consume", "--through", str(n),
                                    "--journal", str(path),
                                    "--applied", str(applied)])
        assert code == cli.EX_USAGE, (
            f"a malformed marker ({bad}) must fall to the named absent "
            f"refusal; got {code}")
        assert "no pending read" in err, (
            f"the refusal must name the absent case (#136); got {err!r}")
        with open_journal(path) as j:
            assert j.cursor(CONSUMER).scanned_through_event_ordinal == 0, (
                "a refused consume must leave the cursor unmoved")
        assert cli._load_pending_read(Path(str(path))) is None, (
            f"a malformed marker ({bad}) must read as absent, not as a marker")


# ---------------------------------------------------------------------------
# #722 — the journal drain livelocks when the head is a receipt.transition,
# and pending was SILENT with an unconsumed ordinal above the cursor.
#
# pending computed its reported head over receipt.created only (the projection
# filters on event_kind); the cursor advances over every ordinal.  A transition
# at the head meant pending reported head=116 while the head was 117, so
# consume --through 117 was refused by #712's guard (correctly — 117 was never
# listed) and consume --through 116 did not move.  No legal --through existed.
# These two tests pin BOTH halves of the fix and the fix did NOT weaken #712.
# ---------------------------------------------------------------------------

def test_pending_reports_true_head_and_not_listed_when_head_is_transition(tmp_path: Path):
    """#722 defect 2 (#702/#136): when the only thing above the cursor is a
    transition (an event_kind pending will not list), pending must still say
    SOMETHING — it knows an ordinal is there — and must not render identically
    to a journal that is genuinely empty.

    The fixture is the live shape from #722: a receipt.created at ord 1, then a
    receipt.transition at ord 2 (the head).  Pre-fix pending printed nothing on
    either stream with ord=2 above the cursor.

    RED LINE (run): make cmd_pending compute head over the listing only (revert
      the true-head change).  The marker's `through` becomes 1, the `not listed`
      report vanishes, and the `head 2` assertion fails.  Production line
      injected: the `head = j.head_ordinal()` line in cmd_pending.
    """
    cli = _load_cli()
    path = tmp_path / "transition.sqlite3"
    seeded = _seed(path, [b'{"a":1}'])
    rid = seeded[0].receipt_id
    # Append a transition — it becomes ord 2, the new head, and is NOT listed.
    trans_head = _append_transition(path, rid)
    assert trans_head == 2, (
        f"precondition: the transition must be the head (ord 2); got {trans_head}")
    # The receipt.created stays at ord 1 (proven via the projection, not assumed
    # — a seed that re-ordered would vacate the assertion).
    with open_journal(path) as j:
        assert j.head_ordinal() == 2
        projected = j.events_since_cursor(CONSUMER)
    assert len(projected) == 1 and projected[0].ordinal == 1, (
        f"precondition: exactly one receipt.created at ord 1; got {projected}")

    code, out, err = _run(cli, ["pending", "--journal", str(path)])
    assert code == 0, f"pending exited {code} (err={err!r})"

    # #722 fix 1: the marker records the TRUE head (2), not the listing head (1).
    mark = _pending_read_marker(cli, path)
    assert mark is not None, "pending must write the read-coverage marker"
    assert mark["through"] == 2, (
        f"the marker must record the TRUE journal head 2 (not the listing head "
        f"1) — else #712's guard refuses the only drainable value; "
        f"got {mark['through']}")

    # #722 fix 2: pending is NOT silent.  It states the true head and NAMES the
    # ordinal it will not list, with its kind (#702 — report, never drop).  This
    # is the channel that distinguishes "nothing needs you" from "something is
    # hiding above your cursor" (#136) — the exact distinction lost pre-fix.
    assert "head 2" in err, (
        f"pending must state the true head on stderr; got {err!r}")
    assert "not listed" in err, (
        f"pending must name the unlisted transition; got {err!r}")
    assert "receipt.transition" in err, (
        f"pending must name the transition's kind; got {err!r}")
    assert "ord=2" in err, (
        f"pending must name the transition's ordinal; got {err!r}")
    # stdout is still the receipt record — the listing did not widen.
    assert len(_pending_ids(out)) == 1, (
        f"the listing stays receipt.created-only; got {out!r}")


def test_consume_drains_transition_head_then_pending_quiet(tmp_path: Path):
    """#722 defect 1 (the livelock): the documented tick — pending then consume
    --through the head pending reports — must DRAIN a journal whose head is a
    transition, and a second pending must be genuinely quiet (not the silent
    "something is hiding" of the pinned cursor).

    Reproduces the live state on a fixture: cursor at 0, ord 1 receipt.created,
    ord 2 receipt.transition.  Pre-fix this was an exact livelock — no legal
    --through existed.

    The load-bearing assertion is the LIVELOCK one: the consume SUCCEEDS and the
    cursor reaches the true head, proving no legal move was missing.  The
    post-drain quiet must be the #136 calm-grey "cursor at head" quiet, not the
    pre-fix silent-hiding quiet — distinguished by the cursor having moved.

    RED LINE (run): revert the true-head fix (marker records the listing head).
      The marker's `through` becomes 1, consume --through 2 is refused by #712
      (2 was never listed), and the cursor stays at 0 → the `cursor == 2`
      assertion fails on the message that names the livelock.  Production line
      injected: the `head = j.head_ordinal()` true-head in cmd_pending (and the
      target-ordinal widening in cmd_consume that follows from it).
    """
    cli = _load_cli()
    path = tmp_path / "drain.sqlite3"
    applied = tmp_path / "applied.md"
    seeded = _seed(path, [b'{"a":1}', b'{"b":2}'])
    rids = [r.receipt_id for r in seeded]
    # Transition the second receipt — it becomes ord 3 (2 receipts + 1 transition).
    head = _append_transition(path, rids[1])
    n_receipts = len(seeded)
    assert head == n_receipts + 1, (
        f"precondition: the transition must be the head at ord {n_receipts + 1}; "
        f"got {head}")
    with open_journal(path) as j:
        assert j.cursor(CONSUMER).scanned_through_event_ordinal == 0, (
            "precondition: fresh cursor at 0")

    # The tick: pending (reports the true head), then consume --through that head.
    code, out, err = _run(cli, ["pending", "--journal", str(path)])
    assert code == 0
    head_reported = _pending_read_marker(cli, path)["through"]
    # THE LIVELOCK ASSERTION IS THE CONSUME BELOW.  Pre-fix, pending reported the
    # listing head (n_receipts, not n_receipts+1); consume --through the TRUE head
    # was then refused by #712 ("never listed"), and --through the listing head did
    # not move.  No legal --through existed.  We consume --through the TRUE head and
    # assert it SUCCEEDS — that is the assertion no legal move existed to satisfy.

    code, out2, err2 = _run(cli, ["consume", "--through", str(head),
                                  "--journal", str(path),
                                  "--applied", str(applied)])
    assert code == 0, (
        f"consume --through {head} (the true head) must SUCCEED — the livelock "
        f"is that pending reported head {head_reported} while the true head was "
        f"{head}, so #712's guard refused the only drainable value and no legal "
        f"--through existed; got exit {code} (err={err2!r})")
    # The cursor advanced to the true head — the drain completed.
    with open_journal(path) as j:
        cur = j.cursor(CONSUMER).scanned_through_event_ordinal
    assert cur == head, (
        f"the cursor must reach the true head {head}; got {cur} — the "
        f"transition was not drained and the livelock persists")

    # #136 calm-grey quiet: a second pending is now silent because the cursor is
    # at the head, NOT because it is hiding something.  The cursor having moved
    # is what makes this quiet safe rather than the pre-fix hiding quiet.
    code3, out3, err3 = _run(cli, ["pending", "--journal", str(path)])
    assert code3 == 0
    assert out3 == "" and err3 == "", (
        f"after draining to head, pending is genuinely quiet (cursor at head, "
        f"not hiding); got {out3!r} / {err3!r}")


# ---------------------------------------------------------------------------
# #864 — the EXPEDITED delivery class.
#
# The whole safety argument is that `expedite` is a READER: it delivers without
# advancing the cursor, so the tick can neither double-consume nor lose an
# event, and the DOUBLE DELIVERY is stopped by the #526/#527 proof instead.
# Each test below therefore asserts the SURVIVING PENDING SET, not only the
# delivered set — the brief's direction-2 candidates are exactly the two
# failures a delivered-set-only assertion cannot tell apart:
#   * cursor never advanced  -> delivered looks right; every tick redelivers.
#   * cursor advanced past unread -> delivered looks right; the rest are lost.
# ---------------------------------------------------------------------------

def _cmd_body(kind: str, text: str) -> bytes:
    """A ``/command`` receipt payload in the shape watch._handle_command commits.

    The kind is INSIDE the payload, which is the whole reason the expedited
    flag needs no journal surface: it is the same string PREEMPT_KINDS already
    matches on.
    """
    import json as _json
    return _json.dumps({"kind": kind, "text": text}).encode("utf-8")


def _expedited_ids(text: str) -> list[str]:
    """Receipt ids of the column-0 ``EXPEDITED`` record lines, in order.

    Continuation lines are indented two spaces, so a payload whose own text
    begins a line with ``EXPEDITED`` cannot be miscounted as a record — that
    indentation is the #126 forged-line defence and this parser depends on it.
    """
    return [ln.split("\t")[1] for ln in text.splitlines()
            if ln.startswith("EXPEDITED\t")]


def _cursor_ordinal(path: Path) -> int:
    """The coordinator cursor position, read from the db, never from the CLI."""
    with open_journal(path) as j:
        return j.cursor(CONSUMER).scanned_through_event_ordinal


def _seed_mixed(path: Path, kinds: list[str]) -> list[str]:
    """Seed one ``/command`` receipt per kind; return the receipt ids in order."""
    bodies = [_cmd_body(k, f"instruction {i} for {k}") for i, k in enumerate(kinds)]
    return [r.receipt_id for r in _seed(path, bodies, route="/command")]


def test_expedite_delivers_only_expedited_and_leaves_every_event_pending(tmp_path: Path):
    """PRODUCTION LINES: ``cmd_expedite``'s candidate filter (``if expedited``)
    and the ABSENCE of any ``advance_cursor`` call in that verb.

    Three assertions, and the last two are the direction-2 closers:

      1. delivered == exactly the expedited ids.  The fixture asserts at
         runtime that BOTH classes are non-empty and that the expedited are a
         PROPER subset — a fixture where every receipt is expedited cannot
         detect a flag that is ignored, and one where none is cannot detect a
         flag that is inverted.
      2. the SURVIVING PENDING SET after the hook == the full seeded set.  An
         assertion on the delivered set alone passes while the cursor was never
         advanced (so every tick redelivers forever) AND while it was advanced
         past unread events (so they are silently lost); only the survivors
         distinguish those two from the correct behaviour.
      3. the cursor ordinal, read from the db rather than from the CLI, is
         unmoved.
    """
    cli = _load_cli()
    path = tmp_path / "j.sqlite3"
    kinds = ["add-idea", "do-next", "maintenance", "do-next", "add-idea"]
    ids = _seed_mixed(path, kinds)
    from user_events import delivery
    expedited_kinds = [k for k in kinds if k in delivery.EXPEDITE_KINDS]
    assert 0 < len(expedited_kinds) < len(kinds), (
        f"precondition: the fixture must hold BOTH expedited and ordinary "
        f"receipts, or the flag being ignored is undetectable; kinds={kinds}, "
        f"EXPEDITE_KINDS={delivery.EXPEDITE_KINDS}")
    want = [rid for rid, k in zip(ids, kinds) if k in delivery.EXPEDITE_KINDS]

    before = _cursor_ordinal(path)
    code, out, err = _run(cli, ["expedite", "--journal", str(path),
                                "--applied", str(tmp_path / "applied.md"),
                                "--limit", str(len(kinds) + 1)])
    assert code == 0, f"expedite exit {code} (err={err!r})"
    assert _expedited_ids(out) == want, (
        f"expedite must deliver exactly the expedited receipts, in ordinal "
        f"order: want {want}, got {_expedited_ids(out)} "
        f"(kinds in seed order: {kinds})")

    # (2) the survivors — the direction-2 closer.
    code2, out2, _ = _run(cli, ["pending", "--journal", str(path)])
    assert code2 == 0
    assert _pending_ids(out2) == ids, (
        f"every seeded receipt must STILL be pending after the hook — the hook "
        f"delivers, the tick drains. want {ids}, got {_pending_ids(out2)}; if "
        f"the expedited ones are missing the cursor advanced past unread "
        f"events (silent loss), and if the list is short the range moved")
    assert _cursor_ordinal(path) == before == 0, (
        f"the cursor must not move: {before} -> {_cursor_ordinal(path)}")


def test_expedite_under_a_cap_prioritises_expedited_over_lower_ordinal_ordinary(tmp_path: Path):
    """PRODUCTION LINE: the sort key in ``cmd_expedite`` —
    ``key=lambda ce: (0 if ce[0] else 1, ce[1].ordinal)``.

    "Oh if we have a cap on events drained at once, these flagged expedited
    should be prioritized."  Prioritisation only MANIFESTS under a cap, so this
    asserts, at runtime and derived from the fixture rather than from literals:

      * the cap is genuinely reached (``limit`` < the number of pending events),
        because with a cap above the population every order passes; and
      * every ordinary receipt holds a STRICTLY LOWER ordinal than every
        expedited one, so an implementation that ordered by ordinal alone would
        fill the whole slice with ordinary receipts and deliver nothing.

    Without both preconditions this test is green on a broken sort key.
    """
    cli = _load_cli()
    path = tmp_path / "j.sqlite3"
    kinds = ["add-idea"] * 6 + ["do-next"] * 6
    ids = _seed_mixed(path, kinds)
    from user_events import delivery
    limit = 4
    with open_journal(path) as j:
        ords = {ev.receipt_id: ev.ordinal for ev in j.events_since_cursor(CONSUMER)}
    exp_ords = [ords[r] for r, k in zip(ids, kinds) if k in delivery.EXPEDITE_KINDS]
    ord_ords = [ords[r] for r, k in zip(ids, kinds) if k not in delivery.EXPEDITE_KINDS]
    assert limit < len(ids), (
        f"precondition: the cap ({limit}) must be BELOW the population "
        f"({len(ids)}) or prioritisation is untested")
    assert exp_ords and ord_ords and max(ord_ords) < min(exp_ords), (
        f"precondition: every ordinary receipt must sit BELOW every expedited "
        f"one (ordinary {ord_ords}, expedited {exp_ords}) — otherwise plain "
        f"ordinal order would pass this test by accident")

    want = [r for r, k in zip(ids, kinds) if k in delivery.EXPEDITE_KINDS][:limit]
    code, out, err = _run(cli, ["expedite", "--journal", str(path),
                                "--applied", str(tmp_path / "applied.md"),
                                "--limit", str(limit)])
    assert code == 0, f"expedite exit {code} (err={err!r})"
    assert _expedited_ids(out) == want, (
        f"under a cap of {limit} the expedited receipts take the slots even "
        f"though the ordinary ones hold the lower ordinals: want {want} "
        f"(ordinals {exp_ords[:limit]}), got {_expedited_ids(out)}")
    over = len(exp_ords) - limit
    assert f"{over} over the cap ({limit})" in err, (
        f"what the cap excluded must be counted out loud, not dropped (#702): "
        f"expected '{over} over the cap ({limit})' in {err!r}")
    # And the excluded ones are not lost: still pending, for the tick.
    code2, out2, _ = _run(cli, ["pending", "--journal", str(path)])
    assert _pending_ids(out2) == ids, (
        f"the cap withholds, it does not consume: want {ids}, got "
        f"{_pending_ids(out2)}")


def test_expedite_does_not_write_the_read_coverage_marker_so_the_tick_is_not_jammed(tmp_path: Path):
    """PRODUCTION LINE: the ABSENCE of a ``_write_pending_read`` call in
    ``cmd_expedite`` (``cmd_pending`` has one; this verb must not).

    If the hook wrote the #658 marker, a hook firing between the coordinator's
    ``pending`` and its ``consume --through N`` would rewrite it and #712's
    ``through == mark['through']`` guard would REFUSE the drain — a hook that
    silently jams the tick it exists to help.  Two assertions: the marker file
    is byte-identical across the hook run, and the bounded consume that follows
    still succeeds.
    """
    cli = _load_cli()
    path = tmp_path / "j.sqlite3"
    ids = _seed_mixed(path, ["do-next", "add-idea", "do-next"])
    code, out, err = _run(cli, ["pending", "--journal", str(path)])
    assert code == 0 and _pending_ids(out) == ids
    marker = cli._pending_read_path(path)
    assert marker.exists(), "precondition: pending must have written the marker"
    before = marker.read_bytes()
    assert before.strip(), "precondition: the marker must be non-empty"

    code2, _, _ = _run(cli, ["expedite", "--journal", str(path),
                             "--applied", str(tmp_path / "applied.md")])
    assert code2 == 0
    assert marker.read_bytes() == before, (
        f"expedite must not touch the #658 read-coverage marker; it changed "
        f"from {before!r} to {marker.read_bytes()!r}, which would make the "
        f"coordinator's next `consume --through` refuse")

    with open_journal(path) as j:
        head = j.head_ordinal()
    code3, out3, err3 = _run(cli, ["consume", "--journal", str(path),
                                   "--applied", str(tmp_path / "applied.md"),
                                   "--through", str(head)])
    assert code3 == 0, (
        f"the tick's bounded consume must still succeed after a hook fired "
        f"mid-sequence; got exit {code3} (err={err3!r})")


def test_expedited_delivered_at_a_pause_is_not_in_the_ticks_act_list_but_is_named(tmp_path: Path):
    """PRODUCTION LINES: ``_prove_drained`` inside ``cmd_expedite`` (the marker
    that lands at the pause) and the ``EXPEDITED`` naming loop in ``cmd_consume``.

    #519/#527: the same instruction delivered twice must be ACTED ON ONCE.  The
    drain's act-list is its ``UNAPPLIED`` lines, so an expedited receipt already
    delivered at a pause must be ABSENT from it while the ordinary receipts of
    the same drain are present — that contrast is what makes the assertion
    discriminating rather than "the list is short".

    And it must not be absent SILENTLY (#136): if the hook's output never
    reached the agent, a bare ``applied N`` would swallow one of his
    instructions, so ``consume`` names each one on an ``EXPEDITED`` line.
    """
    cli = _load_cli()
    path = tmp_path / "j.sqlite3"
    applied = str(tmp_path / "applied.md")
    kinds = ["add-idea", "do-next", "maintenance"]
    ids = _seed_mixed(path, kinds)
    from user_events import delivery
    exp = [r for r, k in zip(ids, kinds) if k in delivery.EXPEDITE_KINDS]
    ordinary = [r for r, k in zip(ids, kinds) if k not in delivery.EXPEDITE_KINDS]
    assert exp and ordinary, "precondition: both classes present, or no contrast"

    code, out, _ = _run(cli, ["expedite", "--journal", str(path),
                              "--applied", applied])
    assert code == 0 and _expedited_ids(out) == exp

    code1, pout, _ = _run(cli, ["pending", "--journal", str(path)])
    assert _pending_ids(pout) == ids, "the hook left everything pending"
    with open_journal(path) as j:
        head = j.head_ordinal()
    code2, cout, cerr = _run(cli, ["consume", "--journal", str(path),
                                   "--applied", applied, "--through", str(head)])
    assert code2 == 0, f"consume exit {code2} (err={cerr!r})"
    assert _unapplied_ids(cout) == ordinary, (
        f"the tick's act-list must hold the ORDINARY receipts only — the "
        f"expedited ones were acted on at the pause: want {ordinary}, got "
        f"{_unapplied_ids(cout)} (expedited were {exp})")
    assert _expedited_ids(cout) == exp, (
        f"consume must NAME each already-delivered expedited receipt, so a "
        f"hook whose output was never seen cannot swallow it in silence: want "
        f"{exp}, got {_expedited_ids(cout)}")

    code3, out3, err3 = _run(cli, ["pending", "--journal", str(path)])
    assert out3 == "", (
        f"and the ordinary drain still drained them — 'it can also be drained "
        f"like normal from the event queue'; pending still shows {out3!r}")


def test_expedite_at_a_second_pause_delivers_nothing_again(tmp_path: Path):
    """PRODUCTION LINE: the ``verdict is apply.Proof.NOT_APPLIED`` test in
    ``cmd_expedite``'s delivery loop.

    A stop hook fires at EVERY pause.  Without the proof gate it would re-emit
    the same text at each one — which is both the #519 double-delivery and a
    hook that talks forever.  The second run must deliver nothing while the
    receipts are still pending, so "nothing to say" is proven distinct from
    "nothing is there".
    """
    cli = _load_cli()
    path = tmp_path / "j.sqlite3"
    applied = str(tmp_path / "applied.md")
    ids = _seed_mixed(path, ["do-next", "add-idea"])
    code, out, _ = _run(cli, ["expedite", "--journal", str(path), "--applied", applied])
    first = _expedited_ids(out)
    assert code == 0 and len(first) == 1, f"precondition: one delivery, got {first}"

    code2, out2, err2 = _run(cli, ["expedite", "--journal", str(path),
                                   "--applied", applied])
    assert code2 == 0
    assert _expedited_ids(out2) == [], (
        f"a second pause must repeat nothing; got {_expedited_ids(out2)}")
    assert "delivered 0 of 1 expedited" in err2 and "applied" in err2, (
        f"and it must SAY it withheld one already-delivered receipt rather "
        f"than fall silent (#136); got {err2!r}")
    code3, out3, _ = _run(cli, ["pending", "--journal", str(path)])
    assert _pending_ids(out3) == ids, (
        f"the receipts are still pending for the tick — the silence is the "
        f"proof gate, not an empty queue: want {ids}, got {_pending_ids(out3)}")


# ---------------------------------------------------------------------------
# #855 — show <ord|receipt-id>... : ordinal resolution, multi-receipt,
#        read-only-by-construction, cursor-stable, tail-survives, count-parity.
#
# These close the five direction-2 candidates the brief names for a verb whose
# subject IS the live journal: truncation invisible to a short fixture,
# zero-denominator green, the cursor moved, the wrong receipt returned, and an
# opened read-write connection.  Each asserts the precondition it depends on at
# runtime so a literal tuned to today's fixture cannot pass vacuously.
# ---------------------------------------------------------------------------


def _receipt_banners(out: str) -> list[str]:
    """The receipt_id of each ``# receipt <id>`` banner show prints, in order."""
    banners = []
    for line in out.splitlines():
        if line.startswith("# receipt "):
            banners.append(line.split()[2])
    return banners


def test_show_long_payload_tail_survives(tmp_path: Path):
    """#855: show prints the FULL payload — the TAIL of a payload longer than
    the preview limit must appear verbatim.  This is the entire point of the
    verb (``pending`` already prints the head) and the direction-1 injection
    target: a show that silently truncates to the preview width passes on a
    short fixture and fails only here.

    The payload length is derived from the CLI's own ``_PREVIEW_LIMIT`` (never
    a literal), so a future bump cannot make a literal fixture pass vacuously.
    The assertion message names the expected tail AND the actual output tail so
    a red distinguishes a truncation from an unrelated format change.

    RED LINE (run): make ``_write_receipt_block`` print ``_preview(payload)``
      instead of the verbatim decoded text.  The tail (past the limit) no
      longer appears → the ``tail in out`` assertion fails, naming both the
      expected tail and the truncated actual.  Production line: the verbatim
      ``out.write(text)`` payload write in ``_write_receipt_block``.
    """
    cli = _load_cli()
    limit = cli._PREVIEW_LIMIT
    path = tmp_path / "tail.sqlite3"
    head = "H" * limit          # fills the preview width exactly
    tail = "TAIL-MARKER-" + "z" * 40   # well past the limit, unique suffix
    payload_text = head + tail
    assert len(payload_text) > limit, (
        f"precondition: payload {len(payload_text)} must exceed the preview "
        f"limit {limit} — else the tail assertion is vacuous")
    seeded = _seed(path, [payload_text.encode("utf-8")])
    rid = seeded[0].receipt_id

    code, out, err = _run(cli, ["show", rid, "--journal", str(path)])
    assert code == 0, f"show must exit 0, got {code} (err={err!r})"
    assert tail in out, (
        f"the payload TAIL (past the {limit}-char preview limit) must appear "
        f"verbatim; expected tail {tail!r} not found in output whose final "
        f"120 chars are {out[-120:]!r} — a truncation to the preview width "
        "drops exactly this")


def test_show_by_ordinal_returns_that_receipts_payload(tmp_path: Path):
    """#855: an all-digits selector is an ORDINAL; show returns THAT ordinal's
    payload, not a neighbour's.  With several receipts in the fixture, an
    ordinal resolution that returned the wrong row (or always row 1) would
    still print *something*, so this asserts the MAPPING: selecting ord=k
    yields payload_k and NOT payload_j for j != k.

    Preconditions derived at runtime: the fixture genuinely holds N>1 receipts
    (from head_ordinal), the ordinals are 1..N (from _ord_fields of a pending
    read — never assumed), and the payloads are pairwise distinct.

    RED LINE (run): make ``_resolve_selector`` ignore the ordinal and always
      read receipt at ordinal 1 (e.g. ``ordinal = 1``), or join on the wrong
      column.  Selecting ord=N returns payload_1, so ``payload_k in out`` fails
      for k != 1 and ``payload_k_absent not in out`` fails for k == 1.
      Production line: the ``SELECT receipt_id FROM events WHERE
      event_ordinal = ?`` join in ``_resolve_selector``.
    """
    cli = _load_cli()
    path = tmp_path / "ordmap.sqlite3"
    payloads = [f'{{"marker":"P{i}"}}'.encode("utf-8") for i in range(4)]
    seeded = _seed(path, payloads)
    n = len(seeded)
    assert n >= 3, "precondition: at least 3 receipts so a wrong-row lookup is catchable"
    with open_journal(path) as j:
        assert j.head_ordinal() == n, "precondition: head equals the seeded count"
    # Ordinals 1..N, derived from a pending read (never assumed).
    code, out_p, _ = _run(cli, ["pending", "--journal", str(path)])
    ords = _ord_fields(out_p)
    assert ords == list(range(1, n + 1)), f"precondition: ordinals 1..{n}; got {ords}"
    payload_by_ord = {ords[i]: payloads[i].decode("utf-8") for i in range(n)}
    # The markers are pairwise distinct — else the cross-check is vacuous.
    assert len(set(payload_by_ord.values())) == n, "precondition: distinct payloads"

    # Select ONE ordinal in the middle; assert its payload appears and the
    # others do NOT (the mapping, not just "something printed").
    k = ords[n // 2]
    code, out, err = _run(cli, ["show", str(k), "--journal", str(path)])
    assert code == 0, f"show {k} exited {code} (err={err!r})"
    want = payload_by_ord[k]
    assert want in out, (
        f"selecting ord={k} must print payload {want!r}; got {out!r}")
    for j, other in payload_by_ord.items():
        if j != k:
            assert other not in out, (
                f"selecting ord={k} must NOT print ord={j}'s payload "
                f"{other!r}; got {out!r}")


def test_show_multi_receipt_prints_one_block_per_selector(tmp_path: Path):
    """#855: ``show <sel>...`` prints exactly one block per selector.  This
    closes two direction-2 inputs at once:

      * zero-denominator green — show on an empty selection "succeeds"; here
        the fixture genuinely holds N receipts (derived from head_ordinal) and
        the count of printed banners MUST equal the count of selectors asked
        for.
      * wrong receipt returned — a multi-select mixing an ordinal and a
        receipt-id must return each SELECTED receipt once, in order, with the
        banner carrying the right id.

    RED LINE (run): make the show loop ``break`` after the first selector, or
      print only the first resolved receipt.  The banner count falls below the
      selector count → the parity assertion fails.  Production line: the
      ``for sel in args.selectors`` loop in cmd_show.
    """
    cli = _load_cli()
    path = tmp_path / "multi.sqlite3"
    payloads = [f'{{"who":"R{i}"}}'.encode("utf-8") for i in range(3)]
    seeded = _seed(path, payloads)
    n = len(seeded)
    with open_journal(path) as j:
        assert j.head_ordinal() == n, "precondition: fixture holds N receipts"
    ids = [r.receipt_id for r in seeded]
    assert len(set(ids)) == n, "precondition: distinct receipt ids"

    # Mix an ordinal (1) and two receipt-ids; expect three blocks in order.
    selectors = ["1", ids[1], ids[2]]
    code, out, err = _run(cli, ["show", *selectors, "--journal", str(path)])
    assert code == 0, f"multi show exited {code} (err={err!r})"
    banners = _receipt_banners(out)
    assert len(banners) == len(selectors), (
        f"show printed {len(banners)} block(s) for {len(selectors)} selector(s) "
        f"— count must match; banners={banners!r}, out={out!r}")
    assert banners == [ids[0], ids[1], ids[2]], (
        f"blocks must appear in selection order with the right ids; "
        f"got {banners!r}")


def test_show_does_not_move_the_cursor(tmp_path: Path):
    """#855: a read must not advance the cursor.  This is the most damaging
    failure available here — a silent advance loses his instructions with a
    zero exit code — so the cursor is asserted byte-identical (ordinal AND
    revision) before and after a show, for BOTH the ordinal and receipt-id
    paths.  A show that read-then-advanced would pass any output assertion.

    PRECONDITION (learned the hard way): the cursor must be at a REAL row, not
    the default origin, or a cursor-bump injection is a no-op against a
    non-existent row and the byte-identical check passes trivially (the
    direction-2 false-green this test was born catching).  So a consume
    advances the cursor to N first; the cursor row now EXISTS (revision>=1,
    ordinal=N), and a bump to it is observable.  The cursor position comes from
    ``j.cursor`` (the real row advance_cursor writes), never faked.

    RED LINE (run): add a write that bumps the cursor inside cmd_show (over a
      WRITING open, so the bump lands).  The byte-identical assertion fails.
      Production line: cmd_show performs no write and opens read-only.
    """
    cli = _load_cli()
    path = tmp_path / "nomove-show.sqlite3"
    applied = tmp_path / "applied.md"
    seeded = _seed(path, [b'{"a":0}', b'{"a":1}', b'{"a":2}'])
    n = len(seeded)
    # Advance the cursor to N so a real row exists (else a bump is a no-op).
    code, out, err = _run(cli, ["consume", "--journal", str(path),
                                "--applied", str(applied)])
    assert code == 0, f"setup consume exited {code} (err={err!r})"
    with open_journal(path) as j:
        before = j.cursor(CONSUMER)
    assert (before.scanned_through_event_ordinal, before.revision) == (n, 1), (
        f"precondition: cursor must sit at a REAL row (ord={n}, rev=1) after "
        f"consume — else a cursor-bump injection is a no-op and the check is "
        f"vacuous; got ord={before.scanned_through_event_ordinal} "
        f"rev={before.revision}")
    rid = seeded[1].receipt_id

    # show by receipt-id, then by ordinal — neither may move the cursor.
    for argv in (["show", rid, "--journal", str(path)],
                 ["show", "1", "--journal", str(path)]):
        code, out, err = _run(cli, argv)
        assert code == 0, f"{argv} exited {code} (err={err!r})"
        with open_journal(path) as j:
            after = j.cursor(CONSUMER)
        assert (after.scanned_through_event_ordinal, after.revision) == (n, 1), (
            f"a show read must leave the cursor byte-identical (expected "
            f"ord={n} rev=1; got ord={after.scanned_through_event_ordinal} "
            f"rev={after.revision}); argv={argv}")


def test_show_journal_is_opened_read_only(tmp_path: Path):
    """#855: show's door (``open_journal_readonly``) opens ``mode=ro`` +
    ``query_only=ON``, so the handle CANNOT mutate the store.  A comment is
    not a check: this asserts a write through that door RAISES, which fails
    the moment someone routes show back through the writing ``open_journal``
    (the original defect — show opened read-write).  This is structural
    read-only-ness, the property the brief says must survive an edit.

    RED LINE (run): change ``open_journal_readonly`` to call ``open_journal``
      (write access).  The INSERT below succeeds → ``sqlite3.OperationalError``
      is not raised → ``pytest.raises`` fails.  Production line: the
      ``Access.READ`` open in ``open_journal_readonly`` (user_events/sqlite.py).
    """
    import pytest
    from user_events.sqlite import open_journal_readonly as _ro

    path = tmp_path / "ro.sqlite3"
    _seed(path, [b'{"x":1}'])  # a real journal, so the read-only open is valid
    assert path.exists(), "precondition: journal exists for a read-only open"

    with _ro(path) as j:
        # A read works (get_receipt is the public read show composes).
        assert j.get_receipt is not None
        # A write MUST be rejected — query_only=ON (mode=ro backs it).  If this
        # opens read-write, the INSERT succeeds and the assertion below fails.
        with pytest.raises(sqlite3.OperationalError):
            j.conn.execute(
                "INSERT INTO meta (key, value) VALUES ('probe', 'x')"
            )


def test_show_unknown_ordinal_exits_usage(tmp_path: Path):
    """#855: an ordinal with no event resolves to "not found" — exit EX_USAGE,
    a stderr line, empty stdout — not a crash and not a silent empty success.

    The precondition (a real journal with a known head, and the probe ordinal
    above it) is derived from head_ordinal so the miss is genuine.

    RED LINE (run): make ``_resolve_selector`` swallow a missing ordinal row
      (return an empty receipt dict instead of None).  The block then prints
      garbage or empty → either the ``out == ''`` or the ``code == EX_USAGE``
      assertion fails.  Production line: the ``if row is None: return None,
      None`` branch in ``_resolve_selector``.
    """
    cli = _load_cli()
    path = tmp_path / "ordmiss.sqlite3"
    _seed(path, [b'{"a":0}', b'{"a":1}'])
    with open_journal(path) as j:
        head = j.head_ordinal()
    probe = head + 10
    assert probe > head, "precondition: probe ordinal is genuinely above the head"

    code, out, err = _run(cli, ["show", str(probe), "--journal", str(path)])
    assert code == cli.EX_USAGE, (
        f"unknown ordinal must exit EX_USAGE({cli.EX_USAGE}); got {code}")
    assert out == "", f"unknown ordinal must write nothing to stdout; got {out!r}"
    assert str(probe) in err, (
        f"the stderr message must name the missing ordinal; got {err!r}")


# ---------------------------------------------------------------------------
# #619 — the cursor must not SILENTLY advance past an unapplied receipt.
#
# The loss: consume advanced the cursor past an UNAPPLIED add-idea whose idea
# never entered the task ledger, and the only record was a transient UNAPPLIED
# line — gone on compaction — while the #526 proof's marker meant a replay
# proved APPLIED and never re-reported.  These tests prove the durable uncleared
# sidecar + the carried-over alarm close it: a drained unapplied receipt is
# recorded durably, re-reported every tick until cleared, and the alarm fires
# only on CARRIED-OVER (not fresh) unapplied so it cannot rubber-stamp.
# ---------------------------------------------------------------------------

def test_unapplied_receipt_recorded_durably_and_rereported_until_cleared(tmp_path: Path):
    """#619 core: a receipt drained unapplied is recorded to the durable
    sidecar, re-reported STILL-UNAPPLIED on the next (idle) tick, and STOPS
    re-reporting once the coordinator confirms filing (``consume --cleared``).

    The durable state is OBSERVED via the production helper that consume uses
    (``_sidecar_ids`` reads ``<journal>.unapplied``), not by trusting a return
    value — so a record that landed in the wrong place is absent and fails here
    (direction-2 strong).  The cursor is asserted MOVED (derived from j.cursor)
    so 'drained' does not rot into 'never drained'.

    RED LINE (run): break the recording seam — make the success-path
      ``_store_unapplied`` call a no-op (e.g. ``if fresh: pass``).  The sidecar
      stays empty → the second consume reads nothing → no STILL-UNAPPLIED, exit
      0 → the ``STILL-UNAPPLIED`` / ``code == EX_UNAPPLIED`` assertions fail.
      Production line injected: the ``_store_unapplied(...)`` call in the
      success block of cmd_consume (and the ``_load_unapplied`` read that feeds
      _emit_uncleared).
    """
    cli = _load_cli()
    path = tmp_path / "p619.sqlite3"
    applied = tmp_path / "applied.md"
    seeded = _seed(path, [b'{"kind":"add-idea","text":"an idea worth keeping"}'],
                   route="/command")
    rid = seeded[0].receipt_id

    # First drain: fresh unapplied → ORDINARY tick → exit 0, UNAPPLIED line, and
    # the receipt is now durably recorded.
    code, out, err = _run(cli, ["consume", "--journal", str(path),
                                "--applied", str(applied)])
    assert code == 0, (
        f"a fresh-unapplied drain is the ordinary tick (exit 0, not the "
        f"alarm); got {code} (out={out!r})")
    assert rid in _unapplied_ids(out), (
        f"the fresh receipt must be listed UNAPPLIED; got {out!r}")
    assert _still_unapplied_ids(out) == [], (
        "a fresh drain must NOT emit STILL-UNAPPLIED — that is the carried-over "
        f"alarm, not the first drain; got {out!r}")
    # Direction-2 strong: OBSERVE the durable sidecar via the production helper.
    assert _sidecar_ids(cli, path) == [rid], (
        "the unapplied receipt must be recorded in the durable sidecar — "
        "without it the next tick cannot re-report it and the idea is lost "
        "the way it was before #619")
    # Precondition (derived): the cursor genuinely advanced past the receipt.
    with open_journal(path) as j:
        assert j.cursor(CONSUMER).scanned_through_event_ordinal >= 1, (
            "precondition: consume must have advanced the cursor — else "
            "'drained' is meaningless")

    # Second (idle) tick: cursor already past the receipt → consumed 0, BUT the
    # carried-over receipt re-reports and the alarm fires.
    code, out, err = _run(cli, ["consume", "--journal", str(path),
                                "--applied", str(applied)])
    assert code == cli.EX_UNAPPLIED, (
        f"a tick with carried-over uncleared unapplied must exit "
        f"EX_UNAPPLIED({cli.EX_UNAPPLIED}) — the missed-idea alarm; got {code}")
    assert rid in _still_unapplied_ids(out), (
        f"the uncleared receipt must re-report STILL-UNAPPLIED; got {out!r}")
    assert "consumed 0 event(s)" in out, (
        f"the idle tick still drains nothing (cursor advanced); got {out!r}")

    # Coordinator confirms filing → the receipt stops re-reporting.
    code, out, err = _run(cli, ["consume", "--cleared", rid,
                                "--journal", str(path),
                                "--applied", str(applied)])
    assert code == 0, (
        f"after clearing the last uncleared receipt, exit returns to 0; "
        f"got {code} (out={out!r})")
    assert rid not in _sidecar_ids(cli, path), (
        "clearing must remove the receipt from the durable sidecar")
    assert any(ln.startswith("CLEARED\t" + rid) for ln in out.splitlines()), (
        f"the clear must name the cleared id; got {out!r}")

    # Third tick: nothing carried, nothing pending → quiet.
    code, out, err = _run(cli, ["consume", "--journal", str(path),
                                "--applied", str(applied)])
    assert code == 0
    assert _still_unapplied_ids(out) == [], (
        f"after clearing, the receipt must NOT re-report; got {out!r}")
    assert out.strip() == "consumed 0 event(s)", (
        f"a fully-cleared idle tick prints only the consumed-0 line; got {out!r}")


def test_fresh_unapplied_is_the_ordinary_tick_no_alarm(tmp_path: Path):
    """#619 no-rubber-stamp: a FRESH unapplied drain (the common case — every
    non-expedited receipt is unapplied on first drain) exits 0 and emits NO
    STILL-UNAPPLIED.  This encodes the measurement that decided the design:
    alarming on fresh unapplied would fire every ordinary tick and become noise.

    RED LINE (run): make _emit_uncleared ignore whether the entries are fresh
      vs carried (e.g. feed the just-recorded fresh list into it).  A fresh
      drain would then emit STILL-UNAPPLIED and exit EX_UNAPPLIED → the
      ``code == 0`` and ``_still_unapplied_ids == []`` assertions fail.
      Production line: the separation between the fresh ``UNAPPLIED`` lines and
      the ``_emit_uncleared(uncleared)`` carried-over block in cmd_consume.
    """
    cli = _load_cli()
    path = tmp_path / "fresh.sqlite3"
    applied = tmp_path / "applied.md"
    seeded = _seed(path, [b'{"kind":"add-idea","text":"x"}', b'{"kind":"chat","text":"y"}'],
                   route="/command")
    rids = sorted(r.receipt_id for r in seeded)

    code, out, err = _run(cli, ["consume", "--journal", str(path),
                                "--applied", str(applied)])
    assert code == 0, (
        f"a fresh-unapplied drain is the ordinary tick → exit 0; got {code}")
    assert sorted(_unapplied_ids(out)) == rids, (
        f"both fresh receipts are listed UNAPPLIED; got {out!r}")
    assert _still_unapplied_ids(out) == [], (
        f"NO STILL-UNAPPLIED on a fresh drain (no rubber stamp); got {out!r}")


def test_force_unapplied_records_nothing_so_no_rereport(tmp_path: Path):
    """#619 escape hatch: ``--force-unapplied`` drains normally (cursor advances,
    UNAPPLIED lines print, proof still marks) but records NOTHING to the sidecar
    — so a later idle tick does NOT re-report.  This is the bootstrap/handled-
    by-inspection escape; the safe default records everything.

    RED LINE (run): make --force-unapplied still record (e.g. delete the
      ``if not args.force_unapplied:`` guard around _store_unapplied).  The
      sidecar gains the id → the second consume re-reports it → the
      ``_sidecar_ids == []`` and ``no STILL-UNAPPLIED`` assertions fail.
      Production line: the ``if not args.force_unapplied:`` guard in cmd_consume.
    """
    cli = _load_cli()
    path = tmp_path / "force.sqlite3"
    applied = tmp_path / "applied.md"
    seeded = _seed(path, [b'{"kind":"add-idea","text":"forced"}'], route="/command")
    rid = seeded[0].receipt_id

    code, out, err = _run(cli, ["consume", "--force-unapplied",
                                "--journal", str(path),
                                "--applied", str(applied)])
    assert code == 0, f"forced consume must exit 0; got {code} (err={err!r})"
    assert rid in _unapplied_ids(out), (
        f"force does not suppress the UNAPPLIED report (only the recording); "
        f"got {out!r}")
    # Direction-2 strong: observe the durable sidecar is EMPTY.
    assert _sidecar_ids(cli, path) == [], (
        "--force-unapplied must record nothing — a record here would make a "
        "later tick re-report a receipt the coordinator chose not to track")
    # The marker still landed (proof ran) and the cursor advanced.
    assert applied.exists(), "precondition: the proof still ran under --force"
    with open_journal(path) as j:
        assert j.cursor(CONSUMER).scanned_through_event_ordinal >= 1

    # Later idle tick: nothing carried → quiet.
    code, out, err = _run(cli, ["consume", "--journal", str(path),
                                "--applied", str(applied)])
    assert code == 0
    assert _still_unapplied_ids(out) == [], (
        f"a force-drained receipt must NOT re-report; got {out!r}")


def test_consumed_zero_with_carried_over_is_not_quiet(tmp_path: Path):
    """#619 / #868 degrade-to-zero edge: an idle tick (``consumed 0``) that has
    CARRIED-OVER uncleared receipts is NOT quiet — it re-reports them and exits
    EX_UNAPPLIED.  'Nothing needs you' holds only when nothing is carried over;
    silencing an idle tick with at-risk ideas is the original loss.

    RED LINE (run): make the consumed-0 early return bypass _emit_uncleared
      (restore the pre-#619 ``return EX_OK``).  The carried-over receipt is
      silently dropped on the idle tick → the ``STILL-UNAPPLIED`` / ``code ==
      EX_UNAPPLIED`` assertions fail.  Production line: the
      ``_emit_uncleared(out, uncleared)`` call on the consumed-0 path.
    """
    cli = _load_cli()
    path = tmp_path / "idle.sqlite3"
    applied = tmp_path / "applied.md"
    seeded = _seed(path, [b'{"kind":"add-idea","text":"idle-but-at-risk"}'],
                   route="/command")
    rid = seeded[0].receipt_id
    _run(cli, ["consume", "--journal", str(path), "--applied", str(applied)])
    assert _sidecar_ids(cli, path) == [rid], "precondition: rid is carried over"

    # Idle tick: nothing to drain, but rid is carried over → NOT quiet.
    code, out, err = _run(cli, ["consume", "--journal", str(path),
                                "--applied", str(applied)])
    assert code == cli.EX_UNAPPLIED, (
        f"an idle tick with carried-over unapplied must alarm; got {code}")
    assert rid in _still_unapplied_ids(out), (
        f"the carried-over receipt must re-report on the idle tick; got {out!r}")
    assert "consumed 0 event(s)" in out


def test_sidecar_is_bound_to_its_journal(tmp_path: Path):
    """#619 / #658 binding: the uncleared sidecar is bound to its journal by
    journal_id, so a sidecar left by a DIFFERENT journal (a stale checkout's
    file) cannot satisfy this one — its uncleared ids do not bleed across.

    RED LINE (run): make _load_unapplied ignore the journal_id check (return
      entries regardless of mismatch).  Journal B's consume would then load A's
      carried-over ids → the ``B's second consume sees nothing`` assertion fails.
      Production line: the ``if data.get('journal_id') != journal_id: return []``
      guard in _load_unapplied.
    """
    cli = _load_cli()
    path_a = tmp_path / "a.sqlite3"
    path_b = tmp_path / "b.sqlite3"
    applied = tmp_path / "applied.md"
    seeded_a = _seed(path_a, [b'{"kind":"add-idea","text":"a"}'], route="/command")
    rid_a = seeded_a[0].receipt_id
    _seed(path_b, [b'{"kind":"add-idea","text":"b"}'], route="/command")
    # Distinct journal_ids (minted at creation) — derived, never assumed.
    with open_journal(path_a) as ja, open_journal(path_b) as jb:
        assert ja.journal_id != jb.journal_id, (
            "precondition: the two journals must have distinct ids for the "
            "binding to mean anything")

    # Drain A (records rid_a to A's sidecar), then drain B.
    _run(cli, ["consume", "--journal", str(path_a), "--applied", str(applied)])
    _run(cli, ["consume", "--journal", str(path_b), "--applied", str(applied)])
    assert _sidecar_ids(cli, path_a) == [rid_a]
    # B's idle tick must NOT see A's carried-over receipt.
    code, out, err = _run(cli, ["consume", "--journal", str(path_b),
                                "--applied", str(applied)])
    assert rid_a not in _still_unapplied_ids(out), (
        f"A's uncleared receipt must not bleed into B's consume (sidecar is "
        f"journal-bound); got {out!r}")


# ---------------------------------------------------------------------------
# #808 — a split applied-ledger (journal in one tree, applied in another) is
# refused before any write.  The applied-ledger is the dedup record for ONE
# journal; a split writes that journal's markers into the wrong tree and is the
# shape that left actor=coordinator-drain files in three reaped lane worktrees.
# ---------------------------------------------------------------------------

def test_consume_refuses_split_applied_ledger(tmp_path: Path):
    """consume refuses when --applied is not co-located with --journal (#808).

    The journal and its applied-ledger are one unit — the ledger's markers
    prove "this receipt was drained from THIS journal".  A lane running a bare
    ``consume`` from a cwd that is the MAIN checkout (the harness default,
    #882) while its own journal lives in its worktree resolves the two
    CWD-relative defaults to DIFFERENT trees: the journal from the worktree's
    ``--journal`` (or a fixture), the applied-ledger from the main checkout's
    ``.dreamwork/applied.md``.  That split stamps ``coordinator-drain`` into
    the wrong dedup file — the defect this task exists to close.

    RED LINE (run): delete the ``_refuse_split_applied`` call in cmd_consume
      (the ``if args.cleared is None`` block).  The split consume then proceeds,
      writes the marker into the wrong tree, and the refusal assertions fail.
      Production line: ``_refuse_split_applied`` in dev/journal_consume.py,
      invoked from ``cmd_consume`` after the journal-existence early return.
    """
    cli = _load_cli()
    # Two trees: the journal here, the applied-ledger there.  Different parent
    # directories is the split.  The seed runs BEFORE the guard sees the paths
    # (the guard only checks parent dirs, never opens the journal).
    checkout_a = tmp_path / "worktree"
    checkout_b = tmp_path / "main"
    checkout_a.mkdir()
    checkout_b.mkdir()
    journal = checkout_a / "user-events.sqlite3"
    applied = checkout_b / "applied.md"
    # Precondition: the parents genuinely differ (derived, not assumed) — a
    # guard that compares resolved paths must see two distinct directories.
    assert journal.resolve().parent != applied.resolve().parent, (
        "precondition: journal and applied must live in different directories "
        "for the split to be real")
    seeded = _seed(journal, [b'{"kind":"add-idea","text":"x"}'], route="/command")

    code, out, err = _run(cli, ["consume", "--journal", str(journal),
                                "--applied", str(applied)])
    # The refusal: EX_USAGE, names the split, names the remedy.
    assert code == 64, (
        f"a split applied-ledger must refuse EX_USAGE (64); got {code} "
        f"(err={err!r})")
    assert "refused" in err, (
        f"the refusal must say 'refused'; got {err!r}")
    assert "same directory" in err, (
        f"the refusal must name the co-location requirement; got {err!r}")
    assert "coordinator-drain" in err or "#808" in err, (
        f"the refusal must name the defect class it closes; got {err!r}")
    # The remedy names the journal's directory as where applied should live.
    assert "applied.md" in err, (
        f"the refusal must name the remedy (point --applied beside the "
        f"journal); got {err!r}")
    # The cursor was NOT advanced (no drain ran).
    with open_journal(journal) as j:
        cur = j.cursor(CONSUMER)
    assert cur.scanned_through_event_ordinal == 0, (
        f"a refused consume must not advance the cursor; got "
        f"{cur.scanned_through_event_ordinal}")
    # NEITHER tree's applied-ledger was written — no marker stamped anywhere.
    assert not applied.exists(), (
        f"the wrong-tree applied-ledger must not be created; {applied} exists")
    worktree_applied = checkout_a / "applied.md"
    assert not worktree_applied.exists(), (
        f"no applied-ledger should appear in the worktree either; "
        f"{worktree_applied} exists")


def test_consume_allows_colocated_applied_ledger(tmp_path: Path):
    """consume proceeds when --applied IS co-located with --journal (#808 parity).

    The guard must not false-refuse the ordinary case: journal and applied-ledger
    in the same directory (the shape every existing test uses, and the shape the
    coordinator's tick produces).  This is the negative control for the guard —
    without it, a guard that refuses everything would pass the split test above.
    """
    cli = _load_cli()
    journal = tmp_path / "consume.sqlite3"
    applied = tmp_path / "applied.md"
    seeded = _seed(journal, [b'{"kind":"add-idea","text":"x"}'], route="/command")
    # Precondition: co-located (same parent dir), derived not assumed.
    assert journal.resolve().parent == applied.resolve().parent, (
        "precondition: journal and applied must share a directory")

    code, out, err = _run(cli, ["consume", "--journal", str(journal),
                                "--applied", str(applied)])
    assert code == 0, (
        f"a co-located applied-ledger must proceed (exit 0); got {code} "
        f"(err={err!r})")
    assert "consumed 1 event(s)" in out, (
        f"the drain must run on a co-located ledger; got {out!r}")


def test_expedite_refuses_split_applied_ledger(tmp_path: Path):
    """expedite refuses the same split — it also stamps coordinator-drain (#808).

    expedite routes every delivered receipt through apply.reconcile (#526), the
    same write consume makes.  A split is refused before any delivery.

    RED LINE (run): delete the ``_refuse_split_applied`` call in cmd_expedite.
      The split expedite then delivers and writes the wrong tree's applied-ledger.
      Production line: ``_refuse_split_applied``, invoked from ``cmd_expedite``
      after the journal-existence early return.
    """
    cli = _load_cli()
    checkout_a = tmp_path / "worktree"
    checkout_b = tmp_path / "main"
    checkout_a.mkdir()
    checkout_b.mkdir()
    journal = checkout_a / "user-events.sqlite3"
    applied = checkout_b / "applied.md"
    assert journal.resolve().parent != applied.resolve().parent, (
        "precondition: journal and applied must live in different directories")
    _seed(journal,
          [b'{"kind":"do-next","text":"urgent"}'], route="/command")

    code, out, err = _run(cli, ["expedite", "--journal", str(journal),
                                "--applied", str(applied)])
    assert code == 64, (
        f"a split applied-ledger must refuse EX_USAGE (64) on expedite too; "
        f"got {code} (err={err!r})")
    assert "refused" in err and "same directory" in err, (
        f"the refusal must name the co-location requirement; got {err!r}")
    assert not applied.exists(), (
        f"the wrong-tree applied-ledger must not be created by expedite")
