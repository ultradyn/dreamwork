#!/usr/bin/env python3
"""Recompute the derived halves of `.dreamwork/status.json` from their sources.

Why this exists rather than a resolution to be careful: the queue count lives
in two files, and every tick that moved a task left them disagreeing until
`lint.py` complained. A coordinator fixed that by hand six times in one
session, and a coordinator also let `current_task_ids` name three tasks that
had closed hours earlier — both render on the dashboard, and `status.json` has
exactly one writer, so it is the one file in the system with no reviewer
(#394's neighbour, recorded in `lessons.md`).

The lesson it implements is *"any figure that recurs gets exactly one place
that holds it"*. The ledger is that place for the open count; the OS process
table is that place for which lanes are live. Neither is memory.

Derived here, and nothing else is touched:

  queue.in_progress / queue.pending   from the ledger's `## Open` section,
                                      counting **every id** — a combined head
                                      `- **#7/#8**` is two ids in one entry
                                      (`file-formats.md`), which is the
                                      distinction that made three independent
                                      hand-counts agree and all be wrong.
  current_task_ids                    the tasks whose dispatched process is
                                      still alive (see `live_lanes`).
  dreamers                            pruned of lanes whose process is gone
                                      OR whose task has landed — a dead or
                                      finished lane leaves the array; nothing
                                      else about the survivors changes. Task
                                      ids are normalised on write (plain → int,
                                      sub-id → str), and malformed entries are
                                      skipped + reported rather than crashing.
                                      A lane dispatched a form the probe cannot
                                      see (`spawn_subagent`, not the `ccc`
                                      default) is kept verbatim — the probe is
                                      blind to it, so it must not prune it; a
                                      landed task still reaps it (#537).
  agent_session                       from the invoking main agent's measured
                                      client environment, accepted only when
                                      its UUID resolves to a live transcript.
                                      This is evaluated only when the target
                                      is the invocation cwd, so a lane syncing
                                      some other checkout cannot overwrite the
                                      main agent's identity.

Everything a human or coordinator wrote by judgement is left alone: notes,
owed_verifications, queued_dispatches, deployed, monitors, session_goal, and
every other key the file happens to carry (listed on every run — see
`coverage`).

Usage:  python3 status_sync.py [--target DIR] [--check]

`--check` exits 1 without writing if anything was stale, so it can be run
before a commit; the default rewrites and prints what changed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

40# #331: the ids-only bold span has ONE definition, in watch.py. Consume it
# here rather than restating it — this was the third unpinned copy of the
# rule, and it matched the other two only by luck. The head form is pinned
# identical to watch.LEDGER_ENTRY and lint.LEDGER_ID by a test.
import watch

# A ledger entry head names one or more ids in a single bold span.
LEDGER_HEAD = re.compile(rf"^- \*\*({watch.IDS_ONLY_SPAN})\*\*", re.M)
# #352: ENTRY_ID was a third hand-written copy of `#(\d+)`; the grammar's
# one home is ledger_parse now.
from ledger_parse import ENTRY_ID  # noqa: E402
from ledger_parse import source_of_truth, store_ids_by_state  # noqa: E402
import lane_liveness  # noqa: E402
import lane_runner_identity  # noqa: E402
from worktree_paths import WORKTREE_DIR  # noqa: E402
from worktree_paths import worktree_roots as _canonical_worktree_roots  # noqa: E402


# The top-level keys this tool owns. Everything else in status.json is
# left to its author, and `coverage` says so on every run by subtracting this
# tuple from the file's actual keys — so a field added next month shows up in
# the untouched list without anyone remembering to extend a literal.
DERIVED = ("queue", "current_task_ids", "dreamers", "agent_session")


def open_ids(ledger: str) -> list[int]:
    """Every id under `## Open`, combined heads expanded.

    Splitting on the literal heading is the same contract `watch.py` and
    `lint.py` read by; a file missing `## Open` parses to nothing, which is
    why the caller asserts the result is non-empty rather than trusting it.
    """
    sections = re.split(r"^## ", ledger, flags=re.M)
    for sec in sections:
        if sec.startswith("Open"):
            return [int(i) for head in LEDGER_HEAD.findall(sec)
                    for i in ENTRY_ID.findall(head)]
    return []


def read_task_ids_by_state(dw, lpath) -> tuple[list[int], list[int]]:
    """``(open, landed)`` ids from one authoritative ledger read."""
    if source_of_truth(str(dw)) == "store":
        open_strs, landed_strs = store_ids_by_state(str(dw))
        return ([int(i) for i in open_strs],
                [int(i) for i in landed_strs])
    ledger = lpath.read_text()
    # Keep the existing open parser here because, unlike the set-valued
    # dashboard parser, it preserves duplicates for main's refusal gate.
    _, landed_strs = watch.parse_ledger(ledger)
    return open_ids(ledger), [int(i) for i in landed_strs]


def task_states(open_task_ids: list[int],
                landed_task_ids: list[int]) -> dict[int, str]:
    return ({i: "open" for i in open_task_ids}
            | {i: "landed" for i in landed_task_ids})


def audit_queued_dispatches(status: dict, states: dict[int, str]) -> None:
    """Report ledger contradictions in structural queue ids; never edit."""
    entries = status.get("queued_dispatches", [])
    if not isinstance(entries, list):
        print("WARN queued_dispatches: expected a list; unclassifiable value=%s"
              % json.dumps(entries, ensure_ascii=False), file=sys.stderr)
        print("queued_dispatches: checked 0 entries, 0 id references; "
              "0 state questions, 1 unclassifiable")
        return

    references = questions = unclassifiable = 0
    for entry in entries:
        quoted = json.dumps(entry, ensure_ascii=False)
        if isinstance(entry, str):
            unclassifiable += 1
            print("WARN queued_dispatches: legacy text entry; unmigrated "
                  "entry=%s" % quoted, file=sys.stderr)
            continue
        if not isinstance(entry, dict):
            unclassifiable += 1
            print("WARN queued_dispatches: expected an object; unclassifiable "
                  "entry=%s" % quoted, file=sys.stderr)
            continue
        if "ids" not in entry:
            unclassifiable += 1
            print("WARN queued_dispatches: no ids key; unclassifiable entry=%s"
                  % quoted, file=sys.stderr)
            continue
        ids = entry["ids"]
        if (not isinstance(ids, list)
                or not ids
                or any(type(task_id) is not int or task_id <= 0
                       for task_id in ids)):
            unclassifiable += 1
            print("WARN queued_dispatches: ids must be a non-empty list of "
                  "positive integers; unclassifiable entry=%s" % quoted,
                  file=sys.stderr)
            continue
        references += len(ids)
        # The prose is deliberately opaque. It may cite any #NNN without
        # making that task a queued subject; only this structural list claims.
        for task_id in ids:
            state = states.get(task_id)
            if state == "open":
                continue
            questions += 1
            if state == "landed":
                fact = "is landed"
            else:
                fact = "is not present in the ledger (retired or non-existent)"
            print("WARN queued_dispatches: #%d %s; entry=%s; entry left "
                  "unchanged — ledger state is a question, not a verdict"
                  % (task_id, fact, quoted), file=sys.stderr)

    print("queued_dispatches: checked %d entr%s, %d id reference%s; "
          "%d state question%s, %d unclassifiable"
          % (len(entries), "y" if len(entries) == 1 else "ies",
             references, "" if references == 1 else "s",
             questions, "" if questions == 1 else "s", unclassifiable))


LivenessUnknown = lane_liveness.LivenessUnknown


def _argv_listing() -> str:
    """Every live process's full argv, one `pid argv` line per process.

    The match is order-independent: the lane is found by its brief path
    *wherever that path appears* in argv, so a flag sitting between the
    binary and the alias (`ccc --yolo @glm52 …/brief.md`) does not hide it.
    That is the bug `^ccc @` had — it meant "no flags between the binary and
    the alias", matched nothing once dispatch became `ccc --yolo @glm52`, and
    `live` came back `[]` while lanes were running.

    `ccc` is unanchored and deliberately broad; the per-lane test is the
    brief-path substring, which is specific, so a broad listing cannot
    manufacture a false lane. Raises `OSError` if the listing cannot be read
    (pgrep missing, etc.).
    """
    return subprocess.run(
        ["pgrep", "-af", "ccc"], capture_output=True, text=True).stdout


def _pid_alive(pid) -> bool:
    """`kill -0` on the recorded dispatch pid.

    Measured (#402a): a live `ccc --yolo @glm52 …` process keeps its pid AND
    its argv for the lane's whole life — the dispatch pid is the survivor, not
    a dead wrapper. A controlled `exec`-in-place showed the two signals have
    opposite failure modes: after `exec`, `kill -0` still succeeds (the pid is
    kept) but the brief path vanishes from argv. So the pid is the exact
    signal and the brief path is the fallback; the old docstring's reasoning
    ("use the brief path, the wrapper pid dies") was backwards. Returns False
    on a clean "no such process" (a dead lane); raises `LivenessUnknown` on
    anything we cannot interpret, because that is not "dead".
    """
    return lane_liveness.pid_alive(pid)


def _pid_matches_lane(pid, brief) -> bool:
    """Whether ``pid`` is alive *and* still carries ``brief``'s lane identity.

    A bare pid is not identity: after reuse, ``kill -0`` succeeds for an
    unrelated process.  Agent-tool lanes keep their worktree as cwd; ccc
    runners deliberately exec from the main checkout, so their controlled
    argv carries the worktree path instead (#775).  Either binding is exact
    to this pid; a global process-list match would merely move the reuse race.
    """
    return lane_liveness.pid_matches_lane(
        pid, brief, is_pid_alive=_pid_alive, proc_cwd=_read_proc_cwd
    )


def live_lanes(dreamers: list[dict]) -> tuple[set, list[dict]]:
    """Return `(live_tasks, pruned_dreamers)`; raise `LivenessUnknown`.

    A lane is live when its recorded dispatch process is still running. The
    **pid is exact** (`kill -0`); the **brief path** is the order-independent
    fallback for lanes recorded without a pid. A lane whose signal says "gone"
    is dropped from `pruned`; a live lane is kept verbatim — nothing else
    about the entry changes.

    If liveness cannot be determined for any lane (the argv listing fails, a
    pid cannot be signalled for reasons other than "gone", or a lane carries
    neither pid nor brief), this raises rather than returning a guess — the
    caller must not write a value it could not derive.
    """
    need_listing = any(_missing_pid(d) for d in dreamers)
    ps = ""
    if dreamers and need_listing:
        try:
            ps = _argv_listing()
        except OSError as e:
            raise LivenessUnknown("process listing failed: %s" % e)

    live: set = set()
    pruned: list[dict] = []
    for d in dreamers:
        pid = d.get("pid")
        brief = d.get("brief")
        if not _missing_pid(d):
            is_live = _pid_matches_lane(pid, brief)
        elif brief:
            is_live = brief in ps
        else:
            # No pid and no brief: there is nothing to ask the OS about, so a
            # derived answer here would be a guess dressed as a measurement.
            raise LivenessUnknown("lane has neither pid nor brief: %r" % (d,))
        if is_live:
            live.add(d["task"])
            pruned.append(d)
    return live, pruned


def _missing_pid(d: dict) -> bool:
    pid = d.get("pid")
    return pid is None or pid == "" or pid == 0


# #537: dispatch forms the liveness probe can OBSERVE. `ccc` is seen by
# `pgrep -af ccc` (the argv fallback) and `kill -0` on a dispatch pid that is
# a `ccc` process. `agent_tool` (#675) is a non-`ccc` process discovered by
# `discover_lanes` walking `/proc/*/cwd` — it has a pid the probe CAN reach
# with `kill -0`, so it is observable by pid even though the argv listing
# (pgrep ccc) never lists it. A lane dispatched any other way — the harness's
# native `spawn_subagent`, an independent clone with no process in the
# worktree and no probe-able pid — is UNOBSERVABLE: neither signal can reach
# it. An observation blind to a form must never clobber records of that form
# — a live fleet of spawn_subagent lanes was once pruned to 0 by this tool
# because the probe could not see them. An entry whose `dispatch` is absent
# is the historical `ccc` default (observable), so every pre-#537 entry stays
# evaluable; any value not listed here is carried verbatim through the
# liveness step and reaped only by the ledger (a landed task is observable
# regardless of dispatch form).
OBSERVABLE_DISPATCH = ("ccc", "agent_tool")


def _observable(d: dict) -> bool:
    """Whether the liveness probe can evaluate this entry's dispatch form.

    Absent ``dispatch`` is the ``ccc`` default (observable); a ``dispatch``
    not in :data:`OBSERVABLE_DISPATCH` is unobservable and is carried verbatim
    through the liveness step rather than pruned by a probe blind to it (#537).
    """
    via = d.get("dispatch")
    return via is None or via in OBSERVABLE_DISPATCH


# #716: lanes the liveness probe (kill -0 / pgrep) cannot see are pruned to 0
# while they run — the probe sees only the `ccc` dispatch path, and the field
# it derives (`dreamers`) is advertised as `coverage: derived` but only ever
# SUBTRACTED. Discovery is the missing ADD: a `ccc` lane's cwd is its worktree
# (new sibling or draining in-repo `.worktrees/<lane>`), so `readlink`
# `/proc/<pid>/cwd` recovers it. The pid a
# lane is recorded under is the `ccc` process itself (measured: cmdline begins
# `ccc -y @glm52 …`, and its ppid is the zsh wrapper — both share the worktree
# as cwd, so the probe is indifferent to which is recorded; #402a already
# settled the recorded pid as the survivor). A lane whose cwd the probe can
# read but cannot classify is REPORTED, never silently dropped and never
# silently added — the mirror of #702's "cannot compare must not read as
# landed" applied to discovery rather than reap.
def worktree_roots(target: Path) -> tuple[str, str]:
    """New-worktree root first, then the draining in-repo root (#846)."""
    return tuple(str(path) for path in _canonical_worktree_roots(target))


def _lane_worktree_path(target: Path, lane: str, pid: int) -> Path:
    """The actual root/path carrying a discovered lane (#846)."""
    roots = worktree_roots(target)
    cwd = _read_proc_cwd(pid)
    for root in roots:
        path = Path(root) / lane
        if cwd == str(path) or (cwd and cwd.startswith(str(path) + os.sep)):
            return path
    for root in roots:
        if _argv_lane(pid, root) == lane:
            return Path(root) / lane
    for root in roots:
        path = Path(root) / lane
        if path.is_dir():
            return path
    return Path(roots[0]) / lane


def _read_proc_cwd(pid: int) -> str | None:
    """`readlink /proc/<pid>/cwd`, or None if unreadable (gone / no perm)."""
    return lane_liveness.read_proc_cwd(pid)


def _argv_lane(pid: int, wt_root: str) -> str | None:
    """The lane name a process's argv carries under ``wt_root``, or None.

    #775: a live ``ccc`` lane's cwd is the MAIN checkout (``os.execvp`` runs
    the runner there), not its worktree — so the cwd-walk in
    :func:`discover_lanes` cannot see it, and the fleet read ``0 live`` while
    lanes ran. But the dispatch route APPENDS the lane's brief as the last
    argv element (``dispatch_lane.py:322``:
    ``os.execvp(runner[0], [*runner, prompt])``), and that brief embeds
    ``Worktree: <abs>/.worktrees/<lane>`` — a path under ``wt_root`` that the
    process carries for its whole life regardless of which runner binary
    later ``exec``s in (#775: the matcher must NOT key on the runner name,
    because ``ccc`` execs away to ``codex-code-mode-host`` / the grok harness;
    the worktree path in argv is the one invariant the dispatch route controls).

    Reads the raw cmdline bytes through :mod:`lane_liveness`'s exact governed
    ``Worktree:``-line grammar. Incidental worktree paths elsewhere in a brief
    are prose, not identity. Returns ``None`` when exactly one governed line
    does not resolve under ``wt_root``.
    """
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            raw = f.read()
    except OSError:
        return None
    if not raw:
        return None
    path = lane_liveness._prompt_worktree(raw, (Path(wt_root).resolve(),))
    return path.name if path is not None else None


def _is_ccc_proc(pid: int) -> bool:
    """Whether ``pid``'s argv[0] basename is a dispatch runner (ccc today).

    Avoids over-counting: a worktree cwd is also held by the zsh wrapper, an
    editor, or a pytest a coordinator ran from a worktree (#716 dir-2). Only
    a dispatch runner is a dispatched lane, so the argv check keeps discovery
    to the one form the liveness probe already reasons about (#675). Reads
    raw bytes then delegates to ``lane_runner_identity.is_dispatch_runner``
    (DISPATCH_RUNNERS) — the classifier lives beside LANE_RUNNERS in the
    shared identity module (#1130), so a reader extending either concept
    sees the other.
    """
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            raw = f.read()
    except OSError:
        return False
    return lane_runner_identity.is_dispatch_runner(raw)


def _ccc_model(pid: int) -> str | None:
    """The model alias a `ccc` lane is running, from argv ELEMENTS (#720).

    A discovered lane's pid has no recorded model, so the dashboard showed
    a blank for lanes the tool found and a value for lanes a coordinator
    typed — the same kind of lane rendered as two kinds. The model IS in the
    same `/proc` read discovery already does: argv[1:3] carries ``cc`` for
    the Opus form (``ccc cc -y +high``) versus ``@<alias>`` for the cheap
    form (``ccc -y @glm52``).

    Reads argv ELEMENTS — never a substring of the raw cmdline. ``/proc``'s
    cmdline is NUL-separated, so a substring test for ``" cc "`` never matches
    and every lane silently reads as the default model (#716 recorded this
    exact trap). The check spans argv[1:3] so a flag sitting between the
    binary and the alias (``-y`` in both forms today) does not hide it.
    Returns ``None`` when the alias is unrecognised — the lane IS classified
    (it is a live ``ccc`` lane under ``.worktrees/``); the model is an
    attribute, not a classification, so #702's "must report" (inherited by
    #719's phantom: a lane the tool CANNOT classify) does not reach it.
    """
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            raw = f.read()
    except OSError:
        return None
    if not raw:
        return None
    args = [a.decode("utf-8", "replace") for a in raw.split(b"\x00") if a]
    early = args[1:3]                           # argv[1] and argv[2]
    if "cc" in early:                           # ccc cc -y +high (opus)
        return "ccc cc +high (opus)"
    aliases = [a for a in early if a.startswith("@")]
    if aliases:                                 # ccc -y @glm52
        return "ccc " + aliases[0]
    return None


# #729: known lane runners — the positive-identity test for the phantom
# split, copying reaper.parse_cmdline's SHAPE (a basename check, not a cwd
# prefix match). A process whose argv[0] is one of these is a lane runner; a
# head/grep/tail/bash sharing the prefix is NOT, however deleted its cwd. The
# pairing of "known runner" with "deleted worktree cwd" is what makes the
# reaper safe where it has kill authority, and it is what separates a genuine
# leftover from shell noise in the phantom report. THE single source is
# lane_runner_identity — both fleet probes read it, so a name added there is
# seen by the tick and status at once (#1113: the #868/#1084 "the fleet count
# lied" defect class was two copies drifting). Re-exported here for readers
# that still name status_sync._LANE_RUNNERS.
_LANE_RUNNERS = lane_runner_identity.LANE_RUNNERS


def _is_lane_runner(pid: int) -> bool:
    """Whether ``pid``'s argv[0] basename is a known lane runner (#440, #671).

    A thin I/O wrapper: read /proc/<pid>/cmdline, then delegate the basename
    classification to ``lane_runner_identity.is_lane_runner`` — the ONE
    classifier, shared with the tick line's cwd channel (#1113). This module
    works with pids (it has a pid from /proc enumeration); the shared
    classifier takes raw bytes (the tick channel already read them). A future
    basename normalisation lands in the shared function and is seen by both
    probes at once. This is the positive test the old "ccc process mid-exit"
    label CLAIMED but never performed (#671: a label asserting a check that
    was not done).
    """
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            raw = f.read()
    except OSError:
        return False
    return lane_runner_identity.is_lane_runner(raw)


# The ancestor-self exclusion (#729) is shared from lane_runner_identity — the
# single source — so this probe and the tick line agree on what is "self", not
# a phantom, exactly as they agree on what is a runner (#1113). Re-exported
# under the private name this module's callers and tests already use.
_ancestor_pids = lane_runner_identity.ancestor_pids


def discover_lanes(target: Path, *, stats: dict | None = None):
    """Live lanes the cwd probe can see, as ``(found, phantoms, agent_tool)``.

    Walks ``/proc/*/cwd`` for paths under both ``<target>/../.worktrees/`` and
    the draining ``<target>/.worktrees/`` (#716/#846), and ALSO scans each
    process's argv for both prefixes (#775). The cwd
    walk is the primary channel; the argv walk is the recovery channel for
    the case that bit: a live ``ccc`` lane's cwd is the MAIN checkout
    (``os.execvp`` runs the runner there, not in the worktree), so a
    cwd-only walk read ``0 live`` while lanes ran. The dispatch route
    appends the brief as the last argv element, and the brief embeds
    ``Worktree: <abs>/.worktrees/<lane>`` — a path the process carries for
    its whole life regardless of which runner binary later ``exec``s in.
    Matching that path (not the runner name) is the fix; the worktree path
    in argv is the one invariant the dispatch route controls.
    ``found`` is the list of live ``ccc`` lanes (as ``(lane, pid, model)``
    triples — #720 derives the model from the same ``/proc`` read) a caller
    MERGES with coordinator-authored entries. ``phantoms`` (#719) is a
    ``ccc`` or non-ccc process whose worktree has been REMOVED (cwd-discovered:
    readlink carries " (deleted)"; argv-discovered: the reconstructed
    worktree path is gone). ``agent_tool`` (#675) is a
    non-``ccc`` process with a lane cwd/argv — an Agent-tool lane's shape,
    merged into ``dreamers`` so ``current_task_ids`` does not degrade to 0
    while Agent-tool lanes run. A lane running somewhere neither channel can
    see (another machine, a harness that strips argv) is carried verbatim
    rather than erased by a narrower automatic view (#537).

    ``target`` is the project root. It is RESOLVED before building the sibling
    and draining worktree roots (#720): the default
    ``--target="."`` produced ``"./.worktrees"``, tested with ``startswith``
    against the ABSOLUTE path ``readlink`` returns — it never matched, so
    discovery was INERT under the invocation the loop actually uses.
    ``resolve()`` (not ``realpath``: #425's symlink contract; not
    ``abspath``: this repo is reached through ``~/.claude-p/skills/…`` while
    lane cwds carry ``~/.llm-general/skills/…``, and ``abspath`` keeps the
    symlink while ``resolve()`` normalises to the real path the cwds share).
    """
    wt_roots = worktree_roots(target)
    found = []
    phantoms = []
    # #675: a non-ccc process whose cwd is a lane worktree is an Agent-tool
    # lane's shape — the harness runs it with no `ccc` in argv, so the
    # liveness probe (`_is_ccc_proc`) is blind to it. The cwd-walk discovery
    # already does CATCHES it, then drops it at the `_is_ccc_proc` gate. We
    # collect those separately as `agent_tool`: merged into `dreamers` (so
    # `current_task_ids` no longer degrades to 0 while Agent-tool lanes run —
    # the drift alarm Max asked the loop to watch for) and REPORTED on stderr
    # (so their runner is visible, never silently mixed with ccc). A process
    # the probe cannot classify is carried, never silently dropped (#702).
    agent_tool = []
    seen_lanes = set()
    seen_rank = {}
    process_candidates = 0
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        process_candidates += 1
        pid = int(entry)
        cwd = _read_proc_cwd(pid)
        cwd_root = next((root for root in wt_roots
                         if cwd is not None and cwd.startswith(root + "/")), None)
        cwd_lane = (cwd_root is not None
                    and os.path.basename(cwd.rstrip("/")))
        # #775: a live ccc lane's cwd is the MAIN checkout (os.execvp runs
        # the runner there), so the cwd-walk above misses it. The dispatch
        # route APPENDS the brief as the last argv element, and that brief
        # embeds ``Worktree: <abs>/.worktrees/<lane>`` — a path the process
        # carries for its whole life. Recover the lane from argv when cwd is
        # elsewhere. This is the ONE invariant the dispatch route controls:
        # matching the runner binary name (ccc/codex/grok) would repeat the
        # bug one level down (a new runner is added, nothing matches, the
        # fleet silently reads zero again). The worktree path in argv is
        # controlled by dispatch_lane.py and survives the exec chain.
        argv_root = None
        argv_lane = None
        if not cwd_lane:
            for root in wt_roots:
                argv_lane = _argv_lane(pid, root)
                if argv_lane:
                    argv_root = root
                    break
        lane = cwd_lane or argv_lane
        if not lane or lane == target.name:
            continue
        # The worktree path to existence-check. A cwd-discovered lane's
        # worktree IS its cwd (readlink, possibly " (deleted)"); an
        # argv-discovered lane's worktree is reconstructed from wt_root +
        # the lane name (its cwd is elsewhere, so cwd existence says
        # nothing about whether the worktree still exists).
        wt_path = cwd if cwd_lane else argv_root + "/" + lane
        # #719: a lane whose worktree has been removed is a phantom.
        # readlink still resolves (Linux appends " (deleted)"), the prefix
        # filter still passes, but the cwd is no longer a directory — the
        # process is exiting, not working. Excluded and REPORTED, not
        # silently dropped (#702, inherited by #716's discovery). Applies to
        # both ccc and non-ccc: a deleted-cwd process is exiting regardless.
        # For an argv-discovered lane the worktree dir is checked directly
        # (wt_path is the reconstructed path, not a readlink result, so the
        # " (deleted)" suffix never appears — isdir is the plain truth).
        if not os.path.isdir(wt_path):
            phantoms.append((lane, pid))
            continue
        # The drain is a SET union by lane identity. Two processes (or even
        # two roots carrying the same basename) must not double-count a lane.
        candidate = Path(wt_path)
        rank = next((i for i, root in enumerate(wt_roots)
                     if candidate == Path(root) / lane), len(wt_roots))
        if lane in seen_lanes:
            if rank >= seen_rank[lane]:
                continue
            found = [row for row in found if row[0] != lane]
            agent_tool = [row for row in agent_tool if row[0] != lane]
            seen_lanes.remove(lane)
        if _is_ccc_proc(pid):
            found.append((lane, pid, _ccc_model(pid)))
            seen_lanes.add(lane)
            seen_rank[lane] = rank
        else:
            # #675: a non-ccc process in a lane worktree. An editor, a shell,
            # or this tool's own grep could share the cwd — so this is a
            # wider net than the ccc check, and it is MERGED into the live
            # set knowing it over-counts (#675's stated cost). The over-count
            # is the lesser evil against the ZERO it replaces: zero is the
            # one value that means "nothing is running" and the drift alarm;
            # an over-count by one transient process is self-correcting on
            # the next tick (the process exits and is gone). Dedup by lane:
            # a ccc lane and its grok child share the cwd, so the ccc arm
            # (above) claims the lane and the child falls through here — the
            # `seen_lanes` check drops the duplicate so the lane counts once.
            if lane not in seen_lanes:
                agent_tool.append((lane, pid))
                seen_lanes.add(lane)
                seen_rank[lane] = rank
    # Stable order by lane name so the merge and the stderr report are
    # deterministic across runs reading the same process table.
    if stats is not None:
        # #821: an empty result is trustworthy only when the detector really
        # examined a plausible process population.  The tick line publishes
        # this count, so an inert /proc walk cannot impersonate "no lanes".
        stats["process_candidates"] = process_candidates
    return (sorted(found, key=lambda lpm: lpm[0]),
            sorted(phantoms, key=lambda lp: lp[0]),
            sorted(agent_tool, key=lambda lp: lp[0]))


def live_lane_count(target: Path) -> int:
    """The ccc lane count — the one supported accessor over ``discover_lanes`` (#440).

    Callers that need only the count call THIS, never a positional unpack
    of ``discover_lanes``: #728 made a 2-tuple unpack a silent 2am gate
    failure when #675 grew the return to three. Pinning the unpack in this
    one function means the next arity change breaks ONE line (this one)
    rather than every caller, and a test can pin it (#728). Raises
    ``OSError`` if ``/proc`` is unreadable (the caller decides whether that
    is a legitimate ``None``) and ``ValueError`` if ``discover_lanes``
    contract changes — the latter is a bug and must stay loud (#136).
    """
    found, _phantoms, _agent_tool = discover_lanes(target)
    return len(found)


def read_open_ids(dw, lpath):
    """Open ids under `## Open`, dispatching on source_of_truth (#294 inc 7).

    Returns ``list[int]`` — every id under Open, combined heads expanded.
    Store mode queries ``store_ids_by_state``; markdown mode parses the
    text. A missing store is fail-closed to markdown by ``source_of_truth``.
    """
    return read_task_ids_by_state(dw, lpath)[0]


def _evaluable(d) -> bool:
    """Whether an entry can be processed at all (#402a, #537).

    The syncer must never crash on a malformed entry: a sync that exits 1
    stops protecting everything after it. An entry is **evaluable** when it
    is a dict carrying a ``task``. For an OBSERVABLE dispatch form (#537:
    ``ccc``, the probe-able default) the entry also needs something to ask
    the OS about — a parseable pid or a brief path; an UNOBSERVABLE form
    (harness-native ``spawn_subagent``) needs only the task, because the
    probe cannot see it and the ledger alone reaps it. Entries that fail
    this are pre-filtered as junk in ``main`` and reported, never reaching
    ``live_lanes``.
    """
    if not isinstance(d, dict):
        return False
    if "task" not in d:
        return False
    if not _observable(d):
        return True                     # unobservable: no probe; ledger reaps
    if _missing_pid(d):
        return bool(d.get("brief"))
    try:                                # pid present — must be parseable
        int(d["pid"])
        return True
    except (TypeError, ValueError):
        return False


def _normalise_task(task):
    """Canonical id form: plain id → int, sub-id → str (#402b).

    **Tolerate on read, normalise on write** — the file is written by more
    than one hand (the coordinator at dispatch, the syncer at reap), so the
    syncer accepts int or str on read and writes back the canonical form.
    A plain numeric id (``172`` or ``"172"``) becomes an int; anything else
    (a sub-id like ``"392a"``, or an unparseable value) stays a string.
    """
    s = str(task)
    if s.isdigit():
        return int(s)
    return s


def _normalise_entry(d: dict) -> dict:
    """A shallow copy with ``task`` in canonical form (#402b)."""
    out = dict(d)
    if "task" in out:
        out["task"] = _normalise_task(out["task"])
    return out


def _entry_tag(d) -> str:
    """A short identifier for an entry in stderr reports, never raises."""
    if isinstance(d, dict):
        return repr(d.get("task", "<no task>"))
    return repr(d)


def _base_id(task) -> int | None:
    """The integer task a (possibly sub-) id refers to.

    `current_task_ids` can legitimately carry a sub-id like `392a` (a lane has
    been `#392a`); the unknown-lane check has to compare it against the open
    ledger by its *base* id (392), not by string equality against `[392]`.
    Returns None for an id with no leading digits.
    """
    m = re.match(r"\d+", str(task))
    return int(m.group()) if m else None


def _lane_task(lane: str, ids) -> int | str:
    """The task id a lane-named worktree is working, from its name (#716).

    A lane worktree is `lane-<id><slug>` (`lane-716fleet` → 716). The id is
    the leading digits after `lane-`. When that id is under `## Open` it is
    returned as an int (the canonical plain form, #402b); otherwise the slug
    is returned verbatim so the entry is carried but `_base_id`-comparable,
    matching the tolerate-on-read contract for a task the ledger comparison
    cannot reach. The slug is NOT guessed as the open id — discovery must not
    invent a task association the ledger does not confirm (#702: a claim the
    comparison cannot reach must not read as landed).
    """
    m = re.match(r"lane-(\d+)", str(lane))
    if not m:
        return lane
    base = int(m.group(1))
    return base if base in set(ids) else re.sub(r"^lane-", "", str(lane))


def _lane_entry_base_id(entry) -> int | None:
    """The task id a free-form ``lanes`` entry names, from its lane prefix.

    ``lanes`` entries are author-written dispatch notes whose text begins
    with the lane name (``cx-968foldsha — #968 P2: …``). A lane name is
    ``<dispatch>-<id><slug>`` (brief.py builds ``cx-{task}``; a slug may
    follow), so the leading digits after the first ``-`` are the task.
    Returns ``None`` for an entry the prefix cannot reach — matching
    ``_base_id``'s contract so *cannot compare* reads as *kept*, never as
    *landed* (#702/#136): a judgement string the tool cannot tie to a task
    is preserved, not pruned on a guess.
    """
    m = re.match(r"^[a-z]+-(\d+)", str(entry))
    return int(m.group(1)) if m else None


def reap_finished_lanes(lanes, open_ids):
    """Prune ``lanes`` entries whose dispatch has landed (#969).

    ``lanes`` is author-owned judgement text, but the dispatch it names is
    finished when its task leaves ``## Open`` — the same ledger signal that
    reaps ``dreamers`` (#402a). ``lanes`` had no deriver at all, so it could
    only be true by coordinator diligence, and for hours it named landed
    dispatches while ``dreamers`` agreed (both stale in the same direction),
    leaving the #702 disagreement check silent. Giving ``lanes`` the same
    task-open reaper breaks the tie: the ledger is the third party both
    fields answer to, so they can no longer corroborate each other's
    staleness.

    Returns ``(kept, reaped, examined, unparseable)``. An entry whose prefix
    yields no task id is KEPT (#702/#136: *cannot compare* must not read as
    *landed*); the population is returned in full so ``examined 0`` is
    visibly not an all-clear — ``lanes: []`` is both the correct idle state
    and what a broken deriver produces (#868 inside the fix).
    """
    if not isinstance(lanes, list):
        return [], [], 0, 0
    open_set = set(open_ids)
    kept, reaped = [], []
    unparseable = 0
    for entry in lanes:
        base = _lane_entry_base_id(entry)
        if base is None:
            unparseable += 1
            kept.append(entry)
        elif base in open_set:
            kept.append(entry)
        else:
            reaped.append(entry)
    return kept, reaped, len(lanes), unparseable


def _normalise_live(live: set) -> list:
    """A deterministic order for mixed-type ids without `sorted()`'s crash.

    A live set may hold `396` (int) and `"401"` / `"392a"` (str) at once;
    `sorted()` raises `TypeError` on that mix and took the whole sync with it
    (#402a). Sort by string form instead — stable, total, and it keeps the
    sub-id rather than dropping or coercing it.
    """
    return sorted(live, key=str)


def coverage(status: dict, skipped: bool = False) -> str:
    """One line naming what was derived and what was left to its author.

    The untouched list is the file's actual keys minus `DERIVED`, never a
    literal — so a field added next month appears in it without anyone
    remembering to extend a list. Printed on every run, including the
    no-change run and the liveness-unknown skip, because *"already in sync"*
    once read as success while three other fields were stale.
    """
    untouched = sorted(k for k in status if k not in DERIVED)
    kind = "derived (skipped: liveness unknown)" if skipped else "derived"
    return ("coverage: %s %s · author-owned %s"
            % (kind, list(DERIVED), untouched))


def _read_status(spath: Path):
    """Read status.json defensively (#402).

    The file is gitignored ephemera written by more than one hand (the
    coordinator at dispatch, the syncer at reap, the dashboard on tick), so
    a file that is absent, empty, truncated mid-write, or structurally wrong
    is the NORMAL case rather than an exception — the brief's own words:
    *"a check that hard-fails on it is worse than none"*. A syncer that
    CRASHES on it (uncaught ``JSONDecodeError`` / ``AttributeError``) stops
    protecting everything after it; a syncer that OVERWRITES it with freshly
    derived fields destroys the author-written ones (``deployed``, ``task``,
    ``monitors``, ``owed_verifications``, …) it could not read. Neither is
    acceptable, so this does neither.

    Returns ``(status, None)`` for a readable object, or ``(None, reason)``
    for anything else, and the caller refuses to write. The ledger and
    ``submissions.log`` are the durable sources a coordinator rebuilds from;
    a projection is not rebuildable by the syncer without losing what its
    author held.
    """
    raw = spath.read_text()
    if raw.strip() == "":
        return None, "status.json is empty"
    try:
        status = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, ("status.json is unparseable (truncated/corrupt at "
                      "line %d): %s" % (exc.lineno, exc.msg))
    if not isinstance(status, dict):
        return None, ("status.json top level is %s, not an object"
                      % type(status).__name__)
    return status, None


def _agent_session_record(status: dict, target: Path, *, env=None, now=None,
                          projects_root=None):
    """Return the automatically derived main-session record, or ``None``.

    The environment is process-local, so it is authoritative only for a sync
    of the invoking process's cwd.  An explicit sync of another checkout is a
    validation of that checkout, not authority to replace its main agent.

    The client registry supplies the candidate UUID; ``session_source`` then
    has to resolve that UUID as ``live`` using the same id as the independently
    expected running-process identity.  Merely producing a path is not enough:
    ``stale``, ``missing``, ``mismatch`` and ``absent`` all become an explicit
    absent record rather than a false-green identity.
    """
    if target.resolve() != Path.cwd().resolve():
        return None

    # Lazy imports avoid a module cycle: client_env reuses _read_status, and
    # session_source imports it too.  main() runs only after this module has
    # defined that shared refusal reader.
    import client_env
    import session_source

    env = os.environ if env is None else env
    rec = client_env.record(env=env, now=now)
    expected = rec.get("session_id")
    if projects_root is None:
        config = env.get("CLAUDE_CONFIG_DIR")
        projects_root = Path(config) / "projects" if config else None
    resolved = session_source.resolve(
        expected, projects_root, now=now, expected_session_id=expected)
    if resolved.status != "live":
        prior_note = rec.get("note")
        rec["session_id"] = None
        rec["note"] = "%s%sresolved %s: %s" % (
            (prior_note + "; ") if prior_note else "",
            ("candidate %s " % expected) if expected else "",
            resolved.status, resolved.detail)

    # recorded_at dates the identity claim, not each mechanical sync.  Keep it
    # when the substantive record is unchanged so --check can be idempotent.
    existing = status.get("agent_session")
    if isinstance(existing, dict):
        old_claim = {k: v for k, v in existing.items() if k != "recorded_at"}
        new_claim = {k: v for k, v in rec.items() if k != "recorded_at"}
        if old_claim == new_claim and existing.get("recorded_at"):
            rec["recorded_at"] = existing["recorded_at"]
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=".", help="target project directory")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if stale, write nothing")
    args = ap.parse_args(argv)

    dw = Path(args.target) / ".dreamwork"
    spath, lpath = dw / "status.json", dw / "tasks.md"
    if not spath.exists() or not lpath.exists():
        print("status_sync: no status.json or tasks.md under %s" % dw,
              file=sys.stderr)
        return 2

    # Read status.json defensively (#402): it is gitignored ephemera, so a
    # truncated/empty/non-object file is the normal case, not an exception.
    # Refuse to write rather than crash (which stops protecting everything
    # after it) or overwrite (which destroys the author-written fields the
    # broken file could not yield). The ledger + submissions.log rebuild it.
    status, why = _read_status(spath)
    if status is None:
        print("status_sync: %s — leaving it untouched; the ledger and "
              "submissions.log are the durable sources, and overwriting a "
              "broken projection would destroy the author-written fields it "
              "could not read" % why, file=sys.stderr)
        return 2

    # #294 inc 7: dispatch on source_of_truth. The store's task table is
    # authoritative after the cutover watermark; markdown stays for pre-cutover.
    # Both paths return the same list[int] of open ids — the rest of main is
    # unchanged. A missing store is fail-closed to markdown by source_of_truth.
    ids, landed_ids = read_task_ids_by_state(dw, lpath)
    if not ids:
        # An unreadable ledger and an empty one look identical to a parser, so
        # refuse rather than write `pending: 0` over a real count.
        print("status_sync: no ids under `## Open` — refusing to write a count "
              "derived from an unreadable ledger", file=sys.stderr)
        return 2
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        print("status_sync: duplicate id(s) %s under `## Open` — fix the "
              "ledger first; `lint.py` reports this too" % dupes,
              file=sys.stderr)
        return 2

    # `queued_dispatches` remains author-owned prose, but every #NNN inside
    # it is a checkable claim about ledger state (#755). Report contradictions
    # after the ledger's refusal gates and never add them to `changes`: a
    # landed id can intentionally name queued follow-up work, so this is a
    # question for the coordinator, not sync staleness and never a rewrite.
    audit_queued_dispatches(status, task_states(ids, landed_ids))

    # Pre-filter malformed entries (#402a): the syncer must never crash on
    # junk. An entry that is not a dict, has no task, or carries neither a
    # parseable pid nor a brief is skipped and reported — it cannot be asked
    # about, so a derived answer would be a guess dressed as a measurement.
    raw_dreamers = status.get("dreamers", [])
    if not isinstance(raw_dreamers, list):
        raw_dreamers = []
    clean = [d for d in raw_dreamers if _evaluable(d)]
    junk = [d for d in raw_dreamers if not _evaluable(d)]
    if junk:
        print("status_sync: skipped %d malformed dreamer entr%s: %s"
              % (len(junk), "y" if len(junk) == 1 else "ies",
                 [_entry_tag(d) for d in junk]), file=sys.stderr)

    # #537: split evaluable entries by whether the liveness probe can OBSERVE
    # their dispatch form. `ccc` is the only form the probe sees; a harness-
    # native `spawn_subagent` clone is unobservable (no `ccc` process, no
    # probe-able pid). An observation blind to a form must never clobber
    # records of that form, so unobservable entries are carried verbatim past
    # the probe and reaped only by the ledger (a landed task is observable
    # regardless of form). Without this split a live spawn_subagent fleet was
    # pruned to 0 because the probe could not see it.
    observable = [d for d in clean if _observable(d)]
    unobservable = [d for d in clean if not _observable(d)]
    if unobservable:
        print("status_sync: carrying %d dreamer(s) of an unobservable "
              "dispatch form verbatim (probe-blind, e.g. spawn_subagent): %s"
              % (len(unobservable), [_entry_tag(d) for d in unobservable]),
              file=sys.stderr)

    try:
        live_set, pid_live = live_lanes(observable)
    except LivenessUnknown as e:
        # Could not tell which lanes are live (pgrep broken, etc.). Leave the
        # derived fields byte-identical to their author's writing and say so
        # on stderr — never write a value the probe could not derive. Still
        # print coverage so the run is not silent about which fields it
        # touched (none).
        print("status_sync: liveness unknown — leaving %s untouched (%s)"
              % (", ".join(DERIVED), e), file=sys.stderr)
        print(coverage(status, skipped=True))
        return 3                       # distinct from stale (1) and clean (0)

    # Unobservable entries (#537) join the survivors here, verbatim — the
    # probe cannot see them, so it must not prune them. They flow through the
    # task-open reap below (landing is observable via the ledger regardless of
    # dispatch form); a live pid is NOT required, only an open task.
    pid_live = pid_live + unobservable

    # Reap entries whose task is no longer under `## Open` (#402a): an entry
    # whose pid is dead was already dropped by live_lanes; this catches the
    # other direction — the work landed, so the lane no longer owns files.
    # A sub-id (`392a`) is in flight on its base task (392); compare by base.
    # Reaping (not a hard stop) is the load-bearing change: the old code
    # returned 2 here, which stopped the whole sync for one stale entry.
    #
    # #702: an entry whose task has no derivable base id (`_base_id` returns
    # None — observed: `"#696"` where `696` was meant, because the regex
    # matches leading digits and a `#` prefix yields none) used to land here
    # too, and `None in ids` is False, so it was reaped with the SAME message
    # as a genuinely dead lane. A format error must not read as a correct reap
    # (#136: "nothing needs you" and "the channel is broken" must not render
    # identically), and a task the comparison cannot reach must not be dropped
    # by a judgment it never reached (#537). So such an entry is KEPT and the
    # format error is reported loudly; only a task whose base id IS derivable
    # and is NOT open counts as genuinely landed.
    pruned = []
    reaped = []
    malformed = []
    for d in pid_live:
        base = _base_id(d.get("task"))
        if base is None:
            malformed.append(d)
            pruned.append(d)          # kept — cannot compare, so cannot reap
        elif base in ids:
            pruned.append(d)
        else:
            reaped.append(d)
    if reaped:
        print("status_sync: reaped %d dreamer(s) whose task is not under "
              "`## Open`: %s"
              % (len(reaped), [_entry_tag(d) for d in reaped]), file=sys.stderr)
    if malformed:
        print("status_sync: KEPT %d dreamer(s) with a task id the ledger "
              "comparison cannot reach (no leading digits — expected a plain "
              "id like 696, saw a form like '#696'); not reaped because "
              "'cannot compare' must not read as 'landed' (#136, #702): %s"
              % (len(malformed), [_entry_tag(d) for d in malformed]),
              file=sys.stderr)

    # #716: DISCOVERY — the other half of `dreamers`. The prune above can only
    # SHRINK the field (dead pid / landed task); nothing added a lane, so a
    # freshly-dispatched fleet read as zero while it ran. A `ccc` lane's cwd
    # is its worktree, so `readlink /proc/<pid>/cwd` recovers it cheaply and
    # exactly. This MERGES with the survivors above rather than replacing
    # them: a lane running somewhere the cwd probe cannot see (another
    # machine, a harness-native spawn_subagent) is carried verbatim (#537), and
    # a lane the probe sees but cannot classify is simply absent from the
    # discovery list — REPORTED, never silently dropped (#702's "cannot
    # compare must not read as landed", applied to discovery rather than reap).
    discovered, phantoms, agent_tool = discover_lanes(Path(args.target))
    existing_lanes = {d.get("lane") for d in pruned if isinstance(d, dict)}
    added = []
    resolved = Path(args.target).resolve()
    for lane, pid, model in discovered:
        if lane in existing_lanes:
            continue
        entry = {"task": _lane_task(lane, ids), "lane": lane,
                 "pid": pid,
                 "brief": str(_lane_worktree_path(resolved, lane, pid)
                              / "BRIEF.md"),
                 "dispatch": "ccc"}
        if model is not None:                 # #720: derived from /proc argv
            entry["model"] = model
        added.append(entry)
        pruned.append(added[-1])
        existing_lanes.add(lane)
    if added:
        print("status_sync: discovered %d live ccc lane(s) the field did not "
              "carry (cwd under either worktree root; merged, not replaced): %s"
              % (len(added), [(a["lane"], a["pid"]) for a in added]),
              file=sys.stderr)
    # #675: Agent-tool lanes — non-ccc processes with a lane cwd. Merged into
    # dreamers with `dispatch: "agent_tool"` so current_task_ids counts them
    # (avoids the permanent-zero drift alarm) and so the next tick's
    # liveness probe can reap them by pid (agent_tool is OBSERVABLE: kill -0
    # reaches it even though pgrep ccc never lists it). REPORTED separately
    # from ccc so the runner is visible and never silently mixed in.
    agent_added = []
    for lane, pid in agent_tool:
        if lane in existing_lanes:
            continue
        entry = {"task": _lane_task(lane, ids), "lane": lane,
                 "pid": pid,
                 "brief": str(_lane_worktree_path(resolved, lane, pid)
                              / "BRIEF.md"),
                 "dispatch": "agent_tool"}
        agent_added.append(entry)
        pruned.append(entry)
        existing_lanes.add(lane)
    if agent_added:
        print("status_sync: discovered %d live agent-tool lane(s) the field "
              "did not carry (non-ccc process with a lane cwd; merged so the "
              "live count does not read zero while Agent-tool lanes run — "
              "#675): %s"
              % (len(agent_added),
                 [(a["lane"], a["pid"]) for a in agent_added]),
              file=sys.stderr)
    if phantoms:
        # #729: the old single bucket rendered three DIFFERENT facts as one
        # (#136): the coordinator's own process (self), a genuine leftover
        # lane runner (e.g. an abandoned ccc/claude/grok/codex), and a shell
        # fragment (head/grep/tail/bash) that merely once held the cwd. All
        # three were labelled "ccc process mid-exit" — a specificity the old
        # code did not have (#671: it matched any cwd under .worktrees/, never
        # read argv). Splitting the bucket and LABELLING the cases is the fix;
        # #702 governs: an entry the tool cannot classify must be REPORTED,
        # never silently dropped. Ancestry (exact, /proc ppid walk) separates
        # self; the positive-identity test (copies reaper.parse_cmdline's shape,
        # #729) separates a runner from noise.
        ancestors = _ancestor_pids()
        self_ph, runner_ph, other_ph = [], [], []
        for lane, pid in phantoms:
            if pid in ancestors:
                self_ph.append((lane, pid))
            elif _is_lane_runner(pid):
                runner_ph.append((lane, pid))
            else:
                other_ph.append((lane, pid))
        if self_ph:
            print("status_sync: %d phantom entr%s the coordinator's own "
                  "ancestry (deleted cwd under .worktrees/, but this process "
                  "is an ancestor of status_sync; not a lane, reported not "
                  "dropped — #729/#702): %s"
                  % (len(self_ph), "y is" if len(self_ph) == 1 else "ies are",
                     self_ph), file=sys.stderr)
        if runner_ph:
            print("status_sync: excluded %d genuine leftover lane runner(s) "
                  "whose worktree is gone (known runner ccc/claude/grok/codex "
                  "with deleted cwd; reported not dropped — #719/#702): %s"
                  % (len(runner_ph), runner_ph), file=sys.stderr)
        if other_ph:
            print("status_sync: %d phantom entr%s a process with a deleted "
                  "worktree cwd that is neither self nor a known runner "
                  "(e.g. head/grep/tail/bash from a lane's pipeline; cwd under "
                  ".worktrees/ matched the old prefix filter — #671/#729; "
                  "reported not dropped — #702): %s"
                  % (len(other_ph), "y is" if len(other_ph) == 1 else "ies are",
                     other_ph), file=sys.stderr)

    # Normalise task ids on write (#402b): plain → int, sub-id → str. This
    # happens BEFORE the live set is derived so current_task_ids and the
    # surviving dreamers agree on the canonical form.
    pruned = [_normalise_entry(d) for d in pruned]

    # The live set for `current_task_ids` is exactly the survivors' tasks.
    live = _normalise_live({d["task"] for d in pruned})

    want_queue = {"in_progress": len(live), "pending": len(ids) - len(live)}
    changes = []
    # #294 T2: post-cutover the store is the ONE source for queue depth and
    # in-flight tasks. status.json loses `queue` and `current_task_ids`, and
    # this tool — the very process that derived them — must not regrow them:
    # lint's absence-invariant ERRORs on a regrown field, and a regrown field
    # is the second derived truth #264 exists to remove. So in store mode the
    # tool's write of those keys is inverted into a strip.
    store_mode = source_of_truth(dw) == "store"
    if store_mode:
        for k in ("queue", "current_task_ids"):
            if k in status:
                changes.append("%s present post-cutover — retired, dropping "
                               "(#294 T2)" % k)
                status.pop(k, None)
    else:
        if status.get("queue") != want_queue:
            changes.append("queue %s -> %s" % (status.get("queue"), want_queue))
        if status.get("current_task_ids") != live:
            changes.append("current_task_ids %s -> %s"
                           % (status.get("current_task_ids"), live))
    dreamers_in = status.get("dreamers", [])
    if dreamers_in != pruned:
        delta = len(pruned) - len(dreamers_in)
        if delta < 0:
            verb = "prune %d stale lane(s)" % (-delta)
        elif delta > 0:
            verb = "discover %d live lane(s)" % delta
        else:
            # Same count, different content: a lane swapped (one dead, one
            # discovered) or a task id changed. Name both without a net delta.
            verb = "change %d lane(s) (count unchanged)" % len(pruned)
        changes.append("dreamers %s (%d -> %d)"
                       % (verb, len(dreamers_in), len(pruned)))

    agent_session = _agent_session_record(status, Path(args.target))
    if agent_session is not None and status.get("agent_session") != agent_session:
        state = "live" if agent_session.get("session_id") else "absent"
        changes.append("agent_session -> %s %s"
                       % (state, agent_session.get("session_id")))

    # #969: `lanes` is author-owned judgement text, but the dispatch it names
    # is finished when its task leaves `## Open` — the same ledger signal that
    # reaps `dreamers` (#402a). `lanes` had no deriver at all, so it could
    # only be true by coordinator diligence, and for hours it named landed
    # dispatches while `dreamers` agreed (both stale in the same direction),
    # leaving the #702 disagreement check silent. Giving `lanes` the same
    # task-open reaper breaks the tie: the ledger is the third party both
    # fields answer to, so they can no longer corroborate each other's
    # staleness. The population is named on every run because `lanes: []` is
    # both correct-idle and a broken deriver's output (#868 inside the fix).
    raw_lanes = status.get("lanes", [])
    if isinstance(raw_lanes, list):
        kept_lanes, reaped_lanes, examined, unparseable = reap_finished_lanes(
            raw_lanes, ids)
        print("status_sync: lanes reap examined %d, pruned %d, kept %d, "
              "unparseable %d — population named because an empty pair is "
              "both idle and a broken deriver (#868/#969)"
              % (examined, len(reaped_lanes), len(kept_lanes), unparseable),
              file=sys.stderr)
        if reaped_lanes:
            status["lanes"] = kept_lanes
            changes.append("lanes reap %d finished dispatch(es) (examined "
                           "%d, pruned %d, kept %d, unparseable %d): %s"
                           % (len(reaped_lanes), examined, len(reaped_lanes),
                              len(kept_lanes), unparseable,
                              [_lane_entry_base_id(e) for e in reaped_lanes]))

    print(coverage(status))

    if args.check:
        for c in changes:
            print("stale: %s" % c)
        return 1 if changes else 0

    if store_mode:
        status["dreamers"] = pruned
    else:
        status["queue"], status["current_task_ids"], status["dreamers"] = (
            want_queue, live, pruned)
    if agent_session is not None:
        status["agent_session"] = agent_session
    # #541: write atomically — serialise to a temp file in the SAME directory
    # as status.json, then `os.replace` (a same-filesystem rename, atomic on
    # POSIX/NTFS). A plain `spath.write_text` truncates the real file the
    # instant it opens it, so a crash mid-write tears status.json — and every
    # reader downstream must then treat a torn file as the normal case (#402).
    # This is the one writer that can prevent it. Mirrors watch.py's
    # question-sigs idiom (_write_question_sigs): tmp + os.replace.
    tmp = str(spath) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(status, indent=2) + "\n")
    os.replace(tmp, spath)
    print("\n".join(changes) if changes
          else "already in sync (%d open, %d live)" % (len(ids), len(live)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
