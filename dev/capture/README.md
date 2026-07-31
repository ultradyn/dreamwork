# watch capture / instrumentation scripts

Headless-chromium evidence for `watch.py`. Two kinds live here, and the
difference matters:

- **Guards** exit non-zero and are gated by `just guards`. They assert.
- **Captures** print and screenshot for a human. They gate nothing.

Only put a script in the guard list when it fails for a reason you would
want a commit blocked over.

## The contract

**Every script takes `(OUT, PORT)`** — an output directory and the port of a
running watch server. It was two contracts for a while and that cost a
falsely-reported regression, because `(BASE_URL, OUT)` and `(OUT, PORT)` both
"work" until you read the output.

**Guards run against `fixture/`, never against this repo.** `just guards`
copies the fixture to a temp dir, serves *that*, and resets it before every
guard. Two things follow:

- Content is frozen, so a red light means the code broke — not that the loop
  folded the last awaiting-fold question overnight. A guard that depends on
  mutable content is testing the content, and its false reds train you to
  ignore it.
- Guards may **write** (POST `/answer`, `/comment`) without touching the real
  `questions.md`, which is what had kept the most valuable ones ungated. The
  per-guard reset is why one writer cannot eat the fixture the next one
  needs; without it you get a red that is really a run-order bug.

When a guard needs a shape the fixture lacks, add it to the fixture. Reaching
for live content is how this got broken the first time.

**House rules for a new check** — each earned on 2026-07-25, most more
than once:

- **Red first, for its stated cause.** "It went red when I broke the
  feature" is not enough when one break reddens twelve checks: break only
  the thing THIS check names and watch THIS check fail. A check that
  cannot fail for the reason its message names sends the next person to
  the wrong file (three of one batch's own guards had this).
- **Run it against nothing.** A per-line loop over an empty file, an
  `every` over an empty array, and a rebuilt-in-the-guard expectation all
  pass over an absent subject. Ask what your check says when its subject
  does not exist — it takes ten seconds and it is the only reliable form.
- **Absence costs one line, not a timeout.** Assert the subject exists
  before driving it: 3.4s and a named FAIL beats thirty seconds of
  Playwright timeout reported as "the guard threw".
- **Report from full output, never a count.** A `grep -c` in a compound
  command reported 6 FAILs where the full output held 14. A count is not
  evidence.
- **Prove a green was caused by your change**: revert only the change on
  the same range and watch it go red again. A green that appears after an
  unrelated edit is luck until shown otherwise.

## Guards (gated)

- `headertravel` — the heading survives a route change and travels; the
  column glides; the `+` opener is never clipped, on any frame, at any width.
- `reflow` — hard-wrapped prose reflows; an A/B of both renderers over a
  width sweep; raw text stays verbatim.
- `qacard` — one question component across `/questions`, the dashboard and
  the review dock, compared structurally.
- `oneinput` — one field per card, send flush against it, the mode picking
  the endpoint; the indicator lands then slides.
- `regroup` — answering a question moves it: it travels, its neighbours
  close the gap, and reduced motion does neither.
- `popbg` — a popped-out window carries the world-space shader field, and it
  matches the main window across the document boundary.
- `typing` — what he is part-way through typing survives a live tick: the
  text, the caret, the focus and the destination mode. `/questions` only.
- `wisp` — the awaiting-fold breath: one envelope, both halves, and it holds
  still at its brightest under reduced motion rather than disappearing.
- `states` — every cell of the question state matrix, asserted on OUTCOME
  (did the card end up somewhere else, continuously) and not on mechanism.
- `dismiss` — a review dismissed from the dock.
- `thread` — a settled follow-up thread folds, and opening it moves the
  cards below it on the shared regroup.
- `status` — the status panel's facts, and its fold-by-complement.
- `motion` — the commits panel's gesture: a re-render never takes the focus
  out of the box he is typing in (#179, both triggers), nothing below the
  panel moves while it cycles (#184), and the cycle travels DOWN (#174).
  Builds its own git target.
- `health` — several targets in states one fixture cannot hold at once
  (missing / unparseable / seeded). Builds its own targets and servers.
- `dashboard` — the commits panel's static half and #151's motion. Builds
  its own git repo with commits planted at known ages.
- `identity` — the title and favicon across a SEQUENCE of loop states on one
  live page, so nothing reloads between them.
- `submitlog` — a REFUSED submission still leaves his words on disk (#199).
  Forces a real 409 the way #116 caused them — the page holding a title the
  file will not match — and then looks for his text in `submissions.log`.
  The successful case is the control, not the check.
- `history` — the composer's history panel (#165): the FAILED sends are in it
  and marked, newest first, and it states what it does not cover. The failures
  are the point — a history showing only successes reads as complete.
- `subslog` — the client's own record of every submission (#175), asserted on
  all three outcomes (`ok`, `rejected`, `unreachable`) and on `pending` caught
  in flight, which is the only moment that proves the record is written
  BEFORE the request.
- `draft` — the composer's half-typed thought survives a real reload, a
  rejected send and the mode-switch defocus path (#163, #162b), and is
  forgotten on a successful send and nowhere else. Both directions, because
  either one alone passes on a page that does the opposite of the feature.
- `indicator` — the composer's selection indicator lands on the button it
  marks even though it is painted mid-reveal (#198). Bounded window, because
  the bug is laundered by the next re-render rather than self-healing — and
  the guard proves that laundering path rather than trusting it.
- `qorder` — questions in priority order, then oldest, on BOTH surfaces (#197).
  Its load-bearing assertion compares the dashboard against `/questions`
  rather than against a list written twice here, because the failure it exists
  for is the two surfaces sorting separately. Also drives a live reorder and
  asserts the cards below it travel rather than jumping.
- `plugcmd` — a plugin's declared commands, in the composer that has to offer
  them (#86). Drives the FILE — unloaded first, so the common case (no plugin
  declares anything) is checked before the populated one — and asserts the
  arrival's intermediate opacities, that the surviving items were reconciled
  rather than re-created, that a plugin cannot reach the main row, and that
  `POST /command` accepts what the menu offers.
- `burndown` — the ledger's own history, drawn (#142). Plants a ledger
  history, then COMMITS INTO IT while the page is open so a real data change
  arrives on the tick. Its sharpest checks are not about the motion: that the
  panel's height never changes (the premise that lets bars animate without a
  FLIP), and that the bars still HAVE a height when the travel ends — which
  is how it found the chart collapsing to its 2px rules after every
  animation. It also states, in its own header, the one thing it does NOT
  check and why. Builds its own git target.
- `provenance` — who filed each task, by first sight (#217): the burndown's
  human / loop / historical-unknown coverage, where unknown is drawn as
  itself and never rolled into loop. Plants a ledger history whose truthful
  answer is known — including an entry marked human an hour AFTER it
  arrived, which must stay unknown forever — and asserts the exact counts,
  the denominator copy, the segment geometry, the hatch, the aria-label,
  no accent and no motion, at 1440x1000 and 390x844, plus the shallow
  clone's named incompleteness. Shown red against the
  unknown-counted-as-loop sabotage. Builds its own git targets.
- `gitrow` — a commit row expands (#166), and does it on the page's own
  gesture. Three of its checks are for contracts the row INHERITED by
  becoming a `<details>` and that no end-state check can fail on: the FLIP
  window (#169's air must land in layout, not transition — this is the list
  `prominence` does not reach), the panel's constant height (#151), and
  surviving the tick (#118). Builds its own git target.
- `serving` — which revision the page is RUNNING (#140), across all four
  answers: no repo, untracked, current, behind. Evolves ONE repo forwards
  because the answer is a function of history; the load-bearing part is that
  only ONE of the four means "I compared and they differ", and two of its
  checks assert the fixture still DISCRIMINATES (watch.py has history at all;
  HEAD really moved past the served revision) before comparing against it.
- `qsec` — the dashboard's questions fold arrives and departs (#196): the
  panels below it travel rather than teleporting, never overshoot, the body
  eases in and dreams away, reduced motion does neither, and the ghost holds
  no address — driven over a real tick, because that is what the address
  would have cost.
- `hfit` — no route scrolls the page sideways at phone width (#312, #595). The
  command menu lives in the persistent chrome and a `visibility:hidden` box
  is still laid out, so a hidden `.cmdmenu` anchored at the ⋯ pushed a 122px
  horizontal scrollbar at 390px on every route. At 390px it asserts
  `documentElement.scrollWidth <= clientWidth` on each route (palette closed)
  and on the dashboard with the menu open, and it asserts the palette and a
  populated menu exist first — the check must not pass over an absent subject.
  #595 is why it is worth reading before writing a content-shaped guard: this
  file PASSED while the live dashboard scrolled 28px sideways, because its two
  other subjects are crumbs whose length comes from DATA and the fixture's
  values happened to be short. The precondition #312 wrote covered the menu it
  was written for and nothing acquired later. Now: the fixture carries a
  worst-case skill-version, a length precondition fails if that is ever
  shortened back, `/file` is in the route list, and a stress section injects
  160 characters into every unbounded slot — the contract is about ANY value,
  and a check tuned to today's data goes quiet the day the data changes.
- `gutter` — the page never moves sideways because a scrollbar came or went
  (#597). Tall routes (`/`, `/questions`, `/file`) take ~10px of classic
  scrollbar out of `clientWidth` and short ones (`/answers`, `/reviews`,
  `/research`, `/chat/<id>`) do not, so the centred column SNAPPED 5px on every
  navigation between the two kinds — the "elements jump around" complaint that
  hoisting the chrome out of `#view` exists to answer, reintroduced under it.
  Fixed by `html { scrollbar-gutter:stable }`. **This is the one guard in this
  directory that launches with `ignoreDefaultArgs: ['--hide-scrollbars']`**, and
  that is the finding worth carrying: Playwright hides scrollbars in headless by
  default, so in every other guard here the scrollbar has zero width and the
  whole class of scrollbar-driven layout effect is invisible. Its first check
  refuses to grade anything until it confirms the scrollbar consumes width in
  the browser actually running, so a Playwright upgrade cannot quietly turn it
  back into the green light it replaced. Samples `#htitle.x` every frame across
  the transition, at 1440px and 390px — a snap is one frame, and a settled
  before/after read cannot see a page that moved and moved back.

Four of those build their own target and take an ephemeral port, ignoring
the one they are handed: `health`, `dashboard`, `identity`, `motion`.
`gitrow`, `serving`, `burndown` and `provenance` do the same —
the justfile's `guards` recipe says which shape each is and why.

## Captures (not gated)

`beautycap`, `cmdcap`, `menucap`, `indtrace`, `note82`, `optrace`, `pip83`,
`reviewcap`, `rm-check2`, `worldspace`.

## Durable techniques

- **Trace motion per frame.** A screenshot of a settled element cannot tell
  you whether it travelled or jumped. Sample per rAF and look at the set of
  intermediate positions.
- **Freeze the clock** (`addInitScript` overriding `Date.now`) to compare a
  time-varying visual across captures that can never be simultaneous —
  including across two documents.
- **Prove the comparison discriminates.** Temporarily reintroduce the bug and
  check the guard goes red. A check that can only pass is worse than none.
  Also assert the plate has detail, or "identical" is satisfied by
  "identically blank".
- **Measure the right box.** `getClientRects()` on a Range returns one rect
  per inline *box*, not per line — group by top edge first. And
  `getBoundingClientRect()` includes transforms, so use `offsetWidth` when
  the question is "did this re-lay-out".
- **Scope to one component.** Counting `.qa textarea` across the page
  measures the page; a component assertion wants one card.
- **Assert the SIGN, not the magnitude, whenever direction is the report.**
  "It moved" and "a ghost existed" are both satisfied by a gesture running
  exactly backwards — #174 was a departing row travelling *up* into the
  gesture pushing everything else down, and every existing check passed on
  it. The same trap as counting that the wisp changed rather than how.
- **A key must be the whole identity.** Truncating `data-qid` for a readable
  trace label merged three cards whose titles share a date prefix into one
  series, and the run reported that nothing moved. Key by index or by the
  full attribute; shorten only what you PRINT.
- **Ask what your own check does when the subject is absent.** A "the row
  arrived" filter written as "missing from some frames" also describes the
  row on its way *out*, so it found two arrivals and skipped its own
  assertions — passing as silence.
