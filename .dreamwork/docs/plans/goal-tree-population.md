# #939 goal-tree population proposal

This is a proposal for the coordinator to apply. It does not write the live
store, change the current pointer, edit `DREAMWORK.md`, or claim that the tree
is complete. The labels below are proposal-local labels; the coordinator can
create them in parent-before-child order and then resolve their database ids.

`goal_rank` is a zero-based sibling order for goal nodes. The existing human
goal is identified by its live id so it must be moved, not duplicated.

## Proposed goal nodes

| label | title | parent | rank | one-line source and justification |
| --- | --- | --- | ---: | --- |
| G0 | Make "leave an agent dreaming on a project" a real workflow: the human can walk away and come back to steady, safe, well-chosen progress. | none | 0 | `DREAMWORK.md:8-9`: “Make \"leave an agent dreaming on a project\" a real workflow: the human can walk away and come back to steady, safe, well-chosen progress.” This is the sourced root, aimed at the project's destination rather than today's task inventory. |
| G1 | The loop's memory survives anything that ends a session — restart, compaction, a fresh agent. What it knew, it still knows. | G0 | 0 | `DREAMWORK.md:10-11`: “The loop's memory survives anything that ends a session — restart, compaction, a fresh agent. What it knew, it still knows.” This makes continuity a first-class branch of the root. |
| G2 | The dashboard is how you check on it and steer it without a chat turn, and it is worth looking at. | G0 | 1 | `DREAMWORK.md:12-13`: “The dashboard is how you check on it and steer it without a chat turn, and it is worth looking at.” This is the direct product surface for the human's day-to-day control. |
| G2a | Dreamhub is the successor surface, not a second window. | G2 | 0 | `DREAMWORK.md:14-20`, including his words: “dreamhub should entirely replace watch.py for normal day-to-day use. All features from watch.py should be ported over. or watch.py should be refactored into modules and then they can be imported to use in dreamhub.” This parent fixes the migration's meaning as successor surface, with extraction/reuse available, not a from-scratch rewrite. |
| G2b | Dreamhub's end state has a front door. | G2 | 1 | `DREAMWORK.md:101-106`: “one frontend for many projects, each with its own dreamworker, all reachable through one webui” and “dreamhub with login ... to see/manage all projects + useful taskboard.” This keeps the upper tier ambitious beyond one converted page. |
| G3 | One human, several dreaming agents | G0 | 2 | `DREAMWORK.md:35-38`: “the workflow scales past one session — a hub aggregates them, and managing an agent's lifecycle ... becomes something the system does deliberately.” This records the multi-agent destination without classifying every current task. |
| G4 | Dogfooding the loop is a goal, not a side effect. | G0 | 3 | `DREAMWORK.md:93-97`: “whenever we notice friction or issues with the loop procedures / work flow ... log tasks in the db to investigate/fix these issues.” This is a human-recorded product goal for the loop itself, not an invented process category. |
| G5 | The loop stays cheap (cache-warm heartbeat), never gets stuck or bored, and is always steerable in a few words (`do now` / `do next` / `add idea`). | G0 | 4 | `DREAMWORK.md:109-110`: “The loop stays cheap (cache-warm heartbeat), never gets stuck or bored, and is always steerable in a few words.” This preserves the operating constraint above future implementation choices. |
| G6 | The loop gets on the human's wavelength over time: goals and preferences accrete here so questions get answered once and asking trends down, not up. | G0 | 5 | `DREAMWORK.md:112-114`: “The loop gets on the human's wavelength over time: goals and preferences accrete here so questions get answered once and asking trends down, not up.” This leaves room for future goals to be added as his preferences accrete. |

## Existing human goal placement

| existing id | title (unchanged) | parent | rank | one-line justification |
| ---: | --- | --- | ---: | --- |
| 1 | Convert webui to fully run via build react webui and migrate watch server over. | G2a | 0 | The live `task_group` row is kind `goal`, origin `human-via-watch`, `goal_state='open'`, with this exact title; place it beneath the successor-surface node because it is his conversion/migration goal, not a tidying or refactor reinterpretation. |

Do not edit, split, or duplicate id 1. The live current pointer is empty, so
after the coordinator applies the tree, the proposed operational follow-up is
`groups set-current 1`; that is a store action for the coordinator, not a
change made by this lane.

## Existing task memberships under id 1

These are task memberships, not additional upper-tier goals. They deliberately
hang work off the human goal without making the current backlog define the
project's destination. Task membership has no `goal_rank`; the order below is
the proposed application order, not a new ranking field.

| task | title (unchanged) | parent group | rank | one-line source and justification |
| ---: | --- | --- | --- | --- |
| #630 | Build the derived component surface + bundle step (the #591 survivor) | existing goal id 1 | n/a — task membership | `#630` is the open successor named by the approval record: “Build the derived component surface + bundle step (the #591 survivor).” Make it the first work spine under his goal because it implements the already-settled React transition. |
| #640 | The ratified #591 G2 artifact cites pre-drift line numbers, and implementers will read it as spec | existing goal id 1 | n/a — task membership | `#640` identifies the live hazard on the #630 path; keep it attached as a guardrail task, not as a competing project goal. |
| #692 | Import the design into Claude Design once the React webui has landed and we have transitioned | existing goal id 1 | n/a — task membership | `#692` records his verbatim intent: “Im going to use that to iterate and design new components and make a mobile UI maybe.” It is a downstream consumer, not a current upper-tier definition. |
| #823 | command composer: paste files and images as attachments (React-gated) | existing goal id 1 | n/a — task membership | `#823` records his explicit gate: “webui, only implement in react ... support pasting files and images”; it belongs downstream of the migration and must not be dispatched early. |
| #859 | Evaluate popout windows as the first React surface instead of /research (his ord-160 suggestion; popouts are JS-built documents, not HTML pages) | existing goal id 1 | n/a — task membership | `#859` is his isolated-surface candidate; attach it as an option under the migration rather than silently replacing #630's chosen sequencing. |

The membership set is intentionally small. It is a traceable first slice, not
a claim that every open task has been classified.

## False-green audit

- **Backlog completeness:** closed by the explicit scope below; this proposal
  does not use “every open task has a home” as its success condition.
- **Source paraphrase:** closed by quoting the source beside every goal node;
  id 1's title is copied exactly from the live row and is explicitly protected
  from rewriting.
- **Quiet parent reinterpretation:** closed by placing id 1 under the exact
  successor-surface decision (G2a), not under a node called cleanup, tidying, or
  refactor. The task memberships remain under id 1, with #630 first.
- **Extraction contradiction:** closed by G2a's quoted “refactored into
  modules ... imported to use in dreamhub” route. Nothing here proposes a
  second from-scratch implementation of watch.py; the extraction route remains
  the preferred reuse shape recorded in `DREAMWORK.md`.

## Deliberately not covered

This partial tree does not enumerate the approximately 179 open tasks, create
a goal for every backlog theme, decide between #630's `/research` sequencing
and #859's popout candidate, or assert that the project's future ambitions are
now exhausted. More goals can be added as the human's direction accretes. It
also does not change the empty-state/denominator behavior discussed by #136
and #671, does not edit `DREAMWORK.md`, and does not implement React, dreamhub,
or any task listed above.
