# Lane 806 review D — cross-change interactions

## Verdict

**Two real interaction findings.**

1. **Medium — the coverage verdict became false when the corpus root moved.**
   The audit reads the main checkout's untracked briefs, then says they are not
   visible and the audit is incomplete.
2. **High at the reviewed range tip; Medium after later successor work — the
   linked-worktree fixture is green when the store half of that move is
   broken.** At the reviewed tip a worktree audit turned every citation into
   `UNRESOLVABLE` while the test passed. A later out-of-range change now makes
   the ordinary missing-store case refuse loudly, but the fixture still passes
   the same wrong-root injection and therefore still does not bind store
   identity.

No production code was changed. The only durable change is this review report.

Scope is the sixteen merge commits in `d45d964f..aadf579f`. I first mapped
first-parent file deltas by shared surface, then read the contracts and fixtures
at surfaces with multiple touchers. I did not use a passing full suite as
evidence.

## Finding 1 — coverage says visible briefs are invisible

**Rank: Medium, confidence: high.**

### Site and interaction

- `dev/citation_audit.py:122-126` states the old assumption: a worktree sees
  only the tracked subset.
- `dev/citation_audit.py:243-245` actually iterates every `*.md` in the
  selected directory.
- `dev/citation_audit.py:271-278` is the later change: both defaults now reach
  the main checkout.
- `dev/citation_audit.py:302-304` still maps every
  `on_disk > tracked` split to
  `AUDIT IS INCOMPLETE — untracked briefs not visible`.
- `test_citation_audit.py:384-426` asserts that contradictory sentence while
  its own fixture deliberately puts the untracked file in the main directory
  the default now reads.

The first change added a valid warning for a worktree-local corpus: untracked
main-checkout briefs could not travel into it. The later change correctly moved
the default corpus to the main checkout. That makes those briefs visible to
`audit_briefs`, but the earlier warning's interpretation did not move with the
reader.

### Actual versus claimed

Actual at the reviewed composite: the default audit traversed all 278
main-checkout briefs and examined 388 citations. Claimed: the 59 untracked
briefs were “not visible” and therefore the audit was incomplete.

The worktree-only control traverses 219 briefs and examines 161 citations. The
additional **227 citations** in the default run are direct evidence that the
untracked corpus is visible and being audited.

### Reproduction

From this linked worktree after the first required rebase, before the
out-of-range corpus-commit successor arrived:

```text
$ python3 dev/citation_audit.py --quiet
corpus: 219 tracked / 278 on disk (AUDIT IS INCOMPLETE — untracked briefs not visible)
citation_audit: examined 388 citation(s)
  UNRESOLVABLE:     2
  NO_RELATIONSHIP:  3
  UNCLASSIFIABLE:   383

$ python3 dev/citation_audit.py --quiet --briefs "$PWD/.dreamwork/docs/briefs"
corpus: 219 tracked / 219 on disk
citation_audit: examined 161 citation(s)
  UNRESOLVABLE:     1
  NO_RELATIONSHIP:  0
  UNCLASSIFIABLE:   160
```

Both commands exit 1 because they also find real citation findings; the
discriminating evidence here is the corpus line plus the 388-versus-161 examined
count, not the exit code.

After the second required rebase, `5c72a0d3` committed the then-persisted
corpus. The current control is `279 tracked / 279 on disk`, with 390 citations
examined, so the false sentence is dormant on that snapshot. It recurs whenever
a newly persisted main-checkout brief is still untracked; the permanent
linked-worktree fixture still constructs exactly that state and requires the
false sentence.

### What it is relied on to do

The module header says a truncated corpus must not read as complete. The current
inverse is also unsafe: a complete on-disk audit reads as truncated on every
healthy invocation while untracked dispatch briefs exist. That is the exact
failure mode in the lesson **“A check that fires on a healthy input is worse
than no check — its message names a failure on every run, so the reader learns
to dismiss the failure it exists to catch.”**

### Doubt and likely fix shape

I am not doubtful that the sentence is false. I am moderately doubtful about
severity because the audit data itself is more complete than it claims; this is
a trust/verdict defect, not a missed-citation defect.

The report needs separate concepts:

- corpus coverage: tracked versus on-disk;
- audit reach: files examined versus files present at the authoritative root.

“Untracked” is not synonymous with “unseen.” A main-root audit can report the
tracking split without calling itself incomplete; an explicit worktree-root
audit can still say it cannot see the main-root delta.

## Finding 2 — the reach fixture cannot see the store half regress

**Rank: High at the reviewed range tip; Medium on final master. Confidence: high.**

### Site and interaction

- The original audit separates its live store reader from corpus traversal at
  `dev/citation_audit.py:231-238`.
- The later root move couples the two defaults at
  `dev/citation_audit.py:271-278`.
- The linked-worktree test at `test_citation_audit.py:395-413` replaces
  `ledger_parse.store_records` with a fake that always returns `[]`, commits
  a marker file as the “store” so that it travels into both checkouts, and gives
  both briefs no citations.
- Its only assertions at `test_citation_audit.py:418-435` inspect the first
  coverage line. None asserts that a known ledger id resolves through the main
  store.

The corpus-root change and store-root change landed together as the repair to
the earlier audit. The fixture represents only the corpus half. It is therefore
green if the roots are split again and the production command returns a
corpus-wide false diagnosis.

### Concrete false green

Against the reviewed range, using `dev/redproof.py`, I injected this plausible
partial regression:

- `_default_briefs_dir()` continued to resolve the main checkout;
- `_default_dw_dir()` resolved the worktree-local `.dreamwork`.

The production command then returned:

```text
corpus: 219 tracked / 278 on disk (AUDIT IS INCOMPLETE — untracked briefs not visible)
citation_audit: examined 388 citation(s)
  UNRESOLVABLE:     388
  NO_RELATIONSHIP:  0
  UNCLASSIFIABLE:   0
```

In that same injected state:

```text
$ just pytest test_citation_audit.py::test_default_corpus_reaches_main_checkout_from_linked_worktree
1 passed in 0.36s
```

That is not a hypothetical weak assertion: a real worktree audit is wholly
wrong, while the test whose name claims main-checkout reach is green.

The final rebase brought in an out-of-range store-fault classifier. Repeating
the same injection against that newer code produced:

```text
audit_exit=2
citation_audit: store missing: .../cx-806revD/.dreamwork/ledger.sqlite3
test_exit=0
1 passed in 0.35s
```

So the later code makes the ordinary absent-worktree-store failure loud, which
reduces current severity. The fixture remains false evidence about root
identity: it commits a fake store marker into both roots and its fake returns
`[]` for either argument, so the wrong-root implementation still passes.

### What it claims or is relied on to do

The test docstring says the default reaches the main checkout. The landed task
record reports that the worktree default went from every citation unresolvable
to only two. The fixture proves only where briefs are found, not where ids are
resolved.

This is the lesson **“A test that fakes the code's dependency can end up
asserting a property of the fake.”** It also applies the selected absence rule:
the check did not exercise the store half, so its pass cannot be read as evidence
about that half.

### Doubt and closure assertion

I have low doubt about the fixture gap. The reviewed-range production code was
correct; this was a silent regression opening, not a present runtime failure.
The later missing-store refusal narrows the remaining risk to a wrong but
existing store, and I have reduced the current rank accordingly.

The closure fixture should put one known citation in the main corpus and make
the fake resolver return that id **only when its argument is the main
`.dreamwork` directory**. The worktree invocation must then assert
`UNRESOLVABLE: 0` (and a classified count of one), not merely the corpus line.
That assertion fails on the injected split above and remains independent of the
live ledger.

## Red-proof record

This is a read lens, so no new check or fix was added and no Direction-1 red is
claimed.

Direction 2 was executed against the existing linked-worktree test. The
genuinely broken state and false green are quoted under Finding 2. The injected
production state was read back through the command output, so the pass cannot
be attributed to an injection that failed to land.

Restore and pre-report gate:

```text
restore: 'dev/citation_audit.py' injected state recorded (sha 7a88d728e705,
hint: '"""Injected regression: resolve the worktree-local store."""');
original restored & verified.
check: clean — 2 injection(s) registered (role: reviewer), all restored and
absent from the working tree and from this branch's commits:
  dev/citation_audit.py (sha f5871baa8f1e,
  hint: '"""Injected regression: resolve the worktree-local store."""')
  dev/citation_audit.py (sha 7a88d728e705,
  hint: '"""Injected regression: resolve the worktree-local store."""')
```

A fixing lane's Direction 1 should inject that same split and require the new
known-id assertion to fail on the discriminating `UNRESOLVABLE` mismatch.
Its Direction 2 should use a main corpus with a genuine untracked brief and
require the fixed coverage wording not to claim the brief is unseen.

## Selected lessons and issue records checked

Each title below resolves to exactly one lesson head.

- **“A citation must carry its own evidence, and a line number carries none —
  the fix for two miscitation findings had the same disease as the disease.”**
  The task record's relied-on line is: “Any insert above line N shifts every
  citation below it … a line number carries no evidence.” I used identity
  (symbols and exact titles) for discovery, and only pinned report lines after
  rebasing.
- **“A tool that answers out of a store which did not resolve manufactures the
  confident wrong citation the brief exists to prevent.”** The task record for
  the zero-input sweep says it printed “nothing to review” after seeing zero
  ledger ids. This is the store half of Finding 2.
- **“A hand-rolled scan over `tasks.md` has now lost twice to per-id set
  membership — stop writing them.”** The selected task record's concrete limit
  is: “the lint check is count-only so lanes=[X]+dreamers=[Y] of equal length
  reads OK.” I compared file and warning member sets, never only counts.
- **“A check that declines to run must say so; a bare `return` turns ‘cannot
  check’ into ‘nothing to fix’.”** The task record states: “a check that did not
  run must say so rather than be silently absent, because absence reads as a
  pass.” Finding 2 is exactly that shape at one half of a two-root fixture.

The two interaction-owning records were also read:

- The corpus task says the audit was correct but “its input is silently
  truncated.”
- The reach repair says the default corpus must see the main checkout's
  untracked briefs and reports the store correction from all-unresolvable to
  two. The current report sentence is the stale assumption left between those
  two decisions.

## Shared surfaces checked and found sound

- `.dreamwork/lessons.md`: the later merge rewrote the two just-added
  provenance clauses in place; it did not insert above older lesson anchors.
- `briefs/boilerplate.md`: the two merges touched disjoint paragraphs. The
  later insertion shifts the screenshot paragraph by one line, but no tracked
  positional citation targets that later paragraph.
- `test_dispatch_lane.py` + `justfile`: the stdout classification change and
  corpus recipe compose. Verify mode branches before stdout validation, and the
  recipe does not launch a runner. The recipe-scope test was narrowed to its own
  recipe after the new verify call was added elsewhere.
- Canonical store composition + citation audit: graph tracing reaches
  `_entries_by_id -> ledger_parse.store_records -> _task_read ->
  task_store_spec -> dreamwork_store_spec`. The final live run resolves 388
  of 390 citations beyond `UNRESOLVABLE`; the composer change did not break
  this reader.
- Modularity/startup plan + docs-freshness edit: both use the same measured
  6,267-line `watch.py` state and both preserve the Python-stdlib constraint
  while retiring the client no-build constraint.
- Doc map: the later row update uses membership equality against the plan files,
  not a count-only comparison; both plans added in the range are named.
- Guard registry: none of the sixteen merges added a browser-guard registry
  member, so there is no same-day count/membership interaction to adjudicate.
- Ordering: the corpus-reach repair is an explicit successor to the coverage
  change, and the doc-map update intentionally follows the two plan additions.
  Those dependencies are visible; no other reverse-order/revert trap survived
  the shared-surface review.

## Position-pinned inventory

The positional-reference sweep excluded the already-filed `watch.py` corpus.
No tracked file cites a numeric line in `citation_audit.py`,
`test_citation_audit.py`, `test_dispatch_lane.py`, the new store module,
the startup benchmark, git-status helper, or bisect helper.

One pre-existing positional defect is outside this lens:
`status_sync.py:336` cites `dispatch_lane.py:322` as the `os.execvp` call,
but line 322 was already a receipt-error string at base `d45d964f`; the call is
currently at line 473. It was wrong before all sixteen merges, so I did not count
it as a same-day interaction.

## Verification and rebase

- Initial branch/base: `aadf579fce727f8037746763d76ba186aa174c69`.
- First rebase: cleanly onto local `master` at
  `7f978b35bb920755cfe6384be12c3f602c768ab3` (16 commits ahead of the brief's
  base; no conflicts).
- Master moved again during verification. Second rebase: cleanly onto local
  `master` at `5c72a0d3d8f81096b25c84485b2064e6ab987624` (20 further
  commits, no conflicts). Those commits included out-of-range successor work;
  its effect on both findings is stated above rather than silently treating
  post-scope state as the reviewed state.
- Master moved a third time during the final lint pass. Third rebase: cleanly
  onto local `master` at `1c7f015b8570126111f56792feab7cf41155632f`
  (8 further commits for the out-of-range subagent-policy control, no
  conflicts; neither finding surface changed).
- Master moved once more after the inbox append. Fourth rebase: cleanly onto
  local `master` at `c4d7d3458b21155a827be165896d108890ef6a9b`
  (2 docs/review commits, no conflicts; neither finding surface changed).
- Focused current-state test:
  `just pytest test_citation_audit.py::test_default_corpus_reaches_main_checkout_from_linked_worktree`
  — 1 passed.
- False-green run under the registered injection — same test, 1 passed.
- `python3 dev/redproof.py check` — clean, two registered injections restored.
- No browser guards, server ports, full suite, or `attn` were used.
- Pre-report lint with the worktree interpreter:
  worktree clean with the expected **five-row set** (absent ledger, absent
  status, zero-entry related-marker check, lesson near-duplicate, seven skipped
  ledger checks); main target clean with the single lesson near-duplicate row.

## DOGFOOD REPORT

1. The linked-worktree test says “default reaches main's untracked briefs” and
   then requires the sentence “untracked briefs not visible.” The contradiction
   is literal in one fixture, but each individual gate had a coherent local
   reason, so only the cross-change reading exposed it.
2. The same fixture stubs the one dependency whose location was the second half
   of the repair. Its careful linked-worktree setup makes it look more realistic
   than it is; a known resolvable citation is the missing positive control.
3. The required rebase changed the subject materially: later lanes committed
   the corpus and classified store faults while this report was being verified.
   A report that quoted only the post-rebase live output would have hidden the
   reviewed-range defects; one that ignored the successors would have asked for
   already-mitigated work. The brief could use an explicit rule for preserving a
   fixed review range while still rebasing the deliverable.
4. The brief's stated main/worktree lint counts were accurate at dispatch and
   had changed after the required rebase only in surrounding master content;
   comparing row identities, as instructed, remained unambiguous.
5. Codebase graph discovery worked and exposed the indirect store call chain.
   Positional/string inventories still required targeted `git grep`/`rg`,
   which is the documented fallback for literal coordinates and non-code files.
6. No other tooling or brief friction was found.
