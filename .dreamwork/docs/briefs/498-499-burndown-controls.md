# Brief — lane-burndown2: burndown hover % elapsed + the limit control (#498, #499)

Lane-owns: the burndown panel in `watch.py` (its generation + the panel's
JS/CSS), `dev/capture/burndown.mjs` (or a new sibling guard if a second
check file is cleaner), and `watch-design.md` (contract rows updated in
the SAME commit as the change). Nothing else — do NOT touch other panels,
`lint.py`, `file-formats.md`, or the shader/motion code outside the
panel.

**Model:** grok-4.5 · **Isolation:** worktree (coordinator merge-gates).

## READ FIRST (in this order)

1. `transitions.md` — **every transition on the UI obeys it, with no size
   floor.** #499's control APPEARS conditionally; appearing is a
   transition. Reuse the existing arrival idiom; author no second one.
   Reduced-motion parity is part of the same obligation.
2. `watch-design.md` — the burndown panel's contract rows (fixed heights,
   copy voice). #417's ruling: **every height in this panel is fixed so
   fresh data never moves the page, and copy lines must not wrap.**
3. The two store entries, quoted below verbatim.
4. `dev/capture/burndown.mjs` and how guards register in the `justfile`.

## The two features (his words, via add-idea)

**#498 (P3):** *"where burndown shows 'period in progress' on hover, it
should show the % of that period elapsed after (eg '43% elapsed')".*
Pure hover-copy extension of the existing tooltip/helper (the one #494
just fixed — find that commit for the current shape). Compute from the
period's real start/end, not from column index.

**#499 (P3):** *"when we have more than 28 elements, we should show,
after 'X landed · <period>', a thing like 'limit [ 28] [⟳]' where [ 28]
is numerical input (<=0 for all/max; max of 168 maybe), and [⟳] is a
button to reset to default (28)."*
- The control renders ONLY when the element count exceeds the active
  limit (today: more than 28) — when absent, nothing reserves its space
  differently… except #417's fixed-height rule: decide and document
  whether the control shares the existing count line (preferred — no new
  row, no height change) or needs a documented slot. A new row that moves
  the page is a contract violation.
- Input semantics: <=0 means all/max; hard cap ~168; invalid input is
  refused quietly (the panel's voice — no toast idiom that doesn't
  already exist). Reset (⟳) restores 28.
- State: client-side only (no server state, no new endpoint). Choose
  between URL param and localStorage-per-project and RECORD the choice
  with its reason in watch-design.md; consistency with how the page
  already keeps small UI state is the tie-breaker. Cross-tab behaviour
  must not fight the posture picker's shared-arm idiom.

## Constraints (hard)

- Red-first guards: extend `dev/capture/burndown.mjs` (or add a sibling)
  with checks that FAIL before your change and PASS after — at minimum:
  (a) hover copy for the in-progress period contains a plausible
  `N% elapsed` figure derived from the fixture's real period bounds
  (assert the derivation, not a literal tuned to today); (b) the limit
  control is absent at/below the limit and present above it; (c) the
  fixed-height premise still holds with the control visible. Each check
  asserts the runtime precondition it depends on (the repo rule: a check
  whose meaning needs two pieces of fixture state to differ derives both
  and asserts the gap).
- **A green red-run is a finding, never a relief.** For each guard: name
  the production line that would have to change for it to fail, change
  that line, watch it fail, restore byte-identical (`cp`, never
  `git checkout`). If you cannot name one, the check is wrong.
- Visual review is not optional: headless screenshots (desktop ~1280 and
  mobile ~390) of the panel in all four states — control absent, control
  present, hover with % elapsed, reduced-motion — embedded or saved for
  the coordinator to inspect. The acceptance bar is EXCEPTIONAL quality,
  not functional.
- Small commits, `git commit --only <paths>` (new files `git add` first).
  NEVER `git add -A`. `watch-design.md` rides the same commit as each
  contract change.
- Never `attn`, never `pkill -f`, never ports 35110/39880-39899. Guards
  bind 39890-39899 via the runner; `ss -ltnp` first if a bind fails, and
  leave no fixture server running at the end.
- Do NOT deploy. The coordinator merge-gates and deploys.
- **The worktree/store trap (known, has bitten before):** your worktree
  lacks the gitignored `.dreamwork/ledger.sqlite3` — a worktree checkout
  sees the `#458` deprecated shim and burndown data will be EMPTY. To see
  real data: copy the main checkout's store (and watermark, if any) into
  a scratch target under /tmp and serve your modified `watch.py` with
  `--target /tmp/<scratch> --port <39890-39898>`. NEVER point anything at
  the main checkout's live `.dreamwork/` for writes; read-only copy only.

## Acceptance criteria (measurable)

1. Hovering the in-progress period shows the existing helper text plus
   `N% elapsed`, N derived from real period bounds (guard (a)).
2. With element count > active limit, the count line carries
   `limit [ 28] [⟳]`; at/below, it does not (guard (b)); input and reset
   behave exactly as specified, invalid refused quietly.
3. Fixed heights unchanged; no wrap; control arrival/departure uses the
   existing transition idiom with reduced-motion parity (guard (c) +
   screenshots).
4. All guards PASS; each new/changed check has a named, executed
   red-proof; `python3 lint.py` no new findings vs a master baseline.
5. Screenshots for the four states attached to the report.
6. `git diff master --stat` touches only the owned paths.

## Hand-off obligation (#398)

Final report (the coordinator writes `.dreamwork/handoffs.md` from it):
what shipped per feature, each guard's red-proof (injection + production
line), the state choice and its reason, the screenshot paths, and any
pushback on this brief.
