#!/usr/bin/env python3
"""#875 — the handoffs drain: an honest join over ``.dreamwork/handoffs.md``.

``handoffs.md`` is the supplementary landing route — the one git cannot see,
for work a session that does not own the ledger landed.  Every tick the
coordinator reads its ``## Pending`` and folds whatever is not yet under
``## Folded``.  There was NO tool for that fold, so the join was hand-written
each tick, and on 2026-08-01 20:26 a join on the WRONG key (SHA) reported
**"120 unfolded"** before a join on the right key (task id) reported **0**.
Ground truth was 0: every pending id was folded.  The SHA join looked
plausible and its number looked alarming, and nothing in the output said what
it had joined on (#875, the #868 denominator family one level worse: the
denominator was never printed at all).

This is that drain: a read-only CLI that joins the two sections ON TASK ID,
SAYS SO in its output, and prints both denominators on every path so a run
that found nothing is distinguishable from one that did not run (#404 / #671,
the contract ``dev/ledger.py sweep`` already honours for the git route).  It
mirrors ``dev/journal_consume.py``'s shape one level over: ``journal_consume``
composes the already-landed ``events_since_cursor`` projection and adds no new
journal query; this tool composes the already-landed ``watch.parse_handoffs``
projection and adds no new parser.  One grammar serves lint, the dashboard,
and this drain — a second parser is exactly the defect class that produced the
false 120 (two instruments, one wrong key, nothing to flag the disagreement).

SUBCOMMANDS
  pending   READ-ONLY.  Reads ``## Pending`` and ``## Folded``, joins on the
            chosen key, and prints the unfolded set with its key and both
            denominators.  Default key ``id`` (task id — the key both sections
            actually key on).  ``--key sha`` joins on SHA instead and EXISTS TO
            DEMONSTRATE THE ORIGINAL WRONG KEY: folded lines cite merge SHAs,
            pending lines land work SHAs, so a SHA join reports a large false
            remainder.  The key is printed on every line of output so a wrong
            key can never again read as a right one.  Advisory: exit 0 always,
            the way ``sweep`` is advisory (#875 proposes "mirroring sweep's
            contract").

NO FOLD VERB THIS INCREMENT.  The measured defect is entirely on the READ
side (the wrong join key); a fold verb writes a tracked file the coordinator
owns (#687 makes the coordinator ``handoffs.md``'s single writer), and a wrong
append is harder to undo than a wrong report.  Read-only closes the measured
defect; the fold half is deferred.  See the delivery's IGC for the decision.

THE APPEND-ONLY CONTRACT IS RESPECTED BY CONSTRUCTION: this tool only ever
READS ``handoffs.md``.  It never opens the file for writing; it composes a
pure parser and prints.  Nothing moves between the sections because nothing
writes.

USAGE
  python3 dev/handoffs_drain.py pending [--handoffs PATH] [--key {id,sha}]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# `watch` is a module at the repo root; this module lives in `dev/`.  Add the
# root so `from watch import parse_handoffs` works when run as
# `python3 dev/handoffs_drain.py` (sys.path[0] is then `dev/`, not the cwd) —
# the same one-line adjustment `dev/journal_consume.py` makes to reach
# `user_events`.  Importing the two PURE parser functions (not a re-implementation)
# is the whole point: lint, the dashboard, and this drain share ONE grammar, so
# they cannot drift the way the hand-written SHA join drifted from the id one.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from watch import parse_handoffs  # noqa: E402  — the authoritative grammar
from watch import pending_handoff_records  # noqa: E402  — the dashboard's (id, sha) view
from watch import HANDOFF_PENDING_RE, HANDOFF_BARE_RE  # noqa: E402  — coverage scan

HANDOFFS_DEFAULT = ".dreamwork/handoffs.md"

# The keys this tool will join on.  ``id`` is the default and the one both
# sections actually key on; ``sha`` is the ORIGINAL WRONG KEY, kept so the same
# tool can demonstrate both answers on the same fixture (#875 red-proof).  The
# key string is printed in every headline, so which key was used is visible on
# every path — the property the measured defect violated.
KEY_ID = "id"
KEY_SHA = "sha"
KEYS = (KEY_ID, KEY_SHA)

# How each key renders in the headline.  The label names the key in prose a
# tired reader cannot mistake: "task id" vs "sha".  The whole defect was a key
# that was never named.
KEY_LABEL = {KEY_ID: "task id", KEY_SHA: "sha"}

# Stable exit codes.  Advisory like ``sweep``: the drain reports, it does not
# gate — a non-zero exit would train the coordinator to ignore the alarming
# case (#868: the alarm must be carried in the PRINTED numbers and key, not in
# a code the reader learns to overlook).
EX_OK = 0
EX_USAGE = 64


def _read_handoffs_text(path: str) -> str:
    """The file's text, or ``""`` when absent.

    An absent ``handoffs.md`` is EMPTY, not an error: a fresh target has no
    hand-offs, and the drain must report ``0 pending + 0 folded`` with its key
    printed rather than refuse — the #404/#671 discriminability rule (a
    "found nothing" that prints its denominators differs from "did not run").
    Degrades to ``""`` on read error for the same reason a guard whose subject
    may not exist returns a reading, never throws.
    """
    p = Path(path)
    try:
        return p.read_text() if p.exists() else ""
    except OSError:
        return ""


def unkeyable_pending_lines(text: str):
    """Entry-shaped ``## Pending`` lines ``parse_handoffs`` silently drops.

    Requirement #3 of #875: "a pending line with no id must be reported as
    unkeyable, not silently dropped."  ``parse_handoffs`` collects a Pending
    line as a pending ROW when it matches the full grammar (which requires an
    id token), and as MALFORMED when it at least carries a ``**#…**`` bold id
    head (HANDOFF_BARE_RE).  A Pending line whose bold head has NO ``#`` — e.g.
    ``- **not-an-id** · landed …`` — matches NEITHER and is dropped outright.
    That is the "no id" case the brief names, and the drain must surface it.

    This is a COVERAGE scan, not a second parser: it reuses watch's own
    HANDOFF_PENDING_RE / HANDOFF_BARE_RE to classify, so it cannot drift from
    the grammar — it asks only "did parse_handoffs account for this line, or
    drop it?"  A line is unkeyable iff it sits under ``## Pending``, looks like
    an entry (``- **``), and matches neither regex.  Returns the raw lines.
    """
    out = []
    section = None
    for ln in (text or "").splitlines():
        s = ln.strip()
        if s == "## Pending":
            section = "P"; continue
        if s == "## Folded":
            section = "F"; continue
        if s.startswith("## "):
            section = None; continue
        if section != "P":
            continue
        if not ln.lstrip().startswith("- **"):
            continue  # not an entry head (blank, prose, sub-bullet)
        if HANDOFF_PENDING_RE.match(ln) or HANDOFF_BARE_RE.match(ln):
            continue  # parse_handoffs collected it (as pending or malformed)
        out.append(ln)
    return out


def join_unfolded(pending, folded_ids, key: str):
    """The pending rows whose key matches NO folded entry, under ``key``.

    ``pending`` is the list ``watch.parse_handoffs`` returns (each row unpacks
    as ``(id, sha, claimer)`` and exposes ``.shas``); ``folded_ids`` is the
    ``FoldedHandoffs`` set it returns.  Returns ``(unfolded_rows, folded_pop)``
    where ``folded_pop`` is the denominator the join ran against — id TOKENS for
    ``key=id`` (so the headline can print "164 folded ids"), or the SHA SET for
    ``key=sha`` (so it prints "236 folded shas").  Returning the population the
    join used is what makes the denominator honest: it is the set the remainder
    was computed against, not an unrelated count.

    KEY=id joins pending id ∈ folded_ids (exact set membership — a folded
    ``#862`` does NOT fold a pending ``#86``, the substring trap the brief names
    as "the likely real bug in any fix here"; set membership is exact by
    construction).  KEY=sha joins pending shas ∩ folded shas; because folded
    lines cite MERGE shas and pending lines land WORK shas, this reports a large
    false remainder — the original 120.  Both are computed from the SAME parsed
    populations, so "same fixture, two keys, two answers" is one ``--key`` flip.
    """
    if key == KEY_SHA:
        # Every sha a fold cites, lowercased (parse_handoffs already lowercases
        # fold shas; lowercase pending shas here to match case-insensitively).
        folded_shas = set()
        for shas in folded_ids.shas_by_id.values():
            folded_shas.update(s.lower() for s in shas)
        unfolded = [
            row for row in pending
            if not ({s.lower() for s in row.shas} & folded_shas)
        ]
        return unfolded, folded_shas
    # KEY_ID — exact membership.  `row.id in folded_ids` is set containment on
    # normalised id tokens, never a substring test.
    unfolded = [row for row in pending if row.id not in folded_ids]
    return unfolded, folded_ids


def _headline(pending_n: int, folded_pop_n: int, key: str, unfolded_n: int,
              distinct_unfolded_n: int, malformed_n: int, unkeyable_n: int,
              folded_pop_label: str) -> str:
    """The always-printed summary line — mirrors ``sweep``'s examined-count line.

    Every denominator and the key print on EVERY path (including the empty
    file), so a 0-remainder names its key and populations rather than reading as
    a bare all-clear (#868: a join that matched zero pairs and a corpus that
    genuinely has zero unfolded must not print alike).  Malformed and unkeyable
    are named separately when non-zero so a reader sees the join REFUSED on
    those entries rather than guessing.
    """
    distinct_clause = (
        f" / {distinct_unfolded_n} distinct id(s)"
        if distinct_unfolded_n != unfolded_n else ""
    )
    refuse_clauses = []
    if malformed_n:
        refuse_clauses.append(f"{malformed_n} malformed")
    if unkeyable_n:
        refuse_clauses.append(f"{unkeyable_n} unkeyable")
    refuse_clause = (
        "; " + " / ".join(refuse_clauses) if refuse_clauses else ""
    )
    return (
        f"handoffs: examined {pending_n} pending + {folded_pop_n} "
        f"{folded_pop_label} (joined on {KEY_LABEL[key]}); "
        f"{unfolded_n} unfolded{distinct_clause}{refuse_clause}"
    )


def cmd_pending(args, out, err) -> int:
    """Read-only: join ``## Pending`` against ``## Folded`` and print the remainder.

    Never writes.  Composes ``watch.parse_handoffs`` (the grammar lint and the
    dashboard already use) and ``watch.pending_handoff_records`` (the
    dashboard's ``(id, sha)``-correlated unfolded view) — it adds no parser, so
    it cannot disagree with either on the grammar.  The join key is chosen by
    ``--key`` and PRINTED in the headline; the default ``id`` is the key both
    sections key on, and ``sha`` is kept to demonstrate the original wrong key.

    For ``--key id`` the headline remainder is the id-join (pending id ∉ folded
    ids), AND a second line reports the dashboard's ``(id, sha)``-correlated
    count — so the tool never silently disagrees with the status panel.  The two
    differ only in the #409 multi-landing case (one id, several landings, a fold
    that cites a sha matching a sibling); when they agree, both are visible, and
    when they differ, both are visible.  Either way the numbers cannot degrade
    to a silent zero.
    """
    text = _read_handoffs_text(args.handoffs)
    pending, folded_ids, malformed = parse_handoffs(text)
    unkeyable = unkeyable_pending_lines(text)
    unfolded, folded_pop = join_unfolded(pending, folded_ids, args.key)
    pending_n = len(pending)
    # The denominator the join used: id tokens for id, shas for sha.  Label it
    # so the headline names the population, not just its size.
    if args.key == KEY_SHA:
        folded_pop_n, folded_pop_label = len(folded_pop), "folded shas"
    else:
        folded_pop_n, folded_pop_label = len(folded_pop), "folded ids"
    distinct_unfolded = len({row.id for row in unfolded})
    out.write(_headline(
        pending_n, folded_pop_n, args.key, len(unfolded), distinct_unfolded,
        len(malformed), len(unkeyable), folded_pop_label) + "\n")
    # The dashboard's (id, sha) view — printed under the id key so the tool and
    # the status panel cannot silently disagree.  Computed from the SAME text by
    # the SAME projection the dashboard uses; this is a reading, not a second
    # join.  Suppressed under --key sha (the demonstration key) where it would
    # be noise beside the deliberately-wrong sha remainder.
    if args.key == KEY_ID:
        dash = len(pending_handoff_records(text))
        out.write(
            f"handoffs: dashboard (id, sha) correlation: {dash} unfolded "
            f"(the status panel's view)\n")
    for row in unfolded:
        shas = ", ".join(f"`{s}`" for s in row.shas)
        if args.key == KEY_SHA:
            out.write(f"  UNFOLDED-by-sha\t#{row.id}\tlanded {shas}\tby {row.claimer}\n")
        else:
            out.write(f"  UNFOLDED\t#{row.id}\tlanded {shas}\tby {row.claimer}\n")
    # Refuse rather than guess: every entry parse_handoffs could not key is
    # LISTED, never dropped from either side of the join.  Two channels, both
    # named in the headline: MALFORMED (parse_handoffs flags a ``**#…**`` head
    # it cannot full-match — wrong section, bad grammar) and UNKEYABLE (a
    # Pending entry whose bold head carries no id at all — the case #875 names,
    # which parse_handoffs drops and this drain's coverage scan recovers).
    for nid, line in malformed:
        out.write(f"  MALFORMED\t#{nid if nid else '(no id)'}\t{line.strip()}\n")
    for line in unkeyable:
        out.write(f"  UNKEYABLE\t{line.strip()}\n")
    return EX_OK


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dev/handoffs_drain.py",
        description=(
            "Drain .dreamwork/handoffs.md: join ## Pending against ## Folded "
            "on task id, print the unfolded set with its key and both "
            "denominators (#875). Read-only; advisory."
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser(
        "pending",
        help="join ## Pending against ## Folded and print the unfolded set (read-only)",
    )
    pp.add_argument(
        "--handoffs", default=HANDOFFS_DEFAULT,
        help="handoffs.md path (default: %(default)s)",
    )
    pp.add_argument(
        "--key", choices=KEYS, default=KEY_ID,
        help=(
            "join key (default: %(default)s). 'id' is the task id both sections "
            "key on. 'sha' is the ORIGINAL WRONG KEY (#875): folded lines cite "
            "merge shas and pending lines land work shas, so a sha join reports "
            "a large false remainder — kept to demonstrate the defect on the "
            "same fixture. The key is printed in every headline."
        ),
    )
    return p


def main(argv=None, out=None, err=None) -> int:
    """Dispatch one subcommand. Returns a stable exit code; never raises SystemExit."""
    if argv is None:
        argv = sys.argv[1:]
    if out is None:
        out = sys.stdout
    if err is None:
        err = sys.stderr
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else EX_USAGE
        return EX_OK if code == 0 else EX_USAGE
    if args.cmd == "pending":
        return cmd_pending(args, out, err)
    return EX_USAGE  # argparse(required=True) makes this unreachable


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
