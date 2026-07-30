# Brief #550 — design: the task_event journal's entity-schema decision (extend or narrow)

**Task** (ledger #550, origin loop): filed from the #460 merge gate.
The round-trip falsifier worked as designed and returned a #294
finding: a store exported via `dev/replay_events.py` and replayed
reconstructs the task_event **chain** completely (all 11 columns
including recomputed `prev_hash`/`hash`) but the task **entity** does
not round-trip — 7 columns (`title`, `body`, `priority`, `origin`,
`type`, `blocked_on`, `body_digest`) are lost, proven with an
entity-setting fixture, not vacuous NULLs. The `.jsonl` contract
(`file-formats.md` § "The `task_event` journal `.jsonl`", `4161f0e1`)
documents this as *transitions-not-entities* and names this task as the
owed extend-or-narrow decision.

## Scope

**Design only — a findings-and-recommendation doc, no production
code.** Produce `.dreamwork/docs/550-journal-entity-schema.md`
(committed) that adjudicates:

1. **Narrow**: the journal is a *lifecycle* log by design. Replay
   reconstructs transitions; the entity lives only in the SQLite store.
   The tool's claim, docstrings, CLI help and the contract are narrowed
   to say so honestly (they currently imply fuller reconstruction).
2. **Extend**: the journal gains entity data — e.g. an entity-snapshot
   record at first sight (and/or on entity mutation), so replay
   reconstructs the full row. This is a **format migration**: #549's
   golden vector (`test_chain_golden.py`, merged `a053d83d`) now pins
   `canonical_event_bytes` byte-for-byte, so any change to the hashed
   field set is deliberate-migration territory with a `file-formats.md`
   edit in the same commit. An *additive* record kind (new `cause`, new
   fields hashed only when present) may be backward-compatible with
   existing journals — analyse whether, precisely.
3. **Sidecar/hybrid**: transitions stay canonical; an optional entity
   export rides beside the journal (second file or a trailer section),
   replay merges them when present.

For each option: what breaks, what it costs, what it does to the merge
rule (`(at, task_id, arrival-rank, …)` total order, no dedup), to
replay determinism (byte-identical store from an empty image), to the
`receipt_id`-stored-not-hashed stance, and to #549's pin. Then a
**recommendation** with the reasoning, and the implementation shape of
the recommended option (which primitives, which files, what the
red-first checks would be) at enough fidelity that a follow-up
implementation lane can be briefed from the doc alone.

Also answer explicitly: **does the decision need the human?** If the
choice turns on what replay is *for* (backup/restore vs lifecycle
audit) and that purpose is not derivable from the repo's own documents,
say so and draft the `questions.md` entry; if the repo's documents
already answer it, cite them and decide.

## Read first

- `file-formats.md` § the `task_event` journal `.jsonl` (the contract
  you may be proposing to amend) and § the `task_event` SQLite table.
- `dev/replay_events.py`, `ledger_store.py` (chain primitives,
  `canonical_event_bytes`, `append_chained_event`), `ledger_write.py`
  (what the writer actually journals).
- `test_replay_events.py` (what the falsifier proved) and
  `test_chain_golden.py` (the pin any extension must respect).
- The #460 Folded line in `.dreamwork/handoffs.md` (the gate record)
  and ledger #294 / #460 / #549 context.

## Hard contracts

- **Design-doc lane**: no production code, no tests, no sabotage
  proofs — the gate for this lane is coordinator review of the doc's
  reasoning (same shape as #505arch/#510orc). If you prototype anything
  to settle a factual question (e.g. whether an additive record keeps
  old journals replayable), do it in a scratch path, report the
  evidence, and do not commit it.
- **file-formats.md is coordinator-owned.** Do not edit it; write the
  proposed contract-diff text into your report as a FLAG.
- **NEVER `read_file` an image** (glm-5.2 API 400 kills the lane).
- **ONE `.dreamwork/handoffs.md` `## Pending` line** before your final
  commit (#398 obligation): #550, sha, date 2026-07-30,
  lane-550schema, what landed (the doc), flags.
- **Commit with `git commit --only <paths>`**; the new doc needs
  `git add` first. Targeted pytest only if you touched nothing that
  tests cover — state that. Never `just test`; never attn; never
  `pkill -f`.

## Lane-owns declaration

You own: `.dreamwork/docs/550-journal-entity-schema.md` and your
handoffs line.
You do NOT own: `file-formats.md`, `ledger_store.py`,
`dev/replay_events.py`, `ledger_write.py`, any test file, `lint.py`.

**Fleet**: lane-551remind (watch.py posture region) and lane-548cap
(dev/capture/bdinput.mjs) are in flight — disjoint from your doc.

## Report shape

Final report: commit(s); the recommendation and its one-paragraph
justification; the human-needed verdict (and the drafted questions.md
entry if yes); the FLAG contract-diff text if you recommend extend or
sidecar; the implementation-brief sketch for the recommended option;
any deviation from this brief with the reason.
