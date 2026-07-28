# Brief — #421 artifact: four options for how the loop asks him things

Repo: `ud-dreamwork`. Worktree: **`.worktrees/421a`**, branch **`wt/421a`**. Do not push, do not merge.
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not write
`.dreamwork/handoffs.md`** — the coordinator writes that line at merge time.

## The spec, and it is a file rather than this brief

**`.dreamwork/docs/plans/question-instruction-options.md`** is authoritative: four options (A the ask
comes first; B unanswered sub-decisions are recorded and lint-enforced; C a length budget with the
evidence in the artifact; D state what a valid answer looks like), one **rejected with its reason**
(one-decision-per-entry), and a recommendation of **A + B + D with C soft**.

Its input is `.dreamwork/docs/research/2026-07-28-question-instruction-design.md` (`ccc @grok`,
`bae566d`, `i-have-adhd` at sha `c784dcb`). **Read both.** Where they disagree, the plan wins and you
should report it.

The question that will link to your artifact is the top entry of `.dreamwork/questions.md` — read it
too, and **match it**; do not introduce a fifth option or change a recommendation.

## The thing that makes this artifact unusual, and it is the whole design problem

**This artifact is about how we present decisions to him, so it is itself an instance of the thing
under discussion.** An overlong, dense page arguing that our questions are overlong would be a
self-refuting document, and he would be right to read it as one.

So the artifact must **demonstrate option A and option D on itself**: the ask and its accepted answers
visible before any argument, above the fold, at both viewports. **If your page cannot pass its own
Option A test, it is wrong regardless of how good the content is** — and say in your report how you
checked that rather than that you intended it.

That constraint fights the usual instinct to show all the evidence at once. Resolve it by **ordering**,
not by omission: ask first, recommendation second, the four options third, the measured evidence
fourth. Nothing is dropped; the argument is downstream of the decision.

## The measurement that carries the argument

Lead the evidence with the finding, because it is counter-intuitive and one number makes it:
**the two entries whose titles promise a "one word" answer are 300 and 448 words, both above the
corpus median of 302.** The size of what we write is weakly coupled to the size of what we are asking.
That single comparison is more persuasive than the whole distribution, and it deserves a visual.

The distribution is worth showing too — n=56, min **29**, p25 **112**, median **302**, p75 **517**,
max **1121** words — but **re-derive every number yourself** from `.dreamwork/questions.md` using
`watch.parse_open_questions` / `watch.parse_answered`, and state the command in the page. **Do not copy
a figure from this brief or from the plan.** Two of the coordinator's figures were wrong today and one
of them is corrected inside the plan you are reading; a third was refuted by the research lane. **If
a number you derive disagrees with the plan, that is a finding — report it and use yours.**

Also show, because it is the part that stops a bad decision: **19 of 56 entries carry ≥2 sub-decisions
and 15 of 16 answered multi-sub entries closed complete.** That is the evidence that kills the obvious
option, and the rejected option must be visible with that number beside it — a rejected option with no
number reads like a straw man.

## Done means all of these

1. **`.dreamwork/review/src/421-question-options.html`** exists and
   `python3 review_artifact.py build .dreamwork/review/src/421-question-options.html` produces
   `.dreamwork/review/421-question-options.html`. **`python3 review_artifact.py check` reports
   `current`** for it. Quote the output verbatim.
2. **It passes its own Option A test**: the ask and the accepted answers are visible without scrolling
   at **1280×900** and **390×844**. Prove it with a rendered capture at each, and say what you measured
   (the element's position, not "it looks fine").
3. **Four options, each with what it reduces, what it costs, and its risk** — the plan states all
   three per option and none may be dropped. The **risk** lines are load-bearing: option C's risk is
   that a length cap pushes evidence behind a click, which is the argument against the coordinator's
   own tidiest idea.
4. **The rejected option is present with the completion number beside it.**
5. **Every number re-derived with its command stated in the page.**
6. **Offline-clean, verified not asserted**: no external fetch of any kind; grep the built file for
   `http://` / `https://` outside link text and report the count.
7. **Matches the repo's dark-mode language.** Read `watch-design.md` and look at
   `.dreamwork/review/task-transition-boundary.html` before writing CSS. **Reuse the idiom; do not
   author a second one.** Use the template's tokens rather than hex literals.
8. **`transitions.md` applies** to anything that appears, disappears, expands or collapses — there is
   no size floor on that rule here. If you use a disclosure to keep the evidence below the ask, read
   that file first, reuse the existing idiom, and honour reduced-motion parity.
9. `python3 lint.py` clean, `review/` reporting nothing stale. **Do not run `just test`** — four other
   lanes are live and guard ports 39890–39899 are held. Serve previews from a temp port **outside
   39880–39899** and stop whatever you start.

## Files

Yours: `.dreamwork/review/src/421-question-options.html` and
`.dreamwork/review/421-question-options.html`. **Nothing else at all** — `git status --porcelain`
proves it at the end.

**Not yours:** `.dreamwork/questions.md`, `.dreamwork/tasks.md` and the plan (report exact lines
instead; the coordinator is their only writer), `watch.py`, `test_watch.py`, `watch-design.md`,
`file-formats.md`, `lint.py`, `test_lint.py`, `user_events/*`, and
`.dreamwork/review/src/263-second-gate.html` — four other lanes hold those.

## Practical

- 2 threads. `git add <file>` then `git commit --only <paths> -m 'docs(#421): …'`. **`--only`, never
  `git add -A`** — four other agents commit in this tree and a bare `git commit` sweeps their staged
  work into your commit under your message.
- **Push back with reasons if any of this is wrong.** Twelve lanes today have refuted something their
  brief asserted, every one was right to, and **two of today's refutations are inside the documents you
  are building from** — the research killed the premise the task was filed with, and the plan corrects
  a claim the coordinator made three hours earlier. If you think an option is wrong, or that the
  recommendation should differ, say so with your reasoning before building.

## Report

Say: the `review_artifact.py check` output verbatim; how you verified the above-the-fold ask at both
viewports and what you measured; every number you re-derived with its command, flagging any that
disagreed with the plan; your offline-clean count; whether you used a disclosure and how you handled
its transition; and **your own visual verdict on whether the page passes the standard it argues for**.
