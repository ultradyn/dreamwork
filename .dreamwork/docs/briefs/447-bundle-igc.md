# Brief — #447: bundle `use-igcs`, and make the loop reach for it before it judges

Repo: `ud-dreamwork`. Worktree: **`.worktrees/igc`**, branch **`wt/igc`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.
Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are** at the
top (a lane report today was labelled `grok` when `glm52` was dispatched, and I track that).
**Do not write `.dreamwork/handoffs.md`** — the coordinator writes that at merge time.
**Do not edit `.dreamwork/tasks.md` or `.dreamwork/questions.md`** — the coordinator is their only writer.
Report the exact lines you want added instead.

## The instruction, verbatim

> *"re blocking #445: see /use-igcs the skill. we should bundle that skill in with dreamwork and the
> ud-dreamwork skill should instruct the agent to use it before and decision making / design judgement is
> required."*
> — the human, 2026-07-29 00:33, in chat

The bundling decision is **his and already made**. You are not being asked whether to do it.

## What IGC is, and why this is load-bearing here

`IGC = (Idea, Goal, Context)` — the Critical Fallibilism method. Read
**`/home/xertrov/.llm-general/skills/use-igcs/SKILL.md`** and its
**`references/cf-concepts.md`** before you write a line. The short version, so you can recognise a violation:
per (idea, goal) in a stated context you ask only *is there a **decisive** error?* — `✔` non-refuted, `✘`
refuted with the error written out beneath the table, `?` a TODO and never a score. An `All` column rolls up
(`✘` if any `✘`, else `?` if any `?`, else `✔`). Maximisation goals ("fastest", "cheapest") are not binary and
get converted to **breakpoints** — the threshold of *enough*, with margin. Factors with excess capacity are
not goals at all. Zero survivors means fix the problem, not pick a refuted option; two survivors means find
the real differentiating goal, never break the tie by scoring.

This matters to this repo specifically because **`#445` blocked on it.** All four of his question/attention
levels name an "evaluation table" and an IGC, and the term appeared nowhere in the tree, so the design could
not proceed without guessing. It is also the currency of every review artifact we ship him: `#421`'s options
table and `#288`'s A-vs-B are both IGC matrixes written by hand without the method, and both would look
different under it.

## What to do

### 1. Bundle it — and decide *how* with an IGC

The rival ideas are at least: **vendor a copy** into this skill (e.g. `skills/use-igcs/` or
`references/use-igcs.md`); **declare a dependency** and load it by name at runtime; **restate a condensed
IGC section inside `SKILL.md`** with a pointer to the full skill. There may be a fourth.

Goals you must state as binary/breakpoint and evaluate honestly — a dreamwork install on a machine that does
**not** have `~/.llm-general/skills/use-igcs` still gets the method; a fix upstream does not silently leave a
stale copy behind here (state the staleness breakpoint you consider acceptable and how it is detected, not
just that it exists); the loop can reach the method in a single step at the moment it needs it; nothing
depends on a path outside the skill directory at runtime.

**Show the matrix in your report and in the doc you write.** This decision is the method's first dogfood in
this repo and getting it by feel would be the whole failure. If your matrix has zero survivors, say so and
say what you would change — that is a complete answer.

### 2. `SKILL.md` — the instruction at the point of judgement

`SKILL.md` is the loop's own instructions. "Before any decision making / design judgement" is not one place;
find the places and put it where the judgement happens, not in a preamble that reads as background. The
obvious candidates, and you should argue about which of them are real:

- **Selecting the next task** — choosing between rival candidate tasks is a judgement.
- **Any design or architectural choice** made inline by the coordinator.
- **Dispatch**: a lane brief that asks a subagent to choose between options must tell it to use IGC. This is
  the highest-leverage one, because subagents are where most choosing now happens.
- **Review artifacts**: when we ask him to rule, the options table **is** an IGC matrix — ideas down the
  side, his goals across the top, decisive errors written out. This is what makes `#445` implementable.

Keep it tight and in the file's existing voice. `SKILL.md` is already long; if you add a paragraph, look for
one that now says something twice and cut it. **State the cost as well as the buy** — the repo's docs do that
consistently and a rule that only advertises itself gets ignored.

### 3. Make it discoverable and, if you can, checkable

- A `doc-map.md` row for anything you add under `.dreamwork/docs/`. **`doc-map.md` is contended** — other
  lanes are live; if you hit a conflict, resolve as a union and verify the row against the actual directory
  in both directions (a doc-map merge went wrong tonight in exactly this way).
- **Consider a `lint.py` check and say why if you decline.** The plausible shape: a review artifact or brief
  that presents options carries an IGC-shaped table (a decisive-error line under it, not a score column). If
  you add one: **red-proof it** — reinstate the defect, watch it fail, and **name the exact production line
  whose change reds it**. **A green red-run is a finding, never a relief**: if the check passes with the
  defect in place, the check is wrong — do not conclude the code was fine. And **assert the check's own
  precondition** (that at least one artifact matching the pattern exists — a check that silently matches
  nothing passes forever), derived at runtime, never a literal tuned to today's tree. If a check here would
  merely restate the prose it reads, refusing it with that reason is the better answer (`#444` did exactly
  that and was right).

## Done means

1. The method is available to a dreamwork install by the route your IGC chose, with the staleness/detection
   story stated.
2. `SKILL.md` instructs the loop to use IGC at the points where judgement happens, including in lane briefs.
3. A doc under `.dreamwork/docs/` recording the decision **and its matrix**, with a `doc-map.md` row.
4. `python3 lint.py --target .` clean and `python3 -m pytest -q -p no:randomly` passing. **Do not run the
   full `just test`**; bind nothing in 39880–39899 or 39890–39899.
5. Do **not** restart, `pkill` or redeploy the live dashboard on **:35110**, and do not touch the heartbeat,
   the monitors, or the loop. Never `pkill -f` — build process patterns from parts (`#431`: the pattern
   self-matched from a comment).
6. A commit that changes what an existing install must do carries a trailer — `Migration:`, `Feature:`, or
   `Needs: config|consent`. A bundled skill plus a new obligation is likely `Feature:`; decide and say why.

## Files

**Yours:** `SKILL.md`, whatever you add under `.dreamwork/docs/`, `lint.py` + `test_lint.py` **for a check you
add only**, and any bundled skill files you introduce.

**Not yours:** `watch.py`, `dev/capture/*` (a live lane holds `dev/capture/states.mjs` and its floors),
`review_artifact.py`, `review-artifact.template.html`, `.dreamwork/review/*` (a live lane is writing
`421-qs-opts-short.html` right now), `dreamhub.py`, `dev/ledger.py`, `justfile`, `.dreamwork/tasks.md`,
`.dreamwork/questions.md`, `.dreamwork/handoffs.md`.

## Practical

- 2 threads. `git add <newfile>` then `git commit --only <paths> -m 'feat(#447): …'` — **`--only`, never
  `git add -A`**: other agents commit in this tree and a bare `git commit` sweeps their staged work into
  yours. Note `--only <directory>` does **not** pick up untracked files inside it and does not say so, so a
  new file needs `git add <file>` first.
- **Commit before you finish.** Two lanes today did correct work and exited without committing.
- **Push back with reasons if any of this is wrong.** The most valuable lanes today refused what they were
  handed and were right. But note the bundling itself is the human's ruling, not mine — a refusal has to be
  about *how*, not *whether*.

## Report

Say: which model you are; **the IGC matrix for the bundling decision**, with the decisive error under each
`✘`; the exact `SKILL.md` text you added and anything you cut as now-duplicated; whether you added a lint
check and, if so, the production line whose change reds it plus the precondition you asserted, or your reason
for declining; the trailer you chose and why; and confirmation you did not run the full `just test`, touch
:35110, or go near the files the live lanes own.
