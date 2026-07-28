# Brief — #402(a): `status.json`'s `dreamers` array has no stated shape, and the syncer never touches it

Repo: `ud-dreamwork`. Worktree: **`.worktrees/dreamers`**, branch **`wt/dreamers`**. Do not push, do not merge.
**Never use `attn`.** **Do not write `.dreamwork/handoffs.md`** — the coordinator writes it at merge time.
Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are**.

Lane-owns: status_sync.py, test_status_sync.py, file-formats.md

## The defect, found by using it

Read `#402` in `.dreamwork/tasks.md`. Three parts, and **only (a) is yours**:

- **It goes stale in the one direction that costs parallelism.** `#396`/`#398` had **landed** and were still
  listed as owning `review_artifact.py`, `file-formats.md`, `dev/capture/fixture/**`, `lint.py`,
  `test_lint.py`. `status_sync.py` recomputes `queue` and `current_task_ids` from live `pgrep` but **never
  touches `dreamers`**, so ownership only accumulates. **A stale entry says a free file is owned**, so the
  coordinator declines a dispatch it could have made — `#264` measured file contention as the binding
  constraint on how much runs at once, and this manufactures it.
- **It crashed on a mixed-type id.** Entries carry `"task": 396` (int); writing `"task": "401"` made
  `sorted()` raise `TypeError: '<' not supported between instances of 'str' and 'int'` and `just status-sync`
  exited 1. Loud, so not the worst kind — but the sync stops and the drift resumes silently from there.
- The `#401`-family sub-instances noted in the entry: read them, and say which your fix covers.

## Yours — (a) only

1. **State the shape** of a `dreamers` entry in `file-formats.md`, in the same commit as the code that relies
   on it (the standing rule, checked by `lint.py`). Ids are the sharp edge: pick **one** type and say what
   happens to the other on read — this file is written by more than one hand, so *tolerate on read, normalise
   on write* is the shape that survives.
2. **Make `status_sync.py` reap stale `dreamers`** the way it already recomputes `queue`: an entry whose pid
   is gone, or whose task is no longer in the ledger's open section, is not an owner. **Ask the live system,
   not memory.** Use `watch.parse_ledger` / `dev/ledger.py` for open-ness — **do not hand-roll a ledger
   parser and never split on the string `## Recently landed`**, which also appears in an entry's *prose*;
   five hand-rolled parsers have been wrong here and one corrupted the file tonight. Anchor with
   `^## Recently landed$` if you locate sections yourself.
3. **Never crash on a malformed entry.** A syncer that exits 1 stops protecting everything after it. Skip,
   report, and keep going — and say in your report what it now does with junk.

**Not yours:** the dashboard rendering of `dreamers`, and any change to what the coordinator writes at
dispatch time (that is the second half of `#402` — report a recommendation instead).

## Done means

1. `file-formats.md` states the entry shape including the id-type rule.
2. `status_sync.py` reaps entries whose pid is dead or whose task has landed, **without** removing live ones.
3. A **mixed-type id no longer crashes** the sync.
4. **Red-first, and name the production line.** Write the test, reinstate the bug (a dead-pid entry that
   survives; a `"401"` string beside a `396` int), watch it fail. **A green red-run is a finding, never a
   relief** — if it stays green your test is not reaching the code, and that is the more valuable result.
5. **Assert your test's precondition**, derived at runtime: if it needs a pid that is genuinely dead, prove it
   is dead in the test rather than trusting a number, and if it needs two ids of different types, derive both.
   A literal tuned to today's file is a check with an invisible expiry — bitten repeatedly here, twice today.
6. `python3 lint.py` clean; `python3 -m pytest -q -p no:randomly` passes (1078). **Do not run the full
   `just test`.** Do not touch :35110, the heartbeat, the monitors, or the loop, and **do not write the live
   `.dreamwork/status.json`** — test against a fixture or a copy. It describes the running session and the
   coordinator owns it.

## Files

Yours: `status_sync.py`, `test_status_sync.py`, `file-formats.md`.

**Not yours:** `watch.py`, `justfile` (**a live lane holds both for `#177`**), `lint.py`, `dev/ledger.py`,
`dev/capture/*`, `.dreamwork/status.json` (live), `.dreamwork/tasks.md`, `.dreamwork/questions.md`.

## Practical

2 threads. `git commit --only <paths>` — **never `git add -A`**. **Commit before you finish.** A trailer if
this changes what an install must do (`Migration:` / `Feature:`).

## Report

Which model you are; the shape you documented and the id-type rule; what the syncer now reaps and how it
decides; what it does with junk; the exact production line whose reversion reds your test; the preconditions
you asserted; and confirmation you never wrote the live `status.json`, ran the full `just test`, or touched
:35110.
