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

| alias | route | verdict |
|---|---|---|
| `@grok` | grok CLI, `grok-4.5` | **works** |
| `@glm52` | grok CLI + `provider=llmp`, `glm-5.2` | **BROKEN — cannot work** |
| `@oc-glm52` | opencode + `zai-coding-plan`, `glm-5.2` | **works** (smoke-tested) |
| `@pi-glm52` | pi + `llmp`, `glm-5.2` | **prefer this for glm-5.2** (his 05:26 steer) |

**Use `@pi-glm52` rather than `@oc-glm52`** — his heads-up at 05:26: opencode
**hangs** when it touches `/tmp` or similar. Confirmed observable in lane A, which
ran `rm -rf /tmp/opencode/green && mkdir -p /tmp/opencode/green && node
dev/capture/plugcmd.mjs /tmp/opencode/green 39897`. It did not die — CPU kept
accruing and the transcript kept growing — but it went very slow, and a stalled
transcript is indistinguishable from a dead agent without checking `ps`. Since the
guards' own `justfile` recipe uses `mktemp -d` (i.e. `/tmp`), **any guard lane is
exposed to this**, which makes pi the right default for guard work specifically.

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
