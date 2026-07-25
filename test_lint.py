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


_FRESH = [0]


def fresh(tmp_path: Path) -> Path:
    """A never-before-used dir under tmp_path.

    `target()` mkdirs unconditionally, so a test that checks TWO files dies
    on FileExistsError rather than on its assertion — which has now cost two
    debugging detours. Call this whenever a test builds more than one.
    """
    _FRESH[0] += 1
    sub = tmp_path / f"t{_FRESH[0]}"
    sub.mkdir()
    return sub


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
    lint.check_watch_tint(dw, watch, rep)
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


class TestPluginCommands:
    """Commands a plugin declares into the target (#86).

    The file exists because watch.py reads the TARGET and plugin skills do
    not live there. Both failure modes it guards are silent: a menu entry
    whose plugin is gone, and a plugin quietly taking over a core command.
    """

    class FakeWatch:
        COMMANDS = ({"kind": "add-idea"}, {"kind": "do-next"}, {"kind": "maintenance"})

    PLUGINS = """\
# DREAMWORK.md

## Plugins

- Load: `ud-dreamwork-github` (2026-07-25) — the forge presence.
- Don't load: `ud-dreamwork-nope`
"""

    def run_pc(self, t, watch=None):
        rep = lint.Report()
        lint.check_plugin_commands(t / ".dreamwork", watch or self.FakeWatch, rep)
        return rep

    def decl(self, tmp_path, commands, dreamwork=None):
        t = target(tmp_path, **{"plugin-commands.json": json.dumps({"commands": commands})})
        if dreamwork is not None:
            (t / "DREAMWORK.md").write_text(dreamwork)
        return t

    GH = {"kind": "gh-sync", "label": "gh sync", "desc": "re-poll the forge now",
          "plugin": "ud-dreamwork-github"}

    def test_absent_is_silent(self, tmp_path):
        # Most targets load nothing that declares commands. A note on each
        # of them is what hides the one that matters.
        assert self.run_pc(target(tmp_path)).rows == []

    def test_a_loaded_plugins_command_is_ok(self, tmp_path):
        rep = self.run_pc(self.decl(tmp_path, [self.GH], self.PLUGINS))
        assert [lvl for lvl, _, _ in rep.rows] == [lint.OK]

    def test_an_empty_list_is_ok_not_an_error(self, tmp_path):
        # A plugin that declares nothing is the common case, and the menu
        # shows no empty section for it.
        rep = self.run_pc(self.decl(tmp_path, [], self.PLUGINS))
        assert not rep.failed and "none" in rep.rows[0][2]

    def test_a_command_from_an_unloaded_plugin_is_stale(self, tmp_path):
        stale = dict(self.GH, plugin="ud-dreamwork-gone")
        rep = self.run_pc(self.decl(tmp_path, [stale], self.PLUGINS))
        assert rep.failed
        assert "not loaded" in rep.rows[0][2] and "ud-dreamwork-gone" in rep.rows[0][2]

    def test_no_plugins_section_is_unverified_not_stale(self, tmp_path):
        # THE CRY-WOLF CASE. Silence in DREAMWORK.md is not a claim that
        # nothing is loaded, and treating it as one marks every declared
        # command stale on a target that simply never wrote the section.
        rep = self.run_pc(self.decl(tmp_path, [self.GH], "# DREAMWORK.md\n\n## Goals\n\n- one\n"))
        assert not rep.failed
        assert [lvl for lvl, _, _ in rep.rows] == [lint.WARN]

    def test_shadowing_a_core_command_is_an_error(self, tmp_path):
        # writing-plugins.md forbids this in prose. Prose cannot refuse.
        bad = dict(self.GH, kind="do-next")
        rep = self.run_pc(self.decl(tmp_path, [bad], self.PLUGINS))
        assert rep.failed and "shadows" in rep.rows[0][2]

    def test_the_core_namespace_is_reserved(self, tmp_path):
        # `do-anything` reads as core to the human even though no core
        # command owns that exact kind.
        bad = dict(self.GH, kind="do-something")
        rep = self.run_pc(self.decl(tmp_path, [bad], self.PLUGINS))
        assert rep.failed and "namespace" in rep.rows[0][2]

    def test_core_kinds_come_from_watch_not_a_copy(self, tmp_path):
        # Discrimination: with a watch whose COMMANDS lack `do-next`, the
        # same file must PASS — proving the ban tracks the real table.
        class Other:
            COMMANDS = ({"kind": "add-idea"},)
        rep = self.run_pc(self.decl(tmp_path, [dict(self.GH, kind="do-next")], self.PLUGINS), Other)
        assert not rep.failed

    def test_an_unnamespaced_kind_is_an_error(self, tmp_path):
        rep = self.run_pc(self.decl(tmp_path, [dict(self.GH, kind="sync")], self.PLUGINS))
        assert rep.failed

    def test_two_plugins_claiming_one_kind_is_an_error(self, tmp_path):
        other = dict(self.GH, plugin="ud-dreamwork-github", label="other")
        rep = self.run_pc(self.decl(tmp_path, [self.GH, other], self.PLUGINS))
        assert rep.failed
        assert any("never runs" in d for _, _, d in rep.rows)

    def test_a_missing_field_names_it(self, tmp_path):
        rep = self.run_pc(self.decl(tmp_path, [{"kind": "gh-sync"}], self.PLUGINS))
        assert rep.failed
        assert "label" in rep.rows[0][2] and "desc" in rep.rows[0][2]

    def test_unparseable_json_says_the_menu_is_empty(self, tmp_path):
        t = target(tmp_path, **{"plugin-commands.json": "{not json"})
        rep = self.run_pc(t)
        assert rep.failed and "no plugin commands" in rep.rows[0][2]

    def test_wrong_toplevel_shape_is_an_error(self, tmp_path):
        t = target(tmp_path, **{"plugin-commands.json": json.dumps([{"kind": "gh-sync"}])})
        assert self.run_pc(t).failed


class TestWatchTint:
    """His colour. The check exists because an unknown name does not break
    the page — it silently ignores what he chose."""

    class FakeWatch:
        TINTS = {"indigo": 229, "teal": 188, "rose": 348}

    def run_tint(self, t, watch):
        rep = lint.Report()
        lint.check_watch_tint(t / ".dreamwork", watch, rep)
        return rep

    def test_absent_is_silent_not_a_warning(self, tmp_path):
        # Deliberately unlike watch-port: most targets never set a colour,
        # and a WARN on every one of them hides the real one.
        rep = self.run_tint(target(tmp_path), self.FakeWatch)
        assert rep.rows == []

    def test_a_known_name_is_ok(self, tmp_path):
        t = target(tmp_path, **{"watch-tint": "teal\n"})
        rep = self.run_tint(t, self.FakeWatch)
        assert [lvl for lvl, _, _ in rep.rows] == [lint.OK]

    def test_an_unknown_name_is_an_error_naming_the_alternatives(self, tmp_path):
        t = target(tmp_path, **{"watch-tint": "chartreuse"})
        rep = self.run_tint(t, self.FakeWatch)
        assert rep.failed
        detail = rep.rows[0][2]
        assert "chartreuse" in detail and "indigo" in detail

    def test_unverifiable_when_watch_is_unreadable(self, tmp_path):
        # Another agent mid-edit in watch.py must not turn into a false ERROR.
        rep = self.run_tint(target(tmp_path, **{"watch-tint": "teal"}), None)
        assert [lvl for lvl, _, _ in rep.rows] == [lint.WARN]
        assert not rep.failed


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

    def test_a_future_stamped_dream_is_an_error(self, tmp_path):
        # Three different dreamers stamped a dream ahead of the clock on
        # 2026-07-25, one by 65 minutes. The filename IS the ordering, so a
        # future stamp sorts wrong permanently — unlike status.json's
        # last_tick, which is merely wrong until the next write.
        from datetime import datetime, timedelta
        ahead = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d-%H%M")
        rep = run(target(tmp_path, **{f"dreams__{ahead}-a-dream.md": "x"}))
        assert ERRORS(rep, "dreams/")
        assert "FUTURE" in next(d for _, w, d in rep.rows if w == "dreams/")

    def test_a_past_stamped_dream_is_fine(self, tmp_path):
        from datetime import datetime, timedelta
        past = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d-%H%M")
        rep = run(target(tmp_path, **{f"dreams__{past}-a-dream.md": "x"}))
        assert levels(rep, "dreams/") == [lint.OK]


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


class TestQuestionPriorities:
    """#197 — an optional `P1 · ` prefix on the entry title, absent = P2.

    Only one failure is worth an error and it is the quiet one: `P4 · `
    reads to a human as prioritised and sorts as unmarked, so the entry he
    most wants seen sits mid-list looking urgent.
    """

    def q(self, *titles):
        body = "\n\n".join(f"- **{t}**\n  Body prose." for t in titles)
        return f"# Questions\n\n## Open\n\n{body}\n\n## Answered\n"

    def run_q(self, tmp_path, text):
        sub = fresh(tmp_path)
        rep = lint.Report()
        lint.check_questions(target(sub, **{"questions.md": text}) / ".dreamwork",
                             lint.load_watch(), rep)
        return rep

    def test_valid_markers_pass(self, tmp_path):
        rep = self.run_q(tmp_path, self.q("P1 \u00b7 urgent", "P3 \u00b7 whenever"))
        assert not rep.failed

    def test_no_marker_is_normal(self, tmp_path):
        # Most entries will never carry one; unmarked must say nothing.
        assert not self.run_q(tmp_path, self.q("2026-07-25 \u2014 an ordinary ask")).failed

    def test_a_marker_outside_the_band_is_an_error(self, tmp_path):
        rep = self.run_q(tmp_path, self.q("P4 \u00b7 looks urgent, sorts as unmarked"))
        assert rep.failed
        assert "P4" in rep.rows[0][2]

    def test_p0_too(self, tmp_path):
        assert self.run_q(tmp_path, self.q("P0 \u00b7 even more so")).failed

    def test_a_colon_or_dash_separator_is_recognised(self, tmp_path):
        # So a near-miss cannot slip past the check by punctuation alone.
        assert self.run_q(tmp_path, self.q("P9: wrong")).failed
        assert self.run_q(tmp_path, self.q("P9 - wrong")).failed

    def test_a_title_merely_starting_with_P_is_not_a_marker(self, tmp_path):
        # Discrimination: "PROPOSAL" must not be read as a priority.
        assert not self.run_q(tmp_path, self.q("PROPOSAL \u00b7 rename the thing")).failed
        assert not self.run_q(tmp_path, self.q("P versus NP, briefly")).failed


class TestSubmissionsLog:
    """#199 — his words, written before anything can lose them.

    The file exists because an answer that failed to match its entry was
    discarded with a 409 and recorded nowhere. So the check must not punish
    the file for the situation it was built for.
    """

    def run_s(self, tmp_path, text):
        rep = lint.Report()
        lint.check_submissions(
            target(fresh(tmp_path), **{"submissions.log": text}) / ".dreamwork", rep)
        return rep

    def rec(self, **kw):
        base = {"t": "2026-07-25T17:43:00", "path": "/answer", "bytes": 42,
                "req": {"title": "a question", "answer": "his words"}}
        base.update(kw)
        return json.dumps(base)

    def test_absent_is_silent(self, tmp_path):
        rep = lint.Report()
        lint.check_submissions(target(tmp_path) / ".dreamwork", rep)
        assert rep.rows == []

    def test_good_records_count(self, tmp_path):
        rep = self.run_s(tmp_path, self.rec() + "\n" + self.rec(path="/command") + "\n")
        assert not rep.failed and "2 submission" in rep.rows[0][2]

    def test_a_torn_last_line_is_a_WARN_not_an_error(self, tmp_path):
        # THE ONE THAT MATTERS. A crash mid-append is exactly what this file
        # is for; going red would mean shouting loudest when the log worked.
        text = self.rec() + "\n" + '{"t": "2026-07-25T17:44:00", "path": "/ans'
        rep = self.run_s(tmp_path, text)
        assert not rep.failed, "a torn tail must not fail the gate"
        assert any(lvl == lint.WARN for lvl, _, _ in rep.rows)
        assert any("1 submission" in d for _, _, d in rep.rows), "intact lines still counted"

    def test_a_malformed_line_in_the_MIDDLE_is_an_error(self, tmp_path):
        # The complement: not a dead process, a broken writer.
        text = self.rec() + "\n" + "{not json\n" + self.rec() + "\n"
        assert self.run_s(tmp_path, text).failed

    def test_raw_requires_why(self, tmp_path):
        text = json.dumps({"t": "x", "path": "/answer", "bytes": 3, "raw": "..."}) + "\n"
        assert self.run_s(tmp_path, text).failed

    def test_why_without_raw_is_an_error(self, tmp_path):
        text = json.dumps({"t": "x", "path": "/answer", "bytes": 3,
                           "req": {}, "why": "json"}) + "\n"
        assert self.run_s(tmp_path, text).failed

    def test_both_req_and_raw_is_an_error(self, tmp_path):
        text = json.dumps({"t": "x", "path": "/a", "bytes": 3, "req": {},
                           "raw": "x", "why": "json"}) + "\n"
        assert self.run_s(tmp_path, text).failed

    def test_a_valid_unparseable_body_record_passes(self, tmp_path):
        text = json.dumps({"t": "x", "path": "/answer", "bytes": 9,
                           "raw": "\udcff not utf8", "why": "decode"}) + "\n"
        assert not self.run_s(tmp_path, text).failed

    def test_missing_required_keys_is_an_error(self, tmp_path):
        assert self.run_s(tmp_path, json.dumps({"req": {}}) + "\n").failed

    def test_bytes_must_be_an_int(self, tmp_path):
        assert self.run_s(tmp_path, self.rec(bytes="42") + "\n").failed

    def test_truncated_false_is_an_error(self, tmp_path):
        # The contract says absent, never false — so `false` means a writer
        # that does not know the contract.
        assert self.run_s(tmp_path, self.rec(truncated=False) + "\n").failed
        assert not self.run_s(tmp_path, self.rec(truncated=True) + "\n").failed

    def test_empty_file_is_fine(self, tmp_path):
        rep = self.run_s(tmp_path, "")
        assert not rep.failed and "no submissions" in rep.rows[0][2]
