# Brief — #462: the dashboard says it is N commits behind and gives him no way to act on it

Repo: `ud-dreamwork`. Worktree: **`.worktrees/updrel`**, branch **`wt/updrel`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: watch.py, test_watch.py, watch-design.md, transitions.md, justfile

## Why you are here, in his words

**Dictated to the dashboard 2026-07-29 02:30, marked next-up and explicitly delegated:** *"re 'this page is 3
watch.py commits behind · serving f9bb49e' on dashboard, we should have a task for adding an 'update & reload'
button/link I think? Please delegate that to a subagent in the near future. I would like it soon."*

Read **`#462` in `.dreamwork/tasks.md`** for the framing. The staleness row already exists and already computes
the gap — **the missing thing is only the action**, which is why he reads it as an obvious omission rather than a
feature request. Find that row in `watch.py` and build outward from what it already knows; do not compute the gap
a second time.

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[updrel]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/updrel-inbox.md` so I can steer you mid-task.

Report a line per milestone (**sources read**, **design set**, **implemented**, **motion verified**,
**committed**). Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which model you are** at the top.
**Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` — report the lines
you want added and I will file them.

## The hard half is not the button

The button is an afternoon. These are the parts that decide whether this is usable:

1. **A reload restarts the server he is reading.** He types into that page. `#269` keys drafts per target
   (`dw:adraft:<target>:<id>` / `dw:draft:<target>`, `watch.py` ~4649) and they are **verified durable across a
   real process restart** — so do not re-solve that, but **do** verify it still holds for whatever restart path
   you build, because a draft lost here is his words lost.
2. **His place must survive it.** Route, scroll, expanded state. A reload that returns him to the top of `/` is a
   worse experience than the stale page he had.
3. **It must say what happened if the restart fails.** A button that silently does nothing on failure is the
   defect this repo names most often. Decide and state where that failure surfaces.
4. **Only offer it when it is true.** The affordance exists when the page is actually behind; when it is current
   there is nothing to offer. That means it **arrives and departs**, which is item 5.
5. **`transitions.md` governs it, with no exception for size.** Read that file **before** designing, and reuse
   the existing idiom rather than authoring a second one. Its opening section is *how to check* — an end-state
   assertion cannot fail on a motion bug and neither can "did it move"; that lesson cost this repo three
   batches. A control that appears when the page falls behind is an **arrival**, not a pop.

## Load the design skills — this is a Web UI change

`CLAUDE.md`'s bar: *every contribution to the Web UI must be of EXCEPTIONAL quality; merely functional,
conventional or locally polished work does not meet the acceptance bar.* Load the relevant design/visual skills
rather than relying on generic frontend defaults, and read **`watch-design.md`** (the authoritative styleguide —
tokens, type, components, copy voice, per-surface contracts) plus **`transitions.md`**. `watch-design.md` stays
single-source: **document the change in the same commit that makes it**, which `just audit-styleguide` measures.

Copy voice matters here. "update & reload" is his phrasing for the idea, not necessarily the label — decide the
label from the styleguide's voice and say why.

## Decide with an IGC, do not guess

`igc-method.md` / `igc-concepts.md` in the repo root: (Idea, Goal, Context), per-cell `✔` non-refuted / `✘`
refuted **with the decisive error written out** / `?` a TODO, an `All` rollup, breakpoints instead of
maximisation, **never a score**.

The fork worth an IGC is **what "update" means**, because the rivals differ in risk, not in polish: reload the
browser page only; restart the server and reload; `git pull`-then-restart; or hand him the command to run. Goals
that are binary and will refute at least one rival: *he does not lose typed text*; *he does not lose his place*;
*a failure is visible*; *the loop's own machinery is never restarted by a UI action* (the standing rule — a
subagent never stops or restarts the heartbeat, the monitors, or the loop, and a button must not do it either).
That last one is a real constraint on the design space, not a formality.

If the honest outcome is that the safest useful version is smaller than what he pictured — a link that reloads
the page, plus the exact command for the server half — **that is a complete answer**; ship it and say why the
bigger version was refused, naming the decisive error.

## Verification

- **Red-first.** For each behaviour, name the exact production line whose change makes your check fail, change
  *that* line, and watch it fail. **A green red-run is a finding, never a relief** — twice tonight a proof came
  back green because the injection never reached the code.
- **Motion is checked by sampling, not by end state.** `transitions.md` opens with how; follow it, and cover
  **reduced-motion parity**.
- **Assert each check's precondition at runtime**, derived — never a literal tuned to today's tree.
- **If you start a `watch.py` and probe it, prove the responder is yours.** Use
  `dev/capture/serve.mjs`'s `serveVerified` (landed tonight as `#461`) instead of spawn-and-sleep. Two orphaned
  servers on 39895/39896 made a correct change read as broken twice tonight, and `watch.py` has **no
  `--no-open` flag** — passing one kills your server on an argparse error and your request reaches a stranger.
- A new guard, if you add one, must be **registered in `justfile`'s `DEFAULT_GUARDS`** (54 today, each needing
  its file) or it gates nothing.
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`.** Bind nothing in 39880–39889 or 39890–39899; kill everything you start by exact pid.
- Do **not** restart, `pkill` or redeploy the dashboard on **:35110** — **he is reading it, and this task is
  about restarting a dashboard, so the temptation is real.** Test against your own instance only. Do not touch
  the heartbeat, the monitors, or the loop. Never `pkill -f` — build process patterns from parts.
- Trailer: a new control on an existing install is likely `Feature:`; if it needs consent to restart anything,
  `Needs: consent`. Decide and say why.

## Files

**Yours:** `watch.py`, `test_watch.py`, `watch-design.md` and `transitions.md` **only** to document what you
change, `justfile`'s `DEFAULT_GUARDS`, and your new `dev/capture/<guard>.mjs`.

**Not yours:** `test_user_events_http.py`, `user_events/*` (**lane E2 holds those and is mid-increment in
`watch.py`'s HTTP paths — keep your diff out of those paths so the merge stays mechanical**), `lint.py`,
`file-formats.md`, `migrations/*` (the `mignotice` lane), `review_artifact.py`, `.dreamwork/review/**`,
`dev/capture/serve.mjs` and `report.mjs` (use them, do not edit them), `SKILL.md`, `DREAMWORK.md`,
`.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/handoffs.md`.

**You share `watch.py` with lane E2 by worktree, not by file lock.** That is deliberate — he wants this soon —
and it means the merge is mine to resolve. Keep your changes localised and say in your report exactly which
regions of `watch.py` you touched.

## Practical

- 2 threads. `git add <newfiles>` then `git commit --only <paths> -m 'feat(#462): …'` — **`--only`, never
  `git add -A`**: other agents commit in this tree, and `--only <directory>` silently skips untracked files.
- **Commit before you finish**, and **land what is done even if the whole thing is not** — two lanes tonight
  exited with correct work uncommitted.
- **~20 minutes per increment.** The right first increment is the affordance appearing and departing correctly
  with nothing behind it; the restart is the second.
- **Push back with reasons.** A refusal with evidence is a complete answer, and the most valuable lanes tonight
  refused what they were handed.

## Report

Say: which model you are; the IGC with each decisive error and the surviving idea; what "update" ended up
meaning and what you refused; where the staleness row is and how you reused its computation; how drafts, route,
scroll and expanded state survive; what he sees when the restart fails; the transition idiom you reused and how
you checked it (sampled, not end-state) including reduced-motion; the production line whose change reds each
check; which regions of `watch.py` you touched; the trailer you chose; and confirmation you never touched
:35110, the heartbeat, the monitors or the loop, killed every server you started by exact pid, and did not run
the full `just test`.
