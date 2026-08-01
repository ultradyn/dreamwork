#!/usr/bin/env python3
"""#864 — the Claude Code STOP hook that delivers EXPEDITED receipts at a pause.

His ask: *"we should have a stop hook (installed locally to the repo level
.claude/ folder or similar) that calls a dreamwork cli command to drain an
eligible msg log from the event log feed."*  This is that hook, and it is
deliberately thin: **all of the journal logic lives in the CLI verb**
``dev/journal_consume.py expedite`` (#855 — the loop must stop hand-querying
the store, and a hook is exactly the place that temptation would land).  This
file parses the hook protocol, decides whether to run at all, and forwards the
verb's stdout.  It contains no SQL and opens no database.

WHY IT CANNOT DAMAGE THE TICK.  The verb it calls is a READER: it never
advances the coordinator cursor and never writes the #658 read-coverage marker,
so a hook firing in the middle of the coordinator's ``pending``→``consume``
sequence changes nothing that sequence depends on.  See the verb's docstring
and ``delivery-modes.md`` §"How the hook and the tick share ONE cursor".

THREE THINGS STOP IT FIRING WHEN IT SHOULD NOT, and all three are cheap:
  * ``stop_hook_active`` in the hook's stdin JSON — Claude Code sets it while
    a stop hook's own continuation is running.  We exit silently, so the hook
    can never stack on itself.
  * the gate file ``.dreamwork/expedite`` — absent means off, which is the
    state every checkout is in until someone runs ``install``.
  * the exactly-once marker — a receipt already delivered proves APPLIED in
    the verb and is not re-emitted, so repeated pauses do not repeat the text.

INSTALLING IS DELIBERATE AND REVERSIBLE.  ``install`` writes the gate file and
merges one Stop entry into ``<target>/.claude/settings.json``; ``uninstall``
removes both; ``status`` says which state you are in.  Nothing is installed by
merely merging this branch — ``.claude/`` is gitignored, so the hook cannot
arrive by checkout.

USAGE
  python3 dev/expedite_hook.py run      [--target DIR] [--limit N]   # the hook
  python3 dev/expedite_hook.py install  [--target DIR] [--limit N]
  python3 dev/expedite_hook.py uninstall [--target DIR]
  python3 dev/expedite_hook.py status   [--target DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
VERB = HERE.parent / "journal_consume.py"

# The cap has ONE home, and it is the verb's — a second literal here would be a
# default that silently disagreed with the documented one the moment either
# moved.  Imported rather than restated, the same discipline EXPEDITE_KINDS is
# under.  (`dev/` has no `__init__.py`, so the root goes on the path first, the
# way `test_check_watch_citations.py` reaches `dev.check_watch_citations`.)
sys.path.insert(0, str(HERE.parent.parent))
from dev.journal_consume import EXPEDITE_LIMIT_DEFAULT as LIMIT_DEFAULT  # noqa: E402

# The gate file and its one legal value — `watch.expedite_enabled` reads the
# same two constants' worth of contract, and `file-formats.md` states it once.
GATE_REL = Path(".dreamwork") / "expedite"
GATE_ON = "on"

JOURNAL_REL = Path(".dreamwork") / "user-events.sqlite3"
APPLIED_REL = Path(".dreamwork") / "applied.md"
SETTINGS_REL = Path(".claude") / "settings.json"

EX_OK = 0
EX_USAGE = 64


def _target(args) -> Path:
    """The dreamwork target this hook serves.

    ``--target`` wins; otherwise ``$CLAUDE_PROJECT_DIR`` (which Claude Code
    exports for hooks, and which is the project the hook was registered in);
    otherwise the cwd.  Resolving it from the environment rather than from this
    file's location matters: the same checkout may be the TOOL for a target
    elsewhere, and it is the target's journal that must be drained.
    """
    return Path(args.target or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())


def _gate_on(target: Path) -> bool:
    """Is the gate file present and `on`? Anything else is OFF (fail to inert)."""
    gate = target / GATE_REL
    try:
        return gate.read_text(encoding="utf-8").strip() == GATE_ON
    except OSError:
        return False


def _hook_command(limit: int) -> str:
    """The exact command string registered in settings.json.

    Absolute, because a hook runs with the session's cwd, not this checkout's;
    it carries ``--limit`` so the installed cap is visible in the settings file
    the human reads rather than hidden in a default.
    """
    return f"{sys.executable} {VERB.parent / HERE.name} run --limit {limit}"


def _stop_entry(command: str) -> dict:
    return {"hooks": [{"type": "command", "command": command}]}


def _load_settings(path: Path) -> dict:
    """Existing settings, or {} — a malformed file is a refusal, not a clobber."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _our_entries(settings: dict) -> list[dict]:
    """Every Stop entry whose command names THIS file (any --limit)."""
    marker = str(VERB.parent / HERE.name)
    out = []
    for entry in settings.get("hooks", {}).get("Stop", []):
        for hook in entry.get("hooks", []):
            if marker in str(hook.get("command", "")):
                out.append(entry)
                break
    return out


def cmd_run(args, out, err) -> int:
    """The hook body: deliver expedited receipts, or say nothing at all.

    ALWAYS EXITS 0.  A stop hook that fails takes the human's session with it,
    and this feature is an accelerator over a drain that already works — so
    every failure path here degrades to "the tick will deliver it", which is
    the documented fallback rather than a loss.
    """
    raw = ""
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        pass
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    # Claude Code sets this while a stop hook's own continuation runs. Exiting
    # here is what makes stacking structurally impossible rather than merely
    # unlikely; the marker already prevents repeating a receipt, but a hook
    # that re-enters on its own output would still cost a turn each time.
    if payload.get("stop_hook_active"):
        return EX_OK
    target = _target(args)
    if not _gate_on(target):
        return EX_OK
    try:
        proc = subprocess.run(
            [sys.executable, str(VERB), "expedite",
             "--journal", str(target / JOURNAL_REL),
             "--applied", str(target / APPLIED_REL),
             "--limit", str(args.limit)],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as e:
        err.write(f"expedite-hook: verb did not run ({e}); the tick will drain\n")
        return EX_OK
    if proc.returncode != EX_OK:
        # Report on stderr (visible in the transcript) but never block the
        # stop: the receipts are still pending and the tick still drains them.
        err.write(f"expedite-hook: verb exited {proc.returncode}; "
                  f"the tick will drain\n{proc.stderr}")
        return EX_OK
    if not proc.stdout.strip():
        return EX_OK  # nothing expedited is waiting — stop silently
    out.write(json.dumps({"hookSpecificOutput": {
        "hookEventName": "Stop",
        "additionalContext": (
            "EXPEDITED delivery (#864) — these arrived while you were working "
            "and are still in the journal, so the tick's drain will list them "
            "too; acting on them now is correct and acting twice is not.\n\n"
            + proc.stdout),
    }}) + "\n")
    return EX_OK


def cmd_install(args, out, err) -> int:
    """Write the gate file and merge one Stop entry into .claude/settings.json.

    Merging, never clobbering: existing settings and existing Stop hooks are
    preserved, and a re-install replaces only the entry that names this file
    (so changing ``--limit`` does not accumulate duplicates).
    """
    target = _target(args)
    settings_path = target / SETTINGS_REL
    try:
        settings = _load_settings(settings_path)
    except (ValueError, OSError) as e:
        err.write(f"install: {settings_path} is unreadable/malformed ({e}) — "
                  f"refusing to overwrite it; fix or move it and re-run\n")
        return EX_USAGE
    hooks = settings.setdefault("hooks", {})
    stop = hooks.setdefault("Stop", [])
    ours = _our_entries(settings)
    for entry in ours:
        stop.remove(entry)
    stop.append(_stop_entry(_hook_command(args.limit)))
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    gate = target / GATE_REL
    gate.parent.mkdir(parents=True, exist_ok=True)
    gate.write_text(GATE_ON + "\n", encoding="utf-8")
    out.write(f"installed: {gate} = {GATE_ON}\n")
    out.write(f"installed: Stop hook in {settings_path} (cap {args.limit})\n")
    out.write("`do next` now waits for a pause instead of interrupting; the "
              "hook takes effect in sessions started after this.\n")
    return EX_OK


def cmd_uninstall(args, out, err) -> int:
    """Remove the Stop entry and the gate file — both, so they cannot diverge."""
    target = _target(args)
    settings_path = target / SETTINGS_REL
    removed = 0
    if settings_path.exists():
        try:
            settings = _load_settings(settings_path)
        except (ValueError, OSError) as e:
            err.write(f"uninstall: {settings_path} is unreadable ({e}); "
                      f"remove the Stop entry by hand\n")
            return EX_USAGE
        for entry in _our_entries(settings):
            settings["hooks"]["Stop"].remove(entry)
            removed += 1
        settings_path.write_text(json.dumps(settings, indent=2) + "\n",
                                 encoding="utf-8")
    gate = target / GATE_REL
    had_gate = gate.exists()
    if had_gate:
        gate.unlink()
    out.write(f"removed: {removed} Stop entr(ies); gate "
              f"{'deleted' if had_gate else 'was already absent'}\n")
    out.write("`do next` pre-empts again (today's behaviour).\n")
    return EX_OK


def cmd_status(args, out, err) -> int:
    """Say which of the four states this checkout is in, and never guess."""
    target = _target(args)
    settings_path = target / SETTINGS_REL
    try:
        registered = len(_our_entries(_load_settings(settings_path)))
    except (ValueError, OSError):
        registered = -1
    out.write(f"target: {target}\n")
    out.write(f"gate {target / GATE_REL}: "
              f"{'on' if _gate_on(target) else 'off (absent or not `on`)'}\n")
    out.write(f"stop hook in {settings_path}: "
              + ("unreadable settings" if registered < 0
                 else f"{registered} entr(ies)") + "\n")
    if _gate_on(target) and registered == 0:
        out.write("WARNING: the gate is on but no hook is registered — "
                  "`do next` no longer pre-empts and nothing delivers it at a "
                  "pause. Run `install`, or `uninstall` to restore pre-emption.\n")
    return EX_OK


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dev/expedite_hook.py",
        description="The Claude Code stop hook for the EXPEDITED class (#864).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, helptext in (
        ("run", "the hook body: read the hook JSON on stdin, deliver, exit 0"),
        ("install", "write the gate file and register the Stop hook"),
        ("uninstall", "remove the Stop hook and the gate file"),
        ("status", "report gate + registration state"),
    ):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("--target", default=None,
                        help="dreamwork target (default: $CLAUDE_PROJECT_DIR, else cwd)")
        if name in ("run", "install"):
            sp.add_argument("--limit", type=int, default=LIMIT_DEFAULT, metavar="N",
                            help="cap one pause's delivery (default: %(default)s)")
    return p


def main(argv=None, out=None, err=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if out is None:
        out = sys.stdout
    if err is None:
        err = sys.stderr
    try:
        args = _parser().parse_args(argv)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else EX_USAGE
        return EX_OK if code == 0 else EX_USAGE
    return {
        "run": cmd_run, "install": cmd_install,
        "uninstall": cmd_uninstall, "status": cmd_status,
    }[args.cmd](args, out, err)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
