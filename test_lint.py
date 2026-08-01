"""Tests for lint.py.

The first test is the one that matters: the linter must go RED on the exact
file shape that failed silently in the field. A checker that has never been
red proves nothing, and this repo has now caught three checks that were
passing on their own bug.
"""

import contextlib
import json
import re
import subprocess
import sys
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


class TestSettingsRegistry:
    def test_real_registry_is_nonempty_known_and_valid(self):
        rep = lint.Report()
        lint.check_settings_registry(rep)
        assert levels(rep, "settings registry") == [lint.OK]
        assert len(lint.SETTINGS) > 0
        assert "gfx.dither" in lint.SETTINGS

    def test_empty_registry_fails_instead_of_passing_vacuously(self, monkeypatch):
        monkeypatch.setattr(lint, "SETTINGS", {})
        rep = lint.Report()
        lint.check_settings_registry(rep)
        assert levels(rep, "settings registry") == [lint.ERROR]
        assert "empty" in rep.rows[-1][2]

    def test_known_default_is_pinned_to_a_literal(self):
        assert lint.SETTINGS["gfx.dither"].default == "ign"


class TestExpectedProductionConstants:
    """#905 — expected values must not share production's authority."""

    def _check(self, tmp_path, test_source, *, production="TASK_EDGES = []\n"):
        (tmp_path / "lint.py").write_text("# marks this as the skill repo\n")
        (tmp_path / "subject.py").write_text(production)
        (tmp_path / "test_subject.py").write_text(test_source)
        rep = lint.Report()
        lint.check_expected_production_constants(tmp_path, rep)
        return [(level, detail) for level, what, detail in rep.rows
                if what == "test expectations"]

    def test_imported_constant_building_expected_value_is_a_warning(self, tmp_path):
        rows = self._check(
            tmp_path,
            "from subject import TASK_EDGES\n"
            "EXPECTED_EDGE_SET = frozenset((a, b) for a, b in TASK_EDGES)\n",
        )
        assert len(rows) == 1 and rows[0][0] == lint.WARN, rows
        assert "EXPECTED_EDGE_SET uses imported production constant TASK_EDGES" in rows[0][1]
        assert "among 1 test module(s)" in rows[0][1], rows[0][1]

    def test_an_import_alias_keeps_the_production_identity(self, tmp_path):
        rows = self._check(
            tmp_path,
            "from subject import TASK_EDGES as edges\n"
            "EXPECTED_EDGE_SET = set(edges)\n",
        )
        assert rows[0][0] == lint.WARN, rows
        assert "production constant TASK_EDGES" in rows[0][1]

    def test_an_intermediate_name_cannot_hide_the_shared_authority(self, tmp_path):
        rows = self._check(
            tmp_path,
            "from subject import TASK_EDGES\n"
            "copied_edges = TASK_EDGES\n"
            "EXPECTED_EDGE_SET = frozenset(copied_edges)\n",
        )
        assert rows[0][0] == lint.WARN, rows
        assert "production constant TASK_EDGES" in rows[0][1]

    def test_a_helper_returning_the_constant_cannot_hide_it(self, tmp_path):
        rows = self._check(
            tmp_path,
            "from subject import TASK_EDGES\n"
            "def subject_edges():\n"
            "    return TASK_EDGES\n"
            "EXPECTED_EDGE_SET = frozenset(subject_edges())\n",
        )
        assert rows[0][0] == lint.WARN, rows
        assert "production constant TASK_EDGES" in rows[0][1]

    def test_constant_reached_through_an_imported_module_is_a_warning(self, tmp_path):
        rows = self._check(
            tmp_path,
            "import subject as prod\n"
            "EXPECTED_EDGE_SET = frozenset(prod.TASK_EDGES)\n",
        )
        assert rows[0][0] == lint.WARN, rows
        assert "production constant TASK_EDGES" in rows[0][1]

    def test_mutating_an_expected_value_from_the_constant_is_a_warning(self, tmp_path):
        rows = self._check(
            tmp_path,
            "from subject import TASK_EDGES\n"
            "EXPECTED_EDGE_SET = set()\n"
            "EXPECTED_EDGE_SET.update(TASK_EDGES)\n",
        )
        assert rows[0][0] == lint.WARN, rows
        assert "production constant TASK_EDGES" in rows[0][1]

    def test_independently_built_helper_is_silent(self, tmp_path):
        rows = self._check(
            tmp_path,
            "import subject\n"
            "def frame(value):\n"
            "    return str(value).encode()\n"
            "EXPECTED_BYTES = frame('independent contract')\n"
            "def test_contract():\n"
            "    assert subject.canonical('x') == EXPECTED_BYTES\n",
            production="def canonical(value):\n    return value.encode()\n",
        )
        assert rows == [(lint.OK,
                         "examined 1 test module(s); no EXPECTED_* value uses "
                         "an imported production constant")]

    def test_literal_expected_value_is_not_banned(self, tmp_path):
        rows = self._check(
            tmp_path,
            "from subject import TASK_EDGES\n"
            "EXPECTED_EDGE_SET = frozenset({('M', 'B')})\n"
            "def test_edges():\n"
            "    assert set(TASK_EDGES) == EXPECTED_EDGE_SET\n",
        )
        assert rows[0][0] == lint.OK, rows

    def test_non_expected_name_is_outside_the_strict_convention(self, tmp_path):
        rows = self._check(
            tmp_path,
            "from subject import TASK_EDGES\n"
            "GOLDEN_EDGE_SET = frozenset(TASK_EDGES)\n",
        )
        assert rows[0][0] == lint.OK, rows

    def test_zero_test_modules_is_an_error_not_an_all_clear(self, tmp_path):
        (tmp_path / "lint.py").write_text("# marks this as the skill repo\n")
        rep = lint.Report()
        lint.check_expected_production_constants(tmp_path, rep)
        rows = [(level, detail) for level, what, detail in rep.rows
                if what == "test expectations"]
        assert len(rows) == 1 and rows[0][0] == lint.ERROR, rows
        assert "examined 0 test modules" in rows[0][1], rows[0][1]

    def test_this_repo_has_a_nonempty_judged_population(self):
        rep = lint.Report()
        lint.check_expected_production_constants(lint.SKILL_DIR, rep)
        rows = [(level, detail) for level, what, detail in rep.rows
                if what == "test expectations"]
        assert len(rows) == 1 and rows[0][0] in {lint.OK, lint.WARN}, rows
        population = re.search(r"(?:among|examined) (\d+) test module", rows[0][1])
        assert population and int(population.group(1)) > 0, rows[0][1]
        assert "test_chain_golden.py" not in rows[0][1], \
            "the independent framing helper is the compatibility control"


def _drain_state(dw: Path, allowed=("cx-846wtmove",), root=".worktrees",
                 *, root_present=True, size=123) -> Path:
    path = dw / lint.WORKTREE_DRAIN_STATE
    path.write_text(json.dumps({
        "version": 2,
        "root": root,
        "root_present": root_present,
        "high_water_count": len(allowed),
        "allowed_worktrees": list(allowed),
        "last_observed_size_bytes": size,
    }) + "\n")
    return path


class TestInRepoWorktreeDrain:
    def test_state_file_deletion_cannot_disable_an_existing_ratchet(
            self, tmp_path, monkeypatch):
        t = target(tmp_path)
        monkeypatch.setattr(lint, "_prior_drain_state",
                            lambda target, current: {"high_water_count": 0})
        rep = lint.Report()
        lint.check_in_repo_worktree_drain(t / ".dreamwork", rep)
        assert levels(rep, lint.WORKTREE_DRAIN_STATE) == [lint.ERROR]
        assert "deletion cannot disable the ratchet" in rep.rows[-1][2]

    def test_old_root_absent_passes_explicitly_at_bound_path(
            self, tmp_path, monkeypatch):
        t = target(tmp_path)
        monkeypatch.setattr(lint, "_main_checkout_for", lambda target: target)
        state = _drain_state(t / ".dreamwork", allowed=(),
                             root_present=False, size=0)
        before = state.read_bytes()
        rep = lint.Report()
        lint.check_in_repo_worktree_drain(t / ".dreamwork", rep)
        rows = [msg for level, what, msg in rep.rows
                if what == lint.WORKTREE_DRAIN_STATE]
        assert levels(rep, lint.WORKTREE_DRAIN_STATE) == [lint.OK]
        assert "in-repo worktree root absent at" in rows[0]
        assert rows[0].endswith("presence/count/size are locked at zero)")
        assert state.read_bytes() == before, "the check must never rebaseline itself"

    def test_absent_root_with_stale_allowance_refuses_until_locked_at_zero(
            self, tmp_path, monkeypatch):
        t = target(tmp_path)
        monkeypatch.setattr(lint, "_main_checkout_for", lambda target: target)
        _drain_state(t / ".dreamwork", root_present=False, size=0)
        rep = lint.Report()
        lint.check_in_repo_worktree_drain(t / ".dreamwork", rep)
        assert levels(rep, lint.WORKTREE_DRAIN_STATE) == [lint.ERROR]
        assert "invalid drain state" in rep.rows[-1][2]

    def test_root_cannot_reappear_after_ratchet_reaches_zero(
            self, tmp_path, monkeypatch):
        t = target(tmp_path)
        (t / ".worktrees").mkdir()
        monkeypatch.setattr(lint, "_main_checkout_for", lambda target: target)
        _drain_state(t / ".dreamwork", allowed=(),
                     root_present=False, size=0)
        rep = lint.Report()
        lint.check_in_repo_worktree_drain(t / ".dreamwork", rep)
        assert levels(rep, lint.WORKTREE_DRAIN_STATE) == [lint.ERROR]
        assert "reappeared after the checkpoint recorded it absent" in rep.rows[-1][2]

    def test_present_empty_root_is_distinct_and_locked_at_its_size(
            self, tmp_path, monkeypatch):
        t = target(tmp_path)
        old_root = t / ".worktrees"
        old_root.mkdir()
        monkeypatch.setattr(lint, "_main_checkout_for", lambda target: target)
        monkeypatch.setattr(lint, "_registered_in_repo_worktrees",
                            lambda main, old: [])
        size = lint._tree_size(old_root)
        _drain_state(t / ".dreamwork", allowed=(), size=size)
        rep = lint.Report()
        lint.check_in_repo_worktree_drain(t / ".dreamwork", rep)
        assert levels(rep, lint.WORKTREE_DRAIN_STATE) == [lint.OK]
        assert "root present: registered count 0/0" in rep.rows[-1][2]

    def test_committed_zero_cannot_be_rebaselined_to_original_name(
            self, tmp_path, monkeypatch):
        t = target(tmp_path)
        lane = t / ".worktrees" / "cx-846wtmove"
        lane.mkdir(parents=True)
        monkeypatch.setattr(lint, "_main_checkout_for", lambda target: target)
        monkeypatch.setattr(lint, "_prior_drain_state", lambda target, current: {
            "high_water_count": 0, "allowed_worktrees": []})
        _drain_state(t / ".dreamwork")
        rep = lint.Report()
        lint.check_in_repo_worktree_drain(t / ".dreamwork", rep)
        assert levels(rep, lint.WORKTREE_DRAIN_STATE) == [lint.ERROR]
        assert "from prior committed count 0 to 1" \
            in rep.rows[-1][2]
        assert str(t / ".worktrees" / "cx-846wtmove") in rep.rows[-1][2]

    def test_wrong_root_cannot_impersonate_absent_end_state(self, tmp_path):
        t = target(tmp_path)
        _drain_state(t / ".dreamwork", root=".worktreez")
        rep = lint.Report()
        lint.check_in_repo_worktree_drain(t / ".dreamwork", rep)
        assert levels(rep, lint.WORKTREE_DRAIN_STATE) == [lint.ERROR]
        assert "literal `.worktrees`" in rep.rows[-1][2]

    def test_new_registered_path_is_named_and_does_not_raise_baseline(
            self, tmp_path, monkeypatch):
        t = target(tmp_path)
        old_root = t / ".worktrees"
        (old_root / "cx-846wtmove").mkdir(parents=True)
        offender = old_root / "regression"
        offender.mkdir()
        monkeypatch.setattr(lint, "_main_checkout_for", lambda target: target)
        monkeypatch.setattr(lint, "_registered_in_repo_worktrees",
                            lambda main, old: [old / "cx-846wtmove", offender])
        state = _drain_state(t / ".dreamwork")
        before = state.read_bytes()
        rep = lint.Report()
        lint.check_in_repo_worktree_drain(t / ".dreamwork", rep)
        assert levels(rep, lint.WORKTREE_DRAIN_STATE) == [lint.ERROR]
        assert str(offender) in rep.rows[-1][2]
        assert "count 2" in rep.rows[-1][2]
        assert state.read_bytes() == before, "a red run must not bless its count"

    def test_unrecorded_worktree_is_read_from_the_real_git_registry(
            self, tmp_path, monkeypatch):
        root = tmp_path / "repo"
        root.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "master"], cwd=root,
                       check=True)
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c",
             "user.email=test@example.invalid", "commit", "--allow-empty",
             "-qm", "base"], cwd=root, check=True)
        offender = root / ".worktrees" / "regression"
        subprocess.run(
            ["git", "worktree", "add", "-q", "-b", "regression",
             str(offender)], cwd=root, check=True)
        (root / ".dreamwork").mkdir()
        _drain_state(root / ".dreamwork", allowed=(),
                     size=lint._tree_size(root / ".worktrees"))
        monkeypatch.setattr(lint, "_prior_drain_state",
                            lambda target, current: None)
        rep = lint.Report()
        lint.check_in_repo_worktree_drain(root / ".dreamwork", rep)
        assert levels(rep, lint.WORKTREE_DRAIN_STATE) == [lint.ERROR]
        assert str(offender) in rep.rows[-1][2]
        assert "count 1" in rep.rows[-1][2]

    def test_size_growth_trips_even_when_registered_count_is_unchanged(
            self, tmp_path, monkeypatch):
        t = target(tmp_path)
        lane = t / ".worktrees" / "cx-846wtmove"
        lane.mkdir(parents=True)
        (lane / "large-build-output").write_bytes(b"x" * 4096)
        monkeypatch.setattr(lint, "_main_checkout_for", lambda target: target)
        monkeypatch.setattr(lint, "_registered_in_repo_worktrees",
                            lambda main, old: [lane])
        _drain_state(t / ".dreamwork")
        rep = lint.Report()
        lint.check_in_repo_worktree_drain(t / ".dreamwork", rep)
        assert levels(rep, lint.WORKTREE_DRAIN_STATE) == [lint.ERROR]
        assert "size grew from recorded 123" in rep.rows[-1][2]
        assert "registered count stayed 1" in rep.rows[-1][2]

    def test_unregistered_stray_bytes_trip_while_count_stays_zero(
            self, tmp_path, monkeypatch):
        t = target(tmp_path)
        stray = t / ".worktrees" / "stray" / "cache"
        stray.mkdir(parents=True)
        stray.joinpath("blob").write_bytes(b"x" * 4096)
        monkeypatch.setattr(lint, "_main_checkout_for", lambda target: target)
        monkeypatch.setattr(lint, "_registered_in_repo_worktrees",
                            lambda main, old: [])
        _drain_state(t / ".dreamwork", allowed=(), size=123)
        rep = lint.Report()
        lint.check_in_repo_worktree_drain(t / ".dreamwork", rep)
        assert levels(rep, lint.WORKTREE_DRAIN_STATE) == [lint.ERROR]
        assert "registered count stayed 0" in rep.rows[-1][2]

    def test_size_shrink_requires_lowering_the_checkpoint(
            self, tmp_path, monkeypatch):
        t = target(tmp_path)
        lane = t / ".worktrees" / "cx-846wtmove"
        lane.mkdir(parents=True)
        monkeypatch.setattr(lint, "_main_checkout_for", lambda target: target)
        monkeypatch.setattr(lint, "_registered_in_repo_worktrees",
                            lambda main, old: [lane])
        size = lint._tree_size(t / ".worktrees")
        _drain_state(t / ".dreamwork", size=size + 1)
        rep = lint.Report()
        lint.check_in_repo_worktree_drain(t / ".dreamwork", rep)
        assert levels(rep, lint.WORKTREE_DRAIN_STATE) == [lint.ERROR]
        assert "size drain advanced" in rep.rows[-1][2]

    def test_absent_checkpoint_cannot_be_widened_back_to_present(
            self, tmp_path, monkeypatch):
        t = target(tmp_path)
        (t / ".worktrees").mkdir()
        monkeypatch.setattr(lint, "_main_checkout_for", lambda target: target)
        monkeypatch.setattr(lint, "_prior_drain_state", lambda target, current: {
            "root_present": False, "high_water_count": 0,
            "allowed_worktrees": [], "last_observed_size_bytes": 0})
        _drain_state(t / ".dreamwork", allowed=(), size=0)
        rep = lint.Report()
        lint.check_in_repo_worktree_drain(t / ".dreamwork", rep)
        assert levels(rep, lint.WORKTREE_DRAIN_STATE) == [lint.ERROR]
        assert "root presence increased from absent to present" in rep.rows[-1][2]


@pytest.fixture
def frozen_tree(tmp_path):
    """A detached worktree at HEAD — a fixed tree no concurrent lane can move.

    The dogfood test used to lint the LIVE working tree, and under 8 concurrent
    lanes it false-redred (#428): another lane committed `Lane-owns:` lines to
    44 briefs mid-run, so the tree the assertion was about changed underneath
    it. A snapshot at HEAD is immutable for the test's duration, so the
    assertion is about one SHA rather than about whatever the machine happens to
    be doing. ~94ms to create (measured); cleaned up in a `finally` so a crash
    cannot orphan a worktree the lane-containment backstop or reaper would
    later trip on. If git cannot make the snapshot, the failure surfaces rather
    than silently falling back to the live tree — that fallback would reintroduce
    the exact false red this exists to fix.
    """
    snap = tmp_path / "frozen-head"
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(snap), "HEAD"],
        check=True, capture_output=True,
    )
    try:
        yield snap
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(snap)],
            capture_output=True,
        )


def _materialize_store(dw, ledger_text, tmp_path):
    """Put the post-cutover store into ``dw`` via the REAL cutover path.

    A git snapshot (the frozen HEAD tree, or any `git archive`/zip install)
    carries no store — `ledger.sqlite3` is gitignored by design — so lint's
    store mode cannot engage and the markdown path falls back to the #458
    shim. `perform_cutover` is the blessed machinery that built the live
    store (#294); it is run in a history-less scratch dir because its git-
    history walk (for burndown first-sight events) is seconds-slow inside a
    real worktree, and a dogfood run needs only the task rows + watermark,
    not the series. Only the resulting `ledger.sqlite3` is copied into `dw`;
    no committed file is touched, and the store holds the same committed
    ledger data the live checkout's does.
    """
    import importlib.machinery, importlib.util, io, shutil
    import ledger_parse
    repo = Path(lint.__file__).resolve().parent
    loader = importlib.machinery.SourceFileLoader(
        "ud_dw_tasks_migrate_dogfood", str(repo / "ud-dw-tasks-migrate"))
    spec = importlib.util.spec_from_loader(
        "ud_dw_tasks_migrate_dogfood", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    scratch = tmp_path / "store-build"
    scratch.mkdir()
    (scratch / "tasks.md").write_text(ledger_text)
    mod.perform_cutover(str(scratch), out=io.StringIO())
    shutil.copy2(ledger_parse.store_path(scratch),
                 ledger_parse.store_path(dw))


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

    def test_this_repo_passes_its_own_linter(
            self, frozen_tree, tmp_path, monkeypatch):
        # Dogfood: the file the whole bug was about, checked by the tool
        # written because of it.
        #
        # The tree is a HEAD snapshot, not the live working tree (#428): under
        # 8 concurrent lanes another lane's commit moved the live tree mid-run
        # and the only failure in 1193 tests was this one. The snapshot is fixed
        # at one SHA, so the assertion is about a tree no lane can move.
        #
        # Post-cutover (#294) the snapshot's tasks.md is the one-line #458 shim
        # and the store is gitignored (absent by design), so lint's markdown
        # path reads the shim (no `Next id` header) and ERRORs — the dogfood
        # could never pass. The real committed ledger is tasks.md.deprecated
        # (populated, frozen at cutover); the non-vacuous precondition reads
        # it, and the store the live checkout carries is materialized from it
        # via the REAL cutover path so the dogfood runs in STORE mode — exactly
        # how lint runs on the live checkout. The snapshot stays fixed at one
        # SHA's committed content, so #428's no-live-race guarantee holds.
        #
        # Precondition, derived at runtime: the snapshot must actually carry the
        # files lint reasons about, or `not rep.failed` proves nothing — an empty
        # tree has nothing to fail on, which is the hollowness this repo keeps
        # paying for. A lost `.dreamwork` would pass vacuously.
        dw = frozen_tree / ".dreamwork"
        q = dw / "questions.md"
        led = dw / "tasks.md.deprecated"
        assert q.is_file() and q.read_text().strip(), \
            "snapshot carries no questions.md — the dogfood run would examine nothing"
        assert led.is_file() and led.read_text().strip(), \
            "snapshot carries no tasks.md.deprecated — the real committed ledger is gone"
        # And the ledger parses to a non-trivial entry count, so the run is
        # against a populated tree rather than a stub. `load_watch` is the same
        # parser loader lint itself uses.
        watch = lint.load_watch()
        assert watch is not None, "watch.py unimportable — cannot derive entry count"
        open_ids, _ = watch.parse_ledger(led.read_text())
        assert len(open_ids) > 0, \
            f"committed ledger parsed {len(open_ids)} open entries — run is vacuous"
        # Materialize the gitignored store (absent by design in any git
        # snapshot) from the committed ledger via the REAL cutover path, so
        # lint engages store mode over real projected data — not the shim.
        _materialize_store(dw, led.read_text(), tmp_path)
        # #592 made an ABSENT store in a linked worktree a WARN rather than an
        # ERROR, and `frozen_tree` IS a linked worktree — so a materialization
        # that quietly failed would now leave this dogfood passing on the
        # excuse instead of on real store-mode data. Pin the mode it must run
        # in, or `not rep.failed` stops meaning what the test says it means.
        assert lint.source_of_truth(dw) == "store", \
            "store did not materialize — the dogfood would pass on the #592 " \
            "worktree excuse rather than on the real ledger"
        # #846's ratchet deliberately reads the LIVE git worktree registry,
        # which cannot be frozen with this content snapshot. Dedicated tests
        # above bind that check in both directions; exclude the moving external
        # subject here so #428's fixed-tree dogfood remains a fixed-tree claim.
        monkeypatch.setattr(lint, "check_in_repo_worktree_drain",
                            lambda dw, rep: None)
        rep = run(frozen_tree)
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


class TestAnsweredResolutionDates:
    """#411: an answered entry that loses its `→ answered (…)` marker silently
    loses the date the collapsed row is found by. `check_questions` verifies the
    file PARSES and is silent on whether each entry carries a resolution date;
    this check is the coverage the ledger entry asks for — a count that cannot
    silently stop counting."""

    def build(self, tmp_path, answered_bodies):
        # `answered_bodies`: list of (title, body) for `## Answered` entries.
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        entries = "\n\n".join(
            f"- **{title}**\n{body}" for title, body in answered_bodies)
        (dw / "questions.md").write_text(
            "# Questions\n\n## Open\n\n## Answered\n\n" + entries + "\n")
        return t

    def rows(self, t):
        rep = lint.Report()
        lint.check_answered_resolution_dates(t / ".dreamwork", lint.load_watch(), rep)
        return [d for lvl, w, d in rep.rows if w == "questions.md"]

    def test_every_dated_entry_is_clean(self, tmp_path):
        t = self.build(tmp_path, [
            ("First?", "  → resolved (2026-07-25): done.\n"),
            ("Second?", "The review is at\n  → answered (2026-07-26 17:49): ok.\n"),
        ])
        # PRECONDITION, derived not pinned: both must parse as dated, or the
        # "clean" assertion is vacuous — a check that never saw an entry cannot
        # fail on one.
        import watch
        items = watch.parse_answered((t / ".dreamwork/questions.md").read_text())
        dated = sum(1 for it in items if watch.answered_at(it["body"]))
        assert dated == 2, dated
        # Silent when every answered entry carries a date: this check is a
        # companion to check_questions (which owns the OK row), and it speaks
        # only when something is wrong. The coverage it provides is the WARN,
        # not a duplicate OK.
        assert self.rows(t) == []

    def test_an_undated_entry_warns_and_is_named(self, tmp_path):
        t = self.build(tmp_path, [
            ("Dated?", "  → resolved (2026-07-25): done.\n"),
            ("Undated?", "  A body with no marker at all.\n"),
        ])
        rows = self.rows(t)
        assert rows and "1 of 2 answered entries have no recorded human response" in rows[0]
        # the offending entry is named, so a withdrawn ask is distinguishable
        # from a dropped marker by reading the line
        assert "Undated" in rows[0]

    def test_a_second_line_marker_recovers_and_is_not_counted_as_undated(self, tmp_path):
        # #411's actual live shape: artifact pointer, then the head on line 2.
        t = self.build(tmp_path, [
            ("LAN?", "The review is at\n  → answered (2026-07-26 17:49): ok.\n"),
            ("Withdrawn?", "  decided by the loop, and withdrawn as an ask.\n"),
        ])
        # PRECONDITION: the second-line marker really does recover under the fix
        # (this is the property the check's coverage depends on — without it,
        # the WARN count would include a recovered entry and cry wolf).
        import watch
        items = watch.parse_answered((t / ".dreamwork/questions.md").read_text())
        by = {it["title"]: watch.answered_at(it["body"]) for it in items}
        assert by["LAN?"] == "2026-07-26 17:49"
        assert by["Withdrawn?"] is None
        rows = self.rows(t)
        assert rows and "1 of 2 answered entries have no recorded human response" in rows[0]
        assert "Withdrawn" in rows[0]

    def test_the_count_is_derived_from_the_fixture_not_pinned(self, tmp_path):
        # The two fixtures above must genuinely differ in their undated count
        # (1 vs 0), or every assertion here could pass over a check that
        # counts nothing. Derive both at runtime and assert the gap.
        dated = self.build(tmp_path, [
            ("One?", "  → resolved (2026-07-25): done.\n")])
        undated = self.build(tmp_path, [
            ("One?", "  no marker here.\n")])
        import watch
        n_dated = sum(1 for it in watch.parse_answered(
            (dated / ".dreamwork/questions.md").read_text())
            if watch.answered_at(it["body"]) is None)
        n_undated = sum(1 for it in watch.parse_answered(
            (undated / ".dreamwork/questions.md").read_text())
            if watch.answered_at(it["body"]) is None)
        assert n_undated - n_dated == 1, (n_dated, n_undated)

    def test_dated_watch_answer_and_comment_are_recorded_resolutions(self, tmp_path):
        t = self.build(tmp_path, [
            ("Answered?", "  - **Answer (via watch, 2026-07-31 19:16):** rec\n"),
            ("Commented?", "  - **Comment (via watch, 2026-07-31 19:12) — ruling:**\n"),
        ])
        import watch
        items = watch.parse_answered((t / ".dreamwork/questions.md").read_text())
        assert len(items) == 2
        assert any(it["follows"] for it in items)
        assert any("Comment (via watch" in it["body"] for it in items)
        assert self.rows(t) == []

    def test_folded_alone_is_reported_not_accepted_as_a_resolution(self, tmp_path):
        t = self.build(tmp_path, [
            ("Processed without his answer?",
             "  - **Folded (2026-07-31 19:18) — coordinator processed this.**\n"),
        ])
        rows = self.rows(t)
        assert len(rows) == 1
        assert "carry `Folded` but no recorded human response" in rows[0]
        assert "Processed without his answer" in rows[0]
        assert "[`Folded`]" in rows[0]

    def test_future_resolution_format_is_reported_as_unclassifiable(self, tmp_path):
        t = self.build(tmp_path, [
            ("Resolved in a format not invented yet?",
             "  - **Verdict (via dreambeam, 2027-01-02 03:04):** rec\n"),
        ])
        rows = self.rows(t)
        assert len(rows) == 1
        assert "dated but unclassifiable resolution record" in rows[0]
        assert "Resolved in a format not invented yet" in rows[0]
        assert "[`Verdict`]" in rows[0]


class TestQuestionsTruncationGuard:
    """#533: a questions.md that is net-shorter than its last commit by more
    than the threshold is a tail-truncation — the coordinator wrote the file
    from a partial read and the tail fell off. watch.py is innocent (collect
    reads, append preserves every line), so the gate is this working-tree-vs-
    HEAD comparison."""

    # A faithful miniature of the #229 entry: a long answered entry whose body
    # carries a NESTED ASCII TABLE (the feature the incident's 16:35 grok-review
    # note shares), plus another answered entry below it — exactly the shape
    # whose tail was lost at 07:44.
    def _full(self):
        rows = "\n".join(
            f"    │ row {i:<3} │ because {i:<6} │" for i in range(70))
        return (
            "# Questions for the human\n\n## Open\n\n"
            "- **P2 · 2026-07-30 — #505: an open question.**\n"
            "  Body prose.\n\n"
            "## Answered\n\n"
            "- **P1 · 2026-07-26 — #229 threaded topic chats: approve the proposal.**\n"
            "  → answered (2026-07-26 17:11): Revision directed.\n"
            "  The reviewed artifact is current.\n"
            "  - **Note (human, via watch, 2026-07-26 16:12):** a note.\n"
            "  - **Note (human, via watch, 2026-07-26 16:35):** re 229, a grok\n"
            "    review with a nested table:\n"
            "    ┌──────────┬──────────────┐\n"
            "    │ Check    │ Why          │\n"
            "    ├──────────┼──────────────┤\n"
            f"{rows}\n"
            "    └──────────┴──────────────┘\n"
            "  - **Follow-up (loop, 2026-07-26 16:48):** a follow-up.\n"
            "  - **Answer (via watch, 2026-07-26 17:10):** the answer.\n\n"
            "- **P1 · 2026-07-25 — #202: another answered entry below.**\n"
            "  → answered (2026-07-26): resolved.\n"
            "  Body of the entry below.\n"
        )

    def _build_repo(self, tmp_path, qmd_text, msg="seed full questions.md"):
        import subprocess
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "questions.md").write_text(qmd_text)

        def git(*a):
            return subprocess.run(["git", "-C", str(t), *a],
                                  capture_output=True, text=True, check=True)
        git("init", "-q")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        git("add", ".dreamwork/questions.md")
        git("commit", "-qm", msg)
        return t, dw

    def _truncation_errors(self, t):
        rep = lint.Report()
        lint.run_checks(t / ".dreamwork", lint.load_watch(), rep)
        return [d for lvl, w, d in rep.rows
                if lvl == lint.ERROR and w == "questions.md" and "truncation" in d]

    def test_a_tail_truncation_is_an_error(self, tmp_path):
        """The 07:44 incident: a full questions.md committed, then the working
        tree rewritten from a partial read so the #229 nested-table tail and
        everything below it is gone. The guard must ERROR."""
        full = self._full()
        t, dw = self._build_repo(tmp_path, full)
        # Truncate at the nested-table rows — mimicking the mid-content cut
        # ("route too." -> "route ") that ended the incident file mid-entry.
        cut = full.index("    │ row 1")
        truncated = full[:cut].rstrip() + "\n"
        (dw / "questions.md").write_text(truncated)
        # Precondition DERIVED AT RUNTIME (not a literal): the loss must clear
        # the threshold, or the assertion says nothing about the bug it names.
        lost = len(full.splitlines()) - len(truncated.splitlines())
        assert lost > lint.QUESTIONS_TRUNCATION_THRESHOLD, lost
        errs = self._truncation_errors(t)
        assert len(errs) == 1, errs
        assert f"lost {lost} lines" in errs[0], errs[0]

    def test_a_line_neutral_fold_is_not_flagged(self, tmp_path):
        """A real fold cuts an entry from Open and pastes it (with a ruling
        summary) into Answered — net-neutral or net-positive — and must not
        trip a guard built for net loss. This is the false-positive the
        threshold was set to avoid."""
        full = self._full()
        t, dw = self._build_repo(tmp_path, full)
        moved = ("- **P2 · 2026-07-30 — #505: an open question.**\n"
                 "  → answered (2026-07-30): folded with a ruling summary.\n"
                 "  Body prose.\n\n")
        folded = full.replace(
            "## Open\n\n"
            "- **P2 · 2026-07-30 — #505: an open question.**\n"
            "  Body prose.\n\n",
            "## Open\n\n", 1
        ).replace("## Answered\n\n", "## Answered\n\n" + moved, 1)
        (dw / "questions.md").write_text(folded)
        assert self._truncation_errors(t) == []

    def test_the_groom_marker_allows_a_deliberate_archive(self, tmp_path):
        """The one legitimate net loss is a deliberate bulk-archive, signalled
        by `groom:` in the commit touching questions.md. The guard honours it
        on the next working-tree pass."""
        import subprocess
        full = self._full()
        t, dw = self._build_repo(tmp_path, full)
        # A prior questions.md commit carries the marker; lint reads it back.
        (dw / "questions.md").write_text(full + "\n")
        subprocess.run(["git", "-C", str(t), "add", ".dreamwork/questions.md"],
                       check=True)
        subprocess.run(["git", "-C", str(t), "commit", "-qm",
                         "groom: archive old answered entries"], check=True)
        cut = full.index("    │ row 1")
        (dw / "questions.md").write_text(full[:cut].rstrip() + "\n")
        assert self._truncation_errors(t) == []

    def test_the_pure_guard_threshold_binds(self):
        """The production line is `lost > threshold and not groom` in
        `questions_truncation_guard`. A loss just over the threshold fires;
        one just under does not; the groom flag suppresses even a large loss.
        All derived at runtime from the live threshold, so a drifted constant
        cannot hollow the test."""
        th = lint.QUESTIONS_TRUNCATION_THRESHOLD
        over = "\n".join("x" for _ in range(th + 5))
        under = "\n".join("x" for _ in range(max(1, th - 5)))
        assert lint.questions_truncation_guard(over, "")[0] == lint.ERROR
        assert lint.questions_truncation_guard(under, "")[0] == lint.OK
        big = "\n".join("x" for _ in range(th + 500))
        assert lint.questions_truncation_guard(big, "", groom=True)[0] == lint.OK

    def test_no_git_baseline_is_silent(self, tmp_path):
        """A target with no .git (a fixture dir, a non-repo project) cannot be
        compared against HEAD and must not fault — 'cannot check' is never an
        error, here or anywhere else this linter meets git."""
        t = target(tmp_path, **{"questions.md": self._full()})
        assert self._truncation_errors(t) == []


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
        # All tasks.md rows are OK — no ERRORs, no WARNs. #685 made
        # check_related_markers report `examined N entries against 0 markers`
        # for a no-marker ledger (it used to be silent), so the row count is
        # no longer exactly one; the sound property is "every level is OK".
        assert all(lvl == lint.OK for lvl in levels(rep, "tasks.md")), rep.rows
        assert levels(rep, "tasks.md"), "a sound ledger must report something"


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

    # #702: `lanes` is author-owned prose the coordinator writes at dispatch
    # (sees every form); `dreamers` is the derived half status_sync prunes by
    # liveness. Nothing connected them, and nothing complained while `lanes`
    # named a real fleet and `dreamers` was empty — the tick read `0 ccc-live`
    # beside live lanes for a whole evening. A non-empty `lanes` beside an
    # empty `dreamers` is either a missed bookkeeping step or a stale `lanes`;
    # both are worth a human's eye.
    def test_lanes_populated_but_dreamers_empty_is_warned(self, tmp_path):
        blob = json.dumps({
            "lanes": [{"lane": "lane-x", "task": "#7"}],
            "dreamers": [],
        })
        rep = run(target(tmp_path, **{"status.json": blob}))
        assert lint.WARN in levels(rep, "status.json"), rep.rows
        detail = next(d for _, w, d in rep.rows if w == "status.json")
        # The WARN names both halves of the disagreement (the backticked keys
        # do not survive a bare substring, so check the load-bearing words).
        assert "lanes" in detail and "empty" in detail, detail

    def test_lanes_and_dreamers_both_populated_is_ok(self, tmp_path):
        # The real file's steady state (this repo, at dispatch): both halves
        # carry the fleet. The check must not fire here.
        blob = json.dumps({
            "lanes": [{"lane": "lane-x", "task": "#7"}],
            "dreamers": [{"task": 7, "pid": 1234, "brief": "/x.md"}],
        })
        rep = run(target(tmp_path, **{"status.json": blob}))
        assert levels(rep, "status.json") == [lint.OK], rep.rows

    def test_both_empty_is_ok(self, tmp_path):
        # The fleet's empty-fleet steady state between dispatches: no dispatch
        # recorded, nothing to disagree. The check must not nag an empty fleet.
        blob = json.dumps({"lanes": [], "dreamers": []})
        rep = run(target(tmp_path, **{"status.json": blob}))
        assert levels(rep, "status.json") == [lint.OK], rep.rows

    def test_lanes_or_dreamers_wrong_type_is_an_error(self, tmp_path):
        # The type guard added in the same change: `lanes`/`dreamers` must be
        # lists (a string where a list belongs makes a reader throw).
        blob = json.dumps({"lanes": "lane-x", "dreamers": {}})
        rep = run(target(tmp_path, **{"status.json": blob}))
        assert ERRORS(rep, "status.json")
        detail = next(d for _, w, d in rep.rows if w == "status.json")
        assert "lanes is str" in detail and "dreamers is dict" in detail, detail


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
    def test_detached_interpreter_refuses_and_names_its_root(self, tmp_path):
        detached = tmp_path / "detached"
        detached.mkdir()
        script = detached / "lint.py"
        script.write_bytes(Path(lint.__file__).read_bytes())
        assert not (detached / "SKILL.md").exists()

        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=Path(lint.__file__).resolve().parent,
            text=True,
            capture_output=True,
        )

        expected = (
            f"lint: refusing detached corpus root {detached.resolve()} — "
            "expected SKILL.md beside lint.py"
        )
        assert expected in proc.stderr
        assert proc.returncode == 2

    def test_empty_target_with_real_interpreter_is_not_detached(self, tmp_path, capsys):
        anchor = Path(lint.__file__).resolve().with_name("SKILL.md")
        assert anchor.is_file()

        assert lint.main(["--target", str(target(tmp_path))]) == 0
        assert "refusing detached corpus root" not in capsys.readouterr().err

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

    def test_short_needs_got_beside_it(self, tmp_path):
        # #371: `short` says a body arrived incomplete and `got` says by how
        # much. The flag alone tells a reader recovering his words that
        # something is missing without telling them what they have, so the
        # contract pairs them and this refuses either half on its own.
        assert self.run_s(tmp_path, self.rec(short=True) + "\n").failed
        assert self.run_s(tmp_path, self.rec(got=11) + "\n").failed
        assert not self.run_s(tmp_path,
                              self.rec(short=True, got=11) + "\n").failed

    def test_short_false_is_an_error_and_got_must_be_an_int(self, tmp_path):
        # Same contract as `truncated`: absent, never false.
        assert self.run_s(tmp_path, self.rec(short=False, got=11) + "\n").failed
        assert self.run_s(tmp_path, self.rec(short=True, got="11") + "\n").failed

    def test_short_and_truncated_can_both_be_absent(self, tmp_path):
        # They are opposite conditions, so the ordinary record carries neither
        # — and a check that demanded one of them would fail every good line.
        assert not self.run_s(tmp_path, self.rec() + "\n").failed

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
        + LANDED + "\n\n- **#5** — landed `abc1234`\n"
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
        lint.check_ledger_sections(Path("."), self.HAZARD, "markdown", rep)
        assert ERRORS(rep, "tasks.md"), "a moved section split must go red"
        detail = next(d for _, w, d in rep.rows if w == "tasks.md")
        assert "1" in detail and "2" in detail, \
            "must report BOTH counts, so the reader can see which one is wrong"
        assert "#304" in detail, "must name the task that explains the failure"

    def test_the_anchored_split_agrees(self):
        rep = lint.Report()
        lint.check_ledger_sections(Path("."), self.HAZARD, "markdown", rep)
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
                + self.LANDED + "\n\n- **#5** — landed `abc1234`\n")
        assert COMBINED_HEAD in text, "fixture must hold a combined head"
        # Runtime precondition is a property of the FIXTURE, not the pattern
        # under test, so derive both ids straight from the head string: a
        # literal pair is true only of today's fixture, and a future edit
        # that collapsed them to one would pass vacuously.
        head_ids = watch.ENTRY_ID.findall(COMBINED_HEAD)
        assert len(head_ids) == 2 and head_ids[0] != head_ids[1], \
            "fixture head must carry two distinct ids to be the combined case"
        rep = lint.Report()
        lint.check_ledger_sections(Path("."), text, "markdown", rep)
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
              "- **#5** — shipped · landed `abc1234`\n"
              "- **#6** — shipped · landed `def5678`\n")

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

    def test_tasks_row_routes_readers_to_the_live_store(self):
        doc_map = (lint.SKILL_DIR / ".dreamwork" / "docs" / "doc-map.md").read_text()
        rows = [line for line in doc_map.splitlines()
                if line.startswith("| `.dreamwork/tasks.md` |")]
        assert len(rows) == 1, "doc-map must contain exactly one tasks.md routing row"
        row = rows[0]
        assert "Five-line migration shim" in row
        assert "`.dreamwork/ledger.sqlite3` store" in row, (
            "tasks.md row must route live-queue readers to the SQLite store"
        )

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

    def test_a_plan_named_only_in_the_lifecycle_column_is_still_missing(self, tmp_path):
        # #699: the enumeration a reader consults lives in the description column
        # (col 2); a plan named only in the lifecycle column (col 3) cannot be
        # *found*, so it must be reported missing. Unioning the whole row let a
        # col-3 parenthetical pass for an enumeration entry — a false match.
        t = fresh(tmp_path)
        docs = t / ".dreamwork" / "docs"
        (docs / "plans").mkdir(parents=True)
        for name in ("alpha", "gamma"):
            (docs / "plans" / f"{name}.md").write_text("# a plan\n")
        # col 2 enumerates only alpha; col 3 names the bare slug `gamma`.
        row = "| `.dreamwork/docs/plans/` | Active feature plans (alpha) | Prune (gamma) |\n"
        (docs / "doc-map.md").write_text(
            "# Doc map\n\n| Doc | Covers | Cur |\n|---|---|---|\n" + row)
        cols = row.split("|")  # ['', path, desc, lifecycle, '']
        assert "gamma" not in cols[2], "precondition: gamma absent from enumeration"
        assert "gamma" in cols[3], "precondition: gamma named only in lifecycle"
        (warn,) = self.warns(t)
        assert "omits" in warn and "gamma" in warn, warn

    def test_a_row_without_the_column_shape_fails_closed(self, tmp_path):
        # #699: a row the check cannot split into `path | desc | lifecycle` must
        # not guess a match — it fails closed, because an unparseable row is the
        # case where reporting OK would be the dangerous answer.
        t = fresh(tmp_path)
        docs = t / ".dreamwork" / "docs"
        (docs / "plans").mkdir(parents=True)
        (docs / "plans" / "alpha.md").write_text("# a plan\n")
        # No second `|`: no description column can be isolated.
        (docs / "doc-map.md").write_text(
            "# Doc map\n\n| Doc | Covers | Cur |\n|---|---|---|\n"
            "| `.dreamwork/docs/plans/` | Active feature plans (alpha)\n")
        assert any("shape" in w for w in self.warns(t)), self.warns(t)

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

    def test_the_warning_carries_when_it_landed_not_only_the_sha(self, tmp_path):
        """#363: this check fired correctly three times and a coordinator
        overrode it FROM MEMORY — "that is another session's live lane" — three
        times across four hours, and was right only the first time. #334's work
        had merged at 01:39 and the override went on for an hour after that.

        Softening the message was tried and explicitly WITHDRAWN in the entry: a
        softened WARN is one nobody re-checks. The replacement rec asks the
        reader to "check git, which takes one command" — so the check runs that
        command itself and prints the answer. Overriding from memory then has to
        be done against a printed timestamp and an age, which is a much harder
        thing to do by accident.

        The production line is the `%cI`/`%cr` fields in the `git log --format`
        and the clause built from them. Drop them and this fails while every
        other row in this class still passes.
        """
        import subprocess
        t, sha2 = self.build(tmp_path)
        # Derived from git rather than written here, so the assertion cannot
        # drift from what the tool will actually report.
        when = subprocess.run(
            ["git", "-C", str(t), "log", "-1", "--format=%cI",
             "--grep", "close(#1)"],
            capture_output=True, text=True, check=True).stdout.strip()
        assert when, "precondition: the close(#1) commit must be findable by git"
        stamp = when[:16].replace("T", " ")
        mine = [d for d in self.warns(t) if d.startswith("#1 (")]
        assert len(mine) == 1, mine
        assert stamp in mine[0], (stamp, mine[0])
        assert re.search(r"\d+ (second|minute|hour|day|week|month|year)s? ago",
                         mine[0]), mine[0]
        # And the sha is still there: the age is added evidence, not a swap.
        assert "`" in mine[0]

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


class TestStatusTaskIds:
    """#332: the loop's claim about WHICH tasks it is on, machine-readably.

    `#281`'s "in progress" badge has to decide whether a given row is the one
    the loop claims, and the prose in `task` cannot answer that — one sentence
    routinely names several ids in different states ("folding #281's answer,
    #326 next"). So the claim gets structured ids beside the prose.

    The failure this guards is narrow and likely: a writer that puts
    `"#281"` or `"281"` where `281` belongs. Nothing would look wrong — the
    field is present, it is a list, it reads correctly to a human — and the
    badge would simply never match any row, silently, which is the exact
    class `lint` calls an ERROR.
    """

    def build(self, tmp_path, **status):
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "status.json").write_text(json.dumps(status))
        return t

    def rows(self, t, level):
        rep = lint.Report()
        lint.run_checks(t / ".dreamwork", lint.load_watch(), rep)
        return [d for lvl, w, d in rep.rows if lvl == level and w == "status.json"]

    def test_integers_are_accepted(self, tmp_path):
        t = self.build(tmp_path, task="on #281", current_task_ids=[281, 326])
        assert not self.rows(t, lint.ERROR)

    def test_a_stringly_typed_id_is_an_error(self, tmp_path):
        # The whole point: this LOOKS right and reads right to a human.
        t = self.build(tmp_path, task="on #281", current_task_ids=["#281"])
        errs = " ".join(self.rows(t, lint.ERROR))
        assert "current_task_ids" in errs, errs
        assert "#281" in errs, f"the offending value must be named: {errs}"

    def test_a_bare_numeric_string_is_also_an_error(self, tmp_path):
        # `"281"` is the subtler half — it survives a careless int() and fails
        # every `in` test against a list of ints.
        t = self.build(tmp_path, task="t", current_task_ids=["281"])
        assert self.rows(t, lint.ERROR)

    def test_per_agent_task_ids_are_checked_too(self, tmp_path):
        t = self.build(tmp_path, task="t",
                       agents=[{"name": "a", "task_ids": [326]},
                               {"name": "b", "task_ids": ["#327"]}])
        errs = " ".join(self.rows(t, lint.ERROR))
        assert "task_ids" in errs and "b" in errs, (
            f"the offending AGENT must be named, not just the field: {errs}")

    def test_absent_is_silent(self, tmp_path):
        # Optional field: a loop that has not adopted it yet is not broken, and
        # every other row of this contract degrades the same way.
        t = self.build(tmp_path, task="t")
        assert not [d for d in self.rows(t, lint.ERROR) + self.rows(t, lint.WARN)
                    if "task_ids" in d]

    def test_bools_do_not_sneak_through_as_ints(self, tmp_path):
        # `isinstance(True, int)` is True in Python, so a naive check passes a
        # bool. It is worth one line because the sibling field in_flight was
        # ALREADY written as a bool by mistake in this very file (#327 found it
        # rendering as `doing: true`), so a bool arriving here is not a
        # hypothetical.
        t = self.build(tmp_path, task="t", current_task_ids=[True])
        assert self.rows(t, lint.ERROR)

    def test_a_string_sub_id_is_accepted_not_rejected(self, tmp_path):
        """#402b — a sub-id like ``"392a"`` is a LEGITIMATE task id.

        The contract the code already implies (status_sync keeps the string
        form by design, #402a): a plain id is an int, a sub-id is a string,
        and only a *quoted plain* id is wrong. Today lint rejects every
        string, which rejects a legitimate sub-id — the live symptom.

        Precondition (asserted, not trusted): the field carries an int AND a
        str at once, so the test's meaning needs both types present. The
        sub-id must look like a real sub-id (digits then one letter), the way
        a lane's task actually reads.
        """
        ids = [263, "392a"]
        assert {type(i) for i in ids} == {int, str}, \
            "precondition: an int and a str coexist — both types present"
        assert any(isinstance(i, str) and re.match(r"^\d+[a-z]$", i) for i in ids), \
            "precondition: at least one string sub-id of the N+letter shape"
        t = self.build(tmp_path, task="on #263 and #392a",
                       current_task_ids=ids)
        assert not self.rows(t, lint.ERROR), \
            "a legitimate sub-id must lint clean (the #402b fix)"

    def test_a_quoted_plain_id_is_still_an_error(self, tmp_path):
        """#402b NEGATIVE — widening must not remove the check that earned it.

        The widening accepts sub-id strings (``"392a"``); it must STILL reject
        a *quoted plain* id (``"263"``), which is the silent-data-loss shape
        this check exists for: it looks right, reads right to a human, and
        matches no task row. A widening with no negative test has removed a
        check rather than improved it.
        """
        t = self.build(tmp_path, task="t", current_task_ids=["263"])
        errs = self.rows(t, lint.ERROR)
        assert errs, "a quoted plain id must remain an ERROR after the widening"
        assert "263" in errs[0]


class TestReviewArtifacts:
    """#329 — lint WARNs when a built review artifact's frame is stale.

    `review_artifact.py check` already answered current/stale/untemplated, but
    nothing ran it; an artifact silently kept an old frame after the template
    improved. These tests wire that answer into the per-target lint pass.

    Every classification case is driven through the REAL builder (`ra.render`
    against the real template) and the REAL subprocess (`review_artifact.py
    check` is spawned by `run_checks`). Faking check's output would test the
    fake: the stale/current distinction is exactly what is under test, so it
    must come from the real tool reading real bytes off disk.
    """

    # A minimal but valid source — every required slot present, parsed by the
    # real `parse_source`, so `ra.render` produces a genuinely current artifact.
    SOURCE = """<!--dreamwork-review-source
title: #329 · lint catches a stale frame · test
identity: test artifact
headline: One line.
status: test
lead: the lead
footer: the footer
no_ask: test fixture — no decision to make
no_if_silent: test fixture — no decision to park
-->
<!--#body-->
<section><p>the body</p></section>
"""

    def _doc(self):
        import review_artifact as ra
        return ra.render(ra.parse_source(self.SOURCE))

    def _stale_doc(self):
        # A real build with the current stamp swapped for a bogus one — exactly
        # how `test_cli_check_reports_and_exits_nonzero_on_stale` makes a stale
        # artifact in test_review_artifact.py. The assert is the precondition
        # the swap depends on: if the build stopped carrying the stamp, the
        # replace would change nothing and "stale" would prove nothing.
        import review_artifact as ra
        doc = self._doc()
        stamp = ra.template_stamp(ra.read_template())
        assert stamp in doc, "fixture precondition: the build carries the stamp"
        return doc.replace(stamp, "v1+00000000")

    def _target(self, tmp_path, **artifacts):
        """A target whose .dreamwork/review/ holds the named built artifacts."""
        t = fresh(tmp_path)
        review = t / ".dreamwork" / "review"
        review.mkdir(parents=True)
        for name, content in artifacts.items():
            (review / name).write_text(content)
        return t

    def _run(self, t):
        rep = lint.Report()
        lint.run_checks(t / ".dreamwork", lint.load_watch(), rep)
        return rep

    def _warns(self, t):
        return [d for lvl, w, d in self._run(t).rows
                if lvl == lint.WARN and w == "review/"]

    def _errors(self, t):
        return [d for lvl, w, d in self._run(t).rows
                if lvl == lint.ERROR and w == "review/"]

    def test_a_stale_artifact_warns(self, tmp_path):
        t = self._target(tmp_path, **{"stale.html": self._stale_doc()})
        rows = self._warns(t)
        assert rows, "a stale frame must be reported"
        assert "stale.html" in rows[0], "must name the file"
        assert "stale" in rows[0], "must say why"
        assert "rebuild" in rows[0].lower(), "must name the fix"

    def test_a_current_artifact_does_not_warn(self, tmp_path):
        t = self._target(tmp_path, **{"current.html": self._doc()})
        assert self._warns(t) == [], "a current frame is not a finding"
        rep = self._run(t)
        assert any(lvl == lint.OK and w == "review/" for lvl, w, _ in rep.rows), \
            "and it confirms it checked, so absence of a row is not silence by crash"

    def test_an_untemplated_artifact_is_silent(self, tmp_path):
        # The twelve pre-existing artifacts predate the template; warning on
        # each every run is noise everyone learns to ignore. `untemplated` is a
        # third answer and lint honours it by saying nothing about it.
        t = self._target(
            tmp_path, **{"old.html": "<html><body>pre-template</body></html>"})
        assert self._warns(t) == []
        assert not self._run(t).failed

    def test_a_malformed_built_artifact_errors_with_the_mismatched_tags(
            self, tmp_path):
        t = self._target(
            tmp_path,
            **{"broken.html": "<html><body><div class=\"call\">x</p></body></html>"})
        errors = self._errors(t)
        assert any(
            "broken.html" in row
            and "closing </p>" in row
            and "cannot close open <div>" in row
            for row in errors), errors

    def test_an_empty_artifact_errors_instead_of_passing_zero_elements(
            self, tmp_path):
        t = self._target(tmp_path, **{"empty.html": ""})
        errors = self._errors(t)
        assert any("examined 0 elements" in row for row in errors), errors
        assert any("no trustworthy denominator" in row for row in errors), errors

    def test_stale_and_untemplated_warn_only_the_stale(self, tmp_path):
        # Discrimination: untemplated must not dilute the stale signal, and a
        # mixed directory must still surface the one that matters.
        t = self._target(
            tmp_path,
            **{"stale.html": self._stale_doc(),
               "old.html": "<html><body>pre-template</body></html>"})
        rows = self._warns(t)
        assert len(rows) == 1, "exactly the stale one — untemplated stays silent"
        assert "stale.html" in rows[0]

    def test_no_review_dir_is_silent(self, tmp_path):
        # Most targets have no review artifacts at all; a row on each would be
        # the noise that hides the one that matters.
        t = fresh(tmp_path)
        (t / ".dreamwork").mkdir()
        assert [r for r in self._run(t).rows if r[1] == "review/"] == []

    def test_an_empty_review_dir_is_silent(self, tmp_path):
        t = fresh(tmp_path)
        (t / ".dreamwork" / "review").mkdir(parents=True)
        assert [r for r in self._run(t).rows if r[1] == "review/"] == []

    def test_a_file_under_src_is_not_checked(self, tmp_path):
        # watch.py's `list_reviews` is non-recursive, so anything under `src/`
        # is invisible to the dashboard. Lint must match — or a stale file
        # dropped in src/ would warn as if it were served. A STALE artifact is
        # planted there on purpose: an untemplated one would stay silent either
        # way, so only the stale case discriminates recursive from not.
        t = fresh(tmp_path)
        review = t / ".dreamwork" / "review"
        (review / "src").mkdir(parents=True)
        (review / "src" / "stale.html").write_text(self._stale_doc())
        assert self._warns(t) == [], "src/ is not where artifacts are served from"

    def test_review_artifact_missing_degrades_silently(self, tmp_path, monkeypatch):
        # If review_artifact.py is gone or python is missing, "cannot check"
        # must not crash the lint pass and must not read as "nothing to fix" —
        # it simply says nothing, the way a non-repo target stays quiet under
        # check_landed_still_open.
        import subprocess
        t = self._target(tmp_path, **{"current.html": self._doc()})

        def boom(*args, **kwargs):
            raise FileNotFoundError("script gone")
        monkeypatch.setattr(subprocess, "run", boom)
        rep = self._run(t)
        assert [r for r in rep.rows if r[1] == "review/"] == []
        assert not rep.failed

    def test_this_repo_introduces_no_stale_artifacts(self):
        # Dogfood: the skill's own .dreamwork/review/ holds the twelve
        # pre-existing artifacts, all untemplated. They must stay silent — and
        # any artifact built from the template must stay current, or this very
        # repo's lint pass would warn on itself every run.
        rep = lint.Report()
        lint.check_review_artifacts(lint.SKILL_DIR / ".dreamwork", rep)
        assert not [d for l, w, d in rep.rows if l == lint.WARN], rep.render()
        assert not rep.failed, rep.render()


class TestSelfCompletedOpen:
    """#335: an entry under `## Open` that declares ITSELF completed in its
    metadata run — the ` · `-delimited chain after the title where `P1`,
    `origin:` and `owner:` live.

    #261 sat open for a full day carrying `completed **2026-07-26 16:21**`
    in that run. #323 could not see it: that check compares the ledger
    against git, and #261 was closed in prose with no `close(#261)` commit.
    The same words (`completed`, `landed`, `merged`) deep in the prose body
    are NOT a self-declared close — four real open entries carry them for
    legitimate reasons, and the discriminator is POSITION, not vocabulary.
    A vocabulary-only grep over the open entries has precision 1-in-5.
    """

    def _real_ledger(self):
        # Post-cutover (#294) `.dreamwork/tasks.md` is the one-line #458 shim
        # — no `## Open`, no parseable entries — so every runtime precondition
        # below would fail vacuously against it. These markdown-path checks
        # describe the FROZEN ledger, which post-cutover lives in
        # tasks.md.deprecated (the same repoint as 135c2e31 / 7068342d). That
        # file is committed and frozen at cutover, so the open/landed
        # membership and body markers the preconditions derive from it cannot
        # drift under the test the way the live store can.
        return (lint.SKILL_DIR / ".dreamwork" / "tasks.md.deprecated").read_text()

    def _entry_text(self, ledger_text, tid):
        for ids, body in lint.ledger_entries(ledger_text):
            if tid in ids:
                return body
        return None

    def _slice_open(self, ledger_text):
        lines = ledger_text.splitlines()
        start = end = None
        for n, ln in enumerate(lines):
            if ln.strip().startswith("## "):
                if ln.strip() == "## Open":
                    start = n + 1
                elif start is not None:
                    end = n
                    break
        if start is None:
            return ""
        return "\n".join(lines[start:end])

    def _self_completed_warns(self, rep):
        return [d for lvl, w, d in rep.rows
                if lvl == lint.WARN and w == "tasks.md" and "#335" in d]

    def test_261_restored_to_open_fires_warn(self, tmp_path):
        """The bug: #261's exact text, placed under ## Open, must WARN.

        #261 is in `## Recently landed` now (its own note says it was moved),
        so the positive case is built by restoring its real entry text into
        an Open section. A fixture that merely resembles it is not evidence.
        """
        real = self._real_ledger()
        body_261 = self._entry_text(real, 261)

        # PRECONDITION: #261 exists and carries the marker this test is about.
        # If the entry moved or was edited, the test must fail loudly rather
        # than quietly pass on a fixture that no longer means anything.
        assert body_261 is not None, "#261 not found in the real ledger"
        assert "completed" in body_261, \
            "#261 must carry its completion marker for this test to mean anything"
        assert "2026-07-26" in body_261, \
            "#261 must carry its completion date for this test to mean anything"

        fixture = ("# Tasks\n\nNext id: **999**\n\n## Open\n\n"
                   + body_261 + "\n\n## Recently landed\n")
        t = target(tmp_path, **{"tasks.md": fixture})
        rep = run(t)
        warns = self._self_completed_warns(rep)
        assert any("#261" in d for d in warns), (
            "#261 declares itself completed in its metadata run; the check "
            f"must WARN. Got: {warns}")

    def test_the_four_false_positives_stay_silent(self, tmp_path):
        """#275, #283, #269, #281 are legitimately open despite carrying
        `landed`/`completed`/`merged` deep in their PROSE BODY.

        Their metadata runs carry no such marker — that is the position
        discrimination, and it is the whole value of the task. Each one's
        real text is read from the live ledger at test time; a fixture
        that merely resembles them is not evidence.
        """
        real = self._real_ledger()
        open_text = self._slice_open(real)

        # PRECONDITION: all four are actually in ## Open right now. If any
        # moved to Recently landed, "stays silent" would pass on nothing.
        open_ids = set()
        for ids, _ in lint.ledger_entries(open_text):
            open_ids.update(ids)
        for tid in (275, 283, 269, 281):
            assert tid in open_ids, (
                f"#{tid} must be in ## Open for this test to mean anything")

        # PRECONDITION: each one's body actually carries the keyword that
        # would trip a vocabulary rule. If the text was edited to remove it,
        # "stays silent" would prove nothing about the discrimination.
        for ids, body in lint.ledger_entries(open_text):
            flat = " ".join(ln.strip() for ln in body.split("\n"))
            if 275 in ids:
                assert "landed" in flat.lower() and "4b49ecb" in flat, \
                    "#275 must carry its body-level landing marker"
            if 283 in ids:
                assert "completed" in flat.lower() and "2026-07-27" in flat, \
                    "#283 must carry its body-level completion marker"
            if 269 in ids:
                assert "landed" in flat.lower() and "0366706" in flat, \
                    "#269 must carry its body-level landing marker"
            if 281 in ids:
                assert "merged" in flat.lower() and "9c00cd2" in flat, \
                    "#281 must carry its body-level merge marker"

        t = target(tmp_path, **{"tasks.md": real})
        rep = run(t)
        warns = self._self_completed_warns(rep)
        for tid in (275, 283, 269, 281):
            assert not any(f"#{tid}" in d for d in warns), (
                f"#{tid} is a false positive — its keyword is in the body, "
                f"not the metadata run; got: {warns}")

    def test_breaking_position_fires_the_false_positives(self, tmp_path, monkeypatch):
        """DISCRIMINATION PROOF: break the position discriminator so the
        check searches the whole entry, and the four false positives fire.

        This is what position discrimination prevents, and it is the whole
        value of the task: the same vocabulary without the position check
        has precision 1-in-5. The production line that would have to change
        for a real bug to pass this silently is `_metadata_clause`'s body-
        break condition (the `;` / length test that stops the token scan);
        this test breaks exactly that function.
        """
        real = self._real_ledger()
        open_text = self._slice_open(real)

        open_ids = set()
        for ids, _ in lint.ledger_entries(open_text):
            open_ids.update(ids)
        for tid in (275, 283, 269, 281):
            assert tid in open_ids, f"#{tid} must be open for this proof"

        # Break: make _metadata_clause return the WHOLE flattened entry,
        # removing the position discrimination entirely.
        monkeypatch.setattr(lint, "_metadata_clause",
                            lambda entry_text:
                            " ".join(ln.strip() for ln in entry_text.split("\n")))

        fixture = ("# Tasks\n\nNext id: **999**\n\n## Open\n\n"
                   + open_text + "\n\n## Recently landed\n")
        t = target(tmp_path, **{"tasks.md": fixture})
        rep = run(t)
        warns = self._self_completed_warns(rep)

        flagged = set()
        for d in warns:
            for m in re.finditer(r"#(\d+)", d):
                flagged.add(int(m.group(1)))
        for tid in (275, 283, 269, 281):
            assert tid in flagged, (
                f"breaking position discrimination must fire on #{tid}; "
                f"the same vocabulary without position has precision 1-in-5. "
                f"Flagged: {flagged}")

    def test_no_open_section_is_silent(self, tmp_path):
        t = target(tmp_path, **{
            "tasks.md": "# Tasks\n\nNext id: **1**\n\n## Recently landed\n"})
        rep = run(t)
        assert self._self_completed_warns(rep) == []

    def test_empty_open_is_silent(self, tmp_path):
        t = target(tmp_path, **{
            "tasks.md": "# Tasks\n\nNext id: **1**\n\n## Open\n\n## Recently landed\n"})
        rep = run(t)
        assert self._self_completed_warns(rep) == []


class TestAuthorTags:
    """#343: a bullet whose author tag the renderer does not know is not a
    contribution — it falls into the entry BODY with its raw tag showing and no
    author label, which is the #340 defect reachable by a one-word typo.

    The evidence for this check is a live near-miss, not a hypothetical: the
    coordinator wrote `Note (loop, …)` on the P0 question gating five lanes an
    hour after writing a merge message explaining that `Answer (loop, …)` was
    the #254 bug for exactly this reason.
    """

    HEAD = "# Questions\n\n## Open\n\n"
    ENTRY = "- **P1 · 2026-07-27 — a question that needs an answer?** Body text.\n"

    def _tag_warns(self, rep):
        return [d for lvl, _w, d in rep.rows
                if lvl in (lint.WARN, lint.ERROR) and "author tag" in d]

    def _q(self, tag_line):
        return self.HEAD + self.ENTRY + f"  {tag_line}\n\n## Answered\n"

    def test_the_loops_real_tag_is_accepted(self, tmp_path):
        t = target(tmp_path, **{"questions.md": self._q(
            "- **Follow-up (loop, 2026-07-27 23:36):** the loop replying.")})
        assert self._tag_warns(run(t)) == []

    def test_his_real_tag_is_accepted(self, tmp_path):
        t = target(tmp_path, **{"questions.md": self._q(
            "- **Note (human, via watch, 2026-07-27 23:24):** his words.")})
        assert self._tag_warns(run(t)) == []

    def test_his_answer_tag_is_accepted(self, tmp_path):
        t = target(tmp_path, **{"questions.md": self._q(
            "- **Answer (via watch, 2026-07-27 23:38):** rec")})
        assert self._tag_warns(run(t)) == []

    def test_the_typo_that_actually_happened_is_caught(self, tmp_path):
        """`Note (loop, …)` — reasonable-looking, and in neither tag set."""
        t = target(tmp_path, **{"questions.md": self._q(
            "- **Note (loop, 2026-07-27 23:36):** the loop replying.")})
        warns = self._tag_warns(run(t))
        assert len(warns) == 1, warns
        assert "Note (loop," in warns[0]

    def test_a_loop_answer_tag_is_caught(self, tmp_path):
        """`Answer (loop, …)` is the #254 bug's own spelling."""
        t = target(tmp_path, **{"questions.md": self._q(
            "- **Answer (loop, 2026-07-27 23:38):** the loop resolving.")})
        assert len(self._tag_warns(run(t))) == 1

    def test_answers_md_is_checked_too(self, tmp_path):
        t = target(tmp_path, **{"answers.md":
            "# Answers\n\n## Open\n\n- **Q · 2026-07-27 — a question?** Body.\n"
            "  - **Note (loop, 2026-07-27 23:36):** wrong tag here too.\n\n"
            "## Answered\n"})
        assert len(self._tag_warns(run(t))) == 1

    def test_an_undated_bolded_bullet_is_not_an_author_tag(self, tmp_path):
        """The discriminator is a DATE inside the parenthesis, so ordinary
        prose bullets like `- **Option A (cheapest):**` must stay silent —
        otherwise the check fires on entry bodies constantly and gets ignored.
        """
        t = target(tmp_path, **{"questions.md": self._q(
            "- **Option A (cheapest):** do the simple thing.")})
        assert self._tag_warns(run(t)) == []

    def test_the_recognised_prefixes_come_from_watch_not_a_copy(self, tmp_path):
        """The check must consume watch.py's own tuples. A second copy of the
        tag list is a second thing able to disagree with the renderer, which is
        the entire defect class. So: every prefix watch.py recognises must be
        accepted here, derived at runtime — if watch.py gains a tag and lint
        keeps a stale copy, this fails.
        """
        w = lint.load_watch()
        if w is None:
            pytest.skip("watch.py unimportable")
        tags = [p for p, _ in list(w.NOTE_TAGS) + list(w.ANSWER_TAGS)]
        assert len(tags) >= 5, tags
        for n, prefix in enumerate(tags):
            line = f"{prefix} 2026-07-27 23:36):** body." if prefix.endswith(",") \
                   else f"{prefix}, 2026-07-27 23:36):** body."
            sub = tmp_path / f"case{n}"
            sub.mkdir()
            t = target(sub, **{"questions.md": self._q(line)})
            assert self._tag_warns(run(t)) == [], f"{prefix} was rejected: {line}"

    def test_prose_that_parenthesises_a_date_is_not_an_author_tag(self, tmp_path):
        """Found by running the check on the REAL questions.md, which is the only
        place it could have been found: a summary bullet reading
        `- **Four early asks, all applied (2026-07-25)** — …` has a date inside a
        parenthesis and is not a tag. A real tag is a SINGLE word followed by the
        parenthesis and then a colon; this has four words before the paren and no
        colon after it. Precision matters more than reach for a WARN — one false
        positive per run and the reader stops believing the other three.
        """
        t = target(tmp_path, **{"questions.md": self._q(
            "- **Four early asks, all applied (2026-07-25)** — the review folded.")})
        assert self._tag_warns(run(t)) == []

    def test_missing_files_are_silent(self, tmp_path):
        t = target(tmp_path, **{"tasks.md": "# Tasks\n\nNext id: **1**\n"})
        assert self._tag_warns(run(t)) == []


class TestLessonLineCitations:
    """#764 — numeric coordinates are checked only on the live text surface."""

    def _target(self, tmp_path, lessons, briefs=None, reports=None):
        root = fresh(tmp_path)
        dw = root / ".dreamwork"
        dw.mkdir()
        (dw / "lessons.md").write_text(lessons)
        for name, text in (briefs or {}).items():
            path = root / "briefs" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        for name, text in (reports or {}).items():
            (dw / name).write_text(text)
        return root

    def _rows(self, root):
        rep = lint.Report()
        lint.check_lesson_line_citations(root / ".dreamwork", rep)
        return [(lvl, detail) for lvl, what, detail in rep.rows
                if what == "lesson citations"]

    def test_drift_into_prose_warns_with_the_actual_line(self, tmp_path):
        root = self._target(
            tmp_path,
            "- **First lesson** body\ncontinuation carrying the wrong subject\n",
            briefs={"live.md": "See `lessons.md:2`.\n"},
        )
        rows = self._rows(root)
        assert len(rows) == 1 and rows[0][0] == lint.WARN, rows
        assert "briefs/live.md:1" in rows[0][1]
        assert "continuation carrying the wrong subject" in rows[0][1]

    def test_out_of_range_warns_loudly(self, tmp_path):
        root = self._target(
            tmp_path,
            "- **Only lesson** body\n",
            briefs={"live.md": "See `lessons.md:99`.\n"},
        )
        rows = self._rows(root)
        assert rows[0][0] == lint.WARN and "<out of range>" in rows[0][1], rows

    def test_historical_lane_reports_are_grandfathered(self, tmp_path):
        root = self._target(
            tmp_path,
            "- **Only lesson** body\n",
            reports={"lane-old-report.md": "Stale `lessons.md:99`.\n"},
        )
        assert self._rows(root) == []

    def test_a_wrong_but_valid_lesson_head_is_beyond_the_check(self, tmp_path):
        """The original disease: syntax cannot establish semantic intent."""
        root = self._target(
            tmp_path,
            "- **Wrong subject** body\n- **Intended subject** body\n",
            briefs={"live.md": "Intends the second but cites `lessons.md:1`.\n"},
        )
        assert self._rows(root) == [
            (lint.OK, "1 numeric citation(s) resolve to lesson heads")
        ]


class TestPlaceholderCitations:
    """#381's cheap half: a landing citation that is an unfilled slot.

    The incident is from tonight. #362's entry read `**LANDED `<pending>`**` and
    sat under `## Open` for hours; it was found by accident while selecting an
    unrelated task. No check saw it, because `check_cited_shas` only reads hex
    and a placeholder is not hex, so it was invisible to the one check whose
    subject is exactly "does this citation point at a commit".

    **WHY IT IS A WARN AND NOT AN ERROR, which the measurement forced.** A
    placeholder is an unavoidable intermediate state: the commit that lands the
    work cannot cite its own sha, so `landed `PENDING`` is what the ledger
    honestly says for exactly one commit. Erroring would block the very commit
    that does the work. The WARN's job is to make the FOLLOW-UP happen, which is
    otherwise carried entirely by the writer remembering.

    **THE DISCRIMINATION, measured on the live ledger before the rule was
    written.** The obvious rule — a landing keyword introducing a backticked
    token that is not a sha — was tried first and is wrong: it flags four things
    on the real file and none of them is a placeholder (`questions.md`,
    `dev/capture/report.mjs`, `dither: "lsb-ign-v1"`, and a run of prose). So
    precision was 0-in-4. The rule is instead a CLOSED vocabulary of slot-shaped
    tokens, which flags all nine real shapes and none of the four.
    """

    LEDGER = """# Tasks

Next id: **9**

## Open

- **#1** — a task · P2 · origin: **loop** · still going

## Recently landed

- **#2** — landed but the sha was never filled in · landed `<pending>` · origin: **loop**
"""

    def rows(self, tmp_path, ledger, level=None):
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "tasks.md").write_text(ledger)
        rep = lint.Report()
        lint.run_checks(dw, lint.load_watch(), rep)
        return [d for lvl, w, d in rep.rows
                if w == "tasks.md" and "placeholder" in d
                and (level is None or lvl == level)]

    def test_a_placeholder_citation_warns(self, tmp_path):
        warns = self.rows(tmp_path, self.LEDGER, lint.WARN)
        assert len(warns) == 1, warns
        assert "<pending>" in warns[0]
        assert "#2" in warns[0]

    @pytest.mark.parametrize("token", [
        "<pending>", "PENDING", "pending", "TBD", "TODO", "<sha>", "xxxxxxx",
        "???", "---",
    ])
    def test_every_slot_shape_is_caught(self, tmp_path, token):
        """Nine shapes an unfilled slot actually takes. One vocabulary, so a
        writer who reaches for a different placeholder is still caught."""
        warns = self.rows(tmp_path,
                          self.LEDGER.replace("<pending>", token), lint.WARN)
        assert len(warns) == 1, (token, warns)

    @pytest.mark.parametrize("token", [
        "questions.md", "dev/capture/report.mjs", 'dither: "lsb-ign-v1"',
        " is load-bearing — ",
    ])
    def test_the_four_live_false_positives_are_not_flagged(self, tmp_path, token):
        """These are the exact tokens the REFUTED rule flagged on the real
        ledger. They are the reason "not a sha" is not the test, and they are
        pinned here so nobody re-widens the rule to catch them."""
        assert self.rows(tmp_path, self.LEDGER.replace("<pending>", token)) == []

    def test_a_real_sha_is_not_a_placeholder(self, tmp_path):
        """Precondition for the whole check: the ordinary case stays quiet.

        `deadbee` is hex and 7 long, so it reaches `check_cited_shas` instead —
        and that check is separately silent here because the fixture is not a git
        repository, which is asserted rather than assumed.
        """
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "tasks.md").write_text(self.LEDGER.replace("<pending>", "deadbee"))
        assert not (t / ".git").exists()
        rep = lint.Report()
        lint.run_checks(dw, lint.load_watch(), rep)
        assert [d for _, w, d in rep.rows
                if w == "tasks.md" and "placeholder" in d] == []

    def test_the_live_ledger_has_no_placeholder_citations(self):
        """Held to the real file, which is the only claim that matters. This is
        also the row that would have caught #362 hours earlier."""
        dw = Path(lint.__file__).parent / ".dreamwork"
        rep = lint.Report()
        lint.check_placeholder_citations(dw, rep)
        assert rep.rows == [], rep.render()

    def test_it_catches_362_in_the_actual_revision_that_hid_it(self, tmp_path):
        """The real case, not a fixture: `tasks.md` as it stood at `4ce04e0`.

        A fixture proves the pattern matches; this proves the check would have
        caught the incident that motivated it, in the bytes that hid it. The
        precondition is asserted first — if that revision no longer carries the
        placeholder, the test must fail loudly rather than pass over an absent
        injection.
        """
        import subprocess
        got = subprocess.run(
            ["git", "-C", str(Path(lint.__file__).parent),
             "show", "4ce04e0:.dreamwork/tasks.md"],
            capture_output=True, text=True)
        if got.returncode != 0:
            pytest.skip("history not present (zip install); fixtures still cover it")
        assert "**LANDED `<pending>`**" in got.stdout, \
            "the historical placeholder is gone — this test no longer proves anything"
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "tasks.md").write_text(got.stdout)
        rep = lint.Report()
        lint.check_placeholder_citations(dw, rep)
        assert len(rep.rows) == 1, rep.render()
        level, _, detail = rep.rows[0]
        assert level == lint.WARN
        assert detail.startswith("#362 "), detail

    def test_the_check_is_registered_in_run_checks(self):
        import inspect
        assert "check_placeholder_citations(dw, rep)" in \
            inspect.getsource(lint.run_checks)


class TestCitationRange:
    """#777 — a line citation in a living doc must name a line that exists.

    The client extraction (#397) moved ~9,300 lines out of watch.py and 335
    `watch.py:N` citations across 48 docs now point past EOF. This check
    catches past-EOF citations in LIVING docs only; HISTORICAL append-only
    records stay silent because their citations were correct when written
    and "fixing" them falsifies a record (#755). The check is general — any
    tracked file can shrink — and resolves every `<file>:<line>` token, not
    only watch.py.
    """

    def _run(self, root):
        rep = lint.Report()
        lint.check_citation_range(root / ".dreamwork", rep)
        return [(lvl, detail) for lvl, what, detail in rep.rows
                if what == "citation range"]

    def _target(self, tmp_path, *, files):
        """A root with .dreamwork/ and arbitrary sibling files (no git)."""
        root = fresh(tmp_path)
        dw = root / ".dreamwork"
        dw.mkdir()
        for rel, text in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        return root

    def test_a_past_eof_citation_in_a_living_doc_warns_with_counts(self, tmp_path):
        """The headline case: a citation past EOF names the file, the cited
        line, and the actual line count — the three facts a fix needs."""
        root = self._target(tmp_path, files={
            "watch.py": "a\nb\nc\n",  # 3 lines
            ".dreamwork/docs/plans/living.md": "See `watch.py:99`.\n",
        })
        rows = self._run(root)
        assert len(rows) == 1 and rows[0][0] == lint.WARN, rows
        msg = rows[0][1]
        assert "watch.py:99" in msg, msg
        assert "watch.py's 3 line" in msg, msg
        assert "#777" in msg, msg

    def test_an_in_range_citation_is_silent(self, tmp_path):
        """A healthy living doc whose citations resolve produces an OK row, not
        silence — the row says 'in range', never 'verified' (#651)."""
        root = self._target(tmp_path, files={
            "watch.py": "a\nb\nc\n",
            ".dreamwork/docs/plans/living.md": "See `watch.py:2`.\n",
        })
        rows = self._run(root)
        assert len(rows) == 1 and rows[0][0] == lint.OK, rows
        assert "in range" in rows[0][1], rows[0][1]
        assert "verified" not in rows[0][1].lower(), rows[0][1]
        assert "undetectable" in rows[0][1], rows[0][1]

    def test_a_citation_to_an_untracked_file_is_silent_not_guessed(self, tmp_path):
        """A token naming no tracked file is skipped, not guessed at (#707).
        Without this, the check would attribute a citation to the wrong file."""
        root = self._target(tmp_path, files={
            ".dreamwork/docs/plans/living.md": "See `nonexistent.py:99`.\n",
        })
        assert self._run(root) == []

    def test_an_ambiguous_basename_is_left_unresolved(self, tmp_path):
        """Two files share a basename; the citation must not be attributed to
        either, because a wrong attribution is worse than no check (#707)."""
        root = self._target(tmp_path, files={
            "a/mod.py": "x\n",
            "b/mod.py": "x\n",
            ".dreamwork/docs/plans/living.md": "See `mod.py:99`.\n",
        })
        assert self._run(root) == []

    def test_historical_handoffs_stays_silent_on_many_dangling(self, tmp_path):
        """Direction 2, the deciding one: 35 dangling citations in handoffs.md
        must produce zero output. A check that flags an append-only record has
        made the repo worse (#755)."""
        root = self._target(tmp_path, files={
            "watch.py": "a\n",
            ".dreamwork/handoffs.md":
                "".join(f"see watch.py:{n}\n" for n in range(100, 135)),
        })
        assert self._run(root) == [], "handoffs.md is historical and must stay silent"

    def test_historical_findings_directory_stays_silent(self, tmp_path):
        root = self._target(tmp_path, files={
            "watch.py": "a\n",
            ".dreamwork/docs/findings/500-audit.md": "see `watch.py:99`\n",
        })
        assert self._run(root) == []

    def test_historical_briefs_and_lane_reports_stay_silent(self, tmp_path):
        root = self._target(tmp_path, files={
            "watch.py": "a\n",
            ".dreamwork/docs/briefs/500-brief.md": "see `watch.py:99`\n",
            ".dreamwork/lane-500-report.md": "see `watch.py:99`\n",
        })
        assert self._run(root) == []

    def test_the_check_catches_any_shrunk_file_not_just_watch_py(self, tmp_path):
        """The bug is 'a citation outlived the file', and any tracked file can
        shrink. ledger_store.py shrank during the sqlite migration too."""
        root = self._target(tmp_path, files={
            "ledger_store.py": "x\n",  # 1 line
            ".dreamwork/docs/plans/living.md": "see `ledger_store.py:500`\n",
        })
        rows = self._run(root)
        assert len(rows) == 1, rows
        assert "ledger_store.py:500" in rows[0][1], rows[0][1]
        assert "ledger_store.py's 1 line" in rows[0][1], rows[0][1]

    def test_one_warn_per_source_file_not_per_citation(self, tmp_path):
        """Granular enough that a regression in a clean file raises the count,
        bounded enough not to bury the rest of the report."""
        root = self._target(tmp_path, files={
            "watch.py": "a\n",
            ".dreamwork/docs/plans/one.md": "see `watch.py:10` and `watch.py:20`\n",
            ".dreamwork/docs/plans/two.md": "see `watch.py:30`\n",
        })
        rows = [r for r in self._run(root) if r[0] == lint.WARN]
        assert len(rows) == 2, rows

    def test_the_live_repo_historical_docs_produce_zero_rows(self):
        """Held to the real repo: every allowlisted historical path must stay
        silent. This is the bar that decides whether the check ships."""
        rep = lint.Report()
        lint.check_citation_range(lint.SKILL_DIR / ".dreamwork", rep)
        hist = lint.HISTORICAL_DOC_PATHS
        hpre = lint.HISTORICAL_DOC_PREFIXES
        flagged = [d for lvl, w, d in rep.rows if w == "citation range"
                   and (d.split(":")[0] in hist
                        or any(d.split(":")[0].startswith(p) for p in hpre))]
        assert flagged == [], f"check flagged historical docs: {flagged}"

    def test_the_check_is_registered_in_run_checks(self):
        import inspect
        assert "check_citation_range(dw, rep)" in \
            inspect.getsource(lint.run_checks)


class TestHandoffs:
    """#381's delivery half: a landing the ledger writer has not folded yet.

    The same night's other incident-class. #334 merged at `ecc1f44` and sat
    open for an hour while a coordinator overrode lint's WARN from memory
    three times; #362 carried ``LANDED `<pending>` `` under `## Open` until it
    was found BY ACCIDENT while selecting an unrelated task. In both, a foreign
    session landed work and the ledger's single writer never heard — the
    report died in the landing session. `.dreamwork/handoffs.md` is the
    channel; this check makes an unfolded one visible to whoever runs lint.

    **WHY WARN AND NOT ERROR**, for the same measured reason as the placeholder
    check: a freshly-landed hand-off is *supposed* to sit pending for the one
    tick before the coordinator folds it. Erroring would cry wolf on correct
    behaviour and the coordinator would learn to mute it — and a muted check is
    worse than none. The WARN is the nudge that makes the fold happen.

    **THE CONSUMED MARKER IS THE ONE LINE THIS CHECK CARES ABOUT.** A folded
    hand-off is silent, always — even if its task is still open. That is the
    load-bearing choice: a check that nags after you have complied gets muted,
    and the fold record is the coordinator's "I have seen this". The
    discriminating red makes the marker ignored and watches a folded hand-off
    get flagged forever; the test for it deliberately uses an OPEN task, because
    a landed one would mask an ignored marker (the delivery signal requires
    open) and the bug would read as green.
    """

    # Ids stay below 216 so the origin rule (a separate check, not exercised
    # here because we call check_handoffs directly) does not govern them.
    LEDGER = ("# Tasks\n\nNext id: **7**\n\n## Open\n\n"
              "- **#5** — a task still open\n\n"
              "## Recently landed\n\n"
              "- **#6** — done\n")

    def _run(self, tmp_path, ledger, handoffs):
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "tasks.md").write_text(ledger)
        (dw / "handoffs.md").write_text(handoffs)
        rep = lint.Report()
        lint.check_handoffs(dw, lint.load_watch(), rep)
        return rep

    def _warns(self, tmp_path, ledger, handoffs):
        rep = self._run(tmp_path, ledger, handoffs)
        return [d for lvl, w, d in rep.rows if w == "handoffs.md" and lvl == lint.WARN]

    def _errors(self, tmp_path, ledger, handoffs):
        rep = self._run(tmp_path, ledger, handoffs)
        return [d for lvl, w, d in rep.rows if w == "handoffs.md" and lvl == lint.ERROR]

    def test_a_handoff_naming_a_landed_task_that_is_still_open_is_flagged(self, tmp_path):
        # THE precondition the check depends on, derived at runtime not a literal.
        watch = lint.load_watch()
        open_ids, _ = watch.parse_ledger(self.LEDGER)
        assert "5" in open_ids, "precondition: #5 is really under ## Open"
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    "- **#5** · landed `abc1234` · 2026-07-28 14:30 · by "
                    "dreamer-5 — the fix\n\n## Folded\n")
        warns = self._warns(tmp_path, self.LEDGER, handoffs)
        assert len(warns) == 1, warns
        assert warns[0].startswith("#5 "), warns[0]
        assert "still under `## Open`" in warns[0]

    def test_a_consumed_handoff_is_not_flagged_again(self, tmp_path):
        # THE red the brief cares about. #5 is OPEN, and the hand-off carries a
        # fold record — so it is consumed and must stay silent even though the
        # task is still open. The task being open is what makes this bind to the
        # consumed marker: a landed task would mask an ignored marker (the
        # delivery signal requires open), so a landed-task fixture could not
        # detect the "flagged forever" bug. Precondition asserted at runtime.
        watch = lint.load_watch()
        open_ids, _ = watch.parse_ledger(self.LEDGER)
        assert "5" in open_ids, "precondition: #5 is really under ## Open"
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    "- **#5** · landed `abc1234` · 2026-07-28 14:30 · by "
                    "dreamer-5 — the fix\n\n## Folded\n\n"
                    "- **#5** → folded (2026-07-28 14:35): moved to Recently "
                    "landed as `def5678`\n")
        assert self._warns(tmp_path, self.LEDGER, handoffs) == []

    def test_a_landed_handoff_with_fold_record_stays_silent(self, tmp_path):
        # #576 companion to test_a_handoff_whose_task_already_landed_is_silent:
        # a landed task WITH a `→ folded` line is consumed — silent, never
        # nagged. Precondition: #6 is really landed.
        watch = lint.load_watch()
        open_ids, _ = watch.parse_ledger(self.LEDGER)
        assert "6" not in open_ids, "precondition: #6 is really landed"
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    "- **#6** · landed `abc1234` · 2026-07-28 14:30 · by "
                    "dreamer-6 — the fix\n\n## Folded\n\n"
                    "- **#6** → folded (2026-07-28 14:35): merged as `def5678`\n")
        assert self._warns(tmp_path, self.LEDGER, handoffs) == []

    def test_a_handoff_whose_task_already_landed_is_silent(self, tmp_path):
        # Pending (not folded) but the task is already landed: the work is done,
        # the fold record is just missing bookkeeping — not the hour-costing case.
        # PRE-#576 this was silent; #576 now WARNs it (landed-but-unfolded was
        # the blind spot that hid Max's 24-entry backlog). The WARN is the same
        # grace shape as the open-but-landed signal.
        watch = lint.load_watch()
        open_ids, _ = watch.parse_ledger(self.LEDGER)
        assert "6" not in open_ids, "precondition: #6 is really landed"
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    "- **#6** · landed `abc1234` · 2026-07-28 14:30 · by "
                    "dreamer-6 — the fix\n\n## Folded\n")
        warns = self._warns(tmp_path, self.LEDGER, handoffs)
        assert len(warns) == 1, warns
        assert "#6" in warns[0]
        assert "no `→ folded` line" in warns[0]
        assert "#576" in warns[0]

    def test_a_missing_file_is_silent(self, tmp_path):
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "tasks.md").write_text(self.LEDGER)
        rep = lint.Report()
        lint.check_handoffs(dw, lint.load_watch(), rep)
        assert rep.rows == [], rep.render()

    def test_a_malformed_pending_entry_is_named(self, tmp_path):
        # A Pending entry head missing the required sha + claimer is a garbled
        # append; the check names the line so the writer fixes it.
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    "- **#5** this line does not follow the grammar\n\n## Folded\n")
        warns = self._warns(tmp_path, self.LEDGER, handoffs)
        assert any("#5" in w and "grammar" in w for w in warns), warns

    def test_a_sub_id_handoff_correlates_to_its_parent_open_id(self, tmp_path):
        """#401: correlation normalises `#392a` → parent `392` against ## Open.

        Precondition: the ledger head is plain `#5`, the hand-off is `#5a`.
        Derived at runtime so a fixture that already used `#5a` as a head
        cannot hollow the test.
        """
        watch = lint.load_watch()
        open_ids, _ = watch.parse_ledger(self.LEDGER)
        assert "5" in open_ids, "precondition: parent #5 is under ## Open"
        assert "5a" not in open_ids, "precondition: sub-id is not a ledger head"
        assert watch.handoff_parent_ids("5a") == ["5"]
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    "- **#5a** · landed `abc1234` · 2026-07-28 14:30 · by "
                    "dreamer-5a — the fix\n\n## Folded\n")
        warns = self._warns(tmp_path, self.LEDGER, handoffs)
        assert len(warns) == 1, warns
        assert warns[0].startswith("#5a "), warns[0]
        assert "still under `## Open`" in warns[0]

    def test_a_pending_line_under_folded_is_named_by_lint(self, tmp_path):
        """#406: a Pending-shaped line under ## Folded is LOUD, not silent."""
        pend_line = ("- **#5** · landed `abc1234` · 2026-07-28 14:30 · by "
                     "dreamer-5 — the fix")
        handoffs = ("# Hand-offs\n\n## Pending\n\n## Folded\n" + pend_line + "\n")
        # Precondition: the line is really after ## Folded.
        assert pend_line in handoffs.split("## Folded", 1)[1]
        warns = self._warns(tmp_path, self.LEDGER, handoffs)
        assert any("#5" in w and "grammar" in w for w in warns), warns

    def test_it_flags_a_handoff_for_a_real_open_id_in_the_live_ledger(self, tmp_path):
        """Red-proved against a REAL condition, not a fixture invented to fail.

        Reads the live ledger, picks a genuinely-open id at runtime, writes the
        hand-off a landing session would write, and asserts the check flags it.
        The precondition — the id really is under `## Open` in the live file —
        is derived at runtime, so the test cannot pass over an id that is no
        longer open. Robust to the ledger changing under it.
        """
        # Post-cutover (#294) tasks.md is the #458 one-line shim (zero open
        # ids), so the runtime `open_ids` precondition below would fail against
        # it. The frozen ledger this check reads is tasks.md.deprecated (same
        # repoint as 7068342d) — committed and frozen at cutover, so the id
        # picked at runtime is a genuinely-open one that cannot drift away.
        live = (Path(lint.__file__).parent / ".dreamwork"
                / "tasks.md.deprecated").read_text()
        watch = lint.load_watch()
        open_ids, _ = watch.parse_ledger(live)
        assert open_ids, "precondition: the live ledger has open ids"
        nid = sorted(open_ids, key=int)[0]
        assert nid in open_ids, "precondition: the chosen id is really open"
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    f"- **#{nid}** · landed `abc1234` · 2026-07-28 14:30 · by "
                    f"dreamer-x — the fix\n\n## Folded\n")
        warns = self._warns(tmp_path, live, handoffs)
        assert len(warns) == 1, warns
        assert warns[0].startswith(f"#{nid} "), warns

    def test_it_would_have_surfaced_362_in_the_revision_that_hid_it(self, tmp_path):
        """The real case, not a fixture: `tasks.md` as it stood at `4ce04e0`,
        where #362 sat under `## Open` carrying ``LANDED `<pending>` ``.

        A hand-off for #362 is what a landing session WOULD have written; this
        check would have surfaced the stuck-open state rather than leaving it
        for accident. The precondition — #362 really is under `## Open` in that
        revision — is asserted first, so the test fails loudly if history no
        longer carries it. The direct model is check_placeholder_citations's
        proof against the same revision.
        """
        import subprocess
        got = subprocess.run(
            ["git", "-C", str(Path(lint.__file__).parent),
             "show", "4ce04e0:.dreamwork/tasks.md"],
            capture_output=True, text=True)
        if got.returncode != 0:
            pytest.skip("history not present (zip install); the live-ledger "
                        "and fixture tests still cover it")
        watch = lint.load_watch()
        open_ids, _ = watch.parse_ledger(got.stdout)
        assert "362" in open_ids, \
            "#362 is no longer under ## Open at 4ce04e0 — this test no longer proves anything"
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "tasks.md").write_text(got.stdout)
        (dw / "handoffs.md").write_text(
            "# Hand-offs\n\n## Pending\n\n"
            "- **#362** · landed `abc1234` · 2026-07-28 04:50 · by dreamer-362 "
            "— the check landed\n\n## Folded\n")
        rep = lint.Report()
        lint.check_handoffs(dw, watch, rep)
        handoff_rows = [d for lvl, w, d in rep.rows
                        if w == "handoffs.md" and lvl == lint.WARN]
        assert len(handoff_rows) == 1, rep.render()
        assert handoff_rows[0].startswith("#362 "), handoff_rows[0]
        assert "still under `## Open`" in handoff_rows[0]

    def test_the_live_repo_handoffs_file_is_silent(self):
        """Dogfood: the live hand-offs file has no hand-off WARNs.

        Coverage always prints an OK row (`N pending, M folded, K malformed`),
        so silence means zero WARNs — not an empty report.
        """
        dw = Path(lint.__file__).parent / ".dreamwork"
        rep = lint.Report()
        lint.check_handoffs(dw, lint.load_watch(), rep)
        warns = [d for lvl, w, d in rep.rows if w == "handoffs.md" and lvl == lint.WARN]
        assert warns == [], rep.render()
        oks = [d for lvl, w, d in rep.rows if w == "handoffs.md" and lvl == lint.OK]
        assert oks and "pending" in oks[0] and "folded" in oks[0] and "malformed" in oks[0], oks

    def test_the_check_is_registered_in_run_checks(self):
        import inspect
        assert "check_handoffs(dw, watch, rep)" in inspect.getsource(lint.run_checks)

    def test_a_two_sha_handoff_is_recognised_not_malformed(self, tmp_path):
        """#415 — a task landing in two commits is the ordinary case.

        #411 landed as two commits (the fix `54c68e8` plus the lint count
        `25a3fe4`); the lane honestly wrote both as ``landed `54c68e8`
        `25a3fe4``` and lint reported *a hand-off entry the grammar does not
        recognise*. The lane was right and the format was wrong. This test
        uses the REAL two-sha line recovered from git history (`f7d5bea`),
        not a fixture invented to fail — a red from a defect that really
        existed is worth more than a synthetic one.

        The task is already landed in the ledger here, so the delivery WARN
        does not fire; the assertion is that the line is NOT malformed.
        """
        import subprocess
        got = subprocess.run(
            ["git", "-C", str(Path(lint.__file__).parent),
             "show", "f7d5bea:.dreamwork/handoffs.md"],
            capture_output=True, text=True)
        if got.returncode != 0:
            pytest.skip("history not present (zip install); the fixture "
                        "test below still covers it")
        # Recover the REAL #411 two-sha line from history, matching by its
        # stable two-sha prefix rather than copying the whole long line.
        two_sha_line = None
        for ln in got.stdout.splitlines():
            if "landed `54c68e8` `25a3fe4`" in ln and ln.lstrip().startswith("- **#411**"):
                two_sha_line = ln
                break
        assert two_sha_line is not None, \
            "the real #411 two-sha line is no longer at f7d5bea — recover it"
        # Precondition (derived at runtime): the line carries TWO backticked
        # shas after `landed`, which is the shape the single-sha grammar
        # rejects. Counting, not a literal, so the test's meaning survives.
        after_landed = two_sha_line.split("landed", 1)[1].split("·", 1)[0]
        sha_count = after_landed.count("`") // 2
        assert sha_count >= 2, "precondition: two shas present, not one"
        # #411 is landed in the live ledger, so the delivery WARN is silent;
        # only the malformed WARN would fire today.
        handoffs = ("# Hand-offs\n\n## Pending\n\n" + two_sha_line +
                    "\n\n## Folded\n")
        warns = self._warns(tmp_path, self.LEDGER, handoffs)
        malformed = [w for w in warns if "grammar" in w]
        assert malformed == [], \
            "a two-sha hand-off must not be malformed (#415): %s" % malformed

    def test_a_zero_sha_pending_handoff_is_still_malformed(self, tmp_path):
        """#415 NEGATIVE — widening the sha count must not swallow zero.

        The grammar widens from one sha to one-or-more. A Pending line with
        NO sha at all — `· landed · ...` — is still malformed: it states no
        commit, so the delivery signal (which commit landed) is empty. A
        widening with no negative test has removed a check rather than
        improved it, and the easy failure of a sha-count widening is
        accepting the empty case.
        """
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    "- **#5** · landed · 2026-07-28 14:30 · by "
                    "dreamer-5 — the fix\n\n## Folded\n")
        warns = self._warns(tmp_path, self.LEDGER, handoffs)
        assert any("#5" in w and "grammar" in w for w in warns), warns

    # #554 — the four git conflict-marker forms, EXACTLY seven of the char at
    # column 0. Each is a real git/diff3 emission, not a synthetic shape.
    @pytest.mark.parametrize("marker_line", [
        "<<<<<<< HEAD",          # merge: ours, with a label
        "||||||| e2acedf5",      # diff3 base + sha — the live #548 incident line
        "=======",               # the separator (a bare seven-= line)
        ">>>>>>> branch",        # merge: theirs, with a label
    ])
    def test_each_conflict_marker_form_at_line_start_is_an_error(
            self, tmp_path, marker_line):
        """#554 — a merge-conflict marker left in handoffs.md is silent to
        parse_handoffs, so it must be LOUD at ERROR.

        parse_handoffs keys on `##` section heads and `- **#id**` entry heads;
        a bare marker line matches neither and falls through to `continue`, so
        it renders as nothing to the parser AND to this check — which is what
        happened at the #548 merge: a ``||||||| e2acedf5`` line lived committed
        in this file and 397/397 tests passed. A marker is a
        reader-cannot-see-what-is-there defect (data loss, silent by nature),
        so this is ERROR, never WARN.

        Born-hollow: every one of these four forms passed the CURRENT suite
        before this check existed — the hole was demonstrated by planting each,
        not theorised. Production line: the ``CONFLICT_MARKER_RE.match(ln)``
        branch plus the ``rep.add(ERROR, "handoffs.md", ...)`` it guards inside
        check_handoffs; sabotage either and this test fails.
        """
        # Precondition (derived at runtime, never a literal): the line really
        # does begin with exactly seven of its marker char at column 0, and not
        # eight — the shape the regex is built for and the shape git emits. A
        # fixture that drifted to six or eight would hollow the meaning, so the
        # gap to both bounds is asserted, not assumed.
        head = marker_line[0]
        assert marker_line.startswith(head * 7), \
            "precondition: line begins with seven of its marker char"
        assert not marker_line.startswith(head * 8), \
            "precondition: not eight — eight-plus is never a git marker form"
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    "- **#6** · landed `abc1234` · 2026-07-28 14:30 · by "
                    "dreamer-6 — the fix\n\n## Folded\n"
                    + marker_line + "\n")
        errs = self._errors(tmp_path, self.LEDGER, handoffs)
        assert len(errs) == 1, errs
        assert "conflict marker" in errs[0], errs[0]
        assert head * 7 in errs[0], errs[0]

    @pytest.mark.parametrize("line", [
        "---",                               # markdown hr — not a marker
        "## A heading",                      # ATX heading — not a marker
        "prose with a ===== run mid-line",   # = inside prose — not at col 0
    ])
    def test_markdown_and_prose_forms_are_not_conflict_markers(
            self, tmp_path, line):
        """#554 NEGATIVE — the marker rule must not cry wolf on markdown/prose.

        The three forms the brief names: a ``---`` hr, a ``##`` heading, and a
        prose line carrying ``=====`` mid-line. None is a conflict marker, and
        none may trip the check — a rule that false-positives on ordinary
        markdown is one the writer mutes, and a muted check is worse than none.
        The over-matching axis is this test's; the under-matching axis (regex
        matches nothing) is the positive test's above.
        """
        # Precondition (non-circular, structural): the line's first seven chars
        # are not one of the four 7-char marker sequences at column 0 — so this
        # fixture is genuinely in the negative class, derived from the string
        # rather than restated from the regex under test.
        seven = ("<<<<<<<", "=======", ">>>>>>>", "|||||||")
        assert line[:7] not in seven, \
            "precondition: this line is not a 7-char marker at column 0"
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    "- **#6** · landed `abc1234` · 2026-07-28 14:30 · by "
                    "dreamer-6 — the fix\n\n## Folded\n" + line + "\n")
        assert self._errors(tmp_path, self.LEDGER, handoffs) == [], \
            "a non-marker markdown/prose line must not trip the check"

    def test_an_eight_equals_line_is_not_the_seven_equals_separator(
            self, tmp_path):
        """#554 boundary — the ``=======`` separator is EXACTLY seven ``=``.

        The regex's negative lookahead pins exactly-seven; an eight-``=`` line
        is the boundary case and must stay silent. This guards the lookahead
        specifically — it is the subtlest line in the regex and the brief's
        ``exactly seven =`` requirement, and a regression to ``={7}`` (no
        lookahead) would flag it.
        """
        line = "========"  # eight =
        # Precondition: really eight equals — the count, not a literal echo.
        assert line.count("=") == 8, "precondition: eight equals, not seven"
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    "- **#6** · landed `abc1234` · 2026-07-28 14:30 · by "
                    "dreamer-6 — the fix\n\n## Folded\n" + line + "\n")
        assert self._errors(tmp_path, self.LEDGER, handoffs) == [], \
            "an eight-= line is not the seven-= separator and must be silent"

    def test_the_marker_check_runs_even_when_the_watch_parser_is_absent(
            self, tmp_path):
        """#554 — the parse hazard is independent of the parser, so the scan
        runs BEFORE the ``watch is None`` early return.

        load_watch returns None when watch.py is unimportable (mid-edit by
        another agent). A conflict marker is still a corruption then — the
        parser being absent does not make a ``|||||||`` line safe — so the scan
        must fire regardless. Guards the placement of the scan: move it after
        the early return and this test fails (the marker would pass silently,
        exactly the born-hollow state).
        """
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "tasks.md").write_text(self.LEDGER)
        (dw / "handoffs.md").write_text(
            "# Hand-offs\n\n## Pending\n\n"
            "- **#6** · landed `abc1234` · 2026-07-28 14:30 · by dreamer-6 — fix\n"
            "\n## Folded\n||||||| e2acedf5\n")
        rep = lint.Report()
        # watch=None is the state load_watch returns on an unimportable watch.py.
        lint.check_handoffs(dw, None, rep)
        errs = [d for lvl, w, d in rep.rows
                if w == "handoffs.md" and lvl == lint.ERROR]
        assert len(errs) == 1 and "conflict marker" in errs[0], errs

    def test_the_conflict_marker_regex_is_wired_into_check_handoffs(self):
        """#554 — the regex is referenced by the check that uses it.

        A module-level constant that nothing imports is a check waiting to be
        silently dropped; this asserts the wiring so a refactor that detaches
        ``CONFLICT_MARKER_RE`` from ``check_handoffs`` is caught.
        """
        import inspect
        assert hasattr(lint, "CONFLICT_MARKER_RE")
        assert "CONFLICT_MARKER_RE.match(ln)" in \
            inspect.getsource(lint.check_handoffs)

    # ---- #679: a cited landing/merge sha must resolve ---------------------
    #
    # The discriminator is `CITED_SHA` (the established keyword-led regex from
    # `check_cited_shas`), applied to the SAME text `check_handoffs` reads —
    # extending the reader, not a second one. These git-backed fixtures mirror
    # `check_cited_shas`'s `build` helper (real repo, one letter-bearing commit).

    def _run_git_handoffs(self, tmp_path, handoffs, ledger=None):
        """A real git repo with one live commit, so sha resolution runs."""
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()

        def git(*a):
            return subprocess.run(["git", "-C", str(t), *a],
                                  capture_output=True, text=True, check=True)
        git("init", "-q")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        n = 0
        while True:  # the short sha must carry a letter (the PID filter)
            n += 1
            (t / "f").write_text(str(n))
            git("add", "f")
            git("commit", "-qm", "a real commit")
            live = git("rev-parse", "HEAD").stdout.strip()[:7]
            if re.search(r"[a-f]", live):
                break
        assert re.search(r"[a-f]", live), live
        (dw / "tasks.md").write_text(ledger or self.LEDGER)
        (dw / "handoffs.md").write_text(handoffs.replace("LIVE", live))
        rep = lint.Report()
        lint.check_handoffs(dw, lint.load_watch(), rep)
        return rep, live

    def _herrs(self, rep):
        return [d for lvl, w, d in rep.rows
                if w == "handoffs.md" and lvl == lint.ERROR and "#679" in d]

    def test_a_dead_cited_sha_in_a_handoff_is_an_error(self, tmp_path):
        # Direction 1. `deadbeef` is cited as a landing but resolves to nothing;
        # `LIVE` (a real commit in the same repo) is cited too, so the
        # all-missing wrong-tree guard does not suppress the ERROR.
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    "- **#5** · landed `deadbeef` · 2026-07-28 · by x — fix\n\n"
                    "## Folded\n\n"
                    "- **#6** → folded (2026-07-28): merged `LIVE`\n")
        rep, live = self._run_git_handoffs(tmp_path, handoffs)
        errs = self._herrs(rep)
        assert len(errs) == 1, (errs, live)
        assert errs[0].startswith("`deadbeef`"), errs[0]
        assert "#5" in errs[0] and "#679" in errs[0]
        # Precondition: the LIVE sha in the same run must NOT be flagged, or
        # the check is flagging everything rather than discriminating.
        assert live not in errs[0]

    def test_a_live_cited_sha_in_a_handoff_resolves_clean(self, tmp_path):
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    "- **#6** · landed `LIVE` · 2026-07-28 · by x — fix\n\n"
                    "## Folded\n")
        rep, live = self._run_git_handoffs(tmp_path, handoffs)
        assert self._herrs(rep) == [], (live,)
        oks = [d for lvl, w, d in rep.rows
               if w == "handoffs.md" and lvl == lint.OK and "resolve" in d]
        assert oks and "1" in oks[0], oks

    def test_a_dead_sha_is_attributed_to_its_combined_id_row(self, tmp_path):
        # #655's reuse guard. The id in the ERROR comes from parse_handoffs's
        # row extraction (combined token #5/#6), never from CITED_SHA — so a
        # copy-pasted parser that split the combined id would mis-attribute.
        watch = lint.load_watch()
        pend, _, _ = watch.parse_handoffs(
            "## Pending\n\n"
            "- **#5/#6** · landed `deadbeef` · 2026-07-28 · by x\n")
        assert pend and pend[0].id == "5/6", \
            "precondition: the parser keeps the combined id token"
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    "- **#5/#6** · landed `deadbeef` · 2026-07-28 · by x — fix\n\n"
                    "## Folded\n\n"
                    "- **#6** → folded (2026-07-28): merged `LIVE`\n")
        rep, live = self._run_git_handoffs(tmp_path, handoffs)
        errs = self._herrs(rep)
        assert len(errs) == 1, errs
        # The parser keeps the combined token #5/#6 as one element, so the
        # attribution is "(#5/6)" — never the split form "(#5, #6)". A
        # copy-pasted parser that split it would render differently.
        assert "(#5/6)" in errs[0], errs[0]
        assert "(#5, #6)" not in errs[0], errs[0]

    def test_a_lane_id_in_a_fold_note_is_not_flagged(self, tmp_path):
        # Direction 2, hazard 1. `(lane \`019fb4e0\`, …)` is a session id, not a
        # commit; "lane" is not a landing keyword, so CITED_SHA must not see
        # it. A bare backtick+hex scan (the over-broad `_handoff_fold_shas`)
        # catches it — the false positive that gets a naive check turned off.
        handoffs = ("# Hand-offs\n\n## Folded\n\n"
                    "- **#6** → folded (2026-07-28): merged `LIVE` (lane "
                    "`019fb4e0`, lane-x, glm-5.2)\n\n## Pending\n")
        rep, live = self._run_git_handoffs(tmp_path, handoffs)
        assert self._herrs(rep) == [], ("lane id flagged: %r" % ([d for _,_,d in rep.rows],))

    def test_a_pending_placeholder_is_not_flagged(self, tmp_path):
        # Direction 2. `landed \`PENDING\`` is a placeholder, not a sha — non-
        # hex, so CITED_SHA (hex 7-40) does not see it. A different defect (no
        # sha at all), not the "indistinguishable from real" kind #679 targets.
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    "- **#5** · landed `PENDING` · 2026-07-28 · by x — fix\n\n"
                    "## Folded\n\n"
                    "- **#6** → folded (2026-07-28): merged `LIVE`\n")
        rep, live = self._run_git_handoffs(tmp_path, handoffs)
        assert self._herrs(rep) == [], ("PENDING flagged: %r" % ([d for _,_,d in rep.rows],))

    def test_a_sha256_page_digest_is_not_flagged(self, tmp_path):
        # Direction 2, hazard 1. A 64-char sha256 page digest in backticks is
        # not a commit sha: the 40-char cap plus backtick delimitation rejects
        # it (no position 7-40 is followed by a backtick).
        digest = "db2b848bcd7a4723b7901cdfa96fdef5721f67336b8cdd9c71ad85ef48bfd0e0"
        handoffs = ("# Hand-offs\n\n## Folded\n\n"
                    "- **#6** → folded (2026-07-28): merged `LIVE`, page "
                    f"sha256 `{digest}`\n\n## Pending\n")
        rep, live = self._run_git_handoffs(tmp_path, handoffs)
        assert self._herrs(rep) == [], ("digest flagged: %r" % ([d for _,_,d in rep.rows],))

    def test_all_shas_missing_reads_as_the_wrong_tree_not_errors(self, tmp_path):
        # Direction 2. A single dead cited sha in a real repo where EVERY cited
        # sha is missing reads as the wrong tree (a fresh clone / different
        # target), not a file of lies — OK, never ERRORs (mirrors #380).
        handoffs = ("# Hand-offs\n\n## Folded\n\n"
                    "- **#6** → folded (2026-07-28): merged `deadbeef`\n\n"
                    "## Pending\n")
        rep, live = self._run_git_handoffs(tmp_path, handoffs)
        assert self._herrs(rep) == [], ("single dead sha ERRORed: %r" % self._herrs(rep))
        oks = [d for lvl, w, d in rep.rows
               if w == "handoffs.md" and "wrong tree" in d]
        assert oks, "expected a wrong-tree OK row"

    def test_in_a_non_git_tree_the_sha_check_says_it_went_unchecked(self, tmp_path):
        # #380: a skip is always a row. A non-git tmp_path with a cited sha
        # must not ERROR (cannot resolve) and must not stay silent.
        rep = self._run(tmp_path, self.LEDGER,
                        "# Hand-offs\n\n## Pending\n\n"
                        "- **#5** · landed `abcdef1` · 2026-07-28 · by x\n\n"
                        "## Folded\n")
        skip = [d for lvl, w, d in rep.rows
                if w == "handoffs.md" and "unchecked" in d]
        assert skip, "expected an 'unchecked' skip row in a non-git tree"
        assert self._herrs(rep) == []

    # ---- #677: warn when a pending hand-off's branch is behind master ------
    #
    # Scoped to pending-and-open (not folded) rows — the "awaiting merge"
    # set. #590's rule: behind-ness is expected for a live lane, so the
    # pending hand-off is the "done" anchor, and a not-yet-merged row is the
    # only one this fires on. The examined-N coverage row is the #671 shape:
    # whatever this pass cannot evaluate it must SAY SO, never a silent skip.

    def _behind(self, tmp_path, handoffs, *, master_tip=None):
        """A real git repo; master at MASTER_TIP, one lane commit on a branch.

        Returns (rep, lane_sha) where lane_sha is the commit on the lane
        branch — behind master when MASTER_TIP is given."""
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()

        def git(*a):
            return subprocess.run(["git", "-C", str(t), *a],
                                  capture_output=True, text=True, check=True)
        git("init", "-q", "-b", "master")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        (t / "f").write_text("1"); git("add", "f"); git("commit", "-qm", "base")
        lane = None
        if master_tip:
            # advance master past the lane's base, so a lane commit off the
            # old base is behind master.
            (t / "f").write_text(master_tip); git("add", "f")
            git("commit", "-qm", "master advanced")
        # lane commit off the FIRST commit (the pre-advance base) so it is behind
        git("checkout", "-q", "HEAD~1" if master_tip else "master")
        (t / "g").write_text("lane"); git("add", "g"); git("commit", "-qm", "lane work")
        n = 0
        while True:
            n += 1
            (t / "g").write_text(f"lane{n}"); git("add", "g")
            git("commit", "-qm", "lane work")
            lane = git("rev-parse", "HEAD").stdout.strip()[:7]
            if re.search(r"[a-f]", lane):
                break
        git("checkout", "-q", "master")
        (dw / "tasks.md").write_text(self.LEDGER)
        (dw / "handoffs.md").write_text(handoffs.replace("LANE", lane))
        rep = lint.Report()
        lint.check_handoffs(dw, lint.load_watch(), rep)
        return rep, lane

    def _677rows(self, rep):
        out = {}
        for lvl, w, d in rep.rows:
            if w == "handoffs.md":
                out.setdefault(lvl, []).append(d)
        return out

    def test_a_pending_open_handoff_behind_master_warns(self, tmp_path):
        # Direction 1. #5 is open and pending (not folded); its sha is one
        # commit behind master (master advanced after the lane branched).
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    "- **#5** · landed `LANE` · 2026-07-28 · by x — fix\n\n"
                    "## Folded\n")
        rep, lane = self._behind(tmp_path, handoffs, master_tip="adv")
        warns = [d for d in self._677rows(rep).get(lint.WARN, []) if "#677" in d]
        assert len(warns) == 1, (warns, lane)
        assert "#5" in warns[0] and lane in warns[0] and "1 commit" in warns[0]

    def test_a_pending_open_handoff_at_master_is_silent(self, tmp_path):
        # The non-behind case: lane branched from master HEAD, no advance.
        # rev-list <sha>..master is 0; no WARN, no ERROR.
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    "- **#5** · landed `LANE` · 2026-07-28 · by x — fix\n\n"
                    "## Folded\n")
        rep, lane = self._behind(tmp_path, handoffs)
        behind_warns = [d for d in self._677rows(rep).get(lint.WARN, [])
                        if "#677" in d]
        assert behind_warns == [], (behind_warns, lane)

    def test_a_folded_handoff_behind_master_is_silent(self, tmp_path):
        # Scope guard (hazard 4). A folded hand-off is consumed — the delivery
        # check skips it, and so must the behind check, even if its branch is
        # behind. Folding is the "I have seen this" marker; nagging after
        # compliance gets a check muted.
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    "- **#5** · landed `LANE` · 2026-07-28 · by x — fix\n\n"
                    "## Folded\n\n"
                    "- **#5** → folded (2026-07-28): merged `LANE`\n")
        rep, lane = self._behind(tmp_path, handoffs, master_tip="adv")
        behind_warns = [d for d in self._677rows(rep).get(lint.WARN, [])
                        if "#677" in d]
        assert behind_warns == [], ("folded-but-behind warned: %r" % behind_warns)

    def test_the_pass_reports_what_it_examined(self, tmp_path):
        # #671 shape. Whenever the behind pass runs at all, it must emit an
        # "examined N, behind M, could-not K" coverage row — never a silent
        # skip. A behind-WARN is present, so the row must be too.
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    "- **#5** · landed `LANE` · 2026-07-28 · by x — fix\n\n"
                    "## Folded\n")
        rep, lane = self._behind(tmp_path, handoffs, master_tip="adv")
        cov = [d for d in self._677rows(rep).get(lint.OK, [])
               if "behind-master" in d and "examined" in d]
        assert len(cov) == 1, (cov, lane)
        # "examined 1 … 1 behind, 0 could not" — the counts travel with words.
        assert "examined 1" in cov[0], cov[0]
        assert "1 behind" in cov[0] or "behind 1" in cov[0], cov[0]

    def test_an_unresolvable_lane_sha_is_reported_not_silently_skipped(self, tmp_path):
        # Direction 1, hazard 3 — the primary case. A lane that appended its
        # hand-off and THEN rebased has a sha that resolves to nothing. A
        # check that silently skips what it cannot resolve is #671 repeating.
        # Here: cite a genuinely-nonexistent sha. The behind pass must count
        # it in could-not-evaluate (the #679 block ERRORs it file-wide too).
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    "- **#5** · landed `deadbeef` · 2026-07-28 · by x — fix\n\n"
                    "## Folded\n\n"
                    "- **#6** → folded (2026-07-28): merged `LANE`\n")
        rep, lane = self._behind(tmp_path, handoffs, master_tip="adv")
        cov = [d for d in self._677rows(rep).get(lint.OK, [])
               if "behind-master" in d]
        assert cov, ("no behind-master coverage row at all", lane)
        # The COUNT must be non-zero — not just the phrase, which the row
        # template always carries ("0 could not be evaluated"). A silent-skip
        # sabotage leaves could_not at 0 while printing the same words, so
        # asserting the phrase alone is hollow (caught: the first direction-2
        # run came back green; this count-assertion is the fix).
        import re as _re
        m = _re.search(r"(\d+) could not be evaluated", cov[0])
        assert m and int(m.group(1)) >= 1, \
            ("unresolvable sha was silently skipped (could_not=0): %r" % cov[0])
        # And it must not WARN as behind (it could not be evaluated).
        behind = [d for d in self._677rows(rep).get(lint.WARN, [])
                  if "#677" in d]
        assert behind == [], behind


class TestConflictMarkerSweep555:
    """#555 — the #554 marker rejection extended to the other tool-parsed
    ledger docs.

    The same silent-corruption class, per surface: each parser keys on its
    own head grammar the way parse_handoffs does, so a bare conflict-marker
    line matches none of those keys and falls through to nothing — the
    reader cannot see what is there. `tasks.md` (parse_ledger, the most
    parse-sensitive file in the repo), `tasks.md.deprecated` (the frozen
    history, also parse_ledger), `questions.md` (parse_questions), and
    `briefs/*.md` (classify_brief_handoff_scope) each have the shape.

    ONE regex — the module-level CONFLICT_MARKER_RE #554 landed — re-used,
    not restated (#137 single-definition rule). The idiom is the #554 one:
    raw-text scan at the TOP of each check, BEFORE any parser-dependent
    early return, one ERROR per marker line so each is named.

    Born-hollow (recorded per surface by the red-first run of these very
    tests against the PRE-scan code): every one of the four marker forms
    passed the CURRENT checks silently — the assertion ``len(errs) == 1``
    failed at ``0`` because no check produced a ``conflict marker`` ERROR.
    The hole was demonstrated by planting each, not theorised.
    """

    # The four real git/diff3 emissions — exactly seven of the char at col 0.
    MARKERS = [
        "<<<<<<< HEAD",          # merge: ours, with a label
        "||||||| e2acedf5",      # diff3 base + sha — the live #548 incident line
        "=======",               # the separator (a bare seven-= line)
        ">>>>>>> branch",        # merge: theirs, with a label
    ]
    # The brief's four negative forms: a markdown hr, an ATX heading, a
    # setext `===` underline, and a prose line carrying `=====` mid-line.
    # None is a 7-char marker at column 0, and none may trip the scan.
    NEG_LINES = ["---", "## A heading", "===", "prose with a ===== run mid-line"]

    # ── questions.md (check_questions, parse_questions) ──────────────────
    def _q_errs(self, tmp_path, body):
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "questions.md").write_text(body)
        rep = lint.Report()
        lint.check_questions(dw, lint.load_watch(), rep)
        return [d for lvl, w, d in rep.rows
                if lvl == lint.ERROR and "conflict marker" in d]

    @pytest.mark.parametrize("marker_line", MARKERS)
    def test_questions_md_marker_is_an_error(self, tmp_path, marker_line):
        """Production line: the CONFLICT_MARKER_RE scan on the raw text at the
        top of check_questions + its rep.add(ERROR, "questions.md", ...).
        parse_questions keys on `- **Title**` entry heads; a marker matches
        none and renders as nothing, so it must be LOUD here.
        """
        head = marker_line[0]
        assert marker_line.startswith(head * 7), "precondition: seven at col 0"
        assert not marker_line.startswith(head * 8), "precondition: not eight"
        body = ("# Questions\n\n## Open\n\n"
                "- **A real open question** · P2 · the ask\n\n"
                + marker_line + "\n\n## Answered\n")
        assert marker_line in body, "precondition: the marker line is really present"
        errs = self._q_errs(tmp_path, body)
        assert len(errs) == 1, errs
        assert head * 7 in errs[0], errs[0]

    def test_questions_md_negatives_are_silent(self, tmp_path):
        body = ("# Questions\n\n## Open\n\n"
                "- **A real open question** · P2 · the ask\n\n"
                + "\n".join(self.NEG_LINES) + "\n\n## Answered\n")
        for nl in self.NEG_LINES:
            assert nl in body, "precondition: each negative line is present"
        assert self._q_errs(tmp_path, body) == [], \
            "a non-marker markdown/prose line must not trip the scan"

    # ── tasks.md markdown (check_ledger_sections, parse_ledger) ──────────
    def _ledger_errs(self, text):
        rep = lint.Report()
        lint.check_ledger_sections(Path("."), text, "markdown", rep)
        return [d for lvl, w, d in rep.rows
                if lvl == lint.ERROR and "conflict marker" in d]

    @pytest.mark.parametrize("marker_line", MARKERS)
    def test_tasks_md_marker_is_an_error(self, marker_line):
        """Production line: the CONFLICT_MARKER_RE scan on the `text` param at
        the top of check_ledger_sections + its rep.add(ERROR, "tasks.md", ...).
        In markdown mode `text` IS tasks.md verbatim; parse_ledger keys on
        `## Open`/entry heads, so a marker is silent to both readers.
        """
        head = marker_line[0]
        assert marker_line.startswith(head * 7), "precondition: seven at col 0"
        assert not marker_line.startswith(head * 8), "precondition: not eight"
        text = ("# Task ledger\n\nNext id: **9**\n\n## Open\n\n"
                "- **#7** — a task · P2 · task\n\n"
                + marker_line + "\n\n## Recently landed\n\n"
                "- **#5** — landed `abc1234`\n")
        assert marker_line in text, "precondition: the marker line is really present"
        errs = self._ledger_errs(text)
        assert len(errs) == 1, errs
        assert head * 7 in errs[0], errs[0]

    def test_tasks_md_negatives_are_silent(self):
        # Negatives placed AFTER the real ledger structure so a stray
        # `## A heading` cannot move the Open section boundary (#304).
        text = ("# Task ledger\n\nNext id: **9**\n\n## Open\n\n"
                "- **#7** — a task · P2 · task\n\n"
                "## Recently landed\n\n"
                "- **#5** — landed `abc1234`\n\n"
                + "\n".join(self.NEG_LINES) + "\n")
        for nl in self.NEG_LINES:
            assert nl in text, "precondition: each negative line is present"
        assert self._ledger_errs(text) == [], \
            "a non-marker markdown/prose line must not trip the scan"

    # ── tasks.md.deprecated store mode (check_ledger_sections store branch) ──
    def _dep_errs(self, tmp_path, dep_text):
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "tasks.md.deprecated").write_text(dep_text)
        rep = lint.Report()
        lint.check_ledger_sections(dw, "unused", "store", rep)
        return [d for lvl, w, d in rep.rows
                if lvl == lint.ERROR and "conflict marker" in d]

    @pytest.mark.parametrize("marker_line", MARKERS)
    def test_tasks_md_deprecated_marker_is_an_error(self, tmp_path, marker_line):
        """Production line: the CONFLICT_MARKER_RE scan on `dtext` inside the
        store branch of check_ledger_sections + its rep.add(ERROR,
        "tasks.md.deprecated", ...). The deprecated file is the FROZEN history
        read only in store mode; a marker rots it the same silent way.
        """
        head = marker_line[0]
        assert marker_line.startswith(head * 7), "precondition: seven at col 0"
        assert not marker_line.startswith(head * 8), "precondition: not eight"
        dep = ("# Task ledger\n\nNext id: **9**\n\n## Open\n\n"
               "- **#7** — a task · P2 · task\n\n"
               + marker_line + "\n\n## Recently landed\n\n"
               "- **#5** — landed `abc1234`\n")
        assert marker_line in dep, "precondition: the marker line is really present"
        errs = self._dep_errs(tmp_path, dep)
        assert len(errs) == 1, errs
        assert head * 7 in errs[0], errs[0]

    def test_tasks_md_deprecated_negatives_are_silent(self, tmp_path):
        dep = ("# Task ledger\n\nNext id: **9**\n\n## Open\n\n"
               "- **#7** — a task · P2 · task\n\n"
               "## Recently landed\n\n"
               "- **#5** — landed `abc1234`\n\n"
               + "\n".join(self.NEG_LINES) + "\n")
        for nl in self.NEG_LINES:
            assert nl in dep, "precondition: each negative line is present"
        assert self._dep_errs(tmp_path, dep) == [], \
            "a non-marker markdown/prose line must not trip the scan"

    # ── briefs/*.md (check_brief_handoff_obligation) ─────────────────────
    def _brief_errs(self, tmp_path, brief_body, name="900-marker.md"):
        t = fresh(tmp_path)
        root = t
        dw = root / ".dreamwork"
        (root / "SKILL.md").write_text("# skill\n", encoding="utf-8")
        briefs = dw / "docs" / "briefs"
        briefs.mkdir(parents=True)
        (briefs / name).write_text(brief_body, encoding="utf-8")
        rep = lint.Report()
        lint.check_brief_handoff_obligation(dw, rep)
        return [d for lvl, w, d in rep.rows
                if lvl == lint.ERROR and "conflict marker" in d]

    @pytest.mark.parametrize("marker_line", MARKERS)
    def test_brief_marker_is_an_error(self, tmp_path, marker_line):
        """Production line: the CONFLICT_MARKER_RE scan over the globbed brief
        files in check_brief_handoff_obligation + its rep.add(ERROR,
        "briefs", ...). The scan lives in the CHECK, not the classifier,
        because classify_brief_handoff_scope only reads text for in-scope
        briefs (grandfathered/skipped short-circuit before read) — a marker
        in any brief is corruption regardless of scope.
        """
        head = marker_line[0]
        assert marker_line.startswith(head * 7), "precondition: seven at col 0"
        assert not marker_line.startswith(head * 8), "precondition: not eight"
        body = "# Brief\n\n" + marker_line + "\n\nDo the work.\n"
        assert marker_line in body, "precondition: the marker line is really present"
        errs = self._brief_errs(tmp_path, body)
        assert len(errs) == 1, errs
        assert head * 7 in errs[0], errs[0]
        assert "900-marker.md" in errs[0], \
            "the ERROR must name the brief file so the reader can find it"

    def test_brief_negatives_are_silent(self, tmp_path):
        body = "# Brief\n\n" + "\n".join(self.NEG_LINES) + "\n\nDo the work.\n"
        for nl in self.NEG_LINES:
            assert nl in body, "precondition: each negative line is present"
        assert self._brief_errs(tmp_path, body) == [], \
            "a non-marker markdown/prose line must not trip the scan"

    def test_each_swept_check_references_the_shared_regex(self):
        """A module-level constant nothing imports is a check waiting to be
        silently dropped; this asserts each swept check is wired to the ONE
        shared CONFLICT_MARKER_RE so a refactor that detaches any is caught.
        Mirrors the #554 wiring test for check_handoffs.
        """
        import inspect
        for fn in (lint.check_questions, lint.check_ledger_sections,
                   lint.check_brief_handoff_obligation):
            assert "CONFLICT_MARKER_RE" in inspect.getsource(fn), fn.__name__


class TestCitedShas:
    """#350: a ledger entry that cites a commit which does not exist.

    Found by self-review, not by anyone noticing. #302's entry cited
    `f0f4e2a`-merge while the work is at `08cd931` — almost certainly the
    worktree branch's sha, unreachable once merged. That matters beyond
    tidiness: `check_landed_still_open` reads a cited commit as the entry's
    evidence that it is deliberately still open, so a dead citation is silent
    in both directions.

    The two false-positive cases below are not hypothetical. Each killed a
    looser rule measured against the live ledger, and each is pinned here so
    the rule cannot quietly loosen back:

    - a pure-digit token: 6 real ones (`1246815`, `251691418`) are PIDs that
      happen to be valid hex;
    - an alias beside a NEIGHBOURING citation: `fade326` is a c2c peer alias of
      seven hex digits, and a "keyword within 40 characters" rule flags it
      because the keyword belongs to the sha before it.
    """

    def build(self, tmp_path, ledger):
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
        # #478: the short sha MUST contain a letter. A pure-digit prefix —
        # (10/16)^7 ≈ 3.7% of commits, measured 6-in-160 against this fixture —
        # is dropped by the check's PID filter (`re.search(r"[a-f]", token)`),
        # so `test_a_dead_cited_sha_warns` collapsed to ONE collected sha, the
        # all-missing branch read it as the wrong tree at OK, and the test
        # failed with a bare `[]` — twice in a full suite, never reproducibly,
        # because the commit sha is new every run. Re-roll until the prefix
        # discriminates, and assert it: this precondition is the whole test.
        n = 0
        while True:
            n += 1
            (t / "f").write_text(str(n))
            git("add", "f")
            git("commit", "-qm", "a real commit")
            live = git("rev-parse", "HEAD").stdout.strip()[:7]
            if re.search(r"[a-f]", live):
                break
        assert re.search(r"[a-f]", live), live
        (dw / "tasks.md").write_text(ledger.replace("LIVE", live))
        return t, live

    def rows(self, t, level=None):
        rep = lint.Report()
        lint.run_checks(t / ".dreamwork", lint.load_watch(), rep)
        return [d for lvl, w, d in rep.rows
                if w == "tasks.md" and "cite" in d
                and (level is None or lvl == level)]

    LEDGER = """# Tasks

Next id: **9**

## Open

- **#1** — a task · P2 · origin: **loop** · still going

## Recently landed

- **#2** — cites a live commit · landed `LIVE` · origin: **loop**
"""

    def test_a_dead_cited_sha_warns(self, tmp_path):
        t, live = self.build(tmp_path, self.LEDGER.replace(
            "landed `LIVE`", "landed `LIVE` and also merged `beefca7`"))
        warns = self.rows(t, lint.WARN)
        # #478: report EVERY cite row on failure, not just the WARN ones. This
        # test has now failed twice in a full suite and passed in isolation both
        # times, and both times the failure printed a bare `[]` — because a
        # check that DECLINED to run emits its skip row at OK, which this
        # filtered view drops. #380 added those rows so the next occurrence
        # would say which exit it took; the assertion has to show them or that
        # work is invisible exactly when it is needed.
        assert len(warns) == 1, (warns, "all cite rows: %r" % (self.rows(t),))
        assert "beefca7" in warns[0]
        # Precondition: the LIVE sha in the same entry must NOT be flagged, or
        # the check is flagging everything rather than discriminating.
        assert live not in warns[0]

    def test_a_live_cited_sha_is_reported_ok_and_never_warned(self, tmp_path):
        t, live = self.build(tmp_path, self.LEDGER)
        assert self.rows(t, lint.WARN) == []
        oks = self.rows(t, lint.OK)
        assert len(oks) == 1 and "resolve" in oks[0]

    def test_a_pure_digit_token_is_a_pid_not_a_sha(self, tmp_path):
        """`1246815` is valid hex and is a PID. Six of them are in the live
        ledger. The production line: the `re.search(r"[a-f]", token)` filter."""
        ledger = self.LEDGER.replace(
            "still going",
            "every snapshot saw PID `1246815`, reparented, and it landed `1246815`")
        t, live = self.build(tmp_path, ledger)
        warns = self.rows(t, lint.WARN)
        assert warns == [], "a pure-digit PID was read as a commit: %r" % warns

    def test_an_alias_beside_a_neighbouring_citation_is_not_flagged(self, tmp_path):
        """The case that killed keyword-proximity. `fade326` is an agent alias;
        the nearby keyword introduces the sha BEFORE it.

        The production line is `CITED_SHA` requiring the keyword to immediately
        introduce the token. Widen it back to a 40-character window and this
        fails while the others still pass.
        """
        ledger = self.LEDGER.replace(
            "still going",
            "· **merged `LIVE`** (agent `fade326`, its own worktree)")
        t, live = self.build(tmp_path, ledger)
        warns = self.rows(t, lint.WARN)
        assert warns == [], "an agent alias was read as a commit: %r" % warns

    def test_a_bare_backticked_sha_with_no_keyword_is_not_a_citation(self, tmp_path):
        """Deliberate scope: a reference is not a claim about a landing, and
        widening to bare tokens reintroduces the alias false positive."""
        ledger = self.LEDGER.replace("still going", "see `abcdef1` for context")
        t, live = self.build(tmp_path, ledger)
        assert self.rows(t, lint.WARN) == []

    def test_every_sha_missing_states_the_assumption_it_made(self, tmp_path):
        """A fresh clone or the wrong target is not a ledger full of errors —
        but it is not nothing either, and it used to render as nothing (#380).

        The production line is the `len(dead) == len(shas)` guard: it must still
        suppress the WARNs (delete it and `test_a_dead_cited_sha_warns` keeps
        passing while this one gains two) and it must now SAY that it did.
        """
        ledger = self.LEDGER.replace("landed `LIVE`", "landed `f0f4e2a`")
        t, live = self.build(tmp_path, ledger)
        assert self.rows(t, lint.WARN) == [], "the wrong tree is not a wrong ledger"
        oks = self.rows(t, lint.OK)
        assert len(oks) == 1, oks
        assert "wrong tree" in oks[0] and "nothing was checked" in oks[0]

    def test_a_target_that_is_not_a_git_repo_says_it_could_not_check(self, tmp_path):
        """#380, and the docstring's own principle: *"cannot check" must not
        read as "nothing to fix"*. It read as exactly that for a non-repo
        target, because the exit was a bare `return`.

        Not a WARN: a target with no `.git` has not done anything wrong. The
        production line is the OK row on the empty-stdout exit — make it a
        bare `return` again and this fails while every other row here passes.
        """
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "tasks.md").write_text(
            self.LEDGER.replace("landed `LIVE`", "landed `f0f4e2a`"))
        # Precondition for the OK-not-WARN branch, asserted rather than assumed.
        assert not (t / ".git").exists()
        assert self.rows(t, lint.WARN) == []
        oks = self.rows(t, lint.OK)
        assert len(oks) == 1, oks
        assert "unchecked" in oks[0]

    def test_a_broken_git_inside_a_real_repo_warns(self, tmp_path):
        """The other half of the same exit, and the half that matters: `.git`
        is present, so git failing IS an anomaly and must be loud.

        The seam is real — no patching. `.git` is replaced with a gitdir
        pointer to nowhere, which is what a moved worktree leaves behind.
        """
        import shutil
        t, live = self.build(tmp_path, self.LEDGER)
        shutil.rmtree(t / ".git")
        (t / ".git").write_text("gitdir: /nonexistent/elsewhere\n")
        assert (t / ".git").exists(), "precondition: the WARN branch needs .git"
        warns = self.rows(t, lint.WARN)
        assert len(warns) == 1, warns
        assert "unchecked" in warns[0]

    def test_git_absent_from_path_is_reported_rather_than_swallowed(self, tmp_path):
        """The `OSError` exit. Induced at a real seam — `PATH` is emptied, so
        the actual `execvp` fails — rather than by patching `subprocess`.

        The production line is the row inside the `except` clause.
        """
        t, live = self.build(tmp_path, self.LEDGER)
        import os
        saved = os.environ.get("PATH", "")
        os.environ["PATH"] = ""
        try:
            rows = self.rows(t)
        finally:
            os.environ["PATH"] = saved
        assert len(rows) == 1, rows
        assert "unchecked" in rows[0] or "could not ask git" in rows[0]

    def test_a_short_answer_from_git_is_not_silently_truncated(self, tmp_path,
                                                               monkeypatch):
        """`--batch-check` writes one line per input, so fewer lines back means
        the tail was never examined — and `zip(shas, lines)` made that
        invisible. A dead sha in the truncated tail went unreported.

        The production line is the `len(lines) != len(shas)` comparison. Delete
        it and this fails: the fixture's dead sha is deliberately the SECOND of
        the two, so `zip` drops precisely the one that should warn.
        """
        ledger = self.LEDGER.replace(
            "landed `LIVE`", "landed `LIVE` and also merged `beefca7`")
        t, live = self.build(tmp_path, ledger)
        real = lint.subprocess.run
        seen = {}

        def short(cmd, *a, **kw):
            out = real(cmd, *a, **kw)
            if isinstance(cmd, list) and "cat-file" in cmd:
                lines = out.stdout.splitlines(True)
                seen["full"] = len(lines)
                out.stdout = lines[0] if lines else ""
            return out

        monkeypatch.setattr(lint.subprocess, "run", short)
        rows = self.rows(t)
        # The precondition the whole test depends on: git really did answer for
        # both, so the truncation removed a line that existed. Without this the
        # test passes just as well when git answers for none.
        assert seen.get("full") == 2, "git did not answer for both shas: %r" % seen
        assert len(rows) == 1, rows
        assert "1 of 2" in rows[0]

    def test_the_fixture_live_sha_never_collapses_to_a_pid(self, tmp_path):
        """#478: the flake that read as a suite-order decline, pinned at its
        actual line.

        `test_a_dead_cited_sha_warns` failed twice in full suites and passed
        every isolated run, printing a bare `[]`. Suite-order env leakage
        (`GIT_DIR`) was the suspect, but it cannot produce that signature: a
        process-wide leak redirects THIS fixture's own `git init`/`commit`/
        `rev-parse` too, so the commit lands in the leaked repo and the check
        finds it there — the WARN still fires. The real mechanism is in
        `build()`: when HEAD's 7-char prefix is pure digits ((10/16)^7 ≈ 3.7%
        of commits; measured 6-in-160 against the unfixed fixture), the
        check's PID filter drops the LIVE cite, the collected list collapses
        to `beefca7` alone, and the all-missing branch reports "wrong tree"
        at OK — the WARN-filtered view then reads as a decline. The failure
        row says so: `all 1 cited commit(s) are missing`.

        The production line is `build()`'s live-sha selection. Break the
        re-roll and this class flakes at the measured rate; the assertion in
        `build()` is the guard, and this test exists so the mechanism is
        written down where the next reader will look for it.
        """
        t, live = self.build(tmp_path, self.LEDGER)
        assert re.search(r"[a-f]", live), (
            "a pure-digit LIVE prefix is filtered as a PID and collapses the "
            "collected list to one sha: %r" % live)
        # And the discriminating case the class exists for still holds: the
        # live cite is collected and resolves, so a dead neighbour WARNs.
        ledger = self.LEDGER.replace(
            "landed `LIVE`", "landed `LIVE` and also merged `beefca7`")
        t, live = self.build(tmp_path, ledger)
        warns = self.rows(t, lint.WARN)
        assert len(warns) == 1 and "beefca7" in warns[0], warns

    def test_the_check_is_registered_in_run_checks(self):
        """Every row above comes through `run_checks`, which is the single list
        `main()` also calls — so a check absent from it cannot be tested at all.
        This asserts the wiring directly rather than trusting that."""
        import inspect
        src = inspect.getsource(lint.run_checks)
        assert "check_cited_shas(dw, rep)" in src


class TestRelatedMarkers:
    """#353: `related:` makes "these two are one piece of work" explicit.

    The ledger has carried this relation implicitly for a year by writing two
    ids in one title — `- **#250/#251**`. #346's store cannot hold that, since
    `task(id PRIMARY KEY)` is one row per id, and his 01:23 ruling asked for the
    relation to become explicit rather than inferred from a slash. Splitting
    those entries without a marker would destroy the only record of the pairing.

    The reciprocity case below is the one that matters. SQLite gets `CHECK (a <
    b)` so the pair exists ONCE and cannot disagree with itself; prose has to
    duplicate it, because an entry is read alone. This check is the only thing
    standing between duplication and two halves that contradict each other.
    """

    def build(self, tmp_path, ledger):
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "tasks.md").write_text(ledger)
        return t

    def rows(self, t, level=None):
        rep = lint.Report()
        lint.check_related_markers(t / ".dreamwork", lint.load_watch(), rep)
        return [d for lvl, w, d in rep.rows
                if w == "tasks.md" and (level is None or lvl == level)]

    LEDGER = """# Tasks

Next id: **9**

## Open

- **#1** — a task · P2 · origin: **loop** · related: **#2** · still going
- **#2** — its other half · P2 · origin: **loop** · related: **#1** · going too
- **#3** — unrelated to anything · P2 · origin: **loop** · alone
"""

    def test_a_reciprocal_pair_is_clean_and_counted_once(self, tmp_path):
        t = self.build(tmp_path, self.LEDGER)
        errs = self.rows(t, lint.ERROR)
        assert errs == [], errs
        oks = self.rows(t, lint.OK)
        # Counted ONCE, not twice: the relation is symmetric, and a count of 2
        # would mean the check is thinking in rows rather than in pairs.
        assert len(oks) == 1 and "1 related pair(s)" in oks[0], oks
        # Coverage number (#395): unparseable count is always named so a silent
        # skip cannot hide — 0 here, because the fixture is well-formed.
        assert "0 entries unparseable" in oks[0], oks

    def test_a_one_sided_relation_errors(self, tmp_path):
        # Precondition, derived rather than assumed: the ledger this starts from
        # must be clean, or "it errors now" proves nothing about the edit.
        assert self.rows(self.build(tmp_path, self.LEDGER), lint.ERROR) == []
        t = self.build(tmp_path, self.LEDGER.replace(
            "origin: **loop** · related: **#1** · going too", "origin: **loop** · going too"))
        errs = self.rows(t, lint.ERROR)
        assert len(errs) == 1, errs
        assert "#1 is related to #2" in errs[0] and "does not say so back" in errs[0]

    def test_a_relation_naming_a_missing_id_errors(self, tmp_path):
        t = self.build(tmp_path, self.LEDGER.replace("related: **#2**", "related: **#77**"))
        errs = self.rows(t, lint.ERROR)
        # Two distinct faults, and both are real: #77 does not exist, AND #2's
        # own marker is now one-sided. Asserting only the first would let the
        # reciprocity pass go missing.
        assert any("#77" in e and "not an id in the ledger" in e for e in errs), errs
        assert any("does not say so back" in e for e in errs), errs

    def test_an_entry_related_to_itself_errors(self, tmp_path):
        t = self.build(tmp_path, self.LEDGER.replace("related: **#2**", "related: **#1**"))
        errs = self.rows(t, lint.ERROR)
        assert any("names ITSELF" in e for e in errs), errs

    def test_two_markers_on_one_entry_error(self, tmp_path):
        t = self.build(tmp_path, self.LEDGER.replace(
            "related: **#2** · still going", "related: **#2** · related: **#3** · still going"))
        errs = self.rows(t, lint.ERROR)
        assert any("has 2 `related:` markers" in e for e in errs), errs

    def test_the_wrong_case_errors_rather_than_reading_as_prose(self, tmp_path):
        t = self.build(tmp_path, self.LEDGER.replace("related: **#2**", "Related: **#2**"))
        errs = self.rows(t, lint.ERROR)
        assert any("wrong case" in e for e in errs), errs

    def test_a_hard_wrapped_marker_is_still_read(self, tmp_path):
        # The loop writes at ~72 columns, so the marker wraps in real entries.
        # An entry-local join is what makes that legal; without it this pair
        # reads as one-sided and the check fires on correct data.
        wrapped = self.LEDGER.replace(
            "origin: **loop** · related: **#2** · still going",
            "origin: **loop** · related:\n  **#2** · still going")
        assert "related:\n" in wrapped        # precondition: the wrap is really there
        t = self.build(tmp_path, wrapped)
        assert self.rows(t, lint.ERROR) == [], self.rows(t, lint.ERROR)

    def test_a_cross_reference_in_prose_is_not_a_marker(self, tmp_path):
        # Two shapes, and the FIRST is the one with a narrow production line.
        # #1 already has a marker, so its prose ids can only be counted by a
        # loose extraction — which is `found[0]` vs `flat` at the `named =` line,
        # and nothing else in the check. #3 has no marker at all, so its prose is
        # gated out earlier; that half is enforced by the marker-existence gate
        # and cannot be broken without breaking most of this class with it.
        t = self.build(tmp_path, self.LEDGER
            .replace("· still going", "· blocked on #3, superseded by #7")
            .replace("· alone", "· blocked on #1 and see #2 for the other half"))
        errs = self.rows(t, lint.ERROR)
        assert errs == [], errs
        # Precondition: the prose ids really are in the marked entry's text, or
        # this passes for want of anything to notice.
        assert "#7" in (t / ".dreamwork" / "tasks.md").read_text()

    def test_a_marker_naming_no_id_errors(self, tmp_path):
        t = self.build(tmp_path, self.LEDGER.replace("related: **#2**", "related: **soon**"))
        errs = self.rows(t, lint.ERROR)
        assert any("naming no id" in e for e in errs), errs

    def test_a_ledger_with_no_markers_reports_what_it_examined(self, tmp_path):
        # #685: a clean no-marker ledger must REPORT that it examined N entries,
        # not fall silent. Silence is the failure mode the #294 dispatch fixes —
        # a check that examined zero entries read as a pass. This was
        # `..._says_nothing_at_all`; the brief ruled that "says nothing" is the
        # anti-pattern, so it now binds the examined-count report (#671's shape).
        # This is the live ledger's state today (zero `related:` markers), which
        # is why the check can be strict: there is no legacy to grandfather.
        bare = self.LEDGER.replace(" · related: **#2**", "").replace(" · related: **#1**", "")
        assert "related:" not in bare        # precondition: really stripped
        t = self.build(tmp_path, bare)
        assert self.rows(t, lint.ERROR) == [], self.rows(t, lint.ERROR)
        oks = self.rows(t, lint.OK)
        # Derived at runtime: the fixture genuinely has this many entries and
        # no markers, so the count is the check's honest answer, not a literal.
        import watch
        n = len(watch.ledger_entries(bare))
        assert n > 0, "precondition: the bare fixture genuinely has entries"
        assert len(oks) == 1, oks
        assert f"examined {n} entries against 0 markers" in oks[0], oks

    def test_the_check_is_registered_in_run_checks(self, tmp_path):
        import inspect
        src = inspect.getsource(lint.run_checks)
        assert "check_related_markers(dw, watch, rep)" in src

    def test_the_summary_never_claims_reciprocity_alongside_an_error(self, tmp_path):
        """Found by the FIRST live red-proof, not by the fixtures above.

        Stripping #251's real marker made lint print `3 related pair(s), all
        reciprocal` in the same run as `#250 ... does not say so back`. Every
        fixture here asserted errors OR the OK line, never both in one run, so
        the contradiction was invisible to all of them.
        """
        t = self.build(tmp_path, self.LEDGER.replace(
            "origin: **loop** · related: **#1** · going too", "origin: **loop** · going too"))
        rows = self.rows(t)
        assert any("does not say so back" in d for d in rows), rows
        # Precondition: a marker really does survive, so `claims` is non-empty and
        # the summary line is genuinely reachable — otherwise this passes vacuously.
        assert "related: **#2**" in (t / ".dreamwork" / "tasks.md").read_text()
        assert not any("all reciprocal" in d for d in rows), rows

    def test_an_unbolded_relation_marker_is_flagged_not_skipped(self, tmp_path):
        """#395: missing bold used to hit `if not found: continue` in silence.

        Production line that must change for this to fail: the branch that
        ERRORS when RELATED_FIELD matches and RELATED_MARKER does not — restore
        a bare `if not found: continue` and this goes green wrongly.
        """
        unbolded = self.LEDGER.replace("related: **#2**", "related: #2")
        # Precondition, runtime: RELATED_MARKER genuinely does not match the
        # unbolded field — a fixture the bold regex still accepted would prove
        # nothing about the silent-skip hole.
        entry_line = next(ln for ln in unbolded.splitlines() if "related: #2" in ln)
        assert lint.RELATED_FIELD.search(entry_line), entry_line
        assert not lint.RELATED_MARKER.search(entry_line), entry_line
        t = self.build(tmp_path, unbolded)
        errs = self.rows(t, lint.ERROR)
        assert any("unparseable" in e and "#1" in e for e in errs), errs
        # Shape named, not a reciprocity symptom about a claim we never saw.
        assert any("unparseable" in e for e in errs), errs

    def test_a_correctly_bolded_marker_still_passes(self, tmp_path):
        """Neighbour of the unbolded case: the required form stays quiet."""
        t = self.build(tmp_path, self.LEDGER)
        assert self.rows(t, lint.ERROR) == [], self.rows(t, lint.ERROR)
        oks = self.rows(t, lint.OK)
        assert any("1 related pair(s)" in o and "0 entries unparseable" in o
                   for o in oks), oks

    def test_two_adjacent_bold_spans_are_flagged_rather_than_silently_truncated(
            self, tmp_path):
        """#395 trap 2: `**#393**, **#394**` used to keep only the first id.

        Production line: RELATED_ADJACENT_SPANS branch — accept adjacent spans
        as one marker (or drop the branch) and this fails by going quiet or by
        reciprocating on a truncated set.
        """
        # Give #3 a reciprocal link to #1 so a truncated parse (only #2 kept)
        # would look reciprocal on the first id alone — the shape error must
        # still fire rather than a reciprocity complaint about the drop.
        ledger = """# Tasks

Next id: **9**

## Open

- **#1** — multi · P2 · origin: **loop** · related: **#2**, **#3** · still going
- **#2** — half a · P2 · origin: **loop** · related: **#1** · going too
- **#3** — half b · P2 · origin: **loop** · related: **#1** · alone
"""
        # Precondition: RELATED_MARKER captures only the first span's interior
        # on the multi-id entry (the silent truncation #395 names).
        multi_line = next(ln for ln in ledger.splitlines() if "related: **#2**, **#3**" in ln)
        captured = lint.RELATED_MARKER.findall(multi_line)
        assert captured == ["#2"], captured
        assert lint.RELATED_ADJACENT_SPANS.search(multi_line)
        t = self.build(tmp_path, ledger)
        errs = self.rows(t, lint.ERROR)
        assert any("adjacent bold spans" in e for e in errs), errs

    def test_the_marker_vocabulary_in_prose_does_not_manufacture_a_marker(
            self, tmp_path):
        """#395 trap 3: mid-sentence `related: **…**` is not a field claim.

        Production line: field anchoring on RELATED_MARKER / RELATED_FIELD —
        remove `(?:^|[·])\\s*` and this fails (phantom marker from prose).
        """
        # Mid-sentence full form, deliberately NOT on a ·-field boundary.
        # Unanchored matching would treat related: **#9** as a real claim.
        prose = self.LEDGER.replace(
            "· alone",
            "· the required form is related: **#9** mid-sentence and must not "
            "count as a claim · alone")
        unanchored = re.compile(r"related:\s*\*\*([^*]*?)\*\*", re.I)
        poisoned = next(ln for ln in prose.splitlines() if "mid-sentence" in ln)
        # Precondition: unanchored WOULD manufacture a phantom; anchored must not.
        assert unanchored.findall(poisoned) == ["#9"], poisoned
        assert not lint.RELATED_MARKER.findall(poisoned), \
            "anchored matcher must not see a mid-sentence phantom"
        assert not lint.RELATED_FIELD.search(
            poisoned.replace("related: **#9**", "X")
        ) or not lint.RELATED_FIELD.search(
            re.sub(r".*?(related: \*\*#9\*\*)", r"\1", poisoned)
        )
        # Field anchor: `related:` is preceded by words, not only whitespace after ·.
        assert not re.search(r"(?:^|[·])\s*related:\s*\*\*#9\*\*", poisoned)
        t = self.build(tmp_path, prose)
        errs = self.rows(t, lint.ERROR)
        assert errs == [], errs
        oks = self.rows(t, lint.OK)
        assert any("1 related pair(s)" in o for o in oks), oks

    def test_it_flags_the_unbolded_markers_in_the_actual_revision_that_hid_them(
            self, tmp_path):
        """The real case, not a fixture: `tasks.md` at `660a294^` (= 8d70486).

        Model: check_placeholder_citations proved against 4ce04e0 for #362.
        Three unbolded markers hid four broken relations (#388→#383, #388→#386,
        #387→#361, #386→#383). A check tuned only to today's repaired tree is
        hollow — this is the criterion that makes it a check.
        """
        import subprocess
        repo = Path(lint.__file__).parent
        got = subprocess.run(
            ["git", "-C", str(repo), "show", "660a294^:.dreamwork/tasks.md"],
            capture_output=True, text=True)
        if got.returncode != 0:
            pytest.skip("history not present (zip install); fixtures still cover it")
        blob = got.stdout
        # Precondition: the historical unbolded forms are still in that blob.
        assert "related: #383, #386" in blob, \
            "historical unbolded #388 marker gone — this test no longer proves anything"
        assert "related: #361" in blob, \
            "historical unbolded #387 marker gone — this test no longer proves anything"
        # Third unbolded is #386 → #383 (landed section); count unbolded fields.
        unbolded_hits = re.findall(r"related: #\d+", blob)
        assert len(unbolded_hits) >= 3, unbolded_hits
        # RELATED_MARKER must not match those unbolded fields (the hole).
        for hit in ("related: #383, #386", "related: #361"):
            assert not lint.RELATED_MARKER.search(hit), hit
            assert lint.RELATED_FIELD.search("· " + hit)
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "tasks.md").write_text(blob)
        rep = lint.Report()
        lint.check_related_markers(dw, lint.load_watch(), rep)
        errs = [d for lvl, w, d in rep.rows
                if lvl == lint.ERROR and w == "tasks.md"]
        # Must name the three entries that carried unbolded markers.
        named = " ".join(errs)
        for eid in ("#388", "#387", "#386"):
            assert eid in named, (eid, errs)
        assert sum(1 for e in errs if "unparseable" in e) >= 3, errs


class TestStatusAgreesWithLedger:
    """#362: the two halves of one fact, measured drifted the day it was written.

    `status.json` states queue depth and what is in flight; `tasks.md` IS queue
    depth and what is in flight. Both were wrong at once on 2026-07-28: `queue`
    summed to 115 against 123 open entries, and `current_task_ids` was `[]` while
    three agents named their task ids. Nothing compared either pair, so eight
    tasks of drift accumulated across one night of hand-maintained edits.

    WARN, not ERROR, and the distinction is the design: `status.json` is a
    best-effort projection of a live process, and the loop is told that failing to
    write it must never block. A momentary lag mid-increment is truthful. Drift
    nobody measures is not.
    """

    def build(self, tmp_path, ledger_open, **status):
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        entries = "\n".join(
            f"- **#{i}** — task {i} · P2 · origin: **loop** · going" for i in range(1, ledger_open + 1))
        (dw / "tasks.md").write_text(
            f"# Tasks\n\nNext id: **{ledger_open + 1}**\n\n## Open\n\n{entries}\n")
        (dw / "status.json").write_text(json.dumps(status))
        # Precondition: the ledger really parses to the count this test reasons
        # about. A fixture that hand-counts its own entries proves nothing about
        # the reader the check uses.
        import watch as _w
        got, _ = lint.load_watch().parse_ledger((dw / "tasks.md").read_text())
        assert len(got) == ledger_open, (len(got), ledger_open)
        return t

    def rows(self, t):
        rep = lint.Report()
        lint.check_status_agrees_with_ledger(t / ".dreamwork", lint.load_watch(), rep)
        return [(lvl, d) for lvl, w, d in rep.rows if w == "status.json"]

    def test_a_queue_that_agrees_says_nothing(self, tmp_path):
        t = self.build(tmp_path, 5, queue={"in_progress": 2, "pending": 3},
                       current_task_ids=[1, 2],
                       agents=[{"name": "a", "task_ids": [1, 2]}])
        assert self.rows(t) == [], self.rows(t)

    def test_a_queue_that_disagrees_warns_with_the_signed_gap(self, tmp_path):
        t = self.build(tmp_path, 12, queue={"in_progress": 1, "pending": 3})
        rows = self.rows(t)
        assert len(rows) == 1, rows
        lvl, d = rows[0]
        # WARN, never ERROR: a projection lagging mid-increment is truthful.
        assert lvl == lint.WARN, rows
        assert "sums to 4" in d and "123" not in d and "12 open" in d
        # The signed gap is the useful part — direction says which side is behind.
        assert "-8" in d, d

    def test_an_empty_current_while_agents_claim_ids_warns(self, tmp_path):
        t = self.build(tmp_path, 4, queue={"in_progress": 0, "pending": 4},
                       current_task_ids=[],
                       agents=[{"name": "a", "task_ids": [7]}, {"name": "b", "task_ids": [9]}])
        rows = self.rows(t)
        # The queue agrees here, so this must be the ONLY row — otherwise the two
        # faults are not separable and neither message means anything on its own.
        assert len(rows) == 1, rows
        assert "current_task_ids is empty" in rows[0][1] and "[7, 9]" in rows[0][1]

    def test_an_empty_current_with_no_agents_is_silent(self, tmp_path):
        # An idle loop truthfully claims nothing and owns nothing.
        t = self.build(tmp_path, 4, queue={"in_progress": 0, "pending": 4},
                       current_task_ids=[], agents=[])
        assert self.rows(t) == [], self.rows(t)

    def test_an_absent_field_is_not_adopted_rather_than_wrong(self, tmp_path):
        t = self.build(tmp_path, 4, agents=[{"name": "a", "task_ids": [1]}])
        assert self.rows(t) == [], self.rows(t)

    def test_a_non_integer_queue_value_is_left_to_check_status(self, tmp_path):
        # `check_status` owns type complaints. The guard is not crash-avoidance —
        # `counts` already filters to ints — it is against comparing a PARTIAL sum
        # to the full ledger, which would report a confident wrong gap on a file
        # whose real fault is a type error somebody else is already reporting.
        t = self.build(tmp_path, 9, queue={"in_progress": "two", "pending": 3})
        assert self.rows(t) == [], self.rows(t)

    def test_a_missing_tasks_md_is_silent(self, tmp_path):
        t = self.build(tmp_path, 3, queue={"in_progress": 9, "pending": 9})
        (t / ".dreamwork" / "tasks.md").unlink()
        assert self.rows(t) == [], self.rows(t)

    def test_the_check_is_registered_in_run_checks(self, tmp_path):
        import inspect
        src = inspect.getsource(lint.run_checks)
        assert "check_status_agrees_with_ledger(dw, watch, rep)" in src


class TestUnfoldedAnswers:
    """#366: an answer sitting in the section reserved for the unanswered.

    His #346 ruling arrived at 01:23 and was folded at 02:27 — for that hour the
    dashboard presented a settled question beside three genuinely open ones.
    Nothing could have caught it: `check_questions` verifies the file parses and
    `check_author_tags` verifies a tag is readable, and both were clean.

    **The first version of this check produced a GREEN RED-RUN** on the real
    pre-fold file, which is why the production code scans the raw section rather
    than the parsed entries: #340 makes an answer bullet under `## Open` a
    CONTRIBUTION, so the raw tag is stripped and a parsed contribution cannot say
    whether it was an answer or a note. The reader hides the one fact this needs.
    """

    def build(self, tmp_path, questions):
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "questions.md").write_text(questions)
        return t

    def rows(self, t):
        rep = lint.Report()
        lint.check_unfolded_answers(t / ".dreamwork", lint.load_watch(), rep)
        return [d for lvl, w, d in rep.rows if w == "questions.md"]

    def q(self, *, bullets, stamp="2026-07-28 01:23"):
        # The REAL tag shape: `- **Answer (via watch, 2026-07-28 01:23):**`.
        # A first draft wrote `(via watch (2026-…)` — a doubled paren that the
        # prefix match still accepted, so every test passed over a fixture that
        # did not look like the file.
        body = "".join(
            f"  - **{b}, {stamp}):** something he said\n" for b in bullets)
        return (
            "# Questions\n\n## Open\n"
            "- **P1 · 2026-07-28 — a question that is genuinely open?** prose here.\n"
            "  - **Note (human, via watch, 2026-07-28 01:00):** a steer, not an answer\n"
            "- **P1 · 2026-07-28 — a question he has already answered?** prose here.\n"
            + body +
            "\n## Answered\n\n"
            "- **P1 · 2026-07-27 — an old one?**\n"
            "  → answered (2026-07-27 10:00): done.\n"
            "  - **Answer (via watch, 2026-07-27 10:00):** his words\n")

    def test_an_answer_under_open_warns_and_names_the_entry(self, tmp_path):
        t = self.build(tmp_path, self.q(bullets=["Answer (via watch"]))
        rows = self.rows(t)
        assert len(rows) == 1, rows
        assert "already answered" in rows[0] and "carries his answer" in rows[0]
        # DISCRIMINATION: the genuinely-open entry above it, and the correctly
        # folded one in `## Answered`, must both stay silent — otherwise the check
        # is reporting the file rather than the fault.
        assert "genuinely open" not in rows[0], rows[0]
        assert "an old one" not in rows[0], rows[0]

    def test_a_note_is_not_an_answer(self, tmp_path):
        t = self.build(tmp_path, self.q(bullets=["Note (human, via watch"]))
        assert self.rows(t) == [], self.rows(t)

    def test_two_answers_with_one_stamp_report_the_duplicate_too(self, tmp_path):
        t = self.build(tmp_path, self.q(bullets=["Answer (via watch", "Answer (via watch"]))
        rows = self.rows(t)
        assert len(rows) == 2, rows
        assert any("2 answer bullets stamped 2026-07-28 01:23" in d for d in rows), rows
        assert any("#274" in d for d in rows), rows

    def test_two_answers_at_different_times_are_not_a_duplicate(self, tmp_path):
        # A follow-up answer on the same entry is legitimate; only an identical
        # stamp is the double-delivery signature.
        text = self.q(bullets=["Answer (via watch"]).replace(
            "\n## Answered",
            "  - **Answer (via watch, 2026-07-28 01:44):** and one more thing\n\n## Answered")
        assert text.count("Answer (via watch, 2026-07-28") == 2, text.count("Answer (via watch, 2026-07-28")
        t = self.build(tmp_path, text)
        rows = self.rows(t)
        assert len(rows) == 1 and "duplicate" not in rows[0], rows

    def test_the_age_is_computed_from_the_bullet_not_pinned(self, tmp_path):
        from datetime import datetime, timedelta
        recent = (datetime.now() - timedelta(minutes=7)).strftime("%Y-%m-%d %H:%M")
        t = self.build(tmp_path, self.q(bullets=["Answer (via watch"], stamp=recent))
        rows = self.rows(t)
        assert len(rows) == 1, rows
        # Derived at runtime: a fresh answer reads in minutes, and the hours
        # wording must NOT appear — that is what separates the legitimate
        # fold-on-the-next-tick window from the hour-long failure.
        assert "minutes ago" in rows[0] and "hours ago" not in rows[0], rows[0]

    def test_an_unstamped_answer_bullet_still_warns(self, tmp_path):
        text = self.q(bullets=["Answer (via watch"]).replace(
            "Answer (via watch, 2026-07-28 01:23):", "Answer (via watch):")
        assert "2026-07-28 01:23" not in text        # precondition: really unstamped
        t = self.build(tmp_path, text)
        rows = self.rows(t)
        assert len(rows) == 1 and "ago" not in rows[0], rows

    def test_only_the_open_section_is_scanned(self, tmp_path):
        # The `## Answered` fixture entry carries an answer bullet by definition.
        # If the section boundary were ignored, every answered entry would warn.
        t = self.build(tmp_path, self.q(bullets=["Note (human, via watch"]))
        assert "Answer (via watch, 2026-07-27 10:00)" in \
            (t / ".dreamwork" / "questions.md").read_text()
        assert self.rows(t) == [], self.rows(t)

    def test_the_check_is_registered_in_run_checks(self, tmp_path):
        import inspect
        assert "check_unfolded_answers(dw, watch, rep)" in inspect.getsource(lint.run_checks)


class TestGuardsRegistered:
    """#377 — a guard that exists and is not in `DEFAULT_GUARDS` gates nothing.

    This is #117's failure mode and it has now happened four times: `filehead`
    and `fileview` were built with named red proofs and left unregistered on
    purpose ("one line, still not mine"), and `fileimg` (#336) and `qfade`
    (#326) had been sitting outside the list since they were written. All four
    pass when invoked by hand, which is exactly why nobody noticed: the
    evidence of a working guard and the evidence of a RUNNING guard look
    identical in a report.

    The check deliberately does NOT try to classify. Eleven other `.mjs` files
    in that directory are captures, one-off traces and one shared helper, and a
    checker that guessed which is which would either declare a real guard
    non-load-bearing or nag forever. It reports the gap and names the list to
    edit; a human decides.
    """

    def test_this_repo_has_every_guard_registered(self):
        rep = lint.Report()
        lint.check_guards_registered(lint.SKILL_DIR, rep)
        levels_seen = levels(rep, "justfile")
        assert lint.WARN not in levels_seen, rep.render()

    def test_an_unregistered_guard_warns_and_names_it(self, tmp_path):
        (tmp_path / "dev" / "capture").mkdir(parents=True)
        (tmp_path / "justfile").write_text(
            'guards port="1":\n    DEFAULT_GUARDS="alpha"\n', encoding="utf-8")
        for name in ("alpha", "orphan"):
            (tmp_path / "dev" / "capture" / f"{name}.mjs").write_text("//\n",
                                                                     encoding="utf-8")
        rep = lint.Report()
        lint.check_guards_registered(tmp_path, rep)
        assert lint.WARN in levels(rep, "justfile"), rep.render()
        detail = next(d for lvl, w, d in rep.rows
                      if w == "justfile" and lvl == lint.WARN)
        assert "orphan" in detail, detail
        assert "alpha" not in detail, "a registered guard must not be reported"
        assert "DEFAULT_GUARDS" in detail, "must name the list to edit"

    def test_the_known_non_guards_are_not_reported(self, tmp_path):
        (tmp_path / "dev" / "capture").mkdir(parents=True)
        (tmp_path / "justfile").write_text(
            'guards port="1":\n    DEFAULT_GUARDS="alpha"\n', encoding="utf-8")
        (tmp_path / "dev" / "capture" / "alpha.mjs").write_text("//\n",
                                                               encoding="utf-8")
        # `report.mjs` is the shared exit-handler helper every guard imports.
        # If it were reported, the check would nag on every run forever, which
        # is how a warning stops being read.
        (tmp_path / "dev" / "capture" / "report.mjs").write_text("//\n",
                                                                encoding="utf-8")
        rep = lint.Report()
        lint.check_guards_registered(tmp_path, rep)
        assert lint.WARN not in levels(rep, "justfile"), rep.render()

    def test_a_registered_name_with_no_file_is_reported(self, tmp_path):
        (tmp_path / "dev" / "capture").mkdir(parents=True)
        (tmp_path / "justfile").write_text(
            'guards port="1":\n    DEFAULT_GUARDS="alpha ghost"\n', encoding="utf-8")
        (tmp_path / "dev" / "capture" / "alpha.mjs").write_text("//\n",
                                                               encoding="utf-8")
        rep = lint.Report()
        lint.check_guards_registered(tmp_path, rep)
        assert lint.WARN in levels(rep, "justfile"), rep.render()
        detail = " ".join(d for lvl, w, d in rep.rows
                          if w == "justfile" and lvl == lint.WARN)
        assert "ghost" in detail, detail

    def test_a_target_without_a_justfile_is_silent(self, tmp_path):
        rep = lint.Report()
        lint.check_guards_registered(tmp_path, rep)
        assert levels(rep, "justfile") == [], rep.render()

    def test_the_count_it_reports_is_derived(self, tmp_path):
        # The OK summary must count what it found, not restate a literal that
        # was true the day it was written.
        (tmp_path / "dev" / "capture").mkdir(parents=True)
        names = ("alpha", "beta", "gamma")
        (tmp_path / "justfile").write_text(
            f'guards port="1":\n    DEFAULT_GUARDS="{" ".join(names)}"\n',
            encoding="utf-8")
        for name in names:
            (tmp_path / "dev" / "capture" / f"{name}.mjs").write_text("//\n",
                                                                     encoding="utf-8")
        rep = lint.Report()
        lint.check_guards_registered(tmp_path, rep)
        detail = next(d for lvl, w, d in rep.rows
                      if w == "justfile" and lvl == lint.OK)
        assert str(len(names)) in detail, detail


class TestRanAndJudged:
    """#471 — "executed" must mean ran AND judged, not "the recipe printed a line".

    A guard that died before its first assertion still earned a recipe-level
    FAIL line, and that is what hid #471 for 3.5h. The signal that it did NOT
    judge is the crash sentinel — the reporter's marker for did-not-finish —
    which is explicitly NOT a verdict.

    Production line named (what must change for these to fail): the
    sentinel-exclusion in `lint.ran_and_judged` (`if m.group(0) !=
    _CRASH_SENTINEL`). Delete that guard and a sentinel-only log reads as
    judged — the exact misread #471 survived on.
    """

    def test_a_genuine_pass_verdict_is_judged(self):
        assert lint.ran_and_judged("----\nPASS a real check\n") is True

    def test_a_genuine_fail_verdict_is_also_judged(self):
        # A guard that ran, judged, and FOUND a failure did execute; its FAIL
        # is a verdict, not a death. The recipe's per-guard FAIL line could
        # not tell these apart — the crux the brief names.
        assert lint.ran_and_judged("----\nFAIL a real failure\n") is True

    def test_the_crash_sentinel_alone_is_not_judged(self):
        log = ("Error: serve: :39899 is serving /x, not /y\n"
               "[coverage] NONE DECLARED\n"
               "----\n"
               + lint._CRASH_SENTINEL + "\n")
        assert lint.ran_and_judged(log) is False

    def test_an_error_stack_with_no_verdicts_is_not_judged(self):
        assert lint.ran_and_judged("") is False
        assert lint.ran_and_judged(
            "Error: serve: :39899 never answered\n    at f (...)\n") is False

    def test_a_guard_that_judged_then_crashed_is_judged(self):
        # The line between "ran and judged" and "died before judging": a guard
        # that reached ok() at least once judged, even if it threw afterwards.
        assert lint.ran_and_judged(
            "PASS judged first\n" + lint._CRASH_SENTINEL + "\n") is True


class TestGuardExecutionCLI:
    """#471 — `lint.py guard-execution` compares executed vs requested and
    fails when a registered guard did not run-and-judge.

    This is the red-proof by synthetic run record (the brief's sanctioned
    alternative to editing a real guard file, which is not ours): a guard log
    in the exact #471 shape (died before judging) is placed among judged
    guards, and the REAL CLI — which reads the file and calls the REAL
    `ran_and_judged` — must name it and exit non-zero. There is no hand-built
    classification standing in front of the decision; the injection reaches
    the production line.
    """

    JUDGED = "----\nPASS a\nPASS b\n"
    JUDGED_FAIL = "----\nFAIL a real failure\n"
    DIED_471 = ("Error: serve: :39899 is serving /x, not /died/y\n"
                "[coverage] NONE DECLARED\n----\n"
                + lint._CRASH_SENTINEL + "\n")

    @staticmethod
    def _logs(out: Path, **name_text):
        out.mkdir(parents=True, exist_ok=True)
        for name, text in name_text.items():
            (out / f"{name}.log").write_text(text)

    def test_all_judged_is_green_with_both_counts(self, tmp_path, capsys):
        out = tmp_path / "OUT"
        self._logs(out, good1=self.JUDGED, good2=self.JUDGED_FAIL)
        rc = lint.main(["guard-execution", str(out), "good1", "good2"])
        captured = capsys.readouterr().out
        assert rc == 0, captured
        assert "OK" in captured
        # Both counts on the row — a single number cannot show a gap, and the
        # row that hid this bug ("N registered") carried exactly one.
        assert "2 of 2" in captured, captured

    def test_a_471_shape_guard_is_named_and_fails(self, tmp_path, capsys):
        out = tmp_path / "OUT"
        self._logs(out, good1=self.JUDGED, died471=self.DIED_471)
        # Runtime precondition: the fixture must contain BOTH a judged guard
        # and a not-judged one, or the assertion proves nothing (a fixture of
        # all-not-judged would pass a broken "always fail" check). Derived via
        # the real classifier, not assumed.
        verdicts = {g: lint.ran_and_judged((out / f"{g}.log").read_text())
                    for g in ("good1", "died471")}
        assert any(verdicts.values()) and not all(verdicts.values()), verdicts
        rc = lint.main(["guard-execution", str(out), "good1", "died471"])
        captured = capsys.readouterr().out
        assert rc == 1, captured
        assert "FAIL" in captured
        assert "died471" in captured, "the not-judged guard must be named"
        assert "good1" not in captured, "a judged guard must not be reported"
        assert "1 of 2" in captured, captured  # executed-of-registered

    def test_a_guard_with_no_log_did_not_run(self, tmp_path, capsys):
        out = tmp_path / "OUT"
        self._logs(out, good1=self.JUDGED)
        rc = lint.main(["guard-execution", str(out), "good1", "neverran"])
        captured = capsys.readouterr().out
        assert rc == 1, captured
        assert "neverran" in captured

    def test_zero_logs_read_is_a_vacuity_failure_not_a_pass(self, tmp_path, capsys):
        # A broken OUT (no logs) must not read as "everything ran" — that is
        # #471's failure mode inverted. Exit 2, never 0.
        rc = lint.main(["guard-execution", str(tmp_path / "nope"),
                        "good1", "good2"])
        err = capsys.readouterr().err
        assert rc == 2, err
        assert "0 logs" in err, err

    def test_the_cli_is_reachable_as_a_subprocess(self, tmp_path):
        # Proves the `__main__` dispatch wiring the recipe depends on, not just
        # main() called in-process: `python3 lint.py guard-execution ...`.
        out = tmp_path / "OUT"
        self._logs(out, good1=self.JUDGED)
        r = subprocess.run(
            [sys.executable, "lint.py", "guard-execution", str(out), "good1"],
            cwd=str(lint.SKILL_DIR), capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "1 of 1" in r.stdout, r.stdout


class TestGuardsExecutionAccounting:
    """#471 — lint cannot watch a run, but it can refuse to let the live
    execution-comparison be deleted from the recipe (the "became hollow"
    shape: a check that passed at birth and was later removed).

    Production line named: the `invoked`/`wired` regexes in
    `check_guards_execution_accounting`. Remove the `lint.py guard-execution`
    line — or its `|| fail=` wiring — from the recipe and this errors.
    """

    @staticmethod
    def _rep(tmp_path, body):
        (tmp_path / "justfile").write_text(body, encoding="utf-8")
        rep = lint.Report()
        lint.check_guards_execution_accounting(tmp_path, rep)
        return rep

    def test_this_repo_wires_the_comparison(self):
        rep = lint.Report()
        lint.check_guards_execution_accounting(lint.SKILL_DIR, rep)
        assert lint.ERROR not in levels(rep, "justfile"), rep.render()
        assert lint.OK in levels(rep, "justfile"), rep.render()

    def test_a_recipe_without_the_hook_is_an_error(self, tmp_path):
        body = ('guards port="1":\n'
                '    DEFAULT_GUARDS="alpha"\n'
                '    echo ran\n'
                '    exit 0\n')
        rep = self._rep(tmp_path, body)
        assert lint.ERROR in levels(rep, "justfile"), rep.render()
        detail = next(d for lvl, w, d in rep.rows
                      if w == "justfile" and lvl == lint.ERROR)
        assert "guard-execution" in detail, detail

    def test_a_hook_present_but_not_wired_to_fail_is_an_error(self, tmp_path):
        # Present yet toothless: it prints and can never red. That is the
        # deletion that matters — a comparison that cannot fail gates nothing.
        body = ('guards port="1":\n'
                '    DEFAULT_GUARDS="alpha"\n'
                '    python3 lint.py guard-execution "$OUT" $GUARDS\n'
                '    exit 0\n')
        rep = self._rep(tmp_path, body)
        assert lint.ERROR in levels(rep, "justfile"), rep.render()

    def test_a_wired_hook_is_ok(self, tmp_path):
        body = ('guards port="1":\n'
                '    DEFAULT_GUARDS="alpha"\n'
                '    python3 lint.py guard-execution "$OUT" $GUARDS || fail=1\n'
                '    exit $fail\n')
        rep = self._rep(tmp_path, body)
        assert lint.ERROR not in levels(rep, "justfile"), rep.render()
        assert lint.OK in levels(rep, "justfile"), rep.render()

    def test_a_target_without_a_justfile_is_silent(self, tmp_path):
        rep = lint.Report()
        lint.check_guards_execution_accounting(tmp_path, rep)
        assert levels(rep, "justfile") == [], rep.render()


class TestBriefCorpusReach:
    """#766: clean historical contents must not imply current coverage."""

    @staticmethod
    def _repo(tmp_path: Path, brief_names: list[str], subjects: list[str]) -> Path:
        root = tmp_path / "repo"
        briefs = root / ".dreamwork" / "docs" / "briefs"
        briefs.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email",
                        "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"],
                       check=True)
        for name in brief_names:
            (briefs / name).write_text("# Brief\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", subjects[0]],
                       check=True)
        for subject in subjects[1:]:
            subprocess.run(["git", "-C", str(root), "commit", "--allow-empty",
                            "-qm", subject], check=True)
        return root

    def test_an_id_current_corpus_is_quiet(self, tmp_path):
        root = self._repo(tmp_path, ["100-current.md"], ["docs(#100): current"])
        reach = lint.brief_corpus_reach(root)
        assert reach == (
            "current through task #100 (0-id gap; "
            "0 unnumbered brief(s) cannot be ordered)")

    def test_a_frozen_nonempty_corpus_says_historical_from_the_line_alone(
            self, tmp_path):
        root = self._repo(
            tmp_path,
            ["100-old.md", "not-numbered.md"],
            ["docs(#100): old brief", "fix(#107): later work"],
        )
        reach = lint.brief_corpus_reach(root)
        assert "HISTORICAL ONLY" in reach
        assert "newest numbered brief #100" in reach
        assert "task history reaches #107 (7-id gap" in reach
        assert "1 unnumbered brief(s) cannot be ordered" in reach

    def test_matching_max_ids_is_the_open_completeness_false_green(
            self, tmp_path):
        root = self._repo(
            tmp_path,
            ["100-first.md", "102-last.md"],
            ["docs(#100): first", "fix(#101): no brief", "fix(#102): last"],
        )
        # The reach signal orders the maxima; it cannot prove one brief per
        # dispatch or notice the deliberately absent #101 artifact.
        assert lint.brief_corpus_reach(root).startswith("current through task #102")

    def test_unorderable_population_is_unknown_not_current(self, tmp_path):
        root = self._repo(
            tmp_path, ["descriptive-only.md"], ["fix(#107): later work"])
        reach = lint.brief_corpus_reach(root)
        assert reach.startswith("coverage reach UNKNOWN")
        assert "1 unnumbered brief(s) cannot be ordered" in reach

    def test_a_brief_ahead_of_landed_history_is_in_flight_not_unknown(
            self, tmp_path):
        root = self._repo(
            tmp_path, ["108-in-flight.md"], ["fix(#107): landed work"])
        reach = lint.brief_corpus_reach(root)
        assert reach.startswith("IN FLIGHT")
        assert "brief #108 is 1 id(s) ahead of landed task history #107" in reach
        assert "UNKNOWN" not in reach

    def test_all_four_checks_carry_the_same_reach_qualifier(self, frozen_tree):
        # HEAD is immutable for this assertion. The real dispatch route still
        # writes the main corpus; freezing the reader does not replace or fake
        # that route (#770), it only stops a unit test sampling two populations.
        root = frozen_tree
        expected = lint.brief_corpus_reach(root)
        checks = (
            lint.check_brief_handoff_obligation,
            lint.check_brief_worktree_abs_inbox,
            lint.check_brief_lane_scratch,
            lint.check_brief_lane_owns,
        )
        for check in checks:
            rep = lint.Report()
            check(root / ".dreamwork", rep)
            oks = [detail for level, what, detail in rep.rows
                   if level == lint.OK and what == "briefs"]
            assert len(oks) == 1, rep.render()
            assert oks[0].endswith(expected), oks[0]

    def test_a_mid_run_persistent_write_is_named_as_interference(
            self, tmp_path, monkeypatch):
        root = target(tmp_path)
        probe = root / ".dreamwork" / "docs" / "briefs" / "773-race.md"
        original = lint.check_brief_worktree_abs_inbox

        def mutate_between_brief_checks(dw, rep):
            probe.parent.mkdir(parents=True, exist_ok=True)
            probe.write_text("# persisted by a concurrent dispatch\n", encoding="utf-8")
            original(dw, rep)

        monkeypatch.setattr(lint, "check_brief_worktree_abs_inbox",
                            mutate_between_brief_checks)
        rep = run(root)
        findings = [detail for level, what, detail in rep.rows
                    if level == lint.ERROR and what == "brief corpus"]
        assert len(findings) == 1, (
            "missing CHANGED DURING LINT interference verdict\n" + rep.render())
        assert "CHANGED DURING LINT" in findings[0]
        assert "five brief-corpus checks" in findings[0]
        assert "not a merge verdict" in findings[0]

    def test_add_then_remove_between_samples_is_the_open_false_green(
            self, tmp_path, monkeypatch):
        root = target(tmp_path)
        probe = root / ".dreamwork" / "docs" / "briefs" / "773-transient.md"
        original = lint.check_brief_worktree_abs_inbox

        def mutate_and_restore_between_samples(dw, rep):
            probe.parent.mkdir(parents=True, exist_ok=True)
            probe.write_text("# transient\n", encoding="utf-8")
            probe.unlink()
            original(dw, rep)

        monkeypatch.setattr(lint, "check_brief_worktree_abs_inbox",
                            mutate_and_restore_between_samples)
        rep = run(root)
        assert not [detail for level, what, detail in rep.rows
                    if level == lint.ERROR and what == "brief corpus"], rep.render()


class TestBriefHandoffObligation:
    """#398: a brief written after the hand-off obligation must carry it.

    The obligation landed in SKILL.md (#394). A coordinator habit with no check
    decays silently; the thing that IS checkable is the brief — a committed file
    whose add-commit is resolvable. Cutoff is content-resolved, never pinned.

    Production lines named per test (what must change for it to fail):
    - flagged: the `if ".dreamwork/handoffs.md" not in text` branch in
      classify_brief_handoff_scope / the ERROR add in check_brief_handoff_obligation
    - grandfathered: the `if add_t <= cutoff_t` branch that skips pre-obligation
      briefs
    - cutoff content: resolve_handoff_obligation_cutoff + the phrase constant +
      the post-resolve "phrase in blob" guard that refuses a hollow no-cutoff
    """

    PHRASE = lint.HANDOFF_OBLIGATION_PHRASE

    def _git_repo(self, tmp_path):
        """A real git repo: the check reads real git log -S / --diff-filter=A."""
        import subprocess
        t = fresh(tmp_path)

        def git(*a, check=True):
            return subprocess.run(
                ["git", "-C", str(t), *a],
                capture_output=True, text=True, check=check)

        git("init", "-q")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        return t, git

    def test_a_brief_added_after_the_obligation_without_it_is_flagged(self, tmp_path):
        """Production line: the missing-mention ERROR in
        check_brief_handoff_obligation — a post-cutoff brief whose body lacks
        `.dreamwork/handoffs.md` must be named by basename.
        """
        import time
        t, git = self._git_repo(tmp_path)
        (t / "SKILL.md").write_text(
            f"# skill\n\n{self.PHRASE}\n", encoding="utf-8")
        git("add", "SKILL.md")
        git("commit", "-qm", "obligation lands")
        # Ensure the brief's commit is strictly newer than the cutoff (same
        # second is possible on a fast FS and would grandfather it).
        time.sleep(1.1)
        briefs = t / ".dreamwork" / "docs" / "briefs"
        briefs.mkdir(parents=True)
        (briefs / "999-no-handoff.md").write_text(
            "# Brief\n\nDo the work. No hand-off line required, wrongly.\n",
            encoding="utf-8")
        git("add", ".dreamwork/docs/briefs/999-no-handoff.md")
        git("commit", "-qm", "brief after obligation, missing mention")

        # Precondition, derived: the brief really is after the cutoff.
        scope = lint.classify_brief_handoff_scope(t)
        assert "999-no-handoff.md" in scope["in_scope"], scope
        assert "999-no-handoff.md" in scope["missing"], scope

        rep = lint.Report()
        lint.check_brief_handoff_obligation(t / ".dreamwork", rep)
        errors = [d for lvl, w, d in rep.rows
                  if lvl == lint.ERROR and w == "briefs"]
        assert len(errors) == 1, rep.render()
        assert "999-no-handoff.md" in errors[0], errors[0]
        assert ".dreamwork/handoffs.md" in errors[0], errors[0]

    def test_a_brief_added_before_the_obligation_is_grandfathered(self, tmp_path):
        """Production line: the `add_t <= cutoff_t` grandfather branch in
        classify_brief_handoff_scope — a pre-obligation brief without the
        mention must stay silent.
        """
        import time
        t, git = self._git_repo(tmp_path)
        briefs = t / ".dreamwork" / "docs" / "briefs"
        briefs.mkdir(parents=True)
        (briefs / "100-old.md").write_text(
            "# Brief\n\nPre-obligation, no handoffs path.\n", encoding="utf-8")
        # SKILL.md exists so the check runs, but without the phrase yet.
        (t / "SKILL.md").write_text("# skill\n\nno obligation yet\n",
                                    encoding="utf-8")
        git("add", "SKILL.md", ".dreamwork/docs/briefs/100-old.md")
        git("commit", "-qm", "brief before obligation")
        time.sleep(1.1)
        (t / "SKILL.md").write_text(
            f"# skill\n\n{self.PHRASE}\n", encoding="utf-8")
        git("add", "SKILL.md")
        git("commit", "-qm", "obligation lands later")

        scope = lint.classify_brief_handoff_scope(t)
        assert "100-old.md" in scope["grandfathered"], scope
        assert "100-old.md" not in scope["in_scope"], scope
        assert scope["missing"] == [], scope

        rep = lint.Report()
        lint.check_brief_handoff_obligation(t / ".dreamwork", rep)
        errors = [d for lvl, w, d in rep.rows
                  if lvl == lint.ERROR and w == "briefs"]
        assert errors == [], rep.render()

    def test_the_cutoff_is_resolved_from_content_not_a_pinned_sha(self):
        """Production line: resolve_handoff_obligation_cutoff +
        HANDOFF_OBLIGATION_PHRASE + the post-resolve 'phrase in blob' guard.

        THE criterion that matters most: if cutoff resolution breaks (phrase
        reworded, -S returns nothing), this must fail LOUDLY rather than the
        check silently grandfathering everything. Asserts:
        - resolved cutoff is a real 40-char commit
        - that commit's SKILL.md actually contains the obligation phrase
        - the sha is not pinned as a literal in lint.py
        - precondition: live tree has at least one brief in scope AND at least
          one grandfathered (a vacuous split would make the check meaningless)
        """
        import subprocess
        root = lint.SKILL_DIR
        cutoff = lint.resolve_handoff_obligation_cutoff(root)
        assert cutoff is not None, (
            "cutoff resolved to nothing — the hollow outcome that would skip "
            "every brief and look like a clean pass")
        assert re.fullmatch(r"[0-9a-f]{40}", cutoff), cutoff

        src = Path(lint.__file__).read_text(encoding="utf-8")
        # Content resolution, not a pinned sha: neither the full nor a short
        # form of today's measured introduction may be hardcoded as the cutoff.
        assert cutoff not in src, (
            "cutoff sha is pinned in lint.py — resolution must be by content")
        assert "6f72b8d" not in src, (
            "measured introduction sha is pinned in lint.py — use content")

        blob = subprocess.check_output(
            ["git", "-C", str(root), "show", f"{cutoff}:SKILL.md"],
            text=True)
        assert self.PHRASE in blob, (
            f"resolved cutoff {cutoff[:7]} does not contain the obligation "
            f"phrase — content resolution picked the wrong commit, which is "
            f"how the check would grandfather everything in silence")

        # Precondition the check's meaning depends on: briefs on BOTH sides of
        # the cutoff. Derived at runtime — a literal tuned to today's 27/3
        # split is a check with an invisible expiry date.
        scope = lint.classify_brief_handoff_scope(root)
        assert scope["cutoff"] == cutoff
        assert len(scope["in_scope"]) > 0, (
            "no brief is in scope — the check is vacuous; every brief fell "
            f"before the cutoff. scope={scope}")
        assert len(scope["grandfathered"]) > 0, (
            "no brief is grandfathered — the check is vacuous; every brief "
            f"fell after the cutoff. scope={scope}")
        # And the live tree is clean: in-scope briefs all mention the path.
        assert scope["missing"] == [], (
            f"live in-scope brief(s) lack the mention: {scope['missing']}")

    def test_the_live_tree_is_green_with_coverage_numbers(self):
        """Criterion 4 + coverage (#395): live tree exits clean; OK names counts."""
        root = lint.SKILL_DIR
        scope = lint.classify_brief_handoff_scope(root)
        assert scope["in_scope"] and scope["grandfathered"], scope
        rep = lint.Report()
        lint.check_brief_handoff_obligation(root / ".dreamwork", rep)
        errors = [d for lvl, w, d in rep.rows
                  if lvl == lint.ERROR and w == "briefs"]
        assert errors == [], rep.render()
        oks = [d for lvl, w, d in rep.rows if lvl == lint.OK and w == "briefs"]
        assert len(oks) == 1, rep.render()
        assert f"{len(scope['in_scope'])} brief(s) in scope" in oks[0], oks[0]
        assert f"{len(scope['grandfathered'])} grandfathered" in oks[0], oks[0]

    def test_an_untracked_brief_is_skipped(self, tmp_path):
        """Decision 1: untracked = mid-write; skip, do not flag."""
        import time
        t, git = self._git_repo(tmp_path)
        (t / "SKILL.md").write_text(
            f"# skill\n\n{self.PHRASE}\n", encoding="utf-8")
        git("add", "SKILL.md")
        git("commit", "-qm", "obligation")
        time.sleep(1.1)
        briefs = t / ".dreamwork" / "docs" / "briefs"
        briefs.mkdir(parents=True)
        (briefs / "998-wip.md").write_text(
            "# WIP brief, never committed\n", encoding="utf-8")
        # No git add — untracked.
        scope = lint.classify_brief_handoff_scope(t)
        assert "998-wip.md" in scope["skipped"], scope
        assert "998-wip.md" not in scope["in_scope"], scope
        rep = lint.Report()
        lint.check_brief_handoff_obligation(t / ".dreamwork", rep)
        assert not any(w == "briefs" and lvl == lint.ERROR
                       for lvl, w, d in rep.rows), rep.render()

    def test_a_post_cutoff_brief_with_the_mention_is_clean(self, tmp_path):
        import time
        t, git = self._git_repo(tmp_path)
        (t / "SKILL.md").write_text(
            f"# skill\n\n{self.PHRASE}\n", encoding="utf-8")
        git("add", "SKILL.md")
        git("commit", "-qm", "obligation")
        time.sleep(1.1)
        briefs = t / ".dreamwork" / "docs" / "briefs"
        briefs.mkdir(parents=True)
        (briefs / "997-ok.md").write_text(
            "# Brief\n\nAlso append one line to `.dreamwork/handoffs.md`.\n",
            encoding="utf-8")
        git("add", ".dreamwork/docs/briefs/997-ok.md")
        git("commit", "-qm", "compliant brief")
        scope = lint.classify_brief_handoff_scope(t)
        assert "997-ok.md" in scope["in_scope"], scope
        assert scope["missing"] == [], scope
        rep = lint.Report()
        lint.check_brief_handoff_obligation(t / ".dreamwork", rep)
        assert not any(lvl == lint.ERROR and w == "briefs"
                       for lvl, w, d in rep.rows), rep.render()
        oks = [d for lvl, w, d in rep.rows if lvl == lint.OK and w == "briefs"]
        assert oks and "1 brief(s) in scope" in oks[0], rep.render()

    def test_the_check_is_registered_in_run_checks(self):
        import inspect
        assert "check_brief_handoff_obligation(dw, rep)" in \
            inspect.getsource(lint.run_checks)

    def test_no_skill_md_is_silent(self, tmp_path):
        """A foreign dreamwork target with briefs but no SKILL.md is not governed."""
        t = fresh(tmp_path)
        briefs = t / ".dreamwork" / "docs" / "briefs"
        briefs.mkdir(parents=True)
        (briefs / "1.md").write_text("x\n", encoding="utf-8")
        rep = lint.Report()
        lint.check_brief_handoff_obligation(t / ".dreamwork", rep)
        assert rep.rows == [], rep.render()


class TestBriefWorktreeAbsInbox:
    """#405: a brief that names a worktree must give an absolute inbox path.

    A lane in `.worktrees/x` told to append to `.dreamwork/inbox.md` writes
    its own copy; the coordinator never sees it. Cutoff is content-resolved
    from SKILL.md (WORKTREE_ABS_INBOX_PHRASE), never pinned.

    Production lines named per test (what must change for it to fail):
    - flagged: the `if not ABS_INBOX_PATH_RE.search(text)` branch in
      classify_worktree_brief_abs_inbox / the ERROR add in
      check_brief_worktree_abs_inbox
    - grandfathered: the `if add_t <= cutoff_t` branch that skips pre-rule
      worktree briefs
    - cutoff content: resolve_worktree_abs_inbox_cutoff + the phrase constant
      + the post-resolve "phrase in blob" guard
    - precondition: live tree has at least one brief containing `.worktrees/`
      (a check that silently matches nothing passes forever)
    """

    PHRASE = lint.WORKTREE_ABS_INBOX_PHRASE
    ABS = "/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md"

    def _git_repo(self, tmp_path):
        import subprocess
        t = fresh(tmp_path)

        def git(*a, check=True):
            return subprocess.run(
                ["git", "-C", str(t), *a],
                capture_output=True, text=True, check=check)

        git("init", "-q")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        return t, git

    def test_a_post_cutoff_worktree_brief_without_abs_inbox_is_flagged(
            self, tmp_path):
        """Production line: the missing-absolute-inbox ERROR in
        check_brief_worktree_abs_inbox — a post-cutoff brief that names
        `.worktrees/` but only has a relative `.dreamwork/inbox.md` must be
        named by basename.
        """
        import time
        t, git = self._git_repo(tmp_path)
        (t / "SKILL.md").write_text(
            f"# skill\n\n{self.PHRASE}\n", encoding="utf-8")
        git("add", "SKILL.md")
        git("commit", "-qm", "absolute-inbox rule lands")
        time.sleep(1.1)
        briefs = t / ".dreamwork" / "docs" / "briefs"
        briefs.mkdir(parents=True)
        # THE defect: worktree named, inbox path repo-relative only.
        (briefs / "999-wt-rel.md").write_text(
            "# Brief\n\nWorktree: `.worktrees/x`\n\n"
            "Report to `.dreamwork/inbox.md`.\n",
            encoding="utf-8")
        git("add", ".dreamwork/docs/briefs/999-wt-rel.md")
        git("commit", "-qm", "worktree brief, relative inbox only")

        # Precondition, derived: the brief is a worktree brief AND after cutoff
        # AND missing the absolute path — the three facts the ERROR depends on.
        scope = lint.classify_worktree_brief_abs_inbox(t)
        assert "999-wt-rel.md" in scope["worktree"], scope
        assert "999-wt-rel.md" in scope["in_scope"], scope
        assert "999-wt-rel.md" in scope["missing"], scope
        # And the relative form does not satisfy the absolute matcher.
        rel_only = ".dreamwork/inbox.md"
        assert not lint.ABS_INBOX_PATH_RE.search(rel_only), rel_only

        rep = lint.Report()
        lint.check_brief_worktree_abs_inbox(t / ".dreamwork", rep)
        errors = [d for lvl, w, d in rep.rows
                  if lvl == lint.ERROR and w == "briefs"]
        assert len(errors) == 1, rep.render()
        assert "999-wt-rel.md" in errors[0], errors[0]
        assert "absolute" in errors[0].lower() or "inbox.md" in errors[0], (
            errors[0])

    def test_a_pre_cutoff_worktree_brief_is_grandfathered(self, tmp_path):
        """Production line: the `add_t <= cutoff_t` grandfather branch in
        classify_worktree_brief_abs_inbox.
        """
        import time
        t, git = self._git_repo(tmp_path)
        briefs = t / ".dreamwork" / "docs" / "briefs"
        briefs.mkdir(parents=True)
        (briefs / "100-old-wt.md").write_text(
            "# Brief\n\nWorktree: `.worktrees/old`\n\n"
            "Report to `.dreamwork/inbox.md`.\n",
            encoding="utf-8")
        (t / "SKILL.md").write_text("# skill\n\nno abs rule yet\n",
                                    encoding="utf-8")
        git("add", "SKILL.md", ".dreamwork/docs/briefs/100-old-wt.md")
        git("commit", "-qm", "worktree brief before rule")
        time.sleep(1.1)
        (t / "SKILL.md").write_text(
            f"# skill\n\n{self.PHRASE}\n", encoding="utf-8")
        git("add", "SKILL.md")
        git("commit", "-qm", "absolute-inbox rule lands later")

        scope = lint.classify_worktree_brief_abs_inbox(t)
        assert "100-old-wt.md" in scope["worktree"], scope
        assert "100-old-wt.md" in scope["grandfathered"], scope
        assert "100-old-wt.md" not in scope["in_scope"], scope
        assert scope["missing"] == [], scope

        rep = lint.Report()
        lint.check_brief_worktree_abs_inbox(t / ".dreamwork", rep)
        errors = [d for lvl, w, d in rep.rows
                  if lvl == lint.ERROR and w == "briefs"]
        assert errors == [], rep.render()

    def test_a_post_cutoff_worktree_brief_with_abs_inbox_is_clean(
            self, tmp_path):
        import time
        t, git = self._git_repo(tmp_path)
        (t / "SKILL.md").write_text(
            f"# skill\n\n{self.PHRASE}\n", encoding="utf-8")
        git("add", "SKILL.md")
        git("commit", "-qm", "rule lands")
        time.sleep(1.1)
        briefs = t / ".dreamwork" / "docs" / "briefs"
        briefs.mkdir(parents=True)
        (briefs / "997-wt-ok.md").write_text(
            f"# Brief\n\nWorktree: `.worktrees/ok`\n\n"
            f"Report to `{self.ABS}`.\n",
            encoding="utf-8")
        git("add", ".dreamwork/docs/briefs/997-wt-ok.md")
        git("commit", "-qm", "compliant worktree brief")
        scope = lint.classify_worktree_brief_abs_inbox(t)
        assert "997-wt-ok.md" in scope["in_scope"], scope
        assert scope["missing"] == [], scope
        rep = lint.Report()
        lint.check_brief_worktree_abs_inbox(t / ".dreamwork", rep)
        assert not any(lvl == lint.ERROR and w == "briefs"
                       for lvl, w, d in rep.rows), rep.render()
        oks = [d for lvl, w, d in rep.rows if lvl == lint.OK and w == "briefs"]
        assert oks and "1 worktree-naming brief(s)" in oks[0], rep.render()

    def test_a_reverted_then_recreated_brief_is_still_untracked(self, tmp_path):
        """The scope and content snapshots must agree after commit + revert.

        The old history-only classifier found the earlier add commit while
        reading the recreated untracked bytes from disk, turning the same
        untracked path from green before its first commit to red after revert.
        """
        import time
        t, git = self._git_repo(tmp_path)
        (t / "SKILL.md").write_text(
            f"# skill\n\n{self.PHRASE}\n", encoding="utf-8")
        git("add", "SKILL.md")
        git("commit", "-qm", "rule lands")
        time.sleep(1.1)
        brief = t / ".dreamwork" / "docs" / "briefs" / "994-reverted.md"
        brief.parent.mkdir(parents=True)
        broken = "# Brief\n\nWorktree: `.worktrees/reverted`\n"
        brief.write_text(broken, encoding="utf-8")
        git("add", str(brief.relative_to(t)))
        git("commit", "-qm", "add broken brief")
        git("revert", "--no-edit", "HEAD")
        brief.parent.mkdir(parents=True)
        brief.write_text(broken, encoding="utf-8")

        assert git("ls-files", "--error-unmatch", str(brief.relative_to(t)),
                   check=False).returncode != 0
        assert lint.brief_add_commit(t, str(brief.relative_to(t))) is None
        scope = lint.classify_worktree_brief_abs_inbox(t)
        assert "994-reverted.md" in scope["skipped"], scope
        assert "994-reverted.md" not in scope["missing"], scope

    def test_well_formed_fake_absolute_inbox_is_an_open_false_green(
            self, tmp_path):
        """Direction 2: #405's regex proves shape, not coordinator ownership."""
        import time
        t, git = self._git_repo(tmp_path)
        (t / "SKILL.md").write_text(
            f"# skill\n\n{self.PHRASE}\n", encoding="utf-8")
        git("add", "SKILL.md")
        git("commit", "-qm", "rule lands")
        time.sleep(1.1)
        brief = t / ".dreamwork" / "docs" / "briefs" / "993-fake.md"
        brief.parent.mkdir(parents=True)
        fake = "/tmp/stale-coordinator/inbox.md"
        brief.write_text(
            f"# Brief\n\nWorktree: `.worktrees/fake`\n\nReport to `{fake}`.\n",
            encoding="utf-8",
        )
        git("add", str(brief.relative_to(t)))
        git("commit", "-qm", "brief points at fake absolute inbox")

        assert lint.ABS_INBOX_PATH_RE.search(fake), fake
        scope = lint.classify_worktree_brief_abs_inbox(t)
        assert "993-fake.md" in scope["in_scope"], scope
        assert scope["missing"] == [], scope
        rep = lint.Report()
        lint.check_brief_worktree_abs_inbox(t / ".dreamwork", rep)
        assert not any(lvl == lint.ERROR for lvl, _, _ in rep.rows), rep.render()

    def test_a_brief_that_does_not_name_a_worktree_is_not_examined(
            self, tmp_path):
        """Only `.worktrees/`-naming briefs are in the match set."""
        import time
        t, git = self._git_repo(tmp_path)
        (t / "SKILL.md").write_text(
            f"# skill\n\n{self.PHRASE}\n", encoding="utf-8")
        git("add", "SKILL.md")
        git("commit", "-qm", "rule")
        time.sleep(1.1)
        briefs = t / ".dreamwork" / "docs" / "briefs"
        briefs.mkdir(parents=True)
        # Relative inbox, but no worktree — must not be flagged.
        (briefs / "996-shared.md").write_text(
            "# Brief\n\nShared-tree lane. Report to `.dreamwork/inbox.md`.\n",
            encoding="utf-8")
        git("add", ".dreamwork/docs/briefs/996-shared.md")
        git("commit", "-qm", "shared-tree brief")
        # Without any worktree brief the check returns without rows; seed one
        # compliant so the OK path runs and the non-worktree brief stays silent.
        (briefs / "995-wt.md").write_text(
            f"# Brief\n\n`.worktrees/y`\n\n`{self.ABS}`\n",
            encoding="utf-8")
        git("add", ".dreamwork/docs/briefs/995-wt.md")
        git("commit", "-qm", "worktree brief ok")

        scope = lint.classify_worktree_brief_abs_inbox(t)
        assert "996-shared.md" not in scope["worktree"], scope
        assert "995-wt.md" in scope["worktree"], scope
        rep = lint.Report()
        lint.check_brief_worktree_abs_inbox(t / ".dreamwork", rep)
        errors = [d for lvl, w, d in rep.rows
                  if lvl == lint.ERROR and w == "briefs"]
        assert errors == [], rep.render()
        assert not any("996-shared" in d for _, _, d in rep.rows), rep.render()

    def test_the_cutoff_is_resolved_from_content_not_a_pinned_sha(self):
        """Production line: resolve_worktree_abs_inbox_cutoff + phrase +
        phrase-in-blob guard. Hollow no-cutoff must not look like a pass.

        Precondition (asserted, not assumed): the live tree has at least one
        brief whose body contains `.worktrees/` — a check that silently
        matches nothing passes forever.
        """
        import subprocess
        root = lint.SKILL_DIR
        # Precondition the check depends on: worktree-naming briefs exist.
        scope = lint.classify_worktree_brief_abs_inbox(root)
        # Before the introducing commit is in history, cutoff is None and
        # worktree list may still be empty from the empty return. Derive the
        # precondition from the filesystem so it holds even mid-landing.
        briefs_dir = root / ".dreamwork" / "docs" / "briefs"
        wt_names = [
            p.name for p in briefs_dir.glob("*.md")
            if lint.WORKTREE_BRIEF_MARKER in p.read_text(
                encoding="utf-8", errors="replace")
        ]
        assert len(wt_names) > 0, (
            "no brief names `.worktrees/` — the absolute-inbox check matches "
            "nothing and would pass forever; precondition failed")

        cutoff = lint.resolve_worktree_abs_inbox_cutoff(root)
        assert cutoff is not None, (
            "cutoff resolved to nothing — the hollow outcome that would skip "
            "every worktree brief and look like a clean pass")
        assert re.fullmatch(r"[0-9a-f]{40}", cutoff), cutoff

        src = Path(lint.__file__).read_text(encoding="utf-8")
        assert cutoff not in src, (
            "cutoff sha is pinned in lint.py — resolution must be by content")

        blob = subprocess.check_output(
            ["git", "-C", str(root), "show", f"{cutoff}:SKILL.md"],
            text=True)
        assert self.PHRASE in blob, (
            f"resolved cutoff {cutoff[:7]} does not contain the absolute-inbox "
            f"phrase — content resolution picked the wrong commit")

        # Live tree is clean for in-scope worktree briefs.
        assert scope["missing"] == [], (
            f"live in-scope worktree brief(s) lack absolute inbox: "
            f"{scope['missing']}")

    def test_the_live_tree_is_green_with_coverage_numbers(self):
        root = lint.SKILL_DIR
        briefs_dir = root / ".dreamwork" / "docs" / "briefs"
        wt_names = [
            p.name for p in briefs_dir.glob("*.md")
            if lint.WORKTREE_BRIEF_MARKER in p.read_text(
                encoding="utf-8", errors="replace")
        ]
        assert len(wt_names) > 0, (
            "precondition: at least one `.worktrees/`-naming brief must exist")
        scope = lint.classify_worktree_brief_abs_inbox(root)
        assert len(scope["worktree"]) == len(wt_names), scope
        rep = lint.Report()
        lint.check_brief_worktree_abs_inbox(root / ".dreamwork", rep)
        errors = [d for lvl, w, d in rep.rows
                  if lvl == lint.ERROR and w == "briefs"]
        assert errors == [], rep.render()
        oks = [d for lvl, w, d in rep.rows
               if lvl == lint.OK and w == "briefs" and "#405" in d]
        assert len(oks) == 1, rep.render()
        assert f"{len(scope['worktree'])} worktree-naming brief(s)" in oks[0], (
            oks[0])

    def test_the_check_is_registered_in_run_checks(self):
        import inspect
        assert "check_brief_worktree_abs_inbox(dw, rep)" in \
            inspect.getsource(lint.run_checks)

    def test_no_skill_md_is_silent(self, tmp_path):
        t = fresh(tmp_path)
        briefs = t / ".dreamwork" / "docs" / "briefs"
        briefs.mkdir(parents=True)
        (briefs / "1.md").write_text(
            "Worktree: `.worktrees/x`\n", encoding="utf-8")
        rep = lint.Report()
        lint.check_brief_worktree_abs_inbox(t / ".dreamwork", rep)
        assert rep.rows == [], rep.render()

    def test_abs_inbox_regex_rejects_relative_and_accepts_absolute(self):
        """Production line: ABS_INBOX_PATH_RE itself — the matcher the
        missing-branch depends on. Relative must not match; absolute must.
        """
        assert not lint.ABS_INBOX_PATH_RE.search(".dreamwork/inbox.md")
        assert not lint.ABS_INBOX_PATH_RE.search("` .dreamwork/inbox.md`")
        m = lint.ABS_INBOX_PATH_RE.search(self.ABS)
        assert m is not None, self.ABS
        assert m.group(0).endswith("/inbox.md")

    def test_abs_inbox_regex_accepts_the_real_comms_convention(self):
        """#587: the matcher must accept the loop's ACTUAL inbox convention,
        not only a basename literally named ``inbox.md``. The real files are
        ``coord-inbox.md`` and ``<lane-id>-inbox.md`` under the comms dir;
        the old ``/.../inbox\\.md`` regex rejected both, so briefs invented
        fake per-lane directories (``.../lane-X/inbox.md``) to satisfy it.

        These positive assertions are the discriminating Direction-1 case:
        they FAIL under the old regex (which matched only a literal
        ``inbox.md`` basename) and PASS once the rule anchors on a leading
        ``/`` plus a basename ending in ``inbox.md``.
        """
        real = [
            "/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md",
            "/home/xertrov/.cache/agent-comms/ud-dreamwork/lane-586routes-inbox.md",
            "/home/xertrov/.cache/agent-comms/ud-dreamwork/352-inbox.md",
        ]
        for p in real:
            m = lint.ABS_INBOX_PATH_RE.search(p)
            assert m is not None, p
            assert m.group(0).endswith("inbox.md"), (p, m.group(0))
        # And a backtick-wrapped real path (how briefs actually cite it).
        bt = "`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`"
        assert lint.ABS_INBOX_PATH_RE.search(bt) is not None, bt

    def test_abs_inbox_regex_still_rejects_non_absolute_or_non_inbox(self):
        """#405 is about ABSOLUTENESS, so a fix that starts accepting relative
        paths has inverted the rule, not fixed it. The relative
        ``.dreamwork/inbox.md`` MUST still fail — that is the discriminating
        negative (#587's whole point). Plus the looks-absolute-but-isn't
        forms a too-permissive regex would let through (#587 Direction 2).
        """
        must_fail = [
            ".dreamwork/inbox.md",            # repo-relative — the #405 defect
            "` .dreamwork/inbox.md`",
            "foo/.dreamwork/coord-inbox.md",  # relative, but has a slash
            "/home/x/coord-inbox.md.bak",     # inbox.md is not the tail
            "~/.cache/agent-comms/ud-dreamwork/coord-inbox.md",  # not POSIX-absolute
            "C:/Users/x/coord-inbox.md",      # Windows drive, not POSIX-absolute
        ]
        for p in must_fail:
            assert lint.ABS_INBOX_PATH_RE.search(p) is None, p


class TestHumanBlocker:
    """#419 — no human blocker without a question.

    He tried to rule on #264 and found no question. The invariant: an open
    task blocked on a human decision has a questions.md entry, open or
    answered-but-unfolded. This check makes Direction 1 checkable — a marker
    `blocked-on: **human**` whose gate has no question. Direction 2 ("he ruled
    and nobody processed it") is REFUSED (see the docstring and the report):
    the brief's amendment retracted the #371 specimen, and the live repo shows
    the prose form fires 11/11 false positives. The amendment's must-NOT-flag
    case is the first test below.
    """

    def build(self, tmp_path, tasks, questions=None):
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "tasks.md").write_text(tasks)
        if questions is not None:
            (dw / "questions.md").write_text(questions)
        return t

    def rows(self, t, level=None):
        rep = lint.Report()
        lint.check_human_blocker(t / ".dreamwork", lint.load_watch(), rep)
        return [d for lvl, w, d in rep.rows
                if w == "tasks.md" and (level is None or lvl == level)]

    TASKS = """# Tasks

Next id: **5**

## Open

- **#1** — a task · P2 · origin: **loop**
- **#2** — blocked on him · P1 · origin: **loop** · blocked-on: **human**
- **#3** — gated on a neighbour · P1 · origin: **loop** · blocked-on: **human** · gate: **#9**
- **#4** — wrong vocab · P1 · origin: **loop** · blocked-on: **approval**
"""

    OPEN_Q = """# Questions for the human

## Open

- **#5: a question about task five** body

## Answered
"""

    ANSWERED_Q = """# Questions for the human

## Open

## Answered

- **#2: a question about task two** → answered (2026-07-28): yes
"""

    def test_a_marker_with_no_question_errors_direction_1(self, tmp_path):
        # The defect he hit: blocked on him, nothing on the channel. This is
        # the one direction this check enforces, and it must go red.
        t = self.build(tmp_path, self.TASKS, self.OPEN_Q)
        errs = self.rows(t, lint.ERROR)
        assert any("#2" in e and "no questions.md entry names #2" in e for e in errs), errs

    def test_the_371_prefix_body_does_NOT_flag_this_is_the_amendment(self, tmp_path):
        # THE amendment's required test (16:23). The pre-fix #371 body is what
        # the brief originally offered as the Direction-2 red; the amendment
        # retracted it: "answered ≠ authorised", and #371 is a must-NOT-flag.
        # #371's body names a #263 question; if a check keyed on "question
        # answered ⇒ unblock" fired here, it would have told the coordinator to
        # repeat 7c5fc82's exact mistake. Restore the real body from
        # `git show 7c5fc82^:.dreamwork/tasks.md` (this constant is verbatim).
        prefix_371 = (
            "- **#371** — `do_POST` witnesses an interrupted body as complete · P1 ·\n"
            "  reliability bug · origin: **loop** · found by dreamer-263-plan, coordinator verified\n"
            "  · **what REMAINS is only the policy, and it is his**: whether a short body is refused\n"
            "  · #263's plan places that half at its increment 20 · **blocked on #263 Q2 only** —\n"
            "  no longer on `watch.py`, which is free\n"
        )
        # Precondition: the body carries the prose phrase a naive D2 would key
        # on. Without this assertion the test is hollow — it would pass if the
        # fixture had been edited to remove the trigger. Assert the trigger.
        assert "blocked on #263" in prefix_371, "fixture lost its trigger phrase"
        tasks = "# Tasks\n\nNext id: **372**\n\n## Open\n\n" + prefix_371
        # #263 has an ANSWERED question in the live repo, so a D2 keyed on
        # "gate answered" would fire. Provide that answered question.
        t = self.build(tmp_path, tasks, self.ANSWERED_Q.replace("#2:", "#263:").replace(
            "about task two", "about task 263"))
        rows = self.rows(t)
        assert rows == [], (
            "the pre-fix #371 body must NOT flag (amendment 16:23): 'answered ≠ "
            "authorised' — a ruling on a decision does not authorise the work; "
            "got: %r" % rows)

    def test_a_marker_with_an_open_question_is_clean(self, tmp_path):
        # The happy path: #2 carries the marker and has an open question. A
        # question on the channel means there IS an answer in our data. Minimal
        # fixture: only the marked entry, so a stray error can't mask the
        # happy path.
        tasks = (
            "# Tasks\n\nNext id: **3**\n\n## Open\n\n"
            "- **#2** — blocked on him · P1 · origin: **loop** · blocked-on: **human**\n"
        )
        questions = (
            "# Questions for the human\n\n## Open\n\n"
            "- **#2: a question about task two** body\n\n## Answered\n"
        )
        t = self.build(tmp_path, tasks, questions)
        errs = self.rows(t, lint.ERROR)
        assert errs == [], errs
        oks = self.rows(t, lint.OK)
        assert any("1 of 1 open entries marked blocked-on-human" in o for o in oks), oks

    def test_a_marker_with_an_answered_question_is_clean(self, tmp_path):
        # An answered-but-unfolded question still counts as "an answer in our
        # data". This is the legitimate transient Direction 2 was meant to
        # catch, and the reason D2 cannot be a check: this very shape is also
        # the #371 trap when the answer does not authorise the build. Direction
        # 1 treats it as satisfied (there is data); the fold is a separate
        # concern, owned by check_unfolded_answers. Minimal fixture: only the
        # marked entry, so a stray error from another entry can't mask it.
        tasks = (
            "# Tasks\n\nNext id: **3**\n\n## Open\n\n"
            "- **#2** — blocked on him · P1 · origin: **loop** · blocked-on: **human**\n"
        )
        t = self.build(tmp_path, tasks, self.ANSWERED_Q)
        errs = self.rows(t, lint.ERROR)
        assert errs == [], errs

    def test_gate_redirection_resolves_to_the_named_question(self, tmp_path):
        # #3 is marked human with gate: #9. #3 has no question, #9 does. The
        # gate must redirect so the check finds #9's question and is clean —
        # this is the mechanism that survives a ruling riding a neighbour.
        t = self.build(tmp_path, self.TASKS, self.OPEN_Q.replace("#5:", "#9:").replace(
            "task five", "task nine"))
        errs = self.rows(t, lint.ERROR)
        assert not any("#3" in e for e in errs), errs  # gate redirected

    def test_transitive_coverage_does_not_count(self, tmp_path):
        # #2's own id has no question. A neighbour #5 has an open question that
        # is "about the same decision". That MUST NOT satisfy #2 — a reader on
        # #2 alone cannot find #5, which is the #371 trap. #2 must ERROR.
        t = self.build(tmp_path, self.TASKS, self.OPEN_Q)  # #5 has the question, #2 does not
        errs = self.rows(t, lint.ERROR)
        assert any("#2" in e and "no questions.md entry names #2" in e for e in errs), errs

    def test_a_wrong_vocabulary_value_errors(self, tmp_path):
        # blocked-on: **approval** is a claim a reader would have to interpret.
        # The vocabulary is exactly `human`; anything else is an error, the
        # same reasoning as the origin marker.
        t = self.build(tmp_path, self.TASKS, self.OPEN_Q)
        errs = self.rows(t, lint.ERROR)
        assert any("#4" in e and "vocabulary is exactly `human`" in e for e in errs), errs

    def test_a_prose_blocked_on_N_does_not_fire_even_when_N_is_answered(self, tmp_path):
        # The load-bearing negative: the prose form `blocked on #N` where N is
        # answered is what every task-dependency entry looks like. On the live
        # repo it fires 11 times, all legitimate. An entry with no marker but a
        # prose `blocked on #263` (answered) must be SILENT.
        tasks = (
            "# Tasks\n\nNext id: **4**\n\n## Open\n\n"
            "- **#1** — a plain task · P2 · origin: **loop**\n"
            "  blocked on #2 landing first; this is a normal task dependency\n"
        )
        t = self.build(tmp_path, tasks, self.ANSWERED_Q.replace("#2:", "#2:").replace(
            "about task two", "about task two"))
        rows = self.rows(t)
        assert rows == [], (
            "prose `blocked on #N` must not fire even when N is answered — it "
            "names a task dependency, not an unprocessed ruling; got: %r" % rows)

    def test_an_entry_with_no_marker_is_not_a_claim(self, tmp_path):
        # Absence is "no claim", never "unblocked". An unmarked entry is simply
        # not checked — the marker is forward-only, and 137 open entries carry
        # none. The check must be silent on them.
        tasks = (
            "# Tasks\n\nNext id: **3**\n\n## Open\n\n"
            "- **#1** — a plain prose-only task · P2 · origin: **loop**\n"
            "  awaiting his ruling on something\n"
        )
        t = self.build(tmp_path, tasks, self.OPEN_Q)
        assert self.rows(t) == [], self.rows(t)

    def test_silent_when_questions_md_is_missing(self, tmp_path):
        # Cannot correlate without the question reader — say nothing rather
        # than claim every marked entry is fine (the hollow-pass this repo
        # refuses). No questions.md ⇒ the check degrades silently.
        t = self.build(tmp_path, self.TASKS)  # no questions.md
        assert self.rows(t) == [], self.rows(t)

    def test_a_hard_wrapped_marker_is_still_read(self, tmp_path):
        # The loop writes at ~72 columns, so a marker wraps: `blocked-on:`
        # ends a line, `**human**` opens the next. _metadata_clause joins the
        # entry's lines before reading, so the wrapped marker must still fire.
        tasks = (
            "# Tasks\n\nNext id: **3**\n\n## Open\n\n"
            "- **#1** — a task · P1 · origin: **loop** · blocked-on:\n"
            "  **human** · body continues\n"
        )
        t = self.build(tmp_path, tasks, self.OPEN_Q)  # #1 has no question
        errs = self.rows(t, lint.ERROR)
        assert any("#1" in e and "no questions.md entry names #1" in e for e in errs), errs

    def test_this_repo_passes_its_own_human_blocker_check(self):
        # Dogfood: the live repo is forward-only (0 markers) so the check is
        # silent. A red here means a marker landed that has no question, which
        # would be a real finding — or a misfire, and the coordinator needs to
        # know which.
        rep = lint.Report()
        lint.check_human_blocker(lint.SKILL_DIR / ".dreamwork", lint.load_watch(), rep)
        assert not any(lvl == lint.ERROR for lvl, _, _ in rep.rows), rep.render()


class TestTitleBlockedClaim:
    """#725 — a deliberately noisy ``blocked on`` phrase heuristic.

    `list` prints titles, not notes, so a title that embeds a condition that
    later becomes false misleads exactly where a correction underneath is
    invisible. #630, #631 and #641 all read as blocked for six hours after
    their rulings landed. The check mechanically finds an open title containing
    the phrase "blocked on" while the structured blocked_on field is empty.
    It does not parse English: negated, quoted and meta uses warn too, and the
    message says a human must review the row.

    The pattern is "blocked on", not bare "blocked" — the discrimination
    #707's lesson governs. Measured on 170 open titles, the phrase caught three
    real instances and zero descriptions; that corpus result is not a grammar.
    """

    # --- markdown-mode fixtures (the shared build idiom) ---

    MD_CLAIM = (
        "# Tasks\n\nNext id: **3**\n\n## Open\n\n"
        # #1: the defect — title claims "blocked on", no structured field
        "- **#1** — build the thing — blocked on his ruling · P1 · "
        "origin: **loop**\n"
        # #2: a description ABOUT blocking, not a claim — must NOT trip
        "- **#2** — a blocked errand is invisible · P2 · origin: **loop**\n"
    )

    def _md_target(self, tmp_path, tasks):
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "tasks.md").write_text(tasks)
        return t

    def _rows(self, t, level=None):
        rep = lint.Report()
        lint.check_title_blocked_claim(t / ".dreamwork", rep)
        return [d for lvl, w, d in rep.rows
                if w == "tasks.md" and (level is None or lvl == level)]

    # --- Direction 1: the check CATCHES the real defect ---

    def test_a_title_claim_with_empty_blocked_on_warns(self, tmp_path):
        # #630's exact shape: "... — blocked on his G2 ruling" with no
        # blocked_on field. The discriminating assertion names the id and
        # quotes the offending title fragment, not just a count.
        t = self._md_target(tmp_path, self.MD_CLAIM)
        warns = self._rows(t, lint.WARN)
        assert any("#1" in d and "blocked on his ruling" in d
                   and "intentionally noisy phrase heuristic" in d
                   and "a human must review the row" in d for d in warns), (
            "a title claiming 'blocked on' with no structured field must WARN, "
            "naming the id and fragment while admitting human review: %r" % warns)

    def test_negated_meta_and_codespan_phrases_warn_as_noisy_matches(self, tmp_path):
        # #746's three discriminating counterexamples. Option (b) deliberately
        # keeps the regex cheap and lowers the claim: all three WARN, and the
        # row must say a human judges them rather than calling them grammar.
        titles = {
            1: "not blocked on #614 anymore",
            2: "Explain why jobs are blocked on CI",
            3: "Document the `blocked on` title lint",
        }
        heads = "".join(
            f"- **#{task_id}** — {title} · P2 · origin: **loop**\n"
            for task_id, title in titles.items()
        )
        tasks = "# Tasks\n\nNext id: **4**\n\n## Open\n\n" + heads
        warns = self._rows(self._md_target(tmp_path, tasks), lint.WARN)
        for task_id, title in titles.items():
            assert any(
                f"#{task_id}" in row and title in row
                and "intentionally noisy phrase heuristic" in row
                and "a human must review the row" in row
                for row in warns
            ), f"#{task_id} must be surfaced as a human-reviewed phrase match: {warns!r}"

    def test_a_description_about_blocking_does_not_trip(self, tmp_path):
        # #707's discipline: a title legitimately ABOUT blocking ("A blocked
        # errand is invisible") must NOT trip. This is the false-positive the
        # brief names, and bare "blocked" would catch it.
        t = self._md_target(tmp_path, self.MD_CLAIM)
        warns = self._rows(t, lint.WARN)
        assert not any("#2" in d for d in warns), (
            "a title describing blocking ('a blocked errand is invisible') "
            "is not a claim and must not WARN: %r" % warns)

    def test_blocked_on_writer_title_does_not_trip(self, tmp_path):
        # The brief's named false-positive: "Fix the blocked_on writer" uses
        # the UNDERSCORE form. "blocked on" (space) must not match it.
        tasks = (
            "# Tasks\n\nNext id: **2**\n\n## Open\n\n"
            "- **#1** — fix the blocked_on writer · P2 · origin: **loop**\n"
        )
        t = self._md_target(tmp_path, tasks)
        assert self._rows(t) == [], (
            "'blocked_on' (underscore) is a field name, not a claim; bare "
            "'blocked' would trip on it, 'blocked on' (space) must not")

    def test_case_insensitive_BLOCKED_matches(self, tmp_path):
        # #641's title: "BLOCKED on the #614 wire-protocol ruling" (all caps).
        tasks = (
            "# Tasks\n\nNext id: **2**\n\n## Open\n\n"
            "- **#1** — implement the thing — BLOCKED on the #614 ruling · "
            "P1 · origin: **loop**\n"
        )
        t = self._md_target(tmp_path, tasks)
        warns = self._rows(t, lint.WARN)
        assert any("#1" in d for d in warns), warns

    def test_a_backed_claim_in_markdown_is_clean(self, tmp_path):
        # A title claiming "blocked on" whose metadata carries
        # blocked-on: **human** is backed — the structured field records the
        # claim, so the title is not a contradiction.
        tasks = (
            "# Tasks\n\nNext id: **2**\n\n## Open\n\n"
            "- **#1** — the thing — blocked on his ruling · P1 · "
            "origin: **loop** · blocked-on: **human**\n"
        )
        t = self._md_target(tmp_path, tasks)
        rows = self._rows(t)
        # No WARN; the coverage OK row may appear
        assert not [r for r in rows if "contains the `blocked on` phrase" in r
                    and "while its blocked_on field is empty" in r], (
            "a title backed by blocked-on: **human** is not a contradiction: %r"
            % rows)

    # --- Direction 2: the false-green the check does NOT close ---

    def test_a_stale_nonempty_blocker_passes_silently(self, tmp_path):
        # The named false-green (#590's stale-blocker case): a title claiming
        # blocked-ness where blocked_on is genuinely NON-empty but names an
        # already-LANDED blocker. The check sees a populated field and stays
        # quiet — which is the documented gap, not a defect. This test PINS
        # the gap: if someone "fixes" it here without the blocker-landing
        # audit (#590), this test goes red and names the overreach.
        td = self._cut_over_store(tmp_path, blocked_on="#11")
        import ledger_parse, sqlite3
        conn = sqlite3.connect(
            f"file:{ledger_parse.store_path(td / '.dreamwork')}?mode=ro", uri=True)
        try:
            blocker = conn.execute(
                "select state from task where id = 11").fetchone()
        finally:
            conn.close()
        assert blocker == ("landed",), "fixture must name an actually landed blocker"
        warns = self._rows(td, lint.WARN)
        assert not any("while its blocked_on field is empty" in d for d in warns), (
            "Direction 2 documented gap: a populated blocked_on (even a stale "
            "one) makes the check quiet by design — closing this needs #590's "
            "blocker-landing audit, not a title check. If this test went red, "
            "the check overreached into territory it cannot judge: %r" % warns)

    # --- store-mode fixtures (the real defect site) ---

    def _cut_over_store(self, tmp_path, *, blocked_on=None, title=None):
        """A post-cutover target whose ``.dreamwork/`` store has ONE open
        entry carrying a 'blocked on' title claim. Returns the TARGET ROOT
        (so ``_rows`` finds ``.dreamwork/`` inside it the same way the
        markdown fixtures do). The blocked_on column is set directly."""
        import importlib.machinery, importlib.util, io
        import sqlite3, ledger_parse, ledger_store
        repo = Path(__file__).resolve().parent
        loader = importlib.machinery.SourceFileLoader(
            "ud_dw_tasks_migrate", str(repo / "ud-dw-tasks-migrate"))
        spec = importlib.util.spec_from_loader("ud_dw_tasks_migrate", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        t = fresh(tmp_path)
        td = t / ".dreamwork"
        td.mkdir()
        # Next id 12 with #10 (open) and #11 (landed) so the seed's
        # MAX(id)+1 == header check holds.
        fixture = (
            "# Task ledger\n\nNext id: **12**\n\n## Open\n\n"
            "- **#10** — placeholder · P2 · origin: **loop**\n\n"
            "## Recently landed\n\n"
            "- **#11** — a landed entry · origin: **loop** (abc1234)\n")
        (td / "tasks.md").write_text(fixture)
        mod.perform_cutover(str(td), out=io.StringIO())
        assert ledger_parse.source_of_truth(td) == "store"
        # Set #10's title and body head line to carry the claim, and
        # optionally its blocked_on column. store_entries returns the verbatim
        # body for headed entries (the import shape), so both the title column
        # AND the body's head line must carry the claim — that is what the real
        # defect data looks like (#630/#631/#641 carry it in both places).
        ttl = title or "build the thing — blocked on his ruling"
        db = ledger_parse.store_path(td)
        conn = sqlite3.connect(str(db))
        conn.execute("UPDATE task SET title = ? WHERE id = 10", (ttl,))
        conn.execute(
            "UPDATE task SET body = ? WHERE id = 10",
            (f"- **#10** — {ttl} · P2 · origin: **loop**",))
        if blocked_on is not None:
            conn.execute(
                "UPDATE task SET blocked_on = ? WHERE id = 10", (blocked_on,))
        conn.commit()
        conn.close()
        return t

    def test_store_mode_title_claim_empty_blocked_on_warns(self, tmp_path):
        # The production defect shape: store mode, title carries "blocked on",
        # blocked_on column is NULL. This is #630/#631/#641's actual mode.
        td = self._cut_over_store(tmp_path)
        warns = self._rows(td, lint.WARN)
        assert any("#10" in d and "blocked on his ruling" in d for d in warns), (
            "store mode: a title claiming 'blocked on' with NULL blocked_on "
            "must WARN, naming the id and title fragment: %r" % warns)

    def test_store_mode_backed_claim_is_clean(self, tmp_path):
        # Store mode happy path: title claims "blocked on", blocked_on column
        # is populated. The structured field backs the title — not a
        # contradiction.
        td = self._cut_over_store(tmp_path, blocked_on="#614")
        rows = self._rows(td)
        assert not any("while its blocked_on field is empty" in r for r in rows), (
            "store mode: a populated blocked_on backs the title claim: %r" % rows)

    def test_store_mode_whitespace_blocked_on_still_warns(self, tmp_path):
        # A whitespace-only blocked_on is empty in truth. The check strips
        # whitespace before testing, so it must WARN as if the column were
        # NULL — a literal comparison would let "   " through silently.
        td = self._cut_over_store(tmp_path, blocked_on="   ")
        warns = self._rows(td, lint.WARN)
        assert any("#10" in d for d in warns), warns

    def test_coverage_row_when_claim_is_backed(self, tmp_path):
        # #430: a check whose subject exists must be VISIBLE once it examined
        # something. A backed claim produces an OK coverage row, not silence.
        td = self._cut_over_store(tmp_path, blocked_on="#614")
        rep = lint.Report()
        lint.check_title_blocked_claim(td / ".dreamwork", rep)
        oks = [d for lvl, w, d in rep.rows if w == "tasks.md" and lvl == lint.OK]
        assert any("containing the `blocked on` phrase" in d for d in oks), (
            "a backed claim must produce a coverage OK row, not silence: %r" % oks)

    def test_silent_when_no_title_claims_blocked(self, tmp_path):
        # Pre-adoption: no title makes a blocked-ness claim. Silence is
        # correct — a row that is always present is a row nobody reads.
        tasks = (
            "# Tasks\n\nNext id: **2**\n\n## Open\n\n"
            "- **#1** — a plain task · P2 · origin: **loop**\n"
        )
        t = self._md_target(tmp_path, tasks)
        assert self._rows(t) == [], self._rows(t)

    def test_absent_ledger_is_silent_not_vacuous(self, tmp_path):
        # No ledger at all: the check records a skip (#611) rather than
        # claiming it examined entries. A skip is the honest answer.
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        rep = lint.Report()
        lint.check_title_blocked_claim(dw, rep)
        assert not any(lvl == lint.ERROR for lvl, _, _ in rep.rows), rep.render()
        # The skip is recorded for check_ledger_skips to render
        assert "check_title_blocked_claim" in rep.ledger_skips, rep.ledger_skips


class TestSubdecisions:
    """#421 B: a fold that drops a declared sub-decision is an ERROR.

    The motivating defect is `#275`'s Q3/Q5/Q6 — unanswered for days with
    nothing noticing, because a multi-part ask can be half-answered and the
    entry folded on the strength of the parts that were. The buildable half
    of his ruling is a lint check, and recognising a sub-decision is
    DECLARED (`**Sub-decisions:**` with backticked `Q1`) rather than guessed
    from prose
    — the corpus labels decisions in freeform text, and inferring them is
    the half-working-regex failure this repo distrusts most.
    """

    def build(self, tmp_path, answered_entries):
        """`answered_entries`: list of (title, body) under `## Answered`."""
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        body = "\n\n".join(f"- **{title}**\n{b}" for title, b in answered_entries)
        (dw / "questions.md").write_text(
            "# Questions\n\n## Open\n\n## Answered\n\n" + body + "\n")
        return t

    def rows(self, t):
        rep = lint.Report()
        lint.check_subdecisions(t / ".dreamwork", lint.load_watch(), rep)
        return [d for lvl, w, d in rep.rows if w == "questions.md"]

    def test_a_dropped_subdecision_is_an_error(self, tmp_path):
        # THE red test: Q1 is resolved by a `Rec **Q1**`, Q2 appears nowhere.
        # This is the half-answer the check exists for. (Production line whose
        # change reds it: the `resolved` membership test in check_subdecisions
        # — make it unconditionally resolve and Q2 stops erroring.)
        t = self.build(tmp_path, [(
            "An ask with two sub-decisions",
            "  **Sub-decisions:** `Q1`, `Q2`\n\n"
            "  → answered (2026-07-29 01:17): rec on Q1.\n\n"
            "  Rec **Q1** is the chosen layout.\n",
        )])
        rep = lint.Report()
        lint.run_checks(t / ".dreamwork", lint.load_watch(), rep)
        errs = [d for lvl, w, d in rep.rows
                if w == "questions.md" and lvl == lint.ERROR]
        assert any("Q2" in e and "drops declared sub-decision" in e for e in errs), errs

    def test_every_declared_label_named_is_clean(self, tmp_path):
        # The same entry with Q2 named in the head carries it forward and is
        # clean — naming-it is both the resolution and the record (no second
        # store).
        t = self.build(tmp_path, [(
            "An ask with two sub-decisions",
            "  **Sub-decisions:** `Q1`, `Q2`\n\n"
            "  → answered (2026-07-29 01:17): rec on Q1; Q2 carried "
            "forward, still open.\n",
        )])
        rep = lint.Report()
        lint.run_checks(t / ".dreamwork", lint.load_watch(), rep)
        assert not any(lvl == lint.ERROR and w == "questions.md"
                       for lvl, w, _ in rep.rows), rep.render()

    def test_an_answer_bullet_resolves_a_label(self, tmp_path):
        # A label named only in an `Answer (via watch…)` follow-up (lifted into
        # `follows` for Answered entries, not the head, not a Rec) is still
        # resolved — the evidence scan covers the whole folded entry.
        t = self.build(tmp_path, [(
            "An ask",
            "  **Sub-decisions:** `Q1`\n\n"
            "  → answered (2026-07-29 01:17): done.\n"
            "  - **Answer (via watch, 2026-07-29 01:17):** Q1 yes.\n",
        )])
        rep = lint.Report()
        lint.check_subdecisions(t / ".dreamwork", lint.load_watch(), rep)
        assert not any(lvl == lint.ERROR for lvl, _, _ in rep.rows), rep.render()

    def test_an_entry_without_a_declaration_is_not_examined(self, tmp_path):
        # History handling: no marker -> not under the rule, so no ERROR and
        # no coverage row. Pre-adoption silence matches every other clean
        # questions.md check (one OK row, from check_questions).
        t = self.build(tmp_path, [(
            "A legacy multi-part ask",
            "  → answered (2026-07-25): rec. Q1 settled, Q2 not mentioned.\n",
        )])
        rep = lint.Report()
        lint.check_subdecisions(t / ".dreamwork", lint.load_watch(), rep)
        assert not any(lvl == lint.ERROR for lvl, _, _ in rep.rows), rep.render()
        # No coverage row: the fixture has no declaration anywhere.
        assert not any("#421 B" in d for _, _, d in rep.rows), rep.render()

    def test_pre_adoption_is_silent_one_ok_row(self, tmp_path):
        # The convention a coordinator's feedback had to reconcile with: a
        # clean questions.md shows exactly ONE OK row (from check_questions),
        # and a second row here on every target would break that. Pre-adoption
        # (no declaration marker anywhere) this check is silent — so a full
        # run still prints one OK for questions.md, not two.
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "questions.md").write_text(
            "# Questions\n\n## Open\n\n## Answered\n")
        rep = lint.Report()
        lint.run_checks(dw, lint.load_watch(), rep)
        oks = [lvl for lvl, w, _ in rep.rows if w == "questions.md"
               and lvl == lint.OK]
        assert oks == [lint.OK], f"pre-adoption should be exactly one OK: {rep.render()}"

    def test_a_marker_on_an_open_entry_makes_the_check_visible(self, tmp_path):
        # #430, reconciled with the one-OK-row convention: the coverage row
        # appears once a declaration marker exists ANYWHERE (open or
        # answered), so the check is visible the moment it has a subject —
        # even before any fold. A marker on an OPEN entry (#275 today) is a
        # future subject; the row reports the folded-side examination (here
        # zero, because the marker is under ## Open), and never ERRORs.
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "questions.md").write_text(
            "# Questions\n\n## Open\n\n"
            "- **An open ask with a marker.**\n"
            "  **Sub-decisions:** `Q1`, `Q2`\n\n"
            "## Answered\n")
        rep = lint.Report()
        lint.check_subdecisions(dw, lint.load_watch(), rep)
        assert not any(lvl == lint.ERROR for lvl, _, _ in rep.rows), rep.render()
        ok_rows = [d for lvl, _, d in rep.rows if lvl == lint.OK]
        assert any("0 folded" in d and "0 declared" in d for d in ok_rows), ok_rows

    def test_a_label_only_in_the_declaration_is_dropped(self, tmp_path):
        # Q1 appears ONLY inside `**Sub-decisions:** \`Q1\`` and nowhere else.
        # The declaration line is excluded from the evidence, so this errors —
        # a fold cannot satisfy the rule by merely restating what it asked.
        t = self.build(tmp_path, [(
            "An ask",
            "  **Sub-decisions:** `Q1`\n\n"
            "  → answered (2026-07-29 01:17): rec, no label named.\n",
        )])
        errs = self.rows(t)
        assert any("Q1" in e and "drops declared sub-decision" in e for e in errs), errs

    def test_the_live_repo_is_dormant_not_broken(self, tmp_path):
        # Dogfood: the live corpus predates the marker (zero declarations), so
        # the check examines nothing and stays silent — correct pre-adoption.
        # A red here means a declaration landed and lint must now reason about
        # it, which is a real finding for the coordinator (who owns the asks).
        rep = lint.Report()
        lint.check_subdecisions(lint.SKILL_DIR / ".dreamwork", lint.load_watch(), rep)
        assert not any(lvl == lint.ERROR for lvl, _, _ in rep.rows), rep.render()


def test_the_subdecision_row_names_open_declarations_awaiting_a_fold(tmp_path):
    """`0 folded, 0 checked` reads as "nothing here" when it means "adopted,
    waiting for a fold" — two different facts, and a reader needs both. On the
    day the convention landed the row was exactly 0/0, so the pending count is
    what says the check has a future subject rather than no subject at all.

    Production line: `_answered_split`, whose offset defines the open half.
    Sabotaging it to a byte before the marker drops the clause; that is the
    change that reds this test.
    """
    dw = tmp_path / ".dreamwork"
    dw.mkdir()
    # PRECONDITION, derived: the fixture puts the declaration in the OPEN half
    # and nothing in the answered half, so a wrong split cannot pass by luck.
    raw = (
        "# Questions for the human\n\n## Open\n"
        "- **P2 · 2026-07-29 — a multi-part ask**\n\n"
        "  **Sub-decisions:** `Q1`, `Q2`\n\n"
        "  body prose.\n\n"
        "## Answered\n\n"
        "- **P3 · 2026-07-29 — an unrelated fold** → answered (2026-07-29): done.\n"
    )
    (dw / "questions.md").write_text(raw)
    split = lint._answered_split(raw)
    assert split > 0, "fixture has no anchored `## Answered` heading"
    assert raw.index("**Sub-decisions:**") < split, (
        "fixture precondition broken: the declaration must sit in the OPEN "
        "half for this test to distinguish a right split from a wrong one")

    rep = lint.Report()
    lint.check_subdecisions(dw, lint.load_watch(), rep)
    rows = [r for r in rep.rows if "#421 B" in r[-1]]
    assert rows, "no #421 B coverage row emitted for a file with a declaration"
    line = rows[0][-1]
    assert "1 open ask declares sub-decisions" in line, line
    assert "0 folded entries examined" in line, line


class TestResolutionMarkerOutsideTitle:
    """#411: a `→ … (date)` marker inside a WRAPPED bold title is invisible to
    `answered_at`, which reads only the body. Wrapping itself is ordinary — the
    live corpus wraps 30 of 65 titles — so the check must fire on the marker's
    position, never on the wrap."""

    def build(self, tmp_path, entries):
        # `entries`: list of raw entry text, each starting with `- **`.
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "questions.md").write_text(
            "# Questions\n\n## Open\n\n## Answered\n\n"
            + "\n\n".join(entries) + "\n")
        return t

    def rows(self, t):
        rep = lint.Report()
        lint.check_resolution_marker_outside_title(
            t / ".dreamwork", lint.load_watch(), rep)
        return [(lvl, d) for lvl, w, d in rep.rows if w == "questions.md"]

    def test_a_marker_inside_a_wrapped_title_errors_and_is_named(self, tmp_path):
        t = self.build(tmp_path, [
            # the shape that actually happened: the title runs on to a second
            # line and the resolution head was inserted before it closed
            "- **P1 · 2026-07-28 — a question whose title runs on\n"
            "  → answered (2026-07-28 01:43): the answer.\n"
            "  and here the title finally closes.** Body prose follows.\n",
            "- **P2 · 2026-07-28 — a well-formed entry**\n"
            "  → answered (2026-07-28 02:00): fine.\n",
        ])
        rows = self.rows(t)
        assert rows and rows[0][0] == lint.ERROR, rows
        assert "INSIDE the wrapped bold title" in rows[0][1]
        assert "title runs on" in rows[0][1], rows[0][1]

    def test_a_legally_wrapped_title_with_the_marker_in_the_body_is_silent(self, tmp_path):
        # The precondition this check depends on is that at least one title
        # wraps -- derived, so it cannot quietly lose its subject. One entry
        # here wraps WITHOUT a marker in the span, which is the legal case.
        t = self.build(tmp_path, [
            "- **P1 · 2026-07-28 — a title that wraps across\n"
            "  two lines legally.** \n"
            "  → answered (2026-07-28 01:43): the marker is in the body.\n",
            "- **P2 · 2026-07-28 — a one-line title**\n"
            "  → answered (2026-07-28 02:00): also fine.\n",
        ])
        # The precondition this check depends on, asserted where it can expire:
        # exactly one of these two titles wraps, derived rather than trusted, so
        # the fixture cannot drift into having no subject without failing here.
        raw = (t / ".dreamwork/questions.md").read_text()
        import re as _re
        wraps = [m.group(0).split("\n")[0]
                 for m in _re.finditer(r"(?m)^- \*\*.*?(?=^- \*\*|\Z)", raw, _re.S)
                 if m.group(0).split("\n")[0].count("**") < 2]
        assert len(wraps) == 1, wraps
        assert self.rows(t) == []

    def test_no_wrapped_title_at_all_is_silent_because_the_defect_is_impossible(self, tmp_path):
        t = self.build(tmp_path, [
            "- **P1 · 2026-07-28 — one line**\n"
            "  → answered (2026-07-28 01:43): fine.\n",
        ])
        # Silent, like its sibling: check_questions owns this file's OK row.
        # With no wrapped title the defect is IMPOSSIBLE rather than merely
        # unobserved, so silence is honest here and no row is owed.
        assert self.rows(t) == []


class TestResolutionMarkerAfterSubbullet:
    """#467: a `→ answered` marker written AFTER a nested `- **` sub-bullet is
    absorbed into that sub-bullet as a wrapped continuation (`_parse_entries`
    invariant 3), so it never reaches `body` and `answered_at` returns None —
    the fold looks done, and the #411 WARN names a "dropped" marker that was
    written, just in the wrong place. Third instance of the #411 family:
    measured 2026-07-29 folding his #445 answer; moving the marker above the
    answer line fixed it instantly."""

    def build(self, tmp_path, entries):
        # `entries`: list of raw entry text, each starting with `- **`.
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "questions.md").write_text(
            "# Questions\n\n## Open\n\n## Answered\n\n"
            + "\n\n".join(entries) + "\n")
        return t

    def rows(self, t):
        rep = lint.Report()
        lint.check_resolution_marker_after_subbullet(
            t / ".dreamwork", lint.load_watch(), rep)
        return [(lvl, d) for lvl, w, d in rep.rows if w == "questions.md"]

    def parsed(self, t):
        import watch
        return watch.parse_answered(
            (t / ".dreamwork/questions.md").read_text())

    def test_a_marker_after_the_answer_bullet_errors_and_is_named(self, tmp_path):
        t = self.build(tmp_path, [
            # the shape that actually happened: the fold appended the marker
            # after his Answer bullet, where the parser swallows it
            "- **P1 · 2026-07-29 — #998: a settled ask with a stranded marker**\n"
            "  some body prose\n"
            "  - **Answer (via watch, 2026-07-29 03:45):** rec\n"
            "  → answered (2026-07-29 03:50): rec — recorded.\n",
            "- **P1 · 2026-07-29 — #999: a well-formed entry**\n"
            "  → answered (2026-07-29 03:50): rec — recorded.\n"
            "  - **Answer (via watch, 2026-07-29 03:45):** rec\n",
        ])
        # PRECONDITION, derived from the real parser — never trusted from the
        # fixture's layout: the stranded marker must be genuinely unreachable
        # (`answered_at` None) while the well-formed entry's is seen, and the
        # stranded marker must be present in what the parser DID absorb (the
        # answer's follow text), or the check has no subject and every
        # assertion below is vacuous.
        import watch
        by = {it["title"]: it for it in self.parsed(t)}
        bad = by["P1 · 2026-07-29 — #998: a settled ask with a stranded marker"]
        good = by["P1 · 2026-07-29 — #999: a well-formed entry"]
        assert watch.answered_at(bad["body"]) is None
        assert watch.answered_at(good["body"]) == "2026-07-29 03:50"
        assert any("→ answered (2026-07-29" in f["text"]
                   for f in bad["follows"]), bad["follows"]
        rows = self.rows(t)
        assert rows and rows[0][0] == lint.ERROR, rows
        assert "stranded marker" in rows[0][1]
        # the repair instruction: where the marker must go
        assert "above" in rows[0][1] and "sub-bullet" in rows[0][1]
        assert "well-formed" not in rows[0][1]

    def test_a_marker_above_the_answer_bullet_is_silent(self, tmp_path):
        t = self.build(tmp_path, [
            "- **P1 · 2026-07-29 — #999: marker at the head of the body**\n"
            "  → answered (2026-07-29 03:50): rec — recorded.\n"
            "  - **Answer (via watch, 2026-07-29 03:45):** rec\n",
        ])
        # PRECONDITION: the marker is genuinely reachable here, or "silent"
        # proves nothing about the position distinction.
        import watch
        (it,) = self.parsed(t)
        assert watch.answered_at(it["body"]) == "2026-07-29 03:50"
        assert self.rows(t) == []

    def test_a_blank_line_releases_the_marker_and_is_silent(self, tmp_path):
        # The parser's invariant 3 ends at a blank line, so a marker after a
        # sub-bullet WITH a blank line between lands back in the body. This
        # pins the check to the parser's truth: it must not cry ERROR on a
        # marker the reader can see.
        t = self.build(tmp_path, [
            "- **P1 · 2026-07-29 — #997: blank-separated marker**\n"
            "  - **Answer (via watch, 2026-07-29 03:45):** rec\n"
            "\n"
            "  → answered (2026-07-29 03:50): rec — recorded.\n",
        ])
        import watch
        (it,) = self.parsed(t)
        assert watch.answered_at(it["body"]) == "2026-07-29 03:50"
        assert self.rows(t) == []

    def test_a_note_bullet_strands_the_marker_just_the_same(self, tmp_path):
        # The absorption is invariant 3's, not the Answer tag's: a Note
        # sub-bullet swallows a following marker identically.
        t = self.build(tmp_path, [
            "- **P1 · 2026-07-29 — #996: marker after a note**\n"
            "  - **Note (human, via watch, 2026-07-29 03:40):** a thought\n"
            "  → answered (2026-07-29 03:50): rec — recorded.\n",
        ])
        import watch
        (it,) = self.parsed(t)
        assert watch.answered_at(it["body"]) is None
        assert any("→ answered (2026-07-29" in f["text"]
                   for f in it["follows"]), it["follows"]
        rows = self.rows(t)
        assert rows and rows[0][0] == lint.ERROR, rows
        assert "marker after a note" in rows[0][1]



class TestBriefLaneOwns:
    """#465: a worktree-naming brief must declare its owned paths.

    The lane-containment guard (dev/lane_guard.py) refuses a main-checkout
    commit touching a dispatched lane's owned paths — but only when the lane's
    brief declares them. A worktree brief with no `Lane-owns:` line is a lane
    the guard cannot protect, so the omission is loud at brief-write time.

    Production lines named per test (what must change for it to fail):
    - flagged: the `if not owned` branch in check_brief_lane_owns that adds the
      ERROR for a worktree brief declaring no Lane-owns paths
    - cutoff content: _resolve_lane_owns_cutoff + LANE_OWNS_PHRASE
    - precondition: live tree has at least one brief containing `.worktrees/`
      (a check that silently matches nothing passes forever)
    """

    PHRASE = lint.LANE_OWNS_PHRASE

    def _git_repo(self, tmp_path):
        import subprocess
        t = fresh(tmp_path)

        def git(*a, check=True):
            return subprocess.run(
                ["git", "-C", str(t), *a],
                capture_output=True, text=True, check=check)

        git("init", "-q")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        return t, git

    def _brief_with_worktree(self, briefs_dir, name, owns=None):
        briefs_dir.mkdir(parents=True, exist_ok=True)
        body = "# Brief\n\nWorktree: `.worktrees/x` on `wt/x`.\n\n"
        if owns is not None:
            body += f"Lane-owns: {owns}\n"
        (briefs_dir / name).write_text(body, encoding="utf-8")

    def test_a_post_cutoff_worktree_brief_without_lane_owns_is_flagged(
            self, tmp_path):
        """Production line: the missing-ownership ERROR in
        check_brief_lane_owns — a post-cutoff brief that names `.worktrees/`
        but declares no `Lane-owns:` must be named by basename.
        """
        import time
        t, git = self._git_repo(tmp_path)
        (t / "SKILL.md").write_text(
            f"# skill\n\n{self.PHRASE}\n", encoding="utf-8")
        git("add", "SKILL.md")
        git("commit", "-qm", "lane-owns rule lands")
        time.sleep(1.1)
        briefs = t / ".dreamwork" / "docs" / "briefs"
        # THE defect: worktree named, no Lane-owns line at all.
        self._brief_with_worktree(briefs, "999-wt-noown.md")
        git("add", ".dreamwork/docs/briefs/999-wt-noown.md")
        git("commit", "-qm", "worktree brief, no Lane-owns")

        # Precondition, derived: the brief is a worktree brief AND after cutoff
        # AND declares no ownership — the three facts the ERROR depends on.
        text = (briefs / "999-wt-noown.md").read_text(encoding="utf-8")
        assert lint._brief_names_worktree(text)
        assert lint._parse_lane_owns(text) == []

        rep = lint.Report()
        lint.check_brief_lane_owns(t / ".dreamwork", rep)
        errors = [d for lvl, w, d in rep.rows
                  if lvl == lint.ERROR and w == "briefs"]
        assert len(errors) == 1, rep.render()
        assert "999-wt-noown.md" in errors[0], errors[0]
        assert "Lane-owns" in errors[0], errors[0]

    def test_a_post_cutoff_worktree_brief_with_lane_owns_is_clean(
            self, tmp_path):
        """Production line: the `if not owned` branch is NOT taken when the
        brief declares ownership — the OK coverage line fires instead.
        """
        import time
        t, git = self._git_repo(tmp_path)
        (t / "SKILL.md").write_text(
            f"# skill\n\n{self.PHRASE}\n", encoding="utf-8")
        git("add", "SKILL.md")
        git("commit", "-qm", "lane-owns rule lands")
        time.sleep(1.1)
        briefs = t / ".dreamwork" / "docs" / "briefs"
        self._brief_with_worktree(briefs, "998-wt-own.md",
                                  owns="watch.py, dev/capture/")
        git("add", ".dreamwork/docs/briefs/998-wt-own.md")
        git("commit", "-qm", "worktree brief, declares ownership")

        # Precondition, derived: ownership actually parses to a non-empty set.
        text = (briefs / "998-wt-own.md").read_text(encoding="utf-8")
        owned = lint._parse_lane_owns(text)
        assert owned == ["watch.py", "dev/capture/"], owned

        rep = lint.Report()
        lint.check_brief_lane_owns(t / ".dreamwork", rep)
        errors = [d for lvl, w, d in rep.rows
                  if lvl == lint.ERROR and w == "briefs"]
        assert errors == [], rep.render()

    def test_a_pre_cutoff_worktree_brief_is_grandfathered(self, tmp_path):
        """Production line: the time-based grandfather branch in
        check_brief_lane_owns — a worktree brief written before the rule
        landed in SKILL.md is not flagged.
        """
        import time
        t, git = self._git_repo(tmp_path)
        briefs = t / ".dreamwork" / "docs" / "briefs"
        self._brief_with_worktree(briefs, "100-old-wt.md")
        (t / "SKILL.md").write_text("# skill\n\nno lane-owns rule yet\n",
                                    encoding="utf-8")
        git("add", "SKILL.md", ".dreamwork/docs/briefs/100-old-wt.md")
        git("commit", "-qm", "worktree brief before rule")
        time.sleep(1.1)
        (t / "SKILL.md").write_text(
            f"# skill\n\n{self.PHRASE}\n", encoding="utf-8")
        git("add", "SKILL.md")
        git("commit", "-qm", "lane-owns rule lands later")

        rep = lint.Report()
        lint.check_brief_lane_owns(t / ".dreamwork", rep)
        errors = [d for lvl, w, d in rep.rows
                  if lvl == lint.ERROR and w == "briefs"]
        assert errors == [], rep.render()

    def test_no_worktree_naming_brief_is_silent_not_a_clean_pass(
            self, tmp_path):
        """Silence is honest here: with no worktree-naming brief, the rule has
        nothing to examine. (A check that matched nothing would pass forever,
        so the live-tree precondition is asserted in the coverage line.)
        """
        t, git = self._git_repo(tmp_path)
        (t / "SKILL.md").write_text(
            f"# skill\n\n{self.PHRASE}\n", encoding="utf-8")
        git("add", "SKILL.md")
        git("commit", "-qm", "lane-owns rule lands")
        briefs = t / ".dreamwork" / "docs" / "briefs"
        # A brief that does NOT name a worktree — not a dispatched lane.
        briefs.mkdir(parents=True)
        (briefs / "123-shared.md").write_text(
            "# Brief\n\nWork in the shared tree.\n", encoding="utf-8")

        rep = lint.Report()
        lint.check_brief_lane_owns(t / ".dreamwork", rep)
        rows = [d for lvl, w, d in rep.rows if w == "briefs"]
        assert rows == [], rep.render()

    def test_an_empty_lane_owns_payload_is_treated_as_absent(self, tmp_path):
        """A declared-but-empty `Lane-owns:` (no paths after the colon) is a
        forgotten fill-in, not a deliberate empty ownership — so it flags like
        a missing line. Production line: _parse_lane_owns returning [] on an
        empty payload, which the ERROR branch then catches.
        """
        import time
        t, git = self._git_repo(tmp_path)
        (t / "SKILL.md").write_text(
            f"# skill\n\n{self.PHRASE}\n", encoding="utf-8")
        git("add", "SKILL.md")
        git("commit", "-qm", "lane-owns rule lands")
        time.sleep(1.1)
        briefs = t / ".dreamwork" / "docs" / "briefs"
        self._brief_with_worktree(briefs, "997-empty.md", owns="")
        git("add", ".dreamwork/docs/briefs/997-empty.md")
        git("commit", "-qm", "worktree brief, empty Lane-owns")

        # Precondition: the empty payload parses to no owned paths.
        text = (briefs / "997-empty.md").read_text(encoding="utf-8")
        assert lint._parse_lane_owns(text) == []

        rep = lint.Report()
        lint.check_brief_lane_owns(t / ".dreamwork", rep)
        errors = [d for lvl, w, d in rep.rows
                  if lvl == lint.ERROR and w == "briefs"]
        assert len(errors) == 1, rep.render()
        assert "997-empty.md" in errors[0]


class TestLaneContainmentBackstop:
    """#468: a path a live lane owns must not be dirty in the MAIN CHECKOUT.

    #465's pre-commit guard refuses the commit; this catches the state one step
    earlier — the uncommitted stray edit, which is what actually aborted a held
    merge. Real git worktrees here, on purpose: the check's whole subject is
    git's worktree registry and a real working tree's dirtiness, so faking
    either would put the fake in front of the thing under test.

    Production lines named per test (what must change for it to fail):
    - the ERROR branch in check_lane_containment_backstop
    - the `if examined and not found` guard on the clean-bill OK row
    - _live_lane_worktrees' `branch.startswith("wt/")` lane test
    """

    def _repo_with_lane(self, tmp_path, owns="watch.py"):
        import subprocess
        t = fresh(tmp_path)

        def git(*a, cwd=None):
            return subprocess.run(
                ["git", "-C", str(cwd or t), *a],
                capture_output=True, text=True, check=True)

        git("init", "-q")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        (t / "watch.py").write_text("# watch\n", encoding="utf-8")
        (t / "other.py").write_text("# other\n", encoding="utf-8")
        briefs = t / ".dreamwork" / "docs" / "briefs"
        briefs.mkdir(parents=True, exist_ok=True)
        (briefs / "900-lane.md").write_text(
            "# Brief\n\nWorktree: `.worktrees/lane` on `wt/lane`.\n\n"
            f"Lane-owns: {owns}\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-qm", "base")
        git("worktree", "add", "-q", "-b", "wt/lane", str(t / ".worktrees" / "lane"))
        return t, git

    def _rows(self, t):
        rep = lint.Report()
        lint.check_lane_containment_backstop(t / ".dreamwork", rep)
        return rep

    def test_a_lane_owned_path_dirty_in_the_main_checkout_is_an_error(self, tmp_path):
        """Production line: the ERROR branch in check_lane_containment_backstop.

        Reproduces the #465 incident exactly: the lane's file edited in the main
        tree, uncommitted.
        """
        t, _ = self._repo_with_lane(tmp_path)

        # Precondition, derived: the lane is visible AND declares ownership, or
        # the intersection below is empty by construction and proves nothing.
        lanes = lint._live_lane_worktrees(t)
        assert [b for _, b in lanes] == ["wt/lane"], lanes
        owned = lint._parse_lane_owns(
            (t / ".dreamwork" / "docs" / "briefs" / "900-lane.md")
            .read_text(encoding="utf-8"))
        assert owned == ["watch.py"], owned

        (t / "watch.py").write_text("# a lane's stray edit\n", encoding="utf-8")
        assert "watch.py" in (lint._dirty_paths(t) or [])

        rep = self._rows(t)
        errors = [d for lvl, w, d in rep.rows
                  if lvl == lint.ERROR and w == "lane-containment"]
        assert len(errors) == 1, rep.render()
        assert "watch.py" in errors[0] and "wt/lane" in errors[0]

    def test_the_clean_bill_never_appears_beside_a_finding(self, tmp_path):
        """Production line: the `if examined and not found` guard on the OK row.

        Found by red-proofing the check itself: the first version printed the
        ERROR and a clean bill saying no owned path was dirty, in one run. A
        check that contradicts itself gets read as noise.
        """
        t, _ = self._repo_with_lane(tmp_path)
        (t / "watch.py").write_text("# stray\n", encoding="utf-8")
        rep = self._rows(t)
        levels = {lvl for lvl, w, _ in rep.rows if w == "lane-containment"}
        assert lint.ERROR in levels, rep.render()
        assert lint.OK not in levels, rep.render()

    def test_a_path_no_lane_owns_is_not_flagged_and_earns_the_clean_bill(self, tmp_path):
        """The ordinary case: the coordinator commits its own files while a lane
        is out. Frictionless, and the OK row states the coverage.
        """
        t, _ = self._repo_with_lane(tmp_path)
        (t / "other.py").write_text("# coordinator's own work\n", encoding="utf-8")

        # Precondition: something IS dirty, so a pass here is a real pass and
        # not the empty-tree case wearing the same output.
        dirty = lint._dirty_paths(t) or []
        assert "other.py" in dirty and "watch.py" not in dirty, dirty

        rep = self._rows(t)
        rows = [(lvl, d) for lvl, w, d in rep.rows if w == "lane-containment"]
        assert [lvl for lvl, _ in rows] == [lint.OK], rep.render()
        assert "1 of 1" in rows[0][1]

    def test_a_worktree_that_is_not_a_lane_is_ignored(self, tmp_path):
        """Production line: _live_lane_worktrees' `wt/` branch test. A worktree
        on an ordinary branch is somebody's checkout, not a dispatched lane, so
        its files must not become untouchable in the main tree.
        """
        t, git = self._repo_with_lane(tmp_path)
        git("worktree", "add", "-q", "-b", "feature/x", str(t / ".worktrees" / "notalane"))
        lanes = lint._live_lane_worktrees(t)
        assert [b for _, b in lanes] == ["wt/lane"], lanes

    def test_a_lane_whose_brief_declares_nothing_is_silence_not_a_clean_bill(
            self, tmp_path):
        """A lane the check cannot evaluate must not be reported as safe.

        Production line: the `if not owned: continue` branch together with the
        `examined` counter — if an undeclared lane were counted, the OK row
        would claim coverage the check does not have.
        """
        t, _ = self._repo_with_lane(tmp_path, owns="")
        owned = lint._parse_lane_owns(
            (t / ".dreamwork" / "docs" / "briefs" / "900-lane.md")
            .read_text(encoding="utf-8"))
        assert owned == [], owned          # precondition: nothing declared
        (t / "watch.py").write_text("# stray, but unknowable\n", encoding="utf-8")
        rep = self._rows(t)
        assert [w for _, w, _ in rep.rows if w == "lane-containment"] == [], rep.render()


    def test_an_older_brief_for_the_same_lane_cannot_shadow_the_newer_one(
            self, tmp_path):
        """A worktree name is reused across sessions, so one lane can have
        several briefs. First-match-by-filename picked the OLDER one.

        Measured on the live tree: `wt/dreamers` matched
        `402-dreamers-shape.md` (no declaration) instead of `402-dreamers.md`,
        because `-` sorts before `.`, so the lane went unprotected while the
        coverage row still counted it — the worst combination, since the row
        reads as reassurance. Eight task ids here have more than one brief.

        Production line: the union loop in check_lane_containment_backstop
        (reverting it to `break` on first match reds this).
        """
        t, _ = self._repo_with_lane(tmp_path, owns="watch.py")
        briefs = t / ".dreamwork" / "docs" / "briefs"
        # The shadowing brief: same lane, sorts FIRST, declares nothing.
        (briefs / "900-lane-shape.md").write_text(
            "# Brief\n\nWorktree: `.worktrees/lane` on `wt/lane`.\n", encoding="utf-8")

        # Preconditions, both derived — the shadow only exists if the empty
        # brief really does sort first AND really does declare nothing.
        names = sorted(p.name for p in briefs.glob("*.md"))
        assert names.index("900-lane-shape.md") < names.index("900-lane.md"), names
        assert lint._parse_lane_owns(
            (briefs / "900-lane-shape.md").read_text(encoding="utf-8")) == []

        (t / "watch.py").write_text("# stray edit\n", encoding="utf-8")
        rep = self._rows(t)
        errors = [d for lvl, w, d in rep.rows
                  if lvl == lint.ERROR and w == "lane-containment"]
        assert len(errors) == 1, rep.render()
        assert "watch.py" in errors[0]

    def test_ownership_is_the_union_across_every_brief_naming_the_lane(
            self, tmp_path):
        """Two briefs, two different owned paths, both protected.

        Union is the safe direction: over-protecting a path costs a dispatch,
        under-protecting corrupts the disjointness invariant. Production line:
        the same union loop.
        """
        t, _ = self._repo_with_lane(tmp_path, owns="watch.py")
        briefs = t / ".dreamwork" / "docs" / "briefs"
        (briefs / "901-lane-second.md").write_text(
            "# Brief\n\nWorktree: `.worktrees/lane` on `wt/lane`.\n\n"
            "Lane-owns: other.py\n", encoding="utf-8")
        (t / "other.py").write_text("# the second brief's file\n", encoding="utf-8")
        rep = self._rows(t)
        errors = [d for lvl, w, d in rep.rows
                  if lvl == lint.ERROR and w == "lane-containment"]
        assert len(errors) == 1, rep.render()
        assert "other.py" in errors[0]


def _load_lane_guard():
    """Load dev/lane_guard.py as a module (dev/ is not a package).

    The pre-merge assertion lives there; these tests exercise it directly. The
    module is also exercised end-to-end by the CLI smoke in the lane's report,
    but a test that drives the function reaches the real decision branches.
    """
    import importlib.util
    path = lint.SKILL_DIR / "dev" / "lane_guard.py"
    spec = importlib.util.spec_from_file_location("lane_guard_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPreMergeAssertion:
    """#468 R2 — the pre-merge assertion (`dev/lane_guard.py pre-merge`).

    `git merge wt/<lane>` aborts when the main checkout's index or worktree is
    dirty with someone else's work, and the abort message names files rather
    than the reason. This is the merge-time gate the lint backstop cannot be
    (lint takes no branch argument; it fires when run, not at merge time).

    Real git worktrees here, on purpose: the check's whole subject is git's
    worktree registry and a real working tree's dirtiness, so faking either
    puts the fake in front of the thing under test. Ownership is REUSED from
    lint (``lane_owned_paths``) — these tests never re-implement Lane-owns.

    Each test names the production line whose change reds it.
    """

    def _repo(self, tmp_path, owns="laneowned/"):
        import subprocess
        t = fresh(tmp_path)

        def git(*a, cwd=None):
            return subprocess.run(
                ["git", "-C", str(cwd or t), *a],
                capture_output=True, text=True, check=True)
        git("init", "-q")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        (t / "other.py").write_text("# other\n", encoding="utf-8")
        (t / "laneowned").mkdir()
        (t / "laneowned" / ".gitkeep").write_text("", encoding="utf-8")
        briefs = t / ".dreamwork" / "docs" / "briefs"
        briefs.mkdir(parents=True)
        (briefs / "900-lane.md").write_text(
            "# Brief\n\nWorktree: `.worktrees/lane` on `wt/lane`.\n\n"
            f"Lane-owns: {owns}\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-qm", "base")
        git("worktree", "add", "-q", "-b", "wt/lane", str(t / ".worktrees" / "lane"))
        return t, git

    def test_clean_main_checkout_passes_and_states_lane_coverage(self, tmp_path, capsys):
        """The OK path: a lane is out, nothing is dirty. The pass names the lane
        and the coverage so it cannot look the same as examining nothing.

        Precondition, derived: the lane is registered AND declares ownership, or
        the OK row's `1 of 1` is a count over an empty subject.
        """
        lg = _load_lane_guard()
        t, _ = self._repo(tmp_path)
        lanes = lint._live_lane_worktrees(t)
        assert [b for _, b in lanes] == ["wt/lane"], lanes
        assert lint.lane_owned_paths(t / ".dreamwork", "wt/lane") == ["laneowned/"]

        rc = lg._pre_merge(t, "wt/lane")
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "pre-merge OK" in out and "wt/lane" in out, out
        assert "1 of 1 live lane(s) declare ownership" in out, out

    def test_a_lane_owned_dirty_path_refuses_naming_lane_path_and_action(
            self, tmp_path, capsys):
        """Production line: ``lint.lane_owned_paths`` (the shared reader).

        An UNTRACKED file under the lane's owned directory isolates the
        ownership finding from the merge-blocking-tracked dimension: it is in
        the dirty set the backstop sees (untracked counts), but it is neither
        staged nor unstaged-tracked, and it is not added by the branch — so the
        ONLY reason to refuse is lane ownership. Breaking ``lane_owned_paths``
        to return [] makes this test pass when it should refuse: non-circular,
        because the reader is the backstop's verbatim logic (the pre-existing
        ownership decision), not a seam this diff introduced.
        """
        lg = _load_lane_guard()
        t, _ = self._repo(tmp_path)
        (t / "laneowned" / "stray.txt").write_text("# a lane's stray edit\n",
                                                   encoding="utf-8")
        # Precondition: the stray file is dirty, untracked, and not added by the
        # lane branch — so only ownership can flag it.
        dirty = lint._dirty_paths(t)
        assert "laneowned/stray.txt" in dirty, dirty
        classified = lg._classify_status(t)
        assert classified is not None
        staged, unstaged, untracked = classified
        assert "laneowned/stray.txt" in untracked
        assert "laneowned/stray.txt" not in staged + unstaged
        assert "laneowned/stray.txt" not in (lg._merge_added_paths(t, "wt/lane") or [])

        rc = lg._pre_merge(t, "wt/lane")
        err = capsys.readouterr().err
        assert rc == 1, err
        assert "laneowned/stray.txt" in err and "wt/lane" in err, err
        # The one action #465's resolution was: retire the finished worktree.
        assert "git worktree remove" in err, err
        # It must not move the work itself.
        assert "stash" not in err.lower() and "git reset" not in err.lower(), err

    def test_staged_and_unstaged_coordinator_work_refuses_without_stash(
            self, tmp_path, capsys):
        """Production line: the ``blocking_tracked`` branch in ``_pre_merge``
        (``set(staged) | set(unstaged)``). This dimension is NEW — the lint
        backstop is silent on the coordinator's own uncommitted work because no
        lane owns it, yet a merge aborts on it regardless. So the red reaches a
        branch this diff adds; that is honest, not circular.
        """
        lg = _load_lane_guard()
        t, git = self._repo(tmp_path)
        # Staged coordinator work + unstaged tracked work, both non-lane-owned.
        (t / "other.py").write_text("# staged change\n", encoding="utf-8")
        git("add", "other.py")
        (t / "other.py").write_text("# and an unstaged change on top\n",
                                    encoding="utf-8")
        # Precondition: other.py is non-lane-owned, so ownership stays silent.
        assert "other.py" not in lint.lane_owned_paths(t / ".dreamwork", "wt/lane")

        rc = lg._pre_merge(t, "wt/lane")
        err = capsys.readouterr().err
        assert rc == 1, err
        assert "other.py" in err, err
        assert "Commit or unwind" in err, err
        # It offers NO destructive command — it moves no work. (The word
        # "stashes" may appear only inside the guarantee "never stashes",
        # never as an action to take, so assert on the command, not the word.)
        for cmd in ("git stash", "git reset", "git checkout"):
            assert cmd not in err, (cmd, err)

    def test_an_untracked_file_the_merge_would_clobber_refuses(self, tmp_path, capsys):
        """Production line: ``_merge_added_paths`` + the clobber intersection.

        The lane branch adds `clobber.txt`; an untracked `clobber.txt` in the
        main tree would be overwritten by the merge. Precondition, derived: the
        branch really does add the path (asked of ``_merge_added_paths``), and
        the file is untracked — so clobber is the only finding.
        """
        lg = _load_lane_guard()
        t, git = self._repo(tmp_path)
        wt = t / ".worktrees" / "lane"
        (wt / "clobber.txt").write_text("from lane\n", encoding="utf-8")
        git("add", "clobber.txt", cwd=wt)
        git("commit", "-qm", "add clobber.txt", cwd=wt)
        (t / "clobber.txt").write_text("untracked in main\n", encoding="utf-8")
        # Preconditions.
        assert "clobber.txt" in lg._merge_added_paths(t, "wt/lane")
        classified = lg._classify_status(t)
        assert classified is not None and "clobber.txt" in classified[2]  # untracked
        assert "clobber.txt" not in lint.lane_owned_paths(t / ".dreamwork", "wt/lane")

        rc = lg._pre_merge(t, "wt/lane")
        err = capsys.readouterr().err
        assert rc == 1, err
        assert "clobber.txt" in err and "would be overwritten" in err, err

    def test_a_harmless_untracked_file_does_not_refuse(self, tmp_path, capsys):
        """An untracked file the merge does NOT touch is not merge-blocking.
        Precondition: the file is untracked and not added by the branch."""
        lg = _load_lane_guard()
        t, _ = self._repo(tmp_path)
        (t / "harmless-untracked.txt").write_text("ignore me\n", encoding="utf-8")
        assert "harmless-untracked.txt" not in (lg._merge_added_paths(t, "wt/lane") or [])

        rc = lg._pre_merge(t, "wt/lane")
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "pre-merge OK" in out, out

    def test_a_non_main_checkout_declines(self, tmp_path, capsys):
        """Production line: the ``is_main_checkout`` gate (pre-existing, #465).
        Run from a linked worktree, the assertion declines rather than acting on
        the wrong tree."""
        lg = _load_lane_guard()
        t, _ = self._repo(tmp_path)
        wt = t / ".worktrees" / "lane"
        assert not lg.is_main_checkout(wt)  # precondition: this is a worktree
        rc = lg._pre_merge(wt, "wt/lane")
        err = capsys.readouterr().err
        assert rc == 2, err
        assert "MAIN CHECKOUT" in err, err

    def test_a_branch_that_does_not_resolve_fails_loud(self, tmp_path, capsys):
        """Production line: the ``_merge_added_paths is None`` branch. A typo'd
        branch name must fail loud naming it, not pass vacuously."""
        lg = _load_lane_guard()
        t, _ = self._repo(tmp_path)
        rc = lg._pre_merge(t, "wt/does-not-exist")
        err = capsys.readouterr().err
        assert rc == 2, err
        assert "wt/does-not-exist" in err and "resolve" in err, err


class TestPostureFile:
    """The three-axis posture override file (#445).

    `.dreamwork/posture` is a sibling to run-mode carrying pace/asking/
    delegation. Pace and asking are closed sets (ERROR on unknown); delegation
    is a number that steers (WARN on nonsense, never gates on the fleet size).
    """

    def _rows(self, dw, level=None):
        rep = lint.Report()
        lint.check_posture(dw, None, rep)
        return [d for lvl, w, d in rep.rows
                if w == "posture" and (level is None or lvl == level)]

    def test_absent_is_silent(self, tmp_path):
        # Absent is the default — posture derives from run-mode. The check must
        # produce no rows, because the derivation happens elsewhere (derive_posture),
        # and a present-file check saying something about an absent file would
        # cry wolf on every fresh target.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        assert self._rows(dw) == [], self._rows(dw)

    def test_all_three_valid_axes_is_clean_with_a_count(self, tmp_path):
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "posture").write_text(
            "pace: hot\nasking: inform\ndelegation: 1\n")
        rows = self._rows(dw)
        assert len(rows) == 1, rows
        assert "3 of 3" in rows[0], rows[0]
        assert "pace=hot" in rows[0] and "asking=inform" in rows[0], rows[0]

    def test_unknown_pace_errors_loud(self, tmp_path):
        # THE closed-set red: an unknown pace must ERROR, not silently fall
        # back. Production line that reds it: the `pace not in
        # POSTURE_STOPS_PACE` membership test in check_posture — make it
        # unconditionally skip and this stops erroring.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "posture").write_text("pace: warp9\nasking: ask\ndelegation: 0\n")
        errs = self._rows(dw, lint.ERROR)
        assert len(errs) == 1, errs
        assert "warp9" in errs[0], errs[0]
        assert "pace" in errs[0], errs[0]

    def test_unknown_asking_errors_loud(self, tmp_path):
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "posture").write_text("pace: idle\nasking: chatty\ndelegation: 0\n")
        errs = self._rows(dw, lint.ERROR)
        assert len(errs) == 1, errs
        assert "chatty" in errs[0] and "asking" in errs[0], errs[0]

    def test_all_four_asking_stops_are_accepted(self, tmp_path):
        # His four dictated levels are a CLOSED set — all four must parse
        # clean AND all four must be present. The set-membership is asserted
        # explicitly (not just iterated), because iterating over a narrowed
        # constant passes over the narrowing — the hollow-check trap. If the
        # set were ever narrowed (e.g. near-auto/auto merged), this reds.
        # Production line: POSTURE_STOPS_ASKING.
        assert set(lint.POSTURE_STOPS_ASKING) == \
            {"ask", "inform", "near-auto", "auto"}, lint.POSTURE_STOPS_ASKING
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        for stop in lint.POSTURE_STOPS_ASKING:
            (dw / "posture").write_text(
                f"pace: idle\nasking: {stop}\ndelegation: 0\n")
            assert not self._rows(dw, lint.ERROR), \
                f"asking={stop!r} should be valid: {self._rows(dw, lint.ERROR)}"

    def test_delegation_non_integer_is_a_warning_not_an_error(self, tmp_path):
        # Delegation is a TARGET number, not a closed set — nonsense WARNs
        # (steer, not gate), never ERRORs. Production line: the ValueError
        # branch in the delegation parse.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "posture").write_text(
            "pace: idle\nasking: ask\ndelegation: sometimes\n")
        warns = self._rows(dw, lint.WARN)
        errs = self._rows(dw, lint.ERROR)
        assert errs == [], errs
        assert any("sometimes" in w for w in warns), warns

    def test_delegation_negative_is_a_warning(self, tmp_path):
        # 0 means occasional (not forbidden); below 0 is nonsense and WARNs.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "posture").write_text(
            "pace: idle\nasking: ask\ndelegation: -1\n")
        warns = self._rows(dw, lint.WARN)
        errs = self._rows(dw, lint.ERROR)
        assert errs == [], errs
        assert any("-1" in w for w in warns), warns

    def test_delegation_zero_is_valid_and_means_own(self, tmp_path):
        # 0 is occasional/own, NOT forbidden — his #445 Q3. It must parse
        # clean and derive the "own" label.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "posture").write_text(
            "pace: idle\nasking: ask\ndelegation: 0\n")
        rows = self._rows(dw)
        assert any("3 of 3" in r and "own" in r for r in rows), rows

    def test_a_present_but_empty_file_is_inert_not_clean(self, tmp_path):
        # A file that parsed to nothing must not look the same as one that
        # found nothing wrong (#380 — count on the OK row). It WARNs that the
        # file is inert; posture stays derived.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "posture").write_text("# just a comment\n\n")
        warns = self._rows(dw, lint.WARN)
        assert any("inert" in w for w in warns), warns
        assert not self._rows(dw, lint.OK), "an inert file must not get a clean bill"

    # ── #342 delivery axis ────────────────────────────────────────────────
    def test_delivery_closed_set_has_both_stops(self, tmp_path):
        # PRECONDITION (the hollow-check rule): assert the set's membership
        # explicitly, not just iterate. If the set were narrowed, iterating
        # passes over the narrowing.
        assert set(lint.POSTURE_STOPS_DELIVERY) == {"instant", "batched"}, \
            lint.POSTURE_STOPS_DELIVERY
        assert "delivery" in lint.POSTURE_AXES, lint.POSTURE_AXES

    def test_delivery_both_stops_parse_clean(self, tmp_path):
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        for stop in lint.POSTURE_STOPS_DELIVERY:
            (dw / "posture").write_text(
                f"pace: idle\nasking: ask\ndelegation: 0\ndelivery: {stop}\n")
            assert not self._rows(dw, lint.ERROR), \
                f"delivery={stop!r} should be valid: {self._rows(dw, lint.ERROR)}"

    def test_unknown_delivery_errors_loud(self, tmp_path):
        # THE closed-set red: an unknown delivery must ERROR, not silently
        # fall back. Production line that reds it: the `delivery not in
        # POSTURE_STOPS_DELIVERY` membership test in check_posture.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "posture").write_text(
            "pace: idle\nasking: ask\ndelegation: 0\ndelivery: postal\n")
        errs = self._rows(dw, lint.ERROR)
        assert len(errs) == 1, errs
        assert "postal" in errs[0] and "delivery" in errs[0], errs[0]

    def test_absent_delivery_is_silent_not_warned(self, tmp_path):
        # Delivery is OPTIONAL — absent is the instant default, not a
        # derivation gap. So a three-line pre-axis file must NOT warn about a
        # missing delivery, and its clean bill still reads "3 of 3" (not
        # "3 of 4", which would imply delivery is missing rather than default).
        # Production line: the `delivery is None` short-circuit + the optional
        # denominator in the clean-bill branch.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "posture").write_text("pace: hot\nasking: ask\ndelegation: 0\n")
        warns = [w for w in self._rows(dw, lint.WARN) if "delivery" in w]
        assert warns == [], warns
        ok = self._rows(dw, lint.OK)
        assert len(ok) == 1, ok
        assert "3 of 3" in ok[0], ok[0]
        assert "delivery" not in ok[0], ok[0]

    def test_delivery_present_joins_clean_bill_count(self, tmp_path):
        # A four-axis file with a valid delivery reads "4 of 4" and names the
        # delivery value — so coverage cannot shrink to silence beside a
        # finding, and a reader sees the axis is set.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "posture").write_text(
            "pace: hot\nasking: ask\ndelegation: 0\ndelivery: batched\n")
        ok = self._rows(dw, lint.OK)
        assert len(ok) == 1, ok
        assert "4 of 4" in ok[0], ok[0]
        assert "delivery=batched" in ok[0], ok[0]

    def test_delivery_alone_is_valid(self, tmp_path):
        # A file that overrides ONLY delivery (no pace/asking/delegation) is
        # legitimate — those stay derived, delivery is set. It must not ERROR;
        # the delivery axis is recognised (no "unknown axis" warn) and valid.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "posture").write_text("delivery: batched\n")
        assert not self._rows(dw, lint.ERROR), self._rows(dw, lint.ERROR)
        unknown = [w for w in self._rows(dw, lint.WARN) if "unknown axis" in w]
        assert unknown == [], unknown

    # ── #510 orchestration axis ──────────────────────────────────────────
    def test_orchestration_closed_set_has_both_stops(self, tmp_path):
        # PRECONDITION (the hollow-check rule): assert the set's membership
        # explicitly, not just iterate. If the set were narrowed, iterating
        # passes over the narrowing.
        assert set(lint.POSTURE_STOPS_ORCHESTRATION) == {"hands-on", "orchestrator"}, \
            lint.POSTURE_STOPS_ORCHESTRATION
        assert "orchestration" in lint.POSTURE_AXES, lint.POSTURE_AXES

    def test_orchestration_both_stops_parse_clean(self, tmp_path):
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        for stop in lint.POSTURE_STOPS_ORCHESTRATION:
            (dw / "posture").write_text(
                f"pace: idle\nasking: ask\ndelegation: 0\norchestration: {stop}\n")
            assert not self._rows(dw, lint.ERROR), \
                f"orchestration={stop!r} should be valid: {self._rows(dw, lint.ERROR)}"

    def test_unknown_orchestration_errors_loud(self, tmp_path):
        # THE closed-set red: an unknown orchestration must ERROR, not silently
        # fall back. Production line that reds it: the `orchestration not in
        # POSTURE_STOPS_ORCHESTRATION` membership test in check_posture.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "posture").write_text(
            "pace: idle\nasking: ask\ndelegation: 0\norchestration: turbo\n")
        errs = self._rows(dw, lint.ERROR)
        assert len(errs) == 1, errs
        assert "turbo" in errs[0] and "orchestration" in errs[0], errs[0]

    def test_absent_orchestration_is_silent_not_warned(self, tmp_path):
        # Orchestration is OPTIONAL — absent is the hands-on default, not a
        # derivation gap. So a three-line pre-axis file must NOT warn about a
        # missing orchestration, and its clean bill still reads "3 of 3" (not
        # "3 of 4" or "3 of 5", which would imply the optional axes are
        # missing rather than default).
        # Production line: the `orchestration is None` short-circuit + the
        # optional denominator in the clean-bill branch.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "posture").write_text("pace: hot\nasking: ask\ndelegation: 0\n")
        warns = [w for w in self._rows(dw, lint.WARN) if "orchestration" in w]
        assert warns == [], warns
        ok = self._rows(dw, lint.OK)
        assert len(ok) == 1, ok
        assert "3 of 3" in ok[0], ok[0]
        assert "orchestration" not in ok[0], ok[0]

    def test_orchestration_present_joins_clean_bill_count(self, tmp_path):
        # A five-axis file with a valid orchestration reads "4 of 4" (the
        # three required + orchestration) and names the orchestration value —
        # so coverage cannot shrink to silence beside a finding, and a reader
        # sees the axis is set. (Delivery absent here, so denom is 4 not 5.)
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "posture").write_text(
            "pace: hot\nasking: ask\ndelegation: 0\norchestration: orchestrator\n")
        ok = self._rows(dw, lint.OK)
        assert len(ok) == 1, ok
        assert "4 of 4" in ok[0], ok[0]
        assert "orchestration=orchestrator" in ok[0], ok[0]

    def test_orchestration_and_delivery_both_present_count_five(self, tmp_path):
        # Both optional axes present + the three required = 5 of 5. Proves the
        # clean-bill denominator accounts for BOTH optional axes (not just one
        # — a literal tuned to one would mask the other). Preconditions
        # derived at runtime: both optional axes are genuinely in their sets.
        assert set(lint.POSTURE_STOPS_DELIVERY) == {"instant", "batched"}
        assert set(lint.POSTURE_STOPS_ORCHESTRATION) == {"hands-on", "orchestrator"}
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "posture").write_text(
            "pace: hot\nasking: ask\ndelegation: 0\n"
            "delivery: batched\norchestration: orchestrator\n")
        ok = self._rows(dw, lint.OK)
        assert len(ok) == 1, ok
        assert "5 of 5" in ok[0], ok[0]
        assert "delivery=batched" in ok[0] and "orchestration=orchestrator" in ok[0], ok[0]

    def test_orchestration_alone_is_valid(self, tmp_path):
        # A file that overrides ONLY orchestration is legitimate — the other
        # axes stay derived, orchestration is set. It must not ERROR; the axis
        # is recognised (no "unknown axis" warn) and valid.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "posture").write_text("orchestration: orchestrator\n")
        assert not self._rows(dw, lint.ERROR), self._rows(dw, lint.ERROR)
        unknown = [w for w in self._rows(dw, lint.WARN) if "unknown axis" in w]
        assert unknown == [], unknown

    # ── #650 the free-text subagent policy, seen from the AXIS file ──────
    def test_subagent_policy_line_in_posture_errors_loud(self, tmp_path):
        # THE misplacement red. `parse_posture_text` drops an unrecognised
        # key, so a policy written here is silently not in effect — the
        # dropped-choice hazard run-mode and watch-tint fail loud on. It must
        # ERROR (not the softer "unknown axis" WARN) and must name the file
        # the value belongs in. Production line: the POSTURE_TEXT_FIELDS
        # branch in check_posture.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "posture").write_text(
            "pace: hot\nasking: ask\ndelegation: 0\n"
            "subagent-policy: use the cheap model\n")
        errs = self._rows(dw, lint.ERROR)
        assert len(errs) == 1, errs
        assert "subagent-policy" in errs[0], errs[0]
        assert ".dreamwork/subagent-policy" in errs[0], errs[0]
        # And it is NOT reported as an unknown axis: the name is recognised,
        # the file is wrong, and telling him "unknown" would send him looking
        # for a typo.
        unknown = [w for w in self._rows(dw, lint.WARN) if "unknown axis" in w]
        assert unknown == [], unknown

    def test_closed_axis_still_fails_loud_when_a_policy_file_exists(
            self, tmp_path):
        # THE regression this whole design is judged on: adding a free-text
        # field must not turn the validator permissive for the CLOSED axes.
        # A present policy file — even one whose prose contains axis-shaped
        # lines — changes nothing about `pace: warp` failing loud.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "subagent-policy").write_text(
            "- pace: warp is a great idea\n- asking: whatever you like\n")
        (dw / "posture").write_text("pace: warp\nasking: ask\ndelegation: 0\n")
        errs = self._rows(dw, lint.ERROR)
        assert len(errs) == 1, errs
        assert "warp" in errs[0] and "pace" in errs[0], errs[0]


class TestSubagentPolicy:
    """The free-text subagent policy sibling file (#650).

    `.dreamwork/subagent-policy` has no grammar — the whole file is the
    value — so the check reports which policy is in effect and whether a
    present file is inert, and never inspects the content.
    """

    def _rows(self, dw, level=None):
        rep = lint.Report()
        lint.check_subagent_policy(dw, rep)
        return [d for lvl, w, d in rep.rows
                if w == "subagent-policy" and (level is None or lvl == level)]

    def _posture_rows(self, dw, level=None):
        rep = lint.Report()
        lint.check_posture(dw, None, rep)
        return [d for lvl, w, d in rep.rows
                if w == "posture" and (level is None or lvl == level)]

    def test_the_standing_default_is_his_text_including_its_typos(self):
        # The seeded standing value. Asserted by the marks that only HIS
        # wording carries — the typo "taks", the contraction, the tool name —
        # rather than by restating the whole policy, which would be a second
        # copy able to disagree with the first. A normalising edit (spell-fix,
        # re-wrap, tidy) reds this.
        p = lint.SUBAGENT_POLICY_DEFAULT
        assert p.endswith("\n"), repr(p[-20:])
        lines = p.splitlines()
        assert len(lines) == 4, lines
        assert all(ln.startswith("- ") for ln in lines), lines
        assert "taks" in p, "his typo was normalised away"
        assert "won't" in p, p
        assert "`ccc -y @glm52`" in p, p
        assert "Sonnet 5 low or medium" in lines[0], lines[0]
        assert "fable high" in lines[3], lines[3]

    def test_absent_is_clean_and_says_the_default_is_in_effect(self, tmp_path):
        # Absent is the NORMAL state (the standing default is committed in
        # code), so it must not warn — but it must not be silent either: a
        # value IS in effect, and coverage that vanishes when nothing is
        # wrong is the #380 hazard.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        assert self._rows(dw, lint.ERROR) == [], self._rows(dw, lint.ERROR)
        assert self._rows(dw, lint.WARN) == [], self._rows(dw, lint.WARN)
        ok = self._rows(dw, lint.OK)
        assert len(ok) == 1, ok
        assert "absent" in ok[0] and "default" in ok[0], ok[0]

    def test_present_policy_is_clean_and_counted(self, tmp_path):
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "subagent-policy").write_text(lint.SUBAGENT_POLICY_DEFAULT)
        assert self._rows(dw, lint.ERROR) == [], self._rows(dw, lint.ERROR)
        ok = self._rows(dw, lint.OK)
        assert len(ok) == 1, ok
        assert "override" in ok[0], ok[0]
        assert "4 lines" in ok[0], ok[0]

    def test_blank_file_warns_inert_rather_than_passing(self, tmp_path):
        # A file that looks set and is not must not pass in silence — the
        # same inert-file shape check_posture uses for a file that parsed to
        # nothing. Clearing the override is `rm`, not an empty write.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "subagent-policy").write_text("   \n\n")
        warns = self._rows(dw, lint.WARN)
        assert len(warns) == 1, warns
        assert "inert" in warns[0], warns[0]
        assert self._rows(dw, lint.OK) == [], self._rows(dw, lint.OK)

    def test_content_is_never_validated_against_any_vocabulary(self, tmp_path):
        # The defining property of a FREE-TEXT field: nothing in the value is
        # checked. His policy is prose that happens to contain colons, hashes
        # and axis names; a checker that read those as posture would fail on
        # his own wording and would have turned free text back into a closed
        # set. Not one ERROR, not one WARN.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "subagent-policy").write_text(
            "# not a comment, just his prose\n"
            "pace: warp\n"
            "orchestration: whatever feels right\n"
            "delegation: heaps\n"
            "unknown-axis: nonsense\n")
        assert self._rows(dw, lint.ERROR) == [], self._rows(dw, lint.ERROR)
        assert self._rows(dw, lint.WARN) == [], self._rows(dw, lint.WARN)

    def test_policy_file_does_not_disturb_the_posture_clean_bill(
            self, tmp_path):
        # The two files are independent: a present policy leaves the axis
        # count and its row exactly as they were, so the policy can never
        # inflate or deflate the axes' coverage claim.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "posture").write_text("pace: hot\nasking: ask\ndelegation: 0\n")
        before = self._posture_rows(dw, lint.OK)
        (dw / "subagent-policy").write_text(lint.SUBAGENT_POLICY_DEFAULT)
        after = self._posture_rows(dw, lint.OK)
        assert before == after, (before, after)
        assert "3 of 3" in after[0], after[0]
        assert "subagent" not in after[0], after[0]

    def test_the_field_is_recognised_but_is_not_an_axis(self):
        # The schema statement: the name is known to the posture schema (so
        # check_posture can redirect rather than say "unknown"), and it is
        # NOT in POSTURE_AXES (so no closed-set machinery ever reaches it).
        assert "subagent-policy" in lint.POSTURE_TEXT_FIELDS, \
            lint.POSTURE_TEXT_FIELDS
        assert "subagent-policy" not in lint.POSTURE_AXES, lint.POSTURE_AXES
        assert lint.POSTURE_TEXT_FIELDS["subagent-policy"] == \
            ".dreamwork/subagent-policy", lint.POSTURE_TEXT_FIELDS
        assert lint.SUBAGENT_POLICY_FILE == "subagent-policy"

    def test_the_check_runs_in_the_live_check_run(self, tmp_path):
        # A check nobody calls is not a check. Drives the real entry point
        # (`run_checks`, what the CLI runs) rather than grepping the source,
        # and looks for the inert-file finding to prove the row came from the
        # run and not from a default.
        dw = tmp_path / ".dreamwork"
        dw.mkdir()
        (dw / "subagent-policy").write_text("   \n")
        rep = lint.Report()
        lint.run_checks(dw, None, rep)
        rows = [d for lvl, w, d in rep.rows if w == "subagent-policy"]
        assert len(rows) == 1, rows
        assert "inert" in rows[0], rows[0]


class TestDerivePosture:
    """The run-mode → three-axis conversion (#445 Q2).

    The mapping must cover every RUN_MODE and preserve today's asking
    behaviour (level 1 = ask), because the brief requires no silent change for
    a loop that has not been restarted.
    """

    def test_every_run_mode_has_a_derivation(self):
        # PRECONDITION: the mapping covers the whole closed set read from
        # watch.py. A mode that lands in the mapping by accident (because the
        # dict was hand-written against a stale copy) is the drift this catches.
        import watch
        for mode in watch.RUN_MODES:
            derived = lint.derive_posture(mode)
            assert derived is not None, \
                f"run-mode {mode!r} has no posture derivation"

    def test_asking_is_ask_for_every_run_mode(self):
        # THE behaviour-preservation red: today's loop asks on ~every material
        # decision (108 resolutions, 28 artifacts), so every derived posture
        # must carry asking=ask. If any derivation said `inform`, the loop
        # would stop asking on upgrade — the silent regression. Production
        # line: the RUN_MODE_TO_POSTURE values.
        import watch
        for mode in watch.RUN_MODES:
            derived = lint.derive_posture(mode)
            assert derived["asking"] == "ask", \
                f"{mode!r} derives asking={derived['asking']!r} — that is a " \
                "behaviour change (today the loop asks on ~every material choice)"

    def test_delegation_matches_the_old_modes_meaning(self):
        assert lint.derive_posture("lackadaisical")["delegation"] == 0
        assert lint.derive_posture("hot")["delegation"] == 0
        # assisted = "a few disjoint helpers" → 1 (assist), per #290's contract.
        assert lint.derive_posture("assisted")["delegation"] == 1

    def test_pace_for_assisted_is_continuous(self):
        # watch.py describes both hot and assisted as "continuous work"; only
        # lackadaisical is "idle-friendly". So assisted derives hot pace —
        # unpacking a bundle, not inventing a decision (#443).
        assert lint.derive_posture("lackadaisical")["pace"] == "idle"
        assert lint.derive_posture("hot")["pace"] == "hot"
        assert lint.derive_posture("assisted")["pace"] == "hot"

    def test_unrecognised_mode_returns_none(self):
        assert lint.derive_posture("nonexistent") is None



class TestLessonNearDuplicates:
    """#349's write-time backstop: a NEW lesson whose first sentence
    near-duplicates an existing one is refused.

    The fixtures' similarity is DERIVED AT RUNTIME, independently of lint's
    own helpers (inline difflib + token overlap here, not lint._norm_claim)
    — the check is vacuous the day the fixture pair drifts under the
    threshold, and a green red-run is a finding, never a relief.
    """

    CLAIM_A = ("A guard assertion whose subject may not exist must RETURN a "
               "value, never throw.")
    # The historical repeat's own rewording (lessons.md:580 vs :622) — the
    # pair this check exists because of.
    CLAIM_A_REPEAT = ("A guard assertion whose subject may not exist has to "
                      "degrade to a reading, never throw.")
    CLAIM_B = ("Write the timestamp from the clock in the same command that "
               "writes the file.")
    CLAIM_DISTINCT = ("Mounting a second instance of a surface is the "
                      "cheapest audit of the first one.")

    @staticmethod
    def _lessons(*claims: str) -> str:
        return "# Lessons\n\n" + "\n".join(
            f"- **{c}** The evidence that earned it, kept whole.\n"
            for c in claims)

    @staticmethod
    def _sim(a: str, b: str) -> tuple[float, float]:
        import difflib as _d
        na = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", a.lower())).strip()
        nb = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", b.lower())).strip()
        stop = set("a an the and or of to in on for with by is are was were "
                   "be been it its this that not no never must can could "
                   "should would from at as so if then than when what which "
                   "who how why your you we our their they them he she his "
                   "her do does did have has had will just only every each "
                   "any all one two three".split())
        ta = {t for t in na.split() if t not in stop and len(t) > 2}
        tb = {t for t in nb.split() if t not in stop and len(t) > 2}
        return _d.SequenceMatcher(None, na, nb).ratio(), len(ta & tb) / len(ta | tb)

    def _git(self, repo: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args],
                       check=True, capture_output=True)

    def _repo(self, tmp_path: Path, committed: str) -> Path:
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "lessons.md").write_text(committed)
        self._git(t, "-c", "init.defaultBranch=main", "init", "-q")
        self._git(t, "add", ".dreamwork/lessons.md")
        self._git(t, "-c", "user.email=t@t", "-c", "user.name=t",
                  "commit", "-qm", "base")
        return t

    def test_fixture_preconditions_hold(self):
        # The check's meaning needs the repeat pair ABOVE threshold and every
        # other fixture pair BELOW it — derive both at runtime, assert the
        # gap, or the tests below are tuned literals with an expiry date.
        r_dup, j_dup = self._sim(self.CLAIM_A, self.CLAIM_A_REPEAT)
        assert r_dup >= lint.LESSON_DUP_RATIO and j_dup >= lint.LESSON_DUP_JACCARD, \
            f"fixture repeat drifted under the threshold ({r_dup:.3f}/{j_dup:.3f})"
        for other in (self.CLAIM_B, self.CLAIM_DISTINCT):
            for claim in (self.CLAIM_A, self.CLAIM_A_REPEAT):
                r, j = self._sim(claim, other)
                assert r < lint.LESSON_DUP_RATIO or j < lint.LESSON_DUP_JACCARD, \
                    f"control pair trips the rule ({r:.3f}/{j:.3f}) — the check would cry wolf"

    def test_new_near_duplicate_is_an_error(self, tmp_path):
        t = self._repo(tmp_path, self._lessons(self.CLAIM_A, self.CLAIM_B))
        with open(t / ".dreamwork" / "lessons.md", "a") as f:
            f.write(f"- **{self.CLAIM_A_REPEAT}** Rewritten evidence.\n")
        rep = run(t)
        assert ERRORS(rep, "lessons.md"), \
            f"a new lesson re-saying an existing claim must be refused:\n{rep.render()}"
        detail = next(d for l, w, d in rep.rows
                      if l == lint.ERROR and w == "lessons.md")
        assert "≈" in detail, "must name BOTH lines, not just report a count"

    def test_new_distinct_lesson_passes(self, tmp_path):
        t = self._repo(tmp_path, self._lessons(self.CLAIM_A, self.CLAIM_B))
        with open(t / ".dreamwork" / "lessons.md", "a") as f:
            f.write(f"- **{self.CLAIM_DISTINCT}** Fresh evidence.\n")
        rep = run(t)
        assert not ERRORS(rep, "lessons.md"), rep.render()
        assert lint.OK in levels(rep, "lessons.md")

    def test_preexisting_pair_warns_never_errors(self, tmp_path):
        # Both halves committed (the 580/622 shape): refusal is a write-time
        # gate, and merging history is his call — WARN names it, forever.
        t = self._repo(tmp_path, self._lessons(self.CLAIM_A, self.CLAIM_A_REPEAT))
        rep = run(t)
        assert not ERRORS(rep, "lessons.md"), rep.render()
        (warn,) = [d for l, w, d in rep.rows
                   if l == lint.WARN and w == "lessons.md"]
        assert "already in HEAD" in warn

    def test_no_git_baseline_degrades_loudly(self, tmp_path):
        # A fixture with no repo: the check must not fake having compared
        # against HEAD — the WARN says the refusal is OFF.
        t = target(tmp_path, **{
            "lessons.md": self._lessons(self.CLAIM_A, self.CLAIM_A_REPEAT)})
        rep = run(t)
        assert not ERRORS(rep, "lessons.md"), rep.render()
        (warn,) = [d for l, w, d in rep.rows
                   if l == lint.WARN and w == "lessons.md"]
        assert "refusal is OFF" in warn

    def test_missing_lessons_is_a_warn_not_an_error(self, tmp_path):
        rep = run(target(tmp_path))
        assert levels(rep, "lessons.md") == [lint.WARN]
        assert not rep.failed


# ---------------------------------------------------------------------------
# Store mode (#294): after the cutover watermark, lint's ledger checks read
# the STORE through ledger_view's synthesized projection, the section
# cross-check guards the frozen history (tasks.md.deprecated), and the #362
# drift check inverts into the retired-fields-stay-absent invariant.
#
# Production line for the class: the ``if source_of_truth(dw) == "store":``
# dispatch in lint.ledger_view. Break it (``if False:``) and every store-mode
# test fails — the shim has no `Next id` header and parses to zero ids.
# ---------------------------------------------------------------------------
class TestStoreModeLint:
    FIXTURE = ("# Task ledger\n\nNext id: **12**\n\n## Open\n\n"
               "- **#10** — a clean open entry · P1 · task · origin: **human**\n\n"
               "## Recently landed\n\n"
               "- **#11** — a clean landed entry · P0 · implementation · "
               "origin: **human** (abc1234)\n")

    def _cut_over(self, tmp_path, fixture=None):
        """A REAL post-cutover scratch target: watermark, shim, deprecated,
        populated store — the same artifact the live cutover will produce."""
        import importlib.machinery, importlib.util, io
        import ledger_parse
        repo = Path(__file__).resolve().parent
        loader = importlib.machinery.SourceFileLoader(
            "ud_dw_tasks_migrate", str(repo / "ud-dw-tasks-migrate"))
        spec = importlib.util.spec_from_loader("ud_dw_tasks_migrate", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        td = tmp_path / "dw"
        td.mkdir()
        (td / "tasks.md").write_text(
            self.FIXTURE if fixture is None else fixture)
        mod.perform_cutover(str(td), out=io.StringIO())
        assert ledger_parse.source_of_truth(td) == "store", \
            "fixture precondition: the watermark must be present"
        return td

    def test_the_projection_parses_to_the_store_id_sets(self, tmp_path):
        import watch
        td = self._cut_over(tmp_path)
        text, source = lint.ledger_view(td)
        assert source == "store"
        o, l = watch.parse_ledger(text)
        mo, ml = watch.parse_ledger(self.FIXTURE)
        assert (o, l) == (mo, ml), \
            "the store projection must parse to the markdown id sets"
        assert o, "precondition: the fixture genuinely has open ids"

    def test_check_tasks_names_the_store_and_stays_clean(self, tmp_path):
        td = self._cut_over(tmp_path)
        rep = lint.Report()
        lint.check_tasks(td, rep)
        assert not ERRORS(rep, "ledger store"), \
            "a healthy store projection must not go red"
        assert not ERRORS(rep, "tasks.md"), \
            "the shim must not be read as the ledger in store mode"

    def test_a_regrown_retired_field_is_an_error(self, tmp_path):
        import watch
        td = self._cut_over(tmp_path)
        (td / "status.json").write_text(json.dumps(
            {"queue": {"in_progress": 1, "pending": 2}}))
        rep = lint.Report()
        lint.check_status_agrees_with_ledger(td, watch, rep)
        errs = ERRORS(rep, "status.json")
        assert errs, "a regrown `queue` post-cutover is a second derived truth"
        detail = next(d for _, w, d in rep.rows
                      if w == "status.json" and "retired" in d)
        assert "queue" in detail

    def test_retired_fields_absent_is_ok_not_vacuous(self, tmp_path):
        import watch
        td = self._cut_over(tmp_path)
        (td / "status.json").write_text(json.dumps({"task": "294"}))
        rep = lint.Report()
        lint.check_status_agrees_with_ledger(td, watch, rep)
        assert not ERRORS(rep, "status.json")
        assert levels(rep, "status.json") == [lint.OK], \
            "the invariant must REPORT, not pass by silence"

    def test_status_task_ids_skips_in_store_mode(self, tmp_path):
        td = self._cut_over(tmp_path)
        # A PRESENT-but-stringly current_task_ids is an ERROR in markdown
        # mode; in store mode the field is retired and this check is moot
        # (the absence invariant above owns reporting it).
        (td / "status.json").write_text(json.dumps(
            {"current_task_ids": ["#281"]}))
        rep = lint.Report()
        lint.check_status_task_ids(td, rep)
        assert not ERRORS(rep, "status.json"), \
            "store mode must not lint the TYPE of a retired field"

    def test_missing_deprecated_history_is_an_error(self, tmp_path):
        td = self._cut_over(tmp_path)
        (td / "tasks.md.deprecated").unlink()
        rep = lint.Report()
        lint.check_ledger_sections(td, "unused", "store", rep)
        assert ERRORS(rep, "tasks.md.deprecated"), \
            "the design says never delete it — its absence must go red"

    def test_the_frozen_history_passes_two_readers(self, tmp_path):
        td = self._cut_over(tmp_path)
        rep = lint.Report()
        lint.check_ledger_sections(td, "unused", "store", rep)
        assert not ERRORS(rep, "tasks.md.deprecated")
        assert levels(rep, "tasks.md.deprecated") == [lint.OK]

    # ------------------------------------------------------------------
    # #557 — the projection must synthesize entry heads for headless bodies.
    # The #294 import stored each body verbatim, head line included, so the
    # projection reparsed. `dev/ledger.py file` / `ledger_write.file_task`
    # store the body WITHOUT a `- **#id**` head (the note text alone), so
    # every entry filed after cutover was invisible to ledger_view and to
    # every text-consuming check (parse_ledger, check_task_origins,
    # check_handoffs's delivery signal). store_entries now synthesizes a head
    # from the store columns for a headless body. These tests file REAL
    # headless entries through the REAL writer (never a hand-built store) and
    # derive the gap at runtime — the id sets come from store_ids_by_state,
    # not a pinned literal.
    # ------------------------------------------------------------------
    def _file_headless(self, td, title, body, **kw):
        """File a NEW task via the REAL store writer; its stored body is headless.

        file_task stores the body verbatim (the note text) with no head — the
        exact defect shape. Returns the new (AUTOINCREMENT) id."""
        import ledger_write, ledger_parse
        from dreamwork_db import Access, open_database
        from dreamwork_db.tasks import task_store_spec
        with open_database(
                task_store_spec(ledger_parse.store_path(td)),
                access=Access.WRITE) as store:
            return ledger_write.file_task(store, title, body, **kw)

    def test_the_projection_sees_a_filed_headless_open_entry(self, tmp_path):
        """#557 born-red: a filed entry has no `- **#id**` head, so the
        projection read FEWER open ids than the store holds. The projection
        must synthesize the head so parse_ledger sees every open id. The gap
        (store open set minus view open set) is DERIVED at runtime."""
        import watch, ledger_parse
        td = self._cut_over(tmp_path)
        store_open_before = set(ledger_parse.store_ids_by_state(td)[0])
        new_id = self._file_headless(
            td, "a headless filed entry", "the body carries no head line",
            priority="P2", type="task", origin="loop")
        store_open = set(ledger_parse.store_ids_by_state(td)[0])
        # Runtime preconditions — the gap this test depends on, derived not pinned.
        assert store_open - store_open_before == {str(new_id)}, \
            "precondition: exactly one new open id was filed"
        rec = next(r for r in ledger_parse.store_records(td) if r["id"] == new_id)
        assert not rec["body"].lstrip().startswith("- **#"), \
            "precondition: the filed body is genuinely headless (the defect shape)"
        # THE binding: the view's parsed open ids must equal the store's open ids.
        text, source = lint.ledger_view(td)
        assert source == "store"
        view_open, _ = watch.parse_ledger(text)
        gap = store_open - view_open
        assert not gap, (
            f"projection blind to headless open id(s) {sorted(gap, key=int)}: "
            f"view={sorted(view_open, key=int)} store={sorted(store_open, key=int)}")

    def test_the_projection_sees_a_filed_headless_landed_entry(self, tmp_path):
        """#557 landed half: landing flips state and appends a note but never
        adds a head, so a filed-then-landed entry is headless in `## Recently
        landed` and was invisible there too."""
        import watch, ledger_parse, ledger_write
        from dreamwork_db import Access, open_database
        from dreamwork_db.tasks import task_store_spec
        td = self._cut_over(tmp_path)
        new_id = self._file_headless(
            td, "a headless entry that will land", "body has no head",
            priority="P1", type="bug", origin="human")
        with open_database(
                task_store_spec(ledger_parse.store_path(td)),
                access=Access.WRITE) as store:
            ledger_write.land_task(store, new_id, note="landed (abc1234)")
        store_open, store_landed = ledger_parse.store_ids_by_state(td)
        store_landed = set(store_landed)
        rec = next(r for r in ledger_parse.store_records(td) if r["id"] == new_id)
        assert not rec["body"].lstrip().startswith("- **#"), \
            "precondition: the landed filed body is still headless"
        assert str(new_id) in store_landed and str(new_id) not in set(store_open)
        text, _ = lint.ledger_view(td)
        _, view_landed = watch.parse_ledger(text)
        gap = store_landed - view_landed
        assert not gap, (
            f"projection blind to headless landed id(s) {sorted(gap, key=int)}: "
            f"view={sorted(view_landed, key=int)} store={sorted(store_landed, key=int)}")

    def test_a_headless_entry_with_null_columns_omits_them_not_fabricates(self, tmp_path):
        """#557 edge (#5): priority/type are nullable, and filed entries are
        filed with no band/type by default. A NULL field is OMITTED (the head
        grammar tolerates absent fields — pre-#216 heads are bare), never
        fabricated; NULL origin becomes `unknown` (the truthful value
        check_task_origins records). The id and the single origin marker are
        what the checks read, and both must survive."""
        import watch, ledger_parse
        td = self._cut_over(tmp_path)
        new_id = self._file_headless(
            td, "no band no type no origin", "headless body", origin=None)
        rec = next(r for r in ledger_parse.store_records(td) if r["id"] == new_id)
        assert rec["priority"] is None and rec["type"] is None \
            and rec["origin"] is None, "precondition: all nullable columns NULL"
        text, _ = lint.ledger_view(td)
        head = None
        for ids, body in ledger_parse.ledger_entries(text):
            if new_id in ids:
                head = body
                break
        assert head is not None, "the headless entry must now head an entry"
        first = head.splitlines()[0]
        assert first.startswith(f"- **#{new_id}** — "), first
        marks = ledger_parse.ORIGIN_MARK.findall(first)
        assert marks == ["unknown"], \
            f"NULL origin -> unknown, exactly one marker; got {marks}"
        # No fabricated priority/type: the only non-title `·`-field is origin.
        # Strip the head's closing ` ·` (it carries no trailing space) first.
        chain = first[:-2] if first.endswith(" ·") else first
        meta = [f for f in chain.split(" · ")[1:] if f]
        assert meta == ["origin: **unknown**"], \
            f"NULL priority/type must be omitted, not fabricated: {first!r}"
        view_open, _ = watch.parse_ledger(text)
        assert str(new_id) in view_open, "the id must be visible to parse_ledger"

    def test_a_headless_body_quoting_an_origin_marker_stays_single(self, tmp_path):
        """#557 edge (#4) / #696: a headless body that quotes `origin: **x**`
        in prose would risk a double-origin ERROR. The live tree has none
        (coordinator-verified 0), but the shape is handled generally. The
        synthesized head's marker is the column's value (the authority); a
        body prose quote is not a claim. Before #696 the body quote sat on a
        column-0 line that ended the entry (truncation hid it); now the
        projection indents continuation lines so they survive `ledger_entries`
        (#696), so the head must be read AUTHORITATIVELY — `origin_marks`
        reads the head line first and ignores the body quote, and
        `check_task_origins` does not ERROR on the two raw markers."""
        import ledger_parse
        td = self._cut_over(tmp_path)
        new_id = self._file_headless(
            td, "headless entry whose body quotes an origin in prose",
            "deliberately quotes origin: **human** inside the body prose",
            priority="P2", type="task", origin="loop")
        rec = next(r for r in ledger_parse.store_records(td) if r["id"] == new_id)
        assert ledger_parse.ORIGIN_MARK.search(rec["body"]), \
            "precondition: the body genuinely quotes an origin marker"
        text, _ = lint.ledger_view(td)
        # #696 precondition: the body continuation is now VISIBLE (indented),
        # so the raw marker count is two — the old truncation hid the body.
        body = next(b for ids, b in ledger_parse.ledger_entries(text)
                    if new_id in ids)
        assert ledger_parse.ORIGIN_MARK.findall(body) == ["loop", "human"], (
            "precondition: #696 made the body quote visible; truncation hid it")
        # THE binding: the head is authoritative, so origin_marks ignores the
        # body quote and classify_origin / check_task_origins are unchanged.
        assert ledger_parse.origin_marks(body) == ["loop"], (
            "head must be the origin authority; body prose must not count: "
            f"{ledger_parse.origin_marks(body)}")
        assert ledger_parse.classify_origin(body) == "loop"
        rep = lint.Report()
        lint.check_task_origins(text, rep)
        assert not [r for r in rep.rows if r[0] == lint.ERROR], (
            "two raw markers must not ERROR once the head is authoritative")



    def test_check_related_markers_reads_the_store_through_ledger_view(self, tmp_path):
        """#685: the check must read through `ledger_view` (the #294 dispatch),
        not `tasks.md` directly. In store mode `tasks.md` is the #458 shim (no
        entries), so a direct read examines 0 — the defect, which read as a
        pass. The binding: a reciprocal marker pair that exists ONLY in the
        store projection must be validated, and the examined count must equal
        the store's entry count, not zero.

        PRODUCTION LINE: `text, source = ledger_view(dw)` in
        check_related_markers. RED: restore the direct
        `(dw / 'tasks.md').read_text()` and this fails — the shim yields 0
        entries, the pair is never seen, and the count is 0. A re-implemented
        reader that opened the store itself would also have to synthesise the
        sectioned projection `ledger_view` builds, or `parse_ledger` would
        return no ids — so the assertion binds the shared dispatch, not a
        second store reader (#655, #352).
        """
        import ledger_parse, watch
        FIXTURE = (
            "# Task ledger\n\nNext id: **4**\n\n## Open\n\n"
            "- **#1** — a task · P2 · origin: **loop** · related: **#2** · going\n"
            "- **#2** — its other half · P2 · origin: **loop** · "
            "related: **#1** · too\n"
            "- **#3** — alone · P2 · origin: **loop**\n")
        td = self._cut_over(tmp_path, FIXTURE)
        # Precondition: the shim genuinely yields no entries (the defect shape),
        # so only the store projection can feed the check.
        shim = (td / "tasks.md").read_text()
        assert not watch.ledger_entries(shim), \
            f"precondition: the shim must yield no entries: {shim!r}"
        rep = lint.Report()
        lint.check_related_markers(td, lint.load_watch(), rep)
        errs = [d for lvl, w, d in rep.rows
                if lvl == lint.ERROR and w == "tasks.md"]
        assert errs == [], errs   # the pair is reciprocal through the store
        oks = [d for lvl, w, d in rep.rows if lvl == lint.OK and w == "tasks.md"]
        # Derived: the examined count must match the STORE's id set, not 0.
        store_open, store_landed = ledger_parse.store_ids_by_state(td)
        n_store = len(set(store_open) | set(store_landed))
        assert n_store == 3, f"precondition: the store holds 3 ids: {n_store}"
        assert any(f"examined {n_store} entries against 2 markers (store)" in o
                   for o in oks), oks
        assert not any("examined 0 entries" in o for o in oks), oks

    # ------------------------------------------------------------------
    # #696 — a filed body whose prose sits at column 0 truncated at the
    # first such line, so ledger_entries saw only the head and every
    # text-consuming check (sweep's `sha in body`, check_landed_still_open)
    # read a fraction of the entry. The projection must indent continuation
    # lines so the body reparses. Filed through the REAL writer; the gap is
    # derived at runtime.
    # ------------------------------------------------------------------
    def test_a_column_zero_body_paragraph_survives_the_projection(self, tmp_path):
        """#696 born-red: ledger_entries ends an entry at the first column-0
        line, and a filed body's multi-paragraph prose reaches the store
        UNINDENTED, so the entry truncated to its head alone. sweep and
        check_landed_still_open read `sha in body` over that truncated text
        and produced false complaints (the confirmed #124 case). The
        projection must indent continuation lines. RED: drop the indenting
        in ledger_view and the sha the second paragraph cites is absent."""
        import ledger_parse
        td = self._cut_over(tmp_path)
        sha = "abc1234deadbeef"
        marker = "SECOND-PARAGRAPH-MARKER"
        body = ("the first paragraph of the note\n"
                f"{marker}: a second paragraph at column zero citing {sha}, "
                "which sweep and check_landed_still_open read as `sha in body`")
        new_id = self._file_headless(
            td, "a multi-paragraph filed entry", body,
            priority="P2", type="task", origin="loop")
        # Runtime precondition — the test is discriminating, not vacuous: the
        # UNINDENTED store body truncates, so ledger_entries loses the second
        # paragraph. This is the production line the fix sits in front of.
        store = {ids[0]: b for ids, b in ledger_parse.store_entries(td)}
        assert new_id in store, "precondition: the entry was filed"
        raw = ledger_parse.ledger_entries(store[new_id])
        raw_body = raw[0][1] if raw else ""
        assert marker not in raw_body, (
            "precondition: the unindented body must truncate before the "
            f"second paragraph; got {raw_body!r}")
        lost_raw = len(store[new_id]) - len(raw_body)
        assert lost_raw > len(sha), (
            f"precondition: real text lost to truncation ({lost_raw} chars)")
        # THE binding: after the projection, the column-0 paragraph survives.
        text, source = lint.ledger_view(td)
        assert source == "store"
        parsed = {ids[0]: b for ids, b in ledger_parse.ledger_entries(text)}
        assert new_id in parsed, "the entry must head an entry in the projection"
        assert sha in parsed[new_id], (
            f"#{new_id}: the column-0 paragraph citing {sha} truncated — "
            f"parsed {len(parsed[new_id])} chars, lost the second paragraph")
        assert marker in parsed[new_id], (
            f"#{new_id}: the second paragraph is invisible to ledger_entries")

class TestReviewDecisionIntegrity:
    """#289 — the coordinator-owned WARN half of the review_decision store:
    dangling question_titles and prose-claim conflicts. The fixture is a REAL
    cut-over target with REAL recorded decisions (ledger_write), never a
    hand-built dict — a check whose fixture builds the store itself cannot
    see the writer drift."""

    QGOOD = ("# Questions for the human\n\n## Open\n\n"
             "- **P1 · 2026-07-29 22:31 — ship the frobnicate?** body\n\n"
             "## Answered\n\n"
             "- **P2 · 2026-07-28 — keep the old panel?**\n"
             "  → answered (2026-07-28): **yes.**\n")

    def _target(self, tmp_path, with_questions=True):
        td = TestStoreModeLint()._cut_over(tmp_path)
        (td / "review").mkdir(exist_ok=True)
        (td / "review" / "alpha.html").write_text("<html>a</html>")
        (td / "review" / "beta.html").write_text("<html>b</html>")
        if with_questions:
            (td / "questions.md").write_text(self.QGOOD)
        return td

    def _record(self, td, artifact, title, decision):
        import ledger_write, ledger_parse
        from dreamwork_db import Access, open_database
        from dreamwork_db.tasks import task_store_spec
        with open_database(
                task_store_spec(ledger_parse.store_path(td)),
                access=Access.WRITE) as store:
            ledger_write.record_review_decision(
                store, artifact, title, decision, actor="test")

    def test_happy_rows_report_examined_not_vacuous(self, tmp_path):
        td = self._target(tmp_path)
        self._record(td, "alpha.html", "P1 · 2026-07-29 22:31 — ship the frobnicate?", "accepted")
        self._record(td, "beta.html", "P2 · 2026-07-28 — keep the old panel?", "pending")
        rep = lint.Report()
        lint.check_review_decision_integrity(td, rep)
        assert not ERRORS(rep, "review_decision")
        assert not [r for r in rep.rows if r[0] == lint.WARN and r[1] == "review_decision"], \
            "well-formed rows must not warn"
        oks = [d for lvl, w, d in rep.rows if w == "review_decision" and lvl == lint.OK]
        assert oks and "2" in oks[0], \
            "the OK row must name the rows examined, or coverage can shrink to silence"

    def test_dangling_question_title_warns(self, tmp_path):
        td = self._target(tmp_path)
        self._record(td, "alpha.html", "P1 · 2026-07-29 22:31 — ship the frobnicate?", "accepted")
        self._record(td, "beta.html", "P9 · 1999-01-01 — no such question anywhere", "rejected")
        # runtime precondition: the fixture genuinely has 2 rows to examine
        import ledger_parse, sqlite3
        conn = sqlite3.connect(f"file:{ledger_parse.store_path(td)}?mode=ro", uri=True)
        assert conn.execute("select count(*) from review_decision").fetchone()[0] == 2
        conn.close()
        rep = lint.Report()
        lint.check_review_decision_integrity(td, rep)
        warns = [d for lvl, w, d in rep.rows if w == "review_decision" and lvl == lint.WARN]
        assert any("beta.html" in d and "no such question" in d for d in warns), \
            f"a dangling question_title must be named: {warns}"
        assert not any("alpha.html" in d and "dangling" in d for d in warns), \
            "a resolvable title must not be flagged"

    def test_prose_claim_conflicting_the_store_warns(self, tmp_path):
        td = self._target(tmp_path)
        self._record(td, "alpha.html", "P1 · 2026-07-29 22:31 — ship the frobnicate?", "accepted")
        # the declared V1 prose grammar claiming the OPPOSITE of the store
        (td / "questions.md").write_text(
            self.QGOOD + "\n- **P3 · 2026-07-30 — tidy-up.** Review (rejected): alpha.html\n")
        rep = lint.Report()
        lint.check_review_decision_integrity(td, rep)
        warns = [d for lvl, w, d in rep.rows if w == "review_decision" and lvl == lint.WARN]
        assert any("alpha.html" in d and "rejected" in d and "accepted" in d for d in warns), \
            f"a prose claim conflicting the store must name both: {warns}"

    def test_prose_claim_agreeing_with_the_store_is_silent(self, tmp_path):
        td = self._target(tmp_path)
        self._record(td, "alpha.html", "P1 · 2026-07-29 22:31 — ship the frobnicate?", "rejected")
        (td / "questions.md").write_text(
            self.QGOOD + "\n- **P3 · 2026-07-30 — tidy-up.** Review (rejected): alpha.html\n")
        rep = lint.Report()
        lint.check_review_decision_integrity(td, rep)
        warns = [d for lvl, w, d in rep.rows if w == "review_decision" and lvl == lint.WARN]
        assert not warns, f"agreement is not a conflict: {warns}"

    def test_markdown_mode_reports_moot_not_coverage(self, tmp_path):
        td = tmp_path / "dw"
        td.mkdir()
        (td / "tasks.md").write_text(TestStoreModeLint.FIXTURE)
        rep = lint.Report()
        lint.check_review_decision_integrity(td, rep)
        rows = [(lvl, d) for lvl, w, d in rep.rows if w == "review_decision"]
        assert rows and not ERRORS(rep, "review_decision"), \
            "markdown-mode must REPORT the check is moot, not vanish"


class TestChatsV1Lint:
    """#504 — lint.check_chats_v1: malformed transcripts and bad chat.json WARN
    (never ERROR — the store degrades silently when a reader skips a chat); an
    absent store and an empty store degrade to silence.

    The WELL-FORMED chats are written through the PRODUCTION writer
    (watch.apply_chat_turn); the DEFECTS (a torn transcript, a bad chat.json)
    are hand-built because the production writer cannot produce them — that is
    exactly what the detector exists to catch. The production line each
    red-proof targets is named in each docstring and sabotaged on lint.py (the
    detector), never on watch.py; restored byte-identical with cp.
    """

    def _dw(self, tmp_path):
        return tmp_path / ".dreamwork"

    def _run(self, dw):
        rep = lint.Report()
        lint.check_chats_v1(dw, lint.load_watch(), rep)
        return rep

    def _warns(self, rep):
        return [d for lvl, w, d in rep.rows if w == "chats-v1" and lvl == lint.WARN]

    def test_absent_store_is_silent(self, tmp_path):
        # no .dreamwork/ at all — a fresh target has no chats
        dw = self._dw(tmp_path)
        rep = self._run(dw)
        assert not [r for r in rep.rows if r[1] == "chats-v1"], \
            "a fresh target with no chats-v1 store must report nothing"

    def test_wellformed_chat_is_ok_with_count(self, tmp_path):
        watch = lint.load_watch()
        watch.apply_chat_turn(str(tmp_path), "c1", "human", "are we shipping?")
        watch.apply_chat_turn(str(tmp_path), "c1", "agent", "yes")
        rep = self._run(self._dw(tmp_path))
        assert not self._warns(rep), f"a well-formed chat must not warn: {self._warns(rep)}"
        oks = [d for lvl, w, d in rep.rows if w == "chats-v1" and lvl == lint.OK]
        assert oks and "1" in oks[0], \
            "the OK row must name the count examined, or coverage can shrink to silence"

    def test_empty_store_is_silent_not_a_vacuous_ok(self, tmp_path):
        # a store root with NO chat dirs must print nothing, not 'all well-formed'
        (self._dw(tmp_path) / "chats-v1").mkdir(parents=True)
        rep = self._run(self._dw(tmp_path))
        assert not [r for r in rep.rows if r[1] == "chats-v1"], \
            "a store with no chat dirs must not print a vacuous OK"

    def test_malformed_transcript_warns(self, tmp_path):
        """Production line: the `if openers != len(turns)` branch in
        check_chats_v1. Sabotage it (drop the branch) and this test reds."""
        watch = lint.load_watch()
        watch.apply_chat_turn(str(tmp_path), "c-good", "human", "fine")
        cdir = self._dw(tmp_path) / "chats-v1" / "c-bad"
        cdir.mkdir(parents=True)
        # a line-start opener with NO close marker: 1 opener, 0 parsed turns
        (cdir / "transcript.md").write_text(
            "<!-- dw-turn role=human at=2026-07-30T01:00:00 -->\n"
            "torn, no close marker\n")
        rep = self._run(self._dw(tmp_path))
        warns = self._warns(rep)
        assert any("c-bad" in d and "malformed" in d for d in warns), \
            f"a torn transcript must be named: {warns}"
        assert not any("c-good" in d for d in warns), \
            "a well-formed chat must not be flagged"

    def test_chat_json_not_valid_warns(self, tmp_path):
        """Production line: the `if data is None` branch in check_chats_v1."""
        watch = lint.load_watch()
        watch.apply_chat_turn(str(tmp_path), "c4", "human", "hi")
        (self._dw(tmp_path) / "chats-v1" / "c4" / "chat.json").write_text("{not json")
        rep = self._run(self._dw(tmp_path))
        warns = self._warns(rep)
        assert any("c4" in d and "not valid JSON" in d for d in warns), \
            f"an invalid chat.json must be named: {warns}"

    def test_chat_json_id_disagrees_with_dir_warns(self, tmp_path):
        """Production line: the `data.get('id') != cdir.name` branch."""
        watch = lint.load_watch()
        watch.apply_chat_turn(str(tmp_path), "c5", "human", "hi")
        (self._dw(tmp_path) / "chats-v1" / "c5" / "chat.json").write_text(
            json.dumps({"id": "WRONG", "mode": "main-dreamer", "created": "x"}))
        rep = self._run(self._dw(tmp_path))
        warns = self._warns(rep)
        assert any("c5" in d and "WRONG" in d and "disagrees" in d for d in warns), \
            f"a chat.json id that disagrees with the dir must be named: {warns}"


# ---------------------------------------------------------------------------
# #592: lint inside a lane WORKTREE must not report a false tasks.md ERROR.
#
# `ledger.sqlite3` is gitignored, so it never travels to a linked worktree;
# `source_of_truth` reads the cutover watermark out of that same file, so its
# absence answers "markdown" and check_tasks falls to the #458 shim, which has
# no `Next id` header. Every lane's verification step therefore ended red.
#
# Production line for this class: the `shared is not None and shared.exists()
# and parse_notice(text)` branch in lint.check_tasks. Force it False (or make
# lint.shared_store_for_worktree return None) and the worktree tests go red;
# force it True unconditionally and the two "still ERRORs" tests go red. Every
# fixture below is a REAL git worktree of a REAL post-cutover repo with a REAL
# absent store — the excuse must be exercised against the actual absence, not
# against a fixture that quietly kept a ledger around.
# ---------------------------------------------------------------------------
class TestWorktreeLedgerAbsent:
    FIXTURE = ("# Task ledger\n\nNext id: **12**\n\n## Open\n\n"
               "- **#10** — a clean open entry · P1 · task · origin: **human**\n\n"
               "## Recently landed\n\n"
               "- **#11** — a clean landed entry · P0 · implementation · "
               "origin: **human** (abc1234)\n")

    def _main_checkout(self, tmp_path):
        """A REAL post-cutover main checkout: the #458 shim committed, the
        gitignored store present and NOT committed — the live repo's shape."""
        import importlib.machinery, importlib.util, io
        import ledger_parse
        repo = Path(__file__).resolve().parent
        loader = importlib.machinery.SourceFileLoader(
            "ud_dw_tasks_migrate_wt", str(repo / "ud-dw-tasks-migrate"))
        spec = importlib.util.spec_from_loader("ud_dw_tasks_migrate_wt", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        root = fresh(tmp_path)
        dw = root / ".dreamwork"
        dw.mkdir()
        (dw / "tasks.md").write_text(self.FIXTURE)
        mod.perform_cutover(str(dw), out=io.StringIO())

        def git(*a):
            return subprocess.run(["git", "-C", str(root), *a],
                                  capture_output=True, text=True, check=True)
        git("init", "-q")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        (root / ".gitignore").write_text(".dreamwork/ledger.sqlite3*\n")
        git("add", ".gitignore", ".dreamwork/tasks.md",
            ".dreamwork/tasks.md.deprecated")
        git("commit", "-qm", "post-cutover seed")
        assert ledger_parse.store_path(dw).exists(), \
            "fixture precondition: the main checkout must carry a real store"
        return root, dw

    def _worktree(self, root, name="lane-x"):
        wt = root.parent / name
        subprocess.run(["git", "-C", str(root), "worktree", "add", "-q",
                        "-b", name, str(wt)],
                       capture_output=True, text=True, check=True)
        return wt, wt / ".dreamwork"

    def _preconditions(self, wtdw):
        """The absence this class is about, asserted rather than assumed.

        Without these the worktree assertions could pass on a fixture that
        still had a ledger — the exact hollowness lessons.md:336 names.
        """
        import ledger_parse
        assert not ledger_parse.store_path(wtdw).exists(), \
            "precondition: the worktree must genuinely have NO store"
        assert ledger_parse.source_of_truth(wtdw) == "markdown", \
            "precondition: the markdown fallback must genuinely engage"
        assert lint.NEXT_ID.search((wtdw / "tasks.md").read_text()) is None, \
            "precondition: the shim must genuinely lack a `Next id` header"

    def _tasks_rows(self, dw):
        rep = lint.Report()
        lint.check_tasks(dw, rep)
        return rep, [(lvl, d) for lvl, w, d in rep.rows if w == "tasks.md"]

    def test_a_worktree_lint_is_not_red(self, tmp_path):
        """The defect itself: a lane worktree ended every run on a false ERROR."""
        root, _ = self._main_checkout(tmp_path)
        wt, wtdw = self._worktree(root)
        self._preconditions(wtdw)
        rep, rows = self._tasks_rows(wtdw)
        assert not ERRORS(rep, "tasks.md"), \
            f"a worktree's absent ledger is not a tasks.md defect: {rows}"
        assert not rep.failed, f"the whole check must be green here: {rows}"
        assert any(lvl == lint.WARN and "ledger absent (worktree)" in d
                   for lvl, d in rows), \
            f"the unrun ledger checks must still be REPORTED: {rows}"

    def test_the_warn_names_the_shared_store_it_verified(self, tmp_path):
        """The WARN must name the store it actually found, not assert one."""
        import ledger_parse
        root, dw = self._main_checkout(tmp_path)
        _, wtdw = self._worktree(root, "lane-named")
        self._preconditions(wtdw)
        _, rows = self._tasks_rows(wtdw)
        detail = next(d for lvl, d in rows if lvl == lint.WARN)
        assert str(ledger_parse.store_path(dw)) in detail, \
            f"the WARN must name the shared store it verified: {detail}"

    def test_a_main_checkout_with_no_store_is_still_an_error(self, tmp_path):
        """The half that stops this becoming a blanket silence."""
        import ledger_parse
        root, dw = self._main_checkout(tmp_path)
        ledger_parse.store_path(dw).unlink()
        for suffix in ("-wal", "-shm"):
            side = Path(str(ledger_parse.store_path(dw)) + suffix)
            if side.exists():
                side.unlink()
        assert (root / ".git").is_dir(), \
            "precondition: a main checkout's .git is a directory"
        assert ledger_parse.source_of_truth(dw) == "markdown", \
            "precondition: the markdown fallback must engage here too"
        rep, rows = self._tasks_rows(dw)
        assert ERRORS(rep, "tasks.md"), \
            f"a genuinely missing ledger in a main checkout must stay red: {rows}"

    def test_a_worktree_whose_shared_store_is_gone_is_still_an_error(self, tmp_path):
        """The worktree excuse is spent on ABSENCE-BY-DESIGN only. If the store
        the worktree shares is itself gone, the ledger is really gone."""
        import ledger_parse
        root, dw = self._main_checkout(tmp_path)
        _, wtdw = self._worktree(root, "lane-orphan")
        self._preconditions(wtdw)
        ledger_parse.store_path(dw).unlink()
        rep, rows = self._tasks_rows(wtdw)
        assert ERRORS(rep, "tasks.md"), \
            f"no shared store means the ledger is genuinely gone: {rows}"

    def test_a_worktree_tasks_md_that_is_not_the_shim_is_still_an_error(self, tmp_path):
        """A real format defect in a worktree must not inherit the excuse."""
        root, _ = self._main_checkout(tmp_path)
        _, wtdw = self._worktree(root, "lane-garbage")
        self._preconditions(wtdw)
        (wtdw / "tasks.md").write_text(
            "# Task ledger\n\n## Open\n\n- **#10** — a header-less ledger\n")
        rep, rows = self._tasks_rows(wtdw)
        assert ERRORS(rep, "tasks.md"), \
            f"only the migration shim is excused, not any headerless file: {rows}"

    def test_the_resolver_refuses_a_main_checkout(self, tmp_path):
        """Unit-level: the discriminator is `.git` being a file, and a main
        checkout must never resolve to a shared store."""
        import ledger_parse
        root, dw = self._main_checkout(tmp_path)
        ledger_parse.store_path(dw).unlink()
        assert lint.shared_store_for_worktree(dw) is None

    def test_the_resolver_is_silent_when_the_store_is_present(self, tmp_path):
        """A worktree that somehow HAS a store needs no excuse at all."""
        root, dw = self._main_checkout(tmp_path)
        _, wtdw = self._worktree(root, "lane-hasstore")
        import shutil, ledger_parse
        shutil.copy2(ledger_parse.store_path(dw), ledger_parse.store_path(wtdw))
        assert lint.shared_store_for_worktree(wtdw) is None

    def test_a_separate_git_dir_main_checkout_is_refused(self, tmp_path):
        """A main checkout is NOT identified by `.git` being a directory alone.

        `git init --separate-git-dir` gives a MAIN checkout a `.git` FILE, the
        same shape a linked worktree has, so the `.git`-is-a-file guard cannot
        decide this one — only the `<common>/worktrees/<name>` layout can. Found
        by red-proofing: deleting the is-a-file guard left every other test in
        this class green (a directory `.git` fails `read_text` into the OSError
        path anyway), so this is the case that gives the resolver's shape check
        something real to be right about.
        """
        import ledger_parse
        root = fresh(tmp_path)
        gitdir = fresh(tmp_path)
        subprocess.run(["git", "init", "-q", f"--separate-git-dir={gitdir}",
                        str(root)], capture_output=True, text=True, check=True)
        dw = root / ".dreamwork"
        dw.mkdir()
        assert (root / ".git").is_file(), \
            "precondition: --separate-git-dir must give a main checkout a .git FILE"
        assert not ledger_parse.store_path(dw).exists(), \
            "precondition: no store, so the resolver actually gets past its first guard"
        assert lint.shared_store_for_worktree(dw) is None, \
            "a separate-git-dir MAIN checkout must not be excused as a worktree"


# ---------------------------------------------------------------------------
# #611: a ledger check that examined NOTHING must say so.
#
# #592 made the `tasks.md` row WARN honestly inside a lane worktree; its
# neighbours went on printing nothing at all, and silent absence reads as a
# pass. Measured on the live repo before writing a line of this: `lint
# --target <worktree>` silently lost `origin recorded on all 390 entries`
# (check_task_origins), `section split agrees with watch.py`
# (check_ledger_sections) and all 7 of #323's stale-open WARNs
# (check_landed_still_open), plus three checks that examine entries but only
# ever speak on a defect (check_self_completed_open, check_human_blocker,
# check_landed_asks).
#
# Production line for this class: the `note_ledger_skip(...)` calls at each
# check's existing silent-return, and `lint.check_ledger_skips` rendering
# them. Delete any one call and the "names every skipped check" test goes
# red; make `check_ledger_skips` emit unconditionally and the "must NOT
# appear when the checks ran" test goes red — that second direction is what
# stops this becoming a row that is always present and therefore ignored.
#
# Fixtures are REAL git worktrees of REAL post-cutover repos with a REAL
# absent store, reusing the #592 class's builders rather than a second copy
# (lessons.md:336 — a fixture that quietly kept a ledger would make every
# assertion here pass for the wrong reason).
# ---------------------------------------------------------------------------
class TestLedgerSkipsAreReported:
    # The #592 class's builders, reused rather than duplicated. A pytest test
    # class has no __init__, so instantiating it is just a namespace grab —
    # and a second copy of "build a real post-cutover repo + worktree" is the
    # thing most likely to drift into a fixture that keeps a ledger.
    _fx = TestWorktreeLedgerAbsent()

    def _repo_with_a_landing(self, tmp_path):
        """A post-cutover main checkout whose git history names a close.

        `check_landed_still_open` returns before it ever looks at the ledger
        when git names NO close/merge commit, so without this commit that
        check could not reach its skip site and the test would silently
        assert over five checks while claiming six. `check_landed_asks`
        needs a `questions.md` for the same reason — found by this test
        going red at five, which is what a discriminating fixture is for.
        """
        root, dw = self._fx._main_checkout(tmp_path)
        (dw / "questions.md").write_text(GOOD)
        subprocess.run(["git", "-C", str(root), "commit", "-q", "--allow-empty",
                        "-m", "close(#10): the landing this fixture needs"],
                       capture_output=True, text=True, check=True)
        subprocess.run(["git", "-C", str(root), "add", ".dreamwork/questions.md"],
                       capture_output=True, text=True, check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "questions"],
                       capture_output=True, text=True, check=True)
        return root, dw

    def _skips(self, root):
        rep = lint.Report()
        lint.run_checks(root / ".dreamwork", lint.load_watch(), rep)
        return rep, list(rep.ledger_skips)

    def _skip_rows(self, rep):
        return [d for lvl, w, d in rep.rows if w == "ledger checks"]

    EXPECTED = ["check_task_origins", "check_ledger_sections",
                "check_landed_still_open", "check_self_completed_open",
                "check_human_blocker", "check_landed_asks",
                "check_title_blocked_claim"]

    def test_a_worktree_names_every_ledger_check_that_examined_nothing(self, tmp_path):
        """The defect: six checks went silent and the report said nothing."""
        root, _ = self._repo_with_a_landing(tmp_path)
        wt, wtdw = self._fx._worktree(root, "lane-skips")
        self._fx._preconditions(wtdw)
        rep, skips = self._skips(wt)
        assert sorted(skips) == sorted(self.EXPECTED), \
            f"every check that examined nothing must be named: {skips}"
        rows = self._skip_rows(rep)
        assert len(rows) == 1, f"one row, not one per skipped check: {rows}"
        for name in self.EXPECTED:
            assert name in rows[0], f"{name} unnamed in the row: {rows[0]}"
        assert not rep.failed, "a skip is missing coverage, not a target defect"

    def test_the_row_is_a_warn_never_an_error(self, tmp_path):
        root, _ = self._repo_with_a_landing(tmp_path)
        wt, wtdw = self._fx._worktree(root, "lane-skiplevel")
        self._fx._preconditions(wtdw)
        rep, _ = self._skips(wt)
        assert [lvl for lvl, w, _ in rep.rows if w == "ledger checks"] == [lint.WARN]

    def test_every_named_check_is_a_real_function(self, tmp_path):
        """The names are strings, so they can drift from the code that skipped.

        A row naming a check that no longer exists is worse than no row: the
        reader goes looking for coverage that was renamed away.
        """
        root, _ = self._repo_with_a_landing(tmp_path)
        wt, wtdw = self._fx._worktree(root, "lane-skipnames")
        self._fx._preconditions(wtdw)
        _, skips = self._skips(wt)
        assert skips, "precondition: something must have skipped"
        for name in skips:
            assert callable(getattr(lint, name, None)), \
                f"{name} is named as skipped but is not a lint check"

    def test_the_row_is_absent_when_the_ledger_checks_really_ran(self, tmp_path):
        """The direction that stops this becoming an always-on, ignored row.

        Same repo, same commit, same checks — linted in the MAIN checkout,
        where the store is present and every check has entries to examine.
        """
        import ledger_parse
        root, dw = self._repo_with_a_landing(tmp_path)
        assert ledger_parse.store_path(dw).exists(), \
            "precondition: the main checkout really does carry the store"
        assert ledger_parse.source_of_truth(dw) == "store", \
            "precondition: the ledger checks really do get real entries"
        rep, skips = self._skips(root)
        assert skips == [], f"nothing skipped here, so nothing may be named: {skips}"
        assert self._skip_rows(rep) == [], \
            "a row that is always present is a row nobody reads"

    def test_the_live_repo_reports_no_skips(self, frozen_tree):
        """The dogfood: this repo's own main checkout must show no skip row.

        `frozen_tree` IS a linked worktree, so its store is absent by design —
        materialize one the way the #592 dogfood does, then the ledger checks
        have real entries and the row must not appear.
        """
        dw = frozen_tree / ".dreamwork"
        led = Path(__file__).resolve().parent / ".dreamwork" / "tasks.md.deprecated"
        _materialize_store(dw, led.read_text(), frozen_tree)
        assert lint.source_of_truth(dw) == "store", \
            "precondition: store mode, or this passes on the #592 excuse"
        rep = lint.Report()
        lint.run_checks(dw, lint.load_watch(), rep)
        assert rep.ledger_skips == [], \
            f"the live ledger gives every check something to examine: {rep.ledger_skips}"

    def test_a_pre_cutoff_only_ledger_is_not_reported_as_skipped(self):
        """`check_task_origins` EXAMINED those entries; none were in scope.

        Every fresh project starts at #1, so counting "no post-cutoff entries"
        as a skip would put this row on every young project forever — the
        ignored-row failure the check exists to prevent.
        """
        text = ("## Open\n\n- **#3** — an old entry · P1 · task\n\n"
                "## Recently landed\n\n- **#4** — another old one · P2 · task\n")
        rep = lint.Report()
        lint.check_task_origins(text, rep)
        assert rep.ledger_skips == [], \
            "entries were examined; none were in scope — that is a run, not a skip"

    def test_an_empty_ledger_is_reported_as_skipped(self):
        """The other half of the same discrimination: nothing examined."""
        rep = lint.Report()
        lint.check_task_origins("## Open\n\n## Recently landed\n", rep)
        assert rep.ledger_skips == ["check_task_origins"]

    def test_nothing_landed_yet_is_not_reported_as_skipped(self, tmp_path):
        """`check_landed_asks` over a ledger with opens but no landings ran."""
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "tasks.md").write_text(
            "# Tasks\n\nNext id: **6**\n\n## Open\n\n- **#5** — open work\n\n"
            "## Recently landed\n")
        (dw / "questions.md").write_text(GOOD)
        watch = lint.load_watch()
        open_ids, landed = watch.parse_ledger((dw / "tasks.md").read_text())
        assert open_ids and not landed, \
            "precondition: opens exist, nothing has landed"
        rep = lint.Report()
        lint.check_landed_asks(dw, watch, rep)
        assert rep.ledger_skips == [], \
            "a real correlation over a ledger with no landings is not a skip"

    def test_the_renderer_is_silent_with_nothing_recorded(self):
        rep = lint.Report()
        lint.check_ledger_skips(rep)
        assert rep.rows == []

    def test_a_skip_recorded_twice_is_named_once(self):
        """`check_human_blocker` has two skip sites; a repeat is one skip."""
        rep = lint.Report()
        lint.note_ledger_skip(rep, "check_human_blocker")
        lint.note_ledger_skip(rep, "check_human_blocker")
        assert rep.ledger_skips == ["check_human_blocker"]

    def test_the_renderer_runs_last_in_run_checks(self):
        """It can only speak once every skipping check has had its turn."""
        import inspect
        body = [ln.strip() for ln in
                inspect.getsource(lint.run_checks).splitlines()
                if ln.strip().startswith("check_")]
        assert body[-1] == "check_ledger_skips(rep)", \
            f"check_ledger_skips must be the last check called: {body[-3:]}"


# ---------------------------------------------------------------------------
# #612: the fold prompt must not reproduce the hand-off body.
#
# `handoffs.md` writes each hand-off as ONE physical line and the `· by
# <claimer>` grammar runs to end of line, so the claimer field carries the
# whole body. Measured on the live file before writing this: 99 pending rows,
# median claimer 1470 characters, longest 4568; the #592 hand-off is 3809 and
# dominated the main checkout's entire lint report. A report nobody can skim
# is a report nobody reads — the same tune-out failure #592 existed to stop,
# arriving by volume instead of by false positives.
#
# Production line for this class: `lint.handoff_quote` and its three call
# sites in check_handoffs. Return the field unchanged and the truncation tests
# go red; drop the cap and the no-terminator test goes red; move the sha back
# behind the quote and nothing goes red — which is why the sha test asserts
# PRESENCE under every input rather than position.
# ---------------------------------------------------------------------------
class TestHandoffQuoteTruncation:
    # The live shape, abridged: a lane id, an em-dash, then prose. The first
    # sentence ends at `mine".` — every earlier dot is inside `lint.py` or
    # `tasks.md`, followed by a letter, which is the case measured on all 99
    # live claimers and the reason the terminator rule needs its lookahead.
    BODY = ("lane-592lint — `lint.py` no longer reports a FALSE `ERROR "
            "tasks.md — no 'Next id'` inside a lane worktree, the red that "
            "#565/#569 each passed on as \"pre-existing, not mine\". "
            + "Then a great deal more prose. " * 60 + "MARKER-AT-THE-END.")
    FIRST = ("lane-592lint — `lint.py` no longer reports a FALSE `ERROR "
             "tasks.md — no 'Next id'` inside a lane worktree, the red that "
             "#565/#569 each passed on as \"pre-existing, not mine\".")

    def _pending(self, claimer, nid="5", sha="abc1234"):
        return ("# Hand-offs\n\n## Pending\n\n"
                f"- **#{nid}** · landed `{sha}` · 2026-07-28 14:30 · by "
                f"{claimer}\n\n## Folded\n")

    def _warn(self, tmp_path, handoffs, ledger=None):
        t = fresh(tmp_path)
        dw = t / ".dreamwork"
        dw.mkdir()
        (dw / "tasks.md").write_text(ledger or TestHandoffs.LEDGER)
        (dw / "handoffs.md").write_text(handoffs)
        rep = lint.Report()
        lint.check_handoffs(dw, lint.load_watch(), rep)
        warns = [d for lvl, w, d in rep.rows
                 if w == "handoffs.md" and lvl == lint.WARN]
        assert len(warns) == 1, warns
        return warns[0]

    def test_the_fold_prompt_does_not_reproduce_the_body(self, tmp_path):
        """THE defect: the whole hand-off, verbatim, in one report row."""
        assert len(self.BODY) > 1500, "precondition: a realistically long body"
        warn = self._warn(tmp_path, self._pending(self.BODY))
        assert "MARKER-AT-THE-END" not in warn, \
            "the tail of the body is in the row — it was reproduced whole"
        assert len(warn) < 500, f"row is {len(warn)} chars, not skimmable: {warn}"

    def test_the_first_sentence_survives_whole(self, tmp_path):
        """Truncating to the first sentence means the WHOLE first sentence."""
        assert len(self.FIRST) < lint.HANDOFF_QUOTE_CAP, \
            "precondition: this sentence is inside the cap, so the cap is not what keeps it"
        warn = self._warn(tmp_path, self._pending(self.BODY))
        assert self.FIRST in warn, f"first sentence cut short: {warn}"

    def test_a_dotted_filename_is_not_a_sentence_end(self):
        """The measured trap: `lint.py` and `tasks.md` in the first sentence.

        A terminator rule without the whitespace lookahead cuts at `lint.`,
        which would make every row in this repo's own report useless.
        """
        assert lint.handoff_quote("lane-x — `lint.py` and tasks.md both work.") \
            == "lane-x — `lint.py` and tasks.md both work."

    def test_no_sentence_terminator_falls_back_to_the_cap(self):
        """30 of the 99 live claimers have no terminator at all.

        The decision: no guessing at an implied sentence — the whole field is
        the candidate and the cap bounds it, marked with an ellipsis.
        """
        field = "lane-y — " + "an unterminated run of words " * 40
        assert "." not in field, "precondition: genuinely no terminator"
        out = lint.handoff_quote(field)
        assert out.endswith("…"), out
        assert len(out) <= lint.HANDOFF_QUOTE_CAP + 1, len(out)

    def test_a_first_sentence_longer_than_the_cap_is_still_capped(self):
        """Live first sentences run to 759 characters; the cap is a backstop
        over the sentence rule, not only over the no-terminator fallback."""
        field = "lane-z — " + "word " * 300 + "end."
        assert lint.HANDOFF_SENTENCE_END.match(field), \
            "precondition: this DOES have a terminator, so the sentence rule fires first"
        out = lint.handoff_quote(field)
        assert len(out) <= lint.HANDOFF_QUOTE_CAP + 1, len(out)
        assert out.endswith("…"), out

    def test_the_rule_is_the_first_sentence_not_the_first_n_characters(self):
        """A GREEN red-run, found and reported rather than swallowed.

        Deleting the first-sentence extraction (`quote = m.group(1) if m else
        flat` -> `quote = flat`) left all 16 tests in this class GREEN,
        because `BODY`'s first sentence is 188 characters and the cap is 200
        — the cap alone kept it, and nothing here could tell a sentence rule
        from a character budget. This is the case that can: a first sentence
        well inside the cap, followed by prose the cap alone would keep.
        """
        field = "lane-s — a short first sentence. " + "trailing prose " * 40
        first = "lane-s — a short first sentence."
        assert len(first) < lint.HANDOFF_QUOTE_CAP, \
            "precondition: the sentence is well inside the cap"
        assert len(field) > lint.HANDOFF_QUOTE_CAP, \
            "precondition: the cap alone would keep more than the sentence"
        out = lint.handoff_quote(field)
        assert out == first, out
        assert "trailing" not in out, \
            "prose past the first sentence survived — this is a cap, not a sentence rule"

    def test_the_cut_lands_on_a_word_boundary(self):
        """A second GREEN red-run, same class, same lesson (lessons.md:336).

        This test used to assert `does not end with a space` and `is a prefix
        of the field` — BOTH true of a naive `field[:CAP]`, so removing the
        boundary logic changed nothing it could see. The real property is
        that the character AFTER the kept prefix is whitespace: no word split.
        """
        field = "lane-w — " + "alpha bravo charlie delta " * 40
        assert not field[:lint.HANDOFF_QUOTE_CAP].endswith(" ") \
            and not field[lint.HANDOFF_QUOTE_CAP].isspace(), \
            "precondition: a naive cut at the cap really would split a word here"
        out = lint.handoff_quote(field)
        kept = out.rstrip("…")
        assert field.startswith(kept), "the kept prefix must be verbatim, not reflowed"
        assert field[len(kept)].isspace(), \
            f"the cut split a word: ...{kept[-20:]!r} | {field[len(kept):len(kept) + 10]!r}"
        assert not kept.endswith(" "), kept

    def test_a_short_claimer_is_unchanged(self, tmp_path):
        """The ordinary hand-off must render exactly as it always has."""
        assert lint.handoff_quote("dreamer-5 — the fix") == "dreamer-5 — the fix"
        warn = self._warn(tmp_path, self._pending("dreamer-5 — the fix"))
        assert "dreamer-5 — the fix" in warn and "…" not in warn, warn

    def test_the_quote_is_one_line(self):
        """A wrapped field inside a one-line report row is unreadable
        whatever its length, so whitespace is collapsed before anything else."""
        out = lint.handoff_quote("lane-q —\n  wrapped\n  over lines.")
        assert out == "lane-q — wrapped over lines."

    @pytest.mark.parametrize("claimer", [
        "lane-a — " + "x" * 4000,                       # no terminator, huge
        "lane-b — " + "sentence. " * 400,               # terminator, huge
        "lane-c.",                                      # terminator immediately
        "lane-d — a body naming abc1234 late " * 200,   # sha-like text in the body
        "z",                                            # the shortest legal field
    ])
    def test_the_sha_survives_every_truncation(self, tmp_path, claimer):
        """The sha is the actionable part; a truncation that can drop it is a
        regression. It survives by CONSTRUCTION — it is its own interpolated
        field, printed BEFORE the quote — so no input can push it off the row.
        """
        warn = self._warn(tmp_path, self._pending(claimer, sha="abc1234"))
        assert "sha `abc1234`" in warn, warn
        assert warn.index("abc1234") < warn.index("by "), \
            "the sha must precede the writer-controlled quote"

    def test_the_landed_but_unfolded_prompt_is_truncated_too(self, tmp_path):
        """#576's branch carries the same claimer and had the same defect."""
        warn = self._warn(tmp_path, self._pending(self.BODY, nid="6"))
        assert "no `→ folded` line" in warn, warn
        assert "MARKER-AT-THE-END" not in warn, warn
        assert "sha `abc1234`" in warn, warn

    def test_the_malformed_entry_quote_is_truncated_too(self, tmp_path):
        """The third site: `malformed` holds the SAME physical line, so it
        carries the same whole body. It fires on no live entry today, which
        is exactly why fixing only the loud branch would leave it to
        resurface the first time this one fires.
        """
        handoffs = ("# Hand-offs\n\n## Pending\n\n"
                    f"- **#5** this line does not follow the grammar. "
                    + "padding words " * 300 + "MARKER-AT-THE-END\n\n## Folded\n")
        warn = self._warn(tmp_path, handoffs)
        assert "grammar" in warn, warn
        assert "MARKER-AT-THE-END" not in warn, \
            "the malformed line was reproduced whole"

    def test_every_prose_field_in_check_handoffs_goes_through_the_quote(self):
        """Wiring, the #554 idiom: a fourth row interpolating a raw claimer
        or line would reintroduce this defect silently."""
        import inspect
        src = inspect.getsource(lint.check_handoffs)
        assert "{claimer}" not in src, \
            "a raw claimer is interpolated somewhere — use handoff_quote()"
        assert "{line!r}" not in src, \
            "a raw hand-off line is interpolated somewhere — use handoff_quote()"
        assert src.count("handoff_quote(") == 3, \
            f"expected 3 quoted fields, found {src.count('handoff_quote(')}"


class TestBriefLaneScratch:
    """#652: a brief teaching the `cp` restore protocol names a lane-private dir.

    Concurrent lanes share one harness scratchpad (one CLI session, one
    `CLAUDE_CODE_SESSION_ID`, one directory — measured). Two lanes snapshotting
    to the same generic filename means one restore writes the other's bytes
    while BOTH `cmp` checks pass. Cutoff is content-resolved from SKILL.md
    (LANE_SCRATCH_PHRASE), never pinned.

    Production lines named per test (what must change for it to fail):
    - flagged: the `if not brief_names_lane_private_snapshot(text)` branch in
      classify_brief_lane_scratch / the ERROR add in check_brief_lane_scratch
    - grandfathered: the `add_t <= cutoff_t` branch that skips pre-rule briefs
    - scope: RESTORE_CLAUSE_RE — a brief that does not teach the protocol is
      not put in front of the hazard and is not in scope
    - satisfied: brief_names_lane_private_snapshot, both accepted shapes
    - cutoff content: resolve_lane_scratch_cutoff + the phrase constant + the
      post-resolve "phrase in blob" guard
    - precondition: live tree has at least one restore-teaching brief (a check
      that silently matches nothing passes forever)
    """

    PHRASE = lint.LANE_SCRATCH_PHRASE
    TEACH = "restore by `cp` (never `git checkout`), confirm with `cmp`"

    def _git_repo(self, tmp_path):
        import subprocess
        t = fresh(tmp_path)

        def git(*a, check=True):
            return subprocess.run(
                ["git", "-C", str(t), *a],
                capture_output=True, text=True, check=check)

        git("init", "-q")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        return t, git

    def _landed(self, tmp_path):
        """Repo whose SKILL.md carries the rule, ready for post-cutoff briefs."""
        import time
        t, git = self._git_repo(tmp_path)
        (t / "SKILL.md").write_text(f"# skill\n\n{self.PHRASE}\n", encoding="utf-8")
        git("add", "SKILL.md")
        git("commit", "-qm", "lane-private snapshot rule lands")
        time.sleep(1.1)
        (t / ".dreamwork" / "docs" / "briefs").mkdir(parents=True)
        return t, git

    def _brief(self, t, git, name, body):
        (t / ".dreamwork" / "docs" / "briefs" / name).write_text(body, encoding="utf-8")
        git("add", f".dreamwork/docs/briefs/{name}")
        git("commit", "-qm", f"add {name}")

    def _errors(self, t):
        rep = lint.Report()
        lint.check_brief_lane_scratch(t / ".dreamwork", rep)
        return [d for lvl, w, d in rep.rows if lvl == lint.ERROR and w == "briefs"], rep

    def test_a_post_cutoff_teaching_brief_with_a_generic_path_is_flagged(self, tmp_path):
        """Production line: the missing-lane-private ERROR. THE defect: the brief
        teaches the restore protocol and points the lane at a shared scratchpad."""
        t, git = self._landed(tmp_path)
        self._brief(t, git, "999-generic.md",
                    "# Brief\n\nWorktree: `.worktrees/lane-999x`\n\n"
                    f"Snapshot to `$SCRATCH/router.js.orig`, {self.TEACH}\n")

        scope = lint.classify_brief_lane_scratch(t)
        assert "999-generic.md" in scope["teaching"], scope
        assert "999-generic.md" in scope["in_scope"], scope
        assert "999-generic.md" in scope["missing"], scope

        # Both findings are true of this brief and both are reported: it names
        # no private directory AND points at the shared scratchpad. One fix must
        # not hide the other.
        assert "999-generic.md" in scope["shared"], scope
        errors, rep = self._errors(t)
        assert len(errors) == 2, rep.render()
        assert all("999-generic.md" in e and "#652" in e for e in errors), errors

    def test_naming_the_helper_satisfies_the_rule(self, tmp_path):
        """Production line: the LANE_SCRATCH_TOKEN_RE branch of
        brief_names_lane_private_snapshot."""
        t, git = self._landed(tmp_path)
        self._brief(t, git, "998-helper.md",
                    "# Brief\n\nWorktree: `.worktrees/lane-998y`\n\n"
                    f'`S="$(dev/lane_scratch.py snap)"`, {self.TEACH}\n')
        errors, rep = self._errors(t)
        assert errors == [], rep.render()

    def test_a_hand_rolled_path_carrying_the_lane_name_satisfies_the_rule(self, tmp_path):
        """Production line: the WORKTREE_LANE_RE branch — the property that
        matters is uniqueness, not a particular helper."""
        t, git = self._landed(tmp_path)
        self._brief(t, git, "997-hand.md",
                    "# Brief\n\nWorktree: `.worktrees/lane-997z`\n\n"
                    f"Snapshot to `/home/x/.cache/lane-997z/router.js`, {self.TEACH}\n")
        errors, rep = self._errors(t)
        assert errors == [], rep.render()

    def test_the_lane_name_in_the_worktree_path_alone_does_not_satisfy(self, tmp_path):
        """The false-green this check must not have: every brief names its
        worktree, so counting that occurrence would pass everything forever."""
        assert not lint.brief_names_lane_private_snapshot(
            "Worktree: `/home/x/.worktrees/lane-996w`\nSnapshot to `$S/bak`.\n")

    def test_a_pre_cutoff_teaching_brief_is_grandfathered(self, tmp_path):
        """Production line: the `add_t <= cutoff_t` grandfather branch."""
        import time
        t, git = self._git_repo(tmp_path)
        (t / ".dreamwork" / "docs" / "briefs").mkdir(parents=True)
        (t / ".dreamwork" / "docs" / "briefs" / "100-old.md").write_text(
            f"# Brief\n\nWorktree: `.worktrees/old`\n\nUse `$S/bak`, {self.TEACH}\n",
            encoding="utf-8")
        (t / "SKILL.md").write_text("# skill\n\nno rule yet\n", encoding="utf-8")
        git("add", "SKILL.md", ".dreamwork/docs/briefs/100-old.md")
        git("commit", "-qm", "teaching brief before the rule")
        time.sleep(1.1)
        (t / "SKILL.md").write_text(f"# skill\n\n{self.PHRASE}\n", encoding="utf-8")
        git("add", "SKILL.md")
        git("commit", "-qm", "rule lands later")

        scope = lint.classify_brief_lane_scratch(t)
        assert "100-old.md" in scope["grandfathered"], scope
        assert "100-old.md" not in scope["in_scope"], scope
        errors, rep = self._errors(t)
        assert errors == [], rep.render()

    def test_a_brief_that_does_not_teach_the_protocol_is_out_of_scope(self, tmp_path):
        """Production line: RESTORE_CLAUSE_RE. A brief that never puts the lane
        in front of the hazard is not required to answer it."""
        t, git = self._landed(tmp_path)
        self._brief(t, git, "995-quiet.md",
                    "# Brief\n\nWorktree: `.worktrees/lane-995q`\n\nJust write the code.\n")
        scope = lint.classify_brief_lane_scratch(t)
        assert "995-quiet.md" not in scope["teaching"], scope
        errors, rep = self._errors(t)
        assert errors == [], rep.render()

    def test_an_unresolvable_cutoff_is_loud(self, tmp_path):
        """Production line: the no-cutoff ERROR. A reworded SKILL.md phrase must
        not silently grandfather every brief (#405's lesson, reused)."""
        t, git = self._git_repo(tmp_path)
        (t / "SKILL.md").write_text("# skill\n\nphrase was reworded away\n",
                                    encoding="utf-8")
        (t / ".dreamwork" / "docs" / "briefs").mkdir(parents=True)
        (t / ".dreamwork" / "docs" / "briefs" / "994-t.md").write_text(
            f"# Brief\n\nUse `$S/bak`, {self.TEACH}\n", encoding="utf-8")
        git("add", "SKILL.md", ".dreamwork/docs/briefs/994-t.md")
        git("commit", "-qm", "no rule phrase anywhere")

        errors, rep = self._errors(t)
        assert len(errors) == 1, rep.render()
        assert "could not resolve" in errors[0], errors[0]

    def test_no_teaching_brief_is_silence_not_a_pass(self, tmp_path):
        """Production line: the any_teaching precondition. A check that matched
        nothing must not emit a clean OK row."""
        t, git = self._landed(tmp_path)
        self._brief(t, git, "993-none.md", "# Brief\n\nNothing about restores.\n")
        rep = lint.Report()
        lint.check_brief_lane_scratch(t / ".dreamwork", rep)
        assert rep.rows == [], rep.render()

    def test_the_ok_row_states_its_coverage(self, tmp_path):
        """A check that stops matching must not look like one that examined all."""
        t, git = self._landed(tmp_path)
        self._brief(t, git, "992-ok.md",
                    "# Brief\n\nWorktree: `.worktrees/lane-992k`\n\n"
                    f'`S="$(dev/lane_scratch.py snap)"`, {self.TEACH}\n')
        rep = lint.Report()
        lint.check_brief_lane_scratch(t / ".dreamwork", rep)
        oks = [d for lvl, w, d in rep.rows if lvl == lint.OK and w == "briefs"]
        assert len(oks) == 1, rep.render()
        assert "restore-teaching brief" in oks[0], oks[0]
        assert "in scope" in oks[0] and "grandfathered" in oks[0], oks[0]

    def test_this_repo_has_restore_teaching_briefs(self):
        """Dogfood precondition: the live tree must give the check material.

        Counted straight off the briefs rather than through
        classify_brief_lane_scratch, because that returns an empty scope when
        the cutoff is unresolvable — which would make a broken scope marker and
        a broken cutoff indistinguishable, and both look like a pass.
        """
        from dev.citation_audit import _default_briefs_dir

        briefs = _default_briefs_dir()
        teaching = [p.name for p in briefs.glob("*.md")
                    if lint.RESTORE_CLAUSE_RE.search(
                        p.read_text(encoding="utf-8", errors="replace"))]
        common = subprocess.run(
            ["git", "-C", str(lint.SKILL_DIR), "rev-parse",
             "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, check=True,
        )
        main_briefs = (Path(common.stdout.strip()).parent / ".dreamwork" /
                       "docs" / "briefs")
        authoritative = {
            p.name for p in main_briefs.glob("*.md")
            if lint.RESTORE_CLAUSE_RE.search(
                p.read_text(encoding="utf-8", errors="replace"))
        }
        assert set(teaching) == authoritative, (
            "restore-teaching corpus truncated or divergent: default saw "
            f"{len(teaching)} / main checkout {len(authoritative)}; "
            f"missing {len(authoritative - set(teaching))}, "
            f"extra {len(set(teaching) - authoritative)}")
        assert len(teaching) >= 10, (
            f"only {len(teaching)} restore-teaching briefs — the scope marker "
            "has stopped matching, and a check that matches nothing passes forever")

    def test_the_cutoff_phrase_is_on_one_line_in_this_skill_md(self):
        """The fragility that actually bit: `git log -S` is a literal search, so
        a line break inside LANE_SCRATCH_PHRASE makes the cutoff unresolvable and
        the check ERRORs instead of examining anything. Cheaper to catch here."""
        text = (lint.SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        assert lint.LANE_SCRATCH_PHRASE in text, (
            f"{lint.LANE_SCRATCH_PHRASE!r} does not appear contiguously in "
            "SKILL.md — rewrap the paragraph or the cutoff cannot resolve")

    def test_the_helper_in_prose_does_not_excuse_a_shared_path_in_the_example(
            self, tmp_path):
        """Production line: the SHARED_SCRATCHPAD_RE finding. The realistic
        failure — helper mentioned, older worked example pasted underneath. The
        lane copies the example, so naming the helper must not buy a pass."""
        t, git = self._landed(tmp_path)
        self._brief(t, git, "991-mixed.md",
                    "# Brief\n\nWorktree: `.worktrees/lane-991m`\n\n"
                    "Use `dev/lane_scratch.py` for scratch.\n"
                    f"Snapshot: `cp client/router.js $SCRATCH/router.js.orig`, {self.TEACH}\n")
        scope = lint.classify_brief_lane_scratch(t)
        assert "991-mixed.md" not in scope["missing"], "helper is named, so not 'missing'"
        assert "991-mixed.md" in scope["shared"], scope
        errors, rep = self._errors(t)
        assert len(errors) == 1, rep.render()
        assert "SHARED" in errors[0], errors[0]

    def test_the_derived_idiom_is_not_flagged_as_shared(self, tmp_path):
        """`$S/` after `S="$(dev/lane_scratch.py …)"` is the CORRECT idiom and
        must not be swept up by the shared-scratchpad matcher."""
        t, git = self._landed(tmp_path)
        self._brief(t, git, "990-good.md",
                    "# Brief\n\nWorktree: `.worktrees/lane-990g`\n\n"
                    '`S="$(dev/lane_scratch.py snap)"`; `cp f "$S/f"`; '
                    f"{self.TEACH}\n")
        errors, rep = self._errors(t)
        assert errors == [], rep.render()

    def test_a_shared_path_suppresses_the_ok_row(self, tmp_path):
        """A finding must not sit next to a clean coverage row."""
        t, git = self._landed(tmp_path)
        self._brief(t, git, "989-sh.md",
                    "# Brief\n\nWorktree: `.worktrees/lane-989s`\n\n"
                    f"`dev/lane_scratch.py`; snapshot to `/tmp/claude-1000/x/scratchpad/bak`, {self.TEACH}\n")
        rep = lint.Report()
        lint.check_brief_lane_scratch(t / ".dreamwork", rep)
        assert [d for lvl, w, d in rep.rows if lvl == lint.OK and w == "briefs"] == [], \
            rep.render()


class TestCommitCleanup:
    """#693 — commit.cleanup must preserve '#' lines, because commit
    subjects start with '#NNN' and `git rebase --continue` takes the editor
    path where unset/strip/default delete every '#' line.

    These build a REAL git repo (the check shells out to `git config`), and
    call the production check directly — `lint.check_commit_cleanup` is the
    line that would have to change for any of these to fail.
    """

    def _repo(self, tmp_path):
        root = fresh(tmp_path)
        subprocess.run(["git", "-C", str(root), "init", "-q"], check=True,
                       capture_output=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "t@t"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "t"],
                       check=True, capture_output=True)
        return root

    def _check(self, root):
        rep = lint.Report()
        lint.check_commit_cleanup(root / ".dreamwork", rep)
        rows = [(lvl, d) for lvl, w, d in rep.rows if w == "commit.cleanup"]
        return rows

    # ── green: each safe value passes ───────────────────────────────────

    @pytest.mark.parametrize("value", sorted(lint.COMMIT_CLEANUP_SAFE))
    def test_a_safe_value_is_clean(self, tmp_path, value):
        root = self._repo(tmp_path)
        subprocess.run(
            ["git", "-C", str(root), "config", "commit.cleanup", value],
            check=True, capture_output=True)
        rows = self._check(root)
        assert rows == [(lint.OK, f"'{value}' preserves '#' lines")], rows

    # ── direction 1: each dangerous value reds on the discriminating msg ─

    def test_unset_is_an_error(self, tmp_path):
        """The dangerous default: unset resolves to strip on the editor path."""
        root = self._repo(tmp_path)
        # precondition: genuinely unset (git config --get exits 1)
        got = subprocess.run(["git", "-C", str(root), "config", "--get",
                              "commit.cleanup"], capture_output=True, text=True)
        assert got.returncode == 1 and got.stdout == "", \
            "precondition: commit.cleanup must be genuinely unset here"
        rows = self._check(root)
        assert lint.ERROR in [lvl for lvl, _ in rows], rows
        d = next(dd for lvl, dd in rows if lvl == lint.ERROR)
        assert "unset" in d and "strip" in d, \
            "must name the unset→strip default as the cause"

    @pytest.mark.parametrize("value", ["strip", "default"])
    def test_a_sharp_eating_value_is_an_error_even_though_set(self, tmp_path, value):
        """Direction 2's discriminating case: 'strip' and 'default' ARE set
        and non-empty, so a presence-only check would pass on them — the
        exact false-green this check must refuse."""
        root = self._repo(tmp_path)
        subprocess.run(
            ["git", "-C", str(root), "config", "commit.cleanup", value],
            check=True, capture_output=True)
        # precondition: the value is genuinely set and equal (presence would pass)
        got = subprocess.run(["git", "-C", str(root), "config", "--get",
                              "commit.cleanup"], capture_output=True, text=True)
        assert got.stdout.strip() == value, \
            f"precondition: commit.cleanup genuinely set to {value!r}"
        rows = self._check(root)
        assert lint.ERROR in [lvl for lvl, _ in rows], \
            f"{value!r} eats '#' lines and must ERROR despite being set"
        d = next(dd for lvl, dd in rows if lvl == lint.ERROR)
        assert value in d and "scissors" in d, \
            "must name the value and the fix"


class TestBoilerplateExpectationDerivation:
    """#906: the standing boilerplate must require a direction-1 report to state
    what its expectation is derived from.

    An expectation drawn from the same source as the thing it checks (a literal,
    an idiom, a non-distinctive line) is silent to every static tool and to
    redproof's expectation-pin; the required sentence asks the question at the
    moment it is answerable — the only instrument that reaches the #836 /
    check_watch_citations shapes. This binds the requirement with a check, the
    way this repo binds every rule a brief carries."""

    PHRASE = lint.EXPECTATION_DERIVATION_PHRASE
    REDPROOF = ("      python3 dev/redproof.py begin <path> "
                "--expectation <expectation-source>\n")

    def _check(self, t, body=None):
        (t / "SKILL.md").write_text("# skill\n", encoding="utf-8")
        bp = t / "briefs" / "boilerplate.md"
        bp.parent.mkdir(parents=True, exist_ok=True)
        if body is not None:
            bp.write_text(body, encoding="utf-8")
        rep = lint.Report()
        lint.check_boilerplate_expectation_derivation(t / ".dreamwork", rep)
        return rep

    def test_present_passes_with_coverage(self, tmp_path):
        t = fresh(tmp_path)
        (t / ".dreamwork").mkdir()
        body = ("# Standing\n- *Direction 1*: inject the defect. "
                f"**A direction-1 report states {self.PHRASE}** (a literal, "
                "an idiom).\n" + self.REDPROOF)
        assert self.PHRASE in body, "precondition: phrase present"
        rep = self._check(t, body)
        assert levels(rep, "briefs") == [lint.OK], rep.rows
        assert "#906" in rep.rows[-1][2]

    def test_absent_is_an_error_naming_the_phrase(self, tmp_path):
        t = fresh(tmp_path)
        (t / ".dreamwork").mkdir()
        body = ("# Standing\n- *Direction 1*: inject the defect.\n" +
                self.REDPROOF)
        assert self.PHRASE not in body, "precondition: phrase absent"
        rep = self._check(t, body)
        assert levels(rep, "briefs") == [lint.ERROR], rep.rows
        detail = rep.rows[-1][2]
        assert self.PHRASE in detail, "ERROR must quote the missing phrase"
        assert "#906" in detail
        assert "briefs/boilerplate.md" in detail

    def test_no_boilerplate_is_silent_not_a_vacuous_pass(self, tmp_path):
        # A foreign target carrying no standing contract is not this check's
        # subject; silence is correct, and distinct from an unexamined pass.
        t = fresh(tmp_path)
        (t / ".dreamwork").mkdir()
        rep = self._check(t, body=None)
        assert rep.rows == [], rep.rows

    def test_real_boilerplate_carries_the_phrase(self):
        # The actual standing contract the loop dispatches must bind the rule —
        # without this, the check could pass vacuously over the real file the
        # way a check that matches nothing passes forever (#655's shape).
        bp = lint.SKILL_DIR / "briefs" / "boilerplate.md"
        assert bp.is_file(), "precondition: real standing boilerplate exists"
        assert self.PHRASE in bp.read_text(encoding="utf-8"), \
            "the real briefs/boilerplate.md must carry the #906 requirement"

    def test_old_redproof_example_is_refused_by_the_real_tool(self, tmp_path):
        t = fresh(tmp_path)
        (t / ".dreamwork").mkdir()
        body = (f"A direction-1 report states {self.PHRASE}.\n"
                "      python3 dev/redproof.py begin <path>\n")
        rep = self._check(t, body)
        assert levels(rep, "briefs") == [lint.ERROR], rep.rows
        detail = rep.rows[-1][2]
        assert "must declare at least one expectation source" in detail
        assert "real tool refuses" in detail

    def test_self_referential_expectation_is_refused_by_the_real_tool(
            self, tmp_path):
        t = fresh(tmp_path)
        (t / ".dreamwork").mkdir()
        body = (f"A direction-1 report states {self.PHRASE}.\n"
                "      python3 dev/redproof.py begin <path> "
                "--expectation <path>\n")
        rep = self._check(t, body)
        assert levels(rep, "briefs") == [lint.ERROR], rep.rows
        detail = rep.rows[-1][2]
        assert "expectation source 'subject.txt' is the injected file" in detail
        assert "distinct canonical paths" in detail

    def test_missing_redproof_example_is_not_a_vacuous_pass(self, tmp_path):
        t = fresh(tmp_path)
        (t / ".dreamwork").mkdir()
        rep = self._check(t, f"A direction-1 report states {self.PHRASE}.\n")
        assert levels(rep, "briefs") == [lint.ERROR], rep.rows
        assert "no redproof begin example was found" in rep.rows[-1][2]

    def test_real_boilerplate_redproof_example_is_accepted(self):
        bp = lint.SKILL_DIR / "briefs" / "boilerplate.md"
        rep = lint.Report()
        lint.check_boilerplate_expectation_derivation(
            lint.SKILL_DIR / ".dreamwork", rep)
        assert levels(rep, "briefs") == [lint.OK], rep.rows
        assert "accepted redproof begin example" in rep.rows[-1][2]

    def test_it_is_wired_into_run_checks(self, tmp_path):
        # A check absent from the one list is a check whose tests cannot fail.
        t = fresh(tmp_path)
        (t / ".dreamwork").mkdir()
        (t / "SKILL.md").write_text("# skill\n", encoding="utf-8")
        bp = t / "briefs" / "boilerplate.md"
        bp.parent.mkdir(parents=True, exist_ok=True)
        bp.write_text("# no phrase or redproof example here\n", encoding="utf-8")
        rep = lint.Report()
        lint.run_checks(t / ".dreamwork", lint.load_watch(), rep)
        assert any(self.PHRASE in d and l == lint.ERROR
                   for l, _, d in rep.rows), rep.rows
        assert any("no redproof begin example was found" in d and l == lint.ERROR
                   for l, _, d in rep.rows), rep.rows


class TestRetiredPhrasings:
    REGISTRY = {
        "version": 1,
        "rulings": [{
            "ruling": "#505 Q2",
            "retired_phrasings": ["no-build single-file constraint"],
        }],
    }

    def _repo(self, tmp_path, docs=None, registry=None):
        root = tmp_path / "repo"
        dw = root / ".dreamwork"
        (dw / "docs").mkdir(parents=True)
        payload = self.REGISTRY if registry is None else registry
        (dw / "docs" / lint.RETIRED_PHRASINGS_REGISTRY).write_text(
            json.dumps(payload), encoding="utf-8")
        for name, content in (docs or {}).items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        return dw

    def _rows(self, dw):
        rep = lint.Report()
        lint.check_retired_phrasings(dw, rep)
        return rep.rows

    def test_live_retired_claim_warns_with_file_and_line(self, tmp_path):
        dw = self._repo(tmp_path, {
            "docs/live.md": "# Design\n\nThe no-build single-file constraint still binds.\n",
        })
        rows = self._rows(dw)
        warnings = [d for level, _, d in rows if level == lint.WARN]
        assert warnings == [
            "docs/live.md:3 repeats retired phrasing "
            "'no-build single-file constraint' from #505 Q2 without a nearby "
            "superseding marker"
        ]

    def test_struck_through_claim_is_recorded_history(self, tmp_path):
        dw = self._repo(tmp_path, {
            "docs/history.md": "~~the no-build single-file constraint~~\n",
        })
        assert self._rows(dw) == [(lint.OK, lint.RETIRED_PHRASINGS_REGISTRY,
                                  "registered 1 retired phrasing(s); scanned "
                                  "1 tracked Markdown document(s)")]

    def test_text_after_a_closed_strike_is_live(self, tmp_path):
        dw = self._repo(tmp_path, {
            "docs/live.md": (
                "~~an older, unrelated claim~~\n\n"
                "The no-build single-file constraint still binds.\n"
                "\n~~another unrelated historical claim~~\n"),
        })
        warnings = [d for level, _, d in self._rows(dw) if level == lint.WARN]
        assert len(warnings) == 1
        assert warnings[0].startswith("docs/live.md:3 repeats retired phrasing")

    def test_affirmative_ruling_quote_is_not_a_false_positive(self, tmp_path):
        dw = self._repo(tmp_path, {
            "watch-design.md": (
                "Python stdlib only. A built web UI is permitted (ruled "
                "2026-07-30, answering `#505` Q2): \"we don't have a "
                "no-build single-file constraint.\"\n"),
        })
        assert [level for level, _, _ in self._rows(dw)] == [lint.OK]

    def test_dated_supersession_in_the_window_marks_history(self, tmp_path):
        dw = self._repo(tmp_path, {
            "docs/history.md": (
                "The no-build single-file constraint was assumed.\n"
                "\nA note.\n\n**SUPERSEDED 2026-07-30** by the ruling.\n"),
        })
        assert [level for level, _, _ in self._rows(dw)] == [lint.OK]

    def test_leading_status_notice_scopes_a_historical_appendix(self, tmp_path):
        dw = self._repo(tmp_path, {
            "docs/history.md": (
                "# #505 design\n\n> **Status.** Q2 is retired.\n" +
                "\n".join(f"history {n}" for n in range(40)) +
                "\nOriginal question: hold the no-build single-file constraint?\n"),
        })
        assert [level for level, _, _ in self._rows(dw)] == [lint.OK]

    def test_multiline_phrase_names_its_start_line(self, tmp_path):
        dw = self._repo(tmp_path, {
            "docs/live.md": "# Design\n\nThe no-build single-file\nconstraint still binds.\n",
        })
        warnings = [d for level, _, d in self._rows(dw) if level == lint.WARN]
        assert len(warnings) == 1
        assert warnings[0].startswith("docs/live.md:3 repeats retired phrasing")

    def test_empty_registry_is_loud_and_prints_both_denominators(self, tmp_path):
        dw = self._repo(tmp_path, {"docs/one.md": "# one\n"},
                        registry={"version": 1, "rulings": []})
        rows = self._rows(dw)
        assert rows == [(lint.WARN, lint.RETIRED_PHRASINGS_REGISTRY,
                         "registered 0 retired phrasing(s); scanned 1 tracked "
                         "Markdown document(s) — registry is empty; this is "
                         "not an all-clear")]

    def test_absent_registry_is_a_loud_warning_not_an_error(self, tmp_path):
        dw = self._repo(tmp_path, {"docs/one.md": "# one\n"})
        (dw / "docs" / lint.RETIRED_PHRASINGS_REGISTRY).unlink()
        rows = self._rows(dw)
        assert rows == [(lint.WARN, lint.RETIRED_PHRASINGS_REGISTRY,
                         "registered 0 retired phrasing(s); scanned 1 tracked "
                         "Markdown document(s) — registry is empty; this is "
                         "not an all-clear")]

    def test_empty_tracked_doc_set_is_loud(self, tmp_path):
        dw = self._repo(tmp_path)
        rows = self._rows(dw)
        assert rows == [(lint.WARN, lint.RETIRED_PHRASINGS_REGISTRY,
                         "registered 1 retired phrasing(s); scanned 0 tracked "
                         "Markdown document(s) — document set is empty; this "
                         "is not an all-clear")]

    def test_only_git_tracked_markdown_is_scanned(self, tmp_path):
        dw = self._repo(tmp_path, {"docs/tracked.md": "# tracked\n"})
        untracked = dw.parent / "docs" / "untracked.md"
        untracked.write_text("the no-build single-file constraint binds\n",
                             encoding="utf-8")
        rows = self._rows(dw)
        assert rows == [(lint.OK, lint.RETIRED_PHRASINGS_REGISTRY,
                         "registered 1 retired phrasing(s); scanned 1 tracked "
                         "Markdown document(s)")]

    def test_malformed_registry_fails_loudly_and_keeps_denominators(self,
                                                                    tmp_path):
        dw = self._repo(tmp_path, {"docs/one.md": "# one\n"})
        registry = dw / "docs" / lint.RETIRED_PHRASINGS_REGISTRY
        registry.write_text("{", encoding="utf-8")
        rows = self._rows(dw)
        assert [level for level, _, _ in rows] == [lint.ERROR, lint.WARN]
        assert "cannot parse" in rows[0][2]
        assert rows[1][2].startswith(
            "registered 0 retired phrasing(s); scanned 1 tracked Markdown")
