"""Tests for lint.py.

The first test is the one that matters: the linter must go RED on the exact
file shape that failed silently in the field. A checker that has never been
red proves nothing, and this repo has now caught three checks that were
passing on their own bug.
"""

import json
from pathlib import Path

import pytest

import lint

# The shape a fresh loop naturally reaches for, and the one that broke:
# `##` headings used AS the questions, so there is no literal `## Open`.
BROKEN = """\
# Open questions for Max

## Console capture (#35): opt-in or on by default?

**Asked:** 2026-07-25 11:01 (in chat, when the idea was captured)

Some context about the privacy default, which is a real decision.

## Page-region context (#15): which privacy default ships?

More context, also a real decision, also invisible.

# Answered
"""

GOOD = """\
# Questions for the human

## Open

- **A question the dashboard can actually see.** Its body is prose.
  - **Note (human, via watch, 2026-07-25 09:00):** a threaded note.

## Answered

- **A folded one.** → resolved (2026-07-25): filed by the loop.
"""


def target(tmp_path: Path, **files) -> Path:
    dw = tmp_path / ".dreamwork"
    dw.mkdir()
    for name, content in files.items():
        p = dw / name.replace("__", "/")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return tmp_path


def run(t: Path):
    rep = lint.Report()
    dw = t / ".dreamwork"
    watch = lint.load_watch()
    lint.check_questions(dw, watch, rep)
    lint.check_tasks(dw, rep)
    lint.check_status(dw, rep)
    lint.check_watch_port(dw, rep)
    lint.check_skill_version(dw, rep)
    lint.check_dreams(dw, rep)
    return rep


def levels(rep, what):
    return [lvl for lvl, w, _ in rep.rows if w == what]


class TestTheBugItWasBuiltFor:
    def test_the_real_broken_shape_is_an_error(self, tmp_path):
        rep = run(target(tmp_path, **{"questions.md": BROKEN}))
        assert ERRORS(rep, "questions.md"), "the field failure must go red"
        detail = next(d for _, w, d in rep.rows if w == "questions.md")
        assert "## Open" in detail, "must name the cause, not just report a zero"

    def test_a_good_file_is_not_an_error(self, tmp_path):
        rep = run(target(tmp_path, **{"questions.md": GOOD}))
        assert levels(rep, "questions.md") == [lint.OK]
        detail = next(d for _, w, d in rep.rows if w == "questions.md")
        assert "1 open" in detail and "1 answered" in detail

    def test_this_repo_passes_its_own_linter(self):
        # Dogfood: the file the whole bug was about, checked by the tool
        # written because of it.
        rep = run(lint.SKILL_DIR)
        assert not rep.failed, rep.render()

    def test_the_canonical_fixture_passes(self):
        rep = lint.Report()
        fixture = lint.SKILL_DIR / "dev/capture/fixture/.dreamwork"
        lint.check_questions(fixture, lint.load_watch(), rep)
        assert levels(rep, "questions.md") == [lint.OK]


def ERRORS(rep, what):
    return lint.ERROR in levels(rep, what)


class TestQuestionsEdges:
    def test_missing_is_a_warning_not_an_error(self, tmp_path):
        # Human's call, 2026-07-25: a missing file is the expected early
        # state of a fresh target, so it stays quiet.
        rep = run(target(tmp_path))
        assert levels(rep, "questions.md") == [lint.WARN]
        assert not rep.failed

    def test_empty_is_fine(self, tmp_path):
        rep = run(target(tmp_path, **{"questions.md": "\n"}))
        assert levels(rep, "questions.md") == [lint.OK]

    def test_heading_present_but_no_entries_is_an_error(self, tmp_path):
        # The subtler half: the section heading is right, so the file looks
        # correct, but nothing under it is an entry.
        text = "# Questions\n\n## Open\n\nJust prose, no bullets at all.\n"
        rep = run(target(tmp_path, **{"questions.md": text}))
        assert ERRORS(rep, "questions.md")

    def test_the_seeded_skeleton_is_not_an_error(self, tmp_path):
        # Exactly what initialization.md step 7 mandates writing. Step 9 then
        # runs this linter, so an ERROR here means every fresh target opens
        # with a false alarm from the tool built to catch false alarms.
        text = "# Questions for the human\n\n## Open\n\n## Answered\n"
        rep = run(target(tmp_path, **{"questions.md": text}))
        assert levels(rep, "questions.md") == [lint.OK]
        assert not rep.failed

    def test_the_exemption_does_not_disable_the_real_check(self, tmp_path):
        # The discrimination test: the field failure must STILL go red now
        # that legitimately-empty files are exempt. An exemption that
        # silently swallows the original bug is worse than no exemption.
        rep = run(target(tmp_path, **{"questions.md": BROKEN}))
        assert ERRORS(rep, "questions.md")

    def test_skeleton_plus_a_stray_line_is_still_an_error(self, tmp_path):
        # The boundary: one line of real content and zero parsed entries is
        # the failure, however short the file.
        text = "# Questions\n\n## Open\n\nsomething he typed\n\n## Answered\n"
        rep = run(target(tmp_path, **{"questions.md": text}))
        assert ERRORS(rep, "questions.md")


class TestLedger:
    def test_duplicate_id_is_an_error(self, tmp_path):
        # This happened: a careless replace left two #98 lines.
        text = "Next id: **99**\n\n- **#98** — one\n- **#98** — two\n"
        rep = run(target(tmp_path, **{"tasks.md": text}))
        assert ERRORS(rep, "tasks.md")
        assert "98" in next(d for _, w, d in rep.rows if w == "tasks.md")

    def test_next_id_that_would_collide_is_an_error(self, tmp_path):
        text = "Next id: **12**\n\n- **#12** — already taken\n"
        rep = run(target(tmp_path, **{"tasks.md": text}))
        assert ERRORS(rep, "tasks.md")

    def test_missing_next_id_header_is_an_error(self, tmp_path):
        rep = run(target(tmp_path, **{"tasks.md": "- **#1** — a task\n"}))
        assert ERRORS(rep, "tasks.md")

    def test_a_sound_ledger_is_ok(self, tmp_path):
        text = "Next id: **3**\n\n- **#1** — one\n- **#2** — two\n"
        rep = run(target(tmp_path, **{"tasks.md": text}))
        assert levels(rep, "tasks.md") == [lint.OK]


class TestStatusIsAnInterface:
    """Two readers as of #96 (watch.py and dreamhub.py), so a wrong TYPE is
    the failure worth catching — an absent field reads as unknown, but a
    string where a list belongs makes a reader render nonsense or throw."""

    def test_invalid_json_is_an_error(self, tmp_path):
        rep = run(target(tmp_path, **{"status.json": '{"task": "x",}'}))
        assert ERRORS(rep, "status.json")

    def test_counts_agents_and_flags_the_human_waiting(self, tmp_path):
        blob = json.dumps({
            "task": "x",
            "agents": [{"name": "a"}, {"name": "b"}],
            "awaiting_human": ["a decision"],
        })
        rep = run(target(tmp_path, **{"status.json": blob}))
        detail = next(d for _, w, d in rep.rows if w == "status.json")
        assert "2 agent" in detail and "1 awaiting" in detail

    def test_every_field_is_optional(self, tmp_path):
        # A fresh loop writes almost nothing, and a target whose loop is not
        # running still has to appear in the hub. Readers degrade.
        rep = run(target(tmp_path, **{"status.json": "{}"}))
        assert levels(rep, "status.json") == [lint.OK]

    def test_a_wrong_type_is_an_error(self, tmp_path):
        blob = json.dumps({"task": "x", "awaiting_human": "a decision"})
        rep = run(target(tmp_path, **{"status.json": blob}))
        assert ERRORS(rep, "status.json")
        assert "awaiting_human is str" in next(d for _, w, d in rep.rows if w == "status.json")

    def test_a_nameless_agent_is_an_error(self, tmp_path):
        blob = json.dumps({"agents": [{"name": "a"}, {"owns": ["x.py"]}]})
        rep = run(target(tmp_path, **{"status.json": blob}))
        assert ERRORS(rep, "status.json")

    def test_a_future_last_tick_is_an_error(self, tmp_path):
        # Two different agents wrote a future timestamp on 2026-07-25 by
        # estimating elapsed time rather than reading the clock. A future
        # time is always wrong and always detectable, so it is checked
        # rather than remembered.
        from datetime import datetime, timedelta
        ahead = (datetime.now() + timedelta(minutes=20)).isoformat(timespec="minutes")
        blob = json.dumps({"task": "x", "last_tick": ahead})
        rep = run(target(tmp_path, **{"status.json": blob}))
        assert ERRORS(rep, "status.json")
        assert "FUTURE" in next(d for _, w, d in rep.rows if w == "status.json")

    def test_a_present_or_past_last_tick_is_fine(self, tmp_path):
        from datetime import datetime, timedelta
        past = (datetime.now() - timedelta(hours=3)).isoformat(timespec="minutes")
        blob = json.dumps({"task": "x", "last_tick": past})
        rep = run(target(tmp_path, **{"status.json": blob}))
        assert levels(rep, "status.json") == [lint.OK]

    def test_an_unparseable_last_tick_is_not_an_error(self, tmp_path):
        # The field is optional and a target may write a shape this does not
        # know. Only a CONFIDENTLY future time is reported.
        blob = json.dumps({"task": "x", "last_tick": "just now"})
        rep = run(target(tmp_path, **{"status.json": blob}))
        assert levels(rep, "status.json") == [lint.OK]

    def test_top_level_must_be_an_object(self, tmp_path):
        rep = run(target(tmp_path, **{"status.json": "[1, 2]"}))
        assert ERRORS(rep, "status.json")


class TestWatchPort:
    def test_a_sane_port_is_ok(self, tmp_path):
        rep = run(target(tmp_path, **{"watch-port": "35110\n"}))
        assert levels(rep, "watch-port") == [lint.OK]

    def test_junk_is_an_error(self, tmp_path):
        rep = run(target(tmp_path, **{"watch-port": "not-a-port"}))
        assert ERRORS(rep, "watch-port")

    def test_out_of_range_is_an_error(self, tmp_path):
        rep = run(target(tmp_path, **{"watch-port": "99999"}))
        assert ERRORS(rep, "watch-port")

    def test_absent_is_a_warning(self, tmp_path):
        rep = run(target(tmp_path))
        assert levels(rep, "watch-port") == [lint.WARN]


class TestOtherFiles:

    def test_skill_version_naming_a_nonexistent_migration_is_an_error(self, tmp_path):
        rep = run(target(tmp_path, **{"skill-version": "2099-01-01-99-nope.md\n"}))
        assert ERRORS(rep, "skill-version")

    def test_skill_version_naming_a_real_migration_is_ok(self, tmp_path):
        real = sorted((lint.SKILL_DIR / "migrations").glob("2026-*.md"))[-1].name
        rep = run(target(tmp_path, **{"skill-version": real + "\n"}))
        assert levels(rep, "skill-version") == [lint.OK]

    def test_misnamed_dream_is_a_warning_only(self, tmp_path):
        rep = run(target(tmp_path, **{"dreams__notes.md": "x"}))
        assert levels(rep, "dreams/") == [lint.WARN]
        assert not rep.failed


class TestExitCodes:
    def test_clean_target_exits_zero(self, tmp_path, capsys):
        t = target(tmp_path, **{"questions.md": GOOD})
        assert lint.main(["--target", str(t)]) == 0

    def test_broken_target_exits_one(self, tmp_path, capsys):
        t = target(tmp_path, **{"questions.md": BROKEN})
        assert lint.main(["--target", str(t)]) == 1

    def test_non_target_exits_two(self, tmp_path, capsys):
        assert lint.main(["--target", str(tmp_path)]) == 2

    def test_watch_unimportable_degrades_rather_than_crashing(self, tmp_path, monkeypatch):
        # Another dreamer may be mid-edit in watch.py. The linter still runs
        # every check that does not need it, and says the entries are
        # unverified rather than claiming they are fine.
        monkeypatch.setattr(lint, "load_watch", lambda: None)
        rep = run(target(tmp_path, **{"questions.md": GOOD}))
        assert levels(rep, "questions.md") == [lint.WARN]
        assert not rep.failed
