# Dogfood record — coordinator-only loop, and which runner to use

Two questions the human wants answered by evidence, not impression (2026-07-28
05:10). This file is the running record; it is a **measurement log, not a
conclusion**, and every row states how it was measured.

1. **Which models/providers are best for us**, per kind of task.
2. **Does the dreamwork loop work with the main session as coordinator only** —
   dispatching every increment — rather than doing the work itself?

And a third, added at 05:13: **does a c2c peer outperform a subagent handed a
task**, ideally on a measurable criterion. Recorded in its own section.

## The success criterion, fixed in advance

Both live lanes are guard work, which is unusually well suited to measurement
because the guard's own verdict is the criterion and it is not a matter of taste:

- **Primary**: does the named guard end **green**, run in isolation, on its
  assigned port?
- **Secondary, and it can fail while the primary passes** — which is the whole
  point of this repo's rules: was the **red-proof real**? The agent must name what
  it broke, the exact check that failed, and the production line that would have to
  change for its check to fail. A guard turned green by widening a tolerance until
  it cannot fail scores **worse than red**.
- **Discipline**: did it stay inside its stated file ownership? (`watch.py` was
  off-limits to both; a third agent holds it.)
- **Cost**: wall-clock from dispatch to report.

Written down before the results so the bar cannot move afterwards.

## Runner routing — what actually works

**This table inverted between 05:52 and 11:10 and both grok-CLI rows flipped.** Re-measure
before trusting it; the verdicts below carry the time they were taken.

| alias | route | verdict (05:52) | verdict (11:10) |
|---|---|---|---|
| `@grok` | grok CLI, `grok-4.5` | works | **DEAD — 401** |
| `@glm52` | grok CLI + `provider=llmp`, `glm-5.2` | BROKEN — cannot work | **works, and is now the CLI default** |
| `@gk-glm52` | grok CLI + `llmp`, `glm-5.2` | predicted to fail the same way | **should work now** (untested) |
| `@oc-glm52` | opencode + `zai-coding-plan`, `glm-5.2` | works (smoke-tested) | untested since |
| `@pi-glm52` | pi + `llmp`, `glm-5.2` | prefer this for glm-5.2 (his 05:26 steer) | untested since |

**The measurement, 11:10.** `grok models` now returns **twelve** models, all the `llmp-*`
ones, and prints `Default model: llmp-glm-5-2`:

```
grok-4.5, llmp-gpt-5-6-luna, llmp-gpt-5-6-terra, llmp-gpt-5-6-sol, llmp-gpt-5-5,
llmp-gpt-5-4-mini, llmp-glm-4-7, llmp-glm-5-turbo, llmp-glm-5-1,
llmp-glm-5-2 (default), llmp-glm-5, llmp-glm-4-5-air
```

At 05:52 that same command returned `grok-4.5` and nothing else. So **`llmp` became
reachable through the grok runner during the day** — the config never changed (`@glm52` is
still `runner = "grok"`, `provider = "llmp"`), the upstream did. Meanwhile `grok-4.5`
itself now 401s: `Model 'llmp-gpt-5-6-luna' is using its own API key` is the CLI telling
you the `llmp-*` models authenticate separately from `grok-4.5`, and only the latter's
credential is expired.

**The lesson is about the table, not the aliases.** A routing verdict is a measurement
with a timestamp, and this one had a shelf life of five hours. I lost two lanes acting on
the `@grok` row and nearly skipped the runner that was working, because the row that said
**"BROKEN — cannot work"** was the strongest claim in the file and the least true.
Anything here that says *cannot* deserves a re-probe before it is believed — `grok models`
costs one second.

**Use `@pi-glm52` rather than `@oc-glm52`** — his heads-up at 05:26: opencode
**hangs** when it touches `/tmp` or similar. Confirmed observable in lane A, which
ran `rm -rf /tmp/opencode/green && mkdir -p /tmp/opencode/green && node
dev/capture/plugcmd.mjs /tmp/opencode/green 39897`. It did not die — CPU kept
accruing and the transcript kept growing — but it went very slow, and a stalled
transcript is indistinguishable from a dead agent without checking `ps`. Since the
guards' own `justfile` recipe uses `mktemp -d` (i.e. `/tmp`), **any guard lane is
exposed to this**, which makes pi the right default for guard work specifically.

**Superseded 11:10 — kept because the reasoning was sound and the conclusion still
expired.** The 05:52 finding, verbatim below, was correct when taken. What it could not
know is that the constraint was upstream and temporary. Read it as a record of a
measurement, not as a fact about the alias:

**`@glm52` cannot reach glm-5.2 and it is not an environment problem.** Measured:

- `grok models` → `You are logged in with grok.com. Default model: grok-4.5.
  Available models: * grok-4.5 (default)`. That is the whole list.
- The failure is `Couldn't set model 'glm-5.2': Invalid params: "unknown model id"`.
- It fails **identically under a `fish -l -c` login shell**, so the missing-fish-env
  hypothesis is refuted — the alias's `provider = "llmp"` is not reaching the grok
  runner, or that runner does not support a custom provider at all.
- `@gk-glm52` has the same shape and will fail the same way.

So glm-5.2 is reachable, but through **opencode or pi, not through the grok CLI**.
Either the `glm52` alias should become `runner = "opencode"` with
`provider = "zai-coding-plan"` (i.e. a copy of `oc-glm52`), or the grok runner needs
whatever makes `llmp` reachable. That is the human's config to change, not mine.

## Live lanes

| lane | runner | task | dispatched | criterion |
|---|---|---|---|---|
| A | `@oc-glm52` | `#382` — `plugcmd`'s fixed-900ms race (`dev/capture/plugcmd.mjs`, port 39897) | 05:12 | plugcmd green + real red-proof |
| B | `@grok` | `#383` — three motion guards that disagree with themselves (`revieworder`, `gitrow`, `burndown`, port 39895) | 05:11 | characterisation table first; then green + real red-proof, or an honest "still flaky" |

Both briefs were written to `.dreamwork/docs/briefs/` and the agent was pointed at
the file rather than handed the prompt inline — so the brief is reviewable,
re-runnable, and comparable between runners. Both were told: never use `attn`,
append once to `.dreamwork/inbox.md`, stage by explicit path, do not push, and
`watch.py` is off-limits.

Lane A cost one false start: dispatched to `@glm52` at 05:10, which died in ~2
seconds on the model error above. **That is itself a result** — a misconfigured
alias fails fast and loudly, which is the good case.

## Results, scored against that bar — all four lanes in, 05:52

Wall-clock is measured from the run directory name (epoch of dispatch) to the
transcript's mtime (written at exit), under
`~/.local/state/cc-w/ccc/runs/<runner>-<epoch>-<pid>-0/`.

| lane | runner | task | cost | primary | red-proof | discipline |
|---|---|---|---|---|---|---|
| A | `@oc-glm52` | #382 plugcmd | **19m** | **pass** — green | **pass** | pass |
| B | `@grok` | #383 three motion guards | **38m** | **pass** — 3/3 isolated | **pass**, per-guard and discriminating | pass |
| C | `@pi-glm52` | #354 filebytes plan | 25m | n/a (design) | n/a | pass |
| D | `@pi-glm52` | #384 two-line selector | **18m** | **pass** — both green | n/a (no check changed) | pass — but did not commit, as instructed |

**Four for four on discipline.** Not one touched `watch.py`, all four appended
once to the inbox, none used `attn`, all staged by explicit path. The
file-ownership section of the brief is doing real work, and it is cheap to write.

**The cost column is the surprising one, and it does not favour either model the
way the brief-writing did.** #384 was a **two-line** change and cost 18m; #383
rebuilt the sampling instrument in three guards, ran a characterisation matrix
under three load levels, and produced three separate sabotage red-runs, for 38m.
So roughly **ten times the work for twice the wall-clock**. Read carefully that
is not "grok is 5× more efficient": #384's 18m was spent almost entirely on
*verification* — it reverted its own two lines to prove `draft`'s tail flake was
pre-existing, which is exactly what I want and is nearly all of its cost. The
floor for a well-verified change on this box is ~18m regardless of diff size,
and **that floor, not the model, is what sets the price of a small task.**

Consequence for how I dispatch: a two-line fix is not cheap enough to be worth a
lane of its own. Batch small mechanical fixes into one brief, or do them inline.

**Observability, corrected 05:58.** I had recorded this as a grok trait. It is
not: `@pi-glm52` also writes **zero bytes until exit** — its run directory holds a
0-byte `transcript.txt` for the whole run and gains `output.txt` only at the end.
**`@oc-glm52` (opencode) is the only one of the three that streams**, 22KB at nine
minutes. So the axis is the *runner*, not the model, and the practical consequence
is that with grok or pi the only mid-run signal is the filesystem: `git log`,
`git status`, and the files the brief says it owns. Which is enough — lane A's A1
commit was visible to me seven minutes in — but it means **the brief must name the
files, or the lane is invisible while it runs.** That is a second, unplanned reason
the ownership section earns its place.

**And one dispatch mistake worth recording, because it cost me a notification:**
backgrounding `ccc … &` *inside* a harness call that is itself backgrounded makes
the harness see its own command exit immediately, so the task reports "completed"
in seconds and no notification arrives when the real work finishes. Lane A ran
detached and I had to poll it. Let the harness own the backgrounding; do not
double it.

**Both models scored the same on the two criteria that matter** (primary and
red-proof), across four lanes. On this evidence I cannot distinguish them on
quality, and I should stop trying to: the difference that showed up repeatedly was
**speed on large tasks** (grok) and **observability during the run** (opencode
streams a live transcript; grok writes zero bytes until exit, which cost me
visibility on the longest lane of the batch).

## The result that actually matters, and it is not about the models

**Three of the four lanes refuted something I had told them was established.**

- Lane A (#382): I briefed a timing race, documented with measurements. It was a
  wrong CSS selector. My hypothesis explained none of the anomaly I had in hand.
- Lane B (#383): I briefed "they sample on a wall-clock schedule and a loaded
  machine drops the sample outside the window." They counted *distinct sampled
  values* — a real smooth travel sampled seven times failed a `>= 8` threshold.
  The count was never a property of the motion at all.
- Lane D (#384): I filed, having explicitly "checked rather than assumed", that
  neither guard asserted on the misread node. `subslog` did.

Three for three against the coordinator. The common shape: **I was confidently
wrong in exactly the place I had done the most work.** Each error sat inside the
part of the brief I had measured and written up carefully, and the careful writeup
is what made it survive — a paragraph of evidence reads as a settled fact to
whoever gets it next.

Two things follow, and they change how I brief:

1. **Say which claims are load-bearing and invite refutation of those
   specifically.** Every one of these briefs did include "if you conclude my
   recommendation is wrong, say so plainly — that is a valuable result." All three
   agents used it. That sentence is not politeness; it is the highest-yield line in
   the template and it should be attached to the *named hypothesis*, not left as a
   general permission at the bottom.
2. **Distinguish measured from inferred in the brief's own prose.** My briefs
   presented both in the same voice under a heading that said "what is established
   — do not re-derive it". The measurement (`said` comes back `""`) was solid every
   time; the *explanation* attached to it was wrong three times out of three. A
   brief should mark the join.

## Observed differences, measured at 05:20 with three lanes in flight

**The biggest practical difference is not speed, it is observability.**

| | `@oc-glm52` (opencode) | `@grok` (grok CLI) |
|---|---|---|
| live transcript | **streams** — 22,843 bytes at 9 minutes, growing | **0 bytes until it finishes** |
| supervisable in flight | yes — I read its reasoning and could correct it | no — a black box until it returns |
| CPU over the window | 54s over 489s (11%) | 28s over 597s (4.7%) |

Both were genuinely working (confirmed by process CPU time, not by assumption).
`grok`'s transcript file exists from the first second and stays empty, which is
indistinguishable from a stalled agent unless you check `ps`. For a coordinator that
matters more than raw speed: **I can catch an opencode lane going wrong at minute
three; a grok lane I cannot catch at all.**

Read them at `~/.local/state/cc-w/ccc/runs/<runner>-<epoch>-<pid>-0/transcript.txt`;
`ccc` prints the path on exit.

**My own dispatch mistake, recorded so it is not repeated:** I backgrounded each
lane as `ccc … | tail -N`, so the harness output file stayed empty until completion
— I blinded myself on top of grok's own opacity. Next dispatch: redirect the full
stream to a file and tail that, or read the `ccc` run log above.

## Quality signal: lane A refuted the coordinator's own diagnosis

Worth recording because it is the first hard quality datapoint, and it did not
favour me.

I had diagnosed `#382` as a **timing race**: the guard samples `.cmdmsg` at a fixed
900ms and the POST round-trip has not returned. I had evidence — the command
genuinely reaches the loop, and the text was empty at 900ms.

`@oc-glm52` found the actual cause in under ten minutes: **`.cmdmsg` is not unique.**
`watch.py:1562` is `<div class="cmdmsg fmsg" id="fmsg">` and `watch.py:1587` is
`<div class="cmdmsg" id="cmdmsg">`, so `document.querySelector('.cmdmsg')` returns
`#fmsg` — the *file* message element, which never receives the composer's
confirmation. The guard was reading the wrong node.

That explains the one thing my hypothesis did not: why it failed **identically in
three runs** including an unloaded one. A race would have been intermittent, like
the other three guards. I had the anomaly in front of me and reached for the
explanation I had just spent an hour on elsewhere.

So: a fresh reader beat an invested one on a DOM detail, which is an argument for
dispatching diagnosis rather than doing it — and it cost a brief to get.

## The finding that constrains the whole model: parallel lanes destroy this repo's verification

Measured at 05:34, with four lanes dispatched:

```
/proc/loadavg → 125.49 102.22 75.20      nproc → 16
51 chrome processes, 29 node processes
```

**Load 125 on 16 cores is eightfold oversubscription.** And this repo's verification
is browser guards, many of which assert on *intermediate frames of a transition* —
because `transitions.md` correctly says an end-state assertion cannot fail on a
motion bug. A browser starved of CPU cannot deliver frames on schedule, so every
one of those checks fails. Not flakily. **Deterministically.**

The evidence is clean. `plugcmd`, run twice back-to-back under this load, produced
byte-identical failure sets:

```
FAIL gh-sync EASES IN rather than blinking on (distinct part-way opacities)
FAIL gh-sync finishes at full opacity and never overshoots on the way
FAIL gh-sync drifts as well as fades (1 distinct transforms)
FAIL gh-triage EASES IN rather than blinking on ...
FAIL gh-triage finishes at full opacity and never overshoots ...
```

Those same checks **passed** at 05:05 when I ran `plugcmd` alone. Nothing in
`watch.py` changed between — my tree's `watch.py` has been clean all night.

So the earlier conclusion needs restating more precisely. I called `revieworder`,
`gitrow` and `burndown` "load-flaky", which was right about the mechanism but
understated it: under *variable* load they are flaky; under *sustained* load they are
reliably red. And `plugcmd` has the same class of check, so the defect spans **at
least four** guards, not three.

**The consequence for orchestration is direct and unwelcome:** while lanes are
running, a guard verdict means nothing. I cannot verify anything with the guards and
run agents at the same time. Verification has to be **serialised against the lanes**,
which removes exactly the throughput that parallelism was for — on the one axis
(browser motion) where this repo does its most careful checking.

It also means I have to re-examine the 04:40 sweep that started all this. It ran
while a c2c peer session was live, so its four reds may themselves have been load
artefacts rather than defects. **`plugcmd` was a genuine defect** — a wrong selector,
found and fixed, load-independent. The other three remain unproven either way, and
proving them now requires a quiet machine.

And it is a violation of a standing instruction I should have connected sooner:
`CLAUDE.md` says *"limit builds and tests to 2 threads to avoid overloading the
system."* Four agent lanes each spawning a browser is that rule broken at a level the
rule did not anticipate — I obeyed it inside each lane and broke it across them.

**Revised practice**: cap concurrent lanes doing browser work at **one**; other lanes
may run in parallel only if they need no browser (lane C, a design task, was free).
Take any guard verdict only on a quiet machine, and record the load average beside
the verdict so a future reader can tell a defect from a starved frame.

## The role at five lanes — what changed when it stopped being two

Written at 06:30 with five lanes live (2 grok, 2 glm52, 1 pi-glm52) after his
06:11 "fixed `ccc @glm52`" and his standing 4+4 budget.

**1 · The binding constraint is file ownership, not model capacity, and not load.**
I could run eight. I cannot run two lanes in `watch.py`, which is 8,647 lines and
the target of four separate open tasks. #385 is briefed, correct, and *idle* —
queued behind #300 for no reason except that one file admits one writer. The lever
that would raise throughput here is **#368, the modular split**, and that is now
measurable rather than aesthetic: it is the difference between one watch.py lane
and three.

**2 · Cheap disjointness is worth engineering for.** Lane F went out the moment B2
landed, and it was the right pick over #367 for a specific reason: **it needs no
browser.** Two browser lanes were already holding guard ports 39891 and 39895, and
three concurrent browser lanes is where load previously destroyed motion-guard
verdicts. So the scheduling resource is not "a lane" — it is *which* scarce thing a
lane consumes: `watch.py`, a guard port, or nothing. Lanes that consume nothing are
nearly free and should be preferred when the queue allows.

**3 · One route was forced by capability, and it is the first time.** #300's
acceptance includes visual-review loops on rendered pixels and a text morph
judgeable only from intermediate frames. `@glm52` is not multimodal, so #300 *had*
to be grok. Until then the two were interchangeable on quality and differed only in
speed and observability — a preference. This is a constraint, and it means the
routing table needs a **capability** column, not just a speed one.

**4 · The brief-as-file earns its cost in a way I did not anticipate.** His reason
was reusability and reviewability. The unplanned payoff: with grok and pi writing
zero bytes until exit, **the brief's file-ownership list is the only thing that
makes a running lane observable.** I watch `git log` and `git status` against the
list. Lane B was visibly through B1–B4 before it said a word. A brief that omits
the file list produces a lane that is invisible for forty minutes.

**5 · Writing five briefs cost more than writing five patches would have.** That
is the honest accounting, and it is still correct: the briefs encode the
verification discipline that the lanes then actually followed — 4/4 stayed inside
ownership, and every one produced a real discriminating red. What I would not do
again is write a brief per two-line fix. **The floor for a well-verified change is
~18 minutes regardless of diff size**, so batching small mechanical work into one
brief is strictly better than a lane each.

**6 · The coordinator's real job turned out to be adjudication, not planning.**
Planning was maybe a third of it. The rest: verifying a peer's merge claim (one
detail wrong), re-running lane A's red myself, auditing lane B's tests against the
criteria I had written, catching that my own commit had swallowed a lane's file,
and deciding two questions he should never have been asked. **Every one of those is
something no lane could do, because each requires seeing the whole tree at once.**
That is the actual division of labour, and it is not the one I assumed at the start
— I assumed I would be a planner with a fleet, and I am closer to a reviewer with
a fleet.

**7 · And the thing I got wrong twice in one hour: I trusted my own careful work.**
The `--only` fix I had just written, verified, and propagated to eight briefs — then
used it in a form (`--only <directory>`) that silently does nothing for untracked
files, and shipped a commit whose message named three files it did not contain.
Same shape as the three-for-three refutation above: **the error lands in the part I
had just done the most work on.** The countermeasure that actually works is not more
care; it is checking the outcome rather than the intent — `git show --stat` after a
commit I am confident about.

## The result that dominates everything else: nine lanes, six refutations

Tallied at 07:05, after nine dispatches. **Six of the nine refuted something their
brief stated as established** — and the briefs were not sloppy; each refuted claim
sat in the passage I had measured most carefully.

| lane | what I asserted | what was true |
|---|---|---|
| #382 | a fixed-900ms timing race | `querySelector('.cmdmsg')` returned the wrong element |
| #383 | guards sample on a wall-clock schedule | they counted `distinct >= 8` sampled values |
| #384 | "checked rather than assumed": no guard asserts on the misread node | `subslog` did |
| #386 | the row's arrival transition is still in flight | the click was a separate roundtrip landing after the trace window |
| #300 | count POSTs/events/file bytes to prove hover is side-effect free | the arm is silent for 10s, so all three stay quiet while it arms |
| B7 | `UNIQUE(client_action_id)` is the red line | `BEGIN IMMEDIATE` + SELECT-before-insert carry it; `UNIQUE` is never reached |

Plus `B1`, where the plan's red line assumed a pragma differing from the platform
default — SQLite 3.53's default already matched, so the prescribed deletion changed
nothing.

**Three distinct error classes, and they want different countermeasures:**

1. **A wrong causal story** (#382, #383, #386). The measurement was right every
   time; the *explanation* attached to it was wrong. Countermeasure: mark measured
   apart from inferred in the brief's own prose, and attach "refute this" to the
   named hypothesis rather than leaving a general permission at the bottom.
2. **A check that cannot observe its subject** (#300). Not a wrong guess — a
   category error. The signals I named are real and they are *late*: a
   deferred-commit control makes durable state a trailing indicator. Countermeasure:
   ask *when* each signal becomes true relative to the act being policed.
3. **A red line naming the wrong layer** (`B1`, `B7`). Both are the same trap and it
   is the one I would not have predicted: **defence-in-depth and a discriminating
   red are in tension.** Where two mechanisms each prevent the bug, deleting either
   proves nothing. A plan written before the code names the layer its author imagines
   will carry the property, not the layer that does. Countermeasure: treat a written
   red line as a hypothesis about the implementation, and when a red comes back green
   ask **"which layer is holding this up?"** rather than "is the code fine?"

**Why this is a result about the method and not about me being careless.** Every one
of the six was caught, none reached a commit unchallenged, and the mechanism that
caught them was the same each time: **a lane instructed to disbelieve a green
red-run, plus explicit permission to contradict the brief.** Those two lines cost
about thirty words. Without them, four of these would have shipped as
confidently-wrong verified claims — the #300 one in particular would have shipped a
guard that passes while hover arms the mode, which is worse than no guard, because
it would be cited as evidence.

**What I would change about my own briefs, concretely:** for every named red line,
add *"if deleting this leaves the suite green, find which layer is actually carrying
the property and report that"* — because the instruction I gave ("report a green
red-run") got the finding, but the lanes that went further and **named the real
mechanism** (`B7`'s `DEFERRED` probe, #386's settled-row discriminator) produced
something I could act on immediately rather than a puzzle.

## Coordinator verification: nine lanes, five independent re-runs

I re-ran one red per lane from my own snapshot rather than folding the report. All
five confirmed the lane, and each was a check that could plausibly have been hollow:

| lane | injection | result |
|---|---|---|
| A | deleted the 8-byte length prefix | named test failed, neighbour green |
| B1 | deleted `PRAGMA synchronous=FULL` | `got 1` vs 2, 7 neighbours green |
| C3 | direct `open(path,"w")` for temp-then-rename | `b'' != b'the quick brown fox…'` — **file emptied** |
| #300 | `pickRunMode` into `showRunDesc` | failed **exactly the two assertions the lane added**; my three stayed green |
| F4 | broke the semantics parser to zero | `parse found only 0 … would be vacuous`, `assert 0 >= 5` |
| B7 | removed `UNIQUE` | **12 passed** — reproduced the hollowness |

Two of those are worth more than the others. The #300 row is *evidence about my own
criterion*: the checks I specified stayed green while the bug was live, so the claim
"my criterion was blind" is measured rather than argued. The C3 row is the one to
copy stylistically — its failure printed `b''` against the file's real contents, so
the diff of the failure *is* the argument for the increment. **Prefer injections
whose failure names the real-world consequence over injections that produce a
boolean.**

## Notes on the orchestrator role, written from inside it

He asked for these at 05:26, an hour into coordinating rather than implementing.
Ordered by how much they surprised me.

**1. Invite refutation or you will get your own wrong ideas back, confirmed.**
This is the one I would keep if I could keep only one. Both briefs that mattered
told the agent it was allowed to refute my premise, and **both did**:

- `#354`'s brief said "if you conclude the entry's own recommendation is
  incomplete, say so plainly; that is a valuable result". It concluded exactly
  that — `Range` does not fix the filed bug, because an `<img>` GET carries no
  `Range` header, so streaming is the real fix and ranges are a separate second
  capability. Verified: `read_bytes` at `watch.py:6752` is a bare `f.read()`.
- `#382`'s brief handed over my race hypothesis as *"the hypothesis to test"*
  rather than as fact. It was **wrong**, and the agent found the real cause.

Had I written either as an instruction, I would have received a competent
implementation of a mistaken idea. The brief's job is to transfer the *question*
and the established facts, not the answer.

**2. The brief is the work, and it does not always pay.** `#354`'s brief took
about as long to write as a small increment would have taken to do. The leverage is
real only when the brief buys work I could not have done serially — three lanes at
once, or a fresh reader on something I am invested in. For a ten-minute mechanical
fix, briefing costs more than doing. `#384` is the test case for where that line
sits, and it is deliberately being dispatched with a short inline prompt instead of
a brief file to find out.

**3. I became the bottleneck on shared state, and it is serial.** Every lane that
finishes generates work only the coordinator may do: file the task, fix the
`related:` reciprocity, add the plan to the doc-map (in the right alphabetical
slot — I got that wrong on the first attempt), reconcile `status.json`'s queue.
Three lanes produced five such edits in fifteen minutes. Parallel workers, serial
ledger. That is the coordination tax and it grows with lane count, not with work
done.

**4. Observability was the binding constraint, not capability.** See the table
above. I could supervise the opencode lane in flight and caught its finding at
minute nine; the grok lanes were opaque until they returned. Worse, I made it
harder for myself by backgrounding each dispatch as `ccc … | tail -N`, which meant
the harness output file stayed empty until exit. **A coordinator who cannot see a
lane cannot coordinate it — it can only wait for it.**

**5. The disjointness invariant is not mainly about files.** I planned file
ownership carefully and nearly missed two sharper hazards: every guard defaults to
**one port** (39899), so two lanes would have silently graded each other's server —
the failure mode `justfile` already has a pre-flight comment about; and concurrent
`git commit` races on `.git/index.lock`, which this machine has a documented
mitigation for. Files are the obvious shared resource and the least dangerous one.

**6. Delegation moves the labour, not the responsibility.** I still had to read
`watch.py:6752` myself to confirm lane C's claim, and to check whether `draft.mjs`
and `subslog.mjs` were hollow or merely mis-noted — they were mis-noted, which is a
smaller finding than it first looked and only checking told me so. A coordinator who
accepts reports is not coordinating, it is forwarding.

**7. The loop's own philosophy fights this.** `SKILL.md` caps an increment at
~15-20 minutes so a mistake is caught while you are still on the path that made it.
A dispatched brief is 25-30 minutes and **cannot be checkpointed mid-flight** — I
cannot pause a lane at minute ten and ask whether it is still on track. So
coordinating trades the loop's core error-catching mechanism for throughput. Worth
it for diagnosis and design; questionable for anything delicate.

**8. What I would do differently, concretely.** Write the brief to a file (that
worked — reviewable, re-runnable, comparable between runners); never pipe a
background dispatch through `tail`; assign the port *and* say who else is in the
range; and forbid committing when two lanes might land within a minute of each
other, taking the commit myself instead.

## c2c peer versus dispatched subagent

The comparison is available because both exist in this tree right now:

- **c2c peer** (`grok`, its own session, `.worktrees/277-dreamfade`): #277's
  departure dreamfade. Long-lived, holds its own port, chooses its own increments,
  and I coordinate it by asking rather than instructing. Cost observed so far: it
  held `:35277` across two requests to release it, and its work sat uncommitted for
  hours where I could not see it — I only learned what it was doing by reading its
  worktree diff. Benefit: it is genuinely autonomous and needs no brief.
- **Dispatched subagent** (`ccc`, lanes A and B): scoped by a brief, owns named
  files, reports to a known path, terminates. Cost: the brief took real effort to
  write, and a bad brief is my fault rather than theirs. Benefit: ownership is
  explicit, so lanes are provably disjoint, and the report arrives where I look.

**Open, and the honest state**: no measurable comparison yet, because the peer's
task and the subagents' tasks are not comparable work. The clean experiment is to
give a peer and a subagent the *same* brief with the same criterion, and that has
not been run.

## Ten lanes, seven refutations — and a fourth error class that is about me

Updated 07:15, after #367 increment 1 (`ccc @glm52`, `dbcbcc5`).

#367 refuted a claim in two of my own documents: the plan and the ledger entry both
said the soft cap produces **"a warning at 7"**, while `file-formats.md`, the brief's
criterion, and the code all say seven is *allowed* and the warning starts at 8. The
lane spotted the disagreement, followed the two that agreed, and reported it. It was
right, and a cap of 7 that warns at 7 is a cap of 6.

That does not fit any of the three classes above, so it is a fourth:

4. **A paraphrase of the human's ruling that lost a boundary.** He said *"soft 7, hard
   15"*. Recording that as "a warning at 7" reads as faithful and is off by one. The
   damage is not the typo — it is that **his words are the authority, and a paraphrase
   inherits that authority while no longer being his words.** A builder reading the
   plan would have implemented a cap he never set, and could have cited the plan for
   it. Countermeasure, now applied: quote the ruling verbatim and put the derived
   boundary *beside* it as visibly derived (`soft 7 → MARKS_WARN_AT = 8`), so a reader
   can check the arithmetic instead of trusting the prose. Two documents restating one
   ruling in their own words is the same single-source failure `lint.py` exists to
   catch in file formats; his rulings deserve the same discipline.

## The highest-yield thing I did as coordinator, and it took five minutes

**A lane's stated uncertainty is a map to the defect, not a question to answer.**

#367's report ended with an honest flag: `data-mark` with no value is treated as
not-a-mark rather than refused, the contract is silent on it, *tell me if you'd rather
it refuse*. That is exactly the disclosure I want from a lane. My instinct was to rule
on it and move on.

Instead I probed the area around it — four inputs through the real parser — and the
valueless form it asked about was **correct**, while the case one step over was the
bug: `data-mark=""` and `data-mark="   "` are collected as marks with unreadable
labels, untested. Filed as #389.

Two things generalise:

- **The lane audited the case it noticed and stopped.** It did not enumerate the
  neighbours of its own edge case. That is not carelessness — it is the natural shape
  of attention, and it is *cheap for a coordinator to fix* because the coordinator
  arrives with no investment in the design. Concrete brief change: *"when you find an
  edge case worth flagging, enumerate its neighbours before reporting — the flagged
  case is usually fine and the one beside it usually is not."*
- **The economics favour coordinator auditing far more than I expected.** The lane
  spent ~30 minutes building well. My audit was five minutes and produced a filed
  defect plus a contract sharpening. Verification of a *finished, reported* increment
  is the cheapest work available to a coordinator, because the lane has already paid
  the cost of understanding — and unlike re-running its reds, probing the *boundary of
  its uncertainty* is work it structurally could not do for itself.

Against which: the independent red-run I owed on the same lane (recompute the frozen
byte-identity baseline from a ref I picked by hand, then inject the realistic
regression) **confirmed the lane exactly** and found nothing. That is now the pattern
across ten lanes: **re-running a lane's own reds almost always confirms it; probing
what the lane said it was unsure about almost always finds something.** If coordinator
attention is the scarce resource, it should be spent on the second, and the first
should be sampled rather than exhaustive.

One caveat I should not lose: the re-runs are cheap *because* they almost always
confirm, and their value is not the finding rate — it is that they keep the reports
honest. A lane that knew its reds were never re-checked is a different lane. Sampling
is the right adjustment; abandoning them is not.

## Runner notes from this batch

- **`ccc @glm52` on a verification-heavy increment: the best work of the day.** It
  exceeded its criterion rather than meeting it — I asked it to *state in its report*
  how it obtained the pre-change baseline; it instead made the baseline's honesty
  **machine-checked**, resolving the pre-change ref by content so a rebase cannot
  quietly turn the proof into a no-op. That is a lane improving the instruction it was
  given, which is the strongest signal I have seen from any runner.
- **It still missed the adjacent case** (above). So: excellent depth on the assigned
  chain, weaker sweep of the space around it. That maps cleanly onto how to use it —
  give it the hard verification chain, and do the perimeter audit myself.
- **The human fixed `ccc @glm52` mid-session** and it has since completed four lanes.
  The earlier "use opencode instead" routing note is spent and has been removed from
  `status.json`.
- **grok drew the geometry measurement** for #367 increment 2 specifically because it
  is multimodal: the task needs someone to look at whether a two-line tab still reads
  as a postit, and no number answers that.

## The cheapest refutation of the day, and it was cheap because I asked for it by name

#354's design lane (`ccc @grok`) refuted the ledger's own recorded recommendation in
**about five minutes**: `Range`/`206` is not the fix for `/filebytes` buffering a whole
file, because the common client is an `<img>` tag which sends **no `Range` header**. The
real fix is chunked streaming, with `Range` as a separate second capability.

**That refutation was not luck, and the contrast with today's other six is the finding.**
The earlier refutations arrived *incidentally* — a lane doing its assigned work noticed the
brief's premise was wrong. This one arrived because the brief contained a numbered question
whose text was, in effect, *"here is the specific claim I think most likely to be wrong,
and if you conclude the entry's own recommendation is incomplete, say so plainly; that is a
valuable result, not a contradiction of your brief."*

So the transferable practice is sharper than "give lanes permission to disagree", which I
already do at the bottom of every brief and which produces incidental refutations:

> **Name the single claim you would least like to be wrong, make it a numbered
> deliverable, and say that refuting it is a success condition.** A general permission
> gets used when a lane trips over the problem. A named target gets checked on purpose.

Two supporting details. First, the claim I named was **inherited from another agent and I
had told the lane to inherit it too** — *"What is established — inherit it, do not
re-derive it"* — so the invitation had to be explicit enough to override my own framing,
and it was, because it named the exact sub-claim rather than gesturing at the section.
Second, I nearly did not get this at all: I had started writing an **implementation** brief
for #354 and only found the design-only one I had written two hours earlier while trying to
save it. Had I dispatched the implementation, a lane would have built `Range`, every test
would have passed, and the 1GB buffer would still be there on the `<img>` path — a
correct-looking feature over an untouched bug. **The design-first order was load-bearing
and I had already reasoned my way to it once and forgotten.** That is an argument for
reading the briefs directory before writing a brief, which is now cheap and which I did not
do.

## The orchestrator's actual leverage is the numbered list, not the prose

This is the sharpest thing I have learned about the role and it cost a live defect on his
dashboard to learn.

`#385`'s brief asked the right question. In prose, in the gaps section, it said: *"The
questions headline is a new caller. Check whether a parseable timestamp reaches the client
for those entries, or whether one has to be added; if it has to be added, that is a
`watch.py` server-side change and it is in scope."* I wrote that sentence because I had
anticipated exactly the failure that then happened.

Its acceptance criteria asked that the headline **show** an age, and that a fixture's two
entries have ages that **differ**. Both held. The guard was green. I re-ran the lane's
discriminating red myself and it was a good red.

Fifteen minutes after I deployed it, the page showed a 24-minute-old question as
**`08h 17m ago`** — `data-ct` resolves to midnight, because a `questions.md` headline
carries a date and no time. The lane never answered the prose question, and nothing
required it to.

> **The lane optimises against the criteria. Prose is where I explain; the numbered list is
> where I bind.** Anything I actually need is a criterion or it is decoration.

I had been treating the two as interchangeable — a well-argued brief with a thin criteria
list felt like a strong brief, because *I* had done the thinking. But the thinking is only
transmitted through the part that gets checked. Every brief I have written this session has
a gaps-and-traps section far richer than its criteria list, so this is not one brief's bug.

**Second-order, and worse:** the criterion I was proudest of is the weak one. "Assert the
fixture's two values differ" is in nearly every brief I wrote today, and it guards against
a *vacuous* check, never a *wrong* one. Two ages can differ by two days and both be wrong
by eight hours. The general form is in `lessons.md`: a check comparing outputs to each
other cannot find a systematic error — **one value must come from outside the system.**

## The one verification a lane structurally cannot do, and it is mine

Thirteen lanes, ten guard runs, a clean `lint.py`, and five independent coordinator
re-runs all passed over an eight-hour error that was visible in a single screenshot of the
deployed page.

That is not thirteen failures of diligence. It is structural: **`just guards` copies
`dev/capture/fixture` to a temp target**, so every lane's verification runs against
synthetic data by construction. It has to — fixtures are what make guards deterministic.
The consequence is that no lane has ever looked at the real page with the real ledger, the
real question file, and the real clock.

> **The coordinator's unique instrument is the deployed artifact with real data.** Not
> better judgement, not more context — *access to the only environment nobody else can
> reach.* Deploying and then looking is a verification step, not a delivery step.

I had been treating `just deploy` as the last thing I do for *him*. It is also the first
thing I do for *me*, and it found in one screenshot what the entire check suite could not.

## Nobody reviews the coordinator

Found in the same twenty minutes, and it is the structural counterpart of the above.

I dumped every numeric field the dashboard renders and two were wrong — both in
`.dreamwork/status.json`, which **I** am the sole writer of. `current_task_ids` named
`[263, 385, 389]`, all three closed hours earlier; `deployed` named pid `1067667` at rev
`9dbc487`, a process that no longer existed. Both render on his page. `lint.py`'s queue-sum
check caught the count drift; nothing caught the other two, because nothing else knows what
is true.

The asymmetry is worth stating plainly:

> **I verify thirteen lanes. Nobody verifies me.** The ledger and `status.json` have a
> single writer *on purpose* — that is the right design, and it is exactly why the
> single writer's output is the only output in the system with no reviewer.

So the coordinator owes itself the discipline it imposes: derive the numbers from the source
rather than from memory, and re-derive rather than carry forward. I had been carrying
`current_task_ids` forward across ticks by editing the interesting fields and leaving the
rest, which is precisely how a field becomes a lie nobody notices. Recomputing the queue
count from `## Open` at every write costs one line and catches it.

The third instance in the same window: I recorded my own measurement as *"filed at 08:03"*
in the ledger, in a lesson, and in a brief. `git log -S` on the headline says **07:54**. The
defect was identical either way, but I had put an unmeasured number in the durable record
three times over while penalising lanes for exactly that — and the exact tool that
corrected it, an 18ms pickaxe, was one command away.

## Runner routing, updated

New this batch: the first task routed to `ccc @grok` **for vision specifically** rather than
for speed — the dashboard figure audit (`392-adj-figure-audit`), where half the deliverable
is reading rendered numbers as he would and screenshotting anything implausible. Previous
grok routings were speed-motivated and its multimodality was incidental. Worth scoring
separately when it reports, because "grok is faster" and "grok can see" are different
reasons to pick it and I have only ever tested the first.

Standing shape, unchanged by this batch: `glm52` for work whose difficulty is *judgement*
under a trap (a format decision, a not-weaker argument, a coupling nothing announces);
`grok` for work whose difficulty is *volume* (a design sweep, a measurement pass, a
mechanical transform) and now for anything needing eyes.

## Correction: this document was wrong about its own central number

I asked the `#264` evidence lane to check this document against `git log` rather than restate
it, and said that finding it wrong would be one of the more valuable things it could do. It
did, twice.

**1. "Thirteen lanes" conflated cumulative dispatches with concurrency, and this document's
tally drifts.** The lane traced it: *"nine"* at 06:56 → *"ten"* at 07:15 → *"thirteen"* in the
sections above. Git does not label lanes, so the honest figures are **~17 lane-instances
dispatched** across the session (**~12** counting `#263`'s sub-lanes as one) and **peak
concurrency 5**, at 06:30 — a number this document itself records and which I then wrote past.

The correction matters beyond tidiness, because **every claim above of the form "thirteen
lanes and nothing caught X" is really "five concurrent at most, seventeen over four hours"**.
Sequential lanes sharing a tree are a *much* weaker version of the experiment `#264` asks
about than five simultaneous ones, and I had been quietly claiming the stronger version. The
structural findings survive — a fixture-based guard still cannot see the real page — but the
*scale* evidence is thinner than I wrote.

The mechanism of the error is worth more than the error: I was updating a running count from
memory, one section at a time, with no single place holding it. **A number that appears in
prose three times and in a record zero times is not a measurement.**

**2. The `git commit --only` warning I put in six briefs is not evidenced.** I have been
writing that `--only` *"would still sweep in a concurrent lane's uncommitted work in the same
file"* and attaching *"that happened in this tree today"*. The lane looked: **no instance
found.** The one index sweep, `12f47e3`, was a plain `git commit` — that is `--only`'s
**absence**, not its failure. The hunk-level claim is true as *mechanism* (`--only` isolates
paths, and a path is not a hunk) but I presented a deduction as an observation. Two things
did happen and I should have cited those instead: a bare `git commit` burying a staged file,
and `--only <directory>` silently skipping untracked files (`d77630e`, `c036540`, three
briefs left uncommitted).

## The result that most changes what to build, and it kills an option

The lane's answer to *"what does the evidence rule out?"* is the most useful sentence produced
about `#264` today:

> **Record-level concurrency primitives — locks, CAS, leases, SQLite, per-record spools —
> would have prevented zero of the actual damage, because no two lanes ever wrote the same
> record.**

Zero concurrent-write instances across every writer and 121 commits in the window. The
single-writer ledger and the append-only inbox both held **by construction**. What actually
caused damage was shared **CPU** (load-starved guards producing deterministic false reds),
a shared **working tree** (dirty-file pollution and one index sweep), a shared **registry**
(one lane's new file reddening others' baselines), and **one overloaded single-writer file**.

So the evidence points at **modularity, not a concurrency mechanism** — and it names the
file: `watch.py`, with six tasks queued behind it. That is a conclusion I would not have
reached from inside the fan-out, because from here the problem *feels* like contention.

## The steering channel I trusted all session is unreliable, and I measured it late

I have written nine relay files today on the belief that a coordinator can steer a running
lane. That belief is now measured and it is half wrong.

**`#389`'s lane read its relay and acted on it** — its report carries *"Bonus red (relay's
second direction)"* and a whole section *"Relay (#389) neighbours — measured and decided"*.
**`#395`'s lane did not.** Its relay was written four minutes into a fifteen-minute run, and
its report mentions the relay zero times and did not do the thing the relay asked. Same
mechanism, same *"re-read it between increments"* line in both briefs, opposite outcomes.

**The discriminator is the lane's own decomposition, which it chooses after dispatch and which
I cannot see.** A lane that treats its task as one increment never reaches a boundary, so it
never re-reads. There is no timing I can pick that fixes this, and — worse — **a missed steer
is silent at both ends**: I cannot tell "read it and judged it irrelevant" from "never opened
it" except by scanning the report for evidence of receipt, which I had not been doing.

So the rule, and it is a sorting rule rather than a resolution:

> **Sort every steer by "what if this is never read". If the answer is "the deliverable is
> incomplete", it belongs in the dispatch prompt.** The relay is for refinements that are safe
> to miss — a ratification, a sharpened edge case, a neighbour worth checking.

I had been using it correctly by accident and incorrectly on purpose in the same hour: the
`#367` relay carried a *ratification* (harmless to miss — it confirmed something the lane had
already done), and the `#395` relay carried a *new obligation* (write a hand-off line), which
simply did not happen. The obligation is now in `SKILL.md` as a dispatch-time requirement and
`#397` is the first prompt to carry it, which makes its landing the actual test.

**The uncomfortable part** is that `#381`'s lane told me this hours earlier, in a section of
its report I read and enjoyed and filed under irony: *"the relay is itself a write-then-hope
channel: the coordinator writes a steer, a lane that has gone idle never reads it, and nothing
wakes it — the same class of problem one layer up."* It even offered the fix. I recorded the
observation and did not test the claim, and then spent two hours writing relays. **A lane
naming a defect in the coordinator's own machinery is the same signal as a lane naming one in
its own work, and I have a documented rule about the second and none about the first.**

## Worktrees: the constraint I managed by hand all session was already solved (10:00-10:40)

**The finding that should have come first.** File contention on `watch.py` was the binding
constraint on this whole session: it shelved `#354` inc1, serialised three dispatches, blocked two
tasks, made me hand-maintain an ownership list in `status.json`, and produced a **459-line design
document** (`#397`) whose own conclusion was *"the throughput win is captured more cheaply by a
worktree"*. `CLAUDE.md` names worktrees as the standing preference. `SKILL.md` says explicitly that
when disjointness cannot be arranged, the dreamer goes in a worktree **and the invariant then holds
by construction**. `git worktree list` shows `.worktrees/277-dreamfade` — the machinery had been
used here before.

**Every lane ran in the shared tree, and nothing consulted either rule.** Not a knowledge failure;
both documents were read at init. A **control-flow** failure: the coordinator checks ownership,
finds a conflict, and treats it as *do not dispatch*. The queue branch resolves the conflict, so the
worktree branch is never evaluated. **A rule that only applies after a decision the code makes
earlier is unreachable, however well documented.**

### What worktrees actually cost and bought, measured over three uses

| | Result |
|---|---|
| **Red-proof in isolation** (`#392a`) | Injected into a copy off `HEAD`; the live tree never went dirty. Strictly better than a `cp` snapshot — no restore step to get wrong |
| **Lane #401/#406** | Landed clean. Merge **conflicted** on `handoffs.md` (the lane reordered sections; main gained lines). Resolvable in one pass |
| **Lane #399** | Landed clean, **merged with no conflict** — regions 300+ lines apart |
| **Setup cost** | Negligible here. Pure Python, no build state to duplicate — the cost `SKILL.md` warns about does not apply to this repo |

**Three traps a shared tree hides, all silent:**

1. **`.dreamwork/inbox.md` is untracked, so it does not exist in a worktree.** A lane appending to
   the relative path creates a file nobody reads. This is the report-loss failure *made structural*.
2. **`.dreamwork/handoffs.md` is committed**, so a lane appends to its own copy — invisible until
   merge, or a merge conflict.
3. **A brief committed after the worktree was created is not in it.** All three are fixed the same
   way: **absolute paths into the main checkout, in the dispatch prompt.**

**And the constraint worktrees do *not* remove: adjacency.** `#399`'s target (`_landed_ids`) and
`#401`'s (`parse_handoffs`) are **27 lines apart** with the constants between them. Worktrees remove
the *contention*, not the *merge* — two lanes in one region still collide, just later and less
visibly. **Route by region, not by file.**

## A lane died with the work finished and uncommitted — and the worktree is why it survived

`#399`'s lane completed a correct, green, 260-line change and **died before committing or
reporting**. No report, no hand-off line, no commit. In the shared tree that work would have been
sitting in a dirty checkout that the next lane or a stray `git checkout` could destroy; in a
worktree it sat safely on its own branch's working copy until I committed it on the lane's behalf.

**That is an argument for worktrees that `#405` did not make**, and it is probably the strongest one:
they are a *durability* mechanism, not only a concurrency one.

The verification burden lands entirely on the coordinator when this happens — there is no report to
fold, so every acceptance criterion must be re-derived. That took about ten minutes and found the
work sound: 502 passed, sets disjoint, `questions.md` untouched, and an independent red that failed
five tests including the original master failure.

## Runner scorecard, second batch

| Runner | Lanes | Compliance | Notes |
|---|---|---|---|
| `ccc @grok` | 4 | Hand-off 4/4, correct section 4/4, report 3/4 | One lane **noticed and self-corrected** the `#406` section trap and reported it as an uncertainty. One died at the commit step with the work complete |
| `ccc @glm52` | 2 | Hand-off 2/2, correct section 1/2, report 1/2 | Produced the best single artifact of the day (`#397`'s plan, which refuted my measurement) |

Still a small sample. The one durable signal: **both runners produced work that corrected the
coordinator**, which is the property worth selecting for. Neither produced work that was wrong in a
way I did not catch.

## The coordinator's leverage, restated after another five lanes

Ranked by what actually found defects today, unchanged at the top and now with a new entry at #2:

1. **Looking at the deployed page.** Found `#392`, and today found that his browser tab read
   `· stalled` for two hours while the loop worked — `watch.py` was right and `status.json` was
   stale. **When a display is wrong, check whether it is faithfully displaying something wrong.**
2. **Verifying my own brief's citations before dispatch.** Cost two minutes; found that `#340`'s
   P1 was **already fixed**, that its "one-argument fix" was actually two asymmetric call sites, and
   that a lane following it would have attributed loop prose to the human — worse than the bug.
   **Reproduce the symptom before commissioning the fix.**
3. **Probing what a lane said it was unsure about.** Five for five over the session.
4. **Running the project's own full verification.** `just test` was **red on master for hours** and I
   did not know, because `lint.py` exits 0 on a WARN and every pytest run I made was a `-k`
   selection that excluded the failing test.


## Dispatch is not a solved problem, and it cost four lanes on one task

`#399b` — the P1 that has `master` red — was dispatched four times before I stopped.
Two of those were real deaths from one cause; the third was my own bad measurement, and
none of it was visible where I was looking.

**Deaths 1 and 2 — `ccc @grok` returns 401.** The runner's credential expired at some
point today. Every lane sent to it died at about three seconds. What made this expensive
rather than obvious:

- I dispatched with `> /dev/null 2>&1 &`, so the only artifact naming the cause was
  destroyed at the moment it was produced.
- **A lane that dies before its first token is indistinguishable from one that ran and
  reported nothing** — same clean worktree, same empty inbox, same absent process. I
  read the first as a mystery, and re-dispatched into the same wall.
- ccc's own run log looks like the answer and is not:
  `~/.local/state/cc-w/ccc/runs/<run>/` holds `output.txt` and `transcript.txt`, and for
  a 401 **both are zero bytes**. The error exists on stderr only.

**"Death" 3 was not a death. I killed a healthy lane's twin instead.** Dispatched with
`ccc @glm52 … &`, the lane read the brief, wrote a correct statement of the diagnosis, and
went quiet. I checked with **`pgrep -c "ccc @"`**, got `0`, and concluded it had been
reaped by the shell that started it. It had not: **`pgrep -c` matches the process *name*,
which is `ccc`, and never the argument string I was searching for.** The earlier checks
that worked used `-f`. The lane was alive and working the whole time; its transcript was
simply unflushed, which for a slow runner mid-tool-call is normal.

So I dispatched a fourth lane into **the same worktree**, and for about a minute two
agents were editing the same files — precisely the split-brain the disjointness invariant
exists to prevent. I stopped the newer one (one minute in, nothing lost) and kept the
incumbent.

This is the day's dominant class *again*, and now in my own instrumentation: **a check
that reports on something other than the thing you care about.** `pgrep -c` joins
`cmd | tail` returning tail's status, `lint.py` exiting 0 on a WARN, `sha256sum` printing
one line for a missing operand, and `grep -c` exiting 1 on zero. **Silence from an agent
and absence of an agent look identical, and the command that distinguishes them differs
from the one that does not by a single flag.**

**The recipe that follows, and it is three changes:**

1. **Never `/dev/null` a dispatch.** `> "$LOG" 2>&1`, and read `$LOG` the moment a lane
   looks quiet. One variable; it is what diagnosed the 401 on the third attempt.
2. **Liveness is `pgrep -cf`, never `pgrep -c`** — and a quiet transcript is not evidence
   of death. Before declaring a lane dead, require **two** signals that agree: no process
   *by command line*, and either an error in `$LOG` or an exit trailer.
3. **Prefer the harness's own background dispatch** (`run_in_background`) over `&`. Not
   because `&` fails — it plainly does not, the incumbent outlived its parent shell by a
   quarter of an hour — but because the harness notifies on exit, which removes the
   polling that produced this whole mistake. It also leaves the session's cwd alone.

**A note on the runners, and my first reading of it was backwards.** I recorded this as
"the fleet is one runner deep". It is the opposite: `grok-4.5` alone is 401, and the
**eleven `llmp-*` models became reachable through the same CLI today** (see the routing
table above). The fleet got *wider* during the outage, not narrower. What is true is the
narrow part: **a runner outage presents as a brief that does not work.** Three times I
reached for the brief, and the brief was fine.

**And the quiet-transcript trap was already in this file before I fell into it.** The
05:58 observability note above says it plainly: grok and pi runners write **zero bytes
until exit**, and "the only mid-run signal is the filesystem". I re-derived that at 11:07
as a lane death and acted on it. The note was right, it was two screens up, and I did not
re-read it. **A record only prevents the mistake if it is consulted at the moment of the
mistake** — which argues for putting this kind of finding where the action happens (the
dispatch recipe) and not only where the reasoning was written down.

## Addendum to the leverage list: what found things this batch

The ranked list above still holds, and this batch added a fifth that belongs on it:

5. **Distrusting an alarming measurement before distrusting the system.** A directory
   listing told me six `.dreamwork/` files had been deleted. They had not — an earlier
   `cd` into a worktree had persisted between tool calls, and a worktree by construction
   has no untracked files. `lint.py` had been printing the wrong target path as the first
   line of its output for four consecutive runs while I grepped that output for
   `WARN|ERROR`. **A filter narrow enough to be useful is narrow enough to hide the line
   that says which file you are looking at.** What broke it was not re-reading the header
   but noticing two readings disagree: `ls` said six files gone while `lint` said
   `handoffs.md`, `questions.md` and `watch-port` were all fine. A directory cannot be
   half-deleted.

## A prediction, written at 11:22 while the lane is still running

Recording this **before** the outcome so it is a prediction and not an explanation
invented afterwards.

The `#399b` lane (`@glm52`, glm-5.2, reasoning-effort high) is **20 minutes in with 42
seconds of CPU and not one byte written** — no commits, clean worktree. Its one flushed
message, at T+1min, states the diagnosis correctly and completely. So it understood the
task immediately and has produced nothing since.

**Hypothesis: the brief is too long for this runner.** `399b-landed-history.md` is ~150
lines and dense — seven acceptance criteria, a discriminating-pair red requirement, five
enumerated neighbours, a hollow-outcome warning, and a "who calls this" question. That
shape has worked well on `@grok` (lane B did a three-guard characterisation matrix from a
brief of similar weight, in 38m). It may be actively wrong for a slower model at high
reasoning effort: **every criterion is another thing to hold, and holding is what this
runner is slow at.**

**What would confirm it:** a short brief — the fix, one test, `just test` green, nothing
else — completing faster on the same runner. **What would refute it:** this lane landing a
complete answer at ~35 minutes, i.e. the brief was fine and glm-5.2 is simply slow and
back-loaded (which the 05:58 observability note predicts, since grok-runner lanes write
nothing until exit).

The second is quite possible and I should not act as though the first is established. The
distinguishing evidence is CPU: **42 seconds over 20 minutes is not a model thinking
hard**, it is a model waiting on a slow API. If the brief were the problem I would expect
CPU to accrue. So on the evidence I have, "slow and back-loaded" is currently the better
explanation, and the brief-length hypothesis is the one I would test second, not first.

**Either way, one thing is already measured and does not depend on which is right:** the
coordinator-only mode has left `master` red for over an hour on a P1 whose diagnosis,
merge gate, and independently-derived analysis were all complete within the first fifteen
minutes. **The bottleneck is not knowing what to do; it is having someone to do it.** That
is the most important dogfood result of the session so far, and it is a cost of the mode
rather than a fault of any runner.
