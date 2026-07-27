"""Fixtures shared by the ud-dreamwork-hooks hook tests."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "hooks"
PRECOMPACT = HOOKS / "precompact_focus.py"
LEDGER_LINT = HOOKS / "posttooluse_ledger_lint.py"
INSTALL = ROOT / "install.py"

LOAD_BLOCK = """# Dreamwork

## Plugins

- Load: `ud-dreamwork-hooks` — approved 2026-07-27
"""

QUESTIONS_MD = """# Questions for the human

## Open

- **2026-07-27 — First open question.** Body text.

- **2026-07-27 — Second open question.** Body text.

## Answered

- **2026-07-26 — Old question.** → answered (2026-07-26 10:00): done.
"""


def make_target(base: Path, *, load_line: bool = True, status: dict | None = None) -> Path:
    """Create a minimal dreamwork target under `base`."""
    target = base / "target"
    dw = target / ".dreamwork"
    dw.mkdir(parents=True)
    (target / "DREAMWORK.md").write_text(
        LOAD_BLOCK if load_line else "# Dreamwork\n\n## Plugins\n\n- (none)\n",
        encoding="utf-8",
    )
    (dw / "questions.md").write_text(QUESTIONS_MD, encoding="utf-8")
    if status is not None:
        (dw / "status.json").write_text(json.dumps(status), encoding="utf-8")
    return target


def run_script(script: Path, payload, *, env_extra: dict | None = None,
               cwd: Path | None = None, timeout: float = 15.0) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(env_extra or {})
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(script)],
        input=raw, capture_output=True, text=True,
        cwd=str(cwd) if cwd else None, env=env, timeout=timeout,
    )


def assert_contract(proc: subprocess.CompletedProcess) -> dict:
    """The stdout contract: exit 0, exactly one line, one JSON object."""
    assert proc.returncode == 0, f"rc={proc.returncode} stderr={proc.stderr!r}"
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1, f"stdout must be one JSON line, got: {proc.stdout!r}"
    obj = json.loads(lines[0])
    assert isinstance(obj, dict)
    assert "ok" in obj
    return obj


def precompact_payload(target: Path, trigger: str = "manual") -> dict:
    return {
        "session_id": "sess-test",
        "transcript_path": "/tmp/transcript.jsonl",
        "cwd": str(target),
        "hook_event_name": "PreCompact",
        "trigger": trigger,
        "custom_instructions": "",
    }


def posttool_payload(file_path: Path, tool_name: str = "Write") -> dict:
    return {
        "session_id": "sess-test",
        "transcript_path": "/tmp/transcript.jsonl",
        "cwd": str(file_path.parent.parent),
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": {"file_path": str(file_path)},
        "tool_response": {"success": True},
    }
