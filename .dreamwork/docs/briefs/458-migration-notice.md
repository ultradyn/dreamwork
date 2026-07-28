# Brief — #458: a migration leaves its notice in the file the stale agent still reads

Repo: `ud-dreamwork`. Worktree: **`.worktrees/mignotice`**, branch **`wt/mignotice`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[mignotice]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/mignotice-inbox.md` so I can steer you mid-task.

Report a line per milestone (**sources read**, **IGC done**, **implemented**, **red-proved**, **committed**).
Full report goes **once** to `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which
model you are** at the top. **Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or
`.dreamwork/questions.md` — report the lines you want added and I will file them.

## The gap, and it is real today

Read **`#458` in `.dreamwork/tasks.md`** first — it is P1 and it carries his own words. Then
`migrations/README.md`.

Migrations apply **at initialization only** (orient compares `.dreamwork/skill-version` to the latest entry). So
a **long-running loop that never re-initializes never sees a migration at all**: it holds its routine in context
and keeps running the old protocol indefinitely. Its **skill files are cold** — read once, hours ago. Its **data
files are hot** — read every tick. That makes the data file the only channel guaranteed to reach a stale agent.

His framing, and it is the whole design: *"at the top of tasks.md we can have a comment message that says, this
is an archived copy … the migrate thing can put in messages that mean that any agent that was still running the
old protocol would find those messages and then be able to update itself, update its own routines."*

**The motivating case is `#294`** (ledger → SQLite). The moment `tasks.md` stops being authoritative, an
old-protocol agent keeps *writing* to it and its work is silently lost, because nothing reads it any more. Build
this **before** `#294`, or the first migration that needs it is the one that eats work.

## The decisions, which are an IGC and not a guess

Use **IGC** — `igc-method.md` / `igc-concepts.md` in the repo root: binary goals or breakpoints, per-cell `✔`
non-refuted / `✘` refuted **with the decisive error written out** / `?` a TODO, an `All` rollup, **never a
score**. One matrix is enough; put it in your design doc.

The four questions the ledger entry names, each a real fork:

1. **Where the notice lives** so a human reader and a parser both see it and neither is confused — a leading
   comment, a front-matter block, a first-line marker.
2. **How it is distinguished from content.** Binary and testable: **`lint.py` must not read it as an entry**, and
   **`watch.py` must not render it as a task**. Those two are the goals most likely to refute a rival, so test
   them rather than reasoning about them.
3. **Instructions or a pointer.** A pointer to a migration entry keeps the file small and survives the
   instruction changing; instructions inline are self-contained but rot. Decide with the goal *"the notice does
   not have to be rewritten when the migration's instructions change"*.
4. **How it is retired.** A notice that outlives its migration is the next agent's confusion. Say what removes
   it and when — and prefer a rule an agent can evaluate over a step a human must remember.

**Also state the shrink rule if it applies:** his standing preference is that an update **gets smaller**, not
longer. A notice channel that accretes one banner per migration is the failure mode; say how the Nth migration
does not leave N banners.

## What to build

The **mechanism plus the format contract**, not a migration that uses it:

- The notice writer, in the migration machinery, so **any** migration can leave one.
- The **format stated in `file-formats.md`** in the **same commit** as the code that reads or writes it — that is
  this repo's rule and the format never ships ahead of the parser.
- `lint.py` and `watch.py` proved indifferent to it (goal 2 above). **`watch.py` is held by another lane — do not
  edit it.** If proving `watch.py`'s indifference needs a `watch.py` change, that is a finding: report it as the
  successor and prove the parser's behaviour without editing the file (a test against the existing parse
  function is fine; editing the file is not).
- **Do not perform the `#294` migration** and do not write a notice into the live `.dreamwork/tasks.md`. The
  live ledger is the coordinator's file and a stray banner in it is a real defect, not a demo.

## Verification

- **Red-proof it.** Name the exact production line whose change makes each new test fail, change *that* line, and
  watch it fail. **A green red-run is a finding, never a relief** — twice tonight a proof came back green because
  the injection never reached the code: once a fixture built the filtered list itself instead of calling the
  function that decides it, once a fake returned `""` for precisely the input that reached the branch.
- **Assert each check's precondition at runtime**, derived — never a literal tuned to today's tree.
- The interesting test is the **negative** one: a file carrying a notice parses to exactly the same entries as
  the same file without it. Derive both sides from the parser; do not hand-write the expected list, or you have
  built the scaffolding that stands in front of the code.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`.** Bind nothing in 39880–39889 or 39890–39899. Kill anything you start by exact pid.
- Do **not** restart, `pkill` or redeploy the dashboard on **:35110** (he is reading it). Do not touch the
  heartbeat, the monitors, or the loop. Never `pkill -f`.
- Trailer: this changes what an install's migration machinery does — `Migration:` or `Feature:`; decide and say
  why.

## Deliverables

1. The mechanism, the `file-formats.md` contract in the same commit, and the tests.
2. A short design doc at `.dreamwork/docs/plans/migration-notices.md` with the IGC and the retirement rule, plus
   a **`doc-map.md` row** (contended: on conflict resolve as a **union** and verify the row against the real
   directory **in both directions**).
3. In your report: the questions.md lines you want filed, if any decision genuinely needs him. Use the declared
   form so a fold can be checked — one bold `**Sub-decisions:** ` `Q1`, `Q2` line naming each call. And
   **prefer deciding it yourself with a stated decisive error** over asking; his desk is nearly clear tonight and
   an ask is the expensive option.

## Files

**Yours:** `migrations/*`, `file-formats.md`, `lint.py` and `test_lint.py` **only** as goal 2 requires,
`.dreamwork/docs/plans/migration-notices.md`, `.dreamwork/docs/doc-map.md`, and your new test file.

**Not yours:** `watch.py`, `test_watch.py`, `test_user_events_http.py`, `user_events/*` (**lane E2 holds those
and is mid-increment**), `review_artifact.py`, `.dreamwork/review/**`, `transitions.md`, `watch-design.md`,
`justfile`, `dev/capture/*`, `SKILL.md`, `DREAMWORK.md`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`,
`.dreamwork/handoffs.md`.

## Practical

- 2 threads. `git add <newfiles>` then `git commit --only <paths> -m 'feat(#458): …'` — **`--only`, never
  `git add -A`**: other agents commit in this tree, and `--only <directory>` silently skips untracked files.
- **Commit before you finish.** **~20 minutes.** If the format decision turns out to need his ruling, land the
  parser-indifference tests plus the documented form and report the rest as the successor.
- **Push back with reasons.** If the honest finding is that a banner in a data file cannot be made safe — or that
  the notice belongs somewhere else entirely — argue it. A refusal with evidence is a complete answer, and the
  most valuable lanes tonight refused what they were handed.

## Report

Say: which model you are; the IGC with each decisive error and the surviving idea; where the notice lives and how
it is distinguished from content; pointer vs instructions and why; the retirement rule and how the Nth migration
avoids leaving N banners; the production line whose change reds each test and the precondition you asserted; the
trailer you chose; and confirmation you did not touch `watch.py`, did not write a notice into the live
`.dreamwork/tasks.md`, did not perform `#294`'s migration, did not touch :35110, and did not run the full
`just test`.
