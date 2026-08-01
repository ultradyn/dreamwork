"""#843 — ingest-plan: confinement, table parsing, and flat filing.

These cover the pure module-level functions in watch.py:
  - resolve_ingest_path: path confinement (realpath resolves symlinks + ..).
  - parse_ingestion_table: the "## Tasks for ingestion" table, with a NAMED
    refusal when it is absent (the #671 vacuous-pass guard).
  - file_ingested_tasks: files rows via dev/ledger.py (the ONE writer, #440).

The integration path (POST /command kind=ingest-plan → _apply_ingest_plan)
lives in test_watch.py alongside the other /command dispatch tests.
"""
import os
import sys
import tempfile

import watch

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# A minimal markdown ledger the markdown file verb accepts (Next id header +
# ## Open). The markdown path is what v1 lands in when no store watermark is
# set, which is the case for a fresh make_target.
LEDGER = "# Task ledger\n\nNext id: **5**\n\n## Open\n\n## Recently landed\n\n"


# ── confinement ─────────────────────────────────────────────────────────────
class TestConfinement:
    def _root(self, tmp):
        """An allowed-root subdir under tmp, swapped in for the test."""
        root = os.path.join(tmp, "plans")
        os.makedirs(root)
        orig = watch.INGEST_PLAN_ROOTS
        watch.INGEST_PLAN_ROOTS = (root,)
        self._restore = orig
        return root

    def teardown_method(self):
        if hasattr(self, "_restore"):
            watch.INGEST_PLAN_ROOTS = self._restore

    def test_a_path_inside_the_root_is_allowed(self, tmp_path):
        root = self._root(str(tmp_path))
        plan = os.path.join(root, "a-plan.md")
        open(plan, "w").close()
        resolved, err = watch.resolve_ingest_path(plan)
        assert err is None, err
        assert resolved == os.path.realpath(plan)

    def test_an_absolute_escape_is_refused_by_name(self, tmp_path):
        self._root(str(tmp_path))
        _, err = watch.resolve_ingest_path("/etc/passwd")
        assert err is not None
        assert "not under an allowed ingest root" in err

    def test_a_dotdot_escape_is_caught_after_resolution(self, tmp_path):
        # The discriminating case (#843 direction 2): a string that LOOKS like
        # it is under the root but resolves out via '..'. Checking the raw
        # string before resolving passes this; realpath catches it.
        root = self._root(str(tmp_path))
        outside = os.path.join(str(tmp_path), "secret.txt")
        open(outside, "w").close()
        escape = os.path.join(root, "..", "secret.txt")
        _, err = watch.resolve_ingest_path(escape)
        assert err is not None, (
            "a '..' path resolving outside the root was allowed — the check "
            "is inspecting the string, not the resolved path")

    def test_a_symlink_inside_the_root_pointing_out_is_caught(self, tmp_path):
        # The second discriminating case (#843 direction 2): the string sits
        # inside the root (so a string check passes), but it is a symlink to a
        # file outside. realpath follows the link and the target escapes.
        root = self._root(str(tmp_path))
        outside = os.path.join(str(tmp_path), "outside-target.md")
        open(outside, "w").close()
        link = os.path.join(root, "escape-link.md")
        os.symlink(outside, link)
        _, err = watch.resolve_ingest_path(link)
        assert err is not None, (
            "an in-root symlink pointing out was allowed — symlinks are not "
            "being resolved before the containment check")


# ── table parsing ───────────────────────────────────────────────────────────
PLAN_WITH_TABLE = """# A plan

Some preamble.

## Tasks for ingestion

Priority bands are the ledger's P0–P3.

| # | Title | type | pri | blocked on |
|---|---|---|---|---|
| A | `do the first thing` | task | P1 | — |
| B | do the second thing | idea | P2 | A |
| C | do the third | task | P3 | A, B |
"""

PLAN_NO_HEADING = "# A plan\n\nJust prose, no ingestion table.\n"

PLAN_HEADING_NO_TABLE = """# A plan

## Tasks for ingestion

No table here, just words.

## Open risks
"""

PLAN_EMPTY_TABLE = """# A plan

## Tasks for ingestion

| # | Title |
|---|---|
"""


class TestParseTable:
    def test_parses_rows_with_title_type_and_priority(self):
        rows, err = watch.parse_ingestion_table(PLAN_WITH_TABLE)
        assert err is None, err
        assert len(rows) == 3
        # backticks stripped from the title; type/pri carried through.
        assert rows[0] == {"title": "do the first thing",
                           "type": "task", "priority": "P1"}
        assert rows[2]["priority"] == "P3"

    def test_a_plan_without_the_heading_is_a_named_refusal(self):
        rows, err = watch.parse_ingestion_table(PLAN_NO_HEADING)
        assert rows == []
        assert err is not None
        assert "no" in err and "Tasks for ingestion" in err, (
            "the refusal must name what is missing, not just 'failed'")

    def test_a_heading_with_no_table_is_a_named_refusal(self):
        rows, err = watch.parse_ingestion_table(PLAN_HEADING_NO_TABLE)
        assert rows == []
        assert err is not None
        assert "no markdown table" in err

    def test_an_empty_table_is_a_named_refusal_not_a_zero_count_success(self):
        # #671 vacuous-pass guard: a table with a header row but no data rows
        # must refuse, not report "filed 0 tasks" as success.
        rows, err = watch.parse_ingestion_table(PLAN_EMPTY_TABLE)
        assert rows == []
        assert err is not None
        assert "empty" in err


# ── flat filing via the ONE writer ──────────────────────────────────────────
class TestFileTasks:
    def _target(self, tmp):
        """A target whose .dreamwork/tasks.md is the LEDGER fixture."""
        dw = os.path.join(tmp, ".dreamwork")
        os.makedirs(dw)
        with open(os.path.join(dw, "tasks.md"), "w") as f:
            f.write(LEDGER)
        return tmp

    def test_files_each_row_and_reports_count_and_ids(self, tmp_path):
        target = self._target(str(tmp_path))
        tasks = [
            {"title": "alpha task", "type": "task", "priority": "P1"},
            {"title": "beta idea", "type": "idea", "priority": "P2"},
            {"title": "gamma", "type": None, "priority": None},
        ]
        count, ids = watch.file_ingested_tasks(target, tasks)
        # Precondition: the fixture's Next id, derived at runtime (not a
        # literal) so the test does not expire when the fixture changes.
        import re
        m = re.search(r"Next id: \*\*(\d+)\*\*", LEDGER)
        base_id = int(m.group(1))
        assert count == 3
        assert ids == [base_id, base_id + 1, base_id + 2], ids
        # The filed entries are under ## Open with the allocated ids.
        text = open(os.path.join(target, ".dreamwork", "tasks.md")).read()
        assert "- **#%d** — alpha task" % base_id in text
        assert "- **#%d** — gamma" % (base_id + 2) in text

    def test_filed_origin_is_human(self, tmp_path):
        target = self._target(str(tmp_path))
        watch.file_ingested_tasks(
            target, [{"title": "x", "type": None, "priority": None}])
        text = open(os.path.join(target, ".dreamwork", "tasks.md")).read()
        assert "origin: **human**" in text, (
            "ingested tasks should be attributed to the human who pasted the "
            "path, not the loop default")
