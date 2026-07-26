# watch.py — live dreamloop dashboard (design record + styleguide)

Human-authorized 2026-07-25; built the same night in committed increments
(server core → dashboard → status.json → tests → components → questions →
review artifacts → events log → shader → router/transitions → dev overlay
→ review morph → the composer → world-space shader). This is the
authoritative reference for anyone changing the page: the standing design,
plus the token / component / motion / voice styleguide below. The delivery
plan it replaces is in git history (`docs/plans/watch-py.md`); keep this
file current as the page evolves.

## What it is

One stdlib-only file serving a single app shell with four client-routed
views — dashboard, questions, file viewer, review — plus the raw review
artifacts the review view embeds. The dashboard shows dreams (with live
ages), main files, the commits panel (five rows, live ages, maintenance
markers highlighted), migrations
vs target version, roll weights, and `.dreamwork/status.json` (loop writes
it per tick; page degrades gracefully without it). Every view's heading
carries a `+` command opener (steer the loop without a chat turn).

## Standing design decisions

- **Stdlib only, self-contained**; no dependencies, no build step.
- **Loopback by default; trusted LAN only by explicit contract.** The default
  remains `127.0.0.1`. A singular numeric `--bind`, repeatable exact
  `--allow-host`, and navigable allowed `--url-host` may opt into an explicitly
  unauthenticated trusted-LAN socket. Every request validates Host before
  reading target data; browser POSTs validate matching HTTP Origin before body
  read/witnessing. This prevents DNS rebinding and cross-site browser writes,
  not another reachable LAN client. Non-loopback startup says so loudly;
  public/WAN exposure is unsupported. The printed/opened URL Host is always a
  member of the exact allowlist: wildcard binds require `--url-host`; a concrete
  bind defaults to itself only when explicitly allowlisted, otherwise it also
  requires an allowed `--url-host`. IPv6 uses an AF_INET6 server and bracketed
  advertised URL.
- **Read-only, six explicit write exceptions** (all human-authorized under
  loopback or explicit trusted-LAN authority): POST `/answer` appends an answer
  to the matching Open entry in `questions.md`; `/ask` appends a human question
  to `answers.md`; `/comment` appends a human note to an Open or Answered
  question; `/command` appends source-tagged steering to
  `.dreamwork/watch-events.log`; `/tint` persists the project colour in
  `.dreamwork/watch-tint`; `/run-mode` commits the main-dreamer pace into
  `.dreamwork/run-mode` (#290). Answer, ask, comment and command always append
  one line to `watch-events.log`, waking the loop. `/run-mode` dual-writes the
  file and appends **one** events line only when the mode actually changes
  (identical final is silent). Tint deliberately does not wake: it is
  presentation state that cross-window mtime polling propagates, not work for
  an agent. Every other POST is rejected; every other route reads. All file
  access goes through `resolve_confined()` (rejects absolute, `~`, traversal);
  `/filedata` and `/reviewraw` are both behind it.
- **Port** persisted to `.dreamwork/watch-port` (random 3000–63000 once)
  so bookmarks survive restarts; port-in-use error names the port.
- **Live reload**: poll `/mtime` ~2s → re-fetch `/data.json` → re-render
  the active view in place (no transition), including a `/review` question
  dock. The tick uses the router's `buildCurrent` seam rather than a partial
  route list; card drafts, selection, resize, scroll and focus ride the
  existing stable-`data-qid` snapshot, while the artifact iframe browsing
  context stays mounted at its current URL and scroll. Dashboard review
  artifacts are ordered by filesystem mtime newest-first, with ascending
  filename as the deterministic exact-mtime tie-break. The displayed
  age seconds are derived from that same exact nanosecond result, so ordering
  and visible recency cannot disagree. A live mtime reorder keys each stable
  review row by filename and runs it through the existing list FLIP: normal
  motion travels without overshoot, while reduced motion places rows instantly.
  Same-origin artifacts
  additionally permit explicit scroll restoration; cross-origin access is
  caught and treated as opaque, so it never prevents the dock refresh. `dev/capture/noteprop.mjs` proves propagation using
  two separate Chromium processes and a `/questions` control (#271). No websockets. `/mtime` is
  `"<generation> <mtime>"`: a changed *mtime* re-renders the data; a changed
  *generation* (the server was restarted/redeployed, or rebuilt under
  `--autoreload`) triggers a full `location.reload()` so open tabs never go
  stale. The poll tolerates the brief unreachable window during a restart.
- **`--autoreload`** (implied by `--dev`): the server re-execs itself
  (`os.execv`) when its own source mtime changes — edit-and-see with no
  manual restart; the close-on-exec listening socket frees the port and the
  generation bump reloads clients.
- **Single-document router**: `/`, `/questions`, `/answers`, `/file`, and
  `/review` serve one shell. `/answers` is the distinct human-to-dreamer
  question ledger while `/questions` remains dreamer-to-human. The client
  router renders the view; pushState/popstate drive
  the URL. The `#dreambg` canvas is a sibling of `#view` — never unmounted,
  so the background survives navigation. Route changes dissolve through a
  turbulence mist (see Motion language); reduced-motion swaps instantly.
  `/review` embeds the raw artifact (served at `/reviewraw`) in an iframe
  for style isolation; a question linking to it travels along, docked.
- **Events log**: actionable user submissions (answers, questions for the
  dreamer, notes, and commands) append one line to
  `.dreamwork/watch-events.log` so agents can wake on a tail Monitor
  instead of waiting for a tick. **One event per line, and the line is
  something an agent then acts on**, so nothing a human can type into a box
  reaches it unfolded: a submission's newlines collapse to spaces (`one_line`)
  or a typed newline forges a second event — and the agent would act on a
  command he never sent. The general rule, because this is a class and not one
  bug: **anywhere the loop writes human text into a line-oriented file that an
  agent reads back, the text must not be able to forge a record.** Nobody has
  to be malicious for it to bite; a pasted multi-line note does it by accident.
- **`--dev`**: fps, measured per-frame draw time (CPU stopwatch around
  `draw()`; true GPU time via `EXT_disjoint_timer_query_webgl2` when the
  context exposes it), inter-frame avg/worst, and a 120-frame sparkline
  overlay — on every view, zero cost when off.

## Design contract (per web-artisan-core, minimalized)

- Mode: Docs/Refined — a quiet tool page, "terminal readout" not product.
- Thesis: glanceable status; **liveness is the design** — every number
  that can drift without a disk change ticks client-side every second.
- Type: one mono stack, two sizes. Geometry: no cards/borders/pills; dim
  uppercase labels; max-width 72ch. Components: shared `page_shell` +
  `:root` token block + factored JS strings — one system, any redesign.
- Color: near-black bg, two grays, ONE accent (indigo) spent on
  maintenance markers and a nonzero open-questions count.
- Ambient shader background (human-authorized): domain-warped fBm with
  tilt-shift focus and a curl-advection pinch; hue-only per-route tint,
  luminance-capped so text always wins; static under reduced-motion,
  absent without WebGL. The sampling domain is anchored to the window's
  on-screen position at a world-fixed scale, and its phase to the wall
  clock, so every window — including popped-out ones — is a viewport onto
  one continuous, screen-pinned field. Hidden layer switcher: `l`
  (ignored inside text fields) / triple-click bottom-right.
- Single ambient dark theme — intentional exception (overnight
  monitoring tool; human's stated dark preference).

## Styleguide

The standing reference for changing the page. New surfaces conform to this;
if a change needs to break a rule, update the rule here in the same commit.

### Tokens

All colour/space lives in the `:root` block in `STYLE` — edit tokens, never
hardcode. `--bg` near-black; `--panel`/`--panel2` raised fills; `--line`
hairlines, `--border` stronger edges; a text ramp `--text` → `--lit` →
`--bright` (up, brighter) and `--muted` → `--dim` → `--dimmer` (down,
quieter); `--accent` indigo. `--space` (section rhythm),
`--radius`. The accent is scarce on purpose — spent only on live/actionable
things (maintenance markers, a nonzero open-questions count, links, the
active command opener). If everything is accented, nothing is.

**There is a second colour, `--warn` amber, and it means BROKEN rather than
live** (#136). It was one accent until then, and the rule is broken on
purpose: the page's only loud colour said "this is happening", so a failure
rendered in it read as activity — and the one thing that must never read as
activity is the human's channel to the loop having stopped working. Its uses
are enumerable and must stay that way: a `questions.md` the reader cannot see,
and a send the server refused. Both are the same fact — the channel failed and
no number on the page would have said so. Nothing that is merely *important*
gets it; if a third use appears, the question to ask is whether it is really
this one.

### Type & geometry

One mono stack, two sizes (heading `1rem`, body `.8rem`, labels `.7rem`).
No cards, borders-as-decoration, pills, or shadows in the reading views —
structure comes from whitespace and dim uppercase labels (`.label`, letter-
spaced). Reading column is `max-width:72ch`, centred; the review view is the
one deliberate exception (`body.review` widens the column for the artifact +
docked question). Dividers are hairlines (`--line`), not boxes.

### Review artifacts

Artifacts under `.dreamwork/review/` are standalone documents, but they
are read inside this dashboard — so they carry the same `:root` tokens,
the same mono stack, and the same restraint. Inline everything (no
fetches; a strict reading of "offline-clean").

An artifact is a separate document, so page-level chrome does not reach
it: it carries its own scrollbar rules (the same hairline track and
`--dimmer` thumb the shell uses) or it shows the browser's default
inside our iframe. Same for any popped-out window.

Two idioms, both endorsed by the human (2026-07-25, on the
goal-hierarchies artifact — *"the diagram here is really nice, we should
be sure to remember it"*):

- **Diagrams are inline SVG in the token palette**, not images and not
  ASCII. Nested boxes indented by depth, hairline arrows between them,
  `--accent` reserved for the one row that is the point.
- **Label the columns, not the gaps.** Every row states its own two
  facts side by side under a header pair (`DEPTH` / `LIVES IN`) — a
  label floating between two rows attaches itself to the wrong one, and
  a reader will not notice they have learned it backwards. Found by
  looking at the render; the markup read fine.

A decision artifact shows each option beside its alternative rather than
only the recommendation: the human is being asked to decide, not to
ratify.

### Components (idioms)

Everything renders through shared factories so a redesign is one edit, not a
hunt: `page_shell` (the one HTML shell + `<script>` bundle); `pageHeader`
(every heading, with the `+` opener in the left gutter); `label`, `expand`
(`<details>`), `preB`/`linkify` (backticked repo paths become `/file`
links; a `.dreamwork/review/*.html` path becomes a `/review` link that docks
its question), `qaCard` (**the question card** — its own section below). A
low-emphasis PiP glyph (`pipBtn`) sits after doc/review affordances
(file + review headers, the dashboard reviews list, the composer); clicking it
floats the target in an identity-headed window (`openPopout` → Document
Picture-in-Picture, `window.open` fallback) that stays put while the main tab
navigates and carries the same dreaming field (see Shader). Views are pure builders returning `#view`'s innerHTML
(`buildDashboard`, `buildQuestions`, `buildAnswers`, `buildFile`,
`buildReview`); the router swaps them. `answerRecord` is deliberately not
`qaCard`: its Open author is the human, it has no human answer/comment controls,
and Answered records are quiet disclosures. The compact ask form clears only
after a confirmed `/ask` success; refused/unreachable sends keep the words and
explain the outcome. Its value, caret, resize, scroll and focus ride live
`/mtime` renders through `snapshotAskState`/`restoreAskState`. **Ctrl/Cmd+Enter
from `#askbox` submits the ask form (#292)** — the same shortcut the composer
and question cards already honour; empty boxes do not POST. **One in-flight
`/ask` at a time:** while a POST is pending, further submit/Ctrl+Enter is a
no-op (no second request with the same bytes). A generation counter means a
late response cannot clear a newer draft; failure keeps his words; only the
matching successful generation clears the box. **Leaving `/answers` destroys
the surface:** `invalidateAskFlight` so a rebuilt form is never stuck blocked,
and a late success cannot clear/status/`tick` the new form. **Open records must not bake a
permanent `.dreamin` into the HTML (#293).** That class is only the enter-snap
start pose. New open rows (keyed by server `aid` on `data-aqid` — title+body+
ordinal, never title alone) receive a one-shot arrival after `setContent` via
`revealNewOpenAsks`: commit `.dreamin`, then remove it on the next frame so
the standing transition eases them in. First paint of the answers view and
hard refresh settle fully visible without replaying a stuck pose. Reduced
motion leaves new rows fully lit (function, no start pose). Settled open rows
use `.aq.open .qt` at `--lit` and body at `--muted`. Answered disclosures
inherit the shared transition/reduced-motion rules in `transitions.md`.
**What he opened on an answered record survives the tick (#238)** the same way a
section does:
each answered `<details>` carries a content-stable `aid` from
`parse_answered_answers` (SHA-256 over title, resolution `when`, body,
`follows`, plus a 0-based occurrence ordinal among exact-content twins) on
both `data-aid` (list FLIP) and `data-keep` (the existing
`snapshotFolds`/`restoreFolds` seam — **re-open only**, never close). Not
positional `a+i` and not title alone: duplicate titles, reorder, and deletion
of another record must keep open on the same logical body. A body edit may
fail to restore (prefer miss over opening the wrong record). No third
snapshot path. `dev/capture/answers.mjs` proves node replacement plus the
three identity cases.

**Missing `aid` fails closed (#247).** If the server entry has no `aid`,
`answerRecord` emits a plain `<details class="aq answered">` with **neither**
`data-aid` nor `data-keep`. Empty attributes collide (every missing record
shares `""` as a fold/FLIP key and can re-open the wrong disclosure). A
shared sentinel such as `ans:missing` collides the same way. Prefer closed
over wrong-record open. **Human click still folds (#250):** the expand
handler's keyed host is `.aq.answered[data-aid]`; without an aid, `preventDefault`
would leave the native toggle dead. Missing-aid details use a listless local
fold (`foldDetailsLocal` — same travel/reveal/ghost pieces as the section
fold) for that click only. Open does **not** ride the tick (no `data-keep`).

**Exact-content twins and deletion (#247).** The ordinal is file-order among
*currently* equal twins. Deleting an earlier twin renumbers later ones, so a
survivor's `aid` changes and open restore fails closed — it must not migrate
onto a different body. Distinct bodies keep stable aids across deletion of a
peer (the browser guard asserts preAid, marker replacement, and same-aid on
the survivor).

Add a view by adding a builder + a `routeOf`/`TINT`/`SEED`
entry, not new chrome.

**`expand` is structure; HOW it moves is `transitions.md`'s, not this
file's.** A `<details>` that changes the page's layout travels: the card's own
`.qfold` (#111), its settled follow-up thread (#128), and the dashboard's
questions section (#141, since #196). The structural half — the part that
belongs here — is that the card handler is written against
`.qa details > summary` rather than against `.qfold`, so the next disclosure
someone adds to a card is covered without anyone remembering this paragraph.

**This paragraph used to argue the opposite about the questions section, and
the correction stays visible because the reasoning is the reusable part.** It
called that section a standalone expand with "nothing to disturb", because it
contains *all* the cards, so "nothing that moves is left below the toggle".
Reviews, files, status and the tint picker are all below that toggle, the
section swings by ~1250px, and his report was that the questions "just appear
and disappear". A justification that is checkable and false gets believed —
this one was, for the whole life of #141. The plain `expand()` peeks are still
instant and the same test would now say they should not be; `transitions.md`
records that as unexamined rather than decided.

### More detail: what expands, what navigates, what hovers

DREAMWORK.md commits the loop to *detail is ranked, never withheld* — "in
general we always want to present the user with more details if there are
more details and users might want them" (human, 2026-07-25). That says a
thing that exists must be reachable. It does not say **how**, and this page
has three answers, which #166 made worth writing down because a commit row
could plausibly have taken any of them.

- **Expand** when the detail is *about the thing he is looking at* and wants
  to stay in its place in the list. He keeps the row's neighbours, its
  position, and everything around it; the page's subject does not change.
  A folded question (#111), its settled thread (#128), the questions section
  (#141), a commit's body (#166).
- **Navigate** when the detail *is its own subject* — a review artifact, a
  file, the questions page. It earns the page's heading, the persistent
  chrome, and above all a **URL**, which is the only form of detail he can
  reload, bookmark or paste to somebody. Choosing expand for one of these
  would trap it inside a page it cannot be linked to.
- **Hover (a `title`)** when the detail is a complete list that would change
  the layout to hold it and is wanted for one second: the commits missing
  from a stale dashboard (#140), a truncated preview. This is the weakest of
  the three — it is invisible on a touch screen and to a keyboard — so it is
  for detail that is *already summarised accurately* by what is on screen,
  never for the only copy of something.

Two corollaries the page already obeys. **A fold is a promise**: the summary
says what is inside (`questions · 2 to answer · 1 awaiting fold`), so a
collapsed panel never hides the fact that something is in flight. And
**nothing is dropped, only demoted** (#130) — the status panel folds
*whatever is left* rather than a second known list, because a reader that
cannot see something renders identically to there being nothing to see.

**And whatever it does, an expanded element becomes PROMINENT rather than
merely taller** (#169). His words: expanding should grow padding above and
below, so the thing he opened reads as foregrounded. Expanding is a change in
**importance**, not a reveal — what he opened is now the subject of the page —
so it is an idiom, and every disclosure inherits it by existing. Two channels,
both the page's own vocabulary:

- **Air.** `details[open]` claims `.5rem` above and below. On a page with no
  cards, borders or fills, whitespace *is* the structural device, so claiming
  space is what being foregrounded looks like here. It costs the summary an 8px
  shift under his pointer on the click that opens it — that is what "air above"
  means, and it is the half he asked for by name.
- **Luminance.** The summary steps one place **up** the text ramp, because
  emphasis on this page is luminance (the same rule as `**bold**`). **Never
  `font-weight`**: a mono face steps rather than transitions, and re-metricing
  the summary would move the very thing being opened. A folded card's contents
  step up with its title, because brightening a title over unchanged prose says
  the title got more important rather than the entry did.

**The step is stated per surface, one line each — the generic thing is the
RULE, not the value.** These sit at four different brightnesses when closed, on
purpose (a settled thread at `--dim`, a folded card's title at `--muted`), so a
single bright colour for every open summary would drag all of them to one
brightness. That is exactly the shape that overruled `.sgbtn` (#121) and leaked
into `.qfield textarea` (#139). The one deliberate non-step is `.qsec`'s zero
state: `.none` outranks `details[open] > summary`, so a section with nothing to
answer stays dim even while he is looking inside it — disabled means "nothing
here needs you", and opening it does not change that (#141).

**The padding does not transition, and that is what keeps this ONE gesture.** A
card-nested disclosure measures its new rect immediately after `det.open`
flips, so the growth has to be in the layout by then; the *card's* height
travel is what animates it, carrying every card below for free. A padding
transition hands `regroupCards` a start-of-transition rect, the FLIP plays to a
height the card never reaches, and the difference **snaps** when the inline
height is cleared. `dev/capture/prominence.mjs` is built around that: it
asserts the neighbour has **arrived when its travel ends**, not merely that it
arrives — which it does either way, which is why every end-state check and
every "did it travel" check is blind to this. Injected, the padding transition
leaves it **20px** short at 950ms and trips that one check and nothing else.

Two consequences of routing a nested expand through the shared path, both of
which were wrong first:

- **What arrives is the disclosure's contents, not the card's.** The body, the
  answer and the compose box were on screen before and after, so re-fading
  them says a change happened where none did. `cardBody(el, toggled)` takes
  the toggle that caused the resize and reveals *its* children; handed the
  card's own `.qfold` it is exactly what it always was.
- **What leaves is ghosted at its own rect.** The card-level clone is clipped
  to below the survivor's new height, which is right for a card folding (the
  body leaves from the bottom) and wrong for a thread (it sits above the
  compose box, so what disappears is a middle band and the clip would ghost
  the box that never left). A closed `<details>` still holds its children in
  the DOM but gives them no geometry, so the rect is measured *before* the
  toggle and `ghostNode` dreams them away on the same departure idiom.

### Anything the human has changed on the page must survive ANY re-render

Promoted to a rule at its third instance, which is where this page promotes
things — and then broken a fourth time anyway, which is why it now says *any
re-render* rather than *the tick*:

- **#118** — text he was typing, destroyed by the tick's `innerHTML` swap;
- **#111** — an entry he had expanded, re-collapsed by the same swap;
- **#141** — a section he had folded, same again, two seconds later;
- **#179** — the **focus** taken out of the box he was typing in, on every
  re-render of the dashboard.

Each was found by hitting it, and each was fixed locally. A fifth feature
carrying human-controllable state will hit it a fifth time unless the rule
sits where the next builder meets it.

**The list re-renders through `innerHTML`, so any state HE owns — text he is
typing, where his caret is, a card he expanded, a section he folded — is
destroyed unless it is snapshotted before the swap and restored after, keyed
by something stable.** *Any* re-render: **a new render path states how it
satisfies this rule**, and "the tick already handles it" is not that
statement — a path that re-renders on a different trigger runs the same
`innerHTML` swap and owes the same answer.

**#179 is what that scoping costs, and it is worth reading before adding a
path.** The rule above was written for the tick and the guard for it
(`typing.mjs`) only ever visited `/questions`. On the **dashboard** every
card lives inside `.qsec`, the fold #141 added — so the fresh render arrives
with the section shut, and `focus()` on an element inside a closed
`<details>` **does nothing and reports nothing**. The box came back filled,
with his caret in the right place, and dead. Two things follow:

- **The two snapshot seams are ordered by what NESTS, not only by what
  measures.** `restoreFolds` must run before `restoreCardState`, because a
  card's restore puts the caret back and the container has to be open for
  that to mean anything; both still run before the regroups, which measure.
- **An ordering constraint fixes the instance; the class needs the restore to
  check that it landed.** `refocus()` focuses, asks whether
  `document.activeElement` actually changed, and if it did not, re-opens
  every `<details>` above the box and tries once more. That is safe by
  construction — he could only have been typing in a box whose ancestors
  were open — and it is the same "only ever re-open, never close" rule the
  restores already obey. The next container someone wraps this list in gets
  the focus back without knowing about any of this.

The reported trigger is worth naming too, because it is a red herring that
would have sent the fix to the wrong layer: he saw it *"when the git log at
the top cycled"*, and #151 had landed that day. The commits panel is
innocent — it is simply the one thing on the dashboard whose re-render he
can SEE, so it is what he noticed. The check therefore fires on a **plain
tick** as well as on a new commit, and both are in `motion.mjs`.
Liveness is not negotiable and never waits on this: the new DOM is committed
immediately, exactly as it always was. What is carried across is only the
state that exists **nowhere else** — nothing on disk can reconstruct it.

**Restore must only ever RE-OPEN or RE-FILL, never close or clear.** That
half is what makes a stale or wrong snapshot harmless *by construction*: the
fresh render is the default and what he did to it is the addition, so the
worst a bad snapshot can do is fail to give something back — never take
something away. It is the same move as `human_block()` (make the bad input
unrepresentable) and the status panel's fold-by-complement (demote what you
do not recognise, never drop it). **When his state is involved, prefer the
failure that loses nothing.**

Two seams exist; extend one rather than adding a third.
`snapshotCardState`/`restoreCardState` carries a card's text, caret, focus,
scroll, box height, destination mode and every `<details>` inside it (#118,
#111), keyed by `data-qid`. `snapshotFolds`/`restoreFolds` carries a section's
`open`, keyed by `data-keep` (#141) — a new section opts in by carrying the
attribute. Answered disclosures on `/answers` opt in the same way (#238), with
`data-keep` equal to their content-stable `aid` (not list index). Both run
**before** the regroups, which measure, and **folds run before cards** (#179,
above).

### The persistent chrome

The heading is not content. It is the page's frame — the same `+` opener, a
title, and a crumb row, on every route — and it lives in the shell as a
**sibling of `#view`**, the standing `#dreambg` already has. While it lived
*inside* `#view` it dissolved and was rebuilt on every navigation, which is
why a route change read as "the elements jump around" rather than as the page
opening up (human, 2026-07-25). View builders return their body only; a new
view adds a `TITLES` entry and a `crumbsFor` branch, not a heading.

**Crumbs are keyed** (`data-k`), and that is the whole trick: a survivor must
be *literally the same element* before and after, or a FLIP has nothing to
measure and you get a fade where a glide was asked for. `home` is one crumb
across three routes even though its text gains and loses an arrow. Departing
crumbs are lifted out of flow at the rect they occupied — so survivors can
close the gap underneath them — and dream away in place on the mist idiom;
arrivals SNAP to their start state (`.dreamin`) before easing in.

The separator belongs to the crumb that **follows**, so a departing crumb
takes no punctuation with it. It is written with non-breaking spaces: an
inline-block collapses the leading and trailing whitespace of generated
content, and `content:" · "` renders flush against its neighbour.

**The column travels.** `/review` is the styleguide's one width exception,
and changing width is a layout change, so it glides (`body.wsliding`) on the
dissolve's own easing rather than snapping. Two consequences that are not
optional:

- **The departing ghost is pinned** to the box it was rendered in (top,
  width, height, measured before the class flip). It is *leaving*: it must
  not re-wrap every paragraph into a new column while still fully opaque.
  That reflow, at frame 0 and at full opacity, *was* the reported jump.
- **`body.wsliding` clips `overflow-x`**, because a ghost pinned to the wider
  old column would otherwise push a horizontal scrollbar as the column
  narrows underneath it.

`.wsliding` is added only for a route change, so a direct load of `/review`
arrives already wide instead of animating its column on first paint.

**The opener clamps, it does not track.** The `+` hangs in the gutter left of
the column, and the gutter does not exist on the review view or in a narrow
window — the button was sliced in half by the page edge. The pull is clamped
to the room that actually exists, in **CSS**:

```css
margin-left: calc(-1 * clamp(0px, (100vw - 100%) / 2 - .6rem, 2.4rem));
```

`100%` is the containing block's width — `.htitlebar`'s, which is the
column's — so `(100vw - 100%)/2` *is* the gutter, without naming a column
that is sized in `ch` (and `ch` would resolve against the button's own font,
not the column's). CSS rather than a measure-then-write in rAF is what makes
the guarantee hold on **every frame**: the column glides, and JS would always
paint one frame behind it. At the tightest column the button parks flush,
still inset by the body padding.

**The opener and the heading text share one centreline** (#123). The opener is
the tallest item in `.htitlebar`, so it defines the flex line's cross-size —
which meant that under `align-items:baseline` the title hung from its own
baseline near the top of that line while the button, at full line height, sat
**3.1px lower** through the middle, on every route. `align-items:center`
centres both boxes in the line and the offset measures 0.00px everywhere. The
remaining ~1px between the button and the text's *ink* centre is the font's
own ascender/descender asymmetry and is deliberately not chased: a magic nudge
would be wrong the moment the mono stack falls back. Being a CSS invariant
rather than a JS measurement is what makes it hold while the header travels.

`dev/capture/headertravel.mjs` traces all of this per frame, in both
directions, plus reduced motion, plus every route at four window widths. Each
check was shown to fail on its own deliberately-reintroduced bug — the
unclamped opener measures **-22px**, i.e. off-screen. Note the ghost is
measured with `offsetWidth`, not `getBoundingClientRect()`: the dissolve
lifts it with `scale(1.07)`, and only layout width answers "did it re-wrap".

### Prose rendering

Everything the loop writes to disk is hard-wrapped at about 72 columns. A
`<pre>` renders those breaks literally and the browser then re-wraps them
inside a narrower card, so every paragraph breaks twice and reads as a
ragged mess (human, 2026-07-25, with a screenshot). So prose is **reflowed**:
wrapped lines are joined and the reading column does the wrapping.

**The line: markdown prose reflows, raw text does not — by what the file
is, not who wrote it (#158).** Question bodies, answers, follow-up notes,
dreams, and the dashboard's `.md` peeks go through `mdB` / `mdBReview`.
`/file` used to treat every path as raw source (#102 drew the line at who
composed the text); that made research docs and notes unreadable at the
reading column. The useful line is the extension: **`.md` / `.markdown` /
`.mdx` at `/file` reflow through the same `mdB`**, and everything else at
`/file` stays verbatim in a `<pre>` (source code must not reflow — human,
2026-07-25 15:23). Path-based, never content-sniffed: a `#` in a `.py`
comment is not a heading. Two things have left the prose list for a different
reason, neither of them markdown: `status.json` (#130) and the git tail
(#132) are sets of *facts*, not text he reads literally, and each now has a
component of its own (below). JSON at `/file` is still neither prose nor a
toggle yet (#178).

Four things survive the join, because each carries meaning a joined line
would destroy: a **blank line** is a paragraph break; a leading **`- `** is a
real list item and its **indent is its nesting**; a **``` fence** is code;
a **`#` heading** stands alone. Nesting is the *rank* of a bullet's indent
among the indents actually present, not its column count — a question body
arrives carrying the source file's own 2-space indent, and absolute columns
would push every sub-bullet a level too deep.

**Inline emphasis is luminance, not weight.** `**bold**` renders as
`--bright` at the same weight; the page already says "more important" with
its text ramp, and a mono bold would change metrics to say no more. `*em*`
is italic, `` `code` `` gets `--lit` on a `--panel` ground (a reading aid for
paths and identifiers, not a badge). Order in `mdSpans` is load-bearing: the
linkifiers inject `<a>` *inside* the backticks, so code spans convert after
them and swallow the link; `**` resolves before `*` so a bold pair is never
read as two emphases.

The parser feeds this: a sub-bullet may itself be hard-wrapped, and its
continuation lines belong to *it*. Capturing only the first line truncated
the note mid-phrase **and** spilled its tail into the body as orphaned prose
(that pair of symptoms was #106 — reported as a "confusing cut-off preview",
which is what data truncation looks like from the outside). Any line that
starts a new bullet ends the capture, so an unrecognised sub-bullet — an
in-session follow-up, say — can never be glued onto the one above it.

`dev/capture/reflow.mjs` measures this rather than eyeballing it. Range
`getClientRects()` returns one rect per inline *box*, so rects are grouped by
top edge into real line boxes first. The decisive check is an A/B: every live
question body rendered *both* ways at the same width, swept across widths.
The win peaks in the middle of the sweep — at a very narrow column both
renderers are ink-limited, and at a wide one the source's own 72 columns
nearly fit; it is the widths a card actually gets where a `<pre>` wraps every
line a second time.

### Authorship

**Anywhere the human's words appear beside the loop's, authorship is
visible.** A page that mixes them will eventually mislead one of them — and
the loop is the one that would then act on its own invention as if it were an
instruction. This is a correctness rule, not a decoration one.

The file carries it: a note is tagged with its **author**, not just its
channel. `- **Note (human, via <channel>, <ts>):**` and
`- **Follow-up (loop, <ts>):**` are current; two legacy forms
(`Follow-up (via watch…)` → human, `Follow-up (in-session…)` → loop) keep
parsing forever, because the file is a record and is never rewritten. An
unrecognised tag renders with **no attribution at all** — a wrong
attribution is worse than an absent one, so `note_author` returns `None`
rather than guessing.

The page says it quietly: a dim uppercase label (`you` / `loop`, the same
label idiom as every other label here) and the human's words one step up the
text ramp (`--lit` against the loop's `--muted`), because emphasis on this
page is luminance. An answer reads at that same brightness — it is his, in a
card whose body the loop wrote. **No accent**: the accent is for live and
actionable things, and a settled note is neither.

**And it says it about the answer too** (#128). An answer read at his
brightness but carried no label, so on a card holding a note and an answer —
both his — only the note said whose it was, and the answer read as somebody
else's remark he was replying to. Attribution that is *sometimes* present is
worse than none: the reader learns to treat its absence as meaningful. So the
answer carries the same `you` label from the same table, derived from its tag
(`ANSWER_TAGS`) rather than assumed, and an answer tag nobody recognises gets
no label — `answer_author` returns `None` for the same reason `note_author`
does.

**Each contribution states when it was written** (`.qts`, a step below the
author label). Order is what carries chronology; the stamp is what settles it
when the order is the thing in doubt. Rendered verbatim from the tag, and
absent when the tag carried none.

### Reading questions.md

`_parse_entries` is the single reader for both sections — they were
near-duplicates, and the last two bugs each had to be fixed twice before
that. Four invariants, each of which was a bug:

1. **A top-level `- **` line ALWAYS starts an entry.** Nothing absorbs it —
   not an unterminated title, not an open sub-bullet — so an entry can never
   silently vanish into the one above it.
2. **A title may be hard-wrapped**, closing at its `**` wherever that falls,
   possibly lines later. The loop writes this file at ~72 columns, so a
   wrapped title is normal input, not malformed. Cutting it at the first
   line break truncated the title and leaked its tail into the body as
   literal asterisks (#116).
3. **A sub-bullet may be hard-wrapped too**, and its continuation lines
   belong to it. Keeping only the first line truncated the note *and*
   spilled its tail into the body (#106).
4. **An Answer or Note sub-bullet is never an entry**, even un-indented.
5. **Chronology survives the read** (#128). A sub-bullet's tag head carries
   when it was written, and lifting the answer out of the sequence discards
   where it sat — so both are kept: `when` on every note, `answer_when` and
   `answer_at` on the entry. Without them the parse of an entry was
   **byte-identical whichever order its sub-bullets were written in**, which
   is the sharp form of the diagnosis: the render was not mis-ordering the
   notes, it had no order to respect, and no rendering fix could have reached
   it. `sub_when` is anchored to the tag's closing `)`, so a date inside the
   note's own text is somebody else's date, and it returns `None` rather than
   guessing — the same rule as `note_author` and `answered_at`.

**Order is decided here too, once** (#197). An entry's title may open with
`P1 · `, `P2 · ` or `P3 · `; `parse_open_questions` sorts by that, and
**absent means P2** — the middle band, which is what makes an explicit `P3`
sort genuinely below an unmarked entry rather than level with it. The marker
stays part of the title, so it renders: he reads the priority on the card
rather than only inferring it from the order.

- **It is a property of the parse, not of a renderer.** Three surfaces show
  these entries — the dashboard's questions section, `/questions`, and the
  review dock — and all three go through `qaCard`. A sort in each is three
  chances to disagree about which question is most urgent, on the one channel
  whose whole job is telling him what to look at first. It also keeps
  `data-qkey` honest: the key is an *index into this list*, so the list the
  client is handed has to be the list it renders.
- **"Oldest first on a tie" is free, and must stay free.** The file is
  chronological and Python's sort is stable, so priority alone produces it.
  Adding a date comparison would be a second mechanism able to disagree with
  the first — and it would disagree exactly on the entries whose stamps are
  missing or hand-edited.
- **A marker outside the band reads as unmarked**, and `lint.py` errors on
  it. That is the quiet failure: it reads to a human as prioritised and sorts
  as unmarked, so the entry he most wants seen sits mid-list looking urgent.
- **`## Answered` is deliberately not sorted.** A priority says how urgently
  something needs him and a settled entry needs him for nothing, so sorting
  those would order a record by an urgency that has expired — and scramble
  the one property that section is read for. It carries no `priority` field
  either: a key nobody sorts by is a claim that something does.
- **A live reorder travels.** A new `P1` arriving pushes every card below it
  down, and that rides the tick's existing regroup for free because
  `data-qid` is the question's own title, which reordering does not change.
  The guard is `dev/capture/qorder.mjs`.

**The writer walks titles the same way, through the same `_join_title`.**
Before that, `append_subbullet` compared against the first source line only,
so a wrapped-title entry could not be matched at all and `/answer` and
`/comment` failed silently on an entry plainly on screen. A silent write
failure on the human's own input channel is worse than the visible symptom
that leads you to it — whenever the reader learns a new way to name something,
check the writer still finds it by that name.

**And the writer must make sure his words cannot BE one of those things**
(#146). `/answer` and `/comment` put text he typed — and pastes into —
straight in this file. Written at column 0, a pasted `- **…**` is a top-level
entry by invariant 1, so the loop reads a question he never asked with a body
the paste invented, in the file it treats as the record of what he wants. The
invariant is right and stays; `human_block()` is where this is handled, and it
gives two guarantees:

- **every continuation line is indented**, so it can open neither an entry
  (`- **`) nor a section (`## `) — the reader tests both on the *raw* line;
- **no continuation line begins a bullet**, which the reader tests on the
  *stripped* line. That one is easy to miss and nearly as bad: a bullet ends
  the note's capture, so the rest of his words fall into the entry's **body**
  and render as prose the loop is assumed to have written — losing his
  attribution, which #109 makes a correctness rule rather than a decoration
  one. A line that would begin one is joined onto the line above; that
  terminates, because every join removes a line.

Folding his text to one paragraph first costs nothing anyone can see: the
reader already joins a sub-bullet's continuation lines back into one string,
so a note has always been one string by the time it renders. The wrapping is
for whoever opens the file in an editor. The guard is a pytest that
round-trips a deliberately hostile note through `append_comment` → `parse`
and **counts the entries** — count, because this is a file whose structure is
data, and a glance at a structural change is how two records get merged.

### The question card

A question is the page's one interactive object, and it appears on four
surfaces — the dashboard, `/questions`, the review dock, and the card the
submit morph restates in place. All four go through **one** component, so a
change to how a question looks is one edit rather than a hunt.

**Contract: `qaCard(q, key)`.**

- **The key addresses the entry**, it does not describe it: `'o'+index` into
  `questions_open`, `'a'+index` into `answered_entries`. `qaEntry(key)` is
  the single place a key becomes an entry, for reads and writes alike. A
  title round-tripped through the DOM is never the address — a stale render
  must not be able to write to the wrong entry.
- **The three states are one axis: who is the entry waiting on?** `open` is
  waiting on the **human**, `awaiting` on the **loop**, `folded` on
  **nobody** — and everything about their treatment follows from that one
  question rather than being three separate skins. Liveness descends along
  it: open is fully lit and carries the answer box; awaiting is a step down
  the ramp but wears the accent rail, a `✓`, and the breathing wisp, because
  it is the one thing on the page still in flight; folded is the dim end,
  collapsed, and carries **no accent at all** — the accent is for live and
  actionable things and a settled entry is neither.
- **The state is derived, never passed.** `qaState(q, key)` returns
  `open` (shows an answer box), `awaiting` (answered from the page, the loop
  hasn't folded it — the answer on a quiet accent rail with a `✓` and no box,
  so it never reads as still-open), or `folded` (key is `a…`; the loop has
  filed it into `## Answered`). Deriving it means no caller can render an
  entry in a state its own data contradicts.
- **The states are class modifiers on one card** (`.qa.open` / `.qa.awaiting`
  / `.qa.folded`, plus `data-qkey`), so shared styling is written once and
  only the differences are stated. A state that needs its own element tree is
  a signal the state is really a different component — **with one deliberate
  exception**: `folded` wraps the card's contents in the page's standing
  `expand` idiom (`<details class="qfold">`), because for that state
  collapsing *is* the treatment (#111). Its title line **becomes** the
  `<summary>` rather than sitting beside one, so `.qt` still names the
  question line in every state and every rule written against it keeps
  applying. **Awaiting does not collapse** — it still needs the loop, so it
  stays visible.
- **A collapsed entry stays findable**: the summary carries the question line
  and `answered <when>`, read server-side by `answered_at()` from the
  `→ <verdict> (<ts>):` head the loop writes. Anchored at the body's start so
  it can only ever read the resolution, and it returns `None` rather than
  guessing — the same rule as `note_author`, for the same reason.
- **`qaInner` is split out from the card** purely so the answer-submit morph
  can restate a *live* card in its new state without assembling look-alike
  markup. Any future in-place state change uses the same seam.

**The thread is cut at its resolution** (#128). His words, on an
awaiting-fold entry: *"the first thing that showed up was like me replying to
me? ... if we have a thread of notes like that, they should be collapsed but
also expandable."* The answer is lifted out of the sub-bullets so the card can
show it as the resolution, and the lift used to throw away its place in the
sequence — so a note he wrote at 08:51 rendered underneath an answer he wrote
at 10:47, tagged `you` while the answer was tagged nothing. `qaThread` cuts
`follows` at `answer_at`: the discussion that led to the resolution sits above
it, an amendment sits below.

- **Only the part above collapses**, and that is the card's own axis applied
  one level down. Discussion a resolution has already answered is settled;
  everything else on a question card is still live. So an **unanswered**
  question never hides its notes — they are his own steers — and a note he
  adds now lands in the segment *below* the answer, which is never folded away
  under him. Defaulting the cut to the end of the list when there is no answer
  is the obvious-looking arithmetic and it sweeps every open question's notes
  into the folding half; the guard caught it.
- **The threshold is two** (`QTHREAD_FOLD_AT`). One note is not a thread:
  hiding a single line behind a click costs more than it saves, and his own
  reported entry had exactly one — for it, the ordering fix *is* the whole
  fix. Do not simplify this to always-collapse.
- **The notes sit in a `.threadin` wrapper** inside the disclosure, so what
  arrives or leaves on a toggle is one node with one rect. That is what
  `cardBody` reveals and what the collapse ghosts.
- A live-appended note goes to the **last** `.threadin`, because what he just
  wrote is the newest thing in the thread — appending to the first would drop
  it above an answer written hours earlier, which is the bug the split exists
  to prevent.

`dev/capture/thread.mjs` guards it, and one of its checks is worth knowing
about: **a closed `<details>` does not give its children `display:none` in
current Chromium** — it skips them with `content-visibility`, so their rects
survive from the last layout and a geometry test for "is it hidden" passes on
collapsed content. Ask `checkVisibility()` instead.

Every state carries the follow-up thread and **one input** (`qaCompose`).
The human's words: *"use same text input for answer and note. below text
input, have a button group choose between [ Answer | Add Note ]. on the RHS
of the text field, integrate a 'send' button that sits flush with the text
field so they appear to be one thing."*

- **Field and send are one object.** The `.qfield` wrapper carries the
  border, the radius, and `overflow:hidden`; the textarea has no border and no
  **margin** of its own, and both it and the button fill the wrapper edge to
  edge. Two controls side by side would read as two controls — and so does one
  object whose halves are inset differently, which is what a leftover
  `.qa textarea` catch-all quietly made of it (#139).
- **The mode picks the endpoint** (`/answer` vs `/comment`) and nothing else
  — the typed text, the submit morph, Ctrl/Cmd+Enter and the ~1.6s
  `holdRerenderUntil` guard are identical either way. The mode group is the
  shared sliding group, not a second implementation of one.
- **Only offer modes the state can accept.** `/answer` appends into the Open
  section, so a **folded** entry is note-only and the group is not rendered
  at all — a choice that would fail is better absent than validated. An
  **awaiting** entry defaults to note: answering again is an amendment, not
  the obvious act.
- The placeholder follows the mode; the typed text does not, because the
  text is the point and the mode is only where it goes.

**What the human did to a card survives a tick.** The list is re-rendered
through `innerHTML`, so every card node is replaced roughly every 2s — and
with it whatever is half-typed, and whichever disclosure he had just opened up
to read (the folded entry, or a settled thread — the snapshot records *every*
`<details>` in the card, positionally, and only ever re-opens: the fresh render
is the default and what he did to it is the addition). Liveness is not negotiable (the tick has always committed its new
DOM immediately), so the fix is not to suppress the render but to carry
across it the state that exists **nowhere else**: the text, the caret, the
focus, the scroll and resize of the box, the **mode**, and the disclosure's
`open`. Keyed by `data-qid` for the same reason the regroup is — answering
re-indexes the entry, so a positional key would drop the text at the exact
moment the card moves. `snapshotCardState` / `restoreCardState` is the one
seam for this; anything else the human can do to a card in place joins it
rather than growing a second mechanism.

The mode is the one that is a correctness rule rather than a comfort: it
decides *which endpoint the text is sent to*, so silently reverting it to the
card's default would redirect his words. `setCardMode` is the single
implementation shared by the mode buttons and the restore, and it **declines
a mode the new state cannot accept** — a folded entry is note-only, so a
carried-over `answer` falls back to what the card rendered rather than arming
a send that would fail. The restore lands the indicator (`snap`) rather than
sliding it: the DOM is fresh, so this is the enter-snap rule again.

`dev/capture/typing.mjs` guards it, and its load-bearing assertion is that
**the card node was actually replaced** — without that, a tick that did not
happen would satisfy every other check in the file. It forces two real ticks:
a quiet one (`POST /command`, the common case — the loop writing its own
files, questions unchanged) and one where the list content genuinely changed
underneath him (`POST /comment` on another entry, which also runs the
regroup).

The Answered section is rendered structured from `answered_entries`, not raw
text. The questions/dashboard views group cards by state with their own
counts — grouping is the view's job, rendering is the card's.

`dev/capture/qacard.mjs` guards this by *structural* comparison: it asserts
the dashboard's and the review dock's cards have the same tag path and class
vocabulary as `/questions`'s, which is exactly what a quiet fork would lose.

### The questions channel's health

"Nothing needs you" and "the loop's channel to you is broken" produce the same
number — and for one morning they produced the same page: a dashboard reading
zero open questions over a `questions.md` holding six, four of them genuinely
open, because the loop had written its questions as `##` headings and the
reader saw none of them (#135, #136). The count cannot tell those apart, so the
count is no longer the only thing that speaks. `questions_health` says *which*
zero this is, and the page treats the three differently:

| state | when | treatment |
|---|---|---|
| `missing` | no file | one dim line. A fresh target has not failed at anything — the loop writes the file the first time it needs him, and init seeds it. His call. |
| `unreadable` | content, and the reader sees no entries | **the fault.** `--warn` on a rail, the line count, and the path — which is a `/file` link, so the next click is the file itself. |
| `empty` | the seeded skeleton, or all answered | **nothing at all.** |

- **`empty` renders silence, and that is what keeps the loud state credible.**
  A page that greeted every freshly-seeded target with a warning would train
  him to ignore the one that matters. Absence of a message is still the
  all-clear, exactly as it was before this existed.
- **The exemption is where this check dies**, so `empty` is defined as
  narrowly as it can be: not merely "no prose", but no prose **and** the
  literal `## Open` the reader matches. A file whose only lines are headings
  and which has no `## Open` is precisely the failure that started this, so it
  is `unreadable`. The linter made the looser version of this mistake an hour
  earlier and red-lit every seeded target; the guard's last assertion takes the
  file the exemption blesses, adds one line of prose, and requires the fault to
  surface anyway.
- **What the empty list SAYS is a claim about the file**, so it is keyed on
  health too (`QNONE`). "none — all answered" was stated unconditionally, and
  it is the sentence that did the lying.
- **The crumb badge is keyed on it as well.** It is what he glances at from
  every route, and a zero there reads as all-clear from three views away.

**A write the server refused is the same failure from the other end**, and it
wears the same colour. A file the reader cannot see is a file `/answer` cannot
write to — but the page did not check: `postAnswer` discarded its response and
the submit morph ran regardless, so the card restated itself as answered, his
text was cleared, and the live tick put the question back two seconds later
with no explanation anywhere. Now a refused write shows why in his terms (the
status names the protocol, not the problem), does not run the morph, and
**keeps his text**, which at that moment is the only copy of it.

`dev/capture/health.mjs` holds all three states plus the write path, because
each is easy to get right alone and the failure is always that one swallowed
another. Two things it learned the hard way: driving the write failure by
rewriting `questions.md` under a live page measures the 2s tick race rather
than the feature (and `holdRerenderUntil` is a module-scope `let`, so freezing
it from outside silently does nothing) — inject the refusal with
`route.fulfill` instead; and the card must be addressed by `[data-qid]` rather
than `.qa.open`, since the bug under test is the card *leaving* that state, so
a selector naming it stops matching exactly when the failure happens.

### The tab title

The title is the only part of this dashboard that exists while the tab is
backgrounded, which is most of its life — so it answers the page's whole
question rather than naming the app (#153). His words: *"dreamwork watch
browser title should be improved"*.

```
(2) dreamwork/ud-dreamwork · dreaming · questions
```

**Four fields, each saying exactly one thing**, ordered so that truncation
takes the least useful first: how many things wait on **him**, which **loop**
this is, whether the loop is **alive**, and where he is. Tabs truncate from
the right, so the count is front-loaded and everything after the second field
is a bonus. `(0)` renders as `(0)`: a title that says nothing about the count
is indistinguishable from one that has not loaded.

**The count and the word are orthogonal, and that is what makes both worth
reading.** The count is about him; the word is about the loop. `(2) x ·
stalled` — he is the bottleneck *and* nothing is moving — is a state neither
field could report alone, and a loop that stops is otherwise perfectly quiet:
it writes nothing, so no tick, no mtime change, no re-render. Which is why
the word rides the standing `ages()` sweep rather than the tick (#132's seam,
load-bearing for a second reason now), and why `identity.mjs` proves the flip
happens with the target's mtime provably unchanged.

**The count is `awaiting_human`, with `open_questions` as the fallback** for
a target whose loop has not written a `status.json` yet. This is the one place
on the page where a second count is right rather than a lie: #141's rule is
that the dashboard section and the crumb badge must not disagree about
*unanswered questions*, and they still don't. The title asks a different
question — *is the loop blocked on him* — which the loop answers itself, and
which can be true with no question in the file at all.

**`!` replaces the count when `questions_health` is `unreadable`**, and no
digit appears beside it: in that state every count derived from the file is
wrong, including this one. It does not say what broke — a tab title cannot —
it says *look*, which is what a tab title is for; the amber line says the
rest. (The guard's first version anchored on `\(!\)\s*\d` and so read the
alternative shape `(!1)` as a pass. It now rejects a digit anywhere in the
bracket.)

**Nothing is claimed that is not known.** Before data arrives the shell's own
`<title>` stands; no `status.json` means no liveness word; an unparseable
`last_tick` means none either — `note_author`'s rule, three surfaces over.
The staleness threshold is two missed heartbeats (`STALE_TICK_MS`, 10m):
one late beat is a busy machine, two is a loop that stopped.

**The first field after the count is `dreamwork/<project>`, one compound
field.** The app's name was dropped at first — it was the only thing in the
title before, and a tab strip never has room for it — and he ruled it back in
on 2026-07-25 at 15:30 (`(4) dreamwork · <status> · <extra>`). His example put
`dreamwork` in the slot the *project* name occupied, while he was reading the
ud-dreamwork dashboard, so it reads equally as "the app name returns" and as
"this is what my tab already says". The compound is right under both, occupies
the one field he wrote, and for another target reads `dreamwork/hark`, which
is what it is. The state stays third, so truncation still takes the route
first. The guard asserts the compound rather than a substring: a title that
kept the app word and dropped the project would otherwise pass.

`dev/capture/identity.mjs` guards it by driving a *sequence* of loop states
through one live page — a guard that reloaded between states would pass on a
title assembled once in `navigate()`, which is precisely the version that is
wrong. Its fixture lesson is worth repeating: the first state wrote **three**
`awaiting_human` items against a `questions.md` holding **two** open
questions, because with two of each a title reading the derived count is
byte-identical to a correct one — and the first deliberate bug injected here
passed against it.

### The run mode (#290)

Main-dreamer **pace**, settable on the dashboard between `status` and `tint`.
His words: add a run mode with options like lackadaisical, continuous/hot, a
few helpers, and (later) hierarchical; track it so the agent can check status;
emit a monitored event; 10s cooldown with a progress bar that resets on every
change.

**Authority is the file, not status.json.** `.dreamwork/run-mode` is one line
from the closed `RUN_MODES` set (`lackadaisical` default, `hot`, `assisted`),
machine-local and gitignored — operational posture on this host, not a
portable project default. `collect()` exposes `run_mode` so every open window
converges on the existing `/mtime` poll. `status.json` may mirror later; it
never owns the value. `hierarchical` is **visible and disabled** until #264
and #288 make that tier honest — discoverable, not selectable.

**Shared 10s arm, then one POST.** Selecting a mode writes a pending
`{mode, until}` into `localStorage` keyed by absolute `data.target` so every
tab on this project shares one countdown. Each selection resets the deadline.
Only the final mode is POSTed; the server atomically writes the file and, on
a real change, appends `run-mode via watch[ /path]: <mode>` to
`watch-events.log`. Identical final → 200, no event. Re-selecting the already
committed mode cancels the pending arm.

**The control is the standing sliding group** (`.sgroup` / `.sgind` /
`.sgbtn`), so geometry and motion are free. Active mode takes `--accent`
(live loop control, not a settled preference like tint). The arm UI is a
linear bar draining 100%→0% over the remaining time plus tabular
`arms in Ns · <mode>` text. **Reduced motion hides the bar and keeps the
second-by-second text and the same application time** — timing may change,
function may not. A refused write reverts the selection and says so in
`--warn`, never confirming a write that did not land.

**Consumption honesty.** The file + the events line are how an agent learns
the mode. This dashboard does not, by itself, change a running session's
scheduler; the loop that tails the events log (or re-reads the file on tick)
must apply policy per its own skill protocol.

`dev/capture/runmode.mjs` is the browser guard: real 10s arm intermediate
progress, reset, commit, event exactly-once, hierarchical disabled, reduced-
motion text path, and cross-tab pending via storage.

### The project tint

His colour for this project (#143). His words: *"user can customize color
tint for watch on dashboard for dreamworker. shoudl persist for that project
and update any other windows for that project too."*

**"Persist" and "share" together are what rule out `localStorage`**: it syncs
the tabs on one machine and loses the setting on the next — and the setting
exists so he can tell this project apart from the others. It lives in
`.dreamwork/watch-tint`, one line, committable beside everything else the
loop keeps about a project, so a checkout arrives already wearing it. Its
contract is a row in `file-formats.md` and a check in `lint.py`, because the
fallback below is silent.

**Sharing needs no new mechanism.** The write lands under `.dreamwork/`,
which `watched_mtime` already walks, so the existing 2s `/mtime` poll carries
it: he picks a colour in one window and every other window on this project
follows within a tick, with nothing added and no reload. The guard keeps a
second page open throughout, never tells it anything, and requires it to
arrive on its own — the half a single-page test cannot reach at all.

**A hue, never a colour.** `TINTS` is a closed set of six, and the tint is a
Rodrigues rotation about the grey axis (1,1,1)/√3. That axis is the
rotation's own eigenvector, so the achromatic component — which is what
luminance contrast is made of — comes back untouched: *contrast survives by
construction*, a property of the operation rather than a claim about the six
values. Free RGB would have let one choice put the field where the accent
lives.

**It rotates the COMPOSED colour, not the tint vector.** Rotating only
`tint` moved the field by 2°, because the tint is multiplied by `glow*0.105`
and the near-black base — most of what is on screen — carried its own fixed
blue through unchanged. Measured, and the measurement is why the line moved.
It is applied before the vignette and the dither, so the neutral ±1/255 noise
stays neutral.

**No backticks in the shader source, including in its comments.** The GLSL
lives in a JS template literal, so a pair of them in a *comment* ends the
literal and the rest of the shader is parsed as JavaScript — the whole page
goes blank. `just test` now catches that in 0.2s (`TestBundleParses` runs
`node --check` over the assembled `<script>`); before that it cost a
twenty-minute guard run and read as thirty unrelated failures.

**Two things the tint deliberately does not touch.** `--accent`, whose one
job is marking the live and actionable thing — an indigo accent over a green
field is *more* legible, not less, and the guard asserts the computed accent
is byte-identical across tints. And the text ramp, which the hue rotation
cannot reach because it only ever runs in the shader.

**None of the six sits in the amber band (~35-70°)**, because `--warn` lives
there: a project tinted amber would paint its whole ambient field the one
colour on this page that means BROKEN. The other constraint that picked them
is that they must be distinguishable **at 16px in the favicon**, which is
where the tint is actually used to navigate.

**The picker is the standing sliding group** (`.sgroup`), so geometry, motion
and the ghost-outline rule come for free. Two things are its own: each label
wears its own hue, because `teal` is a word until you can see it; and the
selected one takes *its own* colour brightened rather than `--accent`, since
a settled preference is neither live nor actionable. A refused write keeps
the old selection and says so, which is `/answer`'s rule (#136).

Cost, measured the way the wisp was: p95 frame time 16.8ms at rotation 0 and
16.8ms at −79° (green) and +83° (magenta), p50 16.7ms throughout —
indistinguishable at vsync.

The guard's three false alarms are worth knowing, because all three were the
instrument: it sampled a region overlapping the 72ch text column (7° for a
79° rotation); it then sampled after a fixed sleep shorter than the 2s poll
(0°); and it ran while the page was still on `/review`, whose iframe covers
the margin it samples (6°). Wait for the *state*, sample where the field
actually is, and know which route the page is on.

### The favicon

The title's companion, and the half of a tab that survives truncation
completely (#153). His words: *"favicon required (we should make a great
favicon, maybe animated? could render offline and load dynamically via round
robin or whatever to loop)"*.

**The mark is a ring with one traveller on it** — the loop, and the thing
going round it — carrying three facts in three channels that do not compete
at 16px, which is the size it is really drawn at:

| channel | says | how |
|---|---|---|
| hue | **which** loop | #143's per-project tint arrives here by one edit (`favHue`) |
| motion | the loop is **alive** | it orbits while ticking; parks, dimmed and trailless, when stalled |
| the pip | **he** is the bottleneck | a crisp badge, knocked out of the ring; amber when the channel is broken |

**Motion is the status, which is the only reason it is here.** An
always-animating favicon is decoration, and this page's motion is opt-in and
meaningful. The two channels are the title's two fields exactly — the pip is
its count, the orbit is its liveness word — because both derive from
`titleNeed`/`titleLive`. A tab that contradicted itself would be worse than
either half alone.

**The amber pip is #136's use on a new surface, not a third use of `--warn`.**
It is the same fact — the reader cannot see `questions.md` — reaching the one
place he looks when the page is not on screen.

**Motion is designed for the frame rate the tab will actually get.** A hidden
document is given no rendering opportunities, so `requestAnimationFrame` does
not run in a background tab at all — and a background tab is where this
surface spends its life. Timers survive there, clamped (≥1s; ≥1min once
Chrome throttles a long-hidden tab intensively). So the orbit is quantised to
**one frame per second**, twenty to a revolution, on the standing `ages()`
sweep: right at 60fps, right at the 1s clamp, and degrading to nearly-still
rather than to a stutter if the clamp becomes a minute. Frames are cached on
first use — his round robin — so after one revolution a tick is a string
assignment.

**Honest note: the clamp figures are documented behaviour, not measured
here.** Two attempts to put a page into the hidden state under Playwright
failed (a second `newPage()` is a separate window, and `window.open` opened
one too, so `visibilityState` stayed `visible` both times). The design does
not rest on those numbers; it rests on rAF being unavailable, which is what
"hidden" *means*.

**The phase is the wall clock, not a counter**, so every window watching the
same loop shows the same frame — the shader's "one world, many viewports"
rule one surface over — and a reload does not restart the orbit.

**It is inline, always**: `just deploy` snapshots `watch.py` alone, so a file
beside the server does not exist in production. Canvas → PNG data URI rather
than an SVG data URI, because Chrome renders an SVG favicon as **one static
frame** and this one has twenty.

**The ground is transparent.** The first version painted the page's own
near-black tile, which is right on his dark browser theme and a black block
on a light one — seen at 16px against real tab-strip greys, not reasoned
about. The same look at that size is what rejected the version before it: a
soft bloom, which is a formless smudge below 32px, and which taught the
thing the shape rests on — **at 16px a change of POSITION is legible where a
change of luminance is not.** That is why the traveller orbits rather than
breathing, and it is the same conclusion #113's wisp reached from the other
direction.

**Reduced motion pins the frame and keeps everything else.** The trail and
the full brightness still say "in flight" with no motion at all — the wisp's
rule, that reduced motion changes timing and never function or legibility. A
guard asserts specifically that a reduced-motion tab is not demoted to the
*stalled* treatment, since that is the tempting one-line version.

`dev/capture/identity.mjs` guards it by decoding the icon back into a canvas
and sampling **pixels**: two icons differ as strings the moment anything at
all changes, so a string comparison can prove "it moved" and nothing else —
not which state it is in, not that the badge is the right colour. Its own
reader was wrong first in the way this file keeps recording: it *rejected* on
an icon that never loads, so the injection where nothing is ever drawn made
the whole guard throw, and the run said "the guard threw" where it should
have said "the favicon is not a PNG and nothing is drawn". It returns a zero
reading instead. A crash reads like silence.

### The status panel

`status.json` is the loop's live state, and it used to be rendered by dumping
it into a `<pre>`. That was fine while it was four keys; it stopped being fine
at ~10:44 on 2026-07-25, when the coordinator started writing runtime state
into it and it grew by half (human, with a screenshot: *"the status section
shows json. It should render that json nicely, using colors effectively, and
making good use of space, and cutting out or hiding bulk or boring stuff."*).

**A glance is three questions**: what is happening, who is doing it, and does
anything need him. `statusBlock` answers those in that order — `awaiting_human`
first, then the task and the goal it serves, then one line per agent (name +
`in_flight`), then a dim row of liveness facts. Everything else in the file is
there so an **agent** can resume, which makes it load-bearing rather than junk.

- **Nothing is dropped, only demoted.** The fold takes whatever is LEFT after
  the named keys, never a second known list — `status.json` is a schema rather
  than a fixed shape and the loop keeps adding to it, so a list would silently
  hide the next thing it learned to say. The fixture carries a key the renderer
  has never heard of, and the guard asserts it is still findable. Unrecognised
  *shapes* fall back to a flattened key/value read rather than to a blank, for
  the same reason.
- **Colour by significance, never by JSON type.** Tinting strings, numbers and
  booleans is the obvious move and the wrong one: it makes the panel louder
  without making any of it easier to read, and it spends the page's one accent
  on `true`. The accent goes to `awaiting_human` — on a rail, and on its count
  — and nowhere else in this panel, because it is the only thing here waiting
  on **him**. That is the question card's axis one surface over. It does not
  breathe: the awaiting-fold wisp is still the page's one moving exception, and
  the thing that separates these two accents is that one of them is in flight.
  Everything else rides the text ramp — the task brightest, the goal under it,
  the liveness facts dim, the fold dimmer.
- **The tick is an age, not a timestamp.** It goes through the page's standing
  `.age` idiom and keeps counting while he watches it — liveness is the design.
  An unparseable `last_tick` renders verbatim rather than as `NaN`.
- **The fold's key column is fixed width, not a minimum.** "Label the columns,
  not the gaps" applies to a key/value list: a long key on a `min-width` shoves
  that row's value out of line with every other row's, and the reader has to
  re-find the column. It wraps inside its own column instead.

`dev/capture/status.mjs` guards it against a frozen `status.json` in the
fixture, and the check worth knowing about is the accent one — reading
`--accent` off `:root` gives the token as authored (`#a5b4fc`) while every
computed `color` comes back as `rgb(…)`, so comparing the two matches nothing
and "the accent is used nowhere else" passes on a page painted entirely in it.
Resolve the token through a throwaway element. It was shown red by deliberately
accenting the agent names.

### The burndown

The ledger's own history, drawn (#142). It sits **below** the questions and
the reviews and **above** `status`: the top of this page is what *needs* him
— a fault, what just happened, what he must answer — and the burndown is
context rather than an errand.

**No new instrumentation, and that is the design.** `.dreamwork/tasks.md` is
versioned and its ids are permanent, so `git log` over that one path *is* the
time series and a task is followable across every snapshot by its id.
Anything the loop had to start recording on purpose would be a second source
that can disagree with the ledger, and the ledger is the one he reads.

**Two tracks over one set of columns, because the open count alone cannot
tell "he steers fast" from "the work is slow" — those are the same curve.**
The *level* (how many were open) sits above; the *flow* (arrivals up,
completions down about a hairline) below. Direction is what separates the two
flow series, so no colour is spent on it, and **the accent is not spent here
at all** — nothing in this panel is waiting on him, which is the status
panel's rule (#130) one surface down.

**The level is a step line, not a filled bar**, and that was decided by
rendering it: on a ledger whose open count runs 12 to 67 the filled version
is a near-uniform block, because every column is between 40 and 100 percent
of the tallest. A 2px cap on a transparent box of the same height is the same
number and reads as the staircase it is.

**No velocity score, deliberately.** A rate computed over a day of a loop
that has been alive for a day is a claim about the future dressed as a
measurement, and the page would then be believed about it.

**An arrival and a completion are FIRST-SEEN events** — the first commit that
mentions an id anywhere, and the first that names it under
`## Recently landed`. That is what makes them survive grooming: the landed
section is pruned, so anything derived from its current contents loses a
completion every time the coordinator tidies. The two sections are read with
*two different rules* because the file has two shapes (an entry head under
`## Open`, a name in prose under `## Recently landed`), and reading the
second with the first finds nothing at all — which renders as "the loop has
completed nothing".

**What counts as an entry is `lint.py`'s rule, verbatim, and a test asserts
the two patterns stay identical.** One rule, one copy: the linter learned
that today (3073055) by holding a wider copy of the priority-marker rule than
the parser and blessing three typos.

**It reports its own provenance COVERAGE rather than drawing a split.** The
most telling number would be human- against loop-initiated, and the ledger
cannot support it — the `**human` stamp is on a minority of entries, so a
chart drawn from it would be mostly one bar wide and would be read as fact.
The head says `sourced 0/4` and the note says what that makes impossible.
It is also the thing most likely to make someone add the field.

**The head is one ellipsised line and the note is CONSTANT prose**, and that
is not a phrasing preference. The note used to carry the counts, and
`0 of 4` becoming `0 of 14` pushed it onto a fourth line and grew the panel
by 14px — so a bar easing over 850ms sat above four panels that had already
jumped. The head ellipsises for the reason a commit row does (#151).

**Every height in the chart is fixed**, which is the premise the motion rests
on: fresh data changes bars and never moves the page, so the bars may animate
without any FLIP over the panels below. `burndown.mjs` **measures** that
premise rather than trusting it — #204 is what a reasoned exemption costs
when nobody checks it.

**A bar travels on a data change and is not disturbed by a tick.** The gate
is #151's, but **here it is an optimisation rather than a behaviour**, and
that difference is stated in the code: a commit row can move because
something else re-laid the page out, while a bar's height is a pure function
of the series — so deleting this gate changes no outcome (`regroupBars`
early-returns on an equal height) and it therefore has **no check**, on
purpose.

**Restoring the percentage is the whole cleanup.** Every other travel on this
page clears its inline height at the end because those elements get their
size from layout; a bar gets its size from an inline `height:N%` the renderer
wrote, so clearing it leaves the bar at zero. The first version collapsed the
entire chart to its 2px rules after every animation and stayed collapsed
until the next re-render replaced the nodes — #198's shape, a permanent bug
with a short unreliable lifetime, laundered by something unrelated. The guard
found it; reading did not.

**Cost.** The walk is one `git show` per ledger commit — 139 today and only
ever growing — so it is cached on HEAD, and the per-revision parse is
memoised on the commit sha because history is immutable: a new HEAD costs
only the commits that are new (measured: 0.26s cold, 0.007s for a new head,
0.0014s warm). Every git call carries `--no-optional-locks`, asserted by a
test rather than remembered. One consequence of caching on HEAD alone: the
chart's right-hand edge is the moment the answer was computed, so it goes
stale until HEAD moves — which is right for a chart about ledger history.

**Both kinds of nothing say so, inside the same `.bd` box.** A project that
is not a git checkout, and one that keeps no versioned ledger, are ordinary
states rather than failures; a panel that drew nothing would be
indistinguishable from a loop that had done nothing.

### The dashboard's questions section

Collapsed by default, counting what is left to answer, and grey at zero
(#141). His words: *"on the dashboard, the questions section should be
collapsed by default and show how many questions there are left to answer. it
should be grayed out and disabeld when that number is zero."*

**The count is `open_questions`, the server's, and there is deliberately no
second way to reach it.** The crumb badge he glances at from every route reads
that same field; two counts that can disagree is how a page starts lying about
the one number he checks.

**Disabled means "nothing here needs you", not "you may not look."** At zero
the summary drops to the dim end of the ramp and loses the accent — and the
disclosure still opens. Refusing to open would be a claim about permission,
where zero is a claim about need. (The guard drives that with a real pointer,
not `element.click()`: a synthetic click sails straight through
`pointer-events:none`, so the obvious version of the check passes on a summary
the human cannot click at all.)

**And it is keyed on `questions_health`, not on the count** (#136). An
unreadable `questions.md` produces a zero too, and a calm grey "nothing to
answer" two lines under that file's amber warning would be the page
contradicting itself. The grey is for a genuine zero; every other zero keeps
the live treatment and lets the warning above it speak.

**The whole section folds, awaiting-fold cards included**, and that is what
makes it a *standalone* `expand` — instant, like the `.md` peeks — rather than
a case for the regroup: nothing that moves sits below the toggle, so opening
it teleports no card. The summary still names what is inside
(`questions · 2 to answer · 1 awaiting fold`), so a collapsed panel never
hides the fact that something is in flight.

**What he opened survives the tick**, which is #118's rule one level up. A
section he expanded exists nowhere on disk and the tick rebuilds the dashboard
through `innerHTML`, so without this it would snap shut under him every two
seconds. `snapshotFolds`/`restoreFolds` key on `data-keep` rather than
position and only ever *re-open*, exactly as the card snapshot does; any
future section gets the same behaviour by carrying the attribute. They run
**before** the regroups, which measure.

`.qsec > summary` uses the child combinator on purpose: a question card inside
carries its own `<details><summary>`, and a descendant rule here would be one
more of the catch-alls that bit #121 and #139.

### The commits panel

Five commits, near the top, each row carrying how long ago it landed
(#132, #151). His words: *"commits on webui should have a timestamp next to
them like 'XXm YYs' ago"*, and *"near the top of dreamworker dashboard should
be the most recent 5 commits. whne a new commit is made, the bottom one should
dreamlike fade away, the new top one should dreamlike fade in, and the other 4
should gently slide down one. should come together nice and smoothly."*

**The age is two units, two digits each** — `05m 23s ago`, `02h 14m ago`,
`03d 07h ago`. Two edges are decided rather than fallen into: under a minute
it still reads as two units (`00m 12s ago`), so the column never changes width
and a seconds-old commit is exactly the case he is watching; and past 100 days
the DAY count widens while the second unit stays at two, because the shape is
"two units" and not "four characters" — a truncated day count is a wrong
number rather than a narrow one.

**The time arrives as a number and the row renders none of it.** `git_tail`
emits `%ct`; the row is a `<span class="age" data-ct=…>` that is *empty* in
the HTML. A page computing an age from what it displayed would be reading its
own output back, and the server's copy is stale the second after it is
written.

**Which makes WHERE the clock ticks the whole design.** A seconds-resolution
age has to change every second, and this page re-renders through `innerHTML`
— so routing it through the tick would re-run the regroup (#113) and re-carry
his half-typed text (#118) sixty times a minute, forever, to move one digit.
It goes through the page's standing `ages()` sweep instead: a targeted
`textContent` write into nodes that already exist, on `setInterval(…, 1000)`,
with `setContent` re-running it after every swap so a fresh row is filled
before it paints. That seam already existed for `.age[data-mt]`; #132 is what
makes it load-bearing rather than convenient.

**Rows are fixed-height and the subject ellipsises**, so the panel's height is
a constant and nothing below it moves when a commit lands. `nowrap` is the
mechanism; the explicit `height` is a floor over it.

**A new commit is ONE gesture, and it is #104's regroup over different rows.**
`snapshotCards`/`regroupCards` take a *list* — a selector plus the attribute
that IS a row's identity (`data-qid` for cards, `data-sha` for commits) — and
both lists go through the same pair. A second implementation of "one leaves,
its neighbours travel" would be two things to keep true. The two branches in
there that are about a card are inert here **by construction rather than by a
guard clause**: a row is fixed-height, so `dh` is always 0 and neither body
branch is reachable, and no `.label` precedes a row inside `.git`, so
`cardGroup` returns `''` on both sides and nothing is ever lifted.

**It animates on a new SHA, never on a tick**, comparing the whole sha
sequence (a rebase or an amend changes the panel without changing its top
row). The dashboard re-renders whenever any watched file changes — the loop
rewrites `status.json` every few seconds — and rows travelling for that is
motion with nothing behind it. Note *why* that gate needs a real check: with
it deleted, a quiet tick still looks identical, because `regroupCards` returns
early for a row that did not move. The gate is only observable when the rows
move for some **other** reason, so the guard makes them (it writes an
unreadable `questions.md`, which puts #136's warning line above the panel) and
requires them to arrive with the layout rather than travel to it.

**The whole cycle travels DOWN, and the direction is not taste** (#174).
*"the bottom commit moves* up *towards where the new one appears. The bottom
commit should move* down *and scale up to fade out (like page transitions).
The top one should fade in moving down and scaling up."* (human, 2026-07-25).
The four survivors are already travelling down one row under the regroup, so
a departure that also falls is continuous with them and grows out of frame,
and an arrival that comes down into its row moves with the rows it is
displacing. Rising does the opposite: it reverses against every other thing
in the gesture, which is what he was seeing.

**So the rule is that a departure leaves in the direction its list is
travelling**, and that is one idiom rather than two. A question card's
neighbours travel *up* to close the gap it left, so `.qaghost.gone` rising is
right there and is unchanged; the commits panel's neighbours travel *down*,
so `.qaghost.commit.gone` falls. Growing while fading is the page's standing
departure either way — it is what `.ghost.out` does for a whole view — so
what varies is the sign, taken from the surroundings, and nothing else. The
arrival is the same statement at the other end: `.git .commit.dreamin` starts
above and smaller (`.dreamin` still supplies the snap) and settles down into
its row.

**The guard asserts the SIGN**, in `motion.mjs`. Counting that the row moved,
or that a ghost existed, passes on exactly the version he complained about —
the same trap as measuring that the wisp changed rather than how.

**No element catch-all in here** — `.git div` used to colour these rows, and
that is the third instance of the shape that overrode `.sgbtn` (#121) and
leaked into `.qfield textarea` (#139). Every part of a row is addressed by its
own class.

`dev/capture/dashboard.mjs` guards all of it, and it **builds its own git
target**: `dev/capture/fixture` is not a repository, so `git_tail` returns
`[]` there and every one of these checks would have passed vacuously against
the shared server. Planting commits at known ages is also the only way to
reach the 100-day boundary.

#### A row expands (#166)

The subject line is a *label* for the reasoning; the **body is the
reasoning**, and in this repo it is the most useful text in the log — the row
shows sixty ellipsised characters of it. So the row opens onto the full sha,
the author, the message body and the files it touched. Per the principle
above this is an **expand**: it is detail about the row he is looking at, and
he keeps the four rows around it.

**The row IS the `<details>`**, not a div wrapping one. That is what makes it
inherit the page's whole disclosure vocabulary at once — `summary::before`'s
`+`/`-`, #169's air and luminance step, `data-keep`'s survival across the
tick, and the shared expand handler's motion — instead of re-stating four
things. It is also the first element on the page to need **two keys at once**:
`data-sha` addresses the row inside `GIT_LIST`, and `data-keep="commit:<sha>"`
addresses what he opened across a re-render. They answer different questions
and a single key would have to lose one of them.

**Three inherited contracts, and all three are invisible to an end-state
check**:

- **The FLIP window.** `regroupCards` measures the row's new rect in the same
  tick the toggle flips, so #169's `.5rem` of air has to be in the layout by
  then. Put a transition on it and the travel plays to a height the row never
  reaches and snaps when the inline height clears — measured at **17.6px to
  go at the end of the opening travel and 36.6px on the close**, with every
  "it moved" and "it ended in the right place" check still green. This is the
  list `prominence.mjs` does not reach, which is why `gitrow.mjs` asserts it
  here.
- **The panel's height is a constant.** #151 rests on five fixed-height rows,
  so `details { margin:.25rem 0 }` — which every *other* disclosure wants —
  is zeroed at `.git .commit`, not weakened at `details`. Left in, the row
  pitch goes 22 → 26 and a landing commit moves the page.
- **What he opened survives the tick** (#118 / #141 one level down), for free,
  by carrying `data-keep`.

**The step is `--dim` → `--muted`**, stated here because #169's rule is
per-surface: a closed commit row is the dimmest summary on the page, so the
shared `--bright` would drag a five-row peek to the loudest thing on the
dashboard.

**The body is reflowed** (`mdB`, #102) — a commit message is hard-wrapped at
~72 columns by every tool that writes one, and rendered verbatim in a wider
column it reads as a poem. **The files are plain text, not links**, and that
is a decision rather than an omission: a path from an old commit may not
exist now, and #157 is open precisely because a link that 404s promises
something. They become links when #157 lands, by resolving first.

**Both empty cases say so** — `(no message body — the subject is all of it)`
and `(no files — an empty or merge commit)`. One line each, and they are the
difference between "this commit had nothing more to tell you" and "this page
could not read it", which is #136's rule one panel over.

`git_tail` carries the extra fields on the existing single `git log` call:
`%x1e` at the head of the format makes each commit one record, so
`--name-only`'s file list — which prints *after* the format, on its own lines
— lands in the last field instead of being indistinguishable from the next
commit. The file list is capped at 40 in Python, because five commits
touching a thousand files each would be a megabyte of `/data.json` on every
tick to fill a disclosure nobody opened.

#### What this page is serving

One line, directly under the `commits` label and above the rows (#140).
`just deploy` snapshots `watch.py` outside the repo and runs *that*, which is
the right property — a dreamer editing the tree cannot change what is already
serving him — and its cost is that **a fix that is committed and not deployed
is indistinguishable from a bug, and he is looking at the deployed page**.
#129 was reported 24 seconds after the commit that fixed it and about four
minutes before the deploy; the report was accurate, the code was correct, and
a tracing cycle went into the gap. The decided answer is not a deploy hook —
`.git/hooks` is untracked, so it would be invisible, machine-local, and would
quietly move deploy authority to whoever commits — it is to make a stale view
**announce itself**.

**Its home is the commits panel because the answer is only meaningful beside
the list it is behind**, and the line sits between the label and the rows so
it is read before them rather than as a footnote to them.

**Three brightnesses for three kinds of answer, and the ranking is the whole
design.** A healthy answer is a fact (`--dim`, `serving c552338`). An answer
this page could not compute is a fact about the page (`--dimmer`,
`serving — unknown · …`). A page running code older than HEAD is a **fault**
— it invalidates everything else on screen — so it takes `--warn` and the
rail: `this page is 2 watch.py commits behind · serving 8513719`. **That is
the second and last use of the rail idiom**, and the comment on `.qhealth`
used to claim it was the only one; what the two share is exactly what earns
it — both are the page saying it cannot be trusted right now, one about the
file it reads and one about the code it runs. Nothing merely important gets
it.

**It is never silent, and that is the one place it differs from the hub's
version of the same line.** dreamhub says nothing on a healthy row because it
has N rows and a line on every healthy one hides the unhealthy one. Here
there is one page, and a silent healthy state is indistinguishable from no
check at all — which is the failure this whole page is organised against. So
`no repo` (the ordinary answer for a target that is somebody else's project,
carrying no `watch.py` history) still renders, dim, saying it cannot tell.

**"watch.py commits", not "commits", and the extra word is load-bearing
here** in a way it is not on the hub: this line sits directly above a list of
*all* the project's commits, where "3 commits behind" would read as a claim
about those rows. HEAD can move thirty times without `watch.py` moving once,
and `missing` is pathspec-filtered.

**Measured by bytes, and by this process's OWN bytes.** The states, the
vocabulary and the missing-commit list are `deployed.py`'s value for value
(#147), so the hub row and this line say the same words — but the question is
not identical, and the difference is the point. `deployed.py` asks what the
snapshot at the conventional path holds; this asks what **this process is
running**, read from its own `__file__` at import. They agree whenever the
deploy recipe started the server and disagree exactly when something else did
— a `just watch` from the tree, or one of the orphaned servers #203 is about,
which is the case where the answer matters most. It is not `import deployed`
because a deployed `watch.py` is routinely the only file of this project on
disk, and reaching into the *target* for a module would mean a read-only
dashboard executing code out of the directory it is watching.

Detail is ranked, never withheld: the summary is the line, and the individual
missing commits are in its `title`, so hovering gives the whole list without
the panel growing to hold it — the hub's arrangement, one surface over.

**No new motion, deliberately.** The line's presence can only change when
HEAD moves, and that is already the commits panel's own gesture (#151): the
sha sequence changed, so `regroupCards` runs and the rows travel from where
they were — which is below where the line now is. The other direction
(`behind` → `current`) happens only on a redeploy, and a redeploy is a new
process, so `GENERATION` changes and the page reloads.

The Python half is cached on HEAD (`serving_cached`) because the `behind`
walk costs one `git show` per revision of `watch.py` — 75 today and growing
forever — and every git call carries `--no-optional-locks`, asserted by a
test rather than remembered, because his `CLAUDE.md` has a live mitigation
about that lock. `dev/capture/serving.mjs` guards the render across all four
states by evolving one repo forwards.

### The enter-snap rule beats the component

`.dreamin` carries `transition:none !important`, and the `!important` is the
rule rather than an escape from it. The class exists to make an arriving
element *begin* at opacity 0 instead of animating toward it, so it has to beat
whatever that element's own component declares — which is everywhere it
matters.

It did not. `.qa` states the same three transitions at the same specificity
and **later in the sheet**, so a question card carrying `.dreamin` kept a
0.85s transition and an opacity of 1: it animated one frame toward 0 and had
the class removed. Arrivals in the question list have been pop-ins since #104,
and crumbs — which declare no transition of their own — have always been
right. Nobody noticed because no guard traced an *arrival*; #151 found it by
reusing the mechanism on a second list, which is the duplication-as-audit
lesson landing for the third time.

Source order is not a contract: a component added below `.dreamin` would take
it back silently. Only the transition is `!important` — the other three
properties are the start *pose*, and a component may reasonably want its own.
`dashboard.mjs` asserts the snap for a commit row, a question card and a
crumb, so the next component to declare a transition cannot quietly undo it.

### The composer

The `+` opener in every heading's left gutter toggles **the composer**
(`#cmdpalette`) — the panel that steers the loop without a chat turn. It is
anchored to its opener, not floated free: `place()` puts it `CMD_GAP` (18px)
under the opener and flush with its left edge. Two things make that
arithmetic non-obvious, and both are load-bearing:

- **The panel is `position:fixed` but the viewport is not its containing
  block.** `.wrap` carries `perspective` (for the dream dissolve's depth),
  which makes `.wrap` the containing block for fixed descendants — so `top`
  and `left` are measured from `.wrap`, while `getBoundingClientRect()`
  returns viewport coords. Subtract `.wrap`'s origin or the panel drifts
  right of the opener and hangs a body-padding too low.
- **The opener rotates 45° into an ×**, which swells its painted box by its
  half-diagonal. Anchor off the rect's *centre* (invariant under that
  rotation) plus the painted extent, so the gap is what the eye sees and is
  identical whether the panel is placed while closed or re-placed while open.

Nothing under the buttons is reserved: `.cmdmsg:empty` collapses, so the
panel grows downward only when there is something to say.

**What it says arrives and departs** (#159/#255). `confirmationFor` is the
single lifecycle controller consumed by the main composer's `.cmdmsg` and the
popped-out composer's `.pmsg`; sharing this one seam does not wait for #241's
full composer mount extraction. Every claim enters through the standing
`.dreamin` snap. The forced reflow between adding and removing that class is
load-bearing: without a committed opacity-zero frame there is no arrival.

A successful `sent to the dream` is true about the command that just landed,
not about whatever draft is typed next. It therefore stays readable for about
five seconds independently of typing **while the panel remains open**, then
departs through the same soft opacity/blur/upward drift and clears. Typing
cancels only the courtesy close, so the steering channel stays open; it cannot
strand or truncate the valid confirmation. Left alone, the panel's courtesy
closes after ~1.5s (`CMD_DISMISS_MS` = 1425 — #131's 1.5× of 950, restored
by #291 after #255 had accidentally tied it to the confirm hold). Closing the
panel is destruction: the line is hard-cleared with the surface rather than
left invisible for the rest of the hold. This courtesy belongs only to the
transient main panel. A command popout is an intentionally persistent separate
window the human explicitly created to keep beside him; successful sends never
auto-close it. Its confirmation completes the shared ~5s lifecycle, and only
explicit window close/`pagehide` destroys it.

**Destruction and falsehood do not depart slowly.** Manual close, route change,
popout `pagehide`, or unmount hard-cleans the controller and invalidates every
old timer **and in-flight submission attempt**. A response returning after that
boundary cannot recreate success; a newer submit similarly supersedes the old
attempt. A later rejection, connection failure or validation claim cancels any
success lifecycle and replaces it immediately; fading a false claim would
merely leave it false for longer. The departure listener is tracked state too,
not fire-and-forget: clear/replacement/fallback removes it so a missing
`transitionend` cannot accumulate stale closures on the persistent node.
Reduced motion keeps the same hold and clear semantics but snaps arrival/
departure visual states.

`confirmation.mjs` showed the old design red in exactly the reported races:
typing during a delayed real POST left main success forever, popout success was
permanent, and neither had a departure trace. It now uses fresh contexts for
main race, close/in-flight-response invalidation, forced transition fallback,
popout and reduced phases; the popout phase also proves the window persists
past the main panel's courtesy threshold. Normal arrival/departure must traverse
many opacity and transform values, while reduced motion traverses none.
`dismiss.mjs` retains the panel courtesy and #159 arrival checks: left-alone
closes on the ~1.5s courtesy (#291), typing cancels that close and lets the
confirmation finish its own ~5s lifecycle (#255).

**A steer carries the page it was sent from, and that page is a HINT** (#126).
The client sends `location.pathname + location.search` with every write
(`/command`, `/answer`, `/comment`) and the server brackets it into the events
line: `command via watch [/review?p=goal-hierarchies.html]: do-next: …`. The
query string is kept because *which* artifact he was reading is usually the
whole point.

The bracket is doing semantic work, not decoration. It puts the page **beside**
the command rather than inside it, because this is **evidence about what he
probably meant and never an instruction**: a command sent from `/questions` is
not thereby about `/questions`, and an agent that treats the hint as scope will
reliably narrow work he did not ask to narrow. The guard asserts the separation
as well as the presence.

Two consequences of the line being read by something that then acts:

- **The path is sanitised down to a shape, not trusted**: leading `/`, no
  control characters, no `]` — which would let it close its own bracket and
  impersonate the rest of the line. Anything else yields **no hint at all**,
  because a wrong hint is worse than none. Over-length is rejected rather than
  truncated: a cut path is a different path, and it points at the wrong file.
- **The popped-out composer captures its path at SPAWN**, not at submit. That
  window floats free while the main tab navigates on and its own location is
  `about:blank`, so where it was popped out *from* is both the only answer
  available and the honest one — it is the thing he popped it out to keep
  beside him.

**The half-typed thought survives a reload** (#163). The panel already keeps
its text across a close and a route change — it lives outside `#view`, so
nothing rebuilds it. What loses his words is a *reload*, including the one the
page performs on him when `tick` sees a new server generation. So the box
autosaves to `localStorage` on every `input` — **no debounce**, because a
debounce is a window in which his words are lost, which is the thing this
exists to prevent — and restores on open, only into a box that is empty (#118:
what he is in the middle of outranks anything stored).

**Browser storage is right here and was wrong for #143**, and the pair is worth
holding together because they look identical from a distance. A tint is a
setting *about* the project: it should follow the project to another machine,
so it is a committable file. An unsent draft is a thought he has not chosen to
send to anyone — writing it into the repo would publish it, and #199 already
gives the server a verbatim record of everything he *did* send. It is keyed by
`data.target`, the absolute path, never the project *name*: two checkouts can
share a basename, and a draft surfacing under the wrong loop is worse than a
lost one. He runs several windows per project, so the store holds *the most
recent* unsent thought on that project; two live boxes never fight, because a
restore never overwrites text.

**It is cleared on a successful send and on nothing else.** Not on close, not
on blur, not on a rejected POST — those are exactly the moments he most needs
it back. Emptying the box himself does clear it, because deleting text is a
deliberate act on the content rather than an accident of the panel. The kind
travels with the text (#103's rule that the mode is *where the text goes*),
validated against the live vocabulary on the way back in, since a plugin's
command can vanish between sessions. It restores **silently**: `setCmdMsg` is
the one line that says whether a command *landed*, and spending it on "draft
restored" would dilute the only place he looks for a send confirmation.
`dev/capture/draft.mjs` guards both directions — a check for "it survives"
alone passes on a page that never forgets, and "it is cleared" alone passes on
a page that never saves.

**Every submission is witnessed by the client too** (#175). #199 gave the
*server* a verbatim record of everything it received; this is the witness for
what that cannot cover — a submission the server never accepted, or never
heard. A 409 from `append_answer` (#136), a rejection he clicked past (#162), a
POST that never left because the server was restarting: in each of those the
client is the only party that knows what he tried to do.

**The recovery-critical field is the OUTCOME, not the text.** The text he can
usually still see; what is unrecoverable an hour later is whether the thing he
typed actually landed. So a record is written *before* the request, as
`pending`, and its outcome (`ok` / `rejected` / `unreachable`, with the status)
is attached when the response returns — a tab that dies mid-POST leaves a
record saying exactly that, which is the true state rather than a guess. An
entry is never deleted and never rewritten except to attach the outcome it was
waiting for.

It goes in **IndexedDB, one database per project** (`dw-submissions:<target>`),
not one database with a `project` column: a column needs every reader to
remember to filter, and a reader that forgets returns another loop's
submissions while looking perfectly correct. A separate database cannot leak by
omission. `postJSON` is the single seam it hangs off — the same reason #199
persists from `do_POST` rather than from four handlers — which is why the
composer's own `fetch` was replaced by a call to it; a second fetch would have
left a third of his submissions unwitnessed. **Nothing here may delay or break
a send**: every failure resolves to null and the write is raced against a
250ms timeout, because a missing record is bad and a command he could not send
because of the logger is worse. `window.__dwSubmissions()` reads it back —
"it must be readable or it is theatre" is the task's own line.

**The history is read where it was written** (#165) — a `<details>` at the
foot of the composer, because the composer is where he sends from and so where
he looks for what he sent. One list with the **kind marked**, not a list per
endpoint: he does not think of an answer as a different act from a command, and
two lists would ask him to remember which one he used. Newest first, capped and
scrolled — the panel is `position:fixed`, so an uncapped list would grow off
the bottom of the screen and take the send button with it.

**Its source is #175's client log, and the ledger line that proposed
`watch-events.log` predates the two features that changed the question.** Three
records exist now and they are not interchangeable: `watch-events.log` covers
every window and machine but is a *rendering* and cannot say whether a
submission landed; `.dreamwork/submissions.log` (#199) is verbatim but written
*before* the work, so it is pre-outcome by construction; only #175 knows the
outcome. A history is for recall and recovery, so the outcome decides it.
Merging them would mean explaining, on every row, which record it came from and
what that record therefore cannot tell him — a panel that apologises per row is
worse than a narrow one that states its limit once.

**So it states its limit once, at the foot: this browser only.** The failures
are the reason it exists, so they are the one thing that leaves the dim end of
the ramp — `--warn`, never the accent, because the accent marks what *needs*
him and a failed send from an hour ago is a fact rather than an errand. The
rows are fetched asynchronously, so they carry the page's enter idiom: without
it they blink in a frame after the disclosure has finished opening, which is
#196 at a smaller size, and "it is only a small panel" is exactly how a page
ends up with one gesture that snaps.

**The panel never closes under him** (#131/#255/#291). Auto-dismiss is a
courtesy (`CMD_DISMISS_MS` ≈ 1.5s), not the confirmation lifecycle
(`CMD_CONFIRM_HOLD_MS` ≈ 5s). Any `input`, `keydown` or `pointerdown` inside
the panel cancels that courtesy, and `composing` covers the race where he
resumes during the POST before a dismiss timer exists. The valid success still
belongs to the command that landed: while the panel stays open it remains
readable and clears on its own controller. Left alone, the courtesy closes the
panel at ~1.5s and hard-clears the line with it (panel close is destruction).
`dev/capture/dismiss.mjs` guards both branches and `confirmation.mjs` owns the
per-frame lifecycle proof.

**One vocabulary.** `COMMANDS` (top of `watch.py`) is the single source of
steering kinds — `{kind, label, desc, common}`. The server derives
`COMMAND_KINDS` from it to validate `POST /command`, the page embeds it as
`CORE_COMMANDS`, the composer renders its buttons from it, and the popped-out
form fills its `<option>`s from it. A new kind is one entry and nothing else.

**Plugin-contributed kinds append to that table** (#86), which is why the page
holds `COMMANDS` as a `let` and nothing downstream may assume a fixed set or a
fixed length. `writing-plugins.md` has granted plugins their own command
namespace in prose since there were plugins, and until this landed the
contract promised what the UI could not show — the human raised it twice.

- **They ride `/data.json`, not the shell.** Which plugins resolved is a
  property of the *machine*, so it can change under a page that is already
  open; the core half is a property of `watch.py` and cannot. `watched_mtime`
  walks `.dreamwork/`, so the existing poll carries it — no new channel, no
  reload, same move as the tint (#143).
- **Absence costs nothing**, and that is the common case rather than the edge
  one: most targets load no plugin that declares a command, and the composer
  with no file renders exactly as it did before any of this existed.
- **They live in the `...` menu and never the row.** `common` from the file is
  ignored, not refused — there is deliberately no way to ask. Core commands
  own the composer's most valuable real estate, so loading a plugin may add to
  the composer and may never degrade it.
- **The item names the plugin that answers it**, right-aligned at `--dimmer` —
  the quietest step of the ramp, the same as the history's ages. A plugin
  command can vanish between sessions and a core one cannot, so the two are
  not interchangeable and the menu says which is which. It is *provenance, not
  an errand*: the accent means "this needs you", and this is read only when a
  command is unfamiliar or has stopped working. The **row** carries no visible
  mark, only the title — the row is a mode switch whose one job is saying
  where the text goes, its width is load-bearing (#162 is that row wrapping
  and taking the panel with it), and by the time a kind is in the row he has
  already read the attribution at the moment he chose it.
- **The menu is reconciled by kind, not rebuilt.** An `innerHTML` rebuild ends
  in the identical DOM and costs two things: any hover or focus he was holding
  is dropped, and every item becomes an arrival, so there is no way to animate
  the ones that actually arrived. See *The menu's arrival* below.
- **The server reads the file per request.** A kind the composer offers has to
  be one `POST /command` accepts, and a set cached at startup would refuse the
  button it had just drawn.

### The menu's arrival

A command that lands while the menu is **open in front of him** eases in on
the page's one enter idiom (`.qreveal` + `.dreamin`). One that lands while the
menu is **shut** does not, and that is not an exemption of the #204 kind: the
menu was showing him nothing, so nothing appeared, and the menu's own reveal
is what brings it in when he next hovers. The guard checks that half too, by
looking for an item left stuck part-faded.

Two things about it were bugs first:

- **`.qreveal` needed a rule of its own here to work at all.**
  `.cmdmenuitem` declares a transition at the same specificity and *later* in
  the sheet, so it won, `.qreveal` supplied no transition, and the class was
  added to an element already at opacity 1 — #154 exactly, one component over.
  `.cmdmenuitem.qreveal` restates both sets and does not depend on source
  order, which is the invariant `.dreamin`'s own comment states.
- **Deleting a file used to be invisible to the poll.** `watched_mtime`
  statted only files, and removing one cannot raise the maximum mtime of the
  files that remain — so unloading a plugin left its commands in the menu
  until something unrelated was written. It walks the directories now. That
  matters beyond this feature: "unloading is the absence of a write" is only
  a contract if absence is observable.

**Choosing a kind** uses the shared sliding group (below): `.sgroup` /
`.sgind` / `.sgbtn`, plus its own `cmdkinds` / `cmdkind` styling. The row
carries the `common` kinds plus the active one when it is uncommon, so
whatever is selected always has a button for the indicator to sit on.

**Rebuild only on membership change.** `renderKinds()` returns early when the
row's kinds are unchanged, so a common→common switch leaves the DOM (and the
indicator) alone and it slides. A rebuild replaces the indicator with a fresh
0-width one, so that path lands instead.

### The sliding selection group

One indicator that slides to the active option, used by the composer's
command kinds and by every question card's answer/note switch — one
implementation (`slideIndicator`, `.sgroup` / `.sgind` / `.sgbtn`), so the
two can never drift apart. Geometry and motion live in the shared classes;
each user styles only its own buttons. Three rules, learned in the composer
and true for any user of it:

- **Land, don't slide, on first paint and on reflow** (`snap`). The
  indicator starts 0-wide at the group's origin, so animating from there
  reads as a glitch rather than a choice — the enter-snap rule again. Add
  `.snap` (`transition:none`), set the geometry, force a reflow, then remove
  it. Verify with a per-frame trace (`dev/capture/indtrace.mjs`,
  `oneinput.mjs`), never a screenshot.
- **Size to the active BUTTON, never to the group.** The row wraps once a
  vocabulary outgrows one line, and a `height:100%` indicator would span
  every line at once.
- **Measure in LAYOUT space, never in visual space** (#198). The indicator is
  a sibling of the buttons, so what it needs is where they sit *in the group*
  — and `getBoundingClientRect` answers a different question: where they
  appear on screen, every ancestor transform included. `openCmd` paints the
  indicator on the same frame it reveals the panel, and the panel reveals
  *through* a transform (`translateY(-8px) scale(.97)` → `none` over `.5s`),
  so every rect read there came back 3% small: measured, the indicator landed
  **4.53px left of its button and 1.88px narrow** on the far option, and
  stayed there. `slideIndicator` divides the scale back out
  (`group.getBoundingClientRect().width / group.offsetWidth`), which is
  exactly `1` wherever nothing is mid-transform — every question card, and
  the composer once settled.

  **It looked self-correcting, and that is the part worth remembering.** His
  report was that it *"autocorrects itself after a bit, or when some rerender
  condition is triggered"*, and the second clause is the whole mechanism:
  nothing heals, `setContent` re-paints every group at rest on the next view
  re-render, and his live dashboard re-renders every couple of seconds. A
  wrong value that something else routinely overwrites is not a transient —
  it is a permanent bug with a short and unreliable lifetime, and any check
  of it must be bounded to before the overwrite.

  Same family as #170 and #160: a transformed ancestor silently redefines
  what a position *means* for everything measured beneath it.
- **The selected label glows, it does not re-metric.** `text-shadow`, not
  letter-spacing or weight: a text effect that changes layout would resize
  the buttons and so move the very target the indicator is chasing.
- **The group is a ghost: an outline that slides, never a filled chip**
  (#121; his words: *"have an outline but no bg color; they are currently
  opaque so you can't see the animation behind it"*). The dreaming field is
  the background of every one of these buttons, so a fill anywhere in the
  group puts a lid on the page. The indicator keeps its **border** — that is
  what marks the active option, and it is the thing that travels — and the
  active label keeps its accent glow.

  This one is worth remembering for its cause rather than its fix. `.sgbtn`
  had asked for `background:none` since #103 and had never once rendered that
  way, because a `.qa button` element rule left over from before these
  components had styling of their own still won on specificity (0,1,1 beats
  0,1,0). **A catch-all that outlives the components it stood in for does not
  announce itself; it quietly overrules them**, and the component's own
  source reads correctly the whole time. The fix was to delete it, not to add
  a stronger selector.

  **It has now happened twice, so it is a standing rule: no element catch-all
  scoped inside a component.** `.qa textarea` was the same shape one component
  over (#139) — it leaked `margin:.3rem 0` into `.qfield textarea`, insetting
  the box 5.8px inside the border it shares with a send button sitting flush
  at 1px, so the one object the field is meant to be had two different insets.
  Everything else the catch-all declared was either already stated by
  `.qfield textarea` or made moot by the flex row, which is the usual state of
  one of these: deleting it *was* the fix. Delete rather than out-specify — an
  out-specified catch-all is still armed for the next component that renders
  inside it. `.qa` now carries none, and a comment in `STYLE` says why, so the
  next one is not re-added innocently.

  Both were invisible to pytest for as long as they existed, because the
  generated source contains the component's own correct rule; it is just the
  rule that loses. And both were invisible to the *browser* guard too, which is
  the sharper lesson: `oneinput` had asserted since #103 that the send button
  spans the field, and never that the textarea does — so it proved the half
  that was already right. **When a rule says two things form one object,
  measure both of them against the object**, or the check passes on a
  component with a seam down the middle.

**Discoverability is the ⋯ menu.** Hovering (or focusing) `.cmdmorebtn`
reveals `.cmdmenu` — *every* kind, common or not, each with its one-line
`desc`. A rare kind is then discoverable rather than hidden knowledge, and
picking one from the menu selects it and adds it to the row. The menu drifts
in on the same soft blur as the composer itself, and there is deliberately
**no gap between the icon and the menu**: `:hover` follows the DOM, not the
box, so the pointer must be able to travel from one to the other without
ever leaving `.cmdmore` or the menu closes en route. `aria-expanded` is
mirrored from JS because CSS cannot set it. Both the row and the menu render
from `COMMANDS` at whatever length it has — plugin kinds (#86) appear with no
redesign, which is the whole point of the shape.

### Motion language

**Moved to `transitions.md`** (skill root, 2026-07-25) so it can be
pointed at on its own — the human asked for a transitions guide, and a
second copy here would be a second source that agrees only on the day it
was written. Everything about how this page moves lives there: when
transitions apply, the regroup, the state matrix, the dissolve, the mist,
the enter-snap rule, the reduced-motion contract, and the two standing
invariants.

**Every transition on this page obeys it** — appear, disappear, expand,
collapse, state change, movement alike.

### Shader

Domain-warped fBm, four cheap passes on a low-res buffer (fractal → two
tilt-shift blur passes → composite/tint/dither); luminance-capped far below
the dim text so text always wins. Per-route `SEED`/`TINT`; transition `warp`
pulse. Recoverable context loss (rebuild on restore).

**One world, many viewports.** `mountDreambg(win, cv, opts)` is a mountable
function, not an IIFE bound to the main document — it reads everything from
the `win` it is handed, so any window can carry the field. The main page
mounts it on `#dreambg` (`{dev, switcher: true}`); `openPopout` mounts it on
every floated window (`mountPopoutBg`, after the fill, which assigns
`body.innerHTML` and would otherwise wipe the canvas), and the popout wears
the spawning view's tint. Three rules make "same screen position ⇒ same
pixels" actually true, and each was a bug until it wasn't:

- **The scale is a world constant** (`WORLD_SCALE = 2.3 / 900`, domain units
  per CSS pixel), not `2.3 / innerHeight`. A per-window scale pins the
  field's *origin* while letting each window pick its own *zoom*, so two
  windows show one dream at two magnifications and the seam can never line
  up. World-fixed scale also makes resizing reveal more of the field rather
  than rescale it — consistent with dragging, which already pinned.
- **The vertical anchor is negated and measured from the viewport's BOTTOM**
  (`-(screenY + chrome + innerHeight)`), because `gl_FragCoord.y` counts up
  from the viewport bottom while `screenY` counts down from the desktop top.
  Adding the top edge instead slides the field the wrong way at double rate.
- **The lens is per-window, deliberately.** The tilt-shift focus band and
  the edge defocus stay in each window's own `uv` space: one shared world,
  seen through each window's own lens. So blur can differ at a seam even
  though the field beneath it matches exactly.

`dev/capture/worldspace.mjs` and `popbg.mjs` prove this by freezing
`Date.now()` (the field is time-varying, so two screenshots are never
simultaneous otherwise) and comparing plates — across window heights, and
across the main/popout document boundary. Hidden layer switcher
for debugging — the hotkey is ignored inside text fields, and any switch
(key or corner triple-click) shows a self-naming auto-fading toast
("background: <layer> — press l to cycle") so an accidental change is
legible. `--dev` measures real per-frame work (steady state is ~0.1–0.3ms
CPU; transition dips are SVG-filter compositing, not the shader).

### Voice & tone (page copy)

The page is a quiet tool that dreams — copy is spare, lowercase-leaning, and
a touch oneiric without being twee. Labels are dim uppercase single words
(`dreams`, `questions`, `answer questions`, `reviews`, `files`, `commits`).
Status reads plainly (`none active`, `updated 3m ago`, `2 open questions`).
The command surface carries the metaphor lightly: `command the dream`,
`a thought for the dream…`, and confirmations `sent to the dream` /
`received`. Never product-y CTA language ("Submit your request!"), never
exclamation. When in doubt: what would a calm terminal say at 3am.

## Non-goals

- The request-authority policy is not authentication. It does not make a LAN
  private, add TLS, trust proxy headers, discover DNS/IPs, or support WAN/public
  exposure. Bearer-token LAN access and public Dreamhub auth are later designs.
- No historical analytics; a live window, not a metrics store.
