"""First-class lanes, epics, and milestones over canonical task state.

Membership has one authoritative home: ``task_group_member``.  Progress is
derived from those exact task ids joined to ``task.state``; neither counts nor
Markdown metadata are stored as a second truth.  A ``lane`` here is a durable
planning group, not a process-liveness record.  Completion therefore survives
restarts and does not depend on the currently unreliable lane detector (#821).

Completion-trigger definitions are deliberately inert.  ``ready_triggers`` is
the future trigger seam: after a task transition commits, an orchestrator may
read affected groups and enqueue each returned definition through a durable,
idempotent outbox before calling ``TaskRepository.file``.  This module does
not enqueue, claim, or file tasks; polling it cannot mutate the loop's brain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .core import Conflict, NotFound, ValidationError


GROUP_KINDS = ("lane", "epic", "milestone")


class EmptyGroup(ValidationError):
    """A group has no membership population from which to judge progress."""


@dataclass(frozen=True, slots=True)
class StoredGroup:
    id: int
    kind: str
    title: str
    description: str
    created_by: str
    created_at: str


@dataclass(frozen=True, slots=True)
class GroupProgress:
    group: StoredGroup
    member_task_ids: tuple[int, ...]
    landed_task_ids: tuple[int, ...]

    @property
    def completed_count(self) -> int:
        return len(self.landed_task_ids)

    @property
    def total_count(self) -> int:
        return len(self.member_task_ids)

    @property
    def completed(self) -> bool:
        return self.landed_task_ids == self.member_task_ids


@dataclass(frozen=True, slots=True)
class CompletionTrigger:
    id: int
    group_id: int
    task_title: str
    task_priority: str | None
    task_type: str


class GroupRepository:
    """Grouping reads and writes over one handle-owned connection."""

    def __init__(self, session: Any) -> None:
        self._session = session

    def create(
        self, *, kind: str, title: str, description: str = "",
        actor: str, at: str,
    ) -> int:
        if kind not in GROUP_KINDS:
            raise ValidationError(
                f"group kind must be one of {GROUP_KINDS}, got {kind!r}"
            )
        _require_text(title, "group title")
        _require_text(actor, "group actor")
        _require_text(at, "group timestamp")
        if not isinstance(description, str):
            raise ValidationError(
                f"group description must be a string, got {description!r}"
            )
        cur = self._session.execute(
            "INSERT INTO task_group"
            " (kind, title, description, created_by, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (kind, title.strip(), description, actor.strip(), at.strip()),
        )
        return int(cur.lastrowid)

    def get(self, group_id: int) -> StoredGroup:
        row = self._session.execute(
            "SELECT id, kind, title, description, created_by, created_at"
            " FROM task_group WHERE id = ?", (group_id,),
        ).fetchone()
        if row is None:
            raise NotFound(f"no task group #{group_id}")
        return _stored_group(row)

    def list(self) -> tuple[StoredGroup, ...]:
        rows = self._session.execute(
            "SELECT id, kind, title, description, created_by, created_at"
            " FROM task_group ORDER BY id"
        ).fetchall()
        return tuple(_stored_group(row) for row in rows)

    def add_task(
        self, group_id: int, task_id: int, *, actor: str, at: str,
    ) -> str:
        group = self.get(group_id)
        task = self._session.execute(
            "SELECT id FROM task WHERE id = ?", (task_id,),
        ).fetchone()
        if task is None:
            raise NotFound(
                f"cannot add task #{task_id} to {group.kind} #{group_id}"
                f" {group.title!r}: no such task"
            )
        existing = self._session.execute(
            "SELECT 1 FROM task_group_member WHERE group_id = ? AND task_id = ?",
            (group_id, task_id),
        ).fetchone()
        if existing is not None:
            return "unchanged"
        _require_text(actor, "membership actor")
        _require_text(at, "membership timestamp")
        self._session.execute(
            "INSERT INTO task_group_member"
            " (group_id, task_id, added_by, added_at) VALUES (?, ?, ?, ?)",
            (group_id, task_id, actor.strip(), at.strip()),
        )
        return "added"

    def progress(self, group_id: int) -> GroupProgress:
        group = self.get(group_id)
        rows = self._session.execute(
            "SELECT t.id, t.state FROM task_group_member gm"
            " JOIN task t ON t.id = gm.task_id"
            " WHERE gm.group_id = ? ORDER BY t.id", (group_id,),
        ).fetchall()
        if not rows:
            raise EmptyGroup(
                f"cannot judge progress for {group.kind} #{group.id}"
                f" {group.title!r}: group has 0 member tasks"
            )
        invalid = [(int(task_id), state) for task_id, state in rows
                   if state not in ("open", "landed")]
        if invalid:
            raise Conflict(
                f"cannot judge progress for {group.kind} #{group.id}"
                f" {group.title!r}: implausible task states {invalid}"
            )
        member_ids = tuple(int(task_id) for task_id, _ in rows)
        landed_ids = tuple(int(task_id) for task_id, state in rows
                           if state == "landed")
        return GroupProgress(group, member_ids, landed_ids)

    def register_completion_task(
        self, group_id: int, *, title: str, actor: str, at: str,
        priority: str | None = None, task_type: str = "task",
    ) -> tuple[int, str]:
        self.get(group_id)
        _require_text(title, "lifecycle task title")
        _require_text(actor, "lifecycle trigger actor")
        _require_text(at, "lifecycle trigger timestamp")
        _require_text(task_type, "lifecycle task type")
        existing = self._session.execute(
            "SELECT id FROM task_group_trigger"
            " WHERE group_id = ? AND event = 'completed' AND task_title = ?",
            (group_id, title.strip()),
        ).fetchone()
        if existing is not None:
            return int(existing[0]), "unchanged"
        if priority is not None:
            known = self._session.execute(
                "SELECT 1 FROM priority_band WHERE band = ?", (priority,),
            ).fetchone()
            if known is None:
                raise ValidationError(
                    f"unknown lifecycle task priority {priority!r}"
                )
        cur = self._session.execute(
            "INSERT INTO task_group_trigger"
            " (group_id, event, task_title, task_priority, task_type,"
            "  created_by, created_at) VALUES (?, 'completed', ?, ?, ?, ?, ?)",
            (group_id, title.strip(), priority, task_type.strip(),
             actor.strip(), at.strip()),
        )
        return int(cur.lastrowid), "registered"

    def triggers(self, group_id: int) -> tuple[CompletionTrigger, ...]:
        self.get(group_id)
        rows = self._session.execute(
            "SELECT id, group_id, task_title, task_priority, task_type"
            " FROM task_group_trigger WHERE group_id = ? ORDER BY id",
            (group_id,),
        ).fetchall()
        return tuple(CompletionTrigger(
            id=int(row[0]), group_id=int(row[1]), task_title=row[2],
            task_priority=row[3], task_type=row[4],
        ) for row in rows)

    def ready_triggers(self, group_id: int) -> tuple[CompletionTrigger, ...]:
        """Return inert definitions only when a non-empty group is complete."""
        progress = self.progress(group_id)
        return self.triggers(group_id) if progress.completed else ()


def _stored_group(row: tuple[Any, ...]) -> StoredGroup:
    return StoredGroup(
        id=int(row[0]), kind=row[1], title=row[2], description=row[3],
        created_by=row[4], created_at=row[5],
    )


def _require_text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must be a non-empty string, got {value!r}")
