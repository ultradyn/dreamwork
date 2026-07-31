# Visual audit — dreamwork dashboard (127.0.0.1:35110)

`[visual-audit]` · 2026-07-31 · read-only inspection of the live instance.
Screenshots: `./visual-audit-shots/<route>-<viewport>.png` (81 files).

Ground truth read before judging: `watch-design.md` (4104 lines, styleguide +
design contracts), `transitions.md`, `client/style.css`, `client/router.js`,
`client/views.js`, `review-artifact.template.html`.

---

## DEFECTS

Ranked by how much they cost the reader.

### D1 — `/` scrolls sideways at 390px (28px) · `dashboard-390.png`

**Route/viewport:** `/` at 390×844 (and any width where `.wrap` < ~410px).

**Measured:** `document.documentElement.scrollWidth` = 408 vs `clientWidth` =
380. `window.scrollTo(9999,0)` reaches `scrollX = 28` — the sideways scroll is
real and reachable, not a phantom overflow region. The single culprit is one
element:

```
SPAN.crumb  right=407.6  (+27.6 past the content edge)  white-space:nowrap
  text: "skill 2026-07-26-02-contextual-plugin-loading.md"
```

**Why it is wrong:** `style.css:65` sets `.crumb { white-space:nowrap; }`, and
the comment immediately above it states the rule and its single exception —
*"the ONE exception is the path, which must wrap anywhere (`.fdir` re-enables
wrapping for its own text)"*. The skill-version crumb (`router.js` ~3465,
`{ k:'version' }`) puts an arbitrary-length **filename** into a nowrap crumb.
It is exactly the class of content `.fdir` exists for, and it never got the
exception. Independently, the styleguide's file-view section commits to *"the
page never scrolls sideways (asserted at desktop and at 390px)"* — that
promise is currently false on the dashboard.

The sibling `{ k:'target' }` crumb (the absolute project path,
`/home/xertrov/.llm-general/skills/ud-dreamwork`) measured right = ~360 at
390px — it fits *today* but is the same unbounded-length value in the same
nowrap box, so it is one deeper checkout path from the same bug.

**Suggested fix:** give the two unbounded-length crumbs the `.fdir` treatment
rather than widening the rule for all crumbs (short labels should still stay
whole). E.g. a `.crumb.crumbfree { white-space:normal; overflow-wrap:anywhere;
word-break:break-word; }` modifier, applied to the `target` and `version`
crumbs at their build sites. Add a 390px `scrollWidth === clientWidth`
assertion for `/` to whichever capture guard owns the crumb row
(`dev/capture/headcrumb.mjs`).

### D2 — `/file?p=DREAMWORK.md` scrolls sideways at 390px (32px) · `filemd-390.png`

**Route/viewport:** `/file?p=<markdown containing a long inline repo path>` at
390×844. Reproduced on `DREAMWORK.md`; not present on `status_derive.py`.

**Measured:** `scrollWidth` 412 vs `clientWidth` 380; `scrollX` reaches 32.
Culprit chain:

```
SPAN.mdfile   +23.8   ".dreamwork/docs/dogfood-orchestration.md"   white-space:nowrap
BUTTON.pipbtn +23.8   (the #506 pip glued to that link)
```

**Why it is wrong:** same styleguide sentence as D1 — the file view's source
pane section explicitly asserts *"a long line scrolls horizontally INSIDE the
pane, and the page never scrolls sideways (asserted at desktop and at 390px)"*.
The existing guard (`dev/capture/filehl.mjs`) proves that for the **source**
pane. Nothing checks the **rendered** markdown pane, and that is where it
fails. `style.css:1823` is the cause:

```css
.mdfile { white-space:nowrap; }
```

with a comment that reasons *"long paths already overflow as one code token"* —
true, but the consequence (the overflow reaches the document's scroll area at
mobile widths) was never measured. Note `/questions`, `/answers` and `/` do
**not** show this: their long `.mdfile` spans happen to sit inside closed
`<details>`, so they have no geometry. That is luck, not containment — open a
fold with a long path in it and the same bug is available there.

**Suggested fix:** the nowrap exists only to stop the pip orphaning onto the
next line. Keep that guarantee on a *tail* unit instead of the whole path:
`.mdfile { white-space:normal; overflow-wrap:anywhere; }` and wrap the final
path segment + `pipBtn` in an inner `white-space:nowrap` span at the `linkify`
/ `mdBReview` emit site. Then assert `scrollWidth === clientWidth` at 390px on
`/file` with a rendered-markdown fixture, not only a source fixture.

### D3 — any unrecognised path serves a raw Python 404 · `tasks-1920.png`

**Route/viewport:** `/tasks` (the route named in my brief) at every viewport;
generalises to any path `routeOf` does not claim.

**What you get:** `HTTP 404` with `BaseHTTPRequestHandler`'s stock body —
black-on-white Times, `<h1>Error response</h1>`, `color-scheme: light dark`,
no chrome, no shader, no crumb, **no link back**. It is the only surface on
the whole instance that is not the design system.

**Why it is wrong:** the SPA already has a not-found voice and uses it well —
`/chat` with no id renders a proper `NOT FOUND` panel with a "← back to
dashboard" link (`chatnone-1920.png`). A mistyped or stale URL is a strictly
more likely arrival than a deleted chat id, and it lands on the one page that
gives the reader nothing.

**Suggested fix:** in the server's routing, treat any unmatched
non-asset path the way `/chat/<unknown>` is treated — serve `page_shell` and
let the client router render the in-voice not-found body. If a hard 404 status
is wanted for correctness, serve the shell **with** a 404 status rather than
the default error page.

### D4 — `/research` heading reads `dreamwork watch` · `research-1440.png`, `researchart-1440.png`

**Route/viewport:** `/research` and `/research?p=window-coords.html`, all
viewports.

**Measured:**

| route | `#htitle` (visible) | `document.title` (tab) |
|---|---|---|
| `/reviews` | `reviews` | `… · reviews` |
| `/research` | **`dreamwork watch`** | `… · research` |
| `/research?p=window-coords.html` | **`dreamwork watch`** | `… · research window-coords.html` |

**Why it is wrong:** `router.js:3323 const TITLES = {…}` has entries for
`dashboard, questions, answers, file, review, question, reviews, chat` —
and **no `research`** — so it falls through to `TITLES.dashboard`. The tab
title is correct because `TITLE_ROUTE` *does* have a `research` entry.

This is precisely the failure the styleguide already documents twice:
*"each table's fallback is silent — a missing tint inherits the dashboard's
hue, a missing title inherits its empty route word"* (#302, #318), and
*"`test_watch.py` now derives the destination set from `routeOf` and diffs all
three [tables], so a fourth table added here must be added there too or the
omission is invisible again."* `TITLES` **is** that fourth table and it is not
in the diff. The comment at `router.js:3335` even reads *"the heading names it
like the research listing does"* — the author believed the entry existed.

It also re-opens #172's stated problem in reverse: the tab strip says
`research`, the open page says `dreamwork watch`, and *"a multi-window strip
and a glance at the open page answered different questions."*

**Suggested fix:** add `research: v => 'research' + (v.param ? …)` to `TITLES`
(mirroring `TITLE_ROUTE`'s shape), and extend `test_watch.py`'s per-route table
diff from three tables to four so `TITLES` can never silently fall back again.

### D5 — every route change between a scrolling and a non-scrolling route snaps the page 5px sideways

**Route/viewport:** any nav between a long route (`/`, `/questions`, `/file`)
and a short one (`/answers`, `/reviews`, `/research`, `/chat/<id>`). Measured
at 1440×900; scales with scrollbar width.

**Measured** — client-side nav `/` → `/answers`, sampling `#htitle`'s rect
every frame for 40 frames:

```
x values visited across the whole transition: [436.2, 441.2]   ← two, i.e. a snap
scrollbar width across the same frames:       [10, 0]
```

Every route the audit touched sits at `titleX = 441.2` except the three that
scroll, which sit at `436.2`. `getComputedStyle(document.documentElement)
.scrollbarGutter === "auto"`.

**Why it is wrong:** `transitions.md`'s whole premise — *"the page arrives and
departs, it never appears"* — and the persistent-chrome section's origin
story: the chrome was hoisted out of `#view` precisely because a route change
*"read as 'the elements jump around' rather than as the page opening up"*. The
heading, the project identity, the crumbs and every line of body text step 5px
right in one frame, on a page where the same section spends real effort making
a **column width** change glide (`body.wsliding`). A snap among drifts.

Caveat, stated because it bounds the impact: this is invisible with overlay
scrollbars (macOS default). It is fully visible with classic scrollbars, which
is what Chromium on Linux/KDE gives you.

**Suggested fix:** one line — `html { scrollbar-gutter: stable; }`. The gutter
is then reserved on every route and the column never moves. (`stable
both-edges` if perfect symmetry matters more than 10px of width.) Worth a
`headertravel.mjs` check that `#htitle`'s `x` is equal across a long route and
a short one.

### D6 — the burndown tip is 88% opaque over a live head line, so two sets of numbers superimpose · `bd-tip-headband-1440.png`, `bd-hover-inspector-1440.png`

**Route/viewport:** `/` while hovering any burndown column; all desktop
viewports.

**Measured** while hovering column `Jul 27`:

```
.bdtip   position:absolute  z-index:2  rect [439, 853, 553×19]
         background-color: color(srgb 0.043 0.059 0.098 / 0.88)   ← alpha 0.88
         text: "125 open · 95↑ 78↓ · 113 commits · Jul 27"
.bdhead  position:static    rect [439, 853, 553×16]
         visibility: visible   opacity: 1                          ← still painted
         text: "122 open · 477 arrived · 358 landed · daily"
```

Identical origin, identical width, and the lower layer is not hidden — so 12%
of the head line's ink composites through the tip. Both lines start with a
three-digit "open" count at the same x, so `125` is printed over a ghost `122`.
Visible in the crop as a stray stroke left of `125` and haze between glyphs.

**Why it is wrong:** the design contract's thesis is *"glanceable status"*;
two different numbers occupying one glyph cell is the exact opposite. And #326
already ruled on painting `--bg` plates on this page: *"The black stuff around
the answer box to emulate the fade thing is ugly… The text itself should fade,
not be covered by fake fade."* The fix chosen there was to make the underlying
**text** translucent rather than paint over it — the same move works here.

**Suggested fix:** cross-fade the two, do not stack them. While a tip is live,
take `.bdhead` to `opacity:0` on the same `.42s` envelope `#559` already uses
for the tip's content cross-dissolve, and drop `.bdtip`'s background to fully
transparent. That also removes a `--bg` plate from in front of the living
shader, which is what #326 asked for. If a plate must stay, take it to
`alpha: 1`.

### D7 — a settled review artifact renders its verdict in `--warn` amber · `review-1440.png`

**Route/viewport:** `/review?p=…` at ≥480px (the marker is hidden below that —
see D9). Inside the artifact document, not the shell.

**Measured** — `review-artifact.template.html:150`:

```css
.status{color:var(--warn); …}
.status::before{ …background:var(--warn); box-shadow:0 0 12px rgba(252,211,77,.55)}
```

unconditionally, for every value. Across the built corpus in
`.dreamwork/review/*.html` the values are:

```
16 × "awaiting review"      1 × "DECIDED · 2026-07-29 01:37 · ack good to go"
 1 × "approved with amendments · re-verified 27 Jul"
 1 × "DECIDED 06:23 · c3+c4+hover"      1 × "awaiting decision"   …
```

So `ack good to go` and `approved with amendments` are painted in amber with a
glowing dot.

**Why it is wrong:** watch-design.md's tokens section is unusually explicit:
*"There is a second colour, `--warn` amber, and it means BROKEN rather than
live (#136)… Its uses are enumerable and must stay that way: a `questions.md`
the reader cannot see, a send the server refused, code this page is not
actually running (#140), and a push channel that cannot reach him (#190)…
Nothing that is merely important gets it."* A review verdict is none of the
four, and an **approved** one is the furthest thing from broken. The dashboard
already got this right — #289's row token uses *"accepted ✔ / rejected ✘ (both
dimmed, the `done` darkening idiom)"* — so the two surfaces now disagree about
what a decision looks like.

**Suggested fix:** key `.status` off the decision state. Settled → step **down**
the ramp (`--dim`, no dot), matching #289's darkening idiom. Pending/awaiting →
`--accent` with the dot (it is live and waiting on him, which is what the accent
is for). Reserve `--warn` for a build that could not read its own decision
record. Add the enumerated-uses check to `test_review_artifact.py` if there is
somewhere natural for it.

### D8 — `#hproj` and the `+` opener drop 7.4px on `/chat/<id>` · `chat-1440.png`

**Route/viewport:** `/chat/6515adb2-…` at 1440×900 (any width where the chat
title wraps — i.e. most).

**Measured** (`getBoundingClientRect`, same 1440px window):

| route | `#hproj` y | `#htitle` height | `.htitlebar` height | `+` opener y |
|---|---|---|---|---|
| `/` | 43.1 | 21 | 27.2 | 40.0 |
| `/questions` | 43.1 | 21 | 27.2 | 40.0 |
| `/chat/<id>` | **50.5** | **42** | **42** | **47.4** |

The chat heading is the chat's full derived title, which wraps to two lines;
`align-items:center` then re-centres the identity and the opener in the taller
flex line.

**Why it is wrong:** #172's stated invariant is *"the identity's box does not
move when `questions` becomes `review 367-option-previews.html`"*, and the
section calls measuring it *"the load-bearing check"*. `dev/capture/
projtitle.mjs` enforces it on `/`, `/questions` and a long `/review?p=…`; it
correctly excludes `/review` from the absolute comparison because *"On /review
the column itself widens"* (guard, line 137). `/chat/<id>` has the **same**
column width as `/` and `/questions`, so it is inside the guard's own
comparison class — it is simply not in the guard's route list, because the
guard predates #562. The invariant is violated and nothing notices.

**Suggested fix:** two parts. (a) Extend `projtitle.mjs`'s absolute-rect
comparison to `/chat/<id>` with a title long enough to wrap. (b) Decide the
behaviour: either constrain the heading to one line (see O1, which I think is
the better answer anyway) or pin `#hproj` to the flex line's **first** line box
(`align-self:flex-start` plus the line-height offset) so it stays put when the
route word grows a second line.

*Note on the doc, not the page:* watch-design.md's prose says the guard
*"requires the three boxes to be identical"*. The guard itself is more careful
than that — it only compares absolutely where the column width matches. The
page is right and the **doc sentence is loose**; it should say "identical
wherever the column width is the same".

### D9 — the review artifact drops its own status and one nav link at narrow widths · `review-390.png`

**Route/viewport:** `/review?p=…` at 390×844 (and any window where the
artifact **pane** is under 860px / 480px — so also a narrow popout).

**Measured** at 390px, inside the iframe, `.topactions` children:

```
SPAN.status  "awaiting review"  display:none   ← @media(max-width:480px)
A.full       "findings"         display:none   ← @media(max-width:860px)
A            "shape"            visible
A            "decision"         visible
```

(`review-artifact.template.html:344` and `:352`.)

**Why it is wrong:** watch-design.md, *More detail*: *"**nothing is dropped,
only demoted** (#130) — … a reader that cannot see something renders
identically to there being nothing to see."* Two things are dropped outright.
The status is the artifact's *state* — whether it is waiting on him at all —
and it vanishes on the device he is most likely to be glancing from. And
`findings` is one of three peer section jumps; removing one of three leaves an
incomplete nav that reads as "this artifact has no findings section", which is
false.

**Suggested fix:** demote rather than drop. For the status: keep the dot and
shorten the word (`awaiting` / `decided`), or move it under the identity line
where there is width. For `findings`: it is only 89px — if the row genuinely
cannot hold three, collapse all three into the same `»` disclosure idiom #367's
markstrip already established for exactly this cliff, rather than hiding the
first one.

---

## OPPORTUNITIES

These work. They could be better.

### O1 — `/chat/<id>`'s heading is the whole chat title, at heading weight, truncated · `chat-1440.png`

The heading currently reads
`okay, first chat message! Let's dogfood this hey? I want you to prioritize any…`
— two full lines at `1rem` `--bright`, i.e. the loudest thing on the page, cut
mid-sentence, and repeated verbatim as the first message immediately below it.

#284 already ruled on this shape for the file view: a long identifier in the
heading *"competes with the document itself"*, and the fix was a two-part
lockup (short subject bright, address dim, one line each). #452 made the same
call for `/question`: *"the heading names the SURFACE, not the question — a
title can run to a line and a half, and it is rendered in full by the card
directly below."* `/chat` is the third instance of the identical situation and
took the opposite decision.

**Suggestion:** `chat` (or `chat · <short derived label>`) as the heading, full
title in the body where it already is. That also makes D8 disappear.

### O2 — `/chat` with no id explains a cause that cannot be true · `chatnone-1920.png`

The bare route renders: *"this link names a chat the list no longer has — it
was most likely removed while you watched."* For `/chat` with no id at all,
nothing was removed and nothing was watched. The panel is otherwise excellent
(right voice, accent rail, working way back).

**Suggestion:** branch the sentence on `param === null` — *"`/chat` names no
chat. Pick one from the dashboard."* — and keep today's copy for an id that
resolved nowhere.

### O3 — ~47px of permanently dead space at the foot of the posture panel on touch · `dashboard-390.png`

`.pdesc { min-height:2.6em }` (29px) and `.parm { min-height:1.15rem }` (18px)
reserve room so the panel does not jump when a posture description appears.
Measured at 390px both are empty with zero content (`.pdesc-text` height 0),
producing an 83px gap between the last chip row (`orchestration`, bottom 1941)
and the `tint` label (top 2024).

Reserving constant height is right (it is the burndown panel's own rule). The
observation is narrower: the description is **hover-driven**, and at 390px
there is no hover, so on a phone that space can never fill.

**Suggestion:** either gate the reservation behind `@media (hover:hover)`, or
give the touch case a reason to use it — e.g. show the *active* axis
description there at rest instead of only on hover, which fills the box and
teaches the axes at the same time.

### O4 — `.bdmed` truncates at 390px with no way to recover the tail

At 390px: `1h median time finished work took to land · over 358…` — box 348px,
text 389px, `text-overflow:ellipsis`, no `title=`. The number survives so the
loss is small ("pairs"), but it is a dropped tail rather than a demoted one.
`.bdcommit-copy` next to it, by contrast, has **106px of headroom** at the same
width — #417's "no ellipsis, the short form is the condition of shipping it"
ruling did its job there. Same shortening treatment would fix `.bdmed`.

### O5 — the column inspector's plate lands on the section label · `bd-hover-inspector-1440.png`

`.bdinsp` renders at y 792–849 while `.bd` starts at 853 — i.e. it floats
*above* the panel it belongs to and its bottom edge sits level with the
`BURNDOWN` label (831–845) and beside the `FILES` list. No glyph overlap at
1440 (the plate starts at x 548, the label ends at ~500), but it is a filled,
bordered box landing in the reading views' whitespace, which is where the
styleguide says structure is supposed to come from. Worth checking at narrower
widths where the plate's left edge moves in.

### O6 — at exactly 1000px the dual column runs edge-to-edge · `question-1000.png` vs `question-999.png`

`min-width:1000px` turns the grid on. At a 1000px window the wrap resolves to
958px (990 client − 32 padding), so both columns are flush against the page
padding with no gutter, while at 999px you get the calm 553px centred column
with ~200px of air either side. Both are correct per the rule; the 1000–1080px
band is where the dual column is at its least comfortable. Bumping the
breakpoint to ~1080 (where the full 1040 column plus real gutters actually
fits) would mean the dual column never appears in a state that looks cramped.
Filed as an opportunity, not a defect, because the documented contract is met
and the columns do read.

### O7 — `#dreambg` is `100vw`, so ~10px of the field sits under the scrollbar

Measured `+10.0` past `clientWidth` on every route at every viewport. Harmless
(the canvas has `overflow:clip` and creates no scroll), and it may be
deliberate so the field is continuous behind an overlay scrollbar. Mentioned
only so it is not re-discovered as a bug. Fixed for free by D5's
`scrollbar-gutter: stable`.

### O8 — `/reviews` does not state its own total · `reviews-1440.png`

The dashboard link that leads there says `all 31 reviews →`; the destination's
label just says `REVIEWS`. A `reviews · 31` label would close the loop and cost
nothing.

---

## Things I checked that are correct

Stated so the report is not read as "everything unmentioned is unexamined".

- **No horizontal scroll anywhere except D1/D2.** All 12 routes × 6 viewports
  audited for elements past the content edge, clipped-without-ellipsis boxes,
  and reachable `scrollX`. Everything else is clean at 1920/1440/1040/1000/999,
  and clean at 390 apart from the two named routes.
- **`/question` dual column geometry (#583)** is right. Traced 11 scroll
  positions at 1440×700: the compose column's centre tracks the question's
  *visible* midpoint to within 1px at every position (10px at scroll 0, the
  clamp), never leaves the viewport, never overlaps the body column.
  `body.question .wrap` = 1040 at 1920, 998 at 1040, 958 at 1000, and collapses
  to the normal 553 at 999 — exactly the documented breakpoint.
- **Burndown hover (#417/#559/#298)** behaves as documented. Full-column hit
  zone confirmed: `.bdnet` (y 891), `.bdflow` (y 932) **and the 9px gap between
  them** (y 910) all produce the readout. Moving between columns keeps the
  container at an identical rect and swaps content only — no depart, no
  re-arrival. Inspector arrives on a ~700ms dwell; both depart on leave.
  `tabindex="0"` is on the level-track columns only, and `aria-label` carries
  all four facts. (Its only problem is D6, which is a paint bug, not a
  behaviour bug.)
- **`/file` source pane (#351)** does the right thing: `status_derive.py`'s
  longest token runs 259px past the pane at 390px and scrolls **inside** it —
  `scrollX` stays 0. Byte-exact, in-pane, as designed.
- **Keyboard focus.** A real 26-stop Tab walk on the dashboard: every stop had
  a visible ring (outline or box-shadow). No gaps found. (An earlier
  programmatic `.focus()` sweep suggested otherwise — that was my error;
  `:focus-visible` does not fire on scripted focus.)
- **`.bdcommit-copy`** has 106px of headroom at 390px — #417's short-form ruling
  is holding.
- **The composer opens cleanly** (`composer-open-1440.png`): kinds group,
  textarea, send, pop-out, history disclosure, all inside the panel, no
  overflow. Opened only — nothing submitted.
- **`/chat` no-id, `/reviews`, `/research` listing, `/answers`, `/questions`**
  all render without overlap, clipping or reflow defects at every viewport
  tested.

---

## Coverage

**Fully covered.** `/` · `/questions` · `/answers` · `/reviews` ·
`/review?p=task-transition-boundary.html` · `/research` ·
`/research?p=window-coords.html` · `/file?p=DREAMWORK.md` ·
`/file?p=status_derive.py` · `/chat` · `/chat/6515adb2-…` ·
`/question?qid=…#584…` — each at 1920×1080, 1440×900, 1040×900, 1000×900,
999×900, 390×844.

**`/tasks` is not a route.** It is not in `routeOf`; the server 404s it. That
is D3 and it is why it has no meaningful screenshot beyond the error page.

**Not exercised, write risk (per brief).** Composer *send*; question
answer/note *send*; `/answers` *Ask*; chat *Reply*; the tint picker; the four
posture axes; run-mode; any deploy/decide/remind control. Also **not**
exercised, because they persist a preference to Max's `localStorage` and
re-fetch `data.json`: the burndown **granularity cycle** (`.bdstep`), the
**column-limit** input and its `[−] [+] [⟳]` steppers (#499/#524), and the
`/review` **splitter drag / keyed resize** (#305, writes `dw.review.split`). I
inspected all of their rendered geometry but did not operate them.

**Not covered at all** (out of scope for the time, named so the gap is
visible): `prefers-reduced-motion` parity on any surface; the PiP pop-out
windows (`pipBtn` → Document Picture-in-Picture); the artifact print
stylesheet; the hidden shader layer switcher (`l` / triple-click); the #367
flag rail and markstrip (the artifact I sampled has zero marks, so the rail
never rendered — a marked artifact would need to be picked deliberately);
`/review?p=…&q=…` with a **docked question**, which is the two-column state
most of #305/#326's design record is actually about — I only saw the
artifact-alone state.

---

## Dogfood report

Friction with the loop itself, not with the dashboard.

1. **The Playwright MCP screenshot root is pinned to a worktree that does not
   exist.** `browser_take_screenshot` refused both my scratchpad path and a
   relative name, with: *"Allowed roots: /tmp/.playwright-mcp,
   /home/xertrov/.llm-general/skills/ud-dreamwork/.worktrees/lane-clientextract"*
   — and that second root is a stale lane directory that is gone (`.worktrees/`
   is empty). So the default output dir errors with `ENOENT` on every call. Cost
   two failed calls plus a staging-and-copy step for all 81 shots. Worth either
   re-pointing the MCP server's `outputDir` at something current, or documenting
   "stage in `/tmp/.playwright-mcp`, copy out afterwards" in the dreamwork
   subagent brief, since every visual lane will hit it.

2. **`browser_take_screenshot` / `browser_navigate` are the wrong granularity
   for a 72-cell sweep.** 12 routes × 6 viewports is 3 MCP calls per cell if
   done with the individual tools. `browser_run_code_unsafe` collapsed that to
   one call, but it is not obvious from the brief that it is the intended tool,
   and its name actively discourages reaching for it. A line in the brief —
   "for multi-route sweeps use `browser_run_code_unsafe`" — would have saved me
   working that out.

3. **The brief listed `/tasks` as a route to inspect and it does not exist.**
   Not costly (30 seconds to confirm the 404), and it turned into finding D3, so
   the net was positive. But it means the route list in the brief was not
   derived from `routeOf`, which is worth knowing for the next lane: the
   authoritative list is `client/router.js:990`.

4. **`watch-design.md` is 260KB / 4104 lines with no index.** It is genuinely
   excellent as a design record and I could not have written D4, D6, D7 or D9
   without it — every one of those is "the page disagrees with a sentence in
   this file". But finding the relevant sentence meant grepping headings and
   reading four ~300-line windows. A 30-line table of contents at the top,
   or a one-line-per-section index, would make it usable as the reference it
   claims to be ("the standing reference for changing the page"). Filing that
   as the concrete ask rather than a complaint.

5. **A methodological trap worth writing into the next visual brief.** My first
   automated overflow sweep reported ~150–300 "past-right" elements on
   `/questions` and `/answers` — all false. They were inside **closed
   `<details>`**, which still report non-zero `getBoundingClientRect()` while
   contributing nothing to layout or scroll. Filtering on
   `Element.checkVisibility()` and confirming with a real
   `window.scrollTo(9999,0)` cut it to the two genuine cases (D1, D2). Anyone
   auditing this page with rect maths will hit the same thing, because the page
   is unusually disclosure-heavy.

Nothing else. The inbox handshake protocol, the coordinator steer mid-task, and
the read-only constraint were all clear and cost nothing.
