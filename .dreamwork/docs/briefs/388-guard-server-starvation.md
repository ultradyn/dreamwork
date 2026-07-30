# Brief — #388: a guard's own watch.py starved at extreme load (ECONNREFUSED)

Lane: lane-388starve (glm-5.2). P3, guards/infrastructure. The filing (`dev/ledger.py get 388`
on the real store) is the spec; its rec and its warning are both binding:

- At load 100+ on 16 cores a guard throws `TypeError: fetch failed [cause] ECONNREFUSED
  127.0.0.1:<port>` — the watch.py the harness spawned never became reachable, or stopped
  being reachable mid-run. Every guard inherits it; the failure arrives as the third verdict
  ("the guard threw"), the worst class we have.
- **Rec: a readiness wait, not a timeout bump** — poll the server's own endpoint until it
  answers, with a bounded deadline, before the first navigation; and make the failure say
  "the server never came up in Ns", not a raw ECONNREFUSED.
- **Measure first**: find whether the refusal happens at STARTUP or MID-RUN — different
  bugs, and the filing is consistent with either.
- **Do NOT make guards more patient in general.** A longer timeout hides a dead server;
  #383's throwing-guard-names-its-exception is what lets us see this class at all.

## Ownership steer (important)

lane-547default currently owns `justfile` (DEFAULT_GUARDS). **Do not edit the justfile.**
Put the readiness wait where guards already share code — `dev/capture/dom.mjs` (the
readiness idioms live there: `waitFor`, `midStates`) or `dev/capture/serve.mjs` if that is
the harness's server-spawn helper (find who actually spawns the fixture server: the
justfile recipe, or a shared module). If the honest fix REQUIRES a justfile change (e.g.
the recipe spawns the server and runs guards with no readiness gate), implement everything
else and FLAG the justfile half to the coordinator in your handoff — do not touch the file.

## Scope

1. **Measure**: reproduce or convincingly characterise startup-vs-mid-run. A load-stress
   probe (burn CPUs, spawn the fixture server, poll it) that reports when the refusal
   happens is a fine deliverable — keep it bounded (seconds, not minutes) and kill
   everything you spawn.
2. **Fix**: one shared readiness helper (e.g. `waitForServer(base, {timeoutMs})` in
   dom.mjs — poll `/` or a cheap endpoint until 200 or deadline; on deadline, throw an
   error whose message says the server never came up in Ns) adopted at the seam where a
   guard run begins (every guard's first navigation, or the single spawn point if there is
   one). Guards that already wait for DOM readiness (`waitFor(p, '.qa')`) still need the
   SERVER readiness first — a dead server fails the fetch before any DOM exists.
3. **Honest failure**: the thrown/named error distinguishes "server never came up" from a
   page fault — that distinction is the point of the task.

## Verification

- Red-first: the readiness helper's deadline path must be provable — e.g. point
  waitForServer at a port with no server and assert the named error (not a raw
  ECONNREFUSED) within the deadline. If you add a test file, it asserts its preconditions
  at runtime. cp-snapshot/sabotage/cp-restore byte-identical for any production-line proof;
  a green red-run is a finding — report it.
- Solo guards only (`DREAMWORK_GUARDS=... DREAMWORK_HUB_GUARDS= just guards 3989X` after
  `ss -ltn` shows the port free); never the full suite; never while another lane runs
  browsers if you can avoid it — and NEVER run a load-stress probe while the coordinator
  or another lane is mid-guard-run (check `ss -ltn` for 39880-39899 first; if busy, defer
  the stress probe and say so).
- NEVER read_file an image. No attn, no pkill -f. Kill every process you spawn (burners,
  servers) — the lane exits with nothing held.
- Commit `git commit --only <paths>` (git add new files first). Append ONE line to
  `.dreamwork/handoffs.md` under `## Pending` before your final commit (#398 obligation).
- Final message: the startup-vs-mid-run finding, the fix shape, red-proof evidence,
  any justfile flag for the coordinator, commit hashes.
