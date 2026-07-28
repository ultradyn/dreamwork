# Brief — correct the #263 artifact: its central claim is wrong

Repo: `ud-dreamwork`. Worktree: **`.worktrees/gate`**, branch **`wt/gate`**, which already holds
`2aac68e` — the artifact you are correcting. Do not push, do not merge. **Never use `attn` under any
circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`. **Do not write
`.dreamwork/handoffs.md`** — the coordinator writes that line at merge time.

## What happened, and the good news is that a lane like you caught it

A previous `@grok` lane built `.dreamwork/review/263-second-gate.html` from
`.dreamwork/docs/briefs/263-second-gate-artifact.md` — good work, and **its own report is what
exposed the error**: it observed from the tree that **lane C's `C4` and `C5` are not in the tree**
while the plan's lane table lists them.

That means the artifact's framing — *A–D are landed, the second gate's condition is met, here are Q1
(open E), Q2 (open H), Q3 (#368 first)* — **is wrong at the top.** Lane C is plan increments 11–15
and only 11–13 exist. **A–D are not proved, and the gate correctly stays shut.** Verified
independently: `user_events/domain_files.py` has no whole-file marker search and no `rebaseline`, and
`test_user_events_domain_files.py` holds three tests.

The artifact **was never merged and he has never seen it**, so nothing is exposed. You are correcting
it before it ships, not after.

## The new shape, and the source of truth for it

**Read `.dreamwork/questions.md`'s top entry first** — the coordinator rewrote it at 16:35 and **it is
the specification**. Match the artifact to it; where the entry and this brief disagree, the entry
wins and you should say so in your report.

In outline, and check it against the entry rather than trusting this summary:

1. **The correction leads.** *"I told you the condition was met; it is not — lane C is 3 of 5."* With
   the mechanism, because it is the useful part: the ledger line said *"lane C DONE … 3/3 green"* and
   the coordinator read a count of what the lane built as the lane's scope. **Do not soften this and
   do not bury it below the status.**
2. **Lane status, honestly**: A 2/2 · B 8/8 · **C 3/5** · D 4/4 · F 4/4, with `C4 markers` and
   `C5 rebaseline` named as the remainder. Make `C` read visibly differently from the others — a
   *"3/5"* in the same visual treatment as *"4/4"* is the mistake that started this.
3. **Q1/Q2 (open E, open H) are NOT being asked.** Keep them present, demoted, and say **why** they
   are not being asked: the condition is unmet, and `C4`/`C5` are inside increments 1–19 which his
   `G1` already authorises, so they need no ruling and are being built now (a lane is on them as you
   read this). This section exists so he can see the gate is shut for a stated reason rather than
   silently.
4. **The one live question, promoted to be the artifact's primary ask: does `#368` (the modular split)
   land before lane E starts?** This is where the previous lane's best work is and **keep all of it**:
   the side-by-side split-first / serial-now frames, the SVG timeline, and the measured figures —
   `watch.py` at **9,688** lines against the plan's stale 8,647, and **6 of 6** lane-E production
   increments touching it. Recommendation stays **split first**.
5. **The withheld boundary stays exactly as prominent as it is.** Lane G (30–33) withheld regardless,
   increment 18's purge and increment 19's PostgreSQL half `UNPLACEABLE`, no live-target migration.
   Add the current truth: **the second gate is shut**, so E and H are withheld too.
6. **The evidence spine stays, and it is the part most worth keeping.** Lane D's hollow red found and
   consolidated; lane B's `B7` red that came back green and is **still an open hole**, not closed.
   Those are distinct proof stories and the previous lane was right not to flatten them into a green
   table. **Add lane C to that spine as a third kind of story**: a lane whose *record* was wrong
   rather than its code.
7. **One softening the previous lane found and got right, keep it:** `#371` is less urgent than the
   coordinator claimed — its **witness half landed** (`d33cc2f`, `short: true` + `got:`), so the
   server no longer records an interrupted body as complete. Only the *policy* half waits on `E1`.

Also fold the previous lane's other corrections, each of which the coordinator has accepted: lane B's
range reaches **`fec80be`**, lane C includes **`b5555e4`** (C3), lane F's code tip is **`4c918b2`**
(`2386345` is the ledger note), and the `200`-literal assertion count is **26** by `ast` where the
plan says 15 — **re-derive that one yourself** rather than taking it, and say what you got.

**Retitle accordingly.** It is no longer a second-gate ask; it is lane status plus the `#368`
sequencing call. Pick the title from the questions entry.

## Derive every number yourself

**Do not copy a figure from this brief.** Two of the coordinator's figures were wrong today and one of
them is why this brief exists. Recompute `watch.py`'s line count, the lane shas and dates, the test
counts per lane, and the `200`-literal count, and state the command for each in the artifact. **If
anything you measure contradicts this brief or the questions entry, say so in your report — that is a
finding, and the last lane's findings are the reason the record is now correct.**

## Done means all of these

1. **`.dreamwork/review/src/263-second-gate.html` updated** and
   `python3 review_artifact.py build .dreamwork/review/src/263-second-gate.html` rebuilds
   `.dreamwork/review/263-second-gate.html`. **`python3 review_artifact.py check` reports `current`**
   for it. Quote the output. **Keep both paths** — do not rename the files, only the title, or the
   link in the questions entry breaks.
2. **No claim anywhere that A–D are proved or that the condition is met.** Grep your own built output
   for `met`, `proved`, `all landed` and similar and say what you found — this is the one regression
   that matters and an assertion is not a check.
3. **Offline-clean, verified not asserted**: grep the built file for `http://` / `https://` outside
   link text and report the count.
4. **The `#368` comparison survives the edit intact** — frames, timeline and costs. If the retitling
   makes anything visually orphaned, fix it and say what moved.
5. **`transitions.md` applies to anything that appears, disappears, expands or collapses** in the
   artifact. There is no size floor on that rule in this repo. If you add a disclosure or a collapse,
   read that file first and reuse the existing idiom.
6. **Look at your own output** — desktop 1280 and mobile 390, above-fold and full-page. Give your own
   visual verdict on: does the correction read as the first thing? does `C 3/5` read differently from
   `4/4` at a glance? is the `#368` question findable without hunting now that it is the primary ask?
   Serve from a temp port **outside 39880–39899** (the previous lane used 41733 and stopped it) and
   stop whatever you start.
7. `python3 lint.py` clean, including `review/` reporting nothing stale. **Do not run `just test`** —
   four other lanes are live and guard ports 39890–39899 are held. Say you skipped it and why.

## Files

Yours: `.dreamwork/review/src/263-second-gate.html` and `.dreamwork/review/263-second-gate.html`.
**Nothing else at all** — `git status --porcelain` proves it at the end.

**Not yours:** `.dreamwork/questions.md` and `.dreamwork/tasks.md` (the coordinator is their only
writer — report exact lines instead), the plan (report corrections), `watch.py`, `test_watch.py`,
`watch-design.md`, `file-formats.md`, `lint.py`, `test_lint.py`, `user_events/*` — four other lanes
hold those.

## Practical

- 2 threads. `git commit --only <paths> -m 'docs(#263): …'` — **`--only`, never `git add -A`**: four
  other agents commit in this tree.
- **Push back with reasons if any of this is wrong.** Eleven lanes today have refuted something their
  brief asserted, every one was right to, and **the lane you are succeeding is the clearest example** —
  it refuted the premise of its own brief and the record is correct because of it. If you think the
  artifact should be scrapped and rebuilt rather than corrected, or that the `#368` question should
  not be primary, say so with your reasoning before building.

## Report

Say: the `review_artifact.py check` output verbatim; the result of your own grep for residual
condition-met language; every number you re-derived with its command, flagging contradictions;
whether you kept or rebuilt the `#368` comparison; your offline-clean count; and your visual verdict
on the three points in criterion 6.

---

## AMENDMENT 2, 2026-07-28 17:22 — lane C is now 5 of 5 and the gate's condition IS met

**Your worktree is `.worktrees/gate2`, branch `wt/gate2`** — the header at the top of this file names `.worktrees/gate`, which was removed after its lane merged. Ignore the header; use `gate2`. The previous artifact is already on `master`, so you are editing files that exist in your worktree.

**The page you corrected an hour ago is now wrong in the other direction, and this is the good kind of
wrong.** `C4` (`f85be1c`) and `C5` (`2cc3537`) landed at 17:21, verified by a merge gate that takes its
denominator from the plan's own increment table and asserts five rows. So:

**A 2/2 · B 8/8 · C 5/5 · D 4/4 · F 4/4 — his 05:43 condition *"until A–D are proved"* is satisfied,
and the second gate is now genuinely his to open.**

**Read `.dreamwork/questions.md`'s `#263` entry first — it was rewritten at 17:22 and it is the
specification.** It is deliberately short and ask-first. Match it; where it and this brief disagree,
it wins and you should say so.

What changes on the page:

1. **The headline flips.** It is no longer *"I told you the condition was met. It is not"*. It is now
   *"the condition is met, verified this time. Open it?"* — and **the correction stays visible below
   the ask**, because the record of having got it wrong at 16:24 is the reason he should trust the
   claim now. **Do not delete the correction; demote it.**
2. **Lane C reads `5/5` and joins the complete lanes**, with `C4 markers` `f85be1c` and
   `C5 rebaseline` `2cc3537` named. The `3/5` treatment goes; the row is no longer the exception.
3. **Q1 (open E) and Q2 (open H) are promoted back to live asks**, no longer "present, demoted". Q3
   (`#368` first) stays and keeps its frames and SVG timeline — the recommendation is unchanged and
   the measured figures (**9,688** lines, **6 of 6** increments in `watch.py`) still hold. **Re-derive
   them anyway** and report any disagreement.
4. **The evidence spine gains two things worth their space**, and both are the kind he is judging when
   he judges whether "proved" means anything:
   - **the gate's one failure was the coordinator's, not the lane's** — it counted every mention of
     `committed_lineage` (7 and 11 across two modules) and called it a duplicated drift detector; it
     is a **parameter name threaded through** and the membership test exists once, at `apply.py:166`.
     A substring cannot tell a duplicated predicate from a threaded argument.
   - **the lane disclosed that its own `C5` red is defence-in-depth**, not the sole mechanism: the file
     after `rebaseline` always sits at `max(committed)+1`, so a caller passing that as
     `reserved_successor` would see `APPLIED` through the successor half alone and the lineage red
     would be hollow. Its test passes `max(new_lineage)+1` so the lineage half is load-bearing.
   - lane B's `B7` hole is **still open** and stays visible. Lane D's hollow red stays. **Lane C's
     story is now a third kind: a record that was wrong while the code was fine, then completed.**
5. **The withheld boundary stays exactly as prominent**, updated: lane **G** (30–33) withheld
   regardless, increment 18's purge and 19's PostgreSQL half `UNPLACEABLE`, no live-target migration.
   **E and H are no longer in that list** — they are the ask.

**Criterion 2 still binds and is still mechanical**: `#ask` (or whatever carries the decision) must
measure `getBoundingClientRect().bottom < innerHeight` at 1280×900 and 390×844, **with the
does-the-page-scroll precondition asserted first**. Print both numbers per viewport. The coordinator
re-ran that check independently on the `#421` artifact and also **red-proved it** with a 1200px spacer;
expect the same here.

**Grep your own built output for `3/5`, `3 of 5`, `condition was met`, `is not` and report every hit
with its surrounding sentence** — not just a count. Five hits of *"condition met"* last time were all
inside retractions, so a count is not an answer and the polarity is not in the pattern.

**You are `@glm52`** (grok is still 401, `#423`). **The visual verdict is owed, not dropped** — say so
and do not guess at appearance.
