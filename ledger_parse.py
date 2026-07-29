#!/usr/bin/env python3
"""ledger_parse.py — the ONE copy of the ledger's entry/origin grammar (#352).

`.dreamwork/tasks.md` is read by `lint.py`, `watch.py`, and
`task_origins.py`, and until #352 each held its own copy of what counts as
an entry (`- **#N**`), what counts as an id inside a combined head
(`- **#7/#8**`), and what counts as an origin claim (`origin: **human**`).
The copies were pinned identical by tests — and a test that two copies
agree is a test that should not need to exist. The linter already learned
the underlying lesson the hard way (3073055): a second copy of one rule is
how a check drifts from the parser it checks.

The seam matters more than the tidiness: #346's read surface and #294's
ledger-store cutover both re-point "the reader", and that phrase is only
meaningful once there is one. This module is it. Everything here is a leaf
— it imports nothing from the repo, so any of the three readers (and the
deployed watch.py snapshot) can import it without a cycle.

NOT here, deliberately: `parse_ledger` (the open/landed id sets) lives in
`watch.py` still — it was never duplicated, and its landed reader is bound
up with watch's `IDS_ONLY_SPAN` core that `lint.LEDGER_ID` and
`status_sync.LEDGER_HEAD` already import from watch. This module is the
entry/origin grammar only; the format itself is governed by
`file-formats.md`, which this change does not touch.
"""

import re
import sqlite3
from pathlib import Path

# An entry opens with a leading bold token (`- **#…**`); only that token
# numbers it. A `#N` deeper in the body is a cross-reference, never the
# entry's number.
ENTRY_HEAD = re.compile(r"^- \*\*([^*]+?)\*\*")
ENTRY_ID = re.compile(r"#(\d+)")
# An origin claim is `origin: **value**`; the entry's lines are joined
# before matching, so a hard-wrapped marker (`origin:` ending a line, the
# value opening the next — #288 and #252 both do this) still reads.
ORIGIN_MARK = re.compile(r"origin:\s*\*\*\s*([^*]+?)\s*\*\*")
# `human` and `loop` are claims about who filed the task; everything else —
# no marker, several, an out-of-vocabulary value — fails closed to unknown.
KNOWN_ORIGINS = ("human", "loop")


def ledger_entries(text: str) -> list[tuple[list[int], str]]:
    """Each ledger entry as (its ids, its full text).

    An entry is a list item opening `- **#…**`; its text is that line plus
    the following blank or indented lines. A line at column 0 that does not
    open an entry ENDS it — the prose summaries under Recently landed are
    not entries and never join one. Only the leading bold token numbers the
    entry: combined entries list every id (`- **#138/#156**`), while a
    `#264` in the body is a cross-reference, not the entry's number.
    """
    entries: list[tuple[list[int], list[str]]] = []
    cur: tuple[list[int], list[str]] | None = None
    for ln in text.split("\n"):
        m = ENTRY_HEAD.match(ln)
        if m:
            ids = [int(x) for x in ENTRY_ID.findall(m.group(1))]
            cur = (ids, [ln])
            entries.append(cur)
        elif cur is not None and (not ln.strip() or ln[0] in " \t"):
            cur[1].append(ln)
        else:
            cur = None
    return [(ids, "\n".join(lines)) for ids, lines in entries]


def classify_origin(entry_text: str) -> str:
    """The origin claim of one entry, from that entry alone, fail-closed.

    Exactly one marker whose value is human or loop is a claim; anything
    else — none, several, an out-of-vocabulary value — is unknown, the
    truthful value rather than a guess (#216's rule). This one function is
    what watch's `entry_origins` and task_origins' `_classify` both meant;
    task_origins wraps it in a try/except because a malformed snapshot must
    fail closed there too.
    """
    marks = [v.strip() for v in ORIGIN_MARK.findall(entry_text)]
    if len(marks) == 1 and marks[0] in KNOWN_ORIGINS:
        return marks[0]
    return "unknown"


def entry_origins(text: str) -> list[tuple[list[int], str]]:
    """(ids, origin) per entry in one ledger snapshot, fail-closed (#216)."""
    return [(ids, classify_origin(body)) for ids, body in ledger_entries(text)]


def open_section_text(text: str) -> str | None:
    """The `## Open` section's body, or None when the ledger has none.

    The slice runs from the `## Open` heading line to the next `## `
    heading (or end of file). This is the linter's idiom (#323) for checks
    that govern open entries only — NOT watch's `parse_ledger` split, which
    divides at `## Recently landed` specifically and reads landed ids too.
    Both live because they answer different questions; what must not live
    twice is this slice, which lint.py once wrote out in two checks.
    """
    lines = text.splitlines()
    start = end = None
    for n, ln in enumerate(lines):
        if ln.strip().startswith("## "):
            if ln.strip() == "## Open":
                start = n + 1
            elif start is not None:
                end = n
                break
    if start is None:
        return None
    return "\n".join(lines[start:end])


# ---------------------------------------------------------------------------
# Post-cutover store read path (#294 cutover / R4).
#
# The store becomes the single source when its cutover watermark is present.
# ledger_parse is the ONE read module for both Markdown and store, so the
# flip dispatches here. These functions use raw sqlite3 (stdlib) — ledger_parse
# stays a leaf module (no repo imports), so watch.py's deployed snapshot and
# every consumer can import it without a cycle.
#
# The watermark is a ONE-WAY flip: present -> store is the source; absent ->
# Markdown. Never dual-write, never two truths (design M2 — the shadow-run
# rival is the second derived truth #264 exists to remove).
# ---------------------------------------------------------------------------

# Co-residence with #263's journal is planned but not yet landed; until then
# the store is a sibling of user-events.sqlite3 (design inc-1 notes).
STORE_FILENAME = "ledger.sqlite3"
_WATERMARK_KEY = "ledger_cut_over"


def store_path(dreamwork_dir) -> Path:
    """The ledger store path for a ``.dreamwork/``-like directory."""
    return Path(dreamwork_dir) / STORE_FILENAME


def _read_meta_value(db: Path, key: str) -> str | None:
    """One meta value from the store, or None when absent / unreadable."""
    if not db.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def cutover_watermark(dreamwork_dir) -> str | None:
    """The store's cutover watermark, or None when not yet cut over.

    Watermark present -> the store is the source of truth. This is the key
    the reader flip checks; it is written exactly once, at cutover, and
    never removed (rollback re-runs forward, keeping the store as source).
    """
    return _read_meta_value(store_path(dreamwork_dir), _WATERMARK_KEY)


def is_cut_over(dreamwork_dir) -> bool:
    """True iff the store's cutover watermark is present (store is source)."""
    return cutover_watermark(dreamwork_dir) is not None


def source_of_truth(dreamwork_dir) -> str:
    """``'store'`` when the cutover watermark is present, else ``'markdown'``.

    The single dispatch point a flipped consumer calls: it answers "where do
    I read the ledger?" in one word, and the answer is authoritative because
    the watermark is a one-way, never-removed flip.
    """
    return "store" if is_cut_over(dreamwork_dir) else "markdown"


def store_entries(dreamwork_dir) -> list[tuple[list[int], str]]:
    """``(ids, body)`` per task row from the store -- the post-cutover
    projection of :func:`ledger_entries`.

    Same return shape, so a consumer flipped to the store drops in
    unchanged. Each row is one id (combined entries were split at #353, so
    the store is one row per permanent id); the body is the verbatim text
    the import stored.
    """
    db = store_path(dreamwork_dir)
    if not db.exists():
        return []
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT id, body FROM task ORDER BY id"
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    return [([int(r[0])], r[1]) for r in rows]


def store_ids_by_state(dreamwork_dir) -> tuple[list[str], list[str]]:
    """``(open_ids, landed_ids)`` from the store -- the post-cutover
    projection of ``watch.parse_ledger``.

    Returns strings to match ``parse_ledger``'s contract (callers normalise
    to int at the seam, as the existing consumers do).
    """
    db = store_path(dreamwork_dir)
    if not db.exists():
        return [], []
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        open_ids = [str(r[0]) for r in conn.execute(
            "SELECT id FROM task WHERE state = 'open' ORDER BY id")]
        landed_ids = [str(r[0]) for r in conn.execute(
            "SELECT id FROM task WHERE state = 'landed' ORDER BY id")]
    except sqlite3.Error:
        return [], []
    finally:
        conn.close()
    return open_ids, landed_ids


def store_series_raw(dreamwork_dir) -> dict | None:
    """The first-sight model from the store's ``task_event`` table.

    The post-cutover projection of ``watch.ledger_series``'s git-walk: the
    synthetic ``migration:git`` rows carry exactly the first-sight arrival
    and landing shape the burndown needs (R3 / design M3-A). Returns a dict
    a consumer feeds into the same bucket builder the markdown walk uses:

    - ``arrived``: ``{str(id): epoch}`` — first arrival (``to_state='open'``).
    - ``landed``: ``{str(id): epoch}`` — first landing (``to_state='landed'``).
    - ``first_sight``: ``{str(id): origin}`` — origin at first sight, from
      the ``task`` table's ``origin`` column (the import parsed it once).
    - ``latest_open``: ``set[str]`` — ids whose ``task.state`` is ``'open'``.
    - ``commit_times``: ``[epoch]`` sorted — distinct event timestamps, the
      store-side analog of the ledger-touching git commits the markdown walk
      counts per bucket.

    Returns ``None`` when the store is absent or unreadable, so a missing
    store never breaks a reader (fail-closed toward markdown, same as
    :func:`source_of_truth`).
    """
    db = store_path(dreamwork_dir)
    if not db.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        arrived_rows = conn.execute(
            "SELECT task_id, MIN(at) FROM task_event "
            "WHERE from_state IS NULL AND to_state = 'open' "
            "GROUP BY task_id").fetchall()
        landed_rows = conn.execute(
            "SELECT task_id, MIN(at) FROM task_event "
            "WHERE to_state = 'landed' "
            "GROUP BY task_id").fetchall()
        task_rows = conn.execute(
            "SELECT id, state, origin FROM task").fetchall()
        time_rows = conn.execute(
            "SELECT DISTINCT at FROM task_event ORDER BY at").fetchall()
    except sqlite3.Error:
        return None
    finally:
        conn.close()

    def _epoch(iso_at):
        """Parse an event ``at`` ISO-8601 string to an int epoch."""
        try:
            from datetime import datetime
            return int(datetime.fromisoformat(iso_at).timestamp())
        except (ValueError, TypeError, OSError):
            return None

    arrived = {}
    for tid, at in arrived_rows:
        e = _epoch(at)
        if e is not None:
            arrived[str(tid)] = e
    landed = {}
    for tid, at in landed_rows:
        e = _epoch(at)
        if e is not None:
            landed[str(tid)] = e
    first_sight = {}
    latest_open = set()
    for tid, state, origin in task_rows:
        s = str(tid)
        first_sight[s] = origin if origin in KNOWN_ORIGINS else "unknown"
        if state == "open":
            latest_open.add(s)
    commit_times = sorted(
        e for e in (_epoch(r[0]) for r in time_rows) if e is not None)
    return {"arrived": arrived, "landed": landed,
            "first_sight": first_sight, "latest_open": latest_open,
            "commit_times": commit_times}
