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
    ORIGINS,
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
    # #681 — validate enum columns BEFORE the INSERT, reading the allowed set
    # LIVE from the store so the message cannot rot out of sync with the
    # schema. A sqlite IntegrityError names NEITHER the column at fault NOR the
    # allowed set (an FK failure on a multi-column INSERT does not even say
    # which value was wrong); this names both. `priority` reads priority_band
    # (the closed FK lookup, seeded at open); `origin` reuses ORIGINS — the
    # CHECK-constraint vocabulary, co-located with the constraint in
    # ledger_store. `type` is deliberately NOT validated: task_type is an OPEN
    # lookup this verb seeds itself (INSERT OR IGNORE below), so any value is
    # valid by design.
    if priority is not None:
        bands = [r[0] for r in conn.execute(
            "SELECT band FROM priority_band ORDER BY band")]
        if priority not in bands:
            raise WriteError(
                "priority: got {!r}, expected one of {}".format(
                    priority, ", ".join(bands)))
    if origin is not None and origin not in ORIGINS:
        raise WriteError(
            "origin: got {!r}, expected one of {}".format(
                origin, ", ".join(ORIGINS)))
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
# reprioritise / unblock (#627) — change priority or clear a stale blocked_on.
#
# The loop's selection reads `priority` as its main ordering key, and a task
# whose `blocked_on` names an already-landed blocker is INVISIBLE to selection
# (#590). `--priority` existed only on `file`, so a band was fixed at birth;
# there was no verb at all for clearing a stale `blocked_on`. These two writers
# close that gap through the SAME supported path fold/note use — one transaction,
# body note + chained event (the reason lands in the task's own history "the way
# fold does"; an unexplained priority change is how a backlog stops being
# trustworthy — #627).
#
# `--why` is mandatory and not decoration: it is recorded in the body (human-
# readable) AND the event detail (machine-readable), matching land_task. A verb
# that made it optional "for convenience" would remove the thing that makes the
# change safe.
#
# Named production lines whose change must red each test:
#
# - reprioritise_task's `if priority not in bands: raise WriteError`
#       → test_reprioritise_rejects_a_bad_band_naming_the_live_bands
# - reprioritise_task's UPDATE task SET priority + body append + event
#       → test_reprioritise_changes_band_and_records_why_in_history
# - unblock_task's `if not old_blocked: raise NotBlocked`  (#671)
#       → test_unblock_refuses_a_task_that_was_never_blocked
# - unblock_task's UPDATE task SET blocked_on=NULL + body append + event
#       → test_unblock_clears_blocked_on_and_records_why_in_history
# ---------------------------------------------------------------------------

_CAUSE_REPRIORITISED = "reprioritised"
_CAUSE_UNBLOCKED = "unblocked"


class NotBlocked(WriteError):
    """The task is not blocked, so there is nothing to unblock (#671).

    An unblock that unblocked nothing must not read as success: a tool that
    silently no-ops on an already-unblocked task cannot tell the operator it
    did nothing, which is the exact failure #671 names."""


def reprioritise_task(store, task_id, priority, *, why, actor="loop", at=None):
    """Change a task's priority band, recording why in body + event chain (#627).

    Validates ``priority`` against ``priority_band`` LIVE (the same #681 guard
    ``file_task`` uses, so a band added to the table is accepted without a code
    change). Appends ``  · reprioritised <old>→<new>: <why>`` to the body and a
    chained ``reprioritised`` event (the task's state is unchanged, so
    from_state == to_state == the current state — the cause carries the
    transition type). One transaction (G4): a crash mid-change leaves no
    partial state.

    Raises ``TaskNotFound`` if the id does not exist; ``WriteError`` on an
    empty ``why`` or a band outside ``priority_band``.
    """
    if not isinstance(why, str) or not why.strip():
        raise WriteError(
            "why must be a non-empty string (the reason for the change)")
    if at is None:
        at = _now_iso()

    conn = store.conn
    # #681 — validate the band BEFORE the INSERT, reading the allowed set LIVE
    # from the store so the message cannot rot. Same guard as file_task.
    bands = [r[0] for r in conn.execute(
        "SELECT band FROM priority_band ORDER BY band")]
    if priority not in bands:
        raise WriteError(
            "priority: got {!r}, expected one of {}".format(
                priority, ", ".join(bands)))

    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT priority FROM task WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            conn.execute("ROLLBACK")
            raise TaskNotFound(f"cannot reprioritise #{task_id}: no such task")
        old = row[0]
        conn.execute(
            "UPDATE task SET priority = ? WHERE id = ?",
            (priority, task_id))
        note = "reprioritised {}→{}: {}".format(old or "—", priority, why)
        conn.execute(
            "UPDATE task SET body = body || ? WHERE id = ?",
            ("\n" + _NOTE_PREFIX + note, task_id))
        state = conn.execute(
            "SELECT state FROM task WHERE id = ?", (task_id,)).fetchone()[0]
        _append_chained_event(
            conn, task_id=task_id, at=at, cause=_CAUSE_REPRIORITISED,
            from_state=state, to_state=state, actor=actor, detail=why)
        conn.execute("COMMIT")
    except TaskNotFound:
        raise
    except Exception:
        conn.execute("ROLLBACK")
        raise


def unblock_task(store, task_id, *, why, actor="loop", at=None):
    """Clear a task's ``blocked_on``, recording why in body + event chain (#627).

    Refuses (#671) when the task is not blocked (``blocked_on`` is NULL or
    empty): an unblock that unblocked nothing must not read as success. On
    success, appends ``  · unblocked (was: <old>): <why>`` to the body and a
    chained ``unblocked`` event. One transaction (G4).

    Raises ``TaskNotFound`` if the id does not exist; ``NotBlocked`` when the
    task was never blocked; ``WriteError`` on an empty ``why``.
    """
    if not isinstance(why, str) or not why.strip():
        raise WriteError(
            "why must be a non-empty string (the reason for the change)")
    if at is None:
        at = _now_iso()

    conn = store.conn
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT blocked_on, state FROM task WHERE id = ?",
            (task_id,)).fetchone()
        if row is None:
            conn.execute("ROLLBACK")
            raise TaskNotFound(f"cannot unblock #{task_id}: no such task")
        old_blocked, state = row
        if not old_blocked or not old_blocked.strip():
            conn.execute("ROLLBACK")
            raise NotBlocked(
                f"cannot unblock #{task_id}: it is not blocked "
                "(blocked_on is empty) — an unblock that unblocked nothing "
                "must not read as success (#671)")
        conn.execute(
            "UPDATE task SET blocked_on = NULL WHERE id = ?", (task_id,))
        note = "unblocked (was: {}): {}".format(old_blocked, why)
        conn.execute(
            "UPDATE task SET body = body || ? WHERE id = ?",
            ("\n" + _NOTE_PREFIX + note, task_id))
        _append_chained_event(
            conn, task_id=task_id, at=at, cause=_CAUSE_UNBLOCKED,
            from_state=state, to_state=state, actor=actor, detail=why)
        conn.execute("COMMIT")
    except (TaskNotFound, NotBlocked):
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
