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


# The three top-level keys this tool owns. Everything else in status.json is
# left to its author, and `coverage` says so on every run by subtracting this
# tuple from the file's actual keys — so a field added next month shows up in
# the untouched list without anyone remembering to extend a literal.
DERIVED = ("queue", "current_task_ids", "dreamers")


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


class LivenessUnknown(Exception):
    """The probe could not tell which lanes are live.

    "I could not tell" and "nothing is running" must not be the same value:
    the old `OSError` branch returned `[]`, and that empty list was then
    written over a correct hand-written `current_task_ids` for the whole
    duration of every flagged dispatch (#402a). A caller that cannot tell
    leaves the derived fields alone.
    """


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
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:          # ESRCH — the lane is gone. Not live.
        return False
    except (TypeError, ValueError):
        # An unparseable pid is malformed input, not liveness data; a lane we
        # cannot evaluate must not let the tool write a derived value.
        raise LivenessUnknown("unparseable dreamers pid: %r" % (pid,))
    except OSError as e:                # EPERM etc. — we cannot tell.
        raise LivenessUnknown("kill -0 %r failed: %s" % (pid, e))


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
            is_live = _pid_alive(pid)
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


# #537: dispatch forms the liveness probe can OBSERVE. The probe sees only
# `ccc` — `pgrep -af ccc` for the argv fallback, `kill -0` on a dispatch pid
# that is a `ccc` process. A lane dispatched any other way is UNOBSERVABLE:
# the harness's native `spawn_subagent` is an independent clone with no `ccc`
# process and no `wt/*` worktree, so neither signal can reach it. An
# observation blind to a form must never clobber records of that form — a
# live fleet of spawn_subagent lanes was once pruned to 0 by this tool
# because the probe could not see them. An entry whose `dispatch` is absent
# is the historical `ccc` default (observable), so every pre-#537 entry stays
# evaluable; any value not listed here is carried verbatim through the
# liveness step and reaped only by the ledger (a landed task is observable
# regardless of dispatch form).
OBSERVABLE_DISPATCH = ("ccc",)


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
# (`.worktrees/<lane>`), so `readlink /proc/<pid>/cwd` recovers it. The pid a
# lane is recorded under is the `ccc` process itself (measured: cmdline begins
# `ccc -y @glm52 …`, and its ppid is the zsh wrapper — both share the worktree
# as cwd, so the probe is indifferent to which is recorded; #402a already
# settled the recorded pid as the survivor). A lane whose cwd the probe can
# read but cannot classify is REPORTED, never silently dropped and never
# silently added — the mirror of #702's "cannot compare must not read as
# landed" applied to discovery rather than reap.
WORKTREE_DIR = ".worktrees"


def _read_proc_cwd(pid: int) -> str | None:
    """`readlink /proc/<pid>/cwd`, or None if unreadable (gone / no perm)."""
    try:
        return os.readlink("/proc/%d/cwd" % pid)
    except OSError:
        return None


def _is_ccc_proc(pid: int) -> bool:
    """Whether `pid`'s argv[0] basename is `ccc` (the probe-observable form).

    Avoids over-counting: a worktree cwd is also held by the zsh wrapper, an
    editor, or a pytest a coordinator ran from a worktree (#716 dir-2). Only a
    `ccc` process is a dispatched lane, so the argv check keeps discovery to
    the one form the liveness probe already reasons about (#675). Reads the
    raw bytes so a NUL-containing cmdline cannot parse as `ccc` by accident.
    """
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            raw = f.read()
    except OSError:
        return False
    if not raw:
        return False
    first = raw.split(b"\x00", 1)[0]
    return os.path.basename(first.decode("utf-8", "replace")) == "ccc"


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


def discover_lanes(target: Path):
    """Live `ccc` lanes the cwd probe can see, as ``(found, phantoms)``.

    Walks ``/proc/*/cwd`` for paths under ``<target>/.worktrees/`` whose
    process is a ``ccc`` dispatch (#716). ``found`` is the list of live lanes
    (as ``(lane, pid, model)`` triples — #720 derives the model from the same
    ``/proc`` read) a caller MERGES with coordinator-authored entries (a lane
    running where the cwd probe cannot reach — another machine, a different
    harness — is carried verbatim rather than erased by a narrower automatic
    view).

    ``phantoms`` (#719) is a ``ccc`` process whose cwd passed the worktree
    prefix filter but whose worktree has been REMOVED — Linux appends
    ``" (deleted)"`` to the readlink, the prefix still matches, and the
    regex still yields a task id, so without a guard the phantom takes a
    fleet slot under a corpse's name. A ccc process whose cwd is no longer a
    directory is EXITING, not working. It is excluded from ``found`` and
    REPORTED via ``phantoms`` — never silently dropped. The #702 rule
    (inherited by #716's discovery: "an entry the probe cannot classify must
    be reported, never silently dropped") reaches this case because the probe
    *can* see the process and *can* tell the worktree is gone; silently
    skipping would make "lane finished and was reaped" and "lane's worktree
    vanished mid-run" render identically (#136). The signal is actionable
    for the reap loop: it distinguishes a clean exit drain from a process
    that hung after its worktree was removed.

    ``target`` is the project root (the dir whose ``.worktrees/`` holds
    lanes). It is RESOLVED before building ``wt_root`` (#720): the default
    ``--target="."`` produced ``"./.worktrees"``, tested with ``startswith``
    against the ABSOLUTE path ``readlink`` returns — it never matched, so
    discovery was INERT under the invocation the loop actually uses.
    ``resolve()`` (not ``realpath``: #425's symlink contract; not
    ``abspath``: this repo is reached through ``~/.claude-p/skills/…`` while
    lane cwds carry ``~/.llm-general/skills/…``, and ``abspath`` keeps the
    symlink while ``resolve()`` normalises to the real path the cwds share).
    """
    wt_root = str(target.resolve()) + "/" + WORKTREE_DIR
    found = []
    phantoms = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        cwd = _read_proc_cwd(pid)
        if cwd is None or not cwd.startswith(wt_root + "/"):
            continue
        lane = os.path.basename(cwd.rstrip("/"))
        if not lane or lane == target.name:
            continue
        if not _is_ccc_proc(pid):
            continue
        # #719: a ccc lane whose worktree has been removed is a phantom.
        # readlink still resolves (Linux appends " (deleted)"), the prefix
        # filter still passes, but the cwd is no longer a directory — the
        # process is exiting, not working. Excluded and REPORTED, not
        # silently dropped (#702, inherited by #716's discovery).
        if not os.path.isdir(cwd):
            phantoms.append((lane, pid))
            continue
        found.append((lane, pid, _ccc_model(pid)))
    # Stable order by lane name so the merge and the stderr report are
    # deterministic across runs reading the same process table.
    return (sorted(found, key=lambda lpm: lpm[0]),
            sorted(phantoms, key=lambda lp: lp[0]))


def read_open_ids(dw, lpath):
    """Open ids under `## Open`, dispatching on source_of_truth (#294 inc 7).

    Returns ``list[int]`` — every id under Open, combined heads expanded.
    Store mode queries ``store_ids_by_state``; markdown mode parses the
    text. A missing store is fail-closed to markdown by ``source_of_truth``.
    """
    if source_of_truth(str(dw)) == "store":
        open_strs, _ = store_ids_by_state(str(dw))
        return [int(x) for x in open_strs]
    return open_ids(lpath.read_text())


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
    ids = read_open_ids(dw, lpath)
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
    discovered, phantoms = discover_lanes(Path(args.target))
    existing_lanes = {d.get("lane") for d in pruned if isinstance(d, dict)}
    added = []
    resolved = Path(args.target).resolve()
    for lane, pid, model in discovered:
        if lane in existing_lanes:
            continue
        entry = {"task": _lane_task(lane, ids), "lane": lane,
                 "pid": pid,
                 "brief": str(resolved / WORKTREE_DIR / lane / "BRIEF.md"),
                 "dispatch": "ccc"}
        if model is not None:                 # #720: derived from /proc argv
            entry["model"] = model
        added.append(entry)
        pruned.append(added[-1])
    if added:
        print("status_sync: discovered %d live ccc lane(s) the field did not "
              "carry (cwd under .worktrees/; merged, not replaced): %s"
              % (len(added), [(a["lane"], a["pid"]) for a in added]),
              file=sys.stderr)
    if phantoms:
        # #719: a ccc lane whose worktree is gone is a phantom — the process
        # is exiting, not working. Reported (not silently dropped) so the reap
        # loop can tell a clean exit drain from a hung-after-removal process:
        # silently skipping would make "finished" and "worktree vanished
        # mid-run" render identically (#136). #702's rule, inherited by #716's
        # discovery, is that an entry the probe cannot classify must be
        # reported. The lane name carries " (deleted)" as readlink appended it.
        print("status_sync: excluded %d phantom lane(s) whose worktree is gone "
              "(ccc process mid-exit, cwd no longer a directory; reported not "
              "dropped — #719/#702): %s"
              % (len(phantoms), phantoms), file=sys.stderr)

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
