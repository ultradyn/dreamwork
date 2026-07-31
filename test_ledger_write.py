"""Red-first tests for ledger_write — the MINIMAL store write verbs (#294 inc 9).

file_task + land_task are the two real writes the loop does (file a new task,
fold a landed one), pointed at the store so the live cutover does not strand
them. Each test names the PRODUCTION LINE its red-proof targets, derives its
preconditions at runtime, and was red-proved: the named line was injected,
the test failed, and the source restored byte-identical.

Named production lines whose change must red each test:

- file_task's INSERT + _append_chained_event inside one BEGIN IMMEDIATE … COMMIT
      → test_file_is_one_transaction_task_row_rolled_back_with_its_event
- file_task returns cur.lastrowid (the AUTOINCREMENT-allocated id)
      → test_file_allocates_the_seeded_next_id
- land_task's UPDATE … WHERE state = 'open' (the CAS)
      → test_land_cas_refuses_a_second_landing / _a_nonexistent_id
- _append_chained_event's prev = _last_event_hash(conn) + hash_event(...)
      → test_chain_verifies_over_file_and_land_events
- land_task's body append (UPDATE task SET body = body || note)
      → test_land_appends_note_to_body
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sqlite3
from pathlib import Path

import pytest

import ledger_store
import ledger_write

REPO = Path(__file__).resolve().parent
MIGRATE_CLI = REPO / "ud-dw-tasks-migrate"


def _load_migrate():
    """Load the extensionless migrate CLI to reach verify_task_event_chain."""
    loader = importlib.machinery.SourceFileLoader(
        "ud_dw_tasks_migrate_write", str(MIGRATE_CLI))
    spec = importlib.util.spec_from_loader("ud_dw_tasks_migrate_write", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture
def store(tmp_path):
    """A scratch store seeded at a known mark (closed by the fixture)."""
    s = ledger_store.open_store(tmp_path / "l.sqlite3", seed_next_id=500)
    yield s
    s.close()


@pytest.fixture
def migrate():
    return _load_migrate()


# ---------------------------------------------------------------------------
# file — allocates the seeded next id, never collides (G1/G2/G3)
# ---------------------------------------------------------------------------

def test_file_allocates_the_seeded_next_id(store):
    """Production line: ``cur.lastrowid`` returned by file_task.

    file_task must return the AUTOINCREMENT-allocated id, never an id chosen
    by the caller. Break by returning a hardcoded id — it would not match the
    seeded next id and the second file would collide with the first.
    """
    # Derive the mark at runtime: the store's next id IS the expected id.
    mark = store.next_id()
    assert mark > 1, f"precondition: non-trivial next id, got {mark}"

    first = ledger_write.file_task(store, "first task", "body one",
                                    at="2026-07-29T10:00:00Z")
    assert first == mark, (
        f"file_task returned {first}, expected the seeded next id {mark}")

    second = ledger_write.file_task(store, "second task", "body two",
                                     at="2026-07-29T10:00:01Z")
    assert second == mark + 1, (
        f"second file returned {second}, expected {mark + 1} — "
        "the sequence must advance and never collide")


def test_file_id_never_collides_with_a_higher_imported_row(tmp_path):
    """Production line: AUTOINCREMENT on task.id (R1) + file_task's lastrowid.

    An import inserts explicit-id rows; a subsequent file must allocate an id
    strictly above the imported high-water mark, never colliding. Break by
    seeding below the imported id and allocating from the seed — collision.
    """
    s = ledger_store.open_store(tmp_path / "l.sqlite3", seed_next_id=10)
    try:
        # Simulate an import: an explicit-id row above the seed.
        s.conn.execute(
            "INSERT INTO task(id, state, title, body) "
            "VALUES (50, 'open', 'imported', 'b')")
        s.conn.commit()
        hw = s.sequence_high_water("task")
        assert hw == 50, f"precondition: AUTOINCREMENT tracks the explicit id, got {hw}"

        new_id = ledger_write.file_task(s, "filed after import", "body",
                                         at="2026-07-29T10:00:00Z")
        assert new_id > 50, (
            f"filed id {new_id} must exceed the imported high-water 50 — "
            "a collision would reuse a permanent id")
        # The filed id is not 50 (the imported row's id).
        assert new_id != 50
    finally:
        s.close()


# ---------------------------------------------------------------------------
# file — one transaction (G4): a task row with no filed event cannot exist
# ---------------------------------------------------------------------------

def test_file_is_one_transaction_task_row_rolled_back_with_its_event(store):
    """Production line: ``conn.execute("ROLLBACK")`` in file_task's except block.

    Sabotage the event INSERT by removing the filed cause from the task_cause
    lookup (the event's cause REFERENCES task_cause). With the ROLLBACK
    present, file_task raises AND leaves no task row. Break by removing the
    ROLLBACK — the task row survives in the open transaction, so the
    count-is-zero assertion fails.
    """
    # Remove the cause the filed event uses, so its INSERT fails the FK.
    store.conn.execute(
        "DELETE FROM task_cause WHERE cause = 'filed_from_command'")
    store.conn.commit()
    # Precondition: the cause is genuinely gone (the FK will fire).
    row = store.conn.execute(
        "SELECT COUNT(*) FROM task_cause WHERE cause = 'filed_from_command'"
    ).fetchone()
    assert row[0] == 0, "precondition: filed cause must be absent for the FK to fire"

    with pytest.raises(sqlite3.IntegrityError):
        ledger_write.file_task(store, "will not persist", "body",
                                at="2026-07-29T10:00:00Z")

    # Neither the task row nor the event survived the rolled-back transaction.
    n_tasks = store.conn.execute("SELECT COUNT(*) FROM task").fetchone()[0]
    assert n_tasks == 0, (
        f"a failed file left {n_tasks} task row(s) — the transition must be "
        "one transaction (G4): a task row with no filed event cannot exist")
    n_events = store.conn.execute("SELECT COUNT(*) FROM task_event").fetchone()[0]
    assert n_events == 0


# ---------------------------------------------------------------------------
# file — the filed event records NULL → open
# ---------------------------------------------------------------------------

def test_file_records_a_filed_event_null_to_open(store):
    """Production line: _append_chained_event's from_state=None, to_state='open'."""
    new_id = ledger_write.file_task(store, "a task", "its body",
                                     actor="coordinator",
                                     at="2026-07-29T10:00:00Z")
    rows = store.conn.execute(
        "SELECT cause, from_state, to_state, actor FROM task_event "
        "WHERE task_id = ?", (new_id,)).fetchall()
    assert len(rows) == 1
    cause, frm, to, actor = rows[0]
    assert cause == "filed_from_command"
    assert frm is None, f"filed event from_state must be NULL, got {frm!r}"
    assert to == "open"
    assert actor == "coordinator"


# ---------------------------------------------------------------------------
# land — CAS: open → landed
# ---------------------------------------------------------------------------

def test_land_flips_an_open_task_to_landed(store):
    """Production line: land_task's UPDATE … SET state='landed' WHERE state='open'."""
    tid = ledger_write.file_task(store, "to land", "body",
                                  at="2026-07-29T10:00:00Z")
    ledger_write.land_task(store, tid, note="done",
                            at="2026-07-29T11:00:00Z")
    state = store.conn.execute(
        "SELECT state FROM task WHERE id = ?", (tid,)).fetchone()[0]
    assert state == "landed"


def test_land_cas_refuses_a_second_landing(store):
    """Production line: ``cur.rowcount == 0`` → BadState in land_task.

    Landing an already-landed task matches zero rows in the CAS UPDATE and
    must refuse. Break by treating rowcount 0 as success — a double-land
    would append a second landed event for an already-landed task.
    """
    tid = ledger_write.file_task(store, "land me twice", "body",
                                  at="2026-07-29T10:00:00Z")
    ledger_write.land_task(store, tid, at="2026-07-29T11:00:00Z")
    with pytest.raises(ledger_write.BadState, match="not 'open'"):
        ledger_write.land_task(store, tid, at="2026-07-29T12:00:00Z")
    # Exactly one landed event — the refused second land wrote nothing.
    n = store.conn.execute(
        "SELECT COUNT(*) FROM task_event WHERE task_id = ? AND cause = 'landed'",
        (tid,)).fetchone()[0]
    assert n == 1, f"expected one landed event, got {n}"


def test_land_refuses_a_nonexistent_id(store):
    """Production line: ``row is None`` → TaskNotFound in land_task."""
    with pytest.raises(ledger_write.TaskNotFound, match="no such task"):
        ledger_write.land_task(store, 99999, at="2026-07-29T11:00:00Z")
    # No event was written for the phantom id.
    n = store.conn.execute(
        "SELECT COUNT(*) FROM task_event WHERE task_id = 99999").fetchone()[0]
    assert n == 0


# ---------------------------------------------------------------------------
# land — appends note to body (bodies accumulate notes across a task's life)
# ---------------------------------------------------------------------------

def test_land_appends_note_to_body(store):
    """Production line: ``UPDATE task SET body = body || note`` in land_task."""
    tid = ledger_write.file_task(store, "note me", "original body",
                                  at="2026-07-29T10:00:00Z")
    ledger_write.land_task(store, tid, note="landed cleanly",
                            at="2026-07-29T11:00:00Z")
    body = store.conn.execute(
        "SELECT body FROM task WHERE id = ?", (tid,)).fetchone()[0]
    assert "original body" in body, "the original body must survive"
    assert "landed cleanly" in body, "the note must be appended to the body"


# ---------------------------------------------------------------------------
# land's event chains — verify_task_event_chain passes; a mutation breaks it
# ---------------------------------------------------------------------------

def test_chain_verifies_over_file_and_land_events(store, migrate):
    """Production line: _append_chained_event's prev = _last_event_hash(conn).

    file + land append two chained events. verify_task_event_chain (in
    ud-dw-tasks-migrate) must pass over them — a live event chains exactly
    like a synthetic one. Break by chaining from genesis always (ignoring the
    last event) — the second event's prev_hash breaks the chain.
    """
    t1 = ledger_write.file_task(store, "first", "b1", at="2026-07-29T10:00:00Z")
    t2 = ledger_write.file_task(store, "second", "b2", at="2026-07-29T10:00:01Z")
    ledger_write.land_task(store, t1, note="done", at="2026-07-29T11:00:00Z")

    db_path = str(store.path)
    # Precondition: there are live (non-migration) events to verify.
    n = store.conn.execute("SELECT COUNT(*) FROM task_event").fetchone()[0]
    assert n >= 3, f"precondition: need >=3 events, got {n}"

    assert migrate.verify_task_event_chain(db_path) == [], (
        "clean chain (file + file + land) must verify")

    # Mutate one row — the chain must break at that row.
    store.conn.execute(
        "UPDATE task_event SET detail = detail || ' TAMPERED' "
        "WHERE ordinal = (SELECT MIN(ordinal) FROM task_event)")
    store.conn.commit()
    fails = migrate.verify_task_event_chain(db_path)
    assert fails, (
        "mutated event row must break the chain — a verifier that does not "
        "recompute the hash from canonical bytes is a silent forgery")


# ---------------------------------------------------------------------------
# note — appends to body (any state), no event, TaskNotFound on a missing id
#
# Named production lines whose change must red each test:
#
# - note_task's UPDATE task SET body = body || note WHERE id = ?
#       → test_note_appends_to_body_in_any_state
# - note_task's cur.rowcount == 0 → TaskNotFound
#       → test_note_raises_task_not_found
# - note_task writes NO task_event row (a note is not a transition)
#       → test_note_writes_no_event_chain_verifies
# ---------------------------------------------------------------------------

def test_note_appends_to_body_in_any_state(store):
    """Production line: ``UPDATE task SET body = body || note`` in note_task.

    A note appends to the body in ANY state — both an open and a landed task
    get annotated (the coordinator notes open tasks mid-flight and landed
    tasks in retrospect). Derive the before-body at runtime and assert the
    note lands in it while the original body survives. Break by making the
    UPDATE a no-op (e.g. ``body = body``) — the note would not appear.
    """
    # Derive distinct bodies so the assertion is not vacuous.
    open_id = ledger_write.file_task(store, "open task", "open body",
                                      at="2026-07-29T10:00:00Z")
    landed_id = ledger_write.file_task(store, "landed task", "landed body",
                                        at="2026-07-29T10:00:01Z")
    ledger_write.land_task(store, landed_id, at="2026-07-29T11:00:00Z")

    before_open = store.conn.execute(
        "SELECT body FROM task WHERE id = ?", (open_id,)).fetchone()[0]
    before_landed = store.conn.execute(
        "SELECT body FROM task WHERE id = ?", (landed_id,)).fetchone()[0]
    # Precondition: the two bodies differ (a shared body makes the per-task
    # append assertions vacuous).
    assert before_open != before_landed, "fixture: the two bodies must differ"

    ledger_write.note_task(store, open_id, "an open note")
    ledger_write.note_task(store, landed_id, "a landed note")

    after_open = store.conn.execute(
        "SELECT body FROM task WHERE id = ?", (open_id,)).fetchone()[0]
    after_landed = store.conn.execute(
        "SELECT body FROM task WHERE id = ?", (landed_id,)).fetchone()[0]
    assert "open body" in after_open and "an open note" in after_open, (
        "the open task's body must keep its text and gain the note")
    assert "landed body" in after_landed and "a landed note" in after_landed, (
        "the landed task's body must keep its text and gain the note")
    # The note did not migrate into the wrong task.
    assert "a landed note" not in after_open
    assert "an open note" not in after_landed


def test_note_raises_task_not_found(store):
    """Production line: ``cur.rowcount == 0`` → TaskNotFound in note_task.

    Annotating a missing id matches zero rows in the UPDATE and must refuse.
    Break by treating rowcount 0 as success — the note would silently vanish
    and no exception would surface.
    """
    # Precondition: 99999 genuinely does not exist.
    row = store.conn.execute(
        "SELECT 1 FROM task WHERE id = 99999").fetchone()
    assert row is None, "precondition: id 99999 must not exist"

    with pytest.raises(ledger_write.TaskNotFound, match="no such task"):
        ledger_write.note_task(store, 99999, "nowhere to land")
    # No event was written for the phantom id.
    n = store.conn.execute(
        "SELECT COUNT(*) FROM task_event WHERE task_id = 99999").fetchone()[0]
    assert n == 0


def test_note_writes_no_event_chain_verifies(store, migrate):
    """Production line: note_task appends to body WITHOUT a task_event row.

    A note is not a state transition (#264's boundary), so note_task writes
    no event — the body is the annotation trail. Break by adding an event in
    note_task and the event-count assertion fails (a note must not invent a
    transition). The chain must still verify: it is untouched, so an ordinal-
    order append of nothing leaves every hash intact.
    """
    tid = ledger_write.file_task(store, "to note", "body",
                                  at="2026-07-29T10:00:00Z")
    n_before = store.conn.execute(
        "SELECT COUNT(*) FROM task_event WHERE task_id = ?", (tid,)).fetchone()[0]

    ledger_write.note_task(store, tid, "a mid-task note")

    n_after = store.conn.execute(
        "SELECT COUNT(*) FROM task_event WHERE task_id = ?", (tid,)).fetchone()[0]
    assert n_after == n_before, (
        f"a note must write no event (got {n_before} → {n_after}); a note is "
        "not a transition, so the chain records nothing")

    # The chain still verifies over the untouched events.
    db_path = str(store.path)
    assert migrate.verify_task_event_chain(db_path) == [], (
        "the untouched chain must verify — note_task must not corrupt it")

    # And the note did land in the body (sanity: the no-event choice did not
    # also drop the body append).
    body = store.conn.execute(
        "SELECT body FROM task WHERE id = ?", (tid,)).fetchone()[0]
    assert "a mid-task note" in body


# ---------------------------------------------------------------------------
# record_review_decision — record an artifact's review answer
# (NOT a task; no task_event chain — questions have no task id)
#
# Named production lines whose change must red each test:
#
# - record_review_decision's INSERT OR REPLACE INTO review_decision
#       → test_record_writes_the_decision_row
# - record_review_decision's `decision not in REVIEW_DECISIONS` validation
#       → test_record_refuses_a_bad_decision
# - the conflict gate's cross-question final-decision raise
#       → test_record_conflicts_on_a_different_title_final_decision
# - the gate does NOT raise on a same-title overwrite
#       → test_record_allows_a_same_title_re_decision
# - the gate's `ex_decision != "pending"` condition (pending is provisional)
#       → test_record_allows_a_pending_to_decided_transition
# ---------------------------------------------------------------------------

def test_record_writes_the_decision_row(store):
    """Production line: the INSERT OR REPLACE into review_decision.

    A first decision lands all five columns and writes NO task_event row (a
    review decision is not a task — #264's boundary). Break by removing the
    INSERT — no row lands, so the assertions fail.
    """
    n_before = store.conn.execute(
        "SELECT COUNT(*) FROM review_decision").fetchone()[0]
    assert n_before == 0, "precondition: review_decision starts empty"

    ledger_write.record_review_decision(
        store, "art-1", "Is the design sound?", "accepted",
        actor="coordinator", at="2026-07-29T10:00:00Z")

    row = store.conn.execute(
        "SELECT artifact, question_title, decision, decided_at, actor "
        "FROM review_decision WHERE artifact = 'art-1'").fetchone()
    assert row == (
        "art-1", "Is the design sound?", "accepted",
        "2026-07-29T10:00:00Z", "coordinator"), f"row mismatch: {row}"
    # A review decision must not touch the task_event chain.
    n_events = store.conn.execute(
        "SELECT COUNT(*) FROM task_event").fetchone()[0]
    assert n_events == 0, (
        f"a review decision wrote {n_events} task_event row(s); it is not a "
        "task and has no task id")


def test_record_refuses_a_bad_decision(store):
    """Production line: `if decision not in REVIEW_DECISIONS: raise WriteError`.

    A decision outside the closed set is refused. Derive a value NOT in the
    set at runtime so the check is not tuned to today's literal. Break by
    accepting any string — no WriteError surfaces.
    """
    bad = "maybe"
    assert bad not in ledger_store.REVIEW_DECISIONS, (
        "precondition: the bad value must be outside the closed set")

    with pytest.raises(ledger_write.WriteError, match="decision must be one of"):
        ledger_write.record_review_decision(
            store, "art-bad", "q", bad, actor="coordinator")
    n = store.conn.execute(
        "SELECT COUNT(*) FROM review_decision").fetchone()[0]
    assert n == 0, "a refused decision must write nothing"


def test_record_conflicts_on_a_different_title_final_decision(store):
    """Production line: the conflict gate's cross-question final-decision raise.

    A decided artifact (non-pending) under one title must refuse a decision
    under a DIFFERENT title. Assert the precondition (the existing row is
    decided, titles differ) at runtime. Break by disabling the raise — the
    INSERT OR REPLACE would silently overwrite and no DecisionConflict fires.
    """
    ledger_write.record_review_decision(
        store, "art-c", "Q-original", "accepted",
        actor="coordinator", at="2026-07-29T10:00:00Z")
    # Precondition: existing row is final and titles differ.
    ex = store.conn.execute(
        "SELECT question_title, decision FROM review_decision "
        "WHERE artifact = 'art-c'").fetchone()
    assert ex == ("Q-original", "accepted"), (
        f"precondition: need a decided row, got {ex}")
    assert ex[1] != "pending", "precondition: existing decision must be final"
    new_title = "Q-different"
    assert new_title != ex[0], "precondition: titles must differ"

    with pytest.raises(ledger_write.DecisionConflict, match="already decided"):
        ledger_write.record_review_decision(
            store, "art-c", new_title, "rejected", actor="coordinator")
    # The conflict left the original decision intact.
    row = store.conn.execute(
        "SELECT question_title, decision FROM review_decision "
        "WHERE artifact = 'art-c'").fetchone()
    assert row == ("Q-original", "accepted"), (
        f"conflict must not overwrite; got {row}")


def test_record_allows_a_same_title_re_decision(store):
    """Production line: the gate does NOT raise on a same-title overwrite.

    Re-deciding the same artifact under the same question is allowed (a mind
    changed). Break by making the gate refuse ANY existing row — the same-
    title re-decision raises instead of overwriting.
    """
    title = "Q-shared"
    ledger_write.record_review_decision(
        store, "art-s", title, "pending",
        actor="coordinator", at="2026-07-29T10:00:00Z")
    ex = store.conn.execute(
        "SELECT question_title FROM review_decision WHERE artifact='art-s'"
    ).fetchone()
    assert ex == (title,), "precondition: the existing row shares the title"

    ledger_write.record_review_decision(
        store, "art-s", title, "accepted",
        actor="coordinator", at="2026-07-29T11:00:00Z")
    row = store.conn.execute(
        "SELECT question_title, decision, decided_at FROM review_decision "
        "WHERE artifact = 'art-s'").fetchone()
    assert row == (title, "accepted", "2026-07-29T11:00:00Z"), (
        f"same-title re-decision must overwrite; got {row}")


def test_record_allows_a_pending_to_decided_transition(store):
    """Production line: `ex_decision != "pending"` in the gate condition.

    A 'pending' row is provisional, so overwriting it with a decision — even
    under a DIFFERENT title — is allowed. A different title is what targets
    the pending condition: same-title would pass even if the pending check
    were broken. Assert the precondition (existing is pending) at runtime.
    Break by treating pending as final — the transition raises.
    """
    ledger_write.record_review_decision(
        store, "art-p", "Q-pending", "pending",
        actor="coordinator", at="2026-07-29T10:00:00Z")
    ex = store.conn.execute(
        "SELECT question_title, decision FROM review_decision "
        "WHERE artifact='art-p'").fetchone()
    assert ex == ("Q-pending", "pending"), (
        f"precondition: need a pending row, got {ex}")

    ledger_write.record_review_decision(
        store, "art-p", "Q-decided", "accepted",
        actor="coordinator", at="2026-07-29T11:00:00Z")
    row = store.conn.execute(
        "SELECT question_title, decision FROM review_decision "
        "WHERE artifact = 'art-p'").fetchone()
    assert row == ("Q-decided", "accepted"), (
        f"pending→decided must overwrite; got {row}")


# ---------------------------------------------------------------------------
# #681 — file_task rejects bad enum columns naming the column + the LIVE
# allowed set, not a sqlite IntegrityError that names neither. The allowed
# set is read live from priority_band, so the named production line is the
# `if priority not in bands: raise WriteError` guard in file_task.
# ---------------------------------------------------------------------------

def test_file_rejects_bad_priority_naming_the_live_bands(store):
    """#681 — a bad priority names the column AND the live allowed set.

    PRODUCTION LINE: file_task's `if priority not in bands: raise WriteError`
    guard. Break by deleting it: file_task falls through to the INSERT and
    sqlite raises IntegrityError (FK) naming neither the column nor the set.
    The bands are derived LIVE from priority_band so a band added to the
    table is named without a test edit (direction 2 — that is right by
    design: the live read is the non-rotting property, not a gap).
    """
    bands = [r[0] for r in store.conn.execute(
        "SELECT band FROM priority_band ORDER BY band")]
    assert bands, "precondition: priority_band is seeded non-empty"
    bad = "3"
    assert bad not in bands, "precondition: '3' must not be a real band"

    with pytest.raises(ledger_write.WriteError) as ei:
        ledger_write.file_task(store, "t", "b", priority=bad)
    msg = str(ei.value)
    assert msg.startswith("priority: got '3', expected one of "), msg
    for b in bands:
        assert b in msg, f"live band {b!r} missing from message: {msg!r}"
    # A refused file writes nothing (the guard is before BEGIN IMMEDIATE).
    assert store.conn.execute("SELECT COUNT(*) FROM task").fetchone()[0] == 0


def test_file_rejects_bad_origin_naming_the_vocabulary(store):
    """#681 — origin outside the CHECK names the allowed set, not a bare
    sqlite IntegrityError from the CHECK constraint.

    PRODUCTION LINE: file_task's `if origin not in ORIGINS: raise WriteError`.
    """
    bad = "agent"
    assert bad not in ledger_store.ORIGINS, (
        "precondition: 'agent' must be outside the origin vocabulary")

    with pytest.raises(ledger_write.WriteError) as ei:
        ledger_write.file_task(store, "t", "b", origin=bad)
    msg = str(ei.value)
    assert msg == "origin: got 'agent', expected one of human, loop, unknown", msg


def test_file_accepts_a_valid_priority_and_origin(store):
    """#681 — a VALID priority/origin still files (the guard must not over-fire
    on the happy path). PRODUCTION LINE: the guard is `if priority not in bands`.
    """
    new_id = ledger_write.file_task(
        store, "ok title", "ok body", priority="P1", origin="human")
    row = store.conn.execute(
        "SELECT priority, origin FROM task WHERE id = ?", (new_id,)).fetchone()
    assert row == ("P1", "human")


# ---------------------------------------------------------------------------
# #627 — reprioritise_task / unblock_task: the writers for priority and
# blocked_on. A task's band was fixed at birth (--priority only on file); a
# stale blocked_on had no clearer at all. These two close the gap through the
# same supported path fold/note use.
#
# Named production lines whose change must red each test:
#
# - reprioritise_task's `if priority not in bands: raise WriteError`
#       → test_reprioritise_rejects_a_bad_band_naming_the_live_bands
# - reprioritise_task's UPDATE priority + body append + chained event
#       → test_reprioritise_changes_band_and_records_why_in_history
# - reprioritise_task raises TaskNotFound
#       → test_reprioritise_raises_task_not_found
# - unblock_task's `if not old_blocked: raise NotBlocked`  (#671)
#       → test_unblock_refuses_a_task_that_was_never_blocked
# - unblock_task's UPDATE blocked_on=NULL + body append + chained event
#       → test_unblock_clears_blocked_on_and_records_why_in_history
# - unblock_task raises TaskNotFound
#       → test_unblock_raises_task_not_found
# - both verbs refuse an empty why
#       → test_reprioritise_refuses_an_empty_why / test_unblock_refuses_an_empty_why
# ---------------------------------------------------------------------------

def test_reprioritise_changes_band_and_records_why_in_history(store, migrate):
    """PRODUCTION LINE: reprioritise_task's UPDATE priority + body append + event.

    The band changes AND the --why lands in the task's OWN HISTORY (body +
    event detail), not just the field. Derive distinct old/new bands at
    runtime so the test is not tuned to today's seed. Break by dropping the
    body append or the event — the why would vanish from history while the
    field still changed, which is exactly the silent #627 failure the brief
    warns against.
    """
    tid = ledger_write.file_task(store, "to reprioritise", "body",
                                  priority="P2", at="2026-07-29T10:00:00Z")
    before = store.conn.execute(
        "SELECT priority FROM task WHERE id = ?", (tid,)).fetchone()[0]
    new_band = "P1"
    assert new_band != before, "precondition: the band must actually change"

    ledger_write.reprioritise_task(store, tid, new_band, why="focus shift",
                                    at="2026-07-29T11:00:00Z")

    after = store.conn.execute(
        "SELECT priority FROM task WHERE id = ?", (tid,)).fetchone()[0]
    assert after == new_band, f"band must change {before}→{new_band}, got {after}"

    # THE THING THAT MAKES THE VERB SAFE: the why lands in the body (human-
    # readable history) and the event detail (machine-readable history).
    body = store.conn.execute(
        "SELECT body FROM task WHERE id = ?", (tid,)).fetchone()[0]
    assert "focus shift" in body, (
        "the --why must land in the body — an unexplained priority change is "
        "how a backlog stops being trustworthy (#627)")
    assert "reprioritised" in body, "the body note must name the transition"

    events = store.conn.execute(
        "SELECT cause, detail FROM task_event WHERE task_id = ?", (tid,)).fetchall()
    causes = [e[0] for e in events]
    assert "reprioritised" in causes, (
        f"a reprioritised event must be chained; got causes {causes}")
    rep_event = [e for e in events if e[0] == "reprioritised"][0]
    assert rep_event[1] == "focus shift", (
        f"the event detail must carry the why; got {rep_event[1]!r}")

    # The chain still verifies (the event was chained correctly).
    assert migrate.verify_task_event_chain(str(store.path)) == [], (
        "the reprioritised event must chain correctly")


def test_reprioritise_rejects_a_bad_band_naming_the_live_bands(store):
    """PRODUCTION LINE: reprioritise_task's `if priority not in bands` guard (#681).

    A bad band names the column AND the live allowed set, not a bare sqlite
    IntegrityError. Derive a value NOT in the set at runtime. Break by
    deleting the guard — sqlite raises IntegrityError (FK) naming neither.
    """
    bands = [r[0] for r in store.conn.execute(
        "SELECT band FROM priority_band ORDER BY band")]
    bad = "P9"
    assert bad not in bands, "precondition: 'P9' must not be a real band"

    tid = ledger_write.file_task(store, "t", "b", priority="P2")
    with pytest.raises(ledger_write.WriteError) as ei:
        ledger_write.reprioritise_task(store, tid, bad, why="x")
    msg = str(ei.value)
    assert msg.startswith("priority: got 'P9', expected one of "), msg
    for b in bands:
        assert b in msg, f"live band {b!r} missing from message: {msg!r}"
    # The band was NOT changed.
    after = store.conn.execute(
        "SELECT priority FROM task WHERE id = ?", (tid,)).fetchone()[0]
    assert after == "P2"


def test_reprioritise_raises_task_not_found(store):
    """PRODUCTION LINE: reprioritise_task's `row is None → TaskNotFound`."""
    assert store.conn.execute(
        "SELECT 1 FROM task WHERE id = 99999").fetchone() is None
    with pytest.raises(ledger_write.TaskNotFound, match="no such task"):
        ledger_write.reprioritise_task(store, 99999, "P1", why="x")
    assert store.conn.execute(
        "SELECT COUNT(*) FROM task_event WHERE task_id = 99999").fetchone()[0] == 0


def test_reprioritise_refuses_an_empty_why(store):
    """--why is mandatory and not decoration: an empty why is refused."""
    tid = ledger_write.file_task(store, "t", "b", priority="P2")
    with pytest.raises(ledger_write.WriteError, match="why must be a non-empty"):
        ledger_write.reprioritise_task(store, tid, "P1", why="   ")
    # Nothing changed.
    assert store.conn.execute(
        "SELECT priority FROM task WHERE id = ?", (tid,)).fetchone()[0] == "P2"


def test_unblock_clears_blocked_on_and_records_why_in_history(store, migrate):
    """PRODUCTION LINE: unblock_task's UPDATE blocked_on=NULL + body + event.

    The blocked_on clears AND the --why lands in the task's own history. Derive
    a non-empty blocked_on at runtime so the test is not vacuous. Break by
    dropping the body append or event — the why vanishes while the field cleared.
    """
    tid = ledger_write.file_task(store, "blocked task", "body",
                                  blocked_on="blocked on #999",
                                  at="2026-07-29T10:00:00Z")
    before = store.conn.execute(
        "SELECT blocked_on FROM task WHERE id = ?", (tid,)).fetchone()[0]
    assert before and before.strip(), "precondition: task must be blocked"

    ledger_write.unblock_task(store, tid, why="#999 landed",
                               at="2026-07-29T11:00:00Z")

    after = store.conn.execute(
        "SELECT blocked_on FROM task WHERE id = ?", (tid,)).fetchone()[0]
    assert after is None, f"blocked_on must be NULL, got {after!r}"

    body = store.conn.execute(
        "SELECT body FROM task WHERE id = ?", (tid,)).fetchone()[0]
    assert "#999 landed" in body, (
        "the --why must land in the body — the reason an unblock happened is "
        "the thing that keeps a backlog trustworthy (#627)")
    assert "unblocked" in body, "the body note must name the transition"
    assert before in body, "the old blocked_on must survive in the note (audit)"

    events = store.conn.execute(
        "SELECT cause, detail FROM task_event WHERE task_id = ?", (tid,)).fetchall()
    causes = [e[0] for e in events]
    assert "unblocked" in causes, (
        f"an unblocked event must be chained; got causes {causes}")
    unb_event = [e for e in events if e[0] == "unblocked"][0]
    assert unb_event[1] == "#999 landed", (
        f"the event detail must carry the why; got {unb_event[1]!r}")

    assert migrate.verify_task_event_chain(str(store.path)) == [], (
        "the unblocked event must chain correctly")


def test_unblock_refuses_a_task_that_was_never_blocked(store):
    """PRODUCTION LINE: unblock_task's `if not old_blocked: raise NotBlocked` (#671).

    An unblock that unblocked nothing must not read as success. Derive the
    precondition (blocked_on is empty) at runtime. Break by treating empty as
    success — the verb would silently no-op and the operator cannot tell it
    did nothing.
    """
    tid = ledger_write.file_task(store, "never blocked", "body")
    before = store.conn.execute(
        "SELECT blocked_on FROM task WHERE id = ?", (tid,)).fetchone()[0]
    assert not before or not before.strip(), (
        "precondition: task must not be blocked")

    with pytest.raises(ledger_write.NotBlocked, match="not blocked"):
        ledger_write.unblock_task(store, tid, why="x")
    # No event for a refused unblock.
    assert store.conn.execute(
        "SELECT COUNT(*) FROM task_event WHERE task_id = ?", (tid,)).fetchone()[0] == 1


def test_unblock_raises_task_not_found(store):
    """PRODUCTION LINE: unblock_task's `row is None → TaskNotFound`."""
    with pytest.raises(ledger_write.TaskNotFound, match="no such task"):
        ledger_write.unblock_task(store, 99999, why="x")


def test_unblock_refuses_an_empty_why(store):
    """--why is mandatory: an empty why is refused before any write."""
    tid = ledger_write.file_task(store, "t", "b", blocked_on="blocked on #1")
    with pytest.raises(ledger_write.WriteError, match="why must be a non-empty"):
        ledger_write.unblock_task(store, tid, why="")
    # Still blocked — nothing changed.
    assert store.conn.execute(
        "SELECT blocked_on FROM task WHERE id = ?", (tid,)).fetchone()[0] == "blocked on #1"


def test_reprioritise_works_on_a_landed_task(store):
    """Direction-2 case: reprioritising a LANDED task. The brief lists it as a
    candidate for 'the write succeeds and the ledger is now wrong.' A landed
    task's priority is moot (it is done), but changing it is not DATA CORRUPTION
    — it is a no-op-in-spirit that harms nothing. This test documents that the
    verb ALLOWS it (does not over-refuse), which is the chosen behavior. If the
    coordinator wants landed-task reprioritise refused, that is a separate call.
    """
    tid = ledger_write.file_task(store, "landed", "body", priority="P2")
    ledger_write.land_task(store, tid, at="2026-07-29T11:00:00Z")
    ledger_write.reprioritise_task(store, tid, "P1", why="retroactive")
    after = store.conn.execute(
        "SELECT priority FROM task WHERE id = ?", (tid,)).fetchone()[0]
    assert after == "P1"
