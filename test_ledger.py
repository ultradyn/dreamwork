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


# ---------------------------------------------------------------------------
# #707 — the widening. SWEEP_SUBJECT previously matched ONLY verb(#N); every
# coordinator `Merge #N:` and every bare lane `#N:` commit was invisible to
# the tool whose job is discovering landings. The widening adds Merge/Fold and
# bare-#N forms; the report splits them into a lower-confidence class. These
# pure-function tests pin the PATTERN widening; the report split is in
# test_ledger_cli.py.
#
# The fixture SWEEP_LEDGER holds #10 and #11 OPEN; SWEEP_COMMITS uses the
# verb(#N) form. The widened-form tests below use the SAME open ids so the
# contrast is real: the same landing, two subject shapes, one visible today
# and one not.
# ---------------------------------------------------------------------------

def test_sweep_subject_widened_to_match_the_coordinator_merge_form():
    """DIRECTION-1 measurement, fixture not live repo (#707 brief).

    `Merge #688: branch-level reachability` is the commit form EVERY
    coordinator landing takes, and the #707 brief measured it MISSED today.
    PRODUCTION LINE: the Merge/Fold alternative in SWEEP_SUBJECT.
    RED on the un-widened pattern: this returns None.
    """
    assert ledger.SWEEP_SUBJECT.match("Merge #10: branch-level reachability"), (
        "the coordinator merge form — every landing this loop records — must "
        "now match; #707 measured it invisible")
    # group(1) is the verb(#N) capture; Merge/Fold land in their own group, so
    # the id is reachable via the non-None group, not a literal group(1).
    m = ledger.SWEEP_SUBJECT.match("Merge #10: x")
    groups = [g for g in m.groups() if g]
    assert groups == ["#10"], f"the id must be capturable from the widened form: {m.groups()!r}"


def test_sweep_subject_widened_to_match_the_bare_lane_form():
    """The form the #705 boilerplate mistakenly codified for ~30 minutes.

    `#10: a landing` and `#10 — a landing` are the bare lane forms. A
    SEPARATOR is required (colon, space, em-dash) so a bare id floating in
    prose at the head of a non-landing subject does not match.
    PRODUCTION LINE: the bare-id alternative in SWEEP_SUBJECT.
    """
    for subj in ["#10: the gate is a file", "#10 — sweep pattern", "#10 skip collision test"]:
        m = ledger.SWEEP_SUBJECT.match(subj)
        assert m is not None, f"bare lane form must match: {subj!r}"
        assert "#10" in [g for g in m.groups() if g]
    # a bare id with NO separator is not a landing subject — it is a token.
    assert ledger.SWEEP_SUBJECT.match("#10foo") is None, (
        "a separator after the bare id is required, or any #N token matches")


def test_sweep_finds_a_merge_prefixed_landing_it_previously_missed():
    """DIRECTION-1 red: the real gap, fixture not live repo.

    A `Merge #10:` commit where #10 is OPEN and its entry does not cite the
    sha is a TRUE finding today (the coordinator merged but the fold didn't
    happen) — and it is the form that has been invisible since the store
    cutover. Pre-widening this returned no finding for #10.
    PRODUCTION LINE: the widened SWEEP_SUBJECT + the `for tid in ...` loop in
    `sweep`. RED: drop the Merge alternative and #10 vanishes from findings.
    """
    commits = [("bbb0001", "Merge #10: branch-level reachability")]
    n, findings = ledger.sweep(SWEEP_LEDGER, commits)
    by_id = {tid: shas for tid, shas in findings}
    assert 10 in by_id, (
        "a Merge #10: landing for an open id whose entry does not cite the sha "
        "must now be found — #707 measured this class invisible")
    assert any(sha == "bbb0001" for sha, _ in by_id[10])


def test_sweep_finds_a_bare_lane_landing_it_previously_missed():
    """The bare form a lane actually writes when the boilerplate waversed.

    PRODUCTION LINE: the bare-#N alternative in SWEEP_SUBJECT. RED: drop it
    and #10 is not found.
    """
    commits = [("ccc0001", "#10: a lane commit in the bare form")]
    n, findings = ledger.sweep(SWEEP_LEDGER, commits)
    assert 10 in {tid for tid, _ in findings}, (
        "the bare #N: form must now be found, not silently skipped as 'bare-#N'")


def test_sweep_still_subtracts_cited_shas_for_widened_forms():
    """The subtraction convention (#404: cite the sha, the row disappears)
    must hold for the WIDENED forms too, or widening floods the report with
    already-reconciled merge commits.

    PRECONDITION (not an assumption): the Merge form must actually MATCH after
    widening, or this test is hollow — it would pass today against the
    un-widened pattern because the subject never matched at all (#707's own
    "green red-run is a finding" trap). Asserting the match here is what makes
    the subtraction assertion non-vacuous.

    PRODUCTION LINE: `if sha in bodies.get(tid, ""): continue` in `sweep`,
    now reached with Merge/bare subjects. RED: drop the `continue` and the
    merge commit citing its sha would be named.
    """
    # #11 cites abc1234 in the fixture body; a Merge #11: form must subtract.
    subj = "Merge #11: branch-level reachability"
    # The precondition that makes the subtraction assertion non-vacuous:
    assert ledger.SWEEP_SUBJECT.match(subj) is not None, (
        "precondition: the Merge form must match post-widening, else this "
        "test is hollow — it passes when nothing matched at all")
    assert "abc1234" in _sweep_open_body(11), (
        "precondition: #11's body must cite the sha the merge commit carries")
    commits = [("abc1234", subj)]
    _, findings = ledger.sweep(SWEEP_LEDGER, commits)
    assert 11 not in {tid for tid, _ in findings}, (
        "a Merge #11: whose entry cites the sha must be subtracted, or "
        "widening re-proposes every reconciled merge")


# ---------------------------------------------------------------------------
# #688 — reach(): the pure function that collapses duplicate sha sets and
# reports only branches with at least one + commit. The integration path
# (git cherry, fold hook) is in test_ledger_reach.py; these pin the
# collapsing/filter logic against synthetic marks, so a regression in the
# algorithm is caught independently of git's patch-id behaviour.
#
# Mark grammar: (marker, sha, subject) where marker is '+' (not
# patch-equivalent) or '-' (patch-equivalent, strong evidence it's on base).
# ---------------------------------------------------------------------------

def _reach_marks():
    """A synthetic branch set exercising the three cases that matter.

    - ``live-work``: one + commit, one - commit  → reported (the gap)
    - ``cherry-picked``: only - commits          → NOT reported (already on base)
    - ``pi-agent-aaa``: same shas as ``live-work`` → collapsed into an alias
    - ``scratch-only``: one + commit, unique shas → reported (its own row)
    """
    return [
        ("live-work", [("+", "aaa111", "fix(#42): a real change"),
                       ("-", "bbb222", "")]),
        ("cherry-picked", [("-", "ccc333", "")]),
        ("pi-agent-aaa", [("+", "aaa111", "fix(#42): a real change"),
                          ("-", "bbb222", "")]),
        ("scratch-only", [("+", "ddd444", "wip: experiment")]),
    ]


def test_reach_reports_only_branches_with_a_plus_commit():
    n, sup, rows = ledger.reach(_reach_marks())
    names = {b for b, _, _ in rows}
    assert "live-work" in names, "a + commit must surface the branch"
    assert "scratch-only" in names
    assert "cherry-picked" not in names, (
        "a branch with only - commits (all on base) must NOT be reported — "
        "that is #676 finding 2's strong-evidence side")


def test_reach_collapses_duplicate_sha_sets_into_one_row():
    n, sup, rows = ledger.reach(_reach_marks())
    by_name = {b: (aliases, plus) for b, aliases, plus in rows}
    # pi-agent-aaa shares live-work's sha set → alias, not a separate row
    assert "pi-agent-aaa" not in by_name, (
        "a duplicate sha set must collapse (#676 finding 3), not get its own row")
    assert "pi-agent-aaa" in by_name["live-work"][0], (
        "and it must be named as an alias of the surviving row")
    assert sup == 1, (
        f"one duplicate was suppressed; got {sup} — the count lets the report "
        f"say how many were hidden, not just that some were (#671)")


def test_reach_counts_every_branch_examined_so_did_not_run_is_distinguishable():
    marks = _reach_marks()
    n, sup, rows = ledger.reach(marks)
    assert n == len(marks), (
        "n_examined must count EVERY branch, so 'found nothing' differs from "
        "'did not run' (#404, #671 — the same contract sweep carries)")


def test_reach_text_always_prints_the_examined_count():
    """PRODUCTION LINE: the `examined N branches` clause in reach_text's header.
    RED: drop it and the header no longer carries the count, so a reach that
    enumerated nothing reads as a clean result (#671, #404's trap)."""
    text = ledger.reach_text(_reach_marks(), "master")
    assert "examined 4 branches" in text, (
        f"the examined count must be in the header: {text!r}")
    # A + is a question, never a verdict (#590, #676 finding 2)
    assert "a + is a question, not a verdict" in text, (
        f"the closing line must not promote a + to a verdict: {text!r}")


def test_reach_text_clean_result_differs_from_could_not_check():
    """#404's ruled contract carried one layer in (#671): a clean report and a
    cannot-check must not render identically. The clean path says 'nothing to
    review (this ran)'; an empty branch list is handled by the CLI layer."""
    marks = [("branch-x", [("-", "aaa", "")])]  # only - commits → no rows
    text = ledger.reach_text(marks, "master")
    assert "nothing to review (this ran" in text, (
        f"a clean result must name itself as having run: {text!r}")
    assert "examined 1 branches" in text


# ---------------------------------------------------------------------------
# #681 — the store-mode `file` verb surfaces a bad enum as one-line stderr +
# exit 2, not a bare sqlite traceback. file_task (ledger_write) does the
# validation; _file_store (here) is the catch that turns WriteError into the
# #667-style refusal. PRODUCTION LINE: _file_store's `except WriteError`.
# ---------------------------------------------------------------------------

def test_file_store_bad_priority_is_exit2_stderr_no_traceback(tmp_path, capsys):
    # Seed a real store so _file_store can open it and reach file_task.
    sp = ledger.store_path(str(tmp_path))
    ledger.ledger_store.open_store(sp, seed_next_id=1).close()
    # priority '3' is not in priority_band — derive that at runtime.
    bands = ledger.ledger_store.PRIORITY_BANDS
    assert "3" not in bands, "precondition: '3' must not be a real band"

    rc = ledger._file_store(str(tmp_path), "a title", "a body", "3", None, None)

    assert rc == 2, f"a bad priority must exit 2, not {rc}"
    err = capsys.readouterr().err
    assert "priority: got '3'" in err and "expected one of" in err, err
    assert "Traceback" not in err, "a bad enum must not dump a traceback"
    # Nothing was filed.
    assert sp.exists()


# ---------------------------------------------------------------------------
# #714 — _default_since: the window bound for `sweep`. It finds the most
# recent fold commit. The repo's convention MOVED from lowercase `fold #NNN:`
# to capital `Fold #NNN` mid-history, and the match was case-sensitive
# `^fold ` — so every capital `Fold` (the current convention, 47 measured on
# master) anchored out of the window, leaving it ~555 commits wide instead of
# ~63. A second defect the measurement surfaced: `git log --grep` searches the
# BODY too, so a body line starting `fold` would narrow the window past real
# landings (the dangerous direction for an advisory tool).
#
# These build a bare git repo (`_default_since` only shells out to git — no
# ledger/store needed) and assert on the BOUNDARY sha, not a width count: a
# base wrong-by-one passes a width test, which is the brief's direction-1 trap.
# ---------------------------------------------------------------------------
import subprocess  # noqa: E402


def _git(root, *a):
    return subprocess.run(["git", "-C", str(root), *a],
                          capture_output=True, text=True, check=True)


def _bare_repo(tmp_path, name="r"):
    """A git repo with identity, no commits yet."""
    root = tmp_path / name
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    return root


def _commit(root, subject, body=None):
    """Empty commit; returns the FULL sha (`_default_since` returns %H)."""
    args = ["commit", "-q", "--allow-empty", "-m", subject]
    if body is not None:
        args += ["-m", body]
    _git(root, *args)
    return _git(root, "rev-parse", "HEAD").stdout.strip()


def test_default_since_reads_the_capital_fold_form_the_convention_now_uses(tmp_path):
    """DIRECTION-1 red: the measured defect, fixture not live repo.

    `Fold #674 (merged ...)` is the form EVERY recent fold takes (47 measured
    on master); the case-sensitive `^fold ` anchored all of them out of the
    window. PRODUCTION LINE: the subject match in `_default_since`. RED on the
    un-fixed matcher: this returns None (no lowercase `fold ` subject exists),
    so the window opens at None — full-history scan instead of since the fold.
    """
    root = _bare_repo(tmp_path)
    _commit(root, "fold #1: old-style lowercase fold")
    capital = _commit(root, "Fold #2 (merged abc1234)")  # the current convention
    assert ledger._default_since(root) == capital, (
        "the capital `Fold #N` form — the repo's current convention — must be "
        "the window bound; #714 measured 47 of these anchored out by a "
        "case-sensitive `^fold ` that could only read the extinct lowercase form")


def test_default_since_still_reads_the_old_lowercase_fold_form(tmp_path):
    """The convention moved from lowercase to capital mid-history; both are
    real folds and both must bound the window when they are the most recent.
    PRODUCTION LINE: the matcher in `_default_since`. A fix that ONLY added
    capital `Fold` and dropped lowercase `fold` would re-break old history.
    """
    root = _bare_repo(tmp_path)
    _commit(root, "Fold #2 (merged abc1234)")
    lower = _commit(root, "fold #1: old-style lowercase fold")
    assert ledger._default_since(root) == lower, (
        "lowercase `fold #N:` is the extinct-but-real form; a matcher that "
        "dropped it would open the window too wide on repos whose last fold "
        "was lowercase")


def test_default_since_does_not_match_a_fold_verb_lane_commit(tmp_path):
    """The space after `fold` is load-bearing: `fold(#260):` is a LANE commit
    (the `fold` verb writing a Folded line), not a reconciliation fold. Matching
    it would narrow the window to a lane commit and hide later landings — the
    dangerous direction. Measured on master: ~10 such commits, all older than
    the recent real fold today, but the tie goes to breadth.
    PRODUCTION LINE: the trailing space in the fold matcher.
    """
    root = _bare_repo(tmp_path)
    real = _commit(root, "Fold #2 (merged abc1234)")
    _commit(root, "fold(#260): Folded line — witness-audit merged")
    assert ledger._default_since(root) == real, (
        "`fold(#N):` is a lane verb, not a reconciliation fold; matching it "
        "narrows the window to a lane commit and hides landings after it")


def test_default_since_ignores_a_body_line_starting_fold(tmp_path):
    """DIRECTION-2 red: the case the naive case-insensitive `--grep` fix gets
    WRONG. `git log --grep` searches the body, so a commit whose SUBJECT is not
    a fold but whose BODY starts with `fold` would become the window bound —
    narrowing past real landings. Measured on master: `feat(#294)`'s body opens
    `fold dispatches on source_of_truth:`. A subject-anchored match refuses it.
    PRODUCTION LINE: subject anchoring in `_default_since`. RED on a `--grep`
    implementation (case-insensitive or not): the body line matches and the
    bound jumps to the non-fold commit.
    """
    root = _bare_repo(tmp_path)
    fold = _commit(root, "Fold #2 (merged abc1234)")
    # a lane commit whose BODY (not subject) happens to start with "fold"
    _commit(root, "feat(#294): re-point writes",
            body="fold dispatches on source_of_truth: store -> land")
    assert ledger._default_since(root) == fold, (
        "a body line starting `fold` must not narrow the window past the real "
        "fold — `git log --grep` reads the body and would make this non-fold "
        "commit the bound, hiding every landing between it and the next fold")


def test_default_since_returns_none_when_no_fold_exists(tmp_path):
    """A repo with no fold commit at all. Returning None opens the window to
    full history (maximal scanning — the safe direction); silently scanning
    everything without saying so is a separate concern (#671), but the BOUND
    itself must be None, not a guess. The brief named this case explicitly.
    """
    root = _bare_repo(tmp_path)
    _commit(root, "feat(#1): first commit")
    _commit(root, "fix(#2): second commit")
    assert ledger._default_since(root) is None, (
        "no fold commit means no bound — None opens full-history scanning, "
        "which is the safe direction for an advisory tool")

