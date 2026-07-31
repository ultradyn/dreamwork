# #732 design recommendation — bind the delta's second implementation

## Headline

**The valid per-key composition agrees today, but the shipped wire contract
already does not.** `client/router.js:2453-2464` ignores both `base` and
`check`. It will apply a delta whose `base` is not the version of the document
it currently holds, accept a deliberately wrong `check`, advance `lastDataV`,
and return the mixed document as success.

That is not only a missing test. It contradicts:

- `.dreamwork/docs/plans/ws-delta-transport.md:152-156`, which requires the
  client to hash the reconstruction and refetch in full on mismatch;
- `file-formats.md:2185-2189`, which documents that self-heal as the phase-1
  contract;
- `.dreamwork/lane-641-report.md:5-8`, which says the client self-heals on
  `check`; and
- the comment immediately above `applyDataResponse`, which says the same.

No client code reads `j.check`; there is no SHA-256/Web Crypto code under
`client/` at all.

I confirmed the consequence with a read-only Node probe that loaded the exact
`applyDataResponse` definition from `client/router.js` into `node:vm` (the
function marker was asserted unique). Given:

```text
held version: other-version
held data:    {target: "/wrong-base", tint: "blue", survivor: true}
response:     {v: "v2", base: "v1", changed: {tint: "red"},
               removed: [], check: "deliberately-wrong"}
```

the production function returned:

```text
{target: "/wrong-base", tint: "red", survivor: true}
```

and advanced `lastDataV` to `v2`. This is exactly the silent mixed-document
failure #732 is concerned about.

## What agrees and what does not

The narrow operation on a **well-formed delta applied to its declared base**
does agree:

| Case | Python (`apply_delta`) | JS (`applyDataResponse`) | Verdict |
|---|---|---|---|
| removed keys | Copies the base, then `pop`s each removed key | Copies `data`, then `delete`s each removed key | Same |
| empty `changed` | Applies removals, then an empty update | `{}` is truthy, so it enters the delta branch and applies removals | Same |
| changed keys | Whole-value update after removals | Whole-value `Object.assign` after removals | Same; `changed` wins if a malformed envelope names a key in both lists |
| nested mutation | Replaces the whole top-level value | Replaces the whole top-level value | Same |
| `generated`-only | `compute_delta` emits empty `changed`; applying it carries the base's `generated` | Empty delta carries the held document's `generated` | Same |
| unchanged sentinel | Not an `apply_delta` case; the effective document stays the base | Returns `null`, so the caller skips `setData` | Same end state, deliberately different return interface |
| unknown `since` sent to the server | `_data_json_response` returns the full document | A response without `changed` takes the full-document branch | Safe and consistent |
| delta `base` unknown to the client | The reconstruction proof explicitly passes the matching base | `j.base` is ignored; the delta is applied to whatever global `data` now contains | **Disagrees** |
| `check` mismatch | Server supplies a hash of the target document | `j.check` is ignored | **Disagrees with the documented protocol** |

Key order is not a valid source of truth here. `compute_delta` iterates a
Python `set`, so the insertion order of newly changed keys is not promised in
the first place. Both appliers preserve surviving base keys, overwrite an
existing key in place, and append genuinely new ordinary named keys in the
order received. JavaScript's special enumeration order for integer-index keys
could differ if the top-level schema ever gained numeric-looking names, but
that still would not be a document-value disagreement. JSON object member
order is outside the delta contract and `derived_check` uses `sort_keys=True`,
deliberately making the check order-insensitive. A test should compare document
values, not `JSON.stringify` byte order.

There is one additional malformed-envelope difference worth naming but not
mistaking for today's server path: Python would honour `removed` if `changed`
were absent, while JS classifies such an object as a full document. The current
server always emits `changed`, including `{}`, so this is a fail-safe/schema
case rather than the present divergence.

## The stale-base case is reachable

This does not require a malicious server. `applyDataResponse` chooses its base
at **response time** from global `data`, not at request time from the version
named in the request:

1. A live tick asks for a delta from version `v1` for the current burn step.
2. While that fetch is awaiting its response, the user cycles the burn step.
   `cycleBurnStep` resets `lastDataV`, fetches a full document for the new
   bucketing, and installs it.
3. The older tick response arrives with `base: "v1"` for the old bucketing.
4. The current client applies it to the new-bucketing document, advances the
   version, and has neither the `base` check nor the `check` hash to reject it.

The next poll can now legitimately say "unchanged" for that advanced version,
so the wrong document can persist until another real change or a forced full
fetch. The protocol already carries both belts that would catch this; the
client simply does not use them.

## Harness recommendation

### 1. First: `node --test`, with the shared cases in the same increment

Use Node's built-in `node:test`, `node:assert/strict`, `node:fs`, and `node:vm`.
The measured Node here is v22.23.1 and supports `--test`; the existing
`dev/capture/*.mjs` commands and `test_watch.py`'s Node syntax check already
establish that direct Node execution is an accepted development surface.

Do **not** add a root `package.json`, a test framework, or another lockfile.
There is already a dependency tree under `dev/build/`, but it exists for the
client bundle. Pulling Jest/Vitest/Mocha or even the build install into this
test would turn a pure-object check into `npm ci` infrastructure for no gain.

The cheapest honest access to the production function is:

- read `client/router.js` as text;
- assert exactly one `function applyDataResponse(j)` marker and one following
  `async function cycleBurnStep` marker;
- execute that exact slice in a small `node:vm` context supplying `data`,
  `lastDataV`, and `lastMtime`; and
- invoke it over the cases.

This is intentionally a test-only internal seam. Loading the whole router
would require faking thousands of lines of browser globals, while copying the
function into a test would create a third description. If the router later
becomes an ES module, replace the slice with a normal import. Until then, a
unique-marker failure is loud and local.

**Cost:** one small `.test.mjs` file and a few runner/glue lines; zero packages,
zero installs, no browser, no server, no port, and no `client/dist` rebuild.
It should run in well under a second. The real cost is not Node; it is exposing
the classic-script closure honestly, and `node:vm` keeps that cost contained in
the test.

The first born-red cases should include the five existing adversarial shapes,
an empty `changed` plus a real removal, a mismatched `base`, and an invalid
`check`. The last two must specify the safe outcome (one full refetch, no
version advance on the unverified reconstruction), not freeze today's bug.
That means the correctness repair and its red test should land together; a
green-only composition harness is not enough to call the shipped contract
closed.

### 2. Shared fixture: part of step 1, not a later embellishment

Keep one persistent fixture containing only the named `base`/`next` pairs and
their case labels. Do not hand-write one delta in Python and another in JS.

The strongest low-cost flow is:

1. Python reads those pairs, asserts each precondition, and derives the actual
   envelope with production `compute_delta` and `derived_check`.
2. Python proves `apply_delta(base, envelope) == next` and writes the derived
   envelopes to a temporary JSON file.
3. `node --test` reads that same temporary set and applies the exact production
   JS function to each base.
4. Both sides compare values minus `generated` against the same `next` object.

That leaves one description of the adversarial inputs and **no committed
description of what Python's delta ought to be**. It is stronger than two test
files containing matching literals on the day they are written.

**Cost:** one small JSON fixture plus a modest refactor of the existing Python
test and subprocess glue. It adds some lines, but they buy the central property:
the two language implementations are exercised against the same runtime-derived
envelopes. I would pay this cost immediately rather than land option (a) with
duplicated case literals.

The `check` repair has a separate cost that the harness must not hide. The
server hashes the exact bytes of Python's `json.dumps(..., sort_keys=True,
default=str)`. A naïve hash of JS `JSON.stringify` is not equivalent (spacing,
recursive key ordering, Unicode and number formatting can differ). Either the
wire must define a language-neutral canonical encoding or the JS canonicalizer
must be tested byte-for-byte against Python before Web Crypto verifies the
SHA-256. This is still a zero-npm problem, but it is not a one-line assertion.

### 3. Browser round-trip guard: strongest integration, third to build

A browser guard should eventually drive a real full fetch, a real delta update,
and compare the client's held document with a contemporaneous full document.
It is the only option here that covers request construction, server response
classification, JSON parsing, asynchronous interleaving, application, and the
wire together.

It is not the first check to build:

- it needs a fixture server, mutation choreography, browser state access, and
  guard registration;
- it exercises a handful of shapes per expensive run rather than the whole
  adversarial table cheaply;
- its result depends on a quiet fleet; and
- reproducing the stale-response ordering needs interception or deliberate
  response control, which is more machinery again.

**Cost:** tens to low hundreds of lines plus seconds-to-minutes of serial
runtime and the repo's existing load/flakiness discipline. Add it after the
unit binding is green, or when phase 2's SSE path makes a real-wire regression
guard pay for more than this one composition. It complements the Node binding;
it should not replace it.

## Recommended sequence

1. Treat ignored `base`/`check` as a current P1 correctness defect, not merely
   future test debt.
2. In the repair lane, build the zero-dependency `node --test` harness first,
   fed by Python-derived envelopes from one shared set of source pairs.
3. Make the stale-base and bad-check cases go red for the discriminating reason,
   then implement the full-refetch/no-version-advance behaviour.
4. Keep the valid-delta equivalence cases as the permanent cross-language bind.
5. Add a real browser round-trip guard only after that cheap proof is in place.

This keeps the test interface small: one input table exercises both
implementations, while browser orchestration remains outside the unit seam.

## What I would not do

- **Do not delete the JS delta path and always refetch in full.** That removes
  phase 1's responsiveness/bandwidth feature; it does not verify it.
- **Do not add Jest, Vitest, Mocha, jsdom, or a root npm project.** Node's
  standard library already supplies everything this pure-object test needs.
- **Do not copy the five object literals separately into Python and JS.** That
  recreates the two-descriptions problem in the tests.
- **Do not copy `applyDataResponse` into the test.** Execute the production
  definition, or the test can remain green while the browser implementation
  drifts.
- **Do not use a source-token assertion** such as checking that `delete` and
  `Object.assign` occur. That verifies spelling, not reconstruction, and this
  repo already has evidence that literal seam guards expire when code moves.
- **Do not build the browser guard first.** It is the highest-cost and
  lowest-case-count way to answer the narrow equivalence question.
- **Do not call the dead `check` field a self-heal.** Either implement and test
  its canonical hash/refetch contract or explicitly revise the protocol and
  its docs. The current half-state is the worst option: it advertises a safety
  belt that is not connected.
- **Do not hash naïve `JSON.stringify` output and declare parity.** A check that
  disagrees because the two languages serialized the same value differently
  would force a full refetch on every delta and train maintainers to ignore the
  guard.

No browser guard or server was run for this investigation, and no port was
touched.
