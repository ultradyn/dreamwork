"""Append-only posture history over the canonical Dreamwork store (#866)."""

from __future__ import annotations

from typing import Any, Iterable


class PostureRepository:
    """Record already-validated axis changes without owning posture vocabulary."""

    def __init__(self, session: Any) -> None:
        self._session = session

    def append_changes(
        self,
        changes: Iterable[tuple[str, object, object]],
        *,
        at: str,
        actor: str,
        receipt_id: str | None = None,
    ) -> int:
        """Append one row per actual change and return the number written."""
        rows = [
            (at, axis, str(old), str(new), actor, receipt_id)
            for axis, old, new in changes
            if old != new
        ]
        if rows:
            self._session.executemany(
                "INSERT INTO posture_change"
                " (at, axis, old_value, new_value, actor, receipt_id)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
        return len(rows)
