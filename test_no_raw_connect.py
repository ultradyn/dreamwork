"""No-production-raw-connect guard (#645 increment 5).

The standing rule (#645): every SQLite connection in production code goes
through ``dreamwork_db.core``'s one configured door.  Raw ``sqlite3.connect``
calls bypass its connection policy — WAL, ``synchronous=FULL``,
``busy_timeout``, ``foreign_keys=ON``, read-only ``query_only`` — so a
production source that opens its own connection is a second, uninstrumented
way to touch a store, which is exactly what the design's G1 ("one supported
connection … API") forbids.

This guard scans production Python sources for the ``sqlite3.connect(``
spelling and fails if any appears outside the sanctioned door
(``dreamwork_db/core.py``).  Tests are excluded because they deliberately open
raw connections to corrupt and tamper with fixtures — that is their purpose,
not a policy violation.

What this guard CAN decide
--------------------------
A production source file contains a literal ``sqlite3.connect(`` call site
outside the one door.  That is a structural fact about the source, and it is
the spelling every remaining site in this migration used.

What this guard CANNOT decide
-----------------------------
It sees a **spelling, not a behaviour** (#651).  An aliased connection
(``_c = sqlite3.connect; _c(...)``) or a dynamically-constructed one
(``getattr(sqlite3, "connect")(...)``) evades the lexical scan while opening
the same raw connection.  A ``PRAGMA`` check at runtime would catch some of
those, but that is a different guard with a different cost; this one is the
source-structure backstop, and it does not claim more than a lexical scan
proves.  The guard's name says "raw connect" — a reader must not infer from
that name that it detects every route to a raw connection.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent

# The one sanctioned door.  All other production sources must route through it.
SANCTIONED_DOOR = "dreamwork_db/core.py"

# Files / directories that are NOT production for this guard's purposes.
_EXCLUDE_DIR_PARTS = {"node_modules", "__pycache__", ".dreamwork"}
_SHEBANG_PY = re.compile(rb"^#!.*python", re.MULTILINE)
_RAW_CONNECT = re.compile(r"sqlite3\s*\.\s*connect\s*\(")


def _is_python_source(path: Path) -> bool:
    """A tracked file is Python if it has a .py suffix or a python shebang."""
    if path.suffix == ".py":
        return True
    try:
        with path.open("rb") as fh:
            first = fh.readline()
    except OSError:
        return False
    return bool(_SHEBANG_PY.match(first))


def _is_test(path: Path) -> bool:
    """Test files, conftests, and files inside a tests/ directory."""
    name = path.name
    if name.startswith("test_") or name == "conftest.py":
        return True
    return any(part == "tests" for part in path.parts)


def _production_python_sources() -> list[Path]:
    """Every tracked Python source that is neither a test nor in an excluded dir."""
    import subprocess

    result = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    )
    sources: list[Path] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        rel = Path(line)
        if any(part in _EXCLUDE_DIR_PARTS for part in rel.parts):
            continue
        if _is_test(rel):
            continue
        full = REPO / rel
        if full.is_file() and _is_python_source(full):
            sources.append(rel)
    return sorted(sources)


def _raw_connect_sites(rel: Path) -> list[tuple[int, str]]:
    """The (1-based line number, stripped line) of each sqlite3.connect( call."""
    full = REPO / rel
    hits: list[tuple[int, str]] = []
    try:
        text = full.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return hits
    for idx, line in enumerate(text.splitlines(), start=1):
        if _RAW_CONNECT.search(line):
            hits.append((idx, line.strip()))
    return hits


def test_no_raw_sqlite_connect_in_production_sources() -> None:
    """No production source outside dreamwork_db/core.py may call sqlite3.connect.

    This is #645's standing rule, made enforceable by increment 5.  A failure
    names every offending file:line and the matched source, so the diagnosis
    starts at the call site rather than at a count.
    """
    # repo-wide-guard: scans EVERY production source for a raw sqlite3.connect
    # outside the one sanctioned door. Population: all tracked production Python.
    sources = _production_python_sources()

    # Precondition the guard depends on: the sanctioned door exists and itself
    # holds the connect calls.  If the door disappeared, "no other file" would
    # be vacuously meaningful; this assertion refuses that hollow pass.
    door_rel = Path(SANCTIONED_DOOR)
    assert door_rel in sources, (
        f"sanctioned door {SANCTIONED_DOOR} not found among {len(sources)} "
        "production sources — the guard cannot run without its door"
    )
    door_sites = _raw_connect_sites(door_rel)
    assert door_sites, (
        f"{SANCTIONED_DOOR} contains no sqlite3.connect( call — the door it "
        "is supposed to provide is absent, so the guard proves nothing"
    )

    offenders: list[str] = []
    for rel in sources:
        if rel == door_rel:
            continue
        for lineno, line in _raw_connect_sites(rel):
            offenders.append(f"{rel}:{lineno}: {line}")

    assert not offenders, (
        "production sources contain raw sqlite3.connect( calls outside the "
        f"sanctioned door ({SANCTIONED_DOOR}); route them through "
        "dreamwork_db.core instead:\n  " + "\n  ".join(offenders)
    )
