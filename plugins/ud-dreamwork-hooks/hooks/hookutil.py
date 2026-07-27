"""Shared helpers for the ud-dreamwork-hooks harness hooks (stdlib only).

Both hooks obey the same contract: read one JSON event on stdin, emit exactly
one JSON object on stdout, and ALWAYS exit 0 — a hook failure must never
block compaction or a tool call.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PLUGIN_ID = "ud-dreamwork-hooks"
MAX_STDIN_BYTES = 256 * 1024
MAX_STATE_BYTES = 1024 * 1024

_HEADING = re.compile(r"^##\s+(.+?)\s*$")
_LOAD_LINE = re.compile(r"^\s*-\s*Load:\s*`([^`]+)`(?:\s|$)")


def read_payload() -> dict:
    """Best-effort read of the hook event JSON on stdin. Never raises."""
    try:
        raw = sys.stdin.buffer.read(MAX_STDIN_BYTES + 1)
        if len(raw) > MAX_STDIN_BYTES:
            return {}
        data = json.loads(raw.decode("utf-8", "replace"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def emit(obj: dict) -> None:
    """The stdout contract: exactly one JSON object, one line."""
    sys.stdout.write(json.dumps(obj, separators=(",", ":"), default=str) + "\n")
    sys.stdout.flush()


def bounded(value, limit: int = 200):
    """Bound a value for a machine-local record; never raises."""
    if value is None or isinstance(value, (int, float, bool)):
        return value
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text[:limit]


def target_slug(target: Path) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", str(target)).strip("-").lower()
    return slug[-80:] or "unknown"


def config_dir(target: Path) -> Path:
    """Machine-local state root for this plugin. Never inside the target."""
    override = os.environ.get("DREAMWORK_HOOKS_CONFIG")
    root = Path(override) if override else Path.home() / ".config" / "dreamwork"
    return root / "hooks" / target_slug(target)


def dreamwork_loads_plugin(target: Path) -> bool:
    """True only when the target's DREAMWORK.md records
    `Load: ud-dreamwork-hooks` in its literal Plugins section.

    Mirrors plugin_resolver.py's contract (bounded, casefolded heading,
    backticked ID) so the consent boundary is enforced at hook runtime,
    not just at loop load time.
    """
    path = target / "DREAMWORK.md"
    try:
        if path.stat().st_size > MAX_STATE_BYTES:
            return False
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False
    in_plugins = False
    for line in lines:
        heading = _HEADING.match(line)
        if heading:
            in_plugins = heading.group(1).strip().casefold() == "plugins"
            continue
        if in_plugins:
            match = _LOAD_LINE.match(line)
            if match and match.group(1) == PLUGIN_ID:
                return True
    return False
