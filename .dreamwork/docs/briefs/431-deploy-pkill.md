# Brief — #431: `just deploy`'s `pkill -f` kills any process that merely mentions the snapshot

**Lane-owns:** `justfile`, `dev/deploy_state.py`, `file-formats.md`, new helpers under `dev/` (the
"Files — Yours" section below, declared in #465's vocabulary; added 2026-07-30 when a revert re-committed
this brief inside the guard's window — the lane landed at `522d30d`).

Repo: `ud-dreamwork`. Worktree: **`.worktrees/deploykill`**, branch **`wt/deploykill`**. Do not push, do not merge.
**Never use `attn` under any circumstances.** Report by appending **once** to the absolute path
`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/inbox.md`, and **state which model you are** at the
top — a lane report today was labelled `grok` when `glm52` was dispatched and I am tracking that.
**Do not write `.dreamwork/handoffs.md`** — the coordinator writes that at merge time. Inbox and hand-off
paths for a worktree lane are absolute, per `SKILL.md` (#405).

## The defect, and it has fired four times today

`just deploy`'s `pkill -f <snapshot pattern>` matches **any** process whose command line merely *mentions*
the pattern — including the shell running the deploy, an agent's own `pgrep` check, and (twice today) a
process whose **comment** contained the string. One instance killed a coordinator shell with exit 144.
Read `#431` in `.dreamwork/tasks.md` for the record.

`pkill -f` is the wrong instrument: the pattern is matched against the full command line of every process,
so the matcher matches the matcher. Bracket tricks (`[j]ust`) do **not** fix it — the literal reappears in
whatever text explains the trick.

## What to build

Make the deploy stop **only the process it deployed**. Your design, but state the reasoning:

- **Prefer a pidfile** written by the server it starts, verified before signalling — a pid alone is
  ambiguous after a wrap-around or an `os.exec`, so check the pid is actually the server (`/proc/<pid>/cmdline`
  or `deploy_state.py`, which already separates *is the file right* from *is the process running that file*).
- **Or** the listening socket: whatever owns the deploy port is the thing to stop (`ss -ltnp`, `fuser`).
  Note `.dreamwork/watch-port` records the port.
- Either way: **no `pkill -f` against a pattern that could match the caller.** If any pattern survives,
  build it from parts and say why it cannot self-match.
- **Fail loudly if the target cannot be identified.** Killing nothing and saying so beats killing the shell.

## Done means all of these

1. `just deploy` stops only its own server; a shell whose command line contains the snapshot path survives.
2. **Red-first, and name the production line.** Reinstate the `pkill -f` form and show the self-match
   occurring (a decoy process whose command line merely mentions the pattern is killed), then show it
   surviving after your fix. **A green red-run is a finding, never a relief** — if your check passes with
   the old form in place, the check is not reaching the code and that is the more valuable result.
3. **Assert the check's precondition**: that the decoy process was actually alive and matched the pattern
   before the stop step. A check that silently had no decoy passes forever.
4. **DO NOT stop, restart, redeploy or `pkill` the live dashboard on :35110**, and do not touch the
   heartbeat, the monitors or the loop. Test against **your own** server on an ephemeral port outside
   39880–39899. This is the one task where an over-broad test command is itself the bug — be careful.
5. `python3 lint.py` clean and `python3 -m pytest -q -p no:randomly` passes (1061 at dispatch). **Do not run
   the full `just test`.**
6. A commit that changes what an existing install must do carries a trailer: `Migration:`, `Feature:`, or
   `Needs: config|consent`. A pidfile is likely `Migration:` — decide.
7. If the loop writes a pidfile and a tool parses it, **`file-formats.md` states its shape in the same
   commit** — the standing rule, checked by `lint.py`.

## Files

Yours: `justfile`, `dev/deploy_state.py`, `file-formats.md`, and any new helper under `dev/` plus its
`DEFAULT_GUARDS`/`lint.NOT_GUARDS` registration if it is a `.mjs` guard.

**Not yours:** `watch.py`, `lint.py`, `.dreamwork/tasks.md`, `.dreamwork/questions.md` — report exact lines
instead of editing them.

## Practical

- 2 threads. `git add <newfile>` then `git commit --only <paths> -m 'fix(#431): …'` — **`--only`, never
  `git add -A`**: other agents commit in this tree.
- **Commit before you finish.** A lane today did 24 turns of correct work and exited without committing.
- **This should be small.** If it grows, land the stop-the-right-process half and say what you left.
- **Push back with reasons if any of this is wrong.** Every lane today that refuted its brief was right to.

## Report

Say: which model you are; the mechanism you chose and why; the exact production line whose change reds your
check; the decoy-precondition assertion; the trailer; and confirmation you never touched :35110, the
heartbeat, the monitors, or the loop.
