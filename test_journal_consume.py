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

from user_events.sqlite import Envelope, open_journal

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
        code, out, err = _run(cli, ["consume", "--journal", str(path),
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

