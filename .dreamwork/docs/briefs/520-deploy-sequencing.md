# Brief — #520: deploy recipe ships the snapshot before stopping the old server

**Lane-owns:** `justfile` (the `deploy` recipe ONLY), `dev/deploy_state.py`,
`test_deploy_state.py`, `.dreamwork/handoffs.md`. Nothing else.

**Task (from the store, P2):** the recipe ships the new snapshot
(`ship-siblings` + `mv $snap.tmp $snap`) BEFORE `--stop-deployed` runs. Against
any autoreloading occupant (the old `--dev` server was one), the `mv` triggers
an in-place `os.execv` of the very process the recipe is about to stop —
arming the race the #508 guards then have to detect. The first identity-verified
deploy (2026-07-30 07:38) hit exactly this: stop sampled the flicker ("nothing
to stop"), `wait-port-free` correctly refused, and a human step (guarded stop +
retry) was needed. The ordering is wrong-by-construction even though today's
deployed server no longer runs `--dev`.

**Chosen shape (decided here):** stop FIRST, ship SECOND, start THIRD, verify
LAST. Concretely, the recipe's order becomes: resolve snapshot path →
`--stop-deployed` → `--wait-port-free` → ship siblings + `mv` → start
(`nohup … &`) → `--verify-deployed --expect-pid`. The identity checks from
#508 are LOAD-BEARING and stay exactly as they are — you are reordering, not
weakening. One subtlety to solve honestly: `ship-siblings`/`mv` currently also
serves the "snapshot matches rev" purpose BEFORE the stop (check what
`--resolve-snapshot` vs ship actually need — if stop needs the snap path only,
not the shipped content, the reorder is clean; if something in the stop path
reads shipped content, say so in your report and pick the order that keeps the
stop honest).

**Acceptance (all required):**
1. `test_deploy_state.py` gains a test that reads the justfile recipe and
   asserts the ORDER: stop verb appears BEFORE the ship step, ship BEFORE the
   start, start BEFORE verify (derive the four anchors from the recipe text at
   runtime — a literal line-number assertion is a check with an expiry date).
2. The #508 identity tests (9) all still pass UNCHANGED — any change to them
   is a finding you must justify in the handoff.
3. A fixture test (the #508 lane's fixture idiom — real processes on
   127.0.0.1:0 ports, never the live port): an autoreloading-standin occupant
   + the NEW ordering → the deploy sequence completes with identity verified
   and no manual step. Assert the standin actually re-exec'd (the precondition
   — otherwise the test is vacuous).
4. Every added/changed check red-proved by injection + cp restore; each red
   names the line injected.
5. `git commit --only <paths>`; `.dreamwork/handoffs.md` Pending line
   `· landed \`<sha>\` · … · by lane-520deploy —`.

**Never:** run `just deploy` (the coordinator deploys); touch the live port
35110 or any process on it; touch watch.py; weaken any #508 check; bind ports
outside your fixtures' 127.0.0.1:0.

Model for the record: glm-5.2 (dispatch record — do not self-report a model).
