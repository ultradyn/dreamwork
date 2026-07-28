# The guard suite under concurrent lanes (#428)

Status: increment 1 **landed** `1454717`. The full fix surface is enumerated here
rather than absorbed, because a count of the exposed surface is worth more than
one fixed test.

## The defect, measured

`test_lint.py::TestTheBugItWasBuiltFor::test_this_repo_passes_its_own_linter`
FAILED in a full suite run at 04:55 (eight lanes out) and PASSED alone seconds
later, with `lint.py --target .` clean either side. The cause is not load and
not a flake: **that test lints the LIVE working tree**, and during the run
another lane committed `Lane-owns:` lines to 44 briefs while others wrote their
own files. The tree the assertion was about changed underneath it.

This is a different failure shape from the first two `#428` instances (the
frame-sampling guards). Those were *"passes in isolation"* with no established
mechanism. This one is **state sensitivity with a measured mechanism**, and it
is guaranteed to recur: the human asked for up to 8 concurrent lanes, so a test
that reads mutable shared state during a lane's commit is a false red **by
design**.

Why a false red is worse than a missing check here: there is no CI, so this
suite is the only gate. A gate that cries wolf whenever the machine is busy
gets read as noise, and the next real failure arrives wearing the same clothes.

## What landed (increment 1)

The dogfood test now runs against a **detached worktree snapshot at HEAD** — a
fixed tree no concurrent lane can move — instead of the live working tree.

- `test_lint.py` gains a `frozen_tree` fixture: `git worktree add --detach
  <tmp>/frozen-head HEAD` (~94ms, measured), yielded, and removed `--force` in a
  `finally` so a crash cannot orphan a worktree the lane-containment backstop
  or the `#203` reaper would later trip on.
- The fixture **raises** if git cannot make the snapshot. Falling back to the
  live tree would reintroduce the false red this exists to fix; the failure
  surfaces instead.
- The test asserts a **runtime-derived precondition**: the snapshot carries a
  populated `questions.md`/`tasks.md` and `parse_ledger` yields a non-trivial
  open-id count, otherwise `not rep.failed` proves nothing on an empty tree
  (the hollowness this repo keeps paying for).

### Red-proof, both directions, against pre-existing production code

The check that goes red is `run_checks → check_questions` — production code that
predates this diff. The diff adds a snapshot *fixture*; it does not add the
check. So the red is not circular.

- **A — live churn must not move it.** Breaking the live `questions.md` to the
  exact `#428` failure shape (a `##` heading used as a question) leaves the test
  **GREEN**. It reads the snapshot, not the live tree. *This is the false-red
  mechanism, killed.*
- **B — a corrupted snapshot must fail it.** Writing the failure shape into the
  snapshot's `questions.md` makes `check_questions` ERROR and the test fails on
  `assert not rep.failed`. *The snapshot is the thing under test, not hollow.*

### Why the skill-tool reads staying live is correct

Three checks read the skill's own tool files from the module-global `SKILL_DIR`
rather than the passed target: `load_watch` (`SKILL_DIR/watch.py`),
`check_skill_version` (`SKILL_DIR/migrations/`), and `check_review_artifacts`
(`SKILL_DIR/review_artifact.py`). These are committed skill code, identical at
HEAD between snapshot and live, and no lane owns them. They cannot false-red
from data-file lane churn. Every **data** read goes through the passed `dw` /
`dw.parent`, which is the snapshot.

One caveat, recorded rather than hidden: `status.json` is gitignored, so it is
**absent** in the snapshot and the status checks degrade to WARN/silent — never
ERROR. The dogfood test no longer asserts about machine-local state, which is
correct: machine-local state is covered by `lint.py --target .` at the
quiet-tree gate, which is the brief's third option and where it belongs.

## The sibling surface (enumerated, 7 sites)

The brief asks for a count of the exposed surface, not one fixed test. Every
dogfood test in `test_lint.py` that reads the live tree shares the `#428`
defect. There are **7** sites; only the first false-redred tonight because it
runs the full check list and so is the most sensitive to a `Lane-owns:` sweep.

| # | site (test_lint.py) | reads | can false-red from lane churn? |
|---|---|---|---|
| 1 | `test_this_repo_passes_its_own_linter` (full `run_checks`) | whole `.dreamwork` tree | **yes — fixed (`1454717`)** |
| 2 | `test_this_repo_has_no_forgotten_folds` (`check_landed_asks`) | `questions.md` + ledger | yes — open-question/landing correlation drifts as lanes fold |
| 3 | `test_this_repo_maps_its_own_plans` (`check_doc_map_plans`) | `doc-map.md` + `docs/plans/` | yes — a lane adding a plan moves the enumeration |
| 4 | `test_this_repo_introduces_no_stale_artifacts` (`check_review_artifacts`) | `.dreamwork/review/` | yes — a lane landing an artifact changes staleness |
| 5 | `test_this_repo_passes_its_own_human_blocker_check` (`check_human_blocker`) | `tasks.md` + `questions.md` | yes — a `blocked-on: **human**` marker without a question is exactly what a mid-fold lane produces |
| 6 | `test_the_live_repo_is_dormant_not_broken` (`check_subdecisions`) | `tasks.md` + `questions.md` | lower risk today (zero declarations), but a lane folding a sub-decision entry mid-run would move it |
| 7 | `TestSelfCompletedOpen._real_ledger` (helper, not an assertion) | `tasks.md` | reads-only helper feeding fixtures; no direct false-red, but its callers share the ledger |

### Adoption rule

A dogfood test should adopt `frozen_tree` **iff** its verdict can be moved by a
file a concurrent lane owns. The three options the brief names map to the
site's risk:

- **snapshot** (the landed pattern): the test asserts "this repo passes its own
  linter" and the inputs are the repo's mutable data. Use the fixture. This is
  the right answer for sites 1–5.
- **skip while lanes are out** (`lint._live_lane_worktrees` already answers
  this): a test that genuinely cannot be made deterministic. If used, the skip
  reason must be **printed and visible** — a silent skip converts a false red
  into a silent pass, strictly worse. None of the 7 need this today.
- **move out of pytest** into the quiet-tree gate: a check that is only
  meaningful when no lane is running. `lint.py --target .` at the merge gate is
  that surface; the in-pytest dogfood tests are the busier surface.

Sites 2–5 are the next adoption batch. Each is a one-line change (`run(...)` →
`run(frozen_tree)` with the fixture arg), and each should gain its own
runtime-derived precondition (a non-empty file, a non-trivial parsed count) so
the snapshot cannot pass vacuously. Site 6 stays as-is until the sub-decision
marker is in use; site 7 is a helper.

## Why not retry, and why not tolerance

A retry hides the mechanism and preserves the false red for whoever runs it
next — explicitly forbidden by the brief. Widening the tolerance (e.g. only
failing if N checks error) is the same class of error as `#413`'s inverted
guard: it trades a loud wrong answer for a quiet one. The snapshot is the only
fix that keeps the assertion honest at full strength.

## Verification

- `python3 -m pytest test_lint.py -q -p no:randomly` — **328 passed**.
- `python3 lint.py --target .` — clean (0 errors; 1 warning, unchanged). This
  can itself false-red while lanes commit — see the brief's note; re-run alone
  before believing it.
- `git worktree list | grep frozen-head` after the run — clean (no orphans).

## Related

`#428` (this task), `#424` (the suite is one shared lock), `#461` (a guard
graded whatever held its port — the same *"the test measured somebody else's
state"* shape, one layer up), `#413` (a guard encoding a superseded contract —
the inverse failure mode, a silent green).

---

# #471 — why a self-serving guard cannot run alone, and why the "full run
disagrees" premise is false

This is an investigation, not a patch. The brief's own honest admission — *"I
do not know why these two observations disagree"* — is the thing to resolve,
and the resolution is that **they do not disagree, because Observation B is
false**. Stated plainly so the ledger stops implying otherwise: **no registered
guard fails to gate in a full run by being silent about it; the self-serving
guards fail LOUDLY (exit 1, named message) in every run, single or full.**

## The two observations, rechecked against the cited evidence

- **Observation A** (true): `DREAMWORK_GUARDS=identity just guards` and
  `DREAMWORK_GUARDS=reviewdraft just guards` both fail with
  `serve: :39899 is serving …/target, not …/<guard>/…`.
- **Observation B** (false): *"identity PASSED in the full `just test` run at
  05:33."* The brief points at
  `/tmp/claude-1000/…/scratchpad/justtest.txt` as *"a real record of one full
  run — read it before running anything."* That file shows, verbatim:

  ```
  FAIL identity (exit 1) [load 52.41->52.41 / 16 cores]
        FAIL the guard threw before finishing its checks
        Error: serve: :39899 is serving /tmp/tmp.DXeQJ0ghBL/target, not /tmp/tmp.DXeQJ0ghBL/identity/alpha-loop …
  FAIL reviewdraft (exit 1) [load 57.62->57.62 / 16 cores]
        Error: serve: :39899 is serving …/target, not …/reviewdraft/target …
  FAIL serving (exit 1) [load 49.62->49.62 / 16 cores]
        Error: serve: :39899 is serving …/target, not …/serving/target …
  FAIL gitrow (exit 1) [load 49.62->49.62 / 16 cores]
        Error: serve: :39899 is serving …/target, not …/gitrow/target …
  ```

  `dashboard` and `morph` (both ephemeral-port guards) **PASS** in the same run.
  So the file cited in support of Observation B refutes it: identity did **not**
  pass; it failed with the identical port error. The first draft of #471's
  finding (*"the claim that some of the 57 guards silently do not gate is
  unsupported"*) is correct to retract that claim — and this investigation goes
  further: **the guards fail loud, not silent, so the `#310`/`#413` "guard
  believed to gate that did not" worry does not apply here at all.** A future
  reader of the ledger should not carry that worry forward from #471.

  (One caveat recorded rather than smoothed: the 05:33 run and `justtest.txt`
  may not be the same run. But no post-#461 full run can show identity PASSING —
  see the mechanism below — so any run that did was either pre-#461 or a
  misread. `justtest.txt` is post-#461 — its lint output reports `next id 471` —
  and it shows identity failing.)

## Which of the brief's four possibilities is true: #4, "something else"

The "something else" is that **Observation B is wrong**, full stop. Concretely:

1. *Something frees `{{port}}` before the self-serving guards are reached* —
   **false**. Nothing frees it. The shared server holds 39899 for the whole run,
   and the self-serving guards fail in the full run too (`justtest.txt`).
2. *Those guards differ from `reviewdraft` in a way not found* — **false**. They
   are identical in the load-bearing respect: all adopt `argv[3]`.
3. *`DREAMWORK_GUARDS=<one>` changes recipe behaviour beyond the guard list* —
   **false**. The recipe always starts the shared server on `{{port}}` and always
   passes `{{port}}` as `argv[3]` to every guard, regardless of `DREAMWORK_GUARDS`.
   Setting it to one guard only narrows the loop; the shared server still starts.
4. *Something else* — **true**: Observation B is a misread; both observations
   are the same observation.

## The mechanism, measured not reasoned

`#461` (`aec8adc` then `54f8fcd`) converted the own-server guards to
`serveVerified`. For six of them it **also** changed the port source from
`const PORT = await freePort()` (ignore `argv[3]`, pick an ephemeral port) to
`const PORT = process.argv[3] ? +process.argv[3] : await freePort()` (adopt the
shared port when handed one). Verified per guard against the pre-conversion
blob:

| guard | pre-#461 `PORT` | post-#461 `PORT` | fails in full run? |
|---|---|---|---|
| `fileimg`  | `await freePort()` | `argv[3] ? +argv[3] : freePort()` | yes (would; run SIGTERM'd first) |
| `fileview` | `await freePort()` | `argv[3] ? +argv[3] : freePort()` | yes (would; run SIGTERM'd first) |
| `identity` | `await freePort()` | `argv[3] ? +argv[3] : freePort()` | **yes — seen in `justtest.txt`** |
| `filehead` | `await freePort()` | `argv[3] ? +argv[3] : freePort()` | yes (would; run SIGTERM'd first) |
| `gitrow`   | `await freePort()` | `argv[3] ? +argv[3] : freePort()` | **yes — seen in `justtest.txt`** |
| `serving`  | `await freePort()` | `argv[3] ? +argv[3] : freePort()` | **yes — seen in `justtest.txt`** |
| `reviewdraft` | `+(argv[3] \|\| 39894)` | (unchanged by #461) | **yes — seen in `justtest.txt`** |
| `staleremedy` | `await freePort()` (ignores `argv[3]`) | (unchanged) | **no — immune** |

`justtest.txt` shows 4 of 7 because the run was **terminated by signal 15** at
`burndown` (after `gitrow`/`serving`), so it never reached
`filehead`/`fileview`/`fileimg`. Those three share the identical code shape and
would fail identically — the run simply did not get there.

**This is `#461`'s own stated principle violated on its own batch 1.** The
entry records that batch 2 (8 ephemeral-port guards) was *rejected* because
*"adding an `argv[3]` pin takes eight guards that chose their own ephemeral
port and aims them at a socket that is guaranteed occupied … merging it would
have reddened eight guards in `just test`."* Batch 1 did precisely that to six
guards, and the predicted reddening is exactly what `justtest.txt` records.

## The cheapest discriminating experiment (run, load-independent)

`DREAMWORK_GUARDS="identity gitrow" just guards`, at load 53.77 / 16 cores:

```
FAIL identity (exit 1) [load 53.77->53.77]
      Error: serve: :39899 is serving …/target, not …/identity/alpha-loop …
FAIL gitrow (exit 1) [load 53.77->54.43]
      Error: serve: :39899 is serving …/target, not …/gitrow/target …
```

Both fail with the named port error. This is **not** a frame-sampling flake
(those move with load and print "0 of N part-way"); it is a deterministic
collision that throws before any browser work. The brief's trap — *"a guard
failing is not evidence of your hypothesis unless the failure message is about
the port or the target"* — is respected: every failure here is the port/target
message.

## Where the fix belongs — and where it does not

**`dev/capture/serve.mjs`: NO CHANGE.** `serveVerified` refusing a port held by
a server for a *different* target is correct; that refusal is `#461`'s entire
contract (*"assert the responder's identity, not just that something
responded"*). The brief floats an alternative — *"the guard should be told to
pick its own port when the shared one is not its own"* — and it was weighed and
rejected: (a) auto-fallback to an ephemeral port inside `serveVerified` would
violate the caller's explicit port request and silently mask the `#461`
stranger-squatter case the module was built to refuse; (b) returning a "port
taken, you decide" signal still requires every guard to handle it, so it does
not reduce the fix surface; (c) `#461`'s batch-2 rejection already names the
right answer — these guards should pick an ephemeral port, and `serve.mjs`
should keep refusing. Changing `serve.mjs` to be lenient would re-open the
defect it exists to close.

**The guards (NOT owned here): revert to `await freePort()`, keep
`serveVerified`.** The fix is one line per guard, restoring the pre-#461 port
source while retaining the readiness/identity check `#461` added. The reported
diff (for the coordinator, who owns these files and the recipe):

```diff
- const PORT = process.argv[3] ? +process.argv[3] : await freePort();
+ const PORT = await freePort();
```

applied to `fileimg`, `fileview`, `identity`, `filehead`, `gitrow`, `serving`.
`reviewdraft` is the special case below. **What it fixes:** the seven
self-serving guards stop colliding with the shared server and each gets its own
ephemeral server (immune to squatters by construction, per `#461` batch 2).
**What it risks:** nothing behavioural — this is the exact code that ran before
`aec8adc`/`54f8fcd`, and `serveVerified` still proves each guard's own server
came up. A guard run standalone (`node dev/capture/identity.mjs OUT`) already
took the `freePort()` arm, so the standalone path is unchanged.

**`justfile`: NO CHANGE.** The recipe is correct: it starts one shared server
and passes `{{port}}` to every guard. Guards that want the shared server use
it; guards that serve their own target must ignore `argv[3]`. That is the
contract the header comment already documents (*"identity … (OUT) only"*,
*"serving … OWN TARGET + OWN EPHEMERAL PORT"*) — the code drifted from the
comment, not the other way round.

**`reviewdraft`'s hardcoded `39894`: a separate latent defect, not the #471
cause.** `reviewdraft` uses `+(process.argv[3] || 39894)`. In a full run
`argv[3]=39899`, so it takes 39899 and collides with the shared server — that
is the #471 failure for it, identical to the other six. The hardcoded `39894`
only applies when `argv[3]` is absent (standalone). It is nonetheless a defect:
`39894` is *inside* the reserved watch-guard range `39890–39899`, and it is a
fixed exclusive port, which `#319` ("guard servers should bind port 0") exists
to remove. Reported, not fixed (another lane owns `reviewdraft.mjs`); the #471
fix for `reviewdraft` is the same `await freePort()` revert as the other six,
and the hardcoded `39894` should go with it.

## Verification done here

- `DREAMWORK_GUARDS="identity gitrow" just guards` — both FAIL with the named
  port/target error at load 53.77 (deterministic, load-independent).
- Read `justtest.txt` (the cited full run) end to end: 4 self-serving guards
  fail with the port error; run SIGTERM'd before the other 3.
- `git show <pre-461>:dev/capture/<g>.mjs` for all eight self-serving guards —
  confirms the `freePort()` → `argv[3]` regression set exactly.
- **Not run:** the full `just test` (eight lanes share this machine); nothing
  bound in 39880–39899 left behind (the pair-run's shared server is reaped by
  the recipe's trap); `:35110` untouched; no `pkill -f`.

## Why it matters beyond convenience

A guard that cannot run in isolation cannot be red-proved after the fact, and
this repo's rule is that a check is not verification until it has been red.
The fix above restores isolation for seven guards at once, by reverting the
`#461` batch-1 port regression while keeping its identity check — so the
property `#461` was built for (never grade a stranger's server) survives, and
the property `#319` was built for (never collide on a fixed port) is restored.

Related: `#461` (the regression source, whose batch-2 rejection already named
the right answer), `#319` (bind port 0 — the durable fix these guards should
already embody), `#203` (the orphan-squatter class `serveVerified` exists to
refuse), `#428` (the suite under concurrent lanes — this is a deterministic
cousin, not a load flake), `#310` (the "guard believed to gate that did not"
worry — **does not apply**: these guards fail loud).

---

# #471 successor — the suite must report which guards RAN, not which are registered

`#471`'s port fix (`80ac4b5`) made the eight affected guards run again, but the
**reporting hole it went through is still open**: `lint` says *"N guard(s)
registered, each with a file"* — that measures REGISTRATION. Nothing measures
EXECUTION. So a guard can be registered, have a file, be believed to gate, and
never run, which is `#310`'s family for the second time. This section is the
close on that hole.

## What "executed" means, and the discriminator

**A guard executed iff its run log shows it reached at least one real
assertion** — a `^(PASS|FAIL) ` verdict line that is NOT the crash sentinel
`FAIL the guard threw before finishing its checks`.

Every guard shares that output contract: the 38 that import `report.mjs` get it
from the module, and the 22 that do not (counted: `dashboard dismiss draft
gitrow history identity indicator morph morphhold motion plugcmd prominence
provenance qorder qsec revieworder reviewsplit runmode serving staleremedy
submitlog subslog`) inline the identical idiom — `const ok = (n,c) =>
checks.push(\`${c?'PASS':'FAIL'} ${n}\`)` and the same `process.on('exit')`
sentinel. `dismiss`/`revieworder` lack the inline sentinel but still use `ok()`,
so judging produces verdicts and a pre-judgment crash produces none — they are
classified correctly by the same rule.

This is the crux the brief names, and the definition resolves it: **"ran and
judged" vs "died before judging."** A guard that judged-and-found-a-failure
(genuine `FAIL <name>`) executed; a guard that threw in `serveVerified` before
any `ok()` (#471's exact shape) produced zero genuine verdicts and the sentinel
as its only FAIL-ish line, so it did **not** execute. A guard that judged and
*then* crashed still executed — at least one genuine verdict precedes the
sentinel. The recipe's per-guard `PASS/FAIL $g` line could not tell these apart
(it branches on exit code, and a judged-failure and a pre-judgment death both
exit 1), which is precisely why "did the recipe print a line for it" was the
naive test the brief warned against.

## Where the failure surfaces, and the can-it-be-skipped axis

**The comparison lives in the `guards` recipe (justfile)**, invoked once after
the per-guard loop as `python3 lint.py guard-execution "$OUT" $GUARDS || fail=1`.
lint reads files and cannot watch a run; the recipe is the only component that
runs the guards and is therefore the only place the executed set can be
measured. On the can-it-be-skipped axis this settles it: the comparison cannot
be skipped inside a `just guards`/`just test` run — it feeds `fail`, so a
missing guard reddens the run. A focused `DREAMWORK_GUARDS="a b"` run compares
against the *requested* set (the honest comparison — you can only be held to
what you asked to run), so in a full run requested == registered and the row
reads `N of N`.

**lint's role is the backstop, not the measurement.** `check_guards_execution
_accounting` reads the justfile and errors if the recipe no longer invokes the
comparison (the "became hollow" shape — a check that passed at birth and was
later deleted). It cannot be skipped inside a `just lint`/`just test` run, so
deleting the measurement reddens one of the two gates a lane always runs. Two
independent things are asserted, because either alone can pass over a deletion:
the recipe invokes `lint.py guard-execution` as a command (not merely names it
in a comment) AND wires it to `fail`.

## Zero-assertion guard: a failure

Yes. A guard that reports zero genuine verdicts is, by definition, not executed,
and the run fails — *"a check that examines nothing looks identical to one that
found nothing"* (CLAUDE.md). This is not a separate rule: it falls out of the
definition, because executed ⟺ ≥1 genuine verdict. The #471 guards asserted
zero for 3.5h; treating a zero-assertion guard as "executed" would hide exactly
that shape.

## The red, the production line it names, and that the injection reached it

The red is by synthetic run record (the brief's sanctioned alternative to
editing a real guard file, which is not ours): a guard log in the exact #471
shape (`Error: serve: …` + the crash sentinel, zero genuine verdicts) is placed
among judged guards, and the REAL CLI — which reads the file and calls the REAL
`ran_and_judged` — must name it and exit 1. **Production line named:** the
sentinel-exclusion in `lint.ran_and_judged`. Remove it (make any `PASS/FAIL`
line count, including the sentinel — the "naive did-we-print-a-line" test) and
`TestRanAndJudged.test_the_crash_sentinel_alone_is_not_judged` and
`TestGuardExecutionCLI.test_a_471_shape_guard_is_named_and_fails` go red; the
latter's runtime precondition (`{good1: True, died471: True}` — both judged)
catches the break before the CLI call, which is the "green red-run is a finding"
guard working. **The injection reaches the code:** there is no hand-built
classification in the test — it writes a log file and invokes the production CLI
on it. A second red, against the structural check: deleting the
`guard-execution` line from the real justfile makes both
`TestGuardsExecutionAccounting.test_this_repo_wires_the_comparison` and
`lint.py --target .` ERROR with the named message.

## Runtime-derived preconditions

`guard-execution` asserts, not assumes: (a) the requested set is non-empty
(else exit 2 — a vacuous comparison), and (b) at least one log was read under
OUT (else exit 2 — a broken OUT must not read as "everything ran", which is
#471's failure mode inverted). The test fixture's discriminating power is
itself derived at runtime via the real classifier (`{good1: judged, died471:
not}` — both shapes present, or the assertion proves nothing).

## Both counts on the OK row

`OK    guards: <executed> of <registered> registered guard(s) ran and judged` —
two numbers, so a gap is visible. The row that hid this bug (`N registered`)
carried one. A focused run prints `executed of requested`, which equals
registered in a full run.

## Verification

- `python3 -m pytest test_lint.py -q -p no:randomly` — the 15 new tests pass;
  the dogfood test passes once `lint.py` + `justfile` share a HEAD (the snapshot
  at HEAD then carries the hook — see below).
- `python3 lint.py --target .` — clean (0 errors; 1 pre-existing status.json
  warning). The new structural row is `OK`.
- Real-recipe smoke: `DREAMWORK_GUARDS="identity gitrow" just guards` — a
  single-/two-guard run of own-server guards (impossible before `80ac4b5`) now
  runs, both judge, and the accounting row reports both counts.
- Two genuine red runs performed and restored (classifier break; recipe
  deletion). Neither was green while the bug was in place.
- Not run: the full `just test` (eight lanes share this machine). Scoped pytest
  to `test_lint.py` (the owned file) to avoid the `watch.py` lane and contention.

### Note for the coordinator: the dogfood test now also gates the wiring

`test_this_repo_passes_its_own_linter` lints a snapshot at HEAD through the LIVE
`lint.py`, so it now evaluates `check_guards_execution_accounting` against the
HEAD justfile. That means `lint.py` and `justfile` must land in the **same
commit** — if the hook is missing at the HEAD the snapshot reads, the dogfood
test errors (verified: pre-commit, the snapshot justfile has 0 `guard-execution`
and the test fails; post-commit, both are at HEAD and it passes). This is
desirable, not a regression: the dogfood test is now a third guard that the
wiring cannot be removed at HEAD. `Lane-owns:` notes the same single-commit
obligation for `justfile`.

### `file-formats.md` paragraph wanted (file not owned — for the coordinator)

> **Guard run-log verdict contract.** Every guard in `dev/capture/` (whether it
> imports `report.mjs` or inlines the idiom) writes its verdicts to stdout as
> one line per assertion: `PASS <name>` or `FAIL <name>`, separated from
> coverage/notes by a line containing only `----`. A guard that exits before
> its first assertion emits the crash sentinel `FAIL the guard threw before
> finishing its checks` as its only FAIL-ish line — this marks *did-not-judge*,
> not a verdict. The `guards` recipe captures each guard's combined
> stdout+stderr to `<OUT>/<guard>.log`. `lint.py guard-execution <OUT>
> <guard>…` classifies each log: a guard *ran and judged* iff its log has ≥1
> `^(PASS|FAIL) ` line that is not the sentinel; the recipe fails the run when
> any requested guard did not run-and-judge (#471: registration is not
> execution).

Related: `#471` (the port fix this builds on), `#461` (the regression source),
`#310` (the "guard believed to gate that did not" family — this is its second
instance, now with a detector), `#192` (the `report.mjs` contract this reads),
`#428` (the snapshot the dogfood test uses, which now also gates this wiring).
