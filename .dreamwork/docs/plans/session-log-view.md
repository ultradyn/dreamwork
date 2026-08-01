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

Revised 2026-07-31 by `lane-663indicator`: `#662` (the "never a spinner"
promotion corrected here and scoped at its sources) and `#663` (his 18:53
answers folded — `guides: G1`, `marker: M1`, tool rows gone native in §7c,
the indicator redesigned in §7b).

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

**Answered 2026-07-31 18:53** (`questions.md`, the `#613` entry — his words
verbatim): **`guides: G1`. `marker: M1`**, with a scoping sentence that
governs the whole visual layer, not just the marker: *"we don't care so
much about being truly faithful to tui limitations, just want to keep the
design a bit evocative of that"* — **evocative-of-TUI, not
faithful-to-TUI**. Tool child rows: *"you are welcome to redesign this
part to be less intrusive and include native / special case rendering for
tool calls we care about"*, with hiding empty args named as the minimum
(§7c). The live indicator was **reopened as lane work** (`#662`, `#663`):
loading animations are good, braille-stepping is *"better than many but
still kinda boring"*, he wants *"an interesting thematic one"*, with
`~/src/forum`'s peek icon as inspiration and explicitly not to copy (§7b).
`Q1`/`Q2`/`Q3` (§6, §8) remain open with him.

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
already flags that `resolve_confined` (`watch.py`) cannot serve it;
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
  collapsed one-liner (`8.1 · edit asdf.txt (+123 −48)`,
  `agent turn 8 (29 steps)` — the per-tool label grammar is §7c);
  the body — args, response, full diff, prose —
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
(`watch.py`) and adds **no** write exception — the session view reads.

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
  `/mtime` tick (`watch.py`) by adding a per-session generation token
  — **the one deliberate deviation from "no polling" in v1**, see the
  honesty note below.
- **`GET /session/peek?session=<id>&byte=<b>&len=<n>`** → the parsed body
  of one record (a step's args/response/diff/prose), rendered lazily when a
  row expands. Bounded `len`; parse server-side, ship structured JSON, so
  the client never re-implements the grammar.
- **`GET /session/list`** → discovered sessions for this target (id, client,
  mtime, size, live-or-not), for a "which session" switcher.

**Confinement.** Session files live outside `--target`, so
`resolve_confined` (`watch.py`) must not be widened and is not used
here. The gate is a **server-side registry**: paths are *derived* — client
root (`~/.claude-p/projects/`) + slug(cwd of target) + `<uuid>.jsonl`
matched against a strict pattern — and the browser only ever names a
session **id**, validated against the discovered set. No request parameter
is ever joined into a filesystem path. Same fail-closed posture, second
gate, deliberately narrow.

**Discovery — was a measured gap; RULED 2026-07-31 and now CLOSED (`#665`).**
The original finding and both options are kept verbatim below, because the
ruling is only legible against what was asked. Nothing then recorded which
session IS the running dreamwork agent (grepped `heartbeat.py`,
`status_sync.py`, `status_derive.py`, `SKILL.md`: no session identity
anywhere). Two honest options: **(a)** infer — newest-mtime `*.jsonl` in the
client project dirs for the target cwd (and its `.worktrees/*` slugs), marked
live if mtime is recent; **(b)** self-report — the loop writes
`{client, session_id}` into `.dreamwork/status.json` at orient (a loop-side
change, and exactly the per-client seam `#615`'s onboarding tasks want). Rec
in the questions draft: (a) for v1 with the switcher as the correction
affordance, (b) folded into onboarding as the durable fix.

**He answered (b) and rejected (a) by omission** — *"for the main dreamwork
agent, we can record its session in status.json (note: this is easy to detect
via env var, but the env var name changes per cli client …)"*. That is the
stronger half rather than merely the cheaper one: inference is ambiguous the
moment two sessions run against one target, which is the normal case here.
Built in `#665`: `client_env.py` holds the per-client variable registry, the
main agent writes `agent_session` into `status.json` at orient, and the shape
is in `file-formats.md`. It records ABSENCE honestly for a client with no
session variable rather than inferring one.

Option (a) is dead **as an identity mechanism** and survives only as what it
was always better at: populating the `GET /session/list` switcher with
sessions the loop does *not* own. "Which sessions exist here" and "which
session IS the agent" are different questions, and only the second one was
ruled.

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

His 2026-07-31 scoping sentence governs this whole section:
**evocative-of-TUI, not faithful-to-TUI**. Re-read under it, two earlier
calls turn out to have been argued on fidelity grounds that no longer
count for anything: option B's stepping cycle was credited as *"authentic
TUI"* (authenticity was its one listed virtue, and he called it boring
anyway), and M2's brackets took his mock's `[+]` notation more literally
than he meant it. Braille cells stay in the design as **material** — one
character cell holds eight addressable dots, which §7b spends — not as
fidelity.

- **Thin rows.** One line each (~1.5em), full-row hit target, mono, the
  house luminance ramp (`--text`/`--muted`/`--dim`/`--dimmer` — emphasis is
  luminance, never a second font; `client/style.css:2-5,34`). The commits
  panel rows (`client/style.css:358-390`) are the closest existing idiom
  and the mockup matches their density.
- **Tree + indent guides — his call: `G1`** (2026-07-31). Children indent
  by a fixed step; a **faint vertical guide** (1px, `--line`-grade) marks
  each open ancestor level. (This began as the **INFERRED** completion of
  his cut-off "maybe we add faint" sentence; he confirmed it, so it is now
  his.)
- **Disclosure marker — his call: `M1`** (2026-07-31): quiet chevrons
  `▸/▾`, the page's details idiom, dimmer than the labels they precede so
  the labels keep the luminance ramp. His mock's `[+]`/`[-]` notation was
  a structure-sketch, as suspected, not a visual spec.
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
- **The live indicator — redesigned; §7b.** The first version of this
  plan rejected his braille-stepping option by citing a standing *"Never a
  spinner"* house motion language at `client/style.css:824`. That was
  `#662`: the line number was wrong (the sentence sat at `:884` when
  `#662` was filed; the `#662` fix's own insertion at the `:761` site
  moved it to `:887` — line citations rot, which is the whole lesson),
  and the sentence is **scoped** — it describes the awaiting-fold wisp,
  *"the ONE deliberate exception to the opt-in motion rule (#113)"*
  (`client/style.css:887`, the wisp comment; `transitions.md`, the wisp
  section), an element with no progress to count. The only other
  occurrence (`client/style.css:761`) refuses a *spinner forever* — an
  indeterminate state with no exit — not loading animation. Both source
  sites now carry their scope inline so the promotion cannot recur. Nothing in the house rules forbids a moving
  indicator here; `#113`'s reduced-motion discipline still binds it like
  every animation.
- **Collapsed labels carry the summary**: `agent turn 8 (29 steps)`,
  `edit asdf.txt (+123 −48)`, `page 3 · compacted 288k → 20k`. Counts come
  from bookmarks/scan, diffs from `toolUseResult` at peek time; the
  per-tool label grammar is §7c.
- **Depth cap in practice is 3 rows** (page > turn > step) plus an
  expanded step's indented body — §7c retires the old fourth level — so
  the indent budget at the 32ch floor loosens; the mockup shows the
  narrow case.

### 7b. The tally — a step odometer on an always-clockwise ratchet

His steer (2026-07-31): loading animations are good; braille-stepping is
*"better than many but still kinda boring"*; he wants **interesting and
thematic**, with `~/src/forum`'s peek icon as inspiration, explicitly not
to copy. The reference, read at source
(`app/javascript/stylesheets/design-scarce-mono.scss:1429-1472`,
`app/views/nodes/_ledger_peek_icon.html.erb`, and the Alpine scope at
`_ledger_row.html.erb:6` — `togglePeek() { this.arm += 90; this.group +=
180 }`): a two-bar `+`/`−` icon where every toggle advances the same way
round, so open and close both turn clockwise and the icon **never
unwinds** — its current angle is a memory of every toggle there has ever
been. The transferable quality is not the shape: it is **monotonic
accumulation driven by discrete meaningful acts**, instead of a
wall-clock loop that returns to where it started.

The session log owns a better ratchet than toggles: the transcript is
**append-only** (§2, measured) — work accrues and never rewinds. So the
indicator should *be* the progress:

- **One braille cell as an odometer wheel.** Each record landing in the
  live turn (thinking, tool call, tool result, text) advances the wheel
  one dot around the cell's perimeter, clockwise (dot order 1 2 3 7 8 6
  5 4): `⠁⠃⠇⡇⣇⣧⣷⣿`. A full cell then **empties** one dot per record the
  same way round — the hole sweeps clockwise: `⣾⣼⣸⢸⠸⠘⠈⠀` — and fills
  again. Sixteen states, phase = records mod 16, direction never
  reverses. The glyph is a memory of the turn's work the way the forum
  icon's angle is a memory of its toggles.
- **Motion means a record landed; stillness plus breath means waiting.**
  Between records the glyph breathes on the wisp's envelope (~5.5 s
  opacity — the house's existing "alive, nothing to report" idiom,
  correctly scoped this time: the *wait* gets the breath, the *work* gets
  the ratchet). A landing record pulses the glyph briefly bright as its
  dot arrives, then the breath resumes. A wall-clock spinner animates
  hardest when the agent is most wedged; the tally cannot lie that way —
  which is what makes it interesting rather than decorative, and thematic
  twice over (the append-only log it mirrors; the TUI cell it inhabits).
- **Placement.** Every live-spine row (the live turn and its running
  step) shows the same turn-wheel, advancing together — one clock per
  turn, one shared breath envelope (the wisp's one-organism rule). A new
  turn starts a fresh wheel at `⠀`.
- **Delivery.** v1 events arrive in ~2 s batches (§6), so a batch of N
  records steps the wheel N times at ~120 ms per step rather than
  teleporting — an eased ratchet, still monotonic. `#614`'s push
  transport tightens the granularity without touching the design.
- **Reduced motion is not "nothing happens":** the wheel still changes
  state per landed record — a discrete repaint, no transition, exactly
  the forum icon's own reduced-motion answer (`transition: none`; the
  state still lands) — while the breath holds at a legible constant
  opacity (the wisp's answer) and the arrival pulse is dropped.

**Alternatives, with costs** (all three live in the mockup):

| option | what it is | what it costs |
|---|---|---|
| **T1 · the tally** (rec) | the event-ratcheted odometer above | motion is data-driven, so a long silent Bash call shows only the breath (honest, but quieter than a spinner); needs ~10 lines of client state no pure-CSS loop needs |
| T2 · the snake | a 5-dot arc advancing clockwise on wall-clock (`⣇⣦⣴⣸⢹⠻⠟⡏`), pure CSS `steps()` | always-clockwise but wall-clock: it animates identically whether the agent is working or wedged, and it sits one reshuffle from the stock cycle he already called boring |
| B · stock stepping cycle | `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` | his own verdict is the cost: *"better than many but still kinda boring"* |

Option A (a static `⠏` breathing on the wisp envelope — the first plan's
rec) is **withdrawn**, not merely outranked: its stated justification was
compliance with the rule `#662` corrects, and with that rule gone it is a
progress indicator that never registers progress.

### 7c. Tool rows — native rendering, measured against the real session

His words (2026-07-31): *"the tools [args, response] children, is there a
better way of showing that? If the arguments are empty should hide that
one at the very least. But yeah you are welcome to redesign this part to
be less intrusive and include native / special case rendering for tool
calls we care about."* Hiding empty args is the floor. Which calls earn
special-casing is judged from what the transcripts contain — measured
over the §2 session's 6,439 `tool_use` records (**VERIFIED**, all rows):

| tool | n | share | native fuel in the record |
|---|---|---|---|
| Bash | 5,622 | 87.3% | args `command` + `description`; result `stdout`/`stderr`/`interrupted` — **no exit code is recorded** |
| Edit | 344 | 5.3% | `toolUseResult.structuredPatch` (hunks with `lines`) |
| Read | 185 | 2.9% | `file.filePath`/`numLines`/`startLine`/`totalLines`; result p95 415 kB |
| Write | 150 | 2.3% | `filePath` + `structuredPatch` |
| all others | 138 | 2.1% | playwright 72 (screenshots to 220 kB base64), ToolSearch 24, SendMessage 11, TaskStop 10, Agent 9, TaskList 5, … |

The redesign, from those numbers:

- **The `args`/`response` child pair dies.** A tool step is a **leaf**:
  one thin row; expanding it opens **one body** (the peekbody idiom) with
  the args rendered compactly at top — *when non-empty* — and the result
  below, both lazily fetched by byte range (§3). Two pseudo-rows per tool
  step were a tree level carrying nothing the body does not — across the
  measured session's 6,439 tool steps, ~12,900 chrome rows. Retiring the
  level is also what drops the depth cap to 3 (§7 above).
- **Hide empty args — the floor, measured real:** `TaskList` (5 of 5
  calls) and `browser_close` (2 of 2) take no arguments at all; the
  generic shape rendered an `args` child with literally nothing in it.
- **The four natives** (97.8% of calls between them):
  - **Bash** — label `$ <command>` (truncated ~40ch; args `description`
    as the hover title), the `$` doing the TUI-evocation. Right column:
    stdout line count when clean; `stderr n lines` in `--bad` when
    `is_error` or stderr is non-empty. **Not** `exit 0` — the transcript
    records no exit code (measured; the first mockup invented one). Body:
    stdout tail, stderr first when present.
  - **Edit** — label `edit <basename> (+a −d)`, figures summed from
    `structuredPatch`; body is the real diff, `+`/`−` in `--ok`/`--bad`
    (the mockup's existing peekbody idiom — now verified derivable).
  - **Write** — label `write <basename> · <size>`; body is the
    `structuredPatch` diff when the file existed, else the content head.
  - **Read** — label `read <basename> · <n> lines` (`@<start>` when
    offset); body is the content **head**, never the 415 kB p95 payload.
- **Agent** (9 calls) takes a half-native label — `agent → <name> ·
  <model>` — because its row is `#615`'s mount point: the subagent's own
  tree hangs under the dispatching step once the per-client tasks land.
  Label now, mount later.
- **Everything else** takes the generic leaf: tool name as label, args
  size + result size in the right column, the one-body expansion. Binary
  or base64 result content (playwright screenshots, `isImage`) is
  summarised by size, never inlined. A tool joins the native set when its
  rows earn it in real transcripts, not speculatively.

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
G2 reading. **The second-truth rule does not reach any of this** — he scoped
it 2026-07-31 19:09 (`#614`) to **on-disk master state**, and relaxed the
renderer sentence outright in the same message (canonical: **One fact, one
home on disk**, `DREAMWORK.md` Philosophy). The wrappers are still *derived*
— compiled from the same `client/*.js` `watch.py` already serves, restating
no markup — and new surfaces are still born as components with no builder
twin, but on cost rather than prohibition. For **this** view that is a
distinction without a difference: it is a new surface with no existing
builder, so there is no twin to refuse or to price. **This design was written
before the ruling and
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
(`watch.py:308`) so per-subscriber threads are viable; tool distribution
over the measured session (§7c table — Bash 87.3%, the four natives
97.8%, `TaskList`/`browser_close` the real empty-args cases); Bash
results carry **no exit code** (`stdout`/`stderr`/`interrupted` only);
Edit/Write carry `structuredPatch`, Read carries
`file.numLines`/`startLine`/`totalLines`; the forum peek icon's ratchet
read at source (`_ledger_row.html.erb:6` — `arm += 90; group += 180`,
always clockwise, reduced motion kills only the transition); "never a
spinner" is scoped at both its occurrences (`client/style.css:887` the
wisp — `:884` pre-fix, shifted by the fix's own `:761` insertion — and
`:761` the deploy timeout; `#662`).

**INFERRED (each flagged in place):** the "only via component system"
reading (§8); the v1 tick-delivery deviation from "no polling" (§6);
hidden-chrome suppression (§3); partial-trailing-line handling (§4); the
`#613`/`#614` transport split (§6); POST classification of
`/session/watch` (§6). **Judged rather than asked** (his instruction):
the native set's cut line and label grammar (§7c — the measured four plus
`Agent`); the tally's placement, batching ease, and reduced-motion answer
(§7b). (Guides left this list: `G1` is his call now, 2026-07-31.)

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
4. **Discovery + identity — the environment-variable surface.** RULED and
   built (`#665`): the loop self-reports into `status.json`'s
   `agent_session` at orient, and `client_env.CLIENTS` is the ONE home for
   the variable names. **A client is not supported until a row has been
   MEASURED for it** — an unmeasured client stays absent from the registry
   rather than being guessed at (`plans/harness-containment.md`: *"do not
   invent a capability matrix"*). The measurement is four questions, not
   one, and answering only the first is the trap:

   a. **Which variable carries the session id** — his words, *"identifying
      the best env var to use for session id"*. Verify it against something
      independent rather than accepting a plausible-looking name: for
      Claude Code, `CLAUDE_CODE_SESSION_ID` is the uuid segment of the
      harness scratchpad path, which is how `#652` confirmed it.
   b. **Which sibling variables separate a SUBAGENT from the main agent** —
      the other half of his ask (*"other similar env vars should be
      recorded too so we can have the right info about subagents or
      whatever and not get confused"*). **Never assume the session id does
      this.** For Claude Code it emphatically does not: every concurrent
      lane inherits the SAME `CLAUDE_CODE_SESSION_ID` (`#652`). **And as
      of #678 (measured 2026-07-31), no other variable does either:**
      `CLAUDE_CODE_CHILD_SESSION` — the prior candidate — is present in
      BOTH the coordinator and a real subagent, and `CLAUDE_PID` shares one
      value across both roles (a subagent inherits the CLI process and its
      environment wholesale). So claude-code's registry entry records
      `subagent_var=None`, and `client_env` writes `is_subagent: null`
      (unknown) for this client rather than a confident boolean that would
      mislabel the main agent. **A variable only qualifies as a separator
      after a side-by-side probe has shown it DIFFERS between roles** — and
      "present in a subagent" alone is not that proof, because the
      coordinator's env may carry it too.
   c. **Which variable identifies the CLIENT itself**, and whether a
      harness launched as a CHILD of another client would inherit it. An
      inherited marker makes a registry report the parent; the only real
      defence is the child harness setting its own marker, so this is
      measured rather than assumed. `client_env` refuses (`client: null`)
      when two registry rows match at once instead of picking one.
   d. **What the honest answer is when the client has NO session
      variable** — record it absent, never inferred, which is `#613`'s
      `system_prompt` discipline applied here.
      `client_env.Client(session_id_var=None)` is that state, and it is
      deliberately distinct from an unmeasured client (simply absent from
      the registry).

   Then append the row to `client_env.CLIENTS` with a test asserting its
   measured names. **Still open for `#615` specifically:** how the loop
   learns that client's CHILD session ids (the subagent transcripts of
   point 1). `agent_session` does not answer that — it names the main
   agent's session only.
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

## 12. Numbered landing sequence

Each increment below is a ~15–20 minute landing, not a phase that stays dirty
while its neighbours catch up.  Every one ends with the existing dashboard
working; the first eleven are dark or server-only, and the component is not
made reachable until its complete v1 behaviour has passed in isolation.

The component-system prerequisite is present in the tree, not merely in the
ledger: `dev/build/src/native-entry.js` registers the production `Research`
component, `client/router.js` sends registered authorities through
`dwNative.registry`, and `watch.py` embeds `client/dist/native.js` in the
served page.  The caller inventory below was traced from those running seams.

1. **Standardised wire model — LANDED here as `34208dcd`.** Add the closed
   node/event vocabulary, source ranges, validation and exact wire
   serialisation; nothing imports it in production.
   **Files/callers:** `session_log/{__init__,model}.py` and
   `test_session_log_model.py`; the test is the only caller in this
   increment, while the adapter in increment 2 becomes the first production
   package caller.
   **Proof/red:** `just pytest test_session_log_model.py` (10 tests). Changing
   wire `ref.len` to the Python spelling `length` reds on *"source ref must
   spell its wire length field 'len'"*.  A second injection showed the exact
   happy-path serialisation check stays green when unknown node kinds are
   admitted; the closed-vocabulary test then reds with `DID NOT RAISE
   ModelError`, closing that false-green.
   **Leaves later:** every transcript grammar, scan cursor, store, route,
   watcher and browser consumer.

2. **Claude Code record classifier, still dark.** Add a pure classifier for
   one complete JSONL record: user-turn start, assistant text/thinking/tool,
   tool result, compact boundary/summary, visible system note, or suppressed
   chrome. It extracts timestamps, native tool facts and `SourceRef`, but
   does not build a tree yet.
   **Files/callers:** new `session_log/claude_code.py` and
   `test_session_log_claude_code.py`; the classifier calls
   `session_log.model`, and its fixture test is its only caller.
   **Proof/red:** an exact table over every §2 grammar row, including
   plain-user versus `tool_result` and `isMeta`/`isCompactSummary`. Injecting
   `tool_result` as a user turn must red on *"tool results are steps, not turn
   starts"*; a fixture containing an unknown chrome record must prove it is
   suppressed rather than silently becoming `sys.note`.
   **Leaves later:** parentage, stable ids, bookmarks and incremental state.

3. **Full hierarchy scan, still dark.** Compose classified records into one
   session/page/turn/step tree, pair `tool_use` with `tool_result`, emit
   `open/update/close` events, and produce bookmarks for page and turn starts
   only. This is a from-zero scan; no append cursor yet.
   **Files/callers:** `session_log/claude_code.py` and
   `test_session_log_claude_code.py`; the new `scan_complete` caller set is
   the focused test only, and it calls the increment-2 classifier plus the
   increment-1 model.
   **Proof/red:** a non-trivial frozen transcript asserts the complete ordered
   wire stream, stable ids, parent ids, state transitions, exact line/byte
   refs and the exact bookmark set. Dropping the `requestId/message.id`
   grouping must red by opening two agent turns where the oracle names one;
   counting a tool result as a major event must red the bookmark denominator.
   **Leaves later:** partial tails, resuming and all live consumers.

4. **Incremental cursor and partial-tail equivalence, still dark.** Extend the
   same scanner with `from_byte` state, consuming only newline-terminated
   records and carrying enough frontier state to resume without duplicating a
   node. Concatenated scans must equal one full scan.
   **Files/callers:** `session_log/claude_code.py` and its focused test; the
   test remains the only caller, now exercising both `scan_complete` and
   `scan_incremental` through the same parser.
   **Proof/red:** split a record mid-byte, scan twice, append its remainder and
   require byte-for-byte equality with the one-shot result. Advancing the
   cursor past the unterminated tail must red on *"completed tail record was
   lost"*; replaying the prior complete line must red on duplicate node ids.
   **Leaves later:** source discovery, subscriptions and persistence.

5. **Server-derived session catalogue, still dark.** Extend the existing
   active-session resolver with the switcher catalogue: strict UUID JSONL
   discovery under the measured client root, target-cwd classification,
   mtime/size/liveness metadata, and no browser-supplied path. The recorded
   `agent_session` remains the only active identity; newest-mtime is never
   promoted to identity.
   **Files/callers:** `session_source.py` and `test_session_source.py`.
   Existing callers of `resolve_target` remain `session_source.main` and its
   focused tests; the new catalogue is test-only until `SessionService` calls
   it in increment 6.
   **Proof/red:** fixtures cover a symlinked projects root, two cwd slugs, an
   unrelated target and malformed/non-UUID names. Making newest mtime the
   active choice must red when the recorded id names the older live file;
   returning an absolute path in the wire catalogue must red the confinement
   assertion.
   **Leaves later:** opening or scanning any catalogue entry.

6. **Cold `SessionService`, still dark.** Add one thread-safe service that
   resolves ids through the catalogue, runs the scanner, owns the in-memory
   per-session event ring/cursor, builds a snapshot skeleton and parses a
   bounded peek from a registered source range. It has no file-notification
   thread and no HTTP caller yet.
   **Files/callers:** new `session_log/service.py` and
   `test_session_log_service.py`; the service calls `session_source` and the
   adapter, while its test is its only caller.
   **Proof/red:** register a named fixture and assert the exact snapshot,
   cursor, event replay and structured peek; a client-supplied path must be
   impossible at the API boundary. Replacing id lookup with `Path(id)` must
   red on *"only a discovered session id may select a source"*.
   **Leaves later:** wakeups, retirement, HTTP and the derived store.

7. **`SessionWatcher` and retirement, still dark.** Let the service consume
   a new `SessionWatcher` seam over `file_notify.watch_thread` (the
   thread-native adapter already built for the `ThreadingHTTPServer` world),
   scan from the held cursor on a change, rearm/rescan on `WATCH_LOST` or
   `OVERFLOW`, fan events to subscribers, and stop the handle after the last
   subscriber's bounded idle period.
   **Files/callers:** new `session_log/watcher.py`,
   `session_log/service.py`, `test_session_log_watcher.py` and
   `test_session_log_service.py`; `SessionService.watch` calls
   `SessionWatcher`, which calls `file_notify.watch_thread`, and its callback
   calls the incremental scanner. `file_notify.py` itself is not changed.
   **Proof/red:** every notification measurement uses a real-disk fixture
   under the lane-private cache, never pytest's `/tmp` scratch (#634). Append
   one complete record and require its exact node before the deadline, with
   no sleep-as-assertion; inject watch loss and require a full rescan plus a
   rearmed handle. A tmpfs run is explicitly not acceptable evidence.
   **Leaves later:** HTTP registration and durable bookmarks.

8. **Read routes: list and peek, no page consumer.** Construct one service per
   `make_handler` closure and add `GET /session/list` plus bounded
   `GET /session/peek`. Both run after `_preflight`, expose ids rather than
   paths, and are denied from `summary()`.
   **Files/callers:** `watch.py`, `session_log/service.py`, `test_watch.py` and
   `test_session_log_service.py`. Direct `make_handler` callers that must stay
   green are `watch.main`, the `test_watch` HTTP harnesses,
   `test_user_events_http.HttpHarness`, and `test_reconcile_submissions`.
   **Proof/red:** `just pytest test_session_log_service.py test_watch.py
   test_user_events_http.py test_reconcile_submissions.py`. An invalid Host
   must be rejected before a resolver spy runs; unknown ids, negative/oversize
   ranges and ranges crossing a record must refuse with distinct responses.
   **Leaves later:** registration, event delivery and every UI path.

9. **Registration routes: watch and events, still no page consumer.** Add
   `POST /session/watch` and `GET /session/events`; POST creates only
   in-memory watcher/subscriber state and writes no target file, while events
   return the per-session cursor plus the ordered delta since a caller's
   cursor. Omitting the id selects only the recorded active session. The POST
   is origin-gated as state-changing server work but is dispatched outside
   `WRITE_ROUTE_HANDLERS` and before journal receipt creation: registering a
   reader is not a tenth durable write route.
   **Files/callers:** the same service/handler/test files as increment 8;
   `Handler.do_POST` and `Handler.do_GET` call the service, and the same four
   handler-construction surfaces remain in the verification list.
   **Proof/red:** the route tests assert the full four-route closed set,
   preflight-before-read, an unchanged write-route set, zero journal receipts,
   no target-tree diff, exact current-session default, stale-cursor recovery
   to a full snapshot, and retirement after disconnect.
   Deleting the event-ring append must red on a real-disk transcript append
   with *"watch cursor advanced without delivering its event"*.
   **Leaves later:** cache persistence and browser polling.

10. **Derived bookmark store, deliberately late and dark.** Only after
    **increment 5 of #645** has landed its other-store core routing and the
    no-production-raw-connect guard, add a separate
    `.dreamwork/session-index.sqlite3` `StoreSpec`, initializer and repository
    for the design's `session`/`bookmark` schema. Rebase over whatever later
    #645 work has landed first; do not edit its migration ladder, and never
    place this disposable cache in the durable ledger store.
    **Files/callers:** new `dreamwork_db/session_index.py` and
    `test_session_index.py`; its only caller is the focused test, and all
    connections call `dreamwork_db.core.open_database` rather than
    `sqlite3.connect`. No live database file is created or committed.
    **Proof/red:** use a real-disk private database, assert WAL/timeout policy,
    schema, major-event-only rows, transactional cursor+bookmark writes and
    delete-one-session rebuild. A planted raw `sqlite3.connect` must red the
    #645 increment-5 guard; a rollback injection must leave zero partial rows.
    **Leaves later:** the service continues to work from memory until the next
    increment, so a wrong cache cannot affect the dashboard.

11. **Cache integration with rescan as the safe answer.** Inject the index
    repository into `SessionService`: validate device/inode/first-line
    signature and the bookmarked record, resume from a valid cursor, and drop
    one session's rows then full-rescan on any mismatch. Route wire behaviour
    remains identical to increments 8–9.
    **Files/callers:** `session_log/service.py`,
    `dreamwork_db/session_index.py`, `test_session_log_service.py`,
    `test_session_index.py` and the route cases in `test_watch.py`; handler
    GET/POST callers now reach the store only through the service.
    **Proof/red:** restart a service over a real-disk fixture and require the
    same snapshot/cursor without duplicate events; replace the inode, alter
    the first line, and corrupt a bookmarked byte in three separate cases and
    require the exact full-rescan result. Trusting the stale offset must red on
    a stable-id mismatch, not merely on a changed row count.
    **Leaves later:** no component consumes the API yet.

12. **Client event reducer, bundled but unreachable.** Add a pure client-side
    reducer for snapshots plus `open/update/close`, keyed by stable node id;
    it derives the frontier, tracks explicit hand-open/hand-closed ids and can
    reattach follow without knowing any transcript grammar.
    **Files/callers:** new `dev/build/src/session-state.js`, export-only wiring
    in `dev/build/src/native-entry.js`, `watch.py`'s literal `DATA_SIBLINGS`,
    generated `client/dist/{native.js,manifest.json}`, a focused capture
    probe, its `justfile` registration, and `test_client_assets.py`/
    `test_client_dist.py`/`test_deploy_state.py`/`test_lint.py`. The build
    entry is its only production importer; no registry entry calls it.
    **Proof/red:** `just build-client`, the three targeted pytest files and the
    reducer probe. Reorder/update fixtures assert identity rather than array
    position; an injection that auto-closes a hand-open node when the frontier
    moves must red on *"manual disclosure survived the event"*. Dist hashes
    and deploy sibling completeness bind the committed artifact.
    **Leaves later:** DOM, fetches and a route.

13. **`SessionLog` rendering, still unregistered.** Build the thin three-level
    tree, G1 guides, M1 chevrons, session switcher, native Bash/Edit/Write/Read
    rows, generic leaf fallback, one body slot, tally glyph and all empty/
    absent/stale/error states from passed-in snapshot state. Export a test
    registration function but do not call it in production.
    **Files/callers:** new `dev/build/src/session-log.js`, scoped rules in
    `client/style.css`, export wiring and `DATA_SIBLINGS`, rebuilt dist/
    manifest, `dev/capture/sessionlog.mjs`, `justfile`,
    `test_client_assets.py`, `test_client_dist.py`, `test_deploy_state.py` and
    `test_lint.py`. `native-entry.js` imports the component, but the production
    registry still has no `session` authority.
    **Proof/red:** the focused guard manually registers the export against a
    frozen snapshot and asserts exact depth, guides/markers, no `args` or
    `response` pseudo-rows, empty args absent, binary results summarized, and
    reduced motion changing the tally discretely with no animation. Removing
    the native Bash renderer must red on the literal `$ command` assertion.
    **Leaves later:** network registration, live deltas, peek and production
    routing.

14. **Live controller and existing-tick pulse, still unregistered.** Add the
    component controller for list/watch/events/peek, feed deltas through the
    reducer, move the frontier with height travel, preserve manual disclosure,
    implement follow and lazy body fetch, and extend the registry with an
    optional `pulse` callback invoked by the router's existing two-second
    tick. No second timer and no `/data.json` dependency are introduced.
    **Files/callers:** `dev/build/src/{session-log,registry}.js`,
    `client/router.js`, rebuilt dist/manifest, the session-log and coexistence
    captures, `test_client_dist.py` and `test_watch.py`. `tick` calls
    `registry.pulse`; existing callers of `tick` are its page timer plus
    `sendAsk`, `sendChatArchive` and `sendChatReply`. With no production
    `session` entry yet, the new call is an inert empty iteration.
    **Proof/red:** the focused guard registers the test export, changes a
    real-disk transcript while target mtime stays fixed, and requires one new
    row through the existing tick, no extra timer, the prior frontier folded,
    a hand-open row preserved, and exactly one bounded peek on expansion.
    Removing `registry.pulse` must red on *"transcript event arrived without a
    target-tree mtime change"*; coexistence/research guards prove existing
    native and builder routes are untouched.
    **Leaves later:** only the production route binding.

15. **Atomic production activation.** Register `SessionLog` in
    `native-entry.js`, teach `routeOf` and every governed route-title/token
    table about `/session`, serve the same shell for that deep link, and add
    the one navigation affordance. There is deliberately no `buildSessionLog`
    in `client/views.js`: the surface is available only through the component
    registry, with no builder twin to diverge.
    **Files/callers:** `dev/build/src/native-entry.js`, `client/router.js`,
    `client/views.js` (the dashboard navigation link only), `watch.py`,
    rebuilt dist/manifest,
    `test_watch.py`, `test_client_dist.py`, `test_client_assets.py`,
    `test_deploy_state.py`, `test_lint.py`, and the focused session/coexistence/
    research captures. `buildDashboard` is called by `buildCurrent`; `routeOf`
    is called by router initialisation/navigation;
    `commitCurrent` is called by `navigate` and `crossfade`; `setData` is
    called by `ensureData`, burn-step cycling and `tick`; `_get_page` is called
    by `make_handler` and page-assembly tests.
    **Proof/red:** `/session` must return the common shell, resolve to exactly
    one registry authority, register the recorded active session, paint the
    snapshot, receive a real-disk appended event, lazy-peek one body, survive
    navigation away/back with zero detached roots, and leave every existing
    route green. Unregistering `session` while retaining `routeOf` must red on
    the authority assertion rather than silently render the dashboard.
    **Leaves later:** websocket/delta push, per-client child-session mounts,
    search/filtering and hidden chrome remain the explicit v1 non-goals.
