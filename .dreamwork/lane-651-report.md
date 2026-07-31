# Lane 651 report — assertion messages must describe detectable modes

**Branch:** `cx-651guard`

**Base:** `master` at `0363ed8f` after three required refresh rebases while verification was running

**Lesson commit:** `8064b89f` (`.dreamwork/lessons.md`, post-rebase sha). This report is the branch's second `#651` commit.

## Outcome

I appended the requested long-form lesson, including the exact instance:

```python
self.assertGreater(j, ob, "TITLES table has no closing brace")
```

The arithmetic is the proof: an unterminated walk ends at `j == len(router)`, which is greater than the opening-brace offset `ob`, so the assertion passes in precisely the mode its message claims it detects.

I did **not** add a mechanical check. This is the brief's explicitly licensed measured-then-built-nothing outcome: every decidable proxy measured on the live tree either attributed valid assertions as defects or did not reach the instance's mechanism. Shipping one would turn a semantic judgement into a noisy regex report.

## Live measurement before deciding

Subject: the main checkout, `/home/xertrov/.llm-general/skills/ud-dreamwork`, at the same `master` revision used by this lane. I parsed all 129 tracked Python files with `ast`.

| Candidate proxy | Live matches | Finding |
|---|---:|---|
| Ordering assertion (`assertGreater` / `assertLess` / bare `>` / `<`) whose message contains `no`, `never`, `missing`, `empty`, or `unterminated` | 12 | All 12 were legitimate guards. Examples include `len(entries) > 0` detecting “no open questions” and `str.find(...) > 0` detecting a missing template. A lint finding would falsely attribute all 12. |
| Direct comparison involving `len(...)` or an identifier shaped like end/eof/length/size/limit | 22 | All 22 were legitimate. More importantly, this does not express the historical mechanism: `len(router)` occurs in the walk condition, while the assertion compares `j` with `ob`. |
| Broad message identifier absent from the comparison | 52 | Dominated by ordinary explanatory prose whose words should not repeat expression identifiers. No useful precision. |

The exact historical assertion is absent from current code because `#596` already repaired it. A spelling-specific rule would therefore count zero on the live tree and still be semantically wrong: a correct `assertGreater(close_index, open_index, "no closing brace")` can fail when `close_index == -1`, while the same broken `j > ob` guard evades the rule if its message is changed to `"brace scan finished"`.

The honest limitation is: **“the message names a mode the assertion cannot detect” is a semantic claim, and no regex decides it.** A non-zero match count is a question, not a verdict; here the questions resolved as valid sites.

## IGC decision

Context: choose among (A) the message-vs-mode lint proxy, (B) generalising `#661` to route-table extractors, (C) both, or (D) the licensed lesson-only outcome after live measurement.

The first pass produced no surviving check: A failed the low-false-attribution goal (12/12 live matches were valid); B failed the binding goal because the route-table extractor consumed by the guard is the nested `table_keys` in `test_watch.py`, while the free `dev/capture/` surface has no consumer for a new parallel extractor; C inherits both errors. Per IGC, zero survivors means fix the framing rather than select a refuted option. The brief supplies the corrected breakpoint: when no decidable proxy pays, preserve the demonstrated lesson and do not manufacture a check. D is therefore the sole survivor under the goals “retain the proven rule”, “land no misleading check”, “do not create an unbound second extractor truth”, and “respect `#612` volume”.

`#661` remains the right pattern where it is actually bound: `posturekeys.mjs` is consumed by the summary guard and is exercised against real, widened, and malformed source. Creating `routerkeys.mjs` without changing the real `table_keys` consumer would look like generalisation while protecting nothing.

## Red-proof, both directions

I ran a standalone executable reconstruction with the exact brace walk and unterminated input `"const TITLES = {"`.

Direction 1 output:

```text
direction-1: UNTERMINATED INPUT PASSED
  assertion: self.assertGreater(j, ob, "TITLES table has no closing brace")
  message: 'TITLES table has no closing brace'
  absolute-word proxy: NAMES IT
```

Direction 2 changed only the message to remove the proxy's absolute vocabulary; the guard remained decoration and the proxy passed:

```text
direction-2: UNTERMINATED INPUT PASSED
  assertion: self.assertGreater(j, ob, "brace scan finished")
  message: 'brace scan finished'
  absolute-word proxy: PASSES (MISSES DECORATION)
```

This also states what static checking cannot reach: even an accurate guard can remain decoration when its fixture never constructs the failing branch, and a correct assertion can consume a fail-unsafe extractor's lie. The guard itself must be exercised in its named mode.

No tracked file was injected because no mechanical check was built. I still ran the required hand-off command; verbatim:

```text
check: calm — no injections registered (opt-in discipline; nothing to evaluate).
```

## Verification

- `test_lint.py` before: **535 collected** (`python3 -m pytest --collect-only -q -n 2 test_lint.py`).
- `test_lint.py` after: **535 passed in 38.01s** (`python3 -m pytest -q -n 2 test_lint.py`) on the final rebased tree. No test surface changed, so the count remained 535.
- `python3 lint.py` from this worktree: **clean (6 warnings), no ERRORs**. Inspected warnings: three undated answered entries; absent worktree ledger/store; absent worktree `status.json`; zero-entry ledger-marker coverage; the pre-existing lessons near-duplicate; and the aggregated seven skipped ledger checks. These are the documented worktree baseline, not new findings.
- `python3 lint.py --target /home/xertrov/.llm-general/skills/ud-dreamwork` using this worktree's interpreter: **clean (2 warnings), no ERRORs**. The two live warnings were the same three undated answered entries and the pre-existing lessons near-duplicate.
- No browser guard ran; no port was bound or touched.

## Durable state changed

- `.dreamwork/lessons.md` — appended the measured `#651` assertion red-proof lesson; committed as `8064b89f` after the final rebase.
- `.dreamwork/lane-651-report.md` — this report, including the measurement, IGC ruling, red-proof output, verification, and dogfood notes.

## DOGFOOD REPORT

- The brief says “Two deliverables. Do BOTH” before explicitly licensing lesson-only when no proxy pays. The latter is clear and governed the outcome, but the opening imperative makes the correct measured-build-nothing result initially read like non-compliance. Naming the second deliverable as “measure and build only if supported” would remove that tension.
- `dev/redproof.py` records tracked-file injections. That is excellent for a built check, but a legitimate build-nothing outcome has only an executable standalone counterexample, so its required `check` output is necessarily `calm — no injections registered`. The report preserves the discriminating standalone output; the tool cannot register it without manufacturing a tracked injection.
- The “bound compared against a length/end index” candidate sounds narrower than it is. The real mechanism has `len(router)` in the loop condition, not in the assertion, so a direct-comparison AST proxy structurally cannot see the supplied instance. Discovering that through measurement was useful, but the candidate wording could say that inter-statement flow is required.
- Codebase graph search did not index the nested `table_keys` definition as a named function, but graph-augmented `search_code` found its enclosing test and full source immediately. No material blocker.
- The live ledger lookup and `#661` report were directly discoverable; the deprecated-ledger issue named as out of scope cost no time in this lane.
