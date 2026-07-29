"""T1–T5 seam checks for the matt-pocock bridge tracker-adapter (design §12).

Each check is red-first: the production line it guards and the injection that
reddens it are named in the class docstring. Runtime preconditions are asserted
inline (the design's rule: a check whose meaning depends on a fixture state
must derive that state, never assume it).

The bridge's three binding constraints, and which check pins each:
  C1 — T1 (never opens the ledger), T2 (cutover is invisible).
  C2 — T3 (grill lands via human_block), T5 (no invented author tag).
  C3 — T4 (no new file under .dreamwork/).
"""
from __future__ import annotations

import builtins
import contextlib
import io
import re
import subprocess
from pathlib import Path
from unittest import mock

import ledger_parse
import tracker_adapter
import watch
from conftest import ADAPTER, CORE, cut_over, fake_runner, make_target


@contextlib.contextmanager
def tracking_opens():
    """Record every file open while the block runs, returning the path list.

    Wraps BOTH `builtins.open` and `io.open`. `Path.read_text()` reaches
    `io.open` via `Path.open`, NOT `builtins.open` — a patch on
    `builtins.open` alone let a `read_text()` injection pass green (the test's
    own scaffolding stood in front of the bug it was written for). The two
    names reference the same object at interpreter start, so one saved
    original serves both, and `tracking` calls it to avoid recursion."""
    real_open = builtins.open
    opened: list[str] = []

    def tracking(path, *a, **k):
        opened.append(str(path))
        return real_open(path, *a, **k)

    with mock.patch("builtins.open", tracking), mock.patch("io.open", tracking):
        yield opened


# ---------------------------------------------------------------------------
# T1 — the task seam never opens the ledger (C1)
# ---------------------------------------------------------------------------

class TestT1TaskSeamNeverOpensLedger:
    """T1 — the 'create issue' path shells to `dev/ledger.py file` and NEVER
    opens `.dreamwork/tasks.md` or `.dreamwork/ledger.sqlite3`.

    Production line: the subprocess argv built in `tracker_adapter.create`
    (it shells out; it does not read the ledger). Reddens on: the adapter
    reading the ledger directly — add a `ledger.read_text()` (or `open(...)`)
    to `create` and the open-assertion fires. Runtime precondition: the ledger
    path resolves to a real file, or 'did not open' passes on nothing."""

    def test_create_calls_the_file_verb_with_the_ledger_path(self, tmp_path):
        target = make_target(tmp_path)
        ledger = target / ".dreamwork" / "tasks.md"
        assert ledger.is_file(), "precondition: the ledger must exist"
        runner, argvs = fake_runner()
        tracker_adapter.create(CORE, target, "a bridged task", note="ctx",
                               runner=runner)
        assert argvs, "create must shell out to the verb"
        argv = argvs[0]
        assert "file" in argv, "must invoke the `file` verb"
        assert "a bridged task" in argv, "must pass the title"
        assert any("ledger.py" in a for a in argv), "must call dev/ledger.py"
        assert str(ledger) in argv, "must pass the ledger path to --ledger"

    def test_create_never_opens_tasks_md_or_the_store(self, tmp_path):
        target = make_target(tmp_path)
        ledger = target / ".dreamwork" / "tasks.md"
        sqlite = target / ".dreamwork" / "ledger.sqlite3"
        assert ledger.is_file(), "precondition: the ledger must exist"
        runner, _ = fake_runner()
        with tracking_opens() as opened:
            tracker_adapter.create(CORE, target, "a bridged task", runner=runner)
        hits = [p for p in opened
                if p == str(ledger) or p == str(sqlite)
                or p.endswith("tasks.md") or p.endswith("ledger.sqlite3")]
        assert not hits, f"adapter opened the ledger directly (C1): {hits}"

    def test_close_and_list_open_also_never_open_the_ledger(self, tmp_path):
        # the same invariant holds for the other two verbs — they shell out too
        target = make_target(tmp_path)
        ledger = target / ".dreamwork" / "tasks.md"
        assert ledger.is_file(), "precondition: the ledger must exist"
        runner, _ = fake_runner()
        with tracking_opens() as opened:
            tracker_adapter.close(CORE, target, 10, note="done", runner=runner)
            tracker_adapter.list_open(CORE, target, runner=runner)
        hits = [p for p in opened if p.endswith("tasks.md")
                or p.endswith("ledger.sqlite3")]
        assert not hits, f"close/list_open opened the ledger (C1): {hits}"


# ---------------------------------------------------------------------------
# T1b — every verb maps to the right ledger verb at argv level (C1)
# ---------------------------------------------------------------------------

class TestT1bVerbArgvMapping:
    """T1b — `close` shells to the `fold` verb and `list_open` to `counts`.

    Production line: the verb literal in `tracker_adapter.close`'s argv
    (`"fold"`, the third element). Reddens on: swapping `"fold"` for `"note"`
    — the exact injection applied at the 500bridge merge gate on 2026-07-30,
    which passed the suite at 11 tests GREEN (a green red-run: the suite
    asserted `create`'s argv and C1's never-open invariant, but no test
    asserted WHICH verb close/list_open invoke, so `close` silently not
    landing was invisible). This class is the finding acted on. Runtime
    precondition: fake_runner captured an argv, or membership passes on
    nothing; and the ledger file genuinely exists at the path passed."""

    def test_close_invokes_fold_with_id_note_and_ledger(self, tmp_path):
        target = make_target(tmp_path)
        ledger = target / ".dreamwork" / "tasks.md"
        assert ledger.is_file(), "precondition: the ledger must exist"
        runner, argvs = fake_runner()
        tracker_adapter.close(CORE, target, 42, note="done", runner=runner)
        assert argvs, "precondition: close must shell out (argv captured)"
        argv = argvs[0]
        assert any("ledger.py" in a for a in argv), "must call dev/ledger.py"
        assert "fold" in argv, \
            "close must invoke the `fold` verb — anything else does not land"
        assert "42" in argv, "must pass the task id"
        assert "--note" in argv and "done" in argv, "must pass the note"
        assert str(ledger) in argv, "must pass the ledger path to --ledger"

    def test_list_open_invokes_counts_with_ledger_and_no_write_verb(self, tmp_path):
        target = make_target(tmp_path)
        ledger = target / ".dreamwork" / "tasks.md"
        assert ledger.is_file(), "precondition: the ledger must exist"
        runner, argvs = fake_runner()
        tracker_adapter.list_open(CORE, target, runner=runner)
        assert argvs, "precondition: list_open must shell out (argv captured)"
        argv = argvs[0]
        assert any("ledger.py" in a for a in argv), "must call dev/ledger.py"
        assert "counts" in argv, "list_open must invoke the `counts` verb"
        assert "fold" not in argv and "file" not in argv and "note" not in argv, \
            "a read consumer must not invoke a state-change verb"
        assert str(ledger) in argv, "must pass the ledger path to --ledger"


# ---------------------------------------------------------------------------
# T2 — #294 cutover is invisible (C1)
# ---------------------------------------------------------------------------

class TestT2CutoverIsInvisible:
    """T2 — markdown-source and store-source behaviour is byte-identical: the
    adapter shells to the verb, which dispatches on source_of_truth internally.

    Production line: the argv in `tracker_adapter.create` (it passes no
    source-of-truth flag). Reddens on: the adapter branching on source-of-truth
    itself — add a branch and the two paths' argv diverge. Runtime
    precondition: source_of_truth genuinely differs (markdown then store), or
    'identical' passes on a cutover that silently did nothing."""

    def test_create_argv_identical_across_the_cutover(self, tmp_path):
        target = make_target(tmp_path)
        dw = target / ".dreamwork"
        assert ledger_parse.source_of_truth(dw) == "markdown", \
            "precondition: genuinely markdown before the flip"
        r1, a1 = fake_runner()
        tracker_adapter.create(CORE, target, "same task", runner=r1)
        cut_over(dw)
        assert ledger_parse.source_of_truth(dw) == "store", \
            "precondition: genuinely store after the flip (cutover ran)"
        r2, a2 = fake_runner()
        tracker_adapter.create(CORE, target, "same task", runner=r2)
        assert a1[0] == a2[0], \
            "argv must be byte-identical across the cutover (C1)"

    def test_adapter_never_calls_source_of_truth(self):
        # a branch on source-of-truth would need a CALL (or the import that
        # carries it). The docstring legitimately *mentions* source_of_truth to
        # say it does NOT branch — so the check is for a call site, not the
        # bare word, or it would fire on the very explanation of the invariant.
        src = ADAPTER.read_text(encoding="utf-8")
        assert not re.search(r"\bsource_of_truth\s*\(", src), (
            "the adapter must not call source_of_truth (C1); the verb "
            "dispatches internally")
        assert "import ledger_parse" not in src, (
            "the adapter must not import ledger_parse to branch on "
            "source_of_truth (C1)")


# ---------------------------------------------------------------------------
# T3 — grill questions land validly (C2)
# ---------------------------------------------------------------------------

class TestT3GrillLandsViaHumanBlock:
    """T3 — a grill question written by the bridge is parsed by the REAL
    `watch.parse_open_questions` and appears as a contribution with a
    recognised author tag.

    Production line: `watch.human_block(...)` in `tracker_adapter.grill_note`.
    Reddens on: hand-formatting the bullet — bypass human_block and the body
    lands in the entry's body (not as a contribution), so parse shows no
    `follows`. Runtime precondition: parse genuinely returns entries, or 'it
    parsed' passes on an empty file."""

    def test_grill_question_parses_as_a_loop_contribution(self, tmp_path):
        target = make_target(tmp_path)
        tracker_adapter.needs_info(
            target, "Which spine skills to bridge?",
            "rec: the workflow core", "2026-07-30 09:00")
        text = (target / ".dreamwork" / "questions.md").read_text(encoding="utf-8")
        items = watch.parse_open_questions(text)
        assert items, "precondition: parse must return entries (not vacuous)"
        entry = next((i for i in items if "spine" in i["title"].lower()), None)
        assert entry is not None, "the posed grill entry must be present"
        assert entry["follows"], \
            "the grill note must land as a contribution (Follow-up), not body"
        contrib = entry["follows"][-1]
        valid = {a for _, a in watch.NOTE_TAGS} | {a for _, a in watch.ANSWER_TAGS}
        assert contrib["author"] in valid, (
            f"author {contrib['author']!r} is not in the closed tag set")
        assert contrib["author"] == "loop", \
            "the loop poses grill questions (Follow-up loop)"
        assert "workflow core" in contrib["text"]
        assert contrib["when"] == "2026-07-30 09:00"

    def test_grill_question_uses_the_real_human_block(self):
        # the note the bridge emits is shaped by the production writer: it is
        # indented (a sub-bullet, never column-0) and attributes to `loop`
        note = tracker_adapter.grill_note("a multi line\n\npasted bullet", "2026-07-30 09:00")
        first = note.splitlines()[0]
        assert first.startswith("  "), \
            "human_block indents the note so it cannot forge a top-level entry"
        assert watch.note_author(first.lstrip()) == "loop"


# ---------------------------------------------------------------------------
# T4 — no per-target state dreamhub reads (C3)
# ---------------------------------------------------------------------------

class TestT4NoNewDreamworkFile:
    """T4 — the bridge writes nothing new under `.dreamwork/`; only core files
    the loop already owns (tasks.md via the verb, questions.md via needs_info).

    Production line: the write sites in `tracker_adapter` (needs_info writes
    questions.md; the verbs shell out). Reddens on: the bridge writing a new
    `.dreamwork/` file — add a cache write and the before/after set diverges.
    Runtime precondition: the core files exist AND needs_info genuinely ran
    (questions.md changed), or the set check passes on a no-op."""

    def test_no_new_file_appears_under_dreamwork(self, tmp_path):
        target = make_target(tmp_path)
        dw = target / ".dreamwork"
        before = {p.name for p in dw.iterdir()}
        assert "tasks.md" in before and "questions.md" in before, \
            "precondition: the core files exist"
        q_before = (dw / "questions.md").read_text(encoding="utf-8")
        runner, _ = fake_runner()
        tracker_adapter.create(CORE, target, "t", runner=runner)
        tracker_adapter.close(CORE, target, 10, note="done", runner=runner)
        tracker_adapter.list_open(CORE, target, runner=runner)
        tracker_adapter.needs_info(target, "a grill question?", "body",
                                   "2026-07-30 09:00")
        after = {p.name for p in dw.iterdir()}
        assert after == before, \
            f"new files under .dreamwork/ (C3): {after - before}"
        assert (dw / "questions.md").read_text(encoding="utf-8") != q_before, \
            "precondition: needs_info genuinely ran (questions.md changed)"


# ---------------------------------------------------------------------------
# T5 — no invented author tag (C2)
# ---------------------------------------------------------------------------

class TestT5NoInventedAuthorTag:
    """T5 — the bridge uses no invented author tag; only the closed
    `watch.NOTE_TAGS` / `watch.ANSWER_TAGS` set.

    Production line: the tag literal in `tracker_adapter.grill_note`
    (`Follow-up (loop, …)`). Reddens on: adding an invented tag (Grill (/Spec
    (/Ticket () — it is not in the closed set. The closed set is IMPORTED from
    watch, never restated as literals."""

    @staticmethod
    def _closed_tag_names() -> set[str]:
        names: set[str] = set()
        for prefix, _ in watch.NOTE_TAGS:
            names.add(prefix.split("- **", 1)[1].split("(", 1)[0].strip())
        for prefix, _ in watch.ANSWER_TAGS:
            names.add(prefix.split("- **", 1)[1].split("(", 1)[0].strip())
        return names

    def test_every_adapter_tag_is_in_the_closed_set(self):
        names = self._closed_tag_names()
        assert names, "precondition: the closed tag set is non-empty"
        src = ADAPTER.read_text(encoding="utf-8")
        found = re.findall(r"-\s*\*\*([A-Za-z][A-Za-z-]*)\s*\(", src)
        assert found, "precondition: the adapter emits at least one tag literal"
        for name in found:
            assert name in names, f"invented author tag: {name!r}"

    def test_no_invented_tag_forms_anywhere(self):
        src = ADAPTER.read_text(encoding="utf-8")
        for bad in ("Grill (", "Spec (", "Ticket (", "Question (", "Decision ("):
            assert bad not in src, f"invented author tag present: {bad!r}"

    def test_grill_note_attributes_to_a_closed_tag(self):
        note = tracker_adapter.grill_note("body", "2026-07-30 09:00")
        assert watch.note_author(note.lstrip().splitlines()[0]) == "loop", \
            "the grill note must attribute to a closed-tag author (Follow-up loop)"
