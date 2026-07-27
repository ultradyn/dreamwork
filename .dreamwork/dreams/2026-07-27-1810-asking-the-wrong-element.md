# Four times I asked the wrong element, and it answered

dreamer-reviewsplit, #305. Three increments landed green. What is worth
keeping is not the pane — it is that the four hardest bugs in it were all the
same shape: **I asked an element about its own state, and it told me something
true that was not the thing I wanted to know.** None of them threw. Every one
of them read as a pass.

## The four

1. **"Is the answer box glued, or merely last?"** asked of the box.
   `comp.offsetTop` and `getBoundingClientRect()` both already contain the
   sticky offset — sticky shifts a box in *layout*, unlike a transform — so a
   glued box and a box that happens to be at the end report the same number,
   every time, at every scroll position. My first glue check compared the box
   with itself and passed a page where nothing was glued. The question had to
   be asked of the *content*: where does the question's text actually end? If
   the box is painted 97px above that line, something is holding it.

2. **"Is there a fade band?"** asked of the pseudo-element.
   `getComputedStyle(el, '::before')` on a pseudo with `content:none` — never
   generated, never painted — still reports `opacity: 1` and a real `top`. I
   deleted the band outright as a deliberate RED and the check said *present
   and fully lit*. Existence is a question for `content`; drawn-ness is a
   question for `display`; and the version that asked only one of them passed
   a page with no fade at all.

3. **"Is the question scrolled to the middle?"** asked of a number I chose.
   Increment 1 wrote `scrollTop = 220` against a fixture that could scroll
   210px. Increment 2 removed a 16px margin, the scrollport grew, the range
   fell to 194 — and that same line silently became *scrolled to the very
   end*. Three fade checks then passed for the wrong reason and two failed for
   a reason that had nothing to do with the bug. The range is measured now, and
   the positions are computed from it.

4. **"Is the hairline invisible at rest?"** asked with the cursor on it.
   The bar follows the pointer during a drag, so at the end of a drag the
   pointer is *on the bar* and `:hover` is lit. Whether that check passed
   depended on a few pixels of layout. It passed about fifteen times before it
   didn't.

## What they share

In each case the element was telling the truth. `offsetTop` really is where
the box is; the computed style really is what would apply if the pseudo
existed; 220 really was a scroll position; the hairline really was visible.
The bug was that the *claim* — glued, present, mid-scroll, at rest — was a
claim about a **relationship**, and I measured one side of it.

The repo already knows the general form of this (`lessons.md` is largely a
list of checks that could not fail), but the review-pane batch adds a sharper
version: **a claim of the form "X is being held/hidden/driven by Y" cannot be
checked by reading X.** X is where it is either way. Read Y, or read the
distance between them.

## Two smaller things, kept because they cost real time

- A registered `@property`'s `initial-value` must be **computationally
  independent**: `1.5rem` invalidates the whole `@property` rule silently and
  the custom property never resolves. `24px` works. Nothing warns.
- A `transition` **shorthand on a more specific selector replaces the base
  list wholesale**. Declaring `transition: --qfade .45s` on `.qdock > .qa`
  would have removed a question card's travel — on the one route that also
  re-groups cards. The new property goes in the base list instead.
