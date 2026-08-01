# BRIEF — #778: the guard a lane cannot discover, named where the lane will actually look

Worktree: /home/xertrov/.llm-general/skills/ud-dreamwork/.worktrees/glm-778guards
Branch: glm-778guards
Base sha: e195f901
Repo root: /home/xertrov/.llm-general/skills/ud-dreamwork
Coordinator inbox — ABSOLUTE path, append your completion summary here when you finish: /home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md
  (This is `inbox.md`, NOT `.dreamwork/handoffs.md` — the standing contract's prohibition on
   writing handoffs.md still binds and this line does not override it.)
Lane-owns: briefs/boilerplate.md, dev/repo_wide_guards.py, test_repo_wide_guards.py

**Task:** `python3 dev/ledger.py get 778 --ledger /home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/tasks.md` — read the entry in full. It is measured and it already contains the entry criterion and the honest ceiling. This brief does not repeat it; it adds what I measured afterwards.

## What this is, and what it is emphatically not

Two merges were reverted inside one hour today. Both lanes did **good work** and **obeyed
the rules**: they ran targeted subsets (26 and 107 tests, all green) exactly as
`briefs/boilerplate.md:214` instructs, and my merge gate caught both. **The system worked
as designed.** This is not a case for making lanes run the whole tree — that ruling is
sound, a full sweep costs ~175s for 2648 tests, and N lanes re-proving it is N−1 wasted
suites (#666).

The gap is structural and no `Lane-owns:` line can close it. A **repo-wide** guard asserts
a rule that spans the repo, so it is not a test *of* the lane's files:

- `test_no_raw_connect.py` governs every production source. #776's lane added a raw
  `sqlite3.connect` in `dev/dispatch_lane.py:159`. Reverted at `8c6481fb`.
- `test_ledger_cli.py::test_the_map_covers_every_verb` governs every parser verb. #645 i9
  added seven verbs with no `_VERB_ARGV` rows. Reverted at `5f1ea764`.

"Run the tests for the files you touched" reaches neither. **I have been patching this by
hand** — naming the guard in each brief when I happen to remember — and today I forgot
twice. That is the thing to fix.

## The measurement that decides the design

**I measured the obvious implementation and it fails.** A heuristic of "a test that
enumerates repo files" (`git ls-files`, `rglob`, `os.walk`) matches **six** files here:

```
test_dreamhub.py  test_guard_evidence.py  test_client_dist.py
test_no_raw_connect.py  test_user_events_cli.py  test_lint.py
```

`test_lint.py` alone collects **563 tests**. Sweeping those six in would push the
always-run set from ~1% of the tree toward a large fraction of it — which is how the :214
ruling gets quietly reversed by a helper that was meant to support it (#707: every widening
multiplies false attribution).

For contrast: the two guards that would have caught **today's** reverts,
`test_no_raw_connect.py` + `test_ledger_cli.py`, collect **37 tests in 0.43s** — against
2648 in ~175s. That is the budget. Roughly **1%**. Treat a design that exceeds a few
percent as having failed its own premise, and say so rather than shipping it.

So the entry criterion from the ledger entry is doing real work and it is **narrower** than
"enumerates repo files": *a guard qualifies only if it asserts a property over a population
a lane cannot enumerate from its own diff.* Note the consequence — **the unit may be a test,
not a file.** `test_lint.py` contains a few genuinely repo-wide checks among hundreds of
unit tests of individual checks. If node-id granularity is what the criterion honestly
implies, use it and say why; if you judge node ids too brittle to maintain, argue that and
take the file-level cost explicitly. **Do not pick silently.**

## The shape I recommend, and the part you must not get wrong

A hand-maintained list is the obvious answer and it has the obvious defect: it goes stale
the day someone adds a repo-wide guard and does not know to register it, and a stale list
reads exactly like a complete one (#671). A purely derived list is the other extreme and
the measurement above shows the derivation is too blunt to trust.

**So: a registered set, plus a check that the registry cannot silently miss a new
candidate.** The registry is authoritative for what lanes run; the detector's job is only
to say *"this looks repo-wide and is not registered — classify it."* An unclassified
candidate is a finding to report, not a member to add (#702). That way the list stays
small and deliberate, and it cannot rot in silence.

Land the always-run set in `briefs/boilerplate.md` **next to the :214 targeted-subset
paragraph**, not in a separate section — the whole failure was that the instruction lived
somewhere the lane was not looking. It must read as *additive to* the targeted subset, and
it must not weaken :214's wording; that ruling stands and your text should say so.

## The false-green, named

1. **A registry entry naming a test that does not exist** (renamed, deleted, moved) must
   fail loudly. A guard set that resolves to nothing must never read as "all guards passed"
   — that is #671 verbatim, and it is the most likely way this decays.
2. **A registry that is complete today and silently incomplete tomorrow.** Your detector
   exists precisely for this; if it cannot flag a newly-added repo-wide guard, it is
   decoration.
3. **Do not let the set grow by default.** Every addition needs the criterion argued. State
   in your report what the criterion **admits today**, what it **excludes**, and every guard
   you **could not classify** — the entry asks for this explicitly.

## Red-proof

- **Direction 1:** add a new repo-wide guard (or rename an existing one out from under the
  registry) and confirm the check reds, naming the specific guard. Then delete a registered
  test entirely and confirm you get a loud failure rather than a vacuous pass.
- **Direction 2:** the detector must stay **silent** on an ordinary module test that happens
  to glob a couple of files — that is the widening the measurement above warns about. Show a
  concrete healthy input it does not fire on (#755). If your detector flags `test_lint.py`
  wholesale, you have reproduced the trap rather than avoided it.

- Run `python3 dev/lessons_index.py --act red-proof` before any injection.
- **Never `git checkout` to restore an injection** (#349) — snapshot lane-privately via
  `dev/lane_scratch.py snap` (or `dev/redproof.py`, which subsumes it), restore by `cp`,
  verify with `cmp`. Snapshot the FIXED file, not the pre-fix one (#608).

## Lessons selected for this task

- **#671 — a check that examined nothing must not read as passing.** A registry resolving
  to a deleted test; a stale list that looks complete.
- **#707 — every widening multiplies false attribution.** The six-file heuristic, measured.
- **#755 — a check that fires on a healthy input is worse than no check.** Why the detector
  must be silent on ordinary module tests.
- **#702 — report what you cannot classify.** Unclassified candidate guards are findings,
  not members.
- **#651 — a name must not imply more than it proves.** The entry's own ceiling: this
  catches cross-cutting RULES, not a lane breaking an unrelated feature. Your text must not
  imply the coordinator's full sweep is now optional. It is not.
- **#440 — one supported way.** One registry, one place a lane reads it.

## Run these, explicitly

```
just pytest test_repo_wide_guards.py test_dispatch_lane.py test_guard_preflight.py
```

`test_dispatch_lane.py` and `test_guard_preflight.py` both read `briefs/boilerplate.md`
(`dev/dispatch_lane.py` validates the standing contract against it verbatim), so editing
that file can break them — and no owned-files list would point you there. **That is this
very task's bug, and you are its first victim.** Note that in your report.

**And run your own always-run set against your own change** — if the thing you built does
not apply to you, it will not apply to anyone.

## Bars

**Measured in your worktree at dispatch, 2026-08-01, base `e195f901`:** worktree lint
**25 warnings**; `test_no_raw_connect.py` + `test_ledger_cli.py` collect **37 in 0.43s**;
full tree is **2648 in ~175s**. Re-measure and quote what *you* got.

- Count tests by collecting, not by grepping `def test_`.
- **Two other lanes are live.** `glm-645i9b` owns `dreamwork_db/`, `dev/ledger.py`,
  `test_ledger_cli.py` and is running the full browser-guard suite. `cx-777reanchor` owns
  `.dreamwork/docs/**/*.md`, `lint.py`, `test_lint.py`. **You may READ `test_ledger_cli.py`
  and `test_lint.py` to classify their contents — that is central to your task — but do not
  EDIT either.** If your registry needs a node id from `test_ledger_cli.py`, reference it;
  do not restructure it.
- Machine load is elevated from the guard sweep — if something is flaky on timing, say so
  rather than retrying until green. Limit to 2 threads.
- Do not bind `:35110` or `:35113`.
- Rebase onto master before you finish and resolve conflicts yourself; master will move
  under you (`glm-645i9b` is due to land).
- Do not use `attn`.

# Lane brief boilerplate — appended verbatim to every dispatch

This is the standing half of a lane brief. The coordinator writes a task-specific head
and concatenates this file after it. It lives in the repo rather than in a session
scratchpad because it is corrected by lane dogfood reports several times a night, and
every one of those corrections used to die with the session that made it (`#703`).

**Corrections belong here.** When a lane reports that a rule was wrong, missing, or
unreachable, fix it in this file in the same increment that acts on the report. The duty
runs both ways: when `SKILL.md` gains a lane-facing rule, reflect it here too — a rule
stranded in the coordinator's doc never reaches a lane (`#400`), and no string-match check
can bind "a rule is stated" (a token is not a statement, `#699`), so this rotation carries it.

## Standing rules — these bind you, and this loop has been burned by every one

**Authority and contradictions.** A task-specific instruction overrides this standing
contract only when it says explicitly that it is an override and names the rule it replaces.
An unannounced disagreement is a brief defect: follow this standing contract and report the
conflict in your DOGFOOD REPORT. If two instructions inside the task-specific head disagree,
do not guess which one the coordinator meant. Do only what both readings authorise; when the
disagreement controls whether a deliverable should exist, measure first and build it only if
both readings authorise the build. Report the contradiction plainly. This rule chooses a safe
lane action after a defective dispatch; it does not make the contradictory brief correct.

**Base state.** You branched from the tip of local `master` **at dispatch time**. Do not trust
any literal sha in a brief as current — master moves while you work, and a lane rebasing an
hour later found master three commits past the sha its brief named. Read it yourself:
`git rev-parse master`. (Never a commit count either: a count rots into a comforting number —
a `#655` brief said "one commit ahead" when it was 32 behind, and the merge ERRORed exactly
as that hid.)

**When this brief names a defect site, treat it as an EXAMPLE, not the inventory.** Before
declaring the fix done, check the sibling constructs in the same unit — the same object, the
same function, the same string. On `#690` the brief named one backticked path in a two-line
body; the *same body* backticked a second token, and fixing only the named one left the bug
alive while still passing a naive string assertion. The lane caught it only by extending the
check on its own initiative. Extend it on yours.

**Read resulting state before relying on a command.** After a command mutates state or supplies
an inventory that controls the next action, immediately read the authoritative result: merge
ancestry/HEAD, the stored ledger entry, the worktree list, or the complete target population.
Bind any success report or follow-on write to the producing command's status, not to a later
pipeline element or whatever state was already present. A plausible command spelling is not
evidence that its intended behaviour occurred.

**DO NOT WRITE TO `.dreamwork/handoffs.md` — specifically, do not append any hand-off line
there. That file has a single writer and it is not you** (the lesson *"Both wordings of the hand-off instruction are wrong, and I
found the second by hitting it twice"*, and `#687`). It is an ownership rule reached after the
alternatives were tried and failed twice in twenty minutes: a lane appending to `## Pending`
while the coordinator edits `## Folded` produces a content conflict on *every* merge. **You
write your completion report to the coordinator inbox named in the task-specific head and
nothing to `.dreamwork/handoffs.md`; the coordinator writes the hand-off line from your report at
merge.** (SKILL.md briefly said otherwise; `#687` reconciled it at `dc3ac7c3`, so the two now
agree and neither needs to be believed over the other.)

**Rebase before you report, in that order.** Master moves while you work. Before writing the
sha into your report, rebase onto **the LOCAL `master` branch — not `origin/master`, which is
behind it** (a lane that read "master" as `origin/master` replayed 832 commits into a conflict;
check with `git rev-parse master` vs `origin/master`), and resolve conflicts *here*, with your
context —
the coordinator resolving them blind is how `#667` went wrong. Order matters: **a rebase
rewrites shas**, so a sha captured first names a commit that no longer exists.
Append-only files (`.dreamwork/handoffs.md`, `.dreamwork/lessons.md`) conflict at EOF and
keep-both is nearly always right. After ANY hand resolution, grep line-anchored for all four
diff3 forms:

    grep -nE '^(<{7}|>{7}|\|{7}|={7}$)'

Note the `$`, which only the `=` arm carries and which is load-bearing: the other three
markers are followed by a branch or base name so they cannot be anchored, while `=======`
stands alone — and an unanchored `={7}` matches any rule-of-equals divider of seven or more
characters, which false-positives on this repo's own prose and test files. This repo
discusses conflict markers in prose (the lesson *"A conflict resolver that greps for three
marker forms misses the fourth"*), so a substring test is
wrong by construction.

If the rebase is genuinely hard, **hand back the analysis instead of a bad resolution** —
that is a legitimate outcome, not a failure.

**Red-proof both directions. This is the one that catches real defects.**
- *Direction 1*: inject the real defect and watch your check go red **on the discriminating
  failure message** — not on a red count. A red for the wrong reason is indistinguishable
  from a right one in a `-q` summary.
  **Use `dev/redproof.py`; it owns the snapshot/restore protocol** (`#683`):

      python3 dev/redproof.py begin <path>     # snapshot the file as-is, arm the entry
      …sabotage it, run your check, watch it go red…
      python3 dev/redproof.py restore <path>   # record the injected content, restore, verify
      python3 dev/redproof.py check            # hand-off gate — run before you report, quote it

  **The snapshot is of the file BEFORE sabotage; the real fix is applied AFTER
  `restore` returns it — so the restore can never undo the fix.** If you snapshot
  the pre-fix file and the fix is already in it, restore returns the fixed file;
  if you ever snapshot the pre-fix file and then restore expecting the fix, you
  have silently undone your own work and `cmp` will certify the wrong file (`#608`).

  **Run `check` before reporting and quote its output.** It REFUSES if any injection is left
  unrestored, which is the failure nothing could previously detect: an injection is by
  construction a small plausible edit to real code, so a lane that gets absorbed in writing its
  report and commits has shipped a deliberate defect with a green-looking report attached.
  It also fails closed — an unreadable registry or a missing snapshot is a fault at exit 2, not
  a pass — and distinguishes that from the calm zero of nothing registered (`#136`, `#671`).

  **Keep committing while sabotaged — that rule is unchanged — and let `check` catch what it
  costs.** A clean tree is not a clean branch: `check` also scans every commit this branch adds
  to its base and refuses if one still holds the recorded injection (`#710`), because a merge
  makes that defect reachable from master forever. If it refuses, say so in your report and name
  the commit: the fix is for the coordinator to **squash this one branch** at merge, not for you
  to have committed less. This is a tool that will refuse you, not a rule you have to remember.

  Using the tool also discharges two rules you would otherwise have to remember. It places
  snapshots **lane-privately** (`#652`: the session scratchpad is shared by every live lane, and
  `#703` records a lane's first snapshot landing in a directory already holding another lane's backups of
  `watch.py`, `router.js` and `test_watch.py` — two lanes clobbering each other's restore point
  is the exact failure snapshots exist to prevent), on `~/.cache` (btrfs) rather than `/tmp`
  (tmpfs, the substrate half of `#634`). And because `begin` snapshots at the moment you arm each
  injection, it cannot snapshot a file before later edits and then silently lose them on restore.
  **Never `git checkout` to restore an injection** (`#349`, a repeat offence here); `restore`
  copies from the snapshot and verifies.
- *Direction 2*: construct an input where the thing you are checking is **genuinely broken
  but your check still passes**. Report it even if you cannot close it. If none can be
  constructed, say why not. One-directional red-proofing is exactly what let three
  false-greens through on `#596` and three more on `#655`.

**A guard or test named as evidence must name the assertion that would fail.** On `#655` a
guard was reported PASS as evidence with no assertion about the feature at all and no journal
in its fixture — its PASS was guaranteed before the work started. If you cite a check, say
what it would catch.

**Every issue number you cite must be opened and read**, with the relied-on line quoted into
your report. Confidently-wrong citations are the characteristic failure mode here. **The bare
`dev/ledger.py get <id>` form REFUSES from a worktree** — the store is gitignored so it cannot
travel. Use this exact invocation:

    python3 dev/ledger.py get <id> --ledger /home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/tasks.md

(The refusal does name the working form, so this costs one wasted call rather than a wrong
citation — `#667` built that gate deliberately. This just saves you the call.)

**Cite a lesson by its exact bolded title, not by `lessons.md:<line>`.** Confirm the title
resolves to exactly one lesson head with `grep`; zero matches means it drifted, and two matches
are ambiguous. A line coordinate can silently move to unrelated content while looking valid.

**The path you invoke is the INTERPRETER; `--target`/`--ledger` is only the SUBJECT.** A
brief head may cite a tool by its skill-dir path
(`python3 /home/…/skills/ud-dreamwork/<tool>.py`) — that is a symlink into the MAIN
checkout, so it runs the code you have NOT fixed. If your task edits a tool the brief tells
you to run, invoke the WORKTREE'S copy (`python3 dev/<tool>.py`), which runs your fix. The
one legitimate use of the skill-dir path is the pre-fix BASELINE — running the unfixed tool
deliberately to capture the before state (`#592`, `#607`). That is a technique, not a
mistake; a rule that bans the skill-dir path would forbid it.

**Volume**: land your change as the fewest lines that carry the meaning. A correct
change that triples a doc's length gets reverted by the next reader.

**Shipping an experiment?** Its gate is a file: its own tracked `.dreamwork/<name>`, absent
means off, plus a `file-formats.md` row — the `watch-tint`/`run-mode` family. Do not go
looking for a flag system; `#700` measured that there is none and `SKILL.md`'s Guardrails
now carries the rule.

**Choosing between rival options?** Use IGC — `./igc-method.md`, **in your own worktree**. It
is checked into this repo, so the worktree-local path always resolves; do not go looking under
`~/.claude-p/` (a `ccc` lane reported that path unreachable from its harness).

**Mechanics.** `git commit --only <paths>` — **never `git commit -a`**. Run `git add -N` for
new files first so `--only` can see them. **Never merge, never push** — the coordinator does
both. Never use bare `git stash`/`git stash pop`: the stash stack is shared across worktrees
and you would pop another lane's work. `--only` stops you sweeping OTHER files from the index,
but it commits the path's **full current content** — so if another agent has an uncommitted
edit to the **same** file, your `--only` sweeps their edit too (`#624`). That agent's own
`--only` then reports `nothing to commit, working tree clean`, which reads as failure but
means "your write was already committed by someone else." **If you see `nothing to commit`
after writing to a file, CHECK whether your content is already on master (`grep` for your
line) before re-appending — re-appending creates a DUPLICATE the coordinator folds twice.**
(For `.dreamwork/handoffs.md` specifically this is moot: you do not write it, `#687` made the
coordinator its single writer. The rule is for any other shared file.)

**Name the task id in every commit subject, in the form `verb(#NNN): <subject>`** — e.g.
`feat(#577):`, `test(#577):`, `fix(#688):`, `docs(#700):`. The verb must be one of
`merge fix feat close perf refactor guard docs test design`.

**The form is not cosmetic and `#NNN: <subject>` DOES NOT WORK.** `dev/ledger.py sweep` is how
the coordinator learns your work landed, and `#404` makes it the primary landing-discovery
route on the grounds the id is in the subject "by construction". Its pattern is
`^(?:merge|fix|…|design)\((#\d+)\)` — anchored, and it requires the parens. Measured:
`'#704: skip the collision test'` → **MISSED**; `'design(#700): the gate is a file'` → matched.
So a subject that names the id in the wrong shape is exactly as invisible as one that omits it,
and it is worse, because it *looks* compliant. This paragraph said `#NNN:` for about half an
hour on 2026-07-31 and was wrong; a `#700` lane measured it against the actual regex and
reported it (`#707` tracks widening the pattern, which is the better long-run fix — until then,
write the form the tool can read).

**COMMIT INCREMENTALLY. You can be killed without warning, and uncommitted work is lost.**
This is not the `#686` rule ("commit before you stop") — it is stronger, because stopping is
not always your decision. Four lanes were terminated mid-flight on 2026-07-31 with no error in
any log; one had finished its measurements, chosen its design, and written the change, and had
committed nothing. Its diff survived only because the coordinator salvaged it from the
worktree by hand before removing it. **The moment you have something coherent — a measurement
worth keeping, a working change, even a partial one — commit it.** A commit that says "WIP:
measured X, Y still open" is a result. An uncommitted worktree is a coin flip. Amend or add
commits freely afterwards; the coordinator squashes nothing and reads your history.

**Commit the deliverable, not just the code.** The inbox is not lossless (`#404`/`#392a`
landed work whose report never arrived), so whatever must survive — an audit, an analysis, a
design doc — goes into the commit, and the inbox report carries the richer context. A lane
cannot land work without committing; that is the one channel that cannot be skipped.

**Do NOT touch `:35110` (the live dashboard) or `:35113` (dev).** Bind ephemeral ports only.
Limit builds and tests to **2 threads**.

**Do NOT use `attn`.** You report to the coordinator; the coordinator decides whether to ping
the human. This is absolute.

**Run a targeted subset, not the whole tree — the coordinator owns the single full merged-tree
sweep.** `just pytest <the test files your change touches>` is your verification; the merge gate
already re-proves the whole tree once, so N lanes each re-proving it is N−1 wasted suites under
exactly the load this loop has measured (`#666`). Name the files you ran. **This is
resource-aware, not just wall-clock-aware**: the scarce resource is resident memory, not CPU —
measured, the fleet was 8.5% of CPU on a ~70%-idle machine while swap sat at 52 GB of 60. So a
non-UI lane (docs, tooling, ledger work) can run concurrently with a guard sweep; a
browser-binding lane cannot, because one Chromium costs more than several pytest lanes together.
**A task-specific request for a bare full-suite run is therefore ignored unless it explicitly
names this rule and says why it is overriding it.**
The recipe first prints how many other suites and browser processes are live, so you can see
which situation you are in before adding your own load.

**Lane bars are command-, snapshot-, and interpreter-relative.** Run `python3 lint.py`: require
NO ERRORs and inspect every WARN message against the measured baseline. A worktree may add
`tasks.md` ledger-absent/zero-entry, `status.json`-absent, and `ledger checks`-examined-nothing
WARNs because those artifacts do not travel. To inspect live data with the WORKTREE interpreter,
use `python3 lint.py --target /home/xertrov/.llm-general/skills/ud-dreamwork`; a stale interpreter
need not reproduce current output.

When a brief asks for real-path parity, freeze the subject (a read-only backup, copied fixture,
or pinned revision) and pin the baseline interpreter revision; vary only the intended interpreter
change. Report raw live readings as context, not as the proof. Otherwise concurrent movement can
make an honest "not identical" look like the lane's regression — or tempt it to round the
difference off to satisfy an impossible brief.

Likewise, judge targeted pytest by its own before/after collected count; a whole-repo total quoted
in a moving brief head is not that run's bar.

**Filesystem measurements need a measured substrate and an exact positive control.** Use
`M="$(dev/lane_scratch.py measure)"` as the one lane-private location; ask the kernel for its
filesystem type (`stat -f` / `findmnt`), never infer it from `/tmp`, the repo, or any path prefix.
Before believing a negative mtime result, set up a subject under `$M` and run
`dev/lane_scratch.py require-mtime-change "$M/<subject>" -- <the positive-control command>` with
the **same mmap/write mechanism** as the real probe. Success is silent; `UNSUPPORTED` means the
control ran without advancing mtime, and `UNDETERMINED` means it did not judge. A `touch` control
does not validate an mmap probe, and non-mtime phenomena need their own positive control.

**Verification gate.** `just test` runs pytest + `lint.py` + browser guards. **Do not run the
full `just guards`** — several lanes are live, and a *multi-server* browser guard under high
load returns a WRONG answer rather than a slow one (it dies before judging: `"the guard threw
before finishing its checks"`, the `#471` did-not-judge sentinel, which gates nothing but
reads like a failure). Run only the specific guards your change bears on, say which, and
quote the load figure each one prints.

**Measured load figures, so you do not have to guess a threshold.** The failures were at load
**38-42** (`health`, which spawns four servers at once). Single guards judged correctly at
**22.79**, and `health` itself ran clean end-to-end at **23.72** — all 20 assertions PASS.
So load in the low-to-mid 20s is fine; do not refuse to run on that. A `#690` lane declined
at 21-25 against an over-cautious threshold and handed back a diagnosis with its headline
evidence missing, which the coordinator then had to produce at the gate.

**But know what that number is.** Linux load average counts uninterruptible-sleep processes,
so it conflates *blocked on swap-in* with *running* — the coordinator quoted it three times as
evidence of CPU contention when the machine was ~70% CPU idle and the real constraint was
memory (`#666`, third note). The thresholds above are still the right empirical guide, because
they were measured against the same conflated figure. Just do not reason from load to "the CPU
is busy": if you need the cause rather than the reading, decompose it before attributing.

**A single-process static probe is explicitly authorised at any load** — one Chromium, no
motion, no server fleet. It is load-invariant and is NOT what the paragraph above restricts.
If the real guard is genuinely out of reach, reproducing its exact assertion in a one-process
probe is a legitimate and useful substitute; say that is what you did.

## Deliverable

Report to the coordinator with: the verdict; what you changed and why; **both directions of
every red-proof**, with the discriminating message quoted for direction 1 and the open
false-green named for direction 2; every cited issue with its relied-on line quoted; the
rebase outcome; and anything you found that was out of scope (do not fix it — name it, and
the coordinator files it).

Then a **DOGFOOD REPORT** — required, not optional (#589): what about this
loop's own tooling, docs, or briefs cost you time or misled you? My briefs have
been wrong several times today and the lanes that said so were right. The
section's value is what you found **beyond** your direct task — a premise the
brief got wrong, a hazard a sibling construct hides, friction with a tool, an
out-of-scope warning. Tonight's highest-value findings across seven lanes were
exactly those, and one — a predicted merge break — sat unread in an out-of-scope
section the coordinator never looked at, so write the section **and** know the
coordinator reads it. **"No friction found" is a valid answer that is STATED**;
an omitted section is not, because it reads as "no friction" and is
indistinguishable from a lane that did not look (#136/#671).
