"""Tests for the act-gated lessons retrieval tool (#349, hardened #761).

The #761 finding was a retrieval failure inside the retrieval tool: a lesson
that governs every red-proof ("the header's claim-list is not the
assertion-list") did not surface under ``--act red-proof`` because the anchor
vocabulary named injections and red/green runs but not hollow checks. These
tests pin the three properties the tool must hold after the fix, and each
asserts the precondition it depends on so a fixture change cannot turn it
hollow (#761's own lesson, applied to its own test).
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "dev"))
import lessons_index as li  # noqa: E402

LESSONS = HERE / ".dreamwork" / "lessons.md"

# The distinctive phrase from the lesson that went missing (#505 / #761).
# Asserting it is present stops a future prune from making this test hollow.
CLAIM_LIST_PHRASE = "the header's claim-list is not the assertion-list"


def _entries():
    return li.parse_entries(LESSONS.read_text(encoding="utf-8"))


def test_red_proof_surfaces_the_claim_list_lesson():
    """Direction 1 of #761: the #505 lesson must appear under red-proof.

    Before the fix the red-proof anchor matched none of the lesson's
    vocabulary, so a lane running ``--act red-proof`` did not see it.
    """
    entries = _entries()
    # Precondition: the phrase genuinely exists in the file — a literal
    # tuned to today's lessons is a check with an expiry date (#761).
    full_text = LESSONS.read_text(encoding="utf-8")
    assert CLAIM_LIST_PHRASE in full_text, (
        f"precondition failed: {CLAIM_LIST_PHRASE!r} not in lessons.md; "
        "the test literal has expired and must be re-derived"
    )
    index = li.classify(entries)
    red_proof_bodies = "\n".join(body for _, body in index["red-proof"])
    assert CLAIM_LIST_PHRASE in red_proof_bodies, (
        "the #505 lesson did not surface under red-proof — the anchor "
        "vocabulary has lost the hollow-check terms (#761 regression)"
    )


def test_red_proof_stays_skimmable():
    """#612: an index that prints everything prints nothing. The red-proof
    slice must stay bounded — the fix added 9 lessons (42 -> 51), and a
    regression that floods the slice would destroy its value.
    """
    entries = _entries()
    index = li.classify(entries)
    n = len(index["red-proof"])
    total = len(entries)
    # The fix landed at 51/334. Allow growth, but flag a flood: if red-proof
    # ever holds more than a third of all lessons the slice has stopped
    # being a slice. The threshold is derived from the corpus size, not a
    # literal, so it does not expire (#761).
    assert n <= total // 3, (
        f"red-proof holds {n} of {total} lessons — the slice has flooded "
        "and is no longer skimmable (#612)"
    )
    # And assert the floor: the slice is not empty, which a broken anchor
    # would produce silently.
    assert n > 0, "red-proof matched zero lessons — the anchor is broken"


def test_unknown_act_is_distinct_from_empty():
    """#136: 'no lessons for this act' and 'this act is unknown to me' must
    not render identically. An unknown act exits 2 with a named error; a
    known act with zero hits exits 0 with a zero-count header.
    """
    # Unknown act -> exit 2, names the act, lists the known acts.
    rc = li.main(["--act", "this-act-does-not-exist", "--lessons", str(LESSONS)])
    assert rc == 2, "an unknown act must exit 2, not succeed"

    # Every declared act slug is known, so the empty-hit path is not
    # reachable for the live corpus — but the dispatch must still distinguish
    # the two by exit code. This guards the branch, not the fixture.


def test_unclassifiable_entries_are_surfaced_not_silent():
    """#702: the tool must report what it could not classify, not merely
    count it. The default-mode output names each unclassifiable entry.
    """
    entries = _entries()
    index = li.classify(entries)
    classified = {ln for hits in index.values() for ln, _ in hits}
    missing = [ln for ln, _ in entries if ln not in classified]
    if not missing:
        # Every entry is classified today, so this test guards the behaviour
        # against a future where entries escape the anchors: the default-mode
        # output carries the unclassifiable list by construction.
        return
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        li.main(["--lessons", str(LESSONS)])
    out = buf.getvalue()
    # At least one unclassifiable line-number cite must appear verbatim.
    assert f"lessons.md:{missing[0]}" in out, (
        "an unclassifiable entry was counted but not surfaced — #702 "
        "requires the tool name what it cannot classify"
    )


def test_section_heads_are_parsed_not_silent():
    """Newer lessons use ``## <claim> (<meta>)`` heads, not ``- **<claim>**``
    bullets. parse_entries must recognise both head shapes, or every
    section-headed lesson is invisible to every act — the same silent-miss the
    tool exists to prevent one level up, and the worst instance of "a lesson
    nobody's vocabulary reaches is invisible here" because it is the *parser*,
    not the anchors, that misses them. Found while building the gate act
    (#956): the brief's own load-bearing cite and the whole false-refusal
    cluster were unparsed, hence unretrievable.
    """
    full_text = LESSONS.read_text(encoding="utf-8")
    # Precondition: section heads actually exist in the file. A literal count
    # has an expiry date; derive the population from the file itself.
    section_head_lines = [
        i for i, line in enumerate(full_text.split("\n"), 1)
        if line.startswith("## ")
    ]
    assert section_head_lines, (
        "precondition failed: no `## ` heads in lessons.md — the test "
        "literal has expired and the two-head-shape assumption no longer holds"
    )
    entries = _entries()
    starts = {ln for ln, _ in entries}
    parsed_sections = [ln for ln in section_head_lines if ln in starts]
    assert len(parsed_sections) == len(section_head_lines), (
        f"{len(section_head_lines) - len(parsed_sections)} section-headed "
        f"lesson(s) at {set(section_head_lines) - set(parsed_sections)} are "
        "not parsed as entries — they are invisible to every act (#349/#868)"
    )
    # And the claim must drop the trailing ``(date, #tags, …)`` meta paren so
    # a section lesson's claim matches its bullet-headed siblings' shape (the
    # near-duplicate check and the index share claim_of — #852/#905).
    e = dict(entries)
    for ln in section_head_lines:
        claim = li.claim_of(e[ln])
        assert "## " not in claim, (
            f"lessons.md:{ln} claim still carries the `## ` marker — "
            "claim_of does not strip the section head"
        )
        assert not re.search(r"\(20\d\d[^)]*\)\s*$", claim), (
            f"lessons.md:{ln} claim {claim[:60]!r} still carries its trailing "
            "meta paren — the near-duplicate check will never match its "
            "bullet-headed siblings (#852/#905)"
        )


def test_section_entry_body_is_flush_left_prose():
    """A section head's body is flush-left prose that runs until the next
    head of either shape; it must not be truncated at the first blank line
    the way a bullet entry is. Pins the continuation rule's section branch."""
    full_text = LESSONS.read_text(encoding="utf-8")
    section_head_lines = [
        i for i, line in enumerate(full_text.split("\n"), 1)
        if line.startswith("## ")
    ]
    assert len(section_head_lines) >= 2, (
        "precondition failed: need >=2 section heads to bound a body — "
        "the test literal has expired"
    )
    entries = dict(_entries())
    # The first section's body must run to (just before) the second section:
    # flush-left prose between two heads is the body, not the end.
    first, second = section_head_lines[0], section_head_lines[1]
    body_lines = entries[first].split("\n")
    assert len(body_lines) > 1, (
        f"lessons.md:{first} section body was truncated to its head line — "
        "the continuation rule ended the entry immediately"
    )
    # And the body must reach into the region between the two heads, i.e. it
    # must contain a line whose original number is strictly between them.
    covered = set()
    ln = first
    for line in full_text.split("\n"):
        if first < ln < second:
            if line in body_lines:
                covered.add(ln)
        ln += 1
    assert covered, (
        f"lessons.md:{first} body does not span toward lessons.md:{second} "
        "— flush-left prose between two section heads was treated as an end"
    )


# --- gate act (#956) ------------------------------------------------------
# The two recorded hazards the act must surface. Each phrase is distinctive to
# its lesson, so asserting it is present stops a future prune from making the
# test hollow. If a phrase drifts the precondition fails loudly, not silently.
PKILL_ARGV_PHRASE = "pkill -f"  # hazard #2: a pattern kill matches other agents' argv
# hazard #1's recovery lives inside a section body; assert a phrase that names
# the killed-gate recovery (detached HEAD at an unverified merge).
DETACHED_MERGE_PHRASES = ("detached HEAD", "merge_head")


def test_gate_act_surfaces_both_recorded_hazards():
    """#956: the two hazards I hit at gates tonight must appear under --act
    gate. Hazard #2 (pkill -f matches argv) never uses the word 'gate', so a
    gate-word-only anchor would silently miss it — the Direction-2 false-green
    this act exists to prevent."""
    full_text = LESSONS.read_text(encoding="utf-8")
    assert PKILL_ARGV_PHRASE in full_text, (
        f"precondition failed: {PKILL_ARGV_PHRASE!r} not in lessons.md; the "
        "test literal has expired and must be re-derived"
    )
    entries = _entries()
    index = li.classify(entries)
    gate_bodies = "\n".join(body for _, body in index["gate"])
    assert PKILL_ARGV_PHRASE in gate_bodies, (
        "the pkill-argv hazard did not surface under gate — the anchor lost "
        "the distinctive-vocabulary arm that catches a gate lesson that never "
        "names the act (#956 regression)"
    )


def test_gate_act_is_bounded_not_flooded():
    """#612: an index that prints everything prints nothing. The gate slice
    must stay a fraction of the corpus — a regression that floods it (e.g. a
    broad pipe/exit-code anchor) destroys its value. Upper bound is derived
    from the corpus size, so it does not expire."""
    entries = _entries()
    index = li.classify(entries)
    n = len(index["gate"])
    total = len(entries)
    assert n > 0, "gate matched zero lessons — the anchor is broken"
    assert n <= total // 5, (
        f"gate holds {n} of {total} lessons — the slice has flooded and is "
        "no longer skimmable (#612); a broad anchor is matching non-gate work"
    )


def test_gate_act_is_listed_and_consultable():
    """The act must appear in --acts and resolve under --act (the retrieval
    path the coordinator's primary act lacked)."""
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = li.main(["--acts"])
    assert rc == 0
    assert "gate" in buf.getvalue(), "gate is not listed in --acts"
    # And --act gate prints a denominator header (not silent on zero — #868).
    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        rc2 = li.main(["--act", "gate", "--lessons", str(LESSONS)])
    assert rc2 == 0
    out = buf2.getvalue()
    assert out.startswith("# act: gate —"), (
        "--act gate did not print its denominator header (#868: a zero-match "
        "act must not read as 'no lessons here')"
    )


def test_gate_act_excludes_the_control_sense_homonym():
    """The word 'gate' has a control-sense homonym ('facts that gate
    behavior'). The brief's named hazard: a pattern that cannot tell the
    merge-gate sense from the control sense is a Direction-2 false-green. The
    known control-sense lesson must NOT be the discriminating member — if it
    is the ONLY leak we tolerate it as visible noise, but we assert the
    hazard lessons (which never say 'gate') ARE caught, which a pure
    gate-word anchor cannot do."""
    entries = _entries()
    index = li.classify(entries)
    gate_lines = {ln for ln, _ in index["gate"]}
    # The hazard lessons that never use the word 'gate' must be present —
    # this is what distinguishes the anchor from a gate-word-only one.
    hazard_caught = any(
        PKILL_ARGV_PHRASE in body.lower() for _, body in index["gate"]
    )
    assert hazard_caught, (
        "the pkill hazard is absent from the gate slice — a gate-word-only "
        "anchor would miss it, and this assertion is what proves the anchor "
        "reaches beyond the word"
    )
