"""#458 — migration notices in the hot data file.

The interesting tests are the negative ones: a file carrying a notice
parses to exactly the same ledger entries as the same file without it,
and both sides are derived from the production readers (watch.parse_ledger,
lint.LEDGER_ID), never hand-written expected id lists.

Each red-proof names the production line whose change makes the test fail.
A green red-run is a finding, never a relief.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import lint
import migration_notice as mn
import watch


# Minimal ledger shape both production readers accept. Two open ids, one
# landed, a Next id past both. Derived expectations come from the parsers.
LEDGER = """# Task ledger

Next id: **10**

## Open
- **#7** — open one · P2 · origin: **human**
- **#8** — open two · P1 · origin: **loop**

## Recently landed
- **#3** — done · landed `abc1234`
"""


def _ids_via_ledger_id(text: str) -> list[int]:
    """The same extraction check_tasks uses (lint.LEDGER_ID + ENTRY_ID)."""
    return [
        int(x)
        for m in lint.LEDGER_ID.findall(text)
        for x in lint.ENTRY_ID.findall(m)
    ]


def _open_via_parse_ledger(text: str) -> set[int]:
    # parse_ledger returns digit strings (no '#'); normalise to int so we can
    # compare against lint.LEDGER_ID's ints without a type trap.
    opened, _landed = watch.parse_ledger(text)
    return {int(x) for x in opened}


class TestFormatAndRoundTrip:
    def test_render_round_trips_through_parse(self):
        block = mn.render_notice(
            "2026-07-29-01-example.md",
            file=".dreamwork/tasks.md",
            summary="archived copy; live store moved",
        )
        fields = mn.parse_notice(block)
        assert fields == {
            "migration": "2026-07-29-01-example.md",
            "file": ".dreamwork/tasks.md",
            "summary": "archived copy; live store moved",
        }

    def test_migration_name_shape_is_required(self):
        with pytest.raises(mn.NoticeError, match="YYYY-MM-DD"):
            mn.render_notice("not-a-migration")

    def test_unknown_field_is_rejected(self):
        body = "migration: 2026-07-29-01-example.md\nextra: no\n"
        with pytest.raises(mn.NoticeError, match="unknown"):
            mn.parse_notice_fields(body)

    def test_value_that_looks_like_a_ledger_head_is_rejected(self):
        # Without this guard a summary of `- **#999** …` would be counted by
        # LEDGER_ID (re.M, whole file). The writer is the line that fails.
        with pytest.raises(mn.NoticeError, match="ledger entry head"):
            mn.render_notice(
                "2026-07-29-01-example.md",
                summary="- **#999** phantom",
            )


class TestIndifference:
    """Goal 2: lint and watch do not treat a notice as a task.

    Precondition (asserted at runtime): the bare ledger has a non-empty open
    set, so a parser that returned empty on both sides could not hide a
    regression by matching zeros.
    """

    def test_precondition_bare_ledger_is_nonempty(self):
        opened = _open_via_parse_ledger(LEDGER)
        ids = _ids_via_ledger_id(LEDGER)
        assert opened, "fixture open set empty — indifference check would be hollow"
        assert ids, "fixture id list empty — indifference check would be hollow"
        # The two readers must already agree on the fixture, or a later
        # "same with notice" claim is comparing two wrong baselines.
        assert opened == set(ids) - {3} or opened <= set(ids)

    def test_parse_ledger_ids_identical_with_and_without_notice(self):
        # Production line that must stay indifferent: watch.LEDGER_ENTRY /
        # parse_ledger walk — a notice is not `^- **#N**` under a section.
        with_notice = mn.insert_notice(
            LEDGER,
            "2026-07-29-01-example.md",
            file=".dreamwork/tasks.md",
            summary="archived copy; read the migration",
        )
        bare_open = _open_via_parse_ledger(LEDGER)
        notice_open = _open_via_parse_ledger(with_notice)
        # Precondition: bare side has content (derived, not a literal).
        assert bare_open, "bare open set empty — comparison is hollow"
        assert notice_open == bare_open, (
            f"parse_ledger diverged: bare={sorted(bare_open)} "
            f"with_notice={sorted(notice_open)}"
        )
        # And strip_notice recovers the same open set (the notice is pure
        # chrome relative to the ledger readers).
        assert _open_via_parse_ledger(mn.strip_notice(with_notice)) == bare_open

    def test_lint_LEDGER_ID_findall_identical_with_and_without_notice(self):
        # Production line: lint.LEDGER_ID (module-level, used by check_tasks).
        # Red-proof: change LEDGER_ID to also match inside HTML comments, or
        # make insert_notice emit a real `- **#N**` line — this fails.
        with_notice = mn.insert_notice(
            LEDGER,
            "2026-07-29-01-example.md",
            summary="pointer only",
        )
        bare = _ids_via_ledger_id(LEDGER)
        noticed = _ids_via_ledger_id(with_notice)
        assert bare, "bare ids empty — comparison is hollow"
        assert noticed == bare

    def test_check_tasks_open_count_stable_under_notice(self, tmp_path):
        # Full check_tasks path: write both files, run the real check, compare
        # the OK message's id count. Derived from the report, not a literal.
        def run(text: str):
            dw = tmp_path / "dw"
            dw.mkdir(exist_ok=True)
            (dw / "tasks.md").write_text(text)
            rep = lint.Report()
            lint.check_tasks(dw, rep)
            return rep

        bare_rep = run(LEDGER)
        noticed_rep = run(
            mn.insert_notice(LEDGER, "2026-07-29-01-example.md", summary="x")
        )
        # Report.rows are (level, what, detail) tuples.
        bare_ok = [
            r for r in bare_rep.rows if r[0] == lint.OK and r[1] == "tasks.md"
        ]
        notice_ok = [
            r for r in noticed_rep.rows if r[0] == lint.OK and r[1] == "tasks.md"
        ]
        # Precondition: the bare ledger produced at least one OK about ids.
        assert bare_ok, f"bare check produced no OK: {bare_rep.rows}"
        # Extract "N ids" from the message — both sides must agree.
        def n_ids(rows):
            for _lvl, _what, detail in rows:
                m = re.search(r"(\d+) ids", detail)
                if m:
                    return int(m.group(1))
            return None

        assert n_ids(bare_ok) is not None
        assert n_ids(bare_ok) == n_ids(notice_ok)
        # No new ERROR on the notice path.
        bare_err = [r for r in bare_rep.rows if r[0] == lint.ERROR]
        notice_err = [r for r in noticed_rep.rows if r[0] == lint.ERROR]
        assert notice_err == bare_err


class TestShrinkRule:
    """The Nth migration leaves one banner, not N."""

    def test_insert_replaces_prior_notice(self):
        # Production line: insert_notice → strip_notice before prepend.
        # Red-proof: delete the strip_notice call in insert_notice so the
        # second write appends a second block — findall count goes to 2.
        once = mn.insert_notice(LEDGER, "2026-07-29-01-first.md", summary="one")
        twice = mn.insert_notice(once, "2026-07-29-02-second.md", summary="two")
        blocks = list(mn._BLOCK_RE.finditer(twice))
        # Precondition: the second migration name is actually present, so we
        # are not counting zero-because-empty.
        assert "2026-07-29-02-second.md" in twice
        assert len(blocks) == 1, f"expected one notice, found {len(blocks)}"
        fields = mn.parse_notice(twice)
        assert fields["migration"] == "2026-07-29-02-second.md"
        assert "2026-07-29-01-first.md" not in twice


class TestRetirement:
    def test_spent_when_skill_version_ge_migration(self):
        # Production line: notice_is_spent — lexicographic >= per README.
        assert mn.notice_is_spent(
            "2026-07-29-01-example.md", "2026-07-29-01-example.md"
        )
        assert mn.notice_is_spent(
            "2026-07-29-01-example.md", "2026-07-29-02-later.md"
        )
        assert not mn.notice_is_spent(
            "2026-07-29-02-later.md", "2026-07-29-01-example.md"
        )

    def test_retire_if_applied_removes_spent_notice(self):
        # Production line: retire_if_applied → notice_is_spent gate.
        # Red-proof: force notice_is_spent to always return False — removed
        # stays False and the notice remains.
        text = mn.insert_notice(
            LEDGER, "2026-07-29-01-example.md", summary="go"
        )
        assert mn.parse_notice(text) is not None
        new, removed = mn.retire_if_applied(text, "2026-07-29-01-example.md")
        assert removed is True
        assert mn.parse_notice(new) is None
        # Ledger content preserved (derived: same open set).
        assert _open_via_parse_ledger(new) == _open_via_parse_ledger(LEDGER)

    def test_retire_keeps_unspent_notice(self):
        text = mn.insert_notice(
            LEDGER, "2026-07-29-02-later.md", summary="still pending"
        )
        new, removed = mn.retire_if_applied(text, "2026-07-29-01-example.md")
        assert removed is False
        assert new == text
        assert mn.parse_notice(new)["migration"] == "2026-07-29-02-later.md"


class TestCLI:
    def test_write_and_parse_and_retire(self, tmp_path):
        path = tmp_path / "tasks.md"
        path.write_text(LEDGER)
        assert mn.main([
            "write",
            "--path", str(path),
            "--migration", "2026-07-29-01-example.md",
            "--summary", "archived",
        ]) == 0
        assert mn.parse_notice(path.read_text())["migration"] == (
            "2026-07-29-01-example.md"
        )
        assert mn.main([
            "retire",
            "--path", str(path),
            "--skill-version", "2026-07-29-01-example.md",
        ]) == 0
        assert mn.parse_notice(path.read_text()) is None


class TestRedProofHooks:
    """Named reds — reintroduce the bug, watch the check fail.

    These run the injection against a *copy* of the decision in-process so
    the production file stays clean. If the injection cannot make the
    assertion fail, the test itself is hollow.
    """

    def test_red_insert_without_strip_leaves_two_notices(self):
        # The production line is insert_notice's strip_notice call.
        once = mn.insert_notice(LEDGER, "2026-07-29-01-first.md")
        # Inject: prepend a second block without stripping (the bug).
        second = mn.render_notice("2026-07-29-02-second.md") + once
        blocks = list(mn._BLOCK_RE.finditer(second))
        assert len(blocks) == 2, "injection did not create two notices — red is hollow"
        # The real insert_notice must NOT leave two.
        fixed = mn.insert_notice(once, "2026-07-29-02-second.md")
        assert len(list(mn._BLOCK_RE.finditer(fixed))) == 1

    def test_red_ledger_head_in_summary_would_pollute_ids(self):
        # If the writer accepted a ledger-head summary, LEDGER_ID would gain
        # a phantom id. Prove the hazard exists, then that the writer blocks it.
        poison = (
            mn.NOTICE_OPEN
            + "\nmigration: 2026-07-29-01-example.md\n"
            + "summary: plain\n"
            + mn.NOTICE_CLOSE
            + "\n- **#999** smuggled\n"
            + LEDGER
        )
        polluted = _ids_via_ledger_id(poison)
        bare = _ids_via_ledger_id(LEDGER)
        assert 999 in polluted, "injection did not pollute ids — red is hollow"
        assert 999 not in bare
        # Writer path refuses the equivalent smuggle via the summary field.
        with pytest.raises(mn.NoticeError):
            mn.render_notice(
                "2026-07-29-01-example.md",
                summary="- **#999** smuggled",
            )
