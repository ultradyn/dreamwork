# Brief — #421 B: a half-answered ask must be loud. `lint` errors when a fold drops a sub-decision.

Repo: `ud-dreamwork`. Worktree: **`.worktrees/subdec`**, branch **`wt/subdec`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: lint.py, test_lint.py, file-formats.md

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[subdec]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/subdec-inbox.md` so I can steer you.

Final report goes **once** to `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which
model you are** at the top. **Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or
`.dreamwork/questions.md` — report the lines you want added.

## The grant

`#421` was answered **2026-07-29 01:17 — `rec`: A + B + D adopted.** A and D are conventions the coordinator
applies when writing asks and are already written into `file-formats.md`. **B is the buildable half and it is
yours:**

> **B** — an unanswered sub-decision is recorded, and `lint` errors when a fold drops one.

Read `#421` in `.dreamwork/tasks.md` and the ask contract section of `file-formats.md` (added tonight) before
starting.

## The live defect this exists for — start by confirming it still holds

**`#275`'s Q3, Q5 and Q6 have been unanswered since 2026-07-25, and nothing notices.** That is the whole
argument for B: a multi-part ask can be *half* answered, the entry gets folded on the strength of the parts that
were answered, and the remainder becomes invisible because nothing ever re-reads a folded entry.

**Verify that before you build.** Read `#275` in `.dreamwork/tasks.md` and its `questions.md` entry, and report
which sub-questions are genuinely still open. If the record has moved and they are answered now, **say so** —
then the check still has value but you must find or construct an honest subject for it rather than citing a
defect that healed.

## What to build

A `lint.py` check that a **folded** (Answered) multi-part ask has an answer for **every** sub-decision it posed.
The design decisions are yours; these are the constraints that make it real rather than decorative:

- **Recognising a sub-decision must not be a guess from prose.** The repo's rule is that a parser's input has a
  stated shape (`file-formats.md`) and the format never ships ahead of the parser. Tonight's asks label them
  `C1`/`C2`, `Q1`/`Q2`, `M1`/`M2`/`M3`, `I1` — look at what is actually in `questions.md`, derive the pattern,
  and **state the contract in `file-formats.md` in the same commit** as the code that reads it. If the honest
  answer is that the current corpus is too irregular to parse safely, **say so and propose the minimal declared
  form** rather than shipping a regex that half-works. A check that silently matches nothing is the failure mode
  this repo has paid for most.
- **ERROR, not WARN, for a dropped sub-decision** — that is what "lint errors" means in his answer. But be
  careful about *retroactive* errors: if turning it on reds the existing corpus, the check is unusable on day
  one. Decide and state how history is handled (a content-resolved cutoff, as `lint.py` already does for the
  `#405` brief check — read `resolve_worktree_abs_inbox_cutoff` for the idiom; **not** a sha pinned by hand).
- **Where the "recorded" half lives.** His B has two clauses: unanswered sub-decisions are *recorded*, and a
  dropping fold *errors*. If recording is just "the entry keeps its unanswered `Qn` visible", say that and show
  it. Do not build a second store.

## Verification, which is where this check will live or die

- **Red-proof it.** Construct a folded entry that answers `Q1` but not `Q2`, watch the check error, and **name
  the exact production line whose change reds it.** **A green red-run is a finding, never a relief** — if the
  check passes with a sub-decision dropped, the check is wrong; do not conclude the fixture was fine.
- **Assert the check's own precondition at runtime**: that the corpus contains at least one multi-part ask for
  it to examine. Derive it; never a literal count tuned to today's file. Three checks here were found hollow in
  a single batch for exactly this omission.
- **Beware the fixture that stands in front of the code.** If your test builds the sub-decision list itself
  instead of calling the function that decides it, reverting that function changes nothing the test can see —
  that happened twice in two hours here. Name the production line you changed to red it, and change *that*.
- Do **not** add any length or count gate on the prose itself (his 01:17 ruling: numbers steer, never gate).

## Done means

1. The check exists in `lint.py`, errors on a dropped sub-decision, and the recognised form is documented in
   `file-formats.md` **in the same commit**.
2. `python3 lint.py --target .` is **clean on the current tree** — if it is not, either the corpus has a real
   defect you should report (do not edit `questions.md` to silence it; the coordinator owns that file) or your
   history handling is wrong.
3. `python3 -m pytest -q -p no:randomly` passes, with your new tests included. **Do not run the full
   `just test`.** Bind nothing in 39880–39899 or 39890–39899.
4. Do not touch **:35110** (he is reading it), the heartbeat, the monitors, or the loop. Never `pkill -f`.
5. Trailer if an install's behaviour changes: `Migration:`, `Feature:`, or `Needs: config|consent`. A new
   erroring lint rule on an existing install is likely `Feature:` — decide and say why.

## Files

**Yours:** `lint.py`, `test_lint.py`, and `file-formats.md`'s ask-contract section.

**Not yours:** `watch.py`, `test_watch.py`, `transitions.md`, `watch-design.md`, `justfile`, `dev/capture/*`,
`review_artifact.py`, `.dreamwork/review/**` (a live lane holds the `#263` artifact), `dev/ledger.py`,
`dreamhub.py`, `SKILL.md`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/handoffs.md`.

## Practical

- 2 threads. `git commit --only <paths> -m 'feat(#421): …'` — **`--only`, never `git add -A`**: other agents
  commit in this tree and a bare `git commit` sweeps their staged work into yours.
- **Commit before you finish.** **~15–20 minutes.** If the parsing contract turns out to need a corpus migration,
  land the check plus the documented form and report the migration as a successor.
- Choosing between rival designs? Use **IGC** — `igc-method.md` in the repo root (vendored tonight, `#447`):
  binary goals or breakpoints, `✔`/`✘`/`?`, decisive error written under each `✘`, no scoring.
- **Push back with reasons if this check cannot be made honest.** `#444` refused a threshold check on the ground
  that it would merely restate the constant it read, and was right to. A refusal with evidence is a complete
  answer; a check that cannot fail is worse than none.

## Report

Say: which model you are; whether `#275`'s Q3/Q5/Q6 are still open; the sub-decision form you recognise and
where it is documented; how history is handled and how the cutoff resolves; the production line whose change
reds the check and the precondition you asserted; the trailer you chose; and confirmation lint is clean on the
current tree, you did not run the full `just test`, and you did not touch :35110.
