# Brief #557 — the store projection must synthesize entry heads for headless bodies

**Task:** #557 (P1, dogfood) — `ledger_view`'s store projection is blind to
entries filed via `dev/ledger.py file`. Filed from the #553 merge gate, where
`test_the_live_repo_handoffs_file_is_silent` PASSED with #553 open and its
Pending hand-off line present — a green where red was predicted. The check was
not born hollow; it BECAME hollow when the store grew a second writer.

## Root cause (measured by the coordinator, 2026-07-30 22:15)

The #294 import stored each entry's body verbatim, head line included
(`- **#50** — <title> · P2 · task · origin: **human** ·` and friends). The
store's `file` verb stores the body WITHOUT a `- **#id**` head (entry 553's
stored body begins `Found in coordinator review at the #551 merge gate:…`).
`ledger_view` (lint.py:993) synthesizes `## Open` / `## Recently landed` text
from those bodies and every text-consuming check runs `watch.parse_ledger`
over it — which keys on entry heads. Measured on the live tree:

- 65 of 445 store entries lack a head line; 6 are OPEN (492, 493, 500, 553,
  555, 556) and 59 are landed.
- The view reparses to **104 open ids; the store holds 110.** The 6 headless
  open tasks are invisible to `check_handoffs`' delivery WARN,
  `check_task_origins`, `check_cited_shas`, and every other `ledger_view`
  consumer — i.e. every recently filed task is invisible to the loop's
  delivery signal.

## Fix (projection-side; shape PROVEN by coordinator probe, 22:27)

In `store_entries` (`ledger_parse.py:184` — the ONE store reader for
`(ids, body)`, the #352 single-reader rule), for each row whose body's first
line does not start with `- **#`, prepend a head synthesized from the store
columns:

```
- **#N** — <title> · <priority> · <type> · origin: **<origin>** ·
```

`origin` is constrained at the schema to `human|loop|unknown` (NULL →
`unknown`, the check docstring's truthful value). The coordinator ran exactly
this as a monkeypatched probe over the live repo with the full check suite:
**zero new ERROR/WARN findings** — only two OK rows move (380→446 ids
projected; 269→335 origins recorded). An earlier probe WITHOUT the origin
clause produced 66 `no origin` ERRORs (#492–#557), which is how the clause's
necessity was measured rather than guessed.

Why projection-side and not file-side: the `file` verb's stored body shape is
a store implementation detail; the projection is the contract every consumer
reads. A file-side change leaves the 65 existing headless entries blind;
synthesis is retroactive and cannot regress if the body shape changes again.

## Requirements

1. **Born-red first.** Write the binding test(s) before the fix and watch
   them fail on the live tree. Suggested binding: the synthesized view's
   `watch.parse_ledger` open/landed id sets EQUAL `store_ids_by_state`'s —
   today they differ by exactly the 6/59 headless entries, so the red is
   free and real. Record the born-red output in the report.
2. **Runtime preconditions (the companion rule).** The test must DERIVE and
   assert the gap it depends on (store open count vs view open count), never
   pin a literal tuned to today's fixture.
3. **Red-proof** by sabotaging the production synthesis line (e.g. the head
   prepend) → the named test FAILs → `cp`-restore byte-identical (`cmp`),
   never `git checkout`.
4. **Edge — double origin marker.** A headless body that already quotes
   `origin: **x**` in prose would, with a synthesized head, carry two
   markers and ERROR in `check_task_origins`. The live tree has none
   (probe-verified); derive and assert that at runtime in the test, or
   handle it generally — do not assume.
5. **Edge — NULL/odd columns.** Verify the priority/type/origin column
   constraints yourself; if a column can be NULL, decide the head form for
   that case from evidence (the head grammar tolerates absent fields — the
   pre-#216 corpus has bare heads) and say what you decided.
6. **body_digest.** Synthesis changes only the PROJECTION, never the stored
   body. Coordinator grep-verified (22:27) that nothing outside tests
   compares `store_entries` output to `task.body_digest`; re-verify, and
   check the test suite for a pin on verbatim bodies.
7. **Docstring + contract.** `store_entries`' docstring says "the body is
   the verbatim text the import stored" — that stops being true. Update the
   docstring. Do NOT edit `file-formats.md` (coordinator-owned): flag the
   contract-line change in your report and the coordinator lands it at the
   gate.
8. **Consumers.** Production consumers of `store_entries`: lint.py only
   (grep-verified). Run the FULL `python3 -m pytest test_lint.py -q` and
   grep the wider test suite for `store_entries`.
9. **New live findings = STOP.** If after the fix anything beyond the two
   OK-row moves appears on the live repo, stop and report — never silence
   another check, never fabricate fields to make one quiet.

## Lane-owns

- `ledger_parse.py` (the `store_entries` region)
- `test_lint.py` or a new focused test file (your call; justify if new)

**NOT** lint.py's check regions (the checks are healthy — the projection was
blind), NOT `dev/ledger.py`, NOT `file-formats.md` (flag it), NOT watch.py,
NOT the justfile.

## Hand-offs obligation (#398)

On completion append ONE line under `## Pending` in `.dreamwork/handoffs.md`
(that literal path): `- **#557** · landed \`<sha>\` · <date> · by
lane-557projection — <what>`. Bare shas, no parentheticals. Never claim a
model (#469 — a lane cannot know its own).

## Constraints

Never `just test`; no ports, no browser, no guards. `git commit --only
<paths>` (a NEW file needs `git add <file>` first). Never `read_file` an
image. No `attn`. Never `pkill -f`.
