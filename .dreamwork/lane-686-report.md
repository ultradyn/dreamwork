# Lane 686 report

## Outcome

Built a standalone `dev/reap.py` invoked through the supported coordinator recipe
`just reap-lane <path>`. I chose the standalone-tool option because the policy is
substantial enough to test directly, while the recipe leaves one short supported
removal command. The literal `just reap` name was already occupied by the unrelated
stale-dashboard-process reaper, so reusing it would have broken an existing interface.

The gate:

- proves the target is a registered linked worktree, never the main checkout;
- reads `git status --porcelain=v1 -z --untracked-files=all --ignored` and gates only
  tracked paths, including index-only changes;
- reports `path`, `tracked-dirty`, `untracked-ignored`, and `unmerged-commits` on every
  classified run;
- returns an unknown/refusal (exit 2) when the worktree, status, or base comparison
  cannot be established;
- uses `git cherry <base> HEAD` to refuse clean lanes carrying commits absent from the
  base;
- invokes `git worktree remove` only after the checks pass;
- permits an explicit `--force`, but first prints every tracked, untracked, and ignored
  path plus every unmerged commit whose warning is being overridden.

This directly preserves #404's premise: "a lane cannot land work without committing".
The gate catches the premise failing before the supported removal command destroys the
only copy. It also makes the #677/#679 prose rule executable, preserves #440's one
supported path, reports #671 denominators, reports rather than drops #702 unknowns, and
does not fire on #755's healthy BRIEF/cache-only lane.

## Commits

- `db6078e8 feat(#686): gate lane worktree reap`
- `1325b009 test(#686): bind reap route and status failure`

Rebased onto current `master` before reporting. `git rev-list --count HEAD..master` = 0.

## Red proof

Direction 1 is bound by integration tests:

- a dirty tracked file refuses with `tracked-dirty=1` and names `tracked.txt`;
- an index-only staged change refuses identically;
- a lane carrying only untracked `BRIEF.md` and ignored `__pycache__/` passes the gate
  with `tracked-dirty=0 untracked-ignored=2`.

The deliberate production injection changed the final status classification from
`else "tracked"` to `else "ignored"`. The tracked-dirty test then failed at the
discriminating assertion because the tool returned 0 and printed the false clean result:

```text
E       AssertionError: assert 0 == 1
E        +  where 0 = CompletedProcess(... stdout='... tracked-dirty=0 untracked-ignored=1 unmerged-commits=0\nreap gate OK (check only)\n', stderr='').returncode
```

`dev/redproof.py restore dev/reap.py` restored the fixed snapshot, and `cmp` against the
lane-private snapshot succeeded. The focused test then passed and `git diff --exit-code
-- dev/reap.py` was clean.

Direction 2 is real and covered: a clean worktree with one branch commit absent from
`master` returns 1, reports `unmerged-commits=1`, and prints the commit SHA and subject.
The gate cannot see files mistakenly written into the main checkout (#465); that remains
outside this worktree-local check and is correctly not claimed as covered.

Final `python3 dev/redproof.py check --require 1` output, verbatim:

```text
history: examined 2 commit(s) since 2fde20542db1 (master) against 1 injected path(s); read 2 blob(s), 0 holding a recorded injection.
check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits:
  dev/reap.py (sha 54c1dc940f87, hint: 'kind = "untracked" if code == "??" else "ignored"')
```

## Verification

```text
python3 -m pytest test_reap.py -q -n 2
9 passed in 2.51s

python3 -m pytest test_lint.py -q -n 2
535 passed in 42.68s

python3 lint.py
clean (6 warning(s))
```

The six warnings are the brief's expected worktree-only warnings; there were no ERRORs.
No browser guards were run and no ports were bound.

## DOGFOOD REPORT

- The brief's preferred spelling `just reap <lane>` collides with the established
  process-reaper recipe (`dev/reaper.py`). I used `just reap-lane <path>` so neither
  interface is overloaded. The brief should acknowledge this existing name when offering
  the recipe option.
- The brief's warning expectation was exact: lint finished clean with 6 warnings.
- `dev/redproof.py` made the fixed-file snapshot/restore trail clear and its final check
  remained valid after the mandatory rebase. No other loop friction found.
