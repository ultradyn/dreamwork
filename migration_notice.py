#!/usr/bin/env python3
"""Migration notices — a hot-path signal for agents that never re-initialize.

Migrations apply at orient (see ``migrations/README.md``). A long-running loop
that never re-inits holds its routine in context and never reads a new
migration entry. Its skill files are cold; its data files are hot. So a
migration that changes the *meaning* of a data file leaves a notice **in that
file**, and a stale agent discovers the upgrade by doing its normal work.

Contract: ``file-formats.md`` (``dreamwork-migration-notice``). Design: 
``.dreamwork/docs/plans/migration-notices.md`` (#458).

Only a migration writes these. They carry a declared marker. An agent treats
them as a protocol notice from its own repo — never as peer authority.

    python3 migration_notice.py write  --path FILE --migration NAME.md [--summary TEXT]
    python3 migration_notice.py retire --path FILE --skill-version NAME.md
    python3 migration_notice.py parse  --path FILE
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Declared open marker — same family as review_artifact.HEADER_OPEN
# (``<!--dreamwork-review-source``). Starts at a line beginning so a prose
# mention of the string cannot forge a notice.
NOTICE_OPEN = "<!--dreamwork-migration-notice"
NOTICE_CLOSE = "-->"

# One block: open line, key: value lines, close line. Values are single-line.
# The body never carries a freeform paragraph that could look like a ledger
# entry head (`- **#N**`), which both `watch.LEDGER_ENTRY` and `lint.LEDGER_ID`
# match with re.M against the whole file.
_BLOCK_RE = re.compile(
    r"(?m)^"
    + re.escape(NOTICE_OPEN)
    + r"[ \t]*\n"
    r"(.*?)"
    r"^"
    + re.escape(NOTICE_CLOSE)
    + r"[ \t]*\n?",
    re.DOTALL,
)

_FIELD_RE = re.compile(r"^([a-z][a-z0-9_-]*):\s*(.*?)\s*$")

# Required. `migration` names a real migrations/ entry (checked by the writer
# when --migrations-dir is given; always shape-checked).
REQUIRED = ("migration",)
OPTIONAL = ("file", "summary")
ALLOWED = set(REQUIRED) | set(OPTIONAL)

# Same shape migrations/README.md names: YYYY-MM-DD-NN-slug.md (pre-ordinal
# YYYY-MM-DD-slug.md still matches the looser alternative).
MIGRATION_NAME = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:-\d{2})?-[a-z0-9][a-z0-9-]*\.md$"
)

# A line that would be counted as a ledger entry by the production readers.
# Rejected in field values so a notice can never invent a phantom id.
_LEDGER_HEAD_LINE = re.compile(r"^- \*\*#\d+")


class NoticeError(ValueError):
    """Malformed notice or illegal field."""


def parse_notice_fields(body: str) -> dict[str, str]:
    """Parse the interior of a notice block into a field dict.

    Raises NoticeError on unknown keys, missing required keys, duplicate
    keys, or a value that would look like a ledger entry head.
    """
    fields: dict[str, str] = {}
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _FIELD_RE.match(line)
        if not m:
            raise NoticeError(f"notice line is not `key: value`: {raw!r}")
        key, value = m.group(1), m.group(2)
        if key not in ALLOWED:
            raise NoticeError(
                f"unknown notice field {key!r} — allowed: {sorted(ALLOWED)}"
            )
        if key in fields:
            raise NoticeError(f"duplicate notice field {key!r}")
        if _LEDGER_HEAD_LINE.match(value):
            raise NoticeError(
                f"notice field {key!r} must not look like a ledger entry head"
            )
        # Also reject a multi-line smuggle via embedded newlines (values are
        # single-line by the line-oriented parse, but be explicit).
        if "\n" in value or "\r" in value:
            raise NoticeError(f"notice field {key!r} must be a single line")
        fields[key] = value
    for req in REQUIRED:
        if req not in fields or not fields[req].strip():
            raise NoticeError(f"notice missing required field {req!r}")
    if not MIGRATION_NAME.match(fields["migration"]):
        raise NoticeError(
            f"migration name is not YYYY-MM-DD[-NN]-slug.md: {fields['migration']!r}"
        )
    return fields


def find_notice(text: str) -> re.Match[str] | None:
    """Return the first well-delimited notice block match, or None.

    A block that opens but never closes is not returned — callers that need
    to surface that use ``malformed_notice_span``.
    """
    return _BLOCK_RE.search(text)


def malformed_notice_span(text: str) -> tuple[int, int] | None:
    """If an open marker exists without a matching close, return its span."""
    idx = text.find(NOTICE_OPEN)
    if idx < 0:
        return None
    # Only flag when it sits at a line start (same rule as a real notice).
    if idx > 0 and text[idx - 1] not in "\n":
        return None
    if _BLOCK_RE.search(text, pos=idx) is not None:
        return None
    return (idx, idx + len(NOTICE_OPEN))


def parse_notice(text: str) -> dict[str, str] | None:
    """Return the fields of the first notice in *text*, or None if absent.

    Raises NoticeError if a block is present but its interior is malformed.
    """
    m = find_notice(text)
    if m is None:
        if malformed_notice_span(text) is not None:
            raise NoticeError("notice opens and never closes")
        return None
    return parse_notice_fields(m.group(1))


def render_notice(
    migration: str,
    *,
    file: str | None = None,
    summary: str | None = None,
) -> str:
    """Render one notice block (trailing newline included)."""
    fields = {"migration": migration}
    if file is not None:
        fields["file"] = file
    if summary is not None:
        fields["summary"] = summary
    # Round-trip through the parser so illegal values fail at the writer,
    # not later at a reader that trusted us.
    body = "".join(f"{k}: {v}\n" for k, v in fields.items())
    parse_notice_fields(body)
    return f"{NOTICE_OPEN}\n{body}{NOTICE_CLOSE}\n"


def strip_notice(text: str) -> str:
    """Remove every well-formed notice block. Leaves malformed openers alone."""
    return _BLOCK_RE.sub("", text)


def insert_notice(
    text: str,
    migration: str,
    *,
    file: str | None = None,
    summary: str | None = None,
) -> str:
    """Return *text* with exactly one notice at byte 0.

    Any existing well-formed notice is removed first (the shrink rule: the
    Nth migration leaves one banner, not N). The new notice is prepended.
    """
    cleaned = strip_notice(text)
    block = render_notice(migration, file=file, summary=summary)
    # Keep a blank line between the notice and the file body when the body
    # has content, so a human eye separates protocol chrome from prose.
    if cleaned and not cleaned.startswith("\n"):
        return block + "\n" + cleaned
    return block + cleaned


def remove_notice(text: str) -> str:
    """Alias of strip_notice — the retire writer's primitive."""
    return strip_notice(text)


def notice_is_spent(migration: str, skill_version: str) -> bool:
    """True when *skill_version* means the named migration has been applied.

    migrations/README.md: versions are migration filenames, ordered by plain
    lexicographic sort (the naming scheme makes that chronological). A
    target whose recorded version is >= the notice's migration has applied
    it (or something later), so the hot-path notice is spent.
    """
    if not skill_version or not migration:
        return False
    return skill_version >= migration


def retire_if_applied(text: str, skill_version: str) -> tuple[str, bool]:
    """Remove the notice when skill_version says it is spent.

    Returns ``(new_text, removed)``. Absent notice → ``(text, False)``.
    Malformed notice raises NoticeError (do not silently drop a broken
    banner; the agent must see it to fix or replace it).
    """
    fields = parse_notice(text)
    if fields is None:
        return text, False
    if notice_is_spent(fields["migration"], skill_version):
        return strip_notice(text), True
    return text, False


def write_path(
    path: Path,
    migration: str,
    *,
    file: str | None = None,
    summary: str | None = None,
) -> None:
    """Insert/replace the notice in *path* (creates the file if absent)."""
    raw = path.read_text() if path.exists() else ""
    path.write_text(
        insert_notice(raw, migration, file=file, summary=summary),
        encoding="utf-8",
    )


def retire_path(path: Path, skill_version: str) -> bool:
    """Retire the notice in *path* if spent. Returns whether it was removed."""
    if not path.exists():
        return False
    raw = path.read_text()
    new, removed = retire_if_applied(raw, skill_version)
    if removed:
        path.write_text(new, encoding="utf-8")
    return removed


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="migration_notice.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("write", help="insert or replace a notice at the top of a file")
    w.add_argument("--path", required=True, type=Path)
    w.add_argument("--migration", required=True, help="migrations/ filename")
    w.add_argument("--summary", default=None)
    w.add_argument(
        "--file",
        default=None,
        dest="file_field",
        help="optional `file:` field (defaults to --path's name)",
    )
    w.add_argument(
        "--migrations-dir",
        type=Path,
        default=None,
        help="when set, require --migration to exist there",
    )

    r = sub.add_parser("retire", help="remove the notice if skill-version has applied it")
    r.add_argument("--path", required=True, type=Path)
    r.add_argument(
        "--skill-version",
        default=None,
        help="the recorded migration filename (or use --skill-version-file)",
    )
    r.add_argument(
        "--skill-version-file",
        type=Path,
        default=None,
        help="read skill-version from this file (one line)",
    )

    s = sub.add_parser("parse", help="print the notice fields as key=value lines")
    s.add_argument("--path", required=True, type=Path)

    args = p.parse_args(argv)

    try:
        if args.cmd == "write":
            if args.migrations_dir is not None:
                cand = args.migrations_dir / args.migration
                if not cand.is_file():
                    print(
                        f"migration_notice: {args.migration} is not a file in "
                        f"{args.migrations_dir}",
                        file=sys.stderr,
                    )
                    return 2
            file_field = args.file_field
            if file_field is None:
                file_field = str(args.path)
            write_path(
                args.path,
                args.migration,
                file=file_field,
                summary=args.summary,
            )
            return 0

        if args.cmd == "retire":
            ver = args.skill_version
            if ver is None and args.skill_version_file is not None:
                ver = args.skill_version_file.read_text().strip()
            if not ver:
                print(
                    "migration_notice: retire needs --skill-version or "
                    "--skill-version-file",
                    file=sys.stderr,
                )
                return 2
            removed = retire_path(args.path, ver)
            print("removed" if removed else "kept")
            return 0

        if args.cmd == "parse":
            raw = args.path.read_text() if args.path.exists() else ""
            fields = parse_notice(raw)
            if fields is None:
                print("none")
                return 0
            for k, v in fields.items():
                print(f"{k}={v}")
            return 0

    except NoticeError as e:
        print(f"migration_notice: {e}", file=sys.stderr)
        return 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
