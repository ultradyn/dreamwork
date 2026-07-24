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
