# Lane 758759 report — #758 and #759

## Verdict

PASS. Both corrections landed as separate commits, the branch was rebased onto
the moved `master`, targeted verification is green, lint has no ERRORs, and the
red-proof registry is clean.

## Landed changes

- `3f7544562b5ba5cbf28755a03819137f28eb3eae` — `fix(#758): restore one
  advisory pytest command`
  - `pytest *ARGS:` forwards lane selections while preserving the #666
    concurrency advisory.
  - The boilerplate once again names `just pytest` as the one supported lane
    command.
  - Two dry-run contract tests bind argument forwarding, advisory order, and
    the unchanged bare full-suite command.
- `febd6d6a85eec47d258164b9ce9e725a47550e82` — `fix(#759): freeze
  real-path parity subjects`
  - The boilerplate now requires a frozen subject and pinned baseline
    interpreter revision, varies only the intended interpreter change, and
    labels raw live readings as context rather than proof.
  - It names the reverse failure: honest drift misread as a lane regression,
    or drift rounded away to satisfy an impossible brief.

The two inherited 202/203-character lines are now hard-wrapped. I considered
mass-editing historical briefs and deliberately did not: #398/#405/#587/#756
make the rule forward-only, and the brief explicitly forbids rewriting them.

## Red-proof — #758

Direction 1, pre-fix command:

```text
$ just pytest -q test_lint.py
error: Justfile does not contain recipe `-q`
```

The fixed recipe accepts the same arguments and runs the advisory first:

```text
$ just pytest -q test_concurrent_tests.py::TestJustPytestRecipe
python3 dev/concurrent_tests.py
concurrent tests: 1 other pytest suite; 37 browser/guard processes; mem: swap
53G/61G used (...) (advisory)
python3 -m pytest -q -q test_concurrent_tests.py::TestJustPytestRecipe
..                                                                       [100%]
```

The actual bare invocation still ran the full suite:

```text
$ just pytest
python3 dev/concurrent_tests.py
python3 -m pytest -q
2364 passed, 2 skipped, 1 warning, 65 subtests passed in 312.24s (0:05:12)
```

Direction 2 is real and intentional: replacing the advisory command with
`-false` still forwarded the selected test and continued because the leading
`-` makes advisory failure non-gating:

```text
false
python3 -m pytest -q test_concurrent_tests.py::TestInvocationForms::test_empty_argv_is_none
.                                                                        [100%]
1 passed in 0.19s
```

The new dry-run test detects this omission even though the recipe itself must
continue: its expected first command is exactly
`python3 dev/concurrent_tests.py`.

## Red-proof — #759

No live landing occurred during two adjacent raw reads, so these are context,
not the proof:

```text
LIVE_ONE count=168 sha=8eed5b61d3370a79bfb7585d96fbfaba2838d0618f70127e0ef5fab74bcfa7c3
LIVE_TWO count=168 sha=8eed5b61d3370a79bfb7585d96fbfaba2838d0618f70127e0ef5fab74bcfa7c3
LIVE_IDENTICAL=0
```

I therefore constructed the moving-subject case with a scratch SQLite backup
and mutated only that fixture through `ledger.py file --ledger <fixture>`:

```text
MOVING_BEFORE count=168 sha=8eed5b61d3370a79bfb7585d96fbfaba2838d0618f70127e0ef5fab74bcfa7c3
filed #763 (store)
MOVING_AFTER  count=169 sha=ebc5b8f914b681e2be9fef12edb98f3cc95f1135d531bf822a6082fe97f5631f
MOVING_IDENTICAL=1
```

Exit `1` from `cmp` is the expected not-identical result. Against one frozen,
read-only backup, the unchanged main-checkout interpreter and modified
worktree interpreter produced byte-identical JSON:

```text
FROZEN_MAIN     count=168 sha=8eed5b61d3370a79bfb7585d96fbfaba2838d0618f70127e0ef5fab74bcfa7c3
FROZEN_WORKTREE count=168 sha=8eed5b61d3370a79bfb7585d96fbfaba2838d0618f70127e0ef5fab74bcfa7c3
FROZEN_IDENTICAL=0
```

Direction 2 was injected separately. Wording that froze only the subject but
did not pin the baseline interpreter failed with:

```text
AssertionError: baseline code can move during parity proof
```

That is why the landed wording binds both the subject and baseline revision,
leaving only the intended interpreter change variable.

## Verification

- Before: `550 tests collected` for `test_lint.py test_concurrent_tests.py`.
- After: `552 tests collected`; the increase is the two recipe contract tests.
- `python3 -m pytest -q -n 2 test_lint.py test_concurrent_tests.py`:
  `552 passed in 39.32s`.
- `python3 lint.py`: `clean (6 warning(s))`, with no ERRORs. Every warning was
  inspected: three expected worktree/absent-ledger identities (`tasks.md`
  absent, `status.json` absent, zero-entry/ledger checks examined nothing),
  the pre-existing three undated answered questions, and the pre-existing
  lessons near-duplicate.
- No browser guard was run and no port was bound or touched.
- `master` advanced by seven commits. `git rebase master` completed without a
  conflict; final base is `c9c0976f3f2881b5ca6dfaa7ebb88d6552568014`.

Required final red-proof check, verbatim:

```text
history: examined 2 commit(s) since c9c0976f3f28 (master) against 2 injected path(s); read 4 blob(s), 0 holding a recorded injection.
check: clean — 2 injection(s) registered, all restored and absent from the working tree and from this branch's commits:
  justfile (sha 254e9acf97ea, hint: '-false')
  briefs/boilerplate.md (sha b897bfb391bd, hint: 'or pinned revision), then compare the two interpreters against it. Report raw live readings as')
```

## DOGFOOD REPORT

- The brief mandated an actual bare `just pytest` full-suite proof while the
  standing lane rule says lanes never run the full suite because the
  coordinator owns it. The task-specific instruction won, but it cost 5m12s
  and duplicated the merge gate. A dry-run plus the contract test proves the
  no-argument command shape; if execution is still required, the brief should
  call out this intentional exception explicitly.
- The brief said #756 was four commits ago, but the dispatched base had moved
  well past that point. The named merge SHA remained easy to find, so this was
  stale orientation rather than a blocker.
- The brief did not state the base SHA even though the current dreamwork lane
  contract requires one. I measured the dispatch base as
  `c3e01017e50e...`, detected the later seven-commit move, and rebased before
  reporting.
- No other tooling friction or out-of-scope defect was found.
