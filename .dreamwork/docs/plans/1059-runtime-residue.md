# 1059 — Runtime residue of the React bootstrap, data context, and navigation cutover

> **Scoping pass 1 of 3 for #1053.** This pass covers the runtime half only.
> Pass 2 (build/deploy/harness) and pass 3 (final dependency and deletion
> plan) are **deliberately not done here** — naming that boundary is a
> finding, not a gap (§5).
>
> **Planning only.** No production code changes; no red-proof is owed. The
> document's own accuracy is the quality gate.

## Verdict

`client/router.js` holds 216 indexed functions. **20 of them** — 7 for
bootstrap/data context, 13 for routing/navigation — are the runtime residue
a React bootstrap + React Router cutover would have to own. The remaining
196 are surface-owned runtime (drafts, posture, motion, chrome, write
controls) that converts **with its surface**, not in a runtime pass; or
they are the second-renderer boundary the design refuses (§6).

The native-mount seam already exists and is the sanctioned path: `window.dwNative.registry`
(`router.js:2146`), `isNativeRoute` (`:2150`), `commitCurrent` (`:2164`),
`unmountNativeRoots` (`:2154`). `/research` and `/goals` already mount
through it. So "React bootstrap and routing" is not greenfield — it is
widening a seam that already carries two routes.

## Premise verification — all three hold, with refined citations

Re-resolved against the current tree (`fb644018`, 2026-08-03). The
citations were taken 2026-08-02; `client/` has moved, so each was checked.

### Premise 1 — "216 indexed functions" — HOLDS EXACTLY

Decomposed by syntactic form:

| Form | Count | How verified |
|---|---:|---|
| `function NAME(` declarations | 155 | `grep -cE '^\s*function [A-Za-z_$]\(' client/router.js` |
| `async function NAME(` declarations | 18 | `grep -cE '^\s*async function [A-Za-z_$]\('` |
| `const/let NAME = … =>` arrow assignments | 40 | combined grep |
| object-literal method shorthands (`save`/`restore`/`clear` in `dwDraft`) | 3 | `grep -nE '^\s{2,}[A-Za-z_$]\([^)]*\)\s*\{'` |
| **Total** | **216** | |

The 40 arrow assignments include closure internals of `DraftStore` (`tgt`,
`id`, `v1Key`, `legacyKey`, `parseRec`, etc. at `:1605`–`:1780`), so the
"indexed" count is honest: it names everything a reader would find, not
only top-level exports. The breadth claim (boot, `/mtime` and `/data.json`
delta recovery, drafts, chrome, navigation, motion, write controls) is
confirmed by the classification below — those concerns are all present and
attributed.

### Premise 2 — "watch.py:727 injects legacy assets and generated globals" — HOLDS, location refined

Line 727 is the `page_shell(...)` **call** that constructs `_PAGE_TEMPLATE`.
The generated globals (`COMMANDS`, `TINTS`, `TINT_DEFAULT`, `RUN_MODES`,
`RUN_ARM_MS`, `DEPLOY_WAIT_MS`) are inline-script **string arguments** at
`:728`–`:737`. The legacy asset concatenation is the remaining arguments at
`:738`–`:741`: `MORPHDOM_JS + COMPONENTS_JS + VIEWS_JS + FAVICON_JS +
SHADER_JS`, then `NATIVE_JS`, then `ROUTER_JS + COMMAND_JS`. `page_shell`
itself (`:569`–`:587`) wraps each trailing script arg in `<script>` tags.
So the citation names the right call; the globals and assets are its
arguments, one and two lines down.

### Premise 3 — "client_dist.py:153 derives build inputs" — HOLDS

Line 153 is `def expected_inputs(root):`. Its body (`:159`–`:175`) derives
inputs from the tree (`asset_order(root)` + `native_sources(root)`), **not
from the manifest** — the docstring at `:153`–`:158` states this is the
false-green the ordering closes.

---

## Group A — React bootstrap & data context (7 functions, 3.2%)

**What moves together:** the module-global `data` store and the lifecycle
that establishes and refreshes it. Under React this becomes a context
provider plus a `useEffect` poll. An implementer can take this group and
land it as one increment because nothing outside it reads or writes `data`
except through `setData` (the single replacement point) and `ensureData`
(the cold-start fetch).

| Function | Line | Responsibility |
|---|---:|---|
| `parseMtime` | 34 | Parses `/mtime` response (`"gen mtime"`) into `{gen, mtime}` — the poll heartbeat's discriminator |
| `setData` | 1371 | **The one place `data` is replaced.** Notifies plugin vocabulary (`window.dwPluginCommands`) and the native registry (`registry.update(data)`). Docstring names the two-fetcher trap (#86) |
| `ensureData` | 1382 | Cold-start fetch: `/mtime` → `/data.json` → `setData`. Lazy-loads `burnStepPref` and `drawMode` |
| `dataJsonUrl` | 2889 | Builds the `/data.json` URL, appending `?burn_step=N` when a step is held |
| `applyDataResponse` | 2901 | Applies a full or delta `/data.json` response; sets `lastDataV` for delta versioning |
| `fetchDataResponse` | 2921 | The `/data.json` network call (full or delta via `dataJsonUrl`) |
| `tick` | 4893 | The 2s poll loop: `/mtime` → generation check (reload on change) → mtime check → `fetchDataResponse` → `setData` → `setLiveContent` |

**Module state that is the context's substrate** (not functions, but named
because they are what the provider replaces):

- `data` (`:9`), `fetchedAt` (`:9`), `lastMtime` (`:9`), `serverGen`
  (`:9`) — the store + its freshness tokens
- `lastDataV` (`:10`) — delta version tracking (#641)
- `dataResponseSequence` (`:11`) — only the newest `/data.json` request may
  commit (#741)
- `holdRerenderUntil` (`:30`) — suppresses tick re-render during morph hold

**Boundary inside `tick`:** the function's poll *scheduling* and its
`/mtime`→`setData` path belong here. Its *body after* `setData` — the
snapshot/restore cascade (`snapshotCardState`, `snapshotAskState`,
`snapshotReviewFrame`, `snapshotBdHover`, `snapshotCards`, `snapshotBars`)
and the `setLiveContent` + `regroupCards`/`regroupBars` calls — is
view-commit work that belongs to Group B's commit seam and to the
surface-runtime remainder (§4). `tick` straddles both groups; an
implementer splitting it would extract the poll+fetch head into the data
provider and leave the commit tail in the navigation layer.

**What lands as one increment:** replace `data` + its six freshness globals
with a React context provider whose `useEffect` runs the poll. The fetcher
functions (`ensureData`, `fetchDataResponse`, `applyDataResponse`,
`dataJsonUrl`, `parseMtime`) become provider internals; `setData` becomes
the provider's dispatch. `tick`'s poll head moves into the provider effect;
its commit tail stays in the navigation layer and reads `data` from context.

---

## Group B — React Router / navigation (13 functions, 6.0%)

**What moves together:** URL→view resolution, the navigation transition,
and the DOM commit seam. Under React Router, `routeOf` becomes `<Routes>`,
`navigate` becomes router navigation, and `buildCurrent`/`commitCurrent`
become route elements that either render a native component or hand the
legacy builder string to the existing morphdom commit.

| Function | Line | Responsibility |
|---|---:|---|
| `routeOf` | 1303 | URL → `{name, param, q, mode}`. The route table (12 routes + dashboard default). #252 mode-in-route, #1013 `/tasks`→`/tasks2` |
| `navigate` | 4773 | Navigation core: invalidates departing surfaces, sets `view`, builds URL, `pushState`, awaits `buildCurrent`, commits via `crossfade` or `commitCurrent`. Stale-nav guard (`view !== navView`, #1058 r2) |
| `buildCurrent` | 1470 | Route → HTML string or native payload. Native routes fetch via `fetchRoutePayload` and return `null`; legacy routes call their `build*` builder |
| `fetchRoutePayload` | 1464 | Route-specific fetch dispatch: `/file`→`fetchFile`, `/chat`→`fetchChat`, `/tasks2`→`fetchTaskTriage`. #1058 single seam |
| `commitCurrent` | 2164 | Commit seam: native route → `registry.mount`; legacy route → `setContent` (morphdom). Unmounts prior roots first |
| `setLiveContent` | 1859 | Tick's view-commit: review route reconciles `#qdock` via morphdom; others delegate to `setContent`; native routes skip |
| `setContent` | 2064 | The morphdom commit: I5 hash-skip, keyed reconciliation (`viewNodeKey`), `reconcileGuard`, then `finishViewCommit` |
| `finishViewCommit` | 2077 | Post-commit re-application: `fitReview`, `paintIndicators`, `ages`, reveal/paint cascade, `restoreRolls`, `restoreAnswerDrafts`, `bindAskDraft`, `resolveTaskRefs`. **The one seam every view commit passes through** |
| `nativeRegistry` | 2146 | Resolves `window.dwNative.registry` — the React-mount bridge |
| `isNativeRoute` | 2150 | Checks whether the registry has the route |
| `unmountNativeRoots` | 2154 | Verifies ownership and unmounts all prior React roots before a new mount |
| `isInternal` | 4855 | Link-interception predicate: same-origin, same-document routes only |
| `applyTitle` | 1298 | Sets `document.title` from `pageTitle(view, data)` |

**Module state:** `view` (`:40`) — `{name, param, q}`, the current route
identity that every commit reads.

**Global event bindings** (the navigation entry points; not function
declarations but part of what moves together):

- The boot IIFE (`:4983`–`:4991`): `routeOf(location)` → `navigate(…,
  {push:false, transition:false})` → `.then(loadRolls)` → `tick()`
- `addEventListener('popstate', …)` (`:4988`): back/forward → `routeOf` →
  `navigate(…, {push:false})`
- The click interceptor (`:4878`–`:4886`): `isInternal(a)` →
  `e.preventDefault()` → `navigate(routeOf(a), {push:true})`

**What lands as one increment:** replace `routeOf` + `navigate` + the
`view` global + the three event bindings with React Router (`<Routes>`,
`useNavigate`, `<Link>`). The boot IIFE becomes `createRoot` + the router
tree. `buildCurrent`'s native branch already works through the registry; its
legacy branch becomes a route element that calls the builder and feeds the
string to the existing morphdom commit (`setContent`). The commit seam
(`commitCurrent`/`setContent`/`finishViewCommit`) is the bridge between the
two worlds and is discussed in §6.

---

## Arithmetic — how much of the 216 each group covers

| Group | Functions | % of 216 |
|---|---:|---:|
| A — bootstrap & data context | 7 | 3.2% |
| B — router & navigation | 13 | 6.0% |
| **Runtime residue scoped by this pass** | **20** | **9.3%** |
| Remainder — not this pass (§4) | 196 | 90.7% |

The 20 functions in Groups A and B are the runtime half. The 196 are
surface-owned runtime that converts per-surface, plus the commit machinery
that is the second-renderer boundary.

---

## What is NOT runtime residue — the boundary against passes 2 and 3

### 4a. Surface-owned runtime (converts with its surface, ~180 functions)

These are runtime concerns owned by individual surfaces, not by the
bootstrap or router. They convert when their surface converts (the
wrapper-export sequence in `react-migration-increments.md`), not in a
runtime pass. Named by cluster with representative functions:

- **Drafts** (~27): `DraftStore` IIFE + 21 closure internals (`:1604`–`:1780`),
  `restoreAnswerDrafts` (`:1813`), `bindAskDraft` (`:1552`),
  `bindChatReplyDraft` (`:1567`), the `dwDraft` façade (`:1789`–`:1801`)
- **Posture** (~21): `armPostureUI`, `commitPosture`, `claimPostPending`,
  `posturePicker`, `paintPostureSelection`, `syncPostureFromData`, etc.
  (`:386`–`:752`, `:1206`)
- **Card state & FLIP motion** (~14): `snapshotCardState`,
  `restoreCardState`, `snapshotCards`, `regroupCards`, `travelCard`,
  `dreamAway`, `ghostNode`, `cardBody`, `revealBody` (`:2199`–`:2599`)
- **Burndown** (~37): step nudge, tooltip, stamp/inspector, hover, bars,
  limit, cycle (`:2812`–`:3554`, `:2877`–`:3056`)
- **Stale deploy** (~14): `armStaleDeploy`, `fireStaleDeploy`,
  `paintStaleDeployUI`, `onStaleActionClick`, etc. (`:4241`–`:4476`)
- **Route transition motion** (~11): `crossfade`, `mistTexture`, `fade`,
  `hash`, `oct`, `fxNode`, `stepFx`, `flipDock` (`:4530`–`:4731`)
- **Chrome** (~4): `renderChrome`, `chromeSnapshot`, `departCrumbs`,
  `crumbsFor` (`:3975`–`:4095`)
- **Theme/tint/draw-mode** (~13): `applyTint`, `tintPicker`,
  `pickDrawMode`, `pickTint`, etc. (`:181`–`:308`)
- **Title** (~6): `pageTitle`, `titleNeed`, `titleLive`, `titleWho`,
  `projectName`, `statusOf` (`:116`–`:150`)
- **Rolls** (~8): `toggleRoll`, `persistRoll`, `applyRoll`, `loadRolls`,
  etc. (`:2679`–`:2770`)
- **File surface** (~5): `copyPathBtn`, `fileModeSwitch`, `paintFileMode`,
  `copyFilePath`, `fileConfirmation` (`:3930`–`:4206`)
- **Ask/subagent-policy/remind/post-desc/folds/text-fit/scroll** (~30):
  `snapshotAskState`, `subagentPolicyPicker`, `sendRemind`, `showPostDesc`,
  `foldDetailsLocal`, `fitText`, `scrollRatio`, etc.

A surface converting to native owns its own runtime — its drafts, its
motion, its write controls move with it. None of these are bootstrap or
router concerns, and none would be touched by a Group A or B increment.

### 4b. Pass 2 (build/deploy/harness) — DELIBERATELY NOT DONE

This document does not scope: the build step (`dev/build_client.py`,
`client_dist.py`), the deploy/serve path (`watch.py` page injection,
`_PAGE_TEMPLATE`, `NATIVE_JS` loading), autoreload, or the styleguide audit.
Those are pass 2 and a sibling lane owns them. The asset-injection citation
(`watch.py:727`, §2) is verified here because it is a *premise*; sizing the
cutover of that injection is pass 2.

### 4c. Pass 3 (final dependency and deletion plan) — DELIBERATELY NOT DONE

This document does not scope: the final deletion of legacy builders, the
dependency graph between wrapper exports and native routes, or the order in
which legacy surfaces retire. Those are pass 3.

---

## The second-renderer boundary — flag, do not schedule

`DREAMWORK.md` refuses a second render authority; `dreamhub-design.md`
records the form. This split must not propose reimplementing markup.

The `build*` view builders (`buildDashboard`, `buildQuestions`,
`buildReview`, etc.) live in **`client/views.js`**, not `router.js`.
`buildCurrent` (`:1470`) dispatches to them and returns an HTML string.
`setContent` (`:2064`) commits that string via **morphdom** — the existing
renderer. This is not a second renderer; it is the first and only one.

The sanctioned migration path is the native registry (`window.dwNative.registry`),
which is already live for `/research` and `/goals`. When a route is native,
`commitCurrent` (`:2164`) calls `registry.mount` and bypasses morphdom
entirely. So the commit seam is **half-migrated**: native routes use React,
legacy routes use morphdom, and the two never render the same surface.

**What to flag, not schedule:** `setContent` + `finishViewCommit` (`:2064`,
`:2077`) are the morphdom commit and its post-commit re-application cascade.
They are Group B because they are the navigation commit seam, but they are
also the thing that **shrinks as surfaces convert** — each native route
bypasses them. They must not be reimplemented as a parallel renderer; they
are retired surface-by-surface as the legacy builders are deleted (pass 3).
The `finishViewCommit` cascade (`restoreRolls`, `restoreAnswerDrafts`,
`bindAskDraft`, `paintStaleDeployUI`, `syncPostureFromData`, etc.) is
surface-runtime re-application that belongs to §4a and drops out per-surface
as each surface goes native.

---

## What I could not attribute — honest remainder

Of the 216 functions, I attributed 20 to the two deliverable groups and
classified ~180 into surface-runtime clusters (§4a). The remaining ~16 are
functions whose cluster assignment I am confident about but whose exact
counting I did not individually audit line-by-line — they are distributed
across the posture, burndown, and motion clusters and are named by
representative example rather than exhaustive enumeration. A
surface-conversion pass will re-enumerate them per surface; this pass does
not need to.

Three functions with duplicated names (`finish`, `clear`, `remainingMs`,
`setCount`, `smooth`) appear in multiple clusters — each instance belongs to
its own cluster (e.g., `finish` at `:1098` is post-description, `finish` at
`:3179` is burndown-tip, `finish` at `:3418` is burndown-inspector, `finish`
at `:4655` is crossfade). None are in Groups A or B.

---

## How this document could look finished and still be false

1. **Groups borrowed from React's vocabulary.** Ruled out: every group is
   backed by functions I opened and read in `client/router.js` at the cited
   lines. `routeOf` is a real switch at `:1303`; `setData` is a real
   function at `:1371` with a docstring naming the two-fetcher trap; the
   native registry is real and already mounts `/research` and `/goals`.
2. **The count repeated, not used.** Ruled out: §3 gives the arithmetic.
   Group A is 7/216 (3.2%), Group B is 13/216 (6.0%), remainder is 196/216
   (90.7%). The reader can tell this pass scoped 9.3%, not 90%.
3. **Precision without currency.** Ruled out: every line number was
   re-resolved against `fb644018` on 2026-08-03. The three premises were
   re-verified (§2); premise 2's citation was refined from "727" to the
   precise call-vs-argument distinction.

**One I could not fully close:** the ~16-function counting remainder (§7).
I am confident no Group-A or Group-B function was missed (the boot IIFE,
the event handlers, and all 20 named functions were individually located),
but I did not line-audit every surface-runtime function to guarantee the
cluster counts sum to exactly 196. A discrepancy would be in the §4a
totals, not in the deliverable groups.
