# Brief — #263: rebuild the second-gate artifact so he can rule on it — context, problem, IGC, rec

Repo: `ud-dreamwork`. Worktree: **`.worktrees/gateart`**, branch **`wt/gateart`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[gateart]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/gateart-inbox.md` so I can steer you.

Final report goes **once** to `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which
model you are** at the top. **Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or
`.dreamwork/questions.md`.

## The instruction, verbatim

> *"for this artifact page, please add to the top of it: - a paragraph explaining the context - an explanation
> of the problem - the IGC goals, ideas, and table. - your recommendation. be concise."*
> — the human, 2026-07-29 01:22, typed while reading `.dreamwork/review/263-second-gate.html`

Target: **`.dreamwork/review/src/263-second-gate.html`**, rebuilt to `.dreamwork/review/263-second-gate.html`
with `python3 review_artifact.py build .dreamwork/review/src/263-second-gate.html`. **Never hand-edit the built
file.** If the source is missing, say so immediately in the coord inbox and stop — 12 of 27 artifacts have no
source and reconstructing one is a different task than this.

## Why he asked, and the standard he is applying

Minutes earlier he said of another artifact: *"I feel lost when i read these half the time b/c i have no
context."* An audit (`#455`, landed `8a83df1`) then measured the corpus: **17 of 27 first screens answer at
least three of four orientation questions, but only 3 of 27 say what happens if he says nothing.** So this is
not a cosmetic pass — he is naming the four blocks a decision page needs, and asking for them **at the top**,
in order.

`#455` also landed a **build-time contract** for one of them: an artifact must declare what happens if he stays
silent, enforced in `review_artifact.py` (`enforce_if_silent_contract`), refused on **absence**. Your rebuild
must satisfy it. `269-draft-durability.html` was rewritten in that commit as the worked example — **read it
first and match its register**, rather than inventing a second house style.

## The four blocks, in his order

1. **Context paragraph.** What this artifact is, what decision it serves, why he is being asked now, and what
   happens if he says nothing. One paragraph.
2. **The problem.** What `#263`'s second gate actually is, why lanes E, G and H are behind it, and what the
   verified condition was. Read `#263` in `.dreamwork/tasks.md` and the existing artifact for the substance —
   **do not invent history**; if the record does not say, write that it does not.
3. **The IGC — goals, ideas, and the table.** This is the block with the most room to go wrong. Use the real
   method: **`igc-method.md` in the repo root** (vendored tonight as `#447`), with `igc-concepts.md` for depth.
   Ideas down the side, goals across the top with a legend, cells `✔` non-refuted / `✘` refuted / `?` a TODO,
   an **All** column rolling up, and **the decisive error written out beneath each `✘`**. No score column, no
   weights, no pro/con list. Goals must be **binary or breakpoints** — convert any "more is better" goal into
   the threshold of *enough*. If the honest matrix has zero survivors, say so and say what would have to change;
   if two survive, find the differentiating goal rather than breaking the tie by feel.
4. **Your recommendation**, stated plainly, with the accepted answers (`rec` · named options · free text ·
   `not yet`) — that is the `#421` A+D contract he adopted at 01:17.

## Constraints

- **"Be concise" is a style instruction, not a measurement.** He ruled at 01:17: steer with descriptors
  (precise, concise, dense), plan the words in advance, keep any number advisory — *"we just want to steer the
  soft stuff, not try to measure it."* **Do not add a word-count check, and do not report a word count as
  evidence.** Cut evidence he is not being asked to verify and link to the detail instead.
- **The four blocks go at the top, in his order.** Existing detail below them may stay, but anything the four
  blocks now say twice should be cut — an update that grows the page has spent his attention (his 00:54 rule).
- **`#ask` remains a build-time contract** (`#436`): exactly one real ask, above the derived fold. Check the
  fold with `node dev/capture/above_fold.mjs` — it derives the fold per artifact rather than using a constant.
- **Tables must not overflow.** A 4197px-wide table inside a 1120px pane shipped tonight because
  `review-artifact.template.html` sets `table{min-width:max-content}`. For your IGC table set
  `min-width:0;width:100%;table-layout:fixed` and **check it at 390px** — he reads on a phone and told us he
  could not read the last one.
- **You may not build any of lanes E, G or H.** That gate is his to open and the ask is live on his desk. You
  are making the ask legible, nothing else.
- Do not touch **:35110**, the heartbeat, the monitors, or the loop. Never `pkill -f`. Bind nothing in
  39880–39899 except the ephemeral port `above_fold.mjs` serves itself on.

## Done means

1. `.dreamwork/review/src/263-second-gate.html` carries the four blocks, in order, and the built file is
   regenerated and **not stale** (`review_artifact.py` reports the template version; a stale artifact was
   caught by lint tonight).
2. The IGC table renders inside the pane at desktop **and 390px**, and the `#ask` sits above the derived fold —
   report the fold number you measured, not a remembered one.
3. `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
   `just test`.**
4. Report the scroll height before and after.

## Files

**Yours:** `.dreamwork/review/src/263-second-gate.html` and its built output only.

**Not yours:** `review_artifact.py`, `review-artifact.template.html` (the contract landed an hour ago — use it,
do not change it), `watch.py` and `test_watch.py` (**a live lane holds both**), `transitions.md`,
`watch-design.md`, `justfile`, `dev/capture/*`, `lint.py`, `SKILL.md`, `.dreamwork/tasks.md`,
`.dreamwork/questions.md`, `.dreamwork/handoffs.md`, and every other artifact under `.dreamwork/review/`.

## Practical

- 2 threads. `git commit --only <paths> -m 'docs(#263): …'` — **`--only`, never `git add -A`**: other agents
  commit in this tree and a bare `git commit` sweeps their staged work into yours.
- **Commit before you finish.** Lanes tonight have exited with correct work uncommitted.
- **~15–20 minutes.** The IGC is where to spend it; the prose is not.
- **Push back with reasons if the ask itself is wrong** — e.g. if `#263`'s gate turns out to be a plain
  authorisation with no rival ideas, in which case an IGC matrix would be theatre and you should say so and
  write the authorisation ask instead. That is a complete answer; argue it rather than manufacturing options.

## Report

Say: which model you are; the four blocks as written (quote the context paragraph and the rec); the IGC goals
and the matrix with each decisive error; the measured fold and whether `#ask` clears it; the 390px result;
scroll height before/after; and confirmation you built nothing behind the gate, did not touch :35110, and did
not run the full `just test`.
