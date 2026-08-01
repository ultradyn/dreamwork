# BRIEF — #827 + #826: the same bug in two places, and one of them is mangling his conversation right now

Worktree: /home/xertrov/.llm-general/skills/ud-dreamwork/.worktrees/cx-827markdown
Branch: cx-827markdown
Base sha: 9536c4d2
Repo root: /home/xertrov/.llm-general/skills/ud-dreamwork
Coordinator inbox — ABSOLUTE path, append your completion summary here when you finish: /home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md
  (This is `inbox.md`, NOT `.dreamwork/handoffs.md` — the standing contract's prohibition on
   writing handoffs.md still binds and this line does not override it.)
Lane-owns: `watch.py`, `test_watch.py`, `client/views.js`, `client/style.css`, `client/dist`,
`bin/ud-dw-chat`, `dev/capture/chatsurface.mjs`. No other lane holds these right now.

**Task:** `python3 dev/ledger.py get 827 --ledger /home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/tasks.md`
then `get 826`. **Note the `--ledger` form**; a bare `get` refuses from a worktree.

## This is live damage to a conversation with Max, happening now

At 15:10 today I replied to him in chat `ddc201a6`. My 3351-character reply — six headings, several
bulleted lists, a fenced code block — is stored in `transcript.md` as **ONE LINE**. He read it as a
wall of text, and at 15:33 he typed, from inside that broken surface:

> **"chat messages should be rendered as markdown and newlines should be preserved."**

That is his ruling and it settles the direction. It is not speculative — he has seen the failure.

## #827 — the storage half. The seam is exact.

**`watch.py:2736`**, in `_chat_turn_block`:

```python
return (f"<!-- dw-turn role={role} at={at}{rid} -->\n"
        f"{one_line(text)}\n"
        f"<!-- /dw-turn -->\n")
```

**`watch.py:4893`** — `one_line(text)` is `" ".join((text or "").split())`. It collapses **every**
whitespace run to a single space. Its own docstring names its domain:

> *"Fold a submission onto one line — **the log** is one event per line, and a newline typed into the
> box would otherwise forge a second event."*

**A chat transcript is not a log line.** It is a durable, append-only document. This is `#632`'s exact
shape — a helper reused past its stated domain for a durable value; there, the display-shaped
`read_text` destroyed twelve answered questions.

**The constraint does not even apply here, and this is the key measurement — verify it yourself
before relying on it.** `watch.py:2740` `_CHAT_TURN_RE` is `re.DOTALL` with `(?P<body>.*?)` terminated
by a `^`-anchored `<!-- /dw-turn -->`. **The parser already handles multi-line bodies.** Nothing
downstream requires one line.

**The real defence that IS needed** is the one the docstring gestures at: a body must not be able to
**forge a turn**. So reject-or-escape a body line matching the `dw-turn` open/close marker pattern —
do not collapse all whitespace. **Escape, do not destroy.** Prove the forgery attempt fails.

**Data already lost:** past turns are one-lined on disk and the original text is *not* in the
transcript. Check whether `/chat-reply` receipts carry `exact_payload_bytes` before concluding history
is unrecoverable — and **say either way**. Do not attempt a migration without reporting first.

## His ruling widens it: the chat surface must RENDER MARKDOWN

Preserving newlines is necessary and not sufficient — he asked for markdown. That is `client/views.js`
(the `.chaturn` render) plus whatever `client/style.css` needs.

**The server is stdlib-Python-only and that is a standing ruling** (`watch-design.md:41-51`, commit
`0f97df03`) — so **do not add a Python markdown dependency.** The client build is freed, the server is
not. Render client-side, or argue a different split explicitly.

**Escaping is a correctness requirement, not a nicety.** A markdown renderer that interpolates raw
transcript text into HTML is an injection vector, and the body is human- and agent-authored free text.
`client/views.js` already has an `esc` helper and a documented convention about where it applies (see
the `chatRow` comment `#657` landed at ~`views.js:751`). **Follow it and say how you handled it.**

## #826 — the log half. Same disease, different file, and it is HIS instruction too.

2026-08-01 15:24, receipt `a413470a-b3a5-5cf5-867d-7f4942ea3051`:

> *"when the subagent policy is set, the whole thing should be printed in the log so that the
> dreamwork agent does not need to read another file."*

Today `subagent_policy_line` logs only the set/reset **transition**; the prose is deliberately withheld
(the `SUMMARY_DENIED` reasoning in its docstring). **His ruling overrides that outcome.** But here the
one-event-per-line invariant is REAL — `watch-events.log` genuinely is line-oriented and the drain
parses it that way. So: **escape newlines in the LOG COPY only.** `.dreamwork/subagent-policy` stays
authoritative and byte-exact; the log carries a faithful, escaped, single-line rendering.

`#646`'s byte-for-byte guarantee must survive untouched — I verified it against his real 665-char
write at 15:21 and it holds. **Do not let the log copy's escaping leak into the stored value.**

I also put a question to him that he has not answered: whether the `#673` **tick line** should carry
it too (it repeats every ~4.5 min, so it survives compaction, which serves his stated goal better).
**He said "the log". Do the log. Do not silently substitute the tick line** — if you think it should
also go there, say so in your report and I will ask him.

## Red-proof

- **Direction 1, three seams, each named:** `watch.py::_chat_turn_block` (newline preservation),
  `client/views.js` chat turn render (markdown), `watch.py::subagent_policy_line` (log content). Break
  each and watch it red on a **discriminating** message — for the transcript the failure must name
  that *paragraph structure was lost*, not merely that text differed.
- **Direction 2, MANDATORY, and I am naming the specific false-greens because they are easy to hit:**
  1. A test asserting the transcript **contains** the reply text passes while every newline is gone —
     that is the exact bug shipping today. Assert **structure**: a reply with blank lines, a bulleted
     list and a fenced code block must round-trip with its line breaks.
  2. A test asserting the log line **contains** the policy passes while a multi-line write silently
     breaks every downstream one-line-per-event parser. **Assert the invariant too** — exactly one log
     line for one event, with a policy containing newlines, leading/trailing whitespace and non-ASCII.
  3. A markdown-render test that asserts on the **input string** rather than the rendered DOM proves
     nothing about what he sees.
- Run `python3 dev/redproof.py` for snapshot/restore; `python3 dev/lessons_index.py --act red-proof`
  before any injection. **Never `git checkout` to restore** (`#349`); snapshot the FIXED file (`#608`).

**Editing `client/*` makes lint ERROR until `just build-client` is re-run** (`#653`). Rebuild and
commit the artifacts or you red your own gate. Read `transitions.md` before changing anything that
animates.

## Lessons selected for this task

Cite by **content**, not my wording — verify each. I miscited an id three times today and three
separate lanes caught me, so please do check.

- **`#632`** — the display-shaped reader used for a durable value; twelve answered questions gone.
  This is the closest ancestor of `#827` and worth reading in full.
- **`#671`** — a check that examined nothing must not read as passing.
- **`#440`** — one supported way; if `one_line` needs a sibling, do not grow a third variant.
- **`#651`** — a guard's message must name a mode the guard can actually detect.
- **`#646`** — the byte-for-byte round-trip you must not break, verified live at 15:21 today.

## Run these, explicitly

```
just build-client
just pytest test_watch.py test_user_events_http.py
just pytest $(python3 dev/repo_wide_guards.py list)
python3 lint.py | tail -1
node dev/capture/chatsurface.mjs <outdir>   # NOTE: it takes an outdir argument
```

Browser guards bind **39890–39899**, hub **39880–39889**. Load is ~39 and `#666` measured guards
return WRONG answers under load — **if one reds, re-run it quiet before believing it**; if you could
not run them, say so rather than reporting a visual fix as verified when it was not.

## Bars

**Master is GREEN at `9536c4d2`** — `test_watch.py test_user_events_http.py` read **523 passed** and a
full gate at `05f7f902` read **2849 passed, 0 failed**. `#809` landed today demonstrating two mutations
that survive their whole relevant file, so do not read green as reassurance.

- Main-checkout lint reads **1** — the `lessons.md` near-duplicate, **human-gated and must stay**.
  A worktree reads ~5. `python3 lint.py | tail -1` — the count is in the **trailer** and rows are
  **indented**, so `grep -c '^WARN'` returns a false **0**.
- **Compare the complete WARN ROW SET, not the trailer count** (`#794`).
- Count tests by **collecting**, not by grepping `def test_`.
- Limit builds and tests to 2 threads.
- Do not bind `:35110` (deployed dashboard — **he is actively using it and reading that chat**) or `:35113`.
- **Do not use `attn`** — report to the coordinator inbox and let me decide what reaches the human.
- Rebase onto master before you finish. Master moved 33 times today.
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
