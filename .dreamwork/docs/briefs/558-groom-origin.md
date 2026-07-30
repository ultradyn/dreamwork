# Brief #558 — the `groom` verb: NULL-origin backfill + untyped report

**Task:** #558 (P3) — the #357 warnings footer prints `239 untyped · 107
missing origin` on every verb; a count that cannot shrink on its own.

## Mechanical half (the deliverable)

A new `dev/ledger.py` verb — `groom` — whose first act backfills the store's
NULL origins: `UPDATE task SET origin='unknown' WHERE origin IS NULL`,
reporting how many rows changed. `unknown` is not a guess: the
`check_task_origins` docstring (lint.py, #213) names it the truthful value
for a task filed before the contract existed. The verb is the audited
surface — never raw SQL outside it.

- The store CHECK constraint already admits `unknown`; verify that from the
  schema yourself and cite it.
- The verb must be idempotent (a second run changes 0 rows and says so) and
  must print the warnings footer like every other verb (the #357 contract —
  find `emit_warnings` and reuse, never re-implement).
- `Migration:` trailer on the commit: an existing install's store gains
  origin values on the first `groom` run.
- Markdown-mode targets (no cutover watermark): decide the honest behaviour
  from evidence (the origin lives in entry TEXT there, and a text rewrite is
  a different act) — refuse with a named reason, or implement and justify.
  Record the decision in the verb's docstring.

## Judgment half (report only)

239 rows have no `type`. Do NOT mass-assign — types are per-task judgment.
Report the breakdown: open vs landed, the priority distribution, and whether
any closed subset has a defensible mechanical default. That report is a
section of your final message; the lane lands no type changes.

## Interaction with #557 (in flight, NOT your files)

lane-557projection owns `ledger_parse.py` (`store_entries`) and
`test_lint.py`: its synthesis maps NULL origin to `unknown` in the projected
head, so after both land the view and the store agree. No sequencing
constraint, but do not touch its files. lane-387hook owns
`plugins/ud-dreamwork-hooks/`.

## Red-first requirements

- Tests born-red BEFORE the verb exists (fixture store with a mix of NULL
  and set origins; counts derived from the fixture at runtime, never
  literals — the companion rule).
- Cover: backfill count, idempotency, the markdown-mode behaviour, the
  footer still prints.
- Red-proof by sabotaging the production UPDATE (e.g. `WHERE origin IS
  NULL` → a no-op condition) → the named test FAILs → `cp`-restore
  byte-identical (`cmp`), never `git checkout`.
- Run your test file plus the full ledger CLI suites (`test_ledger*.py`)
  and `python3 -m pytest test_lint.py -q` to prove no drift.

## Lane-owns

- `dev/ledger.py` (the groom verb region)
- `test_ledger_cli.py` or a new focused test file (your call; justify if new)

**NOT** `ledger_parse.py` / `test_lint.py` (lane-557projection), NOT
`plugins/` (lane-387hook), NOT watch.py, NOT file-formats.md (if the verb's
output shape wants a contract line, flag it — coordinator-owned).

## Hand-offs obligation (#398)

On completion append ONE line under `## Pending` in `.dreamwork/handoffs.md`
(that literal path): `- **#558** · landed \`<sha>\` · <date> · by
lane-558groom — <what>`. Bare shas, no parentheticals. Never claim a model
(#469 — a lane cannot know its own).

## Constraints

Never `just test`; no ports, no browser, no guards. `git commit --only
<paths>` (a NEW file needs `git add <file>` first). Never `read_file` an
image. No `attn`. Never `pkill -f`.
