# Durable user-event inbox and replay CLI

**Task:** #263
**Status:** design settled; implementation, migration, purge, and deployment are
not authorised. Lane G remains subject to Max's separate ruling.
**Grounding:** source and tests inspected at `beddf975`, reverified after the
required rebase onto local `master`, plus the accepted contract in
[`user-event-journal.md`](user-event-journal.md).

## Decision

The durable inbox is **not another queue**. It is the bounded, per-consumer view
of `receipt.created` events and nonterminal receipt status in the existing
`.dreamwork/user-events.sqlite3` journal. The journal remains reception
authority; a monitor line only wakes the dreamer, which then reads the inbox.

SQLite remains the physical store. Its canonical history is logical
append-only: receipt events and status transitions append, while current-state
and cursor tables are rebuildable mutable projections. Neither append-only
JSONL nor a directory containing one file per event is introduced.

The installed operator surface becomes one CLI:

```text
ud-dw-user-events pending --limit 20
ud-dw-user-events replay --read-id <id>
ud-dw-user-events consume --read-id <id> --through <ordinal>
ud-dw-user-events list --limit 20
ud-dw-user-events show <receipt-id> --max-bytes 4096
ud-dw-user-events health
```

`dev/journal_consume.py` remains a compatibility wrapper during cutover. Its
working `pending -> process/replay -> consume --through` protocol is preserved,
not reimplemented beside the new CLI.

## Accepted invariants

1. `202 Accepted` means one receipt transaction committed durably, not that the
   requested domain effect happened.
2. The transaction commits immutable receipt metadata, exact request bytes, the
   initial `received` transition, and the chained `receipt.created` event before
   the response is authorised.
3. A client action id plus request digest is the idempotency join. Equal retries
   return the original receipt; a different digest conflicts; a new action id is
   a new intentional action.
4. The monitor is an interrupt only. It may carry the receipt id for diagnosis
   and joining, but no agent acts from the wake text. On every wake and every
   normal tick the dreamer reads the durable inbox first.
5. Exact submitted bytes remain until an explicit, scripted operator purge.
   Agents never hand-edit the store. A purge may remove payload but retains a
   non-sensitive tombstone and a durable purge report.
6. LLMs and operators read bounded projections. No normal workflow tails raw
   SQLite pages, WAL files, JSONL, or an unbounded payload stream.
7. A cursor means “scanned through this verified event ordinal”, not “all work
   below here succeeded”. Retryable, recovering, and needs-human receipts remain
   queryable after cursor advance.
8. Application is exactly-once only when the journal intent and the real domain
   effect are joined by the receipt id. A marker in a generic side ledger is not
   proof that the requested semantic effect happened.

## Existing machinery: keep, replace, migrate

### Keep

- E3's route order: `do_POST` calls `_journal_receive`; `_send_receipt` returns
  `202` only with the committed id, sequence, digest, and `Location`.
- `Journal.receive()` and its one `BEGIN IMMEDIATE` transaction, UUID/digest
  replay/conflict decision, WAL, `synchronous=FULL`, and shared per-target DB.
- Append-only `transitions` and hash-chained `events`; the current receipt row is
  explicitly a projection, not immutable history.
- `Journal.events_since_cursor()`, `verify_chain()`, and `advance_cursor()`.
- The bounded-advance rule: a receipt committed after the pending read remains
  above `--through` and is listed next time.
- Ternary application proof (`APPLIED | NOT_APPLIED | UNKNOWN`), domain locks,
  generation/digest markers, and durable replace for adapters that operate on a
  governed domain file.
- Receipt ids on wake lines. The historical #519 finding said they were absent;
  `command_line(..., receipt_id)` and its three-way join test show that is no
  longer current.
- `submissions.log` as a best-effort audit shadow. Its failure cannot revoke a
  committed receipt and it is never replay input.

### Replace

- **Wake-and-act** becomes **wake-then-read**. Urgent events still wake
  immediately, but urgency changes latency, not the source of the instruction.
- `ud-dw-user-events replay`'s current `not_implemented` response is replaced by
  real adapter reconciliation. Until that exists it must continue to say it did
  nothing.
- The generic `.dreamwork/applied.md` marker path is retained only as legacy
  diagnostic evidence. A bare route marker does not prove that an answer was
  folded, a task was created, or a setting changed. Replay either uses the real
  domain adapter and its co-written marker or records `needs_human` without
  claiming success.
- CLI-owned raw SQL becomes `JournalAdapter` projection methods, so the daemon,
  cursor drain, and CLI cannot disagree about state, reasons, or event bounds.
- In schema v2, exact payload bytes, the plain request digest, and a private
  commitment nonce are stored once in a purgeable payload row. A chained
  receipt event commits to metadata and an unguessable payload commitment, not
  a second copy of the exact bytes or a dictionary-testable plain digest.

### Migrate

- `dev/journal_consume.py pending|consume|show` delegates to the installed CLI
  while retaining its current tab output and exit codes for one compatibility
  window. `SKILL.md` switches only after parity tests pass.
- Existing `default` redaction rows map to the v2 `default` class. No payload is
  reclassified or hidden during migration without an explicit policy.
- A v1 database is never rewritten in place. A quiesced successor database is
  built and verified, then atomically replaces the canonical path. Its first
  event binds the predecessor journal id, schema version, and verified head
  hash. Receipt ids and sequences stay stable; copied events retain their legacy
  ordinal for audit.
- Cursor positions are mapped through copied event ordinals. Any cursor that
  cannot be proved against the predecessor chain is reset to the empty-chain
  origin and replayed idempotently; it is never guessed from time.
- Historical `submissions.log` rows are not imported as authoritative receipts.
  The existing read-only reconciliation audit continues to report
  `UNJOURNALED`/`UNMATCHED` legacy witnesses.
- Legacy `.dreamwork/applied.md` entries do not become `applied` automatically.
  Migration proves the corresponding real domain marker/effect or leaves the
  receipt visible as `needs_human`.

## Storage choice by IGC

**Context:** a shipped SQLite journal already authorises `202`, serialises
same-target writers, maintains status/history/cursors, and feeds the loop. Exact
bytes must be purgeable later without adding a second receipt authority.

| Idea | All | G1 | G2 | G3 | G4 | G5 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| One append-only JSONL file | ✘ | ✘ | ✔ | ✘ | ✘ | ✔ |
| One atomically-renamed file per event | ✘ | ✘ | ✔ | ✘ | ✔ | ✔ |
| SQLite journal + cursor inbox view | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |

- **G1:** one concurrent operation atomically decides idempotency and commits
  receipt, initial status, and event before `202`.
- **G2:** immutable ordered history and a bounded replay cursor are possible.
- **G3:** keep the working E3, claim, transition, chain, and bounded-consume
  machinery; do not create or reconcile a third queue.
- **G4:** scripted physical purge can remove exact bytes while preserving a
  non-sensitive tombstone and verifiable successor history.
- **G5:** every crash and concurrency claim has a real, bounded falsification
  harness that must pass before the claim is made.

Decisive errors:

- JSONL cannot atomically combine concurrent UUID compare/insert, initial
  status, and a cursor-safe ordered append without adding a lock/index/state
  system that recreates the database. A crash also leaves a partial final line,
  and physical purge rewrites the supposedly append-only authority.
- A per-event spool makes individual publication atomic, but concurrent global
  order, compare-and-swap status, claims, cursor position, and UUID uniqueness
  still require a locked manifest/database. Adding it beside the existing
  journal creates two receipt truths.
- SQLite v1 **unchanged** would fail G4 because `events.canonical_payload`
  currently embeds the exact body as well as `receipts.exact_payload_bytes`.
  The surviving idea is therefore SQLite with the v2 payload separation and
  successor migration above, not an assertion that the present schema can
  already purge.

G5 is a design gate, not evidence that current durability was tested. The
current tree checks pragmas and permission failure but has no crash-mid-write or
power-cut test. Until the harness below passes, machine/power durability is an
accepted requirement and an informed SQLite expectation, **not a verified fact**.

## Receive, wake, and dual witnesses

The request sequence is:

```text
durable client attempt (browser lane G)
  -> receive transaction: receipt + received transition + chained event
  -> COMMIT returns
  -> best-effort submissions.log shadow
  -> validate/apply or reject, with append-only status
  -> 202 + stable receipt identity
  -> optional wake containing only a receipt-id hint
  -> dreamer reads the journal inbox
```

There are two deliberate witness pairs, not two queues:

1. **Network ambiguity:** the browser attempt is the client-side intent witness;
   the journal receipt is the server-side reception witness. The action UUID
   joins them. A missing response is retried with the same UUID and bytes.
2. **Application ambiguity:** an append-only journal transition records started
   intent and its reserved successor; the actual domain file/record co-writes
   the receipt marker with the semantic effect. After a crash, both are read to
   decide `Applied`, `NotApplied`, or `Unknown`.

`watch-events.log` and `submissions.log` are diagnostic shadows. They can be
missing, duplicated, or delayed without changing receipt or application truth.

## Bounded inbox and replay protocol

`pending` reads one SQLite snapshot and returns at most `--limit` action rows.
The candidate set is (a) new `receipt.created` events above the cursor and (b)
retryable/recovering/needs-human receipts at or below it. If both classes are
nonempty, half the slots are reserved for each and unused slots spill to the
other; each class is oldest-first. Thus old recovery work cannot starve behind a
steady arrival stream, and new human input cannot starve behind stuck recovery
work. A page is an intentional range, not truncated output. It contains:

```json
{"type":"page","schema":"ud-dw-user-events/v1","read_id":"...","journal_id":"...","consumer":"coordinator","cursor_ordinal":40,"cursor_revision":7,"through":63,"snapshot_head":91,"count":20,"new_count":10,"outstanding_count":10,"has_more":true}
{"type":"event","event_ordinal":41,"event_hash":"...","receipt_id":"...","sequence":31,"endpoint":"/answer","received_at":"...","request_digest":"...","payload_size":123,"redaction_class":"default","preview":"...","preview_truncated":true,"delivery_status":"pending","processing":{"state":"validated","revision":2,"application_adapter":"answer","application_ref":null,"reason_code":null,"bounded_detail":null,"health":[]}}
{"type":"outstanding","event_ordinal":12,"receipt_id":"...","sequence":8,"endpoint":"/comment","delivery_status":"consumed","processing":{"state":"recovering","revision":4,"reason_code":"domain_unknown","bounded_detail":"marker mismatch","health":[]}}
```

The page header and every event are exact for that one read transaction. Preview
is single-line, safely encoded, bounded by bytes, and omitted for restricted
payloads. “Exact event” means exact receipt id, event ordinal/hash, metadata, and
status at the snapshot; exact request bytes remain an explicit bounded `show`.

The read marker is versioned and contains `read_id`, journal id, consumer,
cursor ordinal/revision, `through`, snapshot head, chain hash at `through`, and
the exact receipt ordinals emitted. It is written by temp+fsync+rename. It is
coordination state, not authority: absent, partial, stale, overwritten, or full-
disk failure causes a named refusal and leaves the cursor unchanged.

The current #531 protection remains, generalized for bounded pages:

- `consume --through N` accepts only `N == marker.through`; lower is an older or
  truncated view, higher covers unseen events.
- The marker's starting cursor revision must still match. A competing consumer
  or second pending read causes a safe refusal.
- A concurrent append above the page's `through` is legal and remains pending.
- Intervening non-receipt chain events are included in the verified ordinal
  range and named in page metadata, even though only receipt rows are actions.
- If the range above the cursor contains only transition/health events, the page
  names those non-action ordinals and may advance `through` to the snapshot head;
  zero receipt rows must not make “nothing pending” and “status changed” look
  identical. If no ordinal lies above the cursor, the page is non-consumable and
  replay may still work its bounded outstanding rows without a cursor no-op.

`replay --read-id` re-reads the named receipts from the journal; it never trusts
the preview. For each receipt it emits the receipt id and one closed outcome:

- `applied`: the real domain effect and marker prove present;
- `rejected`: durable validation/domain rejection, with stable reason code;
- `retryable`: transient failure, with bounded code/detail and retry metadata;
- `recovering`: proof is unknown; no mutation was attempted;
- `needs_human`: no authorised semantic adapter can complete it;
- `not_applicable`: a registered route explicitly has no replayable effect.

Unknown routes never become `not_applicable`. They are `needs_human` and name the
route. Re-running replay is safe: applied/rejected/not-applicable are no-ops;
retryable is reclaimed only after its lease; recovering never mutates.

`consume` advances only after every new receipt in the page has one durable
outcome above. Outstanding rows do not control the page endpoint. Nonterminal
outcomes remain listed by status even below the cursor. It then verifies the
chain through the page endpoint and advances to exactly that endpoint. A crash
before advance replays the page; adapter proof makes completed effects no-ops. A
crash after advance cannot hide retryable, recovering, or needs-human receipts
because the status query is independent of the receipt-created cursor.

`list` is a read-only, newest-first search over receipts/status. `show` returns
metadata and transition history plus at most `--max-bytes`; if truncated it
includes original length and digest. `health` reports actual journal/cursor/
receipt health and retains the existing static recovery catalogue under
`health --catalog`. Only `replay` may cause a domain effect; only the separately
authorised operator purge may delete payload.

## Atomicity and concurrency

- Receive, transition, claim, finish, and event append each use one database
  transaction. Receipt metadata and exact payload never appear without their
  initial status/event, or vice versa.
- `BEGIN IMMEDIATE` serialises SQLite writers. UUID uniqueness is a backstop;
  compare-before-insert distinguishes replay from conflict. Busy timeout maps to
  a stable retryable failure, never an invented receipt.
- Page read and cursor advance intentionally are not one transaction. The page
  endpoint and hash bind the read; append-only concurrent writes land above it.
- Status changes are CAS on expected revision. Claims include consumer, random
  token, server-clock lease, and revision; a stale claimant cannot finish.
- Only one process may perform migration/purge. It closes the current generation
  to new receipts, drains in-flight work, checkpoints WAL, and proves old
  processes cannot still hold the generation before the atomic replacement.

## Crash cases and required falsification

A durability statement without a crash-mid-write test is a guess. These are
implementation acceptance gates, not tests performed by this design lane:

| case | chosen-shape behaviour | discriminating falsifier |
|---|---|---|
| Partial JSONL line | Not applicable to canonical storage. A partial read-marker file is non-authoritative and makes consume refuse. | A malformed/short marker lets the cursor move, or produces an unnamed traceback instead of a stable refusal. |
| Kill during receipt transaction | SQLite recovery yields either no receipt or one complete receipt+initial transition+event. No `202` may have been observed for the first case. | Reopen finds a subset, two receipts, a broken chain, or an acknowledged UUID with no receipt. |
| Torn WAL/database record | Recovery rejects an incomplete frame; integrity and chain checks fail closed on committed corruption. | Reopen silently accepts a torn committed event or recreates an empty authority. |
| Full disk / quota | Before commit: rollback and no `202`. After commit: retry returns the same receipt even if the response was lost. | ENOSPC returns `202` without a readable receipt, loses an acknowledged receipt, or changes the UUID outcome on retry. |
| Concurrent writer | Same UUID+digest yields one insert and replays; different digests yield one preserved winner and conflicts; different UUIDs receive one total order. | Two ids/rows for one UUID, split journal histories, duplicate ordinal, or an unbounded hang. |
| Kill after domain fsync before finish | The co-written domain marker proves `Applied`; replay finishes without a second effect. | A duplicate effect, a boolean false on torn/drifted bytes, or a generic side marker treated as effect proof. |
| Append between pending and consume | Cursor stops at the page endpoint; the later event remains pending. | Later ordinal is at/below the advanced cursor without appearing in the page. |
| Crash during successor migration | Before atomic replace, old DB remains authoritative; after replace, successor verifies and links its predecessor. | Neither DB opens, both claim authority, cursors are guessed, or purged bytes remain in active DB/WAL. |

The receipt crash harness must kill at named SQLite/VFS seams rather than mock
the transaction away: before WAL write, during WAL frame write, before/inside
sync, after sync before COMMIT returns, after COMMIT before `202`, and during
checkpoint. A loopback filesystem with a hard quota exercises ENOSPC. A block
fault harness or disposable VM power-cut run is required for the claimed
machine/power boundary. Each run persists the client-observed `202` set outside
the target and, after reopen/reboot, proves every acknowledged UUID exists
exactly once and the chain verifies. If that environment cannot be built, the
machine/power claim must remain explicitly unverified.

## Redaction, retention, and purge

Redaction controls projection, not whether accepted bytes are stored. The server
derives a closed `redaction_class` from the registered route/schema; a request
cannot downgrade it.

- `default`: bounded escaped preview in `list`/`pending`.
- `restricted`: metadata/status only; `show` requires explicit `--reveal` and a
  bounded byte limit. Automated summaries never reveal it.

Reason codes are closed, non-sensitive identifiers. Free-form error detail is
UTF-8-safe, length-bounded, and must not copy request text. Logs contain receipt
ids and reason codes, not payload previews.

Retention defaults to forever. Purge requires a policy file, dry run, typed
confirmation, exclusive maintenance lease, and an immutable report. Only
terminal receipts past every named consumer cursor are eligible. It builds a
fresh successor DB: eligible payload rows and their secret commitment material
become tombstones; noneligible exact bytes are copied; transition/audit history
is re-emitted in order; the new chain links the predecessor head. It checkpoints
and removes WAL/SHM, scans active DB/WAL for the purged bytes, fsyncs the DB and
parent, then atomically replaces the canonical path.

The current schema cannot truthfully perform that purge: exact body bytes also
exist inside `events.canonical_payload`. Schema v2 stores an unguessable payload
commitment in the event and keeps the nonce, plain request digest, and exact
bytes only in the purgeable payload row. Purge destroys all three, leaving a
tombstone that is not a practical dictionary oracle. Unpurged CLI rows may show
the plain digest; a purged row shows only the opaque commitment. A retry after
tombstoning returns the stable receipt identity and `410 purged`; it never
reapplies.

Backups, filesystem snapshots, old database generations, replicas, exported
logs, and offline browser attempts are residual copies with separate retention.
The purge report lists which were verified, deleted, or remain; it never calls
active-store erasure global erasure.

## What was actually checked, and what remains falsifiable

| claim | checked in this lane | what would falsify it / open gap |
|---|---|---|
| Journal commit gates `202` | Read `_journal_receive`, `Journal.receive`, `do_POST`, `_send_receipt`, and the real-permission no-202 test. | A source path sends `202` with no `ReceiveResult`, or a crash/power test loses an acknowledged receipt. Crash half not yet tested. |
| Same-target concurrent idempotency exists | Read the two-real-process UUID test and `BEGIN IMMEDIATE` receive path. | Two receipt rows/ids or two insert results. Existing test covers equal digest; the different-digest race still needs an explicit two-process case. |
| Bounded consume preserves late events | Read `pending`, `consume --through`, cursor APIs, and the test that appends after pending then asserts the late receipt remains. | Any append above `through` is advanced past unread. |
| Wake id can join to receipt | Read `command_line(..., receipt_id)` and the test joining wake, pending, and POST ids. | Any waking write route omits or substitutes the committed id. The current `SKILL.md` sentence saying the id is absent is stale. |
| Replay is semantically exactly-once | Read `apply.reconcile`, default adapters, and `_prove_drained`. | **Currently open:** default adapters append generic markers to `applied.md`; that does not prove the real route effect. This design replaces that witness before claiming success. |
| Physical purge is possible | Read the v1 schema and receipt event canonicalisation. | **Currently false:** exact bytes are duplicated in `events.canonical_payload`; deleting only the receipt blob leaves them. V2 successor migration is required. |
| Power-loss durability | Read WAL/FULL pragma checks and parent/open failure handling. | **Unverified:** no crash-mid-write or power-cut test was found. Pragmas passing is a false-green for this claim. |
| Full-disk refusal | Read the chmod-0500 HTTP failure test. | **Unverified:** permission denial is not ENOSPC and does not exercise a disk filling during WAL/commit. |
| Redaction is enforced | Read the stored `redaction_class` field and current CLI projections. | **Not built:** current list/show do not enforce route-derived projection classes. |

The historical citations also required reconciliation rather than repetition:
#519 accurately records the old missing-id/proof wiring but source now carries
the id; #531's title is an unrelated UI bug while its later note does record the
bounded-consume landing; #702 is about malformed lane bookkeeping and loud
reporting, not a general durability result.

## Authority gate

This document authorises nothing beyond design. No production code, browser
lane G work, schema migration, live-target cutover, payload purge, deployment,
or PostgreSQL operation follows from it. The first implementation increment
must be separately authorised and red-first. The crash harness and schema-v2
purge fixture are acceptance work, not optional hardening after release.
