# composer batch (#91) — what the second window taught me

Five human-requested tweaks to the composer. Four landed as separate
commits; all five items are done. The tweaks themselves were small. What
was not small: **three of the five items uncovered a latent bug that had
been shipping for hours**, and all three had the same shape.

## The pattern: a second instance is the test

Every bug I found was a single-instance assumption that only became
observable once a second instance existed.

- **Item 1** (move the panel down) exposed that `place()` wrote viewport
  coordinates into a `position:fixed` panel whose containing block is
  `.wrap` — because `.wrap` carries `perspective` for the dream dissolve.
  The composer had been sitting 280px right of and 34px below its own
  opener. Nobody noticed because with only one panel there was nothing to
  compare it against; it just looked like a floating panel. The moment the
  requirement became "a specific gap under the opener", the offset became
  measurable, and wrong.
- **Item 2** (popouts get the shader) exposed that #74's "world-space"
  field was only half world-space. The domain *origin* was pinned to the
  screen, but the *scale* was `2.3 / innerHeight` — per-window. One window
  can't tell; two windows of different heights show the same dream at two
  magnifications and the seam can never line up. Fixing it also made
  resizing behave like dragging already did (reveal more of the field
  rather than rescale it), which was an incoherence nobody had named.
- **Item 2 again** exposed a sign error: the vertical anchor added a
  top-down `screenY` to a bottom-up `gl_FragCoord.y`. At `screenY = 0` —
  the only position a single maximised window ever has, and the only one
  headless can produce — the error is exactly zero. It only exists off the
  origin.

The generalisation I'd want a successor to carry: **when a feature
duplicates an existing surface, budget for finding bugs in the surface,
not just for the duplication.** Mounting a second copy of something is the
cheapest audit you can run on the first copy. It falsifies coordinate
assumptions, normalisation choices, and sign conventions that are
unfalsifiable while N=1.

## On proving visual claims

I nearly shipped a green test that proved nothing. `worldspace.mjs`
compares a background plate from an 820px window against a 500px one and
reported `maxDiff: 0`. That is exactly what a *broken* test also reports
if, say, both plates are flat black or both captures silently failed. So I
temporarily restored the old per-window scale and re-ran: `maxDiff 133,
mean 33.8`. Only then was the 0 worth anything.

Two techniques worth keeping:

- **Freeze the clock to compare a time-varying visual.** The field
  animates off `Date.now()`, so two screenshots are never the same frame.
  `context.addInitScript(() => { Date.now = () => T; })` makes captures
  comparable without trying to synchronise them. This is what let me
  compare across two *documents* (main vs popout), which no single-page
  technique reaches.
- **Assert the plate has detail**, not just that two images match. Both
  scripts check a min/max spread so "identical" can't be satisfied by
  "identically blank".

## Judgement calls a human might want to revisit

- I made the shader's domain scale a world constant (`2.3/900`). This is
  the principled fix and it makes the styleguide's existing world-space
  claim true, but it is a **visible change to the main page**: ambient
  pattern density no longer normalises to viewport height. I checked it at
  820px and 1300px and it reads as a whisper either way, but it is the one
  thing in this batch that alters a surface the human did not ask me to
  touch. Cheap to revert (one constant + one line) if they dislike it.
- I kept the tilt-shift focus band and edge defocus **per-window** rather
  than world-space, and wrote that up as a deliberate line: one shared
  world, each window its own lens. Consequence: blur can differ at a seam
  even though the field beneath it matches exactly. Making the lens
  world-space too is a real option, ~12 lines across four places; I judged
  it out of scope for a bounded batch rather than obviously wrong.
- The popped-out command form still uses a `<select>` instead of the new
  button group. It now fills its options from `COMMANDS`, so it cannot
  drift from what the server accepts, but the two surfaces don't look
  alike. Worth a follow-up now that popouts are prettier.

## Small thing that keeps paying

`COMMANDS` as one `{kind, label, desc, common}` tuple at the top of
`watch.py` collapsed three copies of the vocabulary (server validation,
composer, popout form) into one, and it is exactly the shape #86 needs —
plugin kinds append to a list and both the button row and the menu already
render arbitrary lengths. The hover menu was cheap *because* item 4 had
already forced the vocabulary into one place. Ordering mattered more than
either item did on its own.
