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
        """Both set-difference directions are visible, never silently chosen."""
        target = Path(make_target(tmp_path / "project", posture=HOT))
        registered = tmp_path / ".worktrees" / "cx-finished"
        registered.mkdir(parents=True)
        removed = tmp_path / ".worktrees" / "cx-removed"
        raw = ("ccc\x00# Task #999 -- fixture\nWorktree: %s\n" % removed).encode()
        inspection = lane_liveness.inspect_lanes(
            target, process_entries=["999"],
            registered_worktrees=(registered,), read_cmdline=lambda _pid: raw)
        assert inspection.live == ()
        assert inspection.worktree_only == ('cx-finished',), \
            "registered worktree without a process was not named"
        assert inspection.process_only == ('cx-removed',), \
            "process whose worktree was removed was not named"
        monkeypatch.setattr(lane_liveness, "inspect_lanes", lambda _target: inspection)
        out = tick_line.facts(str(target))
        assert "worktree-only 1 [cx-finished]" in out
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
    NEEDLE = "] + posture_parts + [_stamp_fact()])"
    REPLACEMENT = "] + posture_parts + [_stamp_fact(), \"%s\"])" % SENTINEL

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
