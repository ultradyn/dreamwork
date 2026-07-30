# Brief — #497: read-only task CLI — thin Python verbs (RULED 16:31: "rec")

Lane: lane-497cli (glm-5.2). Max answered the design question via watch at 16:31:
**rec — Python thin verbs.** The settled shape (his ruling, from the #497 question entry):

> thin Python verbs in `dev/ledger.py`'s shape: `list [--state] [--sort] [--json]`,
> `get <id>`, `count [--state] [--json]`, `reviews list|get`. The read primitives already
> exist (`ledger_parse.store_entries`, `store_ids_by_state`, the `review_decision` table),
> the #352 parser-unification prereq has landed, and a git-style dispatcher does not exist.
> **The verbs' output contract must survive a future rewrite** (if the binary ever matters).

The full task context is ledger task #497 (`python3 dev/ledger.py get 497` if the store has
a get; otherwise the task title is "Read-only task CLI over the store: list/get/count verbs
+ reviews list" and the answered question entry at the top of `.dreamwork/questions.md`
`## Answered` carries the ruling verbatim).

## Scope

Implement the four read verb groups in `dev/ledger.py` (the existing CLI home — `counts`,
`fold`, `file`, `note`, `sweep` already live there; follow their conventions: argparse
subcommands, `--note`-style flags, the #357 warning footer on exit if that has landed —
check how `counts` does it and match):

- `list [--state open|landed] [--sort id|...] [--json]` — list tasks from the store.
- `get <id>` — one task, full record.
- `count [--state ...] [--json]` — counts by state (thin; may delegate to the same
  primitives `counts` uses — if `count` would duplicate `counts`, say so and implement
  only the difference).
- `reviews list|get` — read the `review_decision` table.

Constraints from the ruling:
- READ-ONLY. No verb in this lane mutates the store, the ledger files, or the journal.
- Ride `ledger_parse` primitives — no new parsing of Markdown, no second store reader.
- The output contract is the deliverable: stable field names in `--json` and a stable
  human shape, documented in the module/verb help, because a future binary rewrite must
  reproduce it byte-for-byte. State the contract in one place (a docstring or
  file-formats.md entry if a tool parses it — the repo rule: files the loop writes and a
  tool parses have their shape stated in `file-formats.md` and checked by `lint.py`, in
  the same commit; stdout of a read verb is borderline — if you add a file-formats entry,
  add the lint check with it).

## Verification (red-first, the repo's rules)

- New tests (extend the existing ledger test file or a new `test_ledger_cli.py`): each
  verb against a fixture store, deriving expectations from the fixture at runtime (never
  literals tuned to today's store — derive both pieces and assert the gap, per the repo's
  precondition rule).
- Red-proof the binding: cp-snapshot the verb implementation, sabotage a named line (e.g.
  the state filter predicate), watch exactly the verb's test FAIL, cp-restore
  byte-identical (never `git checkout`). A green red-run is a finding — report it.
- Run only your test file + `test_lint.py -k` subsets; never the full suite, never browser
  guards, no ports.

## Process

- Lane-owns: `dev/ledger.py` (verb additions only — do not refactor existing verbs),
  `dev/ledger_parse.py` (read primitives only if a genuine gap exists — name it),
  the new/extended test file, `file-formats.md` + `lint.py` ONLY if you take the
  output-contract entry option (coordinator-owned; flag instead if unsure).
- Commit `git commit --only <paths>` (git add new files first). Append ONE line to
  `.dreamwork/handoffs.md` under `## Pending` before your final commit (#398 obligation).
- NEVER read_file an image. No attn, no pkill -f.
- Final message: commit hashes, the verb surface as implemented, red-proof evidence, and
  any deviation from the ruled shape with its reason.
