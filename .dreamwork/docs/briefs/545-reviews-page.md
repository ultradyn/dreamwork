# Brief #545 — dashboard reviews: most recent ~5 + a /reviews page

**Task** (ledger #545, origin loop, receipt d824b6c0): Max via watch
add-idea 16:33 — *"the 'reviews' section on the dashboard can be many
lines long (31 atm). Show the most recent ~5 and link to a dedicated
/reviews page."*

## Scope

Two parts, one lane, both in `watch.py`:

1. **Dashboard section capped at 5.** The dashboard `reviews` section
   renders the most recent ~5 artifacts and a link line to `/reviews`.
   "Most recent" is the section's EXISTING order (#463: filesystem birth
   newest-first, ascending filename tie-break) — take the first five of
   what it already renders; do not invent a second ordering. The link
   line names the total honestly in the panel's voice (spare,
   lowercase-leaning — e.g. `all 31 reviews →`); when the total is ≤5
   the section renders exactly as today (no link, no "showing 5 of 5"
   noise). Rows keep the exact `artifactRow` component and their
   dock-link behaviour — a row on the dashboard and a row on `/reviews`
   are the same row.
2. **A `/reviews` route** listing every artifact through the same
   `artifactRow` factory — the listing shape the review/research
   surfaces already share. This is *navigation*, not expansion, under
   watch-design.md's expand/navigate/hover principle: the full list is
   its own subject and earns a URL.

## Hard contracts (all were bugs before)

- **All per-route tables**: a new route needs its `routeOf` / `TINT` /
  `SEED` / `TITLE_ROUTE` entries — every one of them. `test_watch.py`
  derives the destination set from `routeOf` and diffs the tables; a
  missing entry is a silent fallback (#302/#318 were exactly this).
  Titles wording: watch-design.md's crumb/title grammar.
- **transitions.md applies to any gesture** — but note the dashboard's
  standing rule: a live re-render commits its DOM instantly, and the
  cap is content on an existing panel, not a layout gesture. The likely
  honest answer is *no new motion* (same as the burndown panel's
  conditional controls). If you believe an arrival/departure is needed,
  it must reuse an existing idiom — and `transitions.md` is
  **coordinator-owned**: do not edit it; FLAG the proposed text in your
  final report instead.
- **watch-design.md is coordinator-owned.** Do not edit it. Write the
  design-record paragraph for this change (section cap + new route, in
  the file's voice) into your final report as a FLAG; the coordinator
  lands it in the merge commit.
- **Red-first per part.** Name the production line each check depends
  on, sabotage it (a line you did NOT inject for the independent proof
  is the coordinator's job — yours is the feature red), watch the named
  check fail, cp-restore byte-identical. Assert preconditions your check
  depends on (e.g. the fixture really has >5 artifacts — derive at
  runtime, never a literal tuned to today).
- **Guards**: adjacent are `revieworder` / `reviewsplit` / `reviewask`.
  Extend an existing guard or add one (e.g. `reviews5.mjs`) — your call,
  justify in the report. Solo runs only:
  `DREAMWORK_GUARDS="<names>" DREAMWORK_HUB_GUARDS= just guards <port>`
  after `ss -ltn` shows your chosen port free. Record which port you
  used. Never run the full suite.
- **NEVER `read_file` an image** (glm-5.2 API 400 kills the lane).
  Screenshots go to your scratch outdir; the coordinator renders the
  visual verdict.
- **ONE handoffs.md `## Pending` line** appended before your final
  commit (#398 obligation): id, sha, date, lane name, what landed, red
  proof, flags.
- **Commit with `git commit --only <paths>`**; new files need
  `git add <file>` first.

## Lane-owns declaration

You own: the reviews-section region of `watch.py` (dashboard builder,
router tables, any new `buildReviews`), one guard file under
`dev/capture/`, and your handoffs line.

You do NOT own: `watch-design.md`, `transitions.md`, `justfile`,
`lint.py`, `file-formats.md`, burndown regions of `watch.py`.

**Lane in flight**: lane-544burndown is working the burndown region of
`watch.py` concurrently. Keep your edits tight to the reviews/router
regions so the merges don't fight; do not refactor shared helpers it
might touch.

## Report shape

Final report: commits, red-proof evidence per part (what you sabotaged,
which check failed, restore hash), solo-guard verdict lines, the FLAG
paragraphs for watch-design.md (and transitions.md if any), port used,
and any deviation from this brief with the reason.
