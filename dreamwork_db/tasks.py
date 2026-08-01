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


class SameTitle(WriteError):
    """The requested title is already current."""


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

    def records(self) -> list[dict]:
        rows = self._session.execute(
            "SELECT id, state, title, body, priority, type, origin, blocked_on"
            " FROM task ORDER BY id"
        ).fetchall()
        return [
            {"id": int(r[0]), "state": r[1], "title": r[2], "body": r[3],
             "priority": r[4], "type": r[5], "origin": r[6],
             "blocked_on": r[7]}
            for r in rows
        ]

    def ids_by_state(self) -> tuple[list[str], list[str]]:
        open_ids = [str(row[0]) for row in self._session.execute(
            "SELECT id FROM task WHERE state = 'open' ORDER BY id")]
        landed_ids = [str(row[0]) for row in self._session.execute(
            "SELECT id FROM task WHERE state = 'landed' ORDER BY id")]
        return open_ids, landed_ids

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

    def unblock(self, task_id, *, why, actor="loop", at=None) -> None:
        if not isinstance(why, str) or not why.strip():
            raise WriteError("why must be a non-empty string (the reason for the change)")
        at = at or _now_iso()
        row = self._session.execute(
            "SELECT blocked_on, state FROM task WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise TaskNotFound(f"cannot unblock #{task_id}: no such task")
        old_blocked, state = row
        if not old_blocked or not old_blocked.strip():
            raise NotBlocked(
                f"cannot unblock #{task_id}: it is not blocked "
                "(blocked_on is empty) — an unblock that unblocked nothing "
                "must not read as success (#671)")
        self._session.execute(
            "UPDATE task SET blocked_on = NULL WHERE id = ?", (task_id,))
        note = "unblocked (was: {}): {}".format(old_blocked, why)
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
