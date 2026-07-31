# Lane 741 report — stale browser delta rejection

## Verdict

Partial repair, deliberately: the reachable stale-base and late-response defect
is closed. The browser now captures the requested base per fetch, accepts a
delta only when that base still names the held document, sequences overlapping
requests so only the newest can commit, and recovers from an unprovable response
with one fetch that omits `since`.

Browser verification of the server's `check` is not implemented. The wire hashes
the exact bytes of Python's `json.dumps(..., sort_keys=True, default=str)`, which
cannot be reproduced reliably after JSON has been parsed into JavaScript values:
among the differences, Python `1.0` and `1` become the same JavaScript number
even though Python hashes different spellings. A correct follow-up must define a
language-neutral canonical encoding on the wire and prove Python/JavaScript byte
parity before adding Web Crypto. Naive `JSON.stringify` hashing was not shipped.

The relied-on ledger wording for #741 was: **"capture the requested base per
fetch; reject any delta whose `base` is not the version actually held; sequence
responses so a late one cannot commit"**, and **"every failure path clears
`lastDataV` and refetches WITHOUT `since`"**. The implemented recovery follows
that instruction; a superseded response does not launch a competing recovery
because the newer request already owns the state.

## Changes

- `dev/data-delta-cases.json` is the single committed set of labelled base/next
  pairs. It contains no expected envelopes.
- `test_watch.py` derives each envelope with production `compute_delta` and
  `derived_check`, proves production `apply_delta` reconstructs the target, and
  writes those same derived envelopes to a temporary JSON file.
- `dev/data-delta.test.mjs` reads the exact production `applyDataResponse` slice
  from `client/router.js` through a unique-marker `node:vm` seam. It covers valid
  composition, the direct mismatched-base probe, burn-step interleaving,
  newest-response sequencing, and full recovery without `since`.
- `client/router.js` adds `fetchDataResponse`, explicit per-request base capture,
  response sequencing, base/held-version validation, and full-refetch recovery.
  All three production data fetchers use it.
- `client/dist/ds/index.js` and `client/dist/manifest.json` were rebuilt. Two
  consecutive builds produced identical hashes for all three outputs and the
  manifest (`manifest.json` SHA-256
  `7b9dacebba5d62ed9f09b380b3ecb2a083eabae250b299b6fd5f0565f0811630`).
- `file-formats.md` now states the base/sequence guarantee and says explicitly
  that `check` remains reserved metadata rather than a claimed browser self-heal.

## Red-proof

### Direction 1 — inject the real defect

After the fix was committed, `dev/redproof.py begin client/router.js` snapshotted
the fixed file lane-privately. I disabled the base guard and ran the production
harness. It failed on the discriminating assertions:

> `base mismatch: a delta for v1 was accepted against other-version`

and, independently:

> `burn-step stale base: the old response committed over the new bucketing`

The injected response also failed the recovery assertion:

> `base mismatch did not clear the cached version before recovery`

`dev/redproof.py restore client/router.js` restored and byte-verified the fixed
file. Final gate output:

> `check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits`

### Direction 2 — genuine break that the base-only guard accepts

The harness gives the applier a held document corrupted with an extra surviving
key while keeping the declared base version equal to the requested and held
version. The envelope carries the real 64-hex `derived_check` of the correct
target. The base guard accepts it, advances the version, and the reconstructed
document remains unequal to the target. A second case replaces the check with
`deliberately-wrong`; it too is accepted. These green tests name the open
false-green rather than pretending the partial repair verifies hashes.

Coordinator action: file the canonical-wire/check-verification half as a
follow-up task, carrying the number-normalisation finding above. This lane did
not mutate the shared ledger because the dreamwork lane contract makes the
coordinator its single writer.

## Verification

- Direct `node --test dev/data-delta.test.mjs`, fed the temporary
  Python-derived envelope set: **7 passed, 0 failed**.
- Targeted `python3 -m pytest -q test_watch.py -k 'TestDataJsonDelta or
  live_data_assignments_go_through_one_seam'`: **8 passed, 476 deselected, 6
  subtests passed**.
- Full `python3 -m pytest test_watch.py` after rebase: **484 passed in 69.88s**.
- `node --check client/router.js`: passed.
- `python3 lint.py`: **clean (6 warnings)**, with no errors. The warnings are
  the worktree's absent gitignored ledger/status state and pre-existing content
  warnings; lint reports `client/dist` current.
- `python3 dev/redproof.py check`: clean, quoted above.
- No server, browser, or port was started.

## Rebase

Rebased successfully onto local `master` at
`b6d98794f27c8ea289ef52781e94719214bc7934`; no conflicts. Post-rebase
implementation commits were `42aa10f1` (harness) and `c2e2093b` (repair).

## Out of scope

The canonical wire encoding and browser SHA-256 verification remain open as
described above. No other defect was found in the scoped data-fetch siblings.

## DOGFOOD REPORT

The task brief and design were unusually precise and saved re-derivation time.
Two pieces of friction were real:

1. The required direct `node --test` harness depends on a temporary file that
   only Python can correctly derive, so the standalone command needs a small
   Python setup step. The pytest wrapper is the durable one-command entrypoint;
   the Node invocation itself remains dependency-free.
2. The first full `test_watch.py` run failed in an unrelated Q&A fixture because
   its stub list lagged a newly added `drawModePicker`. Local `master` moved
   during the lane and already contained that exact sibling fix; rebasing made
   the required full-file run green. The instruction to rebase before reporting
   prevented this from becoming a misleading lane failure or an out-of-scope
   edit.

No brief premise was otherwise wrong, and the lane-private red-proof tooling
worked as documented.
