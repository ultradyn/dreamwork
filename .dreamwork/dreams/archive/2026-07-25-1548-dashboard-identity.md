# dreamer-identity — the tab answers "which loop, and does it need me?"

#153 (title + favicon) and #143 (per-project tint), plus one runner fix that
was not in the batch and paid for itself immediately.

Commits: `266db84` title · `7be4a22` guard-runner ownership · `0cefd06`
favicon · `6c49874` tint · `10ca98a` the app name's return.
Gate for each: pytest + lint + 17/17 guards.

## What I would tell the next dreamer

**The 16px finding, which is the only thing here that generalises.** At
favicon size a change of POSITION is legible where a change of LUMINANCE is
not. I found it by rendering both at 16px on real tab-strip greys, not by
reasoning — the breathing bloom I designed first looked lovely at ×7 and was
an indistinguishable smudge at true size, ten frames apart. That is #113's
wisp conclusion arrived at from the opposite side: a wisp has a whole card to
breathe in, so luminance works there and only there. **An idiom that works at
one scale is not a design at another, and rendering it at its real size is
the cheap way to find out.** The same look killed the near-black tile: right
on his dark browser theme, a black block on a light one.

**Design for the frame rate the environment will actually give you.** A
hidden document gets no rendering opportunities, so rAF does not run in a
background tab — which is exactly where a favicon lives. Quantising the orbit
to one frame per second made it correct at 60fps *and* under the background
clamp. It was also wrong in the way that matters: he watched it in the
FOREGROUND and called it "too slow and not smooth" (#182). Both halves of
that are true at once. The fix is two regimes on `visibilitychange`, not a
speed-up, and the reasoning that produced the slow version is what makes the
hidden half of the pair right.

**I could not measure the thing my design turned on.** Two attempts to put a
page into the hidden state under Playwright failed — a second `newPage()` is
a separate window, and `window.open` from the page opened one too, so
`visibilityState` stayed `visible` both times (and Playwright's default args
disable all three throttles, so they have to be removed first). Saying
"unmeasured" and choosing a design that does not depend on the number was
better than either guessing or spending the batch on the harness. **If the
next person needs a genuinely hidden tab, that is an unsolved problem here.**

## The instrument was wrong seven times, and I was the one holding it

Every single one looked like a feature bug first.

- **Two vacuous checks**, both found by the first injection rather than by
  reading: the fixture had two open questions against two awaiting items, so
  a title reading the wrong source was byte-identical to a correct one; and
  `\(!\)\s*\d` anchored on a `)` that the alternative shape `(!1)` does not
  have, so it blessed exactly what it existed to reject.
- **Three false alarms on one measurement**, feature correct throughout: it
  sampled a region overlapping the 72ch text column (7° for a 79° rotation),
  then after a fixed sleep shorter than the 2s poll it was waiting for (0°),
  then while the page was still on `/review` with an iframe over the sample
  region (6°). Wait for the STATE, sample where the field actually is, and
  know which route the page is on.
- **Two crashes instead of reports**: the icon reader rejected on an icon
  that never loads, and the tint reader threw on a file that was never
  written — in both cases the injection that check existed for turned into a
  stack trace, and the run said "the guard threw" while naming nothing. The
  general form, now a lesson: **a guard assertion whose subject may not exist
  has to degrade to a reading, never throw.**

## Two documented behaviours that had never once run

`statusBlock` gated its `last_tick` render on `if (t)`, which is falsy for
NaN — so the verbatim fallback watch-design.md documents had never executed
and an unparseable tick vanished off the page instead. That is #154's exact
shape, the second instance in one day from a different part of the same file.
**A document is what stops anyone checking.** Both were found by someone
working next door, which is the only way they get found.

## The failure with no guard at all, now closed

A pair of backticks inside a **GLSL comment** ended the JS template literal
the shader lives in, and the rest of the shader parsed as JavaScript. Blank
page. Nothing in the fast half of `just test` saw it — pytest's substring
assertions all still matched perfectly, because the source *contains* the
strings; it just will not parse. Only the browser guards caught it, twenty
minutes later, as thirty unrelated red lines. `node --check` over the
assembled script now catches that class in 0.2s. **The gap was structural:
the fast half asserted on a string, and a string is not a program.**

## The runner gap, which is worth more than the feature that found it

`just guards <port>`'s readiness probe accepted any answer on the port. I had
left a `just watch` on 39890; the runner's own server lost the port, my stray
one answered, and ten guards asserted fixture facts against the live repo —
coming back red with messages about a fixture that was never being read. Only
the three guards that start their own servers were immune, so the check
belonged in the runner rather than in each of the other ten. The coordinator
had recorded this exact class that morning from dreamhub and fixed it at the
symptom; the mechanism survived and cost the next agent twenty minutes.
**Fixing the instance is what leaves the class alive.**

## Judgement calls a reader should know about

- **Not an events-log line for the tint**, and the coordinator approved the
  reasoning as much as the departure: that log's contract is one line per
  thing an agent then ACTS on, and a colour is not one. It is now written in
  `watch-design.md` beside the write exception, because the next person
  adding a fifth write will reach for the log by default.
- **Excluding the amber band from `TINTS`.** A project tinted amber would
  paint its whole ambient field the colour that means BROKEN — the page has
  one warning colour and it earns its meaning by scarcity. Accent discipline
  applied to a surface nobody had thought of as competing with it.
- **Hue-only via a Rodrigues rotation about the grey axis**, so the
  achromatic component is the rotation's own eigenvector and contrast
  survives *by construction* rather than by a claim about the six values.
  This page keeps choosing impossible-by-construction over checked, and
  should.
- **The compound `dreamwork/<project>`.** His ruling put `dreamwork` in the
  slot the project name occupied, while he was reading the ud-dreamwork
  dashboard, so it reads two ways. I shipped the shape that is right under
  both rather than picking one silently, and said so. Unconfirmed; a one-line
  trim either way.

## Handed over, not done by me

`file-formats.md`'s `watch-tint` row and `lint.py`'s `check_watch_tint` are
written out in full at
`/tmp/claude-1000/-home-xertrov-src-grok-hark/d417eeb6-60f6-4a0a-b4e6-b03264c3c593/scratchpad/handover-143.md`
and acknowledged by the coordinator. **Until they land, `.dreamwork/watch-tint`
is a loop-written, tool-parsed file with no stated contract and no check** —
which is the thing that rule exists to prevent.

## Nothing else is held outside a commit

The prototypes (`fav1`-`fav4.html`), the throttle probes, the p95 harness and
the injection script are scratch and deliberately not kept; what they proved
is in `watch-design.md`. Everything I know is in the commits, that file, and
this dream.
