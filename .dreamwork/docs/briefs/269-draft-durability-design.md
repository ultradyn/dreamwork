# Brief — #269: he loses drafts on review pages — the design for durable, cross-tab text

Repo: `ud-dreamwork`. Worktree: **`.worktrees/drafts`**, branch **`wt/drafts`**. Do not push, do not merge.
**Never use `attn`.** **Do not write `.dreamwork/handoffs.md`** — the coordinator writes it at merge time.
Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are**.

## Why this one matters

Read `#269` in `.dreamwork/tasks.md`. **He escalated it to P0 and marked it next-up himself** (2026-07-27 21:35
via the composer): *"draft answers to questions on review pages can be lost."* That is his text disappearing —
the same class as `#446` (a second Answer overwriting the first, filed tonight), and it ranks above cosmetics.

His stated scope: composer, answer/note boxes, future chat inputs and **every later user text field** get a
stable **logical input ID**; autosave before submission into one **project-partitioned** IndexedDB draft store;
restore across reloads and route transitions; synchronise the same logical input across tabs so several views
behave as one box. Plus ownership/conflict/clear-on-durable-receipt rules, privacy and retention, and migration
from the existing composer `localStorage`. **One deep module every future input consumes.**

## This is DESIGN ONLY

Do **not** implement. `watch.py` is held by another lane tonight, and more importantly this is a module contract
that several open tasks will build against (`#241`'s mount contract, `#177`'s autogrow, the answer boxes) — a
half-built store is worse than a designed one. **If you find yourself editing `watch.py`, stop.**

**Deliverable: `.dreamwork/docs/plans/draft-durability-design.md`** plus a `doc-map.md` row.

## What the design must answer

- **The logical input ID.** What identifies "the same box" across a reload, a route change, and a second tab —
  and what happens when the thing it is attached to (a question, a review page) no longer exists. Getting this
  wrong is how a draft is restored into the wrong box, which is worse than losing it.
- **Where the truth lives**: IndexedDB store shape, project partitioning (the loop runs against different
  targets), and how it relates to the `localStorage` drafts that exist today — **including the migration**, and
  what happens to a draft written by the old code.
- **Cross-tab coherence.** Two tabs, one logical box: who wins, and when. Name the mechanism (BroadcastChannel,
  storage events, a lock) and its failure mode when a tab is suspended or offline. **Last-write-wins on a text
  field the human is typing into is a data-loss design** — say what you do instead.
- **Clear-on-durable-receipt.** A draft may only be dropped once the real write is *witnessed*, not once a
  request is sent. **`#263`'s receipt boundary is exactly this question** and it is **behind a gate that is
  his to open — you must NOT build any of `#263`'s lanes E, G or H.** Reference it, state the dependency, and
  design so the receipt rule is pluggable rather than assumed.
- **Privacy and retention.** How long, how much, and what a human-visible "forget this" looks like. His drafts
  are his words; retention is a promise, not a default.
- **Failure modes**: quota exceeded, IndexedDB unavailable (private windows), a corrupt record. A draft store
  that throws while he is typing is worse than none.
- **What is NOT worth doing**, with reasons. If a much smaller mechanism captures most of the loss (e.g. save
  on blur plus a beforeunload flush), **say so with the trade** — the goal is that he stops losing text, not
  that a module exists.
- **The seams**: what `#241`, `#177` and the answer boxes each consume, as a named interface, so those tasks
  can be written against it without re-deciding.

## Done means

1. The design exists, answers every bullet, and each recommendation names what it costs as well as buys.
2. A `doc-map.md` row.
3. **An implementation order**: the smallest first increment that stops the actual reported loss (drafts on
   review pages), and what it does not yet cover. He is losing text now; a design whose first useful increment
   is three tasks deep has failed him.
4. **The `#263` dependency stated**, with the gate named and nothing behind it built.
5. **A review artifact with an `#ask`** if a decision is genuinely his — cross-tab conflict policy and
   retention are the likely candidates. `.dreamwork/review/src/269-draft-durability.html` via
   `python3 review_artifact.py build`, `#ask` above the derived fold (`node dev/capture/above_fold.mjs …`,
   which derives it now — `#432`). **Note the table trap fixed tonight (`c19107a`)**: the template's
   `table{min-width:max-content}` sizes tables to unwrapped content — he could not read the last one — so set
   `min-width:0;width:100%;table-layout:fixed` and check 390px. If nothing is genuinely his, **skip it and say
   so**; a decoy ask is worse than none.
6. Report the exact `questions.md` entry text you want filed. **Do not edit `questions.md`.**
7. `python3 lint.py` clean; `python3 -m pytest -q -p no:randomly` passes (1089 at dispatch). **Do not run the
   full `just test`.** Do not touch :35110, the heartbeat, the monitors, or the loop.

## Files

Yours: `.dreamwork/docs/plans/draft-durability-design.md`, `.dreamwork/docs/doc-map.md`, and
`.dreamwork/review/src/269-draft-durability.html` if you ship one.

**Not yours:** `watch.py`, `justfile` (**held by a live lane**), `review-artifact.template.html` and other
`.dreamwork/review/src/**` (**held for `#436`**), `dev/capture/*`, `file-formats.md`, `lint.py`,
`.dreamwork/tasks.md`, `.dreamwork/questions.md`.

## Practical

2 threads. `git add <newfiles>` then `git commit --only <paths>` — **never `git add -A`**. **Commit before you
finish.** **Push back with reasons if any of this is wrong** — including if the right first move is a ten-line
save-on-blur fix rather than a module. That would be a welcome finding, not a failure to follow the brief.

## Report

Which model you are; the logical-ID answer; the cross-tab conflict policy and why it is not last-write-wins;
the clear-on-receipt rule and its `#263` dependency; the smallest first increment that stops the reported loss;
what you recommend NOT doing; whether you shipped an artifact plus the derived fold and `#ask` top; the exact
`questions.md` text; and confirmation you implemented nothing, ran no full `just test`, and never touched
:35110 or anything behind the `#263` gate.
