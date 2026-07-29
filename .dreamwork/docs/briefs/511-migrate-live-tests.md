# Brief — #511: master is RED — the four "live ledger" migrate acceptance tests are stale against the #294 shim

Lane-owns: `test_tasks_migrate.py`, `test_tasks_migrate_verify.py`, `test_tasks_migrate_history.py`, `.dreamwork/handoffs.md` (append ONE `## Pending` line)

## The defect (verified, not guessed)

`python3 -m pytest -q` on master has exactly **4 failures**, all "live ledger"
acceptance tests from the #294 migration tooling:

- `test_tasks_migrate.py::test_live_ledger_acceptance` — `assert 65 == 0`
- `test_tasks_migrate_history.py::test_live_history_recovers_real_groomed_ids`
- `test_tasks_migrate_verify.py::test_live_ledger_import_acceptance` —
  `_Unparseable: no '## Open' section heading — not a task ledger`
- `test_tasks_migrate_verify.py::test_live_groomed_stub_row_fails_verify`

Root cause: these tests read `LIVE_LEDGER = .dreamwork/tasks.md` expecting the
parseable Markdown ledger. Since the cutover (`03d10a9e`, #294 R4) that file is
the **migration-notice shim**; the frozen pre-cutover ledger is
`.dreamwork/tasks.md.deprecated` and the live truth is the SQLite store
(`.dreamwork/ledger.sqlite3`). Verified pre-existing: all four FAIL at
`76367115` in a clean worktree, so no today's lane caused them. A check that
went stale when its fixture's meaning changed — the repo's own "become hollow"
lesson, except here it became loudly red rather than silently green.

## The judgment call — yours to make and defend

The migration is **executed**. So the question is what these four tests are
*for* now. Investigate `ud-dw-tasks-migrate` (the script these test) and the
three test files, then choose and implement ONE, with the reasoning in the
commit message:

- **(a) Re-point** the live tests at `.dreamwork/tasks.md.deprecated` — valid
  only if the migrate tool still has a live job against that frozen file
  (e.g. it remains the audit trail the store was verified against).
- **(b) Rewrite** them to verify the *store* against the deprecated ledger
  (the post-cutover acceptance: the store actually carries what the Markdown
  carried). This is the strongest option IF the verification logic exists or
  is small — do not build a second migrate tool to test the first.
- **(c) Retire** the four live variants (delete them), if the migrate tool's
  job is done and the fixture-based (non-live) tests already cover the logic.
  A deletion must say why the coverage is not lost — name the fixture tests
  that cover the same ground.

Whichever you pick: **no hollow checks**. If you re-point or rewrite, assert
at runtime the precondition the check depends on (e.g. that
`tasks.md.deprecated` genuinely has an `## Open` section and N entries, with N
derived from the file). If you retire, the commit message names the surviving
coverage. `CLAUDE.md`'s verification section is the law here — including: a
new/changed check is not verification until it has been red. Red-prove every
check you add or change: name the production line, inject, watch it fail,
restore byte-identical with `cp`.

## Constraints

- Do NOT edit `ud-dw-tasks-migrate` itself unless the tests reveal a genuine
  tool bug (report instead if so — do not fix the tool to fit a test).
- Do NOT touch `.dreamwork/tasks.md`, `.dreamwork/tasks.md.deprecated`, or the
  store. The live files are read-only subjects.
- `test_live_ledger_acceptance`'s `assert 65 == 0` may mean the test imports
  the live ledger and expects zero conflicts — read the test before assuming.
- After your change: `python3 -m pytest -q` must be **green, 0 failures**
  (1514+ passed — the 4 reds are the only failures on master today), and
  `python3 lint.py` clean.
- Work on a lane branch off master (`lane-511live`); commit with
  `git commit --only <paths>`.
- Append ONE `## Pending` line to `.dreamwork/handoffs.md` (append-only; never
  rewrite; the literal path is `.dreamwork/handoffs.md`).

## Report back

Which option you chose and why (one paragraph), the red-proofs run (production
line named per check, what failed, what restore showed), the final
`pytest -q` summary line, and anything you found that argues the migrate tool
itself has a bug (report only).
