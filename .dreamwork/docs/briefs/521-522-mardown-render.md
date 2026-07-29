# Brief — #521 + #522: markdown rendered view — blockquotes and [text](path) links

**Lane-owns:** `watch.py` (the markdown renderer ONLY: `mdBlocks`, `mdRender`,
`linkify`, `mdInline`, `mdSpans` and their CSS), one new guard under
`dev/capture/` + its registration, `watch-design.md` (the markdown contract,
same commit), `test_watch.py` if you add parser-level tests.
`.dreamwork/handoffs.md` (one Pending line). **Never** `_handle_decide`
(lane-515decide) or `track_question_updates` ~12917 (lane-509sig).

**His report (07:41, screenshot evidence — READ IT):**
`/home/xertrov/.grok/sessions/%2Fhome%2Fxertrov%2F.llm-general%2Fskills%2Fud-dreamwork/019fab09-c6a5-78b0-94ae-25ee4dedca04/assets/image-854b6b8a-e2ee-44c9-984c-4a849e9a869f.png`
(read_file renders images). Two bugs in the dashboard's rendered markdown view
(`/file?p=…` on an .md, and every other surface that reflows prose through
`mdB`):

- **#521 — quote blocks are not rendered.** `mdRender` (watch.py:~2501) knows
  fence/h/li/p; `>` lines fall through to plain paragraphs, so a blockquote
  shows as raw `>` text, one per line. His corpus writes quotes constantly
  (his words pasted into design docs — e.g. `.dreamwork/docs/plans/render-architecture.md`).
- **#522 — `[text](path)` links half-render.** `linkify` (watch.py:~2409)
  promotes a backticked path but has no general markdown-link pass (only
  `linkifyReview` handles review artifacts, in review contexts only). So
  ``[`text`](path)`` renders the text linkified+pip'd but leaves the literal
  `](path)` bleeding into the prose.

**BEFORE designing anything: read `transitions.md` and `watch-design.md`'s
markdown/rendered-prose contract (search for `mdB`, `mdcode`, `mdli`, the #158
reflow ruling). The rendered view's idioms are binding: emphasis is luminance,
chrome is quiet, nothing pops.**

**Design constraints (decided here, not open):**
- Blockquote: consecutive `> ` lines (and `>` continuation lines) form ONE
  quote block; render as a styled block (left rule + the text ramp a step
  dimmer/quieter — follow watch-design.md; do NOT invent a coloured callout).
  Quote content still reflows and still gets inline markdown (`mdInline`).
  A `> ` line inside a fence stays code (fences win — assert this).
- Markdown link `[text](target)`:
  - target is a KNOWN-INTERNAL path (`data.linkable_paths`, the closed set) →
    same treatment as a backticked known path: link + pip, riding the same
    `.mdfile` idiom; the whole `[text](target)` is CONSUMED — no literal tail.
  - target is `http(s)://…` → a plain external link (no pip — a pip floats a
    local view; the #506 rule).
  - anything else (unknown/relative path) → leave the literal text untouched
    (a broken link is a false promise — the existing rule), i.e. today's
    behaviour minus the half-render: either fully consumed or fully literal,
    never in between.
  - `linkifyReview`'s review-artifact pass keeps working exactly as today
    (it is the more specific pass; order your new pass so review docks win in
    review contexts).
- Relative targets like `../../docs/briefs/x.md`: resolve against the viewed
  file's directory ONLY if that resolution lands in the closed linkable set;
  otherwise literal. (The screenshot's `(../../docs/briefs/505-…md)` case is
  from a doc whose author wrote a repo-relative link with `../..` — resolving
  those is the difference between consumed and literal; pick the rule that
  makes his corpus's links work where they resolve to real files.)

**Acceptance (all required):**
1. Both fixes visible in the rendered view for the EXACT doc from his
   screenshot (`.dreamwork/docs/plans/render-architecture.md`): its quote
   block renders as a quote; its ``[`…`](…)`` links render consumed.
2. New guard `dev/capture/mdquote.mjs` (name yours): asserts (a) a fixture
   quote renders as the quote element (derive the fixture's quote line count
   at runtime — a one-line fixture quote asserted present is the
   precondition), (b) the literal `>` glyph count in the rendered quote is
   ZERO, (c) a `[text](known-path)` fixture renders with the target CONSUMED
   (no literal `](` in the text content), (d) an unknown-target markdown
   link stays fully literal, (e) fences still win over `>`. Register it in
   the guard registry; check port ownership before running guards
   (39890-39899; other lanes run guards too — run yours SOLO after checking).
3. Every assertion red-proved by injection into the production line it binds
   + cp restore (never `git checkout`); each red names the line injected.
4. `watch-design.md`'s markdown contract documents the quote block and the
   markdown-link rule IN THE SAME COMMIT (the styleguide stays single-source).
5. Transitions: if the quote block's styling introduces any state change
   (there should be none — static styling), `transitions.md` governs; a pure
   static style needs no transition. Do not animate anything.
6. Visual verdict: headless screenshots of the fixture page at desktop and
   390px mobile, quote block + links at rest; you MUST view the screenshots
   (read_file) and state the verdict in your report.
7. `git commit --only <paths>`; handoffs.md Pending line
   `· landed \`<sha>\` · … · by lane-521md —` naming commits, reds, guard.

**Never:** touch `mdBlocks`'s fence handling beyond adding the quote kind;
never touch the journal, posture, or delivery code; never `just deploy`;
never bind ports outside 39890-39899; never weaken an existing guard.

Model for the record: grok-4.5 (dispatch record — do not self-report a model).
