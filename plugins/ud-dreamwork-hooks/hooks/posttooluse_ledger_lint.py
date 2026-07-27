#!/usr/bin/env python3
"""PostToolUse hook — lint the dreamwork ledger after Write/Edit touches it.

Fires after Write/Edit (matcher "Write|Edit"). When the touched file is a
ledger file (<target>/.dreamwork/questions.md or tasks.md) in a target that
has recorded `Load: ud-dreamwork-hooks`, run the core repo's lint.py against
that target and report the verdict. A malformed ledger fails SILENTLY in the
dashboard (zero parsed entries renders as nothing to report), so the moment
right after the write is exactly when the author can still fix it cheaply.

Contract (stdlib only):
  - reads one JSON event on stdin, emits exactly one JSON object on stdout
  - ALWAYS exits 0 — a failure here must never block the tool call
  - bounded runtime (< 5s; lint subprocess timeout default 4s, overridable
    via DREAMWORK_LINT_TIMEOUT)
  - lint.py resolution: $DREAMWORK_LINT, else <dreamwork-core>/lint.py
    relative to this script (plugins/ud-dreamwork-hooks/hooks/ -> core)
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hookutil  # noqa: E402

HOOK = "ledger-lint"
LEDGER_NAMES = {"questions.md", "tasks.md"}
DEFAULT_TIMEOUT = 4.0
MAX_OUTPUT_CHARS = 2000


def _timeout() -> float:
    try:
        return max(0.1, float(os.environ.get("DREAMWORK_LINT_TIMEOUT", DEFAULT_TIMEOUT)))
    except ValueError:
        return DEFAULT_TIMEOUT


def _lint_path() -> Path:
    override = os.environ.get("DREAMWORK_LINT")
    if override:
        return Path(override)
    # plugins/ud-dreamwork-hooks/hooks/<this file> -> <core>/lint.py
    return Path(__file__).resolve().parents[3] / "lint.py"


def _tail(text: str) -> str:
    lines = text.strip().splitlines()[-20:]
    return "\n".join(lines)[:MAX_OUTPUT_CHARS]


def run() -> dict:
    payload = hookutil.read_payload()
    base = {"hook": HOOK, "plugin": hookutil.PLUGIN_ID}
    tool_input = payload.get("tool_input")
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not file_path:
        return {**base, "ok": True, "skipped": True,
                "reason": "no file_path in tool input"}
    path = Path(file_path)
    if path.name not in LEDGER_NAMES or path.parent.name != ".dreamwork":
        return {**base, "ok": True, "skipped": True,
                "reason": "not a dreamwork ledger file"}
    target = path.parent.parent
    if not hookutil.dreamwork_loads_plugin(target):
        return {**base, "ok": True, "skipped": True,
                "reason": "plugin not loaded in DREAMWORK.md"}

    lint = _lint_path()
    if not lint.is_file():
        return {**base, "ok": False, "error": f"lint.py not found: {lint}"}
    try:
        proc = subprocess.run(
            [sys.executable, str(lint), "--target", str(target)],
            capture_output=True, text=True, timeout=_timeout(),
        )
    except subprocess.TimeoutExpired:
        return {**base, "ok": False,
                "error": f"lint timed out after {_timeout()}s"}
    except Exception as error:
        return {**base, "ok": False,
                "error": f"lint could not run: {type(error).__name__}: {error}"}

    output = (proc.stdout or "") + (proc.stderr or "")
    tail = _tail(output)
    if proc.returncode != 0:
        return {**base, "ok": False,
                "error": f"lint exited {proc.returncode}", "lint_output": tail}
    verdict = "warnings" if re.search(r"\bWARN\b", output) else "clean"
    return {**base, "ok": True, "lint": verdict, "lint_output": tail}


def main() -> int:
    try:
        hookutil.emit(run())
    except Exception as error:  # fail-safe: report, never raise
        hookutil.emit({"ok": False, "hook": HOOK,
                       "error": f"{type(error).__name__}: {error}"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
