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
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import status_sync
import tick_line

PULSE = "[10:15] dream tick (ud-dreamwork): run the tick flow"


def make_target(tmp_path, *, posture, open_ids=(1, 2, 3), dreamers=None,
                policy=None, run_mode="hot", lanes=()):
    """A minimal target dir: run-mode, posture, status.json, tasks.md."""
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

    def test_ccc_live_count_follows_the_process_table(self, tmp_path,
                                                      monkeypatch):
        target = make_target(
            tmp_path, posture=HOT,
            dreamers=[{"task": 1, "pid": 111}, {"task": 2, "pid": 222}])
        monkeypatch.setattr(status_sync, "_pid_alive", lambda pid: True)
        assert "2 ccc-live" in tick_line.facts(target)
        monkeypatch.setattr(status_sync, "_pid_alive", lambda pid: False)
        assert "0 ccc-live" in tick_line.facts(target)

    def test_recorded_count_follows_the_authored_lanes_field(self, tmp_path):
        none = tick_line.facts(make_target(tmp_path / "a", posture=HOT))
        six = tick_line.facts(make_target(
            tmp_path / "b", posture=HOT,
            lanes=[{"lane": "lane-%d" % i} for i in range(6)]))
        assert "lanes 0 recorded" in none
        assert "lanes 6 recorded" in six


class TestNoUnqualifiedFleetSize:
    """The count the loop cannot measure must never be asserted.

    `live_lanes` probes `pgrep -af ccc`, so Agent-tool lanes are structurally
    invisible to it: six lanes were out and it answered 0 while this was
    written. Every number here therefore names how it was obtained, and the
    bare phrasing that would imply a total is forbidden outright.
    """

    def test_agent_tool_fleet_does_not_render_as_an_empty_fleet(self,
                                                               tmp_path):
        """The measured live case: lanes recorded, none of them probeable."""
        out = tick_line.facts(make_target(
            tmp_path, posture=HOT,
            lanes=[{"lane": "lane-%d" % i, "model": "opus"}
                   for i in range(6)]))
        assert "lanes 6 recorded" in out
        assert "0 ccc-live" in out
        # The phrasing that would have inverted his signal.
        assert "0 lanes live" not in out


class TestRunnerTallyMirrorsTheDrift:
    """The subagent-policy half. The measured failure is "reached for native by
    habit", three times over, with the rule sitting in prose the whole time —
    so the line shows what the fleet IS running, not what it should."""

    def test_native_heavy_fleet_is_visible_as_such(self, tmp_path):
        """The live shape at the moment this landed: five opus to one ccc."""
        lanes = [{"lane": "l%d" % i, "model": "opus"} for i in range(5)]
        lanes.append({"lane": "l5",
                      "model": "ccc @glm52 (Opus review MANDATORY)"})
        out = tick_line.facts(make_target(tmp_path, posture=HOT, lanes=lanes))
        assert "runners opus 5, ccc 1" in out

    def test_tally_follows_the_recorded_models(self, tmp_path):
        a = tick_line.facts(make_target(
            tmp_path / "a", posture=HOT,
            lanes=[{"lane": "x", "model": "opus"}]))
        b = tick_line.facts(make_target(
            tmp_path / "b", posture=HOT,
            lanes=[{"lane": "x", "model": "ccc @glm52"}]))
        assert "runners opus 1" in a
        assert "runners ccc 1" in b

    def test_long_model_notes_cannot_grow_the_line(self, tmp_path):
        """Only the first token is tallied, so a lane note of any length costs
        the tick nothing (#612)."""
        out = tick_line.facts(make_target(
            tmp_path, posture=HOT,
            lanes=[{"lane": "x", "model": "ccc " + "very long note " * 40}]))
        assert "runners ccc 1" in out
        assert "very long note" not in out

    def test_unrecorded_model_is_a_question_mark_not_a_runner_name(self,
                                                                  tmp_path):
        out = tick_line.facts(make_target(
            tmp_path, posture=HOT, lanes=[{"lane": "x"}]))
        assert "runners ? 1" in out
        assert "None" not in out

    @pytest.mark.parametrize("banned", ["lanes live", "lanes out", "fleet "])
    def test_no_unlabelled_fleet_phrasing_ever_appears(self, tmp_path, banned):
        for lanes in ([], [{"lane": "a"}], [{"lane": "a"}, {"lane": "b"}]):
            out = tick_line.facts(
                make_target(tmp_path / str(len(lanes)), posture=HOT,
                            lanes=lanes))
            assert banned not in out

    def test_missing_lanes_field_is_loud_not_zero(self, tmp_path):
        """Absent bookkeeping and empty bookkeeping are different claims."""
        target = make_target(tmp_path, posture=HOT)
        p = Path(target) / ".dreamwork" / "status.json"
        p.write_text(json.dumps({"dreamers": []}))
        out = tick_line.facts(target)
        assert "LANES UNRECORDED" in out
        assert "0 recorded" not in out


class TestTheContradictionIsAdjacent:
    """#673's whole mechanism: the rule and the measurement that fails it, on
    the same line, close enough to read as one statement."""

    def test_counts_immediately_precede_the_delegation_target(self, tmp_path):
        out = tick_line.facts(make_target(tmp_path, posture=HOT))
        assert "lanes 0 recorded · 0 ccc-live · delegation 5" in out


class TestUnprobeableLanesDoNotBreakTheProbe:
    """#537: a `spawn_subagent` entry in `dreamers` has no probe-able process,
    so it must be carried past the liveness step rather than asked about."""

    def test_spawn_subagent_entry_does_not_raise_or_inflate_ccc_live(self,
                                                                    tmp_path):
        out = tick_line.facts(make_target(
            tmp_path, posture=HOT,
            dreamers=[{"task": 1, "pid": 111, "dispatch": "spawn_subagent"}]))
        assert "0 ccc-live" in out


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
        assert "lanes 0 recorded · 0 ccc-live" in out
        assert "3 open" in out

    def test_liveness_unknown_is_not_rendered_as_zero(self, tmp_path,
                                                      monkeypatch):
        """'I could not tell' and 'nothing is running' must not be one string
        when one of them is the alarm (status_sync's own words)."""
        target = make_target(tmp_path, posture=HOT,
                             dreamers=[{"task": 1, "pid": 111}])

        def boom(pid):
            raise status_sync.LivenessUnknown("probe broken")

        monkeypatch.setattr(status_sync, "_pid_alive", boom)
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
