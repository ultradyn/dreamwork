# Design — #426: an agent must survive its own files changing under it, or be told to reload

**Origin:** his words, 2026-07-28 17:38 (verbatim in `tasks.md` #426 and in the
brief). **Scope of this document:** the *principle* — every running agent
surface either continues correctly across an on-disk change or is explicitly
told to reload, and silently running against a half-updated tree is the
forbidden third state. **What landed with this design:** one increment —
`watch.skill_identity()` and its `/data.json` exposure — defended below. **What
did not:** the per-surface reload actions, the per-tick flag file, and any UI;
those wait on measured need, and the parts behind the `#263` second gate wait on
his word.

The reference implementations already in this repo, and the design copies their
*shape* rather than their bytes:

- **`.dreamwork/run-mode`** — re-read on every tick by `collect()` →
  `read_run_mode()` (`watch.py:4280`), so an on-disk change reaches a running
  loop. It is the *only* file in the system with that property today, and it is
  the shape to copy for "what reads it, and when".
- **`dev/deploy_state.py`** — answers "is the file right" and "is the process
  running that file" as **two separate questions**, using `GENERATION` (set at
  import, re-set on every `os.exec`) because a pid and a start time both survive
  `exec` and cannot tell those apart. It is the shape to copy for "the defined
  action on mismatch" — two answers, never one collapsed into reassurance.
- **`watch.serving_report` / `serving_cached`** (`watch.py:1360`) — answers
  "which revision is this *server* running" by byte-comparing the running bytes
  against the target's git history. It is the shape to copy for "the signal is
  cheap and per-surface".

The defect the principle names, and it is the default state today:
`SKILL.md`/`CLAUDE.md` are read once at session start by the *harness*, so a
change to either reaches nobody already running; a brief amended mid-flight has
no record of which version a lane read; and the dashboard server routinely
serves a snapshot many commits older than the tree it serves from, while a
status file claims it is current.

---

## 1 — The signal

A running agent checks **two independent facts**, because either alone misleads
(the same lesson `deploy_state.py` cost a batch to learn):

- **`commit`** — the short SHA of the skill tree's HEAD (`git rev-parse
  --short`, `--no-optional-locks` like every git call here). Names the whole
  tree exactly, and is already how the repo moves.
- **`skill_version`** — the latest filename in `migrations/`, which *is* the
  skill's version (`migrations/README.md`: latest by lexicographic sort, which
  the naming scheme makes chronological). A migration landing is *defined* as a
  change that affects what a running loop reads, so this is the cheap answer to
  "did the tree change in a way that reaches me".

**Why not mtime.** mtime survives nothing and lies across machines (a fresh
clone has fresh mtimes for identical content). `run-mode` re-reads mtime only
because it is machine-local and gitignored; it is a local dial, not an identity.

**Why not a content hash.** A hash of "the files I read" requires naming that
set first, and naming that set *is* the open problem — every surface reads a
different set. A hash also cannot distinguish "the tree changed" from "the
change affects what I read", which the brief names as the failure mode that
makes a signal get ignored. `commit` + `skill_version` split that distinction:
`commit` moves on every change, `skill_version` moves only on a migration — so
a commit-only delta is "the tree changed, maybe not for me" and a
`skill_version` delta is "the tree changed in a way defined to reach me".

**Cost / buy.** Cost: one bounded `git rev-parse` and one `os.listdir` per read
(both have hard timeouts and never raise). Buy: a single canonical shape every
surface can read and every report can carry, instead of each agent inventing a
"what version am I" check that drifts from the others.

> The deployed-snapshot case is ordinary, not a fault: a server running from
> `~/.cache/dreamwork/deployed/` is not a git checkout and has no `migrations/`,
> so both are `None`. Its *revision* is already answered separately by
> `serving_report` (byte-compares the running bytes vs the target's history).
> Collapsing the two would read as reassurance and answer half — exactly the
> failure `deploy_state.py` exists to prevent.

---

## 2 — What reads it, and when

Three cadences, one per surface class. `run-mode` is the prior art for the first:

| Surface | Read site (this repo) | When |
|---|---|---|
| the loop / a lane | `watch.skill_identity()` (new, called directly) | **at start** (record into `status.json` or the lane report) and **at increment boundaries** (compare to the recorded value before committing) |
| the dashboard server | `collect()` → `skill_identity()`, rides `/data.json` and the existing `/mtime` poll (`watch.py:3553`, `watch.py:3797`) | **per request** (every `/data.json` is a fresh read; `collect` does not cache identity, because the point is to notice it move) |
| the human / a coordinator | the dashboard (future render) or `status.json` | **on demand** |

**Per-tick is `run-mode`'s cadence, not identity's.** Identity is read *at
boundaries* by agents (cheap, and an agent cannot act mid-edit anyway), and *per
request* by the server. A per-tick *flag* file is a separate, heavier choice —
see §5.

The actual read sites named: `watch.collect()` (server, new field), the loop's
own tick (calls `watch.skill_identity()` directly — the convention below),
`initialization.md` step 7 (already compares `.dreamwork/skill-version` to the
latest migration at init; `skill_identity().skill_version` is the same comparison
factored out so it can run mid-session, not only at orient).

---

## 3 — The defined action on mismatch

Each surface gets the action it can actually perform. A server can replace
itself; a lane mid-edit cannot.

| Surface | Action on `commit` / `skill_version` mismatch | Why this and not another |
|---|---|---|
| **the loop (coordinator)** | record the new identity, surface "skill tree moved: was X, now Y" in `status.json` and the opening status; if `skill_version` moved, read the intervening `migrations/` entries before the next increment (the init protocol, mid-session) | the loop cannot `os.exec` itself, but it CAN re-read, and a migration is defined as reaching it |
| **the heartbeat / watch-events monitors** | **continue** — they are stdlib processes with no skill state; their correctness does not depend on SKILL.md. Report-only: include the identity they started under in their one-line output | killing/restarting them is loop machinery, which a subagent never touches (`#431`'s `pkill` lesson lives here) |
| **the `watch.py` server** | already solved differently and correctly: `GENERATION` changes on re-exec and every open tab reloads on the `/mtime` poll; `serving_report`/`deploy_state` name the staleness. No new action here | the server's mechanism is `os.exec`-on-deploy, which is the right one and already built |
| **an in-flight lane** | **finish the current increment on the tree it started under, commit, THEN reload** — never abort mid-edit | a lane cannot safely re-import its own code mid-edit; the safe equivalent of "reload" is "land this increment and re-read on the next tick". Abort loses committed-eligible work; finish-then-reload loses none |

The two-question discipline from `deploy_state.py` is the rule these all obey:
name what you *cannot* see ("behind by N watch.py commits"), not just that
something differs — "behind" is not actionable and gets ignored, which is worse
than absent.

---

## 4 — Relationship to `#263` lane H (the decision the brief asked for)

**Decision: they do NOT share a mechanism, and building them separately is
correct. Lane H is one *instance* of this principle, not a candidate for a
shared implementation.**

Reasoning, by the three things a "shared mechanism" would have to unify — and
each differs:

- **the comparand.** Lane H compares a *protocol version number* stamped in the
  journal against the server's expected version (`#263` increments 34–35: "a
  mixed-version server refuses writes before accepting one"). `#426` compares
  *code identity* (commit + migration version) against what the process recorded
  at start. A version number in data and a commit of source are different facts.
- **the trigger site.** Lane H fires at a **data-witness boundary** — before the
  server accepts a write. `#426` fires at a **time boundary** — per request / at
  increment start. Wiring lane H's gate to call `skill_identity()` would check
  the wrong thing at the right moment.
- **the action.** Lane H **fails closed** (refuse the write, no receipt, no
  `submissions.log` line — its red line is the check's position relative to the
  body read). `#426` **reloads or reports**. Refusing a write is not reloading.

What they *do* share is the **shape of the question** — "am I running what I
think I am?" — and that shape is already abstracted in `deploy_state.py`'s "two
questions, not one" (is the file right? is the process running it?). Lane H is
the *data-format* instance of that shape; `#426` is the *code-identity*
instance. They are parallel, not nested.

**Practical consequence.** Lane H's `H1 failclosed` and `H2 quiesce` (behind
the `#263` second gate, his to open — **not built here**) should consume a
journal-local version stamp, not `skill_identity()`. And `skill_identity()`
should not grow a "refuse writes" branch to serve lane H. Keeping them separate
is what lets each be built once, correctly, at its own boundary.

---

## 5 — What is NOT worth doing (a design that recommends everything is not a design)

- **A per-tick `.dreamwork/reload-signal` flag file, set by `just deploy` or the
  coordinator.** It would extend the `run-mode` mechanism to a second dial, but
  it needs a *writer* (deploy step or a tick) and a *reader* on every surface,
  and it conflates "the tree changed" with "you must reload" — the exact
  conflation §1 splits on purpose. **Convention beats mechanism here:** an agent
  that records `skill_identity()` at start and compares at increment boundaries
  gets the signal without a new file or a new writer. Defer the flag file until
  there is measured evidence the convention is insufficient (e.g. a lane that
  ran a full session against a stale tree without noticing). This is the one
  decision that is genuinely *his* — whether the convention suffices or the flag
  file earns its keep — and it is premature: the identity signal it would
  consume is what lands in this increment.
- **Auto-reloading `SKILL.md`/`CLAUDE.md` from inside the loop.** The harness
  reads these once at session start; the loop cannot make the harness re-read
  them, and an in-process re-read would desync from the harness's cached copy.
  The honest action is **report-and-reload-at-boundary** (§3), not a hot-swap.
- **A UI element for identity on the dashboard.** The field rides `/data.json`
  so it is *available*; rendering it is a `transitions.md`-governed change and a
  separate increment. The server's staleness is already rendered via
  `deployed`/`serving_report`; the *loop's* identity has no surface yet, and
  adding one before the convention is adopted would render a field that nobody
  writes.
- **Hashing "the files I read".** Named above: it requires solving the open
  problem (which set) and cannot split "changed" from "affects me". `commit` +
  `skill_version` already split it.

---

## The one increment that landed

`watch.skill_identity()` (pure, never raises, `--no-optional-locks`) returning
`{commit, skill_version}`, exposed in `collect()` as `skill_identity` so it
rides `/data.json` and the `/mtime` poll. Test-first, with the precondition
(migrations exist; this is a checkout) asserted at runtime so the check carries
no invisible expiry.

**Why this one.** It is the *foundation* the convention points at — without a
canonical identity shape, every agent invents its own and they drift. It stands
alone: an agent that can read and report its identity is strictly better off
than one that cannot, even if no reload action is ever wired. And it does not
collide with the `#425`/`#368` symlink-staleness work (that is about the
deployed snapshot's byte-identity; this is about the skill tree's identity).

**The named convention (no mechanism, one line each):** an agent records
`skill_identity()` at start and compares at increment boundaries; on a
`skill_version` delta it reads the intervening migrations before the next
increment; on a `commit`-only delta it reports and continues.

**Not a migration, not a UI gesture.** The function is additive and optional;
no existing target must act, so no `migrations/` entry. Nothing on the page
appears or vanishes, so `transitions.md` is not invoked.
