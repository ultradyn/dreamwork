"""Tests for dev/ledger.py — the one supported way to fold a ledger entry (#440)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))          # repo root → import watch
sys.path.insert(0, str(Path(__file__).resolve().parent / "dev"))   # dev/       → import ledger
import ledger  # noqa: E402
import watch   # noqa: E402


# ---------------------------------------------------------------------------
# A fixture ledger whose OPEN section contains the literal string
# `## Recently landed` inside an entry's prose. That is the #440 trap: a bare
# `t.split('## Recently landed', 1)` splits at the mention, not the heading,
# and it has corrupted this file twice. The fixture deliberately also carries
# the mention inside the very entry being folded, so the trap is exercised on
# the move path itself.
# ---------------------------------------------------------------------------
LEDGER_FIXTURE = """\
# Task ledger

Next id: **4**

## Open
- **#1** — do the thing · P1 · origin: **loop**
  · the prose below names the other section's heading verbatim:
  · note how `## Recently landed` appears here as a code reference, not a
  · heading — an unanchored split lands on THIS line, not the real one
- **#2** — fold me · origin: **loop**
  · a continuation line with a sibling reference: see **#1**
- **#3/#4** — a combined open head · origin: **loop**

## Recently landed

- **#5** — already done · origin: **loop** · landed `deadbea`
"""


def _open_body_anchored(text):
    """The real Open section body, via the production anchored headings."""
    o = watch.LEDGER_SEC_OPEN.search(text)
    l = watch.LEDGER_SEC_LANDED.search(text)
    return text[o.end():l.start()]


def _landed_body_anchored(text):
    l = watch.LEDGER_SEC_LANDED.search(text)
    return text[l.end():]


# ---------------------------------------------------------------------------
# the trap itself — derived and asserted, so the fold test can't go hollow
# ---------------------------------------------------------------------------

def test_the_fixture_actually_contains_the_prose_mention_trap():
    # If somebody edits the fixture and drops the prose mention, this fails
    # loudly — and without it the fold test below would prove nothing about
    # the trap. Derived at runtime from the real anchored open section, never
    # assumed.
    open_body = _open_body_anchored(LEDGER_FIXTURE)
    assert "## Recently landed" in open_body


def test_a_naive_unanchored_split_lands_on_the_prose_mention():
    # The bug, stated as a test: the FIRST occurrence of the heading text in
    # the whole file is the prose mention, so `split(..., 1)[0]` (the bogus
    # "open half") stops short of the real heading. This is the failure mode
    # the tool exists to make impossible, and it is present in the fixture.
    before, after = LEDGER_FIXTURE.split("## Recently landed", 1)
    # the prose mention lives inside #1's body, so the bogus open half does
    # NOT contain the whole open section (it is missing #2 and #3/#4)…
    assert "#2" not in before.split("## Open", 1)[1]
    # …and the bogus landed half begins MID-PROSE inside #1 — the mention sits
    # inside backticks, so the split lands on the closing backtick, not on a
    # heading line or an entry head. That is the corruption surface.
    assert after.lstrip().startswith("`"), "naive split did not land inside #1's prose"


# ---------------------------------------------------------------------------
# fold — the entry lands in the REAL landed section, headings stay unique
# ---------------------------------------------------------------------------

def test_fold_moves_the_entry_into_the_real_landed_section():
    text = LEDGER_FIXTURE
    assert "## Recently landed" in _open_body_anchored(text)  # trap present (precondition)

    result = ledger.fold(text, 2, "folded by the tool")

    # exactly one of each heading, anchored — the invariant both incidents broke
    assert len(watch.LEDGER_SEC_OPEN.findall(result)) == 1
    assert len(watch.LEDGER_SEC_LANDED.findall(result)) == 1

    # the moved entry is at the TOP of the REAL landed section, with the note
    landed = _landed_body_anchored(result)
    assert landed.lstrip().startswith("- **#2** — fold me")
    assert "  · folded by the tool\n" in landed

    # production parser agrees: #2 is now landed, not open
    open_ids, landed_ids = watch.parse_ledger(result)
    assert "2" in landed_ids and "2" not in open_ids

    # #1 (which carries the prose mention) stays in Open, unchanged, and its
    # mention survives — the tool did not touch what it did not move
    open_body = _open_body_anchored(result)
    assert "- **#1** — do the thing" in open_body
    assert "## Recently landed" in open_body  # the prose mention is intact


def test_fold_preserves_the_moved_block_byte_exact_apart_from_the_note():
    text = LEDGER_FIXTURE
    before_block = (
        "- **#2** — fold me · origin: **loop**\n"
        "  · a continuation line with a sibling reference: see **#1**"
    )
    assert before_block in text  # precondition: the block looks like this

    result = ledger.fold(text, 2, "the note")
    # the original content lines survive verbatim, with the note appended after
    assert before_block in result
    landed = _landed_body_anchored(result)
    assert before_block + "\n  · the note" in landed


def test_fold_into_a_fixture_whose_only_open_entry_is_the_one_mentioning_the_heading():
    # The crux from the live ledger: the entry being folded can ITSELF be the
    # one carrying the prose mention. A naive split would have no well-formed
    # open section left at all.
    text = (
        "# Task ledger\n\nNext id: **2**\n\n## Open\n"
        "- **#1** — fold me · origin: **loop**\n"
        "  · this body quotes `## Recently landed` in prose, then more detail\n"
        "  · second continuation line\n\n"
        "## Recently landed\n\n"
        "- **#2** — done · landed `cafe` \n"
    )
    assert "## Recently landed" in _open_body_anchored(text)  # trap present

    result = ledger.fold(text, 1, "moved")
    assert len(watch.LEDGER_SEC_OPEN.findall(result)) == 1
    assert len(watch.LEDGER_SEC_LANDED.findall(result)) == 1
    landed = _landed_body_anchored(result)
    assert landed.lstrip().startswith("- **#1** — fold me")
    assert "  · moved\n" in landed
    # the prose mention travelled with the entry and did not duplicate a heading
    assert "## Recently landed" in landed  # still prose, still exactly one heading total
    open_ids, landed_ids = watch.parse_ledger(result)
    assert "1" in landed_ids and "1" not in open_ids


# ---------------------------------------------------------------------------
# refusals — fold must refuse, not guess
# ---------------------------------------------------------------------------

def test_fold_refuses_an_unknown_id():
    try:
        ledger.fold(LEDGER_FIXTURE, 999, "nope")
    except ledger.LedgerError as e:
        assert "unknown id" in str(e)
        assert "999" in str(e)
    else:
        assert False, "expected LedgerError for an unknown id"


def test_fold_refuses_an_id_already_in_landed():
    # #5 is under ## Recently landed in the fixture
    try:
        ledger.fold(LEDGER_FIXTURE, 5, "nope")
    except ledger.LedgerError as e:
        assert "already under" in str(e) or "already in" in str(e)
        assert "5" in str(e)
    else:
        assert False, "expected LedgerError for an id already landed"


def test_fold_refuses_an_id_matching_more_than_one_open_entry():
    # Duplicate id in Open is itself a ledger bug, but the tool must refuse
    # rather than pick one. parse_ledger still reports the id as open (a set),
    # so the refusal has to come from the head scan.
    dup = (
        "# Task ledger\n\nNext id: **3**\n\n## Open\n"
        "- **#1** — first · origin: **loop**\n\n"
        "- **#1** — second (same id) · origin: **loop**\n\n"
        "## Recently landed\n\n- **#2** — done · landed `ab` \n"
    )
    try:
        ledger.fold(dup, 1, "nope")
    except ledger.LedgerError as e:
        assert "matches 2" in str(e) or "not unique" in str(e)
    else:
        assert False, "expected LedgerError for an ambiguous id"


def test_fold_refuses_a_text_with_a_missing_or_duplicate_heading():
    # The anti-corruption guard fires on INPUT too: a file already broken is
    # never silently "repaired" by a fold.
    no_open = LEDGER_FIXTURE.replace("## Open", "## Something Else", 1)
    try:
        ledger.fold(no_open, 2, "nope")
    except ledger.LedgerError as e:
        assert "heading invariant violated" in str(e)
    else:
        assert False, "expected LedgerError for a missing ## Open heading"


# ---------------------------------------------------------------------------
# counts — the production parser's figure, with the expression
# ---------------------------------------------------------------------------

def test_counts_reads_the_production_parser_and_names_the_expression():
    out = ledger.counts_text(LEDGER_FIXTURE)
    # the fixture has open ids {1,2,3,4} and landed {5} (combined head counts both)
    open_ids, landed_ids = watch.parse_ledger(LEDGER_FIXTURE)
    assert f"open ids:   {len(open_ids)}" in out
    assert f"landed ids: {len(landed_ids)}" in out
    # the expression that produced the number is printed beside it
    assert "watch.parse_ledger(text)[0]" in out
    assert "watch.parse_ledger(text)[1]" in out


# ---------------------------------------------------------------------------
# assert_headings — the guard the two incidents were missing
# ---------------------------------------------------------------------------

def test_assert_headings_rejects_a_second_mention_only_when_it_is_a_real_heading():
    # The prose mention must NOT trip the guard (it is not a heading line).
    ledger.assert_headings(LEDGER_FIXTURE, "accepts prose mention")
    # But a real second heading line does.
    duplicated = LEDGER_FIXTURE + "## Recently landed\n\n- **#9** — dupe\n"
    try:
        ledger.assert_headings(duplicated, "dupe")
    except ledger.LedgerError as e:
        assert "2" in str(e) and "Recently landed" in str(e)
    else:
        assert False, "expected LedgerError for a duplicate heading"


# ---------------------------------------------------------------------------
# sweep (#404) — landings discoverable from git subjects, minus cited shas
#
# A lane cannot land work without committing, and this repo's convention puts
# the id in the subject by construction, so git log is the strictly more
# reliable landing channel. The sweep correlates id-bearing subjects against
# the OPEN id set and subtracts ids whose entry already cites the sha — the
# discovery twin of lint.check_landed_still_open (#323), advisory (exit 0),
# and over the full verb set because a discovery sweep tolerates weak verbs
# that a WARN may not.
# ---------------------------------------------------------------------------
from ledger_parse import ledger_entries, open_section_text  # noqa: E402

SWEEP_LEDGER = """\
# Task ledger

Next id: **13**

## Open
- **#10** — uncited landing · origin: **loop**
  · the body never names the commit that landed it
- **#11** — deliberate partial · origin: **loop**
  · landed in `abc1234`, kept open for the remaining half
- **#12** — genuinely unstarted · origin: **loop**

## Recently landed

- **#9** — already folded · origin: **loop**
"""

# (sha, subject) pairs in newest-first order, as `git log --format=%h\x1f%s`
# yields them. The verbs are the forms measured on this repo's own log.
SWEEP_COMMITS = [
    ("fff0001", "docs(#404): unrelated churn, not a landing candidate verb for #10"),
    ("def5678", "merge(#10,#99): the uncited landing"),
    ("abc1234", "fix(#11): the deliberate partial"),
    ("eee0002", "guard(#9): already folded, must not be reported"),
    ("ddd0003", "no id in this subject at all"),
]


def _sweep_open_body(tid):
    """Entry body for `tid` via the production helpers the sweep reuses."""
    for ids, body in ledger_entries(open_section_text(SWEEP_LEDGER)):
        if tid in ids:
            return body
    raise AssertionError(f"#{tid} has no open entry in the fixture")


def test_sweep_fixture_preconditions_derived_at_runtime():
    # The gap the whole sweep rests on must EXIST in the fixture, derived —
    # never assumed — or the report test below proves nothing.
    open_ids, landed_ids = watch.parse_ledger(SWEEP_LEDGER)
    assert "10" in open_ids and "11" in open_ids and "9" not in open_ids
    assert "9" in landed_ids
    # #10's landing sha is NOT cited in its entry — this is the gap itself
    assert "def5678" not in _sweep_open_body(10)
    # #11's IS — the subtraction case would be hollow without this contrast
    assert "abc1234" in _sweep_open_body(11)
    # and the multi-id subject really does carry two ids (the fixture's claim)
    assert ledger.SWEEP_SUBJECT.match("merge(#10,#99): x").group(1) == "#10,#99"


def test_sweep_reports_the_uncited_open_landing_with_its_sha():
    n, findings = ledger.sweep(SWEEP_LEDGER, SWEEP_COMMITS)
    by_id = {tid: shas for tid, shas in findings}
    assert 10 in by_id
    assert any(sha == "def5678" for sha, _ in by_id[10])


def test_sweep_subtracts_entries_that_cite_the_sha():
    _, findings = ledger.sweep(SWEEP_LEDGER, SWEEP_COMMITS)
    assert 11 not in {tid for tid, _ in findings}


def test_sweep_ignores_landed_ids_and_reports_multi_id_subjects():
    _, findings = ledger.sweep(SWEEP_LEDGER, SWEEP_COMMITS)
    by_id = {tid for tid, _ in findings}
    assert 9 not in by_id        # already under ## Recently landed
    assert 99 not in by_id       # second id of merge(#10,#99) — not in the ledger


def test_sweep_counts_every_commit_examined_even_with_no_findings():
    # The count is what distinguishes "found nothing" from "did not run".
    n, findings = ledger.sweep(SWEEP_LEDGER, SWEEP_COMMITS)
    assert n == len(SWEEP_COMMITS)  # non-matching subjects are examined too
    n0, findings0 = ledger.sweep(SWEEP_LEDGER, SWEEP_COMMITS[4:])
    assert n0 == 1 and findings0 == []
