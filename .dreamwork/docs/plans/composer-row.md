# The composer row — one component, built once (#164 and its six dependants)

Seven queued tasks are really one build. This settles the shape so the
next dreamer picks it up instead of re-deriving it, and so the row does
not get written twice.

Tasks: **#161** menu shape and position · **#164** the conveyor ·
**#99** the popout · **#162** wrap + vanish · **#170** opens leftward ·
**#183** the sticky `+` · **#177** boxes that grow.

## The one decision everything else falls out of

**The button row is a COMPONENT, and both the inline composer and the
popout mount it.** Not "build the row, then restyle the popout".

That is the whole of #99. The popout is currently a museum of the
composer's previous state — it still carries the dropdown that #103
replaced, and it has missed #121, #161 and #164 since. `lessons.md`
already says a second mount is the cheapest audit of the first, and
nobody ran it. A shared component means it **cannot drift again**, which
is the difference between fixing #99 and retiring it.

His extra-width idea for the popout then costs nothing: more width means
more buttons visible before they tunnel. No special case, no second code
path — the same component in a wider box.

## The conveyor, restated so it can be built

His model, in his words on #164: new non-default commands enter at the
**left** by apparition, push the existing ones **right**, and are
consumed by the `...` menu at the right, which is both the overflow
affordance and the tunnel mouth. A button approaching it slides **under**
it and fades with proximity. Selecting a default again slides everything
back left; the non-default leaves by ghostly fade.

The reason is "information hints/scents", and it is a real one: the row
shows what he has been reaching for, in the order he reached, and where
the rest went. Things do not vanish — they go *there*.

What makes it buildable rather than a mood:

- **It is #104's regroup on a horizontal axis with a consumer at one
  end.** Reuse it. The FLIP, the departure idiom and the arrival snap
  (`.dreamin`, working only since #154) already exist.
- **Fade by PROXIMITY, not by time.** Opacity as a function of distance
  to the menu's left edge. This is the single detail that makes it read
  as a tunnel rather than a queue, and it is the one most likely to be
  quietly replaced by a transition.
- **Fixed row height and a clipping boundary at the menu**, or "under"
  never reads as under.
- **Reduced motion**: no conveyor. Buttons appear and disappear in place.

## Order, and why it is not negotiable

1. **#161 first** — the menu's shape and position. #164 consumes the
   menu's left edge as its tunnel mouth, so its geometry must be settled
   or the conveyor is built against a moving target. Two things land
   here: centre the dots (**measure first** — #123 was the same shape and
   took two wrong diagnoses), and hard right in the row with a gap.
2. **#164** — the conveyor, **as a component**.
3. **#99** — the popout mounts that component. Should be nearly free by
   this point; if it is not, step 2 built a layout rather than a
   component.
4. **#162** — only half remains. **(a) the wrapping is subsumed**: a
   fixed-height clipped row cannot wrap, by construction. **(b) is a
   separate bug and does not belong to this batch**: the composer
   defocused and vanished on a mode switch. That is the #131 family, and
   #131's "nothing auto-dismisses while it holds focus or unsent text"
   evidently does not cover the mode-switch path. Check whether a draft
   survives it — and note this is the same shape as #179, where a guard
   was green because it never visited the path.

Then the **geometry batch** (#170, #183, #177), which shares one hazard:

- The `+` is #170's anchor, and #183 makes the `+` move. **A fit test
  computed once at open is wrong the moment the anchor scrolls.** #183
  also collides with #108's clamp, so vertical and horizontal
  constraints must be solved together rather than in sequence — his
  observation, not mine.
- `position:fixed` is **not** viewport-relative under a transformed or
  filtered ancestor. Measure the rect, as #160 does.
- #177 makes the box's height state, so #118's tick-survival applies to
  it — and #179 says that state must survive re-render *and* that
  restoring it into a closed `<details>` silently does nothing.

## One piece of vocabulary this batch owes watch-design.md

From #161: **outline means "this acts", fill means "this reveals".** A
menu reveals where a button acts. That is a vocabulary rule for every
control on the page, not styling for one control, so it belongs in the
styleguide rather than in the diff. The fill is a surface colour, never
the accent — the accent marks the live and actionable thing and spending
it on a menu costs the page its loudest signal.

## Where this will go wrong

- **Building #164 as a layout.** The tell is #99 still costing 25
  minutes afterwards. If the popout is not nearly free, stop and extract.
- **Time-based fade.** It will look fine and be wrong; the tunnel is the
  point.
- **Doing #162(b) inside the conveyor work.** It is a focus/dismiss bug
  that happens to share a trigger. Separate it or it will be "fixed" by
  a rewrite that hides it.
- **Guards that never drive the path.** Twice today a guard was green
  because it visited the wrong page or answered by POST instead of the
  gesture. Every check here drives the real interaction.

## Taste is the deliverable

As with #122. Iterate on captures, and measure the animation cost the
way the wisp was measured — this row moves on every command change and
#177's growth fires on every newline, which makes them the two most
frequent animations on the page.
