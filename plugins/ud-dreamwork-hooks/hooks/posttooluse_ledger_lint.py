#!/usr/bin/env python3
"""PostToolUse hook — lint the dreamwork ledger after Write/Edit touches it.

Two routes, decided by whether the event carries a ``file_path``:

- **Write/Edit (``file_path`` present).** The matcher is ``"Write|Edit"`` and
  the touched file is the payload's ``file_path``. If it is a ledger file
  (``<target>/.dreamwork/questions.md`` or ``tasks.md``) in a target that
  records ``Load: ud-dreamwork-hooks``, run the core repo's lint.py and report
  the verdict. A malformed ledger fails SILENTLY in the dashboard (zero parsed
  entries renders as nothing to report), so the moment right after the write is
  exactly when the author can still fix it cheaply.

- **Bash (no ``file_path``).** #387: the coordinator's structural ledger edits
  go through Bash heredocs (``python3 - <<PY … write_text(…)``), so the
  ``file_path`` route has never seen a real ledger write. A Bash event's
  ``tool_input`` carries a command string, not a path — the ledger path lives
  *inside* the heredoc as Python source — so the hook ignores ``tool_input``
  entirely and keys off the **file**: it resolves the target from the event's
  ``cwd`` and compares the two ledger files' mtimes against a small stored
  state. Lint only when one moved. Robust to any writer (heredoc, sed, an
  editor, another agent), at the cost of one ``stat`` per Bash call.

  This branch is repo-side only. The matcher widening (``Write|Edit`` →
  ``Write|Edit|Bash`` in ``~/.claude/settings.json``) is install-side and
  behind #465's pending consent, so the branch is inert until that lands —
  tested here by driving ``run()`` with fabricated Bash payloads.

  **First-sight seeds silently.** When no state file exists the hook records
  the current mtimes and returns without linting. A write that happened before
  the hook first looked has no baseline to call "moved" — linting on first
  sight would fire once for every fresh target on its very first Bash event,
  which is noise, not signal. (If a reason to lint-on-first-sight is later
  measured, say so and justify it here.)

Contract (stdlib only):
  - reads one JSON event on stdin, emits exactly one JSON object on stdout
  - ALWAYS exits 0 — a failure here must never block the tool call
  - bounded runtime (< 5s; the mtime check is O(1); the lint subprocess keeps
    its existing timeout, default 4s, overridable via DREAMWORK_LINT_TIMEOUT)
  - lint.py resolution: $DREAMWORK_LINT, else <dreamwork-core>/lint.py
    relative to this script (plugins/ud-dreamwork-hooks/hooks/ -> core)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hookutil  # noqa: E402

HOOK = "ledger-lint"
LEDGER_NAMES = {"questions.md", "tasks.md"}
# The Bash route's mtime memo. Distinct from .status-keys (lint.py owns that);
# this one is loop-written/tool-parsed. Shape flagged for file-formats.md:
#   {"<absolute path to questions.md or tasks.md>": <int mtime_ns>, ...}
STATE_FILENAME = ".ledger-lint-mtimes.json"
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


def _read_mtimes(dw: Path) -> dict:
    """Current mtime_ns of each ledger file that exists. A missing ledger
    file is not an error — a target may carry only one."""
    out = {}
    for name in LEDGER_NAMES:
        p = dw / name
        try:
            out[str(p)] = p.stat().st_mtime_ns
        except OSError:
            continue
    return out


def _load_state(state_path: Path) -> dict:
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_state(state_path: Path, mtimes: dict) -> None:
    """Best-effort persist. Never raises — a state write failure must not
    block the tool call."""
    try:
        state_path.write_text(
            json.dumps(mtimes, separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )
    except OSError:
        pass


def _run_lint(target: Path) -> dict:
    """The shared lint subprocess + verdict, used by both routes."""
    base = {"hook": HOOK, "plugin": hookutil.PLUGIN_ID}
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


def _bash_route(payload: dict, base: dict) -> dict:
    """The #387 Bash/mtime route. Resolve target from cwd; lint only when a
    ledger mtime moved past the stored state; seed silently on first sight."""
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return {**base, "ok": True, "skipped": True,
                "reason": "Bash event with no cwd — cannot resolve the ledger"}
    target = Path(cwd).resolve()
    if not (target / ".dreamwork").is_dir():
        return {**base, "ok": True, "skipped": True,
                "reason": f"cwd is not a dreamwork target: {target}"}
    if not hookutil.dreamwork_loads_plugin(target):
        return {**base, "ok": True, "skipped": True,
                "reason": "plugin not loaded in DREAMWORK.md"}

    dw = target / ".dreamwork"
    state_path = dw / STATE_FILENAME
    current = _read_mtimes(dw)
    stored = _load_state(state_path)

    if not state_path.exists():
        # First sight: seed silently, do not lint. A write that happened
        # before the hook first looked is not this hook's window.
        _write_state(state_path, current)
        return {**base, "ok": True, "skipped": True,
                "reason": "first sight — seeded ledger mtimes without linting"}

    # Moved iff any ledger file now on disk differs from its stored mtime,
    # INCLUDING one that appeared after seeding (absent in `stored` → its
    # .get is None, which != an int mtime, so it counts as moved). A ledger
    # file springing into existence is a structural change worth one lint,
    # and the state must learn of it now so it is watched from here on.
    moved = any(stored.get(name) != current[name]
                for name in current)
    if not moved:
        return {**base, "ok": True, "skipped": True,
                "reason": "no ledger mtime moved since last check"}
    _write_state(state_path, current)
    return _run_lint(target)


def run() -> dict:
    payload = hookutil.read_payload()
    base = {"hook": HOOK, "plugin": hookutil.PLUGIN_ID}
    tool_input = payload.get("tool_input")
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not file_path:
        # Bash (or any tool whose event carries no file_path): #387 route.
        return _bash_route(payload, base)
    path = Path(file_path)
    if path.name not in LEDGER_NAMES or path.parent.name != ".dreamwork":
        return {**base, "ok": True, "skipped": True,
                "reason": "not a dreamwork ledger file"}
    target = path.parent.parent
    if not hookutil.dreamwork_loads_plugin(target):
        return {**base, "ok": True, "skipped": True,
                "reason": "plugin not loaded in DREAMWORK.md"}
    return _run_lint(target)


def main() -> int:
    try:
        hookutil.emit(run())
    except Exception as error:  # fail-safe: report, never raise
        hookutil.emit({"ok": False, "hook": HOOK,
                       "error": f"{type(error).__name__}: {error}"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
