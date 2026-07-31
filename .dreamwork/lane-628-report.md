# Lane #628 PHASE 1 — which `dev/capture` guards could `--hide-scrollbars` have blinded?

**Scope:** every guard-shaped `.mjs` in `dev/capture/` (95 files minus 4 helper modules =
91; the `justfile` `guards` recipe lists 85, of which `gutter` is the fixed exemplar).
**Method:** read the `ok()`/`present()` assertion bodies, never the header comments
(`lessons.md:3280`), then asked of each assertion: *does its value couple to
`document.documentElement.clientWidth` or to a centered column's absolute horizontal
position — both of which shift when a real scrollbar consumes ~10px — or is it
sibling-relative / vertical / non-geometric, and therefore invariant?*
**No guard was run. No launch option was changed.** This is a read-only classification.

---

## The mechanism, stated once

Playwright passes `--hide-scrollbars` in headless by default, so in every guard
except `gutter.mjs` the scrollbar has zero width. The discriminating questions:

| signal | scrollbar-sensitive? | why |
|---|---|---|
| `document.documentElement.clientWidth` | **YES** | = `innerWidth − scrollbarWidth`; flips between scroll/no-scroll routes |
| `el.scrollWidth > clientWidth` (overflow-x) | **YES** | clientWidth is the divisor; hidden scrollbar inflates it, suppressing overflow |
| `scrollTo(9999,0)` / `window.scrollX` | **YES** | no horizontal scroll exists when clientWidth is inflated |
| `getBoundingClientRect().x/.left/.right` of a **centered** column | **YES** | the column recenters on clientWidth; shifts ~5px (the gutter bug, `#597`) |
| `getBoundingClientRect()` **between siblings** in one container | **no** | both shift together; the delta is invariant |
| `window.innerWidth` | **no** | the full layout viewport; the scrollbar does not change it |
| `scrollHeight` / `clientHeight` / `.top` / `.bottom` | **no** | vertical; the scrollbar is horizontal |
| `opacity` / `color` / `transform` / `display` / text content | **no** | not geometry |

The one exception the suite already knows about — `gutter.mjs` — is the reference.

---

## Direction-1 discharge: the method re-finds the known answer

**`gutter.mjs` → AFFECTED (by definition — it is the fixed exemplar).** The method
re-derives this from its assertions, not from the header. Relied-on lines:

- `gutter.mjs:61` — `ignoreDefaultArgs: ['--hide-scrollbars']` (the one launch that keeps the scrollbar).
- `gutter.mjs:129` — `ok('… this browser's scrollbar consumes width (sb=${tall.sb}px) …', tall.sb > 0)` — §0 refuses to grade until `innerWidth − clientWidth > 0`.
- `gutter.mjs:169` — `ok('… #htitle visits ONE x across the … transition …', nav.xs.length === 1)` — the contract: a centered chrome element's `.x` must not gain a second value when the scrollbar flips. This is a centered-column absolute-`.x` assertion → **AFFECTED** by the table above.

**`#597`'s route-change case → AFFECTED.** The finding (ledger `#597`): "`#htitle`'s `x`
visits exactly two values across a `/` -> `/answers` transition, 436.2 and 441.2,
while the scrollbar width goes 10 -> 0." That is a centered-column `.x` measured
across a scroll/no-scroll route pair — the row marked **YES** above. The method
classifies it AFFECTED without being told it is the known case. A method that could
not re-find the case we already solved has not been shown to work; this one does.

---

## AFFECTED — ranked for phase 2's running order

Ranked by how likely a real-scrollbar re-run is to *change the verdict*, not merely
the measured number. Tier 1 asserts overflow-x / `clientWidth` directly, so the
value is certain to differ; the question is only whether the verdict flips. Tier 2
asserts centered-column horizontal position, so it differs only across a
scroll/no-scroll route pair.

### Tier 1 — overflow-x / clientWidth / horizontal-scroll (HIGH)

| # | file | the assertion that couples | line |
|---|---|---|---|
| 1 | `hfit.mjs` | `scrollTo(9999,0) moves the page nowhere`; `no horizontal scroll at 390px`; `160 chars … still does not scroll the page sideways` — and the ledger names this guard explicitly ("Same shape as hfit: the assertion was right and the instrument was wrong") | 209, 214, 283 |
| 2 | `reviewsplit.mjs` | `no part of the pane hangs off the side of the window`; `the artifact and the question are both full width`; `dragging the bar LEFT narrows the artifact and widens the question`; `the width he dragged survives a route change` — heavy absolute horizontal geometry + a route change | 658, 660, 397, 412 |
| 3 | `filehead.mjs` | `no part of the path is painted outside the reading column`; `the page still does not scroll sideways at 520px` | 246, 252 |
| 4 | `filehl.mjs` | `the overflow stays INSIDE the pane: the document does not [scroll sideways]`; `390px: … the PAGE still does not scroll sideways` | 222, 238 |
| 5 | `fileview.mjs` | `the page still does not scroll sideways`; column width-ratio across Source/Rendered swap | 325, 480 |
| 6 | `provenance.mjs` | `no horizontal overflow at 1440px, and the legend is not clipped`; `the datum itself never sticks out of the viewport` | 315, 337 |
| 7 | `artifactwrap.mjs` | `the page does not scroll horizontally`; word-ink width measured via `Range` over each word (width-coupled by construction) | 195, 191 |

### Tier 2 — centered-column horizontal position (MEDIUM)

| # | file | the assertion that couples | line |
|---|---|---|---|
| 8 | `markrail.mjs` | `never clips past the page edge (g.worst.r <= g.vw + 0.5)`; `the flag anchors at the reading column's right edge` — flag `.right` is centered-column-coupled, `vw` is `innerWidth` | 191, 194 |

### The exemplar (already fixed — AFFECTED by definition)

| — | `gutter.mjs` | `#htitle visits ONE x across the transition`; `this browser's scrollbar consumes width` | 169, 129 |

---

## UNCLEAR — reported, not forced (`#702`)

A guard lands here when its assertion *could* couple but whether the verdict flips
depends on a fact not decidable from the source alone: **do the two routes it
compares differ in scroll-state?** If both scroll (or both do not), the scrollbar
tax cancels and the assertion is invariant; if one scrolls and the other does not,
it is the gutter bug in disguise. Phase 2 resolves each by checking the routes'
`scrollHeight > innerHeight`.

| file | why it is unclear | what phase 2 checks |
|---|---|---|
| `headertravel.mjs` | Navigates between routes and asserts the heading `+`'s `.left`/`.width` (`:213` "the + is fully visible with a gap, every route x every width") and that "the column really changes width" (`:174`). If the wider route scrolls and the narrower does not, the width delta absorbs the scrollbar tax and the `+` shifts. | Whether the two routes it navigates between differ in `scrollHeight > innerHeight`. |
| `projtitle.mjs` | Compares the route title's `.left`/`.right`/`.width` across routes with a tolerance (`:115` `Math.abs(a.left − b.left) <= tol`). A centered title shifts ~5px across a scroll/no-scroll pair; whether that exceeds `tol` is the open question. | The tolerance value and the two routes' scroll-state. |

---

## UNAFFECTED — one line each (`#612`)

The assertion is sibling-relative, vertical-only, non-geometric (opacity/colour/
text/DOM identity), or measures `innerWidth` (which the scrollbar does not change).

**Sibling-relative / innerWidth geometry (robust to a uniform shift):** `indicator.mjs`
(indicator-vs-button `.left`/`.width` delta), `qdual.mjs` (`cr.left >= br.right`;
1280-vs-1000 breakpoint has 270px margin), `typing.mjs` (indicator `.left` stable
across a tick on one page), `indtrace.mjs` (indicator transform intermediates —
sibling slide), `plugcmd.mjs` (`offsetWidth > 10` existence + transform/opacity).

**Vertical-only geometry:** `autogrow.mjs`, `morph.mjs`, `qorder.mjs`, `qsec.mjs`,
`prominence.mjs`, `gitrow.mjs`, `resize.mjs`, `qroll.mjs`, `qfade.mjs` (vertical
fade masks), `noteprop.mjs` (vertical iframe scroll), `menucap.mjs` (vertical top),
`posture.mjs`, `posturerecuse.mjs` (sticky top/bottom vs `innerHeight`; width is
content-driven deploy label), `reviewsplit`'s resize/fade sub-checks (the
AFFECTED-flagged layout checks above are the ones that couple).

**Non-geometric (opacity/colour/transform/display/text/DOM identity/timing):**
`answers.mjs`, `bdhover.mjs`, `bdinput.mjs`, `burndown.mjs` ("nowrap" is
`display === 'flex'`, a declaration; bars are height-driven), `chatsurface.mjs`,
`cmdcap.mjs`, `coexist.mjs`, `confirmation.mjs`, `corpse.mjs`, `dashboard.mjs`,
`devoverlay.mjs` (`innerWidth === w` is the full viewport; fold heights are
vertical), `dismiss.mjs`, `dissolve.mjs`, `dreamfade.mjs`, `draft.mjs`,
`escattr.mjs`, `fileimg.mjs`, `headcrumb.mjs`, `health.mjs`, `history.mjs`,
`identity.mjs`, `marktab-geometry.mjs`, `mdquote.mjs`, `mdtable.mjs`,
`morphhold.mjs`, `motion.mjs`, `oneinput.mjs`, `optrace.mjs`, `popbg.mjs`,
`qacard.mjs`, `qfocus.mjs`, `qgroup.mjs`, `qlinkpip.mjs`, `qsignal.mjs`,
`reflow.mjs` (controls `host.style.width` itself — viewport-decoupled),
`regroup.mjs`, `regroupdraft.mjs`, `rejectwrite.mjs`, `remindbtn.mjs`,
`research.mjs`, `restcollapse.mjs`, `reviewask.mjs`, `reviewcap.mjs`,
`reviewdraft.mjs`, `revieworder.mjs`, `reviews5.mjs`, `rm-check2.mjs`,
`selectkeep.mjs`, `serving.mjs`, `staleremedy.mjs`, `states.mjs`, `status.mjs`,
`submitlog.mjs`, `subslog.mjs`, `summaryjson.mjs`, `thread.mjs`, `wisp.mjs`
(2px rail + keyframes), `worldspace.mjs` (canvas creation, not measurement).

---

## Header-vs-body mismatches (`lessons.md:3280`)

The brief warns that a guard's header is not its assertion list. Two worth naming:

- **`burndown.mjs`** — its header and `#417` commentary talk about column "cap
  weight" and the figure line not ellipsising, which *sounds* width-coupled. The
  actual `ok()` at `:557` is `rDef.headDisplay === 'flex'` (a `display` declaration,
  not a width measurement), and the ellipsis check reads `text-overflow` computed
  style. Neither couples to `clientWidth`. Classified UNAFFECTED on the body, not
  the header.
- **`answers.mjs`** — collects `getBoundingClientRect().width` (`:533`) and reads
  inline `style.overflow` (`:100`), which look horizontal. The `ok()` that consumes
  the width is an existence check (`h > 8`); the overflow reads are inline-style
  cleanup after a vertical collapse transition (`height === '' && overflow === ''`).
  UNAFFECTED on the body.

No guard was found whose header claims one thing and whose body asserts a
scrollbar-sensitive value the header hides — but the two above are the places a
careless read would have misclassified.

---

## Findings named, not fixed (per the brief)

- **`reviewsplit.mjs:658`** — `phone: no part of the pane hangs off the side of the
  window` asserts an absolute `.right` against `innerWidth` on a page that scrolls.
  With `scrollbar-gutter: stable` (the `#597` fix) the gutter is reserved on every
  route, so this is likely already correct in production; but the *guard* has never
  seen the scrollbar, so it has never actually tested the claim. This is the
  highest-value phase-2 target after `hfit`.
- **`hfit.mjs`** — the ledger says this guard's assertion "was right and the
  instrument was wrong," the same shape as `gutter`. It is the single most likely
  guard to produce a real defect on re-run. Phase 2 should re-run it first.

No guard was observed to be *broken* (asserting the wrong thing); the finding is
that eight guards assert the right thing through an instrument that has never been
able to see the class of effect they guard.

---

## Rebase & sweep

Rebased onto local `master` before writing the sha-free verdict above (no sha is
cited, so no rebase-order hazard). Conflict-marker scan after any resolution:
`grep -nE '^(<{7}|>{7}|\|{7}|={7}$)'` — clean.
