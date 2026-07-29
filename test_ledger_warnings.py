"""#357 — the CLI warning footer (red-first).

The footer every ``dev/ledger.py`` verb emits at exit (#357, design
``cli-warning-layer.md``). It rides **stderr** (stdout stays machine-clean),
is **WARN-only** (never changes an exit code, never blocks), and is
**stateless** (no memory between calls — the throttle fork was refuted).

Both forks were ruled before this lane started: the footer prints on EVERY
verb (Q5), and every verb carries the FULL line (Q6, I1) — not a terse hint.

This file owns ONLY the footer's contract. The store/markdown dispatch parity
lives in ``test_ledger_dispatch.py``; the footer concerns (stream, exit code,
reuse, quiet rules, the journal count) are narrower and need different
fixtures (a clean all-zero tree; a scratch journal seeded through
``receive()``), so they get a dedicated file rather than entangling the
parity suite.

REUSE, NEVER REBUILD — the load-bearing invariant the red-proofs target:
the footer calls the PRODUCTION readers (``store_ids_by_state``,
``lint.check_unfolded_answers``, ``watch.parse_open_answers`` /
``parse_open_questions``, ``open_journal`` + ``head_ordinal`` + ``cursor``).
A second copy of any count is the defect. Each red-proof names the production
line whose breakage must fail its check, and each was run: the line was
injected, the check went red, and the source was restored byte-identical
(``cp`` of a backup — never ``git checkout``).
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import re
import uuid
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent


def _load_dev_ledger():
    """Load dev/ledger.py as a module (it lives in dev/, not the root)."""
    loader = importlib.machinery.SourceFileLoader(
        "dev_ledger_warnings", str(REPO / "dev" / "ledger.py"))
    spec = importlib.util.spec_from_loader("dev_ledger_warnings", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture
def dev_ledger():
    return _load_dev_ledger()


# A markdown-mode ledger with two open tasks (no watermark → no store).
# Used wherever the footer must actually EMIT (open-task count > 0), so the
# stream / exit-code / zero-absent tests are not vacuous.
OPEN_TASKS_LEDGER = """# Task ledger

Next id: **20**

## Open

- **#10** — an open task · P1 · task · origin: **human**

- **#12** — another open task · P2 · bug · origin: **loop**

## Recently landed

- **#11** — a landed task · P0 · task · origin: **human** (abc1234)
"""

# A ledger with an EMPTY open section — the clean-tree fixture (every count
# zero). Headings present so parse_ledger's anchored readers are satisfied.
CLEAN_LEDGER = """# Task ledger

Next id: **20**

## Open

## Recently landed
"""

# questions.md carrying an answer-tagged bullet UNDER ## Open — the one shape
# lint.check_unfolded_answers warns over (#366). The stamp matches
# ANSWER_BULLET_STAMP and the prefix matches watch.ANSWER_TAGS, both read from
# the production modules (never restated here).
UNFOLDED_QUESTIONS = """## Open

- **A question that was answered but not folded**

  - **Answer (via watch, 2026-07-30 03:00)** the answer text

## Answered
"""


# ---------------------------------------------------------------------------
# Footers never touch stdout; never change an exit code; ride every verb.
#
# The footer emits on EVERY verb's success path. These run the real `counts`
# verb end-to-end (markdown mode) so the seam is main()'s tail, not a helper.
# ---------------------------------------------------------------------------

def test_footer_writes_to_stderr_not_stdout(dev_ledger, tmp_path):
    """The footer rides stderr; stdout is byte-identical to the verb alone.

    PRODUCTION LINE (red-proof target): the STREAM emit_warnings writes to in
    dev/ledger.py. RED: point it at stdout and the `warnings:` line appears in
    stdout (breaking `counts | head` / any piped consumer). The fixture has
    open tasks so the footer genuinely emits — a clean tree emits nothing and
    the stream distinction would be vacuous.
    """
    dw = tmp_path / "dw"
    dw.mkdir()
    (dw / "tasks.md").write_text(OPEN_TASKS_LEDGER)

    # Precondition (derived, never trusted from layout): the footer will emit,
    # because there ARE open tasks. Without this the test passes over a footer
    # that wrote to the right stream of nothing.
    import watch
    open_ids, _ = watch.parse_ledger((dw / "tasks.md").read_text())
    assert open_ids, "precondition: fixture must have open tasks so the footer emits"

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = dev_ledger.main(["counts", "--ledger", str(dw / "tasks.md")])
    assert rc == 0

    assert "warnings:" in err.getvalue(), (
        "footer must ride stderr (stdout is machine-readable)")
    assert "warnings:" not in out.getvalue(), (
        "footer must NEVER touch stdout — it would corrupt `counts | head`")
    # The verb's own output is still intact on stdout.
    assert "open ids:" in out.getvalue()


def test_footer_never_changes_exit_code(dev_ledger, tmp_path):
    """A verb with warnings still exits 0 (WARN, never ERROR).

    PRODUCTION LINE (red-proof target): the return value emit_warnings hands
    back to main() (the `return emit_warnings(...)` tail). RED: make that
    return non-zero on the warnings path and a `counts` over open tasks exits
    non-zero — the footer must never block or fail a verb.
    """
    dw = tmp_path / "dw"
    dw.mkdir()
    (dw / "tasks.md").write_text(OPEN_TASKS_LEDGER)

    # Precondition: warnings genuinely exist (open tasks > 0).
    import watch
    open_ids, _ = watch.parse_ledger((dw / "tasks.md").read_text())
    assert open_ids, "precondition: warnings must exist for the exit-code test"

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        rc = dev_ledger.main(["counts", "--ledger", str(dw / "tasks.md")])
    assert rc == 0, (
        "a verb that succeeded must exit 0 even when the footer has warnings")


def test_footer_absent_on_a_failing_verb(dev_ledger, tmp_path):
    """A failing verb prints NO warning footer — the `if rc == 0:` gate.

    PRODUCTION LINE (red-proof target): the `if rc == 0:` gate in
    emit_warnings. RED: replace it with `if True:` and the footer rides a
    FAILED verb's stderr — a warning line after an error reads as the
    error's own output and trains him to ignore both. (Surfaced as a GREEN
    red-run at the #357 merge gate: the lane's seven proofs bound the
    stream, the exit code, the two reuse seams, the zero-suppression, the
    clean-tree quiet, and the journal count — but nothing failed with this
    gate removed. A green red-run is a finding; this check is it acted on.)
    """
    dw = tmp_path / "dw"
    dw.mkdir()
    (dw / "tasks.md").write_text(OPEN_TASKS_LEDGER)

    # Precondition: warnings genuinely exist, so the footer WOULD print if
    # the gate were open — a clean fixture makes the assertion vacuous.
    import watch
    open_ids, _ = watch.parse_ledger((dw / "tasks.md").read_text())
    assert open_ids, "precondition: warnings must exist for the gate test"

    # Direct: rc != 0 suppresses the footer even with warnings present.
    buf = io.StringIO()
    rc = dev_ledger.emit_warnings(str(dw), 65, stream=buf)
    assert rc == 65, "emit_warnings must return the rc it was handed"
    assert "warnings:" not in buf.getvalue(), (
        "a failing verb must not carry the warning footer")

    # End to end: a failing verb through main() prints no footer on stderr.
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        rc = dev_ledger.main(["fold", "99999", "--note", "x",
                              "--ledger", str(dw / "tasks.md")])
    assert rc != 0, "precondition: the verb must genuinely fail"
    assert "warnings:" not in err.getvalue(), (
        "a failing verb's stderr carries the error, never the footer")


# ---------------------------------------------------------------------------
# Reuse, never rebuild — the footer's open-task count IS store_ids_by_state.
# ---------------------------------------------------------------------------

def test_footer_open_tasks_reuses_store_ids_by_state(dev_ledger, tmp_path):
    """The footer's open-task count equals len(store_ids_by_state(...)[0]).

    PRODUCTION LINE (red-proof target): the `store_ids_by_state(str(dw))[0]`
    call in the footer's count reader. RED: replace it with a direct query
    over a different WHERE (e.g. all rows, or landed) and the footer's count
    diverges from the projection `counts` itself uses — two numbers for one
    fact, the exact dual-write defect.

    Store mode (watermark present) so the store is the source; reuses the
    migrate plumbing from the dispatch-parity suite to seed a real scratch
    store, never a hand-built cursor.
    """
    from test_ledger_dispatch import (
        LEDGER as DISPATCH_LEDGER, _load_migrate, _setup_store, _write_watermark)
    import ledger_parse

    migrate = _load_migrate()
    dw = tmp_path / "dw"
    dw.mkdir()
    (dw / "tasks.md").write_text(DISPATCH_LEDGER)
    db = _setup_store(migrate, dw, DISPATCH_LEDGER)
    _write_watermark(db)

    # Precondition (derived): the store genuinely has open ids, and the
    # footer's count is non-trivial only if open ids exist.
    expected_open = len(ledger_parse.store_ids_by_state(str(dw))[0])
    assert expected_open > 0, "precondition: fixture must have open ids in the store"

    buf = io.StringIO()
    dev_ledger.emit_warnings(str(dw), 0, stream=buf)
    line = buf.getvalue()
    assert "open tasks" in line, "the footer must carry the open-task count"

    m = re.search(r"(\d+) open tasks", line)
    assert m is not None, "footer line must name the open-task count"
    assert int(m.group(1)) == expected_open, (
        f"footer open-task count ({m.group(1)}) must equal "
        f"len(store_ids_by_state(...)[0]) ({expected_open}) — the SAME reader "
        "the `counts` verb uses, never a second query")


# ---------------------------------------------------------------------------
# Reuse, never rebuild — the unfolded-answer count IS lint.check_unfolded_answers.
#
# Structural guard (the born-hollow trap): the precondition is derived by
# calling the REAL lint.check_unfolded_answers, not a hand-built count. The
# red-proof breaks the footer's CALL to it and watches the footer's count
# drop to zero while the file still holds an unfolded answer.
# ---------------------------------------------------------------------------

def test_footer_unfolded_count_reuses_check_unfolded_answers(dev_ledger, tmp_path):
    """The footer's unfolded count comes from lint.check_unfolded_answers.

    PRODUCTION LINE (red-proof target): the `lint.check_unfolded_answers(dw,
    watch, rep)` call in the footer's count reader. RED: skip that call (count
    via a no-op) and the footer reports 0 while questions.md still holds an
    answer under ## Open — the file is wrong and the footer is silent over it.
    """
    import lint
    import watch

    dw = tmp_path / "dw"
    dw.mkdir()
    (dw / "questions.md").write_text(UNFOLDED_QUESTIONS)

    # Precondition (derived from the REAL production reader): the file
    # genuinely holds an unfolded answer, so a footer that reused the reader
    # would see > 0. This is what makes a "0" a finding, not a relief.
    rep = lint.Report()
    lint.check_unfolded_answers(dw, watch, rep)
    expected = sum(1 for lvl, _, _ in rep.rows if lvl == lint.WARN)
    assert expected > 0, (
        "precondition: fixture must hold an unfolded answer that the real "
        "check_unfolded_answers warns over")

    buf = io.StringIO()
    dev_ledger.emit_warnings(str(dw), 0, stream=buf)
    line = buf.getvalue()
    m = re.search(r"(\d+) unfolded answers", line)
    assert m is not None, (
        "footer must carry the unfolded-answer count when one exists")
    assert int(m.group(1)) == expected, (
        f"footer unfolded count ({m.group(1)}) must equal the real "
        f"check_unfolded_answers WARN count ({expected})")


# ---------------------------------------------------------------------------
# Quiet rule 1 — a zero count is absent from the line.
# ---------------------------------------------------------------------------

def test_zero_count_is_absent_from_the_line(dev_ledger, tmp_path):
    """A count at zero does not appear; a non-zero count does.

    PRODUCTION LINE (red-proof target): the `if n > 0` filter in the footer's
    formatter. RED: drop the filter (always print every label) and the
    zero-count label appears — "0 unanswered questions" spends the line's
    credibility on the success state.

    Fixture: open tasks > 0 (emits), but no questions.md → unanswered = 0
    (must be absent). Both sides derived at runtime.
    """
    import watch

    dw = tmp_path / "dw"
    dw.mkdir()
    (dw / "tasks.md").write_text(OPEN_TASKS_LEDGER)

    # Precondition (derived): open tasks > 0 (footer emits) AND the
    # unanswered-questions count is genuinely 0 (no questions.md). Asserting
    # both makes the "absent" claim load-bearing rather than coincidental.
    open_ids, _ = watch.parse_ledger((dw / "tasks.md").read_text())
    assert open_ids, "precondition: open tasks > 0 so the line is non-empty"
    assert not (dw / "questions.md").exists(), (
        "precondition: no questions.md → unanswered questions = 0")

    buf = io.StringIO()
    dev_ledger.emit_warnings(str(dw), 0, stream=buf)
    line = buf.getvalue()

    assert "open tasks" in line, "a non-zero count must appear"
    assert "unanswered questions" not in line, (
        "a zero count must be ABSENT — '0 unanswered questions' is the "
        "fatigue case the quiet rule exists to prevent")


# ---------------------------------------------------------------------------
# Quiet rule 2 — a fully clean tree prints nothing.
# ---------------------------------------------------------------------------

def test_clean_tree_prints_nothing(dev_ledger, tmp_path):
    """Every count zero → the footer emits nothing (not even 'no warnings').

    PRODUCTION LINE (red-proof target): the `if not parts: return ""` guard in
    the footer's formatter. RED: always emit a header (drop the guard) and a
    clean tree gains a line — which teaches him to scroll past the footer.

    Precondition: assert EACH count source is genuinely zero at runtime (open
    ids empty, no answers/questions, no store, no journal) — a clean tree
    asserts clean, never trusts layout.
    """
    import watch

    dw = tmp_path / "dw"
    dw.mkdir()
    (dw / "tasks.md").write_text(CLEAN_LEDGER)

    # Derive every count's zero-ness so the silence is proven, not assumed.
    open_ids, _ = watch.parse_ledger((dw / "tasks.md").read_text())
    assert not open_ids, "precondition: zero open tasks"
    assert not (dw / "answers.md").exists(), "precondition: no answers.md"
    assert not (dw / "questions.md").exists(), "precondition: no questions.md"
    assert not (dw / "user-events.sqlite3").exists(), "precondition: no journal"
    # No store → markdown mode → incomplete-data counts are absent.

    buf = io.StringIO()
    dev_ledger.emit_warnings(str(dw), 0, stream=buf)
    assert buf.getvalue() == "", (
        "a clean tree must print exactly what the verb prints today — "
        f"got {buf.getvalue()!r}")


# ---------------------------------------------------------------------------
# The journal unconsumed-receipt count — real cursor arithmetic, real journal.
#
# Seeded through the PRODUCTION receive() path (open_journal + Envelope +
# receive), never a mocked cursor. The count is head_ordinal − the
# coordinator cursor's scanned_through — the durable "something is waiting"
# signal that survives compaction.
# ---------------------------------------------------------------------------

def test_footer_unconsumed_receipts_from_real_cursor(dev_ledger, tmp_path):
    """unconsumed = head_ordinal − coordinator cursor scanned_through.

    Seeds 3 receipts via receive(), advances the coordinator cursor through
    ordinal 1, and expects head(3) − scanned(1) = 2 unconsumed.

    PRODUCTION LINE (red-proof target): the `head_ordinal() −
    cursor("coordinator").scanned_through_event_ordinal` arithmetic in the
    footer's journal reader. RED: drop the subtraction (report head alone = 3)
    or return 0, and the footer's count diverges from the real cursor gap.
    """
    from user_events.sqlite import Envelope, open_journal

    dw = tmp_path / "dw"
    dw.mkdir()
    jpath = dw / "user-events.sqlite3"

    # Seed through the production receive() path. Capture the chain head at
    # ordinal 1 so we can advance the coordinator cursor through it.
    with open_journal(jpath) as j:
        for k in range(3):
            r = j.receive(Envelope(
                client_action_id=str(uuid.uuid4()),
                protocol_version="1", method="POST", route="/answer",
                content_type="application/json", body=f'{{"k":{k}}}'.encode()))
            assert r.kind == "inserted", f"receive {k} must insert, got {r.kind}"
            if k == 0:
                head_at_1 = j.head_hash()
        # Advance the coordinator cursor through ordinal 1 only.
        adv = j.advance_cursor("coordinator", expected=head_at_1, scanned_through=1)
        assert adv.kind == "advanced", f"cursor advance must succeed, got {adv!r}"
        scanned = j.cursor("coordinator").scanned_through_event_ordinal
        head = j.head_ordinal()

    # Precondition (derived from the production API, never a literal): the
    # gap is genuinely 2, so the footer reporting anything else is a bug.
    assert head == 3, f"precondition: head must be 3, got {head}"
    assert scanned == 1, f"precondition: cursor must sit at 1, got {scanned}"
    expected = head - scanned
    assert expected == 2

    buf = io.StringIO()
    dev_ledger.emit_warnings(str(dw), 0, stream=buf)
    line = buf.getvalue()
    m = re.search(r"(\d+) unconsumed receipts", line)
    assert m is not None, "footer must carry the unconsumed-receipt count"
    assert int(m.group(1)) == expected, (
        f"footer unconsumed count ({m.group(1)}) must equal head−cursor "
        f"({expected}); the journal's durable 'something is waiting' signal")
