# Brief — a short version of `421-question-options`: only what he needs to decide

Repo: `ud-dreamwork`. **Work in the main checkout on master.** **Never use `attn`** — the coordinator handles
notifying him; a subagent never does. Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are**.
**Do not write `.dreamwork/handoffs.md`.**

## His request, verbatim (composer, 2026-07-29 00:27, while reading the page)

> *"get a grok subagent to make a must shorter version of this page for me, just the essentials. what do I
> *need* to know to make the decision required? then use attn to tell me it's ready. call it
> 421-qs-opts-short.html and put it next to this one."*

**Output: `.dreamwork/review/src/421-qs-opts-short.html`**, built to
`.dreamwork/review/421-qs-opts-short.html` with `python3 review_artifact.py build`. Leave the long page
untouched — he wants a short version *beside* it, not a replacement.

## The actual task, which is editorial not cosmetic

Read `.dreamwork/review/src/421-question-options.html` and `#421` in `.dreamwork/tasks.md`. Then answer, as
the page: **what does he need to know to make this decision, and nothing else.**

That means cutting, and cutting is the deliverable. Guidance:

- **The decision, stated once, at the top.** He should know what he is choosing between before he scrolls.
- **The options** — four, one already rejected. Keep the rejection and its one-line reason; a rejected option
  he cannot see, he will re-propose.
- **For each live option: what it changes for him.** Not what it changes in the code. He reads these on a phone
  to make a call, so the axis that matters is *what will be different about how the loop asks me things.*
- **Cut anything that is evidence for a claim he is not being asked to check.** Provenance, measurement detail
  and implementation notes belong in the long page — which still exists, so link to it rather than summarising
  it.
- **One table at most**, and only if it genuinely compares. Prose beats a table with one meaningful column.
- **Aim for something he can read in under a minute.** If the long page is ~4300px of scroll, this should be a
  small fraction of that. Say the two numbers in your report.

**Do not invent content.** If a distinction matters and the long page does not make it, say so in your report
rather than filling the gap with plausible reasoning — this page must not become a fifth opinion.

## Hard requirements

1. **A real `#ask`** wrapping the actual decision with the accepted answers spelled out. A build now
   **refuses** a page with no `#ask`, one with both an ask and an exemption, or a **decoy** (`#436`, landed
   tonight) — so this is enforced at build time, not by review.
2. **`#ask` above the fold at both viewports**: `node dev/capture/above_fold.mjs .dreamwork/review/421-qs-opts-short.html`.
   The tool **derives** the fold from the live `/review` route now (`#432`) — trust and print its numbers. On a
   short page this should be easy; if it is not, the page is still too long.
3. **The table trap, fixed tonight in `c19107a` and the reason he could not read the last one**: the shared
   template sets `table{min-width:max-content}`, so a table sizes to unwrapped content — 4197px inside a
   1120px pane. If you use a table, set `min-width:0;width:100%;table-layout:fixed` on it, and **check 390px**.
4. **Do not hand-edit the built file** — it is generated; edit `src/` and rebuild.
5. **Do not touch the shared template** (`review-artifact.template.html`): it re-stamps 23 artifacts and 12
   cannot be rebuilt (`#436`). Page-local CSS only.
6. `python3 lint.py` clean. **Do not run the full `just test`.** Do not touch :35110, the heartbeat, the
   monitors, or the loop.
7. **`transitions.md` binds with no size floor** — you almost certainly introduce no gesture; say so explicitly.

## Files

Yours: `.dreamwork/review/src/421-qs-opts-short.html` and its build output.

**Not yours:** `421-question-options.html` and its source (leave the long page alone),
`review-artifact.template.html`, `watch.py`, `justfile`, `dev/capture/*` (**a live lane holds `states.mjs`**;
you may *run* `above_fold.mjs`), `lint.py`, `.dreamwork/tasks.md`, `.dreamwork/questions.md` — report lines.

## Practical

`git add` the new source then `git commit --only <both paths> -m 'docs(#421): a one-minute version of the
options page'` — **`--only`, never `git add -A`**: other agents are committing in this tree right now.
**Commit before you finish.**

## One thing you should know, and should say if it changes your judgement

At 23:40 he dictated a **full design** for question/attention modes, filed as `#445` — four named levels, an
evaluation table he calls IGC, and a subagent target-plus-policy field. That design arguably **supersedes**
`#421`'s multiple-choice question. He asked for this short page **after** filing it, so build it as asked —
but if you conclude the honest short version is *"this decision may already be answered by `#445`, here is the
residual choice"*, **say that in your report** and consider whether the page should say it too. Do not editorialise
beyond what the two entries support.

## Report

Which model you are; the scroll height before and after; what you cut and the one thing you were most reluctant
to cut; the derived fold and the `#ask` top at both viewports; whether you think `#445` supersedes the question
and why; and confirmation you left the long page and the template untouched and did not hand-edit the built file.
