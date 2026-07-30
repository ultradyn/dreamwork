# Brief #565+#569 — the posture widget: sticky on scroll, and the update countdown bar recused into it

Origin: human. #565 (add-idea, journal ord=61): the posture countdown
bar should be sticky on scroll. #569 (do-next, journal ord=65): the
update countdown bar should be recused from the posture settings
component into the remaining horizontal space after the label.

Both are the same surface (the posture widget) and are briefed together
so one lane owns the whole surface's current shape.

## Lane-owns

- `watch.py`, **posture widget region only**: the posture picker /
  countdown bar (`#posture`, `.posture`, the arm/copy lines), the
  deploy-staleness update UI (`#462`'s `.gservact` / the "updating"
  message), and their CSS.
- Tests: extend the posture/deploy tests; a guard on port 39895
  (39890-39894 are used by other lanes) if the sticky/recuse behaviour
  needs one.

**Explicitly not yours:** the composer region (lane-570compose live),
the burndown region, the chat region, the Q&A region, `transitions.md`,
`watch-design.md`, `file-formats.md`, `lint.py`, the justfile, the
ledger. FLAG, never edit.

## The two acts

### Act 1 (#565) — the posture countdown bar is sticky on scroll

His words: *"when the countdown timer bar is on screen (the part
including 'arms in 3s · hot · near-auto · 3'), it should be sticky so
that if I scroll up I can still see it. Ideally a HR line would appear
above it and then above that, the bottom of the normal page would fade
away like questions on review pages do."*

- The posture widget (the countdown bar with the axis chips) is
  **sticky** — `position: sticky` at its natural place in the flow, so
  scrolling up keeps it visible.
- The HR + fade: his ideal, not a hard requirement. If the review-pages
  fade idiom (`reviewsplit.mjs`'s mask/`@property --qfade`) can be
  reused honestly, reuse it; if it fights the sticky positioning, say
  so and ship the sticky bar alone. Do NOT invent a second fade idiom.
- Sticky must not break the page's layout rhythm — the bar occupies the
  same space it did, it just stays visible when scrolled past.

### Act 2 (#569) — the update countdown bar recused into the posture widget

His words: *"when updating the webui, a message counting down shows up
(and later shows 'updating — waiting for the new page'). We should
recuse the countdown bar from the posture settings component in the
remaining horizontal space after that label. since the width of the
text label might change a bit, make sure there's an appropriate css
transition/animation on the bar so it doesn't jump around."*

- When the deploy-staleness update UI shows its countdown / "updating"
  message, that message (the countdown bar) moves OUT of its current
  position and INTO the posture widget's remaining horizontal space
  (after the posture label/chips).
- The bar's width changes as the label text changes (e.g. "arms in 3s"
  → "updating — waiting for the new page"), so the bar needs a **CSS
  transition on its width/flex** so it does not jump — a smooth reflow,
  not a snap. transitions.md governs this.
- The recuse is only while the update message is live; when it clears,
  the posture widget returns to its normal shape.

## Contracts to read first (not optional)

- `transitions.md` — sticky is not motion, but the recuse (an element
  moving from one place to another) and the width transition ARE.
  The review-pages fade idiom if act 1's HR+fade is attempted.
- `watch-design.md` — the posture widget's existing shape, tokens,
  the `.gservact` deploy-remedy styling (#462).

## Verification (the repo's discipline, all of it)

- **Born-red** for each act separately (two failing tests, two
  implementations, two greens — or one test covering both if the
  fixture naturally shares). Through the REAL render path.
- **Red-proof** per act: name the production line, `cp`-backup,
  sabotage, watch the discriminating tests fail (a GREEN red-run is a
  finding), `cp`-restore, `cmp` byte-identical. ALL inside YOUR
  worktree; verify `pwd`.
- Solo guard on port 39895 if the sticky/recuse/width-transition
  behaviour needs a browser assertion the pytest render tests cannot
  hold. Otherwise say why none.
- Never touch port 35110, never `pkill -f`, never `attn`, never the
  full coordinator suite. NEVER read_file an image.

## Handoff (#398)

`## Pending` line appended to the literal path
`.dreamwork/handoffs.md`: task id `#565/#569`, bare shas, no
parentheticals, no model claims. Marker grep empty before finishing.
Commits `git commit --only <paths>`. Report: commits, born-red +
red-proof evidence per act, the sticky mechanism, the recuse mechanism,
the width-transition approach, guard yes/no, FLAGs, found-not-fixed.
