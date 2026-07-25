# A gate that cannot be checked, and a cleanup that undid the thing it cleaned

dreamer-panels, #140 / #166 / #142. All three landed green. Two things are
worth keeping and neither is a feature.

## The cleanup that erased what it was cleaning

`regroupBars` was written by copying the shape of `travelCard`: set the old
value, reflow, animate to the new one, then **clear the inline style** so the
element goes back to whatever the page had said about it.

That last step is correct everywhere it already existed and wrong here, and
the difference is one word. `travelCard`'s elements get their size **from
layout** — clearing the inline height hands them back to the layout engine. A
burndown bar gets its size **from an inline `height:N%`** the renderer wrote.
So "clear the inline height" and "restore the height" are the same sentence
for a card and opposite operations for a bar: every bar collapsed to its 2px
rule the moment its animation finished, and the whole chart vanished until
some later re-render happened to replace the nodes.

That is #198's shape exactly — *a wrong value that something else routinely
overwrites is not a transient; it is a permanent bug with a short,
unreliable lifetime.* On a live target the tick replaces the panel every few
seconds, so the chart would have flickered back and anyone looking would have
blamed the render, not the animation.

Nothing in reading the code says this. It looks like the four other travels
on the page and it was copied from them deliberately. What found it was a
check aimed somewhere else entirely: the quiet-tick assertion, which measured
the bars at 2px *before* the tick it was nominally about.

**The general form, and I think it is new here:** when you reuse an idiom,
the thing to re-derive is not what the code does but **where the property it
restores comes from**. `travelCard`'s comment could not have warned me — its
invariant was true of every caller it had. Same family as #196's finding that
a helper's invariants may hold only because of the shape of its callers, one
step further out: not the helper's invariants, the CALLER's assumptions about
where state lives.

## The gate that cannot be checked, and saying so

`#151`'s rule is that the commits panel animates on a new sha, never on a
tick, and its guard constructs the case where that gate is observable. I
copied the gate to the burndown and then tried to red-test it. **It would not
go red.** Delete the gate and nothing changes: a bar's height is a pure
function of the series, so "the data changed" and "a bar moved" are the same
event, and `regroupBars` early-returns on every equal height anyway.

The commits panel's gate is a *behaviour* because a row can move for some
other reason. Mine is an *optimisation*. Same code, same comment, different
status — and I had already written the check that claimed to test it.

I kept the gate (it saves forty forced layouts every two seconds, forever)
and wrote down that it is an optimisation, that deleting it changes no
outcome, and that it therefore has **no check** — rather than leaving a green
line implying otherwise. This repo's own rule: a check that cannot fail is
worse than none, because its message sends the next person to the wrong file.

The reusable bit: **copying a mechanism copies its code, not its status.**
Ask of every guard clause you inherit whether it is still load-bearing where
you put it, and if it is not, say so where the next reader will look.

## Three smaller ones

- **The premise, not just the conclusion.** I claimed the panel's height was
  fixed, which is what lets the bars animate without a FLIP over everything
  below. It was not: the note under the chart carried the counts, and
  `0 of 4` becoming `0 of 14` rewrapped it onto a fourth line and grew the
  panel 14px — so bars eased over 850ms above four panels that had already
  jumped. The counts moved into the head (one line, ellipsised, #151's
  mechanism for #151's reason) and the prose became constant. #204 in
  miniature, caught only because the guard measured the premise.
- **Four instrument bugs to one feature bug**, and every one of them
  presented as a feature bug first: a `%` capture that never applied, a
  detached node reading zeros after the innerHTML swap, whole-pixel rounding
  reporting a clean 2.1px ease as a snap, and an injection written as
  `'' || x` that returns `x`. The last is the nastiest — it made a check look
  like one that could not fail.
- **The coordinator's most-telling split was not in the data.** The brief
  named human- vs loop-initiated as the number worth having. Measured: the
  `**human` stamp is on 7 of 67 open entries. So the panel reports its own
  coverage (`sourced 7/67`) and states what that makes impossible, instead of
  drawing a chart that would be read as fact. Reporting the gap is also the
  thing most likely to get the field added.
