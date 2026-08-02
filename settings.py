"""Code-declared user-setting registry and value validation (#584)."""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, Mapping


SETTING_KINDS = ("boolean", "enum", "number", "string")
SETTING_CONTROLS = ("radio", "select")
HIDDEN_SUBTYPES = ("advanced", "dev", "debug", "lowLevel")
LOCAL_USER_ID = "local"


class SettingValidationError(ValueError):
    """A key, registry declaration, or value violates the settings schema."""


@dataclass(frozen=True, slots=True)
class Setting:
    kind: str
    default: Any
    label: str
    category: str
    description: str
    values: tuple[Any, ...] = ()
    labels: Mapping[Any, str] | None = None
    control: str | None = None
    hidden: str | None = None
    minimum: float | None = None
    maximum: float | None = None


SETTINGS = MappingProxyType({
    "composer.askMeDefault": Setting(
        kind="boolean",
        default=False,
        label="Ask me by default",
        category="Composer",
        description="Start new composer drafts in ask-me mode.",
    ),
    "composer.rememberManualResize": Setting(
        kind="boolean",
        default=False,
        label="Remember manual size",
        category="Composer",
        description="Restore the composer's last manually chosen size.",
    ),
    "gfx.dither": Setting(
        kind="enum",
        default="ign",
        label="Dither",
        category="Graphics",
        description="Choose the dashboard's dithering pattern.",
        values=("ign", "white-noise", "bayer"),
        labels=MappingProxyType({
            "ign": "IGN", "white-noise": "White noise", "bayer": "Bayer",
        }),
        control="radio",
    ),
    "links.backtickTasks": Setting(
        kind="boolean",
        default=True,
        label="Link task ids in code spans",
        category="Links",
        description="Turn a task id written inside backticks (like `#1007`) "
                    "into a link. Turn off to keep them as literal text.",
    ),
})


def validate_registry(registry: Mapping[str, Setting] = SETTINGS) -> list[str]:
    """Return every declaration error without stopping at the first one."""
    errors: list[str] = []
    for key, spec in registry.items():
        prefix = f"{key}: "
        if not isinstance(key, str) or not key.strip():
            errors.append(prefix + "key must be a non-empty string")
            continue
        if not isinstance(spec, Setting):
            errors.append(prefix + "entry must be a Setting")
            continue
        if spec.kind not in SETTING_KINDS:
            errors.append(prefix + f"unknown kind {spec.kind!r}")
        if not spec.label.strip() or not spec.category.strip():
            errors.append(prefix + "label and category must be non-empty")
        if not spec.description.strip():
            errors.append(prefix + "description must be non-empty")
        if spec.hidden is not None and spec.hidden not in HIDDEN_SUBTYPES:
            errors.append(prefix + f"unknown hidden subtype {spec.hidden!r}")
        if spec.control is not None and spec.control not in SETTING_CONTROLS:
            errors.append(prefix + f"unknown control {spec.control!r}")
        if spec.kind == "enum":
            if not spec.values or len(set(spec.values)) != len(spec.values):
                errors.append(prefix + "enum values must be non-empty and unique")
            if spec.default not in spec.values:
                errors.append(prefix + "enum default must be in values")
            if spec.labels is not None and set(spec.labels) != set(spec.values):
                errors.append(prefix + "enum labels must cover values exactly")
        elif spec.values or spec.labels is not None or spec.control is not None:
            errors.append(prefix + "values, labels, and control require enum kind")
        try:
            validate_value_for(spec, spec.default)
        except SettingValidationError as exc:
            errors.append(prefix + f"invalid default: {exc}")
    return errors


def validate_value_for(spec: Setting, value: Any) -> Any:
    """Return *value* if its exact JSON scalar type satisfies *spec*."""
    if spec.kind == "boolean":
        if type(value) is not bool:
            raise SettingValidationError("expected a boolean")
    elif spec.kind == "enum":
        if value not in spec.values:
            raise SettingValidationError(
                f"expected one of {', '.join(map(repr, spec.values))}"
            )
    elif spec.kind == "number":
        if type(value) not in (int, float):
            raise SettingValidationError("expected a number")
        if not math.isfinite(value):
            raise SettingValidationError("expected a finite number")
        if spec.minimum is not None and value < spec.minimum:
            raise SettingValidationError(f"expected a number >= {spec.minimum}")
        if spec.maximum is not None and value > spec.maximum:
            raise SettingValidationError(f"expected a number <= {spec.maximum}")
    elif spec.kind == "string":
        if type(value) is not str:
            raise SettingValidationError("expected a string")
    else:
        raise SettingValidationError(f"unknown setting kind {spec.kind!r}")
    return value


def validate_value(key: str, value: Any) -> Any:
    """Validate a registered key/value pair, refusing arbitrary keys."""
    try:
        spec = SETTINGS[key]
    except (KeyError, TypeError) as exc:
        raise SettingValidationError(f"unknown setting key {key!r}") from exc
    return validate_value_for(spec, value)


def defaults() -> dict[str, Any]:
    """Return a fresh effective-value map for a store with no overrides."""
    return {key: spec.default for key, spec in SETTINGS.items()}


def public_registry() -> dict[str, dict[str, Any]]:
    """JSON-ready registry metadata for the generic settings page."""
    return {
        key: {
            "kind": spec.kind,
            "default": spec.default,
            "label": spec.label,
            "category": spec.category,
            "description": spec.description,
            "values": list(spec.values),
            "labels": dict(spec.labels or {}),
            "control": spec.control,
            "hidden": spec.hidden,
            "minimum": spec.minimum,
            "maximum": spec.maximum,
        }
        for key, spec in SETTINGS.items()
    }
