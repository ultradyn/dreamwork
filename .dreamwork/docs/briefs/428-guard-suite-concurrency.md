# Brief — #428: the guard suite fails under concurrent lanes and passes alone

**Task:** #428 (P2, loop-tooling) — the full guard suite has failed under
concurrent lanes and passed solo twice (`subslog` named in the filing; the
#507 audit later found the same class in burndown/bdhover/markrail and fixed
those three). This lane closes the CLASS, not another instance.

**Lane-owns:** `dev/capture/` (the guard `.mjs` files it converts, plus the
shared helpers `dev/capture/dom.mjs` and `dev/capture/serve.mjs`). Nothing
else. NOT `watch.py` (lane-505impl owns it), NOT the `justfile` (guard
*registration* is lint-checked and unchanged by this work — you are
converting readiness idioms inside existing guards, not adding or renaming
any), NOT `dev/capture/fixture/`.

## The class

The #507 folded hand-off line (`.dreamwork/handoffs.md`, `## Folded`) is the
reference characterisation — read it first. Two readiness layers raced fixed
sleeps under load:

1. **Server readiness** — spawning `watch.py` then `sleep(2500)` + fetch;
   under load python outlasts the sleep → ECONNREFUSED → "threw before
   finishing" over a correct server. The fix idiom is `serveVerified`
   (`dev/capture/serve.mjs`, #461) — 16+ guards already use it.
2. **Render readiness** — `goto … networkidle` + a fixed sleep before the
   first DOM read; networkidle fires when data.json is fetched but the
   client JS that BUILDS the DOM has not run. The fix idiom is the shared
   `waitFor(page, sel, timeout)` in `dev/capture/dom.mjs` (added by #507).

Measured starting point (coordinator, 2026-07-30 10:05): **79 guard files
mention `networkidle`** and ~20+ still call a `sleep(` idiom. Some of those
uses are benign (networkidle followed by a real `waitFor` before any read).
Characterising which is which IS the first increment.

## Shape

1. **Characterise before converting.** Table every guard: readiness idiom
   used (serveVerified / fixed sleep / networkidle-only / networkidle +
   waitFor), whether its first DOM read is gated on a real selector wait,
   and any flake evidence (the #428 filing names `subslog`; the suite has
   named others under load). Commit the table as
   `.dreamwork/docs/findings/428-readiness-census.md` — an absolute path
   into the MAIN CHECKOUT, committed there by the coordinator on merge, so
   ALSO commit it in your worktree.
2. **Convert the offenders** to `serveVerified` + `waitFor`, worst-first
   (any guard with a suite-failure naming it, then any guard whose first
   DOM read has no selector wait). **Zero assertion values or thresholds
   loosened** — a readiness conversion changes WHEN the guard reads, never
   WHAT it asserts. If a conversion seems to require touching an
   assertion, stop and report instead.
3. **Prove under load.** Each converted guard: 5 consecutive solo PASS,
   including runs with a CPU spinner pinning one core (the #532 lane's
   load idiom). Then reds must still fire: for each converted guard pick
   ONE existing red-proof injection (a production line in watch.py or a
   fixture sabotage the guard binds), reintroduce it, watch the guard
   FAIL, restore byte-identical with `cp` (never `git checkout`). If a
   guard has no known injection, say so — do not invent assertion changes
   to manufacture one.

## Rules that have cost batches here

- **Ports 39890-39899**: before ANY guard run, check who owns the range
  (`just reap` reports; lanes are running — 505impl runs its own guards
  solo). Take one free port, ordinary-class: OUT is a fresh `$B/<name>`
  dir and the served fixture is `$B/target` (some guards derive the plant
  dir as `OUT/../target` — replicate that layout or readiness fails for
  harness reasons, not feature reasons). NEVER run the full suite — the
  coordinator owns it (#424).
- **Screenshot contamination**: several guards write screenshots
  repo-relative under `screenshots/`. After solo runs from a worktree
  that's fine; never commit them.
- **A green red-run is a finding, never a relief.** If your injection
  passes, the injection or the check is wrong — name the production line
  the test binds, change THAT line, and watch. The three-shape triage
  (hollow check / bad injection / defense-in-depth) is in
  `.dreamwork/lessons.md` — search "green red-run".
- **Red-proof restore is `cp` from a snapshot taken before the injection**,
  then `git status --porcelain` of the touched file is empty.
- `git commit --only <paths>`; new files need `git add` first. Never
  `attn`. Never `pkill -f`. Never touch the main checkout — work only in
  your worktree.
- Report: append your report to the coordinator inbox (path in your
  dispatch prompt), AND append ONE literal `## Pending` line to
  `/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/handoffs.md`
  (absolute path — it is the main checkout's file; the grammar is in the
  file's header: `- **#428** · landed \`<sha>\` · <date> · by lane-428suite — <what>`),
  and COMMIT that handoffs.md change in your worktree too (the file exists
  in your worktree; commit it there with `--only`).

## Done when

The census is committed; every guard the census marks readiness-defective
is converted or explicitly named as deferred-with-reason; each conversion
has its under-load PASS evidence and its red-still-fires evidence; and the
Pending line names the shas.
