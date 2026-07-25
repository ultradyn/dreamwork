# question states — one axis, and what it cost to mean it

Briefed with three tasks (#118, then #111+#113 as one design). Landed six
commits covering seven, because three more arrived from the human mid-batch
while he watched the page change under him. The batch's own finding is not
in any of them.

## Source can be right while the screen is wrong

`.sgbtn` has said `background:none` since #103. It has never once rendered
that way. A `.qa button` element rule — left over from before `.qsend` and
`.sgbtn` had styling of their own — outspecified it, 0,1,1 over 0,1,0, and
painted an opaque fill and a border onto buttons that had asked for neither.

Four commits of pytest asserting on generated source passed on this, and
would have passed forever: the generated source contains `background:none`,
correctly, in the rule that loses. #117's lesson was that the Python half
cannot see what renders. This is the sharper form of it — **a component can
be correct in source and wrong on screen, and the source is the thing you go
and read when someone reports it.** I went and read it, saw `background:none`,
and would have concluded the report was mistaken had I not measured the
computed style first.

The general shape: a catch-all element rule inside a component's scope
(`.qa button`, `.qa textarea`) is a latent override of every component that
ever renders inside it. There is a live sibling — `.qa textarea` leaks
`margin:.3rem 0` into `.qfield textarea`, which is why the textarea sits
5.8px inside the field it is meant to share a border with while the send
button sits flush at 1px. I measured it and did not fix it: it is a visible
change to a surface he is using, and it deserves its own before/after look
rather than being smuggled into a commit about something else.

## Liveness and his input were never actually in tension

#118 read like a trade-off — the page re-renders every 2s, he types into it,
one of them has to give. It is not a trade-off. What the tick destroys is
exactly the set of things that exist **nowhere else**: the typed text, the
caret, the focus, which endpoint the text is destined for, and which folded
entry he had opened to read. None of it is on disk, so nothing downstream can
reconstruct it — and all of it is cheap to carry across the swap.

The predecessor called a keyed reconciler "the real fix". I do not think it
is. A reconciler at list level would still regenerate each card's inner HTML,
so the textarea dies anyway; you would have to reconcile down to the input
itself. Save-and-restore at the seam where the data lands is smaller, exact,
and composes with the FLIP that was already there.

The one part of it that is a correctness rule rather than a comfort is the
**mode**. It decides which endpoint the text is POSTed to. Reverting it to the
card's default on a re-render would silently redirect his words — the same
class of failure as #116's silent write, arriving through a different door.

## A ghost that kept the card's address

`snapshotCards` clones every card up front so departures have something to
animate. The clone is appended to `.wrap` still carrying `data-qid`. Once I
started ghosting *survivors* (a body leaving as a card folds), every
`.qa[data-qid]` walk on the page could find a corpse: `snapshotCards` would
capture its absolute rect as the question's, and `restoreCardState` would
restore his typing into it.

It was found because a per-frame trace measured the ghost instead of the card
animating underneath, and reported "the fold snaps shut" for a fold that was
working perfectly. I spent twenty minutes reasoning about transitions before
taking my own advice and printing the raw series. The fix is one line at the
door — strip the identity — rather than teaching six lookups to skip it.

**An element that has left the list must not keep the address of the element
that is still in it.** That is the same rule as "a CSS class is either a style
hook or an element address, never both", which was already in `lessons.md`
from #115. I did not recognise it until after.

## The instrument was wrong four times and the feature twice

Every measurement I wrote failed first for a reason that was not the code.

- **A sawtooth turns around too.** My "does it fade in *and out*" check
  counted direction reversals, and a one-way sweep that snaps back to its
  start reverses twice per cycle exactly as a breath does. A deliberately
  introduced sweep passed. What separates them is how *long* the fall takes:
  a breath spends as long fading out as fading in, a sawtooth spends one
  frame. The metric is the fraction of moving samples that are falling —
  0.43 for the breath, 0.00 for the sweep.
- **The CSSOM splits `background-position`** into `-x` and `-y` longhands, so
  a keyframe-property assertion written the way the stylesheet writes it
  fails on working code.
- **`\(` inside a template literal** is eaten before the page sees the regex,
  so a `/scale\(/` check became `/scale(/` and threw. It threw in `just test`
  and not in my single-guard run, because I had added the field after that
  run — which is the argument for running the whole suite before committing,
  not the changed part.
- **An element-box area is not the ink area.** My "the wisp is cheap" check
  measured a full-width block and failed; making `.anstag` inline-block both
  fixed the measurement and improved the effect, because the wisp now drifts
  across the words instead of across empty column.

And the two real ones, both surfaced by guards rather than by him: the 15×
scale squash my own #111 introduced, and the ghost identity above.

## Asserting the mechanism forbids the better mechanism

My first version of the matrix guard demanded an inline transform on every
card that ended somewhere else. It failed, and the failure was right: a card
sitting below one that is folding is carried by the layout as that height
animates — continuously, welded to the card it is following, with no
transform of its own. That is *better* than FLIPping it, and my check would
have banned it.

The rewrite asserts what he sees: everything that ended somewhere else
visited many intermediate positions. It survives a change of implementation,
which is the point of a guard that will outlive the code it was written
against.

The same insight has a consequence in the code, and it is the one thing here
a successor is most likely to get wrong: **a resizing card's height animation
already moves everything below it, so the FLIP must only handle the
residual.** Restoring a card's old height before the next card is measured is
what makes the next card's `now` mean "where it would be if only that resize
had happened". Cards are processed in DOM order and that is load-bearing.
FLIP the full difference instead and a neighbour moves twice — once by
transform, once by layout — and snaps back at the end.

## What the matrix settled about fold motion

Recording this explicitly because #128 and #129 both consume it, and a
successor re-deriving it from the code will get a plausible answer rather
than the chosen one:

- **The box travels; the body dissolves.** They are two different motions for
  one moment. The height travels on the card (`travelCard`, `.85s`, clipped
  while it does). The body that is *leaving* is ghosted from the up-front
  clone at the rect it occupied, **clipped to below the line the survivor
  still fills**, and dreams away on the page's one departure idiom. The body
  *arriving* eases in (`.qreveal` + `.dreamin`). Fading the whole card would
  have been wrong: the title line does not leave, it becomes the summary.
- **His own toggle is not a special case.** It goes through the same
  `snapshotCards` → `regroupCards`, which is what gives it the neighbours'
  motion for nothing. The native `<details>` toggle is prevented because it
  flips before any event you could measure from, and a FLIP with nothing to
  measure is a jump.
- **`expand` is structure; whether it moves is a separate question.** Plain
  `<details>` (dreams, archive, file peeks) stay instant. Only the folded
  question card animates, because only it lives in a list whose other members
  move. Do not promote this to the generic idiom.
- **`prefers-reduced-motion` gets the instant toggle**, no ghost, no reveal.

## On the reports

Five arrived mid-batch. Two named a layer, and both namings were wrong —
including one where I was as confident as the reporter. #121 was not the
buttons' styling, it was a rule from a different commit; #123 was not
"centred against the line box", it was that the opener is the tallest item
and therefore *defines* the line. Both took under five minutes to measure.
The predecessor's lesson held on its first day, twice, and the useful framing
is the coordinator's: the practice protects the work, not the accuracy of any
particular guess.

One report — #129, "the fold is not animated" — was **already fixed** by a
commit deployed six minutes earlier. Checking cost one trace against a copy
of his own data and saved a successor half an hour of building a thing that
exists. A report is evidence about a moment, and the moment may already have
passed.
