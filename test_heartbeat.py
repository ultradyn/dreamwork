"""Tests for heartbeat.py.

The first six classes are the Rust suite's tests, ported case for case and in
its order, because the point of the port is behavioural identity — a test that
only checks what the Python does proves nothing about whether it is a copy.
Cases beyond that suite are marked where they appear.
"""

from datetime import datetime, timedelta, timezone

import pytest

from heartbeat import (
    ScheduleError,
    Schedule,
    banner,
    compute_next_fire,
    format_duration,
    main,
    parse_compound,
    parse_schedule,
    render_line,
)


class TestParseCompound:
    def test_single_token(self):
        assert parse_compound("30m") == 30 * 60_000
        assert parse_compound("500ms") == 500
        assert parse_compound("1.5s") == 1500

    def test_compound_tokens(self):
        assert parse_compound("2h30m") == 150 * 60_000
        assert parse_compound("1h15m30s") == 60 * 60_000 + 15 * 60_000 + 30_000
        assert parse_compound("1d2h") == 26 * 3_600_000

    @pytest.mark.parametrize("bad", ["", "30", "m30", "30m junk", "30x"])
    def test_rejects_garbage(self, bad):
        with pytest.raises(ScheduleError):
            parse_compound(bad)

    def test_fractional_minutes(self):
        # Not in the Rust suite, but this is the loop's own tick and the
        # 4.75m -> 285000ms truncation is the whole reason it works.
        assert parse_compound("4.75m") == 285_000

    def test_ms_wins_over_m_then_s(self):
        # Not in the Rust suite. "500ms" must not parse as 500m + s; the
        # alternation order in the regex is load-bearing and silent if wrong.
        assert parse_compound("500ms") != parse_compound("500m")


class TestParseSchedule:
    def test_aligned_no_offset(self):
        s = parse_schedule("@30m")
        assert s == Schedule(30 * 60_000, 0, True)

    def test_aligned_with_offset(self):
        s = parse_schedule("@1h+15m")
        assert s == Schedule(3_600_000, 15 * 60_000, True)

    def test_unaligned(self):
        s = parse_schedule("30m")
        assert s == Schedule(30 * 60_000, 0, False)

    @pytest.mark.parametrize(
        "bad,why",
        [
            ("30m+5m", "offset without @"),
            ("@30m+45m", "offset >= interval"),
            ("@30m+30m", "offset == interval"),
            ("@0s", "zero interval"),
        ],
    )
    def test_rejects_bad_forms(self, bad, why):
        with pytest.raises(ScheduleError):
            parse_schedule(bad)


def at(h, m, s=0, day=15):
    return datetime(2024, 6, day, h, m, s)


class TestComputeNextFire:
    def test_quarter_hour(self):
        s = parse_schedule("@15m")
        assert compute_next_fire(at(10, 7), s) == at(10, 15)
        # On the boundary itself: the NEXT one, never now — otherwise a fire
        # that lands exactly on the mark busy-loops.
        assert compute_next_fire(at(10, 15), s) == at(10, 30)

    def test_hour_with_offset(self):
        s = parse_schedule("@1h+15m")
        assert compute_next_fire(at(10, 7), s) == at(10, 15)
        assert compute_next_fire(at(10, 20), s) == at(11, 15)

    def test_rolls_past_midnight(self):
        s = parse_schedule("@2h30m")
        assert compute_next_fire(at(22, 45), s) == at(0, 0, day=16)

    def test_rolls_past_midnight_with_offset(self):
        s = parse_schedule("@2h30m+30m")
        assert compute_next_fire(at(23, 30), s) == at(0, 30, day=16)

    def test_before_first_offset_fire(self):
        # Not in the Rust suite. Between midnight and the first offset fire,
        # `adjusted` is negative and k must clamp to 0 rather than floor to -1.
        s = parse_schedule("@1h+15m")
        assert compute_next_fire(at(0, 5), s) == at(0, 15)


class TestFormatDuration:
    def test_components(self):
        assert format_duration(150 * 60_000) == "2h30m"
        assert format_duration(15 * 60_000) == "15m"
        assert format_duration(500) == "500ms"
        assert format_duration(0) == "0s"


class TestBanner:
    """Not in the Rust suite: the startup line is the only output a short-lived
    caller sees, and its two forms are worded differently on purpose."""

    def test_plain_reports_minutes_to_two_places(self):
        assert banner(parse_schedule("4.75m"), "dream tick") == (
            'heartbeat is set up to repeat "dream tick" every 4.75 minutes'
        )

    def test_aligned_names_the_anchor(self):
        assert banner(parse_schedule("@15m"), "ping") == (
            'heartbeat will repeat "ping" every 15m aligned to midnight'
        )

    def test_aligned_with_offset_says_so(self):
        assert banner(parse_schedule("@1h+15m"), "ping") == (
            'heartbeat will repeat "ping" every 1h aligned to midnight '
            "(offset 15m)"
        )


class TestRenderLine:
    """Not in the Rust suite, which only asserted that %H:%M is five characters.
    These pin the actual line the loop's monitor greps."""

    FIRE = datetime(2024, 6, 15, 10, 15, 30, 123_000)

    def line(self, **kw):
        opts = dict(
            time_prefix=True,
            utc=False,
            print_datetime=False,
            remaining=None,
            total=None,
        )
        opts.update(kw)
        return render_line(self.FIRE, "dream tick", **opts)

    def test_default_shape(self):
        assert self.line() == "[10:15] dream tick"

    def test_prefix_can_be_turned_off(self):
        # The divergence from the Rust: there, --no-time-prefix is documented
        # but rejected by the binary, so this is unreachable.
        assert self.line(time_prefix=False) == "dream tick"

    def test_countdown_counts_down_and_never_reaches_zero(self):
        assert self.line(remaining=2, total=2) == "[10:15] [2/2] dream tick"
        assert self.line(remaining=1, total=2) == "[10:15] [1/2] dream tick"

    def test_datetime_carries_milliseconds(self):
        assert self.line(print_datetime=True) == (
            "[10:15] 2024-06-15 10:15:30.123 dream tick"
        )

    def test_utc_shifts_both_prefixes_together(self):
        aware = self.FIRE.replace(tzinfo=timezone(timedelta(hours=10)))
        out = render_line(
            aware,
            "dream tick",
            time_prefix=True,
            utc=True,
            print_datetime=True,
            remaining=None,
            total=None,
        )
        assert out == "[00:15] 2024-06-15 00:15:30.123 dream tick"


class TestMain:
    """End to end, with intervals short enough to actually run."""

    def test_fires_n_times_then_exits(self, capsys):
        assert main(["-n", "2", "10ms", "tick"]) == 0
        lines = capsys.readouterr().out.strip().splitlines()
        assert len(lines) == 3  # banner + two firings
        assert lines[0].startswith("heartbeat is set up to repeat")
        assert lines[1].endswith("[2/2] tick")
        assert lines[2].endswith("[1/2] tick")

    def test_bad_interval_exits_2_with_a_reason(self, capsys):
        assert main(["30x", "tick"]) == 2
        assert "invalid duration" in capsys.readouterr().err

    def test_no_time_prefix_is_accepted(self, capsys):
        assert main(["-n", "1", "--no-time-prefix", "10ms", "tick"]) == 0
        assert capsys.readouterr().out.strip().splitlines()[1] == "[1/1] tick"
