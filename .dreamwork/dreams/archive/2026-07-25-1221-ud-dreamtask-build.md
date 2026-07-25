# ud-dreamtask, built and dogfooded (#50)

2026-07-25, 12:07–12:21. Dreamer: dreamer-dreamtask. Plan:
`.dreamwork/docs/plans/ud-dreamtask.md` (Max: "rec lgtm", 10:47).

## What landed

- **This repo** (commits 6f732dd, 3166cb4, and a timestamp correction):
  the plan folded — Open questions replaced by Settled + Findings +
  Coordinator rulings; one doc-map row; one README bullet.
- **A new sibling repo**, `/home/xertrov/.llm-general/skills/ud-dreamtask/`
  (4 commits): `SKILL.md` (209 lines), `newerrand.py`,
  `test_newerrand.py` (4 passing), `README.md` with the repo's topics,
  `.git/description`, `.gitignore`. Symlinked into `~/.claude/skills/`;
  the harness now lists the skill, which is independent confirmation the
  frontmatter parses.
- **An archived errand**,
  `~/.config/dreamwork/tasks/archive/dreamstate-creator/`, which is the
  stage-4 dogfood: a real errand walked through ud-dreamtask's own
  opening → increments → verification → wrap → archive.

Stages 1-5 of the plan are done. Stage 6 (harvest) is gated and is a
handoff, not an edit.

## The decision the rest hangs off

The dreamstate is **target-shaped**: `~/.config/dreamwork/tasks/<slug>/`
holds `task.md` and a nested `.dreamwork/{status.json,questions.md,
dreams/}`. Every existing reader then sees an errand with zero new code,
and this was checked rather than assumed — `lint.py --target` ran on
one, `dreamhub.is_target()` returned True on one, `watch.py` resolves
`<target>/.dreamwork` at line 3197. The alternative (flat files plus a
reader that knows about errands) would have been a second implementation
of formats that already have one.

Two rules fell out of it and are now stated in the skill:

- **Capture flows one way.** A dreamtask writes only its own dreamstate
  and hands ideas upstream by *report*; a future dreamwork init *reads*
  archived dreamstates. Ids belong to a coordinator and `questions.md`
  has a single-writer discipline, so an errand writing into a garden's
  `.dreamwork/` would be the fifth unowned-state incident of the day.
- **One home, no branch.** A repo's DREAMWORK.md changes what *binds*,
  never where errand state *goes*.

## Guardrails by reference — what it actually costs

The brief said inherit by reference, not by restatement, and warned that
restating feels safer. It does. What made it easy in the end was having
something specific to say instead: the skill states only five things
that are genuinely different about an errand (criteria are the
termination test and are fixed at the opening; no rotation, so no
`maintain:` commit marker; a shorter chain for the scope gate; capture
has one destination; an errand that cannot verify stops rather than
grinds). Everything else points at SKILL.md by section name.

The cost lands on the *other* side, which is easy to miss: a rename of
Guardrails/Subagents/Durable-state now orphans a live pointer in another
repo. That obligation is the doc-map row, not a comment in the skill.

## Two findings the fold produced, before any code

- The plan's **"maintenance scaling"** bullet (budget reflection beats
  by size; maybe `roll.py --budget N`) does not survive its own answers:
  what it scaled is the maintenance rotation, which an errand has none
  of. Reflection is per-change and is not scalable without relaxing an
  inherited guardrail. A 15-minute errand has one increment and
  therefore one reflection.
- Task #50 was titled "plugin". It takes no `ud-dreamwork-` prefix, so
  plugin discovery never sees it; the coordinator retitled it. A word
  nobody had re-read since it was written would have sent someone to
  build against `writing-plugins.md`'s contract.

## From the dogfood

Walking the opening as written found three things reading it did not:

1. Step 4 said "create the dreamstate" and left an agent to hand-write
   the two formats in this project that fail *silently*. It now calls
   `newerrand.py`, whose test shells out to `lint.py` — so the creator
   states no format of its own and the linter stays the single
   interpreter.
2. Step 5 assumed the errand owns the session. Run as a dreamer inside
   another loop, arming a monitor breaks an inherited rule. Now stated.
3. The opening wrote `last_tick` before anything had ticked.

And one thing about my own work: the plan's status header carried two
timestamps I *estimated* — 12:20 and 12:40 for work done at 12:11 and
12:16. Ten minutes had passed; I felt forty. Corrected in a commit. The
coordinator made the same error four hours earlier and lint.py now
carries a future-skew check for `last_tick` because of it, so the rule
was written, enforced in one place, and broken in the place the check
does not reach.

## What I did not do

- Did not run `just test`: nothing I touched in this repo is Python, and
  `watch.py`/`test_watch.py` were mid-edit by another dreamer. The
  sibling repo's own tests ran (4 passing), and its checks were each
  shown red by injection first.
- Did not touch `initialization.md`, `migrations/`, `file-formats.md`,
  `lint.py`, `tasks.md` or `questions.md` — coordinator's, by ruling.

## Open, for whoever picks this up

- **Stage 6 (harvest)** needs Max's go before it is planned: dreamwork
  init reading archived dreamstates to seed a new garden. It edits core
  files, so it is a handoff.
- **A blocked errand is invisible.** Hub listing is opt-in (right call —
  errands are transient), but an errand with a non-empty
  `awaiting_human` sitting in `~/.config/dreamwork/tasks/` is read by
  nothing. Parked deliberately in the plan; dreamhub stage 2 or stage 6
  inherits it.
- **Sub-loop composition** (a dreamtask inside a live dreamwork session)
  remains unbuilt by design.
