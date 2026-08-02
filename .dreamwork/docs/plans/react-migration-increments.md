# React migration increments after the bundle already exists

> **Coordinator action required before landing:** add
> `react-migration-increments` to the plans row in
> `.dreamwork/docs/doc-map.md`. This lane does not own that custodial file.
>
> **Planning only.** No production seam changes here, so no red-proof is owed.

This plan serves DREAMWORK goal 1, now the main near-term goal: new Web UI
features belong on the React side of the transition. It applies the ratified
#591 survivor without reopening it: a component package derived from the same
builders the dashboard serves, plus component-native new surfaces. It does not
propose a parallel hand-maintained library or a wholesale rewrite.

## Verdict

The build step is already built. Rebuilding it would be waste.

The remaining local work is to widen the **derived export surface one wrapper
at a time**, after the existing QaCard export passes the authenticated design
tool checkpoint. Each wrapper calls its incumbent builder and owns no markup.
New dashboard surfaces must continue to enter the runtime registry directly,
with no builder twin.

There are two current exceptions to that last sentence: `/settings` and
`/tasks2` were added as `buildSettings` and `buildTasks2` after the React
ruling. They are migration debt, not evidence against the survivor. Converting
them is separate surface work because doing so here would turn a bundle/export
plan into the wholesale migration the ruling rejected.

## What exists now, measured at `9601556625dc`

The command contract is exact:

- `just --dry-run build-client` exits 0 and expands to the pinned npm install
  check plus `python3 dev/build_client.py`.
- `just --dry-run build` exits 1: `Justfile does not contain recipe 'build'`.
- `python3 -c 'import client_dist; print(client_dist.check("."))'` reports
  `state: ok` and `client/dist matches 15 inputs and 3 outputs`.

The build's actual surface is:

| Evidence | Current measured amount | What it proves |
|---|---:|---|
| `dev/build/package.json` | 11 lines | pinned esbuild 0.25.10, React 18.3.1 and ReactDOM 18.3.1 |
| `dev/build/package-lock.json` | 558 lines | the npm toolchain is committed and pinned |
| `dev/build_client.py` | 320 lines | builds the design bundle, byte-copies the stylesheet, builds the native bundle and writes the manifest |
| `client_dist.py` | 299 lines | derives the eight served assets plus native sources, and checks hashes without Node |
| the eight `_CLIENT_ASSETS` under `client/` | 12,748 lines / 683,199 bytes | the source population used by the build is the population `watch.py` serves |
| `dev/build/src/*.js` | 6 files / 775 lines / 36,744 bytes | React registry, delegation, probe, `/research`, and `/goals` already exist |
| `client/dist/manifest.json` | 41 lines | records 15 inputs and 3 outputs, including tool versions |
| `client/dist/ds/index.js` | 8,563 lines / 355,212 bytes | compiled design package; contains the served builders in the AST-derived page order |
| `client/dist/ds/styles.css` | 2,283 lines / 145,793 bytes | byte-identical copy of `client/style.css` |
| `client/dist/native.js` | 792 lines / 156,203 bytes | React/ReactDOM, registry and native surfaces already ship on the page |

How much component surface already ships:

- `dev/build/src/native-entry.js:29-46` creates the registry and registers an
  unreachable probe plus two real routes: `/research` and `/goals`.
- `client/router.js:2081-2112` resolves native routes, verifies/unmounts prior
  roots, clears `#view`, and mounts the selected component.
- `dev/build/src/research.js` is 75 lines. Its React-owned shell delegates
  `artifactRow` and `label` through `fromBuilder`; this is already the visible
  end-to-end proof that React and an incumbent builder coexist.
- `dev/build/src/goals.js` is 237 lines and is a born-native read/write
  surface; it delegates only Markdown rendering through `mdB`.
- `dev/build/wrapper-exports.js` is 45 lines and exports exactly one design
  wrapper, `QaCard`. Its companions are 24-line `.d.ts`, 24-line fixture and
  16-line prompt files. `dev/capture/wrappereq.mjs` (88 lines) compares the
  builder and wrapper through the same parser and serializer.
- `watch.py:569-587` already supports multiple inline classic scripts, and
  `watch.py:681-714` already deploys and loads `native.js`; this is not future
  work.

What the build does **not** yet do:

- The design package exports no component other than QaCard.
- The authenticated design-tool ingestion checkpoint has not been performed.
- No guard currently makes “new surfaces are born native” a standing rule;
  the later `/settings` and `/tasks2` builders demonstrate the gap.
- The legacy surface builders remain legacy by design. Exporting a delegating
  wrapper does not convert or duplicate them; the builder stays the only
  markup authority.

## Gate model used below

`dev/land_lane.py:52-59` declares six gates:
`red-proof-history`, `lint-precheck`, `named-tests`, `guard-selection`,
`repo-wide-guards`, and `lint-comparison`. “Risky phase” below names the phase
most likely to REFUSE, not the only phase that can fail.

Every future estimate below is explicitly a **guess**, not elapsed-time
evidence. Git records commits, not hands-on duration, and no comparable landed
wrapper has a trustworthy start/stop receipt. Each dispatch is therefore
capped at 20 minutes. If its source + contract + fixture + rebuilt dist cannot
land atomically inside that cap, it REFUSES and is re-planned; it does not
commit a wrapper without its package artifacts.

## Increment sequence

### 1. QaCard proves the delegating-wrapper path end to end — ALREADY DONE

**Goal:** export one component that calls the real `qaCard`, ship its typed
contract and fixture, build it, and prove DOM equality.

Already-landed files: `dev/build/wrapper-exports.js`,
`dev/build/ds-src/QaCard.{d.ts,fixture.json,prompt.md}`,
`dev/capture/wrappereq.mjs`, `client/dist/ds/index.js`, and
`client/dist/manifest.json`. Coverage: full `test_client_dist.py` plus the
registered `wrappereq` capture. The equality assertion compares the real
builder result with the mounted wrapper after both traverse the same DOM
parser/serializer; the purity assertion rejects a wrapper containing an HTML
tag literal.

This is the smallest end-to-end proof the task asks for, so it is marked done
rather than proposed again. Its historical risky gate was **named-tests**:
the committed artifact once reproduced only in the lane's physical path, and
the reproducibility test skipped in a fresh worktree. Both faults are now
closed by the current path-independent double-build test.

**External checkpoint before increment 2:** Max runs this already-built
QaCard package through the authenticated design tool. This is not a repo
increment and has no `land-lane` fiction. If ingestion rejects the wrapper or
its granularity is poor, increments 2-9 REFUSE; authoring more wrappers before
that result would spend the budget the checkpoint exists to protect.

### 2. Export `Label`

**Goal:** add the smallest stateless primitive after QaCard.

Touches `dev/build/wrapper-exports.js`, new
`dev/build/ds-src/Label.{d.ts,fixture.json,prompt.md}`,
`dev/capture/wrappereq.mjs`, `client_dist.py` only if companion discovery is
not already tree-derived, and rebuilt `client/dist/ds/index.js` plus
`client/dist/manifest.json`. Tests: full `test_client_dist.py` and registered
`wrappereq`; equality must fail if `label()` output differs by one node.

Estimate: **15-20 minutes, guess.** Risky phase: **lint-comparison** — any
source/manifest/output mismatch adds the permanent `client/dist` ERROR row.

### 3. Export `PipBtn`

**Goal:** prove a small interactive builder remains exact, including its
attributes and disabled state.

Touches the same wrapper/companion/capture/dist families as increment 2, with
`PipBtn.*` companions. Tests: full `test_client_dist.py` and `wrappereq` with
enabled and disabled fixture cases; the assertion covers serialized
attributes, not merely text.

Estimate: **15-20 minutes, guess.** Risky phase: **named-tests** — a fixture
that exercises only the label text would pass while interaction attributes
were wrong, so the full named module must reject the shallow fixture.

### 4. Export `Expand`

**Goal:** expose the disclosure primitive without restating its nested markup.

Touches the same families with `Expand.*` companions. Tests: full
`test_client_dist.py` and `wrappereq` over open/closed and non-empty body
fixtures; equality catches a missing disclosure node.

Estimate: **15-20 minutes, guess.** Risky phase: **named-tests** — the most
likely refusal is incomplete fixture state coverage rather than the bundle.

### 5. Export `FollowThread`

**Goal:** expose one real threaded content primitive and its nested entries.

Touches the same families with `FollowThread.*` companions. Tests: full
`test_client_dist.py` and `wrappereq` over empty and multi-entry threads; the
fixture must assert it examined more than zero entries.

Estimate: **15-20 minutes, guess.** Risky phase: **named-tests** — an empty
thread is a genuine state but is also a vacuous equality population unless a
non-empty fixture is mandatory.

### 6. Export `QaCompose`

**Goal:** expose the answer/note composer while bounding its ambient page
dependencies explicitly.

Touches the same families with `QaCompose.*` companions and may extend the
single ambient-context helper in `dev/build/wrapper-exports.js`. Tests: full
`test_client_dist.py`, `test_client_env.py`, and `wrappereq`; they must prove
the temporary ambient bindings restore after both success and a thrown
builder.

Estimate: **15-20 minutes, guess.** Risky phase: **red-proof-history** — this
is the first future wrapper likely to widen ambient behavior, so its proof
must sabotage the real binding/restore seam and retain a discriminating red.

### 7. Export `ArtifactRow`

**Goal:** expose the row shared by review/research listings, including both
kind variants.

Touches the same families with `ArtifactRow.*` companions. Tests: full
`test_client_dist.py` and `wrappereq` over `review` and `research`, decided and
undecided fixtures; the assertion covers exact row DOM and link destinations.

Estimate: **15-20 minutes, guess.** Risky phase: **named-tests** — one kind
passing does not cover the parameterized second surface.

### 8. Export one route composition: `Reviews`

**Goal:** prove a whole legacy view can be consumed as a derived component
without converting or copying it.

Touches the same families with `Reviews.*` companions. Tests: full
`test_client_dist.py` and `wrappereq` over empty and populated review lists;
the populated fixture must contain more than one distinct row.

Estimate: **15-20 minutes, guess.** Risky phase: **named-tests** — a whole-view
fixture is more likely than a primitive fixture to omit a live branch.

### 9. Export remaining route compositions one per commit

**Goal:** repeat the proven Reviews shape for one builder per independently
landable commit, in rising interaction risk:

1. `Answers`
2. `Settings`
3. `Chat`
4. `File`
5. `Review`
6. `Tasks2`
7. `Questions`
8. `Question`
9. `Dashboard`

Each commit touches only the shared wrapper file, that route's three new
companion files, `wrappereq`, and rebuilt ds/manifest outputs. Each runs full
`test_client_dist.py` and `wrappereq`; `Chat` additionally runs the full
chat-render assertions in `test_watch.py`, `File` the full file-view
assertions, and the qaCard-family routes the full qaCard capture. Each wrapper
equality fixture names the incumbent builder branch it exercises and requires
a non-empty sentinel.

Estimate: **15-20 minutes per route, guesses.** The risky phase is
**named-tests** for Answers through Review, **red-proof-history** for Tasks2
through Question where ambient or interaction seams widen, and
**repo-wide-guards** for Dashboard because it composes the broadest shared
population. If Dashboard cannot fit atomically in 20 minutes it REFUSES; the
plan does not hide a larger rewrite behind a small estimate.

### 10. Make “new surfaces are born native” a standing, non-WARN fact

**Goal:** prevent a third post-ruling builder surface after the existing
Settings/Tasks2 debt is separately adjudicated.

This increment starts only after those two exceptions have either converted
or received an explicit grandfather record. It touches the smallest existing
authority-map/check surface selected at implementation time, its full test
module, and no route implementation. The check must enumerate routed
surfaces, native registrations and any declared legacy authorities; it emits
an **OK** row naming the examined population, never a permanent WARN. Tests
must construct both a duplicate authority and a route in neither registry.

Estimate: **15-20 minutes, guess.** Risky phase: **red-proof-history** — a
new guard is not evidence until sabotage at the real route/registry seam
produces a discriminating failure and restoration returns green.

## Landability and consistency

Every implementation increment names a non-empty test selection; none relies
on an empty selection. The design-wrapper commits do not alter the dashboard's
served DOM, and each includes its own source, contract, fixture, capture
extension, rebuilt output and manifest. Therefore **no adjacent pair must land
together** and the UI is not visibly broken between commits.

The planning branch itself is the known exception: it is docs-only. Current
`land-lane` refuses an empty named selection, and the new plan also makes lint
report the missing coordinator-owned doc-map row. Until the coordinator adds
that row, this branch is correctly not landable. Naming `test_lint.py` is the
non-empty workaround because it directly exercises plan-map completeness; an
unrelated test with “plan” in its name is not coverage.

For every implementation commit, `just build-client` is atomic with the
source change and all committed `client/dist` outputs. `just pytest
test_client_dist.py test_client_assets.py test_client_env.py` is the minimum
client selection, expanded by the route-specific full module above, followed
by `just pytest $(python3 dev/repo_wide_guards.py list)` and lint row-set
comparison.

## Does any increment touch `watch.py` inline HTML?

**No.** None of these increments needs to edit `watch.py`'s HTML envelope.
`page_shell` already places the generated native runtime between the incumbent
builders and the router, and the visible `/research` and `/goals` components
already use that path. The literal HTML still in `watch.py` is server-owned
document/error/highlight framing, not the old UI surface builders the human
meant.

This distinction matters: the derived-wrapper sequence expands what the
design tool can consume but intentionally makes no visible dashboard change.
Visible replacement happens only in separately-scoped surface flips (as
`/research` already demonstrates) or in born-native new routes (as `/goals`
demonstrates). Claiming that wrapper exports “replace inline HTML” would read
as a stronger claim than the code supports.

## How this plan could be wrong

1. **The authenticated ingestion may reject or badly degrade QaCard.** That
   refutes increments 2-9 at their prerequisite; the response is to stop, not
   to design a parallel library.
2. **The requested outcome may mean visible conversion of every legacy
   route.** That is not this survivor: it is wholesale migration, explicitly
   refuted in the ruling. This plan does not smuggle it back in under the word
   “wrapper.”
3. **A route wrapper may take more than 20 minutes once its ambient inputs are
   measured.** The estimates are guesses. The increment refuses rather than
   land a wrapper without equality fixtures and rebuilt outputs.
4. **Settings and Tasks2 expose a process failure.** They were added after
   the ruling as builders. If their existence means the project no longer
   accepts “born native” as binding, this plan's final guard is wrong; that
   requires a new human ruling, not a quiet exception.
5. **The bundle may already contain more exports by landing time.** Re-run the
   manifest/input/output counts and inspect `wrapper-exports.js` before every
   dispatch. Any listed increment already present becomes **ALREADY DONE** and
   is not repeated.

## Citation evidence opened for this plan

- **#591:** “one All-✔ survivor: a DERIVED component surface … plus
  born-native components for new surfaces.” This is the design boundary.
- **#630:** “The bundle step RUNS and is reproducible today; your job is to
  establish what it does NOT yet do.” This is why increment 1 is marked done.
- **#1010:** “an empty selection is indistinguishable from broken derivation.”
  This is why every implementation row names real tests.
- **#1018:** “a documentation-only branch has no test by construction” and
  the current workaround is to name `test_lint.py`, which actually exercises
  plan-map completeness. This is the planning branch's landability exception.
- **#794:** “The COUNT was stable-to-falling while the COMPOSITION changed.”
  This is why lint verification compares the complete WARN row set.
