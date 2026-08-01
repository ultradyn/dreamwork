"""Narrow tests for `dev/occur.py` — the occurrence counter that replaces ``grep -c``.

Selection is NARROW on purpose (#916).  Four tests cover the load-bearing
behaviour only: the count is OCCURRENCES not LINES (the #946 defect), the
non-overlapping contract is stated (direction 2), the denominator is loud at
zero (#868), and the CLI's discrepancy NOTE names both numbers.

Every expectation is derived from HAND-ENUMERATION, not from the helper's own
output (#906): the fixture's counts are stated as constants the author placed,
and the overlapping-count expectation is derived by counting match positions by
hand, not from any ``count`` function — so the test cannot agree with itself
(#852/#905/#909).
"""

from __future__ import annotations

from pathlib import Path

from dev import occur


# A hand-written fixture replicating the #946 discriminating structure: ONE line
# holds TWO needles, so the line count (3) and the occurrence count (4) differ.
# This is the real shape of `.dreamwork/docs/briefs/551-posture-remind.md` line
# 21 (`watch.py:5489-5502 @ dc739001; ... watch.py:5760-5768 @ dc739001)`),
# reproduced here so the test is independent of corpus drift (#906).  The author
# placed exactly 4 occurrences across 3 lines — the expectation of 4 derives
# from that placement, not from the helper.
NEEDLE = "dc739001"
TWO_PINS_ONE_LINE = (
    "see `watch.py:5489-5502 @ dc739001` and `watch.py:5760-5768 @ dc739001`.\n"
    "also `watch.py:4063 @ dc739001` is a neighbour.\n"
    "and `watch.py:5504-5520 @ dc739001` too.\n"
)
# Hand-enumerated: 4 occurrences, 3 matching lines (line 1 holds two pins).
EXPECTED_OCCURRENCES = 4
EXPECTED_LINES_MATCHED = 3


def test_count_reports_occurrences_not_lines(tmp_path):
    """The count is OCCURRENCES, not matching lines — the #946 defect.

    Expectation source: the fixture is hand-written with exactly 4 needles on 3
    lines (line 1 carries two).  A line-counting implementation (``grep -c``
    semantics) returns 3; the occurrence count is 4.  Asserting 4 discriminates
    the two.  This is direction 1.
    """
    f = tmp_path / "doc.md"
    f.write_text(TWO_PINS_ONE_LINE)
    tally = occur.scan([f], NEEDLE)
    assert tally.occurrences == EXPECTED_OCCURRENCES, (
        f"expected {EXPECTED_OCCURRENCES} occurrences (hand-counted), "
        f"saw {tally.occurrences} — a line count would report {EXPECTED_LINES_MATCHED} (#946)"
    )
    assert tally.lines_matched == EXPECTED_LINES_MATCHED, (
        f"expected {EXPECTED_LINES_MATCHED} matching lines, saw {tally.lines_matched}"
    )
    # The gap IS the defect: occurrences != lines_matched exactly when a line
    # holds 2+ matches.  Asserting the inequality pins that the helper exposes
    # the discrepancy rather than collapsing it to one number.
    assert tally.occurrences > tally.lines_matched


def test_count_is_non_overlapping_the_stated_direction_2_limit():
    """Non-overlapping count: ``"aaaa"`` / ``"aa"`` -> 2, not 3.

    Direction 2 (the sharp one): the helper reports 2, which is CORRECT for
    non-overlapping semantics — but a caller who wanted OVERLAPPING matches (3)
    draws the wrong conclusion.  This is a stated, unclosed limitation: the
    helper matches ``grep -o | wc -l``, ``re.findall`` and ``str.count``, and a
    caller needing overlapping counts wants a different tool.

    Expectation source: hand-enumeration of match positions in ``"aaaa"``.
    Non-overlapping: positions (0-1) and (2-3) = 2.  Overlapping would also
    count (1-2) = 3.  The expectation of 2 is derived from that enumeration,
    NOT from ``str.count`` (which the helper calls for literals — using it as
    the oracle would be the helper agreeing with itself, #852/#905/#909).
    """
    assert occur.count("aaaa", "aa") == 2, (
        "non-overlapping count of 'aa' in 'aaaa' must be 2 (positions 0-1, 2-3); "
        "3 would be the overlapping count, which this helper does not provide"
    )
    # A compiled regex takes the same non-overlapping path (re.finditer), so the
    # contract is consistent across needle kinds — no second semantics beside it.
    import re

    assert occur.count("aaaa", re.compile("aa")) == 2


def test_scan_denominator_is_loud_at_zero_files(capsys):
    """files_examined=0 must exit 2 — a scan that matched no files is broken (#868, #943).

    A scan that examined nothing and a scan that found nothing must not print
    the same sentence.  The denominator (files_examined) is the one number that
    tells them apart.
    """
    rc = occur.main([NEEDLE, "/no/such/path/that/does/not/exist-946"])
    assert rc == 2, "a scan that examined zero files must exit 2 (loud vacuity)"
    err = capsys.readouterr().err
    assert "files_examined=0" in err


def test_cli_note_names_both_numbers_when_counts_differ(tmp_path, capsys):
    """The discrepancy NOTE must print both numbers, not a literal ``{...}``.

    Guards the f-string bug the helper shipped for one run: the NOTE's third
    line was not an f-string, so it printed the literal ``{tally.lines_matched}``
    instead of the value.  A reader relying on the NOTE to see what ``grep -c``
    would report would have seen a template token, not a number.
    """
    f = tmp_path / "doc.md"
    f.write_text(TWO_PINS_ONE_LINE)
    assert occur.main([NEEDLE, str(f)]) == 0
    out = capsys.readouterr().out
    assert f"occurrences={EXPECTED_OCCURRENCES}" in out
    assert f"lines_matched={EXPECTED_LINES_MATCHED}" in out
    # The NOTE must name the grep -c value as a NUMBER, and must not carry an
    # unresolved ``{tally.lines_matched}`` template token.
    assert "would report 3 here" in out
    assert "{tally.lines_matched}" not in out
