# Findings — #519: audit the do-now exactly-once path (wake AND drain)

**Lane:** `lane-519audit` (audit; owns no production file). **Scope:** when the
coordinator processes a do-now that BOTH woke at POST (a `command via watch` line
in `.dreamwork/watch-events.log`) AND has its receipt pending in the journal
cursor, is the SAME instruction acted on twice? And conversely, is there a path
where acting on the wake-line leaves the receipt unconsumed forever (a
permanently-growing pending list)? The premise under audit (brief, drawn from
delivery-modes.md §"How an agent consumes the cursor in batched mode",
`delivery-modes.md:168-170`): *the tick's cursor drain replays receipts through
`apply.py`'s adapters, and `apply.prove_applied` is exactly-once, so a replay of
an already-applied receipt is a no-op — that is why batched mode cannot
double-deliver.*

**Method:** static, read-only. Read `user_events/apply.py` (the proof and the
adapters), `dev/journal_consume.py` (the actual drain CLI), `SKILL.md`'s tick
habit and command handling, and `watch.py`'s `_handle_command` / `do_POST` E3
cutover / wake routing. Completeness cross-checks:
`grep -rn "import apply\|from user_events.apply" *.py **/*.py` (who wires the
proof) and `grep -rn "reconcile\|adapter_for\|\.prove(\|apply\." *.py` (who
calls it). No server was started; no POST was made; no port was bound.

10→---

## Verdicts (headline)

| path | verdict | where it bites |
|---|---|---|
| **double-act** — same do-now acted on via the wake-line AND the cursor drain | **VIOLATION** | batched mode: a do-now pre-empts by wake-line (`emits_wake`→True) AND drains on the tick; the two channels share no id and the proof that is supposed to make the drain a no-op is not wired |
| **never-consumed / leak** — acting on the wake-line leaves the receipt unconsumed forever | **VIOLATION** | instant mode (the **default**): every `/command` receipt journals (E3) but the drain is instructed only for `delivery: batched`, so the coordinator cursor never advances and `(cursor, head]` grows without bound |

**Counts:** VIOLATION **2** · COMPLIANT **0** · UNCLEAR **0** for the two required
path verdicts. Two further doc/code defects (F3, F4) are the root enablers and
are recorded below. The design's stated exactly-once mechanism
(`apply.prove_applied`) is defined and red-proven in lane D but **never invoked by
any production path** (F4) — that single fact is why neither path holds.

---

## How the exactly-once question is implemented (the seam)

A do-now travels through TWO independent delivery channels, and the question is
whether anything reconciles them:

- **Channel A — the wake-line (the interrupt).** `_handle_command`
  (`watch.py:14341`) emits one line to `.dreamwork/watch-events.log` whenever
  `emits_wake(kind, target)` is true (`watch.py:14360-14362`). For a do-now it is
  *always* true: `emits_wake` returns `True` for any kind in `PREEMPT_KINDS =
  ("do-now","do-next")` regardless of delivery mode (`watch.py:13406`,
  `watch.py:13426`). The line is built by `command_line(kind, text, source)`
  (`watch.py:13690-13694`) as `command via watch{from}: do-now: <text>` — it
  carries the kind and the one-line text, and **no receipt id**. The tail Monitor
  fires on the append; the coordinator reads the file by mtime
  (`SKILL.md:117`). There is no durable reader offset for this file — "session
  memory of the offset is exactly what compaction destroys"
  (`delivery-modes.md:54-62`).

- **Channel B — the cursor drain (the durable record).** The same POST also
  commits a receipt *before* dispatch: `/command` is a registered write route
  (`WRITE_ROUTE_HANDLERS["/command"]`, `watch.py:14544`), and the E3 cutover
  commits the receipt in `do_POST` before the handler runs
  (`watch.py:14148-14150`; the envelope carries `route=self.path`,
  `body=self._body` — the raw `{kind,text}` JSON — `watch.py:13776-13782`). On a
  tick the coordinator drains `(coordinator_cursor, head]` with
  `dev/journal_consume.py`: `pending` lists the `receipt.created` events
  (`journal_consume.py:138-151`), the coordinator "process[es] each event — act
  on it, file it as a task, or fold it" (`SKILL.md:182-183`), then `consume`
  read-then-advances the cursor (`journal_consume.py:155-198`).

- **The reconciliation the design names (and the seam this audit breaks on).**
  delivery-modes.md act 2 of the batched consume says the drained events "route
  to their adapters (`apply.py`'s `reconcile` / the per-route
  `ApplicationAdapter` registry)... The proof machinery (`apply.prove_applied`)
  is exactly-once, so a batched replay of an already-applied receipt is a no-op —
  *that* is why batched mode cannot double-deliver" (`delivery-modes.md:168-170`).
  `apply.py` realises this: `reconcile` reads the target file, runs the ternary
  `prove_applied` (`apply.py:184-249`), and on `Proof.APPLIED` calls `finish()`
  only — **no second write** (`apply.py:318-321`); a `/command` adapter is even
  registered (`apply.py:419`, `_install_default_adapters`). **But `apply` is
  imported by no production module** — only `test_user_events_apply.py:34` and
  `test_user_events_domain_files.py:372`. The drain itself, `dev/journal_consume.py`,
  imports only `from user_events.sqlite import open_journal` (`journal_consume.py:75`)
  and `cmd_consume` calls exactly two journal methods — `events_since_cursor` then
  `advance_cursor` (`journal_consume.py:168-181`); it never imports or calls
  `apply.reconcile` / `prove_applied` / `adapter_for`. The proof machinery is
  dead code from a production standpoint. So the mechanism delivery-modes.md leans
  on to make the replay a no-op does not exist in the code path that actually runs.

The result is two delivery channels for one instruction, joined by nothing: the
wake-line has no cursor (no reader offset survives compaction) and no receipt id
(`command_line:13690-1394`), and the drain has no proof (it lists ids and
advances, full stop). Neither channel knows the other fired.

---

## Findings (severity first)

### F1 — VIOLATION (HIGH): the double-act path — a do-now that both woke and drained can be acted on twice

Under `delivery: batched`, a do-now is delivered through BOTH channels on the same
tick window:

1. It pre-empts: `emits_wake("do-now", target) → True` unconditionally
   (`watch.py:13426`), so `_handle_command` appends `command via watch: do-now: X`
   (`watch.py:14360-14362`). The coordinator reads watch-events.log by mtime
   (`SKILL.md:117`) and, per the `do now` command contract, parks the current
   increment and works it immediately (`SKILL.md:657-659`). **Act 1.**
2. Its receipt is also in the journal (E3, `watch.py:14148`). The tick drains it:
   `pending` lists it (`journal_consume.py:138-151`) and the tick habit says to
   "process each event — act on it, file it as a task" (`SKILL.md:182-183`).
   **Act 2** — the same instruction `X`, reached a second time through the cursor.

Nothing reconciles the two. The wake-line carries no receipt id
(`command_line:13690-1394`), so the coordinator cannot match the drained receipt
to the line it already acted on. SKILL.md gives no "skip events already handled
by a wake-line" rule. And the design's stated guard for exactly this case —
`prove_applied` making the drain a no-op (`delivery-modes.md:168-170`) — is not
wired (seam above): `consume` lists ids and advances the cursor; it does not
prove, and the `/command` adapter that `apply.py:419` registers is never invoked.

**Why this is a path, not a hypothesis.** The double-*delivery* is unconditional
in batched mode: the wake-line fires for every do-now (`watch.py:13426`) and the
receipt is in every drain (`journal_consume.py` lists all `receipt.created` in
`(cursor, head]`). What is runtime-dependent is the double-*act* — whether a given
coordinator run recognises `X` as already-handled. The design's own argument is
that safety must NOT rest on that recognition: it rests on the proof
(`delivery-modes.md:168-170`), and "session memory of the offset is exactly what
compaction destroys" (`delivery-modes.md:54-62`). The proof is absent, so the
property does not hold by construction. A do-now that wakes on tick N and drains
on tick N+1 (after a compaction, or simply because the wake fired before the tick
that drains) has nothing preventing the second act; the cursor advance at
`consume` only stops a *third* listing, not the second.

**Consequence of a double-act.** "Acting on a do-now" is parking the current
increment, minting the task as `in_progress`, and working it (`SKILL.md:657-659`).
A second act mints a duplicate task (or re-parks an already-parked increment) — a
concrete ledger/queue effect, not a no-op.

### F2 — VIOLATION (MEDIUM): the leak path — instant mode (the default) journals every command but never drains, so the pending list grows forever

`DELIVERY_DEFAULT = "instant"` (`watch.py:13386`); an absent `delivery` axis
reads as instant (`delivery_mode`, `watch.py:13409-13412`). In instant mode the
E3 cutover still commits a receipt for every `/command` POST — the receipt
commits "BEFORE the handler dispatches" for every registered write route
(`watch.py:14148-14150`) and "instant mode only adds the wake line on top; it
never replaces the durable receipt" (`delivery-modes.md:86-89`). **But the cursor
drain is instructed only for batched mode:** the whole tick-habit block opens
"**Batched delivery drains the journal on the tick**... When the delivery axis is
`batched`... The tick habit is `pending → process → consume`"
(`SKILL.md:171-176`). There is no instruction to drain in instant mode.

So in the default mode the coordinator acts on wake-lines (Channel A) while
Channel B's receipts pile up with the coordinator cursor unmoved. `(cursor, head]`
grows without bound — exactly the "permanently-growing pending list" the brief
asks about. Two consequences:

- **The design's central "nothing forgotten" guarantee is broken in its default
  mode.** delivery-modes.md promises "Low-urgency items are guaranteed processed
  in *instant* mode because the cursor read is part of the tick, not part of the
  wake... the tick's cursor read drains it whether or not the monitor fired"
  (`delivery-modes.md:218-226`). In the code as instructed, the cursor read does
  NOT run in instant mode, so a wake-line missed because the monitor is off
  (resumed session, compacted session, `watch.py` started after init —
  `SKILL.md:119-122`) is forgotten, AND its receipt stays unconsumed. The wake
  was supposed to become "an optimisation, not the delivery path"
  (`delivery-modes.md:222-226`); in instant mode it is still the only path.
- **A mode switch mass-replays.** When the posture flips instant→batched, the
  first `pending` lists every receipt since the journal was created (the cursor
  never advanced). That is a mass replay of every previously-instant item — and,
  per F1, with no proof wired, a mass double-act surface for any of them that was
  already handled by its wake-line.

### F3 — defect (MEDIUM, enabler): SKILL.md's command-channel paragraph is stale post-E3, and it is the doc root of both F1 and F2

`SKILL.md:117-122` states a command "exists **only** as a line in that file —
nothing is written anywhere else." That was true pre-E3; it is false now: every
`/command` receipt is also journaled (`watch.py:14148`). This stale text is the
double-act's enabler — it tells the coordinator the wake-line is the *only*
record of a command, so there is nothing to reconcile the cursor drain against,
and no reason to expect the same instruction to arrive a second time. It is also
the leak's enabler: it frames the command channel as wake-only, which is why the
drain was never extended to instant mode (the doc says the command rides the
wake-line alone, so draining it would seem redundant). delivery-modes.md itself
quotes this exact line as the *pre-journal* failure mode it set out to fix
(`delivery-modes.md:54-62`); the SKILL.md paragraph was not updated when E3
landed, so the two docs now disagree about whether a command is durable.

### F4 — defect (HIGH, root cause): the exactly-once proof is defined, red-proven, and never called in production

`apply.prove_applied` (`apply.py:184`), `reconcile` (`apply.py:274`), the
`ApplicationAdapter` registry and the `/command` adapter (`apply.py:355-425`) are
the mechanism delivery-modes.md names as the reason "batched mode cannot
double-deliver" (`delivery-modes.md:168-170`). They are exercised only by
`test_user_events_apply.py` and `test_user_events_domain_files.py`. No production
module imports `apply` (`watch.py` imports only `from user_events.sqlite import
Envelope, open_journal`, `watch.py:36`; `dev/journal_consume.py` imports only
`open_journal`, `journal_consume.py:75`). The drain's `consume` is a two-act
read-then-advance (`journal_consume.py:168-181`); the design's three-act consume
— read, **verify+replay through adapters**, advance (`delivery-modes.md:162-180`)
— is missing its middle act in the code that runs. This is the single load-bearing
fact behind F1: if the proof were wired, a replayed do-now receipt would prove
`APPLIED` and finish only (`apply.py:318-321`); because it is not, the drain has
no idea whether a receipt was already acted on.

---

## What I COULD NOT determine (static, read-only)

- **Whether a coordinator actually acts twice on a given do-now.** I proved the
  double-*delivery* is unconditional in batched mode (wake-line always fires for
  pre-empt kinds + the receipt always drains) and that the reconciliation
  mechanism is absent. The double-*act* — the coordinator recognising or failing
  to recognise the duplicate — is prose/runtime behaviour, not code. Runtime
  evidence that would settle it: a tick transcript where a single do-now is filed
  as a task twice, or consumed without the coordinator noting it was already
  worked from the wake-line. The risk concentrates where the wake fires on tick N
  and the drain runs on tick N+1 (post-compaction, or a wake that lands between
  ticks), because there the coordinator has no in-context memory of act 1.
- **Whether the loop in fact runs instant-mode-without-draining.** Instant is the
  default (`watch.py:13386`) and SKILL.md gates the drain on batched
  (`SKILL.md:171`), so a loop with no `delivery:` posture line should leak by the
  code-as-instructed. I did not measure a live cursor's `head_ordinal −
  scanned_through_event_ordinal` over time; that would confirm or refute F2
  empirically. (Note: `dev/ledger.py`'s warning footer now reports
  `journal unconsumed receipts` as `head_ordinal − coordinator cursor` — folded
  #357 — so the leak, if present, is already observable there.)
- **Whether the `consume`-blind loss mode interacts with either path.** `consume`
  prints receipt ids, not content, and advances the cursor regardless of whether
  the coordinator read the payload (`journal_consume.py:190-191`; the documented
  #513 loss, `SKILL.md:187-191`). That is a *third* failure (silent content loss),
  not the double-act or the leak; I note it because it shares the same root
  (consume advances on ids alone, with no proof and no content gate), but it is
  out of scope for the two paths this audit was asked to settle.

---

## Proposed follow-up tasks (titles for the coordinator to file verbatim)

1. **#520 — Wire the exactly-once proof into the cursor drain, or restate batched mode's exactly-once basis honestly** (either route drained receipts through `apply.reconcile`/`prove_applied` so a replay proves `APPLIED` and finishes only, as delivery-modes.md:168-170 already claims; or, if the prose-coordinator model is intended, delete the doc's claim that `prove_applied` governs the replay and state the actual basis — then prove THAT basis holds under compaction).
2. **#521 — Reconcile the wake-line against the cursor so a do-now that both woke and drained is acted on once** (e.g. carry the receipt id in `command_line` so the coordinator can match a drained receipt to a wake-line it already acted on; or have the drain skip/finish pre-empt-kind receipts whose wake-line already delivered; or give `watch-events.log` a durable offset so the wake-line itself is idempotent across compaction).
3. **#522 — Drain the cursor on every tick regardless of delivery mode** so instant mode (the default) does not leave a permanently-growing pending list and an instant→batched switch does not mass-replay (honour delivery-modes.md:218-226's "cursor read is part of the tick" guarantee; today SKILL.md:171 gates the drain on `delivery: batched` only).
4. **#523 — Fix the stale SKILL.md command-channel paragraph** (`SKILL.md:117-122`: a command no longer "exists only as a line in that file" — E3 journals every `/command` receipt) so the two docs agree a command is durable and the coordinator has a reason to expect/reconcile the second delivery.

---

## Contradictions with delivery-modes.md

The ruling (do-now/do-next pre-empt; the ambiguous class batches) is sound and
the wake routing for it is landed (the #514 audit confirmed the four content
gates). What this audit finds contradicts the doc is the **exactly-once claim the
ruling's batched half rests on**:

- **The doc's act-2 ("replay through adapters") is not implemented.**
  delivery-modes.md describes the batched consume as three acts — read,
  verify+route-to-adapters (`apply.reconcile`), advance
  (`delivery-modes.md:162-180`) — and asserts the adapter proof "is exactly-once,
  so a batched replay of an already-applied receipt is a no-op — *that* is why
  batched mode cannot double-deliver" (`delivery-modes.md:168-170`). The code that
  runs (`dev/journal_consume.py consume`) is two acts — read, advance
  (`journal_consume.py:168-181`) — with no adapter and no proof. The
  `/command` adapter `apply.py:419` registers is never called. The doc's central
  safety argument is aspirational, not built.
- **The doc's "cursor read on every tick" guarantee is contradicted by SKILL.md.**
  delivery-modes.md:218-226 promises the cursor read runs on every tick in BOTH
  modes (so a missed wake is still drained). SKILL.md:171-176 instructs the drain
  only for `delivery: batched`. In instant mode (the default) the guarantee is
  unrealised and the pending list leaks (F2).
- **The doc and SKILL.md disagree on whether a command is durable.**
  delivery-modes.md:54-62 (correctly, post-E3) treats the command receipt as the
  durable half; SKILL.md:117-122 (stale, pre-E3) still says a command "exists
  only as a line in that file." F3.

These are defects to close (proposed follow-ups #520–#523). The wake routing and
the cursor/CAS machinery themselves are correctly built; the gap is the join
between the two channels and the proof that was supposed to sit on the drain.
