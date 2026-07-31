# Parallelism architecture — the lived fleet, and the norms that make it cheap (#124)

Human-proposed 2026-07-25 (~10:45): *"break up watch.py and adopt norms
that help work in parallel for faster dreaming (note: we don't want to
overuse subagents by default, might get expensive, but if the user asks for
parallelization, then we have the option provided we first have the right
architecture)."*

This plan was first written the day it was filed and **predates the entire
multi-lane era**: the first fan-out ran the same evening, and the fleet it
described (one file, one writer) became the four-lane reality it now has to
account for. It was refreshed 2026-07-30 (lane-124plan) against current
code, with every claim re-verified by file:line. What follows keeps the
parts that held, names what was **SUPERSEDED** and by what, and ends with a
re-scoped remainder as a recommendation.

The framing still holds, and it is the whole point: **parallelism stays
opt-in, the architecture stops making it impossible.** Today a `parallelize`
request against the webui can be honoured by several lanes at once — but
only across disjoint files, and `watch.py` still admits exactly one writer.

## What superseded the original's measurement

The original measured `watch.py` at **4,008 lines / 58 commits on one day**
and concluded it *is* the bottleneck, not just feels like one. Both halves
of that are now sharper:

- **watch.py is 15,563 lines** (verified `wc -l`, 2026-07-30) — nearly 4×
  the original measurement, and still the largest single file.
  ~~**still the single deployed file** (the single-file, no-build,
  one-authority deploy it predicted the split must not break is intact:
  `watch-design.md`'s "one file by design" line)~~ — **that parenthesis was
  already stale when written and is corrected here (2026-07-31, `#633`)**;
  this doc's own "What must not break" section below supersedes all three of
  its claims. Deploy ships a **directory**, not one file (`#480`/`#425`,
  `ship_siblings`); **no-build was retired 2026-07-30** (his `#505` Q2 ruling,
  `0f97df03`); and **one-authority now reads per-surface** — he ruled
  2026-07-31 17:03 that the UI is **transitioning to a component-based React
  web UI** (`#591`, receipt `dc9200a0-4ebf-5d3b-afab-71257155bef9`), with the
  claude-design breakpoint component-level and staged. **Then on 2026-07-31
  19:09 (`#614`) he relaxed the renderer sentence outright and scoped the
  second-truth rule to on-disk master state** (canonical: **One fact, one home
  on disk**, `DREAMWORK.md` Philosophy) — so "one-authority" is no longer a
  render constraint at all; the component surface is still **derived**
  (wrappers compiled from the same `client/*.js` `watch.py` serves, no markup
  restated) because that is cheapest, not because a rule demands it. What
  *does* survive from the original claim, and is this section's actual point,
  is the ownership fact below: `watch.py` still admits **one writer at a
  time**, and that is the bottleneck — not the deploy shape.
- **The binding constraint on fan-out is file ownership, not model capacity
  and not load.** Measured at peak concurrency five
  (`dogfood-orchestration.md:313–321`): *"I could run eight. I cannot run
  two lanes in `watch.py`."* A `delegation: 4` posture (the average-concurrency
  target, `#445`) is routinely starved not by the fleet ceiling but by one
  file admitting one writer. The lever that would raise throughput here is
  **modularity**, and `#264`'s evidence lane reached the same conclusion by a
  different route: *"record-level concurrency primitives would have prevented
  zero of the actual damage, because no two lanes ever wrote the same record …
  the evidence points at modularity, not a concurrency mechanism, and it names
  the file: `watch.py`"* (`dogfood-orchestration.md:780–796`).

So the bottleneck thesis survived and intensified. What did **not** survive
was the original's "candidate seams, in the order they pay" — the splits
that actually happened were demand-driven, and the file did not come apart
the way the list assumed. See the "seams" section below.

## Running a 4-lane fleet from this doc alone

A fresh coordinator dispatched into this repo runs the fleet under these
rules. Each is learned the expensive way; each cites where it is enforced.

### Dispatch shape

- **Dispatch is the harness's native `spawn_subagent` with worktree
  isolation** (current policy: `DREAMWORK.md:364` — *"set 2026-07-29 18:02
  (this harness's native `spawn_subagent`)"*; the `ccc`-runner bullets above
  it are the previous harness's form of the same two-model policy).
- **A `spawn_subagent` lane is an independent `.git` clone, not a git linked
  worktree.** This is the one fact a fresh coordinator must hold, because
  everything about containment follows from it: its `.git` is a full
  independent directory (no `commondir`), so `git worktree list` shows only
  `master`, and every registry built on `git worktree list` **sees zero
  spawn_subagent lanes** (the `#423` audit, `findings/423-dead-runner-audit.md:60–90`).
  Two lanes have committed directly on `master` and been accepted after
  verification, because the lane-containment guard does not see them.
- **The coordinator plans; the lane executes a written brief** (human-set,
  `DREAMWORK.md:166–181`). The brief is a **file** under
  `.dreamwork/docs/briefs/<id>-<slug>.md`, carrying measurable goals and
  acceptance criteria. The brief, not the prompt, is what survives a
  re-dispatch after a failure.
- **Each brief declares what the lane owns** — see the ownership grammar
  below. The brief is the only place file ownership is recorded that the
  guards read.
- **Dispatch the right model by capability, then by task shape**
  (`dogfood-orchestration.md:1190–1230`): vision/pixels → the multimodal
  runner; subtle correctness where being wrong is expensive and invisible →
  the reasoning runner. Acceptance criteria that *name a modality* make the
  routing decision for you.

### Ownership grammar

- **`Lane-owns:` in the brief is the single source of file ownership.**
  One or more comma-separated repo-relative paths (`file-formats.md:1950+`);
  a path ending `/` owns the whole directory. `lint.check_brief_lane_owns`
  ERRORs on a worktree brief that declares none, so the omission is loud at
  dispatch rather than a silent no-op at commit (`SKILL.md:385–399`).
- **The invariant is disjointness: parallel increments — the coordinator's
  own, or several lanes' — only ever touch disjoint files, so there is never
  a split brain over the same files** (`SKILL.md:335–340`). Route by
  *region*, not by file: two lanes in one 300-line neighbourhood of
  `watch.py` collide at merge even if their files differ
  (`dogfood-orchestration.md:860–866`).
- **`watch.py` admits exactly one holder at a time.** Seven of the eight
  coherent batches measured in the original plan needed it, and that ratio
  held: the fleet routes around the single writer by ownership, not by
  splitting the file (yet). Everything else can be READ-ONLY to a lane.
- **Disjointness must cover the environment, not only files** (`DREAMWORK.md:201–209`):
  CPU, guard ports, and the wall clock are shared. A lane that consumes a
  scarce thing is scheduled against the lanes that measure it.

### Committing: the one concurrency rule with no exceptions

- **While anyone else holds the tree, commit with `git commit --only <paths>`**
  (`SKILL.md:340–355`; `CLAUDE.md` conventions). `git commit` commits the
  whole **index**, so a file another agent had staged rides along in your
  commit under your message even though you never named it — and avoiding
  `git add -A` does not prevent it. The incident is `12f47e34`: a `file(#387)`
  ledger commit (`tasks.md`) that also carries `test_user_events_digest.py`,
  a peer's staged test. **`--only` commits exactly the named paths and leaves
  the rest of the index staged** — verified.
- **Two edges, both measured:** `--only <directory>` silently skips
  untracked files inside it, so a NEW file needs `git add <file>` before
  `git commit --only <file>`; and re-checking the outcome beats re-checking
  the intent — `git show --stat` after a confident commit
  (`dogfood-orchestration.md:771–779`). Note the `dogfood` correction: the
  original plan's stronger claim that `--only` *"sweeps a concurrent lane's
  uncommitted work in the same file"* was a deduction, not an observation
  — the path-level rule and the `<directory>` trap are measured; treat a
  hunk-level claim as plausible mechanism, not evidenced fact.

### Lane completion: look at the tree (#535)

- **At lane completion, look at the tree before treating the lane as done**
  (`#535`, from the `#423` audit; `SKILL.md:370–385`). A lane that *worked
  but did not commit* is invisible to every automated signal — `sweep`
  reads commit subjects, the lane-containment registry sees only `wt/*`
  linked worktrees, and `status_sync` knows alive-or-gone, not
  gone-with-work-left-behind. So when a lane's completion notice arrives (or
  is reconciled after compaction), run `git -C <lane-tree> log --oneline`
  since dispatch and `git -C <lane-tree> status --porcelain`:

  | exit state | `git log` since dispatch | `--porcelain` | action |
  |---|---|---|---|
  | delivered | new commits | clean | fold normally |
  | crashed before working | empty | clean | retire quietly |
  | **worked, did not deliver** | empty | **dirty** | **commit/salvage on the lane's behalf and record** |

  The `gate2`/`da197b87` recovery was the dirty case, found by luck; this
  one command at one step closes it.

### The merge-gate: the coordinator owns verification, with independent red

- **A lane never runs `just test` or the full guard suite; the coordinator
  owns both** (`#424`; `SKILL.md:400–410`). The browser guards bind
  39890–39899 and the recipe hard-aborts if any port in the range is held,
  so with N lanes live at most one process can ever run it — and worse,
  parallel lanes **destroy** this repo's verification: motion guards assert
  on intermediate frames, and a CPU-starved browser drops them, so the
  checks fail *deterministically* under sustained load (load 125 on 16
  cores reddened four guards that passed alone; `dogfood-orchestration.md:253–300`).
  A lane runs targeted pytest + `lint.py` only (plus its *own* guard, solo,
  after checking the range is free); **the coordinator verifies guards once
  on the merged tree before folding.**
- **The merge-gate's quality bar is independent red.** The coordinator
  re-runs a lane's discriminating red from its own snapshot rather than
  folding the report (`dogfood-orchestration.md:425–445`): re-running a
  lane's own reds almost always confirms it, but it keeps reports honest, so
  **sample rather than exhaust**. The higher-yield move is to **probe the
  boundary of a lane's stated uncertainty** — a lane's flagged edge case is
  usually fine and the one beside it usually is not (`:555–595`).
- **Delegation moves the labour, not the responsibility** (`dogfood-orchestration.md:494–500`):
  the coordinator still reads the cited lines itself. A coordinator who
  accepts reports is forwarding, not coordinating. And nobody reviews the
  coordinator — the single-writer ledger and `status.json` have no reviewer,
  so the coordinator owes itself the discipline it imposes: derive numbers
  from the source, never carry them forward (`:706–735`).

### Delivery and steering: coord-inbox + handoffs.md

- **A lane that LANDS a commit writes two things, not one** (`#394`;
  `SKILL.md:480–498`): its report to the coord-inbox, **and one line to
  `.dreamwork/handoffs.md`'s `## Pending` — which it must also commit**,
  named among its paths. "Write this" is not "commit this"; the first lane
  asked for a hand-off appended it and left it unstaged. The two are read by
  different things: the inbox carries judgement, read once in prose; the
  hand-off carries the id + sha, read by `lint.py` and the dashboard forever.
  In a worktree/clone, give both as **absolute paths into the main checkout**
  — a repo-relative path is silently wrong in a worktree (`SKILL.md:411–419`).
- **Steering takes two acts: write, then wake** (`SKILL.md:500–512`). The
  inbox is durable but not delivered — a lane reads it *between increments*,
  so an idle one never sees it. Write with `relay.py`, then send through the
  harness. **But the inbox is unreliable for anything mandatory, measured**
  (`DREAMWORK.md:193–209`; `dogfood-orchestration.md:799–835`): a lane that
  treats its task as one increment never re-reads. Sort every steer by *"what
  if this is never read"* — if the answer is "the deliverable is incomplete",
  it belongs in the dispatch prompt, not the relay.

## Known containment gaps, and their status

The disjointness invariant is void the moment a lane edits the main checkout
instead of its worktree. Two guards exist and both have a measured ceiling.

- **The `#465` lane-containment guard** (`dev/lane_guard.py`) refuses a
  main-checkout commit whose staged paths intersect a live lane's owned set.
  Its registry is `git worktree list --porcelain` filtered to `wt/*`
  (`dev/lane_guard.py:81` `LANE_BRANCH_PREFIX = "wt/"`, `:147`). **It sees
  `ccc` linked-worktree lanes and is blind to `spawn_subagent` independent
  clones.** The `#468` lint backstop (`lint.check_lane_containment_backstop`)
  ERRORs when a lane-owned path is dirty in the main tree; same `wt/*`
  registry, same blind spot.
- **Neither guard is write-time containment** (`#450`;
  `harness-containment.md`): on the harnesses the loop dispatches, a `Write`
  with an absolute path is not interceptable before it lands — cwd, `git -C`,
  and the brief do not stop it. The guards fail at first *commit* (or after
  the write via lint). Do not read either as a guarantee a lane cannot touch
  the main checkout.
- **#465 is OPEN** (P1, in the store). The live gap under the current
  `spawn_subagent` dispatch: a lane can edit the main checkout and **neither
  guard sees it** (the registry enumerates zero harness-clone lanes), so
  nothing notices until a merge fails or a coordinator commit sweeps the
  lane's half-finished edits (`#465` brief; the `12f47e34` shape, one level
  worse). Write-time interception needs process authority that run-mode /
  posture grant none of (`#288`); the honest state is *known deficiency,
  noted, defences built where they can attach* — the post-commit guard, the
  lint backstop, the `Lane-owns:` declaration, and the `#535` exit-dirtiness
  check. The un-covered half (write-time, and the spawn_subagent registry
  gap) **awaits his consent** on the authority question.

### The `#537` dispatch field (why a live fleet doesn't get pruned)

Because `spawn_subagent` lanes are independent clones with no `ccc` process
and no `wt/*` worktree, the liveness probe (`kill -0` on a pid, brief-path
fallback) **cannot ever see them**. So the `dreamers` entry carries an
optional `dispatch` field recorded at dispatch time (`file-formats.md:1448`):
absent is the historical `ccc` default (observable); a value not in
`status_sync.OBSERVABLE_DISPATCH` — `"spawn_subagent"`, the only entry today
is `("ccc",)` (`status_sync.py:209`) — is **carried verbatim past the probe
and reaped only by the ledger** (its task leaving `## Open`), never by the
probe. An observation blind to a form must not prune records of that form; a
live `spawn_subagent` fleet was once pruned to 0 by exactly that mistake.

## Norms that survived, and how they sharpened

The original plan's norms list mostly held; several were promoted from
advice to enforced contract, and two new families were added.

- **Parallelism is a capability, not a default.** Still true, and now the
  posture axes make it sayable: `delegation` is an **average-concurrency
  target** integer, not a cap or a refusal (`#445`; `SKILL.md:148–190`).
  `parallelize` is the explicit fan-out; the coordinator still works one
  inline increment at a time.
- **Shared vocabularies get one owner.** Held. `COMMANDS`, the token block,
  motion constants, and now the ids-only span (`watch.IDS_ONLY_SPAN`,
  `file-formats.md:770+`) — one definition, one holder, every reader imports
  the core rather than restating it.
- **A CSS class is a style hook or an element address, never both** (spike
  `#115`). Held, and now the reconciler's keyed matching is what makes
  identity attributes load-bearing (below).
- **The styleguide stays single-source.** Held; `just audit-styleguide`
  measures it.
- **Ports have owners, and a test proves the server is its own.** Held, and
  the table is unchanged. **The lesson it predicted came true the day it was
  written** — a hub guard graded a stranger's watch instance, green
  (`#505`-era finding): every guard verifies the server is its own before
  asserting.
- **NEW — invariant: disjointness is void on a stray write; only the guards
  + the `#535` check cover it, and they are partial.** (See containment
  gaps.)
- **NEW — invariant: parallel lanes destroy guard verification.** Verify on
  a quiet machine; record the load beside a motion verdict
  (`dogfood-orchestration.md:253–300`). A verdict taken under load is not a
  verdict.

## What must not break (unchanged, and confirmed)

- **Stdlib only, no build step.** ~~Held~~ — **SUPERSEDED 2026-07-30** by his
  ruling on `#505` Q2: *"we don't have a no-build single-file constraint. We
  had a python stdlib constraint, but otherwise building the webui bundle and
  breaking up watch.py into modules are good and reasonable things."* The
  Python-stdlib half stands; the no-build/single-file half does not. What was
  true when this was written (no bundler existed) is now a fact about the
  tree, not a constraint on it.
- **`python3 watch.py --target . --dev` still works** from a checkout. Held.
- **Deployment.** ~~`just deploy` still snapshots `git show HEAD:watch.py` to
  a single file.~~ **No longer true as of `#480`/`#425`:** deploy ships the
  **transitive closure** of the snapshot's repo-local imports plus everything
  `DATA_SIBLINGS` declares, creating subdirectories and writing each file
  atomically (`dev/deploy_state.py`, `ship_siblings`/`sibling_closure`). The
  deployed thing is already a small directory, not one file. The seam that
  arrived first (the `#505` reconciler, `vendor/morphdom.min.js`) rode
  `DATA_SIBLINGS`, and any later client assets can ride it the same way — so
  a multi-file client layout no longer costs a deploy rewrite.
- **The generation reload.** `/mtime` still bumps. Held.

## The seams question — did "as batches demand them" happen?

The original predicted the split would come incrementally, seam by seam, as a
real batch needed each one. **The prediction was right; the specific seams
differed from the candidate list:**

- **The `#505` reconciler is the seam that landed.** A vendored morphdom was
  extracted as a keyed-reconciliation diff over `#view`
  (`watch.py:7178` keyed reconciliation, `:7223` `morphdom(viewEl, …)`,
  `:11074` vendored source) — generalising the keyed diff the chrome already
  used, subsuming the ~11 hand-maintained snapshot/restore pairs. **It did
  not split the file**; it split a *responsibility* out into a vendored
  dependency. This is the existence proof that a demand-driven seam can be
  taken without breaking the single-file deploy.
- **`bin/ud-dw-chat` imports `watch` rather than re-implementing.** The
  reply path goes through `watch.apply_chat_turn` — *"Import it; never
  re-implement it"* (`bin/ud-dw-chat:6`). The original's "shared vocabularies
  get one owner" is now also "the writer is one module, imported not copied"
  — a second instance of routing around the monolith by reuse, not by split.
- **The `#112` components module** (the original's seam 1) **did not land as
  a *Python* module split — but the client half has since been extracted.**
  ~~The components vocabulary stayed inlined.~~ **Corrected 2026-07-31
  (`#633`):** `#397` moved the eight UI constants into real files under
  `client/`, so the components vocabulary is `client/components.js` (1,085
  lines) today, not a Python string constant. What has *not* happened is the
  seam this section is about: `watch.py` is still one Python module and still
  admits one writer, so the contention this bullet measures is unrelieved.
  The point stands for that half — *no batch has yet demanded the Python
  split*: the fleet has run for days with one `watch.py` writer at a time,
  and the throughput loss was absorbed by routing everything else READ-ONLY.
  **Forward-looking:** the client side is now going further still — he ruled
  2026-07-31 17:03 that the UI is transitioning to a component-based **React**
  web UI (`#591`, receipt `dc9200a0-4ebf-5d3b-afab-71257155bef9`), staged and
  component-level, with `#630` prioritising the replacement of `watch.py`'s
  inline HTML by those components. That transition is **derived**, not a
  rewrite beside the original — the wrappers compile from the same
  `client/*.js` the server serves — so it does not create the second
  maintained truth this doc's ownership rules exist to prevent.

So the answer to "did the seams appear?" is **yes, but as extracted
responsibilities and imported writers, not as a file split.** The monolith
has not come apart; it has gained seams at its edges.

## Re-scoped remainder — a recommendation to the human

The original remainder asked: *do NOT do one big split; take seams as
demand demands them.* That is still right, and it is now the lived answer:
the fleet runs, the seams are taken at the edges, and `watch.py` has not
come apart.

The open question for **him** is whether "break up watch.py" is still the
right goal, or whether the ownership grammar has made the split unnecessary
except for specific seams. The recommendation:

- **Keep `#124` open, but re-scope it from "break up the file" to "take the
  next demand-driven seam."** The ownership grammar (disjoint files + `--only`
  + the merge-gate + the containment guards) already delivers the parallelism
  the original was after, *up to* the one-file-one-writer ceiling. That
  ceiling bites exactly when two live batches both need `watch.py`, which is
  real but not constant.
- **The single seam worth taking next is the one that opens a second writer
  on the most-contended region.** Today the contended region is the
  rendering/data path (the `#505` reconciler already lives there, and the
  ~11 snapshot/restore families cluster around `setContent`/`buildCurrent`).
  Extracting that into an imported module — the way `bin/ud-dw-chat` imports
  the chat writer — would let a second lane stand on the data path while the
  server-core / routing region keeps its own holder. That is the `#112`
  components seam, just re-justified by measured contention rather than by
  tidiness.
- **Do not** attempt the full five-seam split the original listed. A
  15,000-line file rewritten in one increment is exactly the change this
  loop's philosophy exists to prevent, and the deploy/migration constraints
  (`#425`: a split must keep the old path working for processes already
  started; `watch.py` may become a symlink, not a smaller file) make a
  big-bang split actively harmful here.
- **The honest state for the parallelism goal:** the architecture *no longer
  makes parallelism impossible* — the fleet runs four. What it still makes
  *expensive* is two concurrent `watch.py` batches. That is a narrower
  problem than the original filed, and the right next act is one seam
  (rendering/data → imported module), taken when a batch demands it, not a
  project to "break up watch.py."

Net: **`#124`'s deliverable was the norms, not the split, and the norms
landed.** The split is now an on-demand seam-extraction problem with one
named candidate, not an architectural overhaul.
