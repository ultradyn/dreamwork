# Brief — #263 lane C remainder: `C4 markers` and `C5 rebaseline`

Repo: `ud-dreamwork`. Worktree: **`.worktrees/263c`**, branch **`wt/263c`**. Do not push, do not merge.
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not write
`.dreamwork/handoffs.md`** — the coordinator writes that line at merge time.

Lane-owns: user_events/domain_files.py, test_user_events_domain_files.py

## Why you exist, stated plainly

Lane C was recorded **DONE, 3/3** in the ledger nine hours ago. Lane C is plan increments **11–15**.
`C1`, `C2` and `C3` landed (`3f1a6af`, `8c1bb60`, `b5555e4`, plus `4a773e2`); **`C4` and `C5` never
did.** `user_events/domain_files.py` has no whole-file marker search and no `rebaseline`, and
`test_user_events_domain_files.py` holds three tests.

`3/3` was true about what that lane built and silent about what it did not, and the coordinator read
it as the lane's scope — then told the human that the second gate's condition (*"until A–D are
proved"*) was met. It is not, because of you. **These two increments are the whole remaining distance
between the project and an honest gate ask**, which is why a P3-looking pair of increments is being
dispatched ahead of everything else.

Authority: his `G1` ruling authorises increments **1–19**, so both of these are already approved. You
are not near the gate. **Do not touch anything in lane E (increments 20–25), lane G (30–33) or lane H
(34–35).**

## The spec is in the plan, not in this brief

Read `.dreamwork/docs/plans/user-event-journal-implementation.md`:

- the one-line contracts at **lines 64–65** (`C4`, `C5`), and
- the detailed increments **`**14 · C4 markers**`** and **`**15 · C5 rebaseline**`** (around line 494),
  each of which names its test, its **red line**, and for the neighbouring increments its
  *must-not-fake*.

**Follow those rows; do not restate or reinterpret them here.** The plan's own note says copying a
spec into a brief makes the two drift. If a row is ambiguous or wrong, **say so in your report and
quote it** — that is a finding worth more than a guess.

## The one thing the plan cannot tell you, and it is the first thing to check

**Lane D landed after lane C stopped, and lane D's code may already contain part of `C5`.**
`user_events/apply.py` has `prove_applied`, `_is_valid_known_file` and a `successor_matches` with
generation, body-digest, receipt-id and adapter predicates — and `C5`'s named red line is
*"the `generation in committed_lineage or generation == reserved_successor` predicate"*, which sounds
like it may already live there.

So **before writing anything**: determine what of `C5` already exists, where, and what genuinely
remains. Two failure modes, both real:

1. **Building a second implementation** of drift detection in `domain_files.py` beside the one in
   `apply.py`. Two truths about the same fact is precisely what this design forbids elsewhere; if the
   predicate exists, `C5`'s remaining work is the **operator `rebaseline`** and its journalled import,
   not the detection.
2. **Reporting "already done"** because the predicate exists. `C5` also requires that `rebaseline`
   *validates, preserves bytes, mints a successor generation, and journals the import* — four things,
   and a predicate is none of them.

**State your conclusion and your evidence in the report before the criteria below**, and if you
conclude the plan's `C5` row is partly satisfied by `apply.py`, say which half and by what line.

## Red-first, and this repo's reds have a documented habit of lying

Both increments' red lines are named in the plan. For each:

1. **Write the test, watch it fail against current `master` behaviour, then make it pass.** From a
   `cp` snapshot, `grep`- and `ast.parse`-confirmed before running.
2. **A green red-run is a finding, never a relief.** If deleting the named red line leaves your test
   green, **say so plainly** — the check is wrong, and that is the more useful result. This has
   happened twice in this task alone: lane B's `B7` red stayed green (still an open hole) and lane D
   found a hollow red inside itself where the predicate lived in two places, so deleting the copy
   under test changed nothing. **If your `C5` predicate exists in two files, you have lane D's exact
   bug** — check for it deliberately.
3. **Name, in the report, the production line that would have to change for each test to fail.** If
   you cannot name one, there isn't one.
4. **`C4`'s precondition is written into the plan and is not optional**: *assert at runtime that the
   two fixtures actually differ in which section holds the marker*. A fixture with the marker in both
   sections makes the test vacuous and it will still pass. Do the same for anything else your test's
   meaning depends on — derive it and assert it, never a literal tuned to today's fixture.
5. **`C1`'s trap still applies**: valid fixtures must be produced **by `DomainFileStore`**, not
   hand-written. A hand-written file has a digest and lineage the test invented, and then the proof
   reads the test's own arithmetic.

## Done means all of these

1. **`C4`**: whole-file marker search across both literal `Open` and `Answered` sections, with
   `test_a_fold_between_sections_cannot_hide_a_marker` as the plan names it, including the runtime
   differ-precondition.
2. **`C5`**: external-drift detection *reconciled with whatever `apply.py` already does* plus an
   explicit operator `rebaseline` that validates, preserves bytes, mints a successor generation and
   journals the import, with
   `test_unjournaled_valid_successor_fails_closed_until_rebaselined`.
3. **Both red-proofs**, each with the exact failing assertion named, and the discriminating pair
   `C5`'s row calls for (deleting the lineage half fails the first assertion while the
   post-`rebaseline` assertion still passes).
4. **Two commits, one per increment** — `feat(#263 C4): …` and `feat(#263 C5): …` — because each is
   separately verifiable and the ledger will cite them separately. Do not land both in one.
5. `python3 -m pytest test_user_events_domain_files.py test_user_events_apply.py -q -p no:randomly`
   passes — **run `apply.py`'s tests too**, since you may touch shared ground — and `python3 lint.py`
   is clean.
6. **`just test`.** Do **not** pipe it — a pipeline returns the last command's status. Write to a
   file, read the file, quote the tail and the **real** exit code. The suite was fully green at 16:05
   (52 guards, 1009 pytest, 0 failures), so any failure is yours. **Guard ports 39890–39899 are held
   by other lanes**: check `ss -ltnp | grep 3989` first and say whether you waited.
7. **A one-line statement of whether lane C is now 5 of 5**, and if anything in increments 11–15 is
   still unbuilt, name it. The coordinator is about to quote you to the human; **be the version of
   this record that does not need correcting.**

## Files

Yours: `user_events/domain_files.py`, `test_user_events_domain_files.py`, and
`user_events/apply.py` + `test_user_events_apply.py` **only if** your `C5` analysis shows the change
belongs there — if it does, say so explicitly in the report, because no other lane is holding those
and the coordinator needs to know they moved.

**Not yours:** `watch.py`, `test_watch.py`, `watch-design.md` (a lane holds those), `file-formats.md`,
`lint.py`, `test_lint.py` (another lane), `.dreamwork/review/` (a third), and
`.dreamwork/tasks.md` / `.dreamwork/questions.md` — the coordinator is their only writer. Do not edit
the plan; report corrections to it instead.

## Practical

- 2 threads. `git commit --only <paths> -m '…'` — **`--only`, never `git add -A`**: four other agents
  commit in this tree and a bare `git commit` sweeps their staged work into your commit under your
  message. A **new** file needs `git add <file>` first. Lane A already lost a test file's attribution
  to exactly this.
- **Push back with reasons if any of this is wrong.** Eleven lanes today have refuted something their
  brief asserted and every one was right to — including the one that caught the `3/3` error that
  created this brief.

## Report

Say: your `C5`-versus-`apply.py` analysis and its evidence, **first**; both red-proofs with exact test
names and failing assertions; the production line that would have to change for each test to fail;
the real `just test` exit code and how you got it; whether lane C is now 5 of 5; and anything in the
plan's rows 14–15 you found wrong.

---

## AMENDMENT, 2026-07-28 17:02 — do NOT run `just test`; run `pytest` + `lint` and stop

**This supersedes the `just test` criterion in this brief.** Guards bind **39890-39899** and the
recipe hard-aborts when any port in the range is held — correctly, it is the `#203` trap. **Three
lanes are live and one of them holds 39899**, so at most one lane can ever run the suite and the
others wait or report a blocked one. `#419` waited, refused to force-kill the holder, and was right
to; the reaper refused too, and I confirmed the holder is a **live** run rather than a leak.

So the instruction was unsatisfiable at fan-out and it was mine — filed as `#424`, rec (b), which is
this:

- **Run `python3 -m pytest <your test files> -q -p no:randomly` and `python3 lint.py`.** Both must
  be green and both are yours.
- **Do not run `just test`. Do not bind any port in 39880-39899. Do not kill a process holding one.**
- **The coordinator runs the full suite once at merge**, which is the right owner because it is who
  merges. If your change *should* have a capture guard, still write and register it — just do not
  execute the guards recipe.
- **Say in your report that you skipped it and why.** That is correct here and not a gap; a lane that
  claims a green `just test` while another holds the range has claimed something it cannot have.
