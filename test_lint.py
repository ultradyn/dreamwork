"""Tests for lint.py.

The first test is the one that matters: the linter must go RED on the exact
file shape that failed silently in the field. A checker that has never been
red proves nothing, and this repo has now caught three checks that were
passing on their own bug.
"""

import json
import re
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
    """Run exactly what `lint.py` runs — never a second copy of the list.

    This helper used to hand-maintain its own sequence and had drifted six
    checks behind main(), so a newly added check was tested by nothing while
    its tests passed. `lint.run_checks` is now the single definition.
    """
    rep = lint.Report()
    lint.run_checks(t / ".dreamwork", lint.load_watch(), rep)
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


class TestTaskOrigin:
    """#213 — forward-only provenance, enforced from the #216 cutoff.

    From the cutoff onward, who filed a task is a fact recorded at filing
    time; before it, the fact was never written down and must NOT be
    reconstructed by guessing. So the rule looks only forward: an entry
    naming any id >= 216 carries exactly one `origin: **human**` /
    `**loop**` / `**unknown**`, and older entries are not checked at all.
    `unknown` is a first-class truthful value, never a failure.
    """

    def ledger(self, *entries):
        body = "\n\n".join(entries)
        return f"# Task ledger\n\nNext id: **300**\n\n## Open\n\n{body}\n"

    def run_l(self, tmp_path, text):
        return run(target(fresh(tmp_path), **{"tasks.md": text}))

    def origin_rows(self, rep):
        return [d for _, w, d in rep.rows if w == "tasks.md"]

    def test_a_new_task_without_origin_is_an_error(self, tmp_path):
        text = self.ledger("- **#216** — a new task · P2 · task · 20m")
        rep = self.run_l(tmp_path, text)
        assert ERRORS(rep, "tasks.md")
        detail = next(d for d in self.origin_rows(rep) if "#216" in d)
        # The message names the task AND the accepted vocabulary — "origin
        # is wrong" reads as nonsense to someone who never heard the rule.
        assert "origin: **human**" in detail
        assert "origin: **loop**" in detail
        assert "origin: **unknown**" in detail

    def test_each_valid_value_is_accepted(self, tmp_path):
        for value in ("human", "loop", "unknown"):
            text = self.ledger(
                f"- **#216** — a new task · P2 · task · 20m · origin: **{value}**")
            rep = self.run_l(tmp_path, text)
            assert not ERRORS(rep, "tasks.md"), value

    def test_explicit_unknown_is_truthful_coverage_not_a_failure(self, tmp_path):
        # The migration value: a post-cutoff task whose origin was never
        # recorded says unknown rather than being guessed.
        text = self.ledger(
            "- **#250** — landed before the contract existed · P1 · landed\n"
            "  2026-07-27 · origin: **unknown** · did the thing")
        rep = self.run_l(tmp_path, text)
        assert not ERRORS(rep, "tasks.md")

    def test_an_unmarked_old_task_is_accepted(self, tmp_path):
        # Historical entries stay unmarked: absent reads as historical
        # unknown, and nobody backfills a guess.
        text = self.ledger("- **#100** — an old task · P2 · idea · 30m")
        rep = self.run_l(tmp_path, text)
        assert not ERRORS(rep, "tasks.md")

    def test_the_cutoff_boundary_is_exact(self, tmp_path):
        # 215 is history, 216 is the first governed id — same file, so the
        # boundary itself is what is exercised, not two separate ledgers.
        text = self.ledger(
            "- **#215** — the last ungoverned task · P2 · task",
            "- **#216** — the first governed task · P2 · task")
        rep = self.run_l(tmp_path, text)
        assert ERRORS(rep, "tasks.md")
        detail = next(d for d in self.origin_rows(rep) if lint.ERROR and "#216" in d)
        assert "#215" not in detail

    def test_an_invalid_value_is_an_error_naming_the_vocabulary(self, tmp_path):
        text = self.ledger("- **#216** — a task · P2 · origin: **bot**")
        rep = self.run_l(tmp_path, text)
        assert ERRORS(rep, "tasks.md")
        detail = next(d for d in self.origin_rows(rep) if "#216" in d)
        assert "bot" in detail and "human" in detail and "loop" in detail

    def test_the_wrong_case_is_an_error(self, tmp_path):
        # The vocabulary is lowercase; `Human` is a marker-shaped claim the
        # reader would have to interpret, and interpreting is guessing.
        text = self.ledger("- **#216** — a task · P2 · origin: **Human**")
        assert ERRORS(self.run_l(tmp_path, text), "tasks.md")

    def test_two_markers_on_one_entry_is_an_error(self, tmp_path):
        # Exactly one: a second marker makes the first unreadable as fact.
        text = self.ledger(
            "- **#216** — a task · P2 · origin: **human** · origin: **loop**")
        rep = self.run_l(tmp_path, text)
        assert ERRORS(rep, "tasks.md")

    def test_a_duplicate_of_the_same_marker_is_still_an_error(self, tmp_path):
        text = self.ledger(
            "- **#216** — a task · P2 · origin: **unknown** · origin: **unknown**")
        assert ERRORS(self.run_l(tmp_path, text), "tasks.md")

    def test_combined_ids_require_origin_when_any_id_is_new(self, tmp_path):
        # The enforcement key is every numeric id in the leading token:
        # #250/#251 are both governed, so the combined entry is governed.
        text = self.ledger(
            "- **#250/#251** — a combined landing · P1/P2 · landed 2026-07-27")
        assert ERRORS(rep := self.run_l(tmp_path, text), "tasks.md")
        assert "#250" in next(d for d in self.origin_rows(rep) if "#250" in d)

    def test_combined_ids_all_old_are_exempt(self, tmp_path):
        # #138/#156 landed as a combined summary; both predate the cutoff,
        # so the entry stays unmarked and is never demanded a marker.
        text = self.ledger(
            "- **#138/#156** — an old combined landing · P2 · landed 2026-07-27")
        assert not ERRORS(rep := self.run_l(tmp_path, text), "tasks.md")

    def test_a_body_cross_reference_is_not_the_entrys_id(self, tmp_path):
        # `blocked on #264` in the body does not make an old entry governed;
        # only the leading bold token numbers the entry. The inverse hole —
        # absorbing body ids — would demand markers on most of history.
        text = self.ledger(
            "- **#100** — an old task · P2 · task · blocked on #264, relates #299")
        assert not ERRORS(self.run_l(tmp_path, text), "tasks.md")

    def test_a_marker_may_hard_wrap_like_the_real_entries(self, tmp_path):
        # #288 and #252 wrap `origin:` onto the next line; the linter joins
        # the entry's lines before reading, as the title rule already does.
        text = self.ledger(
            "- **#288** — a task with a long title that wraps · P0/P1 · origin:\n"
            "  **loop** · the body continues here")
        assert not ERRORS(self.run_l(tmp_path, text), "tasks.md")

    def test_a_marker_on_a_later_continuation_line_is_found(self, tmp_path):
        text = self.ledger(
            "- **#216** — a task · P2 · task · 20m ·\n"
            "  origin: **loop** · blocked on #213")
        assert not ERRORS(self.run_l(tmp_path, text), "tasks.md")

    def test_prose_after_an_entry_is_not_part_of_it(self, tmp_path):
        # Recently landed holds column-0 prose summaries after the last
        # entry; an `origin:` claim in them must not charge the entry above.
        text = (
            "# Task ledger\n\nNext id: **300**\n\n## Open\n\n"
            "- **#216** — a governed task · P2 · task · origin: **loop**\n"
            "\n## Recently landed\n\n"
            "- **#215** — an old landing · P2 · landed 2026-07-26\n"
            "\n**#214** a prose summary mentioning origin: **bot** in passing.\n")
        assert not ERRORS(self.run_l(tmp_path, text), "tasks.md")

    def test_a_marker_shaped_non_value_on_a_new_entry_is_invalid(self, tmp_path):
        # `origin: **human|loop**` is neither value; on a governed entry it
        # is an invalid claim, not a missing one.
        text = self.ledger("- **#216** — a task · P2 · origin: **human|loop**")
        assert ERRORS(self.run_l(tmp_path, text), "tasks.md")

    def test_a_quoted_spec_line_in_an_old_entry_is_prose(self, tmp_path):
        # #213's own entry quotes `origin: **human|loop**` as its spec.
        # Pre-cutoff entries are not checked at all, so the quote stays.
        text = self.ledger(
            "- **#213** — the provenance task · P2 · record `origin: **human|loop**`\n"
            "  on every task from cutoff #216 onward")
        assert not ERRORS(self.run_l(tmp_path, text), "tasks.md")


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


class TestStatusPush:
    """#190 — `push` is how the dashboard learns the loop's channel to him is
    dead. The data has three distinguishable states (never tried / landed /
    failed) and lint's job is the SHAPE: a malformed `push` is a writer bug,
    and a writer bug here is exactly the silent class this file exists for —
    the loop believed it reported a fault and the dashboard rendered nothing.

    Lint must not treat a FAILED push (`ok:false`) as an error: that is a
    truthful runtime claim, not a broken file. Only a wrong TYPE is broken.
    The "three states are distinguishable" assertion lives in the browser
    guard (it is a property of the render); here we assert lint accepts all
    three shapes and rejects only malformed ones.
    """

    PUSH_OK = json.dumps({"push": {
        "at": "2026-07-27T20:17:00+10:00",
        "channel": "attn",
        "ok": True,
        "detail": "delivered",
    }})
    PUSH_FAIL = json.dumps({"push": {
        "at": "2026-07-27T20:17:00+10:00",
        "channel": "attn",
        "ok": False,
        "detail": "403 — out of credits or need a Grok subscription",
    }})

    def test_absent_push_is_clean(self, tmp_path):
        # never tried is one of the three states and lints as valid.
        rep = run(target(tmp_path, **{"status.json": '{"task": "x"}'}))
        assert levels(rep, "status.json") == [lint.OK]

    def test_a_successful_push_is_clean(self, tmp_path):
        rep = run(target(tmp_path, **{"status.json": self.PUSH_OK}))
        assert levels(rep, "status.json") == [lint.OK]

    def test_a_failed_push_is_NOT_an_error(self, tmp_path):
        # ok:false is a truthful runtime claim, not a broken file. Lint crying
        # red on it would punish the loop for reporting the very fault this
        # field exists to surface.
        rep = run(target(tmp_path, **{"status.json": self.PUSH_FAIL}))
        assert levels(rep, "status.json") == [lint.OK]

    def test_push_that_is_not_an_object_is_an_error(self, tmp_path):
        rep = run(target(tmp_path, **{"status.json": '{"push": "down"}'}))
        assert ERRORS(rep, "status.json")

    def test_push_ok_must_be_bool(self, tmp_path):
        # the renderer branches on `p.ok === false` (strict), so a string
        # "false" would never trip the fault branch and the failure would be
        # silent again — the exact class this check exists for.
        bad = json.dumps({"push": {"at": "x", "channel": "attn",
                                   "ok": "no", "detail": "y"}})
        rep = run(target(tmp_path, **{"status.json": bad}))
        assert ERRORS(rep, "status.json")
        # check_status adds an OK row first, so find the ERROR row specifically
        # — `next(...)` on the OK row was how this test passed while reading
        # the wrong line.
        err = next(d for lvl, w, d in rep.rows
                   if w == "status.json" and lvl == lint.ERROR)
        assert "ok" in err

    def test_push_channel_and_detail_must_be_strings(self, tmp_path):
        bad = json.dumps({"push": {"at": "x", "channel": 403,
                                   "ok": False, "detail": 7}})
        rep = run(target(tmp_path, **{"status.json": bad}))
        assert ERRORS(rep, "status.json")

    def test_push_at_must_be_a_string(self, tmp_path):
        bad = json.dumps({"push": {"at": 1234567890, "channel": "attn",
                                   "ok": False, "detail": "y"}})
        rep = run(target(tmp_path, **{"status.json": bad}))
        assert ERRORS(rep, "status.json")

    def test_push_at_in_the_future_is_an_error(self, tmp_path):
        # the dashboard's thesis is liveness, so a push timestamp must come
        # from the clock, never from memory — same bias and same rule as
        # `last_tick`. A future `at` would make "failed 4m ago" lie.
        from datetime import datetime, timedelta
        ahead = (datetime.now() + timedelta(minutes=20)).isoformat(timespec="minutes")
        bad = json.dumps({"push": {"at": ahead, "channel": "attn",
                                   "ok": False, "detail": "y"}})
        rep = run(target(tmp_path, **{"status.json": bad}))
        assert ERRORS(rep, "status.json")
        err = next(d for lvl, w, d in rep.rows
                   if w == "status.json" and lvl == lint.ERROR)
        assert "FUTURE" in err

    def test_unknown_keys_inside_push_are_not_an_error(self, tmp_path):
        # status.json's key list is a MENU not a whitelist (#310), and the
        # rule descends into `push` too: the loop may grow the object, and a
        # check that rejected unknown subfields would red the first addition.
        blob = json.dumps({"push": {"at": "x", "channel": "attn",
                                    "ok": True, "detail": "y",
                                    "retries": 3, "fallback": "PushNotification"}})
        rep = run(target(tmp_path, **{"status.json": blob}))
        assert levels(rep, "status.json") == [lint.OK]


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


class TestDreamworkFrontmatter:
    """#194 — the version stamp the upgrade check compares against.

    DREAMWORK.md may open with YAML frontmatter carrying `dreamwork-version`:
    the first token of `bin/ud-dw-githash` output as last reconciled. The file
    is the human's, so absence and extra keys stay survivable (WARN); what
    goes red is a stamp that would lie to the comparison — a dirty
    annotation stored as identity, a truncated sha, an unclosed block.
    """

    def check(self, tmp_path, dreamwork_md):
        t = target(fresh(tmp_path))
        if dreamwork_md is not None:
            (t / "DREAMWORK.md").write_text(dreamwork_md)
        rep = lint.Report()
        lint.check_dreamwork_frontmatter(t / ".dreamwork", rep)
        return rep

    GOOD = "---\ndreamwork-version: 5853e1789929\n---\n# DREAMWORK.md\n\nGoals.\n"

    def test_a_stamped_file_is_ok(self, tmp_path):
        rep = self.check(tmp_path, self.GOOD)
        assert not rep.failed
        assert all(lvl == lint.OK for lvl, _, _ in rep.rows)

    def test_unknown_is_a_legal_version_not_an_error(self, tmp_path):
        # Fresh zip install, no git: "unknown" is a normal quiet state.
        rep = self.check(tmp_path, "---\ndreamwork-version: unknown\n---\n# x\n")
        assert not rep.failed

    def test_no_frontmatter_is_a_warn_because_old_targets_are_legal(self, tmp_path):
        rep = self.check(tmp_path, "# DREAMWORK.md\n\nGoals.\n")
        assert not rep.failed
        assert any(lvl == lint.WARN for lvl, _, _ in rep.rows)

    def test_absent_file_is_a_warn(self, tmp_path):
        rep = self.check(tmp_path, None)
        assert not rep.failed
        assert any(lvl == lint.WARN for lvl, _, _ in rep.rows)

    def test_a_dirty_annotation_stored_as_identity_is_an_error(self, tmp_path):
        # The githash tool prints "sha +3" live; only the first token is
        # identity. Storing the annotation makes every comparison miss.
        rep = self.check(tmp_path, "---\ndreamwork-version: 5853e1789929 +3\n---\n# x\n")
        assert rep.failed

    def test_a_truncated_sha_is_an_error(self, tmp_path):
        rep = self.check(tmp_path, "---\ndreamwork-version: 5853e17\n---\n# x\n")
        assert rep.failed

    def test_frontmatter_without_the_key_is_an_error(self, tmp_path):
        # A block that exists but says nothing reads as stamped at a glance.
        rep = self.check(tmp_path, "---\nother-key: value\n---\n# x\n")
        assert rep.failed

    def test_an_unclosed_block_is_an_error(self, tmp_path):
        rep = self.check(tmp_path, "---\ndreamwork-version: 5853e1789929\n# x\n")
        assert rep.failed

    def test_extra_keys_warn_so_growth_is_deliberate(self, tmp_path):
        rep = self.check(
            tmp_path,
            "---\ndreamwork-version: 5853e1789929\nflavour: grape\n---\n# x\n")
        assert not rep.failed
        assert any(lvl == lint.WARN for lvl, _, _ in rep.rows)

    def test_a_typoed_key_cannot_read_as_merely_unstamped(self, tmp_path):
        # dreamwork-verison: the required-key ERROR is what catches this;
        # if it ever demotes to the absent-frontmatter WARN, typos vanish.
        rep = self.check(tmp_path, "---\ndreamwork-verison: 5853e1789929\n---\n# x\n")
        assert rep.failed


class TestPriorityMarkers:
    """#197 — a title that reads as prioritised and does not sort that way.

    The check's whole job is the QUIET failure, so every test here is about
    a file the linter used to pass.
    """

    def one(self, tmp_path, title):
        return run(target(fresh(tmp_path), **{"questions.md":
            "# Questions for the human\n\n## Open\n\n"
            f"- **{title}** a body.\n\n## Answered\n"}))

    def test_the_three_legal_markers_say_nothing(self, tmp_path):
        for title in ("P1 · blocks work", "P2 · soon",
                      "P3 · whenever", "no marker at all"):
            rep = self.one(tmp_path, title)
            assert not ERRORS(rep, "questions.md"), title

    def test_a_band_outside_the_three_is_an_error(self, tmp_path):
        for title in ("P4 · x", "P0 · x", "P9 · x"):
            rep = self.one(tmp_path, title)
            assert ERRORS(rep, "questions.md"), title

    def test_a_legal_BAND_with_an_illegal_SEPARATOR_is_an_error(self, tmp_path):
        # THE HOLE THIS CLOSED, and it is the whole reason the linter asks
        # watch.py for the band instead of re-deriving it. The check shipped
        # with its own copy of the marker rule, and the copy was the more
        # permissive of the two: each of these read to a human as a perfectly
        # good P1, sorted as unmarked, and the linter said nothing.
        for title in ("P1: blocks work", "P1·blocks work",
                      "P1 - blocks work", "P3:whenever"):
            rep = self.one(tmp_path, title)
            assert ERRORS(rep, "questions.md"), title
            detail = next(d for _, w, d in rep.rows if w == "questions.md")
            # ...and it names the FIX. "P1 is wrong" reads as nonsense to
            # someone who just typed a perfectly good P1.
            assert "·" in detail and "wants" in detail, detail

    def test_P2_with_an_odd_separator_is_NOT_an_error(self, tmp_path):
        # `P2: soon` is not honoured by the parser either — but unmarked
        # already means P2, so it sorts exactly where its author wanted. The
        # check reports an OUTCOME (it does not sort as it reads), not a
        # pattern, so this correctly says nothing.
        rep = self.one(tmp_path, "P2: soon")
        assert not ERRORS(rep, "questions.md")

    def test_the_linter_never_re_derives_the_band(self, tmp_path):
        # The structural half of the same claim: if lint.py grows a second
        # copy of the mapping, these two disagree again the next time
        # watch.py's rule moves.
        import inspect
        src = inspect.getsource(lint.check_priorities)
        assert "watch.title_priority" in src, \
            "the band must come from watch.py, never from a copy in here"


class TestLedgerSectionSplit:
    """#304: two independent readers must agree on where the open section is.

    `watch.parse_ledger` once located the sections with an unanchored
    `str.split` on the heading text, so an entry whose PROSE quoted a heading
    became the split point. The ledger read 2 open / 187 landed against a true
    105 / 84 and every derived number on the dashboard was wrong — while this
    linter reported the file clean, because it counts entries without
    splitting sections at all. The check exists to make that divergence loud,
    so the test reintroduces the OLD ALGORITHM rather than asserting on a
    hand-written number: a guard for a regression has to be shown failing on
    the regression.
    """

    # Never write the literal heading sequences in this file either — the same
    # trap one layer up, and a test file is read by the same eyes.
    OPEN = "## " + "Open"
    LANDED = "## " + "Recently landed"

    HAZARD = (
        "# Task ledger\n\nNext id: **9**\n\n" + OPEN + "\n\n"
        "- **#7** — a live one · P2 · task\n"
        "  · prose quoting `" + LANDED + "` while describing the parser\n"
        "- **#8** — another · P3 · idea\n\n"
        + LANDED + "\n\n**#5** landed (abc1234).\n"
    )

    def _old_parse_ledger(self, text):
        """The pre-#304 implementation, verbatim. This IS the bug."""
        import watch
        # The narrow entry-head rule the parser held at the time, pinned
        # locally so that widening the module-level LEDGER_ENTRY later (#315)
        # does not rewrite history: this reconstruction must stay the bug it
        # was, not track a fix applied elsewhere.
        narrow_entry = re.compile(r"^- \*\*#(\d+)\*\*", re.M)
        if not text or self.OPEN not in text:
            return set(), set()
        after = text.split(self.OPEN, 1)[1].split(self.LANDED, 1)
        landed = (set(watch.LEDGER_MENTION.findall(after[1]))
                  if len(after) > 1 else set())
        return set(narrow_entry.findall(after[0])), landed

    def test_the_old_unanchored_split_is_caught(self, monkeypatch):
        import watch
        monkeypatch.setattr(watch, "parse_ledger", self._old_parse_ledger)
        rep = lint.Report()
        lint.check_ledger_sections(self.HAZARD, rep)
        assert ERRORS(rep, "tasks.md"), "a moved section split must go red"
        detail = next(d for _, w, d in rep.rows if w == "tasks.md")
        assert "1" in detail and "2" in detail, \
            "must report BOTH counts, so the reader can see which one is wrong"
        assert "#304" in detail, "must name the task that explains the failure"

    def test_the_anchored_split_agrees(self):
        rep = lint.Report()
        lint.check_ledger_sections(self.HAZARD, rep)
        assert not ERRORS(rep, "tasks.md"), \
            "an entry may quote a heading in prose; only a heading LINE counts"
        assert levels(rep, "tasks.md") == [lint.OK]

    def test_a_heading_line_still_opens_a_section(self):
        """The anchor must not have been achieved by matching nothing."""
        import watch
        openids, landed = watch.parse_ledger(self.HAZARD)
        assert openids == {"7", "8"}
        assert landed == {"5"}, "a real heading line must still end the open section"

    def test_a_combined_open_head_agrees_across_both_readers(self):
        """#315: a combined entry HEAD under Open (`- **#7/#8**`) names two
        ids on one line. Both readers must count BOTH ids, or the section
        cross-check fires a false #304 — which is exactly what happens if
        either reader widens without the other (a previous agent watched
        `test_combined_ids_all_old_are_exempt` go red proving it).

        The fixture head genuinely carries two DISTINCT ids, asserted at
        runtime by deriving both from the fixture: a literal pair is true
        only of today's fixture, and a future edit that collapsed them to
        one would pass vacuously. No combined head is open in the live
        ledger today, so this guard runs only against the fixture — which
        is the reason it exists, since a check that only ever ran against
        today's ledger proves nothing about the case it was written for.
        """
        import watch
        COMBINED_HEAD = "- **#7/#8**"
        text = ("# Task ledger\n\nNext id: **9**\n\n" + self.OPEN + "\n\n"
                + COMBINED_HEAD + " — a combined live one · P2 · task\n"
                + "- **#9** — a singular live one · P3 · idea\n\n"
                + self.LANDED + "\n\n**#5** landed (abc1234).\n")
        assert COMBINED_HEAD in text, "fixture must hold a combined head"
        # Runtime precondition is a property of the FIXTURE, not the pattern
        # under test, so derive both ids straight from the head string: a
        # literal pair is true only of today's fixture, and a future edit
        # that collapsed them to one would pass vacuously.
        head_ids = watch.ENTRY_ID.findall(COMBINED_HEAD)
        assert len(head_ids) == 2 and head_ids[0] != head_ids[1], \
            "fixture head must carry two distinct ids to be the combined case"
        rep = lint.Report()
        lint.check_ledger_sections(text, rep)
        assert not ERRORS(rep, "tasks.md"), \
            "both readers count both ids of the combined head — no #304 split"
        # And both readers genuinely SEE the combined ids, not just agree on
        # zero: an empty open section agrees trivially and proves nothing.
        openids, _landed = watch.parse_ledger(text)
        assert openids == {"7", "8", "9"}, \
            "the combined head contributed BOTH ids to the open set"


class TestLandedAsks:
    """#306: an ask whose subject has already shipped must not read as a gate.

    #290 was authorized in answers.md and its implementation landed and
    deployed, while the P1 question sat Open for ~15 hours — because the
    answering commit wrote the answer channel and the ledger and never touched
    the ask channel. A handoff had to carry a hand-written "this question is
    stale" caveat, which is a human remembering instead of a tool checking.

    WARN and not ERROR, deliberately: a legitimate amendment thread on a
    landed task exists, and this cannot tell one from a forgotten fold.
    """

    LEDGER = ("# Task ledger\n\nNext id: **9**\n\n" + "## " + "Open" + "\n\n"
              "- **#7** — still live · P2 · task · origin: **loop**\n\n"
              + "## " + "Recently landed" + "\n\n"
              "**#5** shipped (abc1234). **#6** shipped (def5678).\n")

    def _q(self, *titles):
        body = "# Questions for the human\n\n## Open\n\n"
        for ti in titles:
            body += f"- **{ti}** some body text.\n\n"
        return body + "## Answered\n\n"

    def test_an_ask_for_a_landed_task_warns(self, tmp_path):
        rep = run(target(tmp_path, **{
            "tasks.md": self.LEDGER,
            "questions.md": self._q("P1 · 2026-07-27 — #5 do the shipped thing?"),
        }))
        rows = [d for _, w, d in rep.rows if w == "questions.md" and "#5" in d]
        assert rows, "an open ask naming only a landed id must be reported"
        assert "landed" in rows[0], "must say WHY, not just name the id"
        assert lint.WARN in [l for l, w, _ in rep.rows if w == "questions.md"], \
            "this is a WARN: an amendment thread on a landed task is legitimate"

    def test_an_ask_naming_one_open_id_is_left_alone(self, tmp_path):
        """The rule is ALL named ids landed, not any — measured, not guessed.

        The naive any-landed rule fired on this repo's real
        `#229/#270 topic chats v2` question, where #270 had landed but #229 was
        still open, so the ask was genuinely live. A check that cries wolf on a
        live question teaches the reader to ignore it.
        """
        rep = run(target(tmp_path, **{
            "tasks.md": self.LEDGER,
            "questions.md": self._q("P1 · 2026-07-27 — #5/#7 half shipped?"),
        }))
        assert not [d for _, w, d in rep.rows if w == "questions.md" and "fold" in d], \
            "a question naming a still-open id must not be flagged"

    def test_a_prose_note_does_not_clear_it_and_the_message_admits_that(self, tmp_path):
        """The remedy a check suggests must be one that actually works.

        The first message said "add a note saying why it is still open". The
        check reads titles, so a note changes nothing — the entry would warn on
        every run forever, which is the cry-wolf failure the class docstring
        opens by naming. Both halves are asserted because either alone rots: a
        message-only test passes over a check that started reading bodies, and a
        behaviour-only test passes over a message that lies about it.
        """
        q = self._q("P1 · 2026-07-27 — #5 do the shipped thing?")
        noted = q.replace("some body text.",
                          "some body text.\n  · still open: the research produced the ask.")
        assert noted != q, "the note must actually be in the fixture"
        rows = [d for _, w, d in run(target(tmp_path, **{
            "tasks.md": self.LEDGER, "questions.md": noted,
        })).rows if w == "questions.md" and "#5" in d]
        assert rows, "a note in the body must NOT silence it — titles are what is read"
        assert "note" in rows[0] and "cannot clear" in rows[0], \
            "so the message must tell the reader a note will not work"
        assert "reopen" in rows[0], "and name the remedy that does, beside the fold"

    def test_an_ask_naming_no_task_is_left_alone(self, tmp_path):
        rep = run(target(tmp_path, **{
            "tasks.md": self.LEDGER,
            "questions.md": self._q("P2 · 2026-07-27 — a general policy question?"),
        }))
        assert not [d for _, w, d in rep.rows if w == "questions.md" and "fold" in d]

    def test_this_repo_has_no_forgotten_folds(self):
        rep = lint.Report()
        lint.check_landed_asks(lint.SKILL_DIR / ".dreamwork", lint.load_watch(), rep)
        assert not [d for l, w, d in rep.rows if l == lint.WARN], rep.render()


class TestDocMapPlans:
    """The row that enumerates a directory, and so drifts on its own."""

    ROW = "| `.dreamwork/docs/plans/` | Active feature plans ({}) | Prune |\n"

    def build(self, tmp_path: Path, listed: str, on_disk: list[str]) -> Path:
        t = fresh(tmp_path)
        docs = t / ".dreamwork" / "docs"
        (docs / "plans").mkdir(parents=True)
        for name in on_disk:
            (docs / "plans" / f"{name}.md").write_text("# a plan\n")
        (docs / "doc-map.md").write_text("# Doc map\n\n| Doc | Covers | Cur |\n|---|---|---|\n" + self.ROW.format(listed))
        return t

    def warns(self, t: Path):
        rep = lint.Report()
        lint.check_doc_map_plans(t / ".dreamwork", rep)
        return [d for l, w, d in rep.rows if l == lint.WARN and w == "doc-map.md"]

    def test_the_field_drift_goes_red(self, tmp_path):
        # The live shape on 2026-07-27: the row listed 8, the directory held 14.
        t = self.build(tmp_path, "alpha, beta", ["alpha", "beta", "gamma", "delta"])
        (warn,) = self.warns(t)
        assert "omits 2" in warn and "delta, gamma" in warn, "named, and in a stable order"

    def test_a_name_with_no_file_is_named_too(self, tmp_path):
        t = self.build(tmp_path, "alpha, ghost", ["alpha"])
        (warn,) = self.warns(t)
        assert "no file" in warn and "ghost" in warn

    def test_both_directions_are_reported_together(self, tmp_path):
        t = self.build(tmp_path, "ghost", ["alpha"])
        assert len(self.warns(t)) == 2, "one fix must not hide the other"

    def test_a_matching_row_is_quiet(self, tmp_path):
        t = self.build(tmp_path, "alpha, beta", ["beta", "alpha"])
        assert self.warns(t) == []

    def test_a_missing_row_is_not_silence(self, tmp_path):
        t = fresh(tmp_path)
        (t / ".dreamwork" / "docs" / "plans").mkdir(parents=True)
        (t / ".dreamwork" / "docs" / "doc-map.md").write_text("# Doc map\n\nno table\n")
        assert "unmapped" in self.warns(t)[0]

    def test_no_docs_dir_is_not_a_finding(self, tmp_path):
        # Most targets have no plans/ at all; the check must not nag them.
        t = fresh(tmp_path)
        (t / ".dreamwork").mkdir()
        assert self.warns(t) == []

    def test_this_repo_maps_its_own_plans(self):
        rep = lint.Report()
        lint.check_doc_map_plans(lint.SKILL_DIR / ".dreamwork", rep)
        assert not [d for l, w, d in rep.rows if l == lint.WARN], rep.render()


class TestStatusKeys:
    """`status.json` losing a key it used to carry (#303).

    The incident: a wholesale rewrite dropped `retired_today` and lint called
    the result clean, because a projection missing a key is indistinguishable
    from one that never had it.
    """

    def build(self, tmp_path: Path, **keys) -> Path:
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "status.json").write_text(json.dumps(keys or {"task": "t"}))
        return dw

    def rewrite(self, dw: Path, **keys) -> None:
        (dw / "status.json").write_text(json.dumps(keys))

    def run(self, dw: Path):
        rep = lint.Report()
        lint.check_status_keys(dw, rep)
        return rep

    def losses(self, dw: Path):
        return [d for l, w, d in self.run(dw).rows if l == lint.WARN and w == "status.json"]

    def memo(self, dw: Path) -> set:
        return {
            ln.strip()
            for ln in (dw / ".status-keys").read_text().splitlines()
            if ln.strip() and not ln.startswith("#")
        }

    def test_a_fresh_target_is_learned_not_flagged(self, tmp_path):
        # The cry-wolf failure #306 was measured against: a new target's
        # status.json is nearly empty by design and must not go red for it.
        dw = self.build(tmp_path, task="t", goal="g")
        assert self.losses(dw) == []
        assert self.memo(dw) == {"task", "goal"}

    def test_the_real_incident_goes_red(self, tmp_path):
        dw = self.build(tmp_path, task="t", goal="g", retired_today=["a", "b"])
        assert self.losses(dw) == []          # learn first
        self.rewrite(dw, task="t", goal="g")  # the wholesale rewrite
        (warn,) = self.losses(dw)
        assert "retired_today" in warn

    def test_it_keeps_warning_rather_than_absorbing_the_loss(self, tmp_path):
        """The design decision, and the one a plain implementation fails.

        Re-recording the current key set each run makes the FIRST run after a
        bad rewrite adopt the reduced set as its baseline: one warning, then
        silence. A check that goes quiet about a live loss is indistinguishable
        from one that found nothing, so the memo never shrinks by itself.
        """
        dw = self.build(tmp_path, task="t", retired_today=["a"])
        self.losses(dw)
        self.rewrite(dw, task="t")
        assert self.losses(dw), "the run that sees the loss must warn"
        assert self.losses(dw), "and so must the NEXT one — the memo must not absorb it"
        assert self.losses(dw), "and every one after that"
        assert "retired_today" in self.memo(dw)

    def test_a_human_edit_is_what_accepts_a_retirement(self, tmp_path):
        dw = self.build(tmp_path, task="t", retired_today=["a"])
        self.losses(dw)
        self.rewrite(dw, task="t")
        assert self.losses(dw)
        keys = self.memo(dw) - {"retired_today"}
        (dw / ".status-keys").write_text("".join(f"{k}\n" for k in sorted(keys)))
        assert self.losses(dw) == []

    def test_a_new_key_is_added_without_complaint(self, tmp_path):
        dw = self.build(tmp_path, task="t")
        self.losses(dw)
        self.rewrite(dw, task="t", brand_new="x")
        assert self.losses(dw) == []
        assert self.memo(dw) == {"task", "brand_new"}

    def test_every_lost_key_is_named_not_just_counted(self, tmp_path):
        # "lost 3 keys" sends the reader to diff a gitignored file against
        # nothing. The names are the whole value of the warning.
        dw = self.build(tmp_path, a=1, b=2, c=3, d=4)
        self.losses(dw)
        self.rewrite(dw, a=1)
        (warn,) = self.losses(dw)
        assert all(k in warn for k in ("b", "c", "d"))

    def test_absent_status_json_writes_no_memo(self, tmp_path):
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        assert self.run(dw).rows == []
        assert not (dw / ".status-keys").exists()

    def test_broken_status_json_does_not_teach_the_memo(self, tmp_path):
        # check_status already ERRORs on it; learning an empty key set from a
        # half-written file would erase the baseline this check exists to hold.
        dw = self.build(tmp_path, task="t", retired_today=["a"])
        self.losses(dw)
        before = self.memo(dw)
        (dw / "status.json").write_text("{not json")
        assert self.run(dw).rows == []
        assert self.memo(dw) == before

    def test_it_is_wired_into_run_checks(self, tmp_path):
        # A check absent from the one list is a check whose tests cannot fail.
        dw = self.build(tmp_path, task="t", retired_today=["a"])
        lint.run_checks(dw, lint.load_watch(), lint.Report())
        self.rewrite(dw, task="t")
        rep = lint.Report()
        lint.run_checks(dw, lint.load_watch(), rep)
        assert any("retired_today" in d for l, _, d in rep.rows if l == lint.WARN)


class TestLandedStillOpen:
    """#323: git says a task landed; the ledger still lists it under Open.

    Three real cases in one evening (#314, #156, #315) motivated this, and
    the third was found by this check's own measurement rather than by
    anyone noticing. `lint` already cross-checks the open COUNT, so it
    catches a miscount but never a task sitting in the wrong section —
    nothing compared the ledger against git.

    The discrimination is the whole design, and it is why a keyword search
    was rejected: #315's body contains the word "landed" describing the
    problem (`#301 fixed the LANDED half`), so any prose-matching rule
    flags it for the wrong reason and would flag deliberate partials too.
    The rule is instead **git names a close/merge commit that the entry
    does not** — and an entry that deliberately stays open after a landing
    already names its commit, because #269 and #275 both do so naturally.
    """

    LEDGER = """# Tasks

Next id: **9**

## Open

- **#1** — a task whose landing the entry does NOT acknowledge · P2 ·
  origin: **loop** · this is the stale case

- **#2** — a task deliberately still open after a partial landing · P2 ·
  origin: **loop** · the acute half landed `SHA2`, the module remains

- **#3** — a task with no close or merge commit at all · P2 ·
  origin: **loop** · still genuinely in progress

## Recently landed

- **#8** — something else · landed `deadbee`
"""

    def build(self, tmp_path):
        """A REAL git repo, because the check reads real `git log` output."""
        import subprocess
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()

        def git(*a):
            return subprocess.run(["git", "-C", str(t), *a],
                                  capture_output=True, text=True, check=True)

        git("init", "-q")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        (t / "f").write_text("1")
        git("add", "f")
        git("commit", "-qm", "close(#1): landed and the entry never said so")
        (t / "f").write_text("2")
        git("add", "f")
        git("commit", "-qm", "merge(#2): the acute half of a partial")
        sha2 = git("rev-parse", "--short", "HEAD").stdout.strip()
        (dw / "tasks.md").write_text(self.LEDGER.replace("SHA2", sha2))
        return t, sha2

    def warns(self, t):
        rep = lint.Report()
        lint.run_checks(t / ".dreamwork", lint.load_watch(), rep)
        return [d for lvl, w, d in rep.rows if lvl == lint.WARN and w == "tasks.md"]

    def flagged(self, t):
        """The ids this check actually flagged, not a substring search.

        A substring test is wrong here and cost one debugging pass: the
        warning's own advice names #269 and #275, so `"#2" in text` is true
        for a warning about #1. Read the id from the head of the message,
        which is the only place the SUBJECT appears.
        """
        import re as _re
        out = []
        for d in self.warns(t):
            m = _re.match(r"#(\d+) \(", d)
            if m:
                out.append(int(m.group(1)))
        return out

    def test_it_flags_the_unacknowledged_landing_only(self, tmp_path):
        t, sha2 = self.build(tmp_path)

        # --- PRECONDITIONS, so this cannot pass vacuously ---
        # The fixture's meaning depends on the three cases genuinely differing.
        # Derive each at runtime; a fixture edit that collapsed them would
        # otherwise make the assertions below true about nothing.
        import subprocess
        subs = subprocess.run(["git", "-C", str(t), "log", "--format=%s"],
                              capture_output=True, text=True).stdout
        assert "close(#1)" in subs, "case 1 needs a real close commit"
        assert "merge(#2)" in subs, "case 2 needs a real merge commit"
        assert "#3)" not in subs, "case 3 must have NO close/merge commit"
        ledger = (t / ".dreamwork" / "tasks.md").read_text()
        assert sha2 in ledger, "case 2 must NAME its commit — that is the discriminator"
        assert not any(s in ledger for s in ("close(#1)",)), "case 1 must not name its commit"

        got = self.flagged(t)
        assert got == [1], (
            "exactly the stale landing must be flagged: #2 is a deliberate "
            "partial that NAMES its commit (#269/#275's real shape) and #3 has "
            f"no close commit at all; flagged {got}")

    def test_it_is_a_warning_never_an_error(self, tmp_path):
        # A close commit is strong evidence, not proof: #275 has both a close
        # and a merge and is legitimately open because its ask awaits his
        # ruling, which is part of its definition of done (#306). So this is a
        # prompt to look, like the styleguide audit — an error would make the
        # ledger's honest states unrepresentable.
        t, _ = self.build(tmp_path)
        rep = lint.Report()
        lint.run_checks(t / ".dreamwork", lint.load_watch(), rep)
        assert not rep.failed, [r for r in rep.rows if r[0] == lint.ERROR]

    def test_a_target_that_is_not_a_git_repo_is_silent(self, tmp_path):
        # The loop runs on targets that may not be git repos at all, and
        # "cannot check" must not read as "nothing to fix".
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "tasks.md").write_text(self.LEDGER.replace("SHA2", "abc1234"))
        assert not any("landed" in w for w in self.warns(t))
