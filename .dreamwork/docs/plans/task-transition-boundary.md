# The task-transition boundary — one history, no second truth

**Tasks:** #264 (the `human via watch 14:11` amendment only) · consumers #294, #334, #281
**Status:** design; **no implementation authority**. No table is created, no CLI
ships, nothing is migrated under this id.
**Date:** 2026-07-28
**Depends on:** `user-event-journal.md` (#263, approved `"rec"` 01:27 — contract
only) and `task-store-schema.md` (#346, S1/S2/S4 ruled 01:23). Both shapes are
settled; this document adds the verb half neither of them covers.

---

## The recommendation

His question was *"decide whether it shares #263's journal or uses a task-state
outbox, but never dual-write two fallible truths."*

**Neither, as literally stated — and the reason is one sentence: those two
options both assume a task transition and a user event are the same kind of
fact, and they are not.** The answer is the third shape both were reaching for:

> **A task transition is one row appended to its own append-only
> `task_event` log, in the same SQLite database as #263's journal, in the same
> transaction as the compare-and-swap that moves `task_state`. There is no
> outbox and no drain. Burndown and the dashboard status section are
> **queries** over `task_event` — not tables, not caches, not files — so
> neither can be stale. `task_state` exists only because a claim needs a row
> to CAS against, and it is rebuildable and verified by replay.**

Concretely, the whole boundary:

| what | authority | derived from | how it is rebuilt |
|---|---|---|---|
| `task_event` | **AUTHORITATIVE** — append-only, never updated, never purged | — | it is the truth |
| `task`, `entry`, `depends`, `related` (#346) | **AUTHORITATIVE** | — | — |
| `task_state` (one row per task) | derived | `task_event` | `tasks rebuild --verify` replays and diffs |
| burndown series + headline counts | derived | `task_event` | it is a query; there is nothing to rebuild |
| dashboard status section, queue depth, `/tasks` per-row badge | derived | `task_event` + `task_state` | same |
| `blocked` | derived | `depends` + gate rows | never written, so it cannot drift |
| `tasks.md` | **shadow**, best-effort, deterministic export | `entry` + `task_state` | regenerate and diff |
| `status.json`'s `queue`, `current_task_ids`, per-agent `task_ids` | **DELETED** | — | — |
| `watch-events.log` | wake signal, best-effort | — | — |

**Inside one transaction, per transition, exactly this and nothing else:**

```sql
BEGIN IMMEDIATE;                      -- not deferred; see the footgun table
  INSERT INTO task_event(...);        -- ordinal, prev_hash, hash, cause, actor
  UPDATE task_state SET ..., revision = revision + 1, at_ordinal = <new ordinal>
    WHERE task_id = ? AND revision = ?  AND <verb's own predicate>;
  -- for a 'filed' event only: INSERT INTO entry(...), INSERT INTO task(id,...)
COMMIT;
```

**Outside it, always, and never load-bearing:** the `tasks.md` export, the
`watch-events.log` wake line, any dashboard cache, and any file an agent
writes by hand.

Everything else in this document is why, and what has to be true for it to
hold.

---

## The findings that force it

Each names how to show it false, because a design finding with no
falsification route is an opinion.

### F1 — "never dual-write two fallible truths" is already violated, and the two truths already disagree by 9

Two numbers describing queue depth are rendered on the same dashboard page.
Measured 2026-07-28 01:52 against the live target:

```
python3 -c "import sys; sys.path.insert(0,'.'); import watch, json
t='/home/xertrov/.llm-general/skills/ud-dreamwork'
o,l=watch.parse_ledger(open(t+'/.dreamwork/tasks.md').read()); print(len(o),len(l))
s=json.load(open(t+'/.dreamwork/status.json')); print(s['queue'], sum(s['queue'].values()))"
```

- ledger: **122** open ids, 129 landed (and `lint.py` independently agrees:
  `section split agrees with watch.py at 122 open ids`).
- `status.json`: `{"in_progress": 4, "pending": 109}` — sum **113**.
- the burndown's own open reading, from the last committed revision: **122**
  (`watch.ledger_series('.')['open']`).

So the page shows 122 in one panel and 113 in another. And it is worse one
level down — *inside* `status.json`, two fields describing which tasks the loop
holds disagree with each other:

```
current_task_ids: []          union(agents[].task_ids): [252, 264, 284]
```

`file-formats.md:632` says `/tasks` badges a row "in progress" **from
`current_task_ids`**, so today that badge would badge nothing while three tasks
are in flight. `lessons.md:980` (#306) already stated the rule this confirms:
*"where two files hold two halves of one fact, assume they have already
drifted."* The measurement is that rule coming true on the exact fact #264 is
about.

**Falsify it:** re-run the command above and show the three numbers agree, or
show that `status.json`'s `queue` is documented somewhere as meaning something
other than the ledger's open count.

### F2 — a task's lifecycle and a receipt's lifecycle are different lifecycles, and #263's `Transition` cannot hold both

The coordinator handed this over as the crux. **It holds.** Evidence, from
`user-event-journal.md`:

- `:101` — `Transition { transition_id, receipt_id, at, from_state, to_state,
  revision, consumer_id?, claim_token?, ... }`. In that document's own notation
  a trailing `?` marks an optional field; **`receipt_id` has none**, while nine
  siblings do. `grep -c receipt_id` → 5, every one receipt-scoped.
- the state machine is the *processing of a submission*:
  `received → validated → claimed → applying → applied`, with `rejected`,
  `retryable`, `recovering`, `needs_human`, `purged`. Not one of those is a
  thing a task is.
- `§Replay cursor` says replay *"enumerate[s] every receipt event after the
  cursor plus all current nonterminal/recovering receipts"*. A journal
  carrying task events with a NULL `receipt_id` makes that enumeration wrong by
  default: every consumer must remember to filter, and the day one forgets, a
  task event is applied as a receipt.

One nuance worth stating rather than glossing: the chain does carry an event
class that is not a transition — *"health event"*, e.g. `shadow_failed`. But
health is per-receipt too, so the invariant *every journal event names a
receipt* survives intact. That is the invariant Option A would break.

**Falsify it:** find a line in `user-event-journal.md` that admits an event
with no receipt, or show that `?`-suffixing is not that document's
optional-field notation (check `Receipt { … purged_at? }` at `:97`).

### F3 — most task transitions have no receipt, and even the ones that do are not in the receipt's transaction

Two separate claims, both measured.

**(a) The channel barely touches task state at all.** `watch.py` has six POST
write routes — `/answer`, `/ask`, `/comment`, `/command`, `/tint`, `/run-mode`
(`grep -n 'self.path == ' watch.py` around `do_POST`, lines 8398-8411). Only
`/command` carries `do now:` / `do next:` / `add idea:`. And
`_handle_command` (`watch.py:8505`) validates the kind and then does exactly
one thing: `log_event(target, command_line(kind, text, req.get("from")))`.
**Zero task state is mutated at HTTP time today.** A `do now:` becomes a task
because an LLM reads `watch-events.log` on a later tick and decides to make
one.

**(b) So even a receipt-caused transition cannot share the receipt's
transaction.** The applying party is an LLM, on a later tick, and the mapping
is one-to-many and judgement-laden: one `do now:` routinely files a task,
marks another blocked, and re-prioritises a third. There is no transaction that
could contain both the `202` and that.

**Which is the load-bearing reframing of his constraint:** *never dual-write
two fallible truths* forbids storing **one fact** in two places. It does not
forbid storing **two facts**. "He asked for this at 14:11" and "the loop
started #264 at 01:47" are different facts, neither derived from the other, and
they are related by a foreign key — `task_event.receipt_id` — not by a shared
transaction. The receipt is the *cause*; the transition is the *effect*; the FK
is the whole of their relationship.

Scale, as an upper bound rather than an estimate: over the ledger's whole
history `ledger_series` reports 270 arrivals, 130 landings, and first-sight
provenance of `human 87 / loop 55 / unknown 126`. Human-origin arrivals are an
**upper** bound on receipt-borne arrivals (he also steers in chat, and "via
watch" appears in 58 of 122 open entries but marks the *steer*, not the
transition). Arrivals are one of the ~18 causes in §"Why a task changes with no
user event", every other one of which is loop-authored by construction. So
receipt-borne transitions are a small minority of a small minority.

**Falsify it:** show a write route that mutates task state synchronously, or a
single existing code path where a `do now:` creates a task inside the request.

### F4 — burndown is already a projection of an append-only log; the log is just git, and git lags

`ledger_series` (`watch.py:6948`) walks every commit touching
`.dreamwork/tasks.md`, `git show`s each revision, parses it, and takes
first-sightings: *"An id ARRIVES at the first commit that mentions it anywhere,
and is COMPLETE at the first commit that names it under `## Recently
landed`."* Its own comment states the consequence: *"an uncommitted entry in
the working tree is not a historical arrival."*

So the burndown does not read current state at all — it cannot be computed
from current state — and its source is already immutable and append-only. The
design question is not *whether* a history exists. It is **which append-only
log**, and today's answer costs a commit per reading:

```
git --no-optional-locks log --format=%ct -- .dreamwork/tasks.md | python3 -c "…"
```

→ **331** commits touching the ledger; median inter-commit gap **288 s (4.8
min)**, p90 **1198 s (20 min)**, max **795 min (13.3 h)**.

That distribution *is* the "no Git-HEAD lag" his #294 amendment forbids. Two
honest qualifications: the chart's bucket step is currently 14400 s (4 h), so a
5-minute lag is invisible in the chart's *shape* — but the headline
`open/arrived/landed` numbers are exact, and they are the ones that disagree
with `status.json` in F1. And `ledger_stats` caches on HEAD, so a tick with an
unmoved HEAD reuses the answer by design.

**The bonus nobody has to pay for again:** first-sight semantics exist because
`## Recently landed` gets pruned during grooming, so *current* contents lose a
completion every time the coordinator tidies. An append-only `task_event` log
removes that hazard entirely — a landing is one immutable row, not a mention
that must be caught before it is pruned.

**Falsify it:** show `ledger_series` reading the working-tree file, or show the
gap distribution is materially tighter over a recent window.

### F5 — an outbox would add the second fallible truth, not remove it

An outbox earns its place when the consumer **cannot participate in the
producer's transaction** — a different process, a different store, a network.
Here both consumers read the same SQLite file the writer just committed to. So
a drain step buys nothing and costs the one thing his constraint is about: a
projector that dies leaves the dashboard silently behind, and an undrained
outbox row *is* a second derived truth in exactly the sense #294 names (*"no
second derived truth"*).

The naming ambiguity is worth resolving rather than winning on: if "task-state
outbox" means **the task store keeps its own transactional transition log**,
that is the recommendation and we agree. If it means **a queue a projector
drains into separate view tables**, it is refuted. Only the second is the
outbox pattern; the first is the log.

**Falsify it:** name a burndown or status consumer that cannot open the store —
a browser is not one, because it reads `/data.json`, and `watch.py` can.

### F6 — one database file, because SQLite cannot express the foreign key across two

Measured against SQLite 3.53.3:

```python
cb.execute("ATTACH DATABASE 'a.db' AS j")
cb.execute("CREATE TABLE task_event(ordinal INTEGER PRIMARY KEY,
            receipt_id TEXT REFERENCES j.receipt(receipt_id))")
# -> sqlite3.OperationalError: near ".": syntax error
```

There is no syntax for a cross-database foreign key. Same-file, the constraint
is real (`INSERT` of an unknown `receipt_id` raised `FOREIGN KEY constraint
failed`). So the only place the `task_event.receipt_id → receipt.receipt_id`
check of F3 can exist is inside one database file. Two files reduce that check
to an unvalidated string — the precise "single truth across two stores" hazard.

**One thing NOT measured and not to be assumed:** a `BEGIN IMMEDIATE`
spanning two ATTACHed WAL databases committed here **without raising an
error**, which is the dangerous shape — it looks fine. Whether SQLite
guarantees atomicity for a multi-database commit in WAL mode must be checked
against SQLite's own documentation before anything relies on it. Do not take
the absence of an error as the answer.

**Falsify it:** show a working cross-database FK on any SQLite version this
project would ship on.

---

## Why a task changes with no user event

This is the list the answer has to accommodate. Every cause below is
loop-authored unless marked ⟵receipt, and each becomes a value in a `cause`
lookup table (#346's S4 ruling: lookup table for a vocabulary that grows,
`CHECK` for sets closed by definition).

| cause | when | where it is written down |
|---|---|---|
| `filed_from_command` ⟵receipt | `do now:` / `do next:` / `add idea:` in the composer | SKILL.md Commands |
| `next_up_set` ⟵receipt | `do next:` marks next-up | SKILL.md Commands |
| `next_up_cleared` | *"clearing the mark on start"* | SKILL.md selection step 0 |
| `filed_from_leftover` | out-of-scope leftovers, *"add it as in_progress first so the list stays truthful"* | selection step 1 |
| `filed_from_idea` | the idea beat | selection step 2 |
| `filed_from_brainstorm` | a brainstorm dreamer's dream, many at once | selection step 3.1 |
| `filed_from_split` | the ~20-min cap: *"Land a coherent point, commit, split the remainder into a new task"* | Philosophy + mid-task tick |
| `started_from_backlog` | *"pick the highest-priority unblocked pending task"* | selection step 3.2 |
| `landed` | reflect, verify, commit, *"mark the task completed"* | tick: task just finished |
| `claimed_by_agent` / `released` | dispatch: *"Record what a dispatched dreamer owns (files/dirs) at dispatch"* | Subagents |
| `lease_expired` | a dreamer died holding a claim | §Concurrency |
| `hold_set` / `hold_cleared` | a judgement call to park work | §Blocked is derived |
| `reprioritised` | grooming: *"dedupe, reprioritize, prune stale"* | maintenance rotation |
| `superseded` / `dropped` | grooming dedupe and pruning | maintenance rotation |
| `feasibility_noted` | *"do a quick feasibility check"* on a complex leftover | selection step 1 |
| `goal_realigned` | *"check every task `parent` still resolves to a DREAMWORK.md heading"* | maintenance rotation |
| `reconciled` | init: *"Mark done what's done, split what's half-done, drop what's moot — trust neither a ledger line nor a stale in-progress status"* | `initialization.md:181` |
| `ingested_upstream` | a plugin's forge issue when the loop actually starts on it | Task-list conventions, `writing-plugins.md` |

Eighteen causes; **two carry a receipt.** Supporting measurement over the 122
open entries (wrap-tolerant, via `watch.LEDGER_ENTRY` on the real section
split, because a naive scan of this file has produced a confident wrong number
three times):

```
blocked on 28   next-up 3   UNBLOCKED 4   "from #N" 9   supersede 3   via watch 58
```

The 4 hand-written `UNBLOCKED` annotations and 28 free-text "blocked on"
phrases are the specific drift the next section removes.

**Falsify the list:** name a state change the loop performs that is not
representable by one of these causes, or show that two of them are the same
event.

---

## The shape

### `task_event` — the authority

```sql
CREATE TABLE task_event (
  ordinal    INTEGER PRIMARY KEY AUTOINCREMENT, -- monotonic; the store's own sequence
  task_id    INTEGER NOT NULL REFERENCES task(id),
  at         TEXT    NOT NULL,   -- server clock, never a client's, never an LLM's
  cause      TEXT    NOT NULL REFERENCES task_cause(cause),
  from_state TEXT    NULL,       -- NULL only where the cause creates the task
  to_state   TEXT    NULL,       -- NULL where the cause changes something else
  actor      TEXT    NOT NULL,   -- 'coordinator' | 'dreamer:<name>' | 'cli:<user>'
  receipt_id TEXT    NULL REFERENCES receipt(receipt_id),  -- present iff receipt-borne
  detail     TEXT    NULL,       -- bounded; the reason in words, never a payload
  prev_hash  BLOB    NOT NULL,
  hash       BLOB    NOT NULL
);
CREATE INDEX task_event_by_task ON task_event(task_id, ordinal);
CREATE INDEX task_event_by_cause ON task_event(cause, ordinal);
```

Rows are never updated and never deleted — including by purge. **Purge is
#263's receipt-payload machinery and must not reach `task_event`**, because
burndown needs 2026's landings in 2027. `detail` is bounded and carries no
submitted bytes precisely so that no retention policy ever needs to.

`actor` is **attributed, not authenticated**. Anything holding the store can
write any actor string. That is fine — one trust domain — and it must be said
plainly rather than implied, because the ownership invariant (*"a compacted
coordinator that forgets a dreamer owns `foo.py` will edit `foo.py`"*) depends
on actors being honest, not on them being enforced.

### `task_state` — materialised, and only because a claim needs a row

```sql
CREATE TABLE task_state (
  task_id     INTEGER PRIMARY KEY REFERENCES task(id),
  state       TEXT    NOT NULL REFERENCES task_state_kind(state),
  hold        INTEGER NOT NULL DEFAULT 0,       -- explicit park; not derived
  hold_reason TEXT    NULL,
  owner       TEXT    NULL,                     -- 'dreamer:<name>' while claimed
  claim_token TEXT    NULL,                     -- unguessable, per #263's claim laws
  lease_until TEXT    NULL,                     -- server clock
  revision    INTEGER NOT NULL,                 -- CAS
  at_ordinal  INTEGER NOT NULL REFERENCES task_event(ordinal)
);
```

`state ∈ {pending, in_progress, landed, dropped}`. **`blocked` is not in it**
— see below.

`at_ordinal` is the load-bearing column and the answer to *"how does a reader
detect that the view is stale or behind?"*. It makes currency a comparison
rather than a belief: this row was produced by that event. It is what a rebuild
diffs against, what a cached snapshot compares itself to, and what catches a
hand-edited row — a `task_state` whose `at_ordinal` names an event that does
not imply that state is detectable, whereas a bare `state` column is not.

**The governing rule, which is what keeps this design small:** *a materialised
row exists only where a **writer** must compare-and-swap against it.
Everything a **reader** wants is a query.* One table qualifies. Nothing else
does.

This is also #263's own idiom, reused rather than invented: *"A transactional
projection accelerates claims but is rebuildable and checked against the
chain."*

### `blocked` is derived, so it can never drift

```sql
-- a task is blocked iff something it needs has not landed
SELECT t.id FROM task t
WHERE EXISTS (SELECT 1 FROM depends d JOIN task_state s ON s.task_id = d.needs
              WHERE d.task = t.id AND s.state <> 'landed')
   OR EXISTS (SELECT 1 FROM gate g WHERE g.task = t.id AND g.resolved_at IS NULL);
```

`depends` is #346's, unchanged. `gate` is the small addition this needs: a
task blocked on **him** rather than on another task — an open questions.md
entry, a review decision — which today is free prose in 28 entries and gets
hand-annotated `UNBLOCKED` in 4.

The consequence is that landing #263 **writes no unblock events at all**:
every task depending on it becomes selectable the instant its `landed` row
commits. One of the eighteen causes disappears by construction, and with it the
whole class of "the ledger says blocked and the blocker landed yesterday".

What is *not* derived is `hold` — a judgement to park work, with a reason and
an actor, set and cleared by real events. Separating the two matters: today one
prose phrase means both *"mechanically waiting"* and *"we decided not now"*,
and only the first can be computed.

### Burndown is a query

```sql
-- arrivals and completions are single rows now, not first-sightings to catch
-- before grooming prunes them
SELECT (at_bucket) AS t0,
       SUM(cause IN ('filed_from_command','filed_from_idea',…))       AS arrived,
       SUM(to_state = 'landed')                                        AS landed
FROM task_event GROUP BY t0 ORDER BY t0;
```

Today's equivalent is 331 `git show` invocations plus 331 Markdown parses,
memoised on HEAD because it is expensive. As a `GROUP BY` over a few thousand
rows it needs no cache, so there is no cache to go stale — and the bucket step
stays a presentation choice (`_burn_step` picks it from the span today) instead
of being frozen into a stored table.

The open **level** stays a level, not a count of events, exactly as
`ledger_series` already computes it: a bucket with no events inherits the one
before rather than reading as a drop to zero.

### The dashboard status section

`status.json` keeps the fields that are genuinely a live process's own claim —
`task` prose, `goal`, `agents`, `monitors`, `deploy`, `last_tick`,
`last_commit` — and **loses every task-derived field**: `queue`,
`current_task_ids`, and per-agent `task_ids`. Those become queries:

- queue depth → `SELECT state, COUNT(*) FROM task_state GROUP BY state`
- "which tasks are in progress" → `WHERE state='in_progress'`
- "which tasks does agent X hold" → `WHERE owner='dreamer:X'`
- `/tasks` per-row badge → the same, per row

That is what removes F1's disagreement, and it is the direct reading of his
*"no agent hand-editing `status.json`"*.

Two rules the dashboard must keep, both already learned here:

1. **A store it cannot read renders `unknown`, never zero** — #136's rule,
   *"zero entries is not one fact"*. `BURN_NONE` / `BURN_ERROR` already
   distinguish these for the burndown; the status section needs the same three
   states.
2. **Merge, never re-author** `status.json` — `lessons.md:953`: a coordinator
   re-authored it from scratch and fifteen lanes' `retired_today` vanished with
   no error, because a projection with a missing key is indistinguishable from
   one that never had it.

---

## Ordering and identity

**Reuse #263's mechanism; do not share its sequence.**

- **Own ordinal.** `task_event.ordinal` is the store's own monotonic sequence.
  Sharing `event_ordinal` would serialise every task write behind the receipt
  allocator and make the journal's *"bounded full rebuild from ordinal 1"*
  proportional to task churn — but the decisive reason is F2: a shared sequence
  means shared rows, and shared rows mean a nullable `receipt_id`.
- **Same hash chain, for a different threat.** `H_0 = SHA-256(stream_id ||
  schema_version)`, `H_i = SHA-256(domain_tag || H_(i-1) ||
  length_framed(canonical_event_i))` — #263's construction verbatim, with a
  distinct `domain_tag` so a task event can never verify as a receipt event.
  On receipts the chain is tamper-evidence over what a human said; on task
  events its job is narrower and still worth having: detecting an out-of-band
  write — a second process on a stale schema, a restored backup, a hand-edited
  DB. Once #263 ships the verifier it is near-free.
- **A canonical byte form from day one**, even though nothing exports it yet.
  The chain needs one anyway, and defining it now is what makes the
  git-portability question below a *deployment* choice instead of a schema
  change: a committed text export becomes a byte-for-byte projection whose
  rebuild is provable by re-verifying the chain.

**Two footguns, each a checked invariant rather than a comment.** #346 found
the first pair of these; the shape repeats:

| footgun | what breaks | the check |
|---|---|---|
| `PRAGMA foreign_keys` is **OFF by default, per connection** | `receipt_id`, `task_id`, every lookup-table reference validates nothing on any connection that forgot | one place in the adapter sets it; a test asserts a violating insert raises |
| `BEGIN` (deferred) takes the write lock **late** | a read-then-CAS transaction hits `SQLITE_BUSY` mid-transaction, where retry is not safe; under concurrency this is the common failure, not the rare one | every write verb uses `BEGIN IMMEDIATE`; a two-process test asserts one writer wins and the other retries cleanly |

---

## Concurrency

Today's rule is *"the coordinator is its only writer"*, and its stated reason
is the failure #264 exists to remove: *"two dreamers mint the same id, and the
ledger loses exactly what it exists to keep."*

**What the store removes structurally:**

- **Lost ids.** `task(id INTEGER PRIMARY KEY)` with allocation inside the
  transaction makes two writers minting the same id impossible, rather than
  avoided by policy.
- **Lost entries.** A concurrent append cannot overwrite another's, because
  there is no whole-file rewrite.
- **Split-brain state.** `task_state` moves only under CAS.

**What it does not remove, and must be said:** two dreamers each deciding to
file "the same" idea still produce two rows. Deduplication is judgement, and no
schema performs it. Grooming stays a loop responsibility (`superseded`).

**Claim (`grab`), as one transaction:**

```sql
BEGIN IMMEDIATE;
  UPDATE task_state
     SET owner = :actor, claim_token = :token, lease_until = :now_plus_lease,
         state = 'in_progress', revision = revision + 1, at_ordinal = :ord
   WHERE task_id = :id AND revision = :expected
     AND (owner IS NULL OR lease_until < :server_now);   -- expired is claimable
  -- 0 rows changed => someone else holds it; abort, report the holder, do not retry blindly
  INSERT INTO task_event(...) VALUES (:ord, :id, :server_now, 'claimed_by_agent', ...);
COMMIT;
```

#263's claim laws apply unchanged and are not re-derived here: atomic and
exclusive claim, unguessable token, monotonic revision, start/renew/finish
compare task+token+actor+revision, expired claims are reclaimable, a stale
claimant cannot finish, dual reclaimers cannot both win. **Lease deadlines use
the server/backend clock, never a client's and never an LLM's** — the same rule
`lessons.md:326-335` records the coordinator breaking by estimating `last_tick`
from a heartbeat message.

**A stale claim on recovery is an EVENT, not a silent overwrite.** This is the
one place a task deliberately differs from a receipt. An expired receipt claim
may be quietly reclaimed. An abandoned *task* claim is information the
coordinator needs — which dreamer vanished, when, and therefore which files
may still be held — so recovery appends `lease_expired` with the prior owner in
`detail` before clearing the row. A reclaim that erased the owner would delete
the only durable trace of a dreamer that died mid-increment, and that trace is
what the file-ownership invariant reads.

**Worktrees.** A dreamer in `.worktrees/x` shares the machine, so it shares the
store — the store lives at the target root, not in the worktree, and is
gitignored, so a worktree's copy of the repo cannot fork it. One consequence to
verify at implementation: `git worktree` checkouts have their own working
directory, so any path resolution must go through the target, exactly as
`ledger_series` already resolves the ledger pathspec against the repository
**top level** rather than the target (`watch.py:6970-6979`, #217).

---

## The seam a non-Python CLI can implement

#264's entry names `dreamwork tasks list|get|grab|cycle` as the public seam
instead of direct `tasks.md` mutation, and his 01:05 note wants a small fast
binary with git-style `dreamwork-thingy` extension dispatch. So the boundary is
stated as **data and SQL, not as a Python protocol**:

1. **The schema and its migrations are SQL files**, versioned, applied by any
   implementation.
2. **Every write verb is one named transaction script** — the `BEGIN
   IMMEDIATE` … `COMMIT` above, with its predicate and its event row spelled
   out. Any language with a SQLite driver implements it; so does the `sqlite3`
   shell.
3. **The canonical event byte form and the chain construction are a spec**,
   not a function, so two implementations produce the same hashes.
4. **The enum vocabularies are lookup tables**, so an extension in another
   language reads the legal values instead of hard-coding them — #346's S4
   ruling, applied to `cause` and `state`.

Nothing above depends on a Python class, and no `JournalAdapter`-style Protocol
is required for task state. `#352` (standardise the two `ledger_entries`
implementations, three callers) remains the prerequisite it was ruled to be:
the *read* seam has three doors and re-pointing "the reader" is only meaningful
once there is one.

**The verbs this boundary implies**, beyond #346's read-only set:

```
dreamwork tasks grab <id> [--lease 20m]      # CAS claim; prints the holder on refusal
dreamwork tasks release <id> --token …
dreamwork tasks cycle <id> --to landed|dropped --cause … --detail …
dreamwork tasks file --title … --cause … [--receipt …]
dreamwork tasks hold <id> --reason … | tasks unhold <id>
dreamwork tasks history [<id>] [--since <ordinal>] [--json]
dreamwork tasks burndown [--step 4h] [--json]
dreamwork tasks watermark                    # MAX(ordinal); what a reader compares
dreamwork tasks rebuild --verify             # replay, diff, exit non-zero on divergence
dreamwork tasks export --to tasks.md         # deterministic shadow; diff is the check
```

`--json` stability across independently compiled extensions is #346's open
question and stays open.

---

## Rebuild, and how a reader checks

Because `task_state` is written in the same transaction as its event, it cannot
*lag*. It can still be **wrong** — a bug, a hand-edit, a restored backup, a
second process on an older schema. So three checks, and each is a command he
can run:

1. **`tasks rebuild --verify`** replays `task_event` from ordinal 1 into a
   temporary table, diffs against `task_state` row for row including
   `at_ordinal`, and exits non-zero on any divergence. Rec: it also runs once
   at loop init, where it is cheap and where `initialization.md:181`'s
   reconcile step is already the moment for it.
2. **Chain verification** over `task_event`, #263's construction, catching a
   mutated or deleted row below the high-water ordinal.
3. **`tasks export --to tasks.md`** regenerates the shadow deterministically;
   a non-empty diff is health, never a block. This is the pattern
   `.dreamwork/run-mode` already sets — one authoritative store, one
   best-effort mirror, and `file-formats.md:503` saying outright that
   *"`status.json` is an ephemeral loop claim and must not be the sole
   store."*

**And a reader's own staleness** is `tasks watermark`: `/data.json` carries
`MAX(ordinal)` alongside the existing `/mtime` generation, so an open page
holding an old watermark knows it is behind without a new channel — the same
route `tint` and `run_mode` already ride.

---

## Red-first acceptance fixtures

Stated as *the production line that must change for this to fail*, because
three checks in this repo have passed over the thing they were named for, and
twice in one night a red-run came back green because the test's own scaffolding
stood in front of the bug.

1. **A transition and its state change are one transaction.** Kill the process
   between the `INSERT` and the `UPDATE`; recovery shows neither. *Break by
   splitting them into two transactions — the test must show an event with no
   state change.*
2. **`task_state` is rebuildable.** Corrupt one `task_state.state` directly,
   then `rebuild --verify` exits non-zero and names the task. *Break by having
   rebuild read `task_state` instead of replaying `task_event` — a rebuild that
   copies its own target passes on any corruption.*
3. **`at_ordinal` catches an inconsistent row.** Set a `state` that its
   `at_ordinal`'s event does not imply; verify fails. *Break by dropping
   `at_ordinal` from the diff.*
4. **Burndown is not stale after an uncommitted transition.** File and land a
   task with **no git commit**; the series and headline counts move.
   *Break by re-pointing burndown at `ledger_series` — this is F4's whole
   point, and it must go red on today's code.*
5. **Queue depth has exactly one source.** Assert no writer sets a
   task-derived field in `status.json`, and that the dashboard's queue number
   equals the store's `GROUP BY`. *Break by restoring `status.json`'s `queue`
   — and the fixture must construct a state where the two would differ, i.e.
   at least two states with different non-zero counts, derived at runtime and
   asserted to differ (F1's 122-vs-113 is the live instance; a literal tuned
   to today's numbers is a check with an invisible expiry).*
6. **Two writers, one winner.** Two processes `grab` the same task; exactly
   one succeeds, one event is written, the loser is told the holder. *Break by
   using `BEGIN` instead of `BEGIN IMMEDIATE`, or by dropping the `revision`
   predicate.*
7. **A dead claimant leaves a trace.** Kill a claimant mid-lease; after
   expiry, reclaim succeeds **and** a `lease_expired` event names the prior
   owner. *Break by clearing `owner` without appending the event.*
8. **`blocked` cannot drift.** Land a blocker; the dependent becomes
   selectable with no unblock write anywhere. *Break by storing `blocked` as a
   column — the test must fail with a task still blocked by a landed
   dependency.*
9. **A receipt-borne transition links, and a loop transition does not lie.**
   `filed_from_command` carries a `receipt_id` that resolves; a
   `filed_from_idea` with a `receipt_id` is refused. *Break by making
   `receipt_id` free text, or by dropping `PRAGMA foreign_keys=ON` — assert
   the pragma in the test, since the connection default is OFF.*
10. **Purge cannot reach history.** Run #263's purge over a store whose tasks
    cite purged receipts; every `task_event` row survives and the burndown is
    unchanged. *Break by including `task_event` in the purge policy's scope.*
11. **A store the dashboard cannot read renders `unknown`, not zero.** Make it
    unreadable; the status section and burndown both say so. *Break by
    defaulting a failed read to 0 — and the fixture must distinguish
    "genuinely zero" from "unknown", or it passes on either.*
12. **The export is a shadow.** Make the `tasks.md` write fail; the transition
    still commits and health reports it. *Break by writing the export inside
    the transaction.*
13. **A task event cannot verify as a receipt event.** Feed a task event to the
    journal's chain verifier with the same ordinal; it fails on `domain_tag`.
    *Break by sharing the tag.*

---

## What stays open

- **Git portability, and it is the one that could change the shape.** The
  ledger is committed project content today, so the burndown works on any fresh
  clone — git history *is* the source. A SQLite store is gitignored and
  machine-local, so a clone starts with no history. Three candidates: commit
  the DB (binary, unmergeable), gitignore it and commit a deterministic
  append-only text export of `task_event` (mergeable, and rebuild is provable
  because the chain re-verifies), or accept machine-local for v1. **Defining
  the canonical byte form now (§Ordering) makes this a deployment decision
  rather than a schema change**, which is why it is open rather than blocking.
  It is #294's scope; it is listed here because it constrains this one.
- **Multi-database atomic commit in WAL mode** — measured to raise no error,
  not verified to be atomic. Check SQLite's documentation before relying on it
  (F6). One database file makes the question moot, which is a second reason for
  one.
- **`gate`'s exact reference.** It points at whatever #289's `Review
  (pending|accepted|rejected, stamp)` record and the questions.md entry
  identity become. Deliberately not decided here — #289 was approved for design
  only and told to *"tie future versions into sqlite"*.
- **Lease duration and renewal cadence.** A dreamer's increment is capped at
  ~20 minutes, which suggests a lease near that, but the renewal beat belongs
  with the heartbeat's, and that is a loop-policy question.
- **`--json` contract stability** across independently compiled extensions —
  inherited from #346, unchanged.
- **Whether `dropped` and `superseded` are one state or two.** They read
  differently in grooming prose and the distinction may be `cause`-only.

## What I deliberately did not decide

The migration and its cutover ordering, the import of git history into
`task_event` (whether the 331 revisions become synthetic events, and with what
`actor`), rollback, `tasks.md.deprecated`'s frontmatter, mixed-writer freeze,
and the read-side entity work #346 already owns. All #294's, all after a
ruling.

## What approval of this does not authorise

Nothing is built. Approving accepts **the boundary**: that `task_event` is the
single authority for task history, that `task_state` is its only materialised
row and exists for CAS alone, that burndown and the status section are queries,
that `status.json` loses its task-derived fields, and that receipt and task
transitions are two facts joined by a foreign key rather than one fact in two
places.

It does **not** authorise creating a table, writing a CLI, migrating, cutover,
deleting anything from `status.json`, touching `tasks.md`, PostgreSQL, or
payload purge — those wait on #263's implementation gate exactly as the rest of
#294 does. #263's own approval gate says its approval *"does not authorise
implementation, migration, deployment, PostgreSQL operation, topic chats, or
payload purge"*, and this document inherits every one of those limits.

--- SUMMARY ---

- **The recommendation: neither of his two named options, and the reason is one
  finding.** A task transition and a user event are different facts, so
  "never dual-write two fallible truths" is satisfied by joining them with a
  foreign key, not by forcing them into one row. Task history is its own
  append-only `task_event` log, in the **same SQLite database** as #263's
  journal, appended in the **same transaction** as the CAS that moves
  `task_state`. No outbox, no drain.
- **Option A (share #263's journal) is refuted** because `Transition.receipt_id`
  is mandatory in that document's own notation, its states are the receipt
  processing lifecycle, and its replay enumerates *receipt* events — so task
  events would need a nullable receipt and a filter in every consumer.
- **Option B (an outbox) is refuted** because an outbox exists to cross a
  boundary the consumer cannot cross, and both consumers read the same file the
  writer just committed to. An undrained outbox row *is* the second derived
  truth #294 forbids. If "outbox" only meant "the task store keeps its own
  transactional log", that is the rec and we agree.
- **The constraint is already violated and the two truths already disagree by
  9**: the ledger and burndown say 122 open, `status.json` says 113, and inside
  `status.json` `current_task_ids` is `[]` while the agents hold 252, 264, 284.
  #306's lesson predicted exactly this.
- **Burndown is already a projection of an append-only log — git — and git
  lags**: 331 ledger commits, median gap 4.8 min, p90 20 min, max 13.3 h, and
  the working tree is explicitly not read. That distribution is the "no
  Git-HEAD lag" his amendment forbids.
- **Most transitions have no receipt, and even the ones that do cannot share
  its transaction.** Eighteen enumerated causes from the actual loop; two carry
  a receipt. `_handle_command` mutates no task state at all — it appends one
  `watch-events.log` line and an LLM decides later, one-to-many.
- **Nothing is a stored view except one row.** The governing rule: a
  materialised row exists only where a *writer* must CAS against it. So
  `task_state` is a table; burndown, queue depth, the `/tasks` badge and
  `blocked` are queries. `blocked` being derived means landing a blocker writes
  **no** unblock event and can never drift — which removes one of the eighteen
  causes by construction.
- **Staleness is a comparison, not a belief**: `task_state.at_ordinal` names
  the event that produced the row, `tasks rebuild --verify` replays and diffs,
  the chain catches out-of-band writes, and `tasks watermark` on `/data.json`
  lets an open page know it is behind over the channel that already exists.
- **Own ordinal, #263's mechanism, distinct `domain_tag`** — sharing the
  sequence means sharing rows, and sharing rows means the nullable receipt
  again.
- **Two footguns become checked invariants**, in #346's style: SQLite's
  `foreign_keys` pragma is OFF per connection, and deferred `BEGIN` takes the
  write lock late, which is the common concurrency failure rather than a rare
  one. `BEGIN IMMEDIATE` everywhere, asserted.
- **One database file, measured**: SQLite has no syntax for a foreign key into
  an ATTACHed database (`near ".": syntax error`), so the
  `task_event.receipt_id → receipt` check can only exist in one file.
- **A stale claim is an event, not a silent reclaim** — the one place a task
  deliberately differs from a receipt, because which dreamer vanished is what
  the file-ownership invariant reads.
- **Thirteen red-first fixtures**, each naming the production line that must
  change for it to fail, and two of them naming the fixture-shaped way the
  check could pass hollow.
- **Open, and honestly load-bearing:** git portability. The ledger is committed
  and the burndown works on any clone; a gitignored store loses that. Defining
  the canonical event byte form now makes it a deployment choice rather than a
  schema change, so it does not block — but it is the question most likely to
  move the shape if he rules the other way.
