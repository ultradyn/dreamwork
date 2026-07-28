# Brief — #218: how long work actually takes, from data we already throw away

Repo: `ud-dreamwork`. Worktree: **`.worktrees/218`**, branch **`wt/218`**. Do not push, do not merge.
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not write
`.dreamwork/handoffs.md`** — the coordinator writes that line at merge time.

## The task, and why it is cheap

`#218` in the ledger: *"`ledger_series` already computes arrival/landing pairs and discards them;
render the median without a velocity score after provenance work."* The provenance work is `#217`,
landed `c1f5aaa` — so this is startable and has been for a day; nobody re-read it from the blocked
side, which is how `#420`'s census found it.

`watch.ledger_series` (`watch.py:7933`) builds two dicts on its way to the burndown — an id's first
mention time and its first appearance under `## Recently landed` — and returns only their **lengths**
(`arrived=len(arrived), landed=len(landed)`). **Every filed-to-landed duration in the project's
history is computed and then dropped on the floor.** Read that function's docstring before anything
else: both events are deliberately *first-seen* rather than current-contents, so they survive
grooming. That property is what makes a median over them meaningful, and it is the reason not to
re-derive the pairs somewhere else.

## The two traps, and the second one is his explicit constraint

**1. "Median" over what population?** An id in `arrived` but not `landed` is still open, and it has
no duration. So the median is over the *intersection*, which silently answers a different question
than the one a reader assumes: it is *"of the work that finished, how long did it take"*, **not**
*"how long does work here take"* — the still-open long tail is excluded, so the figure is
optimistically biased and gets more so the longer something sits. **The label must say which
question it answers, and the report must say the size of the population it was computed over.** A
median over 4 pairs and a median over 200 are different kinds of claim.

Also decide and state: are combined heads (`- **#138/#156**`, documented at `file-formats.md:244`)
one landing or two? `ledger_series` already counts them as two ids — a fact `#392`'s audit lane got
wrong and had refuted — so follow the function, and assert in a test that a combined head
contributes **two** pairs, not one.

**2. His words in the entry: "without a velocity score."** Take that literally. He does not want a
composite, a rate, a burn-rate, a "points per day", or anything that blends two quantities into an
index. One duration, honestly labelled. **If your design drifts toward a derived score, stop and say
so in the report rather than shipping it.**

## Design before pixels, and `#417` is next door

He filed `#417` five hours ago about this exact chart, verbatim: *"design needs to be considered
since we have a pretty good design now and it would be easy to make it worse."* That is about adding
a commits-per-period series, not your median — but **the caution transfers, and it is the reason this
brief is not "add a number to the chart"**. `#417`'s conclusion is that the burndown's current
quality is not to be traded for an extra series.

So: **the median is a figure in the burndown's surrounding copy or its meta line, not a new visual
element competing with the chart**, unless you can argue otherwise. Read `watch-design.md`'s burndown
contract and the existing figures around that surface first, and **reuse the idiom** — the chart
already states honest denominators and hatches unknowns (that is `#217`'s work); a median belongs in
that same voice. If you conclude it genuinely needs a mark on the chart, **say so in your report with
your reasoning and build the copy version anyway**, so the coordinator has the cheaper option in hand.

## Transitions are not optional here and there is no size floor

`CLAUDE.md`: *"Every transition on the UI obeys `transitions.md`."* If your figure appears, changes
value, or is absent-then-present across a data refresh, **that is a transition** and it obeys that
file — read it before writing any CSS, and reuse the existing arrival idiom (`dreamin` + the
`arrived` list, as the header project name does at `watch.py:~5483`) rather than authoring a second.

`transitions.md` opens with **how to check** one, and that matters more than usual: an end-state
assertion cannot fail on a motion bug, and neither can *"did it move"*. Follow what it says there,
including reduced-motion parity.

## Done means all of these

1. **`ledger_series` returns the durations** (or a median plus the population size — your call, but
   say which and why). Do **not** re-walk git a second time; the pairs already exist inside that
   function, and a second walk is a second truth.
2. **The figure is rendered**, labelled so it cannot be read as *"how long work takes"* when it means
   *"how long finished work took"*, and it states its population size where he can see it.
3. **The empty and degenerate cases are handled and tested**: zero pairs, one pair, and an even-sized
   population (which of the two middle values, or their mean? state it). `ledger_series` already has
   a *"says which kind of nothing"* test at `test_watch.py:1062` — **follow that existing idiom for
   the no-data case rather than rendering a bare `0` or a dash**, and say in the report which kind of
   nothing you distinguish.
4. **A combined-head test**: an id pair from `- **#A/#B**` contributes two durations. There is a
   model at `test_watch.py:1009` (`test_ledger_series_lands_every_id_in_a_combined_head`).
5. **A red-proof, from a `cp` snapshot**, `grep`- and `ast.parse`-confirmed before running: break the
   median (return the mean, or include unlanded ids as zero-duration) and watch a **named** assertion
   fail. **A green red-run is a finding, not a relief** — if the suite stays green with the median
   broken, say so plainly; the test is wrong and that is the more useful result.
6. **Assert the precondition your test depends on.** If the meaning of your fixture needs two
   durations to differ, or needs the population to be even-sized, **derive that at runtime and assert
   it** — do not encode a literal tuned to today's fixture. Three checks in this repo went hollow
   exactly that way and two were invisible in the guard output.
7. **`watch-design.md` updated in the same commit as the code** — that is this repo's standing rule,
   and `just audit-styleguide` measures whether it happened. Run it and quote the result.
8. **A capture guard only if the figure is a visual element.** If it is copy in an existing line, a
   unit test plus the existing surface guard is right and a new guard is noise — say which you
   concluded. If you do add one, register it in the `justfile`'s `DEFAULT_GUARDS` and red-prove it.
9. `python3 lint.py` clean, `python3 -m pytest test_watch.py -q -p no:randomly` passes, and
   **`just test`**. Do **not** pipe it — a pipeline returns the last command's status. Write to a
   file, read the file, quote the tail and the **real** exit code. The suite was fully green at 16:05
   (52 guards, 1009 pytest, 0 failures), so any failure is yours. **Guard ports 39890–39899 may be
   held** by another lane: check `ss -ltnp | grep 3989` first and say whether you waited.

## Files

Yours: `watch.py`, `test_watch.py`, `watch-design.md`, and the `justfile`'s `DEFAULT_GUARDS` line
**only if** criterion 8 earns a guard (plus `dev/capture/<name>.mjs` if so).

**Not yours:** `file-formats.md`, `lint.py`, `test_lint.py` — another lane holds all three right now,
so if your work wants a format documented there, **report it and let the coordinator sequence it**.
Also not yours: `status_sync.py`, `.dreamwork/review/` (a third lane is building an artifact there),
and `.dreamwork/tasks.md` / `.dreamwork/questions.md` — the coordinator is their only writer.

## Practical

- 2 threads. `git commit --only <paths> -m 'feat(#218): …'` — **`--only`, never `git add -A`**: three
  agents commit in this tree and a bare `git commit` sweeps their staged work into your commit under
  your message. A **new** file needs `git add <file>` first.
- **Push back with reasons if any of this is wrong.** Nine lanes today have refuted something their
  brief asserted and every one was right to. In particular: if you think the median belongs on the
  chart rather than in copy, or that the intersection population makes the figure not worth showing
  at all, say so with your reasoning **before** building — "this figure would mislead him" is an
  acceptable and valuable answer.

## Report

Say: the real `just test` exit code and how you got it; the median value and the population size it
was computed over on the live repo, with the command that produced them; which of the intersection /
labelling decisions you made and why; whether you put the figure in copy or on the chart and your
reasoning; your red-proof with the exact failing assertion; the `just audit-styleguide` result; and
which kind of nothing you distinguish for the no-data case.

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
