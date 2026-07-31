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

from dreamwork_db import Access, open_database
from dreamwork_db.tasks import task_store_spec

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


def origin_marks(entry_text: str) -> list[str]:
    """The origin markers that count — head-authoritative (#696).

    The head line carries the origin claim (synthesized for filed entries by
    `store_entries`, in the ` · `-chain for imported ones). Body prose that
    QUOTES `origin: **x**` is not a claim, so it must not count once the
    `ledger_view` projection makes body continuation lines visible (#696):
    the head line is read first, and only when it holds no COMPLETE marker —
    the #288/#252 hard-wrap, where `origin:` ends the head and `**value**`
    opens the indented continuation — does the full entry text supply them.
    """
    head = entry_text.split("\n", 1)[0]
    marks = [v.strip() for v in ORIGIN_MARK.findall(head)]
    if marks:
        return marks
    return [v.strip() for v in ORIGIN_MARK.findall(entry_text)]


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
    marks = origin_marks(entry_text)
    if len(marks) == 1 and marks[0] in KNOWN_ORIGINS:
        return marks[0]
    return "unknown"


def entry_origins(text: str) -> list[tuple[list[int], str]]:
    """(ids, origin) per entry in one ledger snapshot, fail-closed (#216)."""
    return [(ids, classify_origin(body)) for ids, body in ledger_entries(text)]


def open_section_text(text: str) -> str | None:
    """The `## Open` section's body, or None when the ledger has none.

    The slice runs from the `## Open` heading line to the next column-0 `## `
    heading (or end of file). This is the linter's idiom (#323) for checks
    that govern open entries only — NOT watch's `parse_ledger` split, which
    divides at `## Recently landed` specifically and reads landed ids too.
    Both live because they answer different questions; what must not live
    twice is this slice, which lint.py once wrote out in two checks.
    """
    lines = text.splitlines()
    start = end = None
    for n, ln in enumerate(lines):
        if ln.startswith("## "):
            if ln.rstrip() == "## Open":
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


def _task_read(db: Path, method: str, default, *args):
    """Call one repository read while preserving the facade's soft failure."""
    if not db.exists():
        return default
    try:
        with open_database(task_store_spec(db), access=Access.READ) as database:
            return getattr(database.tasks, method)(*args)
    except sqlite3.Error:
        return default


def _read_meta_value(db: Path, key: str) -> str | None:
    """One meta value from the store, or None when absent / unreadable."""
    return _task_read(db, "meta_value", None, key)


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
    the store is one row per permanent id). A row whose body opens with a
    ``- **#N`` head (the #294 import stored bodies verbatim, head line
    included) is returned verbatim. A row whose body has NO head -- every
    entry filed via ``dev/ledger.py file`` after cutover, whose stored body
    is the note text alone -- has a head SYNTHESIZED from the store columns
    and prepended, so the projection reparses to the same id sets the store
    holds and every text-consuming check sees every entry (#557):

        - **#N** — <title> · <priority> · <type> · origin: **<origin>** ·

    A NULL ``priority`` / ``type`` is OMITTED (the head grammar tolerates
    absent fields -- pre-#216 heads are bare; inventing one would fabricate a
    field), and NULL ``origin`` becomes ``unknown``, the truthful value
    :func:`lint.check_task_origins` records (``origin`` is constrained at the
    schema to ``human`` / ``loop`` / ``unknown``). Only the PROJECTION
    changes -- the stored body and its ``body_digest`` are never touched, so
    every consumer that reads the body column directly (the replay checks,
    the digest verifiers) is unaffected.
    """
    return _task_read(store_path(dreamwork_dir), "entries", [])


def store_records(dreamwork_dir) -> list[dict]:
    """One dict per task row from the store -- the full-record read (#497).

    GENUINE GAP (#497): :func:`store_entries` returns only ``(id, body)``;
    the read-only task CLI's ``list``/``get`` verbs need the structured
    columns (title, state, priority, type, origin). This is the ONE store
    reader for full rows, read-only via the ``?mode=ro`` idiom (parity with
    :func:`store_entries` / :func:`store_ids_by_state` -- a second store
    reader in a consumer is the defect #352 exists to prevent). Markdown-mode
    (no store) returns ``[]``. Rows are ascending by id.

    The dict KEYS are the read verbs' stable output contract -- a future
    binary rewrite of the CLI must reproduce them: ``id`` (int), ``state``
    (``"open"|"landed"``), ``title`` (str), ``body`` (str), ``priority``
    (str|None), ``type`` (str|None), ``origin`` (str|None), ``blocked_on``
    (str|None).
    """
    return _task_read(store_path(dreamwork_dir), "records", [])


def store_ids_by_state(dreamwork_dir) -> tuple[list[str], list[str]]:
    """``(open_ids, landed_ids)`` from the store -- the post-cutover
    projection of ``watch.parse_ledger``.

    Returns strings to match ``parse_ledger``'s contract (callers normalise
    to int at the seam, as the existing consumers do).
    """
    return _task_read(store_path(dreamwork_dir), "ids_by_state", ([], []))


def store_review_decisions(dreamwork_dir) -> list[dict]:
    """One dict per ``review_decision`` row -- the full review read (#497).

    GENUINE GAP (#497): ``watch._review_decisions`` is a PRIVATE dashboard
    helper that returns ``{artifact: (decision, question_title)}``, dropping
    ``decided_at`` and ``actor``. The read-only CLI's ``reviews`` verbs need
    the full row, so this is the ONE public store reader for review
    decisions -- read-only via the ``?mode=ro`` idiom, the same pattern every
    store read in this module uses. A missing store or a pre-v2 store whose
    table is absent returns ``[]`` (no review data), never raises. Rows are
    ascending by ``(decided_at, artifact)`` (deterministic; the verb that
    wants newest-first reverses).

    The dict KEYS are the read verbs' stable output contract: ``artifact``,
    ``question_title``, ``decision``, ``decided_at``, ``actor``.
    """
    return _task_read(store_path(dreamwork_dir), "review_decisions", [])


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
    return _task_read(store_path(dreamwork_dir), "series_raw", None)
