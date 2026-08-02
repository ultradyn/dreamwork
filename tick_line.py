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
reader may believe they are already following. "lanes 0 live [] · delegation
5" is a measurement that contradicts them. The second clause of his sentence —
*"no agents running but plenty of work waiting"* — is the load-bearing half, so
the counts are not decoration here, they are the point.

The live count names its OS-probe coverage because an empty result from a
detector that examined nothing is not an empty fleet.

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
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import status_sync
import lane_liveness
import watch
from dreamwork_db import Access, open_database
from dreamwork_db.tasks import task_store_spec
from ledger_parse import store_path

# The separator between the pulse and the facts, and between facts. Matches the
# ` · ` the ledger and hand-off rows already use for co-ordinate lists.
SEP = " · "

# The current goal's title is elided to a HARD 48 characters (#862 design call
# 2). He writes real acceptance criteria into the title, so it WILL be long,
# and #612 is the failure being designed around: a long field pushing the fleet
# count off the read. The elision is the feature, not a cosmetic. Beyond this
# width the title is cut to LIMIT-1 and an ellipsis is appended, so the quoted
# content is at most exactly LIMIT characters in every case.
GOAL_TITLE_LIMIT = 48


def _resident_sources_sha() -> str:
    """First 8 hex of sha256 over the source bytes of every LOCAL module that
    is resident in this process, read once at import (#840, option 3).

    LOCAL = a module whose ``__file__`` lives under this repo tree (same root
    as tick_line.py), so stdlib and third-party packages are excluded. By the
    time this runs — at the end of tick_line's import — ``sys.modules`` already
    holds the whole resident closure: status_sync, watch, ledger_parse,
    client_dist, and the ``dreamwork_db`` / ``user_events`` packages they pull
    in. So the hash MOVES when any of them changes. A stamp of tick_line alone
    would read "unchanged" while a status_sync edit moved the output — the
    partial-stamp form of the partial-watch trap that made #821's fix look like
    a no-op while the filter kept serving it.

    Read at IMPORT (this call binds ``RESIDENT_SHA`` once); never at print. The
    stamp must name the code that is RESIDENT, so a long-lived filter that has
    gone stale prints its OLD sha and the staleness is VISIBLE rather than
    silent. Re-reading at print time would print the NEW sha while running OLD
    code — the exact inversion of the bug, and a worse lie than no stamp. The
    per-tick child (below) makes this moot in the live pipeline: a fresh
    interpreter's resident bytes ARE the current disk bytes, so the stamp is
    honest there for the trivial reason that nothing has had time to go stale.
    """
    prefix = os.path.dirname(os.path.abspath(__file__)) + os.sep
    files = set()
    for mod in sys.modules.values():
        f = getattr(mod, "__file__", None)
        if not f:
            continue
        try:
            af = os.path.abspath(f)
        except (OSError, ValueError):
            continue
        if af.startswith(prefix):
            files.add(af)
    h = hashlib.sha256()
    for f in sorted(files):
        try:
            with open(f, "rb") as fh:
                h.update(fh.read())
        except OSError:
            continue
    return h.hexdigest()[:8]


RESIDENT_SHA = _resident_sources_sha()


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


def _fleet_fact(target: str) -> str:
    """Live lane names from the canonical lock/process identity detector.

    The old line repeated ``status.json['lanes']`` and then probed only the
    recorded ``dreamers``. Both can be stale. A lane lock binds a registered
    worktree to the runner pid through :mod:`lane_liveness`; both set-difference
    directions are reported, and zero candidates is an instrument failure.
    """
    if not (Path(target) / ".dreamwork").is_dir():
        raise status_sync.LivenessUnknown("target has no .dreamwork directory")
    inspection = lane_liveness.inspect_lanes(Path(target))
    fact = "lanes %d live [%s] (probe examined %d processes)" % (
        len(inspection.live), ", ".join(inspection.live),
        inspection.examined_processes)
    if inspection.worktree_only:
        fact += " · worktree-only %d [%s]" % (
            len(inspection.worktree_only), ", ".join(inspection.worktree_only))
    if inspection.process_only:
        fact += " · process-only %d [%s]" % (
            len(inspection.process_only), ", ".join(inspection.process_only))
    return fact


def _goal_fact(target: str) -> str:
    """The current goal as a HANDLE: id, elided title, progress — nothing else.

    Design call 2 of the #862 goal tree puts this in the trailing slot (the one
    _stamp_fact's docstring reserves for things that must not push the fleet
    count out of view), AFTER the fleet/delegation pair because that adjacency
    is the contradiction #673 exists to surface. #612 is the failure being
    designed around: a long field pushing the fleet count off the read. The
    goal title WILL be long, because he writes real acceptance criteria into
    it — so the title is elided to a HARD GOAL_TITLE_LIMIT characters and that
    elision is the feature, not a cosmetic.

    NO DETAILS, EVER (#862). The loop reads details from the store when it
    selects work, once per tick at most; that is the whole reason the line
    stays a handle. progress() supplies the ratio; the id and title supply the
    identity. The id carries a ``G`` prefix so a goal number is never read as a
    task number on the same line.

    Degrade-to-zero — the shape that bit six times tonight (#868/#875/#883/
    #867/#886/#888): "no goal is set" and "the goal store did not answer" must
    not render the same. This mirrors _open_fact, which returns OPEN UNKNOWN
    rather than 0 because "an unreadable ledger and an empty one look
    identical to a parser":

      - the store answered and the pointer is empty -> "no current goal
        (<N> goals defined)" (lowercase, no capitals: a genuine, measured
        state, not a fault);
      - the store exists but would not answer (unreadable, pre-v008, or a
        pointer to a row that is missing or not a goal) -> GOAL UNKNOWN
        (<reason>) in capitals, which in this file always means "a number here
        is missing";
      - no store file at all (markdown-mode target) -> "no current goal": the
        goal system is absent, not a broken store claiming an answer it never
        gave. source_of_truth agrees: an absent store reads as markdown.
    """
    dw = Path(target) / ".dreamwork"
    db = store_path(dw)
    if not db.exists():
        return "no current goal"
    try:
        with open_database(task_store_spec(db), access=Access.READ) as store:
            goal_id = store.goals.current_goal_id()
            if goal_id is None:
                goal_count = sum(
                    group.kind == "goal" for group in store.groups.list())
                return "no current goal (%d goal%s defined)" % (
                    goal_count, "" if goal_count == 1 else "s")
            title = store.groups.get(goal_id).title
            progress = store.groups.progress(goal_id)
    except Exception as exc:                                  # noqa: BLE001
        return "GOAL UNKNOWN (%s: %s)" % (exc.__class__.__name__, exc)
    shown = (title if len(title) <= GOAL_TITLE_LIMIT
             else title[:GOAL_TITLE_LIMIT - 1] + "\u2026")
    return 'goal #G%d "%s" %d/%d' % (
        goal_id, shown, progress.completed_count, progress.total_count)


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


def _stamp_fact() -> str:
    """Which code produced this line — the resident sha, not the disk sha.

    Trailing the line on purpose: it is provenance, never a number acted on,
    so it sits where nothing can push the fleet count out of view (#612). A
    reader who suspects the filter is stale compares this to a direct call's
    stamp; a mismatch is the legible sign that was MISSING when #821/#837
    served hours-old code with no indication.
    """
    return "src %s" % RESIDENT_SHA


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
    ] + posture_parts + [_guarded(lambda: _goal_fact(target), "goal"),
                         _stamp_fact()])


def decorate(pulse: str, target: str) -> str:
    """One heartbeat line in, one decorated line out."""
    return pulse + SEP + facts(target)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="tick_line.py",
        description="Append the live posture and fleet to each heartbeat pulse.")
    ap.add_argument("--target", default=".", help="target project directory")
    # Internal: the parent loop spawns this image per pulse (--one-shot) so
    # every tick runs the code currently on disk. Suppressed from --help.
    ap.add_argument("--one-shot", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--pulse", default="", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    if args.one_shot:
        # CHILD PATH — one decoration in a FRESH interpreter, then exit. The
        # parent spawns this per pulse, so the facts always reflect the code on
        # disk for tick_line AND every module it imports. A streaming filter
        # holds its imports for the process lifetime, which is exactly why an
        # edit to tick_line.py (or status_sync, or watch) was inert until the
        # monitor was re-armed — #821 served 20h08m of pre-merge code, #837
        # kept doubling lanes after the dedupe landed. A fresh interpreter per
        # tick has no resident set to go stale (#840, option 2: correct by
        # construction — no mtime watch, no source list to forget).
        sys.stdout.write(decorate(args.pulse, args.target) + "\n")
        return 0

    # PARENT PATH — the long-lived pipe filter. heartbeat stays the only
    # scheduler; this reads its pulses and hands each one to a fresh child.
    # The pulse passes through UNCONDITIONALLY (#655): a child failure degrades
    # the facts to a loud UNRESOLVED, it never costs the loop its wake.
    self = os.path.abspath(__file__)
    while True:
        pulse = sys.stdin.readline()
        if not pulse:
            return 0
        pulse = pulse.rstrip("\n")
        result = subprocess.run(
            [sys.executable, self, "--one-shot", "--target", args.target,
             "--pulse", pulse],
            capture_output=True, text=True)
        if result.returncode == 0:
            sys.stdout.write(result.stdout)
        else:
            sys.stdout.write(pulse + SEP + _unresolved(
                "tick child", ChildProcessError(
                    "exit %d%s" % (result.returncode,
                                   ": " + result.stderr.strip().splitlines()[-1][:100]
                                   if result.stderr.strip() else ""))) + "\n")
        # `flush` IS THE TICK. Measured: stdout to a pipe is BLOCK-buffered,
        # not line-buffered, so without this the decorated lines sit in an 8KB
        # buffer while the coordinator waits — ~27 ticks, over two hours of
        # silence from the loop's only wake channel, ending in a burst. The
        # per-tick child does not change this: the child writes to a pipe the
        # parent captures, and it is the PARENT's stdout the reader is on.
        sys.stdout.flush()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
