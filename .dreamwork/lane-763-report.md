# Lane #763 report — coordinator dispatch hygiene

## Verdict

The lane half landed. `briefs/boilerplate.md` now defines the authority order:
an explicit, named override may replace a standing rule; a silent conflict loses to the
standing contract; and an internally contradictory task head authorises only the work common
to both readings. The bare-full-suite case is stated at its actual seam.

The coordinator half is a measured refusal. Under the original goal — prevent all four
recorded defect classes at dispatch — the IGC has zero survivors. I did not ship a checklist,
an after-dispatch lint proxy, or a partial `just dispatch` command and present it as a complete
fix. The safe residue is the lane rule plus a durable lesson recording exactly what syntax can
and cannot establish.

Historical briefs and lane reports were not rewritten. The existing grandfathering precedent
was considered and upheld: `#398` records “3 brief(s) in scope … 27 grandfathered”; `#405`
records “30 existing worktree briefs grandfathered, 0 in scope”; `#465` makes a new omission
loud “at brief-write time”; and `#652` resolves its collision class with a derived writer rather
than retrofitting old briefs. The live corpus remained 218 files.

## Measurement before build

- Corpus: 218 `.dreamwork/docs/briefs/*.md` files.
- Canonical base evidence: 0/218 contain any 40-hex SHA anywhere; therefore 0/218 have a
  canonical resolvable base header. This is why a new cutoff would begin with zero in-scope
  examples rather than a meaningful clean population.
- Broad conditional proxy (`if|unless|only if|when|conditional|depending|survives|measure`):
  218/218 files. It cannot discriminate a conditional deliverable from ordinary prose.
- Broad imperative proxy (`must|do both|required|deliverable|build`): 211/218 files.
- Even the narrow “two deliverables / do both” proxy names two healthy unconditional briefs,
  `414-prominence-precondition.md` and `472-questionsignal.md`. It misses the recorded #651
  wording while false-positiveing on valid briefs.
- Baseline and post-change `python3 lint.py`: clean with exactly 6 worktree warnings. No new
  healthy-tree warning was introduced.

The governing evidence from `#755` is explicit: its accepted check nevertheless had a
“KNOWN GAP … the check fires two warnings on the healthy live file”. That is the failure this
task forbids repeating. `#671` supplies the zero-coverage rule verbatim: “Zero entries now says
`DID NOT REVIEW` rather than ‘nothing to review’”. `#702` supplies the classification rule:
“Malformed task ids are KEPT and reported loudly rather than reaped as dead.”

## IGC

Context: one coordinator manually writes heterogeneous task heads and dispatches lanes through
more than one harness. The requested intervention must prevent all four observed brief defects,
act before the lane consumes the brief, remain silent on healthy briefs, and state what it did
not classify.

| Idea | All | G1 | G2 | G3 | G4 | G5 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Coordinator checklist file | ✘ | ✘ | ✘ | ✘ | ✘ | ✔ |
| Grandfathered lint over committed briefs | ✘ | ✘ | ✘ | ✘ | ✔ | ✔ |
| `just dispatch` owning worktree + generated base header | ✘ | ✔ | ✔ | ✘ | ✔ | ✔ |

- **G1:** acts before a lane receives the brief.
- **G2:** proves the named base is the worktree branch point, not merely hex-shaped or resolvable.
- **G3:** catches silent external conflicts and internal conditional/unconditional contradictions
  without accusing ordinary unconditional briefs.
- **G4:** becomes the one supported route rather than another act to remember.
- **G5:** reports coverage and unclassifiable inputs, including zero examined.

Decisive errors:

- Checklist: it is the same remembered act as manual brief review and does not bind the base to
  `git worktree add`. `#440` states the relevant one-way lesson: “`lint` cannot police a throwaway
  script … the anti-corruption assertions live inside [the tool], not in a linter looking at the
  aftermath.”
- Lint: a committed-brief check fires after dispatch, after the lane has already consumed the bad
  brief. Its first cutoff run would have 0 in scope; it can prove neither branch-point truth nor
  prose consistency.
- Dispatch command: using one generated SHA for both `git worktree add` and the header can make
  the base true by construction, and it can reject simple rotting commit-distance phrases. It
  still cannot decide whether two natural-language deliverable clauses contradict. The measured
  word proxies name 218/218 and 211/218 healthy historical briefs, so adding one would violate
  the healthy-input goal and train the coordinator to ignore it.

Zero survivors therefore means the original coordinator-side framing remains unsolved. Splitting
out only the mechanical base-header subproblem would be legitimate future work, but it would not
close #763's four-instance claim and was not shipped under that claim.

## Direction 2 — the cases that must not pass

No mechanical check was added, so there is no direction-1 red-proof to claim. I still constructed
the required false-green inputs to establish the boundary a future check must report:

1. `ffffffffffffffffffffffffffffffffffffffff` passes `^[0-9a-f]{40}$` and fails commit
   resolution. A shape-only header check therefore passes a citation carrying no repository
   evidence.
2. `513a42dcc735fc4659d25774c7bb2554f036fa97` is a real commit. It passes both the shape and
   resolution checks, but the measured branch point was
   `bfd7b2f604e15fc4f5585236ce9d195650d6a65b`; therefore it is still a false base.
3. A resolution-only check can prove “this names a commit in this repository”. It cannot prove
   “this was the lane's branch point”. Only a writer that uses the same captured SHA for worktree
   creation and header emission can carry that evidence by construction.
4. An unconditional “Two deliverables” brief must not trip a conditional-imperative check.
   Both measured narrow matches were exactly that healthy case; the broad proxy named every brief.

This follows `#764`'s own diagnosis: “a line number carries no evidence of what it points at”. A
hex token has the same disease unless its creation carries the branch-point evidence.

## Changes and verification

- `briefs/boilerplate.md`: added explicit override precedence, safe handling of internal
  contradictions, and the concrete bare-full-suite application.
- `.dreamwork/lessons.md`: added the measured distinction between generated truth and noisy prose
  validation.
- `.dreamwork/lane-763-report.md`: this report.
- `python3 lint.py`: clean, 6 warnings, before and after the change.
- `git diff --check`: clean.
- `just pytest test_lint.py -k Brief`: 46 passed, 489 deselected in 40.97s.
- `python3 dev/redproof.py check`: “calm — no injections registered (opt-in discipline;
  nothing to evaluate).” No check landed, so this is an honest zero rather than a red-proof claim.
- No test-bearing source file was changed. No browser guard, port, live ledger mutation, live
  status write, merge, push, or `attn` use occurred.
- Rebased cleanly onto local `master` at `377da328becc506bd64dc165d958e773ee69b063` before
  reporting. Post-rebase implementation commit:
  `38226a100d0f3c6d1a7efdd3300455843abf9190`. The commit containing this report is the branch
  head the coordinator should merge.

## DOGFOOD REPORT

The brief's requested precedence rule was already exercised by the brief itself: its absolute
rules say the standing contract wins an unflagged disagreement, while its verification section
correctly labels the targeted-pytest sentence “the contract, not an override”. That did not bite;
it is a useful dogfood example of the explicitness the new rule requires.

The actual friction was the instruction to consider a semantic lint check while demanding silence
on healthy input. Because ordinary brief prose contains conditional and imperative vocabulary,
the broad proxies looked maximally comprehensive while examining no useful distinction. The
measurement refuted them; treating their match count as evidence would have reproduced the task's
own defect one level higher.

One out-of-scope warning: the base-state boilerplate tells lanes not to trust the dispatch SHA as
*current*, which is correct for rebasing, but future generated headers must distinguish “historical
branch point” from “current master”. Collapsing those into one `Base` concept would make a truthful
header look stale and invite someone to remove it.
