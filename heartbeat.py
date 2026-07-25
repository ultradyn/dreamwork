#!/usr/bin/env python3
"""heartbeat — print a message on a schedule, at an interval or aligned to the clock.

A stdlib-only port of the Rust `heartbeat` (~/src/heartbeat), vendored so the
dreamwork loop's wake mechanism is never a binary that happens to be installed
on one machine. Same CLI, same output, same scheduling arithmetic.

    heartbeat.py [OPTIONS] <INTERVAL> <MESSAGE>

INTERVALS

    Plain — fires N from now, then every N:
        30m         30 minutes from now, then every 30m
        2h30m       compound
        4.75m       fractional values are allowed (this is the loop's own tick)
        500ms       units: ms, s, m, h, d

    Aligned (@) — fires on wall-clock multiples from local midnight:
        @15m        :00, :15, :30, :45 of every hour
        @1h+15m     with an offset: :15 past every hour

    An offset requires aligned mode, must be strictly less than the interval,
    and the interval must be non-zero.

OPTIONS

    -p, --print-datetime    prefix with YYYY-MM-DD HH:MM:SS.mmm
    -n, --nb-iters N        fire N times then exit (default: forever)
    --time-prefix           prefix with [HH:MM] (on by default)
    --no-time-prefix        turn that prefix off
    --time-prefix-utc       render both prefixes in UTC

ONE DELIBERATE DIVERGENCE FROM THE RUST, and it is a fix rather than a drift:
the Rust README documents `--no-time-prefix`, but the binary rejects it
(`error: unexpected argument`) because the flag is declared with a default of
true and clap gives no negation. So the prefix cannot be switched off there at
all, and the documented flag is a dead letter. This port implements what the
README says: `--no-time-prefix` works, and `--time-prefix` is accepted as a
no-op for compatibility. Verified against the binary 2026-07-25.

KNOWN EDGE: alignment is computed against naive local midnight, so a DST
transition on the day of an aligned fire can shift it by the offset of the
jump. The Rust resolves local midnight properly and panics if it does not
exist. Matching that needs a real tz database and a zone name; it is not worth
a dependency for a heartbeat, but it is worth knowing rather than discovering.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timedelta, timezone

MS_PER_SECOND = 1_000
MS_PER_MINUTE = 60_000
MS_PER_HOUR = 3_600_000
MS_PER_DAY = 86_400_000

_UNIT_MS = {
    "ms": 1,
    "s": MS_PER_SECOND,
    "m": MS_PER_MINUTE,
    "h": MS_PER_HOUR,
    "d": MS_PER_DAY,
}

# `ms` must precede the single letters or "500ms" parses as "500m" + "s".
_DURATION_RE = re.compile(r"(\d+(?:\.\d+)?)(ms|[dhms])")


class ScheduleError(ValueError):
    """A malformed interval or offset. Message is shown to the user as-is."""


def parse_compound(text: str) -> int:
    """Parse a compound duration like `2h30m` or `4.75m` into whole milliseconds.

    Strict by construction: every character must belong to a token, so `30x`
    and `30m junk` are errors rather than a silently truncated 30 minutes. The
    total is truncated to milliseconds, matching the Rust.
    """
    if not text:
        raise ScheduleError("empty duration")
    total_ms = 0.0
    cursor = 0
    for match in _DURATION_RE.finditer(text):
        if match.start() != cursor:
            raise ScheduleError(f"invalid duration: {text}")
        cursor = match.end()
        total_ms += float(match.group(1)) * _UNIT_MS[match.group(2)]
    if cursor != len(text):
        raise ScheduleError(f"invalid duration: {text}")
    return int(total_ms)


class Schedule:
    __slots__ = ("interval_ms", "offset_ms", "aligned")

    def __init__(self, interval_ms: int, offset_ms: int, aligned: bool) -> None:
        self.interval_ms = interval_ms
        self.offset_ms = offset_ms
        self.aligned = aligned

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Schedule):
            return NotImplemented
        return (
            self.interval_ms == other.interval_ms
            and self.offset_ms == other.offset_ms
            and self.aligned == other.aligned
        )

    def __repr__(self) -> str:
        return (
            f"Schedule(interval_ms={self.interval_ms}, "
            f"offset_ms={self.offset_ms}, aligned={self.aligned})"
        )


def parse_schedule(text: str) -> Schedule:
    """Parse `30m`, `@15m`, or `@1h+15m` into a Schedule."""
    aligned = text.startswith("@")
    rest = text[1:] if aligned else text

    interval_str, sep, offset_str = rest.partition("+")
    if sep and not aligned:
        raise ScheduleError("offset (+...) requires aligned mode (@)")

    interval_ms = parse_compound(interval_str)
    if interval_ms == 0:
        raise ScheduleError("interval must be non-zero")

    offset_ms = parse_compound(offset_str) if sep else 0
    if aligned and offset_ms >= interval_ms:
        raise ScheduleError("offset must be strictly less than interval")

    return Schedule(interval_ms, offset_ms, aligned)


def compute_next_fire(now: datetime, schedule: Schedule) -> datetime:
    """The next aligned fire at or after `now`, anchored to local midnight.

    Always strictly after `now`: `k` is the count of whole intervals elapsed
    plus one, so calling this at an exact boundary yields the NEXT one rather
    than returning immediately and spinning.
    """
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    since_midnight_ms = int((now - midnight).total_seconds() * 1000)

    adjusted = since_midnight_ms - schedule.offset_ms
    k = 0 if adjusted < 0 else adjusted // schedule.interval_ms + 1
    target_ms = k * schedule.interval_ms + schedule.offset_ms

    if target_ms >= MS_PER_DAY:
        # Past the end of the day: restart the cadence at tomorrow's anchor
        # rather than letting a long interval drift across midnight.
        return midnight + timedelta(days=1, milliseconds=schedule.offset_ms)
    return midnight + timedelta(milliseconds=target_ms)


def format_duration(total_ms: int) -> str:
    """Render milliseconds the way the startup banner does: `2h30m`, `500ms`."""
    days, total_ms = divmod(total_ms, MS_PER_DAY)
    hours, total_ms = divmod(total_ms, MS_PER_HOUR)
    mins, total_ms = divmod(total_ms, MS_PER_MINUTE)
    secs, ms = divmod(total_ms, MS_PER_SECOND)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    if secs:
        parts.append(f"{secs}s")
    if ms:
        parts.append(f"{ms}ms")
    return "".join(parts) or "0s"


def banner(schedule: Schedule, message: str) -> str:
    if schedule.aligned:
        suffix = (
            f" (offset {format_duration(schedule.offset_ms)})"
            if schedule.offset_ms
            else ""
        )
        return (
            f'heartbeat will repeat "{message}" every '
            f"{format_duration(schedule.interval_ms)} aligned to midnight{suffix}"
        )
    minutes = schedule.interval_ms / 60_000
    return f'heartbeat is set up to repeat "{message}" every {minutes:.2f} minutes'


def render_line(
    fire_at: datetime,
    message: str,
    *,
    time_prefix: bool,
    utc: bool,
    print_datetime: bool,
    remaining: int | None,
    total: int | None,
) -> str:
    """Build one output line.

    Both prefixes are rendered from the SCHEDULED time, not from the moment the
    sleep happened to return — so an aligned `@15m` prints `[10:45]` even if the
    process woke a few milliseconds late.
    """
    stamp = fire_at.astimezone(timezone.utc) if utc else fire_at
    prefix = f"[{stamp:%H:%M}] " if time_prefix else ""
    countdown = f"[{remaining}/{total}] " if total is not None else ""
    if print_datetime:
        millis = f"{stamp:%Y-%m-%d %H:%M:%S}.{stamp.microsecond // 1000:03d}"
        return f"{prefix}{countdown}{millis} {message}"
    return f"{prefix}{countdown}{message}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="heartbeat",
        description=(
            "Print a message repeatedly, either at a fixed interval after "
            "start or aligned to wall-clock boundaries (cron-like)."
        ),
    )
    parser.add_argument(
        "-p",
        "--print-datetime",
        action="store_true",
        help="Prefix each message with a timestamp (YYYY-MM-DD HH:MM:SS.mmm)",
    )
    parser.add_argument(
        "--time-prefix",
        dest="time_prefix",
        action="store_true",
        default=True,
        help="Prefix each output line with [HH:MM] (on by default)",
    )
    parser.add_argument(
        "--no-time-prefix",
        dest="time_prefix",
        action="store_false",
        help="Turn the [HH:MM] prefix off",
    )
    parser.add_argument(
        "--time-prefix-utc",
        action="store_true",
        help="Use UTC for the time prefixes instead of local",
    )
    parser.add_argument(
        "-n",
        "--nb-iters",
        type=int,
        default=None,
        help="Number of times to fire before exiting (default: run forever)",
    )
    parser.add_argument(
        "interval",
        help="How often to fire. Plain (30m, 2h30m, 4.75m) or aligned (@15m, @1h+15m).",
    )
    parser.add_argument("message", help="Message to print on each firing")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        schedule = parse_schedule(args.interval)
    except ScheduleError as exc:
        print(f"heartbeat: {exc}", file=sys.stderr)
        return 2

    print(banner(schedule, args.message), flush=True)

    fired = 0
    while args.nb_iters is None or fired < args.nb_iters:
        now = datetime.now()
        if schedule.aligned:
            fire_at = compute_next_fire(now, schedule)
        else:
            fire_at = now + timedelta(milliseconds=schedule.interval_ms)

        wait = (fire_at - now).total_seconds()
        if wait > 0:
            time.sleep(wait)

        print(
            render_line(
                fire_at,
                args.message,
                time_prefix=args.time_prefix,
                utc=args.time_prefix_utc,
                print_datetime=args.print_datetime,
                remaining=None if args.nb_iters is None else args.nb_iters - fired,
                total=args.nb_iters,
            ),
            flush=True,
        )
        fired += 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
