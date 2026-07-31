# Lane #747 report — fleet denominator and permitted pairings

## Verdict: Q1 is PROCESSES

The live denominator must be **live process records, not unique task ids**.
The number is printed immediately beside `delegation`, which `SKILL.md`
defines as an average-concurrency target for agents. Two supported agents
pairing on one task consume two units of that concurrency. Collapsing them to
one task understates the measured fleet and biases the drift signal toward
dispatching another agent.

This does not claim that a task is a worktree. The available accessor does not
measure worktrees: `status_sync.live_lanes` returns a set of task ids and the
verbatim live `pruned` process records. The set is intentionally lossy for this
display; the records retain both processes and their dispatch provenance. If
duplicate records for one PID are possible, that is a separate data-integrity
question, not a reason to deduplicate by task.

### IGC decision

Context: choose the live denominator rendered beside an average agent-
concurrency target, while supported agents may pair on one task/worktree.

| Idea | All | G1: equals agent concurrency | G2: permitted pairing is numeric | G3: preserves dispatch provenance | G4: accessor expresses it |
|---|:---:|:---:|:---:|:---:|:---:|
| Count live process records | ✔ | ✔ | ✔ | ✔ | ✔ |
| Count unique task ids | ✘ | ✘ | ✘ | ✔ | ✔ |
| Count unique worktrees | ✘ | ? | ✔ | ✔ | ✘ |

The decisive error for task ids is G1: two live agents consume two concurrency
slots but render as one, creating apparent under-delegation. Unique worktrees
cannot be chosen here because the live records do not carry a worktree identity;
using `task` as its proxy would assert an equivalence the data does not express.

## Q2 and implementation

Commit `d5bdc1a61b81ca1644ee190ddce0f45c9cff4e11` replaces both task-id sets with
sums over the verbatim live records and removes only the cross-dispatch
intersection raise. A ccc process and an Agent-tool process on one task now
render as:

```text
lanes 0 recorded · 1 ccc + 1 agent-tool live · delegation 5
```

The unknown-dispatch raise remains untouched, as required. The `_fleet_fact`
docstring now states that the live denominator is processes and ties that
choice to the average-concurrency target.

Commit `99078974f2daa6707248465e22ae9e8672ed104d` adds/binds three cases:

- two ccc processes on one task count as two;
- one legacy ccc process (absent `dispatch`) plus one Agent-tool process on one
  task render as the numeric line above, never `FLEET UNRESOLVED`;
- two recorded lanes whose processes are dead render `2 recorded` beside
  `0 ccc + 0 agent-tool live`, preserving the documented disagreement rather
  than flattening the two sources.

## Red-proof

### Direction 1 — restore the rejected task-set implementation

I used `python3 dev/redproof.py begin tick_line.py`, restored the task-id sets
and cross-dispatch raise, then ran the exact final pairing test. The
discriminating failure was:

```text
assert 'lanes 0 recorded · 1 ccc + 1 agent-tool live · delegation 5' in
'FLEET UNRESOLVED (LivenessUnknown: live task has multiple dispatch paths) · delegation 5 ...'
```

`python3 dev/redproof.py restore tick_line.py` reported that the injected state
was recorded and the original restored and verified. `cmp` against its
lane-private snapshot succeeded.

### Direction 2 — try inputs that could leave a misleading green

The stale-record/dead-process construction rendered:

```text
lanes 1 recorded (ccc 1) · 0 ccc + 0 agent-tool live · delegation 5 ...
```

So process counting did not flatten authored bookkeeping into OS liveness. The
absent-dispatch construction rendered:

```text
lanes 0 recorded · 1 ccc + 0 agent-tool live · delegation 5 ...
```

So the historical absent field remains the observable ccc default. The final
tests pin both properties. I found no remaining false-green for the chosen
denominator within the supported inputs. Duplicate records carrying the same
PID remain an unpriced, out-of-scope integrity case rather than a pairing case.

Hand-off gate, quoted:

```text
history: examined 3 commit(s) since ecd3a09f7010 (master) against 1 injected path(s); read 3 blob(s), 0 holding a recorded injection.
check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits:
  tick_line.py (sha fb36cf010db9, hint: 'ccc_live = {')
```

## Verification and rebase

- Before: `python3 -m pytest test_tick_line.py` collected 46; **46 passed**.
- After rebasing: the same command collected 48; **48 passed**.
- `python3 lint.py`: **clean (6 warning(s))** and no ERRORs. The warnings are
  the worktree's absent ledger/status projections plus existing repository
  warnings; the output explicitly refuses to call those skipped checks clean.
- `python3 dev/redproof.py check --require 1`: clean, quoted above.
- Rebased successfully onto local `master` at
  `ecd3a09f7010750bb63fa6e07fb630e33f1659ea`; no conflicts occurred.
- No browser guards were run, per the task brief.

## Relied-on ledger citations

- **#747:** “Two processes pairing on ONE task now count as 1” and “If
  processes wins, both the set-comprehension and the raise go.” This is the
  decision and requested consequence implemented here.
- **#727:** “The COUNT is more honest; the LABEL is now wrong.” This preserves
  the already-landed ccc/Agent-tool labels while changing only their
  denominator.
- **#136:** “present-but-unparseable is a fault and must look like one.” The
  relied-on distinction is that an
  understood, permitted pairing must not render as an unresolved fault.
- **#702:** “Malformed task ids are KEPT and reported loudly rather than reaped
  as dead.” The relied-on principle is to retain fail-closed reporting for
  genuinely unclassifiable input rather than silently bucket it.

## Out of scope finding

The requested unknown-dispatch raise is preserved, but it appears unreachable
today: `_fleet_fact` first filters `clean` through `status_sync._observable`,
whose closed observable set is only absent/ccc/agent_tool, and then searches
the resulting `pruned` records for any other dispatch. An unknown dispatch is
removed before that search. The intent of the raise is correct; its current
placement cannot enforce it. Fixing that would require changing the accessor
boundary or prefilter and is expressly outside this lane's scope
(`status_sync.py` is off-limits), so I did not alter it.

## DOGFOOD REPORT

The task brief's substantive premise, requested red-proof directions, absolute
ledger command, and no-`attn` rule were all accurate and useful. The mandatory
second thread improved the final fixture by binding absent `dispatch` and the
stale-record/dead-process disagreement.

One boilerplate citation was misleading: it says “Volume (`#612`): land your
change as the fewest lines that carry the meaning,” but ledger entry **#612**
instead concerns one 4KB hand-off dominating the whole lint report. The
principle is sensible,
but that issue does not establish the general scope rule. This cost a required
ledger lookup and confirms that copied boilerplate citations need independent
resolution.

Graph-first discovery worked after indexing this worktree, but symbol regexes
for some module-level helpers returned no graph nodes while graph-augmented
code search found them immediately. That was recoverable without broad grep.
