# Durable user-event journal design

**Tasks:** #260, #262, #263, #269, #274
**Status:** human approval required; no implementation authority
**Date:** 2026-07-26

## Goal and truth order

After `202`, one immutable receipt exists durably; retries share one identity;
application is replayable without duplicate effects; a bounded CLI explains every
event.

```text
browser draft -> client attempt -> durable receipt -> proved domain effect
   mutable        intent witness     reception truth    application truth
```

`submissions.log`, `watch-events.log`, Markdown, browser history, and dashboard
indexes remain shadows, projections, or wake signals. None is receipt authority.

## Accepted decisions

1. `202 Accepted` means durably received, not applied.
2. SQLite ships first behind a PostgreSQL-portable `JournalAdapter`.
3. Journal commit alone authorises `202`; `submissions.log` is best-effort.
4. Browser persists a UUID before POST and reuses it for retries.
5. Same UUID+digest returns one receipt; same UUID+different digest is `409`;
   new UUID+same bytes is a distinct intentional action.
6. Exact bytes remain until explicit scripted purge; agents never hand-edit
   storage. Purge retains a non-sensitive tombstone.
7. Application uses exclusive leased claims and compare-and-swap (CAS).
8. Application proof is ternary: `Applied | NotApplied | Unknown`.
9. Mutable browser drafts/attempts and immutable server receipts are separate.

## Durability boundary

A successful receive transaction survives process crash and the backend's
declared power-loss failure domain before `202`. SQLite uses one shared
machine-local target database with WAL, `synchronous=FULL`, bounded busy timeout,
and durable database/parent creation. This covers process/OS/reboot/power loss
while the local filesystem/disk functions, not physical disk destruction. A
later PostgreSQL/replicated adapter may widen the failure domain without changing
HTTP or application contracts.

Suggested gitignored path: `.dreamwork/user-events.sqlite3` (+ WAL/SHM). All
same-target watch processes open this one journal.

## Receive and idempotency

```text
client_action_id = UUIDv4
request_digest = SHA-256(length_framed(
  protocol_version, UPPERCASE_method, canonical_route,
  canonical_content_type, exact_body_bytes))
```

Every digest field is length-prefixed; concatenation cannot collide at delimiters.
Routes are the exact registered path with a defined query policy (current write
routes accept no semantic query); content type is a parsed, lower-cased media type
plus deterministically ordered parameters. Duplicate/ambiguous Content-Length,
unsupported Transfer-Encoding, multi-valued identity/content headers, unsupported
method/path/media type, authority failure, interruption, and over-limit body are
**transport-envelope failures before receipt**. They return the applicable
4xx/503 and leave the browser attempt durable.

The server recomputes the digest. One receive transaction gives:

| UUID | Digest | Result |
|---|---|---|
| absent | - | insert receipt + `received`; `202` |
| present | equal | original receipt/status; `202`; no insert |
| present | different | `409`; preserve original |

Order is load-bearing:

1. Validate authority and the registered transport envelope before body read.
2. Read one complete bounded body. Interrupted/over-limit bodies remain client
   attempts; do not claim receipt or drain an unbounded socket. **The server still
   keeps its own non-authoritative witness of what arrived, explicitly marked
   incomplete** (amended 2026-07-28, approved by the human at 05:43; proposed in
   `user-event-journal-implementation.md` §Amendments). Without this, tightening
   receipt semantics would *reduce* recoverability for every client that has no
   durable attempt store of its own — the CLI and `curl` paths, which the browser
   increments do not cover. Today the server witnesses an interrupted body
   *badly*: `watch.py:8387` reads `min(nbytes, MAX_BODY)` and never compares the
   result to `nbytes`, so a short read is appended as though complete (#371). A
   witness marked incomplete is strictly better than that, and refusing to witness
   at all is strictly worse.
3. Compute digest and durably commit receipt plus `received` transition.
4. Best-effort append `submissions.log`; failure records `shadow_failed` health
   but cannot invalidate receipt.
5. Always return `202` for that committed receipt with `status=received`, receipt
   id/sequence/digest, and `Location: /user-events/<receipt-id>`; then wake the
   validator/consumer. A same-UUID retry returns the current stable status and
   same Location. The status projection has bounded machine-readable reason codes.

JSON parsing, schema checks, and stable-target/domain validation happen after
receipt, without an application claim. Valid content transitions
`received -> validated`; malformed/schema-invalid/domain-invalid content
transitions `received -> rejected`. Thus a complete registered envelope never
disappears behind synchronous `400`, but an unknown POST path is pre-receipt
`404/405`, not an event. UUID identity conflicts remain synchronous `409`.

## Journal records and state

```text
Receipt { receipt_id, sequence, client_action_id, request_digest, received_at,
method, endpoint, content_type, exact_payload_bytes, payload_size, target_id,
source_hint, redaction_class, purged_at? }

Transition { transition_id, receipt_id, at, from_state, to_state, revision,
consumer_id?, claim_token?, lease_until?, application_adapter?,
application_ref?, reason_code?, bounded_detail? }
```

```text
received -> validated -> claimed -> applying -> applied
    \-> rejected                  \-> retryable -> claimed
                                  \-> recovering / needs_human
```

Validation and rejection append transitions transactionally against the receipt
revision; rejected receipts are never claimed. History is immutable and
append-only. Every receipt creation, validation, claim/lease action, application
result, health event, and purge/tombstone is a canonical journal event with a
monotonic `event_ordinal` and hash:

```text
H_0 = SHA-256(journal_id || schema_version)
H_i = SHA-256(domain_tag || H_(i-1) || length_framed(canonical_event_i))
```

The transaction inserts event `i`, its prior/current hash, and updates the
current-state projection together. Rows below the high-water ordinal cannot be
updated/deleted by normal adapter APIs. A transactional projection accelerates
claims but is rebuildable and checked against the chain. `purged` is retention
state on a terminal receipt; `shadow_failed` is health, not application state.

## `JournalAdapter`

```python
class JournalAdapter(Protocol):
    def receive(envelope) -> ReceiveResult: ...
    def get(receipt_id) -> ReceiptView: ...
    def list(query, limit) -> Page: ...
    def claim(receipt_id, consumer, lease_seconds, expected_revision) -> Claim: ...
    def start_application(claim, adapter, application_ref) -> Started: ...
    def finish(claim, outcome, application_ref, reason) -> FinishResult: ...
    def renew(claim, lease_seconds) -> Claim: ...
    def cursor(consumer) -> Cursor: ...
    def advance_cursor(consumer, expected, scanned_through) -> Cursor: ...
    def purge(policy, operator) -> PurgeReport: ...
```

SQLite and PostgreSQL pass one behavioral contract suite against real databases
and concurrent processes, not only doubles. Both enforce a unique
`client_action_id`; atomically compare its stored digest before insert/replay;
preserve immutable receipt bytes/digest; and serialize event ordinal/hash-chain
append with state revision. Claims update only when state, expected revision,
and lease predicates match. Lease deadlines use backend/server time, never client
clocks. PostgreSQL serialization/deadlock retries are bounded; exhaustion maps to
503 with no receipt unless receive already committed. `SKIP LOCKED` is optional
throughput, never correctness.

Claim laws: atomic/exclusive claim; unguessable token; monotonic revision;
start/renew/finish compare receipt+token+consumer+revision; expired claims may be
reclaimed; stale claimant cannot finish; dual reclaimers cannot both win.

## Crash-safe `ApplicationAdapter`

Journal state alone cannot close this crash window: domain mutation lands, then
process dies before journal finish.

```python
class Proof(Enum): APPLIED; NOT_APPLIED; UNKNOWN
class ApplicationAdapter(Protocol):
    def prove_applied(receipt) -> ProofResult: ...
    def idempotent_apply(receipt, claim) -> ApplicationResult: ...
```

Laws:

1. After cutover, **every supported writer** of managed Markdown/settings uses one
   `DomainFileStore`: server answer/comment handlers, loop folding, coordinator
   CLI, settings writes, and application adapters. Legacy direct writers are
   version-gated/refused. Concurrent unsynchronised editor writes are outside the
   supported mutation contract; file fingerprint drift is detected and fails
   closed rather than being silently overwritten.
2. Every managed full file contains structured `domain_generation`,
   `body_digest`, and last-application identity in that same file. The digest
   covers the canonical body excluding only its own digest field. Missing or
   mismatched metadata, or a generation/fingerprint outside committed lineage
   **and the exact provisional successor reserved by started intent**, proves
   `Unknown`, never `NotApplied`.
3. `DomainFileStore` takes an OS-visible per-domain lock before read; validates
   the complete file and embedded digest/lineage; checks marker and preimage;
   applies effect+marker; increments generation and embeds the new digest; writes
   temp, fsyncs, atomically renames, fsyncs parent. Stale preimages retry fresh.
4. CAS journal `applying` **before** mutation with expected before generation/
   fingerprint and deterministic provisional successor (`after_generation =
   before_generation + 1`, receipt id, adapter, application reference). A file
   committed before journal finish proves `Applied` only when its generation is
   that reserved successor, its body digest validates, and its embedded receipt/
   adapter/application reference exactly match started intent. CAS finish records
   its observed after fingerprint and promotes it to committed lineage. Any other
   unjournaled successor proves `Unknown`.
5. Human-visible effect, receipt marker, generation, and body digest share that
   one durable file write. No writer may add the body then metadata later.
   Intentional external edits use an explicit operator `rebaseline` command:
   validate/preserve bytes, mint a new successor generation, and journal the
   import before further application. Arbitrary editor drift fails closed.

6. Append-only domains use one framed append plus `fdatasync`; incomplete or
   ambiguous framing proves `Unknown`.
7. Marker presence proves `Applied` only in a valid committed-lineage file or the
   exact provisional successor predicate in law 4; a forged marker alone never
   suffices. Questions parsing scans the whole valid file, both literal Open and
   Answered sections, so folding cannot hide a marker.
8. Marker absent proves `NotApplied` only after a complete locked search **and**
   valid known generation lineage that predates this receipt's started intent.
   Torn/malformed/ambiguous/drifted bytes prove `Unknown`.
9. `idempotent_apply` is no-op success when marker exists. Markers live in
   structured margins, not raw prose: adjacent metadata for questions/answers/
   tasks, receipt map for settings, turn metadata for chats.

| Post-crash state | Proof | Action |
|---|---|---|
| received/claimed/applying | Applied | CAS finish; no domain write |
| same | NotApplied | one idempotent apply; then CAS finish |
| same | Unknown | CAS recovering; no mutation; surface evidence |
| applied | any | no-op |
| rejected/terminal fail | - | no apply |

Unknown is a third path, never boolean false. Quarantine is safer than a silent
duplicate or drop.

## Browser `DraftStore` and `AttemptStore` (#269)

One project-partitioned IndexedDB module serves every current/future text field.

```text
Draft { logical_input_id, revision, text, selection, resize, scroll,
owner_tab, owner_lease_until, updated_at, conflict_snapshot? }
Attempt { client_action_id, request_digest, exact_request_bytes,
logical_input_id, draft_revision, created_at,
state: pending|received|conflict|unreachable, receipt_id?, sequence? }
```

Rules: autosave draft before submit; persist attempt/UUID before POST; retries use
identical bytes/UUID; later edits create a newer revision and later send gets a
new UUID; clear only the submitted revision after matching durable `202`; never
clear newer text; unreachable/5xx retains both; `409` locks the attempt and
surfaces both digests. Same logical input uses revision CAS plus short owner-tab
lease. Other tabs mirror changes; divergent edits preserve a conflict snapshot
and require explicit takeover/merge, never last-write-wins. Migrate composer
localStorage once with a migration marker.

Client storage proves attempt, not server reception. Journal receipt proves
reception, not every unsubmitted thought.

## Replay cursor and compaction recovery (#260)

```text
Cursor { consumer, journal_id, scanned_through_event_ordinal,
         chain_hash_at_ordinal, revision }
```

At loop start/after compaction, stream/recompute the canonical chain through the
cursor ordinal (or verify an adapter-owned trusted checkpoint whose creation is
itself chained). Gap/hash/journal-id mismatch triggers a bounded full rebuild from
ordinal 1; mutation/deletion below high water cannot false-pass. Enumerate every
receipt event after the cursor plus all current nonterminal/recovering receipts;
apply by state/proof, never inferred time. CAS advance only after the full page
and chain endpoint were verified. Retry/recovering receipts stay queryable below
high water. This independently covers answer, ask, comment, command, tint, and
future chat adapters.

## Bounded CLI

```text
ud-dw-user-events list --status pending,recovering --after 120 --limit 20
ud-dw-user-events show <receipt> --max-bytes 4096
ud-dw-user-events replay --limit 20
ud-dw-user-events health
ud-dw-user-events purge --policy <file> --confirm
```

Default bounded JSONL/table includes id, sequence, endpoint, time, digest, state,
application reference, payload size, and safely quoted/truncated preview.
Truncation includes original length/digest. Exact bytes require explicit bounded
`show`; no LLM tails raw DB/log pages. Commands return stable machine-readable
exit codes and never mutate domain files except explicit `replay`/`purge`.

## Retention and scripted purge

Purge is an operator script with dry-run, explicit policy file, typed confirmation,
exclusive maintenance lock, and durable report. For the **active primary SQLite
store only**, it replaces eligible payload rows with tombstones, commits, performs
and verifies WAL checkpoint/truncate, rebuilds/vacuums to a fresh database where
required for page-level erasure, fsyncs database and parent, then verifies exact
bytes are absent from active DB/WAL. PostgreSQL reports the primary/replica scope
its adapter can actually verify. Tombstones retain receipt id/sequence, UUID
digest (not raw UUID when prohibited), request digest, endpoint, times, final
state, application reference, reason, policy/version/operator.

Purge never edits Markdown effects and never runs autonomously. Pre-existing
backups, filesystem snapshots, media remnants, replicas outside the verified
adapter scope, exported logs, and offline browser IndexedDB are **residual copies**,
not falsely declared erased. Each has a separate expiry/deletion workflow and is
listed in the purge report. Online project browser stores receive a signed/local
purge generation and delete eligible attempts on next connection; offline stores
remain residual until verified.

## Migration and cutover

Cutover is versioned and quiesced; old and new direct writers never overlap:

1. Back up/verify schema inputs, create journal/schema/version and gitignore
   entries. Do not import historical `submissions.log` as authoritative receipts;
   rows remain legacy witnesses with unknown application status.
2. Acquire an exclusive target cutover lease. Stop/refuse legacy write routes,
   drain in-flight HTTP requests, application claims, and coordinator mutations,
   and prove no old process still owns the target generation.
3. Install `DomainFileStore` as the sole supported writer, then atomically write an
   immutable cutover event/watermark and target protocol version.
4. Start journal-first routes. New writes commit receipt first and best-effort
   shadow second. Recovery/replay consume journal only.
5. Mixed-version servers fail closed before accepting writes. A request spanning
   the cutover either finishes entirely under the old drained generation or is
   retried by its durable browser attempt under the new generation.
6. After a release window, stop shadow writes. Rollback must be journal-aware and
   continue using `DomainFileStore`; restoring a legacy direct writer is forbidden.
   Rollback never deletes/renumbers receipts.

## Failure semantics

- Journal open/transaction/fsync failure: no `202`; client attempt remains.
- Busy timeout: retriable 503; no receipt unless receive transaction committed.
- Shadow failure: still `202`; health reports `shadow_failed`.
- JSON/schema/domain validation error after a registered complete envelope:
  `received -> rejected` without claim, with bounded stable reason/status URL.
- Transient domain I/O: `retryable`; preserve exact receipt and claim history.
- Ambiguous/torn domain: `recovering`; no mutation until operator resolves.
- Consumer crash: lease expiry + ternary proof; never “start from latest time.”
- Corrupt journal: fail closed, preserve files, health explains recovery path;
  never silently recreate over the only authority.

## Red-first acceptance fixtures

1. authority/unknown route/bad framing/interrupted/over-limit => no receipt;
2. registered malformed JSON and schema/domain-invalid JSON => `202`, stable
   receipt/status URL, then durable rejected; retry preserves identity/status;
3. journal fsync failure => no `202`, attempt retained;
4. crash after commit before response => retry UUID returns one receipt;
5. shadow `OSError` => `202`, durable receipt, visible health;
6. concurrent same UUID/same digest across two servers => one receipt;
7. same UUID/different bytes => `409`; new UUID/same bytes => distinct receipts;
8. length framing, method/media case/parameters cannot create digest ambiguity;
9. crash after `applying` before domain write => NotApplied, one effect;
10. crash after domain fsync before finish => file generation is exactly reserved
    before+1, digest+receipt+adapter+application reference match started intent,
    therefore Applied, finish only, one effect; a syntactically valid forged
    next-generation/marker with any predicate mismatch => Unknown;
11. torn domain / false-negative => Unknown, no second effect;
12. dual reclaimer and stale claimant => one CAS winner/effect;
13. two processes concurrently answer/comment/fold, stale-preimage retry, and
    crash at rename preserve both mutations/markers; Open->Answered fold during
    reclaim still proves one effect;
14. after marker commit, an external editor writes a syntactically valid file
    that removes/changes marker or body without a known successor generation =>
    `Unknown`/recovering and no duplicate; explicit rebaseline journals a new
    lineage successor before later application;
15. mutate/delete a low-ordinal transition with unchanged high water => chain
    verification fails and full rebuild occurs;
16. answer/ask/comment/command/tint each replay through its own adapter;
17. cross-tab draft conflict and newer draft survives older receipt;
18. active-store purge verifies DB/WAL erasure+tombstone and explicitly reports
    an unchanged pre-existing backup/offline browser export as residual;
19. real SQLite and PostgreSQL multi-client contract suites prove UUID uniqueness,
    revision/lease CAS, server-clock expiry, and retry exhaustion;
20. two server versions plus a request spanning quiesced cutover cannot produce a
    legacy direct write or lost/duplicate receipt.

Every new check must first be red against the pre-implementation behavior. Crash
fixtures kill at named seams rather than mocking away durability.

## Modules and ownership

- `user_events/journal.py`: backend-neutral records/service and state laws.
- `user_events/sqlite.py`: SQLite implementation and migrations.
- `user_events/apply.py`: registry, lease executor, ternary reconciliation.
  (**This design said `application.py`; the built module is `apply.py`.** Lane D's brief
  named `apply.py` and the lane correctly followed the brief as operative, then flagged
  the divergence. Renamed here rather than in code, because the code is what imports
  resolve against and a doc is what drifts. Landed `6cd9f95`.)
- `user_events/domain_files.py`: mandatory cross-process lock, parse/preimage,
  atomic durable replace; sole supported writer after version-gated cutover.
- endpoint adapters: only their own domain format and marker/search scope.
- `ud-dw-user-events`: bounded operator/LLM projection and explicit replay/purge.
- browser `DraftStore`/`AttemptStore`: IndexedDB only; no server authority.
- `watch.py`: validate/receive/respond/wake; no embedded queue or SQL policy.

The exact filenames are implementation-plan choices; these boundaries are design
requirements. Topic chats may later register an adapter but cannot introduce a
second receipt queue.

## Approval gate

Approval accepts this contract and authorises a separate red-first implementation
plan. It does not authorise implementation, migration, deployment, PostgreSQL
operation, topic chats, or payload purge. Amendments must name the section/law
being changed.

--- SUMMARY ---

- One durable receipt journal replaces timestamp guesses and competing witnesses.
- SQLite ships behind a behavioral adapter that a later PostgreSQL backend shares.
- `202` follows journal commit; UUID+digest makes retries idempotent.
- Client drafts/attempts survive before receipt but never impersonate reception.
- Leases/CAS plus ternary domain proof close the mutation-before-finish crash gap.
- Cursor replay is bounded and time-independent; CLI projections protect context.
- Purge is explicit scripted operator work retaining tombstones and audit.
- Red crash/concurrency/migration fixtures gate implementation after approval.
