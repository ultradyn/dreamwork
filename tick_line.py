#!/usr/bin/env python3
"""tick_line.py — decorate every heartbeat pulse with the live posture and fleet.

`heartbeat` takes its message as a positional string, once, at monitor setup,
and reprints those same bytes forever (`heartbeat <INTERVAL> <MESSAGE>`; the
vendored `heartbeat.py` port is identical). So the tick text has been static
since the #341 micro-protocol landed: it says what to DO and nothing about the
state the loop is actually in.

#673 (his do-next, verbatim): *"every loop tick the cli should remind the main
dreamworker what their posture is + subagent policy. This prevents forgetting
about it after compaction or getting stuck with no agents running but plenty of
work waiting."*

THIS IS A FILTER, NOT A CLOCK. heartbeat stays the only scheduler; this reads
its pulses on stdin and appends the resolved facts to each one:

    heartbeat 4.75m '<micro-protocol>' | python3 tick_line.py --target <dir>

Appending rather than composing is deliberate. The pulse passes through byte
for byte, so this program knows NOTHING about heartbeat's output grammar — not
its `[HH:MM]` prefix, not its startup banner, not its `[n/N]` countdown. Every
one of those could change tomorrow and this would still be correct. The price
is that the facts land at the end of the line rather than the front, which is
where they are read last — acceptable, because the micro-protocol half is
identical on every beat and the facts half is the only part that ever moves.

WHY THE TICK AND NOT THE SKILL. SKILL.md has said since #513 to *"restate the
posture at each tick, don't just re-read it"*, and it already names this exact
defect — *"a `delegation: 4` posture with zero lanes out is drift"*. That is
doctrine the coordinator must be holding in context to obey, and a compaction
drops it while the monitor keeps firing. The tick string is the one channel
that reaches the coordinator on every beat regardless of what its context still
holds, which is the compaction-survival property he named.

WHY IT STATES A MEASUREMENT AND NOT A RULE. "delegation 5" alone is a rule the
reader may believe they are already following. "lanes 0 recorded · delegation
5" is a measurement that contradicts them. The second clause of his sentence —
*"no agents running but plenty of work waiting"* — is the load-bearing half, so
the counts are not decoration here, they are the point.

AND THE COUNTS NAME THEIR OWN PROVENANCE, because no single honest fleet number
exists in this system today — see `_fleet_fact`, which is the most important
docstring in this file. A confident count would have inverted the very signal
he asked for.

IT DOES NOT EDITORIALISE. There is no DRIFT verdict, deliberately: lanes are
legitimately at zero for minutes after a merge, so a flag that fired most of
the time would train the reader to skip the line — the tune-out failure of #592
(false positives) and #612 (volume) arriving by a third route. This program
measures; SKILL.md says what the measurement means.

FAIL CLOSED (#655). Three facts resolve independently and any one of them may
fail without hiding the other two. A fact that cannot be resolved is printed in
CAPITALS with its reason — never omitted, and never silently degraded back to
the bare pulse, which is precisely the shape that reassures where it should
shout. Capitals are reserved for exactly this, so upper case anywhere in the
facts always means "a number here is missing", never "a number here is bad".

The pulse itself is unconditional: it is echoed before any fact is resolved, so
no failure in this file can cost the loop its wake.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import status_sync
import watch

# The separator between the pulse and the facts, and between facts. Matches the
# ` · ` the ledger and hand-off rows already use for co-ordinate lists.
SEP = " · "


def _posture_facts(p: dict) -> list[str]:
    """The four non-delegation axes, from the single source's already-merged dict.

    `watch.resolve_posture` is that source: it merges `.dreamwork/run-mode`,
    `.dreamwork/posture` and `.dreamwork/subagent-policy` into one dict and is
    what the dashboard renders. Restating the merge here would be a second
    answer to "what is the posture", free to drift from the one on screen.

    It is resolved ONCE per tick and the dict is passed down. Three separate
    calls would be three separate reads of three files, and a posture written
    between them would produce a line that never described any real state.

    Delegation is stated BESIDE the live count by the caller rather than as a
    value in this list, because it is the one axis with a measurable
    counterpart to contradict; the other four have nothing to check them
    against and are stated as values.
    """
    return [
        "pace %s" % p["pace"],
        "asking %s" % p["asking"],
        "delivery %s" % p["delivery"],
        "orchestration %s" % p["orchestration"],
    ]


def _policy_fact(p: dict) -> str:
    """The subagent policy, sized and located — never quoted.

    His words ask for the policy at every tick, but the policy is ~700
    characters of prose and this line is read on every beat forever (#612 is
    the standing lesson on volume). Quoting it would bury the one number that
    changes behaviour under the four tiers it is meant to make the reader act
    on.

    So this names what a compacted reader cannot otherwise know: that a policy
    exists, how big it is, and whether it is HIS file or the standing default —
    that last bit being the only one that distinguishes "he set this" from
    "nobody has".

    THIS IS THE SECONDARY HALF OF THE POLICY SIGNAL, and on its own it would
    not be enough: a pointer to where a rule lives reproduces the failure it is
    meant to fix, because re-reading the prose is exactly the step that does
    not happen (`DREAMWORK.md`, after the second recurrence). The half that
    does the work is `_runner_tally`, which shows what the fleet is actually
    running. This one supplies the provenance that tally cannot: whether the
    policy being drifted from is his or the default.

    Size is in LINES, matching `lint.check_subagent_policy`, which is the
    established way to size this file without reading it. Counting `- ` bullets
    would impose a grammar on a file `file-formats.md` documents as "free text
    — the whole file is the value", and which lint "deliberately never inspects
    the CONTENT" of.
    """
    lines = len([ln for ln in p["subagent_policy"].splitlines() if ln.strip()])
    return "subagent-policy %d lines (%s)" % (lines, p["subagent_policy_source"])


def _posture_file_ignored(target: str) -> str | None:
    """Why `.dreamwork/posture` contributed nothing, or None if that is fine.

    THE SILENT FALLBACK THIS EXISTS TO CATCH, measured rather than reasoned
    about: `watch.read_posture_file` reads through `read_text_full`, which
    answers `None` for a file it cannot decode, and `None` becomes `{}` —
    byte-identical to the answer for a file that is not there. `resolve_posture`
    then derives from run-mode and returns a confident posture that no file on
    disk says. A `.dreamwork/posture` containing `b"\\xff\\xfe\\x00"` yields
    `delegation 0 · pace hot · asking ask · delivery instant · orchestration
    hands-on`, and **`delegation 0` is precisely the value that tells the
    coordinator its empty fleet is correct**. A corrupt posture file would
    switch this alarm off permanently while every axis still looked answered.

    That fallback is defensible for the dashboard, which renders `source`
    beside the axes and has `lint.check_posture` watching the file. It is not
    defensible on the only line that survives a compaction. So the file is
    checked as BYTES — no decode to fail, no parse to disagree with — and any
    file that holds something while setting nothing is named.

    Absent is not a fault: derivation from run-mode is the documented,
    intended behaviour there, and it is reported as provenance, not as an error.
    """
    path = Path(target) / ".dreamwork" / "posture"
    try:
        if not path.exists():
            return None
        return "present, set no axis" if path.read_bytes().strip() else None
    except OSError as exc:
        return "unreadable (%s)" % exc.__class__.__name__


def _delegation_fact(target: str, p: dict) -> str:
    """The delegation target, carrying its own provenance when it is not his.

    The provenance rides ON this fact rather than trailing the line because
    this is the number that gets acted on, and #612's fix is the precedent: put
    the load-bearing field where nothing can push it out of view.
    """
    value = "delegation %s" % p["delegation"]
    if p.get("source") == "file":
        return value
    why = _posture_file_ignored(target)
    if why:
        return "%s (POSTURE FILE IGNORED: %s — derived from run-mode)" % (
            value, why)
    return "%s (derived from run-mode)" % value


def _open_fact(target: str) -> str:
    """How many tasks sit under `## Open` — the "plenty of work waiting" half.

    Reuses `status_sync.read_open_ids`, which dispatches on `source_of_truth`
    and counts every id in a combined head. An empty answer is reported as
    UNKNOWN rather than as zero for `status_sync`'s own stated reason: *"an
    unreadable ledger and an empty one look identical to a parser"*. A backlog
    that is genuinely empty is the rarer reading of that ambiguity, and it is
    the one whose mislabelling costs nothing.
    """
    dw = Path(target) / ".dreamwork"
    ids = status_sync.read_open_ids(dw, dw / "tasks.md")
    if not ids:
        return "OPEN UNKNOWN (no ids under `## Open`)"
    return "%d open" % len(ids)


def _runner_tally(lanes: list) -> str:
    """Which runners the recorded fleet is actually using — the policy half.

    HIS ASK WAS "posture + subagent policy", and the policy half turns out to
    be the half with the measured recurrence. In the hour before he sharpened
    the rule, five native Opus lanes went out against one `ccc @glm52`, three
    of the five plainly standard work — at least the THIRD occurrence, and it
    recurred with `DREAMWORK.md`'s own diagnosis sitting in the file: *"a
    routing rule that lives only in prose is re-checked exactly as often as
    someone happens to re-read the prose."*

    WHICH IS WHY THIS IS A TALLY AND NOT A RESTATEMENT OF THE RULE. A pointer
    ("see DREAMWORK.md") reproduces the failure exactly, because re-reading the
    prose is the step that does not happen. And a hardcoded "prefer glm52"
    would be a rule with no source: `.dreamwork/subagent-policy` is free text
    by contract — `file-formats.md` says "the whole file is the value", and
    lint "deliberately never inspects the CONTENT" — so no honest parse of it
    exists, and a literal copied into this file goes stale the next time he
    changes his mind, which he did twice this week.

    So the same move the rest of this line makes: state the live fact, not the
    rule. `runners opus 5, ccc 1` on every beat is a mirror, and the drift it
    reflects has never been "chose the wrong exotic tier" — it has always been
    "reached for native by habit". A habit is broken by seeing it, not by being
    told about it.

    The runner is the FIRST TOKEN of the recorded `model`; the rest is
    qualification ("ccc @glm52 (Opus review MANDATORY before merge)" tallies as
    `ccc`). That is a display normalisation, not a semantic parse — it imposes
    no grammar on the field and cannot disagree with it, and it keeps the line
    bounded no matter how long a lane's note grows (#612).

    Provenance is the same as `recorded`: `status.json["lanes"]` is written by
    the coordinator's judgement, so this mirrors the bookkeeping, not the OS.
    """
    counts: dict[str, int] = {}
    for lane in lanes:
        model = lane.get("model") if isinstance(lane, dict) else None
        # A lane recorded without a model is `?`, never the string "None" —
        # an unrecorded runner must not read as a runner someone chose.
        text = "" if model is None else str(model).strip()
        token = text.split()[0] if text else "?"
        counts[token] = counts.get(token, 0) + 1
    if not counts:
        return ""
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return "runners " + ", ".join("%s %d" % (k, v) for k, v in ordered)


def _read_status(target: str) -> dict:
    dw = Path(target) / ".dreamwork"
    try:
        status = json.loads((dw / "status.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise status_sync.LivenessUnknown(
            "status.json unreadable: %s" % exc.__class__.__name__)
    if not isinstance(status, dict):
        raise status_sync.LivenessUnknown("status.json is not an object")
    return status


def _fleet_fact(target: str) -> str:
    """The fleet, as TWO labelled numbers — never one unqualified "fleet size".

    THERE IS NO SINGLE HONEST FLEET COUNT IN THIS SYSTEM TODAY, and pretending
    otherwise is the whole trap. `status_sync.live_lanes` derives liveness from
    `pgrep -af ccc` plus `kill -0` on recorded pids, so it sees the `ccc`
    dispatch path and nothing else. Harness-native Agent-tool lanes run inside
    the harness process; they have no `ccc` process and no probe-able pid, and
    they are therefore **structurally invisible to it** — not by an oversight
    that could be patched, but by what the probe is. MEASURED while this file
    was written: six lanes were out (five Agent-tool, one `ccc @glm52`) and the
    probe answered 0.

    A line reading `delegation 5 · 0 lanes live` under those conditions is not
    a small inaccuracy. It is the precise inverse of the signal #673 asks for,
    fired on every beat — and a reminder that cries wolf every beat is one the
    reader learns to skip, which ends with the reminder present and the drift
    continuing. So the count is not routed as-is.

    The two sources fail in OPPOSITE directions, which is what makes reporting
    both worth its characters rather than merely verbose:

      `recorded`  — `status.json["lanes"]`, written by the coordinator's own
                    judgement. Sees every dispatch form, so it cannot be
                    deflated by the probe's blindness; it goes stale upward
                    when a landed lane is not removed. An upper bound.
      `ccc-live`  — the OS measurement. Cannot be inflated by forgetfulness;
                    it is blind to Agent-tool lanes. A lower bound.

    Each is labelled by HOW IT WAS OBTAINED, so neither can be read as "the
    fleet". Where they disagree the reader learns something real. Where both
    are zero against a delegation target, that is the alarm — and it is honest,
    because `recorded` is the source that sees all dispatch forms.

    `LivenessUnknown` propagates rather than being caught: "I could not tell"
    and "nothing is running" must not render as one string when one of them is
    the alarm (`status_sync`'s own reasoning, applied here).
    """
    status = _read_status(target)

    lanes = status.get("lanes")
    if not isinstance(lanes, list):
        recorded = "LANES UNRECORDED (status.json has no `lanes` list)"
    else:
        recorded = "%d recorded" % len(lanes)
        runners = _runner_tally(lanes)
        if runners:
            recorded += SEP + runners

    raw = status.get("dreamers", [])
    if not isinstance(raw, list):
        raise status_sync.LivenessUnknown("dreamers is not a list")
    clean = [d for d in raw if status_sync._evaluable(d)]
    observable = [d for d in clean if status_sync._observable(d)]
    live, _pruned = status_sync.live_lanes(observable)

    return "lanes %s%s%d ccc-live" % (recorded, SEP, len(live))


def _unresolved(label: str, exc: BaseException) -> str:
    """The one rendering of a fact that could not be measured.

    Capitals plus the exception class plus its message: enough for the reader
    to know which number is missing and why, in the place that number would
    have been. Never an omission and never a plausible-looking default.
    """
    return "%s UNRESOLVED (%s: %s)" % (label.upper(), exc.__class__.__name__, exc)


def _guarded(fn, label: str) -> str:
    """Run one zero-arg fact resolver; on ANY failure return a loud stand-in.

    Broad by intent. This runs inside the loop's only wake channel, so an
    exception class nobody predicted must degrade one fact rather than take the
    tick down or — worse — leave the pulse looking normal with a number quietly
    missing from it.
    """
    try:
        return fn()
    except Exception as exc:                                  # noqa: BLE001
        return _unresolved(label, exc)


def facts(target: str) -> str:
    """The whole appended fragment. Never raises, never returns empty.

    The fleet count and the delegation target lead, adjacent, because that
    juxtaposition is the contradiction #673 exists to surface: a rule and the
    measurement that fails it, side by side, needing no arithmetic from a
    reader whose context may have just been compacted away. Everything after
    them is the rest of what he asked for.

    The three sources fail independently — an unreadable posture file must not
    cost the reader the fleet count, which is the number that would have told
    them to dispatch.
    """
    try:
        p = watch.resolve_posture(target)
        posture_parts = _posture_facts(p) + [_policy_fact(p)]
        delegation = _delegation_fact(target, p)
    except Exception as exc:                                  # noqa: BLE001
        # One failure, one cause, but two holes in the line: say so at both,
        # so neither reads as "resolved and happens to be absent".
        posture_parts = [_unresolved("posture", exc),
                         _unresolved("subagent-policy", exc)]
        delegation = _unresolved("delegation", exc)

    return SEP.join([
        _guarded(lambda: _fleet_fact(target), "fleet"),
        delegation,
        _guarded(lambda: _open_fact(target), "open"),
    ] + posture_parts)


def decorate(pulse: str, target: str) -> str:
    """One heartbeat line in, one decorated line out."""
    return pulse + SEP + facts(target)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="tick_line.py",
        description="Append the live posture and fleet to each heartbeat pulse.")
    ap.add_argument("--target", default=".", help="target project directory")
    args = ap.parse_args(argv)

    while True:
        pulse = sys.stdin.readline()
        if not pulse:
            return 0
        # `flush=True` IS THE TICK. Measured, and it is the whole reason
        # TestStreaming runs a real process: stdout to a pipe is
        # BLOCK-buffered, not line-buffered, so without this the decorated
        # lines sit in an 8KB buffer while the coordinator waits. At ~300
        # bytes a tick that is roughly 27 ticks — over two hours of silence
        # from the loop's only wake channel, ending in a burst. Dropping it
        # makes that test hang rather than fail, which is what it looked like
        # when this was red-proved.
        #
        # `readline()` rather than `for pulse in sys.stdin` is NOT part of that
        # contract, and the comment here used to claim it was. Red-proving the
        # claim refuted it: iteration was swapped in and every streaming test
        # still passed, because TextIOWrapper iteration calls readline() and
        # the read-ahead this warned about is a Python 2 behaviour. The form is
        # kept only for the explicit EOF branch; nothing depends on it.
        print(decorate(pulse.rstrip("\n"), args.target), flush=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
