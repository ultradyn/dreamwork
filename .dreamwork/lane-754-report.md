# Lane 754 report — restore the real-route coexistence closures

## Verdict

**PASS.** `dev/capture/coexist.mjs` once again binds both deliberate
closures to the production `/research` registry entry without resurrecting
the synthetic probe:

- every React-created element in the listing is inspected for `class`, down
  through child elements and stopping only below a builder-owned Delegate
  boundary;
- the production component is mounted over non-empty `/reviews` builder DOM,
  allowed to settle its mount effect, unmounted, and compared to the original
  `#view` as UTF-8 bytes.

The source claim in `dev/build/src/registry.js` is therefore true again:

> `dev/capture/coexist.mjs` asserts that round-trip byte-for-byte.

## Changes

The guard now drives this sequence:

1. Navigate through the production `/research` route and then to the real
   `/reviews` builder route.
2. Assert that the builder baseline is real and non-vacuous: its serialized
   DOM exceeds 500 bytes and its label is `reviews`.
3. Mount the registered production `research` component over that builder
   DOM, wait until `data-dw-research-seen="1"` proves the mount effect settled,
   and assert that real delegated rows rendered.
4. Recursively inspect React-owned elements for class attributes. Builder
   descendants under `[data-dw-delegate]` are intentionally excluded because
   those builders legitimately own their established style and behavioural
   classes; the Delegate element itself is inspected.
5. Unmount and compare the before/after UTF-8 byte arrays. A failure names the
   first differing offset, both byte values, and both lengths.

The existing deliberate-collision phase exposed a related defect while being
re-run. Morphdom currently removes `data-dw-mount` but may reuse the same
`<div>` node, so master's `verify()` returned `mounted` merely because
`document.contains(container)` stayed true. The untouched master guard was
reproduced red with:

> `FAIL the ownership violation is named, never a silent blank box`

`verify()` now requires the container to remain in its original host **and**
retain the route's ownership marker. This is the smallest correction that
makes its promised reading true for both physical deletion and in-place node
reuse. The guard catches teardown's expected `NotFoundError` only after the
deliberately corrupted state has been measured, so teardown cannot erase the
verdict.

## Red-proof

### Direction 1 — the checks fail on the real defects

Both injections were armed and restored with `dev/redproof.py`.

I added `className: 'cx-754-redproof-child'` to the production Research root,
rebuilt `client/dist`, and appended one ASCII `!` byte after registry unmount.
One focused red run at load 23.08 on 16 cores named both defects:

> `FAIL THE RUNTIME ADDS NO CLASS to React-owned elements; offending element and class: div[data-dw-research-instance="r3zq2f8dd"] class="cx-754-redproof-child"`

> `FAIL unmounting the real /research component restores #view byte-for-byte; first differing bytes: offset 880: <end> -> 0x21 (lengths 880 -> 881)`

The restored-source build returned `client/dist` to its committed bytes before
the real fix was applied. Final red-proof gate:

> `check: clean — 2 injection(s) registered, all restored and absent from the working tree and from this branch's commits`

### Direction 2 — attempted false-greens

- **Class on a child rather than the mount root:** closed. The walk begins at
  `[data-dw-mount="research"]`, recursively visits every React-created child,
  and includes each Delegate wrapper before stopping at its builder-owned
  HTML. The injected class was on the Research child, not the mount container,
  and the failure named that exact element and token.
- **Class added by the mount effect after the first synchronous sample:**
  closed for the component's settled mount state. Sampling waits for the real
  component's `seen === 1` sentinel; failure of that precondition is red rather
  than a classless pass. A timer that fires only after the component has been
  unmounted cannot violate the inspected live tree.
- **Both round-trip sides empty:** closed. The pre-mount builder DOM must be a
  named `reviews` surface over 500 serialized bytes, and the native mount must
  contain the real Research instance, at least one Delegate, and over 200
  serialized bytes before unmount.
- **Both sides equal but the mount did no work:** closed by the same rendered
  component and Delegate preconditions.

No case remained where both new assertions passed while either property was
violated within the guard's declared settled-DOM trace window.

## Verification

- `node --check dev/capture/coexist.mjs`
- `node --check dev/build/src/registry.js`
- `node --check dev/build/src/research.js` after restoring the temporary
  injection
- `just build-client` twice after the final source change; both runs produced
  `ds/index.js dda8e80621e0`, `ds/styles.css 2994a6e271ec`,
  `native.js e1211897fd59`, and the same manifest SHA-256
  `7fc2b279150e05a8f3e6395adbcae3b871d901c75d8f09e80e650902a07daf51`
- focused browser guard on ephemeral port `34337`: preflight
  `OK [load 23.37 (1.5x cores) on 16 cores, 4 ccc lane(s)]`, then
  `PASS coexist` and `1 of 1 registered guard(s) ran and judged`
- `python3 lint.py`: `clean (6 warning(s))`; all warnings are the existing
  worktree-ledger/status, answered-date, and near-duplicate warnings, while
  `client/dist matches 14 inputs and 3 outputs`
- focused pytest baseline before the lane changes: 518 collected,
  516 passed, 2 skipped. After rebasing over the moving master, the same
  focused collection is 518 tests; the required final post-commit run reported
  `518 passed in 76.52s` after the final rebase.
- whole-repo collection was 2323 at dispatch (the supplied master baseline)
  and is 2324 after rebase. This lane adds no pytest test; the extra collected
  test arrived in the seven master commits rebased underneath it.

## Rebase, commits, and scope

Master advanced by twenty commits after dispatch. The lane rebased cleanly
twice, finally onto `92a24d21`; there were no conflicts. Current implementation
commits are:

- `0c6e60b3` — `test(#754): restore coexistence closure assertions`
- `e5337632` — `test(#754): sample class closure after mount effects`
- `40dcc035` — `fix(#754): detect morphdom ownership-marker loss`

No fixed dashboard/dev port was bound, every started server was killed, and
nothing was merged or pushed. `BRIEF.md` remains the untracked dispatch input
and was not committed. No unrelated product work was found.

## DOGFOOD REPORT

The task's premise said the collision pair had survived and `verify()` already
reported the root detached. The untouched master guard reproducibly disproved
that premise: morphdom preserved the node object while stripping its ownership
marker, so a contains-only detector silently called lost ownership healthy.
The lane would have reported a clean closure restoration if it had looked only
at its two new PASS lines. Keeping the full guard's original assertion list in
the gate exposed the stale premise and led to the narrow registry correction.

The dispatch also says **one targeted browser run is authorised** while
requiring two injected defects to be observed red and a restored implementation
to be observed green. Those obligations cannot literally be satisfied in one
invocation of a guard: the red run must exit failing and the restored run must
be a separate process. I treated "one" as one targeted guard name (`coexist`),
not one invocation, and used no other browser guard. The coordinator should
clarify that wording in future lane heads so faithful red-proofing does not
require silently choosing which instruction to violate.
