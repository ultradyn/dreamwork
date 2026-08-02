# #1083 — Scope the native Markdown boundary needed to remove `/goals`' `mdB` delegate

**Scope:** a call-graph + contract measurement, and a costed recommendation.
**Not:** code. This document changes no source. It says what the increments
*are*, not that they will work (`#994`).
**Measured at:** `fb644018` (worktree HEAD == local `master` at start).
**Citation drift noted (`#967`):** the brief cites `mdB` at
`client/components.js:742`; it is now at **line 779**. The substance holds
(defined there, short entrypoint); only the line moved as `client/` shifted.
The delegation at `dev/build/src/goals.js:5` is VERIFIED at the cited line.

---

## 0. Premise check — what was claimed vs. what the tree holds

| Brief claim | Citation | Status |
|---|---|---|
| `/goals` delegates Markdown rendering to legacy `mdB` | `goals.js:5` | **VERIFIED** — `fromBuilder('mdB', …)` at `:5`; the call is `mdB(props.text \|\| '')` at `:6` |
| `mdB` lives at `client/components.js:742` | `:742` | **DRIFTED** — now at **`client/components.js:779`**. Same definition, same entrypoint role. |
| `mdB` is a short entrypoint into a larger helper graph; its 8 visible lines do not honestly remove the dependency | `:779` | **VERIFIED** — see §1; the transitive graph is 17 functions + 2 regex constants + 1 external global. |

---

## 1. The actual call graph under `mdB` (transitive)

**How traversed:** by hand, reading `client/components.js` end to end from
the `mdB` definition (`:779`), following every callee into its definition,
then repeating until only leaves remained. Cross-checked with
`grep -n` for each symbol to fix exact line numbers. The graph below is the
*full transitive closure* of what `mdB` reaches; I stopped when every callee
was a leaf (`esc`, `document.createElement`, the global `data`, or a regex).

`/goals` calls `mdB(props.text || '')` with **one argument** (`goals.js:6`),
so `filePath` is `undefined` and `base` resolves to `null` inside `mdB`. The
graph below is therefore the *one-arg* path — the path actually exercised.

```
mdB (779)                         ← entry; wraps in <div class="md">
├─ mdInlineAt (772)               ← builds the inline closure; base=null here
│  ├─ mdSpans (766)               ← **bold**, *em*, `code` span replacements
│  ├─ linkify (286)               ← backticked-path → /file links
│  │  └─ mdFileUnit (254)         ← the .mdfile link idiom + pip button
│  │     ├─ tailCut (248)         ← label wrap point
│  │     └─ pipBtn (212)
│  │        └─ actionButton (140) ← leaf (the page's button chrome)
│  │  · reads global data.linkable_paths  (data declared in router.js:9)
│  ├─ linkifyMd (334)             ← [text](target) markdown links
│  │  ├─ resolveMdTarget (318)
│  │  │  └─ mdNormJoin (307)
│  │  │  · reads global data.linkable_paths
│  │  └─ mdFileUnit (254)         ← (shared with linkify)
│  └─ esc (3)                     ← leaf: textContent→innerHTML escape
└─ mdRender (498)                 ← block-level dispatcher
   └─ mdBlocks (431)              ← line parser → block list
      ├─ mdLooksLikeRow (427)
      ├─ mdIsDelimRow (421)
      ├─ mdSplitRow (415)
      ├─ MD_BULLET (410)          ← regex constant
      └─ MD_QUOTE  (411)          ← regex constant
   · mdRender calls the inline closure (mdInlineAt) per block
```

**Count:** 17 functions + 2 regex constants, plus a read of the **external
global `data`** (`data.linkable_paths`, declared in `client/router.js:9` and
populated by `setData` at `router.js:1372`). That global coupling is the one
part of the graph that does not live inside `components.js` and is the reason
a naive copy of `mdB`'s eight lines would not render a single link.

**Deliberately not in this graph** (siblings, reached by other entrypoints,
not by `mdB`):
- `mdBReview` (`:787`) / `mdInlineReview` (`:775`) / `linkifyReview` (`:368`)
  / `revDock` (`:365`) — the review-dock linkifier family. `mdB` does **not**
  reach these; `goals.js` does not call `mdBReview`. Naming them here so the
  boundary is drawn around what `/goals` uses, not everything that looks
  adjacent (`#1068` defect class).
- `escA` (`:15`, attribute escape), `preB` (`:353`, raw `<pre>`) — separate
  utilities, not on the `mdB` path.

---

## 2. The contract `goals.js` actually depends on

Read from the consumer side (`goals.js`), not from `mdB`'s side. `/goals`
mounts the delegate once, at `goals.js:196`:
`React.createElement(Details, { text: current.details })` — and `Details`
(`:5`) calls `mdB(props.text || '')`.

**What `/goals` passes in:**
- one `string` (`current.details` — a goal's Markdown body, free text).

**What `/goals` expects back:**
- one HTML `string`, already wrapped in `<div class="md">…</div>`, committed
  via `dangerouslySetInnerHTML` (`delegate.js:110-111`). It never inspects the
  string's interior.

**Behaviours `/goals` uses** (the boundary should cover these):
- prose reflow — hard-wrapped (~72-col) input joined into paragraphs.
- inline spans: `**bold**` (rendered as luminance via `.mdh`/CSS, not mono
  bold), `*em*`, `` `code` ``.
- backticked-path linkification → `/file` links (when the path is in
  `data.linkable_paths`).
- `[text](target)` markdown links — with `base=null`, so only absolute
  `http(s)`, known-internal paths, and fully-literal fallthrough.
- block structure: `#` headings, `- `/`*` bullets with indent-rank nesting,
  `>` blockquotes, ` ``` ` fenced code, GFM pipe tables.

**Behaviours `mdB` *has* that `/goals` does *not* use** (out of boundary):
- **`filePath` / `baseDir` threading** — relative `[text](../x)` resolution
  against the viewed file's directory. `/goals` calls `mdB` with **one arg**,
  so `base` is always `null` and `mdNormJoin` is never given a non-null
  `baseDir`. This is live machinery in the graph that `/goals` never drives.
  (`views.js:1148` and `:1394` *do* pass a `filePath` and exercise it — see §3.)

This is the `#1068`-class distinction the brief names: a coupling
description that listed `filePath`/`baseDir` as a `/goals` need would name
machinery the surface does not use.

---

## 3. Who else calls into this graph — the make-or-break measurement

**Search run:** `grep -rn "mdB\b\|mdBReview\b" --include=*.js --include=*.py
--include=*.mjs dev/ client/` (excluding `node_modules`), plus a separate
`grep -rn "fromBuilder(" dev/build/src/` to enumerate every native delegate.
Results classified below. This is not "I did not find any" (`#136`); there
are many, and they are listed.

`mdB` and the graph above are **not exclusive to `/goals`**. The entire
classic dashboard (`client/views.js`) renders Markdown through the same graph:

| Caller | Site | What it renders | Args |
|---|---|---|---|
| `views.js:8` | `mdB(d.content, '')` | a dream's content | text |
| `views.js:436` | `mdB(c.body)` | a commit message body | text |
| `views.js:1148` | `mdB(d.files[n], n)` | a peeked file's body | **text + filePath** |
| `views.js:1185` | `mdB(e.body)` | an answer/ask body | text |
| `views.js:1394` | `mdB(text, param)` | `/file` for a Markdown path | **text + filePath** |
| `views.js:1508` | `mdB(task.body \|\| '')` | a task's body | text |
| `views.js:1100` | `mdBReview(q.body.trim(), q.title)` | a question body (sibling renderer) | text + title |

`dev/capture/*.mjs` (reflow, mdquote, mdtable) also bind `mdB` on known input
for capture-grade equality checks — they are test/capture harness, not a
served surface, but they confirm the graph is the canonical renderer.

**How the two consumers reach `mdB`:** all of `client/*.js` are concatenated
in `_CLIENT_ASSETS` order (`watch.py:498`: `components.js` before `views.js`
before `router.js` …) into **one classic page scope**. `views.js` calls
`mdB` by bare name, resolved from that shared lexical scope. The native
bundle (`client/dist/native.js`) is a separate esbuild module, and
`/goals`' delegate resolves the same `mdB` by bare name through the page's
global lexical environment — the `#630` coexistence bridge documented in
`delegate.js:76-82`. **Both sides already reach one authority.**

**Decisive consequence for deletability:** `client/components.js` cannot be
made deletable by removing `/goals`' delegate alone. `views.js` independently
holds it alive (six `mdB` sites + one `mdBReview`). The legacy layer is
deleted *atomically*, as a set, by **`#1053`** ("replace routeOf with a React
Router and delete `client/{router,views,components}.js` — the atomic move"),
which kills all three files in one commit. So the brief's framing — *"/goals
is still what prevents `components.js` from being deleted"* — is **only
partly right**: `/goals` is *a* consumer, but the blocker is the whole
classic dashboard, and the deletion vehicle is `#1053`, not this task.

---

## 4. Three costed options, with a recommendation

The filing says to **file** the implementation increments, not size them
here. Increments are named below; their durations are not estimated.

### Option A — **Share it (status quo, formalised)**  ← RECOMMENDED
Keep `mdB` and its graph in `client/components.js` as the single Markdown
authority. `/goals` keeps delegating to it; `views.js` keeps calling it
directly. **This is already the state of the tree.** The "native Markdown
boundary" is the existing `fromBuilder('mdB', …)` delegate — the `#630`
coexistence bridge — and no new boundary needs to be drawn *for this task*.

- **`components.js` deletability:** unchanged. It stays undeletable until
  `#1053`, regardless of `/goals`, because `views.js` needs it. This is
  honest, not a failure: `#1053` is the planned deletion vehicle.
- **Other callers:** all of `views.js` continues to work unchanged.
- **Second-truth rule:** **most favoured.** There is exactly one renderer,
  reached from both sides (`DREAMWORK.md`; `dreamhub-design.md`'s *"two
  renderers only agree on the day they are written"*). No second authority is
  created.
- **Cost now:** zero code. The deliverable *is* this document; it records the
  boundary and pushes the move/replace decision into `#1053`'s atomic flip,
  where the whole legacy layer dies together and a native Markdown authority
  is chosen *then*, with the full picture in hand.
- **Increments filed:** none new. The boundary decision is deferred to
  `#1053`; this task's increment is "decide share/move/replace inside `#1053`
  as part of the atomic flip." (`#994`: a scoping doc names what the
  increments are.)

### Option B — Move the parser (extract a shared Markdown file now)
Extract `mdB` + its graph into a new file (e.g. `client/markdown.js`), add it
to `_CLIENT_ASSETS` in the same position, delete the definitions from
`components.js`. Both `views.js` and the native delegate keep resolving
`mdB` by bare name from the shared page scope.

- **`components.js` deletability:** **not achieved** by this move alone —
  `views.js` still needs the (now relocated) `mdB`, and `views.js` itself is
  only deleted in `#1053`. So this removes *one* reason `components.js` is
  thick, but does not make it deletable.
- **Other callers:** `views.js` keeps working (same bare-name resolution);
  the capture harnesses keep working.
- **Second-truth rule:** still one authority — favoured, same as A.
- **Cost now:** non-trivial and **redo-prone**. The graph reads the external
  global `data.linkable_paths` (`router.js:9`), so the extracted file must
  keep that coupling intact or it silently stops linkifying. Roughly: (i) new
  `client/markdown.js` + `_CLIENT_ASSETS` entry; (ii) move 17 functions + 2
  constants; (iii) rebuild `client/dist` (manifest + both bundles); (iv) a
  capture equality check that the page renders identically. `#1053` will
  re-examine this seam when it deletes `views.js`, so the move may be done
  twice.
- **Increments filed:** (B1) create `client/markdown.js` + asset entry;
  (B2) relocate the graph and rebuild dist; (B3) capture-equality guard.

### Option C — Replace it (a native Markdown React component for `/goals`)
Write a new design-package export (in the `QaCard` family) that renders
Markdown natively, and stop delegating to `mdB` from `/goals`.

- **`components.js` deletability:** **not achieved** — `views.js` still uses
  `mdB`, so `components.js` survives until `#1053` exactly as in A.
- **Other callers:** `views.js` unaffected (keeps `mdB`).
- **Second-truth rule:** **refused on principle** *as a standalone change*.
  Until `#1053` deletes the legacy `mdB`, this option creates a **second
  maintained renderer** of the same Markdown — precisely the divergence the
  rule exists to prevent. It becomes defensible only *inside* `#1053`, where
  the legacy `mdB` is deleted in the same atomic commit (zero-commit overlap,
  the `#751`/`#890` model `#1053` cites).
- **Cost now:** high, and doctrinally blocked until `#1053`. Re-implementing
  reflow + spans + both linkifiers + tables + the `data.linkable_paths`
  coupling, plus a wrapper + `.d.ts` + fixture + rebuilt dist.
- **Increments filed:** (C1) native markdown wrapper + design-package export;
  (C2) `.d.ts` + fixture + `wrappereq`-style equality; (C3) delete the
  `/goals` `mdB` delegate — **blocked behind `#1053`'s atomic flip**.

### Why "share it" wins
The three are **not symmetric**, and the brief asks me to say so. A and B
keep one authority (favoured); C creates two (refused standalone). Between A
and B, B buys nothing the deletion vehicle (`#1053`) does not already buy,
costs real increments now, and risks being redone. **A is the correct
boundary for this task: the existing delegate already shares one authority,
and the move/replace decision belongs to `#1053`.**

---

## 5. The design-package exposure question

Does a shared boundary need a design-package wrapper (a `QaCard`-style
export)? **It depends on the `#1053` decision, which this task does not
make — stated plainly rather than guessed:**

- Under **A (share, status quo):** no wrapper. The `fromBuilder('mdB', …)`
  delegate already bridges native→classic without one.
- Under **B (move):** still no wrapper — `mdB` stays a classic-script
  builder; the delegate resolves it by bare name exactly as today.
- Under **C (replace):** a wrapper/export is the *whole point*, but C is
  blocked behind `#1053`.

So the exposure question has no answer at this layer: it is downstream of the
`#1053` atomic-flip decision (native module vs. continued classic-script
coexistence). Filing it there, not deciding it here.

---

## 6. How this document could look finished and still be false

The brief names four; here is each, with what I did about it.

1. **The graph is shallow.** Ruled out: I traversed transitively to leaves
   and listed the closure (17 functions + 2 regex constants + the external
   `data` global). I stopped only when every callee was a leaf or an external.
   The "eight visible lines" error is the one thing this graph is *not*.
2. **Callers outside `/goals` were never searched for.** Ruled out: §3 lists
   the search command and every hit. There are **seven** `mdB`/`mdBReview`
   sites in `views.js` alone; the finding is "there are many", not "I found
   none" (`#136`).
3. **The contract is described from `mdB`'s side.** Ruled out: §2 is written
   from `goals.js`'s call (`mdB(props.text || '')`, one arg) and explicitly
   carves `filePath`/`baseDir` *out* of the boundary as machinery `/goals`
   does not drive (`#1068`).
4. **A recommendation with no losing option.** Ruled out: each option names
   its cost. A's cost is "defers the decision to `#1053`" (not zero — it
   leaves `components.js` thick until then); B's is "real increments that
   `#1053` may redo"; C's is "doctrinally refused as a second renderer until
   `#1053`."

---

## Citation evidence opened

- **#967** — "verify the brief's premises before building on them." The
  `:742` citation drifted to `:779`; caught at §0, not after the doc was
  built on it.
- **#136** — "an empty selection is indistinguishable from a broken
  derivation." §3 distinguishes "there are many callers" from "I found none."
- **#1068** — a coupling description that named machinery the surface did not
  use. §2 keeps `filePath`/`baseDir` out of the `/goals` boundary for this
  reason.
- **#994** — "a report is not a certification." This doc names increments; it
  does not certify they will work.
- **#1053** — "delete `client/{router,views,components}.js` — the atomic
  move." The deletion vehicle for `components.js`; decisive for §3 and §4.
