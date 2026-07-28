# Brief — #405: the skill must make worktrees the dispatch default, because the loop paid all session for a rule it already had

Repo: `ud-dreamwork`. Worktree: **`.worktrees/wtdefault`**, branch **`wt/wtdefault`**. Do not push, do not merge.
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are** at
the top — a lane report today was labelled `grok` when `glm52` was dispatched and I am tracking that.
**Do not write `.dreamwork/handoffs.md`** — the coordinator writes that at merge time.

## The defect, and it is a documentation defect with a measured cost

`CLAUDE.md` and `SKILL.md` both already say worktrees are the preference when work overlaps owned files.
**Every lane earlier this session ran in the shared tree anyway**, because nothing consulted either rule at
*dispatch* time. Read `#405` in `.dreamwork/tasks.md` for the counted cost: one increment shelved
(`a6c0732`), three dispatches serialised on `watch.py`, two tasks blocked on it, and a 459-line design
document (`#397`) commissioned for a problem the human had already ruled on in writing.

Note the situation has since changed and your fix must not contradict it: the coordinator **is** now
dispatching into `.worktrees/` (three live lanes as you start). So this is about making the default
**stated and checkable**, not about persuading anyone.

## What to change

`SKILL.md` in the skill root. Make the dispatch step say, at the point of dispatch rather than in a general
discussion of parallelism:

- **Worktree is the default for any dreamer that writes files.** Shared-tree dispatch is the exception and
  needs a reason (a read-only lane is the obvious legitimate one — `#437` ran read-only on master today and
  that was correct).
- **The absolute-path rule.** A lane in `.worktrees/x` that is told to append to `.dreamwork/inbox.md`
  writes to *its own* copy, and the coordinator never sees it. Every brief today carried the absolute path
  for exactly this reason. State it once, in the skill, so it stops depending on the coordinator
  remembering: **inbox and hand-off paths given to a worktree lane are absolute.**
- **Say what it costs**, not just what it buys — worktrees duplicate build state, and the cleanup rule
  (never force-remove without `git status --porcelain --ignored`) is the human's standing convention.

Keep it tight. This is a rule the skill already half-states; the win is putting it where dispatch happens
and cutting whatever now says it twice. **If you find the existing text already says this adequately and
the real gap is elsewhere, say so and argue it** — a refusal with evidence is a complete answer here, and
the most valuable lane today refused what it was handed.

## Done means

1. `SKILL.md` states worktree-by-default at the dispatch point, with the exception, the absolute-path rule,
   and the cost. No duplicated guidance left behind.
2. **The absolute-path rule is checkable, or you say why it is not worth a check.** `lint.py` already checks
   briefs for the hand-off obligation (`#398`) — a sibling check that a brief naming a worktree also gives
   absolute paths for `inbox.md` is the obvious shape. **`lint.py` is yours for this one task only.**
   If you add it: **red-proof it** — strip the absolute path from a brief, watch it fail, name the exact
   production line whose change reds it. **A green red-run is a finding, never a relief.** And **assert the
   check's own precondition** (that a brief matching the worktree pattern exists at all — a check that
   silently matches nothing passes forever).
3. **`python3 lint.py` clean** and **`python3 -m pytest -q -p no:randomly` passes.** **Do not run the full
   `just test`**; bind nothing in 39880–39899.
4. Do **not** restart, `pkill` or redeploy the live dashboard on :35110, and do not touch the heartbeat,
   monitors or the loop. `just deploy`'s `pkill -f` matches any process whose command line merely *mentions*
   the pattern (`#431`) — and today it self-matched from a **comment** containing it. Build process patterns
   from parts.
5. A commit that changes what an existing install must do carries a trailer: `Migration:`, `Feature:`, or
   `Needs: config|consent`. A skill-behaviour change is likely `Feature:` — decide.

## Files

Yours: `SKILL.md`, `lint.py`, and `test_lint.py` / `test_watch.py` for a check you add.

**Not yours:** `dev/capture/above_fold.mjs`, `dev/capture/devoverlay.mjs`, `justfile` (**a live lane holds
all three**), `watch.py`, `file-formats.md`, `dev/deploy_state.py` (**a second live lane holds those**),
`.dreamwork/docs/doc-map.md` (contended), `review-artifact.template.html`, and `.dreamwork/tasks.md` /
`questions.md` — the coordinator is their only writer, so report exact lines instead of editing them.

## Practical

- 2 threads. `git add <newfile>` then `git commit --only <paths> -m 'docs(#405): …'` — **`--only`, never
  `git add -A`**: other agents commit in this tree and a bare `git commit` sweeps their staged work into
  yours.
- **Commit before you finish.** A lane today did 24 turns of correct work and exited without committing.
- **This should be small.** If it grows, land the `SKILL.md` half and say what you left.

## Report

Say: which model you are; the exact `SKILL.md` text you added and what you removed as duplicated; whether
you added a lint check and, if so, the production line whose change reds it plus the precondition you
asserted; the trailer you chose; and confirmation you did not run the full `just test`, touch :35110, or go
near the files the live lanes own.
