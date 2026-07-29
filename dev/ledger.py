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
  python3 dev/ledger.py sweep [--since REF] [--ledger PATH] [--repo PATH]

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
import os
import re
import subprocess
import sys
from pathlib import Path

# `watch.py` lives at the repo root; this module lives in `dev/`. Add the
# root so `import watch` works when run as `python3 dev/ledger.py` from the
# root (in which case sys.path[0] is `dev/`, not the cwd).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import watch  # noqa: E402  — the production parser, reused not copied
from ledger_parse import ledger_entries, open_section_text  # noqa: E402

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

    ps = sub.add_parser(
        "sweep",
        help="open ids git names a landing for that the entry does not cite "
             "(advisory; exit 0 always)")
    ps.add_argument("--since", default=None,
                    help="ref to scan from (default: the most recent fold commit)")
    ps.add_argument("--ledger", default=LEDGER_DEFAULT, help="path to the ledger (default %(default)s)")
    ps.add_argument("--repo", default=".", help="the git repo to scan (default %(default)s)")

    args = p.parse_args(argv)

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
    if not ledger_path.exists():
        sys.stderr.write(f"ledger not found: {ledger_path}\n")
        return 2
    text = ledger_path.read_text()

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
    except LedgerError as e:
        sys.stderr.write(f"ledger: {e}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
