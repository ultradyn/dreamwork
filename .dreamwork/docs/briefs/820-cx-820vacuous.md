# BRIEF — #820: two false-greens that were DEMONSTRATED, not suspected — and one is a live hazard

Worktree: /home/xertrov/.llm-general/skills/ud-dreamwork/.worktrees/cx-820vacuous
Branch: cx-820vacuous
Base sha: 05f7f902
Repo root: /home/xertrov/.llm-general/skills/ud-dreamwork
Coordinator inbox — ABSOLUTE path, append your completion summary here when you finish: /home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md
  (This is `inbox.md`, NOT `.dreamwork/handoffs.md` — the standing contract's prohibition on
   writing handoffs.md still binds and this line does not override it.)
Lane-owns: `test_guard_argv.py`, `test_dreamwork_db_import.py`. You may READ `dev/capture/*.mjs` and
`dreamwork_db/question_parse.py` but **do not change production behaviour** — these are test defects.

**Task:** `python3 dev/ledger.py get 820 --ledger /home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/tasks.md`
Then read the full evidence: **`.dreamwork/lane-809-report.md`** (landed today, on master).
**Note the `--ledger` form**; a bare `get` refuses from a worktree.

## These are not hypotheses. Someone already broke the code and watched the tests pass.

`#809`'s lens E ran a bounded mutation audit. Most of the suite killed its mutations. **These two
survived their COMPLETE relevant test file.** Both are `#702`'s count-vs-membership shape.

### 1. `test_guard_argv.py::test_outdir_sweep_count` — and this one is a live hazard

**Appears to check:** every outdir-shaped browser guard uses the shared `outdir(process.argv)` parser;
its docstring says a revert shrinks the sweep and should fail.

**Actually checks:** at least `CENSUS == 84` files contain the literal string `from './outdir.mjs'`.
**The live population is 94.** So **ten** named guards may lose that import before the floor fires.

**The demonstrated mutation:** delete `import { outdir } from './outdir.mjs';` from
`dev/capture/wisp.mjs` while keeping `const OUT = outdir(process.argv)`. That guard now calls an
undefined identifier and **cannot judge anything**. Result: the named node passed, and the whole file
passed — `10 passed in 1.03s`.

**Why this is worse than a weak test:** a guard that crashes before judging is exactly the shape
`#611` is about — absence reading as a pass. This test is what stands between us and a silently
non-functional guard, and it currently has ten guards of slack.

### 2. `test_dreamwork_db_import.py::TestDatelessEntries::test_dateless_entries_imported`

**Appears to check:** the three dateless Answered entries import as answered questions.

**Actually checks:** `len([q for q in snapshot if q.status == "answered"]) == 3`. It never asserts
**which** questions occupy that set.

**The demonstrated mutation:** in `dreamwork_db/question_parse.py::_build_entry`, force ordinal 1 (the
**Open** `#90001`) to `answered` and ordinal 2 (the **Answered** `#90002`) to `unanswered`. Cardinality
holds at three; identities are wrong. Result: `34 passed in 0.43s`.

This matters beyond the test: `#632` is the incident where the wrong question state destroyed twelve
answered entries. A test that cannot see swapped identities cannot see that class of bug.

## Deliverable

**Assert membership and identity, not cardinality**, in both. For (1) that means the census must bind
the actual guard set — derive it rather than hardcoding a floor, so it cannot drift again; a floor
that trails the population by ten is how this happened. For (2) it means asserting *which* ordinals
carry which status.

**Do not simply raise 84 to 94.** A hand-maintained count describing a moving population drifts the
moment the population moves — that is the defect, not the number. `#813` landed the same correction
in `briefs/boilerplate.md` today for the same reason; read that landing before you choose.

## Red-proof — and here it is unusually concrete, so there is no excuse for a weak one

- **Direction 1:** re-run **each lane's exact mutation above** against your fixed test and show it now
  REDS on a **discriminating** message — for (1) the failure must name *which guard lost the import*,
  not merely that a count differed; for (2) it must name *which ordinal has the wrong status*.
- **Direction 2, mandatory:** construct the case where your fix **looks** applied but is not. For (1)
  the obvious one: a derived census that silently derives an EMPTY set passes vacuously forever —
  assert the derivation found a non-zero, plausible population. For (2): a membership assertion that
  compares two sets built by the same buggy helper compares a value to itself.
- Run `python3 dev/redproof.py` for snapshot/restore; `python3 dev/lessons_index.py --act red-proof`
  before any injection. **Never `git checkout` to restore** (`#349`); snapshot the FIXED file (`#608`).
- **Do NOT run browser guards** — load is high and `#666` measured they return wrong answers under
  load. You do not need to run `wisp.mjs` to do this work; say in your report that you did not.

## Lessons selected for this task

Cite by **content**, not my wording — verify each. I miscited an id three times today and three
separate lanes caught me, so do check.

- **`#702`** — a count comparison passes when membership changed but length did not. Both findings.
- **`#611`** — a check that did not run must say so; absence reads as a pass. Finding (1) exactly.
- **`#671`** — a check that examined nothing must not read as passing.
- **`#632`** — the wrong-state incident that destroyed twelve answered entries; why (2) matters.
- **`#813`** — landed today: the fix for a drifting hardcoded count is not a new hardcoded count.

## Run these, explicitly

```
just pytest test_guard_argv.py test_dreamwork_db_import.py
just pytest $(python3 dev/repo_wide_guards.py list)
python3 lint.py | tail -1
```

## Bars

**Master is GREEN as of `05f7f902`** on targeted files; a full gate is in flight. `#809` is the reason
you should not read that as reassurance.

- Main-checkout lint reads **1** — the `lessons.md` near-duplicate, **human-gated and must stay**.
  A worktree reads ~5. `python3 lint.py | tail -1` — count is in the **trailer**, rows are
  **indented**, so `grep -c '^WARN'` returns a false **0**.
- **Compare the complete WARN ROW SET, not the trailer count** (`#794`).
- Count tests by **collecting**, not by grepping `def test_`.
- Limit builds and tests to 2 threads.
- Do not bind `:35110` (deployed dashboard, live — he is watching it) or `:35113` (dev).
- Do not use `attn` — report to the coordinator inbox and let me decide what reaches the human.
- Rebase onto master before you finish. Master moved 29 times today.
# Lane brief boilerplate — appended verbatim to every dispatch

This is the standing half of a lane brief. The coordinator writes a task-specific head
and concatenates this file after it. It lives in the repo rather than in a session
scratchpad because it is corrected by lane dogfood reports several times a night, and
every one of those corrections used to die with the session that made it (`#703`).

**Ledger reads from a worktree.** The bare `python3 dev/ledger.py get <id>` form
refuses because the store is gitignored. Use this working invocation for every read:

    python3 dev/ledger.py get <id> --ledger /home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/tasks.md

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
  from a right one in a `-q` summary. **Name the production seam you broke (path plus
  symbol or branch), and inject there.** Editing a test's assertion or expected value proves
  only that the test rejects its own sabotage, so it is not a direction-1 proof. A test file
  is a valid target only when test/guard tooling is itself the production subject; name that
  executable seam and why. The observed failure must also distinguish the broken seam from
  an environmental precondition — if either condition produces the same message, it proves
  neither. `redproof.py check` certifies snapshot restoration and branch absence, **not** that
  the test reached the named seam; a production edit in an unvisited branch still passes it.
  **Use `dev/redproof.py`; it owns the snapshot/restore protocol** (`#683`):

      python3 dev/redproof.py begin <path>     # snapshot the file as-is, arm the entry
      …sabotage it, run your check, watch it go red…
      python3 dev/redproof.py restore <path>   # record the injected content, restore, verify
      python3 dev/redproof.py check            # hand-off gate — run before you report, quote it

  **Snapshot the FIXED file immediately before sabotage.** `restore` then returns
  that fixed state byte-for-byte. A baseline reproduction done before building is a
  separate round; finish its restore, apply the fix, then `begin` again for the final
  proof. Otherwise a pre-fix snapshot can silently undo the work while `cmp` certifies
  the wrong file (`#608`).

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
your report. Confidently-wrong citations are the characteristic failure mode here.

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

**Also run the always-run repo-wide guard set — additive to the targeted subset above, not a
replacement for it.** A repo-wide guard asserts a property over a population your diff cannot
enumerate (every production source, every parser verb), so "the tests for the files you touched"
cannot reach it — two merges were reverted in one hour for exactly this (`#776`'s lane added a raw
`sqlite3.connect`; `#645` i9 added verbs with no `_VERB_ARGV` rows). The ruling above stands
unchanged: this is a small, deliberate ~1%-of-the-tree set ON TOP of your targeted subset, not the
whole tree. Run it alongside your subset:

    just pytest $(python3 dev/repo_wide_guards.py list)

The command above is the single source for the set and its current population (`#440`).
This catches cross-cutting
RULES only — not a lane breaking an unrelated feature's behaviour, which is what the coordinator's
full merged-tree sweep is for and remains for (`#651`); nothing here makes that sweep optional.
Adding a member needs the entry criterion argued (see the tool's docstring).

**Lane bars are command-, snapshot-, and interpreter-relative.** Run `python3 lint.py`: require
NO ERRORs and compare the complete WARN row set against the measured baseline, not only the trailer
count; the rows are indented, so `grep -c '^WARN'` returns a false `0`. A worktree may add
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

**The MCP playwright browser's screenshot output root comes from the server's launch cwd,
not the lane's cwd
(#670).** The `@playwright/mcp` server (v0.0.78) derives its output dir from `process.cwd()`
when no `--output-dir` flag is set — and that cwd is the coordinator's, because the server is
one per session and shared by all lane subagents. `browser_take_screenshot` accepts only a
`fileName` (a basename resolved against the output dir), so you cannot redirect per-call. A
default-named screenshot lands in `<cwd>/.playwright-mcp/` inside a git tree that is not yours.
The harm is mitigated today by `.gitignore` (`.playwright-mcp/` is ignored), but do not rely on
that. Run `python3 dev/mcp_screenshot_root.py` to discover the shared server and see where
screenshots will land; `UNKNOWN` means no reliable root was found and must not be replaced
with the lane's cwd. `--safe` prints a lane-private staging dir (same identity derivation
as `dev/lane_scratch.py`) to copy screenshots into after taking them. The MCP browser also
**blocks `file://` URLs** by default — to verify a built HTML artifact, bind an ephemeral port
(outside 39890–39899 and 35110/35113) and navigate to `http://localhost:<port>/<file>`.

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
