# Brief — #445 increment 1: convert the run modes into the three-axis vocabulary he ratified

Repo: `ud-dreamwork`. Worktree: **`.worktrees/axes`**, branch **`wt/axes`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: file-formats.md, lint.py, test_lint.py, SKILL.md, .dreamwork/docs/plans/attention-modes.md

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[axes]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/axes-inbox.md` so I can steer you mid-task.

Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which model you are** at the
top. **Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` — report
the lines you want added.

**Report a line per increment and commit as you go.** Two lanes were killed by an external sweep tonight with
everything uncommitted and their final reports lost; the per-milestone inbox lines were the only surviving
record. Assume you may be stopped without warning.

## He has already ruled. You are implementing, not designing.

Read `#445` and `#443` in `.dreamwork/tasks.md`, and the design at
`.dreamwork/docs/plans/attention-modes.md`. His answer arrived 2026-07-29 03:45 and is folded in
`.dreamwork/questions.md` under `## Answered`. **His words, verbatim, are the specification:**

- **Q1: `rec`** — the three orthogonal axes stand: **pace × asking × delegation**.
- **Q2:** *"widen it, but we don't need to do that yet. We can just convert the current modes into the new
  values. we should add controls for the new values and their dimensions. We can have like 3 stops on each
  axis maybe? IDK that i will leave up to you, but we get 3 dimensions of input is the point."*
- **Q3:** *"0 can mean that subagents aren't necessarily banned or w/e, but they should only be used when a
  subagent is necessary or a particularly good choice. So like occasional subagent use. Another way to look
  at it is that the avg number of subagents running at any one time is <0.5. if the setting is 1, then the
  avg number of subagents should be 0.5 < x < 1.5. or the target number of subagents running at any one time
  is that."* Plus: *"we can get agents to work on a single worktree as a pair, too."*

**Read the two things this changes in `DREAMWORK.md`** (Preferences, near the end) — they are already
recorded and they are authoritative: the subagent number is an **average-concurrency target, not a cap**, and
**two subagents may pair on one worktree**.

## Your scope, and the line it stops at

**IN:** the vocabulary, the file shape, the closed sets, the conversion of today's three values, the parser
and its `lint` checks, `file-formats.md`, and `SKILL.md`'s selection posture.

**OUT, and this is firm: no `watch.py`, no dashboard controls.** Another lane holds `watch.py` right now. He
asked for controls and they are coming as increment 2 — your job is to make the *vocabulary* something a
control can be built against. If your design cannot be driven by a three-stop control per axis, say so in
your report rather than reaching for the UI.

## The decisions that are actually yours

1. **The stops.** *"3 stops on each axis maybe? IDK that i will leave up to you."* Three stops per axis is
   his suggestion and the number is explicitly delegated. Name them, and name them in this repo's copy voice
   (`watch-design.md` has it) — these strings are what he will read on a control. **No brittle numeric gates:**
   a stop steers posture; nothing measures or gates on it. His standing instruction.
2. **Where the value lives, given Q2 defers widening.** `.dreamwork/run-mode` today is one line from
   `lackadaisical` / `hot` / `assisted`, gitignored, machine-local, **re-read every tick** — that last
   property is load-bearing (`#426`: it is the only way an on-disk change reaches a running loop) and must
   survive. The design's recommendation was a **sibling file** precisely to avoid a migration. Decide, and if
   you widen anything, the commit carries `Migration:` and a **self-migration notice** — `migration_notice.py`
   exists for exactly this (`#458`), and a notice a stale agent still reads is the mechanism, not a comment.
3. **The conversion, stated as a mapping, not a rewrite.** `lackadaisical` → idle pace; `hot` → hot pace,
   own hands; `assisted` → delegating. Each of today's values must land somewhere in the new space with **no
   silent change in behaviour for a loop that has not been restarted**. State the mapping explicitly and say
   what an *unrecognised* value does — a closed set must fail loud, and `#290`'s existing behaviour is prior
   art you should match rather than reinvent.
4. **The delegation axis carries a number, and its meaning is his.** An average-concurrency target is not a
   cap, so nothing may implement it as a limit or a refusal. `0` is *occasional*, not *forbidden*. Whatever
   `lint` enforces must not turn his target into a gate: warn on nonsense (a negative), never on a session
   that happens to be above or below its average right now — that is what an average means and a checker that
   forgets it will be wrong most of the time.

## Verification

- `file-formats.md` states any shape a tool parses, **in the same commit as the code that reads it**, and
  `lint.py` checks it. That is this repo's rule and it is not optional.
- **Red-proof every check on the production line.** Name the line whose change reds it, change *that*, and
  watch it fail. **A green red-run is a finding, never a relief.**
- **Could your red have been produced against the code as it stood before your diff?** If reaching the
  failure needs a seam your change introduced, the proof is circular — a lane was rejected for exactly that
  tonight.
- **Assert the precondition the check depends on, derived at runtime.** A parser check whose fixture happens
  to contain one valid value proves nothing about the closed set; derive the set from the production constant
  and assert the fixture exercises more than one member.
- **A check that examines nothing looks identical to one that found nothing.** Tonight a new check's OK row
  silently never appeared because its parser saw no subjects, and only an expected-but-absent coverage row
  gave it away. Put the count on the OK row.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`.** Bind nothing in 39880–39899.
- Do **not** touch **:35110**, the heartbeat, the monitors, or the loop. Never `pkill -f`.
- Trailer: `Migration:` if any existing install's file must change, `Feature:` otherwise. Decide and say why.

## Files

**Yours:** the five in `Lane-owns:` above.

**Not yours:** `watch.py`, `test_watch.py`, `watch-design.md`, `transitions.md`, `dev/capture/*`, `justfile`,
`dev/lane_guard.py`, `review_artifact.py`, `user_events/*`, `DREAMWORK.md`, `.dreamwork/tasks.md`,
`.dreamwork/questions.md`, `.dreamwork/handoffs.md`, `.dreamwork/lessons.md`.

Note `lint.py` and `test_lint.py` are yours **as of this brief** — the coordinator has stopped touching them.
`lint.check_lane_containment_backstop` and `check_brief_lane_owns` landed there minutes ago (`64f0431`); read
them before you edit around them, and do not regress their coverage rows.

## Practical

- 2 threads. **One commit per increment**, `git add <newfiles>` then `git commit --only <paths>` —
  **`--only`, never `git add -A`**; `--only <directory>` silently skips untracked files.
- **Work only inside `.worktrees/axes`.** Verify cwd and branch before every write. A lane that edited the
  main checkout tonight aborted a held merge and produced `#465` — whose guard and backstop would now both
  catch you, and the backstop names the file and the lane.
- ~20 minutes. **Commit before you finish**; land the mapping and its checks even if the naming is still
  provisional.
- **Push back with reasons.** If the honest answer is that the axes cannot be expressed without widening the
  file now, argue it — he approved widening in principle and only deferred it, so a good argument moves the
  line rather than breaking a rule.

## Report

Say: which model you are; the stop names per axis and why those words; where the value lives and whether
anything widened (with the trailer and, if widened, the migration notice you wrote); the explicit mapping from
today's three values and what an unrecognised value does; how you kept the delegation number a target rather
than a cap, and what `lint` does and deliberately does not enforce about it; the coverage counts on each new
OK row; for each check the production line whose change reds it and confirmation no red needed a seam your
diff introduced; and confirmation you worked only in `.worktrees/axes` (state the cwd and branch you
verified), touched no `watch.py`, never touched :35110, and did not run the full `just test`.
