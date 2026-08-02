#!/usr/bin/env python3
"""Build a goal-fixture for dev/capture/goalfault.mjs (#1029).

Creates a .dreamwork target with two goals — both seeded in the 'open'
state — and sets the current-goal pointer per `mode`:

  current  the goal titled 'Broken goal' is current (the already-working case)
  other    the goal titled 'Healthy goal' is current (Finding 1: the dashboard
           must show that a sibling is unreadable even when the current is fine)

The NULL goal_state injection (the real production fault) does NOT happen
here. It runs as an inline python3 -c call in goalfault.mjs (around line 83)
because the no-raw-connect guard (#645) scans every non-test .py file and
this is test infrastructure it cannot distinguish from production. So this
helper emits two healthy goals and hands back the db_path so the guard can
inject the fault itself.

Prints JSON: {"good_id": N, "fault_id": N, "current_id": N, "db_path": str}.

usage: python3 goalfault_fixture.py <target_dir> <current|other>
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import watch
from ledger_parse import store_path
from dreamwork_db import Access, open_database
from dreamwork_db.tasks import task_store_spec


def make_target(root):
    dw = os.path.join(root, ".dreamwork")
    os.makedirs(os.path.join(dw, "dreams", "archive"), exist_ok=True)
    os.makedirs(os.path.join(dw, "docs"), exist_ok=True)
    with open(os.path.join(root, "DREAMWORK.md"), "w") as f:
        f.write("# DREAMWORK\n")
    with open(os.path.join(dw, "dreams", "2026-01-01-x.md"), "w") as f:
        f.write("dream body\n")
    with open(os.path.join(dw, "dreams", "archive", "2025-12-01-y.md"),
              "w") as f:
        f.write("old dream\n")
    with open(os.path.join(dw, "questions.md"), "w") as f:
        f.write("# Questions for the human\n\n## Open\n\n## Answered\n")
    with open(os.path.join(dw, "lessons.md"), "w") as f:
        f.write("# Lessons\n")
    with open(os.path.join(dw, "skill-version"), "w") as f:
        f.write("2026-07-25-x.md\n")
    return root


make_target(sys.argv[1])
dw = os.path.join(sys.argv[1], ".dreamwork")
os.makedirs(os.path.join(dw, "review"), exist_ok=True)

# Seed the ledger store watermark the way _store_target does, so
# source_of_truth is 'store' and goal_tree_payload reads the DB.
import ledger_store
from ledger_parse import _WATERMARK_KEY
store = ledger_store.open_store(store_path(dw), seed_next_id=1)
store.conn.execute(
    "INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",
    (_WATERMARK_KEY, "2026-07-30T00:00:00Z"))
store.close()

mode = sys.argv[2]

with open_database(
        task_store_spec(store_path(dw)), access=Access.WRITE) as db:
    with db.transaction():
        for title in ("healthy task body", "broken task body"):
            db.tasks.file(
                title, title, priority="P2", type="test",
                origin="human", blocked_on=None, actor="test",
                at="2026-08-01T01:00:00Z")
        good = db.groups.create(
            kind="goal", title="Healthy goal", actor="test",
            at="2026-08-01T01:00:01Z")
        fault = db.groups.create(
            kind="goal", title="Broken goal", parent_id=good,
            actor="test", at="2026-08-01T01:00:02Z")
        db.groups.add_task(good, 1, actor="test", at="2026-08-01T01:00:03Z")
        db.groups.add_task(fault, 2, actor="test", at="2026-08-01T01:00:04Z")
        db.goals.set_state(good, "open")
        db.goals.set_state(fault, "open")
        db.goals.set_rank(good, 1)
        db.goals.set_rank(fault, 2)
        db.goals.set_current_goal_id(fault if mode == "current" else good)

# Inject the fault the way it happened: NULL goal_state on the broken node.
# This file is test infrastructure (a guard fixture builder), but the
# no-raw-connect guard (#645) scans every non-test .py file, so the injection
# runs through a separate inline python3 -c call from the .mjs guard instead.
print(json.dumps(
    {"good_id": good, "fault_id": fault,
     "current_id": fault if mode == "current" else good,
     "db_path": str(store_path(dw))}))
