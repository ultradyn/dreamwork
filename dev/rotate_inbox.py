#!/usr/bin/env python3
"""rotate_inbox — archive older entries from .dreamwork/inbox.md (#1104).

Lanes die appending to inbox.md because the harness requires a Read before an
Edit, and the file grew to 3.77 MB / ~938K tokens. This tool moves older
entries to a dated archive so the live file stays small enough that a lane
can append its report without loading the whole history.

No code reads the contents of inbox.md (verified: lint.py, dev/brief.py,
dev/launch_lane.py, dev/dispatch_lane.py all treat it as a path string only;
file-formats.md:1063 states "append-only prose read by a language model").
So moving bytes to a sibling archive breaks no parser. The one real reader —
the coordinator LLM — reads via shell (tail/grep), and a pointer comment at
the top of the live file names the archive so older entries stay findable.

Usage:
    python3 dev/rotate_inbox.py status  --target <dreamwork-dir-or-repo>
    python3 dev/rotate_inbox.py rotate  --target <dreamwork-dir-or-repo> [--keep N]

Exit codes: 0 success (including "nothing to do"), 1 argument/path error,
2 I/O error.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

HEADING_RE = re.compile(r"^## ", re.MULTILINE)
DEFAULT_KEEP = 50
ARCHIVE_DIR = "inbox-archive"


def _inbox_path(target: Path) -> Path:
    """Resolve the inbox path from a target that may be a repo root or .dreamwork."""
    target = target.resolve()
    if target.name == ".dreamwork":
        return target / "inbox.md"
    return target / ".dreamwork" / "inbox.md"


def _split_entries(text: str) -> tuple[str, list[str]]:
    """Split inbox text into (prologue, entries).

    The prologue is everything before the first ``## `` heading (old single-line
    /tmp-pointer era). Entries are the text from each ``## `` heading up to the
    next one (or EOF), each including its heading line and trailing newlines.
    """
    match = HEADING_RE.search(text)
    if not match:
        return text, []
    prologue = text[: match.start()]
    rest = text[match.start() :]
    # Split on heading starts, keeping the heading line with its body.
    parts = re.split(r"(?=^## )", rest, flags=re.MULTILINE)
    entries = [p for p in parts if p.startswith("## ")]
    return prologue, entries


def _archive_path(dw: Path) -> Path:
    return dw / ARCHIVE_DIR / f"{date.today().strftime('%Y-%m')}.md"


def _pointer_line(archive_rel: str, n_moved: int) -> str:
    return (
        f"<!-- inbox-archive: {archive_rel} — {n_moved} older entries rotated; "
        f"grep there for history (#1104) -->\n"
    )


def rotate(dw: Path, keep: int = DEFAULT_KEEP) -> dict:
    """Rotate older entries from inbox.md to a dated archive.

    Returns a dict with keys: action ('rotated'|'noop'), entries_total,
    entries_kept, entries_moved, bytes_before, bytes_after, archive_path.
    Never deletes data: every moved byte goes to the archive. The live file
    is written atomically (temp + fsync + os.replace).
    """
    inbox = dw / "inbox.md"
    if not inbox.is_file():
        return {"action": "noop", "reason": "inbox.md absent"}
    text = inbox.read_text(encoding="utf-8", errors="replace")
    prologue, entries = _split_entries(text)
    if len(entries) <= keep:
        return {
            "action": "noop",
            "reason": f"{len(entries)} entries <= keep={keep}",
            "entries_total": len(entries),
        }

    split_at = len(entries) - keep
    to_archive = entries[:split_at]
    to_keep = entries[split_at:]

    # The prologue (pre-heading era) goes to the archive too — it is old.
    archive_text = prologue + "".join(to_archive)
    if not archive_text.endswith("\n"):
        archive_text += "\n"

    archive = _archive_path(dw)
    archive.parent.mkdir(parents=True, exist_ok=True)
    # Append to the archive if it already exists (multiple rotations same month).
    if archive.exists():
        existing = archive.read_text(encoding="utf-8", errors="replace")
        if not existing.endswith("\n"):
            existing += "\n"
        archive.write_text(existing + "\n" + archive_text, encoding="utf-8")
    else:
        archive.write_text(archive_text, encoding="utf-8")

    archive_rel = f"{ARCHIVE_DIR}/{archive.name}"
    pointer = _pointer_line(archive_rel, len(to_archive))
    live_text = pointer + "".join(to_keep)

    # Atomic write of the live file.
    inbox.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(inbox.parent), prefix=".inbox.md.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(live_text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(inbox))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    return {
        "action": "rotated",
        "entries_total": len(entries),
        "entries_kept": len(to_keep),
        "entries_moved": len(to_archive),
        "bytes_before": len(text.encode("utf-8")),
        "bytes_after": len(live_text.encode("utf-8")),
        "archive_path": str(archive),
    }


def status(dw: Path) -> dict:
    """Report inbox.md size and entry count without modifying anything."""
    inbox = dw / "inbox.md"
    if not inbox.is_file():
        return {"exists": False}
    text = inbox.read_text(encoding="utf-8", errors="replace")
    _, entries = _split_entries(text)
    return {
        "exists": True,
        "bytes": len(text.encode("utf-8")),
        "entries": len(entries),
        "path": str(inbox),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "verb", choices=["status", "rotate"], help="status: report; rotate: archive"
    )
    parser.add_argument(
        "--target",
        type=Path,
        required=True,
        help="repo root or .dreamwork directory",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=DEFAULT_KEEP,
        help=f"entries to keep in the live file (default {DEFAULT_KEEP})",
    )
    args = parser.parse_args(argv)

    inbox = _inbox_path(args.target)
    dw = inbox.parent

    if args.verb == "status":
        info = status(dw)
        if not info.get("exists"):
            print(f"inbox.md absent at {dw}")
            return 0
        print(
            f"inbox.md: {info['bytes']} bytes ({info['bytes'] // 1024}KB), "
            f"{info['entries']} entries — {info['path']}"
        )
        return 0

    if args.verb == "rotate":
        result = rotate(dw, keep=args.keep)
        if result.get("action") == "noop":
            print(f"noop: {result.get('reason', 'nothing to do')}")
            return 0
        print(
            f"rotated: {result['entries_moved']} entries -> "
            f"{result['archive_path']}; live file {result['entries_kept']} entries, "
            f"{result['bytes_before']} -> {result['bytes_after']} bytes"
        )
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
