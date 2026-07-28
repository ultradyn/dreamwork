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
  dreamers                            pruned of lanes whose process is gone —
                                      a dead lane leaves the array; nothing
                                      else about the survivors changes.

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
ENTRY_ID = re.compile(r"#(\d+)")


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


def _base_id(task) -> int | None:
    """The integer task a (possibly sub-) id refers to.

    `current_task_ids` can legitimately carry a sub-id like `392a` (a lane has
    been `#392a`); the unknown-lane check has to compare it against the open
    ledger by its *base* id (392), not by string equality against `[392]`.
    Returns None for an id with no leading digits.
    """
    m = re.match(r"\d+", str(task))
    return int(m.group()) if m else None


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

    status = json.loads(spath.read_text())
    ids = open_ids(lpath.read_text())
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

    try:
        live_set, pruned = live_lanes(status.get("dreamers", []))
    except LivenessUnknown as e:
        # Could not tell which lanes are live. Leave the derived fields
        # byte-identical to their author's writing and say so on stderr —
        # never write a value the probe could not derive. Still print coverage
        # so the run is not silent about which fields it touched (none).
        print("status_sync: liveness unknown — leaving %s untouched (%s)"
              % (", ".join(DERIVED), e), file=sys.stderr)
        print(coverage(status, skipped=True))
        return 3                       # distinct from stale (1) and clean (0)

    live = _normalise_live(live_set)
    # A sub-id (`392a`) is in flight on its base task (392); compare by base.
    unknown = [t for t in live if _base_id(t) not in ids]
    if unknown:
        print("status_sync: live lane(s) %s are not under `## Open` — a lane "
              "is working on a task the ledger calls closed" % unknown,
              file=sys.stderr)
        return 2

    want_queue = {"in_progress": len(live), "pending": len(ids) - len(live)}
    changes = []
    if status.get("queue") != want_queue:
        changes.append("queue %s -> %s" % (status.get("queue"), want_queue))
    if status.get("current_task_ids") != live:
        changes.append("current_task_ids %s -> %s"
                       % (status.get("current_task_ids"), live))
    dreamers_in = status.get("dreamers", [])
    if dreamers_in != pruned:
        changes.append("dreamers prune %d dead lane(s) (%d -> %d)"
                       % (len(dreamers_in) - len(pruned),
                          len(dreamers_in), len(pruned)))

    print(coverage(status))

    if args.check:
        for c in changes:
            print("stale: %s" % c)
        return 1 if changes else 0

    status["queue"], status["current_task_ids"], status["dreamers"] = (
        want_queue, live, pruned)
    spath.write_text(json.dumps(status, indent=2) + "\n")
    print("\n".join(changes) if changes
          else "already in sync (%d open, %d live)" % (len(ids), len(live)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
