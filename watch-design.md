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
- **Read-only, eight explicit write exceptions** (all human-authorized under
  loopback or explicit trusted-LAN authority): POST `/answer` appends an answer
  to the matching Open entry in `questions.md`; `/ask` appends a human question
  to `answers.md`; `/comment` appends a human note to an Open or Answered
  question; `/command` appends source-tagged steering to
  `.dreamwork/watch-events.log`; `/tint` persists the project colour in
  `.dreamwork/watch-tint`; `/run-mode` commits the main-dreamer pace into
  `.dreamwork/run-mode` (#290); `/posture` commits the three-axis posture
  override into `.dreamwork/posture` (#445); `/deploy` schedules `just deploy`
  (#462, **loopback peer only**, single-flight — trusted-LAN Host/Origin is not
  enough for a command that restarts the server). Answer, ask, comment and
  command always append one line to `watch-events.log`, waking the loop.
  `/run-mode` and `/posture` dual-write their file and append **one** events
  line only when the value actually changes (identical final is silent). Tint
  and deploy deliberately do not wake: tint is presentation state; deploy
  restarts the dashboard process. Every other POST is rejected; every other
  route reads.
  All file access goes through `resolve_confined()` (rejects absolute, `~`,
  traversal); `/filedata`, `/filebytes` (#336) and `/reviewraw` are all
  behind it.
- **`/summary.json` — a redacted, whitelist view of `collect()` for any
  non-loopback consumer** (Q5; `plans/hub-public-auth.md` §11.2,
  `plans/hub-ssh-auth.md`). `/data.json` serves `DREAMWORK.md`,
  `questions.md` and `lessons.md` **in full** plus parsed entries, dream
  transcripts and `status.json` — the loop's whole operating state, including
  the operator's unfinished thinking — so it is unfit to expose. `summary()`
  (served at `/summary.json`) replaces it for dreamhub reading across
  projects and any later authenticated remote reader: it keeps the counts,
  health and operational metadata and drops every full-text and parsed-entry
  field.
  **Redaction is a whitelist, never a denylist.** `summary()` names the
  fields that may leave (`SUMMARY_ALLOWED`) and pulls only those; it never
  iterates `collect()`'s keys, so a field `collect()` grows cannot appear
  unless deliberately classified. Whether a new `collect()` key may leave is
  a decision recorded in `SUMMARY_ALLOWED` or `SUMMARY_DENIED`, and the
  partition test (`TestSummary.test_summary_classifies_every_collect_key`)
  is what notices that decision got made — a brand-new unclassified key reds
  until classified rather than passing through by default. That is the heart
  of the endpoint: the next field someone adds is safe by construction, not
  by vigilance.
  **The whitelist, field by field.** `generated` (build stamp), `open_questions`
  (an int count), `questions_health`/`answers_health` (enum tokens — `ok`/
  `missing`/`unreadable`/`empty`, never prose), `tint`/`run_mode` (closed
  enum values, not his words), `posture` (only the four enum/int axes — pace,
  asking, delegation, source — never the display label), `skill_identity`
  (commit + skill_version), `burndown_counts` (only the three scalar counts —
  open/arrived/landed — never the working-cadence time series or error prose),
  and `skill_version` (the one safe scalar pulled out of `files`, projected
  from `files.skill-version`). A ledger or question **title** is often a
  description of his words, and a question title **is** his words — so neither
  titles nor any parsed entry leaves, and the decision was made at the
  category (everything carrying his words is denied by name) rather than per
  title. Everything else — full documents, parsed entries, transcripts,
  handoffs, `status`, `git`, `deployed`, `plugin_commands`, the machine path
  — is denied by name in `SUMMARY_DENIED`.
  **It rides the same `_preflight()` authority gate as every other GET**; the
  endpoint adds a read surface, never a wider authority. Where it may listen
  is a separate ruling (`#275`/Q3) the human has not given, and this lane
  changed no bind address, host allowlist, flag or listener. Guard:
  `dev/capture/summaryjson.mjs` — a fetch-only (not browser) content/leak
  check, with leak strings DERIVED from the fixture's real documents and
  their PRECONDITION asserted (the probe really is in `/data.json`).
- **Port** persisted to `.dreamwork/watch-port` (random 3000–63000 once)
  so bookmarks survive restarts; port-in-use error names the port.
- **Live reload**: poll `/mtime` ~2s → re-fetch `/data.json` → re-render
  the active view in place (no transition), including a `/review` question
  dock. The tick uses the router's `buildCurrent` seam rather than a partial
  route list; card drafts, selection, resize, scroll and focus ride the
  existing stable-`data-qid` snapshot (in-memory, so it carries a draft
  across a tick but not a reload — a `dw:adraft:` `localStorage` backstop
  carries it across the reload instead, see "The answer box's half-typed
  draft" below), while the artifact iframe browsing
  context stays mounted at its current URL and scroll. Dashboard review
  artifacts are ordered by filesystem **birth / created** newest-first (#463),
  with ascending filename as the deterministic exact-created tie-break.
  POSIX `st_ctime` is *not* used — it is inode-change time, not creation.
  Birth comes from Linux `statx` `stx_btime` (or `st_birthtime` on BSD);
  when unavailable the row is a named state (`created unknown`) and sorts
  after every known-created artifact — never silently under mtime. The
  displayed primary age seconds are derived from that same birth ns; mtime
  is kept only so a secondary *"modified X ago"* (dimmer, chrome ` · `
  separator, same idiom as #456) can appear when created ≠ modified — and
  "differs" means **the rendered figures differ**, not the nanoseconds. Writing
  a file sets birth and then the content write moves mtime, so 24 of this
  repo's 28 artifacts differ sub-millisecond and exact inequality would print
  `3d old · modified 3d ago` on nearly every row. The server therefore marks a
  **candidate** (`show_modified`: birth known and mtime later) and `ages()`
  decides, beside `ageStr` itself, so no threshold is invented and the
  formatter is never mirrored. A suppressed secondary is dropped inside
  `ages()`, which `setContent` runs **before paint** — so it is absent from the
  first frame rather than vanishing out of a painted one. A live
  created reorder keys each stable review row by filename and runs it through
  the existing list FLIP: normal motion travels without overshoot, while
  reduced motion places rows instantly. Same-origin artifacts
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
- **Single-document router**: `/`, `/questions`, `/answers`, `/file`,
  `/review`, `/question`, and `/research` serve one shell. `/answers` is the distinct human-to-dreamer
  question ledger while `/questions` remains dreamer-to-human. `/question?qid=<title>`
  (#452) focuses ONE question on its own page — a surface the loop's list
  churn cannot shift under him mid-answer; its key and resolution contract
  are specified under *The focused question* below. `/research` (#484) lists
  the built research artifacts under `.dreamwork/docs/research/` — the same
  listing shape as `list_reviews` (non-recursive, so `src/` sources stay
  invisible), with **no** questions.md pairing and no archive-on-answered
  lifecycle, which is the review *surface* research deliberately does not
  reuse. `/research?p=<name>` views one artifact through the review view's
  own idiom: the raw self-contained page (served at `/researchraw`) in the
  same `#reviewwrap`/`#reviewframe` iframe, borrowing `body.review`'s wide
  column for the doc half only — the listing keeps the normal column. The client
  router renders the view; pushState/popstate drive
  the URL. The `#dreambg` canvas is a sibling of `#view` — never unmounted,
  so the background survives navigation. Route changes dissolve — the
  liquify mist is the human's moved-texture mechanism (#453: ONE cached
  feImage field drifted by feOffset, applied to the ghost only, since #449/#453
  measured the per-frame cost as the COUNT of full-page filter rasterisations
  and nothing else; the arriving view's haze is compositor CSS blur, measured
  free; see transitions.md *The mist filter*); reduced-motion swaps instantly.
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
  overlay — on every view, zero cost when off. The three text readouts
  refresh on a **100ms window** (fps scaled to a per-second rate from the
  window's count/elapsed, so a 60fps tab still reads ~60 rather than the
  raw 100ms count); the **sparkline paints every frame**, so it reflects
  the latest sample immediately. The graph hugs the right-hand wall — the
  canvas is narrower than the readout text beside it, so `margin-left:auto`
  pins its right edge to the text's right edge rather than parking at the
  box's left. **The project wordmark yields the overlay's column on a wide
  window** (#435): mounting the overlay sets `body.dev`, and `.hproj` takes
  a right margin equal to the overlay's reserved `min-width` plus its right
  inset, so the two never paint on top of each other. Below 720px that same
  margin wraps the title bar, so the overlay drops under the chrome instead
  and the wordmark keeps the trailing edge. The counter stays either way.
  Settled chrome, not a gesture — no transition, reduced-motion parity free.
  Guard: `dev/capture/devoverlay.mjs`.

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
a send the server refused, code this page is not actually running (`#140`), and
a push channel that cannot reach him (`#190`). All are the same fact — the
channel failed and no number on the page would have said so. Nothing that is
merely *important* gets it; if a further use appears, the question to ask is
whether it is really this one.

### Type & geometry

One mono stack, two sizes (heading `1rem`, body `.8rem`, labels `.7rem`).
No cards, borders-as-decoration, pills, or shadows in the reading views —
structure comes from whitespace and dim uppercase labels (`.label`, letter-
spaced). Reading column is `max-width:72ch`, centred; there are two
deliberate width exceptions — the review view (`body.review` widens the
column for the artifact + docked question, and **he sets the ratio between
them** — see The review pane) and the file view (`body.file` widens it to
`110ch` for source — see The file view's source pane). Dividers are
hairlines (`--line`), not boxes.

### The file view's source pane (#351)

His ask, typed from `/file?p=lint.py`: *"syntax highlighting for source
code files, and a bit wider of a body + no line wrapping."* Three changes,
and the two mechanical ones exist to serve the first — he wants to read
code as code.

- **The highlighter is #339's, reused, never rewritten.** `/filedata`
  tokenises server-side through review_artifact.py's public `highlight()`
  (the tested one — two highlighters would drift) and adds an `hl` field to
  the response ONLY when the extension names a supported language
  (`_FILE_LANG`: py, json, sh/bash, js/mjs/cjs, html/htm, sql). The client
  never tokenises and never invents markup; it chooses between the server's
  two renderings. An unknown extension renders plain — #339's never-guess
  rule, inherited whole. The pane's `textContent` is still byte-exact the
  file, the same bar #252 set for the Source mode.
- **The caching is a decision, not an inheritance.** #339 tokenises at
  build time because an artifact is frozen; `/file` renders on request, so
  the highlighted markup is cached by path and validated by
  `(mtime_ns, size)` — the same staleness predicate the whole dashboard
  already trusts (`/mtime`), and stat is cheap beside the read the response
  does anyway. A content digest was refused: it costs a full read per
  request to detect what mtime already names, and "rewritten with identical
  mtime and size" is the edge the live-reload mechanism has always
  accepted. Bounded (32 entries); a stale entry is a highlight one edit
  behind, never stale bytes — the content is read fresh every request.
- **The #252 collision is an explicit condition, not an absence.** A
  markdown file's Source mode renders plain by NAME
  (`isMarkdownFile(param) && mode === 'source'`), so the guarantee does not
  depend on what the server chose to send. The pytest check that used to
  assert no `tok-` anywhere on the page is narrowed to that path (evaluated
  against the real `buildFile`), not deleted.
- **Wider body: `body.file .wrap { max-width:110ch }`.** A reading column
  sized for source, not review's 1360px pane. The class is toggled beside
  `review` at the same three route-commit sites, so the column glides on
  the same `body.wsliding` mechanism and a direct load arrives already
  wide. Guarded as a *derived* comparison: `/file`'s column against the
  same browser's dashboard column, never a literal.
- **No line wrapping, scrolling inside the pane.** `#filebody > pre` takes
  `white-space:pre; overflow-x:auto` — the idiom `.md pre.mdcode` already
  kept for fences, reaching the pane it was meant for. The trade is real
  and is the one he asked for: a long line scrolls horizontally INSIDE the
  pane, and the page never scrolls sideways (asserted at desktop and at
  390px, where the pane holds 349px of a 390px viewport). Every other
  `<pre>` on the page keeps `pre-wrap`. The markdown Source pane takes the
  same nowrap — its bytes are the file — and that is the change #252's
  note predicted.
- **The palette is the artifact's, value for value**, spent only inside
  the pane, with one rename: numerals and types take `--amber`, never
  `--warn` — on this page `--warn` means broken (#136) and a numeral is
  not broken. The three code tokens (`--accent2`, `--ok`, `--amber`) are
  declared in `:root` beside the ramp they extend. The generic inline-code
  chip is reset inside the pane (`#filebody > pre > code`) so it does not
  plate the block.

Guard: `dev/capture/filehl.mjs` (own target, ephemeral port): token kinds
derived from the fixture's bytes, byte fidelity on the highlighted pane,
distinct computed colours, the width comparison, in-container scroll at two
viewports, the never-guess plain path, the shimmed-offer Source collision,
and reduced-motion parity. No motion trace: the surface is static content,
and the width glide is review's guarded mechanism reused verbatim.

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

**Orientation before the ask (#455).** He typed from inside a review
artifact: *"I feel lost when i read these half the time b/c i have no
context."* Headline and sub already summarise every page, and they did not
stop that — so a second summary line is the wrong fix. What orients is a
small set of answers a cold reader can take from the first screen:

1. **what this is** — design, analysis, plan, go/no-go;
2. **which decision** it serves, named by task id, in one clause;
3. **why he is being asked now** — what triggered it, what is waiting;
4. **what happens if he says nothing** — blocked, a default taken, or
   parked.

An audit of the built corpus found about half the first screens already
answer three of those four. The structural hole is (4): almost nobody
writes the cost of silence unprompted, and it is the most decision-
relevant of the four. So the *voice* contract is all four answers; the
*build* contract enforces only (4) — one sentence in
`<... id="if-silent">`, refused when absent or empty, exemptible by
`no_if_silent: <reason>` for a page with no parked decision. Same shape
as the `#ask` contract (#436). No word-count rule: refuse on absence,
never on size. The header scalar `context:` remains the short toprail
crumb and is a different thing.

Worked example: `269-draft-durability.html` (the page he was reading when
he felt lost). Low scorers on the first-screen audit are a follow-up list,
not a bulk rewrite — surfaces get smaller, not longer.

### Essential marks — the flag rail (#367)

His idea, typed from a twenty-screen review: *"pointer labels at the most
important parts. like the absolute essentials. then i could have a next/prev
button too. something like those little thin postits that lawyers use to
indicate key points and where you need to sign… (Sometimes they are quite
long)."* A lawyer's flag marks **where you must act**, at the height of the
clause — so a mark is a different axis from `nav` (structure), and merging the
two produces the second table of contents he did not ask for.

**A flag is a child of its passage, not a decoration on a box.** Blocks in a
section run from `.read` (614px) to the full wrap (1120px), so a flag pinned to
its block's right edge would sit in a different place for every kind of
passage. It anchors instead to the **reading column's right edge**, at its
passage's top — which is free in both axes without any script: the flag is a
child of the marked element (the positioning ancestor, `.is-marked`), so `top:0`
is the passage's own top, and `left:calc(var(--measure) + .4ch)` is the column's
edge. The artifact is offline-clean (no script ever), so the rail is BUILT into
the HTML at build time by `review_artifact.py`, not positioned at read time.

**The flag's outer box inherits the body font on purpose.** `--measure` is
`78ch`, and `ch` resolves against the element that uses it — so a single-element
flag at `.66rem` would place itself at the **tab's** narrower column, not the
reading column's. `.marktab` (outer, body font) carries the `left`; `.markflag`
(inner, `.66rem`) is the visible postit. Two elements is the price of one honest
column.

**Two lines, grow-to-fit, nobody truncates** (his 2026-07-28 05:35 ruling,
which overrode a one-line ~12-character builder-truncated flag). A ~6-word label
fills `.markflag`'s `max-width` and wraps to two lines; the worst case measures
~184×32px (`.dreamwork/docs/measurements/367-two-line-tab-geometry.md`).

**Above the cliff, the rail; below it, the collapsible strip.** The worst-case
flag fits inside `.wrap` down to ~830px (measured), so the rail shows at/above
the existing **860px** breakpoint — reused rather than inventing a seam, with
~26px of margin to spare. Below it the whole rail is `display:none` (absent, not
a broken flag) and the **markstrip** shows instead.

**The strip is option C with a collapsible index** (his 2026-07-28 15:11
ruling): collapsed by default at walk height (~32px); a double chevron (`»`) on
the RHS as the expand affordance; expanded reveals the labelled marks. The
control is a native `<details class="markstrip-panel">` — keyboard parity is
Enter/Space on the summary; `aria-expanded="false"` documents the
default-collapsed contract at load; the live expanded state is the HTML `open`
attribute (the same disclosure idiom every other `<details>` on the page uses,
and the one screen readers already announce). Expand/collapse reuses
`details::details-content` (transitions.md) — no second gesture.

**Implementer decisions, fixed in the plant:**
- **List sits beneath the walk row** (summary stays when open). Next/prev remain
  reachable while the index is open; replacing the walk would hide the control
  he chose as the default chrome.
- **Expanded state does not persist.** No `open` attribute, no script, no
  localStorage — every load is collapsed. Offline-clean forbids the machinery
  persistence would need, and "collapsed by default" is the ruling.

**Walk tracking below the cliff.** With no script, "current" is still
`:target`. The strip's walk row shows an idle "N essentials" until a mark is
targeted; then generated `body:has(#id:target)` rules flip to that mark's
`‹ n / N ›` next/prev. Same fragment links as the rail.

**"Current" is `:target`; next/prev are real fragment links.** No script means
no scroll-spy: the current passage is the one navigated to (`:target`), and the
flag's opacity lifts to full when its passage is targeted (the page's own
state-change transition, `.45s`, instant under reduced motion). Next/prev live
inside the current flag's `.marknav` (above the cliff) or the strip's walk row
(below it) and walk the marks in document order as plain `#id` links — so the
arrows read as a single control that follows the current mark, are
keyboard-operable, and work offline. Each marked host carries `tabindex="-1"`
so fragment navigation announces the passage to a screen reader.

**Next/prev lands SETTLED, not as a journey.** A long-range smooth scroll is
already refuted (the #229 v2 review's 1.5s one failed the gate); the template
declares no `scroll-behavior`, so fragment navigation is an instant jump — the
function, which reduced motion keeps. `dev/capture/markrail.mjs` proves it
traced part-way: an instant jump visits no frame between its ends, a smooth one
fills the window. The red is `html{scroll-behavior:smooth}`.

**Two marks closer than a tab height are the renderer's problem, not the
author's.** The densest real pair (a section and its first marked `.read`) sits
~29px apart against a ~32px tab; the builder cannot know pixel gaps (the
artifact is script-free), so it staggers a flag **nested** inside another marked
element — the honest structural proxy for "right next to" — and the template
offsets a staggered flag down rather than sideways (a sideways push would
overflow the wrap below ~1120px). The guard re-proves no two flags overlap in
pixels.

`dev/capture/markrail.mjs` guards the rail: the worst-case flag fits inside
`.wrap` at the cliff and never clips the page edge; it anchors at the column;
next/prev lands settled (normal and reduced); the arrival's state change
travels; below the cliff the rail renders nothing (the strip is 2b's surface);
flags are focusable and the current passage is announced; the close pair does
not overlap. It builds its own artifact through the real builder and loads it
via `file://`, like `marktab-geometry.mjs` — the rail is a property of the
artifact, not the server. The strip's structure and collapse contract are held
by `test_review_artifact.py`'s markstrip suite.

### The review pane (#305)

`/review` is **one window-tall pane of two columns**, not two documents
stacked in a scrolling page. His report, sent from `/review?p=…&q=…` while he
was reading one: *"should be able to scroll the question alongside a review
document, and the answer/add note input should stay glued to the bottom in
line with the bottom of the review document… an invisible vertical bar
between review doc and question being answered that allows dragging
left/right… we also can extend the height of the review doc and RHS column if
the height of the window allows."* Before it, the artifact stopped at `74vh`
and the docked question ran on underneath it, so its answer box sat a
thousand pixels below the fold: reading and answering were two scrolls, and
you could not do the second while looking at the first.

- **The pane is measured, not assumed.** `fitReview` writes `--rvh` from
  `window.innerHeight` minus the pane's own `offsetTop` and the body's bottom
  padding. `offsetTop` rather than a rect because it is **layout** and cannot
  be read through the dissolve's transform (`transitions.md`), and it is
  refitted from `renderChrome` as well as `setContent`, because the pane's top
  *is* the bottom of the chrome and the chrome is written after the view.
  The `calc(100dvh - 12rem)` in the CSS is a floor for the frames before the
  first measurement, not the value.
- **`min-height:26rem` is what keeps a short window honest.** Below that the
  page starts scrolling again instead of crushing two columns into slivers.
  Measured: a 1240px window gives a 1080px pane with the page not scrolling at
  all; a 520px window gives the 416px floor and 56px of page scroll. The pane
  **follows a resize** rather than being measured once at load, which is the
  half of *"if the height of the window allows"* that a single-height
  assertion cannot see.
- **The gutter IS the splitter.** The 1.3rem the eye already reads as space
  became a `role="separator"` with a value: invisible at rest, a hairline on
  hover/focus/drag, `col-resize`, and **operable from the keyboard** —
  arrows ±2%, shift ±8%, Home/End to the floors, Enter or double-click back
  to 70%. A drag-only affordance is one a keyboard cannot reach, and this one
  is invisible as well.
- **It needs `z-index`, and the reason is not cosmetic.** An
  answered-awaiting card hangs its accent rail `.9rem` into that gutter
  (`.qa.awaiting`'s negative margin) and, as a positioned sibling later in
  the DOM, wins the hit test — so without it the bar is dead to the pointer
  in exactly the state he is in one second after answering.
- **The floors live in CSS**, as `clamp(32ch, var(--rsplit), calc(100% -
  26ch))`, for #108's reason: a clamp holds on every frame and at every window
  width, where a JS re-derivation is always one frame behind the layout it is
  correcting. 30–82% is the range in which both columns still read.
- **Where the width lives:** `localStorage['dw.review.split']`, read by
  `buildReview` at build time and emitted into the markup, so a fresh
  `/review` *paints* at his width instead of correcting to it a frame later.
  It is a preference, not shared state, and it needs no snapshot seam: the
  tick replaces only `#qdock`, never `#reviewwrap`.
- **The question's BODY is the scroller** — not the dock, so `answering` stays
  put as a column head, and not the card, because the card holds the answer box
  too and a scrollport that holds the box cannot fade its text at the box
  without fading the box (#326, below). `qaInner` therefore wraps everything the
  question *says* — its title included, so it still scrolls under `answering` —
  in a `.qbody` element, and leaves `.qcompose` as that wrapper's sibling.
  `scrollbar-gutter:stable` keeps a live re-render from re-wrapping the text
  when the scrollbar comes and goes.
  **Everywhere else `.qbody` must not exist, and `display:contents` is how an
  element says so:** no box is generated, so margins collapse exactly as they
  did before the wrapper, and — the half that is load-bearing rather than
  convenient — no box means no mask and no scrollport, which is what the narrow
  layout wants back. Proved rather than argued: every `.qa` rect and every
  visible descendant rect on `/questions` and the dashboard is byte-identical
  with and without the wrapper. Two things read the wrapper's children as the
  card's own and both look **through** it — `cardBody` (the fold's reveal and
  ghost, where a `display:contents` element would have no rect to animate) and
  `sendComment`'s first-thread insert (which would otherwise land a note
  *outside* the scroller, wedged between the question and the box). A folded
  entry keeps its title out of the wrapper and has no choice: the title *is* the
  `<summary>`, which must be the disclosure's first child.
- **The answer box is glued to the foot of the pane**, ending on the same line
  as the artifact — and it is glued **by construction**: it is the last flex
  item of a card that does not scroll. `.qcompose` stays the shared component
  three other surfaces render and four functions address through the card
  (`snapshotCardState`, `setCardMode`, `submitCard`, the mode group) — a copy
  for this one route would be a second thing to keep true. The card's own `1rem`
  bottom margin goes: *"in line with the bottom"* is a measurable claim and 16px
  is a visible miss. `padding-bottom:.3rem` keeps air under the mode buttons
  without a margin that would move the border edge off the artifact's line.
  **#305 reached the same geometry with `position:sticky` + `margin-top:auto`
  and paid for both; #326 removed them.** Sticky only holds a box the flow would
  push out of view, so a *short* question left it floating mid-column — at a
  1240px window the artifact ended at 1200 and the box at 974 — and the
  `margin-top:auto` that fixed that made every child of the card a flex item, so
  its internal margins stopped collapsing and the dock card ran ~20px taller
  than the same card on `/questions`. With the scroller taking the leftover
  space, the box needs neither, and the body is a plain block box again that
  collapses margins the way `/questions` does.
- **Two fades, one mechanism, mirrored.** *"The black stuff around the answer
  box to emulate the fade thing is ugly. The text itself should fade, not be
  covered by fake fade. And the buttons and text box shouldn't have anything
  behind them (should look like it did before)"* (human, 2026-07-27, #326, about
  the band #305 shipped an hour earlier). Both ends of the column are now a
  single `mask-image` on `.qbody`: **the glyphs go translucent and nothing is
  painted at all.**
  - **Why the band was there, and why the objection to a mask stopped
    applying.** #305 argued that *"a mask over the scroller cannot be told about
    the box, and would dim his last line at the end"*, and that is true of a
    scrollport that **contains** the box. It is not true of one that stops where
    the box begins. A band, meanwhile, can only emulate a fade by painting
    `--bg` over whatever is behind it — on this page that is the living shader —
    and it has to be as tall as the box, so the box ends up sitting on a black
    plate. That is the thing he was looking at.
  - **At the foot** the mask's transparent edge *is* the scrollport's bottom
    edge, which is exactly where the text used to run into the band, and the box
    is outside the masked element entirely: nothing behind it, nothing dimming
    it. **At the head** the same gradient, mirrored: making the body a scroller
    left the first visible line sliced in half directly under `answering`, which
    reads as a rendering fault rather than as scrolled text.
  - **Two depths, `--qfade` (head) and `--qfoot` (foot), both `24px`** and both
    registered properties, so each edge **arrives** and **departs** rather than
    blinking (`transitions.md`). One property could not hold both, because the
    two ends lift on different states. A registered property's `initial-value`
    must be computationally independent, so it is `24px`, not `1.5rem`. The
    `transition` shorthand sits on `.qbody`, which has no other transition to
    clobber — the same declaration on `.qdock > .qa` would replace `.qa`'s list
    wholesale and silently take a card's travel away on the one route that also
    re-groups cards.
  - **Both lift where they would be lying.** `syncDockFade` reads one scroll
    distance and sets `atend` (nothing passes under the box, so a fade there
    would dim his last line to hide nothing — *his own exception*) and `attop`
    (nothing is above, so the question's own title stays crisp). It is read
    from the scroll, never remembered, and called from the three places the
    answer can change: the scroll, a resize, and a re-render — the last of
    those from the tick, **after** the restore that puts the scroll back, not
    from inside the swap, because one line earlier that scroll is still 0 and
    the answer would be about a question he is not looking at. The listener is
    delegated on the **capture** phase, because `scroll` does not bubble and
    the element it watches is replaced every two seconds.
  - **A poll is not a gesture, so the state rides across the swap.** The dock
    is replaced wholesale every two seconds and the server's markup carries
    neither class, so a fresh dock resolved the full `24px` first and eased to
    its real value one style pass later: **both edges of a question he was only
    reading dimmed and lifted, every tick.** The classes are therefore copied
    onto the incoming `#qdock` before it is swapped in — the same rule as the
    scroll position and the half-typed draft, which is that a re-render carries
    what the human's state was rather than starting from the server's default.
    Content that *grew* is the one case where the carried answer is wrong, and
    `syncDockFade` corrects it after the restore: that one IS a change, and it
    moves. Guarded by tracing both depths across a real tick at three scroll
    positions (`reviewsplit.mjs`), with the tick's own swap measured — the live
    scroller is marked beforehand and its absence afterwards is what proves the
    dock was replaced at all.
- **How far he has READ is state he owns** (#118's rule, with reading in
  place of typing): `snapshotCardState` carries the scroller's `scrollTop`
  under `read` and restores it, or a question he was halfway down would snap
  back to its first line every two seconds. Which element that is, is asked
  once — `qaScroller(card)` — because three callers in three script blocks
  would otherwise each carry their own answer.
  **And it goes back through `putScroll`, which CHECKS that it landed** —
  `refocus`'s rule (#179) applied to the other thing a restore hands back
  silently. A `scrollTop` assigned to a node the swap is one statement old is
  clamped to zero (the fresh box has no overflow yet as far as the assignment
  can see) and reports nothing in either direction; reading the value back
  both detects that and forces the layout that fixes it. The textarea's scroll
  restore and `restoreAskState` have had the identical latent bug since #118
  and now go through the same helper.
  **Stated as unguarded on purpose:** whether the clamp happens depends on
  whether something between the swap and the restore already forced a layout,
  so removing the retry leaves `reviewsplit.mjs` green — a check that cannot
  fail for its stated cause would send the next reader to the wrong file. The
  mechanism was measured directly instead: 209 assigned to a just-swapped card
  reads back 0, and reads back 209 with the layout forced first.
- **Narrow stacks rather than crushing.** Below 900px it is a document again:
  one column, natural heights, the page scrolls, and the bar is `display:none`
  so it leaves the tab order with the layout it belonged to. Nothing is glued
  and neither fade is drawn: there is no inner scroller, so both would be
  lying about the layout — the box is simply the end of the question again.
  **One line does all of it** — `.qbody` back to `display:contents`, the value
  it has on every other route — because an element with no box carries no
  scrollport and no mask. A rule that switched the fades off by name would have
  to name each of them, and after #326 they are one element's property.
  Checked at 700px and at a 390px phone, where the pane hangs 0px off the side
  and the answer box is 358px wide in the page rather than floating over it.
- **The mobile frame fills the window, not a fraction of it** (#434). Below
  900px the two-column pane is gone, and the artifact used to take a fixed
  `60vh` — 506px of a 844px phone, with ~200px of empty viewport under it
  (`scrollHeight === innerHeight`, so not off-screen content). That was the
  reading surface for every review decision. The narrow layout now reuses
  `fitReview`'s measured `--rvh` for `#reviewdoc`, so the frame takes the
  height the window actually gives under the chrome, and on the review route
  alone the body's bottom pad tightens from 2.5rem to 1rem (desktop keeps
  2.5rem / its accepted ~40px foot — the 40px "waste" on desktop *is* that
  pad). A docked question stacks below and the page scrolls (the narrow
  layout's own rule); with no dock the frame ends near the page foot and the
  dead space is under 24px. Desktop's two-column measured pane is unchanged.
  No height transition — measured layout, not a gesture. The fold constant
  in `dev/capture/above_fold.mjs` moves with this measurement. Guard:
  `dev/capture/devoverlay.mjs` (frame dead-space half).

Motion for all of it — the keyed step travelling while the drag does not, the
hairline arriving rather than blinking on, and both fades crossing rather than
switching — is `transitions.md`'s.
`dev/capture/reviewsplit.mjs` guards the pane. Every check that names a
behaviour was shown red against a build broken in exactly the way it names —
25 injections across the three increments. There is one exception and it is
named in its commit: the check that the question can scroll far enough for
*half way down* to be a middle is the guard's own anti-vacuity assertion, and
its failure mode was observed for real rather than injected.

`dev/capture/qfade.mjs` guards #326 in **pixels**, and it has to: every
assertion that could be written against the source text of the CSS would pass
the next well-meaning band, because that one would have a different selector.
So it hides the shader, paints the page a colour nothing in the design uses,
and reads the composited result back — *no pixel inside the answer box's own
box, or in the fade strip above it, may be the page's `--bg`*, which is the
only colour a band can paint. The same plate measures the fade as a fade: the
ink profile of the strip above the box falls toward the box and reaches the
page colour at its edge, with the precondition (there IS text in that strip,
and the question DOES overflow) derived at runtime and asserted first.

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
`buildReview`, `buildResearch`); the router swaps them. One `artifactRow`
factory spells the review/research listing row both surfaces share (#484) —
link, pip, and the #463 created/modified age pair — so a listing surface is
a parameter, not a second idiom. `answerRecord` is deliberately not
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

Add a view by adding a builder + a `routeOf`/`TINT`/`SEED`/`TITLE_ROUTE`
entry, not new chrome. **All three per-route tables, and the check is the
reason the list is exhaustive here**: `/answers` shipped missing its `TINT`
and `SEED` entries (#302) and then its `TITLE_ROUTE` entry (#318), because
each table's fallback is silent — a missing tint inherits the dashboard's hue,
a missing title inherits its empty route word. `test_watch.py` now derives the
destination set from `routeOf` and diffs all three, so a fourth table added
here must be added there too or the omission is invisible again.

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
  means, and it is the half he asked for by name. **Both sides stay** (#391):
  #277 cut the rule to bottom-only (`padding:0 0 .5rem`) to quiet that 8px
  shift when fold motion made it more visible, and every surface lost top air
  at once. The shift is the feature, not a fold-motion bug; do not re-cut it.
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
scroll, destination mode and every `<details>` inside it (#118, #111), keyed
by `data-qid`. The box's grown **height** (#177) is not carried — it is
re-fit from the restored content (`fitText(ta, false)` in `restoreCardState`,
snapped), so it cannot drift from the text the snapshot also restored. `snapshotFolds`/`restoreFolds` carries a section's
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

**A crumb never breaks inside itself** (`.crumb { white-space:nowrap }`), and
the one exception is the path, which must wrap anywhere (`.fdir` re-enables
wrapping for its own text). The rule exists because "the separator belongs to
the crumb that follows" is only true if it cannot be *separated* from it: a
crumb is an inline-block whose contents wrap like any other inline content, so
once #252's switch made the row long enough to wrap at 390px, the row broke
between the separator and the switch and left a lone `·` on a line of its own,
17px above the crumb it belonged to. A trailing **word joiner** (U+2060) in the
separator was tried first and does not work — it suppresses a break at its own
position, and Chromium still takes the break opportunity before an atomic
`inline-flex` box.

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

### Project identity in the title bar (#172)

The tab title already names the project (`dreamwork/<basename>`, #153). The
visible heading did not: `#htitle` carried only the route word (and on the
dashboard the app phrase `dreamwork watch`), so a multi-window strip and a
glance at the open page answered different questions. His words: show the
project name *"in a materially more prominent position within the visible
title section"*, and **"anchor what is invariant to an edge, not to a
variable-width neighbour"** — the route title varies; repo identity does not.

**`#hproj` is a sibling of `#htitle`, pinned to the trailing edge of
`.htitlebar`.** `margin-left:auto` plus `.htitle { flex:1 }` is the pin: the
route word grows and shrinks in the middle, and the identity's box does not
move when `questions` becomes `review 367-option-previews.html`. Measuring
that is the load-bearing check — present-on-one-route is not enough.
`dev/capture/projtitle.mjs` captures `getBoundingClientRect()` on `/`,
`/questions`, and a long `/review?p=…` and requires the three boxes to be
identical.

**Basename in the bar; full path on `title=`.** Popouts already show basename
*and* full path (`popoutShell`), because two checkouts can share a basename
and the band has room. An `h1`-adjacent full path is almost certainly wrong —
#284 already ruled that a long path competes with the subject — so the bar
shows the basename at the same size and `--bright` as the heading (identity,
not a dim breadcrumb), and the absolute `data.target` path rides the native
tooltip. The tab title keeps the compound `dreamwork/<project>` field; this
surface does not re-state the app word.

**It is a survivor, not a per-route arrival.** The name is invariant across
navigation, so `renderChrome` rewrites `#hproj` only when the text itself
changes and does not re-apply `.dreamin` on every route change. First paint
rides the standing enter-snap; reduced motion keeps the same text with no
arrival. The route word still dissolves and re-arrives as it always has.

### The file heading lockup (#284)

His report: a full path such as
`.dreamwork/docs/research/contextual-review-annotations.md` in the heading
**competes with the document itself**. It is the longest, brightest thing on
the page and almost all of it is address rather than subject. So the heading
splits in two, on one line each:

| line | what | token |
|---|---|---|
| the `<h1>` | the **basename** — the document's name | `--bright`, `1rem` |
| the crumb row | the **exact parent path**, selectable | `--dim`, `.8rem` |

**The heading is a real `<h1>`, on every route.** It was a styled `<span>`;
one top-level heading per document is what a screen reader's heading list is
for, and it is also what the copy button describes itself by
(`aria-describedby`). It carries **no** weight or size of its own
(`font:inherit; margin:0`) — emphasis here is luminance, and a UA-bold 2em
title would say "more important" twice while moving the metrics the `+` opener
is centred against (#123). The `+` still shares its centreline: `.htitlebar`
centres both boxes in the flex line, so a two-line lockup centres against the
whole lockup rather than drifting.

**The parent path is a CRUMB, and that is the whole reason there is no new
component and no new motion.** The crumb row is already this page's subdued
metadata line, directly beneath the heading, and crumbs are already keyed —
so the path arrives, departs and travels on the same keyed route transition as
`home` and the PiP glyph (see The persistent chrome). Animating path text on
its own would have been a second gesture for a smaller reason.

**It wraps anywhere and is never shortened.** His words, and there is no room
in them: *a path that lies about its own segments is worse than one that takes
two lines*. No ellipsis, no middle-truncation, no clamp, no reordering.
`overflow-wrap:anywhere` is what lets a directory segment longer than the
column break **inside** the segment — Chrome offers a soft-wrap opportunity
after `/`, so slashes alone are not enough. It is selectable text on purpose:
selecting it is the fallback when the clipboard is refused.

**Copy hands back the whole path.** `.fcopy` is a real `<button>` (so Enter and
Space activate it natively, and Tab reaches it in three stops) and it reads
`view.param` rather than carrying a `data-path`. Two reasons, and the second is
security: a second copy of the truth drifts, and `esc()` is
`div.textContent → innerHTML`, which escapes `<`, `>` and `&` but **not** the
double quote — so any `esc()`'d value interpolated into a double-quoted
attribute can be broken out of by a crafted query string. Reading the route
needs no escaping at all. `aria-describedby="fdir htitle"` names the metadata
line and *then* the heading, so the button announces as the full path in
reading order.

**Its focus ring is the page's own.** `.pipbtn` marks focus by taking the
accent alone, which is the same signal as hover; on a dark surface Chromium's
default ring computes to `rgb(16,16,16)` and is invisible. So `.fcopy` draws
a 1px accent outline with 2px of offset, plus an accent border — measured
against the resolved `--accent`, not against the browser's idea of focus.

**Both outcomes speak, on the page's ONE confirmation idiom.** `#fmsg` is the
composer's `.cmdmsg` component driven by the composer's `confirmationFor`
lifecycle (`transitions.md`, *Composer success confirmation*); the only thing
added for it is `note(text, ok)` — `claim` **with** the hold-and-depart
lifecycle, because a copy that failed a second ago is history rather than a
standing claim. Voice: success is `path copied`; failure is
`copy was blocked — the path beside it is selectable`, which names the fallback
instead of apologising. A route change hard-clears it (the chrome survives
navigation, so otherwise the message would follow him to another page and
describe a path no longer on screen); a **mode** change does not, because that
is the same file. Reduced motion keeps the ~5s hold and the same words and
drops only the fade — timing, never function.

**Where it sits costs no layout.** `.fmsg` is absolutely positioned at
`top:100%` of `#chrome`, inside the 2rem gap `#meta`'s bottom margin already
leaves above `#view`. A message that arrives therefore moves nothing at all,
which is the cheapest possible way to obey "appearing is a transition".

`dev/capture/filehead.mjs` guards it, and three of its checks are worth
copying:

- **the split is asserted as a reassembly** — `metadata + heading === the
  route's path`, character for character. Two remembered strings would pass on
  a dropped segment;
- **the wrap's overflow condition is derived at runtime** (the same text
  measured in the same font at `white-space:pre`, against the column's width)
  and the *painted* right edge of the furthest line box is compared to the
  column's. An earlier version compared `scrollWidth` to `clientWidth`, which
  are **both 0** on an inline box: `0 <= 1` passed over an ellipsis, over a
  nowrap, and over a page with no path at all;
- **the confirmation's departure is traced per rAF**, with reduced motion
  asserted to have *no* part-way frames on the same measure. "The message is
  gone" cannot fail on a snap.

Its focus-ring check is also a recorded finding: the first version asserted
only that *an* outline was drawn, and deleting this page's focus rule left it
green because the UA default satisfied it. A red run that comes back green is
the check's fault.

**H2 (clickable breadcrumb segments) stays refuted** until real directory
routes exist — a segment that navigates nowhere is a false promise (#243/#244).
**H3 refuted:** letting the long path keep the primary line is the reported bug.

### Rendered / Source (#252)

`.md` at `/file` reflows (see Prose rendering). Reflowing is right for reading
and wrong for **checking**, so the mode is a choice he makes: one compact
two-position switch beside the path, **markdown only**, `rendered` by default.

**The mode is a ROUTE, not a toggle.** `?view=source`, parsed in exactly one
place (`routeOf`) and written in exactly one place (`navigate`'s `url`), so a
link he copies preserves the intent he copied it with and the address bar can
never disagree with the page. Anything that is not `source` is rendered — an
unknown value must not mint a third state, and `?view=` on a non-markdown path
is inert, because that body is verbatim in either mode.

**The switch is two ordinary internal links**, which buys three things at once
and re-implements none of them: the mode is deep-linkable because it lives in
the `href`; it is keyboard- and middle-click-operable because it is a link
(Tab reaches `source` in five stops, Enter activates it); and the swap rides
the router's existing dissolve because `isInternal` already claims `/file`. A
pair of buttons would have needed a handler, a history push and a transition of
its own. The active label carries `aria-current="page"` rather than a radio's
checked state — these *are* pages.

It is the standing **sliding selection group** (`.sgroup`/`.sgind`/`.sgbtn`,
#121), so the travelling outline, its easing and its reduced-motion landing
come for free. What is its own:

- it sits in a line of text, so `display:inline-flex` on the row's baseline at
  the crumb row's own size (`.7rem`), not a control panel bolted to it;
- **both labels stay in one row at every width** (his rule). `.sgroup` wraps by
  default and a wrapped two-position switch is a stack with the indicator
  sliding vertically through it, so the switch sets `flex-wrap:nowrap`. Two
  words cost under 16ch — there is no viewport where hiding or stacking half of
  a binary choice is the better trade;
- **the selector is `#meta .fmodes`, and that is a contract rather than a
  habit.** `.sgroup` re-declares `display:flex; flex-wrap:wrap` at plain class
  specificity and *later* in the sheet, so a bare `.fmodes` lost both: the
  switch became a **block-level** flex container, which forces a line break
  before and after itself — inside its own crumb — and orphaned the separator
  above it. The id keeps the invariant true wherever this block sits in the
  file, which is the same reasoning `.dreamin`'s `!important` states in its own
  comment. Its guard asserts the *computed* `display` and `flex-wrap`, not only
  that two labels happened to fit: two words fit in 390px whatever the wrap
  rule says, so the observable check alone could not fail on this;
- the active label takes `--accent`, i.e. `.sgbtn.on` unmodified. That is the
  accent's rule rather than an exception to it: the mode is the live state of
  the surface he is reading, not a settled preference like the project tint
  (whose selected label deliberately wears its own hue instead).

**`.on` is deliberately absent from the crumb's html**, and the crumb is
declared `stable` so `renderChrome` never rewrites it while it survives. A
rewritten `.sgroup` is fresh nodes with a 0-width indicator, so the outline
would grow out of the row's left edge instead of sliding to the other label;
`paintFileMode` paints the state after the row is assembled and slides the
indicator only when the group actually survived. The crumb's key carries the
**path** (`fview:<p>`), so switching *files* departs one switch and arrives
another — a different file's control — while switching *mode* on one file keeps
the same element. Nothing stale can survive a change of file.

**Motion** is the route dissolve, unchanged (`transitions.md`, *The dream
dissolve*): the heading and the switch are chrome, so they are the same
elements before and after and are **held fixed** while the body dissolves under
them. Reduced motion swaps instantly, with the same mode, the same bytes and
the same restored reading position.

**The reading position survives, as a ratio.** The two panes are different
heights — a rendered document is shorter than the source it came from, by
roughly its own markup — so the same pixel offset is a different place in the
text. Two measurement traps are live on this path and both are
`transitions.md` rules:

- `documentElement.scrollHeight` counts the outgoing **ghost**, which is an
  absolutely positioned clone inside `.wrap` and, going source → rendered, the
  taller of the two. The restore would land low and then be clamped when the
  corpse is removed a second later.
- `getBoundingClientRect` answers in **visual** space, and on the frame this
  runs `#view` is mid-`enter`: pushed back in Z and scaled down.

So `contentBottom()` walks `offsetTop` up the `offsetParent` chain and adds
`offsetHeight` — layout values, immune to both. A pointer user has to scroll
back to the top to reach the switch, so the restore earns its keep on
**popstate** (back/forward between the modes) and on a keyboard activation.

**Source is never syntax-rewritten**, and that is the whole point of the mode
rather than a detail to optimise away (his words). It is the same
`` `<pre>${esc(text)}</pre>` `` every non-markdown file at `/file` has always
rendered — reached by a second route, never by a second renderer — so there is
nothing between the server's string and one escaped text node: no transform to
audit, no tokeniser to drift out of step with the file. **#351 asks for syntax
highlighting on `/file`; a markdown file's Source pane is the one place it must
not reach.** `review_artifact.py`'s build-time highlighter (#339/#348) stays in
review artifacts, and the page carries no `tok-` output at all.

**Two limits on "exact", stated rather than implied**, because a guarantee with
an unstated edge is worse than a narrower one:

- `read_text` opens in **text mode**, so Python's universal-newline
  translation turns `\r\n` into `\n` before the page ever sees it. A CRLF file
  renders as LF in both modes. Nothing the loop writes is CRLF, and the raw
  bytes remain reachable at `/filebytes`.
- `read_text` caps at **200,000 characters**. Both modes are equally truncated;
  neither claims otherwise, and again `/filebytes` is the uncapped path.

`dev/capture/fileview.mjs` guards it. Four of its checks are worth copying:

- **the deep link is LOADED, not clicked.** A switch that works only on click
  is precisely the bug a click test cannot see, and the pasted link is the
  point of the parameter;
- **the pane is asserted to hold NO element children**, not "no `tok-` span":
  the narrower form passes over every other rewrite;
- **inertness AND visibility.** A page that *deleted* the `<script>` is also
  inert and has silently lost the file's content, so the literal characters are
  asserted present;
- **the two modes' scroll ranges are asserted to DIFFER** before the ratio is
  checked. With equal ranges, restoring a ratio is indistinguishable from
  keeping a pixel offset — and from doing nothing.

Three findings from red-proving it, all recorded because each cost a run:
`page.click()` **scrolls its target into view**, and the switch is at the top of
the document — so driving the scrolled phase through Playwright's mouse
destroyed the ratio it was about to assert and read as a broken feature.
`waitUntil:'networkidle'` plus a sleep is **not** enough before measuring
height: `/filedata` is fetched after load, so under concurrent browsers the
guard measured a `loading…` placeholder as the whole document and the range
read 0. And the reduced-motion landing has **two independent implementations**
— the `@media` block's `transition:none` and `slideIndicator`'s `rmr` branch —
so removing either alone left the check green; it goes red only when both go,
which is redundancy rather than a hollow check, and worth knowing before
someone deletes "the duplicate".

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

**Review-artifact references — one shape (#472).** The corpus writes a
backticked path `` `.dreamwork/review/<name>.html` ``; `linkifyReview` turns
that into a dock link to `/review?p=<name>&q=<title>` so the originating
question travels with the artifact. Prefer that shape in every new ask —
it is what `#294`, `#445` and most of the open set already use. A markdown
inline link whose target is a review artifact
(`[label](../review/name.html)` or `[label](.dreamwork/review/name.html)`)
is also recognised and rewritten to the same dock URL: `mdSpans` has no
general `[text](url)` pass, and a relative `../review/` path is wrong for
the `/questions` route, so the outlier form used by `#417` was raw text
and unreachable. Bare relative paths are never left as navigable hrefs.
(`file-formats.md` is where the writing rule belongs; this paragraph is
the page-side contract.)

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

### The file view's image and binary surfaces (#336)

His report, typed from the page it happened on: *"viewing images should work.
this renderes as binary ascii like:"* and a paste of U+FFFD soup. `/filedata`
read every file as UTF-8 (`errors=replace`), so a 150KB evidence PNG became a
`<pre>` of replacement characters — plausible-looking garbage instead of a
state, which is the quiet-wrong DREAMWORK.md forbids in as many words. The
fix splits the file-content path by **what the file is**, decided once on the
server by **extension AND magic bytes** (an extension alone is a guess, and a
guess is what produced the bug):

- **Text** stays on `/filedata` and renders exactly as before — `<pre>` or
  reflowed `.md` per #158. The branch the bug was in is unchanged for the
  case it was right about.
- **Image** (a raster whose extension is in `INLINE_IMAGE_EXTS` AND whose
  magic bytes confirm it) is described by `/filedata` as
  `{binary, kind:'image', mime, size}` and served as raw bytes by a new
  `/filebytes` endpoint behind the **same `resolve_confined` gate**. The
  view renders an `<img>` for it.
- **Binary, non-image** is described the same way (`kind:'binary'`) and the
  view shows a labelled panel — type, size — with a download link, never a
  `<pre>` of bytes. The bytes are reachable via `/filebytes`, but only as
  `application/octet-stream` with `Content-Disposition: attachment`.

**The allowlist is raster-only, and that is the load-bearing security
decision.** A raw-bytes endpoint that echoed a client-asserted
Content-Type would turn any `.svg` or `.html` in the tree into stored XSS
against the dashboard's own origin — and #275/#276 are actively
considering LAN and public exposure, so this is not theoretical. So:

- Inline Content-Types come from a server-side table
  (`INLINE_IMAGE_EXTS` / `_INLINE_IMAGE_MIME`), never from the request.
- **SVG is explicitly OUT of the inline allowlist**, and the entry says so
  because the next reader will want to add it. Do not add it: the moment
  SVG is inline it is XSS. (The magic-byte gate would also stop a naive
  add — see below — but the allowlist is the contract and the magic gate
  is defence in depth.)
- Every non-inline response is `application/octet-stream` with
  `Content-Disposition: attachment` and `X-Content-Type-Options: nosniff`.

**Detection is extension AND magic bytes**, because either alone re-opens
the bug a different way. `_magic_matches(ext, head)` requires the file's
first bytes to begin with the signature `ext` claims — a `.png` containing
an SVG body does not get served as `image/png`; an `.html` containing PNG
bytes does not get served as an image either, because `.html` is not in
the allowlist. AVIF, which has no fixed prefix, is gated on its ISO BMFF
`ftyp` box brand (`avif`/`avis`/`mif1`).

**Motion.** However the image arrives in the view, it obeys
`transitions.md`. The route change is the reference implementation and the
image is inside `#view`, so it rides the dream dissolve like every other
element of the view — the guard traces `#view`'s opacity through the
dissolve and requires intermediate frames (a snap visits none). The
`<img>` also carries its own smaller arrival for the late-load case its
bytes land after the view settled: a `.pose` start state at `opacity:0`,
removed by `imgArrived()` on `load`, eased on `.fileimg`'s own `.55s`
opacity transition. **The pose is opt-in by JS and suppressed by CSS under
reduced motion**, so a JS error or a removed handler fails *visible*
rather than invisible, and reduced motion keeps the same information with
the movement removed — never a feature that silently degrades.

**The binary-file panel is information, not an error.** The copy is read by
a person who expected to see something:

> **binary file**
> type   application/octet-stream
> size   149.5 KB
> *[download the bytes](/filebytes?p=object.bin)*

The file IS here, it is named, and its bytes are one click away — what it
is not is text the page can show, so the page says that plainly. Same
hairline rail, same dim labels, same `label` idiom as every fact list on
this page, so it reads as a quiet part of the dashboard rather than as a
fault. A load failure on an image (truncated upload, exotic codec) falls
back to the same panel rather than leaving a broken-image icon — the
bytes stay reachable. The download link's `filename=` is sanitised to
ASCII alphanumerics + `.-_`, because a malformed `Content-Disposition`
header is worse than a drab name.

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

**That was true on `## Open` and false on `## Answered` for as long as both
existed (#340).** The Answered path parses with `lift_answer=False`, and an
answer bullet matches `ANSWER_TAGS` but not `NOTE_TAGS` — so it was neither
lifted nor recognised as a contribution, fell into the entry body, and rendered
as a `·` item with its raw tag visible and no label at all. On **22 of 36**
answered entries. The paragraph above was already the contract; only one of the
two paths obeyed it, and the more-travelled one did not. Worth stating here
rather than only in the ledger, because a styleguide claim that describes half
the surfaces is the kind of thing a reader trusts and should be able to.

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

- **It is a property of the parse, not of a renderer.** Four surfaces show
  these entries — the dashboard's questions section, `/questions`, the
  review dock, and the `/question` focus page (#452) — and all four go
  through `qaCard`. A sort in each is four
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

A question is the page's one interactive object, and it appears on five
surfaces — the dashboard, `/questions`, the review dock, the `/question`
focus page, and the card the submit morph restates in place. All five go
through **one** component, so a
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

**An open card rolls up to the top of its scroll** (#454). His words:
*"questions on the questions page should be collapsible. However, the size of
each collapsed question should be at least like 5-6 lines. So it's more like
a card or the top of a rolled up scroll. This should be persisted to
IndexedDB and kept in sync like other ui state."* Rolling is not a fourth
state on the waiting-on axis — a rolled question is still **open**, still
waiting on him; it is a reading posture he takes toward the card, which is
why it is a class on the card (`rolled`) rather than a `qaState`, and why
only `open` cards offer it (awaiting still needs the loop; folded already IS
the collapse).

- **The 5-6 line floor is the design, not a detail.** A one-line collapse
  is a title list, and a title alone does not say whether an entry still
  needs him. So the clamp is a line COUNT (`ROLL_LINES`) times the RENDERED
  line height, measured at runtime through `lineHeightOf`'s probe and handed
  to CSS as `--rollh` — never a pinned pixel constant (#441's split-literal
  lesson). The bottom edge softens with a CSS mask, the rolled scroll's
  cut; never a per-card SVG filter (#449's measured jank — this feature is
  precisely the many-filtered-elements shape).
- **The clamp is the one place `.qbody` has a box off the dock.** #326's
  `display:contents` stands everywhere else; a clamp needs an overflow edge
  and an edge needs a box, so `.qa.rolled .qbody` is `display:block` for
  exactly as long as the roll lasts. The compose box leaves with the body:
  answering a question means reading it, and reading it means unrolling.
- **The gesture is the card fold's own** (#111/#169): `toggleRoll` runs the
  same snapshot → toggle → `regroupCards` with `toggled = null`, so the
  height travels, the departing slice ghosts from the card-level clone
  clipped below the new edge, and the arriving body eases in on `revealBody`.
  Reduced motion snaps to the same end state.
- **Persistence is per-question UI state**, keyed by the title identity
  (`data-qid`), in the `dw-ui:<target>` IndexedDB store — through the ONE
  helper the submissions log already races against a wedged store, never a
  second path — and kept in sync across tabs through the standing
  `storage`-event ping idiom (#290). `rolledQids` is the page's truth
  between the two; `restoreRolls` re-applies it inside `setContent`, the one
  seam every render commits through, so a tick, a route swap, or an
  autoreload cannot lose it (his standing rule), and the tick's regroups
  measure after it so a kept roll invents no travel. The boot read is async
  after `ensureData`: first paint never waits on IndexedDB.
- **The dock is exempt**: it is the reading surface, its card is never
  rolled, and the affordance the shared markup emits declines there by CSS
  (and is stripped in `dockHeadline` per the #474 chrome rule). The focus
  page suppresses the button, as it suppresses the focus link — the page IS
  the focus. Rolling composes with #452 rather than competing with it:
  rolling is how the LIST stays scannable, focusing is how ONE question
  holds still; the rolled card keeps its focus link visible inside the
  clamp, so the way in is never rolled away.

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
  — the typed text, the submit morph, Ctrl/Cmd+Enter and the
  `MORPH_HOLD_MS` (1250ms, #234) `holdRerenderUntil` guard are identical
  either way. The mode group is the
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
card's default would redirect his words. **A non-default mode IS his state
even with no text typed** (#479): `snapshotCardState`'s inclusion test counts
`modeHis` on its own — otherwise any tick re-render reverts the destination
mode to the card's default and re-aims words he has not typed yet. And
`restoreCardState` restores the mode **before** the no-text early return, so
an empty box keeps its mode too. `setCardMode` is the single
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

### The focused question

*#452, human via watch 2026-07-29: "should be able to focus on a question,
like open up to a page showing only that question. useful if other qs are
being updated etc."* The reason given IS the requirement: the loop rewrites
`questions.md` while he is reading it, so a list view re-sorts and re-bodies
entries under him mid-answer. `/question?qid=<title>` is the surface that
churn cannot move — exactly one card, the full `qaCard`, answered from the
same compose path as everywhere else.

- **The key is the question's title identity — the same string `data-qid`
  already carries.** It was chosen for what SURVIVES it: body rewrites,
  priority re-sorts and the open→answered fold all keep the title, and
  those three are the churn the page exists for. The alternatives were
  rejected on the same evidence: a content hash breaks on the body rewrites
  that are the common case, and a positional key breaks on every re-sort.
  `#294`'s planned `question_id` can later be accepted *beside* the title
  without invalidating a single link.
- **The fold is followed, not reported.** Resolution searches
  `questions_open` AND `answered_entries`, because answering re-indexes the
  entry while he watches — a live question reported as gone is the failure
  the route exists to prevent. Same title, same card, new `a<n>` address.
- **An unresolvable key fails LOUD.** A retitle breaks the key, and
  `.qmissing` says what happened (most likely re-titled or removed), guesses
  at nothing (a near title is a different question), and links back to the
  list — "I could not tell" and "nothing" must never render the same. It
  wears the rail at DIM level, deliberately not `--warn`: the channel is
  healthy and the question is simply gone; a fault colour would cry broken
  over an edit.
- **The way in is a real link on every card, in every state.** `.qfocus`
  sits in the headline beside the age chrome: the href makes it
  deep-linkable and copyable, keyboard operation is native, and the click
  rides the router's existing dissolve (the #252 argument — a button would
  re-implement all three). It is headline CHROME under the #474 rule: a
  node with a class, and that class is listed in `dockHeadline`. It is
  quiet at rest (dimmer than the age it sits beside), accent on
  hover/focus, and has no motion of its own — it is part of the card's
  HTML and rides the card's own arrival. On the focus page itself it is
  suppressed: the page IS the focus.
- **A link inside the folded card's `<summary>` is navigation, never a
  fold.** The `EXPAND_SURFACES` handler declines clicks on `a` descendants
  — it is registered before the router's handler, so its `preventDefault`
  would otherwise swallow the navigation and the affordance would read as
  present while only ever toggling the fold.
- **The route change is the existing dissolve and nothing else.** Entering
  and leaving is the crossfade every route uses, with the route's own
  `TINT`/`SEED`/`TITLE_ROUTE` entries; reduced motion swaps instantly.

`dev/capture/qfocus.mjs` guards all of it: the affordance on every card and
its key identity, the folded-summary navigation, the arrival dissolve
(`transitionstart` on `#view`, the load-independent detector), an answer
sent from the focused surface landing on the same question, the tick
following a real fixture fold, the said-missing state, and reduced-motion
parity.

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

**A rejected body is the same failure on a receipt that says otherwise**
(#263 E5b). E5 turned a body-validation failure from a synchronous `400`
into a `202` carrying `{ok:false, rejected:true, reason}` — a durable
`rejected` transition with a bounded reason, not a transport refusal. But
`202` makes `res.ok` **true**, and every write surface gated on `res.ok`,
so the box cleared, the page said *asked*, and on `/answer` and `/comment`
the draft store cleared too — the only copy of what he typed, gone. A
rejected receipt is a write the server refused from the other end, so a
write surface treats it as exactly that. **One verdict decides it**:
`writeVerdict(res)` reads the body once (a `Response` body is read once, so
it is the single reader) and returns `{landed, rejected, reason, detail, status}`,
where `landed` is `res.ok && !rejected` — the one thing `/ask`, `/answer`,
`/comment`, `/command`, `/tint` and `/run-mode` gate on, never `res.ok`
alone. The reason is named in his voice through a closed map (`REJECT_WHY`)
paired with the server's `REJECTION_REASONS` (`malformed_json`,
`schema_invalid`, `domain_invalid`); a code outside the set falls through to
the status line, never an unrecognised string. The consequence is the same
idiom as a transport refusal — the box does not clear, the morph does not
run, the confirmation does not land — and the line says so in the same
breath: `not written — <reason>. your words are kept` (ask, composer,
command) and `not written (rejected) — <reason>. what you typed is still
here.` (answer/comment cards). `dev/capture/rejectwrite.mjs` guards the four
write surfaces against a `route.fulfill`-injected rejected `202`.

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

**One shared description surface (#300).** Hovering or focusing any chip
explains that mode in a single `#rundesc` below the group and **above** the
arm/countdown — never a per-button tooltip, never over the countdown.
`RUN_MODE_DESC` holds one sentence per mode, traced to the behavioural
contract in `file-formats.md` / `SKILL.md` (what continues, stops, commits),
not marketing. Button→button keeps the shell fixed (`min-height:2.6em`) while
the words dissolve and resolve; first arrival and final departure reuse the
atmospheric blur/drift idiom (`transitions.md`). Keyboard focus shows the
same text; every chip's `aria-describedby="rundesc-text"` resolves to that
live node. Escape / pointer-leave / blur dismiss with **no mode side effect**
— hover must never call `pickRunMode`, write pending, or POST. Reduced motion
swaps text instantly with identical meaning and the same wiring.

**Consumption honesty.** The file + the events line are how an agent learns
the mode. This dashboard does not, by itself, change a running session's
scheduler; the loop that tails the events log (or re-reads the file on tick)
must apply policy per its own skill protocol.

`dev/capture/runmode.mjs` is the browser guard for the arm/commit path: real
10s arm intermediate progress, reset, commit, event exactly-once,
hierarchical disabled, reduced-motion text path, and cross-tab pending via
storage. `dev/capture/rundesc.mjs` guards the description surface: one
stable box across every chip, zero arm/file/event side effects on
hover/focus/Escape (including pending localStorage and the countdown text,
because a 10s arm is silent to POST for ten seconds), per-frame morph
`between()` intermediates, reduced-motion parity, and hover≡focus text.

### The three-axis posture (#445)

The fine-grained override of run-mode's bundled decisions. His words: *"we
should add controls for the new values and their dimensions. We can have like
3 stops on each axis maybe? IDK that i will leave up to you, but we get 3
dimensions of input is the point."* Increment 1 landed the vocabulary
(`.dreamwork/posture`, sibling of run-mode); this surface is the control.

**Three orthogonal axes, one file.** `pace` × `asking` × `delegation`,
written as three `axis: value` lines in `.dreamwork/posture` (gitignored,
machine-local). An **absent** file is derived from run-mode via
`lint.derive_posture` (single source — the dashboard imports, never restates,
the closed sets and the conversion). A **present** file is an explicit
override. `collect()` exposes `posture` so every open window converges on the
existing `/mtime` poll.

**Asymmetry is honest, not tidied.** Pace has three stops (`idle` / `steady`
/ `hot`). Asking keeps **all four** of the levels he dictated (`ask` /
`inform` / `near-auto` / `auto`) — near-auto still journals an ADR-shaped
record per material choice, auto does not, so merging them would delete a
behaviour he specified. His "3 stops maybe" was about the control, not a
licence to drop a level. Delegation is an **integer average-concurrency
target**, not a chip and not a cap (his Q3): `0` means *occasional* (avg
below 0.5 — not forbidden), `1` means avg between 0.5 and 1.5, `2+`
delegates. The derived label (`own` / `assist` / `delegate`) is display only.
Two agents may pair on one worktree. The stepper's UI max is a control
affordance, not a fleet limit.

**One shared 10s arm over the whole triple.** Three independent arms would be
three ceremonies for one file and one events line. Any axis change resets
`RUN_ARM_MS` (the #290 arm, reused); only the final triple POSTs `/posture`.
Identical final is silent. Re-selecting the fully committed triple cancels.
Cross-tab pending rides `localStorage` keyed by `data.target`
(`dw:posture-pending:`), same owner/orphan-reclaim shape as run-mode. The
control is the standing sliding group for pace and asking; the stepper is a
quiet − / value / + with the derived label beside it. Active stop takes
`--accent` (live loop control). Reduced motion hides the bar and keeps the
second-by-second text and the same application time.

**Source note (#488).** A dim chip sits **beside the Posture heading**
(`.posture-head`: label + `#posture-src`), not under the axes — so a glance
never confuses derived values with an `override · .dreamwork/posture`. The
copy still reads `derived from run mode · pick a stop to override` when the
file is absent, and `arming override…` while the shared arm is live.

**Hover description reserves layout (#488).** `#pdesc` is always in flow
with a permanent `min-height` (empty space is intentional). Show/hide is
opacity + the rundesc blur/drift idiom only — never `display:none`, never
the HTML `hidden` attribute, never insert/remove — so the card and
everything below it do not reflow when the text arrives or departs.
Hover/focus never arms, POSTs, or touches localStorage.

**Consumption honesty.** The file + the events line
(`posture via watch[ /path]: pace=… asking=… delegation=…`) are how an agent
learns the override. The loop re-reads on tick (#426); this dashboard does
not, by itself, change a running session's scheduler.

`dev/capture/posture.mjs` is the browser guard: stop counts (including the
four-stop asking axis), arm drain sampled mid-bar via `between()`, one POST
+ one events line on change, cancel on re-select, reduced-motion text path,
hover side-effect free, hard-refresh follows the file, source chip geometry
beside the heading, and desc open/closed bounding-box parity so a reflow
cannot hide behind an end-state text assertion.

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

**The push channel, down — the master fault, rendered first (#190).** `attn`
died with a 403 ("out of credits or need a Grok subscription") for an
afternoon and nothing made the loop notice: it reported progress into a
transcript he was not reading while the channel it believed had escalated sat
refused. The channel for reporting a broken channel WAS the broken channel, so
the dashboard is the only surface left that can say so. `status.json` gains a
`push` object (`{at, channel, ok, detail}`), and the status panel renders its
failure at the top — before `awaiting_human`, because a loop that cannot push
cannot deliver that list either, which is what makes the push fault the
context for everything under it.

**THREE STATES, distinguishable from the data, and only one earns pixels.**
No `push` key means the loop has never tried (a fresh target); `ok:true` means
the last push landed; `ok:false` means the last one failed. The first two are
QUIET — a channel that is fine deserves no pixels, and a page that greeted
every healthy target with a push-fault rail would train him to ignore the one
that matters (the same credibility argument as `questions_health`'s calm
states). Only `ok:false` renders, and the branch is **strict** (`p.ok ===
false`): a missing or malformed `ok` — which `lint.py` catches at the writer —
must never read as a fault, and "absent key means fine" is the trap the task
named, because then a loop that never even tried looks identical to one whose
pushes all land. The renderer is quiet for both non-fault states *because the
data lets it tell them apart*, not because it cannot.

**The copy names the channel and the reason, because the remedy is his.**
"push channel down" alone sends him hunting; the 403 and the credit message
are the actionable part, since the fix is billing rather than re-auth (a loop
that had acted on the first 403 diagnosis — "re-auth" — would have burned his
time on the wrong thing). So the fault line carries `push channel down ·
failed <age> ago` (the age rides the standing `.age[data-at]` idiom — a thing
that *happened* renders "Xm ago", clock-derived like `last_tick`), and the
body states plainly: *the loop cannot reach you — its last push (`attn`) came
back: <detail>. pushes land nowhere until this clears; the remedy is likely
yours (billing or re-auth), not the loop's. this dashboard keeps working
either way.* It wears `--warn` on a rail, the idiom `.qhealth.unreadable`
already owns — a member of that class, not a new one.

**It does not move.** The status panel is re-rendered through `innerHTML` on
every tick, so nothing inside it is a "survivor that travelled" or a
disclosure that changed layout — the two things `transitions.md` licenses to
animate. The push fault appears when the data says so and disappears when it
clears, exactly as `.stneed` and `.qhealth` do: a data-driven fact the loop
reports, not a gesture the page initiates. The motion rule's "nothing else
animates" is what makes that consistent rather than a gap.

`dev/capture/pushhealth.mjs` holds all three states at once — each easy to get
right alone and the failure always that one swallowed another — and its
load-bearing half is the anti-vacuity precondition: it asserts the three DATA
shapes genuinely differ (absent lacks the key, `ok` holds `true`, `ok` holds
`false`) *before* it asserts any render, so a check that read "nothing
rendered" in all three cases would fail at the data line rather than pass over
the feature. The same idiom as `health.mjs`'s exemption check, one surface up.

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
of the tallest. A cap on a transparent box of the same height is the same
number and reads as the staircase it is.

**#417 — commits-per-period, without trading the chart away.** He asked for
how many commits were made each period, and then ruled **`c3` + `c4` + a
per-column hover** (2026-07-29): the level line's cap weight carries the
count, a figure line names the summary, and hovering a column shows the
exact numbers so the weight mapping is learnable rather than argued about.

- **`c3` — weight is commits, height is still open.** Cap `border-top-width`
  maps ledger-touching commits (the same `revs` walk, no second source) onto
  **2–6px**, linear over the real range. **Zero is 1px**, below the 2px floor,
  so a quiet period is distinguishable from a single-commit one; the peak is
  always 6px. Height still means open count — the line now carries two facts,
  which is why the hover exists. Weight travels with height on the bar's
  `.85s` curve (`regroupBars`), not a snap. Accent is not spent.
- **`c4` — one shortened figure line.** `N median commits/period · peak P ·
  Q empty`, in the panel's `#218` voice (`.bdcommit-copy`). **No ellipsis**:
  the long form clipped at mobile and read as broken; the short form is the
  condition of shipping it. The +19px is a **one-time allowance** baked into
  the panel's constant height, not a growth on data change. No motion.
- **Per-column hover — all the facts, not only commits.** Height = open,
  weight = commits, flow = arrived↑/landed↓; the tip names all of them so the
  line is never left implying only one meaning. Floats over the chart
  (`.bdtip`, position absolute inside `.bd`) so it **never changes panel
  height**. Arrival reuses the rundesc atmospheric blur+drift (`pose` → ease
  in, `depart` → ease out); reduced motion snaps. Keyboard focus reaches the
  same readout (`tabindex` on level-track columns). Accent is not spent.

**#298 — the column inspector, a richer reading on the same seam.** The
glance tip answers a passing hover; the inspector (`.bdinsp`) answers a
*deliberate* look — a hover that **dwells 700ms**, a keyboard focus
(immediate: focus is already deliberate), or a **tap** (pinned until
dismissed). It is not a second hover: same data attributes, same
pose→ease-in / depart idiom, same floats-over-the-chart premise.

- **What it adds** is what the geometry cannot say: the **exact interval**
  (`Wed 29 Jul, 14:00 – 18:00`, `– now` for the open period) and the
  **coverage state** — a period with no ledger commit *carries* the
  previous level rather than measuring it (the chart's own rule), so the
  inspector says `level carried — no ledger commits`; the current period
  adds `period in progress`. Values are the column's own served numbers —
  detail *about values already summarised*, never a hidden dataset.
- **It follows the column**: horizontally centred on the active column,
  **clamped to the panel's edges** so an edge column never sends it
  off-chart, anchored above the level track so it never sits on a
  neighbour. Laid out in JS (`bdinspLay`) because centring-plus-clamping
  is not expressible in CSS.
- **Dismissal**: pointer-leave (unless pinned), focus-leave, tap the same
  column again, tap outside the chart, **Escape**, or scroll — a scrolled
  page moves the column out from under the reading, so it departs rather
  than drifting on stale coordinates. Tap never calls `preventDefault`,
  so chart scroll is never the inspector's to break. Reduced motion snaps.
- **Restraint**: a pinned reading is not hover's to move — dwelling on
  another column does not displace a tap-pinned inspector.

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

**Who filed each task, by first sight (#217).** The panel used to report
its own provenance COVERAGE (`sourced 0/4`) instead of drawing the split,
because the only marker it could read — the `**human` stamp on the current
file — sat on a minority of entries, and a chart drawn from it would have
been mostly one bar wide and read as fact. #216 made the real answer
readable: a task's origin is a fact about its ARRIVAL, classified from the
first committed snapshot where its id appears and never revisited. So the
split is drawn now — as three counts, `human · loop · historical unknown`,
under the axis — and the shape of the drawing is the honesty:

- **The unknown remainder is drawn as itself, never folded into loop.** It
  is the third segment and the third legend key, labelled `historical
  unknown`, because that is what it is: entries filed before the marker
  existed, whose arrival says nothing about who filed them. Adding them to
  the loop's count is the exact lie the task was filed against, and the
  guard (`dev/capture/provenance.mjs`) was shown red against precisely that
  sabotage before it was trusted.
- **Colour never carries the split alone.** Human and loop are solid at two
  text-ramp steps; unknown is a HATCH — a pattern, not a shade — so the
  distinction survives every project tint and every colour-vision. The
  legend states the same three counts in words (each key wearing its
  segment's ramp step), every segment states its count on hover, and the
  bar's `role="img"` aria-label is the whole datum in one sentence. The
  accent is not spent: the panel's rule (#142) is that nothing in it waits
  on him.
- **The copy names the denominator and the scope**: `N first sightings in
  recorded git history`. Committed sightings — an entry sitting uncommitted
  in the working tree is not a historical arrival and appears nowhere in
  the datum. A shallow clone cannot see first sightings before its
  boundary, and says so (`coverage is incomplete`, on its own line and in
  the aria-label) rather than claiming full coverage.

**The count-carrying lines may never wrap**, which is the ellipsised-head
rule (#151) one element down: the note that used to carry counts grew the
panel by 14px when `0 of 4` became `0 of 14`, so a bar easing over 850ms
sat above four panels that had already jumped. The legend and the
denominator line are one line each, `nowrap` + ellipsis, short enough to
never clip at 390px at any realistic count; the full text rides the
aria-label either way. The incomplete-coverage line is constant prose.

**How long finished work took, from the pairs the walk already holds
(#218).** `ledger_series` builds an id's first-sighting time and its first
appearance under `## Recently landed` on its way to the burndown, and used
to return only their counts — so every filed-to-landed duration in the
project's history was computed and dropped on the floor. The median is now
rendered, as ONE honest duration in the panel's surrounding copy and the
population it was computed over. It is not a velocity score, a rate, a
burn-rate, or anything that blends two quantities into an index: the entry
said "without a velocity score", and that is taken literally. (The
burndown's standing "no velocity score, deliberately" rule is unchanged —
this is a single honest measurement, not the composite that rule refuses.)

  - **Copy, not a chart mark.** #417's caution is that the burndown's
    quality is not to be traded for an extra series, and the chart already
    states honest denominators and hatches unknowns (#217); a median belongs
    in that same voice rather than as a new visual element competing with
    the chart. So it is one line of `.bd` copy — the head's `bdnum`/`bdhead`
    treatment one element down — placed after the provenance block. The
    number rides the SAME age ladder as the commits (`ageParts`), one figure
    at its dominant unit (`1h`, `2d`) rather than a second humanizer; the
    count beside it is the population the median was computed over, because
    a median over 4 pairs and one over 200 are different kinds of claim.
  - **The population is the INTERSECTION, and the label says so.** An id in
    `arrived` but not `landed` is still open and has no duration, so the
    median is over the ids that have both — the work that FINISHED. That
    silently answers a different question than a reader assumes: it is "of
    the work that finished, how long did it take", NOT "how long does work
    take", and the still-open long tail is excluded (an optimistic bias that
    grows the longer something sits). The copy says `median time finished
    work took to land · over N pairs`, so it cannot be read as the second;
    the aria-label adds that still-open work is not in the median.
  - **A combined head is two pairs, not one.** `- **#A/#B**` names two ids
    and `ledger_series` already counts each as a landing; the median follows
    the function, and a test asserts the head contributes TWO durations.
    (#392's audit lane got this wrong and was refuted.)
  - **An even-sized population takes the MEAN of its two middle values**
    (the standard median), stated here so the choice is known. A test pins
    it against a four-pair fixture with distinct durations.
  - **The no-data case says which kind of nothing**, following the panel's
    existing idiom (`test_ledger_series_says_which_kind_of_nothing`): a bare
    `0` or a dash reads as "work takes no time", which is a lie, so when
    nothing has landed the line says so (`nothing landed yet — no
    filed-to-landed duration to take the median of`). `median` is `None` and
    `median_n` is `0`, and the renderer keys its no-data branch on
    `median_n` — `None` rather than `0` is the absence the branch names, and
    a genuine single-pair median of 0s is not collapsed into it.
  - **No second walk.** The pairs already exist inside `ledger_series`, and
    a second git walk is a second truth; the median rides the same walk the
    provenance counts do (#217), so it costs no second pass over history.
  - **No motion, like the rest of this panel.** A live tick commits its DOM
    instantly (transitions.md) and nothing about a median is a gesture the
    page initiates, so `.bdmed` declares no transition and reduced-motion
    parity is the identical settled visual. The accent is not spent — the
    panel's rule (#142) is that nothing in it waits on him, and a median does
    not.

`dev/capture/burndown.mjs` measures the panel's constant height premise
(derived at runtime across a real data change — never a literal pixel
floor), the c3 weight mapping (zero vs one vs peak, against served data),
the c4 copy (no ellipsis at both widths, figures derived from `/data.json`),
and the per-column hover (readout numbers match the hovered column's served
bucket, transition mid-frames, reduced-motion parity). The median and commit
figure lines are re-rendered copy in that same panel.

**No motion, on purpose.** A live tick commits its DOM instantly
(transitions.md), and nothing about this datum is a layout change anyone
initiated — so no part of it declares a transition, and reduced-motion
parity is the identical settled visual rather than a second path.

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
0.0014s warm). The provenance counts ride the SAME walk — each memoised
revision also carries its entries' first-sight classifications, so the
datum costs no second pass over history (#217). Every git call carries
`--no-optional-locks`, asserted by a test rather than remembered. One
consequence of caching on HEAD alone: the chart's right-hand edge is the
moment the answer was computed, so it goes stale until HEAD moves — which
is right for a chart about ledger history.

**The ledger's pathspec is resolved against the repository's TOP LEVEL**
(#217), and the walk runs from there: a target nested inside a larger repo
must read its own `.dreamwork/tasks.md` history, and `git -C sub log --
.dreamwork/tasks.md` would otherwise walk the parent repo and read the repo
ROOT's ledger — silently. The first-sight grammar (`ENTRY_HEAD`, `ENTRY_ID`,
`ORIGIN_MARK`, the entry walker) is lint.py's #213 grammar held VERBATIM —
watch.py is one file by design and cannot import it — and a test pins the
two identical, the one-copy rule `LEDGER_ENTRY` already states.

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

**A TIMED age is two units, two digits each** — `05m 23s ago`, `02h 14m ago`,
`03d 07h ago`, `02w 03d ago`, `01y 14w ago` (#385). A DATE-ONLY age is ONE
figure (#392a, below — the number of figures is the precision). Two edges are decided
rather than fallen into: under a minute it still reads as two units
(`00m 12s ago`), so the column never changes width and a seconds-old commit
is exactly the case he is watching; and the ladder runs seconds → minutes →
hours → days → weeks → years so neither field reaches 100 for ~100 years —
his own invariant. Without the year and week rungs the day count alone
passed 99 at 100 days, which broke the format he designed. Year length is
365 days (not 52 weeks = 364); weeks are 7 days. The remainder after a year
can show 52 weeks, which is still two figures.

**A single-digit unit is prefixed with a gray 0** (#385) — `05h 09m` greys
both leading zeros; `15h 42m` greys none. The pad is a `.agepad` span at
**opacity 50%** (#456) inside the already-dim `.age`, built by the shared
`pushFig` (one grey-rule path used by `paintAgePair` and `paintDayAge`, so
the two-figure and one-figure painters cannot drift apart). Opacity rather
than a dimmer colour token: it composites against the animated shader and
reads close to invisible, which a solid token cannot. The discriminating
half is the second case: a rule that greys unconditionally passes any check
that only looks at `05`. The text still updates once a second through
`ages()` with no transition — the live ages sweep is opt-in-off by design
(`transitions.md`).
**Question headlines reuse the same age, next to the date already in the
title** (#385 / #456). `qtHtml` splits an optional `P1 · ` priority, the
`YYYY-MM-DD` date, and the rest; the chrome's ` · ` sits between the date
and an empty `.age.qage[data-ct]` filled by the standing `ages()` sweep, so
`2026-07-28 · 01d ago` is two phrases rather than one continuous digit run.
No date in the title stays plain text. The date is day-resolution only, so
`ct` is local midnight of that day.

**An updated question also says so (#473).** "Updated" is a *per-entry
content change* — body, notes or answers — not the file mtime of
`questions.md` (a neighbour's answer rewrites the same file). The server
tracks a content digest per entry in machine-local
`.dreamwork/question-sigs.json`; first sight records the digest with no
stamp, a later change stamps `updated_at` and appends a best-effort
`question-updated via watch: …` line to `watch-events.log` (that channel is
lossy by design, so the display half is the reliable deliverable). The
title line then carries ` · updated X ago` via `.age.qup[data-ut]`, the
same chrome separator and ages() sweep as #456 / #463. Honesty reuses
#463's rule: ages() suppresses the secondary when `ageStr(updated)` equals
the created figure — exact inequality produced 24 false positives of 28
there. Digit flips are pure text (no transition); the *node's* first
appearance is an arrival (`.dreamin` via `revealQuestionUpdates`), with
reduced-motion settling fully lit. Guard: `dev/capture/qsignal.mjs`.

**A question headline is therefore no longer its title.** `qtHtml` emits the
age span *between* the date and the ` — ` separator, so `.qt`'s textContent is
not the raw title with something appended — the title is **interrupted**, and a
substring test against it fails. Anything asking *"is this the same question?"*
of rendered text must strip the age node first; `dev/capture/dom.mjs`'s
`dockHeadline` is the one copy of that rule and both dock guards use it. This is
not hypothetical: adding the age silently reddened `docktarget` and `noteprop`
for six hours, and because the failures were inherited by every lane as
"pre-existing" nobody read them. Identity that must survive presentation belongs
in **data** — `posted.question` (#266) reads the question id path, never the
headline, and it stayed correct throughout.

**So every piece of headline chrome is a NODE with a class, and that class is
listed in `dockHeadline`** (#474). Not a rule of tidiness — the strip is the
only reason a rendered-text identity check can work at all, and text cannot be
stripped by node. `#456` added its ` · ` between the date and the age as **bare
text**, so removing the age node left the middot behind, the raw title stopped
being a substring of the result, and `docktarget` and `noteprop` failed for two
days on a page that was behaving correctly — the second instance of exactly the
failure the paragraph above warned about, and the reason `#473`'s separator is
already an `.rsep` node. Both middots are now `.rsep`, which also settles a
cosmetic inconsistency: one of the two used to be dim and the other title-bright.

The list in `dockHeadline` still has to be extended by hand when chrome is
added, so the guards **derive the precondition** rather than trusting it: they
read raw and stripped textContent and assert the two **differ**. A strip that
removes nothing is indistinguishable from one that works, right up until the
headline changes shape — that is what makes the assertion worth its one line.

**The number of figures IS the precision, and that is a deliberate departure
from #385's always-two-figures grammar** (#392a). A question title carries a
DAY and no TIME, so its midnight `ct` cannot honestly produce the hour figure
#385 wrote beside it: measured on the deployed dashboard, a question that
landed at 07:54 rendered `08h 17m ago` at 08:18 — midnight to the second, an
eight-hour lie about a 24-minute-old entry. The error was LARGEST for the
newest entries (exactly the ones where *how long has this been waiting* is
the question) and invisible on old ones (`02d 08h` for a three-day-old
question is believable), which is why it sat unnoticed. So a date-only title
now renders ONE figure — `03d ago` beside a timed commit's `03d 07h ago` —
and the MISSING second figure is the signal, read against the timed entries
beside it. `qtHtml` marks the span `data-day="1"` (the precision of the
input) and `ages()` routes it to `paintDayAge`, which is `paintAgePair` with
the second figure removed: the same `ageParts` ladder and the same greyed
`.agepad` pad digit, never a second humanizer. No tilde, tooltip, badge or
new glyph — the grammar itself encodes it. (Putting a time INTO the format is
#392b, blocked on another lane holding `file-formats.md`; this half removes
the whole user-visible error from the data the page already has.)

**An entry dated TODAY reads as the word `today`** (#392a) — the one case the
human sees most and the one a figure gets most wrong. `0d ago` reads as a
broken zero for something filed this morning, and `0d 0Xh` would repeat the
very claim a day-only date cannot support. `today` is a singular, deliberate
break from the figure grammar — the one honest thing day-only data can say
about the day it is in — and it is the whole of the special-casing: under a
day old (`s < 86400`, i.e. the same calendar day as the midnight `ct`)
`paintDayAge` writes the word and returns. A future-dated entry (clock skew)
clamps to `today` too, which is #385's existing `Math.max(0, …)` negative
clamp, unchanged.

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

**The departure has two beats** (#277): the question-card ghost dissolves in
place for `180ms` (`.pregone`: blur `0→8px`, opacity `1→.8`, `≤2px` drift)
before `.gone` sends it away, so it reads as "dissolve then leave" rather
than "mush then snap". `.gone`'s blur is `8px` (matching `.pregone`'s peak),
so the corpse never gets crisper as it leaves. The commits panel skips
`.pregone` and keeps its original `6px` blur via `.commit.gone` — its gesture
is the grow-and-fall, and a `2px` upward drift would fight the `14px` fall.
The whole motion contract lives in `transitions.md` (*The departure has two
beats*); reduced motion never creates a ghost at all.

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
could not read it", which is #136's rule one panel over. **A no-body commit
shows its FULL subject in the detail first** (#486): the header's `.gsub`
ellipsises (`nowrap` + `text-overflow`), so without `.gfullsub` the one line
the commit has to say is truncated in the header and shown nowhere — worst on
the loop's own long fold subjects. The parenthetical stays: it still says
*why* there is no body.

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

**The remedy is on the page (#462), and it runs the deploy.** The row named the
fault; without more it told him something was wrong and gave him no way to act
on it. Increment 1 shipped a copyable `just deploy` pending his consent.
**Authorised 2026-07-29 03:46 (`rec`)**: a `behind` row carries `just deploy`
as an **action** — loopback peer only, single-flight, behind the existing
confirmation idiom. What "update" means is stated by what the running process
IS: `just deploy` snapshots `watch.py` from HEAD and restarts, and the
`GENERATION` bump reloads this tab.

**Arm, then POST — #290's cooldown, not a second one.** First click arms for
`RUN_ARM_MS` (10s, the run-mode arm reused); re-click cancels; only the deadline
POSTs `/deploy`. The server refuses a non-loopback peer and a second deploy
while one is in flight (durable `rejected`, so `writeVerdict.landed` is false
— never `res.ok` alone, E5b). The POST returns as soon as the runner is
scheduled; the process may die when the deploy stops the listening snap.

**What the page shows.** On the page's one confirmation lifecycle (`#fmsg`,
same `confirmationFor` as the file-path copy):

| state | copy |
|---|---|
| arming | `arms in Ns — then this page updates` |
| running | `updating — waiting for the new page` |
| refused (another machine) | `update was refused — the update only runs from the machine serving the page` |
| refused (already running) | `already updating — this page will pick up the new one when it lands` |
| never finishes | `update never finished — this page is still the old one` |
| success | a new `GENERATION` → full `location.reload()` (the page *is* the new one) |

**Why two refusal rows, and the general rule they establish.** Both refusals are
`domain_invalid`, because `REJECTION_REASONS` is a three-wide contract and this
route can refuse for two unrelated causes. Reusing the generic `REJECT_WHY` copy
said *"the value was not one the server accepts"* for both — and since these are
the only two refusals he can provoke, that copy was wrong every time it appeared.
So a rejection may carry an **optional `detail`**, narrowing the reason **for copy
only**: `DEPLOY_WHY` maps it, `writeVerdict` carries it through beside `reason`,
and nothing ever gates on it — `landed` remains the only verdict. Widening the
closed set would change the journal contract; a copy hint does not. Any route with
several refusals behind one reason takes this idiom rather than a second one.
(The dead branch this replaced tested `res.status === 403`, which the 202 cutover
had made unreachable, so its "only runs from this machine" line could never print.)

**Deadline: `DEPLOY_WAIT_MS` = 30s.** `just deploy`'s own readiness is sleep 1
+ up to 5s of curl probes (~6s healthy); 30s is ~3× that budget so a contended
box is not a false timeout, and still short enough that a hung deploy is not a
spinner forever. The message is a copy decision as much as a timing one.

**Drafts survive the restart.** #269 keys them in `localStorage` per target;
a restart destroys the *server*, not the loaded document's storage. The
generation-bump reload restores them through the existing draft path.

**The line itself still has no new motion; the remedy arrives.** The line's
*presence* can only change when HEAD moves, which is already the commits
panel's own gesture (#151), and `behind` → `current` is a redeploy = a new
process = a `GENERATION` change = a full reload, so the line departs with the
page and needs no motion of its own. The *remedy* is different: it appears
exactly when the page falls behind, which is an **arrival**, and it obeys
`transitions.md` with no exception for size. It uses the one-shot `.dreamin`
idiom mirrored from `revealNewOpenAsks` (`revealStaleAction`): the start pose
is applied only on the genuine current→behind transition, never on first paint
(which settles visible), never replayed on a tick where it was already
present, and never under reduced motion (function, no pose). Arming/running
are class toggles on the same control (`paintStaleDeployUI` after `setContent`),
not a second arrival gesture. `dev/capture/staleremedy.mjs` guards the arrival
by sampling mid-transition opacity (`midFrames`) with `transitionstart` as the
load-independent snap detector, reduced-motion parity, a runtime-derived
current→behind precondition, the rejected-POST path, the never-finished
deadline, and draft survival across reload.

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

**The scrollbar gutter is reserved, always (#464).** His report: the bar
appearing and vanishing as the box grows *"causes text to reflow… a bit
distracting."* The reflow is a width change when the scrollbar leaves, so
**reserving the gutter** removes it. `#cmdform textarea` carries
`scrollbar-gutter:stable` — the gutter-without-furniture reading of *"always
show"*, not a permanently-visible bar. Both fix the reflow; the gutter does
it without adding chrome this page deliberately keeps scarce. Overflow still
scrolls past the 15-row ceiling; reduced motion only drops the height-travel
timing and leaves the gutter. The answer box is not in scope: he named the
command composer.

**The box grows with what he types, then scrolls (#177).** His numbers are the
contract: the composer starts at 2–3 rows and grows to **15**, then scrolls
past that. The answer/note box on every question card starts at 2 and grows to
**6** — a smaller ceiling on purpose, because a 15-line box *inside a question
card* would shove the whole list for a ten-second sentence, and the two
surfaces hold different kinds of thought. The ceiling is a per-surface constant
carried as `data-max-rows` (15 / 6) and resolved against the box's own measured
line-height in `fitText`, so it tracks the font rather than a pixel literal.

The growth is **the page's one height-travel gesture, not a second one**: the
box's `height` rides the same `.85s cubic-bezier(.32,.1,.2,1)` curve the card
fold and `#104`'s regroup use, and what sits below it is **carried** by that
travel rather than teleported — a height transition re-flows the box's
containing block every frame, so the cards under a growing answer box (or the
composer's send row under a growing thought) ride the growth continuously,
welded to it. The plan's literal seam (`snapshot → resize → regroupCards(…,
card)`) was the first instinct and reuses the right gesture, but `travelCard`
clamps the host card to its old height with `overflow:hidden` for the travel,
which hides the line he just typed — and its caret — for the whole `.85s` on
every newline. That is unacceptable for the most frequent animation on the page,
so the box itself owns the travel (caret always in view) and carries what is
below on the same curve; the gesture is the page's, only the carrier differs.
Shrinking back (a deletion, a cleared send) is the same gesture reversed, never
a snap. `resize:none` because autosize owns the height — a manual drag and a
content fit fighting over it is a box that loses his resize on the next
keystroke. Reduced motion keeps the growth (function) and drops only the timing.
The box's height is now **state**, so `#118`'s tick-survival applies to it:
`restoreCardState` re-fits the box from its restored content **snapped**
(`fitText(ta, false)`), so the tick never re-grows a box he is mid-thought
in. The height is not carried in the snapshot — recomputing it from the
content is the same value and cannot drift from the text the snapshot also
restored. There is a second, redundant restore-fit: `restoreAnswerDrafts`
(the `dw:adraft:` reload backstop, #269) also calls `fitText` when it puts a
stored draft into a fresh box, so a tick's height survives either path
independently. `dev/capture/autogrow.mjs` reds on tick-survival only when
BOTH are removed (93px → 45px floor); removing the snapshot path alone stays
green because the draft path masks it — the check is not hollow (it reds
when survival is genuinely broken) but it cannot isolate the snapshot line.

Because autosize owns the height, **a guard must never assert a height it set
itself** (#474). `noteprop` seeded `ta.style.height = '80px'` and required
exactly that back after a tick; `fitText`'s restore branch correctly re-fit the
box to 96px and the guard went red in both motion modes on behaviour this
styleguide had already specified. It now dispatches `input`, lets autogrow
choose, and asserts *that* height survives — the invariant that outlived the
change. The same guard also has to wait for the .85s travel to LAND before
seeding `scrollTop`, because a textarea clamps scroll to its current scrollable
range: seeded mid-travel it recorded 160 in normal motion and 109 in reduced for
identical content, and the post-travel re-clamp then read as lost scroll. `dev/capture/autogrow.mjs`
guards growth, both ceilings, scroll-past-ceiling, shrink, reduced-motion parity,
and that the growth carries the cards below rather than teleporting them.

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

**The answer box's half-typed draft survives a reload too** (#269, acute). The
composer's store is one surface; the per-question answer box on the review dock
is where he actually answers the loop, and it had only #118's IN-MEMORY snapshot
— which carries a half-typed answer across a tick re-render but drops it on a
reload, exactly the loss he reported ("never lose work on an autoreload of a
page"). The reload is the one `tick` performs on him the moment the server's
generation bumps (a restart, a redeploy, an edit under `--autoreload`), so it
strikes mid-thought. **`DraftStore`** is now the one module every text surface
consumes (extract + `#459`, still `localStorage` — IndexedDB deferred because
sync write on `input` must not become an async hazard mid-keystroke). `dwDraft`
remains a thin façade over `DraftStore.id('card', title)` so existing call
sites keep the title-keyed shape. Rules, verbatim across every consumer: save
on `input` with no debounce, restore only into a mounted element that declares
its logical id (never fuzzy-match), clear only when `DraftStore.isDurable`
says the write landed (today: `writeVerdict.landed` when attached, else
`res.ok`; `#263` receipt is a later body for that one function), a live box
outranks storage (#118), every storage call is try/catch.

Logical id is `kind:scopeKey` inside the `data.target` partition. Primary key
`dw:draft:v1:<target>:<logicalId>`; dual-read of the pre-module keys
(`dw:adraft:<target>:<title>`, `dw:draft:<target>`) so an existing browser
draft is not orphaned by the extract. On save through the new API the old key
is removed after the new one is written. Consumers today: `card:<title>`
(answer/note boxes), `composer:main` (`#cmdtext`), **`ask:main` (`#askbox`)**,
**`popout:main` (`#ptext`)** — the last two had no persistence at all and are
the discriminating proof the module is a module. Cross-tab (C1 offer-to-load)
and 30-day GC leave seams only.

Cards key by the question's **title** — its `data-qid` identity, stable across
a re-render, a re-sort and the re-index between sections (`o3`→`a0`), where the
positional key is none of those. The store runs *after* the in-memory snapshot
has had its say, so the snapshot wins and storage is the backstop: #118 across
a tick, DraftStore across the reload #118 cannot. Restores silently and before
paint (no new gesture — the text in the box is the statement).

The diagnosis mattered and is recorded for the agent that generalises this: the
report named the *live re-render* as the probable cause, but reproducing both
modes showed the tick was already covered by #118 and the **reload** was the
real loss — a fix verified only against the tick would have left his reported
bug untouched. `dev/capture/reviewdraft.mjs` drives *both* modes for the dock,
proves dual-read of a planted legacy key (old-key precondition asserted at
runtime), and proves `#askbox` / `#ptext` survive a real reload.

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
steering kinds — `{kind, label, desc, common, sticky}`. The server derives
`COMMAND_KINDS` from it to validate `POST /command`, the page embeds it as
`CORE_COMMANDS`, the composer renders its buttons from it, and the popped-out
form fills its `<option>`s from it. A new kind is one entry and nothing else.

**A landed command does not keep its kind** (#337). `sticky` is the one
property that decides: after a successful submit the composer decays back to
the sticky kind, and `add idea` is the only one. A mode that persists
silently raises the authority of his NEXT message, so the composer settles
on the least dangerous kind — #257's danger reasoning for `do now`,
generalised to every steering kind, `maintenance` included. Absent means
NOT sticky: a plugin kind that says nothing decays too, so a new kind is
never a third place to remember. The decay rides `setKind` — the
indicator's existing slide, never a second gesture.

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

**The menu grows LEFT from the ⋯, and the page never scrolls sideways (#312).**
The ⋯ sits at the right end of the kinds row, so the menu is anchored to its
RIGHT edge (`right:0`) and opens leftward into the room the composer already
occupies — a `left:0` menu grew right, off-screen, by 122px at a 390px phone.
That it did so while *shut* was the trap: `visibility:hidden` is not
`display:none`, so the box was still laid out and still counted toward
`documentElement.scrollWidth`, palette open or closed, on every route — a
phone could thumb the whole dashboard sideways. The body never scrolls
horizontally; the menu holds its preferred `32ch` wherever that fits and
`max-width:calc(100vw - 2rem)` clamps it before its left edge can cross the
viewport. `dev/capture/hfit.mjs` is the red light: at 390px it asserts
`scrollWidth <= clientWidth` on each route, palette closed and (on the
dashboard) with the menu open, and it asserts the menu is present and
populated first so the check can never pass over an absent subject.

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

A failure **names what he can do instead**, in the same breath and without
apologising: `question was refused — your words are kept`,
`dreamwork is unreachable — your words are kept`,
`copy was blocked — the path beside it is selectable` (#284). The em dash is
the idiom's own punctuation — a state, then its consequence for him. Success is
shorter than failure because it needs no consequence: `path copied`, `asked`,
`sent to the dream`.

**Review-artifact orientation** is not a second summary. Headline and sub
already summarise; what he is missing is consequence and situating — see
*Review artifacts / Orientation before the ask (#455)*. The one sentence
the build requires is the cost of silence (`#if-silent`): blocked, default,
or parked. Do not pad the other three answers into every page that already
carries them.

## Non-goals

- The request-authority policy is not authentication. It does not make a LAN
  private, add TLS, trust proxy headers, discover DNS/IPs, or support WAN/public
  exposure. Bearer-token LAN access and public Dreamhub auth are later designs.
- No historical analytics; a live window, not a metrics store.
