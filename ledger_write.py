"""ledger_write.py — the MINIMAL store write verbs: file + land (#294 inc 9).

The loop's two real ledger writes are FILING a new task and LANDING (folding)
a finished one. Pre-cutover both edit ``.dreamwork/tasks.md`` directly; post-
cutover the SQLite store is the single source and these two verbs own it, or
the loop's writes are stranded (design cutover step 7: "new writes go through
``dreamwork tasks file|grab|cycle``").

One transaction per transition (G4 — the import's fixture-3 shape, applied to
the live writer): a crash mid-file or mid-land leaves no partial state. Each
transition appends one hash-chained ``task_event`` row via the SAME chain
construction ``ud-dw-tasks-migrate`` uses (``genesis_hash`` / ``hash_event`` /
``canonical_event_bytes``, now the one copy in ``ledger_store``), so
``verify_task_event_chain`` passes over live events exactly as it passes over
synthetic ones — the verifier walks by ordinal and chains each row from the
previous, so an ordinal-order append is always valid.

Actor is explicit (default ``'loop'``), never fabricated as the human. The two
verbs are the minimal pair #294's cutover step 7 names; the full #264 verb set
(grab/release/cycle/hold/history) and claims/leases are deliberately out of
scope — build the minimal pair in #264's one-row-per-transition spirit, nothing
more.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from ledger_store import (
    canonical_event_bytes,
    genesis_hash,
    hash_event,
)

# The cause values the two verbs emit — both in TASK_CAUSES (closed set).
_CAUSE_FILED = "filed_from_command"
_CAUSE_LANDED = "landed"

# The ledger's continuation idiom for a note on an entry body (matches
# dev/ledger.py's NOTE_PREFIX): a two-space indent, U+00B7, space.
_NOTE_PREFIX = "  · "


class WriteError(RuntimeError):
    """A file/land transition could not be performed (bad input, CAS refused)."""


class TaskNotFound(WriteError):
    """The task id does not exist in the store."""


class BadState(WriteError):
    """The task is not in the state the transition requires (CAS refused)."""


def _now_iso() -> str:
    """The current UTC timestamp as an ISO-8601 string (the event ``at``)."""
    return datetime.now(timezone.utc).isoformat()


def _last_event_hash(conn) -> str:
    """The hash of the last task_event row by ordinal, or genesis if none.

    A live transition appends one event at the end (ordinal is AUTOINCREMENT),
    so the previous hash in the chain is always the current last row's hash.
    """
    row = conn.execute(
        "SELECT hash FROM task_event ORDER BY ordinal DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else genesis_hash()


def _append_chained_event(conn, *, task_id, at, cause, from_state, to_state,
                          actor, detail="") -> None:
    """INSERT one task_event row, chained from the current last event.

    Caller holds the transaction (``BEGIN IMMEDIATE … COMMIT``). The row's
    ``prev_hash`` is the last event's hash by ordinal; its ``hash`` covers
    the canonical bytes plus that prev. This is the live counterpart of
    ``chain_events``'s bulk loop — one event at a time, in real time.
    """
    event = {"task_id": task_id, "at": at, "cause": cause,
             "from_state": from_state, "to_state": to_state,
             "actor": actor, "detail": detail}
    prev = _last_event_hash(conn)
    h = hash_event(prev, canonical_event_bytes(event))
    conn.execute(
        "INSERT INTO task_event(task_id, at, cause, from_state, to_state,"
        " actor, receipt_id, detail, prev_hash, hash)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (task_id, at, cause, from_state, to_state, actor, None, detail,
         prev, h))


def file_task(store, title, body, *, priority=None, priority_uncertain=0,
              type=None, origin=None, blocked_on=None, actor="loop",
              at=None) -> int:
    """File a new task: INSERT the task row + the chained ``filed`` event.

    The task id comes from the seeded AUTOINCREMENT — never chosen by the
    caller — so two writers can never mint the same id (R1). The row and its
    ``filed`` event (from_state NULL → open) are written in ONE ``BEGIN
    IMMEDIATE … COMMIT``; a crash mid-file leaves no task row without its
    event (G4 — the import's fixture-3 shape, applied to the live writer).

    Returns the new task id. Raises ``WriteError`` on bad input.
    """
    if not isinstance(title, str) or not title.strip():
        raise WriteError("title must be a non-empty string (task.title NOT NULL)")
    if not isinstance(body, str) or not body.strip():
        raise WriteError("body must be a non-empty string (task.body NOT NULL)")
    if at is None:
        at = _now_iso()

    conn = store.conn
    conn.execute("BEGIN IMMEDIATE")
    try:
        # task.type REFERENCES task_type (an unseeded lookup the import owns);
        # register the value before the row if one is given.
        if type is not None:
            conn.execute(
                "INSERT OR IGNORE INTO task_type(type) VALUES (?)", (type,))
        cur = conn.execute(
            "INSERT INTO task(state, title, body, priority,"
            " priority_uncertain, type, origin, blocked_on, body_digest)"
            " VALUES ('open', ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, body, priority, priority_uncertain, type, origin,
             blocked_on, hashlib.sha256(body.encode()).hexdigest()))
        new_id = cur.lastrowid
        _append_chained_event(
            conn, task_id=new_id, at=at, cause=_CAUSE_FILED,
            from_state=None, to_state="open", actor=actor)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return new_id


def land_task(store, task_id, *, note=None, actor="loop", at=None) -> None:
    """Land (fold) a task: CAS state open→landed + append note + chained event.

    The state flip is a compare-and-swap: ``UPDATE … WHERE state = 'open'``
    matches zero rows if the task is not currently open, and the transition
    refuses (the CAS). If ``note`` is given it is appended to ``task.body``
    (bodies accumulate notes across a task's life — schema comment). The
    ``landed`` event (open → landed) is chained and the whole transition is
    one transaction.

    Raises ``TaskNotFound`` if the id does not exist; ``BadState`` if the task
    is not currently open.
    """
    if at is None:
        at = _now_iso()

    conn = store.conn
    conn.execute("BEGIN IMMEDIATE")
    try:
        cur = conn.execute(
            "UPDATE task SET state = 'landed' WHERE id = ? AND state = 'open'",
            (task_id,))
        if cur.rowcount == 0:
            # CAS refused — read the actual state for a useful error, then
            # roll back (the UPDATE changed nothing; the read is honest).
            row = conn.execute(
                "SELECT state FROM task WHERE id = ?", (task_id,)).fetchone()
            conn.execute("ROLLBACK")
            if row is None:
                raise TaskNotFound(f"cannot land #{task_id}: no such task")
            raise BadState(
                f"cannot land #{task_id}: state is {row[0]!r}, not 'open' "
                "(CAS refused)")
        if note:
            conn.execute(
                "UPDATE task SET body = body || ? WHERE id = ?",
                ("\n" + _NOTE_PREFIX + note, task_id))
        _append_chained_event(
            conn, task_id=task_id, at=at, cause=_CAUSE_LANDED,
            from_state="open", to_state="landed", actor=actor,
            detail=note or "")
        conn.execute("COMMIT")
    except (TaskNotFound, BadState):
        raise
    except Exception:
        conn.execute("ROLLBACK")
        raise


# ---------------------------------------------------------------------------
# note — annotate a task (body append, no transition)
# ---------------------------------------------------------------------------

def note_task(store, task_id, note, *, actor="loop") -> None:
    """Annotate a task: append the note to ``task.body`` in ANY state.

    A note is not a state transition (#264's boundary: one event per
    transition), so it appends to the body ONLY — no ``task_event`` row.
    The body is the annotation audit trail (the schema's own comment: "body
    is where notes/updates accumulate across a task's life"), and the note's
    date and attribution live in its prose, as the coordinator writes them.
    ``verify_task_event_chain`` therefore passes trivially: the chain is
    untouched. One transaction: the body append is atomic.

    ``actor`` is accepted for parity with the file/land verb set; because no
    event is written it is not recorded in the chain. Works for any state
    (open or landed — both get annotated in practice).

    Raises ``TaskNotFound`` if the id does not exist; ``WriteError`` on an
    empty note.
    """
    if not isinstance(note, str) or not note.strip():
        raise WriteError("note must be a non-empty string")

    conn = store.conn
    conn.execute("BEGIN IMMEDIATE")
    try:
        cur = conn.execute(
            "UPDATE task SET body = body || ? WHERE id = ?",
            ("\n" + _NOTE_PREFIX + note, task_id))
        if cur.rowcount == 0:
            conn.execute("ROLLBACK")
            raise TaskNotFound(f"cannot note #{task_id}: no such task")
        conn.execute("COMMIT")
    except TaskNotFound:
        raise
    except Exception:
        conn.execute("ROLLBACK")
        raise
