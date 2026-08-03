"""Task-store repository and binding for the legacy ledger API."""

from __future__ import annotations

import re
import hashlib
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

from ledger_store import ORIGINS, REVIEW_DECISIONS, append_chained_event, last_event_hash

from .core import StoreSpec


_KNOWN_ORIGINS = ("human", "loop")
_STORED_ORIGINS = ("human", "loop", "unknown")
_COMMIT_SHA = re.compile(r"\(([0-9a-f]{7,40})\)")
_BLOCKER_REF = re.compile(r"(task|question):([1-9][0-9]*)\Z")
_NOTE_PREFIX = "  · "


class WriteError(RuntimeError):
    """A task-store command could not be performed."""


class TaskNotFound(WriteError):
    """The requested task does not exist."""


class BadState(WriteError):
    """The task is not in the state required by a transition."""


class DecisionConflict(WriteError):
    """A final review decision belongs to a different question."""


class NotBlocked(WriteError):
    """The requested task has no blocker to clear."""


class NotNextUp(WriteError):
    """The requested task carries no next-up mark to clear."""


class SameTitle(WriteError):
    """The requested title is already current."""


class DependencyCycle(WriteError):
    """Adding the edge would close a dependency cycle."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _epoch(iso_at: object) -> int | None:
    try:
        return int(datetime.fromisoformat(iso_at).timestamp())  # type: ignore[arg-type]
    except (ValueError, TypeError, OSError):
        return None


class TaskRepository:
    """All task-ledger reads and writes over one handle-owned connection."""

    def __init__(self, session: Any) -> None:
        self._session = session

    def meta_value(self, key: str) -> str | None:
        row = self._session.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None

    def entries(self) -> list[tuple[list[int], str]]:
        rows = self._session.execute(
            "SELECT id, body, title, priority, type, origin"
            " FROM task ORDER BY id"
        ).fetchall()
        out: list[tuple[list[int], str]] = []
        for id_, body, title, priority, type_, origin in rows:
            if body.split("\n", 1)[0].startswith("- **#"):
                out.append(([int(id_)], body))
                continue
            origin_value = origin if origin in _STORED_ORIGINS else "unknown"
            fields = [value for value in (priority, type_) if value]
            fields.append(f"origin: **{origin_value}**")
            head = f"- **#{int(id_)}** — {title} · " + " · ".join(fields) + " ·"
            out.append(([int(id_)], head + "\n" + body))
        return out

    def next_up_ordinals(self) -> dict[int, int]:
        """Open tasks marked next-up → the ordinal of the mark (#884).

        The mark is DERIVED from the append-only event log rather than stored
        in a column: a task is next-up when the newest of its
        ``next_up_set``/``next_up_cleared`` events is a set.  The two causes
        were seeded by v001 and emitted zero times until #884 wired them, so
        the storage needed no migration — which also kept this off #584's
        ladder.

        The ordinal is the ``newest first`` key SKILL.md's selection step 0
        asks for.  It is the chain position, not a timestamp, so it cannot be
        reordered by clock skew.

        Scoped to ``state='open'`` deliberately: a landed task is not next-up
        whatever its history says.  There is no start event to clear the mark
        against (``task_state`` holds no rows), so the loop clears it by hand
        on start — and this scoping makes a forgotten clear self-heal at land
        instead of hoisting finished work forever.
        """
        rows = self._session.execute(
            "SELECT e.task_id, e.ordinal, e.cause FROM task_event AS e"
            " JOIN task AS t ON t.id = e.task_id"
            " WHERE t.state = 'open'"
            "   AND e.cause IN ('next_up_set', 'next_up_cleared')"
            "   AND e.ordinal = (SELECT MAX(x.ordinal) FROM task_event AS x"
            "                    WHERE x.task_id = e.task_id"
            "                      AND x.cause IN ('next_up_set',"
            "                                      'next_up_cleared'))"
        ).fetchall()
        return {int(tid): int(ordinal)
                for tid, ordinal, cause in rows if cause == "next_up_set"}

    def records(self) -> list[dict]:
        rows = self._session.execute(
            "SELECT t.id, t.state, t.title, t.body, t.priority, t.type,"
            " t.origin, t.blocked_on, MIN(e.at)"
            " FROM task AS t LEFT JOIN task_event AS e ON e.task_id = t.id"
            " GROUP BY t.id ORDER BY t.id"
        ).fetchall()
        marks = self.next_up_ordinals()
        dep_rows = self._session.execute(
            "SELECT task, needs FROM depends ORDER BY task, needs").fetchall()
        question_rows = self._session.execute(
            "SELECT id, status FROM question ORDER BY id").fetchall()
        question_statuses = {int(qid): status for qid, status in question_rows}
        depends_map: dict[int, list[int]] = {}
        for task, needs in dep_rows:
            depends_map.setdefault(int(task), []).append(int(needs))
        return [
            {"id": int(r[0]), "state": r[1], "title": r[2], "body": r[3],
             "priority": r[4], "type": r[5], "origin": r[6],
             "blocked_on": r[7], "date": r[8],
             "next_up": marks.get(int(r[0])),
             "depends_on": tuple(depends_map.get(int(r[0]), ())),
             "question_statuses": question_statuses}
            for r in rows
        ]

    def ids_by_state(self) -> tuple[list[str], list[str]]:
        open_ids = [str(row[0]) for row in self._session.execute(
            "SELECT id FROM task WHERE state = 'open' ORDER BY id")]
        landed_ids = [str(row[0]) for row in self._session.execute(
            "SELECT id FROM task WHERE state = 'landed' ORDER BY id")]
        return open_ids, landed_ids

    def landed_shas(self, task_ids: tuple[int, ...]) -> tuple[str, ...]:
        """Return landing commits for *task_ids* from the append-only store."""
        if not task_ids:
            return ()
        placeholders = ",".join("?" for _ in task_ids)
        rows = self._session.execute(
            "SELECT detail FROM task_event WHERE task_id IN (" + placeholders + ")"
            " AND to_state = 'landed' ORDER BY ordinal",
            task_ids,
        ).fetchall()
        shas: list[str] = []
        for (detail,) in rows:
            match = _COMMIT_SHA.search(detail or "")
            if match and match.group(1) not in shas:
                shas.append(match.group(1))
        return tuple(shas)

    def review_decisions(self) -> list[dict]:
        rows = self._session.execute(
            "SELECT artifact, question_title, decision, decided_at, actor"
            " FROM review_decision ORDER BY decided_at, artifact"
        ).fetchall()
        return [
            {"artifact": r[0], "question_title": r[1], "decision": r[2],
             "decided_at": r[3], "actor": r[4]}
            for r in rows
        ]

    def series_raw(self) -> dict:
        arrived_rows = self._session.execute(
            "SELECT task_id, MIN(at) FROM task_event "
            "WHERE from_state IS NULL AND to_state = 'open' "
            "GROUP BY task_id").fetchall()
        landed_rows = self._session.execute(
            "SELECT task_id, MIN(at) FROM task_event "
            "WHERE to_state = 'landed' GROUP BY task_id").fetchall()
        task_rows = self._session.execute(
            "SELECT id, state, origin FROM task").fetchall()
        time_rows = self._session.execute(
            "SELECT DISTINCT at FROM task_event ORDER BY at").fetchall()

        arrived = {str(tid): epoch for tid, at in arrived_rows
                   if (epoch := _epoch(at)) is not None}
        landed = {str(tid): epoch for tid, at in landed_rows
                  if (epoch := _epoch(at)) is not None}
        first_sight = {
            str(tid): origin if origin in _KNOWN_ORIGINS else "unknown"
            for tid, _state, origin in task_rows
        }
        latest_open = {
            str(tid) for tid, state, _origin in task_rows if state == "open"
        }
        commit_times = sorted(
            epoch for row in time_rows if (epoch := _epoch(row[0])) is not None
        )
        return {"arrived": arrived, "landed": landed,
                "first_sight": first_sight, "latest_open": latest_open,
                "commit_times": commit_times}

    def origins(self) -> list[dict]:
        task_rows = self._session.execute(
            "SELECT id, origin FROM task ORDER BY id").fetchall()
        event_rows = self._session.execute(
            "SELECT task_id, MIN(at), detail FROM task_event "
            "WHERE from_state IS NULL GROUP BY task_id").fetchall()
        first: dict[int, tuple[str, int]] = {}
        for tid, at, detail in event_rows:
            match = _COMMIT_SHA.search(detail or "")
            first[int(tid)] = (
                match.group(1) if match else "",
                _epoch(at) or 0,
            )
        return [
            {"id": int(tid),
             "origin": origin if origin in _KNOWN_ORIGINS else "unknown",
             "first_commit": first.get(int(tid), ("", 0))[0],
             "first_seen": first.get(int(tid), ("", 0))[1],
             "title": ""}
            for tid, origin in task_rows
        ]

    def incomplete_counts(self) -> tuple[int, int]:
        untyped = self._session.execute(
            "SELECT COUNT(*) FROM task WHERE type IS NULL").fetchone()[0]
        missing = self._session.execute(
            "SELECT COUNT(*) FROM task WHERE origin IS NULL").fetchone()[0]
        return int(untyped), int(missing)

    def _last_event_hash(self) -> str:
        return last_event_hash(self._session)

    def _append_chained_event(self, *, task_id: int, at: str, cause: str,
                              from_state: str | None, to_state: str | None,
                              actor: str, detail: str = "") -> None:
        append_chained_event(
            self._session, task_id=task_id, at=at, cause=cause,
            from_state=from_state, to_state=to_state, actor=actor,
            receipt_id=None, detail=detail)

    def file(self, title, body, *, priority=None, priority_uncertain=0,
             type=None, origin=None, blocked_on=None, actor="loop", at=None) -> int:
        if not isinstance(title, str) or not title.strip():
            raise WriteError("title must be a non-empty string (task.title NOT NULL)")
        if not isinstance(body, str) or not body.strip():
            raise WriteError("body must be a non-empty string (task.body NOT NULL)")
        if at is None:
            at = _now_iso()
        if priority is not None:
            bands = [r[0] for r in self._session.execute(
                "SELECT band FROM priority_band ORDER BY band")]
            if priority not in bands:
                raise WriteError(
                    "priority: got {!r}, expected one of {}".format(
                        priority, ", ".join(bands)))
        if origin is not None and origin not in ORIGINS:
            raise WriteError(
                "origin: got {!r}, expected one of {}".format(
                    origin, ", ".join(ORIGINS)))
        if type is not None:
            self._session.execute(
                "INSERT OR IGNORE INTO task_type(type) VALUES (?)", (type,))
        cur = self._session.execute(
            "INSERT INTO task(state, title, body, priority,"
            " priority_uncertain, type, origin, blocked_on, body_digest)"
            " VALUES ('open', ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, body, priority, priority_uncertain, type, origin,
             blocked_on, hashlib.sha256(body.encode()).hexdigest()))
        new_id = int(cur.lastrowid)
        self._append_chained_event(
            task_id=new_id, at=at, cause="filed_from_command",
            from_state=None, to_state="open", actor=actor)
        return new_id

    def land(self, task_id, *, note=None, actor="loop", at=None) -> None:
        at = at or _now_iso()
        cur = self._session.execute(
            "UPDATE task SET state = 'landed' WHERE id = ? AND state = 'open'",
            (task_id,))
        if cur.rowcount == 0:
            row = self._session.execute(
                "SELECT state FROM task WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise TaskNotFound(f"cannot land #{task_id}: no such task")
            raise BadState(
                f"cannot land #{task_id}: state is {row[0]!r}, not 'open' "
                "(CAS refused)")
        if note:
            self._session.execute(
                "UPDATE task SET body = body || ? WHERE id = ?",
                ("\n" + _NOTE_PREFIX + note, task_id))
        self._append_chained_event(
            task_id=task_id, at=at, cause="landed", from_state="open",
            to_state="landed", actor=actor, detail=note or "")

    def note(self, task_id, note, *, actor="loop") -> None:
        if not isinstance(note, str) or not note.strip():
            raise WriteError("note must be a non-empty string")
        cur = self._session.execute(
            "UPDATE task SET body = body || ? WHERE id = ?",
            ("\n" + _NOTE_PREFIX + note, task_id))
        if cur.rowcount == 0:
            raise TaskNotFound(f"cannot note #{task_id}: no such task")

    def reprioritise(self, task_id, priority, *, why, actor="loop", at=None) -> None:
        if not isinstance(why, str) or not why.strip():
            raise WriteError("why must be a non-empty string (the reason for the change)")
        at = at or _now_iso()
        bands = [r[0] for r in self._session.execute(
            "SELECT band FROM priority_band ORDER BY band")]
        if priority not in bands:
            raise WriteError(
                "priority: got {!r}, expected one of {}".format(
                    priority, ", ".join(bands)))
        row = self._session.execute(
            "SELECT priority, state FROM task WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise TaskNotFound(f"cannot reprioritise #{task_id}: no such task")
        old, state = row
        self._session.execute(
            "UPDATE task SET priority = ? WHERE id = ?", (priority, task_id))
        note = "reprioritised {}→{}: {}".format(old or "—", priority, why)
        self._session.execute(
            "UPDATE task SET body = body || ? WHERE id = ?",
            ("\n" + _NOTE_PREFIX + note, task_id))
        self._append_chained_event(
            task_id=task_id, at=at, cause="reprioritised", from_state=state,
            to_state=state, actor=actor, detail=why)

    def block(self, task_id, *, needs, why, actor="loop", at=None) -> str:
        """Record a typed blocker without conflating landing and answering.

        Task referents retain their FK-backed home in ``depends``. Question
        referents use the legacy ``blocked_on`` column as an exact typed value;
        their status is resolved from ``question`` by readers. Integer
        ``needs`` remains the compatibility form for the already-typed
        repository API; the CLI requires an explicit prefix.

        ``block`` writes the structured edge that ``unblock`` clears, so the
        two are genuine inverses for the edge case.  The schema's own
        ``CHECK (task <> needs)`` catches a self-edge at the DB layer; we
        refuse it here with a named message so the caller never sees a raw
        sqlite traceback.  A cycle across three tasks is refused by walking
        the existing ``depends`` graph from *needs* toward *task_id* and
        naming the path — an unrefused cycle makes ``counts`` non-terminating
        or silently wrong, and this CLI is the single writer (#1054).

        Returns ``"recorded"`` for a new edge and ``"unchanged"`` when the
        edge already exists (idempotent, like ``groups require``).
        """
        if not isinstance(why, str) or not why.strip():
            raise WriteError("why must be a non-empty string (the reason for the change)")
        at = at or _now_iso()
        row = self._session.execute(
            "SELECT state, blocked_on FROM task WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise TaskNotFound(f"cannot block #{task_id}: no such task")
        state, blocked_on = row
        kind = "task"
        if isinstance(needs, str):
            match = _BLOCKER_REF.fullmatch(needs.strip())
            if match is None:
                raise WriteError(
                    "blocker referent must be typed as task:NNN or question:NNN; "
                    "an untyped id is refused because it could resolve against "
                    "the wrong store")
            kind, raw_id = match.groups()
            needs = int(raw_id)

        if kind == "question":
            question = self._session.execute(
                "SELECT status FROM question WHERE id = ?", (needs,)).fetchone()
            if question is None:
                raise TaskNotFound(
                    f"cannot block #{task_id}: question:{needs} does not exist")
            referent = f"question:{needs}"
            if blocked_on == referent:
                return "unchanged"
            if blocked_on and blocked_on.strip():
                raise WriteError(
                    f"cannot block #{task_id} on {referent}: blocked_on already "
                    f"contains {blocked_on!r}; clear it before replacing it")
            self._session.execute(
                "UPDATE task SET blocked_on = ? WHERE id = ?", (referent, task_id))
            note = f"blocked on {referent}: {why}"
            self._session.execute(
                "UPDATE task SET body = body || ? WHERE id = ?",
                ("\n" + _NOTE_PREFIX + note, task_id))
            self._append_chained_event(
                task_id=task_id, at=at, cause="blocked", from_state=state,
                to_state=state, actor=actor, detail=why)
            return "recorded"

        needs_row = self._session.execute(
            "SELECT 1 FROM task WHERE id = ?", (needs,)).fetchone()
        if needs_row is None:
            raise TaskNotFound(f"cannot block #{task_id}: blocker #{needs} does not exist")
        if task_id == needs:
            raise DependencyCycle(
                f"cannot block #{task_id} on itself: a self-dependency can "
                "never resolve and would make the task permanently stuck")
        existing = self._session.execute(
            "SELECT 1 FROM depends WHERE task = ? AND needs = ?",
            (task_id, needs)).fetchone()
        if existing is not None:
            return "unchanged"
        cycle = self._depends_path(needs, task_id)
        if cycle is not None:
            rendered = " -> ".join("#{}".format(n) for n in cycle)
            raise DependencyCycle(
                f"cannot block #{task_id} on #{needs}: #{needs} already "
                f"depends on #{task_id} ({rendered}), so nothing on that "
                "path could ever start")
        self._session.execute(
            "INSERT INTO depends (task, needs) VALUES (?, ?)",
            (task_id, needs))
        note = "blocked on #{}: {}".format(needs, why)
        self._session.execute(
            "UPDATE task SET body = body || ? WHERE id = ?",
            ("\n" + _NOTE_PREFIX + note, task_id))
        self._append_chained_event(
            task_id=task_id, at=at, cause="blocked", from_state=state,
            to_state=state, actor=actor, detail=why)
        return "recorded"

    def _depends_path(self, start: int, goal: int) -> list[int] | None:
        """A ``depends`` path from *start* to *goal*, or ``None``.

        DFS following ``needs`` edges; returns the node-id path (inclusive
        of both endpoints) if *goal* is reachable from *start*, else None.
        """
        stack = [(start, [start])]
        seen = {start}
        while stack:
            node, path = stack.pop()
            for (nxt,) in self._session.execute(
                    "SELECT needs FROM depends WHERE task = ?", (node,)).fetchall():
                if nxt == goal:
                    return path + [nxt]
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append((nxt, path + [nxt]))
        return None

    def unblock(self, task_id, *, why, actor="loop", at=None) -> None:
        if not isinstance(why, str) or not why.strip():
            raise WriteError("why must be a non-empty string (the reason for the change)")
        at = at or _now_iso()
        row = self._session.execute(
            "SELECT blocked_on, state FROM task WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise TaskNotFound(f"cannot unblock #{task_id}: no such task")
        old_blocked, state = row
        old_edges = tuple(int(r[0]) for r in self._session.execute(
            "SELECT needs FROM depends WHERE task = ? ORDER BY needs",
            (task_id,)).fetchall())
        has_prose = bool(old_blocked and old_blocked.strip())
        if not has_prose and not old_edges:
            raise NotBlocked(
                f"cannot unblock #{task_id}: it is not blocked "
                "(blocked_on is empty and no depends edge) — an unblock "
                "that unblocked nothing must not read as success (#671)")
        if has_prose:
            self._session.execute(
                "UPDATE task SET blocked_on = NULL WHERE id = ?", (task_id,))
        if old_edges:
            self._session.execute(
                "DELETE FROM depends WHERE task = ?", (task_id,))
        parts = []
        if has_prose:
            parts.append("was: {}".format(old_blocked))
        if old_edges:
            parts.append("depended on {}".format(
                ", ".join("#{}".format(e) for e in old_edges)))
        note = "unblocked ({}): {}".format("; ".join(parts), why)
        self._session.execute(
            "UPDATE task SET body = body || ? WHERE id = ?",
            ("\n" + _NOTE_PREFIX + note, task_id))
        self._append_chained_event(
            task_id=task_id, at=at, cause="unblocked", from_state=state,
            to_state=state, actor=actor, detail=why)

    def retitle(self, task_id, title, *, why, actor="loop", at=None) -> None:
        if not isinstance(title, str) or not title.strip():
            raise WriteError("title must be a non-empty string (task.title NOT NULL)")
        if not isinstance(why, str) or not why.strip():
            raise WriteError("why must be a non-empty string (the reason for the change)")
        at = at or _now_iso()
        row = self._session.execute(
            "SELECT title, state FROM task WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise TaskNotFound(f"cannot retitle #{task_id}: no such task")
        old_title, state = row
        if title == old_title:
            raise SameTitle(
                f"cannot retitle #{task_id}: title is unchanged — a retitle "
                "that changed nothing must not read as success (#671)")
        self._session.execute(
            "UPDATE task SET title = ? WHERE id = ?", (title, task_id))
        note = "retitled {!r}→{!r}: {}".format(old_title, title, why)
        self._session.execute(
            "UPDATE task SET body = body || ? WHERE id = ?",
            ("\n" + _NOTE_PREFIX + note, task_id))
        self._append_chained_event(
            task_id=task_id, at=at, cause="reconciled", from_state=state,
            to_state=state, actor=actor, detail=why)

    def set_next_up(self, task_id, *, why, actor="loop", at=None) -> None:
        """Mark a task next-up — the human's steer, ahead of priority (#884).

        Re-setting an already-marked task is NOT a no-op and is allowed: it
        mints a newer mark, which is how "several next-ups: newest first"
        lets his latest steer win.
        """
        if not isinstance(why, str) or not why.strip():
            raise WriteError(
                "why must be a non-empty string (what he asked for)")
        at = at or _now_iso()
        row = self._session.execute(
            "SELECT state FROM task WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise TaskNotFound(f"cannot mark #{task_id} next-up: no such task")
        state = row[0]
        if state != "open":
            raise BadState(
                f"cannot mark #{task_id} next-up: state is {state!r}, not "
                "'open' — a task that is not open cannot be picked next")
        self._session.execute(
            "UPDATE task SET body = body || ? WHERE id = ?",
            ("\n" + _NOTE_PREFIX + f"marked next-up: {why}", task_id))
        self._append_chained_event(
            task_id=task_id, at=at, cause="next_up_set", from_state=state,
            to_state=state, actor=actor, detail=why)

    def clear_next_up(self, task_id, *, why, actor="loop", at=None) -> None:
        """Clear the next-up mark — SKILL.md's "clearing the mark on start"."""
        if not isinstance(why, str) or not why.strip():
            raise WriteError(
                "why must be a non-empty string (the reason for the change)")
        at = at or _now_iso()
        row = self._session.execute(
            "SELECT state FROM task WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise TaskNotFound(
                f"cannot clear #{task_id}'s next-up mark: no such task")
        if task_id not in self.next_up_ordinals():
            raise NotNextUp(
                f"cannot clear #{task_id}'s next-up mark: it is not marked "
                "next-up — a clear that cleared nothing must not read as "
                "success (#671)")
        state = row[0]
        self._session.execute(
            "UPDATE task SET body = body || ? WHERE id = ?",
            ("\n" + _NOTE_PREFIX + f"next-up mark cleared: {why}", task_id))
        self._append_chained_event(
            task_id=task_id, at=at, cause="next_up_cleared", from_state=state,
            to_state=state, actor=actor, detail=why)

    def record_review_decision(self, artifact, question_title, decision, *,
                               actor, at=None) -> None:
        if decision not in REVIEW_DECISIONS:
            raise WriteError(
                f"decision must be one of {REVIEW_DECISIONS}, got {decision!r}")
        at = at or _now_iso()
        existing = self._session.execute(
            "SELECT question_title, decision FROM review_decision "
            "WHERE artifact = ?", (artifact,)).fetchone()
        if existing is not None:
            ex_title, ex_decision = existing
            if ex_title != question_title and ex_decision != "pending":
                raise DecisionConflict(
                    f"artifact {artifact!r} is already decided {ex_decision!r} "
                    f"under a different question ({ex_title!r} vs "
                    f"{question_title!r}); a final review decision is not "
                    "silently reassignable to another question")
        self._session.execute(
            "INSERT OR REPLACE INTO review_decision"
            "(artifact, question_title, decision, decided_at, actor)"
            " VALUES (?, ?, ?, ?, ?)",
            (artifact, question_title, decision, at, actor))


def task_store_spec(path: str | Path) -> StoreSpec:
    """Compatibility facade for the canonical Dreamwork store spec."""

    # Local import avoids a module cycle while ``store`` composes this
    # repository with the question and review repositories.
    from .store import dreamwork_store_spec

    return dreamwork_store_spec(path)
