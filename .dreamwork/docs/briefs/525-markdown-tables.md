# Brief — #525 markdown tables not rendered in the markdown view

Ledger id: **#525** (bug, his report 2026-07-30: "oh please log
corresponding bug for tables not being rendered either" — the third in
the family with #521 quotes and #522 links, both landed).

## The defect

The `/file` rendered-markdown view (`mdBlocks`/`mdRender` in watch.py —
the region #521/#522 just extended with the `MD_QUOTE` quote kind and
`linkifyMd`, merged `f0d9458`) has no table kind. GFM pipe tables in
served markdown render as raw prose lines, pipe glyphs and all.

## The fix

Add a table block kind to `mdBlocks` (pipe-table recognition: header row,
`|---|` delimiter row, body rows; consecutive lines) and render it in
`mdRender` as a real `<table>`. Cells run through the SAME inline pipeline
as quote/paragraph content (linkifyMd etc.) so a `[text](target)` inside
a cell behaves exactly as it does in prose. CSS per `watch-design.md` —
read it first; the table must be quiet, dim-ruled, and monospaced-numeric-
friendly the way the rest of the surface is. Every transition rule in
`transitions.md` applies, though a static table should need none.

Scope discipline: pipe tables only. No alignment colons beyond ignoring
them gracefully, no cell merging, no block content inside cells. Fences
win — a pipe-table-looking region inside a code fence stays code (the
`if (fence) { fence.push(line); continue; }` line is load-bearing; your
red-proof must cover it).

## Proof obligations

- Extend the `mdquote.mjs` guard (or add a sibling guard registered the
  same way) with table checks: header/delimiter/body recognition, fences
  win over pipes, inline links inside cells resolve via linkifyMd, a
  malformed table (ragged rows) degrades to prose rather than
  half-rendering.
- Red-proofs by injection + cp restore, each naming the production line:
  table kind removed → FAIL; fence-wins broken (table parsed inside a
  fence) → FAIL; cell inline pipeline skipped → FAIL.
- Visual evidence: screenshots desktop + 390px of a served markdown file
  with a table — the coordinator inspects the actual pixels at the gate.
  Guard writes screenshots into its OUT dir, not the repo.
- Preconditions asserted in the check, derived at runtime (the
  hollow-check rule): the fixture must contain a table the check can
  distinguish from prose.

## Lane-owns

The `mdBlocks`/`mdRender` region of `watch.py`, its `.md` CSS block, and
the guard file(s) under `dev/capture/`. Nothing else in watch.py. The
region is free — #521/#522 merged `f0d9458` and their readiness fix
`635a29cb`.

## Handoff

Append a literal Pending line to `.dreamwork/handoffs.md` in the
established grammar (`- **#525** · landed \`<sha>\` · … · by
<claimer> —`), including reds, guard counts, and the visual evidence
paths.
