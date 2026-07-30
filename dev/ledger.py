#!/usr/bin/env python3
"""#440 — the one supported way to fold a ledger entry.

The coordinator hand-rolled a ledger split on every fold. The unanchored
form `t.split('## Recently landed', 1)` splits at the first MENTION of the
heading text, and `## Recently landed` appears in the PROSE of an open
entry — so twice on 2026-07-28 the fold wrote a file with two landed
headings (130 lines in the wrong half) and once counted 33 open entries
instead of 142. Five hand-rolled ledger parsers have now been wrong in
this repo, against a file whose production parser was importable every
time.

This module is the single supported path for those operations. It reuses
the production parser (`watch.parse_ledger` / `watch.ledger_entries`) for
what it already answers — the open/landed id sets, and the entry-head and
id grammar — and the production ANCHORED heading patterns
(`watch.LEDGER_SEC_OPEN` / `watch.LEDGER_SEC_LANDED`, both
`^[ \t]*## <name>[ \t]*$`) to locate the sections. It NEVER splits on a
bare heading string. The block-move itself is something the production
parser does not expose (it returns id sets, not byte spans), so that is
done here over lines — using the production head/id patterns, never a
sixth copy of either.

INVARIANTS — enforced before AND after the write
  - exactly one `## Open` heading LINE and one `## Recently landed` heading
    LINE, matched anchored, and Open precedes landed. The post-write
    assertion matters most: both 2026-07-28 incidents had the symptom
    appear far from the cause.
  - a file that fails those assertions is never written. Build the new
    text, assert, then write. A partial write is the failure mode that
    cost the recovery.

USAGE
  python3 dev/ledger.py counts [--ledger PATH]
  python3 dev/ledger.py fold <id> --note <text> [--ledger PATH] [--dry-run]
  python3 dev/ledger.py file <title> [--note <text>] [--priority P] [--type T] [--origin O] [--ledger PATH] [--dry-run]
  python3 dev/ledger.py note <id> --note <text> [--ledger PATH] [--dry-run]
  python3 dev/ledger.py sweep [--since REF] [--ledger PATH] [--repo PATH]
  python3 dev/ledger.py list [--state open|landed] [--sort id|id-desc] [--json] [--ledger PATH]
  python3 dev/ledger.py get <id> [--ledger PATH]
  python3 dev/ledger.py count [--state open|landed] [--json] [--ledger PATH]
  python3 dev/ledger.py reviews list|get <artifact> [--ledger PATH]

`counts` prints the open and landed id counts from `watch.parse_ledger`
with the expression that produced them — the same anchored read every
consumer (the dashboard, lint, the burndown) uses, so the count that was
33-against-142 can no longer come from a second, unanchored reader.
`fold` moves the entry from `## Open` to the TOP of `## Recently landed`,
appending `--note` as a `  · <text>` continuation line on the moved
block, and preserves the block byte-exact otherwise. Fold refuses on:
unknown id, id already in landed, id matching more than one open entry.
"""
import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

# `watch.py` lives at the repo root; this module lives in `dev/`. Add the
# root so `import watch` works when run as `python3 dev/ledger.py` from the
# root (in which case sys.path[0] is `dev/`, not the cwd).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import watch  # noqa: E402  — the production parser, reused not copied
from ledger_parse import ledger_entries, open_section_text  # noqa: E402
from ledger_parse import source_of_truth, store_ids_by_state  # noqa: E402
from ledger_parse import store_path  # noqa: E402
from ledger_parse import classify_origin, store_records  # noqa: E402  — #497 read verbs
from ledger_parse import store_review_decisions  # noqa: E402  — #497 reviews verbs
import lint  # noqa: E402 — NEXT_ID, the one header reader
import ledger_store  # noqa: E402 — open the store for write verbs (#294 inc 9)
import ledger_write  # noqa: E402 — file_task / land_task (#294 inc 9)
from user_events.sqlite import open_journal  # noqa: E402 — the journal read API (#357)

LEDGER_DEFAULT = ".dreamwork/tasks.md"
NOTE_PREFIX = "  · "  # two-space indent, U+00B7, space — the ledger's continuation idiom


class LedgerError(Exception):
    """A fold or count could not be performed safely."""


# ---------------------------------------------------------------------------
# anchored-heading invariant — the single thing this tool exists to protect
# ---------------------------------------------------------------------------

def assert_headings(text, when):
    """Exactly one anchored `## Open`, one anchored `## Recently landed`, Open first.

    `when` labels the check ("before fold", "after fold", …) so a failure
    names the moment, which is how the two 2026-07-28 incidents were traced.
    """
    n_open = len(watch.LEDGER_SEC_OPEN.findall(text))
    n_landed = len(watch.LEDGER_SEC_LANDED.findall(text))
    if n_open != 1 or n_landed != 1:
        raise LedgerError(
            f"heading invariant violated {when}: found {n_open} `## Open` "
            f"and {n_landed} `## Recently landed` heading line(s); need exactly "
            f"one each. A section heading is probably quoted inside an entry's "
            f"prose, which is the corruption this tool exists to prevent (#440)."
        )
    o = watch.LEDGER_SEC_OPEN.search(text)
    l = watch.LEDGER_SEC_LANDED.search(text)
    if o.start() >= l.start():
        raise LedgerError(
            f"heading invariant violated {when}: `## Recently landed` does not "
            f"follow `## Open` — the ledger is not in the expected order."
        )


def _heading_line(lines, pattern):
    """Index of the first line matching the anchored heading `pattern`."""
    for i, ln in enumerate(lines):
        if pattern.match(ln):
            return i
    raise LedgerError("a heading vanished between assert_headings and locate — cannot happen")


# ---------------------------------------------------------------------------
# counts — what the second 2026-07-28 incident broke (33 against 142)
# ---------------------------------------------------------------------------

def counts_text(text):
    """Open and landed id counts from the production parser, with expression.

    `watch.parse_ledger` returns id SETS (a combined head `- **#7/#8**` is two
    ids), and that set size is the figure every consumer uses — the dashboard's
    queue, `lint.check_status_agrees_with_ledger`, the burndown — so it is the
    count that was wrong. The expression is printed beside it so the number is
    never a mystery literal.
    """
    assert_headings(text, "on counts")
    open_ids, landed_ids = watch.parse_ledger(text)
    return (
        f"open ids:   {len(open_ids)}   "
        f"(len(watch.parse_ledger(text)[0]) — anchored `## Open` entry heads)\n"
        f"landed ids: {len(landed_ids)}   "
        f"(len(watch.parse_ledger(text)[1]) — anchored `## Recently landed`)\n"
    )


# ---------------------------------------------------------------------------
# fold — what the first 2026-07-28 incident broke (two landed headings)
# ---------------------------------------------------------------------------

def fold(text, task_id, note):
    """Move entry `task_id` from `## Open` to the top of `## Recently landed`.

    Appends `  · <note>` as a continuation line on the moved block; preserves
    the block's lines byte-exact otherwise. Returns the new text (the caller
    writes it). Raises `LedgerError` on any refusal or invariant violation;
    it never returns a text that fails `assert_headings`.
    """
    assert_headings(text, "before fold")

    # Membership comes from the PRODUCTION parser — never a hand-rolled scan,
    # which is the fifth thing that was wrong here.
    open_ids, landed_ids = watch.parse_ledger(text)
    sid = str(task_id)
    if sid in landed_ids:
        raise LedgerError(f"#{task_id} is already under `## Recently landed` — nothing to fold")
    if sid not in open_ids:
        raise LedgerError(f"#{task_id} is in neither section — unknown id")

    lines = text.split("\n")
    open_idx = _heading_line(lines, watch.LEDGER_SEC_OPEN)
    landed_idx = _heading_line(lines, watch.LEDGER_SEC_LANDED)
    open_lines = lines[open_idx + 1:landed_idx]

    # Locate the entry block by its head line, using the production head/id
    # patterns. An entry is its head (`^- **<ids-only>**`) plus the blank or
    # indented lines that follow, up to the next head — the same shape
    # `watch.ledger_entries` walks. `parse_ledger` promised this id is in Open,
    # so a failure to find exactly one head for it is a real inconsistency.
    head_indices = []
    matches = []
    for i, ln in enumerate(open_lines):
        m = watch.LEDGER_ENTRY.match(ln)
        if m:
            head_indices.append(i)
            if sid in watch.ENTRY_ID.findall(m.group(1)):
                matches.append(i)
    if len(matches) != 1:
        raise LedgerError(
            f"#{task_id} matches {len(matches)} open entry head(s); will not "
            f"fold an id that is not unique in `## Open`"
        )
    h = matches[0]
    next_head = next((hi for hi in head_indices if hi > h), len(open_lines))
    block = open_lines[h:next_head]  # head + continuations, incl. trailing separator blanks

    # Split the block's content from its trailing separator blanks: the
    # content moves and gains the note; the blanks are section structure.
    content_end = len(block)
    while content_end > 0 and block[content_end - 1].strip() == "":
        content_end -= 1
    moved = block[:content_end] + [NOTE_PREFIX + note]

    new_open_lines = open_lines[:h] + open_lines[next_head:]
    new_landed_lines = _prepend_at_top_of_landed(lines[landed_idx + 1:], moved)

    new_lines = (
        lines[:open_idx + 1]      # up to and including `## Open`
        + new_open_lines          # Open body, the folded entry removed
        + [lines[landed_idx]]     # the `## Recently landed` heading line
        + new_landed_lines        # landed body, the folded entry prepended
    )
    new_text = "\n".join(new_lines)

    # THE LINE THAT COST TWO INCIDENTS: assert on the BUILT text, before any
    # write reaches disk. A partial/corrupt write is the failure mode this tool
    # exists to make impossible.
    assert_headings(new_text, "after fold")
    return new_text


def _prepend_at_top_of_landed(landed_lines, moved):
    """Place `moved` as the first entry under `## Recently landed`.

    `moved` is the entry's content lines plus the note (no trailing blanks).
    The landed body conventionally opens with a blank line after the heading;
    that blank is dropped and a single blank separator is inserted after the
    moved entry, so the result has exactly one blank between the new entry and
    the former first one regardless of what was there.
    """
    i = 0
    while i < len(landed_lines) and landed_lines[i].strip() == "":
        i += 1
    return moved + [""] + landed_lines[i:]


# ---------------------------------------------------------------------------
# sweep (#404) — landings discoverable from git subjects, minus cited shas
#
# A lane cannot land work without committing, and this repo's commit
# convention puts the id in the subject BY CONSTRUCTION — so git log is a
# strictly more reliable landing channel than `.dreamwork/handoffs.md`,
# which is an extra act a lane must remember. This is the discovery twin of
# `lint.check_landed_still_open` (#323), not a second implementation: the
# correlation rule (git names a commit the entry does not) and the
# production helpers (`ledger_parse.open_section_text` /
# `ledger_parse.ledger_entries`) are the same; what differs is that the
# sweep is ADVISORY (exit 0 always), bounded to commits since a ref, and
# matches the full verb set — a discovery sweep tolerates weak verbs
# (`docs(#N)`) that the lint WARN may not.
# ---------------------------------------------------------------------------

# The id-bearing subject forms, derived from this repo's own git log
# (1,131 subjects measured: merge 132, fix 103, docs 77, feat 71, close 48,
# guard 18, design 15, test 9, refactor 1, perf 1). The parens may carry
# several ids (`merge(#422,#403)`); lint's CLOSE_SUBJECT takes only the
# first, which a discovery sweep must not.
SWEEP_SUBJECT = re.compile(
    r"^(?:merge|fix|feat|close|perf|refactor|guard|docs|test|design)"
    r"\((#\d+(?:,#\d+)*)\)")
SWEEP_ID = re.compile(r"#(\d+)")


def sweep(text, commits):
    """Correlate id-bearing subjects against the OPEN ids; subtract cited shas.

    `commits` is an iterable of (sha, subject) pairs, newest first. Returns
    (n_examined, findings) where findings is a list of (task_id, [(sha,
    subject), ...]) for open ids git names a landing for that the entry does
    not cite. `n_examined` counts EVERY commit looked at, matching subjects
    or not — a sweep that found nothing must be distinguishable from one
    that did not run.
    """
    open_ids, _ = watch.parse_ledger(text)
    bodies = {}
    for ids, body in ledger_entries(open_section_text(text) or ""):
        for tid in ids:
            bodies[tid] = body
    found = {}
    n = 0
    for sha, subject in commits:
        n += 1
        m = SWEEP_SUBJECT.match(subject)
        if not m:
            continue
        for tid in (int(x) for x in SWEEP_ID.findall(m.group(1))):
            # parse_ledger's ids are strings; ledger_entries' are ints — the
            # membership check is against the former, the body map the latter.
            if str(tid) not in open_ids:
                continue
            if sha in bodies.get(tid, ""):
                continue  # a deliberate partial: it cites its commit (#323's rule)
            found.setdefault(tid, []).append((sha, subject))
    return n, sorted(found.items())


# ---------------------------------------------------------------------------
# write — only after the post-write assertion has passed
# ---------------------------------------------------------------------------

def _write(path, text):
    p = Path(path)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, p)


# ---------------------------------------------------------------------------
# write verbs — store (#294 inc 9) + markdown, dispatched on source_of_truth
# ---------------------------------------------------------------------------

_MIGRATE_MOD = None


def _migrate_guard():
    """Load ud-dw-tasks-migrate (extensionless) for guard_markdown_write.

    The lane-H version gate lives there; calling it (not reimplementing it)
    keeps one copy of the post-cutover Markdown-write refusal (#263 lane H).
    """
    global _MIGRATE_MOD
    if _MIGRATE_MOD is None:
        import importlib.util
        import importlib.machinery
        cli = Path(__file__).resolve().parent.parent / "ud-dw-tasks-migrate"
        loader = importlib.machinery.SourceFileLoader(
            "_ud_dw_tasks_migrate", str(cli))
        spec = importlib.util.spec_from_loader("_ud_dw_tasks_migrate", loader)
        _MIGRATE_MOD = importlib.util.module_from_spec(spec)
        loader.exec_module(_MIGRATE_MOD)
    return _MIGRATE_MOD


def _fold_store(dw_dir, task_id, note):
    """Store-mode fold: land_task (state CAS open→landed, note appended to body).

    There is no text to move — the state flip IS the fold. The Markdown file
    is untouched (the store is the single source post-cutover).
    """
    store = ledger_store.open_store(store_path(dw_dir))
    try:
        ledger_write.land_task(store, task_id, note=note)
    finally:
        store.close()
    sys.stdout.write(f"folded #{task_id} (store: state open→landed)\n")


def _file_store(dw_dir, title, body, priority, type, origin):
    """Store-mode file: file_task (seeded AUTOINCREMENT id, chained filed event)."""
    store = ledger_store.open_store(store_path(dw_dir))
    try:
        new_id = ledger_write.file_task(
            store, title, body, priority=priority, type=type, origin=origin)
    finally:
        store.close()
    sys.stdout.write(f"filed #{new_id} (store)\n")
    return new_id


def _note_store(dw_dir, task_id, note):
    """Store-mode note: note_task (append note to body in any state, no event).

    There is no state change — a note annotates the body, so the store verb
    appends and the Markdown file is untouched (the store is the single
    source post-cutover).
    """
    store = ledger_store.open_store(store_path(dw_dir))
    try:
        ledger_write.note_task(store, task_id, note)
    finally:
        store.close()
    sys.stdout.write(f"noted #{task_id} (store)\n")


def file_text(text, title, note, priority, type, origin):
    """Markdown-mode file: insert a new entry under ``## Open``, bump ``Next id``.

    Returns the new text (the caller writes it). Raises ``LedgerError`` on any
    refusal or invariant violation; it never returns a text that fails
    ``assert_headings``. The entry shape matches the ledger's
    ``- **#N** — title · P2 · [type ·] origin: **value**`` idiom.
    """
    assert_headings(text, "before file")

    header = lint.NEXT_ID.search(text)
    if header is None:
        raise LedgerError(
            "no `Next id: **N**` header — cannot file without the next id")
    new_id = int(header.group(1))

    # Build the entry head + metadata chain, matching the ledger idiom.
    fields = [priority or "P2"]
    if type:
        fields.append(type)
    fields.append("origin: **{}**".format(origin or "loop"))
    head = "- **#{}** — {} · {}".format(new_id, title, " · ".join(fields))
    if note:
        head += "\n{}{}".format(NOTE_PREFIX, note)

    lines = text.split("\n")
    open_idx = _heading_line(lines, watch.LEDGER_SEC_OPEN)
    # Skip blank line(s) after the heading to find where entries begin, then
    # insert the new entry at the top of the open section.
    body_start = open_idx + 1
    while body_start < len(lines) and lines[body_start].strip() == "":
        body_start += 1
    new_lines = (
        lines[:open_idx + 1]   # up to and including ## Open
        + ["", head, ""]        # blank, new entry, blank separator
        + lines[body_start:]    # original open body onwards
    )
    new_text = "\n".join(new_lines)

    # Bump the Next id header via the production pattern (one reader).
    new_text = lint.NEXT_ID.sub(
        "Next id: **{}**".format(new_id + 1), new_text, count=1)

    assert_headings(new_text, "after file")
    return new_text


def note_text(text, task_id, note):
    """Markdown-mode note: append a ``  · <note>`` continuation line to an entry.

    The entry may be in either section (note works in any state). The note
    line is appended at the END of the entry's content block, matching how
    the coordinator's notes accumulate; the entry is never moved. Returns
    the new text (the caller writes it). Raises ``LedgerError`` on an unknown
    id or a non-unique match; it never returns a text that fails
    ``assert_headings``.

    The entry is located by the production head pattern
    (``watch.LEDGER_ENTRY`` + ``watch.ENTRY_ID``) after ``watch.parse_ledger``
    confirms the id is known in either section — never a fresh regex.
    """
    assert_headings(text, "before note")

    open_ids, landed_ids = watch.parse_ledger(text)
    sid = str(task_id)
    if sid not in open_ids and sid not in landed_ids:
        raise LedgerError(f"#{task_id} is in neither section — unknown id")

    lines = text.split("\n")
    matches = []
    for i, ln in enumerate(lines):
        m = watch.LEDGER_ENTRY.match(ln)
        if m and sid in watch.ENTRY_ID.findall(m.group(1)):
            matches.append(i)
    if len(matches) != 1:
        raise LedgerError(
            f"#{task_id} matches {len(matches)} entry head(s); will not "
            f"note an id that is not unique in the ledger")
    h = matches[0]

    # The entry's content runs from the head through blank/indented lines up
    # to the next column-0 content line (the production parser's own rule:
    # a column-0 line ends an entry). Append the note at the end of the
    # content (notes accumulate), before any trailing blank separator.
    next_head = len(lines)
    for j in range(h + 1, len(lines)):
        ln = lines[j]
        if ln.startswith(" ") or ln.startswith("\t") or ln == "":
            continue
        next_head = j
        break
    block_end = next_head
    while block_end > h + 1 and lines[block_end - 1].strip() == "":
        block_end -= 1

    new_lines = lines[:block_end] + [NOTE_PREFIX + note] + lines[block_end:]
    new_text = "\n".join(new_lines)

    assert_headings(new_text, "after note")
    return new_text


# ---------------------------------------------------------------------------
# sweep — the git half (subprocess stays out of the pure function)
# ---------------------------------------------------------------------------

def _git_subjects(repo, since):
    """(sha, subject) pairs, newest first; None when git cannot answer."""
    rng = [f"{since}..HEAD"] if since else []
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "log", "--format=%h\x1f%s"] + rng,
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    commits = []
    for line in out.stdout.splitlines():
        sha, sep, subject = line.partition("\x1f")
        if sep:
            commits.append((sha, subject))
    return commits


def _default_since(repo):
    """The most recent fold commit — the last time landings were reconciled."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "log", "--format=%H", "-n", "1",
             "--grep=^fold "],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def sweep_text(text, commits, since):
    """The advisory report. Always says how many commits were examined."""
    n, findings = sweep(text, commits)
    where = f"since {since[:12]}" if since else "across the whole history"
    lines = [f"sweep: examined {n} commits {where}"]
    for tid, landings in findings:
        ev = ", ".join(f"`{sha}` {subject}" for sha, subject in landings)
        lines.append(f"  #{tid} — {ev}")
    lines.append(
        f"sweep: {len(findings)} open id(s) git names a landing for that the "
        f"entry does not cite" if findings else
        "sweep: nothing to review (this ran — see the examined count above)")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# #357 — the warning footer every verb tacks onto stderr at exit.
#
# Design: `.dreamwork/docs/plans/cli-warning-layer.md` (both forks RULED:
# the footer prints on EVERY verb (Q5); every verb carries the FULL line
# (Q6, I1); the read-verb throttle is REFUTED — the footer is STATELESS).
#
# His five counts plus incomplete-data plus the journal unconsumed-receipt
# count, in his order, one dense line on STDERR (stdout stays machine-clean
# so `counts`/`fold --dry-run` stay pipeable). WARN, never ERROR: the footer
# never changes an exit code and never blocks. Quiet rules hold by content —
# a zero count is absent from the line, and a fully clean state prints
# nothing. STATELESS: it reads the live counts every call, no memory.
#
# Reuse, never rebuild: every count comes from a PRODUCTION reader —
# watch.parse_open_answers / parse_open_questions, store_ids_by_state (the
# SAME projection `counts` uses, so the open-task number cannot diverge),
# lint.check_unfolded_answers (the function that already computes the
# unfolded count + its age), and the journal's head_ordinal/cursor API (the
# same functions dev/journal_consume.py composes). A second implementation
# of any is the defect this design refused to propose.
# ---------------------------------------------------------------------------

JOURNAL_FILENAME = "user-events.sqlite3"
# The single consumer whose cursor the footer measures (delivery-modes.md /
# dev/journal_consume.py). A constant so the footer and the drain cannot
# drift on the string the cursor row is keyed by.
_JOURNAL_CONSUMER = "coordinator"


def _unconsumed_receipts(dw):
    """head_ordinal − the coordinator cursor's scanned_through.

    The durable 'something is waiting' signal — receipts the coordinator has
    not yet drained. Read-only and reuse-only: open_journal + head_ordinal +
    cursor are the same API dev/journal_consume.py composes, so the footer's
    count cannot diverge from the drain's own (cursor, head] range. An absent
    journal is empty (0) and is never created (the read has no side effect),
    matching `journal_consume.py pending`'s read-only posture.
    """
    journal = dw / JOURNAL_FILENAME
    if not journal.exists():
        return 0
    try:
        with open_journal(journal) as j:
            head = j.head_ordinal()
            scanned = j.cursor(_JOURNAL_CONSUMER).scanned_through_event_ordinal
    except sqlite3.Error:
        return 0  # unreadable journal is not a warning the footer can carry
    return max(0, head - scanned)


def _store_incomplete_counts(dw):
    """NULL ``type`` and NULL ``origin`` counts from the store (source only).

    His 'data is incomplete' warnings. Read-only over the store path the
    verbs use (``store_path``). Markdown mode has no such columns, so the
    counts are absent there (0) — they are a store concept, queried only
    when the store is the source of truth. ``origin`` NULL is legitimate for
    pre-cutoff tasks (forward-only from #213/#216); the footer reports the
    count, the squelch of legitimate noise is a separate concern not built
    here. Both counts share ONE connection (warm reads; the design budget).
    """
    if source_of_truth(str(dw)) != "store":
        return 0, 0
    db = store_path(str(dw))
    if not db.exists():
        return 0, 0
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error:
        return 0, 0
    try:
        untyped = conn.execute(
            "SELECT COUNT(*) FROM task WHERE type IS NULL").fetchone()[0]
        missing = conn.execute(
            "SELECT COUNT(*) FROM task WHERE origin IS NULL").fetchone()[0]
    except sqlite3.Error:
        return 0, 0
    finally:
        conn.close()
    return int(untyped), int(missing)


def _warning_counts(dw_dir):
    """The seven counts in his order, each from its production reader.

    Order is his (see the design doc's worked example —
    ``open tasks · unanswered questions · untyped · missing origin ·
    unconsumed receipts``, with the zero-counts absent): unchecked messages,
    open tasks, unanswered questions, unfolded answers, untyped, missing
    origin, unconsumed receipts.

    'new question count' and 'unanswered question count' are the SAME number
    (an open question in questions.md IS an unanswered one — there is no
    second state between asked and answered), so the footer emits one count
    for both. Measuring it twice would be a second reader of one fact.
    """
    dw = Path(dw_dir)
    counts = []

    # unchecked messages — answers.md `## Open` (watch.parse_open_answers).
    answers = dw / "answers.md"
    n = len(watch.parse_open_answers(answers.read_text())) if answers.exists() else 0
    counts.append(("unchecked messages", n))

    # open tasks — reuse the SAME projection `counts` uses (store or markdown),
    # so the footer's number and the verb's number are one fact, never two.
    if source_of_truth(str(dw)) == "store":
        open_ids, _ = store_ids_by_state(str(dw))
    else:
        ledger = dw / "tasks.md"
        open_ids, _ = watch.parse_ledger(ledger.read_text()) if ledger.exists() else ([], [])
    counts.append(("open tasks", len(open_ids)))

    # unanswered questions — questions.md `## Open` (watch.parse_open_questions).
    questions = dw / "questions.md"
    n = len(watch.parse_open_questions(questions.read_text())) if questions.exists() else 0
    counts.append(("unanswered questions", n))

    # unfolded answers — lint.check_unfolded_answers (the function, not a copy).
    rep = lint.Report()
    lint.check_unfolded_answers(dw, watch, rep)
    counts.append(("unfolded answers",
                   sum(1 for lvl, _, _ in rep.rows if lvl == lint.WARN)))

    # incomplete-data — untyped + missing origin, from the store (source only).
    untyped, missing = _store_incomplete_counts(dw)
    counts.append(("untyped", untyped))
    counts.append(("missing origin", missing))

    # unconsumed receipts — journal head − coordinator cursor.
    counts.append(("unconsumed receipts", _unconsumed_receipts(dw)))

    return counts


def _format_warnings(counts):
    """One dense line, zeros absent; empty string when everything is clean.

    The shape is deliberately a single line (not a table/box) because this
    rides output the human already scrolled to — a multi-line footer teaches
    him to scroll past it, the failure this design exists to prevent.
    """
    parts = [f"{n} {label}" for label, n in counts if n > 0]
    if not parts:
        return ""
    return "warnings: " + " · ".join(parts) + "\n"


def emit_warnings(dw_dir, rc=0, stream=None):
    """Tack the warning footer onto stderr; return ``rc`` unchanged (#357).

    Called by every verb's success path (rc == 0) at exit. WARN-only and
    stateless: it never touches stdout (stdout stays machine-clean) and never
    changes the exit code — a warning that blocks is a verb, and the settled
    shape is 'tacked on', not 'gated on'. Quiet rules hold by content: a zero
    count is absent, a clean tree prints nothing.

    Returns the ``rc`` it was handed so the footer is transparent to the
    verb's outcome (the production line the exit-code red-proof targets).
    """
    if rc == 0:
        line = _format_warnings(_warning_counts(dw_dir))
        if line:
            (stream if stream is not None else sys.stderr).write(line)
    return rc


# ---------------------------------------------------------------------------
# #497 — read-only task verbs (list / get / count / reviews).
#
# Ruled 2026-07-30 16:31 ("rec -- Python thin verbs"): four read verb groups
# over the store, riding ledger_parse primitives. READ-ONLY -- no verb here
# mutates the store, the ledger files, or the journal. The store read goes
# through ledger_parse (the ONE read module for both markdown and store);
# a second store reader in this file would be the defect #352 exists to
# prevent.
#
# OUTPUT CONTRACT -- the deliverable. A future binary rewrite of these verbs
# must reproduce this contract byte-for-byte; it is documented here in one
# place (stdout of a read verb is consumed by humans/scripts, not a file the
# loop writes for a tool to parse, so it lives in this docstring rather than
# file-formats.md -- no tool parses it yet, and adding a lint check for an
# unconsumed shape would be premature scope):
#
#   list --json  -> a JSON ARRAY, one object per task, each with EXACTLY:
#                     id (int) . state ("open"|"landed") . title (str)
#                     priority (str|null) . type (str|null) . origin (str|null)
#                   (body is omitted -- list is a summary; --state filters by
#                   state; --sort id (asc, default) | id-desc orders the array.)
#   count --json -> a JSON OBJECT mapping each counted state to an int.
#                   No --state: {"open": N, "landed": M}; --state open: {"open": N}.
#   get <id>     -> human-readable full record (no --json in the ruled shape):
#                   a `#<id>  <state>` line, one `field: value` line per
#                   populated structured field, a blank line, then the verbatim
#                   body. Unknown id -> one-line stderr + exit 1.
#   reviews list -> human-readable, one line per decision (newest first):
#                   `<artifact>  <decision>  <decided_at>  <actor>  - <question_title>`
#   reviews get <artifact> -> human-readable full row; unknown -> exit 1.
#
# Human shapes are stable: fixed columns on single lines, the body verbatim.
# `count` is the --json/--state sibling of `counts`: counts annotates the
# markdown expression and carries neither flag; count carries both and emits
# machine output. Markdown-mode (no store) list/count ride the same primitives
# the markdown `counts` uses; reviews is store-only (the table is a store
# concept -- /decide itself refuses markdown-mode writes, watch.py:_handle_decide).
# ---------------------------------------------------------------------------

# Closed value sets the verbs expose (parity with ledger_store.ENTRY_STATES).
_READ_STATES = ("open", "landed")
_READ_SORTS = ("id", "id-desc")


def _read_records(dw_dir):
    """All task records from the current source of truth, ascending by id.

    Store mode -> ``store_records`` (full structured rows). Markdown mode ->
    ``ledger_entries`` + ``watch.parse_led`` (the primitives ``counts`` uses)
    -- no new Markdown grammar. ``priority``/``type`` have no production
    reader in markdown (#346 measured them with a scan that is deliberately
    not a shared primitive), so they are None there and populated only in
    store mode; ``origin`` reuses ``classify_origin`` (the ONE origin
    grammar); ``title`` is the head-line prose after the id token.
    """
    if source_of_truth(dw_dir) == "store":
        return store_records(dw_dir)
    ledger = Path(dw_dir) / "tasks.md"
    if not ledger.exists():
        return []
    return _markdown_records(ledger.read_text())


def _markdown_records(text):
    """Records from the markdown ledger via the ONE entry grammar (#497).

    Reuses ``ledger_parse.ledger_entries`` (entries) + ``watch.parse_ledger``
    (open/landed id sets) -- no new Markdown parsing. ``title`` is the
    head-line prose after the id token (presentation of an entry the grammar
    already identified, not a second grammar).
    """
    open_ids, landed_ids = watch.parse_ledger(text)
    open_set, landed_set = set(open_ids), set(landed_ids)
    recs = []
    for ids, body in ledger_entries(text):
        head = body.split("\n", 1)[0]
        for tid in ids:
            sid = str(tid)
            state = ("open" if sid in open_set
                     else "landed" if sid in landed_set else "open")
            recs.append({
                "id": int(tid), "state": state, "title": _head_title(head),
                "body": body, "priority": None, "type": None,
                "origin": classify_origin(body), "blocked_on": None,
            })
    return recs


def _head_title(head_line):
    """Title prose off an entry head line (presentation, not a grammar).

    A head looks like ``- **#497** -- the title . P2 . task . origin: **loop**``;
    this strips the leading ``- **...**`` bold token and the `` -- `` separator
    and keeps the prose up to the first `` . `` (where the metadata chain
    begins). For a head with no `` -- `` returns ''.
    """
    rest = head_line
    if rest.startswith("- **"):
        end = rest.find("**", 4)
        if end != -1:
            rest = rest[end + 2:]
    rest = rest.strip()
    # The entry idiom separates the title from its metadata with ` -- ` then
    # chains metadata with ` . `.
    if rest.startswith("—"):
        rest = rest[1:].strip()
    if " · " in rest:
        rest = rest.split(" · ", 1)[0]
    return rest


def _records_for(args, dw_dir):
    """Records filtered by ``--state`` and ordered by ``--sort``."""
    recs = _read_records(dw_dir)
    if getattr(args, "state", None):
        recs = [r for r in recs if r["state"] == args.state]
    sort = getattr(args, "sort", "id") or "id"
    recs.sort(key=lambda r: r["id"], reverse=(sort == "id-desc"))
    return recs


def _record_json(r, body):
    """The JSON object for one record -- EXACTLY the contract keys."""
    d = {"id": r["id"], "state": r["state"], "title": r["title"],
         "priority": r["priority"], "type": r["type"], "origin": r["origin"]}
    if body:
        d["body"] = r["body"]
        d["blocked_on"] = r["blocked_on"]
    return d


def _list_line(r):
    """One stable human line per task for `list`."""
    parts = [f"#{r['id']}", r["state"]]
    for key in ("priority", "type", "origin"):
        if r[key]:
            parts.append(r[key])
    return f"{'  '.join(parts)}  — {r['title']}"


def _record_text(r):
    """The stable human full-record shape for `get`."""
    lines = [f"#{r['id']}  {r['state']}", f"title: {r['title']}"]
    for key in ("priority", "type", "origin", "blocked_on"):
        if r.get(key):
            lines.append(f"{key}: {r[key]}")
    lines += ["", r["body"].rstrip("\n")]
    return "\n".join(lines) + "\n"


def _verb_list(args, dw_dir):
    recs = _records_for(args, dw_dir)
    if getattr(args, "json", False):
        sys.stdout.write(json.dumps([_record_json(r, body=False) for r in recs]) + "\n")
        return 0
    if not recs:
        sys.stdout.write("(no tasks)\n")
        return 0
    for r in recs:
        sys.stdout.write(_list_line(r) + "\n")
    return 0


def _verb_get(args, dw_dir):
    recs = _read_records(dw_dir)
    match = next((r for r in recs if r["id"] == args.id), None)
    if match is None:
        sys.stderr.write(f"ledger: #{args.id} not found\n")
        return 1
    sys.stdout.write(_record_text(match))
    return 0


def _verb_count(args, dw_dir):
    """Counts by state -- the --json/--state sibling of `counts`.

    Rides the SAME primitives `counts` uses (store_ids_by_state / parse_ledger)
    so the count can never diverge from `counts`'s figure. The difference:
    `count` carries --state (filter to one state) and --json (machine output);
    `counts` annotates the markdown expression and carries neither.
    """
    if source_of_truth(dw_dir) == "store":
        open_ids, landed_ids = store_ids_by_state(dw_dir)
    else:
        ledger = Path(dw_dir) / "tasks.md"
        if not ledger.exists():
            open_ids, landed_ids = [], []
        else:
            open_ids, landed_ids = watch.parse_ledger(ledger.read_text())
    counts = {"open": len(open_ids), "landed": len(landed_ids)}
    if args.state:
        counts = {args.state: counts.get(args.state, 0)}
    if args.json:
        sys.stdout.write(json.dumps(counts) + "\n")
        return 0
    for st in _READ_STATES:
        if st in counts:
            sys.stdout.write(f"{st}: {counts[st]}\n")
    return 0


def _review_line(r):
    """One stable human line per decision for `reviews list` (newest first)."""
    return (f"{r['artifact']}  {r['decision']}  {r['decided_at']}"
            f"  {r['actor']}  — {r['question_title']}")


def _review_text(r):
    """The stable human full-row shape for `reviews get`."""
    return "\n".join([
        f"artifact: {r['artifact']}", f"question_title: {r['question_title']}",
        f"decision: {r['decision']}", f"decided_at: {r['decided_at']}",
        f"actor: {r['actor']}",
    ]) + "\n"


def _verb_reviews(args, dw_dir):
    """reviews list|get -- read the review_decision table (store-mode only)."""
    if source_of_truth(dw_dir) != "store":
        sys.stderr.write("reviews: no ledger store (markdown mode)\n")
        return 1
    rows = store_review_decisions(dw_dir)
    if args.reviews_cmd == "get":
        row = next((r for r in rows if r["artifact"] == args.artifact), None)
        if row is None:
            sys.stderr.write(f"reviews: {args.artifact!r} not found\n")
            return 1
        sys.stdout.write(_review_text(row))
        return 0
    # list -- newest first (the primitive returns ascending by decided_at).
    if not rows:
        sys.stdout.write("(no review decisions)\n")
        return 0
    for r in reversed(rows):
        sys.stdout.write(_review_line(r) + "\n")
    return 0


# ---------------------------------------------------------------------------
# #558 — groom: backfill NULL origins to 'unknown' (the truthful pre-contract
# value), store-mode only. The audited surface for that backfill — never raw
# SQL outside it.
#
# `unknown` is not a guess: lint.check_task_origins (lint.py, #213) names it
# a first-class value ("not a failure: the truthful origin of every post-
# cutoff task filed before this contract existed"), and the store CHECK
# constraint admits it:
#   origin TEXT CHECK (origin IS NULL OR origin IN ('human','loop','unknown'))
# (ledger_store.py:262). Before this verb, that column stayed NULL forever
# and the #357 footer printed a `missing origin` count that could not shrink
# on its own; groom is the one audited way to make it do so.
# ---------------------------------------------------------------------------

def _verb_groom(dw_dir):
    """Backfill the store's NULL ``origin`` to ``'unknown'`` (#558).

    ``'unknown'`` is the truthful origin of a task filed before the #213
    origin contract — ``lint.check_task_origins`` names it a first-class
    value ("not a failure"), and the store CHECK constraint admits it
    (``origin IS NULL OR origin IN ('human','loop','unknown')``,
    ``ledger_store.py:262``). This verb is the AUDITED surface for that
    backfill — never raw SQL outside it. It reports the count of rows
    changed and is idempotent: once every NULL is ``'unknown'``, the
    ``WHERE origin IS NULL`` clause matches nothing and a second run
    reports 0.

    MARKDOWN-MODE DECISION: refuse. The store's NULL ``origin`` is a
    COLUMN state; markdown mode has no such column — origins are TEXT
    claims an entry makes (``origin: **human**``), classified by
    ``classify_origin``. A markdown "groom" would be a TEXT REWRITE
    (inserting ``origin: **unknown**`` into entry bodies), a fundamentally
    different act from a column UPDATE, and ``check_task_origins`` already
    enforces that governed entries (id >= 216) carry exactly one marker.
    There is no "missing origin" column to backfill in markdown mode — the
    #357 footer's missing-origin count is a STORE concept (0 in markdown),
    so refusing keeps one act per surface and never invents a markdown
    write the cutover retired.
    """
    if source_of_truth(dw_dir) != "store":
        sys.stderr.write(
            "groom: markdown mode has no origin column — origins are text "
            "claims an entry makes, not a backfillable NULL; the store is "
            "the source of truth after the #294 cutover\n")
        return 1
    store = ledger_store.open_store(store_path(dw_dir))
    try:
        # The audited backfill. rowcount is the changed rows; a re-run on a
        # store with no NULL origin matches nothing (idempotent).
        cur = store.conn.execute(
            "UPDATE task SET origin='unknown' WHERE origin IS NULL")
        changed = cur.rowcount
        store.conn.commit()
    finally:
        store.close()
    sys.stdout.write(
        f"groom: backfilled {changed} NULL origin(s) to 'unknown'\n")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(
        prog="dev/ledger.py",
        description="The one supported way to fold a ledger entry (#440).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("counts", help="open and landed id counts via watch.parse_ledger")
    pc.add_argument("--ledger", default=LEDGER_DEFAULT, help="path to the ledger (default %(default)s)")

    pf = sub.add_parser("fold", help="move an entry from ## Open to the top of ## Recently landed")
    pf.add_argument("id", type=int, help="the task id to fold (e.g. 440)")
    pf.add_argument("--note", required=True, help="appended as a `  · <text>` continuation line")
    pf.add_argument("--ledger", default=LEDGER_DEFAULT, help="path to the ledger (default %(default)s)")
    pf.add_argument("--dry-run", action="store_true", help="print the result; do not write")

    pfile = sub.add_parser("file", help="file a new task under ## Open (or the store after cutover)")
    pfile.add_argument("title", help="the task title (head-line prose)")
    pfile.add_argument("--note", default=None, help="body / continuation note")
    pfile.add_argument("--priority", default=None, help="priority band P0-P3 (default P2)")
    pfile.add_argument("--type", default=None, help="task type (idea/task/bug/...)")
    pfile.add_argument("--origin", default="loop", help="who filed: human/loop/unknown (default %(default)s)")
    pfile.add_argument("--ledger", default=LEDGER_DEFAULT, help="path to the ledger (default %(default)s)")
    pfile.add_argument("--dry-run", action="store_true", help="print the result; do not write")

    pn = sub.add_parser("note", help="append a `  · <note>` line to an entry in either section")
    pn.add_argument("id", type=int, help="the task id to annotate (e.g. 294)")
    pn.add_argument("--note", required=True, help="appended as a `  · <text>` continuation line")
    pn.add_argument("--ledger", default=LEDGER_DEFAULT, help="path to the ledger (default %(default)s)")
    pn.add_argument("--dry-run", action="store_true", help="print the result; do not write")

    ps = sub.add_parser(
        "sweep",
        help="open ids git names a landing for that the entry does not cite "
             "(advisory; exit 0 always)")
    ps.add_argument("--since", default=None,
                    help="ref to scan from (default: the most recent fold commit)")
    ps.add_argument("--ledger", default=LEDGER_DEFAULT, help="path to the ledger (default %(default)s)")
    ps.add_argument("--repo", default=".", help="the git repo to scan (default %(default)s)")

    # #497 — read-only task verbs. list/get/count over the store (or markdown
    # for list/count); reviews over the review_decision table (store-mode only).
    plist = sub.add_parser("list", help="list tasks (read-only) [#497]")
    plist.add_argument("--state", choices=_READ_STATES, default=None,
                       help="filter to one state (default: both)")
    plist.add_argument("--sort", choices=_READ_SORTS, default="id",
                       help="row order (default id ascending)")
    plist.add_argument("--json", action="store_true",
                       help="emit a JSON array (stable field names; see module docstring)")
    plist.add_argument("--ledger", default=LEDGER_DEFAULT,
                       help="path to the ledger; its parent is the .dreamwork/ dir (default %(default)s)")

    pget = sub.add_parser("get", help="show one task's full record (read-only) [#497]")
    pget.add_argument("id", type=int, help="the task id")
    pget.add_argument("--ledger", default=LEDGER_DEFAULT,
                      help="path to the ledger; its parent is the .dreamwork/ dir (default %(default)s)")

    pcnt = sub.add_parser("count", help="count tasks by state (read-only) [#497]")
    pcnt.add_argument("--state", choices=_READ_STATES, default=None,
                      help="count one state only (default: both)")
    pcnt.add_argument("--json", action="store_true",
                      help="emit a JSON object {state: count}")
    pcnt.add_argument("--ledger", default=LEDGER_DEFAULT,
                      help="path to the ledger; its parent is the .dreamwork/ dir (default %(default)s)")

    prev = sub.add_parser("reviews", help="read the review_decision table (store-mode only) [#497]")
    prev_sub = prev.add_subparsers(dest="reviews_cmd", required=True)
    prev_list = prev_sub.add_parser("list", help="list all review decisions (newest first)")
    prev_list.add_argument("--ledger", default=LEDGER_DEFAULT,
                           help="path to the ledger; its parent is the .dreamwork/ dir (default %(default)s)")
    prev_get = prev_sub.add_parser("get", help="one review decision by artifact")
    prev_get.add_argument("artifact", help="the artifact name (review_decision primary key)")
    prev_get.add_argument("--ledger", default=LEDGER_DEFAULT,
                          help="path to the ledger; its parent is the .dreamwork/ dir (default %(default)s)")

    pgroom = sub.add_parser(
        "groom",
        help="backfill the store's NULL origins to 'unknown' (store-mode only) [#558]")
    pgroom.add_argument("--ledger", default=LEDGER_DEFAULT,
                        help="path to the ledger; its parent is the .dreamwork/ dir (default %(default)s)")

    args = p.parse_args(argv)
    rc = _dispatch(args)
    # #357 — the warning footer tacks onto stderr on every verb's success
    # path. WARN-only, stateless, never touches stdout, never changes rc
    # (emit_warnings returns the rc it was handed).
    return emit_warnings(str(Path(args.ledger).parent), rc)


def _dispatch(args):
    """Run one verb and return its exit code. The footer is tacked on by main."""
    if args.cmd == "sweep":
        # Advisory by design (#404): every failure mode is a printed line and
        # exit 0 — "cannot check" must never read as "nothing to fix".
        ledger_path = Path(args.ledger)
        if not ledger_path.exists():
            sys.stdout.write(f"sweep: ledger not found: {ledger_path} (examined 0 commits)\n")
            return 0
        since = args.since if args.since is not None else _default_since(args.repo)
        commits = _git_subjects(args.repo, since)
        if commits is None:
            sys.stdout.write("sweep: git could not answer (not a repo?) — did not run\n")
            return 0
        sys.stdout.write(sweep_text(ledger_path.read_text(), commits, since))
        return 0

    ledger_path = Path(args.ledger)
    dw_dir = str(ledger_path.parent)

    # #497 — read-only verbs dispatch on source_of_truth themselves and never
    # touch the markdown file, so they run BEFORE the markdown-existence gate
    # below (a store-mode project need not keep tasks.md around). They ride
    # ledger_parse primitives and mutate nothing.
    if args.cmd == "count":
        return _verb_count(args, dw_dir)
    if args.cmd == "list":
        return _verb_list(args, dw_dir)
    if args.cmd == "get":
        return _verb_get(args, dw_dir)
    if args.cmd == "reviews":
        return _verb_reviews(args, dw_dir)

    # #558 — groom dispatches on source_of_truth itself (it is store-mode
    # only and refuses markdown with a named reason), so like the #497 read
    # verbs it runs BEFORE the markdown-existence gate below. It mutates the
    # STORE only (never the markdown file).
    if args.cmd == "groom":
        return _verb_groom(dw_dir)

    # #294 inc 9: write verbs (fold, file, note) dispatch on source_of_truth.
    # Store mode → the store write verbs; markdown mode → today's text path.
    # `counts` (inc 7) is a read consumer and dispatches below.
    if args.cmd in ("fold", "file", "note") and source_of_truth(dw_dir) == "store":
        if args.cmd == "fold":
            _fold_store(dw_dir, args.id, args.note)
            return 0
        if args.cmd == "note":
            _note_store(dw_dir, args.id, args.note)
            return 0
        _file_store(dw_dir, args.title, args.note or args.title,
                    args.priority, args.type, args.origin)
        return 0

    if args.cmd == "counts" and source_of_truth(dw_dir) == "store":
        open_ids, landed_ids = store_ids_by_state(dw_dir)
        sys.stdout.write(
            f"open ids:   {len(open_ids)}   "
            f"(store_ids_by_state — task.state='open')\n"
            f"landed ids: {len(landed_ids)}   "
            f"(store_ids_by_state — task.state='landed')\n")
        return 0

    if not ledger_path.exists():
        sys.stderr.write(f"ledger not found: {ledger_path}\n")
        return 2
    text = ledger_path.read_text()

    # Markdown write path — refuse post-cutover via the same gate migrate
    # uses (defense-in-depth: the dispatch above already routed cut-over
    # writes to the store; this catches a watermark set between dispatch and
    # write, and documents that the markdown writer is pre-cutover only).
    if args.cmd in ("fold", "file", "note"):
        try:
            _migrate_guard().guard_markdown_write(dw_dir)
        except Exception as exc:
            sys.stderr.write(f"ledger: {exc}\n")
            return 1

    try:
        if args.cmd == "counts":
            sys.stdout.write(counts_text(text))
            return 0
        if args.cmd == "fold":
            new_text = fold(text, args.id, args.note)  # asserts before AND after
            if args.dry_run:
                sys.stdout.write(new_text)
                if not new_text.endswith("\n"):
                    sys.stdout.write("\n")
                return 0
            _write(args.ledger, new_text)
            sys.stdout.write(f"folded #{args.id} into {args.ledger}\n")
            return 0
        if args.cmd == "file":
            new_text = file_text(text, args.title, args.note, args.priority,
                                 args.type, args.origin)
            if args.dry_run:
                sys.stdout.write(new_text)
                if not new_text.endswith("\n"):
                    sys.stdout.write("\n")
                return 0
            _write(args.ledger, new_text)
            sys.stdout.write(f"filed into {args.ledger}\n")
            return 0
        if args.cmd == "note":
            new_text = note_text(text, args.id, args.note)  # asserts before AND after
            if args.dry_run:
                sys.stdout.write(new_text)
                if not new_text.endswith("\n"):
                    sys.stdout.write("\n")
                return 0
            _write(args.ledger, new_text)
            sys.stdout.write(f"noted #{args.id} into {args.ledger}\n")
            return 0
    except LedgerError as e:
        sys.stderr.write(f"ledger: {e}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
