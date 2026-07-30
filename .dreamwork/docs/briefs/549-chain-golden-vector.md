# Brief #549 — golden vector for the task_event chain byte format

**Task** (ledger #549, origin loop): filed from the #460 merge gate —
the coordinator's independent red-run swapped `from_state`/`to_state`
in `canonical_event_bytes` (`ledger_store.py:122-126`, a pre-existing
line the #460 lane did NOT inject) and ALL 66 replay/store/writer tests
PASSED. Every check hashes through the same shared function, so a
self-consistent corruption of the chain's byte format is invisible
everywhere: the format is exercised everywhere and pinned nowhere. The
contract it must be pinned against is `file-formats.md` § *"The
`task_event` journal `.jsonl` — portable export/replay of the
transition log (#460)"* (landed `4161f0e1`).

## Scope

Tests only — new golden-vector tests (extend `test_ledger_store.py` or
add a focused `test_chain_golden.py`; your call, justify in the
report). No production code changes.

1. **One fixed event, independent expectation.** Build ONE event dict
   with fixed literal field values (task_id, at, cause, from_state,
   to_state, actor, detail — every field distinct so a swap moves the
   bytes). Construct the expected canonical bytes **independently in
   the test**: the parts listed literally in the contract's field
   order, each framed as an 8-byte big-endian length prefix + utf-8
   bytes, written out as explicit test code — NEVER by calling
   `_length_framed` or `canonical_event_bytes` (that is the
   self-consistency trap this task exists to close).
2. **Exact-bytes assertion** — `canonical_event_bytes(e) == <the
   independently built bytes>`, not a hash comparison alone (bytes
   first: a diff on failure must show WHICH field moved).
3. **Golden digests, with provenance.** Assert a recorded literal
   sha256 of those canonical bytes, a recorded literal `hash_event`
   output for a fixed `prev_hash`, and a recorded literal
   `genesis_hash()`. Compute each golden ONCE from the independently
   built expectation (never from the production function), and record
   in a comment above each literal: the date, and the exact
   one-liner a reviewer runs to recompute it from the contract.
4. **A migration warning in prose**: a comment at the test head that
   these literals ARE the chain format — changing them deliberately is
   a format migration and must come with a `file-formats.md` contract
   edit in the same commit (the file-formats.md section already says
   this; the test points at it).

## Hard contracts

- **Red-first with the finding's own repro**: sabotage
  `ledger_store.py` by swapping `from_state`/`to_state` in
  `canonical_event_bytes` (the exact swap that passed green at the #460
  gate) → your golden test must FAIL by name. cp-restore byte-identical
  (verify with `cmp`), never `git checkout`. Second red: drop one
  field from the framing in the sabotaged copy → FAIL. Assert your
  fixture precondition at runtime: every field value in the fixed event
  is distinct (a swap of two equal values moves nothing).
- **Targeted pytest only**: your test file plus `test_ledger_store.py`
  `test_ledger_write.py` `test_replay_events.py` must stay green.
  Never `just test`.
- **NEVER `read_file` an image** (glm-5.2 API 400 kills the lane).
- **ONE `.dreamwork/handoffs.md` `## Pending` line** before your final
  commit (#398 obligation): #549, sha, date 2026-07-30,
  lane-549golden, what landed, red proofs, flags.
- **Commit with `git commit --only <paths>`**; new files need
  `git add <file>` first. No ports, no browser, no guards. Never attn;
  never `pkill -f`.

## Lane-owns declaration

You own: your test file(s) and your handoffs line.
You do NOT own: `ledger_store.py` (sabotage for the red proof, restore,
never commit), `file-formats.md`, `lint.py`, `dev/ledger.py`,
`dev/replay_events.py`.

**Fleet**: lane-551remind (watch.py posture region) and
lane-548cap (dev/capture/bdinput.mjs) are in flight — all disjoint
from your test files.

## Report shape

Final report: commit(s); the two red proofs (field swap → named FAIL;
dropped field → named FAIL) with restore verification; how each golden
literal was computed independently (show the derivation); the targeted
pytest verdict lines; any deviation with the reason.
