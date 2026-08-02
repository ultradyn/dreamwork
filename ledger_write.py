"""SQL-free compatibility facades for task-store write commands.

Each facade preserves the established signature and owns exactly one database
transaction.  The implementation and chained-event mechanics live behind the
handle-bound :class:`dreamwork_db.tasks.TaskRepository`.
"""

from __future__ import annotations

from ledger_store import ORIGINS, REVIEW_DECISIONS
from dreamwork_db.tasks import (
    BadState,
    DecisionConflict,
    DependencyCycle,
    NotBlocked,
    NotNextUp,
    SameTitle,
    TaskNotFound,
    WriteError,
)


def file_task(store, title, body, *, priority=None, priority_uncertain=0,
              type=None, origin=None, blocked_on=None, actor="loop",
              at=None) -> int:
    """File a task row and its chained event as one unit of work."""
    with store.transaction():
        return store.tasks.file(
            title, body, priority=priority,
            priority_uncertain=priority_uncertain, type=type, origin=origin,
            blocked_on=blocked_on, actor=actor, at=at)


def land_task(store, task_id, *, note=None, actor="loop", at=None) -> None:
    """Land an open task and append its chained event atomically."""
    with store.transaction():
        store.tasks.land(task_id, note=note, actor=actor, at=at)


def note_task(store, task_id, note, *, actor="loop") -> None:
    """Append a task-body note atomically without adding an event."""
    with store.transaction():
        store.tasks.note(task_id, note, actor=actor)


def reprioritise_task(store, task_id, priority, *, why, actor="loop", at=None):
    """Change priority and record the mandatory reason atomically."""
    with store.transaction():
        store.tasks.reprioritise(
            task_id, priority, why=why, actor=actor, at=at)


def unblock_task(store, task_id, *, why, actor="loop", at=None):
    """Clear a blocker and record the mandatory reason atomically."""
    with store.transaction():
        store.tasks.unblock(task_id, why=why, actor=actor, at=at)


def block_task(store, task_id, *, needs, why, actor="loop", at=None) -> str:
    """Record a task→task dependency edge and the mandatory reason atomically."""
    with store.transaction():
        return store.tasks.block(task_id, needs=needs, why=why, actor=actor, at=at)


def set_next_up(store, task_id, *, why, actor="loop", at=None) -> None:
    """Mark a task next-up and record the mandatory reason atomically."""
    with store.transaction():
        store.tasks.set_next_up(task_id, why=why, actor=actor, at=at)


def clear_next_up(store, task_id, *, why, actor="loop", at=None) -> None:
    """Clear a next-up mark and record the mandatory reason atomically."""
    with store.transaction():
        store.tasks.clear_next_up(task_id, why=why, actor=actor, at=at)


def retitle_task(store, task_id, title, *, why, actor="loop", at=None):
    """Change a title and record the mandatory reason atomically."""
    with store.transaction():
        store.tasks.retitle(task_id, title, why=why, actor=actor, at=at)


def record_review_decision(store, artifact, question_title, decision, *,
                           actor, at=None):
    """Record a review decision atomically without a task event."""
    with store.transaction():
        store.tasks.record_review_decision(
            artifact, question_title, decision, actor=actor, at=at)
