# Lane 645i5 report — the other-store unit (no-production-raw-connect guard)

**Branch:** `glm-645i5`
**Base:** `9c62f384c5dcee7855efb3e7c19d1c78b43b2dae` (= local `master` at dispatch; not moved)
**Verdict:** ✅ LANDED — guard green, 678 tests pass, both red-proofs clean

## What changed

Increment 5 routes every remaining production `sqlite3.connect(` through
`dreamwork_db.core._connect` — the one configured door — and enables the
no-production-raw-connect pytest guard. The standing rule (#645's "all our DB
access should be like this") is now enforceable rather than aspirational, ahead
of increment 6's schema-v3 work.

**7 sites in 6 files routed** (core's READ path = `?mode=ro` + `query_only=ON`
+ `busy_timeout` + `foreign_keys=ON`, `isolation_level=None`; WRITE path adds
WAL + `synchronous=FULL` + parent-durable):

| File | Site | Access | Notes |
|---|---|---|---|
| `user_events/sqlite.py` `open_journal` | :1600 | WRITE | Live dashboard journal writer. Core's `isolation_level=None` (autocommit) is exactly what the Journal needs — it manages its own `BEGIN IMMEDIATE`/`COMMIT`. `_apply_pragmas` still called (idempotent over core). |
| `ud-dw-user-events` `_open_ro` | :114 | READ | Bounded CLI projection. Dropped the hand-rolled `query_only`/`busy_timeout` (core sets them). |
| `dev/journal_consume.py` `_non_listed_events` | :458 | READ | Reports non-listed events (#702). |
| `dev/replay_events.py` `export_journal` | :167 | READ | Source store never mutated. |
| `watch.py` `_review_decisions` | :3472 | READ | Soft-failure (`return {}`) preserved across the `_connect` call. |
| `ud-dw-tasks-migrate` `_verify_import` | :787 | READ | Scratch DB verification. |
| `ud-dw-tasks-migrate` `verify_task_event_chain` | :1263 | READ | Chain recomputation from genesis. |

Each preserves its existing domain API, signatures, and soft-failure behaviour
unchanged — the increment-3/4 precedent.

The guard (`test_no_raw_connect.py`): a pytest assertion that scans every
tracked production Python source (`.py` + extensionless-with-shebang, excluding
tests/`node_modules`/`.dreamwork`) for the `sqlite3.connect(` spelling and
fails on any outside the sanctioned door. A precondition asserts the door
itself exists and holds connects, refusing a hollow pass.

## Re-measurement vs the brief

The brief said raw `sqlite3.connect` remained at **exactly three paths**:
`ud-dw-tasks-migrate`, `ud-dw-user-events`, `watch.py`. The actual count was
**7 sites in 6 files**. The brief's `--include="*.py"` framing missed:

- `user_events/sqlite.py:1600` (the journal writer itself — `open_journal`)
- `dev/journal_consume.py:458` (`_non_listed_events`)
- `dev/replay_events.py:167` (`export_journal`)
- `ud-dw-tasks-migrate` holds **two** sites (:787 and :1263), not one

The three the brief named were correct as far as they went; they were not the
inventory. This is the call-graph rule from the boilerplate in action — the
brief's file list was derived from a partial scan, and the two extensionless
CLIs + the two `dev/` tools + the journal writer itself were the fallout.

## Red-proof — both directions

### Direction 1 (injection goes red on the discriminating message)

Armed `dev/redproof.py begin watch.py`, injected a literal
`_sabotage = sqlite3.connect(str(db))`, ran the guard:

```
FAILED test_no_raw_connect.py::test_no_raw_sqlite_connect_in_production_sources
AssertionError: production sources contain raw sqlite3.connect( calls outside the
sanctioned door (dreamwork_db/core.py); route them through dreamwork_db.core instead:
    watch.py:3476: _sabotage = sqlite3.connect(str(db))  # REDPROOF: raw connect reintroduced
```

Red on the named file:line, not a count. Restored; guard green.

### Direction 2 (false green — the honest limit)

The guard scans for a **spelling**, not a behaviour. Constructed an aliased
connect in `watch.py`:

```python
_raw_open = getattr(sqlite3, "connect")
_sabotage = _raw_open(str(db))
```

This opens a raw connection that bypasses the guard entirely — the lexical
regex `sqlite3\s*\.\s*connect\s*\(` does not match. **The guard PASSED on a
genuinely-broken input.** This is the open false-green, and it is structural:
no purely-lexical scan can catch an aliased or dynamically-constructed
connection. A runtime `PRAGMA`-probe guard would catch some, but that is a
different guard with a different cost. The guard's docstring states this limit
rather than letting the name imply omniscience (`#651`: a guard's message must
not name a mode it cannot detect).

`dev/redproof.py check` → **clean** — 2 injections registered, all restored and
absent from the working tree and the branch's commits.

## Verification

- **`python3 lint.py`** → `clean (6 warning(s))` — the lane bar (the gitignored
  ledger store does not travel into a worktree; `#611`/`#667`).
- **Targeted pytest** (678 passed, 0 failed, 65 subtests, 88.6s):
  `test_no_raw_connect.py test_user_events_sqlite.py test_user_events_cli.py
  test_user_events_http.py test_journal_consume.py test_replay_events.py
  test_watch.py test_ledger_cli.py test_ledger_dispatch.py
  test_ledger_write.py test_ledger_warnings.py test_status_derive.py`

  This is the files I touched plus the caller fallout — every test that
  exercises these connection sites. It includes the 7 HTTP tests the brief
  named (test_watch ×6, test_user_events_http ×1) that start the watch server
  and POST, the journal pragma-permanence test
  (`test_user_events_sqlite.py::test_pragmas_hold_on_fresh_open`), and the
  consume/replay/tasks-migrate CLI tests.

## Rebase

Not needed: local `master` was at `9c62f384` at dispatch and has not moved
(`git rev-parse master` = `9c62f384`). `origin/master` (`ad6ee0d0`) is behind,
as the boilerplate warns. No conflicts.

## What the guard can and cannot decide

**Can:** detect that a production source file contains a literal
`sqlite3.connect(` call site outside the one sanctioned door. That is the
spelling every remaining site in this migration used, so it is the right
backstop for this increment.

**Cannot:** detect an aliased connection (`_c = sqlite3.connect`),
a dynamically-constructed one (`getattr(sqlite3, "connect")`), or a connection
opened through a re-exported symbol. The guard sees source structure, not
runtime behaviour. Stated in the guard's docstring and demonstrated by the
direction-2 red-proof.

## Citations (opened and read)

- **#645** — the task. Increment 5: "Route Journal, replay and consume
  connections through the core … enable the no-production-raw-connect guard.
  The standing rule is real before the first new schema depends on it."
- **#651** — "A guard whose message names a failure mode it cannot detect."
  Relied-on line from the ledger entry: *"It reads as a guard and is
  decoration."* The guard's docstring states its lexical limit rather than
  implying it detects aliased connects.
- **#759** (the frozen-subject method, cited by increments 2–4) — not directly
  used here; this increment routes connections rather than moving SQL, so there
  is no "before" implementation to freeze. The parity evidence is the 678
  passing tests against the routed connection, not a snapshot comparison.
- Lesson: **"A green reading is evidence only if you know what produced it"**
  (lessons.md:3317) — the direction-2 false green is the specific instance: the
  guard's green is produced by a lexical regex, and an aliased connect produces
  a green for the wrong reason.

## DOGFOOD REPORT

1. **The brief's site count was wrong, and the boilerplate's call-graph rule
   caught it.** The brief said "exactly three paths" and named
   `ud-dw-tasks-migrate`, `ud-dw-user-events`, `watch.py`. The actual count was
   7 sites in 6 files — the two extensionless CLIs were each counted as one
   path but `ud-dw-tasks-migrate` holds two sites, and `user_events/sqlite.py`
   (the journal writer), `dev/journal_consume.py`, and `dev/replay_events.py`
   were omitted entirely. The brief's `--include="*.py"` framing in its
   measurement caused it to miss the extensionless CLIs, and it appears to have
   counted only the three named in its own prose. This is exactly the failure
   the boilerplate's "call-graph rule" section warns about: *"Twice my briefs'
   file lists were derived from the diff I expected rather than from the call
   graph of what was moving."* The fix was to re-measure with a scan that
   includes extensionless shebang scripts and `dev/`.

2. **The brief's "Measured before dispatch" timestamp (06:17) was honest but the
   measurement was incomplete.** It said "Re-measure this yourself — the tree
   moves." The re-measurement found 4 additional sites. This is not a criticism
   of the instruction (it was correct to say re-measure); it is a note that the
   original measurement's grep was too narrow, and a future brief measuring the
   same property should grep extensionless files explicitly.

3. **`dev/redproof.py` worked exactly as the boilerplate describes.** The
   `begin`/`restore`/`check` cycle caught the two injections cleanly, and
   `check`'s scan of branch commits (none held an injection) was the right
   backstop. No friction.

4. **The guard-in-pytest decision was correct.** Putting it in `lint.py` would
   have collided with the concurrent lane editing `lint.py`/`test_lint.py`
   (the brief's stated reason). No merge-conflict risk encountered.
