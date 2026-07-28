# Brief — #264, the empirical half: what thirteen parallel lanes in one tree actually did

Lane-owns: .dreamwork/docs/research/2026-07-28-parallel-lanes-evidence.md

You are a dreamer on the `ud-dreamwork` skill repo. Read `CLAUDE.md` first.

**Do NOT use the `attn` utility. Ever.** Only the coordinator talks to the human.
Report by the file route at the bottom.

**This task writes ONE research document and changes no code.** Three lanes are live and
between them they hold `watch.py`, `test_watch.py`, `lint.py`, `test_lint.py`,
`file-formats.md`, `SKILL.md`, `review_artifact.py`, `review-artifact.template.html`,
`.dreamwork/review/`, `watch-design.md` and the `justfile`. There is nothing here for you to
fix and any fix would collide.

## The chain above this task

- **DREAMWORK.md goal**: the loop serves the human's ability to see and steer it — and he
  has asked, twice through the dashboard, whether it can safely run more than one worker.
- **Session goal**: dogfooding the loop with a coordinator directing subagents instead of
  doing the increments itself. He asked for that to produce findings, not just output.
- **This task**: the **empirical half of `#264`** (P1, `origin: **human**`). Its design half
  — the task-transition/materialised-view boundary — **already landed** at `914648c`. Do not
  redo it.

## Read this scoping paragraph twice, because #264 is much bigger than your task

`#264` as filed asks for a comparison of single-writer+workers, append-only
events/materialised views, locks/atomic-replace/CAS, leases, SQLite and per-record spools,
**plus** the `#294` migration script, mixed-writer cutover, rollback and recovery. **That is
not your task and you must not attempt it.** A lane that returns a survey of concurrency
primitives has failed this brief however good the survey is.

**Your task is the evidence, not the design.** Today this repository ran **thirteen dreamer
lanes in a single shared working tree** in one session. That is the exact experiment `#264`
asks about, it already happened, and **nobody has read the record of it as a corpus.** You
are going to, and then you are going to say what it demonstrates about `#264`'s options.

The distinction that keeps you in scope: **you report what the evidence shows and what it
rules out. You do not choose a mechanism.** If the evidence favours one, say "the evidence
favours X because of these N incidents" — that is a finding. "We should build X" is a design
call and it is not yours.

## Your corpus, and it is entirely durable

- **`git log`** for today (2026-07-27 and 2026-07-28) — every lane's commits, their
  messages, their file sets, their interleaving, and their timestamps. `git log --format=...
  --name-only` is your primary instrument. **The interleaving is the data**: which commits
  from different lanes landed between each other, and on which files.
- **`.dreamwork/inbox.md`** — every lane's self-report, including what each said it was not
  confident about.
- **`.dreamwork/lessons.md`** (~2000 lines) — the coordinator's running record of what went
  wrong. Several entries are directly about concurrency; find them rather than trusting this
  list.
- **`.dreamwork/docs/dogfood-orchestration.md`** (~700 lines) — the coordinator's own notes
  on running the fan-out, including a section on how parallel lanes interact with
  verification.
- **`.dreamwork/status.json`** — the live ownership table: which lane owns which files.
- **`.dreamwork/dreams/`** and **`dreams/archive/`** — lane journals.
- **`.dreamwork/tasks.md`** — the ledger, single-writer by design.

## The questions to answer, in priority order

1. **Enumerate every actual incident of concurrent-access damage or near-damage**, with its
   commit sha or inbox line. Not classes — instances. For each: what two parties touched
   what, what the damage was or would have been, and what caught it (a check, a human, a
   coordinator's eye, or nothing until later).
   **This is the deliverable's spine.** A claim in this document without an instance behind
   it is worth nothing, because #264's whole difficulty is that the failure modes sound
   plausible in the abstract and only some of them actually happen.
2. **Which mechanism actually prevented damage, and which merely appeared to?** The repo
   relies on: a stated ownership list per lane, `git commit --only <paths>`, the
   single-writer rule for the ledger, and an append-only inbox. **For each, find an instance
   where it held and an instance where it did not** — or say plainly that you could not find
   one, which is itself a result about how load-bearing it really is.
   Known starting point, and check whether it is the only one of its kind: `git commit
   --only` isolates **paths, not hunks**, so it still sweeps a concurrent lane's uncommitted
   changes *in the same file*. Find whether that ever actually happened.
3. **What did the shared tree cost that a worktree would not have?** `CLAUDE.md` prescribes
   worktrees when disjointness cannot be arranged, and today's session used **one** while
   running thirteen lanes. Was that a mistake, and what is the evidence either way? Count
   the incidents that a worktree would have prevented, and — the other half, which is the
   part usually skipped — the costs a worktree would have **added**, evidenced from the one
   lane that did use one (`.worktrees/264-transition-boundary`, merged at `914648c`).
4. **Where did serialisation actually bite?** Lanes queued behind a held file rather than
   running. Find the instances in `status.json`'s `queued_dispatches` and in the ledger, and
   say **which file was the bottleneck** and how much work waited on it. A contended file
   named with evidence is more useful to `#264` than any abstraction.
5. **What broke that was NOT concurrent access, but was caused by parallelism anyway?**
   Second-order effects. One is documented: a new file in a registry-checked directory
   reddens *other* lanes' baselines until registered. Find the rest. **This class is the one
   #264 does not currently anticipate**, so anything you find here is new information rather
   than confirmation.
6. **What does the evidence rule OUT?** The most useful sentence you can write is one that
   kills an option `#264` lists. If the record shows that, say, a lease-based scheme would
   have prevented zero of the actual incidents, that is worth more than a paragraph in
   favour of anything.

## Acceptance criteria — binary, and I will check each one

1. **Files touched, and only this one:**
   `.dreamwork/docs/research/2026-07-28-parallel-lanes-evidence.md` (new). `git status
   --porcelain` shows nothing else. **Do not create a directory** — that one exists, and a
   new file in a registry-checked directory reddens the live lanes' `lint.py` baseline.
2. **At least 8 concrete incidents**, each with a **sha, an inbox line, or a lessons.md
   quote** identifying it. Fewer than 8 with a stated reason is acceptable; fewer than 8
   silently is not. **An incident without a locator does not count toward the 8** and I will
   check the locators.
3. **Every one of questions 1-6 has a section, and question 6 is not empty.** If the evidence
   rules nothing out, say so explicitly and explain why the record cannot discriminate —
   that is a finding about the record.
4. **Each of the four mechanisms in question 2 gets a held-instance and a failed-instance, or
   an explicit "no instance found".** Six of eight boxes filled beats eight boxes filled
   plausibly.
5. **A count.** How many lanes ran, how many commits they produced, how many files were
   touched by more than one lane, and how many incidents you found. **Derive these from `git
   log`, not from `dogfood-orchestration.md`'s prose** — that document is the coordinator's
   account and this task's value is partly in checking it. **If your count disagrees with
   that document, the disagreement is a finding and you must report it.**
6. **`python3 lint.py` exits 0** when you finish, run as its own command — proving you left
   the tree as you found it.
7. **The document ends with a literal `--- SUMMARY ---` line** followed by a concise
   dot-point summary. That is the human's house style and he reads the summary first. Read
   an existing file in `.dreamwork/docs/research/` first and follow its shape.

## The hollow outcomes, and there are three

**One: a concurrency survey.** Locks versus leases versus CAS, well written, evidence-free.
`#264` already contains that list; you are here because nobody has checked it against what
happened.

**Two: restating `dogfood-orchestration.md`.** That document is the coordinator's own
account, written from inside the session, by the party with the strongest incentive to
believe the fan-out went well. **Read it, cite it, and check it.** Where `git log` disagrees
with it, `git log` wins and you say so. Finding it wrong is one of the more valuable things
you could do here.

**Three: counting near-misses as incidents without distinguishing them.** "This would have
been damage if X" and "this was damage" are different rows and must be labelled. `#264`'s
answer depends on the ratio.

## The rules that matter most here

**One value must come from outside the system.** A defect landed on the deployed dashboard
this morning because every value a check compared came from inside the thing being checked
(`#392`). Your analogue: **do not source a fact about a lane solely from that lane's own
report.** Cross-check against `git log`.

**Before you report an edge case, enumerate its neighbours.** If you find one incident on a
file, check the files beside it in the same commit.

**`grep -c` exits 1 when the count is zero**, so a verification chain joined by `&&` reports
a skipped tail as a pass. You are counting things and some counts will legitimately be zero.

**Say what you are not confident about.** An honest "the record cannot tell me whether X"
is worth more than an inferred instance, and inventing an incident to reach 8 would poison
the one deliverable this task has.

## Files

**Yours:** `.dreamwork/docs/research/2026-07-28-parallel-lanes-evidence.md` (new). Nothing
else.

**Read freely, do not edit:** everything named under "Your corpus", plus `CLAUDE.md`,
`SKILL.md` (a lane is editing it — read it with `git show HEAD:SKILL.md` if you want a
stable copy), `.dreamwork/docs/plans/task-transition-boundary.md` (the landed design half —
read it so you do not duplicate it), `file-formats.md`, `justfile`.

**Never touch:** every file in the working tree except your one new document. Three lanes
are mid-flight and the tree has uncommitted work in `watch.py`, `lint.py`, `SKILL.md`,
`file-formats.md`, `review_artifact.py`, `test_watch.py`, `test_lint.py`,
`test_review_artifact.py`, `review-artifact.template.html` and the `justfile`. **Do not
revert, stash, checkout or clean anything** — that uncommitted work is three lanes' live
increments and destroying it is the single worst thing available to you in this tree.
Specifically: **no `git stash`, no `git checkout -- `, no `git clean`, no `git reset`.**

## Operational constraints

- Limit any builds/tests to **2 threads**. Three lanes are live. **Do not generate load
  deliberately** — two run browser guards and load manufactures false reds for them.
- You need **no server and no port**. Do not run `just guards`; three ports are held.
- **Commit with `git commit --only <paths> -m …`**, and **`git add <file>` first** because
  your file is new — `--only <directory>` silently skips untracked files and does not say
  so. A bare `git commit` after `git add` commits the whole index and would bury three
  lanes' staged work in your commit. That has happened in this tree. **Do not push.**
- Use **`docs(#264): …`**.
- Cap yourself at roughly **40 minutes**. **Priority order: question 1, then 2, then 4, then
  the rest.** Question 1 is the spine and questions 3/5/6 are worthless without it. Report
  what you did not reach.

## How to report

Append **once**, at the end, in a single shell append (`cat >> …`), never by rewriting the
file, because other agents append concurrently:

`.dreamwork/inbox.md`

It must state: the document path; **your incident count, split into actual damage versus
near-miss**; your derived lane/commit/multi-touched-file counts and whether they agree with
`dogfood-orchestration.md`; which of the four mechanisms you could not find an instance for;
your answer to question 6 in one sentence; and what you are not confident about.

If you have insight beyond the direct result, also write
`.dreamwork/dreams/2026-07-28-<hhmm>-<slug>.md` and say so.
