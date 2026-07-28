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
that holds it"*. The ledger is that place for the open count; `pgrep` is that
place for which lanes are live. Neither is memory.

Derived here, and nothing else is touched:

  queue.in_progress / queue.pending   from the ledger's `## Open` section,
                                      counting **every id** — a combined head
                                      `- **#7/#8**` is two ids in one entry
                                      (`file-formats.md`), which is the
                                      distinction that made three independent
                                      hand-counts agree and all be wrong.
  current_task_ids                    from live `ccc @` processes, matched to
                                      the `dreamers` entries already recorded.

Everything a human or coordinator wrote by judgement is left alone: notes,
owed_verifications, queued_dispatches, deployed, monitors, session_goal.

Usage:  python3 status_sync.py [--target DIR] [--check]

`--check` exits 1 without writing if anything was stale, so it can be run
before a commit; the default rewrites and prints what changed.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# #331: the ids-only bold span has ONE definition, in watch.py. Consume it
# here rather than restating it — this was the third unpinned copy of the
# rule, and it matched the other two only by luck. The head form is pinned
# identical to watch.LEDGER_ENTRY and lint.LEDGER_ID by a test.
import watch

# A ledger entry head names one or more ids in a single bold span.
LEDGER_HEAD = re.compile(rf"^- \*\*({watch.IDS_ONLY_SPAN})\*\*", re.M)
ENTRY_ID = re.compile(r"#(\d+)")


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


def live_tasks(dreamers: list[dict]) -> list[int]:
    """Tasks whose dispatched process is still running.

    Matched by the brief path recorded at dispatch rather than by pid, because
    `ccc` re-execs its runner and the pid recorded at dispatch is the wrapper's,
    not the survivor's.
    """
    try:
        ps = subprocess.run(["pgrep", "-af", "^ccc @"],
                            capture_output=True, text=True).stdout
    except OSError:
        return []
    return sorted({d["task"] for d in dreamers
                   if d.get("brief") and d["brief"] in ps})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=".", help="target project directory")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if stale, write nothing")
    args = ap.parse_args()

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

    live = live_tasks(status.get("dreamers", []))
    unknown = [t for t in live if t not in ids]
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

    if args.check:
        for c in changes:
            print("stale: %s" % c)
        return 1 if changes else 0

    status["queue"], status["current_task_ids"] = want_queue, live
    spath.write_text(json.dumps(status, indent=2) + "\n")
    print("\n".join(changes) if changes
          else "already in sync (%d open, %d live)" % (len(ids), len(live)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
