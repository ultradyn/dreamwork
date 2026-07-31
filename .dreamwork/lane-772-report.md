# Lane 772 report

## Verdict

**The `#405` scope/content split was a bug.** `brief_add_commit()` said it returned
`None` for an untracked path, but used `git log --diff-filter=A` alone. After an
add commit was reverted, that query still returned the historical add while the
classifier read the recreated untracked bytes from disk. The green pre-commit
reading and red post-revert reading therefore classified the same current
untracked state differently.

The fix first asks `git ls-files --error-unmatch` whether the path is in the
current index, then consults add history only for tracked paths. This shared
helper also serves the hand-off-obligation and lane-scratch classifiers, so all
three now match their stated “untracked is skipped” contract.

## Dispatch contract

The checked route now requires exactly one task-head line of this form, resolved
from the same git common directory as the corpus:

> Coordinator inbox — ABSOLUTE path, append your completion summary here when
> you finish: `<main-checkout>/.dreamwork/inbox.md`

It validates rather than inserts or repairs the line. Thus the bytes validated,
persisted, hashed, and passed to the runner remain identical. The ambiguous
“append your hand-off line” wording is refused. `briefs/boilerplate.md` now leads
with “DO NOT WRITE TO `.dreamwork/handoffs.md`” and directs the completion report
to the coordinator inbox named by the task head.

The legacy `#405` regex remains a shape check, not an ownership check. A committed
brief naming `.worktrees/fake` and `/tmp/stale-coordinator/inbox.md` is in scope
and passes it. That is the open false-green: the lint check cannot distinguish a
real inbox from a well-formed fake. The dispatcher can, and rejects that exact
fake because it knows the main checkout. The lint check is still useful for
hand-written/historical artifacts, unsupported dispatch paths, and regression
defence over the corpus; it should not be described as proving destination
ownership. On a valid checked dispatch it is intentionally redundant and cannot
fire.

## Real-route proof

In scratch root `/tmp/ud-dreamwork-772.s2OjjF` I cloned this rebased branch,
created a linked lane worktree, and ran `just dispatch-lane prompt.md @cx-coder`
with a harmless fake `ccc` runner. Authoritative reads immediately after showed:

- the exact brief and receipt existed only in the scratch main corpus;
- `sha256sum -c 772-cx-scratch772.sha256` printed `772-cx-scratch772.md: OK`;
- commit `1a8c794` added the pair in the scratch clone;
- post-commit `python3 lint.py` reported `OK briefs 97 worktree-naming brief(s),
  66 in scope after absolute-inbox rule, 31 grandfathered (#405)`.

The scratch clone's whole lint had four unrelated clone-fidelity errors: its
gitignored ledger was absent (`tasks.md` had no next-id header), and three old
handoff SHAs were unreachable in the clone. None was a `#405` finding. The
worktree's route artifact was absent, proving corpus placement as well as content.

## Red proofs

Direction 1, dispatch header: after arming `dev/redproof.py`, I disabled the
`inbox_lines != [expected]` gate and amended the branch commit temporarily. The
named test failed on the discriminating result:

> `assert result.returncode == 2` — `AssertionError: assert 0 == 2`

That proves the ambiguous “hand-off line” prompt launched when the production
gate was removed.

Direction 1, tracked scope: I removed the current-index membership query and
temporarily amended the commit. The commit-then-revert test failed on:

> `assert lint.brief_add_commit(...) is None` — got historical add commit
> `74c5bd0596e020ac2be6c249427375f46cd51dff`

Both injections were restored through `dev/redproof.py`; fixed copies were also
snapshotted lane-privately, copied back, and verified with `cmp`. The final gate
said:

> `history: examined 1 commit(s) ... 0 holding a recorded injection.`
> `check: clean — 2 injection(s) registered, all restored and absent from the working tree and from this branch's commits`

Direction 2 is the committed fake-inbox fixture described above: the lint regex
passes `/tmp/stale-coordinator/inbox.md`; the dispatcher rejects it. This remains
an honest limit of the corpus check rather than being hidden by its name.

## Issue evidence used

- `#405`: “the dispatch prompt must give both channels as ABSOLUTE paths into
  the main checkout” and a relative inbox “creates a fresh file in the worktree
  that the coordinator never reads.” The present single-writer contract removes
  the handoff channel, but the inbox requirement remains.
- `#440`: “a lesson is not a guardrail.” This is why the canonical line is
  enforced by the checked route rather than left as remembered header prose.
- `#671`: the broken sweep printed “nothing to review” after examining no open
  ids; its fix required both denominators. The corpus check retains explicit
  worktree/in-scope/grandfathered counts, and the route has positive tests.
- `#136`: “THREE zero-states, not one”; present-but-unparseable is a fault while
  genuinely empty is calm. Missing/malformed coordinator instruction is a
  dispatch refusal, not a clean dispatch.
- `#702`: id-less/non-text queued entries were “unclassifiable rather than
  dropping them.” Likewise a noncanonical inbox instruction is refused rather
  than silently classified as absent or acceptable.
- `#755`: the accepted Direction-2 gap was “open id + already-landed prose
  passes, because ledger state cannot judge prose truth.” Here regex shape
  cannot judge inbox ownership, and the report states that limit.
- `#651`: “a guard's message must name a mode the guard can actually detect.”
  The fake absolute inbox demonstrates exactly what `#405` cannot detect.

## Rebase and verification

Rebased cleanly a second time onto moving local `master` `796655fa` during
closeout. The final rebased implementation commit is `a2aa3a8e`. Neither rebase
required hand resolution.
The pre-change lane bar was clean at **5 warnings**. Final commands and counts
after the report commit:

- `just pytest test_lint.py test_dispatch_lane.py`: **570 passed in 83.01s**
  after the final rebase;
- `python3 lint.py`: **clean, 5 warnings** (the same worktree-only categories
  as baseline: absent ledger/status, zero-entry marker/ledger checks, and the
  pre-existing near-duplicate lesson warning);
- `python3 dev/redproof.py check`: clean, two restored injections, four branch
  blobs read and zero containing an injection;
- `git diff --check`: clean; working tree clean.

## DOGFOOD REPORT

The brief's claim that the ambiguous header wording is “`#440` violated” does
not resolve to the actual `#440` ledger entry. That entry is about an unanchored
`tasks.md` section split and the need to reuse the production parser; its useful
general line is “a lesson is not a guardrail,” but it does not state a
one-instruction/two-readings rule. The ambiguity diagnosis is sound, but the
numeric citation is not evidence for it.

The scratch-clone requirement also exposed an evidence pitfall: invoking the
main interpreter while the shell cwd remained the linked lane made lint target
the lane. Re-running from the scratch main checkout was necessary to see the
committed corpus artifact enter `#405`'s count (96/65 became 97/66). The first
reading was not evidence about the corpus even though the interpreter path
looked right.
