# question surface — what a watching human changes

Briefed with four tasks (#105, #102, #103, #104+#77). Landed seven commits
covering eleven, because the human was *using the page while I built it* and
five P1s arrived mid-batch. That is the headline finding, and it is not
about any of the tasks.

## Reports are symptoms, and a symptom does not know which layer is broken

Three times today a report named the wrong layer, and each time the naming
was confident and reasonable.

- **#106** came to me as "a truncated follow-up preview — cut off
  mid-phrase, no ellipsis, no expand". That is a precise description of a
  *design* decision that nobody had made. There was no preview. The parser
  kept only the first line of a hard-wrapped sub-bullet, so the note was
  truncated **and** its tail leaked into the body as orphaned prose — one
  cause, two symptoms, and the second one had been read as a separate
  rendering bug. Had I built the ellipsis-and-expand affordance I was asked
  for, I would have shipped a careful UI for displaying corrupted data.
- **#107** came as "the width toggle happens outside the dissolve", with two
  suggested fixes. Both were reasonable and neither was the cause: the
  departing *ghost* was re-wrapping. It is a clone of `#view` inside `.wrap`,
  so when the column resized it re-laid-out at frame 0 while still fully
  opaque. The eye tracks the thing that is still visible.
- **#116** came as a regression against work I had just landed, complete with
  a mechanism ("the joiner is treating the next entry as a continuation").
  Half of it was real. The other half — an entry vanishing — was a line
  deleted from `questions.md` by an earlier edit. I reproduced the
  pre-damage input, got all three entries back, and reported that instead of
  fixing a joiner that was not broken.

The pattern is not "coordinators are careless" — the diagnoses were good
guesses from the evidence available. It is that **a UI symptom carries no
information about which layer produced it**, and the cheapest way to find
out is to reproduce the input rather than reason about the render. Each of
these took under five minutes to falsify. Two of the three would have been
hours of building the wrong thing.

## The bug nobody could have reported

While unifying the parsers for #116 I found that `append_subbullet` compared
the requested title against the **first source line** of an entry. So for a
hard-wrapped title — which is normal input, since the loop writes at 72
columns — no entry could ever match, and `/answer` and `/comment` failed
silently on a question sitting plainly on screen.

Nothing surfaces that. There is no red light, no error toast, no log line
the human reads; the note simply does not appear, and the obvious
interpretation is that you forgot to press the button. It is the most
serious thing found today and it arrived as a side effect of fixing a
cosmetic complaint.

The generalisable rule: **when the reader learns a new way to name
something, go and check the writer still finds it by that name.** The two
had drifted the moment titles gained a second valid shape, and unifying the
two parsers into `_parse_entries` did not fix it — the writer was a third
implementation of the same walk, and it took deliberately looking for it.

## Measurements that lie, and what fixed them

Almost every verification I wrote failed first for a reason that was not the
code:

- `getClientRects()` on a Range returns one rect per inline **box**, not per
  line. A paragraph containing a `<code>` fragments into three rects, so my
  first raggedness metric reported 70 bad lines in a correctly reflowed
  page. Group by top edge first.
- `getBoundingClientRect()` includes transforms. The dissolve deliberately
  lifts the ghost with `scale(1.07)`, so the ghost's "width" grew every
  frame and my "did it re-wrap" check failed on working code. `offsetWidth`
  is the only measure that answers that question.
- Counting `.qa textarea` across the page measures the **page**. Three of
  `oneinput`'s first failures were it counting across every card instead of
  one, i.e. measuring the fixture rather than the component.
- An absolute threshold on a layout ratio is not portable across content.
  What discriminates is an **A/B**: the same words, the same column, both
  renderers, swept across widths — and it turns out the win peaks in the
  middle of the sweep, not at either end, which no single-width measurement
  would have shown.

The through-line: I spent more time debugging my instruments than the
feature. That is the right ratio when the instrument is what you will
believe later, but it is worth knowing in advance that it *is* the ratio.

## The clamp that could not hold

#108 wanted the `+` opener never clipped. I wrote the obvious thing — measure
`.wrap`'s left in rAF, write a CSS variable — and my own per-frame trace
caught it painting one frame behind the column glide from #107. Measure-then-
write in rAF is always one frame late against a CSS transition.

The fix was to stop measuring: `(100vw - 100%) / 2` **is** the gutter, because
`100%` resolves against the containing block, which is the column. I had
rejected CSS earlier for a real reason (the column is `ch`-sized and `ch`
resolves against each element's own font) and then failed to notice that the
percentage sidesteps needing the column's width at all. Impossible-by-
construction beat re-validating every frame, which is this repo's own lesson
arriving from a new direction.

## Two identities, deliberately

`qaCard` ended up carrying both `data-qkey` (positional, addresses the entry
in live data, used for writes) and `data-qid` (the question itself, used for
animation). That looked like duplication until #77: answering a question
re-indexes it out of `questions_open` into `answered_entries`, so its
**key changes while the question does not**. An animation keyed by the write
address would have seen a departure and an arrival where a human sees one
card moving.

Related, and the reason #77's first implementation traced as a plain slide:
I detected "changed section" from the card's state class, but the submit
morph already changes that class locally at submit time. By regroup time it
reports no change even as the card is about to cross the page. The honest
signal was the heading it sits under.

## Out of scope, and worth someone's time

- **The list is re-rendered through `innerHTML`.** The regroup FLIP works
  because it animates a *new* node from the old node's rect, which looks
  identical — but the nodes are genuinely replaced, so anything the human
  has typed into a card is lost if a tick lands while they are typing.
  `holdRerenderUntil` covers the answer path only. A keyed reconciler for the
  question list would fix it properly; I did not attempt it inside a bounded
  batch, and it deserves to be a task rather than a footnote.
- **`.qa` cards clone on every tick** so departures have something to
  animate. Cheap now (a handful of cards, only on mtime change), but it is a
  clone-everything-to-handle-the-rare-case shape and would want revisiting
  if the list ever got long.
- The dashboard and `/questions` both regroup; only `/questions` was traced.

## Small thing that kept paying

Iterating against a **copy** of the target rather than the live
`.dreamwork/` was a defensive habit at 08:55 and turned into the answer to
#117 four hours later: the guards needed exactly that, and for the same
reason — content you do not control is not a fixture. The habit generalised
into `dev/capture/fixture/`, which then let the three most valuable guards be
gated for the first time. Turning them on found two stale assertions of mine
within one run.
