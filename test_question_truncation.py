"""#632 — a dashboard `/answer` deleted 12 answered entries from questions.md.

THE REGRESSION IS REAL, NOT INVENTED. The payload below is the exact body of
the POST that did it, recovered verbatim from `.dreamwork/submissions.log`
(`2026-07-31T17:03:02`, `/answer`, 717 bytes) — his words, his typo, his
backticks. A synthetic payload would have proved that some answer is safe;
this one proves that THE answer that destroyed the file is.

WHAT ACTUALLY HAPPENED, because the shape of it is what the tests pin:

`_handle_answer` did read → mutate → write, and the read was `read_text`,
which caps at 200,000 characters and says nothing when it cuts. questions.md
was 230,876 characters. So the handler appended his answer to the first
200,000 characters of the file and wrote that back over all of it. The
evidence was threefold and agreed: the damaged file ended mid-word
("…Therefore the durable que"), which no retention policy produces; replaying
this payload against `base[:200_000]` reproduces the damaged length of
200,366 characters exactly; and the `## Open` section GREW by 407 characters
while `## Answered` lost 30,875 — a gain at the head with a loss at the tail
is a short read, not a delete.

The "twelve OLDEST entries" reading was a misdirection worth recording:
`## Answered` is newest-first, so the oldest entries live at the END of the
file. Oldest-deleted and tail-truncated are the same event seen from two
directions, and only one of them suggests the right cause.

Each test names the production line it defends, and each was red-proofed by
reverting that line and watching this file fail.
"""

import importlib.util
import os

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "watch_under_test", os.path.join(os.path.dirname(__file__), "watch.py"))
watch = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(watch)


# The exact recovered POST body (submissions.log, 2026-07-31T17:03:02).
REAL_TITLE = ("P1 · 2026-07-31 17:00 — #591: claude-design compatibility does "
              "NOT cost the single render authority — one ruling makes it "
              "official.")
REAL_ANSWER = (
    "1. rec (prioritize replacing old inline-html in watch.py with new UI "
    "components at the earliest suitable time)\n2. rec\n3. rec\n\nnote re "
    "`16:38 goals refute \"no components\"`, we should update any references "
    "to this (no compoinents ruling) to say new ruling is transition to "
    "component-based react webui."
)
REAL_STAMP = "2026-07-31 17:03"

ANSWERED_TOTAL = 63          # what the file held at commit 5fc09bab, 16:57


def _oversized_questions():
    """A questions.md shaped like the real one and past the 200,000 cap.

    Newest-first `## Answered`, exactly as the file is written, so the entries
    a truncating read destroys are the ones at the bottom — which is what
    makes "oldest" and "truncated" indistinguishable by symptom.

    The padding is per-entry body text rather than one blob at the end: the
    cut has to land INSIDE the answered section for this to reproduce the
    reported failure, not past everything that matters.
    """
    out = ["# Questions for the human", "", "## Open", "",
           f"- **{REAL_TITLE}** **Sub-decisions:** `Q1`, `Q2`, `Q3`.",
           "  The open entry his answer attaches to.", "",
           "## Answered", ""]
    for i in range(ANSWERED_TOTAL):
        out.append(f"- **P1 · 2026-07-{25 + (i % 6):02d} — #{900 + i} entry {i}**")
        out.append(f"  → answered (2026-07-{25 + (i % 6):02d}10:00): resolved.")
        for j in range(50):
            out.append(f"  Body line {j} of entry {i}; "
                       f"padding that carries the file past the cap.")
        out.append("")
    text = "\n".join(out) + "\n"
    assert len(text) > 200_000, f"fixture must exceed the cap, got {len(text)}"
    return text


def _answered_titles(text):
    return [it["title"] for it in watch.parse_answered(text)]


def test_the_bug_itself_the_capped_read_destroys_the_tail():
    """THE DEFECT, pinned so the fix cannot be quietly undone.

    This is the OLD code path spelled out: `read_text`'s bounded result fed
    into `append_answer`. It must still lose entries — if this test ever goes
    green it means the 200,000 cap moved rather than the read path changing,
    which is the "raise the number" non-fix that just moves the cliff.
    Defends: watch.py `read_text`'s limit being a DISPLAY concern only.
    """
    full = _oversized_questions()
    truncated = full[:200_000]                       # what read_text returned
    damaged, matched = watch.append_answer(
        truncated, REAL_TITLE, REAL_ANSWER, REAL_STAMP)
    assert matched, "his answer still attaches; that was never the problem"
    survived = _answered_titles(damaged)
    assert len(survived) < ANSWERED_TOTAL, (
        "the capped read must still demonstrate loss, else this fixture no "
        "longer reproduces #632")
    # THE SIGNATURE: what vanishes is a contiguous run at the END of the
    # section — the tail — and the survivors are an unbroken prefix of the
    # original order. That is what a cut looks like, and it is what made
    # "the twelve oldest" the misleading description of a truncation.
    original = _answered_titles(full)
    assert survived == original[:len(survived)], (
        "loss must be a clean tail cut, not a scattered delete")


def test_real_payload_through_the_write_door_loses_nothing(tmp_path):
    """THE FIX. The exact POST that destroyed the file, replayed.

    Defends: `rewrite_append_only` reading through `read_text_full`
    (watch.py). Red-proof: change that call back to `read_text` and this fails
    with 12 answered entries missing — the original incident, reproduced.
    """
    qpath = tmp_path / "questions.md"
    full = _oversized_questions()
    qpath.write_text(full, encoding="utf-8")
    before = _answered_titles(full)

    status, value = watch.rewrite_append_only(
        str(qpath),
        lambda text: watch.append_answer(text, REAL_TITLE, REAL_ANSWER,
                                         REAL_STAMP))

    assert status == "ok", f"the write must be accepted, got {status!r} {value!r}"
    after_text = qpath.read_text(encoding="utf-8")
    after = _answered_titles(after_text)
    assert after == before, (
        f"#632: {len(before) - len(after)} answered entries lost through the "
        f"write door")
    assert len(after) == ANSWERED_TOTAL
    # his words landed, and the file grew rather than shrank
    assert "compoinents" in after_text, "his answer must be in the file"
    assert len(after_text) > len(full)


def test_comment_on_an_oversized_file_loses_nothing(tmp_path):
    """/comment shares the defect and therefore shares the door.

    Defends: the `rewrite_append_only` call in `_handle_comment`. A fix that
    only covered /answer would leave an identical loss one route away.
    """
    qpath = tmp_path / "questions.md"
    full = _oversized_questions()
    qpath.write_text(full, encoding="utf-8")
    before = _answered_titles(full)
    status, _ = watch.rewrite_append_only(
        str(qpath),
        lambda text: watch.append_comment(text, REAL_TITLE, "a follow-up note",
                                          REAL_STAMP, "Open"))
    assert status == "ok"
    assert _answered_titles(qpath.read_text(encoding="utf-8")) == before


def test_write_door_refuses_a_mutation_that_drops_a_line(tmp_path):
    """THE BACKSTOP. A lossy mutation is refused, not written.

    Defends: the `first_lost_line` check inside `rewrite_append_only`. The
    file on disk must be untouched — a refusal that still wrote would be
    worse than no check, because it would report safety it did not deliver.
    """
    qpath = tmp_path / "questions.md"
    full = _oversized_questions()
    qpath.write_text(full, encoding="utf-8")

    status, dropped = watch.rewrite_append_only(
        str(qpath), lambda text: (text[:200_000], True))

    assert status == "lossy", "a truncating mutation must be refused"
    assert dropped and dropped.strip(), "the refusal names the line it saved"
    assert qpath.read_text(encoding="utf-8") == full, (
        "a refused write must leave the file byte-identical")


def test_missing_and_unmatched_are_distinct_from_loss(tmp_path):
    """The door keeps 404 and 409 separable from a refusal.

    Defends: the status mapping in `_handle_answer` / `_handle_comment`.
    Collapsing these would tell him "not found" when the truth is "refused to
    destroy your file", which is the wrong thing to act on.
    """
    missing = tmp_path / "nope.md"
    assert watch.rewrite_append_only(
        str(missing), lambda t: (t, True))[0] == "missing"

    qpath = tmp_path / "questions.md"
    qpath.write_text(_oversized_questions(), encoding="utf-8")
    status, _ = watch.rewrite_append_only(
        str(qpath),
        lambda text: watch.append_answer(text, "no such entry title", "x",
                                         REAL_STAMP))
    assert status == "unmatched"


@pytest.mark.parametrize("old,new,expect_lost", [
    ("a\nb\nc\n", "a\nb\nc\n", None),                    # unchanged
    ("a\nb\nc\n", "a\nNEW\nb\nc\n", None),               # pure insertion
    ("a\nb\nc\n", "a\nb\n", "c"),                        # tail truncated
    ("a\nb\nc\n", "a\nc\n", "b"),                        # middle deleted
    ("a\nb\nc\n", "c\nb\na\n", "b"),                     # reordered
    ("a\n\n\nb\n", "a\n\nb\n", None),                    # blank-line collapse
])
def test_first_lost_line_is_a_subsequence_test(old, new, expect_lost):
    """Defends: `first_lost_line`'s two-pointer subsequence walk.

    The blank-line row is the one that stops this being a whole-line equality
    check: `append_human_question` legitimately collapses trailing blanks, and
    a stricter rule would refuse a correct write. The reorder row is why it is
    a subsequence rather than a set test — a set would call a scramble safe.
    """
    assert watch.first_lost_line(old, new) == expect_lost


def test_a_fold_IS_refused_and_that_is_the_scope_boundary():
    """A fold does NOT pass this guard, deliberately — read this before reusing it.

    I checked rather than assumed, and the first version of this test asserted
    the opposite and failed. A fold moves an entry from `## Open` to the top of
    `## Answered`, which moves entry lines ACROSS the section header and past
    the entries left behind. Relative order changes, so a subsequence test
    flags it. There is no way to have both a check strong enough to catch a
    partial deletion and one blind to arbitrary reordering.

    That makes this a SCOPED invariant, not a universal one, and the scope is
    the whole reason it is safe to arm: `rewrite_append_only` is the door for
    the three HTTP routes (/ask, /answer, /comment), and none of them folds.
    Folding is the loop editing the file directly, which never passes through
    here.

    So this test exists to fail loudly if anyone ever wires a fold — or any
    other reordering rewrite — through this door. Doing so is a design error,
    and it should be caught by a red test rather than by the guard refusing a
    legitimate write in production at 3am.
    """
    before = ("## Open\n\n- **entry X**\n  its body\n\n## Answered\n\n"
              "- **entry Y**\n  y body\n")
    folded = ("## Open\n\n## Answered\n\n- **entry X**\n  its body\n\n"
              "- **entry Y**\n  y body\n")
    assert watch.first_lost_line(before, folded) == "## Answered", (
        "a fold reorders and is therefore refused; if this ever returns None "
        "the guard has been weakened and no longer catches partial deletion")


def test_read_text_full_returns_more_than_the_capped_read(tmp_path):
    """Defends: `read_text_full` existing and being unbounded.

    Without this the two readers could drift to the same behaviour and every
    other test here would still pass while protecting nothing.
    """
    p = tmp_path / "big.md"
    body = _oversized_questions()
    p.write_text(body, encoding="utf-8")
    assert len(watch.read_text(str(p))) == 200_000
    assert watch.read_text_full(str(p)) == body
