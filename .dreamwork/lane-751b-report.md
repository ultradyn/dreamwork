# Lane 751b report — P3 `/research` native conversion

## Verdict

**PASS.** `/research` now has one native React render authority. The runtime is
inlined before route selection, `buildResearch` is deleted in the same atomic
flip commit that registers and routes the component, and the component keeps
`artifactRow` builder-owned by consuming it through the delegating wrapper.

Final implementation commits after rebasing onto local `master`:

- `a28bfc0d` — `feat(#751): inline the native runtime before route selection`
- `56364e48` — `feat(#751): flip research to native component authority`

## Decision and implementation

I chose the inline delivery shape. It preserves the dashboard's one-response
contract and the existing guard against external scripts. An external
`<script src>` would recreate P2's measured false-green: content-containment
checks could pass while the browser fetched React separately. The page now has
three ordered classic scripts: builders, byte-for-byte `native.js`, then the
router. The native bundle still excludes the concatenated client assets and
their top-level side effects.

The flip commit:

- adds `dev/build/src/research.js`, including listing, named empty state, and
  iframe artifact sub-mode;
- delegates every row to `artifactRow` through `fromBuilder`;
- registers `research`, routes it away from the string-builder dispatch, sends
  tick data through the existing `setData` seam, and unmounts before a builder
  route takes `#view` back;
- deletes `buildResearch` with zero-commit overlap;
- rebuilds all committed dist artifacts and extends the `research` and
  coexistence browser guards.

The binding task line from `#751` was:

> "THE WORK: /research (the listing) flips native. buildResearch is DELETED in
> the same commit — the flip-commit rule, zero-commit overlap"

The settled doctrine from `#668` was applied without widening it:

> "the webui state is secondary ... and is fine to be a 'second description'
> of state."

Its unchanged boundary remains:

> "He did not touch the on-disk master state rule, which stays exactly as
> strict as it was."

## Verification

- `node --check` passed for both edited client files, all four edited/new
  native sources, and both edited capture guards.
- After the rebase: `python3 -m pytest -q test_watch.py test_client_dist.py`
  reported `518 passed, 65 subtests passed in 73.73s`.
- `just build-client` ran twice after the rebase. Both runs emitted
  `ds/index.js dda8e80621e0`, `ds/styles.css 2994a6e271ec`,
  `native.js 985a022c536f`; `git diff --exit-code -- client/dist` was clean.
- `python3 lint.py` reported `clean (6 warning(s))`, with only the existing
  answered-date, worktree-ledger/status, and near-duplicate warnings. It also
  reported `client/dist matches 14 inputs and 3 outputs`.
- One authorised targeted browser run used ad-hoc port `45673`. Preflight:
  `OK [load 23.18 (1.4x cores) on 16 cores, 4 ccc lane(s)]`; result:
  `PASS research` and `1 of 1 registered guard(s) ran and judged`.

## Red-proof

### Direction 1 — break the conversion

Using `dev/redproof.py`, I changed the route exclusion to:

> `if (false && isNativeRoute(view.name)) return null;`

The focused test went red on the discriminating message:

> `a native route must bypass the string-builder dispatch`

The tool restored and verified the original bytes. Its final gate says:

> `check: clean — 1 injection(s) registered, all restored and absent from the
> working tree and from this branch's commits`

### Direction 2 — flip works, surface is wrong

The `research` guard constructs the named adversarial cases rather than
inferring success from a non-empty mount:

- an intercepted `data.json` with `research: []` must have one owned root,
  zero rows, and the explicit `no built research artifacts yet` text, so a
  blank native box cannot pass;
- a real mtime tick must increment the seen counter exactly once while keeping
  the same instance id, so a remount cannot masquerade as a state-preserving
  update;
- navigation to `/reviews` must leave zero mounted/owned native roots, and
  returning must produce a fresh research instance;
- the existing artifact-view assertions still require the iframe sub-mode,
  `/researchraw` source, crumb return, and restored listing.

The targeted guard ran all of these and judged PASS. The false-green shape for
each is closed by an explicit precondition or identity pair; no remaining case
was found where the flip could mount successfully while one of these named
surfaces silently rendered the wrong information.

## Rebase and scope

Local `master` advanced by eleven commits during the lane. Both commits rebased
cleanly onto `83d7d03c`; there were no conflicts. Post-rebase tests, rebuild,
lint, and red-proof all passed. No delta machinery was touched, no fixed
dashboard/dev port was bound, and nothing was pushed or merged.

No out-of-scope product work was found.

## DOGFOOD REPORT

The resume summary named only eight staged files, while the surviving index
actually held fourteen, including the new component, two capture guards, two
test files, and `watch.py`. Requiring `git status` plus the staged diff first
prevented those surviving edits from being overlooked.

The inherited `31 passed` result was also too narrow to establish the brief's
full `test_watch.py` gate. The complete run found two stale single-script
assumptions: one regex examined minified runtime locals as though they were
router assignments, and the syntax gate concatenated HTML script boundaries
into JavaScript. Both were repaired to inspect the correct script boundary.
The brief's explicit full-suite requirement was the only reason those were
found before hand-off; no further workflow change is proposed.
