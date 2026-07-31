# Brief — #592: `lint.py` in a lane worktree emits a false `tasks.md` ERROR

Lane-owns: `lint.py`, `test_lint.py`, `.dreamwork/handoffs.md` (append ONE `## Pending` line)

Worktree: `/home/xertrov/.llm-general/skills/ud-dreamwork/.worktrees/lane-592lint` (branch `lane-592lint`, from `d44070cc`)
Your inbox: `/home/xertrov/.cache/agent-comms/ud-dreamwork/lane-592lint/inbox.md`
Coordinator inbox: `/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`

## Chain

- **This task:** stop `lint.py` reporting a false ERROR when run inside a worktree.
- **Session goal:** the loop's own signals must be trustworthy — a red that is always red teaches everyone to ignore reds.
- **DREAMWORK.md goal:** *"Nothing fails quietly."* Its inverse matters just as much: nothing should fail loudly and falsely, because that is how a loud channel gets tuned out.

## The defect

`.dreamwork/ledger.sqlite3` is gitignored, so it does not travel to a worktree. `lint.py` then falls back to the git-tracked `.dreamwork/tasks.md` — which, since the SQLite cutover, is only a **migration-notice stub** with no `Next id: **N**` header. So it reports:

```
ERROR tasks.md — no 'Next id: **N**' header
```

The same lint against the main checkout reports `OK tasks.md — origin recorded on all 366 entries`. Verified both ways by the #586 lane.

## Why this is P1 despite being cosmetic

Every lane runs `lint.py` as its verification step, so every lane ends on an ERROR. The hand-off lines from **#565/#569, #583 and #586** each describe it as *"the pre-existing tasks.md Next-id error"* — three consecutive hand-offs teaching the next lane that a lint ERROR is background noise. `SKILL.md` says an ERROR here *"outranks other first tasks"*. We have spent that authority on a false positive.

## What to do

Measure before you accept my account — run the lint in this worktree and in the main checkout and confirm the divergence and its cause yourself.

Then pick a fix and say why you picked it:

- **Resolve the ledger from the main checkout when linting a worktree.** `git rev-parse --git-common-dir` gives the shared git dir, whose parent is the main checkout, so the real `ledger.sqlite3` is reachable. Truthful — a worktree lane genuinely shares one ledger — but it makes lint read outside its `--target`, which may be a boundary worth keeping.
- **Classify an absent ledger in a worktree as a distinct non-ERROR outcome** — `ledger absent (worktree)` as OK or WARN. Keeps `--target` honest; costs the ability to detect a *genuinely* missing ledger in the main checkout, so make sure that case stays an ERROR.

Do not silence the check unconditionally: an absent ledger in the **main checkout** must still be a loud ERROR. That distinction is the whole job.

## Verification

- `python3 -m pytest test_lint.py -q` plus any module your change touches. Then run `lint.py` **with an absolute `--target`** against both trees:
  - `python3 /home/xertrov/.claude-p/skills/ud-dreamwork/lint.py --target /home/xertrov/.llm-general/skills/ud-dreamwork/.worktrees/lane-592lint`
  - `python3 /home/xertrov/.claude-p/skills/ud-dreamwork/lint.py --target /home/xertrov/.llm-general/skills/ud-dreamwork`
  **Always pass an absolute `--target`.** Bash cwd resets between tool calls in this harness; a previous lane's `--target .` silently linted the wrong directory and produced no output at all, which it nearly read as clean.
- **Do NOT run `just test` or `just guards`** — the coordinator owns both, and a gate run is in flight on ports 39880-39899 right now.
- **Red-proof the new behaviour.** A test that a worktree lint is clean must be shown to fail before the fix: take a `cp` backup first, revert the production line, watch the test go red, restore by `cp` (**never `git checkout`**), confirm byte-identical with `cmp`. Then red-proof the *other* direction too — a genuinely absent ledger in a main checkout must still ERROR. That second one is the check that stops this fix becoming a blanket silence.
- **A green red-run is a finding, not a relief.** Report it.

## Lessons that bear on this

- **`lessons.md:336`** — *a check is only as good as the distance between what it asserts and what it exercises.* The trap here is a test that asserts "no ERROR in a worktree" and passes because it built a fixture with a ledger present. Exercise the real absence.
- **`lessons.md:180`** — my diagnosis above is a hypothesis. Measure it.
- **`lessons.md:405`** — *when a format fails silently, the fix is a writer, not a second description of it.* Relevant in reverse: resist adding a doc paragraph explaining the false ERROR. Fix the classification.
- **`lessons.md:953`** — edit surgically; do not re-author `lint.py`'s check block wholesale.

## Delivery obligations

1. Commit on your branch with `git commit --only <paths>`; a NEW file needs `git add <file>` first.
2. Append ONE line to `## Pending` in `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/handoffs.md` naming `#592` and your sha, **and commit it on `master` in the main checkout** (that is where `handoffs(#NNN): …` commits live; `## Folded` is first in the file, `## Pending` second, both append-only).
3. Report to the coordinator inbox, every line prefixed `[lane-592lint] `, starting with your handshake and ending with a `DONE` report: shas, what you measured, each red-proof and its result, what you remain uncertain about.
4. **End your report with a `Dogfood report` section** — friction you hit with the loop itself: an unclear brief, missing or wrong tooling, a convention that cost you time. "Nothing to report" is valid **if you say it**; an omitted section reads as no friction, which is not the same as none found.
5. **Do NOT use `attn`.** Do not merge, push or deploy. Do not stop the heartbeat, the watch server on :35110, or any loop machinery.
