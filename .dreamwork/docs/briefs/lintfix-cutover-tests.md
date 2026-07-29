# Brief — lane-lintfix: repair the 5 cutover-broken test_lint.py tests (#495)

**Lane-owns:** `test_lint.py` ONLY. Do not touch `lint.py`, `watch.py`,
`ledger_*.py`, or any other file. If a repair seems to require a production
change, STOP and report — that is a finding, not a licence.

**Model:** llmp-glm-5-2 · **Isolation:** worktree (coordinator merges).

## The failure

Five tests in `test_lint.py` are red on master (`06a88bc`), all one class:
they read the live ledger from `.dreamwork/tasks.md`, which post-cutover
(#294/#458) is a one-line migration shim carrying NO entries, so
`watch.parse_ledger` returns zero open ids and every runtime precondition
fails. Same class as `135c2e31` and `7068342d` (which repaired two
test_watch.py siblings by repointing to `tasks.md.deprecated`).

1. `TestTheBugItWasBuiltFor::test_this_repo_passes_its_own_linter` — the
   frozen-tree (HEAD snapshot) precondition parses the snapshot's `tasks.md`
   shim and asserts >0 open ids → "run is vacuous".
2. `TestSelfCompletedOpen::test_261_restored_to_open_fires_warn` — asserts
   `#261` is in the live ledger; in the STORE #261 is **landed**.
3. `TestSelfCompletedOpen::test_the_four_false_positives_stay_silent` —
   pins #275/#283/#269/#281 as open; in the store **#283 is landed**
   (#275, #269, #281 still open).
4. `TestSelfCompletedOpen::test_breaking_position_fires_the_false_positives`
   — same pin problem.
5. `TestHandoffs::test_it_flags_a_handoff_for_a_real_open_id_in_the_live_ledger`
   — "picks a genuinely-open id at runtime" from the shim → empty set.

## Live-store truth (measured 2026-07-30, READ-ONLY)

Store: `.dreamwork/ledger.sqlite3` in the MAIN checkout (gitignored — your
worktree does NOT have it; read the main checkout's store with
`file:<abs path>?mode=ro`, `uri=True`; do NOT write to it, do NOT copy it
into your tree). Task table: `task(id, state IN ('open','landed'), title,
body, …)`. #261 landed, #283 landed, #275/#269/#281 open.

Production readers to reuse (never a second copy): `watch.parse_ledger` for
markdown text; for the store, the projections `lint.py`/`status_sync.py`
already use (look at how `lint.check_status_agrees_with_ledger` and
`ledger_parse.source_of_truth`/`store_ids_by_state` get live open ids —
use the SAME path).

## Direction (not a straitjacket — the tests' INTENT is the contract)

- Each test's docstring states what it proves. Preserve the proof; repair
  the data path. The repo's standing rule: **assert in the check the
  precondition the check depends on, derived at runtime** — never a literal
  tuned to today's ledger. The pins (#261, #283) drifting is exactly the
  failure that rule exists for; where possible derive candidates at runtime
  (e.g. find open store entries whose prose body carries
  landed/completed/merged vocabulary and assert the set is non-empty)
  rather than re-pinning new ids.
- `TestTheBugItWasBuiltFor`: the frozen HEAD tree has no store (gitignored,
  by design). The non-vacuous precondition should read the snapshot's
  `tasks.md.deprecated` (committed, populated) — same repair as `7068342d`.
- Store-mode tests must build state via the REAL cutover path
  (`perform_cutover`, see `TestStoreModeLint._cut_over`) or read the REAL
  store — never hand-built fixtures that stand in front of the code under
  test (`.dreamwork/lessons.md` has the two structural-hollowness cases).

## Acceptance criteria (all measurable)

1. The 5 named tests pass.
2. Full `python3 -m pytest test_lint.py -q` → 0 failures (373 tests).
3. `python3 lint.py` on the main checkout stays clean (no new WARN/ERROR).
4. For EACH repaired test, your report names the production line whose
   change would make it fail again (the "name the production line" rule).
5. `git diff --stat` touches only `test_lint.py`.

## Hand-off obligation

Your final report goes in `.dreamwork/handoffs.md` per the #398 contract:
what changed, the per-test production-line names (criterion 4), and
anything you did NOT do. Commit your work in your worktree with
`git commit --only test_lint.py`; the coordinator merge-gates.
