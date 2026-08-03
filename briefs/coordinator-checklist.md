# Coordinator brief checklist

Use this before `just dispatch-lane`. The wrapper mechanically proves only the
base-state item; the remaining checks require coordinator judgement. They are a
checklist rather than semantic lint because wording proxies have already named
healthy briefs and cannot reliably distinguish instructions from evidence.

- Give the lane one `Base sha: <git revision>` line. Obtain it with
  `git merge-base master <branch>` at dispatch; never substitute a commit
  distance. The wrapper resolves the revision and refuses it unless it is the
  branch point of local `master` and the named branch.
- Name every standing-rule override explicitly and name the rule it replaces.
  Remove contradictions within the task-specific head — **and between the head
  and the boilerplate it is composed with.** The head is read as an addition to
  the standing rules, not as a replacement for them, so a head that restates a
  rule differently is a contradiction the lane must resolve on its own. `#1171`
  round 2 reported this: the head cited
  `/home/xertrov/.claude-p/skills/ud-dreamwork/igc-method.md` while
  `boilerplate.md:315` says to use the worktree-local `./igc-method.md` and not
  to read under `~/.claude-p/`. The two copies happened to be byte-identical, so
  nothing was decided wrongly — but the lane had to establish that itself before
  it could proceed. **When the head needs to point at a resource the boilerplate
  already governs, cite it the boilerplate's way.**
- State a conditional deliverable conditionally at its first imperative.
- Derive scope and verification lists from the moved symbol's callers and
  caller fallout, not from expected diff ownership.
- Present observations as measurements, with the command or method that
  produced them. Never instruct a lane not to re-derive a measurement. Mark an
  unreproduced premise as unverified and make non-reproduction a valid result.
- **Before asserting that a file contains something, or that a tool behaves a
  certain way, OPEN IT.** On 2026-08-04 three briefs shipped in one day with a
  premise I had not measured: `#1177` said `reap.py` asks sha identity when it
  has called `git cherry` since `db6078e8`; `#1170` said `briefs/boilerplate.md`
  carries a bare `cat >> …inbox.md` recipe when it carries none; `#1175` round 3
  cited `#1153`'s identity split for a pair it does not describe (the redproof
  launch token vs its hashed registry directory — not a status entry's lane name
  vs the probe's, which do match). Every one was caught by a lane's premise-stop,
  each costing a dispatch. A one-line `grep` or `--check` run would have caught
  all three in seconds. **The tell is a sentence about the codebase written from
  memory rather than from a command** — those are the sentences to verify, and
  the cheapest moment is while composing, not after a lane stops.
- Keep the "if a premise here is false, STOP and report" clause in every brief,
  and scope it per-deliverable. It is what turns the mistake above from a wasted
  round into a ten-minute correction, and it is the single highest-value
  paragraph in the boilerplate. Where a stop was correct, **say so plainly in
  the next round's brief and name the error as yours** — a lane that is told its
  refusal was right refuses again when it should.
- **Derive `Lane-owns:` from the deliverables, not from memory of the diff.**
  Read each numbered deliverable back and name the file it lands in. On
  2026-08-04 two headers failed within an hour, in opposite ways. `#1071`'s
  wrapped across two lines with a parenthetical, and `launch-lane` refused at
  `phase=brief-generation` — *"an empty selection is indistinguishable from
  broken derivation"* — which cost two minutes and is the refusal working. But
  `#1049` round 11's listed neither `client/style.css` nor `watch-design.md`
  while its own P2b required styling **and** an authoritative styleguide entry;
  every path resolved, so nothing refused, and the lane reported it afterwards
  in its dogfood. **The tool checks that the paths resolve, never that they are
  the right paths** — so a clean dispatch is not evidence the header is
  complete. Keep it one line, plain paths, no parentheticals.
- Put the measurement instrument beside every numeric bar so a reader can
  audit how the number was obtained.
- **Never quote a piped command's empty output as a measurement.** The exit
  status dies in the pipe and a failed command's empty stdout is
  indistinguishable from an empty result. `ledger.py list --status open | grep …`
  returned nothing and I filed the nothing as evidence in `#1185`; the verb
  takes `--state`. Check the verb's own `--help` first, and let the conclusion
  survive redoing the measurement before it survives being written down.

## Mechanism decision (IGC)

Context: persisted briefs exist from task 766 onward; the governed corpus has
one known bootstrap exception, while semantic wording proxies have produced
false attribution.

| Idea | All | G1 | G2 | G3 |
|---|:---:|:---:|:---:|:---:|
| Checklist only | ✘ | ✘ | ✔ | ✔ |
| Dispatch base gate only | ✘ | ✔ | ✔ | ✘ |
| Semantic dispatch lint | ✘ | ✔ | ✘ | ✘ |
| Base gate plus checklist | ✔ | ✔ | ✔ | ✔ |

- **G1:** a missing, unresolvable, or wrong base is refused before runner exec.
- **G2:** healthy governed briefs are not refused by wording proxies.
- **G3:** judgement failures have an honest coordinator-facing home.

The checklist-only idea cannot prevent dispatch. A base-only gate leaves the
other brief species structural only in memory. Semantic lint is refuted because
text shape cannot establish contradiction, scope completeness, or world truth.

- **When `launch-lane` says it derived zero tests from `Lane-owns`, read it as a scope finding, not a
  formatting complaint.** `#1184` owned only `landed-guards.md`; the refusal said *"selected 0 existing
  test(s) … an empty selection is indistinguishable from broken derivation"*. It was right on the
  merits: the change removes a `lint.py` WARN row, and whatever test asserts the WARN population has to
  be in scope to be updated. A doc-only scope for a change with a measurable output is usually a scope
  that is too small, and the derivation is what notices.

- **`Lane-owns:` paths are COMMA-separated, not space-separated.** A space-separated
  list parses as ONE entry and refuses with `scope derivation FAULT: resolved 0 existing
  files from 1 Lane-owns entrie(s)`. The message names the count that gives it away —
  `1 entrie(s)` for five paths — but the refusal prints below several NOT CHECKED
  reports and above a `no controlling tty` note, so it is easy to misread the tty line
  as the cause. Read the `REFUSE phase=` line, not the last line (2026-08-04, #1163).

- **Cite the IGC method as repo-root `igc-method.md`, never
  `/home/xertrov/.claude-p/skills/ud-dreamwork/igc-method.md`.** The standing contract
  tells lanes not to read under `~/.claude-p`, so a brief citing that path asks the lane
  to break a rule to follow an instruction. A #1190 lane reported the contradiction; it
  did not block only because the worktree-local copy happened to match (2026-08-04, #1190).

- **Before writing "confirm the WARN row disappears", ask where the lane will be standing
  when it looks.** Several lint checks resolve against the working tree and exclude
  `/.worktrees/`, so a lane cannot observe them at all; the gate's own lint runs from
  `.worktrees/.gate-*` and is equally blind. An instruction only the main checkout can
  satisfy is unsatisfiable for a lane (2026-08-04, #1184).

- **Dispatch reviews with `dev/dispatch_lane.py --launch-review`, not by hand** (2026-08-04, #1163).
  It pins the reviewed SHA, creates `<branch>-review-r<round>` as an **attached** branch worktree,
  records `.launch.json`, launches from that worktree's cwd, and verifies runner containment.
  Hand-rolling `git worktree add --detach` + `ccc` is what produced the lane-containment ERROR that
  blocked an unrelated clean-MERGE landing, and left four worktrees unreapable. Note a review worktree
  still refuses `reap` until its lane lands — its branch legitimately carries the lane's unmerged shas
  — so that refusal is correct and is not a reason to reach for `--detach` again.

- **Never quote a WARN-count or a "known false positives" number in a brief; tell the lane to pin its
  own pre-rebase row set and compare against that** (2026-08-04, #1190 r2). The brief's "three known
  `lesson citations` rows" became four within the hour, because a coordinator lessons commit added a
  citation that trips `#1176`. A lane that trusts the number either reconciles to a stale figure or
  reports a false drift; a lane that pins its own baseline is right regardless of what master does
  underneath it.

- **When a task is unblocked by another task landing, say what changed and tell the lane to re-derive,
  not to reconcile** (2026-08-04, #1071 r4). Its blocking measurement — 165185 against a 165000 budget —
  was taken against a tree 42 commits old and is now meaningless. Carrying a stale number into the
  unblocking brief is how the number outlives the condition that produced it.

## From 2026-08-04's landings (#1189, #1188, #1169, #1071, #1194, #1193, #1180)

- **Verify a liveness/absence probe in the POSITIVE direction before trusting it.**
  `tr -d '\000'` over `/proc/*/cmdline` deletes the NUL separators, so
  `sed -n '2p'` can never print argv[1] for a command with no embedded newline —
  the probe reported a running landing gate as dead and cost two redundant gate
  launches. Use `tr '\000' '\n'`. More generally: run the probe against a case
  you KNOW is positive and watch it say so.
- **A 0-byte log and a missing exit marker are the NORMAL early state of a healthy
  redirected background job**, not symptoms. Python block-buffers stdout to a
  file; the exit marker is written after exit. Do not read them as corroboration.
- **Check a citation's HOLDING, not just whether the words appear.** `#1180` r1
  stopped because I hung an auditability rule on `#612`, whose sentence I quoted
  correctly but whose decision ran the opposite way (it TRUNCATED an over-long
  report). If no task states the requirement, state it as mine with no citation —
  a lane can weigh an uncited requirement, but must refuse a false attribution.
- **`land_lane` can exit 1 on a branch that LANDED.** All six gates can pass and
  master advance, then `phase=retirement` refuses because `reap` found a
  non-disposable ignored file. The batch summary then prints `REFUSED`, which
  reads as did-not-land. **Always check master's head against the merge sha
  before re-gating anything.** Filed as `#1197`.
- **Carry-forward dispatches must create the branch AT the carried head**, and
  must name the whole STACK, not just its tip — `#1189` round 1 was a 3-commit
  stack and a literal one-commit cherry-pick would have dropped the production
  fix; `#1071` had to re-point an otherwise-empty branch.
- **`dev/lane_scratch.py job-launch` / `job-wait` is now the supported background
  recipe** (`#1169`, `da98635a`), with the form in `briefs/boilerplate.md`. Point
  lanes at it instead of `nohup`; five bare `nohup` launches were measured dying
  with 0-byte logs while five `setsid` controls survived.
- **`lessons_index.py --act` is now bounded to six plus an explicit `N more` and
  an `--all` command** (`#1194`). It was printing 423–5189 lines per act. When an
  act's top six look wrong for the task at hand, run `--all` rather than assuming.

## Reaping review worktrees (adopted 2026-08-04, from #1180's IGC)

`#1180` landed `dev/reap_sweep.py` — report-only by default, `--apply` explicit, exact-basename holds
in `dev/reap-holds.txt` loaded fail-closed, `.gate-*` always skipped, main checkout excluded
structurally (`worktrees[1:]`). Run `python3 dev/reap_sweep.py` on a quiet tick to see
`reaped/reapable/refused/held/live`; nothing is removed without `--apply`.

**Its IGC also named a coordinator-custodial trigger that no lane can land, and I am adopting it:**
**reap a review worktree when I read that review's verdict.** That has the smaller apply-time
first-error blast radius than a periodic sweep (one known-finished worktree at a time, at the moment I
have just read its output), and the periodic sweep is the fallback for everything it misses. Both, not
one instead of the other.

- **When a brief deliberately departs from its task record's own conclusion, SAY SO IN THE BRIEF.**
  `#1180`'s record concludes a sweep is a bail-out and review-exit is the remedy; my brief closed off
  review-exit (coordinator-custodial, not lane-landable) and mandated the sweep without saying it was
  departing. The lane had to reconcile two authoritative texts, and said so.
- **Do not file a finding from a summary line without checking the mechanism.** `reap_sweep`'s report
  lists `REFUSED master`, which looks like the main checkout being caught by luck rather than excluded
  by design. It is not — that is a *linked* worktree at `/tmp/glm1038-master-review.ep08Nq/master`
  whose basename is coincidentally `master`, and the main checkout is excluded structurally. One
  command settled it.

### Correction, same day: the trigger is the LANDING, not the verdict

The rule above is wrong as I first wrote it, and the first attempt to follow it refused. A review
worktree is an *attached* checkout of the branch under review, so it holds exactly that branch's
unmerged commits. Reaping it at verdict time gives:

    reap examined path=.../cx-1166r9parse-review-r9 ... unmerged-commits=17
    REFUSE: unmerged commit would become easier to delete unseen: ... (x17)

That refusal is correct and must not be forced — `dev/reap.py --force` is never the answer. After the
reviewed branch landed, the identical command reported `unmerged-commits=0` and removed it cleanly.

**So: reap a review worktree when its reviewed branch LANDS.** Reading the verdict is when the
worktree becomes *finished*, not when it becomes *reapable*. The lane's own worktree needs no action —
`land_lane`'s retirement phase reaps it as part of the gate.

## Reading a review verdict (2026-08-04, #1166 r9)

A review gives you three separable things, and they can point in different directions:

- its **verdict word** (`MERGE` / `MERGE WITH FIXES` / `ANOTHER ROUND`) — a recommendation;
- its **constructions** — evidence, and the most valuable thing it produces;
- its **stated consequences** — claims, which you can and sometimes must check independently.

`#1166` round 9 returned `ANOTHER ROUND` on a branch with no defect of its own: the reviewer labelled
its single finding "inherited — already present at `f860a1cb`, not introduced by round 9". The
construction was real and reproduced. The consequence — "it wedges the next landing; the row-set gate
refuses" — was false, because `land_lane` reads BOTH the baseline (`:2169`) and the merged tree
(`compare_lint`) with `_lint(gate_worktree)`, the same worktree on both sides, so the WARN appears in
both readings and cancels. The reviewer had compared main-checkout lint against its own
review-worktree lint, a pairing the gate never forms.

I gated it, and the gate settled the dispute in the branch's favour:
`lint-comparison WARN row-set comparison: added=0 removed=0`, `baseline=11 rows; post-gates=11 rows`.

- **Check a consequence before spending a round on it.** A round 10 here would have asked the lane to
  fix `#1191` — a separately filed task that was itself blocked on this branch landing.
- **An inherited finding is a task to file or note, not a reason to refuse the branch that found it.**
- **Corroborate with history when you can.** `2b682505` (the commit that created the divergence) was
  already an ancestor of three successful merges. That was decisive before any argument about
  mechanism.

## Brief-generation refusals I hit this session, and the shape of each

- **`Lane-owns:` needs at least one existing FILE.** A directory alone gives
  `scope derivation FAULT: resolved 0 existing files from 1 Lane-owns entrie(s)` —
  *"Lanes creating only new files must also name an existing owned file."* For a lane whose
  deliverable is a new document, name the existing sibling it will legitimately update.
- **Do not prohibit a whole file class.** *"This task produces one markdown file"* was refused:
  it *"prohibits the whole Markdown-file class while the standing contract requires
  `.dreamwork/inbox.md` and may require a `.dreamwork/dreams/<date>-<time>-<slug>.md`"*. **Protect by
  identity** — name the documents not to edit, and name `inbox.md` and `dreams/` as explicitly outside
  the prohibition.
- **Cite lessons as `.dreamwork/lessons.md:N`, never bare `lessons.md:N`.** A lane reported the bare
  form cost it a failed lookup; there is no `lessons.md` at the repo root.
