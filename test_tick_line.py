"""Tests for tick_line.py — the per-tick posture/fleet decorator (#673).

THE TRAP THESE ARE WRITTEN AGAINST. The obvious test for this feature asserts
that the output "contains the posture" — and passes against an implementation
that hardcodes a plausible posture string, because the fixture's posture and
the hardcoded one look alike. Every assertion here that matters is therefore
DIFFERENTIAL: it writes one state, reads the line, writes a *different* state,
and requires the line to have changed. A constant cannot survive that, however
well-chosen the constant.

The fixtures use axis values that are legal but not the defaults (`asking:
auto`, `delivery: instant`) for the same reason: a line built from
`derive_posture`'s fallbacks rather than from the file would match a
default-valued fixture and prove nothing.
"""

import json
import selectors
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import status_sync
import tick_line
import lane_liveness

PULSE = "[10:15] dream tick (ud-dreamwork): run the tick flow"


def make_target(tmp_path, *, posture, open_ids=(1, 2, 3), dreamers=None,
                policy=None, run_mode="hot", lanes=()):
    """A minimal target dir: run-mode, posture, status.json, tasks.md."""
    (tmp_path.parent / ".worktrees").mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    dw = tmp_path / ".dreamwork"
    dw.mkdir(parents=True, exist_ok=True)
    (dw / "run-mode").write_text(run_mode + "\n")
    (dw / "posture").write_text(posture)
    (dw / "status.json").write_text(json.dumps(
        {"dreamers": [] if dreamers is None else dreamers,
         "lanes": list(lanes)}))
    body = "\n".join("- **#%d** — a task · P2" % i for i in open_ids)
    (dw / "tasks.md").write_text("# Tasks\n\n## Open\n\n%s\n" % body)
    if policy is not None:
        (dw / "subagent-policy").write_text(policy)
    return str(tmp_path)


def _add_goal_store(target, title, *, completed=0, total=0, current=True,
                    description=""):
    """Add a v008 goal store under an existing make_target dir.

    Creates one goal, sets it open, and seeds progress() directly: ``total``
    member tasks live in the STORE (progress joins the store's task table, not
    tasks.md), ``completed`` of them landed. ``current=False`` leaves the
    current-goal pointer empty. Returns the goal id.
    """
    from dreamwork_db import Access, open_database
    from dreamwork_db.store import dreamwork_store_spec
    dw = Path(target) / ".dreamwork"
    db = dw / "ledger.sqlite3"
    with open_database(dreamwork_store_spec(db), access=Access.WRITE) as store:
        with store.transaction() as tx:
            goal_id = tx.groups.create(
                kind="goal", title=title, description=description, actor="test",
                at="2026-08-01T00:00:00Z")
            tx.goals.set_state(goal_id, "open")
            for i in range(total):
                tid = tx.tasks.file(
                    "member task %d" % i, "body %d" % i, actor="test",
                    at="2026-08-01T00:00:01Z")
                tx.groups.add_task(
                    goal_id, tid, actor="test", at="2026-08-01T00:00:02Z")
                if i < completed:
                    tx.tasks.land(tid, actor="test", at="2026-08-01T00:00:03Z")
            if current:
                tx.goals.set_current_goal_id(goal_id)
    return goal_id


HOT = textwrap.dedent("""\
    pace: hot
    asking: near-auto
    delegation: 5
    delivery: batched
    orchestration: orchestrator
    """)

COLD = textwrap.dedent("""\
    pace: idle
    asking: auto
    delegation: 1
    delivery: instant
    orchestration: hands-on
    """)


class TestTracksTheFile:
    """The differential core: every axis must MOVE when the file moves.

    A hardcoded line, a stale cached line, or a line built from run-mode
    derivation instead of the posture file all pass a "contains a posture"
    assertion and fail every test in this class.
    """

    @pytest.mark.parametrize("axis,hot_text,cold_text", [
        ("pace", "pace hot", "pace idle"),
        ("asking", "asking near-auto", "asking auto"),
        ("delegation", "delegation 5", "delegation 1"),
        ("delivery", "delivery batched", "delivery instant"),
        ("orchestration", "orchestration orchestrator",
         "orchestration hands-on"),
    ])
    def test_axis_follows_the_posture_file(self, tmp_path, axis, hot_text,
                                           cold_text):
        hot = tick_line.facts(make_target(tmp_path / "a", posture=HOT))
        cold = tick_line.facts(make_target(tmp_path / "b", posture=COLD))
        assert hot_text in hot, axis
        assert cold_text in cold, axis
        # And not merely present in both — the point is that it CHANGED.
        assert hot_text not in cold, axis
        assert cold_text not in hot, axis

    def test_posture_is_reread_within_one_target_not_cached(self, tmp_path):
        """CONSTRUCTED FALSE GREEN, and the reason this test exists.

        Every other test here uses a fresh target directory, so an
        implementation that memoises `resolve_posture` PER TARGET passes all 36
        of them — measured, not supposed. It is also plausible ("three file
        reads a tick") and completely broken in production: he changes the
        posture from the dashboard mid-session, and a cached line would go on
        reporting the old axes until the monitor is re-armed. That is the exact
        failure #673 exists to prevent, dressed as an optimisation.

        Only rewriting the file UNDER AN ALREADY-READ TARGET can catch it.
        """
        target = make_target(tmp_path, posture=HOT)
        assert "delegation 5" in tick_line.facts(target)
        (Path(target) / ".dreamwork" / "posture").write_text(COLD)
        after = tick_line.facts(target)
        assert "delegation 1" in after
        assert "orchestration hands-on" in after

    def test_open_count_follows_the_ledger(self, tmp_path):
        few = tick_line.facts(
            make_target(tmp_path / "a", posture=HOT, open_ids=(1, 2)))
        many = tick_line.facts(
            make_target(tmp_path / "b", posture=HOT, open_ids=range(1, 40)))
        assert "2 open" in few
        assert "39 open" in many


    def test_live_counts_follow_the_process_table(self, tmp_path,
                                                  monkeypatch):
        target = make_target(tmp_path, posture=HOT)

        def two_live(_target):
            return lane_liveness.LaneInspection(
                ('cx-one', 'cx-two'), (), (), 37)

        monkeypatch.setattr(lane_liveness, "inspect_lanes", two_live)
        out = tick_line.facts(target)
        assert "lanes 2 live [cx-one, cx-two]" in out, \
            "live lanes cx-one/cx-two were omitted from the tick line: %s" % out
        assert "probe examined 37 processes" in out

    def test_dead_processes_do_not_inherit_the_recorded_lane_count(
            self, tmp_path, monkeypatch):
        target = make_target(
            tmp_path, posture=HOT,
            lanes=[{"lane": "one", "model": "ccc"},
                   {"lane": "two", "model": "agent-tool"}],
            dreamers=[{"task": 1, "pid": 111},
                      {"task": 1, "pid": 222,
                       "dispatch": "agent_tool"}])
        def none_live(_target):
            return lane_liveness.LaneInspection((), (), (), 41)

        monkeypatch.setattr(lane_liveness, "inspect_lanes", none_live)
        out = tick_line.facts(target)
        assert "lanes 0 live []" in out
        assert "recorded" not in out, \
            "stale status.json lanes were still reported as live posture"

    def test_recorded_count_follows_the_authored_lanes_field(self, tmp_path):
        target = make_target(
            tmp_path, posture=HOT,
            lanes=[{"lane": "stale-%d" % i} for i in range(6)])
        out = tick_line.facts(target)
        assert "recorded" not in out
        assert "stale-" not in out


class TestWorktreeSizeDirection:
    """Growth is loud; shrinkage and an expected nonzero floor are calm."""

    @staticmethod
    def _target(tmp_path):
        target = Path(make_target(tmp_path / "repo", posture=HOT))
        root = tmp_path / ".worktrees"
        return target, root

    def test_growth_flags_regression_and_shrink_does_not(self, tmp_path):
        grow_target, grow_root = self._target(tmp_path / "grow")
        payload = grow_root / "payload"
        payload.write_bytes(b"a" * 4096)
        before = tick_line._worktrees_size_fact(str(grow_target))
        payload.write_bytes(b"b" * (1024 * 1024))
        growth = tick_line._worktrees_size_fact(str(grow_target))

        shrink_target, shrink_root = self._target(tmp_path / "shrink")
        payload = shrink_root / "payload"
        payload.write_bytes(b"c" * (1024 * 1024))
        tick_line._worktrees_size_fact(str(shrink_target))
        payload.write_bytes(b"d" * 4096)
        shrink = tick_line._worktrees_size_fact(str(shrink_target))

        assert "REGRESSION" not in before
        assert "WORKTREE-SIZE-REGRESSION +" in growth
        assert "REGRESSION" not in shrink
        assert "new durable low-water" in shrink

    def test_unreadable_root_is_unmeasured_not_zero(self, tmp_path,
                                                    monkeypatch):
        target, _root = self._target(tmp_path)

        def unreadable(_root):
            raise PermissionError("fixture root is unreadable")

        monkeypatch.setattr(tick_line, "_allocated_worktree_bytes", unreadable)
        out = tick_line.facts(str(target))
        assert "WORKTREES UNRESOLVED (PermissionError: " \
               "fixture root is unreadable)" in out
        assert "worktrees 0" not in out

    def test_growth_stays_a_regression_after_process_restart(self, tmp_path):
        """A process-local previous reading is a false green this closes."""
        target, root = self._target(tmp_path)
        payload = root / "payload"
        payload.write_bytes(b"a" * 4096)
        probe = (
            "import sys, tick_line; "
            "print(tick_line._worktrees_size_fact(sys.argv[1]))")
        first = subprocess.run(
            [sys.executable, "-c", probe, str(target)], check=True,
            capture_output=True, text=True).stdout
        payload.write_bytes(b"b" * (1024 * 1024))
        after_restart = subprocess.run(
            [sys.executable, "-c", probe, str(target)], check=True,
            capture_output=True, text=True).stdout
        assert "REGRESSION" not in first
        assert "WORKTREE-SIZE-REGRESSION +" in after_restart


class TestNoUnqualifiedFleetSize:
    """The count the loop cannot measure must never be asserted.

    Every number names how it was obtained, and the bare phrasing that would
    imply an unqualified total is forbidden outright.
    """

    def test_agent_tool_fleet_does_not_render_as_an_empty_fleet(self,
                                                               tmp_path):
        """Recorded lanes alone do not imply an observable live lane."""
        out = tick_line.facts(make_target(
            tmp_path, posture=HOT,
            lanes=[{"lane": "lane-%d" % i, "model": "opus"}
                   for i in range(6)]))
        assert "lanes 0 live []" in out
        assert "lanes 6" not in out
        assert "recorded" not in out


class TestLiveFleetDetector:
    """The tick names live worktree lanes, never cached bookkeeping."""

    def test_agent_tool_and_ccc_names_share_one_live_fleet(
            self, tmp_path, monkeypatch):
        target = make_target(tmp_path, posture=HOT)

        def mixed(_target):
            return lane_liveness.LaneInspection(
                ('cx-agent', 'cx-ccc'), (), (), 52)

        monkeypatch.setattr(lane_liveness, "inspect_lanes", mixed)
        out = tick_line.facts(target)
        assert "lanes 2 live [cx-agent, cx-ccc]" in out
        assert "runners ?" not in out

    def test_one_lane_in_both_buckets_is_counted_once_not_twice(
            self, tmp_path, monkeypatch):
        """#837: a ccc lane runs a wrapper process AND an inner agent process,
        both with the worktree cwd, so discover_lanes legitimately lists the
        SAME lane name in the `ccc` and `agent` buckets. That is the normal
        live case. _fleet_fact must dedupe across the two buckets: a lane is
        one lane however many processes carry its cwd.

        This is the case NO earlier test constructed. Every other live-fleet
        test puts a DISTINCT name in each bucket, where a plain concatenation
        and a dedupe agree and the double-count bug is invisible. With a lane
        in both, the broken concatenation renders the name twice and inflates
        the count.

        The assertion binds the NAME SET and the count in ONE substring: a
        count comparison alone passes when membership changed but length did
        not, and a membership check alone cannot name the doubled lane. The
        doubled rendering (`cx-dup, cx-dup`) is what makes this discriminating.
        """
        target = make_target(tmp_path, posture=HOT)

        def overlap(_target):
            return lane_liveness.LaneInspection(
                ('cx-dup', 'cx-only-agent', 'cx-only-ccc'), (), (), 9)

        monkeypatch.setattr(lane_liveness, "inspect_lanes", overlap)
        out = tick_line.facts(target)
        assert "lanes 3 live [cx-dup, cx-only-agent, cx-only-ccc]" in out, \
            "a lane present in both the ccc and agent buckets was not " \
            "deduped (double-counted): %s" % out

    def test_zero_candidates_is_instrument_failure_not_empty_fleet(
            self, tmp_path, monkeypatch):
        target = make_target(tmp_path, posture=HOT)

        def inert(_target):
            raise lane_liveness.LivenessUnknown(
                "lane detector examined 0 process candidates")

        monkeypatch.setattr(lane_liveness, "inspect_lanes", inert)
        out = tick_line.facts(target)
        assert "FLEET UNRESOLVED" in out, \
            "detector examined zero candidates but tick reported an empty " \
            "live fleet: %s" % out
        assert "examined 0 process candidates" in out
        assert "lanes 0 live" not in out, \
            "broken detector was indistinguishable from no live lanes"

    def test_right_count_over_wrong_set_is_rejected(self, tmp_path, monkeypatch):
        """#886: six-vs-six is hollow; bind every expected lane name."""
        target = make_target(tmp_path, posture=HOT)
        expected = ('cx-584settings', 'cx-862reconcile', 'cx-867briefgit',
                    'cx-876survive', 'cx-883lintzero', 'cx-884nextup')
        wrong = expected[:-1] + ('review',)
        assert len(wrong) == len(expected) == 6, \
            "precondition: count-only comparison must pass the incident shape"
        monkeypatch.setattr(
            lane_liveness, "inspect_lanes",
            lambda _target: lane_liveness.LaneInspection(expected, (), (), 1188))
        tick = tick_line.facts(target)
        exact = "lanes 6 live [%s]" % ", ".join(expected)
        assert exact in tick, \
            "right count concealed a wrong lane set: expected %r, tick=%s" \
            % (expected, tick)
        assert "review" not in tick

    def test_inspection_names_worktree_only_and_process_only(
            self, tmp_path, monkeypatch):
        """Every classified mismatch is visible, never silently conflated."""
        target = Path(make_target(tmp_path / "project", posture=HOT))
        settled = tmp_path / ".worktrees" / "cx-settled"
        settled.mkdir(parents=True)
        finished = tmp_path / ".worktrees" / "cx-finished"
        (finished / ".dreamwork").mkdir(parents=True)
        identity = finished / "brief.md"
        (finished / ".dreamwork" / "lane.lock").write_text(json.dumps({
            "pid": 4242, "task": 999, "lane": "cx-finished",
            "identity": str(identity),
        }))
        removed = tmp_path / ".worktrees" / "cx-removed"
        raw = ("ccc\x00# Task #999 -- fixture\nWorktree: %s\n" % removed).encode()
        monkeypatch.setattr(
            lane_liveness, "pid_matches_lane", lambda *_args: False)
        inspection = lane_liveness.inspect_lanes(
            target, process_entries=["999"],
            registered_worktrees=(settled, finished),
            read_cmdline=lambda _pid: raw)
        assert inspection.live == ()
        assert inspection.worktree_only == ('cx-settled',), \
            "lockless settled worktree landed in the wrong bucket: %r" % \
            (inspection,)
        assert inspection.finished == (lane_liveness.FinishedLane(
            lane="cx-finished", task=999, pid=4242,
            identity=str(identity)),), \
            "cx-finished task #999 landed in the wrong bucket: %r" % \
            (inspection,)
        assert inspection.process_only == ('cx-removed',), \
            "process whose worktree was removed was not named"
        monkeypatch.setattr(lane_liveness, "inspect_lanes", lambda _target: inspection)
        out = tick_line.facts(str(target))
        assert "worktree-only 1 [cx-settled]" in out
        assert "finished 1 [#999 cx-finished]" in out
        assert "process-only 1 [cx-removed]" in out

    def test_incidental_review_path_cannot_become_lane_identity(self, tmp_path):
        root = (tmp_path / ".worktrees").resolve()
        actual = root / "cx-884nextup"
        raw = (
            "ccc\x00# Task #884\n"
            f"Compare {root / 'review'} before finishing.\n"
            f"Worktree: {actual}\n"
        ).encode()
        found = lane_liveness._prompt_worktree(raw, (root,))
        assert found == actual, \
            "incidental path invented lane 'review' and omitted cx-884nextup: %r" % found


class TestCwdLiveLanesReported:
    """#1084: a hand-dispatched lane has no lane.lock but a live runner in its
    worktree cwd. The tick line must count it in the headline AND name the
    disagreement with the lock channel, not silently resolve it (#136)."""

    def test_cwd_only_lane_counted_in_headline_and_disagreement_named(
            self, tmp_path, monkeypatch):
        target = make_target(tmp_path, posture=HOT)

        def inspection(_target):
            return lane_liveness.LaneInspection(
                live=('cx-lock',), worktree_only=(), process_only=(),
                examined_processes=99, cwd_live=('glm-hand',))

        monkeypatch.setattr(lane_liveness, "inspect_lanes", inspection)
        out = tick_line.facts(target)
        assert "lanes 2 live [cx-lock, glm-hand]" in out, \
            "cwd-only lane not counted in headline: %s" % out
        assert "cwd-only 1 [glm-hand]" in out
        assert "live runner, no live lane.lock" in out

    def test_cwd_only_lane_named_not_just_counted(self, tmp_path, monkeypatch):
        """Direction-2 anchor: a count-only check passes when the lane is
        silently dropped. Bind the NAME of the missed lane."""
        target = make_target(tmp_path, posture=HOT)

        def inspection(_target):
            return lane_liveness.LaneInspection(
                live=(), worktree_only=(), process_only=(),
                examined_processes=99, cwd_live=('glm-1034clean',))

        monkeypatch.setattr(lane_liveness, "inspect_lanes", inspection)
        out = tick_line.facts(target)
        assert "lanes 1 live [glm-1034clean]" in out, \
            "cwd-only lane glm-1034clean was not named in the headline: %s" % out
        assert "cwd-only 1 [glm-1034clean]" in out, \
            "the missed lane was not named in the disagreement clause: %s" % out

    def test_no_cwd_live_means_no_disagreement_clause(self, tmp_path,
                                                      monkeypatch):
        """When lock and cwd agree, no cwd-only clause clutters the line."""
        target = make_target(tmp_path, posture=HOT)

        def inspection(_target):
            return lane_liveness.LaneInspection(
                live=('cx-lock',), worktree_only=(), process_only=(),
                examined_processes=99)

        monkeypatch.setattr(lane_liveness, "inspect_lanes", inspection)
        out = tick_line.facts(target)
        assert "lanes 1 live [cx-lock]" in out
        assert "cwd-only" not in out


class TestTheContradictionIsAdjacent:
    """#673's whole mechanism: the rule and the measurement that fails it, on
    the same line, close enough to read as one statement."""

    def test_counts_immediately_precede_the_delegation_target(self, tmp_path):
        out = tick_line.facts(make_target(tmp_path, posture=HOT))
        assert "live [] (probe examined " in out
        assert " processes) · delegation 5" in out


class TestUnprobeableLanesDoNotBreakTheProbe:
    """#537: a `spawn_subagent` entry in `dreamers` has no probe-able process,
    so it must be carried past the liveness step rather than asked about."""

    def test_spawn_subagent_entry_does_not_raise_or_inflate_live_counts(
            self, tmp_path):
        out = tick_line.facts(make_target(
            tmp_path, posture=HOT,
            dreamers=[{"task": 1, "pid": 111, "dispatch": "spawn_subagent"}]))
        assert "lanes 0 live []" in out


class TestFailsClosed:
    """A fact that cannot be measured is stated as missing, loudly, in the
    place it would have occupied — never omitted, never defaulted (#655)."""

    def test_undecodable_posture_taints_the_number_it_would_corrupt(self,
                                                                    tmp_path):
        """MEASURED, and the reason `_posture_file_ignored` exists at all.

        `watch.resolve_posture` cannot decode these bytes, silently treats the
        file as absent, and derives `delegation 0` from run-mode — the exact
        value that tells a coordinator its empty fleet is correct. The derived
        axes are genuinely in effect and are still shown; what must not survive
        is `delegation 0` reading as a setting somebody chose.
        """
        target = make_target(tmp_path, posture=HOT)
        (Path(target) / ".dreamwork" / "posture").write_bytes(b"\xff\xfe\x00")
        out = tick_line.facts(target)
        assert "POSTURE FILE IGNORED" in out
        assert "delegation 0 (POSTURE FILE IGNORED" in out
        # Never the bare form a healthy file produces.
        assert "delegation 0 · " not in out

    def test_posture_file_of_only_comments_is_named_too(self, tmp_path):
        """It holds something and sets nothing — lint calls this inert and says
        a file that looks set and is not must not pass in silence."""
        target = make_target(tmp_path, posture="# TODO: decide\n")
        assert "POSTURE FILE IGNORED: present, set no axis" in tick_line.facts(
            target)

    def test_absent_posture_file_is_provenance_not_an_error(self, tmp_path):
        """Deriving from run-mode is documented, intended behaviour here."""
        target = make_target(tmp_path, posture=HOT)
        (Path(target) / ".dreamwork" / "posture").unlink()
        out = tick_line.facts(target)
        assert "delegation 0 (derived from run-mode)" in out
        assert "IGNORED" not in out

    def test_one_failure_does_not_hide_the_other_facts(self, tmp_path):
        """The fleet count is the number that would have said 'dispatch'. An
        unreadable posture file must not cost the reader that number."""
        target = make_target(tmp_path, posture=HOT, open_ids=(1, 2, 3))
        (Path(target) / ".dreamwork" / "posture").write_bytes(b"\xff\xfe\x00")
        out = tick_line.facts(target)
        assert "lanes 0 live []" in out
        assert "3 open" in out

    def test_liveness_unknown_is_not_rendered_as_zero(self, tmp_path,
                                                      monkeypatch):
        """'I could not tell' and 'nothing is running' must not be one string
        when one of them is the alarm (status_sync's own words)."""
        target = make_target(tmp_path, posture=HOT,
                             dreamers=[{"task": 1, "pid": 111}])

        def boom(_target, *, stats=None):
            raise status_sync.LivenessUnknown("probe broken")

        monkeypatch.setattr(lane_liveness, "inspect_lanes", boom)
        out = tick_line.facts(target)
        assert "FLEET UNRESOLVED" in out
        assert "lanes live" not in out

    def test_unreadable_ledger_is_not_rendered_as_zero_open(self, tmp_path):
        target = make_target(tmp_path, posture=HOT)
        (Path(target) / ".dreamwork" / "tasks.md").write_text("# Tasks\n")
        out = tick_line.facts(target)
        assert "OPEN UNKNOWN" in out
        assert "0 open" not in out

    def test_missing_dreamwork_dir_degrades_every_fact_and_still_returns(
            self, tmp_path):
        out = tick_line.facts(str(tmp_path / "nope"))
        assert "FLEET UNRESOLVED" in out
        assert "OPEN UNRESOLVED" in out
        assert out.strip()

    def test_facts_never_raise_for_any_broken_target(self, tmp_path):
        """The pulse is the loop's only wake channel; no input may cost it."""
        for junk in (b"", b"\x00\x00", b"delegation: not-a-number\n"):
            d = tmp_path / ("t%d" % len(junk))
            target = make_target(d, posture=HOT)
            (Path(target) / ".dreamwork" / "posture").write_bytes(junk)
            assert tick_line.facts(target).strip()


class TestNeverSilentlyFallsBackToTheStaticLine:
    """The #655 shape stated directly: whatever happens, the decorated line
    must differ from the bare pulse, and must not look like a normal line."""

    def test_a_totally_broken_target_still_changes_the_pulse(self, tmp_path):
        out = tick_line.decorate(PULSE, str(tmp_path / "gone"))
        assert out != PULSE
        assert out.startswith(PULSE)
        assert "UNRESOLVED" in out

    def test_no_degraded_line_can_be_mistaken_for_a_healthy_one(self,
                                                               tmp_path):
        healthy = tick_line.decorate(PULSE, make_target(tmp_path, posture=HOT))
        broken = tick_line.decorate(PULSE, str(tmp_path / "gone"))
        assert "UNRESOLVED" not in healthy
        assert "UNRESOLVED" in broken


class TestThePulsePassesThroughIntact:
    """This program knows nothing about heartbeat's output grammar, and these
    pin that: prefixes, countdowns and the startup banner are opaque."""

    @pytest.mark.parametrize("pulse", [
        "[10:15] dream tick",
        "[10:15] [2/2] dream tick",
        "2024-06-15 10:15:30.123 dream tick",
        'heartbeat is set up to repeat "dream tick" every 4.75 minutes',
        "",
    ])
    def test_pulse_is_a_verbatim_prefix_of_the_output(self, tmp_path, pulse):
        out = tick_line.decorate(pulse, make_target(tmp_path, posture=HOT))
        assert out.startswith(pulse + " · ")

    def test_output_is_exactly_one_line(self, tmp_path):
        """A tick that spans lines would break every reader that greps ticks,
        and the facts come from files a human edits by hand."""
        target = make_target(tmp_path, posture=HOT,
                             policy="a\nb\nc\nd\ne\nf\ng\n")
        assert "\n" not in tick_line.decorate(PULSE, target)


class TestPolicyIsSizedNotQuoted:
    """#612 on volume: the tiers are a dispatch-time lookup, so the tick names
    the policy's size and provenance instead of reprinting ~700 chars forever."""

    def test_counts_lines_and_names_the_source(self, tmp_path):
        target = make_target(tmp_path, posture=HOT,
                             policy="- tier one\n- tier two\n")
        out = tick_line.facts(target)
        assert "subagent-policy 2 lines (file)" in out
        assert "tier one" not in out

    def test_absent_policy_reports_the_standing_default(self, tmp_path):
        out = tick_line.facts(make_target(tmp_path, posture=HOT))
        assert "subagent-policy 4 lines (default)" in out

    def test_blank_lines_do_not_inflate_the_count(self, tmp_path):
        target = make_target(tmp_path, posture=HOT,
                             policy="- one\n\n\n- two\n\n")
        assert "subagent-policy 2 lines (file)" in tick_line.facts(target)


def _readline_within(stream, seconds: float) -> str:
    """One line, or a FAILURE — never an unbounded wait.

    A test that hangs is not a red: it reports nothing, and under `-q` it is
    indistinguishable from a slow suite until someone kills it. The defect this
    guards (a missing `flush`) fails exactly that way, so the wait is bounded
    here and turned into a message that names the cause.
    """
    with selectors.DefaultSelector() as sel:
        sel.register(stream, selectors.EVENT_READ)
        if not sel.select(seconds):
            raise AssertionError(
                "no line within %.1fs — the decorated pulse is sitting in a "
                "block buffer; stdout to a pipe needs an explicit flush"
                % seconds)
    return stream.readline()


class TestStreaming:
    """The pipeline's delivery contract, measured by running the real process.

    stdout to a pipe is BLOCK-buffered. Without an explicit flush the loop's
    only wake channel goes silent until ~8KB has accumulated — dozens of ticks,
    hours — and then arrives all at once. No unit test of `decorate()` can see
    that; only a process on the far side of a pipe can.
    """

    def test_one_pulse_in_one_line_out_before_the_next(self, tmp_path):
        target = make_target(tmp_path, posture=HOT)
        proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).parent / "tick_line.py"),
             "--target", target],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            cwd=str(Path(__file__).parent))
        try:
            proc.stdin.write(PULSE + "\n")
            proc.stdin.flush()
            # No second pulse is written: the line must arrive on its own.
            line = _readline_within(proc.stdout, 10)
            assert line.startswith(PULSE + " · ")
            assert "delegation 5" in line
        finally:
            proc.stdin.close()
            proc.wait(timeout=10)
        assert proc.returncode == 0

    def test_closed_stdin_exits_zero(self, tmp_path):
        proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).parent / "tick_line.py"),
             "--target", make_target(tmp_path, posture=HOT)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True,
            cwd=str(Path(__file__).parent))
        assert proc.wait(timeout=10) == 0


# The src stamp. Anything matching "src " followed by 8 hex chars at line end.
import re as _re
_STAMP = _re.compile(r"src [0-9a-f]{8}")


class TestSourceStampIsHonest:
    """#840 option 3: the line names the code that produced it.

    The single most important property — the trap the brief names outright —
    is that the stamp reflects the code RESIDENT in the running process, NOT
    a fresh re-read from disk at print time. A stamp that re-read would print
    the NEW sha while running OLD code: the exact inversion of the bug, and a
    worse lie than no stamp.
    """

    def test_line_carries_a_stamp(self, tmp_path):
        out = tick_line.facts(make_target(tmp_path, posture=HOT))
        assert _STAMP.search(out), "no src stamp on the tick line: %s" % out

    def test_stamp_is_bound_at_import_not_reread_at_print(self, monkeypatch):
        """THE TRAP. If RESIDENT_SHA were recomputed inside facts() (a disk
        re-read at print time), editing tick_line.py's source on disk would
        flip the stamp while the resident code stayed old — the inversion.

        This monkeypatches a _resident_sources_sha RECOMPUTE over a *different*
        byte set than the one bound at import, then asserts facts() still
        reports the IMPORT-time value. It binds the module attribute directly,
        which is the production symbol a re-read would overwrite; a recompute
        living inside facts() would re-read disk and disagree.
        """
        original = tick_line.RESIDENT_SHA
        assert _re.fullmatch(r"[0-9a-f]{8}", original)
        # Simulate disk having moved on under a resident process: the import
        # value is frozen, and a later re-read would disagree.
        monkeypatch.setattr(tick_line, "RESIDENT_SHA", "deadbeef")
        out = tick_line.facts(".")
        assert "src deadbeef" in out, (
            "stamp did not report the resident (import-bound) value; a disk "
            "re-read at print time would invert the bug: %s" % out)

    def test_stamp_covers_the_whole_local_closure_not_just_tick_line(
            self, tmp_path, monkeypatch):
        """The partial-stamp trap (#821 shape one level up). _fleet_fact calls
        into status_sync, so a stamp of ONLY tick_line would read 'unchanged'
        while a status_sync edit moved the output. This proves the hash walks
        every local module's bytes via sys.modules, not a hard-coded list.

        Differential: recompute the hash twice with status_sync's __file__
        pointing at two DIFFERENT temp files (both admitted by the local-path
        filter), and require the stamp to MOVE. A tick_line-only hash is blind
        to status_sync's __file__ and would return identical stamps."""
        import os
        here = os.path.dirname(os.path.abspath(tick_line.__file__))
        # Precondition: status_sync IS a local module the stamp reads.
        assert os.path.isfile(os.path.join(here, "status_sync.py"))
        a = os.path.join(here, "_840_probe_a.py")
        b = os.path.join(here, "_840_probe_b.py")
        try:
            with open(a, "wb") as f:
                f.write(b"# probe a\n")
            with open(b, "wb") as f:
                f.write(b"# probe b - DIFFERENT bytes\n")
            monkeypatch.setattr(status_sync, "__file__", a, raising=False)
            stamp_a = tick_line._resident_sources_sha()
            monkeypatch.setattr(status_sync, "__file__", b, raising=False)
            stamp_b = tick_line._resident_sources_sha()
        finally:
            for p in (a, b):
                if os.path.exists(p):
                    os.remove(p)
        assert stamp_a != stamp_b, (
            "stamp did not move when status_sync's source bytes changed; a "
            "tick_line-only stamp would read 'current' through the #821 edit")


class TestStaleFilterServesFreshCode:
    """#840 option 2: the long-lived parent spawns a fresh child per pulse, so
    an edit to tick_line.py (or any module it imports) takes effect on the VERY
    NEXT tick — no re-arm, no mtime watch, no source list to forget.

    This is the end-to-end fix for the observed bug: #821 served 20h08m of
    pre-merge code, #837 kept doubling lanes after the dedupe landed, both
    'fixed' by stopping and re-arming the monitor. A per-tick child has no
    resident set to go stale.
    """

    SENTINEL = "SENTINEL_840_TEST"
    # A unique, exactly-once substring of the facts() return to inject after.
    # The anchor is the list close (`_stamp_fact()])`): #889 moved a goal fact
    # in ahead of the stamp, so the stamp call is no longer the list's first
    # element. The contract this guard binds (an edit reaches the next pulse)
    # is unchanged; only the injection point moved with it.
    NEEDLE = "_stamp_fact()])"
    REPLACEMENT = "_stamp_fact(), \"%s\"])" % SENTINEL

    def test_edit_to_tick_line_appears_on_the_next_pulse(self, tmp_path):
        """Direction-1 red-proof, as a permanent guard. Holds ONE process across
        an edit (the precondition the brief flags: a test that restarts the
        process between edit and assertion tests nothing). Pulse 1 runs the
        original; edit tick_line.py under the process; pulse 2 MUST carry the
        sentinel. The baseline (pre-fix streaming filter) served the old code
        indefinitely here."""
        src = Path(tick_line.__file__)
        backup = src.read_bytes()
        assert src.read_text().count(self.NEEDLE) == 1, "precondition: needle unique"
        target = make_target(tmp_path, posture=HOT)
        try:
            proc = subprocess.Popen(
                [sys.executable, str(src), "--target", target],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                cwd=str(src.parent))
            try:
                proc.stdin.write(PULSE + " a\n")
                proc.stdin.flush()
                line1 = _readline_within(proc.stdout, 10)
                assert self.SENTINEL not in line1  # precondition: absent before

                edited = src.read_text().replace(self.NEEDLE, self.REPLACEMENT)
                assert edited.count(self.SENTINEL) == 1
                src.write_text(edited)

                proc.stdin.write(PULSE + " b\n")
                proc.stdin.flush()
                line2 = _readline_within(proc.stdout, 15)
                assert self.SENTINEL in line2, (
                    "edit to tick_line.py did not appear on the next pulse; "
                    "the streaming filter served stale resident code: %s"
                    % line2)
            finally:
                proc.stdin.close()
                proc.wait(timeout=10)
        finally:
            src.write_bytes(backup)
            assert src.read_bytes() == backup

    def test_two_fresh_children_report_the_same_stamp(self, tmp_path):
        """The stamp is a deterministic function of the resident closure, so
        two fresh children over the same disk bytes agree. (A direct call
        from WITHIN pytest would disagree, because pytest makes the test
        module resident too — that is honest, not a bug, but it is why this
        test compares two subprocess children rather than a child to the
        in-process value.)"""
        target = make_target(tmp_path, posture=HOT)
        exe = str(Path(tick_line.__file__).parent / "tick_line.py")

        def child_stamp():
            proc = subprocess.Popen(
                [sys.executable, exe, "--target", target],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                cwd=str(Path(tick_line.__file__).parent))
            try:
                proc.stdin.write(PULSE + "\n")
                proc.stdin.flush()
                return _readline_within(proc.stdout, 10)
            finally:
                proc.stdin.close()
                proc.wait(timeout=10)

        line1 = child_stamp()
        line2 = child_stamp()
        m1, m2 = _STAMP.search(line1), _STAMP.search(line2)
        assert m1 and m2
        assert m1.group(0) == m2.group(0), (
            "two fresh children over the same disk disagreed on the stamp; "
            "the stamp must be a deterministic function of the closure: "
            "%s vs %s" % (m1.group(0), m2.group(0)))


class TestGoalHandleOnTheTickLine:
    """#889 (#862 increment 2): the current goal as a handle, in the trailing
    slot before the src stamp.

    The goal title WILL be long (he writes acceptance criteria into it), and
    #612 is the failure being designed around: a long field pushing the fleet
    count off the read. So the elision to a hard 48 is the feature, and the
    binding assertion is the fleet count staying readable AT the longest title
    the elision permits — not at a convenient short one.
    """

    def test_handle_carries_prefix_elided_title_and_progress(self, tmp_path):
        title = "modular watch.py, React front end"
        target = make_target(tmp_path, posture=HOT)
        _add_goal_store(target, title, completed=2, total=5)
        out = tick_line.facts(target)
        assert 'goal #G1 "modular watch.py, React front end" 2/5' in out, out

    def test_goal_handle_follows_the_current_goal(self, tmp_path):
        """Differential: a hardcoded handle cannot survive two real goals."""
        a = make_target(tmp_path / "a", posture=HOT)
        _add_goal_store(a, "goal alpha", completed=1, total=4)
        b = make_target(tmp_path / "b", posture=HOT)
        _add_goal_store(b, "goal beta", completed=3, total=3)
        fa, fb = tick_line.facts(a), tick_line.facts(b)
        assert 'goal #G1 "goal alpha" 1/4' in fa
        assert 'goal #G1 "goal beta" 3/3' in fb
        assert "goal alpha" not in fb
        assert "goal beta" not in fa

    def test_goal_sits_in_the_trailing_slot_before_the_src_stamp(
            self, tmp_path):
        target = make_target(tmp_path, posture=HOT)
        _add_goal_store(target, "ordered", completed=1, total=2)
        out = tick_line.facts(target)
        assert 'goal #G1 "ordered" 1/2 \u00b7 src ' in out, (
            "goal handle is not in the trailing slot before the src stamp "
            "(design call 2): %s" % out)

    def test_long_title_is_elided_and_fleet_count_stays_readable(
            self, tmp_path, monkeypatch):
        """THE DIRECTION-2 FALSE-GREEN THIS INCREMENT EXISTS TO CLOSE.

        The vacuous check is 'the line contains the goal' — which passes even
        when an un-elided title has pushed the fleet count off the read. The
        binding property is the fleet count staying readable AT the longest
        title the elision permits, not at a convenient short one. The title
        here is genuinely long (real acceptance criteria), and the fleet count
        the loop dispatches on must still be a readable substring beside it.
        """
        long_title = (
            "Ship modular watch.py with a React front end, goal panel "
            "verdicts, the current-goal pointer, and a tick-line handle; "
            "acceptance: the fleet count is never pushed off the read at any "
            "title length, because elision to 48 is the feature")
        assert len(long_title) > tick_line.GOAL_TITLE_LIMIT  # precondition
        target = make_target(tmp_path, posture=HOT)
        _add_goal_store(target, long_title, completed=7, total=19)
        monkeypatch.setattr(lane_liveness, "inspect_lanes", lambda _t:
            lane_liveness.LaneInspection(('cx-862', 'cx-864'), (), (), 41))
        out = tick_line.facts(target)
        # The fleet count the loop dispatches on is still a readable substring.
        assert "lanes 2 live [cx-862, cx-864]" in out, (
            "the long goal title pushed the fleet count out of view (#612): "
            "%s" % out)
        # The title was elided, never printed in full.
        assert long_title not in out, (
            "title longer than GOAL_TITLE_LIMIT was not elided: %s" % out)
        assert "7/19" in out
        # The quoted content is capped at exactly GOAL_TITLE_LIMIT chars.
        shown = long_title[:tick_line.GOAL_TITLE_LIMIT - 1] + "\u2026"
        assert len(shown) == tick_line.GOAL_TITLE_LIMIT
        assert 'goal #G1 "%s" 7/19' % shown in out, (
            "elided title was not the hard %d-char cut: %s"
            % (tick_line.GOAL_TITLE_LIMIT, out))

    def test_title_at_the_elision_boundary_is_full_and_keeps_fleet_readable(
            self, tmp_path, monkeypatch):
        """AT the longest title the elision permits to pass through un-elided."""
        boundary = "x" * tick_line.GOAL_TITLE_LIMIT  # exactly 48: not elided
        target = make_target(tmp_path, posture=HOT)
        _add_goal_store(target, boundary, completed=0, total=3)
        monkeypatch.setattr(lane_liveness, "inspect_lanes", lambda _t:
            lane_liveness.LaneInspection(('cx-1',), (), (), 7))
        out = tick_line.facts(target)
        assert "lanes 1 live [cx-1]" in out
        assert 'goal #G1 "%s" 0/3' % boundary in out, (
            "a title of exactly GOAL_TITLE_LIMIT should pass through full, "
            "not be elided: %s" % out)

    def test_no_current_goal_is_distinct_from_a_store_that_will_not_answer(
            self, tmp_path):
        """Degrade-to-zero (#868/#875/#883/#867/#886/#888 shape): 'no goal is
        set' and 'the goal store did not answer' must not render the same."""
        # No store at all (markdown-mode target): the goal system is absent.
        markdown = tick_line.facts(make_target(tmp_path / "md", posture=HOT))
        assert "no current goal" in markdown
        assert "GOAL UNKNOWN" not in markdown

        # Store answered and the pointer is empty: genuinely no goal set.
        empty_target = make_target(tmp_path / "empty", posture=HOT)
        _add_goal_store(empty_target, "exists but unset", current=False)
        empty = tick_line.facts(empty_target)
        assert "no current goal (1 goal defined)" in empty
        assert "GOAL UNKNOWN" not in empty

        # Store exists but will not answer the goal question: the current-goal
        # pointer row is gone (the shape a pre-v008 or damaged store produces).
        import sqlite3
        damaged = make_target(tmp_path / "damaged", posture=HOT)
        _add_goal_store(damaged, "was current", current=True)
        conn = sqlite3.connect(
            str(Path(damaged) / ".dreamwork" / "ledger.sqlite3"))
        conn.execute("DELETE FROM meta WHERE key = 'current_goal_id'")
        conn.commit()
        conn.close()
        unreadable = tick_line.facts(damaged)
        assert "GOAL UNKNOWN" in unreadable, (
            "a store that would not answer rendered as 'no current goal' "
            "(the degrade-to-zero false green): %s" % unreadable)
        assert "no current goal" not in unreadable
        assert "current_goal_id" in unreadable  # the reason is named

    def test_null_pointer_names_the_measured_goal_population(self, tmp_path):
        """A zero-only fixture would pass before #963; move N and filter kind."""
        from dreamwork_db import Access, open_database
        from dreamwork_db.store import dreamwork_store_spec

        populated = make_target(tmp_path / "populated", posture=HOT)
        _add_goal_store(populated, "first goal", current=False)
        _add_goal_store(populated, "second goal", current=False)
        populated_db = Path(populated) / ".dreamwork" / "ledger.sqlite3"
        with open_database(
                dreamwork_store_spec(populated_db), access=Access.WRITE) as store:
            with store.transaction() as tx:
                tx.groups.create(
                    kind="batch", title="not a goal", actor="test", at="now")
        assert tick_line._goal_fact(populated) == (
            "no current goal (2 goals defined)")

        zero = make_target(tmp_path / "zero", posture=HOT)
        zero_db = Path(zero) / ".dreamwork" / "ledger.sqlite3"
        with open_database(dreamwork_store_spec(zero_db), access=Access.WRITE):
            pass
        assert tick_line._goal_fact(zero) == (
            "no current goal (0 goals defined)")

    def test_dangling_current_pointer_is_unknown_not_a_population(self, tmp_path):
        """A non-null pointer must be validated before any healthy rendering."""
        import sqlite3

        target = make_target(tmp_path, posture=HOT)
        goal_id = _add_goal_store(target, "deleted", current=True)
        db = Path(target) / ".dreamwork" / "ledger.sqlite3"
        conn = sqlite3.connect(str(db))
        conn.execute("DELETE FROM task_group WHERE id = ?", (goal_id,))
        conn.commit()
        conn.close()
        out = tick_line._goal_fact(target)
        assert out.startswith("GOAL UNKNOWN ("), out
        assert "goals defined" not in out

    def test_corrupt_store_is_not_rendered_as_no_goal(self, tmp_path):
        """The unreadable arm: a store file that is not a database at all."""
        broken = make_target(tmp_path / "broken", posture=HOT)
        _add_goal_store(broken, "was current", current=True)
        (Path(broken) / ".dreamwork" / "ledger.sqlite3").write_bytes(
            b"this is not a sqlite database\x00")
        out = tick_line.facts(broken)
        assert "GOAL UNKNOWN" in out, (
            "a corrupt store rendered as 'no current goal': %s" % out)
        assert "no current goal" not in out

    def test_no_details_from_the_goal_leak_onto_the_line(self, tmp_path):
        """#862: the line is a handle. The goal description is never quoted."""
        target = make_target(tmp_path, posture=HOT)
        _add_goal_store(target, "titled goal", completed=0, total=1,
                        description="SECRET-ACCEPTANCE-CRITERIA-NEVER-ON-LINE")
        out = tick_line.facts(target)
        assert "SECRET-ACCEPTANCE-CRITERIA" not in out
        assert 'goal #G' in out


class TestLiveLivenessOnTheTickLine:
    """#1155: the live count qualifies itself. A wedged lane is named so the
    fleet count no longer asserts a working count it never measured. These
    inject a LaneInspection with live_liveness verdicts — the same way the
    other fleet tests inject lane counts — so no real process is touched."""

    def _inspection(self, live=(), cwd_live=(), liveness=()):
        return lane_liveness.LaneInspection(
            live=tuple(live), worktree_only=(), process_only=(),
            examined_processes=99, cwd_live=tuple(cwd_live),
            live_liveness=tuple(liveness))

    def test_wedged_lane_named_on_the_line(self, tmp_path, monkeypatch):
        """The lane that prompted #1155: a live runner that cannot do work.
        The tick names it WEDGED so the count is not read as a working count."""
        target = make_target(tmp_path, posture=HOT)
        verdicts = (lane_liveness.LiveLane(
            "glm-wedged", lane_liveness.LIVE_WEDGED,
            "auto-rejecting external_directory"),)
        monkeypatch.setattr(lane_liveness, "inspect_lanes",
                            lambda _t: self._inspection(live=("glm-wedged",),
                                                        liveness=verdicts))
        out = tick_line.facts(target)
        assert "lanes 1 live [glm-wedged]" in out, \
            "the wedged lane should still count in the live headline: %s" % out
        assert "WEDGED 1 [glm-wedged]" in out, \
            "the wedged lane was not named on the tick line: %s" % out
        assert "positive wedge evidence" in out

    def test_working_fleet_renders_zero_counts(self, tmp_path, monkeypatch):
        """#868 / #1155 P2a: when every lane is working, the zero counts for
        wedged / unknown / not-yet-observed are STILL rendered — a count that
        disappears when it is zero is a denominator the reader must
        reconstruct. The zero forms are compact (no names, no parenthetical)
        so the line does not grow unboundedly (#612). The zero label for
        WEDGED is lowercase ('wedged 0'): zero wedged lanes is not alarming."""
        target = make_target(tmp_path, posture=HOT)
        verdicts = (
            lane_liveness.LiveLane("cx-a", lane_liveness.LIVE_WORKING, "5s cpu"),
            lane_liveness.LiveLane("cx-b", lane_liveness.LIVE_WORKING, "8s cpu"))
        monkeypatch.setattr(lane_liveness, "inspect_lanes",
                            lambda _t: self._inspection(live=("cx-a", "cx-b"),
                                                        liveness=verdicts))
        out = tick_line.facts(target)
        assert "lanes 2 live [cx-a, cx-b]" in out
        assert "working 2 [cx-a, cx-b] (cpu above floor)" in out
        # Zero counts are rendered compactly — the denominator is visible.
        assert "wedged 0" in out
        assert "live-liveness-unknown 0" in out
        assert "not-yet-observed 0" in out
        # No alarming non-zero WEDGED count.
        assert "WEDGED 1" not in out

    def test_unknown_lane_named_so_cannot_tell_is_sayable(self, tmp_path,
                                                          monkeypatch):
        """#136: 'cannot tell' must be sayable. A lane the probe could not
        classify is named live-liveness-unknown, not folded into wedged or
        silently dropped — the honest stall signature."""
        target = make_target(tmp_path, posture=HOT)
        verdicts = (lane_liveness.LiveLane(
            "glm-maybe", lane_liveness.LIVE_UNKNOWN, "no signal"),)
        monkeypatch.setattr(lane_liveness, "inspect_lanes",
                            lambda _t: self._inspection(live=("glm-maybe",),
                                                        liveness=verdicts))
        out = tick_line.facts(target)
        assert "lanes 1 live [glm-maybe]" in out
        assert "live-liveness-unknown 1 [glm-maybe]" in out, \
            "an unclassifiable lane was not named on the line: %s" % out
        assert "could not classify" in out

    def test_not_yet_observed_counted_not_named(self, tmp_path, monkeypatch):
        """A young lane is too common to name individually — a fleet of freshly
        dispatched lanes would all read not-yet-observed and bury the count.
        The count is stated; the names are not (#612)."""
        target = make_target(tmp_path, posture=HOT)
        verdicts = (lane_liveness.LiveLane(
            "cx-young", lane_liveness.LIVE_NOT_YET, "alive 30s"),)
        monkeypatch.setattr(lane_liveness, "inspect_lanes",
                            lambda _t: self._inspection(live=("cx-young",),
                                                        liveness=verdicts))
        out = tick_line.facts(target)
        assert "lanes 1 live [cx-young]" in out
        assert "not-yet-observed 1" in out
        assert "cx-young" not in out.split("not-yet-observed")[1]

    def test_mixed_fleet_names_wedged_and_unknown(self, tmp_path, monkeypatch):
        """The #868 denominator: a fleet with one wedged, one unknown, one
        working must name the first two and state the denominator implicitly
        by counting all live lanes in the headline."""
        target = make_target(tmp_path, posture=HOT)
        verdicts = (
            lane_liveness.LiveLane("glm-w", lane_liveness.LIVE_WEDGED, "m"),
            lane_liveness.LiveLane("glm-u", lane_liveness.LIVE_UNKNOWN, "?"),
            lane_liveness.LiveLane("cx-ok", lane_liveness.LIVE_WORKING, "c"))
        monkeypatch.setattr(lane_liveness, "inspect_lanes",
                            lambda _t: self._inspection(
                                live=("glm-w", "glm-u", "cx-ok"),
                                liveness=verdicts))
        out = tick_line.facts(target)
        assert "lanes 3 live [cx-ok, glm-u, glm-w]" in out
        assert "WEDGED 1 [glm-w]" in out
        assert "live-liveness-unknown 1 [glm-u]" in out

    def test_no_liveness_verdicts_means_no_clause(self, tmp_path, monkeypatch):
        """A LaneInspection with no live_liveness (e.g. an older caller, or no
        live lanes) adds no clause — the qualifier is purely additive."""
        target = make_target(tmp_path, posture=HOT)
        monkeypatch.setattr(lane_liveness, "inspect_lanes",
                            lambda _t: lane_liveness.LaneInspection(
                                live=(), worktree_only=(), process_only=(),
                                examined_processes=50))
        out = tick_line.facts(target)
        assert "lanes 0 live []" in out
        assert "WEDGED" not in out
        assert "live-liveness-unknown" not in out

    def test_unrendered_liveness_state_is_named(self, tmp_path, monkeypatch):
        """#1155 round 4 / #651: a verdict state NOT in _LIVENESS_CLAUSE_SPECS
        is a denominator mismatch — the headline counts a live lane the
        rendered clauses do not name. Without this guard the tick prints
        'lanes 1 live [foo] · working 0 · wedged 0 · ... 0 · ... 0' and the
        reader must do arithmetic to notice. The mismatch must be NAMED so a
        reader meets it at the surface, not in the arithmetic (#868)."""
        target = make_target(tmp_path, posture=HOT)
        verdicts = (lane_liveness.LiveLane(
            "glm-fifth", "fifth-state", "a state the tick does not render"),)
        monkeypatch.setattr(lane_liveness, "inspect_lanes",
                            lambda _t: self._inspection(live=("glm-fifth",),
                                                        liveness=verdicts))
        out = tick_line.facts(target)
        assert "lanes 1 live [glm-fifth]" in out, \
            "the fifth-state lane should still count in the headline: %s" % out
        assert "UNRENDERED-LIVENESS-STATE" in out, \
            "a verdict state not in _LIVENESS_CLAUSE_SPECS was not named " \
            "on the tick line — the denominator mismatch is invisible " \
            "without arithmetic: %s" % out
        assert "fifth-state" in out, \
            "the unrendered state name was not quoted: %s" % out
        assert "glm-fifth" in out.split("UNRENDERED")[1], \
            "the unrendered lane was not named: %s" % out
