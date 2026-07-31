# Lane 762 report

## Outcome

`dev/reap.py` (invoked as `just reap-lane <path>`) gated the removal on
tracked dirt and unmerged commits — and then handed `git worktree remove`
the target **without** `--force` unless the tool's own `--force` was set.
But `git worktree remove` refuses on **any** untracked file, and
`BRIEF.md` is untracked in every lane by construction (the coordinator
writes it into each worktree and never tracks it). So the happy path
could never complete for any real lane: the gate said OK, and the
removal refused anyway. A coordinator who typed `--force` habitually —
because it was the only thing that worked — had silently disabled the
tracked-work gate, the exact "a gate people learn to `--force` past is
worse than no gate" failure `#686` was built to avoid and `#755`
measured, reintroduced one layer down.

One flag carried two meanings:

1. *let git remove despite untracked scratch* — **always** needed;
2. *override my gate and discard tracked work and unmerged commits* — needed almost never.

The fix separates them: **once the tool's own gate has PASSED, `--force`
is passed to `git worktree remove` unconditionally.** The gate has
already established there is no tracked dirt and no unmerged commit; git's
untracked-file refusal is a cruder check the tool has superseded, and
`BRIEF.md`/`__pycache__` are precisely what it is refusing over. The
tool's own `--force` then means **only** "override my gate" — which is what
its help text already claimed: *"override refusals, printing every
discarded path and commit"*.

What changed in `dev/reap.py` (the removal block, lines ~213-227):

- `args` is now `["worktree", "remove", "--force", str(target)]`
  unconditionally — the conditional `if force: args.append("--force")`
  is gone.
- The stale remove-failure hint (`if (untracked or ignored) and not
  force: print("Rerun with --force …")`) is gone: it named a recovery
  path that no longer exists, because the happy path no longer refuses on
  untracked scratch.

Every property `#686` and `#760` proved is preserved (each verified in
the red-proof below):

- the gate stays **tracked-only** (`#755`) — `unsafe = bool(tracked or
  commits)` is unchanged; the unconditional `--force` never runs when the
  gate refuses, because the gate returns 1 before reaching the removal;
- `--force` still prints **every** discarded path and commit before
  proceeding (`#702`) — the `if force:` discard-reporting block is
  unchanged and runs before the removal;
- denominators still print on the **clean** run (`#671`) — unchanged;
- REFUSE-on-cannot-establish still **exits 2** rather than reading as
  clean (`#136`) — the `_unknown` early returns are unchanged and fire
  before the removal;
- untracked and ignored stay **separate**, and paths beyond
  `EXPECTED_UNTRACKED` are still named (`#760`) — unchanged;
- refuses when the target is not a **registered linked worktree**, never
  the main checkout — unchanged;
- `git cherry <base> HEAD` still refuses a clean lane carrying commits
  absent from the base — unchanged.

### The test gap that let this ship — closed

`test_reap.py` (11 tests) proved the gate's **verdict** but never proved
the **removal completes**. That is why a tool whose happy path cannot run
for any real lane passed its own suite. The new test
`test_real_lane_scratch_is_removed_without_force` reproduces the exact
real-lane shape — `BRIEF.md` (untracked) + `__pycache__/` (ignored) — and
asserts the gate passes **and** the directory is gone and the worktree is
deregistered. This is `#671` in the suite itself: the existing tests
examined the verdict and nothing examined the outcome.

## Commits

- `92f0e683 fix(#762): pass --force to git unconditionally once the gate has passed`

## Red proof

### Direction 1 — the happy path cannot complete for any real lane

Reproduced on a scratch worktree (never a live lane) holding only the
per-lane scratch every real lane carries. The gate **PASSED**; the
removal **REFUSED** (exit 2) on the untracked `BRIEF.md`:

```
=== gate check first (should PASS, the happy path) ===
reap examined path=/tmp/.../lane tracked-dirty=0 untracked=1 ignored=1 unmerged-commits=0
reap gate OK (check only)
check rc=0

=== now the actual removal with CURRENT code (no --force) ===
REFUSE: git worktree remove failed: fatal: '...lane' contains modified or untracked files, use --force to delete it
Rerun with --force to print and explicitly discard scratch paths.
reap examined path=/tmp/.../lane tracked-dirty=0 untracked=1 ignored=1 unmerged-commits=0
remove rc=2
```

Under the fix the same scratch lane removes cleanly and the directory is
gone. The new test `test_real_lane_scratch_is_removed_without_force`
binds this end-to-end and was RED against the current (buggy) code:

```
E       AssertionError: REFUSE: git worktree remove failed: fatal: '...' contains modified or untracked files, use --force to delete it
E         Rerun with --force to print and explicitly discard scratch paths.
E       assert 2 == 0
```

The deliberate production injection (`dev/redproof.py begin`/inject/`restore`)
reintroduced the conditional `--force` (`args = ["worktree", "remove"]`
with `if force: args.append("--force")`). The new test failed red at the
discriminating assertion — the worktree still exists after a gate that
passed. `restore` brought the fixed file back; the test went green. The
injection reached the code under test: it changed the `args` list the
subprocess executes, which the test reads via the CLI subprocess — no
scaffolding stood in front of it.

### Direction 2 — the ordering (gate first, unconditional --force second)

The concern the change introduces: with `--force` now always passed to
git, tracked dirt could be destroyed if the gate does not refuse first.
Injected by dropping `tracked` from the gate's `unsafe` condition
(`unsafe = bool(commits)`), proving that when the gate fails to refuse
tracked dirt the unconditional `--force` would destroy it. Both
tracked-dirty gate tests went red:

```
>       assert result.returncode == 1
E       AssertionError: assert 0 == 1
E        +  where 0 = ...stdout='... tracked-dirty=1 untracked=0 ignored=0 unmerged-commits=0\nreap gate OK (check only)\n'...
```

The gate read `tracked-dirty=1` but printed "reap gate OK" (rc=0) — the
tracked dirt was no longer gated, so the unconditional `--force` would
have destroyed it. The injection reached the code under test: the
production line `unsafe = bool(tracked or commits)` directly controls the
REFUSE branch the tests assert via the CLI subprocess. Restored; both
tests green. This proves the **ordering** rather than asserting it: the
gate is what protects tracked work, and the unconditional `--force` never
runs when the gate refuses, because the gate returns 1 before reaching
the removal.

(The other direction-2 candidates the brief named are covered by existing
tests that did not change: a lane carrying unmerged commits with a clean
tree still refuses via `test_clean_branch_with_unmerged_commit_refuses`;
a target that is the main checkout or an unregistered path still refuses
via `test_non_worktree_is_unknown_not_clean`.)

Final `python3 dev/redproof.py check --require 1` output, verbatim:

```text
history: EXAMINED NO COMMIT — 0 between c9c0976f3f28 (master) and HEAD. Nothing of this branch is in history yet, which is not the same as a history examined and found clean.
check: clean — 2 injection(s) registered, all restored and absent from the working tree and from this branch's commits:
  dev/reap.py (sha 2975ad737bc3, hint: 'args = ["worktree", "remove"]')
  dev/reap.py (sha e5175312102e, hint: 'unsafe = bool(commits)')
```

## Verification

`test_reap.py` was 243 lines / 11 tests as landed. After: 274 lines /
12 tests (1 new `#762` test).

```text
python3 -m pytest -q -n 2 test_reap.py
12 passed in 2.16s
```

```text
python3 lint.py
clean (6 warning(s))
```

The six warnings are the expected worktree-only baseline (`#611`/`#667`:
the gitignored ledger store does not travel, so the ledger checks
examine nothing; `lessons.md` near-duplicate pair; `tasks.md` row
yielded no entries). No ERRORs. Inspected per-message, not by total.

No browser guards were run and no ports were bound. Tests limited to 2
threads (`-n 2`).

## DOGFOOD REPORT

- **The brief was exactly right and a pleasure to work from.** The
  one-paragraph diagnosis, the recommended fix, the red-proof
  directions, the properties to keep, and the governing lessons were all
  precise. Nothing was wrong or misleading.
- **`dev/redproof.py` was clean to use for two injections.** The
  `begin`/inject/`restore`/`check --require 1` cycle made both
  directions checkable. The `#717` dedup (distinct injections append,
  same bytes collapse) worked as documented — direction 1 and direction
  2 injected the same file with different sabotages and both landed as
  separate entries.
- **The test-suite gap the brief named (#671 in the suite) was real and
  is now closed.** The existing 11 tests exercised the gate's verdict and
  the `--force` discard path but never a happy-path removal over
  untracked scratch — so the bug was invisible to the suite. The new
  test reproduces the exact real-lane shape and asserts the outcome.
- **Master moved during the run** (the `#758`/`#759` pytest-recipe work
  from `lane-cx-758759` landed, 4 commits). Neither of my files was
  touched; rebase is expected clean.
- **One small residual worth noting** (not a defect in the fix): with
  `--force` now always passed to git, a `git worktree remove` that fails
  for a reason *other* than untracked files (e.g. the worktree is locked
  via `git worktree lock`) will also be overridden silently. This is
  extremely unlikely in the lane model (lanes are not locked), and the
  gate's pre-checks (registered linked worktree, status, cherry) catch
  the cases that matter. Naming it so a future reader knows the
  unconditional `--force` covers git's lock refusal too.
