# Research artifacts — the kind (#422, #403)

A research artifact is **a deliverable, not a note to the author**. His words
via watch, 2026-07-28 16:29 (recorded in `DREAMWORK.md`): research a named
thing, derive options from it, put the options to him — *"we should support
research artifacts in like `.dreamwork/docs/research/` or something. ideally
HTML when they are user facing or benefit from visual expression."* This
directory is that home; this file is the contract a writer obeys when adding
to it.

## Location — decided: this directory, not the flat form

Three spellings of one kind existed when #422 was measured: this directory
(already holding thirteen files), the doc-map's documented flat form
`.dreamwork/docs/research-*.md`, and one stray file actually living in that
flat form (`research-window-coords.md`, since moved here as
`window-coords.md`). A convention spelled three ways is not a convention.

The directory wins, and not by majority: his sentence names it; the docs root
is already crowded enough that a growing `research-*` prefix band would bury
its neighbours; and a directory is the only spelling that can hold its own
header (this file) where the writer is already looking. The flat form is
retired — new research does not land at `docs/` root.

## Naming

`<slug>.md`, where the slug names the question the artifact answers
(`contextual-plugin-discovery.md`), with a `-NNN` suffix when the research
was commissioned by task NNN (`shader-acceleration-278.md`). No date prefix:
git keeps the date, and an alphabetical directory reads as a catalog. The
three `2026-07-28-*` files are grandfathered, not a pattern to repeat.

## What research is not — the boundaries

- **Not a measurement** (`docs/measurements/`). A measurement answers
  how-fast / how-many with a number and a method; research answers
  what-does-it-mean / what-are-the-options. A research artifact may *cite*
  measurements, and commissioning one often means commissioning the other
  first.
- **Not a plan** (`docs/plans/`). A plan proposes a change to this project
  and is pruned when the change lands. Research informs plans but proposes
  nothing by itself; it is kept while its conclusion holds, which is usually
  longer than any plan lives.
- **Not a spike** (`docs/spikes/`). A spike is timeboxed code that answered a
  question; the diff lived on a branch. Research is reading and reasoning,
  not an experiment.
- **Not a review artifact** (`.dreamwork/review/`). A review artifact is
  paired with a `questions.md` entry and archived when the question is
  answered. Research has no question-entry lifecycle and outlives the
  decisions it informed.

When the research itself is generic — true of every target, not just this
one — the finding goes to the system-wide KB (`~/.llm-general/`) and what
stays here is what the answer *means for this project*.

## HTML — implemented by #484, exactly as recommended here

"HTML when user-facing or benefiting from visual expression" has no builder
and no surface today: `review_artifact.py` builds and `watch.py` serves
templated HTML only under `.dreamwork/review/`, and both files are
coordinator-owned, so this is the argued recommendation for a later task,
not an implementation.

**One builder, a second listing surface.** The builder half is already
generic: `review_artifact.py build` takes an arbitrary source file and wraps
it in the one template — the drift it exists to end (five font-families
across twelve hand-authored artifacts) is exactly what hand-authored research
HTML would reproduce. Inventing a second template pipeline would be the same
mistake with a new name. What research must NOT reuse is the review
*surface*: the review listing is paired to `questions.md` entries and
archives with the answered question, a lifecycle research does not have.
So the recommendation is: research sources at `docs/research/src/<slug>.html`
(same `src/` trick that keeps sources out of `list_reviews`' non-recursive
listing), built to `docs/research/<slug>.html` by the existing builder, and a
second listing route in `watch.py` mirroring `list_reviews` over this
directory. Options derived from research still ship to him as review
artifacts through the existing pipeline — that half of his 16:29 message is
already served.

Until #484 landed, research shipped as markdown, and any research finding
that needed visual expression reached him through the review pipeline as
options, per the interim rule already in `DREAMWORK.md`. Now: sources at
`src/<slug>.html` in the review-artifact source format, built by the one
builder to `<slug>.html` beside them, listed and viewed at watch's
`/research` route (raw at `/researchraw`, bare basenames only — a source in
`src/` can never be listed or served as a finished page). `window-coords`
is the first built artifact. Options derived from research still ship as
review artifacts through the existing pipeline — unchanged.

## Retention

Keep while the conclusion holds. When a conclusion is superseded, say so at
the top of the artifact rather than deleting it — a refuted premise with its
reasons recorded is how the same proposal stops returning (#421's "ask one
thing at a time" is the example, refuted by his own answering record).
