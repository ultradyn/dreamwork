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
