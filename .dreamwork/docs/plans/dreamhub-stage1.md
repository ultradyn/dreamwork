# dreamhub — stage 1, in detail (#96)

Human go 2026-07-25 10:48, after an earlier go and an explicit retraction.
The approval is real and narrow: **stage 1, and a plan before a build.**
Anything that widens past what this file scopes goes back to him first.

Chain: these increments serve **stage 1 (the aggregator)**, which serves
**"one human, several dreaming agents"** (DREAMWORK.md, added today),
which serves **"make 'leave an agent dreaming on a project' a real
workflow — walk away, come back to steady, safe, well-chosen progress"**.

The settled decisions in `daemon-mode.md` (herdr-preferred adapter, web
lifecycle, ssh swarm, channel plugins, PWA yes / Tauri deferred,
metadreamer) are not re-opened here. None of them is stage 1.

## What stage 1 IS

One stdlib-only file, `dreamhub.py`, serving a **read-only aggregate
overview of several dreamwork targets on this machine**: a registry the
human edits from the CLI (`add` / `remove` / `list`), and a page that
shows, per project, whether its loop is dreaming or has gone quiet, what
it is working on, how many questions are waiting on him, which dreamers
are out and what they own, and a way through to that project's own watch
dashboard. It reads each target's existing state — it computes almost
nothing of its own — and it writes nothing outside its own config
directory.

The value it adds that nothing today has: **one glance tells him which of
his dreamers has stopped moving.** Today that requires N bookmarks and
remembering which ports exist.

## What stage 1 is NOT

- **No lifecycle.** No start, stop, pause, resume, wrap, spawn, kill. Not
  for loops, not for watch instances. A down watch shows the command to
  start it; the human runs it. (Stage 2, and it needs the runtime adapter.)
- **No runtime adapter.** No herdr, no tmux, no send-keys, no stop hooks.
- **No remote, no ssh, no non-localhost bind, no auth.** `127.0.0.1` by
  construction, exactly as watch.py. Stage 3 opens that question, and it
  opens the auth question with it.
- **No channels, no notifications, no PWA, no push.** Stage 4.
- **No metadreamer, no dreamer spawning dreamers.** Stage 5.
- **No writes to any target.** No answering questions, no commands, no
  events-log lines. Steering stays on each project's own watch page,
  which already does it well. The checkable form of this edge: *the hub
  opens no file for writing outside `~/.config/dreamwork/hub/`.*
- **No second task list.** The hub never mints an id and never holds a
  queue; it reads each target's ledger and status.
- **Not a second UI for one project.** If you have one project, use watch.

## The one deviation from `daemon-mode.md`, and why

`daemon-mode.md` stage 1 says: `/` lists projects, `/{project}/…`
reverse-proxies to that target's watch port. **That is not buildable
today without changing `watch.py`**, and `watch.py` is owned by another
dreamer. Measured, not guessed — the page is root-absolute in three
distinct places:

| Where | Code | Breaks under a path prefix |
|---|---|---|
| Data fetches | `fetch('/data.json')`, `/mtime`, `/filedata`, `/answer`, `/comment`, `/command` | 404 at the hub |
| URL writes | `navigate()` builds `'/questions'`, `'/file?p=…'`; `history.pushState(…, url)` | address bar loses the prefix; next reload 404s |
| Route reads | `isInternal()` and `routeOf()` compare `a.pathname` against the literal `'/'`, `'/questions'`, `'/file'`, `'/review'` | deep link renders the *wrong view*, silently |

A generic injected shim can patch `fetch` and `pushState` from outside.
It **cannot** patch `routeOf`/`isInternal` — those are local functions
comparing string literals — so the failure that survives is the silent
one: a deep link that renders the dashboard and looks fine.

**Rec (taken here): origin-per-project.** The hub links out to each
project's own `http://127.0.0.1:<its port>/`, where every absolute URL is
already correct and nothing needs patching. This is not a dead end for
the swarm either: `ssh -L` gives a *local port per remote project*, which
is the same shape — the prefix problem never has to be solved to get
stage 3.

The prefix belongs to `watch.py`'s **server-core seam in #124**, where
those three sites are being touched anyway. Filed there, not here.

## The boundary with `ud-dreamtask` (#50)

Both were approved today and both are about "agents and tasks outside one
session", so state the line before either is built.

| | ud-dreamtask | dreamhub |
|---|---|---|
| What it is | a **skill** — a loop shape | a **server** — a surface |
| Scope | one errand, one agent, ends when acceptance criteria verify | N loops, seen from outside, runs indefinitely |
| Whose problem | how *an agent* works a task | what *the human* sees and steers |
| Serves a page | never | always |
| Runs a loop | always | never |
| Mints ids / holds a queue | for its own decomposition | never |

They meet at exactly one place, and it is a **data contract, not code**:
ud-dreamtask writes a dreamstate (`status.json`, `questions.md`,
`dreams/`) in the same shapes a `.dreamwork/` uses, so **a dreamtask
dreamstate is just another target the hub can list.** Neither builds the
other. If a future increment finds itself teaching the hub about tasks,
or teaching dreamtask about serving, the boundary has been crossed.

Namespace, so they cannot collide under one home:
`~/.config/dreamwork/tasks/` is dreamtask's, `~/.config/dreamwork/hub/`
is dreamhub's. Named owners, per the day's most expensive lesson.

## What is genuinely shared with `watch.py`

**The protocol, the styleguide, and the guard contract — never the code.**

- **Protocol.** Per project the hub polls `GET /mtime` (tiny: `"<gen>
  <mtime>"`) and re-fetches `GET /data.json` only when it changes. That
  is the same contract watch's own client uses, so the hub costs a
  running watch instance almost nothing, and `/mtime` doubles as the
  liveness check. It also means **the hub never parses `questions.md`** —
  the open-question count has exactly one implementation, and when that
  implementation is not running the hub says *unknown* rather than
  computing a second, subtly different answer.
- **Styleguide.** `watch-design.md` tokens, mono stack, two sizes, one
  accent, no cards, dim uppercase labels, "liveness is the design", the
  page voice. Read it; do not edit it (owned).
- **Guards.** `(OUT, PORT)` argv contract, playwright, against a frozen
  fixture. One contract; a second doubles the confusion (#117).

**No `import watch`.** It would couple the hub to a 3000-line owned file
and break the single-file deploy-snapshot property. The trade, stated so
it stays bounded: *duplicate trivia (a `read_text`, a `_safe_json`), never
duplicate an interpreter (a parser, a counter, a classifier).*

`dreamhub.py` stays **one stdlib file** in stage 1, so `just deploy`'s
snapshot pattern (`git show HEAD:<file>` → run from outside the repo, so
an agent editing the tree cannot change what is serving) applies to it
unchanged. It will eventually hit the same size wall watch.py did; stage
1 should land around 600–800 lines, well short of it.

## The increments

Nine, each ~15–20 minutes, each ending green and committable. Eight are
build; the ninth is a handoff.

**I1 — Registry and CLI.** `dreamhub.py`: `add <path>` / `remove <slug>` /
`list`, JSON at `~/.config/dreamwork/hub/projects.json`, written via
atomic replace. Slug = lowercased basename, collision → `-<6 hex of
abspath>`; **the slug is stored at add time, never recomputed on read** —
recomputing means adding a colliding project silently renames an existing
one. `add` rejects a directory with no `.dreamwork/` and no
`DREAMWORK.md` unless `--force`.
*Gate:* `pytest test_dreamhub.py` — round-trip, collision, duplicate add
is idempotent, non-target rejected, `~`/relative paths normalised to
absolute. *Catches:* the two silent registry bugs — a collision eating an
entry, and a typo'd path sitting in the list looking healthy.

**I2 — Disk probe (pure, no network).** Directory → row: port from
`.dreamwork/watch-port` (absent = never watched), `status.json` parsed
defensively, `last_tick` age, and a state: `dreaming` (<10m), `quiet`
(10–60m), `stalled` (>60m), `no status`, `missing`.
*Gate:* pytest over `dev/hub/fixture/` (fresh, stale, no-status,
half-written JSON, deleted directory). *Catches:* a crash on a
half-written `status.json` — it is rewritten every tick, so the hub
*will* read one mid-write; and a missing target vanishing from the list
instead of showing as broken.

**I3 — Live probe (network half).** `GET /mtime` per project with a hard
timeout; `/data.json` only on change; each project isolated so one bad
one cannot affect another.
*Gate:* pytest against a stdlib stub server — up, 404, connection
refused, slow (must time out), garbage body. *Catches:* the classic
aggregator failure, one dead port hanging the whole page. This is the
single most likely stage-1 bug.

**I4 — Server and index render.** `dreamhub.py serve`: binds `127.0.0.1`,
port persisted to `~/.config/dreamwork/hub/port` (mirrors watch's
per-target `watch-port`, one level up), `/hub.json` returns the aggregate,
`/` renders it. Two facts per row under a header pair, per the
"label the columns, not the gaps" idiom.
*Gate:* pytest on the generated HTML (a row per registry entry, states
present, no unescaped target text) plus `/hub.json` shape. *Catches:*
**nothing visual** — which is precisely why I5 exists and why this
increment must not be mistaken for done.

**I5 — Structural guard.** `dev/hub/hub.mjs`, playwright, `(OUT, PORT)`.
Against a registry over the hub fixture, assert: N rows for N entries;
the stale row carries its marker; the down row shows a start command and
does not link to a dead port; no horizontal overflow; a screenshot lands
in `OUT` for a human to look at.
*Gate:* `node dev/hub/hub.mjs "$out" 39897` exits 0. *Catches:* #117
exactly — pytest green while the page renders blank, or one row, or all
rows identical.

**I6 — Cross-contract guard, against a real watch instance.** Start
`watch.py` against a copy of `dev/capture/fixture` (read-only use of an
owned directory — never edited), point a registry at it, assert the hub
row's question count equals what that watch instance reports in
`/data.json`, then mutate the copy's `questions.md` and assert the hub
row follows within one poll.
*Gate:* the script exits non-zero on mismatch. *Catches:* the only
cross-file dependency stage 1 has — `/data.json` or `/mtime` shape drift
under the watch.py owner's edits. Without this, the hub silently reports
stale or zero counts and looks fine doing it.

**I7 — Liveness.** The page polls `/hub.json` ~2s and re-renders ages
client-side every second; state changes are visible without a reload.
*Gate:* the guard asserts an age string changes with no navigation, and
that rewriting a fixture's `status.json` mid-run flips that row's state.
*Catches:* a dashboard that lies about being live — the one sin
`watch-design.md` names as disqualifying for this kind of page.

**I8 — CLI ergonomics and docs.** `serve --open`, `--port`, a port-in-use
error that names the port (watch.py's wording), `--help` that reads like
the tool. `dreamhub-design.md` at the skill root — the standing design
record, and in particular **the exact `/data.json` and `/mtime` fields
the hub depends on**, so the drift I6 catches has somewhere to be read.
Doc-map rows for `dreamhub.py` and `dreamhub-design.md`; one README line.
*Gate:* `--help` snapshot test; doc-map row present. *Catches:* a second
tool in the repo with no documented contract — the thing the doc-map
exists to prevent.

**I9 — Handoff (not a build).** Stage 1's guards are **not** in
`just test` until the justfile's owner adds them. Produce the one-line
recipe diff, hand it to the coordinator, and until it lands say out loud
in the report that *green `just test` does not cover the hub*. Report the
queue changes (follow-on tasks below) to the coordinator; the ledger has
one writer.

**Honest estimate:** the ledger says 120m for #96. Nine increments at
15–20m is **150–180m**. The plan itself was not free either.

## Where the state lives

The rule is one home per fact.

| Fact | Home | Why there |
|---|---|---|
| Which projects exist | `~/.config/dreamwork/hub/projects.json` | a fact about *this machine*, not about any repo; committing it would be wrong on the next machine and would leak local paths |
| The hub's port | `~/.config/dreamwork/hub/port` | same; mirrors `.dreamwork/watch-port` one level up |
| Hub logs / scratch | `~/.cache/dreamwork/hub/` | mirrors `~/.cache/dreamwork/deployed` |
| A project's status, questions, port, git | that project's own `.dreamwork/` | **read only, never copied.** A cached copy would be a second source of truth that goes stale exactly when it matters |
| The aggregate | in memory, per request | a persisted aggregate is that same second source of truth with a longer life |
| `dreamhub.py`, tests, guards, fixture, design doc, this plan | this repo | shipped product, like watch.py |

Nothing in stage 1 is added to `.gitignore`: all of the hub's mutable
state is outside the repo by construction.

## Ownership and disjointness

Stage 1 can run beside the dreamer holding the webui.

**Creates (uncontended):** `dreamhub.py`, `test_dreamhub.py`,
`dreamhub-design.md`, `dev/hub/` (guard + fixture),
`.dreamwork/docs/plans/dreamhub-stage1.md`.

**Edits (low contention, name it at dispatch):**
`.dreamwork/docs/doc-map.md` (rows), `README.md` (one line).

**Must not touch (owned by another dreamer):** `watch.py`,
`watch-design.md`, `test_watch.py`, `dev/capture/`, the `justfile`
`GUARDS` list. I6 *reads* `dev/capture/fixture` and *runs* `watch.py`;
neither is an edit. The justfile change is I9's handoff, not an edit.

**Coordinator-only:** `.dreamwork/tasks.md`, `.dreamwork/questions.md`.

Stage 1 does not need `watch.py`. If a later increment finds it does, the
answer is to stop and hand it over, not to edit it.

## Where the rest lands (so nothing here pretends to be stage 1)

- **Compaction's managed sender** (`compaction.md`, #127) is **stage 2**:
  sending a notice and then the command requires a session handle, which
  is the runtime adapter. Stage 1 does contribute its precondition — it
  makes `status.json`'s `agents` block *visible*, and a managed sender
  that cannot see which dreamers are out and what they own has no
  business sending anything.
- **`/{project}/` prefix URLs** — `watch.py`'s server-core seam, #124.
- **A light `/summary.json`** on watch, so an aggregator does not pull
  full document text over a link — a stage-3 concern (ssh), not a local
  one. Noted so it is not invented twice.

## Follow-on tasks for the ledger (coordinator writes them)

1. Teach `watch.py` a URL prefix (3 sites: fetches, `navigate`/pushState,
   `routeOf`/`isInternal`) — do it inside #124's server-core seam.
2. Wire the hub guards into `just test` (one line; justfile owner).
3. `/summary.json` on watch for cheap aggregation — blocked on stage 3.

## Open question for the human (one, not blocking)

**URL space.** Your sketch was `/{project}/…` under one hub URL. Stage 1
ships **origin-per-project** instead (the hub lists and links; each
project keeps its own port and its own URLs) because the prefix requires
three changes inside `watch.py`, which another dreamer holds, and because
`ssh -L` preserves origin-per-project all the way into the swarm stage.
The prefix stays available and is filed against #124. Build proceeds on
this rec unless you say otherwise — say so if you want the single-URL
bookmark badly enough to serialise stage 1 behind a watch.py change.

--- SUMMARY ---

- **Stage 1 is a read-only aggregate over several local dreamwork
  targets**: a CLI-managed registry, one page showing per project whether
  it is dreaming / quiet / stalled / down, what it is working on, its
  open-question count, and which dreamers are out — plus a link through
  to that project's existing watch dashboard.
- **Explicitly not**: lifecycle, runtime adapters, ssh/remote, auth,
  channels, PWA, metadreamer, any write to any target, any second task
  list.
- **One deviation from `daemon-mode.md`, measured not guessed**: the
  planned `/{project}/` reverse proxy cannot be built without editing
  `watch.py` (root-absolute fetches, pushState URLs, and — the one no
  external shim can fix — `routeOf`/`isInternal` comparing
  `location.pathname` to string literals, which fails *silently* by
  rendering the wrong view). Rec taken: origin-per-project now; the
  prefix belongs to #124's server-core seam. `ssh -L` makes
  origin-per-project survive into the swarm stage.
- **Reuse is at the protocol layer**: the hub polls each watch's
  `/mtime` and re-reads `/data.json` on change — so it never parses
  `questions.md`, and the open-question count keeps exactly one
  implementation. No `import watch`; duplicate trivia, never duplicate
  an interpreter.
- **Nine increments of 15–20 minutes**, each with its own gate and a
  stated failure it catches. The verification story is deliberately two
  halves after #117: pytest cannot see what renders, so a playwright
  guard asserts the page, and a sixth increment runs the hub against a
  **real watch instance** to catch `/data.json` drift. Honest estimate
  150–180m, not the ledger's 120m.
- **State**: registry and hub port are machine-local under
  `~/.config/dreamwork/hub/`; every per-project fact stays in that
  project's `.dreamwork/` and is read, never cached to disk; code, tests,
  guards and docs are committable repo content.
- **Disjoint from the webui dreamer**: creates `dreamhub.py`,
  `test_dreamhub.py`, `dreamhub-design.md`, `dev/hub/`; touches
  `doc-map.md` and one README line; never `watch.py`,
  `watch-design.md`, `test_watch.py`, `dev/capture/` or the justfile
  (the guard-wiring line is handed to its owner).
- **Boundary with ud-dreamtask stated**: dreamtask is a loop shape for
  one errand and never serves a page; dreamhub is a surface over many
  loops and never runs one. They meet only as a data contract — a
  dreamtask dreamstate is a target the hub can list — and their config
  namespaces are split (`tasks/` vs `hub/`).
- **One open question, non-blocking**: confirm origin-per-project vs the
  single-URL `/{project}/` prefix.

## Decided by the loop, 2026-07-28 — origin-per-project, and the ask is withdrawn

The URL-space question (#96) sat open in `questions.md` from 2026-07-25 and was
**withdrawn without being answered** under his 05:35 rule: a decision with one
clearly superior answer is not an ask, and its reasoning belongs in an aux
document, which is this one.

**Origin-per-project stands.** The hub lists and links out; each project keeps its
own port and its own URLs. The measurement that decides it: `routeOf()` and
`isInternal()` compare `location.pathname` against string literals **inside a
generated JS string**, so they cannot be reached from outside the page. Two of the
three root-absolute sites (the fetches and `pushState`) can be shimmed; that third
cannot. Under a path prefix a deep link therefore renders the **wrong view,
silently** — which is the worst failure available, strictly worse than not
supporting the prefix at all.

`ssh -L` also yields a local port per remote project, so origin-per-project
survives into the swarm stage unchanged, and prefix support (if ever wanted)
belongs to #124's server-core seam where those three sites are being touched
anyway.

**Reopenable.** The single-URL bookmark is a preference only he holds, so if he
wants it he can overturn this — the cost is a `watch.py` change and serialising
stage 1 behind it. It is simply not worth his attention unasked.
