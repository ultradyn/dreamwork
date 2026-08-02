"""Tests for dev/ledger.py — the one supported way to fold a ledger entry (#440)."""
import sys
from pathlib import Path

import pytest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))          # repo root → import watch
sys.path.insert(0, str(Path(__file__).resolve().parent / "dev"))   # dev/       → import ledger
import ledger  # noqa: E402
import ledger_write  # noqa: E402  — for filing a blocked task in #627 CLI tests
import watch   # noqa: E402


def test_fold_citation_refusal_names_the_presquash_tag_remedy(monkeypatch):
    """An off-base commit remains refused, but no longer teaches deletion."""
    token = "866eb584"
    commit = token + "0" * 32
    base_commit = "a" * 40
    monkeypatch.setattr(
        ledger, "_git_resolve_commit",
        lambda _repo, revision: {token: commit, "master": base_commit}.get(revision))
    monkeypatch.setattr(ledger, "_git_is_ancestor", lambda *_args: False)

    report, unreachable, cannot_judge = ledger._fold_citation_check(
        ".", f"squashed pre-merge tip {token}", "master")

    assert unreachable == [(token, commit)] and cannot_judge == []
    assert f"REFUSE {token} resolves as commit {commit}" in report
    assert "NOT an ancestor of master" in report
    assert "cite the preservation tag <branch>-presquash instead" in report
    assert "it is a ref and will not be collected" in report
    assert "examined 1 token(s); could not judge 0 token(s)" in report


def test_fold_cli_refusal_names_the_presquash_tag_remedy(
        tmp_path, monkeypatch, capsys):
    token = "866eb584"
    commit = token + "0" * 32
    ledger_path = tmp_path / "tasks.md"
    ledger_path.write_text(LEDGER_FIXTURE)
    monkeypatch.setattr(
        ledger, "_fold_citation_check",
        lambda *_args: ("citation report\n", [(token, commit)], []))

    rc = ledger.main([
        "fold", "2", "--note", f"squashed pre-merge tip {token}",
        "--ledger", str(ledger_path)])
    captured = capsys.readouterr()

    assert rc == 2
    assert f"{token} exists but is NOT an ancestor of master" in captured.err
    assert "cite the preservation tag <branch>-presquash instead" in captured.err
    assert "it is a ref and will not be collected" in captured.err
    assert "- **#2** — fold me" in ledger_path.read_text(), (
        "the refusal must precede the irreversible write")


def test_fold_citation_hex_english_is_unjudged_not_refused(monkeypatch):
    """`defaced` is a lexical candidate, not evidence of an off-base commit."""
    monkeypatch.setattr(ledger, "_git_resolve_commit", lambda *_args: None)

    report, unreachable, cannot_judge = ledger._fold_citation_check(
        ".", "the old surface was defaced", "master")

    assert "CHECK defaced does not resolve to a commit" in report
    assert "REFUSE defaced" not in report
    assert "examined 1 token(s); could not judge 1 token(s)" in report
    assert unreachable == [] and cannot_judge == []


def test_fold_citation_ignores_fences_and_quoted_past_refusals(monkeypatch):
    """Quoting the check's own evidence must not recursively trigger it."""
    planted = "abc1234"
    resolved = planted + "0" * 33
    seen = []

    def resolve(_repo, revision):
        seen.append(revision)
        return {planted: resolved, "master": "b" * 40}.get(revision)

    monkeypatch.setattr(ledger, "_git_resolve_commit", resolve)
    monkeypatch.setattr(ledger, "_git_is_ancestor", lambda *_args: True)
    note = (
        "actual landing abc1234\n"
        "```text\n"
        "REFUSE 866eb584 resolves as commit " + "8" * 40
        + ": it exists but is NOT an ancestor of master\n"
        "```\n"
        "I previously saw \"REFUSE 7c51c0b5 resolves as commit " + "7" * 40
        + ": it exists but is NOT an ancestor of master\", then verified "
        "abc1234 independently.\n")

    report, unreachable, cannot_judge = ledger._fold_citation_check(
        ".", note, "master")

    assert seen == [planted, "master"], (
        "only the independently planted prose citation and base may resolve; "
        f"quoted evidence leaked into the scanner: {seen!r}")
    assert "examined 1 token(s); could not judge 0 token(s)" in report
    assert unreachable == [] and cannot_judge == []


def test_fold_citation_zero_population_states_both_denominators():
    report, unreachable, cannot_judge = ledger._fold_citation_check(
        ".", "ordinary prose", "master")
    assert "examined 0 7+ hex token(s)" in report
    assert "could not judge 0 token(s)" in report
    assert "population is zero, not a clean citation sweep" in report
    assert unreachable == [] and cannot_judge == []


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

OPEN_SECTION_EMBEDDED_HEADING = """\
# Task ledger

Next id: **754**

## Open
- **#736** — body contains Markdown headings · origin: **loop**
  · prose before the heading
 ## What to build
  · this is still #736's body
 ## Recently landed
  · this literal heading text is still #736's body too
- **#753** — last open entry must stay visible · origin: **loop**
  · cites `e6e44ddc` and `96e47397`

## Recently landed

- **#735** — already folded · origin: **loop**
"""


def test_open_section_keeps_the_last_entry_after_an_indented_body_heading():
    """#753: an indented body heading is content, not a section boundary."""
    assert " ## What to build" in OPEN_SECTION_EMBEDDED_HEADING, (
        "precondition: the fixture must carry the store projection's indented "
        "body-heading shape")
    assert " ## Recently landed" in OPEN_SECTION_EMBEDDED_HEADING, (
        "precondition: the fixture must quote a section name inside a body")

    section = open_section_text(OPEN_SECTION_EMBEDDED_HEADING)
    parsed_ids = {
        tid for ids, _body in ledger_entries(section) for tid in ids
    }
    assert 753 in parsed_ids, (
        "#753, the fixture's last open entry, disappeared after #736's "
        "indented `## What to build` body heading")


def test_open_section_tolerates_trailing_whitespace_on_its_heading():
    """#753: column-0 anchoring must not make the heading byte-exact."""
    trailing_space = OPEN_SECTION_EMBEDDED_HEADING.replace(
        "## Open\n", "## Open \n", 1)

    expected = open_section_text(OPEN_SECTION_EMBEDDED_HEADING)
    actual = open_section_text(trailing_space)

    assert actual == expected, (
        "a trailing space on the column-0 `## Open` heading hid the entire "
        "Open section")


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


def test_sweep_refuses_when_the_open_and_body_projections_disagree():
    """#753: a second parser failure must not render as an all-clear."""
    starved = """\
# Task ledger

## Open
- **#1** — canonical entry · origin: **loop**
column-zero prose starves #1's body here
- **stage #2** — malformed head only ledger_entries accepts

## Recently landed
"""
    open_ids, _ = watch.parse_ledger(starved)
    body_ids = {
        tid for ids, _body in ledger_entries(open_section_text(starved) or "")
        for tid in ids
    }
    assert open_ids == {"1"} and body_ids == {1, 2}, (
        "precondition: the independent readers must disagree for a non-heading "
        "parser reason")

    out = ledger.sweep_text(starved, [], "", "markdown")

    assert "DID NOT REVIEW" in out, (
        f"sweep reported a verdict despite disagreeing projections: {out!r}")
    assert "1 unexpected parsed body id(s): #2" in out, (
        f"the refusal must name the entry it cannot classify: {out!r}")
    assert "nothing to review" not in out, (
        f"projection blindness must not render like a clean sweep: {out!r}")


# ---------------------------------------------------------------------------
# #724 — a citation and a commit sha name the SAME object at different widths.
# git's `%h` abbreviates at a length that GROWS with the repo, so a 7-char
# citation correct when written rots to 8 later; the substring check #404
# codified misses, and the entry is re-flagged forever despite citing the sha
# it is flagged for. Resolution (`git rev-parse`: 58e3040 IS 58e3040d to git)
# is immune to that rot; width-matching re-breaks next year. The fix keeps
# `sweep` pure by accepting a `cites(sha, body) -> bool` callable: the default
# is the substring check (every existing test still passes unchanged), and a
# resolution-backed predicate is built in `sweep_text` from the small set of
# shas that FAIL substring, batched through one `git cat-file --batch-check`.
# ---------------------------------------------------------------------------

def test_sweep_cites_param_defaults_to_substring_so_existing_tests_hold():
    """The `cites` param is optional and defaults to the #404 substring check.

    PRODUCTION LINE: `_cites = cites if cites is not None else (lambda sha,
    body: sha in body)` in `sweep`. RED: drop the default and the two-arg call
    below raises TypeError.
    """
    # same fixture, same commits — the default must reproduce #404's behaviour
    n, findings = ledger.sweep(SWEEP_LEDGER, SWEEP_COMMITS)
    assert 11 not in {tid for tid, _ in findings}, (
        "default cites must still subtract #11 (abc1234 in its body)")


def test_sweep_resolution_backed_cites_reconciles_a_width_mismatch():
    """A 7-char citation in a body must reconcile an 8-char commit sha when
    the `cites` predicate resolves them to the same object id.

    This is #724's core: the body cites ``58e3040`` (7 chars, as a human wrote
    it) and git's ``%h`` yields ``58e3040d`` (8 chars) for the same commit.
    The substring check misses; a resolution-backed predicate catches it. The
    discriminating assertion NAMES the id and BOTH widths — not just a changed
    count — so a green red-run cannot hide behind a number that moved for the
    wrong reason.

    PRODUCTION LINE: `if _cites(sha, bodies.get(tid, "")): continue` in
    `sweep`. RED: pass the substring default (omit `cites`) and #465 stays
    flagged.
    """
    # #465 cites a 7-char prefix; the commit carries the 8-char form.
    short_citation = "58e3040"   # 7 chars — as written in the ledger
    commit_sha = "58e3040d"      # 8 chars — as git's %h yields it
    # PRECONDITION: the two widths must actually differ, else the test is
    # hollow — it would pass with substring alone (#655's green-red-run trap).
    assert len(short_citation) != len(commit_sha), (
        "precondition: the citation and the commit sha must be different "
        "widths, or the substring check would already match")
    assert commit_sha.startswith(short_citation), (
        "precondition: the short citation must be a prefix of the commit sha")
    # A resolution-backed cites predicate: both resolve to the same object.
    # (Simulated — the real resolver uses git cat-file --batch-check; this
    # test stays pure by mapping the known prefix to the known full sha.)
    def cites(sha, body):
        if sha in body:
            return True
        # resolve: the body's 7-char citation and the 8-char commit sha ARE
        # the same object — the resolver must compare object ids, not strings
        return short_citation in body and sha == commit_sha

    ledger_text = (
        "# Task ledger\n\nNext id: **13**\n\n## Open\n"
        "- **#465** — width-rotted citation · origin: **loop**\n"
        f"  · landed in `{short_citation}`, kept open for the remaining half\n"
        "- **#466** — genuinely uncited · origin: **loop**\n\n"
        "## Recently landed\n")
    commits = [(commit_sha, "wip(#465): the kill-recovery landing"),
               ("fff9999", "fix(#466): a genuinely uncited landing")]
    n, findings = ledger.sweep(ledger_text, commits, cites=cites)
    flagged = {tid for tid, _ in findings}
    assert 465 not in flagged, (
        f"#465 cites {short_citation} (7c) and git %h = {commit_sha} (8c) — "
        f"both resolve to the same object, so the resolution-backed cites "
        f"predicate must subtract it. Substring misses; resolution must not.")
    assert 466 in flagged, (
        "precondition: #466 genuinely does not cite its sha, so the test is "
        "not vacuous — if #466 disappears the cites predicate is over-broad")


def test_sweep_resolves_citations_in_the_repo_it_was_given(
        tmp_path, monkeypatch, capsys):
    """The resolver's subject is ``--repo``, not the process CWD (#743).

    Two independent repositories make the distinction observable: the SAME
    sha resolves in the target repo and does not resolve in the deliberately
    different CWD repo.  Merely asserting that sweep subtracts a citation is
    hollow when the test happens to run inside the target repo — the shape
    that let the bare ``git cat-file`` call through.
    """
    target = _bare_repo(tmp_path, "target")
    cwd_repo = _bare_repo(tmp_path, "cwd")
    _commit(cwd_repo, "docs: unrelated cwd history")
    target_sha = _commit(target, "fix(#465): target-repo landing")
    citation = target_sha[:7]

    target_resolves = subprocess.run(
        ["git", "-C", str(target), "cat-file", "-e",
         f"{target_sha}^{{commit}}"], capture_output=True).returncode == 0
    cwd_resolves = subprocess.run(
        ["git", "-C", str(cwd_repo), "cat-file", "-e",
         f"{target_sha}^{{commit}}"], capture_output=True).returncode == 0
    assert target_resolves is True, "precondition: the sha must resolve under --repo"
    assert cwd_resolves is False, (
        "precondition: the same sha must NOT resolve in the process CWD repo")

    ledger_path = tmp_path / "ledger" / "tasks.md"
    ledger_path.parent.mkdir()
    ledger_path.write_text(
        "# Task ledger\n\nNext id: **466**\n\n## Open\n"
        "- **#465** — target citation · origin: **loop**\n"
        f"  · landed in `{citation}`\n\n## Recently landed\n")
    # Force a width mismatch while retaining a real object for cat-file. Git's
    # normal %h is often seven chars in tiny test repos, which would take the
    # substring fast path and make this regression test vacuous.
    monkeypatch.setattr(
        ledger, "_git_subjects",
        lambda repo, since: [(target_sha, "fix(#465): target-repo landing")])
    monkeypatch.chdir(cwd_repo)

    rc = ledger.main([
        "sweep", "--repo", str(target), "--ledger", str(ledger_path)])
    out = capsys.readouterr().out

    assert rc == 0, "sweep remains advisory (#404)"
    assert "  #465 —" not in out, (
        f"#465 cites {citation}, which resolves to {target_sha} under --repo; "
        f"it must not appear as an UNCITED finding: {out!r}")
    assert "CITED-OPEN #465" in out, (
        f"resolution-backed citation is evidence, but the entry is still open: "
        f"{out!r}")


def test_sweep_merge_citation_acknowledges_each_lane_commit(tmp_path):
    """A land-lane merge sha cites the exact commits its side branch brought.

    The expected commit population comes from the two explicit ``_commit``
    results below, not from the production ``rev-list`` call (#894/#905).
    """
    root = _bare_repo(tmp_path, "merge-citation")
    _commit(root, "docs: base")
    trunk = _git(root, "symbolic-ref", "--short", "HEAD").stdout.strip()
    _git(root, "checkout", "-q", "-b", "lane-11")
    first = _commit(root, "test(#11): first lane increment")
    second = _commit(root, "feat(#11): second lane increment")
    _git(root, "checkout", "-q", trunk)
    _git(root, "merge", "-q", "--no-ff", "lane-11", "-m", "Merge lane-11")
    merge = _git(root, "rev-parse", "HEAD").stdout.strip()
    citation = merge[:8]

    ledger_text = (
        "# Task ledger\n\nNext id: **12**\n\n## Open\n"
        "- **#11** — partial landing stays open · origin: **loop**\n"
        f"  · land-lane printed merge `{citation}`\n\n"
        "## Recently landed\n")
    out = ledger.sweep_text(
        ledger_text,
        [(second, "feat(#11): second lane increment"),
         (first, "test(#11): first lane increment")],
        "base-sha", "markdown", repo=root)

    assert "  #11 —" not in out, (
        f"#11 cites merge {citation}, whose explicitly planted lane commits are "
        f"{first[:8]} and {second[:8]}; neither may remain an UNCITED finding: "
        f"{out!r}")
    assert "CITED-OPEN #11" in out, (
        f"the merge citation is evidence but does not close #11: {out!r}")
    assert "citation resolution: 1/1 cited sha(s) resolved" in out, out
    assert f"`{citation}`:2" in out, (
        f"the resolution denominator must say that {citation} yielded the two "
        f"explicitly planted lane commits: {out!r}")


def test_sweep_unrelated_merge_citation_does_not_hide_a_landing(tmp_path):
    """Direction 2: a different task's merge must not false-green #11."""
    root = _bare_repo(tmp_path, "unrelated-merge")
    _commit(root, "docs: base")
    trunk = _git(root, "symbolic-ref", "--short", "HEAD").stdout.strip()
    _git(root, "checkout", "-q", "-b", "lane-12")
    other_commit = _commit(root, "feat(#12): another task's landing")
    _git(root, "checkout", "-q", trunk)
    _git(root, "merge", "-q", "--no-ff", "lane-12", "-m", "Merge lane-12")
    other_merge = _git(root, "rev-parse", "HEAD").stdout.strip()
    actual = _commit(root, "fix(#11): uncited landing after the other merge")
    citation = other_merge[:8]
    missing = "ffffffffffffffffffffffffffffffffffffffff"

    ledger_text = (
        "# Task ledger\n\nNext id: **13**\n\n## Open\n"
        "- **#11** — genuinely uncited · origin: **loop**\n"
        f"  · unrelated task merge `{citation}` and bad citation `{missing}`\n"
        "- **#12** — other task · origin: **loop**\n\n"
        "## Recently landed\n")
    out = ledger.sweep_text(
        ledger_text, [(actual, "fix(#11): uncited landing after the other merge")],
        "base-sha", "markdown", repo=root)

    assert "  #11 —" in out and "CITED-OPEN #11" not in out, (
        f"#11 cites merge {citation}, but that merge yielded only the explicitly "
        f"planted #12 commit {other_commit[:8]}, not #11's {actual[:8]}; #11 "
        f"must remain visibly UNCITED: {out!r}")
    assert "citation resolution: 1/2 cited sha(s) resolved" in out, out
    assert f"`{citation}`:1" in out and f"`{missing}`:0" in out, (
        f"each resolution candidate needs a denominator, including zero for "
        f"the deliberately missing hardcoded sha: {out!r}")


@pytest.mark.parametrize(
    "failure",
    [ledger.subprocess.TimeoutExpired(["git", "cat-file"], timeout=20),
     OSError("git executable unavailable")],
    ids=["timeout", "oserror"],
)
def test_sweep_reports_degraded_substring_fallback_when_git_is_unavailable(
        monkeypatch, failure):
    """An unavailable resolver falls back visibly; advisory sweep never dies."""
    commit_sha = "58e3040d"
    citation = commit_sha[:7]
    ledger_text = (
        "# Task ledger\n\nNext id: **466**\n\n## Open\n"
        "- **#465** — width-rotted citation · origin: **loop**\n"
        f"  · landed in `{citation}`\n\n## Recently landed\n")

    def unavailable(*args, **kwargs):
        raise failure

    monkeypatch.setattr(ledger.subprocess, "run", unavailable)
    out = ledger.sweep_text(
        ledger_text, [(commit_sha, "fix(#465): landing")], None, "markdown")

    assert "DEGRADED" in out and "substring" in out, (
        f"the fallback must say it fired, not merely avoid an exception: {out!r}")
    assert "#465 —" in out, (
        "the documented substring fallback cannot reconcile different widths; "
        "the finding proves that fallback, rather than resolution, answered")


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


def test_sweep_report_distinguishes_an_empty_window_from_a_full_history_scan():
    """The clean sentence must carry a denominator and its boundary.

    These two inputs have the same finding set.  One examined nothing after a
    fold boundary; the other examined a real, non-id commit from repository
    root.  Their all-clear lines are intentionally identical, so the header is
    the discriminating evidence rather than a reworded verdict.

    PRODUCTION SEAM: ``sweep_text``'s header.  RED: remove the explicit window
    start and both outputs again answer only "how many findings?".
    """
    looked_nowhere = ledger.sweep_text(
        SWEEP_LEDGER, [], "fold-boundary-123", "markdown")
    looked_from_root = ledger.sweep_text(
        SWEEP_LEDGER, [("aaa0001", "docs: no task id")], None, "markdown")

    assert "nothing to review" in looked_nowhere
    assert "nothing to review" in looked_from_root
    assert "examined 0 commits; window start: fold-boundar" in looked_nowhere, (
        f"the zero-sized window must say both facts: {looked_nowhere!r}")
    assert "examined 1 commits; window start: repository root" in looked_from_root, (
        f"the non-empty full-history population must stay visible: "
        f"{looked_from_root!r}")


def test_sweep_report_calls_a_cited_open_landing_an_anomaly():
    """Citation is evidence of a landing, not evidence of closure.

    The fixture independently proves #11 is OPEN and cites abc1234.  The
    report must therefore keep it visible in a distinct bucket while the
    legacy pure ``sweep`` API may continue returning only uncited findings.

    PRODUCTION SEAM: ``_sweep_classified``'s cited bucket plus the
    ``CITED-OPEN`` rendering branch.  RED: route cited matches nowhere and the
    discriminating id+sha assertion fails.
    """
    open_ids, landed_ids = watch.parse_ledger(SWEEP_LEDGER)
    assert "11" in open_ids and "11" not in landed_ids, (
        "precondition: #11 must genuinely remain open")
    assert "abc1234" in _sweep_open_body(11), (
        "precondition: #11 must genuinely cite its named commit")

    out = ledger.sweep_text(
        SWEEP_LEDGER, [("abc1234", "fix(#11): cited landing")],
        "fold-boundary-123", "markdown")

    assert "1 open id(s) excluded by sha-citation" in out, out
    assert "CITED-OPEN #11" in out and "`abc1234`" in out, (
        f"the cited open id and its evidence must remain reportable: {out!r}")
    assert "  #11 —" not in out, (
        f"a cited landing belongs only in the anomaly bucket, never also in "
        f"the uncited findings: {out!r}")
    assert "cited-but-still-open id(s)" in out, out
    assert "nothing to review" not in out, (
        f"an open task citing its landing is not an all-clear: {out!r}")


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
# #723 — `wip(#NNN)`: the kill-recovery form. SWEEP_SUBJECT's verb
# alternation does not include `wip` (it is not a landing verb: the brief's
# approved set is `merge fix feat close perf refactor guard docs test
# design`), so `wip(#465): lane containment …` — an ancestor of master
# carrying 752 lines of dev/lane_guard.py — was STRUCTURALLY INVISIBLE to
# the primary landing-discovery route. The id surfaced only via a bare-form
# docs/hand-off commit, not via the commit that shipped the code.
#
# MEASURED on the live repo (2866 commits): 3 wip( commits total, only ONE
# (#465) names an open id — the other two (#463, #326) are landed, so
# invisible to sweep regardless. #465 is already surfaced today via the
# bare-form commit `36c7d867`. The widening adds +0 new open ids and +1 real
# landing row (the 752-line guard commit `58e3040d`, whose sha is 8 chars
# but the body cites only 7, so subtraction does not catch it). That single
# row is the whole value: the tool now points at the CODE, not the docs.
#
# The brief argued for a distinct PRESENTATION class ("may carry partial
# work"). REJECTED on measurement: 3 instances, 0 partials (2 merged to
# completion, 1 open by design). But `wip` MUST be excluded from the
# high-confidence "verb" class — without a `_subject_class` guard it falls
# through to `return "verb"`, classifying a kill-recovery snapshot as
# landing-intent. The guard is correctness, not presentation.
# ---------------------------------------------------------------------------

def test_sweep_subject_widened_to_match_the_wip_kill_recovery_form():
    """DIRECTION-1 measurement, fixture not live repo (#723 brief).

    `wip(#465): lane containment …` is the convention for committing a
    killed lane's work as-found. The #723 brief measured it invisible:
    SWEEP_SUBJECT's verb alternation does not include `wip`. This is the
    primary landing-discovery route (#404) blind to the form that carries
    work nobody got to tidy.
    PRODUCTION LINE: the wip alternative in SWEEP_SUBJECT (g4).
    RED on the un-widened pattern: this returns None.
    """
    assert ledger.SWEEP_SUBJECT.match("wip(#10): lane containment"), (
        "the wip(#) kill-recovery form — the convention for a lane's work "
        "as-found when its process was killed — must match; #723 measured "
        "it invisible to the primary landing-discovery route")
    m = ledger.SWEEP_SUBJECT.match("wip(#10): x")
    groups = [g for g in m.groups() if g]
    assert groups == ["#10"], (
        f"the id must be capturable from the wip form: {m.groups()!r}")


def test_sweep_wip_is_not_classified_as_high_confidence_verb():
    """wip is NOT a landing verb — it is a kill-recovery snapshot.

    Without a `_subject_class` guard, a matched `wip(#N)` subject falls
    through to `return "verb"`, classifying it as HIGH confidence (the verb
    carries landing intent). That is the #707 false-attribution hazard: wip
    carries 'I was interrupted', not 'this landed'. PRODUCTION LINE: the
    `_subject_class` guard for wip. RED: drop the guard and the class is
    'verb' (the fallthrough).
    """
    # Precondition: the pattern must actually MATCH wip, or this is hollow.
    assert ledger.SWEEP_SUBJECT.match("wip(#10): x") is not None, (
        "precondition: wip(#) must match post-widening, else the class test "
        "is hollow — it passes when nothing matched at all")
    cls = ledger._subject_class("wip(#10): lane containment")
    assert cls != "verb", (
        f"wip(#) must NOT be high-confidence 'verb' (landing intent) — it is "
        f"a kill-recovery snapshot; got {cls!r}")


def test_sweep_finds_a_wip_landing_it_previously_missed():
    """DIRECTION-1 red: the real gap, fixture not live repo.

    A `wip(#10):` commit where #10 is OPEN and uncited is the #723
    instance: the commit that shipped real code, invisible to sweep.
    PRODUCTION LINE: the widened SWEEP_SUBJECT + the `for tid in ...` loop.
    RED: drop the wip alternative and #10 vanishes from findings.
    """
    commits = [("www0001", "wip(#10): lane containment as the lane left it")]
    n, findings = ledger.sweep(SWEEP_LEDGER, commits)
    by_id = {tid: shas for tid, shas in findings}
    assert 10 in by_id, (
        "a wip(#10): landing for an open uncited id must now be found — #723 "
        "measured this class invisible")
    assert any(sha == "www0001" for sha, _ in by_id[10])


def test_sweep_still_subtracts_cited_shas_for_wip_form():
    """The subtraction convention (#404) must hold for wip too (#707's
    principle applied to the new form).

    PRECONDITION: the wip form must MATCH after widening, or this test is
    hollow — the #707 'green red-run is a finding' trap.
    PRODUCTION LINE: `if sha in bodies.get(tid, ""): continue` in `sweep`,
    now reached with wip subjects.
    """
    subj = "wip(#11): lane containment"
    assert ledger.SWEEP_SUBJECT.match(subj) is not None, (
        "precondition: the wip form must match post-widening")
    assert "abc1234" in _sweep_open_body(11), (
        "precondition: #11's body must cite the sha the wip commit carries")
    commits = [("abc1234", subj)]
    _, findings = ledger.sweep(SWEEP_LEDGER, commits)
    assert 11 not in {tid for tid, _ in findings}, (
        "a wip(#11): whose entry cites the sha must be subtracted")


def test_sweep_wip_multi_id_subject_captures_all_ids():
    """`wip(#10,#12):` must surface both open ids, matching how the verb
    and Merge alternatives handle multi-id parens (#404: 'the parens may
    carry several ids'). PRODUCTION LINE: the `for tid in …` loop in `sweep`
    feeding off SWEEP_ID.findall on the wip group.
    """
    commits = [("www0002", "wip(#10,#12): two tasks in one kill-recovery")]
    _, findings = ledger.sweep(SWEEP_LEDGER, commits)
    by_id = {tid for tid, _ in findings}
    assert 10 in by_id and 12 in by_id, (
        "a multi-id wip(#) subject must surface every open id it names")


# ---------------------------------------------------------------------------
# #1108 — presquash: a --squash landing carries a `Presquash-Ref:` trailer
# (dev/land_lane.py:720) naming the preserved `<branch>-presquash` tag. The
# follower resolves that ref and scans the constituent SUBJECTS, recovering
# any task id a constituent claimed that the one squashed subject did not.
# Only SUBJECTS are scanned (#404 convention); constituent bodies are not
# (#1097). These tests build real repos because the follower is git-backed.
# ---------------------------------------------------------------------------

def _short_sha(root, sha):
    """The %h form `_git_subjects` yields — the form the trailer map keys on."""
    return _git(root, "rev-parse", "--short", sha).stdout.strip()


def _squashed_commit(root, base_sha, tree_ref, subject, trailer_ref):
    """A commit off base whose tree is tree_ref and whose message carries the
    Presquash-Ref trailer — the shape land_lane --squash builds."""
    tree = _git(root, "rev-parse", f"{tree_ref}^{{tree}}").stdout.strip()
    msg = f"{subject}\n\nPresquash-Ref: {trailer_ref}\n"
    out = subprocess.run(
        ["git", "-C", str(root), "commit-tree", tree, "-p", base_sha, "-F", "-"],
        input=msg, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def test_presquash_ref_from_message_extracts_the_trailer_and_absent_yields_none():
    assert ledger._presquash_ref_from_message(
        "build(#11): x\n\nPresquash-Ref: refs/tags/lane-presquash\n") == (
        "refs/tags/lane-presquash")
    assert ledger._presquash_ref_from_message("build(#11): no trailer") is None
    assert ledger._presquash_ref_from_message("") is None


def test_presquash_expand_follows_a_resolving_ref_and_returns_hidden_ids(tmp_path):
    """The acceptance shape: a constituent SUBJECT names a task the squashed
    subject did not, and the follower recovers it. An id the squashed subject
    CLAIMS (a recognised verb form) is de-duped, not re-reported."""
    root = _bare_repo(tmp_path, "presquash-follow")
    base = _commit(root, "docs: base")
    _git(root, "checkout", "-q", "-b", "lane")
    _commit(root, "fix(#11): first task the squash subject claims")
    c2 = _commit(root, "feat(#12): second task the squash subject hides")
    _git(root, "tag", "lane-presquash")
    _git(root, "checkout", "-q", base)
    squashed = _squashed_commit(
        root, base, "refs/tags/lane-presquash",
        "fix(#11): squashed rebuild", "refs/tags/lane-presquash")
    short = _short_sha(root, squashed)

    expanded, followed, unfollowable = ledger._presquash_expand(
        root, [(short, "fix(#11): squashed rebuild")])

    hidden = {tid for _, tid, _ in expanded}
    assert 12 in hidden, (
        f"#12 lives in constituent subject {c2[:7]!r} the squashed subject did "
        f"not name; the follower must recover it: {expanded!r}")
    assert 11 not in hidden, (
        f"#11 is CLAIMED by the squashed subject (fix(#11)); re-reporting it "
        f"from a constituent is the double-report #1108 Direction 2 forbids: "
        f"{expanded!r}")
    assert followed and followed[0][0] == short and followed[0][2] == 2, (
        f"the ref resolved and the follower saw both constituent commits: "
        f"{followed!r}")
    assert unfollowable == [], (
        f"a resolving ref must not be reported unfollowable: {unfollowable!r}")


def test_presquash_expand_recovers_ids_a_build_squash_subject_did_not_claim(
        tmp_path):
    """The real #1029 shape: the squashed subject is ``build(#N): rebuild
    client/dist`` — ``build`` is NOT a landing verb, so SWEEP_SUBJECT does not
    treat it as a claim. A constituent ``fix(#N):`` IS a claim, so #N is
    legitimately recovered from the constituent (not de-duped, because the
    squashed subject claimed nothing). This is why the follower has value even
    for a squash whose subject names its own task in a non-verb form."""
    root = _bare_repo(tmp_path, "presquash-build")
    base = _commit(root, "docs: base")
    _git(root, "checkout", "-q", "-b", "lane")
    _commit(root, "fix(#11): the real landing verb the build subject lacks")
    _git(root, "tag", "lane-presquash")
    _git(root, "checkout", "-q", base)
    squashed = _squashed_commit(
        root, base, "refs/tags/lane-presquash",
        "build(#11): rebuild client/dist", "refs/tags/lane-presquash")
    short = _short_sha(root, squashed)

    expanded, followed, _unfollowable = ledger._presquash_expand(
        root, [(short, "build(#11): rebuild client/dist")])

    hidden = {tid for _, tid, _ in expanded}
    assert 11 in hidden, (
        f"the squashed subject build(#11) is not a landing claim (build is not "
        f"a verb), so the constituent fix(#11) legitimately recovers #11: "
        f"{expanded!r}")


def test_presquash_expand_reports_unfollowable_when_the_ref_does_not_resolve(
        tmp_path):
    """#136: a trailer whose ref cannot resolve is a distinct state from a
    squash that followed its ref and found no new ids."""
    root = _bare_repo(tmp_path, "presquash-broken")
    base = _commit(root, "docs: base")
    _git(root, "checkout", "-q", "-b", "lane")
    _commit(root, "fix(#11): only task")
    _git(root, "tag", "lane-presquash")
    _git(root, "checkout", "-q", base)
    squashed = _squashed_commit(
        root, base, "refs/tags/lane-presquash", "build(#11): squash",
        "refs/tags/lane-presquash")
    short = _short_sha(root, squashed)
    # delete the tag the trailer names — the ref no longer resolves
    _git(root, "tag", "-d", "lane-presquash")

    expanded, followed, unfollowable = ledger._presquash_expand(
        root, [(short, "build(#11): squash")])

    assert expanded == [] and followed == [], (
        f"a ref that does not resolve yields neither ids nor a followed row: "
        f"{(expanded, followed)!r}")
    assert len(unfollowable) == 1 and unfollowable[0][0] == short, (
        f"the broken ref must be reported unfollowable, naming the squashed "
        f"sha: {unfollowable!r}")
    assert "does not resolve" in unfollowable[0][2], (
        f"the reason must name the ref resolution failure: {unfollowable!r}")


def test_presquash_expand_does_not_scan_constituent_bodies(tmp_path):
    """A constituent id that lives only in a BODY is NOT recovered — the
    #1108 acceptance case (#1030) is exactly this shape. Scanning bodies would
    import #1097's false-positive problem (a head-lined reference like '#710 —
    why --squash exists' is not a landing)."""
    root = _bare_repo(tmp_path, "presquash-body")
    base = _commit(root, "docs: base")
    _git(root, "checkout", "-q", "-b", "lane")
    _commit(root, "fix(#11): the named task",
            body="#12 — mentioned only in this body, not the subject")
    _git(root, "tag", "lane-presquash")
    _git(root, "checkout", "-q", base)
    squashed = _squashed_commit(
        root, base, "refs/tags/lane-presquash", "build(#11): squash",
        "refs/tags/lane-presquash")
    short = _short_sha(root, squashed)

    expanded, followed, unfollowable = ledger._presquash_expand(
        root, [(short, "build(#11): squash")])

    hidden = {tid for _, tid, _ in expanded}
    assert 12 not in hidden, (
        f"#12 is in a constituent BODY only; subjects are scanned, bodies are "
        f"not (#1097), so it must not be recovered: {expanded!r}")
    assert followed and unfollowable == [], (
        f"the ref resolved (the body-only id is a limitation, not a broken "
        f"ref): {(followed, unfollowable)!r}")


def test_sweep_text_reports_a_constituent_landing_the_squashed_subject_hid(
        tmp_path):
    """Integration: the CLI-built presquash triples surface in the report as a
    landing attributed to the squashed sha (#1108 acceptance shape)."""
    root = _bare_repo(tmp_path, "presquash-report")
    base = _commit(root, "docs: base")
    _git(root, "checkout", "-q", "-b", "lane")
    _commit(root, "fix(#11): named in the squash subject")
    _commit(root, "fix(#12): hidden by the squash subject")
    _git(root, "tag", "lane-presquash")
    _git(root, "checkout", "-q", base)
    squashed = _squashed_commit(
        root, base, "refs/tags/lane-presquash", "build(#11): squash",
        "refs/tags/lane-presquash")
    short = _short_sha(root, squashed)
    presquash = ledger._presquash_expand(
        root, [(short, "build(#11): squash")])
    ledger_text = (
        "# Task ledger\n\nNext id: **13**\n\n## Open\n"
        "- **#11** — named · origin: **loop**\n"
        "- **#12** — hidden · origin: **loop**\n\n## Recently landed\n")

    out = ledger.sweep_text(
        ledger_text, [(short, "build(#11): squash")], "base", "markdown",
        repo=root, presquash=presquash)

    assert "#12 —" in out, (
        f"#12 is named in a constituent subject the squashed subject hid; the "
        f"report must surface it: {out!r}")
    assert "presquash: followed 1 ref(s)" in out, (
        f"the report must say it followed the ref (#136 discriminability): "
        f"{out!r}")
    # #11 is in BOTH the squashed subject and a constituent — reported once
    assert out.count("#11 —") + out.count("#11,") <= 1 or "CITED-OPEN #11" in out


def test_sweep_text_distinguishes_unfollowable_from_followed_and_found_nothing(
        tmp_path):
    """#136: 'could not follow' must not render like 'followed and found
    nothing'. Two presquash args, same empty id result, different status."""
    ledger_text = (
        "# Task ledger\n\nNext id: **13**\n\n## Open\n"
        "- **#11** — open · origin: **loop**\n\n## Recently landed\n")
    commits = [("sss0001", "build(#11): squash")]
    # followed, found nothing new (#11 already in the squashed subject)
    followed_empty = ([], [("sss0001", "refs/tags/x-presquash", 1)], [])
    # could not follow — ref does not resolve
    unfollowable = ([], [], [("sss0001", "refs/tags/x-presquash",
                              "ref does not resolve")])

    out_ok = ledger.sweep_text(
        ledger_text, commits, "base", "markdown", presquash=followed_empty)
    out_bad = ledger.sweep_text(
        ledger_text, commits, "base", "markdown", presquash=unfollowable)

    assert "followed 1 ref(s)" in out_ok and "; 0 could not follow" in out_ok, (
        f"a followed ref that found nothing names its followed count, not a "
        f"could-not-follow: {out_ok!r}")
    assert "COULD NOT FOLLOW" not in out_ok, (
        f"a followed ref must not raise the could-not-follow alarm: {out_ok!r}")
    assert "COULD NOT FOLLOW" in out_bad and "ref does not resolve" in out_bad, (
        f"an unresolvable ref must be reported as could-not-follow, distinct "
        f"from followed-and-empty: {out_bad!r}")


# ---------------------------------------------------------------------------
# #1111 — Also-Fixes: a declared trailer for incidental fixes that bodies
# cannot surface (#1097) and subjects may not carry. These tests exercise
# the reader (_collect_also_fixes), the classifier, the dedup, and the
# short-sha join fix. See #1108's presquash tests for the shared pattern.
# ---------------------------------------------------------------------------

def _also_fixes_commit(root, subject, also_ids):
    """An empty commit whose message carries an Also-Fixes trailer."""
    also_line = ", ".join(f"#{i}" for i in also_ids)
    msg = f"{subject}\n\nAlso-Fixes: {also_line}\n"
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "--allow-empty", "-F", "-"],
        input=msg, capture_output=True, text=True, check=True)
    return _git(root, "rev-parse", "HEAD").stdout.strip()


def test_collect_also_fixes_reads_a_single_trailer(tmp_path):
    """The basic acceptance shape: one commit, one Also-Fixes id."""
    root = _bare_repo(tmp_path, "also-fixes-basic")
    full = _also_fixes_commit(root, "fix(#11): the named task", [12])
    short = _short_sha(root, full)

    result = ledger._collect_also_fixes(
        root, [(short, "fix(#11): the named task")])

    tids = {tid for _, tid, _ in result}
    assert 12 in tids, (
        f"#12 is declared in the Also-Fixes trailer and must be collected: "
        f"{result!r}")
    assert 11 not in tids, (
        f"#11 is in the SUBJECT, not the trailer; _collect_also_fixes reads "
        f"only trailers: {result!r}")


def test_collect_also_fixes_reads_multiple_ids_on_one_line(tmp_path):
    """``Also-Fixes: #12, #13`` — both ids must be collected."""
    root = _bare_repo(tmp_path, "also-fixes-multi")
    _also_fixes_commit(root, "fix(#11): task", [12, 13])

    commits = [(_short_sha(root, "HEAD"), "fix(#11): task")]
    result = ledger._collect_also_fixes(root, commits)
    tids = {tid for _, tid, _ in result}
    assert 12 in tids and 13 in tids, (
        f"both ids on one line must be collected: {result!r}")


def test_collect_also_fixes_reads_multiple_trailer_lines(tmp_path):
    """Two ``Also-Fixes:`` lines on one commit — both ids collected.

    Git's %(trailers:valueonly) yields one line per trailer, so the parser
    must accumulate across lines for the same commit."""
    root = _bare_repo(tmp_path, "also-fixes-lines")
    msg = ("fix(#11): task\n\n"
           "Also-Fixes: #12\n"
           "Also-Fixes: #13\n")
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "--allow-empty", "-F", "-"],
        input=msg, capture_output=True, text=True, check=True)

    commits = [(_short_sha(root, "HEAD"), "fix(#11): task")]
    result = ledger._collect_also_fixes(root, commits)
    tids = {tid for _, tid, _ in result}
    assert 12 in tids and 13 in tids, (
        f"ids across multiple trailer lines must be collected: {result!r}")


def test_collect_also_fixes_handles_length_mismatch(tmp_path):
    """#1111 direction-2: the short-sha join must survive a length mismatch.

    _collect_also_fixes uses the same full-sha keying as _git_presquash_refs.
    This test constructs a commit, then reads it through _collect_also_fixes
    using a DIFFERENT abbreviation length (7 chars vs git's default) — the
    realistic shape that broke #1108's join during development."""
    root = _bare_repo(tmp_path, "also-fixes-shamismatch")
    full = _also_fixes_commit(root, "fix(#11): task", [12])
    # git default is 7 chars for small repos; use a 7-char abbreviation
    short7 = full[:7]
    result = ledger._collect_also_fixes(root, [(short7, "fix(#11): task")])
    tids = {tid for _, tid, _ in result}
    assert 12 in tids, (
        f"a 7-char sha must still resolve to the full-sha trailer map; the "
        f"length mismatch must not silently drop the id: {result!r}")


def test_sweep_text_reports_also_fixes_as_candidates(tmp_path):
    """An Also-Fixes id that the subject did NOT name surfaces as a CANDIDATE."""
    root = _bare_repo(tmp_path, "also-fixes-report")
    full = _also_fixes_commit(root, "fix(#11): named task", [12])
    short = _short_sha(root, full)
    also_fixes = ledger._collect_also_fixes(
        root, [(short, "fix(#11): named task")])
    ledger_text = (
        "# Task ledger\n\nNext id: **13**\n\n## Open\n"
        "- **#12** — open · origin: **loop**\n\n## Recently landed\n")

    out = ledger.sweep_text(
        ledger_text, [(short, "fix(#11): named task")], "base", "markdown",
        also_fixes=also_fixes)

    assert "ALSO-FIXES #12" in out, (
        f"#12 is declared in an Also-Fixes trailer; the report must surface it "
        f"as a candidate: {out!r}")
    assert "also-fixes candidate(s)" in out, (
        f"the summary must name the candidate count: {out!r}")


def test_sweep_text_does_not_double_report_an_also_fixes_id(tmp_path):
    """#1111 direction-2: an id named by BOTH the subject and the trailer
    must be reported ONCE — as a subject landing, not a candidate."""
    root = _bare_repo(tmp_path, "also-fixes-dedup")
    # #12 is in BOTH the subject AND the Also-Fixes trailer
    full = _also_fixes_commit(root, "fix(#12): named task", [12])
    short = _short_sha(root, full)
    also_fixes = ledger._collect_also_fixes(
        root, [(short, "fix(#12): named task")])
    ledger_text = (
        "# Task ledger\n\nNext id: **13**\n\n## Open\n"
        "- **#12** — open · origin: **loop**\n\n## Recently landed\n")

    out = ledger.sweep_text(
        ledger_text, [(short, "fix(#12): named task")], "base", "markdown",
        also_fixes=also_fixes)

    # #12 appears as a subject landing (verb form), NOT as an ALSO-FIXES row
    assert "#12 —" in out, (
        f"#12 is in the subject and must be reported as a landing: {out!r}")
    assert "ALSO-FIXES #12" not in out, (
        f"#12 was already found by the subject scan; re-reporting it as an "
        f"ALSO-FIXES candidate is the double-report #1111 forbids: {out!r}")
    assert "also-fixes candidate(s)" not in out, (
        f"zero also-fixes candidates after dedup; the summary must not claim "
        f"a candidate: {out!r}")


def test_sweep_text_drops_an_also_fixes_id_that_is_already_landed(tmp_path):
    """An id not in open_ids is silently dropped — not a candidate, not an error."""
    root = _bare_repo(tmp_path, "also-fixes-landed")
    full = _also_fixes_commit(root, "fix(#11): task", [99])
    short = _short_sha(root, full)
    also_fixes = ledger._collect_also_fixes(root, [(short, "fix(#11): task")])
    # #99 is NOT in the ledger at all — it is either landed or non-existent
    ledger_text = (
        "# Task ledger\n\nNext id: **100**\n\n## Open\n"
        "- **#11** — open · origin: **loop**\n\n## Recently landed\n")

    out = ledger.sweep_text(
        ledger_text, [(short, "fix(#11): task")], "base", "markdown",
        also_fixes=also_fixes)

    assert "ALSO-FIXES #99" not in out, (
        f"#99 is not an open id; it must not be reported as a candidate: "
        f"{out!r}")


def test_sweep_text_exit_zero_with_also_fixes_only(tmp_path):
    """#1111: sweep's advisory contract — exit 0 always, even with only
    also-fixes candidates. 'found nothing' must stay distinguishable from
    'did not run' via the examined commit count."""
    root = _bare_repo(tmp_path, "also-fixes-advisory")
    full = _also_fixes_commit(root, "fix(#11): task", [12])
    short = _short_sha(root, full)
    also_fixes = ledger._collect_also_fixes(root, [(short, "fix(#11): task")])
    ledger_text = (
        "# Task ledger\n\nNext id: **13**\n\n## Open\n"
        "- **#12** — open · origin: **loop**\n\n## Recently landed\n")

    out = ledger.sweep_text(
        ledger_text, [(short, "fix(#11): task")], "base", "markdown",
        also_fixes=also_fixes)

    assert "examined 1 commits" in out, (
        f"the examined count must be real (#404/#136): {out!r}")
    assert "ALSO-FIXES #12" in out


def test_presquash_expand_survives_a_sha_length_mismatch(tmp_path):
    """#1111: _presquash_expand must resolve the commits-list %h sha to the
    full %H the trailer map keys on, even when the abbreviation length differs.

    This constructs the exact shape that broke #1108 during development: the
    commits list carries a DIFFERENT abbreviation than the trailer map's own
    %h. Before the fix, the join silently missed and the follower returned
    all-empty with no COULD NOT FOLLOW signal (#136 collapse)."""
    root = _bare_repo(tmp_path, "presquash-shamismatch")
    base = _commit(root, "docs: base")
    _git(root, "checkout", "-q", "-b", "lane")
    _commit(root, "feat(#12): hidden by the squash subject")
    _git(root, "tag", "lane-presquash")
    _git(root, "checkout", "-q", base)
    squashed = _squashed_commit(
        root, base, "refs/tags/lane-presquash",
        "fix(#11): squash", "refs/tags/lane-presquash")
    # Use a 7-char abbreviation (git's %h for a small repo is 7 chars); the
    # trailer map uses its own %h. Before the fix, a mismatch dropped the join.
    short7 = squashed[:7]

    expanded, followed, unfollowable = ledger._presquash_expand(
        root, [(short7, "fix(#11): squash")])

    hidden = {tid for _, tid, _ in expanded}
    assert 12 in hidden, (
        f"#12 is named in a constituent subject; the length mismatch must "
        f"not silently drop it: {expanded!r}")
    assert followed, (
        f"the ref must be followed despite the sha length mismatch: "
        f"{followed!r}")
    assert unfollowable == [], (
        f"a resolving ref must not be reported unfollowable: {unfollowable!r}")


def test_sweep_text_round_trip_also_fixes_through_a_squashed_commit(tmp_path):
    """#1111 Direction-2: a squashed commit carries a propagated Also-Fixes
    trailer, and a sweep finds it. Proves the reader + sweep form a closed loop
    against the shape land_lane --squash produces (the propagation itself is
    tested in test_land_lane.py)."""
    root = _bare_repo(tmp_path, "also-fixes-roundtrip")
    base = _commit(root, "docs: base")
    _git(root, "checkout", "-q", "-b", "lane")
    _commit(root, "fix(#11): the named task")
    _git(root, "tag", "lane-presquash")
    _git(root, "checkout", "-q", base)
    # Build a squashed commit carrying BOTH trailers — the shape land_lane
    # produces when a constituent declared an Also-Fixes
    tree = _git(root, "rev-parse", "refs/tags/lane-presquash^{tree}").stdout.strip()
    msg = ("fix(#11): squashed rebuild\n\n"
           "Presquash-Ref: refs/tags/lane-presquash\n"
           "Also-Fixes: #12\n")
    squashed = subprocess.run(
        ["git", "-C", str(root), "commit-tree", tree, "-p", base, "-F", "-"],
        input=msg, capture_output=True, text=True, check=True).stdout.strip()
    short = _short_sha(root, squashed)
    commits = [(short, "fix(#11): squashed rebuild")]

    also_fixes = ledger._collect_also_fixes(root, commits)
    assert {tid for _, tid, _ in also_fixes} == {12}, (
        f"the propagated Also-Fixes #12 must be collected from the squashed "
        f"commit: {also_fixes!r}")
    ledger_text = (
        "# Task ledger\n\nNext id: **13**\n\n## Open\n"
        "- **#12** — open · origin: **loop**\n\n## Recently landed\n")

    out = ledger.sweep_text(
        ledger_text, commits, "base", "markdown",
        repo=root, also_fixes=also_fixes)

    assert "ALSO-FIXES #12" in out, (
        f"the round trip must find #12: the squashed commit carries the "
        f"trailer, sweep collected it, and the report surfaces it: {out!r}")


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
    n, ndup, nlive, rows = ledger.reach(_reach_marks())
    names = {b for b, _, _ in rows}
    assert "live-work" in names, "a + commit must surface the branch"
    assert "scratch-only" in names
    assert "cherry-picked" not in names, (
        "a branch with only - commits (all on base) must NOT be reported — "
        "that is #676 finding 2's strong-evidence side")


def test_reach_collapses_duplicate_sha_sets_into_one_row():
    n, ndup, nlive, rows = ledger.reach(_reach_marks())
    by_name = {b: (aliases, plus) for b, aliases, plus in rows}
    # pi-agent-aaa shares live-work's sha set → alias, not a separate row
    assert "pi-agent-aaa" not in by_name, (
        "a duplicate sha set must collapse (#676 finding 3), not get its own row")
    assert "pi-agent-aaa" in by_name["live-work"][0], (
        "and it must be named as an alias of the surviving row")
    assert ndup == 1, (
        f"one duplicate was suppressed; got {ndup} — the count lets the report "
        f"say how many were hidden, not just that some were (#671)")


def test_reach_counts_every_branch_examined_so_did_not_run_is_distinguishable():
    marks = _reach_marks()
    n, ndup, nlive, rows = ledger.reach(marks)
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


def test_reach_exact_adjudication_note_moves_branch_to_classified_bucket():
    """The expected branch comes from this hardcoded fixture, not the matcher.

    Both established corpus phrases are planted literally. The production
    regex is the checked thing; it is not used to manufacture the expectation.
    """
    records = [
        {"id": 691, "body":
         "task prose\n  · BRANCH CLASSIFIED — cx-691recap (3 commits) is "
         "a SUPERSEDED DUPLICATE; do NOT merge."},
        {"id": 863, "body":
         "task prose\n  · BRANCH ADJUDICATED — opus-863jank2 is "
         "SUPERSEDED; do NOT merge."},
    ]
    adjudications, examined, matched = ledger._branch_adjudications(records)
    marks = [
        ("cx-691recap", [("+", "aaa111", "docs(#691): old design")]),
        ("opus-863jank2", [("+", "bbb222", "wip(#863): old fix")]),
        ("never-reviewed", [("+", "ccc333", "wip: unknown")]),
    ]

    text = ledger.reach_text(
        marks, "master", live=set(), adjudications=adjudications,
        record_count=examined, adjudication_matches=matched)

    assert "examined 3 branches" in text, text
    assert "2 CLASSIFIED, 1 UNEXAMINED" in text, text
    assert "CLASSIFIED by BRANCH CLASSIFIED note on #691" in text, text
    assert "CLASSIFIED by BRANCH ADJUDICATED note on #863" in text, text
    assert "not proof that content landed" in text, text
    assert "UNEXAMINED (+ is a question, not a verdict):\n  never-reviewed" \
        in text, text


def test_reach_near_miss_or_quoted_branch_does_not_false_classify():
    """Direction 2: a different/quoted branch must leave the target open.

    Expected ``cx-691recap`` is a hardcoded planted branch, independently of
    the production note parser. A loose ``if branch in body`` fails here.
    """
    records = [
        {"id": 900, "body":
         "  · BRANCH CLASSIFIED — cx-691recap2 is superseded\n"
         "  · Someone wrote \"BRANCH ADJUDICATED — cx-691recap\" in a quote"},
    ]
    adjudications, examined, matched = ledger._branch_adjudications(records)
    marks = [("cx-691recap", [
        ("+", "aaa111", "docs(#691): genuinely unexamined")])]

    text = ledger.reach_text(
        marks, "master", live=set(), adjudications=adjudications,
        record_count=examined, adjudication_matches=matched)

    assert "0 CLASSIFIED, 1 UNEXAMINED" in text, text
    assert "UNEXAMINED (+ is a question, not a verdict):\n  cx-691recap" \
        in text, text
    assert "CLASSIFIED by" not in text, text


def test_reach_zero_task_record_denominator_is_an_alarm_not_green():
    text = ledger.reach_text(
        [("unexamined", [("+", "aaa111", "wip: unknown")])],
        "master", live=set(), adjudications={}, record_count=0,
        adjudication_matches=0)

    assert "examined 1 branches" in text, text
    assert "ALARM — classification scan examined 0 task records" in text, text
    assert "0 CLASSIFIED, 1 UNEXAMINED" in text, text


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
# #715 — reach() suppresses LIVE lane branches (not lane-* by name). A live
# lane ALWAYS carries + commits, so it is the one class reach can never learn
# anything from — and after #711 it is 100% of the output. The discriminator
# is LIVENESS, never the name: an abandoned lane-* branch is the thing this
# check exists to find. The count line is the PRIMARY output after the fix.
# ---------------------------------------------------------------------------

def _reach_lanes():
    """A synthetic branch set exercising the three lanes + an abandoned one.

    - ``lane-710history``: + commits, LIVE  → suppressed as a live lane
    - ``lane-716fleet``:   + commits, LIVE  → suppressed as a live lane
    - ``lane-700dead``:    + commits, DEAD  → reported (the finding #715 exists for)
    - ``non-lane-spike``:  + commits        → reported (not a lane at all)
    """
    return [
        ("lane-710history", [("+", "aaa111", "fix(#710): active work")]),
        ("lane-716fleet", [("+", "bbb222", "fix(#716): active work")]),
        ("lane-700dead", [("+", "ccc333", "fix(#700): abandoned work")]),
        ("non-lane-spike", [("+", "ddd444", "wip: experiment")]),
    ]


def test_reach_suppresses_live_lanes_but_not_abandoned_ones():
    """#715: a LIVE lane's + branch is suppressed; an ABANDONED lane-* branch
    is NOT. PRODUCTION LINE: the ``{branch, *aliases} & live_set`` guard in
    ``reach``. RED: make ``live`` include every branch name and
    ``lane-700dead`` disappears — the bug the brief says matters most."""
    marks = _reach_lanes()
    live = {"lane-710history", "lane-716fleet"}
    n, ndup, nlive, rows = ledger.reach(marks, live=live)
    names = {b for b, _, _ in rows}
    assert "lane-710history" not in names, (
        "a LIVE lane must be suppressed — its + commits are work in progress")
    assert "lane-716fleet" not in names, (
        "a LIVE lane must be suppressed — its + commits are work in progress")
    assert "lane-700dead" in names, (
        "an ABANDONED lane-* branch must be REPORTED — that is the one thing "
        "this check exists to find (#590, #706). Name-based suppression would "
        "delete this purpose while making the output look clean.")
    assert "non-lane-spike" in names, (
        "a non-lane branch with + commits must be reported regardless")
    assert nlive == 2, (
        f"two live lanes were suppressed; got {nlive} — the count is the "
        f"PRIMARY output after #711 made live lanes 100% of reach's output")


def test_reach_does_not_suppress_by_lane_name():
    """The discriminator is LIVENESS, never the ``lane-*`` prefix. A lane-*
    branch that is NOT in the live set must be reported, even if other lane-*
    branches ARE live."""
    marks = _reach_lanes()
    # Only lane-710history is live; lane-700dead and lane-716fleet are NOT.
    live = {"lane-710history"}
    n, ndup, nlive, rows = ledger.reach(marks, live=live)
    names = {b for b, _, _ in rows}
    assert "lane-716fleet" in names, (
        "a lane-* branch NOT in the live set must be reported — "
        "suppression by name would hide an abandoned lane")
    assert "lane-700dead" in names
    assert "lane-710history" not in names


def test_reach_text_names_suppressed_live_lanes_in_the_header():
    """#136/#671: '3 suppressed as live lanes, 0 to triage' must not render
    identically to '0 branches'. The count line is the PRIMARY output after
    the fix, not a footer."""
    marks = _reach_lanes()
    live = {"lane-710history", "lane-716fleet", "lane-700dead", "non-lane-spike"}
    text = ledger.reach_text(marks, "master", live=live)
    assert "suppressed as live lanes" in text, (
        f"the header must name how many live lanes were suppressed: {text!r}")
    assert "nothing to triage" in text, (
        f"when everything is suppressed the closing line must say so: {text!r}")


def test_reach_text_all_live_differs_from_all_empty():
    """#136: 'examined 4 branches (0 carry + commits, 4 suppressed as live
    lanes)' must not render the same as 'examined 0 branches'."""
    marks = _reach_lanes()
    live = {"lane-710history", "lane-716fleet", "lane-700dead", "non-lane-spike"}
    all_live = ledger.reach_text(marks, "master", live=live)
    truly_empty = ledger.reach_text([], "master")
    assert all_live != truly_empty, (
        f"all-suppressed-as-live must differ from nothing-to-check (#136):\n"
        f"{all_live!r}\n{truly_empty!r}")


def test_reach_text_unavailable_liveness_fails_to_flood():
    """When the liveness signal is unavailable (live=None), every + branch is
    REPORTED with a [liveness unavailable] header. Flood is safe; silence is
    not (#671). The check must never print nothing when it suppressed nothing."""
    marks = _reach_lanes()
    text = ledger.reach_text(marks, "master", live=None)
    assert "[liveness unavailable" in text, (
        f"the header must say it could not check liveness: {text!r}")
    # Every + branch is reported — fail to flood, not to silence.
    assert "lane-710history" in text
    assert "lane-700dead" in text
    assert "non-lane-spike" in text


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


# ---------------------------------------------------------------------------
# #627 — reprioritise / unblock CLI verbs. These exercise the full _dispatch
# path against a store-mode fixture (cutover watermark set), which is the real
# integration surface. They DIRECTION-1 the brief: a band change and an unblock
# that CANNOT be expressed today, then the verb doing it, asserting --why
# landed in the task's own history (not just that the field changed).
#
# The bare `dev/ledger.py get <id>` form REFUSES from a worktree (#667), and
# these run `ledger.main([... --ledger <fixture>])` so they pass --ledger on
# every call. The store does not resolve from a worktree (#667), so each test
# sets the cutover watermark so source_of_truth == 'store'.
# ---------------------------------------------------------------------------

def _cut_over_store(tmp_path):
    """A .dreamwork/ dir with a cut-over ledger store (source_of_truth='store').

    Seeds the store so the write verbs can open it and adds the cutover
    watermark so `source_of_truth` flips to 'store'. Returns the path to pass
    as `--ledger` (the tasks.md path — its parent is the .dreamwork/ dir).
    """
    dw = tmp_path / "dw"
    dw.mkdir()
    sp = ledger.store_path(str(dw))
    ledger.ledger_store.open_store(sp, seed_next_id=1).close()
    # Set the one-way cutover watermark (source_of_truth flips to 'store').
    import sqlite3
    conn = sqlite3.connect(str(sp))
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('ledger_cut_over', '1')")
    conn.commit()
    conn.close()
    return dw / "tasks.md"


def test_reprioritise_cli_changes_band_and_records_why_in_history(tmp_path, capsys):
    """#627 DIRECTION-1: a band change that CANNOT be expressed today, then the
    verb doing it — and the --why lands in the task's OWN HISTORY, not just the
    field. A test asserting only the new value passes against a verb that
    silently drops the reason (the brief's explicit trap).

    PRODUCTION LINE: the body append in reprioritise_task (surfaced via the
    CLI dispatch _reprioritise_store). Break by dropping the body append —
    the field still changes but 'focus shift' vanishes from the body.
    """
    ledger_path = _cut_over_store(tmp_path)
    # File a task at P2 via the store path so the fixture is realistic.
    ledger.main(["file", "a task", "--priority", "P2", "--ledger", str(ledger_path)])
    capsys.readouterr()  # drain file output

    # DIRECTION-1 precondition: before the verb, --priority existed ONLY on
    # `file`. There was NO way to change it. Demonstrate by confirming the
    # task is at its filed band and the body has no reprioritise note yet.
    recs = ledger._read_records(str(ledger_path.parent))
    tid = recs[0]["id"]
    assert recs[0]["priority"] == "P2", "precondition: filed at P2"
    assert "reprioritised" not in recs[0]["body"]

    rc = ledger.main(["reprioritise", str(tid), "P1", "--why", "focus shift",
                      "--ledger", str(ledger_path)])
    assert rc == 0, f"reprioritise must exit 0, got {rc}"
    out = capsys.readouterr().out
    assert "reprioritised" in out and "P1" in out

    # THE THING THAT MAKES THE VERB SAFE: the why lands in the body.
    recs = ledger._read_records(str(ledger_path.parent))
    match = [r for r in recs if r["id"] == tid][0]
    assert match["priority"] == "P1", f"band must change to P1, got {match['priority']}"
    assert "focus shift" in match["body"], (
        "the --why must land in the body — an unexplained priority change is "
        "how a backlog stops being trustworthy (#627)")


def test_unblock_cli_clears_blocked_on_and_records_why_in_history(tmp_path, capsys):
    """#627 DIRECTION-1: an unblock that CANNOT be expressed today (there was NO
    verb to clear blocked_on), then the verb doing it, with --why in history.

    PRODUCTION LINE: the body append in unblock_task. Break by dropping it —
    blocked_on clears but the reason vanishes.
    """
    ledger_path = _cut_over_store(tmp_path)
    # File a blocked task. file_task accepts blocked_on as a kwarg, but the CLI
    # `file` verb does not expose it — set it directly via the store writer.
    sp = ledger.store_path(str(ledger_path.parent))
    with ledger.open_database(
            ledger.task_store_spec(sp), access=ledger.Access.WRITE) as store:
        tid = ledger_write.file_task(
            store, "blocked task", "body", blocked_on="blocked on #999")
    capsys.readouterr()

    # DIRECTION-1 precondition: there was NO verb to clear blocked_on.
    recs = ledger._read_records(str(ledger_path.parent))
    match = [r for r in recs if r["id"] == tid][0]
    assert match["blocked_on"] == "blocked on #999", "precondition: blocked"

    rc = ledger.main(["unblock", str(tid), "--why", "#999 landed",
                      "--ledger", str(ledger_path)])
    assert rc == 0, f"unblock must exit 0, got {rc}"

    recs = ledger._read_records(str(ledger_path.parent))
    match = [r for r in recs if r["id"] == tid][0]
    assert match["blocked_on"] is None, f"blocked_on must clear, got {match['blocked_on']!r}"
    assert "#999 landed" in match["body"], (
        "the --why must land in the body — the reason an unblock happened is "
        "the thing that keeps a backlog trustworthy (#627)")


def test_reprioritise_cli_bad_band_is_exit2_no_traceback(tmp_path, capsys):
    """#627 DIRECTION-2: an invalid band (P9) must refuse, not write garbage.
    Exit 2 + one-line stderr naming the live bands, not a sqlite traceback.
    """
    ledger_path = _cut_over_store(tmp_path)
    ledger.main(["file", "a task", "--priority", "P2", "--ledger", str(ledger_path)])
    capsys.readouterr()
    tid = ledger._read_records(str(ledger_path.parent))[0]["id"]

    rc = ledger.main(["reprioritise", str(tid), "P9", "--why", "x",
                      "--ledger", str(ledger_path)])
    assert rc == 2, f"a bad band must exit 2, got {rc}"
    err = capsys.readouterr().err
    assert "priority: got 'P9'" in err and "expected one of" in err, err
    assert "Traceback" not in err
    # The band was NOT changed.
    recs = ledger._read_records(str(ledger_path.parent))
    assert [r for r in recs if r["id"] == tid][0]["priority"] == "P2"


def test_unblock_cli_never_blocked_refuses_not_success(tmp_path, capsys):
    """#671: an unblock that unblocked nothing must NOT read as success. A task
    that was never blocked refuses (exit 1, named message), not exit 0.
    """
    ledger_path = _cut_over_store(tmp_path)
    ledger.main(["file", "never blocked", "--ledger", str(ledger_path)])
    capsys.readouterr()
    tid = ledger._read_records(str(ledger_path.parent))[0]["id"]
    assert ledger._read_records(str(ledger_path.parent))[0]["blocked_on"] is None

    rc = ledger.main(["unblock", str(tid), "--why", "x", "--ledger", str(ledger_path)])
    assert rc == 1, f"unblocking an un-blocked task must refuse (exit 1), got {rc}"
    err = capsys.readouterr().err
    assert "not blocked" in err, (
        f"the refusal must name that it was not blocked (#671): {err!r}")


def test_reprioritise_cli_nonexistent_id_is_exit1(tmp_path, capsys):
    """DIRECTION-2: a nonexistent id refuses (exit 1), matching the #497 contract."""
    ledger_path = _cut_over_store(tmp_path)
    rc = ledger.main(["reprioritise", "99999", "P1", "--why", "x",
                      "--ledger", str(ledger_path)])
    assert rc == 1
    assert "no such task" in capsys.readouterr().err


def test_reprioritise_cli_missing_why_is_argparse_error(tmp_path, capsys):
    """--why is mandatory: omitting it is an argparse error (exit 2), not a
    silent acceptance that drops the reason."""
    ledger_path = _cut_over_store(tmp_path)
    with pytest.raises(SystemExit) as ei:
        ledger.main(["reprioritise", "1", "P1", "--ledger", str(ledger_path)])
    assert ei.value.code == 2  # argparse uses 2 for a missing required arg


def test_retitle_cli_changes_title_and_records_why_in_history(tmp_path, capsys):
    """#731: title changes and the mandatory reason survives in history."""
    ledger_path = _cut_over_store(tmp_path)
    ledger.main(["file", "stale title", "--ledger", str(ledger_path)])
    capsys.readouterr()
    tid = ledger._read_records(str(ledger_path.parent))[0]["id"]

    rc = ledger.main([
        "retitle", str(tid), "current title", "--why", "the ruling landed",
        "--ledger", str(ledger_path)])
    assert rc == 0
    assert "retitled" in capsys.readouterr().out
    rec = ledger._read_records(str(ledger_path.parent))[0]
    assert rec["title"] == "current title"
    assert "stale title" in rec["body"]
    assert "current title" in rec["body"]
    assert "the ruling landed" in rec["body"]
    store = ledger.ledger_store.open_store(ledger.store_path(ledger_path.parent))
    try:
        event = store.conn.execute(
            "SELECT cause, detail FROM task_event WHERE task_id = ? "
            "ORDER BY ordinal DESC LIMIT 1", (tid,)).fetchone()
    finally:
        store.close()
    assert event == ("reconciled", "the ruling landed"), (
        "retitle must record its why in the machine-readable history too")


def test_retitle_cli_same_title_refuses_not_success(tmp_path, capsys):
    """DIRECTION 1: a retitle that changes nothing must refuse (#671)."""
    ledger_path = _cut_over_store(tmp_path)
    ledger.main(["file", "already current", "--ledger", str(ledger_path)])
    capsys.readouterr()
    before = ledger._read_records(str(ledger_path.parent))[0]
    tid = before["id"]
    store = ledger.ledger_store.open_store(ledger.store_path(ledger_path.parent))
    try:
        events_before = store.conn.execute(
            "SELECT COUNT(*) FROM task_event WHERE task_id = ?", (tid,)).fetchone()[0]
    finally:
        store.close()

    rc = ledger.main([
        "retitle", str(tid), "already current", "--why", "mistaken call",
        "--ledger", str(ledger_path)])
    captured = capsys.readouterr()
    assert rc == 1, f"same-title retitle must refuse (exit 1), got {rc}"
    assert captured.out == "", f"refusal must not report success: {captured.out!r}"
    assert "title is unchanged" in captured.err
    after = ledger._read_records(str(ledger_path.parent))[0]
    assert after["title"] == before["title"]
    assert after["body"] == before["body"]
    store = ledger.ledger_store.open_store(ledger.store_path(ledger_path.parent))
    try:
        events_after = store.conn.execute(
            "SELECT COUNT(*) FROM task_event WHERE task_id = ?", (tid,)).fetchone()[0]
    finally:
        store.close()
    assert events_after == events_before, "a refused retitle must append no event"


def test_retitle_cli_missing_why_is_argparse_error(tmp_path):
    """--why is parser-required, matching reprioritise and unblock (#627)."""
    ledger_path = _cut_over_store(tmp_path)
    with pytest.raises(SystemExit) as ei:
        ledger.main([
            "retitle", "1", "new title", "--ledger", str(ledger_path)])
    assert ei.value.code == 2


def test_retitle_allows_a_changed_title_that_still_claims_blockedness(
        tmp_path, capsys):
    """DIRECTION 2: retitle is a writer, not a second copy of lint #725.

    A changed title may still contradict empty blocked_on; the existing lint
    warning remains the authority that exposes that choice. Refusing here
    would couple a general writer to one current lint idiom and second-guess
    an author who supplied a mandatory reason.
    """
    ledger_path = _cut_over_store(tmp_path)
    ledger.main([
        "file", "blocked on his ruling", "--ledger", str(ledger_path)])
    capsys.readouterr()
    tid = ledger._read_records(str(ledger_path.parent))[0]["id"]

    rc = ledger.main([
        "retitle", str(tid), "still blocked on his ruling", "--why",
        "author confirms it remains blocked", "--ledger", str(ledger_path)])
    assert rc == 0
    rec = ledger._read_records(str(ledger_path.parent))[0]
    assert rec["title"] == "still blocked on his ruling"
    assert rec["blocked_on"] is None, (
        "constructed false-green: retitle succeeds while #725 still warns")
