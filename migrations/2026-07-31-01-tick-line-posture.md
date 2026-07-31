# 2026-07-31 — the tick line carries the posture, the policy and the fleet

## What changed

The heartbeat message was static: `heartbeat` takes `<MESSAGE>` as a
positional string once, at monitor setup, and reprints those bytes forever.
It said what to do and nothing about the state the loop was in, so after a
compaction the posture habit could be gone while the monitor kept firing
normally.

`tick_line.py` now sits downstream of `heartbeat` in the monitor command and
appends the resolved facts to every pulse:

    heartbeat 4.75m '<micro-protocol>' | python3 <skill-dir>/tick_line.py --target <target>

Today's line:

    <pulse> · lanes 6 recorded · runners opus 5, ccc 1 · 0 ccc-live ·
    delegation 5 · 180 open · pace hot · asking near-auto · delivery batched ·
    orchestration orchestrator · subagent-policy 4 lines (default)

`heartbeat` itself is UNCHANGED. It is a shared CLI used by other projects
and must not learn this loop's posture files; it stays the scheduler and this
repo owns the text. Nothing landed outside this repo.

## How to apply

Running sessions: swap the monitor — `TaskStop` the old one, then arm the new
command from initialization step 5 (stop-then-arm; never two at once). Fresh
sessions pick it up automatically.

**The swap is the only way to get this.** A monitor armed before today keeps
firing the bare pulse and looks completely normal doing it.

## What it will and will not tell you

It states measurements, not verdicts. There is no DRIFT flag: lanes are
legitimately at zero for minutes after a merge, and a flag that fired most of
the time would train you to skip the line.

It never prints an unqualified fleet size, and that is the load-bearing
caveat. `status_sync.live_lanes` derives liveness from `pgrep -af ccc`, so
harness-native Agent-tool lanes are structurally invisible to it — six lanes
were out while it answered 0 on the day this landed. So each count names how
it was obtained: `recorded` is your own `status.json["lanes"]` bookkeeping
(sees every dispatch form, goes stale upward), `ccc-live` is the OS
measurement (cannot be inflated, blind to Agent-tool lanes). They bound the
truth from opposite sides. `#675` tracks closing the gap.

Anything it cannot resolve is printed in CAPITALS with its reason, in the
place the number would have been — never omitted and never silently defaulted
back to the bare pulse, which is the shape that reassures where it should
shout (#655). Upper case in the facts always means "a number here is
missing".

`runners` tallies the recorded fleet by the first token of each lane's
`model`. It is there because the subagent-policy drift is the half with the
measured recurrence — three occurrences of reaching for native by habit, the
third with `DREAMWORK.md`'s own diagnosis sitting in the file: *"a routing
rule that lives only in prose is re-checked exactly as often as someone
happens to re-read the prose."* So the line shows what you ARE running rather
than restating what you should.
