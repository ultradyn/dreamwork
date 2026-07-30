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
    REVIEW_DECISIONS,
    append_chained_event,
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


class DecisionConflict(WriteError):
    """A final (non-pending) review decision exists for this artifact under a
    different question. Refused rather than overwritten — a decided review is
    not silently reassignable to another question."""


def _now_iso() -> str:
    """The current UTC timestamp as an ISO-8601 string (the event ``at``)."""
    return datetime.now(timezone.utc).isoformat()


def _last_event_hash(conn) -> str:
    """The hash of the last task_event row by ordinal, or genesis if none.

    Delegated to :func:`ledger_store.last_event_hash` — the ONE copy of the
    "chain from the last row" mechanic (#460 gap-fill). Kept as a thin local
    alias so the live write verbs read as they always did.
    """
    from ledger_store import last_event_hash
    return last_event_hash(conn)


def _append_chained_event(conn, *, task_id, at, cause, from_state, to_state,
                          actor, detail="") -> None:
    """INSERT one task_event row, chained from the current last event.

    Delegates to :func:`ledger_store.append_chained_event` — the ONE apply
    primitive the live writer and the journal replay tool both ride (#352 /
    #460), so the chain construction has one definition. The caller holds the
    transaction (``BEGIN IMMEDIATE … COMMIT``); this function only appends.
    """
    append_chained_event(
        conn, task_id=task_id, at=at, cause=cause, from_state=from_state,
        to_state=to_state, actor=actor, receipt_id=None, detail=detail)


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


# ---------------------------------------------------------------------------
# review decision — record an artifact's answer (NOT a task, no event chain)
# ---------------------------------------------------------------------------

def record_review_decision(store, artifact, question_title, decision, *,
                            actor, at=None):
    """Record a review decision for an artifact.

    A review decision is NOT a task: it has no task id and no entry in the
    ``task_event`` hash chain (#264's boundary — one event per *task*
    transition). Its identity is ``(artifact, question_title)``: the artifact
    is the review's PRIMARY KEY, and question_title is the question it answers
    (questions are not ledger tasks, so their only identity is their title).

    Idiom: one ``BEGIN IMMEDIATE … COMMIT`` transaction (a crash leaves no
    half-row). Before the upsert a conflict gate reads any existing row:
    - same question_title, any decision  → re-decide (overwrite, allowed)
    - different question_title, 'pending' → pending is provisional, overwrite
    - different question_title, decided   → ``DecisionConflict`` (a final
      decision is not silently reassignable to another question)

    ``decision`` is validated against ``REVIEW_DECISIONS`` (imported from
    ledger_store — the one closed set, never redefined here).

    Raises ``WriteError`` on a bad decision; ``DecisionConflict`` on the
    cross-question final-decision clash. ``actor`` and ``at`` are explicit
    (actor has no default — a review decision must be attributed).
    """
    if decision not in REVIEW_DECISIONS:
        raise WriteError(
            f"decision must be one of {REVIEW_DECISIONS}, got {decision!r}")
    if at is None:
        at = _now_iso()

    conn = store.conn
    conn.execute("BEGIN IMMEDIATE")
    try:
        existing = conn.execute(
            "SELECT question_title, decision FROM review_decision "
            "WHERE artifact = ?", (artifact,)).fetchone()
        if existing is not None:
            ex_title, ex_decision = existing
            if ex_title != question_title and ex_decision != "pending":
                conn.execute("ROLLBACK")
                raise DecisionConflict(
                    f"artifact {artifact!r} is already decided "
                    f"{ex_decision!r} under a different question "
                    f"({ex_title!r} vs {question_title!r}); a final review "
                    "decision is not silently reassignable to another question"
                )
        conn.execute(
            "INSERT OR REPLACE INTO review_decision"
            "(artifact, question_title, decision, decided_at, actor)"
            " VALUES (?, ?, ?, ?, ?)",
            (artifact, question_title, decision, at, actor))
        conn.execute("COMMIT")
    except DecisionConflict:
        raise
    except Exception:
        conn.execute("ROLLBACK")
        raise
