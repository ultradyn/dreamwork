"""Append-only posture history over the canonical Dreamwork store (#866)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


POSTURE_AGREE = "AGREE"
POSTURE_DISAGREE = "DISAGREE"
POSTURE_CANNOT_COMPARE = "CANNOT_COMPARE"
_UNSET_HISTORY_VALUE = "\x1eunset"


def _history_value(value: object) -> str:
    """Keep an unset value distinct from the literal posture text ``None``."""
    return _UNSET_HISTORY_VALUE if value is None else str(value)


def _display_value(value: object) -> str:
    return "<absent>" if value is None else repr(value)


def resolve_posture_agreement(
    file_posture: Mapping[str, object] | None,
    history_posture: Mapping[str, object],
    axes: Iterable[str],
    *,
    file_error: str | None = None,
    history_error: str | None = None,
) -> dict[str, object]:
    """Compare parsed file posture with the point reconstructed from history."""
    axis_names = tuple(axes)
    differences: list[dict[str, object]] = []
    uncompared: list[str] = []

    if file_posture is None:
        uncompared.extend(axis_names)
    else:
        for axis in axis_names:
            if axis not in file_posture or axis not in history_posture:
                uncompared.append(axis)
                continue
            file_value = file_posture[axis]
            history_value = history_posture[axis]
            if _history_value(file_value) != _history_value(history_value):
                differences.append({
                    "axis": axis,
                    "file": file_value,
                    "db": history_value,
                })

    compared = len(axis_names) - len(uncompared)
    if differences:
        status = POSTURE_DISAGREE
        detail = "; ".join(
            f"{item['axis']} file={_display_value(item['file'])} "
            f"db={_display_value(item['db'])}"
            for item in differences
        )
    elif uncompared:
        status = POSTURE_CANNOT_COMPARE
        if file_posture is None:
            detail = file_error or "posture file did not resolve"
        elif not history_posture:
            detail = history_error or "posture history is empty"
        else:
            detail = "missing axis on file or db side: " + ", ".join(uncompared)
    else:
        status = POSTURE_AGREE
        detail = "all posture axes match"

    return {
        "status": status,
        "message": (
            f"{status}: {detail}; axes compared {compared}, "
            f"axes not compared {len(uncompared)}"
        ),
        "differences": differences,
        "uncompared_axes": uncompared,
        "axes_compared": compared,
        "axes_not_compared": len(uncompared),
    }


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
            (at, axis, _history_value(old), _history_value(new), actor, receipt_id)
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

    def current(self) -> dict[str, object]:
        """Reconstruct the latest known value for every axis from history."""
        rows = self._session.execute(
            "SELECT axis, old_value, new_value FROM posture_change "
            "ORDER BY ordinal"
        ).fetchall()
        current: dict[str, object] = {}
        for axis, _old_value, new_value in rows:
            current[axis] = None if new_value == _UNSET_HISTORY_VALUE else new_value
        return current

    def agreement(
        self,
        file_posture: Mapping[str, object] | None,
        axes: Iterable[str],
        *,
        file_error: str | None = None,
    ) -> dict[str, object]:
        return resolve_posture_agreement(
            file_posture, self.current(), axes, file_error=file_error
        )
