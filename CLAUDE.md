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

## Exceptional Web UI quality

**Every contribution to the Web UI must be of EXCEPTIONAL quality.** Merely
functional, conventional, or locally polished work does not meet the acceptance
bar. Treat composition, interaction, copy, accessibility, responsive behavior,
motion, reduced-motion parity, and evidence as one product-quality obligation.

Before designing, implementing, or reviewing Web UI work, load the relevant
design and visual skills rather than relying on generic frontend defaults. Use a
focused subagent when it would materially improve dedication, visual judgment,
or review depth; explicitly tell that agent to load the relevant design skills
and this repository's design/transition contracts. Delegation never replaces
coordinator inspection, red-first guards, or visual review of the actual pixels.

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

That rule is a one-time act, and it only catches a check born hollow. It
cannot catch one that *becomes* hollow, because the red run happened
commits ago and nobody re-runs it: a directory grew, a second fetcher
appeared, a fixture gained a third question and two numbers that had to
differ met. Three such were found in a single batch, two of them
invisible in the guard output entirely. So the companion rule, and it
costs one line each time: **assert in the check the precondition the
check depends on.** If its meaning needs two pieces of the fixture to
differ, derive both at runtime and assert the gap — a literal tuned to
today's fixture is a check with an expiry date nobody can see.

Both rules assume the red run itself is trustworthy, and twice in two
hours it was not: **the proof came back green while the bug was in
place.** Not born hollow, not become hollow — the injection never
reached the code, because the test's own scaffolding stood in front of
it. Once a fixture built the filtered list itself instead of calling the
function that decides it, so reverting that function changed nothing the
test could see. Once a fake returned `""` for precisely the input that
would have reached the branch under test, so deleting the branch changed
nothing either. Both read as thorough unit tests. Both were structurally
incapable of failing, and both were about the single decision they were
named for.

So: **a green red-run is a finding, never a relief.** When you reinstate
a bug and the check passes, the check is wrong — do not conclude the code
was fine anyway. And when a test patches, fakes or hand-builds anything,
name the production line that would have to change for it to fail, then
change that line and watch. If you cannot name one, there isn't one.

Before an injection, read the slice of `.dreamwork/lessons.md` that
governs it: `python3 dev/lessons_index.py --act red-proof`. The file is
3000 lines and nobody re-reads it before acting — the `git checkout` RED-undo
lesson sat in it for three days and did not prevent its own repeat (#349).
The slice is a page; the file is not.

## Conventions

- Commit each increment with **`git commit --only <paths> -m …`**. More
  than one agent commits in this tree, and `git add <path>` alone does
  **not** protect you: `git commit` commits the whole index, so anything
  a concurrent agent had staged lands in your commit under your message.
  That happened at `12f47e3`, which carries a lane's test file inside a
  ledger commit. Avoiding `git add -A` does not help — the sweep is
  invisible in your own command. `--only` is the fix and it is verified:
  it commits just those paths and leaves the rest of the index staged. One
  edge: `--only` does not pick up an untracked file — a directory pathspec
  silently drops one inside it, a bare pathspec errors — so a **new** file
  needs `git add -N <paths>` first (intent-to-add, not `git add`, so nothing
  is staged into the index `--only` protects) (#684).
- A commit that changes what an existing install must do says so in a git
  trailer: `Migration:`, `Feature:`, `Needs: config|consent`.
- Files the loop writes and a tool parses have their shape stated in
  `file-formats.md` and checked by `lint.py`, in the same commit.
