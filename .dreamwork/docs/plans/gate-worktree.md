# Gate worktree — separate provisional gating from the main checkout

## Verdict

**INFERRED — feasible, staged, and still serial.** Build and test each
provisional merge in one dedicated detached scratch worktree while the main
checkout stays attached to `master`. Keep one gate mutex for the whole landing,
then advance the single `master` ref once, from the main checkout, only after all
gates pass and a compare-before-advance check proves `master` is still the
captured base. **This does not permit concurrent gates.** Two provisional gates
cannot both own the next `master` value; a second gate must wait.

**INFERRED — do not remove the dispatch refusal in the first increment.** The
scratch worktree removes detachment as a reason for refusing dispatch, but it
does not remove the shared brief-corpus write/read race or give a stale finished
lane an owner able to rebase and re-arm its evidence. Preserve an explicit live-
gate refusal first. Relax it only after the corpus and re-arm increments below
land. Otherwise the first visible result would be a larger finished queue whose
evidence becomes stale after every serial landing.

**VERIFIED — payoff boundary.** The reported incident was eight finished
branches and no live lanes, with one gate taking 7–9 minutes. That is enough to
motivate the work, not enough to certify a landing rate. Increment 1 removes the
main-checkout detachment, deploy refusal, and dangerous crash shape; by itself it
does **not** reclaim the reported hour of dispatch capacity. Later increments may
keep useful work live during a gate, but the landing throughput remains bounded
by one serial gate and has not been measured here.

## Premises re-verified before choosing

- **VERIFIED — launch already uses a stable ref.** `launch_lane.launch` resolves
  `base_sha` from `master^{commit}` and passes that exact SHA to `git worktree
  add ... -b <lane> <base_sha>` (`dev/launch_lane.py:373,507`). A plan to add
  that seam would re-propose current behaviour.
- **VERIFIED — the corpus is deliberately main-checkout-owned.** `_briefs_dir`
  resolves the common `.git` directory and returns the main checkout's
  `.dreamwork/docs/briefs` (`dev/dispatch_lane.py:86-123`); `persist_prompt`
  creates the brief and receipt there (`dev/dispatch_lane.py:511-545`), including
  the `--prepare` route through `main` (`dev/dispatch_lane.py:718-801`).
- **VERIFIED — the present gate has five main-checkout transitions.** `land`
  requires the invocation checkout on `master` (`dev/land_lane.py:1618-1637`),
  detaches it at the captured base (`:1930-1940`), builds the provisional merge
  there (`:2005-2017`), restores it to `master` (`:2273-2284`), and only then
  fast-forwards `master` (`:2284-2299`).
- **VERIFIED — deploy refusal is a consequence of detached main HEAD.**
  `detached_head_refusal` rejects a detached checkout and the stop transition
  calls it (`dev/deploy_state.py:329-339,918-926`). Keeping the main checkout
  attached removes this gate-induced case; the generic deploy guard remains
  valid for other detached checkouts.
- **VERIFIED — a plan under this directory is inert.** `_is_inert_doc` classifies
  Markdown under `.dreamwork/` as inert unless explicitly executable, and
  `_classify_diff` uses that result to calculate binding paths and required
  injections (`dev/land_lane.py:252-262,1002-1018`). The actual committed diff
  still has to be classified; this statement is not a substitute for that run.

## IGC choice

**Context.** There is one local `master` ref, one main checkout, linked lane
worktrees, a serial 7–9 minute gate, a shared operator-side brief corpus read by
lint, and queued lanes whose red-proof evidence cannot survive an unowned
rebase. The immediate design question is not “how can two gates run?” but “where
can one provisional gate run without monopolising the main checkout?”

**Binary goals.** G1: the main checkout remains attached to `master` throughout
provisional merge and tests. G2: exactly one gate can advance `master`, and an
advance refuses if `master` moved. G3: lint compares one stable brief-corpus
population. G4: no post-rebase lane is called gate-ready without a full re-arm
owned by an active agent. G5: a crash is discoverable and has an exact recovery
target. G6: the first increment preserves current evidence and is small enough
to dispatch.

| Idea | All | G1 | G2 | G3 | G4 | G5 | G6 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| I1 — scratch gate and immediately allow dispatch | ✘ | ✔ | ✔ | ✘ | ✘ | ✔ | ✘ |
| I2 — unattended drain runner only | ✘ | ✘ | ✔ | ✔ | ✔ | ✘ | ✔ |
| I3 — batch non-conflicting lanes into one gate | ✘ | ✔ | ✔ | ✔ | ✘ | ✔ | ✘ |
| I4 — order the queue by file contention | ✘ | ✘ | ✔ | ✔ | ✘ | ✘ | ✔ |
| **I5 — staged scratch gate, corpus isolation, then owned re-arm/drain** | **✔** | **✔** | **✔** | **✔** | **✔** | **✔** | **✔** |

**I1 decisive errors.** Dispatch still writes the main corpus while the gate's
baseline and comparisons read it, so G3 fails. Each successful serial advance
also stales every other queued base; allowing more dispatch without assigning
the re-arm fails G4. Those are correctness errors, not costs to average away.

**I2 decisive errors.** A drain runner removes human gaps between gates but the
current gate still detaches the main checkout, so it fails G1 and cannot restore
fleet dispatch. It is useful after I5 as the owner of queue transitions, not as
the storage or worktree design.

**I3 decisive errors.** A failed batch no longer attributes the verdict to one
lane, and individual pre-batch causal evidence does not certify the combined
tree. Recovering that attribution and re-arming the composite is a new gate
protocol, not a cheap way to reuse one test run. It fails G4 and G6.

**I4 decisive errors.** Ordering disjoint changes can reduce conflict-resolution
cost, but every successful landing moves `master` regardless of file overlap.
It therefore changes neither main-checkout detachment nor re-arm frequency and
fails G1, G4, and G5. Keep it as a queue heuristic only.

**I5 survivor.** Staging makes each safety boundary explicit: first move the
provisional tree without changing dispatch policy; then give lint an immutable
corpus subject; then permit dispatch only with an owned `needs-rearm` queue
state and a drain runner. No stage borrows correctness from a later one.

## Question 1 — the five `land_lane` sites

| Current site | Scratch-worktree form |
|---|---|
| **Preflight requires the one checkout on `master`** | Resolve the unique main checkout from the common Git directory; prove it is attached to `master`, clean, and at `base_sha`, but do not use it as the gate cwd. Acquire the whole-run gate mutex, capture `base_sha` and `branch_sha`, then under a short worktree-registry mutex run `git worktree add --detach <gate-path> <base_sha>`. The lane remains a separate registered worktree. |
| **Detach the main checkout at the base** | Delete this transition. The new gate worktree is detached at the exact captured SHA from birth. Main stays attached to `master`. A shared worktree-registry mutex serialises this `worktree add` with `launch_lane`'s `worktree add`, so the design does not depend on unmeasured simultaneous Git worktree mutations. |
| **Build and gate the provisional merge in main** | Run `git merge --no-ff <branch_sha>` and every merge-identity, lint, pytest, guard-selection, and red-proof command with the gate worktree as cwd. Continue proving parents are exactly `[base_sha, branch_sha]`. The lane worktree and main checkout are inputs, never provisional-merge workspaces. |
| **Restore `master` in main** | There is nothing to reattach. On a clean refusal, remove the registered gate worktree and prove it disappeared before clearing its breadcrumb. A cleanup failure keeps the breadcrumb and refuses. On success, keep the scratch worktree until after the master advance so the gated merge remains reachable. |
| **Advance the one `master` ref** | After all declared gates pass, enter a short master-state critical section shared with launch selection. Re-read `refs/heads/master == base_sha`, the main checkout's current branch is `master`, and tracked state is clean; then run `git -C <main> merge --ff-only <merged_sha>`. Prove `master == merged_sha`, remove the scratch worktree, and clear the breadcrumb. If the ref moved, refuse and clean up without landing. |

Three exclusions must not be collapsed into one vague “gate lock”:

1. **Gate mutex, owned by `land_lane`, whole run:** one provisional merge and one
   candidate next value for `master`. This is why gates remain serial.
2. **Repository-state mutex, shared by `launch_lane` and `land_lane`, short:**
   worktree registry mutations plus launch's base snapshot versus the final
   main-checkout fast-forward. This removes any dependency on simultaneous
   `git worktree add` behaviour and prevents launch from reading half of a
   checkout transition.
3. **Brief-corpus exclusion, owned at the writer/reader seam, separately:**
   `dispatch_lane` owns writes; the gate's lint population owns its fixed read
   interval. Its scope is Question 2, not a consequence of Git worktrees.

The main checkout being available is not the same as `master` being
multi-writer. Two gates may build speculative commits only if a later design
needs that, but they still cannot both claim the captured old value of
`master`; this plan deliberately does not create or recommend concurrent gates.

## Question 2 — corpus-write exclusion is unchanged by scratch gating

**Answer: unchanged, so the dispatch ban survives in reduced form.** The writer
uses the common Git directory to find the main corpus, and lint deliberately
reads that shared population. Moving the merge cwd does not move either side.
Worse, protecting only each individual lint process is insufficient: a dispatch
between the pre-merge baseline and final lint comparison can change the row set
and look like a merge effect. Until lint has an immutable corpus subject, the
exclusion must cover the population from baseline capture through comparison.

Increment 1 therefore replaces the accidental “main is detached” refusal with
an explicit live-gate refusal in `launch_lane`. That is reduced in *reason*—the
main checkout and deploy transition remain usable—but may cover the same gate
interval. It must not be sold as recovered fleet throughput.

The separate corpus increment should define one explicit input for all three
gate lint readings. Viable shapes are a gate-owned immutable corpus snapshot or
an operator-local corpus-store snapshot API. The writer takes the corpus mutex
only while publishing a complete brief/receipt pair; the gate takes it only
long enough to capture a complete snapshot, then releases it before pytest.
Baseline, precheck, and comparison use the same snapshot identity and report
that identity. Present-but-unreadable, absent, and genuinely empty remain three
different results.

**`#867` is independent and composes.** Untracking changes the corpus authority
and invalidates Git-history-derived readers; it neither creates a gate worktree
nor serialises `master`. Conversely, a scratch gate does not make an
operator-local corpus immutable. The two designs compose if the scratch gate
accepts a corpus snapshot through an explicit reader interface. They conflict
only if this plan hardcodes “copy the tracked corpus from the gate worktree,”
which it must not do because that would become empty or historical when the
operator-local ruling lands.

## Question 3 — re-arm ownership gets worse if dispatch alone is freed

**Answer: scratch location alone is unchanged; relaxing dispatch is worse in
aggregate.** A successful landing still moves the one `master` ref. Every other
finished branch is then stale, and the full red-proof re-arm remains required
after its rebase. Letting six lanes continue to finish while gates serialize
grows the number of queued branches exposed to that cycle. The tests run at the
gate remain fresh correctness evidence; what becomes stale is the causal claim
that those tests catch the injected defect.

Price this honestly: the task measured a queue of eight and gates of 7–9
minutes; it did not measure how many re-arms a scratch design saves or adds.
The known direction is adverse—more finished work can queue behind each ref
advance—so no throughput rate is claimed.

Mitigation is a gate-readiness state machine, not a coordinator doing a blind
rebase:

```text
author-finished(base B, evidence B)
  -> queued-current (only while master == B)
  -> needs-rearm (as soon as master moves)
  -> active owner rebases + full forget/begin/sabotage/observe/restore/check
  -> queued-current(new base, new evidence)
  -> serial gate
```

- A drain runner may automate transitions and start the next gate, but it may
  not label `needs-rearm` as ready or fabricate evidence itself.
- The re-arm owner is either the still-live original lane or a newly dispatched
  re-arm lane with the branch, registry, expectation source, and exact observed
  command. A finished agent's branch is never rebased silently at the gate.
- Admission control caps the **finished landing queue**, not necessarily all
  useful work. When the cap is reached, spare delegation can do review, design,
  or the next queued re-arm rather than create more stale landing work.
- Queue-by-contention remains a cheap conflict heuristic. It does not waive a
  rebase or re-arm merely because files are disjoint.

The dispatch refusal should be relaxed only when the corpus snapshot and the
`needs-rearm` ownership transition are both enforced. That makes the increased
re-arm frequency a scheduled cost instead of degraded evidence.

## Question 4 — crash residue moves to the scratch worktree

Today the breadcrumb is written under the main checkout and recovery says to
switch that checkout back to `master` (`dev/land_lane.py:133-192,1558-1582`).
With scratch gating the dangerous main-detached state disappears, but the old
breadcrumb wording becomes false. A killed gate instead leaves a registered
scratch worktree whose detached HEAD keeps the provisional merge reachable;
`master` and the main working tree remain untouched.

Keep the breadcrumb in the shared main `.dreamwork` directory so the next gate
and launch can find it. Extend its schema with at least `gate_worktree`,
`common_git_dir`, `base_ref`, `base_sha`, `branch`, `branch_sha`, `merge_sha`,
`phase`, and `pid`. Write it before the scratch worktree becomes authoritative,
update it after worktree creation and each phase, and clear it only after
verified cleanup. An unreadable record is a refusal, not “no gate.”

Recovery becomes:

1. Read the breadcrumb and distinguish live pid, dead pid, and unreadable
   record.
2. Prove the recorded path is exactly the registered scratch worktree for this
   gate; never remove an inferred or broad path.
3. Prove `master` is still at the recorded `base_sha` or report that it moved.
4. Remove the exact registered scratch worktree, verify its registration and
   path are gone, then clear the breadcrumb. If any proof fails, retain both and
   print the manual recovery facts.

SIGTERM/SIGINT and ordinary exceptions may attempt that cleanup. SIGKILL,
`os._exit`, a segfault, or power loss cannot; the durable breadcrumb and the
registered worktree cover those cases. A message must say which path it
actually detected. `deploy_state` needs no relaxation: it should still refuse a
detached checkout in general, while the main checkout used for deployment no
longer enters that state during a gate.

## Dispatchable increments

### Increment 1 — move the gate, preserve the refusal

**Files:** `dev/land_lane.py`, `dev/launch_lane.py`, `test_land_lane.py`,
`test_launch_lane.py`, and `.dreamwork/docs/file-formats.md` for the breadcrumb
schema. Do not change `dispatch_lane` or lint corpus semantics yet.

**Implementation:** add the whole-run gate mutex and short repository-state
mutex; create one exact-base detached scratch worktree; run provisional merge
and every post-merge command there; keep main attached; perform one checked
`merge --ff-only` in main; clean the scratch worktree on every judged exit;
reshape the breadcrumb and dead-gate recovery; and make `launch_lane` explicitly
refuse while that live gate exists so corpus safety is unchanged.

**Tests:** run the full touched files with `just pytest test_land_lane.py
test_launch_lane.py`, plus `just pytest $(python3 dev/repo_wide_guards.py list)`
and `python3 lint.py`. The tests must prove: main stays on `master`; scratch is
created at the exact captured SHA; merge/tests/lint run with scratch cwd;
parents are exact; a moved `master` refuses before advance; a second gate
refuses; launch refuses explicitly during Increment 1; clean refusal removes
scratch; dead breadcrumb retains and names the exact scratch; cleanup failure
retains the breadcrumb; and success advances once then removes scratch.

**Red-proof subject:** `dev/land_lane.py::land`, with `test_land_lane.py` as the
tracked expectation source. Inject the old defect by routing the provisional
merge command back to the main checkout (or by substituting `repo` for the
scratch cwd). The discriminating assertion should say **“provisional gate
command ran in main checkout”**, not merely that a subprocess failed.

**Direction-2 false-green to close:** a test that only checks “main is still on
`master`” passes if commands accidentally run in the lane worktree, or in a
scratch worktree created from the wrong SHA. Bind the cwd to the registered
scratch path, assert its initial HEAD equals `base_sha`, assert merge parents,
and separately move `master` before advance to prove the compare-before-advance
refuses. The actual diff classifier decides the injection count; this plan does
not assume it.

### Increment 2 — immutable corpus subject

Coordinate with the `#867` owner before touching its reader/writer surface.
Define the corpus snapshot interface and identity across `dev/dispatch_lane.py`,
`lint.py`, and `dev/land_lane.py`, with focused tests in `test_dispatch_lane.py`,
`test_lint.py`, and `test_land_lane.py`. Only after baseline/precheck/comparison
prove the same snapshot may the live-gate dispatch refusal narrow to the
snapshot critical section.

### Increment 3 — owned re-arm and drain

Add an explicit `needs-rearm` queue state and owner, then automate serial drain.
Do not batch gates in this increment. Measure gate idle gaps, queue age, re-arm
cycles, and landed branches before claiming a rate improvement; a report that
the fleet stayed busy is not a certification that landing throughput rose.

## Task-record authority used

Every numbered task cited above was opened from the live ledger before this
plan was written. Relied-on lines:

- **`#997`:** “the gate does not have to run in the main checkout at all.”
- **`#967`:** “A wrong premise silently converts into wrong work that passes its
  own gate, because the gate checks the work against the brief and the brief is
  what is wrong.”
- **`#773`:** “the hazard window is WIDER than #773's sentence describes — it
  is not only 'dispatch during a gate' but 'any brief-corpus write overlapping a
  gate's lint-baseline'.”
- **`#867`:** “you cannot untrack the corpus and leave the checks reading git
  history, because untracking DESTROYS the only record those checks consult.”
- **`#993`:** “THE VERDICT: a full re-arm is required after every rebase.”
- **`#1120`:** “Note (1) cannot cover SIGKILL, so (2) is what makes the state
  DISCOVERABLE rather than merely rare.”
- **`#994`:** “Justification correctness is NOT CHECKED and requires human
  judgment” rather than letting claim presence read as correctness.
- **`#136`:** “THREE zero-states, not one: missing ... present-but-unparseable
  ... genuinely empty.”
- **`#651`:** “a guard's message must name a mode the guard can actually
  detect, and the way to know is to construct that mode and watch it fail.”

## Decision boundary

Proceed with Increment 1. It is useful even before throughput is unlocked: it
removes the main checkout from provisional execution, keeps deployment attached,
and gives crashes an isolated residue. Do **not** claim Task `#997`'s fleet-idle
cost recovered until Increment 2 lets dispatch coexist with one fixed lint
population and Increment 3 supplies a re-arm owner. Reopen the IGC if either
interface cannot be made fail-closed without holding the whole gate interval.
