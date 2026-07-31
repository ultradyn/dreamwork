# Lane 630 P5 stage 2 report — one `QaCard` wrapper

## Verdict and measurement first

`QaCard` was ready enough for this increment. The production builder exists at
`client/components.js:820-822`, returns one outer `.qa` card, and is called by
four production builder paths (`qSection`, `buildQuestions`, `buildReview`, and
`buildQuestion`). Its render-time ambient reads reduce to the mutable `data`
and `view` bindings; `rmr` is used by post-mount indicator painting rather than
card construction, and the emitted onclick only names the existing
`submitCard` function for a real dashboard to resolve later.

The real fixture measured 1,741 characters after DOM parse/serialization. The
mounted wrapper measured the same 1,741 characters, and strict equality passed
after both sides went through the same detached-template parser and serializer.
That supports the local wrapper increment. It does **not** answer whether
claude.ai/design presents a useful editable component.

One prerequisite is shakier than the plan records. `ds/index.js` concatenates
all client sources, whose top-level startup expects the dashboard shell. In a
blank document it threw `composer mount main missing #cmdpalette` and
`morphdom is not defined`; injecting it a second time into a running dashboard
initially threw `composer already mounted by main`. The equality guard therefore
mounts the exported wrapper in an isolated root in the real shell, after
clearing the shell's composer ownership marker for the design bundle's one
startup. This proves the wrapper and bundle locally, but it is also the precise
question the external ingestion spike must answer: does the design tool analyse
the export without requiring the dashboard startup environment, or does the
package need a later side-effect isolation increment?

## What changed

- Exported **only** `QaCard` from `dev/build/wrapper-exports.js`. It calls
  `qaCard(q, k)` and supplies/restores the bounded `data`/`view` context. It
  contains no fallback markup and no palette.
- Added `QaCard.d.ts`, `QaCard.prompt.md`, and `QaCard.fixture.json` as authored
  build inputs under `dev/build/ds-src/`; `just build-client` copies them into
  `client/dist/ds/`, and pytest checks each copy byte-for-byte.
- Added and registered `dev/capture/wrappereq.mjs`. Its assertions are:
  builder output non-empty; builder output contains `class="qa"`; mounted
  output clears the runtime-derived 1,740-character floor; strict normalized
  equality; and no browser page errors.
- Rebuilt `client/dist`. The standing manifest remains **14 inputs / 3 hashed
  executable outputs**. The three design-only companion files are copied and
  pytest-guarded rather than added to the deployed-output manifest: adding
  them there would require editing `watch.py`'s AST-literal `DATA_SIBLINGS`
  shipping tuple, which this lane is explicitly forbidden to touch. The
  executable wrapper lives in manifest-guarded `ds/index.js`.
- No other wrapper, route conversion, live-route mount, token value, palette,
  `client/*.js` source, or `watch.py` edit landed.

Commits after rebasing onto local master:

- `7ef03934` — `feat(#630): export one derived QaCard wrapper`
- `baf73d6b` — `fix(#630): register the wrapper equality guard`

## Red-proof, both directions

### Wrapper equality

Direction 1 changed only the wrapper result, replacing the fixture key with an
equal-length wrong key, rebuilt the design bundle, and ran the browser guard.
All three preconditions stayed green at 1,741 / 1,741 characters. The exact
discriminating failure was:

> `FAIL QaCard wrapper serialization strictly equals qaCard builder serialization`

Direction 2 constructed the requested wrong-but-consistent case: a component
can mount a captured copy of today's builder string through
`dangerouslySetInnerHTML`; after the shared parser/serializer, equality still
passes. Equality alone therefore **cannot distinguish derivation from
coincidental identity**. The source purity check catches the ordinary copied
tag-literal form, but an adversarial restatement split across string fragments
or imported from an ungoverned file evades that regex. The honest guarantee is:
equality permanently catches drift between the current builder and the shipped
wrapper over the fixture, while purity makes the normal second-renderer mistake
loud; neither is a semantic call-graph proof.

### Wrapper purity

Direction 1 planted `const FORBIDDEN_COPY = '<span>';` in the governed wrapper
source. The detector first found more than twenty real tag literals in
`client/components.js`, then failed on the intended assertion:

> `dev/build/wrapper-exports.js states markup of its own (['span']). A wrapper must CALL the builder`

Direction 2 is the fragment/import bypass above: a manually maintained string
can avoid a contiguous `<tag` literal. It is a real open false-green, not
claimed closed.

The exact lesson title consulted before injection resolved once:
**A red for the wrong reason is indistinguishable from a red for the right one
in a `-q` summary**.

`python3 dev/redproof.py check` after restoration reported:

> `check: clean — 4 injection(s) registered, all restored and absent from the working tree and from this branch's commits`

## Verification

- Rebased cleanly onto local `master` `3d082c0d`; no hand resolution was
  needed. Post-rebase branch head before this report was `baf73d6b`.
- `just pytest test_client_dist.py` — **30 passed**.
- Focused browser guard `wrappereq` on ephemeral port `49013` — **PASS**;
  preflight load **24.84**, suite-start load **24.85** on 16 cores; runner
  confirmed **1 of 1 registered guards ran and judged**.
- `python3 lint.py` — **clean, 5 warnings**, matching the lane bar.
- `client/dist` — **OK, 14 inputs and 3 outputs**.
- No other existing browser guard asserts wrapper/builder equality. The new
  `wrappereq` guard is the precise coverage for the changed surface.

## External ingestion step still owed to Max

Upload the contents of `client/dist/ds/` to claude.ai/design: `index.js`,
`styles.css`, `QaCard.d.ts`, `QaCard.prompt.md`, and
`QaCard.fixture.json`. Render the fixture and judge both whether the export is
accepted and whether the string-mounted card is usefully editable at component
granularity. Also observe whether preview execution tolerates the concatenated
client startup assumptions described above. That authenticated upload is the
end-to-end signal; this lane did not attempt it and does not claim it passed.

## Issue evidence relied on

- `#630`: **"Stage 2 (wrapper exports, .d.ts, .prompt.md, fixture props) is
  next and §6-R5 still binds it: run ONE wrapper end-to-end through the design
  tool before authoring the rest."** This bounds the increment to `QaCard`.
- `#651`: **"a guard's message must name a mode the guard can actually detect,
  and the way to know is to construct that mode and watch it fail."** This is
  why the report quotes the discriminating failures rather than red counts.
- `#440`: **"a single supported way"** is the relied-on rule; this increment
  keeps one `qaCard(q, k)` render path and one styling source.

## DOGFOOD REPORT

The highest-value finding is the design bundle's startup assumption. The P1
story says concatenating the client sources is harmless for a tool with no
dashboard, but execution on a blank canvas fails before `DreamworkDesign`
becomes available because those sources expect dashboard DOM and morphdom.
The new guard had to expose this before it could judge equality. The external
spike should treat side-effect isolation as a first-class observation, not
only visual editability.

The brief also contains a narrow reporting tension: it supplies an absolute
coordinator `inbox.md` path and says to append there, while the boilerplate
says the lane writes its report and nothing else so the coordinator owns the
hand-off line. I treated `inbox.md` as the explicit delivery channel distinct
from the forbidden shared `.dreamwork/handoffs.md`; I did not touch
`handoffs.md`.

---

# #630 P5 stage 2 re-land — reproducible artifact repair

## Verdict and headline proof

**PASS.** Two builds from distinct absolute subjects, one with a physically
local `node_modules` copy and one using the invoking checkout's fallback,
produced byte-identical output. `cmp` passed for every output and the paired
sha256 readings were:

- `client/dist/ds/index.js` — `f7dc2b1681d077f32cda87fd81729a24734c16b62c17bdc49d40e77c83deb4c8`
- `client/dist/ds/styles.css` — `2994a6e271ec9614385089a52ba6fb1c45fe3bf0e73d717f91565140f376cd39`
- `client/dist/native.js` — `e1211897fd595304a88af9107df17ec2d3b4031e371189be81e091d845830be5`

The subjects were
`/home/xertrov/.cache/ud-dreamwork/lane-scratch/ud-dreamwork/cx-630p5c/measure/byte-proof.iHc70U/pytest/test_the_build_is_reproducible0/build-a`
and
`/home/xertrov/.cache/ud-dreamwork/lane-scratch/ud-dreamwork/cx-630p5c/measure/byte-proof.iHc70U/pytest/test_the_build_is_reproducible0/build-from-a-different-absolute-path`.
This is the invariant check. A supplementary scan
found no `/home/`, `/opt/`, `/srv/`, or lane name in committed artifacts, but
that spelling-dependent scan is not claimed as the proof.

## What changed and why

- Reverted revert `911b6ab7` as instructed. The immediate `git diff master
  --stat` was non-empty and listed the wrapper, `client/dist/ds/`,
  `dev/build/`, `client_dist.py`, and `test_client_dist.py` surfaces.
- Replaced the design bundle's absolute `NODE_PATH` resolution with a
  temporary `node_modules` symlink plus esbuild `--preserve-symlinks`.
  Module labels are now the stable virtual `node_modules/react/...` path,
  independent of checkout and toolchain location.
- Strengthened the reproducibility test to build twice from different
  absolute roots and different dependency topologies, assert both non-empty
  output inventories, compare every output pair, then compare against the
  committed artifacts.
- Closed the lane/gate gap: when this lane's `dev/build/node_modules` was
  moved aside, `just pytest test_client_dist.py` ran **30 passed, 0 skipped**
  by using the main-worktree toolchain. Before the change the same command was
  **28 passed, 2 skipped**; the reproducibility test explicitly skipped.
- Rebuilt and committed `client/dist/ds/index.js` and its manifest. The
  wrapper, fixture, declaration, prompt, equality guard, and mechanical
  one-export §6-R5 fence are restored unchanged.

The manifest distinction is now sharper: checkout location and the presence
of a local install no longer change output hashes, so **"built somewhere
else" collapses to the same bytes** rather than masquerading as stale output.
A manifest mismatch therefore still cannot narrate which real input/tool/output
change occurred, but it no longer confounds staleness with filesystem location.
That removes this `#136` false-red class instead of adding a special spelling
check for it.

No surface was converted, nothing was mounted into a live route, `watch.py`
was untouched, and no external service was authenticated to or uploaded to.
The earlier finding stands: claude.ai/design still has to judge a package whose
`ds/index.js` expects dashboard-shell DOM and morphdom during execution.

## Red-proof, both directions

### Reproducibility invariant

Direction 1 restored the real defect, not a proxy: it removed the controlled
symlink and `--preserve-symlinks`, and reinstated
`NODE_PATH=NODE_MODULES`. The injected source was read back before running the
test. The precise assertion failed before committed-output comparison:

> `building client/dist/ds/index.js from two different absolute paths, with and without local node_modules, produced different bytes — the artifact leaks its build location`

Direction 2 constructed a genuinely broken check input that initially passed:
both absolute build subjects pointed through symlinks to the same physical
fallback toolchain. Removing `--preserve-symlinks` then leaked the same real
toolchain path into both artifacts, so pairwise equality stayed green and only
the later committed-artifact comparison reddened. The test now physically
copies `node_modules` into one subject while leaving the other absent; the two
dependency locations genuinely differ, and the exact old fallback goes red at
the pairwise assertion above. No further path/topology false-green was found:
the compared output inventory is asserted equal and non-empty before hashes
are compared, and the committed-output comparison remains a second net.

The fixed file was snapshotted under the lane-private directory returned by
`dev/lane_scratch.py snap`. After each injection, `dev/redproof.py restore`
restored it; an explicit `cp` from the fixed snapshot and `cmp` verified the
restored bytes. Final gate:

> `check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits`

The consulted lesson title resolved uniquely:
**A red for the wrong reason is indistinguishable from a red for the right one
in a `-q` summary**.

## Verification

- Explicit two-path `cmp` proof — **PASS**, all three hashes paired above.
- `just pytest test_client_dist.py` with lane-local node_modules absent —
  **30 passed**, zero skips; advisory reported no other pytest suites and 35
  browser/guard processes.
- Focused `wrappereq` guard on post-rebase ephemeral port `45259` — **PASS**;
  preflight load **21.80** on 16 cores; **1 of 1** registered guard ran and judged. It
  catches wrapper serialization diverging from the `qaCard` builder.
- `python3 lint.py` — **clean, 5 warnings**, matching the current lane bar;
  `client/dist` reports **14 inputs and 3 outputs** current.
- `python3 dev/redproof.py check` — clean, quoted above.
- Rebased onto local `master` `d09b2598b8e3c104f4c0da2baa43dce923ae85f8`
  after it moved during report writing — cleanly, with no conflicts or hand
  resolution.

Post-rebase commits before this report:

- `1f546d11` — reapply the reverted #630 stage-2 increment
- `b04b0003` — `fix(#630): make design bundle path-independent`
- `f0d2a574` — `test(#630): vary build path and dependency topology`
- `8ce116a1` — `test(#630): vary physical toolchain location`

## Issue evidence relied on

- `#630`: **"P5 STAGE 2 MERGED THEN REVERTED. Merge eaef072a, revert
  911b6ab7. The wrapper work is sound and the lane's proofs held; the committed
  BUILD ARTIFACT is what failed"** — restore the increment; repair the artifact.
- `#755`: **"The check reports a contradiction for a human to resolve; it does
  not resolve it."** — no platform-path substring repair was added; byte
  identity exposes the contradiction.
- `#671`: **"the report accounts for BOTH halves of the correlation it
  performs"** — both output inventories and their non-emptiness are asserted
  before comparison.
- `#136`: **"present-but-unparseable is a fault and must look like one"** —
  missing toolchains remain an explicit skip, while the lane/main toolchain
  asymmetry no longer skips.
- `#702`: **"Nothing connects them and nothing complains when 'lanes' is
  populated and 'dreamers' is empty"** — the analogous local/fallback
  toolchain split is now connected in one test rather than inferred.
- `#651`: **"a guard's message must name a mode the guard can actually detect,
  and the way to know is to construct that mode and watch it fail"** — the
  exact fallback defect produced the quoted location-leak assertion.
- `#440`: **"a single supported way"** — dependency resolution is normalized
  inside the real builder; no wrapper or second build implementation was added.

## DOGFOOD REPORT

The brief's hypothesis about the lane/gate gap was correct and more valuable
than the first code fix: `just pytest test_client_dist.py` had skipped exactly
the two build tests when a worktree lacked `node_modules`, while the main gate
had an install and judged them. The skip count was visible, but a green summary
made it easy to report the file as passed. Reusing the main-worktree install
closes that ordinary lane case without making every pytest invocation run
`npm ci`.

The unexpected finding was that “two absolute source paths” is not sufficient
when both builds resolve dependencies through the same physical absolute
fallback: the same leaked path appears twice and compares equal. The proof must
vary the dependency's physical location too. That refinement is now executable
in `test_client_dist.py`, not left as report prose.

The corrected task-specific inbox wording is no longer contradictory: the
absolute `inbox.md` is the report-notification lane, while
`.dreamwork/handoffs.md` remains coordinator-only. No other brief or tooling
friction was found.
