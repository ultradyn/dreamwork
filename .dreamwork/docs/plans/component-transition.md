# #630 — the transition to a component-based React web UI (plan)

Lane: `lane-630components` (**plan only — no production code**; `watch.py` and
`client/**` are held/in flux, and the first thing this transition needs is a
sequence with no flag day). Authority: his ruling of 2026-07-31 17:03, receipt
`dc9200a0-4ebf-5d3b-afab-71257155bef9` — `rec` on all three of `#591`'s
sub-decisions (`.dreamwork/docs/plans/g2-question-draft.md`, analysis
`.dreamwork/review/505-g2-render-authority.html`), plus the priority sentence:
*"prioritize replacing old inline-html in watch.py with new UI components at
the earliest suitable time."* The ruling's note also asks that references to
the earlier "no components" framing be updated to name the new ruling —
§Bookkeeping lists them.

The three settled constraints (his, not this plan's to reopen):

- **Q1 — one render authority *per surface*; a derived surface is not a second
  authority.** Two *maintained* renderers of the same rows stay refused. A
  hand-maintained component twin of an existing surface is refused, however
  incremental.
  **RELAXED 2026-07-31 19:09 (`#614`) — read this before starting, because it
  loosens the constraint this plan was shaped around.** He relaxed *"one
  renderer, and it is the Python one"* outright (*"we should relax this now
  since we're changing over to react based webui"*) and scoped the
  second-truth rule to **on-disk master state** (canonical: **One fact, one
  home on disk**, `DREAMWORK.md` Philosophy). So a hand-maintained twin is no
  longer *refused* — it is merely expensive. **This plan's shape does not
  change**, and that is a deliberate call rather than an oversight: derived
  wrappers plus deletion-on-flip were chosen because they cost the least, not
  because a rule required them, so the cheapest path is still the cheapest
  path. What changes is that a lane hitting an awkward surface may now *argue*
  for a hand-written component instead of being blocked by doctrine.
- **Q2 — claude-design compatibility at component level, staged**: tokens+CSS
  first, delegating wrappers second.
- **Q3 — React.**

Also binding: the **server stays stdlib-Python-only** (ruled 2026-07-30, commit
`0f97df03`, recorded at `watch-design.md:41-51` — the *client* build is freed,
the server imports nothing outside the stdlib and no install stands between a
checkout and a running dashboard).

Every claim below is tagged **VERIFIED** (measured or read in source, cited by
file:line in this worktree) or **INFERRED** (judgement / estimate).

---

## 1. What exists now — the honest starting line

### 1a. "Old inline-html in watch.py" names two different things today

**Sense A — HTML literally inline in `watch.py`: ~8 lines, and that is all.**
VERIFIED by tag-sweep (`grep` for every common opening tag across the file).
The only emitters:

- `page_shell` (`watch.py:549-560`) — the one document envelope
  (`<!doctype html>…<head>…<body>`, one f-string `<title>`), plus the
  `<style>` wrap at `watch.py:532`.
- `file_highlight_html` (`watch.py:709-736`) — one `<pre><code
  class="language-…">` wrapper at `watch.py:730`.

Everything else matching a tag in `watch.py` is a comment or docstring.
**These ~8 lines are not the target of the transition.** The envelope is the
server's serving concern (a component cannot serve itself), and the highlight
wrapper feeds a scanner with its own round-trip check. They stay Python.

**Sense B — the string-builder idiom, formerly inline, now in `client/`:
~6,300 lines, and this is what his sentence names.** `#397` (implemented
2026-07-31, `watch-client-extraction.md:6-11`) moved the eight inline
constants (6,719 lines as measured at `watch-client-extraction.md:105-118`)
into real files, proven byte-identical (576,217 bytes, sha256 `08d4e0bf…`).
The *idiom* — functions concatenating HTML strings, committed to the DOM at
one seam — moved with them, unchanged. Measured today (VERIFIED, `wc -l` +
tag-literal count per file):

| file | lines | HTML-emitting lines (approx) | role |
|---|---|---|---|
| `client/views.js` | 1,912 | ~170 | nine route builders (`buildChat:761`, `buildDashboard:878`, `buildQuestions:950`, `buildAnswers:998`, `buildFile:1117`, `buildReview:1222`, `buildResearch:1293`, `buildReviews:1315`, `buildQuestion:1342`) + shared rows (`artifactRow:1250`) |
| `client/components.js` | 1,085 | ~58 | the component vocabulary: `qaCard:820` ("THE question component", contract at `:633`), `expand:182`, `label:115`, `pipBtn:124`, `followThread:493`, `qaCompose:585`, the md pipeline — plus non-render utilities (IndexedDB, `postJSON`, `writeVerdict`) |
| `client/router.js` | 4,365 | ~86 | routing, the tick, the morph seam (`setContent:1656` → `morphdom:1662`; dock `:1473`), transitions machinery, chrome |
| `client/command.js` | 839 | ~19 | composer |
| `client/app_body.html` | 109 | all | static shell |
| `client/style.css` | 1,927 | — | tokens + all CSS |
| `client/favicon.js`, `client/shader.js` | 148 + 526 | 0 | no HTML |

So the actionable reading of his sentence, stated plainly: **the replacement
target is the string-builder HTML in `client/*.js` (Sense B), surface by
surface; the residual Sense-A lines in `watch.py` are out of scope** (they are
an envelope, not a UI surface). Both senses measured so nobody re-litigates
what the goal names.

### 1b. The surfaces and the incumbent render path

Nine routes (`client/router.js:991-1030`): dashboard, `/questions`,
`/answers`, `/file`, `/review`, `/question`, `/research`, `/reviews`,
`/chat[/<id>]`. All render as HTML strings through one seam: `setContent`
(`router.js:1656`) reconciles `#view` via vendored morphdom
(`vendor/morphdom.min.js`, `#505` I5 — landed, live code) with a content-hash
skip; the review dock reconciles through the same idiom (`router.js:1473`).
`qaCard` renders on four surfaces (dashboard `views.js:245,248`; /questions
`views.js:959-965`; the review dock `views.js:1229`; /question focus
`views.js:1348,1356`) — the shared-card fact that shapes the endgame (§4).

### 1c. Assembly and shipping, as they constrain the build

- `watch.py` reads the eight assets at import (`_CLIENT_ASSETS:478`,
  `_read_client:490` — refuses empty files, byte-faithful), assembles one
  PAGE (`_PAGE_TEMPLATE:603`, preamble of `json.dumps` constants + morphdom +
  the JS in a fixed order), serves it as a single HTML response.
- `just deploy` ships **committed state only** (`justfile:398-403`) via
  `dev/deploy_state.py`: `DATA_SIBLINGS` (`watch.py:580`) is **AST-parsed as a
  tuple of plain string literals** (`deploy_state.py:298-310`) and
  `ship_siblings` (`:379`) stages every path. It already carries
  `vendor/morphdom.min.js` — the house already ships a vendored *built*
  artifact.
- **Node is already a dev-time dependency** (guards run `node
  dev/capture/*.mjs` + Playwright, `justfile:303,334`). It is not, and must
  not become, a serve-time dependency.
- `test_client_assets.py` is the standing seam-guard (loader fidelity,
  page containment, DATA_SIBLINGS completeness, autoreload watch set) — the
  verification model §5 extends.

---

## 2. The target shape

End state: every surface has exactly one authority, of one of three kinds.

1. **Builder-owned** (legacy, shrinking): the string builder is the sole
   authority; renders through the landed morph seam. No component twin.
2. **Component-native**: a React component tree is the sole authority (the
   session view first — born native, never a builder; converted surfaces
   after). No builder twin, ever.
3. **Derived wrappers** (the claude-design export, Q2 stage 2): React
   components **compiled from the same `client/*.js` files watch.py serves** —
   consumed, never copied, no markup restated.

### 2a. How a wrapper is *derived*, concretely

The builders are not ES modules — they are top-level `const`s in one shared
script scope, concatenated by `watch.py` in a fixed order (`watch.py:603-617`).
The build reproduces exactly that: its entry is **generated** as

```
concat( client/<asset> for asset in watch.py's _CLIENT_ASSETS order )
  + wrapper-exports.js        # references builder names lexically, same scope
→ esbuild → one IIFE assigning exports to window.<globalName>
```

with the asset list and order **read out of `watch.py` by AST** at build time
(the same trick `deploy_state.py:298-310` uses on `DATA_SIBLINGS`) — so the
load order has one truth and the build cannot quietly diverge from the page's.
A wrapper is then (the ratified artifact's shape, current line numbers):

```js
export const QaCard = ({ q, k, ctx }) =>
  ambient(ctx, () => html(qaCard(q, k)));   // qaCard: client/components.js:820
```

`html()` mounts the builder's string (`dangerouslySetInnerHTML` on a typed
shell); `ambient()` supplies the closed set of page globals the builders read:
`data` (`components.js:202,235`), `view` (`components.js:728,747`), `rmr`
(`components.js:547`), and a stubbed `submitCard` (`components.js:602` — in
the design tool a preview's click has nothing to submit to). VERIFIED closed
set by reading `components.js` end to end; the ratified artifact enumerates
the same four. `client/style.css` ships unchanged as the package stylesheet.
Starting export set: `QaCard`, `Expand`, `Label`, `PipBtn`, `FollowThread`,
`QaCompose`, `ArtifactRow`, and the view builders as preview compositions.

### 2b. What mechanically prevents divergence — tiered, honestly

**Wrappers (kind 3): divergence has no place to live at the markup level, and
staleness — the real channel — is made loud, not left to care.**

- *No restatement:* the wrapper's render **calls** the builder; there is no
  second statement of any markup, so there is nothing to drift. Enforced
  mechanically, not by review: the wrapper-exports file is the only
  hand-written build input, and a born-red check refuses any HTML tag literal
  in it (the check first asserts its detector finds tag literals in
  `components.js`, so it cannot pass vacuously — §5).
- *No copy:* the build reads `client/*.js` in place; there is no second
  checkout of the builders. The generated-entry + AST-order design above is
  what makes "consumes, never copies" a property of the build, not a habit.
- *Staleness is the residual channel* — a bundle compiled from yesterday's
  builders. Mechanism: `client/dist/manifest.json` records sha256 of every
  input and output; lint/test recomputes and goes **ERROR** on mismatch
  ("dist is stale — run `just build-client`"); `serving_report` surfaces the
  same comparison server-side (stdlib `hashlib`, no node needed to *detect*).
  Stale can then never be silent; it cannot be made *impossible* without a
  serve-time build, which the no-node requirement refuses. Stated plainly:
  **for wrappers the guarantee is "divergence impossible, staleness
  impossible-to-miss."**

**Conversions (kind 2): the mechanism is deletion, not discipline — and
during authorship, identity is *proven*, not guaranteed.** This is the
finding the task demanded be said plainly: while a native rewrite of an
existing surface is being written, a twin exists *in the author's working
tree* and nothing makes divergence impossible there — it is only *detected*,
by the oracle check (§5: the builder's recorded output over a fixture corpus
is the bar the native render must meet). What makes the *repo* never hold two
truths is the **flip-commit rule**: the native component lands and the
builder for that surface is **deleted in the same commit**. After the flip
the builder no longer exists, so there is nothing to diverge from; before the
flip nothing native is reachable. The overlap window in history is zero
commits. A revert restores the builder whole.

**Shared primitives: delegation direction, guarded.** A native surface that
needs a primitive the builders still own (`artifactRow`, `agePair`, `label`,
`expand`…) consumes the **wrapper**, never re-derives it — one `agePair`,
whoever is asking. Guard: a closed-set check that each primitive name has
exactly one defining site (grep-able; born-red by adding a decoy second
definition in a fixture). When the *last* builder consumer of a primitive
goes native, the primitive itself flips native in that same commit and the
delegation direction inverts — same flip rule, one level down.

**The authority map is written down, and checked.** A table (watch-design.md,
at implementation time) lists each route → its authority kind. A guard
asserts the map matches reality: every route resolves in exactly one of the
two registries (string-builder table `router.js:1100-1112` / the component
registry §4-P2), never both, never neither.

### 2c. What does NOT change

The morph seam, the transitions machinery, and every builder surface render
exactly as today until their own flip commit — `#505`'s landed I5 is the
incumbent for kind-1 surfaces throughout (`render-architecture.md` §Status).
The transition never runs two maintained renderers of one surface at any
phase; that is Q1 holding at every intermediate point, not only at the ends.

---

## 3. The build step

- **What runs it:** `just build-client` → `node` + esbuild (vendored or
  npm-pinned under `dev/`; INFERRED tool choice — esbuild is what the
  claude-design ingestion itself uses, per the verified design-sync spec).
  Dev-time only; the same dependency class as the guards (`justfile:303`).
- **What it emits, where:** `client/dist/` —
  - `native.js`: the on-page runtime bundle (React + ReactDOM + native
    components, one IIFE). React rides *inside* the bundle — no CDN, no
    separate vendor fetch; the page stays offline-clean and single-response.
    INFERRED size ~140-180 KB minified on top of today's ~576 KB page —
    budget-checked in §5, measured before P2 lands.
  - `ds/` (Q2 stage 2): the claude-design package — IIFE assigning exports to
    `window.<globalName>`, per-component `.d.ts` + `.prompt.md`, plus
    `styles.css` (= `client/style.css`, byte-identical). **Not served by
    `watch.py`** — it ships to the design tool.
  - `manifest.json`: sha256 of every input and output + tool versions (§2b).
- **Committed, not generated at serve time.** `client/dist/*` is checked in —
  the `vendor/morphdom.min.js` precedent. Two reasons this is forced, not
  taste: `just deploy` ships committed state only (`justfile:398-403`), and
  the dashboard must come up from a plain checkout with no node.
- **How `watch.py` serves it:** `native.js` joins the page assembly the way
  morphdom does (read at import beside `_CLIENT_SRC`, refused-if-empty via
  the `_read_client` discipline, concatenated into PAGE) — one HTML response,
  as today. Its path joins `DATA_SIBLINGS` as a **plain string literal**
  (the AST contract, `deploy_state.py:298-310`), so `just deploy` ships it
  with zero recipe change; `test_client_assets.py:130-163`'s
  DATA_SIBLINGS-completeness check extends to it.
- **A machine with no node:** serves everything (dist is committed); can edit
  Python, CSS, and builder JS freely; **cannot rebuild dist** — and the
  manifest check tells it exactly that, as a red with the fix named, the
  moment a dist *input* is edited without a rebuild. Serving never requires
  node; only changing component code does. INFERRED policy choice: red at
  lint (commit-time catch) + WARN in `serving_report`, never a serve refusal
  — a stale ds-bundle must not dark the live dashboard.

---

## 4. The phased sequence

Every phase lands alone, reverts alone, and leaves the dashboard fully
working. No code is authorised by this doc.

**P1 — the build step, emitting nothing the page uses.** `just build-client`,
the generated-entry + AST-order machinery, `client/dist/` committed (at this
phase: the ds skeleton with zero wrapper exports, or `native.js` as an empty
shell — either way *nothing referenced by PAGE*), `manifest.json` + the
staleness check. The dashboard is **byte-identical** (checked, §5). This is
the smallest first phase that is real: it is the shared foundation of both
tracks, it touches no serving path, and revert = delete a recipe, a dev
directory, and dist. *Why it is safe to be wrong about:* if the build design
is wrong (order, scope, tool), nothing downstream exists yet and no user ever
saw it.

**P2 — React runtime + the component-registry seam, mounting nothing.**
`native.js` gains React; the router gains the second registry: a route may
resolve to a component mount instead of a builder string, with
mount/unmount wired into navigation (the dissolve) and the tick (data updates
flow to mounted components through the same `setData` — one data authority).
Behind a dev flag, a probe route proves mount/unmount/tick coexistence with
morphdom (§5's coexistence guard is born here). User-visible change: none.
Revert: drop the registry branch; builders never noticed.

**P3 — the first conversion: `/research` (listing) flips native.** The first
real instance of his sentence — a string-builder surface replaced by a
component, flip-commit rule applied (`buildResearch` deleted in the same
commit, `views.js:1293-1307`). The native surface consumes `ArtifactRow` via
the **wrapper** (the row is still builder-owned — `/reviews` and the
dashboard render it, `views.js:929,1319`), which makes P3 exercise the whole
architecture at minimum size: native shell + delegated primitive + oracle
check + registry routing + tick updates + ages-sweep interplay.

*Why `/research` is the safest surface to be wrong about:* smallest builder
(~15 lines listing + 5-line iframe branch); **no gesture families of its
own** (the FLIP regroup on review rows is dashboard-gated,
`router.js:4305-4306` — the /research page has none; no composer, no qaCard,
no draft state); lowest blast radius (a rarely-visited listing, nowhere near
his answer path — a broken /research is an inconvenience, a broken dashboard
or /questions is the product down); and still real enough that passing it
proves the machinery (live data, empty states, ages, dock links, iframe
sub-mode). Runner-up considered: `/reviews` — same shape but it feeds his
review workflow daily; it is P5's first item instead.

**P4 — the session view, born native (#613).** The registry from P2 is the
mount his *"only be available via that"* directive lands in; the component is
`#613`'s `SessionLog` with its narrow in/out contract. **Its three open
design calls stay #613's** — this plan only guarantees the component system
exists by then, and that "1 simple component now, swap later" has a home. P3
and P4 commute: whichever design is ready first goes first; neither depends
on the other.

**P5 — the claude-design track (Q2, staged), parallel after P1.** Stage 1:
tokens + `styles.css` + `conventions.md` (nearly free — the file is real
today). Stage 2: wrapper exports for the starting set (§2a), `.d.ts` +
`.prompt.md` + fixture props. Cheapest-early-signal rule (§6-R5): run ONE
wrapper (`QaCard`) through the design tool end-to-end before authoring the
rest.

**P6…Pn — remaining surfaces, by rising risk:** `/reviews` → `/answers` →
`/chat` (+`/chat/<id>`) → `/file` → then the **qaCard family endgame**:
`/questions`, `/question`, the review dock, and the dashboard. These four
share `qaCard`, so per-surface conversion would fork it — the exact I3 error
the ruling priced. Two shapes avoid the fork, both keeping one truth:

- **(a) coordinated family flip** (default): the four surfaces + `qaCard` +
  its satellite primitives convert in one phase — a mini flag day, scoped to
  the card family, taken last when the machinery is most proven.
- **(b) card-as-island first**: `qaCard` alone flips native and mounts as a
  component island inside the four builder surfaces (morphdom taught to skip
  component-owned subtrees — a standard hook), builders keep their shells;
  the surfaces then convert one at a time with the card already native.
  Smaller steps — but a surface whose page is builder-owned while its card
  subtree is component-owned needs Q1's *per-surface* reading extended to
  *per-subtree partition* (a natural extension — partition is not
  duplication, nothing renders twice — but **unratified**).

Not decided here and not asked now: the endgame is several phases away, and
the choice deserves the evidence P3-P5 will generate. If (b) still looks
superior when the phase is planned, the one-line reading extension goes to
him then, through the coordinator — flagged so it cannot arrive by accident.

**Bookkeeping rides each phase** (single-source rule, as `#614` does it):
watch-design.md's authority map + the client bullet (`watch-design.md:60-63`)
update in the same commit as P2; `file-formats.md` gains the manifest shape
with P1; the styleguide audit and `--autoreload` watch set gain dist inputs
with P1 (`test_client_assets.py:219` pattern).

---

## 5. The verification story

The model is `#397`'s byte-equality capture plus its standing seam-guards
(`test_client_assets.py`), with its two traps designed against by rule:
**every comparison asserts its own preconditions, and every check proves its
detector can detect** (a comparison that would pass on two empty sides must
first show both sides non-trivial). Every phase ships a born-red check —
red-proved against the defect it exists to catch, then green.

- **P1:** (i) PAGE unchanged: capture the served page before/after, assert
  byte-equal AND `len > 100_000` (the `test_client_assets.py:113` guard
  shape — non-vacuous by construction). (ii) Manifest honesty: build, then
  touch one input byte → the staleness check must go red (the red-proof is
  part of the test, not a ceremony). (iii) ds `styles.css` byte-equals
  `client/style.css`, precondition: contains a known token (e.g. `--bg`).
- **P2:** (i) coexistence guard (dev/capture idiom): mount the probe route,
  drive ticks, navigate away and back — assert builder surfaces' DOM
  untouched by mount/unmount and the component's state survives a tick;
  precondition: the probe actually mounted (sentinel node present).
  (ii) page-weight budget: assert PAGE size below a measured-then-set bound,
  so React's cost is a number someone chose, not a drift.
- **Wrapper equality (P5, permanent — the check that beats one-time byte
  identity):** for each exported wrapper, over fixture props: parse the
  builder's string into a detached DOM, serialize; mount the wrapper,
  serialize its root's innerHTML; assert **strict equality of the two
  serializations**. Both sides pass through the same parser+serializer, so
  entity/quoting normalization cannot false-red — that procedural detail is
  the difference between a check and a flake. Preconditions: builder output
  non-empty, contains a surface sentinel (`class="qa"` for QaCard), length
  above a floor. Runs in guards forever — every future builder edit is
  re-proven against its wrapper, which is what makes "derived, not copied"
  a checked property rather than a founding story.
- **Wrapper purity (P1/P5):** no HTML tag literal in the wrapper-exports
  file; the detector first asserts it finds ≥ 1 tag literal in
  `components.js`, so it cannot pass by being broken.
- **Flip commits (P3, P6…):** the **oracle protocol**. Before the flip:
  record the builder's output over a fixture corpus (real `/data.json`
  shapes: populated, empty-state, edge entries); assert the corpus is
  non-empty and each snapshot carries surface sentinels — the vacuity trap
  closed at the source. The native render must serialize-equal each oracle
  (same normalization procedure as wrappers). Red-proof: perturb one
  character of the native output → red. In the flip commit the builder is
  deleted; the oracles stay in the test tree as the record until the phase
  settles, then retire with a note. Plus: the surface's existing capture
  guards (dissolve, ages, dock links) run unchanged — they assert behavior,
  not implementation, and must stay green across the flip.
- **Primitive singleness (P3 on):** the closed-set one-defining-site check
  (§2b), red-proved with a planted decoy.
- **Authority map (P2 on):** each route in exactly one registry (§2b).

---

## 6. What could go wrong — ranked, with the cheapest early signal

1. **React and morphdom fight over DOM** (the coexistence risk — wrong here
   and the whole shape wobbles). *Earliest signal:* the P2 probe-route guard,
   before any real surface exists; cheapest probe is a scratch page with one
   component root inside `#view` under forced ticks — hours, not a phase.
2. **Stale dist served silently** (the wrappers' one divergence channel).
   *Signal:* the P1 manifest red-proof — it is the first check written, and
   `serving_report`'s WARN makes a stale live deploy visible on the dashboard
   itself.
3. **A flip regresses a gesture** (transitions.md families are the product's
   feel). *Signal:* the surface's existing capture guards across the flip
   commit — which is why the ladder starts at the surface with **zero**
   families (`/research`) and ends at the dashboard.
4. **The qaCard endgame becomes a real flag day** (I3's error, in miniature).
   *Signal:* before planning that phase, count the gesture families keyed on
   `.qa` nodes (submit morph, FLIP regroup, travelCard, wisp) — if the count
   makes (a) too big to revert, shape (b) + the reading extension goes to him
   *then*, with the count as the evidence.
5. **claude-design ingestion rejects or degrades wrapper granularity** (the
   artifact's one INFERRED cell: a string-mounting wrapper satisfies the tool
   *mechanically* — whether it satisfies it *well* is unproven). *Signal:*
   one wrapper end-to-end through design-sync before the rest are authored
   (P5's rule) — a day's spike protects the whole stage-2 budget.
6. **The ambient contract grows unnoticed** (a builder starts reading a new
   global; the shim silently lacks it). *Signal:* a closed-set check —
   enumerate globals the builders reference vs the shim's supply — red the
   commit the drift is introduced, not the day a preview breaks.
7. **Page weight creep** (React inlined into a single-response page).
   *Signal:* the P2 budget assert; measured before, chosen, then enforced.
8. **No-node friction bites a lane** (edits a dist input, can't rebuild).
   *Signal:* the lint ERROR names the fix and the machines that have node
   (build boxes); if it recurs, that is dogfood evidence for a committed
   pre-push hook or CI rebuild — logged then, not built now.

---

## Seams with the two live plans (touched, not decided)

- **#613 (session-log view):** P2's registry + P4's mount are where *"should
  use new component system and only be available via that"* lands; this plan
  supplies the system and guarantees no `views.js` twin of that surface ever
  exists (its authority is kind-2 from birth). `SessionLog`'s three open
  design calls, its data model, API, and inotify story remain `#613`'s.
- **#614 (SSE/delta transport):** orthogonal by both plans' construction.
  Components receive data through the same `setData` seam the tick feeds
  today; when `#614` lands, builder surfaces re-render through the morph seam
  and native surfaces apply the same document (later: its `changed`-keys hint
  narrows component re-renders — an optimization, not a dependency). Nothing
  here presumes SSE vs WS; nothing there presumes a renderer.

## Bookkeeping owed by the ruling (his note, verbatim: update "no components"
references to the new ruling)

Stale statements to update at implementation time (not this lane's files;
listed for the coordinator / the landing commits): `DREAMWORK.md:54-57`
("still unruled on" → ruled, receipt `dc9200a0…`); `watch-design.md:52-58`
(the second-renderer bullet gains the per-surface reading);
`render-architecture.md:22-27` §Status (+ its I3 note — the G2 half is now
scoped per-surface); `ws-delta-transport.md:151,348-350` ("pending his
ratification" → ratified); `session-log-view.md:339-367` §8 (the
G2-open framing → ruled; its Q1 ask about the "only via" reading may fold).
The review artifact stays as the record of the analysis as made.

## No ask

Nothing here needs him now. The ruling fixed the frame; the remaining calls
either have one clearly superior answer under his standing rules (committed
dist, flip-commit rule, `/research` first) or are implementation-time
(esbuild vs alternative, inline-vs-separate asset). The one future candidate
— the endgame island reading (§4) — is deliberately deferred to when its
evidence exists, and flagged so it cannot be decided by accident.

## VERIFIED vs INFERRED (roll-up)

**VERIFIED:** every file:line cited above, including: watch.py's total inline
HTML (~8 lines, two sites); the eight-asset load path and PAGE assembly; the
nine routes and their builders; qaCard's four surfaces; the morph seam; the
ambient-global closed set (components.js read end to end); DATA_SIBLINGS'
AST-literal contract and morphdom precedent; deploy's committed-only rule;
node as an existing dev dependency; `/research`'s lack of gesture machinery
(the review-FLIP is dashboard-gated); the ruling texts (receipt shown via
`journal_consume.py`, artifact and question-draft read).
**INFERRED:** the ~170/58/86/19 HTML-emitting line counts (pattern-count
approximation, method stated); esbuild as the tool; React bundle size range;
the lint-red-not-serve-refusal staleness policy; the phase ordering beyond
P1-P3 (P3/P4 commute is argued, not forced); that wrapper granularity
satisfies claude-design *well* (the artifact's own flagged inference — §6-R5
is its test).

---

--- SUMMARY ---

- **What his sentence names, measured:** `watch.py` holds only ~8 lines of
  literal inline HTML (the document envelope + one highlight wrapper — out of
  scope); the real target is the string-builder idiom `#397` moved into
  `client/` (~6,300 lines across nine route builders and the shared
  component vocabulary, `qaCard` on four surfaces).
- **Target shape per the ruling:** three authority kinds — builder-owned
  (legacy, shrinking, morph seam unchanged), component-native (session view
  born there; converted surfaces join), and claude-design wrappers **derived**
  from the very files watch.py serves (generated build entry concatenates
  them in watch.py's own AST-read order; wrapper render *calls* the builder,
  restating nothing).
- **Divergence mechanisms, tiered honestly:** wrappers — impossible at
  markup level (no restatement, enforced by a tag-literal check) with
  staleness made loud (sha256 manifest, lint ERROR + serving_report WARN);
  conversions — **deletion is the mechanism**: native lands and the builder
  dies in the same commit (zero-commit overlap; during authorship identity is
  *proven* against oracle snapshots, not guaranteed — stated plainly);
  primitives — delegation direction + one-defining-site guard.
- **Build:** `just build-client` (node/esbuild, dev-time only — guards
  already need node); emits committed `client/dist/` (native.js bundles React
  in, ds package for the design tool, manifest); watch.py inlines native.js
  like morphdom; DATA_SIBLINGS literals carry it through `just deploy`
  untouched; a no-node machine serves everything and gets a named red if it
  edits dist inputs.
- **Sequence:** P1 build step (page byte-identical) → P2 runtime + component
  registry (mounts nothing) → **P3 first conversion: `/research`** (smallest
  builder, zero gesture families, lowest blast radius, still exercises
  registry/tick/delegation/oracle) → P4 session view (#613's design calls
  stay theirs) → P5 claude-design tokens-then-wrappers (parallel after P1) →
  P6… risk ladder ending in the qaCard family endgame (coordinated flip
  default; card-as-island alternative priced — needs a one-line extension of
  Q1's reading, deferred with a flag, not decided by accident).
- **Verification:** every phase born-red with red-proofs; the #397 traps
  closed by rule (preconditions asserted, detectors proven detecting);
  wrapper serialize-equality runs in guards *forever* (beats the one-time
  byte capture); flip commits use an oracle-snapshot protocol with sentinel
  preconditions; coexistence, budget, purity, ambient-set, and authority-map
  guards named.
- **Top risks + early signals:** React/morphdom coexistence (P2 probe guard,
  hours), stale dist (P1 manifest red-proof), gesture regression (existing
  capture guards per flip; safest-first ladder), qaCard endgame flag day
  (count gesture families before planning it), claude-design granularity
  (one wrapper end-to-end before authoring the rest).
- **Seams:** #613 gets the mount and the no-twin guarantee, keeps its design
  calls; #614 is orthogonal — components ride the same setData/delta seam.
  Bookkeeping list for the ruling's "update no-components references" note
  included. **No ask for him in this plan.**
