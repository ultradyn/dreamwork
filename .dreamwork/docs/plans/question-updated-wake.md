# question-updated wake policy under batched delivery (#516)

**Task #516** (P2), filed from the **#514** wake-semantics audit, finding **F2
(VIOLATION, MEDIUM)**: `track_question_updates` writes a `question-updated`
line to `watch-events.log` on every content-digest change — **ungated and
unjournaled**. This is the DESIGN half only (watch.py is owned for writes by
another lane); the deliverable is a ruling another lane implements cold.

Line numbers cite **HEAD `3b846c64`** (the brief commit). They were verified by
re-reading the cited region, not carried from the audit's snapshot.

## The four rulings (summary)

1. **Mode-gate it.** `question-updated` is a per-kind signal routed under the
   delivery mode, **not** an always-instant carve-out. In `instant` it fires as
   today; in `batched` it is suppressed. The mechanism is the existing
   `emits_wake` seam — one `if` around the `log_event` call at `watch.py:13513`.
2. **Not journaled — by construction, and correctly.** The durable record is
   `question-sigs.json` (the sig store) plus `questions.md` itself, both of
   which the loop re-reads every tick. The event is a lossy nudge; journaling it
   would create a second durable truth for content a file already holds.
3. **Name the swallow defect.** The #534 re-seed branch's early `return`
   (`watch.py:13491`) skips change detection, so a **real** content change that
   rides the same collect as an algorithm re-seed loses both its event and its
   `updated_at` stamp (the stamp carries the prior value). That is a defect to
   fix, not a behaviour to design around. Under ruling (1) its blast radius
   shrinks to a stale *display age* (the lost event is moot in batched mode); it
   is still worth fixing in the same increment.
4. **Policy row lives in `delivery-modes.md`.** It already has a "`question-updated`
   — policy pending under #516" stub; the implementation lane rewrites that stub
   to the ruled policy and adds the matching code guard. One doc place, one code
   seam.

## Two load-bearing facts, measured

**1 · The loop reads `questions.md` on every tick — the event is a nudge, not a
delivery path.** `SKILL.md:80-87` is the tick habit: *"If `questions.md` changed
since your last look, check for new human-authored blocks … fold them first."*
`collect()` (`watch.py:13547`) re-reads the file and re-stamps every entry's
`updated_at` from the sig store on **every dashboard poll** (`track_question_updates`
called at `watch.py:13560`). So the loop learns question content drift from the
file, not from the event. The event's only value is **timing** — waking the
coordinator between ticks to act one tick sooner. That is precisely the
instant-vs-batched distinction, which is precisely what the delivery-mode
routing exists to decide.

Who is the event FOR? It fires when the dashboard server notices a digest
change, which is almost always because **the coordinator or a lane just rewrote
`questions.md`** — the loop waking itself to announce its own edit. The only
non-circular case is an out-of-band human edit between ticks, and the next
tick's file read catches that regardless. So the event is, at best, a one-tick
latency saving on a content-adjacent signal.

**2 · The unguarded channel's cost is real and was measured: a 63-event storm.
** `watch-events.log` (live target, 2026-07-25 → 2026-07-30) holds **107**
`question-updated` lines. **63 of them** (59%) fire at a single timestamp,
`2026-07-30T09:43:31`, spanning entries dated across five different days
(`watch-events.log:302-364`). Sixty-three entries cannot all have genuinely
changed content in one second; that burst is the signature of a digest-**algorithm**
change — every stored (old-algo) digest differing from every recomputed
(new-algo) digest. The timeline confirms it exactly:

| time | event |
|---|---|
| 09:33:55 | **#509** merges (`feceeef9`): whitespace-normalised signature digest = an algorithm change |
| 09:43:31 | the **63-event phantom burst** — live store still held old-algo digests |
| 10:06:14 | 1 genuine change (#233 LAN binding) |
| 10:52:14 / 11:07:42 | **#534** commits / folds (`0a1a3f3f` / `8ed86e90`): silent re-seed |

So the burst is **pre-#534** — #534 is the fix for exactly this storm, and it
had not folded yet when #509's algorithm change hit the live store. #534 is now
on master and prevents the burst going forward. The 63-line storm is the
measured refutation of leaving this channel ungated (see Decision 1).

## Decision 1 — mode-gate (rule), not always-instant (refuted)

**Ruling: `question-updated` is a per-kind signal routed under the delivery
mode.** Apply the existing `emits_wake(kind, target)` gate
(`watch.py:14054`) to the emit site at `watch.py:13513`. `"question-updated"` is
not in `PREEMPT_KINDS` (`("do-now","do-next")`, `watch.py:14042`), so it behaves
exactly like the batched-class content routes: it wakes only in `instant` mode
(`delivery_mode(target) == DELIVERY_DEFAULT`, `watch.py:14045`).

Why this is right, in delivery-modes' own terms: the question surface **is** the
batched class (his Q1 ruling: answers/notes/questions batch as a whole). A
content-drift signal on that surface is content-adjacent, not a steer, so it has
no claim on the pre-empt set. And batched mode's definition is *"stop the
interrupts; the tick drains the state"* — for `questions.md`, the tick's file
read (`SKILL.md:80-87`) **is** the drain. Withholding the wake line is batching;
the content is still read on the next tick. Today (`delivery: batched` live in
`.dreamwork/posture`) every question-content edit still wakes the loop
immediately through this ungated legacy channel — which is the interrupt the
toggle exists to suppress.

**Refuted alternative — declare it an always-instant sync signal (carve-out),
like `/posture` and `/run-mode`.** A control-plane carve-out (`/posture`,
`/run-mode`) is justified because a toggle that does not wake until its next
tick *defeats the toggle*. `question-updated` has no such property: it is not a
steer, and its latency cost of one tick is exactly what batched mode buys for
the content class. The carve-out would also **preserve the measured failure
mode**: an unguarded always-instant question-content channel is what produced
the 63-event storm (`watch-events.log:302-364`). #534 closes the *algorithm*
cause of that storm; mode-gating closes the *policy* cause — a future signal
that fires per-entry on a content surface should never be exempt from the mode
that exists to throttle exactly that class.

## Decision 2 — not journaled, and that is correct by construction

**Ruling: do NOT journal `question-updated`.** The submissions journal (#263) is
the durable record a cursor drain consumes; `watch-events.log` is lossy
(`log_event` swallows `OSError`, `watch.py:14111-14112`; `file-formats.md:2103`
calls the event half *"a convenience and never a notification to rely on"*). A
signal that can matter after a restart needs journal durability — but this one
cannot lose anything, and the reason is structural, not a policy preference:

- **The sig store is the durable record of question content state.**
  `question-sigs.json` is written atomically (`_write_question_sigs`,
  `watch.py:13533`, tmp + `os.replace`), per-entry content digest + `updated_at`,
  and is the source `collect()` re-stamps from on every poll. It survives
  restart and compaction.
- **`questions.md` is the authoritative content, polled every tick.** There is
  no "unprocessed question update" to lose: the file *is* the state, and the
  loop re-reads it on every tick (`SKILL.md:80-87`). Losing an event costs at
  most one tick of display freshness — the next poll re-derives `updated_at`
  from the sig store.
- **Journaling it would file a second durable truth** for content the file
  already holds authoritatively — the two-durable-truths failure #263 exists to
  prevent, and the failure delivery-modes.md explicitly refuses to reintroduce.

So the event stays unjournaled, and the lossiness is harmless: it is a
best-effort interrupt whose loss is bounded to one tick by the per-tick file
poll. The sig store + `questions.md` are the delivery mechanism; the event is
the (optional, mode-gated) optimisation.

## Decision 3 — the swallow defect (name it, fix it)

The brief asked: when a **real** content change rides the **same collect** as an
algorithm re-seed, is it still reported? **No. The merged #534 code swallows it.**

`track_question_updates` (`watch.py:13450`) has two paths separated by an early
`return`. The re-seed branch (`if _store_algo(store) != SIG_ALGO:`,
`watch.py:13475-13491`) recomputes every entry's digest under the current
algorithm, **carries forward each entry's prior `updated_at`**
(`watch.py:13481-13488`), persists the store, and **`return entries`**
(`watch.py:13491`) — before the change-detection loop (`watch.py:13493-13528`)
ever runs. So in a re-seed collect:

- **No event fires** for a genuine change (the `elif prev.get("digest") != dig:`
  → `log_event` path at `watch.py:13508-13516` is unreachable).
- **The changed entry's `updated_at` is stale** — it carries the prior value
  (`prev_at`, `watch.py:13484`), not `now`, so the dashboard shows an old "updated"
  age for content that did change.
- **The change is permanently invisible as an event/age:** the re-seed stores
  the entry's *current-algorithm* digest of its *current (changed)* content
  (`watch.py:13482`), so the next collect sees no digest diff and never fires.

Cross-algorithm change detection is **impossible by construction**: you cannot
compare a current-algorithm digest to a stored old-algorithm digest (they differ
for unchanged content by definition), and the old algorithm's implementation is
not retained (only the `_SIG_ALGO_GENERATIONS` aliases are). So a re-seed
collect genuinely cannot tell which entries changed — which makes the choice of
what to stamp for `updated_at` a real one, and today's choice (`prev_at`) is the
silent-lie option.

**This is a defect, not a behaviour to design around.** Its severity is
narrowed by ruling (1): in `batched` mode no event fires anyway, so the lost
event is moot there; only the stale **display age** persists in both modes, and
only when an algorithm-upgrade deploy (rare — one so far: v0→v1) coincides with
a genuine content edit in the same collect window. **LOW-MEDIUM.** But it is a
silent data-quality defect on a display field, and this repo's culture treats a
silent loss as a finding, not a relief.

**Proposed fix direction (for the implementation lane):** in the re-seed branch,
stamp `updated_at = now` for every entry instead of carrying `prev_at`. This
preserves #534's silence (still zero events — an algorithm change is not content
change) and removes the silent lie: a genuinely-changed entry gets `now`
(approximately correct — it changed at or before now) instead of a stale prior
value. The tradeoff is that *unchanged* entries transiently show "just updated"
for one poll after an algorithm upgrade — a visible, self-correcting blip that
follows a deploy the operator knows about. The repo's verification culture
favours the **visible** error (every entry shows fresh) over the **hidden** one
(the one changed entry silently shows a stale age), so stamp-`now` is the
recommended default; the implementer may argue for carry-`prev_at` only with a
stated reason. (A dual-algorithm detection scheme — retaining old algorithm
implementations to compare — was considered and rejected as over-engineering for
a once-ever event.)

## Decision 4 — where the policy row lives

The ruling is a per-kind mode-gate, so it joins the structure that already
carries the per-kind wake policy: **`delivery-modes.md`**. That doc already has
a dedicated stub under "Wake channels outside the route table (#517)" —
*"`question-updated` — policy pending under #516"* — which currently states the
policy is undecided. The implementation lane **rewrites that stub** to the ruled
policy (mode-gated; not journaled; sig store + per-tick file poll are the
delivery) in the same commit that adds the code guard. One doc place, kept
single-source per the repo's design-as-built discipline.

The code seam is **also single and pre-existing**: `emits_wake(kind, target)`
(`watch.py:14054`) is the one per-kind decision point. The implementation adds
exactly one gate at the emit site (`watch.py:13513`); no new constant is
strictly required (`"question-updated"` is never a pre-empt kind, so passing the
literal routes it to instant-only, matching how the content routes pass their
path string as `kind`). A named constant is optional for greppability only.

## Implementation checklist (verbatim for the follow-up lane)

> lane-504chat (or whoever owns watch.py writes at merge time) executes this.
> Red-first per repo culture: each check must be shown to fail before it passes.

1. **Gate the emit (Decision 1).** Wrap the `log_event` call in
   `track_question_updates` (`watch.py:13513-13516`) in
   `if emits_wake("question-updated", target):`. Verify on HEAD that
   `emits_wake` is imported/in-scope at that site (it is module-level,
   `watch.py:14054`).
2. **Red-first the gate.** Under `delivery: batched`, assert a `questions.md`
   content edit writes **no** `question-updated` line to `watch-events.log`
   (the digest still changes and `updated_at` still stamps — assert *that* too,
   so the check does not pass over the stamping it depends on). Flip to
   `instant` and assert the line *does* fire. Reinstate the bug (remove the
   `if`), watch the batched assertion fail, restore.
3. **Fix the swallow (Decision 3).** In the re-seed branch (`watch.py:13475-13491`),
   stamp `now = time.time()` and set each entry's `updated_at` to `now` (and
   `e["updated_at"] = now`) instead of carrying `prev_at`. Keep the early
   `return` and the zero-event silence.
4. **Red-first the swallow fix.** Construct a store written under `sigtext-v0`
   (no `algo` key) with one entry whose content has *also* genuinely changed,
   run `track_question_updates`, and assert the changed entry's `updated_at` is
   ~now (not the carried prior value) and that zero events fired. Revert the
   `now`→`prev_at` change, watch the assertion fail (stale age), restore. State
   the production line your fake store stands in front of (the
   `_store_algo(store) != SIG_ALGO` read at `watch.py:13475`) and confirm
   changing it moves the test.
5. **Update the policy doc (Decision 4).** Rewrite the `question-updated` stub
   in `delivery-modes.md` (§"Wake channels outside the route table") from
   "policy pending" to the ruled policy: mode-gated via `emits_wake`, not
   journaled (sig store + per-tick `questions.md` poll are the durable
   delivery), and the re-seed swallow fixed. Same commit.
6. **No journal change (Decision 2).** Confirm `track_question_updates` still
   touches only `question-sigs.json` and `log_event` — no `journal.receive`.
   This is an assertion, not an action.
7. **Trailer.** If the commit changes what an existing install does (it does:
   `batched` mode stops waking on question edits), add `Feature: question-updated wake is now delivery-mode-gated` per the repo's commit-trailer convention.

## Flagged for the human

**Default: this is near-auto posture; nothing here is yours to rule.** The
mode-gate is the direct application of your already-ruled Q1 (the content class
batches) to a channel the original ruling did not name, and the journal ruling
follows from #263's single-durable-truth law. Two things are flagged only so
they are on the record, not because they block:

- **The swallow fix's tradeoff (Decision 3).** Stamping `now` for all entries on
  an algorithm re-seed means every question transiently shows "just updated" for
  one poll after a deploy. The alternative (carry the prior age) silently lies
  for the one entry that genuinely changed. This design recommends the visible
  blip; flagging only because "every question just changed" is a display you
  might see and wonder about. Algo upgrades are rare (one ever).
- **The 63-event storm is already fixed by #534.** This plan does not re-litigate
  #534; it cites the storm only as the measurement that refutes leaving the
  channel ungated. No action.

---

--- SUMMARY ---

- **What this is:** the #516 design half — a ruling on the `question-updated`
  wake channel (watch.py `track_question_updates`), which fires ungated and
  unjournaled on every content-digest change (#514 finding F2). Design only;
  authorises no code.

- **Ruling (1) — mode-gate.** `question-updated` is a per-kind signal routed
  under the delivery mode via the existing `emits_wake` seam (`watch.py:14054`):
  fires in `instant`, suppressed in `batched`. The question surface is the
  batched class (your Q1), and the loop re-reads `questions.md` every tick
  (`SKILL.md:80-87`), so the event is a one-tick-latency nudge, not a delivery
  path — withholding it in batched mode costs nothing. The always-instant
  carve-out alternative is refuted by the **63-event phantom storm** measured in
  `watch-events.log:302-364` (an unguarded per-entry content channel's cost).

- **Ruling (2) — not journaled, by construction.** `question-sigs.json` (atomic
  write) + `questions.md` (polled every tick) are the durable delivery; the
  event is a lossy nudge (`log_event` swallows `OSError`). Journaling it would
  file a second durable truth for content a file already holds — the #263
  anti-pattern. Loss is bounded to one tick by the per-tick file poll.

- **Ruling (3) — name the swallow defect.** The #534 re-seed branch's early
  `return` (`watch.py:13491`) skips change detection, so a real content change
  in the same collect as an algorithm re-seed loses its event and gets a stale
  `updated_at` (carries prior value). Cross-algorithm change detection is
  impossible, so the conservative fix is to stamp `now` for all entries on
  re-seed (visible, self-correcting blip) over carrying `prev_at` (hidden silent
  lie). LOW-MEDIUM; blast radius shrinks under ruling (1) (lost event is moot in
  batched mode). Named as a defect to fix, not design around.

- **Ruling (4) — policy row in `delivery-modes.md`.** It already has a
  "`question-updated` — policy pending under #516" stub; the implementation lane
  rewrites it to the ruled policy and adds the one `if emits_wake(...)` guard at
  `watch.py:13513`. One doc place, one code seam.

- **Measured basis:** 107 `question-updated` lines in the live log; 63 (59%) in
  one phantom burst at 09:43:31, dated exactly between #509's algorithm change
  (09:33:55) and #534's silent-re-seed fix (10:52:14). The loop reads
  questions.md every tick (SKILL.md). `delivery: batched` is live now.

- **Flagged for the human:** nothing blocking — near-auto posture. Recorded
  only: the swallow fix's visible-blip tradeoff, and that the storm is already
  fixed by #534 (cited as measurement, not re-litigated).
