# #1028 — task-state claim corpus threshold & provenance

## The figure, recomputed 2026-08-02

Reproduced with `dev/brief.py`'s actual regexes by `dev/brief_state_claim_stats.py`
(the tracked classification scanner), which examines the 77 briefs that carry the
boilerplate sentinel (218 skipped — it globs every `*.md` in the briefs directory,
not just task-named files). The companion `dev/brief_corpus_stats.py --sample 0`
(#881) also examines 77 but skips only 206, because it filters to task-named files
(`\d+-…\.md`); both agree on the 77 examined. The prior revision of this document
attributed the 218 skip count to `brief_corpus_stats.py` and cited "1,363 `#NNN`
citations" — neither tracked tool reports a citation count, and `brief_corpus_stats.py`
reports 206, not 218. Both errors are corrected here (#1028 Finding 2):

| metric | value |
|---|---|
| state candidates (deduplicated by file,line,task) | **5** |
| false positives | **0** |
| false-positive rate | **0.0%** |
| candidate classification (reproducible from tree) | 5 genuine state predicates (all "`#NNN` is live") |
| ledger verdict (NOT reproducible from tree) | all 5 MISMATCH: ledger says `landed` |

Raw per-candidate data: `1028-state-claim-corpus.tsv` (alongside this file).
Every candidate is a `state predicate` form ("`#NNN` is live …"); zero
`WARN output` candidates fire across this corpus.

## What instrument produced this figure

**`dev/brief_state_claim_stats.py`** (tracked). It imports `brief.py`'s
regexes and applies them to each examined core via
`brief._collect_state_claims` — the shared fence-aware claim-collection loop
that production's `_task_state_claim_report` also calls — then deduplicates
by `(file, line, task)`. The scanner delegates to the same function production
uses rather than re-implementing the fence logic, so the population it
measures is the one the report sees (#1028 Finding 3; the prior copy once
opened `~~~` fences but only closed backtick ones).

`dev/brief_corpus_stats.py` (#881) is the companion that enumerates briefs and
fields; it cannot compute state candidates or false positives. Both tools
examine the same 77 briefs but count different skip totals because they use
different file globs (above).

## Threshold: no durable pre-commitment; raw result only

**No threshold was durably pre-committed before the measurement.** Two records
of a threshold exist (both in `.dreamwork/inbox.md` on 2026-08-02), and they
conflict:

1. `≤1 FP / ≈20%` — "ship only if re-measured FP rate ≤ 1 (≤~20%)"
2. `≤15% and ≤1 FP` — "FP rate ≤15% (≤1 FP)"

These do **not** collapse to the same test. At a population of 5 candidates,
1 false positive is 20%: it **passes** `≤1 FP` but **fails** `≤15%`. The
measured result (0 FP) satisfies both, so the data cannot distinguish which
commitment governed — and neither commitment was durably fixed before the
result. Git history finds the threshold text only in the delivery commit,
**after** the measurement commit; the prior lane's stated pre-commit rests on
lane-private scratch that does not survive across sessions and is not in the
diff.

The prior revision of this document resolved the conflict by adopting `≤1 FP`
and presenting the result as having cleared it. That is selecting the weaker
of two records after the fact — the retroactive manufacture the original
requirement anticipated: *"if that commitment was not durably made, say so
rather than manufacture one retroactively."* This revision corrects that
(#1028 Finding 1).

**Raw result, no pre-registered bar claimed:**

- 5 candidates, 0 false positives, 0.0% FP rate.
- All five are genuine state predicates (`#818`, `#816`, `#821` "is live").
- Whether that would have satisfied a pre-committed threshold is unknowable,
  because no threshold was durably pre-committed.

## Reproducibility notes

**Candidate classification (reproducible from tree).** The five candidates and
their classification as genuine state predicates are reproducible by running
`dev/brief_state_claim_stats.py` against the tracked brief corpus. The "is this
a state claim" judgement requires only the source lines, not the ledger.

**Ledger verdict / MISMATCH (NOT reproducible from tree).** The
`ledger_state=landed` column in `1028-state-claim-corpus.tsv` was derived from
the local `.dreamwork/ledger.sqlite3`, which is gitignored and does not travel.
To reproduce the MISMATCH verdict: run `dev/ledger.py get <id> --ledger …`
against a populated ledger in the main checkout.

**Pre-commit (not verifiable).** The artifact the prior lane cited
(lane-private scratch) does not survive sessions and is not in the diff. Git
history confirms the threshold text appears only in the delivery commit, after
the measurement commit.

## Test reproducibility (#1028 Finding 4)

`test_brief.py` is not hermetic: the module-scoped `lane` and `generated`
fixtures call `brief.build(881, …)`, which reads the real
`.dreamwork/ledger.sqlite3` in the ambient checkout. A clean clone with no
populated ledger hits pre-existing non-hermetic failures unrelated to the
state-claim work (the `1 failed, 93 passed` result this lane reports requires
a populated ledger). The 22 state-claim tests added by this task ARE hermetic
— each builds its own fixture store via `_state_ledger(tmp_path)` — and pass
independently of the ambient ledger. These counts are re-derived at the lane
tip; the prior reading of 92 passed / 21 tests went stale when the F3 commit
added the tilde-fence regression and the count was not re-run — which is the
only way a number in a record about measurement rigour goes stale.
