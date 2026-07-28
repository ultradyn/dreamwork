# Brief — #463 + #464: two things he asked for in one dictation, both small, both his own eyes

Repo: `ud-dreamwork`. Worktree: **`.worktrees/agebar`**, branch **`wt/agebar`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[agebar]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/agebar-inbox.md` so I can steer you mid-task.

Report a line per increment as it lands. Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which model you are** at the top.
**Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` — report the lines
you want added.

## These are his words, dictated 2026-07-29 02:30

Read `#463` and `#464` in `.dreamwork/tasks.md`. Both came from one dictation into the dashboard composer, so
both are things he is looking at right now.

**`#463` — review artifacts sort and age by the wrong timestamp.** *"fix the assets for review sorting — they
should use ctime not mtime. And the age should show since ctime, not mtime. However, when ctime != mtime, we can
show a 'modified X ago' msg to the right in a slightly different color. separate it from the age with a dot."*

**`#464` — the composer's scrollbar.** *"make the scroll bar in the command composer always show. It causes text
to reflow when it disappears after the text box grows large enough to hold all the text. It's a bit
distracting."*

## `#463`: the trap is the word ctime

**POSIX `st_ctime` is *inode change time*, not creation time.** It changes on a chmod, a rename, a hardlink — and
on Linux it is *not* birth time. So shipping `st_ctime` and calling it "created" would give him a number that is
wrong in exactly the cases he cares about, and it would look right in testing.

**Decide the source of truth with an IGC** (`igc-method.md` in the repo root: binary goals or breakpoints,
`✔`/`✘`/`?`, decisive error under each `✘`, never a score). Rivals worth stating: `statx` birth time where the
filesystem supplies it; the artifact's own build stamp, which `review_artifact.py` already writes into the file;
the first commit that introduced the file (`git log --diff-filter=A --follow`); `st_ctime` as-is.

Goals that will refute at least one: *the number does not change when the file is merely touched or rebuilt*;
*it is available for every artifact in the corpus, including the source-less ones* (`#436b` counted those — read
`.dreamwork/review/legacy-contract-exemptions.txt`); *it does not require a `git` call per artifact on every
render* (the review list is rendered often; `#283` exists because `git` calls in the render path took the index
lock). **Say what happens when the chosen source is unavailable** — a missing birth time must degrade to a named
state, not silently to mtime, because "silently the old behaviour" is the bug you are fixing.

**The three parts, and the third is the interesting one:**

1. sort the review list by created, not modified;
2. the age reads since created;
3. **when created ≠ modified, a *"modified X ago"* rides to the right of the age** — dimmer, dot-separated. The
   two facts coexist; the secondary only appears when it differs.

**Reuse the idiom that exists.** `#456` landed the day-age separator and found that `.qage`'s margin would have
doubled the gap — read that entry and the styleguide section it wrote, then use the same separator and the same
age treatment rather than authoring a second one. **A second dot idiom is a defect**, not a variation.

## `#464`: decide what "always show" means

The reflow is caused by a width change when the scrollbar vanishes, so **reserving the gutter** removes it.
`scrollbar-gutter: stable` reserves the space with no visible bar; a permanently visible bar is the literal
reading of *"always show"*. **Both fix the reflow.** Say which you chose and why — and note explicitly that the
gutter version removes the distraction he described **without** adding furniture to the page, which may or may
not be what he wants. If you genuinely cannot tell, implement the gutter, say so in the report, and I will ask
him rather than have you guess twice.

Check it against the **autogrow** behaviour that makes the box tall enough in the first place (`autogrow` is a
registered guard — read it), and against reduced-motion.

## Both are Web UI, so the bar is the repo's bar

`CLAUDE.md`: *every contribution to the Web UI must be of EXCEPTIONAL quality; merely functional, conventional or
locally polished work does not meet the acceptance bar.* **Load the relevant design skills** rather than relying
on generic frontend defaults, and read **`watch-design.md`** (authoritative styleguide — tokens, type,
components, copy voice, per-surface contracts) and **`transitions.md`** before designing.

**Anything that appears, disappears, moves or changes obeys `transitions.md`, with no size floor** — a *"modified
X ago"* that arrives when a file is edited is an arrival. Its opening section is *how to check*: an end-state
assertion cannot fail on a motion bug and neither can "did it move". Sample.

`watch-design.md` stays single-source: **document each change in the same commit that makes it**, which
`just audit-styleguide` measures.

## Verification

- **Red-proof each part on the production line.** Name the line whose change reds your check, change *that*, and
  watch it fail. **A green red-run is a finding, never a relief.**
- **Could your red have been produced against the code as it stood before your diff?** If reaching the failure
  needs a seam your change introduced, the proof is circular — a lane was rejected for exactly that tonight.
- **Assert preconditions at runtime, derived.** For `#463` the precondition is sharp and expiring: **at least one
  artifact whose created ≠ modified**, or the secondary-line check has no subject and passes forever. Derive it
  from the corpus; if none exists naturally, construct one in a fixture and assert the inequality you constructed.
- **Two numbers that must differ must be *derived* to differ.** A fixture with two hand-written timestamps that
  happen to differ today is a check with an expiry date — this repo has paid for that three times.
- Use `dev/capture/serve.mjs`'s `serveVerified` / `serveAllVerified` if you start a `watch.py` — **do not
  spawn-and-sleep**, and note `watch.py` has **no `--no-open` flag** (passing one kills your server on an
  argparse error and your request silently reaches a stranger). Register any new guard in `justfile`'s
  `DEFAULT_GUARDS` (**56** today, each needing its file) or it gates nothing.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`.** Bind nothing in 39880–39889; kill everything you start by exact pid and check `ss -ltnp` before
  finishing.
- Do **not** restart, `pkill` or redeploy the dashboard on **:35110** (he is reading it). Do not touch the
  heartbeat, the monitors, or the loop. Never `pkill -f`.
- Trailer: a changed sort order and a changed age basis alter what an existing install shows — `Migration:` or
  `Feature:`; decide per commit and say why.

## Files

**Yours:** `watch.py`, `test_watch.py`, `watch-design.md`, `transitions.md` (only to document what you change),
`justfile`'s `DEFAULT_GUARDS`, your new `dev/capture/*.mjs`, and `review_artifact.py` **only** if the created
timestamp must come from the build stamp it writes.

**Not yours:** `lint.py`, `test_lint.py`, `file-formats.md`, `migration_notice.py`, `user_events/*`,
`test_user_events_http.py`, `dev/capture/serve.mjs` and `report.mjs` (use them, do not edit them), `SKILL.md`,
`DREAMWORK.md`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/handoffs.md`,
`.dreamwork/lessons.md`, and anything under `dev/` outside `dev/capture/` (the `contain` lane holds `dev/`).

## Practical

- 2 threads. **One commit per increment** — `#463`'s three parts are naturally two or three, `#464` is one —
  `git add <newfiles>` then `git commit --only <paths> -m 'feat(#463): …'`. **`--only`, never `git add -A`**:
  other agents commit in this tree, and `--only <directory>` silently skips untracked files.
- **Work only inside `.worktrees/agebar`.** Verify your cwd and branch before each write: a lane tonight edited
  the main checkout instead of its worktree, aborted a merge that had been held for half an hour, and nearly had
  its half-finished work swept into someone else's commit. That is `#465`.
- **Commit before you finish**, and land what is done even if both tasks are not. `#464` is the smallest and
  entirely independent — if time is short, land it first so something of his lands.
- **Push back with reasons.** If `ctime` cannot mean creation on this filesystem and the honest answer is the
  build stamp, say so plainly; that is a better answer than a number that is wrong in the cases he cares about.

## Report

Say: which model you are; the IGC for the created-timestamp source with each decisive error and the survivor;
what happens when it is unavailable; the three `#463` parts with their shas; which reading of *"always show"* you
chose for `#464` and why; the separator idiom you reused and where it is documented; the transition check you ran
(sampled, not end-state) and reduced-motion parity; the production line whose change reds each check, the expiring
precondition you asserted for created ≠ modified, and confirmation no red needed a seam your diff introduced; the
trailers; and confirmation you worked only in `.worktrees/agebar` (state the cwd and branch you verified), left
nothing listening, did not touch :35110, and did not run the full `just test`.
