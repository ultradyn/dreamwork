# Brief — #508: `just deploy` silently never cycles the server — success is reported against the OLD process

Lane-owns: `dev/deploy_state.py`, `test_deploy_state.py`, `justfile` (the `deploy` recipe only), `.dreamwork/handoffs.md` (append ONE `## Pending` line)

## The defect (observed, ranked P1 because the deployed dashboard is what the human SEES)

`just deploy` is the only route new code has to the dashboard the human
watches. Today it is a lie: it reports `deployed <rev> on :<port>` while the
process serving that port is the OLD one. Symptoms as filed:

- The stop-check races the server's autoreload: the recipe's `--stop-deployed`
  signals the pid listening on the port, but the old server was started with
  `--dev`, and `--dev` implies autoreload (watch.py line ~14605:
  `if args.autoreload or args.dev:`) — so something respawns after the stop.
- The replacement `nohup python3 "$snap" …` then dies on bind (the port is
  held again), and its death is invisible to the recipe.
- The readiness loop (`curl -sf … && echo "deployed …"`) passes against
  whatever IS listening — the old, respawned process. Success is printed;
  `deployed.py --target .` keeps reporting the deployment as stale.

The human reads the DEPLOYED dashboard as the state of the repo (the repo's
own lesson, twice: #129, and "the human sees the deployed dashboard, which may
be older than HEAD"). A deploy that did not deploy is worse than no deploy.

## What to do

1. **Root-cause first, in writing** (in your commit message): reproduce the
   failure in a FIXTURE (never against the live server — see Constraints).
   Answer precisely: after `--stop-deployed` returns, what is still holding
   the port, and why? (Hypotheses to test, not assume: an autoreload
   supervisor/child split where the stop kills one and the other respawns;
   the `sleep 1` being shorter than the socket's TIME_WAIT or the
   supervisor's respawn latency; the new server's bind failure going
   unnoticed because `nohup … &` detaches it and nothing checks it stayed
   up.) Name the mechanism you CONFIRMED and the evidence.
2. **Fix so the recipe cannot report success against the wrong process.**
   The acceptance bar is not "the race is less likely"; it is that the
   success line is now TRUE BY CONSTRUCTION. The natural shape (yours to
   refine, not to bypass):
   - after the stop, WAIT for the port to be free (bounded), refusing if it
     never frees;
   - after the start, verify the LISTENER'S IDENTITY — pid, and that its
     argv is the new snapshot, and that it is the process the recipe just
     spawned (or its re-exec'd descendant) — not merely that something
     answers on the port. The recipe already has the "identify by listening
     socket, verify via /proc/<pid>/cmdline" machinery (#431) — reuse that
     discipline for the readiness half. A `curl` 200 is a liveness check,
     not an identity check.
   - if the new server died on bind, the recipe must FAIL LOUDLY (check
     serve.log / the child's liveness before declaring success).
3. **Consider the autoreload question head-on**: should the deployed server
   run with `--dev` (autoreload) at all? If autoreload under a swapped
   snapshot is the race's whole cause, removing `--dev` from the recipe's
   start line may be the fix — but check first why it is there (git log the
   recipe line; #480 and deploy_state.py's docstring line ~36 mention
   autoreload re-exec'ing into OLD code — there is history you must not
   re-litigate blindly). Whatever you decide, the commit message states the
   reasoning and the identity-check stands regardless.

## Tests (the repo's verification law applies — read CLAUDE.md first)

Extend `test_deploy_state.py` (and/or a new test file you own — add it to
Lane-owns if so). You need tests that would have caught THIS defect:

- a fixture server on a PRIVATE port (NOT 39890-39899 — that range belongs
  to the guards; NOT the live port; bind 127.0.0.1, port 0 to get a free
  one) that the stop+start+identify flow cycles, asserting the listener
  BEFORE and AFTER are different pids AND the after-pid's argv is the new
  snapshot;
- the failure mode: a fixture that simulates the old process refusing to
  die (or respawning) must make the flow REFUSE, loudly — never print
  success;
- assert at runtime the preconditions each test depends on (the fixture
  server really is listening, the old pid really is dead when you claim
  it is).

**Red-proof every test**: name the production line, sabotage, watch it fail,
restore byte-identical with `cp`. If a test cannot be made to fail by ANY
production change, it is hollow — rewrite it. A green red-run is a finding,
never a relief.

## Constraints

- **NEVER run `just deploy`, and never signal any process, in the main
  checkout or against the live dashboard port** (`cat .dreamwork/watch-port`).
  The deployed server is the human's window; your fixtures run entirely in
  temp dirs with their own ports. The deploy recipe edits are reviewed by
  diff, not exercised live.
- Branch `lane-508deploy` off master; `git commit --only <paths>`.
- A lane never runs `just test` or the guard suite. Targeted pytest +
  `python3 lint.py` only.
- Append ONE `## Pending` line to `.dreamwork/handoffs.md` (append-only;
  never rewrite; the literal path is `.dreamwork/handoffs.md`) and COMMIT it
  among your paths.
- If the root cause turns out to live in watch.py's autoreload (not the
  recipe/deploy_state), STOP and report — you do not own watch.py.

## Report back

The confirmed mechanism (one paragraph, with the fixture evidence), the fix
shape and why success is now true by construction, the tests added with their
red-proofs (production line named per test), the `pytest -q` summary line for
your files, and anything you found that says the deployed server should or
should not keep `--dev`.
