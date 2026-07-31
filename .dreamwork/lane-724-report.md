# Lane report — `#724`: sweep resolves shas; a 7-char citation reconciles git's 8-char %h

**Verdict: MECHANISM LANDED.** The measurement was not 1, so the fix-one-citation path
was closed; the resolver is in `dev/ledger.py`, immune to the rot that re-breaks
width-matching. 2 commits on `lane-724sha`, rebased clean onto `master` (236828b5).

## The measurement (came first, did not end the task)

**4 open ids are flagged ONLY because of sha width mismatch: #263, #269, #448, #465.**
On whole-history sweep the substring check flags 5 ids totalling 32 rows; with the
resolver, 14 of those rows reconcile (the width-rotted ones) and the ids that remain
do so for genuinely-uncited landings, which is correct:

| id | substring rows | resolved rows | reconciled |
|----|---------------|--------------|------------|
| #263 | 25 | 15 | **10** |
| #269 | 3 | 1 | **2** |
| #448 | 2 | 1 | **1** |
| #465 | 1 | 0 | **1** |
| #724 | 1 | 1 | 0 (my own measurement commit) |

The live tick window (since the last fold) flags nothing — the class only surfaces
on whole history, which is why #723's lane found it while measuring a delta.

Not 1: **#263 alone rotted 10 citations**, so fixing citations individually is a
whack-a-mole that re-breaks as the repo grows. `#590` governs: the non-zero count is
a question, and the answer here is "build the mechanism."

## What I changed and why

`sweep()` gained an optional `cites(sha, body) -> bool` callable. The default is the
`#404` substring check — **every existing test passes unchanged**, which keeps the
four `#404` pins binding the behaviour they were written for. `sweep_text` builds a
resolution-backed predicate and passes it in; the pure function stays pure.

The resolver (`_resolved_cites`) resolves only the shas that **FAIL substring** — the
lazy set the brief hinted at — not every sha in the ledger. Measured: **79 comparisons**
reach the subtraction line over 2896 commits, of which a handful fail substring. Those
plus the citations in the touched bodies are resolved in **one `git cat-file
--batch-check` call** (2.3 ms for ~190 shas). Per-sha subprocess was measured at 457 ms
(20× the substring check) — rejected. `cat-file --batch-check` returns `missing` for
unresolvable shas (no error, no crash), which is the correct answer for a typo (`#136`).

**Resolution, not width-matching.** Git's abbreviation length GROWS with the repo: a
7-char citation unambiguous when written becomes 8 later. A fix that normalises today's
widths solves tonight and re-breaks next year; resolution (`git rev-parse`: `58e3040`
IS `58e3040d` to git) is immune. This is the strongest argument for the chosen fix and
it is structural, not aesthetic.

## Cost — argued with numbers

| approach | time |
|----------|------|
| current sweep (substring, no resolution) | 22.6 ms |
| per-sha `git rev-parse` (238 shas, rejected) | 456.8 ms |
| batched `git cat-file --batch-check` (190 shas, 1 process) | 2.3 ms |
| lazy batched (only substring-failures: 92 shas) | 1.9 ms |
| resolver built + sweep run (whole history, live) | ~70 ms |

The resolver adds ~50 ms to a per-tick sweep that already costs ~23 ms, and it only
fires when there are failures to resolve. On the live tick window (149 commits since
the last fold, 0 failures) the resolver returns the plain substring default — zero
added cost.

## Red-proof — both directions

### Direction 1 (the real defect, discriminating message)

Snapshotted the fixed `dev/ledger.py`, sabotaged the production line
(`_cites(sha, bodies.get(tid, ""))` → `sha in bodies.get(tid, "")`), ran
`test_sweep_resolution_backed_cites_reconciles_a_width_mismatch`. Went RED on the
message that **names the id and both widths**:

```
AssertionError: #465 cites 58e3040 (7c) and git %h = 58e3040d (8c) — both resolve
to the same object, so the resolution-backed cites predicate must subtract it.
Substring misses; resolution must not.
assert 465 not in {465, 466}
```

Restored via `dev/redproof.py restore`; `check` clean. The test also carries a
non-vacuous precondition (#466 genuinely uncited stays flagged) and asserts the
widths differ at runtime.

### Direction 2 (false-greens — constructed, all correct)

- **Typo sha** (`58e304X`, 7 hex-invalid chars that prefix-match nothing): resolver
  returns `False` — the id stays flagged. Correct: a typo should not suppress a real
  finding. `cat-file --batch-check` reports `missing`, which resolves to no id.
- **Foreign/missing sha**: resolver returns `False` — stays flagged. Correct.
- **Merge-sha vs lane-sha** (`#628`'s adjacent bug): body cites the lane commit
  (`2c0521df`), sweep sees the merge (`f054e882`). Both resolve, but to **different
  object ids** → `False`. Correct: the merge IS genuinely uncited, the lane commit is
  a different object. Resolution does not conflate them.
- **Ambiguous short prefix** (`f054`): `cat-file --batch-check` resolves it to the
  unique full sha — no error, no false positive.

No false-green was constructible: the resolver compares resolved object ids, so a
citation and a commit sha only match when they ARE the same object.

## Cited issues — relied-on lines quoted

- **#404**: *"scan subjects, subtract entries that cite the sha, report the remainder
  with a count"* and *"Cite the sha, the row disappears"* — the suppression convention
  the width bug silently broke, and the primary landing-discovery route this noise
  degrades.
- **#590**: *"a non-zero count is a question, never a verdict"* — governs the
  measurement (4 is a question; the answer is "build the mechanism").
- **#723**: *"MEASURED, and the measurement cut against my framing: 3 wip( commits in
  2866, one naming an open id … delta +0 new open ids"* — the precedent for reporting
  a measured number honestly; this lane's 4 is not +0, but the same discipline applies.
- **#628**: *"My earlier note cited only the MERGE sha, which is why sweep kept naming
  this entry"* — adjacent; a Direction-2 candidate confirmed correct under the resolver.
- **#612**: volume — the fix is ~60 production lines and 2 tests, not a mechanism that
  triples the doc.

## Out of scope (named, not fixed)

- **`lint.py:1405` carries the IDENTICAL `sha in body` bug** in
  `check_landed_still_open` (`#323`'s twin). `lint.py`/`test_lint.py` is off-limits
  (`#725` live). The fix shape transfers directly: the same `cites`-callable seam or
  a shared resolver would close it. **The coordinator should file this.**
- `_resolved_cites` uses `id(body)` was my first approach — it broke because `sweep`
  rebuilds its own bodies map (different string objects). Fixed by deriving the cited
  set from the body each call. Not a defect in the shipped code, but worth noting: the
  pure function and the resolver must not share body objects by identity.

## Verification

- `python3 -m pytest test_ledger.py test_ledger_write.py` → **79 passed** (was 72 when
  the brief was written; master moved with more tests; my change adds 2).
- `python3 lint.py` → **clean** (6 store WARNs expected in a worktree per `#611`, no
  ERRORs).
- `python3 dev/redproof.py check` → **clean** (1 injection registered, all restored,
  absent from tree and commits).

## Dogfood report

1. **The measurement's first run was structurally hollow** — I read the raw markdown
   `tasks.md`, which is a one-line shim now that the store is the source of truth.
   `watch.parse_ledger` returned 0 open ids and the sweep found nothing, which read as
   "the class is empty." The fix was to use `lint.ledger_view()` (the `#671` dispatch
   the real sweep uses), not open the file directly. The brief's `--ledger` invocation
   runs sweep correctly, but a hand-written measurement script that reads the file
   directly is the trap — and it is not obvious that `tasks.md` is a shim in a worktree.
   A one-line note in the brief ("the store is the source of truth; raw `tasks.md` is a
   shim — use `ledger_view` for any hand measurement") would have saved 15 minutes.

2. **`git cat-file --batch-check` vs `git rev-parse`**: the brief suggested `rev-parse`,
   but `cat-file --batch-check` is the better tool — it batches in one process (2.3 ms
   vs 457 ms), returns `missing` instead of erroring on bad input, and echoes the full
   sha. Worth adding to the brief's resolver guidance.

3. **The `id(body)` bug was subtle.** The pure function and `sweep_text` each build
   their own bodies map from the same text, but the string objects are distinct.
   Caching by `id(body)` silently broke the resolver. Python interns short strings but
   not multi-KB bodies. No tool catches this; only the row-count delta did.
