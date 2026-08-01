# Work hierarchy — nested collections, cross-level dependencies, batches (#841)

His do-next, 2026-08-01 16:56:47, receipt `76c1b7af`, verbatim:

> "If we don't already support this, please have an opus 5 subagent (use
> /subagent-protocols) plan and build this feature: the db should support
> hierarchical collections of tasks, like: milestone/feature > epic > task.
> Tasks can and should be batched intelligently. We should support dependency
> links between tasks and epics and milestones. You shouldn't be limited to
> this particular hierarchy, btw, you should consider what is going to work
> best for us and then use that organization system."

This plan extends `#824`'s v004 grouping store. It does not build a second
one (`#440`: one supported way).

---

## 1. What the store actually held before this change — MEASURED

Every row below was read from the **live** `.dreamwork/ledger.sqlite3` over a
read-only URI handle (`mode=ro`, `PRAGMA query_only=ON`) on 2026-08-01.

| Fact | Value | How known |
|---|---|---|
| Live `schema_version` | **4** | VERIFIED — `SELECT value FROM meta WHERE key='schema_version'` → `('4',)` |
| Tasks | **730** (543 landed, 187 open), max id **841** | VERIFIED — `SELECT COUNT(*) FROM task` |
| `task_group` population | **0** | VERIFIED — `SELECT COUNT(*) FROM task_group` |
| `task_group_member` / `task_group_trigger` | **0** / **0** | VERIFIED |
| `depends(task, needs)` | **23 rows, acyclic** | VERIFIED — full row dump + DFS cycle scan, no cycle |
| `related(a, b)` | **151 rows** | VERIFIED |
| `task.blocked_on` non-empty | **27** | VERIFIED |

**Two premises in the dispatch brief were stale and are corrected here.**

1. The brief said *"the live ledger is still schema 3; it migrates on store
   open via `initialize_legacy_store`."* It is **already schema 4** —
   VERIFIED above. v004 has landed on the live store. So v005 upgrades a
   **4 → 5** store in the field, not a 3 → 4 → 5 store, and the v004 step is
   no longer the one being exercised on live data.
2. The brief said **728** existing tasks. The count is **730** (VERIFIED).

**And one whole table the brief did not mention.** `depends(task INTEGER
REFERENCES task(id), needs INTEGER REFERENCES task(id), PRIMARY KEY (task,
needs), CHECK (task <> needs))` has existed since **v001**
(`dreamwork_db/migrations/v001_legacy.py:92`, index `depends_by_needs` at
`:98`) and carries **23 live rows**. The brief described `task.blocked_on`
as "a task-level dependency primitive"; that is only half true —
`v001_legacy.py:68` says in so many words that *"`blocked_on` stays verbatim
prose, never an edge (#346 S1: edges live in `depends`)"*. **Task→task
dependency edges already have a home, with data in it.** This single fact
reshaped the dependency half of this design (§4): the naive "one new
polymorphic dependency table" would have been a second way to say something
the store already says — exactly what `#440` forbids.

### What genuinely did not exist

- **`task_group` has no `parent_id`** (VERIFIED, `v004_groups.py:21-28`), so
  groups cannot nest. `milestone > epic > task` is not expressible.
- **No dependency edge with a group endpoint.** `depends` is `task→task`
  only (both columns `REFERENCES task(id)`).
- **No batching concept.**
- `kind` is pinned by an inline `CHECK (kind IN ('lane','epic','milestone'))`
  (VERIFIED, `v004_groups.py:23`).

---

## 2. The interesting decision — the `CHECK`, and the shape

He flagged the tension himself: *"you shouldn't be limited to this
particular hierarchy."* Note the concrete evidence in his own sentence —
he wrote **"milestone/feature"**, and **`feature` is a kind v004's `CHECK`
rejects** (VERIFIED against the constraint text above). The vocabulary was
already too tight for the message that asked for it.

### 2a. IGC — how do collections nest?

**Context.** A single-repo autonomous dev loop. Group population today is 0,
so migration cost is near-free *now* and will not be later. Reads are
interactive (a dashboard and a CLI), volumes are hundreds of rows, so query
cost is nowhere near a breakpoint. Writes are rare and human/loop-initiated.

| Idea | All | G1 | G2 | G3 | G4 | G5 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| **A. Adjacency list** — `task_group.parent_id` self-reference | **✔** | ✔ | ✔ | ✔ | ✔ | ✔ |
| B. Closure table — `(ancestor, descendant, depth)` rows | ✘ | ✔ | ✔ | ✔ | **✘** | ✔ |
| C. Fixed deeper enum + `level` column | ✘ | ✔ | **✘** | ✔ | ✔ | ✔ |
| D. Materialised path — `'/1/7/12/'` | ✘ | ✔ | ✔ | ✔ | **✘** | ✔ |
| E. Nested sets — `lft`/`rgt` | ✘ | ✔ | ✔ | ✔ | **✘** | **✘** |

- **G1** `milestone > epic > task` is expressible today.
- **G2** A new organisational level can be added **without a schema
  migration** — his explicit instruction, so a binary pass/fail.
- **G3** A cycle cannot be persisted; the store refuses it, so no traversal
  can hang or silently truncate.
- **G4** Parentage has **exactly one** authoritative home — no second copy of
  the same fact that can drift (`#440`).
- **G5** Migration is data-preserving and reversible.

**The ✘s, stated.**

- **B** fails **G4**: the closure rows duplicate ancestry that the edge
  already states. Either the edge is dropped (and then re-parenting means
  rewriting O(subtree × depth) rows with no single source to re-derive from)
  or both exist and can disagree. A recursive CTE over the adjacency list
  gets the same answer at these volumes with one truth.
- **C** fails **G2** decisively: adding "initiative" above milestone, or
  "sub-epic", means editing a `CHECK` and shipping a migration. This is the
  option he pre-emptively refused.
- **D** fails **G4** for the same reason as B and worse: the path stores each
  ancestry fact once *per descendant*, so a re-parent that partially fails
  leaves rows whose paths contradict each other, with nothing to reconcile
  against.
- **E** fails **G4** (same duplication) **and G5**: every insert renumbers up
  to half the table, so a migration or a routine write touches rows it has no
  business touching.

**One survivor: A, the adjacency list.** Depth becomes data, not schema —
which is the precise sense in which the design stops being "limited to this
particular hierarchy". Reads use `WITH RECURSIVE`; there is deliberately **no
`LIMIT` in the recursive CTEs**, because a limit is silent truncation wearing
a passing result (`#671`). Cycles are refused at write time instead (§3).

### 2b. IGC — the `kind` vocabulary

| Idea | All | G6 | G7 | G8 |
|---|:--:|:--:|:--:|:--:|
| Keep the inline `CHECK` | ✘ | **✘** | ✔ | ✔ |
| Free-text `kind` | ✘ | ✔ | **✘** | ✔ |
| **Seeded lookup table + FK** | **✔** | ✔ | ✔ | ✔ |

- **G6** a new kind (`feature`, `batch`, `initiative`) can be added without a
  code change.
- **G7** a typo (`epics`, `Epic`) is refused, so the vocabulary cannot
  silently fork.
- **G8** matches how this schema already expresses a controlled vocabulary.

**G8 is the decisive one and it is measurable.** Every other controlled
vocabulary in this store is a seeded lookup table with an FK, not an inline
`CHECK`: `priority_band`, `task_state_kind`, `task_cause`, `task_type`
(VERIFIED, `v001_legacy.py:45-60`; live `task_type` holds 14 seeds including
`feature`). v004's inline `CHECK` is the **only** exception in the schema.
Converting it to `task_group_kind(kind TEXT PRIMARY KEY)` with
`kind TEXT NOT NULL REFERENCES task_group_kind(kind)` is therefore not a new
mechanism — it is `#440` applied in the direction that *removes* the second
way.

`kind` carries **no behaviour**: v004's `groups.py` never branches on it
except to validate it (`GROUP_KINDS` at `groups.py:24`, checked at `:79`) and
to interpolate it into error text. A pure label with no behavioural coupling
is exactly the thing that should not be pinned in DDL.

**Seeded kinds:** `lane`, `epic`, `milestone` (v004's three, preserved),
plus `feature` (he named it) and `batch` (§5).

### 2c. Deliberately rejected: kind ordering

The store does **not** enforce that a milestone may only contain epics, or
that a lane may not contain a milestone. Encoding an ordering needs a `rank`
per kind, and every newly-defined kind would then have to be slotted into
that order — re-introducing precisely the schema-level rigidity G2 exists to
remove. The tree is the structure; the kind is the label. A nonsensical
arrangement is a *planning* error, visible in `groups tree`, not a
constraint violation.

---

## 3. Nesting — the mechanism

`ALTER TABLE task_group ADD COLUMN parent_id INTEGER REFERENCES
task_group(id)`; `NULL` means root. Existing rows become roots, which is
their current meaning exactly.

**Cycle refusal is a write-time repository check, not a constraint** —
SQLite cannot express "no cycle" declaratively. `set_parent` and
`create(parent_id=…)` both:

1. refuse `parent_id == group_id`;
2. walk the candidate parent's ancestor chain and refuse if `group_id`
   appears in it.

The refusal message names **the path**, not merely "a cycle exists" — e.g.
`cannot set parent of epic #3 'Beta' to epic #4 'Gamma': that would create a
cycle 3 -> 4 -> 3`. This is the discriminating-message bar: a reader learns
*which* group's parent was wrong.

The ancestor walk is itself cycle-safe (it stops on a repeat), so even a
hypothetically corrupted store cannot hang the checker that is supposed to
prevent the corruption.

### Rollups become subtree rollups

`progress(group_id)` changes from direct membership to **transitive subtree**
membership. This is a strict generalisation — for a childless group the two
are identical, which is why every v004 progress test still passes unchanged.
Direct-only progress on a parent node would be a lie about the thing it
names: a milestone with three child epics and no direct members currently
raises `EmptyGroup`, and after this change it reports its subtree.

**A task may belong to a group *and* its ancestor** (`task_group_member`'s
PK is `(group_id, task_id)`, so nothing prevents it). The subtree rollup
therefore **`SELECT DISTINCT`**s task ids, and returns the **id set**; counts
are derived from that set, never counted separately. A naive implementation
double-counts, and a test that only compares lengths would not see it
(`#702`; `#820` demonstrated exactly this twice, once as a self-comparison).

### 3a. "Empty" stops being one condition — the rule

`#836` (master `83414ede`) gave v004's API its first production consumer:
`watch.group_progress()` (in `watch.py`), called from `collect()` on every
dashboard poll, reading `.id/.kind/.title/.description` off `list()`,
`.completed/.completed_count/.total_count/.member_task_ids/.landed_task_ids`
off `progress()`, and catching `EmptyGroup` **by name** to render "progress
unavailable" with no bar (its `except EmptyGroup` arm). That refusal is
load-bearing
and is the same vacuous-truth trap as `all([]) is True`: without a
denominator the view has not judged progress and must not draw a reassuring
0% or 100%.

**Nothing in this plan renames or reshapes those three surfaces.** `list()`,
`progress()`, and `EmptyGroup` keep their names, signatures, and every
attribute `watch.py` reads; `StoredGroup` gains `parent_id` and
`GroupProgress` gains `empty_group_ids`, both purely additive. So
`watch.py` and `dev/capture/groupprogress.mjs` need **no edit** — which is
also what the lane boundary requires, since another lane holds
`dev/capture/`. A rename here would have turned the whole groups panel into
an empty list through `group_progress`'s `except DatabaseError: return []`,
failing silently and looking like "no groups exist".

With nesting, "empty" splits into three cases. The rule, stated:

| Case | `progress()` | `completed` |
|---|---|---|
| **1. Transitively empty** — no task anywhere in the subtree (incl. a milestone whose two epics both hold zero tasks) | raises **`EmptyGroup`** | n/a — not judged |
| **2. Partly populated** — ≥1 subtree task, but some descendant group's own subtree is empty | returns a rollup over the union of subtree tasks; `empty_group_ids` names the empty descendants | **`False`**, even when every known task landed |
| **3. Fully populated** — ≥1 subtree task and no empty descendant | returns the rollup; `empty_group_ids` is `()` | `landed_task_ids == member_task_ids` (v004's rule, unchanged) |

Case 1 preserves `#836`'s property exactly: no denominator, no bar.

Case 2 is the genuinely new question, and the conservative answer is the
honest one. A denominator *does* exist, so a bar can be drawn — refusing to
show one would hide real progress. But **completion is withheld**, because an
empty child collection is `all([])` one level up: a named sub-collection that
has never had any work put into it is not evidence that there is no work
left. `empty_group_ids` says which ones, so the refusal is discriminating
rather than a bare `False`.

Case 3 is v004's rule verbatim, which is why every v004 progress test passes
unchanged: for a childless group, case 3 *is* the flat case.

The same rule governs dependencies (§4): a required group with no tasks is
**unmet**, never vacuously satisfied.

### 3b. A read surface must not migrate

`group_progress()` opens with `Access.READ`, and `core.py:338` runs the
initialiser **only** for `Access.WRITE`, so a poll can never migrate. Against
a store still on v4, `progress()`'s query names `task_group.parent_id`,
SQLite answers `no such column`, `_raise_classified` (`core.py:295-298`) maps
that to `SchemaMismatch`, and `group_progress`'s `except DatabaseError`
returns `[]`. The dashboard degrades to "no groups" until some writer
migrates through the canonical path — which is the documented behaviour for a
pre-v004 store already, now extended one version.

---

## 4. Dependencies — one concept, two typed homes, no overlap

He asked for "dependency links between tasks and epics and milestones", i.e.
all four combinations of `{task, group} → {task, group}`.

| Idea | All | G9 | G10 | G11 |
|---|:--:|:--:|:--:|:--:|
| New polymorphic `(kind, id) → (kind, id)` table | ✘ | **✘** | ✔ | **✘** |
| Rebuild `depends` to carry group endpoints | ✘ | ✔ | ✔ | **✘** |
| Three separate typed tables | ✘ | ✔ | **✘** | ✔ |
| **`task_group_dependency` with an exclusive arc, `depends` kept** | **✔** | ✔ | ✔ | ✔ |

- **G9** every endpoint is FK-enforced, so a dangling edge is impossible.
- **G10** there is exactly one place to write any given edge (`#440`).
- **G11** the 23 live `depends` rows are not migrated, rewritten, or put at
  risk.

The polymorphic table fails **G9**: SQLite cannot conditionally FK a column
pair, so `(group, 999)` would persist after group 999 is deleted, in a store
that is FK-strict everywhere else. It also fails **G11**, since honouring
G10 would mean moving the 23 rows into it. Rebuilding `depends` fails
**G11** for the same reason. Three tables fail **G10**.

### The shape

```sql
CREATE TABLE task_group_dependency (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    dependent_group_id INTEGER REFERENCES task_group(id) ON DELETE CASCADE,
    dependent_task_id  INTEGER REFERENCES task(id),
    needs_group_id     INTEGER REFERENCES task_group(id) ON DELETE CASCADE,
    needs_task_id      INTEGER REFERENCES task(id),
    created_by TEXT NOT NULL CHECK (length(trim(created_by)) > 0),
    created_at TEXT NOT NULL CHECK (length(trim(created_at)) > 0),
    -- exactly one endpoint on each side
    CHECK ((dependent_group_id IS NOT NULL) + (dependent_task_id IS NOT NULL) = 1),
    CHECK ((needs_group_id IS NOT NULL) + (needs_task_id IS NOT NULL) = 1),
    -- task -> task belongs in v001's `depends`; the schema refuses the second way
    CHECK (dependent_group_id IS NOT NULL OR needs_group_id IS NOT NULL),
    -- no self-edge
    CHECK (dependent_group_id IS NULL OR needs_group_id IS NULL
           OR dependent_group_id <> needs_group_id)
);
```

Each endpoint column is individually FK'd and `NULL` in the columns that do
not apply — NULL never constrains, so **G9 holds for every row shape**.

**The third `CHECK` is `#440` written into the schema.** A `task→task` edge
*cannot* be stored here; the database itself rejects it. The repository
refuses it earlier with a message that names `depends` as the home. There is
no second way to say `task needs task`, by construction — and unlike most
"by construction" claims, this one is a constraint you can execute.

Uniqueness needs an **expression index**, because SQLite treats `NULL`s as
distinct in a `UNIQUE` constraint and two identical edges would both insert:

```sql
CREATE UNIQUE INDEX task_group_dependency_edge ON task_group_dependency (
    ifnull(dependent_group_id,-1), ifnull(dependent_task_id,-1),
    ifnull(needs_group_id,-1),     ifnull(needs_task_id,-1));
```

### Readiness — what a dependency actually *does*

A dependency that nothing reads is decorative, and a decorative check reads
as a passing one (`#671`). So the store answers it.

- **task complete** ⟺ `state = 'landed'`.
- **group complete** ⟺ its subtree holds **≥ 1** task **and** every subtree
  task is landed. An empty group is never complete.
- **blockers(node)** = every edge into `node` whose required side is
  incomplete, **plus** — for a task — every unmet edge into any group the
  task belongs to *or any ancestor of those groups*. Inherited blocking is
  what makes a group-level dependency mean anything: if epic E requires
  milestone M, no task inside E may start before M completes.
- **task→task blockers are read from v001's `depends`**, so the 23 live rows
  participate in readiness without being moved. One concept, read from both
  homes; two homes, no overlap.

Cycles are refused on dependency edges too, by the same ancestor-walk shape
over the dependency graph, with the same path-naming message. A dependency
cycle is worse than a parent cycle: nothing in it is ever ready, silently.

---

## 5. "Batched intelligently" — stated interpretation

This is the vaguest phrase in his message, so the interpretation is recorded
as an **ASSUMPTION**, not smuggled in as a fact.

> **ASSUMPTION (INFERRED).** A *batch* is a small set of tasks intended to be
> executed together as one unit of work. "Batched intelligently" means the
> store must (a) let a batch be **named and persisted** as a first-class
> collection, and (b) supply the facts a selector needs to **form** a good
> batch. It does **not** mean the database clusters tasks by itself.

**(a) A batch is a group kind, not a new table.** This is where the two
halves of the design meet, and it is the strongest argument that the model is
right rather than merely adequate: the reason not to be locked to
`milestone > epic > task` is precisely that you want to slot a delivery-sized
level in between. With arbitrary depth and an open vocabulary,
`milestone > epic > batch > task` needs **no new schema at all** — `batch` is
one seed row in `task_group_kind`. Had the fixed enum survived §2b, batching
would have required its own table and its own migration.

**(b) `ready_tasks(group_id)`** returns the subtree's tasks that are `open`
**and** have no unmet blocker under §4 — the exact candidate pool a batcher
draws from, as an **id set**. Choosing *which* candidates and *how many* is
selection policy and stays in the loop, where the goals, priorities, and the
increment cap live.

**What is deliberately not built:** any auto-clustering heuristic. A
similarity batcher that returns everything, or returns a plausible-looking
set for the wrong reason, is `#671` in its purest form — machinery that reads
as intelligence while examining nothing. The store's honest contribution is
the candidate pool; an actual batching policy is a separate task with its own
evidence bar.

---

## 6. Migration v005 — reversibility and effect on the 730 tasks

**Effect on the 730 existing tasks (543 landed, 187 open): none.** v005 does
not read, rewrite, or reference the `task` table. Task rows are untouched
byte-for-byte, as are `depends` (23), `related` (151), and `task.blocked_on`
(27). VERIFIED by the migration test that snapshots every task row before and
after and compares the full rows, not a count.

**Why a table rebuild is needed at all.** SQLite cannot drop a `CHECK`
constraint with `ALTER TABLE`, so replacing v004's inline `kind` check with
the FK requires rebuilding `task_group`. `PRAGMA foreign_keys` is ON before
the initialiser runs (`core.py:335-339`) and is a **no-op inside a
transaction**, and the ladder runs inside `BEGIN` (`migrate.py:98`), so the
textbook `foreign_keys=OFF` twelve-step is unavailable. Dropping
`task_group` with children present would fire `task_group_member`'s
`ON DELETE CASCADE` and **destroy membership**. The migration therefore
sequences around it:

1. create + seed `task_group_kind`;
2. `CREATE TABLE … AS SELECT` backups of `task_group_member` and
   `task_group_trigger` (plain tables, no FKs);
3. drop both child tables — dropping a *child* is always safe;
4. rebuild `task_group` (kind FK + `parent_id`), copy rows preserving ids,
   drop the old table (now unreferenced), rename;
5. **restore `sqlite_sequence` for `task_group` to its pre-migration value** —
   a rebuild otherwise resets it to `max(id)`, and a deleted high-water id
   would then be reissued. v001 calls `AUTOINCREMENT` load-bearing for `task`
   for exactly this reason (`v001_legacy.py:64-66`); the same reasoning
   applies to group ids, which `task_group_member` references;
6. recreate the child tables and the member index, copy the backups back,
   drop the backups;
7. create `task_group_dependency` + its expression index;
8. `PRAGMA foreign_key_check` — the migration refuses to finish on any
   violation.

All of it is inside the ladder's single transaction, so a failure at any step
rolls back to v004 intact.

**`downgrade` follows v004's model exactly** (`v004_groups.py:65-83`): it
counts each *new* table's population **first** and raises `SchemaMismatch`
naming every non-empty one, rather than dropping data. For v005 the
populations that block a downgrade are `task_group_dependency` (rows would be
lost outright) and any `task_group` row with a non-NULL `parent_id` (the
nesting would be lost), plus any `task_group_kind` row outside v004's three
(a group of a kind v004 cannot express). When it does proceed it rebuilds
`task_group` back to the inline `CHECK` through the same child-backup
sequence, preserving membership and triggers, and sets `schema_version` to
`'4'`.

---

## 7. Not this plan

- **Goal hierarchies (`#95`, `plans/goal-hierarchies.md`)** are a different
  axis and stay separate. That tree is *why* work is done (user goal →
  session goal → task goal, living in `DREAMWORK.md` + `status.json`); this
  tree is *what* work is grouped into (durable store records). They will
  cross-reference eventually; merging them now would put a session-scoped,
  human-edited concept into a permanent-id store.
- **The animated progress bar** (`#824`'s third deliverable) is still not
  here and still needs its own lane.
- **Trigger firing.** `task_group_trigger` remains inert; `ready_triggers`
  stays a read. Nothing in v005 enqueues or files a task.
- **An actual batching policy** — §5(b).
- **A repository API for `depends`.** v001's task→task edges are read for
  readiness but still have no write verb; adding one is a separate increment.
