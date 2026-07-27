#!/usr/bin/env python3
"""PreCompact hook — write a preservation-focus note before compaction.

Claude Code fires this just before the transcript is compacted. The note
cannot buy landing time, but it gives the post-compact session a durable,
machine-local record of what the loop was holding: the current task, the
open-question count, and the trigger (manual/auto).

Contract (stdlib only):
  - reads one JSON event on stdin, emits exactly one JSON object on stdout
  - ALWAYS exits 0 — a failure here must never block or skip compaction
  - total wall budget < 2s
  - writes only to ~/.config/dreamwork/hooks/<target-slug>/ (machine-local,
    never committed); skips silently when the target has not recorded
    `Load: ud-dreamwork-hooks` in DREAMWORK.md
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hookutil  # noqa: E402

HOOK = "precompact-focus"
BUDGET_SECONDS = 1.5
MAX_RECORDS = 200
TRIM_TO = 100
LOG_NAME = "precompact-focus.jsonl"


def _on_alarm(signum, frame):  # noqa: ARG001
    hookutil.emit({"ok": False, "hook": HOOK, "error": "timeout"})
    os._exit(0)


def _open_question_count(path: Path):
    try:
        if not path.is_file() or path.stat().st_size > hookutil.MAX_STATE_BYTES:
            return None
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    in_open = False
    count = 0
    for line in lines:
        if line.startswith("## "):
            in_open = line[3:].strip().casefold() == "open"
            continue
        if in_open and line.lstrip().startswith("- **"):
            count += 1
    return count


def _current_task(status_path: Path):
    """Return (current_task, note). Missing file is a note, not an error."""
    try:
        if not status_path.is_file() or status_path.stat().st_size > hookutil.MAX_STATE_BYTES:
            return None, "status.json unavailable"
        status = json.loads(status_path.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(status, dict):
            return None, "status.json unreadable: not an object"
        return hookutil.bounded(status.get("current_task")), None
    except Exception as error:
        return None, f"status.json unreadable: {type(error).__name__}"


def _append_bounded(log: Path, record: dict) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    existing: list[str] = []
    try:
        if log.is_file() and log.stat().st_size <= hookutil.MAX_STATE_BYTES * 4:
            existing = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        existing = []
    if len(existing) >= MAX_RECORDS:
        existing = existing[-TRIM_TO:]
    existing.append(json.dumps(record, separators=(",", ":"), default=str))
    tmp = log.with_suffix(".tmp")
    tmp.write_text("\n".join(existing) + "\n", encoding="utf-8")
    os.replace(tmp, log)


def run() -> dict:
    payload = hookutil.read_payload()
    base = {
        "hook": HOOK,
        "plugin": hookutil.PLUGIN_ID,
        "trigger": hookutil.bounded(payload.get("trigger"), 40),
    }
    cwd = payload.get("cwd")
    target = Path(cwd).resolve() if isinstance(cwd, str) and cwd else Path.cwd()
    if not (target / ".dreamwork").is_dir():
        return {**base, "ok": False, "error": f"not a dreamwork target: {target}"}
    if not hookutil.dreamwork_loads_plugin(target):
        return {**base, "ok": True, "skipped": True,
                "reason": "plugin not loaded in DREAMWORK.md"}

    current_task, note = _current_task(target / ".dreamwork" / "status.json")
    open_questions = _open_question_count(target / ".dreamwork" / "questions.md")
    if note is None and open_questions is None:
        note = "questions.md unavailable"

    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": "PreCompact",
        "trigger": base["trigger"],
        "session_id": hookutil.bounded(payload.get("session_id"), 80),
        "target": str(target),
        "current_task": current_task,
        "open_questions": open_questions,
        "note": hookutil.bounded(note),
    }
    log = hookutil.config_dir(target) / LOG_NAME
    _append_bounded(log, record)
    out = {**base, "ok": True, "wrote": str(log),
           "focus": {"current_task": current_task, "open_questions": open_questions}}
    if note:
        out["note"] = record["note"]
    return out


def main() -> int:
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, _on_alarm)
        signal.setitimer(signal.ITIMER_REAL, BUDGET_SECONDS)
    try:
        hookutil.emit(run())
    except Exception as error:  # fail-safe: report, never raise
        hookutil.emit({"ok": False, "hook": HOOK,
                       "error": f"{type(error).__name__}: {error}"})
    finally:
        if hasattr(signal, "SIGALRM"):
            signal.setitimer(signal.ITIMER_REAL, 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
