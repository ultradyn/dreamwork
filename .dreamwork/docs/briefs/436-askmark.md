# Brief — #436: an artifact without a measurable `#ask` cannot be checked, and 19 of 22 were not

Repo: `ud-dreamwork`. Worktree: **`.worktrees/askmark`**, branch **`wt/askmark`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: review_artifact.py, .dreamwork/review/legacy-contract-exemptions.txt, test_review_artifact.py

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[askmark]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/askmark-inbox.md` so I can steer you mid-task — I do, and two
lanes tonight were corrected mid-flight through exactly that channel.

Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md` (absolute path, main checkout — a report
written inside your worktree reaches nobody); **state which model you are** at the top, taken from the alias
you were dispatched with if you know it. **Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or
`.dreamwork/questions.md` — report the lines you want added.

**Report a line per milestone and commit as you go.** Lanes have been killed mid-task by an external sweep
with everything uncommitted and their final reports lost to 0-byte files.

**Several lanes are running.** Touch only your `Lane-owns:` paths — `dev/lane_guard.py` and
`lint.check_lane_containment_backstop` name you by file and branch otherwise, and tonight they caught the
coordinator doing it. Verify cwd and branch before **every** write.

## The defect

Read `#436` in `.dreamwork/tasks.md` and `.dreamwork/review/legacy-contract-exemptions.txt`.

A review artifact exists to make him a decision he can rule on, and the `#ask` is the element that makes it a
decision rather than a document. It is **not a required element**, so **19 of 22 artifacts could not be
measured at all** — and `#436b` counted the source-less ones, which is why the exemptions file exists.

## What to build

Make `#ask` a **required, checkable element** of an artifact `review_artifact.py` builds, and make the absence
of one loud at build time rather than discovered when he cannot answer. Decide and state:

- **What counts as an `#ask`** — the sub-decision labels, a `rec`, and the *if you say nothing* line are the
  three parts every good artifact tonight had. If you require all three, say what happens to an artifact that
  legitimately has one decision and no alternatives.
- **What happens to the exempt ones.** They are history and they are source-less. The exemptions file is the
  mechanism; **it must not become a place new artifacts quietly land.** State how a new exemption is
  distinguished from a legacy one — a grandfather list that keeps growing is not a contract.
- **Where the check lives.** `lint.py` and `test_lint.py` belong to another lane tonight, so **report the lint
  check you want rather than writing it**; build the `review_artifact.py` half and its own tests.

## The precondition that will otherwise expire

Your check needs **at least one artifact that legitimately has an `#ask` and one that does not** to prove both
branches. Derive both from the corpus at runtime and assert the pair — a fixture with two hand-written cases
that happen to differ today is a check with an invisible expiry date, and this repo has paid for that three
times.

## Verification — this repo's rules

- **Red-proof every check on the production line.** Name the line whose change reds it, change *that*, and
  watch it fail. **A green red-run is a finding, never a relief.**
- **Could your red have been produced against the code as it stood before your diff?** A red that needs a seam
  your change introduced is circular; a lane was rejected for that tonight.
- **Assert the precondition the check depends on, derived at runtime**, and put the count on the OK row. A
  check that examines nothing is output-identical to one that found nothing — that exact bug was found twice
  tonight, once in a coverage row reading `7 of 8`, once in tests appended into the wrong class so they never
  ran at all.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`.** Note `test_this_repo_passes_its_own_linter` can FALSE-RED while other lanes commit (`#428`) —
  if it fails, re-run it alone before believing it, and say so.
- Bind nothing in 39880–39899. Kill by exact pid; never `pkill -f`. **Never touch :35110**, the heartbeat, the
  monitors, or the loop.
- 2 threads. **One commit per increment**: `git add <newfiles>` then `git commit --only <paths>` — never
  `git add -A`; `--only <directory>` silently skips untracked files.
- ~20 minutes. **Commit before you finish.** Trailer where it applies; decide and say why.
- **Push back with reasons.** Several briefs tonight had premises measurement refuted — doubting mine is
  expected.
