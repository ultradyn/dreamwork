# Brief — #462 increment 2: the staleness row becomes an action, because he said yes

Repo: `ud-dreamwork`. Worktree: **`.worktrees/deployact`**, branch **`wt/deployact`**. Do not push, do not merge.
**Never use `attn` under any circumstances** — the coordinator is the only party that notifies the human.

Lane-owns: watch.py, test_watch.py, watch-design.md, dev/capture/staleremedy.mjs

## Two-way channel — do this first

Load the **`subagent-protocols`** skill (`/home/xertrov/.claude-w/skills/subagent-protocols/SKILL.md`) and
follow **`for-subagents.md`**. **Coordinator inbox:
`/home/xertrov/.cache/agent-comms/ud-dreamwork/coord-inbox.md`** — monitored live. Handshake there **before**
starting, prefix every line `[deployact]`, and create + watch
`/home/xertrov/.cache/agent-comms/ud-dreamwork/deployact-inbox.md` so I can steer you mid-task.

Full report goes **once** to
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`; **state which model you are** at the
top. **Do not write `.dreamwork/handoffs.md`**, `.dreamwork/tasks.md` or `.dreamwork/questions.md` — report
the lines you want added.

**Report a line per increment as it lands, and commit as you go.** Two lanes were killed by an external
sweep at 03:42 tonight with everything uncommitted and their final reports lost — the per-milestone inbox
lines were the only surviving record of what they had done. Assume you may be stopped without warning: an
uncommitted hour is an hour nobody can recover.

## What he authorised, in his words

Read `#462` in `.dreamwork/tasks.md` — the whole entry, including increment 1, which you are extending.

**The ask, answered 2026-07-29 03:46: `rec`.** The `rec` was *"yes, the page may trigger `just deploy` on
click — loopback-only and behind the existing confirmation idiom"*. So the row that today **copies a
command** becomes a row that **runs it**. His original words were *"we should have a task for adding an
'update & reload' button/link"*, and increment 1 deliberately stopped short of that pending his consent.

**What increment 1 already established, and you must not re-litigate:** a deployed dashboard serves a
**snapshot**, so a browser reload and `--autoreload`'s `os.execv` both re-serve byte-identical bytes. "Update"
can only mean *re-snapshot from HEAD and restart*, which is `just deploy`. The gap is already computed by
`serving_report`'s `missing` — **reuse it, do not compute it twice.**

## The hard half is what happens after the click

The server you restart is the server rendering the page he is reading. So:

- **His drafts must survive.** `#269` keys them per target and they survive a restart because a restart
  destroys the *server*, not the loaded document. Verify that claim rather than trusting it — it is the
  claim increment 1's lane got wrong in one direction and then corrected.
- **The page must say what happened, including when nothing does.** The loaded document keeps polling
  `/mtime`; a successful redeploy arrives as a new generation. **A redeploy that fails or never completes must
  become visible in the page**, not stay a spinner forever. Decide the deadline and say why; a deadline is a
  copy decision as much as a timing one, so the message must be in the styleguide's voice, not a status code.
- **Concurrency.** Two clicks, or a click while a deploy is already running, must not run two deploys. There
  is prior art for an arm/cooldown in the run-mode control (`#290` arms for 10s) — **reuse that idiom rather
  than authoring a second one**, and say which you reused.
- **Loopback only.** Trusted-LAN serving exists; this action must refuse from a non-loopback peer, and the
  refusal must be a refusal, not a silent no-op. Assert the refusal in a check.

## The 202 contract applies to this route

`#263`'s E5/E5b landed the rule that a **202 does not mean the write landed**: `res.ok` is true for a
durable rejection, and six routes gate on a `landed` verdict computed once via `writeVerdict(res)`. If your
action posts, it gates on `landed` too — and if it invents its own success test, that is the defect E5b
existed to remove. Read `writeVerdict` before you write a fetch.

## Web UI bar

`CLAUDE.md`: *every contribution to the Web UI must be of EXCEPTIONAL quality; merely functional,
conventional or locally polished work does not meet the acceptance bar.* **Load the relevant design skills**
and read **`watch-design.md`** and **`transitions.md`** before designing.

**A control that appears when the page falls behind is an arrival**, and so is every state it moves through
(idle → armed → running → landed/failed). `transitions.md` has no size floor and its opening section is *how
to check*: an end-state assertion cannot fail on a motion bug, and neither can "did it move" — **sample**.
Reduced-motion parity is part of the work, not a follow-up. Reuse `staleremedy`'s existing gesture rather
than adding a second one beside it.

## Verification

- Extend **`dev/capture/staleremedy.mjs`** (11 checks today) rather than adding a rival guard; if you add
  one, register it in `justfile`'s `DEFAULT_GUARDS` (**56** today) or it gates nothing.
- **Do not actually run `just deploy` in a check.** Drive the route with the deploy command faked, and make
  the fake's parameters part of the check's scope — a fake pinned to success tests only the happy path, and
  `#413` exists because a fake pinned to `409` hid a live defect for hours. Drive **both** a success and a
  failure.
- **Red-proof each check on the production line.** Name the line whose change reds it, change *that*, and
  watch it fail. **A green red-run is a finding, never a relief.**
- **Could your red have been produced against the code as it stood before your diff?** If reaching the
  failure needs a seam your change introduced, the proof is circular — a lane was rejected for exactly that
  tonight.
- **Assert preconditions at runtime, derived.** The gating check needs a state where the page really *is*
  behind; derive it, never assume the fixture is.
- Use `dev/capture/serve.mjs`'s `serveVerified` — **do not spawn-and-sleep**, and note `watch.py` has **no
  `--no-open` flag** (passing one kills your server on an argparse error and your request silently reaches a
  stranger; that cost two false measurements tonight).
- `python3 lint.py --target .` clean; `python3 -m pytest -q -p no:randomly` passing. **Do not run the full
  `just test`.** Bind nothing in 39880–39889; kill what you start by exact pid; check `ss -ltnp` before
  finishing.
- **Do not restart, `pkill` or redeploy the dashboard on :35110** — he is reading it, and this task is
  literally about a redeploy button, so the temptation to test it against the live server is real. Never
  `pkill -f`. Do not touch the heartbeat, the monitors, or the loop.
- Trailer: this adds a capability an existing install did not have and it runs a command — `Feature:` plus
  `Needs: consent` is likely. Decide and say why.

## Files

**Yours:** the four in `Lane-owns:` above.

**Not yours:** `lint.py`, `test_lint.py`, `file-formats.md` (the coordinator holds these for `#468`),
`dev/lane_guard.py`, `user_events/*`, `dev/capture/serve.mjs` and `report.mjs` (use, do not edit),
`SKILL.md`, `DREAMWORK.md`, `.dreamwork/tasks.md`, `.dreamwork/questions.md`, `.dreamwork/handoffs.md`,
`.dreamwork/lessons.md`.

## Practical

- 2 threads. **One commit per increment**, `git add <newfiles>` then `git commit --only <paths>` —
  **`--only`, never `git add -A`**; `--only <directory>` silently skips untracked files.
- **Work only inside `.worktrees/deployact`.** Verify cwd and branch before every write. A lane that edited
  the main checkout tonight aborted a held merge and produced `#465`, whose guard would now catch it.
- ~20 minutes. **Commit before you finish**, and land the smaller coherent half rather than nothing.
- **Push back with reasons.** If the honest conclusion is that running `just deploy` from the page cannot be
  made safe without something he has not agreed to, say so plainly — he authorised the action, not any
  particular cost.

## Report

Say: which model you are; the arm/cooldown idiom you reused and where it is documented; what the page shows
on success, on failure, and on a deploy that never finishes, with the deadline and why; how you proved his
drafts survive the restart; how the loopback refusal is asserted; whether you gate on `landed`; the
transition checks you ran (sampled, not end-state) and reduced-motion parity; for each check the production
line whose change reds it and confirmation no red needed a seam your diff introduced; the derived
precondition for "is behind"; the trailers; and confirmation you worked only in `.worktrees/deployact`
(state the cwd and branch you verified), left nothing listening, never touched :35110, and did not run the
full `just test`.
