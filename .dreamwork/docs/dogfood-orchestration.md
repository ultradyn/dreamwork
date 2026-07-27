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
