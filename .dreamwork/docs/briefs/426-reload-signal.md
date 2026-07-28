# Brief — #426: an agent must survive its own files changing under it, or be told to reload

Repo: `ud-dreamwork`. Worktree: **`.worktrees/reload`**, branch **`wt/reload`**. Do not push, do not merge.
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are** at
the top — a lane report today was labelled `grok` when `glm52` was dispatched and I am tracking that.
**Do not write `.dreamwork/handoffs.md`** — the coordinator writes that at merge time.

## This is the human's own words, and it is a principle rather than a bug report

Verbatim, 2026-07-28 17:38:

> *"In general this should kind of be a principle of ours: the files on disk might be updated while agents
> are running, so they need to be able to continue running OR be explicitly told (via tooling or which
> files they read) that they must reload the skill and associated tooling like heartbeat, Monitor for user
> events, etc."*

**Two acceptable states, and there is no third:** either the running agent **continues correctly** across
the on-disk change, or it is **explicitly told to reload** the skill and its tooling. Silently running
against a half-updated tree is the state this forbids — and it is the default state today.

**Live evidence, which is why this is P1 and not hygiene:**

- A brief was amended mid-flight three times today, and each time *"has the lane already read it?"* had no
  answer available to either side.
- `SKILL.md` and `CLAUDE.md` are read once at session start, so a change to either reaches nobody already
  running.
- This session is running `watch.py` as a server from a tree that has taken **many** commits since it
  started — and earlier today it served a two-hour-old snapshot while a status file claimed it was current.

**Prior art in this repo, and it is the shape to copy:** `.dreamwork/run-mode` is re-read on **every tick**
precisely so an on-disk change reaches a running loop. It is the only file in the system with that
property. `dev/deploy_state.py` is the second half of the idea — it answers *"is the file right"* and
*"is the process running that file"* as two separate questions, using a `GENERATION` stamp set at import
and re-set on every `os.exec`, because a pid and a process start time both survive `exec` and cannot tell
those apart.

## Your task is a DESIGN plus ONE safe increment, not the whole principle

The principle is large and touches every agent surface. Do **not** try to land all of it.

**Deliverable 1 — the design**, as `.dreamwork/docs/reload-signal-design.md`, with a `doc-map.md` row:

- **The signal.** What a running agent checks, and how cheaply. Version, content hash, mtime, commit —
  argue the choice. It must distinguish *"my tree changed"* from *"the change affects what I read"*, or
  every commit anywhere becomes a reload demand and the signal gets ignored, which is worse than absent.
- **What reads it, and when.** Per-tick (like `run-mode`), on demand, or at increment boundaries. Name the
  actual read sites in this repo.
- **The defined action on mismatch**, per surface: the loop itself, the heartbeat monitor, the
  watch-events monitor, the `watch.py` server, and an in-flight lane. These differ — a server can
  `os.exec` itself, a lane in the middle of an edit cannot.
- **The relationship to `#263` lane H** (*"mixed-version fail-closed before witnessing"*), which solves
  this same problem for the journal. **Decide whether they share a mechanism before either is built
  twice** — that is the entry's explicit question. **You must NOT build lane H, or lanes E or G of `#263`:
  that gate is the human's to open and the ask is open on his desk.** Design only, and say plainly which
  parts wait on that gate.
- **What is NOT worth doing**, with reasons. A design that recommends everything is not a design. If part
  of the principle is better served by convention than mechanism, say so — the strongest possible outcome
  here is a small mechanism plus a named convention.

**Deliverable 2 — one increment that stands alone**, chosen by you and defended in the report. It must be
verifiable, committable, and useful even if nothing else in the design is ever built. Candidates, but your
judgement governs:

- A `dreamwork-version` / identity signal a running agent can read and report.
- Extending the per-tick `run-mode` read to cover a broader "reload needed" flag.
- Making one concrete surface detect and report its own staleness (the `watch.py` server already has
  `GENERATION` and `serving_report` — note that `#425`'s lane flagged `serving_report` and root
  `deployed.py` as reading **behind** for a self-hosted tree once `watch.py` is a symlink, and left both
  for `#368`).

**Deliverable 3 — a review artifact**, `.dreamwork/review/src/426-reload-signal.html` built with
`python3 review_artifact.py build`, IF and only if your design has a decision that is genuinely his to
make. The repo's rule is that every request for a ruling ships a self-contained artifact. If your design
has no such decision, **say so and skip it** — a decoy ask is worse than none. If you do build one:

- It must carry an **`#ask`** element wrapping the actual decision, with the accepted answers spelled out.
- Check it with `node dev/capture/above_fold.mjs .dreamwork/review/426-reload-signal.html` — **note a live
  lane owns that file, so run it, do not edit it.** If the fold constant is mid-change under you, say so
  rather than working around it.
- Report the exact `questions.md` entry text you want filed. **Do not edit `questions.md`** — the
  coordinator is its only writer.

## Done means all of these

1. **The design doc exists**, answers all five bullets above, and each recommendation names what it costs
   as well as what it buys.
2. **The `#263` lane H relationship is decided and stated** — shared mechanism or not, with the reason.
3. **One increment landed**, with a test or guard that has been **red on the bug first**. **A green
   red-run is a finding, never a relief** — if the check passes with the defect reinstated, the check is
   wrong and that is the more valuable result. **Name the exact production line whose change fails it.**
4. **Assert the precondition your check depends on.** If its meaning needs two values to differ, derive
   both at runtime and assert the gap; a literal tuned to today's tree is a check with an invisible expiry.
   This has bitten here repeatedly, including twice today.
5. **`file-formats.md` states the shape of anything the loop writes and a tool parses**, in the same
   commit — the standing rule, checked by `lint.py`.
6. **`python3 lint.py` clean** and **`python3 -m pytest -q -p no:randomly` passes**. **Do not run the full
   `just test`** and bind nothing in 39880–39899.
7. **Do not restart, `pkill` or redeploy the live dashboard on :35110**, and do not stop or restart the
   heartbeat, the monitors, or the loop — a subagent never touches loop machinery; if you believe it
   should stop, say so in the report and the human decides. Note `just deploy`'s `pkill -f` matches any
   process whose command line merely *mentions* the snapshot (`#431`); the same self-match bit twice more
   today, once from a **comment** containing the pattern. Build process patterns from parts.
8. **`transitions.md` binds with no size floor** if you touch anything on the UI; state whether you
   introduced a gesture.

## Files

Yours: `.dreamwork/docs/reload-signal-design.md` (new), `.dreamwork/docs/doc-map.md`, and — for your one
increment — whichever of `watch.py`, `test_watch.py`, `file-formats.md`, `dev/deploy_state.py` it needs,
plus `.dreamwork/review/src/426-reload-signal.html` and its build output if you ship an artifact.

**Not yours:** `dev/capture/above_fold.mjs` and `dev/capture/devoverlay.mjs` (**a live lane holds both** —
you may *run* `above_fold.mjs`, not edit it), `justfile`'s `DEFAULT_GUARDS` (same lane),
`review-artifact.template.html` (touching it re-stamps 23 artifacts and 12 cannot be rebuilt — that is
`#436`), `lint.py`, and `.dreamwork/tasks.md` / `.dreamwork/questions.md` — the coordinator is their only
writer, so report exact lines instead.

## Practical

- 2 threads. `git add <newfile>` then `git commit --only <paths> -m 'feat(#426): …'` — **`--only`, never
  `git add -A`**: another agent commits in this tree and a bare `git commit` sweeps its staged work into
  yours. `--only <directory>` silently skips untracked files inside it.
- **Commit before you finish.** A lane today did 24 turns of correct work and exited without committing;
  it had to be recovered by hand from the dirty worktree.
- **A commit that changes what an existing install must do carries a trailer**: `Migration:`, `Feature:`,
  or `Needs: config|consent`. A reload signal is very likely `Migration:` or `Feature:` — decide.
- **Push back with reasons if any of this is wrong.** Every lane today that refuted its brief was right
  to, and the most valuable one **refused** what it was handed: given four specimens described as defects,
  it measured them, found all four legitimate, and declined to build the check — then red-proved the
  refusal so that rebuilding it fails a test. If the right answer here is "the mechanism is not worth it,
  the convention is", that is a complete and welcome answer.

## Report

Say: which model you are; the design's answer to each of the five bullets; the lane-H decision and its
reason; which increment you landed and why that one; the exact production line whose change reds your
check; whether you shipped an artifact and, if so, the `questions.md` text you want filed; the commit
trailer you chose; and confirmation you did not run the full `just test`, touch :35110, or go near the
files a live lane owns.
