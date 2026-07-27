# #367 — pointer flags to a review's essentials

Status: **ruled and building.** He answered M1–M4 on 2026-07-28 05:35 (see §"What was
decided", which wins over the superseded proposals left in place around it), and
**increment 1 landed at `dbcbcc5`** — the parser, the caps and the no-id refusal, with
no visible change and no artifact rebuilt. Increment 2 (the rail, the strip, the tab,
next/prev) is **gated on one owed measurement**, in flight as of 07:12: a two-line tab
at ~6 words is taller and possibly wider than every number below, all of which were
measured against a one-line tab. See §"Before increment 2 touches the template" for a
coupling that will otherwise be discovered by a red test.

Everything above §"What was decided" is the *original* design reasoning, written before
his ruling. It is kept because the measurements in it are still the load-bearing facts,
but where it and the ruling disagree — the cap, and the label length — **the ruling
wins**. In particular §"The design" still says "the cap is five, and it refuses the
build", which he overrode.

His words, typed from inside `/review?p=task-store-schema.html` at 02:36:

> on reviews, it would be really handy to have some pointer labels at the most
> important parts. like the absolute essentials. then i could have a next/prev
> button too. something like those little thin postits that lawyers use to
> indicate key points and where you need to sign. would make it a lot quicker
> to go through reviews I think. (Sometimes they are quite long)

## What the measurements decided, before any design

Everything below is measured on the live artifacts, because three plausible
designs die on these numbers and picking one first would have wasted the batch.

**"Quite long" is 19.6 screens.** `threaded-topic-chats-v2.html` is 6,533 words
and 19,582px tall at a 1000px viewport. Median across the 16 artifacts is 1,777
words. The complaint is well-founded and the longest few are where flags pay.

**A table of contents is already refuted by his own analogy, and the numbers
agree.** That artifact has **22 `<section>`s and 23 `.label`s**. A nav over
structure would be 22 entries; a lawyer's flag set is five. The existing
`.topactions` nav is that structural axis already (`findings` / `shape` /
`decision`), so marks are a *different axis* — "read this if you read nothing
else" — and merging them produces the second table of contents he did not ask
for.

**The outside gutter cannot hold a flag.** `.wrap` is
`width:min(calc(100% - 2rem),1120px)`, so the margin outside it is **16px at
every viewport from 1120px down** — 1120, 960, 860, 480, 390 all give 16px. The
physical "protrudes past the edge of the page" reading of his metaphor is
affordable only above ~1250px, and is *nothing* on a laptop at 1120. Any design
built on the outside gutter is a design that works on one monitor.

**But the reading column leaves half the wrap unused, and that is where flags
live.** `.read` is `max-width:78ch`, which resolves to a **fixed 613.5px** (78ch
at 13.12px, and that font does not scale with viewport), and it is
**left-aligned** in the wrap. Measured at 1280px: wrap 1120, `.read` 614, slack
to its right **506px**. So:

| viewport | wrap | slack right of `.read` | room for a 96px flag |
|---|---|---|---|
| 1440 | 1120 | 506 | yes |
| 1120 | 1088 | 474 | yes |
| 960 | 928 | 314 | yes |
| 860 | 828 | 214 | yes |
| 780 | 748 | 134 | yes |
| 700 | 668 | 54 | **no** |
| 480 | 448 | −166 | **no** |

**The cliff is at ~780px, not at mobile.** This is the single most useful thing
the measurement produced: `#367`'s entry anticipated that "on mobile a
protruding edge tab competes with the column for width", and the real boundary
arrives far earlier — between 700 and 780px, above the existing 860px and 480px
breakpoints. A design that answers only for 390px would break silently on a
narrow window on his own desktop.

## The design

**A mark is a flag at a vertical position, not a decoration on a box.** Blocks
inside a section are not all the same width — `.read` paragraphs are 614px while
tables, `.facts` and `.spine` span the full 1120px wrap — so a mark attached to
its block's right edge would sit in a different place for every kind of
passage. It attaches instead to the **right edge of the reading column**, at the
height of the passage it marks. That is what a lawyer's flag does: it protrudes
at the edge of the page, at the height of the clause, regardless of what is
printed on that line.

**Two presentations, one behaviour, and the switch is at the cliff.**

- **≥780px — the flag rail.** A fixed-width column in the wrap's right slack,
  beside the reading column. Each mark is a thin tab at its passage's height
  carrying its short label. This is the metaphor, at full strength, on every
  desktop and laptop and landscape tablet.
- **<780px — the essentials strip.** The same marks as a single compact row
  under the top rail, with the same next/prev. Not a shrunken rail: the rail's
  whole affordance is *lateral space at a height*, and below the cliff there is
  none, so the same information takes the only form that fits. His "next/prev
  button" is already this, which is why the fallback is not a consolation.

Next/prev walks the marks in document order in **both** presentations, so the
behaviour is width-independent and only the presentation changes. That is what
makes the switch a presentation detail rather than two features.

**The cap is five, and it refuses the build.** His point is that five flags help
and fifty are wallpaper, and a cap that only warns is a cap that gets ignored —
`review_artifact.component_violations` already refuses a build for a lesser
offence. Five marks against 22 sections is the ratio that keeps the meaning.

**Marks come from the source, and that is half the value.** The authoring
dreamer must name which three-to-five passages are the essentials, so an
artifact that cannot say what its own essentials are is an artifact that has not
decided what it is asking. The forcing function is worth as much as the reader's
saved time.

## Motion, which `transitions.md` governs

Next/prev is movement between marks, so it is not exempt.

- **A long-range smooth scroll is already refuted** — the #229 v2 review found a
  1.5s one and it failed the gate. The requirement is a settled landing, not a
  journey.
- The template declares **no `scroll-behavior` at all** (measured: zero
  occurrences), so the behaviour is chosen here rather than inherited, and
  choosing "instant with the arrival marked" is available.
- The arriving mark's change of state is itself a transition and takes the
  page's existing idiom, not a new one.
- Reduced motion: the jump is the function and survives; nothing about
  *finding* the passage may depend on animation.

## What was decided — his ruling, 2026-07-28 05:35

All four were put to him as M1–M4. **Two went with the recommendation and two
overrode it**, and the two he overrode are the two that were about *his* reading
experience rather than about the code — which is the pattern worth noticing.

1. **M1 · the rail-plus-strip split at 780px — `rec`, taken.** Build both
   presentations; the cliff measurement stands.
2. **M2 · the cap — OVERRIDDEN.** I proposed **five, refusing the build** above
   it. He set **soft 7, hard 15** — meaning seven is *allowed*: the warning
   starts at 8, the refusal at 15. (This line used to read "a warning at 7",
   which the #367 builder flagged as contradicting both `file-formats.md` and
   its own brief. A cap of 7 that warns *at* 7 is a cap of 6; the code is
   `MARKS_WARN_AT = 8`.) So the build
   never fails on the count a careful author might legitimately reach, and the
   forcing function moves from a refusal to a warning across a band. My "five and
   refuse" was the tidier rule and the wrong one — a refusal at the number where
   his judgement and mine differ makes the tool argue with him.
3. **M3 · the label's length and who truncates — OVERRIDDEN.** I proposed a
   **~12-character** label truncated by the builder. He set **two-line tabs at a
   smaller text size, up to ~6 words** — so the tab grows to fit the label rather
   than the label shrinking to fit the tab, and nobody truncates. **Measure the
   two-line tab's width and height against the 16px gutter before building it**:
   the whole design rests on `.read` being a fixed 613.5px with 506px of slack at
   1280px, and a two-line tab is taller and possibly wider than the one this was
   measured for. If ~6 words does not fit at some viewport, that is a measurement
   to report, not a cap to quietly reintroduce.
4. **M4 · marks are not a `nav` entry — `rec`, taken.** Different axis; no second
   table of contents.

**Superseded, kept deliberately:** the paragraphs above and in §"The design" that
argue for five-and-refuse and a 12-character label are my superseded proposals.
They are left in place rather than rewritten because the reasoning behind an
overridden recommendation is the record of what he wanted differently, and
deleting it would make the next author re-propose it. Where the two conflict,
**this section wins.**

## What this does not touch

The existing `.topactions` nav, the `.spine`, and any artifact without marks —
which is all sixteen today, so the frame change must render identically when a
source declares none. That is the first check to write, and it is the one that
makes the change safe to ship before any artifact adopts it.

## Cost

A frame change, so `template_stamp` restamps all 16 artifacts and they rebuild
once. `#347`'s batch has landed, so this is its own commit rather than something
to batch with — one restamp, accepted deliberately.

--- SUMMARY ---

- **His ask**: thin protruding flags marking a review's absolute essentials,
  with next/prev, because reviews are sometimes 20 screens long. Measured: they
  are — 19.6 screens and 6,533 words at the top, 1,777 median.
- **Three things the measurements killed before design started**: a table of
  contents (22 sections vs a lawyer's five flags, and the structural axis is
  already the `nav`); the outside gutter (16px at every viewport ≤1120, so the
  literal "past the page edge" reading only works above ~1250px); and a
  mobile-only fallback (the real cliff is ~780px, above both existing
  breakpoints).
- **The design**: a mark is a flag at a *height*, anchored to the reading
  column's right edge — because `.read` is a fixed 613.5px, left-aligned, with
  506px of unused wrap beside it at 1280px, and blocks in a section vary from
  614px to the full 1120px so a per-block anchor would scatter them.
- **Two presentations, one behaviour**: the flag rail in the slack at ≥780px,
  a compact essentials strip under the top rail below it, and next/prev walks
  marks in document order in both — so the switch is presentation, not a second
  feature.
- **Cap five, refusing the build**, on his "five help, fifty are wallpaper", and
  because a warning-only cap is ignored.
- **Marks come from the source**, which forces the authoring dreamer to name the
  essentials — an artifact that cannot is one that has not decided what it asks.
- **Motion**: long-range smooth scroll is already refuted (#229's 1.5s failed
  the gate); the template declares no `scroll-behavior`, so a settled landing is
  chosen here; reduced motion keeps the jump.
- **Four open decisions** for him: the 780px split, the cap and its severity,
  the label's length and who truncates, and whether marks also appear in `nav`
  (recommended no — the cost of being wrong is the second table of contents).
- **Safety first check**: with no marks declared, the frame must render byte-
  identically, which is what makes this shippable before any artifact adopts it.

## Before increment 2 touches the template — a coupling that is invisible until it reddens

**A CSS fix to a selector the template SHARES with `.dreamwork/review/tasks-page.html`
must be made in both files, or `just test` goes red.**

`test_template_rules_match_the_reference_rule_for_rule` holds every selector shared
between `review-artifact.template.html` and `tasks-page.html` to identical
declarations, and `DECLARATION_DIVERGENCES` — the one documented door for a deliberate
difference — is **empty**. `tasks-page.html` is the hand-rolled artifact the template
was cut from (the human's named "good one"); it is **untemplated and never rebuilt**,
so the coupling is manual and nothing announces it until the test fails.

The #347/#372/#364 frame batch hit this and paid for it: `white-space:nowrap` on
`.topactions a` and `min-width:max-content` on `table` each had to be applied twice.
Its brief's ownership list named the template and "the built `.dreamwork/review/*.html`"
but not `tasks-page.html`, because "built" is arguable for a file that is not.

**So increment 2, which adds tab CSS, needs `tasks-page.html` in its ownership list
from the start** — and if a new tab selector is genuinely *not* wanted on the
reference, the honest route is a `DECLARATION_DIVERGENCES` entry with a reason, not a
silent divergence. Two further notes for whoever writes that brief:

- The tab is **new** CSS, so it is only coupled if its selectors collide with existing
  shared ones. Check before assuming either way: a wholly new `.mark`-family selector
  may be uncoupled, in which case say so rather than editing the reference for nothing.
- The test's failure message does not currently name `tasks-page.html` as the other
  half. **Improving that message belongs to increment 2**, since it will be the second
  batch to learn the same thing the hard way, and `test_review_artifact.py` is the
  right place for it. (It is owned by #389 as of 07:12, so it is not editable today.)
