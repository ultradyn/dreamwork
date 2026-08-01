"""User-setting repository over the canonical Dreamwork store (#584)."""

from __future__ import annotations

import json
from typing import Any

from settings import LOCAL_USER_ID, SETTINGS, SettingValidationError, defaults, validate_value

from .core import ValidationError


class SettingRepository:
    """Read effective values and persist only validated non-default overrides."""

    def __init__(self, session: Any) -> None:
        self._session = session

    def effective(self, userid: str = LOCAL_USER_ID) -> dict[str, Any]:
        values = defaults()
        rows = self._session.execute(
            "SELECT key, value FROM user_setting WHERE userid = ? ORDER BY key",
            (userid,),
        ).fetchall()
        for key, encoded in rows:
            try:
                value = json.loads(encoded)
                validate_value(key, value)
            except (json.JSONDecodeError, SettingValidationError) as exc:
                raise ValidationError(
                    f"invalid stored user setting {userid}/{key}: {exc}"
                ) from exc
            values[key] = value
        return values

    def set(self, key: str, value: Any, userid: str = LOCAL_USER_ID) -> bool:
        try:
            validate_value(key, value)
        except SettingValidationError as exc:
            raise ValidationError(str(exc)) from exc
        existing = self._session.execute(
            "SELECT value FROM user_setting WHERE userid = ? AND key = ?",
            (userid, key),
        ).fetchone()
        if value == SETTINGS[key].default:
            if existing is None:
                return False
            self._session.execute(
                "DELETE FROM user_setting WHERE userid = ? AND key = ?",
                (userid, key),
            )
            return True
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if existing is not None and existing[0] == encoded:
            return False
        self._session.execute(
            "INSERT INTO user_setting(userid, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(userid, key) DO UPDATE SET value=excluded.value",
            (userid, key, encoded),
        )
        return True
