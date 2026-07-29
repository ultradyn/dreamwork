# ud-dreamwork-matt-pocock-skills — bridge plugin (design spec)

> **Status:** design **settled** (lane-287spec, #287) — the five open calls
> (OQ1–OQ5, §14) were ruled by the human 2026-07-30 00:20. This document is
> the deliverable; it is not a
> plugin, not a Load line, not a setup script, and not an edit to any
> suite file. **Approval of this document authorises none of those** —
> it authorises only the design, and each extension seam it names is a
> separate grant, exactly as `ud-dreamwork-github`'s plan made its
> authority lines separate. Where this file says "the bridge would", it
> describes work that is not authorised yet.
>
> **What the human asked for:** a *generic wrapper/adapter layer* that
> unifies the installed first-party `mattpocock/skills` suite with the
> Dreamwork protocol — "we don't want to rewrite the skills" — named
> exactly `ud-dreamwork-matt-pocock-skills`. His three constraints bind
> the design (§3); his A′ notes remove polling/dual queues/handoff
> authority, scope grilling, and demand the "do not rewrite" rule be
> stated outright (§2).

**Depends on (both met as designs, one met as execution):**
- **#294 (SQLite ledger cutover)** — *executed today*. The ledger is now
  `.dreamwork/ledger.sqlite3` (machine-local); reads/writes go through
  `dev/ledger.py` verbs (`file`/`fold`/`note`/`counts`) and
  `ledger_parse.py`; `tasks.md` is a one-line shim. The bridge targets
  the **verb seam**, so the cutover is invisible to it by construction
  (§3, C1).
- **#254 (rooted exchange)** — design ratified. Grill chains reuse the
  existing `questions.md` author-tag grammar and `human_block()`; a new
  tag is a reviewed `file-formats.md` change, never a side effect (§3,
  C2; §5).
- `writing-plugins.md` — the plugin-authoring contract and the
  **bridge-plugin pattern** this design follows: *wrap, never
  wholesale-adopt; feed, never bypass; schedule through the rotation;
  run autonomously only with a recorded authority line.*

---

## 1. The one rule, and what it forbids

**The suite runs unchanged.** The bridge is an adapter between two
systems; it edits zero suite files and adds zero suite commands. Every
behaviour the suite names keeps the suite as its single source of truth,
and every behaviour Dreamwork names keeps Dreamwork as its single source
of truth. The bridge's entire job is the **translation at the seam**
where the two meet, and nothing more.

### 2. "Do not rewrite" — stated outright, not implied

A later agent will read "adapt the suite to dreamwork" and reach for the
suite's `SKILL.md` files, because editing upstream is the obvious reading
of *adapt*. It has happened in this repo's history that a prohibition
left implicit was treated as permission. So:

- **No suite file is edited, forked, shadowed, or wrapped-in-place.** The
  suite is read where it is installed (`~/.agents/skills/`,
  `~/.jcode/skills/`, or wherever the resolver finds it) and invoked as-is.
- **"What to change to make it compatible" is a WRITTEN compatibility
  note (§9), not a set of edits anyone makes.** It lists the gaps between
  the suite's assumptions and Dreamwork's contracts, names the
  bridge-local adaptation for each, and stops. The suite's authors close
  the gaps upstream if and when they choose; this repo does not.
- **The bridge never holds a copy of suite content.** It points at the
  installed suite by resolved path; a vendored duplicate is exactly the
  "second source of truth" this repo has paid for repeatedly
  (`file-formats.md`, `#331`'s one-definition rule).

The positive form of the rule: the bridge *configures the suite's
per-repo dials* (its `docs/agents/*.md` files, which the suite itself
treats as configurable input) and *translates at the call boundary*. That
is the full surface.

---

## 3. The three binding constraints

These are his conditional recs, restated as invariants the design is
checked against. A design that breaks one is wrong, not unrefined.

**C1 — tasks only through the tool/CLI seam.** The bridge touches the
task ledger **exclusively** through `dev/ledger.py` verbs
(`file`/`fold`/`note`/`counts`) and `ledger_parse.py` reads. It never
opens `.dreamwork/tasks.md`, never opens `.dreamwork/ledger.sqlite3`,
and never re-implements a parser — five hand-rolled ledger parsers have
been wrong here against an importable production one (`dev/ledger.py`
exists for this reason). The #294 cutover is invisible to the bridge
because the verb dispatches on `source_of_truth` internally: markdown
today, store after cutover, and the caller sees neither. **Proposed
core improvement, split out and not assumed (§10):** a future
`dreamwork tasks` dispatcher that the bridge shells out to unchanged —
narrowly justified only because two bridges (this one, `ud-dreamwork-
github`) now want a stable task CLI, and the verb set already exists.

**C2 — grill chains use the existing `questions.md` grammar.** A grill
session's questions become `questions.md` entries written through
`watch.human_block()` (the only correct way to write human text into
that file — `file-formats.md`), using the **closed author-tag set**:
`Note (human, via <channel>, <ts>)`, `Follow-up (loop, <ts>)`,
`Answer (via watch, <ts>)` (his, never the loop's). The bridge invents
no `Grill (loop, …)` tag — a wrong spelling deletes the bullet in
silence (`#343`), and a new tag is a reviewed `file-formats.md` +
`NOTE_TAGS` change in one commit, never a side effect of a plugin. The
chain obeys #254's rooted-exchange rule (one root, one flat branch, one
inset depth). See §5.

**C3 — no per-target state dreamhub must learn to read.** Machine-local
bridge state (the resolved suite path, any suite-issue ↔ ledger-id
mapping cache, cursors) lives under
`~/.config/dreamwork/matt-pocock/<target-slug>/` — ephemeral,
gitignored, **rebuildable from the durable truth**. The durable truth is
the `questions.md` grill chain and the ledger `#N`s; dreamhub reads
neither the bridge's cache nor any bridge-specific file. A state that
dreamhub had to learn to read would be a second source of liveness
(this repo refuses inferring liveness from surviving artefacts —
`#363`, `#381`), so the bridge introduces none.

---

## 4. Responsibilities — who owns what

Three actors, one table. The load-bearing column is *single source of
truth*: each behaviour has exactly one owner, and the bridge never
becomes a second owner of something either side already owns.

| behaviour | suite owns | Dreamwork core owns | the bridge owns |
|---|---|---|---|
| **What to work on** (the task spine) | the *workflow shape* — spec→tickets→implement→review | the **ledger** (`#N`, open/landed, single writer) | **translation only**: a suite "publish to tracker" call routes to `dev/ledger.py file`; the bridge mints no id, holds no queue |
| **Identity** | the suite's tracker-issue number (when backed by a real tracker) | the **ledger `#N`**, permanent | the mapping between them, *cached machine-local, rebuildable* — never authoritative (C3) |
| **Asking the human** | the *grilling method* (one question, recommended answer, await) | **`questions.md`** — the only channel; closed tags; `human_block()` | **scoping + durability**: one grill question → one `questions.md` entry via `human_block()`; the live cadence is the suite's, the durable record is the loop's (C2) |
| **Domain vocabulary** | **`CONTEXT.md`** + `docs/adr/` (ubiquitous language) | **`DREAMWORK.md`** (goals, philosophy, preferences) | a *pointer*: the loop consults `CONTEXT.md` for terms; the bridge copies nothing |
| **Repo config** | `setup-matt-pocock-skills` writes `docs/agents/*.md` (its configurable input) | **`DREAMWORK.md`** Load/Don't-load + authority lines | **configure the suite's dials** (`docs/agents/issue-tracker.md` → the ledger seam); never write `CLAUDE.md`/`AGENTS.md` |
| **Handoff / delivery** | the `handoff` skill (compact → temp-dir doc) | **`handoffs.md`** + `relay.py` (the delivery channel, single-writer) | **nothing** — handoff authority is explicitly *not* granted (§7) |
| **Review / research / prototype** | the *skills themselves* (two-axis review, primary-source research, throwaway prototype) | the **scope gate** + increment discipline | **expose for dispatch**: the loop may dispatch these as subagents; their output feeds tasks/questions, never bypasses (§6) |

The bridge owns exactly three things: the **call translation** at the
task seam, the **grill-to-questions scoping**, and the **suite-dial
configuration**. Everything else is a pointer, a cache, or someone
else's job.

---

## 5. Lifecycle hooks — which seams, and why

`writing-plugins.md` names five seams. The bridge uses three, declines
two, and the justification for each is the test of whether it earns its
loop context cost.

**Initialization (used).** Detect the installed suite at init (resolve
`writing-great-skills`/`grilling`/`setup-matt-pocock-skills` by name via
`plugin_resolver`'s deterministic path logic — never a broad filesystem
scan). If present and not yet configured, propose the bridge through
`questions.md` (orientation's existing bridge-suggestion path, init step
7). On a recorded yes: write the suite's `docs/agents/issue-tracker.md`
so its "tracker" *is* the ledger seam (the bridge's adapter contract,
§8), and contribute one wizard question — which spine skills to bridge,
default the workflow core (`to-spec`/`to-tickets`/`triage`/`implement`/
`code-review`/`grilling`/`domain-modeling`).

**Tasks (used — this is the bridge's main job).** The bridge *is* the
issue-tracker adapter the suite calls. `to-spec`/`to-tickets` "publish
to tracker" and `triage`'s state machine route through the bridge, which
calls `dev/ledger.py file` (never the ledger file directly — C1). Triage
state collapses to Dreamwork's grain:
- `ready-for-agent` ↔ a filed candidate in normal selection;
- `ready-for-human` / human-authored or human-triaged ↔ **passes the
  scope gate** (a human steer);
- `needs-info` ↔ a `questions.md` entry (the bridge writes it);
- `wontfix`/closed ↔ a fold with a note.
The five-state machine becomes a *projection* the bridge derives from
ledger state + the scope gate, not a second store.

**Commands (declined for v1, with the reason).** The suite skills are
user-invoked (`disable-model-invocation: true` on the spine); under
Dreamwork the human reaches them by typing their name, which already
works. Adding `...`-menu plugin commands would shadow nothing core but
would spend composer complexity for no reach the typing doesn't already
give. **If** the human wants one-tap dashboard invocation, that is a
separate grant — and it is the one seam where a command is genuinely
earned, so it is left open rather than refused.

**Tick flow (declined — removed by A′).** No poll loop, no dual queue,
no Monitor. The suite has no event source of its own once its tracker is
the local ledger; a tick check would re-derive what selection already
derives. This is the explicit A′ removal: the bridge contributes no
polling, no second inbox, no autonomous grill runner.

**Maintenance (used, lightly).** One rotation item: re-resolve the
suite's installed path and re-check `docs/agents/*.md` against drift
(the suite's own `setup` is the writer; the bridge only notices if the
dial moved). Marked with `dreamwork(maintain:matt-pocock-config)`.

---

## 6. Precedence — when both systems name the same behaviour

Each row is a real conflict the suite and the loop both claim. The
precedence is stated as a decision so an implementer chooses nothing.

**P1 — the ledger is the task spine, not the suite's tracker.** When the
suite's `to-tickets`/`triage` say "publish to the tracker", the tracker
*is* the ledger, by the bridge's `docs/agents/issue-tracker.md`
configuration (§8). There is no second task list. A suite issue number,
when the suite is backed by a real GitHub tracker (a mode the bridge
supports but defaults off, OQ1), is durable upstream and keeps its id
*as a candidate* until the loop starts it, then earns a `#N` — exactly
`writing-plugins.md`'s rule for upstream-durable identity. In the
default (local-ledger) mode there is no separate id space at all.

**P2 — `questions.md` is the only channel to the human; grilling is
scoped to it.** The suite's grilling is a live, in-chat, one-question-
at-a-time interview. Dreamwork's contract is absolute: decisions never
use the harness Ask-User-Question tool; every ask lands in
`questions.md` and the dashboard is where he rules (`DREAMWORK.md`).
Precedence: **durability wins.** A grill question becomes a
`questions.md` entry before it is asked; the conversational cadence (one
question, recommended answer, wait) is preserved on top of the durable
record, never instead of it. The loop **never answers its own grill
questions** — the suite's HITL invariant (a grilling agent that answers
its own questions has broken it) and the loop's `DREAMWORK.md`
preference ("ask him less, only where the answer is genuinely his")
agree, and the bridge enforces neither by invention: it routes the
question to the file and stops.

**P3 — `DREAMWORK.md` is the authority; `CONTEXT.md` is a referenced
glossary.** They store different things and do not collide:
`DREAMWORK.md` holds goals, philosophy, preferences, plugin decisions;
`CONTEXT.md` (the suite's `domain-modeling`) holds the project's
ubiquitous domain language. Precedence on the *one* overlap — a term
that appears in both — is: **`DREAMWORK.md` wins for how the loop
behaves; `CONTEXT.md` wins for what domain words mean.** A contradiction
between them is surfaced as a `questions.md` entry (the loop's
"contradictions get surfaced and the human resolves them" rule), not
silently reconciled.

**P4 — the scope gate governs agent-initiated surfaces; suite tools that
*produce* work are gated, suite tools that *decide with him* are HITL.**
`to-spec`/`to-tickets` *generate* tasks — agent-initiated when the loop
runs them, so **filing their output is a human steer by default**
(OQ5). `code-review`/`research`/`prototype` are tools; dispatching them
autonomously is scope expansion the gate governs, so **default
human-invoked** (OQ4). `grilling`/`domain-modeling` are HITL by their
own design and stay HITL. The gate is Dreamwork's; the bridge maps the
suite's roles onto it rather than relaxing either.

**P5 — commit-yes/push-no unless authorized; the suite's `implement`
inherits this.** The suite's `implement` commits to the current branch
by habit. Under Dreamwork it inherits the loop's authority model: the
bridge's dispatch brief restates "commit each increment; push/deploy
only with a recorded line", and the suite's own commit step is the
place it is most likely to strain it.

---

## 7. Authority model

Read-only floor, as every bridge plugin starts (`writing-plugins.md`).
What the bridge may do at the floor, and what each elevated action would
cost — each its own DREAMWORK.md line, silence meaning the floor.

**At the floor (no authority line needed):**
- read the installed suite (resolve, never scan broadly);
- configure the suite's `docs/agents/*.md` dials (the suite's own
  configurable input — this is *using* the suite, not acting on the
  world);
- file tasks through `dev/ledger.py file`, fold/note through the verbs;
- write grill questions to `questions.md` through `human_block()`;
- dispatch `research`/`code-review`/`prototype` as **read-only**
  subagents whose output feeds tasks/questions.

**Explicitly NOT granted (A′ removals, recorded so they are not
re-proposed):**
- **no handoff authority.** The suite's `handoff` skill is not adopted as
  a delivery channel; `handoffs.md` + `relay.py` remain the single
  writer's channel. The bridge neither reads nor writes handoffs.
- **no autonomous grilling.** The bridge never runs a grill session on
  its own; grilling is HITL and scoped to one `questions.md` entry.
- **no dual queue, no poll loop, no second inbox.** (P5/tick decline.)
- **no edits to suite files, `CLAUDE.md`, `AGENTS.md`, `CONTEXT.md`,
  `DREAMWORK.md`, `file-formats.md`, `lint.py`.** (Authority limits +
  do-not-rewrite.)

**Elevated actions, each a separate line he grants by name:**
- `comment` / `push` / `open-pr` / `merge` — only meaningful if the
  suite's tracker is a *real* GitHub/GitLab tracker (OQ1), since the
  default local-ledger mode has no remote to act on;
- `file-as-task` — letting the loop's own `to-spec`/`to-tickets` output
  enter the ledger without a human steer (the scope-gate override, OQ5);
- `dispatch-review` / `dispatch-prototype` — autonomous tool dispatch
  (OQ4).

Silence keeps the floor. A DREAMWORK.md line that names one grants only
that one, with its limits and the protocol for anything hard to revert
(propose via `questions.md`, never do).

---

## 8. State model + the tracker-adapter contract

**Durable (`.dreamwork/`, committable, single-source):**
- the ledger `#N`s (written only via `dev/ledger.py`, C1);
- the `questions.md` grill chain (the durable truth of every grill
  session — `human_block()`, C2; #254);
- `docs/agents/issue-tracker.md` (the suite's own configurable dial, now
  pointing at the ledger seam);
- `.dreamwork/docs/domain/` or a pointer to the repo's `CONTEXT.md` —
  the referenced glossary, never copied (P3).

**Machine-local (`~/.config/dreamwork/matt-pocock/<slug>/`, gitignored,
rebuildable — C3):**
- the resolved suite install path(s);
- a suite-issue ↔ ledger-`#N` mapping cache, *only* in real-tracker mode
  (OQ1); rebuilt from the ledger + the tracker on demand;
- any cursor/etag for a real tracker (precedent:
  `ud-dreamwork-github`'s `~/.config/dreamwork/github/<slug>/`).

**dreamhub reads none of the machine-local state.** Its readers
(`status.json`, `watch-port`, `/data.json`, `handoffs.md`) are
unchanged by this bridge. The bridge's liveness is the ledger's
liveness and the questions count — both already on the dashboard.

### The tracker-adapter contract (what `docs/agents/issue-tracker.md` says)

The suite's skills consult `docs/agents/issue-tracker.md` to learn
"where issues live and how to read/write them." The bridge writes that
file so the answer is **the Dreamwork ledger, through the verb seam**.
The adapter contract (the bridge's one real spec) is the set of
operations the suite's skills call and how each maps:

| suite operation | bridge action | Dreamwork verb |
|---|---|---|
| create issue / publish ticket | file a task | `dev/ledger.py file <title> …` |
| set state `ready-for-agent` | (default — a filed candidate) | — |
| set state `needs-info` | ask the human | `questions.md` via `human_block()` |
| set state `wontfix` / close | land with a note | `dev/ledger.py fold <id> --note …` |
| list open issues | read open ids | `dev/ledger.py counts` / `ledger_parse` |
| native blocking edges | map to `depends` (prose today; gap, §9) | — |

The adapter **shells out to the verb**; it does not link the ledger
module into the suite's process, because the verb is the stable seam and
the suite is not Dreamwork-aware. A test pins that the adapter's "create
issue" path invokes `dev/ledger.py file` and never opens a ledger file.

---

## 9. Compatibility note — "what to change to make it compatible"

This is the WRITTEN list of gaps, per §2. **Nobody edits upstream.** Each
gap names the bridge-local adaptation that closes it under Dreamwork; if
the suite's authors close it upstream later, the adaptation retires.

| # | suite assumption | Dreamwork contract | the gap | bridge-local adaptation (no upstream edit) |
|---|---|---|---|---|
| G1 | `setup-matt-pocock-skills` step 4 writes an `## Agent skills` block into `CLAUDE.md`/`AGENTS.md` | `DREAMWORK.md` is the authority; `CLAUDE.md`/`AGENTS.md` edits are outside this lane's authority | setup writes to files the bridge may not touch | the bridge runs setup's *exploration + `docs/agents/*.md` writing*, and **omits step 4's CLAUDE.md edit**; DREAMWORK.md's Load line replaces the `## Agent skills` block |
| G2 | the tracker is a real issue tracker with native blocking (`gh api`) | the ledger has `open`/`landed` + `depends` (prose, not yet a field) | blocking-edge queries won't work | v1: blocking edges map to `depends` *prose*; the adapter declines native-blocking queries with a printed reason. (A real `depends` field is #353's open work, not the bridge's.) |
| G3 | grilling asks live, in chat | asks are durable in `questions.md`; no Ask-User-Question | the live interview has no durable record | grill questions are bridged to `questions.md` *before* they are asked; cadence preserved on top (P2) |
| G4 | `domain-modeling` writes `CONTEXT.md` at the repo root | durable docs live under `.dreamwork/`; repo-root layout is the human's | two homes for the glossary | the bridge treats the repo-root `CONTEXT.md` as **external reference** the loop points at; or, his choice, a `.dreamwork/docs/domain/` mirror (OQ3) |
| G5 | `handoff` compacts to a temp-dir doc | `handoffs.md` + `relay.py` are the delivery channel | two handoff mechanisms | handoff authority is **not granted** (§7); the suite's `handoff` stays available as a human-typed tool but is not wired as a loop channel |
| G6 | no loop-authored resolution tag exists in `questions.md` (`#254` R1, pending his word) | a grill the loop *resolves* needs a tag that does not exist | the bridge cannot write a loop grill-resolution | the bridge **only poses** grill questions (HITL); it writes no loop resolution. If #254 R1 lands, the bridge adopts that tag — never an invented one |

---

## 10. Proposed core improvement — split out, not assumed

One core change is *proposed*, clearly separated from plugin-local
adaptation, and only because two bridges now want it:

**A `dreamwork tasks` dispatcher** — a thin CLI wrapping the
`dev/ledger.py` verb set (`file`/`fold`/`note`/`counts`) plus
`ledger_parse` reads, that plugins shell out to unchanged. Today the
bridge targets `dev/ledger.py` directly (C1 is met). The dispatcher is
justified only because `ud-dreamwork-github` and this bridge both want a
stable task CLI, and the verb set already exists — so it is a re-skin of
an existing seam, not new machinery. **It is not assumed:** the bridge
works against `dev/ledger.py` today and keeps working if the dispatcher
never lands. If it does, the bridge swaps one shell command. This is the
only place this spec touches core, and it is a proposal for him, not a
dependency.

No other core hooks are proposed. A′ demands speculative core hooks be
rejected; the bridge adds none to `watch.py`, `lint.py`,
`file-formats.md`, the parser, or the scope gate.

---

## 11. Invocation truth — how a suite skill is actually reached

The suite mixes invocation modes (`writing-great-skills` GLOSSARY:
model-invoked keeps a description; user-invoked strips it). Under
Dreamwork the *coordinator* is the dispatching agent and the *human*
steers via the dashboard, so the invocation truth is three-valued and
the bridge distinguishes each rather than blurring them:

- **Human-typed (the default for the spine).** `grilling`, `to-spec`,
  `to-tickets`, `triage`, `implement`, `domain-modeling`, `handoff`,
  `prototype`, `setup-matt-pocock-skills` are `disable-model-invocation:
  true` — reachable only by the human typing the name. Under Dreamwork
  that is unchanged: he types it (in-session), and the bridge's
  task/questions adaptations apply to whatever it files/asks. The bridge
  does not make these model-invoked.
- **Loop-dispatched as a subagent (gated).** `research`, `code-review`
  are model-invoked in the suite. Under Dreamwork the loop *may*
  dispatch them as subagents, but that is agent-initiated surface → the
  scope gate (P4), and default **off** at the floor (OQ4). When
  dispatched, their output feeds tasks/questions, never bypasses.
- **Never autonomous: any skill that decides with him.** `grilling`,
  `domain-modeling` (the HITL branch), `wayfinder` HITL tickets — the
  loop never stands in for the human's side (the suite's own invariant;
  P2). The bridge routes their *questions* to `questions.md` and stops.

The bridge states, in its SKILL.md, which skills fall in each bucket, so
neither a coordinator nor a reviewer infers reach from the suite's
frontmatter alone — the frontmatter says how the *suite* reaches them,
not how the *loop* may.

---

## 12. Tests and verification

A bridge is mostly translation, so its checks prove the seams hold. The
repo's standard applies in full: a check is not verification until it
has been red; a green red-run is a finding, never a relief; assert at
runtime the precondition each check depends on.

**T1 — the task seam never opens the ledger (C1).** The adapter's
"create issue" path is invoked; the test asserts it called
`dev/ledger.py file` (subprocess, mocked) and asserts it **did not**
open `.dreamwork/tasks.md` or `.dreamwork/ledger.sqlite3`. *Reddens on:*
the adapter reading the ledger directly — make it `open()` the file and
the open-assertion fires. *Runtime precondition:* assert the ledger path
resolves to a real file, or "did not open" passes on nothing.

**T2 — #294 cutover is invisible (C1).** Run the adapter against a
markdown-source target, then flip `source_of_truth` to store, and assert
the adapter's behaviour is byte-identical (it shells to the verb, which
dispatches internally). *Reddens on:* the adapter branching on
source-of-truth itself — add a branch and the two paths diverge.

**T3 — grill questions land validly (C2).** A grill question written by
the bridge is parsed by the **real** `watch.parse_open_questions` and
appears as a contribution with a recognised author tag. *Reddens on:*
the bridge hand-formatting the bullet — route it through
`human_block()`'s evil twin (column-0 text) and the parser drops it
(`#343`). *Runtime precondition:* assert the fixture has ≥1 real
contribution, or "it parsed" passes on an empty file.

**T4 — no per-target state dreamhub reads (C3).** Assert dreamhub's
readers (`status.json`, `watch-port`, `/data.json`, `handoffs.md`) are
unchanged by the bridge's presence — i.e. the bridge writes nothing
under `.dreamwork/` that is not already a core file. *Reddens on:* the
bridge writing a new `.dreamwork/` file — list the dir before/after.

**T5 — no invented author tag (C2).** Grep the bridge for any
`Grill (`/`Spec (`/`Ticket (` tag string; assert none. *Reddens on:*
adding one. (A future #254 R1 tag is adopted, not invented — this check
whitelists only the tuples `watch.NOTE_TAGS`/`ANSWER_TAGS` already
hold, imported, never restated.)

**Stated ceiling (not faked).** The bridge cannot verify the harness
actually dispatches a suite skill when the loop asks, nor that the human
typing a name reaches the bridged adaptation — both are harness
contracts, invisible to a unit test (the same ceiling the hooks plugin
records, `hook-plugin-coverage.md`). The mitigation: the adaptations
are fail-safe (their absence degrades — a question lands un-bridged but
still lands), and T1–T5 prove the seams the harness would call.

---

## 13. Activation story

1. **Detect.** Init resolves the suite by name (no scan); if
   `writing-great-skills` + `grilling` + `setup-matt-pocock-skills` are
   all present, the bridge is a candidate.
2. **Propose.** Orientation asks via `questions.md`: "the
   mattpocock/skills suite is installed — bridge it? (rec: yes, workflow
   spine only)". Per `DREAMWORK.md`, one clearly-superior answer would
   not be an ask — but the spine scope (OQ1–OQ5) is genuinely his, so it
   is.
3. **On yes.** DREAMWORK.md gains `Load: ud-dreamwork-matt-pocock-skills`
   + authority lines (default: none, the floor). The bridge writes
   `docs/agents/issue-tracker.md` → the ledger seam (§8), and a
   `docs/agents/domain.md` pointer to `CONTEXT.md`.
4. **Run.** Suite skills the human types get their task asks/questions
   bridged; the loop may dispatch read-only `research`/`code-review`
   subagents. Nothing polls; nothing holds a second queue.

---

## 14. Open questions — RULED (2026-07-30 00:20, via questions.md)

All five are **settled**. His rulings, recorded on `#287` and folded in
`questions.md`:

- **OQ1 → local ledger.** He also filed a follow-up (now `#492`, P3,
  deliberately much later): mirror task state to GitHub — issues for tasks,
  PR/issue↔task linking, webhook comments into the hub as task events.
- **OQ2 → rec.** One question per `questions.md` entry, awaited. His stated
  reason is the design's own: outdated questions are never asked and every
  question is as informed as it can be.
- **OQ3 → rec.** Repo-root `CONTEXT.md`, referenced not copied.
- **OQ4 → an autonomy level on posture.** Autonomous dispatch of suite tools
  is gated on a posture autonomy axis rather than being a flat no — filed as
  `#493`. Until that axis exists the default stands: human-invoked only.
- **OQ5 → probably the same autonomy level.** Self-filing becomes a steer the
  autonomy level gates (`#493`), not a permanent refusal.

The original five forks, with their recs, are kept below as the record of
what was ruled on.

**OQ1 — local ledger, or a real tracker mirrored?** Rec: **local ledger**
(the suite's tracker-doc names the ledger seam; no GitHub). Makes #294
invisible by construction and needs no remote authority. *Fork:* he may
want the suite to keep driving a real GitHub tracker (its designed-for
home), in which case `ud-dreamwork-github` already covers the forge side
and this bridge's tracker-adapter points at GitHub instead — the two
bridges would then share the forge spine. Which is it?

**OQ2 — grill cadence: block-and-await, or batch?** Rec: **one question
per `questions.md` entry, await** (preserves the suite's one-at-a-time
cadence + #254's one-root rule). *Fork:* that is chattier than
Dreamwork's "ask him less" preference; he may prefer a grill batched
into one multi-part entry (the `#421` sub-decision grammar). The two
read differently on the dashboard.

**OQ3 — `CONTEXT.md` home.** Rec: **repo-root `CONTEXT.md` as external
reference** (the loop points at it; copies nothing). *Fork:* he may want
it under `.dreamwork/docs/domain/` for consistency with durable docs —
which touches repo-root layout and is his call (G4).

**OQ4 — autonomous tool dispatch.** Rec: **human-invoked only by
default** (`research`/`code-review`/`prototype` are tools; autonomous
review/prototype is scope expansion the gate governs). *Fork:* he may
want the loop to self-review every increment — a real productivity gain,
and exactly the kind of thing the authority lines exist to grant.

**OQ5 — loop-generated specs/tickets through the gate.** Rec: **filing
loop-generated `to-spec`/`to-tickets` output is a human steer by
default** (agent-initiated → gated). *Fork:* he may want the loop to
draft-and-file autonomously (`file-as-task` authority) — convenient, and
the scope gate exists precisely because convenient is the case to gate.

---

## SUMMARY

- **What it is.** A design spec for `ud-dreamwork-matt-pocock-skills`, a
  bridge plugin that unifies the installed `mattpocock/skills` suite
  with Dreamwork. Specification only — approval authorises the design,
  not implementation, loading, setup, or any core change.
- **The one rule.** The suite runs unchanged. The bridge translates at
  three seams only: the task seam, the grill-to-questions scoping, and
  the suite-dial configuration. "Do not rewrite" is stated outright
  (§2); "what to change" is a written compatibility note (§9), not
  edits.
- **Three binding constraints.** C1 — tasks only through `dev/ledger.py`
  verbs / `ledger_parse` (the #294 cutover is invisible; a `dreamwork
  tasks` dispatcher is a split-out proposal, not a dependency). C2 —
  grill chains reuse the existing `questions.md` grammar + `human_block()`,
  obey #254, invent no tag. C3 — machine-local state stays rebuildable;
  dreamhub reads nothing new.
- **Responsibilities.** One table (§4): each behaviour has one owner;
  the bridge owns translation only. Lifecycle uses init/tasks/maintenance,
  declines tick (no polling/dual-queue — A′) and commands-for-v1.
- **Precedence.** Ledger is the spine (P1); `questions.md` is the only
  channel and grilling is scoped to it (P2); `DREAMWORK.md` authorises,
  `CONTEXT.md` defines terms (P3); the scope gate maps the suite's roles
  (P4); commit-yes/push-no inherits (P5).
- **Authority.** Read-only floor; handoff authority, autonomous grilling,
  dual queues, and edits to suite/core files are explicitly *not*
  granted (§7). Elevated actions are separate DREAMWORK.md lines.
- **Verification.** Five seam checks (T1–T5), each with its red line and
  runtime precondition, plus the stated harness-dispatch ceiling (not
  faked).
- **Open questions — RULED 2026-07-30 (§14).** OQ1 local ledger (+ `#492`
  much-later GitHub mirroring); OQ2 one question per entry, awaited; OQ3
  repo-root `CONTEXT.md` referenced; OQ4/OQ5 a posture autonomy axis (`#493`)
  gates autonomous dispatch and self-filing.
