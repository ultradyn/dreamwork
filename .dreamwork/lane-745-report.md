# Lane 745 report — make the delta claim match its proof

## Verdict

Choose **(a): semantic JSON-value equality**, explicitly ignoring JSON object
member order while retaining ordinary JSON semantics (array order and values
still matter). This is a correction of the contract, not a retreat from a
property the implementation ever supplied.

This is **not a current UI failure**. Present `collect()` top-level keys remain
fixed within a running generation, nested mutations ship their whole top-level
value, and `derived_check` sorts keys. The defect was that the strongest prose
claim — byte identity — was the one property the test did not inspect, leaving
a future key-reordering change able to land green.

### IGC decision

| Idea | All | G1: words match behaviour | G2: Python/JS contract stays single | G3: claimed property discriminates |
|---|:---:|:---:|:---:|:---:|
| (a) semantic JSON equality | ✔ | ✔ | ✔ | ✔ |
| (b) preserve/compare byte order | ✘ | ✘ | ✘ | ✔ |

The decisive errors for (b) are that `compute_delta` deliberately iterates a
set, JSON object order was never part of the wire value, and the integrity hash
deliberately uses `sort_keys=True`. Making bytes authoritative would add a new
ordering/canonicalisation contract, including a cross-language definition that
does not exist. The existing #741 harness already compares the two production
appliers structurally from one Python-derived envelope source; it should not
gain a second byte authority.

## Reproduction before changes

The finding reproduced under explicit seeds. The same base and target, with
four added keys, rebuilt to these unsorted serialisations:

```text
seed=1 {"generated":"old","survivor":true,"alpha":1,"beta":2,"delta":4,"gamma":3}
seed=2 {"generated":"old","survivor":true,"delta":4,"gamma":3,"alpha":1,"beta":2}
seed=3 {"generated":"old","survivor":true,"gamma":3,"alpha":1,"delta":4,"beta":2}
seed=4 {"generated":"old","survivor":true,"delta":4,"gamma":3,"alpha":1,"beta":2}
```

That is three distinct byte sequences; seeds 2 and 4 collided. Mapping equality
remained true in every run, so the defect shape is confirmed even though this
particular constructed key set did not produce four unique orders.

## Changes

- `file-formats.md` now promises semantic equality of the complete JSON value
  minus `generated`, not byte identity.
- `watch.compute_delta` and `TestDataJsonDelta` use the same language.
- The false re-stamping claim is removed. Both appliers carry the base's old
  `generated` value because the field is excluded; only a later full document
  replaces it.
- The live-path reconstruction assertion now compares the entire generated-free
  document, rather than iterating only target keys and missing an extra stale
  key.

Behaviour-and-contract commit after the final rebase: `07789e68`.

## Red-proof

### Direction 1 — semantic difference goes red

I injected an `apply_delta` defect that omitted `new_key` while
`compute_delta` still correctly listed it. The adversarial round-trip failed on
the discriminating assertion:

```text
case 'key added': reconstruction diverged from target — delta was {changed: ['new_key'], removed: []}
```

This proves the assertion grades reconstruction semantics rather than merely
the expected delta-key list.

I separately injected an extra `__stale_injected__` key to bind the tightened
live-path sibling. It failed with:

```text
live delta reconstruction differs semantically from the current document
```

The old per-target-key loop would have ignored that extra key.

Both injections were restored through `dev/redproof.py`; no checkout restore
was used. The final gate said:

```text
check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits
```

### Direction 2 — the old byte claim's open false-green

I constructed equal top-level mappings whose nested object member order alone
differs:

```text
semantic_assertion_passes True
target_bytes {"outer":{"a":1,"b":2},"z":3}
rebuilt_bytes {"outer":{"b":2,"a":1},"z":3}
byte_claim_is_wrong True
```

Thus the assertion passes while reconstruction is wrong **under the rejected
byte-identity wording**. Under the selected contract this is deliberately not
wrong: the two JSON object values are equal. No semantic false-green can be
constructed from member reordering, including nested reordering; the complete
recursive dict/list/value comparison covers the selected property, with only
`generated` intentionally excluded.

## Relied-on issue text

- #440: "`dev/ledger.py` is now the one supported path". Applied here as the
  brief's one-supported-way principle: one contract description, not semantic
  comparison plus a rival byte description.
- #641: "The reconstruction test is REAL ... apply(base, delta(base, next)) ==
  next". The test remains real; its contract is now stated honestly.
- #732: "It also argues key ORDER is not a valid source of truth here
  (`compute_delta` iterates a Python set, and `derived_check` uses
  sort_keys=True deliberately)". Its design at lines 61–70 additionally says:
  "A test should compare document values, not `JSON.stringify` byte order."
- #741: "`dev/data-delta.test.mjs` (7 tests) executes the PRODUCTION
  `applyDataResponse` ... against envelopes derived at runtime by the production
  `compute_delta`/`derived_check`". I reused that harness through its existing
  Python test; no new scaffolding was built.
- #742: "487 tests." The lane rebased from that cache-signature change before
  measuring and retained the same full-file count.
- #750: "design only, no encoder." Its structural-digest design landed while
  this lane ran; browser verification remains implementation work rather than
  something this lane should smuggle into the reconstruction-contract fix.

## Verification and rebase

- Before change: `python3 -m pytest test_watch.py` — **487 passed** in 68.83s.
- Focused delta class, including the Python subprocess call to
  `node --test dev/data-delta.test.mjs` — **10 passed** both before and after
  the final rebase.
- After change and after rebasing onto `52d23a2a`:
  `python3 -m pytest test_watch.py` — **487 passed** in 69.97s. The final
  `e2f6c973` base movement changed only `.dreamwork/lessons.md`; the focused
  delta/Node class was rerun after it.
- After the final rebase: `python3 lint.py` — `clean (6 warning(s))`, **no
  ERRORs**. The warnings are the worktree's explicit absent-ledger/status
  refusals plus existing repository warnings; none arose from this change.
- `python3 dev/redproof.py check --require 1` — clean, injection restored and
  absent from both working tree and branch commits.

The lane began at local `master` `3db7c26b`. While verification ran, local
`master` advanced through `96e47397`, `52d23a2a`, and finally `e2f6c973`;
all three `git rebase master` runs completed without conflicts. No merge, push,
browser guard, server, or port was used.

## Out of scope

No out-of-scope product defect was found. #750's structural-digest design
landed on `master` during this lane, but its ledger explicitly says "design
only, no encoder"; this lane did not widen into that protocol implementation.

## DOGFOOD REPORT

Two pieces of useful friction:

1. The brief's literal "FOUR different serialised orders" did not hold for my
   constructed four-added-key target: seeds 1–4 yielded three unique orders
   because 2 and 4 collided. The material premise — hash-dependent divergence
   hidden by mapping equality — did reproduce immediately. Future briefs should
   distinguish the invariant (more than one order) from an observed sample's
   exact uniqueness count.
2. `dev/redproof.py` keeps one registry entry per path. Red-proving two distinct
   injections in `watch.py` required forgetting the first before arming the
   second, so the final `check` can mechanically attest only the latest
   injection even though both failure transcripts were captured. A multi-entry
   history per path would make repeated same-file proofs easier to hand off.

No other loop or brief friction found.
