#!/usr/bin/env python3
"""Wire ud-dreamwork-hooks into Claude Code settings — explicit, human-invoked.

This is the ONLY way the hooks reach ~/.claude/settings.json, and it never
runs itself: DREAMWORK.md's `Load: ud-dreamwork-hooks` records consent to
use the plugin; running `install.py --apply` is the recorded machine-config
act. Loading the plugin never auto-applies.

    python3 install.py --print            # show the exact snippet to paste
    python3 install.py --apply            # merge into ~/.claude/settings.json
    python3 install.py --apply --force    # replace a stale/conflicting entry

--apply is idempotent (a second run is a no-op), writes a timestamped backup
before touching an existing settings file, and refuses to overwrite an
existing-but-different entry for these hooks without --force.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent / "hooks"
PRECOMPACT = HOOKS_DIR / "precompact_focus.py"
LEDGER_LINT = HOOKS_DIR / "posttooluse_ledger_lint.py"
DEFAULT_SETTINGS = Path.home() / ".claude" / "settings.json"

EVENTS = ("PreCompact", "PostToolUse")


def desired_groups() -> dict[str, dict]:
    return {
        "PreCompact": {
            "matcher": "",
            "hooks": [{"type": "command", "command": f"python3 {PRECOMPACT}"}],
        },
        "PostToolUse": {
            "matcher": "Write|Edit",
            "hooks": [{"type": "command", "command": f"python3 {LEDGER_LINT}"}],
        },
    }


def snippet() -> dict:
    groups = desired_groups()
    return {"hooks": {event: [groups[event]] for event in EVENTS}}


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _commands(group: dict) -> list[str]:
    hooks = group.get("hooks")
    if not isinstance(hooks, list):
        return []
    return [h.get("command", "") for h in hooks if isinstance(h, dict)]


def _our_command(event: str) -> str:
    script = PRECOMPACT if event == "PreCompact" else LEDGER_LINT
    return str(script)


def merge(settings: dict, force: bool) -> tuple[dict, bool, list[str]]:
    """Return (merged, changed, conflicts). Pure — no IO."""
    groups = desired_groups()
    merged = json.loads(json.dumps(settings))  # deep copy via JSON
    hooks = merged.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        return settings, False, ["settings.json 'hooks' is not an object"]
    changed = False
    conflicts: list[str] = []
    for event in EVENTS:
        desired = groups[event]
        existing = hooks.setdefault(event, [])
        if not isinstance(existing, list):
            conflicts.append(f"hooks.{event} is not a list")
            continue
        identical = any(_canonical(g) == _canonical(desired)
                        for g in existing if isinstance(g, dict))
        if identical:
            continue
        ours = [g for g in existing
                if isinstance(g, dict) and any(_our_command(event) in c
                                               for c in _commands(g))]
        if ours and not force:
            conflicts.append(
                f"hooks.{event} already has a different ud-dreamwork-hooks "
                "entry; re-run with --force to replace it")
            continue
        if ours:
            hooks[event] = [g for g in existing if g not in ours]
        hooks[event].append(desired)
        changed = True
    return merged, changed, conflicts


def write_settings(settings_path: Path, text: str) -> int:
    """Write `text` to `settings_path` without breaking hardlinks to it (#369).

    `os.replace` is the right write for a file with one name and the WRONG
    write for a file with two: the rename rebinds *this* name to a new inode
    and leaves the other name on the old one. His two config dirs are one
    inode — `~/.claude/settings.json` and `~/.claude-w/settings.json` both
    `256518042` — and a session running with `CLAUDE_CONFIG_DIR=~/.claude-w`
    would have been handed hooks it could not see, while exit 0, a timestamped
    backup and an idempotent re-run all reported success. Silent, and the
    tempting fix (point `--settings` at the other name) only mirrors it.

    Refusing instead would be safe and useless: his real config IS linked, so
    a refusal makes `--apply` unusable on the only machine it is for. So above
    one link this writes IN PLACE, which trades atomicity for the link — the
    reason the caller's backup is not optional. `r+b` writes over the old
    bytes and then truncates, so there is no window where the file is empty,
    and the JSON is serialised before the file is opened at all.

    Returns the link count observed, so the caller can report the trade.
    """
    data = text.encode("utf-8")
    nlink = settings_path.stat().st_nlink if settings_path.exists() else 1
    if nlink > 1:
        with open(settings_path, "r+b") as fh:
            fh.write(data)
            fh.truncate()
            fh.flush()
            os.fsync(fh.fileno())
        return nlink
    tmp = settings_path.with_name(f"{settings_path.name}.tmp")
    tmp.write_bytes(data)
    tmp.replace(settings_path)
    return nlink


def apply(settings_path: Path, force: bool) -> tuple[int, dict]:
    base = {"settings": str(settings_path)}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            return 2, {**base, "ok": False,
                       "error": f"cannot parse {settings_path}: {error}"}
        if not isinstance(settings, dict):
            return 2, {**base, "ok": False,
                       "error": f"{settings_path} is not a JSON object"}
    else:
        settings = {}

    merged, changed, conflicts = merge(settings, force)
    if conflicts:
        return 2, {**base, "ok": False, "error": "; ".join(conflicts)}
    if not changed:
        return 0, {**base, "ok": True, "changed": False,
                   "note": "already installed; no-op"}

    backup = None
    if settings_path.exists():
        stamp = time.strftime("%Y%m%dT%H%M%S")
        backup = settings_path.with_name(f"{settings_path.name}.bak-{stamp}")
        backup.write_text(settings_path.read_text(encoding="utf-8"),
                          encoding="utf-8")
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    nlink = write_settings(settings_path, json.dumps(merged, indent=2) + "\n")

    # Read back what landed. This is the class of bug #369 belongs to — every
    # visible signal said success while the file the session reads was
    # untouched — so success is claimed from the file, not from the write
    # returning.
    try:
        landed = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return 2, {**base, "ok": False,
                   "error": f"wrote {settings_path} but cannot read it back: "
                            f"{error}",
                   "backup": str(backup) if backup else None}
    if landed != merged:
        return 2, {**base, "ok": False,
                   "error": f"{settings_path} does not contain what was written",
                   "backup": str(backup) if backup else None}

    # The link count is reported from AFTER the write, not from before it. The
    # pre-write number is a prediction and #369 is a bug about predictions
    # being believed: a report derived from the count we intended to preserve
    # would say `hardlinked: 2` in the exact run that split the inode.
    after = settings_path.stat().st_nlink
    if nlink > 1 and after != nlink:
        return 2, {**base, "ok": False,
                   "error": f"{settings_path} had {nlink} links and has {after} "
                            "after writing: the other name is on the old inode "
                            "and does not have these hooks",
                   "backup": str(backup) if backup else None}

    return 0, {**base, "ok": True, "changed": True,
               "backup": str(backup) if backup else None,
               "hardlinked": after if after > 1 else None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--print", action="store_true",
                      help="print the exact settings.json snippet (default)")
    mode.add_argument("--apply", action="store_true",
                      help="merge the snippet into the settings file")
    parser.add_argument("--settings", type=Path, default=DEFAULT_SETTINGS,
                        help=f"settings file (default: {DEFAULT_SETTINGS})")
    parser.add_argument("--force", action="store_true",
                        help="replace an existing different entry for these hooks")
    args = parser.parse_args(argv)

    if not args.apply:
        print(json.dumps(snippet(), indent=2))
        return 0
    code, summary = apply(args.settings, args.force)
    print(json.dumps(summary, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
