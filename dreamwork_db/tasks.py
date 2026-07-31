"""Task-store repository and binding for the legacy ledger read API."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .core import StoreSpec


_KNOWN_ORIGINS = ("human", "loop")
_STORED_ORIGINS = ("human", "loop", "unknown")
_COMMIT_SHA = re.compile(r"\(([0-9a-f]{7,40})\)")


def _epoch(iso_at: object) -> int | None:
    try:
        return int(datetime.fromisoformat(iso_at).timestamp())  # type: ignore[arg-type]
    except (ValueError, TypeError, OSError):
        return None


class TaskRepository:
    """All task-ledger reads over one handle-owned snapshot."""

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


def task_store_spec(path: str | Path) -> StoreSpec:
    """Bind the task repository through the core's one factory seam."""
    return StoreSpec(path, repositories={"tasks": TaskRepository})
