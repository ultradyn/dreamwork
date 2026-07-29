# Brief — lane-431deploy: `just deploy`'s `pkill -f` kills the shell that mentions the snapshot (#431)

**Lane-owns:** the deploy recipe in `justfile` + any deploy helper script it
calls (e.g. `dev/deploy_state.py` ONLY if the kill logic lives there — locate
it first) + a new guard/test file under `dev/` if the fix needs one. Do NOT
touch `watch.py`, `test_watch.py`, `lint.py`, `test_lint.py`,
`file-formats.md`, or `status_sync.py` (other lanes own those this window).

**Model:** llmp-glm-5-2 · **Isolation:** worktree (coordinator merge-gates).

## The bug (from the ledger, measured 2026-07-28 18:16)

The deploy recipe runs `pkill -f "$(basename "$snap")"` where the basename is
`ud-dreamwork-watch.py`. `pkill -f` matches the WHOLE command line of every
process, so it kills anything that merely names the file — an agent shell that
assigned the path to a variable, an editor, a `grep`. It killed the shell
running the deploy itself: exit 144 (128+16 SIGTERM), recipe cut off partway —
and a half-completed deploy is the one failure that leaves the human's
dashboard down. It only fires when the caller's own command line mentions the
basename, so it is rare, silent, and self-interrupting.

## The fix direction (yours to refine, the invariant is not)

**Kill by identity, not by name-substring.** The process deploy must stop is
the server bound to the deploy port — find it by what it IS, not by a string
in its argv. Strong candidates:

- look up the listener on the deploy/watch port (the repo already reasons
  about port ownership for the guarded ranges — see how the guards and
  `just deploy` itself check ports) and signal that pid; or
- `pgrep -f` with the FULL anchored path plus exclusion of $$ and its
  ancestry — strictly weaker, use only if port-lookup is unworkable.

The invariant the merge-gate will check: **a process whose command line
contains the snapshot basename but which is not the server MUST survive the
kill step**, and the actual server MUST still be stopped (the fix that
"never kills anything" is a failure, not a fix — deploy must still deploy).

## Constraints (hard)

- **NEVER run `just deploy` itself.** Port 35110 deploys are the
  coordinator's, standing-authorized only there. Test the kill-step logic in
  isolation against processes YOU spawn on unprivileged high ports outside
  39880-39899 and 35110 (e.g. 42xxx), and clean them up.
- Never `pkill -f` anything in your own testing except against your own
  planted decoys by exact pid.
- Red-first: write the decoy-survival guard BEFORE the fix and watch it fail
  against the CURRENT recipe logic (you may invoke the recipe's kill step
  extracted, or a test harness that runs the same command the recipe runs —
  name in your report exactly which production line you exercised).
- Small committed increments, `git commit --only <paths>` (new files need
  `git add` first).

## Acceptance criteria (measurable)

1. A guard/test that plants a decoy process whose cmdline mentions
   `ud-dreamwork-watch.py` and asserts the decoy SURVIVES the recipe's kill
   step while a planted fake server (the thing listening on the deploy
   port) is stopped. Red against the old logic, green against the new.
2. The guard names the production line it exercises, per the repo's
   structural-red rule.
3. `just deploy`'s recipe still stops the real server (argued by the guard's
   fake-server half, since you may not run a real deploy).
4. Full `just test` green in your worktree (the suite binds 39890-39899 /
   39880-39889 — check `lsof -i :39890-39899` first; if occupied, run only
   `pytest` + `lint.py` and say so in the report).
5. `git diff --stat` touches only your owned paths.

## Hand-off obligation (#398)

Final report in `.dreamwork/handoffs.md` format: what changed, the red/green
evidence (commands + output), the production line the guard exercises, and
anything you did NOT do. The coordinator merge-gates from your worktree.
