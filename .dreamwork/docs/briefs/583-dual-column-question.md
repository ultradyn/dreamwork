# Brief — #583: dual-column question page

## His words (receipt a95cc0d3, do-next)

> when focused on a question like i am now, we should have a dual column
> design where the answer/note response field is taller than normal and
> is vertically centered relative to the midpoint of union of (question
> height range, viewport height / y axis). So basically if the question
> is partially on screen, we use it's visual midpoint y for the midpoint
> y of the response component, and otherwise it's fully on screen so we
> use the midpoint y of the screen. make sense? It should be smooth and
> elegant and always present regardless of where you are scrolling /
> looking.

## What changes

The `/question?qid=<title>` focus view (NOT the dashboard cards) gets a
dual-column layout: the question content on the left, the answer/note
response field on the right, taller than normal, vertically centered on
the question's visible midpoint.

## The geometry (his spec, precisely)

The response component's vertical-centre Y is the midpoint of the union
of two ranges:

1. **The question's visible height range** — the part of the question
   card currently in the viewport (from `max(questionTop, 0)` to
   `min(questionBottom, viewportHeight)`). If the question is partially
   off-screen (scrolled past the top or bottom), use the visible part's
   midpoint Y.
2. **If the question is fully on-screen** — use the viewport's midpoint Y
   (`viewportHeight / 2`).

So: `responseCentreY = midpoint(visibleQuestionRange ∪ viewportRange)`.
When the question is fully visible, the visible range IS the question
range, and the midpoint may differ from viewport-centre. When partially
visible, the question's visible midpoint takes precedence.

"Always present regardless of scroll" means the response field follows
the user as they scroll through a long question — likely `position: sticky`
or a scroll-driven repositioning, not a fixed overlay.

## Files (post-#397 client extraction)

- **`client/views.js`** — `buildQuestion(title, d)` at line 1333 renders
  `<div id="qfocus">` containing one `qaCard()`. The dual-column layout
  applies HERE, not in `qaCard` itself (the card is shared with the
  dashboard). The question body and the answer/note compose area are
  siblings inside the card — the lane must split them into two columns
  for the focus view only.
- **`client/router.js`** — route dispatch at line 1106; crumb at 3425.
  No route change needed — this is a layout change within the existing
  `question` view.
- **`watch.py`** — CSS constants (the `STYLE` / `_read_client()` path).
  New CSS for the dual-column layout goes here as a constant addition.
- **`client/style.css`** — if CSS lives here post-#397 (check
  `_read_client` / `DATA_SIBLINGS` for the actual file list).

## Contracts to respect

- **`transitions.md`** — every appearance/disappearance/movement obeys
  the transition matrix. The response field arriving on route entry,
  departing on route leave, and repositioning on scroll are all
  transitions. Read `transitions.md` FIRST and reuse existing idioms.
- **`watch-design.md`** — the styleguide. The dual-column layout must
  respect the reading column width (613.5px), the 16px outer margin,
  and the section rhythm tokens. A second column is a width exception —
  `watch-design.md` names `/review` as *the* deliberate width exception,
  so a second one here needs the same documented justification.
- **#505 reconciler** — the response field lives inside `#view`, which
  is morphdom-reconciled. Any DOM structure change must work with keyed
  reconciliation (`data-qid`/`data-keep` etc.). The response field's
  stable identity key must survive a `/mtime` tick.
- **#523** — typed text inside the response field must survive a
  data.json tick (the #523 input snapshot/restore contract, now handled
  by the morphdom reconciler's key matching).

## Scope

- `/question?qid=<title>` focus view ONLY. The dashboard question cards
  are NOT changed.
- The answer/note compose area (`.qcompose` / `.askform`) is the
  response component. It becomes the right column.
- The question body (the entry text, follow-ups, answer thread) stays
  in the left column.
- The vertical-centring logic is the core deliverable. "Smooth and
  elegant" means it tracks scroll without jank — a scroll listener with
  requestAnimationFrame, or a CSS `position: sticky` if the geometry
  allows it.
- Reduced motion: the repositioning snaps rather than animates.

## Red-first

- A structural test asserting the dual-column layout renders on the
  question focus view (two columns present, response field taller).
- A test asserting the dashboard question cards are UNCHANGED (one
  column, same height).
- Red-proof on a named production line (the layout-split branch in
  `buildQuestion`).

## Out of scope

- The dashboard. The `/questions` listing. The `/answers` page.
- Changes to `qaCard` itself (shared with the dashboard).
- A design IGC — his spec is the geometry, and it is precise.

## Verification

- `pytest test_watch.py -k question` — question-route tests pass.
- `node --check` on all touched client files.
- `python3 lint.py` — clean for your files.
- Solo guard if you add one (register in justfile, coordinator-owned —
  FLAG it and the coordinator will register).
- Visual review: the coordinator will verify on the deployed instance.

## Commits

`git commit --only <paths>` (new files need `git add` first). One commit
per logical increment. Append a `## Pending` line to
`.dreamwork/handoffs.md` when done.
