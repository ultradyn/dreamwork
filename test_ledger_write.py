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
import subprocess
import types
from contextlib import contextmanager
from pathlib import Path

import pytest

import ledger_store
import ledger_write
from dreamwork_db import Access, ConstraintViolation, open_database
from dreamwork_db.tasks import task_store_spec
from dreamwork_db.tasks import TaskRepository

REPO = Path(__file__).resolve().parent
MIGRATE_CLI = REPO / "ud-dw-tasks-migrate"
PRE_MOVE_SHA = "e72674be"


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
    """A WRITE handle plus a test-only raw observer over one scratch store."""
    path = tmp_path / "l.sqlite3"
    ledger_store.open_store(path, seed_next_id=500).close()

    class StoreHarness:
        def __init__(self, handle, observer):
            self._handle = handle
            self.conn = observer
            self.path = path

        @property
        def tasks(self):
            return self._handle.tasks

        def transaction(self, **kwargs):
            return self._handle.transaction(**kwargs)

        def next_id(self):
            row = self.conn.execute(
                "SELECT seq FROM sqlite_sequence WHERE name='task'").fetchone()
            return int(row[0]) + 1 if row else 1

    observer = sqlite3.connect(path, isolation_level=None)
    with open_database(task_store_spec(path), access=Access.WRITE) as handle:
        yield StoreHarness(handle, observer)
    observer.close()


@pytest.fixture
def migrate():
    return _load_migrate()


def _load_pre_move_writer():
    source = subprocess.run(
        ["git", "show", f"{PRE_MOVE_SHA}:ledger_write.py"], cwd=REPO,
        check=True, capture_output=True, text=True).stdout
    module = types.ModuleType("ledger_write_pre_move_e72674be")
    exec(compile(source, f"{PRE_MOVE_SHA}:ledger_write.py", "exec"),
         module.__dict__)
    return module


def _captured_write_state(path):
    with sqlite3.connect(path) as conn:
        return {
            "tasks": conn.execute(
                "SELECT id, state, title, body, priority, type, origin, "
                "blocked_on, body_digest FROM task ORDER BY id").fetchall(),
            "events": conn.execute(
                "SELECT task_id, at, cause, from_state, to_state, actor, "
                "detail, prev_hash, hash FROM task_event ORDER BY ordinal"
            ).fetchall(),
            "reviews": conn.execute(
                "SELECT artifact, question_title, decision, decided_at, actor "
                "FROM review_decision ORDER BY artifact").fetchall(),
        }


def _run_seven_commands(writer, store):
    task_id = writer.file_task(
        store, "original title", "original body", priority="P2",
        type="task", origin="loop", blocked_on="blocked on #9",
        actor="fixture", at="2026-08-01T00:00:00Z")
    writer.note_task(store, task_id, "annotation", actor="fixture")
    writer.reprioritise_task(
        store, task_id, "P1", why="priority reason", actor="fixture",
        at="2026-08-01T00:01:00Z")
    writer.unblock_task(
        store, task_id, why="blocker landed", actor="fixture",
        at="2026-08-01T00:02:00Z")
    writer.retitle_task(
        store, task_id, "current title", why="title reason", actor="fixture",
        at="2026-08-01T00:03:00Z")
    writer.land_task(
        store, task_id, note="land reason", actor="fixture",
        at="2026-08-01T00:04:00Z")
    writer.record_review_decision(
        store, "design.html", "Ship it?", "accepted", actor="fixture",
        at="2026-08-01T00:05:00Z")
    return task_id


def test_repository_writes_match_pre_move_store_shapes(tmp_path):
    """All seven commands preserve the exact pre-move persisted shapes."""
    old_path = tmp_path / "old.sqlite3"
    new_path = tmp_path / "new.sqlite3"
    old_store = ledger_store.open_store(old_path, seed_next_id=700)
    ledger_store.open_store(new_path, seed_next_id=700).close()
    try:
        old_id = _run_seven_commands(_load_pre_move_writer(), old_store)
    finally:
        old_store.close()
    with open_database(task_store_spec(new_path), access=Access.WRITE) as handle:
        new_id = _run_seven_commands(ledger_write, handle)
    expected = _captured_write_state(old_path)
    actual = _captured_write_state(new_path)
    assert old_id == new_id == 700, (
        f"file parity differs: expected allocated id={old_id!r}, "
        f"actual allocated id={new_id!r}")
    for name, rows in expected.items():
        assert rows, f"{name} parity captured no pre-move rows; refusing vacuous equality"
        assert rows == actual[name], (
            f"{name} parity differs after seven commands:\n"
            f"expected store state={rows!r}\nactual store state={actual[name]!r}")


def test_new_event_extends_chain_built_by_pre_move_code(tmp_path, migrate):
    """A new repository event verifies after a literal pre-move writer event."""
    path = tmp_path / "mixed.sqlite3"
    old_store = ledger_store.open_store(path, seed_next_id=800)
    try:
        task_id = _load_pre_move_writer().file_task(
            old_store, "pre-move task", "body", actor="old",
            at="2026-08-01T01:00:00Z")
    finally:
        old_store.close()
    before = _captured_write_state(path)["events"]
    assert len(before) == 1, (
        f"pre-move fixture must contribute one real event, got {before!r}")
    with open_database(task_store_spec(path), access=Access.WRITE) as handle:
        ledger_write.land_task(
            handle, task_id, actor="new", at="2026-08-01T01:01:00Z")
    after = _captured_write_state(path)["events"]
    assert len(after) == 2, (
        f"mixed chain must contain old and new events, got {after!r}")
    assert migrate.verify_task_event_chain(str(path)) == [], (
        f"new land event did not extend the pre-move chain: {after!r}")


def test_field_only_and_self_verifying_chain_are_false_green(
        tmp_path, monkeypatch, migrate):
    """Demonstrate the weak checks that pass when file silently drops its event."""
    path = tmp_path / "false-green.sqlite3"
    ledger_store.open_store(path, seed_next_id=900).close()
    monkeypatch.setattr(
        TaskRepository, "_append_chained_event", lambda self, **kwargs: None)
    with open_database(task_store_spec(path), access=Access.WRITE) as handle:
        task_id = ledger_write.file_task(handle, "wrong write", "body")
    state = _captured_write_state(path)
    assert state["tasks"] and state["tasks"][0][0] == task_id, (
        f"field-only check unexpectedly failed to see the committed row: {state!r}")
    assert state["events"] == [], (
        f"precondition: the injected writer must silently drop the event: {state!r}")
    assert migrate.verify_task_event_chain(str(path)) == [], (
        "FALSE GREEN construction failed: an empty chain should verify against "
        "itself even though the filed task has no event")


@pytest.mark.parametrize("command", [
    "file", "land", "reprioritise", "unblock", "retitle",
])
def test_task_event_commands_rollback_row_when_event_append_fails(
        store, monkeypatch, command):
    """A BaseException between the row mutation and event leaves no change."""
    anchor = ledger_write.file_task(
        store, "anchor", "anchor body", priority="P2",
        at="2026-08-01T02:00:00Z")
    if command == "land":
        target = anchor
    else:
        target = ledger_write.file_task(
            store, f"{command} target", "target body", priority="P2",
            blocked_on="blocked on #1",
            at="2026-08-01T02:01:00Z")
    before = _captured_write_state(store.path)
    assert before["tasks"] and before["events"], (
        f"{command} rollback fixture captured no state; refusing vacuous proof")

    class InjectedCrash(BaseException):
        pass

    def fail_after_row_write(self, **_kwargs):
        raise InjectedCrash(f"{command}: injected between row write and event append")

    monkeypatch.setattr(TaskRepository, "_append_chained_event", fail_after_row_write)
    with pytest.raises(InjectedCrash, match=f"^{command}: injected"):
        if command == "file":
            ledger_write.file_task(store, "doomed", "doomed body")
        elif command == "land":
            ledger_write.land_task(store, target)
        elif command == "reprioritise":
            ledger_write.reprioritise_task(
                store, target, "P1", why="doomed reason")
        elif command == "unblock":
            ledger_write.unblock_task(store, target, why="doomed reason")
        else:
            ledger_write.retitle_task(
                store, target, "doomed title", why="doomed reason")
    after = _captured_write_state(store.path)
    assert after == before, (
        f"{command} rollback differs after injected event failure:\n"
        f"expected store state={before!r}\nactual store state={after!r}")


def test_all_seven_facades_open_exactly_one_default_transaction():
    """Every facade delegates once inside the handle's default transaction."""
    calls = []

    class Repositories:
        def __getattr__(self, name):
            def call(*_args, **_kwargs):
                calls.append(("repository", name))
                return 1 if name == "file" else None
            return call

    class Handle:
        tasks = Repositories()

        @contextmanager
        def transaction(self, *, immediate=True):
            calls.append(("begin", immediate))
            yield self
            calls.append(("commit", immediate))

    handle = Handle()
    invocations = [
        lambda: ledger_write.file_task(handle, "t", "b"),
        lambda: ledger_write.land_task(handle, 1),
        lambda: ledger_write.note_task(handle, 1, "n"),
        lambda: ledger_write.reprioritise_task(handle, 1, "P1", why="w"),
        lambda: ledger_write.unblock_task(handle, 1, why="w"),
        lambda: ledger_write.retitle_task(handle, 1, "t2", why="w"),
        lambda: ledger_write.record_review_decision(
            handle, "a", "q", "accepted", actor="loop"),
    ]
    for invoke in invocations:
        before = len(calls)
        invoke()
        command_calls = calls[before:]
        assert command_calls[0] == ("begin", True), command_calls
        assert command_calls[-1] == ("commit", True), command_calls
        assert len(command_calls) == 3, (
            f"command did not own exactly one transaction and one repository "
            f"call: {command_calls!r}")


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
    path = tmp_path / "l.sqlite3"
    s = ledger_store.open_store(path, seed_next_id=10)
    try:
        # Simulate an import: an explicit-id row above the seed.
        s.conn.execute(
            "INSERT INTO task(id, state, title, body) "
            "VALUES (50, 'open', 'imported', 'b')")
        s.conn.commit()
        hw = s.sequence_high_water("task")
        assert hw == 50, f"precondition: AUTOINCREMENT tracks the explicit id, got {hw}"

    finally:
        s.close()
    with open_database(task_store_spec(path), access=Access.WRITE) as handle:
        new_id = ledger_write.file_task(
            handle, "filed after import", "body",
            at="2026-07-29T10:00:00Z")
    assert new_id > 50, (
        f"filed id {new_id} must exceed the imported high-water 50 — "
        "a collision would reuse a permanent id")
    assert new_id != 50


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

    # The FK violation routes through the ladder (file_task → store.tasks.file
    # → the dreamwork_db session), so it is named ConstraintViolation, not a
    # raw sqlite3.IntegrityError: the ladder names what sqlite proved (#651/#702).
    with pytest.raises(ConstraintViolation, match="constraint"):
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


# ===========================================================================
# next-up (#884) — the mark is DERIVED from the event log, so these bind the
# derivation, not a column.
# ===========================================================================


def _marks(store):
    """``next_up_ordinals`` through a transaction — a WRITE handle requires
    one for every repository call, read or not."""
    with store.transaction():
        return store.tasks.next_up_ordinals()


def test_set_next_up_emits_the_cause_v001_seeded_and_never_used(store):
    """The storage was already installed; #884 only wired a writer to it.

    PRODUCTION LINE: the ``cause="next_up_set"`` append in
    ``TaskRepository.set_next_up``. RED: change the cause string and the
    FOREIGN KEY into ``task_cause`` rejects it — which is the point: the
    enumeration is the contract, not a convention.
    """
    seeded = {r[0] for r in store.conn.execute("SELECT cause FROM task_cause")}
    assert {"next_up_set", "next_up_cleared"} <= seeded, (
        f"precondition: v001 seeds both causes: {sorted(seeded)}")
    task_id = ledger_write.file_task(store, "a task", "body")
    assert _marks(store) == {}, "born unmarked"

    ledger_write.set_next_up(store, task_id, why="he asked for this one")

    rows = store.conn.execute(
        "SELECT cause, detail, from_state, to_state FROM task_event"
        " WHERE task_id = ? AND cause LIKE 'next_up%'", (task_id,)).fetchall()
    assert rows == [("next_up_set", "he asked for this one", "open", "open")], rows
    assert _marks(store) == {
        task_id: store.conn.execute(
            "SELECT MAX(ordinal) FROM task_event WHERE task_id = ?",
            (task_id,)).fetchone()[0]}


def test_re_marking_mints_a_newer_ordinal_rather_than_refusing(store):
    """"Several next-ups: newest first" needs a re-mark to MOVE the task."""
    a = ledger_write.file_task(store, "first", "body")
    b = ledger_write.file_task(store, "second", "body")
    ledger_write.set_next_up(store, a, why="this one")
    ledger_write.set_next_up(store, b, why="no, this one")
    ledger_write.set_next_up(store, a, why="back to the first")
    marks = _marks(store)
    assert marks[a] > marks[b], (
        f"the latest steer must carry the highest ordinal: {marks}")


def test_a_landed_task_cannot_be_marked_next_up(store):
    """PRODUCTION LINE: the ``state != "open"`` guard in ``set_next_up``."""
    task_id = ledger_write.file_task(store, "a task", "body")
    ledger_write.land_task(store, task_id)
    with pytest.raises(ledger_write.BadState, match="not 'open'"):
        ledger_write.set_next_up(store, task_id, why="too late")


def test_landing_a_marked_task_drops_it_from_the_mark_set(store):
    """A forgotten clear must self-heal at land, not hoist finished work.

    PRODUCTION LINE: the ``t.state = 'open'`` clause in
    ``next_up_ordinals``. RED: drop it and a landed task stays marked
    forever, so `list` (unfiltered) keeps ranking work that is done.
    """
    task_id = ledger_write.file_task(store, "a task", "body")
    ledger_write.set_next_up(store, task_id, why="steer")
    assert task_id in _marks(store), "precondition: marked"
    ledger_write.land_task(store, task_id)
    assert _marks(store) == {}, (
        "a landed task is not next-up whatever its event history says")


def test_next_up_writes_require_a_why(store):
    """The steer's words are the reason the record is worth keeping."""
    task_id = ledger_write.file_task(store, "a task", "body")
    with pytest.raises(ledger_write.WriteError, match="non-empty"):
        ledger_write.set_next_up(store, task_id, why="   ")
    ledger_write.set_next_up(store, task_id, why="ok")
    with pytest.raises(ledger_write.WriteError, match="non-empty"):
        ledger_write.clear_next_up(store, task_id, why="")
