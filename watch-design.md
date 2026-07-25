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
- **Bind 127.0.0.1 only.** Localhost by construction, never exposed.
- **Read-only, three write exceptions** (all human-authorized, localhost
  trust): POST `/answer` appends an answer into questions.md's matching Open
  entry; POST `/comment` threads a `- **Follow-up (via watch, <ts>):** …`
  note onto any entry (Open or Answered — a chronological mini-thread; a note
  on an Answered entry is flagged as a potential amendment in the events
  log); POST `/command` appends a source-tagged steering line
  (`command via watch [<page>]: <kind>: <text>`, kinds add-idea / do-next /
  do-now / maintenance) to `.dreamwork/watch-events.log`. All three also append
  an events-log line so the loop's tail monitor wakes. Every other route reads.
  All file access goes through `resolve_confined()` (rejects absolute, `~`,
  traversal); `/filedata` and `/reviewraw` are both behind it.
- **Port** persisted to `.dreamwork/watch-port` (random 3000–63000 once)
  so bookmarks survive restarts; port-in-use error names the port.
- **Live reload**: poll `/mtime` ~2s → re-fetch `/data.json` → re-render
  the active view in place (no transition). No websockets. `/mtime` is
  `"<generation> <mtime>"`: a changed *mtime* re-renders the data; a changed
  *generation* (the server was restarted/redeployed, or rebuilt under
  `--autoreload`) triggers a full `location.reload()` so open tabs never go
  stale. The poll tolerates the brief unreachable window during a restart.
- **`--autoreload`** (implied by `--dev`): the server re-execs itself
  (`os.execv`) when its own source mtime changes — edit-and-see with no
  manual restart; the close-on-exec listening socket frees the port and the
  generation bump reloads clients.
- **Single-document router**: `/`, `/questions`, `/file`, `/review` serve
  one shell; the client router renders the view, pushState/popstate drive
  the URL. The `#dreambg` canvas is a sibling of `#view` — never unmounted,
  so the background survives navigation. Route changes dissolve through a
  turbulence mist (see Motion language); reduced-motion swaps instantly.
  `/review` embeds the raw artifact (served at `/reviewraw`) in an iframe
  for style isolation; a question linking to it travels along, docked.
- **Events log**: user actions (answers, commands) append one line to
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
(`buildDashboard`,
`buildQuestions`, `buildFile`, `buildReview`); the router swaps them. Add a
view by adding a builder + a `routeOf`/`TINT`/`SEED` entry, not new chrome.

**`expand` is structure; whether it MOVES is a separate question, and the
answer follows from where it sits.** A plain `<details>` — dreams, the
archive, the dashboard's `.md` peeks, the dashboard's questions section
(#141) — toggles instantly, like every other opt-in-motion surface on this
page. The questions section is worth naming because it *contains* cards that
move and still belongs here: it holds **all** of them, so nothing that moves
is left below the toggle to be teleported. **A `<details>` inside a question card
animates**: the card's own `.qfold` (#111) and its settled follow-up thread
(#128) both route their toggle through `snapshotCards` → `regroupCards`, so
the card travels its height and its neighbours close the gap, exactly as when
the loop folds one (see *The state matrix*).

The line is not decoration and it is not per-component: an expand inside a
**list whose other members move** must animate, or opening it teleports every
card below it; a standalone expand has nothing to disturb. That is why the
handler is written against `.qa details > summary` rather than against
`.qfold` — the next disclosure someone adds to a card is covered without
anyone remembering this paragraph. A reader who finds only this section will
assume `<details>` animates everywhere; it does not, and promoting it to the
generic idiom would animate three surfaces nobody asked for.

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

### Anything the human has changed on the page must survive the tick

Promoted to a rule at its third instance, which is where this page promotes
things:

- **#118** — text he was typing, destroyed by the tick's `innerHTML` swap;
- **#111** — an entry he had expanded, re-collapsed by the same swap;
- **#141** — a section he had folded, same again, two seconds later.

Each was found by hitting it, and each was fixed locally. A fourth feature
carrying human-controllable state will hit it a fourth time unless the rule
sits where the next builder meets it.

**The list re-renders through `innerHTML`, so any state HE owns — text he is
typing, a card he expanded, a section he folded — is destroyed unless it is
snapshotted before the swap and restored after, keyed by something stable.**
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
attribute. Both run **before** the regroups, which measure.

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

**The line: markdown prose reflows, raw text does not.** Question bodies,
answers, follow-up notes, dreams, and the dashboard's `.md` peeks are prose
the page composes, and they go through `mdB` / `mdBReview`. `/file` is shown
*as it is on disk* and stays verbatim in a `<pre>` — the file viewer's whole
job is to be literal, and it serves code as well as prose. Two things have
left that list, both for the same reason and neither of them prose:
`status.json` (#130) and the git tail (#132) are sets of *facts*, not text he
reads literally, and each now has a component of its own (below).

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
(2) ud-dreamwork · dreaming · questions
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

The app's own name is deliberately **not** in the title. It was the only
thing there before, and it is the thing a tab strip never has room for; the
favicon carries app identity, which is the part of a tab that survives
truncation completely.

`dev/capture/identity.mjs` guards it by driving a *sequence* of loop states
through one live page — a guard that reloaded between states would pass on a
title assembled once in `navigate()`, which is precisely the version that is
wrong. Its fixture lesson is worth repeating: the first state wrote **three**
`awaiting_human` items against a `questions.md` holding **two** open
questions, because with two of each a title reading the derived count is
byte-identical to a correct one — and the first deliberate bug injected here
passed against it.

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

**No element catch-all in here** — `.git div` used to colour these rows, and
that is the third instance of the shape that overrode `.sgbtn` (#121) and
leaked into `.qfield textarea` (#139). Every part of a row is addressed by its
own class.

`dev/capture/dashboard.mjs` guards all of it, and it **builds its own git
target**: `dev/capture/fixture` is not a repository, so `git_tail` returns
`[]` there and every one of these checks would have passed vacuously against
the shared server. Planting commits at known ages is also the only way to
reach the 100-day boundary.

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

**The panel never closes under him** (#131). The auto-dismiss after a send is
a *courtesy* — it gets the panel out of the way once the thought has landed —
and a courtesy must never take a channel away from someone still using it.
That is the same rule as #118, one surface over: what the human is in the
middle of doing outranks anything the page decided on a timer. Any `input`,
`keydown` or `pointerdown` inside the panel cancels the dismiss, and a
`composing` flag covers the race where he resumes *during* the POST, before
there is a timer to cancel. Resuming also clears the `sent to the dream`
confirmation, because a stale one sitting above a fresh unsent thought is a
false confirmation on his steering channel — he could read it as the new
command having landed. The wait is `CMD_DISMISS_MS` (1425ms, his 1.5×).
`dev/capture/dismiss.mjs` guards it, and asserts the panel is **still open at
1.0s** as well as that it eventually closes: an end-state-only check passes on
the old timing.

**One vocabulary.** `COMMANDS` (top of `watch.py`) is the single source of
steering kinds — `{kind, label, desc, common}`. The server derives
`COMMAND_KINDS` from it to validate `POST /command`, the page embeds it as a
JS `const`, the composer renders its buttons from it, and the popped-out form
fills its `<option>`s from it. A new kind is one entry and nothing else;
plugin-contributed kinds (#86) append to the list, so nothing downstream may
assume a fixed set or a fixed length.

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

### Motion language (authored across the transition work)

The page *dreams*: motion is soft, slow, and never crisp-mechanical. It is
also strictly opt-in — most state changes do **not** animate.

**Things that move, slide** (human, 2026-07-25): "in general when things
need to move they should slide gently, ethereally, not jump around." Read
this as the tie-breaker it is — it does not overturn the opt-in rule (a
live tick still re-renders instantly), but wherever the page *has* decided
to change layout, the elements that survive travel to their new positions
instead of teleporting. FLIP is the mechanism; reduced-motion is the
exception; an element leaving fades rather than vanishing.

- **When transitions apply.** Route changes (client nav) dissolve. The live
  mtime tick commits its new DOM **immediately** — liveness never waits on an
  animation — but where that re-render *moves* something that survived, the
  survivor travels to its new place rather than appearing there (the
  regroup, below). The composer reveals on a soft blur drift. Nothing else
  animates.
- **The regroup** (a question is answered). One moment seen two ways: the
  questions below close the gap it left (#104), and the question itself
  travels to its new heading rather than being re-set there (#77). One
  mechanism — a FLIP over the list keyed by **`data-qid`**, the question's
  own identity, which survives the move its positional `data-qkey` cannot.
  A card whose **heading changed** gets the lifted-hero morph so the eye
  follows it across the page; a card that merely shifted slides. Use the
  heading, not the card's state class: the submit morph already changed that
  class locally when the answer was sent, so by regroup time it reports no
  change even as the card is about to cross the page. A card gone entirely
  dreams away at the rect it occupied, which is why the snapshot clones every
  card up front — after the re-render there is no node left to animate, and
  you cannot know in advance which will go.
- **The state matrix, and the one mechanism under it.** The three question
  states are one axis, so their transitions are one matrix, and every cell
  goes through `regroupCards` → `travelCard`. A card **travels** from the
  rect it had to the rect it has — in position *and* in height — and if it
  crossed to a different **heading** it is lifted while it goes (raised,
  blurred, dimmed, resolving) so the eye follows that one card.

  | cell | who acts | what happens |
  |---|---|---|
  | open → awaiting | he answers | the submit morph restates the card in place (the typed text lifts from the box into the answer, a ripple), then the regroup travels it to its new heading, lifted. The wisp starts at its dim keyframe and breathes up, so it arrives rather than snapping on. |
  | awaiting → folded | the loop folds it | travels, lifted; the height collapses; the departing body dreams away |
  | open → folded | the loop answers it itself | the same, with no wisp ever |
  | folded → open/awaiting | a follow-up reopens it | travels, lifted; the height grows; the arriving body eases in |
  | awaiting → open | the loop drops the answer | travels, lifted; rail and wisp leave with the old node |
  | same state, moved | a neighbour left, a note landed | slides; if it also resized, the height travels |
  | folded ↔ expanded | **he** clicks the summary | the same snapshot and the same regroup — his own expand is not a special case, and routing it through the shared path is what gives it the neighbours' motion for free |
| thread ↔ expanded | **he** opens a settled thread | the same cell one level down: the card resizes, so the cards below it are carried. The reveal and the ghost are the disclosure's own contents, not the card's (see *`expand` is structure*) |
  | gone | the entry was deleted | dreams away at the rect it occupied |
  | arrived | a new question | `.dreamin`: snap, then ease in |

  Four things in there are not obvious and all four were bugs first:

  - **Height, never scale.** `flipDock` morphs by `scale()`, which is right
    for the review dock, where the card really does change column. In the
    list the column never changes but the height now can, by a factor of
    fifteen, because folding collapses the card. A scale morph would squash
    the text by that ratio at frame 0 and read as a stretch, not a fold.
  - **A body that leaves fades; a body that arrives eases in.** *"When it
    folds in, the body shouldn't disappear all at once"* (human,
    2026-07-25). The new node is already the folded one, so there is no live
    body left to animate — which is what the up-front clone in
    `snapshotCards` is for. `dreamAway` ghosts it at the rect it occupied,
    **clipped to below the line the survivor still fills**, on the page's one
    departure idiom. Unfolding is that moment run backwards, so the revealed
    children get `.qreveal` + `.dreamin`.
  - **Cards are processed in DOM order, and that is load-bearing.** A
    resizing card's own height animation carries everything below it —
    continuously, for free, and welded to the card it is following. So the
    FLIP only handles the **residual**: whatever moved for some other reason.
    Restoring a card's old height before the next is measured is exactly what
    makes the next card's `now` mean "where it would be if only that resize
    had happened". FLIPping the full difference instead moves a neighbour
    twice, once by transform and once by layout, and snaps it back at the end.
  - **A ghost is a corpse and must not keep the card's address.** It is a
    clone appended to `.wrap`, so it arrives carrying `data-qid` — and every
    `.qa[data-qid]` walk on the page would then find it: `snapshotCards`
    would capture its absolute rect as the question's, `restoreCardState`
    would restore his typing into it, and a per-frame trace measures it
    instead of the card animating underneath (which is how this was found).
    `dreamAway` strips the identity at the door rather than teaching six
    lookups to skip it.

  The guard is `dev/capture/states.mjs`, and its assertion is deliberately
  about **outcome, not mechanism**: every card that ended somewhere else
  visited many intermediate positions. The first version demanded an inline
  transform on everything that moved and was wrong — a card riding an
  animated height above it travels perfectly with no transform of its own,
  and the mechanism check would have forbidden the better motion.
- **The dream dissolve** (route change). The outgoing view becomes a
  `.ghost` (z-index above `#view`) that liquifies into a swirling mist and
  lifts up and toward the viewer as it fades — dissolving *in front*. The
  incoming view surfaces from *behind and below*, in depth: `.wrap` carries
  a `perspective`, and `#view.enter` starts pushed back (`translateZ`),
  lower and scaled down, at true opacity 0, then drifts forward into focus.
  ~1.15s with a hazy dwell (`DREAM_MS`); opacity + 3D transform ride CSS,
  the mist is JS-enveloped. The `#dreambg` shader stirs in sympathy (a
  `warp` pulse deepening the curl advection + a centred twist). Each
  destination has its own turbulence `SEED` and `TINT`.
- **True-zero start — the enter-snap rule.** Because `#view` carries an
  always-on opacity/transform transition, the enter (start) state **must**
  set `transition:none` so it *snaps* to opacity 0 / pushed-back; otherwise
  adding the class animates *toward* 0 and the class is removed a frame
  later, so opacity never leaves ~1 (the incoming "pops in" instead of
  fading up from nothing). Snap the start, force a reflow, then remove the
  class on the next frame to animate in. A brief opacity delay keeps it
  genuinely absent for the first ~150ms so it emerges rather than blends.
- **The mist filter — the load-bearing rule.** Put *all* softening (blur
  **and** displacement) inside **one** SVG filter
  (`feTurbulence`→`feDisplacementMap`→`feGaussianBlur`) driven per-frame
  from rAF; keep only `opacity`/`transform` on CSS. You cannot CSS-tween a
  `filter` that holds a non-interpolable `url(#…)`, and its cost scales with
  filtered-layer *area*, not turbulence octaves. Clear the inline filter at
  rest so the settled element is pixel-crisp and zero-cost.
- **Lifted-hero FLIP** (shared-element morph, e.g. question → review dock).
  Measure the source rect, render the destination, invert to the source,
  play to identity — but the dream twist is a blurred, low-opacity drift,
  not a reveal.js slide. When the morph crosses a full view-swap, **lift the
  hero above the dissolve** (z-index, higher opacity floor, less own-blur)
  and make its glide **outlast** the dissolve, or it drowns in the page mist
  and reads as "page changed + thing appeared" rather than "thing
  travelled".
- **The ripple.** A soft expanding ring marks a received command; a felt
  pulse, not a modal.
- **The composer's sliding indicator.** Choosing a command kind slides the
  selection background to it (~.3s, the dream easing) — the composer's one
  piece of crisp motion. It lands without sliding on open and on reflow; see
  The composer.
- **Answer-submit morph.** Submitting an answer (button or **Ctrl/Cmd+Enter**,
  which works from any answer box) *is* the confirmation: the card reshapes
  in place into its answered-awaiting-fold state and the typed text lifts
  from the box into the rendered answer (the lifted-hero FLIP — the answer
  is the tracked element), a ripple accenting it. The live re-render is held
  ~1.6s so the morph settles before the loop's fresh data regroups the card.
  reduced-motion swaps straight to the answered state.
- **The awaiting-fold wisp — the one standing exception to "opt-in".**
  Everything else on this page moves only in response to something; the
  awaiting-fold state breathes continuously, on purpose, because it is the
  only genuinely **in-progress** thing here: the human has answered and the
  loop has not yet folded it. Say that out loud whenever this rule is
  re-read, or it looks like the opt-in rule rotted. A wisp of accent drifts
  along a 2px rail and across the `answered · awaiting fold` label, ~5.5s,
  **fading in and out** rather than sweeping — a breath, not a spinner, and
  ambient in the way the shader is. One envelope duration and easing for both
  halves, so they read as one organism rather than two effects.

  **The cost is bounded by construction, not by a measurement that can
  drift**: the keyframes touch only `opacity` and `background-position`, and
  the animated boxes are a 2px rail and one short inline-block label (the
  label is inline-block precisely so its box hugs the words instead of
  invalidating a full-column strip to say nothing). Measured anyway:
  p95 frame time 16.8ms with the wisp, 16.9ms with every animation killed —
  indistinguishable at vsync.

  Under reduced motion the wisp **holds still at its brightest** rather than
  disappearing: the state must still read as in-progress with no motion at
  all. Legibility is safe by construction too — the gradient's darkest stop
  is `--dim`, the colour the label had before it moved.

  `dev/capture/wisp.mjs` guards all three claims, and one of its checks is
  worth knowing about: counting direction reversals does **not** tell a
  breath from a sawtooth, because a sweep that snaps back to its start also
  turns around twice per cycle. A deliberately introduced one-way sweep
  passed the first version of that check. What separates them is how *long*
  the fall takes — a breath spends about as long fading out as fading in, a
  sawtooth spends one frame — so the assertion is on the fraction of moving
  samples that are falling.
- **Reduced-motion is a hard contract.** `prefers-reduced-motion` changes
  *timing, never function or legibility*: route swaps are instant (no ghost,
  no mist, tint/seed snap, no `warp`), the composer shows/hides at once, its
  selection indicator jumps rather than slides, the dock appears without a
  FLIP. Verify it on anything that moves.
- **Two invariants that always hold.** (1) *Settled crispness* — at rest,
  no filter, text wins the luminance contract, nothing blurred. Transient
  mid-transition haze is fine. (2) *Frame continuity* — the `#dreambg`
  canvas never unmounts, pauses, or resets across navigation; its frame
  tally stays monotonic. Both are guarded by tests; keep them green.

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

- Writes are limited to the two human-authorized localhost paths (`/answer`,
  `/command`); nothing else mutates. Steering stays lightweight.
- No historical analytics; a live window, not a metrics store.
- No public exposure; localhost only, by construction.
