# Lane 743 report — sweep resolves against `--repo`

## Verdict

Complete. `sweep` now passes its subject repository through `sweep_text()` to
`_resolved_cites()` and runs `git -C <repo> cat-file --batch-check`. Resolver
timeouts and executable/OS failures fall back to the documented substring
predicate, keep the advisory exit-0 contract, and add an explicit `DEGRADED`
line to the report.

Changed only `dev/ledger.py`, `test_ledger.py`, and this report. The parser was
not touched, so the every-verb coverage map needed no change.

## Red proofs

### Defect 1 — resolver substituted the process CWD

The test creates independent `target` and `cwd` repositories, changes the
process CWD to the latter, and derives both preconditions at runtime:

```text
target_repo_resolves=True
cwd_repo_resolves=False
```

With the fixed `git -C <repo>` line sabotaged back to bare `git cat-file`, the
test failed on the discriminating assertion:

```text
AssertionError: #465 cites 414b7de, which resolves to
414b7def8d38b8fd2e2c884bb247c87b4569aee8 under --repo; the resolver must not
substitute the unrelated CWD repo
```

The output named `#465` as uncited. Restoring the fixed file made that exact
test pass.

### Defect 2 — unavailable git crashed or degraded silently

The committed test is parametrized over `subprocess.TimeoutExpired` and
`OSError`. It requires both the substring-fallback result (the different-width
`#465` citation remains a finding) and the visible `DEGRADED`/`substring` line.

For the red proof I sabotaged only the visibility flag, leaving the exception
handler and substring fallback active. The test therefore reached the report,
named `#465`, and failed on the intended distinction:

```text
AssertionError: the fallback must say it fired, not merely avoid an exception
```

Restoring the fixed file made the timeout case pass; the final suite also
passes the `OSError` case.

### Direction 2 — open false-green beyond both fixes

The legacy substring fast path still accepts a full foreign-shaped SHA merely
because it begins with the local `%h`. Constructed after both fixes and after
the final rebase:

```text
local_short=4cfd011f
foreign_full=4cfd011fffffffffffffffffffffffffffffffff
local_short_resolves=True
foreign_full_resolves_locally=False
sweep: nothing to review (this ran — see the examined count above)
```

This is a real remaining gap in the predicate: because `local_short in body`
is true, the pair never enters the resolution residue, so sweep suppresses the
row without checking that the cited full SHA names the local commit. I did not
widen #743 into changing the legacy fast path; the coordinator should file it
as a separate task.

## Verification

After rebasing cleanly from original base `4e83d224` onto local `master`
`b73e4a34`:

```text
python3 -m pytest -n 2 test_ledger.py test_ledger_cli.py test_ledger_write.py
122 passed in 3.86s

python3 lint.py
clean (6 warning(s))
```

The six lint warnings are the explicit worktree/store and pre-existing warning
rows; there were no ERRORs.

Final red-proof gate, quoted verbatim:

```text
history: examined 2 commit(s) since b73e4a349c08 (master) against 1 injected path(s); read 2 blob(s), 0 holding a recorded injection.
check: clean — 2 injection(s) registered, all restored and absent from the working tree and from this branch's commits:
  dev/ledger.py (sha 58a778927d15, hint: '["git", "cat-file", "--batch-check"],')
  dev/ledger.py (sha 8e2adcecb235, hint: 'return substring, False')
```

Post-rebase commits:

- `e70c5629` — `test(#743): expose repo-subject and degraded sweep failures`
- `4cfd011f` — `fix(#743): resolve sweep citations in the subject repo`

## Relied-on issue text

- #743: “`--repo` is the subject; the bare git call silently substitutes the
  interpreter's location.”
- #724: “Resolution, not startswith — a 4-char citation prefix-matches many
  commits.”
- #607: “The path you invoke is the INTERPRETER; `--target`/`--ledger` is only
  the SUBJECT.”
- #404: “advisory, exit 0 on every failure mode.”
- #671: the broken sweep's count was real while “the ‘nothing to review’ is
  false, and the two together read as a positive all-clear.”
- #136: “present-but-unparseable is a fault and must look like one.”
- #612: “A report nobody can skim is a report nobody reads.”
- #349: “Revert a deliberate RED injection with the inverse of the injection,
  never with `git checkout <file>`.”

## DOGFOOD REPORT

No additional loop-tooling friction found. `dev/redproof.py` safely handled two
separate injections into the same file, restored and verified each snapshot,
and its final history scan remained correct after the rebase. The worktree lint
warnings explicitly said which ledger checks examined nothing, so they did not
masquerade as a clean ledger review. The direction-2 foreign-prefix false-green
above is the only out-of-scope finding.
