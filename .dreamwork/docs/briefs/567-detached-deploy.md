# Brief #567 — the page-triggered deploy must survive the death of the server that spawned it

Origin: human friction, filed #567 (P1, bug). He clicked "cancel update"
right as/after the arm hit 0; the POST /deploy had already fired; the
deploy stopped the old server and died mid-recipe — his dashboard dark
until the coordinator redeployed from the shell.

## Lane-owns

- `watch.py`, **deploy-runner region only**: `_default_deploy_runner`
  (~11195-11210), `start_deploy` (~11213-11237), and if needed the
  `_handle_deploy` docstring (~15071-15081) to stop half-anticipating
  the death and state the real contract.
- Tests: the deploy-runner tests (extend the existing home; the #520
  autoreload-standin idiom in test_deploy_state.py is the reference for
  process fixtures).

**Explicitly not yours:** the justfile deploy recipe (coordinator-owned;
the fix should not need it — say so if you judge otherwise), the
burndown region (lane-559 live), the chat region (lane-562 live), the
dashboard questions region (lane-564 live), `transitions.md`,
`watch-design.md`, `file-formats.md`, `lint.py`, the ledger. FLAG, never
edit.

## The defect (evidence + code)

Evidence from the live incident (2026-07-31 00:38-00:47): the deploy
staged siblings + a fresh snapshot at 00:38 (ship-siblings and
assert-importable completed), `--stop-deployed` killed the old server —
and the recipe never ran `mv` / start / verify. No new process, no
`.tmp`, `serve.log` untouched.

Code: `start_deploy` runs the runner in a **daemon thread inside the
server process**, and `_default_deploy_runner` does
`subprocess.run(["just", "deploy"], capture_output=True, …)`. The
recipe's `--stop-deployed` kills the very process that (a) owns the
runner thread and (b) holds the read end of the child's stdout/stderr
pipes. The next print after the stop (`--stop-deployed`'s own progress
lines) lands on a broken pipe → SIGPIPE → the recipe dies mid-flight,
before `mv`. The thread dying with the process is the second blade of
the same scissors. `_default_deploy_runner`'s docstring even says "May
kill this process — that is the recipe's job" — the knowledge existed
and was never carried to the spawn.

## The act

Detach the runner from the server's lifetime:

- Spawn `just deploy` with `start_new_session=True` (its own process
  group — no signal aimed at the server can reach it) and its output to
  a **file**, never a pipe the dying server was reading (a `deploy.log`
  beside the deployed dir's `serve.log`, or the target's `.dreamwork/`;
  pick one, state the choice).
- Fire-and-forget: `subprocess.Popen` without `communicate`/`run`'s
  wait — the POST already returns before the runner finishes and
  success for the client is the new GENERATION on /mtime, not the
  runner's exit. No client change. No timeout that outlives the spawner.
- The single-flight slot (`_deploy_inflight`) stays as-is — but note in
  the report what releases it now (the thread can still wait on the
  Popen; when the server dies mid-deploy the slot dies with the process,
  which is correct: the new server starts with a clear slot).
- Update the two docstrings (`_default_deploy_runner`, `_handle_deploy`)
  to state the contract the code now keeps.

## Verification (the repo's discipline, all of it)

- **Born-red, and the red must be the INCIDENT, not a unit smell:**
  build the standin fixture — a parent server process that spawns the
  runner against a fixture deploy whose recipe prints after it stops the
  parent (the #520 autoreload-standin idiom). Current code: the recipe
  dies after the stop (assert: no ship, no new listener). Fixed code:
  the deploy completes end-to-end after the parent's death — assert the
  new process is listening and identity-verified, and assert the
  fixture's deploy output really reached its log file (the pipe-SIGPIPE
  mechanism is the thing being pinned; a test that never exercises a
  print-after-stop is born hollow).
- **Assert preconditions at runtime:** the standin really died; the
  child really outlived it (reparented); the fixture recipe really did
  print after the stop.
- **Red-proof:** name the production line each test binds
  (`start_new_session` / the output-to-file), `cp`-backup, sabotage,
  watch the discriminating tests fail — **a green red-run is a finding,
  never a relief** — `cp`-restore, `cmp` byte-identical. ALL
  sabotage/restore inside YOUR worktree; verify `pwd` first.
- Existing deploy tests (single-flight, E2Shadow route table, loopback
  gate) must stay green unchanged.
- No ports bound except a free one for your standin fixture (39xxx
  outside 39880-39899); never touch :35110; never `pkill -f`; never
  `attn`; never the full coordinator suite.
- NEVER read_file an image.

## Handoff (#398)

`## Pending` line appended to the literal path `.dreamwork/handoffs.md`:
task id, bare shas, no parentheticals, no model claims.
`grep -nE '^(<{7}|>{7}|={7}|\|{7})' .dreamwork/handoffs.md` empty before
finishing. Commits `git commit --only <paths>` (new files `git add`ed
first). Report: commits (bare shas), born-red + red-proof evidence with
named production lines, the spawn contract as shipped, the log-file
choice, FLAGs, found-not-fixed (incl. the "did page-deploy EVER work"
post-mortem question if your fixture answers it).
