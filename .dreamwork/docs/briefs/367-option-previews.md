# Brief — #367 previews: show him A, B and C below the cliff

Repo: `ud-dreamwork`. Worktree: **`.worktrees/367p`**, branch **`wt/367p`**. Do not push, do not merge.
**Never use `attn`** — report through the inbox path at the bottom.

Lane-owns: .dreamwork/review/src/367-option-previews.html, .dreamwork/review/367-option-previews.html, .dreamwork/review/evidence/367-option-previews/

**You were chosen for this because you can see.** The deliverable is judged on rendered pixels
and the acceptance includes your own visual verdict, not only measurements. Say what the
screenshots actually look like.

## The ask, verbatim

He is ruling on `#367` and wrote at 14:52:

> *"can you generate previews of each of the options and what they would look like please? I
> tihnk C is fine but want to see it first."*

So: three previews, one page, honest enough that seeing them could change his mind.

## The decision they illustrate

Question marks (5–7 of them) need navigation chrome. **Above ~830px** viewport width there is a
lateral rail of tabs and it works. **Below** the cliff there is no lateral space — the reading
column is fixed at **613.5px** and the page's outer margin is **16px at every width from 1120px
down** — so the chrome has to stack above the text.

A tab's worst case is **180 × 32.3px** (two lines, ~6 words; he ruled out truncation on
2026-07-27, so a label is never cut).

- **A · Pay the chrome.** The strip grows to as many rows as the marks need. At his soft cap of
  7 that is ~3 rows, ~214px of chrome above the text.
- **B · Bounded strip, then "+3 more".** Two rows and an overflow affordance. The loop's rec is
  *reject*: it keeps most of the chrome and becomes an incomplete index, truncating the **set**
  rather than a label — the argument he already rejected one level up.
- **C · Just the walk.** No labels in the chrome. One row: next/prev and "3 of 7", ~32px; the
  label appears **at** the mark you land on. Nothing truncated, every mark reachable, and the
  at-a-glance overview is lost.

**The cost is the whole decision: 214px of permanent chrome versus losing the overview.** The
page must let him price that. Do not build a sales pitch for C — if A looks better than its
number suggests, that is the most useful thing this page can tell him.

## The rule that makes this worth building: measure, never draw

A mockup that draws a plausible strip and captions it *"214px"* is worse than nothing, because
the number is the decision and the caption is the only part he can check at a glance. This repo
has spent a day on checks that reported on something other than the thing they named.

**So no pixel figure in this artifact may be typed by hand.** Every height, row count and
"3 of 7" is **measured from the rendered DOM at load** — `getBoundingClientRect()` — and written
into its own caption by script. The caption then cannot disagree with the pixels above it.

The red-proof for that, and it is required: **change one option's row count in the markup and
reload.** Its caption number must change with no text edit. If it does not, the number is a
literal wearing a measurement's clothes — say so.

## Build it through the template, not by hand

`review_artifact.py` owns the head, palette, frame and footer (`#325`); artifacts authored
freehand drifted to five font stacks and eight backgrounds all meaning "the dark one".

- Source: **`.dreamwork/review/src/367-option-previews.html`** — the `src/` subdirectory is
  load-bearing, since `watch.py`'s `list_reviews` is a non-recursive listdir and a source
  sitting beside the artifacts would be served as one.
- Build: `python3 review_artifact.py build .dreamwork/review/src/367-option-previews.html`
- Verify: `python3 review_artifact.py check .dreamwork/review/367-option-previews.html` — it
  must report neither `stale` nor `untemplated`, and **offline-clean is a hard contract**: any
  remote fetch is refused, so inline everything.

## Done means all of these, each measured

1. **All three options render at true below-cliff geometry**: viewport **780px**, reading column
   **613.5px**, outer margin **16px**, **7 marks** with realistic ~6-word labels that wrap to two
   lines. Not lorem — use plausible question titles so the wrap is real.
2. **Every figure on the page is measured at load and injected by script.** Grep your own source:
   no hardcoded `214`, `32`, `3 of 7` or row count in any caption. Report the grep.
3. **The row-count red-proof** above: change a row count, reload, caption follows. Exact before
   and after numbers in your report.
4. **A second below-cliff width** — render at **640px** too, and state whether the 16px outer
   margin claim actually holds there. That claim is load-bearing for the whole "no lateral
   space" argument and it was measured once.
5. **One reference row showing the above-cliff rail**, clearly labelled *not an option* — he
   cannot price what C loses without seeing what it loses.
6. **Screenshots** of each option at both widths, saved under
   `.dreamwork/review/evidence/367-option-previews/`, committed.
7. **Your visual verdict, as prose in the report.** Does C at ~32px read as a usable walk or as
   a stub? Does A at ~214px look as heavy as the number says, or does the eye forgive it? Does B
   look like the worst of both, as the loop claims? **You may disagree with the rec** — a lane
   that confirms every prior is not adding vision to this.
8. `python3 -m pytest test_review_artifact.py -q -p no:randomly` passes, and `python3 lint.py`
   is clean.

## Files

Yours: `.dreamwork/review/src/367-option-previews.html`, the built
`.dreamwork/review/367-option-previews.html`, and
`.dreamwork/review/evidence/367-option-previews/**`. **Nothing else.**

**Do not implement the feature.** `watch.py` is read-only for you — read it to match the real
strip/rail markup and classes so the previews look like the product rather than like a diagram,
but change nothing. `git status --porcelain` proves your scope at the end.

**Do not touch `.dreamwork/questions.md` or `.dreamwork/tasks.md`** — the coordinator is the
only writer for those, and it will fold your artifact into his open question itself.

## Practical

- **Do not bind ports 39890-39899.** Another lane is running the guard suite on them. Open your
  artifact over `file://` for screenshots — it is offline-clean by contract, so it needs no
  server.
- 2 threads.
- Commit with `git commit --only <paths> -m 'review(#367): …'`. **`--only`, never `git add -A`**:
  two other agents are committing in this tree and a bare `git commit` sweeps up their staged
  work under your message. **New** files need `git add <file>` first.
- Push back with reasons if any of this is wrong. The last three lanes each found a real error
  in a brief and each was right to report it rather than guess.
- Then append one line to the **absolute** path
  `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/handoffs.md`:
  `- **#367** · landed \`<sha>\` · <YYYY-MM-DD HH:MM> · by <you> — <what>`, and commit it.

## Report

Append once, at the end, to the **absolute** path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`.

Say: the measured chrome height of each option at both widths; the row-count red-proof numbers;
whether the 16px margin holds at 640px; the grep proving no hand-typed figures; and **your own
visual verdict on all three**, including whether you would still recommend C.
