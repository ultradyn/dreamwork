# Delivery modes — instant push vs batched queue (#342)

**RULED 2026-07-30 00:23 (via questions.md): Q1 rec — the ambiguous class is
batched by default (a `do now` still pre-empts); Q2 rec — the posture axis
`delivery` (`instant`|`batched`) in `.dreamwork/posture`, absent = instant,
with the most-urgent kinds pre-empting even in batched mode; Q3 rec amended —
the loop gates urgency, but plugins may *suggest* it.** The ruling settled the
design; the implementation landed as **#342b** (folded 2026-07-30 — the
`delivery` axis, `emits_wake`, `PREEMPT_KINDS`, and the four content-route gates).
What follows is the design as ruled on — the "his to rule" framings are kept as
the record, with the outcomes marked.

## Authority and what this builds on

His ask (#342): a mode toggle for delivery method — **instant push** (the agent
is woken the moment he sends something) vs **batched/queued delivery** (the agent
gets all pending updates at once, on its next tick). Batched is more efficient but
less responsive, so it suits orchestration-heavy phases. **His stated defaults:**
`add idea` / `add task` do **not** interrupt; `do now` **does** interrupt; answers
and notes on questions/reviews are *"the genuinely ambiguous class the toggle is
for."* The stated purpose, in his words: *"this should also help with the agent
being overwhelmed or forgetting to process some things."*

Both blockers cleared today:
- **#294 (store + CLI seam)** executed — `ledger_store.py` / `ledger_write.py` /
  `ud-dw-tasks-migrate` are the cutover; `tasks.md` is a shim, never a source.
- **#263 (user-event journal)** landed — `user_events/` (SQLite, WAL +
  `synchronous=FULL`, hash-chained events, a per-consumer read cursor) is the
  durable receipt store, and the **E3 cutover is in `watch.py`**: every write
  route commits a receipt *before* dispatch (`do_POST` → `_journal_receive` at
  `watch.py`, `Handler._journal_receive` at `watch.py`).

This task **consumes #263's cursor and adds the per-kind interrupt policy +
toggle on top.** Filing a second cursor would be the two-durable-truths failure
#263 exists to prevent; this design does not propose one.

## Two load-bearing facts, measured

**1 · `kind` reaches the wake channel as nothing but a string prefix — so no
consumer can tell urgency today.** `_handle_command` (`watch.py`) builds
the wake line with `command_line(kind, text, source)` (`watch.py`), which
formats `f"command via watch{from_hint(source)}: {kind}{body}"`. An `add-idea`
and a `do-now` are identical to the tail monitor: both append one line to
`watch-events.log`, both wake the coordinator exactly as hard. The journal
receipt carries the route (`/command`) and the exact body, but **`kind` is inside
the body, not a first-class field** — so the journal cannot route on urgency
either, today. Urgency is recoverable only by string-matching `kind` out of the
body. That is the seam delivery-modes routes through (§"What changes in
watch.py").

**2 · The command channel was push-only and not durable — but #263 made it
durable, and that is the half this toggle rides.** `SKILL.md:117-124` records the
pre-journal failure mode verbatim: *"a command he types into the dashboard
composer exists only as a line in that file… so if the tail monitor is not armed
(a resumed session, a compacted one, a `watch.py` started after init), his
`do now:` is lost with no error anywhere."* `watch-events.log` is best-effort
append (`log_event`, `watch.py`) with `except OSError: pass`; an mtime change
says the file moved but tells no reader which lines are new, and **session memory
of the offset is exactly what compaction destroys.** #263 fixes the durable half:
every write route now commits a receipt with an ordinal in a hash-chained event
log, and a cursor records how far a consumer has read. **The cursor is the
delivery mechanism for batched mode; the wake line is the delivery mechanism for
instant mode.** The toggle chooses which one an item rides.

## Per-kind interrupt policy

The table is the contract. Each dashboard command kind maps to a default delivery
mode. **HIS** marks a default he stated; **PROPOSAL** marks one this design
offers for him to rule on or amend. The four built-in kinds are from `COMMANDS`
(`watch.py:342`): `add-idea`, `do-next`, `do-now`, `maintenance` (plus
dynamically-resolved plugin kinds).

| dashboard input | route / kind | default | source | rationale |
|---|---|---|---|---|
| `do now: …` | `/command` `do-now` | **instant** | **HIS** | he stated it interrupts; it is the explicit preemption |
| `do next: …` | `/command` `do-next` | **instant** | **PROPOSAL** | a queue-jump steer (`SKILL.md:622`) is the same gesture as `do-now`, just one rung less urgent; it names the *next* task, so acting on it promptly costs nothing. He did not name it — open if he disagrees |
| `add idea: …` / `add task: …` | `/command` `add-idea` | **batched** | **HIS** | he stated it does not interrupt; it parks a thought the loop picks up when it chooses next |
| `maintenance` | `/command` `maintenance` | **batched** | **PROPOSAL** | housekeeping is never a preemption; batching it onto the next tick is exactly its shape |
| plugin commands | `/command` `<plugin>` | **batched** | **PROPOSAL** | default to the least disruptive; a plugin that needs to interrupt opts in per-kind (see open Q3) |
| his answer to a question (`/answer`) | `/answer` | **batched** | **HIS (RULED 2026-07-30)** | the ambiguous class batches as a whole — his Q1 ruling overrides this design's instant proposal; a pending answer is read on the tick, and the ruling prioritises "not overwhelmed" over unblocking latency |
| his note on a question/review (`/comment`) | `/comment` | **batched** | **HIS (RULED)** | same class, same ruling; a follow-up note amends rather than preempts |
| his new question for the dreamer (`/ask`) | `/ask` | **batched** | **HIS (RULED)** | same class, same ruling; the dreamer folds it on the next tick |

Two rules run through the whole table and are stated once here:

- **Instant is always a *subset* of the loop's own reading.** An item delivered
  instantly still lands in the journal (the receipt commits in `do_POST` before
  dispatch, for every write route). Instant mode only adds the wake line on top;
  it never *replaces* the durable receipt. So nothing delivered instantly is
  invisible to the cursor, and nothing batched is lost if the monitor is off.
- **The toggle sets the mode; the table sets the per-kind default *under* the
  mode.** In instant mode, batched kinds are *still batched* (an `add-idea` does
  not interrupt even in instant mode). In batched mode, instant kinds are
  *demoted to batched* (a `do-now` rides the queue rather than pre-empting) —
  **or** the table's instant kinds stay instant regardless of mode. Which of
  those two readings "batched mode" means is open Q2; this design proposes the
  latter (the most-urgent kinds pre-empt even in batched mode), because
  *"forgot to process some things"* is the failure batched mode must never
  *cause*, and a `do-now` that does not pre-empt is a `do-now` that lied.

## How the toggle is represented and changed

Delivery is operational posture on this host — *when* he is interrupted — so it
belongs with `pace` / `asking` / `delegation`, which are already gitignored,
per-tick-re-read, and dashboard-settable behind a shared 10s arm. **Proposed: a
fourth posture axis, `delivery`, closed set `instant` (default) | `batched`**,
one line in `.dreamwork/posture`, mirroring the exact contract of the other three
(`file-formats.md:1124`). Absent → `instant` (today's behaviour: every wake line
fires), so a posture file that predates the axis behaves identically. This adds a
line to an existing closed-set file rather than a new file, and it reuses
`POST /posture` (`watch.py`, dual-write of file + one `watch-events.log`
line on real change) rather than a new route.

The alternative shape, offered because the brief told me to check how posture is
persisted and not to assume: a **sibling file** `.dreamwork/delivery` (one line,
closed set, no migration, no `posture` widening). That is the same
sibling-vs-widen choice #445 already ruled on for the other axes, and the same
arguments apply (a sibling touches no closed set; a widening keeps one control).
**Which shape is HIS to rule (Q2).** This design proposes the posture axis,
because delivery is posture by definition and the closed-set discipline that
already guards `pace`/`asking` guards it for free.

Either way: a dashboard control (a chip or toggle beside the posture picker), the
shared 10s arm so a flailing click does not thrash the wake policy, and one
`delivery via watch: <mode>` events line on a real change — the same ceremony
`run-mode` and `posture` already use, and *not* a second one.

## How an agent consumes the cursor in batched mode (exact API)

The cursor is #263's, in `user_events/sqlite.py`. The functions that matter:

- **`Journal.cursor(consumer) -> CursorView`** (`sqlite.py:1392`) — this
  consumer's position, or the **empty-chain origin** (ordinal 0, `H_0`) if none.
  `CursorView` (`sqlite.py:110`) carries `scanned_through_event_ordinal`,
  `chain_hash_at_ordinal`, and `revision`.
- **`Journal.head_ordinal() -> int`** (`sqlite.py:497`) — the high-water event
  ordinal; **`head_hash()`** (`sqlite.py:501`) — the hash there, or `H_0`.
- **`Journal.verify_chain(through_ordinal=None) -> ChainVerifyResult`**
  (`sqlite.py:550`) — recomputes `H_1..H_n`, names the first mismatch.
- **`Journal.advance_cursor(consumer, expected, scanned_through) ->
  AdvanceCursorResult`** (`sqlite.py:1415`) — CAS-advance *only* past a verified
  chain endpoint; the `expected == verified head_hash` comparison (B6 red line)
  is what stops a consumer advancing past a hash it does not hold. On a broken
  chain it refuses and reports `ordinals_read` (a bounded full rebuild).

The cursor position is **durable and machine-local**: it lives in the `cursors`
table (`consumer PRIMARY KEY, scanned_through_event_ordinal,
chain_hash_at_ordinal, revision`, `sqlite.py:358`) inside the per-target
`.dreamwork/user-events.sqlite3` — the same WAL+FULL database that holds the
receipts. It is per-consumer (the coordinator is one consumer; a subagent could
be another), and it survives restart and compaction because it is not session
memory. **"Start of the queue" means concretely: the events with ordinal in
`(cursor.scanned_through_event_ordinal, head_ordinal()]`** — the half-open range
strictly above what the cursor has already verified-and-advanced past.

A batched consume is then three acts:

1. **Read the range.** `cursor("coordinator")` for the position; `head_ordinal()`
   for the end. The events in that ordinal range are the queue. **Finding: the
   journal has no read API that returns the event rows between two ordinals yet.**
   `cursor()`/`advance_cursor()` give the *position* and the *integrity check*;
   they do not return the rows. The CLI `list` (`ud-dw-user-events:cmd_list`) is a
   status/after/limit projection, not cursor-bounded. So delivery-modes needs a
   **cursor-bounded read projection** — a function returning the
   `receipt.created` events (and their receipts' route + `exact_payload_bytes`)
   in `(cursor, head]`, ordered by ordinal. That is the one genuinely-new journal
   surface this design names; everything else consumes what #263 already built.
2. **Verify, then act.** `verify_chain(head_ordinal())` confirms the chain is
   intact to the end; the events route to their adapters (`apply.py`'s
   `reconcile` / the per-route `ApplicationAdapter` registry, `apply.py:417`),
   which is where a receipt becomes the loop's action (fold an answer, act on a
   command, etc.). The proof machinery (`apply.prove_applied`) is exactly-once, so
   a batched replay of an already-applied receipt is a no-op — *that* is why
   batched mode cannot double-deliver.
3. **Advance.** `advance_cursor("coordinator", expected=head_hash(),
   scanned_through=head_ordinal())` commits the new position inside the same
   durable store. A crash between act and advance replays the range on the next
   tick; the adapters' proof turns the replay into a no-op for the finished ones.

This is the "agent gets all updates at once" he asked for: one bounded read, one
batch of adapter replays, one cursor advance — on the tick, not on the wake.

## What changed in watch.py's write routes (design-as-built — #342b landed)

The #342 ruling's per-kind wake routing **is landed** in `watch.py` (increment
#342b, folded 2026-07-30). The seam is `emits_wake(kind, target)` (`watch.py`):
`kind in PREEMPT_KINDS` (`("do-now","do-next")`, `watch.py`) wakes regardless
of mode; every other kind wakes only when `delivery_mode(target)` (`watch.py`)
reads `instant` (absent axis → `DELIVERY_DEFAULT = "instant"`, `watch.py`).
Every wake goes through the single append fn `log_event` (`watch.py`); the
receipt commits unconditionally in `do_POST` before dispatch. **The receipt is the
durable home; the wake line is the interrupt.** Withholding the wake line IS batching.

`WRITE_ROUTE_HANDLERS` (`watch.py`) registers **twelve** write routes. Their
wake status today, each verified against the handler while writing this section:

| route | handler (def) | wake gate | status |
|---|---|---|---|
| `/command` | `_handle_command` (`14341`) | `if emits_wake(kind, target):` (`14363`) → `log_event` (`14364`) | **GATED** — pre-empt kinds (`do-now`/`do-next`) always wake; `add-idea`/`maintenance`/plugin kinds wake only in instant mode. COMPLIANT |
| `/answer` | `_handle_answer` (`14206`) | `if emits_wake("/answer", target):` (`14236`) → `log_event` (`14237`) | **GATED** — batched kind. COMPLIANT |
| `/ask` | `_handle_ask` (`14181`) | `if emits_wake("/ask", target):` (`14201`) → `log_event` (`14202`) | **GATED** — batched kind. COMPLIANT |
| `/comment` | `_handle_comment` (`14243`) | `if emits_wake("/comment", target):` (`14271`) → `log_event` (`14272`) | **GATED** — batched kind. COMPLIANT |
| `/decide` | `_handle_decide` (`14277`) | none — unconditional `log_event` (`14334`) | **NOT GATED** — a content route with a journal receipt that wakes unconditionally, silently undoing batched mode for review decisions. Gating it behind `emits_wake` so a review decision rides the batched cursor like `/answer` and `/comment` was landed under #515 (mode-gated behind `emits_wake`, merged `8908b96`) — every content route now realises the ruling |
| `/tint` | `_handle_tint` (`14367`) | no `log_event` call at all | **non-waking by design** — a colour is not a thing an agent acts on; the loop learns it from the file via the 2s poll, not a wake (handler docstring: *"DELIBERATELY NOT AN EVENTS-LOG LINE, and it is the only write here that is not"*) |
| `/run-mode` | `_handle_run_mode` (`14392`) | none — unconditional `log_event` (`14417`) on a real change | **always-instant carve-out** — control-plane (see next section) |
| `/posture` | `_handle_posture` (`14421`) | none — posture-triple `log_event` (`14495`) + delivery-axis `log_event` (`14499`), each on a real change | **always-instant carve-out** — control-plane (see next section) |
| `/deploy` | `_handle_deploy` (`14508`) | no `log_event` call at all | **non-waking by design** — it restarts the server; success is a new `GENERATION` on `/mtime`, not a wake line |

So the "one decision point per write route" this section once asserted is now
realised for four of the five content routes. The fifth — `/decide` — is the gap
#515 closes; until it lands, a `/decide` under `delivery: batched` fires its wake
line every time. `/tint` and `/deploy` correctly have no wake line at all (a
colour and a restart are not agent actions). The two control routes wake
unconditionally and on purpose — that carve-out is the next section.

## Wake channels outside the route table (#517)

The ruling was framed entirely around user input *kinds*, so it says nothing about
system, control, or error wakes. The #514 audit traced every `log_event` call site;
four live wake channels sit outside the per-kind route table above, and each now
has a stated policy:

### Control-plane wakes — always-instant carve-out

`_handle_run_mode` (`watch.py`) and `_handle_posture` (`watch.py`) each
call `log_event` on a real change with no `emits_wake` branch: a `run-mode via
watch` line (`14417`), a `posture via watch` line for the pace/asking/delegation
triple (`14495`), and a `delivery via watch` line for the delivery axis (`14499`).
These are **control/meta** events — the human reconfiguring how the loop runs — not
content inputs, so they fall outside the per-kind table. **They wake unconditionally
on purpose.** A `delivery` toggle that does not wake the loop until its next tick
*defeats the toggle*: he switches to batched to stop the noise, and if the switch
itself does not interrupt, the loop keeps firing under the old (instant) mode until
it happens to tick — the opposite of the control he just asserted. The same holds
for run-mode and posture changes: he is steering, and the steer must take now. This
is the code's current behaviour and it is correct; this section exists to state it
as a carve-out rather than leave it an unannotated default.

### Journal failure-path wakes — always-loud error diagnostics

`_journal_receive` (`watch.py`), `_journal_record_health` (`4685`), and
`_journal_reject` (`13542`) each call `log_event`, but **only inside an `except`**
(at `13524`, `13539`, `13561`). They fire solely when the journal
open/receive/record/reject itself failed. An error diagnostic should always be loud
— a receipt-commit failure means his inputs may not be durable — so these wake in
any mode. They are not content and are not a class the per-kind ruling governs.

### The tasks-cutover one-shot — operational migration

`ud-dw-tasks-migrate` step 6 (`ud-dw-tasks-migrate:1411-1414`) appends one
`ledger-cutover …` line to `watch-events.log` with no mode awareness. It is a
one-shot operational CLI event that runs once at cutover, not a dashboard route,
and is outside the delivery ruling's scope.

### `question-updated` — mode-gated, not journaled (#516, RULED 2026-07-30)

Ruled in `.dreamwork/docs/plans/question-updated-wake.md` and landed in the
same increment. `track_question_updates` runs inside `collect()` on every
dashboard poll and, when a question entry's content digest changes, emits one
`question-updated via watch: …` line **behind `emits_wake("question-updated",
target)`** — a per-kind signal routed under the delivery mode: fired in
`instant`, withheld in `batched` (the tick's `questions.md` read IS the drain;
withholding the wake IS batching, not dropping — the sig store still stamps).
**Not journaled, by construction:** `question-sigs.json` (atomic write) +
`questions.md` (polled every tick) are the durable delivery; journaling the
event would file a second durable truth for content a file already holds — the
#263 anti-pattern. The always-instant carve-out alternative is refuted by
measurement: an unguarded per-entry content channel is what produced the
63-event phantom storm at `2026-07-30T09:43:31` (63 of 107 live log lines,
fired between #509's algorithm change and #534's silent-re-seed fix).

The same increment fixed the **re-seed swallow** (#516 Decision 3): the #534
re-seed branch's early return skips change detection, so a real content change
riding the same collect as an algorithm re-seed lost its event and kept a
stale `updated_at` — permanently (the new-algo digest of changed content never
diffs again). Cross-algorithm change detection is impossible by construction,
so the re-seed now stamps `now` uniformly (a visible, self-aging blip on a
rare algo upgrade) instead of carrying the prior stamp (a hidden stale age).

## The "always part of the agent's loop" guarantee

Instant mode must not make low-urgency items depend on a monitor being armed, and
batched mode must not let them pile up unprocessed. **Both halves are the cursor
read on every tick** — the same per-tick re-read `run-mode` and `posture` already
use (`#426`):

- **Low-urgency items are guaranteed processed in *instant* mode** because the
  cursor read is part of the tick, not part of the wake. Today (`SKILL.md:117`) an
  `add idea` rides the wake line and is lost if the monitor is off; under this
  design it rides the durable receipt, and the tick's cursor read drains it
  whether or not the monitor fired. The wake becomes an *optimisation* (act
  sooner), not the *delivery path* (act at all).
- **Batched mode is bounded by the tick.** A batched item waits at most one tick;
  the cursor read on the next tick drains the whole range. There is no unbounded
  queue, because the consumer's position advances every tick to `head_ordinal()`.

This is the realisation of his stated purpose — *"help with the agent being
overwhelmed or forgetting to process some things."* Forgetting was possible
because delivery was a best-effort wake line with no durable marker and no
reader-side offset; the cursor + tick read removes both gaps at once. Being
overwhelmed is addressed by *batching*: in batched mode, a burst of `add idea`s
arrives as one cursor-bounded read and one batch of adapter replays, not N
wake-and-act cycles.

## Open calls for him — RULED 2026-07-30 00:23

- **Q1 — the ambiguous class (answers / notes on questions / reviews) →
  RULED: batched by default, the whole class.** His `rec` answered the
  question as put in `questions.md`, whose rec was batched for the class as a
  whole — *"they are read on the tick either way, and the class is exactly
  where 'overwhelmed' comes from"*. This **overrides** this design's proposed
  `/answer` → instant split: `/answer`, `/comment` and `/ask` all default to
  batched; a `do now` still pre-empts. The toggle exists *because* this class
  is judgement — and his judgement is that it batches.
- **Q2 — where the toggle lives, and what "batched mode" reads as → RULED:
  rec.** (a) the posture axis `delivery` (`instant`|`batched`) in
  `.dreamwork/posture`, absent = `instant`; (b) the proposed reading stands —
  the most-urgent kinds (`do-now`) pre-empt even in batched mode. The sibling
  `.dreamwork/delivery` file is rejected.
- **Q3 — plugin commands → RULED: rec, amended.** The **loop gates** a kind's
  urgency — a plugin cannot mark itself instant. Amendment: **plugins may
  *suggest*** urgency; the suggestion is input to the loop's gate, never a
  self-grant.

## What this design did NOT authorise — landed as #342b

The 2026-07-30 ruling settled Q1–Q3. The implementation then landed as
**#342b** (folded 2026-07-30): the `delivery` posture axis (`delivery_mode`,
`watch.py`), the per-kind gate (`emits_wake`, `watch.py`), the
pre-empt set (`PREEMPT_KINDS`, `watch.py`), and the four content-route
gates named in the table above. The list below is kept as the historical record
of what the *design doc alone* did not authorise before the ruling — it is
history, not current state. What is current is the design-as-built state in the
two sections above: the gates are in for four of the five content routes, and the
the `/decide` gap closed under #515 (landed).

Matched to house style (`attention-modes.md`, `user-event-journal-implementation.md`
§"What this plan does not authorise"): #342 was filed as a DESIGN task, and this
doc was the deliverable. Pre-ruling it authorised **no code.** Specifically:

- **any `watch.py` change** — not the per-kind wake routing, not the posture-axis
  plumbing, not a `delivery` field on the receipt.
- **any `user_events/` change** — not the cursor-bounded read projection this
  design names as the one new journal surface, not a `kind`/urgency field.
- **any `apply.py` change** — batched replay uses the adapters and proof exactly
  as lane D built them.
- **any `file-formats.md` or `lint.py` change** — a `delivery` posture axis, if
  he rules it in, lands its closed-set and lint in the implementation commit, not
  here.
- **no migration, no deployment, no change to a running loop or live target.**

A design gets read as a licence. It is not one. The open calls above are what the
next gate has to decide.

---

--- SUMMARY ---

- **What this is:** the #342 design — instant push vs batched delivery, a
  per-kind interrupt policy, and a toggle. **Design only; authorises no code.**
  It consumes #263's cursor and adds the policy + toggle on top; it does not file
  a second cursor (the two-durable-truths failure #263 exists to prevent).

- **Two measured facts frame it.** (a) `kind` reaches the wake channel
  (`watch-events.log`) as nothing but a string prefix (`command_line`,
  `watch.py`), so an `add-idea` wakes the loop exactly as hard as a
  `do-now` — no consumer can tell urgency today. (b) The command channel was
  push-only and not durable (`SKILL.md:117`: a `do-now` is lost if the monitor is
  off); #263's E3 cutover made every write route commit a durable receipt first,
  and the per-consumer cursor (`sqlite.py:1392`/`1415`) records how far a reader
  has got. **The cursor is batched mode's delivery mechanism; the wake line is
  instant mode's.**

- **Policy table** maps each dashboard input to a default. Post-ruling every
  row is settled: `do now`/`do next` → instant; `add idea`/`add task`,
  `maintenance`, plugins, `/answer`, `/comment`, `/ask` → batched (the
  ambiguous class batches as a whole — his Q1 ruling).

- **Toggle representation — RULED (Q2):** a fourth posture axis `delivery`
  (`instant` | `batched`) in `.dreamwork/posture`, reusing `POST /posture` and
  the 10s arm — absent defaults to `instant` (today's behaviour). The
  sibling-file alternative is rejected; the most-urgent kinds pre-empt even in
  batched mode.

- **Batched consumption** = three acts on the tick: read the events in
  `(cursor, head_ordinal()]`, verify + replay through the adapters (proof is
  exactly-once, so replay can't double-deliver), then `advance_cursor`. **One
  new journal surface named: a cursor-bounded read projection** — `cursor()`/
  `advance_cursor()` give the position and integrity check but return no rows, so
  delivery-modes needs the read that the CLI `list` does not provide. Everything
  else consumes what #263 built.

- **watch.py routing — LANDED (#342b):** the per-kind gate `emits_wake`
  (`watch.py`) now decides, per route, whether to emit the wake line; the
  receipt always commits. Four of the five content routes are gated
  (`/command`, `/answer`, `/ask`, `/comment`); `/decide` is the gap **#515**
  closes (in flight). `/tint` and `/deploy` have no wake line by design; the
  control routes (`/run-mode`, `/posture`) wake unconditionally as a carve-out.
  Withholding the wake line *is* batching.

- **The loop guarantee:** the cursor read runs on every tick (like run-mode/
  posture), so low-urgency items are drained whether or not the monitor fired —
  the wake becomes an optimisation, not the delivery path. This is his stated
  purpose ("forgetting to process some things") made impossible by construction.

- **Open calls — RULED 2026-07-30:** Q1 the ambiguous class batches (whole
  class; overrides the `/answer` → instant proposal); Q2 the `delivery`
  posture axis with urgent kinds pre-empting; Q3 the loop gates urgency,
  plugins may suggest. The routing **landed as #342b**; the open remainder is
  `/decide` (#515, landed), the `question-updated` policy (#516, RULED
  2026-07-30 — mode-gated, not journaled, re-seed swallow fixed), and the
  control/journal/migrate wakes now documented here as carve-outs.
