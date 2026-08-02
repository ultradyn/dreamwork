# #1028 — task-state claim corpus threshold & provenance

## The figure, recomputed 2026-08-02

Reproduced with `dev/brief.py`'s actual regexes (`_TASK_STATE_PREDICATE` +
`_TASK_WARN_OUTPUT`) over the same 77-brief population
`dev/brief_corpus_stats.py --sample 0` examines (77 examined, 218 skipped for
no boilerplate; 1,363 `#NNN` citations in examined cores):

| metric | value |
|---|---|
| state candidates (deduplicated by file,line,task) | **5** |
| false positives | **0** |
| false-positive rate | **0.0%** |
| genuine findings | 5 (all MISMATCH: brief asserts `live`, ledger says `landed`) |

Raw per-candidate data: `1028-state-claim-corpus.tsv` (alongside this file).
Every candidate is a `state predicate` form ("`#NNN` is live …"); zero
`WARN output` candidates fire across this corpus.

## What instrument produced this figure

**Not `dev/brief_corpus_stats.py`.** That tool enumerates briefs and fields
only; grep for `state|candidate|false.positive|mismatch|threshold` across its
source returns zero hits — it cannot compute state candidates or false
positives at all.

The figure was produced by a classification script that imports `brief.py`'s
regexes and applies them to each examined core, then deduplicates by
`(file, line, task)` exactly as `_task_state_claim_report` does. That script is
not tracked (it is a one-off probe), but the method is fully specified by
"`_TASK_STATE_PREDICATE.finditer` + `_TASK_WARN_OUTPUT.finditer` over the
`brief_corpus_stats.py --sample 0` population" and the raw data is in the `.tsv`,
so the rate is recomputable by anyone.

## Threshold reconciliation

Two durable records disagreed (both in `.dreamwork/inbox.md` on 2026-08-02):

1. `≤1 FP / ≈20%` — "ship only if re-measured FP rate ≤ 1 (≤~20%)"
2. `≤15% and ≤1 FP` — "FP rate ≤15% (≤1 FP)"

**Both agree on `≤1 FP`.** They disagree only on the percentage bound. At the
measured population of 5 candidates, `≤1 FP` is arithmetically equivalent to
`≤20%` (1/5 = 20%), so the two bounds collapse to the same test at this size.

**Reconciled threshold: `≤1 FP`.** This is the bound both records state, it is
population-independent (a count, not a rate), and the percentage is a derived
consequence rather than a commitment. With 0 FP observed, the threshold is met
under either reading.

## Provenance of the pre-commit

The prior lane stated it pre-committed the threshold to a lane-private scratch
file (`precommit_threshold` / `igc_decision_statecheck`) **before** measuring.
That artifact is not in the diff and lane scratch is not durable across
sessions, so the pre-commit cannot be independently verified after the fact.
The raw corpus classifications (`1028-state-claim-corpus.tsv`) are now tracked,
so the *rate* is reproducible; whether the *threshold* was fixed before the
result is a claim that rests on the lane's report and cannot be re-established
from artifacts alone.
