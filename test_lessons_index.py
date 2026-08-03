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


def test_red_proof_slice_is_truncation_detectable():
    """#1033: the red-proof slice is the loop's largest (hundreds of lines),
    and a reader (an agent harness) that receives a truncated prefix has no
    way to tell it is incomplete — the consultation looks performed. The act
    output must let a caller that received a partial slice detect it.

    The mechanism: a header states the magnitude up front (a truncated read
    still has the header), and a trailing sentinel restating the lesson count
    is the presence-check a truncated read loses. Absence of the sentinel IS
    the truncation signal.

    The sentinel's stated count must equal the lessons actually emitted: a
    count that lies makes a truncated read look complete, which is worse than
    no count at all (#1033 Direction 2). Tested against the REAL slice, not a
    synthetic handful, because a three-lesson act would prove nothing about
    the case that is the entire point (#136: a check that can pass on a
    trivial population is not a check).
    """
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        li.main(["--act", "red-proof", "--all", "--lessons", str(LESSONS)])
    out = buf.getvalue()
    lines = out.split("\n")

    # Actual count of lessons emitted — one `lessons.md:N` cite per entry.
    actual = len(re.findall(r"(?m)^lessons\.md:\d+$", out))

    # Precondition: the slice is genuinely large. The whole defect is that
    # red-proof overflows its reader; a regression that shrank it to a
    # handful would make this test prove nothing about truncation (#136).
    assert actual > 10, (
        f"precondition failed: red-proof matched only {actual} lessons — "
        "the slice is too small for this test to discriminate truncation; "
        "re-derive the population before trusting this gate"
    )

    # Direction 1: the sentinel must be present — a truncated reader loses
    # it, so its absence is the detectable truncation signal.
    sentinels = [l for l in lines if l.startswith("# end red-proof")]
    assert sentinels, (
        "no `# end red-proof` sentinel — a reader that received a prefix "
        "cannot tell it is incomplete; truncation is silent (#1033)"
    )

    # The sentinel must be the FINAL non-blank line. If anything trails it, a
    # truncation that cuts after the sentinel still leaves a present sentinel
    # and is undetectable.
    nonblank = [l for l in lines if l.strip()]
    assert nonblank[-1].startswith("# end red-proof"), (
        "the sentinel is not the final line — truncation after it would "
        "leave the sentinel present and the read would still look complete"
    )

    # Direction 2: the sentinel's stated lesson count must equal the lessons
    # actually emitted. A count that does not match makes a partial read look
    # whole, which is the false-green this whole task exists to close.
    m = re.search(r"(\d+) lessons", sentinels[-1])
    assert m, f"sentinel {sentinels[-1]!r} carries no lesson count"
    stated = int(m.group(1))
    assert stated == actual, (
        f"sentinel states {stated} lessons but {actual} were emitted — a "
        "mismatched count makes a truncated read look complete (#1033 "
        "Direction 2)"
    )

    # The header up front must state the same count, so a reader that still
    # has the header (truncation cuts the end, not the start) knows the
    # magnitude even before checking for the sentinel.
    header = lines[0]
    mh = re.search(r"(\d+) of \d+ lessons", header)
    assert mh, f"header {header!r} carries no 'N of M lessons' count"
    assert int(mh.group(1)) == actual, (
        f"header states {mh.group(1)} lessons but {actual} were emitted"
    )


def test_bounded_act_reports_every_omission_and_exact_recovery_command(tmp_path):
    """#1194: a cap without an omission count is silent truncation."""
    fixture = tmp_path / "many-clock-lessons.md"
    fixture.write_text(
        "\n".join(
            f"- **Clock lesson {n} governs elapsed time.**\n"
            f"  Evidence {n}: a timestamp was trusted without measurement."
            for n in range(li.DEFAULT_ACT_LIMIT + 2)
        ) + "\n",
        encoding="utf-8",
    )
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = li.main(["--act", "clock", "--lessons", str(fixture)])
    assert rc == 0
    out = buf.getvalue()

    shown = len(re.findall(r"(?m)^lessons\.md:\d+$", out))
    assert shown == li.DEFAULT_ACT_LIMIT, "the default act slice was not capped"
    for n in range(li.DEFAULT_ACT_LIMIT):
        assert f"Evidence {n}:" in out, "the cap dropped a shown lesson's evidence"
    expected = (
        "# omitted: 2 more matching lessons — run "
        f"`python3 dev/lessons_index.py --act clock --all --lessons {fixture}` "
        f"to see all {li.DEFAULT_ACT_LIMIT + 2}"
    )
    assert expected in out, (
        "the bounded act silently omitted lessons or did not print the exact "
        "command that retrieves them"
    )

    all_buf = io.StringIO()
    with contextlib.redirect_stdout(all_buf):
        all_rc = li.main([
            "--act", "clock", "--all", "--lessons", str(fixture),
        ])
    all_out = all_buf.getvalue()
    assert all_rc == 0
    assert len(re.findall(r"(?m)^lessons\.md:\d+$", all_out)) == (
        li.DEFAULT_ACT_LIMIT + 2
    ), "the printed --all recovery command does not retrieve every match"
    assert "# omitted:" not in all_out


def test_empty_act_emits_no_uncounted_blank_line(tmp_path):
    """#1033 r2 (P2): the count the header and sentinel state must equal the
    lines actually emitted — even at zero. An act with no lessons declared
    ``0 lines`` yet printed one blank line (``print("\\n".join([]))`` emits a
    newline), so the stated magnitude lied about the received body. That is
    the same defect class this task exists to close: a stated count that does
    not equal what was emitted (#1033 Direction 2, at its degenerate zero).

    No real act is empty today, so this uses a controlled fixture — but the
    fixture is the PRECONDITION (an entry that matches one act but not the
    one asked for), not the thing under test. The thing under test is the
    emission path in ``main()``: the ``print("\\n".join(body_lines))`` line
    is the production line that would have to change for this to fail. The
    test calls ``li.main`` for real, so an empty-body print reaches that line.
    """
    # A single lesson that matches worktree-dispatch but never 'clock' — so
    # --act clock yields zero hits against a non-empty file (the denominator
    # is real, the numerator is genuinely zero).
    fixture = tmp_path / "empty_act.md"
    fixture.write_text(
        "- **Dispatching a lane is a worktree act.**\n"
        "  Some prose about lanes.\n",
        encoding="utf-8",
    )
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = li.main(["--act", "clock", "--lessons", str(fixture)])
    assert rc == 0, "a known act with zero hits exits 0, not an error"
    out = buf.getvalue()
    parts = out.split("\n")

    # Header is first, sentinel is the first `# end ...` line.
    header = parts[0]
    assert header.startswith("# act: clock"), f"unexpected header {header!r}"
    sent_idx = next(
        (i for i, p in enumerate(parts) if p.startswith("# end clock")), None
    )
    assert sent_idx is not None, "no `# end clock` sentinel emitted"
    # Lines strictly between the header and the sentinel.
    between = parts[1:sent_idx]

    # The invariant the whole format exists to hold: stated line count equals
    # lines actually emitted. At zero this means NOTHING sits between the
    # header and the sentinel — not even one blank line.
    m = re.search(r"(\d+) lines", header)
    assert m, f"header {header!r} carries no line count"
    stated = int(m.group(1))
    assert stated == len(between), (
        f"header states {stated} lines but {len(between)} line(s) were "
        f"emitted between header and sentinel {between!r} — a stated count "
        "that does not match the received body is the false-green #1033 "
        "exists to close, and the zero case is the one nobody exercises"
    )
    # And state the zero property directly so the intent is unmissable.
    assert stated == 0, "this fixture must produce zero hits; precondition"


def test_act_output_survives_a_truncating_reader():
    """#1033 r2 (P3): this command exists BECAUSE readers truncate it, and
    ``| head`` is the most likely way a caller does that. Piping into a reader
    that exits early must not leave a producer-side ``BrokenPipeError``
    traceback on stderr (nor exit 120) — a traceback on the intended usage
    undermines the fix's credibility even though truncation detection itself
    is unaffected.

    This cannot be exercised with an ``io.StringIO`` redirect (a StringIO
    never breaks), so it runs the real CLI as a subprocess, reads one line,
    and closes the pipe — exactly what ``head`` does. The production line is
    the ``__main__`` guard's ``sys.exit(main())``: the BrokenPipeError raised
    by a ``print`` inside ``main()`` must be caught there, not traced.
    """
    import subprocess
    import sys as _sys
    # The red-proof slice is ~84KB, well past a 64KB pipe buffer, so a reader
    # that takes one line and exits guarantees the producer's next write hits
    # a closed pipe. A tiny act would fit in the buffer and never break,
    # making this test hollow (#136). Assert the precondition against the real
    # corpus so a future shrink is caught, not silently passed over.
    #
    # A faithful two-process pipeline (producer | head) is required: closing
    # only the parent's read fd does NOT reproduce the bug, because the
    # producer never observes a reader that *exited*. The break happens when a
    # downstream reader (head) closes ITS stdin, exactly the `| head` usage.
    prod = subprocess.Popen(
        [_sys.executable, "dev/lessons_index.py",
         "--act", "red-proof", "--lessons", str(LESSONS)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=str(HERE),
    )
    reader = subprocess.Popen(
        ["head", "-1"], stdin=prod.stdout, stdout=subprocess.DEVNULL,
    )
    # Release the parent's read fd so the producer's only reader is `head`;
    # when head exits after one line, the producer's next write has nowhere
    # to go.
    prod.stdout.close()
    try:
        prod.wait(timeout=30)
        reader.wait(timeout=30)
    finally:
        if prod.poll() is None:
            prod.kill()
            prod.wait()
        if reader.poll() is None:
            reader.kill()
            reader.wait()
    stderr = prod.stderr.read().decode("utf-8", "replace")
    assert "BrokenPipeError" not in stderr, (
        "piping the act output into a truncating reader left a "
        f"BrokenPipeError traceback on stderr:\n{stderr}"
    )
    assert "Traceback" not in stderr, (
        "piping the act output into a truncating reader left a traceback "
        f"on stderr:\n{stderr}"
    )


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
