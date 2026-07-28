# Brief — #417: price the commits-per-period treatments, do not pick one

Repo: `ud-dreamwork`. Worktree: **`.worktrees/417`**, branch **`wt/417`**. Do not push, do not merge.
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not write
`.dreamwork/handoffs.md`** — the coordinator writes that line at merge time.

## What he asked for, and the caution is the requirement

Via the dashboard, 2026-07-28 14:58:

> *"burndown chart should show how many commits were made each period. design needs to be considered
> since we have a pretty good design now and it would be easy to make it worse."*

**He is not asking for a bar chart behind the line.** He is saying the burndown is at a quality he
does not want traded for the extra series. So **you ship a proposal, not an implementation** — a
review artifact showing candidate treatments **rendered against the real chart with real data**, and
he rules before anything lands in `watch.py`.

**This is the `#367` lesson applied before it costs anything:** what ships is what gets argued with.
A provisional version in the tree becomes the default by inertia. So the tree stays unchanged.

## The design problem, stated so you can price it rather than solve it

Commits-per-period is **a second quantity in a different unit** on a chart whose legibility comes
entirely from one line meaning one thing. Density beside a trend is the classic way a good chart
becomes a busy one. **Note that the panel gained a line an hour ago** — `#218`'s filed-to-landed
median (`eb02cf8`), one copy line after the provenance block — so the panel is fuller than the last
person to look at it remembers. **Read the current state before proposing anything.**

Candidates to price (the entry's list, not a decision, and **add any you think better**):

1. **A faint baseline histogram behind the burndown** — the obvious one, and the one most likely to
   make the chart busy.
2. **A thin sparkline rail beneath the axis** — separate, so it cannot fight the line, but it adds a
   band to a panel with a constant-height premise (see below).
3. **Encoding it into the existing line** — dot size or segment weight per period, so **no second
   scale is introduced at all**. Cheapest visually, least precise numerically.
4. **Copy only** — a figure in the panel's voice, the way `#218`'s median went in. Include this one
   even if you think it is weak: it is the option that spends nothing, and it is the baseline every
   other option has to beat.

For each: **what it costs the existing chart**, what it buys, and **what it makes harder to read**.
That third column is the one he needs and the one a proposal usually omits.

## Render them. This is the deliverable, and you do not need to see for it

You are `@glm52` and cannot see rendered output. **That does not weaken this task, because the
artifact's job is to put pixels in front of *him*, not in front of you.** Produce **real renders** of
each candidate — modify `watch.py` **in your worktree only**, drive the page headless, capture, and
embed the images in the artifact as data URIs.

**Do not commit any `watch.py` change.** Your commit contains the artifact and its source only. State
in your report that `git diff --stat` for `watch.py` is empty at commit time, and how you confirmed it.

Render with **real data** — the live repo's own ledger history through `ledger_series` — not a
fixture. A treatment that looks fine on three tidy buckets and fails on the real distribution is the
thing this exercise exists to catch, and the real distribution is available.

Capture each candidate at **1280×900 and 390×844**, because the mobile case is where a second series
usually breaks and where a proposal usually goes quiet.

## Two constraints from the repo that bind your candidates

1. **`watch-design.md`'s burndown contract**, including the **constant-height premise** the existing
   `burndown` guard measures. A candidate that adds a band changes the panel's height and **may break
   that guard** — say which candidates do, because that is part of their cost and it is invisible
   from a screenshot.
2. **`transitions.md` applies with no size floor.** Anything that appears, disappears or changes on a
   data refresh is a transition. The panel re-renders through `innerHTML` each tick, so state for each
   candidate whether it introduces a gesture and whether reduced-motion parity is inherited or needs
   authoring. **A candidate that needs a new motion idiom is more expensive than one that does not**,
   and that belongs in its price.

## Done means all of these

1. **`.dreamwork/review/src/417-burndown-commits.html`** exists and
   `python3 review_artifact.py build .dreamwork/review/src/417-burndown-commits.html` produces
   `.dreamwork/review/417-burndown-commits.html`, with `python3 review_artifact.py check <path>`
   reporting **`current`**. Quote the output verbatim.
2. **Four or more candidates, each with a real render at both viewports**, embedded as data URIs
   (the artifact is offline-clean; a remote image would break it).
3. **Each candidate priced in three columns: buys / costs / makes harder to read.** No candidate
   without all three.
4. **A recommendation with its reasoning, and an explicit statement of what you are least sure of.**
   You may recommend *"copy only"* or *"none of these"* — his caution admits that answer and it is not
   a failure to reach it.
5. **The ask is above the fold**, and prove it mechanically: `getBoundingClientRect().bottom <
   window.innerHeight` for the ask element at both viewports, **with the anti-vacuity precondition
   asserted first** (`scrollHeight > innerHeight`) — an above-the-fold assertion passes trivially on a
   page that fits entirely. Print both numbers per viewport. The idiom exists in `dev/capture/*.mjs`,
   and note the playwright import path those files use.
6. **Guard impact stated per candidate** (criterion 1 of the constraints above), and **transition cost
   stated per candidate** (criterion 2).
7. **`watch.py` is unchanged in your commit.** `git status --porcelain` clean at the end except your
   two artifact paths.
8. `python3 lint.py` clean, `review/` reporting nothing stale. **Do NOT run `just test`** — guards bind
   39890–39899 and two other lanes are live; the coordinator runs the suite at merge (`#424`). Do not
   bind any port in 39880–39899. Serve previews from a temp port outside that range and stop it.
9. **The visual verdict is owed, not yours** — you cannot see. Say *"visual verdict owed"* and do not
   characterise how anything looks beyond what you measured.

## Files

Yours to **commit**: `.dreamwork/review/src/417-burndown-commits.html` and
`.dreamwork/review/417-burndown-commits.html`. Yours to **modify uncommitted**: `watch.py`, for
rendering only.

**Not yours:** `file-formats.md`, `lint.py`, `test_lint.py`, `status_sync.py` (a lane holds those),
`.dreamwork/review/src/263-second-gate.html` (another), `watch-design.md` (read it, do not edit — a
design change is documented in the commit that makes it, and you are making none), and
`.dreamwork/tasks.md` / `.dreamwork/questions.md`, where the coordinator is the only writer.

## Practical

- 2 threads. `git add <file>` then `git commit --only <paths> -m 'docs(#417): …'`. **`--only`, never
  `git add -A`** — two other agents commit in this tree, and here it matters twice over: a bare
  `git commit` would sweep your uncommitted `watch.py` render changes into the commit, which criterion
  7 forbids.
- **Push back with reasons if any of this is wrong.** Fourteen lanes today have refuted something their
  brief asserted and every one was right to. **If you conclude the chart should not carry this series at
  all, say so with the renders that show why** — that is a complete answer to his question, not a
  refusal of it.

## Report

Say: the `review_artifact.py check` output verbatim; the candidates you priced and any you added; the
above-the-fold measurement with both numbers at both viewports; which candidates break the burndown
guard's constant-height premise and which need a new motion idiom; your recommendation and what you
are least sure of; and confirmation that `git diff --stat watch.py` is empty at commit time and how you
checked.
