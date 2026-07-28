# Durable user-event journal — red-first implementation plan

**Tasks:** #263 (the plan only) · consumers #260, #262, #269, #274 · adjacent #264, #294, #287, #289, #342, #346
**Status:** **lanes A–D and F authorised** 2026-07-28 05:43 (`8c5c9cf`) and **ALL LANDED** — **A** `aad1d8d` (2/2) · **B** `6a865e4`..`fec80be` (8/8) · **C** `3f1a6af`, `8c1bb60`, `b5555e4`, `f85be1c`, `2cc3537` (**5/5** as of 17:21) · **D** `6cd9f95` (4/4) · **F** `9263a42`..`4c918b2` (4/4). **So the second gate's condition — his 05:43 *"until A–D are proved"* — IS MET**, and lanes **E** (20–25) and **H** (34–35) await only his word; lane **G** (30–33) was never in `G1` and stays withheld regardless. Verified by a merge gate whose denominator is parsed from this document's own increment table and asserted to be five rows — because at 16:24 a coordinator claim that the condition was met was **wrong**, having read the ledger's *"lane C DONE … 3/3"* as the lane's scope when the lane's scope is 5. §"What this plan does not authorise" still binds everything it names.
**Do not read a landed prerequisite as an open gate.** On 2026-07-28 at 16:14 the coordinator dispatched a lane onto `#371` — which is increment **20**, `E1 envelope`, **lane E** — having read his *"Q2 yes"* at line 19 below as authorisation. It authorises the **design** change; the row itself says *"Increment 20 implements it — behind the second gate."* Killed at 16:20 with nothing committed; retracted at `6ea8f6b`. **An answered question and an opened gate are different facts**, and this document states both in the same table.
**Date:** 2026-07-28
**Input:** [`user-event-journal.md`](user-event-journal.md), approved `"rec"` via watch 2026-07-28 01:27 — contract only. Its §"Red-first acceptance fixtures" is this plan's acceptance set; nothing here invents a different one.
**Adjacent:** [`task-transition-boundary.md`](task-transition-boundary.md) (#264, ask open) built on that contract. Its conclusions are treated as context; §"Where this plan touches #264" says where the two meet and this plan contradicts none of them.

---

## His rulings, 2026-07-28 05:43 — answered `rec` to all four

The questions.md entry that asked these is now under `## Answered`. Recorded here
because this is the document an implementer reads.

| call | ruling | consequence for this plan |
|---|---|---|
| **G1 · scope of authority** | granted as recommended | increments **1–19** (lanes A–D) and **26–29** (lane F) may be built. Increments **20–25** (lane E) and **34–35** (lane H) may **not** — they need a second gate. Lane G (30–33) was not part of G1 and stays unauthorised. |
| **Q2 · amend law 2** | **yes** | landed in the design: `user-event-journal.md` §"Receive and idempotency" law 2 now requires a partial witness marked incomplete. §Amendments below is history. Increment 20 implements it — **behind the second gate.** |
| **Q3 · `200 → 202`** | **yes, a non-event** | the 15 assertions pinning the literal `200` move with the cutover. Lane E only. |
| **Q4 · purge and PostgreSQL** | **not built** | fixtures **18** and the PostgreSQL half of **19** stay `UNPLACEABLE` in the fixture map and no test is written for them. Increment 10 leaves the contract suite *ready* for a second backend and stops. **Not** built-and-skipped: a permanently-skipped test misrepresents coverage. |

**One consequence of G1 that is easy to miss:** lane D (16–19) is authorised but
cannot start cold — `D1` needs `B5` and `C3`. And the scheduling constraint is not
the dependency graph but the tree: lanes E and G both live inside the one
8,647-line `watch.py`, so they are a single lane in practice. That is an argument
for #368 (the modular split) landing before the second gate opens.

**A note for whoever implements a lane:** the brief is a file, not a prompt
(human-set, same answer). Lanes A and C were dispatched with
`.dreamwork/docs/briefs/263-lane-a-digest.md` and `263-lane-c-domain-files.md`,
which carry numbered binary acceptance criteria and point back at the per-increment
rows here rather than restating them. Follow that shape; do not copy the spec into
the brief, or the two will drift.

---

## The increment sequence

Thirty-five increments, each ~15–20 minutes, each ending committable and
verifiable, each named with what it makes true that was not true before.
Phase letters are lanes, not milestones: §"Dependency order and lanes" says
which run in parallel.

| # | increment | makes true |
|---|---|---|
| **A · digest** | | |
| 1 | `A1 framing` | a length-framed digest exists, and field boundaries cannot be shifted to collide |
| 2 | `A2 canonical` | method, media type and route canonicalise to one form, so case and parameter order cannot fork a digest |
| **B · journal** | | |
| 3 | `B1 database` | a journal database is created durably with WAL + `synchronous=FULL`, and its pragmas read back |
| 4 | `B2 receive` | a first receive inserts one receipt; same UUID+digest replays it; a different digest conflicts |
| 5 | `B3 chain` | every journal event carries a monotonic ordinal and a hash chained to its predecessor |
| 6 | `B4 states` | `received→validated` / `received→rejected` commit against the receipt revision, and a rejected receipt can never be claimed |
| 7 | `B5 claims` | a claim is exclusive, leased on backend time, and only one of two reclaimers wins |
| 8 | `B6 cursor` | a cursor advances only past a verified chain endpoint, and a broken chain forces a bounded full rebuild |
| 9 | `B7 twoproc` | two real OS processes on one database file cannot make two receipts for one UUID |
| 10 | `B8 contract` | the adapter contract suite is parameterised by backend, so a second backend adds no new test |
| **C · domain files** | | |
| 11 | `C1 lock` | a managed domain file cannot be read or written without an OS-visible cross-process lock |
| 12 | `C2 lineage` | every managed file embeds its own generation and a body digest that excludes only itself |
| 13 | `C3 onewrite` | effect, marker, generation and digest land in one atomic durable replace, or none of them do |
| 14 | `C4 markers` | a marker is found anywhere in a valid file, including after a fold moved it between sections |
| 15 | `C5 rebaseline` | an unjournaled valid successor fails closed, and `rebaseline` is the only way to adopt one |
| **D · application** | | |
| 16 | `D1 ternary` | proof is ternary, and a torn or drifted file yields `Unknown` rather than `NotApplied` |
| 17 | `D2 reserve` | `applying` reserves exactly one provisional successor before any mutation |
| 18 | `D3 reconcile` | reconciliation after a really-killed process produces exactly one effect per row of the proof table |
| 19 | `D4 adapters` | answer/ask/comment/command/tint each replay through their own adapter, and none can read another's format |
| **E · HTTP** | | |
| 20 | `E1 envelope` | transport-envelope failures are decided before the body is read, and none creates a receipt |
| 21 | `E2 shadow` | a receipt is committed on every write request while observable behaviour is unchanged |
| 22 | `E3 cutover` | the journal commit, not the handler, authorises the response: `202` + `Location` + receipt identity |
| 23 | `E4 besteffort` | a `submissions.log` failure is `shadow_failed` health on a durable receipt, not a refusal |
| 24 | `E5 reject` | malformed and schema-invalid bodies are `202` then durably `rejected`, with a bounded reason code |
| 25 | `E6 visible` | `shadow_failed` is visible on the dashboard, arriving and departing under `transitions.md` |
| **F · CLI** | | |
| 26 | `F1 list` | `ud-dw-user-events list` is a bounded projection with stable exit codes |
| 27 | `F2 show` | `show` is the only path to exact bytes, and it says what it truncated |
| 28 | `F3 replay` | `replay` is the only command that may cause a domain effect |
| 29 | `F4 health` | `health` names a recovery path for every failure semantic the design lists |
| **G · browser** | | |
| 30 | `G1 draft` | a draft survives a reload before it was ever submitted |
| 31 | `G2 attempt` | an attempt and its UUID are durable before the POST leaves the tab |
| 32 | `G3 conflict` | two tabs editing one input preserve a conflict snapshot rather than last-write-wins |
| 33 | `G4 migrate` | composer `localStorage` migrates once, under a marker |
| **H · version gate** | | |
| 34 | `H1 failclosed` | a mixed-version server refuses writes before accepting one |
| 35 | `H2 quiesce` | a request spanning a quiesced cutover completes under the drained generation or is retried under the new one |

`E3` is the cutover. Everything before it is additive; everything after it
assumes the journal is authority. `H2` is the only increment that writes an
irreversible watermark, and it is **not authorised to run against a live
target** — see §"Order that makes each step safe".

---

## What this plan does not authorise

His approval at 01:27 was one word, `"rec"`, on a request for *"a separate
red-first implementation plan"*. **This document is that plan and nothing
more.** It authorises no code. Specifically, and quoting the design's own
§Approval gate, the approval that produced this plan does **not** authorise:

- **implementation** — including increment 1. Every increment below needs
  authority this plan does not carry.
- **migration** — no live target's files or state are converted.
- **deployment** — nothing is installed into a running loop.
- **PostgreSQL operation** — increment 10 makes the suite backend-parameterised;
  it does not stand a PostgreSQL up or run against one.
- **topic chats** — no chat adapter, even though the design says one may later
  register.
- **payload purge** — no purge script, no purge run. Fixture 18 is therefore
  unplaceable; §"Fixture map" says so rather than quietly dropping it.

A plan gets read as a licence. It is not one. The next reader needs a fresh
gate, and §"What this plan does not resolve" states what that gate has to
decide.

---

## Seams that already exist, measured

Measured 2026-07-28 in the worktree at `wt/263-journal-plan`, at the same
commit as the main checkout's `master`. Every command is repeatable; **the
measurements, not memory, are what the increments are sized against.** Where a
measurement disagrees with an existing check, doubt the measurement — a ledger
scan lost to `lint.py` here last night because it assumed markers are never
line-wrapped.

### `JournalAdapter` — nothing exists

```
$ git grep -l 'sqlite3' -- '*.py' | wc -l
0
```

No tracked Python file mentions `sqlite3`. There is no database, no schema, no
adapter, no `user_events/` package (`ls -d user_events` → no such file). Every
one of increments 3–10 is greenfield, which has a consequence for the red rule
that §"Red-first, per increment" states rather than assumes.

### `log_submission()` — the one existing witness, and it is best-effort by construction

- `watch.py:8066` — `def log_submission(target, path, body, nbytes, truncated=False)`.
- `watch.py:8389` — the single call site, in `do_POST`, before dispatch.
- `watch.py:8128-8129` — `except OSError: pass`. This is #262's whole bug: the
  witness can fail silently and the request is still dispatched and acknowledged.
- `watch.py:8387` — `body = self.rfile.read(min(nbytes, MAX_BODY))`, and:

```
$ git grep -n 'len(body)\|len(self._body)' -- watch.py
(no output)
```

**There is no short-read check.** A client that closes mid-body today yields a
*short* `body`, which is written to `submissions.log` as if complete — the
declared `bytes` is right, the payload is truncated, and nothing says so. That
is a finding with an ordering consequence: increment 20 makes interrupted
bodies receipt-less, and if it ships without care it makes them *witness*-less
too. §"Order that makes each step safe" resolves it and §"Amendments this plan
proposes" names the design section it amends.

Test coverage of that function today:

```
$ git grep -ln 'log_submission' -- '*.py'
watch.py
```

**Zero direct unit tests.** It is exercised only through six HTTP-level
assertions (`git grep -n 'submissions' -- test_watch.py` → lines 199, 209,
2837, 2854, 3254, 3501) and the `submitlog` / `subslog` browser guards, plus
`lint.py:1308 check_submissions` reading the file's shape.

### `_handle_command` and the six write routes — no task state, no `202`

- `watch.py:8398-8411` — six POST routes: `/answer`, `/ask`, `/comment`,
  `/command`, `/tint`, `/run-mode`.
- `watch.py:8505` — `_handle_command` validates `kind`, validates non-empty
  `text` for everything but `do-next`, calls `log_event(...)`, returns `{"ok": true}`.
  **No task state is mutated at HTTP time**, which is #264's F3(a) and this
  measurement independently agrees with it.
- `watch.py:8231-8233` — `_send` hardcodes `self.send_response(200)`.

```
$ git grep -n '202' -- watch.py
watch.py:4, 2516, 3360, 4481, 7143     # all of them the year 2026-07-25
```

**No write route returns `202` today**, and there is no code path that can.
Increment 22 has to add a status-carrying send, not change an argument.

What pins `200`, and therefore what turns red at increment 22 — **fifteen
assertions**, counted with `ast` rather than by grep, because a hand-rolled scan
over this repo's files has produced a confident wrong number more than once
(`lessons.md:1413`) and it produced one here too on the first attempt:

```
$ python3 - <<'EOF'
import ast
ROUTES = ("/answer","/ask","/comment","/command","/tint","/run-mode")
src = open('test_watch.py').read(); tree = ast.parse(src)
for node in ast.walk(tree):
    if not isinstance(node, ast.Call): continue
    f = node.func
    if not (isinstance(f, ast.Attribute) and f.attr.startswith('assert')): continue
    if not any(isinstance(a, ast.Constant) and a.value == 200 for a in node.args): continue
    seg = ast.get_source_segment(src, node) or ''
    print(node.lineno, any(r in seg for r in ROUTES))
EOF
```

- 20 `assertX(…, 200)` calls in `test_watch.py`; **7** name a write route in the
  call itself (203, 206, 3338, 3342, 3562, 3572, 3609) and **4 more** assert a
  `status` local set by a `_post` to a write route (2833 `/ask`, 3177
  `/comment`, 3196 and 3203 `/command`) — those four the `ast` filter cannot see,
  and they were classified by reading the eight lines above each. **11 total.**
- **4** browser-guard assertions: `dev/capture/submitlog.mjs:165`,
  `dev/capture/subslog.mjs:100`, `dev/capture/answers.mjs:151`,
  `dev/capture/runmode.mjs:219` (`grep -rn 'status === 200' dev/capture/*.mjs`).
- and **nothing in the browser client**:

```
$ git grep -n -E 'r\.ok|res\.ok|response\.ok' -- watch.py
watch.py:2010, 2640, 3015, 3059, 3450, 3691, 3891, 5309, 5798
```

Every client-side check is `res.ok`, which is true for `202`. So the cutover's
user-visible blast radius is **zero** and its test blast radius is fifteen
assertions. That asymmetry is the argument for doing it as one increment rather
than a flag.

### `DomainFileStore` — the durable half exists, the lock and lineage halves do not

- `watch.py:7423` — `atomic_write_text(path, text)`: temp in the same
  directory, `fsync` the file, `os.replace`, best-effort parent-directory
  `fsync`. **This is law 3's durable-replace clause, already written.**
- The lock clause has nothing:

```
$ git grep -c -E 'import fcntl|fcntl\.flock|O_EXCL' -- watch.py
(exit 1 — zero hits)
```

- `watch.py:8026` — `ANSWER_LOCK = threading.Lock()`, used at `8430`, `8453`,
  `8486`. **In-process only.** Two `watch.py` processes on one target serialise
  against nothing, which is the second half of #262.
- And the writes are not even atomic:

```
$ git grep -n 'open(qpath, "w"' -- watch.py
watch.py:8462     # _handle_answer
watch.py:8496     # _handle_comment
```

`/answer` and `/comment` **truncate `questions.md` in place** — no temp, no
rename, no `fsync` — while `/ask` (`watch.py:8433`) uses `atomic_write_text`.
A crash between truncate and write loses the whole file, on the two paths that
carry his answers. This is pre-existing, it is not #263's to fix inside a plan,
and it is the strongest single argument for scheduling lane C early. **Reported,
not fixed** — it wants its own task.

- Lineage metadata is absent everywhere:

```
$ git grep -c -E 'domain_generation|body_digest' -- '*.py' '*.md'
.dreamwork/docs/plans/user-event-journal.md:2
```

Only the design mentions them. Increment 12 introduces both to real files, and
that is a `file-formats.md` change in the same commit by repo convention.

### Harness that already works, and should be reused

`test_watch.py:150-211` (`TestRequestAuthorityHTTP`) reserves a real port on a
probe server, closes it, binds `watch.make_handler` to that exact port, POSTs
with `urllib`, and asserts on real `submissions.log` rows. **That is the
end-to-end shape increments 20–25 need**, including its port discipline. It
already asserts `200` on `/command` at lines 203 and 206, so two of the fifteen
that increment 22 must move are in it.

The gitignore has no journal entry (`git grep -n 'sqlite\|user-events' --
.gitignore` → nothing), so increment 3 adds one, and by convention that is a
`Migration:` trailer.

### Health surface, for fixture 5

There is a per-channel health idiom already: `questions_health` in `/data.json`,
rendered as `.qhealth` (`watch.py:781-794`, `2051-2087`, `2242-2283`), keyed on
health rather than on a count, with an `unreadable` variant on `--warn`.
Increment 25 extends that idiom rather than inventing a second one — and being
UI, it is bound by `transitions.md` and the exceptional-quality bar, which is
why it is its own increment and not a line inside increment 23.

---

## Red-first, per increment

Every increment below names its test, what it asserts, and **the production
line whose absence makes it fail**. Where no such line can be named, the entry
says so instead of listing a decorative test.

Two rules apply to all thirty-five and are not repeated in each row:

1. **A greenfield module makes an `ImportError` red available, and an
   `ImportError` red is not verification.** It proves the test runs; it does not
   discriminate. So for every increment in a new file the red is a *second*
   act: after the module exists and the test is green, delete the named line,
   run, watch that test fail and its neighbours stay green, restore from a
   snapshot you took (`cp f $S/bak`; never `git checkout -- f`).
2. **Assert the precondition, derived at runtime.** If a test's meaning needs
   two fixture values to differ, compute both and assert the gap. No literal
   tuned to today's fixture.

### Lane A — digest

**1 · `A1 framing`.** New `user_events/digest.py`: `length_framed(*parts) -> bytes`
and `request_digest(...) -> str`.
*Test:* `test_framing_boundary_cannot_be_shifted` — for the two field splits
`("ab","c")` and `("a","bc")`, assert the digests differ, and assert the
precondition that the naive concatenations are equal (derive both at runtime;
if they are not equal the test proves nothing and must fail loudly on that).
*Red line:* the length prefix write inside `length_framed` — delete the prefix
and the two digests collapse.
*Must not fake:* the test may not build the framed bytes itself. It calls
`length_framed`. A fixture that assembles the framing is asserting a property
of the fixture — the #320 trap, `lessons.md`.

**2 · `A2 canonical`.** `canonical_media_type()`, `canonical_route()`,
`canonical_method()`.
*Test:* `test_case_and_parameter_order_do_not_fork_a_digest` — `POST` vs `post`,
`Application/JSON; Charset=UTF-8` vs `application/json;charset=utf-8`, and a
reordered two-parameter media type all give one digest; a *different* media type
gives a different one (the discriminating half — without it, `return ""` passes).
*Red line:* the `.lower()` on the media-type subtype, and the parameter `sorted()`.
Each deleted separately; each must fail this test alone.
*Must not fake:* no direct `hashlib` in the test.

### Lane B — journal

**3 · `B1 database`.** `user_events/sqlite.py: open_journal(path)` — create
parent durably, `journal_mode=WAL`, `synchronous=FULL`, bounded `busy_timeout`,
schema + `schema_version` row.
*Test:* `test_pragmas_are_what_the_durability_boundary_claims` — reopen the file
in a *fresh* connection and read `PRAGMA journal_mode`, `PRAGMA synchronous`,
`PRAGMA busy_timeout` back.
*Red line:* the `PRAGMA synchronous=FULL` execute. **This row was WRONG and lane B
found it by obeying it** (amended 2026-07-28, `6a865e4`): it assumed deleting the
pragma leaves `synchronous` at `1`, but **SQLite 3.53's compile-time default is
already FULL (2)**, so the deletion changed nothing and the prescribed red came
back **green**. Per this repo's rule that a green red-run is a finding and never a
relief, the lane did not conclude the code was fine — it made the pragma
load-bearing by pinning `NORMAL` and then `FULL`, so deleting the `FULL` execute
now genuinely leaves `1`. Coordinator re-verified independently: the injection
yields `AssertionError: expected synchronous=FULL (2), got 1` with 7 neighbours
green. **The general trap, worth carrying to any other pragma or default in this
plan: a red that depends on a value differing from the platform default is only as
discriminating as that default, which the plan cannot see.**
*Must not fake:* read the pragmas from a *second* connection, not the one that
set them; `synchronous` is per-connection and asserting on the setter's own
handle can pass with the pragma applied to the wrong scope.

**4 · `B2 receive`.** `receive(envelope) -> ReceiveResult` implementing the
three-row table: absent → insert; present+equal → replay; present+different →
conflict.
*Test:* `test_same_uuid_same_digest_replays_and_does_not_insert` and
`test_same_uuid_different_bytes_conflicts_and_preserves_the_original` — the
second asserts the stored `exact_payload_bytes` are byte-identical to the first
call's, and counts rows.
*Red line:* the `SELECT request_digest … WHERE client_action_id = ?` comparison
before insert. Delete it and the unique constraint turns a replay into an
`IntegrityError` rather than a replay — a *different* failure, so also assert
the result *kind*, not just the row count.
*Must not fake:* no raw `INSERT` in the test to set up state. Both calls go
through `receive()`, or the test is hand-building the state whose construction
is the thing under test.

**5 · `B3 chain`.** `event_ordinal` + `H_i = SHA-256(domain_tag || H_(i-1) ||
length_framed(canonical_event_i))`, appended in the same transaction as the
event, plus `verify_chain(through_ordinal)`.
*Test:* three properties, no recomputation —
(a) the same event sequence built twice yields the same head hash;
(b) one byte changed in one event's payload changes the head;
(c) `UPDATE`ing a low-ordinal row directly, leaving the high-water ordinal
untouched, makes `verify_chain` return failure naming that ordinal.
*Red line:* the `prev_hash` term in the hash input. Delete it and (c) still
passes on the row's own hash but the *chain* stops linking — so (c) must assert
the verifier names the ordinal, and (b) must be run with the mutation on an
*earlier* event than the head.
*Must not fake:* the test must not hold its own copy of the `H_i` formula. A
check and the thing it checks cannot hold separate copies of one rule
(`lessons.md:874`) — assert relations between outputs, never an expected digest.

**6 · `B4 states`.** Transition append with `expected_revision`; the
`received→validated|rejected` edges; `claim()` refuses a rejected receipt.
*Test:* `test_rejected_receipt_can_never_be_claimed` plus
`test_stale_revision_transition_is_refused`.
*Red line:* the `AND state = 'validated'` predicate in the claim `UPDATE`.
*Must not fake:* revisions must be read back from the store between calls, not
tracked in the test.

**7 · `B5 claims`.** `claim/renew/finish` with unguessable token, monotonic
revision, and lease deadlines from **backend** time.
*Test:* `test_expired_lease_is_reclaimable_and_the_stale_claimant_cannot_finish`
— two claims either side of a **real** short lease, then the first claimant's
`finish()` fails.
*Red line:* the `lease_until > <backend now>` predicate in the claim `UPDATE`.
*Must not fake:* **do not patch the clock.** The design's law is "backend/server
time, never client clocks"; a monkeypatched `time.time` proves the opposite of
what the test is named for. Use a 1-second real lease and a real sleep, and
assert at runtime that the observed elapsed time exceeded the lease.

**8 · `B6 cursor`.** `cursor()/advance_cursor()` with
`chain_hash_at_ordinal`, and bounded full rebuild from ordinal 1 on mismatch.
*Test:* `test_broken_chain_forces_rebuild_not_a_silent_advance` — corrupt below
high water, then assert `advance_cursor` refuses and the rebuild path runs
(count the ordinals it read, asserted against a runtime-derived total, never a
literal).
*Red line:* the `expected == stored_chain_hash` comparison in `advance_cursor`.

**9 · `B7 twoproc`.** Nothing new in production if 4–8 are right; this
increment is the test plus whatever the test finds.
*Test:* `test_two_processes_one_uuid_make_one_receipt` — two
`multiprocessing` children (separate interpreters), a barrier, both call
`receive()` with the same UUID and bytes; assert exactly one insert and two
`202`-shaped results with one receipt id.
*Red line:* ~~the `UNIQUE(client_action_id)` constraint in the schema.~~
**WRONG, and lane B2 found it by obeying it** (amended 2026-07-28, `5f729dc`):
removing `UNIQUE` leaves the whole suite **green**, because `BEGIN IMMEDIATE` plus
`B2`'s SELECT-before-insert already serialise the writers — the second process
*replays* and never reaches the constraint. Verified twice: by the lane, and
independently by the coordinator (12 passed with `UNIQUE` deleted). The lane also
probed the mechanism rather than guessing at it: `DEFERRED` + no `UNIQUE` gives
`database is locked` under `busy_timeout`, so the concurrency is real and `UNIQUE`
simply is not the line that carries it. **The load-bearing lines today are
`BEGIN IMMEDIATE` and the SELECT-before-insert**; `UNIQUE` is defence-in-depth and
is retained as such. To make this increment's red discriminating, either name those
two as co-reds, or switch `receive()` to insert-first so `UNIQUE` becomes the
concurrent backstop it was assumed to be.
**This is the second red line in this plan that named a mechanism which was not the
load-bearing one** (see `B1`). The general trap: **where two mechanisms each prevent
the bug, deleting one proves nothing — defence-in-depth and a discriminating red are
in direct tension**, and a plan written before the code cannot see which layer will
end up carrying the property.
*Must not fake:* **threads are not processes.** The existing code's only mutual
exclusion is a `threading.Lock` (`watch.py:8026`), and a threaded version of
this test passes with no database constraint at all — which is precisely #262's
bug reproduced as a green test.

**10 · `B8 contract`.** Parameterise 4–9 over a `backend` fixture so a second
adapter inherits them.
*Test:* the suite itself, plus `test_every_contract_test_runs_under_every_registered_backend`
— derive the counts from the registry and the collected node ids at runtime.
*Red line:* the registry entry. Removing a backend must drop the parameterised
count, and the meta-test asserts the product, not a literal.
*Must not fake:* the meta-test must not hold a hand-copied list of the contract
tests — that drifts (`lessons.md:991`).

### Lane C — domain files

**11 · `C1 lock`.** `user_events/domain_files.py`: `fcntl.flock` on a sidecar
lock path, taken **before** read, released after the durable rename.
*Test:* `test_a_second_process_cannot_read_while_the_lock_is_held` — a child
holds the lock, the parent's acquisition times out.
*Red line:* the `fcntl.flock(fd, LOCK_EX)` call.
*Must not fake:* do not patch `fcntl` and assert it was called. That asserts the
mock. Two real processes, or the test proves nothing about OS visibility.

**12 · `C2 lineage`.** Embedded `domain_generation`, `body_digest`, and
last-application identity; the digest covers the canonical body **excluding only
its own field**.
*Test:* `test_body_digest_excludes_only_itself` — write, then rewrite the digest
field alone to a wrong value: validation fails. Then change one byte of body:
validation fails. Then re-emit the same body with the digest recomputed: the
digest is *unchanged*, which is the exclusion property.
*Red line:* the field-exclusion filter in the canonical-body builder. Delete it
and the digest becomes self-referential and the third assertion fails.

**13 · `C3 onewrite`.** Effect + marker + generation + digest in one
`atomic_write_text`-shaped replace, with the lock held across read→write.
*Test:* `test_kill_at_rename_leaves_the_previous_generation_intact` — a child
process `os._exit`s at a named seam between `fsync` and `os.replace`; the parent
asserts the file is byte-identical to its pre-state and the temp file is gone or
ignorable.
*Red line:* the `os.replace(tmp, path)` ordering — specifically, replacing the
temp-then-rename with a direct `open(path, "w")` (which is what
`watch.py:8462` does today) must make this test fail.
*Must not fake:* an end-state-only assertion cannot fail on a crash-window bug.
Kill the child, and snapshot the pre-state bytes *before* the run so the
comparison is against a captured value.

**14 · `C4 markers`.** Whole-file marker search across both literal `Open` and
`Answered` sections.
*Test:* `test_a_fold_between_sections_cannot_hide_a_marker` — build a fixture
whose marker sits in `Answered`, assert found; move it to `Open`, assert found;
assert at runtime that the two fixtures actually differ in which section holds
it (the precondition — a fixture that puts it in both is vacuous).
*Red line:* the second section in the scan's section list.

**15 · `C5 rebaseline`.** External-drift detection + an explicit operator
`rebaseline` that validates, preserves bytes, mints a successor generation, and
journals the import.
*Test:* `test_unjournaled_valid_successor_fails_closed_until_rebaselined` — write
a syntactically valid file with a generation outside committed lineage; assert
`Unknown`/refusal; run `rebaseline`; assert application proceeds and the journal
holds the import event.
*Red line:* **corrected 2026-07-28 17:21, by the lane that built it.** This row named
the `generation in committed_lineage or generation == reserved_successor`
predicate — but that predicate lives in `apply._is_valid_known_file` and is
**`D1`'s** red, already proven there. `C5`'s own red is `rebaseline`'s
lineage-adoption line, `new_lineage = set(committed_lineage) | {successor}`:
dropping the successor from the returned lineage fails
`test_unjournaled_valid_successor_fails_closed_until_rebaselined` on its
lineage-equality assertion. Same class of stale row as `B1`/`B7`.
*And the geometry is narrower than it looks, disclosed by the lane rather than
glossed:* the file after `rebaseline` always sits at `S = max(committed)+1`, so a
caller computing `reserved_successor = S` would see `APPLIED` through the
**successor half alone** and the lineage red would be hollow. The test passes
`max(new_lineage)+1` precisely so the lineage half is what grants `APPLIED`.

### Lane D — application

**16 · `D1 ternary`.** `Proof` enum + `prove_applied()` for one adapter.
*Test:* `test_torn_and_drifted_files_prove_unknown_not_notapplied` — three
fixtures (truncated mid-record, valid-but-drifted generation, valid-and-in-lineage
without marker) map to `UNKNOWN`, `UNKNOWN`, `NOT_APPLIED`.
*Red line:* the `UNKNOWN` branch for a failed digest validation. Delete it and
the first two collapse into `NOT_APPLIED` — and the third case is what makes
that a discriminating red rather than a suite that moves together.
*Must not fake:* the valid fixtures must be produced **by `DomainFileStore`**,
not written by the test. A hand-written file has a digest and lineage the test
invented, and then the proof is reading the test's arithmetic (`lessons.md:1462`).

**17 · `D2 reserve`.** CAS to `applying` before mutation, recording expected
before-generation/fingerprint and `after_generation = before + 1` plus receipt,
adapter and application reference.
*Test:* `test_a_forged_next_generation_with_any_predicate_mismatch_proves_unknown`
— four sub-cases, each mismatching exactly one of {generation, body digest,
receipt id, adapter/application reference}, all `UNKNOWN`; and the all-match
case `APPLIED`.
*Red line:* each predicate in the reserved-successor comparison, deleted one at a
time; each deletion must flip exactly its own sub-case. Four separate reds, and
this is where a suite that moves together shows itself.

**18 · `D3 reconcile`.** The executor: lease, proof, the post-crash table's five
rows.
*Test:* `test_each_row_of_the_proof_table_produces_exactly_one_effect` — a real
child killed at each of two named seams (after `applying`, after domain
`fsync`), then reconciliation, then assert the effect appears exactly once by
counting marker occurrences in the file.
*Red line:* the `if proof is APPLIED: finish only` branch. Delete it and the
after-`fsync` case applies a second time and the count is 2.
*Must not fake:* do not simulate the crash by calling `finish()` out of order.
`os._exit` a child, or the test is asserting the shape of its own simulation.

**19 · `D4 adapters`.** Five adapters, registered, each seeing only its own
format.
*Test:* `test_each_endpoint_replays_through_its_own_adapter` plus
`test_an_adapter_refuses_another_adapters_payload`.
*Red line:* the registry dispatch key. Deleting the `/comment` entry must fail
exactly the comment case.
*Must not fake:* five real receipts through five real adapters onto five real
files; not one adapter parameterised five ways over the same file.

### Lane E — HTTP

**20 · `E1 envelope`.** Decide authority, method, path, media type,
`Content-Length` well-formedness **before** the body read; enforce a complete
bounded read; interrupted and over-limit bodies get no receipt (see
§"Amendments this plan proposes" for what they *do* get).
*Test:* `test_an_interrupted_body_creates_no_receipt` — a raw `socket` that
sends `Content-Length: 500` and then 100 bytes and closes.
*Red line:* the `len(body) != nbytes` check — which does **not exist today**
(measured above), so this increment's red is available immediately and against
real production behaviour, not against a placeholder.
**WRONG, and lane E found it by obeying it** (amended 2026-07-29, lane E batch 1):
the `#371` incomplete-witness work landed **after** that measurement, so
`short = len(body) < want` already exists at `do_POST` and is documented in
`file-formats.md` lines 1084–1096. The prescribed red came back **green** against
it — deleting the computation makes the *witness-honesty* test fail (the log no
longer marks the partial `short`) but does not by itself stop a receipt, because
the check and the gate that uses it are two lines. This is the **fourth** wrong
red line in this plan (after `B1`'s pragma, `B7`'s `UNIQUE`, row 15's predicate).
The real load-bearing line is the gate that *uses* `short` to skip receipt:
`if short: self.send_error(400); return` in `do_POST`. Deleting that gate alone
fails `test_an_interrupted_body_creates_no_receipt` (`1 != 0`, a receipt
appears), verified by the lane. The plan measurement (`watch.py:8387`) and the
"does not exist today" claim were both true at measurement time and are stale
now; `file-formats.md` already documents the `short`+`got` marker, so no
`file-formats.md` change is needed for E1.
*Must not fake:* `urllib` cannot express this. It always sends a complete body.
A test that uses `urllib` and a short `Content-Length` header is testing the
library, and it will pass with the check absent.

**21 · `E2 shadow`.** Commit a receipt on every write request. Response,
status code, `submissions.log` and every handler are unchanged; a journal
failure here is logged and swallowed.
*Test:* `test_every_write_route_commits_a_receipt_and_changes_nothing_else` —
POST all six routes, assert six receipts *and* assert the responses and
`submissions.log` are identical to a baseline captured with the journal disabled.
*Red line:* the `journal.receive(...)` call in `do_POST`.
*Must not fake:* derive the route list from `watch.py`'s dispatch rather than
listing six paths, so a seventh route added later fails this test instead of
slipping past it. The absence of exactly that discipline is why
`log_submission` has one call site and a comment explaining why.

**22 · `E3 cutover`.** The journal commit authorises the response. `202`,
`Location: /user-events/<id>`, receipt id/sequence/digest in the body; a
same-UUID retry returns the same identity; a journal open/commit failure returns
no `202`.
*Test:* three —
(a) `test_202_names_a_receipt_that_exists` (parse the body, `get()` that id from
the journal; a hardcoded `202` fails);
(b) `test_retry_of_the_same_uuid_returns_one_receipt_and_the_same_location`;
(c) `test_no_202_when_the_journal_cannot_commit` — journal path in a directory
`chmod 0500` before start, so the open genuinely fails.
*Red line:* the `send_response(202)` in the new status-carrying send, and
separately the `if not result.committed: 503` guard.
*Must not fake:* (c) must not patch `sqlite3.connect`. Real permissions, real
failure. And see §"Fixture map" for the honest limit: this covers *commit*
failure; an `fsync`-specific failure needs a fault-injection layer and is a
recorded gap, not a claimed pass.

**23 · `E4 besteffort`.** `submissions.log` failure records `shadow_failed`
health against the receipt and does not change the response.
*Test:* `test_a_shadow_write_failure_still_returns_202_and_records_health` —
make `submissions.log` a **directory** so the append raises a real `OSError`.
*Red line:* the `record_health("shadow_failed", ...)` call, and separately the
absence of a re-raise.
*Must not fake:* do not patch `open`. Patching `open` also breaks the journal
write, so the test would pass for the wrong reason and would keep passing if the
ordering inverted — a green that means nothing.

**24 · `E5 reject`.** Post-receipt validation: malformed JSON and
schema/domain-invalid JSON become `received → rejected` with a bounded reason
code, not a synchronous `400`. Unknown paths stay pre-receipt `404/405`.
*Test:* `test_malformed_json_is_202_then_durably_rejected` and
`test_an_unknown_post_path_is_404_and_creates_no_receipt` — the pair is the
point; either alone is passable by a wrong implementation.
*Red line:* the `self.send_error(400)` removal in `_read_json` (`watch.py:8354`)
— reinstating it must fail the first test and leave the second green.

**25 · `E6 visible`.** `shadow_failed` on the dashboard, reusing the
`questions_health` / `.qhealth` idiom.
*Test:* a browser guard, and per `transitions.md` **it must sample mid-flight**:
an end-state assertion cannot fail on a motion bug, and neither can "did it
move". Read the idiom before authoring a second one; load the design skills and
`watch-design.md` before touching pixels.
*Red line:* the health key in the `/data.json` payload builder, and separately
the CSS transition declaration whose deletion must fail the motion sample.
*Must not fake:* do not assert "the element exists". Assert the health *state*
drives the variant, with a runtime-derived precondition that the unhealthy and
healthy fixtures actually differ.

### Lane F — CLI

**26 · `F1 list`.** `ud-dw-user-events list --status --after --limit`, bounded
JSONL/table with the design's field set, stable exit codes.
*Test:* `test_list_is_bounded_and_never_exceeds_limit` + `test_exit_codes_are_stable`.
*Red line:* the `LIMIT ?` bind. A test that only checks field presence passes
with it deleted, so assert the row count against a fixture whose size is derived
at runtime and asserted to exceed the limit.

**27 · `F2 show`.** `show <receipt> --max-bytes` — the only exact-bytes path;
truncation reports original length and digest.
*Test:* `test_truncation_reports_the_original_length_and_digest` — with a
payload whose length is asserted at runtime to exceed `--max-bytes`.
*Red line:* the truncation-metadata emit.

**28 · `F3 replay`.** The only command that may cause a domain effect.
*Test:* `test_no_command_but_replay_touches_a_domain_file` — snapshot every
managed file's bytes, run `list`/`show`/`health`, assert byte-identical; run
`replay`, assert changed. Derive the file set by walking the managed directory,
**not** from a list in the test — a directory that grows is how a check goes
hollow after its red run.
*Red line:* the read-only guard in the command dispatcher.

**29 · `F4 health`.** Every failure semantic in the design's §Failure semantics
has a named recovery path.
*Test:* `test_every_failure_semantic_has_a_health_row` — parse the design
document's list and assert coverage. Fragile by nature, so assert the parse
found a plausible count derived from the document, and fail if it found zero.
*Red line:* the health-row table entries.
*Must not fake:* if the parse silently finds nothing the test is vacuous — this
is the `lessons.md:1447` shape, a silent third verdict read as reassurance.

### Lane G — browser

**30 · `G1 draft`.** Project-partitioned IndexedDB `DraftStore`, autosave
before submit.
*Test:* browser guard: type, reload, assert restored; and assert the store is
partitioned by project (two targets do not see each other's drafts).
*Red line:* the autosave call on input.

**31 · `G2 attempt`.** `AttemptStore`; UUID and exact request bytes persisted
**before** the POST; retries reuse them.
*Test:* guard that blocks the network, submits, asserts the attempt is durable
with `state: unreachable`, then unblocks and asserts the retry carries the same
UUID and identical bytes.
*Red line:* the `await put(attempt)` placed before `fetch`. Moving it after must
fail this test — which is the only assertion that distinguishes the feature from
a cosmetic one.

**32 · `G3 conflict`.** Revision CAS + short owner-tab lease; divergent edits
preserve a conflict snapshot.
*Test:* two real browser contexts on one origin, divergent edits, assert the
snapshot exists and neither text was silently lost; and assert a newer draft
survives an older receipt.
*Red line:* the revision comparison in the CAS. Cross-tab countdowns and leases
are distributed systems (`lessons.md:917`) — "the tab that armed it" is not a
sound owner and the test must not assume it.

**33 · `G4 migrate`.** One-time composer `localStorage` migration under a marker.
*Test:* run migration twice, assert the second is a no-op and the marker is why.
*Red line:* the marker write.

### Lane H — version gate (code only)

**34 · `H1 failclosed`.** A server whose target protocol version does not match
refuses writes **before** accepting one.
*Test:* `test_a_mixed_version_server_refuses_before_witnessing` — assert no
receipt and no `submissions.log` line, exactly as
`test_origin_gates_post_before_body_witness` (`test_watch.py:193`) does for
`Origin`. Reuse that harness.
*Red line:* the version check's position relative to the body read.

**35 · `H2 quiesce`.** Cutover lease, drain, watermark; a request spanning the
cutover completes under the drained generation or is retried under the new one.
*Test:* two server instances over one temp target, a request held at a named
seam across the cutover; assert exactly one receipt and no legacy direct write.
*Red line:* the drain wait. Deleting it must produce either two receipts or a
legacy write.
*Must not fake:* this runs against **temp targets only**. Nothing in this
increment may be executed against a live target — that is migration, and
migration is not authorised.

---

## Fixture map

The design's twenty acceptance fixtures against the increment that first makes
each pass. Two cannot be placed; both are named with which of the two reasons
applies, per the brief.

| fixture | first passes at | note |
|---|---|---|
| 1 · authority / unknown route / bad framing / interrupted / over-limit ⇒ no receipt | **20** | over-limit already 413s; interrupted is new (M22) |
| 2 · malformed + schema-invalid ⇒ `202`, status URL, durable `rejected`, retry preserves identity | **24** (needs 22) | |
| 3 · journal fsync failure ⇒ no `202` | **22, partially** | **FINDING** — see below |
| 4 · crash after commit before response ⇒ retry returns one receipt | **22** | real `os._exit` child |
| 5 · shadow `OSError` ⇒ `202`, durable receipt, visible health | **23** durable + **25** visible | split deliberately: the visible half is UI |
| 6 · concurrent same UUID/digest across two servers ⇒ one receipt | **9** | processes, not threads |
| 7 · same UUID/different bytes ⇒ `409`; new UUID/same bytes ⇒ distinct | **4** | |
| 8 · framing and method/media case/parameters cannot create ambiguity | **1** and **2** | |
| 9 · crash after `applying` before domain write ⇒ NotApplied, one effect | **18** | |
| 10 · crash after domain fsync before finish ⇒ reserved successor Applied; forged mismatch Unknown | **17** predicate, **18** end-to-end | |
| 11 · torn domain / false negative ⇒ Unknown, no second effect | **16** | |
| 12 · dual reclaimer and stale claimant ⇒ one CAS winner | **7** | |
| 13 · two processes answer/comment/fold, stale-preimage retry, crash at rename | **13** + **14** | |
| 14 · external editor removes marker ⇒ Unknown/recovering; rebaseline journals a successor | **15** | |
| 15 · mutate a low-ordinal transition with unchanged high water ⇒ chain fails, rebuild | **5** detect, **8** rebuild | |
| 16 · answer/ask/comment/command/tint each replay through their own adapter | **19** | |
| 17 · cross-tab draft conflict; newer draft survives older receipt | **32** | |
| 18 · active-store purge verifies DB/WAL erasure + tombstone + residual report | **UNPLACEABLE** | **excluded by the approval clause**, not a design gap and not untestable |
| 19 · real SQLite **and PostgreSQL** multi-client contract suites | **9/10** for SQLite; PostgreSQL half **UNPLACEABLE** | **excluded by the approval clause** ("no PostgreSQL operation"). Increment 10 makes the suite ready for it and stops there |
| 20 · two server versions + a request spanning quiesced cutover | **34** + **35** | code and temp targets only; running it against a live target is migration |

### Finding: fixture 3 is not fully testable as written

The fixture says *"journal fsync failure ⇒ no `202`"*. Increment 22 tests the
**contract** — any journal open-or-commit failure yields no `202` — at a real
seam (a `chmod 0500` parent directory), with no mocking. That is honest and it
is the property the design's §Failure semantics actually states.

An **`fsync`-specific** failure is a different thing, and stdlib SQLite gives no
way to induce it: there is no pluggable VFS, `PRAGMA`s cannot be made to fail,
and a patched `os.fsync` does not reach SQLite's own syscall. The faithful
options are a fault-injecting filesystem or an `LD_PRELOAD` shim that fails
`fsync` for one path — real syscall path, production code untouched, but a tool
this repo does not have.

**Recommendation:** place the contract-level test at increment 22, and record
the `fsync`-specific case as a deferred gap with the shim named, rather than
writing a mocked test that would report a durability guarantee it never
exercised. The design itself says *"crash fixtures kill at named seams rather
than mocking away durability"* — a mocked `fsync` is exactly the thing that
sentence forbids, so leaving the gap visible is the design-conformant answer.

---

## Dependency order and lanes

```
A1 ─ A2 ─────────────┐
B1 ─ B2 ─ B3 ─ B4 ─ B5 ─ B6 ─ B7 ─ B8      (B2 needs A2)
C1 ─ C2 ─ C3 ─ C4 ─ C5
                     └─ D1 ─ D2 ─ D3 ─ D4   (D1 needs B5 + C3)
E1 ──────────────────── E2 ─ E3 ─ E4 ─ E5 ─ E6   (E2 needs B2 + E1; E3 needs B4)
                                  F1 ─ F2 ─ F3 ─ F4   (F1 needs B2; F3 needs D4)
G1 ─ G2 ─ G3 ─ G4    (G2 needs A2)
                                            H1 ─ H2   (needs E3)
```

**Parallel from a cold start, on disjoint files:** `A1`, `B1`, `C1`, `E1`, `G1`
— five lanes, five different files (`user_events/digest.py`,
`user_events/sqlite.py`, `user_events/domain_files.py`, `watch.py`'s `do_POST`,
`watch.py`'s `PAGE` JS).

**And one hard serialisation, which is the practical constraint:** `watch.py` is
one 8,647-line file, and lanes E and G both live in it, as does every other
dreamer working on the dashboard. So **E and G share a single lane in
practice** even though they are logically independent, and the dispatcher must
treat "who holds `watch.py`" as the scheduling resource. Lanes A, B, C, D and F
touch new files only and can run concurrently with each other and with whoever
holds `watch.py`.

`test_watch.py` is a second contended file: increments 20–25 and 34 all add to
it. Prefer a new `test_user_events_http.py` for lane E, so lane E's tests do not
contend with the dashboard dreamers' tests — a plan decision, cheap, and it
removes the only remaining collision.

---

## Order that makes each step safe

The journal sits on the durability path of the human's own words. The invariant
that must hold **at every commit, including the intermediate ones**:

> **His words never have fewer durable homes than they had at the previous
> commit.**

That invariant, not the increment order, is what makes the sequence safe. Three
places where it is at risk:

**1 · Increment 20 reduces what is on disk unless it is careful.** Measured
above: an interrupted body today produces a short read that is written to
`submissions.log` as though complete. Increment 20 correctly stops calling that
a receipt — but if it also stops witnessing it, a partial answer that today
leaves *something* recoverable leaves *nothing*. So increment 20 must keep
writing the partial bytes as a witness marked `incomplete: true`, and that is a
`file-formats.md` change in the same commit. §"Amendments this plan proposes"
names the design section this amends. **Do not schedule 20 before that
amendment is ruled on.**

**2 · Two different things are called "shadow", in opposite directions.** Name
them, because confusing them is how a cutover goes wrong:

- **journal-shadow phase** — increments 21 → 22. The *journal* is the shadow.
  It is written, its failures are swallowed, and `submissions.log` plus the
  existing handlers remain authority. Rolling back is a revert.
- **log-shadow phase** — after increment 22. The *journal* is authority and
  `submissions.log` is the best-effort shadow (design decision 3). Its failure
  is health, not a refusal (increment 23).

**Before increment 22 (the cutover), all of these must be true:**

- increments 3–9 green, **including the two-process test at 9** — a single-process
  green there is the exact shape of #262's bug;
- increment 21 has been running on a real target for at least one dreamwork
  session with the journal receipt count matching the `submissions.log` line
  count over that window (assert the two counts, derived at runtime, and
  investigate any gap before proceeding — a gap is the finding, not the noise);
- the fifteen `200` assertions are updated in the same commit, not before it,
  so the suite is red between the two halves and cannot be committed half-done;
- `lint.py` clean, run as its **own command**. Never a lint run and a `git
  commit` in one shell command — that has committed through a lint ERROR twice
  in this repo, because the error scrolled past above the commit's output.

**3 · `submissions.log` must not become load-bearing on the way.** Decision 3
makes it best-effort; the risk is that increments 21–25 quietly start *reading*
it. Assertable guard, and it costs one line: `git grep -n 'submissions' --
user_events/ ud-dw-user-events` must be empty, checked in the CLI's own test as
a precondition. If the journal ever needs the log to answer a question, the
journal is incomplete.

A related consequence to handle at increment 22 rather than discover later:
`file-formats.md:576` says *"This log is the only VERBATIM copy of what he
typed."* Once the journal stores `exact_payload_bytes`, that sentence is false.
Update it in increment 22's commit — same-commit documentation is the repo's
rule and this is precisely the kind of true-sentence-turned-stale that the
ledger's own note about the design doc's status line warns about.

**Irreversible steps, and what must be true first:**

| step | why irreversible | precondition |
|---|---|---|
| 22 · cutover | a browser holds a receipt id minted by the new path; a revert orphans it | everything in the list above |
| 35 · cutover watermark | design: *"Rollback never deletes/renumbers receipts"* | **temp targets only under this plan.** A live watermark is migration and needs a new gate |
| purge | erasure | **not authorised. Do not build it.** |

---

## Amendments this plan proposes

The design's §Approval gate requires an amendment to name the section and law
being changed. This plan proposes exactly one, and it is a consequence of a
measurement rather than a preference.

**§"Receive and idempotency", ordering law 2.** It reads: *"Interrupted/over-limit
bodies remain client attempts; do not claim receipt or drain an unbounded
socket."* Correct about receipts, and silent about the server's own witness —
and today the server *does* witness them (as a short body indistinguishable
from a complete one). Proposed addition: *the server keeps its non-authoritative
partial witness, explicitly marked incomplete, so tightening receipt semantics
never reduces recoverability for a client without a durable attempt store* (the
CLI/`curl` path, which increments 30–33 do not cover).

**Ruled `rec` (approved) 2026-07-28 05:43, and now landed in the design** at
`user-event-journal.md` §"Receive and idempotency" law 2 — so this section is
history, not a pending ask. Increment 20 implements the witness; the paragraph
below records why the alternative was rejected.

This needed his ruling because it amends an approved contract, and because the
alternative — reordering lane G ahead of increment 20 — protects browsers only
and leaves the same hole for every other client.

---

## Where this plan touches #264

`task-transition-boundary.md`'s ask is open, so its conclusions are context.
This plan contradicts none of them, and two are load-bearing here:

- **`Transition.receipt_id` is mandatory** (its F2). So nothing in lanes B–D
  puts a task event in the journal, and increment 5's chain carries only
  receipt-scoped events. If #264 lands as written, `task_event` is a *separate*
  table and this plan's increment 3 should create the database at the path both
  want (`.dreamwork/user-events.sqlite3`) so its foreign key can exist — one
  file, two tables. This plan takes no position on whether that name is right
  once tasks share the file; it only avoids making a second file inevitable.
- **Zero task state is mutated at HTTP time** (its F3(a)). Independently
  re-measured above at `watch.py:8505`. So increment 22's `202` promises
  reception only, and no increment in this plan needs to make a task change
  inside a request — which is what keeps the cutover small.

---

## What this plan does not resolve

### Needs him

1. **Staged authority.** Lanes A–D and F change no live behaviour: new files,
   new tests, no HTTP change, no migration. Lanes E and H change the response
   the browser gets and the version gate. May the first group start while the
   second waits? This is the ask.
2. **The one amendment** in §"Amendments this plan proposes" — the incomplete
   witness. It changes an approved law.
3. **`200` → `202` on all six write routes.** Measured: the browser uses
   `res.ok` throughout, so nothing he sees changes, and fifteen test/guard
   assertions move. Confirming he considers that a non-event is cheaper than
   discovering he does not.
4. **Purge and PostgreSQL stay out entirely** — built-not-run, or not built?
   This plan assumes not built, and fixtures 18 and 19's second half are
   recorded unplaceable on that basis.

### Deferred to a later increment on purpose

- the exact bounded `reason_code` vocabulary — increment 24 picks it and
  `file-formats.md` records it in the same commit;
- CLI output detail beyond the design's field list — increment 26;
- which adapter is written first — increment 19 takes `/answer`, the
  highest-loss path, and the rest follow;
- SQLite index and vacuum tuning — after increment 10 has a measurement to tune
  against;
- the non-Python CLI seam (#264 §"The seam a non-Python CLI can implement") —
  lane F ships Python and leaves the seam where #264 put it;
- whether `task_event` shares the database file — #264's ask, not this plan's;
- topic chats — excluded, and the design already says an adapter may register
  later without a second queue.

### Found while measuring, out of scope, reported not fixed

- **`/answer` and `/comment` truncate `questions.md` in place** (`watch.py:8462`,
  `8496`) — no temp, no rename, no `fsync`, while `/ask` next to them uses
  `atomic_write_text`. A crash mid-write loses the file, on the two routes that
  carry his answers. Wants its own task; lane C would subsume it, but lane C is
  a long way off and this is one function call.
- **No short-read check in `do_POST`** (`watch.py:8387`, M22) — an interrupted
  body is witnessed as complete. Increment 20 fixes it; worth its own id in case
  lane E is deferred.
- **`log_submission` has zero direct unit tests** — the most durability-critical
  function in the file is covered only end-to-end.
- **`_send` cannot express a status code** (`watch.py:8231`) — a small structural
  gap that any future non-200 write response hits.

---

--- SUMMARY ---

- **What this is:** the red-first implementation plan `#263`'s `"rec"`
  authorised, and nothing else. Thirty-five increments of ~15–20 minutes across
  eight lanes, taking `user-event-journal.md` §"Red-first acceptance fixtures"
  as the acceptance set. **It authorises no code**; §"What this plan does not
  authorise" lists the six exclusions verbatim so the next reader cannot read a
  plan as a licence.

- **Shape of the sequence:** A digest (2) → B journal (8) → C domain files (5)
  → D application (4) → E HTTP (6) → F CLI (4) → G browser (4) → H version gate
  (2). `E3` (increment 22) is the single cutover; everything before it is
  additive, everything after assumes the journal is authority.

- **Measured, not remembered.** No tracked `.py` mentions `sqlite3` — lanes B–D
  are entirely greenfield. No `202` exists anywhere in `watch.py`; `_send`
  hardcodes `200`. No cross-process lock exists at all (`ANSWER_LOCK` is a
  `threading.Lock`), so `DomainFileStore`'s durable-replace half already exists
  as `atomic_write_text` and its lock and lineage halves do not. Every command
  is in §"Seams that already exist, measured".

- **Two measurements changed the plan.** (a) There is **no short-read check** in
  `do_POST`, so an interrupted body is currently witnessed as complete —
  tightening receipt semantics at increment 20 would *reduce* recoverability
  unless the partial witness is kept, which is the one amendment this plan asks
  him to rule on. (b) The browser checks `res.ok` everywhere, so `200 → 202`
  changes nothing he sees and exactly fifteen assertions (counted with `ast`, not
  grep — the grep answer was wrong).

- **Per-increment rigour, not a preamble.** Each increment names its test, what
  it asserts, the production line whose deletion makes it fail, and **what its
  tests must not fake** — threads standing in for processes at increment 9, a
  patched clock at 7, a test-authored domain file at 16, `urllib` at 20, a
  patched `open` at 23, a hand-copied hash formula at 5. A greenfield
  `ImportError` red is explicitly declared *not* verification: the discriminating
  red is a second act, after green, by deleting the named line.

- **Fixtures: 18 of 20 placed.** Fixture 18 (purge) and the PostgreSQL half of
  fixture 19 are **unplaceable because the approval clause excludes them** — not
  a design gap, not untestable. One genuine testability finding: fixture 3's
  `fsync`-specific failure cannot be induced through stdlib SQLite, so increment
  22 tests the contract at a real seam (`chmod 0500`) and the `fsync` case is a
  recorded gap with the `LD_PRELOAD` shim named — a mocked `fsync` is the exact
  thing the design's own crash-fixture sentence forbids.

- **Safety is one invariant, not an order:** *his words never have fewer durable
  homes than at the previous commit*. Two things called "shadow" run in opposite
  directions and are named separately (journal-shadow before the cutover,
  log-shadow after). The cutover has an explicit precondition list including a
  green **two-process** test, a real-target shadow window with the two counts
  asserted at runtime, and the fifteen `200` assertions moving in the same
  commit. `submissions.log` is kept from becoming load-bearing by a one-line
  grep assertion in the CLI's own tests.

- **Parallelism as it will actually dispatch:** five lanes can start cold on
  disjoint files, but `watch.py` is one 8,647-line file that lanes E and G both
  live in and other dreamers already hold — so **E and G share one lane in
  practice**, and lane E should get its own `test_user_events_http.py` to remove
  the last collision.

- **Open, needing him:** staged authority for lanes A–D+F while E and H wait;
  the incomplete-witness amendment; confirmation that `200 → 202` is a non-event;
  and whether purge/PostgreSQL are not-built rather than built-not-run.

- **Deferred on purpose:** reason-code vocabulary, CLI output detail, adapter
  order, index tuning, the non-Python CLI seam, whether `task_event` shares the
  file (#264's ask), topic chats.

- **Reported, not fixed:** `/answer` and `/comment` truncate `questions.md` in
  place while `/ask` beside them writes atomically — a crash mid-write loses the
  file on the two routes carrying his answers, and it is one function call to
  repair.
