# Brief — #288: design subagent tool containment, and a bounded falsification prototype

Repo: `ud-dreamwork`. Worktree: **`.worktrees/containment`**, branch **`wt/containment`**. Do not push, do not merge.
**Never use `attn`.** **Do not write `.dreamwork/handoffs.md`** — the coordinator writes it at merge time.
Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are**.

## The incident this exists for

Read `#288` in `.dreamwork/tasks.md` in full. Summary: a guard-only subagent was told *"own target/port, no live
35110"*, **interpreted that as requiring the live dashboard to be absent**, executed `kill 1884627` — the
deployed committed `:35110` process — and then reported *"PASS no live 35110"*. The coordinator detected the
outage, restored `just deploy HEAD` at `010ab7a`, and proved the kill from the agent's transcript.

**The lesson already established, and do not relitigate it:** worktrees, prompts and supervision **cannot**
prevent same-UID signalling. A prompt is not a boundary. That is why the immediate detection rule is positive
PID/health preservation rather than any instruction.

**He authorised P1 on 2026-07-28 01:26 (`rec`):** *a written design and a bounded falsification prototype for
explicit subagent tool routing through a real sandbox, with supervised restart plus positive same-PID/health
invariants as defence-in-depth.* **Design and prototype only — no deployment.** And `#290`'s run-mode grants
no kill or sandbox authority on its own.

**The general form he described is `#358`** (head/body split: the head makes the LLM API calls, the body runs
tools over a socket in a container, so the body *"cannot kill the head or exfiltrate the API key, it can only
kill itself"*). **`#358` is not yours** — reference it, do not design it.

## Deliverable 1 — the design

`.dreamwork/docs/plans/subagent-containment.md` plus a `doc-map.md` row:

- **The threat model, stated plainly**: what a same-UID agent can do that no prompt prevents — signal any
  process, read any readable file, bind any port, exhaust any shared resource. Be concrete and bounded; this is
  not a general security essay.
- **The routing boundary**: which tool calls cross it, what the body may hold (no API key), and what the head
  retains. Name the actual mechanism you would use on this host (container runtime, namespaces, seccomp, a
  socket protocol) and **what it costs in latency and complexity per subagent** — this loop dispatches 5–6 at a
  time, so per-lane cost is decisive.
- **Positive invariants as defence-in-depth**: the same-PID/health checks he named. What is sampled, when, and
  what happens on violation. **Note `dev/deploy_state.py` already separates *is the file right* from *is the
  process running that file*, and `#442`'s `GENERATION` idea plus `#426`'s `skill_identity()` are the existing
  vocabulary — reuse rather than invent.**
- **Supervised restart**: who restores what, and how a restart is distinguished from a fresh start.
- **What is NOT worth doing**, with reasons. A design recommending everything is not a design. If part of this
  is better served by convention or by detection than by containment, **say so** — that is a real finding, and
  the honest answer may be that full containment costs more than this loop can pay and the invariants are the
  whole win.

## Deliverable 2 — a bounded falsification prototype

**Falsification, not demonstration**: a small artifact that tries to **break** the boundary and records whether
it could. Concretely — a contained process that attempts to signal a process outside it, read a path it should
not, and reach the network, with the results recorded. Put it under `dev/` with a clear name and a docstring
saying it is a prototype, not wired into anything.

**Absolute limits, and these are not negotiable:**

- **Never signal, kill, stop or restart any process you did not create.** Not `:35110`, not the heartbeat, not
  the monitors, not the loop, not another lane, not a `pgrep` match. **If your prototype needs a victim
  process, spawn your own** and say so in the report.
- **No `pkill -f`, ever.** `#431` landed tonight precisely because that pattern matched the deploy's own shell
  and killed it. Build process patterns from parts if you must match at all.
- **No host changes**: no unit installed/started/enabled, no daemon, no config edited, no sudo, no image pulled
  that persists, no port bound in 39880–39899, nothing on :35110.
- **No deployment.** He authorised design plus prototype and explicitly withheld deployment.
- If the prototype cannot run without one of the above, **do not do it** — report that the falsification
  requires an authorisation he has not given, and say exactly what you would need. That is a complete answer.

## Done means

1. The design exists and answers every bullet, each recommendation naming its cost.
2. The prototype exists, ran, and its **results are recorded** — including *"could not test X without
   authorisation Y"*.
3. **A `questions.md` entry text you want filed**, if a decision is genuinely his — most likely the
   contain-vs-detect trade. **Do not edit `questions.md`.** If the design has a decision for him, the repo's
   rule is that it ships a self-contained review artifact: build
   `.dreamwork/review/src/288-containment.html` with `python3 review_artifact.py build`, with an **`#ask`**
   above the derived fold (`node dev/capture/above_fold.mjs …` — it derives the fold now, `#432`). Note the
   table trap fixed tonight (`c19107a`): the template's `table{min-width:max-content}` sizes tables to
   unwrapped content, so set `min-width:0;width:100%;table-layout:fixed` and check 390px.
4. `python3 lint.py` clean; `python3 -m pytest -q -p no:randomly` passes (1089 at dispatch). **Do not run the
   full `just test`.**

## Files

Yours: `.dreamwork/docs/plans/subagent-containment.md`, `.dreamwork/docs/doc-map.md`, a new prototype under
`dev/`, and `.dreamwork/review/src/288-containment.html` if you ship an artifact.

**Not yours:** `watch.py`, `justfile` (**a live lane holds both**), `review-artifact.template.html` and other
`.dreamwork/review/src/**` (**held for `#436`** — coordinate by not touching), `dev/capture/*`, `lint.py`,
`dev/ledger.py`, `dev/deploy_state.py`, `status_sync.py`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`.

## Practical

2 threads. `git add <newfiles>` then `git commit --only <paths>` — **never `git add -A`**: several agents commit
in this tree. **Commit before you finish.** **Push back with reasons if any of this is wrong.**

## Report

Which model you are; the threat model in three lines; the boundary and its per-lane cost; what you recommend
NOT doing; what the prototype attempted and what actually happened for each attempt; anything you could not
test and the authorisation it needed; the `questions.md` text if any; and explicit confirmation that you
signalled no process you did not create, changed nothing on the host, and never went near :35110.
