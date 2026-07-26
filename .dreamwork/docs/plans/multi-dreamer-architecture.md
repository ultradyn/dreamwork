# Multi-dreamer architecture — IGC plan (#96, #124, #264)

**Tasks:** #96 (one human, several dreaming agents), #124 (parallel
norms), #262/#263 (event substrate), #264 (concurrent-safe state)
**Status:** plan for human review; no implementation authority
**Date:** 2026-07-26
**Method:** IGC matrix — candidate architectures (ideas) down the left,
goals across the top, ✔/✘/? per cell; the *All* column folds each row
(any ✘ → ✘, else any ? → ?, else ✔).

## Context

"Multi-dreamer" already names three different layers in this repo, and a
plan that does not say which one it means will be read as promising all
three:

- **L1 — several projects.** One coordinator session per project, one
  watch per project, `dreamhub` aggregating. Shipped as #96 stage 1.
- **L2 — several dreamers inside one project.** The coordinator fans out
  subagents under the disjointness invariant (`SKILL.md` Subagents,
  `parallelize`), optionally in worktrees with the plugin's claim/inbox
  protocol. Exists as protocol; its shared state is fragile — ownership
  lives in ephemeral `status.json`, which dies with the session.
- **L3 — several coordinators on one target.** Not safe today, by
  design: the ledger has one writer, or "two dreamers mint the same id,
  and the ledger loses exactly what it exists to keep" (`SKILL.md`).
  #264 is the open research question of whether this can ever be safe.

Standing decisions that constrain the option space: daemon-mode's
option 3 (server-product rewrite) is already rejected; Max chose
session-manager adapters (herdr | tmux) over a supervisor daemon, web
lifecycle controls, an eventual ssh swarm, and a metadreamer *last*
(2026-07-25 decisions in `daemon-mode.md`). The #263 user-event journal
design (SQLite receipts, leased claims + CAS for application) is
reviewed and awaiting go. Cross-host co-agents are explicitly gated on a
durable relay adapter (`DREAMWORK.md` Plugins).

## Goals

Each goal is traceable; none is invented for this plan.

- **G1 — Scales past one session.** Several dreamers at once, and
  lifecycle (spawn, steer, compact, retire) managed deliberately rather
  than improvised per client (`DREAMWORK.md`, approved #96).
- **G2 — No split brain.** Durable shared state keeps a single writer
  per stream; an id is minted exactly once (`SKILL.md` ledger rule).
- **G3 — Nothing fails quietly.** Who is dreaming, what each owns, and
  what landed is durable and legible; a wrong state is loud
  (`DREAMWORK.md` goal, folded 2026-07-25).
- **G4 — Cost discipline.** Parallelism stays opt-in; the idle loop
  stays cheap (#124: "parallelism stays opt-in, the architecture stops
  making it impossible").
- **G5 — Survives session death.** Compaction, crash, or a fresh agent
  cannot orphan a dreamer or lose track of what it owns ("a compacted
  coordinator that forgets a dreamer owns `foo.py` will edit `foo.py`").
- **G6 — Steerable from the web.** A few words, including lifecycle,
  when the session is backgrounded (#96 decisions: pause/resume/wrap
  from the hub).
- **G7 — Preserves the session model and existing invariants.** Reuses
  disjoint ownership, claims, inbox-then-wake, port ownership — no
  second protocol beside them (daemon-mode's rejection of the rewrite;
  the worktrees plugin already carries the claim idiom).
- **G8 — Small verified increments.** Each stage lands separately and is
  useful on its own (Philosophy; the #124 sequencing rec).

## Ideas

- **I1 — Harden the status quo.** Keep everything as is; write down and
  enforce the current norms, nothing new.
- **I2 — Hub-and-spoke.** One coordinator per target stays the sole
  ledger writer; N dreamers hold *durable* disjoint claims (the
  worktrees claim ledger generalised into core); user events and
  lifecycle commands ride the #263 journal; the hub gains a runtime
  adapter (herdr | tmux) for wake/steer/lifecycle.
- **I3 — Peer coordinators.** Several full coordinators on one target,
  made safe with locks/leases/CAS over `.dreamwork/`.
- **I4 — Supervisor daemon first.** A daemon owns the project registry,
  heartbeats, and session lifecycle before anything else lands
  (daemon-mode option 2 as the opening move).
- **I5 — Event-source everything.** All durable state becomes
  append-only events with materialised views; markdown demoted to
  projections everywhere, not just where reliability demands it.
- **I6 — Metadreamer first.** Dreamers spawn and manage dreamers;
  recursion is the scaling mechanism.
- **I7 — Server-product rewrite.** Loop and watch rebuilt as one
  long-lived service.

## The matrix

| Idea | All | G1 | G2 | G3 | G4 | G5 | G6 | G7 | G8 |
|---|---|---|---|---|---|---|---|---|---|
| I1 status quo, hardened | ✘ | ✘ | ✔ | ? | ✔ | ✘ | ✘ | ✔ | ✔ |
| I2 hub-and-spoke | ? | ✔ | ✔ | ✔ | ✔ | ? | ✔ | ✔ | ✔ |
| I3 peer coordinators | ✘ | ✔ | ✘ | ? | ? | ? | ✔ | ✘ | ✘ |
| I4 supervisor daemon first | ✘ | ✔ | ✔ | ? | ✔ | ✔ | ✔ | ? | ✘ |
| I5 event-source everything | ✘ | ? | ✔ | ✔ | ✔ | ✔ | ? | ✘ | ✘ |
| I6 metadreamer first | ✘ | ✔ | ✘ | ✘ | ✘ | ? | ? | ? | ✘ |
| I7 server rewrite | ✘ | ✔ | ? | ? | ? | ✔ | ✔ | ✘ | ✘ |

### Why each ✘ and ? (a bare matrix is a quiet failure)

- **I1×G1 ✘** Lifecycle stays improvised; the hub stays read-only; and
  one file still collapses fan-out to one holder — #124 measured seven
  of eight batches queueing behind `watch.py`.
- **I1×G3 ?** Ownership is legible only while the session that recorded
  it lives.
- **I1×G5 ✘** `status.json` dies with the session; only plugin users get
  durable claims. This is the architecture's named self-doubt, verbatim
  in `SKILL.md`.
- **I1×G6 ✘** No web lifecycle at all.
- **I3×G2 ✘** Replaces the single-writer invariant with lock machinery
  over markdown files never designed for concurrent writers; two
  coordinators minting ids is the exact failure the rule exists to
  prevent. #264 may eventually revise this, but today it is unproven.
- **I3×G3/G4/G5 ?** Conflict states are hard to render honestly; two
  heartbeats per target; stale-lease recovery undesigned.
- **I3×G7 ✘, I3×G8 ✘** A second protocol beside claims/inbox, and every
  durable file must convert before the *first* safe peer exists — no
  small increment is useful alone.
- **I4×G3 ?** The daemon itself becomes a new quiet-failure surface
  (its health, its restarts) before it pays anything back.
- **I4×G7 ?, I4×G8 ✘** "The full vision, much more new surface"
  (daemon-mode's own words); the 2026-07-25 decision already chose
  adapters over a supervisor, and jumping to it skips every increment
  that is buildable now.
- **I5×G1/G6 ?** Event-sourcing by itself adds no dreamers and no
  steering; it is substrate, not architecture.
- **I5×G7 ✘, I5×G8 ✘** Demotes human-readable markdown from source of
  truth to projection *everywhere*, where #263 does it only for user
  events, precisely bounded; and it is a big-bang migration.
- **I6×G2 ✘, ×G3 ✘, ×G4 ✘** Recursive fan-out multiplies writers unless
  every spawn carries the single-writer rule down with it — guardrails
  daemon-mode explicitly says do not exist yet (depth limits, budget,
  cascading no-attn/machinery rules); nobody can see the spawn tree; the
  cost is unbounded. Its own plan parks it at stage 5.
- **I7×G7 ✘, ×G8 ✘** Discards the working session model and the
  harness's tooling; already rejected in daemon-mode. The matrix simply
  confirms the standing decision.
- **I2×G5 ?** The one open cell in the winning row: durable claims fix
  the ephemerality, but *stale-claim recovery* — a dreamer whose
  coordinator died, a claim whose holder is gone — is exactly the
  undesigned part #264 lists ("stale recovery, multi-process
  same-target servers, worktrees/c2c, compaction"). The plan below
  exists to turn this ? into a ✔.

## Reading the matrix

I2 is the only row without a ✘. Everything load-bearing in it already
exists somewhere in this repo — the sole-writer ledger, the disjointness
invariant, the worktrees claim/inbox protocol, the #263 journal, the
daemon-mode adapter decision — so the architecture is less an invention
than a promotion: take the idioms that work and make them durable, core,
and visible. The rejected rows are not wasted: I5's good part is already
absorbed into I2 via #263 (event-source the streams that need it, keep
markdown for the rest), and I4/I6 are later *stages* of I2's growth, not
alternatives to it.

The other honest ? — cross-host reach — sits outside the goal columns
because it is a decided later stage (#96 stage 3), not a criterion for
choosing the shape. I2 does not foreclose it; the worktrees plugin
already names its gate (a durable relay adapter).

## The plan

Answering per layer: **L1 is shipped, L2 is what we build, L3 is what we
explicitly refuse — loudly.**

- **Stage 0 — substrate (already queued, unchanged).** #263 journal and
  #262 durable witness land first; multi-dreamer inherits their
  discipline (durable receipt before acknowledgement, leased claims +
  CAS for application) rather than growing a competing queue. One watch
  process per target, and a second one fails loudly (#262 names split
  receipt history as the incident).
- **Stage 1 — durable dreamer registry.** Generalise the worktrees
  plugin's claim ledger into core: dispatch writes a durable claim
  (dreamer id, task id, owned paths, worktree if any, lease stamp)
  before the dreamer starts; retire clears it; `status.json.agents`
  becomes a *projection* of the claims, never the source; watch renders
  it. Init's reconcile step reads claims, so a fresh or compacted
  coordinator inherits its dreamers instead of forgetting them. Stale
  recovery gets designed here with #264 (lease expiry + coordinator
  adjudication, never silent expiry). Red-first check: kill a
  coordinator mid-dispatch, start a new session, prove it refuses the
  claimed paths and can deliberately retire the orphan. This resolves
  I2×G5.
- **Stage 2 — lifecycle from the hub.** Daemon-mode stage 2 as decided:
  runtime adapter (herdr | tmux) behind an adapter model, hub-driven
  wake/steer (send-keys + stop hooks), pause/resume/wrap from the web.
  A lifecycle command is a user event — it rides the #263 journal, so
  steering while backgrounded gets the same durability as an answer.
  The hub stays read-only about project *state*; it gains write only as
  the transport for events, mirroring watch's five-exceptions shape.
- **Stage 3 — one coordinator per target, enforced.** Answer #264 with
  this matrix's verdict: single-writer-plus-workers wins; peers lose on
  G2/G7/G8. Then enforce it: a coordinator lease marker in
  `.dreamwork/`, checked at init, so a second coordinator on the same
  target fails loudly at startup instead of corrupting the ledger
  quietly. Refusing L3 is a feature, and it must be a loud one.
- **Stage 4 — reach, then recursion.** The durable relay adapter
  unlocks cross-host co-agents (the plugin's stated gate), then ssh
  spawn/attach per daemon-mode stage 3. Metadreamer comes last and only
  with its guardrails designed: depth limits, budget, and every spawn
  carrying the claim discipline and the single-writer rule down with
  it.

## What must not break

Port ownership and prove-the-server-is-yours readiness
(`parallel-architecture.md` — the repo has already paid for this once);
disjoint staging (`git add` by explicit path while anyone holds the
tree); prefer-fresh dreamers with the ~4-minute reuse window, and the
coordinator, not the incumbent, making that call; `parallelize` stays
opt-in — nothing here makes fan-out a default (G4 is a goal, not a
casualty); and the #124 seams remain the enabler — more dreamers only
help if they have somewhere disjoint to stand.

## Open questions for the human

1. **Where do durable claims live?** Rec: gitignored under
   `.dreamwork/` (they describe machine-local runtime, like
   `status.json`, but must outlive the session) — either a `claims/`
   spool or a table in the #263 journal database. Decide with #264;
   committing them would lie the moment a process died.
2. **Core or plugin?** Stage 1 promotes the worktrees claim idiom into
   `SKILL.md` proper. Rec: core, with the plugin keeping only the
   worktree-specific lifecycle — two claim protocols would be the
   second-idiom mistake `transitions.md` exists to prevent, in state
   instead of motion.
3. **Sequencing vs #263.** Everything above stage 1 assumes the journal
   ships; #263 still awaits implementation authority. If it stalls,
   stage 1 (claims) is still buildable on plain files — flag if that
   fallback should be planned in detail.
