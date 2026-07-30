# #264 — Can a second dreamer/coordinator run in parallel against the CURRENT architecture?

Findings only. No production code touched; `watch.py` read throughout. Every
claim cites a file:line verified at HEAD `2cc00174` (clean tree). The filing
(#264) predates several landings; where its assumptions are moot, this says so.

Model: glm-5.2 per the dispatch record (a lane cannot know its own model).

---

## Verdict (read this first)

**No.** A second coordinator cannot run safely against the same target today,
and the reason is not a missing lock — it is that the durable state a
coordinator acts on is **machine-local per clone by design**, so a second
coordinator in a second clone operates on an *independent, empty* copy of
every load-bearing store and shares only git-tracked text files that are no
longer the source of truth. The concurrency machinery that *does* exist
(SQLite WAL + `BEGIN IMMEDIATE`, CAS state flips, hash-chained append-only
logs, a cross-process `flock`, idempotent receipt `receive`) is correct **but
only within a single database file on a single target**. Two clones have two
files; SQLite's locking and CAS protect one of them, not the pair.

The single highest-leverage finding is also the one the filing could not have
known: **the #294 cutover replaced `tasks.md` with a 5-line deprecation
notice but made the replacement store (`ledger.sqlite3`) gitignored and
machine-local**, with cross-clone sharing explicitly deferred to a "committed
text export (T3)" that has **not landed**. So at HEAD there is *no functioning
shared task-ownership surface a second coordinator can read* — see §1.

**Top recommendation:** do not attempt two coordinators on one target until
the T3 text-export (or an equivalent shared, append-only, merge-friendly
projection of the store) lands. The cheapest *real* safety is to keep the
existing single-coordinator-per-target invariant and run a second loop only as
**stateless fan-out workers** (the model the loop already uses: 2–5
`spawn_subagent` lanes per coordinator, each in an independent clone, each
owning disjoint files by convention, reconciled by the *one* coordinator).
The §7 table ranks the changes that would make a genuine second coordinator
safe, with cost.

---

## 0. What exists now (verified, not assumed)

The brief's "what exists now" list is *partially* true at HEAD. Verified:

- **#294 SQLite ledger: code LIVE, store NOT shared, and NOT the source of
  truth in a fresh clone.** `ledger_store.py` / `ledger_write.py` /
  `ledger_parse.py` are landed and exercised. But `ledger.sqlite3` is
  **gitignored** (`.gitignore:24`: *"#294: the ledger store is machine-local
  (C1 — the same trust boundary as the journal); cross-clone history is the
  committed text export (T3), a later deployment choice"*). `ledger_store.py`
  itself states it (`ledger_store.py:16`: *"Machine-local, stdlib sqlite3
  only (C1)"*). **T3 has not landed.**
- **`tasks.md` is a 5-line deprecation notice**, tracked and committed:
  `<!--dreamwork-migration-notice … ledger migrated to SQLite store; use
  'dreamwork tasks …' -->`. The real ledger (9,143 lines) lives in
  `tasks.md.deprecated`.
- **`source_of_truth()` returns `'markdown'` in this clone** because the
  cutover watermark lives in the store's `meta` table
  (`ledger_parse.py:158-184`, key `ledger_cut_over`), the store is 0 bytes /
  absent, so `is_cut_over` is False. Against the 5-line notice, `dev/ledger.py
  counts` **errors** (`assert_headings`, `dev/ledger.py:82-96`: *"found 0
  `## Open`"*). This is not a quirk of this worktree: it is the state of *any
  fresh clone*, because the watermark and the store contents never travel in
  git.
- **User-event journal (#263): LIVE and correct within one file**, also
  machine-local (`.gitignore`: *"Durable user-event journal (#263). Machine-
  local per target"*). Idempotent `receive`, hash-chained events, CAS
  transitions, per-receipt claim/lease/finish (`user_events/sqlite.py`).
- **Multi-lane fan-out is the lived reality** — but as *stateless workers
  under one coordinator*, not as two coordinators. Since 2026-07-29 18:02 the
  dispatch form is the harness's native `spawn_subagent`: lanes are
  independent clones, invisible to `pgrep -af ccc` and to `git worktree list`
  (`status_sync.py:194-209` `OBSERVABLE_DISPATCH=("ccc",)`; #423 audit; #537).
- **Live defects in this area, confirmed open:** #465 (a lane can edit the
  main checkout undetected), #423 (harness-clone invisibility), #537 (the
  liveness probe is blind to the current dispatch form).

---

## 1. The split-brain finding (the thing the filing could not have known)

This clone's state is internally inconsistent, and that inconsistency *is* the
answer to #264:

| signal | says | source |
|---|---|---|
| `tasks.md` content | "ledger migrated to SQLite; use `dreamwork tasks`" | committed notice |
| `source_of_truth()` | `'markdown'` | `ledger_parse.py:184`, no watermark |
| `ledger.sqlite3` | absent/empty, gitignored | `.gitignore:24` |
| `dev/ledger.py counts` | ERROR (no `## Open`) | `dev/ledger.py:82` |

In the *live* target the coordinator ran `dreamwork tasks migrate`, which
populated the store, set the watermark, and replaced `tasks.md` with the
notice — there `source_of_truth()` is `'store'`. In a *second clone* (a second
coordinator, or any `spawn_subagent` lane) the store and watermark do not
exist, so the reader flips to markdown and reads a notice with no entries.

**Concurrency consequence:** the task ledger — the thing that decides who owns
what and what is open — does not exist as a readable surface in a second
coordinator's clone at all. The "second coordinator" cannot see task #N is
open, cannot fold it, cannot avoid the file its lane owns, because it has no
task rows. This is stronger than "two writers race": it is "the second writer
has no state to race on." The architecture is single-coordinator-per-target
*by the placement of its state*, not merely by convention.

---

## 2. Store-by-store walk — failure mode for a second coordinator

Two deployment shapes matter, and they fail differently:
- **(A) Two coordinators, two clones** (the `spawn_subagent` reality). Each
  has its own machine-local DBs; they share only git-tracked text.
- **(B) Two coordinator processes, one clone** (sharing one `.dreamwork/`).
  They share the DBs and domain files directly.

### ledger.sqlite3 — the task ledger store — UNSAFE (per-clone); SAFE within one file
- Within one DB the writes are correct: WAL + `synchronous=FULL` +
  `busy_timeout=5s` (`ledger_store.py:295-309`); `file_task` uses AUTOINCREMENT
  so *"two writers can never mint the same id (R1)"* (`ledger_write.py:108`);
  `land_task` is a real CAS (`UPDATE … WHERE id=? AND state='open'`,
  rowcount-checked, `ledger_write.py:148-170`); each transition is one
  `BEGIN IMMEDIATE … COMMIT` with a hash-chained `task_event` row.
- **Shape A failure:** two clones have *two independently-seeded* stores.
  Each seeds its AUTOINCREMENT from the markdown ledger at migration
  (`ledger_store.py:416-466`, `derive_next_id` = MAX(id)+1). Both seed to the
  same N; both then `file_task` → **both mint #N → permanent-id collision**
  with no reconciliation path (T3 text-export not landed). The CAS in
  `land_task` protects one file; it cannot see the other clone's row, so both
  can "land" the same logical task in two stores.
- **Shape B failure:** SQLite serializes them (one file), so no corruption —
  but `open_store` *refuses an unseeded first open* (`ledger_store.py:636`),
  and the cutover watermark + seeding are one-time acts with no multi-holder
  guard (unlike the journal's cutover lease, §`user_events`). A second process
  migrating concurrently is unguarded.

### user-events.sqlite3 — the journal — SAFE to receive; UNSAFE to *drain* with two coordinators
- `receive()` is idempotent: `client_action_id` UNIQUE + digest compare before
  insert → inserted | replay | conflict (`user_events/sqlite.py:614-782`).
  Two watch.py servers receiving the same submission twice → one receipt. Good.
- The per-receipt lifecycle (`transition`/`claim`/`finish`,
  `user_events/sqlite.py:806-1408`) is **explicitly multi-consumer**: it takes
  a `consumer`, uses CAS on `revision`, and has claim tokens + leases with
  expiry/reclaim (`claim`, `:1166-1304`). Two agents competing for one
  receipt are handled — *if they go through claim/finish*.
- **The drain is single-consumer and is the hazard.** `dev/journal_consume.py`
  hardcodes `CONSUMER = "coordinator"` (`:108`). The cursor row is keyed by
  that one name. `advance_cursor` verifies the chain and checks
  `expected == verified_head` (`user_events/sqlite.py:1429-1470`) **but the
  cursor `UPDATE` has no revision CAS** (`:1492-1503`: it overwrites
  `WHERE consumer=?`). Two coordinators sharing the name "coordinator":
  - both read `(cursor, head]`, both report the same receipts UNAPPLIED, both
    **act on them** (dispatch lanes, reply to chats) → duplicate work;
  - the `applied.md` proof ledger reconciles under a real cross-process
    `flock` (`user_events/apply.py:276` + `domain_files.DomainFileLock`,
    `user_events/domain_files.py:44-99`), and is idempotent (marker present →
    APPLIED, no write), so the *marker file* is not torn — but the marker is
    written **before** the coordinator acts, so the concurrent window still
    double-reports;
  - because the cursor UPDATE ignores revision, a late-running advance to a
    lower ordinal **rewinds** the cursor (15 → 10), re-draining events. Not
    lossy (append-only + idempotent markers), but a liveliness/rework hazard.
- **Shape A failure:** two clones have *two journals*. Only the clone running
  watch.py receives receipts; the other's journal is empty → the second
  coordinator sees none of the human's submissions. The user-event stream does
  not fork to a second clone.
- Net: the journal is the store *closest* to multi-coordinator-safe (its
  receipt CAS/lease layer was designed for competing consumers), but the
  **batched-delivery wiring collapses it to one consumer**, and the cursor
  lacks a revision guard.

### tasks.md — UNSAFE (now a notice); was single-writer-by-convention
- Pre-cutover, `tasks.md` was the shared (tracked) ledger, *"single-writer by
  design"* (#264-evidence brief). The one supported writer, `dev/ledger.py`,
  uses atomic temp-then-`os.replace` (`dev/ledger.py:288-291`) — but that
  protects one clone's write, not two clones' git merge. Two coordinators
  folding different tasks produce a text conflict that git cannot auto-merge
  (entry blocks, `Next id` header, section order). The `#440` heading-
  invariant exists precisely because hand-rolled splits corrupted this file.
- Post-cutover (HEAD), it is a 5-line notice — so this store **carries no
  task state at all** in a fresh clone (§1). The filing's "single-writer for
  the ledger" strategy is **moot**: the ledger is no longer this file.

### questions.md / answers.md / chats-v1 — UNSAFE across two watch.py servers (#262, open)
- The write routes (`/ask`, `/answer`, `/comment`, `/command`, `/tint`) are
  guarded only by `ANSWER_LOCK = threading.Lock()` — an **in-process** lock
  (`watch.py:14301`, used at `:15096/15119/15157`). `domain_files.py` calls
  this out by name: *"The existing writer's only mutual exclusion is an
  in-process threading.Lock (watch.py's ANSWER_LOCK), which two watch.py
  processes on one target serialise against nothing — the second half of
  #262"* (`user_events/domain_files.py:6-11`). The managed-file `flock` +
  digest + atomic-replace machinery (`domain_files.py`) that *would* make
  these safe is **"not wired to watch.py's writers"** (`domain_files.py:22`).
- `chats-v1` transcripts are appended by `apply_chat_turn`
  (`watch.py:12884`) under the same in-process lock. Two servers replying to
  one chat → interleaved/torn transcript.
- **Shape B failure** (two watch.py servers, one target): torn writes, lost
  answers, duplicate chat turns — the unmitigated #262.

### status.json — UNSAFE (no lock, no atomicity; "one writer, no reviewer")
- Gitignored. Carries the coordinator's dispatch/ownership table (`dreamers`)
  and is written by *"more than one hand"* — the coordinator at dispatch, the
  syncer at reap (`status_sync.py:8-12, 328-358`). It is *"the one file in
  the system with no reviewer."*
- `status_sync.py` reads-defensively then writes with a plain
  `spath.write_text(json.dumps(...) + "\n")` (`status_sync.py:519`) — **no
  flock, no temp-then-rename**. Two syncers (or a syncer + a dispatching
  coordinator) interleaving read-modify-write → **lost update** (one author's
  `dreamers`/`deployed`/`monitors` clobbered) or a **torn/truncated write**
  that the next reader must treat as the normal case (`status_sync.py:328`).
- **Shape A:** two clones have two `status.json`; ownership does not cross
  clones, so neither coordinator can avoid the other's files via this table.

### posture / run-mode / question-sigs.json — machine-local, single-reader-per-tick — N/A for sharing
- All gitignored as machine-local posture (`.gitignore`: posture, run-mode,
  question-sigs.json each annotated *"describes THIS host … committing it
  would export one machine's settings"*). `question-sigs.json` is rewritten by
  `collect()` via tmp+`os.replace` (`watch.py:13743`) — atomic within one
  process, last-write-wins across two. These describe *one dashboard's* view;
  a second coordinator's copy is simply a different (correct) view of its own
  host. No shared-state failure, but also **no shared meaning**: a posture
  change by coordinator A does not reach B.

### submissions.log — append-only, in-process lock — WEAK across processes
- Append-only (#199), guarded by `SUBMIT_LOCK = threading.Lock()`
  (`watch.py:14338`). In-process only. Two servers appending rely on the OS
  `O_APPEND` atomicity for single writes; the lock wraps more than the write,
  so a multi-line append under contention can interleave. Recovery-only
  surface, low blast radius, but not multi-process-safe by construction.

### sig store (#534) — see question-sigs.json above.

### handoffs.md / relay/ — append-only git-tracked — SAFE-ish; git merge is the real cost
- Append-only by convention (one `## Pending` line per landing, `cat >>`).
  Concurrent appends are atomic at the line level on local FS. Two
  coordinators landing concurrently → two lines; the failure mode is a **git
  merge** on the same file, which for append-only markdown is usually
  auto-resolvable but is not guaranteed (the `## Folded` section the
  coordinator owns, and any rewrite, loses a concurrent appender's line — the
  #264-evidence brief warns *"a rewrite loses their line"*).

---

## 3. What the filing's strategies are worth against THESE failure modes

The filing lists: single-writer+workers; append-only events/materialised
views; locks/atomic-replace/CAS; leases; SQLite; per-record spools.

- **Single-writer + workers — ALREADY THE DEPLOYED MODEL, and it works.** The
  loop runs one coordinator driving 2–5 `spawn_subagent` lanes. The lanes are
  stateless workers that own disjoint files (`Lane-owns:`), commit with
  `git commit --only <paths>`, and report back via `handoffs.md`/relay. This
  is the only concurrency shape the current state placement *supports*, and
  the evidence (13 lanes in one session, #264-evidence brief) is that its
  failures are second-order (registry-checked dirs, `--only` hunk sweeps,
  containment #465), not ledger corruption. **The filing's question is
  answered: keep this; do not promote a worker to a second coordinator.**
- **SQLite — necessary, NOT sufficient.** It removes the markdown single-writer
  bottleneck *within one file* (CAS land, AUTOINCREMENT ids), which is real.
  But it is machine-local, so it does not create a *shared* truth — it
  fragments truth across clones. SQLite solves the "two writers, one file"
  problem; #264's problem is "two writers, two files." **The store as built
  makes a second coordinator worse, not better**, because it removes the one
  shared (tracked) surface (tasks.md) and replaces it with N unshared ones.
- **Append-only events + materialised view — the right shape for sharing, and
  it is half-built.** The journal is exactly an append-only event log with a
  hash chain and cursor projection. A *committed* append-only export of task
  transitions (the `task_event` table is already append-only and hash-chained,
  `ledger_store.py:91-153, 244-261`) consumed by each clone into its own
  materialised `task` view is the T3 design that has not landed. This is the
  strategy that maps to the actual failure mode (§1): make the *event log*
  shared (git, like the journal's design intends) and keep the *materialised
  view* local. **Highest fit; largest gap.**
- **Locks / atomic-replace / CAS — sufficient for the files that lack them.**
  The domain-file writers (questions/answers/chats) and `status.json` are the
  live #262/#394 defects; the `flock`+atomic-replace+digest primitive already
  exists (`domain_files.py`) and is simply unwired. Wiring it would make Shape
  B (one clone, two processes) safe for those files. It does nothing for
  Shape A (two clones).
- **Leases — already in the journal, absent in the store and the dispatch
  table.** The journal's claim/finish lease (`user_events/sqlite.py:1166`)
  would let two coordinators *contend for one receipt* safely — if the drain
  used per-receipt claims instead of a single cursor. `status.json`'s
  `dreamers` (who owns task #N) has no lease/claim; two coordinators can
  dispatch the same task because nothing records an ownership claim with an
  expiry. The `task_state` table *has* `owner`/`claim_token`/`lease_until`
  columns (`ledger_store.py:262-272`) — **the schema for task leases exists
  but the verbs to use them were deliberately deferred** ("the full #264 verb
  set (grab/release/cycle/hold) … out of scope", `ledger_write.py:20-24`).
- **Per-record spools — the drain's applied-ledger is one, and it is the
  model that makes the cursor replay-safe.** `applied.md` markers under `flock`
  (`user_events/apply.py`) are what stop a rewound cursor from double-applying.
  It is the right local fix for the drain's replay window, not a sharing fix.

---

## 4. What is ALREADY safe vs. safe-by-convention vs. unsafe

**Already safe (by mechanism):**
- Journal `receive()` idempotency (one receipt per submission, even across two
  servers) — `user_events/sqlite.py:614`.
- Per-receipt claim/lease/finish CAS (multi-consumer, expiry/reclaim) —
  `user_events/sqlite.py:1166-1408`.
- Within-one-DB task writes: AUTOINCREMENT ids, CAS land, hash-chained events,
  one transaction per transition — `ledger_write.py`, `ledger_store.py`.
- The applied-ledger exactly-once proof under cross-process `flock` —
  `user_events/apply.py`, `domain_files.py`.
- Append-only event logs (journal `events`, store `task_event`) — append never
  alters a prior row, so concurrent appends to one file are safe.

**Safe-by-convention-only (name the convention + its enforcement gap):**
- *"The coordinator is the single writer to tasks.md / the store"* — enforced
  only by there being one coordinator; **no guard prevents a second**. The
  store even removes the tracked fallback, so the convention is now load-
  bearing with no escape hatch.
- *"Lanes own disjoint files (`Lane-owns:`) and commit `--only <paths>`"* —
  enforced softly by `lint.check_brief_lane_owns` and `dev/lane_guard.py`, but
  `lane_guard`'s registry is `wt/*` linked worktrees and is **blind to
  `spawn_subagent` clones** (#423/#465); `--only` isolates paths not hunks
  (#264-evidence). The disjointness invariant holds *within one coordinator's
  fan-out*; it cannot be checked *across* two coordinators because neither
  sees the other's ownership.
- *"Append one line to handoffs.md / relay, never rewrite"* — no lock; relies
  on every writer honouring `cat >>`.

**Unsafe (no mechanism, or mechanism defeated by per-clone placement):**
- Cross-clone task state (§1): no shared surface; id collision on file.
- The drain cursor under a second consumer name "coordinator" (§2 journal).
- questions.md / answers.md / chats-v1 across two watch.py processes (#262).
- `status.json` read-modify-write (no lock, no atomicity).
- Task ownership/dispatch: `task_state` lease columns exist but are unused;
  two coordinators can dispatch the same task.

---

## 5. The smallest set of changes that would make a second loop safe — ranked

| # | change | fixes | cost | notes |
|---|---|---|---|---|
| 1 | **Do not run a second coordinator; keep single-coordinator + stateless fan-out workers.** | all of #264 | ~0 | The deployed model already does this safely. Cheapest by far; the evidence favours it. |
| 2 | **Land T3: a committed, append-only export of `task_event` (already hash-chained) consumed into each clone's local `task` view.** | §1 split-brain, cross-clone id collision, cross-clone task visibility | high (design+build) | Maps directly to the actual failure. The event log is the shared truth; the materialised view stays local. Reuses the journal's proven shape. |
| 3 | **Add a cursor-revision CAS to `advance_cursor` + per-receipt claim drain** (stop hardcoding one consumer). | journal double-drain / cursor rewind / duplicate dispatch | medium | The claim/lease layer already exists; wire the drain to it instead of a single named cursor. |
| 4 | **Wire `domain_files` (`flock`+atomic-replace+digest) into watch.py's write routes** (close #262). | torn questions/answers/chats across two servers | medium | The primitive exists and is unwired (`domain_files.py:22`). Fixes Shape B for domain files. |
| 5 | **Add a lock/atomic-replace to `status.json` writes** (or retire it per #294 T2). | status.json lost-update/torn-write | low | `status_sync.py` already retires `queue`/`current_task_ids` in store mode; finish the job or add tmp+rename. |
| 6 | **Implement the deferred `task_state` lease verbs** (grab/release/hold). | duplicate task dispatch across coordinators | medium | Schema columns already exist (`ledger_store.py:262`); needs the verbs + a shared surface (#2) to be meaningful across clones. |

#1 is recommended. If a genuine second coordinator is required, #2 is the
prerequisite (without it, #3–#6 protect one clone against itself, not against
a second coordinator).

---

## 6. What the filing assumed that is now MOOT

- *"Design the #294 SQLite migration."* — Moot. It landed (`ledger_store.py`,
  `ledger_write.py`, `ledger_parse.py`, the cutover watermark). #294 is code-
  complete within one target.
- *"tasks.md single-writer strategy."* — Moot as a concurrency answer.
  `tasks.md` is a notice; the single writer no longer writes entries. The
  strategy that replaced it (machine-local store) is the *source* of the new
  cross-clone hazard, not a fix for it.
- The filing's list of stores omits the **cutover watermark** as a concurrency
  unit. It is the most important one: it is a per-clone, one-way, never-removed
  flip (`ledger_parse.py:158`) that decides source-of-truth, and because it
  lives in a gitignored file, two clones can disagree on what the source of
  truth even *is*. Any multi-coordinator design must make the watermark (or
  its equivalent) shared, not machine-local.

---

--- SUMMARY ---

- **Verdict: no.** A second coordinator is unsafe today, not for lack of locks
  but because every load-bearing store (`ledger.sqlite3`, `user-events.sqlite3`,
  `status.json`, posture) is **machine-local per clone by design** (`.gitignore`
  C1 annotations); SQLite's WAL/CAS/`BEGIN IMMEDIATE` protect one file, not two
  clones' two files.
- **Strongest finding (§1):** the #294 cutover replaced tracked `tasks.md` with
  a gitignored, machine-local store and deferred cross-clone sharing to a "T3
  text export" that never landed. In any fresh clone `source_of_truth()` is
  `'markdown'` against a 5-line notice, so `dev/ledger.py counts` *errors* — a
  second coordinator's clone has **no readable task state at all**, and two
  clones seeding independently **collide on AUTOINCREMENT ids**.
- **What already works:** single-coordinator + 2–5 stateless `spawn_subagent`
  workers owning disjoint files (`Lane-owns:`, `git commit --only`). Its
  failures are second-order (containment #465, `--only` hunk sweeps), not state
  corruption. The filing's question is best answered by *keeping* this shape.
- **Per-store:** journal `receive()` idempotent + per-receipt claim/lease CAS
  are multi-consumer-safe, but the drain hardcodes one consumer
  (`CONSUMER="coordinator"`) and `advance_cursor` has no revision CAS (rewind
  risk); questions/answers/chats use only in-process `threading.Lock` (#262
  open); `status.json` has no lock/atomicity ("one writer, no reviewer").
- **Top recommendation:** do not promote a worker to a second coordinator
  until T3 (a committed append-only `task_event` export consumed into local
  views) lands — it is the only change that addresses the actual cross-clone
  failure mode; the rest (#3–#6) protect one clone against itself.
