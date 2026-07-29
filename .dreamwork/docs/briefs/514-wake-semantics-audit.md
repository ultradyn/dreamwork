# Brief — #514: audit wake semantics under batched delivery — report-first

Lane-owns: `.dreamwork/docs/findings/514-wake-semantics-audit.md` (NEW file — your report), `.dreamwork/handoffs.md` (append ONE `## Pending` line)

This is an **audit lane**: investigate, write the findings doc, report. Do NOT
fix anything you find — the coordinator files follow-up tasks from your report.
You own no production file.

## The question

Delivery is now `batched` (posture axis set by the human 2026-07-29 04:52; the
#342 design is `.dreamwork/docs/plans/delivery-modes.md` — READ IT FIRST). The
ruling in one line: under batched delivery, ambiguous-class events accumulate
in the durable journal and the loop drains them on its own tick
(`dev/journal_consume.py pending → process → consume`); only do-now/do-next
class events may pre-empt (wake the loop immediately). The wake channel is
`.dreamwork/watch-events.log` — every line appended there fires the loop's
tail Monitor and wakes the session.

So: **every append to `watch-events.log` is a wake.** The audit: does every
wake line that CAN fire under batched mode match the ruling?

## What to trace (all in the main checkout, read-only for you)

1. **Every writer.** Find every code path that appends to
   `.dreamwork/watch-events.log` (start: `watch.py` around lines 13231,
   13346, 13377, 13452, 13678; also `dreamhub.py`, `dev/*.py`, and the
   `dev/capture/*.mjs` guards are READERS not writers — verify that claim).
   Produce the complete list: file, function, route/command, and the class of
   event it represents.
2. **Classify each against the ruling.** For each writer: is its event
   do-now/do-next (wake legitimate under batched) or ambiguous-class (wake is
   a ruling violation under batched — it should journal silently and wait for
   the tick)? Note especially: `/command` submissions (do-now vs do-next vs
   add-idea vs question-answer — does the wake decision distinguish them?),
   posture/delivery/run-mode changes, question-updated lines, and anything
   emitted on receipt arrival (the `receive()` path in watch.py — does the
   server write a wake line per receipt, and is that conditional on the
   CURRENT delivery mode?).
3. **Mode-awareness.** For each writer: does it know the delivery mode at all?
   The ruling expects wake decisions to be conditional on the live mode
   (`.dreamwork/posture`, `delivery:` line) — a writer that wakes
   unconditionally is a violation for every ambiguous-class route it serves.
   Check how mode is read (file read per event? cached?) and whether a stale
   read is possible.
4. **The journal side.** Confirm `dev/journal_consume.py`'s consume path
   itself never writes to watch-events.log (the drain must not wake the loop
   that runs it — a self-wake would be a loop). And confirm the receipt-batch
   wake story in delivery-modes.md matches the implementation: when a batch
   contains a do-now, what fires the wake, and does it name the batch or the
   event?

## The report (`.dreamwork/docs/findings/514-wake-semantics-audit.md`)

Structure it:

- **Writers table**: file:function | route/command | event class | wake under
  batched? | mode-aware? | verdict (COMPLIANT / VIOLATION / UNCLEAR).
- **Findings**: numbered, each with the evidence (file:line, the code, why it
  violates or why it's fine). Rank by severity. A violation that could wake
  the loop on every ambiguous event is the top severity — it silently undoes
  batched mode.
- **What you could NOT determine**: name it. An audit that hides its blind
  spots is worse than one that declares them.
- **Proposed follow-ups**: one line each, phrased as task titles the
  coordinator can file verbatim. Do not implement them.

## Verification (yes, audits have it here)

- Every COMPLIANT verdict must cite the line that makes it compliant (the
  mode check, the class gate). A verdict without a line number is unchecked.
- Every VIOLATION verdict must have been exercised READ-ONLY where possible:
  e.g. if you claim route X wakes unconditionally, quote the function and
  show there is no mode branch — do NOT start a server or POST to the
  dashboard (ports 39890-39899 belong to the guards; the hub is 39880-39889).
- Cross-check your writer list for completeness: `grep -rn "watch-events"
  watch.py dreamhub.py dev/ user_events/` and account for every hit — either
  it's in your table or you say why it's not a writer.

## Constraints

- You own NO production file. If you find an obvious one-line fix, you
  REPORT it; you do not make it.
- Do not run servers, guards, or the deploy path. `python3 -m pytest -q`
  is allowed (read-only effect) but not required.
- Append ONE `## Pending` line to `.dreamwork/handoffs.md` (append-only;
  never rewrite; the literal path is `.dreamwork/handoffs.md`).

## Report back

The writers-table summary (counts by verdict), the findings list (one line
each, severity first), the follow-up task titles proposed, and anything you
found that contradicts delivery-modes.md itself (the doc, not just the code,
can be wrong).
