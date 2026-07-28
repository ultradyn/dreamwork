# Brief — #275: research public Dreamhub authentication — RESEARCH ONLY, nothing exposed

Repo: `ud-dreamwork`. Worktree: **`.worktrees/hubauth`**, branch **`wt/hubauth`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: .dreamwork/docs/plans/hub-public-auth.md, .dreamwork/review/src/275-hub-auth.html

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[hubauth]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/hubauth-inbox.md` so I can steer you mid-task — I do, and two
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

## Hard boundary first

**Public/WAN serving of Dreamhub is FORBIDDEN until he approves a reviewed design.** This lane produces
research and a review artifact. **Do not bind a socket to a non-loopback address, do not touch a tunnel, do
not change how `dreamhub.py` serves.** If your research needs a running hub, run it loopback-only.

## What to research

Read `#275`, `#359` and `#360` in `.dreamwork/tasks.md`, and the existing
`.dreamwork/docs/plans/hub-public-auth.md` and `hub-ssh-auth.md` — **note `hub-ssh-auth.md` SUPERSEDES this
one's identity recommendation** and extends its threat model, TLS analysis and `/data.json` leak (C2), which
are inherited rather than re-derived. Do not re-derive them; cite them.

He has **three sub-decisions still open** on `#275` (Q3/Q5/Q6). Find them in `.dreamwork/questions.md` and
**answer them with research, not opinion** — that is the point of this lane. His original steer was to inform
the work with **shoo.dev**; treat that as a source to study, not a template to copy.

## The standard the artifact must meet

**Every request for a review ships a review artifact** (his rule): self-contained HTML, inline everything,
offline-clean, at `.dreamwork/review/src/275-hub-auth.html`. Read `review_artifact.py` and an existing
artifact and follow how they are built. `#436` is open precisely because artifacts have been shipped without a
measurable `#ask` — **yours must carry a real one**, with the sub-decisions named and a `rec`, plus an
if-you-say-nothing line.

**The one thing that would make this lane worthless:** a survey of authentication options with no decisive
errors. Use an IGC — binary goals, `✘` with the decisive error written out — against goals that actually
discriminate here: *no inbound port on his machine*; *no third-party identity provider holding his data*;
*works when he is on a phone away from the LAN*; *a compromised credential does not grant write access to the
loop*. If an option survives everything, say so and say why the others died.

Do not edit `doc-map.md` (contended) — report the row you want.

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
