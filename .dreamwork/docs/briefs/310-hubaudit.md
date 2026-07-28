# Brief — #310-shaped audit: `dreamhub.py` against `dreamhub-design.md`, for drift since the last one

Repo: `ud-dreamwork`. Worktree: **`.worktrees/hubaudit`**, branch **`wt/hubaudit`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: dreamhub.py, dreamhub-design.md, dev/hub

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[hubaudit]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/hubaudit-inbox.md` so I can steer you mid-task — I do, and two
lanes tonight were corrected mid-flight by exactly that channel.

Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which model you are** at the
top. **Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` — report
the lines you want added.

**Report a line per milestone and commit as you go.** Two lanes were killed by an external sweep tonight with
everything uncommitted and their final reports lost to 0-byte files; the per-milestone inbox lines were the
only surviving record. Assume you may be stopped without warning.

**Eight lanes are running.** Touch only your `Lane-owns:` paths. `dev/lane_guard.py` and
`lint.check_lane_containment_backstop` will name you by file and branch if you edit the main checkout —
verify your cwd and branch before **every** write.

## What this is

`dreamhub-design.md` is the hub's authoritative styleguide, and the repo's rule is that it stays
**single-source: a change is documented in the same commit that makes it.** `#310` audited it on 2026-07-27
and found **five** drifts — *all five were the DOC being wrong, not the code*. Time has passed and the hub has
moved. Audit it again.

Read `#310` in `.dreamwork/tasks.md` first: it records the five findings **and** one claim of its own that
review corrected, which is the more useful half. The corrected claim: it read `kind`/`awaiting_result` as
consumed by nothing, but `watch.py` folds every unnamed agent key into "the rest" deliberately — *"Whatever is
LEFT, not a second known list"* — so **the field list is a menu, not a whitelist.** An audit that prunes a
field because it cannot find a reader will repeat that mistake.

## How to audit so the result is trustworthy

- **Cite lines for every finding**, both sides: the doc line and the code line. A finding I cannot check
  against the cited lines is not actionable and I will not apply it.
- **For each drift, say which side is wrong** — the doc or the code — and why. `#310`'s value was that all
  five were doc-side, which is a different fix from a code change.
- **State clean bills explicitly.** *"I did not check X"* and *"X is clean"* must stay distinguishable.
- **`dreamhub-design.md`'s tokens are `watch-design.md`'s value for value**, deliberately, because he moves
  between the two constantly. A token drift is a real finding. **You do not own `watch-design.md`** — if the
  divergence is watch's fault, report it; do not edit it.
- **Fix the doc where the doc is wrong** (you own it), and report code-side findings for a later increment
  rather than changing behaviour inside an audit.
- Hub guards bind **39880–39889**, watch guards 39890–39899. Two servers in one range is a mistake this repo
  has already paid for; check `ss -ltnp` before binding, and remember eight lanes are running.

## Verification — this repo's rules, and they are not optional

- **Red-proof every check on the production line.** Name the line whose change reds it, change *that*, and
  watch it fail. **A green red-run is a finding, never a relief** — when you reinstate a bug and the check
  passes, the check is wrong.
- **Could your red have been produced against the code as it stood before your diff?** If reaching the
  failure needs a seam your change introduced, the proof is circular. A lane was rejected outright for that
  tonight.
- **Assert the precondition the check depends on, derived at runtime.** A check that examines nothing looks
  identical to one that found nothing — tonight a new check's coverage row silently never appeared because its
  parser saw no subjects. Put the count on the OK row.
- **Two values that must differ must be derived to differ.** A literal pair tuned to today's fixture is a
  check with an invisible expiry date; this repo has paid for that three times.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`** — eight lanes share this machine and the guard suite has documented load sensitivity (`#428`).
- Bind nothing in 39880–39899. Kill by exact pid; never `pkill -f`. Check `ss -ltnp` before finishing.
- **Never touch :35110, the heartbeat, the monitors, or the loop.** He is reading that dashboard.
- Trailer where it applies: `Migration:`, `Feature:`, `Needs: config|consent`. Decide and say why.
- 2 threads. **One commit per increment**: `git add <newfiles>` then `git commit --only <paths>` —
  **`--only`, never `git add -A`**; `--only <directory>` silently skips untracked files.
- ~20 minutes. **Commit before you finish**; land the smaller coherent half rather than nothing.
- **Push back with reasons.** A smaller honest result beats a larger one built on a premise you doubt — and
  two briefs tonight had premises that measurement refuted, so doubting mine is expected, not rude.
