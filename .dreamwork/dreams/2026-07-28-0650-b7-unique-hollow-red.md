# B7 UNIQUE red is hollow under BEGIN IMMEDIATE + SELECT

Lane B2 (increments 7–10), 2026-07-28.

The plan's B7 red line is `UNIQUE(client_action_id)`. Removing it left
`test_two_processes_one_uuid_make_one_receipt` green. The children were real
spawn processes with distinct pids — not threads.

Why: receive() does `BEGIN IMMEDIATE` then SELECT-by-UUID before insert. Writers
serialize; the second process always sees the first's row and replays. UNIQUE
never fires on the happy path. It is defense-in-depth for a DEFERRED/racy
receive, not the line that makes the two-process property true *today*.

Same class of finding as B1: the plan assumed a platform/shape default that did
not match (FULL already default; here IMMEDIATE+SELECT already unique). A green
red-run is a finding, never a relief.

Amendment options for the plan:
1. Name `BEGIN IMMEDIATE` (or the SELECT-before-insert) as co-reds for B7.
2. Switch receive to insert-first + IntegrityError → replay/conflict, so UNIQUE
   is the concurrent backstop and the red becomes load-bearing without
   weakening the property.

UNIQUE stays in the schema either way.
