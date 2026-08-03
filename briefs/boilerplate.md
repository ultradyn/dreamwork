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

**After every rebase, RE-ARM every required red-proof in full** — `forget` → `begin` →
sabotage → `observe` → `restore` → `cmp` against the path `begin` printed → `check --require N`
— **even when the changed paths look unrelated to your seam** (`#993`). This is an epistemic
requirement, not a claim that your evidence is definitely stale: `#993` ran 5 real rebase shapes
and measured that 1 preserved the pre-rebase evidence and 4 did not, and that the registry
cannot tell them apart, because it records no fail-closed dependency closure for the observed
command. Its sharpest case: master changed only an imported module, the recorded injection was
no longer reached, the post-rebase injection run went GREEN — and `check --require 1` still
exited 0 reporting CAUGHT 1/1. Content-based history scanning is orthogonal to whether the
causal evidence still holds.

**"Unrelated paths" is judged by what your command actually reads, not by what your seam
touches.** The coordinator nearly waved a rebase through on that reasoning when the seam was in
`lint.py` and master had only moved `briefs/boilerplate.md` — but `lint.py` READS that file, so
it was a direct input to the module under test. If you cannot enumerate every input to your
observed command, you cannot claim the paths were unrelated; re-arm instead.

**Red-proof both directions. This is the one that catches real defects.**
- *Direction 1*: inject the real defect and watch your check go red **on the discriminating
  failure message** — not on a red count. A red for the wrong reason is indistinguishable
  from a right one in a `-q` summary. **Name the production seam you broke (path plus
  symbol or branch), and inject there.** **A direction-1 report states what its expectation is derived from** (a hardcoded literal, a symbol, an idiom, a computed value): an expectation drawn from the same source as the thing it checks is silent to every tool — #836's `role="img" aria-label=…` assertion had drifted onto two unrelated components, and `check_watch_citations` matched two of its 24 against a BLANK line — and naming the derivation at the moment it is answerable is the only instrument that reaches those cases (#906). Editing a test's assertion or expected value proves
  only that the test rejects its own sabotage, so it is not a direction-1 proof. A test file
  is a valid target only when test/guard tooling is itself the production subject; name that
  executable seam and why. The observed failure must also distinguish the broken seam from
  an environmental precondition — if either condition produces the same message, it proves
  neither. `redproof.py check` certifies snapshot restoration and branch absence, **not** that
  the test reached the named seam; a production edit in an unvisited branch still passes it.
  Its successful verdict is restoration evidence only: quote its resolved target classes, and
  never report that verdict as the direction-1 evidence. A zero-registration verdict is
  explicitly **no evidence**, not a vacuous proof over zero injections.
  **Use `dev/redproof.py`; it owns the snapshot/restore protocol** (`#683`), and **registering an
  injection is no longer enough** — `check` requires evidence that some exact command went red
  BECAUSE of your injection and green again once it was restored (`#948`). **Carry
  `--lane <your-lane>` on every verb** (`#957`): a lane may have more than one registry, and the
  bare verbs resolve only to the legacy one, so omitting it operates on a different registry than
  the one that answered you.

      python3 dev/redproof.py begin <path> --expectation <expectation-source>
      …sabotage it, run your check, watch it go red…
      python3 dev/redproof.py observe <path> --failure '<discriminating message>' \
          --lane <your-lane> --command just pytest <test-file>
      python3 dev/redproof.py restore <path> --lane <your-lane>
      python3 dev/redproof.py check --require 1 --lane <your-lane>

  **`<expectation-source>` should be the TRACKED test file that binds your change** — the
  docstring's own example is `router.js --expectation test_router.py`. It must be a file that
  still exists, unchanged in identity, when `restore` and `check` run later. A lane pointed
  `begin` at an untracked `.bak` copy of the production file, cleaned the copy up, and both
  `restore` and `check` then FAULTED with *"registered path absent from the working tree"* — one
  cycle lost (`#1123`). `begin` does warn about untracked expectation sources, but the warning is
  easy to lose in the output wall, so choose the tracked test file up front rather than relying on
  catching it.

  **A test-only diff still owes an injection — it is NOT inert.** `land_lane._classify_diff`
  treats any path outside `.dreamwork/` as binding, so a lane that owns nothing but test files
  computes `required_injections=1`. Arm up front rather than discovering the requirement at
  `check`; several briefs (mine included) have said a test-only change "may classify inert", and
  `#1123` measured that it does not. **Whatever any brief tells you, run
  `land_lane._classify_diff` against your ACTUAL diff and believe the tool**, not the prose.

  **`--lane` MUST come BEFORE `--command`, and this ordering is load-bearing** (`#989`).
  `--command` is an `argparse.REMAINDER` (`dev/redproof.py:1765`), so it consumes everything after
  it — including `--lane` (`:1772`), which is then never parsed. The tool resolves a DIFFERENT
  registry and reports `has no armed injection`: a statement that is TRUE of the registry it
  examined and FALSE about your lane. This example taught the broken order until `#989` was filed
  by a lane that hit it live. Until `#989` lands the refusal, the ordering is yours to get right.

  **The `begin` line above is the ONE exception, and it is a linter artefact, not a rule:** it omits
  `--lane` because `lint.py` executes that exact line as a standing example and its cleanup does not
  thread the flag (`#909`), so adding it there makes the repo's own lint refuse. **Add `--lane
  <your-lane>` when you run `begin` yourself** — a `begin` on the legacy registry followed by an
  `observe` on the lane registry is `#957` in its purest form, and neither verb complains.

  **`--failure` must name a string that appears ONLY because of your injection.** A generic
  `AssertionError` matches an unrelated failure and proves nothing. `observe` refuses if the command
  exits 0, and refuses if the declared string is absent from the output. `restore` then reruns that
  exact command against the restored bytes, and only *injected-red plus restored-green* is reported
  CAUGHT — which is what makes the evidence causal rather than merely concurrent: an unrelated or
  flaky failure fails the control too, and correctly does not count. `check` distinguishes CAUGHT /
  NOT CAUGHT / NOT CHECKED and prints both denominators; **NOT CHECKED is a refusal under
  `--require`, not a pass** — `red-proof reach: DID NOT CHECK … examined 0 evidence artifact(s) for
  N registered injection(s)`. Absence of evidence is not evidence the injection was caught.

  **Your `--failure` string must also survive the test runner's own output rendering.** Pytest
  ABBREVIATES long values when it renders an assertion, so a `--failure` declaring the whole
  injected line can be genuinely ABSENT from the captured output even though the test failed for
  exactly the reason you intended — and `observe` will correctly report NOT CAUGHT. That refusal is
  the tool working, not a bug: it compares the string you declared against the bytes actually
  produced. **Declare the SHORTEST substring only your injection could produce**, and read the
  captured output to confirm it is there rather than assuming. `#980` hit this live and recovered by
  shortening `RED-PROOF INJECTION: presquash ref may be collected` to
  `presquash ref may be collected`.

  **Register against a TRACKED path that exists in every checkout.** The gate evaluates the registry
  from the MAIN CHECKOUT, so an injection registered against an ephemeral fixture or a lane-relative
  path FAULTS there — `cannot evaluate its injection; refusing rather than guessing` — even though
  your own `check` was clean when you ran it. Creating a fixture, proving a detector fires against
  it, and cleaning up is correct practice that the registry cannot yet express (`#982`); until it
  can, keep the registered subject a real tracked file.

  **Editing your `--expectation` file mid-injection is legitimate** (inject →
  red → add a test → restore is the natural rhythm) and `restore`/`check` will
  refuse on the changed bytes — that refusal is correct, not a mistake (#852):
  re-arm with `forget <path>`, then `begin <path> --expectation <source>`
  against the new bytes, re-sabotage, `restore` (#910). Do not silently re-pin.

  **Snapshot the FIXED file immediately before sabotage.** `restore` then returns
  that fixed state byte-for-byte. A baseline reproduction done before building is a
  separate round; finish its restore, apply the fix, then `begin` again for the final
  proof. Otherwise a pre-fix snapshot can silently undo the work while `cmp` certifies
  the wrong file (`#608`).

  **Run `check --require 1` before reporting and quote its output.** The minimum closes the
  zero-registration case for a brief that mandates red-proofing; bare `check` still reports
  **no evidence** without faulting for callers where the discipline is genuinely optional. It
  REFUSES if any injection is left
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

**This rule binds the brief's AUTHOR exactly as hard as it binds you, and on `#996` the author
was the one who broke it.** Of the 20 tracked sites citing `#140`, 17 carried its real meaning
(*"show the deployed revision so a stale view announces itself"*) and 3 substituted *"a check
that could not run must never look like one that ran"* — all 3 written by the coordinator, in
briefs and a code comment, in a single session. The correct authority for that principle is
`#136` (three zero-states: missing, present-but-unparseable, genuinely empty). `cx-866wording`
STOPPED rather than build on it, opened the entry, quoted `#140`'s actual title back, and was
right. **So: if a citation in the brief head does not say what the brief claims it says, that is
a refuted premise — stop and report it, and do not assume the coordinator checked.** The error is
seductive precisely because the wrong entry is usually true and adjacent; adjacency is not
authority.

**And a citation can be wrong by naming a real entry whose TITLE says something else entirely.**
`#996` landed at `e89b50be` and its generation-time citation report caught the author on its
FIRST run against a live brief: every brief written that night carried *"`#894` — never compose a
note inline; write to a file"*, while `#894`'s title is *"ledger.py sweep cannot see a merge-sha
citation."* **A remembered number is not evidence.** If you cannot quote the entry, state the
rule without a number rather than borrowing authority from one.

**The correction to that very example is the sharper lesson, and it is the coordinator's error.**
This paragraph used to say the `#894` citation was *invented wholesale* and that no ledger entry
stated the note rule. **That was false.** `#894`'s BODY states it exactly — *"THE STANDING FIX for
the coordinator: write long notes to a file and pass `--note "$(cat <file>)"`"* — so the citation
named the right entry and glossed it with a rule that lives in the body rather than the title. A
gloss mismatch, not an invention. The coordinator's search was entry titles plus one narrow
`LIKE '%inline%'` body pattern; it returned nothing, and **"I found nothing" was published as
"there is nothing"** — the exact collapse `#136` names, committed in the same breath as quoting
`#136`. So: before writing *no entry says X*, say what you searched and what would have made that
search miss, exactly as `lessons.md`'s *"A probe that can match itself has no floor"* demands of a
count. **A title search is not an entry search.**

**Compose a `--note` in a FILE and pass `$(cat …)`, never inline** — the rule is `#894`'s, stated
in that entry's body, so reach it with `python3 dev/ledger.py get 894` and read, never by grepping
titles. A note is prose containing backticks, quotes, `$`, `#` and newlines; composing it inline
hands all of that to the shell, which is how a note gets silently truncated at the first
unescaped character.

**Every quantity a brief asserts must sit next to the command that re-derives it** (`#978`).
`dev/brief.py` now reports, at generation, each bare number in a core that no re-derivation
command covers — and coverage means an apparent command on the SAME, previous, or next nonblank
line, inside an explicitly cued verification block. **A command elsewhere in the brief is
deliberately NOT borrowed as coverage**, because that is the defect `#978` was filed for: a
verified sub-claim beside an unverified headline makes the headline look verified. The `#972`
brief said *"13 recipes; 5 carry pipefail"*, gave a command for the `5`, and the true figure was
`17`. The report certifies SYNTACTIC completeness only — that a command is present — never that
the command can produce the number: `#978` measured `grep -c 'pipefail' justfile` → 7 against the
semantic 5, same file, same question, both defensible. So a covered number is not a verified one,
and **counts in a brief head are CONTEXT unless the brief names them as blocking** (`#994`).

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

**File-edit tools resolve relative paths against the coordinator's CWD, not your worktree.**
Pass an ABSOLUTE worktree path to every file-edit tool. A relative `file_path` lands in the
main checkout, invisible from your worktree — `#465`'s exact shape; `#889`'s lane caught it
only because its next act was an import that could not see the change (`#899`). The trap is
invisible because BOTH defaults point at the main checkout: file-edit paths resolve there,
and shell commands ALSO reset cwd there on every call (`#882`). You are the only thing that
knows you should not be there.

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

**Client builds.** Touching anything under `client/` requires `just build-client`
and committing the rebuilt `client/dist` in the same commit. During a rebase,
never hand-merge `client/dist/manifest.json`: take one side, then rebuild,
because it contains derived hashes.

**Doc map.** Do not edit `.dreamwork/docs/doc-map.md` — the coordinator folds its
rows at merge, and the file is shared across concurrent docs lanes. **Report every
new doc path in your completion report**; that report is what gets the row folded,
and without it the map rots silently. A lane adding a plan under
`.dreamwork/docs/plans/` hits a PREDICTED lint row on `doc-map.md` —
`plans row omits N plan(s) that exist: <names> — a reader of the map cannot learn they are there` —
expected, not a regression, when the omitted names are the plans you just added;
any other `doc-map.md` WARN is a real finding.

  **This holds even if your brief tells you to add the slug yourself — the brief is wrong and the
  rule wins.** The file has two different kinds of row and they mislead in opposite directions: a
  per-plan *description* row (clearly the coordinator's) and a single enumerated *plan-slug list*
  (which looks like a one-word append anyone could make). It is the second that bites. On
  2026-08-03 two lanes each appended one slug to that one line, both correctly, and collided at
  the merge gate; the coordinator hand-merged two 60-slug lines with three assertions to be sure
  the result was right. **Two lanes cannot append to the same line.** Report your new doc path and
  let it be folded. If a brief instructs otherwise, say so in your report — that is a defect in the
  brief worth more than the row.

**Lane bars are command-, snapshot-, and interpreter-relative.** Run `python3 lint.py`: require
NO ERRORs and compare the complete WARN row set against the measured baseline, not only the trailer
count; the rows are indented, so `grep -c '^WARN'` returns a false `0`. A worktree may add
`tasks.md` ledger-absent/zero-entry, `status.json`-absent, and `ledger checks`-examined-nothing
WARNs because those artifacts do not travel. To inspect live data with the WORKTREE interpreter,
use `python3 lint.py --target /home/xertrov/.llm-general/skills/ud-dreamwork`; a stale interpreter
need not reproduce current output.

Materialise a baseline interpreter at a real file path beside the checkout's `SKILL.md` (for
example, write `git show master:lint.py` to a temporary file beside `lint.py`), run it there, then
remove it. Never use process substitution (`python3 <(git show master:lint.py)`): that makes
`__file__` a detached `/dev/fd/...` path with no repo anchor, so lint must refuse instead of
producing a false zero-row baseline.

When a brief asks for real-path parity, freeze the subject (a read-only backup, copied fixture,
or pinned revision) and pin the baseline interpreter revision; vary only the intended interpreter
change. Report raw live readings as context, not as the proof. Otherwise concurrent movement can
make an honest "not identical" look like the lane's regression — or tempt it to round the
difference off to satisfy an impossible brief.

Likewise, judge targeted pytest by its own before/after collected count; a whole-repo total quoted
in a moving brief head is not that run's bar.

**Filesystem measurements need a measured substrate and an exact positive control.** Use
`M="$(dev/lane_scratch.py measure)" || true` followed by `[ -n "$M" ] || exit 1` as the one
lane-private location — **capture the refusal, do not let the assignment swallow it.** In
`X="$(cmd)"` the assignment's exit status IS the command's, but a caller that never tests it
receives an EMPTY string and carries on as though it got a path: `#981` measured exactly that
(`refused_assignment_exit=2 refused_value=<> shell_continued=yes`), and `#985` then measured
every such site in the repo and found this the only exposed one. The `guards` recipe is the
model — it captures with `|| true` and then tests the value. Ask the kernel for the substrate's
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
