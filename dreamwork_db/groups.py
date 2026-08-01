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


#: v004's fixed trio, kept as a name for callers that still import it.  The
#: authoritative vocabulary is now the ``task_group_kind`` table (#841): kinds
#: are data, so this tuple is a historical default, not the constraint.
GROUP_KINDS = ("lane", "epic", "milestone")


class EmptyGroup(ValidationError):
    """A group has no membership population from which to judge progress.

    Raised only when a group's WHOLE SUBTREE holds no task.  Without a
    denominator, progress has not been judged and no caller may draw a
    reassuring 0% or 100% (``watch.group_progress`` catches this by name and
    renders "progress unavailable" with no bar).
    """


class DependencyCycle(ValidationError):
    """An edge would close a loop, so nothing in the loop could ever start."""


@dataclass(frozen=True, slots=True)
class StoredGroup:
    id: int
    kind: str
    title: str
    description: str
    created_by: str
    created_at: str
    parent_id: int | None = None

    @property
    def label(self) -> str:
        return f"{self.kind} #{self.id} {self.title!r}"


@dataclass(frozen=True, slots=True)
class Blocker:
    """One unmet prerequisite, named on both sides."""

    dependent_kind: str
    dependent_id: int
    needs_kind: str
    needs_id: int
    reason: str

    def __str__(self) -> str:
        return (
            f"{self.dependent_kind} #{self.dependent_id} needs"
            f" {self.needs_kind} #{self.needs_id}: {self.reason}"
        )


@dataclass(frozen=True, slots=True)
class GroupProgress:
    group: StoredGroup
    member_task_ids: tuple[int, ...]
    landed_task_ids: tuple[int, ...]
    #: Groups in this subtree whose OWN subtree holds no task.  A named
    #: sub-collection that has never had work put into it is not evidence
    #: that there is no work left, so it withholds completion (#841 §3a).
    empty_group_ids: tuple[int, ...] = ()

    @property
    def completed_count(self) -> int:
        return len(self.landed_task_ids)

    @property
    def total_count(self) -> int:
        return len(self.member_task_ids)

    @property
    def completed(self) -> bool:
        return (
            not self.empty_group_ids
            and self.landed_task_ids == self.member_task_ids
        )


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

    def kinds(self) -> tuple[str, ...]:
        """The vocabulary, read from the store — never a Python literal."""
        return tuple(row[0] for row in self._session.execute(
            "SELECT kind FROM task_group_kind ORDER BY kind"
        ).fetchall())

    def define_kind(self, kind: str) -> str:
        """Widen the vocabulary without a schema change (#841 §2b)."""
        _require_text(kind, "group kind")
        kind = kind.strip()
        known = self._session.execute(
            "SELECT 1 FROM task_group_kind WHERE kind = ?", (kind,)
        ).fetchone()
        if known is not None:
            return "unchanged"
        self._session.execute(
            "INSERT INTO task_group_kind (kind) VALUES (?)", (kind,)
        )
        return "defined"

    def create(
        self, *, kind: str, title: str, description: str = "",
        actor: str, at: str, parent_id: int | None = None,
    ) -> int:
        known = self._session.execute(
            "SELECT 1 FROM task_group_kind WHERE kind = ?", (kind,)
        ).fetchone()
        if known is None:
            raise ValidationError(
                f"unknown group kind {kind!r}; defined kinds are"
                f" {self.kinds()} — define it first rather than inventing one"
            )
        if parent_id is not None:
            parent = self.get(parent_id)
            del parent
        _require_text(title, "group title")
        _require_text(actor, "group actor")
        _require_text(at, "group timestamp")
        if not isinstance(description, str):
            raise ValidationError(
                f"group description must be a string, got {description!r}"
            )
        cur = self._session.execute(
            "INSERT INTO task_group"
            " (kind, title, description, created_by, created_at, parent_id)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (kind, title.strip(), description, actor.strip(), at.strip(),
             parent_id),
        )
        return int(cur.lastrowid)

    def get(self, group_id: int) -> StoredGroup:
        row = self._session.execute(
            f"SELECT {_GROUP_COLUMNS} FROM task_group WHERE id = ?",
            (group_id,),
        ).fetchone()
        if row is None:
            raise NotFound(f"no task group #{group_id}")
        return _stored_group(row)

    def list(self) -> tuple[StoredGroup, ...]:
        rows = self._session.execute(
            f"SELECT {_GROUP_COLUMNS} FROM task_group ORDER BY id"
        ).fetchall()
        return tuple(_stored_group(row) for row in rows)

    # --- hierarchy (#841) ---------------------------------------------------

    def set_parent(self, group_id: int, parent_id: int | None) -> str:
        """Re-home one group, refusing any link that would close a cycle."""
        group = self.get(group_id)
        if parent_id is None:
            if group.parent_id is None:
                return "unchanged"
            self._session.execute(
                "UPDATE task_group SET parent_id = NULL WHERE id = ?",
                (group_id,),
            )
            return "detached"
        parent = self.get(parent_id)
        if parent_id == group_id:
            raise DependencyCycle(
                f"cannot set parent of {group.label} to itself"
            )
        chain = self._ancestor_ids(parent_id)
        if group_id in chain:
            path = chain[: chain.index(group_id) + 1]
            rendered = " -> ".join(str(node) for node in [parent_id, *path])
            raise DependencyCycle(
                f"cannot set parent of {group.label} to {parent.label}:"
                f" #{parent_id} already descends from #{group_id}"
                f" (chain {rendered}), so the link would create a cycle"
            )
        if group.parent_id == parent_id:
            return "unchanged"
        self._session.execute(
            "UPDATE task_group SET parent_id = ? WHERE id = ?",
            (parent_id, group_id),
        )
        return "reparented"

    def children(self, group_id: int) -> tuple[StoredGroup, ...]:
        self.get(group_id)
        rows = self._session.execute(
            f"SELECT {_GROUP_COLUMNS} FROM task_group"
            " WHERE parent_id = ? ORDER BY id", (group_id,),
        ).fetchall()
        return tuple(_stored_group(row) for row in rows)

    def ancestors(self, group_id: int) -> tuple[StoredGroup, ...]:
        """Nearest parent first, up to the root."""
        self.get(group_id)
        return tuple(self.get(node) for node in self._ancestor_ids(group_id))

    def descendants(self, group_id: int) -> tuple[StoredGroup, ...]:
        """Every group below this one, at any depth, excluding itself."""
        subtree = self._subtree_ids(group_id)
        return tuple(
            self.get(node) for node in subtree if node != group_id
        )

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
        """Roll the WHOLE SUBTREE up, by exact task identity.

        A task may sit in a group and in one of its ancestors at once, so the
        member set is de-duplicated by id and the counts are derived from that
        set — never counted independently, which is how a duplicate hides
        behind a plausible length (#702, #820).
        """
        group = self.get(group_id)
        subtree = self._subtree_ids(group_id)
        rows = self._session.execute(
            "SELECT DISTINCT t.id, t.state FROM task_group_member gm"
            " JOIN task t ON t.id = gm.task_id"
            f" WHERE gm.group_id IN ({_placeholders(subtree)})"
            " ORDER BY t.id", tuple(subtree),
        ).fetchall()
        if not rows:
            raise EmptyGroup(
                f"cannot judge progress for {group.kind} #{group.id}"
                # Phrased to stay compatible with the wording `#836`'s
                # dashboard guard already asserts, while naming how much
                # subtree was actually examined.
                f" {group.title!r}: 0 member tasks anywhere in its subtree"
                f" ({len(subtree)} group(s))"
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
        return GroupProgress(
            group, member_ids, landed_ids, self._empty_within(subtree)
        )

    # --- dependencies (#841) ------------------------------------------------

    def add_dependency(
        self, *, actor: str, at: str,
        dependent_group_id: int | None = None,
        dependent_task_id: int | None = None,
        needs_group_id: int | None = None,
        needs_task_id: int | None = None,
    ) -> tuple[int, str]:
        """Record one prerequisite edge with at least one group endpoint."""
        dependent = self._endpoint(
            dependent_group_id, dependent_task_id, "dependent"
        )
        needs = self._endpoint(needs_group_id, needs_task_id, "needs")
        if dependent[0] == "task" and needs[0] == "task":
            raise ValidationError(
                f"task #{dependent[1]} needs task #{needs[1]} is a task-to-task"
                " edge: its one supported home is the `depends` table, not"
                " task_group_dependency (#440)"
            )
        if dependent == needs:
            raise DependencyCycle(
                f"{dependent[0]} #{dependent[1]} cannot depend on itself"
            )
        _require_text(actor, "dependency actor")
        _require_text(at, "dependency timestamp")
        existing = self._session.execute(
            "SELECT id FROM task_group_dependency WHERE"
            " ifnull(dependent_group_id,-1) = ifnull(?,-1)"
            " AND ifnull(dependent_task_id,-1) = ifnull(?,-1)"
            " AND ifnull(needs_group_id,-1) = ifnull(?,-1)"
            " AND ifnull(needs_task_id,-1) = ifnull(?,-1)",
            (dependent_group_id, dependent_task_id,
             needs_group_id, needs_task_id),
        ).fetchone()
        if existing is not None:
            return int(existing[0]), "unchanged"
        path = self._path_to(needs, dependent)
        if path is not None:
            rendered = " -> ".join(f"{kind} #{node}" for kind, node in path)
            raise DependencyCycle(
                f"cannot record {dependent[0]} #{dependent[1]} needs"
                f" {needs[0]} #{needs[1]}: {needs[0]} #{needs[1]} already"
                f" depends on {dependent[0]} #{dependent[1]}"
                f" ({rendered}), so nothing on that path could ever start"
            )
        cur = self._session.execute(
            "INSERT INTO task_group_dependency (dependent_group_id,"
            " dependent_task_id, needs_group_id, needs_task_id,"
            " created_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (dependent_group_id, dependent_task_id, needs_group_id,
             needs_task_id, actor.strip(), at.strip()),
        )
        return int(cur.lastrowid), "recorded"

    def blockers(
        self, *, group_id: int | None = None, task_id: int | None = None,
    ) -> tuple[Blocker, ...]:
        """Every unmet prerequisite of one node, including inherited ones."""
        node = self._endpoint(group_id, task_id, "blocked")
        if node[0] == "group":
            self.get(node[1])
        elif self._session.execute(
            "SELECT 1 FROM task WHERE id = ?", (node[1],)
        ).fetchone() is None:
            raise NotFound(f"no task #{node[1]}")
        return tuple(self._unmet(node))

    def ready_tasks(self, group_id: int) -> tuple[int, ...]:
        """Open subtree tasks with no unmet prerequisite — a batch's pool.

        This is the store's whole contribution to "batched intelligently"
        (#841 §5): it names the candidates honestly.  WHICH candidates form a
        batch, and how many, is selection policy and lives in the loop.
        """
        subtree = self._subtree_ids(group_id)
        rows = self._session.execute(
            "SELECT DISTINCT t.id FROM task_group_member gm"
            " JOIN task t ON t.id = gm.task_id"
            f" WHERE gm.group_id IN ({_placeholders(subtree)})"
            " AND t.state = 'open' ORDER BY t.id", tuple(subtree),
        ).fetchall()
        return tuple(
            int(row[0]) for row in rows
            if not self._unmet(("task", int(row[0])))
        )

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


    # --- private -----------------------------------------------------------

    def _ancestor_ids(self, group_id: int) -> list[int]:
        """Parent ids, nearest first.  Stops on a repeat, so the check that
        prevents cycles cannot itself be hung by one."""
        chain: list[int] = []
        seen = {group_id}
        current = group_id
        while True:
            row = self._session.execute(
                "SELECT parent_id FROM task_group WHERE id = ?", (current,)
            ).fetchone()
            if row is None or row[0] is None:
                return chain
            current = int(row[0])
            if current in seen:
                return chain
            seen.add(current)
            chain.append(current)

    def _subtree_ids(self, group_id: int) -> tuple[int, ...]:
        """This group and every descendant, at any depth.

        ``UNION`` (not ``UNION ALL``) makes the walk terminate even against a
        store that somehow holds a cycle, and there is deliberately no
        ``LIMIT``: a limit here would silently truncate a deep tree and read
        as a complete answer (#671).
        """
        self.get(group_id)
        rows = self._session.execute(
            "WITH RECURSIVE subtree(id) AS ("
            "  SELECT ?"
            "  UNION"
            "  SELECT g.id FROM task_group g"
            "  JOIN subtree ON g.parent_id = subtree.id"
            ") SELECT id FROM subtree ORDER BY id", (group_id,),
        ).fetchall()
        return tuple(int(row[0]) for row in rows)

    def _empty_within(self, subtree: tuple[int, ...]) -> tuple[int, ...]:
        """Groups in *subtree* whose own subtree holds no task at all."""
        populated = {
            int(row[0]) for row in self._session.execute(
                "SELECT DISTINCT group_id FROM task_group_member"
                f" WHERE group_id IN ({_placeholders(subtree)})",
                tuple(subtree),
            ).fetchall()
        }
        parents = {
            int(row[0]): row[1] for row in self._session.execute(
                f"SELECT id, parent_id FROM task_group"
                f" WHERE id IN ({_placeholders(subtree)})", tuple(subtree),
            ).fetchall()
        }
        # Propagate "has a task" upward: a group is non-empty when it or any
        # descendant holds one.
        non_empty = set()
        for node in populated:
            current: int | None = node
            while current is not None and current not in non_empty:
                non_empty.add(current)
                current = parents.get(current)
                if current is not None:
                    current = int(current)
        return tuple(sorted(set(subtree) - non_empty))

    def _endpoint(
        self, group_id: int | None, task_id: int | None, label: str,
    ) -> tuple[str, int]:
        if (group_id is None) == (task_id is None):
            raise ValidationError(
                f"exactly one of {label}_group_id / {label}_task_id must be"
                f" given, got group={group_id!r} task={task_id!r}"
            )
        return ("group", int(group_id)) if group_id is not None \
            else ("task", int(task_id))

    def _needs_of(self, node: tuple[str, int]) -> list[tuple[str, int]]:
        """Direct prerequisites of one node, from BOTH dependency homes."""
        kind, node_id = node
        column = "dependent_group_id" if kind == "group" else "dependent_task_id"
        edges = [
            ("group", int(row[0])) if row[0] is not None else ("task", int(row[1]))
            for row in self._session.execute(
                "SELECT needs_group_id, needs_task_id FROM"
                f" task_group_dependency WHERE {column} = ?", (node_id,),
            ).fetchall()
        ]
        if kind == "task":
            # v001's `depends` is the one home for task -> task edges, so
            # readiness reads it rather than restating those edges (#440).
            edges.extend(
                ("task", int(row[0])) for row in self._session.execute(
                    "SELECT needs FROM depends WHERE task = ?", (node_id,)
                ).fetchall()
            )
        return edges

    def _path_to(
        self, start: tuple[str, int], goal: tuple[str, int],
    ) -> list[tuple[str, int]] | None:
        """A prerequisite path from *start* to *goal*, or ``None``."""
        stack = [(start, [start])]
        seen = {start}
        while stack:
            node, path = stack.pop()
            for nxt in self._needs_of(node):
                if nxt == goal:
                    return path + [nxt]
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append((nxt, path + [nxt]))
        return None

    def _governing_groups(self, task_id: int) -> list[int]:
        """Every group holding this task, plus all of their ancestors.

        Inherited blocking is what makes a group-level dependency mean
        anything: if an epic requires a milestone, no task inside the epic may
        start before the milestone completes.
        """
        direct = [int(row[0]) for row in self._session.execute(
            "SELECT group_id FROM task_group_member WHERE task_id = ?",
            (task_id,),
        ).fetchall()]
        governing: list[int] = []
        for group_id in direct:
            for node in [group_id, *self._ancestor_ids(group_id)]:
                if node not in governing:
                    governing.append(node)
        return governing

    def _incomplete_reason(self, node: tuple[str, int]) -> str | None:
        """Why *node* is not complete, or ``None`` when it is."""
        kind, node_id = node
        if kind == "task":
            row = self._session.execute(
                "SELECT state FROM task WHERE id = ?", (node_id,)
            ).fetchone()
            if row is None:
                return "no such task"
            return None if row[0] == "landed" else f"state is {row[0]!r}"
        try:
            progress = self.progress(node_id)
        except EmptyGroup:
            # `all([])` is vacuously true, so an empty required collection is
            # UNMET, never silently satisfied.
            return "it holds no tasks, so its completion cannot be judged"
        except NotFound:
            return "no such group"
        if progress.empty_group_ids:
            return (
                "group(s) "
                + ", ".join(f"#{gid}" for gid in progress.empty_group_ids)
                + " in its subtree hold no tasks"
            )
        outstanding = [
            task_id for task_id in progress.member_task_ids
            if task_id not in set(progress.landed_task_ids)
        ]
        if outstanding:
            return (
                f"{len(outstanding)} of {progress.total_count} subtree task(s)"
                " not landed: "
                + ", ".join(f"#{tid}" for tid in outstanding[:8])
            )
        return None

    def _unmet(self, node: tuple[str, int]) -> list[Blocker]:
        sources: list[tuple[str, int]] = [node]
        if node[0] == "task":
            sources.extend(
                ("group", gid) for gid in self._governing_groups(node[1])
            )
        found: list[Blocker] = []
        seen: set[tuple[str, int, str, int]] = set()
        for source in sources:
            for needs in self._needs_of(source):
                key = (source[0], source[1], needs[0], needs[1])
                if key in seen:
                    continue
                seen.add(key)
                reason = self._incomplete_reason(needs)
                if reason is not None:
                    found.append(Blocker(
                        dependent_kind=source[0], dependent_id=source[1],
                        needs_kind=needs[0], needs_id=needs[1], reason=reason,
                    ))
        return found


_GROUP_COLUMNS = (
    "id, kind, title, description, created_by, created_at, parent_id"
)


def _placeholders(values: tuple[Any, ...]) -> str:
    return ",".join("?" * len(values))


def _stored_group(row: tuple[Any, ...]) -> StoredGroup:
    return StoredGroup(
        id=int(row[0]), kind=row[1], title=row[2], description=row[3],
        created_by=row[4], created_at=row[5],
        parent_id=None if row[6] is None else int(row[6]),
    )


def _require_text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must be a non-empty string, got {value!r}")
