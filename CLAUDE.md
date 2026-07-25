# ud-dreamwork — working on this repo

This is the dreamwork skill itself: the loop's own source, its dashboard
(`watch.py`), its hub (`dreamhub.py`), and its tools. Working *on* this
repo is different from *running* dreamwork on a project — when the loop
runs elsewhere, that target's own CLAUDE.md applies, not this one.

## Transitions — the one rule with no exceptions

**Every transition on the UI obeys [`transitions.md`](transitions.md).**
Appearing, disappearing, expanding, collapsing, state changes, movement —
all of them. There is no size below which this stops applying.

The rule it exists to enforce, in the human's words: *transitions must be
atmospherically suitable, like the transitions between pages.* Nothing on
this page appears or vanishes; it arrives and departs. The route change is
the reference implementation and every smaller change is a smaller
instance of the same gesture.

"It is only a small toggle" is how a page ends up with one gesture that
snaps among a hundred that drift — and the snap is the one the eye
catches. If you are making something visible, invisible, bigger, smaller,
different, or elsewhere: read that file first, and reuse the idiom that
already exists rather than authoring a second one.

Checking it is not optional and is not obvious: an end-state assertion
cannot fail on a motion bug, and neither can "did it move". `transitions.md`
opens with how to check, and the reasoning behind it cost three batches to
learn.

## The rest of the design

`watch-design.md` is the styleguide — tokens, type, components, copy
voice, and the per-surface contracts. It is authoritative and it stays
single-source: document a change in the same commit that makes it.
`just audit-styleguide` measures whether that happened.

`dreamhub-design.md` is the same for the hub, whose tokens are watch's
value for value, because the human moves between the two constantly.

## Verification

`just test` — pytest, `lint.py`, and the browser guards. There is no CI;
this is it. Guards bind ports 39890-39899 (watch) and 39880-39889 (hub);
check who owns them before running, because two servers in one range is a
mistake this repo has already paid for.

**A new check is not verification until it has been red.** Reintroduce the
bug, watch it fail, then fix it. Checks here have a documented habit of
passing over the thing they were written for — `.dreamwork/lessons.md`
keeps the running list of how.

## Conventions

- Commit each increment; stage by explicit path (more than one agent
  commits in this tree).
- A commit that changes what an existing install must do says so in a git
  trailer: `Migration:`, `Feature:`, `Needs: config|consent`.
- Files the loop writes and a tool parses have their shape stated in
  `file-formats.md` and checked by `lint.py`, in the same commit.
