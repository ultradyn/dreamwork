# Brief — #448 (survey half): what `pag-server`'s question form does, and what of it we should want

Repo: `ud-dreamwork`. **Work in the main checkout. Create no worktree and no branch.** You are **read-only
everywhere except the one output file below** (plus its `doc-map.md` row).
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.
Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are** at the
top. **Do not write `.dreamwork/handoffs.md`** — the coordinator writes that at merge time.
**Do not edit `.dreamwork/tasks.md` or `.dreamwork/questions.md`** — the coordinator is their only writer;
report the exact lines you want added.

## Two-way channel — do this first, before any work

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow its **`for-subagents.md`**. Your **coordinator inbox is
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — it is monitored live, so a line you append
there reaches me in seconds rather than at my next poll. Send the startup handshake there **before** you start
working, prefix every line with `[pagsurvey]`, and if you can watch a file as a background monitor, create
`/home/xertrov/.cache/agent-comms/ud-dreamwork/pagsurvey-inbox.md` and watch it so I can steer you mid-task.

Append a one-line progress note to the coord inbox at each milestone (form found; data model read; table
drafted; committed). This is not ceremony — **three lanes today exited without reporting after doing correct
work**, and the coordinator could not tell a working lane from a dead one. Your final report still goes to
`.dreamwork/inbox.md` as below; the coord inbox is for liveness and steering.

## The instruction, verbatim

> *"eventually we should add a questionnaire feature (after sqlite so we can rely on structured data). This can
> work like pag's (get a grok subagent to see ~/src/pag-server/ and look for the question form. it was quite
> feature rich. We should probably cut back on any superfluous elements."*
> — the human, 2026-07-29 00:34, typed into the dashboard composer while reading a review artifact

Two clauses do the work. **"after sqlite"** means the feature itself is blocked on `#294`, so **you are not
building anything** — the survey is what is unblocked. **"cut back on any superfluous elements"** is a design
constraint he volunteered *before* seeing a proposal, so treat cutting as the deliverable's point rather than
a later review note.

## Why this exists now

`pag-server` is a system he built, so its question form is evidence of what he actually wants a form to do —
worth more than a specification we invent. The reference is fresh in his mind right now; it will not be later.
But it was built for a different product, so a faithful port is the wrong output. What we need is: **what it
does, which of those things a dreamwork questionnaire genuinely needs, and which are superfluous here.**

Context for what this would serve: dreamwork asks him things through `.dreamwork/questions.md` (markdown,
parsed by `watch.py`, rendered in the dashboard) and through review artifacts under `.dreamwork/review/`.
`#445` is his design for four question/attention levels, and `#421` is the standing ask about how the loop
should ask him things at all. Read `#445` and `#421` in `.dreamwork/tasks.md` before you judge relevance —
a questionnaire is plausibly the surface those modes ask *through*.

## What to produce

**One file: `.dreamwork/docs/plans/questionnaire-survey.md`.** Nothing else, plus its `doc-map.md` row.

1. **What `~/src/pag-server/` actually does.** Find the question form and describe its capabilities
   concretely, with **file paths and symbol names** so the next reader can go look. Question types, validation,
   conditional/branching logic, required-vs-optional, defaults, persistence and schema, partial saves, editing
   an answer after submit, rendering, accessibility. **Cite what you read.** If you cannot find something,
   say "not found" rather than assuming it exists — an invented feature would propagate into a design.
2. **The data model**, as it really is (tables/columns or types). This is the half that matters most, because
   his stated reason for waiting on `#294` is *structured data* — so the question is what structure a
   questionnaire needs, and whether `#294`'s planned schema can carry it. Read `#294` in the ledger and say
   plainly whether it can, or what it would have to add.
3. **A keep / cut / open table**, one row per capability, each with a **one-line reason in dreamwork's terms**
   — not pag's. This is the *"cut back on any superfluous elements"* deliverable and I expect the cut column
   to be the longer one. A capability whose reason to keep is "it was there" is a cut.
4. **What dreamwork needs that pag has no equivalent for.** At least consider: a question that must record
   *who authored it* (`questions.md` tags human vs loop authorship deliberately, and it is load-bearing);
   threaded follow-ups on an already-answered question (`#254` has a spec — read it); an answer that reopens
   or amends an earlier one; free-text alongside choices (his `#445` dictation asks for exactly this, with
   `>=1` valid, warn on zero, hard-invalid below zero); and the relationship between a questionnaire and a
   review artifact, which today carries the `#ask` block.

**Use IGC where you are choosing, not a pro/con list.** If a capability has rival designs, evaluate it as
(Idea, Goal, Context) with binary goals and decisive errors — `✔` non-refuted, `✘` refuted with the error
written out, `?` a TODO, never a score; convert "better/faster/richer" goals to breakpoints (the threshold of
*enough*). The method is in `/home/xertrov/.llm-general/skills/use-igcs/SKILL.md` — read it before you write
the table. This is a house rule as of tonight (`#447`) and a scored comparison will be sent back.

## Constraints that matter

- **Read-only outside your one output.** Do not modify anything in `~/src/pag-server/` — it is not our repo
  and you are surveying it, not maintaining it. Do not modify `watch.py`, `dreamhub.py`, `lint.py`,
  `review_artifact.py`, `status.json`, `questions.md`, `tasks.md`, `handoffs.md`, or any source file here.
- **Do not build, prototype, migrate, or touch SQLite.** He sequenced this after `#294`. A prototype would be
  the exact thing he said to wait on.
- **Do not start a server, bind a port, or touch :35110.** Do not run `just test`. Do not `pkill` anything.
- **No literal counts** — if you count questions types or tables, derive it and show the expression. A literal
  is wrong the day after it is written.
- If `~/src/pag-server/` does not exist or holds no question form, **say so and stop** — a survey of something
  else is not a smaller version of this task. Report it and do not substitute.

## Done means

1. `.dreamwork/docs/plans/questionnaire-survey.md` exists with all four sections, paths and symbols cited.
2. A **`doc-map.md` row** for it. **`doc-map.md` is contended** — live lanes are running; if you hit a
   conflict, resolve as a union and verify the row against the actual directory in both directions (a doc-map
   merge went wrong tonight in exactly this way).
3. The keep/cut/open table is present and each row carries a reason in dreamwork's terms.
4. `python3 lint.py --target .` still clean — you changed nothing else it checks, so a new failure means you
   touched more than you meant to.

## Practical

- `git add .dreamwork/docs/plans/questionnaire-survey.md` then
  `git commit --only .dreamwork/docs/plans/questionnaire-survey.md .dreamwork/docs/doc-map.md -m 'docs(#448): …'`
  — **`--only`, never `git add -A`**: other agents commit in this tree and a bare `git commit` sweeps their
  staged work into yours. Note `--only <dir>` does not pick up untracked files, hence the `git add` first.
  Commit on **master**.
- **Commit before you finish.** Two lanes today did correct work and exited without committing it.
- **This should be fast.** Spend the time on the keep/cut judgement, not on prose.
- **Push back with reasons if any of this is wrong** — including if you think the survey is the wrong artifact.
  Lanes that refused what they were handed were the most valuable ones today.

## Report

Say: which model you are; where the form lives (paths); the three or four capabilities you would **keep** and
the reason; the largest thing you would **cut** and why; whether `#294`'s planned schema can carry the data
model or what it must add; anything you looked for and could not find; and confirmation you modified nothing
in `~/src/pag-server/`, ran no server, did not touch :35110, and did not run `just test`.
