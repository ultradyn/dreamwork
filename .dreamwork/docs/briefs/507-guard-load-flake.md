# Brief — #507: burndown + markrail (+bdhover/motion) guards flake red under chronic load — find the mechanism, fix the harness, never loosen an assertion

Lane-owns: `dev/capture/burndown.mjs`, `dev/capture/bdhover.mjs`, `dev/capture/markrail.mjs`, `dev/capture/lib/` (if a shared harness helper exists — extend Lane-owns in your handoff line if so), `.dreamwork/handoffs.md` (append ONE `## Pending` line)

## The defect (filed from the coordinator's gate log, with one hard-won caveat)

Under chronic load (~35+ on 16 cores — this host runs a 5-7 lane fleet), the
content guards flake red: `burndown`, `markrail`, `bdhover`, and motion guards
have all failed under load and passed on the identical tree at lower load.
That is the filed observation. **The caveat, and it cost a real regression:**
a "flake" claim must be verified against a pre-merge baseline, never assumed —
the coordinator triaged a bdhover red as this flake and it was a REAL 390px
overflow (merged, then reverted and fixed). So your first job is not to make
the red go away; it is to say WHAT the red is made of.

## What to do

1. **Reproduce and characterise.** Run the named guards (your own guards,
   solo — see Constraints) under induced load (e.g. `stress-ng`/`yes` workers
   to push loadavg past 30) and at rest, same tree, N runs each. For EVERY
   failure, record the failing assertion and the actual vs expected values.
   The question that decides everything: do content checks fail because the
   measured content is genuinely different (a real timing-dependent rendering
   difference — interesting, report it), or because the measurement ran
   before the page/server was ready (a harness defect — the likely case:
   a slow server under load serves late, the guard measures a half-rendered
   page, the content assertion fires)?
2. **Fix the mechanism, at the harness layer.** If it is readiness: the
   guards must WAIT for the condition they measure (deterministic readiness
   — the server serving, the data.json present, the specific DOM the
   assertion reads rendered) rather than racing a fixed delay. Whatever you
   add must be shared (one helper the named guards use) rather than four
   copies of a wait.
3. **NEVER loosen an assertion to buy a pass.** A guard that only reddens
   under load is the #203 failure family the justfile names; a guard whose
   assertion was weakened to stop flaking is worse — it is green over the
   defect it was written for. If an assertion genuinely cannot be made
   load-robust without losing its meaning, STOP and report; the coordinator
   decides, not the lane.

## Tests and red-proofs (the repo's verification law applies — read CLAUDE.md)

- Every harness change keeps its teeth: after your fix, reintroduce a defect
  each guard was written for (pick one named production sabotage per guard
  you touched — e.g. burndown's slice, bdhover's overflow) and watch the
  guard STILL fail — at rest AND under induced load. A fix that makes the
  guard pass-under-load but also pass-over-defects is the born-hollow trap
  and is worse than the flake.
- Name each red line in your report: production line sabotaged, guard run
  (rest + load), failure observed, byte-identical `cp` restore.
- Evidence bar for "fixed": the named guards pass N>=5 consecutive runs
  under induced load >= 30 on the merged tree, and the red-proofs above
  still fire under the same load.

## Constraints

- Branch `lane-507flake` off master; `git commit --only <paths>`.
- You may run YOUR OWN guards solo: `DREAMWORK_GUARDS=burndown,bdhover,markrail
  DREAMWORK_HUB_GUARDS= just guards 39899` — CHECK the port range is free
  first (39890-39899); never run the full suite, never another lane's guard
  (512show, 514wake, 508deploy are in flight — none owns guards, but check
  anyway), never `just test`.
- Induced load must be cleaned up: every `stress-ng`/`yes` you spawn, you
  kill by its own pid. Never `pkill -f`.
- Do NOT touch watch.py, the justfile, or any pytest file — the flake is a
  guard-harness defect until proven otherwise; if you prove it lives in
  watch.py's serving, STOP and report.
- Append ONE `## Pending` line to `.dreamwork/handoffs.md` (append-only;
  never rewrite; the literal path is `.dreamwork/handoffs.md`) and COMMIT it
  among your paths.

## Report back

The characterisation table (guard × load × runs × outcome × failing
assertion), the mechanism confirmed (one paragraph), the fix shape, the
red-proofs (production line, rest+load results, restores), the N-run
under-load evidence, and anything that says a content difference is REAL
timing-dependent rendering rather than harness readiness (that would be a
watch.py finding — report only).
