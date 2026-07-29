# The SQLite ledger migration — from Markdown to one store, safely

**Tasks:** #294 (migration, cutover, rollback, git-history import, `tasks.md.deprecated`,
mixed-writer freeze). Consumers: #287, #289, #342, #281's badge, #229/#270's CLI seam
**Status:** design ratified 2026-07-29 05:48 (`rec` on R1–R4 + C1). **Increments 1–5
landed:** schema + seeded sequence (`ledger_store.py`), `--dry-run`, `--backup`,
`--import`, `--verify`, `--import-history` (first-sight synthetic events,
`actor='migration:git'`, hash chain). **Increment 6 (R4) landed:** `--cutover` (the
7-step ordering: #263 lease reused, freeze, import+verify under lease, one-way watermark
reader-flip, rename+shim, watch-events line, release) and `--rollback` (restore + re-run
forward, never restores a legacy direct writer). Red-first fixtures 6, 8, 9, 10
landed in `test_tasks_migrate_cutover.py`. **Still coordinator-owned:** the live
execution, the lint.py #362 retirement + inverse-invariant replacement, and the
re-pointing of watch.py/lint.py/task_origins.py/status_sync.py consumers at `ledger_parse.source_of_truth`.
**Date:** 2026-07-29
**Depends on:** `user-event-journal.md` (#263 — contract approved `"rec"` 01:27; lanes
A–F and E merged, G/H authorised, **not yet fully landed**) and
`task-transition-boundary.md` (#264 — boundary approved in full, T1–T4, 02:45).
**Consumes but does not re-derive:** `task-store-schema.md` (#346 — entity schema +
read-only CLI; S1–S4 ruled 01:23).

---

## What the dependencies actually settled — read this before anything below

The brief asks to establish what `#264` and `#263` *actually* settled, and to design
only on what is met. Both are met **as designs**, and this document builds on both
without re-deriving them:

- **#263 (user-event journal).** Contract approved. One SQLite database at
  `.dreamwork/user-events.sqlite3` (gitignored), WAL, `synchronous=FULL`. Receipts are
  immutable; `202` follows journal commit; claims/leases/CAS; a ternary
  `Applied|NotApplied|Unknown` proof; a hash-chained event log with its own ordinal. Its
  cutover section (§"Migration and cutover") is the template this migration copies:
  versioned, quiesced, exclusive cutover lease, drain in-flight, prove no old process owns
  the generation, mixed-version fail-closed, rollback is journal-aware and **forbidden to
  restore a legacy direct writer**.
- **#264 (task-transition boundary).** Approved in full. A task transition is one row in
  its own append-only `task_event` log **in the same SQLite file** as #263's journal,
  appended **in the same transaction** as the CAS that moves `task_state`. Burndown and
  the dashboard status section become **queries**. `status.json` **loses** `queue`,
  `current_task_ids`, and per-agent `task_ids` (T2, rec). A canonical byte form is defined
  on day one so a committed text export is a provable projection (T3, rec). His Q2 answer
  `(c)`: a machine-local gitignored `.jsonl` log for **recovery and reprocessing**, and
  cross-clone history is a later deployment choice, not a v1 requirement.
- **#346 (entity schema + read-only CLI).** S1–S4 ruled. `task(id INTEGER PRIMARY KEY)`
  with ids permanent and never reused; `entry` separated from `task` only where combined
  entries survive (S1 split, so today there is no join — the three combined entries were
  split at `9fec0bf`); `priority` closed with a `priority_uncertain` bit (S2); `type` a
  lookup table (S4); `related` n:n symmetric, `depends` directed. Read verbs
  `list|get|count|reviews` are #346's; write verbs `grab|release|cycle|file|hold|history|`
  are #264's.

**One dependency is genuinely unmet, and it is implementation, not design:** #263's lane
**H** (the mixed-version / version gate, increments 34–35) is authorised but not landed.
Cutover needs the mixed-writer freeze, and lane H is what makes a mixed-version writer
**fail closed before accepting a write**. So **the design below is complete; shipping it
is gated on #263 lane H landing**, exactly as #263's own approval gate says its approval
"does not authorise implementation, migration, deployment." Nothing in this document
assumes the store exists yet.

This document owns exactly what #264's closing section says it deliberately did **not**
decide: *"the migration and its cutover ordering, the import of git history into
`task_event` (whether the revisions become synthetic events, and with what `actor`),
rollback, `tasks.md.deprecated`'s frontmatter, mixed-writer freeze."* The entity schema is
#346's; the transition boundary is #264's; the receipt journal is #263's. This is the
**how we cross over** design.

---

## The recommendation

> A **single staged, human-readable migration script** — `dreamwork tasks migrate` — that
> dry-runs against the production parser, reports exact counts/IDs/digests/conflicts,
> backs up, imports atomically into the one SQLite file, verifies by replay, and cuts over
> behind an **exclusive cutover lease** that freezes every writer (coordinator, `watch.py`,
> any lane) for the duration. The id sequence lives **in the store** (`AUTOINCREMENT`,
> seeded from the Markdown `Next id` and verified). Git history is imported as
> **first-sight synthetic events** (`actor = 'migration:git'`) so the burndown survives in
> the store, with no claim to intra-life precision the Markdown never had. At cutover,
> `tasks.md` is renamed to `tasks.md.deprecated` carrying a #458 migration notice, and a
> one-line `tasks.md` shim is left so a stale agent still reading that path **self-heals**
> rather than silently losing work. Rollback restores the backup file but **never restores
> a legacy direct writer** — it re-runs the migration forward, because #263 forbids the
> reverse.

Everything else is why, and what has to be true for it to hold.

---

## Findings that shape the migration

Each is measured against the readers the system already uses (`watch.parse_ledger`,
`watch.ledger_entries`), never a fresh regex — three hand-rolled scans of this file have
produced confident wrong numbers tonight. Numbers are point-in-time (2026-07-29) and the
migration script re-derives every one rather than trusting these.

### F1 — the two truths already disagree, and the disagreement is the migration's reason

Measured 2026-07-29 through `watch.parse_ledger` and the live `status.json`: the ledger
reads **144 open / 219 landed** (0 overlap), while `status.json`'s `queue` is an LLM's
hand-written estimate that has disagreed with the ledger by 9–40 all session (#264's F1,
#362's WARN). This is the exact drift #264's T2 retires by deleting those fields; the
migration is the act that actually deletes them. A migration that left `status.json`'s
task-derived fields in place would ship #264's boundary on paper while preserving the
second truth the boundary exists to remove.

### F2 — ids are permanent, and the Markdown already hands out the next one

`tasks.md`'s header carries `Next id: **470**` today. The contract (file-formats.md,
#97) is that ids are permanent and never reused, and the ledger hands out the next one.
After import, the store must (a) accept every existing id verbatim, (b) continue from
470, and (c) never hand out an id that collides with an imported one. SQLite
`AUTOINCREMENT` does all three if it is **seeded** from 470 and the seed is verified
against `MAX(id)+1`, not trusted.

### F3 — git history already encodes the burndown, but only as first-sightings

`ledger_series` (`watch.py`) walks every commit touching `tasks.md` and takes first-sight
arrivals and landings. Today: **578 commits** touch the ledger. That walk is already the
burndown's source — #264's F4 measured it and ruled (T3) that a committed text export
makes cross-clone history a deployment choice. The honest constraint: the Markdown records
**arrivals and landings**, not the ~18 intermediate causes (#264's table). No migration
can reconstruct per-tick state changes that were never written down. So a git-history
import can be **first-sight only** and must say so, rather than fabricating precision.

### F4 — three readers parse `tasks.md` today, and cutover renames all of their input

#346 measured it: `ledger_entries` has two implementations (`lint.py`, `watch.py`) and
three callers (`lint.py`, `watch.py`, `task_origins.py`). #352 (standardise them into one
module) is the ruled prerequisite and is **not yet landed**. So at cutover, renaming
`tasks.md` to `tasks.md.deprecated` breaks three parsers unless they have been re-pointed
at the store first. **#352 is a hard prerequisite to cutover**, not to this design: the
migration script can be written against the current duplicated parser, but the cutover
step that flips the readers must come after #352 unifies them, or lint keeps a Markdown
parser aimed at a deprecated file and "slowly becomes a checker of history" (#346).

### F5 — a stale agent still reads `tasks.md`, and the migration must reach it

#458 (landed, `migration_notice.py`) exists for exactly this: a long-running loop that
never re-initialises holds its routine in context and keeps reading the data file every
tick. The moment `tasks.md` stops being authoritative, an old-protocol agent keeps
*writing* to it and its work is silently lost. #458's mechanism is an HTML-comment notice
at byte 0, pointer-only, single-slot. The migration must write one, and it must live
where the stale agent looks.

---

## The migration script — `dreamwork tasks migrate`

Readable, user-modifiable, staged. Each stage prints exact counts and exits non-zero on
any surprise, so a human reading the output can see what the import will do **before** it
does it. The script uses the production parser (#352's unified module once it lands; until
then, `watch.ledger_entries`/`parse_ledger`), never a regex of its own.

```
dreamwork tasks migrate --dry-run            # parse + report; writes nothing
dreamwork tasks migrate --report <path>      # write the full report to a file
dreamwork tasks migrate --backup <dir>       # copy tasks.md + the DB to <dir>, fsync
dreamwork tasks migrate --import             # atomically populate the store
dreamwork tasks migrate --verify             # replay import, diff, exit non-zero on divergence
dreamwork tasks migrate --cutover            # the lease + rename + notice (see §Cutover)
dreamwork tasks migrate --rollback <backup>  # restore the file; never restore a legacy writer
```

### Stage 1 — dry-run / report (writes nothing)

Parses every open and landed entry through the production reader and reports:

- entry count and id count, **derived and asserted to differ only where a combined entry
  is intended** (today they are equal because the three combined entries were split; the
  report re-derives both rather than trusting equality — #346's finding 2);
- the exact histogram of `priority` bands (including any surviving `priority_uncertain`
  cases), `type` lookup values, and `origin` markers;
- every entry whose band/type/origin could not be unambiguously read, with the offending
  substring;
- every "blocked on #N" phrase not convertible to a `depends` edge, with the evidence
  substring;
- a **digest per entry** (SHA-256 of the verbatim body), so a later `--import` can prove
  it carried the same bytes;
- the `Next id` from the header, and the `MAX(id)+1` over parsed ids, **asserted equal** —
  a header that has drifted below `MAX(id)+1` is a data bug the migration must stop for,
  not paper over.

Exits non-zero only on a **parse failure**, never on an unclassifiable entry — those are
output, not errors (#346's ruling). This stage is useful on its own today and is how the
schema gets falsified before anything depends on it.

### Stage 2 — backup

Copies `tasks.md` and the SQLite database (if it exists) to a timestamped backup
directory, `fsync`s, and refuses to proceed if the backup did not land durably. This is
the rollback substrate; it is the `cp`+`fsync` #263's cutover relies on, not a git
commit (the working tree is explicitly not authoritative for the burndown, #264's F4).

### Stage 3 — atomic import

Imports into the **live store inside one `BEGIN IMMEDIATE … COMMIT`**, because #264's F6
measured that the `task_event.receipt_id → receipt` foreign key can only exist in one
database file. Building a separate DB and swapping would orphan that constraint. Inside
the transaction:

- `INSERT INTO entry/task/related/depends/review_decision` for every parsed record, with
  verbatim bodies and the per-entry digest in a side column for verification;
- `INSERT INTO task_event` synthetic rows for git-history first-sights (see §Git history),
  each `actor = 'migration:git'`, chained;
- seed `sqlite_sequence` (or the explicit next-id row) to the verified `Next id`;
- write a single `migration` watermark row naming the import's terminal ordinal and the
  backup path.

`PRAGMA foreign_keys=ON` is set by the adapter in one place and asserted by a test
(#264's footgun table). A failed import leaves the store untouched because the whole
population is one transaction.

### Stage 4 — verify

Replays the import into a temporary table and diffs against the live `task`/`entry`/state
row-for-row, including digests; re-derives the open/landed id sets from the store and
asserts they equal the sets the production parser returned from `tasks.md` **before**
rename. Exits non-zero on any divergence. This is #264's `rebuild --verify` applied to
the import specifically.

### Stage 5 — cutover (see §Cutover ordering)

The only stage that renames a file or deletes a field. It is deliberately separate from
`--import` so a human can run 1–4, read the report, and decide.

---

## Cutover ordering and the mixed-writer freeze

Copies #263's cutover section stage for stage, because the hazard is the same (two
generations of writer must never overlap) and the cure is already approved there:

1. **Acquire an exclusive cutover lease** on the target (the same lease primitive #263's
   claim laws define). Hold it for the whole window.
2. **Freeze every writer.** Quiesce the coordinator, drain in-flight `watch.py` request
   handling and any live lane, and prove no process still owns the target generation.
   This is the "mixed-writer freeze" in #294's acceptance scope. **It is not a `pkill`**
   — it is the lease plus the version gate (#263 lane H) that makes a mixed-version
   writer fail closed before accepting a write.
3. **Run stages 1–4** (dry-run, backup, import, verify) under the lease.
4. **Flip the readers.** After #352 unifies the parser, repoint the single reader at the
   store; until #352 lands, cutover cannot complete (F4). `watch.py`'s `ledger_series`,
   `parse_ledger`, the `/tasks` badge, and the dashboard status section all become store
   queries (#264's T2).
5. **Rename + notice** (see §`tasks.md.deprecated`).
6. **Write the cutover watermark** into the store and emit one `watch-events.log` line.
7. **Release the lease.** New writes go through `dreamwork tasks file|grab|cycle`, each
   one transaction appending `task_event` and CAS-ing `task_state` (#264).

**Mixed-version fail-closed is the load-bearing safety property, and it is #263 lane H.**
Until H lands, an old `watch.py` could keep writing `tasks.md` after cutover and the store
would never know. So **cutover is sequenced after #263 lane H**, full stop. This design
does not invent a second version gate; it consumes #263's.

---

## `tasks.md.deprecated` and the notice a stale agent reads

His #294 words: *"preserve the old ledger as `tasks.md.deprecated` with YAML frontmatter
declaring deprecation and pointing to canonical task-access and recovery instructions;
never delete it automatically."* #458's mechanism: a notice in the hot file a stale agent
still reads, so it self-heals. Those two combine into one shape:

- **Rename** `tasks.md` → `tasks.md.deprecated`, carrying its full content verbatim plus a
  leading deprecation block (YAML frontmatter, per his words) naming the canonical access
  path (`dreamwork tasks …`) and the recovery procedure (`tasks migrate --rollback
  <backup>`).
- **Leave a one-line `tasks.md` shim** carrying only a #458 migration notice
  (`<!--dreamwork-migration-notice … migration: ledger-sqlite … -->`) pointing at the
  store and at `tasks.md.deprecated`. A stale agent reading `tasks.md` every tick finds
  the notice and switches to the CLI; an agent reading `tasks.md.deprecated` finds the
  deprecation block. Both paths self-heal. **Never delete `tasks.md.deprecated`
  automatically** — his standing rule.

The shim is the resolution to the tension between "rename it" (his #294) and "the notice
must live where the stale agent looks" (#458): the content moves to `.deprecated`, the
notice stays at the path that is read every tick.

---

## Git history import — first-sight synthetic events

Whether the 578 revisions become synthetic `task_event` rows, and with what `actor`, is
#264's explicitly-open question. The principled answer, from F3:

**Import first-sight arrivals and landings as synthetic events, `actor =
'migration:git'`, and nothing more.** `ledger_series` already computes exactly these
first-sights; the migration replays its output as one `filed_from_*` event per task at
its first-seen commit time and one `landed` event at its first landed sighting. Each row
is hash-chained like any other (#264's construction, distinct `domain_tag`). What is
**not** imported: the ~16 intra-life causes (#264's table) the Markdown never recorded —
a `claimed_by_agent` mid-history is not reconstructable and must not be invented.

Consequence, stated plainly: the store's burndown matches `ledger_series`'s shape
(arrivals/landings over time, open level as a step) but does not carry per-tick state
history before cutover. After cutover, every real transition is a real event. This is
honest about what the data held, and it is what makes T3 (committed text export) a real
projection: the chain re-verifies over synthetic + live events alike.

---

## What happens to `lint`'s drift check (#362)

`check_status_agrees_with_ledger` (#362, `4ce04e0`) WARNs when `status.json`'s `queue` /
`current_task_ids` disagree with the ledger. At cutover, T2 **deletes those fields** from
`status.json`, so the comparison the check measures no longer exists — it would become
vacuous, examining nothing (the failure mode this repo keeps paying for). The design's
decision:

- **Retire `check_status_agrees_with_ledger` at cutover** and replace it with the inverse
  invariant: the three retired fields must stay **absent** from `status.json`. That is the
  same shape as #303's append-only `.status-keys` memo — a field that reappears is a
  regression, not a drift. The check fails closed on reappearance rather than silently
  re-measuring a comparison that has one source now.
- The burndown/status **disagreement itself disappears** by construction: there is one
  source (the store), and burndown is a query over it (#264). There is nothing left to
  compare, which is the whole point.

---

## IGC — the decisions worth rivals

Context (the C): the ledger is moving from one committed Markdown file (single writer by
convention, 578 commits of history) to one gitignored SQLite store shared with #263's
journal. The migration must not lose an id, an entry, or a burndown point, and must be
rollback-able without restoring the hazard it removed. Goals are binary pass/fail.

**G1** two writers can never mint the same id · **G2** an imported id and a future id
never collide · **G3** the id seed is verified, not trusted · **G4** the sequence
survives a crash mid-`file` · **G5** rollback restores data without restoring a legacy
direct writer · **G6** a stale agent reading `tasks.md` self-heals rather than losing work ·
**G7** the migration is readable and modifiable by a human before it runs

### M1 — where the id sequence lives after import

| Idea | All | G1 | G2 | G3 | G4 | G5 | G6 | G7 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| A · `AUTOINCREMENT` in the store, seeded from `Next id`, verified `== MAX(id)+1` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| B · keep `Next id` in `tasks.md.deprecated`'s header as authority | ✘ | ✘ | ✔ | ✘ | ✔ | ✔ | ✔ | ✔ |
| C · an explicit `next_id` row written alongside each `filed` event | ✘ | ✔ | ✔ | ✔ | ✘ | ✔ | ✔ | ✘ |

- **A** is the survivor. The store is the single place that hands out ids; the seed is
  checked against `MAX(id)+1` so a drifted header stops the migration (F2); `AUTOINCREMENT`
  is crash-safe inside the `filed` transaction (G4); and it adds no second truth. ✔ on G7
  because the seed rule is one readable line.
- **B** is refuted on **G1 + G3**: two places (the deprecated header and the store) can
  disagree, and "trust the header" is exactly the drift #362 measured — a header that has
  already drifted below reality would mint a colliding id silently.
- **C** is refuted on **G4 + G7**: a `next_id` row written beside the event is a second
  derived truth that can lag the event under crash, and it is machinery a human must
  maintain where `AUTOINCREMENT` is one declarative line. Decisive error: a crash between
  the `next_id` write and the `filed` commit leaves the sequence advanced past an id that
  was never used.

### M2 — cutover ordering and the mixed-writer freeze

| Idea | All | G1 | G2 | G3 | G4 | G5 | G6 | G7 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| A · exclusive cutover lease + #263 lane-H version gate; freeze all writers; flip readers after #352 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| B · "big bang": one process does parse+import+rename with no freeze | ✘ | ✔ | ✔ | ✔ | ✔ | ✘ | ✘ | ✔ |
| C · shadow run: keep Markdown authoritative, mirror into the store, flip later | ✘ | ✔ | ✘ | ✔ | ✔ | ✘ | ✘ | ✘ |

- **A** is the survivor and is #263's own cutover, reused. The lease + version gate make a
  mixed-version writer fail closed (G1/G2 hold under concurrency); rollback restores the
  backup file then re-runs forward (G5); the notice reaches the stale agent (G6).
- **B** is refuted on **G5 + G6**: with no freeze, a concurrent writer can mutate
  `tasks.md` mid-import and the backup no longer represents what was imported; and a stale
  agent keeps writing Markdown after the rename with no notice to stop it — silent work
  loss, which is #458's entire motivating case.
- **C** (dual-write shadow) is refuted on **G2 + G5 + G6 + G7** and is the most important
  refutation: it is **the second derived truth #264 exists to remove**, preserved
  indefinitely. His #294 amendment is explicit — *"no second derived truth"* — and a
  shadow run is that truth by another name. It also never reaches a decision to flip
  (G7 — a human cannot read "when is it safe to stop shadowing").

### M3 — git history as synthetic events

| Idea | All | G1 | G2 | G3 | G4 | G5 | G6 | G7 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| A · import first-sight arrivals+landings, `actor='migration:git'`, chain them | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| B · import nothing; store starts at cutover; burndown-before-cutover stays on git | ✘ | ✔ | ✔ | ✔ | ✔ | ✔ | ✘ | ✔ |
| C · reconstruct every intermediate cause from prose | ✘ | ✘ | ✔ | ✘ | ✔ | ✔ | ✔ | ✘ |

(goals read as: G3 "the burndown the store reports is honest about its precision";
G6 repurposed here as "the store's burndown is self-sufficient for the history git
holds". The other goals are trivially held by all three and omitted from the prose.)

- **A** is the survivor. First-sight is exactly what `ledger_series` already computes (F3);
  synthetic events are chained like any other so T3's export re-verifies; and the
  `actor='migration:git'` tag makes them auditable as reconstruction rather than lived
  events. ✔ on the precision goal because it imports **only** what the Markdown recorded.
- **B** is refuted on the precision goal: a store whose burndown is flat-before-cutover
  silently understates the loop's history on any clone that does not also walk git, which
  is precisely the cross-clone case T3 exists to make optional.
- **C** is refuted on **G1 + G3 + G7**: the Markdown did not record intra-life causes, so
  "reconstructing" them is fabrication (G3 — dishonest precision), and a script that
  guesses 18 causes per task is not readable (G7).

### M5 — `tasks.md.deprecated` + the stale-agent notice

| Idea | All | G1 | G2 | G3 | G4 | G5 | G6 | G7 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| A · rename content to `.deprecated` (YAML deprecation block); leave a one-line `tasks.md` shim with a #458 notice | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| B · rename to `.deprecated`, no shim; rely on agents re-initialising | ✘ | ✔ | ✔ | ✔ | ✔ | ✔ | ✘ | ✔ |
| C · keep `tasks.md` authoritative; store is a read cache | ✘ | ✔ | ✘ | ✔ | ✔ | ✘ | ✔ | ✘ |

- **A** is the survivor and is the resolution of his #294 rename + #458's self-heal. The
  content he said never to delete lives at `.deprecated`; the path a stale agent reads
  every tick carries the notice that switches it to the CLI (G6). ✔ on G5 because
  rollback restores the file from backup and re-points the shim.
- **B** is refuted on **G6**: an agent that never re-initialises (the exact case #458 was
  filed for) keeps reading `tasks.md`, finds it gone, and either crashes or silently keeps
  writing to a `tasks.md` it recreates — work loss with no notice.
- **C** is refuted on **G2 + G5 + G7**: it is the dual-write shadow M2-C refuted again, and
  keeping Markdown authoritative means the store is never the truth, so the migration never
  finishes.

(There is no M4 — the migration-script shape is not a rival: pure SQL cannot parse
Markdown, so the importer is a staged script using the production parser. The atomicity
mechanism *inside* the script — one `BEGIN IMMEDIATE` population vs. a temp-DB swap — is
settled by #264's F6: one file, so import-into-live inside one transaction.)

---

## Rollback

Rollback restores the backup file (`tasks.md` from stage 2) and the pre-cutover database,
then **re-runs the migration forward** rather than restoring a legacy direct writer. This
is #263's rule verbatim — *"Rollback never deletes/renumbers receipts"* and *"restoring a
legacy direct writer is forbidden"* — applied to tasks. The decisive point: a rollback
that re-opened direct Markdown mutation would reintroduce the single-writer-by-convention
hazard #264 removed, and the store's `task_event` chain would diverge from the file on the
very next hand-edit. So rollback is **migration-aware**: it restores data, then re-imports
under a fresh lease, preserving every event the store already chained. If the store itself
is corrupt, rollback falls back to the file backup plus `tasks migrate --import` from
scratch — the chain is rebuildable by definition (#264).

---

## Red-first acceptance fixtures

Each is stated as *the production line that must change for this to fail*, because checks
in this repo have passed over the thing they were named for, and a green red-run is a
finding.

1. **No id is lost or duplicated.** Import; assert the store's id set equals the parser's
   id set on `tasks.md` before rename. *Break by dropping the verbatim-id INSERT — the test
   must fail on a missing or duplicated id, and the two sets must be derived at runtime,
   not pinned (F1's 144/219 is today's number, not a constant).*
2. **The id seed is verified, not trusted.** Drift the header's `Next id` below `MAX(id)+1`;
   `--dry-run` exits non-zero naming the drift. *Break by trusting the header — must pass
   on a drifted header, which is the bug.*
3. **Import is one transaction.** Kill the process mid-`--import`; the store is unchanged
   (verify by re-running `--dry-run` against the store's projection). *Break by splitting
   population into two transactions — an event with no entry must survive.*
4. **Verify catches a corrupt import.** Corrupt one imported body; `--verify` exits
   non-zero naming the entry and digest. *Break by having verify read the store instead of
   replaying — a verify that copies its own target passes on any corruption.*
5. **Git first-sights match `ledger_series`.** After import, the store's per-bucket
   arrivals/landings equal `ledger_series`'s over the same history. *Break by importing
   from current state instead of first-sight — the early buckets must go to zero, which is
   F3's whole point.*
6. **Cutover freezes writers.** Start a second writer under the lease; it fails closed.
   *Break by dropping the lease — the second writer must succeed, which is the mixed-writer
   hazard.*
7. **The retired `status.json` fields stay absent.** After cutover, re-adding `queue` fails
   the retired-field invariant. *Break by leaving #362's old comparison in place — it must
   pass vacuously on the absent fields, which is the hollow-check failure.*
8. **A stale agent self-heals.** Simulate an old-protocol read of `tasks.md` after cutover;
   it finds the #458 notice and the deprecation block, not a missing file. *Break by
   leaving no shim — the read must find nothing and the agent has no path to the store.*
9. **Rollback never restores a legacy writer.** Roll back; then attempt a direct Markdown
   mutation; it is refused by the version gate. *Break by restoring the legacy writer — the
   mutation must succeed, reintroducing the hazard.*
10. **The chain verifies over synthetic + live events.** After import + one real
    `filed` event, chain verification passes; mutate a synthetic row and it fails. *Break
    by exempting `migration:git` rows from the chain — the verifier must pass over a
    mutated synthetic row, which is a silent forgery.*

---

## What is open, and what approval does not authorise

**Open, and his to rule:**

- **T3 in practice — does the store ship machine-local (his Q2 `(c)`) or committed?** His
  #264 Q2 answer `(c)` accepted machine-local for v1. This design assumes machine-local and
  imports git history so the store is self-sufficient regardless. If he later wants
  cross-clone history, committing the canonical byte export **is** that — a deployment
  choice, not a schema change (T3). Confirm machine-local for v1.
- **Lease duration for the cutover window.** Bounded by the import's wall-clock (a few
  seconds over 578 commits' first-sights, plus verify), but the freeze must cover any live
  lane's in-flight write. The lease primitive is #263's; the duration is a loop-policy
  call.
- **Whether `dropped` and `superseded` are one state or two** — inherited from #264,
  unchanged; it does not affect the migration.

**Approval of this design authorises nothing being built.** It accepts the migration
**shape**: a staged readable script, `AUTOINCREMENT` seeded and verified, first-sight
git-history synthetic events, an exclusive cutover lease consuming #263 lane H, the
rename + shim + #458 notice, the retirement of #362's drift check, and journal-aware
rollback. It does **not** authorise creating a table, writing the CLI, running the
migration, renaming `tasks.md`, deleting `status.json` fields, or payload purge — those
wait on #263 lane H landing and #352 unifying the parser, exactly as #264's gate states.

---

## Increment 1 — schema + seeded sequence (built 2026-07-29, lane `wt/schema`)

His 05:48 ruling (`rec` on all five) unblocked **building the store module**, not
cutover. What landed:

| Piece | Where | Notes |
|---|---|---|
| Entity + event schema | `ledger_store.py` `_SCHEMA_SQL` | `entry`, `task` (`AUTOINCREMENT`), `related`, `depends`, `review_decision`, `task_event`, `task_state`, lookup tables — #346 + #264 shapes |
| Open / create | `open_store(path, …)` | WAL, `synchronous=FULL` (NORMAL-then-FULL pin, user_events B1 lesson), `foreign_keys=ON`, busy_timeout |
| Seed derivation | `derive_next_id(text)` | `lint.load_watch()` → `parse_ledger` → `MAX(id)+1`; header `Next id` must agree (lint's `NEXT_ID`) |
| Seed write + verify | `LedgerStore.seed_sequence` | writes `sqlite_sequence.seq = next_id - 1`, re-reads, refuses to *lower* an established mark |
| Fail loud | `SeedError` | unseeded open, empty parse, header drift, non-positive next_id, lower-guard |

**What building taught that the design understated:**

1. **`sqlite_sequence` is not created until an AUTOINCREMENT table exists**, but a
   direct `INSERT INTO sqlite_sequence` works once the table is present in the schema —
   no dummy row is required to force the high-water mark. Seed is therefore one
   INSERT/UPDATE, not a throwaway row that would then need deleting.
2. **Unseeded open must refuse, not default to 1.** A fresh DB whose first allocate
   hands out `1` after cutover collides with every imported permanent id. The design
   said "seeded and verified"; the concrete rule is *refuse to open until seeded*.
3. **`task_event.receipt_id` is free TEXT in increment 1**, not a FK to `receipts`.
   The receipt table lives in the same *file* only after co-residence with #263's
   journal; wiring the FK now would require either inventing a second receipts table
   or opening the journal file, both out of this increment's scope. The column is
   there so the import can write it; the FK lands when the files merge.
4. **Live measurement 2026-07-29:** `parse_ledger` → 146 open / 219 landed / union
   365; `MAX(id)+1 = 472`; header `Next id: **472**` — agreement holds. F2's "470"
   was a point-in-time number, not a constant.

**Red-proved (each injection restored, suite green after):**

- Drop `AUTOINCREMENT` from `task.id` → `test_autoincrement_does_not_reuse_…` fails
  (high-water no longer tracks the deleted peak).
- Unseeded open invents `seed_sequence(1)` → `test_open_without_seed_fails_loud` fails.
- Ignore header drift → `test_derive_next_id_fails_when_header_drifts_…` fails.

**Still firmly out of this increment:** import, cutover, migration script, shim,
`tasks.md` rename, write verbs, co-residence with the journal file, chain hashing
implementation beyond the `prev_hash`/`hash` columns.

**`file-formats.md` paragraph wanted (not this lane's file):** describe the
machine-local ledger SQLite store path (once co-resident name is fixed —
candidate is the same file as `.dreamwork/user-events.sqlite3`, or a sibling
`.dreamwork/ledger.sqlite3` until merge), that `task.id` is `AUTOINCREMENT` with
the sequence seeded from `MAX(parse_ledger ids)+1` verified against the Markdown
`Next id` header, and that an unseeded or drifted seed is a hard open failure
(`SeedError`), never a silent start-at-1.

--- SUMMARY ---

- **The dependencies are met as designs.** #263's contract is approved and partially
  landed; #264's boundary is approved in full; #346's schema is ruled. The one unmet
  dependency is #263's lane H (the version gate) — implementation, not design — and
  cutover is sequenced after it.
- **The migration owns what #264 deliberately left open:** cutover ordering, git-history
  import, rollback, `tasks.md.deprecated`, mixed-writer freeze. The entity schema is
  #346's, the boundary is #264's, the receipt journal is #263's.
- **A single staged, human-readable `dreamwork tasks migrate`** dry-runs through the
  production parser, reports exact counts/IDs/digests/conflicts, backs up, imports
  atomically into the one SQLite file inside one `BEGIN IMMEDIATE`, verifies by replay,
  and cuts over behind an exclusive lease. #352 (unify the parser) is a hard prerequisite
  to the cutover step, not to the design.
- **The id sequence lives in the store** (`AUTOINCREMENT`, seeded from the Markdown
  `Next id` and verified `== MAX(id)+1`), so two writers can never mint the same id and
  the seed cannot drift — the IGC survivor over a header-authority and a sidecar-row
  rival.
- **Git history imports as first-sight synthetic events** (`actor='migration:git'`),
  chained, honest about the precision the Markdown actually held — the burndown survives in
  the store without fabricating the ~16 intra-life causes nobody wrote down.
- **Cutover is #263's own sequence**, reused: exclusive lease, freeze every writer, flip
  the readers after #352, rename + notice, watermark. Mixed-version fail-closed is #263
  lane H, consumed not reinvented. The dual-write "shadow run" is refuted — it *is* the
  second derived truth #264 exists to remove.
- **`tasks.md` content moves to `tasks.md.deprecated` (YAML deprecation block); a
  one-line `tasks.md` shim carries a #458 notice** so a stale agent reading the path every
  tick self-heals instead of losing work. Never auto-deleted.
- **#362's drift check is retired at cutover** and replaced by the inverse invariant — the
  three retired `status.json` fields must stay absent. The disagreement disappears by
  construction: one source, burndown a query.
- **Rollback restores the backup then re-runs the migration forward**, never restoring a
  legacy direct writer (#263's rule), because re-opening Markdown mutation would reintroduce
  the single-writer-by-convention hazard and diverge the chain on the next hand-edit.
- **Ten red-first fixtures**, each naming the production line that must change for it to
  fail, two of them naming the hollow-check way it could pass.
