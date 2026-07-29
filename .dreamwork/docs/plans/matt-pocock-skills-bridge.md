# ud-dreamwork-matt-pocock-skills — bridge plugin (design spec)

> **Status:** design proposal, **specification only** (lane-287spec, #287).
> Not yet put to the human. This document is the deliverable; it is not a
> plugin, not a Load line, not a setup script, and not an edit to any
> suite file. **Approval of this document authorises none of those** —
> it authorises only the design, and each extension seam it names is a
> separate grant, exactly as `ud-dreamwork-github`'s plan made its
> authority lines separate. Where this file says "the bridge would", it
> describes work that is not authorised yet.
10>
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
30- **#254 (rooted exchange)** — design ratified. Grill chains reuse the
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
40systems; it edits zero suite files and adds zero suite commands. Every
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
50  `~/.jcode/skills/`, or wherever the resolver finds it) and invoked as-is.
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
60treats as configurable input) and *translates at the call boundary*. That
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
70been wrong here against an importable production one (`dev/ledger.py`
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
80`Answer (via watch, <ts>)` (his, never the loop's). The bridge invents
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
