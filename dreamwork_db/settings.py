"""User-setting repository over the canonical Dreamwork store (#584)."""

from __future__ import annotations

import json
from typing import Any

from settings import LOCAL_USER_ID, SETTINGS, SettingValidationError, defaults, validate_value

from .core import ValidationError


class BatchSettingValidationError(ValidationError):
    """All per-key refusals from one batch, before any write is attempted."""

    def __init__(self, errors: dict[str, str]) -> None:
        self.errors = errors
        super().__init__("; ".join(f"{key}: {error}" for key, error in errors.items()))


class SettingRepository:
    """Read effective values and persist only validated non-default overrides."""

    def __init__(self, session: Any) -> None:
        self._session = session

    def effective(self, userid: str = LOCAL_USER_ID) -> dict[str, Any]:
        if userid != LOCAL_USER_ID:
            raise ValidationError(f"unsupported userid {userid!r}; v1 is local-only")
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
        if userid != LOCAL_USER_ID:
            raise ValidationError(f"unsupported userid {userid!r}; v1 is local-only")
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
        encoded = json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )
        if existing is not None and existing[0] == encoded:
            return False
        self._session.execute(
            "INSERT INTO user_setting(userid, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(userid, key) DO UPDATE SET value=excluded.value",
            (userid, key, encoded),
        )
        return True

    def get_many(
        self, keys: list[str] | tuple[str, ...], userid: str = LOCAL_USER_ID
    ) -> dict[str, Any]:
        """Return a non-empty registry-validated subset of effective values."""
        if userid != LOCAL_USER_ID:
            raise ValidationError(f"unsupported userid {userid!r}; v1 is local-only")
        errors: dict[str, str] = {}
        if not keys:
            errors["$batch"] = "at least one setting key is required"
        for index, key in enumerate(keys):
            if not isinstance(key, str):
                errors[f"$key[{index}]"] = "setting key must be a string"
            elif key not in SETTINGS:
                errors[key] = f"unknown setting key {key!r}"
        string_keys = [key for key in keys if isinstance(key, str)]
        if len(set(string_keys)) != len(string_keys):
            errors["$batch"] = "setting keys must be unique"
        if errors:
            raise BatchSettingValidationError(errors)
        values = self.effective(userid)
        return {key: values[key] for key in keys}

    def set_many(
        self, values: dict[str, Any], userid: str = LOCAL_USER_ID
    ) -> list[str]:
        """Validate every entry, then apply the batch through the one-key seam."""
        if userid != LOCAL_USER_ID:
            raise ValidationError(f"unsupported userid {userid!r}; v1 is local-only")
        errors: dict[str, str] = {}
        if not values:
            errors["$batch"] = "at least one setting value is required"
        for key, value in values.items():
            try:
                validate_value(key, value)
            except SettingValidationError as exc:
                errors[key] = str(exc)
        if errors:
            raise BatchSettingValidationError(errors)
        return [key for key, value in values.items() if self.set(key, value, userid)]
