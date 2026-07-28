# Brief — #421 research: how `i-have-adhd` instructs, and what our questions cost him

Repo: `ud-dreamwork`. Worktree: **`.worktrees/421`**, branch **`wt/421`**. Do not push, do not merge.
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not write
`.dreamwork/handoffs.md`** — the coordinator writes that line at merge time.

Lane-owns: .dreamwork/docs/research/2026-07-28-question-instruction-design.md

## What he asked for, verbatim

Via the dashboard at 2026-07-28 16:29:

> *"We should update instructions for the dreamwork agent: when asking users questions: get a
> subagnet to write a research artifact about how https://github.com/ayghri/i-have-adhd works (in
> terms of its instructions). Use that to create some options for how we can change instructions to
> ask better questions. Then present those options to me as a question. also, we should support
> research artifacts in like `.dreamwork/docs/research/` or something."*

**You are the first half only: the research.** The coordinator derives the options and writes the
question — that split is his standing instruction from 05:43 (*"I expect you main opus 5 claude
orchestrator to do all the planning … and to prepare precise instructions with measurable goals and
acceptance criteria for your subagents"*). **So do not propose our new instruction text.** Give the
coordinator the material it needs to propose it, and say what the material does and does not support.

Two halves, and the second is the one only you can get:

## Half A — how `i-have-adhd` actually instructs

**Read the repository, not its README summary.** Clone it to a temp directory
(`git clone --depth 1 https://github.com/ayghri/i-have-adhd /tmp/iha-<something>`) and read the
**instruction files themselves** — prompts, system messages, skill/command definitions, whatever
form they take. If the clone fails or the repo is not what the URL suggests, **say so plainly and
stop Half A there**; do not reconstruct it from a web search and present that as the research.

What the coordinator needs, in descending order of value:

1. **The mechanism, concretely.** How does it decide *when* to ask, *what* to ask, and *how much* to
   put in front of the person at once? Quote the instruction text that does each. Quotes over
   paraphrase — a paraphrase of an instruction is a second instruction.
2. **What it forbids or bounds.** Caps, "never do X", one-thing-at-a-time rules, defaults that fire
   when the person does not answer. **Prohibitions and defaults are usually where an instruction set
   earns its behaviour**, and they are what a summary drops first.
3. **What it does when the person does not respond, responds partially, or responds later.** We have
   that exact problem: he answered one sub-question of `#275` and left three, and nothing in our
   instructions notices.
4. **Its theory, if it states one** — why these instructions rather than others. If it does not state
   one, say that; an inferred rationale presented as the author's is the failure mode here.

**Say explicitly what does NOT transfer.** It is a tool for a human's own attention, and we are a
development loop asking an expert about his own project. Mapping it across cleanly is the obvious
mistake, and a research doc whose "implications" section is a straight port is worth less than one
that names three principles and the boundary of each. **Where you are speculating, mark it.**

## Half B — measure what our questions currently cost him

This half is pure measurement against this repo, and it is what makes the coordinator's options
arguable rather than aesthetic. **Every number derived at runtime with the command that produced it
in the doc; no literals.** Use the production parsers — `import watch`, then
`watch.parse_open_questions` and `watch.parse_answered` over `.dreamwork/questions.md`. **Four
hand-rolled parsers were wrong in this repo today**, each against a file whose production parser was
importable; if you write a regex, anchor heading matches (`^## X[ \t]*$`, `re.M`) and assert exactly
one match, and report any disagreement with the parser as a finding.

Measure at least:

1. **Size distribution of question entries** — lines and words per entry, for open and answered.
   Median and max, and name the largest few by title.
2. **Sub-questions per entry.** Our convention marks them `**Q1 —**`, `**Q2 —**`, `**S1**`,
   `**R1**`, `**G1**` and similar; derive the pattern from the corpus rather than assuming a fixed
   list, and say what pattern you used. This is the number the coordinator most needs.
3. **Partial answers: how often he answered some sub-questions and not others.** `#275` is the known
   case (Q2 answered, Q3/Q5/Q6 open); `#263`'s entry was answered across four calls at once. Find
   them all. **This is the single highest-value measurement in the brief** — it is direct evidence
   about format cost rather than an opinion about it.
4. **Time from filing to his answer**, where both are derivable. Note that a questions headline
   carries a **date only** and no time (that is `#392`), so sub-day precision needs
   `git log --format=%cI -1 -S'<headline substring>' -- .dreamwork/questions.md` — measured at ~18ms
   per entry, so fine for a one-off but say if you used it. **Do not report a midnight-derived age as
   an age**; that is the exact bug `#392` describes.
5. **Whether entries with more sub-questions take longer or get answered less completely.** State the
   population size; with a corpus this small, say when a pattern is too thin to call. **"No signal at
   n=6" is a real and useful result** — do not manufacture a trend.

## Done means all of these

1. **`.dreamwork/docs/research/2026-07-28-question-instruction-design.md`** exists, dated in its
   filename (that directory's existing file
   `2026-07-28-parallel-lanes-evidence.md` sets the naming; follow it).
2. **Half A quotes the instruction text it characterises**, with file paths inside the cloned repo
   and the commit sha you read, so the coordinator can re-read exactly what you read.
3. **Half B's every number carries the command that produced it**, and the parser cross-check is
   stated even if it found nothing.
4. **Speculation is marked as speculation**, and there is an explicit *"what does not transfer"*
   section that names boundaries rather than caveats.
5. **A "for the coordinator" section at the end**: the three-to-five findings that should shape the
   options, ranked, each one sentence, each traceable to a quote or a number above. **Not options —
   findings.** If a finding argues against changing anything, include it.
6. **`python3 lint.py` clean.** Do **not** run `just test` — it binds guard ports 39890–39899 and
   another lane holds them; say you skipped it and why. Do not bind any port in 39880–39899.
7. **No HTML.** He asked for research artifacts to be HTML when user-facing, but nothing builds or
   serves research HTML today (that gap is `#422`), so markdown now and the coordinator ships the
   *options* as a review artifact through the existing pipeline. **If you think this doc itself
   should be rendered, say so in the report** — that is evidence for `#422`, not a reason to
   hand-roll a page.

## Files

Yours: `.dreamwork/docs/research/2026-07-28-question-instruction-design.md`. **Nothing else at all** —
`git status --porcelain` proves it at the end. Clone the external repo to `/tmp`, never into this tree.

**Not yours:** `.dreamwork/questions.md` and `.dreamwork/tasks.md` (the coordinator is their only
writer — report findings, do not edit), `file-formats.md`, `lint.py`, `test_lint.py`, `watch.py`,
`test_watch.py`, `watch-design.md`, `.dreamwork/review/` — three other lanes hold those.

## Practical

- 2 threads. `git add <file>` then `git commit --only <path> -m 'docs(#421): …'`. **`--only`, never
  `git add -A`** — three other agents commit in this tree and a bare `git commit` sweeps their staged
  work into your commit under your message.
- Read-only GETs against the running dashboard on **:35110** are fine.
- **Push back with reasons if any of this is wrong.** Ten lanes today have refuted something their
  brief asserted and every one was right to. In particular: if Half B's measurements turn out not to
  support any claim about format cost, **say that clearly** — the coordinator has already written a
  ledger entry asserting three signals point that way, and it would rather be corrected than
  confirmed.

## Report

Say: the cloned repo's commit sha and the instruction files you read; the three-to-five findings from
criterion 5; the derived headline numbers from Half B with their commands, especially the
partial-answer count; anything in Half B that contradicts the premise that our question format costs
him; and which half of your own doc you trust least.
