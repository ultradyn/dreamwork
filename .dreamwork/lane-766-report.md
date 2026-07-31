# Lane #766 report — corrected Half A / Half B record

## Corrected verdict

**Half A shipped; this lane's original Half B was refused and did not ship.**
The former verdict, “Both halves shipped”, described commits that remained only
on `cx-766brief`.  The accepted Half B was later built by `cx-766b`: the checked
dispatch wrapper writes the validated prompt and its integrity receipt before it
execs the runner.  The coordinator verifies and commits that pending pair at the
merge gate.  See `.dreamwork/lane-766b-report.md` for the accepted implementation.

The original Half A result remains true: all four brief checks qualify their
content verdict with corpus reach, so a frozen nonempty population says
`HISTORICAL ONLY` rather than implying current coverage.

## Measurements carried forward from the original lane

At the original decision point:

- the corpus held **218** Markdown briefs, **215** orderable by leading task id
  and **3** explicitly unorderable;
- the newest numbered brief was **#595**;
- additions were 64 on 2026-07-28, 36 on 07-29, 61 on 07-30, 12 on 07-31,
  and zero on 08-01;
- **62** lane reports were committed and **60** were numbered above #595, so
  reports preserved judgement while losing the byte-exact source;
- three gitignored kept briefs (`#631`, `#634`, `#766`) demonstrated survival
  without clone durability or lint visibility.

At Half A's final rebase, task-bearing history reached #768: a 173-id gap from
#595.  The current accepted Half B adds `766-cx-766b.md`; its exact four-line
movement is recorded in the follow-up report.

## Original Half B IGC — preserved, not silently replaced

The original lane evaluated four durable-record options against:

- **G1:** preserve the byte-exact worktree brief the lane received.
- **G2:** enter git before task changes can obscure or amend the evidence.
- **G3:** exactly one supported persistence route.
- **G4:** keep later steering attributable instead of rewriting the original.
- **G5:** preserve the actual branch point and tip-at-dispatch contract.

| Idea | All | G1 | G2 | G3 | G4 | G5 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Report only; destroy brief | ✘ | ✘ | ✘ | ✔ | ✔ | ✔ |
| Lane persists untouched brief first | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Lane persists final, possibly edited brief | ✘ | ✘ | ✘ | ✔ | ✘ | ✔ |
| Coordinator commits staged original before dispatch | ✘ | ✔ | ✔ | ✔ | ✔ | ✘ |

The decisive G5 catch was correct and remains load-bearing.  If the coordinator
commits the brief before creating the worktree, the brief cannot cite the SHA of
the content-addressed commit containing itself.  If it creates the worktree and
commits second, master is no longer the lane's branch point at dispatch.
Report-only loses the source; lane-final permits amendments; pre-dispatch commit
creates that circularity.  Under these five goals, lane-first was the survivor.

## Why lane-first was refused

The matrix omitted an independent goal: **the route must work when the lane
cannot perform an obligation**.  A lane cannot persist a brief it never received
(the #768 incident), one it died before committing, or one on a branch later
abandoned.  Those are the dispatches whose original inputs are most diagnostic.
Adding that goal refutes lane-first even though its G5 reasoning is sound.

The accepted fifth option dissolves G5 instead of trading against it: after
validation, `dev/dispatch_lane.py` writes the prompt uncommitted to
`.dreamwork/docs/briefs/<task>-<lane>.md`, beside a SHA-256 receipt, and only then
execs the runner.  Master does not move at dispatch, no SHA cites itself, and a
lane has no second act to remember.

The cost is real: this is weaker than lane-first on G2.  The pair remains
uncommitted through the lane's lifetime.  The receipt detects ordinary edits and
one-sided deletion at the merge gate; deleting both pending files is still an
open false-green, exposed only indirectly when Half A's reach gap grows.  The
wrapper therefore records a pending brief; it does not claim committed
persistence.
