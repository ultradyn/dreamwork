# #613 — the live session-log view (design)

Lane: `lane-sessionlog` (design only — no production code). His words are the
source: durable receipt `a71d1105-1e41-5c73-abe7-3f2c144f5301`
(`journal_consume.py show`), submitted through the dashboard composer
2026-07-31 ~16:35, including the dictated `## uiux-aux` section and an ASCII
tree mock. Companion tasks: `#614` (websocket/delta transport — lane-wsdelta,
NOT designed here), `#615` (per-client subagent views — scoped, not designed,
§10). Mockups: `.dreamwork/review/session-log-view.html` — he asked for
mockups *before* the component design locks, so the artifact shows
alternatives, not a fait accompli. Draft questions:
`.dreamwork/docs/plans/session-log-questions-draft.md`.

Every claim below is tagged **VERIFIED** (measured against a real file or
cited code) or **INFERRED** (a reading of his words or a judgment call).

## 1. What he asked for (the load-bearing sentences)

- A live, streamed, **hierarchical** view of the running dreamwork agent's
  session: `session > compaction page (if known) > [system_prompt |
  compaction msg | other non-user/assistant things | turn]`, then
  `turn > step (tool call | thinking | text output | …)`.
- Visually: *"thin thin single line expandable segments"* in a tree,
  indented children, TUI-inspired but pretty, consistent with the existing
  style; **the most recent child of every node auto-expands** so the view
  descends and ascends as the agent works. His sentence *"maybe we add
  faint"* cuts off mid-thought — **INFERRED** as faint indent-guide lines,
  flagged in the mockup as an inferred detail.
- **"should use new component system and only be available via that"** —
  quoted exactly; §8 is about not glossing it.
- **"make 1 simple component now but let us swap it out later"** — a stated
  tolerance for an interim component.
- Storage: the session JSONL **stays the source**; the DB holds
  **bookmarks** — line number AND byte offset — for major events. Within a
  turn, no DB references: knowing where a turn starts is enough because
  scanning forward is cheap. If offsets go inconsistent, **rescan** — he is
  explicit that rescan is the cheap fallback.
- **No polling**: the page registers via an API call; the server sets up an
  **inotify** watcher on the session file and scans new entries on notify.
- Events from different supported clients are **standardised somewhat**
  before forwarding to the web UI.
- *"Ask clarifying questions about this early on … show UI mockup artifacts
  for review before locking in UI component design and function."*

## 2. The source data, measured — Claude Code session JSONL

Measured against `/home/xertrov/.claude-p/projects/`
`-home-xertrov--llm-general-skills-ud-dreamwork/`
`c196985f-4070-4762-915f-7fd6cc8af895.jsonl` — the previous main-dreamer
session: 31,784 lines, 81.9 MB, 28 compactions, 4 days of loop time. All
**VERIFIED** unless marked.

**Location.** `~/.claude-p/projects/<cwd-slug>/<session-uuid>.jsonl`, where
`<cwd-slug>` is the working directory with `/` → `-`. Subagent transcripts
live beside it at `<session-uuid>/subagents/agent-<slug>-<hash>.jsonl`
(§10). **The transcript sits OUTSIDE `--target`** — `#180`'s open note
already flags that `resolve_confined` (`watch.py:3978`) cannot serve it;
§6 designs the gate rather than widening that one.

**Record grammar** (types × counts in the measured file):

| type | count | maps to (his hierarchy) |
|---|---|---|
| `user` — `message.content` a plain string (401) or text blocks (4), not `isMeta`, not `isCompactSummary` | 405 | **user turn** start |
| `user` — `content` is `tool_result` blocks | 6,439 | step: a tool call's result half |
| `user` — `isCompactSummary: true` | 28 | **compaction msg** |
| `user` — `isMeta: true` (skill preambles etc.) | 11 | "other non-user/assistant things" |
| `assistant` — blocks: `text` 2,836 · `tool_use` 6,439 · `thinking` 3,731 | 13,006 | **steps** inside an agent turn |
| `system` `compact_boundary` (carries `compactMetadata`: trigger, preTokens, postTokens, `logicalParentUuid`) | 28 | **compaction page boundary** |
| `system` `stop_hook_summary` 345 · `turn_duration` 22 (durationMs, messageCount) · `away_summary` 9 | 404 | "other" row / turn annotation |
| `last-prompt` / `mode` / `permission-mode` / `ai-title` / `queue-operation` / `attachment` / `file-history-*` | 9,963 | chrome/meta — mostly hidden, §4 |

**Findings against his hierarchy:**

- **"compaction page (if known)" IS derivable** — `system:compact_boundary`
  records partition the file into pages; page N runs from one boundary to
  the next (page 0 = file start → first boundary). The boundary's
  `compactMetadata.preTokens/postTokens` make a good collapsed-row label.
- **`system_prompt` is NOT in the file.** No record type carries the system
  prompt; the harness never writes it to the transcript. The hierarchy slot
  he named renders as *absent* for this client (the tree simply has no such
  child), never invented. A per-client adapter MAY supply one where a
  client does record it. **VERIFIED** (absence measured over every record
  type in two sessions).
- **Turn boundaries are identifiable.** A *user turn* starts at a `user`
  record whose `message.content` is a string / text blocks (not
  `tool_result`, not `isMeta`, not `isCompactSummary`). An *agent turn* is
  the run from the first `assistant` line after that to the next user turn.
  One API call = 1–5 consecutive `assistant` lines sharing
  `requestId`/`message.id` (measured max 5), one content block per line;
  `tool_result` user lines interleave. Steps pair `tool_use` ↔
  `tool_result` by `tool_use_id`.
- **Append-only, measured.** A live session file grew 7,228,500 →
  7,338,867 bytes while its first 100,000 bytes stayed byte-identical
  (sha256 `db502b05…` both reads). The per-prompt metadata lines
  (`last-prompt`/`mode`/…) are *interleaved* throughout, not a rewritten
  header (line 1's `leafUuid` resolves 5 lines later, and the types recur
  at lines 15/16/17, 23/24/25, …). Compaction appends a boundary + summary
  record; it does not rewrite. So **(line, byte-offset) bookmarks are
  stable** under normal operation, exactly as he assumed — and staleness is
  still *detected*, never trusted (§5).
- **Rescan is cheap, measured.** A full parse-every-line structural scan of
  the 81.9 MB file: **1.0 s (82 MB/s)** in stdlib-json Python; line-split
  alone 0.03 s. Bookmark-worthy events in 4 days: **433** (405 user turns +
  28 boundaries). Do not over-engineer against drift; his rescan fallback
  costs a second on the largest session we have ever produced.
- **Timestamps** are ISO-8601 with ms (`2026-07-27T05:42:05.835Z`) on every
  content record.

## 3. The standardised model (the layer clients adapt into)

One vocabulary the web UI consumes, whatever the client. Two shapes: a
**node** (a row in the tree) and an **event** (a change to the tree). The
tree IS the standardisation — a client adapter's whole job is to turn its
transcript into these.

```
node  = { id, parent, kind, seq, ts, label, state, n_children?, ref? }
kind  ∈ session | page | turn.user | turn.agent | step.tool |
        step.thinking | step.text | sys.compact | sys.note
state ∈ live | done | error
ref   = { line, byte, len }          # where the detail lives in the source
event = { ev: open | update | close, node }
```

- `id` is content-stable (the record `uuid` where the client has one;
  `sess:<sid>/pg:<n>/turn:<uuid>` style paths otherwise) so the UI can key
  rows across ticks — the same identity discipline as `data-qid`
  (`transitions.md`, the regroup).
- **Thin rows carry labels and counts, never bodies.** `label` is the
  collapsed one-liner (`tool 8.1 · Edit asdf.txt (+123 −48)`,
  `agent turn 8 (29 steps)`); the body — args, response, full diff, prose —
  is fetched lazily via `ref` when a row expands (§6, `/session/peek`).
  This is what makes "no DB references within a turn" work: `ref` points at
  the source file, and the server serves the range on demand.
- `sys.note` is the honest bucket for `stop_hook_summary`, `away_summary`,
  `queue-operation` and anything a client emits that has no better home —
  his "other similar things that are not a user msg or assistant msg".
  Hidden-by-default chrome (`mode`, `last-prompt`, `file-history-*`)
  is *not emitted at all* in v1 (**INFERRED**: "concise" rules them out;
  an adapter can add an opt-in later without a schema change).
- `state: live` is derivable only at the frontier: the last agent turn with
  no closing user turn is live; a `tool_use` with no matching `tool_result`
  yet is live. Everything before the frontier is `done`. **VERIFIED**
  derivable; `error` comes from `tool_result.is_error` (present in the
  grammar) and API-error records.

## 4. Bookmarks — the DB half

**Where.** A machine-local, gitignored `.dreamwork/session-index.sqlite3`,
opened with the same WAL + `synchronous` + `busy_timeout` discipline as
`user_events/sqlite.py` (prior art named in `ledger_store.py`'s docstring).
**Not** a table in the ledger store: the ledger is durable truth with a
seeded id sequence and an event chain; this is a **disposable derived
cache** whose entire contents can be rebuilt by a 1-second rescan. Mixing a
rebuild-at-will cache into the store that must never be wrong-sequenced
couples their failure modes for nothing. (Decided here, not escalated — the
derived/durable split has one right answer.)

```sql
CREATE TABLE session (
  session_id TEXT PRIMARY KEY,       -- client's own id (the uuid)
  client     TEXT NOT NULL,          -- 'claude-code' | … (closed set, seeded)
  path       TEXT NOT NULL,          -- absolute, server-derived, never client-supplied
  cwd        TEXT,                   -- the target dir the session ran in
  started_at TEXT,                   -- first record ts
  last_line  INTEGER NOT NULL DEFAULT 0,   -- scan cursor: lines consumed
  last_byte  INTEGER NOT NULL DEFAULT 0,   -- scan cursor: bytes consumed
  sig        TEXT                    -- staleness tell: "<dev>:<ino>:<first-line-sha8>"
);
CREATE TABLE bookmark (
  session_id TEXT NOT NULL REFERENCES session(session_id),
  seq        INTEGER NOT NULL,       -- monotonic per session
  kind       TEXT NOT NULL,          -- 'page' | 'turn.user' | 'turn.agent' | 'sys.compact'
  line       INTEGER NOT NULL,
  byte       INTEGER NOT NULL,
  ts         TEXT,
  label      TEXT,                   -- the collapsed row label, precomputed
  meta       TEXT,                   -- JSON: counts, token figures, uuid
  PRIMARY KEY (session_id, seq)
);
CREATE INDEX bookmark_by_kind ON bookmark(session_id, kind, seq);
```

- **Major events only**, per his rule: page boundaries and turn starts.
  ~433 rows for the 4-day session — within a turn the scanner reads forward
  from the turn's `byte`, which §2 measured at 82 MB/s.
- **Consistency check, then rescan.** On use, seek to `byte`, read one
  line, require it to parse and (where `meta` holds a uuid) match. On any
  mismatch — or a `sig` change (inode replaced, first line differs) — drop
  the session's rows and rescan the file. No partial repair, no
  offset-arithmetic recovery: rescan is 1 s and cannot be half-right.
- The scan cursor (`last_line`/`last_byte`) is what makes the notify path
  incremental: on wake, read from `last_byte`, parse only new lines, append
  bookmarks for any new majors, emit events.
- A **partial trailing line** (the writer mid-append) is expected: the
  scanner consumes only lines ending `\n` and leaves the cursor before an
  unterminated tail. **INFERRED** necessary (not observed in the wild, but
  the failure is silent truncation if unhandled).

## 5. The scan/ingest path

One pure function per client adapter: `scan(fh, from_byte) → (events,
bookmarks, new_cursor)`. The Claude Code adapter implements §2's grammar;
it is the only adapter v1 ships. Ingest never blocks a request thread:
a single scanner thread per watched session owns the file handle, the
cursor, and the DB writes, and fans events out to registered listeners
(in-process queues, one per subscriber). Sequence:

1. registration names a session (§6) → scanner thread ensured, watcher armed;
2. cold start: if `session` row absent or `sig` mismatched → full rescan
   (1 s), bookmarks written, tree snapshot served from the result;
3. notify → incremental scan from `last_byte` → events to subscribers +
   bookmark/cursor writes;
4. no subscribers for N minutes → watcher and thread retire (the server
   must not tail files nobody is watching).

## 6. Registration, notify, and the API

Four routes; every one rides the existing `_preflight()` authority gate
(`watch.py:4497`) and adds **no** write exception — the session view reads.

- **`POST /session/watch`** `{session?: <id>}` → `{session, client, pages,
  cursor}`. Registers interest; arms the watcher; returns the snapshot
  skeleton (pages + turn bookmarks) so the page paints at once. With no
  `session` argument the server picks the **active** session (discovery
  below). This is his "register through an API call", **VERIFIED** as his
  words; it is a POST because it changes server state (a watcher exists),
  but it writes no target file, so the nine-write-exceptions contract
  (`watch-design.md:93`) is untouched — **INFERRED** classification, called
  out for review.
- **`GET /session/events?session=<id>&from=<cursor>`** → standardized
  events since `cursor` (§3). The *delivery* of "there are new events" is
  `#614`'s decision (websocket/SSE/long-poll); this route is the pull side
  every transport shares, and v1 binds it to the page's existing ~2s
  `/mtime` tick (`watch.py:4535`) by adding a per-session generation token
  — **the one deliberate deviation from "no polling" in v1**, see the
  honesty note below.
- **`GET /session/peek?session=<id>&byte=<b>&len=<n>`** → the parsed body
  of one record (a step's args/response/diff/prose), rendered lazily when a
  row expands. Bounded `len`; parse server-side, ship structured JSON, so
  the client never re-implements the grammar.
- **`GET /session/list`** → discovered sessions for this target (id, client,
  mtime, size, live-or-not), for a "which session" switcher.

**Confinement.** Session files live outside `--target`, so
`resolve_confined` (`watch.py:3978`) must not be widened and is not used
here. The gate is a **server-side registry**: paths are *derived* — client
root (`~/.claude-p/projects/`) + slug(cwd of target) + `<uuid>.jsonl`
matched against a strict pattern — and the browser only ever names a
session **id**, validated against the discovered set. No request parameter
is ever joined into a filesystem path. Same fail-closed posture, second
gate, deliberately narrow.

**Discovery — a measured gap.** Nothing today records which session IS the
running dreamwork agent (grepped `heartbeat.py`, `status_sync.py`,
`status_derive.py`, `SKILL.md`: no session identity anywhere). Two honest
options: **(a)** infer — newest-mtime `*.jsonl` in the client project dirs
for the target cwd (and its `.worktrees/*` slugs), marked live if mtime is
recent; **(b)** self-report — the loop writes `{client, session_id}` into
`.dreamwork/status.json` at orient (a loop-side change, and exactly the
per-client seam `#615`'s onboarding tasks want). Rec in the questions
draft: (a) for v1 with the switcher as the correction affordance, (b) folded
into onboarding as the durable fix.

**The inotify question, honestly.** There is **no inotify module in the
Python stdlib**, and the stdlib-only constraint survives (ruled 2026-07-30
07:44, `watch-design.md:41-51` — it retired the no-build/single-file half,
not the Python half). `#180` already recorded "no inotify in stdlib: poll"
for the events-stream idea. The real options:

| mechanism | what it costs | what it gives |
|---|---|---|
| `ctypes` against libc `inotify_init1`/`inotify_add_watch`, the fd read by the scanner thread (blocking `os.read`, or `selectors` if it multiplexes) | ~60–80 lines of struct-parsing ctypes; Linux-only; fd lifecycle owned by the scanner thread; needs a real test | true push, ~0 latency, zero idle cost — his stated design |
| bounded-interval `stat()` poll of ONE file (0.5–1 s) in the same thread | a stat syscall per second per watched session (~free); latency ≤ interval | portable, ~15 lines, cannot break |
| `inotifywait` subprocess | an external binary the loop cannot assume exists (the `#180` `jq` counter-rec, same ground) | nothing the ctypes path lacks |

**Recommendation, stated directly:** implement the watcher as one seam
(`SessionWatcher.wait_for_change()`), with **ctypes-inotify as the primary
on Linux and the stat-poll as the automatic degrade** (non-Linux, or
inotify init fails). This honours his stated design where the platform
supports it, and the fallback is the same code path with worse latency —
not a quiet substitution. If he prefers zero ctypes in the server, the
stat-poll alone is behaviourally indistinguishable in v1 *while the browser
tick is 2 s* — the server-side watcher only becomes the latency floor after
`#614` lands push. That fork is Q2 in the questions draft, with this
paragraph as its costs.

**Transport dependency (`#614`).** This design deliberately splits "server
learns the file changed" (the watcher, above — this lane's) from "browser
learns the tree changed" (`#614`'s websocket/delta lane, whose task entry
names this view as its main consumer). The event stream (§3) is the
interface between them: v1 delivers it over the existing tick, and `#614`'s
transport replaces the delivery without touching the schema, the scanner,
or the component. **INFERRED** split, from the two tasks' wording.

## 7. What the view shows (UI spec — see the mockup for the look)

- **Thin rows.** One line each (~1.5em), full-row hit target, mono, the
  house luminance ramp (`--text`/`--muted`/`--dim`/`--dimmer` — emphasis is
  luminance, never a second font; `client/style.css:2-5,34`). The commits
  panel rows (`client/style.css:358-390`) are the closest existing idiom
  and the mockup matches their density.
- **Tree + indent guides.** Children indent by a fixed step; a **faint
  vertical guide** (1px, `--line`-grade) marks each open ancestor level —
  the **INFERRED** completion of his cut-off "maybe we add faint" sentence,
  shown in the mockup with an alternative (no guides, indent only) so he
  can refuse it cheaply.
- **Auto-expand the frontier.** At every node, the most recent child is
  expanded by default; as new children arrive the previous frontier folds
  and the new one opens — the view "descends and ascends". Two hard rules
  from the house contracts:
  - **His hand wins.** A row he expanded or collapsed leaves the auto
    regime (the `#141`/`#494` class: open state is his, nowhere on disk);
    a quiet `follow` affordance re-attaches to the live frontier. Without
    this, the tree re-folds under his pointer every few seconds — the exact
    reset family `#505` catalogued.
  - **Fold/unfold are travels, not teleports.** The frontier moving is a
    disclosure closing + a disclosure opening: height travel + body
    reveal/ghost, the `foldDetailsLocal`/`travelCard` family
    (`transitions.md`, the section fold). Reduced motion: instant, function
    intact. A tick that lands mid-travel resumes it (`#477`).
- **The `⠏` progress indicator.** His mock uses a braille spinner glyph on
  live nodes. House tension, named rather than glossed: the wisp's design
  says *"Never a spinner"* (`client/style.css:824`; `transitions.md`, the
  awaiting-fold wisp — the one standing motion exception breathes instead).
  Both readings ship in the mockup: **(a)** a static `⠏` that *breathes* on
  the wisp's envelope (opacity in and out, ~5.5 s — TUI glyph, house
  motion); **(b)** a stepping braille cycle (`⠋⠙⠹⠸…`, authentic TUI, but a
  loop that sweeps — precisely what the wisp rule refused). Rec: (a). The
  glyph is the TUI half of "TUI inspired but pretty"; the breath is the
  pretty half.
- **Collapsed labels carry the summary**: `agent turn 8 (29 steps)`,
  `Edit asdf.txt (+123 −48)`, `page 3 · compacted 288k → 20k`. Counts come
  from bookmarks/scan, diffs from `toolUseResult` at peek time.
- **Depth cap in practice is 4** (page > turn > step > detail), so the
  indent budget at the 32ch floor is safe; the mockup shows the narrow case.

## 8. "Should use new component system and only be available via that"

The sentence presupposes a component system that did not exist yet when
this was written (`client/` was eight extracted files; `views.js`
string-builders were the one render authority). Whether one *should* exist
was exactly `#591` / `#505` G2 — **now ruled** (2026-07-31 17:03, `#591`,
receipt `dc9200a0-4ebf-5d3b-afab-71257155bef9`; `rec` on all three): **the
UI is transitioning to a component-based React web UI** — **G2 reads
per-surface** (one render authority *per surface*; a **derived** surface is
not a second authority), the claude-design breakpoint is **component-level
and staged** (tokens + `client/style.css` first, delegating wrappers
second), and the framework is **React**. `DREAMWORK.md:54-57` carries the
ruling for the loop; `render-architecture.md:166-177` carries the pinned
G2 reading. **The second-truth rule stays in force**: the wrappers are
*derived* — compiled from the same `client/*.js` `watch.py` already serves,
restating no markup, so nothing can diverge — and new surfaces are born as
components with no builder twin; a hand-maintained twin beside an existing
renderer stays refused. **This design was written before the ruling and
needed nothing to comply with it** — the ruling-independent contract below
is exactly the shape the ruling asks for. What it does:

- **The component contract is ruling-independent.** One component,
  `SessionLog`, with a narrow surface: *in* — the §3 event stream + an
  expand-state map; *out* — DOM under one mount point + `expand`/`collapse`
  /`follow` intents. Everything in §§3–7 (data model, API, scan path,
  visual spec, motion) is unchanged by whichever way G2 goes.
- **The binding is now informed by the ruling, though not forced by it**:
  whether `SessionLog` is (a) the first citizen of the new component
  system, or (b) a view module under the existing single render authority
  (registered like every view, `watch-design.md:202`). `#630`'s
  component-transition plan names new surfaces, this one explicitly, as
  **(a)** — *"component-native (session view born there; conversions
  join)"* — but defers the concrete call to this view's own implementation
  (*"P4 session view (#613's calls stay theirs)"*). His *"make 1 simple
  component now but let us swap it out later"* still licenses (b) as an
  interim in either world, so the contract above needs no revision for
  whichever way that lands.
- **"only be available via that"** is read as: the session view must never
  grow a second, hand-rolled rendering path in `views.js` that the
  component system would then have to replicate — the two-renderers trap
  (`watch-design.md:52-58`). It is **not** read as "block the view until
  `#591` rules", because his swap-later sentence points the other way.
  **INFERRED** reading — Q1 in the questions draft asks him to confirm or
  correct it, since the sentence is consequential enough that a wrong
  silent reading poisons the implementation plan.

## 9. Verified / inferred ledger (the roll-up)

**VERIFIED:** record grammar and counts (§2 table); compaction pages
derivable; `system_prompt` absent from the file; turn/step boundaries
derivable; append-only under growth (prefix-hash measurement); rescan 1.0 s
/ 82 MB/s; 433 bookmark-majors in 4 days; subagent transcripts at
`<session>/subagents/agent-*.jsonl` with the same grammar + `agentId`
(§10); no session-identity record anywhere in the loop's files; stdlib has
no inotify; stdlib constraint survives while no-build retired
(`watch-design.md:41-51`); "No websockets" is the standing live-reload
design (`watch-design.md:193`); `#591` ruled 2026-07-31 — component-based
React web UI, per-surface G2 (§8); `#180` prior art (poll note,
`resolve_confined` concern); server is `ThreadingHTTPServer`
(`watch.py:308`) so per-subscriber threads are viable.

**INFERRED (each flagged in place):** faint indent guides complete his cut
sentence; the "only via component system" reading (§8); the v1
tick-delivery deviation from "no polling" (§6); hidden-chrome suppression
(§3); partial-trailing-line handling (§4); the `#613`/`#614` transport
split (§6); POST classification of `/session/watch` (§6).

## 10. Point B (`#615`) — scoped, not designed

What a per-supported-client task must answer before anyone writes one:

1. **Where subagent transcripts live** and their naming/lifecycle. Claude
   Code: **VERIFIED** — `<projects>/<cwd-slug>/<session-uuid>/subagents/`
   `agent-<slug>-<hash>.jsonl`, same record grammar, every line
   `isSidechain: true`, plus `agentId` and the parent `sessionId`; files
   appear at dispatch and go quiet at completion (no terminator record —
   liveness is mtime).
2. **How the parent names the child** — whether the parent's `tool_use`
   (Agent tool) can be joined to the child file (id ↔ filename hash), so
   the subagent tree can mount *under the dispatching step* rather than in
   a separate list. Unmeasured even for Claude Code.
3. **The adapter mapping** — that client's records → §3's standardized
   nodes/events; what `system_prompt`/compaction/turn mean there, if
   anything (`ccc` runners: unknown; each needs the research he predicted).
4. **Discovery + identity** — how the loop learns child session ids for
   that client, and where onboarding records it (the §6 self-report seam is
   the natural home; `dev-support-onboarding-impl` gains one step per
   client, which is exactly how he asked for it to be folded in).
5. **Cost bounds** — a dispatch fans out to many files; the retire rule
   (§5.4) and a per-target watcher cap need numbers per client.

Dependency his wording already states: none of this starts until this
design's hierarchy + bookmark model settle, or every client task gets
redone.

## 11. Non-goals (v1)

- No search, no filtering, no cross-session diffing.
- No rendering of hidden chrome records (§3).
- No writes of any kind to the session file; the view is read-only by
  construction.
- No public/WAN exposure — the standing bind contract
  (`watch-design.md:81-92`) is untouched; the transcript is the loop's
  whole operating state and is *more* sensitive than `/data.json`, so
  `/session/*` is denied to `summary()`-class remote consumers by default.
