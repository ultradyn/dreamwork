# Multi-dreamer architecture (#96 lineage, IGC-evaluated)

Human-asked 2026-07-26: *"plan a multi-dreamer architecture"*, with the
IGC skill named as the method. This is the plan; nothing here is
authorized to build. The decision artifact paired with it is
`.dreamwork/review/multi-dreamer-architecture.html`, and the ask sits in
`.dreamwork/questions.md`.

It serves the DREAMWORK.md goal recorded on 2026-07-25 (#96):

> **One human, several dreaming agents** — the workflow scales past one
> session — a hub aggregates them, and managing an agent's lifecycle
> (spawning, steering, compacting, retiring) becomes something the system
> does deliberately rather than something the human improvises per client.

Lineage, none of which this doc repeats: `daemon-mode.md` (the option
space and his five recorded decisions), `dreamhub-stage1.md` (what
shipped), `parallel-architecture.md` (the norms that make parallel work
cheap, and the port table), `user-event-journal.md` (#263, the receipt
spine), and the `ud-dreamwork-worktrees` plugin (subagent and co-agent
isolation, and the claim ledger this plan promotes).

## Method — how to read the matrices

An **IGC triple** is idea × goal × context: an idea is never good or bad
on its own, only in relation to a stated goal, inside a stated context.
Each matrix below puts goals across the top and ideas down the left. A
cell is:

| Mark | Means | What it obliges |
|---|---|---|
| ✔ | the idea satisfies that goal in this context | nothing |
| ✘ | it fails that goal — a refutation | change the idea, or drop/narrow the goal, and say which |
| ? | not yet known | an investigation; the idea cannot be adopted while it stands |

The **All** column is the whole point: ✘ if the row holds any ✘,
otherwise ? if it holds any ?, otherwise ✔. Ideas are **not scored and
not weighed** — a row with one ✘ is refuted no matter how many ✔s sit
beside it. If several rows come out all-✔ you need another goal to tell
them apart, not a tie-break by taste. If none do, the honest output is a
new idea, not the least-bad old one.

Two consequences worth stating because they are what makes this method
worth the table:

- **A ? is a task with a name.** Every ? below is followed by the
  cheapest experiment that turns it into ✔ or ✘, which is the same
  discipline the `explore` command already asks for.
- **Repairing an idea is a legal move, and it must be visible.** Where a
  refuted idea is repaired, the repaired version gets its own row and its
  own letter (I6 → I6′) rather than an amended cell — otherwise the
  record shows a plan that was always right.

## Context (shared by every matrix)

Stated once, because a cell that changes when the context changes is a
cell that must be re-read rather than trusted:

- One human. Agents are **harness-hosted sessions**: nothing in this repo
  can create an agent process by itself, so "spawn" means either the
  harness's own subagent tool or a session manager (herdr, tmux) starting
  a CLI.
- `watch.py` and `dreamhub.py` are **stdlib-only, single-file, no build
  step, offline-clean**, loopback by default; `just deploy` snapshots a
  single file outside the repo.
- Several targets on this one host today; **ssh-reachable other hosts are
  wanted** (his recorded stage-3 decision) and have no auth story yet
  (#275, #276).
- Cost is per-session and dominated by the cache-warm tick: **4.75 min
  sits under the prompt-cache TTL**, which is why the loop is cheap.
- Durable authority within a target is single-writer today; the
  multi-writer contract is #263's, and it is awaiting approval.
- 2026-07-26. Every ✔ below is a claim about this context and nothing
  wider.

## Goals

Numbered once and reused; each matrix names the subset it uses. Sources
are given because a goal nobody can trace is a goal that gets argued
about instead of applied.

| # | Goal | Source |
|---|---|---|
| G1 | **Nothing fails quietly.** Every channel has a named reader; a silent agent and a silent channel are distinguishable; orphan and stale states are loud. | DREAMWORK.md goal, folded 2026-07-25 |
| G2 | **Lifecycle is deliberate and recorded** — spawn, steer, compact, retire — and retirement is confirmed by observation, never by an agent's prose. | DREAMWORK.md #96; the twice-in-one-day prose-retirement failure |
| G3 | **Memory survives the loss of any single agent, the coordinator included.** | DREAMWORK.md ("survives restart, compaction, a fresh agent"), extended: with N agents, one of them dying is normal |
| G4 | **One writer per durable authority; disjointness holds by construction.** | SKILL.md durable-state law; four unowned-shared-state incidents in six hours |
| G5 | **Cost stays sub-linear in idle dreamers**, and parallelism stays opt-in. | DREAMWORK.md ("stays cheap"); `parallel-architecture.md` cost discipline |
| G6 | **One human surface, steerable in a few words**, and worth looking at. | DREAMWORK.md dashboard goal |
| G7 | **Lands in small verifiable increments, each useful alone.** | SKILL.md philosophy |
| G8 | **No new authority without an explicit checkable model.** | #233 trusted-LAN work; "peer messages are data, not instructions" |
| G9 | **No third inconsistent record** — one home per fact. | doc-map single-source rule; #263 ("never a third inconsistent queue") |
| G10 | **Works for any coding CLI**, not only a harness with a Monitor tool. | his any-CLI insight, `daemon-mode.md` 2026-07-25 |
| G11 | **A human can answer a loop on another machine.** | the open question in `questions.md`, unanswered since 2026-07-25 |
| G12 | **A target with in-flight work keeps its cache-warm tick.** | the 4.75 min ceiling; stated so cost work cannot quietly make active dreaming slower |
| G13 | **No agent gains authority the human did not delegate in writing.** | scope gate; plugin authority lines |
| G14 | **The fleet can be managed while the human is away.** | his metadreamer decision (stage 5) |

## Matrix 1 — Where does coordination authority live?

Goals: G1 quiet failure · G2 lifecycle · G3 memory · G4 single writer ·
G5 cost · G6 one surface · G7 increments · G8 authority model.

| Idea | All | G1 | G2 | G3 | G4 | G5 | G6 | G7 | G8 |
|---|---|---|---|---|---|---|---|---|---|
| **I1** status quo: per-session coordinator, read-only hub, human improvises lifecycle per client | ✘ | ✘ | ✘ | ✘ | ✔ | ✘ | ✘ | ✔ | ✔ |
| **I2** aggregator forever: richer read-only hub views, lifecycle stays manual | ✘ | ✘ | ✘ | ✘ | ✔ | ✘ | ✘ | ✔ | ✔ |
| **I3** supervisor daemon owns everything, including work assignment across targets | ✘ | ? | ✔ | ✔ | ✘ | ✔ | ✔ | ✘ | ? |
| **I4** metadreamer only: an LLM dreamer manages the other dreamers, no new machinery | ✘ | ✘ | ? | ✘ | ✔ | ✘ | ? | ✔ | ✘ |
| **I5** server-product rewrite: loop and dashboard as one long-lived service | ✘ | ✔ | ✔ | ✔ | ✔ | ? | ✔ | ✘ | ✘ |
| **I6** three tiers: dreamer owns work, host supervisor owns processes, hub is the human's surface | ? | ✔ | ✔ | ✔ | ✔ | ? | ✔ | ✔ | ✔ |

Why the load-bearing cells read as they do:

- **I1 G1 ✘, G2 ✘.** Not a prediction. Four orphaned `watch.py` servers
  were found in the guard ranges on 2026-07-25, one up 4.5 hours (#203);
  two dreamers announced retirement in prose and stayed alive; three
  consecutive agents believed they had cleaned up. The current design has
  no place to look that would have said otherwise.
- **I1/I2 G3 ✘.** `status.json`'s `agents[]` is session-ephemeral by
  design, and SKILL.md defends that: it describes a running process, so
  committing it "would be a lie the moment it landed." That defence holds
  for one session and breaks for N: **a dreamer outlives the coordinator
  that spawned it**, so the record of who is out must outlive the
  coordinator too. This is the finding that most changes the shape of the
  answer, and it is Matrix 2.
- **I1/I2 G5 ✘.** Five dreaming targets means five always-on cache-warm
  timers. #205 already measured the single-target case: ~40 ticks in a
  day, most arriving mid-increment or mid-stream where the right action
  was nothing. Scaling that is a standing bill for ticks nobody wanted.
- **I2 G1 ✘ specifically.** A richer read-only hub can only show what a
  live coordinator chose to write. A dead coordinator's dreamers are
  invisible to it, and invisible is the failure mode being fixed.
- **I3 G4 ✘.** A daemon that assigns work is a second thing deciding what
  a target does next, over one queue whose whole value is that ids and
  ordering are stable. That is the "never a third inconsistent queue"
  refutation with a different subject, and it also duplicates SKILL.md's
  selection algorithm in code, where it will drift from the prose.
- **I3 G7 ✘.** Nothing useful lands until the daemon exists.
- **I4 G1 ✘.** An agent watching agents shares their failure mode: it can
  go quiet, and nothing notices. G5 ✘ too — a metadreamer is another
  always-on session that also spawns. This does not refute a metadreamer;
  it refutes the metadreamer *as the mechanism*. See Matrix 6.
- **I5 G7 ✘** decisively, and `daemon-mode.md` already recorded why:
  it discards the working session model and the harness's tooling.
- **I6 G5 ?** — the only open cell on the recommendation. Three tiers do
  not by themselves make N dreamers cheaper than N timers. Resolved in
  Matrix 5.

### The repair — I6′

Matrix 5 finds that **retire-when-idle** (M3) satisfies G5 with no
measurement and no new machinery: cost is sub-linear in idle dreamers if
idle dreamers do not exist. I6 plus M3 is a different idea and gets its
own row.

| Idea | All | G1 | G2 | G3 | G4 | G5 | G6 | G7 | G8 |
|---|---|---|---|---|---|---|---|---|---|
| **I6′** three tiers **+ retire-when-idle policy**, with event-driven scheduling (#205) as a later measured optimisation | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |

I6′ is the recommendation. Note what this method just bought: the
recommendation is adoptable *now* because its one open question turned
out to have an all-✔ fallback that needs no experiment, and the
experiment (#205's scheduler) becomes an optimisation with a known
safe alternative rather than a dependency the plan is betting on.

## Matrix 2 — What is a dreamer's durable record?

Goals: G1 · G3 · G4 · G7 · G9 no third record.

| Idea | All | G1 | G3 | G4 | G7 | G9 |
|---|---|---|---|---|---|---|
| **J1** `status.json` `agents[]` only (today) | ✘ | ✘ | ✘ | ✔ | ✔ | ✔ |
| **J2** git-committed agent records under `.dreamwork/agents/` | ✘ | ✔ | ✔ | ✔ | ✔ | ✘ |
| **J3** new machine-local roster beside the plugin's `claims.json` | ✘ | ✔ | ✔ | ✔ | ✔ | ✘ |
| **J4** promote the worktrees plugin's claim ledger to a **core roster**; the plugin extends the same records; `status.json` becomes its projection | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| **J5** rows in the #263 SQLite journal | ✘ | ✔ | ✔ | ? | ✘ | ✔ |

- **J2 G9 ✘.** Committing a running process's state is the thing SKILL.md
  already refuses for `status.json` and `watch-events.log`, and for the
  right reason.
- **J3 G9** entered this matrix as a ? and was resolved to ✘ by looking
  rather than by arguing, so it is written as ✘: two files describing
  which agents hold which paths is exactly how a claim and a roster come
  to disagree, and the disagreement gets discovered by an agent trusting
  the wrong one.
- **J4** invents nothing, which is its main argument.
  `~/.config/dreamwork/worktrees/<stable-target-slug>/claims.json`
  already has the properties a roster needs and they were already
  reviewed: coordinator-only writes, a monotonic `revision` for CAS,
  states (`offered → claimed → working ⇄ blocked → ready → released`,
  plus `stale`), `paths` that must be disjoint while active, `last_seen`
  heartbeats, and a deterministic `stable-target-slug`
  (`{basename}-{sha256(abs)[:12]}`, in the plugin's
  `references/file-formats.md`) rather than a basename that collides.
  Core takes ownership of the base record; the plugin keeps `worktree`
  and `branch` as its own fields on it. `status.json`'s `agents[]` stays
  exactly as it is — the hub and the dashboard already read it — but is
  documented as a **projection** rather than the record.
- **J5 G7 ✘** for now: #263 is awaiting approval, so nothing can land
  behind it. Worth revisiting once it exists, since the roster's CAS and
  lease needs are the journal's own; recorded here so the later question
  is a re-evaluation and not a rediscovery.

**The rule this settles:** a lifecycle fact that outlives a session is
written to the roster; a lifecycle fact that describes this session is
projected into `status.json`. If you cannot say which a new field is, it
is the first one.

## Matrix 3 — Wake and steer: what carries an instruction?

Goals: G1 · G2 · G6 · G8 · G10 any CLI.

| Idea | All | G1 | G2 | G6 | G8 | G10 |
|---|---|---|---|---|---|---|
| **K1** harness message only | ✘ | ✘ | ✘ | ✔ | ✔ | ✘ |
| **K2** file inbox + harness message (today: `relay.py`, then wake) | ✘ | ✔ | ? | ✔ | ✔ | ✘ |
| **K3** runtime adapter send-keys only (herdr/tmux) | ✘ | ✘ | ✘ | ✔ | ? | ✔ |
| **K4** durable **intent** record + adapter wake + **observed** confirmation | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| **K5** c2c DM | ✘ | ✘ | ✘ | ✔ | ✘ | ? |

- **K1 G1 ✘.** A channel nobody reads back. Utility subagents reporting
  by final message silently swallowed two of three deliverables (#144).
- **K2 G2 ?** and it is the interesting one, because K2 is what the loop
  does today and `relay.py` exists precisely to make it safe. Its gap is
  narrow and documented in its own docstring: the inbox is durable but
  **not delivered** — an idle agent never reads it — so delivery is
  procedural (write, then wake) and *nothing records whether the wake
  landed*. A batch written two minutes after a dreamer went quiet sat
  unread indefinitely. G10 ✘ because the wake half needs a harness with a
  message tool, which a plain CLI session does not have.
- **K3 G1 ✘.** Keystrokes into a TUI have no receipt. Delivery without
  durability is the mirror of K2's fault, and the pair of them is the
  reason to stop treating the two halves as separate practices.
- **K4** is K2's durability plus K3's reach plus the one thing neither
  has: the intent is a record with a state, and its confirmation is an
  **observation** — the process moved, the roster changed, the commit
  landed — not an agent's claim. It reuses #263's ternary proof shape
  (`Applied | NotApplied | Unknown`) rather than inventing a second one,
  and `Unknown` is a real outcome: a wake that may or may not have
  arrived is quarantined and surfaced, never assumed either way.
- **K5 G1 ✘, G8 ✘.** `co-agent-mode.md` already says it: a DM is wake
  only, not a receipt, and same-repo c2c is convenience and not operator
  authority.

## Matrix 4 — Cross-host: how does an answer reach a loop on another machine?

This matrix answers a question that has been open in `questions.md` since
2026-07-25. Goals: G1 · G3 · G4 · G7 · G8 · G11 cross-host answer.

| Idea | All | G1 | G3 | G4 | G7 | G8 | G11 |
|---|---|---|---|---|---|---|---|
| **L1** don't — same-host only | ✘ | ✔ | ✔ | ✔ | ✔ | ✔ | ✘ |
| **L2** ssh in and append the remote target's `questions.md` | ✘ | ✘ | ✔ | ✘ | ✔ | ✘ | ✔ |
| **L3** shared filesystem for `.dreamwork/` (NFS, syncthing) | ✘ | ✘ | ✔ | ✘ | ✔ | ? | ✔ |
| **L4** remote **intent** to that target's own writer, over an ssh forward to its receive endpoint | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| **L5** hub-to-hub federation over authenticated HTTP | ✘ | ✔ | ✔ | ✔ | ✘ | ? | ✔ |

- **L2 G4 ✘.** Two writers to one authority. The loop's own words when it
  filed the question: *a wrong write corrupts another loop's record.* G1
  ✘ as well, because a foreign write is invisible to that coordinator's
  own assumptions about who last touched the file, and G8 ✘ because ssh
  access to a filesystem is not an authority model for a domain record.
- **L3 G4 ✘.** Concurrent unsynchronised writers are outside #263's
  supported mutation contract by construction, and sync tools resolve
  conflicts by last-write-wins, which is the one resolution a durable
  record must never accept.
- **L4** keeps the law intact: **the target's own coordinator remains the
  only writer of its files.** A remote human, a remote hub, or a
  metadreamer sends an intent to that target's receive endpoint; the
  local writer applies it and issues the receipt. An ssh forward is not a
  new bind, so the loopback-only property survives (G8 ✔) and the shape
  is the one `daemon-mode.md` already recorded for stage 3.
- **L5 G7 ✘** today: it is large and it is blocked on auth (#275, #276).
  It becomes the right answer once auth exists, and it does not conflict
  with L4 — L4 is the transport L5 would eventually authenticate.

**Recommended fold, if this direction is accepted:** the open question
gets answered with L4 and the general rule — *never write another
target's files; send an intent to its writer* — lands in SKILL.md's
durable-state section, where the trigger lives.

## Matrix 5 — Cost: what wakes N dreamers?

Goals: G1 · G5 cost · G7 · G12 cache-warm for active work.

| Idea | All | G1 | G5 | G7 | G12 |
|---|---|---|---|---|---|
| **M1** N per-session heartbeats (today, scaled up) | ✘ | ✔ | ✘ | ✔ | ✔ |
| **M2** one host scheduler: event-driven wake, quiet backoff (#205), cache-warm interval only for targets with in-flight work | ? | ✔ | ? | ✔ | ? |
| **M3** retire-when-idle: no dreamer, therefore no timer, for a target with nothing in flight | ✔ | ✔ | ✔ | ✔ | ✔ |
| **M4** M2 and M3 together | ? | ✔ | ? | ✔ | ? |

- **M1 G5 ✘** by arithmetic: the tick interval is chosen to sit under the
  prompt-cache TTL, so an idle target's timer is a bill for keeping a
  cache warm that nothing is reading.
- **M2 G5 ? and G12 ?** — both unmeasured. Event-driven waking might
  reduce total ticks a lot or might merely move them, and the risk to G12
  is real in the other direction: a scheduler that decides a target is
  quiet while it is mid-increment makes active dreaming *slower*. The
  experiment is small and #205 already names its inputs
  (`heartbeat-into-monitor.md`, `run_watch()` in `ez-feedback-pipeline`):
  run one host for a fixed window with the scheduler behind a flag, count
  ticks and measure the cost against the same window on timers, and
  assert that a target with in-flight work never waited longer than
  4.75 min. Until that runs, M2 is not adoptable.
- **M3 G5 ✔.** It is a policy, not machinery, and the loop already
  believes it: *"Retire idle dreamers rather than leaving them parked"*
  (DREAMWORK.md), *"dreamers are batches, not careers"* (SKILL.md). What
  is missing is that nothing enforces it and no record shows it happened
  — which is Matrix 2's roster and Matrix 3's observed retirement, both
  of which this plan builds first anyway. G12 ✔ because it retires only
  targets with nothing in flight; an active target is untouched.
- The cost of M3 is the human's first steer to a retired target paying a
  cold start. That is his latency once, not a standing bill, and it is the
  trade `daemon-mode.md` was already willing to make.

## Matrix 6 — The metadreamer

Goals: G2 · G4 · G5 · G8 · G13 written delegation · G14 fleet managed
while away.

| Idea | All | G2 | G4 | G5 | G8 | G13 | G14 |
|---|---|---|---|---|---|---|---|
| **N1** no metadreamer; the human is the only fleet manager | ✘ | ✔ | ✔ | ✔ | ✔ | ✔ | ✘ |
| **N2** metadreamer with its own lifecycle path (direct spawn and kill) | ✘ | ✔ | ✘ | ✘ | ✘ | ✘ | ✔ |
| **N3** metadreamer as a **client of the same lifecycle API the human uses**: depth ≤ 1, budget lease, delegation written in DREAMWORK.md | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |

- **N2 G8 ✘.** A private path is authority without a model. G4 ✘ because
  it is a second lifecycle writer, and G5 ✘ because recursive spawn with
  no depth or budget bound is unbounded by construction.
- **N3** costs nothing architecturally, which is the interesting part: it
  is the same intents, the same roster, the same observed confirmations.
  Its bounds are three lines of policy — spawn depth ≤ 1 (a metadreamer
  may spawn dreamers; those may not spawn dreamers), a budget lease it
  cannot renew for itself, and a DREAMWORK.md delegation line naming what
  it may do, in the shape plugin authority lines already use.

**The design rule this yields, and it constrains every stage below:**
**build no lifecycle path that only the human can use, and none that only
an agent can use.** The metadreamer must reuse the human's path, and the
human must be able to do by hand anything the system does for him. A
private path for either is how N2's failure arrives later wearing N3's
name.

## What this plan deliberately does not decide

Single-source rule: these have homes, and a second description would be a
second thing to keep current.

- **Multi-writer file safety within a target** — `DomainFileStore`,
  atomic replace, embedded generation and digest lineage, ternary proof:
  `user-event-journal.md` (#263), awaiting approval. This plan *depends*
  on it for durable intents and *reuses* its proof vocabulary; it does not
  restate the contract, and #264's research question is largely answered
  by it plus Matrix 2's single-writer roster.
- **Topic chats, worker promotion, per-chat caps** — #229/#270 v2,
  awaiting approval. Its `WorkerAdapter` and this plan's supervisor are
  the same seam seen from two surfaces; whichever is approved first
  should name the other.
- **Auth for any non-loopback exposure** — #275 (public) and #276 (LAN
  bearer token). Nothing in stages A–D needs it; stage E is blocked on it.
- **Which session manager wins** — herdr is his recorded preference with
  tmux as fallback, *behind an adapter*, and #201 holds the reading list
  (`~/.llm-general/ai-coding/herdr/`, verified against 0.7.4 protocol 16).
  The adapter interface is stage C; the choice is a stage-C measurement.

## The architecture, in one page

Three tiers, and one sentence that separates them: **the supervisor moves
processes, the dreamer moves work, the hub is where the human stands.**

| Tier | Owns | Durable state | Never does |
|---|---|---|---|
| **Dreamer** (per target, unchanged) | selection, increments, that target's files | the target's `.dreamwork/`, committed | touch another target; decide its own retirement |
| **Host supervisor** (new, small) | process lifecycle and wake scheduling for this host's dreamers | the roster (Matrix 2), machine-local | decide what work a dreamer does |
| **Hub** (exists, read-only today) | the human's one surface; issues intents | its own `~/.config/dreamwork/hub/` only | write into any target's tree |

The laws, each traceable to a matrix above:

1. **One writer per target.** Everything else sends intents (L4).
2. **A lifecycle fact that outlives a session lives in the roster;**
   `status.json` is a projection (J4).
3. **Durability and delivery are separate, and both are recorded.** An
   intent is durable; a wake is delivered; a confirmation is *observed*
   (K4).
4. **Retirement is observed, never claimed.** The harness said it
   terminated, the process is gone, the port is released — or the state is
   `Unknown` and loud (K4, G2).
5. **Caps are leases in the roster, not counters in a process.** Two
   watch processes on one target cannot each believe they hold half the
   cap — the finding from #229's review.
6. **Ports are OS-assigned and servers prove their identity.** Where
   shared mutable state can be removed instead of owned, remove it
   (#203's class, `parallel-architecture.md`'s prediction).
7. **No private lifecycle path**, for the human or for an agent (N3).

## Staging

Each stage is useful alone and adds no authority it does not need. Sizes
are the loop's 15–20 minute increments.

**Stage A — make the fleet legible; no new authority.**

- A1 Roster: promote the claim ledger to the core record (J4). Shape in
  `file-formats.md`, check in `lint.py`, `migrations/` entry, plugin
  fields folded onto the same records, `status.json` documented as a
  projection. *2–3 increments.*
- A2 `ud-dw-agents list | show | orphans` — a bounded CLI projection,
  because an LLM reads projections and not raw stores (#263's rule).
- A3 Orphan reconciliation: roster against observed processes and ports,
  using #203's discrimination rule (target path **and** elapsed time
  together are the evidence). Unknown is a rendered state.
- A4 Hub renders the roster per project, still read-only. One glance says
  which dreamers are out, which are stale, and which are orphans.

**Stage B — lifecycle as intents, still executed by hand.**

- B1 Intent record and `ud-dw-agents intend <spawn|wake|compact|retire>`;
  the coordinator executes; every intent carries an observed confirmation
  or `Unknown`.
- B2 Observed retirement (law 4), red-proved against the exact failure:
  an agent that acknowledges shutdown in prose and stays alive must make
  the check fail.
- B3 Compaction as an intent: the managed sender (#127) plus the
  PreCompact plugin (#138/#156, already approved as an optional
  off-by-default plugin) writing the preservation record.
- B4 Retire-when-idle policy (M3) becomes enforceable because B1 and B2
  exist. **This is the stage that closes I6's open cell.**

**Stage C — runtime adapter and the supervisor.**

- C1 Adapter interface plus capability profile, read-only first: list
  sessions, classify status. herdr and tmux behind one shape; the harness
  is a third implementation, not a special case (G10).
- C2 Spawn and wake through the adapter; OS-assigned ports; identity
  proof before any client acts on a server.
- C3 The scheduler experiment (M2): behind a flag, measured against
  timers, with the G12 assertion as a hard gate. If it fails, M3 already
  carries G5 and nothing downstream changes.

**Stage D — the hub becomes a control plane.**

- D1 POST surface with `watch.py`'s authority model exactly — exact Host
  allowlist, matching Origin before body read, loopback default. Intents
  only; the existing `writes nothing outside its own home` test extends
  to cover it.
- D2 pause / resume / wrap / compact / retire from the page; project add
  and remove stay CLI (his recorded decision).
- D3 Every new UI state obeys `transitions.md` — arrival and departure,
  not appearance and disappearance — checked by intermediate-value
  assertions, because an end-state assertion cannot fail on a motion bug.

**Stage E — cross-host.** L4 as the transport, host-qualified identity,
blocked on auth for anything wider than an ssh forward.

**Stage F — metadreamer.** N3: the fleet as a target with its own
DREAMWORK.md, depth ≤ 1, a budget lease, the human's own API.

## Verification

Per the repo's law, **a new check is not verification until it has been
red**. Each of these names the bug it must fail on:

| Check | Made red by |
|---|---|
| Roster shape and disjointness | a roster with two active agents holding the same path must fail `lint.py` |
| Orphan detection | kill a dreamer's process and assert the row becomes orphan, not stale-but-fine |
| Observed retirement | an agent that prints "retiring" and stays alive must fail B2 |
| Cap leases | two watch processes on one target must not each admit half the global cap |
| Intent confirmation | crash between the wake and the confirmation must yield `Unknown`, never a silent success |
| Hub writes nothing | an intent POST must not modify any target file (extend the existing hub test) |
| Host / Origin gate | a wrong Origin must be refused **before** the body is read |
| Port identity | a stranger's server answering on the expected port must be rejected, not graded |
| Scheduler (C3) | a target with in-flight work waiting longer than 4.75 min must fail the gate |
| Transitions (D) | assert intermediate values; re-run with the bug to see it red |

One warning from this repo's own record, worth repeating where the checks
are being planned rather than discovered: guard runs took 15–25 minutes
under several dreamers and ~40 chromium processes, and a fixture seeded by
one guard has already made a neighbour's check vacuous without making it
red. Multi-dreamer work makes the verification suite itself a
concurrency problem, and #148's shared runner plus #203's port class are
the two items that stop it being one.

## Dependencies and gates

| Needs | For | State |
|---|---|---|
| #263 user-event journal | durable intents, ternary proof, receipts | awaiting human approval |
| #205 heartbeat into monitor | stage C3's scheduler | idea, plan sketched |
| #201 herdr / adapter | stage C | idea; substrate exists and is documented |
| #203 orphan and port class | stages A3, C2 | open bug |
| #148 shared guard runner | verification under load | open chore |
| #275 / #276 auth | stage E beyond an ssh forward | research / open |
| #264 concurrent-safe state | largely answered by #263 + Matrix 2 | blocked on #263 |
| worktrees plugin | roster lineage; co-agent mode | loaded 2026-07-26 |

Stages A and B need none of the unapproved items: the roster is a file,
the intents are records, and both work with the machinery that exists.
That is deliberate — it is what makes G7 a ✔ for I6′ rather than a ?.

## Open questions for the human

1. **Adopt I6′** — three tiers, roster as the durable record, intents with
   observed confirmation, retire-when-idle — as the direction, authorizing
   **stage A only** (a roster, a bounded CLI, orphan reconciliation, and a
   read-only hub view)? Stages B–F would each come back with their own
   plan.
2. **Fold L4's rule** — *never write another target's files; send an
   intent to its writer* — as the answer to the cross-host question open
   since 2026-07-25, and record it in SKILL.md?
3. **M2 or M3 first?** Rec: M3, because it needs no measurement and stage
   B builds its prerequisites anyway; M2 becomes a measured optimisation
   with a known-safe fallback.
4. **Metadreamer delegation** — is *"build no lifecycle path that only the
   human can use"* accepted as a standing constraint now, while stage F is
   far off? It is cheap to hold from the start and expensive to retrofit.
