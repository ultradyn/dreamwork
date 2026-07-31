# Lane report — #757 structural queued-dispatch ids

## Result

Implemented the structural queued-dispatch schema and rebased the lane onto
`master` at `2fde20542db13c5c5b8d848c243e6e2823b1e156`.

- `status_sync.audit_queued_dispatches` now audits only an entry object's
  non-empty `ids` list. It never scans `note`, mutates the field, or adds an
  advisory finding to sync drift.
- Legacy strings remain loadable but are reported as `unmigrated`; missing or
  malformed `ids` and non-object entries are reported as unclassifiable.
- Both denominators remain unconditional: entries examined and structural id
  references examined.
- `client/views.js`'s `queuedDispatchLines` and `stField` render the `note` of a
  structural entry, while retaining legacy-string rendering. They do not emit
  `[object Object]` or expose a separate `ids:` row.
- The checked-in client bundle and manifest were rebuilt.

Post-rebase commits:

- `60a1a228` — `fix(#757): audit structural queued dispatch ids`
- `028fe4c0` — `fix(#757): render queued dispatch notes`
- `67db0c36` — `build(#757): refresh client bundle`
- `de90ad1d` — `build(#757): refresh dashboard bundle`

Exact production functions touched:

- `status_sync.py`: `audit_queued_dispatches`
- `client/views.js`: `queuedDispatchLines` (new), `stField`

`watch.py` itself was not edited: the relevant renderer has already been
extracted into `client/views.js`, and `watch.PAGE` assembles that source.

## Migration hand-off

The lane was forbidden to write the live `.dreamwork/status.json`, so the
coordinator must apply this exact migration after merging:

```json
[
  {"ids": [645], "note": "#645 increments 2-14 - queued behind cx-645i1."},
  {"ids": [631], "note": "#631 (P4) - the session view. NOT parallel with component-registry work."},
  {"ids": [736, 628], "note": "#736 and #628 phase 2 - HELD on load (browser guards return a WRONG answer under load, #666)."},
  {"ids": [758], "note": "#758 (P3) - justfile pytest *ARGS, so one supported command also runs the concurrency advisory."}
]
```

Until that migration is applied, the new loader deliberately reports four
unmigrated entries and zero id references rather than silently reverting to
prose attribution.

## Red proof and direction 2

Before editing, the baseline suite was `67 passed in 11.22s`. A live read-only
run of the old audit examined four current entries and six prose references,
and falsely warned on the landed lesson citation `#666`. The brief's second
expected warning (`#632`) was no longer present in the live field by the time
the lane ran.

The fixed regression fixture contains the current four live strings and their
structural migration. It asserts the discriminating `#666` citation is present
in the note, absent from warnings, and that the non-zero denominators are four
entries and five id references.

The registered injection replaced structural ids with regex-extracted note ids.
The discriminating test failed at `assert "#666" not in err`, with the warning
`#666 is not present in the ledger`; `redproof.py restore` restored the fixed
snapshot and `cmp` verified it byte-for-byte.

Direction 2 remains explicit and honest:

- A structurally correct open id with prose saying “already landed” passes;
  ledger state cannot judge prose truth.
- A wrong `ids` list is not cross-checked against `note`. The suggested partial
  cross-check would produce zero warnings on today's migrated live equivalent,
  but it would warn on a legitimate citation to another open task. That
  recreates false attribution and violates the stated “prose is free” property,
  so it was not shipped; a test pins the legitimate-open-citation case.
- A legacy string is accepted but loudly reported as unmigrated and contributes
  zero references; it does not silently retain the old regex behaviour.

Final red-proof gate, verbatim:

```text
history: examined 4 commit(s) since 2fde20542db1 (master) against 1 injected path(s); read 4 blob(s), 0 holding a recorded injection.
check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits:
  status_sync.py (sha d5b6c7305b0e, hint: 'if isinstance(entry.get("note"), str):')
```

## Verification

- Before change: `python3 -m pytest -q -n 2 test_status_sync.py test_status_derive.py`
  — **67 passed**.
- Full changed surface before rebase:
  `python3 -m pytest -q -n 2 test_status_sync.py test_status_derive.py test_watch.py`
  — **566 passed, 65 subtests passed**.
- After rebasing onto current master: status/derive plus the exact renderer test
  — **77 passed**.
- `python3 lint.py` after rebuild — **clean (6 warning(s))**, no ERRORs.
  Each warning was inspected: three historical answered questions lack dates;
  the gitignored ledger store and status file are absent in this worktree; the
  markdown fallback examined zero ledger entries; one lessons near-duplicate
  already exists in HEAD; and the seven ledger-dependent checks correctly
  report that they examined nothing. None was introduced by #757.
- Live read-only invocation exited 0. `status.json` was `19557` bytes with mtime
  `1785522859` both before and after, and `cmp` succeeded.
- `client/dist` matches 14 inputs and 3 outputs after `just build-client`.
- No ports were bound and no browser guard or full guard suite was run.

## DOGFOOD REPORT

1. The brief's live measurement had already drifted: it promised two permanent
   warnings (`#666`, `#632`), but the coordinator replaced the `#632` string
   with `#758` before this lane's read. The required “CURRENT bytes” rule was
   the right tie-breaker; the resulting defect proof has one real false warning,
   not the stale claimed two.
2. The brief names “`watch.py`'s rendering” and grants `watch.py`, but the source
   of that renderer has already moved to `client/views.js`. Completing the
   user-visible requirement also necessarily changes the generated
   `client/dist/ds/index.js` and manifest. Future briefs should name the current
   source/build ownership explicitly.
3. “Provide a migration” and “never write live status.json” leave the actor for
   the actual four-entry cutover implicit. This lane could implement compatibility
   and provide the exact mapping, but only the coordinator can complete the live
   data write after merge. Future lane briefs should state that hand-off directly.
4. No other loop or tooling friction was found.
