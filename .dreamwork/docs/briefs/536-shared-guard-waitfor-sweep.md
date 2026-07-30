# Brief — #536 per-guard waitFor sweep (the #428 deferred half)

**Lane-owns:** `dev/capture/` (the guard files the census enumerates for the
sweep — declare any file beyond them before touching it; `serve.mjs` and
`dom.mjs` are shared primitives that should need NO change — if one does,
stop and report instead)
**Read, do not edit:** `.dreamwork/docs/findings/428-readiness-census.md`
(the enumeration — your work list), `dev/capture/serve.mjs`,
`dev/capture/dom.mjs`, the nine guards #428 already converted
(`subslog.mjs`, `posture.mjs`, `bdinput.mjs`, `dashboard.mjs`,
`devoverlay.mjs`, `morph.mjs`, `morphhold.mjs`, `motion.mjs`,
`projtitle.mjs` — they are the idiom, follow them exactly).

## Task

#536 (open in the store, verified 2026-07-30): the #428 lane closed the
SERVER readiness layer in full (own-server guards → `serveVerified`) and
converted the render layer for the 8 + subslog. It DEFERRED the ~40
shared-server render guards still on `goto networkidle` + fixed sleep →
direct reads (qacard, reflow, headertravel, states, etc. — the census
tables every one). Convert each deferred guard's post-networkidle fixed
sleep to `waitFor(page, sel, timeout)` (`dom.mjs`, the #507 idiom) on the
selector that guard reads first. These guards take their server from the
harness (the justfile owns server readiness), so the ONLY layer in scope
is the render gate.

**Zero assertion values or thresholds may change.** The diff discipline
the coordinator will verify at the gate: deletions are sleep/spawn/
readiness lines only; insertions are `waitFor` imports + calls + the
explaining comment. If a guard's first read genuinely has no stable
selector to wait on, name it in your report with the reason — do NOT
invent a looser assertion to make the conversion work.

## Hard constraints (the repo's, all measured)

1. **Worktree only.** Edit nothing in the main checkout. Commit with
   `git commit --only <paths>` (new files need `git add` first).
2. **Red-still-fires per converted guard.** For EACH guard you convert,
   one content sabotage (cp snapshot → inject into watch.py or the
   fixture → run the guard, watch it FAIL → cp restore, byte-identical,
   `git status --porcelain` clean). Name the sabotaged line in the
   report. A green red-run is a finding, never a relief — the #428 lane
   hit one honestly (motion binds row MOVEMENT, not the .gsub subject it
   first injected) and re-traced to a check the guard does bind; do the
   same if you meet one.
3. **Solo runs only, after checking the range.** Each guard:
   `DREAMWORK_GUARDS=<name> DREAMWORK_HUB_GUARDS= just guards <port>`
   after `ss -ltn | grep 3989` shows 39890-39899 free; one guard at a
   time; NEVER the suite, NEVER `just test` (the coordinator owns both).
   Evidence bar per guard (the #428 lane's): 5× solo PASS, at least 2
   under a 1-CPU-spinner load, 0 FAIL; report the check counts.
4. **pytest + lint only otherwise:** `python3 lint.py` must show the
   guard-registration rows OK and no new findings.
5. **Hand-off:** append ONE line to the main checkout's
   `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/handoffs.md`
   `## Pending` (absolute path — relative writes your worktree's copy)
   and COMMIT it among your paths.
6. No `attn`, no `pkill -f`. Report durable state changed. Note the
   model running you is glm-5.2 (from the dispatch record — a lane
   cannot know its own model, so repeat it, don't derive it).

## Acceptance

- Every guard the census tables as deferred-and-convertible is converted
  (or named with its reason); the conversions are idiom-identical to the
  nine already-landed ones; zero assertion drift (the coordinator scans
  the diff for it); the red-still-fires + load evidence per guard is in
  the report; lint registration OK (count unchanged unless you added
  one — you should not need to).
