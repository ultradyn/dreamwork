# Artifact templates — proposals as fragments (#112, plan)

Human-proposed 2026-07-25 (~09:25), after reading the first two review
artifacts: design proposals should all be HTML like the goal-hierarchies
one, built from reusable templated components (flow charts, layouts —
"like cursor-agent cli does"), with the shader background as a default
part of the template. **The agent writes only the important bits; the
wrapper is applied automatically**, so presentation updates centrally
and nothing goes stale.

## Why this is right, in one line

Two artifacts exist and I hand-wrote the same 40 lines of shell, tokens,
scrollbar rules and decision-block markup in both. The third would have
been the third copy — and the first one where they quietly diverged.

## The shape

- An artifact is `<slug>.part.html`: a **fragment**, no `<html>`, no
  `<style>`, no shell. Just sections, using the component vocabulary.
- `watch.py` wraps it at serve time (`/reviewraw`) with the shell every
  page already has: `:root` tokens, the mono stack, scrollbar rules, the
  reading column, the `#dreambg` shader canvas, reduced-motion handling.
- Legacy full documents keep working: a file without `.part` is served
  as-is. No migration of the two that exist is *required*, though both
  should convert to prove the vocabulary covers them.

## The component vocabulary (the actual work)

Drawn from what the two existing artifacts already needed, so this is
extraction rather than invention:

- **`chain`** — the nested-boxes-with-arrows diagram from the goal tree:
  rows indented by depth, hairline arrows, one row optionally accented.
  Takes a list of `{depth, title, detail, aside}`.
- **`compare`** — the two-column row grid from the dreamtask artifact
  (`DEPTH | LIVES IN`, `garden | errand`): a header pair and rows, with
  a per-row flag for "this one is the point".
- **`decision`** — the block used for every open question: the question,
  then the recommendation beside the alternative it beat, each with its
  reasoning. Used six times across two artifacts already.
- **`label` / `quiet` / `note`** — the prose furniture: dim uppercase
  section labels, muted commentary, a callout for the risk being named.

Components render server-side into the same markup the styleguide
already describes; `watch-design.md` documents the vocabulary, not each
artifact.

## The trade-off to settle (needs a decision, rec inline)

Artifacts are currently **standalone, self-contained, offline-clean** —
a recorded design decision in `watch-design.md`. Serve-time wrapping
means a fragment renders only through watch.py. That is a real loss:
today an artifact can be opened from disk, attached to a message, or
read after the loop is gone.

Rec: **take the trade, and buy the loss back cheaply** — keep fragments
as the authoring format, and give the server a way to emit a fully
inlined standalone copy on demand (`/reviewraw?p=…&standalone=1`, or a
flag on the export path). Central updates are worth more than a file
that is portable but frozen, and "portable" is recoverable in one
function while "already diverged" is not.

## Stages

1. Wrapper: `.part.html` detection, shell injection, shader on by
   default, legacy passthrough. Convert `goal-hierarchies` as the proof.
2. Component vocabulary: `chain`, `compare`, `decision`, prose
   furniture. Convert `ud-dreamtask` using only components — if
   something needs raw markup, that is a missing component, and the gap
   is the finding.
3. `watch-design.md`: document the vocabulary and the authoring rule;
   the artifacts section stops describing per-file conventions.
4. Standalone export, per the trade-off above.
5. Skill side (coordinator): the review-artifact convention in SKILL.md
   becomes "write a fragment"; migration entry.

## Open question for the human

Nothing blocking. One worth raising when he next looks: should the
**dashboard's own pages** eventually render through the same component
vocabulary, or does it stay artifact-only? Rec: artifact-only for now —
the page has its own factories (`qaCard`, `pageHeader`) that predate
this and work; unifying them is a bigger change than it looks and would
be a poor use of the first version.
