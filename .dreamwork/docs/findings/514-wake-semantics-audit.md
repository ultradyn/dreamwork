# Findings — #514: audit wake semantics under batched delivery

**Lane:** `lane-514wake` (audit; owns no production file). **Scope:** does every
wake line that CAN fire under `delivery: batched` match the #342 ruling? The
ruling (`.dreamwork/docs/plans/delivery-modes.md`): *do-now/do-next pre-empt even
in batched mode; every other kind — add-idea, maintenance, plugin kinds, and the
`/answer`, `/comment`, `/ask` routes — wake only in instant mode, riding the
durable receipt + the tick's cursor read.* Every append to
`.dreamwork/watch-events.log` is a wake (the loop's tail Monitor fires on a line).

**Method:** static, read-only. Every `log_event` call site in `watch.py` was read
(13 sites) plus the one raw append outside it. Completeness cross-check:
`grep -rn "watch-events" watch.py dreamhub.py dev/ user_events/` — every hit is
either a writer in the table below, a reader (the `dev/capture/*.mjs` guards), a
comment/docstring, or a test. No server was started; no POST was made.

---

## How the wake decision is implemented (the seam)

- `log_event(target, line)` (`watch.py:13451`) is the **single append function**;
  it is the only place that opens `watch-events.log` in append mode
  (`watch.py:13459`). Every wake goes through it.
- `delivery_mode(target)` (`watch.py:13398`) reads `.dreamwork/posture` **fresh
  per call** via `read_posture_file` — no cache, so a stale read within one event
  is not possible (same per-tick re-read contract as pace/asking). Absent axis →
  `DELIVERY_DEFAULT = "instant"` (`watch.py:13375`).
- `emits_wake(kind, target)` (`watch.py:13403`) is the per-kind gate:
  `kind in PREEMPT_KINDS` (`("do-now","do-next")`, `watch.py:13388`) → always wake;
  else wake only when `delivery_mode == "instant"`. This is the #342 routing,
  and it IS landed (the doc framed it as a future increment; the code is in).

**The receipt itself never wakes.** `do_POST` (`watch.py:14060`) commits the
receipt via `self._journal_receive` (`watch.py:13747`) → `_journal_receive`
(`watch.py:13498`) → `journal.receive`. That path calls `log_event` **only on an
exception** (`watch.py:13511`). On the success path there is no per-receipt wake
line — the wake is decided later, per-route, in each `_handle_*`. This matches
delivery-modes.md ("the receipt always commits; the wake line is the interrupt").

---

## Writers table

`wake under batched?` answers: would this line fire while `delivery: batched` is
live? `mode-aware?` answers: does the emit branch on `delivery_mode`/`emits_wake`?

| # | file:function | route / command | event class | wake under batched? | mode-aware? | verdict |
|---|---|---|---|---|---|---|
| 1 | `watch.py:_handle_command` (`14350`) | `POST /command` (`kind`) | command — `do-now`/`do-next`/`add-idea`/`maintenance`/plugin | do-now & do-next **YES** (pre-empt); every other kind **NO** (instant-only) | **YES** — `emits_wake(kind, target)` at `14350` | **COMPLIANT** |
| 2 | `watch.py:_handle_answer` (`14224`) | `POST /answer` | his answer (ambiguous → batched) | **NO** (instant-only) | **YES** — `emits_wake("/answer", target)` at `14223` | **COMPLIANT** |
| 3 | `watch.py:_handle_ask` (`14189`) | `POST /ask` | his question for the dreamer (batched) | **NO** (instant-only) | **YES** — `emits_wake("/ask", target)` at `14188` | **COMPLIANT** |
| 4 | `watch.py:_handle_comment` (`14260`) | `POST /comment` | follow-up note (batched) | **NO** (instant-only) | **YES** — `emits_wake("/comment", target)` at `14260` | **COMPLIANT** |
| 5 | `watch.py:_handle_decide` (`14321`) | `POST /decide` | review decision (content) | **YES — unconditional** | **NO** | **VIOLATION** |
| 6 | `watch.py:track_question_updates` (`12902`) | (none — runs in `collect()` on poll) | question content-drift signal | **YES — unconditional** | **NO** | **VIOLATION** |
| 7 | `watch.py:_handle_run_mode` (`14404`) | `POST /run-mode` | control-plane (run-mode change) | **YES — on real change** | **NO** | **UNCLEAR** |
| 8 | `watch.py:_handle_posture` (posture line, `14482`) | `POST /posture` | control-plane (pace/asking/delegation) | **YES — on real change** | **NO** | **UNCLEAR** |
| 9 | `watch.py:_handle_posture` (delivery line, `14486`) | `POST /posture` | control-plane (delivery toggle) | **YES — on real change** | **NO** | **UNCLEAR** |
| 10 | `watch.py:_journal_receive` (`13511`) | (journal commit) | error diagnostic | **YES — exception only** | **NO** | **UNCLEAR** |
| 11 | `watch.py:_journal_record_health` (`13526`) | (health record) | error diagnostic | **YES — exception only** | **NO** | **UNCLEAR** |
| 12 | `watch.py:_journal_reject` (`13548`) | (reject record) | error diagnostic | **YES — exception only** | **NO** | **UNCLEAR** |
| 13 | `ud-dw-tasks-migrate` (`1413`) | CLI cutover (`ud-dw-tasks-migrate`) | operational migration | **YES — one-shot** | **NO** | **UNCLEAR** |

**Verdict counts:** COMPLIANT **4** · VIOLATION **2** · UNCLEAR **7**.

**Verified non-wakers (completeness):** `_handle_tint` (deliberately no line —
`watch.py:14358`, presentation state); `_handle_deploy` (no `log_event` call —
restarts the server); `dreamhub.py` (zero `watch-events`/`log_event` references);
every `dev/*.py` (none reference the events file); every `dev/capture/*.mjs`
guard (all read the file via `readFileSync` — posture/qsignal/runmode/rundesc read
`logPath`/`eventsFile`; plugcmd reads; dismiss does a GET via `/file`; **none
append**); `user_events/` (zero `watch-events` references); `dev/journal_consume.py`
`pending`/`consume` (the drain — confirmed silent, see Finding 7); and the
`do_POST` receipt commit (no per-receipt wake on the success path).

---

## Findings (severity first)

### F1 — VIOLATION (HIGH): `/decide` wakes unconditionally; the #342 gate missed it

`_handle_decide` (`watch.py:14264`) records a review decision into the ledger
store. It is a **registered write route** (`WRITE_ROUTE_HANDLERS["/decide"]`,
`watch.py:14531`) and so journals a receipt via the E3 cutover (`do_POST` commits
before dispatch, `watch.py:14134`). But its wake is emitted with no mode branch:

```python
# watch.py:14321-14324  (_handle_decide)
            log_event(target,
                      f'review-decision{from_hint(req.get("from"))}: '
                      f'"{one_line(artifact)}" {decision} for '
                      f'"{one_line(question_title)}" -> .dreamwork/ledger.sqlite3')
```

There is no `if emits_wake(...)` guard, unlike the four content routes it sits
between (`_handle_comment` at `14260`, `_handle_command` at `14350`). A review
decision is content — it is the same family as the batched-class `/answer` and
`/comment` (a human acting on a review). Under `delivery: batched` a `/decide`
fires a wake line every time, which is exactly the behaviour the toggle exists to
suppress for this class. This silently undoes batched mode for the `/decide` route.

**Why the doc missed it:** delivery-modes.md §"What changes in watch.py's command
handlers" enumerates the routes to gate as `_handle_answer`/`_handle_ask`/
`_handle_comment`/`_handle_command` (four routes). `/decide` was added by #289 and
is not in that list; the doc's "one decision point per write route" was realised
for four of the nine `WRITE_ROUTE_HANDLERS`.

### F2 — VIOLATION (MEDIUM): `question-updated` wakes on every digest change, ungated and unjournaled

`track_question_updates` (`watch.py:12860`) runs inside `collect()` on every
dashboard poll. When a question entry's content digest changes it writes one
`question-updated via watch: …` line, unconditionally:

```python
# watch.py:12902-12908  (track_question_updates)
            log_event(
                target,
                "question-updated via watch: "
                + one_line((e.get("title") or "")[:100]),
            )
```

No `emits_wake` / `delivery_mode` branch. This is a content-adjacent signal on the
question surface (the class delivery-modes batches) yet it (a) ignores delivery
mode and (b) bypasses the journal/cursor entirely — it is a digest computed in
`collect()`, not a receipt. In batched mode every question-content edit by the
dreamer still wakes the loop immediately through this legacy channel, which is the
"interrupt the loop on a batched-class item" the ruling forbids. Whether this
should be mode-gated or explicitly carved out as an always-instant sync signal is
a policy call (see proposed follow-up); the implementation currently does neither.

### F3 — UNCLEAR (LOW): control-plane wakes (`/run-mode`, `/posture`) are unconditional

`_handle_run_mode` (`watch.py:14404`), and `_handle_posture` for both the posture
triple (`watch.py:14482`) and the delivery axis (`watch.py:14486`), each call
`log_event` on a real change with no mode branch. These are **control/meta**
events — the human reconfiguring how the loop runs — not content inputs, so they
fall outside the per-kind table. There is a strong argument they SHOULD always be
instant (a `delivery` toggle that does not wake the loop until its next tick
defeats the toggle), but **delivery-modes.md is silent on control-plane wakes**;
the code's always-instant behaviour is an unstated choice. Not a batched-mode
violation for content, but a doc gap and an unannotated decision.

### F4 — UNCLEAR (LOW): journal failure-path wakes fire unconditionally

`_journal_receive` (`watch.py:13511`), `_journal_record_health` (`watch.py:13526`),
and `_journal_reject` (`watch.py:13548`) each call `log_event`, but **only inside
an `except`** — i.e. only when the journal open/receive/record itself failed. In
batched mode these wake the loop on a journal fault. An error diagnostic arguably
should always be loud (a receipt-commit failure means inputs may not be durable),
so this is plausibly correct-by-design; it is flagged only because the wake is not
mode-aware and the class is not stated in the ruling.

### F5 — UNCLEAR (LOW): the tasks-cutover migration appends a wake line, ungated

`ud-dw-tasks-migrate` step 6 (`ud-dw-tasks-migrate:1409-1414`) appends one
`ledger-cutover …` line to `watch-events.log` with no mode awareness. This is a
one-shot operational CLI event, not a user dashboard route, and is outside
delivery-modes.md's scope. Flagged for completeness; unlikely to matter under
batched mode.

---

## What I COULD NOT determine (static, read-only)

- **Coordinator tick reconciliation of wake-line vs cursor-drain for a do-now.**
  A do-now wakes at POST time via `emits_wake("do-now")→True` (Finding 7 confirms
  the drain is silent). But the do-now's receipt is ALSO in the journal, so the
  tick's cursor drain (`dev/journal_consume.py consume`) will re-list it.
  delivery-modes.md relies on the adapters' exactly-once proof (`apply.prove_applied`)
  to make the replay a no-op. **Whether the coordinator's tick actually invokes
  that proof, and whether it reconciles the `command via watch` wake line against
  the drained receipt, lives in the loop's tick logic — not in `watch.py`.** I did
  not trace it; an audit of the coordinator's consume-of-`pending`/`consume` step
  is needed to confirm no double-act on a do-now that both woke and drained.
- **Frequency of `question-updated` in practice** (F2): it is one wake per
  question-content-change, not per poll, but I could not measure how often the
  dreamer edits `questions.md` between ticks — that determines F2's real noise
  cost. The policy question (gate it, or mark it an always-instant sync signal)
  stands regardless.
- **Whether control-plane wakes (F3) are intentionally exempt.** The code is
  consistent (always-instant) and the 10s arm throttles them, but there is no
  comment or doc line stating the carve-out, so intent is inferred, not shown.

---

## Proposed follow-up tasks (titles for the coordinator to file verbatim)

1. **#515 — Gate `/decide` behind `emits_wake` so a review decision rides the batched cursor like `/answer` and `/comment`** (red-first: assert a `/decide` under `delivery: batched` writes no `watch-events.log` line while still committing the receipt).
2. **#516 — Rule and implement the `question-updated` wake policy under batched delivery** (either mode-gate `track_question_updates` at `watch.py:12902`, or explicitly declare it an always-instant sync signal and document why — and state whether it should be journaled).
3. **#517 — Document control-plane wakes (`/run-mode`, `/posture` triple + delivery) in delivery-modes.md** as an explicit always-instant carve-out (or a mode-aware decision), and add the matching code comment at each emit site.
4. **#518 — Reconcile delivery-modes.md's route enumeration with `WRITE_ROUTE_HANDLERS`** (the doc lists 4 of 9 write routes; cover `/decide` and the control routes so the "one decision point per write route" claim is complete and auditable).
5. **#519 — Audit the coordinator tick's reconciliation of wake-line vs cursor-drain for pre-empt kinds** (confirm a do-now that both woke at POST and drained on the tick is acted on exactly once via `apply.prove_applied`, not twice).

---

## Contradictions with delivery-modes.md itself

No contradiction of the **ruling** (do-now/do-next pre-empt; ambiguous class
batches). The implemented gates for the four covered routes are consistent with
it. What the doc gets wrong is **completeness vs the implemented reality**:

- **The doc's route list is stale.** §"What changes in watch.py's command handlers"
  names `_handle_answer`/`_handle_ask`/`_handle_comment`/`_handle_command` as the
  routes to gate and asserts "one decision point per write route." `WRITE_ROUTE_HANDLERS`
  has **nine** routes (`watch.py:14528`). `/decide` is a content route with a
  journal receipt but **no** wake decision point (F1) — the doc's claim is not
  realised for it. `/tint` and `/deploy` are correctly non-waking by design; the
  control routes (`/run-mode`, `/posture`) wake unconditionally and are unaddressed.
- **The doc is silent on three live wake channels:** the `question-updated` digest
  signal (F2), the control-plane wakes (F3), and the journal failure-path wakes
  (F4). The ruling is framed entirely around user input kinds; it does not say
  what batched mode means for system/control/error wakes, so each defaults to
  today's always-instant behaviour with no stated policy.
- **The doc's "authorises no code / #342's next increment" framing is now
  historical.** The wake routing (`delivery_mode`, `emits_wake`, `PREEMPT_KINDS`,
  the four gates) is landed in `watch.py`. The doc should be updated to
  design-as-built and to name exactly which routes were gated (and which were
  missed) — otherwise the next reader believes the gating is still pending.

These are doc gaps to close (proposed follow-ups #517/#518), not defects in the
ruling. The ruling itself is sound and the four content routes that implement it
are correct.
