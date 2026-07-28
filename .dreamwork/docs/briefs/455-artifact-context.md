# Brief — #455: he feels lost reading our review artifacts. Give every one a context paragraph, enforced at build.

Repo: `ud-dreamwork`. Worktree: **`.worktrees/context`**, branch **`wt/context`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

## Two-way channel — do this first, before any work

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. Your **coordinator inbox is
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Send the startup handshake
there **before** starting, prefix every line `[context]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/context-inbox.md` so I can steer you mid-task. Append a one-line
note at each milestone: **audit counted**, **contract implemented**, **artifacts updated**, **committed**.

Full report goes **once** to `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and
**state which model you are** at the top. **Do not write `.dreamwork/handoffs.md`.** **Do not edit
`.dreamwork/tasks.md` or `.dreamwork/questions.md`** — the coordinator is their only writer; report the lines
you want added.

## The instruction, verbatim

> *"update protocols: when review artifacts are written, they should have a paragraph of text at the top giving
> context to the artifact for review. Like I feel lost when i read these half the time b/c i have no context."*
> — the human, 2026-07-29 01:07, typed into the dashboard composer **while reading**
> `.dreamwork/review/269-draft-durability.html`

He is not asking for a summary. `headline` and `sub` metadata already summarise every artifact, and they did
not stop him feeling lost — so a fix that adds another summary line has missed it.

## Step 1 — measure "half the time" before you change anything

The artifacts are on disk in `.dreamwork/review/` with sources under `.dreamwork/review/src/`. **Count how many
actually open with orientation** and report the fraction with the expression that produced it. **No literal
counts** — a literal is wrong the day after it is written. Start with the one he was reading; it is the
strongest evidence you have about what "lost" means, so read it *as he would*, top to bottom, and say in your
report what a first-time reader cannot tell from its first screen.

If the audit shows most artifacts already orient him and something else is the problem (he is reading them from
a route that hides the top, the ask is above the context, the context is there but buried under a chart), **say
so and argue it.** A refusal with evidence is a complete answer here and the most valuable lanes today refused
what they were handed.

## Step 2 — what the paragraph must answer

Get this right or it becomes a heading he skips. At minimum:

- **what this artifact is** — a design? an analysis? a plan awaiting a go/no-go?
- **what decision it exists to serve**, named by task id, in one clause.
- **why he is being asked now** — what triggered it, what is waiting on him.
- **what happens if he says nothing** — is work blocked, is a default taken, is it parked?

Write the voice contract into `watch-design.md`'s copy section (it is authoritative and single-source), not only
into code. Then **write one yourself for `269-draft-durability.html`** as the worked example, because a contract
demonstrated once is worth more than a contract described three ways.

## Step 3 — enforce it at build, the way `#436` did

`#436` (landed) made the `#ask` block a **build-time** contract in `review_artifact.py`: a build **refuses** an
artifact whose ask is missing, doubled, or a decoy, with an exemption by declaration —
`<meta name="dreamwork-review-ask" content="ask|exempt: <reason>">`. **Reuse that mechanism.** A context slot is
the same shape: required, refused at build, exemptible by a declared reason. Do not author a second enforcement
path, and do not add a browser guard where a build refusal is available — the build already runs on every
artifact.

Two facts that constrain the design, both from `#436`:

- **12 of 24 artifacts have no `src/`**, so a build-time contract cannot reach them. `#436`'s walking guard was
  deliberately left unregistered for exactly this reason. **Decide and state** whether those are reconstructed,
  declared exempt in a side-file the checker reads, or left as the standing reason the guard stays off. **Do
  not register a guard that silently passes over half the corpus** — that is the hollow-check failure this
  repo has paid for repeatedly.
- Rebuild every artifact you can after a template change, and **check for staleness afterwards** — a template
  change left `288-containment.html` stale tonight and lint caught it only because `#329` measures it.

**Red-proof the refusal**: strip the context paragraph from a source, watch the build fail, and **name the exact
production line whose change reds it**. **A green red-run is a finding, never a relief** — if the build succeeds
with the context missing, your check is wrong; do not conclude the artifact was fine. **Assert the check's own
precondition** derived at runtime (that at least one artifact with a `src/` is actually being checked — a check
that matches nothing passes forever).

## Done means

1. The audit fraction, derived and shown.
2. A context contract stated in `watch-design.md` and enforced in `review_artifact.py`, reusing `#436`'s
   mechanism, with the `src/`-less half explicitly decided.
3. Every buildable artifact rebuilt, none stale, `#ask` contract still satisfied.
4. `python3 lint.py --target .` clean and `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
   `just test`.** Bind nothing in 39880–39899 or 39890–39899.
5. Do **not** restart, `pkill` or redeploy the live dashboard on **:35110** — he is reading it right now. Do not
   touch the heartbeat, the monitors, or the loop. Never `pkill -f`.
6. Trailer: a new build-time obligation on an existing install is likely `Feature:` — decide and say why.

## Files

**Yours:** `review_artifact.py`, `review-artifact.template.html`, `.dreamwork/review/**` (sources and built
files), `watch-design.md`'s copy section, `test_review_artifact.py` (or the existing test module for it).

**Not yours:** `watch.py`, `transitions.md`, `justfile`, `test_watch.py`, `dev/capture/*` (the `mistperf` lane
holds all of those and is mid-measurement), `SKILL.md`, `lint.py`, `dev/ledger.py`, `dreamhub.py`,
`.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/handoffs.md`.

**Note on `transitions.md` and `watch-design.md`:** `watch-design.md`'s copy section is yours, but the
`mistperf` lane is editing the same file's motion section in the same window. **Touch only the copy section,
keep the diff tight, and expect to resolve a merge** — the coordinator will union it.

## Practical

- 2 threads. `git add <newfile>` then `git commit --only <paths> -m 'feat(#455): …'` — **`--only`, never
  `git add -A`**: other agents commit in this tree and a bare `git commit` sweeps their staged work into yours.
  `--only <dir>` silently skips untracked files, hence the `git add` first.
- **Commit before you finish.** Lanes today have exited with correct work uncommitted.
- **~15–20 minutes.** If the `src/`-less half turns into a reconstruction project, land the contract plus the
  decision and report that half as a successor task.
- Choosing between rival designs? Use **IGC** — `igc-method.md` in the repo root, vendored tonight (`#447`):
  binary goals, `✔` non-refuted / `✘` refuted with the decisive error written out, breakpoints not
  maximisation. Not a pro/con list.

## Report

Say: which model you are; the audit fraction and its expression; what a first-time reader cannot tell from
`269-draft-durability.html`'s first screen; the contract text you wrote and the worked example; how you handled
the 12 `src/`-less artifacts; the production line whose change reds the build refusal and the precondition you
asserted; and confirmation you did not run the full `just test`, did not touch :35110, and stayed off the
`mistperf` lane's files.
